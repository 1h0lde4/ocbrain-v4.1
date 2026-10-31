"""B2c -- a cancelled caller task must stop the generation and must not look like a failure.

Scope (what is reachable in production at this head): TASK cancellation, i.e.
asyncio.CancelledError arriving while a task awaits ModelRouter.route(). No
production caller currently hands the router or AdapterRuntime a cancellation
TOKEN (PlannerWorker and capability_executor pass context_memory / ""; see
PR #104), so token-driven cancellation is out of this file's scope.

Covered here:

  * the router stops its consumer/watchdog tasks and the provider stream when
    its caller is cancelled (no task outlives the request, the stream's
    `finally` runs);
  * a caller cancelled while the router is cancelling its own consumer is not
    swallowed;
  * AdapterRuntime lets CancelledError propagate: no fallback is started and no
    adapter is penalised because of the cancellation, while genuine failures
    and stalls keep their existing behaviour (pinned);
  * cancelling one request does not disturb a concurrent request.

What this file can and cannot show: logical cancellation and in-process stop are
proven with deterministic fakes; that a real model server stopped generating is
NOT proven here. Closing a client stream does not by itself prove it.
"""
import asyncio
import time

import pytest

import core.model_router as mr
from core.capabilities import (
    AdapterRuntime, CapabilityContract, CapabilityRegistry, CapabilityType,
    ResourceManager,
)
from core.capabilities.adapters.model_router_adapter import ModelRouterAdapter
from core.capabilities.adapters.ollama_adapter import OllamaAdapter
from core.model_router import ModelRouter
from core.runtime.execution_budget import ExecutionBudget

# An explicit word count sends route() down the monitored-streaming branch.
LONG = "write a short story of 1000 words, fantasy type"


class _Ctx:
    """Shaped like the context production hands the router (ContextMemory):
    it has NO `cancellation_token`, so the router uses its own fresh token."""
    def __init__(self):
        self.metadata = {}

    def format_for_prompt(self, n, scope=None):
        return ""


def _budget():
    # Fresh per request (production does the same; ExecutionBudget is mutable).
    # startup 0.3 s: the watchdog's first wake-up; progress 0.05 s: stall window.
    return ExecutionBudget(startup_deadline_s=0.3, progress_deadline_s=0.05,
                           hard_ceiling_s=30.0, absolute_ceiling_s=30.0, max_extension_s=0.0)


@pytest.fixture
def router(monkeypatch):
    """A real ModelRouter (bootstrap stage). Its persistence side effects are
    replaced by spies, so tests can assert what a cancelled generation records."""
    monkeypatch.setattr(
        mr.config, "get_module_state",
        lambda name: {"stage": "bootstrap", "bootstrap_model": "mistral"})
    monkeypatch.setattr(mr.ExecutionPolicy, "for_generation",
                        classmethod(lambda cls, **kw: _budget()))
    r = ModelRouter()
    spies = {"pairs": [], "counts": [], "promoted": []}

    async def _pair(module, query, answer):
        spies["pairs"].append(answer)

    def _count(module):
        spies["counts"].append(module)
        return len(spies["counts"])

    monkeypatch.setattr(r, "_record_training_pair", _pair)
    monkeypatch.setattr(r, "_increment_query_count", _count)
    monkeypatch.setattr(r, "_maybe_promote", lambda *a, **k: spies["promoted"].append(1))
    return r, spies


# --- provider streams ------------------------------------------------------

def _endless(ev):
    async def stream(module_name, subtask, context, scope=""):
        ev["started"] = True
        try:
            while True:
                await asyncio.sleep(0.02)
                yield "tok "
        finally:
            ev["closed"] = True
    return stream


def _slow_cleanup(ev):
    """Hangs after one token; when cancelled it takes a long time to clean up."""
    async def stream(module_name, subtask, context, scope=""):
        yield "Beginning the tale"
        try:
            await asyncio.sleep(9999)
        except asyncio.CancelledError:
            ev["cleanup_started"] = True
            raise
        finally:
            await asyncio.sleep(0.8)
    return stream


def _provider_error():
    async def stream(module_name, subtask, context, scope=""):
        yield mr.ProviderStreamError("[Error: model request failed (ref x)]", "x")
    return stream


async def _hangs_after_one_token(module_name, subtask, context, scope=""):
    yield "Beginning the tale"
    await asyncio.sleep(9999)


async def _complete(module_name, subtask, context, scope=""):
    yield "A complete story."


# --- helpers ---------------------------------------------------------------

async def _leftover_tasks(before, timeout=1.0):
    """Tasks created since `before` that are still running (polled briefly)."""
    deadline = time.time() + timeout
    while True:
        left = [t for t in asyncio.all_tasks()
                if t not in before and t is not asyncio.current_task() and not t.done()]
        if not left or time.time() > deadline:
            return left
        await asyncio.sleep(0.02)


async def _wait_for(flag_dict, key, timeout=6.0):
    deadline = time.time() + timeout
    while not flag_dict.get(key):
        if time.time() > deadline:
            raise AssertionError(f"timed out waiting for {key!r}")
        await asyncio.sleep(0.02)


class _SecondFallback(OllamaAdapter):
    adapter_name = "SecondFallback"


def _ok(text, calls=None):
    async def generate(prompt, *a, **k):
        if calls is not None:
            calls.append(prompt)
        return text
    return generate


def _runtime(router_obj, ollama_generate, second_generate=None):
    registry = CapabilityRegistry()
    registry.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION, description="d"))
    mra, oa, sf = ModelRouterAdapter(router_obj), OllamaAdapter(), _SecondFallback()
    oa._provider.generate = ollama_generate
    sf._provider.generate = second_generate or _ok("SECOND")
    for adapter in (mra, oa, sf):
        registry.register_adapter(CapabilityType.LLM_COMPLETION, adapter)
    return AdapterRuntime(registry=registry, resource_manager=ResourceManager()), mra, oa, sf


def _invoke(runtime, ctx, subtask=LONG):
    return runtime.invoke(CapabilityType.LLM_COMPLETION, module_name="coding",
                          subtask=subtask, context=ctx, scope="")


# ==========================================================================
# Router: the caller task is cancelled
# ==========================================================================

@pytest.mark.asyncio
async def test_caller_cancel_mid_generation_stops_the_stream_and_leaks_no_tasks(router):
    r, spies = router
    ev = {}
    r._stream_external = _endless(ev)
    before = set(asyncio.all_tasks())
    task = asyncio.create_task(r.route("coding", LONG, _Ctx()))
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    left = await _leftover_tasks(before | {task})
    assert ev.get("closed") is True          # the stream generator's finally ran
    assert left == []                        # no consumer/watchdog task keeps running
    assert spies["pairs"] == [] and spies["counts"] == []   # nothing recorded


@pytest.mark.asyncio
async def test_caller_cancel_while_the_router_cancels_its_consumer_is_not_swallowed(router):
    r, _ = router
    ev = {}
    r._stream_external = _slow_cleanup(ev)
    before = set(asyncio.all_tasks())
    task = asyncio.create_task(r.route("coding", LONG, _Ctx()))
    await _wait_for(ev, "cleanup_started")     # the router's own watchdog is now cancelling its consumer
    await asyncio.sleep(0.1)
    task.cancel()                              # ...and the CALLER is cancelled during that window
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=6)
    assert task.cancelled()
    assert await _leftover_tasks(before | {task}) == []


# ==========================================================================
# AdapterRuntime
# ==========================================================================

@pytest.mark.asyncio
async def test_genuine_provider_failure_still_falls_back_and_is_penalised(router):
    """Pinned: existing failure semantics are unchanged."""
    r, _ = router
    r._stream_external = _provider_error()
    runtime, mra, oa, sf = _runtime(r, _ok("OLLAMA FALLBACK"))
    result = await asyncio.wait_for(_invoke(runtime, _Ctx()), timeout=8)
    assert result.success is True and result.adapter_used == "OllamaAdapter"
    assert mra.consecutive_failures == 1 and mra.health_score == 80


@pytest.mark.asyncio
async def test_genuine_stall_still_falls_back_and_is_penalised(router):
    """Pinned: B2c preserves the current behaviour for genuine stalls."""
    r, _ = router
    r._stream_external = _hangs_after_one_token
    runtime, mra, oa, sf = _runtime(r, _ok("OLLAMA FALLBACK"))
    result = await asyncio.wait_for(_invoke(runtime, _Ctx()), timeout=8)
    assert result.success is True and result.adapter_used == "OllamaAdapter"
    assert mra.consecutive_failures == 1


@pytest.mark.asyncio
async def test_task_cancel_during_fallback_stops_it_and_keeps_the_earned_penalty(router):
    r, _ = router
    r._stream_external = _provider_error()
    ev, second_calls = {}, []

    async def slow_generate(prompt, *a, **k):
        ev["started"] = True
        try:
            await asyncio.sleep(9999)
        except asyncio.CancelledError:
            ev["cancelled"] = True
            raise

    runtime, mra, oa, sf = _runtime(r, slow_generate, _ok("SECOND", second_calls))
    task = asyncio.create_task(_invoke(runtime, _Ctx()))
    await _wait_for(ev, "started")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ev.get("cancelled") is True                    # the fallback terminated
    assert second_calls == []                             # and no further fallback began
    assert mra.consecutive_failures == 1                  # the router keeps its genuine penalty
    assert oa.consecutive_failures == 0 and oa.health_score == 100   # no cancellation-induced penalty


@pytest.mark.asyncio
async def test_cancelling_one_request_does_not_affect_a_concurrent_request(router):
    r, _ = router
    ev, calls = {}, []

    async def by_subtask(module_name, subtask, context, scope=""):
        if subtask.endswith("CANCELME"):
            ev["a_started"] = True
            try:
                while True:
                    await asyncio.sleep(0.02)
                    yield "tok "
            finally:
                ev["a_closed"] = True
        else:
            for i in range(5):
                await asyncio.sleep(0.05)
                yield f"w{i} "

    r._stream_external = by_subtask
    runtime, mra, oa, sf = _runtime(r, _ok("OLLAMA", calls))
    cancelled = asyncio.create_task(_invoke(runtime, _Ctx(), LONG + " CANCELME"))
    kept = asyncio.create_task(_invoke(runtime, _Ctx(), LONG + " KEEP"))
    await _wait_for(ev, "a_started")
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    result = await asyncio.wait_for(kept, timeout=8)
    assert result.success is True and result.adapter_used == "ModelRouterAdapter"
    assert result.output == "w0 w1 w2 w3 w4 "
    assert mra.consecutive_failures == 0 and mra.health_score == 100
    assert calls == []
    await _wait_for(ev, "a_closed", timeout=2)            # the cancelled request's stream was stopped


@pytest.mark.asyncio
async def test_cancel_during_training_pair_recording_propagates_and_penalises_nothing(router, monkeypatch):
    r, _ = router
    r._stream_external = _complete
    ev, calls = {}, []

    async def slow_pair(module, query, answer):
        ev["pair_started"] = True
        await asyncio.sleep(9999)

    monkeypatch.setattr(r, "_record_training_pair", slow_pair)
    runtime, mra, oa, sf = _runtime(r, _ok("OLLAMA", calls))
    task = asyncio.create_task(_invoke(runtime, _Ctx()))
    await _wait_for(ev, "pair_started")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == []
    assert mra.consecutive_failures == 0 and mra.health_score == 100
