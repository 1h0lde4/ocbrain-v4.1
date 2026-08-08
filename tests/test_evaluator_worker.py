"""
tests/test_evaluator_worker.py — Packet 07 Tests (Evaluator half).

Architecture Sources:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §4, §8, §12, §13, §15, §16
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 07 — Reflection + Evaluation Workers

Coverage:
    - EvaluationRecord dataclass shape
    - _build_evaluation_record(): pure computation, every field, every
      override/fallback path
    - _fetch_workflow_events(): payload-based workflow_id filtering
    - EvaluatorWorker._run(): missing-plan failure, full flow via
      execute() (real governance gate + mocked memory/event stream)
    - Architecture compliance: no capability invocation/selection, no
      learning/ValidationGate calls, no WorkflowRuntime invocation
"""
import ast
import dataclasses

import pytest
from unittest.mock import AsyncMock

from core.cognitive.planner import ExecutionPlan, PlanStep
from core.events.event_stream import StreamEvent
from core.workers.base import WorkerContext
from core.workers.evaluator import (
    EvaluationRecord,
    EvaluatorWorker,
    _build_evaluation_record,
    _fetch_workflow_events,
)


def _make_plan(resource_id: str = "plan-1", goal_id: str = "goal-1",
                confidence: float = 0.8) -> ExecutionPlan:
    plan = ExecutionPlan(
        goal_id=goal_id,
        steps=[PlanStep(step_id="s1", description="do a thing",
                         capability_type="llm_completion")],
        confidence=confidence,
    )
    plan.resource_id = resource_id
    return plan


def _completed_event(workflow_id: str, success: bool, sequence: int = 1) -> StreamEvent:
    return StreamEvent(
        event_type="workflow.completed",
        source="WorkflowRuntime",
        payload={"workflow_id": workflow_id, "success": success},
        sequence=sequence,
    )


def _worker_event(event_type: str, workflow_id: str) -> StreamEvent:
    return StreamEvent(
        event_type=event_type,
        source="SomeWorker:abcd1234",
        payload={"workflow_id": workflow_id},
    )


class FakeEventStream:
    """Minimal EventStream double supporting both append() (recording,
    mirrors MockEventStream in tests/core/cognitive/test_compiler.py) and
    query() (returning pre-seeded events, filtered by event_type only —
    matching the real EventStream.query()'s own filter set)."""

    def __init__(self, seed_events=None):
        self._events = list(seed_events or [])
        self.appended = []

    async def append(self, event_type, source, payload, checkpoint=""):
        self.appended.append(
            {"event_type": event_type, "source": source, "payload": payload})

    async def query(self, *, event_type=None, source=None,
                     since=0.0, until=0.0, limit=100,
                     payload_workflow_id=None):
        results = [e for e in self._events
                   if event_type is None or e.event_type == event_type]
        if payload_workflow_id is not None:
            results = [e for e in results
                       if e.payload.get("workflow_id") == payload_workflow_id]
        return results[:limit]


# ─────────────────────────────────────────────────────────────────────────
# EvaluationRecord — shape
# ─────────────────────────────────────────────────────────────────────────


class TestEvaluationRecordDataclass:
    def test_defaults(self):
        record = EvaluationRecord()
        assert record.plan_id == ""
        assert record.goal_completed is False
        assert record.quality_score == 0.0
        assert record.reasoning_valid is True
        assert record.tool_success_rate == 0.0
        assert record.predicted_confidence == 0.0
        assert record.actual_outcome is False
        assert record.resource_id  # auto-generated, non-empty

    def test_to_dict(self):
        record = EvaluationRecord(plan_id="p1", goal_completed=True)
        d = record.to_dict()
        assert d["plan_id"] == "p1"
        assert d["goal_completed"] is True


# ─────────────────────────────────────────────────────────────────────────
# _fetch_workflow_events — payload-based workflow_id filtering
# ─────────────────────────────────────────────────────────────────────────


class TestFetchWorkflowEvents:
    @pytest.mark.asyncio
    async def test_filters_by_workflow_id_in_payload(self):
        stream = FakeEventStream(seed_events=[
            _completed_event("wf-1", True),
            _completed_event("wf-2", False),
        ])
        results = await _fetch_workflow_events(stream, "wf-1", "workflow.completed")
        assert len(results) == 1
        assert results[0].payload["workflow_id"] == "wf-1"

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self):
        stream = FakeEventStream(seed_events=[_completed_event("wf-1", True)])
        results = await _fetch_workflow_events(stream, "wf-nonexistent", "workflow.completed")
        assert results == []


# ─────────────────────────────────────────────────────────────────────────
# _build_evaluation_record — pure computation
# ─────────────────────────────────────────────────────────────────────────


class TestBuildEvaluationRecord:
    def test_goal_completed_true_from_event(self):
        plan = _make_plan(confidence=0.7)
        record = _build_evaluation_record(
            plan, [_completed_event(plan.resource_id, True)], [], [], {})
        assert record.goal_completed is True
        assert record.actual_outcome is True
        assert record.predicted_confidence == 0.7
        assert record.plan_id == plan.resource_id

    def test_goal_completed_false_from_event(self):
        plan = _make_plan()
        record = _build_evaluation_record(
            plan, [_completed_event(plan.resource_id, False)], [], [], {})
        assert record.goal_completed is False
        assert record.actual_outcome is False

    def test_no_event_no_override_defaults_false(self):
        plan = _make_plan()
        record = _build_evaluation_record(plan, [], [], [], {})
        assert record.goal_completed is False

    def test_no_event_with_override_respected(self):
        plan = _make_plan()
        record = _build_evaluation_record(
            plan, [], [], [], {"goal_completed": True})
        assert record.goal_completed is True

    def test_most_recent_completed_event_wins(self):
        # SQLiteEventStore.query() orders sequence DESC; index 0 is newest.
        plan = _make_plan()
        events = [
            _completed_event(plan.resource_id, True, sequence=2),
            _completed_event(plan.resource_id, False, sequence=1),
        ]
        record = _build_evaluation_record(plan, events, [], [], {})
        assert record.goal_completed is True

    def test_tool_success_rate_from_worker_events(self):
        plan = _make_plan()
        completed = [_worker_event("worker.completed", plan.resource_id)] * 3
        failed = [_worker_event("worker.failed", plan.resource_id)] * 1
        record = _build_evaluation_record(plan, [], completed, failed, {})
        assert record.tool_success_rate == pytest.approx(0.75)

    def test_tool_success_rate_override_takes_precedence(self):
        plan = _make_plan()
        completed = [_worker_event("worker.completed", plan.resource_id)] * 3
        record = _build_evaluation_record(
            plan, [], completed, [], {"tool_success_rate": 0.1})
        assert record.tool_success_rate == 0.1

    def test_no_worker_events_goal_completed_true_defaults_full_rate(self):
        plan = _make_plan()
        record = _build_evaluation_record(
            plan, [_completed_event(plan.resource_id, True)], [], [], {})
        assert record.tool_success_rate == 1.0

    def test_no_worker_events_goal_completed_false_defaults_zero_rate(self):
        plan = _make_plan()
        record = _build_evaluation_record(
            plan, [_completed_event(plan.resource_id, False)], [], [], {})
        assert record.tool_success_rate == 0.0

    def test_reasoning_valid_defaults_to_goal_completed(self):
        plan = _make_plan()
        record = _build_evaluation_record(
            plan, [_completed_event(plan.resource_id, True)], [], [], {})
        assert record.reasoning_valid is True

    def test_reasoning_valid_override_respected(self):
        plan = _make_plan()
        record = _build_evaluation_record(
            plan, [_completed_event(plan.resource_id, True)], [], [],
            {"reasoning_valid": False})
        assert record.reasoning_valid is False

    def test_quality_score_defaults_to_tool_success_rate(self):
        plan = _make_plan()
        completed = [_worker_event("worker.completed", plan.resource_id)] * 2
        record = _build_evaluation_record(plan, [], completed, [], {})
        assert record.quality_score == record.tool_success_rate

    def test_quality_score_override_respected(self):
        plan = _make_plan()
        record = _build_evaluation_record(
            plan, [], [], [], {"quality_score": 0.9})
        assert record.quality_score == 0.9

    def test_returns_evaluation_record_instance(self):
        assert isinstance(_build_evaluation_record(_make_plan(), [], [], [], {}),
                           EvaluationRecord)


# ─────────────────────────────────────────────────────────────────────────
# EvaluatorWorker — integration
# ─────────────────────────────────────────────────────────────────────────


class TestEvaluatorWorkerRun:
    @pytest.mark.asyncio
    async def test_missing_execution_plan_fails(self):
        worker = EvaluatorWorker(memory=AsyncMock())
        context = WorkerContext(query="evaluate", parameters={})
        result = await worker._run(context)
        assert result.success is False
        assert "execution_plan" in result.error

    @pytest.mark.asyncio
    async def test_full_flow_via_execute(self):
        plan = _make_plan(confidence=0.65)
        stream = FakeEventStream(seed_events=[
            _completed_event(plan.resource_id, True),
            _worker_event("worker.completed", plan.resource_id),
            _worker_event("worker.completed", plan.resource_id),
        ])
        memory = AsyncMock()
        memory.write = AsyncMock(return_value="entry-123")

        worker = EvaluatorWorker(memory=memory, event_stream=stream)
        context = WorkerContext(
            query="evaluate plan",
            workflow_id=plan.resource_id,
            parameters={"execution_plan": plan},
        )
        result = await worker.execute(context)

        assert result.success is True
        assert result.artifacts["evaluation_entry_id"] == "entry-123"
        record = result.artifacts["evaluation_record"]
        assert record["goal_completed"] is True
        assert record["predicted_confidence"] == 0.65
        assert record["plan_id"] == plan.resource_id

        # memory.write called with the right shape
        memory.write.assert_awaited_once()
        _, kwargs = memory.write.call_args
        assert kwargs["truth_status"] == "candidate"
        assert kwargs["layer_hint"] == "l1"
        assert kwargs["derived_from"] == [plan.resource_id]
        assert kwargs["workflow_id"] == plan.resource_id

        # cognitive.evaluation_completed emitted (in addition to the base
        # class's own worker.started/worker.completed)
        completed = [e for e in stream.appended
                     if e["event_type"] == "cognitive.evaluation_completed"]
        assert len(completed) == 1
        assert completed[0]["payload"]["plan_id"] == plan.resource_id

    @pytest.mark.asyncio
    async def test_workflow_id_falls_back_to_plan_resource_id(self):
        plan = _make_plan()
        stream = FakeEventStream(seed_events=[_completed_event(plan.resource_id, True)])
        memory = AsyncMock()
        memory.write = AsyncMock(return_value="entry-1")

        worker = EvaluatorWorker(memory=memory, event_stream=stream)
        # No workflow_id set on context -- must fall back to plan.resource_id
        context = WorkerContext(query="evaluate", parameters={"execution_plan": plan})
        result = await worker.execute(context)

        assert result.success is True
        assert result.artifacts["evaluation_record"]["goal_completed"] is True


# ─────────────────────────────────────────────────────────────────────────
# Architecture compliance
# ─────────────────────────────────────────────────────────────────────────


def _real_code_identifiers(filepath: str) -> set:
    """Mirrors tests/core/cognitive/test_planner.py's / test_compiler.py's
    helper of the same name/purpose verbatim: AST-based, not substring-
    based, so this module's own extensive docstrings (which name
    forbidden concepts specifically to disclaim them) don't false-positive."""
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
    def test_no_capability_invocation_or_selection(self):
        import core.workers.evaluator as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "AdapterRuntime" not in identifiers
        assert "CapabilityRegistry" not in identifiers

    def test_no_learning_or_validation_gate_calls(self):
        """Evaluation never makes learning decisions (Reflection/
        ValidationGate's job, K4 §13)."""
        import core.workers.evaluator as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "validation_gate" not in identifiers
        assert "LearningRecord" not in identifiers

    def test_no_workflow_runtime_invocation(self):
        """Evaluator reads WorkflowRuntime's events; it never calls it."""
        import core.workers.evaluator as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "WorkflowRuntime" not in identifiers

    def test_evaluator_worker_subclasses_abstract_cognitive_worker(self):
        from core.workers.base import AbstractCognitiveWorker
        assert issubclass(EvaluatorWorker, AbstractCognitiveWorker)

    def test_evaluator_worker_type_identity(self):
        assert EvaluatorWorker.worker_type == "EvaluatorWorker"
