"""B2c -- cancellation is not a failure.

Two different events were being conflated:

  failure       the adapter cannot complete the request: the runtime records it,
                applies the existing health policy and may fall back;
  cancellation  the invocation is no longer wanted: nothing should be retried
                elsewhere, nothing should be penalised, and the work should stop.

Cancellation reaches this runtime two ways, and both are covered:

  * task cancellation (asyncio.CancelledError): a control-flow exception that
    must propagate untouched and must stop the provider stream in-process;
  * token cancellation (CancellationToken.cancel(reason)): cooperative. A token
    cancelled with the monitored attempt's OWN watchdog reasons ("stall",
    "hard_deadline") is an adapter-local timeout and keeps its existing
    behaviour; any other reason is a caller-side cancellation.

What this file can and cannot show:
  * logical cancellation (no fallback, no health penalty, no success, no
    training pair) and in-process stop (the stream generator's `finally` runs,
    no task is left running) are proven with deterministic fakes;
  * that a real model server stopped generating is NOT proven here. Closing a
    client stream does not by itself prove the server stopped.

Two behaviours B2c deliberately does not change are recorded as strict xfails so
they stay visible: see the two tests at the end.
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
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_outcome import FailureType

# An explicit word count sends route() down the monitored-streaming branch.
LONG = "write a short story of 1000 words, fantasy type"


class _Ctx:
    def __init__(self, token=None):
        self.cancellation_token = token or CancellationToken()
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


def _cancels_token_with(reason):
    async def stream(module_name, subtask, context, scope=""):
        yield "partial before cancel"
        context.cancellation_token.cancel(reason)
        await asyncio.sleep(9999)
    return stream


def _provider_error(then_cancel_with=None):
    async def stream(module_name, subtask, context, scope=""):
        yield mr.ProviderStreamError("[Error: model request failed (ref x)]", "x")
        if then_cancel_with is not None:
            context.cancellation_token.cancel(then_cancel_with)
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
# Router: the caller is cancelled (task cancellation)
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
# Router: token cancellation
# ==========================================================================

def test_caller_cancellation_helper_distinguishes_the_attempts_own_reasons():
    import core.runtime.watchdog_decision as wd
    assert wd.is_caller_cancellation(None) is False
    assert wd.is_caller_cancellation(CancellationToken()) is False          # not cancelled
    for own in ("stall", "hard_deadline"):                                  # the attempt's own watchdog
        token = CancellationToken()
        token.cancel(own)
        assert wd.is_caller_cancellation(token) is False
    for other in ("cancelled", "user pressed stop", "execution stall", "execution hard_deadline"):
        token = CancellationToken()
        token.cancel(other)
        assert wd.is_caller_cancellation(token) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["cancelled", "user pressed stop",
                                    "execution stall", "execution hard_deadline"])
async def test_a_token_cancelled_by_someone_else_is_classified_cancelled(router, reason):
    r, _ = router
    r._stream_external = _cancels_token_with(reason)
    routed = await asyncio.wait_for(r.route("coding", LONG, _Ctx()), timeout=6)
    detail = routed.execution_detail
    assert detail.failure_type == FailureType.CANCELLED
    assert detail.retryable is False
    assert detail.partial_output == "partial before cancel"     # preserved as data


@pytest.mark.asyncio
async def test_the_attempts_own_stall_reason_is_still_a_stall(router):
    r, _ = router
    r._stream_external = _hangs_after_one_token
    routed = await asyncio.wait_for(r.route("coding", LONG, _Ctx()), timeout=6)
    assert routed.execution_detail.failure_type == FailureType.STALLED


# ==========================================================================
# Completion boundary: what a cancelled generation may and may not record
# ==========================================================================

@pytest.mark.asyncio
async def test_a_cancelled_generation_records_no_training_pair_count_or_promotion(router):
    r, spies = router
    r._stream_external = _cancels_token_with("user pressed stop")
    routed = await asyncio.wait_for(r.route("coding", LONG, _Ctx()), timeout=6)
    assert routed.execution_detail.failure_type == FailureType.CANCELLED
    assert spies == {"pairs": [], "counts": [], "promoted": []}


@pytest.mark.asyncio
async def test_a_completed_generation_still_records_its_training_pair_and_count(router):
    r, spies = router
    r._stream_external = _complete
    await asyncio.wait_for(r.route("coding", LONG, _Ctx()), timeout=6)
    assert spies["pairs"] == ["A complete story."] and len(spies["counts"]) == 1


@pytest.mark.asyncio
async def test_provider_failure_side_effects_are_unchanged_and_tracked_separately(router):
    """Pinned, not endorsed: a provider failure still records its error token as
    a training pair. That pre-existing behaviour (all non-success outcomes) is a
    separate tracked issue and is not changed by B2c."""
    r, spies = router
    r._stream_external = _provider_error()
    await asyncio.wait_for(r.route("coding", LONG, _Ctx()), timeout=6)
    assert len(spies["pairs"]) == 1 and len(spies["counts"]) == 1


# ==========================================================================
# AdapterRuntime
# ==========================================================================

@pytest.mark.asyncio
async def test_token_cancel_during_the_router_attempt_is_terminal_and_not_a_health_event(router):
    r, _ = router
    r._stream_external = _cancels_token_with("user pressed stop")
    calls = []
    runtime, mra, oa, sf = _runtime(r, _ok("OLLAMA", calls))
    result = await asyncio.wait_for(_invoke(runtime, _Ctx()), timeout=8)
    assert result.success is False
    assert result.metadata.get("cancelled") is True
    assert result.metadata.get("failure_type") == "cancelled"
    assert calls == []                                    # no fallback attempt
    assert mra.consecutive_failures == 0 and mra.health_score == 100 and mra.is_available()


@pytest.mark.asyncio
async def test_a_cancelled_invocation_is_neither_a_success_nor_a_failure_in_the_stats(router):
    r, _ = router
    r._stream_external = _cancels_token_with("user pressed stop")
    runtime, *_ = _runtime(r, _ok("OLLAMA"))
    await asyncio.wait_for(_invoke(runtime, _Ctx()), timeout=8)
    stats = runtime.stats()
    assert stats["total_invocations"] == 1
    assert stats["total_failures"] == 0
    assert stats["total_cancelled"] == 1


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
async def test_token_cancel_between_attempts_stops_further_fallback(router):
    r, _ = router
    r._stream_external = _provider_error(then_cancel_with="user pressed stop")
    first, second = [], []
    runtime, mra, oa, sf = _runtime(r, _ok("OLLAMA", first), _ok("SECOND", second))
    result = await asyncio.wait_for(_invoke(runtime, _Ctx()), timeout=8)
    assert result.success is False and result.metadata.get("cancelled") is True
    assert first == [] and second == []                   # neither fallback started
    assert mra.consecutive_failures == 1                  # the genuine provider failure is still penalised
    assert oa.consecutive_failures == 0 and sf.consecutive_failures == 0


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


# ==========================================================================
# Known limitations, recorded as strict xfails (not fixed by B2c)
# ==========================================================================

@pytest.mark.xfail(strict=True, reason=(
    "Known limitation, not fixed by B2c: a token cancelled while a non-token-aware "
    "fallback adapter is already mid-call is not delivered to it. Task cancellation "
    "is (see the task-cancel fallback test). Needs a per-attempt token."))
@pytest.mark.asyncio
async def test_token_cancel_during_an_in_flight_fallback_stops_it_promptly(router):
    r, _ = router
    r._stream_external = _provider_error()
    ev = {}

    async def slow_but_finite(prompt, *a, **k):
        ev["started"] = True
        await asyncio.sleep(1.0)
        return "LATE FALLBACK ANSWER"

    ctx = _Ctx()
    runtime, *_ = _runtime(r, slow_but_finite)
    task = asyncio.create_task(_invoke(runtime, ctx))
    await _wait_for(ev, "started")
    ctx.cancellation_token.cancel("user pressed stop")
    result = await asyncio.wait_for(task, timeout=5)
    assert result.metadata.get("cancelled") is True


@pytest.mark.xfail(strict=True, reason=(
    "Known defect, not fixed by B2c: one module's stall cancels the SHARED "
    "execution token and cuts a healthy sibling mid-stream. Needs a per-attempt "
    "token. Pre-dates B2a/B2b."))
@pytest.mark.asyncio
async def test_one_modules_stall_does_not_cut_a_healthy_sibling_sharing_the_token(router):
    r, _ = router

    async def by_subtask(module_name, subtask, context, scope=""):
        if subtask.endswith("STALLER"):
            yield "stalling module output"
            await asyncio.sleep(9999)
        else:
            for i in range(60):
                await asyncio.sleep(0.02)
                yield f"c{i} "

    r._stream_external = by_subtask
    ctx = _Ctx(CancellationToken())                       # one token shared by both modules
    stall = asyncio.create_task(r.route("coding", LONG + " STALLER", ctx))
    healthy = asyncio.create_task(r.route("coding", LONG + " HEALTHY", ctx))
    routed_stall, routed_healthy = await asyncio.wait_for(asyncio.gather(stall, healthy), timeout=10)
    assert routed_stall.execution_detail.failure_type == FailureType.STALLED
    assert routed_healthy.execution_detail.failure_type == FailureType.SUCCESS
    assert len(routed_healthy.answer.split()) == 60
