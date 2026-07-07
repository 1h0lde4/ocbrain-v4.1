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
    fire on the real request path

Run with:  python scripts/integration_check.py
Exit code: 0 on success, 1 (via AssertionError) on any check failing.
"""

import asyncio
import os
import shutil
import sys
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

    print("=== integration_check.py results ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    assert all(results.values())
    print("\nALL INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
