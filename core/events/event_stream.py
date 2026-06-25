"""
core/events/event_stream.py — EventStream (v4.3.5)

Immutable, append-only event log with pub/sub and replay.

Architecture references:
  - PI LAW 2: "All meaningful cognitive activity must emit immutable events."
  - FA §4.1 Layer 1: "EventStream (immutable WAL, pub/sub, replay, checkpoints)"
  - FA Pattern 2: "OCBrain's EventStream needs to become the basis for durable
                    workflow execution, not just observability."
  - FA §8 Risk 5: "Implement EventStream-based checkpoint first (v4.4.8)"

Design:
  - SQLite WAL-mode backend for single-node durability.
  - Abstract EventStore interface for future migration to Redpanda (v4.5.5).
  - Async pub/sub: subscribers receive events in order of emission.
  - Replay: reconstruct system state from any checkpoint.
  - Checkpoint markers: named timestamps for durable execution (v4.4.8).

Integration:
  - Workers emit lifecycle events through EventStream.append().
  - GovernanceKernel logs decisions through EventStream.append().
  - Complements (does not replace) the existing EventBus (core/event_bus.py),
    which handles in-process pub/sub without persistence.
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger("ocbrain.events.stream")


# ── Event Model ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StreamEvent:
    """A single immutable event in the EventStream.

    Architecture:
        PI LAW 2 — Every major operation must be observable, replayable,
                    inspectable, recoverable.
        FA §4.1 Layer 1 — EventStream event record.

    Attributes:
        event_id: Globally unique event identifier.
        event_type: Categorical event type (e.g. "worker.started").
        source: Originating component (e.g. "MemoryCuratorWorker").
        timestamp: Unix epoch when the event was created.
        payload: Arbitrary structured data.
        checkpoint: Optional checkpoint name for durable execution.
        sequence: Monotonically increasing sequence number (set by EventStore).
    """

    event_id:   str            = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str            = ""
    source:     str            = ""
    timestamp:  float          = field(default_factory=time.time)
    payload:    Dict[str, Any] = field(default_factory=dict)
    checkpoint: str            = ""
    sequence:   int            = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "event_id":   self.event_id,
            "event_type": self.event_type,
            "source":     self.source,
            "timestamp":  self.timestamp,
            "payload":    json.dumps(self.payload, default=str),
            "checkpoint": self.checkpoint,
            "sequence":   self.sequence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StreamEvent":
        """Deserialize from dict."""
        payload = d.get("payload", "{}")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                payload = {}
        return cls(
            event_id=d.get("event_id", str(uuid.uuid4())),
            event_type=d.get("event_type", ""),
            source=d.get("source", ""),
            timestamp=float(d.get("timestamp", time.time())),
            payload=payload,
            checkpoint=d.get("checkpoint", ""),
            sequence=int(d.get("sequence", 0)),
        )


# ── Abstract EventStore ──────────────────────────────────────────────────────

class EventStore(ABC):
    """Abstract persistence backend for EventStream.

    Architecture:
        FA §8 Risk 5 — SQLite WAL first, Redpanda at v4.5.5.
        Abstracting now prevents rewrite when migrating to distributed backend.
    """

    @abstractmethod
    async def append(self, event: StreamEvent) -> int:
        """Append event and return its sequence number."""
        ...

    @abstractmethod
    async def query(self, *,
                    event_type: Optional[str] = None,
                    source: Optional[str] = None,
                    since: float = 0.0,
                    until: float = 0.0,
                    limit: int = 100) -> List[StreamEvent]:
        """Query events by type, source, and time range."""
        ...

    @abstractmethod
    async def replay(self, since_sequence: int = 0) -> AsyncIterator[StreamEvent]:
        """Replay all events from a given sequence number."""
        ...

    @abstractmethod
    async def get_checkpoint(self, name: str) -> Optional[StreamEvent]:
        """Retrieve the latest checkpoint event by name."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Total number of events in the store."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""
        ...


# ── SQLite EventStore ─────────────────────────────────────────────────────────

class SQLiteEventStore(EventStore):
    """SQLite WAL-mode event store.

    Architecture:
        FA §4.1 Layer 1 — "EventStream (immutable WAL, pub/sub, replay, checkpoints)"
        FA §8 Risk 5 — "implement EventStream-based checkpoint first"

    Uses WAL journal mode for concurrent read/write without locking.
    All writes are through a single connection to maintain sequence ordering.
    """

    def __init__(self, db_path: str = ".data/events/stream.db") -> None:
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._sequence: int = 0
        self._init_db()

    def _init_db(self) -> None:
        """Initialize schema and recover sequence counter."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    sequence   INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id   TEXT UNIQUE NOT NULL,
                    event_type TEXT NOT NULL,
                    source     TEXT NOT NULL DEFAULT '',
                    timestamp  REAL NOT NULL,
                    payload    TEXT NOT NULL DEFAULT '{}',
                    checkpoint TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type
                ON events(event_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                ON events(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_checkpoint
                ON events(checkpoint) WHERE checkpoint != ''
            """)
            conn.commit()

            # Recover sequence counter
            row = conn.execute(
                "SELECT MAX(sequence) FROM events"
            ).fetchone()
            self._sequence = (row[0] or 0) if row else 0
        logger.info("SQLiteEventStore ready: %s (seq=%d)",
                     self._db_path, self._sequence)

    async def append(self, event: StreamEvent) -> int:
        """Append an event. Returns the assigned sequence number.

        Args:
            event: The StreamEvent to persist.

        Returns:
            The monotonically increasing sequence number.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._append_sync, event)

    def _append_sync(self, event: StreamEvent) -> int:
        with closing(sqlite3.connect(self._db_path)) as conn:
            cursor = conn.execute(
                """INSERT INTO events
                   (event_id, event_type, source, timestamp, payload, checkpoint)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event.event_id, event.event_type, event.source,
                 event.timestamp, json.dumps(event.payload, default=str),
                 event.checkpoint),
            )
            conn.commit()
            seq = cursor.lastrowid or 0
            self._sequence = seq
            return seq

    async def query(self, *,
                    event_type: Optional[str] = None,
                    source: Optional[str] = None,
                    since: float = 0.0,
                    until: float = 0.0,
                    limit: int = 100) -> List[StreamEvent]:
        """Query events with optional filters."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._query_sync, event_type, source, since, until, limit,
        )

    def _query_sync(self, event_type: Optional[str], source: Optional[str],
                    since: float, until: float, limit: int) -> List[StreamEvent]:
        clauses: List[str] = []
        params: List[Any] = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if since > 0:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until > 0:
            clauses.append("timestamp <= ?")
            params.append(until)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM events{where} ORDER BY sequence DESC LIMIT ?"
        params.append(limit)

        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [StreamEvent.from_dict(dict(r)) for r in rows]

    async def replay(self, since_sequence: int = 0) -> AsyncIterator[StreamEvent]:
        """Replay events from a sequence number.

        Architecture:
            PI LAW 2 — "replayable"
            FA §4.1 — "EventStream (replay, checkpoints)"
        """
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None, self._replay_sync, since_sequence,
        )
        for row in rows:
            yield StreamEvent.from_dict(row)

    def _replay_sync(self, since_sequence: int) -> List[Dict[str, Any]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM events WHERE sequence > ? ORDER BY sequence ASC",
                (since_sequence,),
            ).fetchall()
            return [dict(r) for r in rows]

    async def get_checkpoint(self, name: str) -> Optional[StreamEvent]:
        """Retrieve the latest checkpoint by name.

        Architecture:
            FA §4.1 — "EventStream (checkpoints)"
            FA v4.4.8 — "Checkpoint/resume from EventStream WAL"
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._get_checkpoint_sync, name,
        )

    def _get_checkpoint_sync(self, name: str) -> Optional[StreamEvent]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM events WHERE checkpoint = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (name,),
            ).fetchone()
            return StreamEvent.from_dict(dict(row)) if row else None

    async def count(self) -> int:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._count_sync)

    def _count_sync(self) -> int:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
            return row[0] if row else 0

    async def close(self) -> None:
        pass  # SQLite connections are per-call, nothing to close


# ── EventStream (pub/sub + persistence) ───────────────────────────────────────

# Subscriber type: async callable receiving a StreamEvent
Subscriber = Callable[[StreamEvent], Any]


class EventStream:
    """Immutable event stream with pub/sub and durable persistence.

    Architecture:
        PI LAW 2: "All meaningful cognitive activity must emit immutable events."
        FA §4.1 Layer 1: Event Backbone.
        FA Pattern 2: "EventStream needs to become the basis for durable
                        workflow execution."

    Combines:
      1. Persistent storage via EventStore (SQLite WAL, future Redpanda).
      2. In-process pub/sub for real-time subscribers.
      3. Replay capability for debugging and state reconstruction.
      4. Checkpoint markers for durable execution (v4.4.8).

    Usage:
        stream = EventStream()
        stream.subscribe("worker.*", my_handler)
        await stream.append("worker.started", source="ReActWorker",
                            payload={"task": "analyze code"})
    """

    def __init__(self, store: Optional[EventStore] = None) -> None:
        self._store: EventStore = store or SQLiteEventStore()
        self._subscribers: Dict[str, List[Subscriber]] = defaultdict(list)
        self._global_subscribers: List[Subscriber] = []
        logger.info("EventStream initialized")

    def subscribe(self, event_type: str, handler: Subscriber) -> None:
        """Subscribe to events of a specific type.

        Args:
            event_type: Event type to listen for. Use "*" for all events.
            handler: Async or sync callable receiving StreamEvent.

        Architecture:
            FA §4.1 Layer 1 — "pub/sub"
        """
        if event_type == "*":
            self._global_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Subscriber) -> None:
        """Remove a subscriber."""
        if event_type == "*":
            try:
                self._global_subscribers.remove(handler)
            except ValueError:
                pass
        else:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    async def append(self, event_type: str, *,
                     source: str = "",
                     payload: Optional[Dict[str, Any]] = None,
                     checkpoint: str = "") -> StreamEvent:
        """Create, persist, and broadcast an event.

        Args:
            event_type: Categorical event type (e.g. "worker.started").
            source: Originating component identifier.
            payload: Structured event data.
            checkpoint: If non-empty, marks this event as a checkpoint.

        Returns:
            The persisted StreamEvent with assigned sequence number.

        Architecture:
            PI LAW 2 — "All meaningful cognitive activity must emit immutable events."
        """
        event = StreamEvent(
            event_type=event_type,
            source=source,
            payload=payload or {},
            checkpoint=checkpoint,
        )

        # Persist
        seq = await self._store.append(event)
        # frozen dataclass — recreate with sequence
        event = StreamEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
            timestamp=event.timestamp,
            payload=event.payload,
            checkpoint=event.checkpoint,
            sequence=seq,
        )

        # Broadcast to subscribers
        await self._notify(event)
        return event

    async def _notify(self, event: StreamEvent) -> None:
        """Notify all matching subscribers. Errors are logged, never propagated.

        Architecture:
            FA §4.1 — "pub/sub"
        """
        handlers = (
            list(self._subscribers.get(event.event_type, []))
            + list(self._global_subscribers)
        )
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                    await result
            except Exception as e:
                logger.error("[EventStream] Subscriber error on '%s': %s",
                             event.event_type, e)

    async def query(self, **kwargs: Any) -> List[StreamEvent]:
        """Query persisted events. Delegates to EventStore.query()."""
        return await self._store.query(**kwargs)

    async def replay(self, since_sequence: int = 0) -> AsyncIterator[StreamEvent]:
        """Replay events from a sequence number.

        Architecture:
            PI LAW 2 — "replayable"
            FA §4.1 — "EventStream (replay)"
        """
        async for event in self._store.replay(since_sequence):
            yield event

    async def create_checkpoint(self, name: str,
                                 payload: Optional[Dict[str, Any]] = None
                                 ) -> StreamEvent:
        """Create a named checkpoint event.

        Architecture:
            FA §4.1 — "EventStream (checkpoints)"
            FA v4.4.8 — "Checkpoint/resume from EventStream WAL"

        Args:
            name: Checkpoint name (e.g. "workflow:abc:step3").
            payload: Additional checkpoint state.

        Returns:
            The persisted checkpoint StreamEvent.
        """
        return await self.append(
            event_type="system.checkpoint",
            source="EventStream",
            payload=payload or {},
            checkpoint=name,
        )

    async def get_checkpoint(self, name: str) -> Optional[StreamEvent]:
        """Retrieve the latest checkpoint by name."""
        return await self._store.get_checkpoint(name)

    async def stats(self) -> Dict[str, Any]:
        """Return stream statistics."""
        count = await self._store.count()
        return {
            "total_events": count,
            "subscriber_types": len(self._subscribers),
            "global_subscribers": len(self._global_subscribers),
        }

    async def close(self) -> None:
        """Release store resources."""
        await self._store.close()


# ── Module-level singleton ────────────────────────────────────────────────────

_stream: Optional[EventStream] = None


def get_event_stream() -> EventStream:
    """Return (or create) the shared EventStream singleton.

    Architecture:
        FA §4.1 Layer 1 — Single EventStream per process.
    """
    global _stream
    if _stream is None:
        _stream = EventStream()
    return _stream
