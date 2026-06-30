"""
core/memory/backends/sqlite_archive.py — SQLiteArchiveBackend (L4 Archive)

Immutable, append-only audit log for KnowledgeEvents.
SQLite chosen over JSONL (see MEMORY_MIGRATION_DESIGN_V2.md §6):
  - Contradiction traces require indexed WHERE queries
  - Self-learning validation requires cross-event SQL joins
  - At 1M+ events, JSONL replay latency is unacceptable
  - export_to_jsonl() preserves human-readability on demand

Design invariant: once written, events are NEVER modified.
The only write path is append_event() and append_entry_snapshot().
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from core.memory.backends.base import ArchiveBackend
from core.memory.knowledge_event import KnowledgeEvent

logger = logging.getLogger("ocbrain.memory.backends.sqlite_archive")

DEFAULT_ARCHIVE_PATH = ".data/memory/archive.db"


class SQLiteArchiveBackend(ArchiveBackend):
    """
    L4 Archive — immutable SQLite event log.

    All KnowledgeEvents are append-only with idempotent insert
    (ON CONFLICT DO NOTHING on event_id PRIMARY KEY).

    Provides:
      - O(log n) queries by entry_id, event_type, time range
      - Full replay in chronological order
      - JSONL export for portability and long-term archiving
      - Entry snapshots at key lifecycle points (promote, archive, delete)
    """

    def __init__(self, db_path: str = DEFAULT_ARCHIVE_PATH):
        self.db_path = str(Path(db_path).resolve())
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_sync()
        logger.info("SQLiteArchiveBackend ready: %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sync(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_events (
                    event_id        TEXT PRIMARY KEY,
                    entry_id        TEXT NOT NULL,
                    event_type      TEXT NOT NULL,
                    timestamp       REAL NOT NULL,
                    worker_id       TEXT NOT NULL DEFAULT '',
                    workflow_id     TEXT NOT NULL DEFAULT '',
                    previous_layer  TEXT,
                    previous_truth  TEXT,
                    change_delta    TEXT NOT NULL DEFAULT '{}',
                    reason          TEXT NOT NULL DEFAULT '',
                    metadata        TEXT NOT NULL DEFAULT '{}'
                );

                -- Entry snapshots: full KnowledgeEntry state at key moments
                CREATE TABLE IF NOT EXISTS entry_snapshots (
                    snapshot_id     TEXT PRIMARY KEY,
                    entry_id        TEXT NOT NULL,
                    reason          TEXT NOT NULL DEFAULT '',
                    snapshot_data   TEXT NOT NULL,   -- JSON of full KnowledgeEntry
                    captured_at     REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_kev_entry
                    ON knowledge_events(entry_id);
                CREATE INDEX IF NOT EXISTS idx_kev_type
                    ON knowledge_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_kev_timestamp
                    ON knowledge_events(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_kev_worker
                    ON knowledge_events(worker_id);

                CREATE INDEX IF NOT EXISTS idx_snap_entry
                    ON entry_snapshots(entry_id);
                CREATE INDEX IF NOT EXISTS idx_snap_captured
                    ON entry_snapshots(captured_at DESC);
            """)
            conn.commit()

    async def _run(self, fn):
        """Dispatch blocking fn to thread executor.

        Uses get_running_loop() — correct API inside a coroutine.
        Session 3A: fixed from deprecated get_event_loop().
        """
        return await asyncio.get_running_loop().run_in_executor(None, fn)

    # ── ArchiveBackend implementation ─────────────────────────────────────

    async def append_event(self, event: KnowledgeEvent) -> None:
        """Append an event. Idempotent — duplicate event_id is silently ignored."""
        def _append():
            d = event.to_dict()
            # KnowledgeEvent.to_dict() uses "delta" and "from_layer"/"to_layer";
            # the archive schema uses "change_delta" and "previous_layer".
            # Build the params dict explicitly to keep both representations clean.
            params = {
                "event_id":       d.get("event_id",    ""),
                "entry_id":       d.get("entry_id",    ""),
                "event_type":     d.get("event_type",  ""),
                "timestamp":      d.get("timestamp",   0.0),
                "worker_id":      d.get("worker_id",   ""),
                "workflow_id":    d.get("workflow_id", ""),
                "previous_layer": d.get("from_layer",  ""),   # from_layer → previous_layer
                "previous_truth": "",                           # not on KnowledgeEvent
                "change_delta":   d.get("delta",       "{}"), # delta → change_delta
                "reason":         d.get("reason",      ""),
                "metadata":       d.get("metadata",    "{}"),
            }
            with closing(self._connect()) as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO knowledge_events
                    (event_id, entry_id, event_type, timestamp,
                     worker_id, workflow_id, previous_layer, previous_truth,
                     change_delta, reason, metadata)
                    VALUES
                    (:event_id, :entry_id, :event_type, :timestamp,
                     :worker_id, :workflow_id, :previous_layer, :previous_truth,
                     :change_delta, :reason, :metadata)
                """, params)
                conn.commit()
        await self._run(_append)

    async def append_entry_snapshot(self, entry: "Any",  # KnowledgeEntry
                                     reason: str = "") -> None:
        """Capture full entry state as a provenance record."""
        import uuid
        snapshot_id = str(uuid.uuid4())
        captured_at = time.time()

        def _snap():
            with closing(self._connect()) as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO entry_snapshots
                    (snapshot_id, entry_id, reason, snapshot_data, captured_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (snapshot_id, entry.entry_id, reason,
                      json.dumps(entry.to_dict(), default=str), captured_at))
                conn.commit()
        await self._run(_snap)

    async def query_events(self,
                            entry_id: Optional[str] = None,
                            event_type: Optional[str] = None,
                            worker_id: Optional[str] = None,
                            since: float = 0.0,
                            until: float = 0.0,
                            limit: int = 100) -> List[KnowledgeEvent]:
        def _query():
            conditions = []
            params: list = []
            if entry_id:
                conditions.append("entry_id=?"); params.append(entry_id)
            if event_type:
                conditions.append("event_type=?"); params.append(event_type)
            if worker_id:
                conditions.append("worker_id=?"); params.append(worker_id)
            if since:
                conditions.append("timestamp>=?"); params.append(since)
            if until:
                conditions.append("timestamp<=?"); params.append(until)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"""
                SELECT * FROM knowledge_events
                {where}
                ORDER BY timestamp DESC
                LIMIT {int(limit)}
            """
            with closing(self._connect()) as conn:
                return conn.execute(sql, params).fetchall()

        rows = await self._run(_query)
        return [KnowledgeEvent.from_dict(dict(r)) for r in rows]

    async def replay(self, since: float = 0.0) -> AsyncIterator[KnowledgeEvent]:
        """Yield all events in chronological order from `since`."""
        def _fetch_all():
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    "SELECT * FROM knowledge_events WHERE timestamp>=? "
                    "ORDER BY timestamp ASC",
                    (since,)
                ).fetchall()
                return [dict(r) for r in rows]

        rows = await self._run(_fetch_all)
        for row in rows:
            yield KnowledgeEvent.from_dict(row)

    async def export_jsonl(self, path: str, since: float = 0.0) -> int:
        """
        Export all events to JSONL file. Returns number of events written.
        Portability mechanism — human-readable archive without SQLite.
        """
        def _export():
            count = 0
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    "SELECT * FROM knowledge_events WHERE timestamp>=? "
                    "ORDER BY timestamp ASC",
                    (since,)
                ).fetchall()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                for row in rows:
                    event = KnowledgeEvent.from_dict(dict(row))
                    f.write(json.dumps(event.to_dict(), default=str) + "\n")
                    count += 1
            return count

        return await self._run(_export)

    async def stats(self) -> Dict[str, Any]:
        def _stats():
            with closing(self._connect()) as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM knowledge_events"
                ).fetchone()[0]
                snapshots = conn.execute(
                    "SELECT COUNT(*) FROM entry_snapshots"
                ).fetchone()[0]
                by_type = {
                    row[0]: row[1]
                    for row in conn.execute(
                        "SELECT event_type, COUNT(*) FROM knowledge_events "
                        "GROUP BY event_type ORDER BY COUNT(*) DESC"
                    ).fetchall()
                }
                oldest = conn.execute(
                    "SELECT MIN(timestamp) FROM knowledge_events"
                ).fetchone()[0]
            return {
                "backend": "SQLiteArchiveBackend",
                "db_path": self.db_path,
                "total_events": total,
                "total_snapshots": snapshots,
                "by_event_type": by_type,
                "oldest_event_ts": oldest,
            }
        return await self._run(_stats)
