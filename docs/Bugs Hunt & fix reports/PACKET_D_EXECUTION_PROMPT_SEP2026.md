# Packet D Execution Prompt — Durability / Retry / Concurrency

**Issued:** September 16, 2026, against `main` at `c67187a`.
**Method:** same evidence-first standard as Packets A–C, with one hard precondition Packet C's own closure earned the hard way: the register gets checked before source-tracing a subsystem, not after, and every finding gets checked individually — not stopped at the first match.

## 1. Scope

```
event durability → crash recovery → checkpoint/resume semantics →
retry/idempotency → duplicate side effects → concurrent execution →
race-sensitive state transitions
```

## 2. Starting position — what's already tracked, established by a full register sweep before this prompt was written

- **`DEBT-003` (Resolved, twice-verified — once at creation Sept 5, once by Packet C's C-6 independent re-trace).** Checkpoint/resume genuinely works: durable per-node-boundary checkpointing via `EventStream`, `resume()` never assumes a `RUNNING` node completed. Not to be re-litigated as a fresh question — extended only if new evidence contradicts it.
- **`DEBT-008` (open, Low).** `EventStream` itself — `append()`, `replay()`, `create_checkpoint()`/`get_checkpoint()`, WAL persistence — has no dedicated test file. It's only incidentally exercised as a constructor dependency elsewhere. A real regression in checkpoint/replay logic specifically would not be caught. Directly in scope for this packet.
- **`DEBT-010` (open, Low–Medium).** A confirmed, empirically-reproduced race: `Config`'s background watcher thread reading `CONFIG_DIR` at call-time races against test-time patching of that module-level value, ~50% reproduction rate. Scoped today as a test-flakiness/narrow-theoretical-production issue since `CONFIG_DIR` is never reassigned at runtime outside tests. The open question this packet should pursue: is this the only instance of this pattern (singleton/background-thread reading mutable global state), or are there siblings elsewhere in the runtime that haven't been found because this one was found incidentally rather than by systematic search?
- **`DEBT-015` sub-items (7) retry/idempotency semantics for side-effecting capabilities, and (8) stale-attempt rejection.** Both explicitly proposed-only, not implemented, not blocking. This packet's job is not to implement them, but to establish whether their absence has a *concrete, live* consequence today — a reproducible case, not just the standing architectural concern already on record.
- **`DEBT-004`/`DEBT-005` (open, Low).** Event-mechanism fragmentation (`KnowledgeEvent`/`EventStream`/`EventBus`, three systems). Noted, not this packet's focus unless a durability question specifically depends on which of the three a given fact lives in.
- **`DEBT-024` (Resolved, Packet C).** SupervisorWorker's retry path is deliberately unwired, not a durability gap. Out of scope, already closed.

## 3. Particular attention to

1. Does `EventStream`'s WAL survive a simulated crash mid-write, not merely a clean shutdown — exercised, not assumed from SQLite's general reputation
2. Whether `DEBT-010`'s race pattern (background thread + module-level mutable state) has siblings elsewhere
3. Concurrent execution of the *same* `instance_id` — two callers racing `resume()`, or a retry racing a still-in-flight original attempt
4. A concrete, reproducible instance of a duplicate side effect (not the abstract DEBT-015(7) concern restated)
5. Whether checkpoint-writing itself is safe under concurrent writers, not just readable after the fact

## 4. Classification taxonomy

Carried unchanged from Packet C: **LIVE-ENFORCED / PARTIAL / DOCUMENT-ONLY / TEST-ONLY / BYPASSABLE / UNPROVEN** — applied here to durability/safety guarantees rather than authorization, with the same rule that every unresolved issue gets a concrete disposition, not an open citation.

## 5. Operating rules

- Local branch only (`audit/packet-d-durability-retry-concurrency-sep2026`, off fresh `main`). No push, no merge.
- **Register check first, for every sub-thread, before tracing source** — not once at the start of the packet, but re-applied each time a new angle opens up. This is stated as a precondition because Packet C's own closure needed two separate passes to actually achieve it.
- `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`/`PROJECT_INDEX.md` now exist and were read for this prompt; both are already stale relative to current `main` (missing the CTX-EXPORT-001 fix and new workspace-architecture files) — treated as useful orientation, not as ground truth over source.
