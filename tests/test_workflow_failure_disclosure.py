"""
tests/test_workflow_failure_disclosure.py -- a failed workflow run must not hand
its raw error text to the caller as the answer (CWE-209/497).

Orchestrator.handle()'s K2.2 workflow path returned
f"Sorry, I encountered an internal error: {wf_result.error}", and
wf_result.error is the failing worker's own string. For PlannerWorker that is
"PlannerWorker pipeline error: <str(exception)>", so a ContextMemory / memory /
router failure anywhere in its pipeline put filesystem paths, hosts or config
values into the /query answer. This is answer text, not an internal channel;
DEBT-037 fixed the sibling sites (core/error_ref.py states the rule) and left
this one: "whether PlannerWorker's WorkerResult.error ever reaches a caller has
not been traced". It does, through this branch.

Contract (the answer-text rule of DEBT-037 / core/error_ref.py, applied here):
  C1  the answer is exactly
      "Sorry, I encountered an internal error: WorkflowFailure (ref <uuid>)";
      no part of wf_result.error appears in it
  C2  the real text is logged server-side under that ref
  C3  internal channels are unchanged: the orchestrator.query_failed event
      still carries wf_result.error, and WorkerResult.error is untouched
  C4  the sibling branch (an unexpected exception inside the workflow-runtime
      path) still returns only the exception class name

Not covered: the K4.2 front-end branch, which never reads wf_result.error.
"""
import logging
import re
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.context import ContextMemory
from core.error_ref import log_text_and_ref
from core.events.event_stream import get_event_stream
from core.governance.governance_kernel import get_governance_kernel
from core.memory.unified_memory import UnifiedMemory
from core.model_router import RouteResult
from core.orchestrator import Orchestrator
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workers.base import WorkerResult
from core.workers.planner import PlannerWorker
from core.workflow.runtime import WorkflowRuntime

SECRET = "SECRET-DETAIL password=hunter2 /var/lib/ocbrain/data/context.sqlite locked"
ANSWER_RE = re.compile(
    r"Sorry, I encountered an internal error: WorkflowFailure "
    r"\(ref ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\)")


def _orchestrator(context=None):
    """Wired the way main.py wires K2.2: WorkerRegistry -> ExecutionRuntime ->
    WorkflowRuntime, PlannerWorker registered with the orchestrator's own
    modules/context/router/memory. use_k42_frontend defaults to False, so
    handle() takes the workflow-runtime branch under test."""
    modules = {"web_search": object()}
    context = context or MagicMock(spec=ContextMemory)
    memory = AsyncMock(spec=UnifiedMemory)
    router = MagicMock()
    router.route = AsyncMock(return_value=RouteResult(answer="wired answer", source="mock"))
    registry = WorkerRegistry()
    registry.register(PlannerWorker, constructor_kwargs={
        "modules": modules, "context_memory": context,
        "model_router": router, "memory": memory})
    execution_runtime = ExecutionRuntime(
        worker_registry=registry, governance=get_governance_kernel(),
        event_stream=get_event_stream())
    workflow_runtime = WorkflowRuntime(
        execution_runtime=execution_runtime, event_stream=get_event_stream())
    return Orchestrator(
        modules, context, router, memory=memory,
        governance=get_governance_kernel(), event_stream=get_event_stream(),
        execution_runtime=execution_runtime, workflow_runtime=workflow_runtime)


def _recording_events(orch):
    seen = []
    real = orch._emit_event

    async def spy(event_type, payload):
        seen.append((event_type, dict(payload)))
        return await real(event_type, payload)

    orch._emit_event = spy
    return seen


async def _handle(orch, query="what is OCBrain?"):
    try:
        return await orch.handle(query)
    finally:
        await orch.close()


def _failing_context():
    ctx = MagicMock(spec=ContextMemory)
    ctx.save = MagicMock(side_effect=RuntimeError(SECRET))  # outside dispatch try/except
    return ctx


# ── the helper ────────────────────────────────────────────────────────────

def test_log_text_and_ref_returns_a_uuid_and_logs_the_text_under_it(caplog):
    log = logging.getLogger("ocbrain.test_text_ref")
    with caplog.at_level(logging.ERROR, logger="ocbrain.test_text_ref"):
        ref = log_text_and_ref(log, "unit context", SECRET)
    uuid.UUID(ref)
    assert "hunter2" not in ref
    assert ref in caplog.text and "unit context" in caplog.text
    assert "hunter2" in caplog.text
    assert log_text_and_ref(log, "unit context", SECRET) != ref  # a fresh ref each time


# ── C1 / C2: the caller boundary ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_pipeline_failure_does_not_reach_the_caller(caplog):
    orch = _orchestrator(_failing_context())
    with caplog.at_level(logging.ERROR):
        answer = await _handle(orch)
    m = ANSWER_RE.fullmatch(answer)
    assert m, answer
    for fragment in ("SECRET-DETAIL", "hunter2", "context.sqlite", "PlannerWorker pipeline error"):
        assert fragment not in answer
    # C2: the real text is in the server log, tagged with the answer's ref.
    assert "hunter2" in caplog.text
    assert m.group(1) in caplog.text


@pytest.mark.asyncio
async def test_the_boundary_redacts_any_worker_failure_not_only_the_planners_format(monkeypatch, caplog):
    """The rule is about what reaches the caller, so it must hold whatever
    string the failing node produced -- not just PlannerWorker's own prefix."""
    async def fake_run(self, context):
        return WorkerResult(success=False, error="RAW node failure /opt/ocbrain/private.db token=abc123")

    monkeypatch.setattr(PlannerWorker, "_run", fake_run)
    with caplog.at_level(logging.ERROR):
        answer = await _handle(_orchestrator())
    m = ANSWER_RE.fullmatch(answer)
    assert m, answer
    assert "private.db" not in answer and "abc123" not in answer
    assert "private.db" in caplog.text and m.group(1) in caplog.text


@pytest.mark.asyncio
async def test_each_failure_gets_its_own_ref():
    a1 = await _handle(_orchestrator(_failing_context()))
    a2 = await _handle(_orchestrator(_failing_context()))
    assert ANSWER_RE.fullmatch(a1) and ANSWER_RE.fullmatch(a2)
    assert a1 != a2


@pytest.mark.asyncio
async def test_a_failing_answer_is_still_a_string_not_an_exception():
    answer = await _handle(_orchestrator(_failing_context()))
    assert isinstance(answer, str)


# ── C3: internal channels unchanged ───────────────────────────────────────

@pytest.mark.asyncio
async def test_the_internal_failure_event_still_carries_the_raw_error():
    orch = _orchestrator(_failing_context())
    events = _recording_events(orch)
    await _handle(orch)
    failed = [p for name, p in events if name == "orchestrator.query_failed"]
    assert len(failed) == 1
    assert "hunter2" in failed[0]["error"]            # unchanged: internal channel
    assert failed[0]["error_type"] == "WorkflowFailure"


# ── C4: the sibling branch is unchanged ───────────────────────────────────

@pytest.mark.asyncio
async def test_unexpected_exception_in_the_workflow_path_still_returns_only_the_class():
    orch = _orchestrator()
    orch._workflow_runtime.execute = AsyncMock(side_effect=ValueError(SECRET))
    answer = await _handle(orch)
    assert answer == "Sorry, I encountered an internal error: ValueError"
    assert "hunter2" not in answer


# ── the success path is untouched ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_successful_workflow_run_is_unchanged():
    answer = await _handle(_orchestrator())
    assert answer == "wired answer"
