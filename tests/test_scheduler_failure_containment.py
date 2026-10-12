"""
tests/test_scheduler_failure_containment.py -- B8 / FZ-03.

Background learning jobs must never take the web server down, and their failures must
stay observable and bounded.  Original defect: ``Scheduler._loop_crawler`` /
``_loop_cleaner`` did their lazy import (and interval parsing) outside their try/except,
so an ImportError escaped through ``Scheduler.start()``'s ``asyncio.gather`` and through
``main.py``'s ``asyncio.gather(server.serve(), scheduler.start())`` and ended the process.

These tests drive the real ``Scheduler`` in exactly that gather shape next to a fake
server, with real import poisoning (``sys.modules[...] = None``), and cover the mission's
ten scenarios:

  1 dependency/import failure          2 runtime exception in one job
  3 repeated failure of the same job   4 one loop failing while another continues
  5 server healthy and responsive      6 failure remains observable
  7 no silent infinite restart loop    8 no uncontrolled task accumulation
  9 clean shutdown after failure      10 recovery once the cause is restored

Timing: every job's interval is patched to a few milliseconds via ``Scheduler._interval_s``
(the production interval logic is covered separately and directly); waits poll a predicate
with a generous ceiling instead of sleeping a fixed time.
"""
import asyncio
import contextlib
import json
import logging
import sys
import time
import types
import uuid

import pytest

import learning
from core.event_bus import EVENTS, bus
from learning.scheduler import Scheduler

LOGGER = "ocbrain.learning.scheduler"
SECRET = "SECRET-/home/operator/.private/path-and-token"   # must never reach events/status


# --------------------------------------------------------------------------- helpers

class _StubConfig:
    """Stands in for core.config.config inside learning.scheduler."""
    def __init__(self, **values):
        self.values = {"learning.training_enabled": True, **values}

    def get(self, key, default=None):
        v = self.values.get(key, default)
        if isinstance(v, BaseException):
            raise v
        return v


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    stub = _StubConfig()
    monkeypatch.setattr("learning.scheduler.config", stub)
    return stub


@pytest.fixture
def events():
    got = []

    async def handler(payload):
        got.append(dict(payload))

    names = ("learning.job_failed", "learning.job_recovered", "learning.job_abandoned")
    for n in names:
        bus.on(n, handler)
    yield got
    for n in names:
        bus.off(n, handler)


def _fake_module(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    return m


def _install(monkeypatch, name, **attrs):
    """Install a fake ``learning.<name>`` (sys.modules + package attribute)."""
    mod = _fake_module(f"learning.{name}", **attrs)
    monkeypatch.setitem(sys.modules, f"learning.{name}", mod)
    monkeypatch.setattr(learning, name, mod, raising=False)
    return mod


def _poison(monkeypatch, name):
    """Make ``import learning.<name>`` fail with ImportError, for real."""
    monkeypatch.setitem(sys.modules, f"learning.{name}", None)
    monkeypatch.delattr(learning, name, raising=False)


def _ok_modules(monkeypatch, counters=None):
    counters = counters if counters is not None else {}

    async def crawl_run_all(registry):
        counters["crawl"] = counters.get("crawl", 0) + 1

    def clean_run_all(registry):
        counters["clean"] = counters.get("clean", 0) + 1

    _install(monkeypatch, "crawler", run_all=crawl_run_all)
    _install(monkeypatch, "cleaner", run_all=clean_run_all)
    return counters


def _scheduler(monkeypatch, *, tick=0.02, **kw):
    kw.setdefault("min_interval_s", 0.0)
    kw.setdefault("restart_backoff_base_s", 0.01)
    kw.setdefault("restart_backoff_cap_s", 0.02)
    s = Scheduler({}, **kw)
    monkeypatch.setattr(s, "_interval_s", lambda job: tick)
    cycles = {"train": 0, "distill": 0, "gap": 0}

    async def train():
        cycles["train"] += 1

    async def distill():
        cycles["distill"] += 1

    async def gap():
        cycles["gap"] += 1

    monkeypatch.setattr(s, "_training_cycle", train)
    monkeypatch.setattr(s, "_distillation_cycle", distill)
    monkeypatch.setattr(s, "_gap_detection_cycle", gap)
    s.cycles = cycles
    return s


class _FakeServer:
    """Stand-in for uvicorn's ``server.serve()``; records liveness and event-loop gaps."""
    def __init__(self):
        self.ticks = 0
        self.max_gap = 0.0
        self._stop = False

    async def serve(self):
        last = time.perf_counter()
        while not self._stop:
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            self.max_gap = max(self.max_gap, now - last)
            last = now
            self.ticks += 1

    def stop(self):
        self._stop = True


@contextlib.asynccontextmanager
async def _running(sched):
    """Run ``asyncio.gather(server.serve(), scheduler.start())`` -- main.py's exact shape."""
    server = _FakeServer()

    async def main_like():
        await asyncio.gather(server.serve(), sched.start())

    task = asyncio.create_task(main_like())
    try:
        yield server, task
    finally:
        sched.stop()
        server.stop()
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(task, 5)


async def _until(pred, *, what, timeout=5.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if pred():
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"never reached: {what}")


def _scheduler_tasks():
    return [t for t in asyncio.all_tasks() if (t.get_name() or "").startswith("scheduler:")]


# --------------------------------------------------------------------------- scenarios

class TestContainment:

    @pytest.mark.parametrize("victim", ["crawler", "cleaner"])
    async def test_1_import_failure_does_not_kill_the_server(self, monkeypatch, victim):
        """The original FZ-03 defect, for both exposed jobs."""
        _ok_modules(monkeypatch)
        _poison(monkeypatch, victim)
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()[victim]["total_failures"] >= 2, what="repeated import failures")
            assert not task.done(), "main.py's gather ended: the scheduler failure killed the server"
            ticks = server.ticks
            await _until(lambda: server.ticks > ticks + 5, what="server still ticking after the failures")
            st = s.status()[victim]
            assert st["status"] == "degraded" and st["last_error_type"] in ("ModuleNotFoundError", "ImportError")

    async def test_1b_cleaner_import_failure_is_reported_at_startup_not_hours_later(self, monkeypatch, events):
        """The cleaner historically imported its module when its loop started (process start).  With a
        6 h interval the failure must still be visible at once, not only at the first tick."""
        _ok_modules(monkeypatch)
        _poison(monkeypatch, "cleaner")
        s = _scheduler(monkeypatch)
        monkeypatch.setattr(s, "_interval_s", lambda job: 6 * 3600.0)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()["cleaner"]["total_failures"] == 1, what="preflight failure")
            assert not task.done()
            st = s.status()["cleaner"]
            assert st["status"] == "degraded" and st["last_error_type"] in ("ModuleNotFoundError", "ImportError")
        pre = [e for e in events if e["job"] == "cleaner"]
        assert len(pre) == 1 and pre[0]["phase"] == "preflight" and pre[0]["consecutive_failures"] == 1

    async def test_1c_healthy_cleaner_preflight_is_silent_and_does_not_run_the_job(self, monkeypatch, events):
        counters = _ok_modules(monkeypatch)
        s = _scheduler(monkeypatch)
        monkeypatch.setattr(s, "_interval_s", lambda job: 6 * 3600.0)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()["crawler"]["total_successes"] >= 1, what="crawler ran (run-first)")
            await asyncio.sleep(0.1)
            st = s.status()["cleaner"]
            assert st["total_failures"] == 0 and st["total_successes"] == 0 and "clean" not in counters
        assert events == []

    async def test_2_runtime_exception_in_one_job_is_contained(self, monkeypatch):
        calls = []

        def boom(registry):
            calls.append(1)
            raise RuntimeError(SECRET)

        _ok_modules(monkeypatch)
        _install(monkeypatch, "cleaner", run_all=boom)
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: len(calls) >= 3, what="three failing runs")
            assert not task.done()
            assert s.status()["cleaner"]["last_error_type"] == "RuntimeError"

    async def test_3_and_7_repeated_failure_is_bounded_by_cadence_not_a_hot_loop(self, monkeypatch):
        calls = []

        def boom(registry):
            calls.append(time.perf_counter())
            raise RuntimeError("again")

        _ok_modules(monkeypatch)
        _install(monkeypatch, "cleaner", run_all=boom)
        s = _scheduler(monkeypatch, tick=0.05)
        async with _running(s) as (server, task):
            await asyncio.sleep(0.6)
            n = len(calls)
            st = s.status()["cleaner"]
        assert 4 <= n <= 14, f"{n} attempts in 0.6s at a 0.05s cadence: not paced by the cadence"
        assert st["consecutive_failures"] == n == st["total_failures"]
        assert st["restarts"] == 0, "an iteration failure is not a loop crash and must not restart the loop"
        assert min(b - a for a, b in zip(calls, calls[1:])) >= 0.03, "attempts are not paced"

    async def test_4_one_loop_failing_while_the_others_continue(self, monkeypatch):
        counters = _ok_modules(monkeypatch)
        _poison(monkeypatch, "cleaner")
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()["cleaner"]["total_failures"] >= 2, what="cleaner failing")

            def progress():
                return (counters.get("crawl", 0), s.cycles["train"], s.cycles["gap"], s.cycles["distill"])

            base = progress()
            await _until(lambda: all(c >= b + 2 for c, b in zip(progress(), base)),
                         what="every other job kept running while the cleaner failed")
            others = {k: v for k, v in s.status().items() if k != "cleaner"}
            assert all(v["status"] in ("idle", "running") and v["total_failures"] == 0 for v in others.values())

    async def test_5_server_stays_responsive_while_a_job_keeps_failing(self, monkeypatch):
        _ok_modules(monkeypatch)
        _poison(monkeypatch, "crawler")
        _poison(monkeypatch, "cleaner")
        s = _scheduler(monkeypatch, tick=0.02)
        async with _running(s) as (server, task):
            await asyncio.sleep(0.6)
            assert not task.done()
            assert server.ticks >= 15, f"server ticked only {server.ticks}x in 0.6s"
            assert server.max_gap < 0.5, f"event loop stalled {server.max_gap:.2f}s"

    async def test_6_failure_is_observable_and_never_leaks_exception_text(self, monkeypatch, events, caplog):
        caplog.set_level(logging.ERROR, logger=LOGGER)

        def boom(registry):
            raise RuntimeError(SECRET)

        _ok_modules(monkeypatch)
        _install(monkeypatch, "cleaner", run_all=boom)
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: any(e["job"] == "cleaner" for e in events), what="a job_failed event")
        ev = next(e for e in events if e["job"] == "cleaner")
        assert ev["_event"] == "learning.job_failed" and ev["phase"] == "iteration"
        assert ev["error_type"] == "RuntimeError" and ev["consecutive_failures"] >= 1
        uuid.UUID(ev["error_ref"])
        # Events and status() reach unauthenticated /events clients: no exception text, ever.
        assert SECRET not in json.dumps(events, default=str)
        assert SECRET not in json.dumps(s.status())
        # The operator-facing log has the full detail, keyed by the same ref.
        recs = [r for r in caplog.records if r.name == LOGGER and ev["error_ref"] in r.getMessage()]
        assert recs, "no server-side log line carries the error_ref"
        assert recs[0].exc_info and SECRET in str(recs[0].exc_info[1])

    async def test_7_loop_crash_is_restarted_with_backoff_then_abandoned(self, monkeypatch, events):
        _ok_modules(monkeypatch)
        s = _scheduler(monkeypatch, max_restarts=3, restart_window_s=3600)
        calls = {"gap": 0}

        def interval(job):
            if job.name == "gap_detector":
                calls["gap"] += 1
                raise RuntimeError(SECRET)        # the loop machinery itself breaks
            return 0.02

        monkeypatch.setattr(s, "_interval_s", interval)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()["gap_detector"]["status"] == "abandoned", what="gap_detector abandoned")
            n = calls["gap"]
            await asyncio.sleep(0.3)               # a restart storm would show up as more calls
            assert calls["gap"] == n == 4, f"{calls['gap']} loop starts: restarts are not bounded to max_restarts=3"
            assert not task.done(), "an abandoned job must not end the gather / the server"
            assert s.status()["gap_detector"]["restarts"] == 3
            assert s.cycles["train"] >= 2, "other jobs must be unaffected by the abandoned one"
        loop_failed = [e for e in events if e["job"] == "gap_detector" and e["_event"] == "learning.job_failed"]
        abandoned = [e for e in events if e["_event"] == "learning.job_abandoned"]
        assert len(loop_failed) == 3 and all(e["phase"] == "loop" and e["restart_in_s"] > 0 for e in loop_failed)
        assert len(abandoned) == 1 and abandoned[0]["job"] == "gap_detector"
        assert SECRET not in json.dumps(events, default=str)

    async def test_7b_crash_window_forgets_old_crashes(self, monkeypatch):
        """Rare, spread-out crashes must not permanently kill a job: only crashes inside the window count."""
        _ok_modules(monkeypatch)
        now = {"t": 0.0}

        def clock():
            now["t"] += 1000.0
            return now["t"]

        s = _scheduler(monkeypatch, max_restarts=1, restart_window_s=10, clock=clock)
        crashes = {"n": 0}

        def interval(job):
            if job.name == "gap_detector":
                crashes["n"] += 1
                raise RuntimeError("rare")
            return 0.02

        monkeypatch.setattr(s, "_interval_s", interval)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()["gap_detector"]["restarts"] >= 4, what="four spread-out crashes")
            assert s.status()["gap_detector"]["status"] != "abandoned"

    async def test_8_no_task_accumulation(self, monkeypatch):
        _ok_modules(monkeypatch)
        _poison(monkeypatch, "cleaner")
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()["cleaner"]["total_failures"] >= 1, what="first failure")
            before = len(asyncio.all_tasks())
            assert len(_scheduler_tasks()) == 5
            await _until(lambda: s.status()["cleaner"]["total_failures"] >= 15, what="fifteen failures")
            assert len(asyncio.all_tasks()) == before, "tasks accumulated across failures"
            assert len(_scheduler_tasks()) == 5
            with pytest.raises(RuntimeError, match="already running"):
                await s.start()                    # a second start() must not double the loops
            assert len(_scheduler_tasks()) == 5

    async def test_9_stop_wakes_sleeping_loops_promptly_after_failures(self, monkeypatch):
        _ok_modules(monkeypatch)
        _poison(monkeypatch, "crawler")                               # crawler runs first, so it fails at once
        s = _scheduler(monkeypatch)
        monkeypatch.setattr(s, "_interval_s", lambda job: 3600.0)    # ...then every loop sleeps for an hour
        task = asyncio.create_task(s.start())
        await _until(lambda: s.status()["crawler"]["total_failures"] >= 1, what="crawler failed once, now sleeping 1h")
        t0 = time.perf_counter()
        s.stop()
        await asyncio.wait_for(task, 2.0)          # before: stop() only flipped a flag and slept on
        assert time.perf_counter() - t0 < 1.0
        assert _scheduler_tasks() == []
        assert {v["status"] for v in s.status().values()} == {"stopped"}

    async def test_9b_cancelling_start_cancels_every_child(self, monkeypatch):
        _ok_modules(monkeypatch)
        _poison(monkeypatch, "cleaner")
        s = _scheduler(monkeypatch)
        task = asyncio.create_task(s.start())
        await _until(lambda: s.status()["cleaner"]["total_failures"] >= 1, what="a failure")
        kids = _scheduler_tasks()
        assert len(kids) == 5
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # No extra loop turn here on purpose: when start() has finished, every child must already be done.
        assert all(k.done() for k in kids), "start() returned while child tasks were still running"
        assert _scheduler_tasks() == []

    async def test_9c_full_shutdown_in_main_shape_is_clean_after_failures(self, monkeypatch):
        _ok_modules(monkeypatch)
        _poison(monkeypatch, "cleaner")
        s = _scheduler(monkeypatch)
        server = _FakeServer()

        async def main_like():
            await asyncio.gather(server.serve(), s.start())

        task = asyncio.create_task(main_like())
        await _until(lambda: s.status()["cleaner"]["total_failures"] >= 2, what="failures")
        s.stop()
        server.stop()
        await asyncio.wait_for(task, 3.0)          # completes normally, no exception
        assert _scheduler_tasks() == []

    async def test_9d_late_cleanup_of_a_finished_start_does_not_stop_a_newer_start(self, monkeypatch):
        """Found in review of PR #53: A's children are all done, a second start() B takes over, then A's
        start() resumes and runs its cleanup.  That cleanup used to reset ``_running`` and drop B's tasks."""
        _ok_modules(monkeypatch)
        s = _scheduler(monkeypatch)
        real_supervise, loop, spawned = s._supervise, asyncio.get_running_loop(), {}

        async def supervise(job):
            try:
                await real_supervise(job)
            finally:
                if job.name == "gap_detector" and "b" not in spawned:          # the last child to finish
                    # Queued before this child's completion callbacks, so B's first step runs between
                    # "all of A's children are done" and "A's start() resumes".
                    loop.call_soon(lambda: spawned.setdefault("b", asyncio.ensure_future(s.start())))

        monkeypatch.setattr(s, "_supervise", supervise)
        a = asyncio.create_task(s.start())
        await _until(lambda: len(_scheduler_tasks()) == 5, what="first start() running")
        s.stop()
        await _until(lambda: "b" in spawned, what="second start() spawned")
        await asyncio.wait_for(a, 2.0)                       # A's late cleanup has now run
        b = spawned["b"]
        await asyncio.sleep(0.15)
        assert not b.done(), "the newer start() was stopped by the older start()'s late cleanup"
        assert s._running and len(_scheduler_tasks()) == 5
        before = s.cycles["gap"]
        await _until(lambda: s.cycles["gap"] > before, what="the newer run keeps working")
        monkeypatch.setattr(s, "_supervise", real_supervise)
        s.stop()
        await asyncio.wait_for(b, 2.0)

    async def test_10_job_recovers_by_itself_once_the_cause_is_restored(self, monkeypatch, events):
        counters = _ok_modules(monkeypatch)
        _poison(monkeypatch, "cleaner")
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: s.status()["cleaner"]["consecutive_failures"] >= 2, what="failing")
            failures = s.status()["cleaner"]["consecutive_failures"]
            _install(monkeypatch, "cleaner", run_all=lambda registry: counters.__setitem__("clean", 1))
            await _until(lambda: s.status()["cleaner"]["consecutive_failures"] == 0, what="recovered")
            st = s.status()["cleaner"]
            assert st["status"] == "idle" and st["total_successes"] >= 1 and counters["clean"] == 1
            assert not task.done()
        rec = [e for e in events if e["_event"] == "learning.job_recovered" and e["job"] == "cleaner"]
        assert rec and rec[0]["after_failures"] >= failures


# --------------------------------------------------------------------------- supporting behaviour

class TestSupportingBehaviour:

    def test_new_events_are_in_the_catalogue(self):
        assert {"learning.job_failed", "learning.job_recovered", "learning.job_abandoned"} <= EVENTS

    async def test_a_failing_event_bus_cannot_take_a_job_down(self, monkeypatch):
        calls = []

        def boom(registry):
            calls.append(1)
            raise RuntimeError("x")

        _ok_modules(monkeypatch)
        _install(monkeypatch, "cleaner", run_all=boom)
        real_emit = bus.emit

        async def bad_emit(event, payload=None):
            if event.startswith("learning.job_"):
                raise RuntimeError("bus down")
            return await real_emit(event, payload)

        monkeypatch.setattr(bus, "emit", bad_emit)
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: len(calls) >= 3, what="job keeps running although reporting fails")
            assert not task.done() and s.status()["cleaner"]["restarts"] == 0

    async def test_distiller_gate_skips_without_counting_as_success_or_failure(self, monkeypatch, cfg):
        cfg.values["learning.training_enabled"] = False
        _ok_modules(monkeypatch)
        s = _scheduler(monkeypatch)
        async with _running(s) as (server, task):
            await _until(lambda: s.cycles["gap"] >= 3, what="other jobs ticking")
        d = s.status()["distiller"]
        assert s.cycles["distill"] == 0 and d["total_successes"] == 0 and d["total_failures"] == 0

    async def test_stop_before_start_does_not_break_a_later_start(self, monkeypatch):
        _ok_modules(monkeypatch)
        s = _scheduler(monkeypatch)
        s.stop()
        task = asyncio.create_task(s.start())
        await _until(lambda: s.cycles["gap"] >= 1, what="jobs run after an early stop()")
        s.stop()
        await asyncio.wait_for(task, 2.0)


class TestIntervalHandling:
    """Unusable config must fall back to the default; nothing may produce a hot loop."""

    @pytest.mark.parametrize("raw, expected", [
        (None, 3600.0),                 # unset      -> default (1h)
        (0, 3600.0),                    # 0          -> default (unchanged historical `or` semantics)
        (2, 7200.0),                    # valid
        (0.5, 1800.0),
        ("3", 10800.0),                 # numeric string accepted, as float() always did
        ("abc", 3600.0),                # was: ValueError outside try/except -> process death
        (-5, 3600.0),                   # was: sleep(<0) -> hot loop
        (float("nan"), 3600.0),
        (float("inf"), 3600.0),
        ([1], 3600.0),                  # TypeError
        (RuntimeError("config broke"), 3600.0),   # config.get itself raising
    ])
    def test_crawler_interval_from_config(self, cfg, raw, expected):
        cfg.values["learning.crawl_interval_h"] = raw
        s = Scheduler({})
        crawler = next(j for j in s._jobs if j.name == "crawler")
        assert s._interval_s(crawler) == expected

    def test_interval_is_floored(self, cfg):
        cfg.values["learning.crawl_interval_h"] = 0.0001            # 0.36 s
        s = Scheduler({}, min_interval_s=60.0)
        crawler = next(j for j in s._jobs if j.name == "crawler")
        assert s._interval_s(crawler) == 60.0

    def test_fixed_interval_jobs_keep_their_historical_periods(self):
        s = Scheduler({})
        by = {j.name: s._interval_s(j) for j in s._jobs}
        assert by["distiller"] == 12 * 3600 and by["gap_detector"] == 6 * 3600
        assert by["cleaner"] == 6 * 3600 and by["trainer"] == 24 * 3600 and by["crawler"] == 3600

    def test_historical_run_order_is_preserved(self):
        s = Scheduler({})
        assert {j.name: j.run_first for j in s._jobs} == {
            "crawler": True, "cleaner": False, "trainer": False, "distiller": False, "gap_detector": False}
