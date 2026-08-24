"""Evidence-based progress reporting for execution graphs."""

import time
from typing import Any, Optional

from core.events.event_stream import EventStream, get_event_stream
from core.runtime.execution_graph import ExecutionGraph, ExecutionStatus


class ProgressMonitor:
    def __init__(self, graph: ExecutionGraph,
                 event_stream: Optional[EventStream] = None) -> None:
        self.graph = graph
        self.event_stream = event_stream or get_event_stream()

    async def report_progress(self, node_id: str, *, summary: str = "",
                              current_action: str = "",
                              progress: Optional[float] = None,
                              progress_units: Optional[dict[str, Any]] = None,
                              metadata: Optional[dict[str, Any]] = None) -> None:
        changes = {"status": ExecutionStatus.RUNNING,
                   "summary": summary, "current_action": current_action}
        if progress is not None:
            changes["progress"] = max(0.0, min(1.0, progress))
        if progress_units is not None:
            changes["progress_units"] = progress_units
        node = await self.graph.update(node_id, **changes)
        await self._emit("execution.progress", node, metadata)

    async def record_status(self, node_id: str, status: ExecutionStatus,
                            *, summary: str = "", current_action: str = "") -> None:
        node = await self.graph.update(node_id, status=status, summary=summary,
                                       current_action=current_action)
        await self._emit("execution.node.status", node)

    async def record_completion(self, node_id: str, *, summary: str = "") -> None:
        node = await self.graph.update(node_id, status=ExecutionStatus.COMPLETED,
                                       summary=summary, current_action="")
        await self._emit("execution.node.completed", node)

    async def record_failure(self, node_id: str, error: str, *,
                             failure_type: str = "ExecutionError") -> None:
        node = await self.graph.update(
            node_id, status=ExecutionStatus.FAILED, failure_type=failure_type,
            failure_message=error, summary="Execution failed", current_action="",
        )
        await self._emit("execution.node.failed", node)

    async def record_recovery(self, node_id: str, action: str) -> None:
        node = await self.graph.update(node_id, status=ExecutionStatus.RECOVERING,
                                       recovery_action=action,
                                       current_action="Recovering execution")
        await self._emit("execution.recovery.started", node)

    async def _emit(self, event_type: str, node: Any,
                    metadata: Optional[dict[str, Any]] = None) -> None:
        await self.event_stream.append(
            event_type=event_type,
            source="ProgressMonitor",
            payload={
                "execution_id": self.graph.execution_id,
                "node_id": node.node_id,
                "parent_id": node.parent_id,
                "status": node.status.value,
                "summary": node.summary,
                "current_action": node.current_action,
                "progress": node.progress,
                "progress_units": node.progress_units,
                "updated_at": node.updated_at,
                "last_progress_at": node.last_progress_at,
                "metadata": metadata or {},
            },
        )
