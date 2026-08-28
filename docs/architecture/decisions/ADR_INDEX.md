# OCBrain — Architecture Decision Records Index

**Purpose:** Central index of all Architecture Decision Records (ADRs) for the OCBrain kernel.
**Last synchronized:** Aug 22, 2026, K4.2-H2-D10 integration (H-10's entry description updated -- the full DRIFT-10..15 enforcement layer and CI wiring are now merged, not just the baseline this ADR originally recorded; see K4_2_H2_D10_COMPLETION_REPORT.md and the independent audit K4_2_H2_FINAL_INDEPENDENT_AUDIT.md); prior sync Aug 22, 2026 (K4.2-H2 integration: ADR-K4.2-H-03 and H-07 filled in — both were H2-scope placeholders as of the last sync; ADR-K4.2-H-10, H-11, H-12 added (all three written by the H2 parallel packets, promoted from DRAFT where the deferred question each one flagged is now resolved — see their own "Consequences"/"Decision" sections); ADR-K4.2-H-13 added (a live-debugging fix, not one of the four H2 parallel packets — see that ADR's own Author field); prior sync Aug 16, 2026 added ADR-K4.2-H-01 through ADR-K4.2-H-09, minus H-03/H-07 which are H2 scope)

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
| ADR-K4.2-H-03 | Capability Discrimination — Registration-Order Tie-Break | Accepted | `ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md` |
| ADR-K4.2-H-04 | Canonical CapabilityDiscoveryResult | Accepted | `ADR_K4_2_H_04_CAPABILITY_DISCOVERY_RESULT.md` |
| ADR-K4.2-H-05 | Unified Operation Recovery Budget | Accepted | `ADR_K4_2_H_05_UNIFIED_RECOVERY_BUDGET.md` |
| ADR-K4.2-H-06 | Learning Domain Contract — frozen for H1, K4.1-L reconciliation deferred | Accepted (as a deferral) | `ADR_K4_2_H_06_LEARNING_DOMAIN_DEFERRED.md` |
| ADR-K4.2-H-07 | Terminal Planner Impasse Diagnostic Closeout | Accepted (verification closeout — no code change) | `ADR_K4_2_H_07_TERMINAL_IMPASSE_CLOSEOUT.md` |
| ADR-K4.2-H-08 | Trace and Operation Identifier Semantics | Accepted | `ADR_K4_2_H_08_TRACE_AND_OPERATION_SEMANTICS.md` |
| ADR-K4.2-H-09 | Causal Provenance — derived_from vs. caused_by | Accepted | `ADR_K4_2_H_09_CAUSAL_PROVENANCE.md` |
| ADR-K4.2-H-10 | Architecture-Drift Verification Tooling (D10: baseline + full DRIFT-10..15 enforcement layer + CI wiring) | Accepted | `ADR_K4_2_H_10_DRIFT_TOOLING_RECORD.md` |
| ADR-K4.2-H-11 | Request Language Detection | Accepted | `ADR_K4_2_H_11_LANGUAGE_SUPPORT.md` |
| ADR-K4.2-H-12 | Tracking & Documentation Hardening — `IMPLEMENTATION_TRACKER.md` Disposition | Accepted (scope-extension question resolved at integration — see the ADR's §2 point 2 and `IMPLEMENTATION_TRACKER.md`'s own closing note) | `ADR_K4_2_H_12_TRACKING_HARDENING.md` |
| ADR-K4.2-H-13 | General-Purpose-Only Plans Exempt from ClarificationPolicy | Accepted | `ADR_K4_2_H_13_GENERAL_PURPOSE_CLARIFICATION_EXEMPTION.md` |

*H-13 note: not one of H2's four parallel packets (D3/D7/D11/D12) — a live-debugging fix for a pre-existing, pre-H2 bug (ClarificationPolicy's unconditional 0.5 threshold escalating essentially any request, since the sole registered capability is general-purpose and its own description rarely overlaps lexically with a real request). See the ADR's own Context section.*

---

## Recommended Future ADRs

- A future ADR performing the actual K4.1-L reconciliation pass ADR-K4.2-H-06 explicitly defers (see `KNOWN_ISSUES.md` DEBT-011) — required before K4.2.6+ (Shared ValidationGate and Learning Wiring).
- A future ADR for wiring `RawRequest.detected_language` (ADR-K4.2-H-11) into capability-matching, if that's ever wanted — explicitly out of scope for H-11 itself, per its own Context section and `docs/architecture/h2_packet_ownership.json`'s D11 coordination note.

---

## Agent Evaluation & Reliability Lab Track (ADR-LAB-*)

Parallel/non-blocking track — evaluates OCBrain, does not modify K4.2, the Execution Reliability Track, or Cognitive-Phase-Future work. See `docs/reports/AGENT_EVALUATION_RELIABILITY_LAB_RESEARCH_AND_ARCHITECTURE_REPORT.md` for the full research and architecture writeup these ADRs come from. All four below are `PROPOSED`, pending human review before any Lab code is written.

| ADR ID | Title | Status | File |
|---|---|---|---|
| ADR-LAB-01 | Evaluation Run Identity & Three-Layer Trust Separation | Proposed | `ADR_LAB_01_EVALUATION_RUN_IDENTITY_AND_TRUST_SEPARATION.md` |
| ADR-LAB-02 | Runtime/Lab Package Boundary & Trace Adapter Source Priority | Proposed | `ADR_LAB_02_RUNTIME_LAB_BOUNDARY_AND_TRACE_ADAPTER.md` |
| ADR-LAB-03 | Evaluator Layering, Evidence Model & Judge Calibration | Proposed | `ADR_LAB_03_EVALUATOR_LAYERING_EVIDENCE_AND_JUDGE_CALIBRATION.md` |
| ADR-LAB-04 | Benchmark & Evaluator Versioning / Historical Immutability | Proposed | `ADR_LAB_04_BENCHMARK_AND_EVALUATOR_VERSIONING.md` |

---

*Update this index when new ADRs are created.*
