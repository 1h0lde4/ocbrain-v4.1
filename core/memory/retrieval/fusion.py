"""
core/memory/retrieval/fusion.py — RetrievalFusionEngine

Session 3B: Legacy retrieval chain replaced.

REMOVED:
  - CognitiveVault import and all direct vault calls
  - Raw graph singleton import and all direct graph calls
  - All internal retrieval logic (_semantic_search, _graph_search, _apply_rrf)
  - Module-level singleton

NEW:
  - Constructor injection: __init__(self, memory: UnifiedMemory)
  - fuse_search() is async — delegates entirely to UnifiedMemory.search()
  - No duplicate ranking logic
  - No direct access to any backend

Architecture:
  UnifiedMemory is the single owner of retrieval (FA §4.1 Layer 5).
  RetrievalFusionEngine is now a thin async compatibility façade that lets
  ContextAssemblyEngine call a named method while the real work happens in
  UnifiedMemory.search() (BM25 + vector + RRF + composite scoring).
"""

import logging
from typing import List, Optional

from core.memory.unified_memory import UnifiedMemory, SearchResult

logger = logging.getLogger("ocbrain.memory.fusion")


class RetrievalFusionEngine:
    """
    Async compatibility façade over UnifiedMemory.search().

    Dependency injection: receives UnifiedMemory through the constructor.
    No singletons. No module-level state. No backend access.

    All retrieval logic lives exclusively in UnifiedMemory (ADR-006):
      L2 VectorBackend  — BM25 + optional embeddings
      L1 StorageBackend — FTS5 keyword search
      Composite scoring — recency × importance × relevance (RRF-merged)
    """

    def __init__(self, memory: UnifiedMemory) -> None:
        """
        Args:
            memory: The UnifiedMemory instance that owns all retrieval.
                    Injected at construction time; never fetched internally.
        """
        self._memory = memory

    async def fuse_search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Return top-k SearchResult objects for *query*.

        Delegates entirely to UnifiedMemory.search() — no duplicate logic.

        Args:
            query:           Natural language search string.
            query_embedding: Optional dense vector; passed through to L2
                             vector search when provided.
            top_k:           Maximum number of results to return.

        Returns:
            List[SearchResult] ordered by composite_score descending.
            Empty list when memory contains no relevant entries.
        """
        return await self._memory.search(
            query=query,
            limit=top_k,
            query_embedding=query_embedding,
        )


# ── No module-level singleton ─────────────────────────────────────────────────
# ContextAssemblyEngine owns construction and holds the instance.
