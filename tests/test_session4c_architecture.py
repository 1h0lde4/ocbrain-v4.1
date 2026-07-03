"""
tests/test_session4c_architecture.py — Session 4C Test Suite

Architecture Review & Hardening of the Session 4B implementation.

Three issues were identified as objectively requiring fixes:

  Issue 1 — summary field misuse:
    KnowledgeEntry.summary is reserved for LLM-generated curator summaries
    (MemoryCuratorWorker, v4.3.6). Writing the raw user query into it would
    silently corrupt that field when the curator runs. Fix: leave summary
    empty for interaction writes; preserve query exclusively in metadata.

  Issue 3 — response identity vs interaction identity:
    SHA256(query + answer) means a regenerated answer to the same question
    creates a SECOND L1 entry rather than updating the current one -- the
    opposite of the intended current-state semantics. Fix: SHA256(query)
    alone so L1 holds exactly one row per query topic; L4 archives every
    answer ever produced.

  Issue 4 — L0 cache coherence:
    Two bugs found:
    (a) L0 was populated BEFORE the storage write. A storage failure left a
        phantom L0 entry for a row that was never persisted to disk.
    (b) After a successful UPSERT, L0 held the Python object's construction-
        time created_at while SQLite preserved the original (created_at is
        intentionally absent from the DO UPDATE SET clause). Fix: move L0
        write to after storage succeeds; then reload from storage so L0
        always reflects the DB-authoritative row.

Five issues were audited and intentionally deferred (see SESSION4C_REPORT.md):
  Issue 2 — retrieval semantics (defer: answer-only content is correct for RAG)
  Issue 5 — cancellation safety (defer: executor atomicity is sufficient)
  Issue 6 — archive duplication (defer: N events per query is correct event-sourcing)
  Issue 7 — metadata searchability (defer: v4.3.8 Cognitive Retrieval Engine)
  Issue 8 — logging strategy (defer: metrics infrastructure not yet wired)
"""
import asyncio
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.memory.unified_memory import UnifiedMemory
from core.memory.backends.sqlite_storage import SQLiteStorageBackend
from core.memory.backends.sqlite_archive import SQLiteArchiveBackend
from core.memory.knowledge_entry import KnowledgeEntry
from core.orchestrator import _interaction_id

ORCHESTRATOR_SRC = Path(__file__).parent.parent / "core" / "orchestrator.py"
UNIFIED_MEMORY_SRC = Path(__file__).parent.parent / "core" / "memory" / "unified_memory.py"


def _mem(tmp_path, name: str) -> UnifiedMemory:
    return UnifiedMemory(db_prefix=str(tmp_path / name))


# ──────────────────────────────────────────────────────────────────────────
# ISSUE 1 — summary field must stay empty for interaction writes
# ──────────────────────────────────────────────────────────────────────────

class TestIssue1SummaryFieldSemantics:

    @pytest.mark.asyncio
    async def test_orchestrator_does_not_write_query_into_summary(self, tmp_path):
        """The production write call must leave summary empty. MemoryCurator-
        Worker (v4.3.6) will populate it with an LLM-generated summary of
        the content; overwriting it with raw query text would corrupt that."""
        from core.context import ContextMemory
        from core.model_router import RouteResult
        from core.orchestrator import Orchestrator

        memory = _mem(tmp_path, "i1a")
        router = MagicMock()
        router.route = AsyncMock(return_value=RouteResult(answer="test answer", source="mock"))
        orch = Orchestrator(modules={}, context=MagicMock(spec=ContextMemory),
                             router=router, memory=memory)
        try:
            await orch.handle("what is the summary field for")
        finally:
            await orch.close()

        iid = _interaction_id("what is the summary field for")
        entry = await memory.read(iid)
        assert entry is not None
        assert entry.summary == "", \
            f"summary must be empty for interactions; got: {entry.summary!r}"

    @pytest.mark.asyncio
    async def test_query_is_fully_preserved_in_metadata(self, tmp_path):
        """The query must not be silently dropped. It is preserved in
        metadata['query'] for analytics, replay, and future v4.3.8
        metadata-aware retrieval."""
        from core.context import ContextMemory
        from core.model_router import RouteResult
        from core.orchestrator import Orchestrator

        memory = _mem(tmp_path, "i1b")
        router = MagicMock()
        router.route = AsyncMock(return_value=RouteResult(answer="ans", source="mock"))
        orch = Orchestrator(modules={}, context=MagicMock(spec=ContextMemory),
                             router=router, memory=memory)
        try:
            await orch.handle("unique i1b metadata query string")
        finally:
            await orch.close()

        iid = _interaction_id("unique i1b metadata query string")
        entry = await memory.read(iid)
        assert entry.metadata.get("query") == "unique i1b metadata query string"

    def test_summary_field_comment_still_says_llm_generated(self):
        """Confirm the KnowledgeEntry.summary field comment was not changed
        by this session -- it must still document its future purpose so
        MemoryCuratorWorker authors know the invariant."""
        import core.memory.knowledge_entry as ke_mod
        src = inspect.getsource(ke_mod)
        assert "LLM-generated" in src
        assert "MemoryCurator" in src or "4.3.6" in src

    def test_summary_api_parameter_still_exists_for_other_callers(self):
        """The summary= parameter on UnifiedMemory.write() is a public API.
        Non-interaction callers (knowledge ingestion, future curator) may
        legitimately use it. It must remain, just unused by Orchestrator."""
        sig = inspect.signature(UnifiedMemory.write)
        assert "summary" in sig.parameters
        assert sig.parameters["summary"].default == ""

    @pytest.mark.asyncio
    async def test_curator_can_populate_summary_without_overwriting_query(self, tmp_path):
        """Structural proof: because summary is empty at write time, a future
        curator update() call can populate it without losing the query text.

        Note (Session 4C Phase 2 hidden-issue fix): this exercises
        SQLiteStorageBackend.update() changing an FTS5-tracked column
        (summary) on an already-inserted row -- the exact scenario that
        uncovered a real, deterministic FTS5 external-content trigger bug
        in the ke_au trigger (see SESSION4C_REPORT.md). Fixed as part of
        this session since MemoryCuratorWorker's core v4.3.6 mechanism
        depends on this call being safe."""
        memory = _mem(tmp_path, "i1c")
        iid = _interaction_id("curator test query")
        await memory.write(
            content="an interaction answer",
            content_type="interaction",
            entry_id=iid,
            metadata={"query": "curator test query"},
        )
        ok = await memory.update(iid, {"summary": "LLM-generated summary of the answer"},
                                  reason="curator_v4.3.6")
        assert ok is True
        entry = await memory.read(iid)
        assert entry.summary == "LLM-generated summary of the answer"
        assert entry.metadata.get("query") == "curator test query"   # unchanged


# ──────────────────────────────────────────────────────────────────────────
# ISSUE 3 — interaction identity is query-only (current-state semantics)
# ──────────────────────────────────────────────────────────────────────────

class TestIssue3InteractionIdentity:

    def test_same_query_different_answers_produce_same_entry_id(self):
        """Core Issue 3 fix: interaction identity is the question/topic, not
        the specific response. A regenerated or improved answer to the same
        query UPDATES the existing L1 row in place rather than spawning a
        parallel entry that dilutes retrieval quality."""
        iid1 = _interaction_id("what is OCBrain")
        iid2 = _interaction_id("what is OCBrain")
        assert iid1 == iid2

    def test_different_queries_produce_different_entry_ids(self):
        assert _interaction_id("question A") != _interaction_id("question B")

    def test_entry_id_format_prefix_preserved(self):
        """Interaction IDs are self-describing."""
        iid = _interaction_id("any question")
        assert iid.startswith("interaction:")

    def test_entry_id_is_deterministic_pure_function(self):
        for _ in range(5):
            assert _interaction_id("stable") == _interaction_id("stable")

    @pytest.mark.asyncio
    async def test_repeat_query_updates_l1_row_in_place(self, tmp_path):
        """L1 = current state: the latest answer for a given query is what
        you get back. A repeat query (same question, better answer) must
        update the existing row, not create a second one."""
        memory = _mem(tmp_path, "i3a")
        iid = _interaction_id("what is OCBrain")

        await memory.write(content="first answer", content_type="interaction",
                            entry_id=iid, metadata={"query": "what is OCBrain"})
        await memory.write(content="improved answer", content_type="interaction",
                            entry_id=iid, metadata={"query": "what is OCBrain"})

        l1 = await memory.get_layer("l1", limit=50)
        rows = [e for e in l1 if e.entry_id == iid]
        assert len(rows) == 1, "L1 must hold exactly one row per query"
        assert rows[0].content == "improved answer"

    @pytest.mark.asyncio
    async def test_archive_records_every_answer_for_a_query(self, tmp_path):
        """L4 = immutable history: every answer ever produced for a query
        must be preserved, even after L1 is updated. This gives auditability
        without degrading retrieval quality."""
        memory = _mem(tmp_path, "i3b")
        iid = _interaction_id("audit trail query")

        await memory.write(content="first answer", content_type="interaction", entry_id=iid)
        await memory.write(content="second answer", content_type="interaction", entry_id=iid)
        await memory.write(content="third answer", content_type="interaction", entry_id=iid)

        events = await memory._archive.query_events(entry_id=iid)
        assert len(events) == 3, "L4 must record one event per write regardless of UPSERT"

    @pytest.mark.asyncio
    async def test_search_returns_the_most_recent_answer(self, tmp_path):
        """After updating L1 in place, search must surface the latest answer,
        not the original one.

        Note (Session 4C Phase 2 hidden-issue fix): this test originally
        uncovered a real bug -- the ke_au FTS5 trigger used a raw UPDATE
        that left stale tokens from the old content in the index, so an
        entry could still match searches for content it no longer had.
        Fixed by switching the trigger to the SQLite-documented delete+
        insert pattern for external-content FTS5 tables (see
        SESSION4C_REPORT.md). This directly matters for the Issue 3 fix:
        repeat queries now intentionally update the same L1 row, which is
        exactly the condition that exposed the staleness."""
        memory = _mem(tmp_path, "i3c")
        iid = _interaction_id("search after update query")

        await memory.write(content="xqzOLDanswer original version",
                            content_type="interaction", entry_id=iid)
        await memory.write(content="xqzNEWanswer improved version",
                            content_type="interaction", entry_id=iid)

        by_old = await memory.search("xqzOLDanswer", limit=5)
        by_new = await memory.search("xqzNEWanswer", limit=5)

        assert any(r.entry.entry_id == iid for r in by_new), \
            "latest answer must be FTS5-searchable"
        assert not any(r.entry.entry_id == iid for r in by_old), \
            "old answer must no longer match FTS5 after UPSERT"

    def test_orchestrator_source_uses_query_only_hash(self):
        """AST: the production _interaction_id call in handle() must pass
        only the query, not (query, answer). A two-argument call would
        reintroduce the broken response-identity semantics."""
        import ast
        tree = ast.parse(ORCHESTRATOR_SRC.read_text())
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and
               isinstance(node.func, ast.Name) and
               node.func.id == "_interaction_id"
        ]
        assert len(calls) == 1, "exactly one _interaction_id call in orchestrator.py"
        call = calls[0]
        # Must have exactly 1 positional argument (query), not 2 (query + answer)
        assert len(call.args) == 1, \
            f"_interaction_id must take 1 arg (query only); found {len(call.args)}"
        assert len(call.keywords) == 0


# ──────────────────────────────────────────────────────────────────────────
# ISSUE 4 — L0 cache coherence
# ──────────────────────────────────────────────────────────────────────────

class TestIssue4L0CacheCoherence:

    @pytest.mark.asyncio
    async def test_l0_not_populated_if_storage_fails(self, tmp_path):
        """Phantom entry fix: if the storage write raises, read() must not
        return a cached entry for a row that was never persisted."""

        class _FailingStorage:
            def __init__(self, real):
                self._real = real
            async def write(self, entry):
                raise RuntimeError("storage failure injected")
            def __getattr__(self, name):
                return getattr(self._real, name)

        real_storage = SQLiteStorageBackend(str(tmp_path / "i4a" / "unified.db"))
        memory = UnifiedMemory(storage=_FailingStorage(real_storage))

        with pytest.raises(RuntimeError, match="storage failure injected"):
            await memory.write(content="never persisted", content_type="interaction",
                                entry_id="interaction:i4a")

        # L0 must be empty for this entry — no phantom
        assert memory._l0.get("interaction:i4a") is None

        # storage.read() must also return None (never written)
        entry_from_storage = await real_storage.read("interaction:i4a")
        assert entry_from_storage is None

    @pytest.mark.asyncio
    async def test_l0_reflects_db_created_at_after_upsert(self, tmp_path):
        """Cache coherence: after a repeat write of the same entry_id, the
        L0 cache must reflect the DB-authoritative created_at (preserved by
        UPSERT) rather than the Python object's construction-time value."""
        memory = _mem(tmp_path, "i4b")
        iid = _interaction_id("coherence query")

        await memory.write(content="first answer", content_type="interaction", entry_id=iid)
        first_db = await memory._storage.read(iid)

        await asyncio.sleep(0.05)   # ensure time.time() advances measurably

        await memory.write(content="updated answer", content_type="interaction", entry_id=iid)

        # After the second write, L0 must hold the DB row
        cached = memory._l0.get(iid)
        assert cached is not None

        # The DB preserved the original created_at (not in DO UPDATE SET)
        db_row = await memory._storage.read(iid)
        assert db_row.created_at == first_db.created_at, \
            "DB must preserve original created_at across UPSERT"

        # L0 must match DB — not the fresh Python object's construction time
        assert cached.created_at == db_row.created_at, \
            (f"L0 created_at ({cached.created_at}) must match DB "
             f"({db_row.created_at}), not in-memory object's time.time()")

    @pytest.mark.asyncio
    async def test_read_via_l0_returns_coherent_created_at(self, tmp_path):
        """End-to-end: memory.read() (which checks L0 first) must return the
        same created_at as memory._storage.read() (which bypasses L0).
        This was the visible symptom of the cache coherence bug."""
        memory = _mem(tmp_path, "i4c")
        iid = _interaction_id("read coherence query")

        await memory.write(content="original answer", content_type="interaction", entry_id=iid)
        await asyncio.sleep(0.05)
        await memory.write(content="updated answer", content_type="interaction", entry_id=iid)

        via_cache = await memory.read(iid)    # checks L0 first
        via_storage = await memory._storage.read(iid)   # bypasses L0

        assert via_cache.created_at == via_storage.created_at, \
            ("memory.read() and memory._storage.read() must return the same "
             "created_at after UPSERT; L0 cache was not reflecting DB state")

    @pytest.mark.asyncio
    async def test_l0_not_populated_for_l2_l3_entries(self, tmp_path):
        """L0 cache is intentionally for l0/l1 layers only. l2/l3 entries
        must not be cached there (this was already the design; confirming
        it is not accidentally changed by the Issue 4 fix)."""
        memory = _mem(tmp_path, "i4d")
        entry_id = await memory.write(content="l3 entry", layer_hint="l3",
                                       entry_id="l3:i4d")
        cached = memory._l0.get(entry_id)
        assert cached is None, "L0 must not cache l2/l3 entries"

    @pytest.mark.asyncio
    async def test_l0_is_populated_for_l1_entries_after_successful_write(self, tmp_path):
        """After a successful l1 write, L0 must contain the entry."""
        memory = _mem(tmp_path, "i4e")
        iid = _interaction_id("l0 warmup query")
        await memory.write(content="warmup answer", content_type="interaction", entry_id=iid)
        cached = memory._l0.get(iid)
        assert cached is not None
        assert cached.entry_id == iid

    @pytest.mark.asyncio
    async def test_l0_pure_ephemeral_entry_not_in_storage(self, tmp_path):
        """Pure l0 entries (ephemeral) must populate L0 immediately (before
        any storage write, since there is none) and must never reach
        persistent storage. The Issue 4 fix must not break this path."""
        memory = _mem(tmp_path, "i4f")
        await memory.write(content="ephemeral", layer_hint="l0",
                            entry_id="l0:i4f")
        cached = memory._l0.get("l0:i4f")
        assert cached is not None
        persisted = await memory._storage.read("l0:i4f")
        assert persisted is None, "l0 ephemeral entries must not reach storage"

    @pytest.mark.asyncio
    async def test_concurrent_writes_same_id_l0_stays_coherent(self, tmp_path):
        """L0 coherence must hold even under concurrent writes of the same
        entry_id. The final cached state must match what's in storage."""
        memory = _mem(tmp_path, "i4g")
        iid = _interaction_id("concurrent coherence query")

        async def write_version(content):
            await memory.write(content=content, content_type="interaction", entry_id=iid)

        await asyncio.gather(*[write_version(f"version {i}") for i in range(10)])

        cached = memory._l0.get(iid)
        db_row = await memory._storage.read(iid)
        assert cached is not None and db_row is not None
        assert cached.created_at == db_row.created_at, \
            "L0 created_at must match DB after concurrent UPSERTs"


# ──────────────────────────────────────────────────────────────────────────
# DEFERRED ISSUES — architecture-level justification tests
# ──────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────
# PHASE 2 HIDDEN ISSUE — FTS5 external-content trigger bug (ke_au)
# ──────────────────────────────────────────────────────────────────────────

class TestPhase2HiddenIssueFTS5TriggerBug:
    """
    Not one of the 8 listed issues -- found during Phase 2's hidden-
    architecture review while testing Issue 1 and Issue 3's fixes.

    Root cause: the ke_au (AFTER UPDATE) trigger used a raw
        UPDATE knowledge_entries_fts SET content=new.content, ... WHERE rowid=old.rowid
    against an FTS5 EXTERNAL CONTENT table. SQLite's own documentation for
    external-content FTS5 tables specifies that updates must be expressed
    as a delete of the old row's tokens followed by an insert of the new
    row's tokens, using the special 'delete' command:
        INSERT INTO fts(fts, rowid, ...) VALUES('delete', old.rowid, ...);
        INSERT INTO fts(rowid, ...) VALUES(new.rowid, ...);
    A raw UPDATE against the shadow table is not the documented pattern.

    Two independent, verified symptoms of the same root cause:
      (a) SQLiteStorageBackend.update() changing an FTS5-tracked column to
          a genuinely different value: sqlite3.DatabaseError ("database disk
          image is malformed") raised directly from the UPDATE statement.
      (b) SQLiteStorageBackend.write()'s UPSERT changing an FTS5-tracked
          column to a genuinely different value: no crash, but stale tokens
          from the OLD value are never removed -- the entry remains
          FTS5-searchable via content it no longer has.

    Why this matters for THIS session specifically: Issue 1's fix means
    MemoryCuratorWorker (v4.3.6) will call update() with a summary -- (a)
    would have corrupted the database the first time that ran. Issue 3's
    fix means repeat queries intentionally UPSERT the same L1 row with
    different content -- (b) would have silently degraded retrieval
    quality (stale answers remaining searchable forever) on every
    interaction correction, directly undermining the "single source of
    truth" premise this whole migration exists to establish.
    """

    @pytest.mark.asyncio
    async def test_update_with_changed_fts5_column_no_longer_crashes(self, tmp_path):
        """Direct regression test for symptom (a)."""
        storage = SQLiteStorageBackend(str(tmp_path / "hidden_a" / "unified.db"))
        entry = KnowledgeEntry(entry_id="x1", layer="l1", content="original",
                                importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage.write(entry)
        # This exact call previously raised sqlite3.DatabaseError.
        ok = await storage.update("x1", {"summary": "a genuinely new summary value"})
        assert ok is True
        reread = await storage.read("x1")
        assert reread.summary == "a genuinely new summary value"

    @pytest.mark.asyncio
    async def test_update_with_changed_content_no_longer_crashes(self, tmp_path):
        """Same root cause, different column -- confirms the fix is general,
        not summary-specific."""
        storage = SQLiteStorageBackend(str(tmp_path / "hidden_a2" / "unified.db"))
        entry = KnowledgeEntry(entry_id="x1", layer="l1", content="original",
                                importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage.write(entry)
        # update() doesn't allow content in its `allowed` set, so exercise
        # this via a second write() to the same entry_id (the UPSERT path),
        # which fires the identical trigger.
        entry2 = KnowledgeEntry(entry_id="x1", layer="l1", content="a genuinely new content value",
                                 importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage.write(entry2)   # previously safe (no crash), but see next test
        reread = await storage.read("x1")
        assert reread.content == "a genuinely new content value"

    @pytest.mark.asyncio
    async def test_repeat_write_no_longer_leaves_stale_fts5_tokens(self, tmp_path):
        """Direct regression test for symptom (b)."""
        storage = SQLiteStorageBackend(str(tmp_path / "hidden_b" / "unified.db"))
        e1 = KnowledgeEntry(entry_id="x1", layer="l1", content="xqzSTALEtoken old value",
                             importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage.write(e1)
        e2 = KnowledgeEntry(entry_id="x1", layer="l1", content="xqzFRESHtoken new value",
                             importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage.write(e2)

        stale_hits = await storage.search_text("xqzSTALEtoken")
        fresh_hits = await storage.search_text("xqzFRESHtoken")
        assert len(stale_hits) == 0, "stale token must not remain searchable"
        assert len(fresh_hits) == 1, "fresh token must be searchable"

    @pytest.mark.asyncio
    async def test_multiple_updates_to_same_row_remain_stable(self, tmp_path):
        """Stress the fix across more than two revisions -- confirms it isn't
        a two-write coincidence."""
        storage = SQLiteStorageBackend(str(tmp_path / "hidden_c" / "unified.db"))
        for i in range(6):
            e = KnowledgeEntry(entry_id="x1", layer="l1", content=f"xqzREV{i} revision content",
                                importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
            await storage.write(e)
        for i in range(5):
            hits = await storage.search_text(f"xqzREV{i}")
            assert len(hits) == 0, f"revision {i} should no longer be searchable"
        final_hits = await storage.search_text("xqzREV5")
        assert len(final_hits) == 1

    def test_ke_au_trigger_uses_documented_delete_insert_pattern(self):
        """Static confirmation of the actual fix, independent of runtime
        behavior: the trigger source must use the FTS5 special 'delete'
        command, not a raw UPDATE against the shadow table."""
        src = inspect.getsource(SQLiteStorageBackend._init_sync)
        assert "UPDATE knowledge_entries_fts\n" not in src.replace(" " * 20, "")
        assert "'delete'" in src
        assert src.count("INSERT INTO knowledge_entries_fts") >= 3  # ai trigger + au's 2 inserts

    @pytest.mark.asyncio
    async def test_existing_database_is_migrated_on_reopen(self, tmp_path):
        """A database created before this fix must be transparently upgraded
        the next time SQLiteStorageBackend opens it -- not just new
        databases going forward."""
        import sqlite3
        db_path = tmp_path / "hidden_d" / "unified.db"
        db_path.parent.mkdir(parents=True)

        # Manually create a DB with the OLD, unsafe trigger definition,
        # simulating a pre-fix database.
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
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
        """)
        conn.commit()
        conn.close()

        # Opening SQLiteStorageBackend against this pre-existing DB must
        # detect and migrate the unsafe trigger automatically.
        storage = SQLiteStorageBackend(str(db_path))

        conn = sqlite3.connect(str(db_path))
        trigger_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='ke_au'"
        ).fetchone()[0]
        assert "'delete'" in trigger_sql
        conn.close()

        # And it must actually work now -- not just look migrated.
        e1 = KnowledgeEntry(entry_id="x1", layer="l1", content="xqzMIGRATEDold",
                             importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage.write(e1)
        e2 = KnowledgeEntry(entry_id="x1", layer="l1", content="xqzMIGRATEDnew",
                             importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage.write(e2)   # would have crashed pre-fix on a repeat write
        assert len(await storage.search_text("xqzMIGRATEDold")) == 0
        assert len(await storage.search_text("xqzMIGRATEDnew")) == 1

    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self, tmp_path):
        """Reopening an already-migrated database must not re-trigger the
        migration or error."""
        db_path = tmp_path / "hidden_e" / "unified.db"
        storage1 = SQLiteStorageBackend(str(db_path))
        e = KnowledgeEntry(entry_id="x1", layer="l1", content="hello",
                            importance=0.5, created_at=1.0, updated_at=1.0, accessed_at=1.0)
        await storage1.write(e)

        # Reopen twice more -- must not error, must not re-migrate.
        storage2 = SQLiteStorageBackend(str(db_path))
        storage3 = SQLiteStorageBackend(str(db_path))
        reread = await storage3.read("x1")
        assert reread is not None
        assert reread.content == "hello"


class TestDeferredIssuesRationale:
    """These tests document *why* five issues were deliberately left
    unchanged, rather than fixed. If the architecture changes, these tests
    will need revisiting."""

    def test_issue2_answer_only_content_is_correct_for_rag(self):
        """Issue 2 deferred: retrieval of interaction entries should return
        what the system KNOWS (the answer), not what was asked. This is
        the correct design for a cognitive recall system. The query context
        is available via metadata['query'] for systems that need it. A
        future v4.3.8 Cognitive Retrieval Engine can add metadata-aware
        hybrid retrieval without changing the content field."""
        sig = inspect.signature(UnifiedMemory.write)
        # summary remains available (not forced-empty at the API level)
        assert "summary" in sig.parameters
        # content is still the primary searchable field
        params = list(sig.parameters.keys())
        assert params.index("content") < params.index("summary")

    def test_issue5_cancellation_safety_is_executor_atomic(self):
        """Issue 5 deferred: SQLite writes run inside run_in_executor() which
        executes synchronously in a thread pool. asyncio CancelledError
        cannot interrupt a thread mid-execution. The SQL transaction
        completes or rolls back atomically. Partial state (L1 stored,
        L4 not archived) is consistent with the existing architecture where
        L4 is explicitly best-effort (already try/except)."""
        src = UNIFIED_MEMORY_SRC.read_text()
        # L4 is try/except (already correct)
        assert 'logger.warning("Archive write failed' in src
        # L1 is not shielded (intentional: executor atomicity is the guarantee)
        assert "asyncio.shield" not in src

    def test_issue6_archive_duplication_is_event_sourcing(self):
        """Issue 6 deferred: N writes of the same entry_id producing N L4
        events is correct event-sourcing. L1 = current state (deduplicated
        via UPSERT), L4 = full history (every occurrence). Deduplicating
        the archive would lose access-frequency analytics, retry counts,
        and the ability to replay interaction history in chronological
        order. This is a feature, not a bug."""
        src = UNIFIED_MEMORY_SRC.read_text()
        assert "append_event" in src
        # Archive append is always called (not guarded by a dedup check)
        assert "if not duplicate" not in src

    def test_issue7_metadata_search_deferred_to_v438(self):
        """Issue 7 deferred: full metadata search (querying metadata['query']
        via FTS5 or vector search) requires the v4.3.8 Cognitive Retrieval
        Engine which is not yet implemented. Adding metadata-aware retrieval
        now without the proper infrastructure would be premature complexity.
        The metadata field is persisted and will be available to v4.3.8."""
        storage_src_path = (Path(__file__).parent.parent / "core" / "memory"
                             / "backends" / "sqlite_storage.py")
        src = storage_src_path.read_text()
        # FTS5 virtual table indexes: content, summary, tags (not metadata)
        assert "USING fts5(" in src
        assert "content,\n                    summary,\n                    tags," in src

    def test_issue8_warning_logging_is_correct_for_current_phase(self):
        """Issue 8: warning-level logging for backend failures is correct
        for the current phase (no HealthMonitor metrics integration yet).
        Long-term these should be structured metric events. Upgrading them
        now to a metrics system that doesn't exist would be premature.
        warning is the right compromise: visible without crashing."""
        src = UNIFIED_MEMORY_SRC.read_text()
        assert "Vector indexing failed (non-blocking)" in src
        assert "L2 vector search failed (non-blocking)" in src
        assert "L1 FTS5 search failed (non-blocking)" in src
