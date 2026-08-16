# ADR-K4.2-H-05: Unified Operation Recovery Budget

**Status:** ACCEPTED
**Date:** August 16, 2026
**Author:** K4.2-H1 packet (Contract Evolution Foundation)
**Scope:** `core/cognitive/recovery.py` (new), `core/orchestrator.py`, `core/workers/supervisor.py`, `config/settings.toml`.

---

## 1. Context

`cognitive.planner_impasse` was architecturally specified but never emitted; `SupervisorWorker` had zero wiring to Planner impasse events despite being positioned as the worker whose entire purpose is reacting to cognitive-pipeline failures. Two independent v1.0 recovery actions needed a single, non-bypassable authority: Planner re-planning on impasse, and Supervisor's existing worker-retry mechanism.

## 2. Decision

- `OperationRecoveryBudget` (`core/cognitive/recovery.py`, new file): `max_total_recovery_attempts`, `internal_recovery_used`, `.remaining`, `.exhausted`, `.consume() -> bool`. A pure data contract; no wiring of its own.
- **Orchestrator owns creation.** One budget per `handle()` K4.2-branch invocation (`max_recovery_attempts`, read from `config/settings.toml [runtime]`, default 3 — a configuration default, not an architectural constant).
- **Planner does not own or receive the budget.** `plan()`'s signature is unchanged. Orchestrator drives the re-plan loop itself: call `plan()`, and on `PlannerStatus.IMPASSE`, consume the budget and call `plan()` again; on exhaustion, emit `cognitive.planner_impasse_terminal` and return.
- **`PlannerStatus.REJECTED_PRECHECK` is never retried and never consumes budget.** `_extract_constraints()`/`check_precheck_rejection()` are fully deterministic (no LLM call) — retrying a precheck rejection is provably guaranteed to reproduce the identical result. Retrying it would only waste the shared budget on an outcome that can never change. (This narrows the specification's own illustrative loop sketch, which did not distinguish the two rejection/impasse statuses, to the decision's actual intent.)
- **The same instance is threaded to `SupervisorWorker`** via `context.parameters["recovery_budget"]`, at the one existing call site that invokes it (compilation rejection). `_attempt_retry()` treats a present `recovery_budget` as the sole authority, bypassing the legacy `max_supervisor_retries`/`supervisor_retry_attempt` counters entirely; when absent, the legacy path is unchanged byte-for-byte, preserving every existing caller.
- **No autonomous re-compilation.** v1.0 recovery is exactly these two actions. Compilation rejection remains surfaced-only (K4 §16 invariant 9, unchanged).

## 3. Consequences

- H1-G5 (mandatory): proven by a dedicated integration test (`tests/test_orchestrator_recovery.py`), not unit tests alone. The test forces two Planner re-plan consumptions via a mocked `plan()` sequence, then a compilation rejection, and asserts the `OperationRecoveryBudget` object that reaches `SupervisorWorker` shows `internal_recovery_used == 2` — a value only possible if it is the *same instance*, not two independently-constructed budgets with matching configuration.
- Bounded termination is structural: `budget.consume()` returns `False` once exhausted, so the re-plan loop runs at most `1 + max_total_recovery_attempts` `plan()` invocations, verified directly (`test_budget_exhaustion_terminates_replan_loop`).
- A genuine gap was found, not built around silently: there is currently no code path that invokes `SupervisorWorker` with a `failed_worker_result` after a `WorkflowRuntime.execute()` failure in the K4.2 branch — `wf_result.success` is never checked there today. Supervisor's worker-retry action is budget-aware and tested at the contract level, but has no live trigger yet. Building that detection-and-retry pathway is a new capability, not in H1's exact-modules table, and would require real design decisions (how `retry_worker_type`/`retry_parameters` get constructed) not specified anywhere — left for a future H2/H3 decision rather than invented here.

## 4. Alternatives considered

- **A second, Supervisor-owned budget for worker retry, reconciled after the fact**: rejected — this is precisely the "hidden retry universe" the Recovery Invariant forbids.
- **Threading the budget into `plan()`'s own signature**: rejected — keeps Planner's public interface unchanged; recovery is purely an Orchestrator-level policy concern.
