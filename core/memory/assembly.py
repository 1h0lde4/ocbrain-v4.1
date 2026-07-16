"""
core/memory/assembly.py — ContextAssemblyEngine

Session 3B: Legacy retrieval chain replaced.
K2.2 (this session): Retrieval Runtime cutover — see below.

REMOVED (Session 3B):
  - import of fusion_engine singleton
  - synchronous assemble_context()
  - all direct access to CognitiveVault or graph_engine

K2.2 CHANGE — the live retrieval path is now:

    GraphRAGPipeline.retrieve()  (Stage 1 intent → Stage 2 UnifiedMemory.
                                   search() → Stage 3 graph expansion →
                                   Stage 4 ranking)
            │  EvidenceSet
            ▼
    RetrievalContextBuilder.build()  (dedup → contradiction grouping →
                                        token budgeting → provenance)
            │  Context
            ▼
    assemble_context()'s own formatting step (this file) — produces the
    same three-section string this method has always returned.

    Note on call order: the K2.2 session prompt's own diagram lists
    RetrievalContextBuilder before GraphRAGPipeline. That is reversed
    from the order these two components were actually built and tested
    against (RetrievalContextBuilder.build() takes an EvidenceSet as
    input; GraphRAGPipeline.retrieve() is what produces one —
    core/memory/retrieval/context/builder.py's own module docstring
    example is `evidence = await graph_rag.retrieve(query); context =
    context_builder.build(evidence)`). Implemented here in the order the
    already-tested code actually requires, not the diagram's order; noted
    explicitly rather than silently reconciled.

    RetrievalFusionEngine (core/memory/retrieval/fusion.py) is no longer
    used here — see that module for its own K2.2 change. It remains
    available as a compatibility façade for any other caller, and now
    itself delegates to GraphRAGPipeline rather than calling
    UnifiedMemory.search() directly, so there is exactly one retrieval
    implementation regardless of which entry point is used (K2.2 Rule 4).

    Layer grouping (the three section headers below) is preserved by
    building a local entry_id → KnowledgeEntry map from the EvidenceSet
    *before* it is consumed by RetrievalContextBuilder. This is necessary
    because ContextBlock/ProvenanceRecord — the canonical output types —
    deliberately do not embed a raw KnowledgeEntry or its layer
    (core/memory/retrieval/context/context.py's own docstring explains
    why: so nothing downstream depends on storage internals through
    those objects). The map is local to this method, touches no frozen
    dataclass, and adds no dependency on UnifiedMemory beyond what this
    class already had.

NEW (Session 3B, unchanged this session):
  - Constructor injection: __init__(self, memory: UnifiedMemory)
  - assemble_context() is async
  - Composition root creates context_assembler with get_unified_memory()
  - Output format preserved: identical section headers, field names, ordering

Architecture:
  ContextAssemblyEngine depends on UnifiedMemory, GraphRAGPipeline, and
  RetrievalContextBuilder (KERNEL_ARCHITECTURE_v1.0.md §13.1) — no
  additional singleton, no hidden state, everything constructor-injected
  or built once at __init__ time.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.memory.knowledge_entry import KnowledgeEntry
from core.memory.unified_memory import UnifiedMemory, get_unified_memory
from core.memory.retrieval.fusion import RetrievalFusionEngine
from core.memory.retrieval.graphrag import GraphRAGPipeline
from core.memory.retrieval.context import RetrievalContextBuilder, Context

logger = logging.getLogger("ocbrain.memory.assembly")


class ContextAssemblyEngine:
    """
    Goal-aware context assembly from multi-tier memories.

    Dependency injection: receives UnifiedMemory through the constructor.
    No singletons. No module-level retrieval globals. No backend access.

    Output format is identical to the legacy implementation so that the
    Orchestrator and PlannerWorker — its only two current callers — keep
    receiving the same context string structure with no change on their end.
    """

    def __init__(self, memory: UnifiedMemory) -> None:
        """
        Args:
            memory: The UnifiedMemory instance for all retrieval.
                    Injected at construction; never fetched inside methods.
        """
        self._memory = memory
        # K2.2: the canonical Retrieval Runtime. graph=memory.graph passes
        # through whatever backend is currently registered (may be None;
        # GraphRAGPipeline degrades gracefully to vector-only evidence in
        # that case — identical coverage to the pre-K2.2 path, plus graph
        # expansion whenever a backend is registered).
        self._graphrag = GraphRAGPipeline(memory, graph=memory.graph)
        self._context_builder = RetrievalContextBuilder()
        # Retained for any other caller of the legacy List[SearchResult]
        # shape (K2.2 Rule 3: "may remain... if existing callers require
        # it"). Not used by assemble_context() itself as of this session.
        self._fusion = RetrievalFusionEngine(memory)

    async def assemble_context(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
    ) -> str:
        """Build a multi-tier prompt context string for *query*.

        K2.2: retrieval now flows through GraphRAGPipeline.retrieve() →
        RetrievalContextBuilder.build() — the canonical Retrieval Runtime —
        instead of RetrievalFusionEngine. Fully asynchronous throughout;
        no event-loop blocking.

        Output sections (preserved from legacy implementation — signature,
        headers, and field layout are all unchanged; only what populates
        them changed):
          ### RELEVANT KNOWLEDGE (Semantic)     — L2 entries
          ### PROVEN FIX PATTERNS (Procedural)  — L3 entries
          ### RECENT EPISODES (Timeline)        — L1 entries

        Returns:
            Context string, or "" when memory returns no results.
        """
        # 1. Retrieve via the canonical pipeline — one call to
        #    UnifiedMemory.search() happens inside this (GraphRAGPipeline
        #    Stage 2), plus graph expansion when a backend is registered.
        evidence_set = await self._graphrag.retrieve(
            query, limit=10, query_embedding=query_embedding,
        )

        # 2. Local entry_id -> KnowledgeEntry map, built from the evidence
        #    this method already legitimately holds — the only way to
        #    recover layer/created_at once the canonical Context objects
        #    (deliberately) stop carrying them. See module docstring.
        entries_by_id: Dict[str, KnowledgeEntry] = {
            item.entry_id: item.entry for item in evidence_set.items
        }

        # 3. Build the canonical Context — dedup, contradiction grouping,
        #    token budgeting, provenance all happen here, once.
        context: Context = self._context_builder.build(evidence_set)

        # 4. Group blocks by their primary entry's layer (mirrors legacy
        #    tier grouping L1/L2/L3). Falls back to "l2" (semantic) for
        #    the defensive case of a primary_entry_id absent from the map
        #    — should not occur given every block traces back to this
        #    evidence_set by construction, but this avoids a crash if it
        #    ever does (PI §20.4: engineer defensively).
        episodic:   List = []
        semantic:   List = []
        procedural: List = []
        for block in context.blocks:
            entry = entries_by_id.get(block.primary_entry_id)
            layer = entry.layer if entry is not None else "l2"
            if entry is None:
                logger.warning(
                    "ContextAssemblyEngine: block primary_entry_id=%s not "
                    "found in this request's evidence set; defaulting to "
                    "layer='l2' for section grouping.",
                    block.primary_entry_id,
                )
            if layer == "l1":
                episodic.append((block, entry))
            elif layer == "l3":
                procedural.append((block, entry))
            else:
                semantic.append((block, entry))

        # 5. Format — identical section headers and field layout as legacy.
        sections: List[str] = []

        if semantic:
            sections.append("### RELEVANT KNOWLEDGE (Semantic)")
            for block, _entry in semantic:
                sections.append(f"- {block.content}")

        if procedural:
            sections.append("### PROVEN FIX PATTERNS (Procedural)")
            for block, _entry in procedural:
                sections.append(f"- {block.content}")

        if episodic:
            sections.append("### RECENT EPISODES (Timeline)")
            for block, entry in episodic:
                created_at = entry.created_at if entry is not None else None
                if created_at is not None:
                    ts = datetime.fromtimestamp(
                        created_at, tz=timezone.utc
                    ).isoformat()
                    sections.append(f"[{ts}] {block.content}")
                else:
                    sections.append(f"{block.content}")

        return "\n\n".join(sections)


# ── Composition root ──────────────────────────────────────────────────────────
# Constructed once at module import with the process-level UnifiedMemory
# singleton.  Orchestrator.handle() imports and calls this object directly.
# get_unified_memory() is called here (module level = composition root),
# NOT inside any method — satisfying the no-service-locator-in-methods rule.
context_assembler = ContextAssemblyEngine(get_unified_memory())
