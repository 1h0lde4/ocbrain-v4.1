# OCBrain Architecture Hardening Session — Final Report

**Date:** 2026-06-30
**Builds on:** Session 4 + 4B + 4C (local, uncommitted per explicit instruction — nothing pushed)
**Mandatory architectural decision applied first:** Graph is an Index, not a Memory Layer

---

# PART 0 — Architectural Decision Applied

Before any audit work, the graph-as-index decision was applied:

1. **`core/memory/knowledge_entry.py`** — `LAYERS["l3"]` corrected from `"Graph Memory (entities, relations, knowledge graph)"` to `"Procedural Memory (skills, workflows, procedures)"`. This is not a new opinion — `OCBRAIN_FUTURE_ARCHITECTURE.md` Section 1.1 already describes the existing (already-built) 5-layer system as *"L0 LRU → L1 SQLite+FTS5 → L2 BM25+embeddings → L3 procedural → L4 archive."* The code had drifted from that authoritative document; this restores consistency.
2. **`core/memory/unified_memory.py`** — `write()`'s graph-indexing block changed from `if layer == "l3" and self._graph and entry.is_graph_eligible():` to `if self._graph and entry.is_graph_eligible():`. Graph indexing is now gated purely by eligibility, never by which memory layer stores the entry — matching *"the graph is comparable to: vector index, BM25 index, FTS5 index — not another storage layer."*
3. **`CONTENT_TYPE_ROUTES["entity"]`** — left at `"l2"` (unchanged). Under the new model this was correct all along; only the routing table's own comment was misleading (`# also mutual-indexed in L3 at v4.3.5`, from when L3 meant "graph"). Comment corrected to reflect that graph indexing is orthogonal to routing.

No `GraphLayer`, `L3StorageBackend`, `GraphMemory`, or `GraphRepository` class was introduced — confirmed by test.

**A newly-exposed bug, found while verifying this decision:** graph indexing had *never been reachable* in practice (nothing routes to l3 by default), so the graph-indexing block's own `self._storage.update(entry.entry_id, {"graph_node_id": node_id})` call had never actually executed against a real L0-cached entry. Removing the layer gate made this path reachable for the first time — and immediately exposed that L0 was populated *before* that update ran, so `read()` could return an entry missing `graph_node_id` even though it was correctly persisted and the graph node genuinely existed. Fixed by moving L0 population to after *every* storage mutation `write()` performs (the same principle Session 4C established for `created_at` after UPSERT, now generalized). Verified directly, not just reasoned about — see `TestL0CoherenceForGraphNodeId` in the new test suite.

---

# PART 1 — Composition Root Report

## Initialization Order (`main.py`, actual, traced precisely)

```
main.py: main()
 ├─ Step 1-3: config, logging, module registry (load_all() scans modules/ only)
 ├─ Step 4: modules = load_all()
 ├─ Step 5: (scheduler prep)
 └─ Step 6: from core.orchestrator import Orchestrator
             │
             └─(triggers, as an IMPORT SIDE EFFECT, before Step 6 finishes)─▶
                orchestrator.py's own top-level imports run:
                 from .memory.assembly import context_assembler
                  │
                  └─▶ assembly.py module-level:
                       context_assembler = ContextAssemblyEngine(get_unified_memory())
                       # ^ FIRST call to get_unified_memory() — constructs the
                       #   real UnifiedMemory() singleton right here, as a
                       #   side effect of importing Orchestrator.

    from core.memory.unified_memory import get_unified_memory
    orchestrator = Orchestrator(modules, context_memory, model_router,
                                 memory=get_unified_memory())
                                 # ^ SECOND call — returns the SAME cached
                                 #   instance (get_unified_memory()'s global
                                 #   cache guard: `if _unified_memory is None`).
```

## UnifiedMemory — is only one instance created? ✅ Yes, verified precisely

`get_unified_memory()` (`core/memory/unified_memory.py`) is a correctly-implemented module-level singleton (`global _unified_memory; if _unified_memory is None: _unified_memory = UnifiedMemory(...)`). Two call sites invoke it — `assembly.py`'s module-level `context_assembler` construction, and `main.py`'s explicit call — but both resolve to the *same* object because of the cache guard. Confirmed by direct code read of the caching logic, not assumed.

**Finding (Low severity, documented not fixed):** there are two call sites for what should be one canonical composition-root decision. `assembly.py`'s own docstring defends this explicitly ("composition root creates context_assembler with get_unified_memory()... module level = composition root, not inside any method"), and it is functionally correct. Making `ContextAssemblyEngine` require explicit injection from `main.py` instead would mean re-touching `Orchestrator.__init__`'s signature a fourth time and cascading through test files again, for a style improvement rather than a bug fix. Left as-is.

## Graph Backend — is it registered? ❌ No, confirmed

`register_graph_backend()` is defined on `UnifiedMemory` but never called anywhere in `main.py` or `Orchestrator`. `self._graph` is `None` for the actual running system today. The graph-as-index fix (Part 0) makes graph indexing *correct* whenever a backend is registered, but does not itself register one — that remains a separate wiring decision, appropriately out of this session's "verify, don't invent capability" scope.

## RetrievalFusionEngine — DI, no singleton? ✅ Confirmed correct

`RetrievalFusionEngine.__init__(self, memory: UnifiedMemory)` takes an explicit `UnifiedMemory` parameter with no default and no internal construction. Confirmed via direct source read: no module-level `RetrievalFusionEngine()` instance exists anywhere.

## ContextAssemblyEngine — receives RetrievalFusionEngine correctly? ✅ Yes

`ContextAssemblyEngine.__init__` receives a `UnifiedMemory` and constructs its own `RetrievalFusionEngine(memory)` internally — a legitimate composition pattern (the fusion engine is an implementation detail of assembly, not a separately-shared resource elsewhere).

## Orchestrator — receives ContextAssemblyEngine correctly? Awaits all async retrieval? ✅ Yes

`Orchestrator` imports the module-level `context_assembler` (see composition-root finding above) and calls `await context_assembler.assemble_context(query)` — confirmed `await`ed, confirmed exactly once per `handle()` call (Session 4's own test suite already verifies this).

## EventStream — construction? ❌ Never constructed in production

`get_event_stream()` exists (`core/events/event_stream.py`), correctly implemented as a singleton-cache accessor mirroring `get_unified_memory()`'s pattern — but it is called *nowhere* outside its own file and `core/workers/base.py` (where `AbstractCognitiveWorker.__init__` defaults to it). Since no worker is ever constructed in production (see below), this default is never actually exercised. EventStream is fully built, individually correct, completely disconnected from the running system.

## Worker registration — MemoryCuratorWorker, hooks, governors, lifecycle? ❌ None registered

- `MemoryCuratorWorker()` is constructed in exactly one place: inside its own class docstring, as a "Usage:" example. It is never instantiated in `main.py` or `Orchestrator`.
- `HookRegistry.register_curator()` (the method that would connect a curator to `UnifiedMemory`'s hooks) is consequently never called in production either — the hooks remain unregistered not just "by design pending v4.3.6" as previously documented, but literally because there is no wiring code anywhere that would connect them even if the curator were built today.
- `GovernanceKernel()` is likewise constructed only in its own docstring example; `get_governance_kernel()` (the real singleton accessor) is called nowhere outside `governance_kernel.py` itself and `core/workers/base.py`'s `AbstractCognitiveWorker.__init__` default.
- `AbstractCognitiveWorker` — confirmed via grep across `main.py` and `core/orchestrator.py`: **zero references**. No worker of any type is ever constructed or `.execute()`'d in the production request path.

**This is the single highest-severity finding of the review** (see Part 3, Critical). `Orchestrator.handle()` implements its own bespoke classify→dispatch→merge flow that never touches the worker abstraction — and since `AbstractCognitiveWorker.execute()` is where governance evaluation and event emission actually happen (correctly wired, per direct code read of `core/workers/base.py`), bypassing the worker framework means bypassing governance and event-sourcing *in the primary production hot path*, despite both subsystems being fully built and individually tested (Session 1's `BudgetGovernor` fix; `GovernanceKernel`'s own test coverage).

## Legacy Objects — every occurrence, documented precisely

| Object | File | Construction site | Live in production? | Disposition |
|---|---|---|---|---|
| `MemoryVault` | `core/web_learning/pipeline.py` | `WebLearningPipeline.__init__` | **No** — confirmed via exhaustive grep: `core.web_learning` is imported by nothing else in the repository, and `module_registry.py`'s `load_all()` only scans the unrelated `modules/` directory. **This corrects Sessions 4/4B/4C's own prior assumption** ("the one remaining production write path still using MemoryVault") — it was never live. | Not fixed this session (still real code, still worth migrating eventually, but the urgency assumed by prior sessions was incorrect) |
| `MemoryVault` | `core/meta/health_monitor.py::_check_memory` | bare, discarded, throwaway construction | **Yes** — `Orchestrator._start_background_engines()` does call `health_monitor.start()`, confirmed by direct read of the lifecycle method | **Fixed this session** — replaced with real `UnifiedMemory.stats()`-based check |
| `MemoryVault` | `core/meta/self_model.py::_detect_memory` | `vault = MemoryVault()` | No — `CapabilityDetector.detect()` is never called in production | **Fixed this session** for consistency (was also a self-admitted placeholder + tautology) |
| `CognitiveVault` | `core/memory/cognitive_vault.py` | module-level singleton, `cognitive_vault = CognitiveVault()`, constructed at import time | **Yes**, transitively — imported by `core/memory/consolidation/consolidator.py` | **Disconnected this session** — see below |
| `MemoryConsolidator` | `core/memory/consolidation/consolidator.py` | module-level singleton `consolidator`, started via `Orchestrator._start_background_engines()` | **Yes**, confirmed — ran hourly against `cognitive_vault`, fully disconnected from `UnifiedMemory` | **Fixed this session** — `consolidator.start()`/`.stop()` removed from Orchestrator's lifecycle (see Part 2) |
| `HybridRetriever` | `core/memory/hybrid_retrieval.py` | class definition only | No live consumers (Session 4 removed its only usage from `Orchestrator`; `self_model.py`'s reference to the file was only a `find_spec()` existence probe, itself now fixed) | Not deleted (out of scope; harmless orphan) — capability-detection reference to it fixed |
| `deduplicate_and_merge()` | `core/memory/dedup.py` | free function, takes `vault: MemoryVault` | No callers anywhere in the repository (confirmed by grep in Session 4's own audit, re-confirmed this session) | Not fixed — genuinely dead, zero risk either way, no session has needed to touch it |

## Actual Runtime Dependency Graph (as verified, not as assumed)

```
main.py
  │
  ├─▶ get_unified_memory()  ───────────────────────────┐
  │        (called twice: once as a side effect of      │
  │         importing Orchestrator via assembly.py's     │
  │         module-level context_assembler, once          │
  │         explicitly — same cached instance both times) │
  │                                                        ▼
  │                                                 UnifiedMemory (ONE instance)
  │                                                  ├── SQLiteStorageBackend (L1, always)
  │                                                  ├── InMemoryVectorBackend (L2/L3, in-memory only)
  │                                                  ├── SQLiteArchiveBackend (L4, always)
  │                                                  └── GraphBackend: None  ◀── never registered
  │
  ├─▶ Orchestrator(modules, context, router, memory=<the above>)
  │      ├── self.memory ─── injected, correct
  │      ├── context_assembler ─── module-level import, same UnifiedMemory (verified)
  │      │      └── RetrievalFusionEngine(memory) ─── constructed internally, DI-correct
  │      └── _start_background_engines()
  │             ├── health_monitor.start()  ◀── LIVE, now checks real UnifiedMemory.stats()
  │             └── (consolidator.start() — REMOVED this session)
  │
  ├─▶ GovernanceKernel ─── fully built, tested, never constructed here
  ├─▶ EventStream ─── fully built, tested, never constructed here
  ├─▶ AbstractCognitiveWorker / MemoryCuratorWorker ─── fully built, never constructed here
  └─▶ cognitive_vault / MemoryConsolidator ─── now fully disconnected (was live, now stopped)
```

**If the runtime differs from the "intended" graph** (the one in the new prompt's own illustration, `main.py → UnifiedMemory → RetrievalFusionEngine → ContextAssemblyEngine → Orchestrator`): it differs in exactly one structural way — `ContextAssemblyEngine`/`RetrievalFusionEngine` construction happens as a side effect of importing `Orchestrator`, not as an explicit prior step in `main.py`. Functionally equivalent (verified), structurally less explicit than ideal. Everything else in the illustrated graph — Governance, Workers, EventStream — is simply *absent* from the runtime graph entirely, not miswired; there's no incorrect wiring to fix, only missing wiring to potentially add in a future, dedicated session.

---

# PART 2 — Fix Summary

| File | Change | Architectural reason |
|---|---|---|
| `core/memory/knowledge_entry.py` | `LAYERS["l3"]`: "Graph Memory" → "Procedural Memory" | Matches `OCBRAIN_FUTURE_ARCHITECTURE.md`'s own definition of the existing 5-layer system; graph is not a layer |
| `core/memory/unified_memory.py` | Graph-indexing gate: `layer == "l3" and ...` → `is_graph_eligible()` alone | Mandatory graph-as-index decision — eligibility, not layer, gates indexing |
| `core/memory/unified_memory.py` | `CONTENT_TYPE_ROUTES["entity"]` comment corrected (value unchanged, `"l2"`) | Old comment referenced "L3" as a graph destination, no longer meaningful |
| `core/memory/unified_memory.py` | L0 population moved to after *all* `write()`-time storage mutations, not just the initial L1 write | Newly-exposed cache-coherence bug (see Part 0) — L0 must reflect the fully-completed write, including the graph-indexing block's own separate `storage.update()` |
| `core/meta/health_monitor.py` | `_check_memory()`: `MemoryVault()` throwaway + hardcoded `1.0` → real `get_unified_memory().stats()` check | Confirmed live (runs every 10 min in production); previous check was meaningless by construction |
| `core/meta/self_model.py` | `_detect_memory()`: same fix, same reasoning | Consistency; was a self-admitted placeholder + tautology (`len(vault.entries) >= 0`) |
| `core/meta/self_model.py` | `_detect_retrieval()`: `find_spec()` on orphaned `hybrid_retrieval.py` → check `UnifiedMemory.search` | The capability genuinely moved to `UnifiedMemory.search()` (Session 3B); checking the old file's mere existence checked the wrong thing |
| `core/meta/self_model.py` | Removed now-unused `find_spec` import | No dead imports left behind |
| `core/orchestrator.py` | Removed dead `IterationBudget` construction + `.check()` call; kept the class itself (independently tested) and the `max_iterations` parameter (public API, actively used by call sites) | Confirmed: constructed and checked exactly once per request, can never exceed any `max_iterations ≥ 1` — decorative, not enforcing anything |
| `core/orchestrator.py` | Removed `consolidator` import and its `start()`/`stop()` lifecycle calls | Confirmed live but fully disconnected from `UnifiedMemory` (operated on `cognitive_vault`); migrating it would mean building `MemoryCuratorWorker`'s v4.3.6 logic prematurely — explicitly out of scope, so stopped rather than redirected |
| `tests/test_orchestrator_memory_migration.py` | One assertion updated (unaffected by this session's substance — cascades from Session 4C's own `summary` semantics fix) | N/A — pre-existing from prior session |
| `tests/test_session4b_memory_hardening.py` | Scope-lock test's allowed-file set extended twice more, each time documented | This session legitimately touched `knowledge_entry.py`, `health_monitor.py`, `self_model.py` beyond Session 4B's original scope |
| `tests/test_architecture_hardening_session.py` | **New** — 27 tests | Direct coverage for every change above |

No file was modified beyond what's listed. No governance, EventStream, or worker-framework wiring was implemented (see Part 3 — these are flagged as next-session work, not silently attempted).

---

# PART 3 — Remaining Issues (by severity)

## Critical

1. **Governance and event-sourcing are fully built but structurally disconnected from the production request path.** `GovernanceKernel` (recursion/budget/evolution governors, Session-1-hardened) and `EventStream` (persistent, replayable, pub/sub) both exist, are individually correct, and are even correctly wired *into* `AbstractCognitiveWorker` — but `Orchestrator.handle()` never uses the worker framework, so neither governance nor event-sourcing ever runs for a single production request today. This is a direct LAW 1 / LAW 2 gap in the actual hot path, not a missing feature — the pieces exist. **Why not fixed this session:** wiring this properly means either restructuring `handle()` to route through `AbstractCognitiveWorker.execute()` (a genuine structural rewrite of the core request flow) or hand-wiring direct `governance.evaluate_action()`/`event_stream.append()` calls into `handle()` (which requires designing what "action" a single-pass query handler maps to in governance terms — there's no natural recursion-depth or delegation analog today). Both are consequential, behavior-changing decisions that deserve their own dedicated session with its own test plan, not a corner of an already-large hardening sweep. **Recommended as the top priority for the next session.**

## High

2. **L2 semantic memory has no persistence.** `InMemoryVectorBackend` loses all embeddings on restart — confirmed via direct code read, the class's own docstring already documents this as an accepted Phase-3-to-Phase-5 gap. `OCBRAIN_FUTURE_ARCHITECTURE.md` sequences the Chroma migration at `v4.5.3`, several phases away (after Graph Memory, Memory Curator, Testing & Integration, Retrieval Engine, Instinct→Skill learning). The prompt explicitly forbade a "temporary persistence layer," and a real migration is multi-session-scale work — further underscored by chromadb's demonstrated instability *in this exact environment* (the 5 pre-existing test failures, a version/schema mismatch, present in every regression run throughout Sessions 4 through this one). Implementing this now would mean building on a foundation already shown to be shaky here. **Deferred, not attempted.**
3. **No entity classifier exists anywhere in the codebase.** The routing/graph-indexing fixes in Part 0 make the *pipeline* correct, but there is nothing yet that extracts entities from content and calls `write(content_type="entity", ...)`. This was outside the scope of "verify and fix routing" and would be a genuine new feature (out of scope: "no speculative changes").

## Medium

4. **Composition root has two call sites for `get_unified_memory()`** instead of one canonical point (Part 1). Functionally correct, verified; a style/explicitness improvement, not a bug.
5. **`WebLearningPipeline` is dead code, not a live legacy dependency** — this session's investigation corrects the record left by Sessions 4/4B/4C, which assumed it was live production code needing migration. It is not currently reachable from anywhere. Still worth eventually deciding whether to wire it in (with a `UnifiedMemory`-based rewrite) or formally retire it — but it is not urgent in the way previously documented.
6. **`HybridRetriever`/`hybrid_retrieval.py` is fully orphaned** (zero real consumers). Not deleted this session (no evidence anything still needs it to exist, but deletion wasn't asked for and carries its own small risk of breaking something not yet discovered).

## Low

7. **`core/memory/dedup.py::deduplicate_and_merge()`** has zero callers anywhere. Harmless, dead, not urgent.
8. **`SQLiteGraphBackend` constructs its own `GraphEngine` rather than using `graph_engine.py`'s own `get_graph_engine()` singleton.** Confirmed intentional per that file's own documented guidance for isolated-graph callers — not a bug, just worth naming precisely so it isn't mistaken for an oversight later.

---

# PART 4 — Architecture Validation

| Statement | Status | Evidence |
|---|---|---|
| Graph = Index | ✅ True | Part 0 — verified by direct test (`TestGraphAsIndexDecision`, 7 tests, including a real L1 entry and a real L2 entry both successfully graph-indexed, which was structurally impossible before this session) |
| UnifiedMemory owns all retrieval | ✅ True | `search()` is the only retrieval path in production; `HybridRetriever` (the only alternative) has zero consumers |
| Dependency Injection everywhere | ⚠️ Mostly | `Orchestrator`, `RetrievalFusionEngine`, `ContextAssemblyEngine` all correctly injected. `context_assembler`'s own construction is a module-level singleton (Part 1, Medium #4) — functionally fine, not textbook-explicit |
| No backend bypasses | ✅ True | `Orchestrator` never touches `memory._storage`/`_vector`/`_graph`/`_archive` directly (AST-verified, Session 4C, unchanged) |
| No hidden globals | ⚠️ Mostly | `get_unified_memory()`, `get_governance_kernel()`, `get_event_stream()` are all legitimate, documented, correctly-guarded singletons — not "hidden" in the sense of undocumented magic, but they are globals. `cognitive_vault`'s module-level singleton was actively harmful (Part 2) and is now disconnected from the runtime, not deleted (the class and its file remain, for any future explicit use) |
| One UnifiedMemory instance | ✅ True | Verified precisely (Part 1), not assumed |
| Correct async propagation | ✅ True | No blocking I/O introduced; the new L0-reordering fix and graph-indexing fix are both fully `await`-chained; verified via the full regression run showing no new failures under concurrency-sensitive tests |
| Composition root is consistent | ⚠️ Mostly | One structural imprecision (Part 1, Medium #4) — otherwise consistent and verified |

**What prevents full, unqualified "true" on every line:** the two "Mostly" rows above, both fully explained in Part 1/Part 3 rather than worked around. Per this session's own instruction — *"if anything prevents those statements from being true, identify it explicitly rather than working around it"* — that is exactly what's been done: named precisely, with evidence, and left as a deliberate, reasoned choice rather than silently patched or silently ignored.

---

# Regression Results

Baseline immediately before this session (Session 4C, on top of Session 4+4B pushed to `main` as `6b8b0af`): 380 passed, 5 pre-existing failures (chromadb schema), 1 pre-existing error (stale Session-3B-era import).

After this session: **407 passed, 5 failed, 1 error.** 407 = 380 + 27 (exactly the new suite). Same 5 failures, same 1 error, byte-identical to baseline — confirmed via the complete repository suite (`tests/`, not just the four sessions' own suites run together). No test that constructs an `Orchestrator` broke as a result of removing `IterationBudget` or `consolidator` wiring — confirmed by running the entire suite, not just the tests this session added.

Everything remains local and uncommitted, per the explicit instruction earlier in this engagement to stop pushing until asked again.
