import asyncio
import time
import logging
from enum import Enum
from typing import Callable, Any, Awaitable

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

class AdaptiveSemaphore:
    """
    Adjusts concurrency limit based on observed latency (EMA-smoothed AIMD).
    Slow responses -> Reduce limit. Fast responses -> Gradually increase limit.
    """
    def __init__(self, min_limit: int = 1, max_limit: int = 10, target_latency_ms: float = 5000):
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.target_latency = target_latency_ms / 1000.0
        self.current_limit = min_limit
        self._semaphore = asyncio.Semaphore(self.current_limit)
        self._lock = asyncio.Lock()
        self._avg_latency = self.target_latency # EMA seed
        self._alpha = 0.4 # Faster reaction to latency spikes
        self._acquired = False  # BUG FIX: track acquisition state
        self._start_time = 0.0

    async def __aenter__(self):
        await self._semaphore.acquire()
        self._acquired = True    # BUG FIX: only set after successful acquire
        self._start_time = time.perf_counter()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._acquired:   # BUG FIX: guard release before checking acquired
            return
        self._acquired = False
        latency = time.perf_counter() - self._start_time
        self._semaphore.release()
        
        async with self._lock:
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
                    for _ in range(diff):
                        self._semaphore.release()
                self.current_limit = new_limit
                logger.debug(f"[AdaptiveSemaphore] Limit: {new_limit} (ema_lat: {self._avg_latency:.2f}s)")

# Global instances can be managed here or in limits.py
