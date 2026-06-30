# OCBrain Session 4 — Activate UnifiedMemory as the Production Memory Owner

**Date:** 2026-06-30
**Scope:** `core/orchestrator.py` memory ownership only (per session mandate)
**Tooling used:** graphify v0.8.50 (structural pre-audit), pytest 8.x, manual reality audit

---

## 0. Reality Audit (performed before any code was touched)

Per `PROJECT_INSTRUCTIONS.md` §"repository reality always takes precedence over
documentation," the actual code was audited against the Session 4 prompt's
assumed "CURRENT WRITE PATH" before writing anything.

**Finding: the assumed write path never existed.**

The prompt describes the current write path as:

```
Orchestrator.handle() → MemoryVault.add_entry() → HybridRetriever → vault.json
```

`git log` and `git show` on the first commit of the repository confirm that
`Orchestrator.handle()` has **never**, in any commit, called
`self.vault.add_entry()` or any other persistence method. `self.vault =
MemoryVault()` and `self.retriever = HybridRetriever(self.vault)` were
constructed in `__init__` but were dead weight — held as attributes, never
read or written anywhere in `handle()`. Retrieval already flowed through
`UnifiedMemory` indirectly via `context_assembler.assemble_context()`
(Session 3B), but **no component ever wrote a production interaction to
persistent memory.** `MemoryVault` itself is real and actively used — but
only by `core/web_learning/pipeline.py`, a different subsystem, explicitly
out of scope for this session.

This changes what "replace the legacy write path" mechanically means: there
was no live `add_entry()` call to swap 1:1. Activating UnifiedMemory as the
production memory owner therefore means *adding* the first real write call
Orchestrator has ever made — which is exactly what the session's own
SUCCESS CRITERIA require ("write() called exactly once," "all writes flow
through UnifiedMemory.write()"). I did not stop, because this doesn't
require introducing any excluded system (no Governance, EventStream, or
Workflow needed) — it's squarely the memory-ownership work this session
was scoped for. Flagging it here per the same spirit as the prompt's own
"STOP and explain" instruction, rather than silently treating the prompt's
diagram as ground truth.

One supporting data point: `UnifiedMemory.LayerRouter.CONTENT_TYPE_ROUTES`
already contains an entry for `"interaction" → "l1"` that nothing fed
before this session — i.e., the routing target was pre-provisioned and
unused, consistent with this being the intended (if previously unwired)
behavior rather than a new invention.

`STATUS.md`, `REALITY_AUDIT.md`, and `RECOVERY_REPORT.md` in the repo are
also stale relative to current code in smaller ways (e.g. `REALITY_AUDIT.md`
claims `core/workers/` is "completely missing"; it isn't — `MemoryCuratorWorker`
exists and is tested). Noted for awareness; not in scope to fix.

**Independent structural cross-check (graphify v0.8.50):** a full offline
AST graph was rebuilt after the migration (`graphify update .` — 183 files,
2336 nodes, 4125 edges, no LLM key needed since this repo's 169 code files
need none; the 23 doc files were skipped, semantic community-labeling not
required for this verification). `graphify affected "MemoryVault" --depth 1`
lists every real dependent of `MemoryVault` post-migration: `dedup.py`,
`hybrid_retrieval.py`/`HybridRetriever`, `health_monitor.py`,
`self_model.py`, `web_learning/pipeline.py`, and the two legacy test files —
**`core/orchestrator.py` does not appear.** This corroborates the AST/dynamic
tests below via a second, independent extraction path.

---

## 1. Files Modified

**`core/orchestrator.py`** — the actual migration.
- Removed `from .memory.mem_vault import MemoryVault` and `from
  .memory.hybrid_retrieval import HybridRetriever`.
- Added `from .memory.unified_memory import UnifiedMemory`.
- `__init__` now requires a fourth parameter, `memory: UnifiedMemory`
  (no default — matches the no-fallback constructor-injection pattern
  Session 3A/3B already established in `ContextAssemblyEngine` and
  `RetrievalFusionEngine`). `self.vault` / `self.retriever` are gone;
  replaced by `self.memory: UnifiedMemory = memory`.
- `handle()` gained one new step (6b), after the existing short-term
  `self.context.save(...)` call: `await self.memory.write(content=f"Q:
  {query}\nA: {answer}", content_type="interaction", source="orchestrator",
  importance=0.5, metadata={"modules_used": ..., "entities": ...})`,
  wrapped in its own `try/except` so a memory-layer failure can never turn
  a successful answer into the generic error response (UnifiedMemory's own
  L1 storage write is *not* internally exception-guarded, so this guard
  belongs at the call site).

**`main.py`** (composition root) — now imports `get_unified_memory` and
passes `memory=get_unified_memory()` into `Orchestrator(...)`. This is the
one place in production code allowed to construct/fetch the singleton.

**Five call sites updated for the new required parameter** (mechanical
consequence of the signature change, not a refactor): `tests/test_stress.py`,
`tests/test_fuzz.py`, `tests/break_cancellation.py`, `tests/chaos_monkey.py`,
`tests/phase2_verification.py` (3 inline occurrences). None of these are
pytest-collected (confirmed via `pytest --collect-only`: none match the
`test_*` function-naming pattern pytest requires) — updating them was for
repository hygiene, not regression-suite necessity, since leaving them
broken would violate "preserve backward compatibility when possible."

**New file:** `tests/test_orchestrator_memory_migration.py` (16 tests).

---

## 2. Runtime Changes

**Old (as actually wired in code, not as documented):**
```
User Query → Orchestrator.handle()
                 ├─ self.vault = MemoryVault()        (constructed, never used)
                 ├─ self.retriever = HybridRetriever() (constructed, never used)
                 └─ no persistent-memory write of any kind
```

**New:**
```
User Query → Orchestrator.handle()
                 ├─ await context_assembler.assemble_context(query)   [unchanged, Session 3B]
                 ├─ classify → dispatch → merge → answer              [unchanged]
                 ├─ self.context.save(...)                            [unchanged, short-term]
                 └─ await self.memory.write(content_type="interaction") [NEW]
                          → LayerRouter routes "interaction" → L1
                          → SQLiteStorageBackend (L1 episodic, FTS5)
                          → SQLiteArchiveBackend (L4 event log)
```

---

## 3. Memory Ownership

`UnifiedMemory` is now the only component `Orchestrator` holds a memory
reference to, injected at construction, required (no silent
`get_unified_memory()` fallback inside the class — confirmed by an AST
test that walks `handle()`'s call graph specifically). `MemoryVault` is
untouched and still fully functional — it remains the live, intentional
write target for `core/web_learning/pipeline.py`, which this session was
explicitly told not to migrate. `core/meta/health_monitor.py` and
`core/meta/self_model.py` also still reference `MemoryVault`; both are
"Background engines" / "HealthMonitor," explicitly excluded by the prompt's
STRICT CONSTRAINTS, so left as-is.

---

## 4. Tests Added

All 16 in `tests/test_orchestrator_memory_migration.py`, organized exactly
along the prompt's required categories:

- **Orchestrator (6):** constructor requires `UnifiedMemory` with no
  default; `MemoryVault.__init__` is never invoked when constructing an
  Orchestrator (patched to raise if called); no `vault`/`retriever`
  attributes exist; `memory.write()` is awaited exactly once per `handle()`
  call with `content_type="interaction"`; `context_assembler.assemble_context()`
  is still called exactly once (retrieval untouched); a `memory.write()`
  failure never changes the returned answer.
- **Runtime (2):** a *real* `UnifiedMemory` (tmp-dir backed, not mocked)
  receives the write, the entry lands in L1 with `metadata["content_type"]
  == "interaction"`, FTS5 search surfaces it, and `full_stats()` confirms
  both the L1 write and an L4 archive event were actually created — not
  just that nothing crashed; a live request creates no `vault.json` anywhere.
- **AST (6):** no `MemoryVault`/`HybridRetriever` import anywhere in
  `core/orchestrator.py`'s import graph; no `MemoryVault(...)`/
  `HybridRetriever(...)` call node anywhere in the file; `__init__` has a
  `memory` argument structurally; `UnifiedMemory` is imported;
  `get_unified_memory` is never called from inside `handle()`'s AST subtree.
- **Scope boundary (2):** `core/web_learning/pipeline.py` still references
  `MemoryVault` (confirms the exclusion was honored, not silently dropped);
  `UnifiedMemory.write`/`search` signatures are unchanged from what Session
  3A left them as (confirms `UnifiedMemory` internals weren't touched).

---

## 5. Regression Check

True baseline established by actually running the suite before editing
anything (not by trusting `STATUS.md`, which claims "114 passing" and is
stale): **291 passed, 5 failed, 1 collection error.** The 5 failures are a
chromadb-version/schema mismatch (`KeyError: '_type'`) in
`modules/base.py`'s ChromaDB usage — unrelated to memory/orchestrator,
caused by checked-in `knowledge.db/chroma.sqlite3` fixtures predating the
installed chromadb version. The 1 error is `tests/test_cognitive_memory.py`
importing a `fusion_engine` module-level singleton that Session 3B's own
refactor already removed (`fusion.py` now explicitly has "no module-level
singleton" by design) — a pre-existing casualty of prior work, not this
session's.

**After this session: 307 passed, 5 failed, 1 error.** 307 = 291 + 16
(exactly the new suite, zero unexpected deltas). The same 5 failures and
the same 1 error, byte-for-byte identical to baseline. No new singletons
introduced, no layer violations, no blocking I/O added (the new write call
is `await`ed end-to-end), and `MemoryVault` no longer participates in
Orchestrator's production runtime — confirmed both statically (AST) and
dynamically (patched `__init__` that would raise if called).

One environment note: running the test suite mutates several checked-in
`.data/*.db` files (`.data/memory/graph.db`, `.data/memory/cognitive/vault_v4.json`,
`.data/test_state.sqlite`) as a side effect of pre-existing background
engines (`consolidator`, `health_monitor`) that start on every Orchestrator
construction — this happens with or without this session's changes and was
restored before producing the diff. Worth a `.gitignore` entry in a future
session; not fixed here (out of scope).

---

## 6. Remaining Work (Session 5 — not implemented here)

- Migrate `core/web_learning/pipeline.py` off `MemoryVault.add_entry()` onto
  `UnifiedMemory.write()` — the one production write path this session was
  explicitly told to leave alone.
- `core/meta/health_monitor.py` / `core/meta/self_model.py` still construct
  `MemoryVault()` for health/introspection purposes.
- `tests/test_cognitive_memory.py` still imports the removed `fusion_engine`
  singleton (Session 3B regression, pre-dates Session 4).
- The 5 chromadb-schema test failures in `modules/base.py` are an
  environment/version issue (stale `chroma.sqlite3` fixtures vs. installed
  chromadb) unrelated to memory ownership.
- `.data/*.db` files being checked into git and mutated by test runs is a
  repo-hygiene gap worth a `.gitignore` fix.

None of the above was implemented — listed only, per the session mandate.

---

## Success Criteria — Self-Check

- [x] UnifiedMemory is the production memory owner (Orchestrator's only memory reference).
- [x] Production runtime never writes to MemoryVault (statically + dynamically verified).
- [x] HybridRetriever is no longer used in production (removed entirely).
- [x] All writes flow through `UnifiedMemory.write()` (exactly one per request).
- [x] LayerRouter owns the routing decision (`"interaction"` → `"l1"`, unmodified router).
- [x] Hooks execute correctly (unmodified `HookRegistry`, exercised by the real-`UnifiedMemory` test).
- [x] Archive lifecycle preserved (`full_stats()["l4"]["total_events"] >= 1` verified).
- [x] Retrieval continues working (`context_assembler` call verified unchanged).
- [x] No governance, EventStream, or Workflow introduced.
- [x] No unrelated systems modified (web learning, health monitor, consolidator, graph, LayerRouter, HookRegistry, UnifiedMemory internals all untouched).
