# Minimum Architecture Path

## Objective

This document defines the **smallest implementation set** required to achieve architecture compliance for the current phase (v4.3.5 — Complete Memory Foundation), ranked by risk, dependency order, and deferral safety.

---

## 1. Smallest Implementation Set Required

Based on the Architecture Compliance Report, only **8 components** pass the strict justification test for current-phase implementation. Of those, **5 are essential now** and **3 are stubs**.

### Tier 1 — Blocking / Non-Functional Without These

| Priority | Component | Justification | Effort |
|----------|-----------|---------------|--------|
| **P0** | `knowledge_event.py` | Import blocker. 3 files cannot import without it. System is non-functional. | Low |

### Tier 2 — Architecturally Required Now (Laws + Current Phase)

| Priority | Component | Justification | Effort |
|----------|-----------|---------------|--------|
| **P1** | `GovernanceKernel` | PI LAW 1: "The GovernanceKernel is mandatory." All workers, memory ops, and workflows depend on it. | Medium |
| **P2** | `EventStream` | PI LAW 2: "All meaningful cognitive activity must emit immutable events." FA assumes it exists. | Medium |
| **P3** | `CognitiveWorker` base class | PI §7: Foundation for all workers. Needed before any specialist worker. | Medium |
| **P4** | `MemoryCuratorWorker` | FA §6 Immediate: "Required by spec." Current phase deliverable (v4.3.6). HookRegistry already waiting. | Medium |
| **P5** | Graph-Vector Mutual Indexing | FA §6 Immediate. Current phase primary deliverable (v4.3.5.1). `KnowledgeEntry.graph_node_id` field exists. | Medium |

### Tier 3 — Stub Implementations (Satisfy PI §7.1 Canonical Types)

| Priority | Component | Justification | Effort |
|----------|-----------|---------------|--------|
| **P6** | `WorkflowEngine` | PI §6.2 mandates DAG-based workflows. FA §5.4 says "Already completed" — must restore. Minimal DAG executor. | Medium |
| **P7** | `SkillRegistry` | PI §9.1 mandates versioning and metadata. `skill_interface.py` exists; registry wraps it. | Low |

**Total: 8 components.** 1 import fix + 4 core implementations + 2 medium restorations + 1 registry.

---

## 2. Highest-Risk Missing Components

Ranked by **blast radius** — what fails if the component remains absent.

### Risk Level: CRITICAL

| Component | What Fails Without It | Cascading Impact |
|---|---|---|
| `knowledge_event.py` | `unified_memory.py`, `backends/base.py`, `backends/sqlite_archive.py` all fail to import. **No memory system at all.** | Total system failure. Nothing runs. |
| `GovernanceKernel` | No hard limits on recursion, token budget, or worker execution. Runaway loops possible. **Violates LAW 1.** | Security vulnerability. Autonomy without oversight. |
| `EventStream` | No immutable audit trail. No replay. No checkpoint/resume. **Violates LAW 2.** | Debugging impossible. Durable execution blocked. Memory operations invisible. |

### Risk Level: HIGH

| Component | What Fails Without It | Cascading Impact |
|---|---|---|
| Graph Mutual Indexing | Graph and L2 remain disjoint. No multi-hop reasoning. | Retrieval quality plateaus. v4.3.8 Cognitive Retrieval blocked. |
| `MemoryCuratorWorker` | Memory degrades silently. Stale facts persist. Contradictions accumulate. | v4.3.6 blocked. FA calls this "required by spec." |
| `CognitiveWorker` base | No structured task execution. Orchestrator stuck on old module-dispatch pattern. | All Layer 3 (Agent Runtime) work blocked. |

### Risk Level: MEDIUM

| Component | What Fails Without It | Cascading Impact |
|---|---|---|
| `WorkflowEngine` | No DAG-based execution. Complex multi-step tasks impossible. | v4.4.8 Durable Execution blocked. |
| `SkillRegistry` | Skills not discoverable, not versioned, not MCP-exposable. | v4.3.9 Instinct→Skill blocked. MCP strategy blocked. |

---

## 3. Components That Can Safely Be Deferred

These components are architecturally justified but **explicitly scheduled for later phases** per FA §5.5 and §6 Priority Matrix.

| Component | Defer Until | Justification for Deferral | What to Do Now |
|---|---|---|---|
| **BrowserWorker** (full) | v4.4.1 | FA §5.5: "Phase 4 (v4.4.x)". Requires Playwright MCP, trust pipeline. | Stub class extending CognitiveWorker |
| **EvaluatorWorker** (full) | v4.3.9 | FA §5.6: Prerequisite for Instinct→Skill. Not needed until skill learning begins. | Stub class extending CognitiveWorker |
| **PlannerWorker** (full) | v4.3.9+ | Canonical type but basic routing exists. Full planning needed for complex workflows. | Stub class extending CognitiveWorker |
| **SupervisorWorker** (full) | Phase 4+ | Absent from FA Layer 3 diagram. Weakest architectural justification of all 8 canonical workers. | Stub class only (satisfies PI §7.1) |
| **PipelineMiddleware** | v4.3.6.2 | **Not explicitly named in FA or PI.** Functionality covered by Knowledge Acquisition Pipeline + existing `privacy.py`. | **Do not implement.** |
| **ObservabilityFramework** (full) | v4.4.5 | FA §5.5 Phase 4. Langfuse listed as Immediate (v4.3.9.2) but full Prometheus/Grafana is Phase 4. | Minimal metrics wrapper around existing `tracer.py` |
| **L2 Persistence (Chroma)** | v4.3.5+ (immediate after foundation) | FA §9.1: "highest-impact bug." FA §6: CRITICAL. But requires `pip install chromadb` — external dependency. | Defer to dedicated session. Design InMemoryVectorBackend → ChromaBackend swap via existing `VectorBackend` ABC. |
| **ReflectionWorker** (full) | Phase 4+ | PI §7.3 mandates it. FA Layer 3 lists it. But requires functional EvaluatorWorker for validation pipeline. | Stub class extending CognitiveWorker |
| **CoderWorker** (full) | v4.4.1.1 | FA v4.4.1.1: "Execution Sandbox (Task Runner)." Requires isolated subprocess, import whitelist. | Stub class only |

---

## 4. Recommended Implementation Order

Based on dependency analysis from FA §5.6 and the Tier classification above.

```
Step 0:  knowledge_event.py                    [IMPORT BLOCKER FIX]
         ↓
Step 1:  GovernanceKernel                      [LAW 1 — Foundation]
         + 5 Governor stubs
         ↓
Step 2:  EventStream                           [LAW 2 — Backbone]
         (immutable WAL, pub/sub, replay)
         ↓
Step 3:  CognitiveWorker base class            [Worker Foundation]
         + specialist stubs (Planner, ReAct,
           Reflection, Coder, Evaluator,
           Browser, Supervisor)
         ↓
Step 4:  MemoryCuratorWorker                   [v4.3.6 — Active Memify]
         (registers with HookRegistry,
          wraps MemoryConsolidator)
         ↓
Step 5:  Graph-Vector Mutual Indexing          [v4.3.5.1 — GraphRAG]
         (bidirectional pointers between
          KnowledgeEntry.graph_node_id
          and graph nodes)
         ↓
Step 6:  WorkflowEngine                        [PI §6.2 — Restoration]
         (minimal DAG executor with
          serializable state,
          checkpoint hooks for v4.4.8)
         ↓
Step 7:  SkillRegistry                         [PI §9.1 — Discovery]
         (wraps skill_interface.py,
          adds versioning + discovery)
```

### Dependency Justification

```
knowledge_event.py ← required by unified_memory.py (import)
GovernanceKernel   ← required before any worker (LAW 1)
EventStream        ← required before any worker (LAW 2, workers emit events)
CognitiveWorker    ← required before MemoryCuratorWorker (base class)
MemoryCurator      ← depends on CognitiveWorker + HookRegistry + Graph
Graph Indexing     ← depends on KnowledgeEntry (exists) + GraphBackend (exists)
WorkflowEngine     ← depends on GovernanceKernel + EventStream
SkillRegistry      ← depends on nothing (standalone registry)
```

---

## 5. Components Most Likely to Cause Future Technical Debt

| Component | Debt Risk | Source of Risk | Mitigation |
|---|---|---|---|
| **WorkflowEngine** | **HIGH** | If implemented without checkpoint serialization hooks, v4.4.8 (Durable Execution) will require major rework. FA §5.3 flagged "v4.4.7 Workflow Engine" as "Duplicate — Remove" because it was assumed done. | Design all node state as serializable from day one. Include `serialize_state()` / `restore_state()` on every `WorkflowNode` even if not wired to durable storage yet. |
| **Graph Mutual Indexing** | **HIGH** | If bidirectional pointers are implemented without sync-drift detection, graph and L2 will diverge silently. FA §1.1: "graph and L2 operate independently" is the current weakness. | Include a `verify_index_consistency()` method that detects mismatches. Run it during MemoryCurator sweeps. |
| **EventStream** | **MEDIUM** | If WAL is SQLite-only with no abstraction, migration to Redpanda (v4.5.5) will be painful. | Implement against an abstract `EventStore` interface. SQLite WAL is the first concrete backend. |
| **CognitiveWorker** | **MEDIUM** | If the base class doesn't enforce governance hooks, future workers will silently bypass governance. FA §4.1: Workers sit below Governance (Layer 0 > Layer 3). | Make governance check a non-overridable method in the base class (template method pattern). Workers implement `_execute()`, base class wraps it with governance. |
| **MemoryCuratorWorker** | **LOW** | Active memify (LLM-based fact derivation) risks "hallucinated facts" entering memory as verified. FA §8 Risk 7: "Incorrect fact derivation (mitigate: low confidence score + review)." | All curator-derived entries must start with `truth_status="candidate"` and `confidence < 0.7`. Only graph-confirmed entries promote to `verified`. |
| **InMemoryVectorBackend** | **HIGH** (existing) | FA §9.1: "L2 lost on restart is the highest-impact bug." Already exists and is actively causing silent data loss. Not in the implementation set but will compound debt daily. | **Schedule Chroma migration immediately after this implementation set.** The `VectorBackend` ABC already supports this swap. |

---

## Decision Summary

### Implement Now (8 components)
1. `knowledge_event.py` — import blocker fix
2. `GovernanceKernel` — LAW 1 mandate
3. `EventStream` — LAW 2 mandate
4. `CognitiveWorker` base — Layer 3 foundation
5. `MemoryCuratorWorker` — v4.3.6 deliverable, FA §6 Immediate
6. Graph-Vector Mutual Indexing — v4.3.5.1 deliverable, FA §6 Immediate
7. `WorkflowEngine` (minimal) — PI §6.2 mandate, assumed "done" by FA
8. `SkillRegistry` — PI §9.1 mandate, partial exists

### Do NOT Implement (flagged)
- **PipelineMiddleware** — No explicit naming in FA or PI. Defer to v4.3.6.2 Knowledge Acquisition.
- **ObservabilityFramework** (full) — Phase 4.4.5. Minimal tracer wrapper is acceptable.
- **BrowserWorker** (full) — Phase 4.4.1. Stub only.
- **SupervisorWorker** (full) — Absent from FA Layer 3. Stub only.

### Immediate Follow-Up (Next Session)
- **L2 Persistence (Chroma)** — FA §6 CRITICAL. Highest-impact bug. Requires external dependency.
- **Langfuse Integration** — FA §6 Immediate. Lowest-effort, highest-impact observability.
