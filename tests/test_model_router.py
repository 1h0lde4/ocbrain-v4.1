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
