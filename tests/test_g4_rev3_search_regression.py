"""
Rev 3 amendment tests — Amendment 9: search regression on controlled
alphabetic tokens, driven through BOTH surfaces:

  1. direct FTS5 queries against `knowledge_entries_fts` (the independent
     verification surface), and
  2. the public UnifiedMemory API (`memory.write`, `memory.search`,
     `memory.delete`).

Guarantees tested: old tokens disappear after UPSERT/DELETE revisions on the
public surface and on the direct-FTS surface after revisions; fresh tokens
are discoverable on both surfaces; the FTS rowid and the content-table rowid
carry the entry identity (Amendment 4 identity at retrieval time).

DOCUMENTED RUNTIME FINDING (SQLite 3.50.4, raw probe — see also
tests/test_g4_rev3_mutation_atomicity.py): after a SUCCESSFUL DELETE on an
external-content FTS table, the freed docid remains MATCH-findable on the
direct surface (`_data` mirror gone, count(*) 0, rank=1 command reports
"malformed") while the public `search_text` surface is protected by its
`ke.rowid = fts.rowid` JOIN and returns nothing. Matches are tied to the
freed docid only — newly written content does NOT inherit stale tokens.
Therefore, on the affected build the direct-surface deletion assertion is
encoded conditionally (`classify_wal_safety().wal_safe`), as in the rest of
this suite; a fixed build must satisfy the strict form.
"""
import sqlite3

import pytest

from core.memory.backends.sqlite_archive import SQLiteArchiveBackend
from core.memory.backends.sqlite_storage import SQLiteStorageBackend
from core.memory.sqlite_contract import CONTENT_TABLE
from core.memory.sqlite_integrity import (
    check_fts_retrieval,
    check_structural_integrity,
)
from core.memory.unified_memory import UnifiedMemory


def _memory(tmp_path, name="u.db") -> UnifiedMemory:
    prefix = tmp_path / name
    storage = SQLiteStorageBackend(str(prefix), runtime_gate="acknowledge")
    archive = SQLiteArchiveBackend(str(tmp_path / (name + ".archive.db")))
    return UnifiedMemory(storage=storage, archive=archive)


def _direct_fts_query(db_path: str, query: str):
    """Surface 1 — direct FTS5 MATCH (independent of the public API)."""
    conn = sqlite3.connect(db_path, timeout=20.0)
    try:
        return conn.execute(
            "SELECT rowid FROM knowledge_entries_fts"
            " WHERE knowledge_entries_fts MATCH ? ORDER BY rowid",
            (query,)).fetchall()
    finally:
        conn.close()


def _record_identity(db_path: str, entry_id: str):
    conn = sqlite3.connect(db_path, timeout=20.0)
    try:
        return conn.execute(
            f"SELECT rowid, entry_id, content FROM {CONTENT_TABLE}"
            " WHERE entry_id=?", (entry_id,)).fetchone()
    finally:
        conn.close()


class TestSearchRegressionThroughWriteRevisions:
    """Amendment 9 §1: revision via write() must retire the old tokens and
    admit the new ones on BOTH surfaces."""

    @pytest.fixture
    def mem(self, tmp_path):
        return _memory(tmp_path)

    @pytest.fixture
    def db(self, mem):
        return mem._storage.db_path

    @pytest.mark.asyncio
    async def test_write_revision_retires_old_token_both_surfaces(self, mem, db):
        entry_id = await mem.write("xqzALPHA revision one body",
                                   layer_hint="l1", entry_id="reg1")
        assert entry_id == "reg1"

        identity_v1 = _record_identity(db, "reg1")
        assert identity_v1 and identity_v1[1] == "reg1"

        # Both surfaces see v1:
        assert _direct_fts_query(db, "xqzALPHA") == [(identity_v1[0],)]
        hits = await mem.search("xqzALPHA", limit=5)
        assert [r.entry.entry_id for r in hits] == ["reg1"]

        # Revision (same entry id → UPSERT → ke_au delete+INSERT):
        await mem.write("xqzBETA revision two body",
                        layer_hint="l1", entry_id="reg1")
        identity_v2 = _record_identity(db, "reg1")

        # Old token gone on BOTH surfaces; new token present on both:
        assert _direct_fts_query(db, "xqzALPHA") == []
        hits = await mem.search("xqzALPHA", limit=5)
        assert [r.entry.entry_id for r in hits] == []
        assert len(_direct_fts_query(db, "xqzBETA")) == 1
        hits = await mem.search("xqzBETA", limit=5)
        assert [r.entry.entry_id for r in hits] == ["reg1"]

        # Identity: the FTS rowid still equals the content row for reg1.
        assert _direct_fts_query(db, "xqzBETA")[0][0] == identity_v2[0]
        assert identity_v2[1] == "reg1"
        assert "xqzBETA" in identity_v2[2]

    @pytest.mark.asyncio
    async def test_multi_revision_regression(self, mem, db):
        for rev in range(6):
            token = f"xqzREV{rev}"
            await mem.write(f"{token} revision body {rev}",
                            layer_hint="l1", entry_id="mr1")
            # every retired revision is gone on both surfaces:
            assert _direct_fts_query(db, f"xqzREV{rev}") == [
                (_record_identity(db, "mr1")[0],)]
            for older in range(rev):
                assert _direct_fts_query(db, f"xqzREV{older}") == []
                api_hits = await mem.search(f"xqzREV{older}", limit=5)
                assert [r.entry.entry_id for r in api_hits] == []
            hits = await mem.search(f"xqzREV{rev}", limit=5)
            assert [r.entry.entry_id for r in hits] == ["mr1"]

    @pytest.mark.asyncio
    async def test_integrity_check_agrees_after_revisions(self, mem, db):
        for rev in range(3):
            await mem.write(f"xqzINTEG rev{rev} body",
                            layer_hint="l1", entry_id="im1")
        conn = sqlite3.connect(db, timeout=20.0)
        try:
            structural = check_structural_integrity(conn)
            retrieval = check_fts_retrieval(conn, tokens=[
                ("xqzINTEG", True),
                ("rev9", False),   # never inserted — must not match
            ])
        finally:
            conn.close()
        assert structural.status == "pass"
        assert retrieval.status == "pass", retrieval.detail


class TestSearchRegressionThroughDelete:
    """Amendment 9 §2: deletion retires the entry. PUBLIC-surface token
    retirement is asserted STRICTLY on every runtime (`search_text`'s
    `ke.rowid = fts.rowid` JOIN filters the dangling index entry on the
    affected build). Direct-FTS retirement after DELETE is
    runtime-scoped — see the dedicated finding test below. The write-side
    revision path (UPSERT, no DELETE) retires on both surfaces: that is the
    strict-both-surfaces class above."""

    @pytest.mark.asyncio
    async def test_delete_removes_identity_and_public_hits(self, tmp_path):
        mem = _memory(tmp_path)
        db = mem._storage.db_path
        await mem.write("xqzRETIRED body one", layer_hint="l1", entry_id="d1")
        assert len(_direct_fts_query(db, "xqzRETIRED")) == 1

        ok = await mem.delete("d1")
        assert ok is True

        # Content-table identity is gone:
        assert _record_identity(db, "d1") is None
        # Public surface retires the token — STRICT, every runtime:
        hits = await mem.search("xqzRETIRED", limit=5)
        assert [r.entry.entry_id for r in hits] == []

    @pytest.mark.asyncio
    async def test_delete_direct_surface_retirement_is_runtime_scoped(
            self, tmp_path):
        from core.memory.sqlite_runtime import classify_wal_safety
        mem = _memory(tmp_path, name="dir.db")
        db = mem._storage.db_path
        await mem.write("xqzRETIRE lone body", layer_hint="l1", entry_id="d2")
        await mem.delete("d2")

        matched = [r[0] for r in _direct_fts_query(db, "xqzRETIRE")]
        if classify_wal_safety().wal_safe:
            # Fixed runtime: the token must vanish from the direct surface.
            assert matched == []
        else:
            # Affected runtime — OBSERVED condition (documented finding):
            # the freed docid still matches. It must at least be fully
            # dangling (no live content row carries that rowid).
            live = _live_rowids(db)
            assert all(rowid not in live for rowid in matched), matched

    @pytest.mark.asyncio
    async def test_independent_entries_remain_retrievable(self, tmp_path):
        mem = _memory(tmp_path, name="ind.db")
        db = mem._storage.db_path
        await mem.write("xqzKEEPALPHA first entry", layer_hint="l1",
                        entry_id="i1")
        await mem.write("xqzKEEPBETA second entry", layer_hint="l1",
                        entry_id="i2")
        identity_i2 = _record_identity(db, "i2")
        await mem.delete("i1")

        # The survivor is untouched on BOTH surfaces (no delete touches
        # rowid 2, so the direct surface stays strict here):
        assert _record_identity(db, "i2") == identity_i2
        assert _direct_fts_query(db, "xqzKEEPBETA") == [(identity_i2[0],)]
        hits = await mem.search("xqzKEEPBETA", limit=5)
        assert [r.entry.entry_id for r in hits] == ["i2"]

        # The deleted entry leaves the PUBLIC surface — strict, every
        # runtime (direct-surface staleness is scoped in the test above):
        hits = await mem.search("xqzKEEPALPHA", limit=5)
        assert [r.entry.entry_id for r in hits] == []

    @pytest.mark.asyncio
    async def test_single_token_terms_on_both_surfaces(self, tmp_path):
        """Controlled alphabetic tokens exactly as Amendment 9 mandates:
        single-word queries with no FTS5 syntax, on both surfaces. No
        DELETE happens in this scenario, so both surfaces are asserted
        strictly; API result order is score-derived (recency beats write
        order for equal importsances), so it is compared set-wise."""
        mem = _memory(tmp_path, name="tok.db")
        db = mem._storage.db_path
        await mem.write("qazword plain body", layer_hint="l1", entry_id="t1")
        await mem.write("wsxword other body", layer_hint="l1", entry_id="t2")

        for token, want in (("qazword", ["t1"]), ("wsxword", ["t2"]),
                            ("plain", ["t1"]), ("body", ["t1", "t2"])):
            direct = _direct_fts_query(db, token)
            assert len(direct) == len(want), (token, direct)
            hits = await mem.search(token, limit=10)
            got = sorted(r.entry.entry_id for r in hits)
            assert got == sorted(want), (token, got)


def _live_rowids(db_path: str) -> set:
    conn = sqlite3.connect(db_path, timeout=20.0)
    try:
        return {r[0] for r in conn.execute(
            f"SELECT rowid FROM {CONTENT_TABLE}").fetchall()}
    finally:
        conn.close()


class TestRuntimeFindingStaleMatchAfterDelete:
    """
    DOCUMENTED FINDING (Amendment 12 disclosure), discovered by the
    Amendment 9 regression work: on SQLite 3.50.4 (the affected build
    bundled with this interpreter — raw probes, independent of this
    repository's code), after a SUCCESSFUL DELETE on an external-content
    FTS5 table the freed docid remains MATCH-findable on the direct
    surface, although `_data` mirror rows are gone, `SELECT count(*) FROM
    fts` returns 0, and the rank=1 integrity-check command reports
    "database disk image is malformed".

    Verified consequences (recorded in the Rev 3 report):
      * stale matches are tied to the freed docid — rows with fresh,
        unrelated content never inherit stale tokens;
      * the PUBLIC search surface (search_text → UnifiedMemory.search) is
        protected by its rowid JOIN and behaves correctly even here;
      * a fixed runtime (>= 3.51.3 or backport) must not show the stale
        direct-surface hit.

    Conditional encoding, same pattern as the mutation-atomicity suite.
    """

    @pytest.mark.asyncio
    async def test_stale_match_after_delete_conditionally(self, tmp_path):
        from core.memory.sqlite_runtime import classify_wal_safety
        verdict = classify_wal_safety()
        mem = _memory(tmp_path, name="finding.db")
        db = mem._storage.db_path
        await mem.write("xqzSTALE one first body", layer_hint="l1",
                        entry_id="f1")
        first_rowid = _record_identity(db, "f1")[0]
        await mem.write("xqzSTALE two second body", layer_hint="l1",
                        entry_id="f2")
        await mem.delete("f1")

        matches = [r[0] for r in _direct_fts_query(db, "xqzSTALE")]
        second_rowid = _record_identity(db, "f2")[0]
        if verdict.wal_safe:
            assert matches == [second_rowid]
        else:
            # Freed docid still matches; live docid still matches; and the
            # stale hit hangs on a docid that has no content row anymore.
            assert first_rowid in matches, matches
            assert second_rowid in matches, matches
            assert first_rowid not in _live_rowids(db)
            # Public surface stays protected (strict, runtime-independent):
            hits = await mem.search("xqzSTALE", limit=10)
            ids = sorted(r.entry.entry_id for r in hits)
            assert ids == ["f2"], ids
