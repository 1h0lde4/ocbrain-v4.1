"""
core/memory/backends/sqlite_storage.py — SQLiteStorageBackend (L1 Episodic)

Implements StorageBackend via SQLite WAL + FTS5.
All blocking sqlite3 calls run in asyncio.get_event_loop().run_in_executor()
to avoid event loop starvation (§5, Issue 9 pattern).

Schema: knowledge_entries + knowledge_entries_fts (virtual, FTS5)
FTS5 triggers keep the virtual table in sync automatically.

Rev 3 (OCBrain G4-FTS remediation) construction contract — Amendment 2:
  * Normal startup is VALIDATION-ONLY. The constructor never mutates a
    pre-existing database and never runs a trigger migration or an FTS
    rebuild; a legacy or unrecognized database refuses readiness and points
    the operator at the dedicated maintenance command
    (`ocbrain memory-migrate`).
  * A fresh (absent) database is initialized to the canonical contract and
    ows its own per-database migration ledger (Amendment 7).
  * The SQLite WAL runtime compatibility gate (Amendment 1) is evaluated at
    construction; unsupported runtimes cannot report full memory readiness
    and are refused outright under the default `enforce` mode.
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
from core.memory.sqlite_contract import MemoryReadinessError
from core.memory.sqlite_integrity import (
    run_full_integrity_validation,
    validate_readiness,
    verify_content_row_identity,
)
from core.memory.sqlite_migration import (
    initialize_schema,
    inspect_migration_state,
)
from core.memory.sqlite_runtime import (
    GATE_ACKNOWLEDGE,
    GATE_ENFORCE,
    GATE_ENV_VAR,
    MemoryRuntimeCompatibilityError,
    RuntimeDecision,
    classify_wal_safety,
    load_configured_vendor_provenance,
    resolve_gate_mode,
)

logger = logging.getLogger("ocbrain.memory.backends.sqlite_storage")

DEFAULT_DB_PATH = ".data/memory/unified.db"


def _resolve_configured_gate_mode() -> str:
    """
    Gate-mode resolution for normal application startup (no explicit
    `runtime_gate` constructor argument):

      1. OCBRAIN_MEMORY_RUNTIME_ACK as documented — set to "acknowledge"
         (explicit operator exception) or unset; any other value raises
         through resolve_gate_mode.
      2. config/settings.toml → [memory] wal_gate_mode — "enforce" (default)
         or "acknowledge". An unrecognised value FAILS CLOSED to "enforce"
         with a logged error (Amendment 1 §D: a typo must never silently
         downgrade the gate).
    """
    env_value = os.environ.get(GATE_ENV_VAR)
    if env_value not in (None, ""):
        return resolve_gate_mode(env_value)
    try:
        from core.config import config as app_config
    except Exception:
        return GATE_ENFORCE
    cfg_value = app_config.get("memory.wal_gate_mode")
    if cfg_value in (None, ""):
        return GATE_ENFORCE
    try:
        return resolve_gate_mode(str(cfg_value))
    except ValueError:
        logger.error(
            "[Rev3 Amendment 1] settings.toml [memory] wal_gate_mode=%r is "
            "not 'enforce' or 'acknowledge' — failing closed to 'enforce'.",
            cfg_value)
        return GATE_ENFORCE


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

    def __init__(self, db_path: str = DEFAULT_DB_PATH,
                 *, runtime_gate: Optional[str] = None):
        """
        Opens the database under the Rev 3 readiness contract.

        Args:
            db_path: the database file for this backend.
            runtime_gate: "enforce" (default) refuses construction on an
                affected SQLite runtime; "acknowledge" constructs but every
                readiness report honestly reports the runtime as not fully
                supported (never "full readiness" — Amendment 1 §D). When
                None, the OCBRAIN_MEMORY_RUNTIME_ACK environment variable may
                set "acknowledge" explicitly.
        """
        self.db_path = str(Path(db_path).resolve())
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Amendment 1 — runtime compatibility gate (fail closed).
        self.runtime_gate_mode = (
            resolve_gate_mode(runtime_gate)
            if runtime_gate is not None
            else _resolve_configured_gate_mode()
        )
        self.runtime_verdict: RuntimeDecision = classify_wal_safety(
            approved_vendor_builds=load_configured_vendor_provenance()
        )
        if not self.runtime_verdict.wal_safe:
            finding = (
                f"[Rev3 Amendment 1] SQLite runtime {self.runtime_verdict.inventory.get('sqlite_version_sql')} "
                f"(source: {self.runtime_verdict.inventory.get('sqlite_source_id')}) "
                f"is not safe for multi-connection WAL use: {self.runtime_verdict.reason}"
            )
            if self.runtime_gate_mode == GATE_ACKNOWLEDGE:
                logger.warning(
                    "%s | acknowledged: construction proceeds, readiness is "
                    "NOT reported as full; remediation plan: %s",
                    finding, self.runtime_verdict.remediation)
            else:
                logger.error("%s", finding)
                raise MemoryRuntimeCompatibilityError(self.runtime_verdict)

        # Amendment 2 — validation-only construction.
        self.readiness_state: Dict[str, Any] = {}
        self.last_full_validation: Optional[Dict[str, Any]] = None
        self._init_or_validate_sync()
        logger.info(
            "SQLiteStorageBackend ready: %s (readiness=%s runtime=%s state=%s)",
            self.db_path, self.readiness_state.get("status"),
            self.runtime_verdict.decision,
            self.readiness_state.get("migration_state"),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_or_validate_sync(self) -> None:
        """
        Amendment 2 §B — normal application startup:
          1. opens the configured database using the supported connection
             configuration,
          2. performs validation-only migration-state checks,
          3. verifies the required schema and migration marker,
          4. verifies runtime compatibility (done above),
          5. refuses memory readiness when migration is missing, incompatible,
             incomplete or unsupported.

        A file with no application tables is *initialized* to the canonical
        contract (with its own per-database migration ledger); anything that
        already exists is never mutated here — legacy databases are handed to
        the maintenance migration command instead of silently fixed.
        """
        with closing(self._connect()) as conn:
            state = inspect_migration_state(conn)
            if state.state == "absent":
                initialize_schema(conn)
                state = inspect_migration_state(conn)
            if state.state != "current":
                raise MemoryReadinessError(
                    {
                        "kind": "memory_migration_state",
                        "database": self.db_path,
                        **state.finding,
                    },
                    state.remediation)
            validation = validate_readiness(conn)
            if not validation["passed"]:
                raise MemoryReadinessError(
                    {
                        "kind": "memory_schema_validation",
                        "database": self.db_path,
                        "reason": "; ".join(
                            f"{c['name']}: {c['detail']}"
                            for c in validation["checks"]
                            if c["status"] in ("fail", "error")),
                        "checks": validation["checks"],
                    },
                    "run the dedicated maintenance operation in a maintenance "
                    "window (stop all processes using this database first): "
                    f"`ocbrain memory-migrate --db {self.db_path}`")

            runtime_ready = self.runtime_verdict.wal_safe
            readiness_status = "ready" if runtime_ready else (
                "ready_degraded_runtime_not_supported")
            self.readiness_state = {
                "status": readiness_status,
                "memory_ready": bool(runtime_ready),
                "database": self.db_path,
                "migration_state": state.state,
                "runtime_gate_mode": self.runtime_gate_mode,
                "runtime": {
                    "decision": self.runtime_verdict.decision,
                    "wal_safe": self.runtime_verdict.wal_safe,
                    "affected_by_wal_reset_bug":
                        self.runtime_verdict.affected_by_wal_reset_bug,
                    "full_wal_support": self.runtime_verdict.full_wal_support,
                    "reason": self.runtime_verdict.reason,
                    "remediation": self.runtime_verdict.remediation,
                    "sqlite_version_sql":
                        self.runtime_verdict.inventory.get("sqlite_version_sql"),
                    "sqlite_source_id":
                        self.runtime_verdict.inventory.get("sqlite_source_id"),
                },
                "validation_summary": validation["summary"],
                "validation_cost_s": validation["total_cost_s"],
                "verified_at": validation["verified_at"],
                "validation_only_startup": True,
            }

    # ── Health / explicit verification (Amendment 3 §C) ──────────────────

    def health_report(self) -> Dict[str, Any]:
        """
        Ordinary health heartbeat input: the readiness state recorded at
        construction plus the last explicit full validation, if any.

        Whole-database integrity validation is NOT run here (Amendment 3 §C:
        per-heartbeat full validation is prohibited); use
        verify_integrity_now() for an explicit verification and to measure
        its cost.
        """
        report: Dict[str, Any] = {
            "backend": "SQLiteStorageBackend",
            "db_path": self.db_path,
            "readiness": dict(self.readiness_state),
        }
        if self.last_full_validation is not None:
            report["last_full_validation"] = {
                k: v for k, v in self.last_full_validation.items()
                if k != "finding_objects"
            }
        return report

    async def verify_integrity_now(
        self,
        retrieval_tokens: Optional[List[tuple]] = None,
    ) -> Dict[str, Any]:
        """
        Explicit (operator-requested) whole-database validation, with measured
        cost. Runs structural, foreign-key, FTS and retrieval checks as
        independent scoped findings and records the result on the instance.
        """
        tokens = retrieval_tokens or []

        def _verify():
            with closing(self._connect()) as conn:
                result = run_full_integrity_validation(conn, retrieval_tokens=tokens)
            identity = None
            with closing(self._connect()) as conn:
                identity = verify_content_row_identity(conn)
            return {
                "integrity": result,
                "content_row_identity": {
                    "passed": identity["passed"],
                    "open_risk_classified": identity.get("open_risk_classified"),
                    "checks": [f.as_dict() for f in identity["checks"]],
                },
            }

        outcome = await self._run(_verify)
        outcome["integrity"].pop("finding_objects", None)
        self.last_full_validation = {
            "verified_at": outcome["integrity"]["verified_at"],
            "passed": outcome["integrity"]["passed"],
            "total_cost_s": outcome["integrity"]["total_cost_s"],
            "findings": outcome["integrity"]["findings"],
        }
        return outcome

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
                "readiness_status": self.readiness_state.get("status"),
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
