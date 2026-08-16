"""
tests/test_orchestrator_recovery.py — K4.2-H1 D5 (ADR-K4.2-H-05) Recovery
Budget integration.

Verifies core/orchestrator.py's Recovery Invariant: "Every user operation
has one authoritative autonomous recovery budget ... Planner and
Supervisor consume the same budget instance. Neither may create a hidden
retry universe."

H1-G5 is explicitly called out as requiring an integration test, not just
budget.consume() unit tests (see tests/core/cognitive/test_recovery.py
for those): two independently-constructed OperationRecoveryBudget objects
with identical max_total_recovery_attempts would produce identical-looking
counts while still violating the invariant. Only proving that the SAME
object instance is used -- inferred here by count propagation, since
Orchestrator's budget is a private local variable with no direct getter
-- actually verifies sharing.

Mocking strategy: interpret_request/plan/compile are patched at their
K4.2-H1-branch import sites (core/orchestrator.py imports each of these
LOCALLY, inside handle(), not at module scope -- so patching
"core.cognitive.X.Y" is the correct target; a module-scope patch of
core.orchestrator.Y would silently miss it). This isolates these tests to
Orchestrator's own recovery-wiring logic, already covered independently
by core/cognitive/planner.py's and core/cognitive/compiler.py's own test
suites.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.cognitive.compiler import CompilationResult, CompilationStatus
from core.cognitive.intent import Goal
from core.cognitive.planner import ExecutionPlan, PlannerResult, PlannerStatus
from core.cognitive.recovery import OperationRecoveryBudget
from core.context import ContextMemory
from core.governance.governance_kernel import GovernanceResult
from core.model_router import RouteResult
from core.orchestrator import Orchestrator
from core.memory.unified_memory import UnifiedMemory


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_orchestrator(max_recovery_attempts: int = 3):
    """An Orchestrator wired for the K4.2 branch, with governance mocked
    to always APPROVE (isolating these tests to D5's recovery-budget
    wiring, not governance evaluation, which has its own test suite) and
    a spied EventStream so emitted events are directly inspectable."""
    memory = AsyncMock(spec=UnifiedMemory)
    context = MagicMock(spec=ContextMemory)
    router = MagicMock()
    router.route = AsyncMock(return_value=RouteResult(answer="unused", source="mock"))
    governance = MagicMock()
    governance.evaluate_action = MagicMock(return_value=GovernanceResult())  # APPROVE by default
    event_stream = AsyncMock()
    execution_runtime = AsyncMock()
    workflow_runtime = MagicMock()  # only needs to be non-None to enter the K4.2 branch
    capability_registry = MagicMock()

    orch = Orchestrator(
        modules={}, context=context, router=router, memory=memory,
        governance=governance, event_stream=event_stream,
        execution_runtime=execution_runtime, workflow_runtime=workflow_runtime,
        capability_registry=capability_registry,
        use_k42_frontend=True, max_recovery_attempts=max_recovery_attempts,
    )
    return orch, execution_runtime, event_stream


def _impasse(op_id: str = "op-impasse") -> PlannerResult:
    return PlannerResult(status=PlannerStatus.IMPASSE, operation_id=op_id)


def _ready(goal_id: str = "g1", op_id: str = "op-ready") -> PlannerResult:
    return PlannerResult(
        status=PlannerStatus.READY_FOR_COMPILATION,
        execution_plan=ExecutionPlan(goal_id=goal_id),
        operation_id=op_id,
    )


def _goal(resource_id: str = "g1") -> Goal:
    return Goal(resource_id=resource_id,
                structured_form={"description": "test", "raw_request": "test"})


# ── H1-G5 (mandatory): shared budget instance ─────────────────────────

class TestSharedRecoveryBudget:
    @pytest.mark.asyncio
    async def test_same_budget_instance_reaches_supervisor_after_replan_attempts(self):
        """plan() impasses twice (consuming 2 of the shared budget via
        Orchestrator's re-plan loop), then succeeds on the third
        attempt; compilation is then rejected, triggering SupervisorWorker
        with context.parameters["recovery_budget"]. If Orchestrator
        created two separate budgets, the one reaching Supervisor would
        show internal_recovery_used == 0 despite the two prior
        consumptions above it -- this assertion fails in exactly that
        case, which is the actual point of this test.
        """
        orch, execution_runtime, _ = _make_orchestrator(max_recovery_attempts=5)
        captured_budgets = []

        async def _invoke_spy(worker_type, **kwargs):
            if worker_type == "SupervisorWorker":
                params = kwargs.get("metadata", {}).get("parameters", {})
                captured_budgets.append(params.get("recovery_budget"))
            return MagicMock(success=False)
        execution_runtime.invoke = AsyncMock(side_effect=_invoke_spy)

        goal = _goal()
        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan", new=AsyncMock(
                 side_effect=[_impasse(), _impasse(), _ready()])), \
             patch("core.cognitive.compiler.compile", new=AsyncMock(
                 return_value=CompilationResult(status=CompilationStatus.REJECTED))):
            await orch.handle("book a flight to Tokyo")

        assert len(captured_budgets) == 1, "SupervisorWorker was not invoked as expected"
        budget = captured_budgets[0]
        assert budget is not None, "recovery_budget was not threaded to SupervisorWorker at all"
        assert isinstance(budget, OperationRecoveryBudget)
        assert budget.internal_recovery_used == 2, (
            "Supervisor received a budget whose used-count does not "
            "reflect the 2 prior Planner re-plan consumptions -- "
            "Planner and Supervisor received SEPARATE budget instances, "
            "violating the Recovery Invariant"
        )
        assert budget.remaining == 3

    @pytest.mark.asyncio
    async def test_budget_shared_even_when_replan_never_triggers(self):
        """The simpler case: plan() succeeds immediately (budget
        untouched by the re-plan loop, internal_recovery_used == 0), and
        that same, still-fresh budget instance is still what reaches
        Supervisor on a subsequent compilation rejection."""
        orch, execution_runtime, _ = _make_orchestrator(max_recovery_attempts=3)
        captured_budgets = []

        async def _invoke_spy(worker_type, **kwargs):
            if worker_type == "SupervisorWorker":
                params = kwargs.get("metadata", {}).get("parameters", {})
                captured_budgets.append(params.get("recovery_budget"))
            return MagicMock(success=False)
        execution_runtime.invoke = AsyncMock(side_effect=_invoke_spy)

        goal = _goal()
        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan", new=AsyncMock(return_value=_ready())), \
             patch("core.cognitive.compiler.compile", new=AsyncMock(
                 return_value=CompilationResult(status=CompilationStatus.ESCALATED))):
            await orch.handle("a fine, simple request")

        assert len(captured_budgets) == 1
        budget = captured_budgets[0]
        assert isinstance(budget, OperationRecoveryBudget)
        assert budget.internal_recovery_used == 0
        assert budget.max_total_recovery_attempts == 3


# ── D5: bounded termination / exhaustion (H1-G4) ──────────────────────

class TestRecoveryBudgetBoundedTermination:
    @pytest.mark.asyncio
    async def test_budget_exhaustion_terminates_replan_loop(self):
        """Bounded termination (STOP condition: 'Orchestrator re-plan
        loop introduces unbounded behavior -- budget MUST enforce
        termination'). With max_recovery_attempts=2, plan() must be
        called at most 1 + 2 = 3 times total, never more, no matter how
        many times it keeps returning IMPASSE."""
        orch, _, _ = _make_orchestrator(max_recovery_attempts=2)
        goal = _goal()
        plan_mock = AsyncMock(return_value=_impasse())
        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan", new=plan_mock):
            result = await orch.handle("an impossible request")
        assert plan_mock.await_count == 3, (
            f"expected exactly 3 plan() calls (1 initial + 2 retries), "
            f"got {plan_mock.await_count}"
        )
        assert "could not form a plan" in result

    @pytest.mark.asyncio
    async def test_successful_replan_stops_the_loop_immediately(self):
        """The loop must not over-consume: if the SECOND plan() call
        succeeds, a third must never be attempted even though budget
        remains."""
        orch, _, _ = _make_orchestrator(max_recovery_attempts=5)
        goal = _goal()
        plan_mock = AsyncMock(side_effect=[_impasse(), _ready()])
        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan", new=plan_mock), \
             patch("core.cognitive.compiler.compile", new=AsyncMock(
                 return_value=CompilationResult(status=CompilationStatus.REJECTED))):
            await orch.handle("a request that needs one retry")
        assert plan_mock.await_count == 2

    @pytest.mark.asyncio
    async def test_rejected_precheck_is_not_retried_and_consumes_no_budget(self):
        """D5/D7 boundary: REJECTED_PRECHECK is deterministic (no LLM
        call in constraint extraction) -- retrying it can never produce
        a different outcome, so it must return immediately without
        entering the re-plan loop at all (plan() called exactly once)."""
        orch, _, _ = _make_orchestrator(max_recovery_attempts=5)
        goal = _goal()
        precheck_rejected = PlannerResult(
            status=PlannerStatus.REJECTED_PRECHECK, operation_id="op-precheck")
        plan_mock = AsyncMock(return_value=precheck_rejected)
        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan", new=plan_mock):
            result = await orch.handle("a self-contradictory request")
        assert plan_mock.await_count == 1, (
            "REJECTED_PRECHECK must not be retried -- it is deterministic"
        )
        assert "could not form a plan" in result


# ── D8: terminal impasse diagnostic event ──────────────────────────────

class TestTerminalImpasseEvent:
    @pytest.mark.asyncio
    async def test_terminal_impasse_event_emitted_on_exhaustion(self):
        """cognitive.planner_impasse_terminal fires exactly once, only
        when the budget is genuinely exhausted, with trace_id/
        operation_id/recovery_budget_state in its payload (D8)."""
        orch, _, event_stream = _make_orchestrator(max_recovery_attempts=1)
        goal = _goal()
        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan",
                   new=AsyncMock(return_value=_impasse(op_id="op-final"))):
            await orch.handle("an impossible request")

        terminal_calls = [
            call for call in event_stream.append.call_args_list
            if call.kwargs.get("event_type") == "cognitive.planner_impasse_terminal"
        ]
        assert len(terminal_calls) == 1
        payload = terminal_calls[0].kwargs["payload"]
        assert payload["trace_id"]
        assert payload["operation_id"] == "op-final"
        assert payload["goal_id"] == "g1"
        assert payload["recovery_budget_state"]["remaining"] == 0
        assert payload["recovery_budget_state"]["internal_recovery_used"] == 1
        assert payload["recovery_budget_state"]["max_total_recovery_attempts"] == 1

    @pytest.mark.asyncio
    async def test_terminal_impasse_event_not_emitted_on_success(self):
        """No terminal event when the budget is never exhausted --
        confirms the event is exhaustion-triggered, not emitted on every
        impasse."""
        orch, _, event_stream = _make_orchestrator(max_recovery_attempts=5)
        goal = _goal()
        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan",
                   new=AsyncMock(side_effect=[_impasse(), _ready()])), \
             patch("core.cognitive.compiler.compile", new=AsyncMock(
                 return_value=CompilationResult(status=CompilationStatus.REJECTED))):
            await orch.handle("a request that needs one retry")

        terminal_calls = [
            call for call in event_stream.append.call_args_list
            if call.kwargs.get("event_type") == "cognitive.planner_impasse_terminal"
        ]
        assert terminal_calls == []
