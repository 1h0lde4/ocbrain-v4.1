"""eval_lab/contracts/authorization.py — side effects and authorization.

Implements §54, §68, §82 of the research report and §54 of this Slice.
Deliberately does not import from core/governance/ -- ADR-LAB-02's package
boundary requires contracts not depend on runtime service implementations,
and the governor classes there (AgentGovernor etc.) are stateful services,
not plain value types safe to reference from a contract (unlike
core.runtime.execution_outcome.FailureType, which failure.py does import,
being a pure stdlib-only enum with zero OCBrain-internal coupling). This
module's ActionType/AuthorizationOutcome are therefore Lab-owned rather
than adapted from an existing primitive -- §6's fallback for exactly this
situation ("create a Lab-owned representation/adapter instead").
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from eval_lab.contracts.serialization import ContractValidationError


class ActionType(str, Enum):
    """Per §54: read/write/delete plus external/irreversible side effects."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    IRREVERSIBLE_SIDE_EFFECT = "irreversible_side_effect"


class AuthorizationOutcome(str, Enum):
    """Per §54: authorization requirement and result, kept as a closed
    outcome set distinct from EvaluationStatus (a run can have
    authorization_outcome=DENIED and still be under evaluation -- these
    are not the same axis, per the amendment invariant "authorization is
    independent from task success")."""

    NOT_REQUIRED = "not_required"
    REQUIRED_AND_GRANTED = "required_and_granted"
    REQUIRED_AND_DENIED = "required_and_denied"
    REQUIRED_AND_UNKNOWN = "required_and_unknown"


@dataclass(frozen=True)
class SideEffectRecord:
    """One observed or expected side effect. `expected` and `observed` are
    separate fields (not one "did it happen" boolean) because the
    interesting evaluation question is usually whether they *match* --
    e.g. an unexpected irreversible side effect is a safety finding even
    if the task otherwise succeeded (research report §7a / amendment
    invariant: "side effects are independent from correctness")."""

    action_type: ActionType
    description: str
    expected: bool
    observed: bool | None = None
    """None = not yet checked (Slice 2 does not execute anything)."""
    is_irreversible: bool = False
    authorization: AuthorizationOutcome = AuthorizationOutcome.NOT_REQUIRED
    approval_reference: str | None = None

    def __post_init__(self) -> None:
        if self.authorization == AuthorizationOutcome.REQUIRED_AND_GRANTED and self.approval_reference is None:
            raise ContractValidationError(
                "granted_authorization_requires_approval_reference",
                "AuthorizationOutcome.REQUIRED_AND_GRANTED requires approval_reference to be set.",
            )

    @property
    def matched_expectation(self) -> bool | None:
        if self.observed is None:
            return None
        return self.expected == self.observed

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "description": self.description,
            "expected": self.expected,
            "observed": self.observed,
            "matched_expectation": self.matched_expectation,
            "is_irreversible": self.is_irreversible,
            "authorization": self.authorization.value,
            "approval_reference": self.approval_reference,
        }
