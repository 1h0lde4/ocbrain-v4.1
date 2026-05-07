"""
core/model_router.py — V2.1: full token streaming via Ollama.
All LLM calls now use stream=True and yield tokens via an async generator.
Callers that want a full string call _collect(); streaming callers iterate directly.
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx

from .config import config
from .privacy import privacy
from .provider_mesh import resolve_provider, generate_with_fallback
from .learning.similarity import get_model
from .runtime.state import state_store

log = logging.getLogger(__name__)

SHADOW_PROMOTE_THRESHOLD   = 0.85
SHADOW_PROMOTE_MIN_QUERIES = 500
REGRESSION_THRESHOLD       = 0.70
REGRESSION_WINDOW          = 100


@dataclass
class RouteResult:
    answer: str
    source: str
    shadow_answer: Optional[str] = None
    similarity: Optional[float]  = None
    latency_ms: int = 0


class ModelRouter:
    def __init__(self):
        self._recent_scores: dict[str, list[float]] = {}

    async def route(self, module_name: str, subtask: str, context) -> RouteResult:
        state = config.get_module_state(module_name)
        stage = state.get("stage", "bootstrap")
        t0    = time.monotonic()

        if stage == "bootstrap":
            providers = resolve_provider(module_name)
            answer = await generate_with_fallback(providers, subtask)
            self._record_training_pair(module_name, subtask, answer)
            self._increment_query_count(module_name)
            return RouteResult(answer=answer, source="external",
                               latency_ms=int((time.monotonic()-t0)*1000))

        elif stage == "shadow":
            providers = resolve_provider(module_name)
            ext_task  = asyncio.create_task(generate_with_fallback(providers, subtask))
            own_task  = asyncio.create_task(self._call_own_model(module_name, subtask, context))
            ext_answer, own_answer = await asyncio.gather(ext_task, own_task)
            
            similarity = await _semantic_sim_text(ext_answer, own_answer)
            self._update_maturity(module_name, similarity)
            self._record_training_pair(module_name, subtask, ext_answer)
            self._increment_query_count(module_name)
            self._maybe_promote(module_name)
            return RouteResult(answer=ext_answer, source="shadow",
                               shadow_answer=own_answer,
                               similarity=round(similarity, 4),
                               latency_ms=int((time.monotonic()-t0)*1000))

        else:  # native
            answer = await self._collect(self._stream_own(module_name, subtask, context))
            score  = await self._spot_check(module_name, subtask, answer)
            if score is not None:
                self._update_maturity(module_name, score)
                self._maybe_rollback(module_name)
            self._increment_query_count(module_name)
            return RouteResult(answer=answer, source="native",
                               latency_ms=int((time.monotonic()-t0)*1000))

    # ── Streaming generators ──────────────────────────────────

    async def stream_route(
        self, module_name: str, subtask: str, context
    ) -> AsyncGenerator[str, None]:
        """
        Streaming entry point — yields token strings as they arrive from Ollama.
        Used by the SSE endpoint and voice output.
        """
        state = config.get_module_state(module_name)
        stage = state.get("stage", "bootstrap")

        if stage == "native":
            gen = self._stream_own(module_name, subtask, context)
        else:
            gen = self._stream_external(module_name, subtask, context)

        full = []
        async for token in gen:
            full.append(token)
            yield token

        full_answer = "".join(full)
        if stage in ("bootstrap", "shadow"):
            self._record_training_pair(module_name, subtask, full_answer)
        self._increment_query_count(module_name)

    async def _stream_external(
        self, module_name: str, subtask: str, context
    ) -> AsyncGenerator[str, None]:
        state  = config.get_module_state(module_name)
        model  = state.get("bootstrap_model", "mistral")
        host   = config.get("global.ollama_host") or "http://localhost:11434"
        ctx_str = context.format_for_prompt(5) if context else ""
        prompt  = f"{ctx_str}\n\nUser: {subtask}\nAssistant:"
        async for token in self._ollama_stream(host, model, prompt):
            yield token

    async def _stream_own(
        self, module_name: str, subtask: str, context
    ) -> AsyncGenerator[str, None]:
        state  = config.get_module_state(module_name)
        model  = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        host   = config.get("global.ollama_host") or "http://localhost:11434"
        ctx_str = context.format_for_prompt(5) if context else ""
        prompt  = f"{ctx_str}\n\nUser: {subtask}\nAssistant:"
        async for token in self._ollama_stream(host, model, prompt):
            yield token

    async def _ollama_stream(
        self, host: str, model: str, prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        Core streaming loop — calls Ollama with stream=true,
        yields each token string as it arrives.
        Falls back to empty string on error (never raises).
        """
        import json as _json
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": True},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data  = _json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield token
                            if data.get("done", False):
                                break
                        except _json.JSONDecodeError:
                            continue
        except Exception as e:
            log.error(f"[model_router] stream error ({model}): {e}")
            yield f"[Error: {e}]"

    @staticmethod
    async def _collect(gen: AsyncGenerator[str, None]) -> str:
        """Drain an async generator into a single string."""
        parts = []
        async for token in gen:
            parts.append(token)
        return "".join(parts)

    # ── Non-streaming helpers (keep for shadow scoring) ──────

    async def _call_external(self, module_name: str, subtask: str, context) -> str:
        providers = resolve_provider(module_name)
        return await generate_with_fallback(providers, subtask)

    async def _call_own_model(self, module_name: str, subtask: str, context) -> str:
        state = config.get_module_state(module_name)
        model = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        p = OllamaProvider(model=model)
        return await generate_with_fallback([p], subtask)

    async def _spot_check(
        self, module_name: str, subtask: str, own_answer: str
    ) -> Optional[float]:
        import random
        if random.random() > 0.05:
            return None
        ext = await self._call_external(module_name, subtask, None)
        return await _semantic_sim_text(own_answer, ext)

    # ── State management ──────────────────────────────────────

    async def _record_training_pair(self, module_name: str, query: str, answer: str):
        if not privacy.can_save_training():
            return
        await state_store.record_training_pair(module_name, query, answer)

    async def _update_maturity(self, module_name: str, score: float):
        """Update maturity in StateStore using AIMD-like sliding window."""
        state = state_store.get_maturity(module_name)
        curr_score = state.get("score", 0.0)
        query_count = state.get("query_count", 0) + 1

        # Use the provided score (similarity) to adjust the stored maturity
        # This simplifies the previous logic by delegating windowing to StateStore if needed
        # but for now we'll do a simple moving average update
        new_score = (curr_score * 0.9) + (score * 0.1)
        
        await state_store.update_maturity(module_name, new_score, query_count)
        self._maybe_promote(module_name, new_score, query_count)

    def _maybe_promote(self, module_name: str, score: float, count: int):
        state = config.get_module_state(module_name)
        stage = state.get("stage", "bootstrap")
        
        if stage == "bootstrap" and count >= 50:
            config.set_module_state(module_name, "stage", "shadow")
        elif stage == "shadow" and count >= 200 and score >= 0.90:
            config.set_module_state(module_name, "stage", "native")
            log.info(f"[ModelRouter] {module_name} PROMOTED to native")

    def get_maturity_score(self, module_name: str) -> float:
        return state_store.get_maturity(module_name).get("score", 0.0)

    def get_maturity_score(self, module_name: str) -> float:
        return float(config.get_module_state(module_name).get("maturity_score", 0.0))


async def _semantic_sim_text(a: str, b: str) -> float:
    """Uses embedding-based cosine similarity for robust model comparison."""
    if not a or not b:
        return 0.0
    
    model = get_model()
    if not model:
        # Fallback to Jaccard-like similarity if embedding model is down
        sa, sb = set(a.lower().split()), set(b.lower().split())
        if not sa or not sb: return 0.0
        return len(sa & sb) / ((len(sa) * len(sb)) ** 0.5)

    try:
        from scipy.spatial.distance import cosine
        embs = model.encode([a, b])
        dist = cosine(embs[0], embs[1])
        return max(0.0, min(1.0, 1.0 - dist))
    except Exception:
        return 0.0


model_router = ModelRouter()
