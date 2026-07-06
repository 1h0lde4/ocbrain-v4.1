"""
core/memory/retrieval/graphrag/evidence.py — Session 5.5 GraphRAG Foundation.

Evidence is GraphRAG's output unit. Every retrieved item -- whether it came
from vector/lexical search or from graph traversal -- becomes one Evidence
object, carrying enough provenance to answer "why is this here?" without
re-querying anything (research guidance #6: "Provenance Is Mandatory").

GraphRAG returns evidence; it never invokes a reasoning model itself
(research guidance #3). EvidenceSet is the explicit boundary between
retrieval and reasoning -- a caller (ContextAssemblyEngine, a future prompt
template, a worker) decides what to do with it next.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.memory.knowledge_entry import KnowledgeEntry


@dataclass
class Evidence:
    """One retrieved item with full provenance.

    retrieval_method: "vector" | "graph" -- how this Evidence entered the
                       result set. An entry found by both the memory-
                       retrieval stage AND graph expansion keeps "vector"
                       (the stronger, direct signal); consolidation
                       (pipeline.py) still fills in graph_distance/path
                       from the traversal hit rather than discarding that
                       provenance.
    graph_distance:    hops from the nearest vector-retrieved seed node via
                        graph traversal. None if this Evidence never
                        touched the graph (no backend registered, entry
                        not graph-eligible, or a pure vector hit with no
                        graph presence at all) -- distinct from 0, which
                        means "graph-eligible and the entry itself is
                        already the vector-retrieved seed."
    path:              ordered list of TraversalHop from the seed node to
                        this one. Empty for direct vector/lexical hits.
    seed_entry_id:      the KnowledgeEntry.entry_id this Evidence was
                        expanded FROM, if it arrived via graph traversal.
                        None for direct vector/lexical hits.
    score_breakdown:    the individual terms RankingStrategy combined into
                        `score`, kept for observability/debugging -- never
                        required by a consumer, always inspectable.
    """
    entry: KnowledgeEntry
    score: float = 0.0
    retrieval_method: str = "vector"          # "vector" | "graph"
    graph_distance: Optional[int] = None
    path: List[Any] = field(default_factory=list)
    seed_entry_id: Optional[str] = None
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    @property
    def entry_id(self) -> str:
        return self.entry.entry_id


@dataclass
class EvidenceSet:
    """Ordered collection of Evidence -- GraphRAG's final output.

    query:            the original query string, carried through for a
                       caller's own context assembly / logging. GraphRAG
                       never re-interprets it after the intent-analysis
                       stage.
    graph_available:  whether graph expansion actually ran (False when no
                       backend was registered, or the backend raised).
                       Distinguishes "graph legitimately found nothing"
                       from "graph wasn't consulted at all" -- both
                       produce the same empty-expansion outcome for
                       ranking purposes, but mean different things for
                       observability (research guidance #7: graceful
                       degradation must be visible, not silent).
    """
    query: str
    items: List[Evidence] = field(default_factory=list)
    graph_available: bool = False

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def entry_ids(self) -> List[str]:
        return [e.entry_id for e in self.items]

    def as_context_blocks(self, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """Render into a structured, LLM-consumable shape -- the "Context
        Assembly" pipeline stage. Deliberately a list of structured dicts,
        not a flattened prompt string: the caller (ContextAssemblyEngine,
        or a future prompt template) owns final formatting. GraphRAG hands
        over structure, never prose, and never calls a reasoning model.
        """
        items = self.items[:max_items] if max_items is not None else self.items
        return [
            {
                "entry_id": e.entry_id,
                "content": e.entry.content,
                "source": e.entry.source,
                "truth_status": e.entry.truth_status,
                "importance": e.entry.importance,
                "score": e.score,
                "retrieval_method": e.retrieval_method,
                "graph_distance": e.graph_distance,
                "path": [{"relation": h.relation, "node_id": h.node_id} for h in e.path],
            }
            for e in items
        ]
