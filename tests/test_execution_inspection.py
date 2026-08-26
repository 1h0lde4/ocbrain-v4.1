import asyncio

import pytest

from core.events.event_stream import EventStream, StreamEvent
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_graph import ExecutionGraph, ExecutionStatus
from core.runtime.progress import ProgressMonitor
from core.runtime.projection import project_graph
from core.runtime.watchdog import ExecutionWatchdog


class MemoryStore:
    def __init__(self):
        self.events = []

    async def append(self, event):
        event = StreamEvent(**{**vars(event), "sequence": len(self.events) + 1})
        self.events.append(event)
        return event.sequence

    async def query(self, **kwargs):
        return list(self.events)

    async def replay(self, since_sequence=0):
        for event in self.events:
            if event.sequence > since_sequence:
                yield event

    async def get_checkpoint(self, name):
        return None

    async def count(self):
        return len(self.events)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_graph_supports_nested_nodes_and_authoritative_states():
    graph = ExecutionGraph("exec-1", title="Write story")
    parent = await graph.add_node(title="Generate story", operation_type="worker")
    child = await graph.add_node(title="Generate setting", parent_id=parent.node_id)
    await graph.update(parent.node_id, status=ExecutionStatus.RUNNING)
    await graph.update(child.node_id, status=ExecutionStatus.COMPLETED,
                       summary="Setting generated")

    snapshot = await graph.snapshot()
    assert snapshot["root_id"] == "exec-1"
    assert child.node_id in parent.children
    assert next(n for n in snapshot["nodes"] if n["node_id"] == child.node_id)["status"] == "completed"


@pytest.mark.asyncio
async def test_progress_monitor_emits_evidence_and_projection_allowlists_fields():
    stream = EventStream(MemoryStore())
    graph = ExecutionGraph("exec-2")
    node = await graph.add_node(title="Generate", operation_type="capability")
    monitor = ProgressMonitor(graph, stream)
    await monitor.report_progress(node.node_id, summary="Receiving output",
                                  progress_units={"tokens": 12})

    snapshot = project_graph(await graph.snapshot())
    projected = next(item for item in snapshot["nodes"] if item["id"] == node.node_id)
    assert projected["progress_units"] == {"tokens": 12}
    assert "execution_detail" not in projected
    assert stream._store.events[0].event_type == "execution.progress"


@pytest.mark.asyncio
async def test_watchdog_cancels_at_hard_deadline_and_never_exceeds_extension_cap():
    stream = EventStream(MemoryStore())
    graph = ExecutionGraph("exec-3")
    node = await graph.add_node(title="Long task")
    monitor = ProgressMonitor(graph, stream)
    await monitor.record_status(node.node_id, ExecutionStatus.RUNNING)
    token = CancellationToken()
    # Real ExecutionBudget (core/runtime/execution_budget.py, K4.4) measures
    # real elapsed wall-clock time from construction and has no fake-time
    # injection hook, so this uses a short real deadline + real sleep instead
    # of the injected `now=` the original (pre-K4.4) budget supported.
    budget = ExecutionBudget(
        startup_deadline_s=0.05, progress_deadline_s=0.05,
        hard_ceiling_s=0.1, absolute_ceiling_s=0.2, max_extension_s=0.1,
    )
    watchdog = ExecutionWatchdog(graph, budget, token, monitor)

    # One extension is available and respects the cap...
    assert budget.grant_extension(0.1) is True
    # ...but the cap is never exceeded: nothing is left for a second request.
    assert budget.grant_extension(0.1) is False

    await asyncio.sleep(0.25)  # past the (extended) hard ceiling
    assert await watchdog.inspect() == "expired"
    assert token.is_cancelled