"""
core/runtime/execution_outcome.py — ExecutionOutcome (K4.4)

Structured classification for how an execution attempt ended, replacing the
generic-exception-collapses-to-"No response" pattern in the original bug
report. Additively attached to the existing WorkerResult
(core/workers/base.py) via `execution_detail` -- this module does not
introduce a competing result hierarchy; WorkerResult remains canonical.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class FailureType(str, Enum):
    """Distinguishes *why* an execution ended, so downstream code (and,
    eventually, a user-facing explanation) doesn't have to reverse-engineer
    a bare exception string. See spec: "Do not collapse all runtime
    failures into a generic exception message." """

    SUCCESS = "success"
    COMPLETED_WITH_PARTIAL_OUTPUT = "completed_with_partial_output"
    STALLED = "stalled"
    HARD_DEADLINE = "hard_deadline"
    CANCELLED = "cancelled"
    PROVIDER_FAILURE = "provider_failure"
    EMPTY_RESPONSE = "empty_response"
    VALIDATION_ERROR = "validation_error"
    OTHER_FAILURE = "other_failure"


# Failure types after which retrying the same execution is generally
# reasonable (a caller policy decision, not enforced here -- this is
# descriptive metadata, not a retry trigger by itself).
_RETRYABLE_BY_DEFAULT = frozenset({
    FailureType.STALLED,
    FailureType.PROVIDER_FAILURE,
    FailureType.EMPTY_RESPONSE,
})


@dataclass
class ExecutionOutcome:
    """Structured detail for one execution attempt's end state.

    Carried on WorkerResult.execution_detail (additive field). Never
    required -- code written against WorkerResult before this field existed
    continues to work; execution_detail is simply None for those paths.
    """

    failure_type: FailureType = FailureType.SUCCESS
    execution_id: str = ""
    provider: str = ""
    model: str = ""
    started_at: float = field(default_factory=time.monotonic)
    completed_at: Optional[float] = None
    elapsed_ms: float = 0.0
    last_progress_at: Optional[float] = None
    partial_output: Optional[str] = None
    recovery_action: str = ""
    watchdog_verdict: str = ""
    retryable: bool = False
    detail: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, **kwargs: Any) -> "ExecutionOutcome":
        return cls(failure_type=FailureType.SUCCESS, retryable=False, **kwargs)

    @classmethod
    def failure(cls, failure_type: FailureType, *, retryable: Optional[bool] = None, **kwargs: Any) -> "ExecutionOutcome":
        if retryable is None:
            retryable = failure_type in _RETRYABLE_BY_DEFAULT
        return cls(failure_type=failure_type, retryable=retryable, **kwargs)

    @property
    def is_success(self) -> bool:
        return self.failure_type in (FailureType.SUCCESS, FailureType.COMPLETED_WITH_PARTIAL_OUTPUT)


# ─────────────────────────────────────────────────────────────────────────
# CompletionStatus / CompletionReason / CompletionEvaluation (DEBT-020)
#
# Distinct axis from FailureType above. FailureType (and WorkerResult.success
# it's attached to) answers "did execution reach a terminal state without
# erroring" -- including, by design, a node recovered via error_branch. It
# was never intended to answer "did the output satisfy what the task
# actually required", and nothing enforced that distinction: the plain
# execution-status boolean propagated unchanged into workflow.completed's
# payload and from there into EvaluatorWorker's goal_completed, three layers
# removed from anything that could have checked scope.
#
# See docs/Bugs Hunt & fix reports/DEBT_020_PRE_IMPLEMENTATION_TRACE_AND_GATE_DESIGN.md
# for the live-path trace this repairs.
# ─────────────────────────────────────────────────────────────────────────


class CompletionStatus(str, Enum):
    """Did the task's authoritative completion conditions actually get
    satisfied? Independent of, and evaluated after, execution status."""

    SATISFIED = "satisfied"
    INCOMPLETE = "incomplete"
    VIOLATED = "violated"
    UNKNOWN = "unknown"


class CompletionReason(str, Enum):
    """Typed reason a non-SATISFIED CompletionStatus was reached -- same
    rationale as FailureType: downstream code and eventual user-facing
    explanations shouldn't have to reverse-engineer a free-text string.
    Only categories with an actual, populated source in this repository
    today; DEBT-020 explicitly forbids decorative values nothing ever sets."""

    NO_CHECKABLE_CONSTRAINT = "no_checkable_constraint"
    HARD_CONSTRAINT_VIOLATED = "hard_constraint_violated"
    PARTIAL_OUTPUT = "partial_output"
    EXECUTION_FAILURE = "execution_failure"
    CANCELLED = "cancelled"
    NO_RESULT = "no_result"
    COMPLETION_EVALUATION_FAILED = "completion_evaluation_failed"


@dataclass
class CompletionEvaluation:
    """Result of evaluating whether a task's authoritative completion
    conditions were satisfied. `reason` is "" exactly when
    `status == CompletionStatus.SATISFIED` -- there is nothing to explain
    in that case, matching WorkerResult.error's existing "" convention.
    """

    status: CompletionStatus = CompletionStatus.UNKNOWN
    reason: str = ""
    detail: str = ""
