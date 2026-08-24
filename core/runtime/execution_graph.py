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
    """

    def __init__(self) -> None:
        self._graphs: Dict[str, ExecutionGraph] = {}
        self._queues: Dict[str, asyncio.Queue] = {}
        self._stream = None

    def attach_event_stream(self, stream: Any) -> None:
        if self._stream is stream:
            return
        if self._stream is not None:
            self._stream.unsubscribe("*", self._on_event)
        self._stream = stream
        stream.subscribe("*", self._on_event)

    def create(self, execution_id: str, *, title: str = "Execution") -> ExecutionGraph:
        existing = self._graphs.get(execution_id)
        if existing is not None:
            if title and existing.root.title == "Execution":
                existing.root.title = title
            return existing
        graph = ExecutionGraph(execution_id, title=title)
        self._graphs[execution_id] = graph
        self._queues[execution_id] = asyncio.Queue(maxsize=256)
        return graph

    def get(self, execution_id: str) -> Optional[ExecutionGraph]:
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
        queue = self._queues.get(execution_id)
        if queue is None:
            return
        while True:
            yield await queue.get()

    def ids(self) -> Iterable[str]:
        return self._graphs.keys()


execution_registry = ExecutionRegistry()