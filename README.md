<img width="1536" height="1024" alt="a5c8335f-e65d-4698-a789-4e1c05752f22" src="https://github.com/user-attachments/assets/2830440e-a250-45ee-95f6-095530b7ddd1" />
# OCBrain

<div align="center">

# **OCBrain**

### **Overclocked Brain — a local-first cognitive runtime for intelligent systems**

**From intent to governed action.**

[![License](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![Architecture](https://img.shields.io/badge/architecture-K4.2-blueviolet?style=flat-square)](#current-architecture)
[![Status](https://img.shields.io/badge/status-active%20development-orange?style=flat-square)](#development-status)

</div>

---

## Table of Contents

* [What is OCBrain?](#what-is-ocbrain)
* [The Core Idea](#the-core-idea)
* [Current Architecture](#current-architecture)
* [Architectural Principles](#architectural-principles)
* [K4.2 Cognitive Front-End](#k42-cognitive-front-end)
* [Cognitive Runtime](#cognitive-runtime)
* [Capabilities and Adapters](#capabilities-and-adapters)
* [Models and Providers](#models-and-providers)
* [Memory and Learning](#memory-and-learning)
* [Event Backbone](#event-backbone)
* [Security & Privacy](#security--privacy)
* [Schemas & Contracts](#schemas--contracts)
* [Failure Handling and Recovery](#failure-handling-and-recovery)
* [Testing Philosophy](#testing-philosophy)
* [Where OCBrain Is Going](#where-ocbrain-is-going)
* [A Glimpse of the Future](#a-glimpse-of-the-future)
* [Universal Cognitive Kernel](#universal-cognitive-kernel)
* [Development Status](#development-status)
* [Roadmap](#roadmap)
* [Repository Structure](#repository-structure)
* [Installation](#installation)
* [Contributing](#contributing)
* [License](#license)

---

# What is OCBrain?

OCBrain is a **local-first cognitive runtime** designed to turn human or machine intent into **structured, governed, verifiable, and executable behavior**.

It is not simply:

* a chatbot
* an LLM wrapper
* an agent framework
* a collection of specialized agents
* a model router

OCBrain is being built as a **cognitive substrate**: an environment in which intelligence can interpret information, reason about goals and constraints, discover available capabilities, construct plans, verify those plans, execute through explicit boundaries, observe outcomes, remember experience, learn from results, and recover from failure.

The long-term objective is a **Universal Cognitive Kernel** that can support different models, capabilities, environments, and domains without changing the fundamental cognitive and governance model.

---

# The Core Idea

Most AI applications follow a simplified pattern:

```text
User
  ↓
LLM
  ↓
Answer / Action
```

OCBrain is designed around a much stricter pipeline:

```text
Input
  ↓
Intent Interpretation
  ↓
Constraint Extraction
  ↓
Capability Discovery
  ↓
Planning
  ↓
Plan Compilation
  ↓
Validation
  ↓
Governance
  ↓
Execution
  ↓
Observation
  ↓
Memory / Learning / Reflection
  ↓
Supervision
```

The distinction is fundamental.

An AI model may propose what should happen.

**The runtime determines what is actually valid, permitted, executable, observable, and recoverable.**

---

# Current Architecture

OCBrain is currently being developed around the **K4.2 Cognitive Front-End** architecture.

K4.2 establishes the cognitive boundary between natural-language intent and runtime execution.

```text
                         OCBRAIN K4.2

┌──────────────────────────────────────────────────────────┐
│                    HUMAN / SYSTEM INPUT                  │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│                  COGNITIVE FRONT-END                     │
│                                                          │
│  Intent Interpretation                                   │
│            ↓                                             │
│  Constraint Extraction                                   │
│            ↓                                             │
│  Capability Discovery                                    │
│            ↓                                             │
│  Planning                                                 │
│            ↓                                             │
│  Plan Compilation                                         │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 VALIDATION / GOVERNANCE                  │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│                    COGNITIVE RUNTIME                     │
│                                                          │
│     Scheduler • Workers • State • Events • Memory        │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 CAPABILITIES / ADAPTERS                  │
└──────────────────────────────────────────────────────────┘
```

The architecture deliberately separates:

```text
Reasoning
Governance
Execution
```

This separation is one of the central design constraints of OCBrain.

---

# Architectural Principles

## 1. Intent Before Execution

Natural language is **not an executable command**.

OCBrain explicitly separates:

```text
Raw Request
Semantic Description
Intent
Constraints
Required Capabilities
Plan
Executable Operations
```

This protects the runtime from treating model-generated language as trusted execution instructions.

---

## 2. Capabilities Are Explicit

The runtime does not assume that an LLM can perform an operation merely because the LLM knows how to describe that operation.

Capabilities are represented through explicit contracts and registries.

A capability defines **what can be done**.

An adapter defines **how it is done**.

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
Concrete System
```

This abstraction allows the same cognitive architecture to operate across very different environments.

Potential domains include:

* filesystem operations
* GitHub
* databases
* HTTP APIs
* browsers
* local applications
* enterprise systems
* industrial systems
* SCADA environments
* future robotic or physical systems

---

## 3. Planning Is Separate From Execution

The planner produces an **abstract cognitive plan**.

The runtime then determines whether that plan can be compiled and executed.

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

This allows OCBrain to reject:

* impossible plans
* incomplete plans
* unsupported plans
* invalid capability requests
* malformed operations
* unauthorized actions
* inconsistent execution state

before they become runtime actions.

---

## 4. Governance Is a Runtime Primitive

Governance is not a cosmetic layer around the system.

It is part of the runtime architecture.

Validation and governance boundaries exist to ensure that cognitive output does not automatically become system behavior.

A core OCBrain principle is:

> **Intelligence proposes. The runtime verifies.**

---

## 5. Events Are First-Class

Important runtime transitions are represented as structured events.

Events provide the foundation for:

* observability
* auditability
* worker coordination
* deterministic testing
* persistent state transitions
* external integrations

Typical event families include:

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

---

## 6. Memory Is a Cognitive Subsystem

Memory is not merely a database attached to an assistant.

It is a cognitive subsystem responsible for preserving, retrieving, consolidating, and evaluating information that can affect future cognition.

The architectural direction emphasizes explicit:

* memory records
* read paths
* write paths
* persistence boundaries
* consolidation
* evaluation
* governance
* learning integration

Memory should remain observable and testable rather than becoming opaque hidden state.

---

## 7. Failure Is a State, Not an Exception to Hide

OCBrain treats failure handling as part of the architecture.

A failed cognitive operation should become structured runtime information that can be:

* detected
* classified
* observed
* recovered
* escalated
* recorded

rather than silently swallowed or converted into an arbitrary fallback.

---

# K4.2 Cognitive Front-End

K4.2 is the architectural layer that transforms language into structured cognition.

## Intent Interpretation

Transforms the incoming request into a structured representation of what the user or calling system is attempting to accomplish.

The system should distinguish between what was literally said and what the cognitive system believes the request semantically means.

---

## Constraint Extraction

Extracts the conditions that must remain true throughout planning and execution.

Examples include:

* temporal constraints
* resource restrictions
* required output format
* environmental restrictions
* user requirements
* forbidden actions
* execution boundaries

Constraints become explicit cognitive data rather than remaining buried inside free-form language.

---

## Capability Discovery

Determines which registered capabilities can potentially satisfy the interpreted intent.

Discovery is based on structured capability contracts and multiple signals rather than textual matching alone.

A capability must be:

1. discoverable
2. contractually valid
3. compatible with the request
4. available to the runtime

before it can participate in a plan.

---

## Planner

The planner constructs a structured plan from:

* intent
* semantic information
* constraints
* available capabilities
* memory
* runtime context

Planning failure is an explicit cognitive state.

It is not silently converted into arbitrary execution.

---

## Plan Compilation

Compilation transforms an abstract plan into the runtime representation required for execution.

This boundary matters because:

> A plan that makes semantic sense is not automatically a plan that the runtime can safely execute.

---

## Validation

Validation gates enforce runtime invariants before execution.

They verify that cognitive structures and executable representations satisfy the contracts expected by downstream components.

---

## Reflection and Evaluation

After execution, outcomes can be evaluated and converted into structured feedback.

This allows OCBrain to distinguish:

```text
What was planned
What was executed
What actually happened
What was learned
```

---

## Supervision

The Supervisor coordinates recovery and escalation when a cognitive or runtime problem cannot be resolved locally.

The Supervisor is a coordination and governance mechanism, not an alternative hidden execution engine.

---

# Cognitive Runtime

The Cognitive Runtime surrounds the Cognitive Front-End.

Its responsibility is to make cognition:

* durable
* observable
* governed
* executable
* recoverable

Conceptually:

```text
                ┌─────────────────────────┐
                │  COGNITIVE FRONT-END    │
                │                         │
Request ───────►│ Intent                  │
                │ Constraints             │
                │ Discovery               │
                │ Planning                │
                │ Compilation             │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │ VALIDATION / GOVERNANCE │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │     COGNITIVE RUNTIME   │
                │                         │
                │ Scheduler               │
                │ Workers                 │
                │ State                   │
                │ Events                  │
                │ Memory                  │
                └────────────┬────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │  CAPABILITIES / ADAPTERS│
                └─────────────────────────┘
```

The runtime is intentionally independent from any single LLM provider.

---

# Capabilities and Adapters

OCBrain separates **what a system can do** from **how an external system implements it**.

```text
Capability
   │
   ├── Contract
   │
   └── Adapter
            │
            ▼
      External System
```

This permits the same capability to have different implementations.

For example:

```text
GitHub Capability
   ├── GitHub API Adapter
   └── Future Enterprise Adapter
```

or:

```text
Database Capability
   ├── PostgreSQL Adapter
   ├── SQLite Adapter
   └── Enterprise Database Adapter
```

The kernel should not depend on the implementation details of these systems.

---

# Models and Providers

OCBrain is **local-first** and intentionally avoids making the cognitive architecture dependent on a particular model vendor.

The runtime may use:

* local LLMs
* multiple inference providers
* specialized models
* multimodal models
* domain-specific models

Examples during development may include local providers such as Ollama and models from the Mistral or Llama families.

Models are treated as **cognitive components inside the runtime**, not as the runtime itself.

The architecture should remain valid when a model is replaced.

---

# Memory and Learning

OCBrain is designed to improve over time, but learning is treated as a **governed process**, not unrestricted self-modification.

The desired lifecycle is:

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

This means:

* generated output is not automatically trusted
* learned information is not automatically promoted
* runtime behavior is not modified without explicit validation boundaries
* memory changes should remain observable
* learning should be reversible where appropriate

The long-term objective is **controlled cognitive improvement**, not uncontrolled autonomy.

---

# Event Backbone

The event backbone provides structured communication between runtime components.

It supports:

* durable state transitions
* observability
* audit trails
* worker coordination
* deterministic testing
* runtime integration
* future external consumers

Events are intended to remain independent of specific cognitive implementations.

This makes it possible for future systems to subscribe to meaningful runtime events without directly coupling themselves to internal components.

---

# Security & Privacy

Security and privacy are architectural concerns in OCBrain, not documentation afterthoughts.

The system is designed around a **local-first trust model** and explicit boundaries between untrusted input, cognitive processing, governance, and execution.

## Local-first by design

OCBrain is intended to keep sensitive data within the user's or organization's infrastructure whenever the configured architecture permits it.

External network communication should be explicit and capability-driven rather than an invisible side effect of reasoning.

---

## Trust boundaries

A simplified trust model is:

```text
                    UNTRUSTED / EXTERNAL
                             │
             ┌───────────────┼────────────────┐
             │               │                │
        User Input      External Events    Model Output
             │               │                │
             └───────────────┼────────────────┘
                             ▼
                    Schema Validation
                             │
                             ▼
                  Structured Cognitive State
                             │
                             ▼
                   Validation / Governance
                             │
                             ▼
                    Trusted Runtime State
                             │
                             ▼
                     Capability Adapter
                             │
                             ▼
                      External System
```

The exact implementation may evolve, but the trust boundary is fundamental.

---

## The model is not the security boundary

An LLM should not be trusted simply because it generated structured-looking output.

Model output can be:

* incomplete
* incorrect
* contradictory
* manipulated
* prompt-injected
* semantically ambiguous

Therefore, model output must cross explicit validation and governance boundaries before it can influence execution.

---

## Capability isolation

A model should not gain arbitrary access to the machine merely by asking for it.

Execution occurs through registered capabilities and adapters.

This creates an explicit boundary:

```text
Model
  ↓
Cognitive Request
  ↓
Capability Contract
  ↓
Governance
  ↓
Adapter
  ↓
External System
```

---

## Fail-closed behavior

Where appropriate, invalid or ambiguous state should fail closed rather than silently becoming an executable action.

Examples include:

* invalid capability requests
* malformed plans
* invalid parameters
* missing required constraints
* governance rejection
* unsupported operations

---

## Auditability

Important cognitive and runtime transitions should be represented in structured events.

This provides a foundation for answering questions such as:

```text
What did the system receive?
What did it infer?
What did it plan?
Why was a capability selected?
What was validated?
What was executed?
What happened afterward?
What did the system learn?
```

This is particularly important for enterprise and industrial environments.

---

## Data minimization

OCBrain should retain only the information required for the configured cognitive and operational objectives.

Future privacy controls should be able to govern:

* memory retention
* event retention
* learning data
* external access
* capability permissions
* sensitive data propagation

---

## No hidden autonomy

A core security principle is:

> **No subsystem should silently acquire the ability to act simply because another subsystem can reason about an action.**

Reasoning authority and execution authority remain distinct.

---

# Schemas & Contracts

Schemas are an important part of OCBrain's security and correctness model.

They provide the typed boundaries through which cognitive and runtime state moves.

The purpose of the schemas is not merely serialization.

They provide:

* structural validation
* explicit contracts
* predictable state transitions
* integration boundaries
* testability
* security checks
* compatibility guarantees

---

## Core schema families

OCBrain's cognitive architecture is organized around structured objects such as:

| Schema family                 | Purpose                                                |
| ----------------------------- | ------------------------------------------------------ |
| **Intent**                    | Represents the interpreted objective                   |
| **Constraints**               | Represents conditions that must be respected           |
| **Capability**                | Describes an available ability                         |
| **Discovery Result**          | Represents capability matching/discovery               |
| **Plan**                      | Represents the abstract cognitive plan                 |
| **Compiled Plan / Operation** | Represents executable runtime form                     |
| **Validation Result**         | Represents contract validation                         |
| **Governance Decision**       | Represents approval/rejection/escalation state         |
| **Event**                     | Represents durable runtime transitions                 |
| **Memory Record**             | Represents structured persistent cognitive information |
| **Reflection / Evaluation**   | Represents outcome analysis                            |
| **Supervisor State**          | Represents escalation/recovery state                   |

---

## Why schemas matter

Without explicit schemas, a cognitive runtime can gradually become a collection of implicit assumptions:

```text
String
   ↓
Some interpretation
   ↓
Some dictionary
   ↓
Some model output
   ↓
Some action
```

OCBrain instead aims for:

```text
Structured Request
      ↓
Validated Contract
      ↓
Structured Cognitive Object
      ↓
Validated Transition
      ↓
Governed Runtime Object
      ↓
Controlled Execution
```

This provides a much stronger foundation for both security and long-term maintainability.

---

## What is public

OCBrain should document the **purpose and boundaries** of its core schemas publicly.

Detailed contract definitions should live in the dedicated architecture and contract documentation.

Sensitive implementation details should not be required knowledge for understanding the security model.

The public documentation should explain:

* what each schema represents
* which subsystem owns it
* who may create it
* who may modify it
* which validation boundary protects it
* which transitions are allowed

---

# Failure Handling and Recovery

OCBrain treats failure as structured runtime information.

Possible failure classes include:

* intent interpretation failure
* constraint failure
* capability discovery failure
* planner failure
* compilation failure
* validation failure
* governance rejection
* execution failure
* dependency failure
* runtime infrastructure failure

The general recovery model is:

```text
Detect
  ↓
Classify
  ↓
Preserve Context
  ↓
Evaluate Recovery
  ↓
Recover / Escalate
  ↓
Record Outcome
```

The objective is **controlled degradation**, not silent fallback.

---

# Testing Philosophy

Architecture-level correctness matters more than feature count.

OCBrain therefore emphasizes:

* contract tests
* integration tests
* lifecycle tests
* persistence tests
* governance tests
* deterministic testing
* failure injection
* event integrity
* regression testing

The runtime should remain testable under both normal and deliberately degraded conditions.

Testing should verify not only whether a function returns a value, but whether **architectural invariants survive failure and integration**.

---

# Where OCBrain Is Going

K4.2 is not the final destination.

It is the point where OCBrain begins transitioning from an AI application into a **general cognitive runtime**.

The longer trajectory is:

```text
AI Application
      ↓
Cognitive Front-End
      ↓
Cognitive Runtime
      ↓
Governed Cognitive Infrastructure
      ↓
Universal Cognitive Kernel
      ↓
Multi-domain Cognitive Fabric
```

The ambition is not simply to make the assistant smarter.

The ambition is to make intelligence **usable as infrastructure**.

---

# A Glimpse of the Future

Imagine giving OCBrain an objective rather than a single question.

Instead of:

> "What happened to production?"

you might eventually give it:

> "Monitor the production system and identify significant deviations. Investigate probable causes, respect operational policies, and escalate anything requiring human authorization."

OCBrain could then continuously:

```text
Observe
   ↓
Detect
   ↓
Correlate
   ↓
Interpret
   ↓
Plan
   ↓
Validate
   ↓
Govern
   ↓
Act / Ask
   ↓
Observe Outcome
   ↓
Learn
```

This is fundamentally different from a traditional chatbot.

---

## Persistent Cognitive Services

A future OCBrain architecture may contain **Persistent Cognitive Services (PCS)**.

A PCS continuously observes a specific domain and emits structured events.

Examples could include:

```text
GitHub Service
   ↓
Issues / PRs / repository changes
   ↓
Structured Events
```

```text
Market Service
   ↓
Market conditions
   ↓
Structured Events
```

```text
Industrial Service
   ↓
Telemetry / alarms / state changes
   ↓
Structured Events
```

The PCS does **not** become an unrestricted autonomous agent.

Instead:

```text
Persistent Cognitive Service
          ↓
       Event
          ↓
   Cognitive Runtime
          ↓
Reason / Verify / Govern
          ↓
Decision
          ↓
Action or Human Escalation
```

This preserves the central OCBrain boundary:

> **Observation can be continuous without making execution uncontrolled.**

---

# Enterprise Cognitive Control Plane

A future OCBrain instance could sit above heterogeneous enterprise systems:

```text
ERP ────────┐
MES ────────┤
SCADA ──────┤
Databases ──┤
GitHub ─────┤
Cloud ──────┤
Tickets ────┤
Documents ──┤
Sensors ────┤
Human Input ┤
            │
            ▼
      ┌───────────────┐
      │    OCBrain    │
      │               │
      │ Understand    │
      │ Correlate     │
      │ Reason        │
      │ Plan          │
      │ Govern        │
      │ Execute       │
      │ Observe       │
      └───────────────┘
```

Instead of building a separate autonomous agent for every system, capabilities and adapters could expose those environments through a common cognitive substrate.

---

# Industrial Cognition

One particularly ambitious future direction is industrial environments.

Imagine an OCBrain instance connected to:

* production systems
* machine telemetry
* quality data
* maintenance systems
* inventory
* scheduling
* ERP/MES
* operator reports

A future diagnostic cycle might look like:

```text
Machine anomaly detected
        ↓
Event generated
        ↓
OCBrain correlates:
  • telemetry
  • machine history
  • production state
  • maintenance records
  • inventory
  • operator reports
        ↓
Hypotheses generated
        ↓
Capabilities discovered
        ↓
Diagnostic plan
        ↓
Governance evaluation
        ↓
Recommendation / permitted action
        ↓
Outcome observed
        ↓
Learning
```

The objective is not simply:

> "AI controls a factory."

The objective is:

> **A governed cognitive layer understands the state of a complex system and coordinates the capabilities that already exist.**

---

# From Agents to a Cognitive Fabric

Today's AI ecosystem is strongly centered around individual agents.

OCBrain's longer-term direction is broader.

It could become a **cognitive fabric** in which multiple specialized cognitive services communicate through common contracts and events.

```text
                  ┌────────────────┐
                  │   Supervisor   │
                  └───────┬────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
      Research        Operations       Planning
       Service          Service          Service
          │               │               │
          └───────────────┼───────────────┘
                          │
                          ▼
                  Cognitive Runtime
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
       Memory         Capabilities       Events
```

This model is closer to a **cognitive operating environment** than a single chatbot.

---

# The Universal Cognitive Kernel

The ultimate architectural direction is the **Universal Cognitive Kernel**.

The kernel should not care whether the environment is:

```text
a laptop
a code repository
a cloud environment
an enterprise
a laboratory
a factory
a SCADA system
a fleet
a robot
or another future environment
```

The environment exposes capabilities.

The kernel provides:

* cognition
* governance
* runtime coordination
* memory
* events
* validation
* supervision
* learning infrastructure

This creates a stable cognitive center while allowing implementations and domains to evolve independently.

---

# The Bigger Vision

The long-term goal is not to build a better chatbot.

It is to build infrastructure in which intelligence can operate.

A mature OCBrain system could eventually:

* understand continuously changing environments
* reason across heterogeneous sources
* maintain long-term cognitive context
* discover capabilities dynamically
* construct and revise plans
* verify proposed actions
* execute under explicit governance
* monitor outcomes
* recover from failure
* learn from experience
* coordinate multiple cognitive services
* escalate decisions to humans when required
* operate across software, enterprise, and industrial domains

The LLM would be only one component.

The **runtime becomes the intelligence infrastructure around the models**.

---

# Guiding Principle

The long-term philosophy of OCBrain can be summarized as:

> **The model reasons.**
> **The kernel understands.**
> **The runtime verifies.**
> **Governance decides what is allowed.**
> **Capabilities execute.**
> **Memory preserves experience.**
> **Reflection evaluates outcomes.**
> **The system learns.**

That separation is the foundation for turning AI from a conversational tool into a general cognitive runtime.

---

# Development Status

OCBrain is an actively evolving engineering project.

## Current Focus

### K4.2 — Cognitive Front-End

The current implementation work focuses on:

* intent interpretation
* constraint extraction
* capability discovery
* planning
* plan compilation
* validation
* memory and learning integration
* reflection
* evaluation workers
* supervision
* end-to-end runtime integration

The architecture is being implemented incrementally and independently verified.

## Stability

OCBrain should currently be considered **development software**.

Architectural correctness, explicit contracts, governance, deterministic behavior, runtime reliability, and security boundaries take priority over feature count.

---

# Roadmap

## K4.2

Complete and harden the Cognitive Front-End.

## Post-K4.2

Strengthen:

* runtime reliability
* governance
* memory
* reflection
* supervision
* capability discovery
* event-driven coordination
* observability
* deterministic simulation
* integration testing

## Universal Cognitive Kernel

Evolve the runtime into a reusable cognitive substrate capable of supporting multiple domains, models, capability ecosystems, and execution environments.

## Long-Term Exploration

Potential future directions include:

* persistent cognitive services
* continuous domain observation
* enterprise cognitive control planes
* industrial and SCADA integration
* multimodal cognition
* distributed cognitive systems
* large-scale capability ecosystems
* human-AI operational collaboration
* cognitive fabrics spanning multiple runtimes

These are **architectural directions, not current product capabilities**.

---

# Repository Structure

The repository is progressively moving toward explicit separation between cognition, runtime infrastructure, governance, memory, capabilities, and interfaces.

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
│   ├── events/
│   ├── governance/
│   ├── memory/
│   └── providers/
│
├── capabilities/
│   ├── contracts/
│   ├── registry/
│   └── adapters/
│
├── interface/
├── tests/
├── docs/
├── pyproject.toml
├── LICENSE
└── README.md
```

The exact implementation structure may evolve.

The architectural boundaries are the important part.

---

# Installation

OCBrain is currently developed primarily as a Python application.

## Requirements

* Python 3.11+
* A supported local inference provider such as Ollama for local model execution
* Platform-specific dependencies required by individual capabilities

## Development Setup

```bash
git clone https://github.com/1h0lde4/OpenClaw-Brain.git
cd OpenClaw-Brain

python -m venv .venv
```

Activate the virtual environment and install dependencies according to the current `pyproject.toml`.

Run the test suite with:

```bash
pytest
```

The repository configuration is the source of truth for installation and packaging details.

---

# Contributing

OCBrain is an architecture-driven project.

Contributions should preserve the separation between:

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

Avoid introducing:

* hidden execution paths
* duplicate runtime infrastructure
* uncontrolled autonomous actions
* capability bypasses
* undocumented security boundaries
* implementation-specific coupling inside the kernel
* implicit trust in model output

For significant architectural changes, consult the relevant documentation in `docs/`.

---

# License

OCBrain is licensed under the MIT License.

See [LICENSE](LICENSE).

---

# Links

* **Repository:** https://github.com/1h0lde4/ocbrain-v4.1
* **Issues:** https://github.com/1h0lde4/ocbrain-v4.1/issues
* **Releases:** https://github.com/1h0lde4/ocbrain-v4.1/releases

---

<div align="center">

### **Build intelligence as infrastructure.**

**OCBrain**

</div>

