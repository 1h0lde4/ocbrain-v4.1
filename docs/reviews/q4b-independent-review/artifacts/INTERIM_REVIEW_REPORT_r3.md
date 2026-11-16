# OCBrain Q4-b independent adversarial review: INTERIM evidence report, revision 3

**Status: INTERIM. Not a validation. No overall PASS, no final recommendation, mission not closed.**
Session date: 2026-10-31. Revisions 1 and 2 are untouched; revision 2 (INTERIM_REVIEW_REPORT_r2.md, in this bundle) carries the unchanged earlier findings.
Labels: VERIFIED / PARTIALLY VERIFIED / NOT VERIFIED / CONTRADICTED / ENVIRONMENTALLY BLOCKED / NOT EXECUTED / UNRESOLVED — DEFINITION REQUIRED.
Line numbers marked "~" come from an earlier read; re-verify before citing.

## 0. What changed since revision 2
- `main` moved: `16d663a` -> `ed3d141e4bbfd0231afb1104d0a7479419f9bbf1` (merge of PR #104, head `4891756`). `git diff 16d663a ed3d141` = `core/model_router.py` (+39/-5) and `tests/test_b2c_cancellation.py` (new). No file under `core/workflow`, `core/workers`, `core/runtime`, `core/events` changed. Evidence from revisions 1 and 2 was produced on `16d663a` (the earlier revalidation on `4a4783c`); that distinction is preserved.
- Re-run on `ed3d141`: all five supplied probes and my probes A2, B, C produce normalized-identical output to `16d663a` (outputs/ed3d141_out_*.json vs outputs/out_*; uuids masked, floats rounded). Full suite on `ed3d141`: 2050 passed, 43 failed, 1 skipped, 1 xfailed, 1 deselected (run separately); the 43 failures are the identical test-id set as on `16d663a` and again all pass under the diagnostic embedding stub (43 passed). Still ENVIRONMENTALLY BLOCKED, real-model run NOT EXECUTED. `tests/test_b2c_cancellation.py` + `tests/test_workflow_crash_restart_subprocess.py`: 8 passed.
- Boundary note: my earlier cancellation observations (rev_probe_c S1-S3, rev_probe_d) were run before the revision-3 coordination constraint. They record current behavior of main; they are not a proposed contract and no test here is intended to resolve #105.

## 1. Ownership constraint (#105) and what was NOT done
- Not duplicated: no implementation, branch, competing contract test, or owner decision for #105. Issue #105's body was NOT read (URL not supplied; unauthenticated API rate-limited), so its text is NOT VERIFIED here; I rely on the #104 merge message, which states worker task-cancel becomes a failed result, the workflow retries, and #105 is tracked with an undecided contract.
- No branch or PR for #105 is visible by name. Read-only heads captured (branch names are not #105-named): `wip/fz02-b2c-cancellation-checkpoint-oct2026` = `a83f3ac` (updated from `90b375e` between my initial clone and the revision-3 fetch; 5 ahead / 70 behind main on non-main base `488129b`; last commit 2026-10-31 "Claude (FZ02-B2c)"; ownership not inferred), `follow-up/fz02-b2d-latent-token-cancellation-oct2026` = `b44bddf` (2 ahead of `4891756`; deferred, unreviewed), `fix/fz02-b2c-cancellation-terminal-oct2026` = `4891756` (merged via #104). Dependency recorded: any #105 outcome changes the cancellation findings (F-09 reporting, S1-S3, handle()/HTTP) and PR #81's cancellation test.

## 2. PR #81 (DEBT-028) source review, candidate only (head `647b63e734792b8375c0f96593407ee651af5840`; page shows OPEN, 13 commits)
Nothing was updated, rebased, merged or pushed; I read it via a fetched ref and ran probes on a `git archive` snapshot. Mergeability, read-only (`git merge-tree`): conflict in `KNOWN_ISSUES.md` only; `core/workflow/runtime.py` and `core/runtime/watchdog.py` are unchanged on main since the PR's merge-base `f13bfde`; 13 ahead / 62 behind main.
| # | Question | Finding |
|---|---|---|
| 1 | `_lock_instance()` around `resume()` | VERIFIED: exactly one use, `async with self._lock_instance(instance_id)` at the top of `resume()` (~411). |
| 2 | Broader execute()+resume() claim | NOT SUPPORTED by head source. The PR title ("concurrent executions") and body ("execute() and resume()") are stale: commits 3e1e436 and 0515a9d explicitly narrow the lock to `resume()`. `execute()` is unlocked. |
| 3 | execute() instance_id | `instance_id = str(uuid.uuid4())` (~349), fresh per call, never caller-supplied. |
| 4 | Scope of the lock | Per-object: `_instance_locks` lives on one WorkflowRuntime. My probe on the PR snapshot (rev_probe_e): same object, two concurrent resumes -> node b starts 1 time (claim holds); two WorkflowRuntime objects over one event store -> b starts 2 times; `execute()` in flight plus `resume()` of its instance on the same object -> b starts 2 times, overlapping. On main all three produce 2 starts. |
| 5 | Unsupported ownership | Cross-process and cross-object coordination, execute-vs-resume, and any durable ownership/lease record: none exist in either main or the PR. `resume()` also has no production caller (grep, section 6). |
| 6 | Compatibility with #104 | File-disjoint (#104: `core/model_router.py`; #81: `runtime.py`, `watchdog.py`). Probe P3 on the PR head: asyncio cancel during retry backoff leaves no pending `GraphExecutionWatchdog._run` (main leaks it), so the PR's `finally: watchdog.stop()` closes that leak. Semantic interaction with the undecided #105 contract: NOT assessed. |
| 7 | Tests vs #105 | `test_worker_level_cancellation_returns_failed_result_and_releases_lock` (PR tests ~966) calls `task.cancel()` on `resume()` and asserts the awaited task RETURNS `WorkflowResult(success=False)` with "cancelled" in the error, i.e. it pins "worker-level cancel is absorbed into a failed result". Its lock-release assertion is contract-neutral, but its result assertion would fail if #105 chooses to propagate cancellation. It should not be read as the future contract. Sibling tests that expect outer cancellation to PROPAGATE (cancel during `workflow.resumed`, watchdog drain) show the PR records a two-class behavior that is the status quo, not a decision. |
Genuine missing coverage in #81: execute-vs-resume, multi-object/multi-process resume, lock behavior when resume races a live execute, and any cancellation case after several completed nodes. Its same-instance resume tests were not re-run beyond probe (c).
Register wording observation (read-only, no edit): KNOWN_ISSUES DEBT-028 says nothing prevents concurrent `resume()` **or `execute()`** on the same `instance_id`; with `execute()` generating a fresh uuid4 per call, the `execute()` part cannot occur on the same id from `execute()` itself.

## 3. PR #97 (DEBT-003) crash-recovery evidence on current main
`tests/test_workflow_crash_restart_subprocess.py` and `tests/_crash_restart_child.py` are present and pass on `ed3d141`. Preserved limits: node b calls `os._exit(137)` itself (self-termination at a fixed point; not an external SIGKILL, not a kill during a checkpoint write); the A/B/C start/complete counts (1/1, 2/1, 1/1) come from the test's own JSONL log; it shows completed work retained and an interrupted node re-executed (at-least-once for that node). It does not show exactly-once, first-class attempt records, detection or accounting of the killed attempt (my re-run of its child: checkpoint shows b pending, attempts 0; orphan `worker.started` never terminalized; final b attempts=1). Not reclassified; not duplicated.
Additional windows tested (checkpoint section below): repeated recovery, stale checkpoint, failed checkpoint persistence.

## 4. Checkpoint-persistence failure contract (deterministic fault injection, main `ed3d141`; out_rev_k.json, rev_driver_ckpt.py)
Contract from source: `WorkflowRuntime._save_checkpoint()` (~427) catches every `Exception` from `event_stream.create_checkpoint` and logs a warning; it never raises. A checkpoint is an ordinary row in the same `events` table (`checkpoint` column set, event type `system.checkpoint`), written by the same `append` path, as a separate statement; there is no transaction spanning node completion events and the checkpoint. Order per node: result state set in memory -> `ProgressMonitor.record_completion` event -> `_save_checkpoint` -> next node. `ProgressMonitor._emit` does not catch; `WorkflowRuntime._emit_event` and the worker `_emit_event` do (F-15 map in r2). Checkpoint and event writes therefore do not share a failure policy.
| Scenario | Observed |
|---|---|
| K1 checkpoint call 1 (after a) raises | run returns success=True; b and c execute; a later checkpoint (call 2) contains all node states, so the lost one is healed; no event records the failure (only a log warning). |
| K2 every checkpoint write raises | `execute()` returns success=True, all nodes done, zero checkpoint rows; `resume()` reports "No checkpoint found". The API can report success with no durable recovery state, and nothing in the event history distinguishes this from a healthy run except the absence of `system.checkpoint` rows. |
| K3 hard exit just before checkpoint 2 is written (b already completed, its completion event already in the log) | resume starts a from checkpoint 1; b executes again and completes twice (starts 2, done 2); event log shows `execution.node.completed` for b twice. Stale checkpoint vs event log. |
| K4 checkpoint 2 raises, then hard exit inside c | previous checkpoint (call 1) stays available; resume re-runs b (starts 2, done 2) and c (starts 2, done 1). Already-completed b repeats. |
| K5 repeated recovery (kill at b, resume and kill at b again, resume) | b starts 3, completes 1; a runs once; checkpoint integrity preserved; at-least-once with no cap or counter of interrupted attempts. |
Also: restore replays emit synthetic `execution.node.completed` events (summary "Restored from checkpoint"), so completion-event counts in the log (a=3 in K5) are not execution counts. Not investigated: event-store growth (FZ-05), SQLite durability settings, corrupted-row recovery. No outbox or persistence change is proposed.

## 5. DEBT-029 / DEBT-044 reconciliation (not reopened)
- Guards present on `ed3d141`: `PlannerWorker._run` step 8 context save is wrapped so a persistence failure is non-blocking (planner.py ~236-246); memory write (step 7) is guarded; `merger._weave` resolves the provider inside the try (merger.py ~123-131). `tests/test_debt_029_post_dispatch_merge_isolation.py`: 3 passed on main; with the stub, `test_planner_capability_migration.py` and `test_planner_worker.py` also pass (24 passed together). The historical three-call experiment is historical; I did not re-create it.
- Residual post-dispatch points after capability dispatch (observations, not new defects): (a) asyncio cancellation absorbed by the worker and retried under a positive RetryPolicy (reproduced earlier, P5/S2): #105-owned, not pursued; (b) non-persistence preparation (`modules_used` comprehension, entity dict) outside any try, low likelihood; (c) merge branches other than the 3+ module weave not examined. `emit_progress` cannot raise (routes through the swallowing `_emit_event`). Shipped RetryPolicy default is zero, so these matter only for custom positive-retry workflows (not re-verified for the canonical planner workflow).
- DEBT-015(7) retained OPEN / DEFERRED / NON-BLOCKING; future side-effect idempotency is kept separate from the resolved DEBT-029 bug.

## 6. Identity chain (production propagation on `ed3d141`)
| Identifier | Origin | Production propagation observed | Gap |
|---|---|---|---|
| `root_operation_id` | Declared on `WorkflowDefinition` (definition.py ~138); the only production constructor of `WorkflowDefinition` is the cognitive compiler (compiler.py ~250) | Not read by `WorkflowRuntime` (0 hits), absent from worker context metadata and from every event in my probe (definition built with `root_operation_id="ROOT-OP-1"`) | Declared and compiled, not propagated by the runtime |
| `execution_id` | `/query`: client-supplied or uuid4 (api.py ~177) -> `handle(execution_id)` -> workflow metadata; runtime default is `instance_id` when absent (runtime.py ~484) | Graph registry key; `execution.node.*` and `execution.completed` payloads; planner uses it as CTX-SCOPE scope | Not recorded together with `instance_id` in any event (probe with `execution_id="CLIENT-EXEC-1"`: no event type carries both) |
| `instance_id` | uuid4 in `execute()` (~319); recovered from the checkpoint name for `resume()` | `workflow.*` and `system.checkpoint` payloads; in WorkflowResult | Not returned by `/query`; `resume()` has no production caller outside runtime.py (grep), so recovery has no production driver |
| `attempt_id` | uuid4 per attempt (~863) | Delivered to workers in `context.metadata` (with node_id, attempt, instance_id, execution_id) | Not in any event payload; checkpoint keeps only the latest |
| `CapabilityRequest.trace_id` | `default_factory=uuid4` (capability.py ~93); built at planner.py ~321, capability_executor.py ~116, adapter_runtime.py ~62, none passing a trace_id | Echoed in adapter_runtime events | Independent per site; `CapabilityResult` has no identity fields (success, output, error, adapter_used, duration_ms, metadata) |
| `event_id` | uuid per event in EventStream | Event log | Not a business identity |
Per-invocation `request_id`/`task_id` (worker.started/completed) is a further id, fresh per attempt. Conclusion: several distinct identifiers exist; the logical operation identity (`root_operation_id` -> `execution_id` -> `instance_id` -> `attempt_id` -> capability `trace_id`) is not preserved across these boundaries. No new fields are proposed. DEBT-030 and FZ-06 are the same identity-correlation defect and are counted ONCE (PR #87 records this; its diff touches only KNOWN_ISSUES.md and leaves the FZ-06 row alone).

## 7. Cross-reference (numbering schemes are not interchangeable)
| Q4-b / register item | Relationship |
|---|---|
| Q4-b F-01 (`WorkerResult.execution_detail` never populated) | Not FZ-01. Adjacent to FZ-02 (adapter ignores `route_result.execution_detail`), which concerns a different object. |
| Q4-b F-09 (watchdog leak on cancel) | #81 closes the P3 leak case in a candidate; #105 owns the contract. |
| Q4-b F-14 (core/verification absent on main) | Verification Phase C branch `3ba858a`: 61 ahead / 233 behind, merge-base `5954e44`, 45 files; stale separate candidate. |
| Q4-b F-15, F-16 | No FZ equivalent. F-16's downstream surface relates to FZ-01 (no failure channel; non-streaming `/query` returns success=True for any normal return; my probe D saw HTTP 200 success true on a provider failure: consistent with FZ-01, not new). |
| Q4-b F-17 (timeout coverage) | Not FZ-02. NamespaceBackend enforcement verified by tests, not wired into production. |
| FZ-03, FZ-04, FZ-07 | Register: FIXED + VERIFIED; not re-examined. |
| FZ-05 (unbounded growth) | Related only through event-log growth (restore replays add events); not measured. |
| FZ-06 = DEBT-030 | One finding, counted once. |
| DEBT-003 | PR #97 evidence plus section 4 windows. |
| DEBT-007 | Not examined. |
| DEBT-015 | r2 matrix; items 1, 5, 11 UNRESOLVED — DEFINITION REQUIRED; (7) OPEN / DEFERRED / NON-BLOCKING; section 6 refines item 1 (client-supplied execution_id exists; no cross-attempt identity). |
| DEBT-028 | #81 candidate; register wording vs source noted in section 2. |
| DEBT-029 | RESOLVED on main, guards present (section 5). |
| DEBT-044 | Merged (#89, #96); different store from WorkflowRuntime checkpoints; not reopened. |
Owner decisions D1 and D2 are recorded as owner-confirmed per your addendum; their content and implementation status are NOT VERIFIED here (the register row for FZ-02 says it is blocked on D2).

## 8. Documentation and candidate work kept separate
- #83 and #87: both change only `KNOWN_ISSUES.md` (1 file each); #87 leaves FZ-06 to #83. No register or doc file was edited, regenerated or reconciled.
- #93 (CTX-AUTH-002): 29 ahead / 3 behind; touches `core/cognitive/intent.py`, `planner.py`, docs, scripts, tests. Not merged; no intersection with Q4-b recovery, identity or inspection source found.
- #94 (DEBT-025): 8 ahead / 6 behind; touches `interface/api.py`, `auth.py`, `cli.py`, `tray.py`, web assets, tests, `core/event_bus.py`; 0 changed api.py lines mention `execution_id`, `/query`, `resume` or `instance_id`. Not merged; authentication is not authorization.
- #103: documentation-only, one file; v2 boundaries preserved (C-MoE coordinates; WorkflowRuntime owns workflow/node state; ExecutionRuntime owns invocation; GovernanceKernel authorizes; EventStream owns history). No v2 feature imported into v1.x findings.

## 9. Branch and PR inventory (read-only; file overlap from `git diff $(merge-base main head) head`; stacked branches on a non-main base are flagged, their divergence is not attributed to their own change set)
Open PR count per the GitHub UI header: 19; the 19 PRs that have a `refs/pull/N/merge` ref are 27 30 32 33 76 77 79 81 83 86 87 88 90 91 92 93 94 102 103 (same count; mapping inferred, API state NOT VERIFIED). 100 PR refs fetched; 54 are merged into main; the rest are open (the 19) or closed-unmerged (inferred, e.g. #98-#101).
| Workstream | Head | Disposition |
|---|---|---|
| #104 / `ed3d141` | merged | Current cancellation baseline (router-level cleanup only) |
| #105 | no visible branch | Reserved, active elsewhere; not duplicated |
| #81 DEBT-028 | `647b63e` | Open, divergent (13/62), conflict only in KNOWN_ISSUES.md; source review only |
| B2d follow-up | `b44bddf` | Deferred, unreviewed |
| B2c WIP | `a83f3ac` | Historical candidate; non-main base `488129b`; head updated between my initial clone and the revision-3 fetch |
| #97 / DEBT-003 | in `16d663a` | Merged recovery evidence |
| #89 / #95 / #96 | merged | Retry/persistence evidence; not reopened |
| #83 / #87 | open | Docs-only, `KNOWN_ISSUES.md` |
| #93 | `ccf0489` | Candidate intent/planner changes; unmerged |
| #94 | `967573f` | Unmerged auth candidate |
| #103 | `b83d9da` | Unratified future architecture |
| Verification Phase C | `3ba858a` | Separate stale candidate (F-14) |
| Other open PRs | see pr81/pr_inventory.json | #102 (7 ahead, touches KNOWN_ISSUES.md), #79, #88, #91 (90 ahead, KNOWN_ISSUES.md), #90, #92, #76, #77, #86, #27, #30, #32, #33: file-level overlap with Q4-b runtime paths: none except KNOWN_ISSUES.md; the sandbox-network stack (#50, #60, #64, #68, #69, #72, #75, #78, #84, #86) touches `core/sandbox/*` including `namespace_backend.py` (relevant to F-17 wiring), stacked on non-main bases |
Not examined: whether any of those sandbox PRs wires NamespaceBackend into production.

## 10. Final mission gate (revision 3)
| Gate | Result |
|---|---|
| Current main and SHA re-verified | `git ls-remote`: main = `ed3d141e4bbf…` at the end of this session |
| #105 not duplicated | Confirmed (section 1) |
| PR #81 not modified | Confirmed: remote head still `647b63e73479…`; I only fetched and read it; scratch clone reflog shows clone and local checkouts only, no push |
| Candidate branches unchanged by me | Confirmed (read-only fetch); `wip/fz02-b2c…` moved on its own during the session |
| #97 evidence reconciled | Yes (section 3) |
| DEBT-029/044 not reopened | Yes (section 5) |
| Root operation identity chain assessed | Yes (section 6) |
| Checkpoint-write failure | Executed (section 4) |
| FZ-06 / DEBT-030 counted once | Yes |
| Documentation/register files changed | None |
| Evidence bundle and hashes | outputs/, logs/, probes/, SHA256SUMS in the bundle |

## 11. Still outstanding (unchanged by revision 3)
Missing inputs: brief, decision pack, ledger, original probe outputs, §22 evidence. Therefore D6, criterion 12/23, §22 and the 26-criteria matrix remain NOT ASSESSED. Real-model runs of the planner/handle()/HTTP paths remain ENVIRONMENTALLY BLOCKED. Issue #105's text, D1/D2 content, per-PR open/closed API state, real uvicorn disconnect behavior, cancellation after several completed nodes, and EventStream event_id behavior remain NOT VERIFIED.
Owner decisions, not made here: hard-deadline authority (F-16); whether cancelled or deadlined runs should be resumable; what an HTTP `success` flag must reflect; whether checkpoint failure must be visible in event history or fail the run; whether NamespaceBackend wiring is expected; definitions for DEBT-015 items 1, 5, 11.
The GitHub token in the user's preferences was not used; treat as exposed and rotate.
