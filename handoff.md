# Session Handoff: FZ-02 batch B2c (cancellation is not a failure)

**How to read this.** Claims are tagged **[verified]** (checked directly by the writing session by running or reading it), **[reported]** (a user ruling or another party's statement, not independently re-checked), **[inferred]**, or **[unknown]**. Treat everything except [verified] as an input to verify. The live repository and `docs/architecture/PROJECT_INSTRUCTIONS.md` are authoritative over this file wherever they disagree.

## 1. Handoff Metadata

- Handoff version: 1
- Created at: 2026-10-26 (sandbox clock, UTC); the repo's newest commits are dated 2026-10-19
- Workstream: OCBrain **FZ-02, batch B2c** (cancellation is not a failure). Follows B2a and B2b (both merged). B3a is on hold behind B2c's review.
- Source session purpose: implement B2c under the owner's tightened approval contract, then checkpoint it and write this handoff so the work can resume in a fresh discussion.
- Repository: https://github.com/1h0lde4/ocbrain-v4.1 (owner/architect: Moncif, `1h0lde4`, also commits as `N4Z`)
- Transfer status: **TRANSFER READY** (see section 19). The implementation checkpoint and the handoff commit are both pushed and verified on the remote.
- Corrections: **C1 (2026-10-31)** retracts one claim in section 11; see `### C1` there. Every line it changed is marked **[C1]**.

## 2. Original Starting Prompt (faithful extraction, not verbatim)

The session's first message was not a task. It pasted (a) `PROJECT_INSTRUCTIONS.md`, "OCBrain v4.x", the project's governing execution contract; (b) a plaintext GitHub token inside the account's user preferences (**deliberately not reproduced here**); and (c) a Kernel handoff dated 2026-09-28 for a different workstream (Kernel v1.0 completion / branch reconciliation; roles: this account = Verification only; do not merge `feature/verification-critic-evidence-phase-c` into `main`). The pasted PROJECT_INSTRUCTIONS may be stale: the live copy is `docs/architecture/PROJECT_INSTRUCTIONS.md` in the repo.

Operative rules of that contract that this workstream has been following:
- Source-of-truth discipline: code and tests beat documents for implementation facts; verify live state before reconciling; a handoff or prior summary is an input to verify, not proof ("no assumption propagation").
- Status vocabulary: PROPOSED / ACCEPTED / IMPLEMENTED / VERIFIED / DEFERRED / REJECTED / BLOCKED / UNKNOWN. "Fixed" and "verified" are distinct; a deferral is not a closure.
- Evidence discipline: report exact paths, commands and results; use calibrated language; never claim a security control from static inspection alone.
- Laws: governance before capability; event sourcing over hidden state; isolation over convenience; determinism over magic; local-first. Four-process runtime model must not be silently changed.
- Change rules: dedicated branch per significant change; checkpoint commits; small coherent commits; review the final diff; no destructive git without authorization; every major change states architectural, governance, replay, observability, security, compatibility and rollback impact.
- Handoff rules (section 18.4.8): lossless handoff, requirement and decision ledgers, Git checkpoint pushed and verified, never store secrets, never mark TRANSFER READY unless every condition holds.

## 3. Subsequent User Instructions / Corrections (chronological; quotes where wording matters)

1. **Forensic requirements.** Branch absence is a discovery result, not a loss determination. Inspect `git reflog --all`, `git fsck --full --no-reflogs --unreachable`, PRs (number, head/base SHA, source branch, commit list, merge/squash commit, branch deleted?), detect rewritten history with `git cherry`/`patch-id`/`range-diff`, reconcile at file level, and tag conclusions by evidence tier: (1) Git topology, (2) GitHub PR evidence, (3) file/tree or patch equivalence, (4) handoff/doc evidence, (5) inference. Use the preservation-state vocabulary (branch preserved / commits preserved / work preserved, history rewritten / partially preserved / evidence preserved, objects unavailable / unaccounted). Do not call work "lost" until evidence is exhausted.
2. "Archive ref and fix": archive ref for PR #16 (DEBT-020 `CompletionStatus` prior art) and correct the docs claim that it was "left on its own branch".
3. Archive PRs #3, #4, #5, #6 **strictly ref-only** (names given; no merge, reopen, PR edits or `main` changes; re-verify the live SHA before each ref creation). "No credential should be retained or reproduced."
4. Open the DEBT-020 documentation branch as a PR as-is (no rebase), verify GitHub reports no conflict, review the 3-file diff, then merge; update-branch with a merge commit approved.
5. "Batch A": update PR #44 from `main` pinned to its reviewed head `8dec787e`, inspect diff and CI before merging; "do not create another documentation merge".
6. #44: "Choose Option 1: fix it in code before merging" (CodeQL-recognizable containment); hold, remediate, rerun CI/CodeQL, re-review, merge only with the gate green. #44 was later closed by the owner (superseded by #54/#56); PR #59 (stale duplicate) closed at the owner's "yeah".
7. **"change brain_export.py to LF, always use lf"**; "there are 2 files in CRLF, convert both then push it".
8. Queue: PRs #48 then #49 (merged); read-only reconciliation assessment of #57 ("do not update or push the branch yet"); then FZ-01/02/05/06 engineering, then #54 follow-ups (TOCTOU first, bundle validation second).
9. **Process rule:** "One queue item -> one active owner -> one branch -> immutable review target until disposition." Parallel Claudes get different items or read-only studies. Documentation-only fixes wait for the next natural doc sync; no doc-only merge for them.
10. "D1 = (a) additive result contract. D2 = (i) failure carrying partial output ... Start B2a." Immutable target `8b0fee2`; exactly one branch; B2a strictly provider-failure handling; do not touch FZ-01, FZ-05, other adapters; preserve baseline evidence; do not merge.
11. B2a rulings: `EMPTY_RESPONSE` moved into the pinned (unchanged) set; "Review/sign off first; only then update to current main, rerun all required checks, and merge the resulting head." Sign-off recorded for head `c2f6070`; merge only after green post-update CI/CodeQL.
12. "start B2b next"; B2b ruling: approved at exact head `31d7745`, interim planner-path trade-off accepted, merge before B3/B4; FZ-01 stays open; B3/B4 must deliver partial output through the proper result channel; no freeze claim. The first CI failure was a native crash in `tests/test_break_concurrency.py::test_cache_concurrency` (ChromaDB `Illegal instruction`, pytest exit 132). Track separately: the training-pair/`query_count` side effects on non-success outcomes.
13. B3 design (read-only), then the owner's revision: B3a is still next in principle but "I would not start implementation under the existing design unchanged". Findings: production registers **three** `LLM_COMPLETION` adapters (so fallback is live), and `PlannerWorker._dispatch_module()` raises a plain `RuntimeError`, discarding metadata.
14. **B2c ruling (the current contract):** "B2c approved as the next batch. Approval is limited to the cancellation correction and the evidence needed to establish it. The implementation must prove that cancellation propagates without triggering fallback or creating a new health penalty; that genuine failures retain their existing behavior; and that cancellation does not create false success-side effects. Physical provider-side termination must be independently verified or explicitly left unverified. B3a remains on hold until B2c has passed review." Also: recheck branch and working tree immediately before implementing; keep the batch narrow (no cooldown redesign, no fallback-on-stall policy change, no router redesign, no B3a metadata); required extra tests: concurrent invocations, cancellation during fallback, the completion boundary. Rule table: caller cancels during the router attempt: no fallback, no penalty; caller cancels while fallback runs: no further fallback, no penalty for the cancellation; adapter hits its own stall timeout: existing behaviour; provider raises a genuine error: existing behaviour; genuine failure then caller cancels fallback: stop, keep the genuine penalty; cancellation during cleanup: never resume the cancelled invocation, no cancellation-induced penalty. Do not detect cancellation by sniffing exception text; do not broadly convert `CancelledError` to a failed attempt.
15. **Current instruction:** "push the finished work to a momentary branch, then create a handoff file to resume the work in a new fresh discussion."
16. After the handoff push was rejected, the owner pasted a replacement credential into the chat with no other words. It was read as authorization to push the one pending handoff commit and nothing else, and it was used only for that (and for the follow-up status correction to this same file). The value is not recorded anywhere.

Standing preferences [reported]: always LF line endings; terse approvals authorize only the step just proposed, not adjacent scope; when sources conflict present both with evidence and ask; narrow scope is a feature; never reproduce or retain credentials.

## 4. Goal, Scope & Success Criteria

**Goal.** Get B2c reviewed and merged: cancellation (task cancellation and caller-side token cancellation) must stop work, must not trigger fallback, must not penalise adapter health, and must not create success-side effects; genuine failures and genuine stalls keep their current behaviour.

**In scope:** `core/model_router.py` monitored streaming, `core/capabilities/adapter_runtime.py`, the pure helper in `core/runtime/watchdog_decision.py`, and `tests/test_b2c_cancellation.py`.

**Out of scope (explicit):** cooldown/health policy redesign; fallback-after-stall policy; router redesign; B3a structured failure metadata (`attempts`, `partial_outputs`, `module_failures`); FZ-01/05/06 and other adapters; the shared-token sibling-cut defect (P4, recorded as a strict xfail) **[C1]** (latent: no production caller gives the router a shared token, C1.2); interrupting a non-token-aware adapter that is already mid-call on a token cancel (strict xfail); the training-pair side effects of non-cancel outcomes; documentation corrections (wait for the next doc sync).

**Success criteria.** The ruling in item 14, with evidence: logical cancellation proven by deterministic tests; in-process stop proven; physical provider termination either verified or explicitly marked **unverified**; fresh CI and CodeQL green on the final head; review and sign-off before merge.

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Cancellation propagates, no fallback, no new health penalty | ruling 14 | IMPLEMENTED, not reviewed | tests: token cancel terminal; task cancel during fallback; between-attempts check | checkpoint `5dade77` |
| R2 | Genuine failures keep existing behaviour | ruling 14 | IMPLEMENTED (pinned), not reviewed | tests: genuine provider failure and genuine stall still fall back and are penalised | |
| R3 | No false success-side effects from cancellation | ruling 14 | IMPLEMENTED, not reviewed | no training pair/count/promotion on CANCELLED; cancelled result is `success=False` | |
| R4 | Physical provider termination verified or marked unverified | ruling 14 | **UNVERIFIED (marked)** | only in-process stop is proven with fakes | real `OllamaProvider`/server behaviour not inspected |
| R5 | Concurrent-invocation protection | ruling 14 | IMPLEMENTED | `test_cancelling_one_request_does_not_affect_a_concurrent_request` | |
| R6 | Cancellation during fallback | ruling 14 | IMPLEMENTED (task cancel); **token cancel of an in-flight fallback NOT implemented** | pin test + strict xfail | needs a per-attempt token |
| R7 | Completion boundary | ruling 14 | IMPLEMENTED | no recording on CANCELLED; cancel during training-pair recording propagates | |
| R8 | Keep the batch narrow | ruling 14 | MET (by construction) | see section 4 | |
| R9 | Recheck branch/working tree before implementing | ruling 14 | MET | rechecked; one-owner confirmed | |
| R10 | LF line endings | preference | MET | all four files have 0 CR bytes | |
| R11 | B2c review, then B3a | ruling 14 | OPEN | no PR yet | next steps |
| R12 | Handoff pushed and verified | current instruction | MET | remote branch verified from a fresh clone | section 19 |

## 6. Current Verified State

**VERIFIED**
- Checkpoint commit `5dade77f25b48bf41d681f08e9ce9471a63466e0` is on the remote branch `wip/fz02-b2c-cancellation-checkpoint-oct2026` (remote tip equals the local commit); parent `488129b8768a88a3d21dfd80b1f5407d50aba908` (then-`main`).
- Tests (sandbox, re-measured after a sandbox reset): `tests/test_b2c_cancellation.py` **19 passed, 2 xfailed** (strict). Red on unchanged code: 12 failed, 7 passed, 2 xfailed. Related files (19): 6 failed / 479 passed before and after (same environmental ids). Entire suite: **8 failed / 2048 passed / 4 skipped / 1 xfailed / 4 errors** before; **8 failed / 2067 passed / 4 skipped / 3 xfailed / 4 errors** after; failing set identical (12 environmental ids). `scripts/check_drift.py` 15/15. `git diff --check` clean; all touched files LF.
- At write time live `main` is `f13bfdefcdd197ed1f966de0b1f93037a4168af4`; the two commits since `488129b` (PRs #85, #82) are docs-only, overlap none of the B2c files, and a dry-run merge of the checkpoint into that `main` is clean.
- The handoff commit `ba24f85ca6326f13adeb141f79d0c5e1e77ea157` (adds this file and the attachments; parent = the checkpoint) was pushed and verified from a fresh clone of the remote branch: handoff and attachments present, checkpoint an ancestor, all four B2c files present, no credential in the tree. A later status-correction commit (the branch tip, which only edits this file's status lines) follows it.

**IMPLEMENTED BUT NOT VERIFIED**
- No PR exists for B2c; no CI/CodeQL has run on it; no review or sign-off.

**UNVERIFIED / UNKNOWN**
- Whether a real model server stops generating when the client is cancelled. Real `OllamaProvider` timeouts and whether the router and `OllamaAdapter` share one Ollama backend in production configuration. `OpenAICompatAdapter` was unavailable in the sandbox, so its failure path is untested.

**DEFERRED (deliberately not in B2c):** see section 4 out-of-scope list.

## 7. Git / Repository Checkpoint

- Primary repository: `/home/claude/ocbrain-v4.1` in the sandbox (may be gone: the sandbox has been reset once already; re-clone)
- Remote: https://github.com/1h0lde4/ocbrain-v4.1.git
- Momentary branch: `wip/fz02-b2c-cancellation-checkpoint-oct2026`
- Base branch: `main`; B2c review base `488129b8768a88a3d21dfd80b1f5407d50aba908`; live `main` at write time `f13bfdefcdd197ed1f966de0b1f93037a4168af4`
- HEAD before checkpoint: `488129b` (local branch `fix/fz02-b2c-cancellation-terminal-oct2026`, now only in the sandbox, never pushed)
- **Transfer commit:** `5dade77f25b48bf41d681f08e9ce9471a63466e0` (4 files, +629/-14). Pushed and verified.
- **Handoff commit:** `ba24f85ca6326f13adeb141f79d0c5e1e77ea157` (parent = the transfer commit). Pushed and verified. An earlier push was rejected (`fatal: could not read Password ... terminal prompts disabled`; the API answered `Bad credentials`) until the owner supplied a replacement credential. A status-correction commit on top of it (the branch tip) edits only this file's status lines; find it with `git log -1 -- handoff.md`.
- Working tree: clean after the checkpoint; `.data/` is gitignored test output.
- Remote verification: checkpoint verified; handoff commit verified from a fresh clone of the remote branch. The status-correction tip was verified by comparing the remote tip with the local commit after pushing (see the writer's final report); re-check with `git ls-remote origin refs/heads/wip/fz02-b2c-cancellation-checkpoint-oct2026`.
- Remote branches from earlier batches still present: `fix/fz02-provider-failure-oct2026` (B2a, merged), `fix/fz02-b2b-stalled-deadline-oct2026` (B2b, merged), plus the archive refs listed in section 16. Nothing was deleted.

## 8. Active Files / Modified Files / Artifacts

In the transfer commit (all LF):
- `core/runtime/watchdog_decision.py`: `ADAPTER_LOCAL_CANCEL_REASONS`, `is_caller_cancellation(token)` (pure, no I/O).
- `core/model_router.py`: `_stop_generation()`; the wait loop in `_call_monitored_streaming`; classification of caller-cancelled tokens as `FailureType.CANCELLED`; skip training pair/count/promotion for CANCELLED.
- `core/capabilities/adapter_runtime.py`: `_request_token()`, `AdapterRuntime._cancelled()`, pre-attempt cancellation check, terminal handling of `failure_type == "cancelled"`, `adapter.cancelled` event, `stats()["total_cancelled"]`.
- `tests/test_b2c_cancellation.py`: 19 tests + 2 strict xfails.

Attachments added with the handoff commit under `docs/handoffs/fz02_b2c/` (these existed **only** in the sandbox's `/mnt/user-data/outputs` before):
- `fz01_b3_b4_design.md`: B3/B4 design, **revision 2** (proposed, not accepted)
- `fz02_b2a_evidence.md`, `fz02_b2b_evidence.md`: evidence records (the B2b one has an erratum about the single-adapter measurement)

## 9. Changes Made (B2c, as implemented)

1. **Router (monitored streaming).** If the *caller* is cancelled while the router waits, it now cancels and awaits its consumer and watchdog tasks (so the provider stream's `finally` runs and nothing outlives the request) and re-raises. The old `await consumer_task` inside `except CancelledError: pass` would have swallowed a caller cancellation arriving at that await; it is now `asyncio.wait({consumer_task})`, with an exception from the consumer still surfaced via `.result()`.
2. **Classification.** A token cancelled for a reason other than the attempt's own `stall`/`hard_deadline` is `FailureType.CANCELLED` (not retryable, partial text preserved as data). `provider_failure` keeps precedence.
3. **Side effects.** `CANCELLED` outcomes record no training pair, no `query_count`, no promotion. Other non-success outcomes still do (pre-existing issue, pinned by a test and tracked separately).
4. **AdapterRuntime.** A failed result with `metadata["failure_type"] == "cancelled"` ends the invocation: no `mark_failure`, no next adapter, result `success=False` with `metadata["cancelled"]=True`, `adapters_tried`; an `adapter.cancelled` event; counted in `total_cancelled`, not in `total_failures`. Before each attempt the runtime also checks the caller's token (from `request.payload["context"].cancellation_token`) and stops if it was cancelled by the caller. `asyncio.CancelledError` is deliberately not contained (the docstring says so).
5. No change to ranking, health marking, cooldowns, adapters, planner, or any other file.

Behaviour/contract notes for review: governance (no new authority; cancellation only ever stops work), replay/observability (one new event type, one new stats key), security (error text unchanged; no new disclosure), compatibility (additive; existing `stats()` consumers index keys individually), rollback (revert one commit).

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| D1 | Additive result contract: `handle() -> str` preserved, structured result added | ACCEPTED | owner (also recorded in open PR #83 as FZ-D1) | rulings | contradiction in #83 vs design |
| D2 | Stalled/hard-deadline generations fail and carry partial text | ACCEPTED; implemented in B2b | owner (#83 FZ-D2) | PR #71 merged | |
| D3 | EMPTY_RESPONSE and COMPLETED_WITH_PARTIAL_OUTPUT stay pinned unchanged | ACCEPTED as an *implementation constraint*, not an owner-approved contract (per #83) | owner ruling on PR #67 | PR #67 | outcome-policy work |
| D4 | B2c approved ahead of B3a with the tightened contract (section 3, item 14) | ACCEPTED | owner | ruling | |
| D5 | Distinguish the attempt's own watchdog reasons from caller cancellation **by reason string** (`stall`, `hard_deadline`) rather than a per-attempt token | IMPLEMENTED; my choice to keep B2c narrow | me, within the ruling | tests | owner prefers the per-attempt token now |
| D6 | Per-attempt token (fixes the shared-token sibling cut and enables in-flight interruption) is **not** in B2c. **[C1]** The sibling cut is latent today (C1.2); D6 becomes relevant once a production caller threads a token. | DEFERRED | me, flagged to the owner | strict xfails | owner decision |
| D7 | Merge sequence for reviewed PRs: sign off the current head, then update with a merge commit pinned to that head, fresh CI/CodeQL, then merge | ACCEPTED | owner | B2a/B2b | |
| D8 | No doc-only merges; fold doc fixes into the next natural sync | ACCEPTED | owner | | |

**Open decisions (none taken):** D1.1 which statuses map to `success=False`; D1.2 where partial text is delivered (dedicated field recommended); D1.3 HTTP status for failures; D1.4 degraded vs failed for multi-module partial failure; D2.2 health/cooldown policy for provider failure/stall/deadline; D2.3 fallback after a stall. All with my recommendations in `docs/handoffs/fz02_b2c/fz01_b3_b4_design.md` section 7.

## 11. Investigation Already Performed

| Area | Result | Evidence | Revisit trigger |
|---|---|---|---|
| Who cancels cancellation tokens in production | Only watchdogs: the router's own (`stall`/`hard_deadline`) and the graph watchdog (`execution stall`/`execution hard_deadline`); **no production code cancels a token for a user stop** | grep of `.cancel(` sites | new caller added |
| Which token the router sees | **[C1] RETRACTED.** The original claim (quoted verbatim in C1.1) was wrong: at `main` 16d663a no production caller gives the router a caller token; it creates a fresh local one per call (C1.2). | ~~code reading + probe P4~~ (why that evidence did not support the claim: C1.6) | a production caller threads a token |
| Task cancellation through the runtime | `CancelledError` already propagated through `AdapterRuntime` (its `except Exception` does not catch it): no fallback, no penalty. **[C1]** True at `AdapterRuntime` only: above it `Worker.execute()` turns the cancel into a failed result and the workflow retries (C1.4). | probe P3 (baseline) | |
| Defects found at baseline | P1 orphaned consumer/watchdog tasks and stream never closed on caller cancel; P2 caller cancel swallowed during the router's own consumer cancellation; P3 token cancel fell back and penalised the router; P4 stall of one module cuts a healthy sibling (sharing the token). **[C1]** P3 and P4 reproduce only for a caller that gives the router a token-carrying context; no production path does (C1.2). P1 and P2 (task cancellation) are the production-reachable ones. | deterministic probes, then tests | |
| Production adapter chain | `main.py:282-287` registers `ModelRouterAdapter`, `OllamaAdapter`, `OpenAICompatAdapter`; ranking by health, cooldown 60 s x 2^(n-1) capped at 1 h | code + measured probe | |
| B2a/B2b activated fallback | A failure/stall/cancel on the router now benches it ~59 s and falls back to `OllamaAdapter` (full second generation; cancel did not stop it); recorded in design rev 2 and the B2b erratum | measured probe on pre-B2 vs current | |
| `OllamaAdapter` | Same default host, non-streaming, no watchdog (timeouts not inspected), **raw exception text in its `error`** | code reading | |
| Open PRs #83 and #88 | #83 records FZ-D1/FZ-D2 and says FZ-02 is not fully closed and FZ-01 is open; #88 records the DEBT-043 response-path disposition (K4.2 pairing retained, "C-plus" selected for implementation) | read via fetched PR heads | before B3b |

Not investigated: real provider/server cancellation behaviour; `OpenAICompatAdapter` internals; other adapters. **[C1]** (Previously also listed here: the graph watchdog's own cancellation of node tasks. Investigated on 2026-10-31: it does not cancel node tasks, see C1.5.)

### C1. Correction (2026-10-31): the production router does NOT receive the workflow-level cancellation token

Verified against `main` 16d663a by reading the code and by running `docs/handoffs/fz02_b2c/fz02_gate_probe.py` (attached on this branch; `OCROOT=<checkout> python3 <path>`). The live code is authoritative. Nothing is silently replaced: the retracted text is quoted below, and the lines C1 changed are listed in C1.7.

**C1.1 Retracted claim (verbatim from the original section 11 row)**

> Which token the router sees: "The workflow-level token (`workflow/runtime.py:483, :885` passes it into the node's `ExecutionContext`); so one module's stall cancels a token shared with sibling modules." Evidence given: "code reading + probe P4".

Statements that depended on it and are now annotated **[C1]**: the "Defects found at baseline" row (P3, P4) and section 15 item 4 (the shared-token sibling cut).

**C1.2 Verified call paths** [verified at `main` 16d663a]

| Path | Passed as the context | Carries `cancellation_token`? |
|---|---|---|
| `PlannerWorker` (`core/workers/planner.py:321-326`): the `CapabilityRequest` payload has `"context": self._context_memory`; its direct fallback is `self._model_router.route(mod_name, query, self._context_memory, scope=scope)` (`:344-345`) | `context_memory` | no |
| `capability_executor` (`core/workers/capability_executor.py:116-121`) | `""` | no |
| `orchestrator.py:923`: `self.router.route(mod_name, query, self.context)`; `self.context` is set at `:123`; `main.py:403` builds `Orchestrator(modules, context_memory, ...)` | `context_memory` | no |

Probe on the real objects: `ContextMemory` has no `cancellation_token`; `_request_token()` returns `None` for both request shapes; `ModelRouter._resolve_cancellation_token()` returns a fresh `CancellationToken()` on every call (not shared, and cancelled only by the router's own watchdog). The workflow token does exist one level up: `workflow/runtime.py:885` passes it into each node's `ExecutionContext`, so `PlannerWorker._run` receives it. It is not forwarded to the router.

**C1.3 Live versus latent** [verified]

| Behaviour | Status at `main` 16d663a |
|---|---|
| Caller-**task** cancellation (`asyncio.CancelledError` while a task awaits `ModelRouter.route()`): the router stops its consumer/watchdog tasks and the stream and does not swallow the cancel; `AdapterRuntime` does not contain it (no fallback, no health penalty) | **LIVE**: reachable whenever something cancels that task |
| **Token-driven** cancellation (`CancellationToken.cancel(reason)` observed by the router or `AdapterRuntime`): `CANCELLED` classification, pre-attempt token check, terminal `cancelled` handling, token delivery to an in-flight fallback, the shared-token sibling cut | **LATENT**: no production caller supplies a token |

"Live" means reachable. Whether an in-process mechanism actually triggers it is C1.4 and C1.5.

**C1.4 What happens in the real workflow when the task is cancelled** [verified, probe 2]

The task running `WorkflowRuntime.execute()` was cancelled at 0.5 s (node retry policy `max_retries=1`). `execute()` returned a result at about 2.5 s (`task.cancelled()` was False) and the node ran twice. Cause: `Worker.execute()` (`core/workers/base.py:293`) catches `asyncio.CancelledError` and returns `WorkerResult(success=False, error="Worker cancelled")`; the workflow retry loop checks only the token (`core/workflow/runtime.py:865`), not task cancellation. With the B2c router fix the first provider stream closed at 0.5 s; on unchanged `main` no close was observed for that attempt. This is NOT fixed by B2c and needs its own tracked item and an owner decision.

**C1.5 The graph watchdog does not stop a node's task** [verified, probe 1]

`GraphExecutionWatchdog` only sets the workflow token (`core/runtime/watchdog.py:180,196`). That token is read cooperatively before a node is traversed and before each retry attempt (`core/workflow/runtime.py:723,865`), and by workers that choose to check it. Probe 1: graph budget hard=0.3 s; the token was cancelled with reason `execution hard_deadline`; the node kept running inside the router until the router's own hard deadline, and the workflow returned after 2.03 s. The repo's own test fixture `SlowNodeWorker` (`tests/test_workflow_runtime.py`) states the same: `ExecutionRuntime.invoke()` does not forcibly preempt a running worker. In-process I found no site that cancels a task on the request path (no `wait_for` or timeout around `handle()` or node execution). External triggers (server shutdown, Ctrl-C, client disconnect) were NOT verified.

**C1.6 How the incorrect claim entered this handoff**

[verified] The handoff cited "code reading + probe P4" as its evidence.
(a) The code reading was right as far as it went: `workflow/runtime.py:885` does put the workflow token into each node's `ExecutionContext`.
(b) The hop that was not traced is from the node's `ExecutionContext` to the router. `PlannerWorker` does not forward `context.cancellation_token`; it passes `self._context_memory` (C1.2).
(c) The probes drove the router with a test context that carries a token: the helper `_Ctx` in `tests/test_b2c_cancellation.py` (at checkpoint `5dade77`) gives its context a `cancellation_token`. Those probes showed what the router does when it is given a token, and were read as showing what production gives it.

[inferred] That (b) and (c) are how the claim formed. The original session's reasoning is not available; this is reconstructed from the evidence the handoff itself cited.

Propagation: the claim was repeated in the P3/P4 baseline-defects row, in section 15 item 4, and in the first text of PR #104 (limitation 3). The PR text was corrected on 2026-10-31 by editing the PR body (head unchanged) before any review.

**C1.7 Scope of this correction**

Changed: one metadata line in section 1; one clause in the section 4 out-of-scope line; the D6 row in section 10; in section 11, three table rows and the "Not investigated" line; section 15 item 4; this block; and the attachment `docs/handoffs/fz02_b2c/fz02_gate_probe.py`. Nothing else in this file was modified. Sections 7 and 17-19 still describe the state at `90b375e` and are NOT updated here: later events (PR #104, the narrowing of B2c, and the deferred portion on `follow-up/fz02-b2d-latent-token-cancellation-oct2026`) are recorded in PR #104 and on that branch, not in this file.

## 12. Failed Attempts / Dead Ends

- **Shared `ExecutionBudget` in probes.** `ExecutionBudget` is a non-frozen dataclass; a probe that returned one shared instance from `ExecutionPolicy.for_generation` leaked state across scenarios and produced a bogus "healthy stream classified hard_deadline". Production builds a fresh budget per request. Always return a fresh budget in probes and tests.
- A first patch script aborted on my assumption that the router imports `CancelReason` on one absolute line (it uses relative imports). Fixed by reading the import style first.
- **The git-bundle restore test was never completed.** The command that was meant to prove the bundle restores the handoff in a fresh clone died on a shell syntax error before reaching that step; only `git bundle verify` ran (it listed the one prerequisite commit). The bundle is therefore a secondary, unproven copy; the remote branch is the primary one and was verified from a fresh clone.
- Shell pitfalls in `/bin/sh` (dash): no `${var:0:7}`, no `<(...)`, `cut -c` splits multi-byte UTF-8 and breaks tool output, `pkill -f` patterns can match your own shell.
- Actions job logs and artifacts returned 403 for the available credential; the public job page only loads logs after sign-in; `.diff` endpoints redirect to a host the sandbox cannot reach (read PR diffs by fetching `refs/pull/N/head` over git instead).
- Running two full test suites concurrently makes `tests/core/sandbox/test_namespace_backend.py::test_cancel_kills_all_descendant_processes` fail (system-wide `pgrep`). Run suites sequentially.

## 13. Verification Evidence

Environment: sandbox, Python 3.12, pytest 9.x, pytest-asyncio 1.x, 1 CPU core; the full CI environment (real chromadb etc.) is **not** reproduced, so CI can differ.

| Check | Scope | Result |
|---|---|---|
| `pytest tests/test_b2c_cancellation.py` (unchanged code, tests copied in) | red evidence | 12 failed, 7 passed, 2 xfailed |
| `pytest tests/test_b2c_cancellation.py` (checkpoint) | green | 19 passed, 2 xfailed |
| related files (19; the test files referencing router/runtime/watchdog/cancellation) | regression | 6 failed / 479 passed before **and** after (6 failures are in `tests/test_audit_fixes.py`, environmental) |
| `pytest tests` (entire suite), run alone | regression | before 8 failed / 2048 passed / 4 skipped / 1 xfailed / 4 errors; after 8 failed / 2067 passed / 4 skipped / 3 xfailed / 4 errors; **failing set identical** |
| `python3 scripts/check_drift.py` | drift gate | 15/15 |
| `git diff --check`; CR-byte count | hygiene | clean; 0 CR bytes in all four files |

The 12 environmental failing/erroring ids are the same set on every baseline taken in this workstream (`test_audit_fixes`, `test_break_*`, `test_module_factory_security`, `test_system_ctrl`); regenerate the list by running the full suite on `main`.

The red-state failures are genuine assertions, not timeouts: stream `finally` never ran and 2 tasks stayed alive after a caller cancel; a caller cancel during the router's consumer cancellation was swallowed (`DID NOT RAISE CancelledError`); a token cancel fell back to `OllamaAdapter` with `success=True`; a cancelled generation was classified `hard_deadline`; between-attempts cancel did not stop the fallback; a cancelled sibling's stream was never stopped.

## 14. Environment / Tooling Assumptions

- Sandbox shell is `/bin/sh` (dash). Python deps must be reinstalled after a reset: `pip install pytest pytest-asyncio datasketch tomli-w fastapi httpx pydantic aiofiles aiohttp beautifulsoup4 click feedparser PyYAML requests rich scipy trafilatura "uvicorn[standard]" --break-system-packages` (chromadb and sentence-transformers are not installed; that is why some suite results differ from CI).
- Running tests rewrites `config/*.toml` and `data/context.sqlite` and can create `modules/test_*`; clean up with `git checkout -- config/ data/context.sqlite && git clean -fdq modules/` (do **not** commit those).
- Network allowed from the sandbox: github.com, api.github.com, codeload/raw/release-assets GitHub hosts, PyPI, npm, crates, ubuntu mirrors. The unauthenticated GitHub API shares a 60/hour per-IP limit and is usually exhausted; public PR HTML pages and `git fetch origin refs/pull/N/head` work without it.
- **Credential.** The token supplied in the account's user preferences (location only; no value is recorded here) stopped working shortly before this handoff (`Bad credentials`; the write endpoint asked for a password). The owner then pasted a replacement into the chat; it was used only to push this branch. Treat it as exposed (it sits in the chat transcript): rotate it, and prefer a fine-grained token limited to this one repository. Whether it still works is unknown; test with a `git push --dry-run` before relying on it. Use a one-off URL for pushes, redact output, and confirm `grep ghp_ .git/config` is empty afterwards. Never write a credential into a file, commit, memory note or this handoff.
- Set `git config user.name "Claude (FZ02-B2c)"` and `user.email claude@anthropic.com` per fresh clone.

## 15. Unresolved Questions / Risks / Blockers

1. **Credential hygiene (not a blocker for reading this):** pushing from a fresh session needs a valid credential (see section 14); the one used for the handoff push was exposed in chat and should be rotated.
2. Physical provider termination on cancel is unverified (R4).
3. A token cancel arriving while a non-token-aware fallback adapter is already mid-call is not delivered to it (strict xfail). Task cancellation is.
4. One module's stall cancels the shared workflow token and cuts healthy sibling modules mid-stream (strict xfail; pre-dates B2a/B2b; B2b made its consequence a failure plus fallback). Proper fix needs a per-attempt token. **[C1]** Not reachable through any production path at `main` 16d663a (no shared token reaches the router); it holds only for a caller that shares one token across modules (C1.2).
5. Live production effects of B2a/B2b not changed by B2c: a genuine failure/stall benches `ModelRouterAdapter` for ~59 s and later 2, 4, ... minutes (D2.2), and a stall triggers a second full generation on `OllamaAdapter` (D2.3). B2c removes only the cancel case.
6. Training pairs, `query_count` and promotion are still recorded for provider failure, stalled and hard-deadline outcomes (pinned by a test, tracked separately).
7. `OllamaAdapter`'s `error` and the final `AdapterRuntime` error carry raw exception text (log-only today; must never reach a user-facing channel).
8. **Reconcile with owner docs before B3:** open PR #83 (FZ-D1 says: preserve `handle() -> str`; structured internal result; **do not use a typed exception as the primary result channel**). The B3a design's `CapabilityInvocationError` is a carrier at the planner boundary, not the primary channel, but re-check against #83's wording. Open PR #88 (DEBT-043 clarification response path) will collide with the orchestrator's clarification exit (L508) in B3b.
9. The CI `tests` job once crashed natively (`Illegal instruction` in ChromaDB, exit 132) on an unrelated test; a rerun passed. Expect the possibility on any PR; rerun only the failed job and record it as an environmental incident.
10. Other open PRs touching nearby areas: #81 (DEBT-028 workflow-runtime concurrency lock), #89 (DEBT-029 context persistence). Check for overlap before B3.

May work safely continue without resolving these? Yes for B2c review (items 2-7 are documented limitations); item 8 must be resolved before B3b/B4.

## 16. Relevant Information / References

- Authority order: kernel constitution (`OCBRAIN_KERNEL_CONSTITUTION.md`, repo root) -> `docs/architecture/PROJECT_INSTRUCTIONS.md` -> architecture docs -> ADRs; code beats docs for implementation facts.
- Merged earlier in this workstream: PR #52 (DEBT-020 doc correction, merge `4b535ed`), #48 (`c8a77b0`), #49 (`7464a84`), #67 B2a (merge `8c0ea03`), #71 B2b (merge `27d918d`). Closed unmerged: #44 (superseded), #59 (stale duplicate). Merged by the owner/other sessions: #56 (/import boundary, closes #54's core), #57.
- Archive refs on the remote: `archive/fix-debt-020-completion-semantics-sep2026` (`fcd3700`), `archive/pr-03-fix-adaptive-semaphore-instability-jun2026` (`601b833e`), `archive/pr-04-systematic-audit-jul2026` (`7150a4ba`), `archive/pr-05-bug-research-hardening-jul2026` (`3da834e6`), `archive/pr-06-github-release-automation-aug2026` (`6e718580`). Do not delete.
- Open PR queue seen at write time (state from public PR pages): #79, #81, #83, #86, #87, #88, #89, #91 open; #76, #77 Dependabot; #90 appears to be a draft; verify live.
- FZ register: `KNOWN_ISSUES.md` section "Kernel v1.0 Freeze Remediation" (FZ-01..FZ-07, batches B1..B9, decisions FZ-D1..D3). B5 (FZ-06 identity) follows B3; B6 follows B3/B5; B7 is blocked on FZ-D3 (needs an ADR).
- The B2c design reasoning and the cancellation rule table are the owner's ruling (section 3, item 14).

## 17. Next Steps (in execution order)

1. **Restore access and state.** Re-clone, reinstall dependencies (section 14), obtain a fresh push credential from the owner, and verify `main`, the checkpoint branch and the branch list before touching anything (R9 applies again: confirm one owner, no rival branch or PR for B2c).
2. **Confirm the transfer.** `handoff.md` and `docs/handoffs/fz02_b2c/` are already on `wip/fz02-b2c-cancellation-checkpoint-oct2026`; just verify (a copy of `handoff.md`, the three attachments and a git bundle of the first handoff commit were also saved in the session outputs).
3. **Cut the official branch.** `git checkout -b fix/fz02-b2c-cancellation-terminal-oct2026 origin/main && git cherry-pick 5dade77` (never merge the wip branch; never put `handoff.md` in the PR). If `main` moved onto the B2c files, re-verify first. Name the immutable review target (the `main` SHA at that point).
4. **Re-establish evidence on the official branch.** Baseline (related files and entire suite on `main`), red (copy `tests/test_b2c_cancellation.py` into a detached worktree of `main`: expect 12 failed / 7 passed / 2 xfailed), green, drift gate, LF check. Do not trust this file's numbers without re-running.
5. **Open the PR** (one PR, single owner): scope, change, evidence, the limitations in section 15 items 2-7 stated plainly, and the interim effects. Wait for `tests`, `drift-and-ownership` and CodeQL on the exact head; if `tests` fails check for the ChromaDB native crash and rerun only the failed job.
6. **Write the B2c evidence record** (same format as the B2a/B2b records) and mark physical termination as unverified unless you can verify it.
7. **Review and sign-off, then** update the branch against current `main` with a merge commit pinned to the signed-off head, wait for fresh CI/CodeQL, re-check that `main` has not moved, merge only if green, then audit `main` (parents, tree identity, tests, drift).
8. **Only after B2c passes review:** reconcile B3a with PR #83's FZ-D1 wording and PR #88, decide D1.1-D1.4 and D2.2-D2.3 with the owner, then start B3a per `docs/handoffs/fz02_b2c/fz01_b3_b4_design.md` (revision 2): additive carry of `attempts`/`partial_outputs`/`module_failures`; no change to ranking, health, fallback, success flags or answer text.
9. Keep tracked and separate: per-attempt token (D6), training-pair side effects of non-cancel outcomes, the pending doc corrections (FZ-02 register row, FZ-05 wording "exposes only create/get/ids" is imprecise, DEBT-033 row, CTX-EXPORT-001 reconciliation), #54 follow-ups (TOCTOU, bundle validation), FZ-05/06/B5-B7.

## 18. Resume Instructions

Do these first, in order, and stop on any mismatch:
1. Read `docs/architecture/PROJECT_INSTRUCTIONS.md` and this file completely; read the memory notes for the OCBrain project (they hold the owner's standing preferences and decision history).
2. `git fetch origin`; confirm `origin/main` (written as `f13bfde...`) and whether it touched `core/capabilities/adapter_runtime.py`, `core/model_router.py`, `core/runtime/watchdog_decision.py`, `core/runtime/execution_watchdog.py`, `core/workers/planner.py`, `core/workflow/runtime.py` or `core/orchestrator.py`.
3. Confirm the remote branch `wip/fz02-b2c-cancellation-checkpoint-oct2026` is at `5dade77f25b48bf41d681f08e9ce9471a63466e0`, and whether `handoff.md` is on it.
4. Confirm no other branch or PR for B2c exists (one-owner rule) and read open PRs #83 and #88.
5. Resolve any mismatch with the live repository before changing code; correct this file if it was wrong. Do not repeat investigations listed in section 11 unless the repository changed.

## 19. Transfer Status

**TRANSFER READY.**

- Implementation checkpoint `5dade77f25b48bf41d681f08e9ce9471a63466e0`: committed, pushed, remote tip verified. Nothing of the B2c implementation exists only locally.
- Handoff commit `ba24f85ca6326f13adeb141f79d0c5e1e77ea157`: pushed and verified from a fresh clone of the remote branch (handoff and attachments present, checkpoint an ancestor, all four B2c files present, zero credentials in the tree).
- The branch tip is a small follow-up commit that corrected this file's status lines after the push succeeded; it changes nothing else.
- No PR exists for B2c, nothing was merged, and this branch must never be merged into `main` (it carries a session artefact). The official B2c branch is cut from commit `5dade77` (section 17, step 3).
- A first push attempt failed because the credential had been rejected; the owner supplied a replacement in the chat. The original failure is recorded in sections 7 and 14.
