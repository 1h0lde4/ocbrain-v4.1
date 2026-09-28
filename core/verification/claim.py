"""
Claim (architecture v1 §12, mission §7.8, §30, Phase 2 -- epistemic
spine): an assertion under verification.

A Claim may originate directly (a stated requirement, a user
assertion) or via an Observation -> Interpretation chain
(observation.py). Both are represented and kept distinguishable --
mission §30 is explicit that "evidence supports a claim" is a
different fact from "evidence proves where the claim came from", and
collapsing origin into an unattributed string would make that
distinction unenforceable. This module only says where a Claim came
from; whether it is well-supported is evidence.py/the assessment layer's
question, not this one's.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .identity import ClaimId, ObservationId


class ClaimOrigin(str, Enum):
    """How this Claim came to exist -- not how well-supported it is,
    and not its authority. A DIRECT_ASSERTION claim is not thereby
    more trustworthy than an INTERPRETED_OBSERVATION one; origin and
    warrant are different axes."""
    DIRECT_ASSERTION = "direct_assertion"
    INTERPRETED_OBSERVATION = "interpreted_observation"
    DERIVED = "derived"  # inferred from other Claims, not from a fresh Observation


@dataclass(frozen=True)
class Claim:
    claim_id: ClaimId
    content: str
    origin: ClaimOrigin
    source_observation_id: Optional[ObservationId] = None

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise ValueError("Claim requires non-empty content")
        if self.origin is ClaimOrigin.INTERPRETED_OBSERVATION and self.source_observation_id is None:
            raise ValueError(
                "a Claim with origin=INTERPRETED_OBSERVATION must record "
                "source_observation_id -- an 'interpreted' claim with "
                "nothing to point back to is unattributed, not derived"
            )
        if self.origin is not ClaimOrigin.INTERPRETED_OBSERVATION and self.source_observation_id is not None:
            raise ValueError(
                "source_observation_id is only meaningful for "
                "origin=INTERPRETED_OBSERVATION -- setting it for "
                "DIRECT_ASSERTION or DERIVED implies an observation "
                "chain that isn't actually there"
            )


class ClaimDependencyType(str, Enum):
    """How one claim depends on another -- NOT how well-supported either
    claim is, and NOT how either claim came to exist (that's ClaimOrigin).

    IMPLEMENTATION JUDGMENT: the frozen architecture (v1 §42, v2 §49)
    names ClaimDependency as a required type but does not prescribe a
    dependency taxonomy.  Two values chosen as the minimal set that makes
    the concept semantically queryable without overlapping with:
      - ClaimOrigin (how a claim came to exist)
      - derived_from (artifact/resource lineage, cognitive layer)
      - caused_by (causal event linkage, cognitive layer)
      - evidence support/refutation (evidence.py)
      - verification disposition (verdict.py)
    """
    RELIES_ON = "relies_on"          # dependent claim's truth requires the
                                     # depended-upon claim to hold
    PRESUPPOSES = "presupposes"      # dependent claim's meaning/interpretability
                                     # depends on the depended-upon claim


@dataclass(frozen=True)
class ClaimDependency:
    """An immutable dependency edge: claim_id depends on
    depends_on_claim_id via dependency_type.

    This type answers ONLY: "which claim depends on which other claim?"
    It does NOT answer:
      - which claim is true
      - which claim is supported by evidence
      - which claim is authoritative
      - how either claim came to exist (that's ClaimOrigin)

    Reconciliation with existing provenance concepts:
      ClaimOrigin      = how a claim came to exist
                         (DIRECT_ASSERTION / INTERPRETED_OBSERVATION / DERIVED)
      ClaimDependency  = what other claim this claim relies on at
                         verification time
      derived_from     = artifact/resource lineage (cognitive layer)
      caused_by        = causal event linkage (cognitive layer)

    These four concepts are kept deliberately non-overlapping.

    Structural parallel: CriterionDependency (rubric.py) -- same pattern,
    same self-dependency guard, no independent identity wrapper.
    """
    claim_id: ClaimId
    depends_on_claim_id: ClaimId
    dependency_type: ClaimDependencyType

    def __post_init__(self) -> None:
        if self.claim_id == self.depends_on_claim_id:
            raise ValueError(
                f"claim {self.claim_id!r} cannot depend on itself"
            )
