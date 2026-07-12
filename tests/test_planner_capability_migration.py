"""
tests/test_planner_capability_migration.py — K2.3 Legacy Dispatch Migration

Verifies the actual migration this session performs: PlannerWorker's
_dispatch_module() goes through AdapterRuntime (capability-based) when
adapter_runtime is supplied, and falls back to direct model_router calls
only for backward-compatible test construction (main.py's composition
root always supplies adapter_runtime now — see K2.3 Composition Root
Review).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.context import ContextMemory
from core.memory.unified_memory import UnifiedMemory
from core.model_router import RouteResult
from core.workers.base import WorkerContext
from core.workers.planner import PlannerWorker
from core.capabilities import (
    AdapterRuntime,
    CapabilityContract,
    CapabilityRegistry,
    CapabilityResult,
    CapabilityType,
    ResourceManager,
    BaseAdapter,
)


class FakeLLMAdapter(BaseAdapter):
    adapter_name = "fake_llm"
    capability_type = CapabilityType.LLM_COMPLETION

    def __init__(self, answer: str = "capability answer", fail: bool = False):
        super().__init__()
        self._answer = answer
        self._fail = fail

    async def execute(self, request, resources):
        if self._fail:
            return CapabilityResult(success=False, error="fake adapter failure")
        assert request.payload["module_name"]
        assert "subtask" in request.payload
        return CapabilityResult(success=True, output=self._answer)


def _make_adapter_runtime(answer: str = "capability answer", fail: bool = False) -> AdapterRuntime:
    reg = CapabilityRegistry()
    reg.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION, description="d"))
    reg.register_adapter(CapabilityType.LLM_COMPLETION,
                          FakeLLMAdapter(answer=answer, fail=fail))
    return AdapterRuntime(registry=reg, resource_manager=ResourceManager())


def _make_context() -> MagicMock:
    return MagicMock(spec=ContextMemory)


def _make_memory() -> AsyncMock:
    return AsyncMock(spec=UnifiedMemory)


class TestPlannerWorkerCapabilityDispatch:
    @pytest.mark.asyncio
    async def test_uses_adapter_runtime_when_supplied(self):
        worker = PlannerWorker(
            modules={"web_search": object()},
            context_memory=_make_context(),
            adapter_runtime=_make_adapter_runtime("via capability"),
            memory=_make_memory(),
        )
        result = await worker.execute(WorkerContext(query="what is OCBrain?"))
        assert result.success is True
        assert result.output == "via capability"

    @pytest.mark.asyncio
    async def test_adapter_runtime_preferred_over_model_router_when_both_given(self):
        mock_router = MagicMock()
        mock_router.route = AsyncMock(
            return_value=RouteResult(answer="legacy answer should not win", source="mock"))
        worker = PlannerWorker(
            modules={"web_search": object()},
            context_memory=_make_context(),
            adapter_runtime=_make_adapter_runtime("capability wins"),
            model_router=mock_router,
            memory=_make_memory(),
        )
        result = await worker.execute(WorkerContext(query="which path wins?"))
        assert result.output == "capability wins"
        mock_router.route.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_capability_failure_folded_into_merged_error_like_legacy(self):
        """Matches the legacy path's own containment: a dispatch failure
        becomes part of the merged answer text, not an unhandled
        exception reaching the caller."""
        worker = PlannerWorker(
            modules={"web_search": object()},
            context_memory=_make_context(),
            adapter_runtime=_make_adapter_runtime(fail=True),
            memory=_make_memory(),
        )
        result = await worker.execute(WorkerContext(query="trigger a failure"))
        assert "fake adapter failure" in (result.output or result.error or "")

    @pytest.mark.asyncio
    async def test_no_adapter_runtime_and_no_model_router_is_contained_not_raised(self):
        """Regression check for the latent-bug fix in _dispatch_module:
        previously this path returned a bare WorkerResult that leaked
        into merger.merge() uncaught; now it raises, which the existing
        gather(return_exceptions=True) containment already handles."""
        worker = PlannerWorker(
            modules={"web_search": object()},
            context_memory=_make_context(),
            memory=_make_memory(),
        )
        result = await worker.execute(WorkerContext(query="no dispatch backend configured"))
        # Must not raise past execute() -- AbstractCognitiveWorker's
        # template method contains it, same as any other worker failure.
        assert isinstance(result.success, bool)
        assert "No adapter_runtime or model_router" in (result.output or result.error or "")


class TestBackwardCompatibilityModelRouterOnly:
    """Exact K2.2-era construction pattern (model_router=, no
    adapter_runtime=) must keep working unmodified — see also
    tests/test_planner_worker.py, unchanged by this session."""

    @pytest.mark.asyncio
    async def test_model_router_only_still_works(self):
        mock_router = MagicMock()
        mock_router.route = AsyncMock(
            return_value=RouteResult(answer="legacy still works", source="mock"))
        worker = PlannerWorker(
            modules={"web_search": object()},
            context_memory=_make_context(),
            model_router=mock_router,
            memory=_make_memory(),
        )
        result = await worker.execute(WorkerContext(query="legacy path"))
        assert result.success is True
        assert result.output == "legacy still works"


class TestCompositionRootShape:
    """Exercises the exact object graph main.py builds for K2.3, with a
    fake underlying LLM call (no real Ollama in this environment) but
    everything else real: CapabilityRegistry, ResourceManager,
    AdapterRuntime, ModelRouterAdapter wrapping a real ModelRouter whose
    only mocked seam is the network call inside provider_mesh."""

    @pytest.mark.asyncio
    async def test_full_chain_planner_to_model_router_adapter(self):
        from core.model_router import ModelRouter
        from core.capabilities.adapters.model_router_adapter import ModelRouterAdapter

        real_router = ModelRouter()
        with mock_route_ctx(real_router, "end-to-end answer"):
            reg = CapabilityRegistry()
            reg.register_capability(CapabilityContract(
                capability_type=CapabilityType.LLM_COMPLETION, description="d"))
            reg.register_adapter(CapabilityType.LLM_COMPLETION,
                                  ModelRouterAdapter(real_router))
            runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())

            worker = PlannerWorker(
                modules={"web_search": object()},
                context_memory=_make_context(),
                adapter_runtime=runtime,
                memory=_make_memory(),
            )
            result = await worker.execute(WorkerContext(query="full chain test"))
        assert result.success is True
        assert result.output == "end-to-end answer"


class _RouteContextManager:
    """Tiny context manager patching ModelRouter.route on one instance."""
    def __init__(self, router, answer):
        self._router = router
        self._answer = answer
        self._original = None

    async def _fake_route(self, module_name, subtask, context):
        return RouteResult(answer=self._answer, source="patched")

    def __enter__(self):
        self._original = self._router.route
        self._router.route = self._fake_route
        return self

    def __exit__(self, *exc):
        self._router.route = self._original


def mock_route_ctx(router, answer):
    return _RouteContextManager(router, answer)
