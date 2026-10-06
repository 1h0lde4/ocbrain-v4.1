"""FZ-02 / batch B2a -- a provider failure must not complete as success.

Register text (KNOWN_ISSUES.md, FZ-02): _ollama_stream() yields its error text
as a normal token and returns normally; ModelRouterAdapter.execute() hard-codes
success=True and ignores route_result.execution_detail.

Scope of B2a (decisions D1=(a), D2=(i); this batch implements neither):
  * a provider failure (connect error, mid-stream drop) is classified
    PROVIDER_FAILURE, and the adapter reports success=False for it;
  * the adapter fails closed for any other outcome that is not a success;
  * STALLED / HARD_DEADLINE / COMPLETED_WITH_PARTIAL_OUTPUT keep their current
    adapter behaviour (success=True) -- pinned below, to be changed by B2b;
  * a RouteResult with execution_detail=None (every route() branch except the
    monitored long-form stream) is not classified here and is unchanged.

Method follows the register's reproduction: the real ModelRouter and the real
ModelRouterAdapter, with only the HTTP client faked.
"""
import json

import httpx
import pytest

import core.model_router as mr
from core.capabilities.adapters.model_router_adapter import ModelRouterAdapter
from core.capabilities.capability import CapabilityRequest, CapabilityType
from core.model_router import ModelRouter, RouteResult
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_outcome import ExecutionOutcome, FailureType

# An explicit word count sends route() down the monitored-streaming branch,
# the only branch that attaches execution_detail.
LONG_FORM = "write a short story of 1000 words, fantasy type"
# Stands in for transport detail (host/URL) that must never reach a caller.
HOST_MARKER = "provider.internal.example:11434"
UNCHANGED_SUCCESS_METADATA = {"source", "similarity", "route_latency_ms"}


class _FakeContext:
    def __init__(self):
        self.cancellation_token = CancellationToken()
        self.metadata = {}

    def format_for_prompt(self, n, scope=None):
        return ""


class _Resp:
    def __init__(self, lines, drop_after):
        self._lines = lines
        self._drop_after = drop_after

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line
        if self._drop_after:
            raise httpx.ReadError(f"connection dropped by {HOST_MARKER}")


class _StreamCM:
    def __init__(self, resp, connect_error):
        self._resp = resp
        self._connect_error = connect_error

    async def __aenter__(self):
        if self._connect_error:
            raise httpx.ConnectError(
                f"All connection attempts failed: http://{HOST_MARKER}/api/generate")
        return self._resp

    async def __aexit__(self, *exc):
        return False


def _install_fake_ollama(monkeypatch, *, tokens=(), connect_error=False, drop_after=False):
    lines = [json.dumps({"response": t, "done": False}) for t in tokens]
    if not (connect_error or drop_after):
        lines.append(json.dumps({"response": "", "done": True}))

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, json=None):
            return _StreamCM(_Resp(lines, drop_after), connect_error)

    monkeypatch.setattr(mr.httpx, "AsyncClient", _Client)


@pytest.fixture
def router(monkeypatch):
    """A real ModelRouter in bootstrap stage with its persistence side effects
    (query counter, training pair, promotion) neutralised."""
    real_get = mr.config.get
    monkeypatch.setattr(
        mr.config, "get_module_state",
        lambda name: {"stage": "bootstrap", "bootstrap_model": "mistral"})
    monkeypatch.setattr(
        mr.config, "get",
        lambda key, *a, **k: f"http://{HOST_MARKER}" if key == "global.ollama_host"
        else real_get(key, *a, **k))
    r = ModelRouter()

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(r, "_record_training_pair", _noop)
    monkeypatch.setattr(r, "_increment_query_count", lambda module: 1)
    monkeypatch.setattr(r, "_maybe_promote", lambda *a, **k: None)
    return r


def _request(context=None, subtask=LONG_FORM):
    return CapabilityRequest(
        capability_type=CapabilityType.LLM_COMPLETION,
        payload={"module_name": "coding", "subtask": subtask,
                 "context": context, "scope": ""})


async def _execute(router, context=None):
    return await ModelRouterAdapter(router).execute(_request(context), resources=None)


class _StubRouter:
    """Returns a fixed RouteResult, to pin adapter behaviour per outcome."""

    def __init__(self, route_result):
        self._route_result = route_result

    async def route(self, module_name, subtask, context, scope=""):
        return self._route_result


async def _adapter_result_for(route_result):
    return await ModelRouterAdapter(_StubRouter(route_result)).execute(
        _request(), resources=None)


# --------------------------------------------------------------------------
# The marker on the error token: out-of-band signal, byte-identical text
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_token_is_marked_but_its_text_is_unchanged(router, monkeypatch):
    _install_fake_ollama(monkeypatch, connect_error=True)
    tokens = [t async for t in router._ollama_stream(
        f"http://{HOST_MARKER}", "mistral", "prompt")]
    assert len(tokens) == 1
    token = tokens[0]
    assert token.startswith("[Error: model request failed (ref ")
    assert HOST_MARKER not in token            # redaction preserved
    assert isinstance(token, mr.ProviderStreamError)
    assert token.error_id and token.error_id in token


@pytest.mark.asyncio
async def test_sse_visible_text_is_unchanged_for_a_provider_failure(router, monkeypatch):
    _install_fake_ollama(monkeypatch, connect_error=True)
    text = "".join([t async for t in router.stream_route("coding", LONG_FORM, _FakeContext())])
    assert text.startswith("[Error: model request failed (ref ")
    assert text.endswith(")]")
    assert HOST_MARKER not in text


# --------------------------------------------------------------------------
# The register's reproduction: connect error -> must no longer be "success"
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_error_is_classified_provider_failure(router, monkeypatch):
    _install_fake_ollama(monkeypatch, connect_error=True)
    result = await router.route("coding", LONG_FORM, _FakeContext())
    detail = result.execution_detail
    assert detail.failure_type == FailureType.PROVIDER_FAILURE
    assert detail.retryable is True
    assert detail.partial_output is None        # nothing real was generated
    assert detail.detail.get("error_id")
    # The answer text itself is unchanged for every existing consumer.
    assert result.answer.startswith("[Error: model request failed (ref ")


@pytest.mark.asyncio
async def test_adapter_reports_failure_when_the_provider_is_unreachable(router, monkeypatch):
    _install_fake_ollama(monkeypatch, connect_error=True)
    result = await _execute(router, _FakeContext())
    assert result.success is False
    assert result.output is None
    assert result.metadata["failure_type"] == "provider_failure"
    assert result.metadata["retryable"] is True
    assert result.metadata["error_id"]
    # The error string reaches users on some paths: it must carry no transport detail.
    assert HOST_MARKER not in result.error
    assert "ConnectError" not in result.error
    assert "connection attempts" not in result.error
    assert result.error


@pytest.mark.asyncio
async def test_mid_stream_drop_fails_and_preserves_the_partial_text(router, monkeypatch):
    _install_fake_ollama(monkeypatch, tokens=("Once ", "upon "), drop_after=True)
    ctx = _FakeContext()
    result = await router.route("coding", LONG_FORM, ctx)
    assert result.execution_detail.failure_type == FailureType.PROVIDER_FAILURE
    assert result.execution_detail.partial_output == "Once upon "   # error token excluded
    assert result.answer.startswith("Once upon [Error: model request failed")

    _install_fake_ollama(monkeypatch, tokens=("Once ", "upon "), drop_after=True)
    adapted = await _execute(router, _FakeContext())
    assert adapted.success is False
    assert adapted.output is None
    assert adapted.metadata["partial_output"] == "Once upon "
    assert HOST_MARKER not in adapted.error


@pytest.mark.asyncio
async def test_a_stream_that_raises_also_fails_at_the_adapter(router, monkeypatch):
    """The already-classified exception path (PROVIDER_FAILURE today) used to be
    hidden by the adapter's hard-coded success=True as well."""
    async def _raising(module_name, subtask, context, scope=""):
        yield "Star"
        raise ConnectionError(f"dropped by {HOST_MARKER}")

    monkeypatch.setattr(router, "_stream_external", _raising)
    result = await _execute(router, _FakeContext())
    assert result.success is False
    assert result.metadata["failure_type"] == "provider_failure"
    assert HOST_MARKER not in result.error


@pytest.mark.asyncio
async def test_a_healthy_stream_still_succeeds_unchanged(router, monkeypatch):
    _install_fake_ollama(monkeypatch, tokens=("Once ", "upon ", "a time"))
    result = await _execute(router, _FakeContext())
    assert result.success is True
    assert result.output == "Once upon a time"
    assert set(result.metadata) == UNCHANGED_SUCCESS_METADATA
    assert not result.error


# --------------------------------------------------------------------------
# Pinned: behaviour deliberately UNCHANGED by B2a (changed by B2b under D2)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("failure_type", [
    FailureType.STALLED,
    FailureType.HARD_DEADLINE,
    FailureType.COMPLETED_WITH_PARTIAL_OUTPUT,
])
async def test_stalled_deadline_and_partial_outcomes_are_pinned_unchanged(failure_type):
    rr = RouteResult(
        answer="partial text", source="external",
        execution_detail=ExecutionOutcome.failure(failure_type, partial_output="partial text"))
    result = await _adapter_result_for(rr)
    assert result.success is True                       # today's behaviour, pending B2b
    assert result.output == "partial text"
    assert set(result.metadata) == UNCHANGED_SUCCESS_METADATA   # no new keys either
    assert not result.error


@pytest.mark.asyncio
async def test_a_route_result_without_execution_detail_is_unchanged():
    result = await _adapter_result_for(RouteResult(answer="Hi there!", source="external"))
    assert result.success is True
    assert result.output == "Hi there!"
    assert set(result.metadata) == UNCHANGED_SUCCESS_METADATA


# --------------------------------------------------------------------------
# Fail closed for every other non-success outcome
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("failure_type", [
    FailureType.PROVIDER_FAILURE,
    FailureType.EMPTY_RESPONSE,
    FailureType.CANCELLED,
    FailureType.VALIDATION_ERROR,
    FailureType.OTHER_FAILURE,
])
async def test_non_success_outcomes_fail_closed(failure_type):
    rr = RouteResult(
        answer="whatever the model said", source="external",
        execution_detail=ExecutionOutcome.failure(failure_type, provider="coding", model="mistral"))
    result = await _adapter_result_for(rr)
    assert result.success is False
    assert result.output is None
    assert result.metadata["failure_type"] == failure_type.value
    assert result.error
    assert "whatever the model said" not in result.error
