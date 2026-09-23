"""
Assumption (mission §7.7, §32, Phase 2 -- epistemic spine): something a
verification takes as given, not something it checked.

Assumption != Evidence (mission §7.7) -- this is a deliberately
separate type with no shared base class and no overlapping fields with
EvidenceItem (evidence.py), so the two cannot be used interchangeably
by accident or silently upgraded into one another.
"""
from __future__ import annotations

from dataclasses import dataclass

from .identity import AssumptionId


@dataclass(frozen=True)
class Assumption:
    """
    Mission §32: "A result should be able to answer: What had to be
    true for this verification statement to hold?" -- relied_upon_for
    exists so that answer is queryable directly rather than left
    implicit in a verifier's prose.
    """
    assumption_id: AssumptionId
    description: str
    relied_upon_for: str  # what part of the verification depends on this holding

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("Assumption requires a non-empty description")
        if not self.relied_upon_for or not self.relied_upon_for.strip():
            raise ValueError("Assumption requires non-empty relied_upon_for")
