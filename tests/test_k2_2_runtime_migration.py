"""
tests/test_k2_2_runtime_migration.py — K2.2 Production Runtime Migration

Verifies the actual cutover this session performs:

    Orchestrator.handle() -> WorkflowRuntime -> ExecutionRuntime ->
    PlannerWorker

when workflow_runtime is supplied (main.py's composition root, K2.2), and
that the untouched legacy classify->dispatch->merge flow still works
identically when it is not (existing tests, e.g.
tests/test_execution_runtime.py::TestBackwardCompatibility, construct
Orchestrator without it).

Phase 0 audit context (see K2.2 Cutover Report): before this session,
main.py already constructed ExecutionRuntime and passed it to Orchestrator,
but nothing inside Orchestrator.handle() ever called it -- self._execution_
runtime was stored and never read. WorkflowRuntime, WorkflowDefinition, and
PlannerWorker existed as complete, well-tested-in-isolation-by-this-session
implementations with zero production callers. This suite is what proves the
wiring this session adds actually closes that gap, not just that the
pieces exist.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.context import ContextMemory
from core.model_router import RouteResult
from core.memory.unified_memory import UnifiedMemory
from core.orchestrator import Orchestrator
from core.workers.planner import PlannerWorker
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.execution_runtime import ExecutionRuntime
from core.workflow.runtime import WorkflowRuntime
from core.governance.governance_kernel import (
    GovernanceAction,
    GovernanceKernel,
    GovernanceResult,
    GovernanceVerdict,
    get_governance_kernel,
)
from core.events.event_stream import get_event_stream


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_router(answer: str = "mocked answer") -> MagicMock:
    router = MagicMock()
    router.route = AsyncMock(
        return_value=RouteResult(answer=answer, source="mock"))
    return router


def _make_context() -> MagicMock:
    return MagicMock(spec=ContextMemory)


def _make_memory() -> AsyncMock:
    return AsyncMock(spec=UnifiedMemory)


def _make_orchestrator_with_workflow_runtime(
    answer: str = "wired answer",
    modules: dict | None = None,
    memory: AsyncMock | None = None,
    context: MagicMock | None = None,
    router: MagicMock | None = None,
):
    """Builds an Orchestrator wired exactly the way main.py wires it for
    K2.2: WorkerRegistry -> ExecutionRuntime -> WorkflowRuntime, PlannerWorker
    registered with the same modules/context/router/memory Orchestrator
    itself receives."""
    modules = modules if modules is not None else {"web_search": object()}
    memory = memory or _make_memory()
    context = context or _make_context()
    router = router or _make_router(answer)

    registry = WorkerRegistry()
    registry.register(PlannerWorker, constructor_kwargs={
        "modules": modules,
        "context_memory": context,
        "model_router": router,
        "memory": memory,
    })
    execution_runtime = ExecutionRuntime(
        worker_registry=registry,
        governance=get_governance_kernel(),
        event_stream=get_event_stream(),
    )
    workflow_runtime = WorkflowRuntime(
        execution_runtime=execution_runtime,
        event_stream=get_event_stream(),
    )
    orch = Orchestrator(
        modules, context, router,
        memory=memory,
        governance=get_governance_kernel(),
        event_stream=get_event_stream(),
        execution_runtime=execution_runtime,
        workflow_runtime=workflow_runtime,
    )
    return orch, memory, context, router


# ── New path: Orchestrator WITH workflow_runtime ─────────────────────────────


class TestOrchestratorRoutesThroughWorkflowRuntime:
    @pytest.mark.asyncio
    async def test_answer_comes_from_planner_worker(self):
        orch, memory, context, router = \
            _make_orchestrator_with_workflow_runtime("the workflow answer")
        try:
            answer = await orch.handle("what is OCBrain?")
        finally:
            await orch.close()
        assert answer == "the workflow answer"

    @pytest.mark.asyncio
    async def test_memory_write_happens_exactly_once(self):
        """PlannerWorker performs the memory write internally (K2.2) --
        Orchestrator's new branch must NOT also write, or every interaction
        would be persisted twice."""
        orch, memory, context, router = \
            _make_orchestrator_with_workflow_runtime("dedup check")
        try:
            await orch.handle("does this write once?")
        finally:
            await orch.close()
        memory.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_save_happens_exactly_once(self):
        orch, memory, context, router = \
            _make_orchestrator_with_workflow_runtime("save check")
        try:
            await orch.handle("does context save once?")
        finally:
            await orch.close()
        context.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_failure_returns_error_not_crash(self):
        """If the underlying module dispatch fails entirely, the workflow
        path must degrade the same way the legacy path always has: a
        user-facing message, never an unhandled exception."""
        failing_router = MagicMock()
        failing_router.route = AsyncMock(
            side_effect=RuntimeError("downstream provider unavailable"))
        orch, memory, context, router = \
            _make_orchestrator_with_workflow_runtime(router=failing_router)
        try:
            answer = await orch.handle("trigger a downstream failure")
        finally:
            await orch.close()
        # merger.merge() folds a single dispatch error into a returned
        # string rather than failing the workflow outright (matches
        # legacy behaviour) -- assert we got a real answer back, not a
        # raised exception reaching the caller.
        assert isinstance(answer, str)
        assert "downstream provider unavailable" in answer

    @pytest.mark.asyncio
    async def test_orchestrator_level_governance_still_enforced(self):
        """The K2.2 migration must not weaken governance -- a REJECT
        verdict at the orchestrator level must still short-circuit before
        WorkflowRuntime is ever reached (PI LAW 1)."""
        class AlwaysRejectGovernor:
            name = "AlwaysReject"

            def evaluate(self, action: GovernanceAction) -> GovernanceResult:
                return GovernanceResult(
                    verdict=GovernanceVerdict.REJECT,
                    reason="test rejection",
                    governor=self.name,
                )

        rejecting_kernel = GovernanceKernel()
        rejecting_kernel.register_governor(AlwaysRejectGovernor())

        modules = {"web_search": object()}
        memory = _make_memory()
        context = _make_context()
        router = _make_router("should never be reached")

        registry = WorkerRegistry()
        registry.register(PlannerWorker, constructor_kwargs={
            "modules": modules, "context_memory": context,
            "model_router": router, "memory": memory,
        })
        execution_runtime = ExecutionRuntime(
            worker_registry=registry, governance=rejecting_kernel,
            event_stream=get_event_stream(),
        )
        workflow_runtime = WorkflowRuntime(
            execution_runtime=execution_runtime,
            event_stream=get_event_stream(),
        )
        orch = Orchestrator(
            modules, context, router, memory=memory,
            governance=rejecting_kernel, event_stream=get_event_stream(),
            execution_runtime=execution_runtime,
            workflow_runtime=workflow_runtime,
        )
        try:
            answer = await orch.handle("this should be rejected")
        finally:
            await orch.close()

        assert "blocked by governance" in answer
        router.route.assert_not_awaited()
        memory.write.assert_not_awaited()


# ── Legacy path: Orchestrator WITHOUT workflow_runtime (regression) ─────────


class TestLegacyPathUnchangedWhenNoWorkflowRuntime:
    @pytest.mark.asyncio
    async def test_legacy_path_still_works(self):
        """workflow_runtime defaults to None -- this must reproduce the
        exact pre-K2.2 behaviour, unmodified."""
        memory = _make_memory()
        context = _make_context()
        router = _make_router("legacy answer")
        orch = Orchestrator({}, context, router, memory=memory)
        try:
            answer = await orch.handle("legacy path query")
        finally:
            await orch.close()
        assert answer == "legacy answer"
        memory.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_legacy_path_used_when_workflow_runtime_explicitly_none(self):
        memory = _make_memory()
        context = _make_context()
        router = _make_router("explicit none answer")
        orch = Orchestrator({}, context, router, memory=memory,
                             workflow_runtime=None)
        try:
            answer = await orch.handle("explicit none")
        finally:
            await orch.close()
        assert answer == "explicit none answer"


# ── A/B parity ────────────────────────────────────────────────────────────


class TestPathParity:
    @pytest.mark.asyncio
    async def test_both_paths_return_same_answer_for_same_router_response(self):
        """Not byte-for-byte identical internals (different call graph),
        but the observable contract -- same query, same mocked module
        response -- must produce the same answer either way."""
        legacy_orch = Orchestrator(
            {}, _make_context(), _make_router("consistent answer"),
            memory=_make_memory(),
        )
        new_orch, _, _, _ = _make_orchestrator_with_workflow_runtime(
            "consistent answer")
        try:
            legacy_answer = await legacy_orch.handle("same query")
            new_answer = await new_orch.handle("same query")
        finally:
            await legacy_orch.close()
            await new_orch.close()
        assert legacy_answer == new_answer == "consistent answer"
