# ADR-K3.5-01: Event Architecture — EventStream vs EventBus

**Status:** Accepted
**Date:** 2026-07-17
**Context:** K3.5 Kernel Hardening (Constitution Law 9 — Single Source of Truth)

---

## Decision

OCBrain maintains two event systems that serve different architectural layers.
They are **not** duplicated authority. They are **not** planned for merger.

### EventStream (`core/events/event_stream.py`)

| Property | Value |
|---|---|
| **Layer** | Kernel Infrastructure (FA §4.1 Layer 1) |
| **Durability** | Durable — SQLite WAL-mode, append-only |
| **Replay** | Supported — full event replay from any checkpoint |
| **Checkpoints** | Named checkpoint markers for durable execution |
| **Pub/Sub** | Async subscribers, ordered delivery |
| **Scope** | Kernel lifecycle events |

**Canonical event types:**
- `worker.started`, `worker.completed`, `worker.failed`, `worker.cancelled`, `worker.rejected`, `worker.escalated`, `worker.progress`
- `workflow.started`, `workflow.completed`
- `execution.completed`
- `orchestrator.query_started`, `orchestrator.query_completed`, `orchestrator.query_failed`, `orchestrator.rejected`, `orchestrator.escalated`
- `memory_write_rejected`, `memory_write_escalated` (K3.5)

**Authority:** EventStream is the canonical event system for all kernel infrastructure.
All future kernel events MUST use EventStream.

### EventBus (`core/event_bus.py`)

| Property | Value |
|---|---|
| **Layer** | Application Signaling |
| **Durability** | Ephemeral — in-process only, lost on restart |
| **Replay** | Not supported |
| **Checkpoints** | Not supported |
| **Pub/Sub** | Async callbacks, no ordering guarantees |
| **Scope** | Module lifecycle and application-level notifications |

**Canonical event types:**
- `module.promoted`, `module.rollback`, `module.weights_updated`, `module.weights_failed`, `module.created`
- `learning.crawl_done`, `learning.clean_done`, `learning.train_started`, `learning.train_done`, `learning.distill_done`, `learning.gap_detected`
- `kb.ingested`
- `brain.ready`

**Authority:** EventBus is the application-level notification system.
It is not suitable for kernel events that require durability or replay.

---

## Rationale

### Why two systems?

1. **Different durability requirements.** Kernel events (governance decisions, worker lifecycle, memory write rejections) must survive process restarts for replay, audit, and debugging. Module lifecycle events (`module.promoted`, `brain.ready`) are transient signals that only need to reach in-process subscribers during the current run.

2. **Different performance profiles.** EventStream writes to SQLite on every append — acceptable for kernel events (tens to hundreds per request), but unnecessary overhead for high-frequency application signals.

3. **Different consumers.** EventStream consumers need replay (future: durable workflow resume from checkpoint). EventBus consumers are immediate, in-process handlers (e.g., the health monitor reacting to `module.weights_updated`).

### Why not merge them?

Merging would force one of two bad outcomes:
- Making all events durable (unnecessary SQLite writes for transient signals)
- Making all events ephemeral (losing the replay/audit capability that Law 2 requires)

The two-system design correctly separates these concerns.

### Boundary rule

A new event belongs in **EventStream** if:
- It represents a kernel governance decision, lifecycle transition, or state mutation
- It must be replayable or auditable
- It may be needed to resume durable execution

A new event belongs in **EventBus** if:
- It is a transient application signal
- Losing it on restart has no correctness impact
- It does not need replay

---

## Consequences

- EventStream remains the **sole durable event authority** in the kernel.
- EventBus remains the **sole application signaling mechanism**.
- No event type should be emitted to both systems (that would be duplicated authority).
- Future kernel events (e.g., Cognitive Layer plan compilation events) MUST use EventStream.
- Future application events (e.g., UI notifications) MAY use EventBus.

---

## References

- Constitution Law 2 — Explicit State
- Constitution Law 9 — Single Source of Truth
- FA §4.1 Layer 1 — EventStream
- `core/events/event_stream.py` — Implementation
- `core/event_bus.py` — Implementation
