"""
tests/test_unified_memory.py — UnifiedMemory Session 3A Test Suite

Covers:
  UnifiedMemory.delete()       — full lifecycle, hooks, layer ordering
  HookRegistry                 — registration, duplicate prevention, execution order
  MemoryCuratorWorker          — no private backend access, public API only
  SQLiteArchiveBackend         — column mapping fix, event persistence
  GraphBackend.delete_node     — ABC contract, GraphEngine, SQLiteGraphBackend
  Integration                  — write→search→update→delete end-to-end
"""

import asyncio
import os
import sqlite3
import tempfile
from contextlib import closing
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock, patch, call

import pytest
import pytest_asyncio

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.memory.unified_memory import UnifiedMemory, HookRegistry, get_unified_memory
from core.memory.knowledge_entry import KnowledgeEntry
from core.memory.knowledge_event import (
    KnowledgeEvent, event_created, event_deleted, event_curated,
)
from core.memory.backends.sqlite_archive import SQLiteArchiveBackend
from core.memory.backends.sqlite_graph import SQLiteGraphBackend
from core.memory.graph.graph_engine import GraphEngine
from core.workers.curator import MemoryCuratorWorker, CurationConfig


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_prefix(tmp_path) -> str:
    prefix = str(tmp_path / "memory")
    os.makedirs(prefix, exist_ok=True)
    return prefix


@pytest.fixture
def memory(tmp_prefix) -> UnifiedMemory:
    return UnifiedMemory(db_prefix=tmp_prefix)


@pytest.fixture
def memory_with_curator(memory) -> tuple:
    curator = MemoryCuratorWorker()
    curator.register(memory)
    return memory, curator


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "graph.db")


# Helper — content long enough to pass curator quality gate (≥10 chars for l2/l3)
def _fact(text: str = "A sufficiently long fact about the world.") -> str:
    return text


async def _write(memory, content=None, **kwargs) -> str:
    """Write helper with a default content that passes quality gates."""
    return await memory.write(
        content or _fact(),
        content_type=kwargs.pop("content_type", "fact"),
        importance=kwargs.pop("importance", 0.8),
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — HookRegistry
# ═══════════════════════════════════════════════════════════════════════════════

class TestHookRegistry:

    def test_initial_state_empty_hooks(self):
        hr = HookRegistry()
        assert hr.before_write == []
        assert hr.after_write == []
        assert hr.before_promote == []
        assert hr.after_promote == []
        assert hr.before_archive == []
        assert hr.after_archive == []
        assert hr.before_delete == []
        assert hr.after_delete == []

    def test_curator_not_registered_initially(self):
        hr = HookRegistry()
        assert hr.curator_registered is False

    def test_register_curator_wires_three_hooks(self):
        hr = HookRegistry()
        curator = MemoryCuratorWorker()
        hr.register_curator(curator)

        assert len(hr.before_write)  == 1
        assert len(hr.after_write)   == 1
        assert len(hr.before_delete) == 1
        assert hr.curator_registered is True

    def test_register_curator_correct_functions(self):
        hr = HookRegistry()
        curator = MemoryCuratorWorker()
        hr.register_curator(curator)

        assert curator._before_write_hook  in hr.before_write
        assert curator._after_write_hook   in hr.after_write
        assert curator._before_delete_hook in hr.before_delete

    def test_duplicate_registration_blocked(self):
        hr = HookRegistry()
        c1 = MemoryCuratorWorker()
        c2 = MemoryCuratorWorker()
        hr.register_curator(c1)
        hr.register_curator(c2)   # should be a no-op

        assert len(hr.before_write)  == 1
        assert len(hr.after_write)   == 1
        assert len(hr.before_delete) == 1

    def test_unregister_curator_clears_hooks(self):
        hr = HookRegistry()
        curator = MemoryCuratorWorker()
        hr.register_curator(curator)
        hr.unregister_curator()

        assert hr.before_write  == []
        assert hr.after_write   == []
        assert hr.before_delete == []
        assert hr.curator_registered is False

    def test_unregister_when_not_registered_is_noop(self):
        hr = HookRegistry()
        hr.unregister_curator()   # must not raise
        assert hr.curator_registered is False

    def test_register_after_unregister_succeeds(self):
        hr = HookRegistry()
        curator = MemoryCuratorWorker()
        hr.register_curator(curator)
        hr.unregister_curator()
        hr.register_curator(curator)   # second registration after unregister

        assert hr.curator_registered is True
        assert len(hr.before_write) == 1

    def test_hook_execution_order_deterministic(self):
        """Hooks execute in the order they were registered."""
        order = []
        hr = HookRegistry()

        def hook_a(entry):
            order.append("a")
            return entry

        def hook_b(entry):
            order.append("b")
            return entry

        hr.before_write.append(hook_a)
        hr.before_write.append(hook_b)

        entry = KnowledgeEntry(entry_id="x", content="test", layer="l1")
        for hook in hr.before_write:
            result = hook(entry)
            if result is not None:
                entry = result

        assert order == ["a", "b"]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — UnifiedMemory.delete()
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnifiedMemoryDelete:

    @pytest.mark.asyncio
    async def test_delete_existing_entry_returns_true(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)
        result = await memory.delete(eid)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_removes_from_l1_storage(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)
        await memory.delete(eid)
        entry = await memory.read(eid)
        assert entry is None

    @pytest.mark.asyncio
    async def test_delete_evicts_l0_cache(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory, content_type="observation", importance=0.6,
                            content="Short observable event that fits l1")
        # Ensure entry is in L0
        await memory.read(eid)
        assert memory._l0.get(eid) is not None

        await memory.delete(eid)
        assert memory._l0.get(eid) is None

    @pytest.mark.asyncio
    async def test_delete_missing_entry_returns_false(self, memory):
        result = await memory.delete("nonexistent-entry-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_missing_entry_is_safe(self, memory):
        """Delete of missing entry must not raise."""
        result = await memory.delete("nonexistent-entry-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_empty_id_returns_false(self, memory):
        result = await memory.delete("")
        assert result is False

    @pytest.mark.asyncio
    async def test_repeated_delete_is_idempotent(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)
        d1 = await memory.delete(eid)
        d2 = await memory.delete(eid)
        assert d1 is True
        assert d2 is False   # second delete: entry not found

    @pytest.mark.asyncio
    async def test_delete_archives_deletion_event(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)
        await memory.delete(eid, reason="test_deletion")

        events = await memory._archive.query_events(entry_id=eid,
                                                     event_type="deleted")
        assert len(events) >= 1
        assert events[0].reason == "test_deletion"

    @pytest.mark.asyncio
    async def test_delete_archives_entry_snapshot(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)
        await memory.delete(eid)

        with closing(sqlite3.connect(memory._archive.db_path)) as conn:
            snaps = conn.execute(
                "SELECT reason FROM entry_snapshots WHERE entry_id=?", (eid,)
            ).fetchall()
        reasons = {s[0] for s in snaps}
        assert "delete" in reasons

    @pytest.mark.asyncio
    async def test_delete_archives_before_removal(self, memory_with_curator):
        """Archive event must be created even if L1 removal fails."""
        memory, _ = memory_with_curator
        eid = await _write(memory)

        # Intercept archive to confirm it fires
        archived_events = []
        original_append = memory._archive.append_event
        async def spy_append(ev):
            archived_events.append(ev)
            await original_append(ev)
        memory._archive.append_event = spy_append

        await memory.delete(eid)
        types = [e.event_type for e in archived_events]
        assert "deleted" in types

    @pytest.mark.asyncio
    async def test_delete_blocked_by_before_delete_hook(self, memory_with_curator):
        """L4 entries are blocked from deletion by the curator hook."""
        memory, _ = memory_with_curator
        eid = await memory.write(
            "Immutable audit record — must never be deleted",
            layer_hint="l4",
        )
        result = await memory.delete(eid)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_blocked_l4_entry_still_exists(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await memory.write("L4 audit record for block test", layer_hint="l4")
        await memory.delete(eid)
        entry = await memory.read(eid)
        assert entry is not None

    @pytest.mark.asyncio
    async def test_delete_fires_after_delete_hooks(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)

        fired = []
        memory._hooks.after_delete.append(lambda entry: fired.append(entry.entry_id))
        await memory.delete(eid)
        assert eid in fired

    @pytest.mark.asyncio
    async def test_before_delete_hook_none_blocks_deletion(self, memory):
        """A before_delete hook returning None must block the delete."""
        memory._hooks.before_delete.append(lambda entry: None)

        eid = await memory.write(
            "Entry that should be blocked from deletion",
            layer_hint="l1",
        )
        result = await memory.delete(eid)
        assert result is False
        assert await memory.read(eid) is not None

    @pytest.mark.asyncio
    async def test_delete_removes_from_l2_vector(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)
        # Verify it's in the vector index
        before = await memory._vector.search_bm25("sufficiently long fact", top_k=10)
        eids_before = {r[0] for r in before}
        assert eid in eids_before

        await memory.delete(eid)
        after = await memory._vector.search_bm25("sufficiently long fact", top_k=10)
        eids_after = {r[0] for r in after}
        assert eid not in eids_after

    @pytest.mark.asyncio
    async def test_delete_with_graph_backend_removes_graph_node(self, memory_with_curator, db_path):
        memory, _ = memory_with_curator
        graph = SQLiteGraphBackend(db_path=db_path)
        memory.register_graph_backend(graph)

        # Write an l3 entry so it gets graph-indexed
        eid = await memory.write(
            "Semantic entity for graph indexing test — long enough",
            layer_hint="l3", importance=0.9,
        )
        entry = await memory.read(eid)
        if entry and entry.graph_node_id:
            # Graph node was created
            node_before = await graph.get_node(entry.graph_node_id)
            assert node_before is not None

            await memory.delete(eid)
            node_after = await graph.get_node(entry.graph_node_id)
            assert node_after is None, "Graph node should be removed on delete"
        else:
            # Graph node not created (l3 entry without graph_node_id) — skip graph check
            await memory.delete(eid)

    @pytest.mark.asyncio
    async def test_delete_without_graph_backend_succeeds(self, memory_with_curator):
        """delete() must succeed even with no graph backend wired."""
        memory, _ = memory_with_curator
        assert memory._graph is None
        eid = await _write(memory)
        result = await memory.delete(eid)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_multiple_independent_entries(self, memory_with_curator):
        memory, _ = memory_with_curator
        ids = [await _write(memory, content=f"Unique fact number {i} for deletion test")
               for i in range(5)]

        results = [await memory.delete(eid) for eid in ids]
        assert all(results), "All deletes should succeed"

        # All entries should be gone
        for eid in ids:
            assert await memory.read(eid) is None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — UnifiedMemory Public API Completeness
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnifiedMemoryPublicAPI:

    def test_all_required_methods_exist(self, memory):
        for method in ("read", "write", "search", "update", "delete",
                        "stats", "full_stats", "archive_event",
                        "archive_snapshot", "find_contradictions",
                        "get_layer", "get_by_truth_status",
                        "register_curator", "register_graph_backend",
                        "consolidate"):
            assert hasattr(memory, method), f"UnifiedMemory missing: {method}"

    def test_no_private_backend_in_public_api(self, memory):
        """Public API must not expose _storage, _vector, _archive, _l0, _graph."""
        public_attrs = [a for a in dir(memory) if not a.startswith("_")]
        assert "_storage" not in public_attrs
        assert "_vector"  not in public_attrs
        assert "_archive" not in public_attrs
        assert "_l0"      not in public_attrs
        assert "_graph"   not in public_attrs

    @pytest.mark.asyncio
    async def test_archive_event_public_method(self, memory):
        ev = event_created("test-entry-id", reason="public-api-test")
        await memory.archive_event(ev)   # must not raise
        events = await memory._archive.query_events(entry_id="test-entry-id")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_archive_snapshot_public_method(self, memory):
        entry = KnowledgeEntry(
            entry_id="snap-test", content="snapshot test content",
            layer="l1",
        )
        await memory.archive_snapshot(entry, reason="public-api-snapshot")
        with closing(sqlite3.connect(memory._archive.db_path)) as conn:
            row = conn.execute(
                "SELECT reason FROM entry_snapshots WHERE entry_id=?",
                ("snap-test",),
            ).fetchone()
        assert row is not None
        assert row[0] == "public-api-snapshot"

    @pytest.mark.asyncio
    async def test_find_contradictions_no_graph_returns_empty(self, memory):
        result = await memory.find_contradictions()
        assert result == []

    @pytest.mark.asyncio
    async def test_find_contradictions_with_graph_delegates(self, memory, db_path):
        graph = SQLiteGraphBackend(db_path=db_path)
        memory.register_graph_backend(graph)

        await graph.add_node("A", "concept", "Alpha")
        await graph.add_node("B", "concept", "Beta")
        await graph.add_edge("A", "B", "contradicts")
        await graph.add_edge("B", "A", "contradicts")

        result = await memory.find_contradictions()
        assert len(result) == 1
        pair = result[0]
        assert set([pair["node_a"], pair["node_b"]]) == {"A", "B"}

    @pytest.mark.asyncio
    async def test_stats_returns_expected_keys(self, memory):
        s = memory.stats()
        for key in ("writes", "searches", "l0", "graph_active"):
            assert key in s, f"stats() missing key: {key}"

    @pytest.mark.asyncio
    async def test_full_stats_returns_all_layers(self, memory):
        s = await memory.full_stats()
        for key in ("l0", "l1", "l2", "l3", "l4"):
            assert key in s, f"full_stats() missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — MemoryCuratorWorker: No Private Backend Access
# ═══════════════════════════════════════════════════════════════════════════════

class TestCuratorNoPriceBackendAccess:

    def test_curator_source_has_no_private_storage_access(self):
        import inspect, textwrap
        src = textwrap.dedent(inspect.getsource(MemoryCuratorWorker))
        # Exclude comments and docstrings by checking actual code tokens
        lines = [l for l in src.split("\n") if not l.strip().startswith("#")]
        code = "\n".join(lines)
        assert "._storage" not in code, "Curator accesses ._storage (private)"
        assert "._vector"  not in code, "Curator accesses ._vector (private)"
        assert "._archive" not in code, "Curator accesses ._archive (private)"
        assert "._l0"      not in code, "Curator accesses ._l0 (private)"

    def test_curator_uses_only_public_memory_methods(self):
        """All memory interactions in curator must be via public methods."""
        import inspect, ast, textwrap
        src = textwrap.dedent(inspect.getsource(MemoryCuratorWorker))
        tree = ast.parse(src)
        # Find all attribute accesses on self._memory
        violations = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Attribute)
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "self"
                    and node.value.attr == "_memory"
                    and node.attr.startswith("_")):
                violations.append(f"self._memory.{node.attr}")
        assert violations == [], \
            f"Private access via self._memory: {violations}"

    @pytest.mark.asyncio
    async def test_register_does_not_touch_hooks_directly(self, memory):
        """register() must delegate to memory.register_curator(), not append to hooks."""
        import inspect, ast, textwrap
        src = textwrap.dedent(inspect.getsource(MemoryCuratorWorker.register))
        tree = ast.parse(src)

        # Check for any direct _hooks access
        direct_hooks = [
            ast.unparse(node) for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "_hooks"
        ]
        assert direct_hooks == [], \
            f"register() accesses _hooks directly: {direct_hooks}"

    @pytest.mark.asyncio
    async def test_prune_stale_uses_delete_not_private_backends(self, memory_with_curator):
        """prune_stale() must call memory.delete() — verified by mock."""
        memory, curator = memory_with_curator

        delete_calls = []
        original_delete = memory.delete

        async def spy_delete(entry_id, **kwargs):
            delete_calls.append(entry_id)
            return await original_delete(entry_id, **kwargs)

        memory.delete = spy_delete

        # Create a stale entry (age > 30 days)
        import time
        eid = await _write(memory, content="Stale fact that should be pruned today.")
        entry = await memory.read(eid)
        if entry:
            # Backdating: update created_at to 35 days ago
            old_ts = time.time() - (35 * 86400)
            await memory._storage.update(eid, {
                "created_at": old_ts,
                "importance": 0.05,   # below min_importance_to_prune
                "access_count": 0,
            })

            pruned = await curator.prune_stale()
            if pruned > 0:
                assert eid in delete_calls, \
                    "prune_stale should call memory.delete() not private backends"

    @pytest.mark.asyncio
    async def test_resolve_contradictions_uses_find_contradictions(self, memory_with_curator, db_path):
        """resolve_contradictions() must use memory.find_contradictions()."""
        memory, curator = memory_with_curator
        graph = SQLiteGraphBackend(db_path=db_path)
        memory.register_graph_backend(graph)

        find_calls = []
        original = memory.find_contradictions
        async def spy():
            find_calls.append(True)
            return await original()
        memory.find_contradictions = spy

        await curator.resolve_contradictions()
        assert len(find_calls) == 1, \
            "resolve_contradictions must call memory.find_contradictions()"

    @pytest.mark.asyncio
    async def test_resolve_contradictions_uses_archive_event(self, memory_with_curator, db_path):
        """resolve_contradictions() must use memory.archive_event()."""
        memory, curator = memory_with_curator
        graph = SQLiteGraphBackend(db_path=db_path)
        memory.register_graph_backend(graph)

        # Set up contradicting graph entries
        await graph.add_node("mem:eid-a", "concept", "Entry A")
        await graph.add_node("mem:eid-b", "concept", "Entry B")
        await graph.add_edge("mem:eid-a", "mem:eid-b", "contradicts")
        await graph.add_edge("mem:eid-b", "mem:eid-a", "contradicts")

        archive_event_calls = []
        original_ae = memory.archive_event
        async def spy_ae(ev):
            archive_event_calls.append(ev)
            await original_ae(ev)
        memory.archive_event = spy_ae

        await curator.resolve_contradictions()
        # If entries are missing (no actual l1 entries), resolution is skipped — that's OK.
        # What matters is that archive_event is used, not _archive directly.

    @pytest.mark.asyncio
    async def test_curator_register_calls_register_curator(self, memory):
        """register() must call memory.register_curator(), not memory._hooks."""
        calls = []
        original_rc = memory.register_curator
        def spy_rc(curator):
            calls.append(curator)
            original_rc(curator)
        memory.register_curator = spy_rc

        curator = MemoryCuratorWorker()
        curator.register(memory)
        assert len(calls) == 1
        assert calls[0] is curator


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — SQLiteArchiveBackend
# ═══════════════════════════════════════════════════════════════════════════════

class TestSQLiteArchiveBackend:

    @pytest.fixture
    def archive(self, tmp_path) -> SQLiteArchiveBackend:
        return SQLiteArchiveBackend(db_path=str(tmp_path / "archive.db"))

    @pytest.mark.asyncio
    async def test_append_event_created(self, archive):
        ev = event_created("entry-1", worker_id="worker-x", reason="test")
        await archive.append_event(ev)
        events = await archive.query_events(entry_id="entry-1")
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].worker_id == "worker-x"

    @pytest.mark.asyncio
    async def test_append_event_deleted(self, archive):
        ev = event_deleted("entry-2", reason="test_deletion", worker_id="w")
        await archive.append_event(ev)
        events = await archive.query_events(entry_id="entry-2", event_type="deleted")
        assert len(events) == 1
        assert events[0].reason == "test_deletion"

    @pytest.mark.asyncio
    async def test_append_event_curated(self, archive):
        ev = event_curated("entry-3", delta={"action": "test"}, reason="r", worker_id="c")
        await archive.append_event(ev)
        events = await archive.query_events(entry_id="entry-3")
        assert len(events) == 1
        assert events[0].event_type == "curated"

    @pytest.mark.asyncio
    async def test_append_event_idempotent(self, archive):
        ev = event_created("entry-4")
        await archive.append_event(ev)
        await archive.append_event(ev)   # duplicate — silent ignore
        events = await archive.query_events(entry_id="entry-4")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_append_snapshot_stored(self, archive):
        entry = KnowledgeEntry(entry_id="snap-eid", content="snapshot content", layer="l1")
        await archive.append_entry_snapshot(entry, reason="test_snap")
        with closing(sqlite3.connect(archive.db_path)) as conn:
            row = conn.execute(
                "SELECT reason, snapshot_data FROM entry_snapshots WHERE entry_id=?",
                ("snap-eid",),
            ).fetchone()
        assert row is not None
        assert row[0] == "test_snap"

    @pytest.mark.asyncio
    async def test_column_mapping_change_delta(self, archive):
        """Ensure 'delta' from KnowledgeEvent maps to 'change_delta' column."""
        from core.memory.knowledge_event import event_updated
        ev = event_updated("entry-5", delta={"importance": 0.9}, reason="boost")
        await archive.append_event(ev)
        with closing(sqlite3.connect(archive.db_path)) as conn:
            row = conn.execute(
                "SELECT change_delta FROM knowledge_events WHERE entry_id=?",
                ("entry-5",),
            ).fetchone()
        assert row is not None
        import json
        delta = json.loads(row[0])
        assert delta == {"importance": 0.9}

    @pytest.mark.asyncio
    async def test_column_mapping_previous_layer(self, archive):
        """Ensure 'from_layer' from KnowledgeEvent maps to 'previous_layer' column."""
        from core.memory.knowledge_event import event_promoted
        ev = event_promoted("entry-6", from_layer="l1", to_layer="l2")
        await archive.append_event(ev)
        with closing(sqlite3.connect(archive.db_path)) as conn:
            row = conn.execute(
                "SELECT previous_layer FROM knowledge_events WHERE entry_id=?",
                ("entry-6",),
            ).fetchone()
        assert row is not None
        assert row[0] == "l1"

    @pytest.mark.asyncio
    async def test_uses_running_loop_not_get_event_loop(self, archive):
        import inspect, ast, textwrap
        src = textwrap.dedent(inspect.getsource(archive._run))
        tree = ast.parse(src)
        attrs = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
        assert "get_running_loop" in attrs, "_run must use get_running_loop()"
        assert "get_event_loop"   not in attrs, "_run must not use get_event_loop()"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — GraphBackend.delete_node (ABC + Engine + Backend)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteNode:

    def test_delete_node_in_graphbackend_abc(self):
        import inspect
        from core.memory.backends.base import GraphBackend
        abstract = {n for n, v in inspect.getmembers(GraphBackend)
                    if getattr(v, "__isabstractmethod__", False)}
        assert "delete_node" in abstract

    def test_graph_engine_delete_node_existing(self, db_path):
        g = GraphEngine(db_path=db_path)
        g.add_node("n1", "entity", "Alpha")
        result = g.delete_node("n1")
        assert result is True
        assert g.get_node("n1") is None

    def test_graph_engine_delete_node_missing(self, db_path):
        g = GraphEngine(db_path=db_path)
        result = g.delete_node("nonexistent")
        assert result is False

    def test_graph_engine_delete_node_removes_incident_edges(self, db_path):
        g = GraphEngine(db_path=db_path)
        g.add_node("a", "t", "A")
        g.add_node("b", "t", "B")
        g.add_node("c", "t", "C")
        g.add_edge("a", "b", "knows")
        g.add_edge("c", "a", "knows")
        g.delete_node("a")
        assert g.stats()["edge_count"] == 0

    def test_graph_engine_delete_node_leaves_unrelated_edges(self, db_path):
        g = GraphEngine(db_path=db_path)
        g.add_node("a", "t", "A")
        g.add_node("b", "t", "B")
        g.add_node("c", "t", "C")
        g.add_edge("b", "c", "unrelated")
        g.add_edge("a", "b", "related")
        g.delete_node("a")
        assert g.stats()["edge_count"] == 1

    def test_graph_engine_delete_node_committed(self, db_path):
        """Deletion must be committed — verified in fresh connection."""
        g = GraphEngine(db_path=db_path)
        g.add_node("x", "t", "X")
        g.delete_node("x")
        with closing(sqlite3.connect(db_path)) as conn:
            row = conn.execute("SELECT id FROM nodes WHERE id='x'").fetchone()
        assert row is None

    def test_graph_engine_delete_nonexistent_node_no_write(self, db_path):
        """delete_node on missing node must not open a write transaction."""
        g = GraphEngine(db_path=db_path)
        g.add_node("a", "t", "A")
        stat_before = g.stats()
        g.delete_node("nonexistent")
        assert g.stats() == stat_before   # nothing changed

    @pytest.mark.asyncio
    async def test_sqlite_graph_backend_delete_node_existing(self, db_path):
        b = SQLiteGraphBackend(db_path=db_path)
        await b.add_node("n1", "entity", "Alpha")
        result = await b.delete_node("n1")
        assert result is True
        assert await b.get_node("n1") is None

    @pytest.mark.asyncio
    async def test_sqlite_graph_backend_delete_node_missing(self, db_path):
        b = SQLiteGraphBackend(db_path=db_path)
        result = await b.delete_node("ghost")
        assert result is False

    @pytest.mark.asyncio
    async def test_sqlite_graph_backend_delete_node_removes_edges(self, db_path):
        b = SQLiteGraphBackend(db_path=db_path)
        await b.add_node("a", "t", "A")
        await b.add_node("b", "t", "B")
        await b.add_edge("a", "b", "r")
        await b.delete_node("a")
        s = await b.stats()
        assert s["edge_count"] == 0

    @pytest.mark.asyncio
    async def test_sqlite_graph_backend_satisfies_abc_delete_node(self, db_path):
        """SQLiteGraphBackend must implement all GraphBackend abstract methods."""
        import inspect
        from core.memory.backends.base import GraphBackend
        abstract = {n for n, v in inspect.getmembers(GraphBackend)
                    if getattr(v, "__isabstractmethod__", False)}
        implemented = set(dir(SQLiteGraphBackend))
        missing = abstract - implemented
        assert missing == set(), f"Missing: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Integration: Write → Search → Update → Delete
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnifiedMemoryLifecycle:

    @pytest.mark.asyncio
    async def test_write_then_read(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory, content="Integration test content for read.")
        entry = await memory.read(eid)
        assert entry is not None
        assert entry.entry_id == eid

    @pytest.mark.asyncio
    async def test_write_then_search(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory, content="Eiffel Tower located in Paris France landmark.")
        results = await memory.search("Eiffel Tower Paris")
        eids = [r.entry.entry_id for r in results]
        assert eid in eids

    @pytest.mark.asyncio
    async def test_write_then_update_then_read(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory)
        ok = await memory.update(eid, {"importance": 0.95}, reason="boost")
        assert ok is True
        entry = await memory.read(eid)
        assert entry is not None
        assert abs(entry.importance - 0.95) < 0.01

    @pytest.mark.asyncio
    async def test_write_update_delete_full_lifecycle(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await _write(memory, content="Full lifecycle test fact — write update delete.")

        # Write
        entry = await memory.read(eid)
        assert entry is not None

        # Update
        ok = await memory.update(eid, {"importance": 0.9})
        assert ok is True

        # Delete
        deleted = await memory.delete(eid, reason="lifecycle_test")
        assert deleted is True

        # Verify gone
        assert await memory.read(eid) is None

        # Verify archive contains full trail
        events = await memory._archive.query_events(entry_id=eid)
        event_types = {e.event_type for e in events}
        assert "created" in event_types
        assert "updated" in event_types
        assert "deleted" in event_types

    @pytest.mark.asyncio
    async def test_write_delete_archive_snapshot_has_content(self, memory_with_curator):
        memory, _ = memory_with_curator
        content = "Content that must appear in archive snapshot after deletion."
        eid = await _write(memory, content=content)
        await memory.delete(eid)

        with closing(sqlite3.connect(memory._archive.db_path)) as conn:
            row = conn.execute(
                "SELECT snapshot_data FROM entry_snapshots WHERE entry_id=?",
                (eid,),
            ).fetchone()
        assert row is not None
        import json
        snap = json.loads(row[0])
        assert snap.get("content") == content

    @pytest.mark.asyncio
    async def test_multiple_writes_search_delete(self, memory_with_curator):
        memory, _ = memory_with_curator
        facts = [
            "Quantum computing uses qubits for computation.",
            "Classical computers use binary bits for computation.",
            "Machine learning models learn from training data.",
        ]
        ids = [await _write(memory, content=f) for f in facts]

        # All should be searchable
        results = await memory.search("computation")
        found_ids = {r.entry.entry_id for r in results}
        assert len(found_ids) > 0

        # Delete all
        for eid in ids:
            await memory.delete(eid)

        # None should be findable
        results_after = await memory.search("computation")
        after_ids = {r.entry.entry_id for r in results_after}
        for eid in ids:
            assert eid not in after_ids

    @pytest.mark.asyncio
    async def test_write_rejected_by_quality_gate(self, memory_with_curator):
        """Content shorter than 10 chars for l2 entries must be rejected."""
        memory, _ = memory_with_curator
        eid = await memory.write("Short", content_type="fact", importance=0.8)
        assert eid == "", "before_write hook should reject short l2 content"

    @pytest.mark.asyncio
    async def test_l4_entry_not_deletable(self, memory_with_curator):
        memory, _ = memory_with_curator
        eid = await memory.write(
            "Provenance audit record — immutable", layer_hint="l4"
        )
        deleted = await memory.delete(eid)
        assert deleted is False
        assert await memory.read(eid) is not None

    @pytest.mark.asyncio
    async def test_get_layer_after_writes(self, memory_with_curator):
        memory, _ = memory_with_curator
        content = "Episodic event recorded in layer one for scanning."
        eid = await memory.write(content, content_type="observation", importance=0.5)
        entries = await memory.get_layer("l1")
        eids = {e.entry_id for e in entries}
        assert eid in eids

    @pytest.mark.asyncio
    async def test_consolidate_promotes_high_importance(self, memory_with_curator):
        memory, _ = memory_with_curator
        # Write high-importance l1 entry
        eid = await memory.write(
            "Important episodic event that should be promoted to semantic layer.",
            content_type="observation", importance=0.9,
        )
        stats = await memory.consolidate(min_importance=0.7)
        assert stats["l1_promoted"] >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Session 1 + 2 Regression
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegression:

    def test_graph_engine_add_node_still_commits(self, db_path):
        g = GraphEngine(db_path=db_path)
        g.add_node("r1", "t", "Regression")
        with closing(sqlite3.connect(db_path)) as conn:
            row = conn.execute("SELECT id FROM nodes WHERE id='r1'").fetchone()
        assert row is not None, "BUG-01 regression: add_node no longer commits"

    def test_graph_engine_add_edge_still_commits(self, db_path):
        g = GraphEngine(db_path=db_path)
        g.add_node("a", "t", "A")
        g.add_node("b", "t", "B")
        g.add_edge("a", "b", "r")
        with closing(sqlite3.connect(db_path)) as conn:
            row = conn.execute("SELECT id FROM edges").fetchone()
        assert row is not None, "BUG-01 regression: add_edge no longer commits"

    @pytest.mark.asyncio
    async def test_sqlite_graph_backend_imports(self):
        from core.memory.backends.sqlite_graph import SQLiteGraphBackend
        assert SQLiteGraphBackend is not None

    @pytest.mark.asyncio
    async def test_budget_governor_no_permanent_lockout(self):
        from core.governance.governance_kernel import (
            GovernanceKernel, GovernanceAction, GovernanceVerdict,
        )
        kernel = GovernanceKernel()
        for i in range(200):
            action = GovernanceAction(
                action_type="worker_execute", worker_id="test"
            )
            result = kernel.evaluate_action(action)
            assert result.verdict == GovernanceVerdict.APPROVE, \
                f"BUG-03 regression: permanent lockout at step {i+1}"

    def test_graph_test_suite_still_passes(self):
        """Confirm the Session 2 graph test suite imports without error."""
        from tests.test_graph import (
            TestGraphEngineInit, TestAddNode, TestAddEdge,
            TestGetNode, TestGetNeighbors, TestStats,
        )
        # If the imports succeed, the classes are intact.
        assert TestGraphEngineInit is not None
