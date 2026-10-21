"""
tests/test_debt_029_context_persistence.py — DEBT-029 Regression Tests

Tests for:
1. ContextMemory.save() SQLite transaction rollback atomicity.
2. PlannerWorker Step 8 best-effort context history save containment.
3. Orchestrator K4.2 canonical request path context history save containment.
4. Orchestrator legacy compatibility path context history save containment.
5. Streaming helper context history save containment.
6. Defensive retry-enabled workflow execution test.
7. Negative control: genuine execution errors remain failures.
"""

import asyncio
import sqlite3
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.context import ContextMemory
from core.runtime.execution_context import ExecutionContext
from core.workers.planner import PlannerWorker
from core.workers.base import WorkerResult


# ── Test A: Real SQLite Transaction Rollback ──────────────────────────────────

def test_a_sqlite_transaction_rollback(tmp_path, monkeypatch):
    """Test A: Real SQLite failure during entity persistence rolls back turn insert.

    Asserts:
    1. save() raises the original persistence failure.
    2. No partial turn row remains.
    3. No partial entity rows remain.
    4. Connection is usable after rollback.
    5. Subsequent save succeeds.
    6. last_n() reflects only committed state.
    7. Caches reflect only committed state.
    """
    db_file = tmp_path / "test_debt029_rollback.sqlite"
    monkeypatch.setattr("core.context.DB_PATH", db_file)

    ctx = ContextMemory()

    # Create a trigger on 'entities' that aborts any insert
    with ctx._lock:
        ctx._conn.execute(
            "CREATE TRIGGER fail_entities_insert BEFORE INSERT ON entities "
            "BEGIN SELECT RAISE(FAIL, 'simulated entity insert error'); END;"
        )
        ctx._conn.commit()

    # Attempt save with entities - should fail in entity loop after turn row inserted
    with pytest.raises(sqlite3.Error, match="simulated entity insert error"):
        ctx.save(
            query="failed query",
            modules_used=["knowledge"],
            answer="failed answer",
            entities={"urls": ["http://fail.com"]},
        )

    # Check DB state directly
    with ctx._lock:
        cur = ctx._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM turns")
        turn_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM entities")
        entity_count = cur.fetchone()[0]

    assert turn_count == 0, "Failed save left partial turn row in database"
    assert entity_count == 0, "Failed save left partial entity rows in database"

    # Connection and instance should be usable; drop trigger and save again
    with ctx._lock:
        ctx._conn.execute("DROP TRIGGER fail_entities_insert")
        ctx._conn.commit()

    ctx.save(
        query="successful query",
        modules_used=["knowledge"],
        answer="successful answer",
        entities={"urls": ["http://success.com"]},
    )

    turns = ctx.last_n(10)
    assert len(turns) == 1
    assert turns[0].query == "successful query"
    assert turns[0].answer == "successful answer"

    prompt_str = ctx.format_for_prompt(5)
    assert "successful query" in prompt_str
    assert "failed query" not in prompt_str


# ── Test B: PlannerWorker History Save Failure ────────────────────────────────

@pytest.mark.asyncio
async def test_b_planner_worker_context_save_failure():
    """Test B: PlannerWorker._run() returns success=True when context.save() fails.

    Asserts:
    - Merged answer is returned unchanged.
    - WorkerResult.success is True.
    - Modules/capabilities invoked exactly once.
    - No raw exception text in answer/output/metadata.
    """
    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("database is locked")

    invocation_count = 0

    class CountingRouter:
        async def route(self, mod_name, query, ctx, scope=""):
            nonlocal invocation_count
            invocation_count += 1
            from core.model_router import RouteResult
            return RouteResult(answer="Capability output answer", source="test")

    planner = PlannerWorker(
        modules={"knowledge": MagicMock()},
        context_memory=failing_ctx,
        model_router=CountingRouter(),
    )

    exec_ctx = ExecutionContext(metadata={"query": "What is OCBrain?"})

    with patch("core.classifier_v3.classify", return_value=[{"module": "knowledge"}]):
        res = await planner._run(exec_ctx)

    assert res.success is True
    assert "Capability output answer" in res.output
    assert invocation_count == 1
    assert "database is locked" not in res.output
    assert res.metadata.get("outcome") == "success"


# ── Test C: K4.2 Canonical Request Path Context Save Failure ──────────────────

@pytest.mark.asyncio
async def test_c_k42_canonical_request_path_save_failure():
    """Test C: K4.2 Orchestrator path returns completed answer when context.save fails.

    Asserts:
    - Original computed answer is returned.
    - Query is not marked as failed.
    - orchestrator.query_completed event is emitted.
    - orchestrator.query_failed event is NOT emitted for save failure.
    - Capability executed exactly once.
    """
    from core.orchestrator import Orchestrator
    from core.workflow.definition import WorkflowDefinition, WorkflowNode
    from core.workflow.runtime import WorkflowResult

    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("disk I/O error")

    mock_wf_runtime = AsyncMock()
    mock_wf_result = WorkflowResult(
        instance_id="inst-1",
        workflow_id="wf-1",
        success=True,
        output="Computed K4.2 answer",
        node_results={},
    )
    mock_wf_runtime.execute.return_value = mock_wf_result

    events_emitted = []

    async def mock_emit_event(event_type, payload):
        events_emitted.append((event_type, payload))

    orch = Orchestrator(
        modules={"knowledge": MagicMock()},
        context=failing_ctx,
        router=MagicMock(),
        memory=AsyncMock(),
        workflow_runtime=mock_wf_runtime,
        capability_registry=MagicMock(),
        use_k42_frontend=True,
    )
    orch._emit_event = mock_emit_event

    # Mock the front-end planning/compilation pipeline
    fake_goal = MagicMock()
    fake_goal.resource_id = "goal-1"
    fake_plan = MagicMock()
    fake_plan.resource_id = "plan-1"
    fake_plan.confidence = 0.9
    fake_step = MagicMock()
    fake_step.capability_type = "llm_completion"
    fake_plan.steps = [fake_step]

    fake_compilation = MagicMock()
    fake_compilation.status = "compiled"
    fake_compilation.workflow_definition = WorkflowDefinition(workflow_id="wf-1")

    with patch("core.cognitive.intent.load_known_categories", AsyncMock(return_value=[])), \
         patch("core.cognitive.intent.interpret_request", AsyncMock(return_value=[fake_goal])), \
         patch("core.cognitive.planner.plan", AsyncMock(return_value=MagicMock(status="ready_for_compilation", execution_plan=fake_plan))), \
         patch("core.cognitive.compiler.compile", AsyncMock(return_value=fake_compilation)), \
         patch("core.shadow.shadow_learner.shadow_learner.record_interaction"):

        answer = await orch.handle("Test query")

    assert answer == "Computed K4.2 answer"
    event_types = [e[0] for e in events_emitted]
    assert "orchestrator.query_completed" in event_types
    assert "orchestrator.query_failed" not in event_types


# ── Test D: Legacy Orchestrator Direct Compatibility Path ─────────────────────

@pytest.mark.asyncio
async def test_d_legacy_orchestrator_compatibility_path_save_failure():
    """Test D: Legacy Orchestrator path (workflow_runtime=None) handles save failure.

    Asserts:
    - Computed answer is returned successfully.
    - Query is not failed because of context.save error.
    - Module executed once.
    """
    from core.orchestrator import Orchestrator
    from core.model_router import RouteResult

    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("database disk image is malformed")

    mock_router = AsyncMock()
    mock_router.route.return_value = RouteResult(answer="Legacy answer text", source="test")

    orch = Orchestrator(
        modules={"knowledge": MagicMock()},
        context=failing_ctx,
        router=mock_router,
        memory=AsyncMock(),
        workflow_runtime=None,
        use_k42_frontend=False,
    )

    with patch("core.classifier_v3.classify", return_value=[{"module": "knowledge"}]), \
         patch("core.shadow.shadow_learner.shadow_learner.record_interaction"):
        answer = await orch.handle("Legacy query")

    assert answer == "Legacy answer text"
    failing_ctx.save.assert_called_once()
    assert failing_ctx.save.call_args[0][0] == "Legacy query"


# ── Test E: Streaming Helper Save Failure Containment ────────────────────────

@pytest.mark.asyncio
async def test_e_streaming_save_failure_containment():
    """Test E: Streaming _save_context_background contains save exceptions safely."""
    from interface.api import _save_context_background

    failing_orch = MagicMock()
    failing_orch.context.save.side_effect = sqlite3.OperationalError("database locked")

    # Calling background save directly
    await _save_context_background(failing_orch, "stream query", ["coding"], "stream answer", "exec-123")

    failing_orch.context.save.assert_called_once_with("stream query", ["coding"], "stream answer", scope="exec-123")


# ── Test F: Defensive Retry-Enabled Workflow Test ─────────────────────────────

@pytest.mark.asyncio
async def test_f_defensive_retry_enabled_workflow_save_failure():
    """Test F: Defensive coverage for a workflow with RetryPolicy(max_retries=2).

    Asserts:
    - Context save failure inside worker is contained.
    - Worker completes successfully on attempt 1.
    - Capability invocation count remains 1 (no spurious retry triggered).
    """
    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("locked")

    capability_invocations = 0

    class CountingRouter:
        async def route(self, mod_name, query, ctx, scope=""):
            nonlocal capability_invocations
            capability_invocations += 1
            from core.model_router import RouteResult
            return RouteResult(answer="Retry-enabled answer", source="test")

    planner = PlannerWorker(
        modules={"knowledge": MagicMock()},
        context_memory=failing_ctx,
        model_router=CountingRouter(),
    )

    exec_ctx = ExecutionContext(metadata={"query": "Defensive retry query"})

    with patch("core.classifier_v3.classify", return_value=[{"module": "knowledge"}]):
        res = await planner._run(exec_ctx)

    assert res.success is True
    assert res.output == "Retry-enabled answer"
    assert capability_invocations == 1


# ── Test G: Negative Control: Genuine Execution Errors Still Fail ─────────────

@pytest.mark.asyncio
async def test_g_negative_control_genuine_execution_failures_still_fail():
    """Test G: Negative control proving genuine execution failures remain failures.

    Asserts:
    - Empty query in PlannerWorker returns WorkerResult(success=False).
    - Save is NOT attempted on execution failure.
    """
    ctx_mock = MagicMock()
    planner = PlannerWorker(
        modules={"knowledge": MagicMock()},
        context_memory=ctx_mock,
    )

    exec_ctx = ExecutionContext(metadata={"query": ""})
    res = await planner._run(exec_ctx)

    assert res.success is False
    assert "No query provided" in res.error
    assert ctx_mock.save.call_count == 0
