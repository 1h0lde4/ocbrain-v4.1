"""
core/memory/retrieval/context/context.py — Session 5.6 Retrieval Context
Builder.

Context is the standard exchange object between retrieval and every future
reasoning system (KAG, Reflection, Planning, Skills, ...). ContextBlock
deliberately does NOT embed a raw KnowledgeEntry -- ProvenanceRecord
projects only the fields a consumer needs, independent of storage
implementation, so nothing downstream ever depends on UnifiedMemory's
internals through this object.

Fields reserved for future sessions (verification_history -> Session 5.9)
are present but explicitly left unimplemented (None), never fabricated --
Phase 0 confirmed KnowledgeEntry has no verification-history mechanism
today, so populating this field now would be inventing data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProvenanceRecord:
    """Projection of KnowledgeEntry + Evidence provenance -- primitives
    only, no live reference back to the entry or any backend object."""
    source: str
    worker_id: str
    workflow_id: str
    confidence: float
    trust_score: float
    truth_status: str
    retrieval_method: str                      # "vector" | "graph"
    graph_distance: Optional[int] = None
    graph_path: List[Dict[str, str]] = field(default_factory=list)   # [{"relation", "node_id"}, ...]
    seed_entry_id: Optional[str] = None
    verification_history: Optional[List[Any]] = None   # reserved — Session 5.9, intentionally unimplemented


@dataclass
class ContextBlock:
    """One consolidated unit of context. May represent a single Evidence
    item, or several near-duplicate items merged into one (merged_entry_ids)."""
    primary_entry_id: str
    content: str
    score: float
    importance: float
    provenance: ProvenanceRecord
    merged_entry_ids: List[str] = field(default_factory=list)
    contradicts: List[str] = field(default_factory=list)   # from the primary entry, carried through
    supports: List[str] = field(default_factory=list)
    contradiction_group_id: Optional[str] = None
    token_count: int = 0

    @property
    def all_entry_ids(self) -> List[str]:
        """primary + everything merged into it -- what "dropping this
        block" actually means for dropped_entry_ids reporting."""
        return [self.primary_entry_id] + list(self.merged_entry_ids)


@dataclass
class ContradictionGroup:
    group_id: str
    entry_ids: List[str]   # primary_entry_ids of the blocks in this group


@dataclass
class Context:
    """The standard interface consumed by every future reasoning system.
    Organization only -- Context never contains a synthesized answer,
    summary, or resolved contradiction; that's explicitly out of scope
    for this session and belongs to future reasoning layers."""
    query: str
    blocks: List[ContextBlock] = field(default_factory=list)
    contradiction_groups: List[ContradictionGroup] = field(default_factory=list)
    total_tokens: int = 0
    token_budget: Optional[int] = None
    truncated: bool = False
    dropped_entry_ids: List[str] = field(default_factory=list)
    graph_available: bool = False

    def __len__(self) -> int:
        return len(self.blocks)
