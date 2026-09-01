"""eval_lab/contracts/simulator.py — user simulator definition and reliability.

Implements ADR-LAB-06 §2's simulator half and §32 of this Slice. Mirrors
oracle.py's shape deliberately (OracleValidation <-> SimulatorReliability
are the same idea applied to a different trust-requiring mechanism), per
ADR-LAB-06's own framing of oracle/simulator trust as one decision with
two applications -- but kept as separate concrete types rather than one
generic "ValidatedMechanism" base class, since forcing them under one
supertype for two fields' worth of shared shape would be exactly the
"generic framework abstraction" PROJECT_INSTRUCTIONS.md warns against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.enums import LifecycleState, ORACLE_SIMULATOR_LIFECYCLE
from eval_lab.contracts.identifiers import CURRENT_SCHEMA_VERSION, SchemaVersion, SimulatorId, SimulatorVersion
from eval_lab.contracts.serialization import ContractValidationError, frozen_mapping


@dataclass(frozen=True)
class UserSimulatorDefinition:
    """Per ADR-LAB-06 §2: simulator_id, simulator_version, configuration,
    scenario/script reference. `known_failure_modes` defaults to the two
    named in the research report (§7a.5): sycophancy and unrealistic
    persona consistency -- not because every simulator necessarily has
    both, but because a simulator definition that hasn't considered
    either should say so explicitly rather than silently have an empty
    list read as "checked, found none."""

    simulator_id: SimulatorId
    simulator_version: SimulatorVersion
    scenario_reference: str
    model_identity_description: str
    configuration: dict[str, Any] = field(default_factory=dict)
    known_failure_modes_considered: frozenset[str] = field(
        default_factory=lambda: frozenset({"sycophancy", "unrealistic_persona_consistency"})
    )
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.lifecycle_state not in ORACLE_SIMULATOR_LIFECYCLE:
            raise ContractValidationError(
                "invalid_simulator_lifecycle_state",
                f"{self.lifecycle_state} is not a valid simulator lifecycle state.",
            )
        # Correction pass: see serialization.frozen_mapping's docstring.
        object.__setattr__(self, "configuration", frozen_mapping(self.configuration))

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulator_id": self.simulator_id,
            "simulator_version": self.simulator_version,
            "scenario_reference": self.scenario_reference,
            "model_identity_description": self.model_identity_description,
            "configuration": dict(self.configuration),
            "known_failure_modes_considered": sorted(self.known_failure_modes_considered),
            "lifecycle_state": self.lifecycle_state.value,
            "schema_version": str(self.schema_version),
        }


@dataclass(frozen=True)
class SimulatorAuditSample:
    """One audited conversation. Mirrors the AURA/CRMArena-Pro methodology
    cited in ADR-LAB-06 §1: a small human-audited sample checking whether
    the simulator followed its own script -- `deviated_from_script` is the
    single boolean that methodology actually needs; free-text `notes`
    holds the specifics."""

    conversation_id: str
    deviated_from_script: bool
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "deviated_from_script": self.deviated_from_script,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class SimulatorReliability:
    """Per ADR-LAB-06 §2: required before a simulator backs a PROTECTED
    case. `audit_samples` holds the human-audited conversations; the
    deviation rate is a derived property, not a stored/settable field, so
    it can never drift out of sync with the underlying samples."""

    simulator_id: SimulatorId
    simulator_version: SimulatorVersion
    audit_samples: tuple[SimulatorAuditSample, ...]
    audited_at: datetime | None = None
    audited_by: str | None = None

    def __post_init__(self) -> None:
        if not self.audit_samples:
            raise ContractValidationError(
                "simulator_reliability_requires_audit_samples", "audit_samples cannot be empty."
            )

    @property
    def deviation_rate(self) -> float:
        return sum(1 for s in self.audit_samples if s.deviated_from_script) / len(self.audit_samples)

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulator_id": self.simulator_id,
            "simulator_version": self.simulator_version,
            "audit_samples": [s.to_dict() for s in self.audit_samples],
            "audited_at": self.audited_at.isoformat() if self.audited_at else None,
            "audited_by": self.audited_by,
            "deviation_rate": self.deviation_rate,
            "n_audited": len(self.audit_samples),
        }
