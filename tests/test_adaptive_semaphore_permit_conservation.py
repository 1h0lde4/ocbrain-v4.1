"""FZ-04 -- AdaptiveSemaphore permit conservation.

Defect (Kernel v1.0 freeze audit, FZ-04): ``AdaptiveSemaphore`` kept its
"am I holding a permit" flag and start time on the shared instance, so with two
or more concurrent holders the first exit cleared the flag and every later exit
returned WITHOUT releasing its permit. A single burst permanently removed
capacity (reported limit 10, usable permits 1) and no existing test noticed,
because every existing test used serial holders.

Invariant under test (when idle, i.e. no live holders):

    available == current_limit + drain_count

and, always, ``available + held == current_limit + drain_count`` (checked via
``snapshot()`` where no waiter is mid-handoff).

Layout
------
``TestPermitConservation`` uses only the pre-fix public surface plus two private
attributes (``_semaphore._value``, ``_drain_count``) so it can be run against the
unfixed implementation to show it fails there.
``TestPerAcquisitionAccounting`` covers behavior that needs the fix's additions
(injectable clock, ``snapshot()``, per-task holds).

Determinism: no wall-clock sleeps decide outcomes. Ordering is driven by events
and ``asyncio.sleep(0)`` spins; timeouts only ever fire on coroutines that can
never complete on their own.
"""
import asyncio
import logging
import random

import pytest

from core.runtime import limits as limits_mod
from core.runtime.resilience import AdaptiveSemaphore


# --------------------------------------------------------------------------- helpers

def _acct(sem):
    """(current_limit, available, drain_count) -- valid on pre-fix and fixed code."""
    return sem.current_limit, sem._semaphore._value, sem._drain_count


def _assert_idle_conserved(sem, where=""):
    limit, avail, drain = _acct(sem)
    assert avail == limit + drain, (
        f"permit loss{' ' + where if where else ''}: current_limit={limit} "
        f"available={avail} drain_count={drain} lost={limit + drain - avail}"
    )


def _fixed(n):
    """Limit pinned at n (min == max): isolates conservation from adaptation."""
    return AdaptiveSemaphore(min_limit=n, max_limit=n, target_latency_ms=5000)


def _growing(max_limit=10):
    """Always-grow policy (target latency effectively infinite)."""
    return AdaptiveSemaphore(min_limit=1, max_limit=max_limit, target_latency_ms=1e9)


async def _until(pred, *, what, spins=1000):
    for _ in range(spins):
        if pred():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"never reached: {what}")


class _Meter:
    def __init__(self):
        self.inside = 0
        self.peak = 0

    def enter(self):
        self.inside += 1
        self.peak = max(self.peak, self.inside)

    def leave(self):
        self.inside -= 1


async def _assert_can_fill(sem, n):
    """n holders must be able to be inside simultaneously (effective capacity >= n)."""
    release = asyncio.Event()
    meter = _Meter()

    async def holder():
        async with sem:
            meter.enter()
            try:
                await release.wait()
            finally:
                meter.leave()

    tasks = [asyncio.create_task(holder()) for _ in range(n)]
    try:
        await _until(lambda: meter.inside == n,
                     what=f"{n} concurrent holders (usable capacity), got {meter.inside}")
    except BaseException:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    release.set()
    await asyncio.gather(*tasks)
    return meter.peak


class _Boom(Exception):
    pass


# --------------------------------------------------------------------------- core

class TestPermitConservation:

    async def test_two_concurrent_holders_both_return_their_permit(self):
        """The audited race, deterministically: A and B inside together, A exits, B exits."""
        sem = _fixed(2)
        meter = _Meter()
        go = asyncio.Event()

        async def holder():
            async with sem:
                meter.enter()
                try:
                    await go.wait()
                finally:
                    meter.leave()

        a, b = asyncio.create_task(holder()), asyncio.create_task(holder())
        await _until(lambda: meter.inside == 2, what="both holders inside")
        assert meter.peak == 2, "test harness must exercise genuinely concurrent holders"
        go.set()
        await asyncio.gather(a, b)

        _assert_idle_conserved(sem)
        assert _acct(sem)[1] == 2
        await _assert_can_fill(sem, 2)

    async def test_burst_then_idle_conserves_permits_repeatedly(self):
        """Original audit repro: warm up serially, then repeated 6-way bursts."""
        sem = _growing(10)
        for _ in range(5):
            async with sem:
                await asyncio.sleep(0)
        _assert_idle_conserved(sem, "after serial warm-up")

        for cycle in range(1, 6):
            async def w():
                async with sem:
                    await asyncio.sleep(0)
            await asyncio.gather(*(w() for _ in range(6)))
            _assert_idle_conserved(sem, f"after burst {cycle}")

    async def test_effective_capacity_matches_reported_limit_after_bursts(self):
        """Reported limit must equal what can actually run at once (audit: 10 vs 1)."""
        sem = _growing(10)
        for _ in range(5):
            async with sem:
                await asyncio.sleep(0)
        for _ in range(5):
            async def w():
                async with sem:
                    await asyncio.sleep(0)
            await asyncio.gather(*(w() for _ in range(10)))
            peak = await _assert_can_fill(sem, sem.current_limit)
            assert peak == sem.current_limit

    async def test_exhaustion_and_recovery_cycles(self):
        sem = _fixed(3)
        for cycle in range(5):
            release = asyncio.Event()
            meter = _Meter()

            async def holder():
                async with sem:
                    meter.enter()
                    try:
                        await release.wait()
                    finally:
                        meter.leave()

            holders = [asyncio.create_task(holder()) for _ in range(3)]
            await _until(lambda: meter.inside == 3, what=f"cycle {cycle}: capacity exhausted")
            extra = asyncio.create_task(holder())          # 4th: must wait
            for _ in range(20):
                await asyncio.sleep(0)
            assert meter.inside == 3 and not extra.done(), "4th holder must be blocked while exhausted"
            release.set()
            await asyncio.wait_for(asyncio.gather(*holders, extra), timeout=5)
            _assert_idle_conserved(sem, f"after exhaustion cycle {cycle}")
            assert meter.peak == 3

    async def test_cancellation_while_waiting_does_not_leak(self):
        sem = _fixed(1)
        release = asyncio.Event()
        holder_in = asyncio.Event()

        async def holder():
            async with sem:
                holder_in.set()
                await release.wait()

        async def waiter():
            async with sem:
                pass

        h = asyncio.create_task(holder())
        await holder_in.wait()
        waiters = [asyncio.create_task(waiter()) for _ in range(3)]
        for _ in range(10):
            await asyncio.sleep(0)
        for w in waiters:
            w.cancel()
        await asyncio.gather(*waiters, return_exceptions=True)
        assert all(w.cancelled() for w in waiters)

        release.set()
        await h
        _assert_idle_conserved(sem)
        await _assert_can_fill(sem, 1)

    async def test_cancellation_after_acquisition_returns_permit(self):
        sem = _fixed(3)
        meter = _Meter()
        never = asyncio.Event()

        async def holder():
            async with sem:
                meter.enter()
                try:
                    await never.wait()
                finally:
                    meter.leave()

        tasks = [asyncio.create_task(holder()) for _ in range(3)]
        await _until(lambda: meter.inside == 3, what="3 holders inside")
        for t in tasks:
            t.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(r, asyncio.CancelledError) for r in results)
        _assert_idle_conserved(sem)
        await _assert_can_fill(sem, 3)

    async def test_timeout_while_waiting_does_not_leak(self):
        sem = _fixed(1)
        release = asyncio.Event()
        holder_in = asyncio.Event()

        async def holder():
            async with sem:
                holder_in.set()
                await release.wait()

        async def timed_waiter():
            async with sem:
                pass

        h = asyncio.create_task(holder())
        await holder_in.wait()
        for _ in range(3):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(timed_waiter(), timeout=0.01)
        release.set()
        await h
        _assert_idle_conserved(sem)
        await _assert_can_fill(sem, 1)

    async def test_timeout_while_holding_returns_permit(self):
        sem = _fixed(2)
        never = asyncio.Event()

        async def stuck():
            async with sem:
                await never.wait()

        for _ in range(3):
            results = await asyncio.gather(
                asyncio.wait_for(stuck(), timeout=0.01),
                asyncio.wait_for(stuck(), timeout=0.01),
                return_exceptions=True,
            )
            assert all(isinstance(r, asyncio.TimeoutError) for r in results)
            _assert_idle_conserved(sem)
        await _assert_can_fill(sem, 2)

    async def test_exception_while_holding_propagates_and_returns_permit(self):
        sem = _fixed(2)
        with pytest.raises(ValueError, match="boom"):
            async with sem:
                raise ValueError("boom")                     # must not be suppressed
        _assert_idle_conserved(sem)

        async def failing():
            async with sem:
                await asyncio.sleep(0)
                raise _Boom()

        async def succeeding():
            async with sem:
                await asyncio.sleep(0)
                return "ok"

        results = await asyncio.gather(
            *(failing() if i % 2 else succeeding() for i in range(8)),
            return_exceptions=True,
        )
        assert [type(r) for r in results[1::2]] == [_Boom] * 4
        assert results[0::2] == ["ok"] * 4
        _assert_idle_conserved(sem)
        await _assert_can_fill(sem, 2)

    @pytest.mark.parametrize("make", [lambda: _fixed(4), lambda: _growing(8)],
                             ids=["fixed4", "growing8"])
    async def test_repeated_mixed_outcome_cycles_conserve_permits(self, make):
        """40 seeded cycles of concurrent ok / raise / cancel / timeout holders."""
        sem = make()
        rng = random.Random(0xF204)
        for cycle in range(40):
            kinds = [rng.choice(["ok", "raise", "cancel", "timeout"])
                     for _ in range(rng.randint(3, 12))]
            park = asyncio.Event()                           # never set

            async def one(kind):
                if kind == "ok":
                    async with sem:
                        await asyncio.sleep(0)
                elif kind == "raise":
                    async with sem:
                        await asyncio.sleep(0)
                        raise _Boom()
                elif kind == "cancel":
                    async with sem:
                        await park.wait()
                else:
                    async def inner():
                        async with sem:
                            await park.wait()
                    await asyncio.wait_for(inner(), timeout=0.005)

            tasks = [asyncio.create_task(one(k)) for k in kinds]
            for _ in range(10):
                await asyncio.sleep(0)
            for t, k in zip(tasks, kinds):
                if k == "cancel":
                    t.cancel()
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=10)

            expected = {"ok": type(None), "raise": _Boom,
                        "cancel": asyncio.CancelledError, "timeout": asyncio.TimeoutError}
            for k, r in zip(kinds, results):
                assert isinstance(r, expected[k]), f"cycle {cycle}: {k} -> {r!r}"
            _assert_idle_conserved(sem, f"after mixed cycle {cycle} ({kinds})")

        # recovery: after all that abuse the semaphore must still serve its full reported limit
        for _ in range(12):
            async with sem:
                await asyncio.sleep(0)
        _assert_idle_conserved(sem, "after recovery calls")
        await _assert_can_fill(sem, sem.current_limit)

    async def test_safe_llm_call_burst_conserves_the_global_limiter(self, monkeypatch):
        """Production caller (core/runtime/limits.py::safe_llm_call) with the production
        limiter parameters: bursts, provider failures and cancelled in-flight calls."""
        sem = AdaptiveSemaphore(min_limit=2, max_limit=12, target_latency_ms=8000)
        monkeypatch.setattr(limits_mod, "ADAPTIVE_LLM_LIMIT", sem)

        async def ok():
            await asyncio.sleep(0)
            return "x"

        async def bad():
            await asyncio.sleep(0)
            raise RuntimeError("provider down")

        never = asyncio.Event()

        async def hang():
            await never.wait()

        for cycle in range(5):
            hung = [asyncio.create_task(limits_mod.safe_llm_call(hang)) for _ in range(2)]
            calls = ([limits_mod.safe_llm_call(ok) for _ in range(12)]
                     + [limits_mod.safe_llm_call(bad) for _ in range(4)])
            gathered = asyncio.gather(*calls, return_exceptions=True)
            for _ in range(10):
                await asyncio.sleep(0)
            for t in hung:
                t.cancel()
            results = await asyncio.wait_for(gathered, timeout=10)
            await asyncio.gather(*hung, return_exceptions=True)
            assert results[:12] == ["x"] * 12
            assert all(isinstance(r, RuntimeError) for r in results[12:])
            _assert_idle_conserved(sem, f"after safe_llm_call cycle {cycle}")
        await _assert_can_fill(sem, sem.current_limit)


# --------------------------------------------------------------------------- needs the fix's additions

class _FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestPerAcquisitionAccounting:

    async def test_each_holder_is_timed_from_its_own_acquisition(self):
        """Pre-fix, latency came from whichever holder wrote the shared start time last."""
        clock = _FakeClock()
        sem = AdaptiveSemaphore(min_limit=2, max_limit=2, target_latency_ms=1000, clock=clock)
        a_release, b_release = asyncio.Event(), asyncio.Event()
        a_in, b_in = asyncio.Event(), asyncio.Event()

        async def a():
            async with sem:
                a_in.set()
                await a_release.wait()

        async def b():
            async with sem:
                b_in.set()
                await b_release.wait()

        ta = asyncio.create_task(a())
        await a_in.wait()                       # A acquired at t=0
        clock.now = 5.0
        tb = asyncio.create_task(b())
        await b_in.wait()                       # B acquired at t=5
        clock.now = 10.0
        a_release.set()
        await ta                                # A latency = 10 (not 5)
        b_release.set()
        await tb                                # B latency = 5

        expected = 1.0                          # EMA seed = target (1.0 s), alpha = 0.4
        for lat in (10.0, 5.0):
            expected = 0.4 * lat + 0.6 * expected
        assert sem._avg_latency == pytest.approx(expected)
        _assert_idle_conserved(sem)

    async def test_snapshot_accounts_for_live_holders(self):
        sem = _fixed(3)
        release = asyncio.Event()
        meter = _Meter()

        async def holder():
            async with sem:
                meter.enter()
                await release.wait()

        tasks = [asyncio.create_task(holder()) for _ in range(2)]
        await _until(lambda: meter.inside == 2, what="2 holders inside")
        s = sem.snapshot()
        assert s == {"current_limit": 3, "available": 1, "held": 2, "drain_count": 0}
        assert s["available"] + s["held"] == s["current_limit"] + s["drain_count"]
        release.set()
        await asyncio.gather(*tasks)
        s = sem.snapshot()
        assert s["held"] == 0 and s["available"] == s["current_limit"] + s["drain_count"]
        assert sem._holds == {}, "no per-task hold records may outlive their holders"

    async def test_nested_acquisition_in_one_task_is_lifo(self):
        sem = _fixed(2)
        async with sem:
            async with sem:
                assert sem.snapshot()["held"] == 2
                assert sem.snapshot()["available"] == 0
            assert sem.snapshot()["held"] == 1
        assert sem.snapshot() == {"current_limit": 2, "available": 2, "held": 0, "drain_count": 0}

    async def test_nested_holds_are_timed_and_released_in_lifo_order(self):
        """Inner exit must consume the inner hold (latency 7), outer the outer hold (10)."""
        clock = _FakeClock()
        sem = AdaptiveSemaphore(min_limit=2, max_limit=2, target_latency_ms=1000, clock=clock)
        async with sem:                          # outer acquired at t=0
            clock.now = 3.0
            async with sem:                      # inner acquired at t=3
                clock.now = 10.0
        expected = 1.0                           # EMA seed = target, alpha = 0.4
        for lat in (7.0, 10.0):                  # inner exits first, then outer
            expected = 0.4 * lat + 0.6 * expected
        assert sem._avg_latency == pytest.approx(expected)
        _assert_idle_conserved(sem)

    async def test_growth_satisfies_pending_drain_before_releasing(self):
        """Pins the pre-existing adaptive policy (not part of the FZ-04 invariant, which a
        policy deviation here would still satisfy): when the limit grows while shrink
        permits are still pending, the growth cancels pending drain instead of releasing.
        Pending drain only exceeds 1 when a shrink step is >= 2, i.e. limits >= 20."""
        clock = _FakeClock()
        sem = AdaptiveSemaphore(min_limit=1, max_limit=40, target_latency_ms=1000, clock=clock)
        for _ in range(39):                      # warm up to 40 (latency 0)
            async with sem:
                pass
        assert sem.current_limit == 40
        for _ in range(3):                       # slow serial calls: shrink steps of 4, drain builds
            async with sem:
                clock.now += 100.0
        assert sem._drain_count >= 2
        _assert_idle_conserved(sem, "after slow phase")

        checked = False
        for _ in range(100):                     # fast serial calls until the first growth step
            limit0, avail0, drain0 = _acct(sem)
            async with sem:
                pass
            limit1, avail1, drain1 = _acct(sem)
            _assert_idle_conserved(sem, "during recovery")
            if limit1 > limit0 and drain0 >= 2:
                # avail0 was read before this holder took its permit. The exit absorbed that
                # permit (drain0 - 1) instead of returning it, then growth cancelled one more
                # pending drain instead of releasing a new permit:
                # drain drops by 2, available is down by exactly the absorbed permit.
                assert drain1 == drain0 - 2 and avail1 == avail0 - 1, (
                    f"growth released instead of cancelling pending drain: "
                    f"drain {drain0}->{drain1}, available {avail0}->{avail1}")
                checked = True
                break
        assert checked, "scenario never reached a growth step with >= 2 pending drain"

    async def test_aexit_never_suspends(self):
        """Release/adapt runs atomically on the loop: it must contain no suspension point,
        so it cannot be interleaved with or cancelled part-way through another release."""
        sem = _fixed(2)
        await sem.__aenter__()
        coro = sem.__aexit__(None, None, None)
        try:
            with pytest.raises(StopIteration):
                coro.send(None)                 # a suspension would return a future instead
        finally:
            coro.close()
        assert sem.snapshot()["held"] == 0
        _assert_idle_conserved(sem)

    async def test_exit_without_matching_hold_is_reported_and_releases_nothing(self, caplog):
        sem = _fixed(1)
        await sem.__aenter__()
        before = sem.snapshot()

        async def other_task_exit():
            await sem.__aexit__(None, None, None)

        with caplog.at_level(logging.ERROR, logger="ocbrain.runtime.resilience"):
            await asyncio.create_task(other_task_exit())
        assert "no matching hold" in caplog.text
        assert sem.snapshot() == before, "an unmatched exit must not over-release"

        await sem.__aexit__(None, None, None)   # the owning task exits normally
        _assert_idle_conserved(sem)

    async def test_shrink_drain_conserves_permits_and_capacity_recovers(self):
        """Deterministic adaptation under concurrent holders: slow phase shrinks (drain
        scheduled), fast phase grows back; accounting holds at every idle point."""
        clock = _FakeClock()
        sem = AdaptiveSemaphore(min_limit=1, max_limit=8, target_latency_ms=1000, clock=clock)

        for _ in range(7):                       # warm up to the max (latency 0)
            async with sem:
                pass
        assert sem.current_limit == 8
        _assert_idle_conserved(sem, "after warm-up")

        for cycle in range(3):                   # slow phase: 8 concurrent holders, 100 s each
            release = asyncio.Event()
            meter = _Meter()

            async def holder():
                async with sem:
                    meter.enter()
                    await release.wait()

            limit_at_start = sem.current_limit
            tasks = [asyncio.create_task(holder()) for _ in range(limit_at_start)]
            await _until(lambda: meter.inside == limit_at_start, what="slow-phase holders inside")
            clock.now += 100.0
            release.set()
            await asyncio.gather(*tasks)
            _assert_idle_conserved(sem, f"after slow cycle {cycle}")
        assert sem.current_limit < 8, "slow phase must have shrunk the limit"

        async def quick():
            async with sem:
                pass

        for cycle in range(60):                  # fast phase: EMA decays, limit grows back
            await asyncio.gather(*(quick() for _ in range(8)))
            _assert_idle_conserved(sem, f"after recovery cycle {cycle}")
            if sem.current_limit == 8 and sem._drain_count == 0:
                break
        assert (sem.current_limit, sem._drain_count) == (8, 0), "capacity did not recover to max"
        assert sem.snapshot()["available"] == 8
        await _assert_can_fill(sem, 8)

    async def test_snapshot_reads_one_low_while_a_release_is_handed_to_a_parked_waiter(self):
        """Pins the one documented window in which ``available + held`` under-reads.

        ``asyncio.Semaphore.release()`` hands the permit straight to a parked waiter
        (``_value`` is decremented at once), but that waiter records its hold only
        when it next runs.  Between the two the permit is in neither ``available`` nor
        ``held``.  Nothing is lost: it is counted again as soon as the waiter resumes
        and every idle point is exact.  (Reproduced from the Graphify advisory on
        PR #51; identical on CPython 3.11, 3.12 and 3.13.)
        """
        sem = _fixed(1)
        a_inside, release_a = asyncio.Event(), asyncio.Event()
        seen = {}

        async def a():
            async with sem:
                a_inside.set()
                await release_a.wait()
            # A's __aexit__ ran without suspending: B owns the permit but has not run yet.
            seen["handoff"] = sem.snapshot()
            await _until(lambda: sem.snapshot()["held"] == 1, what="B resumed and recorded its hold")
            seen["resumed"] = sem.snapshot()

        async def b():
            async with sem:
                await asyncio.sleep(0)

        ta = asyncio.create_task(a())
        await a_inside.wait()
        tb = asyncio.create_task(b())
        await _until(lambda: bool(sem._semaphore._waiters), what="B parked as a waiter")
        release_a.set()
        await asyncio.gather(ta, tb)

        h, r = seen["handoff"], seen["resumed"]
        assert h == {"current_limit": 1, "available": 0, "held": 0, "drain_count": 0}
        assert h["available"] + h["held"] == h["current_limit"] + h["drain_count"] - 1  # one hand-off pending
        assert r == {"current_limit": 1, "available": 0, "held": 1, "drain_count": 0}
        assert r["available"] + r["held"] == r["current_limit"] + r["drain_count"]       # exact once B ran
        _assert_idle_conserved(sem)
        assert sem._holds == {}
