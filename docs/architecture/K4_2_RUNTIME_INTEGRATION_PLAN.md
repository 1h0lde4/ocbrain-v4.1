# K4.2 Cognitive Front-End — Runtime Integration Plan

**Status:** Planning document only. No production code was modified to produce this plan; `main.py` was read in full and not edited. This document exists so a future, dedicated integration task can begin from an informed starting point rather than rediscovering this repository's current structure from scratch.

---

## 1. Current Runtime Entry Point

`main.py`'s `async def main()` is the composition root — it constructs every production singleton and, at Step 12, starts a `uvicorn` server. The actual per-query entry point at runtime is **`Orchestrator.handle()`** (`core/orchestrator.py`), reached via `interface/api.py`'s HTTP routes.

**Critical finding, confirmed by direct reading of `main.py`'s own docstring and Step 6 comments, not assumed:** `Orchestrator.handle()` today wraps every incoming query in a **single-node workflow** built by `core/workflow/definition.py::build_planner_workflow()`, containing exactly one node — the **legacy** `PlannerWorker` (`core/workers/planner.py`) — and runs it through `WorkflowRuntime.execute()`. This is a live, working, already-governed production path (K2.1/K2.2/K2.3), and it is **entirely separate from** K4.2's `plan()` (`core/cognitive/planner.py`). The two share almost nothing: different `PlannerRequest`/`PlannerResult`-shaped types don't even overlap (legacy `PlannerWorker` predates and is unrelated to K4.2's `PlannerRequest`/`PlannerResult`/`ExecutionPlan` dataclasses), and legacy `PlannerWorker` calls `AdapterRuntime` directly rather than going through K4.2's `discover_capabilities()`/`compile()` seam.

This is the single most important fact this plan surfaces: **runtime integration is not "plug K4.2 in" — it requires a decision about how K4.2's pipeline relates to the already-live legacy `PlannerWorker` path** (replace it, run alongside it behind a flag, or something else). This document identifies the decision point; it does not make the decision, per this task's own "planning only" scope.

## 2. Where the Cognitive Front-End Should Connect

The natural seam is `Orchestrator.handle()`'s own entry, where a raw query string is currently handed to `build_planner_workflow()`. A future integration task's realistic options, for the record (not a recommendation — an architectural decision, out of this plan's scope):

- **Option A — Parallel path behind a flag.** `Orchestrator.handle()` gains a config-gated branch: when enabled, route through `interpret_request() → plan() → compile()` instead of `build_planner_workflow()`, then hand the resulting `WorkflowDefinition` to the *same*, already-constructed `WorkflowRuntime.execute()`. Legacy path stays fully intact as the default.
- **Option B — Full replacement.** Retire `build_planner_workflow()`/legacy `PlannerWorker` from the live path once K4.2's pipeline is proven equivalent or superior in production.
- **Option C — Compose, not replace.** Legacy `PlannerWorker` becomes one possible node `compile()` can route to for certain `capability_type`s, rather than the pipeline's own top-level entry.

## 3. Affected Modules

- **`main.py`** — the only file that constructs singletons. Would need: (a) new `worker_registry.register(EvaluatorWorker)`, `.register(ReflectionWorker)`, `.register(SupervisorWorker, constructor_kwargs={"execution_runtime": execution_runtime})` calls, alongside the two existing registrations; (b) a decision about whether `interpret_request()`/`plan()`/`compile()` are called directly from `Orchestrator` or wrapped in their own Worker subclasses first (none currently exist — K4.2's three entrypoints are free functions, not `AbstractCognitiveWorker` subclasses, unlike the three new workers).
- **`core/orchestrator.py`** — `Orchestrator.handle()` is where the actual behavioral branch point (§2 above) would live.
- **`core/workflow/definition.py`** — `build_planner_workflow()` is the legacy single-node builder; unaffected unless Option B/C above is chosen.
- **Nothing under `core/cognitive/` or `core/workers/{evaluator,reflection,supervisor}.py` needs to change** — see §6.

## 4. Initialization Order

No new singletons are required. Every dependency K4.2's functions and new workers need is **already constructed in `main.py` today**, in this order:
1. `memory = get_unified_memory()` (existing)
2. `governance_kernel = get_governance_kernel()`, `event_stream = get_event_stream()` (existing)
3. `capability_registry` with `LLM_COMPLETION` already registered (existing — `_decompose()`/`discover_capabilities()` need nothing new here)
4. `worker_registry`, `execution_runtime` (existing — `SupervisorWorker` needs exactly this `execution_runtime` instance, already available)

The only *new* initialization work is the additional `worker_registry.register(...)` calls in §3(a), which can be inserted immediately after the two existing registration calls with no reordering of anything already there.

## 5. Dependency Flow

```
raw query text
      │
      ▼
interpret_request(text, memory, event_stream)      [needs: memory, event_stream — both exist]
      │  -> List[Goal]
      ▼
PlannerRequest(goal_id=goal.resource_id, goal=goal)
      │
      ▼
plan(request, capability_registry, event_stream)   [needs: capability_registry, event_stream — both exist]
      │  -> PlannerResult (READY_FOR_COMPILATION | IMPASSE | REJECTED_PRECHECK)
      ▼
compile(execution_plan, event_stream, governance)  [needs: event_stream, governance — both exist]
      │  -> CompilationResult (COMPILED | REJECTED | ESCALATED)
      ▼
[NOT YET CONNECTED] WorkflowRuntime.execute(workflow_definition)   [already exists, already works]
      │  -> WorkflowResult
      ▼
EvaluatorWorker.execute(...) -> EvaluationRecord    [needs: memory, event_stream, governance — all exist]
      │
      ▼
ReflectionWorker.execute(...)                       [needs: memory, event_stream, governance — all exist]
      │  (candidate KnowledgeEntry, only if a pattern is detected)
      ▼
SupervisorWorker.execute(...)                        [needs: memory* , event_stream, governance, execution_runtime — all exist]
      (* Supervisor itself has no memory dependency; listed only for completeness of the chain)
```

One real gap, not a K4.2 defect: **`interpret_request()`'s hypothesis generation calls an LLM provider** (`generate_with_fallback`/`resolve_provider`) that gracefully degrades to a low-confidence "novel" hypothesis when unreachable (confirmed in Packet 09's own testing, and this repository's sandbox environment never has a reachable provider). Whether the production deployment target has a working provider configured is an operational question outside this plan's scope, but a future integration task should confirm it explicitly rather than assume it, since the degrade path — while functionally safe — produces lower-quality plans.

## 6. Verification: Integration Requires No Cognitive Front-End Changes

Explicitly checked, not assumed:
- Every one of K4.2's three public entrypoints (`interpret_request()`, `plan()`, `compile()`) already accepts its dependencies as **optional, injectable parameters** defaulting to the existing production singletons (`get_unified_memory()`, `get_event_stream()`, `get_governance_kernel()`) — this was a deliberate design choice in every packet from 01 onward, verified again here by re-reading each signature.
- `EvaluatorWorker`, `ReflectionWorker`, and `SupervisorWorker` are ordinary `AbstractCognitiveWorker` subclasses, matching the exact shape `WorkerRegistry.register()` already knows how to construct (the same pattern `MemoryCuratorWorker` and legacy `PlannerWorker` already use, including `constructor_kwargs` for `SupervisorWorker`'s `execution_runtime`).
- No K4.2 module imports or depends on anything from `core/orchestrator.py` or `main.py` — dependency flow is one-directional (`main.py`/`orchestrator.py` would depend on K4.2, never the reverse), so wiring is purely additive from K4.2's side.

**Conclusion: yes, runtime integration can occur without changing the Cognitive Front-End implementation.** All required changes are confined to `main.py` (registration) and `core/orchestrator.py` (the routing decision in §2) — a future task's estimated blast radius is those two files plus whichever new test/smoke-test files it adds.

## 7. Rollback Strategy

Because integration is additive (§6) and the legacy `PlannerWorker` path remains fully intact regardless of which option in §2 is chosen initially, rollback is low-risk:
- **If behind a flag (Option A):** rollback is flipping the flag back off. No code revert needed.
- **If merged as a direct change:** a single revert commit restores `Orchestrator.handle()`/`main.py` to their current (pre-integration) state; nothing about K4.2's own modules would need to be touched either way, since they were never modified.
- The existing 1094-test suite (unaffected by any integration work, since none of it currently exercises `main.py`/`Orchestrator.handle()`'s wiring) provides an immediate regression signal if a rollback is needed.

## 8. Smoke-Test Strategy

For whichever future task performs the actual wiring:
1. **Composition-root smoke test** — a test that imports and calls enough of `main()`'s construction logic (or a refactored, testable subset of it) to confirm the new worker registrations don't raise at startup.
2. **Parity test** — the same query run through both the legacy single-node path and the new K4.2 path (if Option A/C), asserting both produce a `WorkflowResult` (not necessarily identical output, but both complete without error).
3. **Existing suite as a regression gate** — the full 1094-test suite must stay green throughout; K4.2's own unit/integration tests (`tests/test_integration_full_pipeline.py` and friends) are the direct evidence the *pipeline itself* is correct, so the smoke tests only need to prove *wiring* correctness, not re-prove pipeline correctness.
4. **Manual end-to-end check** — one real query through the running server (`main.py`), inspecting `EventStream` afterward for the expected event trail, mirroring exactly what Packet 09's own tests already verify against synthetic input.

---

This plan is deliberately silent on *which* option in §2 to choose — that is an architectural decision for whoever owns the dedicated runtime-integration task, informed by production requirements (traffic patterns, acceptable risk, whether legacy `PlannerWorker` should be retired at all) that are outside this document's scope.
