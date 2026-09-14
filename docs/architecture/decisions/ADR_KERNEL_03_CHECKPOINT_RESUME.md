# ADR-KERNEL-03: Checkpoint/Resume (DEBT-003)

**Status:** Accepted
**Date:** September 5, 2026
**Context:** `KNOWN_ISSUES.md` DEBT-003 — `WorkflowRuntime` tracked node state in local dicts, never persisted; `EventStream.create_checkpoint()`/`get_checkpoint()` existed but were never called. Reclassified Aug 29, 2026 as a Kernel v1.0 completion item in its own right (`docs/studies/OCBRAIN_KERNEL_COMPLETION_STUDY.md` §8, §12, §21 Step 3): "Kernel v1.0 itself cannot honestly claim durability... while [it stands]." Its prerequisite — stable identity across an execution (`root_operation_id`, `attempt_id`) — was resolved by ADR-KERNEL-01 (Aug 29). Per Moncif, this session follows the existing roadmap: this is the second of two items (after DEBT-016) addressed before the Kernel freeze audit; Verification/Critic/Evidence integration remains post-freeze/post-C-MoE as already planned.

---

## What was actually found (not assumed)

- `create_checkpoint(name, payload)` / `get_checkpoint(name)` already existed on `EventStream`, backed by `SQLiteEventStore` (real WAL-mode SQLite, not in-memory) with "latest by name" retrieval (`ORDER BY sequence DESC LIMIT 1`) — a complete, working, unused primitive.
- `docs/archive/research/OCBRAIN_FUTURE_ARCHITECTURE.md` (also mirrored at repo root, byte-identical) had already analyzed this exact problem and recommended, in its own words, exactly what this ADR does: *"Implement checkpoint/resume on top of existing EventStream WAL first (simpler, 80% of value). Full Temporal integration only at Phase 4.8+."* This ADR does not adopt a Temporal-style durable-execution engine; it uses the existing WAL primitive directly, per that research's own recommendation.
- `ADR-KERNEL-01` explicitly left an open question for this exact moment: *"nodes are not currently persisted, transported, or indexed independently of their parent WorkflowDefinition — no checkpoint/resume exists yet (DEBT-003)... Revisit this specific decision if/when DEBT-003 changes that."* Resolved below (see "Node-level identity").
- `WorkflowRuntime._execute_from`'s recursion has a `state.status != PENDING -> return cached result` short-circuit, added for diamond-shaped DAGs (two branches merging back into one downstream node): the second path to reach that node must not re-run it or re-walk its successors, since the first path already did. This same check, unmodified, would have silently broken resume — see "A real bug this ADR's own tests found" below.

## Decision

### Checkpoint content and timing

`WorkflowRuntime._save_checkpoint()` writes after every node boundary (`_execute_from`, both the success and failure/error-branch paths), keyed by `f"workflow:{instance_id}"` — one evolving checkpoint per execution instance (not per step; "latest by name" retrieval makes a distinct name per step unnecessary). Payload: `workflow_id`, `instance_id`, `saved_at`, and every node's serialized `WorkflowNodeState` (via new `WorkflowNodeState.to_dict()`/`from_dict()`). Best-effort: a checkpoint-write failure is logged and swallowed, never allowed to fail otherwise-correct work in progress — mirrors `_emit_event`'s existing failure-containment convention in this same class, not a new one.

`NodeStatus` is a plain `Enum` (unlike `watchdog_decision.WatchdogVerdict`/`CancelReason`, which are `str, Enum` by design precisely so they cross the JSON boundary safely) — `to_dict()`/`from_dict()` extract `.value` explicitly rather than relying on `SQLiteEventStore`'s `json.dumps(..., default=str)` fallback, which would otherwise silently produce the unparseable `"NodeStatus.PENDING"` instead of `"pending"`.

### `WorkflowRuntime.resume(definition, instance_id, ...)`

Loads the latest checkpoint for `instance_id`; fails cleanly (returns `WorkflowResult(success=False, ...)`, never raises) if none exists or its `workflow_id` doesn't match `definition`. Reconstructs `node_states`/`node_results`, then re-enters the same `_run()`/`_execute_from()` engine `execute()` uses — no separate "resume traversal" algorithm exists; `execute()` and `resume()` differ only in how `node_states` starts out. `execute()` was refactored into a thin wrapper generating fresh state, plus a shared `_run()` both callers use, rather than duplicating the validate/graph/watchdog/aggregate logic a second time (the same "one shared engine, not two parallel copies" lesson as DEBT-016).

### Safety: a `RUNNING` (or `CANCELLED`) node is reset to `PENDING`, never resumed in place

Whether a node whose last known status was `RUNNING` at checkpoint time actually finished before the crash is unknowable from here. This project's Verification principle applies directly and was treated as binding, not just an analogy: a status of `RUNNING` is not evidence of completion. `resume()` resets any such node to `PENDING`, `result=None`, so it is re-executed from scratch rather than silently assumed successful or silently left stuck.

### Budget: always fresh on resume, never restored from the checkpoint

Preserving "remaining time across an unknown period of downtime" is ambiguous — too strict if the process was down 2 seconds, too lenient if it was down 2 hours. `resume()` always calls `default_budget_for()` unless the caller supplies their own `metadata["execution_budget"]`, identically to `execute()`. Simpler than trying to model elapsed-downtime accounting, and no part of DEBT-003's own problem statement ("workflows cannot survive process restart") requires it.

### Node-level identity: ADR-KERNEL-01's deferred question, now answered

Checkpointed node state is nested *inside* one checkpoint keyed by the whole execution's `instance_id` — never independently addressable or queryable by node identity alone; you cannot look up "node X's checkpoint," only "instance Y's checkpoint," and then find node X's entry within it. This does not cross the threshold ADR-KERNEL-01's own I7 guidance set ("a node-level reference may be justified only if nodes are independently persisted, transported, indexed, or emitted"). **Conclusion: `WorkflowNode` still does not need its own `root_operation_id`. ADR-KERNEL-01's decision stands, now confirmed rather than merely provisional.**

## A real bug this ADR's own tests found

`_execute_from`'s `state.status != PENDING -> return cached result` short-circuit conflates two different questions: "has *this traversal* already visited this node" (true for a diamond-merge revisit — correctly skip, since the first path already walked its successors) and "is this node already done" (true for a checkpoint-restored node — but this traversal has never visited it before, so its successors have never been reached). The original code could only ask the second question, which happened to also correctly answer the first only because, in every pre-resume caller, a node could never be marked done without this same traversal having already been the one to do it.

First draft of `resume()`, tested against a 2-node linear workflow with node `a` pre-marked `COMPLETED`: node `b` was never invoked at all — `test_resume_skips_completed_node_and_only_reruns_pending` failed with `CountingNodeWorker.invocations == []`, and the real-SQLite end-to-end test (`test_resume_survives_a_real_process_restart`) failed the same way. Fixed by adding a per-traversal `visited: set` (default fresh per `_run()`/`_execute_from()` call from `resume()`/`execute()`, threaded through every recursive call including the error-branch redirect): a node's *first* visit this traversal always continues into its successors, whether it needed fresh execution or was already done; only a *second* visit within the same traversal short-circuits. The successor-walking loop was extracted into `_continue_to_successors()` so both exit paths (freshly completed; already-done-but-first-visit) share one implementation rather than two copies that could drift.

## What was explicitly not done

- No adoption of DEBT-015's broader `Operation`/`ExecutionAttempt`/`ExecutionSnapshot`/`RecoveryDecision` architecture. This resolves DEBT-015 sub-item (6) specifically ("node-boundary checkpoint persistence via `EventStream` replay") using the existing primitive directly; the rest of DEBT-015 remains correctly deferred, proposed-only, requiring its own ADR.
- No automatic discovery/resume-on-startup orchestration (scanning for interrupted workflows when a process boots and resuming them unprompted). `resume()` is a capability a caller invokes with a known `instance_id`; deciding *when* and *which* interrupted executions get resumed automatically is a separate, larger design question (retry policy, staleness limits, who's authorized to trigger it) outside DEBT-003's stated scope ("Long-running workflows cannot survive process restart" — solved by making resume possible and correct, not by making it automatic).
- `execution_detail` (K4.4's `ExecutionOutcome`) is not restored on a resumed node's cached `WorkerResult` — see `_worker_result_to_dict`'s docstring. `success`/`output`/`error`/`artifacts`/`events_emitted`/`duration_ms`/`metadata` round-trip faithfully (proven by real `json.dumps`/`json.loads`, not just Python-object equality); the original attempt's detailed failure classification does not.
- Side-effect idempotency (re-running a node that already sent an email, wrote a file, etc. before the crash) is not addressed — this is DEBT-015 sub-item (7), explicitly deferred, proposed-only future architecture. DEBT-003 solves durability of *state*; idempotency of *effects* is a different, larger problem this ADR does not claim to solve.
- No checkpoint pruning/retention policy. Older checkpoint events for a given name are never read again (`get_checkpoint` only ever reads the latest) but remain in the SQLite WAL indefinitely — the same accumulation model every other event type in this store already has, per Law 2 (event sourcing, immutable, replayable). Not a new class of resource concern introduced by this change; not addressed here.

## Evidence

`tests/test_workflow_runtime.py`: `TestWorkflowNodeStateSerialization` (3 tests — round-trip, real-JSON round-trip, `None`-result round-trip) and `TestWorkflowRuntimeCheckpointResume` (6 tests — checkpoint written after each node; resume with no checkpoint fails cleanly; resume rejects a mismatched `workflow_id`; resume skips an already-completed node while still executing its pending successor, proven via an invocation counter, not just the final result; resume resets and re-executes a `RUNNING` node; and the real end-to-end proof — two separate `WorkflowRuntime`/`EventStream`/`SQLiteEventStore` instances sharing only an on-disk file, no shared Python objects, genuinely proving cross-process-like durability). All existing tests in this file (32 total after these additions) and in `test_execution_inspection.py`/`test_runtime_integration.py` pass unchanged. Full suite: 1,365 passed / 39 failed (34 pre-existing `huggingface.co`-unreachable, 5 pre-existing intentionally-red security-regression tests — unchanged from this session's DEBT-016 baseline). Nine new tests, zero regressions.

## Consequences

- DEBT-003 (`KNOWN_ISSUES.md`) is resolved by this ADR.
- `WorkflowRuntime.execute()`'s public signature and behavior are unchanged; existing callers are unaffected. `resume()` is new. `_execute_from()` gained an additional optional `visited` parameter (internal method, no external callers — confirmed by trace).
- Any future workflow-graph feature that reasons about "has this node been handled" must use the same `visited`-vs-`status` distinction this ADR's bug fix establishes; conflating them silently reintroduces the exact bug found here.
- DEBT-016 (Watchdog reconciliation, `ADR-KERNEL-02`) is unaffected — no changes to `watchdog.py`, `watchdog_decision.py`, `execution_watchdog.py`, `progress.py`, or `progress_monitor.py`.
- Verification/Critic/Evidence integration remains post-freeze/post-C-MoE per the existing roadmap. The Kernel freeze audit is the next planned step now that both DEBT-016 and DEBT-003 are resolved.
