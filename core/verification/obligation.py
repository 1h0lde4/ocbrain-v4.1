"""
Verification obligation contracts (architecture v2 Part 2 §8, mission
§11-12): what an obligation to verify actually is, where it came from,
and why this record deliberately carries no closure status.

An obligation is the definitional link between "something needs to be
verified" and "here is exactly why" -- derivation provenance, not an
outcome. It does not carry a verdict, a verified/unverified flag, or any
other field a later Result could silently disagree with. Mission §12's
own warning -- "never let 'not run' become 'verified' implicitly" -- is
exactly the failure mode a status field on this class would invite: a
default value, an unset field, or a stale copy would all read as *some*
answer rather than as the explicit absence of one. Closure belongs to
the Result/Receipt lineage that will reference an obligation_id once
VerificationRun exists (Phase 7-8), not here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .identity import ObligationId, RubricId


class DerivationSource(str, Enum):
    """
    Where an obligation came from (v2 §8, verbatim list). A model-derived
    obligation is exactly as real an obligation as any other -- it still
    needs verifying -- but it must never be mistaken for one a human
    actually asked for. See VerificationObligation.carries_explicit_user_authority
    below for the one place this distinction is load-bearing in this module.
    """
    EXPLICIT_USER_REQUIREMENT = "explicit_user_requirement"
    CONSTRAINT = "constraint"
    PLAN_REQUIREMENT = "plan_requirement"
    POSTCONDITION = "postcondition"
    CAPABILITY_CONTRACT = "capability_contract"
    SYSTEM_INVARIANT = "system_invariant"
    MODEL_DERIVED = "model_derived"


@dataclass(frozen=True)
class VerificationObligation:
    """
    A single thing that needs to be verified, and why. Compiles into a
    Rubric -- rubric_id is set once that compilation happens, None
    beforehand, never guessed or defaulted to a placeholder rubric.
    """
    obligation_id: ObligationId
    derivation_source: DerivationSource
    description: str
    source_reference: str
    rubric_id: Optional[RubricId] = None

    def __post_init__(self) -> None:
        if not self.obligation_id:
            raise ValueError("VerificationObligation requires a non-empty obligation_id")
        if not self.description or not self.description.strip():
            raise ValueError("VerificationObligation requires a non-empty description")
        if not self.source_reference or not self.source_reference.strip():
            raise ValueError(
                "VerificationObligation requires a non-empty source_reference -- "
                "provenance is mandatory even for model_derived obligations, "
                "which must cite what reasoning produced them, not merely that "
                "something did"
            )

    @property
    def carries_explicit_user_authority(self) -> bool:
        """
        True only when derivation_source is EXPLICIT_USER_REQUIREMENT.
        Deliberately a computed property, not a stored field, so a
        model_derived obligation cannot be constructed with this fact
        overridden -- there is no field to pass a conflicting value into.
        """
        return self.derivation_source is DerivationSource.EXPLICIT_USER_REQUIREMENT
