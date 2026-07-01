"""
core/memory/knowledge_entry.py — v4.3.4.92 Knowledge Model Foundation

KnowledgeEntry: the canonical memory unit (what is known).
KnowledgeEvent: the audit record (what happened) — see knowledge_event.py.

Truth framework required by:
  v4.3.5  Graph Memory (only "verified"/"candidate" get graph nodes)
  v4.3.6  Memory Curator (detects/resolves conflicts via contradicts[])
  v4.3.8  GraphRAG Retrieval (traverses supports[]/contradicts[] edges)
  v4.8    Self-learning (updates truth_status via RL signal)
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

TRUTH_STATUS = {
    "unknown":    "No validation performed yet (default on write)",
    "candidate":  "From trusted source, not yet cross-validated",
    "verified":   "Confirmed by multiple sources or curator approval",
    "conflicted": "Contradicts one or more other verified entries",
    "deprecated": "Superseded; retained for provenance only",
}

# Only these statuses get graph nodes in v4.3.5
GRAPH_ELIGIBLE_STATUSES = {"verified", "candidate"}

# Excluded from default search results
EXCLUDED_FROM_SEARCH = {"deprecated"}

LAYERS = {
    "l0": "Working Memory (LRU, in-process, active context)",
    "l1": "Episodic Memory (SQLite+FTS5, events and observations)",
    "l2": "Semantic Memory (BM25+embeddings, facts and concepts)",
    "l3": "Graph Memory (entities, relations, knowledge graph)",
    "l4": "Archive Memory (immutable audit log, provenance)",
}


@dataclass
class KnowledgeEntry:
    """
    Canonical memory unit. Represents what the system knows.
    Mutable — updated in place as knowledge evolves.
    """

    # Identity
    entry_id:       str   = field(default_factory=lambda: str(uuid.uuid4()))
    layer:          str   = "l1"

    # Content
    content:        str   = ""
    summary:        str   = ""   # LLM-generated in v4.3.6, empty until then

    # Epistemics
    importance:     float = 0.5
    confidence:     float = 1.0
    truth_status:   str   = "unknown"
    trust_score:    float = 1.0

    # Provenance
    source:         str           = ""
    worker_id:      str           = ""
    workflow_id:    str           = ""
    derived_from:   List[str]     = field(default_factory=list)

    # Truth & contradiction relations
    supports:       List[str]     = field(default_factory=list)
    contradicts:    List[str]     = field(default_factory=list)
    supersedes:     List[str]     = field(default_factory=list)

    # Cross-layer link (v4.3.5 mutual index)
    graph_node_id:  Optional[str] = None

    # Retrieval
    tags:           List[str]     = field(default_factory=list)
    metadata:       Dict[str, Any]= field(default_factory=dict)
    procedure_name: Optional[str] = None

    # Lifecycle
    created_at:     float = field(default_factory=time.time)
    updated_at:     float = field(default_factory=time.time)
    accessed_at:    float = field(default_factory=time.time)
    access_count:   int   = 0

    def __post_init__(self) -> None:
        if self.truth_status not in TRUTH_STATUS:
            raise ValueError(f"Invalid truth_status {self.truth_status!r}")
        self.importance  = max(0.0, min(1.0, self.importance))
        self.confidence  = max(0.0, min(1.0, self.confidence))
        self.trust_score = max(0.0, min(1.0, self.trust_score))
        if self.layer not in LAYERS:
            raise ValueError(f"Invalid layer {self.layer!r}")

    def is_graph_eligible(self) -> bool:
        return self.truth_status in GRAPH_ELIGIBLE_STATUSES

    def is_searchable(self) -> bool:
        return self.truth_status not in EXCLUDED_FROM_SEARCH

    def composite_score(self, relevance: float = 0.5) -> float:
        """ADR-006 composite scoring formula."""
        age_hours = (time.time() - self.accessed_at) / 3600
        recency   = 0.99 ** age_hours
        return 0.25 * recency + 0.25 * self.importance + 0.50 * relevance

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "entry_id": self.entry_id, "layer": self.layer,
            "content": self.content, "summary": self.summary,
            "importance": self.importance, "confidence": self.confidence,
            "truth_status": self.truth_status, "trust_score": self.trust_score,
            "source": self.source, "worker_id": self.worker_id,
            "workflow_id": self.workflow_id,
            "derived_from": json.dumps(self.derived_from),
            "supports":     json.dumps(self.supports),
            "contradicts":  json.dumps(self.contradicts),
            "supersedes":   json.dumps(self.supersedes),
            "graph_node_id": self.graph_node_id,
            "tags":     json.dumps(self.tags),
            "metadata": json.dumps(self.metadata, default=str),
            "procedure_name": self.procedure_name,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "accessed_at": self.accessed_at, "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeEntry":
        import json

        def _j(v: Any, default: Any) -> Any:
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except Exception:
                    return default
            return v if v is not None else default

        return cls(
            entry_id=       d.get("entry_id", str(uuid.uuid4())),
            layer=          d.get("layer", "l1"),
            content=        d.get("content", ""),
            summary=        d.get("summary", ""),
            importance=     float(d.get("importance", 0.5)),
            confidence=     float(d.get("confidence", 1.0)),
            truth_status=   d.get("truth_status", "unknown"),
            trust_score=    float(d.get("trust_score", 1.0)),
            source=         d.get("source", ""),
            worker_id=      d.get("worker_id", ""),
            workflow_id=    d.get("workflow_id", ""),
            derived_from=   _j(d.get("derived_from"), []),
            supports=       _j(d.get("supports"), []),
            contradicts=    _j(d.get("contradicts"), []),
            supersedes=     _j(d.get("supersedes"), []),
            graph_node_id=  d.get("graph_node_id"),
            tags=           _j(d.get("tags"), []),
            metadata=       _j(d.get("metadata"), {}),
            procedure_name= d.get("procedure_name"),
            created_at=     float(d.get("created_at", time.time())),
            updated_at=     float(d.get("updated_at", time.time())),
            accessed_at=    float(d.get("accessed_at", time.time())),
            access_count=   int(d.get("access_count", 0)),
        )

    def __repr__(self) -> str:
        return (f"KnowledgeEntry(id={self.entry_id[:8]}, layer={self.layer}, "
                f"truth={self.truth_status}, imp={self.importance:.2f}, "
                f"content={self.content[:40]!r})")
