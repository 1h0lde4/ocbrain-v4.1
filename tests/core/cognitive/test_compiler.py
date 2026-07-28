"""
tests/core/cognitive/test_compiler.py — Packet 06 Tests.

Architecture Sources:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §6 (Execution Plans), §12 (Event Integration),
        §15 (Governance Integration), §16 (Runtime Invariants)
    docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md
        §1 (Top-Level Specification)
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 06 — Plan Compilation

Coverage:
    - CompilationResult / CompilationStatus shape
    - _validate_plan_structure(): missing goal_id, empty steps, duplicate
      step_ids, and the case with no errors
    - _compile_step(): PlanStep -> WorkflowNode field-by-field mapping
    - _compile_workflow(): node/edge/entry_node assembly, single- and
      multi-step plans, provenance metadata
    - compile(): rejected_precheck path (no governance call, no event)
    - compile(): APPROVE path -> valid WorkflowDefinition,
      cognitive.plan_compiled emitted
    - compile(): ESCALATE path (low confidence, attempt < max_escalations)
      -> cognitive.plan_rejected, no WorkflowDefinition
    - compile(): REJECT path (low confidence, attempt >= max_escalations)
      -> cognitive.plan_rejected, no WorkflowDefinition
    - compile(): custom ClarificationPolicy honored; governance
      dependency injection honored
    - Architecture compliance: no forbidden imports/calls (capability
      invocation, capability selection, memory writes, workflow execution)
"""
import ast
import dataclasses

import pytest

from core.cognitive.compiler import (
    CompilationResult,
    CompilationStatus,
    _compile_step,
    _compile_workflow,
    _validate_plan_structure,
    compile as compile_plan,
)
from core.cognitive.planner import ClarificationPolicy, ExecutionPlan, PlanStep
from core.governance.governance_kernel import GovernanceResult, GovernanceVerdict
from core.workflow.definition import WorkflowDefinition, WorkflowNode


class MockEventStream:
    """Minimal EventStream double, mirroring
    tests/core/cognitive/test_planner.py's own helper of the same shape."""

    def __init__(self):
        self.events = []

    async def append(self, event_type, source, payload):
        self.events.append(
            {"event_type": event_type, "source": source, "payload": payload}
        )


def _make_plan(
    goal_id: str = "goal-1",
    steps=None,
    confidence: float = 0.9,
) -> ExecutionPlan:
    if steps is None:
        steps = [
            PlanStep(
                step_id="step-1",
                description="do a thing",
                capability_type="llm_completion",
            )
        ]
    return ExecutionPlan(
        goal_id=goal_id,
        steps=steps,
        confidence=confidence,
        derived_from=[goal_id] if goal_id else [],
    )


# ─────────────────────────────────────────────────────────────────────────
# CompilationStatus / CompilationResult — shape
# ─────────────────────────────────────────────────────────────────────────


class TestCompilationResultDataclass:
    def test_default_values(self):
        result = CompilationResult()
        assert result.status == CompilationStatus.COMPILED
        assert result.workflow_definition is None
        assert result.governance_result is None
        assert result.precheck_errors == []

    def test_status_values_are_distinct_strings(self):
        values = {
            CompilationStatus.COMPILED,
            CompilationStatus.REJECTED_PRECHECK,
            CompilationStatus.REJECTED,
            CompilationStatus.ESCALATED,
        }
        assert len(values) == 4

    def test_to_dict(self):
        result = CompilationResult(status=CompilationStatus.COMPILED)
        as_dict = result.to_dict()
        assert as_dict["status"] == "compiled"
        assert "workflow_definition" in as_dict


# ─────────────────────────────────────────────────────────────────────────
# _validate_plan_structure — K4 §16 "every plan has a goal" + structural
# soundness required for "produces a valid WorkflowDefinition"
# ─────────────────────────────────────────────────────────────────────────


class TestValidatePlanStructure:
    def test_valid_plan_has_no_errors(self):
        assert _validate_plan_structure(_make_plan()) == []

    def test_missing_goal_id_is_rejected(self):
        errors = _validate_plan_structure(_make_plan(goal_id=""))
        assert any("goal_id" in e for e in errors)

    def test_empty_steps_is_rejected(self):
        errors = _validate_plan_structure(_make_plan(steps=[]))
        assert any("steps" in e for e in errors)

    def test_duplicate_step_ids_are_rejected(self):
        steps = [
            PlanStep(step_id="dup", description="a", capability_type="llm_completion"),
            PlanStep(step_id="dup", description="b", capability_type="llm_completion"),
        ]
        errors = _validate_plan_structure(_make_plan(steps=steps))
        assert any("dup" in e for e in errors)

    def test_multiple_structural_errors_all_reported(self):
        errors = _validate_plan_structure(_make_plan(goal_id="", steps=[]))
        assert len(errors) == 2


# ─────────────────────────────────────────────────────────────────────────
# _compile_step — PlanStep -> WorkflowNode, K4 §6 "roughly 1:1"
# ─────────────────────────────────────────────────────────────────────────


class TestCompileStep:
    def test_returns_workflow_node(self):
        step = PlanStep(step_id="s1", description="do X", capability_type="llm_completion")
        assert isinstance(_compile_step(step), WorkflowNode)

    def test_node_id_from_step_id(self):
        step = PlanStep(step_id="s1", description="do X", capability_type="llm_completion")
        assert _compile_step(step).node_id == "s1"

    def test_worker_type_carries_capability_type_unchanged(self):
        step = PlanStep(step_id="s1", description="do X", capability_type="llm_completion")
        assert _compile_step(step).worker_type == "llm_completion"

    def test_config_carries_description_and_capability_type(self):
        step = PlanStep(step_id="s1", description="do X", capability_type="llm_completion")
        node = _compile_step(step)
        assert node.config["description"] == "do X"
        assert node.config["capability_type"] == "llm_completion"

    def test_error_branch_passthrough_when_set(self):
        step = PlanStep(
            step_id="s1", description="do X", capability_type="llm_completion",
            error_branch="s2",
        )
        assert _compile_step(step).error_branch == "s2"

    def test_none_error_branch_becomes_empty_string(self):
        step = PlanStep(
            step_id="s1", description="do X", capability_type="llm_completion",
            error_branch=None,
        )
        assert _compile_step(step).error_branch == ""

    def test_default_retry_policy_applied(self):
        step = PlanStep(step_id="s1", description="do X", capability_type="llm_completion")
        node = _compile_step(step)
        assert node.retry_policy.max_retries == 0


# ─────────────────────────────────────────────────────────────────────────
# _compile_workflow — full assembly
# ─────────────────────────────────────────────────────────────────────────


class TestCompileWorkflow:
    def test_single_step_plan_produces_valid_workflow(self):
        wd = _compile_workflow(_make_plan())
        assert len(wd.nodes) == 1
        assert wd.entry_node == "step-1"
        assert wd.edges == []
        assert wd.validate() == []

    def test_multi_step_plan_produces_sequential_edges(self):
        steps = [
            PlanStep(step_id="a", description="first", capability_type="llm_completion"),
            PlanStep(step_id="b", description="second", capability_type="llm_completion"),
            PlanStep(step_id="c", description="third", capability_type="llm_completion"),
        ]
        wd = _compile_workflow(_make_plan(steps=steps))
        assert len(wd.nodes) == 3
        assert wd.entry_node == "a"
        assert [(e.from_node, e.to_node) for e in wd.edges] == [("a", "b"), ("b", "c")]
        assert wd.validate() == []

    def test_workflow_id_traces_to_execution_plan_resource_id(self):
        plan = _make_plan()
        assert _compile_workflow(plan).workflow_id == plan.resource_id

    def test_metadata_carries_provenance(self):
        plan = _make_plan(goal_id="goal-42")
        wd = _compile_workflow(plan)
        assert wd.metadata["goal_id"] == "goal-42"
        assert wd.metadata["execution_plan_id"] == plan.resource_id
        assert wd.metadata["confidence"] == plan.confidence

    def test_returns_workflow_definition_instance(self):
        assert isinstance(_compile_workflow(_make_plan()), WorkflowDefinition)


# ─────────────────────────────────────────────────────────────────────────
# compile() — structural precheck path (before governance)
# ─────────────────────────────────────────────────────────────────────────


class TestCompilePrecheckRejection:
    @pytest.mark.asyncio
    async def test_missing_goal_id_short_circuits_before_governance(self):
        plan = _make_plan(goal_id="")

        class ExplodingGovernance:
            def evaluate_action(self, action):
                raise AssertionError("governance must not be consulted on precheck failure")

        events = MockEventStream()
        result = await compile_plan(plan, event_stream=events, governance=ExplodingGovernance())
        assert result.status == CompilationStatus.REJECTED_PRECHECK
        assert result.workflow_definition is None
        assert result.governance_result is None
        assert events.events == []

    @pytest.mark.asyncio
    async def test_empty_steps_short_circuits(self):
        plan = _make_plan(steps=[])
        result = await compile_plan(plan, event_stream=MockEventStream())
        assert result.status == CompilationStatus.REJECTED_PRECHECK
        assert any("steps" in e for e in result.precheck_errors)

    @pytest.mark.asyncio
    async def test_duplicate_step_ids_short_circuits(self):
        steps = [
            PlanStep(step_id="dup", description="a", capability_type="llm_completion"),
            PlanStep(step_id="dup", description="b", capability_type="llm_completion"),
        ]
        plan = _make_plan(steps=steps)
        result = await compile_plan(plan, event_stream=MockEventStream())
        assert result.status == CompilationStatus.REJECTED_PRECHECK


# ─────────────────────────────────────────────────────────────────────────
# compile() — governance APPROVE path
# ─────────────────────────────────────────────────────────────────────────


class TestCompileApproved:
    @pytest.mark.asyncio
    async def test_high_confidence_plan_compiles(self):
        plan = _make_plan(confidence=0.9)
        result = await compile_plan(plan, event_stream=MockEventStream())
        assert result.status == CompilationStatus.COMPILED
        assert isinstance(result.workflow_definition, WorkflowDefinition)
        assert result.workflow_definition.validate() == []
        assert result.governance_result is None

    @pytest.mark.asyncio
    async def test_emits_plan_compiled_event_with_no_prior_events(self):
        plan = _make_plan(confidence=0.9)
        events = MockEventStream()
        await compile_plan(plan, event_stream=events)
        assert len(events.events) == 1
        assert events.events[0]["event_type"] == "cognitive.plan_compiled"
        assert events.events[0]["source"] == "PlanCompiler"
        assert events.events[0]["payload"]["goal_id"] == plan.goal_id

    @pytest.mark.asyncio
    async def test_confidence_exactly_at_threshold_compiles(self):
        policy = ClarificationPolicy()
        plan = _make_plan(confidence=policy.confidence_threshold)
        result = await compile_plan(plan, event_stream=MockEventStream())
        assert result.status == CompilationStatus.COMPILED


# ─────────────────────────────────────────────────────────────────────────
# compile() — governance ESCALATE / REJECT paths (ClarificationPolicy,
# K4.2.5's own mechanism, invoked here per K4 §15)
# ─────────────────────────────────────────────────────────────────────────


class TestCompileGovernanceEscalation:
    @pytest.mark.asyncio
    async def test_low_confidence_escalates_within_bound(self):
        plan = _make_plan(confidence=0.2)
        result = await compile_plan(
            plan, event_stream=MockEventStream(), clarification_attempt=0
        )
        assert result.status == CompilationStatus.ESCALATED
        assert result.workflow_definition is None
        assert result.governance_result.verdict == GovernanceVerdict.ESCALATE

    @pytest.mark.asyncio
    async def test_escalation_emits_plan_rejected_event(self):
        plan = _make_plan(confidence=0.2)
        events = MockEventStream()
        await compile_plan(plan, event_stream=events, clarification_attempt=0)
        assert len(events.events) == 1
        assert events.events[0]["event_type"] == "cognitive.plan_rejected"
        assert events.events[0]["payload"]["verdict"] == "escalate"

    @pytest.mark.asyncio
    async def test_repeated_low_confidence_beyond_bound_rejects(self):
        plan = _make_plan(confidence=0.2)
        policy = ClarificationPolicy()
        result = await compile_plan(
            plan,
            event_stream=MockEventStream(),
            clarification_attempt=policy.max_escalations,
        )
        assert result.status == CompilationStatus.REJECTED
        assert result.governance_result.verdict == GovernanceVerdict.REJECT
        assert result.workflow_definition is None

    @pytest.mark.asyncio
    async def test_rejection_emits_plan_rejected_event(self):
        plan = _make_plan(confidence=0.2)
        policy = ClarificationPolicy()
        events = MockEventStream()
        await compile_plan(
            plan,
            event_stream=events,
            clarification_attempt=policy.max_escalations,
        )
        assert len(events.events) == 1
        assert events.events[0]["event_type"] == "cognitive.plan_rejected"
        assert events.events[0]["payload"]["verdict"] == "reject"

    @pytest.mark.asyncio
    async def test_custom_clarification_policy_is_honored(self):
        plan = _make_plan(confidence=0.6)
        strict_policy = ClarificationPolicy(confidence_threshold=0.8, max_escalations=1)
        result = await compile_plan(
            plan,
            event_stream=MockEventStream(),
            clarification_policy=strict_policy,
        )
        # 0.6 < 0.8 under the caller's stricter policy, first attempt -> escalate
        assert result.status == CompilationStatus.ESCALATED


# ─────────────────────────────────────────────────────────────────────────
# compile() — governance dependency injection
# ─────────────────────────────────────────────────────────────────────────


class TestCompileGovernanceInjection:
    @pytest.mark.asyncio
    async def test_injected_governance_kernel_is_consulted_with_correct_action(self):
        plan = _make_plan(confidence=0.9)

        class StubGovernance:
            def __init__(self):
                self.received_action = None

            def evaluate_action(self, action):
                self.received_action = action
                return GovernanceResult(
                    verdict=GovernanceVerdict.REJECT,
                    reason="stub reject",
                    governor="Stub",
                )

        stub = StubGovernance()
        result = await compile_plan(plan, event_stream=MockEventStream(), governance=stub)

        assert result.status == CompilationStatus.REJECTED
        assert stub.received_action is not None
        assert stub.received_action.action_type == "plan_compile"
        assert stub.received_action.metadata["goal_id"] == plan.goal_id
        assert stub.received_action.metadata["step_count"] == len(plan.steps)
        assert stub.received_action.metadata["confidence"] == plan.confidence

    @pytest.mark.asyncio
    async def test_default_governance_kernel_used_when_not_supplied(self):
        # No governance kwarg: falls back to get_governance_kernel(), exercising
        # the real GovernanceKernel end to end for a high-confidence plan.
        plan = _make_plan(confidence=0.95)
        result = await compile_plan(plan, event_stream=MockEventStream())
        assert result.status == CompilationStatus.COMPILED


# ─────────────────────────────────────────────────────────────────────────
# Architecture compliance
# ─────────────────────────────────────────────────────────────────────────


def _real_code_identifiers(filepath: str) -> set:
    """Names actually used as code in a module: imports, bare names, and
    attribute accesses. Mirrors tests/core/cognitive/test_planner.py's
    helper of the same name/purpose verbatim (not imported cross-module,
    consistent with that file's own choice to keep this local rather than
    factor it into a shared test-utilities module).

    Deliberately excludes docstrings and comments: a raw substring search
    over the whole file text false-positives on this module's own
    extensive docstrings, which name AdapterRuntime, UnifiedMemory, and
    CapabilityRegistry specifically in order to disclaim them.
    """
    tree = ast.parse(open(filepath).read())
    identifiers: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                identifiers.add(alias.name.split(".")[-1])
                if alias.asname:
                    identifiers.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                identifiers.add(alias.name)
                if alias.asname:
                    identifiers.add(alias.asname)
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
    return identifiers


class TestArchitectureCompliance:
    """Verify Packet 06 does not violate architectural boundaries."""

    def test_no_capability_invocation_or_selection(self):
        """Packet 06 spec / Evolution Directive: capability invocation and
        capability selection are both forbidden in Plan Compilation."""
        import core.cognitive.compiler as mod

        identifiers = _real_code_identifiers(mod.__file__)
        assert "AdapterRuntime" not in identifiers
        assert "invoke" not in identifiers  # no real .invoke(...) call
        assert "CapabilityRegistry" not in identifiers

    def test_no_memory_writes(self):
        """K4 §1: the Cognitive Front-End never writes to UnifiedMemory."""
        import core.cognitive.compiler as mod

        identifiers = _real_code_identifiers(mod.__file__)
        assert "UnifiedMemory" not in identifiers

    def test_no_workflow_execution(self):
        """K4 §16: 'planning never executes' extends to compilation —
        Plan Compiler produces a WorkflowDefinition, it never runs one."""
        import core.cognitive.compiler as mod

        identifiers = _real_code_identifiers(mod.__file__)
        assert "WorkflowRuntime" not in identifiers
        assert "execute" not in identifiers

    def test_compilation_result_has_no_resource_id(self):
        """Mirrors K4.2 §12's Constraint/PlannerRequest/PlannerResult
        pattern (tests/core/cognitive/test_planner.py): CompilationResult
        is ephemeral, not an independently identified Resource."""
        fields = {f.name for f in dataclasses.fields(CompilationResult)}
        assert "resource_id" not in fields

    def test_compile_is_a_module_level_async_function(self):
        """K4.2 §1 fixes compile() as a free function alongside plan()
        and interpret(), not a method on a stateful class/worker."""
        import asyncio

        import core.cognitive.compiler as mod

        assert asyncio.iscoroutinefunction(mod.compile)
