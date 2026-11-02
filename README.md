<img width="1536" height="1024" alt="OCBrain" src="https://github.com/user-attachments/assets/2830440e-a250-45ee-95f6-095530b7ddd1" />

# OCBrain

**Overclocked Brain** — a local-first, governed cognitive runtime for turning user intent into planned, observable, and controlled execution.

OCBrain is being built as a **cognitive operating system and kernel**, not as another chatbot, thin LLM wrapper, or standalone RAG framework. It coordinates capabilities, workflows, memory, model providers, and specialist workers through explicit contracts and governance. The user retains control of data, providers, permissions, and consequential actions.

> **Engineering status snapshot — November 2, 2026.** The product baseline described here is `main` at `2491ae469edd6ef1267a14604c4f8f40d698f7ea` (PR #106). This is a point-in-time status, not a release-readiness statement. Check the linked live registers before making implementation or merge decisions.

---

## What OCBrain is meant to become

OCBrain's central responsibility is **coordination under governance**:

- Understand intent and constraints before execution.
- Discover and compose capabilities rather than hard-wire tasks to one model or provider.
- Compile plans into explicit workflows and execute them through controlled runtimes.
- Preserve meaningful state transitions, execution identity, provenance, and audit evidence.
- Maintain durable, user-controlled memory.
- Allow specialist workers and external tools to operate within explicit permission, resource, and isolation boundaries.

The kernel should own stable abstractions and policy boundaries. Adapters should own provider-specific integrations. Capabilities should perform work. Applications and workflows should compose capabilities without moving application-specific behavior into the kernel.

OCBrain is an active engineering project. The cognitive front-end and substantial runtime foundations exist, but the current kernel has unresolved freeze-blocking work. **Do not interpret this README, a green CI check, or an open implementation PR as evidence that the system is production-ready or that Kernel v1.0 has been formally frozen.**

## Current development status

| Area | Current position on the November 2 baseline |
|---|---|
| Cognitive front-end | The K4.2 path is enabled by default in `config/settings.toml`. Intent interpretation, discovery, planning, compilation, and workflow execution are present. |
| Workflow and execution runtime | WorkflowRuntime and ExecutionRuntime are present. Failure propagation, cancellation semantics, identity, and recovery still have open work. |
| Governance | GovernanceKernel has seven registered governors. Governance remains a design invariant; coverage of legacy and fallback paths must not be assumed from the K4.2 path alone. |
| Capability system | CapabilityRegistry is metadata-centric. `LLM_COMPLETION` is the only registered capability type in the current baseline; a complete multi-capability ecosystem is not yet delivered. |
| Memory and retrieval | UnifiedMemory uses the L0–L4 model. Graph and hybrid retrieval components exist; memory durability, retrieval correctness, and lifecycle work remain tracked. |
| Events and auditability | EventStream provides durable SQLite/WAL-backed events, while EventBus remains a separate in-process mechanism. They are not yet one unified audit system. |
| C-MoE | Research and architecture direction only. No production C-MoE implementation is included on the current main baseline. |
| Verification / Critic / Evidence | A separate workstream has unmerged Phase C contracts. It is not a production verification engine and is not part of C-MoE or the GovernanceKernel. |
| Kernel v1.0 freeze | **Not freeze-authorized.** G4 remains OPEN / High / freeze-blocking; FZ-01, FZ-02 residuals, FZ-05, and FZ-06 remain open. |

### What is fixed, and what remains open

The current register distinguishes verified fixes from partial remediation and proposals:

- FZ-03 scheduler containment and FZ-04 semaphore permit conservation are fixed and verified on main.
- FZ-07's core CI-gate defect is fixed and verified; its R-1 matching edge case remains open. PR #107 is diagnostic-only and explicitly **NOT FOR MERGE**.
- FZ-01's workflow/API failure channel is not implemented. A decision record in an unmerged PR is not an implementation.
- FZ-02 has merged provider-failure, stalled/deadline, and router-cleanup work, but end-to-end cancellation and terminal outcome semantics remain open. PR #104 is router-resource cleanup, not workflow cancellation.
- FZ-05 execution-registry growth and EventStream retention remain open.
- FZ-06 / DEBT-030 execution identity across event, workflow, and capability boundaries remains open.
- G4 / DEBT-042 remains a High, freeze-blocking workstream. D1–D11 remain open; no product implementation is authorized by the current handoff.

Other important open areas include API authentication/authorization (DEBT-025), test/config isolation (DEBT-012), learning-boundary remediation (DEBT-014), Context authority boundaries (including CTX-AUTH-001b), and incomplete sandbox isolation. See the live register rather than relying on this abbreviated list.

### Repository coordination snapshot

The November 2 GitHub inventory recorded **111 remote branches, 20 open pull requests, and 3 open non-PR issues**. None of the 20 open PRs had a GitHub assignee recorded in that snapshot. PR authorship and last-commit authorship are provenance, not proof of implementation ownership. Many refs are preserved evidence, research, historical fixes, or competing candidates—not one coherent active implementation queue.

This is why the project uses an explicit debt/branch ownership register. A branch, proposal, review report, or green check does not change the implementation state on main.

---

## Architecture and execution model

The configured K4.2 request path is:

`main.py` → `Orchestrator.handle()` → intent / goal and constraint handling → capability discovery → planning → plan compilation → `WorkflowRuntime` → `ExecutionRuntime` → `ExecutionContext`

The exact path depends on the runtime configuration and construction of the orchestrator. The older foundational dispatch path and compatibility components remain in the repository; they must not be treated as deleted or fully audited merely because the K4.2 path is enabled by default.

| Subsystem | Role |
|---|---|
| `core/cognitive/` | Intent, goal, constraint, discovery, and planning contracts that form the cognitive front-end. |
| `core/workflow/` | Workflow definitions and DAG orchestration. |
| `core/runtime/` | Execution lifecycle, contexts, supervision, cancellation, and runtime controls. |
| `core/governance/` | GovernanceKernel and its governors for bounded, policy-controlled action. |
| `core/capabilities/` | Capability metadata, adapter contracts, and execution integration. |
| `core/memory/` | UnifiedMemory, tiered memory, graph indexing, and retrieval. |
| `core/events/` and `core/event_bus.py` | Durable EventStream and separate in-process event publication. |
| `core/model_router.py` and provider integrations | Model-completion routing and provider integration. |
| `interface/` | CLI and API entry points. |
| `modules/` | Earlier module architecture. Some paths remain live; do not remove them without call-site and behavior audits. |

The architectural direction is provider-independent. The current capability registration is much narrower than the long-term target; the table above describes existing subsystem boundaries, not a claim that every future capability, adapter, or governance property is already implemented.

## Long-term design principles

1. **Local-first and user sovereignty.** Local inference, memory, and orchestration are the default operating posture. A local model provider must be usable without a paid hosted-LLM dependency. Cloud AI may be configured as an optional external provider or expert mesh; it must not become a prerequisite for the core runtime.
2. **Provider independence.** The kernel should not be coupled to one model vendor or serving application. Ollama, llama.cpp-backed local servers, other compatible local endpoints, and optional hosted providers belong behind replaceable adapters. This does not require a dedicated llama.cpp subsystem.
3. **Governance before capability.** New tools, workers, and execution powers must arrive with permission boundaries, budgets, isolation, observability, and approval behavior—not receive them as later hardening.
4. **Explicit and replayable state.** Important transitions need stable identity, provenance, durable events, and recovery semantics. A model's self-report is not an audit record or proof of completion.
5. **Deterministic orchestration, replaceable intelligence.** Model outputs may be probabilistic; scheduling, policy evaluation, state transitions, and terminal outcome handling must remain explicit and testable.
6. **No uncontrolled self-modification.** Learning and improvement must be reviewable, bounded, reversible, and governed by the user.

---

## Adaptability: a cross-cutting property of OCBrain

Adaptability is not only C-MoE's ability to select a different expert. It is a system-wide architectural property: OCBrain should adjust *how it works* to the user's task and preferences, the machine and providers actually available, operational health, project context, and changing execution reality—without changing its constitutional rules or weakening its safety and correctness requirements.

The intended behavior is **controlled adaptation through explicit policy and replaceable components**, not hidden self-modification.

### 1. Adapt to different machines, providers, and deployments

OCBrain should not require one specific model, inference server, hardware configuration, or external AI account. Stable kernel contracts sit above replaceable adapters and capabilities. A deployment should be able to use a local model on a modest machine, several local models on a stronger workstation, or optionally combine local resources with remote specialist providers.

The architecture distinguishes a capability being declared or installed from it being registered, enabled, healthy, and currently executable. Its target provider lifecycle distinguishes configured, available, healthy, rate-limited, degraded, offline, and disabled states; the target capability lifecycle distinguishes installed, available, enabled, disabled, unavailable, degraded, deprecated, and removed. Runtime selection should react to actual observations rather than assumptions: select an eligible alternative, reduce concurrency, wait, pause, or ask the user when no safe route remains.

This does **not** mean OCBrain currently auto-detects every hardware configuration or controls every CPU/GPU resource. The canonical Workspace architecture treats CPU/GPU use as opportunistic or externally managed unless a lower-level execution backend can enforce it. Hardware/resource availability may inform a policy; it must not be advertised as a hard guarantee where the runtime cannot enforce it.

### 2. Adapt computational effort to the user's intent and the task

The studied Workspace architecture defines a Computational Level independent of any particular model name:

| Level | Intended behavior |
|---|---|
| **LOW** | Minimize latency and resource consumption. |
| **MEDIUM** | Balance quality, cost, and latency. |
| **HIGH** | Prioritize quality and reliability. |
| **MAX** | Use the maximum justified computation permitted by policy and available resources; never unlimited computation. |

A separate **Resource Policy Engine** is intended to derive an effective per-task Resource Envelope from the requested level, task complexity and type, risk, available resources, provider/model availability, project and session policy, and Governance constraints. The resulting policy may shape model preference, provider-specific reasoning-effort hints, eligible expert count, retrieval breadth, verification depth, retry/tool budgets, token and cost targets, parallelism, and runtime budgets.

**This resource-policy chain is designed to work without C-MoE.** C-MoE may later contribute task-complexity analysis or recommend a level, but it does not own policy or enforcement. That separation allows resource-aware behavior to be developed independently and prevents the whole platform's adaptability from depending on the C-MoE milestone.

### 3. Adapt during execution, not only before it

The target lifecycle is:

`User intent → task/context analysis → Resource Policy → governance-constrained effective envelope → runtime allocation → measured usage → logged adaptation`

The system should be able to revise its allocation as new facts arrive: for example, choose sequential rather than parallel work when resources are constrained, increase effort when unexpected complexity justifies it, or require a minimum verification level for high-risk work. The adaptation must be explainable and observable; the system should record why its effective policy differs from the requested preference.

The precedence is non-negotiable:

`System hard caps → Governance constraints → Project defaults → Session overrides → Task request → Runtime adaptation`

User preferences matter, but cannot exceed system limits or override Governance. Resource scarcity and urgency may change the strategy, but must never silently lower the correctness or assurance criteria.

### 4. Adapt when resource availability or provider health changes

The resource design distinguishes four enforcement classes:

- **Hard ceiling:** OCBrain or its execution backend can detect and stop a violation, but only for limits that are actually wired to an enforcing mechanism.
- **Target:** a goal that may overshoot, such as token or cost budgets when a provider call cannot be reserved exactly.
- **Preference:** a provider hint, such as reasoning effort, that the provider may approximate or ignore.
- **Derived parameter:** a tuning input such as retrieval breadth; it changes behavior but does not itself enforce a limit.

This prevents misleading promises. Reasoning-effort hints are provider-dependent; token and cost limits may have overshoot; CPU/GPU scheduling is not an OCBrain guarantee unless the configured execution backend enforces it.

### 5. Adapt to changing goals, context, and operational reality

Adaptability also means responding correctly when the user changes a task, a project evolves, a capability becomes unavailable, or prior work is invalidated. The C-MoE design treats user task mutation as a typed change to the active goal, followed by dependency-aware impact analysis. Work may remain valid, be reusable, become stale, or require recomputation. The system should preserve useful work where justified, but never allow an older plan to outrank the user's latest authorized instruction.

Project, session, discussion, and task context should remain scoped. Personalization and learned preferences may inform recommendations, but they do not become authority and cannot override permissions, Governance, or hard resource limits.

Long-running work must eventually be able to suspend and resume with its identity, graph state, evidence, and budgets intact. On resumption, the system should re-check whether its prior plan, provider choice, evidence, and assumptions are still current rather than blindly replay a stale decision.

### 6. Adaptation must remain observable, bounded, and reversible

The user and operator should be able to inspect the requested computational level, effective policy, actual allocation, provider/expert choice, resource use, remaining budget, and reason for any escalation or de-escalation. Adaptation decisions need structured provenance and should be available through Studio.

Runtime adaptation is not permission for autonomous architecture changes. Changes to learned routing policy, capability definitions, memory promotion, skills, or the system's own behavior require validation, Governance approval, and rollback paths. Improvements must earn promotion through evidence rather than self-assertion.

### What exists today versus the studied target

Some lower-level adaptive mechanisms already exist on `main`:

- `AdaptiveSemaphore` adjusts concurrency using observed latency with an EMA-smoothed additive-increase / multiplicative-decrease policy.
- Provider integrations track failures and cooldown/availability, while model/runtime paths maintain provider/model throughput observations.
- `ExecutionBudget` and watchdogs provide bounded time/deadline handling.

These are useful foundations, but they are **not** the complete adaptive resource architecture. The November 2 baseline does not yet provide an integrated user-facing Computational Level selector, a wired Resource Policy Engine, effective Resource Envelope derivation, or complete token/cost/reasoning-effort/expert-count controls.

There are `ComputationalLevel` and `ResourcePolicy` data definitions in `core/workspace/domain.py`, but the canonical [Workspace & UX/UI Architecture](docs/architecture/WORKSPACE_ARCHITECTURE.md) explicitly classifies that existing Workspace domain file as non-conformant, unwired, and untested, with a REWORK disposition. The presence of those definitions is therefore not evidence that the policy engine or adaptive Workspace flow is implemented. Treat the canonical architecture—not the incomplete candidate file—as the intended design.

**In one sentence: OCBrain should adapt its strategy, expertise, and resource use to the user's task and the environment it actually has—while its governance, identity, auditability, and correctness floor remain stable.**

The canonical design source for this direction is [Workspace & UX/UI Architecture](docs/architecture/WORKSPACE_ARCHITECTURE.md), especially its Computational Level, Resource Architecture, Provider/Capability Lifecycle, and governance-precedence sections. Its resource-policy mechanisms are architectural requirements, not a claim that the Resource Policy Engine or the full adaptive control loop has shipped. The [C-MoE adaptive scaling study](docs/architecture/future_debt_study/OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md) defines the additional cognitive-effort and expert-escalation behavior.

---

## Architecture evolution and long-term vision

The long-term direction is deliberately layered. OCBrain should become a dependable substrate for increasingly general cognitive systems, while preserving a small, stable, governed kernel. New intelligence belongs in replaceable capabilities, experts, and cognitive runtimes—not as uncontrolled complexity inside the kernel.

The progression below is a strategic architecture direction, not an authorization to start every workstream. The current Constitution, Kernel freeze gates, approved ADRs, and owner decisions continue to control implementation.

### Stage 0 — Complete and freeze the trustworthy kernel

This is the current priority. The kernel must become a dependable substrate before more autonomous cognitive machinery is layered on top of it.

The critical work includes:

- Resolve the currently open freeze-blocking correctness and authority decisions, including G4 and the FZ-01/FZ-02/FZ-05/FZ-06 residuals.
- Establish consistent terminal outcomes, typed failures, cancellation propagation, operation/attempt identity, idempotency, and durable recovery.
- Close the execution-isolation, memory-authority, authentication/authorization, and bounded-resource gaps that would become more dangerous as autonomy grows.
- Make events, state transitions, and execution lineage sufficiently durable and inspectable to explain what happened and why.
- Perform a fresh freeze audit against one exact main SHA. A historical audit, an architecture document, or green CI alone is not a freeze verdict.

**Why this comes first:** C-MoE will multiply the number of decisions, experts, and execution paths the kernel has to govern. A weak execution substrate would turn greater cognitive capability into greater failure surface.

### Stage 1 — C-MoE: the adaptive cognitive runtime

C-MoE means **system-level Cognitive Mixture of Experts**. It is not neural-network MoE, and it is not merely a router that picks one LLM from a list.

The central idea is that OCBrain should coordinate a pool of heterogeneous expertise. An expert may be an LLM-backed capability, a deterministic algorithm, a solver, a retrieval or search system, a specialist worker, a tool, or an external system behind an adapter. The kernel provides the contracts and governance; experts provide the expertise.

C-MoE's north-star rule is:

> Optimize for successful realization of the currently authorized goal—not merely successful execution of the current plan.

The boundaries matter:

| Component | Owns | Does not own |
|---|---|---|
| **Planner (K4.2)** | Interprets the goal and constraints; creates the initial strategy and `ExecutionPlan`. | Runtime expert selection after reality changes; execution mechanics. |
| **C-MoE** | Selects and coordinates which eligible expert(s) should act now; interprets structured outcomes; adapts the live work graph; requests replanning or escalation. | Authorization, low-level execution mechanics, or proof that the goal is truly satisfied. |
| **WorkGraph** | The live realization of the plan: work-unit state, dependencies, completed/pending/failed work, and graph lineage. | Independent decision authority. |
| **ExecutionRuntime / WorkflowRuntime** | Performs the approved work and manages execution mechanics. | Deciding the cognitive next step. |
| **GovernanceKernel** | Authorizes or rejects proposed actions, permissions, resource boundaries, and consequential changes. | Choosing the cognitive strategy. |
| **Verification system** | Establishes whether evidence supports a claim that the requested outcome was achieved. | Planning or selecting experts. |
| **Memory** | Stores scoped knowledge, outcomes, provenance, and approved result promotion. | Acting as hidden task state or an independent agent. |

The C-MoE design has several defining properties:

1. **Heterogeneous expert selection.** Generate candidates, filter them through hard eligibility (permissions, contract compatibility, health), then rank viable candidates using measured signals such as specialization fit, verified performance, latency, cost, and availability. A model's narrative must never be the sole explanation for a routing decision.
2. **Sparse, adaptive effort.** If exactly one expert is eligible, use the direct path; do not introduce a mandatory C-MoE hop for every trivial action. Invoke multiple or redundant experts only when the expected improvement in confidence or assurance justifies the resource cost.
3. **Bounded escalation and honest abstention.** When confidence is inadequate, no expert is eligible, or required facts are missing, C-MoE must be able to abstain, request information, or escalate to the user rather than force a weak route.
4. **Goal-preserving adaptation.** A failed step does not automatically mean the goal is unreachable. C-MoE interprets typed outcomes, updates the WorkGraph, and can request a new plan while preserving the authorized goal. Only the user can explicitly change the goal itself.
5. **User-controlled task mutation.** Mid-execution changes should be represented as typed diffs against the active goal—not treated as an unrelated fresh request. Impact analysis should distinguish work that remains valid or reusable from work that is stale, dependency-broken, or must be recomputed. This preserves useful work without allowing an old plan to silently override the user's latest instruction.
6. **Reality-aware planning.** For requests where project state, prior work, or side effects matter, the studied design adds a conditional, read-only, facts-only `RealityBrief` before planning and a feasibility pass after planning. This must not become a second Planner or an uncontrolled Planner↔C-MoE dialogue.
7. **User-scoped memory.** The design separates memory *tier* (L0–L4) from memory *scope*. Global user knowledge, project knowledge, discussion/task context, and reusable knowledge must not silently bleed into one another. Project and Discussion are application-level concepts over kernel scope primitives, not new kernel primitives.
8. **Governed decisions with provenance.** C-MoE proposes routing, composition, replanning, suspension, and escalation; GovernanceKernel authorizes consequential actions. Structured routing/outcome events explain the decision without exposing private chain-of-thought.

The researched MVP is intentionally single-node and narrow: prove a real dispatch path for at least two distinct capability types, a minimal Expert descriptor, a bounded work-unit state machine, a structured outcome contract, a feasibility check, and plan–reality feedback. Broader expert composition, disagreement handling, complete scoped-memory promotion, and distributed WorkGraphs are later extensions. C-MoE is **post-Kernel-v1.0-freeze**; it is not an official “K4.3” milestone and is not implemented on the current main baseline.

### Stage 2 — Independent verification and assurance

Verification is not C-MoE, not the EvaluatorWorker, and not the GovernanceKernel. It is a distinct assurance system that evaluates evidence about whether a requested state or outcome was actually achieved.

The intended assurance chain is:

`ASSERTION → OBSERVATION → EVIDENCE → VERIFICATION → VERDICT → GOVERNANCE`

Its purpose is to distinguish a claim from an observed fact, evidence from an inference, and a successful-looking response from a verified outcome. It must support explicit assurance levels, provenance, immutable evidence receipts, contradiction handling, and honest states such as **PASS**, **FAILED**, and **UNVERIFIABLE**. A verifier crash or absence of evidence must never be silently converted into PASS.

C-MoE may request verification and consume its structured result, but it does not own the verifier's standards or verdict. The Verification / Critic / Evidence workstream has contracts on a separate unmerged branch; it is not production-integrated on main.

### Stage 3 — Reflection, evaluation, and governed learning

Once execution and verification produce trustworthy data, OCBrain can improve how it works without silently changing its own rules.

The longer-term direction includes:

- Reflection over execution trajectories, failure causes, and successful strategies.
- An Evaluation / Reliability Lab that measures repeatability, regressions, calibration, and task-level outcomes.
- Adaptive Learning that can improve routing policies, memory organization, and strategy selection only through explicit validation and promotion gates.
- Capability and skill evolution with versioning, provenance, review, rollback, and user approval where appropriate.
- A user cognitive model that records confidence and provenance tiers rather than treating inferred preferences as explicit instructions.
- An explicit **self-model** of OCBrain's own architecture, approved decisions, requirements, available capabilities, compatibility, operational health, and known limitations. This supports diagnostics and honest capability awareness; it is not a claim of consciousness or a source of authority.
- **Decision Memory** that preserves the context, alternatives, selected decision, rationale, confidence, and timestamp separately from ordinary factual knowledge.
- A grounded **world/state model** that represents observed entities, relationships, and changes with provenance, while distinguishing observations, hypotheses, decisions, and verified facts.
- Passive detection of recurring workflow patterns and opportunities for improvement. The longer-term Fable/proactive-optimization direction should initially produce explainable suggestions; autonomous initiation of consequential work requires a separate governance design and explicit user control.

The first C-MoE routing policy should use measured evidence with a controlled, reviewable policy—not online self-training or an opaque learned router. Learning new routing behavior is a distinct future capability. It should be introduced only after the evidence pipeline, evaluation criteria, promotion gates, and rollback behavior are proven.

### Stage 4 — Broader expert ecosystem and optional Expert Mesh

OCBrain should be able to grow beyond one model and beyond one machine without making either complexity or cloud access mandatory.

The target provider strategy is:

- A usable **local LLM path is a first-class requirement**. Core operation must not depend on a paid external AI provider.
- Ollama, llama.cpp-backed servers, other compatible local inference servers, and custom local runtimes should be replaceable provider adapters—not kernel dependencies.
- Hosted OpenAI-, Anthropic-, or other providers may be configured as optional External AI Providers.
- An optional **Expert Mesh** may expose remote specialist models, agents, or services as governed experts. It must remain optional; local-only operation must remain a valid deployment posture.
- User-selectable effort levels—such as low, medium, and maximum—should influence resource allocation, expert breadth, parallelism, and verification depth under policy. They must not lower the correctness or safety floor for consequential work.

The long-term ecosystem may include coding, browser research, data analysis, simulation, robotics or device control, and domain-specific experts. These should enter through versioned capabilities and adapters with explicit contracts, least privilege, sandboxing, and auditable outcomes. Multi-node execution, distributed cognition, resource economies, and cognitive marketplaces remain research directions—not prerequisites for the first C-MoE release.

### Stage 5 — OCBrain Studio and the human operator plane

OCBrain Studio should become the operator-facing control plane for long-running cognitive work—not a second workflow engine and not the source of truth for execution state.

Its purpose is to make the live system understandable and governable:

- Show the user's authorized goal, Planner strategy, current WorkGraph, dependencies, work-unit states, and task lineage.
- Surface which experts were considered, why candidates were excluded or selected, what resources were consumed, and what the runtime proposes to do next.
- Present structured outcomes, verification verdicts, evidence receipts, contradictions, and unresolved uncertainty.
- Provide clear human controls to inspect, approve, pause, resume, cancel, supersede, or amend work, with the authority source recorded.
- Display memory scope and provenance so users can see what knowledge influenced a plan and where promoted results will be stored.
- Support replay and debugging from the same durable events and snapshots used by the runtime.

Studio should consume the runtime's authoritative event and snapshot contracts. It must not invent a parallel execution state, silently rewrite goals, or hide the difference between a proposed action and an authorized one. The current event/snapshot work provides useful foundations, but the full Studio experience and its governance controls are not being claimed as complete here.

### Long-term ambition — an architecture that can support increasingly general intelligence

The AGI ambition is the long horizon, not a claim about OCBrain today and not a currently authorized implementation milestone.

The goal is not simply to make one language model larger, connect many models, or create a swarm of agents. It is to build a persistent, governed cognitive system that can generalize across domains by combining:

- **General problem solving:** understand unfamiliar goals, decompose them, identify missing information, and construct strategies.
- **Transferable expertise:** select and compose different kinds of experts, including deterministic tools and non-LLM systems, rather than assuming every problem is a text-generation problem.
- **Continuity over time:** preserve authorized goals, projects, task lineage, and appropriately scoped memory across long-running work.
- **Grounded interaction:** observe external state through tools and environments, distinguish knowledge from hypotheses, and update plans when reality differs.
- **Reliable agency:** act through controlled permissions, recover from interruptions, respect user changes, and seek approval before consequential actions.
- **Independent assurance:** verify important claims and outcomes with evidence rather than relying on the system's own confidence or self-report.
- **Measured adaptation:** learn from outcomes through evaluated, reversible promotion—not uncontrolled self-modification.
- **Metacognitive awareness:** maintain an evidence-backed account of its own capabilities, limitations, resource state, confidence, and operational health, so it can choose when to act, when to seek expertise, and when to abstain.
- **World understanding:** build and update a grounded model of relevant environments and causal relationships from observations and verified memory, rather than treating retrieved text as unquestioned reality.
- **Decision continuity:** remember why significant decisions were made, what alternatives were considered, what evidence supported them, and what later events should cause reconsideration.

C-MoE is a central enabling layer in this direction because it coordinates *which expertise is used, when, and how the work adapts*. It is not AGI by itself, does not create missing expert capability, and cannot compensate for weak foundation models, poor tools, ungrounded memory, or absent verification. The broader system also needs robust planning, durable execution, memory, world/reality grounding, evaluation, learning, and alignment with the user's authorized goals.

Progress toward AGI should therefore be judged by evidence of generalization to unfamiliar tasks and domains, sustained goal coherence over long horizons, calibrated uncertainty and abstention, reliable recovery, safe tool use, and measurable improvement without loss of user control. Passing a narrow benchmark, producing fluent answers, or coordinating multiple agents is not sufficient evidence. The project makes no claim of consciousness, sentience, or achieved AGI.

This ambition does not override the Kernel Constitution or the Future Research Vault. An idea remains research until it has been investigated, architecturally reviewed, accepted through the appropriate ADR, placed on an approved roadmap, assigned an owner, and cleared by its dependencies. **The more general OCBrain becomes, the more important governance, verification, isolation, and user sovereignty become.**

## Installation and development

The package declares Python **3.11 or newer**.

Install the project and development/test dependencies:

```bash
python -m venv .venv
# Activate the virtual environment, then:
python -m pip install -e ".[dev]"
```

Optional extras are defined for training and voice features:

```bash
python -m pip install -e ".[training]"
python -m pip install -e ".[voice]"
```

The package exposes two entry points:

- `ocbrain` — command-line interface.
- `ocbrain-start` — main service entry point.

Review `config/settings.toml` and the selected model/provider configuration before starting the service. OCBrain does not bundle a model server; local inference must be supplied by a configured local provider.

Run the test suite with:

```bash
pytest tests/ -q
```

Some tests exercise model and embedding paths that may require model artifacts, provider configuration, or network access. Record the exact commit, environment, and raw test result when reporting failures. Do not classify an environment-dependent failure as a code defect—or as harmless—without reproducing and documenting its cause.

## Engineering workflow and source of truth

Before changing code, inspect the exact live main SHA, relevant branches and PRs, current tests, and the known-issues register. Reconcile against code and evidence; do not let an old document override live behavior.

Use these records for different purposes:

- [Kernel Constitution](OCBRAIN_KERNEL_CONSTITUTION.md) — constitutional direction; its current status is **Draft, not Final**.
- [Kernel Architecture v1.0](docs/architecture/KERNEL_ARCHITECTURE_v1.0.md) — kernel engineering specification. A specification baseline is not the same as approval to freeze the current implementation.
- [Project Instructions](docs/architecture/PROJECT_INSTRUCTIONS.md) — operational engineering rules.
- [Current State](CURRENT_STATE.md) — current implementation and merge-state snapshot.
- [Known Issues](KNOWN_ISSUES.md) — debt, unresolved findings, and explicit deferrals.
- [Debt / Branch Ownership Register](docs/engineering/DEBT_BRANCH_OWNERSHIP_REGISTER_2026-11-02.md) — the November 2 inventory of branches, open PRs, ownership, and per-workstream dispositions.
- [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md) — historical planning material that was last synchronized on September 13, 2026; reconcile it with the November 2 state before treating it as the live execution queue.
- [Architecture Evolution Directive](docs/architecture/OCBrain%20Architecture%20Evolution%20Directive.md) — approved architectural direction and separation of cognitive-runtime stages.
- [Kernel Completion Study](docs/studies/OCBRAIN_KERNEL_COMPLETION_STUDY.md) — research reconciliation and kernel-completion dependencies; not a freeze verdict by itself.
- [C-MoE Cognitive Runtime Study](docs/studies/OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md) — detailed post-freeze C-MoE design, boundaries, WorkGraph, expert model, and implementation sequencing.
- [C-MoE Reality-Grounding Study](docs/studies/OCBRAIN_CMOE_REALITY_GROUNDING_SUBSTUDY.md) — conditional facts-only grounding and plan-feasibility design.
- [Verification / Critic / Evidence Study](docs/studies/OCBRAIN_CMOE_VERIFICATION_ARCHITECTURE_STUDY.md) — distinct assurance architecture; research/contracts are not equivalent to production integration.
- [C-MoE Adaptive Cognitive Scaling Study](docs/architecture/future_debt_study/OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md) — earlier research input to the reconciled C-MoE design.
- [Workspace & UX/UI Architecture](docs/architecture/WORKSPACE_ARCHITECTURE.md) — authoritative workspace architecture, including Computational Level, Resource Policy, Resource Envelope, provider/capability lifecycle, and adaptation precedence.
- [Future Research Vault](docs/architecture/FUTURE_RESEARCH_VAULT.md) — ideas that remain research until they pass the project's architecture and roadmap gates.
- [Product Definition](PRODUCT.md) — product principles and target boundaries.

A PR is a proposal until merged. A green CI run is evidence for the checks it actually ran, not proof that every requirement is satisfied. A debt is closed only when its acceptance criteria are met and the closure is recorded against the relevant merged baseline. Keep one canonical review target per work item; preserve competing branches until an explicit cleanup decision is made.

## License

OCBrain is distributed under the MIT license. See [LICENSE](LICENSE).
