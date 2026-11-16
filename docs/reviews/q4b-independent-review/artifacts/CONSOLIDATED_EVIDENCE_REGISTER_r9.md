# OCBrain Q4-b independent review: consolidated evidence register (r9)

**PRODUCTION IDENTITY / Q4-b REVIEW: OPEN, NO PASS.** Evidence consolidation only. It lists what is established, conditional, unverified or withdrawn across r1-r8. It is not an edit of the Q4-b brief, decision pack or ledger (never supplied), makes no owner decision, and grants no remediation or implementation authorization. Session dates 2026-10-31 to 2026-11-02. Repository `1h0lde4/ocbrain-v4.1`, read-only.
Governing principle: a verified event payload is not proof that the system reaches that event under the real failure condition; what the code does, what a test demonstrates, what production exercises and what the evidence proves are kept apart.

## 1. Baselines and path qualifiers
| Evidence | Commit | Notes |
|---|---|---|
| Original author's revalidation | `4a4783c` | not independently reproduced |
| r1, r2 | `16d663a` (PR #97 merge) | |
| r3 | `ed3d141` (PR #104; only `core/model_router.py` changed vs `16d663a`) | |
| r4-r8 and this register | `2491ae469edd6ef1267a14604c4f8f40d698f7ea` (34 commits past `ed3d141`; PRs #93, #106 merged; `core/` diff = `core/cognitive/intent.py`, `planner.py`) | re-verified at the end of the session |
All five supplied probes and probes A2, B, C give normalized-identical output on `16d663a`, `ed3d141` and `2491ae4`, so workflow, worker, runtime and event-store findings carry across.
Qualifiers: production config ships `use_k42_frontend = true`; r2-r4 `handle()`-level probes ran the flag-off path (superseded, section 4); r5 onward ran the flag-on path. In `handle()`-level probes the embedding model is stubbed (huggingface.co unreachable), LLM calls and the capability adapter are faked as in the repo's own runtime-integration fixture, and K3 uses the real `ModelRouterAdapter` over a fake `ModelRouter`.

## 2. Status vocabulary
VERIFIED (reproduced on the stated path); VERIFIED, CONDITIONAL (shape or behavior confirmed under a constructed trigger; natural cause not shown); PARTIALLY VERIFIED; NOT VERIFIED; NOT EXECUTED; ENVIRONMENTALLY BLOCKED; UNRESOLVED, DEFINITION REQUIRED; OWNER DECISION; WITHDRAWN.

## 3. Findings register
| ID | Current statement | Status | Evidence (archive: file) |
|---|---|---|---|
| A1 / F-16 | A hard deadline gives different workflow outcomes by DAG position and worker cooperation: ignoring final node = success with a recorded `node.failed` then `node.completed`; ignoring non-final node = "Workflow cancelled"; polling node = the worker's own failure text. | VERIFIED. Authoritative-surface and status semantics: OWNER DECISION | r4: out_rev_g.json; r2: out_rev_a2.json |
| A2 / F-17 | No preemptive timeout found at worker, runtime, workflow or orchestrator layers (grep). NamespaceBackend enforces a timeout and kills descendants (tests pass) but is referenced by no production code. | PARTIALLY VERIFIED (static grep) / VERIFIED (tests) | r2: ns_tests_system_python.log |
| A3 / F-09 | Asyncio cancel during retry backoff leaves `GraphExecutionWatchdog._run` running on main. PR #81's candidate closes that probe case. | VERIFIED on main; candidate only for #81 | r3: out_pr81_probe_main3.json |
| A4 | Asyncio task cancel is absorbed by the worker and retried; cancelled/deadlined runs resume as plain success or replay a stored failure. Owned by #105; no further cancellation tests were written. | VERIFIED observation (pre-constraint); contract OWNER DECISION | r2: out_rev_c.json |
| B1 / F-15 | Progress-event write failures can raise from `execute()`, mask the real error, turn a successful node into a failed workflow, or leak the watchdog. Emit policy is asymmetric (`ProgressMonitor` propagates; `WorkflowRuntime` and worker emitters swallow). | VERIFIED | r2: out_rev_a2.json |
| B2 | Checkpoint writes are best-effort: failure is swallowed and not visible in event history; all writes failing yields success with no recoverable state; stale checkpoints cause completed nodes to run again (at-least-once). | VERIFIED (deterministic injection K1-K5) | r3: out_rev_k.json |
| B3 / PR #97 | Kill and resume recovers completed work. Detection and accounting of the killed attempt are absent (checkpoint shows `pending`, `attempts=0`; orphan `worker.started`). | Recovery VERIFIED; accountability gap VERIFIED | r2: kill_resume/ |
| B4 | Event history mixes executed completions and restore-replayed `execution.node.completed` events. | VERIFIED | r3: out_rev_k.json |
| B5 | `event_id` is a fresh uuid4, `UNIQUE NOT NULL`, no idempotent append, no `IntegrityError` handling. | PARTIALLY VERIFIED | r4 section 2 |
| B6 | `resume()` has no production caller. | VERIFIED (grep) | r3 section 6 |
| C1 | Registry: a repeated `execution_id` shares and overwrites one graph; unknown-id `GET /executions/{id}` grows `_graphs`/`_queues` about 4.2-4.8 KB per request with no eviction; after restart a completed execution appears as an empty `pending` graph with no event replay. Corroborates FZ-05(a). | VERIFIED | r4: out_rev_i.txt |
| D1 | Cognitive -> workflow lineage joins via `workflow_id` (`plan_compiled`); `root_operation_id` is not carried into run metadata, `ExecutionContext`, events or checkpoints (0 references in `runtime.py`). | VERIFIED (source + probe) | r4/r7: out_rev_f_main_2491ae4.txt |
| D2 | Worker -> capability: `CapabilityExecutorWorker` holds `request_id`, `execution_id`, `instance_id`, `attempt_id` and forwards none; the capability request gets a fresh `trace_id`, so `adapter.invoked` events have no join key. Separate from D1; both under FZ-06/DEBT-030, counted once. | VERIFIED (source + events) | r5: out_rev_j1b_with_adapter_events.json |
| D3 | `interaction_id` is `sha256(query)[:32]` (also `session_id`); identical concurrent queries share it. Existing FZ-06 behavior, not a new defect. | VERIFIED | r7: out_rev_k_probe.json |
| D4 | `/query` always supplies an `execution_id` (so it differs from `instance_id`); the mounted `/brain/v2/query` supplies none, so `execution_id == instance_id`. No event carries both ids on `/query`. `execution.completed` has two schemas by producer (`request_id` vs `execution_id`) and no record carries both. | VERIFIED (ASGI, not a real server) | r6/r7 outputs |
| D5 | Ambient trace id is fresh per request under real uvicorn (4 of 4 requests, my harness, one `httpx` session); in-process sequential calls in one task share it. Non-HTTP callers: voice only (conditional, shipped off); none found for scheduler or CLI. | VERIFIED (HTTP, harness-limited); other callers NOT VERIFIED | r5: out_rev_j2.txt |
| D6 | Exceptional events: `planner_impasse_terminal` carries `trace_id`, `operation_id`, `interaction_id`, `goal_id`; `response_incomplete` carries `interaction_id`, `execution_id`, `constraint_violations`; neither carries `instance_id`. | VERIFIED, CONDITIONAL (payload shape; mocked planner and injected violations). Natural triggers NOT VERIFIED | r8: out_rev_l.txt |
| E1 / FZ-01 | Outcome reporting is four separate observations, not one conclusion: (i) adapter failure: workflow reports `success=False`, but `orchestrator.query_completed` says success and `/query` returns 200, `success: true`, empty answer (real `ModelRouterAdapter` over faked router failures); (ii) hard deadline: false workflow success (A1); (iii) progress-event write failure: false workflow failure (B1); (iv) constraint violations: `response_incomplete` coexists with a success completion (constructed). Adapter-level failure mapping (FZ-02 B2a) works for the tested inputs. FZ-01 remains one existing debt. | (i)-(iii) VERIFIED; (iv) VERIFIED, CONDITIONAL; real `ModelRouter`/provider NOT EXECUTED | r7: out_rev_k_probe.json; r8 |
| F1 | Suite on `2491ae4`: 2139 passed, 43 failed, 1 skipped, 1 xfailed; the failing set is identical on all three baselines and passes under the diagnostic embedding stub (not a real-model pass). #97 and #104 tests pass. | Real-model run ENVIRONMENTALLY BLOCKED | r4: logs/ |
| G1 | DEBT-015 12-item matrix: items 2, 3, 4, 8, 10, 12 absent by grep; items 6, 7, 9 partial (checkpoint persistence, retry/attempt ids, attempt id delivered to workers but unused); items 1, 5, 11 UNRESOLVED, DEFINITION REQUIRED. | PROVISIONAL | r2 section 4, r4 |

## 4. Withdrawn or superseded statements
r1: namespace-test failures "UNCLASSIFIED" (artifact of my venv path); DEBT-015 item 1 "NOT IMPLEMENTED". r2-r4: `handle()`/HTTP and identity probes (flag-off path, not production). r3: FZ-05 described as event-log growth only (it also covers the registry); `TRACE-KNOWN-1` "in no persisted event" (true only flag-off; on the production flag it is in six `cognitive.*` event types). r5: `execution_id` -> `request_id` -> `instance_id` join; "one keep-alive connection"; scheduler/CLI callers. r6: "interaction_id has no persisted join" (exceptional events join it); "only two files call `handle()`"; Brain API mount "not determined". r7's first K3 run was invalid (fake adapter not replaced) and is kept only as a labelled file.

## 5. NOT EXECUTED or NOT VERIFIED
Voice listener (shipped off); real `ModelRouter`, provider and network; `main.py` real composition and startup context; real uvicorn client disconnect; natural triggers for both exceptional events; real LLM-driven K4.2 stages; cancellation rows reserved to #105; event-store retention (FZ-05(b)); full K4.2 lineage through `main.py`. Not assessable because the inputs were never supplied: D6 consistency, criteria 12 and 23, section 22 preservation, the 26-criteria matrix.

## 6. Active and candidate work (read-only observations)
PR #81 (open, head `647b63e734792b8375c0f96593407ee651af5840`, 13 ahead / 96 behind, conflict only in `KNOWN_ISSUES.md`, lock covers `resume()` on one runtime object); #105 reserved to another session, unduplicated; `follow-up/fz02-b2d-…` and `wip/fz02-b2c-…` unreviewed. No register or documentation file was changed.

## 7. Owner decisions, not made here
Hard-deadline authority and status semantics; the #105 cancellation contract; whether cancelled or deadlined runs are resumable; whether checkpoint failure must be visible or fail the run; the `execution_id` uniqueness contract; what inspection must show after restart; whether identical concurrent queries must have distinct interaction identities; what a successful completion event must require; definitions for DEBT-015 items 1, 5, 11; whether NamespaceBackend is expected to be wired.

## 8. Integrity
Archive hashes are in ARCHIVE_MANIFEST.tsv (full SHA-256 for every delivered file). At the end of this session `git ls-remote` shows `main` = `2491ae469edd6ef1267a14604c4f8f40d698f7ea` and `refs/pull/81/head` = `647b63e734792b8375c0f96593407ee651af5840`; my scratch clone has no pushes. The GitHub token found in the user's preferences was never used or stored; revoke it through its issuing provider, replace it with a minimally scoped credential, audit its recent use, and keep it out of reports, commits and evidence archives.
