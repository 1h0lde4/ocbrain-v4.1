# OCBrain — Architecture Decision Records Index

**Purpose:** Central index of all Architecture Decision Records (ADRs) for the OCBrain kernel.
**Last synchronized:** Aug 16, 2026 (added ADR-K4.2-H-01 through ADR-K4.2-H-09, minus H-03/H-07 which are H2 scope)

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
| ADR-K4.2-H-01 | Layered Semantic Authority (K42-001 fix) | Accepted | `ADR_K4_2_H_01_LAYERED_SEMANTIC_AUTHORITY.md` |
| ADR-K4.2-H-02 | General-Purpose Capability Fallback (K42-002 fix) | Accepted | `ADR_K4_2_H_02_GENERAL_PURPOSE_FALLBACK.md` |
| ADR-K4.2-H-03 | Capability discrimination acceptance suite | **H2 — not yet written** | — |
| ADR-K4.2-H-04 | Canonical CapabilityDiscoveryResult | Accepted | `ADR_K4_2_H_04_CAPABILITY_DISCOVERY_RESULT.md` |
| ADR-K4.2-H-05 | Unified Operation Recovery Budget | Accepted | `ADR_K4_2_H_05_UNIFIED_RECOVERY_BUDGET.md` |
| ADR-K4.2-H-06 | Learning Domain Contract — frozen for H1, K4.1-L reconciliation deferred | Accepted (as a deferral) | `ADR_K4_2_H_06_LEARNING_DOMAIN_DEFERRED.md` |
| ADR-K4.2-H-07 | Terminal Planner impasse operational diagnostics | **H2 — not yet written** | — |
| ADR-K4.2-H-08 | Trace and Operation Identifier Semantics | Accepted | `ADR_K4_2_H_08_TRACE_AND_OPERATION_SEMANTICS.md` |
| ADR-K4.2-H-09 | Causal Provenance — derived_from vs. caused_by | Accepted | `ADR_K4_2_H_09_CAUSAL_PROVENANCE.md` |

---

## Recommended Future ADRs

- ADR-K4.2-H-03 — Capability discrimination acceptance suite (H2)
- ADR-K4.2-H-07 — Terminal Planner impasse operational diagnostics beyond H1's minimal dependency (H2)
- ADR-K4.2-H-10 — Architecture-drift verification tooling (H2)
- ADR-K4.2-H-11 — Language-aware/preserving support (H2)
- A future ADR performing the actual K4.1-L reconciliation pass ADR-K4.2-H-06 explicitly defers (see `KNOWN_ISSUES.md` DEBT-011) — required before K4.2.6+ (Shared ValidationGate and Learning Wiring).

---

*Update this index when new ADRs are created.*
