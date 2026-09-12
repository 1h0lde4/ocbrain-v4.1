"""tests/core/sandbox/test_events.py — Sandbox Fabric Phase 1, EventStream bridge.

Architecture Sources:
    core/sandbox/events.py
    core/events/event_stream.py
    docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md
        §2 (publish through the EXISTING EventStream, not a new bus)

Coverage:
    - publish() calls append() with the right dotted event_type string and
      a payload carrying handle_id/request_id/detail (fast unit test, a
      MockEventStream double -- mirrors tests/core/cognitive's own
      convention of the same shape)
    - A REAL integration test against the actual EventStream +
      SQLiteEventStore (pointed at a temp file, not the real .data/
      path) proving the wiring genuinely round-trips through persistence,
      not just a mocked assertion
"""
import pytest

from core.events.event_stream import EventStream, SQLiteEventStore
from core.sandbox.contracts import SandboxEvent, SandboxEventType
from core.sandbox.events import publish


class MockEventStream:
    """Minimal EventStream double, mirroring tests/core/cognitive's own
    helper of the same shape."""

    def __init__(self):
        self.events = []

    async def append(self, event_type, *, source="", payload=None, checkpoint=""):
        self.events.append({"event_type": event_type, "source": source, "payload": payload})


@pytest.mark.asyncio
async def test_publish_calls_append_with_expected_shape():
    stream = MockEventStream()
    event = SandboxEvent(
        event_type=SandboxEventType.FINISHED,
        handle_id="ns-abc",
        request_id="req-1",
        detail={"exit_code": 0},
    )
    await publish(stream, event)

    assert len(stream.events) == 1
    recorded = stream.events[0]
    assert recorded["event_type"] == "sandbox.finished"
    assert recorded["source"] == "core.sandbox"
    assert recorded["payload"]["handle_id"] == "ns-abc"
    assert recorded["payload"]["request_id"] == "req-1"
    assert recorded["payload"]["exit_code"] == 0


@pytest.mark.asyncio
async def test_publish_real_event_stream_round_trip(tmp_path):
    """Not a mock: a real EventStream backed by a real (temp) SQLite file,
    proving this actually persists rather than just satisfying a double's
    interface."""
    db_path = str(tmp_path / "sandbox_events_test.db")
    stream = EventStream(store=SQLiteEventStore(db_path=db_path))

    received = []
    stream.subscribe("sandbox.started", lambda e: received.append(e))

    event = SandboxEvent(
        event_type=SandboxEventType.STARTED, handle_id="ns-real-1", request_id="req-real-1"
    )
    await publish(stream, event)

    assert len(received) == 1
    assert received[0].event_type == "sandbox.started"
    assert received[0].payload["handle_id"] == "ns-real-1"
    assert received[0].sequence >= 1  # assigned by the real SQLite store
