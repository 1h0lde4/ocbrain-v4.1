# PROJECT_INSTRUCTIONS.md — OCBrain v4.0

## Purpose

This document defines the operational engineering rules, implementation constraints, architectural discipline, execution philosophy, development workflow, and autonomous coding expectations for all contributors, AI agents, orchestration systems, and coding runtimes interacting with the OCBrain codebase.

This is not documentation.

This is the governing execution contract for the project.

All human developers, Claude Code sessions, autonomous coding agents, workflow workers, and MCP tools must follow these instructions.

---

# 1. Project Mission

OCBrain exists to build a:

* local-first cognitive operating system,
* governed autonomous execution platform,
* event-sourced intelligence runtime,
* modular skill ecosystem,
* distributed inference fabric,
* replayable cognitive architecture.

The system must support:

* autonomous reasoning,
* workflow orchestration,
* cognitive memory,
* safe self-improvement,
* distributed execution,
* human governance,
* long-horizon task execution.

The architecture is inspired and validated by:

* n8n,
* OpenHands,
* Dify,
* Flowise,
* Langflow,
* Activepieces,
* Open WebUI,
* DeepSeek-V3,
* exo,
* NeMo,
* generative_agents,
* anthropics/skills,
* repomix,
* AutoGPT,
* Vercel AI SDK.

---

# 2. Foundational Laws

These are immutable project laws.

Violating them is considered an architectural failure.

---

## LAW 1 — Governance Before Capability

No autonomous capability may bypass governance.

Governance includes:

* permission enforcement,
* recursion limits,
* approval checkpoints,
* budget enforcement,
* policy validation,
* execution isolation,
* audit logging.

If a feature increases capability without increasing governance visibility, redesign it.

---

## LAW 2 — Event Sourcing Over Hidden State

All meaningful cognitive activity must emit immutable events.

Never rely exclusively on:

* hidden runtime memory,
* mutable singleton state,
* opaque agent reasoning.

Every major operation must be:

* observable,
* replayable,
* inspectable,
* recoverable.

---

## LAW 3 — Isolation Over Convenience

Never prioritize convenience over execution safety.

Arbitrary execution must always be sandboxed.

No inline execution of:

* generated Python,
* generated JavaScript,
* shell commands,
* workflow-generated code.

Always use:

* subprocesses,
* containers,
* task runners,
* restricted environments.

---

## LAW 4 — Determinism Over Magic

The system must remain:

* inspectable,
* explicit,
* understandable,
* reproducible.

Avoid:

* hidden framework behavior,
* magic dependency injection,
* implicit orchestration,
* hidden side effects,
* uncontrolled abstractions.

---

## LAW 5 — Local-First By Default

All architecture decisions should assume:

* local inference,
* local memory,
* local orchestration,
* local workflows,
* local observability.

Cloud services are optional accelerators, not core dependencies.

---

# 3. Mandatory Runtime Architecture

OCBrain MUST preserve the validated 4-process runtime model.

```text
Main Process
├── orchestration
├── API
├── workflow coordination
├── state transitions
└── governance entrypoints

Worker Pool
├── workflow execution
├── skill execution
├── cognitive workers
└── queue consumers

Webhook Process
├── event ingestion
├── trigger handling
└── async external events

Task Runner
├── sandboxed code execution
├── isolated subprocess runtime
├── JS/Python execution
└── restricted execution environment
```

Never collapse these responsibilities into a monolith.

---

# 4. Architectural Priorities

The project priority order is:

```text
Governance
→ Replayability
→ Isolation
→ Observability
→ Reliability
→ Determinism
→ Extensibility
→ Performance
→ UX
```

If performance conflicts with governance or replayability, governance wins.

---

# 5. Engineering Standards

## Required Standards

Every module must:

* use full typing,
* expose explicit interfaces,
* emit structured logs,
* support observability,
* avoid hidden side effects,
* support testing,
* support replayability.

---

## Forbidden Practices

Never introduce:

❌ giant God classes
❌ hidden mutable globals
❌ recursive uncontrolled agent loops
❌ synchronous blocking I/O in async paths
❌ silent exception swallowing
❌ implicit orchestration
❌ unbounded memory growth
❌ unversioned prompts
❌ inline arbitrary execution
❌ framework-driven hidden state
❌ auto-self-modification without governance

---

# 6. Core System Rules

## 6.1 Governance Kernel Rules

The GovernanceKernel is mandatory.

Every autonomous action must pass through governance evaluation.

### Required Governors

```text
OrchestrationGovernor
MemoryGovernor
AgentGovernor
EvolutionGovernor
ConversationGuardrails
```

### Governance Responsibilities

* recursion depth limits,
* budget enforcement,
* approval requirements,
* execution authorization,
* memory protection,
* self-modification prevention,
* policy enforcement.

No worker may bypass governors.

---

## 6.2 Workflow Engine Rules

The workflow engine is DAG-based.

Never build recursive autonomous spaghetti loops.

### Workflow Requirements

Every workflow must support:

* serialization,
* replay,
* interruption,
* checkpointing,
* node caching,
* partial execution,
* retry policies,
* error branches,
* observability hooks.

---

## 6.3 Node Execution Rules

Every workflow node must define:

```python
class WorkflowNode:
    node_type: str
    execution_mode: str
    retry_policy: RetryPolicy
    guardrails: GuardrailsConfig
    approval: HITLConfig

    async def execute(self, context):
        ...
```

### Node Constraints

Nodes must:

* be composable,
* support deterministic execution where possible,
* emit events,
* support cancellation,
* support retries.

---

## 6.4 Partial Execution Rules

Workflow execution must support diff-aware reruns.

Only changed nodes should re-execute.

All node outputs should support:

* persistent caching,
* deterministic cache keys,
* replay loading.

---

# 7. Cognitive Worker Instructions

Workers are specialized cognitive runtimes.

Workers are NOT free-form chatbots.

---

## 7.1 Canonical Worker Types

```text
PlannerWorker
ReActWorker
ReflectionWorker
CoderWorker
EvaluatorWorker
BrowserWorker
MemoryCuratorWorker
SupervisorWorker
```

Do not create arbitrary worker types without architectural justification.

---

## 7.2 Worker Requirements

Every worker must:

* emit events,
* stream progress,
* expose state,
* support interruption,
* respect governance,
* support evaluation,
* support observability.

---

## 7.3 Reflection Rules

Reflection workers must:

* critique outputs,
* detect inconsistencies,
* validate reasoning,
* request retries,
* escalate uncertainty.

Reflection is mandatory for high-risk workflows.

---

## 7.4 CoderWorker Rules

CoderWorker must:

* operate in sandboxed environments,
* use repomix context compression,
* emit code modification events,
* support rollback,
* support checkpointing,
* avoid uncontrolled filesystem access.

Never allow unrestricted repository mutation.

---

# 8. Memory System Instructions

Memory is a first-class architecture layer.

---

## 8.1 Memory Layers

```text
L0 — Working Memory
L1 — Episodic Memory
L2 — Semantic Memory
L3 — Procedural Memory
L4 — Immutable Archive
```

Never collapse all memory into a single vector database.

---

## 8.2 Episodic Memory Rules

Every episodic memory must include:

```python
@dataclass
class EpisodicMemory:
    id: str
    content: str
    timestamp: datetime
    importance: float
    embedding: list[float]
    provenance: str
    source_event_id: str
    entities: list[str]
```

No memory without provenance.

---

## 8.3 Retrieval Rules

Memory retrieval must use hybrid retrieval:

```text
BM25 + semantic embeddings + RRF fusion
```

Embedding-only retrieval is prohibited.

---

## 8.4 Memory Scoring

Canonical formula:

```python
score = (
    alpha_recency * recency_decay +
    alpha_importance * importance +
    alpha_relevance * semantic_similarity
)
```

This model is foundational to coherent long-term cognition.

---

# 9. Skill System Instructions

Skills are executable cognitive artifacts.

---

## 9.1 Skill Rules

Every skill must:

* be versioned,
* expose metadata,
* define schemas,
* support validation,
* support replayability,
* support MCP exposure,
* support isolated execution.

---

## 9.2 Skill File Format

Every skill should support export as `.skill.md`.

Canonical structure:

```yaml
---
name: "example_skill"
version: "1.0.0"
category: "analysis"
description: "Skill description"
author: "OCBrain"
mcp_server: true
execution_mode: "task_runner"
---
```

---

## 9.3 Skill Execution Modes

Supported modes:

```text
inline
task_runner
docker
```

Default to isolated execution for anything untrusted.

---

## 9.4 MCP Strategy

Everything should eventually be exposable as MCP:

* skills,
* workflows,
* tools,
* memory providers,
* orchestration services,
* cognitive workers.

MCP-native architecture is mandatory.

---

# 10. Distributed Compute Instructions

The compute layer is local-first.

Preferred stack:

```text
LocalAI
exo
DeepSeek-V3.1
airllm
```

Goals:

* distributed inference,
* sparse MoE execution,
* local orchestration,
* scalable worker distribution.

---

## 10.1 Inference Rules

Inference providers must support:

* streaming,
* cancellation,
* observability,
* retries,
* fallback routing,
* structured outputs.

---

## 10.2 Model Selection Rules

Prefer:

* open-weight models,
* MoE architectures,
* local deployment compatibility,
* quantization support,
* efficient context management.

Avoid closed vendor lock-in.

---

# 11. Knowledge Acquisition Rules

The acquisition pipeline is:

```text
crawl
→ extract
→ normalize
→ score
→ quarantine
→ validate
→ consolidate
→ memory
```

Never inject raw web data directly into memory.

---

## 11.1 Provenance Requirements

All acquired knowledge must preserve:

* source,
* timestamp,
* extraction method,
* trust score,
* transformation history.

---

## 11.2 Trust Pipeline Rules

Every knowledge item must support:

* quality scoring,
* contradiction detection,
* deduplication,
* provenance validation,
* quarantine.

---

# 12. Observability Rules

Observability is mandatory infrastructure.

---

## 12.1 Required Observability

Every major subsystem must emit:

* traces,
* metrics,
* logs,
* events,
* evaluation artifacts.

---

## 12.2 Mandatory Integrations

Preferred stack:

```text
OpenTelemetry
Langfuse
structured JSON logs
workflow replay traces
```

---

## 12.3 Event Replay

All major workflows must support:

* replay,
* deterministic reconstruction,
* debugging inspection,
* execution visualization.

Replayability is a core design constraint.

---

# 13. Autonomous Evolution Rules

Self-improvement is heavily restricted.

---

## 13.1 Evolution Constraints

No autonomous evolution may:

* deploy automatically,
* modify governance,
* bypass approval,
* mutate production code directly.

---

## 13.2 Evolution Workflow

Required pipeline:

```text
simulate
→ evaluate
→ benchmark
→ safety validate
→ human approve
→ deploy
→ monitor
→ rollback capable
```

---

## 13.3 Trajectory Learning

Successful trajectories may become:

* training datasets,
* procedural memory,
* workflow templates,
* reusable skills.

All trajectory ingestion must preserve provenance.

---

# 14. Security Instructions

Security is architecture, not middleware.

---

## 14.1 Sandboxing Rules

All untrusted execution must support:

* memory limits,
* timeouts,
* filesystem restrictions,
* import whitelists,
* network restrictions,
* subprocess isolation.

---

## 14.2 Secret Management

Never:

* hardcode secrets,
* expose tokens in logs,
* store raw secrets in events,
* commit credentials.

Use:

* environment variables,
* runtime secret injection,
* encrypted secret providers.

---

## 14.3 Permission Model

Workers should receive:

* minimum required permissions,
* scoped filesystem access,
* scoped tool access,
* scoped execution rights.

Principle of least privilege is mandatory.

---

# 15. Prompt System Instructions

Prompts are infrastructure.

Prompts must:

* be versioned,
* be reviewable,
* support rollback,
* support templating,
* define constraints,
* define output schemas.

---

## 15.1 Prompt Structure

Canonical template:

```python
class PromptTemplate:
    role: str
    task: str
    constraints: list[str]
    format: str
    examples: list[dict]
```

---

## 15.2 Prompt Rules

Avoid:

* gigantic monolithic prompts,
* hidden prompt injection,
* runtime prompt mutation without tracking.

All prompt changes should be observable.

---

# 16. Testing Instructions

Every major subsystem must support:

```text
unit tests
integration tests
workflow replay tests
benchmark evaluations
safety tests
failure recovery tests
```

---

## 16.1 Workflow Testing

Every workflow should support:

* deterministic replay,
* fixture-based validation,
* failure injection,
* partial rerun testing.

---

## 16.2 Evaluation Standards

Evaluate:

```text
correctness
safety
efficiency
reproducibility
latency
resource usage
```

---

# 17. Repository Organization Rules

Prefer domain-driven organization.

Suggested structure:

```text
/core
/governance
/events
/workflows
/workers
/skills
/memory
/knowledge
/runtime
/compute
/observability
/evaluation
/prompts
/tests
```

Avoid giant flat directories.

---

# 18. Development Workflow Instructions

## 18.1 Incremental Development

Build in phases.

Do not skip foundational infrastructure.

Order matters.

---

## 18.2 Current Phase
## 18.2.1 Roadmap Override Mechanism

The roadmap embedded in PROJECT_INSTRUCTIONS.md is historical context and may become outdated.

The authoritative development status is defined by:

CURRENT_STATE.md
IMPLEMENTATION_ROADMAP.md

When these files exist:

Treat them as the source of truth.
Do not revert development to older roadmap phases.
Do not assume the current phase from PROJECT_INSTRUCTIONS.md.
Verify active work using CURRENT_STATE.md before planning or implementation.

Until those files exist:

Use the most recent approved implementation plan.
---

## 18.3 PR / Change Rules

Every major change should:

* define architectural impact,
* define governance implications,
* define replay implications,
* define observability implications,
* define rollback strategy.

18.4 Context Efficiency & Documentation-First Development
Purpose

As OCBrain grows, repository-wide analysis becomes increasingly expensive.

The objective is to reduce redundant context consumption while preserving architectural correctness, audit quality, and engineering rigor.

Documentation should reduce unnecessary rediscovery, not prevent investigation.

18.4.1 Documentation-First Navigation

Before inspecting source code, consult project knowledge artifacts when available.

Preferred order:

CURRENT_STATE.md
IMPLEMENTATION_ROADMAP.md
ARCHITECTURE_DECISIONS.md
PROJECT_INDEX.md
KNOWN_ISSUES.md
MEMORY_ARCHITECTURE.md

These documents should be treated as project memory.

Source code remains authoritative for implementation details.

18.4.2 Documentation Infrastructure

The repository should maintain:

PROJECT_INDEX.md
CURRENT_STATE.md
ARCHITECTURE_DECISIONS.md
KNOWN_ISSUES.md
IMPLEMENTATION_ROADMAP.md
MEMORY_ARCHITECTURE.md

These files become operational infrastructure rather than optional documentation.

When missing, they should be created during the dedicated Documentation Infrastructure phase after completion of the current memory architecture milestone.

18.4.3 Current Roadmap Authority

The active implementation roadmap is defined by:

IMPLEMENTATION_ROADMAP.md
CURRENT_STATE.md

These files supersede outdated roadmap references embedded elsewhere in the repository.

Before starting new work:

Verify current phase.
Verify completed milestones.
Verify next planned milestone.

Do not revert to older roadmap stages unless explicitly instructed.

18.4.4 Incremental Investigation

Prefer:

Targeted file inspection
Subsystem-level analysis
Diff-aware review
Incremental audits

before performing repository-wide analysis.

However:

Repository-wide analysis is permitted whenever required for:

Cross-cutting bugs
Architecture validation
Security reviews
Major audits
Dependency analysis
System-wide refactors

Correctness takes priority over token efficiency.

18.4.5 Architecture Decision Preservation

When an architectural decision is marked:

FINAL

inside ARCHITECTURE_DECISIONS.md:

treat it as authoritative,
build upon it,
avoid repeatedly re-evaluating it,

unless:

A verified defect exists
A dependency changes
A governance concern exists
A human requests reconsideration
18.4.6 Audit Reuse

Before launching a new audit:

Review:

KNOWN_ISSUES.md
Audit reports
Remediation logs
Architecture reviews

Do not repeatedly audit unchanged subsystems without justification.

Reuse previous findings whenever possible.

18.4.7 Session Continuity

Before ending a significant work session:

Update:

CURRENT_STATE.md
IMPLEMENTATION_ROADMAP.md
KNOWN_ISSUES.md

so future sessions can resume without reconstructing project history.

18.4.8 Diff-Oriented Development

When implementing changes:

Prefer:

Affected files only
Affected subsystems only
Minimal necessary modifications

Avoid unrelated refactors.

Every significant change should document:

Architectural impact
Risk assessment
Reason for change
18.5 Documentation Infrastructure Phase

After completion of:

v4.3.5 Graph Memory
v4.3.6 Memory Curator Worker
v4.3.7 Testing & Integration

and after the current audit remediation work is complete, create a dedicated Documentation Infrastructure phase.

Deliverables:

PROJECT_INDEX.md
CURRENT_STATE.md
ARCHITECTURE_DECISIONS.md
KNOWN_ISSUES.md
IMPLEMENTATION_ROADMAP.md
MEMORY_ARCHITECTURE.md

These files become mandatory project infrastructure and the primary context source for future development sessions.

---

# 19. Explicit Anti-Patterns

The following are forbidden architectural directions:

❌ uncontrolled recursive agents
❌ opaque orchestration
❌ inline arbitrary code execution
❌ cloud-only dependencies
❌ non-versioned prompts
❌ embedding-only retrieval
❌ hidden mutable state
❌ unobservable workflows
❌ governance as future work
❌ monolithic orchestration runtimes
❌ direct autonomous production mutation
❌ non-replayable systems
❌ missing provenance
❌ non-isolated code execution

---

# 20. Elite Engineering Execution Mode

All AI coding agents operating inside this repository must behave as senior principal engineers working on mission-critical infrastructure.

This includes:

* deep architectural reasoning,
* defensive engineering,
* systems thinking,
* production-grade implementation discipline,
* rigorous validation,
* extreme attention to edge cases,
* proactive failure prevention.

The expectation is not merely to generate code.

The expectation is to engineer reliable systems.

---

## 20.1 Required Engineering Behavior

AI coding agents must:

* think before implementing,
* analyze architectural consequences,
* preserve system coherence,
* anticipate failure modes,
* identify hidden coupling,
* minimize technical debt,
* prefer maintainability over cleverness,
* prefer explicitness over abstraction,
* design for scale from the beginning,
* validate assumptions before coding,
* preserve backward compatibility when possible.

Never generate code impulsively.

---

## 20.2 Mandatory Implementation Process

Before implementing any feature:

```text
1. Understand the architecture
2. Identify affected layers
3. Identify governance implications
4. Identify replay implications
5. Identify observability implications
6. Identify security implications
7. Design interfaces
8. Design event flow
9. Design failure handling
10. Implement incrementally
11. Add validation and tests
12. Verify integration consistency
```

Implementation without systems analysis is prohibited.

---

## 20.3 Code Quality Expectations

Generated code must be:

```text
production-grade
fully typed
modular
observable
deterministic where possible
replayable
testable
well-structured
resource-conscious
failure-aware
```

Code should resemble work produced by:

* distributed systems engineers,
* infrastructure architects,
* compiler/runtime engineers,
* production AI platform teams.

---

## 20.4 Failure-Oriented Engineering

AI agents must actively search for:

* race conditions,
* deadlocks,
* memory leaks,
* hidden state mutation,
* replay inconsistencies,
* async cancellation bugs,
* serialization failures,
* governance bypass paths,
* sandbox escape risks,
* queue starvation,
* distributed coordination failures,
* event ordering issues,
* retry storms,
* recursion explosions,
* observability blind spots.

Assume systems fail under scale.

Engineer defensively.

---

## 20.5 Architectural Discipline

Never introduce:

❌ architecture drift
❌ shortcut implementations
❌ temporary hacks without tracking
❌ hidden orchestration logic
❌ magical abstractions
❌ premature microservices
❌ framework-driven lock-in
❌ undocumented side effects
❌ implicit shared state
❌ non-replayable execution paths

Every major abstraction must justify its existence.

---

## 20.6 Systems Thinking Requirements

All implementations must consider:

```text
runtime behavior
failure recovery
distributed execution
memory impact
observability
security
governance
replayability
extensibility
operational maintenance
future evolution
```

The system must remain coherent as complexity increases.

---

## 20.7 Autonomous Coding Constraints

AI coding agents may:

* propose architecture improvements,
* refactor safely,
* generate tests,
* optimize workflows,
* improve observability,
* improve modularity.

AI coding agents may NOT:

* bypass governance,
* silently rewrite core architecture,
* remove safety mechanisms,
* weaken isolation boundaries,
* introduce opaque execution,
* deploy unreviewed self-modification.

---

## 20.8 Preferred Engineering Style

Preferred engineering style:

```text
calm
precise
systematic
deeply analytical
minimal but extensible
high-signal
low-complexity
architecture-first
```

Avoid:

```text
overengineering
clever hacks
fragile abstractions
tutorial-style implementations
prototype-quality infrastructure
```

---

## 20.9 Definition of "Done"

A feature is NOT complete when it merely works.

A feature is complete only when:

* architecture is preserved,
* governance is enforced,
* observability exists,
* replayability is maintained,
* edge cases are handled,
* failure recovery exists,
* interfaces are typed,
* tests exist,
* documentation exists,
* integration behavior is verified.

---

## 20.10 Prime Directive

The AI must operate like a world-class principal engineer designing critical cognitive infrastructure.

Prioritize:

```text
correctness
safety
architecture
reliability
maintainability
scalability
observability
```

Never sacrifice long-term system integrity for short-term implementation speed.

---

# 21. Final Operational Directive

OCBrain is being designed as:

* a governed cognitive runtime,
* a replayable autonomous execution system,
* a modular MCP-native intelligence platform,
* a local-first distributed AI operating layer,
* a safe self-improving architecture.

All engineering decisions must reinforce:

```text
Governed
Replayable
Observable
Composable
Deterministic
Local-First
MCP-Native
Event-Sourced
Sandboxed
```

If a proposed implementation violates these principles:

```text
reject the implementation
redesign the architecture
preserve the laws
```
