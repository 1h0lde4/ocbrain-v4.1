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
