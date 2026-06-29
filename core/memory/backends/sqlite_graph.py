"""
core/memory/backends/sqlite_graph.py — SQLiteGraphBackend (L3 Graph)

Thin async wrapper around the synchronous GraphEngine.
All blocking calls are dispatched via run_in_executor so the asyncio
event loop is never blocked.

Session 2 hardening:
  - _run() uses asyncio.get_running_loop() (not deprecated get_event_loop())
  - add_node() return annotation corrected to str (was implicit via engine)
  - Docstrings updated to match GraphEngine contract

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
    GraphBackend implementation backed by the SQLite GraphEngine.

    All synchronous GraphEngine calls are dispatched to a thread pool
    executor so they never block the asyncio event loop.

    Thread safety: GraphEngine opens a new SQLite connection per operation
    with WAL mode and a 10-second busy timeout.  Concurrent calls from
    asyncio coroutines are safe; SQLite serialises concurrent writers.
    """

    def __init__(self, db_path: str = ".data/memory/graph.db") -> None:
        self._engine = GraphEngine(db_path=db_path)
        logger.info("SQLiteGraphBackend ready: %s", db_path)

    async def _run(self, fn):
        """Dispatch synchronous *fn* to thread executor.

        Uses get_running_loop() — correct API inside a coroutine, avoids
        the deprecation warning emitted by get_event_loop() in Python 3.10+.
        """
        return await asyncio.get_running_loop().run_in_executor(None, fn)

    # ── Write operations ──────────────────────────────────────────────────────

    async def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert or replace a node; returns the node_id written."""
        return await self._run(
            lambda: self._engine.add_node(
                node_id=node_id,
                node_type=node_type,
                name=name,
                properties=properties or {},
            )
        )

    async def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert an edge; returns the auto-incremented edge row id."""
        return await self._run(
            lambda: self._engine.add_edge(
                source=source,
                target=target,
                relation=relation,
                weight=weight,
                properties=properties or {},
            )
        )

    # ── Read operations ───────────────────────────────────────────────────────

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Return the node dict for *node_id*, or None if not found."""
        return await self._run(lambda: self._engine.get_node(node_id))

    async def get_neighbors(
        self,
        node_id: str,
        relation: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return outgoing neighbours of *node_id*, ordered by insertion."""
        return await self._run(
            lambda: self._engine.get_neighbors(
                node_id=node_id, relation=relation, limit=limit
            )
        )

    async def search_nodes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Substring search on node name, ordered alphabetically."""
        return await self._run(
            lambda: self._engine.search_nodes(query=query, limit=limit)
        )

    async def find_contradictions(self) -> List[Dict[str, Any]]:
        """Return mutually-contradicting node pairs, ordered deterministically."""
        return await self._run(self._engine.find_contradictions)

    async def stats(self) -> Dict[str, Any]:
        """Return graph statistics with backend label."""
        base = await self._run(self._engine.stats)
        return {"backend": "SQLiteGraphBackend", **base}

    # ── Internal access ───────────────────────────────────────────────────────

    @property
    def engine(self) -> GraphEngine:
        """Direct access to underlying GraphEngine (for MutualIndexer compatibility)."""
        return self._engine
