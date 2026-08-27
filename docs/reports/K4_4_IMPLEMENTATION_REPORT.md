# K4.4 — Execution Budget / Watchdog: Implementation Report

**Base commit:** `5197d88` (`main`) — public clone, unauthenticated, read-only against the real repo.
**Working branch:** `feature/execution-budget-watchdog` — **local to this sandbox only, not pushed.** No valid GitHub credential was used or should be (the token pasted into this conversation is compromised — see earlier in the thread — and this environment has no path to your local Ollama process regardless). What follows is a patch (`0001-execution-budget-watchdog.patch`) plus the new files standalone, for review and for Claude Code to actually land and live-validate.

---

## A. Scope actually implemented (read this first)

The "Claude Code Implementation Prompt" scoped six things: Execution Budget, Progress Monitor, Execution Watchdog, Execution Graph, User-Safe Progress Projection, Canonical Execution Events. **This pass implements the first three, plus the ModelRouter/limits.py integration and the additive WorkerResult extension — not the graph, projection, or event vocabulary.**

This was a deliberate cut, not an oversight: the first three (plus integration) are what actually fixes the reported bug — a 1000-word story no longer dies at a flat 60s. The graph/projection/events exist to *later* drive the Thinking-UI, which is explicitly a separate pass in every document in this thread so far. Implementing all six to the same tested standard in one sitting, with no live Ollama to validate against, risked a worse outcome than a smaller, fully-tested slice. Treat §I below as the concrete next-PR list.

---

## B. Root cause, confirmed

Traced twice now (static analysis last session, re-confirmed against the same commit this session): `generate_with_fallback()` → `safe_llm_call()` → `asyncio.wait_for(..., timeout=60.0)`, hardcoded, reached by `ModelRouter.route()` for every ordinary chat generation. `stream_route()`/`_ollama_stream()` existed but was never called by the live adapter path.

## C. What changed

| File | Change |
|---|---|
| `core/runtime/execution_budget.py` **(new)** | `ExecutionBudget` (deadlines + bounded-extension accounting) and `ExecutionPolicy` (derives a budget from config + observed historical throughput, safe fallback when neither exists). `default_budget()` is bit-for-bit equivalent to the old hardcoded 60s for un-budgeted callers. |
| `core/runtime/progress_monitor.py` **(new)** | Generic `ProgressMonitor` — distinguishes "activity" from "meaningful progress" so whitespace/keepalive chunks can't indefinitely suppress stall detection. Not LLM-specific; nothing in it assumes tokens. |
| `core/runtime/execution_watchdog.py` **(new)** | `ExecutionWatchdog` — pure `_decide()` function (detection + intra-operation recovery policy) wrapped in an async supervision loop that sleeps until the next relevant deadline. Its only terminal action is calling the existing, **unmodified** `CancellationToken.cancel(reason)` — never a second cancellation path. `CancelReason` is a `str`-backed enum so every existing `cancel()` caller is unaffected. |
| `core/runtime/execution_outcome.py` **(new)** | `ExecutionOutcome` / `FailureType` — structured classification (`stalled`, `hard_deadline`, `provider_failure`, `empty_response`, ...) replacing the generic-exception-collapses-to-"No response" pattern. |
| `core/runtime/limits.py` | `safe_llm_call()` gained an additive, optional `budget: Optional[ExecutionBudget] = None` kwarg. Unset (every existing caller today) → identical behavior to before. |
| `core/provider_mesh.py` | One-line stale-comment fix (said 30s, was actually 60s). No logic change — `generate_with_fallback` still uses the plain default path; it's correct for it to. |
| `core/runtime/execution_context.py` | Additive `execution_budget: Optional[ExecutionBudget] = None` field. Nothing removed, nothing renamed — respects "fields are additive-only." |
| `core/workers/base.py` | Additive `execution_detail: Optional[ExecutionOutcome] = None` field on `WorkerResult`. |
| `core/model_router.py` | The actual fix. `route()` gained a branch: an explicit long-form request (`_estimate_long_form()` — see §I for what this heuristic is and isn't) on `bootstrap`/`native` stage is routed through a new `_call_monitored_streaming()` method instead of `generate_with_fallback`. That method reuses the **existing, unmodified** `_stream_external`/`_stream_own`/`_ollama_stream` generators, feeding a `ProgressMonitor` per chunk and running an `ExecutionWatchdog` concurrently via `asyncio.wait(FIRST_COMPLETED)` against the consumer task — see §H for why a simple cooperative check isn't enough here. `RouteResult` gained an additive `execution_detail` field so the outcome reaches the caller. |
| `config/settings.toml` | New `[runtime]` keys: `default_startup_budget_s`, `default_progress_budget_s`, `default_hard_ceiling_s`, `max_budget_extension_s`, `default_short_request_ceiling_s`. `max_recovery_attempts` (ADR-H-05's, unrelated) untouched. |

## D. Recovery-boundary compliance (ADR-K4.2-H-05)

Nothing here reads or writes `OperationRecoveryBudget` (`core/cognitive/recovery.py`). The watchdog's "bounded extension" is a one-shot-per-stall-episode grace period, intra-operation only, bounded by `ExecutionBudget.max_extension_s` — it never re-enters the Planner, never triggers Supervisor re-entry, never creates a new operation. This is enforced by construction (nothing in the new code has a reference to `OperationRecoveryBudget`), not just by convention.

## E. Freeze-integrity check (§32 of the Claude Code prompt)

Done by direct comparison, not by "tests passed so it must be fine":
- `CancellationToken` (`core/runtime/cancellation.py`): **zero lines changed.** Confirmed via `git diff` — not in the changed-files list at all.
- `OperationRecoveryBudget` / `core/cognitive/recovery.py`: **zero lines changed**, not touched, not imported by any new module.
- `ExecutionContext`: one additive field, default `None`. Existing fields unchanged.
- No second cancellation primitive, no second recovery budget, no second provider abstraction, no ModelRouter↔ProviderMesh import cycle (confirmed: `core/provider_mesh.py`'s only change is a comment).

## F. Tests

New: `test_execution_budget.py` (16), `test_progress_monitor.py` (13), `test_execution_watchdog.py` (16, including the pure `_decide()` branch matrix and the full async loop), `test_model_router_monitored_streaming.py` (6, including an integration test that reproduces the original bug's shape end-to-end).

Regression: ran every existing test file that imports anything touched by this change — `test_model_router.py`, `test_runtime_limits.py`, `test_context.py`, `test_context_builder.py`, `test_orchestrator_recovery.py`, `test_supervisor_worker.py`, `test_planner_worker.py`, `test_reflection_worker.py`, `test_evaluator_worker.py`.

**Result: 186 passed, 0 failed, 5.13s.** Exact command:
```
python -m pytest tests/test_model_router.py tests/test_model_router_monitored_streaming.py \
  tests/test_runtime_limits.py tests/test_context.py tests/test_context_builder.py \
  tests/test_orchestrator_recovery.py tests/test_supervisor_worker.py tests/test_planner_worker.py \
  tests/test_reflection_worker.py tests/test_evaluator_worker.py tests/test_execution_budget.py \
  tests/test_progress_monitor.py tests/test_execution_watchdog.py -v
```
Not run: the rest of `tests/` — 25 files fail to collect in this sandbox on missing `chromadb`/`sentence-transformers` (heavy ML deps deliberately not installed here; unrelated to this change — confirmed these same files fail identically on an unmodified checkout). Claude Code, with the full `requirements.txt` installed, should run the complete suite.

**The test worth reading, not just trusting:** `test_monitored_streaming_actually_interrupts_a_hung_provider`. My first draft of the consumption loop checked `token.is_cancelled` *between* chunks — which does nothing if the provider stops yielding entirely (exactly the failure mode in question). Writing this test caught it before it shipped; the fix races the watchdog against consumption via `asyncio.wait(FIRST_COMPLETED)` and force-cancels the stuck consumer task. Worth Claude Code's attention specifically because it's the one place this patch relies on `asyncio.CancelledError` propagating cleanly out of `_ollama_stream`'s `httpx` read — architecturally sound, but only a live run actually proves it against real httpx/Ollama behavior (see §G).

## G. Live-provider validation — not done, and can't be from here

This sandbox is an isolated cloud container with no path to your local Ollama process, independent of any network setting. Not done, in order of how much they matter:
1. Re-running `Hi` and the original 1000-word request against real Ollama.
2. Confirming `asyncio.CancelledError` actually unwinds cleanly through `_ollama_stream`'s live `httpx` stream (reasoned about in §F, not observed).
3. Tuning `_FALLBACK_TOKENS_PER_SEC = 12.0` (a guess) against your actual hardware's real throughput.
4. The `why did this error happen` follow-up-diagnostics wiring from the original spec — `execution_detail` now reaches `RouteResult`, but I did not trace further upstream to wherever conversation history / follow-up turns would read it. Unknown how far that is from "done."

## H. Known limitations (disclosed, not hidden)

- **`_estimate_long_form()` is a regex for explicit word counts** ("1000 words"), nothing more. It matches the original bug report exactly and is deliberately conservative — no match defaults to the old, unchanged fast path, so it can't misclassify ordinary chat as long-form. It does **not** implement the "estimated execution cost" model from context size / reasoning complexity / tool usage that the original spec describes as the long-term target. That's real remaining work, not done here.
- **`shadow` stage is excluded** from the monitored path (falls through to today's unchanged behavior). Running two concurrent monitored streams, each under its own watchdog, for a shadow-mode comparison is real additional complexity, not a one-line extension.
- **One grace period per execution, not per stall episode** — if generation stalls, resumes, then stalls again well after the first grace window closed, it gets a fresh evaluation naturally; if the second stall happens to land *inside* the first grace window's timestamp, it waits out the old window rather than granting a distinct one. Bounded and safe (never exceeds `max_extension_s` total), just not perfectly precise in that narrow overlap case.
- **`config/models.toml` line-endings**: observed `core/config.py`'s `Config` singleton rewrite this file's line endings (`\r\n`→`\n`, content otherwise identical) merely from being imported and touched during test runs — reverted both times it happened, not included in the patch. Pre-existing behavior, not caused by this change, but worth knowing about if it surprises someone later.
- **Throughput history is process-local and non-durable** (module-level dict) — resets on restart. Flagged as a future durable-execution integration point in the original spec; not addressed here.

## I. Concrete next steps for Claude Code

1. `git apply 0001-execution-budget-watchdog.patch` on a fresh `main` pull (verify base commit still matches — re-verify `main` state first, per this thread's own repeated finding that it drifts).
2. Run the full suite with real dependencies installed.
3. Live-validate per §G.
4. Then, as a separate pass: `ExecutionGraph`, canonical event vocabulary, `User-Safe Progress Projection`, SSE wiring — per the Claude Code prompt's §15–21, now with a working, tested budget/monitor/watchdog layer under them instead of a design doc.
