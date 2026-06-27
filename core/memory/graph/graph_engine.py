"""
core/memory/graph/graph_engine.py — SQLite Knowledge Graph

BUG-01 FIX: add_node() and add_edge() now call conn.commit().
BUG-02 FIX: Added get_graph_engine() factory, get_node(), find_contradictions(),
             stats(), weight param on add_edge(), relation/limit on get_neighbors(),
             limit on search_nodes(). WAL mode enabled. Weight column added to edges.
"""

import json
import os
import sqlite3
import logging
from contextlib import closing
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ocbrain.memory.graph")


class GraphEngine:
    """
    SQLite-based Knowledge Graph for OCBrain.
    Tracks Entities (Nodes) and Relations (Edges).

    All write methods commit their transactions explicitly (BUG-01 fix).
    WAL journal mode is enabled for concurrent read access.
    """

    def __init__(self, db_path: str = ".data/memory/graph.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id         TEXT PRIMARY KEY,
                    type       TEXT,
                    name       TEXT,
                    properties TEXT,
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
                    properties TEXT,
                    FOREIGN KEY(source) REFERENCES nodes(id),
                    FOREIGN KEY(target) REFERENCES nodes(id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation)"
            )
            conn.commit()

            # Migrate: add weight column to existing databases that predate BUG-02 fix.
            try:
                conn.execute("ALTER TABLE edges ADD COLUMN weight REAL NOT NULL DEFAULT 1.0")
                conn.commit()
                logger.info("GraphEngine: migrated edges table — added weight column")
            except sqlite3.OperationalError:
                pass  # Column already exists — normal on all runs after first migration.

    # ── Write operations ──────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert or replace a node.  BUG-01: conn.commit() ensures durability."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes (id, type, name, properties) "
                "VALUES (?, ?, ?, ?)",
                (node_id, node_type, name, json.dumps(properties or {})),
            )
            conn.commit()  # BUG-01 FIX: was missing, causing silent rollback on close

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert an edge and return its row id.  BUG-01: conn.commit() ensures durability."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute(
                "INSERT INTO edges (source, target, relation, weight, properties) "
                "VALUES (?, ?, ?, ?, ?)",
                (source, target, relation, weight, json.dumps(properties or {})),
            )
            conn.commit()  # BUG-01 FIX: was missing, causing silent rollback on close
            return cursor.lastrowid or 0

    # ── Read operations ───────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single node by id, or None if not found."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, type, name, properties, timestamp FROM nodes WHERE id = ?",
                (node_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": row["id"],
                "type": row["type"],
                "name": row["name"],
                "properties": json.loads(row["properties"] or "{}"),
                "timestamp": row["timestamp"],
            }

    def get_neighbors(
        self,
        node_id: str,
        relation: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return neighbour nodes reachable from node_id via outgoing edges.

        Args:
            node_id:  Source node identifier.
            relation: Optional relation type filter.
            limit:    Maximum number of results.

        Returns:
            List of dicts with keys: target_id, relation, target_type, weight.
        """
        params: List[Any] = [node_id]
        relation_clause = ""
        if relation is not None:
            relation_clause = "AND e.relation = ?"
            params.append(relation)
        params.append(limit)

        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute(
                f"""
                SELECT e.target, e.relation, n.type, e.weight
                FROM edges e
                JOIN nodes n ON e.target = n.id
                WHERE e.source = ? {relation_clause}
                LIMIT ?
                """,
                params,
            )
            return [
                {
                    "target_id": r[0],
                    "relation":  r[1],
                    "target_type": r[2],
                    "weight":    r[3],
                }
                for r in cursor.fetchall()
            ]

    def search_nodes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Case-insensitive substring search on node name.

        Args:
            query: Search string.
            limit: Maximum number of results.

        Returns:
            List of dicts with keys: id, type, name.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT id, type, name FROM nodes WHERE name LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            )
            return [{"id": r[0], "type": r[1], "name": r[2]} for r in cursor.fetchall()]

    def find_contradictions(self) -> List[Dict[str, Any]]:
        """Return pairs of nodes that mutually assert a contradicts relation.

        A contradiction exists when node A has a 'contradicts' edge to node B
        AND node B has a 'contradicts' edge back to node A.

        Returns:
            List of dicts with keys: node_a, node_b, detected at both ends.
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT a.source AS node_a, a.target AS node_b
                FROM edges a
                JOIN edges b
                  ON a.source = b.target
                 AND a.target = b.source
                WHERE a.relation = 'contradicts'
                  AND b.relation = 'contradicts'
                  AND a.source < a.target
                """
            ).fetchall()
            return [{"node_a": r[0], "node_b": r[1]} for r in rows]

    def stats(self) -> Dict[str, Any]:
        """Return graph statistics: node count, edge count, db file size."""
        with closing(sqlite3.connect(self.db_path)) as conn:
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
        Mirrors the get_unified_memory() / get_governance_kernel() pattern.
        SQLiteGraphBackend uses this factory so it never imports the singleton
        directly (avoids tight coupling to the default db_path).
    """
    return graph_engine
