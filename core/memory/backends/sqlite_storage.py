"""
core/memory/backends/sqlite_storage.py — SQLiteStorageBackend (L1 Episodic)

Implements StorageBackend via SQLite WAL + FTS5.
All blocking sqlite3 calls run in asyncio.get_event_loop().run_in_executor()
to avoid event loop starvation (§5, Issue 9 pattern).

Schema: knowledge_entries + knowledge_entries_fts (virtual, FTS5)
FTS5 triggers keep the virtual table in sync automatically.
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.memory.backends.base import StorageBackend
from core.memory.knowledge_entry import KnowledgeEntry

logger = logging.getLogger("ocbrain.memory.backends.sqlite_storage")

DEFAULT_DB_PATH = ".data/memory/unified.db"


class SQLiteStorageBackend(StorageBackend):
    """
    Primary CRUD + FTS5 text search backend for L1 Episodic memory.

    Design decisions:
    - WAL mode: concurrent reads without blocking writes
    - FTS5 triggers: no manual index maintenance needed
    - run_in_executor: all sqlite3 calls off the event loop (§20.4)
    - Single connection per call: avoids connection pool complexity
    - UPSERT on entry_id: idempotent write for migration safety
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = str(Path(db_path).resolve())
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_sync()
        logger.info("SQLiteStorageBackend ready: %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sync(self) -> None:
        """Create schema. Called once at construction (not in event loop)."""
        with closing(self._connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_entries (
                    entry_id       TEXT PRIMARY KEY,
                    layer          TEXT NOT NULL,
                    content        TEXT NOT NULL,
                    summary        TEXT NOT NULL DEFAULT '',
                    importance     REAL NOT NULL DEFAULT 0.5,
                    confidence     REAL NOT NULL DEFAULT 1.0,
                    truth_status   TEXT NOT NULL DEFAULT 'unknown',
                    trust_score    REAL NOT NULL DEFAULT 1.0,
                    source         TEXT NOT NULL DEFAULT '',
                    worker_id      TEXT NOT NULL DEFAULT '',
                    workflow_id    TEXT NOT NULL DEFAULT '',
                    derived_from   TEXT NOT NULL DEFAULT '[]',
                    supports       TEXT NOT NULL DEFAULT '[]',
                    contradicts    TEXT NOT NULL DEFAULT '[]',
                    supersedes     TEXT NOT NULL DEFAULT '[]',
                    graph_node_id  TEXT,
                    tags           TEXT NOT NULL DEFAULT '[]',
                    metadata       TEXT NOT NULL DEFAULT '{}',
                    procedure_name TEXT,
                    created_at     REAL NOT NULL,
                    updated_at     REAL NOT NULL,
                    accessed_at    REAL NOT NULL,
                    access_count   INTEGER NOT NULL DEFAULT 0
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_entries_fts
                USING fts5(
                    content,
                    summary,
                    tags,
                    content='knowledge_entries',
                    content_rowid='rowid'
                );

                CREATE TRIGGER IF NOT EXISTS ke_ai AFTER INSERT ON knowledge_entries BEGIN
                    INSERT INTO knowledge_entries_fts(rowid, content, summary, tags)
                    VALUES (new.rowid, new.content, new.summary, new.tags);
                END;

                CREATE TRIGGER IF NOT EXISTS ke_au AFTER UPDATE ON knowledge_entries BEGIN
                    UPDATE knowledge_entries_fts
                    SET content=new.content, summary=new.summary, tags=new.tags
                    WHERE rowid=old.rowid;
                END;

                CREATE TRIGGER IF NOT EXISTS ke_ad AFTER DELETE ON knowledge_entries BEGIN
                    DELETE FROM knowledge_entries_fts WHERE rowid=old.rowid;
                END;

                CREATE INDEX IF NOT EXISTS idx_ke_layer
                    ON knowledge_entries(layer);
                CREATE INDEX IF NOT EXISTS idx_ke_importance
                    ON knowledge_entries(importance DESC);
                CREATE INDEX IF NOT EXISTS idx_ke_truth
                    ON knowledge_entries(truth_status);
                CREATE INDEX IF NOT EXISTS idx_ke_created
                    ON knowledge_entries(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ke_source
                    ON knowledge_entries(source);
                CREATE INDEX IF NOT EXISTS idx_ke_procedure
                    ON knowledge_entries(procedure_name)
                    WHERE procedure_name IS NOT NULL;
            """)
            conn.commit()

    # ── Async helpers ─────────────────────────────────────────────────────

    async def _run(self, fn):
        """Run blocking sqlite3 call in thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn)

    def _row_to_entry(self, row: sqlite3.Row) -> KnowledgeEntry:
        d = dict(row)
        return KnowledgeEntry.from_dict(d)

    # ── StorageBackend implementation ─────────────────────────────────────

    async def write(self, entry: KnowledgeEntry) -> str:
        def _write():
            d = entry.to_dict()
            with closing(self._connect()) as conn:
                conn.execute("""
                    INSERT INTO knowledge_entries (
                        entry_id, layer, content, summary, importance, confidence,
                        truth_status, trust_score, source, worker_id, workflow_id,
                        derived_from, supports, contradicts, supersedes,
                        graph_node_id, tags, metadata, procedure_name,
                        created_at, updated_at, accessed_at, access_count
                    ) VALUES (
                        :entry_id, :layer, :content, :summary, :importance, :confidence,
                        :truth_status, :trust_score, :source, :worker_id, :workflow_id,
                        :derived_from, :supports, :contradicts, :supersedes,
                        :graph_node_id, :tags, :metadata, :procedure_name,
                        :created_at, :updated_at, :accessed_at, :access_count
                    )
                    ON CONFLICT(entry_id) DO UPDATE SET
                        layer=excluded.layer, content=excluded.content,
                        summary=excluded.summary, importance=excluded.importance,
                        confidence=excluded.confidence, truth_status=excluded.truth_status,
                        trust_score=excluded.trust_score, source=excluded.source,
                        worker_id=excluded.worker_id, workflow_id=excluded.workflow_id,
                        derived_from=excluded.derived_from, supports=excluded.supports,
                        contradicts=excluded.contradicts, supersedes=excluded.supersedes,
                        graph_node_id=excluded.graph_node_id, tags=excluded.tags,
                        metadata=excluded.metadata, procedure_name=excluded.procedure_name,
                        updated_at=excluded.updated_at, accessed_at=excluded.accessed_at,
                        access_count=excluded.access_count
                """, d)
                conn.commit()
            return d["entry_id"]
        return await self._run(_write)

    async def read(self, entry_id: str) -> Optional[KnowledgeEntry]:
        def _read():
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT * FROM knowledge_entries WHERE entry_id=?",
                    (entry_id,)
                ).fetchone()
                if row:
                    # Bump access stats
                    conn.execute(
                        "UPDATE knowledge_entries "
                        "SET accessed_at=?, access_count=access_count+1 "
                        "WHERE entry_id=?",
                        (time.time(), entry_id)
                    )
                    conn.commit()
                return row
        row = await self._run(_read)
        return self._row_to_entry(row) if row else None

    async def update(self, entry_id: str, delta: Dict[str, Any]) -> bool:
        """Partial update. delta keys must be valid column names."""
        allowed = {
            "importance", "confidence", "truth_status", "summary",
            "graph_node_id", "tags", "metadata", "layer",
            "supports", "contradicts", "supersedes", "procedure_name",
        }
        safe = {k: (json.dumps(v) if isinstance(v, (list, dict)) else v)
                for k, v in delta.items() if k in allowed}
        if not safe:
            return False
        safe["updated_at"] = time.time()
        safe["entry_id"] = entry_id
        cols = ", ".join(f"{k}=:{k}" for k in safe if k != "entry_id")

        def _update():
            with closing(self._connect()) as conn:
                cur = conn.execute(
                    f"UPDATE knowledge_entries SET {cols} WHERE entry_id=:entry_id",
                    safe
                )
                conn.commit()
                return cur.rowcount > 0
        return await self._run(_update)

    async def delete(self, entry_id: str) -> bool:
        def _delete():
            with closing(self._connect()) as conn:
                cur = conn.execute(
                    "DELETE FROM knowledge_entries WHERE entry_id=?", (entry_id,)
                )
                conn.commit()
                return cur.rowcount > 0
        return await self._run(_delete)

    async def search_text(self, query: str, limit: int = 10,
                           layer: Optional[str] = None,
                           min_importance: float = 0.0,
                           truth_status: Optional[str] = None
                           ) -> List[KnowledgeEntry]:
        def _search():
            with closing(self._connect()) as conn:
                if query.strip():
                    # FTS5 match via rowid join
                    sql = """
                        SELECT ke.* FROM knowledge_entries ke
                        JOIN knowledge_entries_fts fts
                          ON ke.rowid = fts.rowid
                        WHERE fts.knowledge_entries_fts MATCH ?
                          AND ke.importance >= ?
                          AND ke.truth_status != 'deprecated'
                    """
                    params: list = [
                        self._fts_escape(query), min_importance
                    ]
                else:
                    sql = """
                        SELECT * FROM knowledge_entries
                        WHERE importance >= ?
                          AND truth_status != 'deprecated'
                    """
                    params = [min_importance]

                if layer:
                    sql += " AND ke.layer=?" if "JOIN" in sql else " AND layer=?"
                    params.append(layer)
                if truth_status:
                    sql += " AND ke.truth_status=?" if "JOIN" in sql else " AND truth_status=?"
                    params.append(truth_status)

                sql += " ORDER BY ke.importance DESC" if "JOIN" in sql else " ORDER BY importance DESC"
                sql += f" LIMIT {int(limit)}"

                return conn.execute(sql, params).fetchall()

        rows = await self._run(_search)
        return [self._row_to_entry(r) for r in rows]

    async def get_by_layer(self, layer: str, limit: int = 100,
                            min_importance: float = 0.0) -> List[KnowledgeEntry]:
        def _get():
            with closing(self._connect()) as conn:
                return conn.execute(
                    "SELECT * FROM knowledge_entries "
                    "WHERE layer=? AND importance>=? AND truth_status!='deprecated' "
                    "ORDER BY importance DESC LIMIT ?",
                    (layer, min_importance, limit)
                ).fetchall()
        rows = await self._run(_get)
        return [self._row_to_entry(r) for r in rows]

    async def get_by_truth_status(self, truth_status: str,
                                   limit: int = 100) -> List[KnowledgeEntry]:
        def _get():
            with closing(self._connect()) as conn:
                return conn.execute(
                    "SELECT * FROM knowledge_entries WHERE truth_status=? "
                    "ORDER BY importance DESC LIMIT ?",
                    (truth_status, limit)
                ).fetchall()
        rows = await self._run(_get)
        return [self._row_to_entry(r) for r in rows]

    async def count(self, layer: Optional[str] = None) -> int:
        def _count():
            with closing(self._connect()) as conn:
                if layer:
                    return conn.execute(
                        "SELECT COUNT(*) FROM knowledge_entries WHERE layer=?",
                        (layer,)
                    ).fetchone()[0]
                return conn.execute(
                    "SELECT COUNT(*) FROM knowledge_entries"
                ).fetchone()[0]
        return await self._run(_count)

    async def stats(self) -> Dict[str, Any]:
        def _stats():
            with closing(self._connect()) as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM knowledge_entries"
                ).fetchone()[0]
                by_layer = {
                    row[0]: row[1]
                    for row in conn.execute(
                        "SELECT layer, COUNT(*) FROM knowledge_entries GROUP BY layer"
                    ).fetchall()
                }
                by_truth = {
                    row[0]: row[1]
                    for row in conn.execute(
                        "SELECT truth_status, COUNT(*) FROM knowledge_entries "
                        "GROUP BY truth_status"
                    ).fetchall()
                }
            return {
                "backend": "SQLiteStorageBackend",
                "db_path": self.db_path,
                "total": total,
                "by_layer": by_layer,
                "by_truth_status": by_truth,
            }
        return await self._run(_stats)

    @staticmethod
    def _fts_escape(query: str) -> str:
        """Escape FTS5 special chars to prevent query parse errors."""
        special = {'"', "'", '(', ')', '*', '^', ':', '-', '+'}
        tokens = []
        for word in query.split():
            if any(c in word for c in special):
                tokens.append(f'"{word}"')
            else:
                tokens.append(word)
        return " ".join(tokens) if tokens else '""'
