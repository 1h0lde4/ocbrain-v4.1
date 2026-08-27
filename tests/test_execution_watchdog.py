import asyncio

import pytest

from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_watchdog import (
    CancelReason,
    ExecutionWatchdog,
    WatchdogVerdict,
    _decide,
)
from core.runtime.progress_monitor import ProgressMonitor


def _budget(startup=1.0, progress=1.0, hard=1.0, absolute=10.0, max_ext=0.0) -> ExecutionBudget:
    return ExecutionBudget(
        startup_deadline_s=startup,
        progress_deadline_s=progress,
        hard_ceiling_s=hard,
        absolute_ceiling_s=absolute,
        max_extension_s=max_ext,
    )


# ── _decide() — pure function, no event loop needed ─────────────────────────


def test_decide_healthy_when_recently_progressing():
    budget = _budget(startup=1.0, progress=5.0, hard=10.0)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()
    decision = _decide(budget, monitor)
    assert decision.verdict == WatchdogVerdict.HEALTHY
    assert not decision.should_cancel


def test_decide_healthy_before_startup_deadline_with_no_progress_yet():
    budget = _budget(startup=5.0, progress=5.0, hard=10.0)
    monitor = ProgressMonitor()
    monitor.start()
    decision = _decide(budget, monitor)
    assert decision.verdict == WatchdogVerdict.HEALTHY
    assert not decision.should_cancel


def test_decide_expires_when_never_progressed_past_startup_deadline():
    import time
    budget = _budget(startup=0.05, progress=5.0, hard=10.0)
    monitor = ProgressMonitor()
    monitor.start()
    time.sleep(0.08)
    decision = _decide(budget, monitor)
    assert decision.verdict == WatchdogVerdict.EXPIRED
    assert decision.should_cancel
    assert decision.cancel_reason == CancelReason.HARD_DEADLINE


def test_decide_hard_expired_overrides_everything_else():
    import time
    budget = _budget(startup=1.0, progress=1.0, hard=0.05, absolute=10.0, max_ext=5.0)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()  # actively progressing...
    time.sleep(0.08)  # ...but the hard ceiling still wins
    decision = _decide(budget, monitor)
    assert decision.verdict == WatchdogVerdict.EXPIRED
    assert decision.cancel_reason == CancelReason.HARD_DEADLINE


def test_decide_grants_one_extension_on_stall_then_recovers_quietly():
    import time
    budget = _budget(startup=1.0, progress=0.05, hard=1.0, absolute=10.0, max_ext=1.0)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()
    time.sleep(0.08)  # now stalled by the progress-deadline measure

    first = _decide(budget, monitor)
    assert first.verdict == WatchdogVerdict.EXTENDED
    assert not first.should_cancel
    assert budget.hard_ceiling_s > 1.0  # ceiling was pushed out

    # Immediately re-checking must NOT grant a second extension or cancel --
    # it should quietly wait out the grace period.
    second = _decide(budget, monitor)
    assert second.verdict == WatchdogVerdict.RECOVERING
    assert not second.should_cancel


def test_decide_cancels_with_stall_reason_once_grace_and_extension_exhausted():
    import time
    budget = _budget(startup=1.0, progress=0.03, hard=1.0, absolute=10.0, max_ext=0.03)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()
    time.sleep(0.05)  # stalled

    first = _decide(budget, monitor)
    assert first.verdict == WatchdogVerdict.EXTENDED

    time.sleep(0.06)  # grace period (≈0.03s) has now also elapsed, still no progress
    second = _decide(budget, monitor)
    assert second.verdict == WatchdogVerdict.STALLED
    assert second.should_cancel
    assert second.cancel_reason == CancelReason.STALL


def test_decide_progress_during_grace_returns_to_healthy():
    import time
    budget = _budget(startup=1.0, progress=0.05, hard=2.0, absolute=10.0, max_ext=1.0)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()
    time.sleep(0.08)
    extended = _decide(budget, monitor)
    assert extended.verdict == WatchdogVerdict.EXTENDED

    monitor.report_progress()  # provider resumed
    decision = _decide(budget, monitor)
    assert decision.verdict == WatchdogVerdict.HEALTHY
    assert not decision.should_cancel


def test_decide_no_extension_configured_cancels_immediately_on_stall():
    import time
    budget = _budget(startup=1.0, progress=0.03, hard=5.0, absolute=5.0, max_ext=0.0)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()
    time.sleep(0.05)
    decision = _decide(budget, monitor)
    assert decision.verdict == WatchdogVerdict.STALLED
    assert decision.cancel_reason == CancelReason.STALL


# ── ExecutionWatchdog.run() — full async loop ───────────────────────────────


@pytest.mark.asyncio
async def test_watchdog_stops_cleanly_when_work_finishes_first():
    budget = _budget(startup=1.0, progress=5.0, hard=10.0)
    monitor = ProgressMonitor()
    monitor.start()
    token = CancellationToken()
    watchdog = ExecutionWatchdog(budget, monitor, token)

    task = asyncio.create_task(watchdog.run())
    await asyncio.sleep(0.02)
    watchdog.stop()
    verdict = await task

    assert verdict == WatchdogVerdict.HEALTHY
    assert not token.is_cancelled


@pytest.mark.asyncio
async def test_watchdog_cancels_token_on_hard_deadline():
    budget = _budget(startup=0.05, progress=0.05, hard=0.05, absolute=0.05)
    monitor = ProgressMonitor()
    monitor.start()
    token = CancellationToken()
    watchdog = ExecutionWatchdog(budget, monitor, token)

    verdict = await watchdog.run()

    assert verdict == WatchdogVerdict.EXPIRED
    assert token.is_cancelled
    assert token.reason == CancelReason.HARD_DEADLINE.value


@pytest.mark.asyncio
async def test_watchdog_survives_periodic_progress_without_cancelling():
    budget = _budget(startup=0.05, progress=0.1, hard=1.0, absolute=1.0)
    monitor = ProgressMonitor()
    monitor.start()
    token = CancellationToken()
    watchdog = ExecutionWatchdog(budget, monitor, token)

    async def feed_progress():
        for _ in range(5):
            await asyncio.sleep(0.04)
            monitor.report_progress()

    task = asyncio.create_task(watchdog.run())
    await feed_progress()
    watchdog.stop()
    verdict = await task

    assert not token.is_cancelled
    assert verdict in (WatchdogVerdict.HEALTHY, WatchdogVerdict.SLOW_BUT_PROGRESSING)


@pytest.mark.asyncio
async def test_watchdog_notices_external_cancellation_promptly():
    budget = _budget(startup=5.0, progress=5.0, hard=5.0, absolute=5.0)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()
    token = CancellationToken()
    watchdog = ExecutionWatchdog(budget, monitor, token)

    task = asyncio.create_task(watchdog.run())
    await asyncio.sleep(0.02)
    token.cancel(reason="external_test_reason")
    verdict = await asyncio.wait_for(task, timeout=_poll_cap_plus_margin())

    assert verdict == WatchdogVerdict.CANCELLED
    assert token.reason == "external_test_reason"  # watchdog must not overwrite an external reason


def _poll_cap_plus_margin() -> float:
    from core.runtime.execution_watchdog import _POLL_INTERVAL_CAP_S
    return _POLL_INTERVAL_CAP_S + 1.0


@pytest.mark.asyncio
async def test_watchdog_extends_then_eventually_cancels_with_stall_reason():
    budget = _budget(startup=1.0, progress=0.05, hard=2.0, absolute=2.0, max_ext=0.05)
    monitor = ProgressMonitor()
    monitor.start()
    monitor.report_progress()
    token = CancellationToken()
    watchdog = ExecutionWatchdog(budget, monitor, token)

    verdict = await watchdog.run()

    assert verdict == WatchdogVerdict.STALLED
    assert token.reason == CancelReason.STALL.value
