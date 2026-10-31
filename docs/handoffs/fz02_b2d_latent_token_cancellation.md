# FZ-02 / B2d (deferred): token-driven cancellation

Status: **DEFERRED. Latent. NOT reviewed, NOT for merge as-is.**
Branch: `follow-up/fz02-b2d-latent-token-cancellation-oct2026`
Based on: PR #104 head `4891756` (B2c narrowed). The code and test files are restored byte-for-byte from `fc845d0` (the first, un-narrowed B2c head), so the diff over `4891756` is exactly the deferred portion.

Origin: owner decision of 2026-10-31 splitting the production-unreachable part out of B2c ("do not ship latent functionality as though it were operational").

## What is deferred

| Item | Where |
|---|---|
| `FailureType.CANCELLED` for a token cancelled by someone other than the attempt's own watchdog; no training pair / `query_count` / promotion for it | `core/model_router.py` |
| `is_caller_cancellation(token)`, `ADAPTER_LOCAL_CANCEL_REASONS` | `core/runtime/watchdog_decision.py` |
| pre-attempt token check, terminal `failure_type == "cancelled"` (no `mark_failure`, no fallback), `adapter.cancelled` event, `stats()["total_cancelled"]` | `core/capabilities/adapter_runtime.py` |
| 12 tests (parametrised, incl. 4 reasons) + 2 strict xfails: token cancel in-flight fallback not delivered; shared-token sibling cut | `tests/test_b2c_cancellation.py` |

## Why it is latent (verified at `main` 16d663a)

No production caller hands the router or `AdapterRuntime` a cancellation token: `PlannerWorker` (`core/workers/planner.py:321-345`) passes `context_memory`; `core/workers/capability_executor.py:116` passes `""`; `core/orchestrator.py:923` passes the same `context_memory`. `ContextMemory` has no `cancellation_token`, `_request_token()` returns `None` for both request shapes, and `ModelRouter._resolve_cancellation_token()` returns a fresh local token per call.

The graph watchdog does not change this. `GraphExecutionWatchdog` only sets the workflow token (`core/runtime/watchdog.py:180,196`); that token is read cooperatively between nodes and before retry attempts (`core/workflow/runtime.py:723,865`). Nothing cancels a node's task, and the planner node does not forward the token to the router. Probe 1 of `docs/handoffs/fz02_gate_probe.py`: graph budget hard=0.3 s, token cancelled with reason `execution hard_deadline`, yet the node ran until the router's own hard deadline (workflow returned after 2.03 s).

## Activation condition

A production caller passes a real `CancellationToken` into `ModelRouter.route()` / `AdapterRuntime.invoke()` (for example `PlannerWorker` forwarding `ExecutionContext.cancellation_token`). Re-verify the call paths above first. That work must also decide the per-attempt token question (the strict xfail "one module's stall cuts a healthy sibling"), because forwarding a shared token makes that defect reachable.

## Evidence preserved

- 19 passed + 2 xfailed on this branch (5.27 s); against unchanged `main` 16d663a the same file gave 12 failed, 7 passed, 2 xfailed; full suite on the un-narrowed head: 8 failed / 2083 passed / 4 skipped / 3 xfailed / 4 collection errors, failing set identical to `main`'s 12 environmental ids; `scripts/check_drift.py` rc 0. CI on `fc845d0` was green (`tests`, `drift-and-ownership`, CodeQL).
- Sandbox: Python 3.12, no chromadb. CI may differ.
- Gate probe (`docs/handoffs/fz02_gate_probe.py`), probe 2: cancelling the task that runs `WorkflowRuntime.execute()` at 0.5 s: `execute()` still returns a result and the node is retried (attempts=2), because `Worker.execute()` converts `CancelledError` into `WorkerResult(success=False, error="Worker cancelled")` (`core/workers/base.py:293`). With the B2c router fix the first provider stream closes at 0.5 s; on `main` no close is observed for it.

## Known limits (unchanged by this work)

Physical provider-side termination on cancel is UNVERIFIED. `OpenAICompatAdapter`'s failure path is untested here. FZ-01 stays open.
