"""
tests/test_reflection_worker.py — Packet 07 Tests (Reflection half).

Architecture Sources:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §4, §7, §12, §13, §15, §16
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 07 — Reflection + Evaluation Workers

Coverage:
    - _detect_patterns(): each rule individually, combinations, threshold
      overrides, and the "no hypotheses" routine-success case
    - ReflectionWorker._run(): missing-record failure, memory write only
      when hypotheses exist, derived_from provenance, event emission for
      both the write and no-write paths
    - Architecture compliance: no ReflectionRecord type anywhere (locks
      in the K4 §7 KnowledgeEntry resolution), no ValidationGate/Learning
      calls, statelessness
"""
import ast

import pytest
from unittest.mock import AsyncMock

from core.cognitive.planner import ExecutionPlan, PlanStep
from core.workers.base import WorkerContext
from core.workers.evaluator import EvaluationRecord
from core.workers.reflection import ReflectionWorker, _detect_patterns


def _make_plan(resource_id: str = "plan-1", goal_id: str = "goal-1") -> ExecutionPlan:
    plan = ExecutionPlan(
        goal_id=goal_id,
        steps=[PlanStep(step_id="s1", description="do a thing",
                         capability_type="llm_completion")],
        confidence=0.8,
    )
    plan.resource_id = resource_id
    return plan


def _make_record(**overrides) -> EvaluationRecord:
    defaults = dict(
        plan_id="plan-1",
        goal_completed=True,
        quality_score=0.9,
        reasoning_valid=True,
        tool_success_rate=0.9,
        predicted_confidence=0.8,
        actual_outcome=True,
    )
    defaults.update(overrides)
    return EvaluationRecord(**defaults)


class FakeEventStream:
    """Mirrors tests/test_evaluator_worker.py's own double."""

    def __init__(self):
        self.appended = []

    async def append(self, event_type, source, payload, checkpoint=""):
        self.appended.append(
            {"event_type": event_type, "source": source, "payload": payload})


# ─────────────────────────────────────────────────────────────────────────
# _detect_patterns — pure function
# ─────────────────────────────────────────────────────────────────────────


class TestDetectPatterns:
    def test_routine_success_produces_no_hypotheses(self):
        record = _make_record()
        assert _detect_patterns(record, 0.5, 0.4) == []

    def test_low_tool_success_with_failure_flags_capability_weakness(self):
        record = _make_record(goal_completed=False, tool_success_rate=0.2)
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "capability_selection_weakness" in categories

    def test_high_tool_success_with_failure_does_not_flag_capability_weakness(self):
        record = _make_record(goal_completed=False, tool_success_rate=0.9,
                               reasoning_valid=True, predicted_confidence=0.1,
                               actual_outcome=False)
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "capability_selection_weakness" not in categories

    def test_invalid_reasoning_with_failure_flags_planner_weakness(self):
        record = _make_record(goal_completed=False, reasoning_valid=False,
                               tool_success_rate=0.9, predicted_confidence=0.1,
                               actual_outcome=False)
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "planner_weakness" in categories

    def test_valid_reasoning_does_not_flag_planner_weakness(self):
        record = _make_record(goal_completed=False, reasoning_valid=True,
                               tool_success_rate=0.9, predicted_confidence=0.1,
                               actual_outcome=False)
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "planner_weakness" not in categories

    def test_confidence_miscalibration_high_predicted_actual_failure(self):
        record = _make_record(predicted_confidence=0.95, actual_outcome=False,
                               goal_completed=False, tool_success_rate=0.9,
                               reasoning_valid=True)
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "confidence_miscalibration" in categories

    def test_confidence_well_calibrated_no_miscalibration_flag(self):
        record = _make_record(predicted_confidence=0.85, actual_outcome=True)
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "confidence_miscalibration" not in categories

    def test_low_quality_despite_success_flags_quality_shortfall(self):
        record = _make_record(goal_completed=True, quality_score=0.2)
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "quality_shortfall" in categories

    def test_multiple_conditions_produce_multiple_hypotheses(self):
        record = _make_record(
            goal_completed=False, tool_success_rate=0.1, reasoning_valid=False,
            predicted_confidence=0.9, actual_outcome=False,
        )
        hyps = _detect_patterns(record, 0.5, 0.4)
        categories = {h["category"] for h in hyps}
        assert "capability_selection_weakness" in categories
        assert "planner_weakness" in categories
        assert "confidence_miscalibration" in categories
        assert len(hyps) == 3

    def test_threshold_override_changes_sensitivity(self):
        record = _make_record(goal_completed=False, tool_success_rate=0.6)
        # default threshold 0.5 -- 0.6 is NOT below it
        assert _detect_patterns(record, 0.5, 0.4) == []
        # stricter threshold 0.7 -- 0.6 now IS below it
        hyps = _detect_patterns(record, 0.7, 0.4)
        assert any(h["category"] == "capability_selection_weakness" for h in hyps)

    def test_every_hypothesis_has_category_and_text(self):
        record = _make_record(goal_completed=False, tool_success_rate=0.1)
        for h in _detect_patterns(record, 0.5, 0.4):
            assert "category" in h and isinstance(h["category"], str)
            assert "hypothesis" in h and isinstance(h["hypothesis"], str)


# ─────────────────────────────────────────────────────────────────────────
# ReflectionWorker — integration
# ─────────────────────────────────────────────────────────────────────────


class TestReflectionWorkerRun:
    @pytest.mark.asyncio
    async def test_missing_evaluation_record_fails(self):
        worker = ReflectionWorker(memory=AsyncMock())
        context = WorkerContext(query="reflect", parameters={})
        result = await worker._run(context)
        assert result.success is False
        assert "evaluation_record" in result.error

    @pytest.mark.asyncio
    async def test_routine_success_writes_nothing(self):
        record = _make_record()  # nominal success, no hypotheses
        memory = AsyncMock()
        stream = FakeEventStream()
        worker = ReflectionWorker(memory=memory, event_stream=stream)
        context = WorkerContext(query="reflect",
                                 parameters={"evaluation_record": record})

        result = await worker.execute(context)

        assert result.success is True
        assert result.artifacts["reflection_entry_id"] is None
        memory.write.assert_not_called()
        completed = [e for e in stream.appended
                     if e["event_type"] == "cognitive.reflection_completed"]
        assert len(completed) == 1
        assert completed[0]["payload"]["memory_write"] is False
        assert completed[0]["payload"]["hypothesis_count"] == 0

    @pytest.mark.asyncio
    async def test_notable_failure_writes_candidate_entry(self):
        record = _make_record(goal_completed=False, tool_success_rate=0.1,
                               plan_id="plan-99")
        plan = _make_plan(resource_id="plan-99")
        memory = AsyncMock()
        memory.write = AsyncMock(return_value="reflection-entry-1")
        stream = FakeEventStream()
        worker = ReflectionWorker(memory=memory, event_stream=stream)
        context = WorkerContext(
            query="reflect", workflow_id="plan-99",
            parameters={"evaluation_record": record, "execution_plan": plan},
        )

        result = await worker.execute(context)

        assert result.success is True
        assert result.artifacts["reflection_entry_id"] == "reflection-entry-1"
        assert len(result.artifacts["hypotheses"]) >= 1

        memory.write.assert_awaited_once()
        _, kwargs = memory.write.call_args
        assert kwargs["truth_status"] == "candidate"
        assert kwargs["confidence"] == 0.5
        assert kwargs["layer_hint"] == "l1"
        assert "plan-99" in kwargs["derived_from"]

        completed = [e for e in stream.appended
                     if e["event_type"] == "cognitive.reflection_completed"]
        assert completed[0]["payload"]["memory_write"] is True
        assert completed[0]["payload"]["hypothesis_count"] >= 1

    @pytest.mark.asyncio
    async def test_derived_from_includes_plan_id_without_execution_plan(self):
        record = _make_record(goal_completed=False, tool_success_rate=0.1,
                               plan_id="plan-only-id")
        memory = AsyncMock()
        memory.write = AsyncMock(return_value="e1")
        worker = ReflectionWorker(memory=memory, event_stream=FakeEventStream())
        context = WorkerContext(query="reflect",
                                 parameters={"evaluation_record": record})

        await worker.execute(context)

        _, kwargs = memory.write.call_args
        assert kwargs["derived_from"] == ["plan-only-id"]

    @pytest.mark.asyncio
    async def test_threshold_overrides_passed_through_context_parameters(self):
        record = _make_record(goal_completed=False, tool_success_rate=0.6)
        memory = AsyncMock()
        memory.write = AsyncMock(return_value="e1")
        worker = ReflectionWorker(memory=memory, event_stream=FakeEventStream())
        context = WorkerContext(
            query="reflect",
            parameters={"evaluation_record": record, "low_success_threshold": 0.7},
        )

        result = await worker.execute(context)

        # 0.6 is not below the default 0.5 threshold, but IS below the
        # overridden 0.7 -- so a hypothesis should fire and a write occur.
        assert len(result.artifacts["hypotheses"]) >= 1
        memory.write.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────────
# Architecture compliance
# ─────────────────────────────────────────────────────────────────────────


def _real_code_identifiers(filepath: str) -> set:
    """Mirrors the identical helper in tests/test_evaluator_worker.py and
    tests/core/cognitive/test_planner.py / test_compiler.py."""
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
    def test_no_reflection_record_type_anywhere(self):
        """Locks in the K4 §7 resolution: reflections are KnowledgeEntry
        instances, 'not a new object type' -- no ReflectionRecord class
        should ever be (re-)introduced."""
        import core.workers.reflection as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "ReflectionRecord" not in identifiers
        assert not hasattr(mod, "ReflectionRecord")

    def test_no_validation_gate_or_learning_record_calls(self):
        """K4 §13: Reflection's memory write and Packet 04's Learning
        tiers are two separate, already-governed mechanisms -- this
        packet does not wire one into the other."""
        import core.workers.reflection as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "validation_gate" not in identifiers
        assert "LearningRecord" not in identifiers
        assert "LearningTier" not in identifiers

    def test_no_capability_invocation(self):
        import core.workers.reflection as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "AdapterRuntime" not in identifiers
        assert "CapabilityRegistry" not in identifiers

    def test_reflection_worker_subclasses_abstract_cognitive_worker(self):
        from core.workers.base import AbstractCognitiveWorker
        assert issubclass(ReflectionWorker, AbstractCognitiveWorker)

    def test_reflection_worker_type_identity(self):
        assert ReflectionWorker.worker_type == "ReflectionWorker"

    def test_detect_patterns_is_a_pure_module_level_function(self):
        """K4 §4: workers must be stateless. _detect_patterns takes no
        `self` and reads no instance state -- verified structurally, not
        just by convention."""
        import inspect
        sig = inspect.signature(_detect_patterns)
        assert "self" not in sig.parameters
