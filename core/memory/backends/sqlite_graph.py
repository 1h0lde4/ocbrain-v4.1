"""
core/memory/backends/sqlite_graph.py — SQLiteGraphBackend (L3 Graph)

Thin async wrapper around the synchronous GraphEngine.
Follows the run_in_executor pattern (§5, Issue 9) — no blocking
calls on the event loop.

Design: delegates all operations to GraphEngine. No new SQL here.
GraphEngine itself is not modified (per migration constraint 3).

Upgrade path: replace with FalkorGraphBackend at Phase 5+
when graph exceeds ~500K edges.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.memory.backends.base import GraphBackend
from core.memory.graph.graph_engine import GraphEngine, get_graph_engine

logger = logging.getLogger("ocbrain.memory.backends.sqlite_graph")


class SQLiteGraphBackend(GraphBackend):
    """
    GraphBackend implementation backed by the existing SQLite GraphEngine.

    All synchronous GraphEngine calls are dispatched to a thread executor
    so they never block the asyncio event loop.

    This is the L3 layer backend. In v4.3.5 it will be the primary
    storage for entity-relationship knowledge and mutual indexing.
    """

    def __init__(self, db_path: str = ".data/memory/graph.db"):
        self._engine = GraphEngine(db_path=db_path)
        logger.info("SQLiteGraphBackend ready: %s", db_path)

    async def _run(self, fn):
        """Dispatch synchronous fn to thread executor."""
        return await asyncio.get_event_loop().run_in_executor(None, fn)

    async def add_node(self, node_id: str, node_type: str, name: str,
                        properties: Optional[Dict[str, Any]] = None) -> str:
        return await self._run(
            lambda: self._engine.add_node(
                node_id=node_id, node_type=node_type,
                name=name, properties=properties or {}
            )
        )

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return await self._run(lambda: self._engine.get_node(node_id))

    async def add_edge(self, source: str, target: str, relation: str,
                        weight: float = 1.0,
                        properties: Optional[Dict[str, Any]] = None) -> int:
        return await self._run(
            lambda: self._engine.add_edge(
                source=source, target=target,
                relation=relation, weight=weight,
                properties=properties or {}
            )
        )

    async def get_neighbors(self, node_id: str,
                             relation: Optional[str] = None,
                             limit: int = 50) -> List[Dict[str, Any]]:
        return await self._run(
            lambda: self._engine.get_neighbors(
                node_id=node_id, relation=relation, limit=limit
            )
        )

    async def search_nodes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await self._run(
            lambda: self._engine.search_nodes(query=query, limit=limit)
        )

    async def find_contradictions(self) -> List[Dict[str, Any]]:
        return await self._run(self._engine.find_contradictions)

    async def stats(self) -> Dict[str, Any]:
        base = await self._run(self._engine.stats)
        return {"backend": "SQLiteGraphBackend", **base}

    @property
    def engine(self) -> GraphEngine:
        """Direct access to underlying engine (for MutualIndexer compatibility)."""
        return self._engine
