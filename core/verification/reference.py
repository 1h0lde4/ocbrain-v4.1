"""
Reference / GroundTruth (mission Sec7.6, Sec34, Phase 2 -- epistemic
spine): comparison points offered as relevant to a verification, kept
distinct from each other and from Oracle (oracle.py).

Grouped in one file because GroundTruth is specifically an elevation of
a Reference, not an independent concept -- matching this codebase's own
convention for tightly-coupled pairs (InspectionPlan/InspectionStep in
inspection.py; Rubric/Criterion/... in rubric.py).

What this module deliberately does NOT do: resolve conflicts between
multiple References/GroundTruths for the same target (mission Sec34 --
ORACLE_CONFLICT/REFERENCE_CONFLICT/GROUNDTRUTH_CONFLICT are assessment-
layer diagnostics, Phase 4, not epistemic-spine types). This module
only defines what a Reference and a GroundTruth *are*.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .identity import GroundTruthId, ReferenceId


class ReferenceKind(str, Enum):
    EXPECTED_VALUE = "expected_value"
    PRIOR_RESULT = "prior_result"
    DOCUMENTATION = "documentation"
    SPECIFICATION = "specification"
    HUMAN_JUDGMENT = "human_judgment"


class ReferenceQuality(str, Enum):
    """Quality characterization of a Reference -- NOT correctness,
    authority, freshness, GroundTruth status, or any other epistemic
    property.

    IMPLEMENTATION JUDGMENT: the frozen architecture (v2 §49) names
    ReferenceQuality as a required type but does not prescribe a
    closed quality vocabulary.  The following four values represent
    the smallest defensible set:

    - UNASSESSED: quality has not been evaluated.  The absence of a
      quality assessment must not be treated as LOW or HIGH.

    - LOW: the reference has known quality concerns (e.g. outdated
      documentation, unverified model output, incomplete specification).

    - MODERATE: the reference meets basic quality expectations but has
      not been rigorously validated.

    - HIGH: the reference has been validated for accuracy, completeness,
      and relevance within its stated scope.

    Critical non-implications:
      - HIGH quality does NOT mean the reference is correct/true.
      - HIGH quality does NOT promote a Reference to GroundTruth.
      - HIGH quality does NOT override temporal validity, authority,
        integrity, scope, independence, or directness in conflict
        resolution (v2 conflict-resolution semantics treat quality as
        only one consideration among several).
      - Quality is NOT freshness (temporal validity is separate).
      - Quality is NOT authority (authority is separate).

    There is deliberately NO numeric score -- quality is categorical
    to prevent silent ordering assumptions.
    """
    UNASSESSED = "unassessed"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass(frozen=True)
class Reference:
    """
    A comparison point -- not claimed to be correct merely by
    existing. Mission Sec7.6: "A model-generated statement is not
    automatically Ground Truth." Promotion to GroundTruth (below) is a
    separate, explicit act with its own provenance, never implicit in
    a Reference's own fields.

    quality: defaults to UNASSESSED -- the only safe default, since
    the absence of quality assessment must not be silently treated
    as any particular quality level.
    """
    reference_id: ReferenceId
    kind: ReferenceKind
    content_summary: str
    source: str  # where this reference actually came from
    quality: ReferenceQuality = ReferenceQuality.UNASSESSED

    def __post_init__(self) -> None:
        if not self.content_summary or not self.content_summary.strip():
            raise ValueError("Reference requires a non-empty content_summary")
        if not self.source or not self.source.strip():
            raise ValueError("Reference requires a non-empty source")


@dataclass(frozen=True)
class GroundTruth:
    """
    A Reference explicitly elevated to ground-truth status. The
    elevation is the load-bearing part: mission Sec7.6 requires this to
    never happen implicitly, so established_by/established_via are
    mandatory constructor arguments, not defaults -- there is no
    Reference-to-GroundTruth conversion function that skips them, on
    purpose.
    """
    ground_truth_id: GroundTruthId
    reference_id: ReferenceId
    established_by: str  # who/what made this determination -- "human:<id>", "authoritative_policy:<id>"; never a bare model name alone
    established_via: str  # the actual process: "human_review", "authoritative_spec_match", "prior_verified_execution", etc.

    def __post_init__(self) -> None:
        if not self.established_by or not self.established_by.strip():
            raise ValueError(
                "GroundTruth requires a non-empty established_by -- "
                "elevation to ground truth must be attributable, never implicit"
            )
        if not self.established_via or not self.established_via.strip():
            raise ValueError("GroundTruth requires a non-empty established_via")
