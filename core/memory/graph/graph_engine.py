import sqlite3
import os
import logging
from contextlib import closing
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("ocbrain.memory.graph")

class GraphEngine:
    """
    SQLite-based Knowledge Graph for OCBrain.
    Tracks Entities (Nodes) and Relations (Edges).
    """
    def __init__(self, db_path: str = ".data/memory/graph.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            # Nodes: Entities, Events, Upgrades, etc.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    name TEXT,
                    properties TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Edges: Relationships
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source TEXT,
                    target TEXT,
                    relation TEXT,
                    properties TEXT,
                    FOREIGN KEY(source) REFERENCES nodes(id),
                    FOREIGN KEY(target) REFERENCES nodes(id)
                )
            """)
            conn.commit()

    def add_node(self, node_id: str, node_type: str, name: str, properties: Dict[str, Any] = None):
        import json
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes (id, type, name, properties) VALUES (?, ?, ?, ?)",
                (node_id, node_type, name, json.dumps(properties or {}))
            )

    def add_edge(self, source: str, target: str, relation: str, properties: Dict[str, Any] = None):
        import json
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO edges (source, target, relation, properties) VALUES (?, ?, ?, ?)",
                (source, target, relation, json.dumps(properties or {}))
            )

    def get_neighbors(self, node_id: str) -> List[Tuple[str, str, str]]:
        """Returns (target_id, relation, target_type) for a given node."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT e.target, e.relation, n.type 
                FROM edges e 
                JOIN nodes n ON e.target = n.id 
                WHERE e.source = ?
            """, (node_id,))
            return cursor.fetchall()

    def search_nodes(self, query: str) -> List[Dict[str, Any]]:
        """Simple name-based search."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute("SELECT id, type, name FROM nodes WHERE name LIKE ?", (f"%{query}%",))
            return [{"id": r[0], "type": r[1], "name": r[2]} for r in cursor.fetchall()]

# Global singleton
graph_engine = GraphEngine()
