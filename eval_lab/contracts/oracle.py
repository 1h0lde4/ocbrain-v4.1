"""eval_lab/contracts/oracle.py — oracle definition and validation.

Implements ADR-LAB-06 §2 and §30-31 of this Slice's brief. `OracleDefinition`
is kept distinct from `EnvironmentState` (environment.py describes the
environment; this describes a mechanism that *interprets* it) and from
`EvaluatorDefinition` (evaluator.py) -- per ADR-LAB-06's own context, real
verifier-hacking incidents (Meta's Gaia2/ARE) happened precisely because
"what the oracle checked" and "what the evaluator concluded from that
check" were not independently examinable. `EvaluatorMetrics` (sensitivity/
specificity/precision/recall/abstention) lives in evaluator.py, not here,
even though this module's docstring/ADR reference it -- oracles and
evaluators share the same metric *shape* (ADR-LAB-06 §2's "oracles are
treated as classifiers"), so one type is reused for both rather than
duplicated (see evaluator.py's EvaluatorMetrics for the shared definition).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.enums import LifecycleState, ORACLE_SIMULATOR_LIFECYCLE
from eval_lab.contracts.identifiers import CURRENT_SCHEMA_VERSION, OracleId, OracleVersion, SchemaVersion
from eval_lab.contracts.serialization import ContractValidationError, frozen_mapping, nested


@dataclass(frozen=True)
class OracleDefinition:
    """Per ADR-LAB-06 §2: oracle_id, oracle_version, verification rules,
    input expectations, output semantics, provenance, configuration."""

    oracle_id: OracleId
    oracle_version: OracleVersion
    verification_rules_description: str
    input_expectations_description: str
    output_semantics_description: str
    is_deterministic: bool
    """Per ADR-LAB-06 §1/§2: even a deterministic oracle needs
    OracleValidation before backing a PROTECTED case (the competitive-
    programming false-positive example cited there) -- this field records
    the fact, it does not exempt a deterministic oracle from validation."""
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    configuration: dict[str, Any] = field(default_factory=dict)
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.lifecycle_state not in ORACLE_SIMULATOR_LIFECYCLE:
            raise ContractValidationError(
                "invalid_oracle_lifecycle_state", f"{self.lifecycle_state} is not a valid oracle lifecycle state."
            )
        # Correction pass: see serialization.frozen_mapping's docstring.
        object.__setattr__(self, "configuration", frozen_mapping(self.configuration))

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "oracle_version": self.oracle_version,
            "verification_rules_description": self.verification_rules_description,
            "input_expectations_description": self.input_expectations_description,
            "output_semantics_description": self.output_semantics_description,
            "is_deterministic": self.is_deterministic,
            "lifecycle_state": self.lifecycle_state.value,
            "configuration": dict(self.configuration),
            "schema_version": str(self.schema_version),
        }


@dataclass(frozen=True)
class OracleProbeCase:
    """One entry in an OracleValidation run. `expected_verdict` /
    `actual_verdict` are free-text (e.g. "pass"/"fail") rather than
    EvaluatorResultStatus -- an oracle probe checks the oracle's raw
    verdict on a constructed case, which is a narrower thing than a full
    EvaluationResult and shouldn't need result.py's richer type."""

    probe_case_id: str
    probe_type: str
    """One of: "known_good" | "known_bad" | "false_positive_probe" |
    "false_negative_probe" | "boundary" | "adversarial" |
    "mutation_perturbation" -- per ADR-LAB-06 §2's list, following the
    Meta ARE "Verifying the Verifier" pattern. Free string rather than an
    enum: this taxonomy is likely to grow as real probe cases accumulate,
    and a probe_type the contract layer doesn't recognize yet should not
    be a hard validation failure (§70's unknown-value extension policy)."""
    expected_verdict: str
    actual_verdict: str | None = None
    """None until the probe has actually been run against the oracle --
    Slice 2 defines the record, it does not run oracles (§2 scope boundary)."""
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_case_id": self.probe_case_id,
            "probe_type": self.probe_type,
            "expected_verdict": self.expected_verdict,
            "actual_verdict": self.actual_verdict,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class OracleValidation:
    """Per ADR-LAB-06 §2: required before an oracle backs a PROTECTED
    case. `probe_cases` holds the known-good/known-bad/false-positive/
    false-negative/boundary/adversarial/perturbation cases; summary metrics
    (sensitivity/specificity/...) are computed from these once run --
    Slice 2 provides `is_complete` as the only derived signal (are results
    recorded for every probe), leaving actual metric computation to
    whatever later slice runs the probes (this Slice's §31: "Future
    metrics ... No oracle execution engine")."""

    oracle_id: OracleId
    oracle_version: OracleVersion
    probe_cases: tuple[OracleProbeCase, ...]
    validated_at: datetime | None = None
    validated_by: str | None = None

    def __post_init__(self) -> None:
        if not self.probe_cases:
            raise ContractValidationError(
                "oracle_validation_requires_probe_cases", "probe_cases cannot be empty."
            )

    @property
    def is_complete(self) -> bool:
        """True once every probe case has a recorded actual_verdict --
        i.e. the probes have actually been run, not just defined."""
        return all(p.actual_verdict is not None for p in self.probe_cases)

    @property
    def probes_matching_expectation(self) -> int:
        return sum(1 for p in self.probe_cases if p.actual_verdict == p.expected_verdict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "oracle_version": self.oracle_version,
            "probe_cases": [p.to_dict() for p in self.probe_cases],
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "validated_by": self.validated_by,
            "is_complete": self.is_complete,
        }
