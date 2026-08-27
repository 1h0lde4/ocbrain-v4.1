import asyncio
import logging
from typing import Callable, Any, Awaitable, Optional
from .resilience import AdaptiveSemaphore
from .execution_budget import ExecutionBudget, ExecutionPolicy

logger = logging.getLogger("ocbrain.runtime.limits")
_ORIGINAL_WAIT_FOR = asyncio.wait_for

# Global adaptive concurrency controller (Latency-based)
ADAPTIVE_LLM_LIMIT = AdaptiveSemaphore(min_limit=2, max_limit=12, target_latency_ms=8000)

# Backpressure: Maximum number of concurrent tasks in the whole system
# This prevents memory exhaustion from too many pending handle() calls.
MAX_PENDING_REQUESTS = 100
PENDING_COUNTER = asyncio.Semaphore(MAX_PENDING_REQUESTS)

async def safe_llm_call(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    budget: Optional[ExecutionBudget] = None,
    **kwargs: Any,
) -> Any:
    """
    Wraps an async LLM call with adaptive concurrency control and an
    execution-budget-aware timeout.

    `budget` is additive and optional. Callers that don't pass one (every
    existing caller as of this change) see unchanged behavior: the timeout
    defaults to ExecutionPolicy.default_budget().hard_ceiling_s, which is
    the same 60.0s this function has always hardcoded -- see
    core/runtime/execution_budget.py for why that default reproduces the
    old constant exactly.

    This function stays deliberately simple: it enforces a single flat
    deadline for one atomic (non-streaming) call, where no intermediate
    progress signal exists to watch. Long-form, progress-aware generation
    with stall detection and bounded extension goes through
    core/model_router.py's monitored streaming path instead, which is
    where ExecutionWatchdog actually runs -- this function is not where the
    long-generation bug is fixed by itself; it's the safety net for
    short/atomic calls, including each per-provider attempt inside
    generate_with_fallback().
    """
    timeout = budget.hard_ceiling_s if budget is not None else ExecutionPolicy.default_budget().hard_ceiling_s

    async with ADAPTIVE_LLM_LIMIT:
        wait_for = asyncio.wait_for
        if wait_for is not _ORIGINAL_WAIT_FOR:
            # Some tests monkeypatch asyncio.wait_for and then call
            # asyncio.wait_for from inside the patch.  Temporarily restoring the
            # original avoids recursive self-calls while still honoring the
            # patched wrapper's timeout behavior.
            asyncio.wait_for = _ORIGINAL_WAIT_FOR
            try:
                return await wait_for(fn(*args, **kwargs), timeout=timeout)
            finally:
                asyncio.wait_for = wait_for
        return await _ORIGINAL_WAIT_FOR(fn(*args, **kwargs), timeout=timeout)

class BackpressureGuard:
    """
    Context manager to enforce global backpressure.
    Raises RuntimeError if too many requests are already in flight.
    """
    def __init__(self):
        self._acquired = False

    async def __aenter__(self):
        # We use non-blocking acquire to fail fast
        # Actually, in a high-load system, we might want to wait a bit
        try:
            await asyncio.wait_for(PENDING_COUNTER.acquire(), timeout=1.0)
            self._acquired = True
        except asyncio.TimeoutError:
            raise RuntimeError("System is overloaded. Please try again later.")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._acquired:
            PENDING_COUNTER.release()

class IterationBudget:
    def __init__(self, max_steps: int = 5):
        self.steps = 0
        self.max_steps = max_steps

    def check(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise RuntimeError(f"Iteration limit exceeded (max: {self.max_steps})")
