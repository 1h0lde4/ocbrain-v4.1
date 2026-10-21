"""DEBT-029 tests: atomicity, best-effort persistence, and retry isolation."""
import logging
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.context import ContextMemory
from core.events.event_stream import get_event_stream
from core.governance.governance_kernel import get_governance_kernel
from core.model_router import RouteResult
from core.runtime.execution_context import ExecutionContext
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workers.planner import PlannerWorker
from core.workflow.definition import RetryPolicy, WorkflowDefinition, WorkflowNode
from core.workflow.runtime import WorkflowRuntime

Q="QUERY_PRIVATE_SENTINEL"
A="ANSWER_PRIVATE_SENTINEL"
S="EXECUTION_PRIVATE_SENTINEL"
E="EXCEPTION_TEXT_MUST_NOT_BE_LOGGED"

def _cache(ctx):
    return (dict(ctx._prompt_cache),ctx._prompt_cache_turn,ctx._turns_cache_dirty,
            {k:list(v) for k,v in ctx._long_term_memories_by_scope.items()},
            dict(ctx._long_term_memories_string_by_scope))

def _parsed():
    return SimpleNamespace(entities={"urls":[],"languages":[],"filenames":[]})

def _patch_pipeline(answer):
    return (
        patch("core.parser.parse",return_value=_parsed()),
        patch("core.memory.assembly.context_assembler.assemble_context",new=AsyncMock(return_value="")),
        patch("core.classifier_v3.classify",return_value=[{"module":"knowledge"}]),
        patch("core.merger.merge",new=AsyncMock(return_value=answer)),
    )

# A: fail on a later entity insert, verify total rollback and cache invariance.
def test_a_sqlite_late_entity_failure_rolls_back_all_writes_and_caches(tmp_path,monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH",tmp_path/"atomicity.sqlite")
    ctx=ContextMemory()
    try:
        ctx.save("baseline",["knowledge"],"baseline answer",{"urls":["base-url"]},scope="scope-a")
        ctx.last_n(10,scope="scope-a"); ctx.get_entity("urls")
        prompt=ctx.format_for_prompt(5,scope="scope-a"); before=_cache(ctx)
        with ctx._lock:
            conn=ctx._require_connection()
            conn.execute("CREATE TRIGGER fail_language BEFORE INSERT ON entities WHEN NEW.type='languages' BEGIN SELECT RAISE(ABORT,'PRIMARY_ENTITY_INSERT_SENTINEL'); END")
            conn.commit()
        with pytest.raises(sqlite3.IntegrityError,match="PRIMARY_ENTITY_INSERT_SENTINEL"):
            ctx.save("failed query",["knowledge"],"failed answer",
                     {"urls":["url-must-rollback"],"languages":["lang-must-rollback"]},scope="scope-a")
        assert _cache(ctx)==before
        with ctx._lock:
            conn=ctx._require_connection()
            assert conn.execute("SELECT COUNT(*) FROM turns WHERE query='failed query'").fetchone()[0]==0
            assert conn.execute("SELECT COUNT(*) FROM entities WHERE value IN (?,?)",("url-must-rollback","lang-must-rollback")).fetchone()[0]==0
        assert ctx.format_for_prompt(5,scope="scope-a")==prompt
        with ctx._lock:
            conn=ctx._require_connection(); conn.execute("DROP TRIGGER fail_language"); conn.commit()
        ctx.save("success",["knowledge"],"success answer",{"urls":["new-url"]},scope="scope-a")
        assert [t.query for t in ctx.last_n(10,scope="scope-a")]==["baseline","success"]
        assert ctx.get_entity("urls")==["new-url","base-url"]
    finally:
        if ctx._conn is not None: ctx._conn.close()

# B: PlannerWorker's save failure is non-blocking and sanitized.
@pytest.mark.asyncio
async def test_b_planner_save_failure_preserves_answer_and_logs_only_type(caplog):
    ctx=MagicMock(spec=ContextMemory)
    ctx.save.side_effect=sqlite3.OperationalError(f"{E}::{Q}::{A}::{S}")
    calls=0
    class Router:
        async def route(self,*args,**kwargs):
            nonlocal calls
            calls+=1
            return RouteResult(answer="router answer",source="test")
    worker=PlannerWorker(modules={"knowledge":MagicMock()},context_memory=ctx,model_router=Router())
    p1,p2,p3,p4=_patch_pipeline(A)
    with caplog.at_level(logging.WARNING),p1,p2,p3,p4:
        result=await worker._run(ExecutionContext(metadata={"query":Q,"execution_id":S}))
    assert result.success and result.output==A and result.metadata["outcome"]=="success"
    assert calls==1 and ctx.save.call_count==1
    for secret in (E,Q,A,S): assert secret not in caplog.text
    assert "OperationalError" in caplog.text

# C: K4.2 boundary; WorkflowRuntime is deliberately mocked (not a worker-level test).
@pytest.mark.asyncio
async def test_c_k42_orchestrator_save_failure_keeps_mocked_success(caplog):
    from core.orchestrator import Orchestrator
    from core.workflow.runtime import WorkflowResult
    ctx=MagicMock(spec=ContextMemory); ctx.save.side_effect=sqlite3.OperationalError(f"{E}::{Q}::{A}::{S}")
    runtime=AsyncMock()
    runtime.execute.return_value=WorkflowResult(instance_id="i",workflow_id="w",success=True,output=A,node_results={})
    events=[]
    async def emit(kind,payload): events.append((kind,payload))
    orch=Orchestrator(modules={"knowledge":MagicMock()},context=ctx,router=MagicMock(),
       memory=AsyncMock(),workflow_runtime=runtime,capability_registry=MagicMock(),use_k42_frontend=True)
    orch._emit_event=emit
    goal=MagicMock(resource_id="goal")
    plan=MagicMock(resource_id="plan",confidence=0.9,steps=[MagicMock(capability_type="llm_completion")])
    compiled=MagicMock(status="compiled")
    compiled.workflow_definition=WorkflowDefinition(workflow_id="w")
    with patch("core.cognitive.intent.load_known_categories",AsyncMock(return_value=[])), \
         patch("core.cognitive.intent.interpret_request",AsyncMock(return_value=[goal])), \
         patch("core.cognitive.planner.plan",AsyncMock(return_value=MagicMock(status="ready_for_compilation",execution_plan=plan))), \
         patch("core.cognitive.compiler.compile",AsyncMock(return_value=compiled)), \
         patch("core.shadow.shadow_learner.shadow_learner.record_interaction"),caplog.at_level(logging.WARNING):
        answer=await orch.handle(Q,execution_id=S)
    assert answer==A
    runtime.execute.assert_awaited_once()
    types=[kind for kind,_ in events]
    assert "orchestrator.query_completed" in types and "orchestrator.query_failed" not in types
    for secret in (E,Q,A,S): assert secret not in caplog.text
    assert "OperationalError" in caplog.text

# D: Legacy Orchestrator path also contains persistence failure.
@pytest.mark.asyncio
async def test_d_legacy_orchestrator_save_failure_is_non_blocking_and_sanitized(caplog):
    from core.orchestrator import Orchestrator
    ctx=MagicMock(spec=ContextMemory); ctx.save.side_effect=sqlite3.OperationalError(f"{E}::{Q}::{A}::{S}")
    router=MagicMock(); router.route=AsyncMock(return_value=RouteResult(answer=A,source="test"))
    orch=Orchestrator(modules={"knowledge":MagicMock()},context=ctx,router=router,
      memory=AsyncMock(),workflow_runtime=None,use_k42_frontend=False)
    with patch("core.classifier_v3.classify",return_value=[{"module":"knowledge"}]), \
         patch("core.parser.parse",return_value=_parsed()), \
         patch("core.shadow.shadow_learner.shadow_learner.record_interaction"),caplog.at_level(logging.WARNING):
        answer=await orch.handle(Q,execution_id=S)
    assert answer==A and ctx.save.call_count==1 and router.route.await_count==1
    for secret in (E,Q,A,S): assert secret not in caplog.text
    assert "OperationalError" in caplog.text

# E: SSE background persistence has safe observability, rather than silent pass.
@pytest.mark.asyncio
async def test_e_streaming_save_failure_logs_type_only(caplog):
    from interface.api import _save_context_background
    orch=MagicMock(); orch.context.save.side_effect=sqlite3.OperationalError(f"{E}::{Q}::{A}::{S}")
    with caplog.at_level(logging.WARNING):
        await _save_context_background(orch,Q,["knowledge"],A,S)
    orch.context.save.assert_called_once_with(Q,["knowledge"],A,scope=S)
    for secret in (E,Q,A,S): assert secret not in caplog.text
    assert "OperationalError" in caplog.text

# F: real runtime path, with positive retries configured and one capability call.
@pytest.mark.asyncio
async def test_f_real_retry_enabled_workflow_does_not_retry_persistence_failure(caplog):
    ctx=MagicMock(spec=ContextMemory); ctx.save.side_effect=sqlite3.OperationalError(f"{E}::{Q}::{A}::{S}")
    calls=0
    class Router:
        async def route(self,*args,**kwargs):
            nonlocal calls
            calls+=1
            return RouteResult(answer="router answer",source="test")
    registry=WorkerRegistry()
    registry.register(PlannerWorker,constructor_kwargs={"modules":{"knowledge":MagicMock()},
      "context_memory":ctx,"model_router":Router(),"memory":None})
    stream=get_event_stream()
    execution=ExecutionRuntime(registry,governance=get_governance_kernel(),event_stream=stream)
    workflow=WorkflowRuntime(execution,event_stream=stream)
    definition=WorkflowDefinition(workflow_id="debt029-retry",name="retry-test",
      nodes=[WorkflowNode(node_id="planner",worker_type="PlannerWorker",
       retry_policy=RetryPolicy(max_retries=2,backoff_seconds=0,max_backoff_seconds=0))],
      edges=[],entry_node="planner")
    p1,p2,p3,p4=_patch_pipeline(A)
    with caplog.at_level(logging.WARNING),p1,p2,p3,p4:
        result=await workflow.execute(definition,query=Q,metadata={"execution_id":S})
    assert result.success and result.output==A and result.node_results["planner"].success
    assert calls==1 and ctx.save.call_count==1
    for secret in (E,Q,A,S): assert secret not in caplog.text
    assert "OperationalError" in caplog.text

# G: a genuine pre-persistence failure remains a pipeline failure.
@pytest.mark.asyncio
async def test_g_genuine_merger_failure_is_not_swallowed():
    ctx=MagicMock(spec=ContextMemory)
    router=MagicMock(); router.route=AsyncMock(return_value=RouteResult(answer="result",source="test"))
    worker=PlannerWorker(modules={"knowledge":MagicMock()},context_memory=ctx,model_router=router)
    p1,p2,p3,_=_patch_pipeline("unused")
    p4=patch("core.merger.merge",new=AsyncMock(side_effect=RuntimeError("MERGER_PIPELINE_FAILURE_SENTINEL")))
    with p1,p2,p3,p4:
        result=await worker._run(ExecutionContext(metadata={"query":Q}))
    assert not result.success and "MERGER_PIPELINE_FAILURE_SENTINEL" in result.error
    ctx.save.assert_not_called()

# H: commit failure rolls back rows and leaves cache untouched; retry can succeed.
def test_h_commit_failure_rolls_back_and_allows_same_instance_recovery(tmp_path,monkeypatch):
    monkeypatch.setattr("core.context.DB_PATH",tmp_path/"commit.sqlite")
    ctx=ContextMemory(); real=ctx._conn
    class Proxy:
        def __init__(self): self.fail=True
        def cursor(self): return real.cursor()
        def commit(self):
            if self.fail: raise sqlite3.OperationalError("COMMIT_FAILURE_SENTINEL")
            real.commit()
        def rollback(self): real.rollback()
        def close(self): real.close()
    proxy=Proxy()
    try:
        ctx.save("baseline",["x"],"answer",{"urls":["base-url"]}); ctx.format_for_prompt()
        before=_cache(ctx); ctx._conn=proxy
        with pytest.raises(sqlite3.OperationalError,match="COMMIT_FAILURE_SENTINEL"):
            ctx.save("partial",["x"],"answer",{"urls":["partial-url"]})
        assert _cache(ctx)==before
        assert real.execute("SELECT COUNT(*) FROM turns WHERE query='partial'").fetchone()[0]==0
        assert real.execute("SELECT COUNT(*) FROM entities WHERE value='partial-url'").fetchone()[0]==0
        proxy.fail=False; ctx.save("recovered",["x"],"answer")
        assert [t.query for t in ctx.last_n(10)]==["baseline","recovered"]
    finally:
        real.close()

# I: rollback/close failure must not leak exception text or reuse disabled conn.
@pytest.mark.parametrize("close_fails",[False,True],ids=["close-ok","close-fails"])
def test_i_rollback_failure_disables_reads_and_writes_and_redacts(caplog,tmp_path,monkeypatch,close_fails):
    path=tmp_path/f"rollback-{close_fails}.sqlite"
    monkeypatch.setattr("core.context.DB_PATH",path)
    ctx=ContextMemory(); real=ctx._conn
    class Proxy:
        def cursor(self): return real.cursor()
        def rollback(self): raise RuntimeError("ROLLBACK_PRIVATE_DIAGNOSTIC")
        def close(self):
            if close_fails: raise RuntimeError("CLOSE_PRIVATE_DIAGNOSTIC")
            real.close()
    try:
        ctx.save("baseline",["x"],"answer",{"urls":["base-url"]}); ctx.format_for_prompt()
        before=_cache(ctx)
        with ctx._lock:
            real.execute("CREATE TRIGGER fail_language BEFORE INSERT ON entities WHEN NEW.type='languages' BEGIN SELECT RAISE(ABORT,'PRIMARY_ENTITY_INSERT_SENTINEL'); END")
            real.commit()
        ctx._conn=Proxy()
        with caplog.at_level(logging.WARNING):
            with pytest.raises(sqlite3.IntegrityError,match="PRIMARY_ENTITY_INSERT_SENTINEL"):
                ctx.save(Q,["x"],A,{"urls":["partial-url"],"languages":["partial-language"]},scope=S)
        assert ctx._conn is None and ctx._connection_error=="disabled after rollback failure"
        assert _cache(ctx)==before
        for op in (lambda:ctx.save("later",["x"],"answer"),lambda:ctx.last_n(5),
                   lambda:ctx.get_entity("urls"),lambda:ctx.format_for_prompt(5)):
            with pytest.raises(sqlite3.ProgrammingError,match="disabled after rollback failure"): op()
        for secret in ("ROLLBACK_PRIVATE_DIAGNOSTIC","CLOSE_PRIVATE_DIAGNOSTIC",
                       "PRIMARY_ENTITY_INSERT_SENTINEL",Q,A,S):
            assert secret not in caplog.text
        assert "RuntimeError" in caplog.text
        assert ("Connection close failed" in caplog.text) is close_fails
    finally:
        try: real.close()
        except sqlite3.Error: pass
    verify=sqlite3.connect(str(path))
    try:
        assert verify.execute("SELECT COUNT(*) FROM turns WHERE query=?",(Q,)).fetchone()[0]==0
        assert verify.execute("SELECT COUNT(*) FROM entities WHERE value IN (?,?)",
                              ("partial-url","partial-language")).fetchone()[0]==0
        assert verify.execute("SELECT COUNT(*) FROM turns WHERE query='baseline'").fetchone()[0]==1
    finally: verify.close()

# J: privacy opt-out still skips DB writes and cache mutation.
def test_j_privacy_opt_out_skips_writes_and_preserves_cache(tmp_path,monkeypatch):
    from core.privacy import privacy
    monkeypatch.setattr("core.context.DB_PATH",tmp_path/"privacy.sqlite")
    ctx=ContextMemory()
    try:
        ctx.save("baseline",["x"],"answer",{"urls":["base-url"]}); ctx.format_for_prompt()
        before=_cache(ctx); monkeypatch.setattr(privacy,"can_save_history",lambda:False)
        assert ctx.save(Q,["x"],A,{"urls":["must-not-save"]},scope=S) is None
        assert _cache(ctx)==before
        with ctx._lock:
            conn=ctx._require_connection()
            assert conn.execute("SELECT COUNT(*) FROM turns WHERE query=?",(Q,)).fetchone()[0]==0
            assert conn.execute("SELECT COUNT(*) FROM entities WHERE value='must-not-save'").fetchone()[0]==0
    finally:
        if ctx._conn is not None: ctx._conn.close()


# K — Entity preparation is execution logic, not a best-effort save operation.
@pytest.mark.asyncio
async def test_k_entity_preparation_failure_is_not_swallowed():
    ctx = MagicMock(spec=ContextMemory)
    router = MagicMock()
    router.route = AsyncMock(
        return_value=RouteResult(answer="module result", source="test")
    )
    worker = PlannerWorker(
        modules={"knowledge": MagicMock()},
        context_memory=ctx,
        model_router=router,
    )
    malformed_parse = patch(
        "core.parser.parse",
        return_value=SimpleNamespace(entities=None),
    )
    assemble = patch(
        "core.memory.assembly.context_assembler.assemble_context",
        new=AsyncMock(return_value=""),
    )
    classify = patch(
        "core.classifier_v3.classify",
        return_value=[{"module": "knowledge"}],
    )
    merge = patch("core.merger.merge", new=AsyncMock(return_value="merged answer"))

    with malformed_parse, assemble, classify, merge:
        result = await worker._run(
            ExecutionContext(metadata={"query": Q})
        )

    assert result.success is False
    assert "has no attribute 'get'" in result.error
    ctx.save.assert_not_called()
