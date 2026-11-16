# OCBrain Q4-b review note r5: trace-ID discrepancy and the production path

**INTERIM. Evidence only, read-only, no remediation proposed, no PASS, mission not closed.** Baseline `main` = `2491ae469edd` (re-verified at the end). Revisions 1-4 are untouched; this note corrects specific statements in r3 and r4.

## 1. What the discrepancy was
My `handle()`-level probes (rev_probe_d, rev_probe_f, rev_probe_h; r2-r4) built the Orchestrator with the test fixture default `use_k42_frontend=False`. The shipped `config/settings.toml` sets `[runtime] use_k42_frontend = true`, and `main.py` (~398-410) reads it with a default of False only when the key is missing. Production therefore takes the K4.2 branch (`compile_plan` at `orchestrator.py` ~457), which those probes never exercised. Affected statements:
| Earlier statement | Status |
|---|---|
| r3 s6 / r4 s4: `TRACE-KNOWN-1` appears in no persisted event | True only for the flag-off path. CORRECTED below. |
| r4 s4: full K4.2 lineage NOT EXECUTED | Now executed through the repo's own runtime-integration stack (real EventStream, Governance, WorkflowRuntime, Orchestrator; LLM calls and the capability adapter faked exactly as in `tests/test_runtime_integration.py`). Not executed: `main.py`'s real composition and real adapters. |
| r2/r3 rev_probe_d (handle() swallow, HTTP 200 success=True on provider failure) | Flag-off path. Not production behavior. The K4.2 equivalent is in section 2. |
| r3 s6 / r4 s4: no event records the `execution_id` <-> `instance_id` relationship | Too strong; see section 3. |
Not affected (they exercise WorkflowRuntime/ExecutionRuntime/worker/event-store code directly, independent of the flag): F-15 map, F-16 and the topology matrix, K1-K5, kill/resume, PR #81 probes, registry probe I, the five supplied probes.

## 2. Results on the production-flag path (outputs/)
- J1 (in-process, `use_k42_frontend=True`, injected `execution_id`s and ambient trace id `TRACE-KNOWN-1`, 54 events scanned at any depth): `TRACE-KNOWN-1` is persisted in six `cognitive.*` event types (`intent_hypotheses_generated`, `intent_interpreted`, `goal_formed`, `constraints_extracted`, `capabilities_discovered`, `plan_compiled`) and in no `workflow.*`, `worker.*`, `execution.*`, `system.checkpoint` or `orchestrator.*` event. `root_operation_id` appears only in `cognitive.plan_compiled`; `operation_id` in `plan_compiled`, `constraints_extracted`, `capabilities_discovered` (a different value per stage); `execution_id` only in `execution.*` events. Two sequential `handle()` calls in one task context reused the same ambient trace id (no reset boundary in-process).
- J2 (REAL uvicorn on 127.0.0.1, one keep-alive client connection; two sequential and two concurrent `POST /query`; the driver never touched the tracer in the server's main context): 4 distinct ambient trace ids for 4 requests, and each id appears in 6 `cognitive.*` events of its own request. So under a real server the ambient trace id is fresh per request in this harness; the HTTP/ContextVar boundary is not where the break is. NOT run: `main.py` startup, which could create the ContextVar value in a parent context before serving; scheduler and CLI callers.
- J1b (J1 with the adapter given an event stream, as `main.py` ~289 does): `adapter.invoked` events carry a `trace_id` that is a fresh uuid per CapabilityRequest and differs from the ambient id used by the cognitive events (no match); the event carries no workflow, instance, execution or operation id. The capability events therefore have no persisted join key to the rest of the lineage (ordering only), and `CapabilityResult` returns no identity. This matches DEBT-030/FZ-06, now observed in events and not only in source.
- J2 failure reporting (K4.2 path, real HTTP, failing adapter): HTTP 200, `success: true`, `error: null`, empty answer, adapter called once. Consistent with the register's FZ-01 (known, not new).

## 3. Corrected identity relationships (K4.2 path; joins observed, not propagation)
- `workflow_id` joins `cognitive.plan_compiled` (carrying `trace_id`, `operation_id`, `root_operation_id`) to `workflow.*`, `worker.*`, `system.checkpoint` (2/2 workflows matched); `instance_id` appears only in `workflow.*` and the checkpoint.
- `request_id`/`task_id` joins `execution.completed` (which carries `execution_id`) to `worker.*` (6/6) and to the checkpoint (the checkpoint held one request id per workflow, 2/2 matched). So `execution_id` <-> `instance_id` is derivable through `request_id`, but no event carries both and the join depends on what the checkpoint retains. r3/r4 should read "no event carries both; an incidental, partial join exists".
- Break points, as observed: (1) HTTP -> cognitive stages: intact per request. (2) cognitive -> runtime: joinable via `workflow_id`, not propagated (runtime ignores `root_operation_id`; ambient trace id absent from runtime events). (3) runtime -> capability: broken (fresh capability trace id, orphan adapter events). (4) `execution_id` -> `instance_id`: partial join only. No new identifiers or one-uuid design are proposed. The evidence argues against treating the HTTP or ContextVar boundary as the fix point.

## 4. The four gap areas, mapped to evidence (separate gaps, not one defect)
| Area | Evidence |
|---|---|
| Execution identity | section 3; DEBT-030/FZ-06 counted once; `execution_id` reuse (r4 D1/D2) |
| State reconstruction | K1-K5 (stale/missing checkpoints, repeated work), kill/resume (killed attempt unrecorded), no production caller of `resume()`, D4 (inspection after restart shows `pending`) |
| Event delivery | F-15 (asymmetric emit policy), restore-replayed `execution.node.completed`, in-memory SSE queues without replay |
| Outcome reporting | F-16 and the topology matrix, K2 (success without durable state), F-15 false failure, J2 (HTTP success on adapter failure, FZ-01) |

## 5. Boundaries kept
No repository file, branch, PR or register was changed; PR #81 and #105 untouched; no asyncio-cancel test written; the shipped config was only read. Remaining NOT VERIFIED: `main.py` real startup context, real adapters, scheduler/CLI trace behavior, and everything listed as open in r4 section 9. The GitHub token in the user's preferences was not used; treat it as exposed and rotate it.
