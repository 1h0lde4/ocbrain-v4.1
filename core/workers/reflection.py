"""
core/workers/reflection.py — ReflectionWorker (Packet 07).

Architecture:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §4  (Worker Evolution — ReflectionWorker "does not exist yet ...
             specified in §7"; workers must be stateless)
        §7  (Reflection Architecture — post-execution only; consumes
             EvaluationRecord + ExecutionPlan + EventStream events;
             stores output as KnowledgeEntry instances, explicitly "not
             a new object type"; reuses the Truth Framework state
             machine; modifies future behaviour only via a governed
             memory write or handing a revised Goal/Plan back to
             Planner — never by re-triggering the failed workflow)
        §12 (Event Integration — cognitive.reflection_completed)
        §13 (Memory Integration — "Reflection proposing a candidate
             instinct/correction" goes through UnifiedMemory.write()'s
             already-governed path; "no second write path is
             introduced"; "only write what's worth retrieving later")
        §15 (Governance Integration — the reflection act itself is not
             separately gated, only its consequence — the memory write
             — is, via UnifiedMemory.write()'s own internal governance)
        §16 (Runtime Invariants — "Reflection never mutates execution
             history"; continuous reflection loops forbidden)
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 07 — Reflection + Evaluation Workers.

Packet: Packet 07 — Reflection + Evaluation Workers (Reflection half).

Documented discrepancy, resolved in architecture's favor (this project's
own "architecture always wins" rule): the K4.3 Implementation Transition
document's Packet 07 summary line says ReflectionWorker "produces
ReflectionRecord from EvaluationRecord." K4 §7 — the section specifically
and deliberately dedicated to answering exactly this question — is
explicit: reflections are stored as KnowledgeEntry instances, "not a new
object type." No ReflectionRecord dataclass exists anywhere in this
module or this repository. (K4 §4 also mentions "ReflectionRecord" once,
in a list alongside ExecutionPlan and EvaluationRecord being serialized
into WorkerResult.artifacts — read here as the same loose, generic usage,
not a second, conflicting ruling: §7 is the section that asks and answers
"how are reflections stored" directly and deliberately; §4's passing
mention is not.) See core/workers/evaluator.py for the one new record
type this packet does introduce (EvaluationRecord), which K4 §8
specifies field-by-field, unlike Reflection's output.

Scope:
    ReflectionWorker(AbstractCognitiveWorker), run once per completed
    evaluation cycle (never continuously — K4 §16). Reasons over an
    EvaluationRecord (and, optionally, the ExecutionPlan that was
    compiled) to detect a small, fixed, deterministic set of documented
    patterns (K4.2 — "Determinism Over Magic"; this is rule evaluation
    against numeric thresholds, not model-based inference). When one or
    more patterns are detected, proposes exactly one candidate
    KnowledgeEntry (truth_status="candidate" — K4 §13's own wording is
    "candidate instinct/correction") via UnifiedMemory.write(). Produces
    hypotheses and recommendations, never automatic learning.

Explicitly forbidden (K4 §16, Packet 07 spec):
    - Continuous reflection loops — called once per cycle; holds no
      state between invocations (stateless, K4 §4; _detect_patterns is a
      pure function of its inputs, not instance state).
    - Mutating the events / ExecutionPlan / EvaluationRecord it reflects
      on ("Reflection never mutates execution history") — only ever
      writes NEW KnowledgeEntry records.
    - Automatic learning — a detected pattern becomes a *candidate*
      KnowledgeEntry with confidence 0.5, never a direct behavior change.

Explicitly NOT in scope (future work):
    - Wiring this worker's output into Packet 04's ValidationGate/Learning
      tiers (core/cognitive/learning.py). K4 §13 names UnifiedMemory.write()
      as Reflection's one write path ("no second write path is
      introduced") — nothing here calls validation_gate() or constructs a
      LearningRecord. A future integration packet may choose to have some
      later consumer read these candidate KnowledgeEntry writes and feed
      them into the learning pipeline; that wiring is not performed here.
    - Sophisticated causal inference, strategy evaluation, or optimization
      recommendations. The pattern set below is small, fixed, and
      documented precisely so it stays inside "keep responsibilities
      narrowly scoped" rather than reaching toward the full future
      Reflection Runtime vision described in
      "OCBrain Architecture Evolution Directive.md" (explicitly
      placeholder-only, "no implementation planning," per that
      document's own scope statement — not contradicted by this packet,
      which implements only what K4 §7 concretely specifies today).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.cognitive.planner import ExecutionPlan
from core.memory.unified_memory import UnifiedMemory, get_unified_memory
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.workers.evaluator import EvaluationRecord

# Deterministic hypothesis thresholds. Implementation judgment (not
# separately cited in architecture text), analogous in spirit to Packet
# 06's ClarificationPolicy default (0.5): a documented starting point a
# caller may override via context.parameters, not a claim of
# empirically-validated tuning — there is no learned or historical
# calibration of these values anywhere in this repository.
_LOW_SUCCESS_THRESHOLD = 0.5
_CONFIDENCE_MISCALIBRATION_THRESHOLD = 0.4  # |predicted - actual outcome|


def _detect_patterns(
    record: EvaluationRecord,
    low_success_threshold: float,
    miscalibration_threshold: float,
) -> List[Dict[str, str]]:
    """Pure function: EvaluationRecord + thresholds -> detected hypotheses.

    Each rule maps directly onto one of the categories the architecture
    names: recurring patterns, possible causes, planner weaknesses,
    capability-selection weaknesses, confidence-calibration
    opportunities. Deliberately separated from ReflectionWorker/memory
    I/O so the actual reasoning is directly unit-testable, mirroring
    core/workers/evaluator.py's _build_evaluation_record() and
    core/cognitive/compiler.py's pure-mapping functions.

    Returns an empty list for a routine, unremarkable success — K4 §13:
    "only write what's worth retrieving later," the same discipline
    already governing every other memory write in this system.
    """
    hypotheses: List[Dict[str, str]] = []

    if not record.goal_completed and record.tool_success_rate < low_success_threshold:
        hypotheses.append({
            "category": "capability_selection_weakness",
            "hypothesis": (
                f"Goal not completed with low tool success rate "
                f"({record.tool_success_rate:.2f}) — steps may have "
                f"selected unreliable or mismatched capabilities."
            ),
        })

    if not record.goal_completed and not record.reasoning_valid:
        hypotheses.append({
            "category": "planner_weakness",
            "hypothesis": (
                "Goal not completed and reasoning was flagged invalid — "
                "the plan's own decomposition or sequencing may be at fault."
            ),
        })

    miscalibration = abs(
        record.predicted_confidence - (1.0 if record.actual_outcome else 0.0)
    )
    if miscalibration >= miscalibration_threshold:
        hypotheses.append({
            "category": "confidence_miscalibration",
            "hypothesis": (
                f"Predicted confidence ({record.predicted_confidence:.2f}) "
                f"diverged from the actual outcome "
                f"({'success' if record.actual_outcome else 'failure'}) by "
                f"{miscalibration:.2f} — confidence estimation may be "
                f"miscalibrated for this class of plan."
            ),
        })

    if record.goal_completed and record.quality_score < low_success_threshold:
        hypotheses.append({
            "category": "quality_shortfall",
            "hypothesis": (
                f"Goal completed but quality_score is low "
                f"({record.quality_score:.2f}) — possible suboptimal "
                f"approach despite nominal success."
            ),
        })

    return hypotheses


class ReflectionWorker(AbstractCognitiveWorker):
    """Reasons over EvaluatorWorker's output; see module docstring.

    Answers "why did it happen" — produces hypotheses and
    recommendations (candidate KnowledgeEntry writes), never automatic
    learning and never a verified conclusion.
    """

    worker_type = "ReflectionWorker"

    def __init__(self, *, memory: Optional[UnifiedMemory] = None,
                 **kwargs: Any) -> None:
        """Args:
            memory: UnifiedMemory instance. Uses the shared singleton if
                None, mirroring EvaluatorWorker's identical parameter.
            **kwargs: forwarded to AbstractCognitiveWorker.__init__
                (governance, event_stream).
        """
        super().__init__(**kwargs)
        self._memory: UnifiedMemory = memory or get_unified_memory()

    async def _run(self, context: WorkerContext) -> WorkerResult:
        """Reflect on one EvaluationRecord and, if warranted, write a
        candidate KnowledgeEntry.

        Required input: context.parameters["evaluation_record"], an
        EvaluationRecord instance produced by a prior EvaluatorWorker run
        (K4 §7: Reflection consumes "EvaluationRecord for this cycle").

        Optional: context.parameters["execution_plan"] (the ExecutionPlan
        that was compiled, K4 §7) — used only for derived_from provenance
        here; richer use (e.g. comparing plan.justification/alternatives
        against the outcome) is a plausible future extension, not
        implemented in this packet to keep the pattern set small and
        exactly matched to what's testable and defensible today.

        Optional threshold overrides: context.parameters
        ["low_success_threshold"], ["confidence_miscalibration_threshold"].
        """
        record = context.parameters.get("evaluation_record")
        if not isinstance(record, EvaluationRecord):
            return WorkerResult(
                success=False,
                error="ReflectionWorker requires context.parameters['evaluation_record'] "
                      "(an EvaluationRecord instance, produced by a prior "
                      "EvaluatorWorker run).",
            )
        plan = context.parameters.get("execution_plan")

        low_success_threshold = float(
            context.parameters.get("low_success_threshold", _LOW_SUCCESS_THRESHOLD))
        miscalibration_threshold = float(
            context.parameters.get("confidence_miscalibration_threshold",
                                    _CONFIDENCE_MISCALIBRATION_THRESHOLD))

        hypotheses = _detect_patterns(record, low_success_threshold, miscalibration_threshold)

        if not hypotheses:
            await self._emit_event("cognitive.reflection_completed", context, {
                "plan_id": record.plan_id,
                "memory_write": False,
                "hypothesis_count": 0,
            })
            return WorkerResult(
                success=True,
                output={"hypotheses": [], "memory_write": False},
                artifacts={"hypotheses": [], "reflection_entry_id": None},
            )

        derived_from: List[str] = [record.plan_id] if record.plan_id else []
        if isinstance(plan, ExecutionPlan) and plan.resource_id not in derived_from:
            derived_from.append(plan.resource_id)

        entry_content = (
            f"Reflection on plan {record.plan_id}: "
            + "; ".join(h["hypothesis"] for h in hypotheses)
        )
        entry_id = await self._memory.write(
            content=entry_content,
            content_type="reflection",
            layer_hint="l1",
            source=self.worker_type,
            importance=0.5,
            confidence=0.5,           # a hypothesis, not a verified fact
            truth_status="candidate",
            metadata={
                "hypotheses": hypotheses,
                "evaluation": record.to_dict(),
            },
            worker_id=self._id,
            workflow_id=context.workflow_id,
            derived_from=derived_from,
        )

        await self._emit_event("cognitive.reflection_completed", context, {
            "plan_id": record.plan_id,
            "memory_write": True,
            "reflection_entry_id": entry_id,
            "hypothesis_count": len(hypotheses),
        })

        return WorkerResult(
            success=True,
            output={"hypotheses": hypotheses, "memory_write": True},
            artifacts={"hypotheses": hypotheses, "reflection_entry_id": entry_id},
        )
