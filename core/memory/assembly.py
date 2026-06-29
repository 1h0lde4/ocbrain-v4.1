"""
core/memory/assembly.py — ContextAssemblyEngine

Session 3B: Legacy retrieval chain replaced.

REMOVED:
  - import of fusion_engine singleton
  - synchronous assemble_context()
  - all direct access to CognitiveVault or graph_engine

NEW:
  - Constructor injection: __init__(self, memory: UnifiedMemory)
  - assemble_context() is async — propagates await to fuse_search() and search()
  - Composition root creates context_assembler with get_unified_memory()
  - Output format preserved: identical section headers, field names, ordering

Architecture:
  ContextAssemblyEngine depends only on UnifiedMemory (FA §4.1 Layer 6).
  It constructs its own RetrievalFusionEngine at init time, injecting the
  same UnifiedMemory instance — no additional singleton, no hidden state.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from core.memory.unified_memory import UnifiedMemory, SearchResult, get_unified_memory
from core.memory.retrieval.fusion import RetrievalFusionEngine

logger = logging.getLogger("ocbrain.memory.assembly")


class ContextAssemblyEngine:
    """
    Goal-aware context assembly from multi-tier memories.

    Dependency injection: receives UnifiedMemory through the constructor.
    No singletons. No module-level retrieval globals. No backend access.

    Output format is identical to the legacy implementation so that the
    Orchestrator receives the same context string structure.
    """

    def __init__(self, memory: UnifiedMemory) -> None:
        """
        Args:
            memory: The UnifiedMemory instance for all retrieval.
                    Injected at construction; never fetched inside methods.
        """
        self._memory = memory
        self._fusion = RetrievalFusionEngine(memory)

    async def assemble_context(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
    ) -> str:
        """Build a multi-tier prompt context string for *query*.

        Retrieval is fully asynchronous: awaits fuse_search() which awaits
        UnifiedMemory.search() — no event-loop blocking.

        Output sections (preserved from legacy implementation):
          ### RELEVANT KNOWLEDGE (Semantic)     — L2 entries
          ### PROVEN FIX PATTERNS (Procedural)  — L3 entries
          ### RECENT EPISODES (Timeline)        — L1 entries

        Returns:
            Context string, or "" when memory returns no results.
        """
        # 1. Retrieve — fully async, no blocking I/O on event loop
        results: List[SearchResult] = await self._fusion.fuse_search(
            query, query_embedding=query_embedding, top_k=10
        )

        # 2. Group by layer (mirrors legacy tier grouping L1/L2/L3)
        episodic   = [sr for sr in results if sr.entry.layer == "l1"]
        semantic   = [sr for sr in results if sr.entry.layer == "l2"]
        procedural = [sr for sr in results if sr.entry.layer == "l3"]

        # 3. Format — identical section headers and field layout as legacy
        sections: List[str] = []

        if semantic:
            sections.append("### RELEVANT KNOWLEDGE (Semantic)")
            for sr in semantic:
                sections.append(f"- {sr.entry.content}")

        if procedural:
            sections.append("### PROVEN FIX PATTERNS (Procedural)")
            for sr in procedural:
                sections.append(f"- {sr.entry.content}")

        if episodic:
            sections.append("### RECENT EPISODES (Timeline)")
            for sr in episodic:
                ts = datetime.fromtimestamp(
                    sr.entry.created_at, tz=timezone.utc
                ).isoformat()
                sections.append(f"[{ts}] {sr.entry.content}")

        return "\n\n".join(sections)


# ── Composition root ──────────────────────────────────────────────────────────
# Constructed once at module import with the process-level UnifiedMemory
# singleton.  Orchestrator.handle() imports and calls this object directly.
# get_unified_memory() is called here (module level = composition root),
# NOT inside any method — satisfying the no-service-locator-in-methods rule.
context_assembler = ContextAssemblyEngine(get_unified_memory())
