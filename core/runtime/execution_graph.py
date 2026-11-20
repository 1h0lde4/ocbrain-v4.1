"""Canonical runtime execution state for progress inspection.

The graph is runtime state, not a planner tree.  It is intentionally
provider-agnostic and keeps private execution details separate from the
user-safe projection layer.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, Optional


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALLED = "stalled"
    RECOVERING = "recovering"
    WAITING = "waiting"
    BLOCKED = "blocked"


class ExecutionRegistryFull(RuntimeError):
    """Raised when the registry is full of executions that are still active."""


@dataclass
class ExecutionNode:
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str = ""
    operation_type: str = "operation"
    title: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    summary: str = ""
    progress: Optional[float] = None
    progress_units: Dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    updated_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    last_progress_at: float = 0.0
    current_action: str = ""
    failure_type: str = ""
    failure_message: str = ""
    recovery_action: str = ""
    execution_detail: Dict[str, Any] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)

    def elapsed_seconds(self, now: Optional[float] = None) -> float:
        if not self.started_at:
            return 0.0
        end = self.completed_at or (now if now is not None else time.time())
        return max(0.0, end - self.started_at)


class ExecutionGraph:
    """Mutable, hierarchical state for one live execution."""

    def __init__(self, execution_id: str, *, title: str = "Execution") -> None:
        self.execution_id = execution_id
        self.root = ExecutionNode(
            node_id=execution_id,
            operation_type="execution",
            title=title,
        )
        self._nodes: Dict[str, ExecutionNode] = {self.root.node_id: self.root}
        self._lock = asyncio.Lock()

    async def add_node(self, *, title: str, parent_id: str = "",
                       operation_type: str = "operation",
                       node_id: str = "") -> ExecutionNode:
        async with self._lock:
            parent = self._nodes.get(parent_id or self.root.node_id)
            if parent is None:
                raise KeyError(f"Unknown parent node: {parent_id}")
            node = ExecutionNode(
                node_id=node_id or str(uuid.uuid4()),
                parent_id=parent.node_id,
                operation_type=operation_type,
                title=title,
            )
            self._nodes[node.node_id] = node
            parent.children.append(node.node_id)
            parent.updated_at = time.time()
            return node

    async def update(self, node_id: str, **changes: Any) -> ExecutionNode:
        async with self._lock:
            node = self._nodes[node_id]
            for key, value in changes.items():
                if key == "status" and isinstance(value, str):
                    value = ExecutionStatus(value)
                if not hasattr(node, key):
                    raise AttributeError(f"Unknown execution node field: {key}")
                setattr(node, key, value)
            node.updated_at = time.time()
            if changes.get("status") == ExecutionStatus.RUNNING and not node.started_at:
                node.started_at = node.updated_at
            if changes.get("status") in {
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
            }:
                node.completed_at = node.updated_at
            if "progress" in changes or "progress_units" in changes:
                node.last_progress_at = node.updated_at
            return node

    async def get(self, node_id: str) -> Optional[ExecutionNode]:
        async with self._lock:
            return self._nodes.get(node_id)

    async def snapshot(self) -> Dict[str, Any]:
        async with self._lock:
            return {
                "execution_id": self.execution_id,
                "root_id": self.root.node_id,
                "nodes": [self._node_dict(node) for node in self._nodes.values()],
            }

    async def node_snapshot(self, node_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            node = self._nodes.get(node_id)
            return self._node_dict(node) if node else None

    @staticmethod
    def _node_dict(node: ExecutionNode) -> Dict[str, Any]:
        data = dict(vars(node))
        data["status"] = node.status.value
        data["children"] = list(node.children)
        return data


class ExecutionRegistry:
    """Process-local index of active/recent graphs and event queues.

    Queues are fed from the canonical EventStream by ``attach_event_stream``;
    they are a bounded delivery adapter for SSE, not a second event bus.
    Terminal records expire after ``retention_seconds`` and the registry
    enforces ``max_entries`` without evicting active executions.
    """

    _TERMINAL_STATUSES = frozenset({
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    })

    def __init__(
        self, *, max_entries: int = 1024, retention_seconds: float = 3600,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        if retention_seconds < 0:
            raise ValueError("retention_seconds cannot be negative")
        self._max_entries = max_entries
        self._retention_seconds = retention_seconds
        self._graphs: Dict[str, ExecutionGraph] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._created_at: Dict[str, float] = {}
        self._subscribers: Dict[str, int] = {}
        self._stream = None

    def attach_event_stream(self, stream: Any) -> None:
        if self._stream is stream:
            return
        if self._stream is not None:
            self._stream.unsubscribe("*", self._on_event)
        self._stream = stream
        stream.subscribe("*", self._on_event)

    def create(self, execution_id: str, *, title: str = "Execution") -> ExecutionGraph:
        self._prune_expired()
        existing = self._graphs.get(execution_id)
        if existing is not None:
            if title and existing.root.title == "Execution":
                existing.root.title = title
            return existing
        if len(self._graphs) >= self._max_entries:
            self._evict_oldest_terminal()
        if len(self._graphs) >= self._max_entries:
            raise ExecutionRegistryFull(
                "Execution registry is full of active executions"
            )
        graph = ExecutionGraph(execution_id, title=title)
        self._graphs[execution_id] = graph
        self._queues[execution_id] = asyncio.Queue(maxsize=256)
        self._created_at[execution_id] = time.time()
        return graph

    def get(self, execution_id: str) -> Optional[ExecutionGraph]:
        self._prune_expired()
        return self._graphs.get(execution_id)

    async def _on_event(self, event: Any) -> None:
        execution_id = event.payload.get("execution_id")
        queue = self._queues.get(execution_id)
        if queue is None:
            return
        item = {"event_type": event.event_type, **event.payload,
                "timestamp": event.timestamp, "sequence": event.sequence}
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(item)

    async def events(self, execution_id: str):
        self._prune_expired()
        queue = self._queues.get(execution_id)
        if queue is None:
            return
        self._subscribers[execution_id] = self._subscribers.get(execution_id, 0) + 1
        try:
            while True:
                yield await queue.get()
        finally:
            remaining = self._subscribers.get(execution_id, 1) - 1
            if remaining:
                self._subscribers[execution_id] = remaining
            else:
                self._subscribers.pop(execution_id, None)
            self._prune_expired()

    def ids(self) -> Iterable[str]:
        self._prune_expired()
        return self._graphs.keys()

    def _prune_expired(self) -> None:
        now = time.time()
        expired = [
            execution_id
            for execution_id, graph in self._graphs.items()
            if (
                (
                    graph.root.status in self._TERMINAL_STATUSES
                    and graph.root.completed_at
                    and now - graph.root.completed_at >= self._retention_seconds
                )
                or (
                    graph.root.status == ExecutionStatus.PENDING
                    and now - self._created_at.get(execution_id, now)
                    >= self._retention_seconds
                )
            )
            and self._subscribers.get(execution_id, 0) == 0
        ]
        for execution_id in expired:
            self._remove(execution_id)

    def _evict_oldest_terminal(self) -> None:
        terminal = [
            (graph.root.completed_at or self._created_at.get(execution_id, 0.0), execution_id)
            for execution_id, graph in self._graphs.items()
            if graph.root.status in self._TERMINAL_STATUSES
            and self._subscribers.get(execution_id, 0) == 0
        ]
        if terminal:
            _, execution_id = min(terminal)
            self._remove(execution_id)

    def _remove(self, execution_id: str) -> None:
        self._graphs.pop(execution_id, None)
        self._queues.pop(execution_id, None)
        self._created_at.pop(execution_id, None)
        self._subscribers.pop(execution_id, None)


execution_registry = ExecutionRegistry()