<img width="1536" height="1024" alt="OCBrain" src="https://github.com/user-attachments/assets/2830440e-a250-45ee-95f6-095530b7ddd1" />

# OCBrain

**Overclocked Brain** — a local-first, governed cognitive runtime for turning user intent into planned, observable, and controlled execution.

OCBrain is being built as a **cognitive operating system and kernel**, not as another chatbot, thin LLM wrapper, or standalone RAG framework. It coordinates capabilities, workflows, memory, model providers, and specialist workers through explicit contracts and governance. The user retains control of data, providers, permissions, and consequential actions.

> **Engineering status snapshot — November 2, 2026.** The product baseline described here is \x60main\x60 at \x602491ae469edd6ef1267a14604c4f8f40d698f7ea\x60 (PR #106). This is a point-in-time status, not a release-readiness statement. Check the linked live registers before making implementation or merge decisions.

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
| Cognitive front-end | The K4.2 path is enabled by default in \x60config/settings.toml\x60. Intent interpretation, discovery, planning, compilation, and workflow execution are present. |
| Workflow and execution runtime | WorkflowRuntime and ExecutionRuntime are present. Failure propagation, cancellation semantics, identity, and recovery still have open work. |
| Governance | GovernanceKernel has seven registered governors. Governance remains a design invariant; coverage of legacy and fallback paths must not be assumed from the K4.2 path alone. |
| Capability system | CapabilityRegistry is metadata-centric. \x60LLM_COMPLETION\x60 is the only registered capability type in the current baseline; a complete multi-capability ecosystem is not yet delivered. |
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

\x60main.py\x60 → \x60Orchestrator.handle()\x60 → intent / goal and constraint handling → capability discovery → planning → plan compilation → \x60WorkflowRuntime\x60 → \x60ExecutionRuntime\x60 → \x60ExecutionContext\x60

The exact path depends on the runtime configuration and construction of the orchestrator. The older foundational dispatch path and compatibility components remain in the repository; they must not be treated as deleted or fully audited merely because the K4.2 path is enabled by default.

| Subsystem | Role |
|---|---|
| \x60core/cognitive/\x60 | Intent, goal, constraint, discovery, and planning contracts that form the cognitive front-end. |
| \x60core/workflow/\x60 | Workflow definitions and DAG orchestration. |
| \x60core/runtime/\x60 | Execution lifecycle, contexts, supervision, cancellation, and runtime controls. |
| \x60core/governance/\x60 | GovernanceKernel and its governors for bounded, policy-controlled action. |
| \x60core/capabilities/\x60 | Capability metadata, adapter contracts, and execution integration. |
| \x60core/memory/\x60 | UnifiedMemory, tiered memory, graph indexing, and retrieval. |
| \x60core/events/\x60 and \x60core/event_bus.py\x60 | Durable EventStream and separate in-process event publication. |
| \x60core/model_router.py\x60 and provider integrations | Model-completion routing and provider integration. |
| \x60interface/\x60 | CLI and API entry points. |
| \x60modules/\x60 | Earlier module architecture. Some paths remain live; do not remove them without call-site and behavior audits. |

The architectural direction is provider-independent. The current capability registration is much narrower than the long-term target; the table above describes existing subsystem boundaries, not a claim that every future capability, adapter, or governance property is already implemented.

## Long-term design principles

1. **Local-first and user sovereignty.** Local inference, memory, and orchestration are the default operating posture. A local model provider must be usable without a paid hosted-LLM dependency. Cloud AI may be configured as an optional external provider or expert mesh; it must not become a prerequisite for the core runtime.
2. **Provider independence.** The kernel should not be coupled to one model vendor or serving application. Ollama, llama.cpp-backed local servers, other compatible local endpoints, and optional hosted providers belong behind replaceable adapters. This does not require a dedicated llama.cpp subsystem.
3. **Governance before capability.** New tools, workers, and execution powers must arrive with permission boundaries, budgets, isolation, observability, and approval behavior—not receive them as later hardening.
4. **Explicit and replayable state.** Important transitions need stable identity, provenance, durable events, and recovery semantics. A model's self-report is not an audit record or proof of completion.
5. **Deterministic orchestration, replaceable intelligence.** Model outputs may be probabilistic; scheduling, policy evaluation, state transitions, and terminal outcome handling must remain explicit and testable.
6. **No uncontrolled self-modification.** Learning and improvement must be reviewable, bounded, reversible, and governed by the user.

---

## Future direction

The sequence below describes the **intended engineering direction**, not a set of approved implementation tickets. Each work package still requires a current-main baseline, a named owner, explicit scope, independent evidence, and the relevant design decisions.

### 1. Complete the kernel audit and establish a trustworthy freeze boundary

Resolve the current freeze blockers and high-severity correctness gaps before expanding autonomy. This includes:

- Agreeing and implementing explicit workflow/API terminal-result and failure semantics.
- Completing cancellation propagation across workers, workflows, providers, shutdown, and client disconnects.
- Establishing joinable operation, attempt, workflow, and capability identities.
- Resolving bounded lifecycle and retention for execution registries and durable events without weakening audit requirements.
- Closing the G4 search-correctness workstream through the owner's decision and evidence gates.
- Rechecking API authentication and authorization, sandbox boundaries, test isolation, and dependency/security decisions.
- Running a fresh, immutable-baseline freeze audit. A freeze verdict must be based on the exact final main SHA and its evidence.

### 2. Strengthen execution reliability and recovery

Build on the existing workflow and execution runtimes with coherent contracts for:

- Typed terminal outcomes, partial results, retries, deadlines, and cancellation.
- Stable operation and attempt identity, idempotency, and side-effect tracking.
- Durable checkpoint/resume and crash recovery, with clear event-retention and replay rules.
- Measured resource budgets and enforceable limits—not counters that exist only as configuration.
- Cross-process coordination where deployment topology requires it.
- Sandboxed execution and least-privilege access for code, browser, filesystem, and external-service capabilities.

### 3. Develop the capability and provider layer

Move from a narrow completion capability toward a provider-neutral capability system. The target is a kernel that resolves capability contracts and schedules work without owning vendor-specific implementation details.

The intended model-provider strategy is:

- Local model execution remains a first-class, independently usable path.
- Adapters can target Ollama, llama.cpp-backed servers, compatible local inference servers, and custom local providers.
- OpenAI-, Anthropic-, or other hosted services may be optional adapters, never mandatory infrastructure.
- Model choice and reasoning effort can be policy-controlled (for example, low, medium, and maximum) without leaking provider-specific assumptions into the kernel.
- Capability selection, fallback, and multi-model coordination must be visible, budgeted, governed, and measured.

### 4. Advance C-MoE after the kernel boundary is stable

C-MoE is the planned adaptive cognitive runtime above the kernel, not a replacement for it. Its longer-term responsibilities include selecting and coordinating candidate capabilities, adapters, and specialist workers according to task needs, quality, latency, resource budgets, and governance policy.

C-MoE remains research/design work. It must not be represented as shipped capability, and it must not absorb kernel responsibilities or weaken the provider-independent contract.

### 5. Build verification as a distinct assurance system

The Verification / Critic / Evidence system is a separate assurance workstream—not a C-MoE feature, a substitute for GovernanceKernel, or another name for evaluation. Its intended flow is:

\x60ASSERTION → OBSERVATION → EVIDENCE → VERIFICATION → VERDICT → GOVERNANCE\x60

The target is deterministic-first verification with provenance, immutable evidence receipts, explicit assurance levels, and clear handling of FAILED, UNVERIFIABLE, and PASS. It should integrate with execution through explicit contracts while remaining independently testable. The current Phase C branch is not production integration.

### 6. Expand the cognitive and application ecosystem

Once the contracts and controls are proven, OCBrain can grow toward:

- Specialist workers for coding, browser research, evaluation, reflection, and memory curation.
- Versioned skills, tools, workflows, and adapters with explicit schemas and isolated execution.
- Rich task observability, replay, and a Studio that represents live execution state rather than presenting a decorative workflow view.
- Governed long-term learning and memory consolidation, preserving provenance and user control.
- Multi-node or fleet execution only after identity, authorization, audit, quotas, and isolation work is complete.

The guiding rule is that expansion follows trustworthiness: **new autonomy is earned through evidence, not assumed from model capability.**

---

## Installation and development

The package declares Python **3.11 or newer**.

Install the project and development/test dependencies:

\x60\x60\x60bash
python -m venv .venv
# Activate the virtual environment, then:
python -m pip install -e ".[dev]"
\x60\x60\x60

Optional extras are defined for training and voice features:

\x60\x60\x60bash
python -m pip install -e ".[training]"
python -m pip install -e ".[voice]"
\x60\x60\x60

The package exposes two entry points:

- \x60ocbrain\x60 — command-line interface.
- \x60ocbrain-start\x60 — main service entry point.

Review \x60config/settings.toml\x60 and the selected model/provider configuration before starting the service. OCBrain does not bundle a model server; local inference must be supplied by a configured local provider.

Run the test suite with:

\x60\x60\x60bash
pytest tests/ -q
\x60\x60\x60

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
- [Product Definition](PRODUCT.md) — product principles and target boundaries.

A PR is a proposal until merged. A green CI run is evidence for the checks it actually ran, not proof that every requirement is satisfied. A debt is closed only when its acceptance criteria are met and the closure is recorded against the relevant merged baseline. Keep one canonical review target per work item; preserve competing branches until an explicit cleanup decision is made.

## License

OCBrain is distributed under the MIT license. See [LICENSE](LICENSE).
