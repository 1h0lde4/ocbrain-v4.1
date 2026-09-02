"""
tests/test_prompt_cache_security.py — CTX-CACHE-001 security regression.

Permanent regression capturing a verified cache-key collision in
core/prompt/cache.py::cached_generate, surfaced during the cache
isolation audit. See:
    docs/research/context-engineering/context-authority-threat-model.md
    (finding CTX-CACHE-001)

STATUS: test_prompts_differing_only_in_compressed_middle_do_not_collide
is EXPECTED TO FAIL (red). Do not weaken this assertion, do not mark it
xfail (this repository has no such convention), do not delete it. When
the cache key is computed over the full prompt (or otherwise made
dependency-aware) rather than a lossy pre-hash compression, this test
should turn green without modification to the assertion itself.

Root cause: cached_generate() hashes prompt for its cache key only
after running it through compress_context(prompt, max_words=500), which
-- for anything over 500 words -- keeps only the first and last 250
words and discards the entire middle. Two prompts that are genuinely
different (confirmed non-identical strings) but share the same first
250 and last 250 words therefore hash identically and collide,
regardless of what differs between them.

Confirmed live and unconditional in production: generate_with_fallback()
(core/provider_mesh.py) -- the entry point core/cognitive/intent.py's
generate_hypotheses() and other K4.2 LLM calls use -- routes every call
through cached_generate() via safe_llm_call(), per that function's own
docstring ("ALL calls go through the prompt cache before hitting the
backend"). Unlike CTX-AUTH-001, this requires no adversarial input --
any two sufficiently long, sufficiently similarly-shaped organic
requests can trigger it.

TestBenignShortPromptBaseline is a differential control: prompts under
the 500-word threshold must continue to behave correctly (no
compression, no collision). If a future fix breaks this too, the fix
has almost certainly over-corrected (e.g. hashing something even more
lossy, or breaking normal short-prompt caching).

All content below is a clearly-labeled synthetic sentinel.
"""
import pytest

import core.prompt.cache as cache_module


class _FakeProvider:
    def __init__(self, name, response):
        self.name = name
        self._response = response

    async def generate(self, prompt):
        return self._response


@pytest.fixture(autouse=True)
def _clean_prompt_cache():
    """cached_generate()'s _prompt_cache is module-level global state --
    reset it before and after each test so tests here don't contaminate
    each other or any other test module that happens to import
    core.prompt.cache."""
    cache_module._prompt_cache.clear()
    yield
    cache_module._prompt_cache.clear()


class TestCtxCache001Collision:
    @pytest.mark.asyncio
    async def test_prompts_differing_only_in_compressed_middle_do_not_collide(self):
        head = " ".join(f"word{i}" for i in range(250))
        tail = " ".join(f"tail{i}" for i in range(250))
        prompt_a = f"{head} CONTEXT_SENTINEL_SCOPE_A_TASK_DETAILS {tail}"
        prompt_b = f"{head} CONTEXT_SENTINEL_SCOPE_B_TASK_DETAILS {tail}"

        assert prompt_a != prompt_b, "test setup is broken -- prompts must differ"
        assert len(prompt_a.split()) > 500 and len(prompt_b.split()) > 500, (
            "test setup is broken -- both prompts must exceed the "
            "500-word compression threshold"
        )

        result_a = await cache_module.cached_generate(
            _FakeProvider("provider_a", "SCOPE_A_ONLY_RESPONSE"), prompt_a
        )
        result_b = await cache_module.cached_generate(
            _FakeProvider("provider_b", "SCOPE_B_ONLY_RESPONSE"), prompt_b
        )

        # DESIRED FUTURE INVARIANT (CTX-CACHE-001) -- currently expected to fail:
        assert result_b == "SCOPE_B_ONLY_RESPONSE", (
            f"prompt_b received prompt_a's cached response ({result_b!r}) "
            "despite being a genuinely different prompt -- cache key "
            "collision via lossy pre-hash compression (CTX-CACHE-001)"
        )


class TestBenignShortPromptBaseline:
    """Differential control: below the 500-word compression threshold,
    caching must continue to behave correctly. Must keep passing."""

    @pytest.mark.asyncio
    async def test_short_differing_prompts_do_not_collide(self):
        prompt_a = "short prompt CONTEXT_SENTINEL_SHORT_A task details here"
        prompt_b = "short prompt CONTEXT_SENTINEL_SHORT_B task details here"
        assert len(prompt_a.split()) < 500 and len(prompt_b.split()) < 500

        result_a = await cache_module.cached_generate(
            _FakeProvider("provider_a", "SHORT_A_RESPONSE"), prompt_a
        )
        result_b = await cache_module.cached_generate(
            _FakeProvider("provider_b", "SHORT_B_RESPONSE"), prompt_b
        )

        assert result_a == "SHORT_A_RESPONSE"
        assert result_b == "SHORT_B_RESPONSE"

    @pytest.mark.asyncio
    async def test_identical_short_prompt_correctly_reuses_cache(self):
        """Confirms this is genuinely a cache (not accidentally disabled
        entirely) -- an identical prompt to an already-cached one should
        return the cached response without a second provider call."""
        prompt = "identical short prompt CONTEXT_SENTINEL_REUSE task details"
        provider = _FakeProvider("provider", "FIRST_RESPONSE")

        result_1 = await cache_module.cached_generate(provider, prompt)
        # Second provider would answer differently if actually invoked --
        # a correct cache hit must not reach it.
        second_provider = _FakeProvider("provider2", "SHOULD_NOT_BE_SEEN")
        result_2 = await cache_module.cached_generate(second_provider, prompt)

        assert result_1 == "FIRST_RESPONSE"
        assert result_2 == "FIRST_RESPONSE"
