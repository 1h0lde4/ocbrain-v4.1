"""
State / Transition / Invariant verification -- precision subtypes.

Architecture v3 Part 1 section 5: three subtypes under the dimension
taxonomy v2 section 11 describes.

  - StateVerification: "does X exist / is X true now"
  - TransitionVerification: "did action A correctly change S1 -> S2"
  - InvariantVerification: "did constraint X remain true throughout"

VerificationDimension (added 22 Sept 2026, Finding/Critique design pass):
the ten-value taxonomy these three subtypes attach to -- mission Sec16's
own list, taken directly rather than re-derived. A closed Enum, not
plain string constants like method.py's VerificationMethodType: methods
are deliberately open-ended (new verification techniques can always be
invented), but mission Sec16 gives a specific, finite list here, not an
extensible category. These three subtypes add precision to
STATE/TRANSITION/INVARIANT without introducing new top-level concepts
(v3's own framing): none of the three is a new kind of verdict or
evidence, only a more specific shape of check.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class VerificationDimension(str, Enum):
    """Mission Sec16: methods describe HOW, dimensions describe WHAT.
    Orthogonal to VerificationMethod by design (v2-frozen.md Sec11) --
    classified independently on a VerificationFinding, never nested."""
    PROCESS = "process"
    OUTCOME = "outcome"
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    GROUNDEDNESS = "groundedness"
    COMPLIANCE = "compliance"
    SAFETY = "safety"
    STATE = "state"
    TRANSITION = "transition"
    INVARIANT = "invariant"


@dataclass(frozen=True)
class StateVerification:
    """"Does X exist / is X true now" -- a point-in-time predicate check."""
    predicate_description: str
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.predicate_description:
            raise ValueError("StateVerification.predicate_description must be non-empty")


@dataclass(frozen=True)
class TransitionVerification:
    """"Did action A correctly change S1 -> S2" -- a before/after check."""
    action_description: str
    from_state_description: str
    to_state_description: str

    def __post_init__(self) -> None:
        if not self.action_description:
            raise ValueError("TransitionVerification.action_description must be non-empty")
        if not self.from_state_description or not self.to_state_description:
            raise ValueError(
                "TransitionVerification requires both from_state_description and to_state_description"
            )
        if self.from_state_description == self.to_state_description:
            raise ValueError(
                "TransitionVerification.from_state_description and to_state_description must differ "
                "-- a check against the same state is a StateVerification, not a transition"
            )


@dataclass(frozen=True)
class InvariantVerification:
    """"Did constraint X remain true throughout" -- a check over a span, not a point.

    window_end of None means the invariant's window is still open --
    checked up to now, not yet concluded either way.
    """
    invariant_description: str
    window_start: datetime
    window_end: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.invariant_description:
            raise ValueError("InvariantVerification.invariant_description must be non-empty")
        if self.window_end is not None and self.window_end < self.window_start:
            raise ValueError("InvariantVerification.window_end cannot precede window_start")
