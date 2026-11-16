# OCBrain Q4-b independent adversarial review: INTERIM evidence report, revision 2

**Status: INTERIM. Not a validation. The mission is not closed and no final recommendation is issued.**
Reviewer session date: 2026-10-31. Revision 1 (INTERIM_REVIEW_REPORT.md, bundle SHA-256 7dbf02ee65754862bf23a390f3bbde6508394c7fccf92f2d08ea4c47dbd34ec8) is left untouched; this revision supersedes it.
Labels: VERIFIED / PARTIALLY VERIFIED / NOT VERIFIED / CONTRADICTED / ENVIRONMENTALLY BLOCKED / NOT EXECUTED / UNRESOLVED — DEFINITION REQUIRED.
Line numbers marked "~" come from an earlier read and must be re-verified before citing.

## 0. Corrections to revision 1
1. **Namespace sandbox tests.** Rev 1 called the 8 failures UNCLASSIFIED and said the NamespaceBackend timeout was not exercised. Corrected: the 8 failures were an artifact of my venv location (`sys.executable` = /home/claude/review/venv/bin/python is not visible inside the sandbox, so `execvp` fails in `_ns_init.py`). With the system interpreter as `sys.executable` (venv site-packages via PYTHONPATH) all 14 tests pass (logs/ns_tests_system_python.log vs ns_tests_venv_python.log). That includes `test_timeout_terminates_long_running_command` and `test_cancel_kills_all_descendant_processes`, so NamespaceBackend's timeout and descendant-kill enforcement are VERIFIED at runtime. A repo-wide grep of *.py finds no reference to `NamespaceBackend` outside its own module, tests and one docstring in `_seccomp.py`: production wiring NOT found.
2. **DEBT-015 item 1.** Rev 1 said no request-id handling was found. Incomplete: `/query` accepts a client-supplied `execution_id` and uses it as the execution id (interface/api.py ~177-185; observed in rev_probe_d meta.execution_id). Whether that satisfies "stable operation identity end to end" depends on the item's definition: UNRESOLVED — DEFINITION REQUIRED.
3. **Full suite.** Rev 1 reported 28% completion. With HF_HUB_OFFLINE=1 (blocked model loads fail fast) the suite now completes (section 6).
4. **Runtime gaps 2 and 3** are now EXECUTED at workflow level (section 6).

## 1. Provenance
- Repository: github.com/1h0lde4/ocbrain-v4.1 (public; cloned and fetched without credentials). `origin/main` = `16d663ac8449965f774033da46d5063506a772a7`; `4a4783c47ac37971a7d51ab3d7ab6fc904a37106` is an ancestor. Scratch clone detached at 16d663a; probes and tests ran in `git archive 16d663a` snapshots. No repo file, branch or commit was created or changed.
- `4a4783c..16d663a` = 5 commits (e721960, 1ec5451, 7bb0ce2, c228f16, merge 16d663a). `git diff 4a4783c 16d663a -- core` = 0 lines. Changed: KNOWN_ISSUES.md, tests/_crash_restart_child.py (new), tests/test_workflow_crash_restart_subprocess.py (new), tests/test_workflow_runtime.py. The earlier revalidation was on 4a4783c; the claim "ten of twelve audited source files byte-identical" was NOT checked (the twelve files are unknown to me).
- Supplied: files.zip SHA-256 `73c4e52440d018d86194e9ccb0db7feb72224263caf5754a5045b30c750d2222` (8,443 bytes): probe_main.py a761827d450591ddf2d0589b0a65428c5c1703a52f1b1ec4b19b66bfdd87e395; probe_main2.py dc69e68f7818a77b09611fdf6c5a2cfd3c58805d6836fdd18efa6a016535110e; probe_main3.py e1aee93306461167996380d5dd783e525fee780bd6897ee3511d134c6ad1154c; probe_main4.py 5ef869ee74f6749e0a65b937b799582a2750e01513e116eb9ee7c0e51a9f23ed; probe_main5.py 403f6c37853fe8db33a128d22a8f56faaf2ce96511c7016f862bb60ebe522a11; README.md fc5ba8aeb31db4a4983600a32233a64c3755ec5c7249b4c8c9e536e1916d5681.
- NOT supplied (nothing substituted): Q4-b brief, decision pack, ledger (MD/DOCX/PDF, hashes, revision labels/counters), original probe outputs, §22 evidence. NOT ASSESSED for that reason: D6 consistency, criterion 23, criterion 12 (§21), §22, the 26-criteria matrix, and the wording of every finding in those documents. The later pasted analysis is not one of the named inputs.
- Environment: Python 3.12.3; venv outside the repo; torch 2.15.0+cu132, sentence-transformers 3.4.1, chromadb 0.5.3, fastapi 0.162.0, pytest 9.2.0, pytest-asyncio 1.4.1; `pip check` clean; freeze in env/. requirements.txt not modified. Install was staged (see env/), so resolved versions may differ from a single-pass resolver run.

## 2. Executive disposition (interim)
Technical claims examined (F-15, F-16, F-17 core claim, F-01, F-14, P5b) are SUPPORTED WITH QUALIFICATIONS; several are understated and one probe conclusion (P5b) rests on a filter artifact. Most of the mission cannot be assessed without the missing inputs. Final recommendation: withheld.

## 3. Findings register
| ID | Independent conclusion | Evidence |
|---|---|---|
| F-15 | Both reported outcomes reproduce. More outcomes exist (3a). | out_probe_main4.json; out_rev_a2.json |
| F-16 | Reproduces. When the non-polling node is the last node, the workflow returns success=True, error "" although the hard deadline fired and the token is cancelled; events show `execution.node.failed` then `execution.node.completed`. Observation only: graph/event surface, WorkerResult/node state and checkpoint disagree; which surface is authoritative for a hard deadline is not defined in the code I read and is an owner/architecture question, not a reviewer rule. | out_rev_a2.json `last_node_deadline` |
| F-17 | No preemptive timeout in worker, runtime, workflow or orchestrator paths (grep). The enumeration "model call, skill, stub backend" is incomplete: NamespaceBackend (namespace_backend.py:251) enforces a timeout and kills the process group (VERIFIED by passing tests) but is not wired into production code (grep). I/O client timeouts also exist (model_router.py:302, classifier.py:97, network.py, web/fetcher.py); whether they count is definitional. | grep; logs/ns_tests_system_python.log |
| F-01 | Field and nine-member FailureType exist. `execute()` sets `WorkerResult.execution_detail` on no path; P9 reproduces null on four paths. No production assignment found; the only ExecutionOutcome producer is model_router (on RouteResult). The amendment's wording is not assessable (brief missing). | out_probe_main5.json; grep |
| F-14 | VERIFIED at layout level: `core/verification` absent on main 16d663a (`git ls-tree` empty), present on origin/feature/verification-critic-evidence-phase-c. Branch contents not reviewed. | git |
| P5b | Filter artifact: `payload_workflow_id` misses `execution.failed` (its payload has no workflow_id). Unfiltered, a swallowed asyncio cancel emits worker.cancelled, execution.completed(false), execution.node.failed, execution.failed, workflow.completed(false). Real gap: no cancelled status/event above worker level. | out_rev_b.json |
| F-09 | Reproduces; also reproduced through an HTTP-level request cancel (rev_probe_d: `GraphExecutionWatchdog._run` left pending). | out_probe_main3.json; out_rev_d.json |

### 3a. F-15 event-store failure map (one append failed; one-node workflow)
| Failed call | Outcome |
|---|---|
| 1st ProgressMonitor append (root RUNNING) | `execute()` raises OSError before any node runs (progress.py:34 -> :57); no checkpoint. One failure suffices. |
| node RUNNING status | masked error "Unexpected workflow error: …"; node never executed; no checkpoint. |
| `execution.node.completed` (node succeeded) | node result True, workflow success=False with masked message; no checkpoint. |
| `execution.node.failed` | real error "boom" replaced by the masked message (node_results keeps boom); no checkpoint. |
| root final status | `execute()` raises OSError AFTER the node ran and the checkpoint was saved; watchdog task leaked (stop not reached). |
| worker.*, workflow.started, WorkflowRuntime execution.completed/failed, workflow.completed | swallowed; outcome unchanged. |
Cause: ProgressMonitor._emit (~55-73) does not catch; WorkflowRuntime._emit_event and the worker `_emit_event` do; `_run`'s docstring says it never raises.

## 4. DEBT-015 matrix (PROVISIONAL; grep plus the runs here; per-item tests not examined; no coverage numerator/denominator is changed by this table)
| # | Requirement | Status | Evidence / limits |
|---|---|---|---|
| 1 | Stable operation identity end to end | UNRESOLVED — DEFINITION REQUIRED | `/query` accepts client-supplied `execution_id` and uses it; attempt_id is a fresh uuid4 per attempt (runtime.py:863); no identity spans retries/attempts. Rev 1 "NOT IMPLEMENTED" withdrawn |
| 2 | ExecutionAttempt record | NOT IMPLEMENTED (VERIFIED by grep) | 0 hits; only `attempts`/`attempt_id` fields on WorkflowNodeState |
| 3 | ExecutionSnapshot | NOT IMPLEMENTED (VERIFIED by grep) | 0 hits; other names not searched |
| 4 | Extended FailureType/FailureClass | NOT IMPLEMENTED (VERIFIED) | FailureClass 0 hits; FailureType has 9 members |
| 5 | RecoveryDecision | UNRESOLVED — DEFINITION REQUIRED | 0 hits for the name; `watchdog_decision.decide()` is a stall/extend/cancel core that its docstring says is not recovery. Whether the criterion measures events, decisions or persisted evidence is undefined here |
| 6 | Node-boundary checkpoint | IMPLEMENTED; PARTIALLY VERIFIED | Survives a real hard kill and drives a fresh-process resume. Limits: RUNNING never persisted (sequential traversal, one save per finalized node); execution_detail not serialized; checkpoint skipped when ProgressMonitor emission fails; cancellation recorded as failed/pending only (section 6) |
| 7 | Retry/idempotency | PARTIALLY VERIFIED | fresh attempt_id per attempt; interrupted node re-executed on resume (real kill). NOT CHECKED: EventStream.append event_id behavior |
| 8 | Stale-attempt rejection | NOT IMPLEMENTED (VERIFIED by grep) | no stale/supersede logic in runtime paths |
| 9 | Worker-level integration | PLUMBING ONLY | attempt_id reaches workers in context.metadata (~881); no production worker uses it |
| 10 | Capability-level integration | NOT IMPLEMENTED (PARTIALLY VERIFIED) | no idempotency/attempt hits under core/capabilities; CapabilityRequest fields not read |
| 11 | Richer inspection UI | UNRESOLVED — DEFINITION REQUIRED | endpoints exist (api.py ~212, ~226; test_execution_inspection 6 passed); the baseline "merged today" is undefined; no historical cutoff inferred |
| 12 | Durable cross-attempt history | NOT IMPLEMENTED (PARTIALLY VERIFIED) | event log durable but attempts cannot be correlated to events; checkpoint keeps only the latest attempt_id/count |

## 5. Real-process kill and resume (new test in 16d663a)
- Test: `tests/test_workflow_crash_restart_subprocess.py` + `tests/_crash_restart_child.py`; node b calls `os._exit(137)` itself (self-termination at a fixed point, not an external SIGKILL, not a kill during a checkpoint write). Passes on 16d663a.
- ESTABLISHED by the test: process termination (exit 137); a's checkpoint survives; a fresh process resumes from disk; a not re-run; b starts twice and completes once; c runs once; final success. "b started twice" comes from the test's own JSONL log, not system state.
- NOT established, and contradicted as a system capability by my re-run (kill_resume/): after the kill the checkpoint holds b = pending, attempts 0, attempt_id "", indistinguishable from never started. The append-only log keeps `execution.node.status b running` and `worker.started` (task 3f7d3cd3…) with no terminal event, before and after resume; `workflow.resumed` payload is empty; final b = completed, attempts=1; resume returns success=True with no indication of the interrupted attempt. Recovery is demonstrated; detection, accounting and terminalization of an externally killed attempt are not. These are separate claims.

## 6. Runtime gaps and tests
| Group | Status |
|---|---|
| handle() and HTTP under cancellation | NOT EXECUTED with the real embedding model (huggingface.co unreachable: NameResolutionError). SUPPLEMENTAL, embedding STUBBED (rev_probe_d): (a) direct `task.cancel()` of `handle()` mid provider call does NOT raise: the worker swallows it and `handle()` returns "Sorry, I encountered an internal error: WorkflowFailure…" with no memory write; (b) a cancelled HTTP request task raised CancelledError and left `GraphExecutionWatchdog._run` pending (cancel via httpx ASGITransport, not a real uvicorn disconnect); (c) provider failure over `/query` returned HTTP 200, `success: true`, `error: null`, with the failure only in the answer text. Execution registry shows no nodes or cancelled marker for either cancelled execution. |
| resume() after cancelled/deadlined run | EXECUTED (rev_probe_c). S1 hard deadline (node a ignores token): first run "Workflow cancelled", checkpoint a=completed, b=pending; resume runs only b and returns success=True, error "" (cancellation leaves no trace; a deadlined run is indistinguishable from a crash). S2 swallowed asyncio cancel: a checkpointed as failed ("Worker cancelled"); resume re-executes nothing and replays the failure, so a cancelled run cannot be resumed. S3 asyncio cancel during retry backoff: CancelledError propagates, no checkpoint exists, resume reports no checkpoint. |
| Checkpoint after asyncio cancellation | EXECUTED (same runs, S2/S3 above). Not tested: cancellation after several completed nodes. |
| Process kill and recovery | EXECUTED (section 5). |

Full suite at 16d663a (HF_HUB_OFFLINE=1; system interpreter as sys.executable; the crash-restart test deselected and run separately): 2043 passed, 43 failed, 1 skipped, 1 xfailed, 1 deselected, 114 s (logs/suite_all.log). All 43 failures are in 14 files; none was individually inspected beyond the one-line causes. Root-cause lines: 11 direct "couldn't connect to huggingface.co" errors; the others are assertion failures downstream of a failed planner pipeline. DIAGNOSTIC: the same 43 tests all pass (43 passed) when `SentenceTransformer` is replaced by a deterministic stub (hf_stub.py), which shows the unavailable model is their only blocker but is NOT a pass of the real model path. Status: ENVIRONMENTALLY BLOCKED, real-model run NOT EXECUTED. The "170 tests" figure is not reproduced (selection unknown). Earlier targeted runs: all passed except the HF-blocked files above. No baseline from the original author was supplied for comparison.

## 7. Outstanding
- Owner/inputs: supply brief, decision pack, ledger exports with hashes, original probe outputs, §22 evidence; then cross-document (D6), criterion 12/23 and the 26-criteria work.
- Definitions required before DEBT-015 items 1, 5 and 11 can be scored (section 4).
- Owner decisions, not made here: hard-deadline authority (F-16), whether a deadlined or cancelled run should be resumable, what an HTTP `success` flag must reflect, whether NamespaceBackend wiring is expected.
- Environment: a host that reaches huggingface.co (or has the model cached) to run the planner, handle() and HTTP paths for real and re-run the 43; a real uvicorn disconnect test; cancellation after several completed nodes; EventStream.append event_id check; branch review of core/verification.
- The GitHub token in the user's preferences was not used; treat as exposed and rotate.
