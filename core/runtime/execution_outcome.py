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
