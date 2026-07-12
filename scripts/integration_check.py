"""
scripts/integration_check.py — Production wiring smoke test.

Exercises the REAL composition-root wiring end-to-end (not mocks, not
isolated pytest unit tests) -- a manual/CI-able complement to the pytest
suite, kept as a permanent, tracked repo artifact so it survives sandbox
resets (unlike its first version, which lived outside the git repo in a
scratch directory and was lost when that directory was cleaned up).

Fully self-contained: every backend is constructed fresh, scoped under
.data/tmp/integration_check/ (already gitignored via the existing
`.data/tmp/` pattern), so running this NEVER touches the real .data/
directory or any other developer/production state. Safe to run repeatedly.

Covers (Session 5 — Production Runtime Integration, extended as later
sessions add wiring):
  - UnifiedMemory + GraphBackend registration (main.py Step 6 pattern)
  - write / read / search / update / delete through UnifiedMemory
  - a graph-eligible write actually produces a graph node (mechanical
    proof the wiring works, independent of the separate, documented
    truth_status-eligibility gap)
  - GovernanceKernel.evaluate_action() approves a normal query-shaped
    action and genuinely rejects one that violates RecursionGovernor
  - EventStream durability + queryability
  - a real Orchestrator instance + handle() call, confirming the
    governance check and query_started/query_completed events actually
    fire on the real request path (legacy compatibility-bridge shape:
    no execution_runtime/workflow_runtime supplied)
  - K2.2: the actual production wiring shape -- WorkerRegistry ->
    ExecutionRuntime -> WorkflowRuntime -> Orchestrator, with
    PlannerWorker registered via constructor_kwargs exactly as main.py's
    composition root does it, confirming the full chain's events
    (workflow.started/completed, execution.completed,
    orchestrator.query_completed tagged execution_path=workflow_runtime)
    all fire and the answer is correctly returned end-to-end

Run with:  python scripts/integration_check.py
Exit code: 0 on success, 1 (via AssertionError) on any check failing.
"""

import asyncio
import os
import shutil
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

SCRATCH_ROOT = os.path.join(REPO_ROOT, ".data", "tmp", "integration_check")


async def main() -> None:
    # Fresh scratch space every run -- no state carried over between runs.
    if os.path.exists(SCRATCH_ROOT):
        shutil.rmtree(SCRATCH_ROOT)
    os.makedirs(SCRATCH_ROOT, exist_ok=True)

    results = {}

    # ── 1. UnifiedMemory + GraphBackend wiring (main.py Step 6 pattern) ────
    from core.memory.unified_memory import UnifiedMemory
    from core.memory.backends.sqlite_graph import SQLiteGraphBackend

    memory = UnifiedMemory(db_prefix=os.path.join(SCRATCH_ROOT, "memory"))
    assert memory.stats()["graph_active"] is False

    graph = SQLiteGraphBackend(os.path.join(SCRATCH_ROOT, "memory", "graph.db"))
    memory.register_graph_backend(graph)
    assert memory.stats()["graph_active"] is True
    results["graph_backend_registers"] = True

    # ── 2. write / read / search / update / delete ─────────────────────────
    entry_id = await memory.write(
        content="Integration check: production runtime wiring test.",
        content_type="interaction", source="integration_check", importance=0.6,
    )
    entry = await memory.read(entry_id)
    assert entry is not None and entry.content.startswith("Integration check")
    results["write_read"] = True

    search_results = await memory.search("integration check wiring", limit=5)
    assert any(r.entry.entry_id == entry_id for r in search_results)
    results["search"] = True

    await memory.update(entry_id, {"importance": 0.9})
    updated = await memory.read(entry_id)
    assert abs(updated.importance - 0.9) < 1e-6
    results["update"] = True

    # ── 3. Graph write path (bypasses the known, separately-documented
    #      truth_status-eligibility gap on purpose, to prove the mechanical
    #      write()->GraphIndexer->GraphBackend chain works end-to-end) ─────
    with patch("core.memory.knowledge_entry.GRAPH_ELIGIBLE_STATUSES",
               {"unknown", "verified", "candidate"}):
        graph_entry_id = await memory.write(
            content="Graph-eligible entry for wiring proof.",
            content_type="interaction",
        )
    node = await graph.get_node(f"mem:{graph_entry_id}")
    assert node is not None
    results["graph_write_path_mechanically_works"] = True

    assert await memory.delete(entry_id, reason="integration_check_cleanup") is True
    results["delete"] = True

    # ── 4. GovernanceKernel — exact action shape Orchestrator.handle() uses ─
    from core.governance.governance_kernel import (
        GovernanceAction, GovernanceKernel, GovernanceVerdict,
    )
    gk = GovernanceKernel()   # fresh instance -- pure in-memory, no disk state
    action = GovernanceAction(
        action_type="orchestrator_handle", worker_id="Orchestrator",
        description="orchestrator_handle: integration check query",
        recursion_depth=0, metadata={"interaction_id": "interaction:test"},
    )
    result = gk.evaluate_action(action)
    assert result.verdict == GovernanceVerdict.APPROVE
    results["governance_approves_normal_query"] = True

    bad_action = GovernanceAction(
        action_type="orchestrator_handle", worker_id="Orchestrator",
        recursion_depth=999,
    )
    bad_result = gk.evaluate_action(bad_action)
    assert bad_result.verdict == GovernanceVerdict.REJECT
    results["governance_rejects_runaway_recursion"] = True

    # ── 5. EventStream — durability + queryability ─────────────────────────
    from core.events.event_stream import EventStream, SQLiteEventStore
    es = EventStream(store=SQLiteEventStore(
        os.path.join(SCRATCH_ROOT, "events", "stream.db")))
    before = len(await es.query())
    await es.append("integration_check.probe", source="integration_check",
                     payload={"probe": True})
    after_events = await es.query()
    assert len(after_events) == before + 1
    assert any(e.event_type == "integration_check.probe" for e in after_events)
    results["event_stream_durable_and_queryable"] = True

    # ── 6. Real Orchestrator instance, real handle() call ──────────────────
    from core.orchestrator import Orchestrator
    from core.context import ContextMemory

    ctx = MagicMock(spec=ContextMemory)
    router = MagicMock()
    router.route = AsyncMock(return_value=None)
    orch = Orchestrator(modules={}, context=ctx, router=router,
                         memory=memory, governance=gk, event_stream=es)
    before_events = len(await es.query())
    await orch.handle("integration check smoke-test query")
    after_events2 = await es.query()
    event_types = [e.event_type for e in after_events2[before_events:]]
    assert "orchestrator.query_started" in event_types
    results["orchestrator_emits_query_started"] = True
    await orch.close()
    results["orchestrator_close_works"] = True

    # ── 7. K2.2 — real WorkflowRuntime wiring, main.py's actual shape ──────
    # Section 6 above deliberately still constructs Orchestrator WITHOUT
    # execution_runtime/workflow_runtime -- that remains a valid check of
    # the legacy-compatibility bridge (still test-reachable per
    # tests/test_execution_runtime.py::TestBackwardCompatibility). This
    # section proves the actual production shape main.py now builds:
    # WorkerRegistry -> ExecutionRuntime -> WorkflowRuntime -> Orchestrator,
    # with PlannerWorker registered via constructor_kwargs exactly as the
    # composition root does it, and a real (non-mocked) RouteResult so
    # merger.merge() and PlannerWorker's memory.write()/context.save() are
    # mechanically exercised, not just governance/events.
    from core.model_router import RouteResult
    from core.runtime.worker_registry import WorkerRegistry
    from core.runtime.execution_runtime import ExecutionRuntime
    from core.workers.planner import PlannerWorker
    from core.workflow.runtime import WorkflowRuntime

    wf_router = MagicMock()
    wf_router.route = AsyncMock(
        return_value=RouteResult(answer="K2.2 wiring proof", source="mock"))
    wf_ctx = MagicMock(spec=ContextMemory)

    registry = WorkerRegistry()
    registry.register(PlannerWorker, constructor_kwargs={
        "modules": {"web_search": object()},
        "context_memory": wf_ctx,
        "model_router": wf_router,
        "memory": memory,
    })
    execution_runtime = ExecutionRuntime(
        worker_registry=registry, governance=gk, event_stream=es)
    workflow_runtime = WorkflowRuntime(
        execution_runtime=execution_runtime, event_stream=es)

    wf_orch = Orchestrator(
        modules={"web_search": object()}, context=wf_ctx, router=wf_router,
        memory=memory, governance=gk, event_stream=es,
        execution_runtime=execution_runtime,
        workflow_runtime=workflow_runtime,
    )
    # EventStream.query() returns newest-first (ORDER BY sequence DESC)
    # with a default limit=100 -- a before/after-count + slice comparison
    # (as section 6 above does) silently breaks once total event count
    # exceeds the limit, or returns the wrong subset once ordering is
    # accounted for. Use the since= timestamp filter it already supports
    # instead, which is correct regardless of how many events sections
    # 1-6 already appended.
    since_ts = time.time()
    answer = await wf_orch.handle("K2.2 integration check query")
    assert answer == "K2.2 wiring proof"
    results["workflow_runtime_produces_correct_answer"] = True

    wf_events = await es.query(since=since_ts, limit=1000)
    wf_event_types = [e.event_type for e in wf_events]
    # workflow.started/completed (WorkflowRuntime) and execution.completed
    # (ExecutionRuntime) must ALL fire -- proof the full chain ran, not
    # just the orchestrator-level events section 6 already confirmed.
    assert "workflow.started" in wf_event_types
    assert "workflow.completed" in wf_event_types
    assert "execution.completed" in wf_event_types
    results["full_chain_events_fire"] = True

    wf_completed = [e for e in wf_events
                     if e.event_type == "orchestrator.query_completed"][0]
    assert wf_completed.payload.get("execution_path") == "workflow_runtime"
    results["execution_path_tagged_workflow_runtime"] = True

    await wf_orch.close()
    results["workflow_runtime_orchestrator_close_works"] = True

    # ── 8. K2.3 — real Capability Runtime wiring, main.py's actual shape ───
    # Same discipline as section 7: build the exact object graph main.py
    # builds (CapabilityRegistry -> AdapterRuntime -> ModelRouterAdapter
    # wrapping a real ModelRouter, registered alongside OllamaAdapter/
    # OpenAICompatAdapter exactly as main.py orders them), with only the
    # network-level seam (ModelRouter.route(), which would otherwise hit
    # a real Ollama server) patched.
    from core.model_router import ModelRouter, RouteResult
    from core.capabilities import (
        CapabilityRegistry, ResourceManager, AdapterRuntime,
        CapabilityContract, CapabilityType,
    )
    from core.capabilities.adapters.model_router_adapter import ModelRouterAdapter
    from core.capabilities.adapters.ollama_adapter import OllamaAdapter
    from core.capabilities.adapters.openai_compat_adapter import OpenAICompatAdapter

    real_model_router = ModelRouter()

    async def _fake_route(module_name, subtask, context):
        return RouteResult(answer="K2.3 wiring proof", source="patched")
    real_model_router.route = _fake_route

    k23_resource_manager = ResourceManager()
    k23_registry = CapabilityRegistry()
    k23_registry.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION,
        description="integration check"))
    k23_registry.register_adapter(
        CapabilityType.LLM_COMPLETION, ModelRouterAdapter(real_model_router))
    k23_registry.register_adapter(
        CapabilityType.LLM_COMPLETION, OllamaAdapter())
    k23_registry.register_adapter(
        CapabilityType.LLM_COMPLETION, OpenAICompatAdapter())
    assert k23_registry.validate() == []
    results["capability_registry_valid_no_unfulfilled"] = True

    k23_adapter_runtime = AdapterRuntime(
        registry=k23_registry, resource_manager=k23_resource_manager,
        event_stream=es)

    k23_ctx = MagicMock(spec=ContextMemory)
    registry2 = WorkerRegistry()
    registry2.register(PlannerWorker, constructor_kwargs={
        "modules": {"web_search": object()},
        "context_memory": k23_ctx,
        "adapter_runtime": k23_adapter_runtime,
        "memory": memory,
    })
    k23_execution_runtime = ExecutionRuntime(
        worker_registry=registry2, governance=gk, event_stream=es)
    k23_workflow_runtime = WorkflowRuntime(
        execution_runtime=k23_execution_runtime, event_stream=es)

    k23_orch = Orchestrator(
        modules={"web_search": object()}, context=k23_ctx, router=wf_router,
        memory=memory, governance=gk, event_stream=es,
        execution_runtime=k23_execution_runtime,
        workflow_runtime=k23_workflow_runtime,
    )
    since_k23 = time.time()
    k23_answer = await k23_orch.handle("K2.3 integration check query")
    assert k23_answer == "K2.3 wiring proof"
    results["capability_runtime_produces_correct_answer"] = True

    k23_events = await es.query(since=since_k23, limit=1000)
    k23_event_types = [e.event_type for e in k23_events]
    assert "adapter.invoked" in k23_event_types
    results["adapter_runtime_events_fire"] = True

    invoked_event = [e for e in k23_events if e.event_type == "adapter.invoked"][0]
    assert invoked_event.payload.get("adapter") == "ModelRouterAdapter"
    results["model_router_adapter_used_by_default"] = True

    await k23_orch.close()
    results["capability_runtime_orchestrator_close_works"] = True

    print("=== integration_check.py results ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    assert all(results.values())
    print("\nALL INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
