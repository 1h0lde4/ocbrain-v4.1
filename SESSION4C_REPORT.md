# OCBrain Session 4C — Architecture Review & Hardening

**Date:** 2026-06-30
**Scope:** Architecture review of the Session 4B implementation; fix only what is objectively incorrect
**Builds on:** Session 4 + 4B (pushed to `main` as commit `6b8b0af`)

---

## 1. Phase 1 — Architecture Audit

Each of the 8 issues below was evaluated against actual code, not assumption. Three were objectively incorrect and fixed. Five were audited and are architecturally sound as-is; each is justified below and backed by a dedicated deferral test in `tests/test_session4c_architecture.py::TestDeferredIssuesRationale`, so a future session can verify the reasoning still holds rather than re-deriving it from scratch.

### Issue 1 — Misuse of `KnowledgeEntry.summary` → **FIXED**

**Current implementation (before this session):** `summary=query` on every interaction write.

**Correct?** No. `KnowledgeEntry.summary`'s own field comment reads *"LLM-generated in v4.3.6, empty until then"* — it is architecturally reserved for `MemoryCuratorWorker`'s future output. Writing the raw query into it now means the first time the curator runs and calls `update(entry_id, {"summary": ...})`, it silently overwrites the query text with no record that anything was lost — a real semantic corruption, not a style issue.

**Long-term consequence if left as-is:** `MemoryCuratorWorker` (v4.3.6) ships, starts populating summaries, and every interaction entry written before that point loses its query context permanently and silently — no error, no signal, just gone.

**Decision:** Fix now, while the field is still unused by production. The cost of fixing later (after the curator exists) is data loss; the cost of fixing now is one line removed.

**Fix:** `summary` is left empty (`""`, its own default) for interaction writes. The query is preserved in full in `metadata["query"]` instead — machine-readable, available to any future consumer, and explicitly *not* the field the curator is going to write to.

---

### Issue 2 — Retrieval Semantics → **DEFERRED**

**Current implementation:** `content` (the answer) is the only interaction field actively indexed for search; `summary` is empty (post-Issue-1) and `metadata.query` is not FTS5-indexed.

**Correct?** Yes, for the system's current stated purpose. `UnifiedMemory` is a *recall* system — "what does OCBrain know?" — and the answer is what OCBrain knows; the query is what was asked to surface it. Indexing the query too would mean a search for "how do I reset my password" could match an entry whose *answer* is about something unrelated, purely because a past query happened to share vocabulary — the opposite of what search is for here.

**Long-term consequence:** None negative. When `MemoryCuratorWorker` starts populating `summary` with an LLM-generated synopsis, that becomes a second, curated signal automatically layered on top of `content` — no redesign needed, `summary` is already wired into the FTS5 schema and already a `write()` parameter.

**Decision:** Defer. Query-aware / metadata-aware hybrid retrieval is explicitly v4.3.8's job (Cognitive Retrieval Engine, per `OCBRAIN_FUTURE_ARCHITECTURE.md`). Building a bespoke, partial version of it now inside `write()`/`search()` would be exactly the kind of premature complexity Session 4C's constraints forbid ("do not implement unnecessary complexity").

---

### Issue 3 — Stable Interaction Identity → **FIXED**

**Current implementation (before this session):** `entry_id = SHA256(query + answer)`.

**Correct?** No — this is *response* identity, not *interaction* identity, and the prompt's own framing makes the distinction precisely right. A regenerated, retried, or improved answer to the same question changes the hash input, so it gets a brand-new `entry_id` rather than superseding the old one. Concretely: ask "what is OCBrain" three times, get three slightly different phrasings back, and L1 — which is supposed to be *current state* — now holds three parallel rows for the same question. Every one of them remains searchable forever. Retrieval quality degrades exactly in proportion to how often the system self-corrects, which is backwards.

**Long-term consequence if left as-is:** This actively fights v4.3.6 Memory Curator (whose job is partly *contradiction resolution* — but SHA256(query+answer) means "the same question got two different answers" doesn't even register as one entity with two versions; it's just two unrelated entries) and works against Session 4's own stated goal of "UnifiedMemory as the single source of truth" — three rows for one question is not a single source of truth.

**Decision:** Fix now. This is foundational — every session downstream (curator, retrieval engine, replay, analytics) inherits whichever identity model is chosen here, and changing it later means a migration across however much data has accumulated by then.

**Fix:** `entry_id = SHA256(query)` only. Interaction identity is now the *topic* (the question), not the *specific response*. L1 holds exactly one current-state row per query, kept current via UPSERT. L4 archive still records every response ever produced (see Issue 6 — this is the mechanism, not a side effect) — auditability and current-state correctness from the same design, at the cost of nothing.

---

### Issue 4 — L0 Cache Consistency → **FIXED (two distinct bugs)**

**Current implementation (before this session):**
```python
if layer in ("l0", "l1"):
    self._l0.put(entry.entry_id, entry)     # BEFORE storage write
if layer != "l0":
    await self._storage.write(entry)
```

**Correct?** No — two separate, real bugs, both stemming from L0 being populated with the in-memory Python object rather than what actually landed in the database:

1. **Phantom entries on failure.** L0 is populated *before* `self._storage.write(entry)` runs. If storage raises, `read()` would still return a cached hit for a row that was never persisted — the exact "hidden state mutation" §20.4 asks agents to actively hunt for.
2. **Stale `created_at` on UPSERT.** `core/memory/backends/sqlite_storage.py`'s UPSERT deliberately excludes `created_at` from `DO UPDATE SET` (confirmed by reading the schema directly), so the database correctly preserves the original creation time across repeat writes. But L0 was populated with the freshly-constructed Python object's own `created_at` (set at object-construction time, not read from the DB) — so `memory.read(id).created_at` could disagree with `memory._storage.read(id).created_at` after any repeat write, until L0 happened to evict that entry. This is a cache-coherence violation: two code paths to the "same" data returning different answers.

**Long-term consequence if left as-is:** Any consumer trusting `created_at` from a cached read (audit timelines, "how long has OCBrain known this" queries, future replay tooling) gets a silently wrong answer for exactly as long as the entry survives in L0.

**Decision:** Fix now — this is a correctness bug with no valid justification for the current behavior, not an architectural tradeoff to weigh.

**Fix:** L0 population moved to *after* the storage write succeeds. For `l1` entries specifically, after the write, the entry is *reloaded from storage* (`persisted = await self._storage.read(entry.entry_id)`) and that DB-authoritative object — not the original in-memory one — is what goes into L0. A storage failure now leaves L0 untouched for that entry; a successful UPSERT now leaves L0 holding exactly what the database holds.

---

### Issue 5 — Cancellation Safety → **DEFERRED**

**Current implementation:** `SQLiteStorageBackend`'s writes run via `run_in_executor(None, fn)` — the SQL executes synchronously on a thread-pool thread.

**Analysis:** `asyncio.CancelledError` raised against the *awaiting* coroutine cannot interrupt a thread mid-execution. Verified directly (not just reasoned about, in Session 4B): a cancelled `write()` task either (a) the underlying SQL transaction completes cleanly in the background thread regardless of the cancellation, or (b) if cancellation happens before the executor call is even scheduled, nothing ran at all. There is no code path — verified by test — that leaves a *partially written* row. The scenario the issue describes (`L1 stored / L2 skipped / L3 skipped / L4 skipped`) is real, but it isn't a corruption or a partial-write hazard: it's the *existing, intentional* best-effort design for L2–L4, which are already independently wrapped in their own try/except blocks specifically so that a failure (or, equivalently, a task that never gets to run) in any one of them doesn't undo L1. Cancellation just produces the same shape of partial completion that an L2/L3/L4 exception already produces by design.

**Would `asyncio.shield()` help?** No — shielding protects the *shielded coroutine* from being cancelled when its *awaiter* is cancelled, but doesn't change executor-thread semantics, and more importantly would fight the actual architecture: L2/L3/L4 are supposed to be independently best-effort, not bundled into one atomic unit with L1. Adding a transactional boundary across all four layers would be a significant, unrequested redesign (multi-backend distributed transaction / saga pattern) that Session 4B and 4C both explicitly scope out ("do not redesign UnifiedMemory").

**Decision:** Defer, with the reasoning now written down and tested (`test_issue5_cancellation_safety_is_executor_atomic`) so it doesn't need re-litigating. If true atomic all-or-nothing semantics across all four layers become a requirement, that's a `v4.4.8 Durable Workflow Runtime`-scale project (per `OCBRAIN_FUTURE_ARCHITECTURE.md`'s own roadmap), not a Session 4C-scale fix.

---

### Issue 6 — Archive Duplication → **DEFERRED (design confirmed correct)**

**Current implementation:** N writes of the same `entry_id` → 1 L1 row (UPSERT), N L4 archive events.

**Analysis:** This is standard event-sourcing, and — post Issue 3's fix — it's *exactly* the mechanism that makes query-only identity safe. L1 is current-state (one row per topic); L4 is full history (one event per write, forever). Deduplicating L4 would mean losing: how many times a question was asked, how many times an answer was revised, and the ability to reconstruct "what did OCBrain believe at time T" — all things a governed, replayable system (LAW 2) explicitly requires. The prompt asks me to weigh "audit trail vs. duplicate archive growth" — archive growth is a real, eventual operational concern (retention/compaction), but that's a storage-lifecycle question, not a correctness one, and nothing in this session's scope (or Session 4B's) touches storage lifecycle policy.

**Decision:** Defer — current behavior is correct and should not change. If unbounded L4 growth becomes an operational problem, the fix is a retention/archival policy on L4, not deduplication of it.

---

### Issue 7 — Metadata Searchability → **DEFERRED**

**Current implementation:** `metadata` (including `query`, `entities`, `classification_scores`, etc.) is persisted as a JSON blob column, not part of the FTS5 virtual table (`knowledge_entries_fts` indexes `content`, `summary`, `tags` only — confirmed by reading the schema directly).

**Analysis:** Making metadata searchable is a real, plausible future need (e.g., "show me every interaction that used the `knowledge` module"), but it requires actual design work — which metadata fields are searchable, how they're indexed (a second FTS5 table? JSON1 extension queries? a separate structured-query path alongside full-text?), and how results are ranked/fused with content-based results. That design work is squarely `v4.3.8 Cognitive Retrieval Engine` scope per the roadmap document, not something to improvise as a byproduct of a write-path hardening session.

**Decision:** Defer. The data itself is fully preserved (this session confirms it, doesn't just assume it — see Issue 3's fix, which relies on `metadata.query` being present and correct), so nothing is lost by waiting; v4.3.8 will have everything it needs when it's built.

---

### Issue 8 — Logging Strategy → **DEFERRED (current choice confirmed correct for this phase)**

**Current implementation (Session 4B):** backend failures during `write()`/`search()` upgraded from `logger.debug` to `logger.warning`.

**Analysis:** `warning` is the right level *given what exists today*: there is no `HealthMonitor` metrics ingestion, no structured telemetry pipeline, no retry-policy engine listening for these signals (confirmed — grepped for consumers, found none). A log line at `warning` is visible to a human reading logs or running with elevated verbosity, without being mistaken for an unhandled application error (`error`/`critical`). The long-term correct design — these becoming structured metric *events* (count, backend, failure type) that `HealthMonitor` or a future observability layer consumes for retry policy / degraded-mode decisions — requires infrastructure that doesn't exist yet (`v4.4.5 Cognitive Observability Layer` per the roadmap). Upgrading the logging *format* now without a consumer to actually use structured data would just be speculative plumbing.

**Decision:** Defer architecture change; keep `warning` as the correct interim choice. Revisit when `v4.4.5` gives these events somewhere real to go.

---

## 2. Phase 2 — Hidden Architecture Review

Per the prompt's instruction to report only issues "supported by actual code" — this was found through direct testing, not speculation, while validating Issues 1 and 3's fixes.

### Hidden Issue — `ke_au` FTS5 trigger corrupts the database on real content changes

**Discovery path:** Writing the test for Issue 1 (`MemoryCuratorWorker` calling `update()` to set `summary`) raised `sqlite3.DatabaseError: database disk image is malformed` — a genuine SQLite-level corruption, not an application exception. Isolated the root cause with a from-scratch, zero-application-code SQLite reproduction (see investigation trail — over a dozen minimal repros narrowing the exact trigger condition) before touching any fix.

**Root cause:** `core/memory/backends/sqlite_storage.py`'s `ke_au` (`AFTER UPDATE`) trigger used a raw `UPDATE knowledge_entries_fts SET content=new.content, summary=new.summary, tags=new.tags WHERE rowid=old.rowid` against an FTS5 **external content** table. SQLite's own documentation for external-content FTS5 tables specifies updates must be expressed as a delete-then-insert using FTS5's special `'delete'` command — a raw `UPDATE` against the shadow table is not the supported pattern, and this build of SQLite (3.45.1, confirmed via `sqlite3.sqlite_version`) does not handle it safely.

**Two independently confirmed, reproducible symptoms of the same root cause:**

1. **`SQLiteStorageBackend.update()`** (the delta-patch method) — calling it with a genuinely different value for any FTS5-tracked column (`content`, `summary`, `tags`) raised the corruption error directly from the `UPDATE` statement. Reproduced deterministically (5/5 runs) in complete isolation from any application code.
2. **`SQLiteStorageBackend.write()`'s UPSERT path** — did *not* crash, but silently left stale tokens: after writing different content to the same `entry_id` twice, the *old* content remained FTS5-searchable indefinitely, alongside the new content. Confirmed directly against the production class (not just the raw-SQL repro): `search_text("xqzOLDanswer")` still matched after the entry's content had been fully replaced with `"xqzNEWanswer..."`.

**Why this specifically matters for this session's own fixes:** Issue 1's fix explicitly documents "a future curator `update()` call can populate summary" as the intended mechanism — symptom (1) would have corrupted the database the moment `MemoryCuratorWorker` (v4.3.6) made its first real call. Issue 3's fix intentionally makes repeat writes to the same `entry_id` (same question, new answer) the *normal* case — symptom (2) would have silently undermined exactly the "single source of truth" / retrieval-quality guarantee Issue 3 exists to provide, on every single self-correction.

**Fix:** `ke_au` rewritten to the SQLite-documented pattern:
```sql
INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rowid, content, summary, tags)
VALUES ('delete', old.rowid, old.content, old.summary, old.tags);
INSERT INTO knowledge_entries_fts(rowid, content, summary, tags)
VALUES (new.rowid, new.content, new.summary, new.tags);
```
`ke_ai` (INSERT) and `ke_ad` (DELETE) triggers were tested and confirmed *not* affected by this bug class — left untouched.

**Migration:** `SQLiteStorageBackend._init_sync()` now detects a pre-fix trigger definition (`SELECT sql FROM sqlite_master WHERE type='trigger' AND name='ke_au'`, checked for the `'delete'` marker) on every open and transparently replaces it via `DROP TRIGGER` + `CREATE TRIGGER` if needed — verified idempotent (safe to run on every startup) and verified against this repository's own `.data/memory/unified.db`, which had already accumulated the broken trigger from this session's own earlier test runs.

**Scope justification:** `core/memory/backends/sqlite_storage.py` is not one of the two files Session 4B touched, and fixing it goes slightly beyond "the write-path hardening" as literally scoped. I fixed it anyway rather than only reporting it, because: (a) it is an objective, deterministic, data-destroying correctness bug, not an architectural judgment call; (b) it is a direct, foreseeable consequence of this session's *own* Issue 1 and Issue 3 fixes — shipping those fixes while knowingly leaving this bug in place would mean shipping fixes that don't actually work in production; (c) the fix is minimal (2 trigger bodies changed, out of a large file) and uses the pattern SQLite's own documentation prescribes, not a novel design; (d) it touches none of the explicitly-forbidden systems (Governance, EventStream, WorkflowEngine, WebLearning, HealthMonitor, LayerRouter, MemoryCuratorWorker); (e) per the reality-audit mandate embedded in this session's own prompt — "if the repository differs from this prompt: STOP, explain, propose the minimal correction, only continue if in scope" — this is exactly that: explained here, minimal, and in scope because it's required for Issues 1 and 3 to be genuinely correct rather than only appearing correct.

No other hidden issues were found that met the bar of "supported by actual code" rather than speculation — cache coupling, layering, and ownership were all re-examined during this audit and found consistent with the fixes already made.

---

## 3. Phase 3 — Files Modified

- **`core/orchestrator.py`** — `_interaction_id()` changed from `(query, answer)` to `(query)` (Issue 3); production write call no longer passes `summary=query`, query lives exclusively in `metadata["query"]` (Issue 1).
- **`core/memory/unified_memory.py`** — L0 cache population moved to after the storage write succeeds, and reloaded from storage for `l1` entries rather than using the in-memory object (Issue 4, both symptoms).
- **`core/memory/backends/sqlite_storage.py`** — `ke_au` trigger rewritten to the SQLite-documented delete+insert pattern for external-content FTS5 tables, plus a one-time migration for pre-existing databases (Phase 2 hidden issue).
- **`tests/test_orchestrator_memory_migration.py`** — one Session 4 assertion updated: `summary` is no longer asserted to equal the query (now asserted empty); `metadata["query"]` checked instead. This is an assertion Issue 1's fix makes objectively incorrect, not a weakening of the test.
- **`tests/test_session4b_memory_hardening.py`** — Goal 1 tests rewritten for the corrected summary semantics (2 tests); all `_interaction_id()` call sites updated to the new one-argument signature; the Goal 8 scope-lock test extended to allow `sqlite_storage.py` as a third legitimately-touched file, with the reasoning inline.

---

## 4. Phase 4 — Tests Added

**`tests/test_session4c_architecture.py`** — new file, 32 tests:

- `TestIssue1SummaryFieldSemantics` (5) — production write never sets `summary`; query fully preserved in metadata; the field's forward-looking comment is intact; the `summary=` parameter remains available for other callers; a simulated curator `update()` call can populate `summary` without disturbing `metadata["query"]`.
- `TestIssue3InteractionIdentity` (7) — same query → same id regardless of answer; different queries → different ids; format/determinism; a repeat query updates the *existing* L1 row rather than creating a second one; L4 records every answer regardless of L1 collapsing; search surfaces the *latest* answer, not a stale one; an AST check confirming the production call site passes exactly one argument (guards against silently regressing back to two-argument response-identity hashing).
- `TestIssue4L0CacheCoherence` (7) — no phantom L0 entry on a simulated storage failure; L0's `created_at` matches the DB's post-UPSERT (not the fresh object's); `memory.read()` and `memory._storage.read()` agree; L0 correctly excluded for l2/l3 entries; L0 correctly populated immediately for pure-ephemeral l0 entries; coherence holds under 10 concurrent UPSERTs to the same id.
- `TestPhase2HiddenIssueFTS5TriggerBug` (7) — direct regression tests for both symptoms (crash on `update()`, stale tokens on repeat `write()`), a stress test across 6 sequential revisions, a static check that the trigger source uses the documented pattern, a full migration test that hand-builds a pre-fix database and confirms it's transparently upgraded and then actually works, and an idempotency test (reopening an already-migrated database three times).
- `TestDeferredIssuesRationale` (5) — one test per deferred issue (2, 5, 6, 7, 8), each asserting the specific code-level fact the deferral reasoning depends on (e.g., that `summary` remains a live API parameter for Issue 2; that `asyncio.shield` was deliberately not introduced for Issue 5; that archive events are unconditional, not deduplicated, for Issue 6) — so a future session can verify these decisions are still valid mechanically, not just re-read prose.

---

## 5. Regression Results

Baseline immediately before this session (Session 4+4B, on `main`): 348 passed, 5 failed (pre-existing chromadb schema mismatch), 1 error (pre-existing stale import), unchanged from Session 4B's own report.

After Session 4C: **380 passed, 5 failed, 1 error.** 380 = 348 + 32 (exactly the new suite — zero unexpected deltas anywhere else). Same 5 failures, same 1 error, byte-identical to baseline. Confirmed by running:
- `test_session4c_architecture.py` alone (32/32),
- all three session suites together (`test_orchestrator_memory_migration.py` + `test_session4b_memory_hardening.py` + `test_session4c_architecture.py` — 89/89, after fixing the one Session 4B assertion Issue-2-of-scope-tracking made stale),
- the complete repository suite (`tests/` — 380/380 excluding the pre-existing 5+1).

No API regressions (`_interaction_id`'s signature change is internal to `orchestrator.py`, not a public API; `write()`'s parameters are unchanged from Session 4B). No architectural regressions (LayerRouter, MemoryCuratorWorker, HookRegistry all confirmed untouched — same checks as Session 4B, still passing). No performance regressions (the L0 fix adds one `storage.read()` call after every `l1` write — a single indexed primary-key lookup, negligible next to the write itself; the FTS5 trigger fix replaces one `UPDATE` with two `INSERT`s inside the same trigger body, same order of magnitude).

---

## 6. Remaining Limitations

- **L4 archive has no retention policy.** Confirmed correct behavior (Issue 6), but genuinely unbounded — a future session should decide a compaction/retention strategy before this becomes an operational problem, not because the current design is wrong.
- **Metadata is not searchable** (Issue 7, deferred) — by design, pending v4.3.8.
- **Cross-layer write atomicity does not exist** (Issue 5, deferred) — L1 is authoritative and atomic in itself; L2/L3/L4 remain independently best-effort. This is the existing, correct design, not a gap, but worth stating plainly for whoever designs `v4.4.8 Durable Workflow Runtime`.
- **Graph indexing remains structurally unreachable in production** (documented in Session 4B's report, unchanged by this session) — `register_graph_backend()` is still never called anywhere in production code, and fresh entries still default to `truth_status="unknown"`, which `is_graph_eligible()` excludes. Not this session's concern, but still true.
- **This session did not audit `SQLiteStorageBackend` beyond the one trigger bug found.** The Phase 2 review was thorough for the code paths this session's own fixes actually exercise (`write()`, `update()`, `read()`, the FTS5 triggers), but a full independent audit of that file was not performed — it was out of scope, and doing so opportunistically risks exactly the "unrelated refactors" both this prompt and Session 4B's explicitly forbid.

---

## 7. Recommendation for Next Session

Per the prompt: not implementing, listing only.

- Session 5 (unchanged from Session 4/4B's reports): migrate `core/web_learning/pipeline.py` off `MemoryVault.add_entry()` onto `UnifiedMemory.write()`.
- The pre-existing `_fts_escape()` gap (doesn't escape `?`, documented in Session 4B's report) is still unfixed — small, independent, search-layer-only.
- A decision on L4 retention/compaction policy before archive growth becomes operationally relevant.
- Per `PROJECT_INSTRUCTIONS.md` §18.5: once `v4.3.5 Graph Memory`, `v4.3.6 Memory Curator Worker`, and `v4.3.7 Testing & Integration` are complete, a dedicated Documentation Infrastructure session should produce `PROJECT_INDEX.md`, `CURRENT_STATE.md`, `ARCHITECTURE_DECISIONS.md`, `KNOWN_ISSUES.md`, `IMPLEMENTATION_ROADMAP.md`, and `MEMORY_ARCHITECTURE.md` — none of which exist yet (confirmed this session). Not yet, since those prerequisite milestones aren't complete, but flagging it here so it isn't lost.
