import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from core.classifier_v3 import classify, MODULES
from core.orchestrator_v3 import run_module, merge_results, orchestrate
from core.provider_mesh import generate_with_fallback
from core.prompt.cache import compress_context, cached_generate, _prompt_cache


# ──────────────────────────────────────────────────────────────────────────────
# 1. Semantic Classifier
# ──────────────────────────────────────────────────────────────────────────────

def test_semantic_classifier_returns_valid_format():
    """classify() always returns a list of dicts with 'module' and 'score' keys."""
    results = classify("can you write a python script", top_k=1)
    assert len(results) == 1
    assert "module" in results[0]
    assert "score" in results[0]
    assert isinstance(results[0]["score"], float)
    assert 0.0 <= results[0]["score"] <= 1.0


def test_semantic_classifier_top_k():
    results = classify("search for news", top_k=2)
    assert len(results) <= 2  # may return fewer if fewer modules exist


def test_modules_dict_not_empty():
    assert len(MODULES) > 0


# ──────────────────────────────────────────────────────────────────────────────
# 2. Orchestrator
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_module_provider_fallback():
    """
    run_module with no real module registry falls back to provider_mesh.
    We mock generate_with_fallback so no real HTTP call is made.
    """
    label = {"module": "coding", "score": 0.9}
    with patch("core.orchestrator_v3.generate_with_fallback", new=AsyncMock(return_value="mock answer")):
        result = await run_module(label, "write a loop", modules=None)
    assert "coding" in result
    assert "mock answer" in result


def test_merge_results_filters_exceptions():
    results = ["Result A", Exception("Failed module"), "Result B"]
    merged = merge_results(results)
    assert "Result A" in merged
    assert "Result B" in merged
    assert "Failed module" not in merged


def test_merge_results_all_failures():
    results = [Exception("A"), Exception("B")]
    merged = merge_results(results)
    assert "failed" in merged.lower()


def test_merge_results_single():
    results = ["Only result"]
    assert merge_results(results) == "Only result"


@pytest.mark.asyncio
async def test_orchestrate_returns_string():
    """Full orchestrate() call — mock provider so no real HTTP is made."""
    with patch("core.orchestrator_v3.generate_with_fallback", new=AsyncMock(return_value="ok")):
        result = await orchestrate("what is Python?", modules=None)
    assert isinstance(result, str)
    assert len(result) > 0


# ──────────────────────────────────────────────────────────────────────────────
# 3. Provider Mesh Fallback
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_fallback():
    """generate_with_fallback skips failing providers and returns first success."""

    class FailingProvider:
        name = "FailProvider"
        async def generate(self, prompt: str) -> str:
            raise RuntimeError("Primary provider failed")

    class SuccessProvider:
        name = "SuccessProvider"
        async def generate(self, prompt: str) -> str:
            return "Secondary provider succeeded"

    providers = [FailingProvider(), SuccessProvider()]
    result = await generate_with_fallback(providers, "test prompt")
    assert result == "Secondary provider succeeded"


@pytest.mark.asyncio
async def test_provider_all_fail():
    """generate_with_fallback raises RuntimeError when all providers fail."""

    class BadProvider:
        name = "BadProvider"
        async def generate(self, prompt: str) -> str:
            raise RuntimeError("Always fails")

    with pytest.raises(RuntimeError, match="All"):
        await generate_with_fallback([BadProvider(), BadProvider()], "prompt")


# ──────────────────────────────────────────────────────────────────────────────
# 4. Prompt Cache
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_cache_hit():
    _prompt_cache.clear()

    class CountingProvider:
        name = "CountingProvider"
        call_count = 0
        async def generate(self, prompt: str) -> str:
            self.call_count += 1
            return f"answer:{prompt[:20]}"

    provider = CountingProvider()
    r1 = await cached_generate(provider, "hello world")
    assert provider.call_count == 1
    r2 = await cached_generate(provider, "hello world")
    assert provider.call_count == 1  # cache hit — provider not called again
    assert r1 == r2


@pytest.mark.asyncio
async def test_prompt_cache_different_prompts():
    _prompt_cache.clear()

    class SimpleProvider:
        name = "SimpleProvider"
        call_count = 0
        async def generate(self, prompt: str) -> str:
            self.call_count += 1
            return f"resp_{self.call_count}"

    provider = SimpleProvider()
    r1 = await cached_generate(provider, "query one")
    r2 = await cached_generate(provider, "query two")
    assert provider.call_count == 2
    assert r1 != r2


def test_compress_context_short_text_unchanged():
    text = "short text"
    assert compress_context(text, max_words=100) == text


def test_compress_context_long_text_compressed():
    long_text = "word " * 600
    compressed = compress_context(long_text, max_words=100)
    assert "[COMPRESSED]" in compressed
    assert len(compressed.split()) < len(long_text.split())
