# OCBrain — Architecture Changelog

**Purpose:** Historical context for architecture decisions. Gives future contributors the "why" and "what changed" without cluttering the canonical specification. Read `KERNEL_ARCHITECTURE_v1.0.md` for the current architecture. Read this document for how it got here.

---

## Timeline

| Date | Session | Document | Key Outcome |
|---|---|---|---|
| Pre-2026 | Sessions 1–3 | — | Initial module-based system: expert modules, ChromaDB, Ollama integration |
| 2026 Q1–Q2 | Session 4 | `SESSION4_REPORT.md` | UnifiedMemory activated as production memory owner. Legacy cognitive_vault superseded. |
| 2026 Q1–Q2 | Session 4B | `SESSION4B_REPORT.md` | Structured memory payload, stable identity semantics, enriched metadata |
| 2026 Q1–Q2 | Session 4C | `SESSION4C_REPORT.md` | Identity semantics fixed (query-only hash). Summary field reserved for LLM generation. |
| 2026 Q2 | Session 5 | (inline in code) | Governance + EventStream wired into Orchestrator. GraphBackend registered at startup. Composition root hardened. |
| 2026 Q2 | Session 5.25 | (inline in code) | GraphIndexer built. UnifiedMemory.update() syncs graph. TruthStatusEligibilityPolicy. |
| 2026 Q2 | Session 5.5 | (inline in code) | RegexEntityExtractor enabled at composition root. Graph population strategy decided. |
| 2026 Q2 | Architecture Hardening | `ARCHITECTURE_HARDENING_SESSION_REPORT.md` | Dead code audit. MemoryConsolidator stopped. Composition root cleaned. Evidence-first audit methodology established. |
| 2026 Q2 | Repository Cleanup | `REPOSITORY_CLEANUP_REPORT.md` | Stale files removed. Archive directory created. |
| Jul 8, 2026 | Constitution | `OCBRAIN_KERNEL_CONSTITUTION.md` | 9-law Constitution drafted (later updated to 11 laws). North Star: "The kernel coordinates; it does not own." |
| Jul 8, 2026 | Constitution Rationale | `OCBRAIN_KERNEL_CONSTITUTION_RATIONALE.md` | Section-by-section reasoning. Reconciliation with PROJECT_INSTRUCTIONS.md. Naming review. |
| Jul 8, 2026 | Constitution Pressure Test | `OCBRAIN_KERNEL_CONSTITUTION_PRESSURE_TEST.md` | Stress-tested Constitution against real scenarios. Proposed 2 new laws (Contract Stability, Failure Containment). |
| Jul 8, 2026 | **K1 — Kernel Runtime Audit** | `OCBRAIN_K1_KERNEL_AUDIT_AND_SPECIFICATION.md` | Complete audit of running system vs. Constitution. Found Worker layer fully built and fully disconnected. Found governance partially compliant. Established K2 sub-phasing. |
| Jul 8, 2026 | **K1.5 — Kernel API & Service Model** | `OCBRAIN_K1.5_KERNEL_API_SERVICE_MODEL.md` | Vocabulary freeze (42 terms). Service catalog (9 services). Discovered second disconnected subsystem (RetrievalContextBuilder/GraphRAG). Merged Worker + Retrieval wiring into one K2 milestone. |
| Jul 8, 2026 | **K1.6 — Resource Model** | `OCBRAIN_K1.6_RESOURCE_MODEL.md` | Resource as Protocol. Four-category taxonomy (Resource, wrapper, projection, ephemeral). KnowledgeEntry confirmed as the only existing Resource. Twelve-state lifecycle rejected. |
| Jul 10, 2026 | **K1.7–K1.11 — Architecture Freeze** | `OCBRAIN_K1.7-K1.11_FINAL_ARCHITECTURE_FREEZE.md` | ExecutionRuntime, CapabilityModel, WorkflowRuntime, WorkerRuntime fully specified. 6 ADRs. 16 interfaces. Ownership matrix. Dependency graph. K2 readiness confirmed. |
| Jul 10, 2026 | **K4 — Contract Freeze** | (Implicit in K1.7–K1.11) | All public contracts frozen. Architecture locked for K2 implementation. |
| Jul 10, 2026 | **Consolidation** | `KERNEL_ARCHITECTURE_v1.0.md` | All specifications merged into single canonical document. |

---

## Major Architecture Decisions

### 1. Worker Layer — Template Method Pattern

**Decision:** `AbstractCognitiveWorker.execute()` is non-overridable. It wraps `_run()` inside governance evaluation and event emission. Subclasses override only `_run()`.

**Why:** Makes governance bypass structurally impossible. A Worker cannot skip governance by overriding the wrong method — the governance call lives in the non-overridable template.

**When decided:** Pre-K1 (built in v4.3.5 sessions). Confirmed as permanent in K1.7–K1.11.

### 2. UnifiedMemory as Production Memory Owner

**Decision:** `UnifiedMemory` replaced the legacy `cognitive_vault` as the canonical memory system. L0–L4 tier model.

**Why:** The old system had fragmented storage (multiple disconnected stores). UnifiedMemory centralizes with a clean public API while keeping backend flexibility.

**When decided:** Session 4. Confirmed stable in K1.

### 3. EventStream — Durable Event Log

**Decision:** `EventStream` (SQLite WAL-backed, append-only, with replay and checkpoints) became the canonical event system. Complements but does not replace the in-process `EventBus`.

**Why:** PI LAW 2 requires all meaningful activity to emit immutable events. EventBus was in-memory only — no durability, no replay. EventStream provides both while keeping EventBus for low-latency in-process delivery.

**When decided:** v4.3.5 sessions. Confirmed in K1. Relationship clarified (EventBus subscribes to EventStream) in K1.7–K1.11 as ADR-006.

### 4. Resource as Protocol, Not ABC

**Decision:** The `Resource` type is a `Protocol` (structural typing). Objects satisfy it by having the right fields, not by inheriting from a base class.

**Why:** `KnowledgeEntry` already exists with a working inheritance chain and live consumers. Requiring ABC inheritance would force changing its class declaration, breaking Contract Stability. Only objects with genuine independent identity, lifecycle, and persistence satisfy Resource.

**When decided:** K1.6.

### 5. ExecutionContext Replaces WorkerContext

**Decision:** `ExecutionContext` is the canonical execution parameter object. `WorkerContext` is deprecated.

**Why:** Two overlapping context objects doing the same job violates Single Source of Truth. `ExecutionContext`'s name matches its ownership (created by ExecutionRuntime).

**When decided:** K1 proposed the concept. K1.5 specified the fields. K1.7–K1.11 froze it as ADR-001.

### 6. CapabilityAdapter as Protocol

**Decision:** `CapabilityAdapter` is a Protocol. Existing `Provider` classes satisfy it by shape, not inheritance.

**Why:** Provider already has `is_available`, `health_score`, `mark_success()`, `mark_failure()`. A Protocol generalizes this proven pattern from inference-only to all capabilities without touching Provider's class hierarchy.

**When decided:** K1.7–K1.11 (ADR-002).

### 7. Workers Are Ephemeral

**Decision:** New Worker instance per `ExecutionRuntime.invoke()` call. No state persists across invocations.

**Why:** Singleton workers accumulate hidden state across calls, violating Explicit State. The `_total_executions` counter on `AbstractCognitiveWorker` is evidence of this risk.

**When decided:** K1.5 (direction). K1.7–K1.11 (ADR-003, frozen).

### 8. WorkflowRuntime Owns Retries

**Decision:** Retry logic at the workflow node level, not inside Workers or ExecutionRuntime.

**Why:** Workers shouldn't know about infrastructure concerns (Separation of Concerns). A single `invoke()` should be one attempt — implicit retries are hidden side effects violating Determinism.

**When decided:** K1.7–K1.11 (ADR-004).

### 9. No Automatic Rollback

**Decision:** Failed workflows are marked FAILED; completed node results are preserved. No automatic compensating actions.

**Why:** Most cognitive operations (inference, analysis) don't have meaningful inverses. Designing rollback for non-reversible operations would be speculative architecture violating Evidence over Assumption.

**When decided:** K1.7–K1.11 (ADR-005).

### 10. Retrieval Stack Consolidation

**Decision:** `RetrievalContextBuilder` + `GraphRAGPipeline` is the canonical retrieval path. `RetrievalFusionEngine` (the simpler, live path) is superseded.

**Why:** Both stacks were fully built. The sophisticated one matches the Constitution's vocabulary and the Resource Model's `Context` concept. Running two stacks in parallel is dead weight.

**When decided:** K1.5 (§0, §6, §13).

---

## Deprecated Concepts

| Concept | Replaced By | When | Why |
|---|---|---|---|
| `cognitive_vault` | `UnifiedMemory` | Session 4 | Fragmented storage, disconnected from production path |
| `MemoryConsolidator` (hourly task) | `MemoryCuratorWorker` | Architecture Hardening | Was operating on the wrong store (legacy cognitive_vault) |
| `Module` (as dispatch unit) | `Capability` / `Skill` | K1.5 | Modules are the older expert-module concept; Capabilities are contract-based |
| `WorkerContext` | `ExecutionContext` | K1.7–K1.11 | Two overlapping context objects |
| `RetrievalFusionEngine` | `RetrievalContextBuilder` | K1.5 | Simpler stack superseded by structured, provenance-aware retrieval |
| `classify() → module labels` | Capability resolution | K1.5 | Module-label scheme superseded by CapabilityRegistry |
| 12-state universal lifecycle | Per-type lifecycle enums | K1.6 | No evidence for Fork/Merge/Snapshot operations |
| Singleton GovernanceKernel state | Per-workflow budget context | BUG-03 fix (v4.3.5) | Singleton accumulated step_count across process lifetime, permanently rejecting after 100 evaluations |

---

## Migration History

### Session 4 → Session 5: Memory Migration

`cognitive_vault` → `UnifiedMemory` as production memory owner. All memory reads/writes routed through `UnifiedMemory.write()` / `.search()`. Legacy `MemoryConsolidator` stopped (was writing to wrong store).

### Session 5: Governance + Events Wiring

`GovernanceKernel` and `EventStream` explicitly constructed at composition root. Previously only instantiated via singleton getters from `AbstractCognitiveWorker.__init__()`, which was never called (no Workers constructed in production). Now both are explicitly passed to `Orchestrator`.

### Session 5.25–5.5: Graph Foundation

`SQLiteGraphBackend` registered at startup. `GraphIndexer` built with eligibility/extraction/sync/removal. `RegexEntityExtractor` enabled at composition root. `UnifiedMemory.update()` now syncs graph nodes.

### K1 → K1.5: Second Disconnection Found

K1 found the Worker layer disconnected. K1.5's independent re-audit discovered the same pattern in `RetrievalContextBuilder`/`GraphRAGPipeline` — built, tested (64K of tests), zero consumers in the live path. Merged both disconnections into one K2 milestone.

### K1.6: Resource Model Scoping

The expected finding ("unify everything under Resource") was reversed by field-level inspection. Most objects were already correctly *not* unified — they were deliberately designed as storage-decoupled projections. Only `KnowledgeEntry` is a genuine Resource. Protocol-based approach chosen for zero-churn integration.

### K1.7–K1.11: Full Specification

Every remaining architectural question resolved. 6 ADRs written. 16 interfaces specified. Ownership matrix established. Dependency rules documented. Architecture frozen.

---

## Known Technical Debt (at freeze)

| Area | Debt | Severity | Tracking |
|---|---|---|---|
| Workers | 7 of 8 canonical types unbuilt. `MemoryCuratorWorker` exists but never instantiated. | Critical | K2.1 |
| Retrieval | Sophisticated stack (RCB/GraphRAG) disconnected from live path | Critical | K2.2 |
| Governance | `MemoryGovernor` interface incompatible with `Governor` base class. 2 governors unbuilt. | High | K2.4 |
| Memory | L2 semantic memory loses embeddings on restart (InMemoryVectorBackend) | High | v4.5.3 |
| Documentation | README.md, PRODUCT.md describe older product identity | Medium | Parallel |
| Graph | Default run produces no graph population (nothing calls write() with truth_status yet) | Medium | K2.1 (MemoryCuratorWorker wiring) |

---

*Changelog complete. This document is a historical record. For current architecture, see `KERNEL_ARCHITECTURE_v1.0.md`.*
