# Session Handoff

> Governing instructions: `PROJECT_INSTRUCTIONS.md` (repository root), §18.4.8 (handoff), §18.4.9 (fresh-session recovery), §23 (branch and change preservation).
> This file is a **transfer record, not an authority**. Verify it against the live repository before relying on it (section 18).

## 1. Handoff Metadata

- Handoff version: 1
- Created at (sandbox clock, unreliable): 2026-11-17T07:33:17Z
- Workstream: OCBrain cancellation contract (DEBT-105 / issue #105) — **C-b design v2.5** (documentation and design only)
- Task identifiers: issue #105; ADR-KERNEL-09 (PROPOSED); stages C-e, C-a, C-b, C-c+C-d; decisions D-01…D-14, Q-B8…Q-B11, Q-D1
- Source session purpose: final cancellation architecture audit → owner-review cycles → PR-queue verification → stage-gated sequencing → C-b lifecycle/supervision design v2 … v2.4 → v2.5 assignment
- Transfer status: see section 19

## 2. Original Starting Prompt

**FAITHFUL EXTRACTION — not verbatim.** The first mission prompt (≈9,500 words) is too large to reproduce; its deliverables are complete and pushed (the study, the ADR and the index row, see section 8). Operative requirements:

- Title: *Final OCBrain Cancellation Architecture Audit, Contract Decision Package, and DEBT-105 Implementation Readiness*. Architecture study and decision package only — **not** an implementation mission; produce a recommendation with alternatives, evidence, trade-offs and unresolved owner decisions; do not decide for the owner.
- Baseline: `main = ed3d141e4bbfd0231afb1104d0a7479419f9bbf1` (PR #104 merge). Re-fetch main/PR #104/issue #105/B2d branch `follow-up/fz02-b2d-latent-token-cancellation-oct2026`; reconcile if main moved; read-only inspection of B2d.
- Hard boundaries: no production code or test changes, no DEBT-105 implementation, no edits to B2d, PR #104, issue #105, FZ-01/FZ-02, `KNOWN_ISSUES.md`; no new cancellation service/watchdog/Scheduler/RecoveryManager; no destructive git commands; one **local** study branch, no commit, no push (superseded for the final push by the instruction in section 3, item 12).
- Evidence classes: VERIFIED / INFERRED / PROPOSED / ACCEPTED (owner only) / UNVERIFIED / DISPROVEN; every finding with SHA, file/line, call path, behaviour, expected contract, evidence type, reproduction, impact, disposition.
- Audit scope: worker/execution boundary, workflow/retry path, graph watchdog and task cleanup, parallel work and adapters, API/inspection/terminal events, background tasks/shutdown/voice.
- Conceptual model to challenge: three dimensions (initiation/authority/cause · delivery mechanism · observed outcome and effect certainty); request/delivery/acknowledgement/termination/cleanup/effect-certainty distinctions; ownership ≠ DAG ≠ display hierarchy; disconnect ≠ cancellation; no rollback (ADR-005).
- Options A (re-raise native `CancelledError`), B (explicit cancellation outcome), C/C+ (hybrid) evaluated; hypotheses H1–H20 each to be dispositioned.
- Reconcile historical documents (KERNEL_ARCHITECTURE §7.1/§7.4/§8, `k4_2_architecture_hardening_review.md` §6, ADR-KERNEL-02/03, K2 plan, KNOWN_ISSUES, CURRENT_STATE); preserve history, supersede by new ADR; choose next ADR id; keep it PROPOSED.
- External research with citations (Python 3.11 asyncio, AnyIO/Trio, Temporal, `keyboard`).
- DEBT-105: define a narrow contract and the minimum safe boundary, exclusions, owner-decision table, test/acceptance matrix.
- Deliverables: study document, proposed ADR, ADR-index row; second independent review; final handoff; stop and wait for the owner.

## 3. Subsequent User Instructions / Corrections (chronological)

1. **Owner review 1.** C+ direction supported; ADR-KERNEL-09 not approvable as worded; #105 not authorized. Required corrections: (A) `execution.cancelled` is emitted by the workflow finalizer after the node/worker stack unwinds, immediately before the task propagates cancellation — not "after the task has unwound"; (B) subscriber termination must not depend solely on EventStream broadcast (test the actual SSE subscriber for never-persisted and persisted-but-not-broadcast terminal events); (C) an explicit monotonic graph terminal-state transition policy. Recommended: D-03 extend `CancelReason`; D-10 emit `workflow.completed{success:false,cancelled:true}` with the Evaluator recognising cancellation; D-12 gate = C-f/C-g *scheduled* (scope, accountable owner, dependencies, verification criteria); cleanup requirement not a blanket `asyncio.timeout()` mandate.
2. **D-14 DECIDED (owner, option 2; sequencing only):** C-b and C-d must land before PR #81 is reassessed; PR #81's `GraphExecutionWatchdog.stop()` drain loop is not accepted as the cleanup solution (precise defect: **no deadline, and it consumes subsequent caller cancellations once draining**); DEBT-028 stays OPEN/DEFERRED/dormant; six conditions incl. "any lock ahead of `_run()` must be cancellation-safe on acquire, execute and release, with a deterministic regression test for the lock-release refcount leak". Owner-reported: PR #81 open, non-mergeable, 96 behind / 13 ahead, zero reviews/threads.
3. **Standing instruction (2026-11-04):** NO NEW CANCELLATION IMPLEMENTATION; PR review/resolution has priority; do not start C-e/C-a/C-b/C-c/C-d, no branches/PRs for them; PR #81 frozen; resolve the PR #94 CI overlap before scheduling C-e; PR #107 diagnostic-only, never merge; no implementation, merge, issue closure or branch operation authorized.
4. **PR-queue verification mission (read-only).** Delivered report; decision: **NOT READY — PR/CI DISPOSITION OUTSTANDING**; recommended single decision = adopt current `main` as the C-e baseline.
5. **Owner decision ADOPTED (2026-11-07):** C-e baseline frozen at `main 2491ae469edd6ef1267a14604c4f8f40d698f7ea`, `ci.yml` blob `2016eefefab7`; PRs #94, #92, #77, #30 deferred behind C-e (rebase + independent reverification, no merge authorization; #94's green CI is not approval); #32/#33 outside the C-e window; #76 outside C-e; `repair/debt-012-*` branches unpromoted; #107 excluded; #81 frozen. Authorizes **documentation and design only**: stage-gated proposal (C-e → C-a → C-b → C-c+C-d) and the C-b design. Condition 5 stays open until the combined workflow is tested (two-leg 3.11/3.12 config, per-leg artifact naming, 34-entry allowlist on both interpreters, full 3.11 result). Baseline authority = commit/blob identity, not sandbox timestamps; any `main` change before C-e needs a fresh baseline check.
6. **Review of the proposal:** C-e aggregate-job amendment accepted as review baseline (matrix job `tests_matrix`, legs `tests (3.11)`/`tests (3.12)`, aggregate job `tests` with `needs: [tests_matrix]` and `if: always()` failing unless the matrix result is `success`; no branch-protection change; keep the intentional-failure run and the restored green run as evidence; a red 3.11 leg ⇒ C-e not merge-ready, merging red needs a separate owner decision). C-b design v2 accepted with refinements (first-caller flags without a lock, shared absolute deadlines, no autonomous driver task); `asyncio.wait()` accepted as the primitive.
7. **C-b v2.1 NOT approved → v2.2** (A1 persist deadlines as attributes; A2 late takeover; A3 completion check after first wait; A4 loop affinity before/after start; A5 finalizer limits; A6 full T-B acceptance criteria; A7 validate timeouts; A8 Q-B7 limitation). **v2.2 → amend §4** (finalizer mutations; `Task.exception()` on a cancelled task raises `CancelledError`; computed-deadline finiteness) → **v2.2.1**.
8. **"Review the design one more time for flaws, then continue"** → v2.3. **v2.3 NO-GO** → v2.4 requirements: IDLE transition assigns instance attributes; R10 caller cancellation must not bypass escalation (owner prefers contract B without blanket `shield()`/`uncancel()`); strengthen T-B25; combined cancellation+slow-cleanup test; define ABANDONED; record R1 as a temporary integration limitation (not a standalone production end-state); document Q-B8, keep Q-B9 OPEN; pin inherited specs. → **v2.4 delivered** (`docs/handoffs/c-b-v25/C-B_DESIGN_V2.4.md`).
9. **Assignment: C-b v2.5** (`docs/handoffs/c-b-v25/V25_ASSIGNMENT_VERBATIM.md`, preserved verbatim). Design/review only; deliver the complete design **in the response**; "No implementation files or design files are to be created".
10. Q-B8: reviewers recommend Option B (recommended, **not decided**). Q-B9 OPEN. Q-B10 (timer-driven supervision, contract B2) and Q-B11 (release hold for a C-b-only state) are owner decisions, **pending**.
11. Standing rule throughout: a recommendation or DECIDED status is not ACCEPTED; no implementation authorization; separate request + fresh baseline check before any stage.
12. **Latest instruction:** "Push the finished work to the repo, then create the handoff file for the remaining work to be completed in a fresh session." Interpreted as: push a **work branch** (never `main`, no PR, no issue/PR changes) containing the finished study/ADR/index row (checkpoint commit) and then this handoff + preserved inputs/prototypes (handoff commit).

## 4. Goal, Scope & Success Criteria

### Goal
Produce **"C-b design v2.5 — corrected normative lifecycle and supervision baseline"**: a complete, self-contained document (25 sections, assignment §12) correcting C-b design v2.4, delivered **in the response** with disposition matrices and a final assessment (**READY FOR OWNER DECISIONS** or **NO PASS — ADDITIONAL DESIGN WORK REQUIRED**; never ACCEPTED).

### In scope
`GraphExecutionWatchdog` (`core/runtime/watchdog.py`): `start()`, `stop()`, `_advance()`, finalizer, constructor configuration/validation, new tests (as design). Research, adversarial review, algorithm prototypes outside the repository.

### Out of scope
Implementation of any stage; `inspect()` and request-vs-failure semantics (C-g); `WorkflowRuntime` call sites (C-d); `core/runtime/execution_watchdog.py::ExecutionWatchdog` (different class); PR #81 (frozen); the study and ADR-KERNEL-09 (not to be edited); C-e's evidence package; any workflow/CI change; process-isolation redesign (identify as future stage only).

### Success criteria
Assignment §15: no hidden assumptions, no contradictory invariants, no ambiguous transition, no unbounded promise from cooperative cancellation, no implied forced termination, complete finalization contract, transactional timer setup, deadline comparisons consistent with the clock model, no scheduler-independence claim, task-factory assumption tested, shutdown ownership defined, no false leak-free claim, no conflation of algorithm/production/integration evidence, no scope expansion, no implementation authorization. **If the design is not strong enough for an independent implementer, report NO PASS.**

## 5. Requirement Ledger

Status values: OPEN / IN PROGRESS / IMPLEMENTED / VERIFIED / DEFERRED / BLOCKED / NOT APPLICABLE. (Nothing is IMPLEMENTED: no repository code changed.)

| ID | Requirement (source: V25 assignment unless noted) | Status | Evidence / notes |
|---|---|---|---|
| V25-PROV | Pinned provenance: main SHA, runtime.py revision, three `stop()` sites, watchdog revision, `ci.yml` blob | **VERIFIED** at handoff time (sandbox clock 2026-11-17/18) | `core/workflow/runtime.py` and `core/runtime/watchdog.py` blobs are identical on `2491ae4` and on the **current** main `6f93444…`; **`ci.yml` is NOT** (changed by PR #94). **Main is no longer `2491ae4`** — see sections 6 and 15 |
| V25-F01 | Natural completion before done-callback; reorder `_advance()` (finalized → task None → done → requested → escalate → abandon) | OPEN | defect traced by reading (v2.4 `_advance()` returns early when `_cancel_requested` is false, so `stop()` would return `TIMED_OUT` for a child that finished naturally before its callback ran); **not yet reproduced on a prototype** |
| V25-F02 | Advance supervision before any wait; late-caller traces (5 cases) | OPEN | design sketch in Annex A |
| V25-F03 | Clock-resolution Model A vs Model B; zero/sub-resolution/both-due behaviour; do not silently alter I15 | IN PROGRESS | early-timer defect reproduced (emulated 30 ms; `prototypes/clock_probe.py`); CPython `_run_once` source verified; Model B sketch in Annex A, not yet prototyped |
| V25-F04 | Distinguish requested/escalated/expired/terminated/reaped; suppress-both child → ABANDONED | OPEN | v2.4 toy covers suppress-both; needs rewrite of the state definition |
| V25-F05 | Event-loop liveness (starvation, `stop()`, `close()`, shutdown); not hard real-time | IN PROGRESS | documented: `loop.close()` discards pending callbacks; experiments not run |
| V25-F06 | `asyncio.run()` shutdown with an abandoned child; shutdown contract; compare 4 options | IN PROGRESS | CPython `_cancel_all_tasks` cancels **and awaits** tasks (source read); hang experiment **not run** |
| V25-F07 | Finalizer transaction/failure recovery; compare non-raising vs two-phase | OPEN | recommendation in Annex A (results-first, commit last) |
| V25-F08 | Transactional supervision setup (5 failure points) | OPEN | recommended ordering in Annex A |
| V25-F09 | Normative `start()`; eager task factory (3.12+) supported or prohibited | IN PROGRESS | eager factory exists only from 3.12 (source verified); behaviour not prototyped |
| V25-F10 | Cancellation accounting; five child variants; never `uncancel()` | OPEN | docs read; variants not yet prototyped |
| V25-F11 | Abandoned-child observability without driver/graph events/token | OPEN | Annex A recommendation (read-only properties; Q-B12 for an awaitable) |
| V25-F12 | Complete exception matrix; update I13 | OPEN | |
| V25-F13 | Task retention/GC/ownership analysis | OPEN | v2.4 toy shows the watchdog collectable after late completion |
| V25-DISP | Disposition table for the 22 listed prior findings (assignment §6) | OPEN | |
| V25-RES | Research with source attribution and evidence-class separation | IN PROGRESS | done/not done in section 11 |
| V25-Q | Q-B8/Q-B9/Q-B10/Q-B11 owner-decision register, recommendation ≠ acceptance | OPEN | Q-B8 wording must change (first observed `task.done()` at an `_advance()` decision point; no scheduler-independence claim); Q-B9 measurement protocol required; Q-B10/Q-B11 conditions in assignment §8 |
| V25-L1 | Preserve L-1 (three call-site states) exactly; correct "B2 always reaps" | OPEN | text preserved in `C-B_DESIGN_V2.4.md` §8 |
| V25-TEST | Retain T-B1…T-B30; add T-B31…T-B45; accounting rules | OPEN | |
| V25-EVID | Every claim classified Algorithm/Production/Integration/Source/External/Unverified | OPEN | |
| V25-DOC | Final 25-section document | OPEN | not started |
| V25-PASS | Passes A, B, C before publishing | OPEN | |
| V25-OUT | Report order A–F; choose READY FOR OWNER DECISIONS or NO PASS | OPEN | |
| V25-AUTH | No implementation, files, branches, workflow edits; deliver in the response | OPEN (standing) | |
| OWN-D14 | D-14 decided (sequencing) | VERIFIED (owner-stated) | |
| OWN-CE | C-e baseline adopted (`2491ae4` / `ci.yml` `2016eefefab7`) | owner-stated; **premise invalidated** — PR #94 merged and changed `ci.yml` (section 15) | |

## 6. Current Verified State

### VERIFIED (read-only; evidence class named)
- **Source / baseline:** the frozen baseline is `main` = `2491ae469edd6ef1267a14604c4f8f40d698f7ea`. It was unchanged when re-checked after the sandbox reset, but **by handoff time `main` had moved to `6f9344476958…`** — five PRs merged on 2026-11-17: **#109, #110, #94, #108, #87** (32 files changed). Audited blobs: `core/workflow/runtime.py` `9709d31425da` and `core/runtime/watchdog.py` `5e9551f0fab4` are **identical** on both SHAs, so the V25 source claims (three `stop()` sites at `:523/:568/:649`, watchdog structure) still hold. **`.github/workflows/ci.yml` CHANGED**: frozen blob `2016eefefab7` → now `c34a1c1770e4` (PR #94 added the `token-acl-windows` job; the file now has three jobs: `drift-and-ownership`, `tests`, `token-acl-windows`). Also changed on main: `interface/api.py`, `main.py`, `core/event_bus.py`, `interface/auth.py` and other interface files, `tests/conftest.py` (autouse auth opt-out fixture), `KNOWN_ISSUES.md`/`CURRENT_STATE.md` (PR #108; they now mention cancellation). **The study's line citations for `interface/api.py`, `main.py` and `core/event_bus.py` refer to `ed3d141`/`2491ae4` and are stale on current main; the study's probes for the API assume the old `X-OCBrain-Local` gate.** *A historical SHA is not a fresh baseline for a later implementation stage; re-check.*
- **Three `GraphExecutionWatchdog.stop()` call sites** in `core/workflow/runtime.py`: `:523` (validation failure), `:568` (unexpected `_execute_from` exception), `:649` (normal end); `watchdog.start()` at `:517`. Exact states at each join: `C-B_DESIGN_V2.4.md` §8 (read from source).
- **Watchdog structure (source):** `start()` creates `self._task = asyncio.create_task(self._run())` with no guard; `stop()` = `cancel()`, `await self._task`, `except CancelledError: pass`, then `_task = None`; `interval_seconds = max(0.05, …)`; `_run()` loops token/sleep/`inspect()`; `_task` is private to the class; no existing test calls `GraphExecutionWatchdog.start()/stop()` directly.
- **External (CPython 3.11.15 / 3.12.3 sources, installed copies):** `BaseEventLoop._run_once` runs scheduled handles whose time is `< loop.time() + _clock_resolution` — timers can fire up to one resolution **early** (`base_events.py` ~l.1904; `_clock_resolution = time.get_clock_info('monotonic').resolution`, ~l.401); `asyncio.run()`'s `_cancel_all_tasks` cancels all remaining tasks and **awaits** them; `asyncio.eager_task_factory` exists in 3.12, not in 3.11; `Task.cancel()` increments a cancellation counter (`cancelling()`/`uncancel()`); `Task.exception()` on a cancelled task raises `CancelledError`, on a pending task `InvalidStateError` (verified by execution on 3.11.15 and 3.12.3).
- **External (official documentation, found via search; claims paraphrased):** `loop.call_at` uses the same clock as `loop.time()`, a callback is called exactly once and **order for the same instant is undefined**; `loop.close()` **discards pending callbacks**; Task cancellation doc: `CancelledError` should normally propagate after cleanup, suppressing it breaks structured-concurrency components, user code should not generally call `uncancel()`; eager tasks (3.12) start the coroutine synchronously inside task construction (gh-97696); `Task.cancelling()/uncancel()` documented since 3.11 (gh-90908).
- **Algorithm (prototypes, outside repo):** section 13.
- **The finished documents** are on the pushed branch (section 7).

### IMPLEMENTED BUT NOT VERIFIED
None.

### PROPOSED
C-b design v2.4 (known defective, input only); v2.5 design decisions in Annex A (unvalidated); contract B2 (timer-driven supervision); Option B late takeover; sequencing C-e → C-a → C-b → C-c+C-d.

### DEFERRED
PRs #94, #92, #77, #30, #32, #33, #76, #81; Q-D1 (synchronous terminal marking vs async locked `ExecutionGraph.update()` and subscriber sentinel) until the C-d review; C-f, C-g.

### BLOCKED
None. (Owner decisions pending: Q-B9, Q-B10, Q-B11, plus D-01, D-05, D-07, D-09, D-10, D-11, D-12, D-13 before C-c/C-d.)

### UNKNOWN / UNVERIFIED
Real Windows clock resolution under CPython 3.11/3.12; behaviour of uvloop (coarser clock); the hang of `asyncio.run()` with an abandoned cancel-suppressing child (source-read, **experiment not run**); eager-task-factory behaviour of the prototype; upstream CPython issues on early timers/cancellation races (search **not yet done**); research papers (search **not yet done**); any production-class evidence (none exists).

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1` (public)
- Remote: `https://github.com/1h0lde4/ocbrain-v4.1.git` (no credentials in the URL or `.git/config`; verified after pushing)
- Work branch: `study/cancellation-contract-final-gap-oct2026-r2`
- Base branch: `main`; base commit `2491ae469edd6ef1267a14604c4f8f40d698f7ea`
- **Transfer commit** (the implementation state being transferred = the finished documentation): `3f5ec9c90503c5d10588212af66ed7b26fab5fad` — "docs(cancellation): study rev 2.2 and proposed ADR-KERNEL-09 (PROPOSED) - checkpoint"; pushed and verified by `git ls-remote` and by re-cloning the branch after the sandbox reset.
- **Branch vs main:** the branch is based on `2491ae4` and is now **52 commits behind** `main` (`6f93444…`); it was **not** rebased (a rebase is a branch operation the owner has not authorized). `git merge-tree` shows the branch would **conflict with main in `docs/architecture/decisions/ADR_INDEX.md`** (see the ADR-ID collision in section 15).
- Handoff commit: the commit that adds this file; **parent = the transfer commit above** (a commit cannot contain its own SHA; read it from `git log`)
- Working tree status at handoff: clean apart from the handoff commit's files
- Relevant untracked / ignored files: none
- Submodules / nested repositories: none
- Remote push status: see section 19
- `main` was **not** modified; no PR, issue, label or other branch was created or changed. The earlier local first-version checkout (based on `ed3d141`, uncommitted) no longer exists (sandbox reset) and was superseded by this branch.

## 8. Active Files / Modified Files / Artifacts

Added on the branch (nothing existing was modified except the ADR index row):

| Path | Why it matters |
|---|---|
| `docs/studies/OCBRAIN_CANCELLATION_FINAL_GAP_STUDY_OCT2026.md` | Final cancellation gap study, revision 2.2 (evidence at `ed3d141`, reconciled to `2491ae4`; owner-review corrections A–C; D-14 DECIDED; no design statement ACCEPTED). Contains the H1–H20 register, probes P1–P15/C1–C5, A/B/C+ analysis, #105 boundary, test matrix T-W/T-R/T-G/T-P/T-E/T-X/T-V/T-Z, owner decisions D-01…D-14 |
| `docs/architecture/decisions/ADR_KERNEL_09_CANCELLATION_CONTRACT.md` | Proposed ADR; **status PROPOSED — pending repository owner decision**; revision 2.2 |
| `docs/architecture/decisions/ADR_INDEX.md` | exactly one added row (ADR-KERNEL-09) after the KERNEL-08 row |
| `handoff.md` | this transfer record |
| `docs/handoffs/c-b-v25/V25_ASSIGNMENT_VERBATIM.md` | the operative v2.5 specification, verbatim |
| `docs/handoffs/c-b-v25/C-B_DESIGN_V2.4.md` | v2.4 verbatim — the input v2.5 must correct (not an approved baseline) |
| `docs/handoffs/c-b-v25/prototypes/` | `toy_v24.py`, `clock_probe.py`, README. **Algorithm evidence only.** The earlier toys (v1, v2, v2.1, v2.2, v2.2.1, review/demo probes) were **lost in a sandbox reset** and are not preserved (see README and section 12) |
| `docs/handoffs/c-b-v25/study-probes/` | probes P1–P15/C1–C5/reason probe + raw results + README. They run against a **throwaway copy** of the repository |

Note: the study text says its probes were "delivered outside the repository, not committed"; they are preserved here by the handoff commit.

## 9. Changes Made

Documentation only; **no production code, tests, configuration, workflows, issues or PRs were changed**. Behavioural claims in the study are about the *audited* code (baseline `ed3d141`/`2491ae4`), not about any change.

## 10. Decisions & Rationale (decision ledger)

| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| D-14 | C-b and C-d land first; PR #81 reassessed afterwards (six conditions) | **DECIDED** (sequencing only) | owner | PR #81 96/13, DEBT-028 record on main | verified contradiction; owner request |
| CE-BASE | C-e baseline = `main 2491ae4`, `ci.yml` `2016eefefab7`; #94/#92/#77/#30 deferred behind C-e | **ADOPTED by the owner — but its reopen condition has fired**: PR #94 (listed as deferred) was merged on 2026-11-17 and `ci.yml` is now `c34a1c1770e4` | owner | PR-queue report; current main | **owner must re-decide the C-e baseline** (e.g. re-freeze on the current main and blob, with `token-acl-windows` already present; #92/#77/#30 remain open) |
| CE-AGG | C-e adds aggregate job `tests` over `tests_matrix`; no branch-protection change | review baseline accepted | owner review | ci.yml has no `needs:` on `tests` | owner request |
| NO-IMPL | no cancellation implementation; stages need separate authorization | standing | owner | — | explicit authorization |
| CB-FLAGS | first-caller-only cancel via synchronous flags, no lock | accepted by owner review | owner review | toy; cooperative scheduling | contradiction found |
| CB-DEADLINES | absolute deadlines persisted on the watchdog, shared by all callers | accepted by owner review | owner review | toy | |
| CB-WAIT | `asyncio.wait()` (not `wait_for`, not `shield` loops) | accepted by owner review | owner review | toy; N17 hazard | |
| Q-B8 | late takeover = Option B | **recommended, not decided** | — | toy | |
| Q-B9 | supervision envelope and defaults | **OPEN** | owner | no latency evidence | latency protocol run |
| Q-B10 | contract B2 (timer-driven supervision) | **pending owner** | owner | toy; changes the earlier accepted "no autonomous escalation" limitation | |
| Q-B11 | release gating of a C-b-only state | **pending owner** | owner | L-1 | |
| Q-D1 | synchronous terminal marking vs async locked graph update; subscriber sentinel | **OPEN** | C-d review | `execution_graph.py:87-88` async + lock | |
| D-01,05,07,09,10,11,12,13 | cancellation contract decisions | **pending** (recommendations in the study §18); hard gates for C-c/C-d | owner | | |

Rejected/dropped (with reason): contract A (supervision tied to the caller) — reproduced failure; v1 stop() (duplicate cancel, caller-cancel stored globally); lock-based serialization (queued bounds accumulate); `wait_for`/`shield`+loop patterns (PR #81 drain loop) — unbounded or cancel-consuming.

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| Cancellation path in repo (worker base, runtimes, graph, watchdogs, planner, adapters, router, API, orchestrator, event stream, voice) | source at `ed3d141`, blobs identical at `2491ae4` | defects H1–H7, H9, H10, H13, H16, H17 and N-series confirmed; H14/H15/H18/H19 characterised | study §5–§6; probes | blob changes |
| PR queue and CI overlap | all PR heads via `refs/pull/*/head`, `git merge-tree` pairwise/combined | #30/#77/#92/#94 textually clean in any order; #94+#107 conflict; no combined CI run exists | PR-queue report | main/PR heads change |
| #94 CI | run `41999549279` on head `c50caa9` | `token-acl-windows` ran and passed (real `icacls` step) | API job list | #94 head changes |
| C-b algorithm v1…v2.4 | stdlib prototypes | section 13 | `prototypes/` (v2.4 only) | |
| Python semantics | installed CPython 3.11.15/3.12.3 source; official docs via search | section 6 | | version change |
| `asyncio.wait` | docs + prototypes | does not cancel awaited tasks on timeout or caller cancellation | | |
| **Not yet investigated** | upstream CPython issues on early timers/cancellation races; research papers; eager-factory prototype; `asyncio.run` hang experiment; Windows clock | — | — | next session |

## 12. Failed Attempts / Dead Ends

- **Sandbox reset (2026-11-15):** `/home/claude` and `/tmp` were wiped between turns; only `/mnt/user-data/outputs` persisted. Consequences: the earlier toys (v1, v2, v2.1, v2.2, v2.2.1, review/demo probes) and the interim local checkout were lost; the pushed checkpoint commit survived; `toy_v24.py` and `clock_probe.py` were re-typed from the authoring record and sanity-run (system Python 3.12.3 only; 3.11 unavailable after the reset) and reproduced the recorded results. **Lesson: commit/push artifacts as soon as they exist; do not rely on `/tmp`.**
- **Anonymous GitHub API:** egress IPs rotate and are rate-limited (60/h each); many calls fail. Use `git ls-remote`/`git fetch refs/pull/*/head`, retry loops with sleeps, or `web_fetch` only for URLs that appeared in the conversation. `web_search` does not surface this repository's PR/CI pages.
- **First conflict-test harness** produced false conflicts (missing git identity for `commit-tree`); fixed by passing identity via environment. Earlier numbers were not published.
- **`cut -c` on UTF-8** truncates multibyte characters and breaks tool output; use Python slicing.
- **Toy misreadings corrected:** v1 concurrent-stop output `cancel_requests=2` was mis-reported as "no duplicate cancel" (owner review caught it); a pseudocode defect (deadlines as locals) and the v2.3 IDLE pseudocode assigning locals; a one-pending-task "leak" in a toy was my own demonstration child.
- **Dead designs:** v2.4's plain `>=` deadline comparisons (early timer ⇒ missed phase, `stop()` returned `None`); `_advance()` order that checks `_cancel_requested` before `task.done()` (F-01) and `stop()` that waits before advancing (F-02) — both traced by reading, not yet prototyped; to be fixed in v2.5.
- **Do not retry:** lock-based single-owner; `shield()`/`uncancel()` loops; per-call `timeout` parameter plus constructor timeouts (precedence ambiguity).

## 13. Verification Evidence

Prototype runs were on CPython 3.11.15 and 3.12.3 (identical) with a 3.11 debug leg (`PYTHONASYNCIODEBUG=1 -W error`, clean, 0 leaks, 0 loop-handler calls) **before** the reset; after the reset only `toy_v24.py` and `clock_probe.py` were re-run, on system Python 3.12.3, reproducing the recorded results. **Algorithm evidence only.**

- Repo tests at `2491ae4` (throwaway copy): `pytest tests/test_b2c_cancellation.py tests/test_execution_watchdog.py tests/test_workflow_runtime.py tests/test_execution_inspection.py` → **61 passed** on 3.11.15 and 3.12.3. The full suite was **not** run (DEBT-012 rewrites tracked config files; chromadb/sentence-transformers not installed).
- Study probes P1–P15, C1–C5, reason probe: raw results in `study-probes/results_*.txt`. P1 (cancelled `execute()` returned `success=True`, node run twice), P3, P4, P6, P7, C5 re-verified on live main.
- Prototype results: v1 duplicate-cancel and caller-cancel-stored defects; v2 first-caller flags; v2.1 refinements; v2.2 persisted deadlines, Option-B late caller, loop-affinity matrix, finalizer classification, config validation; v2.2.1 finalizer fault (`task.exception()` on a cancelled task) and `inf` deadline from huge finite config (**these earlier toys are not preserved**); v2.4 IDLE fix, timer-driven supervision, abandoned-child lifecycle, and the emulated early-timer defect with its tolerance fix (**preserved**: `toy_v24.py`, `clock_probe.py`).
- Citation audits: 107–110 repo `file:line` citations in the study/ADR resolve at `2491ae4`.
- Limits: no Production-class or Integration-class evidence exists; the early-timer result was **emulated** by patching the loop's private resolution; real Windows resolution unverified.

## 14. Environment / Tooling Assumptions

- The sandbox is **ephemeral and was reset once**; assume nothing under `/tmp` or `/home/claude` survives. Recreate: `uv` (pip-installed) with CPython 3.11 and 3.12; a venv with aiofiles aiohttp beautifulsoup4 click datasketch fastapi feedparser httpx pydantic pytest pytest-asyncio PyYAML requests rich scipy tomli tomli-w "uvicorn[standard]" keyboard (previously resolved: fastapi 0.162.0, starlette 1.10.0, uvicorn 0.54.0, anyio 4.16.0, keyboard 0.13.5, pytest 9.2.0, pytest-asyncio 1.4.1). The toys need only the standard library.
- Network: GitHub reachable (anonymous git/HTTPS works; API rate-limited); PyPI and uv-managed Python downloads reachable.
- Shell: `/bin/sh` is dash — use `bash -c` for bashisms; avoid `cut -c` on UTF-8.
- Sandbox clock readings are inconsistent with elapsed work; **use commit/blob identity, not timestamps**.
- Repository source files may be CRLF; new docs use LF.
- **Credentials:** a GitHub PAT was supplied in the session preferences. It was used **transiently, once**, for the checkpoint push (HTTP header for that command only), is **not** stored in this repository, `.git/config` or this file, and should be **rotated** (it was exposed in plaintext). A fresh session must use its own credential flow and must never persist tokens.

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Disposition | Needed |
|---|---|---|---|
| Q-B9 envelope/defaults | no production latency evidence | OPEN | measurement protocol (T-B45) before any value; total-envelope validation; do not accept 30 s by analogy |
| Q-B10 contract B2 | toy only | pending owner | the six conditions in assignment §8 |
| Q-B11 release hold | L-1 | pending owner | enforceable hold covering release, deployment, packaging, distribution |
| Q-B12 (proposed here) | optional awaitable "watchdog finalized" for abandoned children | OPEN | decide after F-11 analysis |
| Q-D1 | async locked `ExecutionGraph.update()`; no synchronous terminal-marking API; registry sentinel unverified | OPEN | C-d review |
| Windows/uvloop clock granularity | CPython `_run_once` early-firing; `ci.yml` Windows job exists only on deferred #94 | UNVERIFIED | measure; keep slack configurable |
| Abandoned child and process shutdown | `asyncio.run()` awaits cancelled tasks | hang expected, **not demonstrated** | subprocess experiment with timeout (T-B41) |
| Eager task factory (3.12+) | child may run inside `create_task` before ownership is assigned | undecided supported/prohibited | prototype + decision (F-09) |
| Production/integration evidence absent | — | OPEN | real watchdog tests; C-d |
| Frozen/deferred PRs may merge and change the baseline | PR list | risk | fresh baseline check before any stage |
| **ADR-KERNEL-09 identifier COLLISION (found at handoff time)** | `main` now has `ADR_KERNEL_09_CONTROL_PLANE_AUTHORIZATION.md` (PROPOSED, DEBT-025 control-plane authorization; PR #110) and an `ADR-KERNEL-09` row in `ADR_INDEX.md`; this branch's cancellation ADR is also `ADR_KERNEL_09_CANCELLATION_CONTRACT.md` with its own index row. My earlier branch scans (before 2026-11-08) found no claim on 09; the other ADR-KERNEL-09 appeared later | **OPEN — owner decision** | the cancellation ADR (and the study, which cites it) must be **renumbered** — next free identifier appears to be `ADR-KERNEL-10` (verify at the time) — and its index row rebased onto main. This requires the owner's explicit authorization because the owner prohibited editing the study/ADR. Until then the pushed branch must not be merged, and nobody should cite "ADR-KERNEL-09" for the cancellation contract without qualification |
| **C-e baseline invalidated by main moving** | `ci.yml` blob changed on main (PR #94 merged); the owner's frozen baseline named blob `2016eefefab7`; the C-e proposal (aggregate job, matrix edit points, per-leg artifact) was written against the old file | **OPEN — owner decision** | re-run the baseline check, re-derive the C-e edit points against `c34a1c1770e4` (three jobs now), decide whether to re-freeze; do **not** start C-e on the old blob |
| Study citations stale on current main | `interface/api.py`, `main.py`, `core/event_bus.py` changed by PR #94; KNOWN_ISSUES/CURRENT_STATE now mention cancellation (PR #108) | OPEN | re-verify before citing line numbers for those files; the study's historical baseline statements remain correct for `ed3d141`/`2491ae4` |
| Index conflict | the branch's `ADR_INDEX.md` row conflicts with main (verified by `git merge-tree`) | OPEN | resolve together with the renumbering |

May work continue without resolving these? Yes for the v2.5 document (keep them OPEN with alternatives); **no** for any implementation.

## 16. Relevant Information / References

- Repo: `PROJECT_INSTRUCTIONS.md`; `docs/architecture/decisions/ADR_INDEX.md`; `KNOWN_ISSUES.md` (DEBT-012 test side effects, DEBT-028 dormant/deferred, FZ-01); `core/workflow/runtime.py:517,523,568,649`; `core/runtime/watchdog.py`; `core/runtime/progress.py` (graph write then event emit); `core/runtime/execution_graph.py:87-88`.
- Python docs (3.11 and 3.12 `asyncio-eventloop`, `asyncio-task`, `asyncio-sync`, `asyncio-dev`); CPython issues/commits: gh-90908 (`cancelling()`/`uncancel()` docs), gh-102780 (`uncancel()` in timeouts), gh-97696 (eager tasks), issue 104144.
- AnyIO cancellation docs; Temporal cancellation-vs-termination docs (used for vocabulary only).
- PRs: #81 (DEBT-028, frozen), #94 (DEBT-025 auth + Windows ACL job), #107 (diagnostic, never merge), #92/#77/#30 (action pins), #32/#33 (dependency bumps), #76 (release workflow), #91 (DEBT-012), #108 (draft docs), #109 and #110 (docs; **merged**; #110 adds the other ADR-KERNEL-09 and changed ADR_INDEX.md).
- Repository cautions: do not run the full test suite in the checkout (DEBT-012); `ExecutionWatchdog` (router-facing, sync `stop()`) is a different class.

## 17. Next Steps

1. **Recover** (section 18): verify branch, commits, remote; read this file, then `V25_ASSIGNMENT_VERBATIM.md`, then `C-B_DESIGN_V2.4.md`.
2. **Fresh baseline check:** `git ls-remote … refs/heads/main`; expect `6f9344476958…` or later (the frozen SHA was `2491ae469edd…`); compare blobs `runtime.py 9709d31425da` and `watchdog.py 5e9551f0fab4` (identical at handoff time) and `ci.yml` (**now `c34a1c1770e4`, not the frozen `2016eefefab7`**); re-read the three `stop()` sites. If any blob or call site changed, re-verify the affected claims before using them. Report the moved main SHA to the owner as a baseline change (the owner's frozen C-e baseline is defined by commit **and** blob identity).
2b. **Surface the ADR-KERNEL-09 collision to the owner** (section 15). Do not edit the study/ADR, rebase, or push without explicit authorization.
3. **Recreate the sandbox** (uv + CPython 3.11/3.12) and re-run `prototypes/toy_v24.py` and `prototypes/clock_probe.py` to confirm they reproduce (section 13).
4. **Finish the research** (assignment §7): (a) `asyncio.run()`/`Runner` shutdown hang experiment in a **subprocess with a timeout** (3.11 and 3.12); (b) search upstream CPython issues/tests on early timers, cancellation races, eager tasks, pending-task cleanup, loop shutdown; (c) read 3.11 vs 3.12 Task documentation for version differences; (d) search research papers on asynchronous cancellation/structured concurrency; state explicitly if none changes the conclusions; (e) record each claim as documented guarantee / implementation detail / tested behaviour / inference / unverified.
5. **Prototype v2.5** (new toy outside the repo — **commit prototypes to a work branch as they are created, if the owner permits**, or keep them in the response) implementing Annex A and validating F-01 … F-13: natural-completion-before-callback and cancelled-completion traces; late-caller traces 1–5 (white-box: cancel timers and move deadlines into the past); Model A vs B with emulated coarse clocks (zero, sub-resolution, equal, larger grace; both deadlines due in one `_advance()`); transactional setup fault injection (deadline calc, first/second `call_at`, `task.cancel()`, rollback); eager factory (3.12 only; normal/immediate finish/immediate exception; creation failure with coroutine cleanup); cancellation-accounting variants (propagates / suppresses first / suppresses both / retains counts / completes after ABANDONED, recording `cancelling()`); finalizer fault injection (timer cancel, retrieval, logging, repeated and late callbacks); event-loop liveness (blocked loop, `loop.stop()`, `loop.close()`); shutdown experiment; GC/weakref checks; exception matrix.
6. **Write the v2.5 document** (assignment §12 — 25 sections), the disposition matrix (22 prior findings + F-01…F-13), the retained T-B1…T-B30 (correcting only conflicting assertions) plus T-B31…T-B45 with the accounting rules, the evidence classification, and the owner-decision register (recommendation ≠ acceptance).
7. **Run Passes A, B, C** (assignment §13) and record them in the document.
8. **Deliver in the response** (not as files) in the order A–F (assignment §14) and finish with **READY FOR OWNER DECISIONS** or **NO PASS — ADDITIONAL DESIGN WORK REQUIRED**, the remaining owner decisions and the smallest next action. **Do not initiate that action.**

### Annex A — v2.5 design decisions reached so far (PROPOSED, NOT validated)

1. **`_advance()` order:** (1) `_finalized` → return; (2) `_task is None` → return; (3) `task.done()` → finalize, return; (4) not `_cancel_requested` → return; (5) escalate if due and not escalated (`_escalated` = "one escalation attempt made", set before the call; failure logged); (6) abandon if due and STOPPING (requires the escalation attempt); entering ABANDONED cancels any remaining timers.
2. **`stop()` order:** `_check_loop`; IDLE → STOPPED/NOT_STARTED (explicit instance attributes); STOPPED → outcome; `_task is None` while RUNNING (eager first segment) → `RuntimeError`; self-call → `RuntimeError`; **`_advance()` before any wait**; if RUNNING → transactional `_request_stop()` then `_advance()` (handles zero-valued phases); `while state is STOPPING:` wait only for the remaining time to the abandon deadline (+ slack), then `_advance()`; return `_outcome` (never `None`).
3. **Transactional `_request_stop()`:** compute deadlines (finiteness check, no mutation) → install timer 1 → install timer 2 → `task.cancel()` → **commit** (`_timers`, deadlines, `_cancel_requested`, `STOPPING`); any failure cancels installed handles, leaves state RUNNING and propagates the infrastructure exception; a failed `cancel()` is never recorded as a cancellation request.
4. **Model B (not-before):** install timers at `deadline + TIMER_SLACK_S` and compare strictly (`now >= deadline`); callers wait until `abandon_at + TIMER_SLACK_S`; the configured grace is a true **minimum**; lateness ≤ about 2 × resolution; `TIMER_SLACK_S = max(clock resolution, 1 ms)` as an overridable class constant (coarse-clock loops such as uvloop; not read from the loop's private attribute). Zero phases are due immediately; both deadlines can be due in one `_advance()` (escalate then abandon). Model A (early-tolerant `due(t) := now + RES >= t`) shortens effective grace by up to one resolution and makes sub-resolution grace meaningless — recommend B, but **do not silently alter I15**; state the choice explicitly.
5. **State definitions** by supervision conditions (not by timer firing): ABANDONED = cancel requested ∧ escalation attempted ∧ outcome `TIMED_OUT` ∧ task retained ∧ not finalized; `_task` retained from `start()` until finalization; `_loop` cleared at STOPPED (not retained); timers cancelled at ABANDONED and at finalization.
6. **`start()`:** reject if not IDLE; `asyncio.get_running_loop()`; set `_loop` and RUNNING **before** creating the task (eager-safe); create the coroutine, `loop.create_task(coro)` inside `try`; on any failure `coro.close()`, restore IDLE/`_loop=None`, re-raise; assign `_task`; `add_done_callback` (fires via `call_soon` even if the task is already done). Recommend **supporting** eager factories (3.12+) with the explicit `RuntimeError` for `stop()` during `start()`.
7. **Finalizer:** stage 1 classify and store `task_result`/`child_exception` (retrieval at most once; unexpected retrieval failure ⇒ classify as `error`; `CancelledError` ⇒ cancelled); stage 2 commit: cancel timers (each guarded), outcome if unset, `_task=None`, `_loop=None`, `_state=STOPPED`, **`_finalized=True` last**; never raises; logging through a safe wrapper; the done-callback wrapper never raises; a pending-task call is a logged no-op. No intermediate lifecycle state is needed.
8. **I13 rewrite:** `stop()` propagates (a) the caller's `CancelledError`; (b) contract `RuntimeError`s (wrong loop while loop-bound, self-call, stop during start, non-finite deadline); (c) infrastructure exceptions from timer installation or the initial cancel, **after rollback**. Child exceptions are retrieved internally and never raised by `stop()`. Do not promise a narrower whitelist.
9. **Observability:** read-only properties `state`, `outcome`, `task_result`, `child_exception`, `finalized`; **no** background task, graph event or token mutation; an awaitable "finalized" notification is **Q-B12 (OPEN)** — explain its relation to I3, I14 and C-d if recommended.
10. **Shutdown contract (owning runtime):** C-b guarantees only observable state; the owner must enumerate ABANDONED watchdogs at shutdown and report them; waiting indefinitely vs reporting-and-retaining vs controlled process termination vs process isolation compared; hard termination of a cancel-suppressing coroutine requires process-level mechanisms — a **separate stage**, not C-b.
11. **Q-B8 wording:** the first observed `task.done()` at an `_advance()` decision point decides precedence; no extra scheduling turn; exact concurrent boundary ordering is **not** guaranteed (same-instant callback order is undefined). Tests must not assert deterministic ordering where asyncio provides none (T-B38).
12. **Q-B9:** keep OPEN; defaults 1.0 s provisional; `MAX_STOP_ENVELOPE_S` must be ≥ the sum of accepted defaults (assert in a test); define the latency measurement protocol (environment, Python/OS, clock resolution, workload, repetitions, raw data, statistics, limits) separately from T-B12.

## 18. Resume Instructions

First actions, in order (`PROJECT_INSTRUCTIONS.md` §18.4.9):

1. Read `PROJECT_INSTRUCTIONS.md`.
2. `git fetch`; verify branch `study/cancellation-contract-final-gap-oct2026-r2` exists on the remote; verify the transfer commit `3f5ec9c90503c5d10588212af66ed7b26fab5fad` is an ancestor of the branch head and that the head's history contains the handoff commit that added this file.
3. Compare the working checkout to the remote; **do not** reset, clean or stash.
4. Read this file completely, then the verbatim assignment, then v2.4.
5. Run the fresh baseline check (section 17 step 2). `main` has already moved since the frozen SHA; if any of the three blobs or the PR heads of #81/#94/#107 changed, reconcile **before** relying on any claim here.
6. Continue from section 17 step 3. Do not reconstruct completed work unless verification shows the handoff is inconsistent with the repository (then correct this file).
7. Do not implement, edit the study/ADR, create files or branches, or contact deferred PRs unless the owner explicitly authorizes it.

## 19. Transfer Status

**TRANSFER READY**, with one caveat recorded in section 15: the pushed documentation branch carries an **ADR-KERNEL-09 identifier collision with main** that needs an owner decision before any merge — conditional on the verification recorded by the committing session: the transfer commit is pushed and re-verified (remote head checked, branch re-cloned after the sandbox reset); this handoff commit is pushed and the remote head checked afterwards. If, on resume, the remote branch head does not contain this file or the transfer commit, treat the status as **TRANSFER INCOMPLETE** and report it. Not preserved by this transfer (documented, non-reproducible): the ephemeral sandbox, the earlier prototypes listed in section 8, and the conversation itself — everything else required to continue is on this branch.
