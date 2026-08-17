<img width="1536" height="1024" alt="a5c8335f-e65d-4698-a789-4e1c05752f22" src="https://github.com/user-attachments/assets/2830440e-a250-45ee-95f6-095530b7ddd1" />
# OCBrain

<div align="center">

**Overclocked Brain — a local-first cognitive runtime for intelligent systems**

[![License](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)

</div>

---

## What is OCBrain?

OCBrain is a **local-first cognitive runtime** designed to turn raw user intent into governed, verifiable, executable plans.

It is not simply a chatbot, model router, or collection of agents.

OCBrain provides the runtime substrate around intelligence:

* intent interpretation
* constraint extraction
* semantic planning
* capability discovery
* plan compilation
* validation and governance
* execution coordination
* memory and learning
* event-driven state
* reflection and evaluation
* supervision and recovery

The long-term goal is a **Universal Cognitive Kernel** that can operate across domains, models, and execution environments while keeping reasoning, governance, and execution boundaries explicit.

---

## Current Architecture

OCBrain is currently being developed around the **K4.2 Cognitive Front-End** architecture.

The K4.2 pipeline transforms an incoming request into a structured cognitive execution process:

```text
User Request
     │
     ▼
┌─────────────────────┐
│ Cognitive Front-End │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Intent Interpretation│
│ + Semantic Model     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Constraint Extraction│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Capability Discovery │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Planner              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Plan Compilation     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Validation /         │
│ Governance           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Cognitive Runtime    │
│ Execution            │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
  Events      Memory
     │           │
     └─────┬─────┘
           ▼
┌─────────────────────┐
│ Reflection /         │
│ Evaluation           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Supervisor           │
└─────────────────────┘
```

The important architectural principle is that **reasoning, governance, and execution are separate concerns**.

A model may propose an action.

The runtime decides whether that action is valid, permitted, executable, and safe.

---

## Architectural Principles

### 1. Intent before execution

OCBrain does not treat a natural-language request as an executable command.

A request is first interpreted into structured semantic information.

The system distinguishes between:

```text
Raw Request
Semantic Description
Intent
Constraints
Required Capabilities
Plan
Executable Operations
```

This separation prevents the language layer from becoming the execution layer.

---

### 2. Capabilities are explicit

OCBrain does not assume that an LLM can perform an operation merely because it can describe it.

Capabilities are discovered through explicit capability contracts and registries.

A capability describes what the runtime can actually perform.

Adapters provide concrete implementations.

The kernel coordinates them.

```text
Cognitive Kernel
      │
      ▼
Capability Contract
      │
      ▼
Capability Registry
      │
      ▼
Adapter
      │
      ▼
Concrete Implementation
```

This allows the same cognitive architecture to operate across very different environments.

Examples include:

* filesystem operations
* web access
* GitHub operations
* database operations
* APIs
* industrial systems
* automation platforms
* future SCADA integrations

---

### 3. Planning is separate from execution

The planner produces a structured plan.

The plan is then compiled into executable operations and passed through validation and governance before execution.

This creates a deliberate boundary:

```text
Reasoning
   ↓
Plan
   ↓
Compilation
   ↓
Validation
   ↓
Governance
   ↓
Execution
```

An invalid or impossible plan must fail as a cognitive/runtime decision rather than becoming an uncontrolled execution attempt.

---

### 4. Governance is a runtime primitive

Governance is not an optional post-processing feature.

Validation gates exist at important boundaries of the runtime.

Examples include:

* capability validity
* parameter validity
* policy compliance
* execution constraints
* lifecycle state
* failure handling
* plan consistency

The runtime should reject invalid state transitions rather than attempting to recover from fundamentally invalid plans after execution has begun.

---

### 5. Events are first-class state

OCBrain uses structured events to represent important state transitions and runtime activity.

Events provide:

* observability
* auditability
* integration points
* worker coordination
* deterministic testing
* future external consumers

The event system is intended to remain independent from reasoning and execution logic.

---

### 6. Memory is part of cognition, not merely storage

Memory is used to provide the runtime with persistent context and learned information.

The architectural direction moves beyond the original monolithic memory model toward explicit cognitive memory services and controlled read/write paths.

Memory operations should therefore be:

* structured
* observable
* governed
* recoverable
* testable

---

## The Cognitive Runtime

The Cognitive Runtime is the execution environment surrounding the Cognitive Front-End.

It is responsible for turning validated cognitive state into actual runtime behavior.

Conceptually:

```text
                ┌──────────────────────┐
                │   Cognitive Front-End│
                │                      │
Request ───────►│ Interpret            │
                │ Constrain            │
                │ Discover             │
                │ Plan                 │
                │ Compile              │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Validation /          │
                │ Governance            │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │   Cognitive Runtime  │
                │                      │
                │ Scheduler            │
                │ Workers              │
                │ Event Store          │
                │ State                │
                │ Memory               │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ External Capabilities│
                │ / Adapters           │
                └──────────────────────┘
```

The runtime does not depend on a single LLM provider.

Models are inference components inside the larger cognitive system.

---

## Model Providers

OCBrain is designed to be **local-first**.

The architecture supports provider abstraction so that cognitive components can use available local or external inference backends without coupling the kernel to a single vendor.

Typical development environments may use:

* Ollama
* Mistral-family models
* Llama-family models
* other local inference providers

Provider selection is an implementation concern of the runtime and should not redefine the cognitive architecture.

---

## K4.2 Cognitive Front-End

K4.2 introduces the cognitive front-end that sits between natural-language input and runtime execution.

The major architectural components are:

### Intent Interpretation

Transforms the raw request into a structured representation of what the user is trying to accomplish.

The representation distinguishes the original request from the semantic interpretation used for downstream reasoning.

### Constraint Extraction

Extracts explicit and implicit constraints that affect planning and execution.

Examples:

* required output format
* environmental restrictions
* temporal constraints
* resource limits
* user-specified exclusions
* execution boundaries

### Capability Discovery

Determines which registered capabilities can satisfy the interpreted intent.

Discovery is contract-driven rather than based solely on textual similarity.

### Planner

Builds a structured plan from:

* intent
* constraints
* available capabilities
* runtime context
* memory

Planner failure is an explicit cognitive state.

It is not silently converted into arbitrary execution.

### Plan Compilation

Converts a cognitive plan into the runtime representation required for execution.

Compilation is a distinct boundary because a valid abstract plan is not automatically a valid executable plan.

### ValidationGate

Validation gates enforce runtime invariants before execution.

They provide a shared mechanism for validating structured operations and lifecycle transitions.

### Learning and Memory Wiring

Validated cognitive activity can produce structured information for memory and future learning.

Learning must remain subordinate to runtime governance and explicit safety boundaries.

### Reflection and Evaluation

Post-execution evaluation examines outcomes and produces structured feedback for the runtime.

### Supervisor

The Supervisor coordinates recovery and escalation when cognitive or runtime processing encounters conditions that cannot be resolved locally.

---

## Failure Handling

OCBrain treats failure handling as part of the architecture rather than an afterthought.

The runtime distinguishes between different failure classes, including failures originating from:

* planning
* compilation
* validation
* capability resolution
* execution
* dependencies
* runtime infrastructure
* governance

A failure should produce explicit state and events so that the system can:

1. detect the failure
2. classify it
3. preserve relevant context
4. decide whether recovery is possible
5. escalate when required
6. remain auditable

The goal is **controlled degradation**, not silent fallback.

---

## Memory and Learning

OCBrain is intended to become progressively better at reasoning and execution without turning self-modification into uncontrolled autonomy.

Learning is therefore treated as a governed subsystem.

The architecture favors:

```text
Observe
   ↓
Evaluate
   ↓
Record
   ↓
Learn
   ↓
Validate
   ↓
Promote
```

rather than unconstrained automatic modification of the runtime.

The system should never treat "the model generated it" as equivalent to "the runtime verified it."

---

## Event Backbone

The event backbone provides durable structured communication between runtime components.

Important runtime transitions should become inspectable events.

Typical categories include:

```text
intent.*
constraint.*
capability.*
planner.*
plan.*
validation.*
execution.*
memory.*
learning.*
supervisor.*
```

The event backbone is intended to support:

* durable state transitions
* deterministic testing
* audit trails
* worker coordination
* observability
* future integrations

---

## Testing Philosophy

OCBrain emphasizes deterministic and architecture-level testing.

Tests should verify not only whether a function returns the expected value, but whether the runtime preserves its architectural invariants.

Important test categories include:

* contract tests
* integration tests
* lifecycle tests
* failure injection
* governance tests
* planner tests
* capability discovery tests
* event durability tests
* persistence tests
* regression tests

The project also uses controlled failure injection to test runtime behavior without introducing duplicate schedulers, executors, or event systems merely for testing.

---

## Repository Structure

The repository is evolving toward a separation between cognitive contracts, runtime infrastructure, capabilities, memory, governance, and interfaces.

Conceptually:

```text
ocbrain/
├── core/
│   ├── cognitive/
│   │   ├── intent/
│   │   ├── constraints/
│   │   ├── discovery/
│   │   ├── planner/
│   │   ├── compilation/
│   │   ├── validation/
│   │   ├── reflection/
│   │   └── supervisor/
│   │
│   ├── runtime/
│   │   ├── scheduler/
│   │   ├── workers/
│   │   ├── state/
│   │   └── lifecycle/
│   │
│   ├── events/
│   ├── governance/
│   ├── memory/
│   └── providers/
│
├── capabilities/
│   ├── registry/
│   ├── contracts/
│   └── adapters/
│
├── interface/
│   ├── api/
│   ├── cli/
│   └── ui/
│
├── tests/
│
├── docs/
│   ├── architecture/
│   ├── contracts/
│   └── development/
│
├── pyproject.toml
├── LICENSE
└── README.md
```

The exact directory structure may evolve during implementation; the architectural boundaries are the important part.

---

## Installation

OCBrain is currently developed primarily as a Python application.

### Requirements

* Python 3.11+
* Local inference provider such as Ollama for local model execution
* Platform-specific runtime dependencies as required by individual capabilities

### Development setup

```bash
git clone https://github.com/1h0lde4/OCBrain.git
cd OCBrain

python -m venv .venv
```

Activate the virtual environment and install the development dependencies according to the current `pyproject.toml`.

Then run the test suite:

```bash
pytest
```

> Installation commands and packaging targets are intentionally kept minimal here. The repository's packaging configuration is the source of truth.

---

## Development Status

OCBrain is an actively evolving research and engineering project.

### Current architectural focus

**K4.2 — Cognitive Front-End**

The current work focuses on completing and hardening the cognitive pipeline, including:

* intent interpretation
* constraint extraction
* capability discovery
* planner completion
* shared validation
* learning wiring
* user cognitive model
* plan compilation
* reflection/evaluation workers
* supervision
* end-to-end integration

The architecture is being implemented incrementally and independently verified as each subsystem is completed.

### Stability statement

OCBrain should currently be considered **development software**, not a finished general-purpose autonomous agent platform.

Architecture and contracts are prioritized over feature count.

---

## Design Direction

The long-term OCBrain architecture is based on a simple principle:

> **The model reasons. The runtime verifies. The kernel governs. The capability executes.**

This separation allows OCBrain to grow from a local cognitive runtime into a general-purpose cognitive substrate without binding the system to a specific model, agent framework, provider, or domain.

Future domains may include:

* software engineering
* research
* operations
* enterprise automation
* industrial systems
* SCADA environments
* autonomous information monitoring
* other capability-driven systems

The same kernel should be able to coordinate very different environments while preserving the same fundamental cognitive and governance contracts.

---

## Roadmap

The roadmap is organized around architectural maturity rather than a list of disconnected features.

### K4.2

Complete and harden the Cognitive Front-End.

### Post-K4.2

Strengthen:

* runtime reliability
* governance
* memory integration
* reflection
* supervision
* capability ecosystem
* observability
* deterministic simulation and testing

### Long-term

Evolve toward a reusable **Universal Cognitive Kernel** capable of supporting multiple domains and execution substrates.

Potential future subsystems include proactive cognitive services that observe selected domains and emit structured events into the runtime while leaving reasoning, verification, governance, and action decisions to the Cognitive Runtime.

---

## Contributing

OCBrain is an architecture-driven project.

Contributions should preserve the core separation between:

```text
Contracts
  ↓
Cognition
  ↓
Governance
  ↓
Runtime
  ↓
Capabilities
```

Changes that introduce hidden execution paths, duplicate runtime infrastructure, bypass governance, or couple the kernel directly to implementation-specific details should be avoided.

Before making architectural changes, consult the relevant architecture and contract documentation in `docs/`.

---

## License

OCBrain is licensed under the MIT License.

See [LICENSE](LICENSE).

---

## Links

* Repository: https://github.com/1h0lde4/OpenClaw-Brain
* Issues: https://github.com/1h0lde4/OpenClaw-Brain/issues
* Releases: https://github.com/1h0lde4/OpenClaw-Brain/releases
