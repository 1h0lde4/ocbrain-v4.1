"""
tests/test_answer_error_disclosure.py -- exception text in caller-visible answers.

merger.merge() appends "error" results to the string a caller receives
(core/merger.py), and Orchestrator / PlannerWorker / dispatcher built those
results from f"[Error in {mod}: {exc}]". So whatever a module's exception
said -- host, URL, path, config value -- was returned to /query clients.
CodeQL does not flag this (the flow goes through gather(return_exceptions)
and an f-string, not a request-to-response taint path); it was found by
grepping for exception text formatted into strings after the CodeQL-flagged
sites were fixed (see tests/test_api_error_disclosure.py).

Now each site logs the exception with its traceback under a fresh ref
(core/error_ref.py) and puts only "[Error in <module>: <ExceptionClass>
(ref <uuid>)]" in the answer.

Covered here: the helper, the real Orchestrator.handle() call site, and
core/dispatcher.py (dormant -- nothing imports it -- but it built the same
string, so a future caller would have reintroduced the leak). PlannerWorker
is covered by the updated tests in tests/test_planner_worker.py and
tests/test_planner_capability_migration.py, which used to assert the raw
message was in the answer.

Not covered: WorkerResult.error / event-payload "error": str(e) fields
(internal channels, not answer text) and interface/updater.py's
check_error (separate change).
"""
import logging
import re
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

import core.dispatcher as dispatcher
import core.orchestrator as orchestrator_module
from core.context import ContextMemory
from core.decomposer import Task
from core.error_ref import log_and_ref
from core.governance.governance_kernel import GovernanceResult
from core.memory.unified_memory import UnifiedMemory

SECRET = "psycopg2: password=hunter2 host=10.0.0.5 path=/opt/ocbrain/private.db"


def test_log_and_ref_returns_uuid_and_logs_the_real_detail(caplog):
    log = logging.getLogger("ocbrain.test_error_ref")
    with caplog.at_level(logging.ERROR, logger="ocbrain.test_error_ref"):
        ref = log_and_ref(log, "unit context", RuntimeError(SECRET))

    uuid.UUID(ref)  # raises if it is not a real UUID
    assert "hunter2" not in ref
    # Message and traceback reach the log, tagged with the same ref.
    assert ref in caplog.text
    assert "unit context" in caplog.text
    assert "hunter2" in caplog.text


@pytest.mark.asyncio
async def test_orchestrator_handle_redacts_module_exception(monkeypatch, caplog):
    governance = MagicMock()
    governance.evaluate_action = MagicMock(return_value=GovernanceResult())
    orch = orchestrator_module.Orchestrator(
        modules={"web_search": object()},
        context=MagicMock(spec=ContextMemory),
        router=MagicMock(),
        memory=AsyncMock(spec=UnifiedMemory),
        governance=governance,
        event_stream=AsyncMock(),
    )
    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda q, top_k=2: [{"module": "web_search", "score": 0.9}],
    )

    async def boom(self, *a, **kw):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(orchestrator_module.Orchestrator, "_run_module", boom)

    with caplog.at_level(logging.ERROR):
        answer = await orch.handle("find something")

    m = re.fullmatch(r"\[Error in web_search: RuntimeError \(ref ([0-9a-f-]{36})\)\]", answer)
    assert m, answer
    for leaked in ("hunter2", "10.0.0.5", "private.db", "psycopg2"):
        assert leaked not in answer
    # The detail is not lost: same ref, full message, in the server log.
    assert m.group(1) in caplog.text
    assert "hunter2" in caplog.text


@pytest.mark.asyncio
async def test_dispatcher_redacts_task_exception(monkeypatch, caplog):
    async def boom(*a, **kw):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(dispatcher, "_dispatch_one", boom)
    task = Task(id="t1", module="web_search", subtask="find something")

    with caplog.at_level(logging.ERROR):
        results = await dispatcher.run([task], router=MagicMock(), context=MagicMock(), modules={})

    assert len(results) == 1
    answer = results[0].result.answer
    m = re.fullmatch(r"\[Module web_search error: RuntimeError \(ref ([0-9a-f-]{36})\)\]", answer)
    assert m, answer
    assert "hunter2" not in answer
    assert m.group(1) in caplog.text
    assert "hunter2" in caplog.text
