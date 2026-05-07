"""
examples/demo_phase2.py

End-to-end demonstration of Phase 2 components:
  - Semantic Classifier v3
  - Parallel Orchestrator v3
  - Provider Mesh with fallback (mocked so demo runs offline)
  - Prompt Cache

Run from project root:
    python examples/demo_phase2.py
"""
import asyncio
import logging
import json
import sys
import os
from unittest.mock import AsyncMock, patch

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.observability.tracer import set_trace_id, span
from core.classifier_v3 import classify
from core.orchestrator_v3 import orchestrate
from core.provider_mesh import generate_with_fallback
from core.prompt.cache import compress_context, cached_generate, _prompt_cache

# Configure logging so trace JSON is visible in output
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 1: Semantic Classifier
# ─────────────────────────────────────────────────────────────────────────────
def demo_classifier():
    print("\n" + "=" * 60)
    print("DEMO 1: Semantic Classifier v3")
    print("=" * 60)

    queries = [
        "Can you write a Python function to sort a list?",
        "What happened in the news today?",
        "What did I say yesterday about the project?",
        "Solve the integral of x squared from 0 to 3.",
    ]

    for query in queries:
        set_trace_id(None)  # Reset trace per request — generates fresh trace_id on next span
        results = classify(query, top_k=2)
        print(f"\nQuery : {query}")
        print("Result:", json.dumps(results, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 2: Provider Mesh – Fallback in action (offline-safe mock)
# ─────────────────────────────────────────────────────────────────────────────
async def demo_provider_fallback():
    print("\n" + "=" * 60)
    print("DEMO 2: Provider Mesh — Fallback Demonstration (mocked)")
    print("=" * 60)

    class AlwaysFailProvider:
        name = "Ollama(FAILING)"
        async def generate(self, prompt: str) -> str:
            raise ConnectionError("Ollama is not running (simulated)")

    class BackupProvider:
        name = "BackupProvider"
        async def generate(self, prompt: str) -> str:
            return f"[BACKUP] Handled: {prompt[:60]}..."

    providers = [AlwaysFailProvider(), BackupProvider()]
    prompt = "Explain what a neural network is."

    print(f"\nPrompt  : {prompt}")
    print("Providers: AlwaysFailProvider -> BackupProvider")
    result = await generate_with_fallback(providers, prompt)
    print(f"Result  : {result}")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 3: Prompt Cache – Hit vs Miss
# ─────────────────────────────────────────────────────────────────────────────
async def demo_prompt_cache():
    print("\n" + "=" * 60)
    print("DEMO 3: Prompt Cache — Cache Hit vs Miss")
    print("=" * 60)

    _prompt_cache.clear()
    call_log = []

    class TrackedProvider:
        name = "TrackedProvider"
        async def generate(self, prompt: str) -> str:
            call_log.append(1)
            return f"Answer for: {prompt[:40]}"

    provider = TrackedProvider()
    prompt = "What is machine learning?"

    print(f"\nPrompt: '{prompt}'")
    res1 = await cached_generate(provider, prompt)
    print(f"Call 1 (miss) : {res1}  [provider calls: {len(call_log)}]")

    res2 = await cached_generate(provider, prompt)
    print(f"Call 2 (hit)  : {res2}  [provider calls: {len(call_log)}]")
    assert len(call_log) == 1, "Cache should have prevented second provider call"
    print("✓ Cache hit confirmed — provider called only once")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 4: Full Parallel Orchestration (mocked HTTP)
# ─────────────────────────────────────────────────────────────────────────────
async def demo_full_orchestration():
    print("\n" + "=" * 60)
    print("DEMO 4: Full Parallel Orchestration (mocked HTTP)")
    print("=" * 60)

    query = "Write a script to fetch and analyze news headlines"
    print(f"\nQuery: {query}")

    mock_response = "Mocked LLM response for demo (no Ollama required)"
    with patch(
        "core.orchestrator_v3.generate_with_fallback",
        new=AsyncMock(return_value=mock_response),
    ):
        with span("demo_root", mode="parallel_orchestration"):
            result = await orchestrate(query, modules=None, max_iterations=5)

    print("\n--- Final Orchestrated Output ---")
    print(result)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO 5: Context Compression
# ─────────────────────────────────────────────────────────────────────────────
def demo_compress():
    print("\n" + "=" * 60)
    print("DEMO 5: Context Compression")
    print("=" * 60)

    long_text = " ".join([f"sentence_{i}" for i in range(300)])
    compressed = compress_context(long_text, max_words=80)
    print(f"\nOriginal word count  : {len(long_text.split())}")
    print(f"Compressed word count: {len(compressed.split())}")
    print(f"Preview: {compressed[:120]}...")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    demo_classifier()
    await demo_provider_fallback()
    await demo_prompt_cache()
    await demo_full_orchestration()
    demo_compress()
    print("\n" + "=" * 60)
    print("Phase 2 Demo Complete.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
