"""Execution watchdog that observes graph progress and cancels canonically."""

import asyncio
import time
from typing import Optional

from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_graph import ExecutionGraph, ExecutionStatus
from core.runtime.progress import ProgressMonitor


class ExecutionWatchdog:
    def __init__(self, graph: ExecutionGraph, budget: ExecutionBudget,
                 cancellation_token: CancellationToken,
                 monitor: ProgressMonitor, *, interval_seconds: float = 1.0) -> None:
        self.graph = graph
        self.budget = budget
        self.cancellation_token = cancellation_token
        self.monitor = monitor
        self.interval_seconds = max(0.05, interval_seconds)
        self._task: Optional[asyncio.Task] = None

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
        """Inspect the active nodes once; useful for tests and manual polling.

        `now` overrides the progress-staleness check below (wall-clock node
        timestamps). It no longer overrides the hard-deadline check: the real
        ExecutionBudget (core/runtime/execution_budget.py, K4.4) measures
        elapsed time from its own `created_at` via time.monotonic() and has
        no fake-time injection hook.
        """
        if self.budget.is_hard_expired():
            self.cancellation_token.cancel("execution hard deadline expired")
            return "expired"
        snapshot = await self.graph.snapshot()
        wall_now = time.time() if now is None else now
        active = [node for node in snapshot["nodes"]
                  if node["status"] == ExecutionStatus.RUNNING.value]
        for node in active:
            last = node.get("last_progress_at") or node.get("started_at") or wall_now
            if wall_now - last >= self.budget.progress_deadline_s:
                await self.monitor.record_status(
                    node["node_id"], ExecutionStatus.STALLED,
                    summary="No meaningful progress detected",
                    current_action="Investigating execution",
                )
                return "stalled"
        return "healthy" if active else "idle"

    async def _run(self) -> None:
        while not self.cancellation_token.is_cancelled:
            await asyncio.sleep(self.interval_seconds)
            state = await self.inspect()
            if state == "expired":
                break