# ADR-KERNEL-09: Cancellation Contract — native task cancellation, OCBrain-owned cooperative cancellation, and observed termination (DEBT-105 / issue #105)

**Status:** PROPOSED — pending repository owner decision. *Nothing in this record is ACCEPTED, and nothing in it has been implemented.*
**Date:** November 1, 2026; **revision 2:** November 3, 2026 (after owner review — study §21)
**Baseline:** evidence gathered at `main` = `ed3d141e4bbfd0231afb1104d0a7479419f9bbf1` (merge of PR #104); reconciled to current `main` = `2491ae469edd6ef1267a14604c4f8f40d698f7ea` (PR #106) — every audited cancellation-path source file is identical at both SHAs.
**Evidence:** `docs/studies/OCBRAIN_CANCELLATION_FINAL_GAP_STUDY_OCT2026.md` (all citations, probes P1–P15, C1–C5, hypothesis register H1–H20, findings N1–N18, test matrix, and owner decision register D-01…D-12 live there; this ADR does not repeat them).
**Refines / supersedes if ACCEPTED:**
- **Supersedes** the conclusion of `docs/architecture/k4_2_architecture_hardening_review.md` §6 ("Cancellation Semantics — REJECTED … No change needed"). That document is preserved unedited.
- **Amends** `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §7.1 ("never raises") and the §7.4 event mapping (`worker.cancelled` described as "CancellationToken triggered"); notes that the §8 `WorkflowRuntime.cancel()` declaration and `K2_IMPLEMENTATION_PLAN.md` step 6 were never implemented.
- **Refines** `ADR_KERNEL_03_CHECKPOINT_RESUME.md` (the reset of `CANCELLED` nodes to `PENDING`); that ADR is not edited.
- **Does not touch** `ADR_KERNEL_02` (watchdog decision-policy unification — still resolved) or ADR-005 (no automatic rollback — still in force).

---

## 1. Problem

On `ed3d141`, native task cancellation is converted into an ordinary failed `WorkerResult` by `Worker.execute()` (`core/workers/base.py:293-300`); the workflow retries the node and can report `success=True` for a cancelled task (study P1, P10). Where cancellation *does* propagate (three await points today; everywhere once #105 is fixed) the execution runtime skips cleanup, the workflow leaks its graph watchdog, `GraphExecutionWatchdog.stop()` swallows the caller's cancellation, and no code emits the `execution.cancelled` event the API already recognises, so the execution graph stays RUNNING and `/executions/{id}/events` subscribers wait indefinitely (P4–P7, P6b, C3). A separate, supervisor-driven *token* path reports a requested stop as a failed node and a failed execution (P8, P9). The existing primitives are individually present but their composition is unspecified.

## 2. Decision (PROPOSED)

### 2.1 Three dimensions are recorded independently

A stop is described by three orthogonal facts; none may be inferred from another.

1. **Initiation, authority and cause** — a *typed* value (user, parent execution, watchdog stall, watchdog hard deadline, governance, superseded, shutdown, process termination, client disconnect, external caller). Free-form strings are display-only. (Study N6: two incompatible string encodings exist today.)
2. **Delivery / interruption mechanism** — cooperative `CancellationToken`; `Task.cancel()` → `CancelledError`; cancellation of an owned task group; local stream close; provider-specific cancel; subprocess termination; process shutdown. A mechanism **never** proves the stop.
3. **Observed outcome and effect certainty** — returned success; returned ordinary failure; cooperative stop acknowledged; task terminated; cleanup complete/failed/timed out; remote termination *unknown*; side effects *none / committed / unknown*.

The distinctions *request, delivery, acknowledgement, termination, cleanup completion, effect certainty* are carried by existing types and events plus additive payload fields; no enum per concept is introduced.

### 2.2 Native task cancellation (`asyncio.CancelledError`) — Option A semantics

1. It **propagates**. It is never converted into a `WorkerResult`, never retried, never routed to an `error_branch`, never causes successor traversal.
2. Each layer that owns state performs **bounded** cleanup and re-raises: the worker records `CANCELLED` (or keeps `COMPLETED` if `_run()` had already returned) and emits a best-effort `worker.cancelled{phase}`; `ExecutionRuntime.invoke()` clears `WorkingMemory` first (synchronous), in a `finally`, and publishes **no ordinary `execution.completed` runtime event on its cancellation path** (`worker.cancelled` is the record); `WorkflowRuntime._run()` wraps everything from `watchdog.start()` onward in a `try/finally` that stops the watchdog, finalizes the execution graph and emits the terminal event; `GraphExecutionWatchdog.stop()` must not swallow cancellation of its *caller*.
3. "Bounded" is a **requirement, not a primitive**: cleanup must be time-bounded, must leave external cancellation observable (a second cancellation during cleanup propagates immediately), and must leave no detached task behind. The mechanism (`asyncio.timeout()`, a shielded join with a deadline, …) is chosen in the implementation and proven by the acceptance tests; no blanket replacement of `asyncio.wait_for()` is mandated, although the 3.11 `wait_for` return-on-race (study N17) is a recorded hazard in cancellation-sensitive paths.
4. Cancellation is **not a failure**: it does not increment failure counters and is not described as `FAILED`. `WorkerState.COMPLETED` keeps its present meaning ("the invocation returned"); success lives in the event payload.
5. `ExecutionRuntime.invoke()` and `WorkflowRuntime.execute()` are documented as "never raise for worker failure; native cancellation propagates".

### 2.3 OCBrain-owned cooperative (token) cancellation — Option B semantics, deferred

A requested stop observed through the `CancellationToken` is a **distinct, non-failure control outcome**, carried on existing structures — `WorkerResult.execution_detail` (`FailureType.CANCELLED` as the worker→workflow carrier only), `NodeStatus.CANCELLED` / `ExecutionStatus.CANCELLED` (defined, currently never assigned) and the `execution.cancelled` event. Defaults: no retry, no error branch, no successors; the retry backoff is interruptible; the original cause survives; a supervisor timeout (stall, deadline) is **not** relabelled as a caller cancellation. Workers observe a read-only signal; cancel authority belongs to the owning runtime. `FailureType.CANCELLED` stays an attempt-level classification and is not the canonical workflow outcome. *This section's carrier choice is owner decision D-02 and is not part of #105.*

### 2.4 Ownership

A workflow DAG edge, an `ExecutionGraph` parent/child relationship and an HTTP subscriber are **not** task ownership. Ownership exists only where one task creates and awaits another (the workflow task owns the graph watchdog; `PlannerWorker` owns its module tasks; the router owns its provider/consumer/shadow subtasks). Cancelling an owner cancels and **awaits** the owned children. Cancelling a node does not cancel DAG siblings or the parent execution; that is a workflow policy and is not introduced here.

### 2.5 Terminal state and events

1. **Timing.** `execution.cancelled` (already recognised by `interface/api.py`) is emitted **once, by the owning workflow finalizer, after the cancelled node/worker call stack has unwound and immediately before the workflow task propagates cancellation.** It never claims that the workflow *task* has terminated; a fact of that kind could only be established by an outer supervisor awaiting an owned workflow task, which is a different ownership architecture and is not proposed. It is never emitted on a *request*.
2. **Payload (additive).** `execution_id`, `cause`, `mechanism`, `phase`, `observed` (`node_stack_unwound` | `cooperative_stop_acknowledged` | `unknown`), `cleanup` (`complete` | `failed` | `timed_out`), `effects` (`committed` | `none` | `unknown`). Consumers of the `execution.*` family read `execution_id` and the event type only, so additive fields are compatible.
3. **Subscriber termination is independent of broadcast (invariant).** Terminal graph finalization and termination of event-stream subscribers **must not depend exclusively on a successful `EventStream` broadcast.** `EventStream.append()` is persist-then-broadcast and is not an atomic acknowledgement under cancellation (study N10), and `ExecutionRegistry.events()` waits only on an in-memory queue fed by that broadcast; probe C5 reproduced a persisted terminal event, a graph snapshot reading `cancelled`, and a subscriber that never terminated. Whatever mechanism is chosen (a registry-level completion signal, snapshot-aware stream termination with a bounded wake-up, or both), the actual HTTP subscriber must terminate within a bounded interval when the terminal event is *never persisted* and when it is *persisted but not broadcast*, with the terminal state remaining inspectable.
4. **Request ≠ failure.** A watchdog must not record a node `FAILED` (or emit `execution.node.failed`) merely because it *requested* a stop (§2.8).
5. **Second terminal family.** A cancelled workflow emits `workflow.completed{success:false, cancelled:true}` from the same finalizer: `workflow.completed` is already the terminal lifecycle event for failed workflows and carries `success` separately (D-10). `EvaluatorWorker` derives `tool_success_rate` from `worker.completed`/`worker.failed` counts and ignores `worker.cancelled`. On the **native** path the Orchestrator never reaches the Evaluator (`CancelledError` unwinds `handle()` before `orchestrator.py:573-592`); on the **token** path the Orchestrator invokes the Evaluator and Reflection after any returned `WorkflowResult`, so the Evaluator must recognise `cancelled` and must not write an ordinary quality evaluation from partial worker events — that guard is part of the token-path packet (C-g), not of #105.
6. **Best effort, bounded.** Emission is best-effort and bounded; it cannot be the only means by which a stop becomes visible (item 3).

### 2.6 Transport lifecycles are separate

API request task, SSE subscriber, logical workflow operation, provider stream, voice-triggered request, orchestrator background service and application shutdown are different lifecycles. Whether a disconnect cancels the operation, detaches only the subscriber, or does neither is decided **per path** (today non-stream `/query` continues after disconnect; streaming `/query` is cancelled with the response generator; `/executions/*/events` only detaches). That decision (D-06) is **not** made here.

### 2.7 Recovery and effects

Crash-interrupted `RUNNING` nodes keep ADR-KERNEL-03's at-least-once reset. Once `CANCELLED` is actually assigned, resume must distinguish *intentional* cancellation from crash interruption and require explicit authorization before restarting it (D-08); the dormant `resume()` path is not changed by this ADR. No rollback or compensation is introduced (ADR-005); effects of unknown status stay *unknown* until reconciled under the capability contract; closing a local provider stream is never reported as remote termination.

### 2.8 Graph terminal-state transition policy (monotonic per execution attempt)

Terminal statuses are `COMPLETED`, `FAILED`, `CANCELLED`; all others (including `STALLED`) are non-terminal. Native cancellation finalizes the active node and the root as `CANCELLED`, preserves completed predecessors as `COMPLETED`, and leaves nodes that never started `PENDING`. A watchdog *request* is recorded as a request (typed cause), never as `FAILED` or `CANCELLED`; a worker that continues after a request stays `RUNNING` and is not claimed terminated; a worker that later returns a real result takes that outcome with the request retained in the history. A result arriving after a node is already terminal is resolved by an explicit rule (D-13) and never by a silent status rewrite. **Phasing:** an absorbing-state guard in `ExecutionGraph.update()` must not land before the watchdog stops writing `FAILED` for requests; the native-cancellation finalization (#105) is monotonic *within its own routine*, and the general guard belongs to the token-path packet (study §9.5).

## 3. Alternatives considered

| Option | Verdict |
|---|---|
| **A** — re-raise native `CancelledError` only | correct for native cancellation, **not safe alone** (needs §2.2 companions) |
| **B** — return an explicit cancellation outcome | right for token cancellation; cannot represent native cancellation without swallowing it |
| **C / C+** — A for native, B for token, three-dimension record | **recommended** (§2) |
| Token cancellation as `Task.cancel()` of the node task | rejected: loses typed cause, cannot cross thread/process boundaries, hides supervisor timeouts |
| `asyncio.TaskGroup` instead of `gather()` | deferred: changes `PlannerWorker`'s "one module failing must not kill the others" semantics; not a drop-in |
| A new cancellation service / scheduler / third watchdog | rejected: existing `CancellationToken`, `ExecutionContext`, runtimes, graph, `EventStream` and the two watchdogs (shared decision core, ADR-KERNEL-02) suffice |

## 4. Consequences, migration and rollback

* **Behaviour change (for #105 only):** a cancelled workflow task now ends by raising `CancelledError` instead of returning a result; `execute()`'s "never raises" wording changes; `worker.cancelled` carries `phase`; cancellations stop counting as failures. In-repo callers: one (`ExecutionRuntime.invoke`); no test pins the old behaviour.
* **Consumers affected:** `ExecutionRegistry`/SSE (`execution.*`, keyed on `execution_id`), `interface/api.py` terminal predicate, `EvaluatorWorker` (`worker.completed`/`worker.failed` counts and `workflow.completed.success` — it already miscounts returned failures as successes, study N18; it will now see `workflow.completed{success:false,cancelled:true}`, and its cancellation guard is token-path scope), `ReflectionWorker` (consumes the Evaluator's record).
* **Rollback:** the change is delivered as independently revertible units (prerequisite cleanups; worker lifecycle; workflow `finally`/finalization). Reverting the behaviour unit restores the swallow-and-retry behaviour without orphaning the prerequisites, which are harmless on today's paths.
* **Documentation:** the amendments listed in the header are applied by reference from this ADR when accepted; historical documents are not rewritten.

## 5. Verification

The acceptance matrix is §13 of the study (T-W*, T-R*, T-G*, T-P*, T-E*, T-X*, T-V*, T-Z*), including the revision-2 requirements: subscriber termination tested against the **actual HTTP subscriber** for *never persisted* and *persisted-but-not-broadcast* terminal events (T-E3a–c), terminal-transition monotonicity (T-R14), no ordinary completion event from `invoke()` on cancellation (T-R15), and Evaluator exclusion (T-V1 native; T-V2 token path). It must run on **Python 3.11 and 3.12** (CI currently exercises 3.12 only) with config/data isolation (DEBT-012), using deterministic await-boundary injection rather than sleep-based timing. Provider-side termination, live voice and multi-module SSE disconnect remain UNVERIFIED until the gaps in study §19 are closed.

## 6. Out of scope (separate packets, not authorized by this ADR)

DEBT-028 instance locking (open PR #81; deployment-boundary requirement per `KNOWN_ISSUES.md`); B2d token propagation into `AdapterRuntime`/`ModelRouter` (including the router's unconditional training/promotion recording); provider-side remote cancellation; a workflow cancel API; client-disconnect and shutdown policy; checkpoint/resume redesign; generalized parent/child hierarchy; compensation/rollback; new identity/idempotency architecture; the voice-callback thread defect; `CancellationToken` thread-safety.

## 7. Pending owner decisions

D-01 native behaviour · D-02 token-outcome carrier · D-03 typed cause (recommended: extend `CancelReason`) · D-04 child/sibling policy · D-05 terminal-only vs request events · D-06 disconnect/shutdown · D-07 retry of cancellation · D-08 resume authorization · D-09 post-`_run()` cancellation · D-10 `workflow.completed{cancelled}` and Evaluator guard (recommended: emit, guard in C-g) · D-11 minimum companions in #105 · D-12 acceptance gating ("scheduled" = scope, accountable owner, dependencies, verification criteria) · **D-13** late-result policy · **D-14 — DECIDED (owner, 2026-11-03; sequencing only)** — sequencing against open PR #81 (DEBT-028; a process-local `resume()` lock that also rewrites `GraphExecutionWatchdog.stop()` and restructures `core/workflow/runtime.py`): C-b and C-d land first, once separately authorized and independently reviewed; PR #81 is then reassessed against the resulting `main`, any surviving change is rebased and independently reviewed, there is no automatic merge approval, and it may be closed as superseded if DEBT-028 stays dormant. Conditions: (1) its `stop()` drain loop — no deadline, and it consumes later caller cancellations once draining — is not accepted as the cleanup solution; (2) its `WorkflowRuntime` changes are reviewed semantically against the final C-b/C-d implementation; (3) its in-memory lock does not satisfy the DEBT-028 deployment-boundary requirement; (4) DEBT-028 stays OPEN / DEFERRED / dormant unless its own acceptance requirements are independently met; (5) closure as superseded is allowed if no production `resume()` entry point is introduced; (6) any lock ahead of `_run()` must demonstrate cancellation-safe acquisition, execution and release, including a deterministic regression test for the reference-count leak when a second cancellation interrupts the `finally` that re-acquires the guard lock (study §18, §21.9). The owner review's other recommended dispositions are inputs; **none of them is recorded as a decision — D-14 is the only decided item, and it decides sequencing only.**

## 8. Conditions to reopen once ACCEPTED

A verified contradiction in the code or tests; a dependency change that alters cancellation semantics (Python baseline, Starlette/Uvicorn shutdown behaviour, `keyboard`); a governance or security finding; a higher-priority architectural authority; an explicit owner request.

## 9. Status history

* 2026-11-01 — PROPOSED (study draft; not reviewed, not accepted).
* 2026-11-03 — revision 2 after owner review: terminal-event timing corrected (§2.5.1); subscriber-termination invariant added (§2.5.3); graph transition policy added (§2.8); bounded-cleanup recommendation restated as a requirement (§2.2.3); D-03/D-05/D-10/D-12 amended; D-13, D-14 added. **Still PROPOSED; not accepted; no implementation authorized.**
* 2026-11-03 — revision 2.1: D-14 sequencing recommendation recorded as an input (C-b/C-d before any PR #81 reassessment; study §21.9). No other change; still PROPOSED.
* 2026-11-03 — revision 2.2: **D-14 DECIDED by the owner** (option (b); sequencing policy only; six conditions preserved; T-G4 explanation corrected to "no deadline, and consumes subsequent caller cancellations once draining"). **ADR-KERNEL-09 remains PROPOSED; C-b, C-d, PR #81 implementation and all merges remain unauthorized.**
