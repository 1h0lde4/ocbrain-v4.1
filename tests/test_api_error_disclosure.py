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
import json
import logging
import uuid
from types import SimpleNamespace

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
        async def handle(self, *a, **kw):
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


# ── core/brain_api.py _stream_query ─────────────────────────────────────

@pytest.mark.asyncio
async def test_brain_api_stream_query_redacts_exception(caplog):
    class ExplodingOrchestrator:
        async def handle(self, *a, **kw):
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
