# FZ-02 / batch B2b: baseline and evidence record

Review target (immutable): `main` = `8c0ea03` (the B2a merge); unchanged until the merge.
Branch: `fix/fz02-b2b-stalled-deadline-oct2026` (one branch, one commit)
PR: #71 (**merged** as `27d918db18d7d748b91b2a8babafb7339108da70`; parents `8c0ea03` + `31d7745`; main's tree identical to the reviewed head's tree)
Commit: `31d77457cea0f8e40bf9ec5aa46e0cdb3ad49121`

Decision implemented: **D2=(i)**, a stalled or hard-deadline generation is a failure that carries its partial text.

## 1. Register text preserved verbatim (KNOWN_ISSUES.md @ 8c0ea03; not edited by this PR)

| FZ-02 | ModelRouter/Ollama false completion: `_ollama_stream()` yields its error text as a normal token and returns normally; `ModelRouterAdapter.execute()` hard-codes `success=True` and ignores `route_result.execution_detail`. | **OPEN -- BLOCKED on D2** (not started; batch B2) | Reproduced with the real router and adapter, only the HTTP client faked to raise `ConnectError`: `RouteResult.execution_detail.failure_type = success`, `CapabilityResult.success = True`, output = the error token. Code path re-confirmed by inspection on `e438387` (`except Exception` in `_ollama_stream` yields an in-band `[Error: ...]` token; `ModelRouterAdapter.execute` returns `success=True` and never reads `execution_detail`); repro not re-run since. | D2: stalled/deadline outcomes with partial output. Its prerequisite FZ-04 is now met. Other adapters' semantics were not re-inspected. |

## 2. Baseline at 8c0ea03, before any change

- 25 related test files (the B2a set plus `test_fz02_provider_failure.py`): **456 passed, 1 xfailed** (457 collected).
- Entire suite: **8 failed, 1968 passed, 4 skipped, 1 xfailed, 4 errors**. The 12 failing/erroring ids are environmental and identical after the change:

- tests/test_audit_fixes.py::TestA7SystemController::test_accepts_normal_targets
- tests/test_audit_fixes.py::TestA7SystemController::test_open_app_uses_safe_platform_apis
- tests/test_audit_fixes.py::TestA7SystemController::test_open_app_with_injection_raises
- tests/test_audit_fixes.py::TestA7SystemController::test_rejects_empty_target
- tests/test_audit_fixes.py::TestA7SystemController::test_rejects_flag_like_target
- tests/test_audit_fixes.py::TestA7SystemController::test_rejects_shell_metacharacters
- tests/test_break_concurrency.py
- tests/test_break_empty_db.py
- tests/test_break_security.py
- tests/test_module_factory_security.py::test_desc_field_cannot_break_out_of_generated_source
- tests/test_module_factory_security.py::test_name_field_also_uses_safe_literal_substitution
- tests/test_system_ctrl.py

Collected tests per related file at baseline (count, file):

```
76 tests/core/cognitive/test_creative_content_anchor.py
     14 tests/core/cognitive/test_kernel_blocker_resolution.py
      8 tests/phase2_verification.py
      3 tests/test_api_context_scope.py
      6 tests/test_api_error_disclosure.py
     27 tests/test_architecture_hardening_session.py
     33 tests/test_capabilities.py
     34 tests/test_check_drift.py
      9 tests/test_context_scope_security.py
      6 tests/test_execution_inspection.py
     37 tests/test_execution_runtime.py
     17 tests/test_fz02_provider_failure.py
      8 tests/test_k2_2_runtime_migration.py
      9 tests/test_merger.py
     12 tests/test_model_router.py
      6 tests/test_model_router_monitored_streaming.py
     16 tests/test_orchestrator_memory_migration.py
      7 tests/test_orchestrator_recovery.py
      6 tests/test_planner_capability_migration.py
     15 tests/test_planner_worker.py
     41 tests/test_session4b_memory_hardening.py
     32 tests/test_session4c_architecture.py
     35 tests/test_workflow_runtime.py
```

## 3. Red: new tests against the unchanged adapter

`tests/test_fz02_stalled_deadline_failure.py` (8 tests) plus B2a's pin test with STALLED/HARD_DEADLINE removed from its list: **7 failed, 16 passed**.
The 7 red are exactly the B2b behaviour; the 16 green include `route()` itself being unchanged:

- test_stalled_and_deadline_outcomes_fail_and_keep_their_partial[half a story-stalled]
- test_stalled_and_deadline_outcomes_fail_and_keep_their_partial[half a story-hard_deadline]
- test_stalled_and_deadline_outcomes_fail_and_keep_their_partial[None-stalled]
- test_stalled_and_deadline_outcomes_fail_and_keep_their_partial[None-hard_deadline]
- test_a_stalled_stream_fails_with_its_partial_text
- test_a_stream_that_hits_the_hard_ceiling_fails_with_its_partial_text
- test_a_stream_with_no_first_token_fails_without_partial_text

Genuine failures, not harness artifacts (no timeouts): a stalled stream returned `success=True` with `output='Beginning the tale'`; a stream that hit the hard ceiling returned `success=True` with `tok1 tok2 ...`; a stream with no first token returned `success=True` with empty output.

## 4. Change

`core/capabilities/adapters/model_router_adapter.py`: STALLED and HARD_DEADLINE leave the pinned set (renamed `_PINNED_UNCHANGED`, now `COMPLETED_WITH_PARTIAL_OUTPUT` and `EMPTY_RESPONSE` only). They return `success=False`, `output=None`, a fixed opaque error, `failure_type`/`retryable` metadata, and the partial text in `metadata["partial_output"]` when there is any (never in `output`). `route()` is untouched. Files: adapter (+19/-15 incl. comments), `tests/test_fz02_provider_failure.py` (pin list 4 -> 2), new `tests/test_fz02_stalled_deadline_failure.py`.

## 5. Green

- Both FZ-02 test files: 23 passed.
- 26 related files: **462 passed, 1 xfailed** (456 - 2 removed pins + 8 new).
- Entire suite, run alone: **8 failed, 1974 passed, 4 skipped, 1 xfailed, 4 errors**; failing set identical to baseline (none new, none gone).
- `scripts/check_drift.py` 15/15; `git diff --check` clean; all touched files LF.
- CI on the head: `drift-and-ownership` success, `tests` success (see section 7), CodeQL success with "No new alerts in code changed by this pull request" (0 annotations).

## 6. Measured user-visible effect (PlannerWorker -> AdapterRuntime -> real adapter and router; only the stream and budget replaced)

```
STALL after one token
  BEFORE (8c0ea03)  success=True  output='Once upon a time, a brave knight'
  AFTER  (B2b)      success=True  output='[Error in coding: RuntimeError (ref <id>)]'
NO FIRST TOKEN (startup deadline)
  BEFORE            success=True  output=''
  AFTER             success=True  output='[Error in coding: RuntimeError (ref <id>)]'
```

The worker-level `success=True` is FZ-01 (B3/B4), unchanged. On the planner path the truncated text a stalled generation used to show is no longer shown; it is in the adapter result's metadata and reaches the user once the D1(a) result channel carries it. The no-first-token case is a strict improvement.

## 6b. Erratum (added 2026-10-09): the section 6 measurement used a single-adapter chain

Section 6 measured the user-visible effect with only `ModelRouterAdapter` registered. Production registers three `LLM_COMPLETION` adapters (`main.py:282-287`), so after B2a/B2b a stall, provider failure or external cancel makes `AdapterRuntime` fall back to `OllamaAdapter`; the user sees an opaque error only when **every** adapter fails. B2a/B2b also activated the runtime's health and cooldown machinery for the router (one failure benches it for ~59 s), and an external cancel is treated as an adapter failure and does not stop the fallback generation. Measured effects and consequences C1-C5 are in `fz01_b3_b4_design.md`, section 2b. The B2b code and its tests are unaffected; the description of the interim effect was incomplete.

## 7. CI incident on the first run: identified by the reviewer

- Attempt 1 of the `tests` job failed at the gate step. I could not read the log or artifact (HTTP 403 for my token), so I reported the cause as unknown.
- The reviewer then read attempt 1's `pytest-output` artifact: the process crashed in `tests/test_break_concurrency.py::test_cache_concurrency` with `Fatal Python error: Illegal instruction` in ChromaDB's `chromadb/segment/impl/vector/local_hnsw.py` import path, pytest exit code **132**. That is a process-level native-runtime crash, not an assertion failure; the gate fails on any exit code other than 0 or 1 by design. The precise cause is not established (not claimed to be a runner or hardware incompatibility).
- Re-running only the failed job on the identical head passed. B2b's code was not changed in response. (The test is one of the 34 allowlisted entries, but a crash cannot be allowlisted.)
- My own checks agree: my new tests passed 10/10 on a quiet machine and 41/41 under sustained CPU contention; 38 of 39 other `tests` runs over ~5 days were green.
- Classification: a native-runtime incident, not a reproduced functional regression.

## 8. Reviewer notes and open items

1. `route()` labels every non-stall cancellation `HARD_DEADLINE` (deadline, startup window, external cancel), so the HARD_DEADLINE failure message is deliberately neutral. Pre-existing; not changed.
2. `COMPLETED_WITH_PARTIAL_OUTPUT` is defined but never produced by `route()`; it stays pinned. `EMPTY_RESPONSE` stays pinned (PR #67 ruling).
3. The adapter's `error` can reach users: fixed text only, never exception text, hosts or partial text (tested).
4. Other adapters were not inspected.
5. Docs not touched: the FZ-02 register row now describes a closed provider-failure half and a closed stalled/deadline half; that correction waits for the next natural doc sync.
6. **Adjacent issue, tracked separately (not in PR #71).** In `ModelRouter.route()`'s monitored-streaming branch (`core/model_router.py:179-181`) the answer is recorded as a training pair, the module's `query_count` is incremented and `_maybe_promote()` is called **unconditionally**, whatever the outcome. `stream_route()` does the same at 264-270. `_record_training_pair` filters only on the privacy setting and an empty answer. Demonstrated on merged `main` (`27d918d`) with the HTTP/stream faked:

   | scenario | outcome | training pair recorded | query_count |
   |---|---|---|---|
   | connect error | provider_failure | `[Error: model request failed (ref ...)]` | +1 |
   | empty stream | empty_response | none (empty filter) | +1 |
   | stall with partial | stalled | `Beginning the tale` | +1 |

   So failed or partial generations are persisted as training data and count toward bootstrap -> shadow promotion. This predates B2a/B2b (B2a only made the failure visible); both PRs' tests neutralise these side effects. Needs its own disposition (suggested: register it with the next doc sync and fix in its own batch).
