# Runtime Integration — Feature-Flagged K4.2 Front-End — Completion Report

**Status:** Complete. Implements `docs/architecture/K4_2_RUNTIME_INTEGRATION_PLAN.md`'s recommended Option B (feature flag).
**Baseline:** `v4.2.0-k4.2-cognitive-frontend` (commit `0b5fcbb`)
**Date:** August 8, 2026

---

## Summary

`Orchestrator.handle()` now has a third, flag-gated path: `interpret() → plan() → compile() → WorkflowRuntime.execute() → EvaluatorWorker → ReflectionWorker`, wired through the same governed, injected-dependency object graph every other path already uses. Default off (`config/settings.toml`'s `[runtime] use_k42_frontend = false`); legacy `PlannerWorker` path unchanged and remains production default.

## The `worker_type` Bridge (Task 4)

`core/workers/capability_executor.py`'s `CapabilityExecutorWorker` resolves the gap identified in the Runtime Integration Report (§3 item 7, §6): `compile()` sets `WorkflowNode.worker_type = capability_type` ("llm_completion"), which `WorkerRegistry` couldn't previously resolve. `CapabilityExecutorWorker.worker_type = CapabilityType.LLM_COMPLETION` makes `WorkerRegistry.get("llm_completion")` resolve correctly — the class's own `worker_type` attribute *is* the bridge, requiring no changes to `WorkerRegistry` itself. Delegates to `AdapterRuntime.invoke()`, reusing the exact `CapabilityRequest` shape `PlannerWorker._dispatch_module()` already constructs for the same capability. `compile()`, `Planner`, and `WorkflowDefinition` were not modified, per the task's explicit constraint.

## Files Modified

**New:**
- `core/workers/capability_executor.py` — the worker_type bridge (Task 4)
- `tests/test_runtime_integration.py` — 12 tests (Task 6)

**Modified:**
- `core/orchestrator.py` — two new optional constructor parameters (`capability_registry`, `use_k42_frontend`); one new branch in `handle()`, inserted before the existing `workflow_runtime` branch with zero changes to any existing line (Task 3)
- `main.py` — registers `EvaluatorWorker`, `ReflectionWorker`, `SupervisorWorker`, `CapabilityExecutorWorker` (Task 1); reads the config flag and threads it + `capability_registry` into `Orchestrator`'s construction (Task 3)
- `config/settings.toml` — new `[runtime]` section, `use_k42_frontend = false` (Task 2)

**A genuine ordering bug caught during implementation, not left in:** `SupervisorWorker`'s registration needs `execution_runtime`, which didn't exist as a constructed object at the point I first placed the registration call (`constructor_kwargs` values are evaluated immediately, not lazily). Moved the registration to after `ExecutionRuntime` construction — caught by `py_compile`/import failure before any test ran, not discovered later.

## Reconciliation with Upstream Bug-Hunt Work

Mid-task, 5 upstream commits (N4Z, direct GitHub upload, unrelated audit scope — concurrency, config persistence, system-controller safety, plus two items relevant here) landed on `origin/main`. Reconciled as follows:

1. **Committed this session's own work first** (`28a1097`) as a clean checkpoint, then merged — not the reverse — so the two bodies of work stay individually attributable.
2. **Merged with zero conflicts**, confirmed both by git's own resolution and by inspecting the diffs beforehand: upstream's `main.py` change (3 lines, shutdown-block `config.flush()`) and this session's `main.py` changes (composition root) never touch the same region; `core/workers/evaluator.py`, `core/workflow/runtime.py`, `core/events/event_stream.py` were read and relied upon this session but never modified, so merging them in is a pure update with nothing to reconcile.
3. **The `core/workflow/runtime.py` fix is directly relevant, not incidental**: `ExecutionContext.workflow_id` was previously set to the per-call `instance_id` rather than `definition.workflow_id`. This means `EvaluatorWorker`'s event correlation (`_fetch_workflow_events()`, built in Packet 07) never actually matched real worker-level events before this fix — `tool_success_rate` always fell back to its default. This is a genuine, independently-discovered correctness fix that makes this session's own `CapabilityExecutorWorker` → `EvaluatorWorker` wiring work correctly for the first time, not something in tension with it.
4. **`core/workers/evaluator.py`'s own change** simplifies `_fetch_workflow_events()` to use a new native `payload_workflow_id` query parameter instead of the Python-side post-filtering `_fetch_workflow_events()` used since Packet 07 (documented at the time as a workaround for exactly this missing capability). Accepted as-is — functionally equivalent, and it removes a documented workaround now that the underlying gap it worked around is closed.
5. **Full suite re-verified post-merge**, not assumed safe: `1106/1106` passing (excluding `tests/test_audit_fixes.py`, see below), identical to the pre-merge count — this session's own 12 new tests re-run and re-confirmed against the corrected `workflow_id` semantics, not just re-merged blindly.

## A Discrepancy Found, Not Fixed (Out of Scope)

`tests/test_audit_fixes.py` (uploaded upstream) has 10 failing tests, **none caused by this merge and none in this task's scope to fix**:
- **4 failures (`TestA6ConfigWrites`)**: the test file references `core/config.py`'s `_CRITICAL_STATE_KEYS`, but `core/config.py` itself has a **confirmed zero diff** in the upstream upload (`git diff 0b5fcbb..origin/main -- core/config.py` returns nothing) — the test was uploaded, the corresponding fix was not.
- **6 failures (`TestA7SystemController`)**: same root cause as this entire engagement's 4 already-known, already-accepted `chromadb`-not-installed collection errors — `modules/system_ctrl` transitively imports `modules/base.py`, which imports `chromadb`. Not a new problem; it surfaces as regular test failures here rather than a collection error only because these particular imports happen inside the test methods rather than at module load time.

Per this task's own engineering rules ("if architecture and repository differ: document it, do not fabricate around it"), this is reported, not patched — writing `core/config.py`'s A6 fix would be inventing production code with no specification available in this session, well outside Runtime Integration's scope.

## Validation

- `tests/test_runtime_integration.py`: **12/12 passing**
- Full suite: **1106/1106 passing** (4 pre-existing chromadb errors, unchanged; `test_audit_fixes.py` excluded per the discrepancy above, itself unrelated to this task)
- Feature flag confirmed off by default; flag-off path confirmed byte-for-byte unaffected (no `cognitive.*` events, zero adapter calls, existing K2.2 branch behavior unchanged)
- Governance confirmed firing at both levels (`orchestrator_handle`, `plan_compile`) when the K4.2 path is active
- Event trail confirmed replayable, gapless, non-duplicate sequence numbers for the full multi-stage K4.2 path

## Final Notes for Manual Review

- **Compound requests** (`interpret_request()` returning more than one `Goal`) are handled narrowly: only the first `Goal` is planned/compiled/executed. Multi-goal merge through the K4.2 pipeline is not specified anywhere in the architecture and was not invented here — documented, deferred future work, matching the Runtime Integration Report's own §2 note.
- **`clarification_attempt` is not yet threaded through `Orchestrator`**: a caller-tracked retry count exists in `compile()`'s own signature (Packet 06), but `Orchestrator.handle()`'s new branch calls `compile()` with the default (`0`) every time — a single ESCALATE always surfaces to `SupervisorWorker` rather than being retried with an incrementing count. This is consistent with Supervisor's own documented scope (it doesn't hand a revised plan back to Planner — no such interface exists), but is worth a maintainer's explicit sign-off rather than an implicit default.
- **The A6/A7 gap** (above) should be flagged to whoever owns that audit thread — nothing here blocks Runtime Integration, but `test_audit_fixes.py` will keep failing until `core/config.py`'s actual fix is uploaded.
- **`.pyc` files were committed** as part of the upstream upload (visible in `git diff --stat`) — a minor repository-hygiene item, not touched here as it's outside this task's scope.
