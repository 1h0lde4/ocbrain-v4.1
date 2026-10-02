import asyncio
import time
import logging
from enum import Enum
from typing import Awaitable, Any, Callable, Dict, List, Optional

logger = logging.getLogger("ocbrain.runtime.resilience")

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """
    Prevents cascading failures by stopping calls to a failing service.
    Transitions: CLOSED -> OPEN (on N failures) -> HALF_OPEN (after T time) -> CLOSED (on success)
    """
    def __init__(self, name: str, threshold: int = 3, reset_timeout: float = 30.0):
        self.name = name
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = 0
        self._lock = asyncio.Lock()

    async def call(self, fn: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.reset_timeout:
                    logger.info(f"[CircuitBreaker] {self.name} transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise RuntimeError(f"Circuit {self.name} is OPEN")
            elif self.state == CircuitState.HALF_OPEN:
                # Already probing! Reject other probes to avoid thundering herd.
                raise RuntimeError(f"Circuit {self.name} is HALF_OPEN (probing in progress)")
        
        # Call executes outside the lock so we don't block concurrent 503-style failures
        try:
            result = await fn(*args, **kwargs)
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    logger.info(f"[CircuitBreaker] {self.name} transitioning to CLOSED (recovered)")
                    self.state = CircuitState.CLOSED
                    self.failures = 0
            return result
        except Exception as e:
            async with self._lock:
                self.failures += 1
                self.last_failure_time = time.time()
                if self.failures >= self.threshold:
                    if self.state != CircuitState.OPEN:
                        logger.warning(f"[CircuitBreaker] {self.name} transitioning to OPEN")
                    self.state = CircuitState.OPEN
            raise e

class _Hold:
    """Per-acquisition record: one successful acquisition of one permit.

    FZ-04: this state used to live on the AdaptiveSemaphore instance
    (``_acquired`` / ``_start_time``), i.e. it was shared by every concurrent
    holder. With two or more holders, the first ``__aexit__`` cleared the shared
    flag and every later ``__aexit__`` then returned early *without releasing its
    permit*, so capacity was lost permanently. Each acquisition now owns its own
    record, so a release can never depend on another holder's state.
    """
    __slots__ = ("start",)

    def __init__(self, start: float) -> None:
        self.start = start


class AdaptiveSemaphore:
    """
    Adjusts concurrency limit based on observed latency (EMA-smoothed AIMD).
    Slow responses -> Reduce limit. Fast responses -> Gradually increase limit.

    Permit conservation (FZ-04 invariant):
        available + held == current_limit + drain_count
    where ``available`` is the underlying semaphore's free permits, ``held`` is
    the number of live ``async with`` holders and ``drain_count`` is the number of
    permits scheduled to be absorbed instead of released.  When idle
    (``held == 0``) this reduces to ``available == current_limit + drain_count``.
    A holder that exits for ANY reason (success, exception, cancellation,
    timeout) returns or absorbs exactly one permit. ``snapshot()`` exposes these
    numbers read-only.

    Per-acquisition state:
        ``async with sem`` records one ``_Hold`` per successful acquisition, keyed
        by the owning asyncio task as a LIFO stack (so nested use inside one task
        is correct too). ``__aexit__`` pops the hold that its own ``__aenter__``
        pushed. Nothing about one holder is stored on the shared instance.
        Limitation: ``__aenter__`` and ``__aexit__`` must run in the same task
        (always true for a plain ``async with`` inside a coroutine; not true if
        the ``async with`` is suspended inside an async generator that is later
        finalized by the event loop in a different task). An exit with no
        matching hold is logged as an error and releases nothing.

    Shrinking correctness:
        When the limit decreases, _drain_count is incremented.  Finishing
        tasks consult _drain_count: if positive, the finishing task absorbs its
        permit (skips release()) and decrements _drain_count, effectively
        removing one slot from the semaphore.  This is race-safe because:
          - the whole release/adapt section of __aexit__ contains no ``await``
            (the ``async with self._lock`` below is uncontended and does not
            suspend), so it runs atomically on the event loop and cannot be
            interleaved with, or cancelled in the middle of, another holder's
            release; tests/test_adaptive_semaphore_permit_conservation.py pins
            this non-suspending property
          - No task is interrupted — only finishing tasks participate
          - The underlying asyncio.Semaphore is never replaced
    """
    def __init__(self, min_limit: int = 1, max_limit: int = 10, target_latency_ms: float = 5000,
                 *, clock: Callable[[], float] = time.perf_counter):
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.target_latency = target_latency_ms / 1000.0
        self.current_limit = min_limit
        self._semaphore = asyncio.Semaphore(self.current_limit)
        self._lock = asyncio.Lock()
        self._avg_latency = self.target_latency # EMA seed
        self._alpha = 0.4 # Faster reaction to latency spikes
        self._clock = clock      # injectable only so latency-driven tests are deterministic
        self._holds: Dict[Optional[asyncio.Task], List[_Hold]] = {}  # per-task LIFO of live holds
        self._drain_count = 0   # permits to absorb on release

    def snapshot(self) -> Dict[str, int]:
        """Read-only permit accounting (see the conservation invariant above).

        ``available`` reads asyncio.Semaphore's internal counter (``_value``);
        there is no public accessor for it.
        """
        return {
            "current_limit": self.current_limit,
            "available": self._semaphore._value,
            "held": sum(len(stack) for stack in self._holds.values()),
            "drain_count": self._drain_count,
        }

    async def __aenter__(self):
        # If this await is cancelled, no permit was taken and nothing was
        # recorded (asyncio.Semaphore.acquire undoes its own bookkeeping).
        await self._semaphore.acquire()
        # From here to the end of this method there is no await: a permit that
        # has been taken is recorded in the same uninterrupted step.
        try:
            hold = _Hold(self._clock())
            self._holds.setdefault(asyncio.current_task(), []).append(hold)
        except BaseException:
            self._semaphore.release()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        task = asyncio.current_task()
        stack = self._holds.get(task)
        if not stack:
            logger.error(
                "[AdaptiveSemaphore] __aexit__ with no matching hold in this task "
                "(cross-task exit or unbalanced use); no permit released"
            )
            return
        hold = stack.pop()          # this acquisition's own record
        if not stack:
            del self._holds[task]
        latency = self._clock() - hold.start

        async with self._lock:
            # Drain: absorb permit instead of releasing to shrink capacity
            if self._drain_count > 0:
                self._drain_count -= 1
                # Do NOT release the semaphore — permit is absorbed
            else:
                self._semaphore.release()

            # Update EMA latency
            self._avg_latency = (self._alpha * latency) + ((1 - self._alpha) * self._avg_latency)

            # Use smoothed latency for limit decisions to avoid jitter
            if self._avg_latency > self.target_latency:
                new_limit = max(self.min_limit, int(self.current_limit * 0.9))
            else:
                new_limit = min(self.max_limit, self.current_limit + 1)

            if new_limit != self.current_limit:
                diff = new_limit - self.current_limit
                if diff > 0:
                    # Growing: first satisfy pending drain, then release surplus
                    absorb = min(diff, self._drain_count)
                    self._drain_count -= absorb
                    for _ in range(diff - absorb):
                        self._semaphore.release()
                else:
                    # Shrinking: schedule permits for absorption by finishing tasks
                    self._drain_count += abs(diff)
                self.current_limit = new_limit
                logger.debug(f"[AdaptiveSemaphore] Limit: {new_limit} "
                             f"(ema_lat: {self._avg_latency:.2f}s, "
                             f"drain: {self._drain_count})")

# Global instances can be managed here or in limits.py

