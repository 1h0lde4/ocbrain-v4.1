# OCBrain Cancellation Architecture — Final Gap Study and DEBT-105 Contract Decision Package (November 1, 2026; revision 2.2, November 3, 2026)

**Status:** STUDY / DECISION PACKAGE — read-only research. **Nothing in this document is ACCEPTED.** Every design statement is PROPOSED until the repository owner decides.
**Audited against:** `main` = `ed3d141e4bbfd0231afb1104d0a7479419f9bbf1` (merge of PR #104, Oct 31, 2026) — the baseline at which every probe ran and every citation was first verified. **Revision 2 (Nov 3, 2026; 2.1 added the D-14 sequencing input and **2.2 records the owner's D-14 decision**, §21.9)** incorporates the owner review (§21) and reconciles to current `main` = `2491ae469edd6ef1267a14604c4f8f40d698f7ea` (PR #106 merge): every audited cancellation-path source file has an identical blob at both SHAs (§21.1), so file/line citations hold at either. The original baseline evidence is preserved, not rewritten; corrections of this study's own wording are listed in §21.2–§21.6.
**Method:** direct source reading of the full execution/cancellation path, isolated runtime probes executed on **CPython 3.11.15 (the project minimum) and 3.12.3 (the only CI version)** against a throwaway copy of the repository, official-documentation research, and a self-directed disproof pass (§17). No claim rests on a comment, issue text, handoff, or historical ADR alone.
**Companion artifacts:** `docs/architecture/decisions/ADR_KERNEL_09_CANCELLATION_CONTRACT.md` (PROPOSED), one new row in `docs/architecture/decisions/ADR_INDEX.md`.
**Not authorized by this study:** implementation of #105 or any companion change, B2d, resume changes, voice changes, issue/PR/branch operations, FZ-01/FZ-02 status changes.

Evidence classes used throughout: **VERIFIED** (live source, reproducible probe, test, or authoritative spec), **INFERRED** (follows from verified source, not exercised end-to-end), **PROPOSED** (recommended future design, not implemented), **ACCEPTED** (owner-accepted design statement — *this study assigns none*), **DECIDED** (an owner decision on a sequencing/policy question, recorded with its date and source; it does not make any design statement ACCEPTED), **UNVERIFIED** (evidence does not establish the claim), **DISPROVEN** (direct evidence contradicts it).

---

## 1. Executive conclusion

1. **#105 is real and worse than its title says.** On `ed3d141`, cancelling the task that runs `WorkflowRuntime.execute()` does not stop the workflow: `Worker.execute()` turns `CancelledError` into an ordinary failed result (`core/workers/base.py:293-300`), the node is retried, and — in the reproduction (probe P1) — the retried node succeeds, so **`execute()` returns `WorkflowResult(success=True)` for a workflow whose task was cancelled** (`task.cancelled()` is `False`, node executed twice, elapsed ≈2.4 s). With an `error_branch` configured, the branch is entered as well (probe P10: recovery worker executed, `success=True`). Reproduced identically on 3.11.15 and 3.12.3.
2. **The defect is not isolated.** The same cancellation, when it *does* propagate (it can today at three await points, and will everywhere after #105 is fixed), meets four unprepared layers: `ExecutionRuntime.invoke()` skips WorkingMemory cleanup and its terminal event (P4, P5); `WorkflowRuntime._run()` has no `finally` and leaks the graph watchdog task (P6, P6b); `GraphExecutionWatchdog.stop()` swallows the caller's cancellation (P7); and the execution graph and event subscribers are left RUNNING/waiting forever because **`execution.cancelled` — the terminal event the API recognises — is emitted by no code at all** (repo-wide grep; subscriber probe C3). A narrow "re-raise `CancelledError`" patch to `Worker.execute()` alone would convert a *wrong-answer* defect into *leaked-task, stuck-graph, hung-subscriber* defects. #105 therefore cannot be safely implemented as a one-line change.
3. **The recommended contract is C+ with one refinement:** native `asyncio.CancelledError` propagates after bounded cleanup (Option A semantics for #105); OCBrain-owned cooperative cancellation (token) is a *distinct, non-failure control outcome* decided in a follow-up (Option B semantics, carried on existing types), and the two share one finalization routine. The "three-dimension" model (initiation/authority · delivery mechanism · observed outcome/effect certainty) survives challenge, with two corrections (§9.4): *cause must be a typed value, not a free string* (the repository already has two incompatible encodings — N6), and *DAG edges/graph nesting are not ownership* (§10).
4. **Smallest safe #105 boundary (PROPOSED):** two independently mergeable prerequisites (`ExecutionRuntime.invoke()` cleanup in `finally`; `GraphExecutionWatchdog.stop()` caller-cancellation preservation) followed by one cohesive behaviour change (`Worker.execute()` propagation + lifecycle; `WorkflowRuntime._run()` `try/finally` that stops the watchdog and finalizes graph + terminal event). Everything else — B2d, token-outcome semantics, client-disconnect policy, shutdown policy, resume authorization, parent/sibling policy, the voice thread defect, provider-side termination — stays out (§11, §12).
5. **Two adjacent defects found that are independent of #105 and should not be folded into it:** the voice hotkey callback calls `asyncio.create_task()` from `keyboard`'s listener thread (`main.py:442-443`; raises `RuntimeError: no running event loop` — P13); and `CancellationToken.wait()` cannot be woken correctly from a foreign thread despite the docstring claim "Thread-safe via asyncio.Event" (`core/runtime/cancellation.py:13`; P12).
6. **What this study does not establish:** provider-side termination (UNVERIFIED), live voice hardware path (UNVERIFIED end-to-end), production reachability of an independently-cancelled Planner child (UNVERIFIED, §17), and anything about FZ-01. Cancellation is **not** declared solved; the contract is not declared "fully correct".
7. **Revision 2 (owner review).** Three corrections were accepted and applied: (A) the terminal event is emitted by the workflow *finalizer* after the node/worker stack has unwound — not after the whole task has terminated; (B) subscriber termination must not depend on `EventStream` broadcast (reproduced: probe C5); (C) a graph terminal-state transition policy is required (§9.5). D-03, D-05, D-10 and D-12 were amended; four acceptance requirements and one coordination decision (D-14, overlap with PR #81) were added (§21).

---

## 2. Baseline (live state at study start)

| Item | Value | Evidence |
|---|---|---|
| Remote `main` | `ed3d141e4bbfd0231afb1104d0a7479419f9bbf1` — unchanged from the audited snapshot; **no intervening commits to reconcile** | `git ls-remote` at study start and again before writing |
| Reconciliation (rev 2) | `main` moved to `2491ae4` (PR #106, CTX-AUTH-002 closure; 15 files, none on the cancellation path — §21.1). PR #108 (draft, docs-only) and several in-flight branches that **overlap future implementation work** (PR #81 `core/runtime/watchdog.py` + `core/workflow/runtime.py`; PR #94 `interface/api.py` + `main.py`; `ci.yml` branches) are recorded in §21.1. | `git diff ed3d141 2491ae4`; blob comparison; all-branch overlap scan |
| PR #104 | MERGED (merge commit `ed3d141`), no reviewers, no assignees, no labels; title "close the provider stream and leak no tasks when the router's caller task is cancelled" | PR page |
| Issue #105 | OPEN, unassigned, no labels, no linked branch; body states the Worker/workflow retry defect and asks for an owner decision on the contract | issue page |
| B2d follow-up branch | `follow-up/fz02-b2d-latent-token-cancellation-oct2026` head `b44bddf5485cfd8e0cca9bc5a3b4d30281d44c0c`; merge-base with `main` = `4891756` (PR #104's signed-off head); 2 branch-only commits; diff touches `core/capabilities/adapter_runtime.py`, `core/model_router.py`, `core/runtime/watchdog_decision.py`, `tests/test_b2c_cancellation.py`, `docs/handoffs/*`. **Inspected read-only; not treated as accepted evidence.** | `git diff main...follow-up/…` |
| Other related work | Branch-name scan of all 107 remote branches: only the FZ-02 series (`fix/fz02-provider-failure-oct2026`, `fix/fz02-b2b-…`, `fix/fz02-b2c-…`, `wip/fz02-b2c-…`, the B2d branch). No branch touches `core/workers/base.py`, `core/workflow/runtime.py` or `core/runtime/watchdog.py` for cancellation. | `git branch -r`, `git diff --stat` |
| Working tree at study start | Fresh clone, clean; study branch `study/cancellation-contract-final-gap-oct2026` created from `ed3d141` (no pre-existing local or remote branch of that name). | `git status`, `git branch -a` |
| FZ-01 | OPEN (`KNOWN_ISSUES.md:122`). Not touched. | file |
| CI matrix | `ci.yml` pins **Python 3.12 only** (lines 30, 72); `requires-python = ">=3.11"` (`pyproject.toml:11`); the only 3.11 use is one release job (`release.yml:171`). **The declared minimum is not exercised by CI.** | files |
| Installed dependency versions (probe env; requirements are `>=`) | fastapi 0.162.0, starlette 1.10.0, uvicorn 0.54.0, anyio 4.16.0, httpx 0.28.1, keyboard 0.13.5, pytest 9.2.0, pytest-asyncio 1.4.1 | `importlib.metadata` |
| `KNOWN_ISSUES.md` DEBT-012 | Full-suite runs rewrite tracked `config/*.toml`. **All probes and tests ran in a throwaway copy (`/tmp/probe/repo`); the study checkout was verified clean (`git status --short` empty) after probing.** | file; `git status` |

Existing relevant tests (baseline, throwaway copy): `tests/test_b2c_cancellation.py`, `test_execution_watchdog.py`, `test_workflow_runtime.py`, `test_execution_inspection.py` — **61 passed on 3.11.15 and 61 passed on 3.12.3.** A repository-wide grep finds **no test that pins** `worker.cancelled`, `WorkerState.CANCELLED`, `"Worker cancelled"`, `"Workflow cancelled"`, `"Cancelled during retry"`, or `execution.cancelled` (the only mention is a historical K2.2 report row). The paths this study concerns are therefore currently unpinned, not pinned-to-the-wrong-behaviour.

---

## 3. End-to-end execution and cancellation call graph (as built at `ed3d141`)

```
HTTP  POST /query (stream=false)      interface/api.py:161-209
      └─ Orchestrator.handle()        core/orchestrator.py:188   ── except Exception only (769, 909); no token passed to workflow (525, 715)
HTTP  POST /query (stream=true)       interface/api.py:171-184 → _stream_response() :290
      ├─ 1 module: model_router.stream_route()  (bypasses workflow)  :337   ── except Exception only (357); CancelledError/GeneratorExit uncaught
      └─ n modules: Orchestrator.handle()       :380
Orchestrator.handle()
 └─ WorkflowRuntime.execute()         core/workflow/runtime.py:294   (documented "never raises")
     └─ _run()                        :452   creates CancellationToken (483) unless caller supplied one; NO production caller supplies one
         ├─ execution_registry.create / graph root RUNNING                        (485-516)
         ├─ GraphExecutionWatchdog.start()                        (517)   ── child asyncio.Task
         ├─ emit workflow.started                                 (533)   ── await; unprotected
         ├─ _execute_from()                                       (552 → 683)
         │    ├─ token pre-check → WorkerResult(False,"Workflow cancelled")      (723-724)
         │    ├─ state.status = RUNNING                                           (757)
         │    ├─ _execute_node_with_retry()                                       (769 → 840-912)
         │    │    ├─ token pre-check each attempt → "Cancelled during retry"     (865-866)
         │    │    ├─ ExecutionRuntime.invoke()                                   (888)
         │    │    │    └─ Worker.execute()   core/workers/base.py:~200-330
         │    │    │         ├─ governance (sync, :246) → reject returns result, emits event
         │    │    │         ├─ state=RUNNING; emit worker.started  (:273-275)   ── OUTSIDE try
         │    │    │         ├─ try: _run(); state=COMPLETED (:286); emit worker.completed (:287)
         │    │    │         ├─ except CancelledError (:293): state=CANCELLED; failures+=1; emit worker.cancelled; RETURN failed WorkerResult   ← #105
         │    │    │         └─ except Exception (:306)
         │    │    │    ├─ except Exception (invoke :196)  — CancelledError is BaseException, passes through
         │    │    │    └─ runtime event + WorkingMemory.clear()  (:211, :227) — skipped when CancelledError escapes
         │    │    └─ failed result → backoff asyncio.sleep(delay) (:910, ignores token) → next attempt
         │    ├─ success → record_completion (786); failure → record_failure, checkpoint, error_branch (800-807)
         │    └─ successors → _execute_from()
         ├─ watchdog.stop()                                        (523, 568, 649)   ── three explicit calls, no finally
         └─ record_status(root) + emit execution.completed|failed  (633-648)         ── never execution.cancelled

GraphExecutionWatchdog._run()         core/runtime/watchdog.py     polls every ~1 s
 └─ inspect(): on stall/deadline → for each ACTIVE node: ProgressMonitor.record_failure()  (192)  → node FAILED + execution.node.failed
                                  → then token.cancel(f"execution {reason}")                (180, 196)

PlannerWorker._run()                  core/workers/planner.py:131-260
 └─ asyncio.gather(*dispatches, return_exceptions=True)  (:164) → `isinstance(res, Exception)` (:174)
     └─ _dispatch_module() :316-349 → CapabilityRequest(payload={module_name, subtask, context=ContextMemory, scope}) (:321-329)   ── no token field
         └─ AdapterRuntime.invoke()  core/capabilities/adapter_runtime.py:60-134
             ├─ except Exception (:93) → mark_failure + next adapter     (CancelledError passes through)
             └─ result.success False (:117-124) → mark_failure + next adapter   (a returned "cancelled" would be penalised)
                 └─ ModelRouterAdapter.execute() → ModelRouter.route() → _call_monitored_streaming()
                      token = _resolve_cancellation_token(context)  (:420, helper :125-133)  → context is ContextMemory → fresh local token
                      non-stall token cancel → FailureType.HARD_DEADLINE (:499-503); FailureType.CANCELLED is never produced
                      route() records training pair / query_count / promotion unconditionally (:195-197)
```

The production composition root registers more than one `LLM_COMPLETION` adapter (`main.py:282-287`: `ModelRouterAdapter`, then `OllamaAdapter`, then `OpenAICompatAdapter`), so `AdapterRuntime`'s fallback is live and a "failure" outcome from the first adapter starts another full generation on the next.

---

## 4. Probe register (how the evidence was produced)

All probes live **outside** the repository (delivered as study attachments, not committed). They run against a throwaway copy of `ed3d141`, use private temporary EventStream databases, and instrument await boundaries by delaying `EventStream.append()` for chosen event types (delay happens *before* persistence, so a cancel inside it means the event was not persisted). Probe results are on **CPython 3.11.15** unless stated; P1, P3, P7 and the reason probe were re-run on **3.12.3** and gave identical results.

| ID | Probe | Source file |
|---|---|---|
| P1 | cancel the task running `WorkflowRuntime.execute()` mid-node; node `max_retries=1` | `probes_a.py` |
| P2 | cancel while `worker.started` is being emitted | `probes_a.py` |
| P3 | cancel while `worker.completed` is being emitted, after `_run()` returned success | `probes_a.py` |
| P4 | `ExecutionRuntime.invoke()` cleanup when `CancelledError` escapes vs. when it is swallowed | `probes_a.py` |
| P5 | second cancel while `worker.cancelled` is being emitted | `probes_a.py` |
| P6 | cancel during `workflow.started` emission; cancel during the *per-invocation* runtime `execution.completed` emission; watchdog task and graph state afterwards | `probes_a.py` |
| P6b | cancel during the *WorkflowRuntime-level* terminal `execution.completed` emission (delay keyed by event type **and** source) | `probes_b.py` |
| P7 | `GraphExecutionWatchdog.stop()` while the *caller* is cancelled | `probes_a.py` |
| P8 | graph watchdog hard deadline + a worker that ignores the token and later succeeds | `probes_a.py` |
| P9 | token cancelled mid-node; cooperative worker returns an ordinary failure; retry policy + `error_branch` configured | `probes_a.py` |
| P10 | native cancel with `error_branch` configured, `max_retries=0` | `probes_b.py` |
| P11 / P11b | real `PlannerWorker._run()` with an independently cancelled `gather()` child, and with a cancelled parent; isolated `gather` semantics | `probes_b.py` |
| P12 | `CancellationToken.cancel()` from a foreign thread while the loop is idle (normal and asyncio-debug) | `probes_b.py` |
| P13 | the exact `main.py:442-443` voice callback body invoked from a non-loop thread | `probes_b.py` |
| P15 | `EventStream.append()` cancelled while the executor thread is persisting | `probes_b.py` |
| C1–C4b | real in-process Uvicorn 0.54.0 serving the real `interface.api.app` (with its `BaseHTTPMiddleware` CSRF gate): non-stream disconnect, SSE disconnect, `/executions/{id}/events` terminal gap, graceful shutdown with and without `timeout_graceful_shutdown` | `probes_c.py` |
| PR | graph-watchdog token reason string vs `CancelReason` values | `probe_reason.py` |

Limits that apply to every probe: single run per probe (not statistically repeated); fakes stand in for providers and the orchestrator; no physical provider, microphone or keyboard hardware was involved; delays are injected before persistence, so "persisted?" questions were answered separately (P15).

---

## 5. Evidence register — H1 to H20

Dispositions: VERIFIED / INFERRED / UNVERIFIED / DISPROVEN / PROPOSED. "Today" = reachable on `ed3d141`; "Latent" = becomes primary only after a related change (typically #105).

| ID | Disposition | Finding, evidence, scope |
|---|---|---|
| **H1** `Worker.execute()` converts native cancellation to ordinary failure and enables workflow retry | **VERIFIED** (Today) | `base.py:293-300`: `except asyncio.CancelledError` sets `CANCELLED`, increments `_total_failures` (`:295`), emits `worker.cancelled` (`:296`) and **returns** `WorkerResult(success=False, error="Worker cancelled")`. P1: task cancelled at 0.3 s → `execute()` **returned** `WorkflowResult(success=True)`; node ran twice; `task.cancelled()` False, `task.cancelling()==1`; elapsed ≈2.4 s; events: `worker.started, worker.cancelled, execution.completed, worker.started, worker.completed, …`. P10: with `error_branch`, recovery executed and workflow `success=True`. Identical on 3.12.3. Impact: a cancelled request completes, can retry side effects, and can report success. |
| **H2** Cancel during `worker.started` leaves lifecycle inconsistent | **VERIFIED** (Today) | The emission (`base.py:275`) is outside the `try` that begins `:280`; `_emit_event` swallows only `Exception`. P2: `CancelledError` escapes; **worker state stays `running`**, `total_failures` 0, no `worker.cancelled`. The worker instance is ephemeral (ADR-003) so the stale RUNNING state is not observed by later invocations, but the lifecycle record is wrong and — more importantly — the exception escapes `Worker.execute()` into `ExecutionRuntime.invoke()` which is not prepared for it (H4). |
| **H3** Cancel during post-`_run()` completion emission misreports completed work | **VERIFIED** (Today) | `base.py:286-287`: `state=COMPLETED` then `await _emit_event("worker.completed")` inside the `try`. P3: `_run()` returned `success=True`; cancel during the emission → handler returns `success=False, "Worker cancelled"`, state `cancelled`, `total_failures` 1; **the real result is discarded** and `worker.completed` is never emitted. Work completion and event-delivery completion are conflated. |
| **H4** `ExecutionRuntime.invoke()` skips WorkingMemory cleanup and terminal event on propagated cancellation | **VERIFIED** (Today at the escape points; **Latent-primary after #105**) | `execution_runtime.py:196` is `except Exception`; runtime event (`:211`) and `working_memory.clear()` (`:227`) are after it with no `finally`. P4: escaping cancel → WorkingMemory still holds the scratch key, no runtime event; control case (cancel inside `_run()`, currently swallowed) clears memory and emits. P5: second cancel during the `worker.cancelled` emission escapes with memory uncleared. The documented "(never raises)" lifecycle (`KERNEL_ARCHITECTURE_v1.0.md` §7.1) is incompatible with Python task cancellation. |
| **H5** `WorkflowRuntime._run()` lacks a `finally`-protected watchdog lifetime | **VERIFIED** (Today at escape points; Latent-primary after #105) | `watchdog.start()` `runtime.py:517`; `watchdog.stop()` only at `:523`, `:568`, `:649`; no `try/finally`, no `except CancelledError`. P6: cancel during `workflow.started` emission → **1 leaked `GraphExecutionWatchdog._run` task**, graph root `running`, no terminal event. P6 (second case, runtime-level `execution.completed`): same. P6b: cancel during the workflow-level terminal emission → leaked watchdog, graph root already `completed`, terminal event never persisted. Every `await` between `:517` and `:649` (`:533`, the node loop, `:633`, `:639`) is an unprotected leak point. |
| **H6** `GraphExecutionWatchdog.stop()` can swallow cancellation of its caller | **VERIFIED** (Today) | `watchdog.py:132-140`: `self._task.cancel(); try: await self._task; except asyncio.CancelledError: pass`. P7 (child with 0.5 s cleanup; caller cancelled at 0.1 s): `stop()` **returned normally**, caller task `cancelled()==False`, `cancelling()==1`. 3.11 and 3.12. The `except` cannot distinguish "my child ended cancelled" from "I was cancelled". `self._task = None` (`:140`) is reached, so the reference is cleared on that path; the exceptional path (child raising a non-cancel exception) leaves `_task` set (INFERRED from code). A second cancellation interrupting `stop()` is the same defect. |
| **H7** Graph watchdog records active nodes FAILED before termination is known | **VERIFIED** (Today) | `watchdog.py:192` `record_failure(...)` precedes `:196` `token.cancel(...)` and is issued for every ACTIVE node **including the execution root**. P8 (graph hard deadline 0.4 s, token-ignoring worker finishing at ~2.6 s): events `execution.node.failed` (root **and** node) → later `execution.node.completed`; final node status `completed` with stale `failure_type="hard_deadline"`; **workflow returned `success=True`**. `ExecutionGraph.update()` (`execution_graph.py:87-107`) has no terminal-state guard, so FAILED → COMPLETED is accepted. Request, delivery, acknowledgement and termination are not distinguished; the public event says `failed` for a *request*. |
| **H8** Token cancellation and native task cancellation are conflated / incompletely propagated | **VERIFIED** | Two independent mechanisms with different outcomes: native → ordinary failure + retry (P1); token → pre-attempt/pre-node check returns `WorkerResult(False,"Workflow cancelled"/"Cancelled during retry")` which is then recorded as an **ordinary FAILED node** and an `execution.failed` terminal event (P9). **No production code passes a token into `WorkflowRuntime.execute()`** (grep: `cancellation_token=` appears only at `runtime.py:301,327,338,420,462,885` and watchdog/execution_watchdog/model_router internals; `Orchestrator` calls at `orchestrator.py:525,715` omit it), so **in production the only party that can set the workflow token is `GraphExecutionWatchdog`** (stall/deadline). There is **no `WorkflowRuntime.cancel()`** (grep of `core/workflow`, `core/runtime`: none). |
| **H9** Token cancellation at node/retry boundaries can still flow through failure, retry, or error-branch logic | **PARTIALLY VERIFIED / PARTIALLY DISPROVEN** | *Token path:* **DISPROVEN** that an error branch runs — `_execute_from` re-checks the same token at entry (`runtime.py:723`), so P9's `Recovery` worker executed 0 times. **VERIFIED**: the cancelled node is recorded **FAILED** with `execution.node.failed`; the retry **backoff `asyncio.sleep` (`:910`) ignores the token** (P9: 0.3 s cancel + 1.5 s backoff → returned after 1.84 s); `"Cancelled during retry"` is reported even when no retry occurred; the terminal event is `execution.failed`, never a cancellation (N2). *Native path:* **VERIFIED** that both retry and the error branch run (P1, P10). |
| **H10** `PlannerWorker` mishandles an independently cancelled `gather()` child | **VERIFIED as a contract hole; production reachability UNVERIFIED** | `planner.py:164` `gather(..., return_exceptions=True)`; `:174` `isinstance(res, Exception)`. P11b: a cancelled child yields a `CancelledError` **instance** in the results with `isinstance(.., Exception) == False` (it is a `BaseException`). It does not "evade" the merger: `merger.merge` normalises unknown types to `RouteResult(answer=str(r), source="error")` (empty text) with a `[Merger] Received unexpected result type` warning. P11: **`PlannerWorker._run` returned `success=True`, `output="answer-from-beta\n\n"`** — the cancelled module silently vanished, with no `[Error in …]` annotation. All-children-cancelled would return `success=True` with empty output (INFERRED from `merger.py` normalisation). P11 parent-cancel: `CancelledError` propagated and **both children stopped before completing** (gather cancels submitted awaitables — Python docs, §14). No production component was found that cancels a single `_dispatch_module` task independently; reachability needs an inner awaited task being cancelled without the parent (§17). |
| **H11** Adapter-level cancellation returned as a failed result triggers fallback/health penalty | **VERIFIED (mechanism); reachability UNVERIFIED today** | `adapter_runtime.py:117-124`: any `success=False` → `_mark_failure` + `adapter.failed` + next adapter. A result whose `failure_type` is `cancelled` would be treated like any failure. Native `CancelledError` is **not** treated this way (`:93` `except Exception`) — pinned by PR #104's tests. Today no adapter returns a cancelled outcome (see H12), so the penalty path for *cancellation* is latent; the penalty/fallback path for **stall/deadline (`HARD_DEADLINE`)** is live and is a deliberately pinned behaviour (B2a/B2b). |
| **H12** Cancelled/incomplete outputs may enter ModelRouter training, query counts, or promotion | **VERIFIED (source)** | `model_router.py:195-197`: after `_call_monitored_streaming` returns, `_record_training_pair`, `_increment_query_count`, `_maybe_promote` run **unconditionally**, so stalled, hard-deadline, provider-failure and (once reachable) token-cancelled generations with partial text are recorded. Native task cancellation does **not** reach these lines (the caller's `CancelledError` is re-raised at `:466-470`/`:483-485`). `stream_route()` records only after the generator is fully consumed (`:276-286`), so an aborted SSE stream records nothing — but a stream that yielded `ProviderStreamError` text records it (existing tracked item). Not exercised by a probe; the guard exists only on the B2d branch. |
| **H13** `/executions/{id}/events` can stay open because no recognised terminal event is emitted on cancellation | **VERIFIED** | The predicate (`api.py:239-241`) recognises `execution.completed|failed|cancelled`; **`execution.cancelled` is emitted by no code** (repo-wide grep of `*.py`/`*.md`: one hit, the predicate itself). C3: with a workflow whose `CancelledError` propagates, the subscriber received only `execution.node.status` and was **still waiting 3 s later**; manually emitting `execution.cancelled` ended the stream (the predicate works; the emission is what is missing). C2 (SSE `/query`, single module): client disconnect → provider stream got `CancelledError`, but the graph node `Generate response` stayed `running` and the root `pending`, with **no terminal event** (`except Exception` at `api.py:357` does not catch `CancelledError`/`GeneratorExit`). Multi-module SSE: `handle()` exceptions record node failure but emit **no** `execution.failed` event (`api.py:381-388`) (INFERRED reachability; source verified). *Today:* reachable via the escape points and via SSE disconnect. *Latent-primary after #105.* |
| **H14** HTTP disconnect ≠ logical cancellation | **VERIFIED (per path)** | Real Uvicorn 0.54.0 + Starlette 1.10.0, real `CSRFHeaderMiddleware` (`BaseHTTPMiddleware`). **C1** non-stream `POST /query`: client closed at 0.3 s; orchestrator `handle()` **ran to completion** — the logical operation continued. **C2** streaming `POST /query` (single module): disconnect cancelled the response generator and therefore the provider stream — here transport and operation are *coupled by construction* (the work is inside the response generator). Multi-module SSE: same mechanism, INFERRED, not probed. `/executions/{id}/events` disconnect only detaches the subscriber. So disconnect semantics are **path-dependent today**, and that inconsistency is itself the decision to make (§18, D-06). |
| **H15** Shutdown and background-task ownership incomplete or ambiguous | **VERIFIED (partial)** | `Orchestrator.close()` (`orchestrator.py:162-169`) tracks only background *services* (`_background_tasks`, currently the health-monitor start task) — **not** request tasks. Request tasks are supervised by Uvicorn: C4 with `main.py`'s config (no `timeout_graceful_shutdown`): `Server.should_exit` waited **4.67 s** for the in-flight request, which completed normally; C4b with `timeout_graceful_shutdown=1`: Uvicorn cancelled the request task at ~1.16 s (`handle:CANCELLED`). Source (`uvicorn/server.py:286-355`): shutdown waits on `server_state.tasks` indefinitely by default; a **second SIGINT** sets `force_exit`, a second SIGTERM does not. So a long `/query` can hold SIGTERM shutdown unboundedly (no timeout set in `main.py:456-461`), and Uvicorn's `capture_signals` replaces `main.py`'s `_handle_sigterm` only while `serve()` runs. Not a defect of any class "failing to own tasks that Uvicorn supervises". Unsupervised fire-and-forget tasks: `interface/api.py:371,607`, `core/event_bus.py:97`, `main.py:443` (no retained reference; Python docs warn the loop keeps only weak references — N11). `learning/scheduler.py:128` has its own supervisor (not audited here — UNVERIFIED). |
| **H16** `CancellationToken` claims thread safety but uses `asyncio.Event` | **VERIFIED** | `cancellation.py:13` "Thread-safe via asyncio.Event". Python 3.11 docs: asyncio primitives are not thread-safe; `Event` "Not thread-safe". P12 (loop idle, foreign thread calls `cancel()`): the flag is set immediately but `wait()` woke only when its own 3.0 s timeout fired (**0.3 s intended → 3.0 s**); under `asyncio` debug mode the thread gets `RuntimeError: Non-thread-safe operation invoked on an event loop other than the current one` and the waiter **never wakes**. The read side (`is_cancelled`) is a plain flag read; `cancel()` also has an unsynchronised check-then-set. |
| **H17** Voice callback schedules `asyncio.create_task()` from a separate thread | **VERIFIED (mechanism); live hardware path UNVERIFIED** | `main.py:442-443`: `def _handle_voice(q): asyncio.create_task(orchestrator.handle(q))`. `interface/voice.py:86-92,99-105`: `keyboard.add_hotkey(..)` inside a daemon thread; callback calls `on_query(text)`. The installed `keyboard==0.13.5` docstring (`__init__.py:620`) and upstream README: "the callback is executed in a separate thread, asynchronously". P13 (exact callback body from a non-loop thread): **`RuntimeError: no running event loop`** plus "coroutine … was never awaited"; the control call on the loop thread succeeds. Classification: **separate cross-thread scheduling/lifecycle defect, only when `global.voice_enabled` is true; not part of #105.** Also the created task would be unreferenced (N11) and its answer discarded. |
| **H18** Resume may restart intentionally cancelled work | **VERIFIED (mechanism); no production caller VERIFIED** | `runtime.py:405-407` resets `RUNNING` and `CANCELLED` nodes to `PENDING`. `NodeStatus.CANCELLED` is **never assigned** anywhere in production (grep) — the docstring at `:354` calls it "not-currently-reachable". Token-cancelled nodes are recorded **FAILED** (P9) and FAILED nodes are cached and **not** re-run on resume; a node interrupted by native cancellation has no checkpoint of its own (checkpoints are saved at node boundaries), so on resume it is `PENDING` and **re-executes** — i.e. today resume cannot tell crash interruption from intentional cancellation. `resume()` has **no caller anywhere in the repository outside tests/docs** (repo-wide grep of `.py`, including `learning/`, `scripts/`, `install/`, and dynamic `getattr`/string forms). Future rule required before resume becomes reachable (D-08). |
| **H19** Cancellation after a side effect may leave committed or unknown effects | **VERIFIED (structure) / INFERRED (specific effects)** | Cancellation is delivered at any `await`. The Planner performs persistence after merge (`planner.py:197-249`: `UnifiedMemory.write`, `ContextMemory.save`); the router records training/query-count (H12); `EventStream.append` can be **persisted but not broadcast** when the awaiting task is cancelled — P15: awaiter got `CancelledError`, **row persisted (1), subscribers notified `[]`** (the write happens in an executor thread that cannot be cancelled; `event_stream.py:228,409-448`). ADR-005 (no automatic rollback) applies: completed effects stay represented; unknown effects need reconciliation under the capability contract. No effect ledger exists; none is proposed. |
| **H20** Documentation accurately describes the implementation | **DISPROVEN** | See §15 (discrepancy register D1–D10). |

## 6. Newly identified findings (not in the H-table)

| ID | Disposition | Finding |
|---|---|---|
| **N1** | VERIFIED | **`execution.completed` is an overloaded event name**: emitted per worker invocation by `ExecutionRuntime` (`execution_runtime.py:211`, payload carries `success`, can be `false`), at execution level by `WorkflowRuntime` (`runtime.py:640`), and by `StreamingAPI` (`api.py:352,392`). The registry fan-out keys on `payload["execution_id"]` (`execution_graph.py:167-170`) so the runtime-level events do not reach subscribers (INFERRED from payload shape), but any consumer filtering on type alone cannot tell lifecycle phase from outcome. P1/P9 show `execution.completed{success:false}` events. |
| **N2** | VERIFIED | Token cancellation is reported as **failure**: node `FAILED`, `execution.node.failed`, terminal `execution.failed`, `WorkflowResult.error="Workflow cancelled"` (P9). Cause (stall vs deadline vs external) is lost between watchdog and result. |
| **N3** | VERIFIED | Retry backoff sleep is not token-aware (`runtime.py:910`): cancellation latency = remaining backoff (up to `max_backoff_seconds`, default 60 s). |
| **N4** | INFERRED | `state.attempts = attempt + 1` (`:862`) is assigned **before** the token check (`:865`), so a node that ran once can be recorded with `attempts=2`. |
| **N5** | VERIFIED | The watchdog fails the **root execution node** as well as work nodes (P8), and a later completion leaves a stale `failure_type` on a `completed` node. |
| **N6** | VERIFIED | **Two incompatible cancel-cause encodings.** `ExecutionWatchdog` (router-facing) cancels with `CancelReason.<X>.value` (`"stall"`, `"hard_deadline"`; `execution_watchdog.py:133`). `GraphExecutionWatchdog` cancels with `f"execution {reason}"` (`watchdog.py:180,196`; probe PR: `"execution hard_deadline" != "hard_deadline"`). The router classifies by string equality (`model_router.py:501`). The B2d branch's `ADAPTER_LOCAL_CANCEL_REASONS`/`is_caller_cancellation()` treats *every other string* — including the graph watchdog's stall/deadline reasons — as **caller cancellation**, i.e. it would relabel a supervisor timeout as `CANCELLED`. That conflates cause with outcome, which the mission and §9 forbid. |
| **N7** | VERIFIED | `PlannerWorker` dropping a cancelled module silently with `success=True` (see H10). |
| **N8** | INFERRED | On the K4.2 path `Orchestrator.handle()` reads `wf_result.output or ""` and not `success` (`orchestrator.py:532`; FZ-01, OPEN). A cancelled or failed workflow can therefore be rendered to the caller as an **empty answer**. FZ-01 is not touched here. |
| **N9** | VERIFIED | `WorkflowRuntime.execute()` is documented as "never raises" (`runtime.py:254,317,479`; `orchestrator.py:662`). P6/P6b show it raising `CancelledError` today at unprotected awaits. |
| **N10** | VERIFIED | `EventStream.append()` is persist-then-broadcast (`event_stream.py:409-448`) and is **not an atomic acknowledgement under cancellation** (P15). Whatever terminal-event protocol is chosen must tolerate "persisted, not broadcast". |
| **N11** | VERIFIED (sites) / INFERRED (consequence) | Fire-and-forget `create_task` without a retained reference: `interface/api.py:371`, `:607`, `core/event_bus.py:97`, `main.py:443`. Python docs: the loop holds only weak references to tasks. |
| **N12** | VERIFIED | Graceful shutdown with `main.py`'s Uvicorn config waits on in-flight requests without bound (C4); a second SIGTERM does not force exit (uvicorn `handle_exit`). |
| **N13** | VERIFIED | `AbstractCognitiveWorker.cancel()`/`is_cancelled` (`base.py:362`) has **no production caller** (grep of every `.cancel(` site); `core/workers/curator.py:346,399,468` polls `self.is_cancelled` (the instance flag nobody sets) rather than `context.cancellation_token`. Cooperative cancellation inside that worker is dead code with respect to workflow cancellation. No cancellation counter exists in worker or runtime `stats()` (`total_failures` absorbs cancellations — `base.py:295`). |
| **N14** | VERIFIED | `ADR_INDEX.md` is not synchronised with `ADR_KERNEL_08_REJECT_CONTENT_CORROBORATION_AUTHORITY.md`, which exists on `main` but has no index row. This study adds only its own row (§16 / ADR); it does not repair the index. *Rev 2: true at `ed3d141`; PR #106 added the KERNEL-08 row, so at `2491ae4` the row exists and `ADR-KERNEL-09` is still the next free identifier.* |
| **N15** | VERIFIED | `KERNEL_ARCHITECTURE_v1.0.md` §7.4 shows `CancellationToken.cancel(self)` with no `reason` argument (live: `cancel(reason="cancelled")`), and the event table (`:722`) says `worker.cancelled` fires when the **CancellationToken is triggered**, whereas the code emits it only on native `CancelledError`. |
| **N16** | VERIFIED | CI exercises Python 3.12 only; the declared minimum 3.11 is not covered by CI (see §2). Probe results here include 3.11.15 explicitly because of this. |
| **N17** | VERIFIED (source) / INFERRED (race) | CPython 3.11's `asyncio.wait_for` returns the inner result instead of re-raising when the *outer* task is cancelled in the same loop iteration in which the inner future completes (`asyncio/tasks.py`, `except CancelledError: if fut.done(): return fut.result()`; reimplemented on `asyncio.timeout` in 3.12). The kernel uses `wait_for` at `cancellation.py:80` (`CancellationToken.wait`), `execution_watchdog.py:156`, `limits.py:56,73`. Cleanup code in cancellation-sensitive paths must demonstrate that external cancellation stays observable (§21.3); `asyncio.timeout()` is one available primitive, `wait_for` is a known hazard there, and no blanket replacement is proposed. The race was not reproduced (timing-dependent); only the source behaviour is verified. |
| **N18** | VERIFIED | **Two terminal-event families and one consumer that reads the second.** `WorkflowRuntime._run()` ends with `record_status(root)` → `execution.completed|failed` (`runtime.py:633-648`) → `watchdog.stop()` (`:649`) → `workflow.completed{success}` (`:673`), emitted for failures too. `ExecutionRegistry`/SSE consume the `execution.*` family; `EvaluatorWorker` consumes `workflow.completed.success` and the `worker.completed`/`worker.failed` counts (`evaluator.py:171-181,251-256`) to write an L1 evaluation record. After a propagated cancellation neither family is emitted today. The Evaluator treats `worker.completed` as success even when the payload says `success:false` (`base.py:287-290`), so its `tool_success_rate` is already overstated for returned failures; it also ignores `worker.cancelled`. Any terminal-event design must say what the Evaluator should see for a cancelled workflow (D-10). Note also the order at `:633-673`: the watchdog is stopped *after* the `execution.*` emission, so a cancel during that emission leaks it (P6b). |

## 7. Classification summary

**Confirmed defects (reproduced):** H1, H2, H3, H4 (at escape points), H5, H6, H7, H9 (token-path retry/backoff/failure labelling; native-path retry and error branch), H10 (contract hole), H13, H16, H17, N2, N3, N5, N6 (encoding mismatch), N7, N9, N10 (as a constraint), N13.
**Architectural limitations / unspecified contracts (not defects by themselves):** N18 (two terminal-event families; Evaluator semantics), H14 (path-dependent disconnect semantics), H15 (unbounded graceful shutdown; subscriber/operation lifetimes unspecified), H18 (resume vs intentional cancel), H19 (effect certainty), N1 (event naming), N8 (FZ-01).
**Unverified:** provider-side termination; live voice hardware path; production reachability of independent Planner-child cancellation (H10) and of a returned `cancelled` adapter outcome (H11); scheduler supervision; multi-module SSE disconnect (mechanism inferred); N4.
**Disproven:** that a token-cancelled workflow enters its error branch (H9, token path); that `FailureType.CANCELLED` is produced anywhere today (it is not — H12/H11).

---

## 8. Alternatives A, B, C and the C+ recommendation

### 8.1 Option A — re-raise native `asyncio.CancelledError`

*Python correctness.* Verified against the 3.11 docs/AnyIO guidance (§14): cancellation must propagate after cleanup; swallowing it breaks `asyncio.timeout`, `TaskGroup`, `wait_for` and caller `cancel()` accounting. P1/P7 are direct demonstrations of what swallowing does here.
*Compatibility.* `ExecutionRuntime.invoke()` and `WorkflowRuntime.execute()` are specified as "never raises". That wording must be amended to *"never raises for worker failure; native cancellation propagates after bounded cleanup"* (D1 in §15). The only production caller of `Worker.execute()` is `invoke()`; the only production caller of `invoke()` is `_execute_node_with_retry`; the only production callers of `execute()` are the two `Orchestrator` sites, whose `except Exception` already lets `CancelledError` through (`orchestrator.py:769,909`). No test pins swallowed-cancel behaviour (§2).
*Cleanup responsibilities, outermost last:* Worker — lifecycle state + `worker.cancelled` (bounded, best-effort); Runtime — WorkingMemory clear and runtime event in `finally`; Workflow — watchdog stop and graph/terminal finalization in `finally`; Orchestrator — nothing new; API — SSE generators must finalize their own graph node (separate follow-up).
*Terminal state while the exception propagates.* The `finally`/`except CancelledError` blocks run in the cancelled task after the node/worker call stack beneath them has unwound but *before the task itself has finished propagating*, so the state they record is evidence-based for the work beneath the finalizer — not a claim that the whole task has terminated (§21.2 A). Their own awaits (event emission) are subject to a second cancel and to N10's persisted-but-not-broadcast hazard; they must be bounded (§8.4 item 8).
*Effects already completed.* If `_run()` has returned when the cancel is delivered (P3), the work is done and the result is lost to the caller. The recorded state must say so (`COMPLETED`, not `CANCELLED`; payload `phase="post_run"`), and no rollback is implied (ADR-005).
*Callers expecting a `WorkerResult`.* Only in-repo callers; none pin the old behaviour.
**Assessment:** necessary and sufficient for the *native* path, **not sufficient alone** for #105's safety (H4–H6, H13).

### 8.2 Option B — return an explicit cancellation outcome

*Distinguishing from failure.* Possible only if every consumer checks the distinction. Today consumers key on `WorkerResult.success` (`runtime.py:786-808`, `orchestrator.py:532,742`), so an unflagged `success=False` is retried/branched — exactly P1. The workflow would need an explicit control-flow check before retry, error branch and successor traversal.
*Existing structures that already carry it:* `WorkerResult.execution_detail: ExecutionOutcome` (additive field; `FailureType.CANCELLED` exists), `NodeStatus.CANCELLED` and `ExecutionStatus.CANCELLED` (exist, never assigned), and the already-recognised `execution.cancelled` event name. A second result type would duplicate these.
*Applicability.* Option B **cannot** represent native cancellation without swallowing it. It *is* the right shape for OCBrain-owned cooperative cancellation (the token path of N2), where there is no exception to propagate.
**Assessment:** correct for token cancellation, wrong for native cancellation.

### 8.3 Option C — hybrid, and C+

C = A for native + B for token. C+ adds ten refinements; each is assessed below against evidence rather than adopted by default.

| # | C+ element | Assessment | Evidence / correction |
|---|---|---|---|
| 1 | Native cancellation propagates after bounded cleanup | **SUPPORTED** | P1, P7; Python docs; AnyIO guidance |
| 2 | OCBrain cancellation is a distinct control outcome, not an ordinary failed `WorkerResult` | **SUPPORTED in principle; carrier is an owner choice** | N2/P9 show today's token path reports failure. Reuse `execution_detail` + `NodeStatus/ExecutionStatus.CANCELLED` + `execution.cancelled` rather than new types (D-02) |
| 3 | No retry / error branch by default; exceptions need explicit workflow policy | **SUPPORTED** | native: P1, P10 (violated today); token: error branch already blocked (P9), retry blocked only after an uninterruptible backoff (N3) |
| 4 | Timeout/stall/governance/user causes remain distinguishable | **SUPPORTED, but requires a typed cause** | N6: two string encodings; B2d's "everything else is caller cancellation" would erase the distinction |
| 5 | Escalation to `Task.cancel()` preserves the original cause; mechanism recorded separately | **SUPPORTED** | `Task.cancel(msg=…)` carries only a string; the typed cause belongs in the owning runtime's state, with the message used for diagnostics only |
| 6 | Authority belongs to the owning runtime; workers get a read-only signal | **SUPPORTED as direction; not #105** | `ExecutionContext` hands every worker the same mutable token; no worker calls `.cancel()` today (grep), so this is a latent hazard, not a live defect |
| 7 | Terminal outcome and effect certainty derive from observed evidence | **SUPPORTED** | graph watchdog violates it today (H7/P8) |
| 8 | Cleanup bounded; never swallows the original cancellation; never hangs | **SUPPORTED; mechanism matters on 3.11** | mechanism is an implementation choice that must be *proven by tests* (§21.3; N17 records the `wait_for` hazard); a second cancel during cleanup must propagate (P5) |
| 9 | No compensation system | **SUPPORTED** | ADR-005; H19 |
| 10 | `FailureType.CANCELLED` is not automatically the canonical workflow type | **SUPPORTED** | it is an attempt-level classification, produced nowhere (H11/H12). Use it, if at all, only as the worker→workflow *carrier*; node/graph/workflow terminal state use the existing `CANCELLED` statuses |

**Alternative considered and not preferred — A-only everywhere.** Treating token cancellation as `Task.cancel()` of the node task would unify mechanisms but cannot cross the thread/process boundaries the token exists for, would make a *supervisor timeout* indistinguishable from a user stop at the `except` site, and would violate "the mechanism does not prove the stop" (§9). Not recommended.
**Alternative considered and deferred — `asyncio.TaskGroup`.** Available on 3.11; first child exception cancels siblings and the group raises an `ExceptionGroup`, which changes `PlannerWorker`'s deliberate "one module failing must not kill the others" semantics (`return_exceptions=True`, `planner.py:164`). Not a drop-in. Appropriate only if the owner wants required-vs-optional child semantics (§10); do not convert `gather()` call sites indiscriminately.

---

## 9. Corrected conceptual model — three dimensions

### 9.1 The dimensions (PROPOSED; challenged in §17 and found to hold with the corrections in §9.4)

1. **Initiation, authority and cause** — who/what asked for the stop, with what authority, over what scope: `user`, `parent_execution`, `watchdog_stall`, `watchdog_hard_deadline`, `governance`, `superseded`, `shutdown`, `process_termination`, `client_disconnect`, `external_caller`.
2. **Delivery / interruption mechanism** — how the request reaches the work and which resource it acts on: cooperative `CancellationToken`; `Task.cancel()` → `CancelledError`; owned `gather`/`TaskGroup` cancel; local stream close (`aclose`); provider cancel API; subprocess terminate; process shutdown.
3. **Observed outcome and effects** — what evidence shows happened: returned success; returned ordinary failure; cooperative stop acknowledged; task terminated; cleanup completed/failed; local stream closed; remote termination *unknown*; side effects *absent / committed / unknown*.

The dimensions are orthogonal: the same cause (`watchdog_hard_deadline`) can use either mechanism and end in any outcome (P8: delivered via token, ignored, **outcome = success**).

### 9.2 Required semantic distinctions mapped to evidence the code can already produce

| Distinction | Meaning | Where it is (or is not) observable today |
|---|---|---|
| Request | an authorised intention to stop | `token.cancel(reason)`; `Task.cancel()` call — **no event today** |
| Delivery | reached the component/task | token set; `CancelledError` thrown at an await — not recorded |
| Acknowledgement | component observed it | cooperative worker checks `token.is_cancelled`; native: `except CancelledError` ran — recorded only as `worker.cancelled` for native |
| Termination | execution actually stopped | for the work beneath a finalizer: the node/worker call stack unwound (the `finally` is running); the *task* itself terminates only when the exception finishes propagating, observable only to an outer supervisor; for provider/remote: **unobservable** |
| Cleanup completion | owned resources released or failed | WorkingMemory, watchdog task, router subtasks (PR #104 pinned the router's); not recorded |
| Effect certainty | absent / committed / unknown | no ledger; capability contract only |

These can be expressed with the existing event/status vocabulary plus **additive payload fields** (§9.3); no new enum is required for each concept.

### 9.3 Minimal compatible representation (PROPOSED; no new endpoint, no new event schema)

* **Request** — optional additive `execution.cancel_requested` is *not* proposed for #105; the request is represented by the existing token/`Task.cancel()` and is only recorded in the terminal event payload (`cause`, `mechanism`). Rationale: a request event without a terminal guarantee recreates the "FAILED before known" error (H7). Owner decision D-05.
* **Terminal** — the already-recognised `execution.cancelled`, emitted **by the owning workflow finalizer after the cancelled node/worker call stack has unwound, immediately before the workflow task propagates cancellation**. It never claims that the workflow *task* has terminated. Additive payload: `{execution_id, cause, mechanism, phase, observed: "node_stack_unwound"|"cooperative_stop_acknowledged"|"unknown", cleanup: "complete"|"failed"|"timed_out", effects: "committed"|"none"|"unknown"}`. Consumers of the `execution.*` family read `execution_id` and the event type only (`execution_graph.py:167-170`, `api.py:239-241`), so additive fields are compatible. **Subscriber termination must not depend on this broadcast** (§21.2 B). The *other* terminal family, `workflow.completed{success}`, is read by `EvaluatorWorker` (N18). Rev 2 (D-10): a cancelled workflow **does** emit `workflow.completed{success:false, cancelled:true}` from the same finalizer — it already is the terminal lifecycle event for failed workflows and carries `success` separately. On the **native** path the Orchestrator never reaches the Evaluator (the `CancelledError` unwinds `handle()` first); on the **token** path it does (`orchestrator.py:573-592` invokes `EvaluatorWorker` and `ReflectionWorker` after any returned `WorkflowResult`), so the Evaluator guard belongs to C-g (§21.4).
* **Graph/node status** — `ExecutionStatus.CANCELLED` / `NodeStatus.CANCELLED` (both exist; never assigned). The terminal-state set at `execution_graph.py:101` already lists `CANCELLED`, so timestamps behave.
* **Worker lifecycle** — `worker.cancelled` payload gains `phase ∈ {pre_run, run, post_run, event_emission}`; `WorkerState.COMPLETED` keeps meaning "the invocation returned", not "succeeded" (verified: `base.py:286` sets it before `result.success` is consulted; the success flag is on `worker.completed`).
* **Metrics** — cancellation must stop being counted in `_total_failures` (`base.py:295`). No cancellation counter exists (N13); adding one is part of the lifecycle change, not a new subsystem.

### 9.4 Corrections the challenge forced

1. **Cause must be typed.** The repository already has `CancelReason` (`stall`, `hard_deadline`, `external`) but the graph watchdog does not use its values (N6). A free-form string will drift again. The ADR proposes a typed cause carried by the existing token (extend `CancelReason` or add a sibling enum — owner choice D-03), with the string kept for display only.
2. **"Delivered" is not "stopped".** P8 shows a deadline cause, token delivery and a *successful* outcome. Any status derived from the request (as `record_failure` does today) is wrong by construction.
3. **Local close ≠ remote termination.** PR #104 pins that the router closes its local stream and leaks no task; nothing proves the provider stopped generating. Keep `termination="unknown"` for provider-side work.

### 9.5 Graph terminal-state transition policy (PROPOSED; added in revision 2 on owner review)

H7/N5/P8 show why a *policy* is needed: the watchdog records `FAILED` for a **request**, a worker then finishes, and `ExecutionGraph.update()` (no guard) rewrites the node to `COMPLETED` — a contradictory history. The requirement is a **monotonic state per execution attempt**, not merely a guard in `update()`. Existing vocabulary is sufficient: terminal = `COMPLETED`, `FAILED`, `CANCELLED`; non-terminal = `PENDING`, `RUNNING`, `STALLED`, `RECOVERING`, `WAITING`, `BLOCKED`.

| Situation | Required treatment | Lands with |
|---|---|---|
| Node already `COMPLETED` when cancellation arrives | preserved; never overwritten | #105 (C-d) |
| Active node receives native cancellation | finalized `CANCELLED` | #105 (C-d) |
| Root receives native cancellation | finalized `CANCELLED` (after its active node) | #105 (C-d) |
| Earlier completed nodes | remain `COMPLETED` | #105 (C-d) |
| Nodes that never started | remain `PENDING` (not run), not relabelled | #105 (C-d) |
| Watchdog *requests* a stop (stall / deadline) | recorded as a request (typed cause on the token; non-terminal marker such as `STALLED`), **not** `FAILED`, not `CANCELLED` | C-g |
| Worker continues after a token request | stays `RUNNING`; no claim that it terminated | C-g |
| Worker returns a real result after a request | node takes the real outcome (`COMPLETED`/`FAILED`); the request and its cause stay in the history; execution outcome derives from the node results | C-g |
| A result arrives after the node is already terminal | explicit rule (D-13): ignore-for-status + log, or record as a separate history entry; **never** a silent status rewrite | C-d for native finalization; C-g for the general guard |

**Phasing hazard (not obvious from the review's table; recorded for the owner).** An *absorbing* terminal-state guard in `ExecutionGraph.update()` must **not** land before the watchdog stops writing `FAILED` for requests. With the guard but without the watchdog change, P8's late success would be pinned as `FAILED` under a workflow that returns `success=True` — a different contradiction. Therefore #105 implements monotonicity **inside its own finalization routine** (it writes `CANCELLED` only to non-terminal active nodes and never rewrites a terminal node) and leaves `update()` and the watchdog's request semantics to C-g. A resumed attempt (ADR-KERNEL-03) is a new attempt with its own history; how a `CANCELLED` node re-enters `PENDING` is part of D-08, not of this table.

---

## 10. Scope and ownership model (verified relationships only)

| Relationship | Is it task ownership? | Evidence |
|---|---|---|
| Workflow DAG edge `A → B` | **No.** Ordering/data dependency only | `_continue_to_successors` runs successors sequentially in the same task (`runtime.py:815-840`); no task per node |
| `ExecutionGraph` parent/child (root → node) | **No.** Display hierarchy | `execution_graph.py`; the watchdog marks root *and* nodes (P8) |
| `WorkflowRuntime._run()` ↔ node execution | **Yes — same Python task.** One task runs all nodes sequentially; cancelling it interrupts exactly the active node | `runtime.py:552`; P1 |
| `WorkflowRuntime._run()` ↔ `GraphExecutionWatchdog` | **Yes — owned child task**, started `:517`, must be stopped in `finally` | H5, H6 |
| `PlannerWorker._run()` ↔ `_dispatch_module` tasks | **Yes — owned children** via `gather` (parent cancel cancels all — P11) | `planner.py:164` |
| `ModelRouter` ↔ its provider/consumer/shadow subtasks | **Yes — owned**, pinned by PR #104 | `model_router.py:217-232,466-515` |
| HTTP SSE subscriber ↔ workflow | **No.** Subscriber may detach; operation durable unless the work lives inside the response generator (C2) | C1, C2, `/executions/{id}/events` |
| Single-module streaming response ↔ provider stream | **Yes — coupled by construction** (work is inside the generator) | C2 |
| Orchestrator ↔ background services | Yes (`_background_tasks`, `close()`), but **not** request tasks | `orchestrator.py:162-169` |
| Uvicorn ↔ in-flight request tasks | Yes (supervised; waits, cancels only after timeout) | C4/C4b |
| Voice hotkey ↔ request | None — the task is created on the wrong thread and unreferenced | P13 |

**Required policy statements (for the ADR, PROPOSED):** (a) cancelling a node does not cancel DAG siblings or the parent execution — the workflow decides; (b) cancellation of the owning task cancels its *owned* children and **waits** for them (Python's `gather`/task-group semantics already do this: a cancelled parent resumes only after children finish unwinding — P11); (c) optional/required/detached children are not distinguished anywhere today — the only real children are Planner module tasks (all treated as "required, failures tolerated"), router subtasks (owned) and the watchdog (owned); introducing a hierarchy policy is outside #105 (D-04).

---

## 11. DEBT-105 — recommended contract and implementation boundary (PROPOSED; not authorized)

### 11.1 Intended behaviour for native task cancellation

**Workflow level (what a caller must be able to rely on):**

1. The cancellation is **never converted into a `WorkerResult`** and is **never retried or branched on as an ordinary failure** — no `RetryPolicy` attempt, no `error_branch`, no successor traversal.
2. The caller's cancellation stays observable: `WorkflowRuntime.execute()` re-raises `CancelledError` (the "never raises" docstrings are amended to "never raises for failure; native cancellation propagates").
3. Unrelated concurrent executions are unaffected: each execution has its own task, token, graph and watchdog; the only shared structures are the keyed `execution_registry` and the event stream (T-R12 checks this).
4. Owned work is cleaned up or honestly reported: the graph watchdog is stopped; Planner `gather` children and router subtasks are cancelled and awaited by the unwinding (P11, PR #104); a resource that cannot be confirmed stopped is reported `termination="unknown"` rather than `CANCELLED`-as-fact.
5. Graph and subscribers reach a terminal state: root and active node become `CANCELLED` and one `execution.cancelled` event is emitted best-effort and bounded, from the workflow finalizer after the node/worker stack has unwound (§9.3); **the subscriber terminates even if that event is never persisted or broadcast** (§21.2 B).

**Worker boundary, by arrival point:**

| Cancellation arrives… | Required behaviour | `ed3d141` (probe) |
|---|---|---|
| before the state change (governance is evaluated synchronously, `base.py:246`; the only cancellable awaits are the `worker.rejected` / `worker.escalated` emissions at `:249` and ~`:262`, which have no state to restore) | propagate; nothing to clean | propagates (no `try` — correct today) |
| during `worker.started` emission (`base.py:275`) | extend the protected region to start at `state=RUNNING`; state → `CANCELLED`, `phase="event_emission"`; propagate | exception escapes, state stays `RUNNING` (P2) |
| during `_run()` | state → `CANCELLED`, `worker.cancelled{phase:"run"}` (bounded, best-effort), **not** counted in `total_failures`; propagate | swallowed → failed result → retry (P1) |
| after `_run()` returned, during `worker.completed` emission (`:287`) | state **stays `COMPLETED`**; best-effort `worker.cancelled{phase:"post_run", work_completed:true}`; propagate — the result is lost to the caller but the *record* says the work finished | real result discarded, state `CANCELLED`, counted as failure (P3) |
| during the `worker.cancelled` emission itself | the new cancellation propagates immediately; no further awaits in the worker; the layer above still clears WorkingMemory | escapes; WorkingMemory uncleared (P5) |
| during the runtime event or WorkingMemory cleanup in `invoke()` | `working_memory.clear()` is synchronous (`working_memory.py:81`) — run it **first**, in a `finally`, then the best-effort event | skipped (P4) |

`WorkerState.COMPLETED` keeps its present meaning — *the invocation returned* — which is already what `base.py:286` implements (the success flag lives on the `worker.completed` event). Lifecycle events describe execution phase, not successful outcome (`worker.completed` is emitted for every returned result and carries `success`). **One in-repo consumer reads them, and it does not honour that distinction:** `EvaluatorWorker` (`core/workers/evaluator.py:251-256,176-181`) computes `tool_success_rate = len(worker.completed) / (len(worker.completed)+len(worker.failed))` from event *counts*, so a returned `success=False` result is counted as a success (N18), and `worker.cancelled` is invisible to it. The contract must therefore **not** change what `worker.completed` means; it should be written down, and the Evaluator's miscount recorded as a separate finding (not fixed here).

### 11.2 Companion changes — classification

| Companion | Class | Why | Evidence |
|---|---|---|---|
| **C-a** `ExecutionRuntime.invoke()`: `working_memory.clear()` first, in a `finally`, synchronously and before any awaited event; **no ordinary `execution.completed` runtime event on the cancellation path** (`worker.cancelled` is the record; a "completed" event for a cancelled invocation is misleading — N1/rev 2) | **Independently mergeable prerequisite; essential for #105** | Harmless today (changes behaviour only when `CancelledError` already escapes); becomes the main path the moment `Worker.execute()` propagates | H4, P4, P5 |
| **C-b** `GraphExecutionWatchdog.stop()`: preserve caller cancellation; clear `_task` in `finally`; bounded join by a mechanism that keeps external cancellation observable and leaves no detached task (§21.3); **note the open PR #81 already carries a `stop()` rewrite (§21.1) — unreviewed, and its unbounded drain loop would not satisfy T-G4** | **Independently mergeable prerequisite; essential for the acceptance criteria T-G2/T-G4 (second or repeated cancellation during cleanup), *not* for the single-cancel unwinding path** | Defect exists today (P7); a first cancellation already propagating through C-d's `finally` survives a swallowing `stop()`, a *new* cancellation delivered during the join does not | H6, P7 |
| **C-c** `Worker.execute()` propagation + lifecycle + metrics (the #105 defect itself) | **#105 core** | H1–H3 | P1–P3, P10 |
| **C-d** `WorkflowRuntime._run()`: one `try/finally` from `watchdog.start()` to function exit that stops the watchdog, finalizes graph (root + active node → `CANCELLED`), emits `execution.cancelled` and `workflow.completed{success:false,cancelled:true}` (bounded), **terminates event-stream subscribers independently of broadcast success** (§21.2 B), finalizes **monotonically** (§9.5), and re-raises | **Essential; cannot ship without C-c** (shipping C-c alone turns a wrong-answer defect into leaked-task + stuck-graph + hung-subscriber defects) | H5, H13 | P6, P6b, C3 |
| **C-e** `asyncio` 3.11 in CI (`ci.yml` matrix) | **Independently mergeable prerequisite for trustworthy acceptance** | the declared minimum is not tested (N16); probes show 3.11/3.12 agree today but the `wait_for` family differs (N17) | §2 |
| **C-f** `/query` single-module SSE finalization on `CancelledError`/`GeneratorExit` | **Separate follow-up; should block the *contract's* final acceptance, not #105** | reachable today independent of #105 (C2); a different component (`interface/api.py`) | H13, C2 |
| **C-g** token-path outcome (distinct non-failure outcome, interruptible backoff, typed cause, no `FAILED` for a request) | **Separate follow-up; should block the contract's final acceptance, not #105** | reachable today only via the graph watchdog; independent mechanism (Option B) | N2, N3, N6, H7, H9 |
| **C-h** documentation/contract amendments (§15 D1–D10) | **Delivered by the ADR once accepted** | historical documents are preserved, not rewritten | §15 |

### 11.3 Smallest safe cohesive boundary

> **#105 = C-c + C-d**, merged only **after** C-a and C-b (and preferably C-e). The behaviour change is one reviewable unit; the prerequisites are individually valid, individually testable and individually revertible. Nothing in C-f/C-g is required for #105's own correctness; both must be tracked so that "cancellation" is not declared complete when only the native path is fixed.

Why not narrower: `Worker.execute()` alone is demonstrably unsafe (P4/P5/P6/C3). Why not wider: every added concern (B2d, disconnect, resume, hierarchy) has an independent evidence base, owner decision and revert unit.

---

## 12. Explicit exclusions from #105

| Excluded item | Why it is separable | Dependency on #105 | Revisit condition |
|---|---|---|---|
| **B2d** token propagation into `ModelRouter`/`AdapterRuntime` | Different mechanism (cooperative), different files, needs a token that is *reachable* — it is not (§3; `ContextMemory` carries none). The branch also treats any non-local reason as *caller cancellation* (N6) and adds no change to `planner.py`/`capability_executor.py`, so its tests inject the token through a field production never fills | none for #105 correctness | owner decides token identity/scope (D-02/D-03); B2d re-reviewed from scratch, not cherry-picked |
| Provider-side remote cancellation | Closing a local stream proves nothing about the remote server | none | server-side probe (UNVERIFIED today) |
| Full workflow cancellation API (`WorkflowRuntime.cancel()` / endpoint) | Documented but never built (D2); needs authority, idempotency, identity decisions | C-d provides the finalization it will call | D-01/D-05 accepted |
| Shutdown policy (`timeout_graceful_shutdown`, draining) | Uvicorn already supervises requests (C4/C4b); policy question, not a defect | none | D-06 |
| Client-disconnect policy | Path-dependent today (C1 vs C2); product decision | C-f touches only finalization | D-06 |
| Checkpoint/resume redesign | `resume()` has no production caller; rule needed before it is wired | C-d must record `CANCELLED` so resume *can* distinguish (H18) | D-08 and a first production caller |
| Parent/sibling/child hierarchy policy | only owned children exist today (§10) | none | a second owned-child pattern appears |
| Compensation / rollback | rejected by ADR-005 | none | never, without a new ADR |
| New execution identity / idempotency architecture | outside cancellation | at-least-once stays (ADR-KERNEL-03) | owner request |
| Voice `create_task()` from `keyboard`'s thread (H17) | independent defect, `global.voice_enabled` only | none | owner authorizes a voice packet |
| `CancellationToken` thread-safety (H16) | affects only cross-thread callers; none exist except the voice path | none | before any thread/process cancel source is added; at minimum correct the docstring |
| FZ-01 (`wf_result.output or ""`, N8) | separate OPEN finding | none | FZ-01 decision |
| Router training/promotion guard (H12) | existing tracked item; guard exists only on B2d | none | with B2d |

---

## 13. Test and acceptance matrix (to be implemented with the change; none of these tests exist yet)

Constraints: run each test on **3.11 and 3.12**; run the focused files in a **temporary copy or with config isolation** until DEBT-012 is fixed; record command, interpreter, counts and failures. "Fails on `ed3d141`" lists the probe that already demonstrates the baseline failure.

### 13.1 Worker boundary (`tests/test_worker_cancellation.py`)

| ID | Invariant | Setup / action | Expected after change | Fails on `ed3d141` |
|---|---|---|---|---|
| T-W1 | cancel during `worker.started` emission propagates, state consistent | delay `worker.started`; cancel | `CancelledError`; state `CANCELLED` (`phase=event_emission`) | state stays `RUNNING` (P2) |
| T-W2 | cancel during `_run()` propagates | sleeper worker; cancel mid-run | `CancelledError`; `worker.cancelled{phase:run}`; **no failed result returned** | returns failed result (P1) |
| T-W3 | cancel after `_run()` returns keeps work state | `_run` returns success; delay `worker.completed`; cancel | `CancelledError`; state `COMPLETED`; `worker.cancelled{phase:post_run,work_completed:true}` | state `CANCELLED`, result discarded (P3) |
| T-W4 | second cancel during `worker.cancelled` emission | cancel twice | second cancel propagates; worker makes no further await | n/a (swallowed first) |
| T-W5 | bounded cleanup | `worker.cancelled` emission hangs | cleanup abandoned after bound; original `CancelledError` still raised; **no hang** | n/a |
| T-W6 | completed effects not described as absent | T-W3 + assert event/state say completed | `work_completed` true | state says cancelled (P3) |
| T-W7 | state, result, events, exception asserted independently | all of the above | each asserted in its own assertion | — |
| T-W8 | ordinary worker failure unchanged | `_run` raises `ValueError` | failed `WorkerResult`, `worker.failed`, `total_failures` +1 | passes (guard test) |
| T-W9 | cancellation not counted as failure | cancel mid-run | `total_failures` unchanged; cancellation counter +1 | counted as failure (`base.py:295`) |
| T-W10 | governance rejection unchanged | rejected action | rejected result, `worker.rejected` | passes (guard) |

### 13.2 Runtime and workflow (`tests/test_workflow_cancellation.py`)

| ID | Invariant | Setup / action | Expected | Fails on `ed3d141` |
|---|---|---|---|---|
| T-R1 | WorkingMemory cleared on success / ordinary failure / native cancel (3 cases) | scratch key in context; run each | cleared in all three | not cleared when cancel escapes (P4/P5) |
| T-R2 | no retry after native cancel | `max_retries=2`; cancel mid-node | node executed once; `CancelledError` | executed twice, `success=True` (P1) |
| T-R3 | no error branch after native cancel | `error_branch` set; cancel | recovery worker executed 0 times | executed (P10) |
| T-R4 | pre-cancelled token | token cancelled before `execute` | chosen distinct non-failure result (D-02) | `execution.failed`, node FAILED (P9/N2) — *covered by C-g, expected-to-fail until then* |
| T-R5 | token set during active work is observed per cooperative contract | cooperative worker; set token | worker stops; outcome per D-02 | ordinary failure (P9) |
| T-R6 | a worker that ignores the token is not reported terminated | `Sleeper`; graph deadline | node not `FAILED`/`CANCELLED` until the task actually ends; final status = real outcome | FAILED then COMPLETED (P8) |
| T-R7 | cancel between nodes prevents new work | 3-node chain; cancel after node 1 | node 2 never starts | token path passes; native path: cancel lands inside a node |
| T-R8 | cancel racing node success: graph, result and events agree | cancel at the instant node 1 returns | either (success→cancel) or (cancel) — never `COMPLETED`+`failed` for one node | contradictory event history (P8) |
| T-R9 | cancelled workflow enters no successors | chain; cancel node 1 | node 2 not executed | passes for token; verify for native |
| T-R10 | no active watchdog task after cancel at **each** await (`workflow.started`, node loop, `record_status`, terminal emit) | parametrised delay per await | `all_tasks()` has no `GraphExecutionWatchdog._run` | leaked (P6, P6b) |
| T-R11 | ordinary failures still retry/branch exactly as configured | failing worker, `max_retries=2`, branch | 3 attempts then branch | passes (guard) |
| T-R12 | unrelated concurrent execution unaffected | run A and B concurrently; cancel A | B completes `success=True` with its own graph | not tested |
| T-R13 | `execute()` re-raises | cancel mid-node | `task.cancelled()` is `True` | `False` (P1) |
| T-R14 | native-cancel finalization is **monotonic** (§9.5): completed predecessors stay `COMPLETED`; the active node and the root become `CANCELLED`; unstarted nodes stay `PENDING`; no `FAILED`→`COMPLETED` history | 3-node chain; cancel node 2 | exact statuses and event history asserted | n/a (propagation absent) |
| T-R15 | `ExecutionRuntime.invoke()` publishes **no ordinary `execution.completed`** on its cancellation path | cancel mid-invocation | no runtime `execution.completed`; `worker.cancelled` present | emitted with `success:false` when the cancel is swallowed (P1) |

### 13.3 Watchdog (`tests/test_graph_watchdog_cancel.py`)

| ID | Invariant | Expected | Fails on `ed3d141` |
|---|---|---|---|
| T-G1 | `stop()` consumes only its own child's cancellation | child cancelled → `stop()` returns, `_task is None` | passes |
| T-G2 | `stop()` does **not** swallow caller cancellation | cancel caller during join → `task.cancelled()` | swallowed (P7) |
| T-G3 | workflow cancel at each await still stops watchdog | = T-R10 | P6/P6b |
| T-G4 | repeated cancel during cleanup is bounded | cancel twice | returns within bound; no hang | n/a |
| T-G5 | a *request* is not recorded as observed terminal failure | stall → watchdog fires | no `execution.node.failed` until termination observed; request visible as pending | `failed` emitted first (P8) |
| T-G6 | cooperative worker's late result is reflected | worker finishes after request | final state = real result; no stale `failure_type` | stale (P8/N5) |
| T-G7 | non-cooperative continuation represented honestly | worker ignores token | `termination:"unknown"`/still `running` until task ends | `FAILED` (P8) |
| T-G8 | cause encoding typed | graph watchdog token reason equals typed cause | `"execution hard_deadline" != CancelReason` (PR probe) |

### 13.4 Planner and adapters

| ID | Invariant | Expected | Fails on `ed3d141` |
|---|---|---|---|
| T-P1 | independently cancelled `gather` child | child reported as an explicit non-result; never passed to the merger as a `RouteResult`; `PlannerWorker` result annotates the dropped module | `success=True`, silent drop (P11) |
| T-P2 | parent cancel stops all owned children and waits | both children not completed; `CancelledError` | passes (P11) — guard |
| T-P3 | no fallback adapter after native cancel | `AdapterRuntime` with 2 adapters; cancel during first | second adapter never invoked; no `_mark_failure` | passes (guard, pinned by #104) |
| T-P4 | stall/deadline keep fallback semantics | provider stall → fallback | unchanged | passes (guard) |
| T-P5 | token cancel cannot start another generation | (B2d scope) | — | deferred with B2d |
| T-P6 | cancelled/incomplete output not a training pair / promotion | (B2d scope) | — | `route()` records unconditionally (H12) |

### 13.5 Events and API

| ID | Invariant | Expected | Fails on `ed3d141` |
|---|---|---|---|
| T-E1 | cancelled workflow emits the chosen terminal events | `execution.cancelled{execution_id,cause,mechanism,phase,observed,cleanup,effects}` once, plus `workflow.completed{success:false,cancelled:true}`; payload never claims the workflow *task* terminated | never emitted (grep; C3) |
| T-E2 | `/executions/{id}/events` terminates | stream ends on `execution.cancelled` | waits indefinitely (C3) |
| T-E3a | **actual HTTP subscriber terminates when the terminal event is never persisted** (emission cancelled/raises before persistence) | real Uvicorn + `/executions/{id}/events` subscriber; graph finalised | stream ends within a bounded interval; terminal state inspectable by snapshot | waits indefinitely (C3) |
| T-E3b | **actual HTTP subscriber terminates when the terminal event is persisted but not broadcast** | slow `_append_sync`, emitter cancelled between persist and notify | stream ends within a bounded interval; row present; snapshot terminal | **reproduced: persisted row, snapshot `cancelled`, subscriber still waiting (C5)** |
| T-E3c | subscriber termination when the emitter raises a non-cancel exception | store failure | same | not tested |
| T-E4 | graph status, `WorkflowResult`/exception and event history agree | compare three | agree | disagree (P6/P6b/P8) |
| T-E5 | subscriber disconnect ≠ logical cancel (non-stream `/query`, `/executions/*/events`) | operation completes | passes (C1) — guard |
| T-E6 | disconnected subscriber cannot cancel unrelated work | two concurrent requests | unaffected | not tested |
| T-E7 | if the operation intentionally continues after disconnect, that is explicit | documented + asserted | implicit (C1 vs C2) |
| T-E8 | single-module SSE finalizes graph on disconnect | node/ root terminal; terminal event | node `running`, no event (C2) |

### 13.6 Recovery and effects

| ID | Invariant | Expected | Fails on `ed3d141` |
|---|---|---|---|
| T-X1 | crash-interrupted `RUNNING` node keeps at-least-once resume | `resume()` re-runs it | passes — guard |
| T-X2 | intentionally cancelled node is not auto-restarted without the future authorization | resume skips or demands authorization | **cannot be asserted until D-08**; document, do not assert |
| T-X3 | no test claims exactly-once | review gate | — |
| T-X4 | unknown external effect stays unknown | `effects:"unknown"`; no rollback event | — |
| T-X5 | event persisted-but-not-broadcast tolerated | cancel mid-append; consumers read store | consistent with P15 |

### 13.7 Infrastructure

| ID | Requirement |
|---|---|
| T-Z1 | CI matrix includes 3.11 (C-e) |
| T-Z2 | new tests isolate config/data writes (DEBT-012) — temp copy or fixture |
| T-Z3 | cancellation tests use deterministic await-boundary injection (delay-before-persist `EventStream` double), not `sleep`-based timing guesses |

### 13.8 Orchestration and Evaluator (rev 2)

| ID | Invariant | Expected | Fails on `ed3d141`/`2491ae4` |
|---|---|---|---|
| T-V1 | native cancellation of `Orchestrator.handle()` on the K4.2 path never reaches `EvaluatorWorker`/`ReflectionWorker` and writes no L1 evaluation record from partial worker events | cancel during the workflow; assert no `EvaluatorWorker` invocation and no evaluation memory write | passes only after propagation (today the swallow lets the workflow return a result and the Evaluator runs — `orchestrator.py:573-592`) |
| T-V2 | **(C-g, token path)** an Evaluator invoked after a cancelled-by-token `WorkflowResult` recognises `cancelled` and does not produce an ordinary `tool_success_rate` from partial counts | `workflow.completed{cancelled:true}` in history | writes a record with a partial-count rate (N18) |

---

## 14. External research (primary sources) and how each applies to OCBrain

| Source | What it establishes | Applies to OCBrain? |
|---|---|---|
| Python 3.11 *Coroutines and Tasks* — https://docs.python.org/3.11/library/asyncio-task.html (the retrieved text was the identical passages on the 3.9/3.10 locale copies of the page; the 3.11 behaviour was independently confirmed on CPython 3.11.15 by P11/P11b and the stdlib source) | With `return_exceptions=True`, exceptions are aggregated like results; a cancelled child is, in the docs' words, "treated as if it raised `CancelledError`" and the `gather()` call itself is *not* cancelled; cancelling the `gather()` cancels the submitted awaitables; the loop keeps only weak references to tasks, so fire-and-forget tasks need a retained reference; `asyncio.TaskGroup` and `asyncio.timeout()` exist from 3.11 | **Applies directly**: H10 (child returned as a `BaseException` instance), P11 parent-cancel (children stop), N11 (fire-and-forget sites). *Does not apply*: 3.13+ `TaskGroup` cancellation helpers — not assumed |
| Python 3.11 *Synchronization Primitives* — https://docs.python.org/3.11/library/asyncio-sync.html | asyncio primitives, `Event` included, are not thread-safe | **Applies**: H16/P12 |
| Python 3.11 *Developing with asyncio* — https://docs.python.org/3.11/library/asyncio-dev.html | From another OS thread use `loop.call_soon_threadsafe()` for callbacks and `asyncio.run_coroutine_threadsafe()` for coroutines; in debug mode non-thread-safe APIs raise when called from the wrong thread | **Applies**: H17 (the correct bridge for the voice callback is `run_coroutine_threadsafe` onto the captured loop — a *recommendation for a separate packet*, not designed here) and P12's debug-mode `RuntimeError` |
| CPython 3.11.15 `asyncio/tasks.py` (installed stdlib) | `wait_for` returns the inner result if the outer task is cancelled when the inner is already done | **Applies**: N17; informs "use `asyncio.timeout()` for bounded cleanup on the 3.11 baseline" |
| AnyIO *Cancellation and timeouts* — https://anyio.readthedocs.io/en/latest/cancellation.html | Cancellation exceptions must be re-raised; cleanup that must run after cancellation is done in a *shielded scope with a deadline* so it can neither be interrupted forever nor hang; AnyIO's cancellation is level-triggered (delivered at every checkpoint inside a cancelled scope) whereas asyncio's `Task.cancel()` is edge-triggered (delivered once) | **Applies**: principles 1 and 8 of C+ (propagate; bounded cleanup). *Does not apply*: level-triggered delivery is not available to OCBrain's asyncio code on 3.11 — a *second* delivery must be requested explicitly, which is why P5/T-W4 test repeated cancel. AnyIO is not a dependency of OCBrain's kernel and none is proposed |
| Temporal *Cancellation and Termination* — https://docs.temporal.io/encyclopedia/workflow/cancellation-and-termination and *Request Cancel for an Activity* — https://docs.temporal.io/activity-operations/request-cancel | Cancellation is a *request* the workflow/activity may observe and clean up after; termination is forceful and gives no cleanup; an accepted cancel request does not by itself mean the activity stopped | **Applies as vocabulary**: request vs delivery vs acknowledgement vs termination (§9.2); `termination:"unknown"`. *Does not apply*: durable-execution history/replay determinism and server-side workers — OCBrain's `resume()` is at-least-once re-execution, not event-history replay |
| `keyboard` (boppreh) README / PyPI, and the **installed** `keyboard==0.13.5` source (`__init__.py:620`) | `add_hotkey` callbacks run "in a separate thread, asynchronously"; the listener uses its own `listening_thread`/`processing_thread` (`_generic.py:38,42`) | **Applies**: H17 for the version `requirements.txt` resolves to (0.13.5 is also the latest release). Upstream `master` was not relied on |
| Uvicorn 0.54.0 `server.py:286-355` (installed) | `capture_signals` installs `handle_exit` for SIGINT/SIGTERM during `serve()`; shutdown waits for connections and `server_state.tasks`; `timeout_graceful_shutdown` cancels remaining tasks; `force_exit` set by a second SIGINT | **Applies**: H15 / N12; confirmed behaviourally by C4/C4b |

---

## 15. Documentation and contract discrepancy register

Historical documents are **preserved**. The proposed ADR *refines or supersedes* the cited conclusions by reference; it does not edit them.

| ID | Document (as of `ed3d141`) | Claim | Reality (evidence) | Proposed handling |
|---|---|---|---|---|
| D1 | `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §7.1 (`:230` "Return WorkerResult (never raises)"); `runtime.py:254,317,479`; `orchestrator.py:662` | `ExecutionRuntime.invoke()` / `WorkflowRuntime.execute()` never raise | native `CancelledError` is a `BaseException` and passes the `except Exception` at `execution_runtime.py:196` and, when it escapes, through `execute()` (P4, P6, P6b) | ADR amends to "never raises for failure; native cancellation propagates after bounded cleanup" |
| D2 | `KERNEL_ARCHITECTURE_v1.0.md` §8 (`:361` `async def cancel(self, instance_id)`); `K2_IMPLEMENTATION_PLAN.md:144` "WorkflowRuntime.cancel() (cancellation propagation)" | a workflow cancel operation is part of the contract | no `def cancel` exists in `core/workflow` or `core/runtime` workflow code; no production caller; K2 plan step 6 was never delivered or was dropped without a recorded decision | ADR records it as *unimplemented*; its design is deferred (§12) |
| D3 | `docs/architecture/k4_2_architecture_hardening_review.md` §6 (`:160-177`) "Cancellation Semantics — REJECTED … already fully specified"; summary row `:21` | `CancellationToken` + lifecycle states + EventStream + `SHUTTING_DOWN` draining already cover every cancellation scenario | #105/P1 (retry after cancel), N2 (cancel reported as failure), H13 (no terminal event), H5 (no `finally`), N12 (shutdown waits, does not drain by cancelling) | ADR *refines*: the primitives exist but their composition is unspecified; supersedes the "No change needed" conclusion. §6 itself is left as written |
| D4 | `ADR_KERNEL_03_CHECKPOINT_RESUME.md` ("`RUNNING` (or `CANCELLED`) node is reset to `PENDING`") ; `runtime.py:405` | `CANCELLED` nodes can occur and are safe to reset | `NodeStatus.CANCELLED` is never assigned (`runtime.py:354` docstring concedes "not-currently-reachable"); token-cancelled nodes become `FAILED` (P9) and are **cached, not re-run**; native-cancelled nodes re-run as `PENDING` | ADR refines: once `CANCELLED` is assigned, resume must distinguish crash from intentional cancel (D-08). ADR-KERNEL-03 untouched |
| D5 | PR #104 / `docs/handoffs` text: the graph watchdog "only sets a token that no node observes" | token is unobserved | refine: the token **is** delivered to workflow workers (`ExecutionContext.cancellation_token`, `runtime.py:~885`) and observed by a cooperative worker (P9); it does **not** reach the Planner→`AdapterRuntime`→`ModelRouter` path (`planner.py:321-329` payload has no token; `model_router.py:420` resolves from a `ContextMemory`) | study states the precise form; handoff left as is |
| D6 | `KERNEL_ARCHITECTURE_v1.0.md` §7.4 (`:279` `def cancel(self) -> None`) and event table (`:722` `worker.cancelled` — "CancellationToken triggered") | token API has no reason; `worker.cancelled` reports token triggering | live `cancel(reason)`; `worker.cancelled` is emitted only for native `CancelledError` (`base.py:293-296`); a token trigger produces `worker.completed{success:false}` (P9) | ADR corrects the mapping |
| D7 | `core/runtime/cancellation.py:13` "Thread-safe via asyncio.Event" | thread-safe | P12; docs: not thread-safe | correct the docstring (no behaviour change needed unless a foreign-thread caller is introduced) |
| D8 | `core/workers/base.py` `execute()` docstring "Raises: GovernanceRejectionError" | governance rejection raises | governance rejection returns a failed result and emits `worker.rejected` (`base.py:246-262`) | doc-only; not cancellation; listed for completeness |
| D9 | `docs/architecture/decisions/ADR_INDEX.md` | index lists the ADRs | `ADR_KERNEL_08_REJECT_CONTENT_CORROBORATION_AUTHORITY.md` exists on `main` but has no row; the next free identifier is therefore `ADR-KERNEL-09` (scan of all 107 remote branches found no other claimant) | this study adds only its own row; the missing KERNEL-08 row is **reported, not repaired** *(Rev 2: resolved upstream by PR #106 for KERNEL-08; this study's row is rebased onto the current index.)* |
| D10 | `KNOWN_ISSUES.md`, `CURRENT_STATE.md` | project-state documents | grep shows **no** entry for #105, native/token cancellation semantics, or the absent `WorkflowRuntime.cancel()` (only FZ-01 and the resolved DEBT-016 touch adjacent ground) | not edited here (mission boundary); owner decides after review whether `KNOWN_ISSUES.md` gains entries |

---

## 16. ADR and index record

* **Identifier:** next free is **`ADR-KERNEL-09`** (`docs/architecture/decisions/ADR_KERNEL_09_CANCELLATION_CONTRACT.md`). Numbering convention checked against `ADR_INDEX.md`, the ADR directory on `main` (01–04, 06, 07, 08) and every remote branch (no 09 anywhere, no textual claim on "ADR-KERNEL-09").
* **Status:** `PROPOSED — pending repository owner decision`.
* **Index:** exactly one row appended to the ADR table; nothing else in the index touched (D9).
* A new ADR is justified because the contract spans five components, supersedes a published rejection (D3), amends two frozen-document statements (D1, D6) and has several owner decisions that must be recorded rather than left in an issue.

---

## 17. Second-pass review — attempts to disprove this study's own conclusions

Each target was attacked with a concrete counter-argument and, where possible, a counter-probe. Result and any change forced on the study are recorded; unresolved items stay UNVERIFIED.

| # | Target | Counter-argument tried | Outcome |
|---|---|---|---|
| 1 | **C+** | (a) "Option A for everything is simpler" — rejected: token cancellation must cross thread/process boundaries, cannot carry typed cause through `except`, and would turn a supervisor timeout into an indistinguishable user stop. (b) "The token path is dead code, so Option B is unnecessary" — **partly true**: no production code supplies a token (H8), so the token path is reachable *only* through `GraphExecutionWatchdog`. | **Survives, narrowed.** C+ element 2's carrier is an owner decision (D-02), and C+ element 6 is direction-only. The study does not claim the token path is a live user-cancel feature — it is a live *supervisor-timeout* path (P8/P9). |
| 2 | **Three-dimension model** | Find a scenario that does not factor. Shutdown (cause: `shutdown`; mechanism: Uvicorn task cancel after timeout; outcome: stack unwound) and client disconnect (cause: `client_disconnect`; mechanism: Starlette cancels the response generator; outcome: provider stream closed, remote unknown) both factor. The graph watchdog is the counter-example *to the code*, not the model: it records an outcome from a request (H7). | **Survives with corrections §9.4** (typed cause; delivered ≠ stopped; local ≠ remote). |
| 3 | **#105 boundary** | (a) Ship C-c alone — P6/P6b/C3 show leaked task, RUNNING graph, hung subscriber. (b) Drop C-b — a *first* cancellation already unwinding through `finally` survives a swallowing `stop()`. (c) Drop C-a — `WorkingMemory` leak becomes the primary path (P4). | (a),(c) confirmed necessary. **(b) forced a change**: C-b is essential for the repeated-cancel acceptance criteria (T-G2/T-G4), not for the single-cancel path (§11.2 reworded). |
| 4 | **Companion order** | Does moving `working_memory.clear()` ahead of the awaited runtime event change the normal path? The runtime event payload was read: it carries `request_id`/`success`/error and no working-memory content (`execution_runtime.py:205-225`). | Safe — INFERRED by reading; T-R1 covers it. Merge order C-a/C-b/C-e → C-c+C-d stands. |
| 5 | **Graph-watchdog state claims (H7/N5)** | "FAILED→COMPLETED may be an intended late-recovery feature." `ExecutionGraph.update()` has no guard and no comment either way; P8 shows a contradictory *history* (`failed` then `completed`) and `success=True` for a deadline-expired workflow. | VERIFIED behaviour; calling it a *defect* rests on the mission's own rule that a request must not be reported as an outcome. The owner may instead choose "late completion supersedes" — D-05 records the choice. |
| 6 | **API terminal-event gap (H13)** | Perhaps the registry synthesises a terminal event when the graph turns terminal. `ExecutionRegistry._on_event` only forwards persisted events; C3 shows a live subscriber still waiting 3 s after the cancel and ending only when `execution.cancelled` was emitted by hand. P6b additionally shows a graph that is `COMPLETED` with **no** terminal event. | **Survives.** Distinguished *today-reachable* (escape points, SSE disconnect C2) from *latent-primary after #105*. |
| 7 | **Planner child cancellation (H10/N7)** | "Is an independent child cancellation reachable in production?" The router cancels only its own subtasks and re-raises the caller's cancellation (`model_router.py:466-485`); `AdapterRuntime` catches `Exception` only; no component cancels one `_dispatch_module` task. A `CancelledError` could still surface from an inner awaited task cancelled by another owner. | **Downgraded:** VERIFIED *contract hole* (the code mishandles a value `gather` can return); production reachability **UNVERIFIED / low**. Not a driver of the #105 boundary. |
| 8 | **Voice-thread finding (H17)** | "Maybe `keyboard` calls back on the main thread on some platform." Installed 0.13.5 source and docs say separate thread on every backend that uses `GenericListener`. `main.py` passes `_handle_voice` directly as `on_query`; no `call_soon_threadsafe` bridge exists. P13 reproduces the exact failure. | **Survives for the mechanism**; the live hotkey→microphone path needs root/hardware and was **not** run (UNVERIFIED end-to-end). Only active when voice is enabled. |
| 9 | **"`resume()` has no production caller"** | Repo-wide search of `.py` (including `learning/`, `scripts/`, `install/`), string/`getattr` forms, and the API route table. | **Survives**: callers exist only in tests and docs. Re-confirm at the next baseline. |
| 10 | **Reachable-today vs future token behaviour** | The B2d tests inject the token through `request.payload["context"].cancellation_token`; production fills that slot with a `ContextMemory` that has no such attribute (`planner.py:321-329`, `model_router.py:125-133`). | **Survives**: B2d behaviour is *latent* until a token is actually threaded through `CapabilityRequest`; conflating its tests with production reachability would overstate it. |

**Corrections made to this study during review** (kept for auditability): (i) an earlier draft said no consumer reads `worker.*` events — `EvaluatorWorker` does (N18, §11.1 reworded); (ii) probe P6's second case initially claimed to hit the workflow terminal event — it hits the *per-invocation* `execution.completed`; P6b was added to target the workflow-level event by (type, source); (iii) the first P12 run joined the foreign thread on the loop thread, which masks the missed wake-up — it was rerun with an idle loop (0.3 s → 3.0 s); (iv) P11's first completion flag was set in a `finally` and so reported cancelled children as finished — fixed to set only on normal completion; (v) the claim about registered adapters was taken from project notes and replaced by a direct citation (`main.py:282-287`); (vi) one citation range for the "never raises" docstrings was corrected (`runtime.py:254,317,479`).

---

## 18. Owner decision register (all PENDING except **D-14, DECIDED by the owner on November 3, 2026**; no design statement below is ACCEPTED)

| ID | Decision | Options | Recommendation (PROPOSED) | Needed for |
|---|---|---|---|---|
| **D-01** | Native task-cancellation behaviour | (a) status quo: swallow → failed result; (b) propagate `CancelledError` after bounded cleanup; (c) return a cancellation outcome | **(b)** | #105 |
| **D-02** | Domain/token cancellation result semantics (carrier) | (a) existing `WorkerResult.execution_detail`(`FailureType.CANCELLED`) + `NodeStatus/ExecutionStatus.CANCELLED` + `execution.cancelled`; (b) new field on `WorkerResult`; (c) an OCBrain exception class | **(a)** — no second result contract | C-g, not #105 |
| **D-03** | Typing of cancellation cause | (a) extend `CancelReason`; (b) separate `CancelCause` enum; (c) keep strings | **(a)** (rev 2, owner review) — extend the existing `CancelReason`; the token retains the typed cause and exposes its display string separately; reconcile `hard_deadline` vs `execution hard_deadline`, and never treat the latter as a caller cancellation; string callers stay supported during migration | C-g / B2d |
| **D-04** | Child and sibling cancellation | (a) none beyond owned children; (b) cancel-siblings-on-first-cancel; (c) configurable required/optional children | **(a)** now | none today |
| **D-05** | Cancellation event semantics | (a) terminal notification only, emitted by the workflow finalizer after the cancelled node/worker stack has unwound (§21.2 A); (b) request event + terminal; (c) status-quo request-as-`record_failure` | **(a)**; a request is never recorded as terminal failure; (b) only when an external request API exists | C-d |
| **D-06** | Transport disconnect and shutdown | per path: non-stream `/query`, SSE `/query`, `/executions/*/events`: *detach-only* vs *cancel operation*; shutdown: add `timeout_graceful_shutdown`? drain policy? | explicit per-path table; no change to non-stream behaviour (C1) without a durable-operation decision; set an explicit shutdown timeout | C-f; not #105 |
| **D-07** | May any cancellation be retried | (a) never; (b) only via an explicit per-node policy | **(a)** for native; **(b)** reserved for tokens, default off | #105 (native) |
| **D-08** | Authorization for intentional resume | (a) `CANCELLED` nodes never auto-reset; (b) `resume()` takes an explicit authorization argument; (c) separate `restart()` | **(a)+(b)**; crash-interrupted `RUNNING` keeps ADR-KERNEL-03 behaviour | first production `resume()` caller |
| **D-09** | Cancel arriving after `_run()` returned | (a) state `COMPLETED` + `worker.cancelled{phase:post_run}` + propagate; (b) shield the completion emission | **(a)** (no detached tasks) | #105 |
| **D-10** | What `workflow.completed` consumers (the Evaluator) see for a cancelled workflow | (a) emit nothing; (b) emit `workflow.completed{success:false,cancelled:true}` and make the Evaluator recognise cancellation | **(b)** (rev 2, owner review): it is already the terminal lifecycle event for failed workflows and carries `success` separately; the Evaluator guard belongs to C-g because only the token path reaches it (§21.4) | C-d (event), C-g (Evaluator guard) |
| **D-11** | Does #105 include the minimum lifecycle companions | (a) C-c only; (b) C-a, C-b, C-e prerequisites + C-c + C-d | **(b)** (§11.3) | authorization of #105 |
| **D-12** | Gate for accepting ADR-KERNEL-09 | (a) accept on contract alone; (b) accept only after C-f and C-g are *scheduled* | **(b)** — "scheduled" means for each: written scope, accountable owner, dependencies and verification criteria, not merely an open issue; neither blocks the #105 merge (rev 2) | ADR |
| **D-13** | Late-result policy: a result arriving after a node is terminal | (a) ignore for status, log; (b) record as a separate history entry without rewriting status; (c) allow overwrite (status quo) | **(a) or (b)**, never (c) — but absorbing terminal states must land **together with** the watchdog request semantics (C-g), not before (§9.5) | C-d (native finalization), C-g (general guard) |
| **D-14** | Sequencing of C-b/C-d against open PR #81 (DEBT-028: per-instance lock at `resume()`; rewrites `GraphExecutionWatchdog.stop()` and ~417 lines of `core/workflow/runtime.py`) | (a) PR #81 lands first and C-b/C-d rebase on it; (b) C-b/C-d land first; PR #81 is then reassessed against the resulting `main`; only surviving, justified DEBT-028 changes are rebased and independently reviewed; no automatic merge approval; may be closed as superseded; (c) fold the overlapping hunks | **DECIDED — (b)** (owner confirmation, Nov 3, 2026; six conditions and precise reasons in §21.9). Sequencing policy only: ADR-KERNEL-09 stays PROPOSED; C-b, C-d, PR #81 implementation and every merge remain **unauthorized** | sequencing |

No issue, label, assignee or milestone was changed to record these.

---

## 19. Open evidence gaps and how each would be closed

| Gap | Why it stays open | What would close it |
|---|---|---|
| Provider-side termination (local stream closed ≠ remote stopped) | needs the server's own view | a server-side counter/log (e.g., token-generation rate or request-in-flight metric on the model server) sampled after a client close, per provider |
| Live voice path | needs OS keyboard hook + microphone, root on Linux | a manual run with voice enabled on the supported OS, with `PYTHONASYNCIODEBUG=1` |
| Multi-module SSE disconnect | only the single-module and non-stream paths were probed | extend C2 with a two-module fake classifier |
| Reachability of an independently cancelled Planner child (H10) | no producer found | audit of every awaited inner task under `_dispatch_module`, or a fault-injection test |
| All-children-cancelled output of `PlannerWorker` | inferred from `merger.py`, not run | extend P11 |
| N4 (`attempts` over-count) | read, not observed | read `WorkflowNodeState.attempts` after a token-cancelled retry |
| N17 `wait_for` swallowed cancel | timing-dependent | deterministic loop-iteration harness, or move to `asyncio.timeout()` |
| Behaviour on Python ≥ 3.13 | explicitly out of baseline | re-run P-series when the baseline moves |
| Windows/macOS signal and keyboard behaviour | probes ran on Linux | CI or manual runs |
| Load/concurrency effects (many concurrent executions, queue starvation) | single-request probes only | stress harness after the contract is accepted |
| End-to-end caller view of a token-cancelled workflow on the K4.2 path (N8) | inferred from `orchestrator.py:532` + FZ-01 | `Orchestrator.handle()` probe with a graph deadline; owned by FZ-01 |
| `learning/scheduler.py` task supervision | not audited | targeted review |

---

## 20. Implementation sequencing recommendation (does **not** authorize execution)

1. **Owner review** of this study and ADR-KERNEL-09; decisions D-01, D-05, D-07, D-09, D-10, D-11 are the minimum for #105; D-12 decides acceptance gating.
2. **C-e** — add Python 3.11 to the CI matrix (infrastructure; independent).
3. **C-a** and **C-b** — two small PRs, independently reviewable, each with its T-R1 / T-G1–G4 tests; behaviour on today's paths unchanged.
3a. **D-14 coordination** — **decided order (D-14, owner, Nov 3 2026; §21.9): C-b and C-d land before PR #81 is reassessed**; PR #94 (interface/api.py, main.py) is coordinated with C-f/D-06. The *start* of C-b/C-d still needs its own separate authorization — D-14 authorizes the order only.
4. **C-c + C-d** — one PR, two commits (worker lifecycle; `_run()` `try/finally` + finalization + terminal event), with the full T-W/T-R/T-G/T-E1–E4 and T-E3a–c, T-R14–R15, T-V1 set passing on 3.11 and 3.12.
5. **C-f** (SSE/API finalization) and **C-g** (token-path outcome, interruptible backoff, typed cause) as separately scoped packets; **B2d** re-reviewed only after C-g's token/cause design.
6. Separately scheduled, not gated by #105: voice thread scheduling (H17), `CancellationToken` thread-safety/docstring (H16), shutdown timeout (D-06), `KNOWN_ISSUES.md` entries, `ADR_INDEX.md` KERNEL-08 row (D9).

Each step needs its own explicit owner authorization.

---

## 21. Review reconciliation (revision 2, November 3, 2026)

An owner-side review of revision 1 (study, ADR draft, index diff, probe methodology) concluded: *C+ direction supported; ADR-KERNEL-09 not approvable as worded; #105 implementation not authorized.* This section records how each point was checked and what changed. Nothing here accepts a decision or authorizes work.

### 21.1 Baseline and in-flight reconciliation (verified, not taken from the review)

| Check | Result | Evidence |
|---|---|---|
| Current `main` | `2491ae469edd6ef1267a14604c4f8f40d698f7ea` (PR #106 merge, Nov 1 2026); 34 commits and 15 files beyond `ed3d141` (CTX-AUTH-002 closure: `core/cognitive/intent.py`, `core/cognitive/planner.py`, CTX-AUTH tests/harness, ADR-KERNEL-06/08, `ADR_INDEX.md`, `CURRENT_STATE.md`, `KNOWN_ISSUES.md`) | `git ls-remote`; `git diff --stat ed3d141 2491ae4` |
| Audited cancellation-path sources | **identical blobs at both SHAs** for all 31 files compared (worker base, execution/workflow runtimes, graph, watchdogs, progress, cancellation, planner, evaluator, router, adapters, API, orchestrator, event stream/bus, `main.py`, voice, `ci.yml`, `requirements.txt`, `pyproject.toml`). `core/workflow/result.py`, listed in the original mission, **does not exist** at either SHA; `WorkflowResult` is defined at `core/workflow/runtime.py:195` | `git rev-parse <sha>:<path>` |
| Direct re-test at `2491ae4` | the four cancellation-adjacent test files: **61 passed (3.11.15)**; probes P1, P3, P6, P7 and C5 reproduce identically | throwaway copy `/tmp/probe/repo2` |
| PR #108 | **Draft**, unassigned, no reviewers; 19 commits; documentation only (`README.md`, `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, a branch/PR ownership register); states that #104 is router cleanup and **not** end-to-end cancellation, and that #105 is OPEN and unassigned; "no ADRs changed". It therefore partly supersedes this study's D10 observation (it adds cancellation-boundary wording to `KNOWN_ISSUES.md`/`CURRENT_STATE.md`) *if merged* | PR page; branch diff |
| Issue #105 | OPEN, unassigned (listed as open on the PR #108 page) | PR page |
| ADR numbering | `ADR_INDEX.md` at `2491ae4` has a KERNEL-08 row (added by PR #106) and an updated "Last synchronized" line; **`ADR-KERNEL-09` is still free** — all 111 remote branches rescanned, none claims it | `git grep` over every remote ref |
| B2d / WIP FZ-02 branches | unchanged heads (`b44bddf`, wip branch); still read-only candidate evidence | `git rev-parse` |

**In-flight work that overlaps future implementation** (all-branch scan of 21 files: cancellation path, `ci.yml`, ADR index). *None changes a finding; several change sequencing.*

| Branch / PR | Overlap | Consequence |
|---|---|---|
| `fix/debt-028-workflow-runtime-concurrency-lock-…` (PR #81, DEBT-028; head `647b63e`, merge-base `f13bfde`) | `core/runtime/watchdog.py` (+62) and `core/workflow/runtime.py` (417 changed lines; a per-instance `_RefCountedLock`) | **Direct collision with C-b and C-d.** Its `stop()` rewrite already tries to preserve caller cancellation using `asyncio.shield` and `cancelling()` accounting, then drains the child in a loop that *repeated caller cancellations cannot interrupt* — read, **not** run or reviewed; on its face that loop is unbounded and would not satisfy T-G4. The lock adds a new cancellation-sensitive await (acquisition) in front of `_run()`. → **D-14** *Rev 2.1 (verified): head `647b63e`, merge-base `f13bfde`, **13 commits ahead / 96 behind `2491ae4`**; its lock (`_lock_instance`, docstring: "Serialize concurrent resume() calls") is applied **only at `resume()`** (`runtime.py:411` on the branch); `KNOWN_ISSUES.md` DEBT-028 on `main` keeps the guard OPEN / DEFERRED / dormant until a production `resume()` entry point exists (§21.9). The owner reports (Nov 3) the PR is open, unmerged, non-mergeable, with zero submitted reviews and zero review threads — owner-reported, not independently re-read by this study.* |
| `fix/debt-025-api-auth-boundary-oct2026` (PR #94) | `interface/api.py`, `main.py`, `ci.yml`, new auth modules | Touches the same surfaces as C-f/D-06 and `main.py`'s Uvicorn config. **The C-series probes assume today's `X-OCBrain-Local` gate and would need the bearer token once #94 merges.** |
| `fix/ci-gate-r1-structured-report-oct2026`, `fix/ci-gate-r1a-hardening-oct2026` (PR #107 is a diagnostic, NOT FOR MERGE), `repair/debt-012-*` | `.github/workflows/ci.yml` | Coordinate C-e (3.11 in the matrix) with these; DEBT-012 also governs test isolation (T-Z2) |
| `fix/import-root-containment-oct2026` | `interface/api.py` | minor overlap with C-f |
| B2d, `wip/fz02-b2c-…` | `adapter_runtime.py`, `model_router.py`, `watchdog_decision.py` | as in §12 |
| `archive/*`, `feature/` / `integration/capability-foundation-mission1`, `security/freeze-reconciliation-sep2026` | old integration lines touching `runtime.py`, `orchestrator.py`, `main.py` | stale/competing; listed in PR #108's ownership register; **not assessed** |

### 21.2 Corrections accepted

**A. Terminal-event timing — accepted; wording was self-contradictory.** Revision 1 said the event is emitted "after the cancelled task's stack has unwound" *from a `finally` inside `_run()`*. A `finally` runs while the task is still executing; what has unwound is the node/worker call stack **beneath** it. Corrected everywhere (§8.1, §9.2, §9.3, §11.1; ADR §2.5): the owning workflow finalizer emits the terminal notification after the node/worker stack has unwound and immediately before the task propagates cancellation; the payload field `termination:"task_unwound"` became `observed:"node_stack_unwound"|"cooperative_stop_acknowledged"|"unknown"` and no value claims the *task* terminated. Evidence that the *whole* task has terminated would require an outer supervisor awaiting an owned workflow task — a different ownership architecture, not proposed.

**B. Best-effort broadcast does not guarantee SSE termination — accepted; this was the more serious omission.** Revision 1's T-E3 allowed "terminal state readable via snapshot" as sufficient. Probe **C5** (real Uvicorn, real subscriber): the terminal event was **persisted (1 row)**, the graph snapshot read **`cancelled`**, and the subscriber **never terminated**. Source: `ExecutionRegistry.events()` is a bare `while True: yield await queue.get()`, the queue is fed only by `_on_event` through `EventStream` broadcast, and nothing replays the store or consults graph status. New invariant (ADR §2.5): *terminal graph finalization and subscriber termination must not depend exclusively on a successful `EventStream` broadcast; the terminal state stays inspectable.* The mechanism is an implementation decision (a registry-level completion signal set by the finalizer, a snapshot-aware stream termination with a bounded wake-up, or both). T-E3a–c test the **actual HTTP subscriber** for *never persisted*, *persisted-but-not-broadcast*, and *emitter raises*. `core/runtime/execution_graph.py` (the registry) therefore joins C-d's touched files.

**C. Terminal-state transition policy — accepted.** §9.5 records the table and one additional point the review's table does not state: the absorbing-state guard must land *with* the watchdog's request semantics (C-g), otherwise P8's late success is pinned as `FAILED`. #105 implements monotonicity inside its own finalization routine only.

### 21.3 Bounded cleanup — the `asyncio.timeout()` recommendation was too blanket

Accepted. `asyncio.timeout()` bounds an operation by cancelling the *current* task and translating its own cancellation into `TimeoutError`; it is not by itself a shielding or repeated-cancellation strategy, and the study never proved that every kernel `wait_for` must change. Revision 2 states the **requirement** instead of a primitive: cleanup must (1) be time-bounded, (2) leave external cancellation observable (a new cancel during cleanup propagates), and (3) leave no detached task behind. The mechanism is chosen in the implementation and proven by T-W4, T-W5, T-G2, T-G4. N17 (the 3.11 `wait_for` return-on-race) stays recorded as a *hazard in cancellation-sensitive paths*, with no blanket replacement. The review's reading of Python's guidance (clean up in `try/finally`, then propagate `CancelledError`) is the study's own C+ element 1.

### 21.4 D-10 and the Evaluator — the review is right on the verdict, and the path split sharpens it

Revision 1 recommended emitting nothing. Revision 2 recommends **`workflow.completed{success:false, cancelled:true}`**: `workflow.completed` is already the terminal lifecycle event for failed workflows (`runtime.py:673`), with `success` carried separately, so uniform coverage is more informative than a missing event. A further source reading changes *where* the Evaluator guard belongs: on the K4.2 path `Orchestrator.handle()` invokes `EvaluatorWorker` and then `ReflectionWorker` after **any returned** `WorkflowResult` (`orchestrator.py:573-592`; no `success` condition), and the Evaluator derives `tool_success_rate` from `worker.completed`/`worker.failed` counts (N18) and writes an L1 record.

* **Native cancellation (#105):** the `CancelledError` unwinds `handle()` before that block, so the Evaluator is **not** reached — T-V1 asserts this. Today, because the swallowed cancel lets the workflow return a result, the Evaluator *does* run.
* **Token cancellation (C-g):** the failed `WorkflowResult` *is* returned, so the Evaluator and Reflection run on partial work today (VERIFIED by reading; not probed end-to-end). The "Evaluator recognises cancellation" guard (T-V2) is therefore **C-g scope, not #105 scope** — this keeps #105 from silently widening into `core/workers/evaluator.py`, which is the one place the review's fourth acceptance requirement could otherwise have enlarged it.

### 21.5 Acceptance requirements added

1. Terminal-event delivery against the actual HTTP subscriber, for *never persisted* and *persisted-but-not-broadcast* (T-E3a–c; C5 is the baseline failure).
2. Terminal-transition monotonicity (T-R14).
3. No false completion event from `ExecutionRuntime.invoke()` on its cancellation path (T-R15; C-a wording).
4. Evaluator exclusion (T-V1 for #105; T-V2 for C-g).

### 21.6 Reviewer-recommended dispositions D-01…D-12 — concurrence

These are **recommended inputs, not recorded decisions**; nothing is ACCEPTED.

| ID | Review's recommendation | This study (rev 2) |
|---|---|---|
| D-01 | propagate after bounded cleanup | concur |
| D-02 | reuse existing types with explicit downstream discrimination | concur; every consumer must test the discriminator before reading `success` (deferred to C-g) |
| D-03 | extend `CancelReason` | **adopted** (D-03 row amended) |
| D-04 | ownership-based only | concur |
| D-05 | terminal notification; request never terminal failure; amend wording | **adopted** (§21.2 A) |
| D-06 | keep separate; preserve path behaviour in #105 | concur — note current behaviour is path-dependent (C1 vs C2) and PR #94 will change the API surface |
| D-07 | native never; token explicit and off by default | concur |
| D-08 | cancelled work not auto-resumed; explicit authorization | concur; record as a future safety invariant now |
| D-09 | `COMPLETED` retained, post-run cancellation recorded | concur |
| D-10 | emit `workflow.completed{…cancelled:true}`; Evaluator recognises cancellation | **adopted**; Evaluator guard assigned to C-g (§21.4) |
| D-11 | C-a, C-b, C-e then C-c+C-d | concur; **plus D-14 (PR #81 coordination)** |
| D-12 | accept after C-f/C-g are scheduled with accountable ownership | **adopted**; "scheduled" = scope + owner + dependencies + verification criteria |
| new | — | D-13 late-result policy; D-14 coordination with PR #81 |

### 21.7 Evidence provenance and what the review could not see

The review noted that it received the probe *methodology* but not the probe files. The scripts (`probes_a.py`, `probes_b.py`, `probes_c.py` — now including **C5** — and `probe_reason.py`), a README and the raw outputs are delivered as attachments (not committed); the review independently checked the *source*, not the probe runs. Probe results remain experimental evidence from this study's single runs (§4). C5 and the re-runs at `2491ae4` were added in this revision.

### 21.8 Unchanged

The C+ direction, the three-dimension model (§9.4 corrections stand), the #105 boundary C-a, C-b, C-e → C-c+C-d, the exclusions of §12, and the PROPOSED status of ADR-KERNEL-09. No *design statement* was accepted and no implementation authorized by this revision; the only owner decision recorded is **D-14 (sequencing, DECIDED)**, §21.9.


### 21.9 D-14 — sequencing decision (input in revision 2.1; **DECIDED** by the owner, recorded in revision 2.2, November 3, 2026)

A second owner-side review recommended **D-14 option (b): C-b and C-d first; PR #81 reassessed afterwards.** Each factual premise was re-checked against live state before being recorded (table below). **The owner then confirmed and adopted option (b): D-14 is DECIDED** (confirmation of Nov 3, 2026). This decision authorizes the **sequencing policy only**: ADR-KERNEL-09 remains PROPOSED, and C-b, C-d, PR #81 implementation and all merges remain unauthorized. No GitHub state was changed by this study or by the recording of the decision.

**Corrections the owner explicitly accepted:** (i) *T-G4 / watchdog cleanup* — the precise defect in PR #81's drain loop is that it has **no deadline** and **consumes subsequent caller cancellations once drain mode begins**, so cancellation cannot interrupt potentially prolonged cleanup (not that repeated cancellation extends the loop); (ii) *lock-release cancellation safety* — the `await` inside the lock's `finally` creates a potential reference-count leak if another cancellation interrupts acquisition of the guard lock; this is a **source-level finding that requires a deterministic regression test** (injected await boundary) before any such lock can land; (iii) the sixth condition below.

| Premise | Re-check | Result |
|---|---|---|
| PR #81 is far behind `main` | `git rev-list --left-right --count origin/main...origin/fix/debt-028-…` | **96 behind / 13 ahead**, merge-base `f13bfde`, head `647b63e` — confirmed |
| It overlaps directly | `git diff --stat origin/main...<branch>` | `core/runtime/watchdog.py` (+62), `core/workflow/runtime.py` (417 changed lines), `tests/test_workflow_runtime.py` (+396), `KNOWN_ISSUES.md` — confirmed |
| Its `stop()` drain loop conflicts with the bounded-cleanup requirement | read `core/runtime/watchdog.py:161-165` on the branch | **confirmed, with a precision**: the loop `while not task.done(): … await asyncio.shield(task) … except CancelledError: continue` has **no deadline** and **absorbs every later caller cancellation** (only the first is re-raised, after the drain). Its length is bounded only by the watchdog task finishing — not by *repeated cancellation extending it*, as the shorthand "repeated cancellation can keep the loop running" suggests. The defect is "unbounded and uninterruptible while the child is slow", which is exactly what T-G4 rejects. Read, not run |
| It does not meet the current DEBT-028 acceptance wording | `KNOWN_ISSUES.md` at `2491ae4`, DEBT-028 | **confirmed**: the guard must coordinate at the actual deployment boundary; an in-memory lock on one `WorkflowRuntime` cannot stop a second process; the in-process-vs-durable decision belongs in the same change that introduces the first production `resume()` entry point; "no code change is warranted before then"; status OPEN / DEFERRED / dormant. PR #81's lock is process-local and applied at `resume()` only |
| Consistency with this study | H18 | consistent: `resume()` has **no production caller** anywhere in the repository, so a `resume()` lock protects no reachable path today |
| Additional point for the reassessment (not in the review) | PR #81 `_lock_instance` | its `finally` re-acquires `_instance_locks_guard` with an `await` while possibly already cancelled; a **second** cancellation there would skip the refcount decrement and leak the entry (INFERRED from reading; not run). Any lock acquisition placed in front of `_run()` is a new cancellation-sensitive await and must be covered by the same bounded-cleanup acceptance tests |

**D-14 record (DECIDED — sequencing only):** *Option (b). When implementation is separately authorized, C-b and C-d establish the accepted cancellation and cleanup contract on the then-current `main` before any PR #81 change is considered. PR #81 is then reassessed; if still justified it is rebased onto that `main`, and the rebase is not approval to preserve or merge its implementation.* Conditions: (1) PR #81's `stop()` is not accepted as the cancellation-cleanup solution — its drain loop must be replaced or independently proven against the final contract; (2) its `WorkflowRuntime` changes are reviewed semantically, change by change, against the final C-b/C-d implementation; (3) the in-memory lock is not accepted as satisfying the DEBT-028 deployment-boundary requirement; (4) DEBT-028 stays OPEN / DEFERRED / dormant unless its own acceptance requirements are independently met; (5) if no production `resume()` entry point is introduced and no implementation requirement remains, PR #81 may be closed as superseded rather than merged; (6) any lock introduced ahead of `_run()` must demonstrate cancellation-safe acquisition, execution **and** release (T-R / T-G style deterministic tests) before it lands. Owner-reported live recheck (Nov 3): PR #81 is open, unmerged and non-mergeable, 96 commits behind and 13 ahead, with zero submitted reviews and zero review threads; DEBT-028 remains OPEN / DEFERRED / dormant on `main` (the 96/13 counts and the DEBT-028 record were also re-verified by this study above).

The cancellation contract (an existing runtime-correctness concern) and DEBT-028 (a deferred concurrency requirement whose shape depends on the future deployment/recovery model) are **not coupled** merely because their candidate implementations edit the same files. Scope: sequencing only — no change to the #105 boundary, the exclusions of §12, or the PROPOSED status of ADR-KERNEL-09. No GitHub state was changed.

---

## 22. Kernel-freeze classification (reviewer-proposed input; PROPOSED; owner decides — no FZ status is changed here)

| Workstream | Proposed classification | Rationale |
|---|---|---|
| #105 native cancellation | pre-freeze blocker | violates execution correctness; can produce false success (P1) |
| C-a / C-b cleanup | pre-freeze prerequisite | required for safe propagation |
| C-c / C-d lifecycle | pre-freeze requirement | establishes terminal execution correctness |
| C-e Python 3.11 CI | pre-freeze verification requirement | the declared minimum is untested |
| C-g token/watchdog outcome | pre-freeze blocker **for claiming cancellation is resolved** | the graph watchdog is a live production producer of token cancellation (P8, P9); not required for the #105 merge |
| C-f SSE finalization | required before the public cancellation lifecycle is declared complete | streaming finalization is inconsistent (C2) |
| B2d | separate follow-up | needs its own token/cause review (N6) |
| Resume-authorization implementation | post-freeze **only if** `resume()` stays unreachable and the limitation is documented | no production caller (H18) |
| Voice callback; `CancellationToken` thread-safety | separate work | independent threading defects (H16, H17); `run_coroutine_threadsafe` is the documented bridge for the voice path |

PR #108 already states that "end-to-end cancellation and terminal outcome semantics remain open" under FZ-02; this study does not edit that wording.

---

## Appendix A — References

* Python 3.11 documentation: Coroutines and Tasks (`asyncio-task`), Synchronization Primitives (`asyncio-sync`), Developing with asyncio (`asyncio-dev`) — https://docs.python.org/3.11/library/
* AnyIO, *Cancellation and timeouts* — https://anyio.readthedocs.io/en/latest/cancellation.html
* Temporal, *Cancellation and Termination* — https://docs.temporal.io/encyclopedia/workflow/cancellation-and-termination; *Request Cancel for an Activity* — https://docs.temporal.io/activity-operations/request-cancel
* `keyboard` — https://github.com/boppreh/keyboard (installed 0.13.5 source `__init__.py:620`, `_generic.py:38,42`)
* Uvicorn 0.54.0 `uvicorn/server.py` (installed)
* Repository: PR #104 https://github.com/1h0lde4/ocbrain-v4.1/pull/104; issue #105 https://github.com/1h0lde4/ocbrain-v4.1/issues/105; `ADR_KERNEL_02`, `ADR_KERNEL_03`, `ADR_INDEX.md`, `KERNEL_ARCHITECTURE_v1.0.md` §7.1/§7.4/§8, `k4_2_architecture_hardening_review.md` §6, `K2_IMPLEMENTATION_PLAN.md:144`, `KNOWN_ISSUES.md` (FZ-01, DEBT-012), B2d handoff `docs/handoffs/fz02_b2d_latent_token_cancellation.md` (on the follow-up branch)

## Appendix B — Environment and commands

* Study checkout: `/home/claude/ocbrain` on `study/cancellation-contract-final-gap-oct2026`, based on `ed3d141`; working tree contains only the three documentation changes of this study (uncommitted, unpushed).
* Probe copy: `/tmp/probe/repo` (a `cp -r` of the study checkout taken before the documents were written); venvs `/tmp/probe/v311` (CPython 3.11.15) and `/tmp/probe/v312` (CPython 3.12.3) created with `uv`; installed: aiofiles, aiohttp, beautifulsoup4, click, datasketch, fastapi, feedparser, httpx, pydantic, pytest, pytest-asyncio, PyYAML, requests, rich, scipy, tomli, tomli-w, uvicorn[standard], keyboard (ChromaDB and sentence-transformers were **not** installed; none of the probed modules needed them).
* Baseline tests: `pytest tests/test_b2c_cancellation.py tests/test_execution_watchdog.py tests/test_workflow_runtime.py tests/test_execution_inspection.py -q -x -p no:cacheprovider` → **61 passed** on 3.11.15 and **61 passed** on 3.12.3 (in the throwaway copy).
* Probes: `HOME=/tmp/probe/home /tmp/probe/v311/bin/python probes_a.py|probes_b.py|probes_c.py [id …]`; reason probe `probe_reason.py`; 3.12 re-runs of P1, P3, P7 identical.
* **Revision 2:** second clone `/home/claude/ocbrain-r2` (branch `study/cancellation-contract-final-gap-oct2026-r2`, based on `2491ae4`); throwaway copy `/tmp/probe/repo2` for the `2491ae4` re-runs (61 tests passed on 3.11.15; P1, P3, P6, P7, C5 reproduced). The first-version checkout `/home/claude/ocbrain` (based on `ed3d141`, uncommitted) is untouched.
* **Not run:** the full test suite (DEBT-012), any test touching ChromaDB/sentence-transformers, live provider generation, voice hardware, Windows/macOS, Python ≥ 3.13.
* No file under `core/`, `interface/`, `tests/`, `main.py` or any config was modified; the study checkout was verified clean (`git status --short` empty) after all probes and before the documents were written.
