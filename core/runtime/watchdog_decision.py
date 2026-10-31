"""
core/runtime/watchdog_decision.py — shared stall/extension/cancel decision core.

Extracted from core/runtime/execution_watchdog.py as part of the DEBT-016
reconciliation (KNOWN_ISSUES.md; see ADR-KERNEL-02). Prior to this module,
this logic existed once, privately, inside execution_watchdog.py, and the
graph-aware watchdog (core/runtime/watchdog.py) re-implemented a much
cruder version of it independently — detecting a stalled node but never
attempting bounded recovery or ever cancelling *because of* a stall (only
ever cancelling on the unrelated hard-ceiling expiry). This module is the
one place that decision now lives; both watchdogs call it.

Detection vs. policy vs. enforcement (unchanged from execution_watchdog.py's
original framing):
    Watchdog           -> condition detected   (this module, decide())
    RecoveryPolicy      -> action selected      (this module, decide())
    CancellationToken   -> action executed      (core/runtime/cancellation.py)

Recovery-invariant compliance (ADR-K4.2-H-05): the bounded extension this
module may grant on a detected stall is NOT a recovery attempt in
`OperationRecoveryBudget`'s sense (core/cognitive/recovery.py). It never
re-enters the Planner, never triggers Supervisor re-entry, and never
creates a new operation — it is strictly intra-operation: the same
execution attempt (or, for the graph-aware caller, the same workflow
execution) is allowed more wall clock, once per stall episode, bounded by
`ExecutionBudget.max_extension_s`. Nothing here reads or writes
`OperationRecoveryBudget`.

Why a Protocol instead of a concrete monitor type
--------------------------------------------------
The two watchdogs observe progress through genuinely different shapes:
`progress_monitor.ProgressMonitor` (one in-memory counter pair per LLM
generation attempt) vs. a computed, per-poll-tick aggregate over an
`ExecutionGraph`'s several concurrent nodes (core/runtime/watchdog.py).
Rather than forcing a graph-wide adapter to fabricate a fake
`ProgressMonitor`, `decide()` is typed against the minimal structural
`ProgressSignal` it actually needs. `progress_monitor.ProgressMonitor`
already satisfies this Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from core.runtime.execution_budget import ExecutionBudget


class CancelReason(str, Enum):
    """Typed cancellation reasons.

    Deliberately str-backed: passed as plain strings into the existing,
    unmodified CancellationToken.cancel(reason: str = "cancelled") — so
    every existing caller of cancel() keeps working exactly as before, and
    new watchdog-triggered cancellations get real, comparable typed values
    (token.reason == CancelReason.STALL.value).
    """

    STALL = "stall"
    HARD_DEADLINE = "hard_deadline"
    EXTERNAL = "external"


class WatchdogVerdict(str, Enum):
    HEALTHY = "healthy"
    SLOW_BUT_PROGRESSING = "slow_but_progressing"
    RECOVERING = "recovering"
    EXTENDED = "extended"
    STALLED = "stalled"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Decision:
    verdict: WatchdogVerdict
    should_cancel: bool
    cancel_reason: Optional[CancelReason] = None


@runtime_checkable
class ProgressSignal(Protocol):
    """The minimal shape decide() needs from a progress source.

    `progress_monitor.ProgressMonitor` satisfies this structurally with no
    changes beyond adding `is_actively_progressing()` (a one-line wrapper
    around its existing `snapshot().state`, see that module). Graph-aware
    callers build a lightweight, already-resolved, synchronous adapter from
    one `await graph.snapshot()` call per poll tick — see
    core/runtime/watchdog.py's `_GraphProgressSignal`.
    """

    def has_progressed(self) -> bool:
        """Whether at least one meaningful-progress event has ever been
        observed. Distinguishes "never started" (startup-deadline concern)
        from "started, then went quiet" (stall concern)."""
        ...

    def since_last_progress_s(self) -> float:
        """Seconds since the last meaningful-progress event. Only
        meaningful once has_progressed() is True."""
        ...

    def is_actively_progressing(self) -> bool:
        """Whether progress is happening right now (as opposed to: within
        the progress deadline but not currently active). Only affects the
        HEALTHY vs. SLOW_BUT_PROGRESSING distinction — neither leads to
        cancellation, so a conservative/approximate implementation is
        safe."""
        ...


def decide(budget: ExecutionBudget, signal: ProgressSignal) -> Decision:
    """Pure detection + intra-operation recovery decision.

    No I/O, no cancellation side effects — directly unit testable without
    an event loop. See tests/test_execution_watchdog.py (the original,
    still-current unit tests for this logic) and
    tests/test_execution_inspection.py (the graph-adapter integration
    tests added alongside ADR-KERNEL-02).
    """
    if budget.is_hard_expired():
        return Decision(WatchdogVerdict.EXPIRED, True, CancelReason.HARD_DEADLINE)

    if not signal.has_progressed():
        if budget.elapsed_s() >= budget.startup_deadline_s:
            # Never produced meaningful progress within the startup window.
            # Classified as expired (not "stall") because there is nothing
            # to have stalled from yet.
            return Decision(WatchdogVerdict.EXPIRED, True, CancelReason.HARD_DEADLINE)
        return Decision(WatchdogVerdict.HEALTHY, False)

    if signal.since_last_progress_s() < budget.progress_deadline_s:
        if signal.is_actively_progressing():
            return Decision(WatchdogVerdict.HEALTHY, False)
        return Decision(WatchdogVerdict.SLOW_BUT_PROGRESSING, False)

    # Genuinely stalled by the progress-deadline measure from here down.
    if budget.in_grace_period():
        # Already extended once for this stall episode; waiting it out
        # rather than re-detecting the same stall on every poll tick.
        return Decision(WatchdogVerdict.RECOVERING, False)

    if budget.grant_extension(min(budget.progress_deadline_s, budget.remaining_extension_s)):
        return Decision(WatchdogVerdict.EXTENDED, False)

    return Decision(WatchdogVerdict.STALLED, True, CancelReason.STALL)
