"""
core/memory/retrieval/context/duplicates.py — Session 5.6 Retrieval Context
Builder.

DuplicateDetector wraps the EXACT MinHash/LSH pattern already proven in
learning/chunker.py::deduplicate() (datasketch, already a project
dependency) -- adapted for Evidence content instead of Chunk text.
Deliberately not a new algorithm: Phase 0 review found a working, O(n)
near-duplicate detector already in this repository and this reuses it
rather than inventing a second one (PI §1.1: "extract architectural
patterns rather than copying implementations" -- here the pattern AND the
implementation are close enough that literal reuse of the same library
call shape is the right amount of synthesis, not under- or over-adaptation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List

from datasketch import MinHash, MinHashLSH

if TYPE_CHECKING:
    from core.memory.retrieval.graphrag.evidence import Evidence


class DuplicateDetector(ABC):
    """Groups near-duplicate Evidence by content. Returns a dict mapping
    each Evidence's entry_id to a `group_key` string -- Evidence items
    sharing the same group_key are considered duplicates of each other.
    A unique group_key per item (e.g. its own entry_id) means "no
    duplicate found for this item"."""

    @abstractmethod
    def group(self, evidence: List["Evidence"]) -> Dict[str, str]: ...


class MinHashDuplicateDetector(DuplicateDetector):
    """Default implementation: same MinHash+LSH shape as
    learning/chunker.py::deduplicate() -- O(n) LSH queries, no pairwise
    comparison. threshold=0.92 matches chunker.py's own default for
    consistency across the codebase's two independent near-duplicate use
    cases (chunk ingestion vs. context consolidation)."""

    def __init__(self, threshold: float = 0.92, num_perm: int = 64) -> None:
        self.threshold = threshold
        self.num_perm = num_perm

    def group(self, evidence: List["Evidence"]) -> Dict[str, str]:
        if not evidence:
            return {}

        lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)
        group_key_for: Dict[str, str] = {}

        for item in evidence:
            m = MinHash(num_perm=self.num_perm)
            for word in item.entry.content.lower().split():
                m.update(word.encode("utf-8"))

            key = item.entry_id
            try:
                matches = lsh.query(m)
            except Exception:
                matches = []

            if matches:
                # Join the first (highest-ranked, since evidence arrives
                # pre-ranked and LSH preserves insertion order for querying)
                # existing group found.
                group_key_for[key] = matches[0]
            else:
                lsh.insert(key, m)
                group_key_for[key] = key

        return group_key_for
