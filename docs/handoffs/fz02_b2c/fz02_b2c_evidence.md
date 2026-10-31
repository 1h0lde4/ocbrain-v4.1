# FZ-02 / batch B2c (narrowed): baseline and evidence record

Review target (immutable base): `main` = `16d663ac8449965f774033da46d5063506a772a7` (PR #97 merge); unchanged at the time of writing.
Branch: `fix/fz02-b2c-cancellation-terminal-oct2026` (still on the remote; not deleted). PR: #104, **MERGED 2026-10-31** as `ed3d141e4bbfd0231afb1104d0a7479419f9bbf1` (parents `16d663a`, `4891756`) after the owner's narrow sign-off on the exact head `4891756` (section 8).
Head: `4891756b4864c15c4e8df534560a46f5ce7fe34c` = `fc845d0` (first, un-narrowed B2c commit) + one additive narrowing commit. No history was rewritten. Net diff vs `main`: 2 files (`core/model_router.py` +34/-5, `tests/test_b2c_cancellation.py` new, 7 tests).
Deferred portion: branch `follow-up/fz02-b2d-latent-token-cancellation-oct2026` @ `b44bddf` (no PR, not reviewed, not for merge as-is). Separate tracked item for the `Worker.execute()` cancellation swallow: issue **#105** (unassigned).

Status vocabulary: VERIFIED = checked by running or reading in this session; UNVERIFIED = not checked.

## 1. Owner decision of 2026-10-31 (scope split) and where each part went

| Item | Where it is now |
|---|---|
| Router consumer/watchdog cleanup when the caller task is cancelled; propagation of `CancelledError`; no fallback / health penalty from swallowed caller cancellation | **PR #104** (live) |
| `FailureType.CANCELLED` classification, CANCELLED training-pair/count/promotion guard, `AdapterRuntime` pre-attempt token check, terminal `cancelled` handling, `is_caller_cancellation()`, 12 tests + 2 strict xfails | **follow-up branch** (latent, preserved byte-for-byte from `fc845d0`) |

## 2. Gate: how the graph watchdog stops a node (VERIFIED)

- `GraphExecutionWatchdog` only **sets** the workflow token (`core/runtime/watchdog.py:180,196`). The token is read cooperatively before a node is traversed and before each retry attempt (`core/workflow/runtime.py:723,865`), and by workers that choose to check it. Nothing cancels a node's task; the planner node does not forward the token to the router. The repo's own `SlowNodeWorker` fixture (`tests/test_workflow_runtime.py`) states that `ExecutionRuntime.invoke()` does not forcibly preempt a running worker.
- Probe 1 (`docs/handoffs/fz02_gate_probe.py`, real `WorkflowRuntime` + `ExecutionRuntime` + `Worker.execute` + `ModelRouter`; only the provider stream is faked): graph budget hard=0.3 s; token cancelled with reason `execution hard_deadline`; the node ran until the router's own hard deadline; workflow returned after **2.03 s**.
- Conclusion: the graph watchdog does **not** exercise this PR's behaviour. That behaviour is exercised only when something cancels the task that runs the workflow/node. In-process I found no such site on the request path (no `wait_for`/timeout around `handle()` or node execution; `safe_llm_call`'s `wait_for` wraps provider-mesh/evaluator calls, not the monitored-streaming path). External triggers (shutdown, Ctrl-C, client disconnect): **UNVERIFIED**.
- Probe 2: the task running `execute()` cancelled at 0.5 s, node retry policy `max_retries=1`. With this PR: provider stream closes at **0.5 s** (then `[0.5, 2.52]`); on unchanged `main` no close is observed for that attempt (`[2.52]`). In **both**, `execute()` **returns a result** (`task.cancelled()` False) and the node runs twice, because `Worker.execute()` (`core/workers/base.py:293`) converts `CancelledError` into `WorkerResult(success=False, error="Worker cancelled")` and the retry loop checks only the token. **New finding, not fixed here**: a task cancel does not terminate a workflow today.

## 3. Production reachability of the token path (VERIFIED at 16d663a)

No production caller gives the router or `AdapterRuntime` a token: `PlannerWorker` passes `context_memory` (`planner.py:321-326`, `:344-345`), `capability_executor.py:116-121` passes `""`, `orchestrator.py:923` passes `context_memory` (`main.py:403`). `ContextMemory` has no `cancellation_token`; `_request_token()` returns `None` for both request shapes; `_resolve_cancellation_token()` returns a fresh local token each call. The earlier handoff claim that the router sees the workflow-level token was wrong and is retracted (handoff correction C1, wip commit `03a16c0`).

## 4. Baseline at 16d663a, before any change

Entire suite (new test file excluded): **8 failed, 2064 passed, 4 skipped, 1 xfailed, 4 collection errors** (51.72 s). The 12 failing/erroring ids are environmental and identical after the change: `test_audit_fixes.py::TestA7SystemController` (6 tests), `test_module_factory_security.py` (2 tests), and collection errors in `test_break_concurrency.py`, `test_break_empty_db.py`, `test_break_security.py`, `test_system_ctrl.py`. Environment: Python 3.12, pytest 9.x, no chromadb/sentence-transformers (CI can differ).

## 5. Red / green for the narrowed PR

| Check | Result |
|---|---|
| `tests/test_b2c_cancellation.py` on unchanged `main` (red) | **3 failed**, 4 passed: `test_caller_cancel_mid_generation_stops_the_stream_and_leaks_no_tasks`, `test_caller_cancel_while_the_router_cancels_its_consumer_is_not_swallowed`, `test_cancelling_one_request_does_not_affect_a_concurrent_request`. The other 4 are pins of behaviour that already held (genuine provider failure / genuine stall still fall back and are penalised; task cancel during fallback; cancel during training-pair recording). |
| same file on the PR head (green) | **7 passed** (1.53 s) |
| entire suite on the PR head | 8 failed / **2071 passed** / 4 skipped / 1 xfailed / 4 collection errors (49.35 s); failing/erroring ids **identical** to the baseline set |
| `scripts/check_drift.py`; `git diff --check`; CR bytes | 15 of 15 PASS (rc 0); clean; 0 |
| CI on `4891756` | `tests`, `drift-and-ownership`, `CodeQL`, `Analyze (python)`, `Analyze (actions)`: all success |

The test context `_Ctx` is production-shaped (no `cancellation_token`).

## 6. Deferred portion (follow-up branch)

19 passed + 2 xfailed on the restored files (5.27 s); against unchanged `main` the un-narrowed file gave 12 failed / 7 passed / 2 xfailed; CI on `fc845d0` was green. Activation condition: a production caller passes a real `CancellationToken` to `ModelRouter.route()` / `AdapterRuntime.invoke()`; that work must also decide the per-attempt-token question (the sibling-cut xfail becomes reachable once a shared token is forwarded).

## 7. Reviewer notes and open items

1. **Physical provider-side termination on cancel: UNVERIFIED.** Only in-process stop is proven, with fakes.
2. `Worker.execute()` swallows task cancellation above the router (section 2). Needs its own tracked item and an owner decision; this PR does not change it.
3. Genuine failure/stall effects from B2a/B2b are unchanged: a failure or stall benches `ModelRouterAdapter` and can start a second full generation on `OllamaAdapter`.
4. Training pairs, `query_count` and promotion are still recorded for provider-failure, stalled and hard-deadline outcomes (tracked separately).
5. `OllamaAdapter` error text can carry raw exception text (log-only today). `OpenAICompatAdapter` failure path untested here.
6. Handoff reconciliation: C1 (section 11 retraction) and C2 (sections 7 and 17-19, requirement ledger) are on the wip branch; this record is committed there beside the B2a/B2b records.
7. FZ-01 stays open. No freeze claim follows.

## 8. Sign-off boundaries, merge, post-merge audit

Owner sign-off (2026-10-31), narrow, on the exact head `4891756`: a **resource-cleanup fix only**. Recorded boundaries (also in the PR body and the merge commit message):
1. Guaranteed: when the task running the provider call is cancelled, the provider stream closes and no router task outlives the request; a caller cancellation during the router's own consumer cancellation is not swallowed.
2. NOT done: the graph watchdog does not cancel node tasks.
3. NOT established: that execution stops on cancellation. Cleanup must not be mistaken for cancellation of the workflow.
4. UNVERIFIED: shutdown, Ctrl-C and client-disconnect cancellation; physical provider-side termination.
5. Tracked separately: the `Worker.execute()` cancellation-swallow/retry behaviour is issue **#105** (needs its own owner, branch, tests and an explicit decision on the cancellation contract). Not decided or fixed here.
6. The broader cancellation gap is NOT closed and workflow cancellation is NOT marked solved. FZ-01 stays open; no freeze claim.

Merge: `main` had not moved from `16d663a`, so no update-from-main was needed. Merge commit pinned to the signed-off SHA via the API; all five checks were green on `4891756` immediately before.

Post-merge audit of `main` @ `ed3d141`: parents `16d663a` + `4891756`; diff against the first parent is exactly the PR's two files (+355/-5); `tests/test_b2c_cancellation.py` on merged `main`: 7 passed; `scripts/check_drift.py` rc 0; `wip`, `follow-up` and `fix` branch tips unchanged by the merge. CI on the merge commit: `tests`, `drift-and-ownership`, `Analyze (python)`, `Analyze (actions)` all completed with success.
