# FZ-02 / batch B2a: baseline and evidence record

Review target (immutable): `main` = `8b0fee2`
Branch: `fix/fz02-provider-failure-oct2026` (pushed; PR #67 open; not merged; not updated from `main`)

| commit | what |
|---|---|
| `0a6d342` | `style:` CRLF to LF for `core/model_router.py` (whitespace-only; `git diff --ignore-cr-at-eol` is empty) |
| `728bbfd` | `fix(FZ-02/B2a):` the change plus `tests/test_fz02_provider_failure.py` |
| `c2f6070` | `fix(FZ-02/B2a):` scope correction from review: `EMPTY_RESPONSE` pinned unchanged, plus tests |

Decisions in force: D1 = (a) additive result contract, D2 = (i) failure carrying partial output.
B2a implements neither: it only makes provider failures fail. Stalled, deadline and partial outcomes are pinned unchanged.

## 1. Register text preserved verbatim (KNOWN_ISSUES.md @ 8b0fee2)

| FZ-02 | ModelRouter/Ollama false completion: `_ollama_stream()` yields its error text as a normal token and returns normally; `ModelRouterAdapter.execute()` hard-codes `success=True` and ignores `route_result.execution_detail`. | **OPEN -- BLOCKED on D2** (not started; batch B2) | Reproduced with the real router and adapter, only the HTTP client faked to raise `ConnectError`: `RouteResult.execution_detail.failure_type = success`, `CapabilityResult.success = True`, output = the error token. Code path re-confirmed by inspection on `e438387` (`except Exception` in `_ollama_stream` yields an in-band `[Error: ...]` token; `ModelRouterAdapter.execute` returns `success=True` and never reads `execution_detail`); repro not re-run since. | D2: stalled/deadline outcomes with partial output. Its prerequisite FZ-04 is now met. Other adapters' semantics were not re-inspected. |

## 2. Baseline at 8b0fee2, before any change

- 24 test files that reference the router, adapter or outcome types: **439 passed, 1 xfailed, 0 failed**.
- Entire suite: **8 failed, 1943 passed, 4 skipped, 1 xfailed, 4 errors**. The failing/erroring ids are identical before and after (list in section 6).

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

## 3. Red: new tests against the untouched logic

`tests/test_fz02_provider_failure.py` (original 16-test version, measured before the `EMPTY_RESPONSE` correction): **10 failed, 6 passed** at baseline. The 6 passing are the pins (healthy success, SSE text, the three stalled/deadline/partial outcomes, the no-detail path). Failing at baseline (10):

- test_error_token_is_marked_but_its_text_is_unchanged
- test_connect_error_is_classified_provider_failure
- test_adapter_reports_failure_when_the_provider_is_unreachable
- test_mid_stream_drop_fails_and_preserves_the_partial_text
- test_a_stream_that_raises_also_fails_at_the_adapter
- test_non_success_outcomes_fail_closed[provider_failure]
- test_non_success_outcomes_fail_closed[empty_response]
- test_non_success_outcomes_fail_closed[cancelled]
- test_non_success_outcomes_fail_closed[validation_error]
- test_non_success_outcomes_fail_closed[other_failure]

Key assertion failures at baseline: `failure_type == success` where `provider_failure` is expected; adapter `success is True`; `ProviderStreamError` absent.

## 4. Before / after: the register's own reproduction (real router + real adapter, only the HTTP client faked to raise ConnectError)

```
BEFORE (8b0fee2)
route():   failure_type = success | retryable = False
           answer       = [Error: model request failed (ref <id>)]
adapter:   success      = True
           output       = '[Error: model request failed (ref <id>)]'
           error        = ''
           metadata     = {}

AFTER (B2a)
route():   failure_type = provider_failure | retryable = True
           answer       = [Error: model request failed (ref <id>)]        <- text unchanged for SSE/consumers
adapter:   success      = False
           output       = None
           error        = 'model provider failure (ref <id>)'
           metadata     = {'failure_type': 'provider_failure', 'retryable': True, 'error_id': '<id>'}
```

## 5. End-to-end interim effect (PlannerWorker -> AdapterRuntime -> real adapter/router; only HTTP faked)

```
BEFORE  _dispatch_module RETURNED RouteResult (answer = the error token)
        PlannerWorker.execute: success=True, error=''
        output = '[Error: model request failed (ref <id>)]'      provider calls: 1
AFTER   _dispatch_module RAISED RuntimeError("All 1 adapter(s) failed for 'llm_completion'. Last: model provider failure (ref <id>)")
        PlannerWorker.execute: success=True, error=''
        output = '[Error in coding: RuntimeError (ref <id>)]'    provider calls: 1
```

## 6. After the change

- New tests: **17 passed** (corrected head `c2f6070`; the 7 pinning tests also pass on the untouched `8b0fee2` logic).
- 24 related files: **439 passed, 1 xfailed** (unchanged).
- Entire suite, run alone: **8 failed, 1960 passed, 4 skipped, 1 xfailed, 4 errors** (+17 = the new tests). Failing set identical to baseline: 12 ids, none new, none gone.
- `scripts/check_drift.py`: 15/15. `git diff --check`: clean. All touched files LF.

Pre-existing failing/erroring ids (same on both trees):

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

Note: an earlier run executed the baseline and fixed suites concurrently and showed one extra failure,
`tests/core/sandbox/test_namespace_backend.py::test_cancel_kills_all_descendant_processes`. That test uses a
system-wide `pgrep -f "sleep 50"`, so it saw the other tree's processes. It passes 3/3 on both trees in isolation,
and the clean sequential run above has no such failure. (A test-isolation weakness, not related to B2a.)

## 7. Newly exposed or confirmed issues (none fixed in B2a)

1. **FZ-01 unchanged by design.** `PlannerWorker.execute` still returns `success=True` on a provider outage; the failure is contained and formatted into the answer text. Real fix is B3/B4 under D1(a).
2. **User-visible error text changes and loses the adapter's ref.** `[Error: model request failed (ref A)]` becomes `[Error in coding: RuntimeError (ref B)]`. B is the planner's own opaque ref; A appears only in the log line. Still visible and non-empty, less specific. Candidate for B3/B4.
3. **Stalled / hard-deadline outcomes with no partial text** still return `success=True` with an empty answer. Pinned; B2b under D2(i).
4. **Non-monitored branches** (`execution_detail=None`) were checked: `generate_with_fallback` raises `RuntimeError` after exhausting providers (`core/provider_mesh.py:226`) and `_call_external` has no `except`, so they fail loudly. Only the monitored long-form stream swallowed errors, so B2a covers the whole FZ-02 mechanism. Other adapters were not inspected.
5. **`EMPTY_RESPONSE` pinned unchanged (review ruling).** `route()` emits it when a monitored stream ends with no output and no failure (`core/model_router.py:475`). The first B2a commit made the adapter fail closed on it; the reviewer ruled that out of scope. `c2f6070` moves it to the pinned set (adapter keeps `success=True`), and an end-to-end test through the real router proves today's behaviour is preserved. Whether an empty stream is a failure is left to the later outcome-policy work.
6. `main` moved to `58d079f` (PR #63, orchestrator failure-text redaction) after the review target `8b0fee2`. No file overlap with B2a; dry-run merge is clean. PR #63 follows the same CWE-209 policy as the adapter's opaque error.
