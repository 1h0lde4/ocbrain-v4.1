"""
core/verification/construct.py -- Batch 3A: VerificationConstruct / ConstructValidity.

v2 §9: "A rubric defines what's being checked; it doesn't prove that's the
right thing to check."  Construct validity is evaluated separately from
rubric-execution stability, and neither substitutes for the other (v2 §1,
v3 "construct validity vs. verifier stability: unchanged").  This module keeps
three things apart:

    what the rubric claims to measure   -> VerificationConstruct
    whether that claim has been assessed -> ConstructValidity
    whether a verifier is self-consistent -> (not here; a different axis)

The frozen architecture names the concepts but defines no fields and no closed
vocabulary.  Everything below that is not stated in v2 §9 is an IMPLEMENTATION
JUDGMENT, marked as such.

Not in this module (Batch 3A scope): observation/coverage types,
CriterionResult, anything runtime, any stability/confidence/verdict notion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class VerificationConstruct:
    """What a rubric claims to measure, in words (v2 §9).

    A value object with deliberately no identity of its own: it is defined by
    the Rubric that carries it (``Rubric.construct``) and is not independently
    addressable.  No construct_id, category, domain, metric or unit -- none of
    those is established by the architecture.

    Invariant: ``description`` is a string that is non-empty after
    normalization.  Normalization here is ``str.strip()``, the same rule the
    other contracts in this package use for required text.  The value is stored
    exactly as given.  (Like every contract in this package, this does not
    treat invisible format characters such as zero-width spaces as blank.)
    """

    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(
                "VerificationConstruct requires a non-empty description"
            )


class ConstructValidityStatus(str, Enum):
    """State of a construct-validity *assessment*.

    IMPLEMENTATION JUDGMENT: v2 §9 requires construct validity to be assessed
    separately but prescribes no closed vocabulary.  These four states are the
    smallest set that keeps "not yet looked at" distinct from "looked at and
    found wanting":

    - NOT_EVALUATED: no assessment has been made.  Must survive
      serialization without collapsing into any other state.
    - SUPPORTED: the assessment found support for the construct.  It does
      NOT mean the construct is proven or correct.
    - CONTESTED: the assessment found the construct disputed; unresolved.
    - UNSUPPORTED: the assessment found no support for the construct.  It
      does NOT mean the construct is false.

    This is not a verdict on any verification result, not a confidence
    measure, and not a measure of verifier stability.  There is deliberately
    no ordering: SUPPORTED is not "greater than" CONTESTED.

    The string values are namespaced (``construct_*``) on purpose.  This is a
    ``str`` enum, so a member compares equal to any other ``str`` enum member
    with the same value; ``VerificationVerdict`` already has an ``UNSUPPORTED``
    value of ``"unsupported"``, and sharing it would make
    ``ConstructValidityStatus.UNSUPPORTED == VerificationVerdict.UNSUPPORTED``
    true and let the two collide as dict keys or set members.
    """

    NOT_EVALUATED = "construct_not_evaluated"
    SUPPORTED = "construct_supported"
    CONTESTED = "construct_contested"
    UNSUPPORTED = "construct_unsupported"


@dataclass(frozen=True)
class ConstructValidity:
    """An immutable record of one construct-validity assessment.

    It refers to the rubric it assesses only by value -- ``rubric_fingerprint``
    -- never by reference.  Consequences that are the point of the design:

    * It cannot alter the Rubric it evaluates: it holds no Rubric, and Rubric
      holds no ConstructValidity.
    * It never participates in the Rubric's identity or fingerprint, so
      assessing a rubric cannot change which rubric it is (no circularity).
    * History is not rewritten: a changed assessment is a *new* record.
      Mutating ``status`` is impossible (frozen), so an earlier record keeps
      meaning what it meant.

    Its only other field is ``status``, which must be a
    ``ConstructValidityStatus`` -- a ``VerificationVerdict``, a confidence
    value or a bare string is rejected, not coerced.  There is no stability,
    consistency, confidence, verdict or score field: those are other axes.
    """

    rubric_fingerprint: str
    status: ConstructValidityStatus

    def __post_init__(self) -> None:
        if not isinstance(self.rubric_fingerprint, str) or not self.rubric_fingerprint.strip():
            raise ValueError(
                "ConstructValidity requires a non-empty rubric_fingerprint"
            )
        if not isinstance(self.status, ConstructValidityStatus):
            raise TypeError(
                f"ConstructValidity.status must be a ConstructValidityStatus, "
                f"got {type(self.status).__name__} -- it is not a verdict, a "
                f"confidence value or a stability measure and is never coerced "
                f"from one"
            )
