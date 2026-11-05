"""
Rev 3 amendment tests — Amendment 11: migration FAILURE behaviors.

Fault injection uses the documented TEST hook `run_maintenance_migration
(fault_injection=...)` at the runner's step boundary pre_flight/apply/
rebuild/verify/record/commit (and the post-commit checkpoint step). The
injected fault is the SQLITE_FULL equivalent: the message classifies as
"sqlite_full_equivalent" exactly like a real `SQLITE_FULL` would.

Guarantees tested:
  * a fault raised at ANY point inside the migration transaction
    propagates, the transaction rolls back, NOTHING is recorded
    (no ledger row, no meta state change, no schema change — DDL included),
    the repair guidance is issued, and the SAME migration retries
    successfully afterwards,
  * a fault at the POST-COMMIT checkpoint step is handled with the
    commit-first asymmetry: the migration itself IS durable (ledger row
    present, state current) while the report honestly says the maintenance
    RUN failed at the checkpoint step; the retry reports already_applied,
  * the space figures produced for the migration window are labeled as an
    estimate, never a guarantee (Amendment 11).
"""
import json
import os
import sqlite3

import pytest

from core.memory.sqlite_contract import (
    CONTENT_TABLE,
    MIGRATIONS_TABLE,
    MemoryReadinessError,
)
from core.memory.sqlite_integrity import validate_readiness
from core.memory.sqlite_migration import (
    estimate_migration_space,
    inspect_migration_state,
    read_migration_ledger,
    run_maintenance_migration,
)

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
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(LEGACY_SCHEMA)
        conn.execute(
            "INSERT INTO knowledge_entries (entry_id, layer, content,"
            " created_at, updated_at, accessed_at)"
            " VALUES ('x1', 'l1', 'xqzLEGACYOLD legacy body', 1.0, 1.0, 1.0)")
        conn.execute(
            "INSERT INTO knowledge_entries (entry_id, layer, content,"
            " created_at, updated_at, accessed_at)"
            " VALUES ('x2', 'l1', 'xqzLEGACYOTHER second tag body',"
            " 2.0, 2.0, 2.0)")
        conn.commit()
    finally:
        conn.close()


def _schema_snapshot(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        return {
            "objects": conn.execute(
                "SELECT type, name, sql FROM sqlite_schema"
                " ORDER BY type, name").fetchall(),
            "rows": conn.execute(
                f"SELECT * FROM {CONTENT_TABLE} ORDER BY entry_id").fetchall(),
            "ledger_tables": [n for (n,) in conn.execute(
                "SELECT name FROM sqlite_schema WHERE type='table'"
                f" AND name IN ('{MIGRATIONS_TABLE}')").fetchall()],
        }
    finally:
        conn.close()


def _ledger(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        return read_migration_ledger(conn)
    finally:
        conn.close()


def _fault_at(target_step: str):
    """SQLITE_FULL equivalent: both the exception TYPE and the message
    wording mimic what a real disk-full would raise (sqlite3.OperationalError
    with SQLite's `database or disk is full` message), so the runner's
    failure handling is exercised exactly like a real SQLITE_FULL."""
    def injection(step_name: str) -> None:
        if step_name == target_step:
            raise sqlite3.OperationalError(
                "database or disk is full (Amendment 11 fault injection)")
    return injection


class TestTransactionFaultRollsBackEverything:
    """A fault at any in-transaction step: exception propagates (surfaced as
    a failed report), NOTHING is recorded, and a later retry succeeds."""

    @pytest.mark.parametrize("step", [
        "apply", "rebuild", "verify", "record", "commit"])
    def test_fault_mid_transaction_rolls_back_then_retry_succeeds(
            self, tmp_path, step):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        before = _schema_snapshot(db_path)

        report = run_maintenance_migration(
            db_path, fault_injection=_fault_at(step), run_final_checkpoint=True)

        assert report.outcome == "failed", report.to_dict()
        assert isinstance(report.failure, str)
        assert "OperationalError" in report.failure and "disk is full" in \
            report.failure
        # The failure classifies like a real SQLITE_FULL would (Am. 11 §A):
        assert report.verification["failure_classified"] == \
            "sqlite_full_equivalent"
        # Guidance is present and forbids manual file trimming (Am. 11):
        assert isinstance(report.remediation, str) and report.remediation
        assert "memory-migrate" in report.remediation
        assert "NEVER delete" in report.remediation or "never delete" in \
            report.remediation.lower()
        # The injected step is recorded honestly in the step trace:
        assert {"step": "fault_injection", "status": "invoked",
                "detail": f"step={step}"} in report.steps

        # NOTHING was recorded; the database is untouched (DDL + data):
        after = _schema_snapshot(db_path)
        assert after == before
        assert _ledger(db_path) == []
        assert _schema_snapshot(db_path)["ledger_tables"] == []

        # Same migration retries successfully once the fault is gone:
        retry = run_maintenance_migration(db_path)
        assert retry.outcome == "migrated"
        ledger = _ledger(db_path)
        assert len(ledger) == 1
        assert inspect_migration_state(
            sqlite3.connect(db_path)).state == "current"


class TestPreFlightFault:
    """A fault BEFORE any connection is made leaves nothing behind either."""

    def test_preflight_fault_fails_cleanly_then_retry_succeeds(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        before = _schema_snapshot(db_path)

        report = run_maintenance_migration(
            db_path, fault_injection=_fault_at("pre_flight"))

        assert report.outcome == "failed"
        assert report.verification["failure_classified"] == \
            "sqlite_full_equivalent"
        assert _schema_snapshot(db_path) == before
        assert _ledger(db_path) == []

        retry = run_maintenance_migration(db_path)
        assert retry.outcome == "migrated"


class TestPostCommitCheckpointFault:
    """Commit-first semantics: a fault AFTER the commit must NOT retro-
    cancel the migration. The report says 'failed' at the checkpoint step,
    but the durable state (ledger row, migrated meta state) is real and the
    retry reports already_applied instead of re-running side effects."""

    def test_checkpoint_fault_keeps_the_committed_migration(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)

        report = run_maintenance_migration(
            db_path, fault_injection=_fault_at("checkpoint"))

        # Honest report: the RUN failed at the final checkpoint...
        assert report.outcome == "failed"
        assert "disk is full" in report.failure
        # ...but the migration itself was committed BEFORE the fault:
        ledger = _ledger(db_path)
        assert len(ledger) == 1
        conn = sqlite3.connect(db_path)
        try:
            assert inspect_migration_state(conn).state == "current"
        finally:
            conn.close()
        # Retry does NOT repeat side effects:
        retry = run_maintenance_migration(db_path)
        assert retry.outcome == "already_applied"
        assert len(_ledger(db_path)) == 1

        # The migrated database remains usable, work included:
        steps_by_name = {}
        for s in retry.steps:
            steps_by_name.setdefault(s["step"], []).append(s)
        assert steps_by_name["migration"][0]["status"] == "skipped"


class TestConstructorRefusalAfterFailedRun:
    """The refused-construction contract is unchanged by failed attempts:
    a legacy database that failed to migrate still refuses startup with the
    same encapsulated remediation guidance."""

    def test_memory_readiness_error_mentions_remediation(self, tmp_path):
        from core.memory.backends.sqlite_storage import SQLiteStorageBackend
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        report = run_maintenance_migration(
            db_path, fault_injection=_fault_at("rebuild"))
        assert report.outcome == "failed"

        with pytest.raises(MemoryReadinessError) as excinfo:
            SQLiteStorageBackend(db_path)  # no acknowledge: must refuse
        # The refusal carries explicit remediation guidance on the exception.
        remediation = str(excinfo.value.remediation)
        assert "memory-migrate" in remediation
        # It must promote the maintenance window (deployment contract), not
        # an in-place repair:
        assert "stop all processes" in remediation.lower()


class TestSpaceEstimateContract:
    """Amendment 11 §B: space figures are ESTIMATES, labeled honestly."""

    def test_estimate_fields_and_wording(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        est = estimate_migration_space(db_path)

        for key in ("db_bytes", "page_size", "page_count", "freelist_pages",
                    "content_bytes_measured", "estimate_extra_bytes",
                    "estimate_basis", "free_bytes",
                    "sufficient_free_estimate"):
            assert key in est, key
        # Measured facts:
        assert isinstance(est["content_bytes_measured"], int)
        assert est["content_bytes_measured"] > 0
        # Estimate envelope never undercuts the measured content:
        assert est["estimate_extra_bytes"] >= est["content_bytes_measured"]
        # Free space is a number (POSIX/Windows tmp) and the sufficiency
        # flag is a plain boolean DERIVED from the estimate — an estimate,
        # never a guarantee:
        assert isinstance(est["free_bytes"], int) and est["free_bytes"] > 0
        assert isinstance(est["sufficient_free_estimate"], bool)
        basis = est["estimate_basis"]
        assert "estimate" in basis.lower()
        assert "NOT a guarantee" in basis
        assert "Amendment 11" in basis

    def test_estimate_basis_recording_in_report_and_ledger(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _build_legacy_db(db_path)
        report = run_maintenance_migration(db_path)
        assert report.outcome == "migrated"
        # The report carried the labeled basis through the whole window:
        basis = report.space_estimate["estimate_basis"]
        assert "NOT a guarantee" in basis
        ledger = _ledger(db_path)
        assert len(ledger) == 1
        # The pre-checks JSON (including the labeled basis) is part of the
        # durable ledger row; read it from the raw table.
        conn = sqlite3.connect(db_path)
        try:
            (raw,) = conn.execute(
                f"SELECT pre_checks_json FROM {MIGRATIONS_TABLE}"
                " WHERE migration_id = "
                f"(SELECT MIN(migration_id) FROM {MIGRATIONS_TABLE})"
            ).fetchone()
        finally:
            conn.close()
        pre_checks = json.loads(raw)
        assert "Amendment 11" in pre_checks["space"]["estimate_basis"]
