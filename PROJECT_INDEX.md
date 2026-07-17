# OCBrain — Project Index

**Purpose:** Map of the repository for new contributors and AI sessions.
**Last synchronized:** July 2026

---

## Document Hierarchy

Documents are listed in order of authority. Higher-authority documents govern lower ones.

| Priority | Document | Location | Purpose |
|---|---|---|---|
| 1 | Kernel Constitution | `OCBRAIN_KERNEL_CONSTITUTION.md` | 9 laws, 9 invariants — highest authority |
| 2 | Kernel Architecture v1.0 | `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` | Frozen engineering specification |
| 3 | Project Instructions | `docs/architecture/PROJECT_INSTRUCTIONS.md` | Operational engineering rules |
| 4 | Architecture Changelog | `docs/architecture/ARCHITECTURE_CHANGELOG.md` | Historical context for architecture decisions |
| 5 | Current State | `CURRENT_STATE.md` | What is actually built right now |
| 6 | Implementation Roadmap | `IMPLEMENTATION_ROADMAP.md` | What comes next |
| 7 | Known Issues | `KNOWN_ISSUES.md` | Active debt, deferred items, future work |
| 8 | Product Definition | `PRODUCT.md` | External-facing product description |
| 9 | README | `README.md` | Repository entry point |
| 10 | Changelog | `CHANGELOG.md` | Release history |

---

## Directory Structure

```
ocbrain-v4.1-main/
├── main.py                          # Composition root — all singletons wired here
├── OCBRAIN_KERNEL_CONSTITUTION.md   # 9 laws, 9 invariants (highest authority)
├── CURRENT_STATE.md                 # What is built right now
├── IMPLEMENTATION_ROADMAP.md        # What comes next
├── KNOWN_ISSUES.md                  # Technical debt register
├── PROJECT_INDEX.md                 # This file — repository map
├── PRODUCT.md                       # Product definition
├── README.md                        # Repository entry point
├── CHANGELOG.md                     # Release history
│
├── core/                            # Kernel implementation
│   ├── runtime/                     # K2.1 — Execution Runtime
│   │   ├── execution_runtime.py     #   Worker invocation service
│   │   ├── execution_context.py     #   Canonical execution parameter object
│   │   ├── cancellation.py          #   Cooperative cancellation
│   │   ├── working_memory.py        #   L0 per-execution scratch space
│   │   ├── worker_registry.py       #   Worker type index
│   │   └── state.py                 #   Runtime state store
│   │
│   ├── workflow/                    # K2.2 — Workflow Runtime
│   │   ├── runtime.py               #   DAG coordinator
│   │   ├── definition.py            #   Workflow/Node/Edge definitions
│   │   ├── instance.py              #   Workflow instance tracking
│   │   └── result.py                #   WorkflowResult
│   │
│   ├── capabilities/                # K2.3 — Capability Runtime
│   │   ├── capability.py            #   CapabilityType, Adapter Protocol, BaseAdapter
│   │   ├── registry.py              #   CapabilityRegistry (metadata-only)
│   │   ├── adapter_runtime.py       #   AdapterRuntime (execution, fallback)
│   │   └── adapters/                #   Concrete adapters
│   │       ├── model_router_adapter.py
│   │       ├── ollama_adapter.py
│   │       └── openai_compat_adapter.py
│   │
│   ├── governance/                  # K2.4 — Governance
│   │   ├── governance_kernel.py     #   GovernanceKernel + Recursion/Budget/Evolution governors
│   │   ├── orchestration_governor.py#   OrchestrationGovernor
│   │   ├── agent_governor.py        #   AgentGovernor
│   │   ├── conversation_guardrails.py#  ConversationGuardrails
│   │   └── memory_governor.py       #   MemoryGovernor
│   │
│   ├── workers/                     # Cognitive Workers
│   │   ├── base.py                  #   AbstractCognitiveWorker (template method)
│   │   ├── planner.py               #   PlannerWorker (K2.2)
│   │   └── memory_curator.py        #   MemoryCuratorWorker
│   │
│   ├── memory/                      # Memory Service
│   │   ├── unified_memory.py        #   UnifiedMemory (L0–L4)
│   │   ├── knowledge_entry.py       #   KnowledgeEntry (canonical Resource)
│   │   ├── knowledge_event.py       #   KnowledgeEvent (L4 Archive audit trail)
│   │   ├── assembly.py              #   ContextAssemblyEngine
│   │   └── retrieval/               #   Retrieval stack
│   │       ├── fusion.py            #     RetrievalFusionEngine (façade)
│   │       ├── context/             #     RetrievalContextBuilder
│   │       └── graphrag/            #     GraphRAGPipeline
│   │
│   ├── events/                      # Event System
│   │   └── event_stream.py          #   EventStream (SQLite WAL, durable)
│   │
│   ├── event_bus.py                 # EventBus (in-process pub/sub, non-durable)
│   ├── orchestrator.py              # Orchestrator (query handler)
│   ├── model_router.py              # ModelRouter (inference routing)
│   └── provider_mesh.py             # Provider health management
│
├── docs/
│   ├── architecture/                # Canonical architecture documents
│   │   ├── KERNEL_ARCHITECTURE_v1.0.md
│   │   ├── ARCHITECTURE_CHANGELOG.md
│   │   ├── PROJECT_INSTRUCTIONS.md
│   │   └── decisions/               # Architecture Decision Records
│   │       ├── ADR_INDEX.md
│   │       ├── ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md
│   │       └── ADR_K2_EXT_01_EXTENSION_OVER_MODIFICATION.md
│   │
│   └── reports/                     # Session and audit reports
│       ├── FINAL_K3_READINESS_AUDIT.md
│       ├── ARCHITECTURE_CONSOLIDATION_AND_K3_READINESS_REPORT.md
│       ├── K2_2_RETRIEVAL_CUTOVER_REPORT.md
│       ├── K2_4_GOVERNANCE_IMPLEMENTATION_REPORT.md
│       └── ... (session reports)
│
├── tests/                           # Test suites
├── interface/                       # API layer (FastAPI)
└── modules/                         # Legacy expert modules
```

---

## Report Chronology

Reports in approximate chronological order:

| Report | Location | Covers |
|---|---|---|
| Session 4 Report | `docs/reports/SESSION4_REPORT.md` | UnifiedMemory activation |
| Session 4B Report | `docs/reports/SESSION4B_REPORT.md` | Structured memory payload |
| Session 4C Report | `docs/reports/SESSION4C_REPORT.md` | Identity semantics fix |
| Architecture Hardening | `docs/reports/ARCHITECTURE_HARDENING_SESSION_REPORT.md` | Dead code audit |
| K2.2 Workflow Cutover | `K2_2_CUTOVER_REPORT.md` | WorkflowRuntime wiring |
| K2.2 Retrieval Cutover | `docs/reports/K2_2_RETRIEVAL_CUTOVER_REPORT.md` | Retrieval Runtime cutover |
| K2.4 Governance | `docs/reports/K2_4_GOVERNANCE_IMPLEMENTATION_REPORT.md` | Governance completion |
| Doc Synchronization | `docs/reports/K2_DOCUMENTATION_SYNCHRONIZATION_AND_K2_4_READINESS_REPORT.md` | Documentation sync |
| Architecture Consolidation | `docs/reports/ARCHITECTURE_CONSOLIDATION_AND_K3_READINESS_REPORT.md` | K3 readiness |
| Final K3 Readiness Audit | `docs/reports/FINAL_K3_READINESS_AUDIT.md` | Independent K3 readiness assessment |
| Final Architecture Audit | `docs/reports/KERNEL_V1_0_FINAL_ARCHITECTURE_AUDIT_REVISION.md` | Architecture validation |

---

## ADR Index

See `docs/architecture/decisions/ADR_INDEX.md` for the complete Architecture Decision Record index.

---

## Quick Reference

**"What is built?"** → Read `CURRENT_STATE.md`

**"What's next?"** → Read `IMPLEMENTATION_ROADMAP.md`

**"What's broken or missing?"** → Read `KNOWN_ISSUES.md`

**"How does it work?"** → Read `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md`

**"What principles govern it?"** → Read `OCBRAIN_KERNEL_CONSTITUTION.md`

**"Why was X decided?"** → Read `docs/architecture/ARCHITECTURE_CHANGELOG.md` and `docs/architecture/decisions/`

**"How do I contribute?"** → Read `docs/architecture/PROJECT_INSTRUCTIONS.md`

---

*This document is the repository map. Update it when files are added, moved, or removed.*
