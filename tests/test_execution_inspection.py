import asyncio

import pytest

from core.events.event_stream import EventStream, StreamEvent
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_graph import ExecutionGraph, ExecutionStatus
from core.runtime.progress import ProgressMonitor
from core.runtime.projection import project_graph
from core.runtime.watchdog import GraphExecutionWatchdog


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
    watchdog = GraphExecutionWatchdog(graph, budget, token, monitor)

    # One extension is available and respects the cap...
    assert budget.grant_extension(0.1) is True
    # ...but the cap is never exceeded: nothing is left for a second request.
    assert budget.grant_extension(0.1) is False

    await asyncio.sleep(0.25)  # past the (extended) hard ceiling
    assert await watchdog.inspect() == "expired"
    assert token.is_cancelled


# ── DEBT-016 / ADR-KERNEL-02 regression tests ───────────────────────────────
#
# Before this fix, a stalled node was only ever *recorded* as STALLED —
# GraphExecutionWatchdog never attempted a bounded extension and never
# cancelled *because of* a stall (only via the unrelated hard-ceiling
# check). These tests exercise the shared watchdog_decision.decide() logic
# now driving this watchdog, matching the model-router-facing watchdog's
# existing, already-tested behavior (tests/test_execution_watchdog.py).


@pytest.mark.asyncio
async def test_watchdog_grants_bounded_extension_on_real_stall_and_records_recovery():
    stream = EventStream(MemoryStore())
    graph = ExecutionGraph("exec-4")
    node = await graph.add_node(title="Slow task")
    monitor = ProgressMonitor(graph, stream)
    await monitor.record_status(node.node_id, ExecutionStatus.RUNNING)
    token = CancellationToken()
    budget = ExecutionBudget(
        startup_deadline_s=0.05, progress_deadline_s=0.05,
        hard_ceiling_s=0.3, absolute_ceiling_s=1.0, max_extension_s=0.5,
    )
    watchdog = GraphExecutionWatchdog(graph, budget, token, monitor)

    await asyncio.sleep(0.1)  # past progress_deadline_s, node never touched again
    verdict = await watchdog.inspect()

    assert verdict == "extended"
    assert not token.is_cancelled
    assert budget.extension_consumed_s > 0
    recovery_events = [e for e in stream._store.events if e.event_type == "execution.recovery.started"]
    assert len(recovery_events) == 1
    assert recovery_events[0].payload["node_id"] == node.node_id


@pytest.mark.asyncio
async def test_watchdog_extends_then_eventually_cancels_with_stall_reason():
    stream = EventStream(MemoryStore())
    graph = ExecutionGraph("exec-5")
    node = await graph.add_node(title="Never finishes")
    monitor = ProgressMonitor(graph, stream)
    await monitor.record_status(node.node_id, ExecutionStatus.RUNNING)
    token = CancellationToken()
    # hard_ceiling_s is deliberately much larger than progress_deadline_s so
    # there's a comfortable, jitter-tolerant window after the granted
    # extension's grace period ends but before the (extended) hard ceiling
    # would fire on its own -- isolating "extension exhausted" (STALLED)
    # from "genuinely out of wall-clock time" (EXPIRED), which are different
    # code paths in watchdog_decision.decide().
    budget = ExecutionBudget(
        startup_deadline_s=0.05, progress_deadline_s=0.1,
        hard_ceiling_s=0.5, absolute_ceiling_s=0.6, max_extension_s=0.1,
    )
    watchdog = GraphExecutionWatchdog(graph, budget, token, monitor)

    # First stall: extension granted, not cancelled.
    await asyncio.sleep(0.15)
    assert await watchdog.inspect() == "extended"
    assert not token.is_cancelled

    # Grace period (0.1s from the grant) has passed, node still never
    # touched, and the one available extension is now fully consumed: this
    # must now actually cancel -- the entire point of DEBT-016 -- while
    # comfortably short of the (extended) 0.6s hard ceiling, proving this
    # is the stall path, not the hard-deadline path.
    await asyncio.sleep(0.15)
    verdict = await watchdog.inspect()

    assert verdict == "stalled"
    assert token.is_cancelled
    assert token.reason == "execution stall"
    failure_events = [e for e in stream._store.events if e.event_type == "execution.node.failed"]
    assert len(failure_events) == 1
    failed_node = await graph.get(node.node_id)
    assert failed_node.status == ExecutionStatus.FAILED
    assert failed_node.failure_type == "stall"


@pytest.mark.asyncio
async def test_watchdog_does_not_expire_during_gap_between_nodes():
    """Regression test: an earlier version of this fix keyed the "has this
    execution ever progressed" signal on the same has_progressed() check
    used for a single LLM attempt, without special-casing an empty active
    set. Since a gap between two workflow nodes (previous one completed,
    next one hasn't started RUNNING yet) has zero active nodes, that
    version misread the gap as "a fresh attempt that has not progressed
    yet" and expired it once elapsed time crossed the 10s startup
    deadline -- even though nothing had actually stalled. Only the
    unconditional hard-deadline check may fire while nothing is active."""
    stream = EventStream(MemoryStore())
    graph = ExecutionGraph("exec-6")
    monitor = ProgressMonitor(graph, stream)
    token = CancellationToken()
    # startup_deadline_s is deliberately tiny and progress_deadline_s huge:
    # if the gap were (incorrectly) routed through the "never progressed"
    # branch, it would expire almost immediately. hard_ceiling_s is large,
    # so a correct implementation must report "idle", not "expired".
    budget = ExecutionBudget(
        startup_deadline_s=0.01, progress_deadline_s=60.0,
        hard_ceiling_s=60.0, absolute_ceiling_s=120.0, max_extension_s=60.0,
    )
    watchdog = GraphExecutionWatchdog(graph, budget, token, monitor)

    await asyncio.sleep(0.05)  # past startup_deadline_s, but no node is active
    verdict = await watchdog.inspect()

    assert verdict == "idle"
    assert not token.is_cancelled