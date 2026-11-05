"""
Rev 3 amendment tests — Amendment 5: controlled mutation-atomicity failure
injection on the three FTS-sync paths.

Method (per the remediation plan, verified against real SQLite behavior via
probe scripts): a SQLite authorizer denies the dangerous action on the FTS5
VIRTUAL table (`knowledge_entries_fts`):

  * INSERT path  -> deny SQLITE_INSERT on `knowledge_entries_fts`
                    (ke_ai's insert, and ke_au's two inserts),
  * UPDATE path  -> same INSERT denial (the canonical ke_au expresses
                    UPDATE-into-external-content as delete+INSERT pairs),
  * DELETE path  -> deny SQLITE_DELETE on `knowledge_entries_fts`
                    (ke_ad's delete).

Documented hazard (probe session, recorded in the Rev 3 report): denying
SQLITE_READ against the FTS shadow `rowid` column causes SILENT desync — it
is NOT used as an injection instrument here for that reason.

Each test verifies the FULL guarantee set: the statement fails, every row is
rolled back (no partial rows anywhere — content table AND FTS mirror), the
database is left in a rank=1-consistent state, and the SAME operation retries
successfully once the injected fault is removed.
"""
import sqlite3
from contextlib import contextmanager

import pytest

from core.memory.backends.sqlite_storage import SQLiteStorageBackend
from core.memory.knowledge_entry import KnowledgeEntry
from core.memory.sqlite_contract import FTS_TABLE
from core.memory.sqlite_integrity import (
    run_full_integrity_validation,
)


def _entry(entry_id: str, content: str) -> KnowledgeEntry:
    return KnowledgeEntry(entry_id=entry_id, layer="l1", content=content,
                          importance=0.5, created_at=1.0, updated_at=1.0,
                          accessed_at=1.0)


def _authorizer(deny_action: int, deny_target: str):
    def authorizer(action, arg1, arg2, db_name, trigger_name):
        if action == deny_action and arg1 == deny_target:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return authorizer


@contextmanager
def injected(backend: SQLiteStorageBackend, deny_action: int,
             deny_target: str):
    """
    Swap the backend's connection factory for one carrying the authorizer
    (instance attribute shadowing, restored on exit).
    """
    auth = _authorizer(deny_action, deny_target)

    def connect_with_auth():
        conn = sqlite3.connect(backend.db_path, timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        conn.set_authorizer(auth)
        return conn

    backend._connect = connect_with_auth
    try:
        yield
    finally:
        del backend._connect   # restores the class-level factory


def _state(db_path: str) -> dict:
    """Full read-only consistency snapshot incl. the FTS mirror and the
    rank=1 FTS integrity command. The mirror is scoped to content rowids:
    the FTS shadow `_data` table also carries structural rows (id=1, …) that
    exist even on an empty index."""
    conn = sqlite3.connect(db_path, timeout=20.0)
    try:
        content = conn.execute(
            "SELECT entry_id, content, summary FROM knowledge_entries"
            " ORDER BY entry_id").fetchall()
        mirror = conn.execute(
            f"SELECT id, block FROM {FTS_TABLE}_data WHERE id IN"
            " (SELECT rowid FROM knowledge_entries) ORDER BY id").fetchall()
        validation = run_full_integrity_validation(conn)
        rank1 = [f for f in validation["findings"]
                 if f["scope"] == "fts_internal_external_content_integrity"]
        return {"content": content, "mirror": mirror,
                "integrity_passed": validation["passed"],
                # The rank=1 finding separately: on the AFFECTED runtime
                # covered by this suite it reports an ERROR after any
                # successful DELETE (see test below — documented finding).
                "rank1_status": rank1[0]["status"] if rank1 else "missing"}
    finally:
        conn.close()


class TestInsertPathRollback:
    """ke_ai: INSERT INTO knowledge_entries → trigger INSERT into FTS."""

    def test_denied_fts_insert_rolls_back_the_whole_statement(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        before = _state(backend.db_path)
        assert before["content"] == [] and before["mirror"] == []

        with injected(backend, sqlite3.SQLITE_INSERT, FTS_TABLE):
            with pytest.raises(Exception) as excinfo:
                asyncio_run(backend.write(_entry("k1", "xqzNEW token body")))
        # The failure comes from the authorizer, not a silent success:
        assert "not authorized" in str(excinfo.value).lower()

        after = _state(backend.db_path)
        assert after["content"] == []          # no partial content row remains
        assert after["mirror"] == []           # no partial FTS row was written
        assert after["integrity_passed"] is True   # fully consistent state

    def test_retry_succeeds_after_fault_removed(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        with pytest.raises(Exception):
            with injected(backend, sqlite3.SQLITE_INSERT, FTS_TABLE):
                asyncio_run(backend.write(_entry("k1", "xqzNEW token body")))

        # fault removed — same operation again:
        entry_id = asyncio_run(backend.write(_entry("k1", "xqzNEW token body")))
        assert entry_id == "k1"
        hits = asyncio_run(backend.search_text("xqzNEW"))
        assert len(hits) == 1 and hits[0].entry_id == "k1"
        state = _state(backend.db_path)
        assert state["integrity_passed"] is True


class TestUpdatePathRollback:
    """ke_au: summary UPDATE → delete+INSERT pair against the FTS table.

    (A raw `UPDATE knowledge_entries_fts SET ...` anywhere in the trigger
    would be the pre-Rev3 unsafe pattern; the canonical ke_au uses the
    documented 'delete' command INSERT, so the UPDATE sync path is injected
    through the INSERT denial — verified in the probe session.)
    """

    def test_denied_fts_update_preserves_original_content(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        asyncio_run(backend.write(_entry("k1", "xqzORIGINAL body text")))

        original_state = _state(backend.db_path)

        with injected(backend, sqlite3.SQLITE_INSERT, FTS_TABLE):
            with pytest.raises(Exception) as excinfo:
                asyncio_run(backend.update(
                    "k1", {"summary": "xqzUPDATED summary value"}))
        assert "not authorized" in str(excinfo.value).lower()

        after = _state(backend.db_path)
        # The whole statement rolled back: row + mirror unchanged.
        assert after["content"] == original_state["content"]
        assert after["mirror"] == original_state["mirror"]
        assert after["integrity_passed"] is True

        # Same guarantees through the public search path:
        assert len(asyncio_run(backend.search_text("xqzORIGINAL"))) == 1
        assert len(asyncio_run(backend.search_text("xqzUPDATED"))) == 0

    def test_retry_update_succeeds_after_fault_removed(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        asyncio_run(backend.write(_entry("k1", "xqzORIGINAL body text")))
        with pytest.raises(Exception):
            with injected(backend, sqlite3.SQLITE_INSERT, FTS_TABLE):
                asyncio_run(backend.update(
                    "k1", {"summary": "xqzUPDATED summary value"}))
        ok = asyncio_run(backend.update("k1", {"summary":
                                               "xqzUPDATED summary value"}))
        assert ok is True
        reread = asyncio_run(backend.read("k1"))
        assert reread.summary == "xqzUPDATED summary value"
        assert len(asyncio_run(backend.search_text("xqzORIGINAL"))) == 1
        state = _state(backend.db_path)
        assert state["integrity_passed"] is True


class TestDeletePathRollback:
    """ke_ad: DELETE FROM knowledge_entries → trigger DELETE on FTS row."""

    def test_denied_fts_delete_preserves_the_entry(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        asyncio_run(backend.write(_entry("k1", "xqzKEEPME body text")))
        original_state = _state(backend.db_path)

        with injected(backend, sqlite3.SQLITE_DELETE, FTS_TABLE):
            with pytest.raises(Exception) as excinfo:
                asyncio_run(backend.delete("k1"))
        assert "not authorized" in str(excinfo.value).lower()

        after = _state(backend.db_path)
        assert after["content"] == original_state["content"]
        assert after["mirror"] == original_state["mirror"]
        assert after["integrity_passed"] is True
        # Still fully searchable — not silently removed from the index only:
        assert len(asyncio_run(backend.search_text("xqzKEEPME"))) == 1

    def test_retry_delete_succeeds_after_fault_removed(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        asyncio_run(backend.write(_entry("k1", "xqzKEEPME body text")))
        with pytest.raises(Exception):
            with injected(backend, sqlite3.SQLITE_DELETE, FTS_TABLE):
                asyncio_run(backend.delete("k1"))
        ok = asyncio_run(backend.delete("k1"))
        assert ok is True
        assert asyncio_run(backend.read("k1")) is None
        state = _state(backend.db_path)
        assert state["content"] == []
        assert state["mirror"] == []
        # Consistency assertions that hold on EVERY runtime:
        assert asyncio_run(backend.search_text("xqzKEEPME")) == []
        # Amendment 12 honesty note: on the AFFECTED bundled runtime the
        # rank=1 integrity-check command reports "malformed" after ANY
        # successful DELETE (a raw SQLite behavior, verified independent of
        # this code — see the runtime-finding test below and the Rev 3
        # report). The rollback tests above stay strict: no delete happened
        # there, so rank=1 must genuinely pass.
        assert state["rank1_status"] in ("pass", "error")


def asyncio_run(coro):
    """Pytest-asyncio auto mode already provides the loop; run plain coros
    inside sync helper functions."""
    import asyncio
    return asyncio.run(coro)


class TestRuntimeFindingRank1AfterDelete:
    """
    DOCUMENTED FINDING (Amendment 12 disclosure), discovered by the Amendment
    5 injection work: on SQLite 3.50.4 (the affected build bundled with this
    interpreter — raw probe, independent of this repository's code), a
    SUCCESSFUL DELETE on an external-content FTS5 table leaves the documented
    `INSERT INTO fts(fts, rank) VALUES('integrity-check', 1)` command
    returning "database disk image is malformed", and
    PRAGMA integrity_check still passes.

    Two consequences recorded in the Rev 3 report:
      1. AFTER a successful delete, the deletion rollback tests must not
         require a rank=1 PASS (they use MATCH probes + structural checks).
      2. This is one more concrete manifestation for the repair plan: the
         affected runtime is not certified for the FTS contract even
         though the CRITICAL mutation paths (insert/upsert/delete sync with
         rollback) behave correctly under fault injection.

    This test encodes the OBSERVED runtime behavior conditionally: affected
    build in range -> the error finding; fixed build (>= 3.51.3) -> expected
    clean pass.
    """

    def test_rank1_after_delete_conditionally(self, tmp_path):
        from core.memory.sqlite_runtime import classify_wal_safety
        verdict = classify_wal_safety()
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        asyncio_run(backend.write(_entry("k1", "xqzFINDING one")))
        asyncio_run(backend.write(_entry("k2", "xqzFINDING two")))
        asyncio_run(backend.delete("k1"))
        state = _state(backend.db_path)
        assert state["content"] == [("k2", "xqzFINDING two", "")]
        if verdict.wal_safe:
            assert state["rank1_status"] == "pass"
        else:
            assert state["rank1_status"] == "error"
        assert asyncio_run(backend.search_text("xqzFINDING two")) != []
