"""
learning/scheduler.py — V2: adds distillation cycle + gap detection.

Failure containment (Kernel v1.0 freeze remediation B8 / FZ-03)
----------------------------------------------------------------
Background learning jobs must never take the web server down. Before this
change the crawler and cleaner loops ran their lazy imports (and interval
parsing) *outside* their try/except; an ImportError escaped through
``Scheduler.start()``'s ``asyncio.gather`` and through ``main.py``'s
``asyncio.gather(server.serve(), scheduler.start())``, ending the process.

Contract now:

* ``start()`` never raises for a job failure. Only cancellation propagates.
* **Iteration failure** (the job's work raised, including a lazy ImportError):
  logged server-side with traceback under an opaque ``error_ref``, counted,
  announced on the bus, and retried at the job's NORMAL cadence. It never
  disables the job, so a job recovers by itself once its cause (e.g. a missing
  dependency) is fixed, and the cadence itself is the retry bound.
* **Loop crash** (the loop machinery itself raised): the supervisor restarts the
  loop with exponential backoff, at most ``max_restarts`` crashes per
  ``restart_window_s``; beyond that the job is ABANDONED (loud log + bus event)
  until ``start()`` is called again. Other jobs are unaffected.
* **Preflight** (cleaner only): the cleaner historically imported its module when
  its loop started, i.e. at process start, not on its first run hours later. That
  import is kept at loop start but guarded, so a missing dependency is reported at
  once (``phase="preflight"``) instead of staying hidden until the first tick.
* **Interval** values come from config: unusable ones fall back to the job's
  default and every interval is floored at ``min_interval_s`` (no hot loop).
* **Shutdown**: ``stop()`` wakes sleeping loops immediately; cancelling
  ``start()`` cancels and awaits every child task (no leaked tasks).
* **Observability**: ``logging`` (traceback server-side), bus events
  ``learning.job_failed`` / ``learning.job_recovered`` / ``learning.job_abandoned``
  and ``status()``. Events and ``status()`` carry only the job name, the exception
  CLASS NAME and the opaque ``error_ref`` -- never exception text -- because
  ``GET /events`` streams every catalogued event to unauthenticated clients
  (DEBT-037 convention, ``core/error_ref.py``).

Known residual (not changed here, see PR): ``cleaner.run_all`` is synchronous and
runs on the event loop for its duration; the per-module / per-topic ``print()``
handlers inside the cycle methods below are unchanged.
"""
import asyncio
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional

from core.config import config
from core.error_ref import log_and_ref
from core.event_bus import bus

log = logging.getLogger("ocbrain.learning.scheduler")


@dataclass
class _Job:
    """Static description of one background job."""
    name: str
    config_key: Optional[str]            # [learning] key holding the interval in hours
    default_hours: float
    run_first: bool                      # True: work then wait (crawler). False: wait then work.
    work: Callable[[], Awaitable[None]]  # one run; resolved at call time (monkeypatch-friendly)
    gate: Optional[Callable[[], bool]] = None   # falsy => skip this tick (neither success nor failure)
    preflight: Optional[Callable[[], Any]] = None   # guarded once when the loop starts (import smoke test)


@dataclass
class JobState:
    """Per-job health. Holds no exception text (see module docstring)."""
    name: str
    status: str = "idle"                 # idle | running | degraded | abandoned | stopped
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    restarts: int = 0
    last_error_type: Optional[str] = None
    last_error_ref: Optional[str] = None


class Scheduler:
    def __init__(
        self,
        registry_ref: dict,
        *,
        min_interval_s: float = 60.0,
        max_restarts: int = 5,
        restart_window_s: float = 600.0,
        restart_backoff_base_s: float = 1.0,
        restart_backoff_cap_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.registry = registry_ref
        self._running = False
        self.min_interval_s = min_interval_s
        self.max_restarts = max_restarts
        self.restart_window_s = restart_window_s
        self.restart_backoff_base_s = restart_backoff_base_s
        self.restart_backoff_cap_s = restart_backoff_cap_s
        self._clock = clock
        self._stop = asyncio.Event()
        self._tasks: List["asyncio.Task[None]"] = []
        self._jobs: List[_Job] = [
            _Job("crawler", "learning.crawl_interval_h", 1.0, True, self._work_crawl),
            _Job("cleaner", "learning.clean_interval_h", 6.0, False, self._work_clean,
                 preflight=self._preflight_clean),
            _Job("trainer", "learning.train_interval_h", 24.0, False, self._work_train),
            _Job("distiller", None, 12.0, False, self._work_distill,       # V2
                 gate=lambda: bool(config.get("learning.training_enabled", True))),
            _Job("gap_detector", None, 6.0, False, self._work_gap),        # V2
        ]
        self._state: Dict[str, JobState] = {j.name: JobState(j.name) for j in self._jobs}
        self._crashes: Dict[str, Deque[float]] = {j.name: deque() for j in self._jobs}

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if any(not t.done() for t in self._tasks):
            raise RuntimeError("Scheduler.start() called while already running")
        self._running = True
        self._stop = asyncio.Event()
        for job in self._jobs:
            self._crashes[job.name].clear()
            self._state[job.name].status = "idle"
        self._tasks = [
            asyncio.create_task(self._supervise(job), name=f"scheduler:{job.name}")
            for job in self._jobs
        ]
        try:
            results = await asyncio.gather(*self._tasks, return_exceptions=True)
            for job, res in zip(self._jobs, results):
                if isinstance(res, Exception):   # a supervisor itself failed: report it, never raise
                    ref = log_and_ref(log, f"scheduler supervisor '{job.name}'", res)
                    st = self._state[job.name]
                    st.status, st.last_error_type, st.last_error_ref = "abandoned", type(res).__name__, ref
                    await self._emit("learning.job_abandoned", {
                        "job": job.name, "phase": "supervisor",
                        "error_type": type(res).__name__, "error_ref": ref})
        finally:
            # If start() is cancelled, gather() cancels every supervisor AND does not finish until they
            # have all finished, so no child outlives start() (pinned by test_9b).
            self._tasks = []
            self._running = False

    def stop(self) -> None:
        self._running = False
        self._stop.set()

    def status(self) -> Dict[str, Dict[str, Any]]:
        """Read-only per-job health snapshot (plain values, no exception text)."""
        return {
            n: {
                "status": s.status,
                "consecutive_failures": s.consecutive_failures,
                "total_failures": s.total_failures,
                "total_successes": s.total_successes,
                "restarts": s.restarts,
                "last_error_type": s.last_error_type,
                "last_error_ref": s.last_error_ref,
            }
            for n, s in self._state.items()
        }

    # ── supervision ──────────────────────────────────────────────────────────

    async def _supervise(self, job: _Job) -> None:
        state = self._state[job.name]
        try:
            while self._running:
                try:
                    await self._run_loop(job)
                    return                       # loop ended because stop() was requested
                except Exception as exc:         # loop machinery crashed: bounded restart
                    if not await self._on_loop_crash(job, exc):
                        return
        finally:
            if state.status != "abandoned":
                state.status = "stopped"

    async def _on_loop_crash(self, job: _Job, exc: Exception) -> bool:
        """Record a loop crash. True => restart after backoff; False => give up / stopping."""
        state = self._state[job.name]
        ref = log_and_ref(log, f"scheduler job '{job.name}' loop", exc)
        state.last_error_type, state.last_error_ref = type(exc).__name__, ref
        now = self._clock()
        window = self._crashes[job.name]
        window.append(now)
        while window and now - window[0] > self.restart_window_s:
            window.popleft()
        if len(window) > self.max_restarts:
            state.status = "abandoned"
            log.critical("scheduler job '%s' abandoned: %d loop crashes within %.0fs (last error_ref=%s)",
                         job.name, len(window), self.restart_window_s, ref)
            await self._emit("learning.job_abandoned", {
                "job": job.name, "phase": "loop", "restarts": state.restarts,
                "error_type": state.last_error_type, "error_ref": ref})
            return False
        state.restarts += 1
        delay = min(self.restart_backoff_cap_s, self.restart_backoff_base_s * 2 ** (len(window) - 1))
        log.warning("scheduler job '%s' loop crashed (error_ref=%s); restart %d/%d in %.2fs",
                    job.name, ref, len(window), self.max_restarts, delay)
        await self._emit("learning.job_failed", {
            "job": job.name, "phase": "loop", "error_type": state.last_error_type,
            "error_ref": ref, "restart_in_s": delay})
        return await self._wait(delay)

    async def _run_loop(self, job: _Job) -> None:
        if job.preflight is not None:
            try:
                job.preflight()
            except Exception as exc:             # reported at once; the tick retries (and can recover)
                await self._record_failure(job, exc, phase="preflight")
        first = True
        while self._running:
            if not (job.run_first and first):
                if not await self._wait(self._interval_s(job)):
                    return
            first = False
            if not self._running:
                return
            await self._tick(job)

    async def _tick(self, job: _Job) -> None:
        """One guarded run of a job. Only cancellation escapes."""
        state = self._state[job.name]
        try:
            if job.gate is not None and not job.gate():
                return                           # skipped: neither a success nor a failure
            state.status = "running"
            await job.work()
        except Exception as exc:                 # containment boundary: reported, never swallowed
            await self._record_failure(job, exc)
        else:
            await self._record_success(job)

    async def _record_failure(self, job: _Job, exc: Exception, phase: str = "iteration") -> None:
        state = self._state[job.name]
        state.consecutive_failures += 1
        state.total_failures += 1
        state.status = "degraded"
        ref = log_and_ref(log, f"scheduler job '{job.name}'", exc)   # full detail: server-side only
        state.last_error_type, state.last_error_ref = type(exc).__name__, ref
        await self._emit("learning.job_failed", {
            "job": job.name, "phase": phase, "error_type": state.last_error_type,
            "error_ref": ref, "consecutive_failures": state.consecutive_failures})

    async def _record_success(self, job: _Job) -> None:
        state = self._state[job.name]
        was_failing = state.consecutive_failures
        state.consecutive_failures = 0
        state.total_successes += 1
        state.status = "idle"
        if was_failing:
            log.info("scheduler job '%s' recovered after %d consecutive failure(s)", job.name, was_failing)
            await self._emit("learning.job_recovered", {"job": job.name, "after_failures": was_failing})

    async def _emit(self, event: str, payload: Dict[str, Any]) -> None:
        """Reporting must never take a job down."""
        try:
            await bus.emit(event, payload)
        except Exception:
            log.exception("scheduler: bus.emit('%s') failed", event)

    # ── timing ───────────────────────────────────────────────────────────────

    async def _wait(self, seconds: float) -> bool:
        """Wait up to ``seconds``. False => stop() was requested (caller should exit promptly)."""
        if self._stop.is_set():
            return False
        try:
            async with asyncio.timeout(seconds):
                await self._stop.wait()
        except TimeoutError:
            return True
        return False

    def _interval_s(self, job: _Job) -> float:
        """Seconds between runs. Unusable config falls back to the job default; floored at min_interval_s."""
        hours = job.default_hours
        if job.config_key:
            try:
                raw = config.get(job.config_key)
                if raw:                          # 0 / None / "" => default (as before)
                    hours = float(raw)
            except Exception as exc:
                log.warning("scheduler: unusable %s (%s); using default %sh",
                            job.config_key, type(exc).__name__, job.default_hours)
                hours = job.default_hours
        seconds = hours * 3600
        if not math.isfinite(seconds) or seconds <= 0:
            log.warning("scheduler: non-positive/non-finite interval for '%s'; using default %sh",
                        job.name, job.default_hours)
            seconds = job.default_hours * 3600
        return max(seconds, self.min_interval_s)

    # ── one run of each job (lazy imports are INSIDE the guarded tick on purpose) ─

    async def _work_crawl(self) -> None:
        from learning.crawler import run_all
        await run_all(self.registry)
        await bus.emit("learning.crawl_done", {"modules": list(self.registry.keys())})

    def _preflight_clean(self) -> None:
        from learning import cleaner  # noqa: F401  (historical import-at-loop-start, now guarded)

    async def _work_clean(self) -> None:
        from learning import cleaner
        cleaner.run_all(self.registry)           # synchronous: blocks the loop while it runs (residual)
        await bus.emit("learning.clean_done", {})

    async def _work_train(self) -> None:
        await self._training_cycle()

    async def _work_distill(self) -> None:
        await self._distillation_cycle()

    async def _work_gap(self) -> None:
        await self._gap_detection_cycle()

    async def _training_cycle(self):
        from learning import trainer, finetuner, evaluator
        from core.model_router import model_router
        from core.brain_version import brain_version_manager

        for name, module in self.registry.items():
            state = config.get_module_state(name)
            if state.get("pin_to_external", False):
                continue

            data_path = trainer.prepare(name, self.registry)
            if data_path is None:
                continue

            await bus.emit("learning.train_started", {"module": name})

            pending_path = finetuner.train(name, data_path)
            if pending_path is None:
                continue

            passed = await evaluator.evaluate(name, pending_path, self.registry)
            if passed:
                module.load_weights(pending_path)
                model_router._update_maturity(name, 0.7)
                model_router._maybe_promote(name)
                with open(data_path) as _f:
                    n_pairs = sum(1 for _ in _f)
                brain_version_manager.record_training(name, n_pairs)
                await bus.emit("learning.train_done", {"module": name, "passed": True})
                await bus.emit("module.weights_updated", {"module": name})
                print(f"[scheduler] {name}: weights hot-swapped ✓")
            else:
                import shutil
                shutil.rmtree(pending_path, ignore_errors=True)
                await bus.emit("module.weights_failed", {"module": name})
                print(f"[scheduler] {name}: weights failed eval — kept previous")

    async def _distillation_cycle(self):
        """Run distillation for any pending gap queues."""
        from learning.gap_detector import load_gap_queue, clear_gap_queue, mark_topic_known
        from learning.distiller import distill_topic
        from core.brain_version import brain_version_manager

        for name in self.registry:
            gaps = load_gap_queue(name)
            if not gaps:
                continue
            print(f"[scheduler] Distilling {len(gaps)} gaps for '{name}'")
            for topic in gaps:
                try:
                    n = await distill_topic(name, topic, num_pairs=30)
                    if n > 0:
                        mark_topic_known(name, topic)
                        brain_version_manager.record_distillation()
                except Exception as e:
                    print(f"[scheduler] distill '{topic}' for {name}: {e}")
            clear_gap_queue(name)

    async def _gap_detection_cycle(self):
        from learning.gap_detector import detect_and_queue
        for name in self.registry:
            try:
                gaps = await detect_and_queue(name, self.registry)
                if gaps:
                    print(f"[scheduler] {name}: queued {len(gaps)} gap topics")
            except Exception as e:
                print(f"[scheduler] gap detection for {name}: {e}")

    async def trigger_module(self, module_name: str) -> str:
        from learning import trainer, finetuner, evaluator

        data_path = trainer.prepare(module_name, self.registry)
        if data_path is None:
            return f"Not enough training pairs for '{module_name}'."
        pending = finetuner.train(module_name, data_path)
        if pending is None:
            return f"Fine-tuning failed for '{module_name}'."
        passed = await evaluator.evaluate(module_name, pending, self.registry)
        if passed:
            self.registry[module_name].load_weights(pending)
            await bus.emit("module.weights_updated", {"module": module_name})
            return f"'{module_name}' updated and hot-swapped successfully."
        else:
            import shutil
            shutil.rmtree(pending, ignore_errors=True)
            return f"'{module_name}' new weights failed evaluation — kept previous."
