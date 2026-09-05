"""
Requirements / Policy / Strategy / Profile -- four distinct concepts.

Architecture v3 Part 1 section 3 names this a real gap: v2 used
`verification_requirements` as a single C-MoE-facing parameter name
(v2 section 33) without architecting it as four genuinely different
things, kept separate here:

  - VerificationRequirements: what the CALLER actually needs verified,
    and to what rigor -- declarative, caller-supplied.
  - VerificationPolicy: system-level constraints on what's permitted or
    required -- set by Governance/system configuration, never by the
    caller (e.g. "safety-critical claims always require multi-verifier
    composition").
  - VerificationStrategy: Verification's own internal method-selection
    DECISION (v2 sections 17, 32) -- informed by Requirements and Policy
    plus risk/cost, but not constructed by a caller. This module defines
    the STRUCTURE of a strategy (what one IS, once decided); the
    selection ALGORITHM that produces one is explicitly not architected
    here, matching v3's own Phase D deferral of PairwiseConsistency's
    aggregation algorithm in shape.py -- same judgment call, same reason.
  - VerificationProfile: a stable, named, external-facing bundle,
    recovering the original mission document's LIGHT/STANDARD/
    HIGH_ASSURANCE policy classes, which never made it into the
    architecture until this correction.

The corrected C-MoE boundary (v2 section 33, sharpened not reversed by
this file): a caller requests a VerificationProfile or raw
VerificationRequirements. It never constructs or manipulates a
VerificationStrategy directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Optional

from core.verification.shape import VerificationShape


class VerificationProfileName(str, Enum):
    """Recovers the original mission document's rigor classes (v3 Part 1 section 3)."""
    LIGHT = "light"
    STANDARD = "standard"
    HIGH_ASSURANCE = "high_assurance"


@dataclass(frozen=True)
class VerificationRequirements:
    """Caller-declared: what needs verifying, and to what rigor.

    This is the caller-facing half of the corrected C-MoE boundary
    (v2 section 33): a caller calls request_verification(target,
    verification_requirements) without knowing how Verification
    internally composes basis/authority/assurance (epistemic.py).

    required_dimensions is a set of dimension names (v2 section 11's
    dimension taxonomy is not yet built in code -- tracked as remaining
    Phase C scope; plain strings here are a deliberate placeholder for
    that not-yet-existing enum, not a design decision to use strings
    permanently).
    """
    target_description: str
    required_dimensions: FrozenSet[str]
    shape: VerificationShape = VerificationShape.POINTWISE
    minimum_confidence: Optional[float] = None
    hard_stop_on_failure: bool = False

    def __post_init__(self) -> None:
        if not self.target_description:
            raise ValueError("VerificationRequirements.target_description must be non-empty")
        if not self.required_dimensions:
            raise ValueError("VerificationRequirements must specify at least one required dimension")
        if self.minimum_confidence is not None and not (0.0 <= self.minimum_confidence <= 1.0):
            raise ValueError(
                f"VerificationRequirements.minimum_confidence must be in [0.0, 1.0], "
                f"got {self.minimum_confidence}"
            )


@dataclass(frozen=True)
class VerificationPolicy:
    """System/Governance-set constraints -- never caller-set (v3 Part 1 section 3).

    A lower-authority requirement may tighten what a policy demands but
    must never relax below it -- the actual precedence RULE for resolving
    multiple applicable policies is v2 section 45's PolicyPrecedence,
    which this module does not build; VerificationPolicy is the thing
    that future precedence logic will apply to, not the ordering itself.
    """
    policy_id: str
    minimum_shape_for: Dict[str, VerificationShape] = field(default_factory=dict)
    mandatory_multi_verifier_dimensions: FrozenSet[str] = field(default_factory=frozenset)
    forbidden_methods: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("VerificationPolicy.policy_id must be non-empty")


@dataclass(frozen=True)
class VerificationStrategy:
    """Verification's own internal method-selection DECISION -- a result, not a request.

    Produced by combining VerificationRequirements + VerificationPolicy +
    risk/cost context (v2 sections 17, 32). References its inputs by ID
    rather than embedding copies, mirroring this codebase's established
    "reference, don't embed" pattern for provenance (evidence.py).
    """
    selected_shape: VerificationShape
    selected_methods: FrozenSet[str]  # v2 section 11 method names; VerificationMethod not yet built in code
    verifier_count: int
    derived_from_requirements: str  # opaque reference, not an embedded VerificationRequirements
    derived_from_policy: Optional[str] = None  # opaque reference; None if no policy applied

    def __post_init__(self) -> None:
        if self.verifier_count < 1:
            raise ValueError(f"VerificationStrategy.verifier_count must be >= 1, got {self.verifier_count}")
        if not self.selected_methods:
            raise ValueError("VerificationStrategy must select at least one method")
        if not self.derived_from_requirements:
            raise ValueError("VerificationStrategy.derived_from_requirements must be non-empty")


@dataclass(frozen=True)
class VerificationProfile:
    """A stable, named, external-facing bundle -- the one type in this module a typical caller touches directly.

    C-MoE requests a VerificationProfile BY NAME instead of constructing
    raw VerificationRequirements from scratch every time (v3 Part 1
    section 3). default_requirements is what that name currently expands
    to -- expected to be a small, fixed set of profiles (LIGHT/STANDARD/
    HIGH_ASSURANCE), not an open-ended registry.
    """
    name: VerificationProfileName
    default_requirements: VerificationRequirements
    description: str

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("VerificationProfile.description must be non-empty")
