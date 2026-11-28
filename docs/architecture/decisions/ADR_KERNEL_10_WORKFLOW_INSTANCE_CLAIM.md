# ADR-KERNEL-10 — Workflow instance single-flight claim (DEBT-028)

**Status:** PROPOSED. Nothing here is ACCEPTED. Acceptance is the owner's call; the open decisions are in §9.
**Date:** Nov 2026.
**Origin:** the owner's instruction of Nov 21, 2026 that PR #81 (closed, unmerged, Nov 20) be **redone anew**, read together with
the Oct 28, 2026 disposition recorded on DEBT-028: *deferred; the guard must coordinate at the actual deployment boundary; no code change is
warranted before the deployment model is decided*. This ADR proposes that decision and a fresh implementation; it does not close DEBT-028.
**Related:** DEBT-028 (stays OPEN), DEBT-003 (checkpoint/resume), DEBT-015 sub-item (7) (side-effect idempotency, explicitly out of scope),
PR #81 (closed), LAW 2 "Event Sourcing Over Hidden State", LAW 4 "Determinism Over Magic".

Evidence tags: `[FACT]` verified against the repository at `main` `ef1351f`; `[PROPOSED]` a decision awaiting the owner; `[INFER]` reasoning, not observation.

## 1. The requirement (the acceptance criteria)

From the DEBT-028 row and the Oct 28 independent review `[FACT]`:

- **R1** Two concurrent `execute()`/`resume()` calls on one `instance_id` must not both run it.
- **R2** The guard must coordinate "at the actual deployment boundary": the deployment model decides whether an in-process guard suffices or a durable cross-process claim is required.
- **R3** The guard must live in the same change as the first production `resume()` entry point, or earlier.
- **R4** Idempotency of external side effects (DEBT-015 sub-item (7)) stays out of scope.

## 2. What the code does today `[FACT]`

- Exactly one production `WorkflowRuntime` is constructed (`main.py`, inside one `uvicorn.Server`); there is no `multiprocessing`, process pool or `--workers`.
- There is **no production caller of `resume()`**, and `execute()` mints a fresh `uuid4()` per call. So the race is real in shape and currently unreachable, as the register says.
- `Orchestrator.handle()` runs every query through a one-node planner workflow via `execute()`: this is the hot path, so any guard must be nearly free by default.
- Checkpoints live in the SQLite/WAL `EventStream`, which any process pointed at the same data directory can open. That, not the current process count, is the cross-process surface.
- `resume()` reads the checkpoint **before** calling `_run`. A guard that wraps only `_run` leaves the read-then-run window open.

## 3. Decision `[PROPOSED]`

A **reject-fast single-flight claim** on `instance_id`, taken by both `execute()` and `resume()`:

- A second claimant gets `WorkflowResult(success=False)` with `metadata["claim_failure"] == "instance_busy"` and a `workflow.instance_claim_rejected` event. It never waits and the runtime never raises, consistent with the rest of `WorkflowRuntime`.
- The claim is taken at the very start of `resume()`, before the checkpoint is read, and released on every exit path including exceptions and task cancellation.
- Its **scope is an explicit deployment setting**, not a guess about the deployment:

| `runtime.workflow_claim_scope` | Exclusivity | Cost | Correct when |
|---|---|---|---|
| `process` (default) | in-process registry | zero I/O | exactly one process owns the checkpoint store (today) |
| `host` | in-process registry **plus** a durable lease in a shared SQLite file | two small writes per run and a heartbeat | several processes on one host share a data directory |

An unknown value stops startup; there is no silent fallback.

## 4. Design details `[PROPOSED]`

1. **In-process layer.** A dict of in-flight ids guarded by a `threading.Lock` (the check-and-add is atomic and loop-independent). Entries exist only while a run is in flight and are removed on every exit path, so memory is bounded by concurrency.
2. **Durable layer (`host` only).** One table, `workflow_instance_claims(instance_id PRIMARY KEY, holder_id, host, pid, operation, acquired_at, lease_expires_at)`. Acquire is a single `BEGIN IMMEDIATE` transaction that purges expired rows, then inserts or reports the live holder, so two processes cannot both win. Every SQLite call runs in a worker thread (`asyncio.to_thread`) with its own connection: nothing blocks the event loop.
3. **Lease, not liveness probing.** A holder renews its lease every `ttl/3` while it runs; a crashed holder's lease simply expires. No PID probing: on Windows `os.kill(pid, 0)` terminates the process.
4. **Lost claim.** If a renewal reports the claim gone (or errors for a full TTL), the guard calls `on_lost`; the runtime cancels the workflow through its `CancellationToken` and emits `workflow.instance_claim_lost`, so a lost lease cannot silently become a duplicate run. The runtime supplies a token itself when none is given, in `host` scope only.
5. **Fail closed.** In `host` scope, if exclusivity cannot be established or stored, the run is refused (`claim_failure == "claim_unavailable"`). An operator who chose `host` asked for exclusivity; running without it would defeat that choice.
6. **Governance.** No new authority boundary or autonomous side effect: the guard can only refuse. It is runtime-internal and does not call the GovernanceKernel.
7. **Observability.** Refusals and lost claims are events. Routine acquire/release are not: they are already represented by the workflow start/complete events carrying the same `instance_id`.
8. **Diff discipline.** `execute()` wraps its single `_run` call; `resume()` keeps its original body verbatim as `_resume_from_checkpoint` behind a thin guarded wrapper. No block is re-indented.

## 5. Alternatives considered

- **PR #81's per-instance, reference-counted `asyncio.Lock` inside `WorkflowRuntime`** (closed). In-process only, so it cannot satisfy R2; it waits (a queue per id); it re-indented large blocks (+676/−201 across 4 files, including unrelated `watchdog` changes). Rejected; its tests' intent is kept.
- **Waiting/serialising instead of rejecting.** A second `resume()` would block for the duration of a long run, holding a caller (an API request) and growing a waiter queue. Rejecting gives the caller an explicit, immediate answer. `[INFER]` if the owner prefers waiting for the in-process case it is a small change, see D-2.
- **OS advisory file locks.** Auto-release on death is attractive, but one lock file per `instance_id` accumulates without bound (every `execute()` mints a new id), deleting after unlock has a known inode race, and Windows needs a different API. Rejected.
- **PID/liveness probing for stale claims.** Unsafe on Windows (above) and wrong across PID reuse. Rejected.
- **A claims table inside the `EventStream` schema.** Couples claim traffic to the audit store and its migration path. Rejected in favour of a small separate file, `.data/events/workflow_claims.db`.
- **Status quo (deferral).** Valid today because the race is unreachable; no longer wanted by the owner's Nov 21 instruction.

## 6. Test plan and evidence `[FACT]` (local; CI result is recorded on the PR, not here)

`tests/test_workflow_instance_guard.py`, 32 tests:

- in-process: immediate rejection, independence of ids, release on exit/exception/cancellation, bounded registry (1,000 ids), a 50-way storm with exactly one winner and no waiting;
- durable store with an injected clock: conflict with holder details, expiry, stale-holder cannot renew or release, purge of crash leftovers, 16-way concurrent acquire with exactly one winner;
- guard + store: heartbeat keeps a lease alive past its TTL, lost claim, transient renew error is not a loss, fail-closed on store failure, cancellation during acquire releases a possibly committed claim;
- through the real `WorkflowRuntime`: **the race reproduced without the guard (5 concurrent resumes run the node 5 times)**; with it, 8 concurrent resumes run the node exactly once and 7 are refused with an event; a resume of a live `execute()` is refused; 20 independent executes never contend; `host` scope leaves no claim row; `host` scope fails closed without running the node; a lost claim cancels the running workflow;
- **two real processes**: a child holds the claim, the parent is refused (naming the child's PID), the lease survives past its TTL because of the child's heartbeat, the child is hard-killed, and the parent acquires once the lease expires.

Mutation check: seven deliberate defects (in-process rejection removed, durable conflict ignored, heartbeat removed, release removed, registry cleanup removed, lost-claim cancellation removed, expiry removed) were each caught by the suite. 14 existing test files (about 306 tests) touching the workflow runtime, config, orchestrator, startup and drift tooling still pass.

## 7. Compatibility, migration, rollback

- Default scope `process` changes nothing observable except that a duplicate concurrent run of one id is refused, which no production path can currently produce.
- New settings (all optional): `runtime.workflow_claim_scope`, `runtime.workflow_claim_db_path`, `runtime.workflow_claim_lease_s`. No schema change to existing stores; the claims file is created only in `host` scope.
- `WorkflowRuntime(..., instance_guard=None)` keeps existing call sites valid.
- Rollback: revert the change; `host` scope leaves only a small standalone file that can be deleted.

## 8. Non-goals

- No production `resume()` entry point is added (R3 is about ordering, not scope).
- No multi-host coordination: a lease compares wall clocks, which is sound on one host and not across hosts.
- No side-effect idempotency (DEBT-015 sub-item (7)).
- No change to DEBT-025, authentication or the control plane.

## 9. Decisions the owner must make

- **D-1 Deployment model.** Accept `process` as the default scope (today's single-process deployment), with `host` available for several processes sharing one data directory? Or make `host` the default?
- **D-2 Reject versus wait.** Accept reject-fast, or wait (bounded) for the in-process case?
- **D-3 Lease length.** Accept 60 s with a renewal every 20 s? A crashed holder blocks its instance for at most one TTL.
- **D-4 Closure.** DEBT-028 stays OPEN until the owner accepts this ADR. Should closure wait for the first production `resume()` entry point, or close when the guard is merged and verified?
