"""
core/memory/retrieval/context/ — Session 5.6 Retrieval Context Builder.

Transforms Evidence (Session 5.5 GraphRAG output) into Context: a
deterministic, provenance-preserving, token-budgeted structure suitable for
downstream reasoning. Organizes; never reasons.

Deliberately independent of core.memory.retrieval.graphrag — GraphRAGPipeline
must not depend on this package, and this package must not depend on
GraphRAG internals beyond the Evidence/EvidenceSet data types it consumes.

Public API:
    RetrievalContextBuilder — the builder (build(evidence_set) -> Context)
    Context, ContextBlock, ContradictionGroup, ProvenanceRecord — the data model
    DuplicateDetector, MinHashDuplicateDetector — pluggable consolidation
    TokenCounter, HeuristicTokenCounter — pluggable budgeting
"""

from core.memory.retrieval.context.builder import RetrievalContextBuilder
from core.memory.retrieval.context.context import (
    Context, ContextBlock, ContradictionGroup, ProvenanceRecord,
)
from core.memory.retrieval.context.duplicates import DuplicateDetector, MinHashDuplicateDetector
from core.memory.retrieval.context.token_counter import HeuristicTokenCounter, TokenCounter

__all__ = [
    "RetrievalContextBuilder",
    "Context", "ContextBlock", "ContradictionGroup", "ProvenanceRecord",
    "DuplicateDetector", "MinHashDuplicateDetector",
    "TokenCounter", "HeuristicTokenCounter",
]
