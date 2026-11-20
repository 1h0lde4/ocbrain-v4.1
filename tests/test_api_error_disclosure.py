"""
tests/test_api_error_disclosure.py — CodeQL py/stack-trace-exposure fix
(interface/api.py, core/brain_api.py).

Both files' exception handlers used to put str(exception) or
traceback.format_exc() directly into an HTTP response or SSE event body
sent back to the caller (CWE-209/497). Fixed by routing every such
handler through an opaque error_id instead, with the real detail logged
server-side only. Covers all four call sites confirmed live on `main` on
2026-09-26 -- two more than the originating CodeQL report named.
interface/api.py's _stream_response turned out to have the same pattern
at two more sites, found while reading the flagged code for this fix, not
by a separate audit pass:

  1. interface/api.py POST /query                         (CodeQL-flagged)
  2. interface/api.py _stream_response, single-module path (found here)
  3. interface/api.py _stream_response, multi-module path  (found here)
  4. core/brain_api.py _stream_query                       (CodeQL-flagged)

Sites 1-3 share interface/api.py's _log_and_redact helper, tested
directly below and via the real POST /query and single-module streaming
call sites. Site 4 is core/brain_api.py's own file-local equivalent (kept
local rather than importing across the interface/core boundary for one
helper -- see that file's comment).

Not covered here: the multi-module streaming path (site 3) is a one-line
change using the same _log_and_redact helper and the same yield shape as
the tested single-module path (site 2) -- not separately
integration-tested, on the judgment that this is low incremental risk
given the helper itself is verified. Also not covered: whether this
exception-detail class extends to interface/updater.py's /updates /
/update/install responses (check_error=str(e), confirmed present but not
CodeQL-flagged and not fixed by this pass -- a different feature area,
left for its own explicit disposition rather than folded in here).
"""
import asyncio
import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import interface.api as api_module
import core.brain_api as brain_api_module


# ── _log_and_redact (interface/api.py) ──────────────────────────────────

def test_log_and_redact_returns_opaque_uuid_and_logs_real_detail(caplog):
    """The one property the whole fix rests on: the returned id must not
    be (or contain) the exception text, and the exception text must still
    reach the server-side log, tagged with that same id so an operator
    can correlate the two."""
    secret = ValueError(
        "/home/moncif/.ssh/id_rsa: permission denied, token=sk-abc123"
    )

    with caplog.at_level(logging.ERROR, logger="interface.api"):
        error_id = api_module._log_and_redact("test context", secret)

    uuid.UUID(error_id)  # raises ValueError if this isn't a real UUID
    assert "permission denied" not in error_id
    assert "sk-abc123" not in error_id

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert error_id in logged
    assert "test context" in logged


# ── POST /query (interface/api.py) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_query_endpoint_redacts_exception_details(monkeypatch):
    class ExplodingOrchestrator:
        async def handle_with_result(self, *a, **kw):
            raise RuntimeError(
                "psycopg2: connection to 10.0.0.5 failed, password=hunter2"
            )

    monkeypatch.setattr(api_module, "_orchestrator", ExplodingOrchestrator())

    resp = await api_module.query(api_module.QueryRequest(query="hi"))

    assert resp.success is False
    assert resp.error == "internal_error"
    assert "error_id" in resp.meta
    uuid.UUID(resp.meta["error_id"])
    assert "traceback" not in resp.meta
    assert "hunter2" not in json.dumps(resp.meta)
    assert "10.0.0.5" not in json.dumps(resp.meta)


@pytest.mark.asyncio
async def test_query_endpoint_preserves_structured_workflow_failure(monkeypatch):
    from core.orchestrator import OrchestratorResult

    class FailedOrchestrator:
        async def handle_with_result(self, *a, **kw):
            return OrchestratorResult(
                answer="Partial answer. (Note: processing did not complete successfully.)",
                success=False,
                error="workflow_failed",
                metadata={"partial_output": "Partial answer."},
            )

    monkeypatch.setattr(api_module, "_orchestrator", FailedOrchestrator())
    response = await api_module.query(api_module.QueryRequest(query="hi"))
    assert response.success is False
    assert response.error == "workflow_failed"
    assert response.answer.startswith("Partial answer.")
    assert response.meta["outcome"] == "workflow_failed"


@pytest.mark.asyncio
async def test_stream_response_emits_workflow_failure_instead_of_tokens(monkeypatch):
    from types import SimpleNamespace
    from core.orchestrator import OrchestratorResult

    monkeypatch.setattr(
        "core.runtime.execution_graph.execution_registry.get", lambda _id: None
    )
    monkeypatch.setattr("core.parser.parse", lambda query: query)

    async def labels(*args, **kwargs):
        return ["one", "two"]

    monkeypatch.setattr("core.classifier.label", labels)
    monkeypatch.setattr(
        "core.decomposer.build",
        lambda parsed, result: [
            SimpleNamespace(module="one"), SimpleNamespace(module="two")
        ],
    )
    orchestrator = SimpleNamespace(
        context=SimpleNamespace(),
        handle_with_result=AsyncMock(return_value=OrchestratorResult(
            answer="Partial answer.",
            success=False,
            error="workflow_failed",
            metadata={"partial_output": "Partial answer."},
        )),
    )

    chunks = [chunk async for chunk in api_module._stream_response(
        orchestrator, "hi", execution_id="failed-execution"
    )]
    stream = "".join(chunks)
    assert '"error": "workflow_failed"' in stream
    assert '"partial_output": "Partial answer."' in stream
    assert '"token":' not in stream


@pytest.mark.asyncio
async def test_brain_v2_query_exposes_structured_workflow_failure():
    from fastapi import FastAPI
    from core.brain_api import QueryRequest, register, router
    from core.orchestrator import OrchestratorResult

    class FailedOrchestrator:
        async def handle_with_result(self, *a, **kw):
            return OrchestratorResult(
                answer="I'm sorry, I wasn't able to complete your request.",
                success=False,
                error="workflow_failed",
            )

    app = FastAPI()
    register(app, {"orchestrator": FailedOrchestrator()})
    endpoint = next(
        route.endpoint for route in reversed(router.routes)
        if route.path == "/brain/v2/query"
    )
    response = await endpoint(QueryRequest(query="hi"))
    assert response.success is False
    assert response.error == "workflow_failed"


@pytest.mark.asyncio
async def test_brain_api_stream_query_emits_workflow_failure():
    from core.orchestrator import OrchestratorResult

    class FailedOrchestrator:
        async def handle_with_result(self, *a, **kw):
            return OrchestratorResult(
                answer="Partial answer.",
                success=False,
                error="workflow_failed",
                metadata={"partial_output": "Partial answer."},
            )

    chunks = [chunk async for chunk in brain_api_module._stream_query(
        FailedOrchestrator(), "hi"
    )]
    stream = "".join(chunks)
    assert '"error": "workflow_failed"' in stream
    assert '"partial_output": "Partial answer."' in stream
    assert '"token":' not in stream


# ── _stream_response single-module path (interface/api.py) ─────────────

@pytest.mark.asyncio
async def test_stream_response_single_module_redacts_exception(monkeypatch):
    monkeypatch.setattr(
        "core.runtime.execution_graph.execution_registry.get", lambda eid: None
    )
    monkeypatch.setattr("core.parser.parse", lambda q: q)

    async def fake_label(*a, **kw):
        return ["test_module"]

    monkeypatch.setattr("core.classifier.label", fake_label)

    fake_task = SimpleNamespace(module="test_module", subtask="hello")
    monkeypatch.setattr("core.decomposer.build", lambda parsed, labels: [fake_task])

    class ExplodingRouter:
        async def stream_route(self, *a, **kw):
            raise RuntimeError("leaked: /etc/shadow contents")
            yield  # pragma: no cover -- keeps this an async generator

    monkeypatch.setattr("core.model_router.model_router", ExplodingRouter())

    mock_orchestrator = SimpleNamespace(context=SimpleNamespace())

    chunks = []
    async for chunk in api_module._stream_response(
        mock_orchestrator, "hello", execution_id="unregistered-exec-id"
    ):
        chunks.append(chunk)

    joined = "".join(chunks)
    assert "/etc/shadow" not in joined
    assert '"error": "internal_error"' in joined
    assert "error_id" in joined


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure_type", ["provider_failure", "empty_response", "cancelled"])
async def test_stream_response_single_module_failure_is_terminal(monkeypatch, failure_type):
    from core.model_router import ProviderStreamError

    class FakeGraph:
        async def add_node(self, **kwargs):
            return SimpleNamespace(node_id="stream-node")

    class FakeMonitor:
        def __init__(self, _graph):
            self.failures = []
            self.completions = []
            self.statuses = []

        async def record_status(self, *args, **kwargs):
            self.statuses.append((args, kwargs))

        async def report_progress(self, *args, **kwargs):
            pass

        async def record_failure(self, *args, **kwargs):
            self.failures.append((args, kwargs))

        async def record_completion(self, *args, **kwargs):
            self.completions.append((args, kwargs))

    class FakeEventStream:
        def __init__(self):
            self.events = []

        async def append(self, *, event_type, source, payload):
            self.events.append((event_type, source, payload))

    class FakeRouter:
        async def stream_route(self, *args, **kwargs):
            if failure_type == "provider_failure":
                yield "partial output"
                yield ProviderStreamError(
                    "[Error: model request failed (ref opaque)]", "opaque")
            elif failure_type == "cancelled":
                yield "partial output"
                raise asyncio.CancelledError

    graph = FakeGraph()
    monitor = FakeMonitor(graph)
    event_stream = FakeEventStream()
    save_calls = []

    async def fake_save(*args, **kwargs):
        save_calls.append((args, kwargs))

    monkeypatch.setattr("core.runtime.execution_graph.execution_registry.get", lambda _id: graph)
    monkeypatch.setattr("core.runtime.progress.ProgressMonitor", lambda _graph: monitor)
    monkeypatch.setattr("core.events.event_stream.get_event_stream", lambda: event_stream)
    monkeypatch.setattr("core.parser.parse", lambda query: query)

    async def labels(*args, **kwargs):
        return ["test_module"]

    monkeypatch.setattr("core.classifier.label", labels)
    monkeypatch.setattr(
        "core.decomposer.build",
        lambda parsed, result: [
            SimpleNamespace(module="test_module", subtask="hello")
        ],
    )
    monkeypatch.setattr("core.model_router.model_router", FakeRouter())
    monkeypatch.setattr(api_module, "_save_context_background", fake_save)

    stream_response = api_module._stream_response(
        SimpleNamespace(context=SimpleNamespace()), "hello", execution_id="exec-1"
    )
    if failure_type == "cancelled":
        with pytest.raises(asyncio.CancelledError):
            [chunk async for chunk in stream_response]
        assert monitor.statuses[-1][0][1].value == "cancelled"
        assert [event[0] for event in event_stream.events] == ["execution.cancelled"]
        assert save_calls == []
        return

    chunks = [chunk async for chunk in stream_response]
    await asyncio.sleep(0)
    stream = "".join(chunks)

    assert f'"error": "{failure_type}"' in stream
    if failure_type == "provider_failure":
        assert '"token": "partial output"' in stream
        assert "model request failed" not in stream
        assert '"error_id": "opaque"' in stream
    else:
        assert '"token":' not in stream
    assert monitor.failures and not monitor.completions
    assert [event[0] for event in event_stream.events] == ["execution.failed"]
    assert event_stream.events[0][2]["error_type"] == failure_type
    if failure_type == "provider_failure":
        assert event_stream.events[0][2]["error_id"] == "opaque"
    assert save_calls == []


# ── core/brain_api.py _stream_query ─────────────────────────────────────

@pytest.mark.asyncio
async def test_brain_api_stream_query_redacts_exception(caplog):
    class ExplodingOrchestrator:
        async def handle_with_result(self, *a, **kw):
            raise RuntimeError("internal: /data/ocbrain/secrets.db unreachable")

    chunks = []
    with caplog.at_level(logging.ERROR, logger="core.brain_api"):
        async for chunk in brain_api_module._stream_query(
            ExplodingOrchestrator(), "hi"
        ):
            chunks.append(chunk)

    joined = "".join(chunks)
    assert "/data/ocbrain/secrets.db" not in joined
    assert '"error": "internal_error"' in joined
    assert "error_id" in joined

    # The real detail reaches the log via exc_info's traceback rendering,
    # not the format-string message itself -- caplog.text is the fully
    # rendered record text (message + traceback), unlike
    # record.getMessage() which is the format string alone.
    assert "/data/ocbrain/secrets.db" in caplog.text


@pytest.mark.asyncio
async def test_brain_api_stream_query_preserves_workflow_failure():
    class FailedOrchestrator:
        async def handle_with_result(self, *args, **kwargs):
            return SimpleNamespace(
                success=False,
                error="workflow_failed",
                answer="The workflow did not complete.",
                metadata={"partial_output": "partial result"},
            )

    chunks = [chunk async for chunk in brain_api_module._stream_query(
        FailedOrchestrator(), "hi"
    )]
    stream = "".join(chunks)

    assert '"error": "workflow_failed"' in stream
    assert '"answer": "The workflow did not complete."' in stream
    assert '"partial_output": "partial result"' in stream
    assert stream.endswith("data: [DONE]\n\n")


# ── Remaining flows found via CodeQL's own source-to-sink paths ─────────
#
# After the fixes above merged, CodeQL still reported interface/api.py's
# StreamingResponse sink and the /debug `return report` as open
# py/stack-trace-exposure alerts. The SARIF code flows showed why: the
# exception text reached those sinks by two routes the earlier pass
# missed -- core/model_router.py's _ollama_stream yielded
# f"[Error: {e}]" as an ordinary stream token (forwarded verbatim by
# _stream_response), and /debug put str(e) into its returned report.

@pytest.mark.asyncio
async def test_model_router_stream_error_token_redacts_exception(monkeypatch, caplog):
    import re
    import core.model_router as mr

    class ExplodingClient:
        def __init__(self, *a, **kw):
            raise RuntimeError(
                "connect failed to http://10.0.0.5:11434 password=hunter2"
            )

    monkeypatch.setattr(mr.httpx, "AsyncClient", ExplodingClient)

    tokens = []
    with caplog.at_level(logging.ERROR, logger="core.model_router"):
        async for tok in mr.model_router._ollama_stream(
            "http://localhost:11434", "mistral", "hi"
        ):
            tokens.append(tok)

    joined = "".join(tokens)
    assert "hunter2" not in joined
    assert "10.0.0.5" not in joined
    assert joined.startswith("[Error:")

    # The caller gets an id it can quote; the same id ties the log line
    # (which still carries the real detail) to that token.
    ref = re.search(r"ref ([0-9a-f-]{36})", joined)
    assert ref, joined
    uuid.UUID(ref.group(1))
    assert ref.group(1) in caplog.text
    assert "hunter2" in caplog.text


@pytest.mark.asyncio
async def test_debug_endpoint_redacts_exception_text(monkeypatch, caplog):
    import httpx

    class BrokenModule:
        def health(self):
            raise RuntimeError("sqlite3: unable to open /opt/ocbrain/private.db")

    monkeypatch.setattr(
        api_module,
        "_orchestrator",
        SimpleNamespace(modules={"broken_mod": BrokenModule()}),
    )

    class ExplodingClient:
        def __init__(self, *a, **kw):
            raise RuntimeError("Cannot connect to 10.9.9.9:11434 token=sk-zzz")

    monkeypatch.setattr(httpx, "AsyncClient", ExplodingClient)

    with caplog.at_level(logging.ERROR, logger="interface.api"):
        report = await api_module.debug()

    dumped = json.dumps(report)
    assert "private.db" not in dumped
    assert "sk-zzz" not in dumped
    assert "10.9.9.9" not in dumped

    # Still useful for diagnosing: the exception class survives, and the
    # id points at the server log line that has the full detail.
    assert report["modules"]["broken_mod"]["error"] == "RuntimeError"
    assert report["ollama"]["status"] == "UNREACHABLE"
    assert report["ollama"]["error"] == "RuntimeError"
    uuid.UUID(report["ollama"]["error_id"])
    uuid.UUID(report["modules"]["broken_mod"]["error_id"])
    assert "private.db" in caplog.text
    assert "sk-zzz" in caplog.text
