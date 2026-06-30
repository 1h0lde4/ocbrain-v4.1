"""
core/memory/graph/graph_engine.py — SQLite Knowledge Graph

Session 1 fixes (BUG-01, BUG-02):
  - add_node() / add_edge() commit writes
  - get_graph_engine() factory added
  - Missing methods added: get_node(), find_contradictions(), stats()
  - Signature gaps filled: weight on add_edge(), relation/limit on
    get_neighbors(), limit on search_nodes()
  - WAL mode + indexes

Session 2 hardening:
  - add_node() returns node_id (str) — satisfies GraphBackend ABC contract
  - ValueError raised for empty node_id / source / target / relation
  - os.makedirs guard for bare-filename db_path (no directory component)
  - _connect() helper: consistent timeout=10.0 on every connection
  - ORDER BY on get_neighbors (e.id ASC), search_nodes (name ASC, id ASC),
    find_contradictions (node_a ASC, node_b ASC) — deterministic output
  - Multigraph edges documented (duplicate edges are intentionally allowed)
"""

import json
import os
import sqlite3
import logging
from contextlib import closing
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ocbrain.memory.graph")


# ── Parameter validation helper ───────────────────────────────────────────────

def _require_nonempty(value: str, name: str) -> None:
    """Raise ValueError when *value* is empty or None."""
    if not value:
        raise ValueError(f"GraphEngine: {name!r} must be a non-empty string, got {value!r}")


class GraphEngine:
    """
    SQLite-based Knowledge Graph for OCBrain.

    Stores Entities as Nodes and Relations as Edges in two SQLite tables.
    WAL journal mode enables concurrent reads alongside single-writer updates.

    Design notes:
      - Multigraph: add_edge() allows duplicate (source, target, relation) triples.
        Each call creates a distinct edge row. Callers that want upsert semantics
        must implement that at a higher layer.
      - Foreign keys: NOT enforced at the SQLite level (PRAGMA foreign_keys is
        not set). Orphan edges can exist. This is intentional — FK enforcement
        is a higher-layer concern and adds per-connection overhead.
      - Thread safety: each method opens and closes its own connection.  SQLite
        WAL mode allows concurrent readers; writes are serialised by SQLite's
        file lock with a 10-second busy timeout.
    """

    def __init__(self, db_path: str = ".data/memory/graph.db") -> None:
        self.db_path = db_path
        # Guard: os.path.dirname("bare_name.db") == "" → os.makedirs("") raises
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """Return a new SQLite connection with production settings.

        timeout=10.0 prevents immediate SQLITE_BUSY failures under concurrent
        write load; WAL mode was set at init time and persists in the file.
        """
        return sqlite3.connect(self.db_path, timeout=10.0)

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id         TEXT PRIMARY KEY,
                    type       TEXT NOT NULL DEFAULT '',
                    name       TEXT NOT NULL DEFAULT '',
                    properties TEXT NOT NULL DEFAULT '{}',
                    timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    source     TEXT NOT NULL,
                    target     TEXT NOT NULL,
                    relation   TEXT NOT NULL,
                    weight     REAL NOT NULL DEFAULT 1.0,
                    properties TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(source) REFERENCES nodes(id),
                    FOREIGN KEY(target) REFERENCES nodes(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_source   ON edges(source)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_target   ON edges(target)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation)"
            )
            conn.commit()

            # Migrate: add weight column to databases that predate Session 1.
            try:
                conn.execute(
                    "ALTER TABLE edges ADD COLUMN weight REAL NOT NULL DEFAULT 1.0"
                )
                conn.commit()
                logger.info("GraphEngine: migrated edges table — added weight column")
            except sqlite3.OperationalError:
                pass  # Column already present — expected after first migration.

    # ── Write operations ──────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert or replace a node.

        Returns:
            node_id — the identifier that was written (satisfies ABC str return).

        Raises:
            ValueError: if node_id is empty or None.
        """
        _require_nonempty(node_id, "node_id")
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes (id, type, name, properties) "
                "VALUES (?, ?, ?, ?)",
                (node_id, node_type or "", name or "", json.dumps(properties or {})),
            )
            conn.commit()
        return node_id

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert an edge and return its auto-incremented row id.

        Note: multigraph — duplicate (source, target, relation) triples each
        produce a distinct edge row.  There is no deduplication at this layer.

        Returns:
            Positive integer row id of the inserted edge.

        Raises:
            ValueError: if source, target, or relation is empty.
        """
        _require_nonempty(source,   "source")
        _require_nonempty(target,   "target")
        _require_nonempty(relation, "relation")
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "INSERT INTO edges (source, target, relation, weight, properties) "
                "VALUES (?, ?, ?, ?, ?)",
                (source, target, relation, float(weight), json.dumps(properties or {})),
            )
            conn.commit()
            return cursor.lastrowid or 0

    # ── Read operations ───────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single node by id, or None if not found.

        Returns:
            Dict with keys: id, type, name, properties (decoded), timestamp.
            None if node_id does not exist.
        """
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, type, name, properties, timestamp "
                "FROM nodes WHERE id = ?",
                (node_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id":         row["id"],
            "type":       row["type"],
            "name":       row["name"],
            "properties": json.loads(row["properties"] or "{}"),
            "timestamp":  row["timestamp"],
        }

    def get_neighbors(
        self,
        node_id: str,
        relation: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return neighbour nodes reachable from node_id via outgoing edges.

        Results are ordered by edge insertion order (e.id ASC), which is
        stable and deterministic across identical databases.

        Args:
            node_id:  Source node identifier. Non-existent nodes return [].
            relation: Optional relation type filter (exact match).
            limit:    Maximum results. Clamped to 1 minimum.

        Returns:
            List of dicts: target_id, relation, target_type, weight.
        """
        limit = max(1, int(limit))
        params: List[Any] = [node_id]
        relation_clause = ""
        if relation is not None:
            relation_clause = "AND e.relation = ?"
            params.append(relation)
        params.append(limit)

        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT e.target, e.relation, n.type, e.weight
                FROM   edges e
                JOIN   nodes n ON e.target = n.id
                WHERE  e.source = ? {relation_clause}
                ORDER  BY e.id ASC
                LIMIT  ?
                """,
                params,
            ).fetchall()

        return [
            {
                "target_id":   r[0],
                "relation":    r[1],
                "target_type": r[2],
                "weight":      r[3],
            }
            for r in rows
        ]

    def search_nodes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Case-insensitive substring search across node names.

        Results are ordered alphabetically (name ASC, id ASC) for deterministic,
        user-friendly output regardless of insertion order.

        Args:
            query: Substring to search in node names. Empty string matches all.
            limit: Maximum results. Clamped to 1 minimum.

        Returns:
            List of dicts: id, type, name.
        """
        limit = max(1, int(limit))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, type, name FROM nodes "
                "WHERE  name LIKE ? "
                "ORDER  BY name ASC, id ASC "
                "LIMIT  ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [{"id": r[0], "type": r[1], "name": r[2]} for r in rows]

    def find_contradictions(self) -> List[Dict[str, Any]]:
        """Return mutually-contradicting node pairs, ordered deterministically.

        A contradiction exists when node A has a 'contradicts' edge to B
        AND node B has a 'contradicts' edge back to A.  Each pair is returned
        exactly once (node_a < node_b lexicographically).

        Results are ordered by (node_a ASC, node_b ASC) for deterministic output.

        Returns:
            List of dicts: node_a (str), node_b (str).
            Empty list when graph is empty or no contradictions exist.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT a.source AS node_a, a.target AS node_b
                FROM   edges a
                JOIN   edges b
                         ON  a.source = b.target
                         AND a.target = b.source
                WHERE  a.relation = 'contradicts'
                  AND  b.relation = 'contradicts'
                  AND  a.source < a.target
                ORDER  BY node_a ASC, node_b ASC
                """
            ).fetchall()
        return [{"node_a": r[0], "node_b": r[1]} for r in rows]

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its incident edges.

        Incident edges (where node_id appears as source OR target) are removed
        first to maintain logical graph consistency.  SQLite foreign-key
        enforcement is not relied upon (not enabled per-connection).

        Returns:
            True  — node existed and was deleted.
            False — node not found; no-op, no write performed.
        """
        with closing(self._connect()) as conn:
            exists = conn.execute(
                "SELECT 1 FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            if not exists:
                return False
            conn.execute(
                "DELETE FROM edges WHERE source = ? OR target = ?",
                (node_id, node_id),
            )
            conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            conn.commit()
        return True

    def stats(self) -> Dict[str, Any]:
        """Return graph statistics.

        Both counts are read within a single connection to eliminate the
        inconsistency window between two separate queries.

        Returns:
            Dict: node_count (int), edge_count (int),
                  db_size_bytes (int), db_path (str).
        """
        with closing(self._connect()) as conn:
            node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

        try:
            db_size_bytes = os.path.getsize(self.db_path)
        except OSError:
            db_size_bytes = 0

        return {
            "node_count":    node_count,
            "edge_count":    edge_count,
            "db_size_bytes": db_size_bytes,
            "db_path":       self.db_path,
        }


# ── Module-level singleton + factory ─────────────────────────────────────────

graph_engine = GraphEngine()


def get_graph_engine() -> GraphEngine:
    """Return the process-level GraphEngine singleton.

    Architecture:
        Mirrors get_unified_memory() / get_governance_kernel() pattern.
        SQLiteGraphBackend uses this factory so it never imports the singleton
        directly, decoupling itself from the default db_path.

        Callers that need an isolated graph (tests, per-user graphs) should
        instantiate GraphEngine(db_path=...) directly.
    """
    return graph_engine
