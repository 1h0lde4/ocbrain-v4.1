"""Execution watchdog that observes graph progress and cancels canonically.

DEBT-016 / ADR-KERNEL-02: this watchdog used to detect a stalled node and
only ever *record* that fact (`ExecutionStatus.STALLED`), with no bounded
recovery attempt and no path to actually cancel because of a stall — it
would cancel only via the unrelated hard-ceiling check. That meant a
genuinely stuck workflow (the K4.2 default execution path, live since Aug
28, 2026) could sit "stalled" indefinitely until its full hard ceiling
elapsed, while the model-router-facing watchdog
(core/runtime/execution_watchdog.py) already granted a bounded extension
and then gave up correctly. Both watchdogs now share the exact same
decision core (core/runtime/watchdog_decision.py); this module supplies a
synchronous, per-poll-tick adapter over the graph so that shared logic can
run without changing its "pure function, no I/O" contract.

Scope note: the decision (extend vs. give up) is evaluated once per poll
tick for the execution as a whole, against the single `ExecutionBudget`
`WorkflowRuntime.execute()` already constructs for the whole workflow run
— it is not fragmented per node. Per-node `STALLED`/`RECOVERING` status
recording (for the execution-inspection UI) still happens per active node,
unchanged in spirit from before; what's new is that the underlying
decision now actually tries bounded recovery and can actually cancel.
"""

import asyncio
import time
from typing import Optional

from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_graph import ExecutionGraph, ExecutionStatus
from core.runtime.progress import ProgressMonitor
from core.runtime.watchdog_decision import CancelReason, WatchdogVerdict, decide

# The one verdict that should write a fresh graph touch: the instant an
# extension is actually granted. Writing again on every subsequent
# RECOVERING tick (still inside that same grace period) would repeatedly
# touch node.updated_at -- exactly the signal _GraphProgressSignal reads --
# letting the watchdog's own diagnostic writes perpetually look like fresh
# progress and mask a genuine stall indefinitely. One write per grant is
# enough: the persisted RECOVERING status already answers "what's going on"
# for anyone polling the graph/API in between.
_WRITES_RECOVERY_EVENT = (WatchdogVerdict.EXTENDED,)


class _GraphProgressSignal:
    """Synchronous, already-resolved ProgressSignal (see
    watchdog_decision.py) computed from one graph snapshot.

    Built fresh each poll tick from `await graph.snapshot()` so the shared
    `decide()` function can stay a plain, I/O-free, synchronously callable
    function — the async graph read happens once, here, before decide() is
    called, not inside it.

    "Progress" is aggregated across every currently-active (RUNNING) node
    via whichever was touched most recently: the workflow as a whole has
    shown a sign of life if any active node has, and the relevant
    staleness clock is however long it's been since the *most recent* of
    those updates — one node quietly finishing its step keeps the whole
    execution looking alive, which matches how a human watching the graph
    would judge it.

    Deliberately keyed on `updated_at`, not `last_progress_at`: nothing in
    production calls `ProgressMonitor.report_progress()` on this
    (graph-aware) path today — only `record_status()` /
    `record_completion()` / `record_failure()`, none of which touch
    `last_progress_at` (see core/runtime/execution_graph.py `update()`).
    Keying on `last_progress_at` here would mean `has_progressed()` is
    always False and every execution gets treated as "never progressed,"
    which `decide()` expires at `startup_deadline_s` (10s) regardless of
    whether real work is happening — a severe, silent regression this
    module's own tests (see tests/test_execution_inspection.py) exist to
    catch. `updated_at` is the correct broader "activity" signal for this
    adapter, analogous to `progress_monitor.ProgressMonitor`'s
    activity/progress distinction but drawn the other way for this domain:
    a workflow node's mere status touch is meaningful sign-of-life here,
    where a raw LLM keepalive chunk is deliberately not meaningful there.
    """

    def __init__(self, active_nodes: list[dict], wall_now: float) -> None:
        touch_times = [n["updated_at"] for n in active_nodes if n.get("updated_at")]
        self._last_touch_at: Optional[float] = max(touch_times) if touch_times else None
        self._wall_now = wall_now

    def has_progressed(self) -> bool:
        return self._last_touch_at is not None

    def since_last_progress_s(self) -> float:
        if self._last_touch_at is None:
            return 0.0
        return max(0.0, self._wall_now - self._last_touch_at)

    def is_actively_progressing(self) -> bool:
        # No sub-second "currently mid-update" signal exists at the graph
        # level (unlike progress_monitor.ProgressMonitor's PROGRESSING
        # state, which is set the instant a chunk arrives). Approximating
        # "recent enough to call it active" as "updated within the last
        # poll tick" is deliberately conservative — it only affects the
        # cosmetic HEALTHY vs. SLOW_BUT_PROGRESSING verdict, never
        # should_cancel, so imprecision here has no safety consequence.
        return self.since_last_progress_s() <= 1.5


class GraphExecutionWatchdog:
    """Supervises one ExecutionGraph (all its nodes) against one shared
    ExecutionBudget for the lifetime of one workflow execution.

    Renamed from `ExecutionWatchdog` (DEBT-016 / ADR-KERNEL-02): the
    model-router-facing watchdog (core/runtime/execution_watchdog.py) also
    defines a class literally named `ExecutionWatchdog`. The two were never
    import-ambiguous (different modules), but the identical name was
    exactly the kind of "duplicated authority, easy to confuse" pattern
    DEBT-016 called out. This is the only production/test call site
    (core/workflow/runtime.py, tests/test_execution_inspection.py); no
    compatibility alias is needed.
    """

    def __init__(self, graph: ExecutionGraph, budget: ExecutionBudget,
                 cancellation_token: CancellationToken,
                 monitor: ProgressMonitor, *, interval_seconds: float = 1.0) -> None:
        self.graph = graph
        self.budget = budget
        self.cancellation_token = cancellation_token
        self.monitor = monitor
        self.interval_seconds = max(0.05, interval_seconds)
        self._task: Optional[asyncio.Task] = None
        self.last_verdict: WatchdogVerdict = WatchdogVerdict.HEALTHY

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def inspect(self, now: Optional[float] = None) -> str:
        """Inspect the graph once; useful for tests and manual polling.

        `now` overrides the progress-staleness check below (wall-clock node
        timestamps). It does not override the hard-deadline check: the real
        ExecutionBudget (core/runtime/execution_budget.py, K4.4) measures
        elapsed time from its own `created_at` via time.monotonic() and has
        no fake-time injection hook.

        Returns the verdict's string value (e.g. "healthy", "stalled",
        "expired", "recovering", "extended") for backward-compatible
        callers/tests that check the returned string; `self.last_verdict`
        carries the typed `WatchdogVerdict` for new callers.
        """
        snapshot = await self.graph.snapshot()
        wall_now = time.time() if now is None else now
        # RUNNING and RECOVERING both count as "in flight" for watchdog
        # purposes: RECOVERING is the status this watchdog itself applies
        # (via record_recovery(), below) to a node currently riding out a
        # granted extension. Excluding it here would make a node invisible
        # to the very next poll tick right when it most needs continued
        # tracking -- found via test_watchdog_extends_then_eventually_
        # cancels_with_stall_reason during this change. WAITING/BLOCKED are
        # deliberately excluded: those are external, governance-held states
        # (e.g. awaiting human approval), not something this watchdog's
        # stall clock should race against.
        active = [node for node in snapshot["nodes"]
                  if node["status"] in (ExecutionStatus.RUNNING.value,
                                         ExecutionStatus.RECOVERING.value)]

        if not active:
            # Nothing running right now -- between nodes, or before the
            # first one has started. There is no "stall" to detect and no
            # startup window to police here (that concern belongs to the
            # node that's about to start, not this gap); only the
            # unconditional hard-deadline still applies.
            if self.budget.is_hard_expired():
                self.last_verdict = WatchdogVerdict.EXPIRED
                self.cancellation_token.cancel(f"execution {CancelReason.HARD_DEADLINE.value}")
                return "expired"
            self.last_verdict = WatchdogVerdict.HEALTHY
            return "idle"

        signal = _GraphProgressSignal(active, wall_now)
        decision = decide(self.budget, signal)
        self.last_verdict = decision.verdict

        if decision.should_cancel:
            reason = (decision.cancel_reason or CancelReason.HARD_DEADLINE).value
            for node in active:
                await self.monitor.record_failure(
                    node["node_id"], error=f"Execution cancelled: {reason}",
                    failure_type=reason,
                )
            self.cancellation_token.cancel(f"execution {reason}")
        elif decision.verdict in _WRITES_RECOVERY_EVENT:
            for node in active:
                await self.monitor.record_recovery(node["node_id"], action=decision.verdict.value)

        return decision.verdict.value

    async def _run(self) -> None:
        while not self.cancellation_token.is_cancelled:
            await asyncio.sleep(self.interval_seconds)
            state = await self.inspect()
            if state in (WatchdogVerdict.EXPIRED.value, WatchdogVerdict.STALLED.value):
                break