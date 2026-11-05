"""
Rev 3 amendment tests — Amendment 2 (migration lifecycle separation) and
Amendment 7 (per-database inventory/ledgers).

Core guarantees proven here:
  * normal startup is VALIDATION-ONLY: a legacy database is refused with
    MemoryReadinessError and its schema/schema data/rows are NOT mutated
    (no trigger swap, no index creation, no FTS rebuild, no ledger),
  * the dedicated maintenance entry point performs the migration behind
    advisory + write locks, re-reads the state AFTER locking, replaces
    triggers, rebuilds/verifies FTS, and RECORDS a per-database ledger row,
    reporting success only after the commit,
  * concurrent runners (independent subprocesses, the same shape as two
    operators racing `ocbrain memory-migrate`) serialize: exactly one
    migrates, the other reports already_applied after re-reading state under
    the lock,
  * independent database files have independent migration lifecycles.
"""
import json
import os
import sqlite3
import subprocess
import sys
import time

import pytest

from core.memory.backends.sqlite_storage import (
    DEFAULT_DB_PATH,
    SQLiteStorageBackend,
)
from core.memory.sqlite_contract import (
    CONTENT_TABLE,
    FTS_TABLE,
    MIGRATION_ID_V1,
    MIGRATIONS_TABLE,
    META_SCHEMA_STATE,
    META_TABLE,
    MemoryReadinessError,
    CANONICAL_TRIGGER_DDL,
    normalize_sql,
)
from core.memory.sqlite_integrity import (
    run_full_integrity_validation,
    validate_readiness,
)
from core.memory.sqlite_migration import (
    MIGRATION_LOCK_SUFFIX,
    inspect_migration_state,
    read_migration_ledger,
    run_maintenance_migration,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_SCHEMA = """
CREATE TABLE knowledge_entries (
    entry_id TEXT PRIMARY KEY, layer TEXT NOT NULL, content TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '', importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 1.0, truth_status TEXT NOT NULL DEFAULT 'unknown',
    trust_score REAL NOT NULL DEFAULT 1.0, source TEXT NOT NULL DEFAULT '',
    worker_id TEXT NOT NULL DEFAULT '', workflow_id TEXT NOT NULL DEFAULT '',
    derived_from TEXT NOT NULL DEFAULT '[]', supports TEXT NOT NULL DEFAULT '[]',
    contradicts TEXT NOT NULL DEFAULT '[]', supersedes TEXT NOT NULL DEFAULT '[]',
    graph_node_id TEXT, tags TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}', procedure_name TEXT,
    created_at REAL NOT NULL, updated_at REAL NOT NULL,
    accessed_at REAL NOT NULL, access_count INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE knowledge_entries_fts USING fts5(
    content, summary, tags, content='knowledge_entries', content_rowid='rowid'
);
CREATE TRIGGER ke_ai AFTER INSERT ON knowledge_entries BEGIN
    INSERT INTO knowledge_entries_fts(rowid, content, summary, tags)
    VALUES (new.rowid, new.content, new.summary, new.tags);
END;
CREATE TRIGGER ke_au AFTER UPDATE ON knowledge_entries BEGIN
    UPDATE knowledge_entries_fts
    SET content=new.content, summary=new.summary, tags=new.tags
    WHERE rowid=old.rowid;
END;
CREATE TRIGGER ke_ad AFTER DELETE ON knowledge_entries BEGIN
    DELETE FROM knowledge_entries_fts WHERE rowid=old.rowid;
END;
"""


def _build_legacy_db(db_path: str) -> None:
    """A pre-Rev3 database with the documented historical unsafe ke_au."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(LEGACY_SCHEMA)
        conn.execute(
            "INSERT INTO knowledge_entries (entry_id, layer, content,"
            " created_at, updated_at, accessed_at)"
            " VALUES ('x1', 'l1', 'xqzLEGACYOLD legacy body', 1.0, 1.0, 1.0)")
        conn.commit()
    finally:
        conn.close()


def _schema_snapshot(db_path: str) -> dict:
    """Everything Refuses-construction must leave untouched."""
    conn = sqlite3.connect(db_path)
    try:
        objects = conn.execute(
            "SELECT type, name, sql FROM sqlite_schema ORDER BY type, name"
        ).fetchall()
        rows = conn.execute(
            f"SELECT * FROM {CONTENT_TABLE} ORDER BY entry_id").fetchall()
        fts_rows = conn.execute(
            f"SELECT rowid, content, summary, tags FROM {FTS_TABLE}"
            " ORDER BY rowid").fetchall()
        rowids = conn.execute(
            f"SELECT rowid FROM {CONTENT_TABLE} ORDER BY rowid").fetchall()
        return {
            "objects": objects,
            "rows": rows,
            "fts_rows": fts_rows,
            "rowids": rowids,
            "meta_tables": [n for (n,) in conn.execute(
                "SELECT name FROM sqlite_schema WHERE type='table'"
                " AND name IN (?, ?)", (META_TABLE, MIGRATIONS_TABLE)
            ).fetchall()],
        }
    finally:
        conn.close()


# ── Amendment 2 §B: validation-only startup on a legacy database ─────────────

class TestValidationOnlyStartup:
    def test_constructor_refuses_legacy_db_and_points_at_maintenance_cmd(
            self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)

        with pytest.raises(MemoryReadinessError) as exc:
            SQLiteStorageBackend(db_path, runtime_gate="acknowledge")

        err = exc.value
        # The refusal names the dedicated maintenance command (Amendment 2):
        assert "memory-migrate" in err.remediation_plan
        assert err.finding["kind"] == "memory_migration_state"

    def test_validation_only_startup_never_mutates_the_legacy_database(
            self, tmp_path):
        """Amendment 2 headline guarantee: construction (enforce OR
        acknowledge) runs NO migration against a legacy database."""
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        before = _schema_snapshot(db_path)

        with pytest.raises(MemoryReadinessError):
            SQLiteStorageBackend(db_path, runtime_gate="acknowledge")
        after = _schema_snapshot(db_path)

        assert before == after, (
            "validation-only startup must not mutate the database: schema "
            "objects, content rows, FTS mirror rows and rowids must be "
            "identical")
        # In particular: no migration machinery was installed behind the
        # operator's back, and the legacy trigger keeps its historical bytes.
        assert after["meta_tables"] == []
        legacy_ke_au = [sql for (t, n, sql) in after["objects"]
                        if t == "trigger" and n == "ke_au"][0]
        assert "UPDATE knowledge_entries_fts" in legacy_ke_au
        # No advisory lock leftovers from construction either.
        assert not os.path.exists(db_path + MIGRATION_LOCK_SUFFIX)

    def test_construction_fails_on_unrecognized_state_too(self, tmp_path):
        """Not just legacy: an unrecognized schema_state refuses as well."""
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        # Sabotage: drop ke_ad so the trigger set is neither canonical nor
        # the documented historical set.
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DROP TRIGGER ke_ad")
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(MemoryReadinessError):
            SQLiteStorageBackend(db_path, runtime_gate="acknowledge")

    def test_fresh_absent_db_initializes_with_its_own_ledger(self, tmp_path):
        """Unavailable database → canonical init + per-database ledger
        (Amendment 7); a marker DB carries its own state, and this happens at
        construction because there is nothing legacy to protect."""
        db_path = str(tmp_path / "fresh.db")
        backend = SQLiteStorageBackend(db_path, runtime_gate="acknowledge")
        assert backend.readiness_state["migration_state"] == "current"
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                f"SELECT migration_id, status FROM {MIGRATIONS_TABLE}"
            ).fetchall()
            state = conn.execute(
                f"SELECT value FROM {META_TABLE} WHERE key=?",
                (META_SCHEMA_STATE,)).fetchone()
        finally:
            conn.close()
        assert (MIGRATION_ID_V1, "applied") in rows
        assert state[0] == "initialized_fresh_current"


# ── Amendment 2 §B.4-9: the maintenance lifecycle ────────────────────────────

class TestMaintenanceMigration:
    def test_maintenance_applies_migration_and_records_ledger(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        report = run_maintenance_migration(db_path)
        assert report.outcome == "migrated"
        assert report.failure is None

        step_names = [s["step"] for s in report.steps]
        # Amendment 2 §B full sequence, including the post-lock re-read:
        for required in ("pre_integrity_check", "maintenance_lock",
                         "migration_lock", "re_read_migration_state",
                         "replace_triggers", "fts_rebuild", "verification",
                         "record_migration", "commit"):
            assert required in step_names, required
        # §B.9 — success only after commit:
        assert step_names.index("record_migration") < step_names.index("commit")

        # Per-database ledger (Amendment 7):
        conn = sqlite3.connect(db_path)
        try:
            ledger = read_migration_ledger(conn)
            state = conn.execute(
                f"SELECT value FROM {META_TABLE} WHERE key=?",
                (META_SCHEMA_STATE,)).fetchone()[0]
        finally:
            conn.close()
        assert len(ledger) == 1
        row = ledger[0]
        assert row["migration_id"] == MIGRATION_ID_V1
        assert row["status"] == "applied"
        assert row["host_os"]
        assert report.ledger_row["migration_id"] == MIGRATION_ID_V1
        assert state in ("initialized_fresh_current", "migrated_to_current")
        assert report.checkpoint  # post-commit checkpoint recorded honestly

    def test_migrated_ke_au_is_canonical_and_uses_delete_insert(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        run_maintenance_migration(db_path)
        conn = sqlite3.connect(db_path)
        try:
            trigger_sql = conn.execute(
                "SELECT sql FROM sqlite_schema WHERE type='trigger'"
                " AND name='ke_au'").fetchone()[0]
        finally:
            conn.close()
        # Amendment 8: semantic comparison with the canonical definition
        # (not substring matching by the AUDIT; this assertion is the test's
        # own double-check that the general shape is the documented pattern).
        assert normalize_sql(trigger_sql) == \
            normalize_sql(CANONICAL_TRIGGER_DDL["ke_au"])
        assert "'delete'" in trigger_sql

    def test_migrated_db_passes_full_integrity_and_searches_correctly(
            self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        run_maintenance_migration(db_path)

        conn = sqlite3.connect(db_path)
        try:
            result = run_full_integrity_validation(
                conn,
                retrieval_tokens=[("xqzLEGACYOLD", True)])
        finally:
            conn.close()
        assert result["passed"], [f for f in result["findings"]
                                  if f["status"] not in ("pass",
                                                         "not_applicable")]

        # And the migrated database offers ordinary memory service:
        backend = SQLiteStorageBackend(db_path, runtime_gate="acknowledge")
        assert backend.readiness_state["migration_state"] == "current"

    def test_already_applied_re_read_reports_no_work(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        first = run_maintenance_migration(db_path)
        assert first.outcome == "migrated"
        second = run_maintenance_migration(db_path)
        assert second.outcome == "already_applied"
        second_steps = {s["step"] for s in second.steps}
        assert "re_read_migration_state" in second_steps
        assert "replace_triggers" not in second_steps
        assert "fts_rebuild" not in second_steps

    def test_validation_only_constructor_refuses_until_maintenance(self, tmp_path):
        """Order of operations an operator would actually hit: refuse →
        migrate → then the ordinary constructor accepts."""
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        with pytest.raises(MemoryReadinessError):
            SQLiteStorageBackend(db_path, runtime_gate="acknowledge")
        report = run_maintenance_migration(db_path)
        assert report.outcome == "migrated"
        backend = SQLiteStorageBackend(db_path, runtime_gate="acknowledge")
        conn = sqlite3.connect(db_path)
        try:
            validation = validate_readiness(conn)
        finally:
            conn.close()
        assert validation["passed"]
        assert backend.readiness_state["migration_state"] == "current"
        del backend


# ── Amendment 2 §E: concurrent maintenance runners (subprocesses) ───────────

def _run_child(db_path: str, log_path: str, timeout: float = 180.0) -> dict:
    child = subprocess.run(
        [sys.executable,
         os.path.join(REPO_ROOT, "tests", "_g4_migration_child.py"),
         REPO_ROOT, db_path, log_path],
        capture_output=True, text=True, timeout=timeout,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert child.returncode == 0, (child.stdout, child.stderr)
    return child


class TestConcurrentMaintenanceRunners:
    def test_concurrent_subprocess_migrations_serialize(self, tmp_path):
        """Two independent processes race for the same database. Exactly one
        migrates; the other must acquire the lock afterwards, re-read the
        state and report already_applied — no double rebuild, no half-migrated
        state, no crash."""
        db_path = str(tmp_path / "u.db")
        log_path = str(tmp_path / "children.jsonl")
        _build_legacy_db(db_path)

        # Fire both in true parallel and wait for both.
        proc_a = subprocess.Popen(
            [sys.executable,
             os.path.join(REPO_ROOT, "tests", "_g4_migration_child.py"),
             REPO_ROOT, db_path, log_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc_b = subprocess.Popen(
            [sys.executable,
             os.path.join(REPO_ROOT, "tests", "_g4_migration_child.py"),
             REPO_ROOT, db_path, log_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out_a, err_a = proc_a.communicate(timeout=180)
        out_b, err_b = proc_b.communicate(timeout=180)
        assert proc_a.returncode == 0, (out_a, err_a)
        assert proc_b.returncode == 0, (out_b, err_b)

        children = [json.loads(line) for line in
                    open(log_path, encoding="utf-8")]
        assert len(children) == 2
        outcomes = sorted(c["outcome"] for c in children)
        assert outcomes == ["already_applied", "migrated"], children
        assert all(c["failure"] is None for c in children)
        assert all(c["re_read_after_lock"] for c in children)

        # The database ends up migrated exactly once, with a clean state:
        conn = sqlite3.connect(db_path)
        try:
            applied = conn.execute(
                f"SELECT COUNT(*) FROM {MIGRATIONS_TABLE} "
                "WHERE migration_id=? AND status='applied'",
                (MIGRATION_ID_V1,)).fetchone()[0]
        finally:
            conn.close()
        assert applied == 1
        assert not os.path.exists(db_path + MIGRATION_LOCK_SUFFIX)

        result = None
        conn = sqlite3.connect(db_path)
        try:
            result = run_full_integrity_validation(conn)
        finally:
            conn.close()
        assert result["passed"]

        # And the maintenance lock is gone (advisory lock released):
        assert not os.path.exists(db_path + MIGRATION_LOCK_SUFFIX)


# ── Amendment 7: independent databases, per-database ledgers ─────────────────

class TestPerDatabaseLedgers:
    def test_two_independent_databases_migrate_independently(self, tmp_path):
        db_first = str(tmp_path / "u.db")
        db_second = str(tmp_path / "archive_model.db")
        _build_legacy_db(db_first)
        _build_legacy_db(db_second)

        # Migrate ONLY the first database.
        report_first = run_maintenance_migration(db_first)
        assert report_first.outcome == "migrated"

        def _ledger_state(db):
            """Per-database ledger as (applied_count, meta_state). Missing
            housekeeping tables are a legitimate per-database state (a legacy
            file that has not been through the maintenance window)."""
            conn = sqlite3.connect(db)
            try:
                applied = conn.execute(
                    f"SELECT COUNT(*) FROM {MIGRATIONS_TABLE} "
                    "WHERE migration_id=? AND status='applied'",
                    (MIGRATION_ID_V1,)).fetchone()[0]
                state = conn.execute(
                    f"SELECT value FROM {META_TABLE} WHERE key=?",
                    (META_SCHEMA_STATE,)).fetchone()
            except sqlite3.OperationalError:
                return 0, None
            finally:
                conn.close()
            return applied, (state[0] if state else None)

        first_applied, first_state = _ledger_state(db_first)
        second_applied, second_state = _ledger_state(db_second)

        # The first DB's ledger does not appear in the second file: state is
        # IN the database file, not process-global (Amendment 7).
        assert first_applied == 1
        assert first_state == "migrated_to_current"
        assert second_applied == 0
        assert second_state is None

        # The second database still refuses at construction, independently:
        with pytest.raises(MemoryReadinessError):
            SQLiteStorageBackend(db_second, runtime_gate="acknowledge")

        # ... then migrates on its own lifecycle:
        report_second = run_maintenance_migration(db_second)
        assert report_second.outcome == "migrated"
        assert _ledger_state(db_second) == (1, "migrated_to_current")

        # Both databases service memory now (and with a second file in WAL,
        # each has its own independent ledger/metadata tables):
        for db in (db_first, db_second):
            backend = SQLiteStorageBackend(db, runtime_gate="acknowledge")
            assert backend.readiness_state["migration_state"] == "current"
            assert backend.readiness_state["memory_ready"] is False

    def test_unified_default_path_concept_independent_of_tmp_files(self, tmp_path):
        """The default database path constant exists so deployments know which
        file the maintenance command targets by default (Amendment 7
        inventory)."""
        assert DEFAULT_DB_PATH.endswith("unified.db")
