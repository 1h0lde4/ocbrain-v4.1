# OCBrain Session 4B — Harden the UnifiedMemory Write Path

**Date:** 2026-06-30
**Scope:** `UnifiedMemory.write()` / `search()` hardening + the Orchestrator interaction-write call site only
**Builds on:** Session 4 (uncommitted, local working tree — push intentionally deferred at user's request)

---

## 1. Reality Audit (performed before any code was touched)

Confirmed against actual code, not assumptions:

- The "Q:\n<query>\n\nA:\n<answer>" blob format described in the prompt is
  exactly what Session 4 left in `core/orchestrator.py` — no discrepancy here.
- `KnowledgeEntry.summary` exists, defaults to `""`, and is already part of
  the FTS5 virtual table (`knowledge_entries_fts(content, summary, tags)`,
  `core/memory/backends/sqlite_storage.py`) — but `UnifiedMemory.write()`
  never exposed a way to set it, and grepping the entire repo confirms
  nothing currently reads or writes it (its own comment says "LLM-generated
  in v4.3.6, empty until then"). It is genuinely dormant, not redundant
  with anything active — exactly the "structured payload KnowledgeEntry
  already supports" the prompt asks me to use.
- `core/memory/backends/sqlite_storage.py` does
  `INSERT ... ON CONFLICT(entry_id) DO UPDATE SET ...`, and `created_at` is
  deliberately absent from that `SET` list — first-write time is preserved,
  `updated_at`/`accessed_at` refresh. This is real, working UPSERT
  semantics I can build duplicate detection on without inventing anything.
- **`register_graph_backend()` is never called anywhere in production
  code** (grepped the whole repo — only its own definition). `self._graph`
  is `None` for every `UnifiedMemory` instance the running system ever
  constructs. Graph indexing inside `write()` is dead code today for this
  reason alone.
- Independently, `write()` never sets `truth_status`, so every fresh entry
  defaults to `"unknown"`, and `KnowledgeEntry.is_graph_eligible()` requires
  `"verified"`/`"candidate"`. So even if a graph backend *were* registered,
  graph indexing would still be unreachable from `write()` — a second,
  independent reason. Both are documented below; neither is fixed (Goal 5
  asks me to verify isolation, not to make graph indexing reachable —
  that would be a real feature change, out of scope).
- `search()` already wraps both its L1 and L2 lookups in `try/except`, but
  logs failures at `debug` level — easy to mistake for "isolated" when it's
  closer to "invisible." `write()`'s L1 storage call and L2 vector-index
  call were *not* wrapped at all; L3 graph and L4 archive already were.

No discrepancy required stopping — every gap found was addressable within
this session's stated goals without touching Governance, EventStream,
WorkflowEngine, WebLearning, HealthMonitor, LayerRouter, or
MemoryCuratorWorker.

---

## 2. Files Modified

**`core/memory/unified_memory.py`**
- `write()` gained one new parameter, `summary: str = ""`, threaded into
  the `KnowledgeEntry` constructor. Purely additive — every existing
  caller (Session 3A's tests, Session 4's Orchestrator call before this
  session) keeps working unchanged.
- L2 vector indexing (`self._vector.index(...)`) is now wrapped in
  `try/except`, logged as `"Vector indexing failed (non-blocking)"` —
  brings it in line with the L3/L4 pattern two blocks below it, which were
  already correctly isolated.
- `search()`'s two existing exception handlers (L2 vector search, L1 FTS5
  search) upgraded from `logger.debug` to `logger.warning` — same
  exception handling, just no longer invisible by default.

**`core/orchestrator.py`**
- New module-level pure function `_interaction_id(query, answer) -> str`
  (`hashlib.sha256`, no state).
- The Session 4 write call now passes `content=answer`, `summary=query`,
  `entry_id=interaction_id`, and an enriched `metadata` dict
  (`interaction_id`, `query`, `modules_used`, `entities`,
  `classification_scores`, `timestamp`, `response_length`) instead of the
  single concatenated blob.
- Added `import hashlib, time`.

No other files changed in this session.

---

## 3. Runtime Behavior Changes

**Before (Session 4):**
```
content  = "Q: <query>\nA: <answer>"
entry_id = random uuid4()
metadata = {modules_used, entities}
```

**After (Session 4B):**
```
content     = <answer>                          (primary searchable body)
summary     = <query>                            (secondary searchable label)
entry_id    = interaction:<sha256(query|answer)[:32]>   (deterministic)
metadata    = {interaction_id, query, modules_used, entities,
               classification_scores, timestamp, response_length}
```

Write lifecycle ordering is unchanged: `before_write hooks → L1 storage
→ L2 vector → L3 graph → L4 archive → after_write hooks`. What changed is
which of those steps are fault-isolated (L2 now is; L1 still
intentionally is not — see §5) and what data the entry carries.

---

## 4. Architecture Validation (Goal 8)

- No new singleton: `_interaction_id` is a pure function (AST-verified —
  no `global`/`nonlocal`); confirmed by a dedicated test.
- No layer bypass: `write()` still routes everything through
  `self._router.route(...)`; `LayerRouter.CONTENT_TYPE_ROUTES` is
  byte-for-byte what Session 4 left it (14 entries, `interaction → l1`)
  — verified, not just asserted.
- No private backend access: `core/orchestrator.py` never touches
  `.memory._storage` / `._vector` / `._graph` / `._archive` — AST-checked.
- No duplicate retrieval/storage logic: the only files this session
  touched are `core/orchestrator.py` and `core/memory/unified_memory.py`
  (plus `main.py`, untouched in 4B) — verified via `git diff --name-only`
  inside the test suite itself, not just claimed in prose.
- `core/workers/curator.py` (`MemoryCuratorWorker`) has zero diff against
  `HEAD` — confirmed via `git diff --quiet`, not just "I didn't open it."

---

## 5. Backend Failure Analysis (Goal 5)

| Backend | Before 4B | After 4B | Why |
|---|---|---|---|
| L1 storage | Unprotected, propagates | **Unchanged — still propagates** | Primary layer, not auxiliary. If L1 fails, the entry genuinely was never durably stored; the caller needs to know. Session 4's Orchestrator call site already absorbs this so the user-facing answer is unaffected — that's the correct isolation boundary, not `write()` itself. |
| L2 vector | Unprotected, would propagate | **Now isolated**, logged at warning | Auxiliary enrichment layer; matches the existing L3/L4 pattern it was missing from. |
| L3 graph | Already isolated (try/except) | Unchanged | Already correct. Verified the try/except actually fires under a registered-but-failing backend (had to temporarily patch `GRAPH_ELIGIBLE_STATUSES` for the duration of one test, since fresh entries are never graph-eligible by default — see §1). |
| L4 archive | Already isolated (try/except) | Unchanged | Already correct. |

Verified specifically: storage succeeding while vector, graph, *and*
archive all fail simultaneously still returns a valid `entry_id` and a
readable entry (`test_partial_backend_availability_vector_graph_archive_all_down`).
The debug→warning logging change in `search()` had an immediate, concrete
payoff: it surfaced a real, previously-silent bug — `_fts_escape()`
(`core/memory/backends/sqlite_storage.py`) doesn't escape `?`, so any
search query ending in one raises an FTS5 syntax error that was being
swallowed at debug level. Confirmed this is unrelated to this session
(it's purely a function of the search query text, reproducible against
any pre-existing content) and left unfixed — it's a search-query
sanitization issue, not a write-path one. Documented in §10.

---

## 6. Transaction Analysis (Goal 4)

- FTS5 sync is already atomic with the main row: `AFTER INSERT/UPDATE/DELETE`
  SQL triggers (`ke_ai`/`ke_au`/`ke_ad`) update `knowledge_entries_fts` in
  the same SQLite transaction as the row write — not a separate
  application-level step that could desync. Verified an entry is
  immediately searchable right after `write()` returns.
- Ordering is correct and verified, not just read: with a failing L1
  storage backend, `write()` raises before reaching L4 — confirmed zero
  archive events exist for that `entry_id` afterward. The archive can
  never reference an entry that was never durably stored.
- Cancellation safety: `asyncio.CancelledError` raised against an
  in-flight `write()` does not corrupt storage. The SQL itself runs
  synchronously inside a thread-pool executor (`run_in_executor`) and is
  not actually interrupted by asyncio-level cancellation of the awaiting
  task — so a "cancelled" write either completes cleanly in the background
  or never started; there is no code path that leaves a partial row.
  Verified directly, not just reasoned about.
- One genuine nuance found and **not fixed** (out of scope — it's an L0
  cache-invalidation question, UnifiedMemory internals): `UnifiedMemory.read()`
  checks the L0 LRU cache before storage, and every `write()` call
  repopulates L0 with the freshly-constructed Python object — which has
  its own construction-time `created_at`, not the database's
  UPSERT-preserved value. So on a repeat write of the same `entry_id`,
  `memory.read(id).created_at` can read *fresher* than what's actually
  persisted, until L0 evicts that entry. The database itself is correct
  (verified via `memory._storage.read()` directly); only the cached view
  can briefly disagree with it. Documented in §10.

---

## 7. Concurrency Analysis (Goal 6)

All scenarios run against a real `UnifiedMemory` (temp-dir SQLite, not
mocked):

- **100 concurrent distinct writes** (`asyncio.gather`): all 100 succeed,
  all 100 entry_ids unique, all 100 rows present in L1, `stats()["writes"]
  == 100`.
- **20 concurrent writes of the identical interaction** (same
  `interaction_id`): zero exceptions, all 20 calls return the same
  `entry_id`, exactly **one** L1 row exists afterward (UPSERT collapsed
  them), but the L4 archive recorded all **20** events — duplicate
  detection and full auditability from the same mechanism, simultaneously.
- **20 concurrent writes with the vector backend down** (Goal 5 ×
  concurrency combined): all 20 still land correctly at L1/L3.
- **Cancellation mid-write**: see §6.
- Sequential repeat writes 50ms apart: `created_at` preserved,
  `updated_at` advances — confirms UPSERT semantics hold under realistic
  timing, not just back-to-back calls.

No race conditions, no partial rows, no corrupted FTS5 index observed
across any of the above.

---

## 8. Tests Added

`tests/test_session4b_memory_hardening.py` — 41 tests, organized one
class per goal (`TestGoal1StructuredPersistence` through
`TestGoal8ArchitectureClean`), using real `UnifiedMemory` instances
against temp-dir SQLite wherever the test is about genuine backend
behavior, and lightweight delegating fault-injection wrappers
(`_FailingStorage`/`_FailingVector`/`_FailingGraph`/`_FailingArchive` —
each wraps a real backend and overrides exactly one method to raise) for
the failure-isolation tests. AST checks used for the static architecture
claims (no globals, no private attribute access, routing table
unmodified); runtime checks for everything else, exactly per the prompt's
"use both runtime and AST validation where appropriate."

One pre-existing Session 4 test
(`test_write_called_exactly_once_per_handle`) needed its assertions
updated for the new structured format (`content == "the answer"` /
`summary == "what is OCBrain?"` instead of a substring check against a
concatenated blob) — it was testing behavior this session intentionally
changed, not a regression.

---

## 9. Regression Results

True baseline immediately before this session (Session 4's local state):
**307 passed, 5 failed, 1 error** (the 5 chromadb-schema and 1
stale-import issues are pre-existing and documented in `SESSION4_REPORT.md`
— unrelated to memory/orchestrator, unaffected by this session).

After Session 4B: **348 passed, 5 failed, 1 error.** 348 = 307 + 41
(exactly the new suite — zero unexpected deltas). The same 5 failures and
the same 1 error, identical to baseline. Session 1 (runtime fixes),
Session 2 (graph subsystem), Session 3A (`UnifiedMemory` core, including
its own `test_unified_memory.py`), Session 3B (retrieval), and Session 4
(orchestrator migration, all 16 tests, one updated for the new format as
noted above) all remain green. No API regressions (the only `write()`
signature change is one new optional parameter), no architectural
regressions (LayerRouter, MemoryCuratorWorker, HookRegistry untouched and
verified untouched), no performance regressions (no new blocking I/O —
the one new hashing call is synchronous CPU-bound `hashlib.sha256` on
short strings, negligible next to the existing SQLite round-trips).

---

## 10. Remaining Limitations (found, documented, intentionally not fixed)

- **`_fts_escape()` doesn't handle `?`** (`core/memory/backends/sqlite_storage.py`):
  any search query ending in a literal question mark raises an FTS5 syntax
  error. Pre-existing, reproducible independent of anything written,
  surfaced only because this session's logging fix stopped hiding it at
  debug level. A search-query-sanitization fix, not a write-path one —
  out of this session's scope.
- **L0 cache can return a fresher `created_at` than the persisted row**
  on repeat writes of the same `entry_id`, until that entry is evicted
  from L0 (see §6). The database itself is always correct; only
  `UnifiedMemory.read()`'s cached view can briefly disagree. Fixing this
  would mean changing L0 cache invalidation semantics — UnifiedMemory
  internals, out of scope.
- **Graph indexing remains structurally unreachable in production** for
  two independent reasons (no backend ever registered; fresh entries are
  never graph-eligible). This session verified the *isolation* around
  that code path works correctly if/when it's ever reached, but did not
  make it reachable — doing so would be a feature change (wiring a graph
  backend, or having something set `truth_status`), not hardening.
- **Composite relevance scoring is coarse for L1-only entries**: any
  FTS5-only match gets a flat `bm25_score = 0.5` rather than a graduated
  score (see `unified_memory.py` `search()`), so interaction entries don't
  get fine-grained relevance ranking among themselves — only recency and
  importance differentiate them. Pre-existing, not something Goal 7 asked
  me to redesign.
- This session did not measure write latency before/after under
  realistic load (only correctness/isolation under concurrency) — if
  latency budget matters, that's a benchmarking task, not implied by any
  of the 8 goals.

---

## 11. Recommended Next Session

Per the prompt: not implementing any of this now, listing only.

- Session 5 (already identified in `SESSION4_REPORT.md`): migrate
  `core/web_learning/pipeline.py` off `MemoryVault.add_entry()` onto
  `UnifiedMemory.write()` — the one remaining production write path still
  pointing at the legacy store.
- A small, separate fix for `_fts_escape()`'s `?` handling (search-layer,
  not write-layer).
- A decision on whether L0 cache should invalidate-and-reread from storage
  after a write to the same `entry_id`, or whether the current
  write-time-snapshot behavior is intentional and just needs documenting.
