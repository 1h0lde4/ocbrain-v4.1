# ADR-KERNEL-01: Root Operation Identity and ExecutionContext Migration Completion

**Status:** Accepted
**Date:** August 29, 2026
**Context:** `docs/studies/OCBRAIN_KERNEL_COMPLETION_CANONICAL_PLAN.md` identified two Kernel v1.0 freeze blockers. Both were verified against current code before any change was made, per the governing task's explicit "prove the state first, then reconcile it" requirement.

---

## Blocker A: Logical execution identity

### What was actually found (not assumed)

`Goal`, `ExecutionPlan`, and `WorkflowDefinition` carried no field linking them to a stable, cross-stage logical operation identity. Direct code inspection additionally found something more precise than the canonical plan's own framing: an `operation_id` field *already exists*, but as a **different, narrower concept** than the one needed here. Per ADR-K4.2-H-08 (Trace and Operation Identifier Semantics, Accepted), `operation_id` is a per-cognitive-stage-invocation diagnostic correlation ID, generated fresh by `plan()` and again, independently, by `compile()`, by explicit design — its own tests (`test_each_plan_call_generates_a_fresh_operation_id`, `test_each_compile_call_generates_a_fresh_operation_id`) assert exactly this regeneration as correct behavior. Repurposing that field to mean "stable across the whole operation" would have broken an accepted, tested ADR for no benefit.

### Decision

Introduce `root_operation_id` as a new, distinctly-named field, leaving ADR-K4.2-H-08's `operation_id` completely untouched:

- `Goal.root_operation_id: str` — generated once, here, via `uuid.uuid4()` (the earliest point in the current architecture where a persistent cognitive artifact exists; the Orchestrator's admission boundary upstream of Intent interpretation was not touched, per Rule 0.4's preference for minimal-footprint change).
- `ExecutionPlan.root_operation_id: Optional[str]` — threaded from `goal.root_operation_id`, never independently generated.
- `WorkflowDefinition.root_operation_id: Optional[str]` — threaded from `plan.root_operation_id`, never independently generated.
- `WorkflowNode` does **not** carry this field. Per the canonical plan's own I7 guidance ("first determine whether nodes are always scoped by their parent... a node-level reference may be justified only if nodes are independently persisted, transported, indexed, or emitted"): nodes are not currently persisted, transported, or indexed independently of their parent `WorkflowDefinition` — no checkpoint/resume exists yet (`KNOWN_ISSUES.md` DEBT-003). Revisit this specific decision if/when DEBT-003 changes that.
- `WorkflowNodeState.attempt_id: str` — a stable, opaque identifier generated fresh on each retry in `WorkflowRuntime._execute_node_with_retry()`, alongside (not replacing) the existing `attempts: int` counter. Per I3/I6: a bare counter cannot serve as a stable attempt identity across a process restart, even though it remains correct and useful as a retry count in its own right.

### What was explicitly not done

- Goal/Plan *version* fields (integers) were not added. `caused_by` already gives real lineage-in-spirit for the recovery-replan case; a full versioning scheme is a larger design question this fix does not need to answer to close the identity gap, and the canonical plan's own §31 does not require it for freeze.
- ~~The Orchestrator's re-plan loop was not modified to explicitly propagate `root_operation_id` onto a newly-formed `Goal` for the recovery case. A fresh `Goal()` in that path gets a fresh `root_operation_id` today, which is a known, narrower scope than full I2 compliance ("identity survives... goal mutation"). This is named here explicitly, not silently left unaddressed: closing it requires touching the Orchestrator's re-plan construction site, which was judged out of the minimal-footprint scope for this pass. Tracked as a follow-up, not claimed complete.~~

  **Correction, Aug 31, 2026 (same-day follow-up task):** the claim above was written without fully tracing the code and turned out to be imprecise. Direct tracing found the only `Goal()` construction site in the entire codebase is `form_goals()` (`core/cognitive/intent.py`), called exactly once per `handle()` invocation (`core/orchestrator.py`, single call site, confirmed by grep across all of `core/`). The impasse re-plan loop (`core/orchestrator.py`, the `while planner_result.status == PlannerStatus.IMPASSE` loop) re-invokes `plan()` with the *same* `PlannerRequest` — built from the *same* `Goal` object — on every retry. It does not construct a new `Goal` at all. `root_operation_id` is therefore already, trivially preserved across every current replan iteration, because it is the literal same Python object, not a value requiring explicit re-propagation. Proven against the real orchestrator path (not a mock of the identity logic) by two new tests: `test_every_plan_call_across_an_impasse_retry_sees_the_same_root_operation_id` and `test_two_separate_handle_calls_get_different_root_operation_ids`, both in `tests/core/cognitive/test_kernel_blocker_resolution.py`. No code change was needed for this specific item — this ADR's original text simply overstated a gap that direct tracing did not confirm. The genuine forward-looking consideration remains real: *if* a future feature ever re-invokes `form_goals()`/`interpret_request()` for what should be considered the same logical operation (a genuine goal-level replan, as opposed to the plan-level impasse retry that exists today), that path would need explicit `root_operation_id` propagation, since it would be constructing a second `Goal`. No such path exists today; this is noted for whoever eventually builds one, not implemented speculatively now.
- Checkpoint/resume (DEBT-003) was not implemented. Per the governing task's own Section 10, this remains the next dependent Kernel task; this ADR does not claim it complete.
- Idempotency was not implemented. Per Section 11, identity is a prerequisite for idempotency design, not a substitute for it.

### Evidence

`tests/core/cognitive/test_kernel_blocker_resolution.py::TestRootOperationIdSurvivesCognitionToCompilation` (6 tests), `::TestAttemptIdentityDistinctFromRetryCount` (2 tests), and `::TestRootOperationIdSurvivesRecoveryReplan` (2 tests, added Aug 31 2026 — see the correction above), the latter exercising the real `Orchestrator.handle()` impasse-retry path, not a mock of the identity logic. Full suite: 1,347 passed / 36 failed (34 pre-existing `huggingface.co`-unreachable, 2 pre-existing intentionally-red `CTX-AUTH-001` security-regression tests unrelated to this work — both confirmed unchanged before and after).

---

## Blocker B: WorkerContext vs. ExecutionContext

### What was actually found (not assumed)

`ExecutionRuntime.invoke()` was constructing a full `ExecutionContext` and then explicitly converting it to a `WorkerContext` via `context.to_worker_context()` "for backward compatibility" before every single worker invocation — confirmed by direct code read, not inferred. `ExecutionContext` already carried `task_id`/`query`/`recursion_depth` bridge properties, each explicitly commented "Compatibility shim — will be removed after K2.4," clearly built in anticipation of exactly this migration and never finished. `parameters` had no equivalent bridge property. Every actual `WorkerContext(...)` construction site found in production-looking code (`base.py`, `curator.py`) was inside a docstring `Usage:` example, not live code — zero real production callers construct `WorkerContext` directly.

### Decision

Complete the migration ADR-001 already declared:

1. Added the missing `parameters` bridge property to `ExecutionContext`, completing the set.
2. Migrated all type annotations from `WorkerContext` to `ExecutionContext`: `AbstractCognitiveWorker.execute()`, `.emit_progress()`, `._emit_event()`, the abstract `._run()` declaration, and all seven concrete worker classes' `_run()` overrides (`CapabilityExecutorWorker`, `CuratorWorker`, `EvaluatorWorker`, `PlannerWorker`, `ReflectionWorker`, `SupervisorWorker`, plus two internal helper methods on `SupervisorWorker` and `PlannerWorker` found during a full-file sweep, not just the `_run()` signatures the initial search targeted).
3. Removed the `to_worker_context()` conversion call in `ExecutionRuntime.invoke()`. Workers now receive the real `ExecutionContext` instance.
4. `WorkerContext` itself is **retained, not deleted**. Ten pre-existing test files still reference it; all ten pass unchanged (verified via full suite run), meaning they either construct it as their own direct test input (calling a worker's `_run()` without going through `ExecutionRuntime`, where duck-typing means the type annotation change has zero effect on them) or test its standalone shape. None were found testing "a worker receives `WorkerContext` at runtime," which would now be an incorrect assertion — if one exists among the ten that this sweep didn't individually inspect, it was not caught by the full-suite pass and should be treated as a follow-up finding, not silently assumed absent.

### Evidence

`tests/core/cognitive/test_kernel_blocker_resolution.py::TestWorkersReceiveExecutionContextDirectly` (4 tests), specifically `test_execution_runtime_no_longer_converts_to_worker_context`, which asserts `isinstance(received_context, ExecutionContext) is True` and `isinstance(received_context, WorkerContext) is False` against the real `ExecutionRuntime.invoke()` path — not a mock of it. Full suite: 1,343 passed / 34 failed (unchanged).

---

## Consequences

- `ExecutionContext`'s richer fields (`worker_id`, `session_id`, `causal_chain`, `cancellation_token`, `execution_budget`) are now actually reachable inside every worker's `_run()` body for the first time — previously discarded by the `to_worker_context()` conversion, since `WorkerContext` has no fields for any of them. No worker currently uses these newly-reachable fields; that is a capability this fix makes available, not a behavior change this fix performs.
- `WorkerContext`'s deletion condition (Section 7: "once all call sites migrate, remove the shim") is not yet met — ten test files still reference it. Deleting it now would require touching test files this pass judged out of minimal-footprint scope. Recorded here as the specific, concrete condition for a future pass, not left as a vague "eventually."
- Neither change touched Planner, Compiler, GovernanceKernel, WorkflowRuntime's retry-decision logic, UnifiedMemory, EventStream/EventBus, CapabilityRegistry, AdapterRuntime, or ModelRouter, per Rule 0.4.
