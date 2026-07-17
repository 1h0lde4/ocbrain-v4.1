<img width="1536" height="1024" alt="a5c8335f-e65d-4698-a789-4e1c05752f22" src="https://github.com/user-attachments/assets/2830440e-a250-45ee-95f6-095530b7ddd1" />
# OCBrain

<div align="center">

**A local-first cognitive operating system**

[![Version](https://img.shields.io/badge/version-4.1-1d9e75?style=flat-square)](https://github.com/1h0lde4/OCBrain/releases)
[![Architecture](https://img.shields.io/badge/architecture-v1.0_frozen-blue?style=flat-square)](#architecture)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)

</div>

---

## Overview

OCBrain is a **governed, event-sourced intelligence runtime** with modular capabilities, autonomous reasoning under human oversight, and a replayable architecture. It runs locally, remembers persistently, reasons under governance, and explains its decisions.

> **The kernel coordinates; it does not own.**

OCBrain is not a chatbot, not an LLM wrapper, not a RAG framework, and not a cloud service. It is a substrate other intelligent systems are built on.

### Governing Documents

| Document | Purpose |
|---|---|
| [Kernel Constitution](OCBRAIN_KERNEL_CONSTITUTION.md) | Principles, laws, invariants — highest authority |
| [Kernel Architecture v1.0](KERNEL_ARCHITECTURE_v1.0.md) | Engineering specification — all contracts, ownership, dependencies |
| [Architecture Changelog](ARCHITECTURE_CHANGELOG.md) | Historical context for architecture decisions |
| [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md) | Operational engineering rules |

---

## Architecture

The Kernel Architecture v1.0 is **frozen**. All architectural contracts are stable. Implementation (K2) is next.

```
┌─────────────────────────────────────────────────────────┐
│                    Users (Sovereign)                     │
├─────────────────────────────────────────────────────────┤
│              Applications / Workflows                    │
│    (Compositions of capabilities — built ON OCBrain)     │
├─────────────────────────────────────────────────────────┤
│                    Capabilities                          │
│    (Schedulable units of work — Skills, Tools, MCP)      │
├──────────────┬──────────────────────────────────────────┤
│   Workers    │            Adapters                       │
│  (Cognitive  │  (Provider, Skill, MCP, Browser, API)    │
│   runtimes)  │                                          │
├──────────────┴──────────────────────────────────────────┤
│                   OCBrain Kernel                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Governance    Events    Registries    Execution  │   │
│  │                                       Workflow    │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Memory Service                       │   │
│  │  (UnifiedMemory, RetrievalContextBuilder, Graph)  │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│               Substrate (OS, Hardware)                   │
│            (Accessed ONLY through Adapters)              │
└─────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Status | Purpose |
|---|---|---|
| **GovernanceKernel** | Live | Constitutional governance enforcement. 7 governors: Recursion, Budget, Evolution, Orchestration, Agent, ConversationGuardrails, Memory. Template method makes bypass structurally impossible. |
| **EventStream** | Live | Immutable, append-only event log. SQLite WAL. Pub/sub, replay, checkpoints. |
| **UnifiedMemory** | Live | Canonical memory (L0 Working, L1 Episodic, L2 Semantic, L3 Procedural, L4 Archive). SQLite + FTS5 + BM25 + embeddings + graph index. |
| **ExecutionRuntime** | Live | Worker invocation, ExecutionContext lifecycle, failure containment. One worker per call, never raises. |
| **WorkflowRuntime** | Live | DAG-based multi-worker orchestration. Retry with exponential backoff. Lifecycle event emission. |
| **CapabilityRegistry + AdapterRuntime** | Live | Metadata-only capability index + execution with adapter selection, health-based ranking, and automatic fallback. 3 adapters for LLM_COMPLETION. |
| **AbstractCognitiveWorker** | Live | Template method pattern: governance → events → `_run()`. 2 subclasses (PlannerWorker, MemoryCuratorWorker). |
| **RetrievalContextBuilder + GraphRAGPipeline** | Live | Structured retrieval with provenance, contradiction detection, token budgeting. Graph-augmented retrieval. Production-wired. |
| **GraphIndexer + GraphEngine** | Live | Entity extraction, graph storage, neighbor traversal. SQLiteGraphBackend registered at startup. |

### Constitutional Principles

OCBrain is governed by 9 laws. The three most consequential for daily engineering:

1. **Bounded Autonomy** — No capability may exceed the governance wrapped around it
2. **Explicit State** — Nothing meaningful happens without leaving a trace (events)
3. **Separation of Concerns** — The kernel coordinates; it does not perform

See the full [Kernel Constitution](OCBRAIN_KERNEL_CONSTITUTION.md) for all 9 laws and 9 invariants.

---

## Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **Python** | 3.11 | 3.12 |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 10 GB | 50 GB |
| **Ollama** | Required | Latest |
| **OS** | Linux, macOS, Windows 10/11 | Linux |

---

## Installation

### Clone and Setup (Development)

```bash
git clone https://github.com/1h0lde4/ocbrain-v4.1.git
cd ocbrain-v4.1
pip install -r requirements.txt
```

### One-liner (Linux/macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/1h0lde4/OCBrain/main/install.sh | bash
```

### pip from GitHub

```bash
pip install git+https://github.com/1h0lde4/OCBrain.git@main
```

---

## Quick Start

### Step 1: Ensure Ollama is Running

```bash
ollama serve
ollama pull mistral
ollama pull nomic-embed-text
```

### Step 2: Start OCBrain

```bash
python main.py         # Starts on http://localhost:7437
```

### Step 3: Query

```bash
curl -X POST http://localhost:7437/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Write a Python function to reverse a string", "stream": false}'
```

Response:
```json
{
  "success": true,
  "answer": "...",
  "modules_used": ["coding"],
  "latency_ms": 1250
}
```

---

## API Reference

### Query

```
POST /query
Content-Type: application/json

{
  "query": "string (required)",
  "module": "string (optional, force specific module)",
  "stream": "boolean (default: false)",
  "context_turns": "integer (default: 5)"
}
```

### Status

```
GET /brain/v2/status

200 OK
{
  "status": "ok",
  "total_queries": 4217,
  "modules": { ... }
}
```

### Events (Server-Sent Events)

```
GET /brain/v2/events

200 OK (text/event-stream)
data: {"_event": "orchestrator.query_completed", ...}
```

### Streaming Response

```bash
curl -X POST http://localhost:7437/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Write a haiku", "stream": true}'
```

---

## Technical Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.11+ |
| **Web Server** | FastAPI + Uvicorn |
| **LLM Inference** | Ollama (local) |
| **Memory** | SQLite (WAL mode) + FTS5 |
| **Embeddings** | sentence-transformers (nomic-embed-text) |
| **Entity Extraction** | spaCy, RegexEntityExtractor |
| **Graph** | SQLiteGraphBackend |
| **Deduplication** | datasketch (MinHash) |
| **Events** | SQLite WAL (EventStream) |
| **Governance** | GovernanceKernel (3 live governors) |

---

## Project Structure

```
ocbrain-v4.1/
├── KERNEL_ARCHITECTURE_v1.0.md    # Canonical engineering specification
├── OCBRAIN_KERNEL_CONSTITUTION.md # Constitutional principles
├── ARCHITECTURE_CHANGELOG.md      # Architecture decision history
├── PROJECT_INSTRUCTIONS.md        # Engineering rules
├── K2_IMPLEMENTATION_PLAN.md      # Next phase plan
│
├── core/
│   ├── orchestrator.py            # Main query handler
│   ├── provider_mesh.py           # LLM provider selection & fallback
│   ├── governance/                # GovernanceKernel, Governors
│   ├── events/                    # EventStream (SQLite WAL)
│   ├── workers/                   # AbstractCognitiveWorker, MemoryCuratorWorker
│   ├── skills/                    # BaseSkill interface (MCP-ready)
│   ├── memory/                    # UnifiedMemory, graph, retrieval
│   │   ├── unified_memory.py      # Canonical memory (L0-L4)
│   │   ├── knowledge_entry.py     # KnowledgeEntry (canonical Resource)
│   │   ├── graph/                 # GraphIndexer, GraphEngine, SQLiteGraphBackend
│   │   └── retrieval/             # RetrievalContextBuilder, GraphRAGPipeline
│   ├── runtime/                   # State, limits, resilience
│   └── ...
│
├── modules/                       # Legacy expert modules (coding, web_search, knowledge, system_ctrl)
├── tests/                         # Test suites
├── docs/
│   ├── archive/                   # Historical K-session documents
│   └── reports/                   # Session reports
│
├── main.py                        # Composition root & entry point
└── config/                        # Configuration files
```

---

## Roadmap

### Architecture Era (Complete)

- ✅ K1 — Kernel Runtime Audit
- ✅ K1.5 — Kernel Runtime Specification
- ✅ K1.6 — Canonical Resource Model
- ✅ K1.7–K1.11 — Architecture Freeze
- ✅ K4 — Contract Freeze
- ✅ Kernel Architecture v1.0 Consolidation

### 🚩 Kernel Architecture v1.0 — Released

### Implementation Era (Next)

- **K2.1** — Execution Runtime (ExecutionContext, WorkerRegistry, ExecutionRuntime)
- **K2.2** — Workflow Runtime (WorkflowDefinition, DAG execution, checkpoints)
- **K2.3** — Capability Registry (CapabilityAdapter, resolution, adapter wrapping)
- **K2.4** — Governance Completion (MemoryGovernor reconciliation, new governors)
- **K3** — Kernel Validation & Compliance Audit

### Cognitive Phase (Future)

Self-Identity Model · Reflection Engine · Planning Engine · Skills Runtime · External Knowledge Pipeline · Multi-Agent Runtime · KAG · Web UI · Developer Platform

See [K2_IMPLEMENTATION_PLAN.md](K2_IMPLEMENTATION_PLAN.md) for detailed implementation planning.

---

## Contributing

OCBrain welcomes contributions. See [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md) for engineering standards.

### Key Areas

- **K2 Implementation** — ExecutionRuntime, WorkflowRuntime, CapabilityRegistry
- **Worker implementations** — New cognitive worker types
- **Capability adapters** — New adapters for external systems
- **Testing** — Integration tests, regression tests
- **Documentation** — Architecture deep-dives, tutorials

---

## License

OCBrain is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Support

- **Issues & Bugs**: [GitHub Issues](https://github.com/1h0lde4/ocbrain-v4.1/issues)
- **Discussions**: [GitHub Discussions](https://github.com/1h0lde4/ocbrain-v4.1/discussions)

---

**Local-first. Governed. Replayable. User-sovereign.**
