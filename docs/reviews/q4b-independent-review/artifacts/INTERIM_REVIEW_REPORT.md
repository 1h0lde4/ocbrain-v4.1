# OCBrain Q4-b independent adversarial review: INTERIM evidence report

**Status: INTERIM. This is not a validation and does not close the mission.** Reviewer session date: 2026-10-31.
Labels used: VERIFIED / PARTIALLY VERIFIED / NOT VERIFIED / CONTRADICTED / ENVIRONMENTALLY BLOCKED / NOT EXECUTED.
Line numbers marked "~" come from an earlier read of the source and must be re-verified before citing.

## 1. Provenance
- Repository: github.com/1h0lde4/ocbrain-v4.1 (public; cloned and fetched without credentials). `origin/main` = `16d663ac8449965f774033da46d5063506a772a7`; `4a4783c47ac37971a7d51ab3d7ab6fc904a37106` is an ancestor. Checked out detached in a scratch clone; probes and tests ran in `git archive 16d663a` snapshots. No repo files, branches or commits were created or changed.
- `4a4783c..16d663a` = 5 commits (e721960, 1ec5451, 7bb0ce2, c228f16, merge 16d663a). `git diff 4a4783c 16d663a -- core` = 0 lines. Changed files: KNOWN_ISSUES.md, tests/_crash_restart_child.py (new), tests/test_workflow_crash_restart_subprocess.py (new), tests/test_workflow_runtime.py. Previous runtime evidence was produced on 4a4783c; the claim "ten of twelve audited source files byte-identical" was NOT checked (the twelve files are unknown to me).
- Supplied: files.zip SHA-256 `73c4e52440d018d86194e9ccb0db7feb72224263caf5754a5045b30c750d2222` (8,443 bytes) containing:
  - probe_main.py a761827d450591ddf2d0589b0a65428c5c1703a52f1b1ec4b19b66bfdd87e395 (8419 B)
  - probe_main2.py dc69e68f7818a77b09611fdf6c5a2cfd3c58805d6836fdd18efa6a016535110e (3343 B)
  - probe_main3.py e1aee93306461167996380d5dd783e525fee780bd6897ee3511d134c6ad1154c (2279 B)
  - probe_main4.py 5ef869ee74f6749e0a65b937b799582a2750e01513e116eb9ee7c0e51a9f23ed (4668 B)
  - probe_main5.py 403f6c37853fe8db33a128d22a8f56faaf2ce96511c7016f862bb60ebe522a11 (1676 B)
  - README.md fc5ba8aeb31db4a4983600a32233a64c3755ec5c7249b4c8c9e536e1916d5681 (1309 B)
- NOT supplied (omissions recorded, nothing substituted): Q4-b brief, decision pack, ledger (MD/DOCX/PDF, hashes, revision labels/counters); original probe outputs; revision-1 preservation evidence. Consequently NOT ASSESSED: D6 consistency, criterion 23, the 26-criteria matrix, §22, and any statement about the wording of F-01/F-14/F-15/F-16/F-17 in those documents.
- Environment: Python 3.12.3; venv outside the repo; torch 2.15.0+cu132, sentence-transformers 3.4.1, chromadb 0.5.3 (chroma-hnswlib built from source), fastapi 0.162.0, pytest 9.2.0, pytest-asyncio 1.4.1; `pip check` clean; full freeze in env/env_freeze.txt. requirements.txt was not modified. Install was staged (requirements.txt minus sentence-transformers; then each CUDA wheel and torch with `--no-deps`; then sentence-transformers) because single-transaction installs exceeded free disk and background processes are killed between calls. Versions therefore may differ from a single-pass resolver run.

## 2. Executive disposition (interim)
Of the items I could examine, the original audit's technical claims about F-15, F-16, F-17 (core claim), F-01 and F-14 are SUPPORTED WITH QUALIFICATIONS (below). Several are understated. Large parts of the mission could not be assessed because inputs are missing, and three runtime groups are not executed. Recommendation: none issued; the mission is not closed.

## 3. Findings register
| ID | Independent conclusion | Evidence |
|---|---|---|
| F-15 | Both reported outcomes reproduce on 16d663a (probe_main4 P8). Additional outcomes exist: see 3a. | out_probe_main4.json; out_rev_a2.json |
| F-16 | Reproduces (P7: node a success=True, workflow "Workflow cancelled", last checkpoint a=completed, b=pending). Stronger consequence confirmed: when the non-polling node is the LAST node, the workflow returns success=True with error "" although the hard deadline fired and the token is cancelled. | out_probe_main4.json; out_rev_a2.json `last_node_deadline` |
| F-17 | Core claim supported by grep: no wait_for/timeout in worker, runtime, workflow or orchestrator paths. Enumeration incomplete: NamespaceBackend (core/sandbox/backends/namespace_backend.py:251) enforces `proc.communicate(timeout=policy.timeout_sec)` with process-group kill, not named as a preemptive site. I/O client timeouts also exist (model_router.py:302, classifier.py:97, network.py, web/fetcher.py). Namespace timeout NOT exercised at runtime (see 6). Wiring of the backend into production NOT established. | source grep |
| F-01 (amended) | Field exists: `WorkerResult.execution_detail: Optional[ExecutionOutcome] = None` (core/workers/base.py ~138); FailureType has exactly 9 members. `AbstractCognitiveWorker.execute()` sets it on no path; probe_main5 P9 reproduces null on returned-failure, raised, unknown-worker and asyncio-cancel paths. I found no production assignment to `WorkerResult.execution_detail`; the only ExecutionOutcome producer is model_router (on RouteResult, a different object). "Some failure paths leave it None" therefore understates: at WorkerResult level no production path populates it. Wording of the amendment not assessable (brief missing). | out_probe_main5.json; grep |
| F-14 | VERIFIED at layout level: `core/verification` does not exist on main 16d663a (`git ls-tree` = 0 entries); it exists on origin/feature/verification-critic-evidence-phase-c (e.g. core/verification/absence.py, assumption.py). Import searches on main were therefore vacuous. Branch contents not otherwise reviewed. | git ls-tree |
| P5b / F-08 | Probe filter artifact suspected: P5b counts events with `payload_workflow_id=wid`, but WorkflowRuntime's `execution.failed` payload has no workflow_id (keys: execution_id, node_id, status, summary). Unfiltered capture (rev_probe_b) shows a swallowed asyncio cancel emits worker.cancelled, execution.completed (success false), execution.node.failed, execution.failed and workflow.completed(success false). Any claim that cancellation emits no workflow-level terminal event is NOT supported. Real gap: no cancelled status or event exists above worker level; cancellation is reported as failure "Worker cancelled". | out_rev_b.json |
| F-09 | Reproduces: asyncio cancel during retry backoff raises CancelledError, leaves `GraphExecutionWatchdog._run` running, emits no workflow.completed/failed. | out_probe_main3.json |

### 3a. F-15 event-store failure map (single append failed; one-node workflow; out_rev_a2.json)
| Failed call | Outcome |
|---|---|
| 1st ProgressMonitor append (root RUNNING) | `execute()` raises OSError before any node runs (progress.py:34 -> :57); no checkpoint. A single failure suffices; "fails everywhere" is not required. |
| node RUNNING status | masked error "Unexpected workflow error: event store unavailable"; node never executed; no checkpoint. |
| `execution.node.completed` (node succeeded) | node_results x=True but workflow success=False with the masked message; no checkpoint. |
| `execution.node.failed` (node failed) | real error "boom" replaced by the masked message (node_results keeps boom); no checkpoint. |
| root final status (after all work) | `execute()` raises OSError AFTER the node ran and the checkpoint was saved; `GraphExecutionWatchdog._run` leaked (watchdog.stop not reached). |
| worker.*, workflow.started, execution.completed/failed (WorkflowRuntime), workflow.completed | swallowed; outcome unchanged. |
Cause: ProgressMonitor._emit (core/runtime/progress.py ~55-73) does not catch; WorkflowRuntime._emit_event and the worker `_emit_event` do. `_run`'s docstring says it never raises. Original probe's `raised_at` was empty here because it filters tracebacks on the author's directory name "main-new".

## 4. DEBT-015 matrix (PROVISIONAL: grep of core/ interface/ main.py plus the runs in this report; tests per item not examined)
| # | Requirement | Status | Evidence / limits |
|---|---|---|---|
| 1 | Stable operation identity end to end | NOT IMPLEMENTED (PARTIALLY VERIFIED) | attempt_id = fresh uuid4 per attempt (runtime.py:863); no request-id handling found in interface/api.py; `QueryRequest` fields not read |
| 2 | ExecutionAttempt first-class record | NOT IMPLEMENTED (VERIFIED by grep) | 0 hits; only `attempts`/`attempt_id` fields on WorkflowNodeState (runtime.py ~54-98) |
| 3 | ExecutionSnapshot | NOT IMPLEMENTED (VERIFIED by grep) | 0 hits; other names not searched |
| 4 | Extended FailureType/FailureClass | NOT IMPLEMENTED (VERIFIED) | `FailureClass` 0 hits; FailureType has 9 members, none of the named additions |
| 5 | RecoveryDecision layer | NOT IMPLEMENTED (VERIFIED by grep); AMBIGUOUS | 0 hits; `watchdog_decision.decide()` is a stall/extend/cancel core that its own docstring says is not a recovery attempt. Whether it satisfies a "thin RecoveryDecision layer" is an owner question |
| 6 | Node-boundary checkpoint persistence | IMPLEMENTED; PARTIALLY VERIFIED | Real hard kill: checkpoint written at a's boundary survived and drove a fresh-process resume (kill_resume/). Limits: never records RUNNING or an interrupted attempt; execution_detail not serialized; checkpoint skipped when ProgressMonitor emission fails (3a) |
| 7 | Retry/idempotency semantics | PARTIALLY VERIFIED | fresh attempt_id per attempt confirmed (P3, runtime.py:863); resume re-executes interrupted node confirmed in a real kill. NOT CHECKED: that EventStream.append accepts no caller event_id; UNIQUE event_id behavior |
| 8 | Stale-attempt rejection | NOT IMPLEMENTED (VERIFIED by grep) | no stale/supersede logic in runtime paths |
| 9 | Worker-level integration | PLUMBING ONLY | attempt_id reaches workers via context.metadata (runtime.py ~881); no production worker references it |
| 10 | Capability-level integration | NOT IMPLEMENTED (PARTIALLY VERIFIED) | no idempotency/attempt/operation-id hits under core/capabilities; CapabilityRequest fields not read |
| 11 | Richer execution inspection UI | AMBIGUOUS / NOT ASSESSED | endpoints exist (api.py:212, :226; tests/test_execution_inspection.py 6 passed); "beyond what's merged today" has no defined baseline. Owner decision |
| 12 | Durable cross-attempt history | NOT IMPLEMENTED (PARTIALLY VERIFIED) | event log is durable, but attempts cannot be correlated to events (probe_main2 P3b) and the checkpoint keeps only the latest attempt_id/count (kill_resume: b shows attempts=1 after two executions) |

## 5. Real-process kill and resume (new test in 16d663a)
- `tests/test_workflow_crash_restart_subprocess.py` + `tests/_crash_restart_child.py`: node b calls `os._exit(137)` itself (self-termination at a fixed point, not an external SIGKILL and not a kill during a checkpoint write). Test passes on 16d663a (36 passed together with test_workflow_runtime.py).
- ESTABLISHED by the test: process termination (exit 137); a checkpoint from a's boundary survives; a fresh process resumes from disk; a is not re-run; b starts twice and completes once; c runs once; final success with all outputs. Its "starts twice" evidence comes from the test's own side-channel JSONL log, not from system state.
- NOT established, and empirically contradicted as a system capability (my re-run, kill_resume/):
  - Detection: after the kill the checkpoint holds b = pending, attempts 0, attempt_id "". It is indistinguishable from a never-started node. Resume's RUNNING reset cannot be reached by a real crash because RUNNING is never persisted (checkpoints are saved only after a node completes or fails).
  - Recording: the append-only log keeps `execution.node.status b running` and `worker.started` (task 3f7d3cd3...) with no terminal event, and still has none after resume. `workflow.resumed` has an empty payload. Final checkpoint: b completed, attempts=1. No component reads or reports the orphan.
  - Result: resume returns success=True with no indication that an attempt was interrupted.
  - Execution identity: the instance id is recovered from the checkpoint name and is consistent; this is the test's mechanism, not a detection feature.

## 6. Runtime gaps
| Group | Status |
|---|---|
| handle() and HTTP under cancellation | NOT EXECUTED. Source: orchestrator.handle() (core/orchestrator.py:188) contains no cancellation_token, CancelledError or wait_for; interface/api.py `/query` (:161) has no disconnect or cancellation handling (grep). PlannerWorker pipeline tests need huggingface.co (all-MiniLM-L6-v2), unreachable here (NameResolutionError): ENVIRONMENTALLY BLOCKED. |
| resume() after a cancelled/deadlined run | NOT EXECUTED. Source/probe inference only: cancelled runs leave later nodes PENDING in the checkpoint, so they look like crashes. |
| Checkpoint after asyncio cancellation | NOT EXECUTED beyond probes (P5/P5b/P6): swallowed cancel yields a failed result; cancel in backoff leaks the watchdog and saves no cancellation state. |
| Process kill and recovery | EXECUTED (section 5). |

Tests run on 16d663a (snapshot):
- PASSED: test_workflow_crash_restart_subprocess + test_workflow_runtime 36; test_execution_runtime 37; test_execution_watchdog 13; test_progress_monitor 12; test_orchestrator_recovery 7; test_runtime_limits 3; test_scheduler_failure_containment 35; test_fz02_provider_failure 15; test_fz02_stalled_deadline_failure 8; test_execution_budget 16; test_execution_inspection 6; test_debt_020_false_completion 37; test_runtime_integration 15; test_evaluator_worker 26; test_reflection_worker 22; test_supervisor_worker 29.
- test_workflow_failure_disclosure: 7 passed, 1 failed (`test_a_successful_workflow_run_is_unchanged`, 74 s): ENVIRONMENTALLY BLOCKED, huggingface.co unreachable.
- test_planner_worker: did not complete (>90 s); HF MaxRetryError/NameResolutionError seen: ENVIRONMENTALLY BLOCKED, not counted as passed.
- tests/core/sandbox/test_namespace_backend.py::test_network_egress_denied_by_default FAILED here (-x run); cause NOT investigated; likely this sandbox lacks namespace/cgroup capability. UNCLASSIFIED.
- Full suite NOT completed (>280 s; reached ~28% with 1 F and 1 x unattributed). The "170 tests" figure is NOT reproduced (the 170-test selection is unknown to me).
- Probes: all five run on 16d663a; their outputs agree with the original reported results where I could compare (no original outputs supplied).

## 7. Outstanding for the owner or the next session
- Supply the brief, decision pack, ledger exports and hashes, probe outputs and §22 evidence; then do the cross-document, D6, criterion 12/23 and 26-criteria work.
- Criterion 12 (§21): NOT ASSESSED; no rule or policy introduced.
- Owner decisions that stay with the owner: whether `watchdog_decision` counts toward DEBT-015 (5); the baseline for item 11; whether the extra F-15 outcomes, the last-node F-16 consequence and the F-01 understatement change finding severity.
- Re-run on a host that can reach huggingface.co (or with the embedding model pre-cached) to execute the handle()/HTTP and planner paths; chunk the full suite.
- The GitHub token present in the user's preferences was not used; treat as exposed and rotate.
