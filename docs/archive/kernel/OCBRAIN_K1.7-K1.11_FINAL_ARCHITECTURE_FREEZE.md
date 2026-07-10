# OCBrain Kernel — K1.7–K1.11: Final Architecture Freeze

**Date:** July 10, 2026
**Status:** Architecture Freeze — Canonical. No implementation performed.
**Precedence:** Kernel Constitution (11-law) → K1 Audit → K1.5 Specification → K1.6 Resource Model → this document → `PROJECT_INSTRUCTIONS.md` → implemented code.
**Method:** Complete re-read of every source file cited, every prior specification (K1, K1.5, K1.6), the Constitution, and the full `PROJECT_INSTRUCTIONS.md`. Every claim below is either a direct file/line citation or explicitly marked as architectural decision. Nothing is assumed from prior sessions without re-verification.
**Scope:** Everything required between now and K2 implementation. Nothing already frozen is redesigned.

---

## Preamble: Why This Session Exists Despite K1.6's Recommendation

K1.6 §8 recommended against a fixed K1.7–K1.11 sequence, arguing that implementation contact should be the source of the next question. That recommendation was sound for the concern it addressed — preventing speculative redesign of things that were already well-specified.

This session is not speculative redesign. It addresses a specific, concrete gap: **K1, K1.5, and K1.6 collectively specified *what* services exist, *what* vocabulary to use, and *what* data model underpins them — but they did not produce frozen public contracts, lifecycle specifications, or ownership matrices complete enough for K2 to begin without architectural invention.** K1.5 §3's API contracts were explicitly described as "a strong starting proposal, not proven by use yet." K1.5 §10 listed several interfaces as "not yet mature — explicitly not frozen."

The evidence justifying this session is not hypothetical. It is the gap between K1.5's own stated confidence level ("specified precisely enough that K2 can proceed as an implementation session") and the concrete question: can an implementer open `core/runtime/` tomorrow and write `ExecutionRuntime.invoke()` with zero ambiguity about who owns the `ExecutionContext`, who manages retries, who propagates cancellation, and who decides when Working Memory is cleaned up? K1.5 specified these as belonging to named services but did not freeze the interaction contracts between them.

This session closes that gap. It makes the architecture *smaller* and *more deterministic*, not more complicated.

---

# Table of Contents

1. [Phase 1 — Execution Runtime Specification (K1.7)](#phase-1--execution-runtime-specification-k17)
2. [Phase 2 — Capability Model Specification (K1.8)](#phase-2--capability-model-specification-k18)
3. [Phase 3 — Workflow Runtime Specification (K1.9)](#phase-3--workflow-runtime-specification-k19)
4. [Phase 4 — Worker Runtime Specification (K1.10)](#phase-4--worker-runtime-specification-k110)
5. [Phase 5 — Cross-Architecture Review (K1.11)](#phase-5--cross-architecture-review-k111)
6. [Architecture Decision Records](#architecture-decision-records)
7. [Frozen Public Contracts](#frozen-public-contracts)
8. [Ownership Matrix](#ownership-matrix)
9. [Dependency Graph](#dependency-graph)
10. [Constitution Traceability Matrix](#constitution-traceability-matrix)
11. [Interface Inventory](#interface-inventory)
12. [Remaining Architectural Risks](#remaining-architectural-risks)
13. [K2 Readiness Assessment](#k2-readiness-assessment)
14. [Architecture Freeze Checklist](#architecture-freeze-checklist)
15. [Kernel Architecture Baseline v1.0](#kernel-architecture-baseline-v10)
16. [Updated Canonical Roadmap](#updated-canonical-roadmap)

---

# Phase 1 — Execution Runtime Specification (K1.7)

## 1.1 Core Components

### Kernel

**What it is:** The top-level coordination layer. Not a class — a responsibility boundary. The Kernel is the set of services that must be centralized for OCBrain to remain coherent.

**What it owns:** Service registration, governance evaluation, event routing, capability resolution, execution lifecycle.

**What it does NOT own:** Memory internals, retrieval algorithms, classification logic, merge/synthesis logic, model inference. All of these are capabilities or adapters.

**Current implementation:** `main.py` (composition root) + `Orchestrator` (coordination) + `GovernanceKernel` + `EventStream`. The Orchestrator currently conflates kernel-coordination and execution-layer responsibilities. K2 separates these.

### ExecutionRuntime

**What it is:** The service that constructs and invokes one Worker for one unit of work.

**What it owns:**
- Worker instantiation (via WorkerRegistry)
- ExecutionContext creation and propagation
- Working Memory allocation and cleanup for a single execution
- Failure containment at the single-execution level
- Cancellation propagation

**What it does NOT own:**
- Multi-step coordination (that's WorkflowRuntime)
- Retries across executions (that's WorkflowRuntime)
- Worker implementation (that's the Worker subclass)
- Governance evaluation (that's GovernanceService, called *by* the Worker's `execute()` template method — already correctly implemented)

**Lifecycle:**

```
invoke(worker_type, context) called
  → WorkerRegistry.get(worker_type) → Worker class
  → Construct Worker instance (DI: governance, event_stream)
  → Allocate Working Memory in context
  → Worker.execute(context) — governance and events handled inside
  → Capture WorkerResult
  → Clean up Working Memory
  → Return WorkerResult (never raises — failures are result values)
```

### ExecutionContext

**What it is:** The data object threading through one execution. Immutable after creation except for Working Memory writes during execution.

**Frozen fields** (from K1.5 §3.3, verified still correct):

```python
@dataclass
class ExecutionContext:
    request_id: str          # Unique per request (UUID)
    worker_id: str           # Assigned by ExecutionRuntime
    session_id: str          # Correlates related requests
    causal_chain: List[str]  # Parent execution IDs for replay
    working_memory: WorkingMemory  # Scoped scratch space
    governance_state: Dict[str, Any]  # Budget counters, step counts
    cancellation_token: CancellationToken  # Cooperative cancellation
    workflow_id: str = ""    # Set by WorkflowRuntime if in a workflow
    parent_worker_id: str = ""  # Set if invoked by SupervisorWorker
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Relationship to existing `WorkerContext`:** `ExecutionContext` *replaces* `WorkerContext` (`core/workers/base.py:66-89`). `WorkerContext` was the first draft of this concept; `ExecutionContext` is the canonical version. K2 migrates `AbstractCognitiveWorker.execute()` to accept `ExecutionContext`. The migration is a field-level superset — every field in `WorkerContext` maps to a field in `ExecutionContext`:
- `task_id` → `request_id`
- `query` → `working_memory` (query placed into working memory as the initial context)
- `parameters` → `metadata`
- `recursion_depth` → `governance_state["recursion_depth"]`
- `parent_worker_id` → `parent_worker_id`
- `workflow_id` → `workflow_id`

### Working Memory

**What it is:** L0 (PI §8.1) — in-process, per-execution scratch space. Not a service — a resource owned by `ExecutionContext`.

**Ownership:** Created by ExecutionRuntime at invocation. Readable/writable by the Worker during execution. Cleaned up by ExecutionRuntime after execution completes.

**Scope:** Per-execution. Never persists across requests. Long-term persistence is UnifiedMemory's job.

**Contents:** Key-value store. The retrieval Context (from `RetrievalContextBuilder`) is one entry. Worker scratch data is another. Intermediate results in multi-step workflows are checkpointed here between nodes.

**Decision:** Working Memory holds `RetrievalContextBuilder`-shaped `Context` objects, not flat `List[SearchResult]` — per K1.5 §6, unchanged.

### CancellationToken

**What it is:** Cooperative cancellation mechanism. A simple boolean flag with event notification.

```python
class CancellationToken:
    def __init__(self):
        self._cancelled: bool = False
        self._event: asyncio.Event = asyncio.Event()

    def cancel(self) -> None:
        self._cancelled = True
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    async def wait(self, timeout: float = None) -> bool:
        """Wait for cancellation. Returns True if cancelled."""
        ...
```

**Relationship to existing cancellation:** `AbstractCognitiveWorker` already has `self._cancelled` and `is_cancelled` property (`core/workers/base.py:332-349`). K2 replaces this with `context.cancellation_token.is_cancelled`. The Worker no longer owns cancellation state — the ExecutionContext does.

## 1.2 Execution Lifecycle

```
1. Request arrives at Orchestrator
2. Orchestrator determines execution type:
   a. Single worker invocation → ExecutionRuntime.invoke()
   b. Multi-step workflow → WorkflowRuntime.execute()
3. ExecutionRuntime.invoke():
   3a. Create ExecutionContext (request_id, working_memory, etc.)
   3b. Resolve worker type via WorkerRegistry
   3c. Construct Worker instance with DI dependencies
   3d. Call Worker.execute(context)
       - Worker.execute() calls GovernanceService (template method, already built)
       - Worker.execute() emits events (template method, already built)
       - Worker._run(context) does actual work
   3e. Capture WorkerResult
   3f. Clean up Working Memory
   3g. Return WorkerResult
4. Orchestrator receives result, persists to UnifiedMemory, emits completion event
```

## 1.3 Ownership Answers

| Question | Owner | Evidence |
|---|---|---|
| Who creates execution? | ExecutionRuntime | Only entry point for worker invocation |
| Who owns execution? | ExecutionRuntime for lifecycle; Worker for behavior | Template method pattern already enforces this in `base.py` |
| Who owns Working Memory? | ExecutionContext (created by ExecutionRuntime) | Per-execution scope, cleaned up by runtime |
| Who owns ExecutionContext? | ExecutionRuntime creates it; Worker reads/writes it | Passed by value into Worker.execute() |
| Who owns retries? | WorkflowRuntime (multi-step) or none (single execution) | A single `invoke()` does not retry — the caller decides |
| Who owns replay? | EventStream + ExecutionContext.causal_chain | Already built (EventStream.replay()), needs causal_chain propagation |
| Who owns cancellation? | CancellationToken (in ExecutionContext) | Cooperative — Workers check it voluntarily |
| Who owns execution boundaries? | ExecutionRuntime | Each `invoke()` is one boundary |
| Who owns transaction lifetime? | WorkflowRuntime | Only meaningful for multi-step |
| Who owns failure propagation? | ExecutionRuntime (wraps in WorkerResult) | Never raises — failures are result values |
| Who owns dependency injection? | Composition Root (`main.py`) | Explicit constructor injection, per K1 §2 |

## 1.4 State Transitions

```
Worker States (already defined in core/workers/base.py:48-59):

  IDLE → RUNNING → COMPLETED
                 → FAILED
                 → CANCELLED
       → PAUSED (reserved for HITL — not yet exercised)
```

No new states needed. No state added. No state removed.

## 1.5 Failure Model

1. **Worker raises exception:** Caught by `AbstractCognitiveWorker.execute()` (already implemented, `base.py:273-286`). Worker transitions to FAILED. `WorkerResult(success=False, error=str(e))` returned. Event emitted.

2. **Governance rejects:** Caught by `execute()` (already implemented, `base.py:218-240`). `WorkerResult(success=False)` returned with governance reason. Event emitted.

3. **Cancellation:** Caught by `execute()` (already implemented, `base.py:263-271`). Worker transitions to CANCELLED. `WorkerResult(success=False, error="cancelled")` returned.

4. **Event emission fails:** Already non-fatal (already implemented, `base.py:406-409`). Logged, never blocks execution.

5. **ExecutionRuntime.invoke() failure:** The only new failure surface. If WorkerRegistry can't resolve the type, or Worker construction fails, `invoke()` returns `WorkerResult(success=False)` without ever entering the Worker lifecycle. This is a resolution error, not an execution error.

**Principle:** Execution failures never propagate as exceptions past the ExecutionRuntime boundary. Every failure becomes a `WorkerResult` with `success=False`. This preserves the containment pattern already correct in the current `asyncio.gather(..., return_exceptions=True)` fan-out (`orchestrator.py:256`).

---

# Phase 2 — Capability Model Specification (K1.8)

## 2.1 Taxonomy

Every entity that "does work" falls into exactly one of these categories:

| Concept | What it is | Layer | Examples |
|---|---|---|---|
| **Capability** | An abstract, schedulable unit of work defined by its contract | Interface | "inference", "web_search", "code_execution" |
| **Adapter** | A concrete implementation satisfying a Capability's contract by wrapping one external system | Implementation | `OllamaProvider`, `GenericOpenAICompatibleProvider` |
| **Provider** | Sub-type of Adapter scoped to inference specifically | Implementation | Same as above — Provider is the existing class name; Adapter is the kernel term |
| **Skill** | A typed, contract-bearing Capability whose Adapter is local code | Implementation | `BaseSkill` subclasses (`core/skills/skill_interface.py`) |
| **Tool** | What a Skill is called when exposed externally via MCP | External vocabulary | Same underlying object, MCP-facing name |
| **Worker** | A schedulable cognitive unit that *uses* Capabilities | Runtime object | `MemoryCuratorWorker`, future `PlannerWorker` |
| **MCP** | Adapter protocol for external tool integration | Protocol | MCP server/client interactions |
| **Browser** | Capability backed by a browser-automation Adapter | Capability + Adapter | Future `BrowserWorker` uses this |
| **API** | External HTTP service exposed as a Capability via an Adapter | Capability + Adapter | REST endpoints wrapped as skills |
| **Reasoner** | Not a kernel concept — reasoning is what specific Workers do | N/A | `PlannerWorker`, `ReflectionWorker` |
| **LLM** | An Adapter (Provider) for the inference Capability | Adapter | Ollama, OpenAI-compatible |
| **External Service** | Anything outside the kernel, accessed only through Adapters | External | GitHub, databases, web APIs |

### What is an interface vs. implementation vs. runtime object vs. registry entry vs. resource?

| Entity | Classification |
|---|---|
| Capability | Interface (defines contract) |
| CapabilityContract | Interface (formal spec) |
| Adapter | Implementation (satisfies contract) |
| Provider | Implementation (inference-specific Adapter) |
| Skill | Implementation (local-code Adapter) |
| Worker | Runtime object (instantiated per execution) |
| CapabilityMetadata | Resource (K1.6 — satisfies Resource Protocol) |
| CapabilityRegistry entry | Registry entry (static, startup-time) |
| CapabilityResolver result | Runtime computation (stateless function) |

## 2.2 CapabilityRegistry — Frozen Architecture

**What it is:** A static index of what Capabilities and their Adapters exist. Populated at startup.

**What it is NOT:** A runtime service that makes selection decisions. That's CapabilityResolver.

**Registration flow:**

```
Startup (composition root):
  1. Construct CapabilityRegistry
  2. Register inference adapters (from provider_mesh.py's existing Provider subclasses)
  3. Register skill adapters (from future BaseSkill implementations)
  4. Register MCP adapters (when MCP tools are configured)
  5. Freeze registry (no runtime registration)
```

**Contract:**

```python
class CapabilityRegistry:
    def register(self, capability_id: str, adapter: CapabilityAdapter) -> None:
        """Register an adapter for a capability. Startup-only."""

    def resolve(self, capability_id: str) -> List[CapabilityAdapter]:
        """Return all registered adapters for a capability."""

    def list_capabilities(self) -> List[str]:
        """Return all registered capability IDs."""

    def get_metadata(self, capability_id: str) -> Optional[CapabilityMetadata]:
        """Return metadata for a capability."""
```

**Thread safety:** Read-heavy after startup. No writes after initialization. Safe for concurrent reads without locking.

**Failure behavior:** Requesting an unregistered capability returns an empty list — a resolution-time error, surfaced by CapabilityResolver, not a registry-time crash.

## 2.3 CapabilityResolver — Frozen Architecture

**What it is:** A stateless runtime function that picks *which* Adapter satisfies a request right now, given candidates from the Registry.

**Contract:**

```python
class CapabilityResolver:
    def select(self, candidates: List[CapabilityAdapter],
               context: ExecutionContext) -> CapabilityAdapter:
        """Select the best available adapter from candidates.

        Selection criteria (ordered):
        1. Health score (existing: Provider.health_score)
        2. Availability (existing: Provider.is_available())
        3. Cost (future: when multiple providers have different costs)

        Raises CapabilityUnavailableError if no candidate is healthy.
        """
```

**Relationship to existing code:** `provider_mesh.py` already implements health tracking (`mark_success()`, `mark_failure()`, `is_available()`, `health_score`) and fallback ordering (`generate_with_fallback()` iterates providers by health). CapabilityResolver *generalizes* this existing, proven pattern from inference-only to all capabilities.

## 2.4 CapabilityAdapter — Frozen Interface

```python
class CapabilityAdapter(Protocol):
    """Contract every adapter must satisfy."""

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

**Protocol, not ABC:** Same reasoning as K1.6's Resource Protocol decision — existing `Provider` class in `provider_mesh.py` already has `generate()`, `is_available()`, `health_score`, `mark_success()`, `mark_failure()`. Making CapabilityAdapter a Protocol lets Provider satisfy it with minimal field renaming, without changing its inheritance chain.

## 2.5 How Everything Becomes a Capability

| Thing | Capability ID | Adapter class | Status |
|---|---|---|---|
| Ollama | `inference` | `OllamaProvider` (rename `generate` → `invoke`) | Exists, needs wrapper |
| OpenAI-compatible | `inference` | `GenericOpenAICompatibleProvider` | Exists, needs wrapper |
| Future Skill | `skill:{name}` | `BaseSkill` subclass | Interface exists, zero implementations |
| Future MCP Tool | `mcp:{tool_name}` | MCP client adapter | Not yet built |
| Future Browser | `browser` | Playwright adapter | Not yet built |
| Future Code Exec | `code_execution` | Sandbox adapter | Not yet built |

**One contract. Many adapter kinds.** This is Constitution Part II made concrete: "the kernel owns abstractions; adapters own implementations."

---

# Phase 3 — Workflow Runtime Specification (K1.9)

## 3.1 Core Concepts

### WorkflowDefinition

**What it is:** A reusable, versioned template describing a DAG of nodes. Declarative — no execution state.

```python
@dataclass
class WorkflowDefinition:
    workflow_id: str               # Unique identifier
    version: str                   # SemVer
    name: str                      # Human-readable
    nodes: List[WorkflowNode]      # DAG nodes
    edges: List[WorkflowEdge]      # Directed edges between nodes
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### WorkflowNode

```python
@dataclass
class WorkflowNode:
    node_id: str                    # Unique within the workflow
    node_type: str                  # "worker", "capability", "approval", "checkpoint"
    worker_type: str = ""           # If node_type=="worker", which worker
    capability_id: str = ""         # If node_type=="capability", which capability
    retry_policy: Optional[RetryPolicy] = None
    timeout_seconds: float = 300.0
    error_branch: str = ""          # Node to jump to on failure
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### WorkflowEdge

```python
@dataclass
class WorkflowEdge:
    source_node: str
    target_node: str
    condition: str = ""  # Optional condition expression (empty = unconditional)
```

### RetryPolicy

```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_base_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 60.0
    retryable_errors: List[str] = field(default_factory=list)  # Empty = retry all
```

### WorkflowInstance

**What it is:** One execution of a WorkflowDefinition. Carries mutable state.

```python
@dataclass
class WorkflowInstance:
    instance_id: str                  # Unique per execution
    definition: WorkflowDefinition    # Which workflow this is
    state: WorkflowState              # pending/running/completed/failed/cancelled
    current_node: str                 # Which node is active
    node_results: Dict[str, WorkerResult]  # Results per completed node
    checkpoint_sequence: int = 0      # Last EventStream checkpoint
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: str = ""
```

### WorkflowState

```python
class WorkflowState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"  # HITL node
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

## 3.2 WorkflowRuntime — Frozen Architecture

**What it is:** The service that coordinates a DAG of ExecutionRuntime invocations.

**What it owns:**
- WorkflowInstance lifecycle
- Node sequencing (topological order of the DAG)
- Retry logic (per-node, via RetryPolicy)
- Checkpoint/Resume (via EventStream)
- ExecutionTransaction (the whole workflow is one atomic unit by default)
- HITL approval gates (when node_type == "approval")
- Rollback (on unrecoverable failure: mark instance as FAILED, no automatic undo of completed nodes — explicit compensating actions are future work)

**Contract:**

```python
class WorkflowRuntime:
    def __init__(self, execution_runtime: ExecutionRuntime,
                 event_stream: EventStream,
                 governance: GovernanceKernel):
        ...

    async def execute(self, definition: WorkflowDefinition,
                      context: ExecutionContext) -> WorkflowResult:
        """Execute a workflow DAG.

        - Creates a WorkflowInstance
        - Iterates through nodes in topological order
        - For each node: invokes ExecutionRuntime.invoke()
        - Checkpoints after each completed node
        - Handles retries per node's RetryPolicy
        - Emits one event per node transition
        - Returns aggregate WorkflowResult
        """

    async def resume(self, instance_id: str) -> WorkflowResult:
        """Resume a suspended workflow from its last checkpoint."""

    async def cancel(self, instance_id: str) -> None:
        """Cancel a running workflow."""
```

## 3.3 Interaction Model

```
WorkflowRuntime.execute(definition, context)
  ├─ Create WorkflowInstance
  ├─ Emit "workflow.started" event
  ├─ For each node in topological order:
  │   ├─ Emit "workflow.node.started" event
  │   ├─ If node_type == "approval":
  │   │   ├─ Emit "workflow.approval.required" event
  │   │   ├─ Set state = WAITING_APPROVAL
  │   │   └─ Suspend (checkpoint to EventStream, return)
  │   ├─ If node_type == "checkpoint":
  │   │   └─ Create EventStream checkpoint
  │   ├─ If node_type == "worker" or "capability":
  │   │   ├─ ExecutionRuntime.invoke(node.worker_type, context)
  │   │   ├─ If result.success == False AND node has RetryPolicy:
  │   │   │   └─ Retry with backoff
  │   │   ├─ If result.success == False AND retries exhausted:
  │   │   │   ├─ If node has error_branch: jump to error_branch node
  │   │   │   └─ Else: workflow FAILED
  │   │   └─ Store result in instance.node_results
  │   └─ Emit "workflow.node.completed" event
  ├─ Emit "workflow.completed" event
  └─ Return WorkflowResult (aggregate of all node results)
```

## 3.4 Interactions with Other Services

| Service | Interaction | Direction |
|---|---|---|
| ExecutionRuntime | WorkflowRuntime calls `invoke()` for each worker/capability node | Workflow → Execution |
| EventStream | One event per node transition; checkpoints for durability | Workflow → Events |
| GovernanceService | Evaluated by each Worker's `execute()` template method (not by WorkflowRuntime directly) | Worker → Governance |
| UnifiedMemory | Accessed by Workers during execution through Capabilities | Worker → Memory (indirect) |

## 3.5 ExecutionTransaction

**Scope:** One WorkflowInstance = one transaction. If any node fails irrecoverably (retries exhausted, no error_branch), the whole workflow is marked FAILED.

**What "rollback" means at K2:** Setting the instance state to FAILED and emitting a failure event. Automatic compensating actions (undoing completed nodes) are explicitly deferred — they require domain-specific compensation logic that doesn't exist yet.

**What "commit" means:** The workflow completes with all nodes successful. The aggregate result is returned.

---

# Phase 4 — Worker Runtime Specification (K1.10)

## 4.1 Worker Architecture

### Worker Lifecycle

```
Construction → IDLE → execute() called → RUNNING → COMPLETED
                                                  → FAILED
                                                  → CANCELLED
                                       → PAUSED (HITL, future)
```

Workers are **not long-lived.** A new instance is created per `ExecutionRuntime.invoke()` call. This is consistent with "no hidden state outside of resources" (Constitution Part II).

### Worker Identity

Each worker instance has a unique ID: `"{worker_type}:{uuid_hex[:8]}"`. Already implemented in `base.py:168`.

### Execution Boundary

Each Worker executes within one `ExecutionContext`. The boundary is:
- **Can see:** Its own Working Memory, its own ExecutionContext, Capabilities it has permission to use
- **Cannot see:** Other concurrent executions' Working Memory, other Workers' state
- **Cannot do:** Bypass governance (structurally impossible — template method pattern)

### Working Memory Ownership

Working Memory belongs to the ExecutionContext. The Worker reads and writes it during `_run()`. After execution, the ExecutionRuntime cleans it up.

### Context Ownership

The ExecutionContext is owned by the ExecutionRuntime that created it. The Worker receives it by reference and may read/write its Working Memory but cannot replace the context itself.

### Supervisor Interaction

A `SupervisorWorker` creates sub-executions by calling `ExecutionRuntime.invoke()` with `context.parent_worker_id` set to its own ID and `context.governance_state["recursion_depth"]` incremented. RecursionGovernor (already live) prevents unbounded nesting.

### Checkpoint

Workers can request checkpoints by emitting checkpoint events through EventStream. This is already supported: `EventStream.create_checkpoint()` (`event_stream.py:466-487`).

### Recovery

Recovery after crash = replay from the last checkpoint via `EventStream.replay()` + `WorkflowRuntime.resume()`. Individual Worker instances do not survive process restarts — they are recreated during resume.

### Cancellation

Workers check `context.cancellation_token.is_cancelled` periodically in `_run()`. The existing `is_cancelled` property pattern (`base.py:342-349`) is preserved, just redirected to the token.

### Capability Access

Workers access Capabilities through `CapabilityRegistry.resolve()` + `CapabilityResolver.select()` + `adapter.invoke()`. Workers never construct Adapters directly.

### Memory Access

Workers access persistent memory through UnifiedMemory's public API (`write()`, `search()`, `stats()`). Workers never touch UnifiedMemory internals.

### Worker Communication

Workers do not communicate directly. They communicate through:
1. **Working Memory:** Results placed into shared Working Memory within a workflow
2. **EventStream:** Events emitted by one Worker can be observed by subscribers
3. **WorkflowRuntime:** Results from one node are available to subsequent nodes

### Worker Composition

Workers compose through **WorkflowRuntime's DAG**, not through direct invocation (except SupervisorWorker, which explicitly manages sub-workers).

### Worker vs. Capability Distinction

| Property | Worker | Capability |
|---|---|---|
| **What it does** | Cognitive orchestration — decides what to do, coordinates | Atomic work — performs one specific action |
| **Who calls it** | ExecutionRuntime | Workers (through adapters) |
| **Governance** | Self-governing (template method) | Governed by the calling Worker's governance context |
| **State** | Has lifecycle (IDLE→RUNNING→COMPLETED) | Stateless (each invocation is independent) |
| **Examples** | PlannerWorker, EvaluatorWorker | inference, web_search, code_execution |

## 4.2 Canonical Worker Definitions

### Existing Worker

**MemoryCuratorWorker** (`core/workers/curator.py`)
- **Status:** Implemented, never instantiated in production
- **Responsibility:** Active memory improvement — prune stale entries, strengthen high-access connections, resolve contradictions, derive new facts
- **Capabilities used:** UnifiedMemory (read/write), GovernanceKernel (evolution governance)
- **K2 action:** Wire into composition root, schedule periodic execution

### Workers to Implement in K2

**PlannerWorker**
- **Responsibility:** Decompose a goal into a plan (a sequence of sub-tasks)
- **Capabilities used:** inference (to generate plans), UnifiedMemory (to retrieve relevant context)
- **Output:** A `WorkflowDefinition` or a list of sub-tasks
- **K2 priority:** K2.1 (after ExecutionRuntime lands)

**ReflectionWorker**
- **Responsibility:** Evaluate and critique the system's own outputs, decisions, and reasoning
- **Capabilities used:** inference (to generate critiques), EventStream (to review past actions)
- **Output:** Evaluation with scores and recommendations
- **K2 priority:** K2.4+

**EvaluatorWorker**
- **Responsibility:** Score/grade a specific output against criteria
- **Capabilities used:** inference (for evaluation), UnifiedMemory (for ground truth comparison)
- **Output:** Score, pass/fail, structured evaluation
- **K2 priority:** K2.4+

**SupervisorWorker**
- **Responsibility:** Coordinate multiple sub-workers for a complex task
- **Capabilities used:** ExecutionRuntime (to invoke sub-workers), GovernanceKernel (recursion depth tracking)
- **Output:** Aggregate result from coordinated sub-workers
- **K2 priority:** K2.4+ (depends on multiple other workers existing)

**BrowserWorker**
- **Responsibility:** Web browsing, content extraction, interaction
- **Capabilities used:** browser capability (Playwright adapter)
- **Output:** Extracted content, screenshots, interaction results
- **K2 priority:** Cognitive Phase (v4.3.6+)

**CoderWorker**
- **Responsibility:** Code generation, modification, analysis
- **Capabilities used:** inference, code_execution (sandboxed)
- **Output:** Generated code, analysis results
- **K2 priority:** Cognitive Phase (v4.3.6+)

### Future Workers (Post-K2)

- **IdentityWorker:** Self-model construction and maintenance (Cognitive Phase)
- **ResearchWorker:** Multi-source knowledge acquisition (Cognitive Phase)
- **SkillCreatorWorker:** Automated skill generation from patterns (Cognitive Phase)

---

# Phase 5 — Cross-Architecture Review (K1.11)

## 5.1 Circular Ownership Check

| Relationship | Direction | Circular? |
|---|---|---|
| Kernel → ExecutionRuntime | Creates | No |
| ExecutionRuntime → Worker | Creates | No |
| Worker → Capability | Uses | No |
| Capability → Memory | Reads/writes | No |
| WorkflowRuntime → ExecutionRuntime | Uses | No |
| SupervisorWorker → ExecutionRuntime | Uses (creates sub-executions) | **Potential cycle** — mitigated by RecursionGovernor depth limit |

**Verdict:** No circular ownership. The SupervisorWorker re-entry is governed, not circular — it's a tree (bounded depth), not a cycle.

## 5.2 Circular Dependencies Check

```
GovernanceService ← Worker (calls evaluate_action)
EventStream ← Worker (emits events)
EventStream ← GovernanceService? NO — governance doesn't emit to EventStream directly
                                    (Worker emits on governance's behalf)
CapabilityRegistry ← Worker (resolves capabilities)
ExecutionRuntime ← WorkflowRuntime (invokes workers)
ExecutionRuntime ← SupervisorWorker (creates sub-executions)
UnifiedMemory ← Worker (reads/writes via public API)
```

**Verdict:** No circular dependencies. All arrows point in one direction within each pair.

## 5.3 Duplicated Abstractions Check

| Potential duplicate | Verdict | Action |
|---|---|---|
| `WorkerContext` vs `ExecutionContext` | Duplicate | Merge — ExecutionContext replaces WorkerContext |
| `Provider` vs `CapabilityAdapter` | Conceptual overlap | Provider becomes a sub-type of CapabilityAdapter (wrapper, not replacement) |
| `BaseSkill.execute()` vs `CapabilityAdapter.invoke()` | Different levels | BaseSkill is a specific Adapter implementation — its `execute()` is called by `invoke()` |
| `Module` (legacy) vs `Skill` (canonical) | Superseded | Module is phased out; Skill is the canonical term |
| `EventBus` (`core/event_bus.py`) vs `EventStream` | Different purposes | EventBus is in-process pub/sub without persistence; EventStream is durable. Both needed. EventBus should subscribe to EventStream for in-process delivery (not duplicate). |
| `RetrievalFusionEngine` vs `RetrievalContextBuilder` | Two retrieval stacks | RetrievalContextBuilder supersedes. K2 wires it into the live path. (K1.5 §13 finding) |

**Actions taken:** Two merges (WorkerContext → ExecutionContext, RetrievalFusionEngine → RetrievalContextBuilder). One subsumption (Provider under CapabilityAdapter). One phase-out (Module → Skill). No new abstractions introduced.

## 5.4 Hidden Coupling Check

| Component | Hidden coupling found? | Detail |
|---|---|---|
| Orchestrator | Yes — couples kernel coordination with execution | K2 separates these via ExecutionRuntime |
| `classify()` | Tightly coupled to module labels, not capabilities | K2 migrates to capability resolution |
| `merger.merge()` | Expects `RouteResult` objects | Needs to accept `WorkerResult` post-K2 |
| `context_assembler` | Uses `RetrievalFusionEngine` (simple path) | K2 switches to `RetrievalContextBuilder` |

## 5.5 Leaking Responsibilities Check

| Component | Leaking responsibility | Fix |
|---|---|---|
| Orchestrator.handle() | Does governance evaluation directly instead of delegating to Workers | K2: Workers own governance via template method. Orchestrator delegates to ExecutionRuntime. |
| Orchestrator.handle() | Writes to UnifiedMemory directly | K2: This becomes a Worker's responsibility or a post-execution hook |
| Orchestrator.handle() | Runs classification directly | K2: Classification becomes a Capability, invoked by PlannerWorker |

## 5.6 Unnecessary Interfaces Check

Scanned every interface/protocol/ABC in the codebase:

| Interface | Necessary? | Reasoning |
|---|---|---|
| `EventStore` (ABC) | Yes | Enables future Redpanda migration (FA §8 Risk 5) |
| `Governor` (base class) | Yes | Multiple concrete governors exist |
| `BaseModule` (ABC) | Phase-out candidate | Being superseded by BaseSkill/Worker |
| `Provider` (ABC) | Yes, subsumes into CapabilityAdapter | Multiple concrete providers exist |
| `BaseSkill` (ABC) | Yes | The canonical Capability implementation contract |
| `AbstractCognitiveWorker` (ABC) | Yes | The canonical Worker contract |

**Verdict:** No unnecessary interfaces found. `BaseModule` is the only one being phased out, and that's already the plan.

## 5.7 Naming Consistency Check

| Inconsistency | Current | Canonical | K2 Action |
|---|---|---|---|
| Provider vs Adapter | Both used | Adapter (kernel term), Provider (inference sub-type) | Consistent with K1.5 §1.1 |
| Module vs Skill | Both in code | Skill | Phase out Module |
| WorkerContext vs ExecutionContext | WorkerContext in code | ExecutionContext | Merge |
| `evaluate_action()` parameter names | Consistent | Keep | No action |

## 5.8 Constitution Violations Check

| Area | Violation found? | Detail |
|---|---|---|
| Law 1 (Bounded Autonomy) | Partial — governance runs at orchestrator level, not per-capability | Fixed by K2 Worker wiring |
| Law 2 (Explicit State) | Partial — fine-grained events missing below orchestrator level | Fixed by K2 per-node events |
| Law 3 (Separation of Concerns) | Yes — Orchestrator does execution work inline | Fixed by K2 ExecutionRuntime |
| Law 4 (Determinism) | No violations found | |
| Law 5 (User Sovereignty) | No violations (not yet exercised) | |
| Law 6 (Explainability) | Weak — no pre-execution confidence reporting | K2.4+ |
| Law 7 (Replaceability) | Partial — model replaceability exists, capability replaceability doesn't yet | Fixed by K2 CapabilityRegistry |
| Law 8 (Evidence over Assumption) | No violations found (exemplary) | |
| Law 9 (Single Source of Truth) | README/PRODUCT.md drift | Non-blocking; fix in parallel |

---

# Architecture Decision Records

## ADR-001: ExecutionContext Replaces WorkerContext

**Decision:** `ExecutionContext` is the canonical execution parameter object. `WorkerContext` is deprecated.

**Problem:** Two overlapping context objects exist — `WorkerContext` (in code, never used in production) and `ExecutionContext` (specified in K1.5, not yet implemented). Both serve the same purpose: threading execution parameters through a worker invocation.

**Alternatives considered:**
1. Keep both — WorkerContext for workers, ExecutionContext for the runtime
2. Extend WorkerContext with the missing fields
3. Replace WorkerContext with ExecutionContext entirely

**Why (1) rejected:** Two context objects doing the same job is a Single Source of Truth violation. Workers would need to translate between them.

**Why (2) rejected:** WorkerContext's name implies worker-scoping, but the context is actually created and owned by ExecutionRuntime. Extending it would mismatch name and ownership.

**Final decision:** Option 3. ExecutionContext replaces WorkerContext. `AbstractCognitiveWorker.execute()` signature changes from `WorkerContext` to `ExecutionContext`.

**Trade-offs:** Breaking change to `AbstractCognitiveWorker`'s interface. Mitigated by: only one Worker subclass exists (`MemoryCuratorWorker`), and it's never instantiated in production. Zero live consumers break.

**Future implications:** All future Workers use ExecutionContext from day one. No ambiguity about which context object to use.

**Constitution traceability:** Law 9 (Single Source of Truth), Law 4 (Determinism — one clear path, not two).

---

## ADR-002: CapabilityAdapter as Protocol, Not ABC

**Decision:** `CapabilityAdapter` is a `Protocol` (structural typing), not an ABC.

**Problem:** `Provider` (the existing inference adapter base class) already exists with a working inheritance chain. Introducing a new ABC would force all existing providers to change their base class.

**Alternatives considered:**
1. ABC (`class CapabilityAdapter(ABC)`) — explicit inheritance required
2. Protocol (`class CapabilityAdapter(Protocol)`) — structural satisfaction
3. Mixin (`class CapabilityAdapterMixin`) — no enforcement

**Why (1) rejected:** Would require `Provider` to inherit from `CapabilityAdapter`, touching every existing provider class. Law of Contract Stability argues against changing stable interfaces without necessity.

**Why (3) rejected:** No enforcement. A mixin can be forgotten or applied inconsistently.

**Final decision:** Option 2. Protocol gives structural satisfaction — `Provider` already has `is_available`, `health_score`, `mark_success()`, `mark_failure()`. Adding `invoke()` (wrapping the existing `generate()`) and `capability_id`/`adapter_id` properties makes it satisfy `CapabilityAdapter` without touching its class declaration.

**Trade-offs:** Weaker compile-time guarantees than an ABC. Accepted: runtime duck-typing is standard Python practice, and Protocol provides static-analysis support via mypy.

**Constitution traceability:** Law 10 (Contract Stability), Law 7 (Replaceability — Protocol-based matching allows more adapter implementations).

---

## ADR-003: Workers Are Not Long-Lived

**Decision:** Worker instances are created per `ExecutionRuntime.invoke()` call and do not persist across invocations.

**Problem:** Should Workers be stateful singletons (one instance, multiple calls) or ephemeral (one instance per call)?

**Alternatives considered:**
1. Singleton workers — one instance per type, reused across calls
2. Ephemeral workers — new instance per invocation
3. Pooled workers — a fixed pool of instances, reused

**Why (1) rejected:** Singleton workers accumulate hidden state across calls, violating Law 2 (Explicit State). The existing `_total_executions` counter on `AbstractCognitiveWorker` (`base.py:174`) is evidence of this risk — it counts across a worker's lifetime, which in a singleton model would be the entire process lifetime.

**Why (3) rejected:** Adds complexity (pool management, instance reset) without clear benefit at current scale. Pool pattern is justified for expensive-to-construct resources (database connections); Worker construction is cheap (Python object allocation + DI).

**Final decision:** Option 2. New instance per invocation. Constitution Part II: "Resources represent state; the kernel holds no meaningful state outside of resources." A Worker is not a Resource; it's a runtime computation.

**Trade-offs:** Per-call construction cost. Mitigated: construction is `O(1)` Python allocation + DI. `_total_executions` counter becomes meaningless on an ephemeral instance — replace with request-level metrics in EventStream.

**Constitution traceability:** Law 2 (Explicit State), Part II ("the kernel holds no meaningful state outside of resources").

---

## ADR-004: WorkflowRuntime Owns Retries, Not Workers

**Decision:** Retry logic lives in WorkflowRuntime (per-node RetryPolicy), not in Worker or ExecutionRuntime.

**Problem:** Where should retry logic live? Three candidates: Worker, ExecutionRuntime, WorkflowRuntime.

**Alternatives considered:**
1. Worker — each `_run()` implements its own retry logic
2. ExecutionRuntime — retries transparently around `Worker.execute()`
3. WorkflowRuntime — retries at the node level in the DAG

**Why (1) rejected:** Workers shouldn't know about infrastructure concerns like retry timing. Violates Law 3 (Separation of Concerns).

**Why (2) rejected:** A single execution (`invoke()`) should be one attempt. If the caller wants retries, it should express that intent — implicit retries in the runtime are "hidden side effects" that Law 4 (Determinism) prohibits.

**Final decision:** Option 3. WorkflowRuntime's `RetryPolicy` on `WorkflowNode` already specifies this cleanly. A standalone `ExecutionRuntime.invoke()` (not in a workflow) does exactly one attempt; the caller (or WorkflowRuntime) decides whether to retry.

**Trade-offs:** Single-invocation callers who want retries must implement their own retry loop (or wrap in a one-node workflow). Accepted: making retries explicit is a feature, not a cost.

**Note:** `BaseSkill` already has its own `_execute_with_retries()` (`skill_interface.py:107-115`). This is capability-level retry (retrying one LLM call within a skill), which is a different granularity from workflow-level retry (retrying an entire worker invocation). Both are correct and non-overlapping.

**Constitution traceability:** Law 3 (Separation of Concerns), Law 4 (Determinism).

---

## ADR-005: No Automatic Rollback in K2

**Decision:** WorkflowRuntime marks failed workflows as FAILED but does not automatically undo completed nodes.

**Problem:** If node 3 of 5 fails, should nodes 1 and 2 be automatically rolled back?

**Alternatives considered:**
1. Automatic compensating actions (saga pattern)
2. Manual compensating actions (each node declares its own undo logic)
3. No rollback — mark as failed, preserve completed node results

**Why (1) rejected:** Requires every Capability to have a well-defined inverse operation. Most cognitive operations (LLM inference, memory reads, analysis) don't have meaningful inverses. Designing automatic rollback for operations that are fundamentally non-reversible would be speculative architecture — directly against Law 8 (Evidence over Assumption).

**Why (2) rejected:** Same fundamental problem. Additionally, no existing node type has undo logic, and the research corpus hasn't identified a pattern for undoing cognitive operations.

**Final decision:** Option 3 for K2. Failed workflows are marked FAILED. Completed node results are preserved (valuable data). If compensating actions become necessary for specific use cases (e.g., a node that writes to an external system), they can be added as explicit error-branch nodes in the workflow DAG — not as a generic undo mechanism.

**Constitution traceability:** Law 8 (Evidence over Assumption — no rollback pattern proven yet), Law 11 (Failure Containment — failure at one node doesn't corrupt completed nodes' data).

---

## ADR-006: EventBus Subscribes to EventStream, Not the Reverse

**Decision:** The in-process `EventBus` (`core/event_bus.py`) subscribes to `EventStream` for delivery. EventStream is the single source of truth for events.

**Problem:** Two event systems exist: `EventBus` (in-process, no persistence) and `EventStream` (durable, SQLite-backed). They currently operate independently.

**Alternatives considered:**
1. Remove EventBus entirely, use only EventStream
2. EventBus subscribes to EventStream (EventStream is primary)
3. Keep them independent (current state)

**Why (1) rejected:** EventBus has different delivery semantics (sync/async in-process, no persistence overhead). Some consumers genuinely need low-latency in-process delivery without database round-trips.

**Why (3) rejected:** Contradicts Law 9 (Single Source of Truth). Events could be emitted to one system but not the other, creating blind spots.

**Final decision:** Option 2. All events go through `EventStream.append()` (durable, ordered). EventBus becomes a subscriber of EventStream for in-process fan-out. This preserves EventStream as the single source of truth while keeping EventBus's low-latency delivery for in-process consumers.

**Constitution traceability:** Law 9 (Single Source of Truth), Law 2 (Explicit State — all events are durably recorded).

---

# Frozen Public Contracts

## 7.1 ExecutionRuntime

| Property | Value |
|---|---|
| **Responsibilities** | Worker instantiation, ExecutionContext creation, Working Memory lifecycle, failure containment |
| **Public methods** | `invoke(worker_type: str, context: ExecutionContext) -> WorkerResult` |
| **Lifecycle** | Created at startup by composition root. One instance per process. |
| **Allowed dependencies** | WorkerRegistry, GovernanceKernel, EventStream |
| **Forbidden dependencies** | UnifiedMemory (Workers access memory, not the runtime), WorkflowRuntime (inverse direction) |
| **Extension points** | New Worker types registered via WorkerRegistry |
| **Compatibility guarantee** | `invoke()` signature is stable. Adding optional parameters is additive. |

## 7.2 WorkflowRuntime

| Property | Value |
|---|---|
| **Responsibilities** | DAG execution, node sequencing, retry logic, checkpoint/resume, HITL gates |
| **Public methods** | `execute(definition, context) -> WorkflowResult`, `resume(instance_id) -> WorkflowResult`, `cancel(instance_id) -> None` |
| **Lifecycle** | Created at startup by composition root. One instance per process. |
| **Allowed dependencies** | ExecutionRuntime, EventStream, GovernanceKernel |
| **Forbidden dependencies** | UnifiedMemory (indirect only, through Workers), CapabilityRegistry (indirect, through Workers) |
| **Extension points** | New node types (beyond worker/capability/approval/checkpoint) |
| **Compatibility guarantee** | `execute()` signature is stable. WorkflowDefinition format is versioned. |

## 7.3 Worker (AbstractCognitiveWorker)

| Property | Value |
|---|---|
| **Responsibilities** | Governance enforcement (template method), event emission, cognitive work execution |
| **Public methods** | `execute(context: ExecutionContext) -> WorkerResult` (non-overridable), `cancel() -> None`, `state -> WorkerState`, `stats() -> Dict` |
| **Subclass contract** | Override `_run(context: ExecutionContext) -> WorkerResult` only |
| **Lifecycle** | Created per invocation by ExecutionRuntime. Not reused. |
| **Allowed dependencies** | GovernanceKernel (injected), EventStream (injected), CapabilityRegistry (through ExecutionContext) |
| **Forbidden dependencies** | Other Workers directly (communicate through WorkflowRuntime), UnifiedMemory internals |
| **Extension points** | New Worker subclasses. `_run()` is the only extension point. |
| **Compatibility guarantee** | `execute()` → `_run()` template method pattern is permanent. |

## 7.4 ExecutionContext

| Property | Value |
|---|---|
| **Responsibilities** | Thread execution parameters, carry Working Memory, propagate cancellation |
| **Fields** | `request_id`, `worker_id`, `session_id`, `causal_chain`, `working_memory`, `governance_state`, `cancellation_token`, `workflow_id`, `parent_worker_id`, `metadata` |
| **Lifecycle** | Created by ExecutionRuntime. Passed to Worker. Cleaned up after execution. |
| **Mutability** | Working Memory is mutable during execution. All other fields are set at creation. |
| **Compatibility guarantee** | Fields are additive-only. No field will be removed. |

## 7.5 Capability (CapabilityAdapter Protocol)

| Property | Value |
|---|---|
| **Responsibilities** | Wrap one external system into the kernel's capability contract |
| **Required methods** | `invoke(request, context) -> Dict`, `is_available -> bool`, `health_score -> float`, `mark_success()`, `mark_failure()` |
| **Required properties** | `capability_id -> str`, `adapter_id -> str` |
| **Lifecycle** | Created at startup. Lives for the process lifetime. |
| **Compatibility guarantee** | Protocol fields are additive-only. |

## 7.6 CapabilityRegistry

| Property | Value |
|---|---|
| **Responsibilities** | Static index of Capabilities and their Adapters |
| **Public methods** | `register(capability_id, adapter)`, `resolve(capability_id) -> List[Adapter]`, `list_capabilities() -> List[str]` |
| **Lifecycle** | Created at startup, populated at startup, read-only after initialization. |
| **Allowed dependencies** | None (pure data structure) |
| **Compatibility guarantee** | `resolve()` and `register()` signatures are stable. |

## 7.7 Adapter (see CapabilityAdapter Protocol above)

## 7.8 Kernel

| Property | Value |
|---|---|
| **Responsibilities** | Service registration, governance evaluation, event routing, capability resolution |
| **Not a class** | A responsibility boundary, not a concrete type. The composition root (`main.py`) is the Kernel's construction site. |
| **Allowed services** | GovernanceKernel, EventStream, ExecutionRuntime, WorkflowRuntime, CapabilityRegistry, CapabilityResolver, WorkerRegistry |
| **Forbidden additions** | No new service without passing the Constitution's Admission Test (Part V) |

---

# Ownership Matrix

| Component | Canonical Owner | Creates | Mutates | Reads | Destroys |
|---|---|---|---|---|---|
| GovernanceKernel | Composition Root | Composition Root | GovernanceKernel (internal counters) | Everyone (evaluate_action) | Process exit |
| EventStream | Composition Root | Composition Root | EventStream (append) | Everyone (query, replay) | Process exit |
| UnifiedMemory | Composition Root | Composition Root | Workers (write) | Workers (search) | Never (append-only with L4 archive) |
| ExecutionRuntime | Composition Root | Composition Root | ExecutionRuntime (tracks active executions) | WorkflowRuntime, Orchestrator | Process exit |
| WorkflowRuntime | Composition Root | Composition Root | WorkflowRuntime (instance state) | Orchestrator | Process exit |
| CapabilityRegistry | Composition Root | Composition Root | Composition Root (registration at startup) | Workers (resolve) | Process exit |
| CapabilityResolver | Composition Root | Composition Root | None (stateless) | Workers (select) | Process exit |
| WorkerRegistry | Composition Root | Composition Root | Composition Root (registration at startup) | ExecutionRuntime (get) | Process exit |
| ExecutionContext | ExecutionRuntime | ExecutionRuntime.invoke() | Worker (Working Memory) | Worker | ExecutionRuntime (post-execution cleanup) |
| WorkingMemory | ExecutionContext | ExecutionRuntime | Worker | Worker | ExecutionRuntime |
| WorkflowInstance | WorkflowRuntime | WorkflowRuntime.execute() | WorkflowRuntime (state transitions) | WorkflowRuntime | WorkflowRuntime (completion/failure) |
| Worker instance | ExecutionRuntime | ExecutionRuntime.invoke() | Worker (internal state during _run) | ExecutionRuntime (result) | GC after invoke() returns |
| KnowledgeEntry | UnifiedMemory | UnifiedMemory.write() | UnifiedMemory.update() | Workers via search() | UnifiedMemory (archive to L4, never true delete) |
| StreamEvent | EventStream | EventStream.append() | Never (immutable, frozen dataclass) | Everyone | Never (append-only) |
| GovernanceResult | GovernanceKernel | evaluate_action() | Never (value object) | Caller | GC |

**No shared ownership.** Every component has exactly one canonical owner. No ambiguity.

---

# Dependency Graph

```
Layer 0: Governance & Events
  GovernanceKernel ─── [no dependencies on other kernel services]
  EventStream ──────── [no dependencies on other kernel services]

Layer 1: Registries
  CapabilityRegistry ─ [no runtime dependencies]
  WorkerRegistry ───── [no runtime dependencies]
  CapabilityResolver ─ [reads CapabilityRegistry at resolution time]

Layer 2: Execution
  ExecutionRuntime ──── depends on: WorkerRegistry, GovernanceKernel, EventStream
  WorkflowRuntime ───── depends on: ExecutionRuntime, EventStream, GovernanceKernel

Layer 3: Workers
  AbstractCognitiveWorker ── depends on: GovernanceKernel, EventStream
  Concrete Workers ──────── depend on: CapabilityRegistry (to resolve capabilities)

Layer 4: Capabilities
  CapabilityAdapter ──── depends on: external systems (via adapters)

Layer 5: Memory
  UnifiedMemory ─────── depends on: storage backends (SQLite, graph)
  RetrievalContextBuilder ─ depends on: UnifiedMemory, GraphRAGPipeline

Layer 6: External Systems
  Ollama, OpenAI, MCP servers, browsers, etc.
```

### Dependency Rules (Explicit)

| Dependency | Allowed? | Reason |
|---|---|---|
| Worker → CapabilityAdapter | ✅ Yes | Workers use capabilities to do work |
| Worker → UnifiedMemory | ✅ Yes | Workers read/write memory via public API |
| Worker → GovernanceKernel | ✅ Yes | Workers evaluate governance (template method) |
| Worker → EventStream | ✅ Yes | Workers emit events (template method) |
| ExecutionRuntime → WorkerRegistry | ✅ Yes | Runtime resolves worker types |
| WorkflowRuntime → ExecutionRuntime | ✅ Yes | Workflow dispatches to execution |
| CapabilityAdapter → UnifiedMemory | ❌ **Forbidden** | Adapters wrap external systems, not kernel services |
| CapabilityAdapter → Worker | ❌ **Forbidden** | Inverts the direction. A capability must be callable by any worker. |
| UnifiedMemory → WorkflowRuntime | ❌ **Forbidden** | Creates a cycle. Workflow depends on Memory (transitively through Workers). |
| UnifiedMemory → ExecutionRuntime | ❌ **Forbidden** | Memory is a service used by Workers, not by the runtime itself. |
| GovernanceKernel → Worker | ❌ **Forbidden** | Governance evaluates actions, doesn't invoke workers. |
| EventStream → Worker | ❌ **Forbidden** | Events are emitted by workers, not consumed to trigger them (subscribers are a separate concern). |

---

# Constitution Traceability Matrix

| Component | Constitutional Laws Satisfied | Specific Evidence |
|---|---|---|
| **ExecutionRuntime** | Law 3 (Separation of Concerns), Law 11 (Failure Containment) | Separates execution from coordination; failures are result values, never exceptions |
| **ExecutionContext** | Law 2 (Explicit State), Law 4 (Determinism) | All execution state explicitly threaded; `causal_chain` enables replay |
| **Working Memory** | Law 2 (Explicit State), Law 9 (Single Source of Truth) | Per-execution scope prevents hidden cross-request state; one location for scratch data |
| **CancellationToken** | Law 2 (Explicit State), Law 5 (User Sovereignty) | Cancellation is explicit cooperative state; user can cancel at any time |
| **GovernanceKernel** | Law 1 (Bounded Autonomy) | Template method makes governance bypass structurally impossible |
| **EventStream** | Law 2 (Explicit State), Law 4 (Determinism), Law 6 (Explainability) | Immutable event log enables replay, audit, and explanation |
| **CapabilityRegistry** | Law 7 (Replaceability) | Any adapter can satisfy any capability; no vendor lock-in |
| **CapabilityAdapter (Protocol)** | Law 7 (Replaceability), Law 10 (Contract Stability) | Structural typing lets existing code satisfy the contract without changes |
| **WorkflowRuntime** | Law 2 (Explicit State), Law 11 (Failure Containment) | Per-node events; node failure doesn't crash the workflow |
| **RetryPolicy** | Law 4 (Determinism) | Retry behavior is declarative, predictable, inspectable |
| **Worker (template method)** | Law 1 (Bounded Autonomy), Law 2 (Explicit State), Law 3 (Separation of Concerns) | Governance first, events always, execution delegated |
| **WorkerRegistry** | Law 7 (Replaceability), Law 10 (Contract Stability) | New worker types are additive; old types deprecated through a window |
| **Resource Protocol (K1.6)** | Invariant 4 (identity, lifecycle, provenance) | KnowledgeEntry satisfies Protocol; future CapabilityMetadata and WorkflowInstance will too |

---

# Interface Inventory

Every interface required before K2 begins. No more, no less.

| Interface | File (New/Modify) | Status |
|---|---|---|
| `ExecutionContext` | NEW: `core/runtime/execution_context.py` | Specified (§1.1) |
| `CancellationToken` | NEW: `core/runtime/cancellation.py` | Specified (§1.1) |
| `WorkingMemory` | NEW: `core/runtime/working_memory.py` | Specified (§1.1) |
| `ExecutionRuntime` | NEW: `core/runtime/execution_runtime.py` | Specified (§1.1) |
| `WorkerRegistry` | NEW: `core/runtime/worker_registry.py` | Specified (K1.5 §3) |
| `CapabilityAdapter` (Protocol) | NEW: `core/capabilities/adapter.py` | Specified (§2.4) |
| `CapabilityRegistry` | NEW: `core/capabilities/registry.py` | Specified (§2.2) |
| `CapabilityResolver` | NEW: `core/capabilities/resolver.py` | Specified (§2.3) |
| `WorkflowDefinition` | NEW: `core/workflow/definition.py` | Specified (§3.1) |
| `WorkflowNode` | NEW: `core/workflow/definition.py` | Specified (§3.1) |
| `WorkflowEdge` | NEW: `core/workflow/definition.py` | Specified (§3.1) |
| `WorkflowInstance` | NEW: `core/workflow/instance.py` | Specified (§3.1) |
| `WorkflowRuntime` | NEW: `core/workflow/runtime.py` | Specified (§3.2) |
| `RetryPolicy` | NEW: `core/workflow/definition.py` | Specified (§3.1) |
| `WorkflowResult` | NEW: `core/workflow/result.py` | Specified (§3.2) |
| `AbstractCognitiveWorker` | MODIFY: `core/workers/base.py` | Change `WorkerContext` → `ExecutionContext` |
| `PlannerWorker` | NEW: `core/workers/planner.py` | K2.1 |

**Total new files: 11. Total modified files: 1. Total interfaces: 16.**

No speculative interfaces. Every interface above is required by a specific K2 implementation milestone.

---

# Remaining Architectural Risks

## Must Resolve Before K2

| Risk | Severity | Mitigation |
|---|---|---|
| Wiring Workers into the hot path regresses the `return_exceptions=True` containment behavior | Critical | Explicit regression test asserting per-execution containment survives the migration |

## Can Resolve During K2

| Risk | Severity | Mitigation |
|---|---|---|
| Two retrieval stacks merged incorrectly (K1.5 §11) | High | A/B comparison during K2 before cutover |
| `MemoryGovernor` interface redesign breaks something undiscovered | Medium | Full regression suite before/after |
| `classify()` → Capability resolution migration path unclear | Medium | Implement as a Capability wrapper first, then replace |
| README/PRODUCT.md drift | Medium | Fix in parallel with K2, doesn't block |

## Can Defer Until Later

| Risk | Severity | Reasoning |
|---|---|---|
| Distributed execution (Scheduler) | Low | Years out per roadmap; `asyncio.gather` sufficient at current scale |
| Automatic compensating actions (saga pattern) | Low | No proven need; cognitive operations are mostly non-reversible |
| Hot-reload of capabilities | Low | Cognitive Phase concern, not kernel concern |
| Durable workflow execution across process restarts | Medium | Checkpoint/resume architecture is designed, but true durability requires EventStream-based replay. K2 builds the checkpoint infrastructure; full durability is K3+. |

---

# K2 Readiness Assessment

| Area | Status | Explanation |
|---|---|---|
| Resource Model | ✅ Ready | K1.6 froze it. Protocol-based, one object needs field alignment. |
| Memory | ✅ Ready | UnifiedMemory is live, correct, stable. Public API frozen. |
| Retrieval | ✅ Ready | Both stacks built and tested. K2 wires the sophisticated one into the live path. |
| Graph | ✅ Ready | GraphIndexer, GraphEngine, entity extraction all built. Backend registered at startup. |
| Execution | ✅ Ready | ExecutionRuntime fully specified. Every field, method, and lifecycle documented. |
| Workflow | ✅ Ready | WorkflowRuntime fully specified. DAG model, retry, checkpoint, resume all defined. |
| Workers | ✅ Ready | AbstractCognitiveWorker is production-quality. One subclass exists. Template method pattern is the correct, permanent design. |
| Capability | ✅ Ready | CapabilityRegistry, CapabilityResolver, CapabilityAdapter all specified. Generalizes the existing, working provider_mesh pattern. |
| Governance | ✅ Ready | GovernanceKernel is live. 3 of 5 governors exist. MemoryGovernor needs interface reconciliation (scoped, not a blocker). |
| Events | ✅ Ready | EventStream is live, stable, WAL-backed, with pub/sub and replay. |
| Identity | ⏳ Deferred | Self-Identity Model is explicitly Cognitive Phase, not Kernel Phase. |
| Planning | ⏳ Deferred | PlannerWorker is a K2.1 implementation target, but the planning *engine* is Cognitive Phase. |
| Reflection | ⏳ Deferred | ReflectionWorker is K2.4+. Reflection *engine* is Cognitive Phase. |
| External Knowledge | ⏳ Deferred | Knowledge acquisition pipeline is Cognitive Phase. |

---

# Architecture Freeze Checklist

| Question | Answer | Justification |
|---|---|---|
| **Can K2 begin?** | **Yes** | Every interface required for K2 is specified. Every ownership boundary is explicit. Every dependency direction is documented. |
| **Will K2 require changing public contracts?** | **One change:** `WorkerContext` → `ExecutionContext` in `AbstractCognitiveWorker.execute()` | Zero live consumers break (MemoryCuratorWorker never instantiated in production). |
| **Will K2 require inventing new abstractions?** | **No** | Every abstraction needed is documented in this specification. If K2 discovers a genuinely missing abstraction, it's a blocker worth escalating — not expected. |
| **Will K2 require ownership changes?** | **No** | Ownership matrix (§8) is canonical. ExecutionRuntime and WorkflowRuntime are new owners, not replacements of existing ones. |
| **Will K2 require dependency changes?** | **No** | Dependency graph (§9) documents every allowed and forbidden dependency. No existing dependency needs to change direction. |
| **Will K2 require architectural redesign?** | **No** | K2 implements the architecture specified here. If a fundamental flaw is discovered during implementation, it should be flagged as a K2 finding and resolved before K3 validation. |

---

# Kernel Architecture Baseline v1.0

## Layer Diagram

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
│  │  (GovernanceK) (EventStr) (Cap/Worker) (ExecRT)  │   │
│  │                                       (WkflwRT)  │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Memory Service                       │   │
│  │  (UnifiedMemory, RetrievalContextBuilder, Graph)  │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│               Substrate (OS, Hardware)                   │
│            (accessed ONLY through Adapters)              │
└─────────────────────────────────────────────────────────┘
```

## Execution Flow

```
1. Request → Orchestrator
2. Orchestrator → ExecutionRuntime.invoke() or WorkflowRuntime.execute()
3. ExecutionRuntime → WorkerRegistry.get() → Worker.execute()
4. Worker.execute() → GovernanceKernel.evaluate_action()
5. Worker._run() → CapabilityRegistry.resolve() → CapabilityAdapter.invoke()
6. Worker._run() → UnifiedMemory.search() / .write()
7. Worker.execute() → EventStream.append() (lifecycle events)
8. ExecutionRuntime → WorkerResult → Orchestrator
9. Orchestrator → Response
```

## Core Components

| Component | Purpose | Status |
|---|---|---|
| GovernanceKernel | Central governance enforcement | Live, 3 governors |
| EventStream | Immutable event log with pub/sub and replay | Live, SQLite WAL |
| UnifiedMemory | Canonical memory (L0-L4) | Live, production |
| ExecutionRuntime | Worker invocation and lifecycle | K2 — specified |
| WorkflowRuntime | DAG execution with retries and checkpoints | K2 — specified |
| CapabilityRegistry | Static index of capabilities/adapters | K2 — specified |
| CapabilityResolver | Runtime adapter selection | K2 — specified |
| WorkerRegistry | Static index of worker types | K2 — specified |
| AbstractCognitiveWorker | Worker base class (template method) | Live, 1 subclass |
| RetrievalContextBuilder | Structured context assembly | Built, disconnected |
| GraphRAGPipeline | Graph-augmented retrieval | Built, disconnected |

## Ownership Model

See §8 (Ownership Matrix) — single owner per component, no shared ownership.

## Dependency Rules

See §9 (Dependency Graph) — every dependency documented with allowed/forbidden classification.

## Public Interfaces

See §7 (Frozen Public Contracts) and §11 (Interface Inventory) — 16 interfaces, all specified.

## Canonical Terminology

See K1.5 §1 (Kernel Vocabulary Freeze) — 42 canonical terms defined. Key clarifications:
- **Worker** performs cognitive work; **Capability** performs atomic work
- **Adapter** wraps external systems; **Provider** is an inference-specific Adapter
- **Skill** is a local-code Adapter; **Tool** is its MCP-facing name
- **Module** is the legacy term being phased out
- **Working Memory** is per-execution scratch; **Memory** is persistent (UnifiedMemory)
- **Context** is a transient view assembled from Memory; not a store itself

---

# Updated Canonical Roadmap

## Architecture Phase

- ✅ K1 — Kernel Runtime Audit
- ✅ K1.5 — Kernel Runtime Specification
- ✅ K1.6 — Canonical Resource Model
- ✅ **K1.7–K1.11 — Final Architecture Freeze** (this document)
- ⏳ K4 — Freeze Contracts (formalization of this specification into code-level contracts)

## Kernel Implementation

- **K2.1 — Execution Runtime** (unblocks everything else)
  - ExecutionContext, CancellationToken, WorkingMemory
  - ExecutionRuntime.invoke()
  - WorkerRegistry
  - Wire AbstractCognitiveWorker to use ExecutionContext
  - Wire MemoryCuratorWorker into composition root
  - PlannerWorker (minimal: wraps current classify→dispatch as a plan)
  - **Affected files:** NEW `core/runtime/execution_context.py`, `core/runtime/cancellation.py`, `core/runtime/working_memory.py`, `core/runtime/execution_runtime.py`, `core/runtime/worker_registry.py`, `core/workers/planner.py`. MODIFY `core/workers/base.py`, `core/orchestrator.py`, `main.py`.
  - **Complexity:** High (touches primary production path)

- **K2.2 — Workflow Runtime** (parallel with K2.3 once K2.1 lands)
  - WorkflowDefinition, WorkflowNode, WorkflowEdge, WorkflowInstance
  - WorkflowRuntime.execute(), resume(), cancel()
  - RetryPolicy
  - Wire RetrievalContextBuilder/GraphRAGPipeline into live path (K1.5 §13)
  - **Affected files:** NEW `core/workflow/definition.py`, `core/workflow/instance.py`, `core/workflow/runtime.py`, `core/workflow/result.py`. MODIFY `core/memory/assembly.py` (switch to RCB).
  - **Complexity:** Medium (additive, wraps existing decomposer.py)

- **K2.3 — Capability Registry** (parallel with K2.2)
  - CapabilityAdapter Protocol
  - CapabilityRegistry, CapabilityResolver
  - Wrap existing Providers as CapabilityAdapters
  - Wrap BaseSkill as CapabilityAdapter
  - **Affected files:** NEW `core/capabilities/adapter.py`, `core/capabilities/registry.py`, `core/capabilities/resolver.py`. MODIFY `core/provider_mesh.py` (add adapter wrapper).
  - **Complexity:** Low (Provider already has the right shape)

- **K2.4 — Governance Completion**
  - Reconcile MemoryGovernor to Governor interface
  - Implement OrchestrationGovernor, AgentGovernor, ConversationGuardrails
  - Register all governors in GovernanceKernel
  - **Affected files:** MODIFY `core/governance/memory_governor.py`. NEW `core/governance/orchestration_governor.py`, `core/governance/agent_governor.py`, `core/governance/conversation_guardrails.py`.
  - **Complexity:** Medium (MemoryGovernor interface change; new governors are additive)

## Validation

- **K3 — Kernel Validation & Compliance Audit**
  - Constitution compliance review of implemented code
  - Regression testing
  - Performance baseline

## Contract Freeze

- **K4 — Freeze Contracts (Architecture Lock)**
  - Formalize all public contracts with version numbers
  - Document deprecation policy
  - Lock interfaces — additive changes only after K4

## Core Cognitive Runtime (v4.3.6+)

- Self Identity Model
- Reflection Engine
- Planning Engine
- Skills Runtime
- External Knowledge Pipeline
- Autonomous Multi-Agent Runtime
- Advanced GraphRAG / KAG
- Provenance Completion
- Web UI & Developer Experience

---

# Implementation Impact Summary

| K2 Milestone | New Files | Modified Files | Files Untouched | Migration Complexity | Expected Difficulty |
|---|---|---|---|---|---|
| K2.1 Execution Runtime | 6 | 3 | All memory, graph, retrieval, governance, events | High — touches production path | Hard |
| K2.2 Workflow Runtime | 4 | 1 | All except assembly.py | Medium — additive | Medium |
| K2.3 Capability Registry | 3 | 1 | All except provider_mesh.py | Low — wrapping existing code | Easy |
| K2.4 Governance | 3 | 1 | All except memory_governor.py | Medium — interface change | Medium |
| **Total** | **16 new files** | **6 modified files** | **~40+ files intentionally untouched** | | |

---

*K1.7–K1.11 complete. No implementation performed. No repository files modified. The architecture is frozen. K4 becomes a formalization exercise. K2 can proceed as implementation — not invention.*
