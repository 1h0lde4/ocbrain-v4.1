# FZ-01 / batches B3-B4: design and batch decomposition (read-only study)

Baseline: `main` = `1d813bd` (FZ-02 B2a + B2b merged; PRs #73/#74 since touched only dependency governance and docs).
Status: **PROPOSED, revision 2** (corrected after reviewer findings; revision 1 wrongly assumed a single `LLM_COMPLETION` adapter and left the planner boundary undefined). No code written, no branch created. Decision D1 = (a) (additive result contract) is taken; the sub-decisions in section 7 are not.
Line numbers refer to `main` at `1d813bd`.

## 1. Problem (register FZ-01, unchanged)

"K4.2 path has no failure channel: `core/orchestrator.py` reads `wf_result.output or ""` and never `wf_result.success` for node errors, and the non-streaming `/query` returns `success=True` for any normal return (audit repro: HTTP 200, `success=True`, empty answer while the workflow had failed)."
Register requirements: the channel must distinguish **node failure, DEBT-020 constraint under-delivery and cancellation**; streaming needs a **terminal in-band event**; it depends on FZ-02 (done) so real failures reach it.
Obligation inherited from B2b (your ruling): **partial output must reach the user through the proper result channel; adapter metadata alone is not delivery.**

## 2. Finding: the failure is lost in four layers, not one

| # | layer | where | what happens to a failed generation |
|---|---|---|---|
| 1 | AdapterRuntime | `core/capabilities/adapter_runtime.py:117-134` | A `success=False` adapter result contributes only its `error` string (to an `adapter.failed` event and `last_error`); the loop tries the next adapter; the final result is a *new* `CapabilityResult` with only `adapters_tried` in metadata. `failure_type`, `retryable`, `error_id`, `partial_output` are dropped. |
| 2 | PlannerWorker | `core/workers/planner.py:164-190` | `_dispatch_module` raises on `not success`; `gather(return_exceptions=True)` turns the exception into `RouteResult(answer="[Error in {mod}: {Type} (ref ...)]", source="error")`; `merger.merge()` folds it into the single answer string. The worker then reports `success=True`. This folding is intentional and tested (partial-module-failure containment). |
| 3 | WorkflowRuntime | `core/workflow/runtime.py:104-126, 195+` | `WorkflowResult` has `success`, `error`, `constraint_violations`, `node_results`, `metadata`: enough room. But `execution_detail` is deliberately **not restored on resume** (ADR-KERNEL-03), while `metadata` is serialized and restored. |
| 4 | Orchestrator | `core/orchestrator.py:188-901` | The K4.2 site (~L532) takes `wf_result.output or ""` and ignores `success` for genuine node errors (its own comment calls this a separate gap); `handle() -> str` has no way to express failure anyway. |

Edge: `interface/api.py:187-191` (`/query`) wraps any normal return as `success=True`; the streaming path (`api.py:380-400`) always ends with `execution.completed`; `core/brain_api.py:122,181` is a second API surface whose `QueryResponse` has **no** `success`/`error` field at all.

## 2b. Live effect of B2a/B2b through the production adapter chain (measured; new in revision 2)

Correction: revision 1 assumed one adapter for `LLM_COMPLETION`. `main.py:282-287` registers three, in this order: `ModelRouterAdapter`; `OllamaAdapter` (non-streaming `OllamaProvider.generate` on the same default Ollama host, no watchdog, raw exception text in its `error`); `OpenAICompatAdapter` (unavailable without configuration, so skipped here). `AdapterRuntime.invoke` ranks the available adapters by health and tries the next one on failure; `BaseAdapter.mark_failure` costs 20 health and sets a cooldown of 60 s x 2^(consecutive failures - 1), capped at 1 h, during which the adapter is skipped.
Before B2a, `ModelRouterAdapter` never reported failure, so this machinery never engaged for it. B2a/B2b (already on `main`) made failures real and thereby activated it. Measured with the real runtime, registry, router and adapters; only the provider streams / `generate` and the budget were faked (`/tmp/b3/probe_chain.py`, fresh budget per request):

| scenario | pre-B2 (`8b0fee2`) | now (`1d813bd`) |
|---|---|---|
| stall, Ollama works | router "succeeds" with the partial text (2.0 s); router stays healthy | router fails, **`OllamaAdapter` generates a full answer** (stall window + a second generation); router benched **~59 s**; the next request goes straight to `OllamaAdapter` (0.0 s, router bypassed) |
| stall, Ollama down | partial text as success | **`success=False`** once both fail; final error is the *last* adapter's raw text (`OllamaProvider error: conn...`); both benched; next request: "All adapters in cooldown; forced choice: OpenAICompatAdapter" |
| provider error, Ollama works | the error token returned as the answer | router fails, `OllamaAdapter` answers; router benched ~59 s |
| **user cancels** (external cancel) | partial text as success | router fails (route() labels it `HARD_DEADLINE`), **`OllamaAdapter` still generates a full answer despite the cancel**; router benched ~59 s |
| healthy | router answers | unchanged (router answers, no state change) |

Consequences, all live on `main` now and none part of the B2a/B2b reviews:
- **C1** One failed, stalled or cancelled generation benches `ModelRouterAdapter` for a minute (then 2, 4, ... up to an hour on repeats). All `LLM_COMPLETION` traffic, short requests included, then bypasses the router: no stage logic (bootstrap/shadow/native), no training-pair recording, no watchdog.
- **C2** A stalled generation now costs the stall window plus a second full generation on the same backend.
- **C3** External cancellation is not terminal: it is treated as an adapter failure, work continues on another adapter, and the router is penalised for the user's own action.
- **C4** After a fallback the user receives another adapter's answer with no signal that it came from a different path.
- **C5** When every adapter fails, the final `CapabilityResult.error` carries the last adapter's raw exception text, and the router's structured failure is gone.
- **Correction to the B2b record:** the "interim effect" in PR #71 (an opaque error line instead of the truncated text) was measured on a single-adapter chain. In production it applies only when every adapter fails; otherwise the user gets the fallback adapter's answer.

Caveats: the router and `OllamaAdapter` are assumed to share one backend (both default to `localhost:11434`; production config not inspected); `OpenAICompatAdapter` was unavailable in this environment; real `OllamaProvider` timeouts were not exercised. My first run of this probe was contaminated by one shared, mutable `ExecutionBudget` (a non-frozen dataclass) and was discarded; production builds a fresh budget per request.

## 3. Contract proposal (D1 = (a))

New pure module `core/result_contract.py` (frozen dataclasses, no I/O, `to_dict()` for the API):

```
HandleStatus: OK | DEGRADED | FAILED | REFUSED | NEEDS_INPUT | CANCELLED
HandleResult: answer: str            # exactly what handle() returns today
              status: HandleStatus
              reason: str            # stable code, e.g. "workflow_node_failed", "constraint_unmet"
              error: str             # opaque only (fixed text + ref), never exception text
              partial_outputs: tuple[PartialOutput, ...]   # (module, failure_type, text)
              constraint_violations: tuple[str, ...]
              execution_id: str
```
`Orchestrator.handle_result()` becomes the implementation; `handle()` becomes a thin wrapper returning `.answer`. **Existing callers and tests are untouched**: `handle()` is used by 18 test files (61 call sites) and by `main.py:443` (fire-and-forget), `scripts/integration_check.py` and `brain_api`.

`handle()` has **14 return paths** (L251, 262, 430, 447, 508, 520, 649, 665, 731, 759, 773, 809, 892, 901). Proposed mapping:

| exit | path | status / reason |
|---|---|---|
| L251 governance REJECT | governance | REFUSED / governance_blocked |
| L262 governance ESCALATE | governance | NEEDS_INPUT / approval_required |
| L430 no suitable approach | K4.2 | FAILED / no_approach |
| L447 conflicting requirements | K4.2 | NEEDS_INPUT / conflicting_requirements |
| L508 clarification | K4.2 | NEEDS_INPUT / clarification |
| L520 not prepared for execution | K4.2 | FAILED / preparation_failed |
| L649 workflow answer | K4.2 | OK, or DEGRADED (constraint_unmet / module failures), or FAILED (`wf_result.success` False), or CANCELLED |
| L665 outer failure | K4.2 | FAILED / internal_error |
| L731 workflow failure (ref) | legacy | FAILED / workflow_failed |
| L759 workflow answer | legacy | OK / DEGRADED / FAILED as L649 |
| L773 outer error | legacy | FAILED / internal_error |
| L809 no module | bridge | NEEDS_INPUT / no_module |
| L892 bridge answer | bridge | OK |
| L901 outer error | all | FAILED / internal_error |

Distinctions the register demands: node failure = FAILED/`workflow_node_failed`; DEBT-020 under-delivery = DEGRADED/`constraint_unmet` (+ `constraint_violations`); cancellation = CANCELLED.

## 4. Crossing the boundaries: B3a specification (revision 2)

Rules (unchanged): (a) partial text is **never** placed in `answer`/`output`; (b) it is delivered in a **dedicated field** (`HandleResult.partial_outputs` -> API `meta.partial_output`); (c) it travels in **`WorkerResult.metadata`**, never `execution_detail`, because only `metadata` survives checkpoint/resume; (d) it is **not** written into events (size and disclosure); events carry `failure_type`/`error_id`/counts only. B3a is **additive**: answer text, `WorkerResult.success`, adapter ranking, health marking, fallback and cooldowns must all remain exactly as they are, and tests pin each.

**B1. AdapterRuntime -> caller.** The final failure `CapabilityResult.metadata` gains `attempts`: an ordered list, one entry per adapter tried: `{adapter, failure_type, retryable, error_id, has_partial}`, taken from the failed result's own metadata (B2a/B2b adapters set these; an adapter that does not gets `{adapter, failure_type: "adapter_failed"}`), plus `partial_outputs`: `[{adapter, text}]` for failed attempts that produced partial text (text lives only here). All attempts are kept, not just the last, because with three adapters the last failure is usually not the router's. An attempt's raw `error` string is **never** copied (`OllamaAdapter`'s contains exception text); the existing final `error` string stays for logs and compatibility but is documented as non-user-facing.
**B2. Planner boundary.** `PlannerWorker._dispatch_module` today raises a bare `RuntimeError(capability_result.error)`, which discards the metadata. It will raise a typed `CapabilityInvocationError(RuntimeError)` carrying `.result` (the failed `CapabilityResult`). The user-visible folded text must not change: `_run()` formats with `type(res).__name__`, so a one-line `_public_error_name(exc)` returns `"RuntimeError"` for the new class, pinned by a test that compares the folded text before and after. (Rejected: setting attributes on a plain `RuntimeError`, which is implicit.)
**B3. Planner -> worker result.** After `gather`, each `CapabilityInvocationError` becomes a `module_failures` entry `{module, attempts, partial_outputs}` (JSON-serializable) on the worker's `WorkerResult.metadata`. `success`, `output` and the folded text are unchanged in B3a.
**B4. Partial text under fallback.** If a later adapter succeeds, earlier partial text is moot (not delivered, not logged). If all fail, the partials of the failed attempts travel (in practice one: only the monitored router produces partial text).
**B5. Resume.** Everything above is in `WorkerResult.metadata`, which is serialized and restored; `execution_detail` is not relied on.
**B6. Raw text rule (binds B3b).** `HandleResult.error` is opaque (fixed text + ref) and never contains `CapabilityResult.error`, which can carry raw exception text.

## 5. Streaming and other consumers (B4)

- `/query` (`api.py:187`): switch to `handle_result()`; `success = (status == OK)` under the recommended policy (section 7, D1.1); `error`, `meta.status`, `meta.reason`, `meta.partial_output` added; schema shape unchanged (`QueryResponse` already has `success/data/answer/error/meta`).
- `/query?stream` multi-module path (`api.py:380-400`): `FAILED`/`CANCELLED` end with a terminal `{"type":"execution.failed", ...}` frame and the EventStream `execution.failed` instead of `execution.completed`; `DEGRADED` ends with `execution.completed` carrying `status:"degraded"`.
- Single-module stream (`_stream_response`): B2a's `ProviderStreamError` is a typed `str`, so the API loop can detect a provider failure *in the token stream* and emit the terminal failure frame. (DEBT-017's stream bypass is not widened or fixed here.)
- `core/brain_api.py`: additive `success`/`error`/`status` fields; `main.py:443`: log non-OK statuses instead of discarding.

## 6. Batch decomposition (PROPOSED; the register does not define the B3/B4 split)

| batch | scope | behaviour change | key evidence (red first) |
|---|---|---|---|
| **B2c** (proposed; live effect, see 2b) | Cancellation is terminal: `route()` classifies an external cancel as `CANCELLED` (not `HARD_DEADLINE`); `AdapterRuntime` treats a `CANCELLED` failure as terminal: no further adapters, no health penalty | live routing and health behaviour (**not additive**) | the user-cancel row of 2b red -> green; stall / provider-error / healthy rows unchanged |
| **B3a** carry | Section 4 B1-B5: `attempts` + `partial_outputs` through AdapterRuntime, typed `CapabilityInvocationError` at the planner boundary, `module_failures` in `WorkerResult.metadata`. Additive; ranking, health, fallback, `success` flags and text untouched. | none user-visible | attempts survive `invoke` across three adapters; folded planner text byte-identical; `success` unchanged; selection/cooldown tests unchanged; resume round-trip keeps `module_failures` |
| **B3b** contract | `result_contract.py`; `handle_result()` over all 14 exits; K4.2 site reads `wf_result.success`/`constraint_violations`/node metadata; legacy site parity; `handle()` wrapper | `handle()` output text unchanged; new structured result | one test per exit (14); K4.2 node-failure repro red->green; DEBT-020 stays distinct; the 18 existing test files pass untouched |
| **B4a** `/query` | API uses `handle_result()`; `success=False` for non-OK per D1.1; opaque `error`; `meta` fields | **client-visible**: `success` flips for failures | audit repro (HTTP 200, `success=True`, empty answer) red->green |
| **B4b** streaming | terminal in-band failure frame + EventStream event; provider failure detected in single-module stream | stream ending changes for failures | stream tests for failed/degraded/cancelled; SSE text for success byte-identical |
| **B4c** consumers | `brain_api` additive fields; `main.py` logs statuses; scripts unchanged | additive | brain_api failure repro |

Each batch: own branch off the then-current `main`, single owner, immutable review target, sign-off then update then merge, as for B2.
FZ-06/B5 (identity) follows B3b so new failure events carry correct identity; B6/B7 unchanged. Order (revision 2): **B2c if approved**, then B3a, B3b, B4a-c. B3a stays additive and is no longer described as risk-free: it touches three layers and its safety rests on the pinning tests above.

## 7. Decisions needed (recommendations are mine; none is taken)

- **D1.1 `success` semantics.** Recommended (minimal): `success=False` only for FAILED, DEGRADED and CANCELLED (execution outcomes); REFUSED and NEEDS_INPUT keep `success=True` as today and are distinguished by `meta.status`. Strict alternative: `success = (status == OK)`, which also flips refusals and clarifications and is a larger client-visible change.
- **D1.2 partial text placement.** Recommended: dedicated field (`meta.partial_output`), `answer` stays the opaque error line. Alternative: append labelled partial text to `answer` (re-creates the "truncated text looks like an answer" hazard B2b removed).
- **D1.3 HTTP status for failures.** Recommended: keep HTTP 200 with `success=False` (clients already parse `QueryResponse`); alternative 5xx for FAILED.
- **D1.4 multi-module partial failure.** Recommended: some modules failed -> DEGRADED; all modules failed -> FAILED (WorkerResult.success=False), and the opaque `[Error in ...]` lines stay in the answer text.
- **D1.5 order.** Recommended: B2c (if approved), then B3a, as above.
- **D2.1 (new) cancellation.** Approve B2c as a separate behaviour batch before B3a? Recommended: yes. C3 is live now, B3a/B3b are additive and cannot fix it, and the fix is small and has a clear invariant (a cancel stops work and is not a health event).
- **D2.2 (new) health policy (C1).** Keep the generic cooldown for provider failure / stall / deadline, count only provider failures, or use per-type penalties? Recommended: keep for now (it is the runtime's designed behaviour) but decide knowingly once B2c removes the cancel case; changing health policy without production data is speculative.
- **D2.3 (new) fallback after a stall (C2/C4).** Allow it (current) or make a stall terminal? Recommended: allow, and make it visible later (B3b exposes which adapter answered and that a fallback occurred).

## 8. Cross-cutting checks (project rules 18.3 / 22.2)

- **Governance:** no new autonomous capability or authority boundary; refusal outcomes keep today's governance verdict path and text.
- **Replay/checkpoint:** failure info rides `WorkerResult.metadata` (serialized, restored); `execution_detail` is not relied on.
- **Observability:** `orchestrator.query_failed`/completed events gain `status`/`reason`/`error_id`; never partial text.
- **Security:** `HandleResult.error` is opaque (fixed text + ref), same CWE-209 policy as PR #63 and the adapter; partial text is model output only and goes to the caller who would have seen it before B2b.
- **Compatibility/rollback:** additive; `handle()` unchanged; each batch is independently revertible.

## 9. Risks and unverified items

1. **(corrected)** Three `LLM_COMPLETION` adapters are registered and fallback plus cooldown are live: see section 2b. Not verified: real `OllamaProvider` timeouts, and whether the router and Ollama share a backend in production configuration.
2. `merger.merge()` behaviour with `source="error"` entries was not read; B3a must confirm the folded error lines survive for DEGRADED detection.
3. The legacy (K2.2) and K4.2 sites duplicate result handling; B3b must keep them in parity.
4. The HTTP-level audit repro (`ecddbff`) has not been re-run on current `main`; B4a will run it first.
5. `OllamaAdapter` and `OpenAICompatAdapter` were read for failure behaviour only; their provider internals were not inspected.
6. Raw exception text exists in `OllamaAdapter`'s `error` and in the final AdapterRuntime error; it is log-only today and must stay out of every user-facing channel (rule B6).

## 10. Out of scope, tracked separately

- Training-pair and `query_count` side effects on non-success monitored outcomes (verified on `main`; its own batch).
- FZ-05 (registry), FZ-06 (identity, B5), #54 follow-ups (TOCTOU, bundle validation), documentation corrections (FZ-02 row, FZ-05 wording, DEBT-033 row).
