"""
Oracle (mission Sec35, Phase 2 -- epistemic spine): a mechanism that can
be invoked to determine correctness -- distinct from Reference/
GroundTruth (reference.py), which are static comparison values, not
invocable procedures.

Mission Sec35 is explicit that "executable", "reproducible",
"validated", and "authoritative" are not synonyms and must not be
inferred from one another. This module keeps them as four independent
fields rather than a single maturity-level enum, which would impose an
ordering the mission text specifically warns against assuming. The one
constraint enforced below (authoritative requires validated) is not an
exception to that -- it does not claim executable/reproducible/
validated form a ladder, only that asserting the strongest claim
(authoritative) without the one prerequisite check that claim depends
on (validated) is the exact unsupported-trust pattern Sec35 names.

The Evaluation Lab's own oracle-qualification machinery is the actual
qualification process (mission Sec36); this type is what core
Verification carries as the *result* of that process, not a
reimplementation of it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .identity import OracleId


@dataclass(frozen=True)
class Oracle:
    oracle_id: OracleId
    description: str
    is_executable: bool
    is_reproducible: bool
    is_validated: bool
    is_authoritative: bool = False

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("Oracle requires a non-empty description")
        if self.is_authoritative and not self.is_validated:
            raise ValueError(
                "an Oracle cannot be is_authoritative=True without "
                "is_validated=True -- authority asserted without the "
                "validation it depends on is exactly the unsupported "
                "trust claim mission Sec35 warns against"
            )
