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
from enum import Enum
from typing import Any, Dict, List, Optional


class AuthorityLevel(Enum):
    """CTX-AUTH-001 / REM-004 — the authority taxonomy the remediation
    register (docs/reports/context-compiler-remediation-register.md,
    REM-004) names as a prerequisite for REM-002/REM-003 to be
    meaningful. Distinct from ProvenanceRecord.trust_score: trust_score
    is a quality/reliability signal about the CONTENT (how corroborated,
    how confident); AuthorityLevel is a security/instruction-following
    signal about the ROLE this material may play (whether it may ever be
    treated as the operative request). A block can be high-trust_score
    and still RETRIEVED -- trust in the information is not authority to
    instruct. Values are a closed set on purpose (context-authority-
    threat-model.md's "at minimum" list); do not add a value whose
    membership could be inferred from content rather than assigned by a
    trusted application-controlled call site.
    """
    SYSTEM = "system"        # Application/kernel-authored instruction.
    USER = "user"            # The current turn's actual human instruction.
    RETRIEVED = "retrieved"  # Memory/context/RAG-sourced material.
    EXTERNAL = "external"    # Web, tool output, other external material.
    GENERATED = "generated"  # Model-generated intermediate content.


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
    # CTX-AUTH-001 / REM-004: assigned exactly once, by the trusted
    # construction site (RetrievalContextBuilder._to_block), never
    # derived from entry/evidence content. Defaults to the least-
    # privileged value so any future construction site that forgets to
    # set this explicitly fails closed rather than silently trusted
    # (mission-doc §7: missing authority must not be promoted).
    authority: AuthorityLevel = AuthorityLevel.RETRIEVED


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
