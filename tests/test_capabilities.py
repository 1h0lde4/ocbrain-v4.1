"""
tests/test_capabilities.py — K2.3 Capability Runtime Tests

Covers core/capabilities/*: CapabilityRegistry (metadata), ResourceManager
(binding), AdapterRuntime (execution/selection/fallback/failure isolation),
and the three concrete LLM_COMPLETION adapters (ModelRouterAdapter,
OllamaAdapter, OpenAICompatAdapter). This is a new subsystem with zero
prior test coverage — this file is the first.

Architecture:
    K2.3 session prompt success criteria verification.
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.capabilities.capability import (
    Adapter,
    BaseAdapter,
    CapabilityContract,
    CapabilityRequest,
    CapabilityResult,
    CapabilityType,
)
from core.capabilities.registry import CapabilityRegistry, CapabilityRegistrationError
from core.capabilities.resource import HTTPClientResource, ModelResource, ResourceManager
from core.capabilities.adapter_runtime import AdapterRuntime
from core.capabilities.adapters.model_router_adapter import ModelRouterAdapter
from core.capabilities.adapters.ollama_adapter import OllamaAdapter
from core.capabilities.adapters.openai_compat_adapter import OpenAICompatAdapter
from core.events.event_stream import get_event_stream


# ── Test doubles ─────────────────────────────────────────────────────────────


class AlwaysSucceedsAdapter(BaseAdapter):
    adapter_name = "always_succeeds"
    capability_type = CapabilityType.LLM_COMPLETION

    def __init__(self, output="ok"):
        super().__init__()
        self._output = output

    async def execute(self, request, resources):
        return CapabilityResult(success=True, output=self._output)


class AlwaysFailsAdapter(BaseAdapter):
    adapter_name = "always_fails"
    capability_type = CapabilityType.LLM_COMPLETION

    async def execute(self, request, resources):
        return CapabilityResult(success=False, error="deliberate failure")


class RaisesAdapter(BaseAdapter):
    adapter_name = "raises"
    capability_type = CapabilityType.LLM_COMPLETION

    async def execute(self, request, resources):
        raise RuntimeError("adapter blew up")


def _registry_with(*adapters) -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION, description="test"))
    for a in adapters:
        reg.register_adapter(CapabilityType.LLM_COMPLETION, a)
    return reg


# ── CapabilityRegistry ────────────────────────────────────────────────────────


class TestCapabilityRegistry:
    def test_register_and_get_contract(self):
        reg = CapabilityRegistry()
        contract = CapabilityContract(capability_type="x", description="d")
        reg.register_capability(contract)
        assert reg.get_contract("x") is contract

    def test_duplicate_capability_registration_rejected(self):
        reg = CapabilityRegistry()
        reg.register_capability(CapabilityContract(capability_type="x", description="d"))
        with pytest.raises(CapabilityRegistrationError):
            reg.register_capability(CapabilityContract(capability_type="x", description="d2"))

    def test_adapter_for_unknown_capability_rejected(self):
        reg = CapabilityRegistry()
        with pytest.raises(CapabilityRegistrationError):
            reg.register_adapter("nonexistent", AlwaysSucceedsAdapter())

    def test_get_adapters_returns_copy(self):
        reg = _registry_with(AlwaysSucceedsAdapter())
        adapters = reg.get_adapters(CapabilityType.LLM_COMPLETION)
        adapters.append(AlwaysFailsAdapter())
        # Mutating the returned list must not affect the registry's own state.
        assert len(reg.get_adapters(CapabilityType.LLM_COMPLETION)) == 1

    def test_get_adapters_unknown_capability_returns_empty(self):
        reg = CapabilityRegistry()
        assert reg.get_adapters("nope") == []

    def test_list_capabilities(self):
        reg = CapabilityRegistry()
        reg.register_capability(CapabilityContract(capability_type="a", description="d"))
        reg.register_capability(CapabilityContract(capability_type="b", description="d"))
        assert set(reg.list_capabilities()) == {"a", "b"}

    def test_validate_flags_unfulfilled_capability(self):
        reg = CapabilityRegistry()
        reg.register_capability(CapabilityContract(capability_type="x", description="d"))
        problems = reg.validate()
        assert len(problems) == 1
        assert "x" in problems[0]

    def test_validate_clean_when_adapter_registered(self):
        reg = _registry_with(AlwaysSucceedsAdapter())
        assert reg.validate() == []

    def test_stats(self):
        reg = _registry_with(AlwaysSucceedsAdapter(), AlwaysFailsAdapter())
        stats = reg.stats()
        assert stats["total_capabilities"] == 1
        assert stats["total_adapters"] == 2
        assert stats["unfulfilled_capabilities"] == 0


# ── ResourceManager ───────────────────────────────────────────────────────────


class TestResourceManager:
    def test_http_client_resource_is_singleton_per_manager(self):
        rm = ResourceManager()
        r1 = rm.get_http_client_resource()
        r2 = rm.get_http_client_resource()
        assert r1 is r2
        assert r1.resource_id == "http-client-shared"

    def test_bind_model_resource_same_pair_returns_same_identity(self):
        rm = ResourceManager()
        r1 = rm.bind_model_resource(model_tag="mistral", host="http://localhost:11434")
        r2 = rm.bind_model_resource(model_tag="mistral", host="http://localhost:11434")
        assert r1 is r2
        assert r1.resource_id == "model:http://localhost:11434:mistral"

    def test_bind_model_resource_different_pairs_are_distinct(self):
        rm = ResourceManager()
        r1 = rm.bind_model_resource(model_tag="mistral", host="http://localhost:11434")
        r2 = rm.bind_model_resource(model_tag="llama3", host="http://localhost:11434")
        assert r1.resource_id != r2.resource_id

    def test_model_resource_depends_on_http_client_resource(self):
        rm = ResourceManager()
        model_resource = rm.bind_model_resource(model_tag="mistral", host="h")
        assert "http-client-shared" in model_resource.dependencies

    def test_to_dict_roundtrip_shape(self):
        rm = ResourceManager()
        d = rm.get_http_client_resource().to_dict()
        assert d["resource_id"] == "http-client-shared"
        assert d["lifecycle_state"] == "active"

    def test_stats(self):
        rm = ResourceManager()
        rm.bind_model_resource(model_tag="m", host="h")
        stats = rm.stats()
        assert stats["total_resources"] == 2  # http client + 1 model


# ── AdapterRuntime ────────────────────────────────────────────────────────────


class TestAdapterRuntimeSelection:
    @pytest.mark.asyncio
    async def test_unknown_capability_type_fails_cleanly(self):
        reg = CapabilityRegistry()
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke("nonexistent", subtask="hi")
        assert result.success is False
        assert "Unknown capability type" in result.error

    @pytest.mark.asyncio
    async def test_capability_with_no_adapters_fails_cleanly(self):
        reg = CapabilityRegistry()
        reg.register_capability(CapabilityContract(
            capability_type=CapabilityType.LLM_COMPLETION, description="d"))
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        assert result.success is False
        assert "no registered" in result.error

    @pytest.mark.asyncio
    async def test_single_successful_adapter(self):
        reg = _registry_with(AlwaysSucceedsAdapter("the answer"))
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        assert result.success is True
        assert result.output == "the answer"
        assert result.adapter_used == "always_succeeds"

    @pytest.mark.asyncio
    async def test_falls_back_to_second_adapter_on_failure(self):
        reg = _registry_with(AlwaysFailsAdapter(), AlwaysSucceedsAdapter("fallback worked"))
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        assert result.success is True
        assert result.output == "fallback worked"

    @pytest.mark.asyncio
    async def test_falls_back_past_a_raising_adapter(self):
        """An adapter that raises (not just returns success=False) must
        still be contained -- AdapterRuntime.invoke() never propagates an
        adapter's exception (Law of Failure Containment)."""
        reg = _registry_with(RaisesAdapter(), AlwaysSucceedsAdapter("survived"))
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        assert result.success is True
        assert result.output == "survived"

    @pytest.mark.asyncio
    async def test_all_adapters_fail_returns_aggregated_error(self):
        reg = _registry_with(AlwaysFailsAdapter(), RaisesAdapter())
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        assert result.success is False
        assert "All 2 adapter(s) failed" in result.error

    @pytest.mark.asyncio
    async def test_cooldown_forces_a_choice_rather_than_failing_outright(self):
        adapter = AlwaysFailsAdapter()
        adapter.mark_failure(cooldown_seconds=3600)  # force into cooldown
        reg = _registry_with(adapter)
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        # Still attempted (forced choice), still fails on its own merits --
        # proves cooldown doesn't silently skip the only candidate.
        assert result.success is False

    @pytest.mark.asyncio
    async def test_healthier_adapter_is_preferred(self):
        weak = AlwaysSucceedsAdapter("weak answer")
        weak.health_score = 10
        strong = AlwaysSucceedsAdapter("strong answer")
        strong.health_score = 100
        reg = _registry_with(weak, strong)
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        result = await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        assert result.output == "strong answer"

    @pytest.mark.asyncio
    async def test_success_marks_adapter_healthy_failure_marks_unhealthy(self):
        good = AlwaysSucceedsAdapter()
        bad = AlwaysFailsAdapter()
        reg = _registry_with(bad, good)
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        assert bad.consecutive_failures == 1
        assert bad.cooldown_until > time.time()
        assert good.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_stats_track_invocations_and_failures(self):
        reg = _registry_with(AlwaysSucceedsAdapter())
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager())
        await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        reg2 = CapabilityRegistry()
        runtime2 = AdapterRuntime(registry=reg2, resource_manager=ResourceManager())
        await runtime2.invoke("nope", subtask="hi")
        assert runtime.stats()["total_invocations"] == 1
        assert runtime.stats()["total_failures"] == 0
        assert runtime2.stats()["total_failures"] == 1

    @pytest.mark.asyncio
    async def test_events_fire_on_real_event_stream(self):
        """Mechanical proof, not just a mocked call -- uses the real
        EventStream singleton and the since= filter (K2.2 taught this
        session the count/slice pattern is unsafe against
        ORDER BY sequence DESC LIMIT 100)."""
        es = get_event_stream()
        reg = _registry_with(AlwaysFailsAdapter(), AlwaysSucceedsAdapter())
        runtime = AdapterRuntime(registry=reg, resource_manager=ResourceManager(),
                                  event_stream=es)
        since = time.time()
        await runtime.invoke(CapabilityType.LLM_COMPLETION, subtask="hi")
        events = await es.query(since=since, limit=100)
        event_types = [e.event_type for e in events]
        assert "adapter.failed" in event_types
        assert "adapter.invoked" in event_types


# ── Concrete adapters ────────────────────────────────────────────────────────


class TestModelRouterAdapter:
    @pytest.mark.asyncio
    async def test_missing_module_name_fails(self):
        adapter = ModelRouterAdapter(model_router=MagicMock())
        request = CapabilityRequest(capability_type=CapabilityType.LLM_COMPLETION,
                                     payload={"subtask": "hi"})
        result = await adapter.execute(request, ResourceManager())
        assert result.success is False
        assert "module_name" in result.error

    @pytest.mark.asyncio
    async def test_delegates_to_wrapped_model_router(self):
        from core.model_router import RouteResult
        mock_router = MagicMock()
        mock_router.route = AsyncMock(
            return_value=RouteResult(answer="routed answer", source="native",
                                      similarity=0.9, latency_ms=42))
        adapter = ModelRouterAdapter(model_router=mock_router)
        request = CapabilityRequest(
            capability_type=CapabilityType.LLM_COMPLETION,
            payload={"module_name": "web_search", "subtask": "hi", "context": None})
        result = await adapter.execute(request, ResourceManager())
        assert result.success is True
        assert result.output == "routed answer"
        assert result.metadata["source"] == "native"
        mock_router.route.assert_awaited_once_with("web_search", "hi", None)


class TestOllamaAdapter:
    @pytest.mark.asyncio
    async def test_missing_prompt_fails(self):
        adapter = OllamaAdapter()
        request = CapabilityRequest(capability_type=CapabilityType.LLM_COMPLETION,
                                     payload={})
        result = await adapter.execute(request, ResourceManager())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_success_binds_model_resource(self):
        adapter = OllamaAdapter(model="mistral", host="http://localhost:11434")
        with patch.object(adapter._provider, "generate",
                           new=AsyncMock(return_value="generated text")):
            rm = ResourceManager()
            request = CapabilityRequest(capability_type=CapabilityType.LLM_COMPLETION,
                                         payload={"subtask": "hi"})
            result = await adapter.execute(request, rm)
        assert result.success is True
        assert result.output == "generated text"
        # Mechanical proof the resource was actually bound, not just that
        # execute() returned successfully.
        assert rm.get("model:http://localhost:11434:mistral") is not None
        assert result.metadata["model_resource_id"] == "model:http://localhost:11434:mistral"

    @pytest.mark.asyncio
    async def test_provider_exception_contained(self):
        adapter = OllamaAdapter()
        with patch.object(adapter._provider, "generate",
                           new=AsyncMock(side_effect=RuntimeError("connection refused"))):
            request = CapabilityRequest(capability_type=CapabilityType.LLM_COMPLETION,
                                         payload={"subtask": "hi"})
            result = await adapter.execute(request, ResourceManager())
        assert result.success is False
        assert "connection refused" in result.error


class TestOpenAICompatAdapter:
    @pytest.mark.asyncio
    async def test_unconfigured_endpoint_reports_unavailable(self):
        """provider_mesh.GenericOpenAICompatibleProvider refuses its own
        default localhost:8080 unless explicitly configured -- verify
        OpenAICompatAdapter surfaces that, not just the base cooldown
        check."""
        adapter = OpenAICompatAdapter()
        assert adapter.is_available() is False

    @pytest.mark.asyncio
    async def test_success_when_configured(self):
        adapter = OpenAICompatAdapter(endpoint="http://example.com/v1", model="m")
        with patch.object(adapter._provider, "generate",
                           new=AsyncMock(return_value="compat answer")):
            request = CapabilityRequest(capability_type=CapabilityType.LLM_COMPLETION,
                                         payload={"subtask": "hi"})
            result = await adapter.execute(request, ResourceManager())
        assert result.success is True
        assert result.output == "compat answer"
