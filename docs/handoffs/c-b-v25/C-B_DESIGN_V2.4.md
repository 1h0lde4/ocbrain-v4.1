<!-- C-b design v2.4 as submitted for owner review. Preserved verbatim as the INPUT that v2.5 must correct. Status: NOT approved; contains known defects (see handoff.md section 5/17, F-01..F-13). Not an accepted baseline. -->

# C-b design v2.4: self-contained baseline package

This is documentation and design only. Nothing is implemented, no files were created, and the study, the ADR and the deferred PRs are untouched. No stage is authorized. All prototype results come from a stdlib-only toy outside the repository and are algorithm evidence only.

## 0. Disposition of the seven requirements

| # | Requirement | Disposition |
|---|---|---|
| 1 | IDLE transition | Fixed (§4). My v2.3 pseudocode assigned locals (`state = STOPPED`). The toy used instance attributes, so the toy was right and the normative text was wrong. Reproduced on the toy: after the buggy `stop()` returns NOT_STARTED, a later `start()` **succeeds**. New test T-B27. |
| 2 | Caller cancellation vs escalation (R10) | Resolved by a recommended contract, B2 (§3), pending your decision Q-B10. Reproduced: with v2.3 a cancelled caller left `cancel_calls=1`, the watchdog STOPPING indefinitely, and a cancel-suppressing child never escalated or abandoned. |
| 3 | T-B25 and a combined test | T-B25 now has exact per-site states (§8). Added T-B28 (combined) and T-B29 (abandoned child's late completion). |
| 4 | ABANDONED | Defined in §6 and tested by T-B29. |
| 5 | R1 | Recorded as explicit temporary integration limitation L-1 (§8). |
| 6 | Q-B8 / Q-B9 | Q-B8's semantics are documented with the A/B comparison (§7). Q-B9 stays OPEN (§9). |
| 7 | Pinned inherited specs | This document restates the state table, invariants and finalizer in full. |

**A defect in my own v2.4 draft, caught before publishing.** asyncio runs timers whose time is within one clock resolution, so a timer can fire early (`end_time = self.time() + self._clock_resolution`, `base_events.py:1904`). With plain `>=` deadline comparisons, an early timer does nothing. I emulated a 30 ms resolution on Python 3.11.15 and 3.12.3. `stop()` returned `None`, the state stayed STOPPING, and abandonment was missed. Comparisons now tolerate the resolution (§4, I15, test T-B30). I did not verify the real Windows resolution here, so the relevance to Windows is UNVERIFIED. `ci.yml` has a Windows job on the deferred PR #94.

## 1. Scope

- **In scope:** `GraphExecutionWatchdog` lifecycle (`start`/`stop`/`_advance`/finalizer), keyword-only constructor configuration, and new test files, all in `core/runtime/watchdog.py`.
- **Out of scope:**
  - `inspect()` and request-versus-failure semantics (C-g);
  - the `WorkflowRuntime` call sites (C-d);
  - `core/runtime/execution_watchdog.py::ExecutionWatchdog`, a different class with a synchronous `stop()`;
  - PR #81 (frozen);
  - the study and the ADR.
- **Compatibility:** the constructor stays backward compatible, with new keyword-only parameters that have defaults. No existing test calls `start()` or `stop()` directly, so production evidence comes from the new tests.

## 2. Pinned normative model

### 2.1 Attributes

`_state`, `_task`, `_loop`, `_cancel_requested`, `_escalated`, `_escalate_at`, `_abandon_at`, `_timers`, `_outcome`, `_finalized`, and the diagnostics `task_result` and `child_exception`. The configuration is `stop_timeout` and `cancel_grace`.

### 2.2 Configuration

Both are keyword-only. Each must be a finite real number (not `bool`), and each ≥ 0. A **total** envelope `stop_timeout + cancel_grace ≤ MAX_STOP_ENVELOPE_S` is validated at construction. The value of `MAX_STOP_ENVELOPE_S` is open (§9). The defaults of 1.0 s each are provisional. Computed deadlines are validated for finiteness before any mutation.

### 2.3 State invariants (pinned)

| State | Required properties |
|---|---|
| IDLE | no task, loop, cancel request, escalation, deadlines or timers; outcome unset |
| RUNNING | task and owner loop set; flags false; deadlines and timers unset; outcome unset |
| STOPPING | cancel requested; both deadlines set; two timers scheduled; outcome unset; task owned |
| ABANDONED | cancel requested **and escalated**; deadlines set; outcome `TIMED_OUT`; task retained and unfinalized; abandon timer fired |
| STOPPED | finalized (timers cancelled, `_task` cleared) or `NOT_STARTED` recorded; outcome immutable |

Natural completion moves RUNNING straight to STOPPED with the flags still false.

### 2.4 Invariants

| ID | Invariant |
|---|---|
| I1 | The watchdog is single-use. |
| I2 | It is bound to one event loop. The protocol is not thread-safe; cross-thread callers marshal with `run_coroutine_threadsafe`. |
| I3 | Only the watchdog creates, cancels, awaits and clears its task. `stop()` creates no task and touches neither the token nor events. |
| I4 | At most one initial cancel and one escalation, decided in await-free code and only while the task is pending. |
| I5 | The caller's `CancelledError` propagates unchanged and is never stored. |
| I6 | One guarded finalizer, bound by §5. |
| I7 | The stop outcome is sticky and immutable once set. |
| I8 | A completion that has **happened** (`task.done()` true) at a decision point wins. A completion scheduled for a later loop turn does not (§3.2). |
| I9 | Decision code (`_advance` and the first-caller section) contains no await. |
| I10 | No wait begins once its deadline has expired. |
| I11 | The ABANDONED transition happens at most once. |
| I12 | `stop()` from the watchdog's own task is rejected before any mutation. |
| I13 | `stop()` raises only its caller's `CancelledError` and `RuntimeError` for wrong loop while loop-bound, a non-finite computed deadline, or a self-call. The `RuntimeError`s may replace an in-flight exception in a `finally`, with the original kept as `__context__`. |
| I14 | Supervision is driven only by `_advance()`: await-free, idempotent, never raising. It is invoked by two timers the watchdog owns and by `stop()` callers. No new task, no `shield()`, no `uncancel()`. |
| **I15** | Every deadline comparison uses `due(when) := loop.time() + CLOCK_RES ≥ when`, where `CLOCK_RES = time.get_clock_info("monotonic").resolution`. |

## 3. The caller-cancellation contract (R10), and Q-B10

### 3.1 Options

| | Contract | Consequence | Verdict |
|---|---|---|---|
| A | Supervision is tied to the caller. Caller cancellation interrupts it. | Deadlines hold only while some caller is waiting. A cancelled sole caller leaves the child STOPPING and never escalated. Reproduced on v2.3. | Rejected |
| B1 | On caller cancellation, synchronously advance only phases already due, then re-raise. | Better, but a future deadline is still missed. | Insufficient |
| **B2** | Supervision is timer-driven. The first stop request schedules two loop timers (`call_at`) at the escalation and abandonment deadlines. Both call `_advance()`. | Escalation and abandonment happen on time with no caller present. The caller's cancellation propagates at once. | **Recommended** |

B2 uses loop timers, which are not tasks, so it adds no detached driver task. It does supersede the Q-B7 limitation you accepted earlier ("no autonomous escalation"). That is why it needs your explicit decision (Q-B10).

Evidence for B2 (cancel-suppressing child, sole caller cancelled): v2.3 left `cancel_calls=1` and STOPPING after 0.35 s. v2.4 reached `cancel_calls=2` and ABANDONED with `TIMED_OUT`, autonomously. With a cleanup child, the timer's escalation interrupted the cleanup and the child ended STOPPED.

### 3.2 Consequence for boundary precedence

The decision at a deadline is taken by the timer callback. A completion that lands in a later loop turn is late. The outcome is then ABANDONED and sticky `TIMED_OUT`, with the lifecycle later reaching STOPPED. My v2.2 T-B18b ("completion right after the final wait returns gives STOPPED") no longer holds. It is replaced by T-B18a–c below, with wide margins, not exact-boundary assertions.

## 4. Normative algorithm

All underscored names are instance attributes.

```python
async def stop(self) -> StopOutcome:
    self._check_loop()                                   # RuntimeError only if loop-bound and wrong loop
    if self._state is IDLE:
        self._state = STOPPED                            # explicit instance attributes (requirement 1)
        self._outcome = NOT_STARTED
        return self._outcome
    if self._state is STOPPED:
        return self._outcome
    task = self._task
    if task is asyncio.current_task():                   # I12
        raise RuntimeError("stop() must not be called from the watchdog task")
    loop = asyncio.get_running_loop()
    if not task.done() and not self._cancel_requested:   # first caller; await-free
        escalate_at = loop.time() + self.stop_timeout
        abandon_at = escalate_at + self.cancel_grace
        if not (isfinite(escalate_at) and isfinite(abandon_at)):
            raise RuntimeError("non-finite computed deadline")      # validate BEFORE mutating
        self._cancel_requested = True
        self._escalate_at, self._abandon_at = escalate_at, abandon_at
        self._state = STOPPING
        task.cancel()
        self._timers = [loop.call_at(escalate_at, self._advance),
                        loop.call_at(abandon_at,  self._advance)]
    if self._task is not None and not self._task.done() and self._state is STOPPING:
        remaining = self._abandon_at - loop.time()
        if remaining > 0:                                # I10
            await asyncio.wait({self._task}, timeout=remaining)   # never raises the child's exception
    if self._task is not None:
        self._advance()                                  # finalizes if done; else escalates/abandons when due
    return self._outcome if self._state is STOPPED else TIMED_OUT

def _advance(self):                                      # await-free, idempotent, never raises
    task = self._task
    if self._finalized or task is None or not self._cancel_requested: return
    if task.done(): self._finalize(task); return         # I8
    if due(self._escalate_at) and not self._escalated:
        self._escalated = True; task.cancel()
    if due(self._abandon_at) and self._state is STOPPING:        # I11
        assert self._escalated
        self._state = ABANDONED; self._outcome = TIMED_OUT; log.error(...)
```

A second or late caller reuses the persisted deadlines and never restarts them. After a wait ends, `_advance()` decides once. A late caller finds either ABANDONED already recorded by the timer, or an expired phase that `_advance()` advances immediately, with no further wait.

## 5. Pinned finalizer contract

`_finalize(task)` runs from the done-callback registered at `start()` and from `_advance()`/`stop()`, only after `task.done()` is observed. If called on a pending task it mutates nothing, logs ERROR and returns.

**Permitted writes (exhaustive):**

| Field | Write |
|---|---|
| `_finalized` | set to true first, before anything that could raise |
| `task_result` | `finished`, `cancelled` or `error` |
| `child_exception` | the exception, only for `error` |
| `_outcome` | only if unset (never overwritten) |
| `_state` | to STOPPED |
| `_task` | cleared to `None` |
| `_timers` | each handle cancelled, then the list cleared (the only addition over v2.2.1) |

It may also write one log record.

**Forbidden:** events, token, graph or registry mutation, awaiting, scheduling tasks, calling `stop()`, raising.

**Procedure:**
1. Return if finalized or if the identity is not the owned task.
2. Apply the precondition.
3. Set the finalized flag.
4. Cancel the timers.
5. Classify. If `task.cancelled()`, record `cancelled` and do not call `task.exception()`. Otherwise call `task.exception()` once, giving `finished` or `error`. If a `CancelledError` still arises from it, treat it as normal child cancellation and never propagate it.
6. Set the outcome only if unset, then clear `_task` and set STOPPED.

The classification table is unchanged:

| Child end | `task_result` | Outcome (only if unset) | Log |
|---|---|---|---|
| returns | finished | STOPPED | none |
| cancelled | cancelled | STOPPED | none |
| raises | error | CHILD_ERROR | WARNING once |
| returns, cancelled or raises **after `TIMED_OUT`** | finished, cancelled or error | stays `TIMED_OUT` | INFO, INFO, or WARNING once |

The exception is retrieved even after `TIMED_OUT`.

## 6. ABANDONED, defined

ABANDONED means the watchdog's supervision deadline is exhausted. The child may still be alive: `Task.cancel()` is cooperative and a coroutine can suppress it.
- The task stays owned, and the done-callback stays registered.
- The `TIMED_OUT` outcome is sticky.
- Later `stop()` calls return `TIMED_OUT` and issue no cancel.
- When the child eventually ends, the finalizer retrieves its result, cancels the timers, clears `_task` and moves the state to STOPPED, while the outcome stays `TIMED_OUT`.

## 7. Late takeover (Q-B8): comparison and selected rule

| | Option A | **Option B (recommended)** |
|---|---|---|
| Late caller finds an expired deadline and a pending child | gets one more scheduling turn before deciding | escalates if needed and records `TIMED_OUT` with no further turn |
| Result depends on | ready-queue contents | observed state only |
| Deadline contract | effectively extended by one turn | absolute |
| Cost | unpredictable boundary | a child that would finish one turn later is `TIMED_OUT`, with a late STOPPED lifecycle |

**Governing rule:** the first caller establishes the deadlines. Later callers reuse them and never restart or extend them. An expired phase is advanced immediately. Your review recommends Option B and I agree. It stays recommended, not decided.

## 8. Integration limitation L-1 (R1)

The three existing `stop()` call sites stay unchanged in C-b. After C-b, a cancel delivered while a site is joining raises `CancelledError` out of `execute()`. Today that cancel is swallowed. The watchdog child is already cancelled and, with B2, reaped even if nobody calls `stop()` again. The states below were verified by reading `runtime.py` on `main`. T-B25 asserts them exactly, with golden event sequences taken at implementation.

| Site | At the join | After the cancel |
|---|---|---|
| `:523` validation failure | graph created; root RUNNING (status event emitted); `_total_failures` incremented; **no** `workflow.started`, no `execution.completed/failed`, no `workflow.completed` | `execute()` raises; root stays RUNNING; no terminal events at either level; the failure result is lost |
| `:568` unexpected `_execute_from` exception | `workflow.started` and node events up to the failure; root RUNNING; `_total_failures` incremented | `execute()` raises; same graph and events as at the join; no `execution.failed`, no `workflow.completed`; the result is lost |
| `:649` normal end | root terminal in the graph; `execution.completed` or `execution.failed` emitted; `workflow.completed` **not** yet emitted | `execute()` raises; **an execution that looks complete at one level with no `workflow.completed`**; the result is lost |

**Restrictions while L-1 stands:**
- **No cancellation-integration-closure claim.**
- **No claim** that `WorkflowRuntime.execute()` still satisfies its "never raises" contract.
- The C-b-only state is not a completed cancellation solution.
- C-d remains a required follow-on gate.

**Q-B11 (new, for you):** whether C-b may merge before C-d with a release hold on the C-b-only state, or whether C-b and C-d should land back-to-back. Your previous review does not accept the C-b-only state as a standalone production end-state, and I recommend a release hold, with the decision yours.

## 9. Q-B9 stays open

I propose no accepted value. Two independent 3600 s caps would allow a two-hour stop, so the design now validates a **total** envelope. The candidate I would put forward for discussion is 30 s, simply because that is a common container termination grace default. It is a placeholder with no production evidence. The 1.0 s defaults stay provisional. T-B12 on the real watchdog should measure the real child's cancellation latency before any value is accepted.

## 10. Test matrix T-B1…T-B30 (pinned)

**Harness:**
- gates;
- a counting task factory (`cancel_calls`, `exception_calls`);
- children that are prompt, held in cleanup, swallow-until-release, swallow-first, raise-in-cleanup, finish-alone, or already done;
- a loop exception handler;
- `asyncio.all_tasks()` snapshots;
- spies on `_advance` and `_finalize`;
- log capture;
- a failure guard on every wait;
- timing assertions use deadline arithmetic on the attributes, with wide margins (at least 100 ms) for before/after-deadline completions.

"Today" is `main`'s `stop()`.

| ID | Setup / action | Required assertions | Today |
|---|---|---|---|
| T-B1 | prompt child; `stop()` | STOPPED; `_task` and timers cleared; child cancelled; `cancel_calls==1`; `exception_calls==0`; no new tasks; handler 0 | passes |
| T-B2 | child held in cleanup; caller cancelled during the join (long bounds) | caller `cancelled()`, `cancelling()==1`; `cancel_calls==1`; STOPPING; outcome unset; task owned; cleanup uninterrupted; after release: STOPPED, no leaks | caller continues |
| T-B3 | outer `try/finally: await stop()`, cancelled twice | second cancel propagates; `cancelling()==2`; `cancel_calls==1`; cleanup uninterrupted | swallowed |
| T-B4 | cancel-suppressing child; small bounds | the first `stop()` returns `TIMED_OUT`; ABANDONED once (one ERROR log); `cancel_calls==2`; deadline arithmetic exact; a later `stop()` issues no cancel; one generous time bound | hangs (guard) |
| T-B5 | 3 concurrent callers; child swallows the first cancel | all STOPPED; `cancel_calls==2` exactly; one finalization; no ABANDONED | n/a |
| T-B6 | 2 concurrent callers; child held in cleanup | `cancel_calls==1`; cleanup uninterrupted; one finalization | `cancel_calls==2` |
| T-B7 | child raises in cleanup; variant: after `TIMED_OUT` | CHILD_ERROR or sticky `TIMED_OUT`; nothing raised; `exception_calls==1`; handler 0 | n/a |
| T-B8 | already done: returned, raised, cancelled | `cancel_calls==0`; no timers created; correct classification | n/a |
| T-B9 | IDLE stop then start; double start; start after natural completion; start after stop | each `start()` raises `RuntimeError`; state unchanged | accepted |
| T-B10 | in-flight `ValueError` or `CancelledError` in `try/finally: await stop()` | the in-flight exception wins; an I13 `RuntimeError` replaces it with the original as `__context__`; never `TimeoutError`/child exception | n/a |
| T-B11 | `stop()` on a quiescent child | no token, event or graph change by `stop()` | n/a |
| T-B12 | the real `_run()` held at each await (§10.1) | permitted states only | n/a |
| T-B13 | the real watchdog under debug mode (§10.2) | no warnings; handler 0 | n/a |
| T-B14 | child finishes late after `TIMED_OUT` | state STOPPED; outcome stays `TIMED_OUT`; no cancel | n/a |
| T-B15 | late callers: (a) after both deadlines; (b) child already done; (c) between deadlines; (d) deadlines unchanged | (a) `TIMED_OUT`, no further wait; (b) STOPPED, no escalation; (c) escalation at most once by whoever came first; (d) deadline attributes identical | n/a |
| T-B16 | any path | no task created; at most 2 timers; no background driver | n/a |
| T-B17 | child finishes in the same turn, before its callback; then `stop()` | `cancel_calls==0`; STOPPED; one finalization | n/a |
| T-B18a | completion well before the escalation deadline | `cancel_calls==1`; STOPPED; timers cancelled | n/a |
| T-B18b | completion between the two deadlines | `cancel_calls==2`; STOPPED; no ABANDONED | n/a |
| T-B18c | completion well after the abandon deadline | ABANDONED then STOPPED; sticky `TIMED_OUT`; `cancel_calls==2` | n/a |
| T-B19 | the §2.4 I2 matrix: wrong loop while RUNNING/STOPPING/ABANDONED; IDLE and STOPPED from any loop; marshalled call | `RuntimeError` with state untouched (original as `__context__` under a `finally`); allowed cases succeed | n/a |
| T-B20 | invalid configuration | negative, NaN, infinite, `bool`, non-number, envelope exceeded: all raise at construction; zero allowed (zero phases advance immediately) | n/a |
| T-B21a–d | cancelled child on callback path; `stop()` finalizing first; repeat finalize; finalizer on a pending task | no handler call, `stop()` returns STOPPED, no `CancelledError` in a non-cancelled caller; `exception_calls` unchanged; changed fields ⊆ §5 list; pending task: no mutation, one ERROR | literal v2.2: fails |
| T-B22 | non-finite computed deadline (patched `loop.time`) | `RuntimeError`; state RUNNING; flag unset; no cancel; no timers | n/a |
| T-B23 | `stop()` immediately after `start()` | body never runs; STOPPED; `task_result` cancelled; `cancel_calls==1`; no warnings | n/a |
| T-B24 | child calls `stop()` on itself | `RuntimeError`; state RUNNING; `cancel_calls==0`; child ends CHILD_ERROR | n/a |
| T-B25 | the three real `WorkflowRuntime` sites (§8): hold the join with a gated slow-cancel child, cancel the workflow task | `execute()` raises `CancelledError`; the exact per-site states in §8 (golden event sequences); child reaped; no leaks; `cancel_calls` as the gate allows | n/a |
| T-B26 | child with cleanup slower than `stop_timeout` | the escalation interrupts the cleanup (documented as intended) | n/a |
| **T-B27** | `stop()` on a never-started watchdog, then `start()` | returns `NOT_STARTED`; state STOPPED; sticky outcome; `start()` raises. Fails on v2.3's pseudocode. | accepted |
| **T-B28** | child enters slow cleanup after the first cancel; the sole caller is cancelled during it | caller cancelled; at the escalation deadline `cancel_calls==2` (exactly one more) with no caller present. Variant (a): the cleanup is interrupted and the child ends, STOPPED. Variant (b): a cancel-suppressing child leads to ABANDONED at the abandon deadline with `cancel_calls==2`. After the child ends: STOPPED, sticky outcome, timers cancelled, no leaks. Under Contract A the expected values differ (`cancel_calls==1`, STOPPING persists). | n/a |
| **T-B29** | an abandoned child later completes: (i) returns; (ii) raises | result retrieved (`exception_calls==1`); `task_result` and `child_exception` set; `_task` and timers cleared; outcome stays `TIMED_OUT`; the watchdog is garbage-collectable after references are dropped; handler 0 | n/a |
| **T-B30** | a timer fires early by up to the loop clock resolution (patched `loop.time`/resolution) | `_advance()` still takes the due phase (I15); no `None` return; no missed abandonment | n/a |

T-B2, T-B3, T-B6, T-B9, T-B21b, T-B27 and T-B28 must fail against today's `stop()` or the earlier pseudocode. I would record that as mutation evidence.

### 10.1 T-B12: exact permitted and prohibited states (unchanged from v2.2)

| Point | Held at | Permitted state after `stop()` |
|---|---|---|
| I1 | `sleep(interval)` | graph unchanged; no watchdog events; token not set |
| I2 | `graph.snapshot()` | same as I1 |
| I3 | root's `execution.node.failed` emit | root FAILED in graph; that event absent or persisted-not-broadcast; work node RUNNING; token not set |
| I4 | work node's emit | root FAILED with its event; work node FAILED in graph, event absent or persisted-not-broadcast; token not set |
| I5 | `record_recovery` emit (staged extension) | affected nodes RECOVERING in graph; event absent; token not set |

**Prohibited:**
- the token set;
- any node COMPLETED, or a status regression;
- duplicate events for a node;
- an event persisted without its preceding graph write;
- any change attributable to `stop()` itself.

Partial states are asserted as current behaviour (H7/C-g), with no rollback assumed.

### 10.2 T-B13: real-watchdog path under debug

- **Setup:** the real watchdog with a real `ProgressMonitor`, `ExecutionGraph` and `EventStream` on a temp store.
- **Flags:** `PYTHONASYNCIODEBUG=1`, `-W error::RuntimeWarning -W error::ResourceWarning`, and a loop handler that must receive zero calls.
- **Healthy run:** at least 2 real `inspect()` cycles (interval 0.05), then `stop()`.
- **Child-error run:** `inspect()` raises on a later cycle, so the child ends alone and the finalizer classifies CHILD_ERROR, with one retrieval and one WARNING.
- **Injection run:** one T-B12 injection point (I4) as well.

## 11. Evidence

| Class | Status |
|---|---|
| **Algorithm** (toy, not repository code) | Python 3.11.15 and 3.12.3 identical. 3.11 debug mode with warnings as errors clean, 0 leaks, 0 loop-handler calls. It covers the defects of v2.3, the timer contract, the abandoned-child lifecycle, the regression subset, and the emulated coarse-clock defect with its fix. |
| **Production** | Not started. It requires T-B1…T-B30 on the real class. |
| **Integration** | Not started. It is C-d's. |

The toy results for the v2.4 contract:

| Case | Result |
|---|---|
| v2.3 IDLE stop, then `start()` | `start()` succeeded (defect). v2.4: STOPPED, sticky NOT_STARTED, `start()` raises. |
| cleanup child, sole caller cancelled | v2.3: `cancel_calls=1`, cleanup still pending. v2.4: `cancel_calls=2`, cleanup interrupted, child ended. |
| cancel-suppressing child, sole caller cancelled | v2.3: STOPPING indefinitely, `cancel_calls=1`. v2.4: ABANDONED, `TIMED_OUT`, `cancel_calls=2`, abandon entered once. |
| abandoned child later returns or raises | result retrieved once; `_task` and timers cleared; outcome stays `TIMED_OUT`; watchdog collectable |
| concurrent stops, caller cancelled in join, 3 callers plus a later stop, late caller after autonomous abandonment, self-call, stop right after start, wrong-loop stop | all as specified |
| completion landing just after the abandon deadline | `TIMED_OUT` sticky then STOPPED, 1 abandon entry (the §3.2 consequence) |
| coarse clock (emulated 30 ms), plain `>=` | `stop()` returned `None`, STOPPING, no abandonment |
| coarse clock, tolerance rule | `TIMED_OUT`, ABANDONED, `cancel_calls=2` |

Limits: the toy is not the real watchdog, whose `_run()` awaits event emission and graph updates. The coarse-clock result was emulated by patching the loop's private resolution, and real Windows behaviour is unverified.

## 12. Decisions, open items and unchanged items

- **Recommended, not decided:** Q-B8 (Option B).
- **Open:**
  - Q-B9: the supervision envelope and defaults.
  - **Q-B10 (new):** adopt contract B2, timer-driven supervision, which supersedes the earlier Q-B7 limitation. Option A remains available.
  - **Q-B11 (new):** release gating for the C-b-only state.
- **Unchanged:**
  - Q-D1 stays OPEN.
  - ADR-KERNEL-09 is PROPOSED.
  - D-01, D-05, D-07, D-09, D-10 and D-11 stay hard gates.
  - C-e keeps its separate evidence package.
  - Production and integration evidence are not started.
  - The study and the deferred PRs are untouched.

## 13. Authorization boundary and next decision

- **Allowed now:** reviewing this package.
- **Prohibited:** C-e, C-a, C-b, C-c and C-d, any branch, PR, workflow edit or merge, and any change to the study, the ADR or the deferred PRs. None is authorized.
- **Smallest next decision:** approve or amend v2.4 as the C-b design baseline, decide Q-B10 (the timer-driven contract) and Q-B11, and confirm Q-B8. Q-B9 can stay open until real cancellation latency is measured. Authorization for any stage remains a separate request, preceded by a fresh baseline check on `main` and the `ci.yml` blob.
