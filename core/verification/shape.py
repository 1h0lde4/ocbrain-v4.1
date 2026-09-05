"""
Verification shape and pairwise/set-level consistency.

New in architecture v3 Part 1 (sections 1-2), orthogonal to method and
dimension (v2 section 11):
  - VerificationShape: POINTWISE (default) / PAIRWISE / SET_LEVEL
  - ComparisonRelation: a single pairwise judgment (A vs. B)
  - PairwiseConsistency: a SET_LEVEL meta-evaluation of whether multiple
    ComparisonRelations are jointly coherent (no cycles)

Order bias (does swapping A/B change ONE verdict) and pairwise/cycle
consistency (do MULTIPLE comparisons jointly cohere) are v3's own explicit
distinction -- two different failure modes, two different checks. This
file covers only the second; order-bias mitigation is BlindVerificationContext
(v2 section 42), not built in this pass.

The aggregation algorithm for a detected cycle (simple tournament,
Bradley-Terry-style rank estimation, or otherwise) is explicitly out of
scope here -- v3 names it Phase D, not decided at the architecture level.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Tuple


class VerificationShape(str, Enum):
    """Orthogonal to method (v2 section 11) and dimension (v2 section 11).

    POINTWISE is the default for ordinary verification. PAIRWISE/SET_LEVEL
    are invoked only when the task genuinely is a comparison -- never
    forced onto ordinary single-target verification (v3 Part 1 section 1).
    """
    POINTWISE = "pointwise"
    PAIRWISE = "pairwise"
    SET_LEVEL = "set_level"


class ComparisonOutcome(str, Enum):
    """The result of one pairwise judgment."""
    A_PREFERRED = "a_preferred"
    B_PREFERRED = "b_preferred"
    TIE = "tie"
    INCOMPARABLE = "incomparable"  # verifier could not judge -- not the same as a tie


@dataclass(frozen=True)
class ComparisonRelation:
    """One pairwise judgment: A vs. B, with an outcome.

    First step of v3's pipeline: "pairwise judgment -> comparison relation
    -> consistency/transitivity analysis -> aggregation." A ComparisonRelation
    on its own says nothing about order bias or cycle consistency -- those
    are properties of, respectively, a single relation run twice (order
    bias -- see BlindVerificationContext, v2 section 42, not built here) or
    a SET of relations (PairwiseConsistency, below).
    """
    comparison_id: str
    target_a_id: str
    target_b_id: str
    outcome: ComparisonOutcome

    def __post_init__(self) -> None:
        if not self.comparison_id:
            raise ValueError("ComparisonRelation.comparison_id must be non-empty")
        if not self.target_a_id or not self.target_b_id:
            raise ValueError("ComparisonRelation requires both target_a_id and target_b_id")
        if self.target_a_id == self.target_b_id:
            raise ValueError("ComparisonRelation cannot compare a target against itself")

    @property
    def is_decisive(self) -> bool:
        """False for TIE/INCOMPARABLE -- callers building a preference order should skip these."""
        return self.outcome in (ComparisonOutcome.A_PREFERRED, ComparisonOutcome.B_PREFERRED)


class ConsistencyStatus(str, Enum):
    """Outcome of a SET_LEVEL consistency/transitivity check."""
    CONSISTENT = "consistent"
    CYCLE_DETECTED = "cycle_detected"
    INSUFFICIENT_COMPARISONS = "insufficient_comparisons"


@dataclass(frozen=True)
class PairwiseConsistency:
    """A verifier meta-evaluation dimension (v3 Part 1 section 2), not a verdict.

    Describes whether a SET of ComparisonRelations is jointly coherent --
    e.g. A>B, B>C, C>A is a cycle, not three independently-fine judgments.
    Only meaningful at VerificationShape.SET_LEVEL; a single ComparisonRelation
    has nothing to check against (it is trivially consistent with itself).

    This is a finding about the comparisons as a set, separate from whether
    any individual ComparisonRelation's outcome is itself correct -- that
    is ordinary verification, not this dimension.
    """
    status: ConsistencyStatus
    comparisons_checked: Tuple[str, ...]  # ComparisonRelation.comparison_id values
    cycle_members: FrozenSet[str] = field(default_factory=frozenset)  # target IDs forming the cycle

    def __post_init__(self) -> None:
        if not self.comparisons_checked:
            raise ValueError("PairwiseConsistency must reference at least one comparison")
        has_cycle_members = bool(self.cycle_members)
        is_cycle = self.status == ConsistencyStatus.CYCLE_DETECTED
        if has_cycle_members != is_cycle:
            raise ValueError(
                "cycle_members must be non-empty if and only if status is CYCLE_DETECTED "
                f"(status={self.status.value}, cycle_members={sorted(self.cycle_members)})"
            )
