"""
core/memory/retrieval/graphrag/ranking.py — Session 5.5 GraphRAG Foundation.

RankingStrategy is a pluggable interface, independent of TraversalStrategy
(research guidance #5: "Ranking Should Be Independent" -- traversal decides
WHAT is reachable, ranking decides in what ORDER it matters).

WeightedRankingStrategy is the only implementation today. It deliberately
REUSES KnowledgeEntry.composite_score() -- the canonical PI §8.4 formula
(recency x importance x relevance, already used by UnifiedMemory.search())
as its base term, then layers graph-specific signals (graph distance, edge
confidence, truth status) on top, rather than inventing a second, parallel
scoring formula that would drift from §8.4 over time.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from core.memory.retrieval.graphrag.evidence import Evidence

# truth_status is already a closed enum (core/memory/knowledge_entry.py
# TRUTH_STATUS) -- these bonuses cover every valid value explicitly rather
# than defaulting unknowns to a guessed value.
_TRUTH_STATUS_BONUS = {
    "verified":    1.0,
    "candidate":   0.5,
    "unknown":     0.0,
    "conflicted": -0.5,
    "deprecated": -1.0,
}


class RankingStrategy(ABC):
    """Scores and orders a list of Evidence.

    Must be a pure function of the Evidence list -- never re-queries
    memory or the graph, never mutates `entry`. This keeps ranking cheap
    to re-run and safe to swap independently of traversal or memory
    retrieval.
    """

    @abstractmethod
    def rank(self, evidence: List[Evidence]) -> List[Evidence]: ...


class WeightedRankingStrategy(RankingStrategy):
    """Default ranking strategy.

    score = KnowledgeEntry.composite_score(relevance)      # PI §8.4, reused
           + weight_graph_distance   / (1 + graph_distance)  [if graph hit]
           + weight_edge_confidence  * edge_confidence        [if graph hit]
           + weight_truth_status     * truth_status_bonus

    Weight defaults are chosen so graph signals are additive, never
    displacing: a pure vector hit (graph_distance=None, no edge_confidence)
    still ranks by its §8.4 composite_score alone, meaning enabling
    GraphRAG cannot make vector-only retrieval rank worse than
    UnifiedMemory.search() already would on its own -- graph presence can
    only add weight, never subtract, except for the (correctly negative)
    conflicted/deprecated truth_status terms.
    """

    def __init__(self,
                 weight_graph_distance: float = 0.15,
                 weight_edge_confidence: float = 0.10,
                 weight_truth_status: float = 0.10) -> None:
        self.weight_graph_distance = weight_graph_distance
        self.weight_edge_confidence = weight_edge_confidence
        self.weight_truth_status = weight_truth_status

    def rank(self, evidence: List[Evidence]) -> List[Evidence]:
        for item in evidence:
            if item.retrieval_method == "vector":
                # Already the correct PI §8.4 composite_score, computed by
                # UnifiedMemory.search() itself -- reuse exactly, don't
                # recompute from a proxy relevance value.
                base = item.score
            else:
                # Graph-only discovery: no direct query-relevance signal to
                # give it (the query never matched this entry's text) --
                # relevance=0.0 so its ranking comes from the graph terms
                # below plus its own importance/recency, not a borrowed
                # relevance score it didn't earn.
                base = item.entry.composite_score(relevance=0.0)

            distance_term = 0.0
            if item.graph_distance is not None:
                distance_term = self.weight_graph_distance / (1 + item.graph_distance)

            confidence_term = self.weight_edge_confidence * item.score_breakdown.get(
                "edge_confidence", 0.0)

            truth_term = self.weight_truth_status * _TRUTH_STATUS_BONUS.get(
                item.entry.truth_status, 0.0)

            item.score = base + distance_term + confidence_term + truth_term
            item.score_breakdown.update({
                "base_composite": base,
                "graph_distance_term": distance_term,
                "edge_confidence_term": confidence_term,
                "truth_status_term": truth_term,
            })

        # Deterministic: sort by score desc, tie-broken by entry_id so
        # identical scores always produce the same order across runs
        # (research guidance: prefer deterministic ranking).
        return sorted(evidence, key=lambda e: (-e.score, e.entry_id))
