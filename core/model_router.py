"""
core/model_router.py - module maturity routing and streaming support.

The router is the boundary between orchestration and model execution.  It keeps
bootstrap/shadow/native behavior explicit, persists maturity state, and exposes
streaming helpers for the API layer.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import random
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

import httpx

from .config import config
from .learning.similarity import get_model
from .privacy import privacy
from .provider_mesh import OllamaProvider, generate_with_fallback, resolve_provider
from .runtime.state import state_store

log = logging.getLogger(__name__)

SHADOW_PROMOTE_THRESHOLD = 0.85
SHADOW_PROMOTE_MIN_QUERIES = 500
REGRESSION_THRESHOLD = 0.70
REGRESSION_WINDOW = 100


@dataclass
class RouteResult:
    answer: str
    source: str
    shadow_answer: Optional[str] = None
    similarity: Optional[float] = None
    latency_ms: int = 0


async def _maybe_await(value):
    """Await coroutine-like values while preserving sync test doubles."""
    if inspect.isawaitable(value):
        return await value
    return value


def _cosine_sim_text(a: str, b: str) -> float:
    """
    Lightweight lexical cosine similarity.

    This is intentionally dependency-free and kept as a public compatibility
    helper for tests and callers that need deterministic scoring without loading
    embedding models.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0

    return len(sa & sb) / ((len(sa) * len(sb)) ** 0.5)


class ModelRouter:
    def __init__(self):
        self._recent_scores: dict[str, list[float]] = {}

    async def route(self, module_name: str, subtask: str, context) -> RouteResult:
        state = config.get_module_state(module_name)
        stage = state.get("stage", "bootstrap")
        t0 = time.monotonic()

        if stage == "bootstrap":
            answer = await self._call_external(module_name, subtask, context)
            await _maybe_await(self._record_training_pair(module_name, subtask, answer))
            count = self._increment_query_count(module_name)
            self._maybe_promote(module_name, count=count)
            return RouteResult(
                answer=answer,
                source="external",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        if stage == "shadow":
            ext_task = asyncio.create_task(
                self._call_external(module_name, subtask, context),
                name=f"{module_name}:external",
            )
            own_task = asyncio.create_task(
                self._call_own_model(module_name, subtask, context),
                name=f"{module_name}:shadow",
            )
            try:
                ext_answer, own_answer = await asyncio.gather(ext_task, own_task)
            except BaseException:
                for task in (ext_task, own_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(ext_task, own_task, return_exceptions=True)
                raise

            similarity = await _semantic_sim_text(ext_answer, own_answer)
            self._record_recent_score(module_name, similarity)
            count = self._increment_query_count(module_name)
            await _maybe_await(self._update_maturity(module_name, similarity, count))
            await _maybe_await(self._record_training_pair(module_name, subtask, ext_answer))
            self._maybe_promote(module_name, score=similarity, count=count)
            return RouteResult(
                answer=ext_answer,
                source="shadow",
                shadow_answer=own_answer,
                similarity=round(similarity, 4),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        answer = await self._call_own_model(module_name, subtask, context)
        count = self._increment_query_count(module_name)
        score = await self._spot_check(module_name, subtask, answer)
        if score is not None:
            self._record_recent_score(module_name, score)
            await _maybe_await(self._update_maturity(module_name, score, count))
            self._maybe_rollback(module_name)
        return RouteResult(
            answer=answer,
            source="native",
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def stream_route(
        self, module_name: str, subtask: str, context
    ) -> AsyncGenerator[str, None]:
        """
        Streaming entry point used by the SSE endpoint and voice output.
        """
        state = config.get_module_state(module_name)
        stage = state.get("stage", "bootstrap")

        if stage == "native":
            gen = self._stream_own(module_name, subtask, context)
        else:
            gen = self._stream_external(module_name, subtask, context)

        full: list[str] = []
        async for token in gen:
            full.append(token)
            yield token

        full_answer = "".join(full)
        if stage in ("bootstrap", "shadow"):
            await _maybe_await(
                self._record_training_pair(module_name, subtask, full_answer)
            )
        count = self._increment_query_count(module_name)
        self._maybe_promote(module_name, count=count)

    async def _stream_external(
        self, module_name: str, subtask: str, context
    ) -> AsyncGenerator[str, None]:
        state = config.get_module_state(module_name)
        model = state.get("bootstrap_model", "mistral")
        host = config.get("global.ollama_host") or "http://localhost:11434"
        prompt = self._build_prompt(subtask, context)
        async for token in self._ollama_stream(host, model, prompt):
            yield token

    async def _stream_own(
        self, module_name: str, subtask: str, context
    ) -> AsyncGenerator[str, None]:
        state = config.get_module_state(module_name)
        model = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        host = config.get("global.ollama_host") or "http://localhost:11434"
        prompt = self._build_prompt(subtask, context)
        async for token in self._ollama_stream(host, model, prompt):
            yield token

    async def _ollama_stream(
        self, host: str, model: str, prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        Core streaming loop.  Transport and JSON errors are surfaced as a final
        error token rather than being swallowed silently by the caller.
        """
        import json as _json

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": True},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = _json.loads(line)
                        except _json.JSONDecodeError as exc:
                            log.warning("[model_router] invalid stream JSON: %s", exc)
                            continue
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done", False):
                            break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("[model_router] stream error (%s): %s", model, e)
            yield f"[Error: {e}]"

    @staticmethod
    async def _collect(gen: AsyncGenerator[str, None]) -> str:
        parts: list[str] = []
        async for token in gen:
            parts.append(token)
        return "".join(parts)

    def _build_prompt(self, subtask: str, context) -> str:
        ctx_str = context.format_for_prompt(5) if context else ""
        if ctx_str:
            return f"{ctx_str}\n\nUser: {subtask}\nAssistant:"
        return f"User: {subtask}\nAssistant:"

    async def _call_external(self, module_name: str, subtask: str, context) -> str:
        providers = resolve_provider(module_name)
        return await generate_with_fallback(providers, self._build_prompt(subtask, context))

    async def _call_own_model(self, module_name: str, subtask: str, context) -> str:
        state = config.get_module_state(module_name)
        model = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        provider = OllamaProvider(model=model)
        return await generate_with_fallback([provider], self._build_prompt(subtask, context))

    async def _spot_check(
        self, module_name: str, subtask: str, own_answer: str
    ) -> Optional[float]:
        if random.random() > 0.05:
            return None
        ext = await self._call_external(module_name, subtask, None)
        return await _semantic_sim_text(own_answer, ext)

    async def _record_training_pair(self, module_name: str, query: str, answer: str):
        if not privacy.can_save_training():
            return
        if not answer:
            return
        await state_store.record_training_pair(module_name, query, answer)

    def _increment_query_count(self, module_name: str) -> int:
        state = config.get_module_state(module_name)
        count = int(state.get("query_count", 0) or 0) + 1
        config.set_module_state(module_name, "query_count", count)
        return count

    async def _update_maturity(
        self, module_name: str, score: float, query_count: Optional[int] = None
    ) -> float:
        """Persist an EMA maturity score to config and StateStore."""
        state = config.get_module_state(module_name)
        curr_score = float(state.get("maturity_score", 0.0) or 0.0)
        count = query_count
        if count is None:
            count = int(state.get("query_count", 0) or 0)

        bounded_score = max(0.0, min(1.0, float(score)))
        new_score = (curr_score * 0.9) + (bounded_score * 0.1)
        new_score = round(new_score, 4)

        config.set_module_state(module_name, "maturity_score", new_score)
        await state_store.update_maturity(module_name, new_score, count)
        return new_score

    def _record_recent_score(self, module_name: str, score: float) -> None:
        scores = self._recent_scores.setdefault(module_name, [])
        scores.append(max(0.0, min(1.0, float(score))))
        if len(scores) > REGRESSION_WINDOW:
            del scores[:-REGRESSION_WINDOW]

    def _maybe_promote(
        self,
        module_name: str,
        score: Optional[float] = None,
        count: Optional[int] = None,
    ) -> None:
        state = config.get_module_state(module_name)
        stage = state.get("stage", "bootstrap")
        query_count = int(count if count is not None else state.get("query_count", 0) or 0)
        maturity = float(
            score if score is not None else state.get("maturity_score", 0.0) or 0.0
        )

        if stage == "bootstrap" and query_count >= SHADOW_PROMOTE_MIN_QUERIES:
            config.set_module_state(module_name, "stage", "shadow")
            self._emit_lifecycle("module.promoted", module_name, "shadow", maturity)
        elif (
            stage == "shadow"
            and query_count >= SHADOW_PROMOTE_MIN_QUERIES
            and maturity >= SHADOW_PROMOTE_THRESHOLD
        ):
            config.set_module_state(module_name, "stage", "native")
            self._emit_lifecycle("module.promoted", module_name, "native", maturity)
            log.info("[ModelRouter] %s promoted to native", module_name)

    def _maybe_rollback(self, module_name: str) -> None:
        state = config.get_module_state(module_name)
        if state.get("stage") != "native":
            return

        scores = self._recent_scores.get(module_name, [])
        if len(scores) >= REGRESSION_WINDOW:
            regression_score = sum(scores[-REGRESSION_WINDOW:]) / REGRESSION_WINDOW
        else:
            regression_score = float(state.get("maturity_score", 1.0) or 1.0)

        if regression_score < REGRESSION_THRESHOLD:
            config.set_module_state(module_name, "stage", "shadow")
            self._emit_lifecycle(
                "module.rollback", module_name, "shadow", regression_score
            )
            log.warning(
                "[ModelRouter] %s rolled back to shadow (score %.3f)",
                module_name,
                regression_score,
            )

    def _emit_lifecycle(
        self, event: str, module_name: str, stage: str, maturity_score: float
    ) -> None:
        try:
            from .event_bus import bus

            bus.emit_sync(
                event,
                {
                    "module": module_name,
                    "stage": stage,
                    "maturity_score": round(float(maturity_score), 4),
                },
            )
        except Exception as exc:
            log.debug("[ModelRouter] lifecycle emit failed: %s", exc)

    def get_maturity_score(self, module_name: str) -> float:
        state = config.get_module_state(module_name)
        return float(state.get("maturity_score", 0.0) or 0.0)


async def _semantic_sim_text(a: str, b: str) -> float:
    """Use embeddings when available, otherwise fall back to lexical cosine."""
    if not a or not b:
        return 0.0

    model = get_model()
    if not model:
        return _cosine_sim_text(a, b)

    try:
        from scipy.spatial.distance import cosine

        embs = model.encode([a, b])
        dist = cosine(embs[0], embs[1])
        return max(0.0, min(1.0, 1.0 - dist))
    except Exception as exc:
        log.debug("[model_router] semantic similarity fallback: %s", exc)
        return _cosine_sim_text(a, b)


model_router = ModelRouter()
