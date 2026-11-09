# Verification 3C-B: Q4-b trigger boundary of D6

Oct 18, 2026 · @Moncif

**Status.** Analysis only; nothing here is accepted. Q2-a remains a candidate. No enum, lifecycle, schema, contract, ADR or implementation change is authorized, and D1–D10 and ODI-3C-B-01/02/03 are unchanged.

**Revision 2 (2026-10-29).** Sections 1–10 are unchanged from revision 1. Sections 11–16 were added after the runtime audit and the source-recovery check; they record the audit findings, the D1 disposition, the missing-source register, the closure matrix and the residual blockers. Revision 2 accepts no decision and authorizes no implementation.

**The answer in brief.** D6 and master §104-J establish a pairing for a verifier crash: a lifecycle or execution failure and the epistemic result UNVERIFIABLE, never PASS. They do not establish the converse, and they do not say that a timeout, tool failure or budget exhaustion produces the same pair. The built contracts enforce something narrower and differently shaped. Q4-b is therefore not a choice between definitions of “crash”. It is three questions: what triggers the rule, at what level a failure is classified, and which consequences are mandated and which are still undecided.

**Five findings.**

1. **D6 gives a pairing, not its full semantics.** For a crash, both facts are recorded. UNVERIFIABLE without a crash is also valid, as a successful abstention.
2. **The built rule is narrower and differently shaped.** A declared execution failure requires UNVERIFIABLE. There is no FAILED lifecycle field, UNVERIFIABLE does not require a failure, and a crash that happens before a result is built triggers no check at all.
3. **The mapping for the other three causes has no ratified source.** The built code says its “execution failure to UNVERIFIABLE” mapping cites no architectural source. D6 and §104-J now supply one for a crash only. For timeouts, tool failures and budget exhaustion it remains an implementation judgment, while D7 says “as appropriate” among three non-conclusive verdicts.
4. **Failure has levels.** The built contracts carry execution failure at the method, criterion and result levels. D6 does not say at which level a crash is recorded.
5. **A failed target is not a failed verification.** The built enum is documented as “not a semantic finding about the target”.

---

## 1. The question, reframed

Q4-b separates into three questions that this brief keeps apart:

- **Trigger.** Which events engage the rule?
- **Level.** At what level is a failure classified: a method call, a criterion, an attempt or step, a run, the whole request?
- **Outcome obligation.** For each trigger, is a separate lifecycle failure fact required, is UNVERIFIABLE required, or neither?

Who writes the failure record is related but separate (Q4-h, Q2).

**Labels.** **\[R\]** explicit normative requirement. **\[NI\]** necessary implication. **\[A\]** interpretation requiring a decision. **\[P\]** implementation precedent. **\[K\]** candidate, not accepted. **\[D\]** decision required. Quotations from the master prompt use the text supplied in this project; its file-level hash match with the earlier-session file is user-reported and recorded in tracker §10.6 on the local, unpublished branch commit `2221ac1`.

---

## 2. Sources

| # | Source | Wording | Class | What it establishes |
| --- | --- | --- | --- | --- |
| 1 | Tracker §10.2, D6 | “A crash is recorded on two independent axes, kept distinguishable: lifecycle/execution `FAILED` and the epistemic result `UNVERIFIABLE`; not ‘crash = semantic `FAILED`’.” | \[R\] | For a crash, both facts, kept distinguishable. |
| 2 | Master §104-J | “Silent verifier crash.” Expected: “FAILED / UNVERIFIABLE”, “never PASS”. | \[R\] | The expected outcome covers the silent case too. |
| 3 | Tracker §10.2, D7 | “A not-assessable execution is never forced into semantic `FAILED`; it yields no semantic binary conclusion plus `UNVERIFIABLE`/`INSUFFICIENT_EVIDENCE`/`ESCALATE` as appropriate; execution/lifecycle failure is recorded separately.” | \[R\] | A not-assessable execution yields one of three non-conclusive verdicts, and lifecycle failure is recorded separately. |
| 4 | Master §93 | Forbidden: “silent exception → PASS”, “silent timeout → PASS”. “When verification cannot be completed: UNVERIFIABLE / INSUFFICIENT\_EVIDENCE / ESCALATE as appropriate.” | \[R\] | The never-PASS rule reaches exceptions and timeouts, not only crashes. |
| 5 | Master §98 | Fault cases include verifier crash, evidence provider crash, tool delay, tool corruption, network loss, external source unavailable. “Never allow infrastructure failure to masquerade as semantic success.” | \[R\] | A wider failure set. No outcome pairing is stated. |
| 6 | Master §91 | A failure taxonomy “at minimum” including `tool_failure`, `environment_unavailable`, `verification_timeout`, `verification_budget_exhausted`, `unverifiable`. | \[R\] | Names timeout and budget exhaustion as failure classes. Maps no outcome. |
| 7 | Master §85 | Example reason codes include SOURCE\_UNAVAILABLE, TOOL\_FAILURE, BUDGET\_EXHAUSTED, RECURSION\_LIMIT. | \[A\] | Reasons for non-definitive results. They overlap the built `execution_failure` causes (Q2-h). |
| 8 | v1 Self-Review Pass 3; v2 Review C | v1: “Verifier crashes → PASS: **No** — fail-closed by principle (§4); a crash is `FAILED`.” v2: “fail-closed principle, crash is `FAILED`”. | \[R\] | The frozen documents say a crash is FAILED. v1 §25's verdict list has no FAILED; D6 reconciles the two as separate axes. |
| 9 | Built, `verdict.py` | Enum doc: “a verifier crashing, timing out, or exhausting budget is an execution failure, not a semantic finding about the target.” Rule: a non-null `execution_failure` requires the verdict UNVERIFIABLE, “a verifier crash cannot become PASS”. | \[P\] | Four causes: TIMEOUT, TOOL\_FAILURE, VERIFIER\_CRASH, BUDGET\_EXHAUSTED. The enum doc names three of them. |
| 10 | Built, `criterion_result.py` | Rule 4: `execution_failure` is valid only on an ATTEMPTED result whose verdict is UNVERIFIABLE; the reverse is not required. The docstring says the stricter mapping “is NOT an architectural requirement”, “cites no architectural source”, and “stays open to revision once FAILED is reconciled”. | \[P\] | Written in 3C-A, before D6–D10 were ratified. |
| 11 | Built, `method.py` | `MethodExecutionState`: NOT\_RUN, BLOCKED, UNAVAILABLE, EXECUTION\_FAILED, EXECUTED. | \[P\] | A method-level execution failure exists. |
| 12 | v2 §40 | Cancellation or supersession keeps a reason code such as `budget_exhausted`. | \[R\] | A third vocabulary containing budget exhaustion. |

The built code is on the Phase C branch (`core/verification/` is unchanged since `fe338ed`), not on `main`, and is not wired into any production path.

---

## 3. What D6 establishes, in words

Take three statements: a verifier crash occurs; a lifecycle or execution failure is recorded; the epistemic result is UNVERIFIABLE.

- **Established \[R\].** A crash implies that both facts are recorded (D6, §104-J).
- **Not established.** That UNVERIFIABLE implies a crash. UNVERIFIABLE is also a successful abstention (§43, v1 §23).
- **Not established.** That a timeout, tool failure or budget exhaustion implies both facts. D7 says a not-assessable execution yields UNVERIFIABLE, INSUFFICIENT\_EVIDENCE or ESCALATE as appropriate, with lifecycle failure recorded separately.
- **Established \[R\].** No failure of any kind becomes PASS (§66, §93, §98).

---

## 4. What the built contracts enforce

- A `VerificationResult` with a non-null `execution_failure` must have the verdict UNVERIFIABLE \[P\].
- A `CriterionResult` with a non-null `execution_failure` must be ATTEMPTED with the verdict UNVERIFIABLE; UNVERIFIABLE without a failure is valid \[P\].
- There is no FAILED lifecycle field, so the separate lifecycle fact in D6 has no built home.
- UNVERIFIABLE does not require a failure value, so the built contracts cannot tell a crash from an abstention unless `execution_failure` is set.
- These checks run when an object is constructed. A verifier that crashes before building a result triggers none of them, so something outside the verifier must detect the missing completion and record the failure.
- The built rule is stricter than D7 for the declared causes: D7 allows INSUFFICIENT\_EVIDENCE or ESCALATE “as appropriate”, while the built rule forces UNVERIFIABLE.

---

## 5. Failure has levels

| Level | Built form | Status |
| --- | --- | --- |
| Method invocation | `MethodExecutionState.EXECUTION_FAILED` | Built |
| Criterion | `CriterionResult.execution_failure` with ATTEMPTED and UNVERIFIABLE | Built |
| Verification result | `VerificationResult.execution_failure` with UNVERIFIABLE | Built |
| Attempt, step, run | `VerificationRun`, `VerificationStep` (master §68) | Unbuilt; Q2-g |

D6 does not say at which level a crash is recorded. Nothing in the sources says that a method-level failure triggers the pairing, and when other methods succeed a criterion may still conclude.

**Target failure is not verification failure.** The built enum is documented as an execution failure, “not a semantic finding about the target”. If a verifier establishes that a target's operation failed, that is a semantic finding (for example an outcome FAILED under D2, with the process possibly VERIFIED, v1 §20). It must not be recorded as UNVERIFIABLE. The referent of TOOL\_FAILURE is not stated: it could be a tool the verifier used or a tool call made by the target \[A\].

---

## 6. The candidate trigger boundaries

For each candidate, three separate findings: whether D6 and the sources support the trigger, what outcome they obligate, and what lies downstream.

| Candidate | Trigger scope | Outcome obligation | Ownership and downstream effects |
| --- | --- | --- | --- |
| **A. Verifier crash only**, including a silent crash | Supported by D6 (“a crash”) and §104-J (“silent verifier crash”). Silent on timeout, tool failure and budget. | Both facts (D6, §104-J). For the other causes, only never-PASS (§93) and D7 apply. | How a silent crash is detected and recorded is open (Q4-h, Q2). |
| **B. Any of the four built causes that prevents the whole verification from completing** | Not determined by D6. Supported in part by the enum doc, §93 (timeout) and §91. | Never-PASS is established. UNVERIFIABLE for these causes is a built implementation judgment. A separate failure fact follows from D7, not D6. | Needs the level question (what counts as the whole operation) and the TOOL\_FAILURE referent. |
| **C. A broader failure boundary** (evidence-provider failure, network loss, unavailable sources, runtime failures) | Not determined. §98 lists these as fault cases with a never-masquerade rule. | Never-PASS only. No pairing stated. | The line between infrastructure failure and insufficient evidence blurs: §85's SOURCE\_UNAVAILABLE is a reason for a non-conclusion, not necessarily an execution failure. |

The built rule already treats the four causes alike at the result and criterion levels. That is an implementation fact, and it does not prove that every occurrence of those causes is a whole-verification failure.

---

## 7. Scenarios

| # | Scenario | What D6 and §104-J determine | What D7, §93 and the built contracts add | Open |
| --- | --- | --- | --- | --- |
| 1 | The verifier crashes before producing any result | Both facts expected | No built check runs; nothing is constructed | Who detects and records it (Q4-h, Q2) |
| 2 | The verifier crashes after recording some criterion results | The pairing | Constructed criterion results remain valid objects; nothing invalidates them | How the failure is represented without erasing them or implying that aggregation completed (Q4-g, §46) |
| 3 | A declared VERIFIER\_CRASH on a constructed result | The pairing | The built rule requires UNVERIFIABLE; there is no field for the separate failure fact | Where the lifecycle fact lives (Q2) |
| 4 | Timeout, tool failure or budget exhaustion interrupts the whole verification | Silent | Never PASS (§93); D7 “as appropriate” with lifecycle failure recorded separately; the built rule forces UNVERIFIABLE | Q4-b1, Q4-b3 |
| 5 | One method fails and the others continue | Silent | A method-level EXECUTION\_FAILED exists; no rule requires the pairing | The level (Q4-b2) |
| 6 | The target's operation fails and the verifier establishes that | Not a crash | A semantic finding, not an execution failure (D2, v1 §20) | The TOOL\_FAILURE referent (Q4-b4) |
| 7 | Verification abstains for insufficient evidence or escalation | Not a crash | A successful abstention (D7, §43, v1 §23) | Nothing for Q4-b, except that UNVERIFIABLE must not be read as proof of a crash |

---

## 8. Effects on other decisions

- **Q2, where FAILED lives.** The trigger and the lifecycle representation stay separate decisions. Q4-b can say which events require a failure fact without deciding whether that fact belongs to a result lifecycle, a run lifecycle or a relation between them.
- **Q4-g, aggregation and partial results.** A missing assessment, a non-conclusive assessment and a failed attempt are different situations. A crash category must not be used to define when an assessment has been “produced”; §46's undefined aggregation still controls that. A failed attempt does not by itself invalidate criterion results already established.
- **Q4-h, the writer.** Scenario 1 shows the built checks cannot catch a crash that precedes construction. Someone else must record it.
- **Q6, `failure_control`.** The four causes must not be mapped mechanically to CONTROLLABLE, UNCONTROLLABLE, MIXED or UNKNOWN (v1 §20 calls controllability an orthogonal finding that informs Governance and the Supervisor, not a governance decision). The derivation stays open.
- **D7.** The trigger scope must be checked against D7's exact wording. UNVERIFIABLE does not settle how a non-conclusion is represented, and FAILED is not inserted into the verdict vocabulary.

---

## 9. Candidate and decisions required

**Candidate \[K\]: record the settled core, and mark the rest undecided.**

- Settled by D6 and §104-J: a verifier crash is recorded as a lifecycle or execution failure and as the epistemic result UNVERIFIABLE.
- Settled by §66, §93 and §98: no failure becomes PASS.
- Governed by D7: other not-assessable executions yield UNVERIFIABLE, INSUFFICIENT\_EVIDENCE or ESCALATE as appropriate, with lifecycle failure recorded separately.
- Implementation judgment pending a decision: the built rule's extension of “UNVERIFIABLE only” to timeout, tool failure and budget exhaustion.
- Do not accept candidate A, B or C yet. The sources establish a minimum crash pairing and a broader invariant for declared failures, and they do not establish that these are the same rule.

**Decisions required \[D\].**

- **Q4-b1.** Does D6's pairing apply to a verifier crash only, or to any execution failure that prevents the whole verification from completing, and which causes?
- **Q4-b2.** At what level is a failure classified (method, criterion, attempt or step, run, request), and does a lower-level failure trigger the pairing?
- **Q4-b3.** For causes other than a crash, is UNVERIFIABLE mandated (the built rule) or one of three “as appropriate” (D7), and is a separate lifecycle failure fact required?
- **Q4-b4.** What does TOOL\_FAILURE refer to: a tool used by the verifier, or a tool call made by the target? A target failure the verifier establishes is never UNVERIFIABLE by that fact alone.
- **Q4-b5.** Who detects and records a silent crash? (Depends on Q4-h and Q2.)

**Next permissible decision.** Q4-b1 and Q4-b3 can be decided now, because neither depends on Q2. Q4-b4 needs an owner clarification. Q4-b2 and Q4-b5 depend on Q2-g and Q4-h. This brief refines the Q4 brief's earlier candidate C2, which treated all four causes alike.

## 10. Limits

Code was read at the Phase C branch tip, and nothing was executed. The master prompt is read from the supplied text. The earlier “Mission §N” citations in code docstrings are not relied on (M9). Frozen v1, v2 and v3 were read only at the passages cited.

---

## 11. Revision 2 baseline and provenance

Revision 2 rests on three separate evidence sets: the Verification branch (package contracts), `main` (runtime behavior) and the live refs seen on 2026-10-29. Labels follow section 1: OBSERVED means inspected or executed in this session; REPORTED means inherited from the handoff or an earlier session.

| Item | Value | Label |
| --- | --- | --- |
| Branch tip | `3ba858a`, equal to the remote tip; working tree clean | OBSERVED (`git ls-remote`, `git status`) |
| Branch ancestry | `2221ac1`, `b52c53e`, `5bb31aa`, `21bab65`, `dbdfcb7` are ancestors of `3ba858a` | OBSERVED |
| `main` | `f13bfde`, unchanged from the handoff; 171 commits only on `main`, 61 only on the branch (58 at `2221ac1` plus the three handoff commits) | OBSERVED / DERIVED |
| Package baseline | `core/verification` and its tests identical to `fe338ed` (empty diff); 424 pytest passes, 424 stdlib-mirror passes, mypy clean on 28 files, run on `3ba858a` | OBSERVED |
| Scope of those results | Verification package contracts only; no runtime behavior is covered, and nothing outside the package, its tests and the docs imports `core.verification` on either ref | OBSERVED |
| Runtime audit baseline | `main` `f13bfde`, extracted with `git archive` into an isolated directory, Python 3.12.3; six targeted test files give 170 passed | OBSERVED |
| Probes | Five throw-away scripts ran only in that isolated copy; none was committed and the repository was not changed | OBSERVED |
| This brief at revision 1 | Doc id `a8a1f900-2bb0-46ad-8ead-e055cf939aa9`, content node `c9bfd0a8-bd8a`, 10 sections; every revision-1 block kept its id and hash after the revision-2 edits (checked in section 16) | OBSERVED |
| Brief SHA-256 | Not recorded: the Docs export returns inline base64 only and cannot write to the container, so a file hash would need the text retyped. Block ids and per-block hashes are the integrity record instead | UNRESOLVED |

The 424 package results and the 170 runtime-side results are historical for any other commit. Neither set establishes the runtime behavior described in section 12 beyond what each probe in that section states.

The Python version differs from the `cp314` bytecode files found in the repository; the audit does not show whether that changes any result.

**Ref advance during the session.** `main` resolved to `f13bfde` at the start of the work and to `4a4783c` at the end (54 further commits, the latest dated 2026-10-28). The audit baseline stays `f13bfde`. The new commits leave unchanged `core/workers/base.py`, `evaluator.py`, `supervisor.py`, `core/runtime/execution_runtime.py`, `cancellation.py`, `watchdog.py`, `core/workflow/runtime.py` and `definition.py`. They do change `core/orchestrator.py` (two context-save guards at about lines 613 and 842, which move the legacy-branch lines cited in F-13 by about 8), `interface/api.py` (a log line near line 413), `core/context.py`, `core/merger.py`, `core/workers/planner.py`, one test file and `KNOWN_ISSUES.md`. On the new tip the FZ-01 row and the open D1 decision read as before (OBSERVED). F-01 to F-12 and F-14 are therefore expected to hold on `4a4783c`, DERIVED from unchanged files; nothing was re-run there, and the effect of the changed dependencies on those paths was not checked.

---

## 12. Runtime failure-path audit: findings, test coverage and matrix

Fourteen findings come from reading `main` at `f13bfde` and from five isolated probes. Every line reference is to that commit. "Executed" means a probe ran in the isolated copy on Python 3.12.3, once, and was not committed; "source" means static reading only. Nothing here is an accepted decision, and no finding changes D1 to D10.

**Findings.** Status uses CONFIRMED, PARTIALLY CONFIRMED, UNCONFIRMED, CONTRADICTED or NOT TESTED. Effect says whether the finding blocks closure, is a limitation no owner has accepted, or is incidental.

| ID | Behavior and evidence | Status | Relevance to Q4-b and effect |
| --- | --- | --- | --- |
| F-01 | A worker failure carries `success=False` and a free-text error; the `worker.failed` payload adds `error` and `error_type` (the exception class name). No structured cause exists. `core/workers/base.py:293-312`. | CONFIRMED (source) | Nothing on this path produces a cause code, so any cause classification or `TOOL_FAILURE` referent (Q4-b2, Q4-b4) is new work or stays absent. Limitation, unaccepted. |
| F-02 | A worker that returns `success=False` emits `worker.completed` with a `success` field; only an exception inside `_run` emits `worker.failed`. `base.py:287`, `base.py:307`. Executed: one returned failure gave one `worker.completed` with `success` false and no `worker.failed`. | CONFIRMED (source, executed) | A failure cannot be recognized from the event type alone. Limitation, unaccepted. |
| F-03 | `tool_success_rate` is `len(worker_completed_events) / total` (`core/workers/evaluator.py:180`) and ignores the `success` field. Events come from two types only (`evaluator.py:254-256`), at most 200 each (`evaluator.py:114,125`). Executed: a workflow whose node returned a failure scored 1.0; a node that failed twice then succeeded scored 1.0. | CONFIRMED for returned failures; DERIVED for cancelled, rejected, escalated and missing-terminal cases (they are in neither count) | The metric cannot serve as evidence that a failure occurred or did not. Incidental to Q4-b; separately scoped. |
| F-04 | Each attempt gets a fresh `attempt_id` (`core/workflow/runtime.py:863`) stored on the node state, so only the last one survives; it is passed in `ctx.metadata` (`runtime.py:881`) but is absent from worker event payloads. Executed: 3 attempts gave 3 distinct `attempt_id` values seen by the worker, 3 distinct `task_id` values in events, one surviving `attempt_id` in state. The mapping from `task_id` to `attempt_id` is recorded nowhere. | CONFIRMED (source, executed) | Attempts are distinguishable in events but not joinable to node state. Bears on Q2-g and Q4-b2. Limitation, unaccepted. |
| F-05 | `SupervisorWorker._attempt_retry` counts a caller-supplied `supervisor_retry_attempt` (`core/workers/supervisor.py:270`) or a shared recovery budget, then calls `invoke(..., parent_worker_id=self._id)` (`supervisor.py:305-309`). It acts only on a result handed to it (`supervisor.py:214`); nothing in it detects a silent crash. | CONFIRMED (source, tests) | Q4-b5: the Supervisor is not an existing detector. Limitation, unaccepted. |
| F-06 | Error-branch recovery keeps the failed node FAILED (`runtime.py:795`), routes to the branch (`runtime.py:800-812`), and the workflow result follows the branch (`runtime.py:582-592`). Executed: checkpoint states showed the failing node FAILED and the recovery node COMPLETED; the workflow returned `success=True`; the failing node's result stayed `success=False`. | CONFIRMED (source, executed) | Recovery does not erase the node-level failure record, but the enclosing result reads as success. Supports criteria 5 and 6 at node level only. |
| F-07 | Cancellation through a `CancellationToken` is cooperative: it is checked at a node boundary (`runtime.py:723`) and at attempt start (`runtime.py:865-866`); the watchdog cancels the token and nothing preempts a running worker. The repository's own test fixtures say the same. | CONFIRMED (source) | A timeout that only cancels the token does not stop a worker that never polls it. Q4-b2 scope. Limitation, unaccepted. |
| F-08 | An asyncio `CancelledError` inside `Worker.execute` is caught, a `worker.cancelled` event is emitted and a failed result "Worker cancelled" is returned (`base.py:293-296`). Executed: with `max_retries=1` the worker ran a second time after `task.cancel()` and the task kept running; with `max_retries=0` `execute()` returned `success=False` instead of raising. | CONFIRMED (source, executed) | A cancellation can be retried like a failure; only the event type tells them apart. Limitation, unaccepted. |
| F-09 | A cancellation landing outside `Worker.execute` (executed: during the retry backoff) raised `CancelledError` out of `WorkflowRuntime.execute`, against its "Never raises" docstring (`runtime.py:254,479`). No `workflow.completed` event was found for that workflow, no failure was counted, and the `GraphExecutionWatchdog._run` task was still running afterwards (`watchdog.stop()` at `runtime.py:568,649` has no `finally`). | CONFIRMED once (executed); cause DERIVED from source | A lifecycle failure can end with no terminal report. Possible separate defect, not registered. Bears on Q4-b5 and Q4-h. |
| F-10 | Unknown worker type and worker construction failure return a failed result and count one failure but emit no `worker.*` or `execution.completed` event (`core/runtime/execution_runtime.py:128-133,147-152`). Executed: no `worker.failed` for the unknown type. | CONFIRMED (source; probe confirms the absent `worker.failed` only) | Some failures are visible only in the return value and logs. Limitation, unaccepted. |
| F-11 | `_total_failures` is incremented at `execution_runtime.py:199` and again at `:233` when an exception escapes `Worker.execute`. Executed: that path counted 2, while a returned failure, an exception in `_run` and an unknown worker each counted 1. The path is reachable by a subclass overriding `execute()` (executed) and, DERIVED and not run, by an exception from governance evaluation at `base.py:246`, which sits outside the `try`. | CONFIRMED (executed) | Incidental, separately scoped; no Q4-b criterion depends on it. |
| F-12 | `_emit_event` swallows its own failures: `base.py:414-436` and `core/workflow/runtime.py:914-922` catch `Exception` and log. | PARTIALLY CONFIRMED (source; not executed) | If the reporting channel fails, the failure remains only in the return value and logs. Q4-b5, Q4-h. |
| F-13 | The K4.2 route reads `wf_result.output` and never `wf_result.success` for node errors (`core/orchestrator.py:537-553`, comment included); the `success` checks at `orchestrator.py:715-728` belong to the legacy branch; `/query` returns `success=True` after `handle()` returns (`interface/api.py:187-191`). | CONFIRMED (source); HTTP behavior not re-run | D1 / FZ-01 (section 13): the public failure channel is absent on this route. |
| F-14 | No module outside `core/verification`, its tests and the docs imports the package, on `main` and on the branch. The watchdog was read at header level only: it watches graph progress per workflow, not per worker or across processes. | CONFIRMED (import search); PARTIALLY CONFIRMED (watchdog) | No real execution route carries a verification, so every statement about recording a verifier crash concerns contracts, not behavior. |

**Existing test evidence.** The six targeted files all pass (170). Passing shows only what each assertion states.

| Behavior | Test | What it asserts | Status |
| --- | --- | --- | --- |
| Error-branch recovery | `tests/test_workflow_runtime.py` about lines 301-332 | node result `success` false, workflow `success` true | Tested and passing at result level; node state and events NOT TESTED |
| Failure accounting | `tests/test_execution_runtime.py`, `test_stats` | `total_failures >= 1` | Inconclusive: the bound is loose and the F-11 path is not exercised |
| Cancellation | `test_workflow_runtime.py` about line 393 (pre-cancelled token); `test_execution_runtime.py:113` (`token.cancel()`) | cooperative path only | Mid-run asyncio cancellation of a worker or workflow NOT TESTED; `test_scheduler_failure_containment.py:402` covers the scheduler; `break_cancellation.py` is a script and is not collected |
| Evaluator accounting | `tests/test_evaluator_worker.py` about lines 165-190 | events built without a `success` field | A returned-failure `worker.completed` NOT TESTED |
| Attempt identity | `test_workflow_runtime.py:480-488`; `tests/core/cognitive/test_kernel_blocker_resolution.py:265-281` | checkpoint round trip; a UUID the test itself assigns | Runtime generation in `_execute_node_with_retry` NOT TESTED |
| Supervisor retries | `tests/test_supervisor_worker.py:238-427` | attempt counts, `parent_worker_id`, exhaustion, budget | Tested and passing; the call is checked through kwargs, so DERIVED to be against a stubbed runtime |
| Missing terminal event, silent crash | none found | none | NOT TESTED |

**Failure-path matrix.** Each row names what an observer can see on `main`.

| Path | WorkerResult | Terminal event | Evaluator effect | Evidence |
| --- | --- | --- | --- | --- |
| Normal completion | `success=True` | `worker.completed` (success true) | numerator and denominator | `base.py:287` |
| Returned failure | `success=False`, error text | `worker.completed` (success false) | counted as completed, inflating the rate | F-02, F-03 |
| Exception in `_run` | `success=False`, `error_type` | `worker.failed` | denominator only | `base.py:303-307` |
| asyncio cancel inside `Worker.execute` | `success=False`, "Worker cancelled" | `worker.cancelled` | in neither count | F-08 |
| Token cancel at a boundary | `success=False`, "Workflow cancelled" or "Cancelled during retry"; worker not called | none | none | `runtime.py:723,865-866` |
| Governance rejection or escalation | `success=False` | `worker.rejected` or `worker.escalated` | in neither count | `base.py:249,261` |
| Exception escaping `Worker.execute` | `success=False` from the runtime | `execution.completed`; no worker terminal event | none | `execution_runtime.py:196-233`, F-11 |
| Unknown worker or construction failure | `success=False` | none | none | F-10 |
| Error-branch recovery | failed node `success=False`; workflow `success=True` | those of the failing path, plus the recovery worker's | as the failing path | F-06 |
| Cancel outside `Worker.execute` | none; `CancelledError` raised | no `workflow.completed` found | none | F-09 |
| Silent process death | none | none | invisible | UNRESOLVED, NOT TESTED |

**Not established.** Persistence failure of events, `resume()` beyond the handoff's reading, HTTP-level behavior, cross-process crash detection, and behavior on Python 3.14. The probes ran once each; none was repeated or run under load. Whether any finding warrants an issue or a fix is an owner decision and outside this brief.

---

## 13. D1 disposition

The mission's "D1 failure-reporting path" most plausibly means the freeze-remediation D1 (FZ-01, the public result contract). Source supports that match, but nothing in the mission text names which D1 it means, so the identification stays PARTIALLY CONFIRMED until the owner says so. This section makes no D1 decision.

| Reading | Where it is defined | Subject | Fit |
| --- | --- | --- | --- |
| Tracker D1 | tracker section 10.2 (REPORTED through the handoff) | v1 section 20 stays the authoritative semantic source | Poor: about source authority, not a reporting path |
| K4.2 D1 | `CURRENT_STATE.md` K4.2-H1 row (D1/D2/D4/D5/D6/D8/D9) | layered semantic authority for the goal description | Poor: unrelated to failure reporting |
| Freeze-remediation D1 | `KNOWN_ISSUES.md:123` on `main` (OBSERVED) | the public result contract for FZ-01: keep `handle() -> str` plus an internal structured result, change the return type, or raise a typed exception | Good: the only D1 whose subject is a failure channel; the FZ-01 row (`KNOWN_ISSUES.md:115`) reads "K4.2 path has no failure channel" and is blocked on D1 |

**What would settle it.** An owner statement, or a qualifier in the mission wording. The handoff holds Appendix A verbatim and it uses "D1" without a qualifier (handoff lines 722-742 and 828-830), so the repository offers none. Until then every use of "D1" in this brief means the freeze reading and carries the label UNCONFIRMED.

**The failure-reporting path as it stands on `main`.** A normative requirement to record a failure is not evidence that the current channel can detect, associate and persist it.

- Node failures reach `WorkflowResult` (F-06, F-13), but the K4.2 route never reads `success` for node errors and `/query` returns `success=True` (F-13). OBSERVED by source; HTTP behavior was not re-run.
- A worker failure is recorded as an event only on some paths, with no structured cause and no attempt identity (F-01, F-02, F-04, F-10), and a failed event write is swallowed (F-12).
- The recording is done by the failing component's own handler, not by an independent observer; no observer of abnormal termination or a missed terminal event was found (F-05, F-09, F-14).
- No verification runs through any route (F-14), so for Q4-b5 the answer today is that no channel records a verifier crash, because no verifier executes in the system. That describes the current wiring, not a design requirement.

**Effect on Q4-b.** Only criterion 17 and the writer question Q4-h depend on D1. None of the Q4-b candidate dispositions needs D1's options to be chosen first. Choosing among them remains an owner decision, and this brief does not redesign the channel.

---

## 14. Missing-source register and the source-recovery gate

The handoff lists three analysis Docs that exist only in claude.ai. All three were found at the revisions it records, so they are recovered as sources. They are not preserved in the repository, so the transfer stays incomplete.

| Document | Role | Location | Revision recorded | Revision seen 2026-10-29 | Read in this session | In the repository |
| --- | --- | --- | --- | --- | --- | --- |
| Verification 3C-B: Q2 and Q5 decision pack | candidate decisions and dependencies for Q2 and Q5 | doc `b5227c99-327f-483d-b726-3f93d37b8265`, node `4a3bfaae-440e` | 28 | 28 | outline only | no |
| Verification 3C-B: Q4 queryable non-conclusion brief | Q4 candidates C6 to C8, the Q4-a to Q4-i registry and the section 10.3 ledger | doc `85f80a7c-c273-4902-b8f1-fe009d3a3de5`, node `35e76bcb-57e5` | 13 | 13 | outline only | no |
| Verification 3C-B: Q4-b trigger boundary of D6 (this brief) | Q4-b1 to Q4-b5 | doc `a8a1f900-2bb0-46ad-8ead-e055cf939aa9`, node `c9bfd0a8-bd8a` | 1 | 1 before the revision-2 edits | in full | no |

**Gate.** Revision 2 may be applied to the canonical brief when the three Docs are recovered or their absence is resolved by an authoritative disposition. Recovered here means found in the originating store at the recorded revision (OBSERVED). The gate therefore passes for editing this brief. It does not close the transfer.

**Qualifications.** Only this brief was read in full. The pack and the Q4 brief were checked at outline level, so their revision numbers are verified and their content is not. Where sections 11 to 16 mention Q2-g, Q4-b1 to Q4-b5, Q4-h or the section 10.3 ledger, they rely on the handoff and sections 1 to 10, and carry the label REPORTED. Integrity information is limited to revision numbers, block ids and per-block hashes: the Docs export returns inline base64 only, so no content hash and no repository copy were produced.

**Decisions and requirements that may depend on each document.** The pack: Q2-a to Q2-h and Q5. The Q4 brief: Q4-a to Q4-i and its ledger. This brief: Q4-b1 to Q4-b5 and their dependencies.

**Required recovery actions, none taken here.**

1. The owner authorizes exporting the three Docs into the repository, or accepts them as an external dependency. No repository change was authorized for this task.
2. Before any alignment of the Q4 ledger, someone re-reads the pack and the Q4 brief in full. Criterion 23 (brief and ledger agree) depends on that and is not met (section 15).

The transfer status in the handoff, "TRANSFER INCOMPLETE — REQUIRED INFORMATION MISSING", is therefore unchanged by this revision.

---

## 15. Closure matrix against the 26 original criteria

The 26 criteria are the definition of done in Appendix A section 23 of the handoff. ADDRESSED means the brief states the point with its evidence. It does not mean an owner accepted it or an independent review confirmed it. Of the 26, 11 are ADDRESSED, 13 PARTIALLY ADDRESSED, 1 NOT ADDRESSED and 1 BLOCKED, so the brief is not closed.

| Criterion | Evidence in this brief | Status | Outstanding prerequisite or owner decision |
| --- | --- | --- | --- |
| 1. Every original analytical gap has a treatment | sections 1-9 treat trigger, level, outcome obligation, `TOOL_FAILURE` and the writer; sections 11-14 add runtime evidence | PARTIALLY ADDRESSED | Terminality, recovery policy, execution scopes, observed versus inferred cause, and late or retried results have no treatment beyond F-04 to F-09 |
| 2. D6's pairing is not weakened or broadened | sections 3, 6, 9 | ADDRESSED | none; D6 unchanged |
| 3. Scope of crash and epistemic result not inferred | sections 6, 9 (candidates A to C not accepted) | ADDRESSED | Owner decision Q4-b1 |
| 4. Occurrence, terminality, recovery and execution scope are distinct | section 5 (levels); F-06, F-08 (recovery and cancellation are distinct from failure on `main`) | PARTIALLY ADDRESSED | No definition of terminality or execution scope |
| 5. A lower-level failure does not invalidate the enclosing verification | section 5 closing paragraph, section 7 scenario 2; F-06 as a runtime analogue | PARTIALLY ADDRESSED | Owner decision Q4-b2; the unit, enclosing and terminality readings are not written out |
| 6. Recovery does not erase the historical failure | F-06 (OBSERVED: the node stays FAILED after recovery) | PARTIALLY ADDRESSED | Evidence only; no stated policy for verification-level recovery |
| 7. Verifier failure versus target failure | section 5, section 7 scenario 6 | ADDRESSED | Owner clarification Q4-b4 |
| 8. Fail-closed invariant without a cause-to-verdict mapping | sections 3, 9 (never PASS is \[R\]; the extension to other causes is a judgment) | PARTIALLY ADDRESSED | The invariant is not yet stated in one precise sentence |
| 9. Evidence to classify a crash versus evidence of non-completion | section 4 last points; F-05, F-09, F-14 (no existing observer) | PARTIALLY ADDRESSED | No distinction drawn between the two kinds of evidence |
| 10. Missing output is not proof of a crash | section 3 and scenario 7 (UNVERIFIABLE is not proof of a crash) | PARTIALLY ADDRESSED | Missing output itself is not discussed; F-12 and F-14 show why it matters |
| 11. Timeout, budget and cancellation scopes not inferred from reason codes | section 2 row 12, section 6; F-07, F-08 | PARTIALLY ADDRESSED | Scope per reason code is not written out |
| 12. Multiple failures not collapsed to one cause | none | NOT ADDRESSED | Needs its own treatment |
| 13. Outcome policy and lifecycle-recording policy are separate | sections 1, 8; Q4-b3 | ADDRESSED | Owner decision Q4-b3 |
| 14. D7's alternatives not mapped mechanically | sections 4, 6, 9 | ADDRESSED | Owner decision Q4-b3 |
| 15. Criterion-result preservation is not aggregate completion | section 8 (Q4-g), scenario 2 | ADDRESSED | Aggregation (§46) is undefined; owner decision Q4-g |
| 16. Retries, late results, persistence, delivery, supersession only as far as sources support | F-04, F-05, F-08 cover retries; section 2 row 12 names supersession | PARTIALLY ADDRESSED | Late results, persistence and delivery are not treated |
| 17. D1's failure-reporting path inspected | section 13; F-12 to F-14 | ADDRESSED for the freeze reading of D1 | Which D1 is meant is UNCONFIRMED; HTTP behavior not re-run |
| 18. Execution identity and provenance established or left unresolved | F-04, F-05; DEBT-015 as REPORTED | PARTIALLY ADDRESSED | Runtime attempt identity is established at `f13bfde`; verification-level identity stays unresolved (Q2-g) |
| 19. End-to-end path traced; contracts not presented as guarantees | section 12 matrix; F-14 | PARTIALLY ADDRESSED | Worker and workflow path traced; no verification route exists; cross-process and HTTP behavior untraced |
| 20. `TOOL_FAILURE` stays open | section 5, Q4-b4; F-01 (no producer of a cause code) | ADDRESSED | Owner clarification Q4-b4 |
| 21. Every scenario traces to evidence or is marked unresolved | seven scenarios in section 7; eleven rows in the section 12 matrix | PARTIALLY ADDRESSED | The twenty-scenario matrix planned in the handoff was not produced |
| 22. Each open item has alternatives, consequences, dependencies and a closure condition | section 9 | PARTIALLY ADDRESSED | Closure conditions for Q4-b1 to Q4-b5 are not stated |
| 23. The brief and the ledger agree | none | BLOCKED | The Q4 brief's section 10.3 ledger was not re-read or aligned (section 14) |
| 24. Unassigned owners, missing sources and unverifiable claims are qualified | sections 11, 13, 14, 16 | ADDRESSED | No owner is assigned to any decision; the brief hash is not recorded |
| 25. No implementation, schema, contract, ADR, frozen document or accepted decision changed | section 16 checks | ADDRESSED | none |
| 26. Final diff reviewed; report evidence-based | section 16 | ADDRESSED | The only change is to this Doc; no repository diff exists |

---

## 16. Residual blockers, status and revision log

**Status.** REVISION PREPARED: revision 2 is applied to the canonical brief and the source-recovery gate passed (section 14). The audit is complete for the error-branch path, the failure counter and the failure-path matrix, and partial for end-to-end cancellation and test coverage. The revision is not VALIDATED, because no independent review has read it and criterion 23 is blocked. The transfer is not complete and the mission is not closed.

**Validation done.** All 49 blocks of revision 1 keep their ids and hashes (compared with the outline read at revision 1). The hashes of the 11 lists and tables cover structure, not text; no operation sent in this session targeted any revision-1 block except as an insertion anchor, so their text is unchanged (DERIVED). The probe values quoted in section 12 were re-run before the section was kept. The repository was not touched: at the end of the work the branch tip is still `3ba858a` and the working tree is clean. Line references in section 12 were taken from the audit output and not re-checked one by one after writing.

**Residual blockers.**

1. **Transfer.** The three Docs are not in the repository (section 14). The owner decides whether to export them or accept them as an external dependency.
2. **D1 identity.** UNCONFIRMED (section 13). The owner states which D1 the mission means.
3. **Ledger agreement.** Criterion 23 is BLOCKED until the pack and the Q4 brief are re-read in full and the Q4 ledger is compared with this brief.
4. **Analytical content not yet written.** Criteria 1, 4, 5, 6, 8 to 12, 16, 18, 19, 21 and 22 are partial or absent (section 15); criterion 12 has no treatment. Writing it is a further revision and needs the owner's go-ahead.
5. **Audit gaps.** Not traced: the orchestrator and API cancellation path, the timeout wrapper in `core/runtime/limits.py`, a watchdog-triggered cancellation run end to end, persisted state after a cancellation, behavior when terminal reporting itself fails, and the individual DEBT-015 sub-items. Supervisor and evaluator tests were read for their key assertions, not in full.
6. **Findings without an owner.** F-03, F-09 and F-11 might warrant issues or fixes. None is registered or fixed here, and registering them is an owner decision.
7. **Environment.** The audit ran on Python 3.12.3; the repository holds `cp314` bytecode. The brief hash is not recorded (section 11).

**Baseline note.** `main` advanced to `4a4783c` while this revision was prepared (section 11). The audit baseline is still `f13bfde`; a re-audit on the newer tip is not part of revision 2.

**Recommendation, not a decision.** Resolve blockers 1 to 3 first; they are cheap and unlock the rest. Then decide whether a revision 3 should write the content in blocker 4 and close the gaps in blocker 5.

**Revision log.**

| Revision | Date | Change |
| --- | --- | --- |
| 1 | 2026-10-18 | First version: sections 1 to 10 |
| 2 | 2026-10-29 | One pointer paragraph after the Status paragraph and sections 11 to 16 appended. No block of revision 1 was edited. Section 10's "nothing was executed" describes revision 1 only; revision 2 ran isolated probes (sections 11 and 12) and left section 10 unchanged. Authority: the closure mission of 2026-10-29 supplied in this session. Platform revision counters advance with every edit and do not match these labels |

---

## 17. Revision 3: owner directions received 2026-10-29

Revision 3 is an audit and verification revision. Sections 1 to 16 are unchanged and remain the record of revisions 1 and 2; where a statement there is overtaken, a section below says so. Nothing here changes code, tests, schema, contracts or an ADR, and nothing here authorizes any of them.

The directions below come from a message supplied by the owner in this session. Their label is OWNER DIRECTION: they are not yet recorded in a repository decision record.

| Item | Owner direction | What revision 3 did | Status |
| --- | --- | --- | --- |
| D1 identity | The mission's D1 is the freeze-remediation decision for FZ-01, the public result contract | Checked on `main` `4a4783c`: the FZ-01 row (`KNOWN_ISSUES.md:118`) reads "OPEN -- BLOCKED on D1" and the D1 text (line 126) lists the three contract options. The owner's link points at line 125, which is blank on that commit | Identity CONFIRMED by owner direction and by the register. This replaces the UNCONFIRMED label in section 13 for identity only |
| D1 contract choice | Still requires an explicit owner decision | Nothing. The register says no decision was taken, and FZ-01 also depends on FZ-02, so choosing a contract would not close it | OPEN |
| Export of the three Docs into the repository as revision-pinned evidence, by a docs-only branch and review | Accepted as the direction | Not executed; see below | NOT DONE, blocked by tooling |
| Read the full pack and Q4 brief first | Required for criterion 23 | Both read in full: Q4 brief at rev 13, pack at rev 28, matching section 14 | DONE (section 19) |
| Revision 3 as an audit and verification revision, separate from implementation | Yes | In progress; any defect found goes to separate remediation work | IN PROGRESS |
| Cancellation, reporting, `limits.py`, watchdog, persisted state, DEBT-015 sub-items | Investigate and test | Partly done (section 20) | PARTIAL |
| Revalidate against `main` `4a4783c` | Required | Done for six test files and the probes (section 18) | DONE, scope limited |
| Independent review before the brief is marked validated | Required | No independent reviewer is available in this session | BLOCKED |
| Preserve revisions 1 and 2 | Required | Sections 1 to 16 were not edited (section 22) | DONE |

**Why the export was not carried out.** The Docs export returns a tab inline as base64 only; the service reports that this brief alone renders at 44,650 bytes of Markdown. Writing the three exports into the repository from this session would mean copying them through the conversation by hand, with no way to show that the copy equals what the service exported. Its SHA-256 would then describe my copy, not the "actual exported file" the direction requires. I therefore did not do it, and I created no branch and no commit.

**What is needed.** The owner exports each Doc from claude.ai (Markdown as the searchable copy, and DOCX or PDF as the preserved original) and uploads the files here. I would then compute the SHA-256 of the actual files, write a manifest (document id, content node, revision, export format, export date, size, hash) and prepare a docs-only branch for review. Pinning: the pack at rev 28, the Q4 brief at rev 13, and this brief once revision 3 is accepted. The direction names this brief at "rev 2"; the content label is revision 2 until revision 3 is accepted, while the Docs revision counter stood at 11 when this section was written, so the manifest should record both.

---

## 18. Revalidation against `main` `4a4783c`

The section 12 findings were produced on `f13bfde`. They were re-checked on `4a4783c` (54 later commits), extracted with `git archive` into a separate directory and run on Python 3.12.3. The repository itself was not touched.

**Source identity.** `git diff` reports no difference between the two commits for ten of the audited files: `core/workers/base.py`, `evaluator.py`, `supervisor.py`; `core/runtime/execution_runtime.py`, `cancellation.py`, `watchdog.py`, `limits.py`, `execution_context.py`; `core/workflow/runtime.py`, `definition.py` (OBSERVED). The line references in section 12 for those files therefore hold on `4a4783c`. Two audited files changed, `core/orchestrator.py` and `interface/api.py`, and were re-read.

**Refreshed line references on `4a4783c`.**

| Reference | On `f13bfde` | On `4a4783c` |
| --- | --- | --- |
| K4.2 route reads `wf_result.output`, never `success` (F-13) | `core/orchestrator.py:537-553` (comment) | `core/orchestrator.py:532` (`answer = wf_result.output or ""`) and the comment from line 537; no `wf_result.success` read between them and line 723 |
| Legacy-branch `success` check (F-13) | `orchestrator.py:715` | `orchestrator.py:723` |
| `/query` returns `success=True` (F-13) | `interface/api.py:187-191` | `interface/api.py:187-191`, unchanged |
| FZ-01 row, D1 text, DEBT-015 row | `KNOWN_ISSUES.md:115`, `:123`, `:33` | `KNOWN_ISSUES.md:118`, `:126`, `:35` |

**Tests.** The six targeted files (`test_execution_runtime`, `test_supervisor_worker`, `test_evaluator_worker`, `test_workflow_runtime`, `test_workflow_failure_disclosure`, `test_scheduler_failure_containment`) give 170 passed on `4a4783c`, the same count as on `f13bfde`. This establishes the isolated baseline only. It does not establish the failure paths no assertion covers (section 12, test coverage).

**Probes.** All were re-run on `4a4783c` and gave the same results as on `f13bfde`.

| Probe | Result on `4a4783c` | Findings |
| --- | --- | --- |
| P1 failure counter per path | returned failure 1, exception in `_run` 1, exception escaping `Worker.execute` 2, unknown worker 1 | F-10, F-11 |
| P2 error branch | workflow `success=True`; node a FAILED in the checkpoint, recovery node COMPLETED; node a result `success=False`; `worker.completed` flags true and false, no `worker.failed`; `tool_success_rate` 1.0 | F-02, F-03, F-06 |
| P3 retries | 3 distinct `attempt_id` seen by the worker, one surviving on the node (the last); 3 distinct `task_id` in events; no `attempt_id` in event payloads; flags true, false, false; `tool_success_rate` 1.0 | F-03, F-04 |
| P4 unknown worker | failed result; no `worker.failed` for that workflow | F-10 |
| P5, P5b asyncio cancel | with one retry the worker ran twice and the task kept running; with none, `execute()` returned `success=False`, "Worker cancelled" | F-08 |
| P6 cancel during retry backoff | `CancelledError` escaped `execute()`; no `workflow.completed` event; the watchdog task still running; failure count unchanged | F-09 |

**Caution on event queries.** Events were queried by `payload_workflow_id`. Worker and workflow events carry a workflow id, but `execution.*` events carry `execution_id`, so a zero count for an `execution.*` event under that query proves nothing, and no finding relies on one.

**Result.** F-01, F-05, F-07 and F-12 hold by unchanged source. F-02 to F-04, F-06, F-08 to F-11 are reproduced by the re-run probes. F-13 was re-read on the changed files (table above). F-14 needs a correction: `core/verification` does not exist on `main`, so a search for importers there is vacuous; the meaningful search is the one on the branch tip `3ba858a`, where nothing outside the package, its tests and the docs imports it. HTTP-level behavior was not re-run, because the full dependency set is not installed here, and only the six test files above were run.

**Where the probes are.** Four throw-away scripts, not in the repository, delivered with this revision with their SHA-256: `probe_main.py` `a761827d450591ddf2d0589b0a65428c5c1703a52f1b1ec4b19b66bfdd87e395`; `probe_main2.py` `dc69e68f7818a77b09611fdf6c5a2cfd3c58805d6836fdd18efa6a016535110e`; `probe_main3.py` `e1aee93306461167996380d5dd783e525fee780bd6897ee3511d134c6ad1154c`; `probe_main4.py` `5ef869ee74f6749e0a65b937b799582a2750e01513e116eb9ee7c0e51a9f23ed`. Turning them into repository tests would be remediation or verification work with its own authorization.

---

## 19. Criterion 23: reconciliation after reading the pack and the Q4 brief in full

Both documents were read in full in this session: the Q4 brief "Verification 3C-B: Q4 queryable non-conclusion brief" at rev 13 and the pack "Verification 3C-B: Q2 and Q5 decision pack" at rev 28. Their text was compared with this brief's sections 1 to 10 for status, labels, decision identifiers and the D6 wording. Nothing in either document was edited.

| Check | Result |
| --- | --- |
| Status and acceptance | All three documents say analysis only and nothing accepted; Q2-a stays a candidate and Q2-g open; D1 to D10 and ODI-3C-B-01/02/03 are unchanged. AGREE |
| D6 wording | The Q4 brief (A1, section 3) and this brief (section 3) treat the tracker's wording as the source-established one and "independently typed and queryable" as pre-ratification (Q4-a). The pack's D6 bullet was corrected and its header carries a caveat. AGREE, with residual R-1 |
| Scope of "crash" (Q4-b) | The ledger row Q4-b (section 10.3) refines C2 in this brief: do not extend D6's pairing to timeout, tool failure and budget exhaustion by assumption; govern the other causes by D7; mark the built rule's UNVERIFIABLE-only extension as an implementation judgment pending Q4-b1 to Q4-b5. Sections 3, 6 and 9 here say the same. The pack's first scenario ("a non-conclusion with the cause (TIMEOUT)") takes no position on D6's scope. AGREE |
| Labels and identifiers | Q4-a to Q4-i belong to the Q4 brief; this brief uses Q4-b1 to Q4-b5 below Q4-b only. The Q4 brief's section 10.2 maps the review's own labels. No collision found. AGREE |
| `resume()` correction of 2026-10-19 | Present in the pack (rev 27) and the Q4 brief (rev 13): only RUNNING and CANCELLED nodes are reset, FAILED is terminal and cached. This agrees with F-06, where the failed node stays FAILED in the checkpoint. AGREE |
| Identity (DEBT-015) | The pack (section 2.3) and the Q4 brief (section 6) say DEBT-015 is still open. F-04 adds runtime evidence the pack lists as unverified: a per-attempt `attempt_id` exists on `main`, is overwritten on the node, and is absent from events. EXTENDS, no conflict |
| Writer of the record when a verifier crashes (Q4-h) | The ledger names the supervising execution boundary as plausible, recording an observed fact only. F-05, F-09, F-10, F-12, F-15 and F-16 show that no component today detects an abnormal termination and that some reports are swallowed or mask the cause. EXTENDS, no conflict (R-2) |
| Q5 coverage content | Counts targets, not attempts; unrelated to Q4-b. NOT APPLICABLE |

**Residuals.** R-1: the pack still says "D6's queryable non-conclusion" or "independently typed and queryable" in Q2-e (section 2.7), in the Q2-a candidate disposition and in the Q4 row of its section 4; only its header note qualifies them, and the Q4 brief's candidate C5 asks for a rewording. R-2: the Q4 ledger carries none of the runtime evidence in sections 12 and 20. Neither residual contradicts this brief. Closing them means editing the other two Docs, which this task did not do.

**Result.** On this reading the Q4-b treatment in this brief and in the Q4 ledger agree, and no contradiction was found. That is the finding of one reader without an independent review, so criterion 23 moves from BLOCKED to ADDRESSED in section 22 and no further.

---

## 20. Cancellation and reporting audit: remaining gaps, F-15 to F-17 and an amendment to F-01

Audited on `main` `4a4783c`. "Executed" means a throw-away probe on an isolated copy (`probe_main4.py`, `probe_main5.py`, delivered with this revision); "source" means reading only.

| ID | Behavior and evidence | Status | Relevance and effect |
| --- | --- | --- | --- |
| F-01 amended | F-01 said no structured cause exists. That was too strong. `WorkerResult` carries an optional `execution_detail: Optional[ExecutionOutcome]` (`core/workers/base.py:138`) whose `failure_type` is a `FailureType` with nine members: SUCCESS, COMPLETED\_WITH\_PARTIAL\_OUTPUT, STALLED, HARD\_DEADLINE, CANCELLED, PROVIDER\_FAILURE, EMPTY\_RESPONSE, VALIDATION\_ERROR, OTHER\_FAILURE (`core/runtime/execution_outcome.py:19-33`), plus a `retryable` flag. It is built at one real call site, the model router's streaming path (`core/model_router.py:186`); the repository's own comment says the live worker path does not read it (`execution_outcome.py:96-121`), and it is deliberately not restored on resume (`core/workflow/runtime.py:115-123`). Executed: `execution_detail` was `None` for a returned failure, an exception in `_run`, an unknown worker and an asyncio cancellation. The graph node has a separate free-text `failure_type` (`core/runtime/execution_graph.py:43`), which the watchdog sets from the cancel reason (`core/runtime/watchdog.py:192-194`). | CONFIRMED (source, executed) | A classification type exists but no worker failure path populates it, and none of its members is named for a tool or a verifier. Any mapping to the verification causes would be new, and `TOOL_FAILURE` still has no referent (Q4-b4). Replaces F-01 in section 12 |
| F-15 | The emitters differ on an event-store outage. Worker, workflow and orchestrator emitters catch and log it (`core/workers/base.py:429-439`, `core/orchestrator.py:177-185`, `core/workflow/runtime.py:914-922`); `ProgressMonitor._emit` does not (`core/runtime/progress.py:55-73`). Executed with the store failing for chosen event types: all events failing made `execute()` raise `OSError` from `progress.py:34` and `:57` before any node ran; only `worker.*` failing left the failed result intact but persisted no `worker.failed`; only `execution.node.failed` failing returned the error "Unexpected workflow error: event store unavailable" in place of the node's own error "boom"; only `workflow.*` failing kept "boom". | CONFIRMED (executed, once per variant) | Q4-h and criteria 9, 10: what happens when the record cannot be written depends on which emitter fails, and the real cause can be replaced. Limitation, unaccepted; the `execute()` raise contradicts its "never raises" contract. Possible defect, not registered |
| F-16 | The watchdog deadline is cooperative. Executed: with a 1.0 s hard ceiling and a worker that sleeps 3.0 s without polling the token, the run took 3.0 s, the token was cancelled with the reason "execution hard\_deadline", the workflow returned `success=False` with "Workflow cancelled", yet the node result was `success=True`, the last checkpoint held the first node COMPLETED and the second PENDING, and the second node never ran. No node was marked CANCELLED. | CONFIRMED (executed, one run) | A timeout signals but does not stop the work; a result produced after the deadline is recorded as a normal success on the node, and only the workflow-level result shows the cancellation. Bears on Q4-b2 and on late results (criterion 16). DEBT-015 sub-item 8 covers attempt supersession, not lateness. Limitation, unaccepted |
| F-17 | Preemptive timeouts (`asyncio.wait_for`) exist at the single model call (`core/runtime/limits.py:18-58`, used by `core/provider_mesh.py:169` and `core/learning/evaluator.py:35`), at skill execution (`core/skills/skill_interface.py:109`, bounded by `metadata.timeout`) and in the stub sandbox backend (`core/sandbox/backends/stub_backend.py:58`). Two others are not work timeouts: a 1.0 s backpressure acquire (`limits.py:73`) and a 30 s stream-queue read (`interface/api.py:664`). None wraps `Worker.execute`, `ExecutionRuntime.invoke`, `WorkflowRuntime`, `SupervisorWorker` or `Orchestrator.handle`. | CONFIRMED (source search for `wait_for(` and `asyncio.timeout(`; other timeout mechanisms were not searched) | Separates a missing timeout in one function from the whole path: timeouts exist at three inner layers and are cooperative above them (F-07, F-16). Bears on Q4-b2 |

**Orchestrator and API cancellation path (source only).** `core/orchestrator.py` has only `except Exception` and `except RuntimeError` handlers (lines 142, 183, 364, 618, 641, 659, 769, 855, 891, 909). A search of `core` and `interface` for `CancelledError`, `BaseException` and `.cancel()` found handling only in watchdog and service shutdown, streaming in `core/model_router.py`, semaphore and transaction bookkeeping that re-raises (`core/runtime/resilience.py:163`, `core/context.py:163`), and `Worker.execute`. `Orchestrator.close()` cancels background tasks (`orchestrator.py:162-169`), which is shutdown and not query cancellation. A cancelled query therefore reaches the workflow layer unhandled and is absorbed or propagated as F-08 and F-09 describe. `handle()` and the HTTP layer were not run under cancellation.

**Persisted state after cancellation.** In the one run in F-16 the checkpoint shows the completed node COMPLETED and the unstarted one PENDING, with no CANCELLED state. The checkpoint after an asyncio cancellation (F-09) was not captured, and `resume()` after either case was not run.

**DEBT-015 sub-items.** The register row (`KNOWN_ISSUES.md:35`) calls the work "researched and proposed, not implemented", Medium severity, with no functional regression today (REPORTED). Against the code:

| Sub-item | What the audit saw |
| --- | --- |
| 1 stable operation identity end to end | `root_operation_id` is set on `WorkflowDefinition` (`core/workflow/definition.py:138`) and by the compiler (`core/cognitive/compiler.py:263`), but `core/workflow/runtime.py` never reads it; worker events carry `task_id`, `worker_id` and `workflow_id` only. Not end to end |
| 2 `ExecutionAttempt` as a record | An attempt is an `attempt_id` plus an `attempts` count on the node state, and only the last `attempt_id` survives (F-04). Not a record |
| 3 `ExecutionSnapshot` | Not examined |
| 4 extended failure taxonomy | `FailureType` exists with nine members at the model-call layer and has none of the proposed ones; it is not populated on worker paths (F-01 amended) |
| 5 `RecoveryDecision` layer | No class of that name found. Recovery is the node `error_branch` and `RetryPolicy` (F-06) |
| 6 checkpoint persistence | The register marks it resolved through DEBT-003; checkpoints were saved per node in the probes, which is consistent |
| 7 retry and idempotency for side effects | Not examined |
| 8 stale-attempt rejection | Nothing rejects or flags a result that arrives after cancellation or a deadline (F-16) |
| 9, 10, 11 worker and capability integration, inspection UI | Not examined |
| 12 durable cross-attempt history | Events persist per attempt under distinct `task_id` values, but the node state keeps one attempt and no record links them (F-04) |

**Still not done.** Running `Orchestrator.handle()` and the HTTP layer under cancellation (the full dependency set is not installed here); `resume()` after a cancelled or deadlined run; the checkpoint after an asyncio cancellation; cross-process crashes; DEBT-015 sub-items 3, 7, 9, 10 and 11.

---

## 21. Criterion 12: multiple failures

Criterion 12 asks that several failures are not collapsed into one cause. This section records what the built contract can carry and what the runtime shows. It states no rule and accepts no decision.

**What the built contract can carry (OBSERVED on `3ba858a`).** A result holds at most one cause: `CriterionResult.execution_failure` and `VerificationResult.execution_failure` are each an `Optional[VerificationExecutionFailure]` (`core/verification/criterion_result.py:154`, `core/verification/verdict.py:50`), type-checked as a single enum value (`criterion_result.py:174-180`) and valid only on an ATTEMPTED result whose verdict is UNVERIFIABLE (`criterion_result.py:113,194`, `verdict.py:53`). A second cause in the same result has no field to live in; it would need another result, an event or free text. How the verification-level cause relates to the per-criterion ones is not defined, because aggregation (§46) is open (Q4-g, section 8). This is a fact about the package contracts; no route runs a verification (F-14).

**What the runtime shows (OBSERVED, executed on `4a4783c` unless noted).** Several failures already co-occur in one run, and where a single field carries them, one is lost.

| Case | What survives | Finding |
| --- | --- | --- |
| A node fails and an error branch recovers | the node record stays FAILED, the workflow result reads success: two facts, both kept, in different places | F-06 |
| A node fails twice and succeeds on the third attempt | the two failures survive only as events under distinct `task_id` values; the node keeps the last attempt | F-03, F-04 |
| A cancellation is followed by a retry | the later attempt's outcome can stand while the cancellation is visible only as a `worker.cancelled` event | F-08 |
| A node fails and the event store then fails | one error string carries both, and it holds only the later one: "boom" was replaced by "Unexpected workflow error: event store unavailable" | F-15 |
| A deadline passes and the worker later succeeds | the workflow reports "Workflow cancelled" while the node reports success | F-16 |

No test asserts any multi-failure behavior; the replacement in the fourth row is untested.

**What is not established.** No source read defines a precedence among causes, whether causes accumulate in order, or whether a result must name a primary one. Which combinations a verifier could produce is unknown, because none runs in any route.

**Considerations, not decisions (RECOMMENDATION).** Any rule the owner adopts for Q4-b3 or Q4-h should say whether a result may name more than one cause and, if only one, which fact carries the others. The F-15 case shows a concrete risk to design against: a failure of the reporting path must not overwrite the original failure.

**Effect on the closure matrix.** Criterion 12 moves from NOT ADDRESSED to PARTIALLY ADDRESSED: the constraints and the evidence are written, and the policy is still an owner decision.

---

## 22. Revision 3 status, closure-matrix changes, integrity check and log

**Status.** REVISION PREPARED. The audit is not complete: the gaps listed at the end of section 20 remain. The revision is not VALIDATED, because no independent review has read it. The transfer is not complete, because the three Docs are not in the repository (section 17). The mission is not closed. This status replaces the one in section 16.

**Closure matrix changes (the 26 criteria of section 15).**

| Criterion | Rev 2 | Rev 3 | Why |
| --- | --- | --- | --- |
| 12 multiple failures | NOT ADDRESSED | PARTIALLY ADDRESSED | Section 21 records the constraints and the evidence; the policy remains an owner decision |
| 23 brief and ledger agree | BLOCKED | ADDRESSED | Both Docs read in full; no contradiction found; residuals R-1 and R-2 recorded (section 19). One reader, no independent review |
| 17 D1's failure-reporting path | ADDRESSED, D1 identity unconfirmed | ADDRESSED | The identity is now confirmed by owner direction (section 17); the contract choice stays open |
| 9, 10, 11, 16, 18, 19 | PARTIALLY ADDRESSED | PARTIALLY ADDRESSED | New evidence in F-15 to F-17 and the DEBT-015 table; `handle()` and HTTP under cancellation, `resume()` after cancellation and several sub-items are still untraced |
| All others | as in section 15 | unchanged |  |

The totals become 12 ADDRESSED, 14 PARTIALLY ADDRESSED, 0 NOT ADDRESSED and 0 BLOCKED. That is not closure: 14 criteria are partial, and none of the open decisions Q4-b1 to Q4-b5 or the D1 contract choice is taken.

**Errata and supersessions.** Sections 1 to 16 are kept as written. Where they are overtaken:

| Where | What it said | Corrected by |
| --- | --- | --- |
| Section 12, F-01 | No structured cause exists | Section 20, F-01 amended: an optional `execution_detail` exists but no worker failure path populates it |
| Section 12, F-14 | No importer on `main` and on the branch | Section 18: the package does not exist on `main`, so only the branch search is meaningful |
| Section 13 | D1 identity UNCONFIRMED | Section 17: confirmed by owner direction; section 13's description of the candidate meanings stands |
| Section 16, Validation done | The hashes of the 11 lists and tables cover structure only; unchanged text DERIVED | See the integrity check below |
| Section 16, Status and blockers 2 and 3 | D1 unconfirmed; ledger agreement blocked | Sections 17 and 19 |

**Integrity check of revision 1.** At platform revision 17 the Docs outline lists all 49 revision-1 blocks in their original order with the hash recorded at revision 1 and no revision stamp later than 1; the only block inserted among them is the pointer paragraph after the Status paragraph. For each of the 11 lists and tables, a view of changes since revision 1, taken at platform revision 10, returned the container stamped revision 1 with every child folded as unchanged. This rests on the service's own change tracking. It is stronger than the earlier inference from the operations I sent, and it is still not a byte-for-byte comparison of exported text, which the export limit in section 17 prevents. Edits after revision 17 added only the new section 22.

**Revision log.**

| Revision | Date | Change |
| --- | --- | --- |
| 3 | 2026-10-29 | Sections 17 to 22 appended. Records the owner directions, revalidation on `main` `4a4783c`, the criterion 23 reconciliation, findings F-15 to F-17, the F-01 amendment, the DEBT-015 table, criterion 12, and the status and errata above. Sections 1 to 16 not edited. Authority: the owner message of 2026-10-29 supplied in this session |

**Next steps (RECOMMENDATION, not decisions).**

1. The owner exports the three Docs from claude.ai and uploads the files, so the manifest, the hashes and a docs-only branch can be prepared (section 17).
2. Install the full dependency set in an environment with enough disk, then run `Orchestrator.handle()` and the HTTP layer under cancellation, `resume()` after a cancelled or deadlined run, and the checkpoint after an asyncio cancellation.
3. Arrange an independent review of sections 12 to 22 against the code at `4a4783c`.
4. Decide whether F-03, F-09, F-11, F-15 and F-16 become registered issues; any fix is separate work with its own baseline, owner and review target.

**Late note: second ref advance.** After the checks in this section, `main` advanced again to `16d663a` (5 commits, all dated 2026-10-29). They change `KNOWN_ISSUES.md` (register reconciliation for DEBT-003, DEBT-015(7), DEBT-028 and DEBT-044; the FZ-01 row and the D1 text are unchanged and now sit at lines 122 and 130, and the DEBT-015 row at line 39) and tests; no audited source file changed. One new test, `tests/test_workflow_crash_restart_subprocess.py`, hard-kills a real child process mid-node and resumes in a fresh one. By its assertions it pins that the completed node is not re-run, that the interrupted node starts twice and completes once, and that the last node runs once; it does not assert any failure record for the killed attempt. Read only, not executed here. So the row "silent process death" in section 12 and the item "cross-process crashes" in section 20 are partly overtaken: resume after a real kill is now tested on that commit, while detection and recording of the killed attempt remain untested. The audit baseline stays `f13bfde`, with revalidation on `4a4783c`.
