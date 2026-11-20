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

    @property
    def is_fully_satisfied(self) -> bool:
        """DEBT-020 (Kernel freeze blocker, fixed 2026-09-06): distinct
        from is_success above. is_success answers "did this produce usable
        output" (True for a genuinely truncated/partial generation too --
        useful for retry/recovery logic that would rather have something
        than nothing); this answers "did this fully complete" (True only
        for FailureType.SUCCESS). The two were previously conflated into
        one is_success that always returned True for
        COMPLETED_WITH_PARTIAL_OUTPUT, which is the shape of bug DEBT-020
        is about generally -- production code treating incomplete work as
        equivalent to complete work.

        Traced (not assumed) while fixing this: is_success has zero
        callers anywhere in production code, and COMPLETED_WITH_PARTIAL_
        OUTPUT is never constructed by ModelRouter's
        _call_monitored_streaming() path. That path produces SUCCESS,
        PROVIDER_FAILURE, STALLED, HARD_DEADLINE, or EMPTY_RESPONSE.
        ModelRouterAdapter.execute() reads RouteResult.execution_detail
        and converts non-success outcomes to CapabilityResult(success=False),
        so monitored long-form failures do reach the live workflow path.
        However, AdapterRuntime may try fallback adapters and its final
        all-failed result currently retains only adapters_tried metadata;
        CapabilityExecutorWorker preserves the typed CANCELLED outcome
        but not other failure subtypes or partial output. The separate
        The direct stream_route() endpoint now uses the same monitored
        outcome internally, forwards tokens through a bounded queue, and
        emits a typed terminal error marker on failure; its public contract
        remains a token stream rather than an ExecutionOutcome. Typed-outcome
        propagation is still incomplete across adapter fallback and
        CapabilityExecutorWorker for non-cancellation failure subtypes.
        Keeping is_success distinct from is_fully_satisfied prevents future
        callers from silently treating incomplete work as fully complete.
        """
        return self.failure_type == FailureType.SUCCESS
