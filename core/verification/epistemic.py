"""
Epistemic authority model.

Four distinct concepts, kept separate per architecture v3 Part 2:
  - VerificationBasis: what mechanisms contributed (compositional set)
  - ObservationAuthority: what source established the observation
  - InspectionAuthorization: is THIS verifier permitted to use THIS surface
  - VerificationAssurance: what assurance the whole verification provides,
    within an explicit, mandatory scope

This is Phase C's most architecturally load-bearing file: v1 modeled
VerificationBasis as a single exclusive enum, which was an actual bug
(a real verification is often deterministic AND runtime-observed AND
evidence-grounded at once) -- corrected in v2/v3 to a compositional
set. That correction is enforced here, not just documented.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional


class BasisComponent(str, Enum):
    """One atomic contributor to a verification."""
    DETERMINISTIC = "deterministic"
    RUNTIME_OBSERVATION = "runtime_observation"
    EXTERNAL_EVIDENCE = "external_evidence"
    MODEL_VERIFICATION = "model_verification"
    MULTI_VERIFIER = "multi_verifier"


@dataclass(frozen=True)
class VerificationBasis:
    """A SET of contributing mechanisms, never an exclusive single value."""
    components: FrozenSet[BasisComponent]

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError("VerificationBasis must have at least one component")

    def has(self, component: BasisComponent) -> bool:
        return component in self.components

    @property
    def is_deterministic_only(self) -> bool:
        return self.components == frozenset({BasisComponent.DETERMINISTIC})


class ObservationAuthority(str, Enum):
    """What source established the observation. Epistemic -- distinct
    from InspectionAuthorization, which is a permission check."""
    RUNTIME = "runtime"
    FILESYSTEM = "filesystem"
    TEST_RUNNER = "test_runner"
    DATABASE = "database"
    TRUSTED_EXTERNAL_SOURCE = "trusted_external_source"
    HUMAN = "human"
    MODEL = "model"


@dataclass(frozen=True)
class InspectionAuthorization:
    """Is this verifier permitted to use this observation surface at
    all. Deliberately separate from ObservationAuthority: technical
    accessibility is not the same thing as being authorized. Owned
    conceptually by Governance/Runtime; represented here so
    Verification can carry and check it rather than assume it."""
    surface: str
    authorized: bool
    authorized_by: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class VerificationAssurance:
    """What assurance the complete verification provides, WITHIN ITS
    EXPLICIT SCOPE. Never an alias for 'deterministic' or 'high
    confidence' on its own -- assurance_scope is mandatory, not
    optional, and enforced below."""
    basis: VerificationBasis
    observation_authority: ObservationAuthority
    inspection_authorization: InspectionAuthorization
    assurance_scope: str
    coverage: float  # 0.0-1.0, scoped to assurance_scope -- NOT whole-task coverage
    independence_level: str
    integrity_verified: bool

    def __post_init__(self) -> None:
        if not self.assurance_scope:
            raise ValueError(
                "assurance_scope is required -- assurance must always be scoped "
                "(architecture v2 Part 2 §15: assurance=HIGH,scope=artifact_schema "
                "must never be read as assurance=HIGH,scope=whole_task_correctness)"
            )
        if not (0.0 <= self.coverage <= 1.0):
            raise ValueError("coverage must be in [0.0, 1.0]")
        if not self.inspection_authorization.authorized:
            raise ValueError(
                "cannot construct VerificationAssurance over an unauthorized "
                "inspection surface -- InspectionAuthorization.authorized must be True"
            )
