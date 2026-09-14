# ADR-KERNEL-02: Watchdog Reconciliation (DEBT-016)

**Status:** Accepted
**Date:** September 5, 2026
**Context:** `KNOWN_ISSUES.md` DEBT-016 — two independently-built `ExecutionWatchdog`/`ProgressMonitor` implementations, never reconciled, explicitly reclassified (Aug 29, 2026, Kernel Completion Study) as a Kernel v1.0 completion item in its own right. Sequencing decision: per Moncif, this session follows the existing roadmap (Watchdog/DEBT-003/DEBT-016 now, freeze audit next, Verification/Critic/Evidence integration stays post-freeze/post-C-MoE as already planned) rather than the alternative ordering proposed in this session's opening prompt. Both were verified against current code before any change was made, per this project's "prove the state first, then reconcile it" discipline.

---

## Part A: The duplicated-authority problem

### What was actually found (not assumed)

Two classes, both literally named `ExecutionWatchdog`, in different modules, with materially different semantics — not just cosmetic duplication:

- `core/runtime/watchdog.py` (graph-aware, consumed by `WorkflowRuntime` — the K4.2 default execution path, live since Aug 28, 2026): polled an `ExecutionGraph` on a fixed interval, checked `ExecutionBudget.is_hard_expired()`, and on detecting a stale active node, only *recorded* `ExecutionStatus.STALLED` via `progress.ProgressMonitor`. It never called `budget.grant_extension()` and never cancelled *because of* a stall — only the unrelated hard-ceiling check could ever cancel. A stalled node would sit labeled STALLED, polled forever, until the (often large: 300–600s) hard ceiling eventually elapsed.
- `core/runtime/execution_watchdog.py` (model-router-facing, consumed by `ModelRouter`'s long-form generation path): a materially richer design — typed `WatchdogVerdict`/`CancelReason` enums, a pure `_decide()` decision function (directly unit-testable, no I/O), a real activity-vs-progress distinction (`progress_monitor.ProgressMonitor`), and actual bounded-extension recovery (grace period → one bounded extension → cancel with `CancelReason.STALL` only once that extension is exhausted). Already covered by `tests/test_execution_watchdog.py` and documented against ADR-K4.2-H-05's recovery-boundary invariants (the extension is intra-operation only; never touches `OperationRecoveryBudget`, never re-enters the Planner).

The two `ProgressMonitor` classes (`progress.py` vs. `progress_monitor.py`) are also genuinely different, not just duplicated: the graph-aware one is event-sourced (emits `execution.*` events to `EventStream`, multi-node, feeds the execution-inspection API) and the model-router one is a single-attempt, in-memory-only activity/progress tracker with no EventStream dependency. Confirmed by direct read: nothing in production ever calls `report_progress()` on the graph-aware path (`core/workflow/runtime.py` only ever calls `record_status()` / `record_completion()` / `record_failure()`), so `last_progress_at` is never set there — a fact load-bearing for Part C below.

### Decision

Extend the better design into a shared core rather than picking a winner and deleting the other (both `ProgressMonitor`s earn their keep for genuinely different consumers — Extension over Specialization, PROJECT_INSTRUCTIONS.md §on architectural evolution):

1. New module `core/runtime/watchdog_decision.py` holds `WatchdogVerdict`, `CancelReason`, `Decision`, and `decide()` — moved out of `execution_watchdog.py` verbatim in logic, with one interface change: `decide()`'s second parameter is now typed against a minimal structural `ProgressSignal` `Protocol` (`has_progressed()`, `since_last_progress_s()`, `is_actively_progressing()`) instead of the concrete `progress_monitor.ProgressMonitor` class, so a second, differently-shaped caller can supply the same three answers without adopting that class's shape.
2. `progress_monitor.ProgressMonitor` gained one additive method, `is_actively_progressing()` (a one-line wrapper around its existing `snapshot().state`), so it satisfies the new Protocol with no behavior change.
3. `execution_watchdog.py` now imports `CancelReason`, `WatchdogVerdict`, and `decide` (re-imported as `_decide`) from `watchdog_decision.py` instead of defining them locally. Every existing import of this module, including `tests/test_execution_watchdog.py`'s `from core.runtime.execution_watchdog import (CancelReason, ExecutionWatchdog, WatchdogVerdict, _decide)`, works unchanged — verified: all 13 of that file's tests pass with zero modification.
4. `core/runtime/watchdog.py`'s class is renamed `GraphExecutionWatchdog` (the name collision was itself part of what DEBT-016 called a "duplicated authority, easy to confuse" pattern; no other production or test call site existed besides `core/workflow/runtime.py` and `tests/test_execution_inspection.py`, both updated). It gained a private `_GraphProgressSignal` adapter — built fresh each poll tick from one `await graph.snapshot()` call, so `decide()` itself stays synchronous and I/O-free — and now calls the shared `decide()` instead of its own ad hoc staleness check, meaning it can now genuinely attempt bounded recovery and can now genuinely cancel because of a stall, not only via the hard-ceiling path.
5. The decision (extend vs. give up) is evaluated once per poll tick for the execution as a whole, against the single `ExecutionBudget` `WorkflowRuntime.execute()` already constructs per workflow run — not fragmented per node. Per-node `RECOVERING`/`FAILED` status recording for the execution-inspection UI still happens per currently-active node.

### What was explicitly not done

- No per-node `ExecutionBudget`. The existing one-budget-per-workflow-execution shape already matches what `decide()` needs; inventing per-node budgets was unnecessary scope.
- The two `ProgressMonitor` classes were not merged. They serve genuinely different consumers with genuinely different needs (event-sourced multi-node observability vs. single-attempt in-memory tracking); forcing one shape onto both would have been the "hidden second semantic model" this project's laws warn against in the other direction.
- DEBT-015's broader `Operation`/`ExecutionAttempt`/`ExecutionSnapshot`/`RecoveryDecision` architecture (`docs/reports/WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md`) was not adopted. It remains correctly non-blocking future architecture, explicitly gated on its own ADR before implementation; nothing here forecloses it.
- Verification/Critic/Evidence integration was not touched, per this session's sequencing decision (see Context).

### Evidence

`tests/test_execution_inspection.py` — 3 pre-existing tests pass unchanged (renamed class only); 3 new: `test_watchdog_grants_bounded_extension_on_real_stall_and_records_recovery`, `test_watchdog_extends_then_eventually_cancels_with_stall_reason`, `test_watchdog_does_not_expire_during_gap_between_nodes`. `tests/test_workflow_runtime.py` — new `TestWorkflowRuntimeWatchdogReconciliation` (3 tests) exercising the real `WorkflowRuntime.execute()` path end-to-end with a deliberately slow, cooperatively-cancellable worker, not just the isolated watchdog unit. `tests/test_execution_watchdog.py`, `tests/test_progress_monitor.py`, `tests/test_model_router_monitored_streaming.py` — all pass unchanged (31 tests). Full suite: 1,356 passed / 39 failed (34 pre-existing `huggingface.co`-unreachable, 5 pre-existing intentionally-red security-regression tests — CTX-AUTH-001 ×2, CTX-SCOPE-001, CTX-CACHE-001, CTX-DELETE-001 — all confirmed unchanged before and after, same test names as this session's Phase 0 baseline).

---

## Part B: A pre-existing budget-construction bug, found while tracing this

### What was actually found (not assumed)

`WorkflowRuntime.execute()`'s inline default-budget construction set `absolute_ceiling_s=hard_ceiling` — the *same* value as `hard_ceiling_s` — while also setting `max_extension_s=240.0`. `ExecutionBudget.grant_extension()` clamps its grant to `absolute_ceiling_s - hard_ceiling_s`; with the two equal, that clamp is always zero, so `grant_extension()` was structurally incapable of ever granting anything on the K4.2 default path, regardless of `max_extension_s`. Harmless before Part A (the old watchdog never called `grant_extension`), but would have made Part A's whole fix a no-op on the default path — every real stall would have gone straight from "detected" to `STALLED`/cancelled at the first `progress_deadline_s` (45s), with no extension ever actually granted, for any workflow node that doesn't call `report_progress()` (which, per Part A, is all of them today).

### Decision

Give `absolute_ceiling_s` real headroom above `hard_ceiling_s` — `hard_ceiling + max_extension` — matching the relationship `ExecutionPolicy.for_generation()` already uses correctly for the model-router path. Extracted the construction into `WorkflowRuntime.default_budget_for(query) -> ExecutionBudget`, a static method, so the relationship is independently unit-testable rather than buried inline in `execute()`.

### Evidence

`tests/test_workflow_runtime.py::TestWorkflowRuntimeWatchdogReconciliation::test_default_budget_has_real_extension_headroom` asserts `absolute_ceiling_s > hard_ceiling_s` and that `grant_extension()` actually succeeds against the real default budget.

---

## Part C: Two correctness bugs found and fixed during this change's own testing

Recorded explicitly, not silently folded in, per this project's evidence-tagging discipline — both were present in this ADR's own first implementation attempt, not in the pre-existing code, and both were caught by tests written for this same change before being committed.

1. **Self-feedback via the watchdog's own diagnostic write.** The first version of `GraphExecutionWatchdog.inspect()` called `monitor.record_recovery()` on every poll tick while the verdict remained `RECOVERING` (not just the tick a fresh extension was granted). `record_recovery()` writes to the graph, which unconditionally touches `node.updated_at` — the exact field `_GraphProgressSignal` reads as its progress signal (Part A: nothing else touches it for this path). Writing every tick meant the watchdog's own bookkeeping perpetually looked like fresh progress to itself, which would have masked a genuine stall indefinitely once the first extension was granted. Fixed by writing `record_recovery()` only on the `EXTENDED` verdict (the instant of an actual grant), never on subsequent `RECOVERING` ticks riding out that same grace period — one write per grant is sufficient; the persisted status already answers "what's happening" for anything polling the graph in between. Caught by `test_watchdog_extends_then_eventually_cancels_with_stall_reason` failing (`'idle' != 'stalled'`, then later `KeyError`) before this fix.
2. **Empty active-node gap misread as a fresh, unprogressed attempt.** The gap between one node completing and the next starting (or before the first node starts) has zero `RUNNING`/`RECOVERING` nodes. Routing that gap through `decide()` unmodified would have hit the `not has_progressed()` branch and expired the whole execution once elapsed time crossed the 10s `startup_deadline_s` — even though nothing had stalled; there was simply nothing running yet. Fixed by special-casing an empty active set to only the unconditional hard-deadline check (matching the pre-existing safe behavior for this case), bypassing `decide()` entirely rather than trying to make `decide()` itself aware of a case it was never designed to reason about. Regression-tested by `test_watchdog_does_not_expire_during_gap_between_nodes`.

---

## Consequences

- DEBT-016 (`KNOWN_ISSUES.md`) is resolved by this ADR.
- A `RECOVERING`-labeled node's displayed status does not automatically revert to `RUNNING` if the underlying condition resolves on its own (e.g., enough wall-clock time passes without a fresh extension attempt being needed again) — it stays `RECOVERING` until the node eventually completes, fails, or is cancelled. This is not a new limitation: the pre-existing code had the identical property for its `STALLED` label. Left as a documented, non-blocking, purely cosmetic follow-up rather than in-scope for this fix — resolving it correctly would require writing on additional verdicts, reopening exactly the self-feedback risk Part C.1 exists to avoid, and deserves its own consideration rather than a rushed addition here.
- DEBT-003 (checkpoint/resume) is unaffected by this change and remains separately open — it was not touched.
- Verification/Critic/Evidence integration remains post-freeze/post-C-MoE per the existing roadmap, per this session's sequencing decision.
- No changes to `ModelRouter`, `PlannerWorker`, `GovernanceKernel`, `UnifiedMemory`, `EventStream`/`EventBus`, `CapabilityRegistry`, `AdapterRuntime`, or the Verification contracts on `feature/verification-critic-evidence-phase-c`.
