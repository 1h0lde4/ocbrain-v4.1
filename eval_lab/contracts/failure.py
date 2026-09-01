"""eval_lab/contracts/failure.py — normalized failure records and error envelopes.

Implements §44-45 of this Slice and the mission's failure-taxonomy
sections. Per §44's explicit instruction ("Do not invent competing
runtime failure taxonomies where an existing stable one can be
reused/adapted"): `core.runtime.execution_outcome.FailureType` already
classifies *why a single execution attempt ended* (SUCCESS,
COMPLETED_WITH_PARTIAL_OUTPUT, STALLED, HARD_DEADLINE, CANCELLED,
PROVIDER_FAILURE, EMPTY_RESPONSE, VALIDATION_ERROR, OTHER_FAILURE), and
is imported here rather than re-invented for FailureRecords whose
fault_domain is SUBJECT or INFRASTRUCTURE.

This import was checked against ADR-LAB-02's package-boundary rule before
being added: `core/runtime/execution_outcome.py` has zero OCBrain-internal
imports (stdlib only: `time`, `dataclasses`, `enum`, `typing`) and defines
a plain, stateless, side-effect-free `class FailureType(str, Enum)` -- not
a runtime service, database connection, or worker instance, which is what
§6/§86 actually prohibit contracts from depending on. Importing a pure
enum value-type is exactly the "stable identifier" §6 says to prefer.
ORACLE/EVALUATOR/JUDGE/DATA/INTEGRITY fault domains have no equivalent in
FailureType (the runtime has no concept of "judge" or "oracle"), so those
use Lab-owned free-text categories instead -- see `EVALUATION_FAILURE_CATEGORIES`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from core.runtime.execution_outcome import FailureType  # see module docstring: verified safe, stdlib-only, zero coupling

from eval_lab.contracts.enums import FaultDomain
from eval_lab.contracts.identifiers import FailureRecordId
from eval_lab.contracts.serialization import ContractValidationError


class Severity(str, Enum):
    """Correction pass: ErrorEnvelope.severity was a raw `str` with a
    manual membership check -- same gap as EvaluatorRelationshipType and
    AnnotationVerdict (result.py, evidence.py). A closed, small,
    architecturally-defined set."""

    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

# Lab-owned failure categories for the fault domains FailureType has no
# concept of (§44's coverage list, minus SUBJECT/INFRASTRUCTURE which defer
# to FailureType above). Free strings, not a closed Enum, per the same
# extensibility reasoning as TrajectoryEvent.raw_type_name (§35/§70): this
# taxonomy will grow as real failures accumulate, and an unrecognized
# category should not be a hard validation failure.
EVALUATION_FAILURE_CATEGORIES: dict[FaultDomain, frozenset[str]] = {
    FaultDomain.ENVIRONMENT: frozenset({
        "resource_exhaustion", "unrealistic_behavior", "setup_failure", "state_corruption",
    }),
    FaultDomain.ORACLE: frozenset({
        "false_positive", "false_negative", "gamed", "crashed", "ambiguous_verdict",
    }),
    FaultDomain.EVALUATOR: frozenset({
        "crashed", "malformed_input", "missing_evidence", "quarantined_evaluator_used",
    }),
    FaultDomain.JUDGE: frozenset({
        "unavailable", "timeout", "disagreement_unresolved", "bias_detected", "low_confidence_forced_verdict",
    }),
    FaultDomain.DATA: frozenset({
        "corrupt_artifact", "missing_reference", "schema_mismatch", "duplicate_event", "out_of_order_event",
    }),
    FaultDomain.INTEGRITY: frozenset({
        "tamper_detected", "hash_mismatch", "evaluator_gaming_detected", "unauthorized_modification",
    }),
}


@dataclass(frozen=True)
class FailureRecord:
    """One normalized failure. `fault_domain` is the primary classification
    (per the amendment invariants: subject != environment != oracle !=
    evaluator != judge failure); `runtime_failure_type` is populated only
    when fault_domain is SUBJECT or INFRASTRUCTURE and the failure actually
    traces back to a runtime ExecutionOutcome; `category` covers the
    Lab-specific domains via EVALUATION_FAILURE_CATEGORIES above."""

    failure_record_id: FailureRecordId
    fault_domain: FaultDomain
    category: str
    description: str
    occurred_at: datetime
    runtime_failure_type: FailureType | None = None
    trajectory_event_id: str | None = None
    recoverable: bool | None = None

    def __post_init__(self) -> None:
        if self.runtime_failure_type is not None and self.fault_domain not in (
            FaultDomain.SUBJECT, FaultDomain.INFRASTRUCTURE,
        ):
            raise ContractValidationError(
                "runtime_failure_type_wrong_domain",
                "runtime_failure_type may only be set when fault_domain is "
                "SUBJECT or INFRASTRUCTURE (it has no meaning for "
                "ORACLE/EVALUATOR/JUDGE/DATA/INTEGRITY, which don't exist "
                "in the runtime's own vocabulary).",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_record_id": self.failure_record_id,
            "fault_domain": self.fault_domain.value,
            "category": self.category,
            "description": self.description,
            "occurred_at": self.occurred_at.isoformat(),
            "runtime_failure_type": self.runtime_failure_type.value if self.runtime_failure_type else None,
            "trajectory_event_id": self.trajectory_event_id,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True)
class ErrorEnvelope:
    """Per §45: minimal contract-level error representation for
    contract/schema/evaluation-layer failures -- e.g. what a future
    deserializer raises on a malformed record, not a runtime exception."""

    error_code: str
    domain: FaultDomain
    message: str
    severity: Severity = Severity.ERROR
    recoverable: bool = False
    source: str | None = None
    cause_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.severity, Severity):
            raise ContractValidationError(
                "severity_not_enum_member", f"severity must be a Severity member, got {type(self.severity).__name__}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "domain": self.domain.value,
            "message": self.message,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "source": self.source,
            "cause_reference": self.cause_reference,
        }
