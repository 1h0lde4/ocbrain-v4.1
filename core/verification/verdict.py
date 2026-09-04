"""
Verdict / result contracts. Truth status and execution status are
kept as genuinely separate concerns (architecture v1 Part-1 §25 /
mission's own §93 "no fake verification"): a verifier crash produces
VerificationExecutionFailure, never a positive VerificationVerdict,
and that rule is enforced in __post_init__ below -- not just stated.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .identity import VerificationId, TaskId, ExecutionId, AttemptId
from .epistemic import VerificationAssurance


class VerificationVerdict(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNVERIFIABLE = "unverifiable"
    CONDITIONAL = "conditional"
    ESCALATE = "escalate"
    UNSAFE_TO_VERIFY = "unsafe_to_verify"
    NOT_APPLICABLE = "not_applicable"


class VerificationExecutionFailure(str, Enum):
    """Deliberately separate from VerificationVerdict: a verifier
    crashing, timing out, or exhausting budget is an execution
    failure, not a semantic finding about the target."""
    TIMEOUT = "timeout"
    TOOL_FAILURE = "tool_failure"
    VERIFIER_CRASH = "verifier_crash"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class VerificationResult:
    verification_id: VerificationId
    task_id: TaskId
    execution_id: Optional[ExecutionId]  # None only when identity is genuinely unavailable
    attempt_id: Optional[AttemptId]
    verdict: VerificationVerdict
    assurance: VerificationAssurance
    confidence: float
    execution_failure: Optional[VerificationExecutionFailure] = None

    def __post_init__(self) -> None:
        if self.execution_failure is not None and self.verdict != VerificationVerdict.UNVERIFIABLE:
            raise ValueError(
                "an execution failure must produce UNVERIFIABLE, never a positive "
                "verdict -- a verifier crash cannot become PASS"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0.0, 1.0]")
