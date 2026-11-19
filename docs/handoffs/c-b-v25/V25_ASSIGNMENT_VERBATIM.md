<!-- Preserved VERBATIM from the owner's assignment message. Do not edit. It is the operative specification of the remaining work. -->

# Assignment: C-b v2.5 — Complete design correction, independent verification and baseline preparation

## 1. Role

Act as a senior Python asyncio architect, concurrency specialist and independent software-design reviewer.

Your task is to take the supplied **C-b design v2.4** through another adversarial review, identify every remaining correctness and specification gap, investigate opportunities to strengthen the design, and produce a complete, self-contained **C-b design v2.5**.

This is a documentation and design assignment only.

Do not implement anything.

The objective is not to make v2.4 look acceptable. The objective is to establish whether its lifecycle contract can be made internally consistent, implementable, testable and operationally safe.

Challenge the previous reviewers' conclusions as well as the author's assumptions. Do not assume that a finding is correct merely because it appeared in an earlier review.

All findings must be independently reasoned and supported.

---

## 2. Authorization boundary — mandatory

The current authorization is DESIGN AND REVIEW ONLY.

Explicitly prohibited:

- Implementing C-b or any other stage.
- Modifying repository source, tests, configuration or documentation.
- Creating branches, commits or pull requests.
- Editing GitHub Actions workflows.
- Merging, rebasing, cherry-picking or closing PRs.
- Modifying the study or ADR-KERNEL-09.
- Changing deferred PRs.
- Authorizing C-e, C-a, C-b, C-c or C-d.
- Treating a recommendation as an owner decision.

You may perform read-only research and inspect publicly accessible source material where available.

Do not use GitHub credentials when public repository pages are sufficient.

No implementation files or design files are to be created. Deliver the complete design package in your response.

**A recommendation, DECIDED status, or proposed design is not ACCEPTED until explicitly accepted by the owner.**

The authorization for a later implementation stage will require a separate request and a fresh baseline verification.

---

## 3. Source material and baseline

The full C-b design v2.4 is supplied in the preceding conversation. Treat it as the primary design input.

If the full source text is not available in your working context, request the original document rather than reconstructing missing normative requirements from memory.

The baseline concerns:

- `GraphExecutionWatchdog`.
- `core/runtime/watchdog.py`.
- Its `start()`, `stop()`, `_advance()` and finalizer lifecycle.
- Constructor configuration and validation.
- New tests for the watchdog.

The following are out of scope for C-b:

- `inspect()` and request-versus-failure semantics (C-g).
- `WorkflowRuntime` call-site corrections (C-d).
- `core/runtime/execution_watchdog.py::ExecutionWatchdog`, which is a different class.
- PR #81, which remains frozen.
- The study and ADR-KERNEL-09.
- C-e's independent evidence package.

Do not expand C-b into a general runtime redesign.

### Source verification

Perform a read-only source/provenance check where possible.

Identify:

1. The exact repository `main` commit used for source claims.
2. The exact `runtime.py` source revision used for R1.
3. The actual three `stop()` call sites.
4. The relevant watchdog source revision.
5. The exact `ci.yml` blob identity, if available.

If the source cannot be independently accessed or verified, record the relevant claim as UNVERIFIED.

Do not invent a source SHA, file hash or test result.

A new baseline check is mandatory before any separately authorized implementation stage. A historical main SHA must not be presented as a fresh baseline.

---

## 4. Preserve the normative model while correcting it

The following attributes must be accounted for:

`_state`, `_task`, `_loop`, `_cancel_requested`, `_escalated`, `_escalate_at`, `_abandon_at`, `_timers`, `_outcome`, `_finalized`, `task_result`, `child_exception`.

Configuration:

- `stop_timeout`
- `cancel_grace`
- `MAX_STOP_ENVELOPE_S`

Both configuration values must be keyword-only, finite, non-negative real numbers and must reject bool.

The total envelope must be validated.

The defaults of 1.0 seconds remain provisional.

Q-B9 remains OPEN.

The accepted maximum must be compatible with whichever defaults are eventually accepted. Preserve backward compatibility unless an explicit alternative is recommended and justified.

### 4.1 State model

Review and provide a complete normative definition of:

| State | Required meaning |
|---|---|
| IDLE | Never started; no owned task or supervision state |
| RUNNING | Owned child and owner loop established |
| STOPPING | Initial cancellation requested; deadlines and supervision established |
| ABANDONED | Supervision deadline exhausted; child may still be pending |
| STOPPED | Finalization completed or NOT_STARTED outcome recorded |

Correct any inconsistent state requirements.

In particular, do not require that the abandonment timer callback itself must have fired before ABANDONED is valid. Define the state according to the actual supervision conditions.

Define precisely when `_task` is retained and cleared, and when ownership begins and ends.

### 4.2 Existing invariants

Preserve the intent of all the following invariants, but correct their wording where necessary.

- I1: Single-use lifecycle.
- I2: One owner event loop; not thread-safe.
- I3: Watchdog owns task creation, cancellation, awaiting, retrieval and clearing. `stop()` creates no new task and does not mutate graph, events or token.
- I4: At most one initial cancellation and one escalation.
- I5: The caller's `CancelledError` propagates unchanged.
- I6: One guarded finalizer.
- I7: Sticky, immutable outcome once recorded.
- I8: A child already done at the decision point wins.
- I9: Lifecycle decision code is await-free.
- I10: No wait beyond the permitted abandonment boundary.
- I11: At most one ABANDONED transition.
- I12: A child cannot stop its own watchdog.
- I13: Precisely bounded exception propagation.
- I14: Supervision occurs only through `_advance()`, timers and stop callers, without an extra driver task, shield or uncancel.
- I15: One explicitly defined clock-resolution and deadline contract.

Every invariant must be testable.

Do not retain an invariant merely because it existed in v2.4. Where its wording is inconsistent with achievable asyncio behaviour, explain the correction.

---

## 5. Mandatory adversarial investigation

The next revision must address every item below.

### F-01: Natural completion before the done callback

The v2.4 `_advance()` checks `_cancel_requested` before checking `task.done()`.

This can return TIMED_OUT for a naturally completed child whose registered done callback has not yet executed.

Required investigation:

- Establish the failure trace.
- Correct the normative algorithm.
- Check both natural completion and cancellation completion.
- Add a test that deliberately places completion before callback execution.
- Verify that `stop()` itself returns the correct sticky outcome.

The preferred ordering is:

1. Check finalization.
2. Check owned-task existence.
3. Check task completion and finalize if done.
4. Check cancellation-request state.
5. Process escalation.
6. Process abandonment.

Prove that the resulting ordering satisfies all states.

### F-02: Late caller and absolute deadlines

The v2.4 `stop()` waits before calling `_advance()`.

This conflicts with Option B in Q-B8.

Required investigation:

- Advance supervision before any wait.
- Reconcile the already-completed task first.
- Reuse the persisted deadlines.
- Advance overdue escalation immediately.
- Advance overdue abandonment immediately.
- Only wait while the task remains pending, the state remains STOPPING and abandonment is not due.
- Advance again following a normal wait return.

Do not grant a late caller an additional scheduling turn.

Provide normative pseudocode and trace diagrams for:

1. A late caller after escalation but before abandonment.
2. A late caller after both deadlines.
3. A caller while the abandonment timer has not yet executed.
4. A child already done but whose callback is pending.
5. Concurrent callers observing the same deadline.

### F-03: Clock-resolution semantics

Independently investigate the documented `asyncio.call_at()` and `call_later()` behaviour.

Compare two contracts:

**Model A — Early-tolerant**

`due(t) := loop.time() + CLOCK_RES >= t`

This permits effective deadlines up to one clock resolution early.

**Model B — Not-before**

A timer that fires early is compensated or re-armed so that the actual nominal deadline is not crossed prematurely.

For both models, establish:

- Escalation behaviour.
- Abandonment behaviour.
- Timer count.
- Late-caller behaviour.
- Exact-deadline behaviour.
- Sub-resolution grace behaviour.
- Zero-timeout behaviour.
- Behaviour when both deadlines become due in one `_advance()` invocation.

Make a recommendation and explain the trade-off.

Do not silently alter I15.

The specification must say whether a configured grace interval is a true minimum elapsed duration or an early-tolerant scheduling threshold.

### F-04: ABANDONED and child termination

Correctly distinguish:

1. Cancellation requested.
2. Cancellation escalated.
3. Supervision expired.
4. Child terminated.
5. Child finalized and reaped.

B2 cannot force a coroutine to terminate.

Investigate the child that suppresses both cancellation requests indefinitely.

The resulting state must be explicit:

- ABANDONED.
- TIMED_OUT outcome.
- Task retained.
- Finalizer not yet completed.
- Ownership retained.

Do not promise task termination, reaping or leak freedom merely because the supervision deadline expired.

### F-05: Event-loop liveness

Define the conditions under which B2 works.

The event loop must remain operational and able to execute callbacks.

Investigate:

- Event-loop starvation.
- Long synchronous blocking operations.
- `loop.stop()`.
- `loop.close()`.
- Application shutdown.
- Timer callbacks discarded during loop closure.

State clearly that timer-driven supervision is not hard real-time supervision.

### F-06: Process shutdown and indefinitely abandoned tasks

Investigate the actual shutdown behaviour of `asyncio.run()` and supported runner implementations.

Account for the fact that outstanding tasks are cancelled and awaited during shutdown.

Determine what happens if an abandoned child continues suppressing cancellation.

Define a shutdown contract for the owning runtime.

Compare:

- Waiting indefinitely for child completion.
- Reporting and retaining outstanding tasks.
- Controlled process termination.
- Process-isolated execution.

Do not force a process-isolation redesign into C-b. If it is necessary for hard termination, identify it as a separate architectural limitation or future stage.

### F-07: Finalizer transaction and failure recovery

The v2.4 finalizer sets `_finalized = True` before diagnostic retrieval and cleanup.

Investigate the half-finalization failure scenario.

Specify:

- Guard behaviour.
- Pending-task precondition.
- Finalization commitment point.
- Timer cancellation.
- Task classification.
- Exception retrieval.
- Child diagnostic storage.
- Outcome commitment.
- Task clearing.
- Final state transition.
- Logging.
- Repeated and late callbacks.

Compare a fully non-raising guarded finalizer with a two-phase finalization protocol.

Do not introduce unnecessary lifecycle fields. If an intermediate state or flag is necessary, justify it.

Define the behaviour if:

- Timer cancellation fails.
- Diagnostic retrieval fails.
- Logging fails.
- A callback arrives during or after finalization.
- A finalization operation has already partially completed.

The finalizer must never leave an irrecoverably inconsistent state while claiming successful finalization.

Preserve sticky TIMED_OUT after a late child completion.

### F-08: Transactional supervision setup

The first stop request establishes two timers and requests child cancellation.

Define failure-safe ordering.

Investigate failures at:

1. Deadline calculation.
2. First `call_at()`.
3. Second `call_at()`.
4. Initial `task.cancel()`.
5. Rollback timer cancellation.

For every failure, define:

- State before the operation.
- State after the failure.
- Whether cancellation has been requested.
- Which timer handles remain.
- Whether rollback is possible.
- Which exception propagates.

A partially installed timer configuration must never be represented as a fully established B2 supervision contract.

Update I13 to cover any newly permitted infrastructure exceptions.

### F-09: `start()` and eager task factories

Produce a normative `start()` algorithm.

Specify:

- Single-use checks.
- Event-loop acquisition.
- Owner-loop binding.
- State initialization.
- Task creation.
- Ownership assignment.
- Done-callback registration.
- Creation failure.
- Coroutine cleanup if creation fails.
- Eager execution behaviour.
- Immediate child completion.
- Immediate child exception.

Investigate the Python 3.12+ eager task factory.

Choose whether it is prohibited or supported.

If prohibited, define how the supported runtime environment enforces the restriction.

If supported, prove that the child cannot execute against an incompletely initialized watchdog.

T-B23 must reflect the selected contract.

### F-10: Cancellation accounting and structured concurrency

Document the implications of a child suppressing `CancelledError` without clearing its cancellation state.

The watchdog must not call `uncancel()`.

Test a child that:

- Propagates the first cancellation.
- Suppresses the first cancellation.
- Suppresses both cancellation requests.
- Suppresses cancellation while retaining outstanding cancellation requests.
- Completes after ABANDONED.

The design must not assume it can repair child-owned cancellation accounting.

### F-11: Abandoned-child observability

Define how the owner knows that an ABANDONED child eventually completes and is finalized.

Determine whether existing internal state is sufficient or whether a narrowly scoped observation mechanism is needed.

Do not add a background driver task.

Do not add graph events or token mutation.

If a new awaitable or notification is recommended, explain its interaction with I3, I14 and the C-d boundary.

### F-12: Exception contract and I13

Prepare a complete exception matrix.

Include:

- Wrong-loop `RuntimeError`.
- Self-call `RuntimeError`.
- Non-finite computed deadline.
- Invalid configuration.
- Caller `CancelledError`.
- Child cancellation.
- Child exception.
- Timer installation error.
- Task cancellation failure.
- Finalizer diagnostic failure.
- Logging failure.

Explicitly distinguish exceptions propagated by `stop()` from child exceptions retrieved internally.

Do not promise a narrow exception whitelist that the normative algorithm cannot satisfy.

### F-13: Task retention, memory ownership and garbage collection

Establish:

- Why the watchdog owns a strong task reference.
- When timers hold references to the watchdog.
- How finalization releases timer references.
- When `_task` is cleared.
- Whether `_loop` is retained after STOPPED.
- Whether callbacks can still retain the object.
- What happens if an abandoned child never finishes.

Distinguish expected retention, completed cleanup and unexpected leaks.

---

## 6. Reconcile previous review findings

Do not omit any of the previous findings.

At minimum, explicitly close or retain as OPEN:

1. IDLE transition and T-B27.
2. B2 caller-cancellation contract.
3. Natural-completion race in `_advance()`.
4. Late-takeover ordering in `stop()`.
5. I15/remaining-time inconsistency.
6. ABANDONED invariant.
7. Normative `start()` specification.
8. Transactional timer installation.
9. I14 never-raising guarantee.
10. Eager execution compatibility.
11. Indefinite abandoned-child retention.
12. Event-loop and process shutdown.
13. Finalizer half-completion.
14. Q-B8 scheduler-order wording.
15. Q-B9 real latency evidence.
16. Q-B10 explicit owner decision.
17. Q-B11 release control.
18. R1 exact source provenance.
19. T-B16 timer-count semantics.
20. T-B25 cooperative/non-cooperative child variants.
21. T-B30 precise clock-resolution testing.
22. Absence of production and integration evidence.

Provide a disposition table containing the old finding, correction, evidence required and final status.

---

## 7. Research requirements

Before recommending the revised architecture, investigate the underlying technical contracts.

### Official Python sources

Prioritize:

- Python 3.11 asyncio Task documentation.
- Python 3.12 asyncio Task documentation.
- Supported-version asyncio event-loop documentation.
- `Task.cancel()`, `Task.cancelled()`, `Task.cancelling()` and `Task.uncancel()`.
- `asyncio.wait()` versus `asyncio.wait_for()`.
- `loop.call_at()` and `loop.call_later()`.
- TimerHandle cancellation.
- Task creation and eager execution.
- Event-loop shutdown and `asyncio.run()`.
- CPython implementations of Tasks, waiting primitives, runners and event-loop timers.

Check version-specific differences.

Do not use Python 3.15 or development-branch behaviour as proof of Python 3.11 behaviour without verification.

### Upstream implementation evidence

Investigate relevant CPython source and test cases.

Inspect issues or discussions that materially relate to:

- Cancellation races.
- Suppressed cancellation.
- Timer resolution.
- Callback ordering.
- Eager task execution.
- Pending-task cleanup.
- Event-loop shutdown.

### Research papers

Search for relevant research on asynchronous cancellation, structured concurrency and resource ownership if it materially adds to the design.

Do not force academic papers into a Python API contract where official specifications and implementation evidence are stronger.

State explicitly if no research paper changes the conclusions.

### Citation requirements

Every external technical claim must be attributable to a source.

Separate:

- Documented API guarantee.
- CPython implementation detail.
- Behaviour verified in tests.
- Design inference.
- Unverified platform behaviour.

Do not turn an implementation detail into a universal asyncio guarantee.

---

## 8. Q-B8, Q-B9, Q-B10 and Q-B11

Keep owner authority separate from engineering recommendations.

### Q-B8 — Late takeover

The recommendation remains Option B unless new evidence disproves it.

However, change the explanation to:

The first observed `task.done()` state at an `_advance()` decision point determines completion precedence. No extra scheduling turn is granted. Exact concurrent boundary ordering is not guaranteed.

Do not claim scheduler independence.

### Q-B9 — Envelope

Keep OPEN.

Retain the provisional 1.0-second defaults unless evidence warrants a change.

Define a real measurement protocol for the production watchdog.

Separate functional state verification from cancellation-latency measurement.

Do not accept a 30-second candidate based solely on analogy with external container shutdown defaults.

Ensure the accepted maximum envelope can accommodate the accepted defaults.

### Q-B10 — Timer-driven supervision

Recommend B2 only if:

- Timer installation is failure-safe.
- The owner loop remains operational.
- The task remains owned after abandonment.
- Indefinite pending behaviour is defined.
- Shutdown consequences are acknowledged.
- The design does not claim forced termination.

Option A must remain documented for comparison, but do not silently revert to it.

Only the owner can accept B2.

### Q-B11 — C-b before C-d

Recommend back-to-back landing unless an enforceable release hold exists.

An acceptable release hold must cover:

- Production release.
- Deployment.
- Packaging and distribution.
- Any other route by which C-b-only behaviour could reach users.

An informal warning is insufficient.

Only the owner can make this decision.

---

## 9. Integration limitation L-1 — preserve exactly

The three existing `WorkflowRuntime` call sites remain unchanged in C-b.

Preserve the three separate failure states.

**Site :523 — validation failure**

At the join:
- Graph created.
- Root RUNNING.
- Status event emitted.
- `_total_failures` incremented.
- No `workflow.started`.
- No execution terminal events.
- No `workflow.completed`.

After caller cancellation:
- `execute()` raises `CancelledError`.
- Root remains RUNNING.
- Terminal workflow events remain absent.
- The failure result is lost.

**Site :568 — unexpected `_execute_from` exception**

At the join:
- `workflow.started` emitted.
- Node events through the failure.
- Root RUNNING.
- `_total_failures` incremented.

After caller cancellation:
- `execute()` raises `CancelledError`.
- Graph and events remain at their join state.
- No `execution.failed`.
- No `workflow.completed`.
- The failure result is lost.

**Site :649 — normal end**

At the join:
- Root is terminal.
- `execution.completed` or `execution.failed` emitted.
- `workflow.completed` has not yet been emitted.

After caller cancellation:
- `execute()` raises `CancelledError`.
- Execution appears complete at one level, while `workflow.completed` is missing.
- The result is lost.

Preserve these explicit restrictions:

- No cancellation-integration-closure claim.
- No claim that `WorkflowRuntime.execute()` still meets its never-raises contract.
- C-b alone is not a completed cancellation solution.
- C-d remains a required follow-on gate.

Correct the claim that B2 always reaps the child. It only does so when the child actually completes.

---

## 10. Test and acceptance plan

Preserve T-B1 through T-B30 from v2.4.

Do not delete difficult tests to make acceptance easier.

Retain their original purposes and exact state assertions. Correct only the cases whose assertions conflict with the selected v2.5 contract.

Add the following new test IDs, using different IDs if any already exist.

### T-B31 — Done task before done callback

Child completes naturally, but the done callback has not executed.

Call `stop()`.

Require:
- Correct finalization.
- No additional cancellation.
- Correct outcome.
- No false TIMED_OUT result.
- Exactly one finalization.

### T-B32 — Late caller before abandonment

Escalation deadline has expired, but the escalation timer callback has not yet performed the transition.

Call `stop()`.

Require:
- Immediate reconciliation.
- Escalation before waiting.
- No additional scheduling turn granted to the child.
- Original deadlines unchanged.

### T-B33 — First timer installation failure

Inject failure into the first `call_at()`.

Require no partial state transition and no unintended cancellation.

### T-B34 — Second timer installation failure

Allow first timer installation and fail the second.

Verify timer rollback, state consistency, task ownership and exception propagation.

### T-B35 — Initial cancellation failure

Inject failure in the child cancellation operation.

Verify that the watchdog never claims a cancellation request that did not succeed.

### T-B36 — Finalizer fault injection

Inject faults at each operation that could fail.

Require consistent retry or terminal failure semantics, never an irrecoverable half-finalized state.

### T-B37 — Eager task factory

Test supported Python 3.12+ eager execution.

Verify all start invariants and ownership relationships, or verify explicit rejection of an unsupported configuration.

### T-B38 — Same-time completion and timer callbacks

Exercise competing completion and timer callbacks.

Accept only outcomes permitted by the explicitly documented scheduler-boundary contract.

Never assert deterministic ordering where asyncio provides none.

### T-B39 — Sub-resolution grace

Exercise:

- Zero grace.
- Positive grace smaller than clock resolution.
- Grace equal to clock resolution.
- Grace greater than clock resolution.
- Both deadlines due in the same `_advance()` call.

Verify exact selected temporal semantics.

### T-B40 — Indefinitely pending abandoned child

A child suppresses both cancellation requests and remains pending.

Verify:
- ABANDONED.
- TIMED_OUT.
- Strong ownership.
- No false finalization.
- No false leak-free claim.
- Clear owner observability.

### T-B41 — Runtime shutdown interaction

Investigate the indefinitely pending child under the supported event-loop shutdown model.

Use a controlled subprocess timeout or an equivalent safe test harness so that an intentionally hanging shutdown cannot hang the whole test suite.

Do not disguise shutdown failure as watchdog success.

### T-B42 — Caller cancellation during `asyncio.wait`

Verify that caller cancellation:
- Propagates.
- Does not cause an extra watchdog cancellation.
- Does not cancel the owned child through the waiting primitive.
- Leaves timer-driven supervision active.

### T-B43 — Post-abandonment completion

Release the retained child after ABANDONED.

Verify finalization, result retrieval, timer cleanup and sticky TIMED_OUT.

### T-B44 — Wrong-loop and stopped lifecycle matrix

Test all states and owner-loop combinations, including marshalling through `run_coroutine_threadsafe`.

### T-B45 — Real cancellation-latency measurement

Measure actual production watchdog cancellation latency separately from T-B12 correctness checks.

Preserve:
- Environment.
- Python version.
- Operating system.
- Clock resolution.
- Workload.
- Repetition count.
- Raw observations.
- Summary statistics.
- Limitations.

Do not report toy measurements as production latency evidence.

### Important test accounting rules

Differentiate watchdog-owned timers from internal timeout handles used by `asyncio.wait()`.

Differentiate Task creation from Future creation.

Do not describe an intentionally retained ABANDONED task as an unexpected leak.

Use generous timing margins except when testing the exact selected clock semantics.

Use real watchdog tests for production claims and retain the toy strictly as algorithm evidence.

---

## 11. Evidence classification

Every claim in v2.5 must belong to one of these classes:

| Class | Meaning |
|---|---|
| Algorithm | Independent reasoning or isolated prototype outside the repository |
| Production | Executed against the actual `GraphExecutionWatchdog` |
| Integration | Executed through real `WorkflowRuntime` call sites |
| Source | Verified against a pinned repository source revision |
| External | Verified against upstream technical documentation or source |
| Unverified | Evidence unavailable or insufficient |

Do not promote a toy result to production evidence.

Do not promote a production watchdog test to integration evidence.

Do not promote documentation-based reasoning to runtime verification.

Preserve the distinction between algorithm, production and integration status throughout the complete design.

---

## 12. Required final v2.5 deliverable

Produce a complete self-contained document titled:

**C-b design v2.5 — corrected normative lifecycle and supervision baseline**

It must contain these sections:

1. Executive disposition.
2. Scope, exclusions and authorization boundary.
3. Baseline provenance and source evidence.
4. Seven original requirements and their final dispositions.
5. Complete attributes and configuration contract.
6. Complete state transition table.
7. All normative invariants.
8. Normative `start()` algorithm.
9. Normative `stop()` algorithm.
10. Normative `_advance()` algorithm.
11. Timer installation, rollback and scheduling semantics.
12. Clock-resolution and deadline contract.
13. Caller cancellation and concurrent callers.
14. Late takeover and boundary precedence.
15. Complete finalizer contract.
16. ABANDONED ownership, retention and shutdown.
17. Exception propagation matrix.
18. Runtime compatibility and task-factory requirements.
19. L-1 integration limitation.
20. Complete test matrix, retaining T-B1–T-B30 and additions.
21. Evidence classification and acceptance criteria.
22. Q-B8/Q-B9/Q-B10/Q-B11 owner-decision register.
23. Unresolved questions and residual risks.
24. v2.4-to-v2.5 change log.
25. Next-stage authorization requirements.

The document must be independently understandable. Do not require the reader to consult v2.2 or v2.3 to understand any normative requirement.

Include all required state tables, invariants, pseudocode, test definitions, exception contracts and evidence boundaries.

Do not omit a requirement simply because it is difficult to resolve.

If an issue cannot be resolved without an owner decision, keep it explicitly OPEN and provide alternatives.

---

## 13. Independent consistency checks

Before publishing v2.5, conduct at least three separate final passes.

### Pass A — Algorithm versus state model

For every algorithm branch, verify:

- Its preconditions.
- Its permitted mutations.
- Its resulting state.
- Its error behaviour.
- Its concurrency implications.
- Its interaction with timers and callbacks.

No pseudocode branch may violate the state table.

### Pass B — Invariants versus tests

For every invariant, identify at least one test that falsifies a violation.

For every test, identify the invariant or requirement it verifies.

Identify uncovered invariants explicitly.

No test may claim a result stronger than the design permits.

### Pass C — Lifecycle and shutdown

Trace the complete child lifecycle:

```text
IDLE
  |
  v
RUNNING
  |
  | stop request
  v
STOPPING
  |
  +---- child completes ------------> STOPPED
  |
  +---- escalation
          |
          +---- child completes ----> STOPPED
          |
          +---- deadline exhausted -> ABANDONED
                                          |
                                          +---- child completes -> STOPPED
                                          |
                                          +---- child never completes
                                                -> retained ABANDONED
```

Include natural child completion, child errors, caller cancellation, concurrent stops, loop shutdown and finalizer failure.

Demonstrate that no lifecycle path has an undefined owner, false success state, unretrieved exception or silently abandoned cleanup operation.

---

## 14. Output and reporting requirements

Present the work in this order:

**A. Independent findings**

Identify the defects, gaps and strengthening opportunities, with severity and evidence.

**B. Finding-disposition matrix**

For every finding from v2.4 and the previous reviews, report:

- Corrected.
- Partially corrected.
- OPEN.
- Rejected with evidence.

**C. Complete v2.5 design**

Provide the entire revised normative document, not just a list of changes or a patch proposal.

**D. Final acceptance assessment**

Choose one:

- READY FOR OWNER DECISIONS.
- NO PASS — ADDITIONAL DESIGN WORK REQUIRED.

Do not use ACCEPTED.

**E. Owner decisions**

Show the current recommendation for every decision, distinguishing recommendation from acceptance.

**F. Authorization status**

Explicitly state that implementation remains unauthorized.

Be exact about what was inspected, what was researched, what was executed and what remains unverified.

Do not claim that tests passed unless they were actually executed against the relevant implementation.

Do not claim that the repository changed.

---

## 15. Final quality standard

The result must meet all of the following:

- No hidden assumptions.
- No contradictory invariants.
- No ambiguous lifecycle transition.
- No unbounded promise based on cooperative cancellation.
- No implied forced task termination.
- No incomplete finalization contract.
- No partial timer-installation state without rollback.
- No deadline comparison inconsistent with the selected clock model.
- No incorrect claim of scheduler-independent boundary precedence.
- No untested task-factory assumption.
- No undefined shutdown ownership.
- No false leak-free statement.
- No conflation of algorithm, production and integration evidence.
- No accidental scope expansion.
- No implementation authorization.

The most important principle is this:

**The watchdog must guarantee only what its mechanisms can actually guarantee.**

It can request cancellation, escalate, detect supervision expiry, preserve sticky timeout semantics and retain ownership until completion.

It must not claim that it has terminated, reaped or cleaned up a coroutine that remains pending.

The final design must be strong enough that a separate implementer can follow it without making architectural decisions or inventing lifecycle semantics.

If it is not strong enough, report NO PASS.

End with the precise remaining owner decisions and the smallest next action. Do not initiate that action.
