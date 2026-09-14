"""
core/runtime/execution_watchdog.py — ExecutionWatchdog (K4.4)

An intelligent *source* of cancellation, not a second enforcement mechanism.

Per KERNEL_ARCHITECTURE_v1.0.md §7.4: "Timeouts are cancellations triggered
by timers — no separate mechanism." ExecutionWatchdog's only terminal action
is calling the existing, unmodified CancellationToken.cancel(reason) — it
never kills a process, throws across the stack, or maintains a second
cancellation object. core/runtime/cancellation.py is not touched by this
change.

Recovery-invariant compliance (ADR-K4.2-H-05)
----------------------------------------------
`OperationRecoveryBudget` (core/cognitive/recovery.py) is the sole
operation-level autonomous-recovery budget, per the frozen Recovery
Invariant: "one recovery budget per operation... no component may create an
independent recovery budget... no hidden retry universe."

The bounded extension this watchdog grants on a detected stall is NOT a
recovery attempt in that sense — it never re-enters the Planner, never
triggers Supervisor re-entry, and never creates a new operation. It is
strictly intra-operation: the same execution attempt is allowed more wall
clock, once, bounded by ExecutionBudget.max_extension_s, which is itself
bounded by ExecutionBudget.absolute_ceiling_s. Nothing here reads or writes
OperationRecoveryBudget. Cross-operation recovery (replan) is explicitly out
of scope for this module — see the implementation report.

Detection vs. policy vs. enforcement
-------------------------------------
    Watchdog        -> condition detected  (this module, _decide())
    RecoveryPolicy  -> action selected     (this module, _decide() — see
                                             note below)
    CancellationToken -> action executed   (core/runtime/cancellation.py,
                                             unmodified)

For v1, the recovery *decision* (extend vs. cancel) is a small, pure,
directly-unit-testable function (`_decide`) inside this module rather than a
separate RecoveryPolicy module. This is a deliberate v1 simplification
(intra-operation recovery is simple enough not to warrant its own module
yet), disclosed here rather than silently done — see implementation report
"Remaining debt."
"""

from __future__ import annotations

import asyncio
import logging

from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.progress_monitor import ProgressMonitor
from core.runtime.watchdog_decision import (
    CancelReason,
    Decision as _Decision,
    WatchdogVerdict,
    decide as _decide,
)

logger = logging.getLogger("ocbrain.runtime.watchdog")

# Never sleep longer than this between checks, so externally-triggered
# cancellation (token.cancel() called by something else entirely) is
# noticed promptly even mid-wait. This is a responsiveness cap, not a
# busy-poll interval — the loop still sleeps via asyncio.wait_for, not a
# tight spin.
_POLL_INTERVAL_CAP_S = 2.0

# NOTE (DEBT-016 / ADR-KERNEL-02): CancelReason, WatchdogVerdict, _Decision,
# and _decide used to be defined here. They now live in
# core/runtime/watchdog_decision.py, shared with the graph-aware watchdog
# (core/runtime/watchdog.py), and are re-imported above under their
# original names so every existing caller of this module — including
# tests/test_execution_watchdog.py's `from core.runtime.execution_watchdog
# import (CancelReason, ExecutionWatchdog, WatchdogVerdict, _decide)` —
# keeps working completely unchanged. _Decision was never imported
# elsewhere by name (only used structurally), so the alias exists purely
# for symmetry/documentation, not because anything requires it.


class ExecutionWatchdog:
    """Supervises one ExecutionBudget + ProgressMonitor pair for the
    lifetime of one execution attempt.

    Usage:
        watchdog = ExecutionWatchdog(budget, monitor, context.cancellation_token)
        task = asyncio.create_task(watchdog.run())
        ...  # do the actual work; call monitor.report_progress() as it happens
        watchdog.stop()
        await task
    """

    def __init__(
        self,
        budget: ExecutionBudget,
        monitor: ProgressMonitor,
        cancellation_token: CancellationToken,
    ) -> None:
        self._budget = budget
        self._monitor = monitor
        self._token = cancellation_token
        self._stopped = asyncio.Event()
        self.last_verdict: WatchdogVerdict = WatchdogVerdict.HEALTHY

    def stop(self) -> None:
        """Signal the watchdog loop to exit — called once the supervised
        work finishes normally, so the watchdog doesn't outlive it."""
        self._stopped.set()

    async def run(self) -> WatchdogVerdict:
        """Async supervision loop.

        Sleeps until the next relevant deadline rather than busy-polling
        (spec: "the watchdog should sleep until the next relevant deadline
        where practical"). Each wake-up is a cheap, synchronous decision —
        no I/O, no database writes, per token or otherwise.
        """
        while not self._stopped.is_set():
            if self._token.is_cancelled:
                self.last_verdict = WatchdogVerdict.CANCELLED
                return self.last_verdict

            decision = _decide(self._budget, self._monitor)
            self.last_verdict = decision.verdict

            if decision.should_cancel:
                logger.info(
                    "execution.watchdog.cancel verdict=%s reason=%s elapsed=%.1fs",
                    decision.verdict.value,
                    decision.cancel_reason.value if decision.cancel_reason else None,
                    self._budget.elapsed_s(),
                )
                self._token.cancel(reason=decision.cancel_reason.value)
                return self.last_verdict

            if decision.verdict == WatchdogVerdict.EXTENDED:
                logger.info(
                    "execution.watchdog.extended elapsed=%.1fs new_ceiling=%.1fs remaining_extension=%.1fs",
                    self._budget.elapsed_s(),
                    self._budget.hard_ceiling_s,
                    self._budget.remaining_extension_s,
                )

            remaining_hard = max(0.0, self._budget.hard_ceiling_s - self._budget.elapsed_s())
            if monitor_progressed := self._monitor.has_progressed():
                remaining_progress = max(
                    0.0, self._budget.progress_deadline_s - self._monitor.since_last_progress_s()
                )
            else:
                remaining_progress = max(
                    0.0, self._budget.startup_deadline_s - self._budget.elapsed_s()
                )
            sleep_s = max(0.05, min(_POLL_INTERVAL_CAP_S, remaining_hard, remaining_progress))

            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=sleep_s)
            except asyncio.TimeoutError:
                pass  # normal wake-up to re-check, not an error

        self.last_verdict = WatchdogVerdict.HEALTHY
        return self.last_verdict
