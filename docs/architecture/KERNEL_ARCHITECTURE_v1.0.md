# OCBrain — Kernel Architecture v1.0

**Status:** Frozen — Canonical engineering specification.
**Date:** July 10, 2026
**Authority:** Second-highest document in the project hierarchy. The Kernel Constitution governs principles; this document governs engineering.
**Scope:** Every architectural contract, ownership boundary, dependency rule, and public interface required for OCBrain kernel implementation. Nothing in this document is speculative — every claim is either verified against running code or explicitly marked as a K2 implementation target.

> **The kernel coordinates; it does not own.**

---

# 1. Introduction

OCBrain is a local-first cognitive operating system: a governed, event-sourced intelligence runtime with modular capabilities, autonomous reasoning under human oversight, and a replayable architecture.

This document is the single authoritative engineering specification for the OCBrain kernel. It consolidates and supersedes the individual findings of the K1 Kernel Audit, K1.5 Service Model, K1.6 Resource Model, and K1.7–K1.11 Architecture Freeze into one coherent reference. Those documents remain available as historical records (see `ARCHITECTURE_CHANGELOG.md`) but should no longer be consulted for current architectural decisions.

A new contributor should be able to understand the entire OCBrain architecture by reading two documents:

1. **The Kernel Constitution** — principles, laws, invariants, and admission tests.
2. **This document** — how those principles are realized as engineering.

---

# 2. Design Philosophy

OCBrain's architecture follows five core commitments, each traceable to the Constitution:

**Governance before capability.** Every autonomous action passes through governance evaluation before execution. Governance is attached at birth, not retrofitted.

**Evidence over assumption.** Architectural change is earned by evidence — prior implementation experience, convergent findings across independent systems, measured outcomes — not by novelty or preference. If a pattern cannot be justified against real precedent, it is deferred.

**Explicit over implicit.** State changes are represented as events. Dependencies are declared in constructors. Execution paths are inspectable. Hidden state, magic injection, and silent side effects are architectural failures.

**Coordinate, don't own.** The kernel owns abstractions; adapters own implementations. Capabilities perform work; the kernel schedules and governs it. Resources represent state; the kernel holds no meaningful state outside of resources.

**Local-first by default.** All architecture assumes local inference, local memory, local orchestration. Cloud services are optional accelerators, never core dependencies.

---

# 3. Constitutional Principles

The Kernel Constitution defines nine laws, nine invariants, a three-gate admission test, and a north star. This section summarizes their engineering implications — the Constitution itself remains the authoritative source for their full reasoning.

## 3.1 Laws

| # | Law | Engineering Implication |
|---|---|---|
| 1 | Bounded Autonomy | Every Worker's `execute()` wraps `_run()` inside `GovernanceKernel.evaluate_action()`. This is enforced structurally by the template method pattern — governance bypass is not a policy failure, it is a compilation failure. |
| 2 | Explicit State | Every meaningful transition emits an immutable `StreamEvent` to `EventStream`. Working Memory, governance decisions, and lifecycle changes are never silent mutations. |
| 3 | Separation of Concerns | The kernel coordinates; Workers execute; Adapters wrap external systems. The Orchestrator delegates to `ExecutionRuntime`, which delegates to Workers, which invoke Capabilities through Adapters. No layer does the work of another. |
| 4 | Determinism | Given the same intent and state, the kernel produces the same scheduling decisions. `ExecutionContext.causal_chain` enables full replay. Orchestration is deterministic even when individual model outputs are not. |
| 5 | User Sovereignty | The user owns everything OCBrain knows, decides, and does. Nothing is adopted, shared, or acted upon without visibility and consent. Local-first is the default. |
| 6 | Explainability | Every compiled execution plan carries its own justification as a first-class artifact. The kernel can state what it understood, how confident it is, and why — before and after acting. |
| 7 | Replaceability | Every capability has at least one alternative implementation that could replace it without changing the kernel's contract. `CapabilityAdapter` is a Protocol, not an ABC — any conforming object satisfies it. |
| 8 | Evidence over Assumption | Significant changes are justified against real precedent. A pattern five independent systems converged on is preferred over one adopted for being new. |
| 9 | Single Source of Truth | At any moment, there is exactly one authoritative answer to "what is actually true right now." When documentation and reality disagree, reality wins. |

Two additional laws from `PROJECT_INSTRUCTIONS.md` complement the Constitution:

| # | Law | Engineering Implication |
|---|---|---|
| 10 | Contract Stability | Existing stable interfaces are not broken to satisfy new ones. Changes go through deprecation windows. |
| 11 | Failure Containment | Execution failures never propagate as exceptions past the `ExecutionRuntime` boundary. Every failure becomes a `WorkerResult` with `success=False`. |

## 3.2 Invariants

1. The kernel does not act on intent it has not attempted to understand.
2. Every compiled execution plan can be inspected before it runs.
3. Every completed execution can be replayed and explained after it runs.
4. Every resource carries identity, lifecycle, and provenance.
5. Information crossing a kernel boundary is represented as an event.
6. Every capability has a defined contract more than one implementation could satisfy.
7. All user data remains under the user's authority by default.
8. External recommendations are never self-executing.
9. No single implementation detail is load-bearing for the kernel's definition of itself.

## 3.3 Non-Goals

OCBrain is not a chatbot, not an LLM wrapper, not a RAG framework, not a workflow automation tool, not an MCP implementation, not an autonomous agent free of governance, and not a cloud service. These may be built *on* OCBrain. They are not OCBrain itself.

---

# 4. System Overview

## 4.1 Runtime Model

OCBrain runs as a multi-process system:

```
Main Process
├── Orchestration (request coordination)
├── API (FastAPI/Uvicorn)
├── Workflow coordination
├── State transitions
└── Governance entrypoints

Worker Pool (future)
├── Workflow execution
├── Skill execution
├── Cognitive workers
└── Queue consumers

Webhook Process (future)
├── Event ingestion
├── Trigger handling
└── Async external events

Task Runner (future)
├── Sandboxed code execution
├── Isolated subprocess runtime
└── Restricted execution environment
```

Today, the Main Process handles all responsibilities. The Worker Pool, Webhook Process, and Task Runner are future separations that the architecture is designed to support without structural changes.

## 4.2 Request Flow

```
Request → Orchestrator
  → ExecutionRuntime.invoke() or WorkflowRuntime.execute()
    → WorkerRegistry.get(worker_type) → Worker instance
      → Worker.execute(context)
        → GovernanceKernel.evaluate_action()  [template method]
        → Worker._run(context)
          → CapabilityRegistry.resolve() → Adapter.invoke()
          → UnifiedMemory.search() / .write()
        → EventStream.append()  [lifecycle events]
      → WorkerResult
    → Result returned to caller
  → Orchestrator persists result, emits completion event
→ Response
```

---

# 5. Layered Architecture

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

| Layer | Responsibility |
|---|---|
| **Substrate** | Hardware, OS, network. The kernel never manages it directly — only through Adapters. |
| **OCBrain Kernel** | Scheduling, governance, event routing, resource lifecycle, capability resolution, intent validation. Owns abstractions, not implementations. |
| **Memory Service** | Canonical persistent store (UnifiedMemory), retrieval (RetrievalContextBuilder, GraphRAG), graph index. A kernel-internal service, not an external capability. |
| **Workers** | Cognitive runtimes executing governed, evented units of work. |
| **Adapters** | Translate one external system into the kernel's capability contract. Disposable and replaceable by design. |
| **Capabilities** | Units of schedulable work. May be backed by one adapter or composed of several. |
| **Applications / Workflows** | Compositions of capabilities assembled to satisfy intent. Built *on* OCBrain, never *as* OCBrain. |
| **Users** | Sovereign owner of data, policy, and final authority. |

---

# 6. Core Components

## 6.1 Kernel Services

The kernel comprises exactly nine services. Five exist and are live. Four are K2 implementation targets.

| Service | Status | Purpose |
|---|---|---|
| **GovernanceKernel** | Live | Evaluate actions against registered Governors before they proceed. Chain evaluation: first REJECT or ESCALATE terminates. Three governors active: `RecursionGovernor`, `BudgetGovernor`, `EvolutionGovernor`. |
| **EventStream** | Live | Immutable, append-only event log with pub/sub and replay. SQLite WAL-mode backend. Abstract `EventStore` interface for future migration. |
| **UnifiedMemory** | Live | Canonical read/write for all persistent memory (L0–L4). Storage, vector, graph, and archive backends. Public API: `write()`, `search()`, `update()`, `stats()`. |
| **HealthMonitor** | Live | Periodic system health checks. Background task, isolated from request path. |
| **ExecutionRuntime** | Live (K2.1) | Construct and invoke one Worker for one unit of work. Create ExecutionContext. Enforce execution boundaries. |
| **WorkflowRuntime** | Live (K2.2) | Coordinate a DAG of ExecutionRuntime invocations. Own retry logic, checkpoints, HITL gates, and execution transactions. |
| **CapabilityRegistry** | Live (K2.3) | Static index of Capabilities and their Adapters. Populated at startup, read-only after initialization. |
| **CapabilityResolver** | Live (K2.3) | Stateless runtime selection of which Adapter satisfies a request (implemented as `AdapterRuntime`). Health/cost/latency scoring. |
| **WorkerRegistry** | Live (K2.1) | Index of constructable Worker types. Populated at startup, read-only after initialization. |

### Explicitly Rejected Services

| Rejected | Reason |
|---|---|
| Scheduler | `asyncio.gather()` is sufficient at current scale. Justified only when distributed/queue-mode execution is real. |
| ServiceLocator / DI Container | Current explicit constructor injection is correct. A container would trade inspectable wiring for implicit resolution — a Law 4 regression. |
| MetricsCollector | Folds into EventStream. A separate collector would create a second source of truth. |
| RecoveryManager | Recovery is a responsibility of ExecutionRuntime/WorkflowRuntime, not an independent service. |
| StateManager | `core/runtime/state.py` already handles this. Extend it, don't duplicate it. |

## 6.2 Composition Root

`main.py` is the composition root — the single location where all services are constructed, wired together, and injected. All dependency injection is explicit constructor injection (no magic, no containers, no service locators). Every service receives its dependencies through its constructor, defaulting to singleton getters only for backward compatibility.

---

# 7. Execution Model

## 7.1 ExecutionRuntime

The service that constructs and invokes one Worker for one unit of work.

**Owns:** Worker instantiation (via WorkerRegistry), ExecutionContext creation and propagation, Working Memory allocation and cleanup, failure containment at the single-execution level, cancellation propagation.

**Does not own:** Multi-step coordination (WorkflowRuntime), retries across executions (WorkflowRuntime), worker implementation (Worker subclass), governance evaluation (handled by Worker's template method).

**Lifecycle:**

```
invoke(worker_type, context) called
  → WorkerRegistry.get(worker_type) → Worker class
  → Construct Worker instance (DI: governance, event_stream)
  → Allocate Working Memory in context
  → Worker.execute(context)
  → Capture WorkerResult
  → Clean up Working Memory
  → Return WorkerResult (never raises)
```

**Failure model:** Execution failures never propagate as exceptions. Every failure becomes a `WorkerResult(success=False)`. Resolution errors (unregistered worker type, construction failure) also produce `WorkerResult(success=False)` without entering the Worker lifecycle.

**Contract:**

```python
class ExecutionRuntime:
    async def invoke(self, worker_type: str,
                     context: ExecutionContext) -> WorkerResult: ...
```

## 7.2 ExecutionContext

The data object threading through one execution. Replaces the earlier `WorkerContext` prototype (see ADR-001 in §21).

```python
@dataclass
class ExecutionContext:
    request_id: str               # Unique per request (UUID)
    worker_id: str                # Assigned by ExecutionRuntime
    session_id: str               # Correlates related requests
    causal_chain: List[str]       # Parent execution IDs for replay
    working_memory: WorkingMemory # Scoped scratch space
    governance_state: Dict[str, Any]  # Budget counters, step counts, recursion depth
    cancellation_token: CancellationToken  # Cooperative cancellation
    workflow_id: str = ""         # Set by WorkflowRuntime if in a workflow
    parent_worker_id: str = ""    # Set if invoked by SupervisorWorker
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Immutability:** All fields are set at creation except Working Memory, which is mutable during execution. Fields are additive-only across versions — no field will be removed.

## 7.3 Working Memory

L0 — in-process, per-execution scratch space (PI §8.1).

- **Ownership:** Created by ExecutionRuntime at invocation. Readable/writable by the Worker during execution. Cleaned up after execution completes.
- **Scope:** Per-execution. Never persists across requests. Long-term persistence is UnifiedMemory's responsibility.
- **Contents:** Key-value store. The retrieval `Context` (from `RetrievalContextBuilder`) is one entry. Worker scratch data is another.
- **Design decision:** Working Memory holds `RetrievalContextBuilder`-shaped `Context` objects (with `ContextBlock`, `ContradictionGroup`, `ProvenanceRecord`), not flat `List[SearchResult]`. The sophisticated, structured retrieval path is the canonical one.

## 7.4 CancellationToken

Cooperative cancellation mechanism. Workers check `context.cancellation_token.is_cancelled` periodically in `_run()` and exit gracefully. Timeouts are cancellations triggered by timers — no separate mechanism.

```python
class CancellationToken:
    def cancel(self) -> None: ...
    @property
    def is_cancelled(self) -> bool: ...
    async def wait(self, timeout: float = None) -> bool: ...
```

## 7.5 State Transitions

Worker states (already defined in `core/workers/base.py`):

```
IDLE → RUNNING → COMPLETED
               → FAILED
               → CANCELLED
     → PAUSED (reserved for HITL — not yet exercised)
```

No states added. No states removed.

---

# 8. Workflow Model

## 8.1 Core Concepts

**WorkflowDefinition:** A reusable, versioned template describing a DAG of nodes. Declarative — no execution state.

```python
@dataclass
class WorkflowDefinition:
    workflow_id: str
    version: str                   # SemVer
    name: str
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**WorkflowNode:** One step in the DAG.

```python
@dataclass
class WorkflowNode:
    node_id: str
    node_type: str                 # "worker", "capability", "approval", "checkpoint"
    worker_type: str = ""
    capability_id: str = ""
    retry_policy: Optional[RetryPolicy] = None
    timeout_seconds: float = 300.0
    error_branch: str = ""         # Node to jump to on failure
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**RetryPolicy:**

```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_base_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 60.0
    retryable_errors: List[str] = field(default_factory=list)
```

**WorkflowInstance:** One execution of a WorkflowDefinition. Carries mutable state.

**WorkflowState:** `PENDING → RUNNING → COMPLETED | FAILED | CANCELLED | WAITING_APPROVAL`

## 8.2 WorkflowRuntime

Coordinates a DAG of ExecutionRuntime invocations.

**Owns:** WorkflowInstance lifecycle, node sequencing (topological order), retry logic (per-node RetryPolicy), checkpoint/resume (via EventStream), HITL approval gates, execution transactions.

**Contract:**

```python
class WorkflowRuntime:
    async def execute(self, definition: WorkflowDefinition,
                      context: ExecutionContext) -> WorkflowResult: ...
    async def resume(self, instance_id: str) -> WorkflowResult: ...
    async def cancel(self, instance_id: str) -> None: ...
```

**Execution flow:**

```
execute(definition, context)
  ├─ Create WorkflowInstance, emit "workflow.started"
  ├─ For each node in topological order:
  │   ├─ If approval node: emit event, suspend, checkpoint
  │   ├─ If checkpoint node: create EventStream checkpoint
  │   ├─ If worker/capability node:
  │   │   ├─ ExecutionRuntime.invoke(worker_type, context)
  │   │   ├─ On failure + retries available: retry with backoff
  │   │   ├─ On failure + retries exhausted + error_branch: jump
  │   │   └─ On failure + retries exhausted + no branch: workflow FAILED
  │   └─ Emit "workflow.node.completed"
  └─ Emit "workflow.completed", return WorkflowResult
```

**Transaction semantics:** One WorkflowInstance = one transaction. No automatic rollback — failed workflows are marked FAILED, completed node results are preserved. Compensating actions are future work (see ADR-005 in §21).

**Retry ownership:** WorkflowRuntime owns retries at the node level. ExecutionRuntime performs exactly one attempt. Workers never retry internally. `BaseSkill._execute_with_retries()` is capability-level retry (retrying one LLM call within a skill) — a different, non-overlapping granularity.

---

# 9. Worker Model

## 9.1 AbstractCognitiveWorker

The base class for all cognitive workers. Uses the template method pattern to make governance bypass structurally impossible.

**Public API (non-overridable):**

```python
async def execute(self, context: ExecutionContext) -> WorkerResult:
    # 1. GovernanceKernel.evaluate_action() — BEFORE any work
    # 2. Emit "worker.started" event
    # 3. Call _run(context) — subclass implementation
    # 4. Emit "worker.completed" or "worker.failed" event
    # 5. Return WorkerResult
```

**Subclass contract (the only extension point):**

```python
@abstractmethod
async def _run(self, context: ExecutionContext) -> WorkerResult: ...
```

**Instance lifecycle:** Workers are ephemeral — a new instance is created per `ExecutionRuntime.invoke()` call. No state persists across invocations (see ADR-003 in §21).

**Execution boundary:** Each Worker sees only its own Working Memory and ExecutionContext. It cannot see other concurrent executions. It cannot bypass governance.

**Communication:** Workers do not communicate directly. They communicate through Working Memory (within a workflow), EventStream (observable events), and WorkflowRuntime (sequential node results).

## 9.2 Worker vs. Capability

| Property | Worker | Capability |
|---|---|---|
| What it does | Cognitive orchestration — decides what to do, coordinates | Atomic work — performs one specific action |
| Who calls it | ExecutionRuntime | Workers (through Adapters) |
| Governance | Self-governing (template method) | Governed by the calling Worker's context |
| State | Has lifecycle (IDLE → RUNNING → COMPLETED) | Stateless per invocation |
| Examples | PlannerWorker, EvaluatorWorker, MemoryCuratorWorker | inference, web_search, code_execution |

## 9.3 Canonical Worker Types

| Worker | Status | Responsibility | K2 Priority |
|---|---|---|---|
| **MemoryCuratorWorker** | Implemented, wired (K2.1) | Active memory improvement — prune, strengthen, derive, resolve contradictions | K2.1 |
| **PlannerWorker** | Implemented, production-wired (K2.2) | Canonical workflow entry worker — classify, dispatch, merge | K2.1 |
| **ReflectionWorker** | Not built | Evaluate and critique the system's own outputs | Cognitive Phase |
| **EvaluatorWorker** | Not built | Score/grade outputs against criteria | Cognitive Phase |
| **SupervisorWorker** | Not built | Coordinate multiple sub-workers via ExecutionRuntime | Cognitive Phase |
| **CoderWorker** | Not built | Code generation, modification, analysis (sandboxed) | Cognitive Phase |
| **BrowserWorker** | Not built | Web browsing, content extraction | Cognitive Phase |

---

# 10. Capability Model

## 10.1 Taxonomy

Every entity that "does work" falls into exactly one category:

| Concept | Definition | Examples |
|---|---|---|
| **Capability** | Abstract, schedulable unit of work defined by its contract | "inference", "web_search", "code_execution" |
| **Adapter** | Concrete implementation satisfying a Capability's contract | `OllamaProvider`, `GenericOpenAICompatibleProvider` |
| **Provider** | Sub-type of Adapter scoped to inference | Ollama, OpenAI-compatible endpoints |
| **Skill** | A Capability whose Adapter is local code | `BaseSkill` subclasses |
| **Tool** | A Skill exposed externally via MCP | Same underlying object, MCP-facing name |
| **Module** | **Legacy term — being phased out.** Replaced by Skill/Capability. | Expert modules in `modules/` |

## 10.2 CapabilityAdapter Protocol

```python
class CapabilityAdapter(Protocol):
    @property
    def capability_id(self) -> str: ...
    @property
    def adapter_id(self) -> str: ...
    @property
    def is_available(self) -> bool: ...
    @property
    def health_score(self) -> float: ...
    async def invoke(self, request: Dict[str, Any],
                     context: ExecutionContext) -> Dict[str, Any]: ...
    def mark_success(self) -> None: ...
    def mark_failure(self) -> None: ...
```

**Protocol, not ABC.** The existing `Provider` class already has `is_available`, `health_score`, `mark_success()`, `mark_failure()`. Using a Protocol lets Provider satisfy `CapabilityAdapter` with minimal wrapping, without changing its inheritance chain (see ADR-002 in §21).

## 10.3 CapabilityRegistry

Static index of what Capabilities and their Adapters exist. Populated at startup from: `provider_mesh.py`'s Provider subclasses (inference adapters), future `BaseSkill` implementations (skill adapters), future MCP tool configurations (MCP adapters).

```python
class CapabilityRegistry:
    def register(self, capability_id: str, adapter: CapabilityAdapter) -> None: ...
    def resolve(self, capability_id: str) -> List[CapabilityAdapter]: ...
    def list_capabilities(self) -> List[str]: ...
```

## 10.4 CapabilityResolver

Stateless runtime function that picks which Adapter satisfies a request. Generalizes the existing health-tracking pattern in `provider_mesh.py`.

```python
class CapabilityResolver:
    def select(self, candidates: List[CapabilityAdapter],
               context: ExecutionContext) -> CapabilityAdapter: ...
```

Selection criteria (ordered): health score → availability → cost (future). Raises `CapabilityUnavailableError` if no candidate is healthy.

---

# 11. Resource Model

## 11.1 The Resource Protocol

`Resource` is a `Protocol` (structural typing), not an ABC. This lets existing types like `KnowledgeEntry` satisfy it without changing their class declaration.

**Required fields:**

| Field | Purpose | Evidence |
|---|---|---|
| `resource_id` | Unique identity (UUID) | `KnowledgeEntry.entry_id` — real, load-bearing |
| `created_at` | Creation timestamp | Required by memory-scoring recency decay |
| `updated_at` | Last modification timestamp | Mutable resources must express when they last changed |
| `owner` | Which service is authoritative for mutation | Structural field, not trust |
| `lifecycle_state` | Current lifecycle position | Domain-specific per type (not a universal enum) |
| `version` | SemVer (optional) | Needed for Capability/Workflow resources, not for KnowledgeEntry |
| `metadata` | Free-form dict (escape hatch, not a design tool) | `WorkerContext.metadata` precedent |

**Required methods:** `to_dict() -> Dict`, `from_dict(d: Dict) -> Resource`

## 11.2 Resource Taxonomy

| Object | Satisfies Resource? | Reason |
|---|---|---|
| `KnowledgeEntry` | **Yes** | Independent identity, real lifecycle (`TRUTH_STATUS`), persisted |
| Future `CapabilityMetadata` | **Yes** | Identity, lifecycle, version, dependencies |
| Future `WorkflowInstance` | **Yes** | Identity and lifecycle tracked over long-running execution |
| `Evidence` / `EvidenceSet` | **No** | Wraps a Resource — duplicating identity would create a second source of truth |
| `Context` / `ContextBlock` / `ProvenanceRecord` | **No** | Deliberately storage-decoupled projections, by design |
| `WorkerContext` / `ExecutionContext` | **No** | Ephemeral per-call parameters |
| `StreamEvent` | **No** | Immutable, write-once, causally ordered — not lifecycle-ordered |
| Graph nodes | **No** | Index entries pointing at KnowledgeEntry identity, not independent resources |

## 11.3 Lifecycle Model

The Protocol requires that a `lifecycle_state` field exists and that every transition is evented. It does **not** mandate what the state values are. Each Resource type owns its own lifecycle enum:

- `KnowledgeEntry`: `unknown → candidate → verified → conflicted → deprecated`
- Future `CapabilityMetadata`: `draft → registered → active → deprecated`
- Future `WorkflowInstance`: `pending → running → completed | failed`

## 11.4 Identity Model

Standard convention: UUID-based, using `field(default_factory=lambda: str(uuid.uuid4()))`. Cross-resource references are always by ID string, never by embedding a live object.

## 11.5 Relationship Model

`KnowledgeEntry.contradicts[]` / `.supports[]` / `.supersedes[]` establish typed relationships by ID reference. Cycles are forbidden in ownership and dependency edges but explicitly allowed and meaningful in contradiction/support edges (contradiction detection requires finding cycles).

---

# 12. Memory Architecture

## 12.1 Layer Model

| Layer | Name | Purpose | Implementation |
|---|---|---|---|
| **L0** | Working Memory | In-process, per-execution scratch space | `WorkingMemory` (key-value store in ExecutionContext) |
| **L1** | Episodic Memory | Events and observations | SQLite + FTS5 |
| **L2** | Semantic Memory | Facts and concepts | BM25 + embeddings (InMemoryVectorBackend, persistence at v4.5.3) |
| **L3** | Procedural Memory | Skills, workflows, procedures | GraphIndexer + GraphEngine |
| **L4** | Archive Memory | Immutable audit log, provenance | SQLite (append-only) |

## 12.2 UnifiedMemory

Canonical memory service. Single instance, constructed at the composition root.

**Public API (frozen):**

```python
class UnifiedMemory:
    async def write(self, content: str, content_type: str, source: str,
                    importance: float, entry_id: str = None,
                    metadata: Dict = None, truth_status: str = None) -> str: ...
    async def search(self, query: str, limit: int = 5,
                     content_type: str = None) -> List[SearchResult]: ...
    async def update(self, entry_id: str, updates: Dict) -> bool: ...
    def stats(self) -> Dict[str, Any]: ...
```

**Forbidden direct access:** Nothing above the Memory Service layer may touch `._storage`, `._vector`, `._graph`, or `._archive` backends directly.

## 12.3 KnowledgeEntry

The canonical memory unit (what the system knows). Mutable — updated in place as knowledge evolves.

**Key fields:** `entry_id`, `layer`, `content`, `summary`, `importance`, `confidence`, `truth_status`, `trust_score`, `source`, `worker_id`, `workflow_id`, `derived_from`, `supports`, `contradicts`, `supersedes`, `graph_node_id`, `tags`, `metadata`.

**Truth status vocabulary:** `unknown` (default) → `candidate` (trusted source, not cross-validated) → `verified` (confirmed by multiple sources) → `conflicted` (contradicts verified entries) → `deprecated` (superseded, retained for provenance).

**Graph eligibility:** Only `verified` and `candidate` entries get graph nodes.

## 12.4 Graph Architecture

The graph is an index over Memory, not a storage layer.

- **GraphIndexer:** Manages eligibility, extraction, sync, and removal of graph nodes. Uses `TruthStatusEligibilityPolicy` (only graph-eligible entries get nodes) and configurable `EntityExtractor` (default `NullEntityExtractor`; `RegexEntityExtractor` enabled at composition root).
- **GraphEngine:** Entity/relationship storage in SQLite. Supports node creation, edge creation, neighbor traversal, and subgraph extraction.
- **SQLiteGraphBackend:** Production backend registered at startup.

---

# 13. Retrieval Architecture

Two retrieval stacks exist. The sophisticated one is canonical.

## 13.1 Canonical Stack (Live — production retrieval path since K2.2)

**RetrievalContextBuilder** produces structured `Context` objects:
- `ContextBlock`: Storage-decoupled projection of a KnowledgeEntry with provenance
- `ContradictionGroup`: Detected conflicts between entries
- `ProvenanceRecord`: Source, trust, confidence metadata
- Token budgeting, MinHash deduplication

**GraphRAGPipeline** provides graph-augmented retrieval:
- `IntentAnalyzer`: Extracts entities and intent from queries
- `TraversalStrategy`: Pluggable graph traversal patterns
- `RankingStrategy`: Pluggable result scoring

Both are fully built, fully tested (64K of test code), and currently disconnected from the live path.

## 13.2 Legacy Stack (live today, to be superseded)

**RetrievalFusionEngine** delegates to `UnifiedMemory.search()` and returns a flat `List[SearchResult]` — no structure, no provenance, no contradiction handling. Called from `ContextAssemblyEngine`, called from `Orchestrator.handle()`.

**K2 migration:** Replace `RetrievalFusionEngine` with `RetrievalContextBuilder` in the live path. Run A/B comparison before cutover.

---

# 14. Governance

## 14.1 GovernanceKernel

Central enforcement point. All autonomous actions pass through `evaluate_action()` before proceeding. Governors are evaluated in registration order — the first REJECT or ESCALATE terminates evaluation.

```python
class GovernanceKernel:
    def register_governor(self, governor: Governor) -> None: ...
    def evaluate_action(self, action: GovernanceAction) -> GovernanceResult: ...
    def stats(self) -> Dict[str, Any]: ...
```

## 14.2 GovernanceAction

Structured description of an action to be evaluated:

```python
@dataclass
class GovernanceAction:
    action_type: str                # "worker_execute", "memory_write", etc.
    worker_id: str
    description: str
    resource_cost: float = 0.0
    recursion_depth: int = 0
    requires_approval: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

## 14.3 Governors

| Governor | Status | Purpose |
|---|---|---|
| **RecursionGovernor** | Live | Prevents runaway recursive loops (depth > 10 → REJECT) |
| **BudgetGovernor** | Live | Enforces per-workflow step and token budgets (carried in `GovernanceAction.metadata`) |
| **EvolutionGovernor** | Live | Controls self-modifying actions (`memory_curate`, `skill_create`, etc.). HITL escalation when `requires_approval` is set. |
| **MemoryGovernor** | Live (K2.4) | Reconciled with `Governor` base class. Validates memory ingestion quality. Registered in GovernanceKernel. No production call site yet constructs `action_type="memory_write"`. |
| **OrchestrationGovernor** | Live (K2.4) | Authorizes which worker types may execute. Permissive default (empty deny list). |
| **AgentGovernor** | Live (K2.4) | Per-call resource ceiling and delegation permission matrix. Permissive default. |
| **ConversationGuardrails** | Live (K2.4) | Session-level content policy via denylist. Permissive default (empty denylist). |

## 14.4 Verdicts

```python
class GovernanceVerdict(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"  # Requires human-in-the-loop approval
```

---

# 15. Event Architecture

## 15.1 EventStream

Immutable, append-only event log with pub/sub and replay. SQLite WAL-mode backend.

```python
class EventStream:
    async def append(self, event_type: str, *, source: str = "",
                     payload: Dict = None, checkpoint: str = "") -> StreamEvent: ...
    async def query(self, **kwargs) -> List[StreamEvent]: ...
    async def replay(self, since_sequence: int = 0) -> AsyncIterator[StreamEvent]: ...
    async def create_checkpoint(self, name: str,
                                payload: Dict = None) -> StreamEvent: ...
    async def get_checkpoint(self, name: str) -> Optional[StreamEvent]: ...
```

## 15.2 StreamEvent

Immutable record (frozen dataclass):

```python
@dataclass(frozen=True)
class StreamEvent:
    event_id: str       # UUID
    event_type: str     # e.g. "worker.started", "workflow.node.completed"
    source: str         # Originating component
    timestamp: float    # Unix epoch
    payload: Dict       # Structured data
    checkpoint: str     # Optional checkpoint name
    sequence: int       # Monotonically increasing (set by EventStore)
```

## 15.3 Event Taxonomy

| Event Type | Emitter | When |
|---|---|---|
| `worker.started` | Worker | `execute()` begins |
| `worker.completed` | Worker | `_run()` succeeds |
| `worker.failed` | Worker | `_run()` raises |
| `worker.cancelled` | Worker | CancellationToken triggered |
| `worker.rejected` | Worker | Governance REJECT |
| `worker.escalated` | Worker | Governance ESCALATE |
| `worker.progress` | Worker | During `_run()` |
| `orchestrator.query_started` | Orchestrator | Request received |
| `orchestrator.query_completed` | Orchestrator | Request finished |
| `orchestrator.query_failed` | Orchestrator | Request error |
| `workflow.started` | WorkflowRuntime | DAG begins |
| `workflow.node.started` | WorkflowRuntime | Node begins |
| `workflow.node.completed` | WorkflowRuntime | Node finishes |
| `workflow.completed` | WorkflowRuntime | DAG finishes |
| `system.checkpoint` | EventStream | Durable checkpoint |

## 15.4 EventBus Relationship

`EventBus` (`core/event_bus.py`) is an in-process pub/sub system without persistence. `EventStream` is the durable source of truth. EventBus subscribes to EventStream for in-process fan-out delivery — events are not emitted to both independently (see ADR-006 in §21).

---

# 16. Dependency Rules

## 16.1 Dependency Graph

```
Layer 0: Governance & Events (no dependencies on other kernel services)
Layer 1: Registries (no runtime dependencies)
Layer 2: Execution (depends on: Registries, Governance, Events)
Layer 3: Workers (depends on: Governance, Events, Registries)
Layer 4: Capabilities (depends on: external systems via Adapters)
Layer 5: Memory (depends on: storage backends)
Layer 6: External Systems
```

## 16.2 Allowed Dependencies

| From | To | Relationship |
|---|---|---|
| Worker → CapabilityAdapter | Uses | Workers invoke capabilities to do work |
| Worker → UnifiedMemory | Uses | Workers read/write memory via public API |
| Worker → GovernanceKernel | Uses | Template method pattern |
| Worker → EventStream | Uses | Template method pattern |
| ExecutionRuntime → WorkerRegistry | Uses | Runtime resolves worker types |
| WorkflowRuntime → ExecutionRuntime | Uses | Workflow dispatches to execution |

## 16.3 Forbidden Dependencies

| From | To | Reason |
|---|---|---|
| CapabilityAdapter → UnifiedMemory | **Forbidden** | Adapters wrap external systems, not kernel services |
| CapabilityAdapter → Worker | **Forbidden** | Inverts direction — capabilities must be callable by any worker |
| UnifiedMemory → WorkflowRuntime | **Forbidden** | Creates cycle |
| UnifiedMemory → ExecutionRuntime | **Forbidden** | Memory is used by Workers, not by the runtime |
| GovernanceKernel → Worker | **Forbidden** | Governance evaluates, doesn't invoke |
| EventStream → Worker | **Forbidden** | Events are emitted by workers, not consumed to trigger them |

---

# 17. Ownership Model

Every component has exactly one canonical owner. No shared ownership.

| Component | Owner | Creates | Destroys |
|---|---|---|---|
| GovernanceKernel | Composition Root | Composition Root | Process exit |
| EventStream | Composition Root | Composition Root | Process exit |
| UnifiedMemory | Composition Root | Composition Root | Process exit |
| ExecutionRuntime | Composition Root | Composition Root | Process exit |
| WorkflowRuntime | Composition Root | Composition Root | Process exit |
| CapabilityRegistry | Composition Root | Composition Root | Process exit |
| WorkerRegistry | Composition Root | Composition Root | Process exit |
| ExecutionContext | ExecutionRuntime | `invoke()` | Post-execution cleanup |
| WorkingMemory | ExecutionContext | ExecutionRuntime | Post-execution cleanup |
| WorkflowInstance | WorkflowRuntime | `execute()` | Completion/failure |
| Worker instance | ExecutionRuntime | `invoke()` | GC after invoke returns |
| KnowledgeEntry | UnifiedMemory | `write()` | Archive to L4 (never true delete) |
| StreamEvent | EventStream | `append()` | Never (immutable, append-only) |

---

# 18. Public Contracts

These interfaces are frozen. Changes are additive only (new optional parameters, new methods). Removals require a deprecation window.

## 18.1 Already Stable (Live)

| Contract | Method | Guarantee |
|---|---|---|
| `UnifiedMemory` | `write()`, `search()`, `update()`, `stats()` | Signature stable. Internal backends are not public. |
| `GovernanceKernel` | `evaluate_action()`, `register_governor()`, `stats()` | Signature stable. |
| `EventStream` | `append()`, `query()`, `replay()`, `create_checkpoint()` | Signature stable. |
| `AbstractCognitiveWorker` | `execute()` (non-overridable), `_run()` (extension point) | Template method pattern is permanent. |
| `Governor` | `evaluate(action) -> GovernanceResult` | Signature stable. |

## 18.2 K2 Implementation Targets

| Contract | Method | Guarantee |
|---|---|---|
| `ExecutionRuntime` | `invoke(worker_type, context) -> WorkerResult` | Signature frozen at specification. |
| `WorkflowRuntime` | `execute()`, `resume()`, `cancel()` | Signature frozen at specification. |
| `CapabilityRegistry` | `register()`, `resolve()`, `list_capabilities()` | Signature frozen at specification. |
| `CapabilityResolver` | `select(candidates, context) -> CapabilityAdapter` | Signature frozen at specification. |
| `WorkerRegistry` | `get(worker_type) -> Type[AbstractCognitiveWorker]` | Signature frozen at specification. |

---

# 19. Extension Points

The architecture is extended at exactly these points — nowhere else:

| Extension | Mechanism | Example |
|---|---|---|
| New Worker type | Subclass `AbstractCognitiveWorker`, register in `WorkerRegistry` | `PlannerWorker` |
| New Capability | Implement `CapabilityAdapter` Protocol, register in `CapabilityRegistry` | Browser adapter |
| New Governor | Subclass `Governor`, register in `GovernanceKernel` | `OrchestrationGovernor` |
| New Workflow node type | Add to `WorkflowNode.node_type` vocabulary | Custom approval gates |
| New EventStore backend | Implement `EventStore` ABC | Redpanda at v4.5.5 |
| New Memory backend | Implement and register via `UnifiedMemory.register_graph_backend()` | Future persistent vector store |
| New Entity Extractor | Implement `EntityExtractor` interface | LLM-based entity extraction |

**Kernel Admission Test (Constitution Part V):** Any new addition to the kernel itself (not a Worker, Adapter, or Governor) must pass three gates — Necessity, Placement, and Durability — and the test is re-applied periodically to existing kernel contents.

---

# 20. Implementation Constraints

## 20.1 Immutable Rules

1. **No inline execution** of generated code. All code execution is sandboxed (subprocesses, containers, restricted environments).
2. **No hidden framework behavior.** No magic dependency injection, no implicit orchestration, no uncontrolled abstractions.
3. **No singleton abuse.** Singletons exist only for backward compatibility. New services receive dependencies through constructors.
4. **No cross-layer direct access.** Workers never touch UnifiedMemory internals. Adapters are never imported above the Capability layer.
5. **Event emission failure is non-fatal.** Events are logged but never block execution.
6. **Write failures are non-blocking.** Memory write failures are caught and logged, never crash the request path.

## 20.2 K2 Implementation Files

| K2 Milestone | New Files | Modified Files |
|---|---|---|
| K2.1 — Execution Runtime | `core/runtime/execution_context.py`, `core/runtime/cancellation.py`, `core/runtime/working_memory.py`, `core/runtime/execution_runtime.py`, `core/runtime/worker_registry.py`, `core/workers/planner.py` | `core/workers/base.py`, `core/orchestrator.py`, `main.py` |
| K2.2 — Workflow Runtime | `core/workflow/definition.py`, `core/workflow/instance.py`, `core/workflow/runtime.py`, `core/workflow/result.py` | `core/memory/assembly.py` |
| K2.3 — Capability Registry | `core/capabilities/adapter.py`, `core/capabilities/registry.py`, `core/capabilities/resolver.py` | `core/provider_mesh.py` |
| K2.4 — Governance Completion | `core/governance/orchestration_governor.py`, `core/governance/agent_governor.py`, `core/governance/conversation_guardrails.py` | `core/governance/memory_governor.py` |

**Totals:** 16 new files, 6 modified files, ~40+ files intentionally untouched.

---

# 21. Architecture Decision Summary

## ADR-001: ExecutionContext Replaces WorkerContext

`ExecutionContext` is the canonical execution parameter object. `WorkerContext` is deprecated. Both served the same purpose; maintaining two context objects violates Single Source of Truth. `ExecutionContext`'s name matches its ownership (created by ExecutionRuntime, not by Workers). Zero live consumers break — `MemoryCuratorWorker` is never instantiated in production.

## ADR-002: CapabilityAdapter as Protocol, Not ABC

`CapabilityAdapter` is a `Protocol` (structural typing). The existing `Provider` class already has the right shape (`is_available`, `health_score`, `mark_success()`, `mark_failure()`). A Protocol lets it satisfy `CapabilityAdapter` without changing its inheritance chain. Weaker compile-time guarantees than an ABC, accepted because runtime duck-typing is standard Python practice and Protocol provides static-analysis support via mypy.

## ADR-003: Workers Are Ephemeral

Worker instances are created per `ExecutionRuntime.invoke()` call and do not persist across invocations. Singleton workers accumulate hidden state across calls, violating Explicit State. Construction is cheap (`O(1)` Python allocation + DI).

## ADR-004: WorkflowRuntime Owns Retries

Retry logic lives in WorkflowRuntime (per-node RetryPolicy), not in Workers or ExecutionRuntime. Workers shouldn't know about infrastructure concerns. A single `invoke()` does exactly one attempt — implicit retries would be hidden side effects violating Determinism.

## ADR-005: No Automatic Rollback in K2

WorkflowRuntime marks failed workflows as FAILED but does not automatically undo completed nodes. Most cognitive operations (inference, memory reads, analysis) don't have meaningful inverses. Compensating actions can be added as explicit error-branch nodes in the workflow DAG for specific use cases.

## ADR-006: EventBus Subscribes to EventStream

All events go through `EventStream.append()` (durable, ordered). `EventBus` subscribes to EventStream for in-process fan-out. This preserves EventStream as the single source of truth while keeping EventBus's low-latency delivery for in-process consumers.

## ADR-007: Resource as Protocol

`Resource` is a `Protocol`, not an ABC. This lets `KnowledgeEntry` satisfy it without changing its class declaration, preserving Contract Stability. Only objects with genuine independent identity, lifecycle, and persistence satisfy Resource. Projections (`Context`, `Evidence`), ephemeral parameters (`ExecutionContext`), and index entries (graph nodes) are explicitly excluded.

## ADR-008: Per-Type Lifecycle Enums

The Resource Protocol requires a `lifecycle_state` field but does not mandate the values. Each Resource type owns its own lifecycle enum. A universal twelve-state machine was rejected as unproven — zero evidence exists for Fork, Merge, or Snapshot as resource operations in this codebase.

---

# 22. Future Evolution

## 22.1 What Can Change Without Amending This Document

- New Worker types (additive)
- New Capability adapters (additive)
- New Governors (additive)
- New EventStore backends (additive)
- Internal implementation changes within any service
- New optional fields on data objects

## 22.2 What Requires Updating This Document

- New kernel services (must pass Admission Test)
- Changes to public contract signatures
- Changes to dependency rules
- Changes to ownership boundaries
- New architectural layers

## 22.3 What Requires Amending the Constitution

- Changes to Laws or Invariants
- Changes to the Admission Test
- Changes to Non-Goals

## 22.4 Deferred Architecture

| Item | Reason for Deferral |
|---|---|
| Distributed/queue-mode execution | Years out; `asyncio.gather` sufficient |
| Automatic compensating actions (saga) | No proven need; cognitive operations are mostly non-reversible |
| Hot-reload of capabilities | Cognitive Phase concern |
| Self-Identity Model | Cognitive Phase |
| Collective Intelligence | No external input exists yet |
| Persistent L2 vector storage | Tracked at v4.5.3 |
| Redpanda EventStore backend | Tracked at v4.5.5 |
| Durable cross-restart workflow execution | Checkpoint infrastructure designed; full durability is K3+ |

---

# 23. Canonical Roadmap

## Architecture Phase (Complete)

- ✅ K1 — Kernel Runtime Audit
- ✅ K1.5 — Kernel Runtime Specification
- ✅ K1.6 — Canonical Resource Model
- ✅ K1.7–K1.11 — Final Architecture Freeze
- ✅ K4 — Contract Freeze

## Kernel Implementation Phase (✅ Complete — July 2026)

> **Provenance note:** Implementation status markers added post-freeze after K2.1–K2.4 were independently verified complete. Architecture contracts unchanged. See `CURRENT_STATE.md` for detailed implementation status.

```
K2.1 — Execution Runtime              ✅ Complete
  ExecutionContext, CancellationToken, WorkingMemory
  ExecutionRuntime.invoke()
  WorkerRegistry
  Wire AbstractCognitiveWorker to ExecutionContext
  Wire MemoryCuratorWorker into composition root
  PlannerWorker (minimal)

K2.2 — Workflow Runtime                ✅ Complete
  WorkflowDefinition, Node, Edge
  WorkflowRuntime.execute/resume/cancel
  Wire RetrievalContextBuilder into
  live path

K2.3 — Capability Registry             ✅ Complete
  Adapter Protocol (named Adapter, not CapabilityAdapter)
  CapabilityRegistry, AdapterRuntime
  Wrap existing Providers (ModelRouterAdapter)
  OllamaAdapter, OpenAICompatAdapter

K2.4 — Governance Completion           ✅ Complete
  Reconcile MemoryGovernor interface
  OrchestrationGovernor, AgentGovernor, ConversationGuardrails
  7 governors total
```

## Validation Phase

- K3 — Kernel Validation & Compliance Audit (post-implementation)

## Cognitive Phase (Post-Kernel)

Self-Identity Model, Reflection Engine, Planning Engine, Skills Runtime, External Knowledge Pipeline, Multi-Agent Runtime, Advanced GraphRAG/KAG, Provenance Completion, Web UI, Developer Platform.

---

# 24. Glossary

Canonical definitions. When multiple terms existed for the same concept, one was chosen and the others noted as deprecated or scoped.

| Term | Definition |
|---|---|
| **Action** | What a Capability actually does when invoked |
| **Adapter** | A concrete implementation satisfying a Capability's contract by wrapping one external system |
| **Capability** | An abstract, schedulable unit of work defined by its contract |
| **Capability Contract** | The formal input/output/side-effect specification a Capability publishes |
| **Cancellation Token** | Cooperative cancellation mechanism carried in ExecutionContext |
| **Composition Root** | `main.py` — the single location where all services are constructed and wired |
| **Constraint** | Something extracted from an Intent that limits how its Goal can be satisfied |
| **Context** | A transient, task-scoped view assembled from Memory for one execution. Not a persistent store. |
| **Decision** | The outcome of one governance evaluation (maps to `GovernanceVerdict`) |
| **Event** | An immutable record of a specific state transition |
| **Evidence** | Observation(s) evaluated as relevant/reliable enough to justify a claim |
| **Execution Boundary** | The isolation line around one execution — what it can see, touch, and fail without affecting |
| **Execution Context** | The data object threading through one execution |
| **Execution Runtime** | The service that invokes one Worker for one unit of work |
| **Execution Transaction** | The atomicity unit for a multi-step workflow |
| **Goal** | The verified target state an Intent compiles to |
| **Governor** | An implementation of one Policy — a `Governor` subclass |
| **Graph** | An index over Memory, not a storage layer |
| **Kernel** | The smallest set of responsibilities that must be centralized/governed for coherence |
| **Kernel Runtime** | The live process instantiating the Kernel's services |
| **Kernel State** | The kernel's own bookkeeping — registries, governor state, active executions |
| **Knowledge** | The subset of Memory validated past a confidence threshold |
| **Memory** | The kernel's persistent store of observations, evidence, and derived facts |
| **Module** | **Deprecated.** Legacy term for what Skill/Capability replaces. |
| **Observation** | A raw, timestamped record of something perceived or that occurred |
| **Policy** | A specific, declared rule constraining what a capability or resource may do |
| **Provider** | Sub-type of Adapter scoped to inference specifically |
| **Resource** | A managed kernel object with identity, lifecycle, and provenance |
| **Retrieval** | The Capability of querying Memory/Knowledge to produce Evidence |
| **Runtime State** | The state of one in-progress execution (carried by ExecutionContext) |
| **Service** | A kernel-internal component with its own lifecycle that does coordination work |
| **Skill** | A typed, contract-bearing Capability whose Adapter is local code |
| **Task** | A single schedulable unit of work toward a Goal |
| **Tool** | What a Skill is called when exposed externally via MCP |
| **Worker** | A schedulable cognitive unit executing via `AbstractCognitiveWorker.execute()` |
| **Worker Lifecycle** | `IDLE → RUNNING → COMPLETED | FAILED | CANCELLED | PAUSED` |
| **Working Memory** | L0 — in-process, per-execution scratch space |
| **Workflow** | A reusable, versioned template composing Capabilities to satisfy a class of Goals |
| **Workflow Runtime** | The service that coordinates a DAG of Execution Runtime invocations |

---

*KERNEL_ARCHITECTURE_v1.0 — Frozen. This document is the single authoritative engineering specification for OCBrain. All K2 implementation work references this document first.*
