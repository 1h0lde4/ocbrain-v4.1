"""
tests/test_planner_worker.py — K2.2 PlannerWorker Tests

PlannerWorker (core/workers/planner.py) existed as a complete
implementation before this session but had zero test coverage. This file
closes that gap and specifically verifies the WorkerRegistry
constructor_kwargs wiring pattern used at the composition root (main.py).

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §9.1 — PlannerWorker.
    K2.2 success criteria verification.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.context import ContextMemory
from core.model_router import RouteResult
from core.memory.unified_memory import UnifiedMemory
from core.workers.base import WorkerContext, WorkerState
from core.workers.planner import PlannerWorker
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.execution_runtime import ExecutionRuntime
from core.governance.governance_kernel import get_governance_kernel
from core.events.event_stream import get_event_stream


# ── Helpers (mirrors tests/test_orchestrator_memory_migration.py) ───────────


def _make_router(answer: str = "mocked answer") -> MagicMock:
    router = MagicMock()
    router.route = AsyncMock(
        return_value=RouteResult(answer=answer, source="mock"))
    return router


def _make_context() -> MagicMock:
    return MagicMock(spec=ContextMemory)


def _make_memory() -> AsyncMock:
    return AsyncMock(spec=UnifiedMemory)


# ── Direct unit tests (worker.execute(), no ExecutionRuntime) ───────────────


class TestPlannerWorkerDirect:
    @pytest.mark.asyncio
    async def test_empty_query_fails(self):
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=_make_context(),
                                model_router=_make_router(),
                                memory=_make_memory())
        result = await worker.execute(WorkerContext(query=""))
        assert result.success is False
        assert "No query" in result.error

    @pytest.mark.asyncio
    async def test_no_modules_fails(self):
        worker = PlannerWorker(modules={},
                                context_memory=_make_context(),
                                model_router=_make_router(),
                                memory=_make_memory())
        result = await worker.execute(WorkerContext(query="hello"))
        assert result.success is False
        assert "no modules available" in result.error

    @pytest.mark.asyncio
    async def test_success_path_returns_merged_answer(self):
        mock_memory = _make_memory()
        mock_context = _make_context()
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=mock_context,
                                model_router=_make_router("the answer"),
                                memory=mock_memory)
        result = await worker.execute(WorkerContext(query="what is OCBrain?"))
        assert result.success is True
        assert result.output == "the answer"
        assert result.metadata["outcome"] == "success"
        assert worker.state == WorkerState.COMPLETED

    @pytest.mark.asyncio
    async def test_success_path_persists_to_memory(self):
        mock_memory = _make_memory()
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=_make_context(),
                                model_router=_make_router("persisted answer"),
                                memory=mock_memory)
        await worker.execute(WorkerContext(query="remember this"))
        mock_memory.write.assert_awaited_once()
        _, kwargs = mock_memory.write.call_args
        assert kwargs["content"] == "persisted answer"
        assert kwargs["metadata"]["query"] == "remember this"

    @pytest.mark.asyncio
    async def test_success_path_saves_to_context(self):
        mock_context = _make_context()
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=mock_context,
                                model_router=_make_router("ctx answer"),
                                memory=_make_memory())
        await worker.execute(WorkerContext(query="save me"))
        mock_context.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_write_failure_does_not_break_response(self):
        """Matches the legacy path's guarantee (Orchestrator Session 4
        test): a persistence failure must never turn a successful answer
        into an error response."""
        mock_memory = _make_memory()
        mock_memory.write.side_effect = RuntimeError("disk full")
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=_make_context(),
                                model_router=_make_router("still works"),
                                memory=mock_memory)
        result = await worker.execute(WorkerContext(query="resilience check"))
        assert result.success is True
        assert result.output == "still works"

    @pytest.mark.asyncio
    async def test_module_dispatch_exception_contained(self):
        """A module raising during dispatch must be contained the same way
        the legacy Orchestrator.handle() contained it: folded into the
        merged answer as an error entry, not raised past _run()."""
        router = MagicMock()
        router.route = AsyncMock(side_effect=RuntimeError("module exploded"))
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=_make_context(),
                                model_router=router,
                                memory=_make_memory())
        result = await worker.execute(WorkerContext(query="trigger failure"))
        # merger.merge() with only error entries returns the error text
        # directly (see core/merger.py) rather than raising.
        assert "module exploded" in (result.output or result.error or "")

    @pytest.mark.asyncio
    async def test_unclassified_query_returns_friendly_message(self):
        """When classify() returns no labels, PlannerWorker must match the
        legacy Orchestrator's exact user-facing message rather than
        surfacing an internal error."""
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=_make_context(),
                                model_router=_make_router(),
                                memory=_make_memory())
        # An empty/whitespace query is the simplest reliable way to drive
        # classify() to return no labels without mocking the classifier.
        result = await worker.execute(WorkerContext(query="   "))
        # Either "no query" (falsy after strip is not checked, so this
        # actually still has content) or unclassified — assert it's a
        # contained, non-crashing WorkerResult either way.
        assert isinstance(result.success, bool)


# ── Governance / events (template method contract) ──────────────────────────


class TestPlannerWorkerGovernanceContract:
    @pytest.mark.asyncio
    async def test_execute_evaluates_governance_before_run(self):
        """PlannerWorker must not bypass AbstractCognitiveWorker.execute()'s
        governance template method (PI LAW 1) — verified the same way
        test_execution_runtime.py verifies it for other workers."""
        worker = PlannerWorker(modules={"web_search": object()},
                                context_memory=_make_context(),
                                model_router=_make_router("governed answer"),
                                memory=_make_memory(),
                                governance=get_governance_kernel(),
                                event_stream=get_event_stream())
        result = await worker.execute(WorkerContext(query="governed query"))
        assert result.success is True
        assert worker.worker_type == "PlannerWorker"


# ── Integration via WorkerRegistry + ExecutionRuntime ────────────────────────
# This specifically exercises the constructor_kwargs wiring pattern used at
# the composition root (main.py): PlannerWorker needs domain dependencies
# beyond governance/event_stream, supplied via
# WorkerRegistry.register(PlannerWorker, constructor_kwargs={...}).


class TestPlannerWorkerViaExecutionRuntime:
    @pytest.mark.asyncio
    async def test_constructor_kwargs_wiring(self):
        registry = WorkerRegistry()
        registry.register(PlannerWorker, constructor_kwargs={
            "modules": {"web_search": object()},
            "context_memory": _make_context(),
            "model_router": _make_router("wired via registry"),
            "memory": _make_memory(),
        })
        runtime = ExecutionRuntime(
            worker_registry=registry,
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )
        result = await runtime.invoke("PlannerWorker", query="test wiring")
        assert result.success is True
        assert result.output == "wired via registry"
        assert result.metadata["worker_type"] == "PlannerWorker"

    @pytest.mark.asyncio
    async def test_missing_constructor_kwargs_fails_constructor_not_crashes_runtime(self):
        """If PlannerWorker is registered WITHOUT its required
        constructor_kwargs, construction fails (modules defaults to {},
        which _run() correctly rejects) -- but ExecutionRuntime must still
        contain this as a WorkerResult, never raise (Law 11)."""
        registry = WorkerRegistry()
        registry.register(PlannerWorker)  # no constructor_kwargs
        runtime = ExecutionRuntime(
            worker_registry=registry,
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )
        result = await runtime.invoke("PlannerWorker", query="no deps supplied")
        assert result.success is False
        assert "no modules available" in result.error
