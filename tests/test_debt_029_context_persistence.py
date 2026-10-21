"""
tests/test_debt_029_context_persistence.py — DEBT-029 Regression Tests

DEBT-029 regression coverage:
- Mid-transaction entity-insert rollback and cache atomicity.
- Controlled commit failure and rollback-failure fail-closed behavior.
- Privacy-policy preservation.
- Best-effort context-save containment in PlannerWorker, both Orchestrator
  paths, and the streaming helper.
- A real positive-retry WorkflowRuntime execution.
- Genuine pre-persistence failures and caller-safe disclosure.
"""

import logging
import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from core.context import ContextMemory
from core.governance.governance_kernel import get_governance_kernel
from core.runtime.execution_context import ExecutionContext
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workflow.definition import RetryPolicy, WorkflowDefinition, WorkflowNode
from core.workflow.runtime import WorkflowRuntime
from core.workers.planner import PlannerWorker


# ── Test A: SQLite rollback after a later entity insert fails ────────────────

def test_a_sqlite_transaction_rollback(tmp_path, monkeypatch):
    db_file = tmp_path / "test_debt029_rollback.sqlite"
    monkeypatch.setattr("core.context.DB_PATH", db_file)
    ctx = ContextMemory()
    conn = ctx._conn
    trigger = "fail_later_entity_insert"

    try:
        with patch("core.privacy.privacy.can_save_history", return_value=True):
            ctx.save(
                "baseline query", ["knowledge"], "baseline answer",
                {"urls": ["https://baseline.example"]}, scope="baseline-scope",
            )
            baseline_prompt = ctx.format_for_prompt(5, scope="baseline-scope")
            assert "baseline query" in baseline_prompt
            cache_before = dict(ctx._prompt_cache)
            dirty_before = ctx._turns_cache_dirty
            prompt_turn_before = ctx._prompt_cache_turn
            assert dirty_before is False
            assert cache_before

            with ctx._lock:
                conn.execute(
                    f"CREATE TRIGGER {trigger} BEFORE INSERT ON entities "
                    "WHEN NEW.type = 'languages' BEGIN "
                    "SELECT RAISE(FAIL, 'simulated later entity insert error'); END"
                )
                conn.commit()

            with pytest.raises(sqlite3.Error, match="simulated later entity insert error"):
                ctx.save(
                    "failed query sentinel", ["knowledge"], "failed answer sentinel",
                    {
                        "urls": ["https://partially-inserted.example"],
                        "languages": ["python"],
                    },
                    scope="failed-scope",
                )

            # Check cache fields immediately: public reads below may warm them.
            assert ctx._turns_cache_dirty is dirty_before
            assert ctx._prompt_cache == cache_before
            assert ctx._prompt_cache_turn == prompt_turn_before

            with ctx._lock:
                turns = conn.execute(
                    "SELECT query, answer FROM turns ORDER BY id"
                ).fetchall()
                entities = conn.execute(
                    "SELECT type, value FROM entities ORDER BY id"
                ).fetchall()
            assert turns == [("baseline query", "baseline answer")]
            assert entities == [("urls", "https://baseline.example")]

            visible_turns = ctx.last_n(10, scope="baseline-scope")
            assert [(turn.query, turn.answer) for turn in visible_turns] == [
                ("baseline query", "baseline answer")
            ]
            assert "failed query sentinel" not in ctx.format_for_prompt(
                5, scope="baseline-scope"
            )
            assert "https://partially-inserted.example" not in ctx.get_entity("urls")

            with ctx._lock:
                conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                conn.commit()

            ctx.save(
                "successful query", ["knowledge"], "successful answer",
                {"urls": ["https://success.example"]}, scope="success-scope",
            )
            assert ctx._turns_cache_dirty is True
            assert ctx._prompt_cache == {}
            assert ctx._prompt_cache_turn != prompt_turn_before

            with ctx._lock:
                turns = conn.execute(
                    "SELECT query, answer FROM turns ORDER BY id"
                ).fetchall()
                entities = conn.execute(
                    "SELECT type, value FROM entities ORDER BY id"
                ).fetchall()
            assert turns == [
                ("baseline query", "baseline answer"),
                ("successful query", "successful answer"),
            ]
            assert ("urls", "https://success.example") in entities
            assert all("failed query sentinel" not in query for query, _ in turns)

            success_prompt = ctx.format_for_prompt(5, scope="success-scope")
            assert "successful query" in success_prompt
            assert "failed query sentinel" not in success_prompt
    finally:
        try:
            with ctx._lock:
                if ctx._conn is not None:
                    ctx._conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        except sqlite3.Error:
            pass
        if ctx._conn is not None:
            ctx._conn.close()


# ── Test B: PlannerWorker history-save failure ───────────────────────────────

@pytest.mark.asyncio
async def test_b_planner_worker_context_save_failure(caplog):
    query = "What is OCBrain?"
    scope = "exec-planner-save-failure"
    expected_entities = {
        "urls": ["https://planner.example"],
        "languages": ["python"],
        "filenames": ["app.py"],
    }
    parsed = SimpleNamespace(entities=expected_entities)
    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("database is locked")
    invocation_count = 0

    class CountingRouter:
        async def route(self, mod_name, route_query, ctx, scope=""):
            nonlocal invocation_count
            invocation_count += 1
            from core.model_router import RouteResult
            return RouteResult(answer="Capability output answer", source="test")

    planner = PlannerWorker(
        modules={"knowledge": MagicMock()},
        context_memory=failing_ctx,
        model_router=CountingRouter(),
    )
    exec_ctx = ExecutionContext(metadata={"query": query, "execution_id": scope})

    with patch("core.parser.parse", return_value=parsed), \
         patch("core.memory.assembly.context_assembler.assemble_context", AsyncMock(return_value="")), \
         patch("core.classifier_v3.classify", return_value=[{"module": "knowledge"}]), \
         caplog.at_level(logging.WARNING):
        result = await planner._run(exec_ctx)

    assert result.success is True
    assert result.output == "Capability output answer"
    assert result.metadata.get("outcome") == "success"
    assert invocation_count == 1
    failing_ctx.save.assert_called_once_with(
        query, ["knowledge"], "Capability output answer", expected_entities, scope=scope
    )
    assert "database is locked" not in result.output
    assert "database is locked" not in str(result.metadata)
    assert "Context save failed" in caplog.text
    assert query not in caplog.text
    assert "Capability output answer" not in caplog.text


# ── Test C: K4.2 Orchestrator boundary around save failure ───────────────────

@pytest.mark.asyncio
async def test_c_k42_canonical_request_path_save_failure():
    """Boundary test only: WorkflowRuntime returns a mocked successful result."""
    from core.orchestrator import Orchestrator
    from core.workflow.runtime import WorkflowResult

    query = "K4.2 query sentinel"
    execution_id = "exec-k42-save-failure"
    answer_expected = "Computed K4.2 answer sentinel"
    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("controlled disk I/O error")

    mock_wf_runtime = AsyncMock()
    mock_wf_runtime.execute.return_value = WorkflowResult(
        instance_id="inst-1", workflow_id="wf-1", success=True,
        output=answer_expected, node_results={},
    )
    events_emitted = []

    async def mock_emit_event(event_type, payload):
        events_emitted.append((event_type, dict(payload)))

    orch = Orchestrator(
        modules={"knowledge": MagicMock()}, context=failing_ctx,
        router=MagicMock(), memory=AsyncMock(),
        workflow_runtime=mock_wf_runtime, capability_registry=MagicMock(),
        use_k42_frontend=True,
    )
    orch._emit_event = mock_emit_event

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

    try:
        with patch("core.cognitive.intent.load_known_categories", AsyncMock(return_value=[])), \
             patch("core.cognitive.intent.interpret_request", AsyncMock(return_value=[fake_goal])), \
             patch("core.cognitive.planner.plan", AsyncMock(return_value=MagicMock(status="ready_for_compilation", execution_plan=fake_plan))), \
             patch("core.cognitive.compiler.compile", AsyncMock(return_value=fake_compilation)), \
             patch("core.shadow.shadow_learner.shadow_learner.record_interaction"):
            answer = await orch.handle(query, execution_id=execution_id)
    finally:
        await orch.close()

    assert answer == answer_expected
    mock_wf_runtime.execute.assert_awaited_once()
    failing_ctx.save.assert_called_once_with(
        query, ["llm_completion"], answer_expected, {}, scope=execution_id
    )
    event_types = [name for name, _ in events_emitted]
    assert event_types.count("orchestrator.query_completed") == 1
    assert event_types.count("orchestrator.query_failed") == 0


# ── Test D: Legacy Orchestrator compatibility path ────────────────────────────

@pytest.mark.asyncio
async def test_d_legacy_orchestrator_compatibility_path_save_failure():
    from core.orchestrator import Orchestrator
    from core.model_router import RouteResult

    query = "Legacy query sentinel"
    execution_id = "exec-legacy-save-failure"
    expected_entities = {
        "urls": ["https://legacy.example"],
        "languages": ["python"],
        "filenames": ["legacy.py"],
    }
    parsed = SimpleNamespace(entities=expected_entities)
    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("controlled database failure")
    mock_router = AsyncMock()
    mock_router.route.return_value = RouteResult(answer="Legacy answer sentinel", source="test")
    orch = Orchestrator(
        modules={"knowledge": MagicMock()}, context=failing_ctx,
        router=mock_router, memory=AsyncMock(), workflow_runtime=None,
        use_k42_frontend=False,
    )
    try:
        with patch("core.parser.parse", return_value=parsed), \
             patch("core.classifier_v3.classify", return_value=[{"module": "knowledge"}]), \
             patch("core.shadow.shadow_learner.shadow_learner.record_interaction"):
            answer = await orch.handle(query, execution_id=execution_id)
    finally:
        await orch.close()

    assert answer == "Legacy answer sentinel"
    assert mock_router.route.call_count == 1
    failing_ctx.save.assert_called_once_with(
        query, ["knowledge"], answer, expected_entities, scope=execution_id
    )


# ── Test E: Streaming helper containment and safe diagnostics ─────────────────

@pytest.mark.asyncio
async def test_e_streaming_save_failure_containment(caplog):
    from interface.api import _save_context_background

    query = "stream query sentinel"
    answer = "stream answer sentinel"
    execution_id = "exec-stream-save-failure"
    failing_orch = MagicMock()
    failing_orch.context.save.side_effect = sqlite3.OperationalError("database locked")

    with caplog.at_level(logging.WARNING, logger="interface.api"):
        await _save_context_background(
            failing_orch, query, ["coding"], answer, execution_id
        )

    failing_orch.context.save.assert_called_once_with(
        query, ["coding"], answer, scope=execution_id
    )
    assert "Context save failed" in caplog.text
    assert execution_id in caplog.text
    assert "OperationalError" in caplog.text
    assert query not in caplog.text
    assert answer not in caplog.text
    assert "database locked" not in caplog.text


# ── Test F: Real retry-enabled WorkflowRuntime coverage ──────────────────────

@pytest.mark.asyncio
async def test_f_defensive_retry_enabled_workflow_save_failure():
    query = "Defensive retry query"
    execution_id = "exec-retry-save-failure"
    scope = execution_id
    expected_entities = {
        "urls": ["https://retry.example"],
        "languages": ["python"],
        "filenames": ["retry.py"],
    }
    parsed = SimpleNamespace(entities=expected_entities)
    failing_ctx = MagicMock()
    failing_ctx.save.side_effect = sqlite3.OperationalError("controlled locked database")

    capability_invocations = 0
    class CountingRouter:
        async def route(self, mod_name, route_query, ctx, scope=""):
            nonlocal capability_invocations
            capability_invocations += 1
            from core.model_router import RouteResult
            return RouteResult(answer="Retry-enabled answer sentinel", source="test")

    event_stream = MagicMock()
    event_stream.append = AsyncMock()
    event_stream.create_checkpoint = AsyncMock()
    # EventStream subscribe/unsubscribe are synchronous APIs; using AsyncMock
    # here causes unawaited-coroutine warnings from the real runtime stack.
    event_stream.subscribe = MagicMock()
    event_stream.unsubscribe = MagicMock()
    registry = WorkerRegistry()
    registry.register(PlannerWorker, constructor_kwargs={
        "modules": {"knowledge": MagicMock()},
        "context_memory": failing_ctx,
        "model_router": CountingRouter(),
    })
    execution_runtime = ExecutionRuntime(
        worker_registry=registry,
        governance=get_governance_kernel(),
        event_stream=event_stream,
    )
    invoke_calls = []
    real_invoke = execution_runtime.invoke

    async def count_real_invoke(*args, **kwargs):
        invoke_calls.append((args, kwargs))
        return await real_invoke(*args, **kwargs)

    execution_runtime.invoke = count_real_invoke
    workflow_runtime = WorkflowRuntime(
        execution_runtime=execution_runtime,
        event_stream=event_stream,
    )
    definition = WorkflowDefinition(
        workflow_id="debt-029-positive-retry-test",
        nodes=[WorkflowNode(
            node_id="planner",
            worker_type="PlannerWorker",
            retry_policy=RetryPolicy(
                max_retries=2, backoff_seconds=0.0, max_backoff_seconds=0.0
            ),
        )],
        edges=[],
        entry_node="planner",
    )

    with patch("core.parser.parse", return_value=parsed), \
         patch("core.memory.assembly.context_assembler.assemble_context", AsyncMock(return_value="")), \
         patch("core.classifier_v3.classify", return_value=[{"module": "knowledge"}]):
        result = await workflow_runtime.execute(
            definition, query=query, metadata={"execution_id": execution_id}
        )

    assert result.success is True
    assert result.output == "Retry-enabled answer sentinel"
    assert result.node_results["planner"].success is True
    assert result.node_results["planner"].output == result.output
    assert len(invoke_calls) == 1
    assert capability_invocations == 1
    failing_ctx.save.assert_called_once_with(
        query, ["knowledge"], result.output, expected_entities, scope=scope
    )


# ── Test G: Genuine pre-persistence errors remain failures ────────────────────

@pytest.mark.asyncio
async def test_g_negative_control_genuine_execution_failures_still_fail():
    query = "Negative control query"
    parsed = SimpleNamespace(entities={"urls": [], "languages": [], "filenames": []})
    ctx_mock = MagicMock()
    ctx_mock.save = MagicMock()

    class CountingRouter:
        async def route(self, mod_name, route_query, ctx, scope=""):
            from core.model_router import RouteResult
            return RouteResult(answer="Should not be merged", source="test")

    planner = PlannerWorker(
        modules={"knowledge": MagicMock()},
        context_memory=ctx_mock,
        model_router=CountingRouter(),
    )
    with patch("core.parser.parse", return_value=parsed), \
         patch("core.memory.assembly.context_assembler.assemble_context", AsyncMock(return_value="")), \
         patch("core.classifier_v3.classify", return_value=[{"module": "knowledge"}]), \
         patch("core.merger.merge", AsyncMock(side_effect=RuntimeError("controlled merger failure"))):
        result = await planner._run(ExecutionContext(metadata={"query": query}))

    assert result.success is False
    assert "controlled merger failure" in result.error
    ctx_mock.save.assert_not_called()


# ── Test H: commit failure rollback and cache preservation ────────────────────

def test_h_commit_failure_rolls_back_uncommitted_turn_and_entities(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "commit_failure.sqlite")
    ctx = ContextMemory()
    real_conn = ctx._conn

    class FailFirstCommit:
        def __init__(self, connection):
            self.connection = connection
            self.fail_next = False

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def commit(self):
            if self.fail_next:
                self.fail_next = False
                raise sqlite3.OperationalError("controlled commit failure")
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

        def close(self):
            return self.connection.close()

    proxy = FailFirstCommit(real_conn)
    try:
        with patch("core.privacy.privacy.can_save_history", return_value=True):
            ctx.save(
                "baseline commit query", ["knowledge"], "baseline commit answer",
                {"urls": ["https://commit-baseline.example"]}, scope="commit-baseline",
            )
            ctx.format_for_prompt(5, scope="commit-baseline")
            cache_before = dict(ctx._prompt_cache)
            dirty_before = ctx._turns_cache_dirty
            prompt_turn_before = ctx._prompt_cache_turn

            ctx._conn = proxy
            proxy.fail_next = True
            with pytest.raises(sqlite3.OperationalError, match="controlled commit failure"):
                ctx.save(
                    "failed commit query sentinel", ["knowledge"], "failed commit answer sentinel",
                    {"urls": ["https://commit-failed.example"]}, scope="commit-failed",
                )

            assert ctx._turns_cache_dirty is dirty_before
            assert ctx._prompt_cache == cache_before
            assert ctx._prompt_cache_turn == prompt_turn_before
            turns = real_conn.execute("SELECT query, answer FROM turns ORDER BY id").fetchall()
            entities = real_conn.execute("SELECT type, value FROM entities ORDER BY id").fetchall()
            assert turns == [("baseline commit query", "baseline commit answer")]
            assert entities == [("urls", "https://commit-baseline.example")]

            ctx.save(
                "post-commit-recovery query", ["knowledge"], "post-commit-recovery answer",
                {"urls": ["https://commit-recovered.example"]}, scope="commit-recovered",
            )
            turns = real_conn.execute("SELECT query, answer FROM turns ORDER BY id").fetchall()
            entities = real_conn.execute("SELECT type, value FROM entities ORDER BY id").fetchall()
            assert turns == [
                ("baseline commit query", "baseline commit answer"),
                ("post-commit-recovery query", "post-commit-recovery answer"),
            ]
            assert ("urls", "https://commit-recovered.example") in entities
            assert all("failed commit query sentinel" not in query for query, _ in turns)
    finally:
        ctx._conn = real_conn
        real_conn.close()


# ── Test I: failed rollback disables the unusable connection ──────────────────

@pytest.mark.parametrize("close_fails", [False, True])
def test_i_rollback_failure_fails_closed_and_preserves_primary_error(
    tmp_path, monkeypatch, caplog, close_fails
):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / f"rollback_failure_{close_fails}.sqlite")
    ctx = ContextMemory()
    real_conn = ctx._conn
    trigger = "fail_rollback_entity_insert"

    class FailRollbackProxy:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def rollback(self):
            raise sqlite3.OperationalError("secondary rollback diagnostic sentinel")

        def close(self):
            if close_fails:
                raise sqlite3.OperationalError("secondary close diagnostic sentinel")
            return self.connection.close()

    proxy = FailRollbackProxy(real_conn)
    try:
        with patch("core.privacy.privacy.can_save_history", return_value=True):
            ctx.save(
                "rollback baseline query", ["knowledge"], "rollback baseline answer",
                {"urls": ["https://rollback-baseline.example"]}, scope="rollback-baseline",
            )
            with ctx._lock:
                real_conn.execute(
                    f"CREATE TRIGGER {trigger} BEFORE INSERT ON entities "
                    "WHEN NEW.type = 'languages' BEGIN "
                    "SELECT RAISE(FAIL, 'primary entity insert failure sentinel'); END"
                )
                real_conn.commit()
            ctx._conn = proxy

            with caplog.at_level(logging.ERROR, logger="core.context"):
                with pytest.raises(sqlite3.Error, match="primary entity insert failure sentinel"):
                    ctx.save(
                        "rollback failed query sentinel", ["knowledge"], "rollback failed answer sentinel",
                        {"urls": ["https://rollback-partial.example"], "languages": ["python"]},
                        scope="rollback-failed",
                    )

            assert ctx._conn is None
            assert "Rollback failed after save error" in caplog.text
            assert "OperationalError" in caplog.text
            assert "secondary rollback diagnostic sentinel" not in caplog.text
            assert "rollback failed query sentinel" not in caplog.text
            assert "rollback failed answer sentinel" not in caplog.text
            if close_fails:
                assert "Failed to close unusable SQLite connection" in caplog.text

            with pytest.raises(sqlite3.ProgrammingError, match="disabled after rollback failure"):
                ctx.save("later query", ["knowledge"], "later answer")

            # Release the real connection if the simulated close also failed.
            try:
                real_conn.close()
            except sqlite3.Error:
                pass

            reopened = ContextMemory()
            try:
                with reopened._lock:
                    rows = reopened._conn.execute(
                        "SELECT query, answer FROM turns ORDER BY id"
                    ).fetchall()
                    entities = reopened._conn.execute(
                        "SELECT type, value FROM entities ORDER BY id"
                    ).fetchall()
                assert rows == [("rollback baseline query", "rollback baseline answer")]
                assert entities == [("urls", "https://rollback-baseline.example")]
                reopened.save(
                    "fresh connection query", ["knowledge"], "fresh connection answer",
                    {"urls": ["https://fresh-connection.example"]}, scope="fresh-connection",
                )
                assert reopened.last_n(10, scope="fresh-connection")[-1].query == "fresh connection query"
            finally:
                reopened._conn.close()
    finally:
        if ctx._conn is not None:
            try:
                ctx._conn.close()
            except sqlite3.Error:
                pass
        try:
            real_conn.close()
        except sqlite3.Error:
            pass

# ── Test J: history-saving privacy guard remains authoritative ───────────────

def test_j_privacy_guard_still_skips_history_persistence(tmp_path, monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH", tmp_path / "privacy_disabled.sqlite")
    ctx = ContextMemory()
    try:
        cache_before = dict(ctx._prompt_cache)
        dirty_before = ctx._turns_cache_dirty
        prompt_turn_before = ctx._prompt_cache_turn
        with patch("core.privacy.privacy.can_save_history", return_value=False):
            ctx.save(
                "privacy-disabled query", ["knowledge"], "privacy-disabled answer",
                {"urls": ["https://privacy-disabled.example"]},
                scope="privacy-disabled",
            )
        with ctx._lock:
            turns = ctx._conn.execute("SELECT query, answer FROM turns").fetchall()
            entities = ctx._conn.execute("SELECT type, value FROM entities").fetchall()
        assert turns == []
        assert entities == []
        assert ctx._prompt_cache == cache_before
        assert ctx._turns_cache_dirty is dirty_before
        assert ctx._prompt_cache_turn == prompt_turn_before
    finally:
        ctx._conn.close()
