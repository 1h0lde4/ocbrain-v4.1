"""Tests for core/model_router.py (mocked Ollama)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.model_router import ModelRouter, _cosine_sim_text


def test_cosine_sim_identical():
    assert _cosine_sim_text("hello world", "hello world") == pytest.approx(1.0)


def test_cosine_sim_empty():
    assert _cosine_sim_text("", "hello") == 0.0
    assert _cosine_sim_text("hello", "") == 0.0


def test_cosine_sim_partial():
    score = _cosine_sim_text("python is fast", "python is slow")
    assert 0.0 < score < 1.0


def test_cosine_sim_no_overlap():
    assert _cosine_sim_text("apple banana", "dog cat") == 0.0


@pytest.mark.asyncio
async def test_route_bootstrap_calls_external():
    router = ModelRouter()

    mock_context = MagicMock()
    mock_context.format_for_prompt.return_value = ""

    with patch.object(router, "_call_external", new_callable=AsyncMock) as mock_ext, \
         patch.object(router, "_record_training_pair") as mock_rec, \
         patch.object(router, "_increment_query_count"):

        mock_ext.return_value = "external answer"
        result = await router.route("coding", "write hello world", mock_context)

        assert result.answer == "external answer"
        assert result.source == "external"
        mock_ext.assert_called_once()
        mock_rec.assert_called_once()


@pytest.mark.asyncio
async def test_route_native_calls_own_model():
    from core.config import config
    router = ModelRouter()

    mock_context = MagicMock()
    mock_context.format_for_prompt.return_value = ""

    # Temporarily set stage to native
    original = config.get_module_state("knowledge").get("stage")
    config.set_module_state("knowledge", "stage", "native")

    try:
        with patch.object(router, "_call_own_model", new_callable=AsyncMock) as mock_own, \
             patch.object(router, "_spot_check", new_callable=AsyncMock) as mock_check, \
             patch.object(router, "_increment_query_count"):

            mock_own.return_value = "own model answer"
            mock_check.return_value = None

            result = await router.route("knowledge", "explain AI", mock_context)
            assert result.answer == "own model answer"
            assert result.source == "native"
    finally:
        config.set_module_state("knowledge", "stage", original or "bootstrap")


def test_stage_promotion_bootstrap_to_shadow():
    router = ModelRouter()
    from core.config import config

    # Reset
    config.set_module_state("web_search", "stage", "bootstrap")
    config.set_module_state("web_search", "query_count", 0)

    # Simulate reaching 1000 queries
    config.set_module_state("web_search", "query_count", 1000)
    router._maybe_promote("web_search")

    state = config.get_module_state("web_search")
    assert state["stage"] == "shadow"

    # Reset back
    config.set_module_state("web_search", "stage", "bootstrap")
    config.set_module_state("web_search", "query_count", 0)


def test_regression_triggers_rollback():
    router = ModelRouter()
    from core.config import config

    config.set_module_state("knowledge", "stage", "native")
    # Fill recent scores with low values
    router._recent_scores["knowledge"] = [0.5] * 100  # below 0.70 threshold
    config.set_module_state("knowledge", "maturity_score", 0.5)

    router._maybe_rollback("knowledge")
    state = config.get_module_state("knowledge")
    assert state["stage"] == "shadow"

    # Restore
    config.set_module_state("knowledge", "stage", "bootstrap")


# ── CTX-SCOPE-001 caller wiring: does scope actually reach format_for_prompt? ──
#
# The audit's row #4 (docs/Bugs Hunt & fix reports/CONTEXT_ISOLATION_CALLER_AUDIT_SEP2026.md)
# traces the real unwired read to here, not to planner.py's line number it
# cites -- _build_prompt() is the true sink. These tests prove the thread,
# not just that it doesn't crash: they assert the actual scope value that
# reaches context.format_for_prompt().


def test_build_prompt_forwards_scope_to_format_for_prompt():
    router = ModelRouter()
    mock_context = MagicMock()
    mock_context.format_for_prompt.return_value = ""

    router._build_prompt("a subtask", mock_context, "caller-scope-123")

    mock_context.format_for_prompt.assert_called_once_with(5, scope="caller-scope-123")


def test_build_prompt_default_scope_is_empty_string_not_none():
    """The default must match ContextMemory.format_for_prompt()'s own
    unscoped sentinel exactly -- "" -- not None, so omitting scope keeps
    behaving exactly as it did before this fix (see
    tests/test_context_scope_security.py::test_no_scope_supplied_preserves_legacy_shared_behavior,
    which is the ContextMemory-level half of this same guarantee)."""
    router = ModelRouter()
    mock_context = MagicMock()
    mock_context.format_for_prompt.return_value = ""

    router._build_prompt("a subtask", mock_context)

    mock_context.format_for_prompt.assert_called_once_with(5, scope="")


@pytest.mark.asyncio
async def test_route_bootstrap_forwards_scope_end_to_end():
    """route() -> _call_external() -> _build_prompt() -> format_for_prompt(),
    with nothing mocked in between -- only the actual network call
    (generate_with_fallback) and the context object are faked."""
    router = ModelRouter()
    mock_context = MagicMock()
    mock_context.format_for_prompt.return_value = ""

    with patch("core.model_router.generate_with_fallback", new_callable=AsyncMock) as mock_gen, \
         patch.object(router, "_record_training_pair"), \
         patch.object(router, "_increment_query_count"):
        mock_gen.return_value = "external answer"
        await router.route("coding", "write hello world", mock_context, scope="route-e2e-scope")

    mock_context.format_for_prompt.assert_called_once_with(5, scope="route-e2e-scope")


@pytest.mark.asyncio
async def test_stream_route_forwards_scope_to_build_prompt():
    """The streaming sibling of route() -- exercised directly by
    interface/api.py's single-module SSE fast path, which this same fix
    also wires (found during verification, not named in the original
    audit)."""
    router = ModelRouter()
    mock_context = MagicMock()
    mock_context.format_for_prompt.return_value = ""

    with patch("core.model_router.httpx.AsyncClient") as mock_client_cls:
        mock_stream_cm = AsyncMock()
        mock_response = MagicMock()

        async def _empty_lines():
            return
            yield  # pragma: no cover -- makes this an async generator

        mock_response.aiter_lines = _empty_lines
        mock_response.raise_for_status = MagicMock()
        mock_stream_cm.__aenter__.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value.stream = MagicMock(
            return_value=mock_stream_cm)

        async for _ in router.stream_route("coding", "hi", mock_context, scope="stream-scope"):
            pass

    mock_context.format_for_prompt.assert_called_once_with(5, scope="stream-scope")
