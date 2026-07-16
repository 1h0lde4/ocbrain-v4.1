"""
core/memory/retrieval/fusion.py — RetrievalFusionEngine

Session 3B: Legacy retrieval chain replaced.
K2.2 (this session): Retrieval Runtime cutover — see below.

REMOVED (Session 3B):
  - CognitiveVault import and all direct vault calls
  - Raw graph singleton import and all direct graph calls
  - All internal retrieval logic (_semantic_search, _graph_search, _apply_rrf)
  - Module-level singleton

K2.2 CHANGE: RetrievalFusionEngine no longer calls UnifiedMemory.search()
directly. It now delegates to GraphRAGPipeline — the canonical Retrieval
Runtime (KERNEL_ARCHITECTURE_v1.0.md §13.1) — and projects the resulting
EvidenceSet back down to the List[SearchResult] shape this class has
always returned. This is not a second retrieval implementation:
GraphRAGPipeline's own Stage 2 *is* a call to UnifiedMemory.search()
(core/memory/retrieval/graphrag/pipeline.py), with graph expansion,
contradiction linking, and provenance built on top. Class name, __init__
signature, and fuse_search() signature/return type are all unchanged, so
every existing caller (constructor-injected the same way as before)
keeps working with no code change on its end. Per Rule 3 of the K2.2
session: "no duplicate retrieval logic may exist" — there is exactly one
call to UnifiedMemory.search() per fuse_search() call, made by
GraphRAGPipeline, not by this class.

One deliberate, disclosed behavior change: results are now ordered by
GraphRAGPipeline's ranking (vector score plus any graph-derived signal),
not by UnifiedMemory's raw composite_score alone — this is the intended
effect of Rule 4 ("retrieval ranking... must all flow through the
canonical retrieval pipeline"), not a regression. The composite_score
field on each returned SearchResult is populated from the canonical
pipeline's own fused Evidence.score. bm25_score / vector_score /
recency_score are left at their 0.0 defaults: GraphRAGPipeline's ranking
does not preserve that three-way decomposition, and fabricating values
for it would be worse than honestly leaving them unset.

Architecture:
  UnifiedMemory remains the single owner of the underlying storage/vector/
  FTS5 search (ADR-006). GraphRAGPipeline is the single owner of ranking,
  graph expansion, and evidence assembly on top of it
  (KERNEL_ARCHITECTURE_v1.0.md §13.1). RetrievalFusionEngine is now a
  thin, async compatibility façade over GraphRAGPipeline, not over
  UnifiedMemory directly — kept for any caller that has not migrated to
  the richer Context model produced by RetrievalContextBuilder.
"""

import logging
from typing import List, Optional

from core.memory.unified_memory import UnifiedMemory, SearchResult
from core.memory.retrieval.graphrag import GraphRAGPipeline

logger = logging.getLogger("ocbrain.memory.fusion")


class RetrievalFusionEngine:
    """
    Async compatibility façade over GraphRAGPipeline (K2.2 cutover).

    Dependency injection: receives UnifiedMemory through the constructor,
    unchanged from before. No singletons. No module-level state. No
    direct backend access — GraphRAGPipeline is constructed here and owns
    the single call into UnifiedMemory.search().
    """

    def __init__(self, memory: UnifiedMemory) -> None:
        """
        Args:
            memory: The UnifiedMemory instance that owns all retrieval.
                    Injected at construction time; never fetched internally.
                    Signature unchanged from pre-K2.2 — existing callers
                    that construct RetrievalFusionEngine(memory) need no
                    change.
        """
        self._memory = memory
        # K2.2: delegate to the canonical Retrieval Runtime rather than
        # calling memory.search() directly. graph=memory.graph passes
        # through whatever backend UnifiedMemory currently has registered
        # (possibly None); GraphRAGPipeline degrades gracefully to
        # vector-only evidence in that case (core/memory/retrieval/
        # graphrag/pipeline.py's own documented behavior) — identical
        # coverage to the pre-K2.2 path when no graph is registered, plus
        # graph expansion when one is.
        self._graphrag = GraphRAGPipeline(memory, graph=memory.graph)

    async def fuse_search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Return top-k SearchResult objects for *query*.

        K2.2: delegates to GraphRAGPipeline.retrieve() (the canonical
        Retrieval Runtime), then projects each Evidence item back to the
        SearchResult shape this method has always returned. No duplicate
        retrieval logic — see module docstring.

        Args:
            query:           Natural language search string.
            query_embedding: Optional dense vector; passed through to L2
                             vector search when provided.
            top_k:           Maximum number of results to return.

        Returns:
            List[SearchResult], ordered by the canonical pipeline's
            ranking (descending). Empty list when memory contains no
            relevant entries.
        """
        evidence_set = await self._graphrag.retrieve(
            query,
            limit=top_k,
            query_embedding=query_embedding,
        )
        return [
            SearchResult(entry=item.entry, composite_score=item.score)
            for item in evidence_set.items
        ]


# ── No module-level singleton ─────────────────────────────────────────────────
# ContextAssemblyEngine owns construction and holds the instance.
