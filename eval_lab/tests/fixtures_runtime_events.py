"""eval_lab/tests/fixtures_runtime_events.py — realistic StreamEvent fixtures.

Every payload shape here is copied from actual producer code inspected
during Slice 3 discovery (core/workers/base.py, core/workflow/runtime.py,
core/runtime/progress.py), not invented. Where a field's exact value
doesn't matter for a given test, a plausible placeholder is used, but the
*shape* (which keys exist, what they typically hold) is real.
"""

from __future__ import annotations

from core.events.event_stream import StreamEvent


def worker_started(*, event_id: str, sequence: int, timestamp: float = 1000.0,
                    worker_id: str = "PlannerWorker:a1b2c3d4", task_id: str = "task_x") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="worker.started", source=worker_id, timestamp=timestamp,
        payload={"worker_id": worker_id, "task_id": task_id}, sequence=sequence,
    )


def worker_progress(*, event_id: str, sequence: int, timestamp: float = 1001.0,
                     worker_id: str = "PlannerWorker:a1b2c3d4") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="worker.progress", source=worker_id, timestamp=timestamp,
        payload={"worker_id": worker_id, "message": "planning in progress"}, sequence=sequence,
    )


def worker_completed(*, event_id: str, sequence: int, timestamp: float = 1002.0,
                      worker_id: str = "PlannerWorker:a1b2c3d4", success: bool = True,
                      duration_ms: float = 1500.0, task_id: str = "task_x") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="worker.completed", source=worker_id, timestamp=timestamp,
        payload={"worker_id": worker_id, "task_id": task_id, "success": success, "duration_ms": duration_ms},
        sequence=sequence,
    )


def worker_failed(*, event_id: str, sequence: int, timestamp: float = 1002.0,
                   worker_id: str = "PlannerWorker:a1b2c3d4", error: str = "boom",
                   error_type: str = "ValueError") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="worker.failed", source=worker_id, timestamp=timestamp,
        payload={"error": error, "error_type": error_type}, sequence=sequence,
    )


def worker_cancelled(*, event_id: str, sequence: int, timestamp: float = 1002.0,
                      worker_id: str = "PlannerWorker:a1b2c3d4") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="worker.cancelled", source=worker_id, timestamp=timestamp,
        payload={}, sequence=sequence,
    )


def worker_rejected(*, event_id: str, sequence: int, timestamp: float = 1000.0,
                     worker_id: str = "PlannerWorker:a1b2c3d4", reason: str = "budget exceeded",
                     governor: str = "OrchestrationGovernor") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="worker.rejected", source=worker_id, timestamp=timestamp,
        payload={"reason": reason, "governor": governor}, sequence=sequence,
    )


def worker_escalated(*, event_id: str, sequence: int, timestamp: float = 1000.0,
                      worker_id: str = "PlannerWorker:a1b2c3d4", reason: str = "recursion depth",
                      governor: str = "AgentGovernor") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="worker.escalated", source=worker_id, timestamp=timestamp,
        payload={"reason": reason, "governor": governor}, sequence=sequence,
    )


def workflow_started(*, event_id: str, sequence: int, timestamp: float = 999.0,
                      workflow_id: str = "wf_1", source: str = "WorkflowRuntime") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="workflow.started", source=source, timestamp=timestamp,
        payload={"workflow_id": workflow_id}, sequence=sequence,
    )


def workflow_completed(*, event_id: str, sequence: int, timestamp: float = 1100.0,
                        workflow_id: str = "wf_1", source: str = "WorkflowRuntime") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="workflow.completed", source=source, timestamp=timestamp,
        payload={"workflow_id": workflow_id}, sequence=sequence,
    )


def execution_completed(*, event_id: str, sequence: int, timestamp: float = 1100.0,
                         source: str = "WorkflowRuntime") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="execution.completed", source=source, timestamp=timestamp,
        payload={}, sequence=sequence,
    )


def execution_failed(*, event_id: str, sequence: int, timestamp: float = 1100.0,
                      source: str = "WorkflowRuntime") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="execution.failed", source=source, timestamp=timestamp,
        payload={}, sequence=sequence,
    )


def execution_node_status(*, event_id: str, sequence: int, timestamp: float = 1005.0,
                           node_id: str = "node_1", status: str = "running",
                           source: str = "ProgressMonitor") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="execution.node.status", source=source, timestamp=timestamp,
        payload={"node_id": node_id, "status": status}, sequence=sequence,
    )


def execution_node_completed(*, event_id: str, sequence: int, timestamp: float = 1010.0,
                              node_id: str = "node_1", parent_id: str | None = None,
                              source: str = "ProgressMonitor") -> StreamEvent:
    payload = {"node_id": node_id}
    if parent_id:
        payload["parent_id"] = parent_id
    return StreamEvent(
        event_id=event_id, event_type="execution.node.completed", source=source, timestamp=timestamp,
        payload=payload, sequence=sequence,
    )


def execution_node_failed(*, event_id: str, sequence: int, timestamp: float = 1010.0,
                           node_id: str = "node_1", source: str = "ProgressMonitor") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="execution.node.failed", source=source, timestamp=timestamp,
        payload={"node_id": node_id}, sequence=sequence,
    )


def execution_recovery_started(*, event_id: str, sequence: int, timestamp: float = 1008.0,
                                node_id: str = "node_1", source: str = "ProgressMonitor") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="execution.recovery.started", source=source, timestamp=timestamp,
        payload={"node_id": node_id}, sequence=sequence,
    )


def execution_progress(*, event_id: str, sequence: int, timestamp: float = 1004.0,
                        node_id: str = "node_1", source: str = "ProgressMonitor") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type="execution.progress", source=source, timestamp=timestamp,
        payload={"node_id": node_id, "percent": 50}, sequence=sequence,
    )


def unknown_future_event(*, event_id: str, sequence: int, timestamp: float = 1000.0,
                          event_type: str = "future.exotic_thing", source: str = "SomeNewComponent") -> StreamEvent:
    return StreamEvent(
        event_id=event_id, event_type=event_type, source=source, timestamp=timestamp,
        payload={"some_new_field": "some_value"}, sequence=sequence,
    )
