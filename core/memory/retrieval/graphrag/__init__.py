"""
core/memory/retrieval/graphrag/ — Session 5.5 GraphRAG Foundation.

An independent retrieval subsystem (not "graph search"): hybrid vector +
graph retrieval, pluggable traversal and ranking, mandatory provenance,
graceful degradation to vector-only when the graph is absent, sparse, or
malfunctioning. GraphRAG returns evidence; it never invokes a reasoning
model.

Public API:
    GraphRAGPipeline    — the orchestrating pipeline (evidence.py callers
                          construct one per UnifiedMemory/GraphBackend pair)
    EvidenceSet, Evidence — the output data model
    TraversalStrategy, BFSTraversalStrategy — pluggable graph expansion
    RankingStrategy, WeightedRankingStrategy — pluggable scoring
    IntentAnalyzer, PassthroughIntentAnalyzer — pluggable query stage
"""

from core.memory.retrieval.graphrag.evidence import Evidence, EvidenceSet
from core.memory.retrieval.graphrag.intent import (
    IntentAnalyzer, PassthroughIntentAnalyzer, QueryIntent,
)
from core.memory.retrieval.graphrag.pipeline import GraphRAGPipeline
from core.memory.retrieval.graphrag.ranking import (
    RankingStrategy, WeightedRankingStrategy,
)
from core.memory.retrieval.graphrag.traversal import (
    BFSTraversalStrategy, TraversalHop, TraversalResult, TraversalStrategy,
)

__all__ = [
    "GraphRAGPipeline",
    "Evidence", "EvidenceSet",
    "TraversalStrategy", "BFSTraversalStrategy", "TraversalResult", "TraversalHop",
    "RankingStrategy", "WeightedRankingStrategy",
    "IntentAnalyzer", "PassthroughIntentAnalyzer", "QueryIntent",
]
