"""
tests/test_graph.py — Comprehensive Graph Subsystem Tests

Covers:
  GraphEngine          — all public methods, edge cases, persistence
  SQLiteGraphBackend   — async contract, delegation, return types
  GraphBackend ABC     — contract satisfaction
  Concurrent access    — WAL mode, SQLITE_BUSY, no corrupted state
  Determinism          — ORDER BY stability
  Transaction safety   — commit, rollback, idempotency

Session 2 — graph hardening validation.
"""

import asyncio
import os
import sqlite3
import tempfile
import threading
import time
from contextlib import closing
from typing import List

import pytest
import pytest_asyncio

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.memory.graph.graph_engine import GraphEngine, get_graph_engine
from core.memory.backends.sqlite_graph import SQLiteGraphBackend


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "test_graph.db")


@pytest.fixture
def engine(db_path) -> GraphEngine:
    return GraphEngine(db_path=db_path)


@pytest.fixture
def populated_engine(engine) -> GraphEngine:
    """Engine pre-loaded with a small connected graph."""
    engine.add_node("alice",   "person",  "Alice",   {"role": "engineer"})
    engine.add_node("bob",     "person",  "Bob",     {"role": "manager"})
    engine.add_node("charlie", "person",  "Charlie", {})
    engine.add_node("concept", "concept", "Graph DB", {})
    engine.add_edge("alice",   "bob",     "knows",       weight=0.9)
    engine.add_edge("bob",     "charlie", "manages",     weight=1.0)
    engine.add_edge("alice",   "concept", "studies",     weight=0.7)
    return engine


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — GraphEngine: Initialization
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphEngineInit:

    def test_creates_database_file(self, db_path):
        GraphEngine(db_path=db_path)
        assert os.path.exists(db_path)

    def test_creates_parent_directory(self, tmp_path):
        nested = str(tmp_path / "deep" / "nested" / "graph.db")
        GraphEngine(db_path=nested)
        assert os.path.exists(nested)

    def test_bare_filename_no_crash(self, tmp_path):
        """GraphEngine with no directory component must not raise FileNotFoundError."""
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            g = GraphEngine(db_path="bare.db")
            assert os.path.exists("bare.db")
        finally:
            os.chdir(original_dir)

    def test_wal_mode_enabled(self, db_path):
        GraphEngine(db_path=db_path)
        with closing(sqlite3.connect(db_path)) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal", f"Expected WAL, got {mode!r}"

    def test_tables_exist(self, db_path):
        GraphEngine(db_path=db_path)
        with closing(sqlite3.connect(db_path)) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "nodes" in tables
        assert "edges" in tables

    def test_indexes_exist(self, db_path):
        GraphEngine(db_path=db_path)
        with closing(sqlite3.connect(db_path)) as conn:
            indexes = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()}
        assert "idx_edges_source"   in indexes
        assert "idx_edges_target"   in indexes
        assert "idx_edges_relation" in indexes

    def test_reinit_idempotent(self, db_path):
        """Calling __init__ on an existing database must not raise."""
        g1 = GraphEngine(db_path=db_path)
        g1.add_node("n1", "test", "Node1")
        g2 = GraphEngine(db_path=db_path)
        node = g2.get_node("n1")
        assert node is not None
        assert node["name"] == "Node1"

    def test_migration_adds_weight_column(self, tmp_path):
        """Migration must not crash on a database that already has weight."""
        db = str(tmp_path / "migrate.db")
        # Create old-style schema without weight column
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE nodes (
                    id TEXT PRIMARY KEY, type TEXT, name TEXT, properties TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT, target TEXT, relation TEXT, properties TEXT
                )
            """)
            conn.commit()
        # Init should migrate successfully
        g = GraphEngine(db_path=db)
        with closing(sqlite3.connect(db)) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(edges)").fetchall()}
        assert "weight" in cols


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — GraphEngine: add_node
# ═══════════════════════════════════════════════════════════════════════════════

class TestAddNode:

    def test_returns_node_id(self, engine):
        result = engine.add_node("n1", "entity", "Test")
        assert result == "n1", f"add_node must return node_id str, got {result!r}"

    def test_return_type_is_str(self, engine):
        result = engine.add_node("n1", "entity", "Test")
        assert isinstance(result, str)

    def test_node_persisted(self, engine):
        engine.add_node("n1", "concept", "Alpha", {"k": "v"})
        node = engine.get_node("n1")
        assert node is not None
        assert node["id"]   == "n1"
        assert node["type"] == "concept"
        assert node["name"] == "Alpha"
        assert node["properties"] == {"k": "v"}

    def test_none_properties_defaults_to_empty_dict(self, engine):
        engine.add_node("n1", "entity", "X", None)
        node = engine.get_node("n1")
        assert node["properties"] == {}

    def test_empty_properties_stored_cleanly(self, engine):
        engine.add_node("n1", "entity", "X", {})
        node = engine.get_node("n1")
        assert node["properties"] == {}

    def test_complex_properties_round_trip(self, engine):
        props = {"list": [1, 2, 3], "nested": {"a": True}, "null": None}
        engine.add_node("n1", "entity", "Complex", props)
        node = engine.get_node("n1")
        assert node["properties"] == props

    def test_replace_existing_node(self, engine):
        engine.add_node("n1", "old_type", "OldName", {"v": 1})
        engine.add_node("n1", "new_type", "NewName", {"v": 2})
        node = engine.get_node("n1")
        assert node["type"] == "new_type"
        assert node["name"] == "NewName"
        assert node["properties"] == {"v": 2}

    def test_replace_node_count_stays_same(self, engine):
        engine.add_node("n1", "t", "A")
        engine.add_node("n1", "t", "B")
        assert engine.stats()["node_count"] == 1

    def test_unicode_name(self, engine):
        engine.add_node("n1", "entity", "ñoño 日本語 🎉", {"emoji": "👍"})
        node = engine.get_node("n1")
        assert node["name"] == "ñoño 日本語 🎉"
        assert node["properties"] == {"emoji": "👍"}

    def test_empty_node_id_raises(self, engine):
        with pytest.raises(ValueError, match="node_id"):
            engine.add_node("", "entity", "Name")

    def test_none_node_id_raises(self, engine):
        with pytest.raises((ValueError, TypeError)):
            engine.add_node(None, "entity", "Name")  # type: ignore

    def test_large_node_count(self, engine):
        for i in range(500):
            engine.add_node(f"node_{i}", "bulk", f"Node {i}")
        assert engine.stats()["node_count"] == 500


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — GraphEngine: add_edge
# ═══════════════════════════════════════════════════════════════════════════════

class TestAddEdge:

    def test_returns_positive_int(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        eid = engine.add_edge("a", "b", "knows")
        assert isinstance(eid, int)
        assert eid > 0

    def test_sequential_ids_increasing(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        e1 = engine.add_edge("a", "b", "rel1")
        e2 = engine.add_edge("a", "b", "rel2")
        assert e2 > e1

    def test_weight_stored_correctly(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "knows", weight=0.75)
        nbrs = engine.get_neighbors("a")
        assert len(nbrs) == 1
        assert abs(nbrs[0]["weight"] - 0.75) < 1e-9

    def test_default_weight_is_one(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "knows")
        nbrs = engine.get_neighbors("a")
        assert abs(nbrs[0]["weight"] - 1.0) < 1e-9

    def test_zero_weight_stored(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "weak", weight=0.0)
        nbrs = engine.get_neighbors("a")
        assert nbrs[0]["weight"] == 0.0

    def test_properties_round_trip(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        eid = engine.add_edge("a", "b", "knows", properties={"since": 2020})
        with closing(sqlite3.connect(engine.db_path)) as conn:
            row = conn.execute(
                "SELECT properties FROM edges WHERE id=?", (eid,)
            ).fetchone()
        import json
        assert json.loads(row[0]) == {"since": 2020}

    def test_duplicate_edges_allowed(self, engine):
        """Multigraph: same triple can appear multiple times."""
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "knows")
        engine.add_edge("a", "b", "knows")
        nbrs = engine.get_neighbors("a")
        assert len(nbrs) == 2

    def test_self_loop_allowed(self, engine):
        engine.add_node("a", "t", "A")
        eid = engine.add_edge("a", "a", "self_ref")
        assert eid > 0

    def test_empty_source_raises(self, engine):
        with pytest.raises(ValueError, match="source"):
            engine.add_edge("", "b", "knows")

    def test_empty_target_raises(self, engine):
        with pytest.raises(ValueError, match="target"):
            engine.add_edge("a", "", "knows")

    def test_empty_relation_raises(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        with pytest.raises(ValueError, match="relation"):
            engine.add_edge("a", "b", "")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — GraphEngine: get_node
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetNode:

    def test_returns_dict_for_existing_node(self, engine):
        engine.add_node("n1", "entity", "Alpha", {"x": 1})
        result = engine.get_node("n1")
        assert isinstance(result, dict)

    def test_returns_none_for_missing_node(self, engine):
        assert engine.get_node("nonexistent") is None

    def test_returns_none_on_empty_graph(self, engine):
        assert engine.get_node("anything") is None

    def test_required_keys_present(self, engine):
        engine.add_node("n1", "entity", "Alpha")
        node = engine.get_node("n1")
        for key in ("id", "type", "name", "properties", "timestamp"):
            assert key in node, f"Missing key: {key}"

    def test_properties_are_decoded_dict(self, engine):
        engine.add_node("n1", "entity", "X", {"a": 1})
        node = engine.get_node("n1")
        assert isinstance(node["properties"], dict)
        assert node["properties"]["a"] == 1

    def test_timestamp_is_string(self, engine):
        engine.add_node("n1", "entity", "X")
        node = engine.get_node("n1")
        assert isinstance(node["timestamp"], str)
        assert len(node["timestamp"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — GraphEngine: get_neighbors
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetNeighbors:

    def test_returns_direct_neighbors(self, populated_engine):
        nbrs = populated_engine.get_neighbors("alice")
        targets = {n["target_id"] for n in nbrs}
        assert "bob" in targets
        assert "concept" in targets

    def test_returns_empty_for_missing_node(self, engine):
        assert engine.get_neighbors("ghost") == []

    def test_returns_empty_for_isolated_node(self, engine):
        engine.add_node("lone", "entity", "Lonely")
        assert engine.get_neighbors("lone") == []

    def test_relation_filter_exact_match(self, populated_engine):
        nbrs = populated_engine.get_neighbors("alice", relation="knows")
        assert all(n["relation"] == "knows" for n in nbrs)
        assert any(n["target_id"] == "bob" for n in nbrs)

    def test_relation_filter_excludes_others(self, populated_engine):
        nbrs = populated_engine.get_neighbors("alice", relation="knows")
        # "studies" relation should not appear
        assert all(n["relation"] != "studies" for n in nbrs)

    def test_relation_filter_no_match_returns_empty(self, populated_engine):
        nbrs = populated_engine.get_neighbors("alice", relation="nonexistent_rel")
        assert nbrs == []

    def test_limit_applied(self, engine):
        engine.add_node("hub", "entity", "Hub")
        for i in range(10):
            engine.add_node(f"leaf_{i}", "entity", f"Leaf {i}")
            engine.add_edge("hub", f"leaf_{i}", "connects")
        nbrs = engine.get_neighbors("hub", limit=3)
        assert len(nbrs) == 3

    def test_limit_one_returns_single_result(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_node("c", "t", "C")
        engine.add_edge("a", "b", "r")
        engine.add_edge("a", "c", "r")
        nbrs = engine.get_neighbors("a", limit=1)
        assert len(nbrs) == 1

    def test_result_has_required_keys(self, populated_engine):
        nbrs = populated_engine.get_neighbors("alice")
        for n in nbrs:
            for key in ("target_id", "relation", "target_type", "weight"):
                assert key in n, f"Missing key {key} in neighbor dict"

    def test_deterministic_order_repeated_calls(self, populated_engine):
        r1 = populated_engine.get_neighbors("alice")
        r2 = populated_engine.get_neighbors("alice")
        assert r1 == r2

    def test_order_is_insertion_order(self, engine):
        """Results ordered by edge id (insertion order), not node id."""
        engine.add_node("hub", "entity", "Hub")
        engine.add_node("z_node", "entity", "Z")
        engine.add_node("a_node", "entity", "A")
        engine.add_edge("hub", "z_node", "r")  # inserted first
        engine.add_edge("hub", "a_node", "r")  # inserted second
        nbrs = engine.get_neighbors("hub")
        # z_node was inserted first so it comes first despite later alphabetical order
        assert nbrs[0]["target_id"] == "z_node"
        assert nbrs[1]["target_id"] == "a_node"

    def test_orphan_edge_target_not_returned(self, engine):
        """Orphan edges (target node absent) are excluded via JOIN."""
        engine.add_node("src", "entity", "Source")
        # Insert edge directly — bypasses FK (not enforced)
        with closing(sqlite3.connect(engine.db_path)) as conn:
            conn.execute(
                "INSERT INTO edges (source, target, relation, weight, properties) "
                "VALUES ('src', 'ghost_target', 'knows', 1.0, '{}')"
            )
            conn.commit()
        # JOIN on nodes filters out ghost_target
        nbrs = engine.get_neighbors("src")
        assert all(n["target_id"] != "ghost_target" for n in nbrs)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — GraphEngine: search_nodes
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchNodes:

    def test_returns_empty_on_empty_graph(self, engine):
        assert engine.search_nodes("anything") == []

    def test_empty_query_matches_all(self, engine):
        engine.add_node("n1", "t", "Alpha")
        engine.add_node("n2", "t", "Beta")
        results = engine.search_nodes("")
        assert len(results) == 2

    def test_substring_match_case_insensitive(self, engine):
        engine.add_node("n1", "t", "GraphDatabase")
        results = engine.search_nodes("graph")
        assert len(results) == 1
        assert results[0]["id"] == "n1"

    def test_no_match_returns_empty(self, engine):
        engine.add_node("n1", "t", "Alpha")
        assert engine.search_nodes("zzz_never_matches") == []

    def test_limit_applied(self, engine):
        for i in range(20):
            engine.add_node(f"n{i}", "t", f"Node {i}")
        results = engine.search_nodes("Node", limit=5)
        assert len(results) == 5

    def test_limit_one_returns_single(self, engine):
        for i in range(3):
            engine.add_node(f"n{i}", "t", f"Alpha {i}")
        results = engine.search_nodes("Alpha", limit=1)
        assert len(results) == 1

    def test_result_has_required_keys(self, engine):
        engine.add_node("n1", "concept", "Test")
        results = engine.search_nodes("Test")
        assert len(results) == 1
        for key in ("id", "type", "name"):
            assert key in results[0]

    def test_alphabetical_order(self, engine):
        """Results must be ordered name ASC, id ASC — not insertion order."""
        engine.add_node("id_z", "t", "Zeta")
        engine.add_node("id_a", "t", "Alpha")
        engine.add_node("id_m", "t", "Mu")
        results = engine.search_nodes("")
        names = [r["name"] for r in results]
        assert names == sorted(names), f"Not alphabetical: {names}"

    def test_deterministic_on_repeated_calls(self, engine):
        for i in range(10):
            engine.add_node(f"n{i}", "t", f"Node {i}")
        r1 = engine.search_nodes("Node")
        r2 = engine.search_nodes("Node")
        assert r1 == r2

    def test_unicode_query(self, engine):
        engine.add_node("n1", "t", "日本語テスト")
        results = engine.search_nodes("日本")
        assert len(results) == 1
        assert results[0]["name"] == "日本語テスト"

    def test_large_graph_search(self, engine):
        for i in range(1000):
            engine.add_node(f"n{i:04d}", "bulk", f"Bulk Node {i}")
        results = engine.search_nodes("Bulk Node 1", limit=50)
        # "Bulk Node 1" matches "Bulk Node 1", "Bulk Node 10"-"Bulk Node 19",
        # "Bulk Node 100"-"Bulk Node 199" etc.
        assert len(results) <= 50
        assert all("Bulk Node 1" in r["name"] for r in results)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — GraphEngine: find_contradictions
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindContradictions:

    def test_empty_graph_returns_empty(self, engine):
        assert engine.find_contradictions() == []

    def test_no_contradictions_returns_empty(self, populated_engine):
        # populated_engine has no 'contradicts' edges
        assert populated_engine.find_contradictions() == []

    def test_one_way_edge_not_contradiction(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "contradicts")
        assert engine.find_contradictions() == []

    def test_mutual_edge_is_contradiction(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "contradicts")
        engine.add_edge("b", "a", "contradicts")
        results = engine.find_contradictions()
        assert len(results) == 1
        pair = results[0]
        assert pair["node_a"] < pair["node_b"]  # deduplication: a < b
        assert set([pair["node_a"], pair["node_b"]]) == {"a", "b"}

    def test_pair_returned_once(self, engine):
        """Each (A, B) contradiction must appear exactly once, not as (A,B) and (B,A)."""
        engine.add_node("x", "t", "X")
        engine.add_node("y", "t", "Y")
        engine.add_edge("x", "y", "contradicts")
        engine.add_edge("y", "x", "contradicts")
        results = engine.find_contradictions()
        assert len(results) == 1

    def test_multiple_contradictions(self, engine):
        for ch in "abcd":
            engine.add_node(ch, "t", ch.upper())
        # a↔b contradiction
        engine.add_edge("a", "b", "contradicts")
        engine.add_edge("b", "a", "contradicts")
        # c↔d contradiction
        engine.add_edge("c", "d", "contradicts")
        engine.add_edge("d", "c", "contradicts")
        results = engine.find_contradictions()
        assert len(results) == 2

    def test_non_contradicts_edges_ignored(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "supports")
        engine.add_edge("b", "a", "supports")
        assert engine.find_contradictions() == []

    def test_deterministic_order(self, engine):
        for ch in "abcdef":
            engine.add_node(ch, "t", ch.upper())
        engine.add_edge("a", "b", "contradicts"); engine.add_edge("b", "a", "contradicts")
        engine.add_edge("c", "d", "contradicts"); engine.add_edge("d", "c", "contradicts")
        engine.add_edge("e", "f", "contradicts"); engine.add_edge("f", "e", "contradicts")
        r1 = engine.find_contradictions()
        r2 = engine.find_contradictions()
        assert r1 == r2
        # Additionally verify alphabetical ordering
        node_as = [r["node_a"] for r in r1]
        assert node_as == sorted(node_as)

    def test_result_has_required_keys(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "contradicts")
        engine.add_edge("b", "a", "contradicts")
        result = engine.find_contradictions()[0]
        assert "node_a" in result
        assert "node_b" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — GraphEngine: stats
# ═══════════════════════════════════════════════════════════════════════════════

class TestStats:

    def test_empty_graph(self, engine):
        s = engine.stats()
        assert s["node_count"] == 0
        assert s["edge_count"] == 0

    def test_required_keys(self, engine):
        s = engine.stats()
        for key in ("node_count", "edge_count", "db_size_bytes", "db_path"):
            assert key in s, f"Missing key: {key}"

    def test_counts_correct(self, engine):
        engine.add_node("n1", "t", "A")
        engine.add_node("n2", "t", "B")
        engine.add_edge("n1", "n2", "r")
        s = engine.stats()
        assert s["node_count"] == 2
        assert s["edge_count"] == 1

    def test_node_count_type(self, engine):
        s = engine.stats()
        assert isinstance(s["node_count"], int)

    def test_edge_count_type(self, engine):
        s = engine.stats()
        assert isinstance(s["edge_count"], int)

    def test_db_size_positive_after_writes(self, engine):
        engine.add_node("n1", "t", "A")
        s = engine.stats()
        assert s["db_size_bytes"] > 0

    def test_db_path_matches(self, engine):
        assert engine.stats()["db_path"] == engine.db_path

    def test_counts_update_after_replace(self, engine):
        engine.add_node("n1", "t", "A")
        engine.add_node("n1", "t", "B")   # replace
        assert engine.stats()["node_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — GraphEngine: Persistence
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistence:

    def test_data_survives_new_engine_instance(self, db_path):
        g1 = GraphEngine(db_path=db_path)
        g1.add_node("n1", "entity", "Alpha", {"v": 42})
        g1.add_node("n2", "entity", "Beta")
        g1.add_edge("n1", "n2", "knows", weight=0.5)

        # Create a completely new engine instance on the same file
        g2 = GraphEngine(db_path=db_path)
        node = g2.get_node("n1")
        assert node is not None
        assert node["properties"]["v"] == 42
        assert g2.stats()["node_count"] == 2
        assert g2.stats()["edge_count"] == 1
        nbrs = g2.get_neighbors("n1")
        assert len(nbrs) == 1
        assert abs(nbrs[0]["weight"] - 0.5) < 1e-9

    def test_contradiction_data_survives_restart(self, db_path):
        g1 = GraphEngine(db_path=db_path)
        g1.add_node("a", "t", "A")
        g1.add_node("b", "t", "B")
        g1.add_edge("a", "b", "contradicts")
        g1.add_edge("b", "a", "contradicts")

        g2 = GraphEngine(db_path=db_path)
        results = g2.find_contradictions()
        assert len(results) == 1

    def test_node_replace_preserves_existing_edges(self, engine):
        """Replacing a node with add_node must not delete its edges."""
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        engine.add_edge("a", "b", "knows")
        # Replace node a
        engine.add_node("a", "t", "A_updated")
        nbrs = engine.get_neighbors("a")
        assert len(nbrs) == 1
        assert nbrs[0]["target_id"] == "b"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — GraphEngine: Transaction Safety
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransactionSafety:

    def test_add_node_committed(self, engine):
        engine.add_node("n1", "t", "X")
        with closing(sqlite3.connect(engine.db_path)) as conn:
            row = conn.execute("SELECT id FROM nodes WHERE id='n1'").fetchone()
        assert row is not None

    def test_add_edge_committed(self, engine):
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        eid = engine.add_edge("a", "b", "knows")
        with closing(sqlite3.connect(engine.db_path)) as conn:
            row = conn.execute("SELECT id FROM edges WHERE id=?", (eid,)).fetchone()
        assert row is not None

    def test_repeated_add_node_idempotent_count(self, engine):
        for _ in range(5):
            engine.add_node("n1", "t", "X")
        assert engine.stats()["node_count"] == 1

    def test_repeated_add_edge_grows_count(self, engine):
        """add_edge is NOT idempotent — each call creates a distinct row."""
        engine.add_node("a", "t", "A")
        engine.add_node("b", "t", "B")
        for _ in range(3):
            engine.add_edge("a", "b", "r")
        assert engine.stats()["edge_count"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — GraphEngine: Concurrent Access
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcurrentAccess:

    def _run_threaded(self, fns: List, expected_errors=()) -> List[Exception]:
        """Run each callable in its own thread; collect any unexpected exceptions."""
        errors: List[Exception] = []
        threads = []

        def wrapper(fn):
            try:
                fn()
            except expected_errors:
                pass  # tolerated
            except Exception as e:
                errors.append(e)

        for fn in fns:
            t = threading.Thread(target=wrapper, args=(fn,), daemon=True)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        return errors

    def test_concurrent_node_creation(self, engine):
        """50 threads each insert a distinct node — no lost writes, no crashes."""
        N = 50
        fns = [
            (lambda i: lambda: engine.add_node(f"node_{i}", "bulk", f"N{i}"))(i)
            for i in range(N)
        ]
        errors = self._run_threaded(fns)
        assert errors == [], f"Unexpected errors: {errors}"
        assert engine.stats()["node_count"] == N

    def test_concurrent_edge_creation(self, engine):
        """50 threads each insert a distinct edge — no lost writes."""
        N = 50
        engine.add_node("src", "t", "Source")
        for i in range(N):
            engine.add_node(f"tgt_{i}", "t", f"Target {i}")
        fns = [
            (lambda i: lambda: engine.add_edge("src", f"tgt_{i}", "connects"))(i)
            for i in range(N)
        ]
        errors = self._run_threaded(fns)
        assert errors == [], f"Unexpected errors: {errors}"
        assert engine.stats()["edge_count"] == N

    def test_concurrent_reads_alongside_writes(self, engine):
        """Mixed read/write load: no deadlocks, no corrupted state."""
        N = 30
        for i in range(N):
            engine.add_node(f"pre_{i}", "t", f"Pre {i}")

        def read_fn():
            for _ in range(10):
                engine.search_nodes("Pre")
                engine.stats()

        def write_fn(i):
            engine.add_node(f"new_{i}", "t", f"New {i}")

        fns = ([read_fn] * 5) + [
            (lambda i: lambda: write_fn(i))(i) for i in range(10)
        ]
        errors = self._run_threaded(fns)
        assert errors == [], f"Errors under mixed load: {errors}"

    def test_concurrent_contradiction_check(self, engine):
        """find_contradictions under concurrent writes must not crash."""
        for ch in "abcdefghij":
            engine.add_node(ch, "t", ch.upper())
        # Build a web of contradictions
        pairs = [("a","b"), ("c","d"), ("e","f"), ("g","h"), ("i","j")]
        for x, y in pairs:
            engine.add_edge(x, y, "contradicts")
            engine.add_edge(y, x, "contradicts")

        fns = ([engine.find_contradictions] * 20) + [
            (lambda x, y: lambda: engine.add_edge(x, y, "supports"))(x, y)
            for x, y in pairs
        ]
        errors = self._run_threaded(fns)
        assert errors == [], f"Errors during concurrent contradiction check: {errors}"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — get_graph_engine() factory
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetGraphEngineFactory:

    def test_returns_graph_engine_instance(self):
        g = get_graph_engine()
        assert isinstance(g, GraphEngine)

    def test_returns_same_singleton(self):
        g1 = get_graph_engine()
        g2 = get_graph_engine()
        assert g1 is g2

    def test_singleton_is_module_level_instance(self):
        from core.memory.graph import graph_engine as ge_mod
        g = get_graph_engine()
        assert g is ge_mod.graph_engine


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — SQLiteGraphBackend
# ═══════════════════════════════════════════════════════════════════════════════

class TestSQLiteGraphBackend:

    @pytest.fixture
    def backend(self, db_path) -> SQLiteGraphBackend:
        return SQLiteGraphBackend(db_path=db_path)

    @pytest.mark.asyncio
    async def test_add_node_returns_str(self, backend):
        result = await backend.add_node("n1", "entity", "Alpha")
        assert isinstance(result, str)
        assert result == "n1"

    @pytest.mark.asyncio
    async def test_add_node_persisted(self, backend):
        await backend.add_node("n1", "concept", "Graph", {"k": "v"})
        node = await backend.get_node("n1")
        assert node is not None
        assert node["name"] == "Graph"

    @pytest.mark.asyncio
    async def test_get_node_missing_returns_none(self, backend):
        result = await backend.get_node("ghost")
        assert result is None

    @pytest.mark.asyncio
    async def test_add_edge_returns_int(self, backend):
        await backend.add_node("a", "t", "A")
        await backend.add_node("b", "t", "B")
        eid = await backend.add_edge("a", "b", "knows", weight=0.8)
        assert isinstance(eid, int)
        assert eid > 0

    @pytest.mark.asyncio
    async def test_get_neighbors_filters_by_relation(self, backend):
        await backend.add_node("a", "t", "A")
        await backend.add_node("b", "t", "B")
        await backend.add_node("c", "t", "C")
        await backend.add_edge("a", "b", "knows")
        await backend.add_edge("a", "c", "manages")
        nbrs = await backend.get_neighbors("a", relation="knows")
        assert len(nbrs) == 1
        assert nbrs[0]["target_id"] == "b"

    @pytest.mark.asyncio
    async def test_get_neighbors_limit(self, backend):
        await backend.add_node("hub", "t", "Hub")
        for i in range(10):
            await backend.add_node(f"leaf_{i}", "t", f"Leaf {i}")
            await backend.add_edge("hub", f"leaf_{i}", "r")
        nbrs = await backend.get_neighbors("hub", limit=3)
        assert len(nbrs) == 3

    @pytest.mark.asyncio
    async def test_search_nodes_limit(self, backend):
        for i in range(20):
            await backend.add_node(f"n{i}", "t", f"Node {i}")
        results = await backend.search_nodes("Node", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_nodes_alphabetical(self, backend):
        await backend.add_node("id_z", "t", "Zeta")
        await backend.add_node("id_a", "t", "Alpha")
        results = await backend.search_nodes("")
        names = [r["name"] for r in results]
        assert names == sorted(names)

    @pytest.mark.asyncio
    async def test_find_contradictions_detected(self, backend):
        await backend.add_node("a", "t", "A")
        await backend.add_node("b", "t", "B")
        await backend.add_edge("a", "b", "contradicts")
        await backend.add_edge("b", "a", "contradicts")
        results = await backend.find_contradictions()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_find_contradictions_empty_graph(self, backend):
        results = await backend.find_contradictions()
        assert results == []

    @pytest.mark.asyncio
    async def test_stats_has_backend_key(self, backend):
        s = await backend.stats()
        assert s.get("backend") == "SQLiteGraphBackend"

    @pytest.mark.asyncio
    async def test_stats_correct_counts(self, backend):
        await backend.add_node("n1", "t", "A")
        await backend.add_node("n2", "t", "B")
        await backend.add_edge("n1", "n2", "r")
        s = await backend.stats()
        assert s["node_count"] == 2
        assert s["edge_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_node_id_raises_value_error(self, backend):
        with pytest.raises(ValueError):
            await backend.add_node("", "entity", "Name")

    @pytest.mark.asyncio
    async def test_empty_source_raises_value_error(self, backend):
        with pytest.raises(ValueError):
            await backend.add_edge("", "b", "knows")

    @pytest.mark.asyncio
    async def test_engine_property_returns_graph_engine(self, backend):
        assert isinstance(backend.engine, GraphEngine)

    @pytest.mark.asyncio
    async def test_run_uses_running_loop(self, backend):
        """_run() must call asyncio.get_running_loop(), not get_event_loop()."""
        import inspect, ast, textwrap
        raw = inspect.getsource(backend._run)
        src = textwrap.dedent(raw)
        tree = ast.parse(src)
        calls = [
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        ]
        assert "get_running_loop" in calls, \
            f"_run() must call get_running_loop(); attrs found: {calls}"
        assert "get_event_loop" not in calls, \
            f"_run() must not call get_event_loop(); attrs found: {calls}"

    @pytest.mark.asyncio
    async def test_concurrent_async_operations(self, backend):
        """Concurrent coroutines writing to the same graph must not crash."""
        await backend.add_node("hub", "t", "Hub")

        async def create_leaf(i: int):
            await backend.add_node(f"leaf_{i}", "t", f"Leaf {i}")
            await backend.add_edge("hub", f"leaf_{i}", "connected")

        await asyncio.gather(*[create_leaf(i) for i in range(30)])
        s = await backend.stats()
        # hub + 30 leaves
        assert s["node_count"] == 31
        assert s["edge_count"] == 30


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14 — GraphBackend ABC Contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphBackendContract:
    """Verify SQLiteGraphBackend satisfies all GraphBackend abstract methods."""

    def test_all_abstract_methods_implemented(self):
        import inspect, abc
        from core.memory.backends.base import GraphBackend
        abstract_methods = {
            name for name, val in inspect.getmembers(GraphBackend)
            if getattr(val, "__isabstractmethod__", False)
        }
        backend_methods = set(dir(SQLiteGraphBackend))
        missing = abstract_methods - backend_methods
        assert missing == set(), f"SQLiteGraphBackend missing abstract methods: {missing}"

    def test_import_succeeds(self):
        from core.memory.backends.sqlite_graph import SQLiteGraphBackend as SGB
        assert SGB is not None

    def test_can_instantiate_without_error(self, db_path):
        backend = SQLiteGraphBackend(db_path=db_path)
        assert backend is not None
