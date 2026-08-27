import asyncio

import pytest

from core.model_router import ModelRouter, _estimate_long_form
from core.runtime.execution_outcome import FailureType


class _FakeContext:
    """Minimal stand-in exercising the ExecutionContext-shaped path (has a
    real cancellation_token, unlike the legacy WorkerContext)."""

    def __init__(self):
        from core.runtime.cancellation import CancellationToken
        self.cancellation_token = CancellationToken()
        self.metadata = {}

    def format_for_prompt(self, n):
        return ""


async def _healthy_stream(module_name, subtask, context):
    for word in ["Once ", "upon ", "a ", "time, ", "a ", "brave ", "knight..."]:
        await asyncio.sleep(0.01)
        yield word


async def _hung_stream(module_name, subtask, context):
    """Yields once, then never again -- a genuinely stalled provider, not a
    slow-but-eventually-responsive one. This is exactly the shape that a
    cooperative is_cancelled check between chunks cannot interrupt; only
    task-cancelling the consumer can."""
    yield "Beginning the tale"
    await asyncio.sleep(9999)
    yield "unreachable"  # pragma: no cover


async def _erroring_stream(module_name, subtask, context):
    yield "Star"
    raise ConnectionError("provider connection dropped")


def test_word_count_heuristic_matches_the_original_bug_report():
    long_form, tokens = _estimate_long_form("write a short story of 1000 words, fantasy type")
    assert long_form is True
    assert tokens is not None and tokens > 400


def test_word_count_heuristic_ignores_ordinary_short_requests():
    long_form, tokens = _estimate_long_form("Hi")
    assert long_form is False
    assert tokens is None

    long_form2, _ = _estimate_long_form("what's the capital of France?")
    assert long_form2 is False


@pytest.mark.asyncio
async def test_monitored_streaming_completes_and_reports_success():
    router = ModelRouter()
    context = _FakeContext()
    answer, outcome = await router._call_monitored_streaming(
        _healthy_stream, "coding", "write a 1000 word story", context,
        model_label="mistral", estimated_output_tokens=1350,
    )
    assert answer == "Once upon a time, a brave knight..."
    assert outcome.failure_type == FailureType.SUCCESS
    assert outcome.retryable is False
    assert not context.cancellation_token.is_cancelled


@pytest.mark.asyncio
async def test_monitored_streaming_actually_interrupts_a_hung_provider():
    """This is the test that would have caught the original consumer-loop
    bug: a stream that yields once and then hangs forever must not hang
    this call forever -- the watchdog's stall detection has to actually
    stop consumption, not just flag it."""
    router = ModelRouter()
    context = _FakeContext()

    from core.runtime.execution_budget import ExecutionBudget
    import core.model_router as mr

    def _tiny_budget(**kwargs):
        return ExecutionBudget(
            startup_deadline_s=0.5, progress_deadline_s=0.05,
            hard_ceiling_s=5.0, absolute_ceiling_s=5.0, max_extension_s=0.0,
        )

    orig = mr.ExecutionPolicy.for_generation
    mr.ExecutionPolicy.for_generation = classmethod(lambda cls, **kw: _tiny_budget(**kw))

    try:
        answer, outcome = await asyncio.wait_for(
            router._call_monitored_streaming(
                _hung_stream, "coding", "write a 5000 word story", context,
                model_label="mistral", estimated_output_tokens=6750,
            ),
            timeout=3.0,  # the whole point: must resolve fast, nowhere near
                          # the old 60s cap or asyncio.sleep(9999) in the fake
        )
    finally:
        mr.ExecutionPolicy.for_generation = orig

    assert answer == "Beginning the tale"  # partial output preserved, not discarded
    assert outcome.failure_type == FailureType.STALLED
    assert outcome.retryable is True
    assert outcome.partial_output == "Beginning the tale"
    assert context.cancellation_token.is_cancelled
    assert context.cancellation_token.reason == "stall"


@pytest.mark.asyncio
async def test_monitored_streaming_classifies_provider_exceptions():
    router = ModelRouter()
    context = _FakeContext()
    answer, outcome = await router._call_monitored_streaming(
        _erroring_stream, "coding", "write a 1000 word story", context,
        model_label="mistral", estimated_output_tokens=1350,
    )
    assert answer == "Star"
    assert outcome.failure_type == FailureType.PROVIDER_FAILURE
    assert outcome.retryable is True


@pytest.mark.asyncio
async def test_route_short_request_never_touches_monitored_path(monkeypatch):
    """§20 regression proof at the route() level, not just the heuristic
    level: a short request must exercise the pre-existing generate_with_fallback
    path, not the new monitored-streaming machinery, end to end."""
    from core.config import config as real_config
    router = ModelRouter()
    context = _FakeContext()

    called = {"monitored": False}

    async def _spy(*a, **kw):
        called["monitored"] = True
        return "unused", None

    router._call_monitored_streaming = _spy

    async def _fake_external(module_name, subtask, ctx):
        return "Hi there!"

    router._call_external = _fake_external

    result = await router.route("coding", "Hi", context)

    assert called["monitored"] is False
    assert result.answer == "Hi there!"
    assert result.execution_detail is None
