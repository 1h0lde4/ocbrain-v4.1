"""core/sandbox/events.py — publish SandboxEvent through the existing
EventStream (core/events/event_stream.py).

Deliberately thin: this is an adapter, not a second event system
(PI LAW 2; reconciliation §2). Any object exposing an async
``append(event_type, *, source, payload, checkpoint)`` matching
EventStream's real signature works here, so tests can pass a lightweight
double (see tests/core/sandbox/) without spinning up a real SQLite store.
"""
from typing import Protocol

from core.sandbox.contracts import SandboxEvent

_SOURCE = "core.sandbox"


class SupportsAppend(Protocol):
    async def append(
        self, event_type: str, *, source: str = "", payload: dict | None = None, checkpoint: str = ""
    ): ...


async def publish(stream: SupportsAppend, event: SandboxEvent) -> None:
    """Publish one SandboxEvent onto an EventStream-compatible stream."""
    await stream.append(
        event.event_type.value,
        source=_SOURCE,
        payload={
            "handle_id": event.handle_id,
            "request_id": event.request_id,
            "timestamp": event.timestamp,
            **event.detail,
        },
    )
