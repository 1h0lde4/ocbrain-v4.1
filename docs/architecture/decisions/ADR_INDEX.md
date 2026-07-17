# OCBrain — Architecture Decision Records Index

**Purpose:** Central index of all Architecture Decision Records (ADRs) for the OCBrain kernel.
**Last synchronized:** July 2026

---

## ADR Numbering Conventions

Two numbering conventions exist in this project:

1. **ADR-001 through ADR-008** — Embedded in `KERNEL_ARCHITECTURE_v1.0.md` §21, written during the K1.7–K1.11 Architecture Freeze. These are authoritative and frozen with the architecture spec.
2. **ADR-K2.x-NN** — Standalone files in this directory, written during K2 implementation phases.

Both conventions are valid. Embedded ADRs are part of the frozen spec; standalone ADRs document decisions made during implementation.

---

## Embedded ADRs (in KERNEL_ARCHITECTURE_v1.0.md §21)

| ADR | Title | Decision |
|---|---|---|
| ADR-001 | ExecutionContext replaces WorkerContext | `ExecutionContext` is the canonical execution parameter object. `WorkerContext` is deprecated. |
| ADR-002 | CapabilityAdapter as Protocol | `CapabilityAdapter` (now named `Adapter`) is a Protocol, not an ABC. Existing Provider classes satisfy it by shape. |
| ADR-003 | Workers are ephemeral | New Worker instance per `ExecutionRuntime.invoke()` call. No state persists across invocations. |
| ADR-004 | WorkflowRuntime owns retries | Retry logic at the workflow node level, not inside Workers or ExecutionRuntime. |
| ADR-005 | No automatic rollback | Failed workflows are marked FAILED; completed node results are preserved. No compensating actions. |
| ADR-006 | EventStream complements EventBus | EventStream provides durability/replay. EventBus provides low-latency in-process delivery. Both coexist. |
| ADR-007 | — | (See KERNEL_ARCHITECTURE_v1.0.md §21) |
| ADR-008 | — | (See KERNEL_ARCHITECTURE_v1.0.md §21) |

---

## Standalone ADRs

| ADR | Title | Status | File |
|---|---|---|---|
| ADR-K2.3-01 | Governance Ownership in Capability Runtime | Draft | `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` |
| ADR-K2-EXT-01 | Extension over Modification | Accepted | `ADR_K2_EXT_01_EXTENSION_OVER_MODIFICATION.md` |
| ADR-K3.5-01 | Event Architecture — EventStream vs EventBus | Accepted | `ADR_K3_5_01_EVENT_ARCHITECTURE.md` |

---

## Recommended Future ADRs

None currently identified. ADRs should be written when a significant architectural decision is made during implementation.

---

*Update this index when new ADRs are created.*
