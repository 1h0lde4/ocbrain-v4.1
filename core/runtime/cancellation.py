"""
core/runtime/cancellation.py — CancellationToken (K2.1)

Cooperative cancellation mechanism for worker executions.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §7.4 — CancellationToken.
    Workers check context.cancellation_token.is_cancelled periodically
    in _run() and exit gracefully. Timeouts are cancellations triggered
    by timers — no separate mechanism.

Design:
    - Thread-safe via asyncio.Event.
    - cancel() is idempotent.
    - wait() returns True if cancelled within timeout, False on timeout.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("ocbrain.runtime.cancellation")


class CancellationToken:
    """Cooperative cancellation token carried in ExecutionContext.

    Workers check is_cancelled periodically during _run() and exit
    gracefully when True. Timeouts are implemented as timed cancel()
    calls — no separate timeout mechanism.

    Usage:
        token = CancellationToken()
        # In worker._run():
        if context.cancellation_token.is_cancelled:
            return WorkerResult(success=False, error="Cancelled")

        # From runtime or workflow:
        token.cancel()
        await token.wait(timeout=5.0)
    """

    __slots__ = ("_event", "_reason")

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._reason: str = ""

    def cancel(self, reason: str = "cancelled") -> None:
        """Request cancellation. Idempotent — calling multiple times is safe.

        Args:
            reason: Human-readable cancellation reason.
        """
        if not self._event.is_set():
            self._reason = reason
            self._event.set()
            logger.debug("CancellationToken triggered: %s", reason)

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._event.is_set()

    @property
    def reason(self) -> str:
        """Cancellation reason, empty if not cancelled."""
        return self._reason

    async def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for cancellation or timeout.

        Args:
            timeout: Maximum seconds to wait. None = wait forever.

        Returns:
            True if cancelled within timeout, False if timeout expired.
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
