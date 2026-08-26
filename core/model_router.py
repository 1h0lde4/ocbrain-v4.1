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
import re
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Optional, Tuple

import httpx

from .config import config
from .learning.similarity import get_model
from .privacy import privacy
from .provider_mesh import OllamaProvider, generate_with_fallback, resolve_provider
from .runtime.cancellation import CancellationToken
from .runtime.execution_budget import ExecutionPolicy, record_observed_throughput
from .runtime.execution_outcome import ExecutionOutcome, FailureType
from .runtime.execution_watchdog import CancelReason, ExecutionWatchdog
from .runtime.progress_monitor import ProgressMonitor
from .runtime.state import state_store

log = logging.getLogger(__name__)

SHADOW_PROMOTE_THRESHOLD = 0.85
SHADOW_PROMOTE_MIN_QUERIES = 500
REGRESSION_THRESHOLD = 0.70
REGRESSION_WINDOW = 100

# v1 long-form heuristic (K4.4): looks for an explicit word-count request
# ("write a 1000 word story") in the subtask text. Deliberately simple and
# deliberately conservative -- see _estimate_long_form docstring for why
# this is disclosed as a v1 placeholder, not a complexity estimator.
_WORD_COUNT_PATTERN = re.compile(r"(\d{2,5})\s*[-]?\s*words?\b", re.IGNORECASE)
_LONG_FORM_TOKEN_THRESHOLD = 400


@dataclass
class RouteResult:
    answer: str
    source: str
    shadow_answer: Optional[str] = None
    similarity: Optional[float] = None
    latency_ms: int = 0
    execution_detail: Optional[ExecutionOutcome] = None


async def _maybe_await(value):
    """Await coroutine-like values while preserving sync test doubles."""
    if inspect.isawaitable(value):
        return await value
    return value


def _estimate_long_form(subtask: str) -> Tuple[bool, Optional[int]]:
    """v1 heuristic only.

    Looks for an explicit word-count request in the subtask text (e.g.
    "1000 words"). This deliberately does NOT attempt to estimate
    complexity from context size, reasoning depth, or tool usage -- those
    are real signals (see the architecture brief's §21 discussion) left as
    a documented extension point, not implemented here.

    A request with no explicit count defaults to long_form=False -- the
    conservative, regression-safe choice. This heuristic only opts a
    request INTO the new monitored-streaming path on a clear signal; it
    never removes an ordinary short request from the existing, unchanged
    fast path. See "Remaining debt" in the implementation report for what
    a more general complexity estimator would need.
    """
    match = _WORD_COUNT_PATTERN.search(subtask or "")
    if not match:
        return False, None
    words = int(match.group(1))
    estimated_tokens = int(words * 1.35)  # rough words -> tokens ratio
    return estimated_tokens >= _LONG_FORM_TOKEN_THRESHOLD, estimated_tokens


def _resolve_cancellation_token(context) -> CancellationToken:
    """ExecutionContext carries a cancellation_token; the legacy
    WorkerContext does not (see core/workers/base.py). Fall back to a
    fresh, local token so the watchdog still functions for callers on the
    legacy context -- it just won't be externally cancellable through that
    caller's own token in that case, which is a strict improvement over
    today (no watchdog at all on this path) rather than a regression."""
    token = getattr(context, "cancellation_token", None)
    return token if isinstance(token, CancellationToken) else CancellationToken()


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

        long_form, estimated_tokens = _estimate_long_form(subtask)
        if long_form and stage in ("bootstrap", "native"):
            # Monitored-streaming path (K4.4): reuses the existing
            # streaming infrastructure (_stream_external / _stream_own /
            # _ollama_stream, all unmodified) under ExecutionBudget +
            # ProgressMonitor + ExecutionWatchdog supervision, instead of
            # generate_with_fallback's flat-60s-timeout path. This is the
            # actual fix for the "1000-word story -> No response" bug.
            #
            # Restricted to bootstrap/native: running both an external AND
            # an own-model monitored stream concurrently in "shadow" stage,
            # each under its own watchdog, is real additional complexity
            # deferred to a follow-up (see implementation report) --
            # shadow-stage long-form traffic safely falls through to the
            # existing behavior below instead of hitting this branch.
            if stage == "native":
                stream_fn = self._stream_own
                model_label = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
                source = "own_model"
            else:
                stream_fn = self._stream_external
                model_label = state.get("bootstrap_model", "mistral")
                source = "external"

            answer, outcome = await self._call_monitored_streaming(
                stream_fn, module_name, subtask, context,
                model_label=model_label, estimated_output_tokens=estimated_tokens,
            )
            await _maybe_await(self._record_training_pair(module_name, subtask, answer))
            count = self._increment_query_count(module_name)
            self._maybe_promote(module_name, count=count)
            return RouteResult(
                answer=answer,
                source=source,
                latency_ms=int((time.monotonic() - t0) * 1000),
                execution_detail=outcome,
            )

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

    async def _call_monitored_streaming(
        self,
        stream_fn,
        module_name: str,
        subtask: str,
        context,
        *,
        model_label: str,
        estimated_output_tokens: Optional[int],
    ) -> Tuple[str, ExecutionOutcome]:
        """Drains an existing streaming generator (_stream_external /
        _stream_own, themselves unmodified) under ExecutionBudget +
        ProgressMonitor + ExecutionWatchdog supervision.

        On healthy completion, returns the full generated text -- same
        shape as generate_with_fallback's return, from the caller's point
        of view. On a watchdog-triggered cancellation (stall or hard
        deadline), returns whatever partial output had been generated
        rather than discarding it, paired with a structured
        ExecutionOutcome the caller (route()) attaches to RouteResult, so a
        partial answer is always distinguishable from a complete one --
        never silently passed off as a full response.
        """
        budget = ExecutionPolicy.for_generation(
            provider=module_name,
            model=model_label,
            estimated_output_tokens=estimated_output_tokens,
            long_form=True,
        )
        monitor = ProgressMonitor()
        monitor.start()
        token = _resolve_cancellation_token(context)
        watchdog = ExecutionWatchdog(budget, monitor, token)

        chunks: list[str] = []
        provider_failure = False

        async def _consume() -> None:
            nonlocal provider_failure
            try:
                async for piece in stream_fn(module_name, subtask, context):
                    chunks.append(piece)
                    if piece.strip():
                        monitor.report_progress(units=len(piece))
                    else:
                        monitor.report_activity()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("[model_router] monitored streaming failed (%s): %s", model_label, exc)
                provider_failure = True

        watchdog_task = asyncio.create_task(watchdog.run())
        consumer_task = asyncio.create_task(_consume())

        # A cooperative "check token.is_cancelled between chunks" is not
        # enough: a genuinely stalled provider may never yield another
        # chunk at all, leaving the consumer permanently blocked awaiting
        # one. Race the two tasks instead, and forcibly cancel the
        # consumer if the watchdog decides to act first -- this is what
        # actually interrupts a hung stream (propagates asyncio.CancelledError
        # into _ollama_stream's httpx read, which re-raises it rather than
        # swallowing it).
        done, _pending = await asyncio.wait(
            {watchdog_task, consumer_task}, return_when=asyncio.FIRST_COMPLETED
        )

        if consumer_task in done:
            watchdog.stop()
            await watchdog_task
        else:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        full_answer = "".join(chunks)
        has_output = bool(full_answer.strip())

        if provider_failure:
            failure_type = FailureType.PROVIDER_FAILURE
        elif token.is_cancelled:
            failure_type = (
                FailureType.STALLED if token.reason == CancelReason.STALL.value
                else FailureType.HARD_DEADLINE
            )
        elif not has_output:
            failure_type = FailureType.EMPTY_RESPONSE
        else:
            failure_type = FailureType.SUCCESS

        snap = monitor.snapshot()
        if failure_type == FailureType.SUCCESS:
            monitor.complete()
            if snap.throughput_per_sec:
                record_observed_throughput(module_name, model_label, snap.throughput_per_sec)
        elif has_output:
            monitor.cancel()
        else:
            monitor.fail()

        outcome = ExecutionOutcome(
            failure_type=failure_type,
            provider=module_name,
            model=model_label,
            last_progress_at=snap.last_progress_at,
            partial_output=full_answer if (failure_type != FailureType.SUCCESS and has_output) else None,
            watchdog_verdict=watchdog.last_verdict.value,
            recovery_action="bounded_extension" if watchdog.last_verdict.value == "extended" else "",
            retryable=failure_type in (FailureType.STALLED, FailureType.PROVIDER_FAILURE, FailureType.EMPTY_RESPONSE),
        )
        return full_answer, outcome

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
