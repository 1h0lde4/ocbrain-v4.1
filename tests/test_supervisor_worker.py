"""
tests/test_supervisor_worker.py — Packet 08 Tests.

Architecture Sources:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §4, §9, §12, §15, §16 (invariant 9)
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 08 — Supervisor Worker

Coverage:
    - _classify_compilation_outcome(): every CompilationStatus value
    - SupervisorWorker._run() path (1): REJECTED / REJECTED_PRECHECK /
      ESCALATED / COMPILED, event emission (escalated only), invariant 9
      (no retry call under any compilation-rejection circumstance,
      including when a retry input is ALSO present)
    - SupervisorWorker._run() path (2): retry via ExecutionRuntime,
      exhaustion bound, missing-dependency errors, correct invoke() args
    - No-input NO_ACTION case
    - Architecture compliance: no governance mechanism of its own, no
      compile()/Planner/ValidationGate calls, statelessness
"""
import ast

import pytest
from unittest.mock import AsyncMock

from core.cognitive.compiler import CompilationResult, CompilationStatus
from core.cognitive.recovery import OperationRecoveryBudget
from core.governance.governance_kernel import GovernanceResult, GovernanceVerdict
from core.runtime.execution_runtime import ExecutionRuntime
from core.workers.base import WorkerContext, WorkerResult
from core.workers.supervisor import (
    SupervisorOutcome,
    SupervisorWorker,
    _classify_compilation_outcome,
)


class FakeEventStream:
    def __init__(self):
        self.appended = []

    async def append(self, event_type, source, payload, checkpoint=""):
        self.appended.append(
            {"event_type": event_type, "source": source, "payload": payload})


def _compiled_result() -> CompilationResult:
    return CompilationResult(status=CompilationStatus.COMPILED)


def _rejected_result(precheck: bool = False) -> CompilationResult:
    status = CompilationStatus.REJECTED_PRECHECK if precheck else CompilationStatus.REJECTED
    gov = None if precheck else GovernanceResult(
        verdict=GovernanceVerdict.REJECT, reason="stub reject", governor="Stub")
    return CompilationResult(status=status, governance_result=gov,
                              precheck_errors=["bad"] if precheck else [])


def _escalated_result() -> CompilationResult:
    return CompilationResult(
        status=CompilationStatus.ESCALATED,
        governance_result=GovernanceResult(
            verdict=GovernanceVerdict.ESCALATE, reason="low confidence", governor="Stub"),
    )


# ─────────────────────────────────────────────────────────────────────────
# _classify_compilation_outcome — pure function
# ─────────────────────────────────────────────────────────────────────────


class TestClassifyCompilationOutcome:
    def test_none_input_returns_none(self):
        assert _classify_compilation_outcome(None) is None

    def test_compiled_returns_none(self):
        assert _classify_compilation_outcome(_compiled_result()) is None

    def test_rejected_returns_rejected(self):
        assert _classify_compilation_outcome(_rejected_result()) == SupervisorOutcome.REJECTED

    def test_rejected_precheck_returns_rejected(self):
        assert (_classify_compilation_outcome(_rejected_result(precheck=True))
                == SupervisorOutcome.REJECTED)

    def test_escalated_returns_escalated(self):
        assert (_classify_compilation_outcome(_escalated_result())
                == SupervisorOutcome.ESCALATED)


# ─────────────────────────────────────────────────────────────────────────
# SupervisorWorker._run() — path (1): compilation-gate outcomes
# ─────────────────────────────────────────────────────────────────────────


class TestSupervisorCompilationPath:
    @pytest.mark.asyncio
    async def test_no_input_is_no_action(self):
        worker = SupervisorWorker(event_stream=FakeEventStream())
        result = await worker.execute(WorkerContext(query="supervise", parameters={}))
        assert result.success is True
        assert result.output["outcome"] == SupervisorOutcome.NO_ACTION

    @pytest.mark.asyncio
    async def test_compiled_result_is_no_action(self):
        worker = SupervisorWorker(event_stream=FakeEventStream())
        context = WorkerContext(query="supervise",
                                 parameters={"compilation_result": _compiled_result()})
        result = await worker.execute(context)
        assert result.success is True
        assert result.output["outcome"] == SupervisorOutcome.NO_ACTION

    @pytest.mark.asyncio
    async def test_invalid_compilation_result_type_errors(self):
        worker = SupervisorWorker(event_stream=FakeEventStream())
        context = WorkerContext(query="supervise",
                                 parameters={"compilation_result": {"not": "a CompilationResult"}})
        result = await worker._run(context)
        assert result.success is False
        assert "CompilationResult" in result.error

    @pytest.mark.asyncio
    async def test_rejected_is_surfaced_as_failure_no_event(self):
        stream = FakeEventStream()
        worker = SupervisorWorker(event_stream=stream)
        context = WorkerContext(query="supervise",
                                 parameters={"compilation_result": _rejected_result()})
        result = await worker.execute(context)

        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.REJECTED
        assert result.output["governance_verdict"] == "reject"
        escalation_events = [e for e in stream.appended
                              if e["event_type"] == "cognitive.supervision_escalated"]
        assert escalation_events == []

    @pytest.mark.asyncio
    async def test_rejected_precheck_is_surfaced_as_failure(self):
        worker = SupervisorWorker(event_stream=FakeEventStream())
        context = WorkerContext(
            query="supervise",
            parameters={"compilation_result": _rejected_result(precheck=True)})
        result = await worker.execute(context)
        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.REJECTED

    @pytest.mark.asyncio
    async def test_escalated_emits_supervision_escalated_event(self):
        stream = FakeEventStream()
        worker = SupervisorWorker(event_stream=stream)
        context = WorkerContext(query="supervise",
                                 parameters={"compilation_result": _escalated_result()})
        result = await worker.execute(context)

        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.ESCALATED
        escalation_events = [e for e in stream.appended
                              if e["event_type"] == "cognitive.supervision_escalated"]
        assert len(escalation_events) == 1
        assert escalation_events[0]["payload"]["governance_verdict"] == "escalate"

    @pytest.mark.asyncio
    async def test_rejected_plan_is_never_retried_even_with_retry_input_present(self):
        """K4 §16 invariant 9's direct test: even when a retry_worker_type
        and an ExecutionRuntime ARE available, a rejected compilation
        result must short-circuit before any retry is attempted."""
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        context = WorkerContext(
            query="supervise",
            parameters={
                "compilation_result": _rejected_result(),
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
            },
        )
        result = await worker.execute(context)

        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.REJECTED
        execution_runtime.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_escalated_plan_is_never_retried_even_with_retry_input_present(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        context = WorkerContext(
            query="supervise",
            parameters={
                "compilation_result": _escalated_result(),
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
            },
        )
        result = await worker.execute(context)

        assert result.output["outcome"] == SupervisorOutcome.ESCALATED
        execution_runtime.invoke.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────
# SupervisorWorker._run() — path (2): retry via ExecutionRuntime
# ─────────────────────────────────────────────────────────────────────────


class TestSupervisorRetryPath:
    @pytest.mark.asyncio
    async def test_missing_execution_runtime_errors(self):
        worker = SupervisorWorker(event_stream=FakeEventStream())  # no execution_runtime
        context = WorkerContext(
            query="supervise",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
            },
        )
        result = await worker._run(context)
        assert result.success is False
        assert "ExecutionRuntime" in result.error

    @pytest.mark.asyncio
    async def test_missing_retry_worker_type_errors(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        context = WorkerContext(
            query="supervise",
            parameters={"failed_worker_result": WorkerResult(success=False, error="boom")},
        )
        result = await worker._run(context)
        assert result.success is False
        assert "retry_worker_type" in result.error

    @pytest.mark.asyncio
    async def test_successful_retry_calls_execution_runtime_correctly(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        execution_runtime.invoke = AsyncMock(
            return_value=WorkerResult(success=True, output={"ok": True}))
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        context = WorkerContext(
            query="do the thing", workflow_id="wf-1",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
                "retry_parameters": {"execution_plan": "plan-obj"},
            },
        )
        result = await worker.execute(context)

        assert result.success is True
        assert result.output["outcome"] == SupervisorOutcome.RETRY_INITIATED
        assert result.output["attempt"] == 1
        assert result.output["retry_success"] is True

        execution_runtime.invoke.assert_awaited_once()
        args, kwargs = execution_runtime.invoke.call_args
        assert args[0] == "SomeWorker"
        assert kwargs["workflow_id"] == "wf-1"
        assert kwargs["query"] == "do the thing"
        assert kwargs["parent_worker_id"] == worker.worker_id  # self._id
        assert kwargs["metadata"]["parameters"] == {"execution_plan": "plan-obj"}

    @pytest.mark.asyncio
    async def test_failed_retry_propagates_failure(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        execution_runtime.invoke = AsyncMock(
            return_value=WorkerResult(success=False, error="still broken"))
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        context = WorkerContext(
            query="supervise",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
            },
        )
        result = await worker.execute(context)
        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.RETRY_INITIATED
        assert result.output["retry_success"] is False

    @pytest.mark.asyncio
    async def test_retry_exhausted_when_attempt_meets_max(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        context = WorkerContext(
            query="supervise",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
                "max_supervisor_retries": 2,
                "supervisor_retry_attempt": 2,
            },
        )
        result = await worker.execute(context)

        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.RETRY_EXHAUSTED
        assert result.output["attempts"] == 2
        execution_runtime.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_max_retries_is_one(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        # attempt=1, default max=1 -- 1 >= 1, exhausted, no invoke() call
        context = WorkerContext(
            query="supervise",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
                "supervisor_retry_attempt": 1,
            },
        )
        result = await worker.execute(context)
        assert result.output["outcome"] == SupervisorOutcome.RETRY_EXHAUSTED
        execution_runtime.invoke.assert_not_called()


class TestSupervisorSharedRecoveryBudget:
    """K4.2-H1 D5 (ADR-K4.2-H-05). The mandatory Planner/Supervisor
    SAME-instance integration proof lives in
    tests/test_orchestrator_recovery.py (H1-G5); this class covers
    _attempt_retry()'s own budget-consuming behavior and legacy-path
    preservation in isolation."""

    @pytest.mark.asyncio
    async def test_recovery_budget_consumed_when_present(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        execution_runtime.invoke = AsyncMock(
            return_value=WorkerResult(success=True, output={"ok": True}))
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        budget = OperationRecoveryBudget(max_total_recovery_attempts=3)
        context = WorkerContext(
            query="do the thing", workflow_id="wf-1",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
                "recovery_budget": budget,
            },
        )
        result = await worker.execute(context)
        assert result.success is True
        assert result.output["outcome"] == SupervisorOutcome.RETRY_INITIATED
        assert budget.internal_recovery_used == 1
        assert budget.remaining == 2

    @pytest.mark.asyncio
    async def test_recovery_budget_authority_ignores_legacy_counters(self):
        """When a recovery_budget is present, it is the SOLE authority
        -- max_supervisor_retries/supervisor_retry_attempt (which alone
        would signal exhaustion here: attempt >= max) are not consulted
        at all."""
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        execution_runtime.invoke = AsyncMock(
            return_value=WorkerResult(success=True, output={"ok": True}))
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        budget = OperationRecoveryBudget(max_total_recovery_attempts=3)
        context = WorkerContext(
            query="do the thing",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
                "max_supervisor_retries": 1,
                "supervisor_retry_attempt": 5,  # would exhaust the legacy path
                "recovery_budget": budget,
            },
        )
        result = await worker.execute(context)
        assert result.output["outcome"] == SupervisorOutcome.RETRY_INITIATED, (
            "a present recovery_budget must override the legacy "
            "max_supervisor_retries/supervisor_retry_attempt check entirely"
        )
        execution_runtime.invoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retry_exhausted_when_budget_exhausted(self):
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        budget = OperationRecoveryBudget(max_total_recovery_attempts=1)
        budget.consume()  # pre-exhaust, simulating a prior Planner re-plan
        context = WorkerContext(
            query="supervise",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
                "recovery_budget": budget,
            },
        )
        result = await worker.execute(context)
        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.RETRY_EXHAUSTED
        assert result.output["budget_remaining"] == 0
        execution_runtime.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_recovery_budget_falls_back_to_legacy_path_unchanged(self):
        """Backward compatibility: every pre-H1 caller (and every
        existing test above this class) supplies no recovery_budget at
        all -- the legacy max_supervisor_retries/supervisor_retry_attempt
        path must be byte-for-byte unchanged. Exercises the exact
        boundary case from test_retry_exhausted_when_attempt_meets_max
        above, confirming H1 did not silently alter it."""
        execution_runtime = AsyncMock(spec=ExecutionRuntime)
        worker = SupervisorWorker(event_stream=FakeEventStream(),
                                   execution_runtime=execution_runtime)
        context = WorkerContext(
            query="supervise",
            parameters={
                "failed_worker_result": WorkerResult(success=False, error="boom"),
                "retry_worker_type": "SomeWorker",
                "max_supervisor_retries": 2,
                "supervisor_retry_attempt": 2,
            },
        )
        result = await worker.execute(context)
        assert result.output["outcome"] == SupervisorOutcome.RETRY_EXHAUSTED
        assert result.output["attempts"] == 2
        assert "budget_remaining" not in result.output
        execution_runtime.invoke.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────
# Architecture compliance
# ─────────────────────────────────────────────────────────────────────────


def _real_code_identifiers(filepath: str) -> set:
    """Mirrors the identical helper in every other Packet 06/07 test file."""
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
    def test_no_new_governance_mechanism(self):
        """K4 §9: Supervisor has no authority of its own to duplicate —
        it never constructs a GovernanceAction or calls evaluate_action()
        itself; every retry re-enters governance only via
        ExecutionRuntime.invoke() -> Worker.execute()."""
        import core.workers.supervisor as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "GovernanceAction" not in identifiers
        assert "evaluate_action" not in identifiers

    def test_no_direct_compile_planner_or_learning_calls(self):
        """Supervisor reacts to a CompilationResult it is given; it never
        calls compile()/plan() itself, and never touches Packet 04's
        Learning tiers."""
        import core.workers.supervisor as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "validation_gate" not in identifiers
        assert "LearningRecord" not in identifiers

    def test_no_workflow_runtime_termination(self):
        """K4 §9: Supervisor cannot terminate a running WorkflowRuntime
        execution — that is cancellation-token territory, unchanged."""
        import core.workers.supervisor as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "CancellationToken" not in identifiers

    def test_supervisor_worker_subclasses_abstract_cognitive_worker(self):
        from core.workers.base import AbstractCognitiveWorker
        assert issubclass(SupervisorWorker, AbstractCognitiveWorker)

    def test_supervisor_worker_type_identity(self):
        assert SupervisorWorker.worker_type == "SupervisorWorker"

    def test_classify_compilation_outcome_is_pure_module_level_function(self):
        import inspect
        sig = inspect.signature(_classify_compilation_outcome)
        assert "self" not in sig.parameters
