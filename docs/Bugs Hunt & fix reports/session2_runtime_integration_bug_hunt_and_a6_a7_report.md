# OCBrain — Post-Runtime-Integration Bug Hunt + A6/A7 Audit Fixes — Final Report

**Session date:** Aug 12, 2026
**Baseline commit:** `9cd73f8` (Runtime Integration — completion report and merge reconciliation notes)
**Scope:** Adversarial review of the K4.2 Runtime Integration diff (`28a1097`), plus independent investigation and correction of the A6 (Config Writes) and A7 (System Controller) audit findings.

---

## 1. Executive Summary

This session had two independently-attributed halves, per the governing task spec.

**Runtime Integration bug hunt.** Read the actual current code (`core/orchestrator.py`, `core/workers/capability_executor.py`, `main.py`, `core/cognitive/compiler.py`, `core/workflow/runtime.py`, `core/workers/planner.py`, `core/context.py`) against the K4.2 architecture and the Runtime Integration Plan, rather than trusting prior completion reports. Found **one confirmed defect**: interactions processed through the new K4.2 path were never persisted to `UnifiedMemory` or `ContextMemory`, unlike every interaction processed through the existing K2.2 path. Fixed, with a new regression test. Everything else examined (workflow-ID consistency across `ExecutionPlan`/`WorkflowDefinition`/event correlation, multi-goal handling, the `clarification_attempt` parameter, governance layering, the `settings.toml` diff, unsupported-capability handling, worker ephemerality) came back **verified correct or intentionally deferred**, not defective — each with direct evidence, documented below.

**A6/A7 audit fixes.** The upstream report (`docs/Bugs Hunt & fix reports/walkthrough.md`, `final_runtime_integration_audit.md`) claimed both were "VERIFIED AND PRODUCTION-READY" with 86/86 tests passing. This did not match the repository. `core/config.py` had a confirmed zero diff against the pre-upload baseline, and `modules/system_ctrl/module.py` still contained the original `shell=True` vulnerability with no validation function at all. Both were the actual, unfixed defects the original A6/A7 audit findings described. Implemented the real production fixes this session, matching `tests/test_audit_fixes.py`'s exact expectations.

**Incidental finding, not fixed (documented as DEBT-010):** while empirically verifying the A6 fix didn't disturb `tests/test_config.py`, discovered a genuine, timing-dependent race condition in `Config`'s background watcher thread that predates this session (reproduced on **both** pre-fix and post-fix code at a statistically indistinguishable rate — 4/8 vs 6/8 across 8 trials each). Out of scope for A6 (not tested, not requested); the A6 fix was deliberately designed not to add any new writes from the watcher thread so it doesn't make this worse.

---

## 2. Runtime Integration Findings

### RI-1 — CONFIRMED DEFECT: K4.2 path never persists interactions to memory or context

- **Severity:** High
- **File:** `core/orchestrator.py` (fix); `core/workers/capability_executor.py` (where the gap was confirmed absent, correctly, by design)
- **Root cause:** The K2.2 legacy path gets interaction persistence "for free" because `PlannerWorker._run()` internally calls `self._memory.write(content_type="interaction", ...)` and `self._context_memory.save(...)` (`core/workers/planner.py`, Steps 7–8) — and `PlannerWorker` is constructed in `main.py`'s composition root with the *exact same* `memory`/`context_memory` singleton objects `Orchestrator` itself holds (confirmed by direct reading of `main.py` lines ~295–312, including its own comment explaining this deliberately-shared-object design). `CapabilityExecutorWorker`, the new worker Runtime Integration introduced to execute a compiled K4.2 `WorkflowNode`, is deliberately narrow by its own module docstring — a single compiled-step executor, not a whole-query handler — and correctly has no memory/context wiring of its own (confirmed: its `__init__` doesn't accept a `memory` parameter, its `_run()` never references memory or context). Nothing else in the K4.2 branch of `Orchestrator.handle()` filled the gap either (confirmed via `grep -n "memory\.write\|context\.save\|context_assembler" core/orchestrator.py` — all matches were in the old, non-production "Legacy Compatibility Bridge" branch and the K2.2 branch's indirect path through `PlannerWorker`, none in the new K4.2 branch).
- **Evidence:** `grep` of the K4.2 branch's line range (pre-fix: 261–380) for `memory.write`/`context.save`/`context_assembler` returned zero matches. `EvaluatorWorker`/`ReflectionWorker` write `content_type="evaluation"`/`"reflection"` respectively, confirmed distinct from `"interaction"` — so this is a genuine gap, not a duplicate-avoidance design choice.
- **Impact:** Every K4.2-processed query would be invisible to memory-based retrieval (`context_assembler.assemble_context()`, semantic search over past interactions) and to short-term conversational continuity (`ContextMemory`), while every K2.2-processed query is not. Silent, no exception raised — the response itself is unaffected, only downstream memory/context state.
- **Fix:** Added a `self.context.save(query, capability_types, answer, {})` call and a non-blocking `await self.memory.write(content_type="interaction", source="orchestrator_k42", entry_id=interaction_id, ...)` call (wrapped in try/except, logging a warning on failure — matching the existing convention for this call elsewhere in the file) to the K4.2 branch's success path in `core/orchestrator.py`, immediately before the existing `shadow_learner.record_interaction(...)` call. Mirrors `PlannerWorker`'s own pattern exactly, including which object attributes are shared and which failures are non-blocking.
- **Test:** New test `tests/test_runtime_integration.py::TestMemoryWrites::test_interaction_persisted_to_memory_and_context`, which runs a full K4.2 request and asserts the resulting `KnowledgeEntry` (read back via `memory.read(interaction_id)`) has `source == "orchestrator_k42"` and `content == answer`, and that `orchestrator.context.save` was called once with the right query/answer. Also required fixing the shared test fixture (`_build_runtime_stack`) — `Orchestrator.context` was previously stubbed as a bare `object()` (no methods at all), which is why no existing test caught this gap; it needed a real `.save()` method to exercise once the code path existed, so it's now `MagicMock()`. This is a fixture completion, not a weakened assertion — no existing assertion in the file was touched.

### RI-2 — VERIFIED CORRECT: workflow-ID consistency (`ExecutionContext.workflow_id`)

- **Severity:** N/A (not a defect)
- **Files:** `core/cognitive/compiler.py`, `core/workflow/runtime.py`, `core/orchestrator.py`
- **Finding:** The task background specifically asked me to re-verify a previously-discovered `ExecutionContext.workflow_id` bug. Traced the full chain directly: `_compile_workflow()` sets `WorkflowDefinition(workflow_id=plan.resource_id, ...)` (`compiler.py:245`) — so `execution_plan.resource_id` and the compiled workflow's own ID are the same value by construction, not by convention. `WorkflowRuntime.execute()` then uses `definition.workflow_id` consistently for every event it emits and for `ExecutionContext(workflow_id=workflow_id, ...)` (`runtime.py`, 6 separate call sites checked, all consistent, with an explicit comment confirming this is the intended, corrected design: `"workflow_id = definition.workflow_id (canonical, matches..."`). `Orchestrator.handle()`'s call to `EvaluatorWorker`/`SupervisorWorker` with `workflow_id=execution_plan.resource_id` therefore does correctly match the ID used by all worker/workflow events for that execution. Confirmed correct, not reopened.

### RI-3 — VERIFIED INTENTIONAL: only the first `Goal` is planned/compiled/executed

- **Severity:** N/A (documented deferral, not a defect)
- **Files:** `core/orchestrator.py`, `core/cognitive/intent.py`
- **Finding:** `Orchestrator.handle()`'s K4.2 branch does `goals = await interpret_request(...); goal = goals[0]`. Verified this can never raise `IndexError`: `form_goals()`'s only fallback when no compound-request pattern is detected is `_split_compound_goals()` returning `[text]` — a guaranteed non-empty list — so `goals` is never empty. Verified the single-goal restriction itself is explicitly documented in-code as deferred, matching `IMPLEMENTATION_TRACKER.md`'s own notes that capability *selection*/multi-goal orchestration is reserved for the future Cognitive Runtime (C-MoE). Not implemented, per the task's explicit instruction not to invent multi-goal execution.

### RI-4 — VERIFIED INTENTIONAL: `compile(..., clarification_attempt=0)` every call, no Planner↔Supervisor feedback loop

- **Severity:** N/A (documented deferral, not a defect)
- **File:** `core/cognitive/compiler.py`
- **Finding:** `compile()`'s own docstring (lines ~299–304) states this parameter "exists so a future caller (SupervisorWorker, Packet 08 — not built by this packet) can call compile() again for a revised plan with an incrementing attempt count" and explicitly notes `compile()` itself is stateless. `Orchestrator.handle()` never passes this argument explicitly (relies on the default), which is the only correct behavior available today, since no caller anywhere implements the revision loop this parameter is reserved for. Left unimplemented, per the task's explicit instruction not to invent a Planner↔Supervisor feedback loop.

### RI-5 — VERIFIED BENIGN: the 225-line `config/settings.toml` diff

- **Severity:** N/A (not a defect)
- **File:** `config/settings.toml`
- **Finding:** The diff looked disproportionate for adding one `[runtime]` section. Traced it to `tomli_w.dump()` re-serializing the whole file with LF line endings, replacing the original's CRLF — every line shows as changed for that reason alone. Confirmed via a section-header diff between the pre-integration tag (`0b5fcbb`) and the current file: identical section set except for the one legitimate addition, `[runtime]` with `use_k42_frontend = false`. No data loss.

### RI-6 — VERIFIED CONSISTENT: governance layering

- **Severity:** N/A (not a defect)
- **File:** `core/orchestrator.py`
- **Finding:** One top-level governance evaluation at the start of `handle()` applies uniformly to both the K2.2 and K4.2 branches; `compile()` has its own additional `plan_compile` gate deeper in the pipeline. This is the same layered pattern already established and justified for the K2.2 path (top-level gate + `PlannerWorker.execute()`'s own gate) — not a second, competing governance authority. Confirmed via `tests/test_runtime_integration.py::TestGovernance`, both tests (`test_orchestrator_level_gate_still_fires_for_k42_path`, `test_compile_gate_fires_within_k42_path`) passing independently.

### RI-7 — VERIFIED SAFE: unsupported-capability and worker-ephemerality handling

- **Severity:** N/A (not a defect)
- **Files:** `core/capabilities/adapter_runtime.py`, `core/runtime/execution_runtime.py`
- **Finding:** `AdapterRuntime.invoke()` returns `CapabilityResult(success=False, error=...)` for an unregistered capability type rather than raising; `CapabilityExecutorWorker._run()` correctly checks `result.success` and returns a failed `WorkerResult` without crashing. Separately, confirmed `ExecutionRuntime.invoke()` constructs a brand-new worker instance per call (`# ── Step 2: Construct Worker instance (ADR-003: ephemeral) ───`) — `CapabilityExecutorWorker` is registered through the same mechanism as every other worker, so it inherits this pre-existing, already-decided ephemerality guarantee. No shared-mutable-state risk introduced.

---

## 3. A6 Findings — Config Writes

- **Original defect:** `core/config.py`'s `set_module_state()` wrote `models.toml` to disk synchronously, holding `self._lock`, on every call — including on the request hot path via `ModelRouter._increment_query_count()`.
- **Root cause of *this session's* work:** The upstream "verified" report did not match the repository. `tests/test_audit_fixes.py::TestA6ConfigWrites` imports `core.config._CRITICAL_STATE_KEYS`, which did not exist; `Config` had no `_models_dirty` attribute; `git diff` from the pre-upload baseline to `core/config.py` was empty. None of the described fix had actually landed in production code, despite the walkthrough's specific (and, it turned out, fabricated) claims about its implementation.
- **Correction:** Added a module-level `_CRITICAL_STATE_KEYS = frozenset({"stage", "bootstrap_model", "base_model", "active_weights"})` — the two keys the test requires present (`stage`, `bootstrap_model`) plus two more in the same identity/lifecycle category (as opposed to `query_count`/`maturity_score`, which the test requires *absent*, and which are exactly the frequently-written counters the original finding was about). `set_module_state()` now persists immediately only for critical keys; everything else updates in-memory immediately and sets a new `_models_dirty` flag. Added `flush()` to persist deferred state on demand — which `main.py`'s shutdown path already called (`_cfg.flush()`, part of the same partial upload that added the test file, so it was a latent `AttributeError` waiting to happen at process shutdown until this fix). Deliberately did **not** add a periodic auto-flush from the pre-existing background watcher thread, or a flush-before-reload in `_load_all()` that writes — see DEBT-010 below for why; instead used a read-only skip-reload-if-dirty guard in `_load_all()`, which protects the same "don't silently discard a deferred write" property without adding any new write path a background thread could race on.
- **Tests:** `tests/test_audit_fixes.py::TestA6ConfigWrites` — 4/4 passing. `tests/test_config.py` — 7/7 passing (in isolation; see DEBT-010 for the pre-existing, unrelated flakiness risk when run immediately after `TestA6ConfigWrites` in the same process).

---

## 4. A7 Findings — System Controller

- **Whether production or environment:** **Production.** Not an environment artifact. `modules/system_ctrl/module.py`'s `_open_app()` still contained `subprocess.Popen(cmd, shell=(SYSTEM == "Windows"))` with `cmds["Windows"] = ["start", target]` and zero input validation — the exact shell-injection vulnerability the original A7 finding described (e.g. a target of `"notepad & del /f /q C:\\"` would execute the second command on Windows). `_validate_open_target` did not exist anywhere in the file.
- **Root cause:** Same partial-upload gap as A6 — the upstream walkthrough described this fix in detail (including code that closely resembles what was ultimately implemented this session) but it never reached `modules/system_ctrl/module.py` in the actual repository.
- **Correction:** Added `_validate_open_target()` — a character-allowlist validator (`^[A-Za-z0-9._~:/-]+$`, deliberately an allowlist rather than a metacharacter blocklist, since a blocklist can miss novel injection vectors) plus explicit rejection of empty and flag-like (leading `-`) targets. Rewrote `_open_app()` to call this validator first, then use `os.startfile()` on Windows (no shell involved at all) instead of `subprocess.Popen(..., shell=True)`; Linux/macOS already used safe argv-list `subprocess.Popen()` calls and are otherwise unchanged.
- **Tests:** `tests/test_audit_fixes.py::TestA7SystemController` — 6/6 passing, including the AST-level check that no `subprocess` call anywhere in `_open_app`'s source has `shell=True` as a literal. Confirmed via `grep` across the repository that no other test or call site depends on `_open_app`'s previous signature/behavior.

---

## 5. Architecture Compliance

- **K4.2 architecture:** Unmodified. No K4.2 packet contract (`interpret()`/`plan()`/`compile()` public surface, `CompilationResult`/`CompilationStatus` types, `ExecutionPlan`/`WorkflowDefinition` shapes) was touched. The one Runtime Integration fix (RI-1) operates entirely at the Orchestrator level, matching where the equivalent K2.2 behavior lives structurally (`PlannerWorker`, not a K4.2 packet).
- **Runtime Integration Plan:** Consistent with the "Option A — parallel path behind a flag" design it specifies; the feature flag still defaults `false`; the K2.2 branch's source is byte-for-byte unchanged.
- **Governance boundaries:** Unchanged; RI-6 confirms no new governance authority was introduced.
- **Memory boundaries:** RI-1's fix uses `UnifiedMemory.write()` (the single governed write path) exclusively — no second memory-writing mechanism was introduced, consistent with the project's "Learning is evidence, never logic" and single-write-path principles.
- **Execution boundaries:** `CapabilityExecutorWorker` remains unmodified and stays within its documented single-step-executor scope; RI-1's fix was deliberately placed at the Orchestrator level rather than inside it, for exactly that reason.

---

## 6. Files Changed

**Runtime Integration:**
- `core/orchestrator.py` — interaction persistence fix (RI-1)
- `tests/test_runtime_integration.py` — new regression test + fixture fix (`context` stub: `object()` → `MagicMock()`)

**A6:**
- `core/config.py` — `_CRITICAL_STATE_KEYS`, `_models_dirty`, `set_module_state()`, `flush()`, `_persist_models()`, `_load_all()` dirty-guard, `register_module()` now reuses `_persist_models()`

**A7:**
- `modules/system_ctrl/module.py` — `_validate_open_target()`, rewritten `_open_app()`, `os`/`re` imports added

**Tests:** (see above — no separate test-only files; test changes are bundled with their respective scope above since each is a direct regression test/fixture fix for that scope's production change)

**Documentation:**
- `CURRENT_STATE.md` — Runtime Integration + bug-hunt status, Cognitive Workers table (4 new workers), corrected "still not wired" language
- `KNOWN_ISSUES.md` — DEBT-010 added; A6/A7/RI-1 resolved entries added; DEBT-002 corrected (SupervisorWorker exists but still doesn't populate `delegating_worker_type`); stale Future Cognitive Workers table corrected
- `docs/Bugs Hunt & fix reports/session2_runtime_integration_bug_hunt_and_a6_a7_report.md` — this report

---

## 7. Validation

```
Runtime Integration: 13/13   (12 pre-existing + 1 new regression test)
A6:                   4/4
A7:                   6/6
Full suite:        1112/1146 passed, 34 failed

Baseline (before this session): 1101/1145 passed, 44 failed
```

The 34 remaining failures are **environment-only**, not production defects, and are the exact same 34 (by file and test name) present in the baseline before any fix in this session — confirmed by full-traceback inspection of a representative sample from every affected file. Every one traces to this sandbox's network policy not permitting access to `huggingface.co`, needed by:
- `core/classifier_v3.py::classify()` (via `core/learning/similarity.py`) — used by `PlannerWorker._run()` and the K2.2 legacy branch of `Orchestrator.handle()`
- `modules/base.py`'s `Module.__init__()` → chromadb collection's default embedding function — used by any `Module()` subclass instantiation, including `system_ctrl`'s own non-`test_audit_fixes.py` test file

This affects only the K2.2/legacy-path test files (`test_k2_2_runtime_migration.py`, `test_planner_worker.py`, `test_orchestrator_memory_migration.py`, `test_planner_capability_migration.py`, `test_session4b_memory_hardening.py`, `test_session4c_architecture.py`, `test_break_concurrency.py`, `test_break_empty_db.py`, `test_phase2.py`, `test_system_ctrl.py` — none of which are in this session's Runtime Integration or A6/A7 scope) and does not affect `tests/test_runtime_integration.py`, which never touches `classify()` or instantiates a `Module()`. Both fixed scopes (A6/A7, RI-1) were fully executed and verified with zero network dependency.

**Note on prior sessions' reported baseline:** earlier reports in this repository describe "4 pre-existing chromadb collection errors" as the stable environment-only baseline, not 34. This session's sandbox appears to have stricter network isolation than whatever environment produced those reports (or that environment had a warm model cache). This is a difference in test environment, not a change in the code; it does not affect the validity of any finding above, all of which were verified either with zero network dependency (A6, A7) or by confirming the K4.2-path tests specifically don't hit this wall (RI-1 through RI-7).

---

## 8. Remaining Issues

- **DEBT-010** (new, documented in `KNOWN_ISSUES.md`): pre-existing `Config` watcher-thread race against `CONFIG_DIR` patching in tests. Confirmed pre-existing (reproduces on unmodified code), out of scope for this session, not fixed. Low-Medium severity, test-flakiness impact only — no production data-loss risk under normal operation (`CONFIG_DIR` is never reassigned at runtime outside of tests).
- **DEBT-002 correction** (not a new issue, corrected an inaccurate reason for an already-known issue): `SupervisorWorker` exists now but still doesn't populate `metadata["delegating_worker_type"]`, so `AgentGovernor` delegation permissions remain unenforced for a different reason than previously documented.
- No other genuine defects found. Everything else investigated in the Runtime Integration bug-hunt scope (Sections 6–16 of the governing task spec) came back verified-correct or intentionally-deferred, as detailed in Section 2 above.

---

## 9. Commits

Two commits, created locally, matching the task's requested scope separation:

1. `fix: harden K4.2 runtime integration` — `core/orchestrator.py`, `tests/test_runtime_integration.py`
2. `fix: resolve A6/A7 audit findings` — `core/config.py`, `modules/system_ctrl/module.py`

A third, separately-attributed documentation commit covers `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, and this report — not part of the original two-commit scope, added because bringing project-memory documentation current was requested as a follow-up in this same session.

Exact hashes recorded in the chat response for this session, and confirmed against `git log` before any push.
