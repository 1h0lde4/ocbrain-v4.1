"""
core/cognitive/compiler.py — Plan Compilation.

Packet: Packet 06 — Plan Compilation.

Architecture:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §6  (Execution Plans — PlanStep / ExecutionPlan / lifecycle)
        §12 (Event Integration — cognitive.plan_compiled, cognitive.plan_rejected)
        §15 (Governance Integration — the plan_compile gate)
        §16 (Runtime Invariants — "every plan has a goal", "planning
             never executes", "the Cognitive Runtime never bypasses
             Governance")
    docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md
        §1  (Top-Level Specification — "Full public surface, fixed at
             three: interpret(), plan(), compile()."; the single seam
             ExecutionPlan -> Plan Compilation -> WorkflowDefinition ->
             Kernel execution)
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 06 — Plan Compilation (module, dependencies, scope,
        explicitly-forbidden list, completion criteria)

Scope (from the Packet 06 spec):
    compile(plan: ExecutionPlan) -> CompilationResult, the third and
    final public Cognitive Front-End entrypoint. Maps ExecutionPlan
    steps onto WorkflowDefinition nodes/edges and evaluates a governance
    gate (action_type="plan_compile") before ever producing a
    WorkflowDefinition. This is the single seam between reasoning
    (Cognitive Front-End) and execution (Kernel) — nothing on either
    side of this module is this packet's concern.

Explicitly forbidden (K4 §16, Packet 06 spec, Evolution Directive):
    - Reasoning ("execution never plans"; compilation does not re-plan,
      re-sequence, or re-decompose what Planner already produced)
    - Capability invocation (no AdapterRuntime call of any kind)
    - Capability *selection* (choosing which concrete adapter satisfies
      a capability_type) — reserved exclusively for the future
      Cognitive Runtime (C-MoE); see _compile_step()
    - Memory writes beyond governance's own audit trail

Explicitly NOT in scope (later packets / future work):
    - WorkflowRuntime execution of the produced WorkflowDefinition
    - SupervisorWorker's handling of an ESCALATE/REJECT outcome, or
      resubmission of a revised plan (Packet 08)
    - Reflection / evaluation of a compiled plan (Packet 07)
    - Resolving capability_type to a concrete registered WorkerRegistry
      entry (future C-MoE; no such resolution mechanism exists anywhere
      in this repository today)
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.cognitive.planner import ClarificationPolicy, ExecutionPlan, PlanStep
from core.events.event_stream import EventStream, get_event_stream
from core.governance.governance_kernel import (
    GovernanceAction,
    GovernanceKernel,
    GovernanceResult,
    GovernanceVerdict,
    get_governance_kernel,
)
from core.workflow.definition import (
    RetryPolicy,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)

_COMPILER_ID = "PlanCompiler"


class CompilationStatus:
    """Status values for CompilationResult.

    Mirrors PlannerStatus's established shape (core/cognitive/planner.py)
    one level down the pipeline: a structural precheck outcome distinct
    from the two possible governance verdicts that can also prevent a
    WorkflowDefinition from being produced.
    """

    COMPILED = "compiled"
    REJECTED_PRECHECK = "rejected_precheck"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass
class CompilationResult:
    """Output of compile().

    K4.2 §1's frozen public surface names the entrypoint
    ``compile(plan) -> WorkflowDefinition``, but — exactly as K4.2.5
    already formalized K4 §5's illustrative ``plan(goal) -> ExecutionPlan``
    into the real ``plan(request) -> PlannerResult`` — that signature is
    illustrative, not literal: REJECT and ESCALATE governance verdicts,
    and a failed structural precheck, must all be expressible without
    raising and without a WorkflowDefinition ever existing. This class
    is that formalization, mirroring PlannerResult's shape one seam
    later in the pipeline.

    Fields:
        status: one of CompilationStatus's four values.
        workflow_definition: populated only when status == "compiled".
        governance_result: populated only when status is "rejected" or
            "escalated" — i.e. governance actually ran and returned a
            verdict. Always None for "rejected_precheck", which never
            reaches governance (K4 §16's goal-reference / structural
            checks are Plan Compiler's own invariant, not a
            GovernanceVerdict).
        precheck_errors: populated only when status == "rejected_precheck".
            Either the structural precheck's own findings, or (in the
            defensive fallback case) the underlying
            WorkflowDefinition.validate() errors.
    """

    status: str = CompilationStatus.COMPILED
    workflow_definition: Optional[WorkflowDefinition] = None
    governance_result: Optional[GovernanceResult] = None
    precheck_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _validate_plan_structure(plan: ExecutionPlan) -> List[str]:
    """Structural precheck, run before governance is ever consulted.

    K4 §16: "Every plan has a goal ... Enforced structurally:
    ExecutionPlan.goal_id is non-optional; Plan Compiler refuses a plan
    with no goal reference." That is the one structural rule the
    architecture names explicitly.

    The other two checks below are not separately cited in the
    architecture text — they are implementation judgment, documented
    here rather than silently assumed, because they are the minimum
    precondition for *any* WorkflowDefinition this module produces to
    satisfy WorkflowDefinition's own, already-existing .validate():
    an entry_node cannot be derived from zero steps, and node identity
    is undefined if two steps share a step_id. Both are exactly what
    this packet's own completion criterion — "produces a valid
    WorkflowDefinition" — already requires; neither is reasoning about
    plan *content*, only about whether compilation can be attempted at
    all.
    """
    errors: List[str] = []
    if not plan.goal_id:
        errors.append(
            "ExecutionPlan.goal_id is required (K4 \u00a716: "
            "\"every plan has a goal\")"
        )
    if not plan.steps:
        errors.append(
            "ExecutionPlan.steps must be non-empty — an entry_node "
            "cannot be derived from zero steps"
        )
    seen_ids: set = set()
    for step in plan.steps:
        if step.step_id in seen_ids:
            errors.append(f"Duplicate PlanStep.step_id: '{step.step_id}'")
        seen_ids.add(step.step_id)
    return errors


def _compile_step(step: PlanStep) -> WorkflowNode:
    """Maps one PlanStep onto one WorkflowNode.

    K4 §6: "PlanStep maps onto WorkflowNode roughly 1:1 (WorkflowNode is
    confirmed minimal: node_id, worker_type, config, retry_policy,
    error_branch — one worker per node)."

    worker_type is PlanStep.capability_type carried through unchanged,
    not resolved to a concrete registered WorkerRegistry entry. This is
    deliberate, not an oversight. PlanStep's own docstring
    (core/cognitive/planner.py) states that "which specific WorkerType
    executes a given capability_type is Compilation's job" — but
    resolving capability_type to a *specific* adapter is capability
    *selection*, which this packet's own "Explicitly forbidden" list and
    the Evolution Directive reserve exclusively for the future Cognitive
    Runtime (C-MoE). No such resolution mechanism exists anywhere in the
    repository today: WorkerRegistry (core/runtime/worker_registry.py)
    is a static, explicit, composition-root-populated map with worker
    classes as values (PlannerWorker, MemoryCuratorWorker) — neither a
    capability_type is a registered worker_type, nor does any lookup
    table between the two exist. Carrying the label forward unchanged is
    the narrowest mechanical translation available: no ranking, no
    scoring, no choice among alternatives (Planner already committed to
    exactly one capability_type per step) — a structural rename, not
    reasoning or selection.
    """
    return WorkflowNode(
        node_id=step.step_id,
        worker_type=step.capability_type,
        config={
            "description": step.description,
            "capability_type": step.capability_type,
        },
        retry_policy=RetryPolicy(),
        error_branch=step.error_branch or "",
    )


def _compile_workflow(plan: ExecutionPlan) -> WorkflowDefinition:
    """Builds the WorkflowDefinition for an already precheck-validated plan.

    K4 §6: ExecutionPlan.steps is ordered; edges here are exactly that
    order, carried forward unchanged. Planner's own _sequence() (Packet
    03 / K4.2.5) already committed to a specific sequence — K4 §16's
    "planning never executes" extends symmetrically to "compilation
    never re-plans": this function does not re-sequence, branch, or
    otherwise reason about the steps it is given, only translate them.

    Precondition: plan has already passed _validate_plan_structure()
    (non-empty steps, unique step_ids) — callers must not call this
    directly on unvalidated input.
    """
    nodes = [_compile_step(step) for step in plan.steps]
    edges = [
        WorkflowEdge(
            from_node=plan.steps[i].step_id,
            to_node=plan.steps[i + 1].step_id,
        )
        for i in range(len(plan.steps) - 1)
    ]
    return WorkflowDefinition(
        workflow_id=plan.resource_id,
        name=f"plan:{plan.goal_id}",
        nodes=nodes,
        edges=edges,
        entry_node=plan.steps[0].step_id,
        metadata={
            "execution_plan_id": plan.resource_id,
            "goal_id": plan.goal_id,
            "confidence": plan.confidence,
        },
    )


async def compile(  # noqa: A001 — name is frozen by K4.2 §1's public surface
    plan: ExecutionPlan,
    *,
    event_stream: Optional[EventStream] = None,
    governance: Optional[GovernanceKernel] = None,
    clarification_policy: Optional[ClarificationPolicy] = None,
    clarification_attempt: int = 0,
) -> CompilationResult:
    """Plan Compiler's top-level entry point: ExecutionPlan -> CompilationResult.

    This is the third of the three public Cognitive Front-End entrypoints
    (K4.2 §1: interpret(), plan(), compile()) and the single seam through
    which the Front-End's reasoning can ever have a real-world effect
    (K4.2 §1/§6).

    Sequence:
        1. Structural precheck (K4 §16) — no goal_id, no steps, or
           duplicate step_ids short-circuits before governance is ever
           consulted, mirroring how Planner's own rejected_precheck path
           (core/cognitive/planner.py) short-circuits before decomposition.
        2. Governance gate (K4 §15) — constructs
           GovernanceAction(action_type="plan_compile", metadata={...})
           and calls GovernanceKernel.evaluate_action(). This reuses the
           exact, already-proven AbstractCognitiveWorker.execute() pattern
           (core/workers/base.py) rather than introducing a new
           governance mechanism: REJECT and ESCALATE both short-circuit,
           both emit cognitive.plan_rejected (K4 §12 — the same event
           name covers both verdicts at this gate), and no
           WorkflowDefinition is ever produced for either. Passing
           "confidence" in the action metadata is what lets
           OrchestrationGovernor's existing ClarificationPolicy rule
           (built in Packet 03 / K4.2.5 specifically for this later
           gate — see k4_2_5_completion_report.md and K4.2 §2) actually
           fire: below clarification_policy.confidence_threshold escalates
           while clarification_attempt < max_escalations, and rejects
           once the bound is reached — the same bounded-retry mechanics
           already reviewed and tested for Planner's own worker_type
           check, applied here to the plan as a whole.
        3. Compilation (K4 §6) — only reached on GovernanceVerdict.APPROVE.
           Maps steps to nodes/edges (_compile_workflow), defensively
           re-validates the result via WorkflowDefinition's own
           .validate() (structurally unreachable given step 1's checks,
           except for a dangling error_branch reference), and emits
           cognitive.plan_compiled (K4 §12) on success.

    clarification_attempt exists so a future caller (SupervisorWorker,
    Packet 08 — not built by this packet) can call compile() again for a
    revised plan with an incrementing attempt count, without Plan
    Compiler itself needing to hold any state across calls: this function
    is stateless by design (no hidden mutable state, per
    docs/architecture/PROJECT_INSTRUCTIONS.md's Forbidden Practices).

    Note on the name: `compile` shadows the Python builtin of the same
    name within this module's namespace. This is intentional, not an
    oversight — K4.2 §1 fixes the three public entrypoint names, and
    `compile` is not renameable. The builtin is not used anywhere in
    this module.
    """
    event_stream = event_stream or get_event_stream()
    governance = governance or get_governance_kernel()
    clarification_policy = clarification_policy or ClarificationPolicy()

    structural_errors = _validate_plan_structure(plan)
    if structural_errors:
        return CompilationResult(
            status=CompilationStatus.REJECTED_PRECHECK,
            precheck_errors=structural_errors,
        )

    action = GovernanceAction(
        action_type="plan_compile",
        worker_id=_COMPILER_ID,
        description=(
            f"Compile ExecutionPlan {plan.resource_id} "
            f"({len(plan.steps)} step(s)) for goal {plan.goal_id}"
        ),
        metadata={
            "goal_id": plan.goal_id,
            "confidence": plan.confidence,
            "step_count": len(plan.steps),
            "confidence_threshold": clarification_policy.confidence_threshold,
            "clarification_attempt": clarification_attempt,
            "max_escalations": clarification_policy.max_escalations,
        },
    )
    gov_result = governance.evaluate_action(action)

    if gov_result.verdict in (GovernanceVerdict.REJECT, GovernanceVerdict.ESCALATE):
        await event_stream.append(
            event_type="cognitive.plan_rejected",
            source=_COMPILER_ID,
            payload={
                "execution_plan_id": plan.resource_id,
                "goal_id": plan.goal_id,
                "verdict": gov_result.verdict.value,
                "reason": gov_result.reason,
                "governor": gov_result.governor,
            },
        )
        status = (
            CompilationStatus.REJECTED
            if gov_result.verdict == GovernanceVerdict.REJECT
            else CompilationStatus.ESCALATED
        )
        return CompilationResult(status=status, governance_result=gov_result)

    workflow_definition = _compile_workflow(plan)
    validation_errors = workflow_definition.validate()
    if validation_errors:
        # Defensive fallback (Elite Engineering Execution Mode §20.4):
        # structurally unreachable given _validate_plan_structure's own
        # preconditions, except for a dangling error_branch reference (a
        # step_id an error_branch points to that is not present in this
        # plan's own steps). Surfaced the same way any other structural
        # defect is here, rather than silently returning a
        # WorkflowDefinition that WorkflowRuntime would later reject on
        # its own with less context.
        return CompilationResult(
            status=CompilationStatus.REJECTED_PRECHECK,
            precheck_errors=validation_errors,
        )

    await event_stream.append(
        event_type="cognitive.plan_compiled",
        source=_COMPILER_ID,
        payload={
            "execution_plan_id": plan.resource_id,
            "workflow_id": workflow_definition.workflow_id,
            "goal_id": plan.goal_id,
            "node_count": len(workflow_definition.nodes),
        },
    )
    return CompilationResult(
        status=CompilationStatus.COMPILED,
        workflow_definition=workflow_definition,
    )
