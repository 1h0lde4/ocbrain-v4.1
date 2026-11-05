"""
core/memory/sqlite_migration.py — Memory-database migration lifecycle (Rev 3)

Rev 3 Amendment 2 separates three things that Rev 2 (Session 4C) had fused
inside `SQLiteStorageBackend._init_sync()`:

  1. Migration execution — ONLY here, via `run_maintenance_migration()`
     (exposed as the `ocbrain memory-migrate` CLI command), in a maintenance
     window.
  2. Migration-state verification — `inspect_migration_state()` /
     `read_migration_ledger()`, validation-only, no schema mutation.
  3. Memory-service readiness — the storage-backend constructor refuses
     readiness when migration is missing, incomplete, incompatible or
     unsupported; normal startup never mutates an existing database and never
     runs a rebuild (Amendment 2 §B).

Why the separation (Amendment 2 §C): a successful migration does not stop an
*old* application process from resuming writes with the defective write path
afterwards. The deployment contract in the report (and in the CLI command's
own help) therefore requires stopping/draining all processes, running the
maintenance migration, verifying its committed result, and only then starting
the new application version. Process fencing is NOT claimed here (Amendment
2 §D: otherwise explicitly out of scope until a real, tested protocol ships).

Concurrency protection for two independent migrators (Amendment 2 §E): an
advisory lock file plus `BEGIN IMMEDIATE`; the winner must RE-READ the
ledger after acquiring the write lock and must not repeat an already
committed migration.

A large rebuild can grow the WAL and need substantial free space: the runner
estimates and reports requirements from representative measurements
(Amendment 11), never deleting database/WAL/SHM files, and reports success
only after the commit succeeds (Amendment 2 §B.9).
"""

from __future__ import annotations

import getpass
import json
import logging
import os
import platform
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.memory.sqlite_contract import (
    CANONICAL_INDEX_DDL,
    CANONICAL_SCHEMA_STATEMENTS,
    CANONICAL_TRIGGER_DDL,
    CONTENT_TABLE,
    FTS_TABLE,
    META_SCHEMA_STATE,
    META_TABLE,
    MIGRATION_ID_V1,
    MIGRATION_NAME_V1,
    MIGRATIONS_TABLE,
    SCHEMA_STATE_FRESH_CURRENT,
    SCHEMA_STATE_MIGRATED,
    SCHEMA_STATES_CURRENT,
    trigger_audit_classification,
)
from core.memory.sqlite_integrity import (
    check_foreign_key_integrity,
    check_structural_integrity,
    read_fts_configuration,
    run_full_integrity_validation,
    verify_content_row_identity,
    audit_trigger_contract,
)
from core.memory.sqlite_runtime import (
    collect_connection_inventory,
    collect_runtime_inventory,
)

logger = logging.getLogger("ocbrain.memory.sqlite_migration")

# Representative disk-space factor for the maintenance window (Amendment 11).
# Measured in tests/test_g4_rev3_failure_recovery.py against representative
# synthetic content: WAL growth + FTS rebuild can worst-case approach ~2x the
# content table's bytes. This is an ESTIMATE for pre-flight reporting only —
# never a guarantee of required space.
REPRESENTATIVE_SPACE_FACTOR = 2.0

# Explicit checkpoint operations in the codebase (Amendment 10 inventory).
# Static table audited against the source: `grep wal_checkpoint core/`.
EXPLICIT_CHECKPOINT_SITES = [
    {
        "location": "core/runtime/state.py",
        "database": ".data/runtime_state.sqlite (runtime state store)",
        "operation": "PRAGMA wal_checkpoint(TRUNCATE)",
        "purpose": ("fold the small state DB's WAL back after "
                    "read-modify-write repair paths"),
        "owns_memory_db": False,
    },
    {
        "location": "core/memory/sqlite_migration.py",
        "database": "the memory DB under migration",
        "operation": "PRAGMA wal_checkpoint(TRUNCATE) after the maintenance commit",
        "purpose": ("close out the migration's WAL growth inside the "
                    "maintenance window (single-writer, verified quiescence)"),
        "owns_memory_db": True,
    },
]
# The memory backends (sqlite_storage / sqlite_archive / graph_engine) do NOT
# run explicit checkpoints; automatic checkpointing (default
# wal_autocheckpoint=1000 pages per connection) is left untouched — no global
# policy change is authorized by this remediation (Amendment 10).

MIGRATION_LOCK_SUFFIX = ".ocbrain_migrate.lock"


# ── Read-only inspection (lifecycle phase 2) ────────────────────────────────

@dataclass
class MigrationStateResult:
    state: str            # absent | current | legacy_pending_migration | invalid
    finding: Dict[str, Any] = field(default_factory=dict)
    remediation: str = ""

    @property
    def is_ready_modal(self) -> bool:
        return self.state == "current"


def inspect_migration_state(conn: sqlite3.Connection) -> MigrationStateResult:
    """
    Read-only migration-state inspection of ONE database (Amendment 2 §B.2;
    Amendment 7: every database is judged by its own tables — no process
    global flag).
    """
    try:
        tables = {str(n) for (n,) in conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='table'").fetchall()}
    except sqlite3.DatabaseError as exc:
        return MigrationStateResult(
            "invalid", {"reason": f"sqlite_schema unreadable: {exc}"},
            "database file may be corrupt: preserve it and investigate before "
            "running any migration")

    if not tables:
        return MigrationStateResult(
            "absent",
            {"reason": "no application tables — a fresh database will be "
                       "initialized to the canonical contract"},
            "")

    has_content = CONTENT_TABLE in tables
    has_meta = META_TABLE in tables
    has_ledger = MIGRATIONS_TABLE in tables

    if not has_content and not has_meta and not has_ledger:
        # Unknown non-application content already occupies this file.
        return MigrationStateResult(
            "invalid",
            {"reason": f"file contains unrelated tables {sorted(tables)}; "
                       "initializing into it is not authorized"},
            "use a different database path after inspecting this file")

    if has_content and not has_meta:
        # Recognize legacy shapes only; anything unknown also fails closed.
        trig = audit_trigger_contract(conn)
        fts_cfg = read_fts_configuration(conn)
        if (trig["classification"] in ("canonical", "legacy_compatible")
                and fts_cfg.get("classification") == "canonical"):
            return MigrationStateResult(
                "legacy_pending_migration",
                {"reason": (
                    "pre-Rev3 database: recognized legacy/canonical trigger "
                    "state, but this database has no Rev 3 migration ledger "
                    "record; no validated rebuild/integrity run exists"),
                 "trigger_contract": trig["classification"]},
                ("stop all processes using this database, then run: "
                 "ocbrain memory-migrate --db <path>"))
        return MigrationStateResult(
            "invalid",
            {"reason": "unrecognized pre-Rev3 schema (trigger contract: "
                       f"{trig['classification']}, FTS configuration: "
                       f"{fts_cfg.get('classification')})"},
            "do not auto-migrate an unrecognized schema: inspect manually, "
            "then apply the maintenance migration explicitly")

    if has_meta and has_ledger:
        mark = conn.execute(
            f"SELECT value FROM {META_TABLE} WHERE key=?", (META_SCHEMA_STATE,)
        ).fetchone()
        applied = conn.execute(
            f"SELECT COUNT(*) FROM {MIGRATIONS_TABLE} WHERE migration_id=? "
            "AND status='applied'", (MIGRATION_ID_V1,)).fetchone()[0]
        if mark and str(mark[0]) in SCHEMA_STATES_CURRENT and bool(applied):
            return MigrationStateResult(
                "current", {"reason": f"schema_state={mark[0]!r}, migration "
                                       f"{MIGRATION_ID_V1} recorded applied"})
        if mark and str(mark[0]) in SCHEMA_STATES_CURRENT and not applied:
            return MigrationStateResult(
                "invalid",
                {"reason": ("meta marker says current but the migration "
                            "ledger has no applied record — inconsistent "
                            "per-database state")},
                "run ocbrain memory-migrate --db <path> to re-establish a "
                "consistent ledger (idempotent)")
        return MigrationStateResult(
            "legacy_pending_migration",
            {"reason": f"meta marker present but not current: {mark!r}"},
            "run ocbrain memory-migrate --db <path>")

    return MigrationStateResult(
        "invalid",
        {"reason": f"unexpected table set: {sorted(tables)}"},
        "inspect manually before running the maintenance migration")


def read_migration_ledger(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Per-database ledger rows (Amendment 7 §4)."""
    out: List[Dict[str, Any]] = []
    try:
        rows = conn.execute(
            "SELECT migration_id, name, status, started_at, completed_at, "
            "applied_by, host_os, wal_bytes_before, wal_bytes_after "
            f"FROM {MIGRATIONS_TABLE} ORDER BY completed_at").fetchall()
    except sqlite3.Error:
        return out
    for row in rows:
        out.append({
            "migration_id": row[0], "name": row[1], "status": row[2],
            "started_at": row[3], "completed_at": row[4],
            "applied_by": row[5], "host_os": row[6],
            "wal_bytes_before": row[7], "wal_bytes_after": row[8],
        })
    return out


# ── Initialization (fresh databases only — never a legacy mutation) ─────────

def initialize_schema(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Create the canonical schema on an *absent* database and record the fresh
    initialization in this database's own ledger.

    Scope guard (Amendment 2 §F): construction may call this ONLY when
    inspection returned state == "absent". Any pre-existing database (even an
    empty file with junk tables) is refused to validation instead — or handed
    to the maintenance command through an explicit, reviewed path.

    Transaction safety: the connection is switched to autocommit mode
    (isolation_level=None) and wrapped in an explicit BEGIN IMMEDIATE, so
    schema creation + ledger row commit as ONE unit (executescript would
    otherwise commit any implicit transaction mid-script).
    """
    started = time.time()
    applied_by = _applied_by()
    pre = {"state": "absent",
           "runtime": collect_runtime_inventory()["sqlite3_sqlite_version"]}

    isolation = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        for statement in CANONICAL_SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.execute(
            f"INSERT INTO {META_TABLE}(key, value) VALUES (?, ?)",
            (META_SCHEMA_STATE, SCHEMA_STATE_FRESH_CURRENT))
        conn.execute(
            f"INSERT INTO {MIGRATIONS_TABLE}("
            "migration_id, name, status, started_at, completed_at, applied_by, "
            "host_os, pre_checks_json, post_checks_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (MIGRATION_ID_V1, MIGRATION_NAME_V1, "applied", started, time.time(),
             applied_by, platform.platform(),
             json.dumps(pre), json.dumps({"initialized": "fresh"})))
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.isolation_level = isolation
    return {"initialized": True, "applied_by": applied_by}


def _applied_by() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover
        user = "unknown"
    return f"{user}@{platform.node()} pid={os.getpid()}"


# ── Amendment 11 — free-space estimate (report, never a guarantee) ──────────

def estimate_migration_space(db_path: str) -> Dict[str, Any]:
    """
    Representative-measurement based estimate of the extra space the
    maintenance window can require, and the free space actually visible.

    Content table bytes are measured; the FTS rebuild + WAL growth envelope
    uses REPRESENTATIVE_SPACE_FACTOR measured on synthetic datasets. This is
    an estimate, never a guarantee; the resulting report is written into the
    ledger row's pre-checks.
    """
    page_size = page_count = freelist = None
    content_bytes = None
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            freelist = conn.execute("PRAGMA freelist_count").fetchone()[0]
            res = conn.execute(
                f"SELECT COALESCE(SUM(LENGTH(content) + LENGTH(COALESCE(summary, ''))), 0) "
                f"FROM {CONTENT_TABLE}").fetchone()
            content_bytes = int(res[0])
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {"error": str(exc)}
    db_bytes = (page_count * page_size) if page_size and page_count else None
    est_extra = (content_bytes * REPRESENTATIVE_SPACE_FACTOR
                 if content_bytes is not None else None)
    free_bytes = None
    try:
        free_bytes = shutil.disk_usage(os.path.dirname(os.path.abspath(db_path))).free
    except OSError:
        pass
    return {
        "db_bytes": db_bytes,
        "page_size": page_size,
        "page_count": page_count,
        "freelist_pages": freelist,
        "content_bytes_measured": content_bytes,
        "estimate_extra_bytes": est_extra,
        "estimate_basis": (
            f"content-table bytes x {REPRESENTATIVE_SPACE_FACTOR} "
            "representative measurement (WAL growth + FTS index rebuild); "
            "an estimate, NOT a guarantee (Amendment 11)"),
        "free_bytes": free_bytes,
        "sufficient_free_estimate": (
            bool(free_bytes and est_extra is not None
                 and free_bytes >= est_extra)),
    }


# ── Amendment 4 §D — snapshot-preserving backup (SQLite Online Backup API) ──

def create_online_backup(db_path: str, dest_path: str) -> Dict[str, Any]:
    """
    Prefer the SQLite Online Backup API for a consistent snapshot; it
    preserves hidden rowid identity, unlike VACUUM INTO, which is NOT
    interchangeable here (it compacts/remaps and its rowid behavior for
    tables without an INTEGER PRIMARY KEY is not a preservation guarantee —
    Amendment 4 §D). The verification step compares the identity mapping.
    """
    if os.path.exists(dest_path):
        return {"ok": False, "error": f"destination already exists: {dest_path}"}
    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(dest_path)
        try:
            src.backup(dst)
            mapping_src = src.execute(
                f"SELECT entry_id, rowid FROM {CONTENT_TABLE} "
                "ORDER BY entry_id").fetchall()
            mapping_dst = dst.execute(
                f"SELECT entry_id, rowid FROM {CONTENT_TABLE} "
                "ORDER BY entry_id").fetchall()
            identity_preserved = mapping_src == mapping_dst
        finally:
            dst.close()
    finally:
        src.close()
    return {
        "ok": identity_preserved,
        "identities_compared": len(mapping_src),
        "identity_preserved": identity_preserved,
        "method": "sqlite3.Connection.backup (Online Backup API)",
        "note": ("VACUUM INTO is not used for backups: with hidden-rowid "
                 "documents, only an explicit identity verification like this "
                 "one — or the Online Backup API — may be relied on"),
    }


# ── Amendment 10 — checkpoint & WAL operational inventory ───────────────────

def collect_checkpoint_inventory(db_path: str) -> Dict[str, Any]:
    """Amendment 10: the explicit operational checkpoint/WAL report."""
    inv: Dict[str, Any] = {
        "explicit_checkpoint_sites": EXPLICIT_CHECKPOINT_SITES,
        "automatic_checkpointing": (
            "enabled; every memory-backend connection keeps SQLite's default "
            "wal_autocheckpoint=1000 pages — no global change is authorized "
            "by the FTS remediation"),
        "checkpoint_scheduling_owner": (
            "automatic: per-connection SQLite autocheckpoint; explicit: the "
            "maintenance runner's post-commit TRUNCATE checkpoint (and the "
            "unrelated runtime-state repair paths in core/runtime/state.py)"),
        "multiple_processes_can_initiate": (
            "yes for automatic checkpoints (any writer connection); the "
            "maintenance TRUNCATE checkpoint runs only in the maintenance "
            "window after the quiescence gate"),
        "readers_preventing_completion": (
            "a TRUNCATE/PASSIVE checkpoint fails to free the WAL (busy) when "
            "readers/writers hold it; SQLite then retries automatically on "
            "later checkpoints; the runner records busy=1 honestly and never "
            "forces readers out"),
        "wal_monitoring": (
            "WAL file sizes are reported here and in maintenance results; no "
            "continuous -wal wake-up polling exists by design"),
    }
    for suffix, key in (("", "db_bytes"), ("-wal", "wal_bytes"), ("-shm", "shm_bytes")):
        path = str(db_path) + suffix
        try:
            inv[key] = os.path.getsize(path)
        except OSError:
            inv[key] = None
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            inv["connection_facts"] = collect_connection_inventory(conn)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        inv["connection_facts"] = {"error": str(exc)}
    return inv


# ── Amendment 2 §B — the maintenance runner ─────────────────────────────────

@dataclass
class MaintenanceReport:
    db_path: str
    outcome: str                       # migrated | already_applied | failed | preserved_corrupt
    steps: List[Dict[str, Any]] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)
    ledger_row: Dict[str, Any] = field(default_factory=dict)
    space_estimate: Dict[str, Any] = field(default_factory=dict)
    wal_bytes_before: Optional[int] = None
    wal_bytes_after: Optional[int] = None
    checkpoint: Dict[str, Any] = field(default_factory=dict)
    failure: Optional[str] = None
    remediation: str = ""
    preserved_files: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def run_maintenance_migration(
    db_path: str,
    *,
    fault_injection: Optional[Callable[[str], None]] = None,
    run_final_checkpoint: bool = True,
    busy_timeout_ms: int = 20000,
) -> MaintenanceReport:
    """
    The dedicated maintenance migration (Amendment 2 §B) for ONE database.

    Sequence (Amendment 2 §B + Amendment 3 §B):
      1. quiescence: the caller must have stopped/drained all processes using
         this database; an advisory lock file is taken on top of SQLite's own
         write lock,
      2. whole-database structural integrity BEFORE touching a legacy
         database — corruption stops everything and the database is
         preserved for recovery (nothing is "repaired" by an FTS rebuild),
      3. acquire migration serialization (advisory lock + BEGIN IMMEDIATE),
      4. RE-read the migration state after acquiring the lock (Am. §E),
      5. apply the migration (canonical triggers; FTS external-content
         rebuild),
      6. verify: content-row identity, FTS integrity, retrieval, whole-
         database structural check, FK re-check (Amendment 3 §B.5–7),
      7. record the migration in THIS database's ledger,
      8. commit — success is reported only after the commit succeeds
         (Amendment 2 §B.9),
      9. optional post-commit TRUNCATE checkpoint (recorded honestly).

    `fault_injection` is a TEST hook: if provided, it is called with the step
    name before critical steps so tests can raise controlled faults (e.g. a
    SQLITE_FULL equivalent). Production callers never set it.
    """
    report = MaintenanceReport(db_path=db_path, outcome="failed")
    lock_path = str(db_path) + MIGRATION_LOCK_SUFFIX
    lock_fd: Optional[int] = None
    _prepared_already_applied = False

    def _step(name: str, status: str, detail: str = "") -> None:
        report.steps.append({"step": name, "status": status, "detail": detail})
        logger.info("[memory-migrate] %s (%s)%s", name, status,
                    f" {detail}" if detail else "")

    def _fault(step_name: str) -> None:
        if fault_injection is not None:
            _step("fault_injection", "invoked", f"step={step_name}")
            fault_injection(step_name)

    conn: Optional[sqlite3.Connection] = None
    try:
        _fault("pre_flight")
        report.space_estimate = estimate_migration_space(db_path)
        _step("space_estimate", "measured",
              json.dumps({k: report.space_estimate.get(k)
                          for k in ("estimate_extra_bytes", "free_bytes",
                                    "estimate_basis")}, default=str))

        report.wal_bytes_before = _wal_size(db_path)

        # Whole-database structural integrity BEFORE modifying a recognized
        # legacy database (Amendment 3 §B.1). Plain connection, no txn.
        pre_conn = sqlite3.connect(str(db_path), timeout=busy_timeout_ms / 1000.0)
        try:
            structural = check_structural_integrity(pre_conn)
            report.steps.append({"step": "pre_integrity_check",
                                 "status": structural.status,
                                 "detail": structural.detail})
            if structural.status != "pass":
                # Amendment 3 §B.2: stop, preserve, do NOT conceal via rebuild.
                report.outcome = "preserved_corrupt"
                report.failure = (
                    f"whole-database structural corruption detected before "
                    f"migration: {structural.detail}")
                report.remediation = (
                    "database preserved untouched; do not delete or repair "
                    "files in place; investigate recovery from the preserved "
                    "copy before any migration attempt")
                report.preserved_files = _preserve_corrupt_database(
                    db_path, structural.detail)
                return report
            foreign_pre = check_foreign_key_integrity(pre_conn)
            report.steps.append({"step": "pre_foreign_key_check",
                                 "status": foreign_pre.status,
                                 "detail": foreign_pre.detail})
            report.verification["pre_integrity"] = structural.as_dict()
            report.verification["pre_foreign_keys"] = foreign_pre.as_dict()
        finally:
            pre_conn.close()

        # Advisory maintenance lock (serialized independent migrators).
        lock_fd = _acquire_lock_file(lock_path)
        _step("maintenance_lock", "acquired", os.path.basename(lock_path))

        conn = sqlite3.connect(str(db_path), timeout=busy_timeout_ms / 1000.0)
        conn.isolation_level = None          # manual txn control (see below)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        conn.row_factory = sqlite3.Row

        # Amendment 2 §B.2: acquire migration serialization.
        conn.execute("BEGIN IMMEDIATE")
        _step("migration_lock", "acquired", "BEGIN IMMEDIATE")

        # Amendment 2 §B.3/§E: re-read the migration state AFTER acquiring the
        # lock — a pre-lock state inspection is not trusted.
        state = inspect_migration_state(conn)
        report.steps.append({"step": "re_read_migration_state",
                             "status": state.state,
                             "detail": state.finding.get("reason", "")})
        if state.state == "current":
            # An independent migrator already committed this migration while
            # we were waiting — do NOT repeat it.
            conn.execute("ROLLBACK")
            _step("migration", "skipped",
                  "ledger shows this migration already applied (re-read "
                  "after lock)")
            report.outcome = "already_applied"
            _prepared_already_applied = True
            return report
        if state.state not in ("legacy_pending_migration", "absent"):
            conn.execute("ROLLBACK")
            report.outcome = "failed"
            report.failure = (
                f"refusing migration in state={state.state!r}: "
                f"{state.finding.get('reason', '')}"
            )
            report.remediation = state.remediation
            return report

        _fault("apply")

        # Apply: canonical trigger set (replace anything non-canonical).
        replaced: List[str] = []
        for name in ("ke_ai", "ke_au", "ke_ad"):
            row = conn.execute(
                "SELECT sql FROM sqlite_schema WHERE type='trigger' AND name=?",
                (name,)).fetchone()
            current_sql = str(row[0]) if row is not None else ""
            if current_sql and trigger_audit_classification(
                    current_sql, name) == "canonical":
                continue
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
            conn.execute(CANONICAL_TRIGGER_DDL[name])
            replaced.append(name)
        _step("replace_triggers", "ok",
              f"replaced={replaced or 'none (already canonical)'}")

        # Ensure the canonical supporting indexes exist (a recognized legacy
        # database may predate some of them; creating them is additive and
        # part of restoring the complete canonical contract).
        index_names = {str(n) for (n,) in conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='index' AND tbl_name=?",
            (CONTENT_TABLE,)).fetchall()}
        created_idx = [n for n in CANONICAL_INDEX_DDL if n not in index_names]
        for name in created_idx:
            conn.execute(CANONICAL_INDEX_DDL[name])
        _step("ensure_indexes", "ok",
              f"created={created_idx or 'none (already canonical)'}")

        # FTS external-content rebuild from the content table.
        _fault("rebuild")
        conn.execute(f"INSERT INTO {FTS_TABLE}({FTS_TABLE}) VALUES ('rebuild')")
        _step("fts_rebuild", "ok")

        _fault("verify")

        # Verify: content-row identity + FTS + whole-database integrity + FK.
        identity = verify_content_row_identity(conn)
        report.verification["content_row_identity"] = {
            "passed": identity["passed"],
            "checks": [f.as_dict() for f in identity["checks"]],
        }
        if not identity["passed"]:
            raise RuntimeError(
                "content-row identity verification failed: "
                + "; ".join(f"{f.name}: {f.detail}"
                            for f in identity["checks"]
                            if f.status in ("fail", "error")))

        full = run_full_integrity_validation(conn)
        report.verification["post_integrity"] = full
        if not full["passed"]:
            raise RuntimeError(
                "post-migration integrity validation failed: "
                + "; ".join(
                    f"{f.scope}/{f.name}: {f.detail}"
                    for f in full["finding_objects"]
                    if f.status in ("fail", "error")))
        _step("verification", "ok", f"total_cost_s={full['total_cost_s']}")

        # Record the migration in THIS database's ledger.
        _fault("record")
        if not _table_exists(conn, META_TABLE):
            # Legacy state normally lacks the housekeeping tables; they are
            # part of the canonical contract (per-database ledger, Am. 7).
            for statement in CANONICAL_SCHEMA_STATEMENTS:
                if statement.startswith("CREATE TABLE IF NOT EXISTS _ocbrain_"):
                    conn.execute(statement)
        mark = conn.execute(
            f"SELECT value FROM {META_TABLE} WHERE key=?",
            (META_SCHEMA_STATE,)).fetchone()
        if mark is None:
            conn.execute(
                f"INSERT INTO {META_TABLE}(key, value) VALUES (?, ?)",
                (META_SCHEMA_STATE, SCHEMA_STATE_MIGRATED))
        else:
            conn.execute(
                f"UPDATE {META_TABLE} SET value=? WHERE key=?",
                (SCHEMA_STATE_MIGRATED, META_SCHEMA_STATE))
        wal_at_record = _wal_size(db_path)
        conn.execute(
            f"INSERT INTO {MIGRATIONS_TABLE}(migration_id, name, status, "
            "started_at, completed_at, applied_by, host_os, pre_checks_json, "
            "post_checks_json, wal_bytes_before, wal_bytes_after) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (MIGRATION_ID_V1, MIGRATION_NAME_V1, "applied",
             time.time(), time.time(), _applied_by(), platform.platform(),
             json.dumps({"space": report.space_estimate,
                         "pre_integrity": report.verification.get("pre_integrity"),
                         "pre_foreign_keys": report.verification.get("pre_foreign_keys")},
                        default=str),
             json.dumps(report.verification, default=str),
             report.wal_bytes_before, wal_at_record))
        _step("record_migration", "ok")

        # Commit. Success is reported only after the commit succeeds.
        _fault("commit")
        conn.execute("COMMIT")
        _step("commit", "ok")
        report.outcome = "migrated"

        if run_final_checkpoint:
            _fault("checkpoint")
            busy, log_pages, ck_pages = conn.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            report.checkpoint = {
                "operation": "PRAGMA wal_checkpoint(TRUNCATE)",
                "busy": busy, "wal_frames": log_pages,
                "checkpointed_frames": ck_pages,
                "note": ("busy=1 would mean readers blocked the truncation; "
                         "recorded honestly, never forced"),
            }
            _step("final_checkpoint", "done",
                  f"busy={busy} checkpointed={ck_pages}")
        # WAL growth measurement taken while the connection is still open (a
        # closed WAL connection legitimately removes the -wal file).
        report.wal_bytes_after = _wal_size(db_path)
        _step("wal_measurement", "measured",
              f"before={report.wal_bytes_before} after={report.wal_bytes_after}")
        row = conn.execute(
            f"SELECT migration_id, name, status, completed_at FROM "
            f"{MIGRATIONS_TABLE} WHERE migration_id=?", (MIGRATION_ID_V1,)
        ).fetchone()
        if row is not None:
            report.ledger_row = {
                "migration_id": row[0], "name": row[1],
                "status": row[2], "completed_at": row[3],
            }
    except sqlite3.OperationalError as exc:
        report.outcome = "failed"
        report.failure = f"{type(exc).__name__} during maintenance: {exc}"
        report.remediation = (
            "the transaction rolled back; nothing was recorded; free disk "
            "space or fix the underlying cause, then re-run "
            "`ocbrain memory-migrate --db <path>`. NEVER delete or manually "
            "trim database/WAL/SHM files to recover (Amendment 11).")
        report.verification["failure_classified"] = _classify_migration_failure(
            str(exc))
    except Exception as exc:
        report.outcome = "failed"
        report.failure = f"{type(exc).__name__} during maintenance: {exc}"
        report.remediation = (
            "the transaction rolled back; nothing was recorded; re-run "
            "`ocbrain memory-migrate --db <path>` after resolving the cause.")
        report.verification["failure_classified"] = _classify_migration_failure(
            str(exc))
    finally:
        if conn is not None:
            if not _prepared_already_applied:
                try:
                    conn.execute("ROLLBACK")  # no-op when already committed
                except sqlite3.Error:
                    pass
            try:
                conn.close()
            except sqlite3.Error:
                pass
        if lock_fd is not None:
            _release_lock_file(lock_path, lock_fd)

    if report.outcome == "migrated" and report.wal_bytes_after is None:
        # Fallback when the checkpoint step was disabled: measure before the
        # last connection closed (post-close the WAL file may not exist on
        # all platforms).
        report.wal_bytes_after = _wal_size(db_path)
    return report


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _wal_size(db_path: str) -> Optional[int]:
    try:
        return os.path.getsize(str(db_path) + "-wal")
    except OSError:
        return None


def _acquire_lock_file(lock_path: str):
    """
    Advisory lock: O_CREAT|O_EXCL is atomic on POSIX and Windows NTFS, so two
    independent migrators serialize on file creation; the crash of a migrator
    leaves a stale lock only if the process itself is killed mid-run (lock
    removal is in the finally path). Advisory by design — NOT a fencing
    protocol; the deployment contract delivers process quiescence.
    """
    fd = None
    deadline = time.time() + 20.0
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except FileExistsError:
            if time.time() > deadline:
                raise RuntimeError(
                    f"migration lock busy: {lock_path} exists — another "
                    "maintenance run may be active; if you are certain no "
                    "run is active, remove the advisory lock file manually "
                    f"{lock_path!r} after verifying first")
            time.sleep(0.2)


def _release_lock_file(lock_path: str, fd) -> None:
    os.close(fd)
    try:
        os.remove(lock_path)
    except OSError:
        pass


def _preserve_corrupt_database(db_path: str, reason: str) -> List[str]:
    """
    Amendment 3 §B.2: preserve the corrupt database for recovery before any
    further action; nothing about the original file is repaired or deleted.
    """
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    dest_dir = f"{db_path}.ocbrain_preserved_{ts}"
    os.makedirs(dest_dir, exist_ok=True)
    saved = []
    for suffix in ("", "-wal", "-shm"):
        src = str(db_path) + suffix
        if os.path.exists(src):
            dest = os.path.join(dest_dir, os.path.basename(src))
            shutil.copy2(src, dest)
            saved.append(dest)
    manifest = {
        "preserved_at": time.time(),
        "db_path": db_path,
        "reason": reason,
        "files": saved,
        "warning": ("corrupt pre-migration database; do not 'repair' FTS by "
                    "rebuild on the original (Amendment 3 §B.2)"),
    }
    (Path(dest_dir) / "manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.warning("[memory-migrate] corrupt database preserved: %s", dest_dir)
    return saved


def _classify_migration_failure(message: str) -> str:
    m = message.casefold()
    if "disk is full" in m or "database is full" in m or "out of memory" in m \
            or "disk i/o error" in m:
        return "sqlite_full_equivalent"
    if "integrity validation failed" in m:
        return "integrity_check_failure"
    if "identity verification failed" in m:
        return "content_identity_failure"
    if "locked" in m or "busy" in m:
        return "serialization_conflict"
    return "other"
