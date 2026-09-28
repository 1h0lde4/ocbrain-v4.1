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
from enum import Enum
from typing import Optional

from .identity import AssumptionId


class AssumptionSourceKind(str, Enum):
    """Category of where an assumption originated.

    IMPLEMENTATION JUDGMENT: the frozen architecture (v2 §25) requires
    AssumptionSource to exist as a distinct concept but does not prescribe
    a closed source-kind vocabulary.  These values represent the smallest
    set that makes source category semantically queryable without
    collapsing into a single opaque string.

    None of these values automatically imply authority -- a HUMAN source
    is not thereby authoritative, and a MODEL source is not thereby
    suspect.  Authority remains a separate epistemic property
    (ObservationAuthority in epistemic.py, VerificationAssurance, etc.).

    This is NOT an alias for ObservationAuthority (epistemic.py):
      ObservationAuthority = what source established an observation
      AssumptionSourceKind = what category of origin produced an assumption
    They answer different questions about different objects.
    """
    HUMAN = "human"
    MODEL = "model"
    SYSTEM = "system"
    POLICY = "policy"
    DOCUMENTATION = "documentation"


@dataclass(frozen=True)
class AssumptionSource:
    """Where an assumption originated -- provenance, not authority.

    source_kind: the category of origin (AssumptionSourceKind).
    source_identifier: who/what specifically (e.g. "human:moncif",
        "model:claude-sonnet-5", "policy:safety-critical-v1",
        "system:runtime_defaults", "documentation:api-spec-v2").

    This is sufficient structured provenance to make the source
    semantically queryable (by kind and by identity) without inventing
    a full provenance framework.

    Authority is NOT inferable from this type:
      - HUMAN source does not automatically confer authority.
      - MODEL source does not automatically confer or deny authority.
      - POLICY source does not automatically confer authority.
    Authority remains independently established at higher layers.
    """
    source_kind: AssumptionSourceKind
    source_identifier: str

    def __post_init__(self) -> None:
        if not self.source_identifier or not self.source_identifier.strip():
            raise ValueError(
                "AssumptionSource requires a non-empty source_identifier"
            )


class AssumptionStatus(str, Enum):
    """Semantic status of an assumption -- NOT a VerificationVerdict.

    IMPLEMENTATION JUDGMENT: the frozen architecture (v2 §25) requires
    the concept but does not prescribe a closed vocabulary.  The
    following four states are the smallest set that preserves the
    required semantic distinctions:

    - UNEXAMINED: not yet evaluated.  Must survive serialization without
      collapsing into REJECTED, CONFIRMED, or any other state.
      UNEXAMINED != REJECTED.  UNEXAMINED != CONFIRMED.

    - CHALLENGED: the assumption has been questioned but not resolved.
      CHALLENGED != "verified failure" -- it means the assumption is
      under scrutiny, not that it has been found false.

    - CONFIRMED: evidence or authority supports the assumption continuing
      to hold.  NOT VerificationVerdict.VERIFIED -- confirmation of an
      assumption is an epistemic judgment about a prerequisite, not a
      verification verdict about a target.

    - REJECTED: evidence or analysis has determined the assumption does
      not hold.  NOT VerificationVerdict.CONTRADICTED -- rejection of an
      assumption is about the prerequisite, not the verification target.

    There is deliberately NO implicit ordering or numeric trust scale.
    A later change to an assumption's status requires constructing a new
    Assumption instance (frozen=True), compatible with the immutable
    receipt/supersession model -- an already-issued VerificationReceipt
    that recorded a prior status retains its historical meaning.
    """
    UNEXAMINED = "unexamined"
    CHALLENGED = "challenged"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Assumption:
    """
    Mission §32: "A result should be able to answer: What had to be
    true for this verification statement to hold?" -- relied_upon_for
    exists so that answer is queryable directly rather than left
    implicit in a verifier's prose.

    source (IMPLEMENTATION JUDGMENT): Optional[AssumptionSource].
    Optional to preserve backward compatibility with existing
    construction sites that create Assumption without structured
    provenance.  The architecture says assumptions should be
    "identified and tagged" (v2 §25) but does not mandate that
    every Assumption carry structured source at construction time.

    status: defaults to UNEXAMINED -- the only safe default, since
    an unexamined assumption must never be silently treated as
    confirmed or rejected.
    """
    assumption_id: AssumptionId
    description: str
    relied_upon_for: str  # what part of the verification depends on this holding
    source: Optional[AssumptionSource] = None
    status: AssumptionStatus = AssumptionStatus.UNEXAMINED

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("Assumption requires a non-empty description")
        if not self.relied_upon_for or not self.relied_upon_for.strip():
            raise ValueError("Assumption requires non-empty relied_upon_for")
