# OCBrain v4.1 — Product Definition

## What OCBrain Is

OCBrain is a **local-first cognitive operating system**. It is an open-source, self-hosted
intelligence runtime that coordinates LLM inference, memory, retrieval, and autonomous
workers under constitutional governance.

**North Star**: The kernel coordinates; it does not own.

**Core values**: Governed autonomy. Replayable execution. User sovereignty.

OCBrain is not a chatbot. It is not an LLM wrapper. It is not a RAG framework.
It is not a cloud service. It is not a workflow automation tool.

---

## Governing Principles

All design decisions are bound by the **Kernel Constitution** — 11 laws and 9 invariants
that define what the system may and may not do. The Constitution is not advisory; it is
enforced at runtime by the GovernanceKernel.

Key constitutional constraints:
- Every state change is event-sourced and replayable
- No component may bypass governance checks
- Memory is tiered and governed, never silently discarded
- Workers operate under budget, recursion, and evolution limits
- The user retains sovereignty over all data and execution

The engineering specification is frozen in `KERNEL_ARCHITECTURE_v1.0.md`.

---

## Current Capabilities

| Subsystem | Status | Description |
|:---|:---|:---|
| **GovernanceKernel** | Live (3/5+ governors) | RecursionGovernor, BudgetGovernor, EvolutionGovernor |
| **EventStream** | Live | SQLite WAL, immutable append, pub/sub, replay, checkpoints |
| **UnifiedMemory** | Live | L0–L4 tier model with graph backend |
| **GraphRAG Pipeline** | Built, tested | RetrievalContextBuilder + GraphRAGPipeline |
| **Graph Engine** | Built | GraphIndexer, GraphEngine, SQLiteGraphBackend |
| **CognitiveWorker** | Template built | AbstractCognitiveWorker (1 subclass: MemoryCuratorWorker) |
| **Legacy Modules** | Operational | coding, web_search, knowledge, system_ctrl |

**Stack**: Python 3.11+, FastAPI, Ollama (local inference), SQLite.

---

## Target Users

- **Developers** building governed AI systems that need constitutional guarantees,
  not just prompt chains
- **Researchers** needing replayable cognitive architectures with full event-source
  audit trails
- **Teams** needing local-first AI infrastructure that keeps data on their machines

---

## Non-Goals

OCBrain deliberately does not attempt to be:
- A conversational chatbot or chat UI
- A thin wrapper around LLM APIs
- A retrieval-augmented generation framework
- A hosted cloud service or SaaS product
- A visual workflow builder or automation tool

---

## Architecture Era → Implementation Era

The Kernel Architecture v1.0 is frozen. The project is now entering the
**Implementation Era (K2)**, which will deliver:

- **ExecutionRuntime** — lifecycle management for cognitive workers
- **WorkflowRuntime** — DAG-based multi-worker orchestration
- **CapabilityRegistry** — dynamic tool and capability discovery
- **Governance completion** — remaining governors (ConcurrencyGovernor, QualityGovernor+)
- **MCP-native tools** — Model Context Protocol integration for tool interop
- **Self-improvement under governance** — workers that evolve within constitutional bounds

All K2 services will conform to the frozen public contracts defined in the architecture spec.

---

## Licensing

OCBrain is open-source and self-hosted. There are no pricing tiers, no cloud deployment
models, and no managed service offerings. You run it. You own it.
