# The OCBrain Kernel Constitution

**Status:** Constitutional — Draft, not Final. Amend only per the process in Part VIII.
**Date:** July 8, 2026
**Precedence:** The highest-level architectural document in the project. It governs the *framing* of `PROJECT_INSTRUCTIONS.md` and every architecture and research document beneath it. It supersedes none of them in substance — see the companion rationale document for the full reconciliation.
**Nature of this document:** Not an implementation document. Not a roadmap. Not a software specification. A charter — the set of principles OCBrain should still be answerable to even if every model, protocol, and line of code it currently runs on has been replaced.

---

## Part I — Identity

OCBrain is not a product. It is a substrate other products are built on.

The **Kernel** is the smallest set of responsibilities that must be trusted, centralized, and governed for everything built on top of it to be coherent, safe, and explainable. Its job is to coordinate, not to perform; to understand, not merely to execute; to remember, not merely to run.

Everything the Kernel does traces back to one purpose: to be worthy of being trusted with a user's intent, and to prove that trust continuously rather than assume it once.

---

## Part II — Foundational Principles

These are axioms, not rules. They define the vocabulary everything else in this document depends on.

- The kernel owns abstractions; adapters own implementations.
- Capabilities perform work; the kernel schedules and governs it.
- Resources represent state; the kernel holds no meaningful state outside of resources.
- Events communicate change; silence is not a valid state transition.
- Intent precedes execution; execution without understood intent is not autonomy, it is malfunction.
- Determinism is a property of orchestration, not a demand placed on every component beneath it.
- Sovereignty belongs to the user — not to the kernel, and not to anything the kernel connects to.
- Nothing inside the kernel is irreplaceable except the principles in this document.

---

## Part III — Kernel Laws

Each law states what it protects, why, what it implies for implementation, and one concrete example. These are engineering discipline, not aspiration.

**1. Law of Bounded Autonomy**
*Purpose:* No capability may exceed the governance wrapped around it.
*Reasoning:* Capability without oversight is the most common failure mode in autonomous systems — unlimited capability is not a feature, it is unmanaged risk.
*Implications:* Every new capability is born with its governance attached, not fitted afterward. Governance visibility must grow at least as fast as capability.
*Example:* A capability that can modify production state is born with an approval gate; the gate is not something added later "when needed."

**2. Law of Explicit State**
*Purpose:* Nothing meaningful happens inside the kernel without leaving a trace.
*Reasoning:* Hidden state cannot be governed, replayed, explained, or trusted.
*Implications:* State changes are represented as events or resource transitions, never as silent mutation.
*Example:* A capability's internal cache may exist, but the fact that it was consulted, and what it returned, is externally visible.

**3. Law of Separation of Concerns**
*Purpose:* The kernel coordinates; it does not perform.
*Reasoning:* A kernel that also does the work it coordinates cannot isolate failure, cannot be replaced piecewise, and cannot reason cleanly about its own boundaries.
*Implications:* Execution of untrusted or specialized work happens inside capability and adapter boundaries, never inline in kernel logic.
*Example:* The kernel decides that code needs to run and under what constraints; it never runs that code itself.

**4. Law of Determinism**
*Purpose:* The same intent, given the same state, should produce an explainable and reproducible path to execution.
*Reasoning:* A system that cannot be reasoned about cannot be trusted, debugged, or improved with confidence.
*Implications:* Orchestration must be deterministic even when the capabilities it calls are not. What was asked, what was decided, and why must always be reconstructable.
*Example:* Re-running the same compiled execution plan against the same resource state produces the same scheduling decisions, even if a model's exact wording differs run to run.

**5. Law of User Sovereignty**
*Purpose:* The user who owns an OCBrain instance owns everything it knows, decides, and does.
*Reasoning:* A cognitive system that quietly accumulates authority over its owner has failed at its most basic purpose.
*Implications:* Nothing is adopted, shared, or acted on without the user's visibility and, where consequential, consent. Local-first is the default, not an optional mode.
*Example:* A recommendation sourced from outside the instance is proposed and reviewed — never auto-applied.

**6. Law of Explainability**
*Purpose:* The kernel must be able to say what it believes, how confident it is, and why — before and after acting.
*Reasoning:* Trust that cannot be inspected isn't trust, it's faith. Authority over consequential decisions has to be earned continuously, not once.
*Implications:* Every compiled execution plan carries its own justification as a first-class artifact, not something reconstructed after the fact from logs.
*Example:* Before a workflow runs, the kernel can state plainly what it understood the goal to be, and what it's still uncertain about.

**7. Law of Replaceability**
*Purpose:* No implementation is permanent; only the abstraction it satisfies is expected to persist.
*Reasoning:* Technology changes faster than good architecture should have to. A kernel married to one model, protocol, or vendor inherits that thing's obsolescence.
*Implications:* Every capability the kernel depends on must have, in principle, at least one alternative implementation that could replace it without changing the kernel's contract.
*Example:* An inference call does not know or care whether the model behind it is local or remote, open- or closed-weight — only that the contract is satisfied.

**8. Law of Evidence over Assumption**
*Purpose:* Architectural change is earned by evidence, not asserted by preference.
*Reasoning:* A system that evolves on what sounds right, rather than what has been observed to be right, accumulates untested complexity.
*Implications:* Significant changes are justified against real precedent — prior implementation experience, convergent findings across independent systems, measured outcomes — not novelty alone.
*Example:* A pattern five independent, unrelated systems converged on is preferred over one adopted for being new.

**9. Law of Single Source of Truth**
*Purpose:* At any moment, there is exactly one authoritative answer to "what is actually true right now."
*Reasoning:* Competing sources of truth — stale documentation, contradictory configuration, memory that disagrees with source — are how systems quietly rot.
*Implications:* When documentation and reality disagree, reality wins, and the documentation is corrected. The same discipline applies to this Constitution's own relationship to implementation.
*Example:* A roadmap listing a component as complete does not make it complete; the running system's own state is authoritative.

---

## Part IV — Kernel Invariants

Properties that must hold at every point in execution, not principles about what things are or rules about how to build them.

1. The kernel does not act on intent it has not first attempted to understand and, where genuinely ambiguous, verify.
2. Every compiled execution plan can be inspected before it runs.
3. Every completed execution can be replayed and explained after it runs.
4. Every resource the kernel manages carries identity, lifecycle, and provenance.
5. Information that crosses a kernel boundary is represented as an event.
6. Every capability has, at minimum, a defined contract more than one implementation could satisfy.
7. All user data and decisions remain under the user's authority by default.
8. Recommendations sourced from outside a single instance are never self-executing.
9. No single implementation detail is load-bearing for the kernel's own definition of itself.

---

## Part V — Kernel Admission Test

A three-gate framework. Every proposal — new subsystem, new dependency, new capability — passes through all three before it enters the kernel.

**Gate 1 — Necessity** *(any "no" disqualifies)*
- Does this strengthen at least one Invariant or uphold at least one Law, rather than merely adding convenience?
- Is this genuinely about coordination, governance, resource lifecycle, event routing, or intent validation — the kernel's own job — rather than about performing work?
- Would OCBrain's identity (Part I) be incomplete without this, or could this exist on top of OCBrain instead?

**Gate 2 — Placement** *(if Gate 1 passes, where does it actually belong)*
- Could this be satisfied by an **Adapter** — one external system, wrapped?
- Could this be satisfied by a **Capability** — a unit of schedulable work?
- Could this be satisfied by a **Workflow** or **Plugin** — a composition of existing capabilities?
- Could this be satisfied by an **External Service** held at arm's length — advisory, reviewable, never self-executing?
- Only if none of the above cleanly apply does it belong inside the kernel itself.

**Gate 3 — Durability** *(before final acceptance)*
- Is this stated as the problem it solves, not the technology that currently solves it?
- Would this still describe the right shape of solution in ten years, even if every current implementation were replaced?
- Does accepting this now foreclose a future, better implementation of the same need?

**Standing requirement:** this test is not applied only to new proposals. It is re-applied, on a regular cadence, to everything already inside the kernel. Kernel contents that no longer pass Gate 1 are candidates for demotion to Capability or Adapter status — not permanent residents by default.

---

## Part VI — Non-Goals

- **Not another chatbot.** A chatbot is an application built on the kernel; the kernel has no concept of "conversation" as a primitive, only Intent and Resources.
- **Not another LLM wrapper.** Models are Adapters — one of several possible backends for a capability — never a privileged dependency.
- **Not another RAG framework.** Retrieval is a capability, not the kernel's identity.
- **Not another workflow automation tool.** Workflow orchestration is a kernel runtime responsibility; "workflow automation" as a product category describes what runs on the kernel, not the kernel's purpose.
- **Not another MCP implementation.** MCP is today's best adapter protocol, not the kernel itself — the kernel must survive MCP being superseded by something else.
- **Not an autonomous agent free of governance.** Capability without governance is exactly what the Law of Bounded Autonomy forbids, regardless of how capable the system becomes.
- **Not a cloud service.** The kernel's default posture is local-first and user-owned; cloud is an optional adapter backend, never required substrate.

These systems may exist *on top of* OCBrain. They are not OCBrain itself.

---

## Part VII — Architectural Layers

| Layer | Responsibility |
|---|---|
| **Substrate** (hardware, OS, network) | Exists. The kernel never manages it directly — only through Adapters. |
| **OCBrain Kernel** | Scheduling, governance, event routing, resource lifecycle, capability resolution, intent validation. Owns nothing but abstractions. |
| **Adapters** | Translate one specific external system — a model provider, a version-control host, a browser, a robot — into the kernel's capability contract. Disposable and replaceable by design. |
| **Capabilities** | Units of work the kernel can schedule. May be backed by one adapter or composed of several. |
| **Applications / Workflows** | Compositions of capabilities assembled to satisfy a specific intent. This is where "an assistant," "a coding agent," "a research tool" live — built *on* OCBrain, never *as* OCBrain. |
| **Users** | Sovereign owner of data, policy, and final authority over what gets adopted. |

---

## Part VIII — Future Evolution

This Constitution governs principles. It does not govern technology.

Three layers exist beneath it, each free to evolve at its own pace, provided none violate a Law or Invariant above:

- **Architecture Specifications** describe the current best answer to how the kernel's principles are realized — the shape of the resource model, the stages of intent compilation, the protocols adapters speak. These may be rewritten entirely without amending this Constitution, as long as the resulting architecture still passes the Admission Test.
- **Implementation** is the actual running code. It may lag, exceed, or partially satisfy the current Architecture Specification at any given time; the project's existing engineering rules already govern how that gap is tracked and closed.
- **Roadmap** sequences implementation work over time. It is the most volatile layer and carries no constitutional weight at all.

Amending this Constitution is different from changing any of the above, and should be rare. An amendment requires: identifying the specific Law, Invariant, or Principle being changed; evidence from real implementation experience — not speculative preference, per the Law of Evidence over Assumption — that the current wording is actually wrong rather than merely inconvenient; and explicit approval, recorded with `FINAL` status through the same architecture-decision mechanism already used for the rest of the project. A Constitution that changes as easily as a roadmap item is not a Constitution.

---

## North Star

> **The kernel coordinates; it does not own.**

Every Law and Invariant above is a specific consequence of this one sentence. When a future decision doesn't clearly map to an existing Law, this is the question to ask first: does the proposed change increase what the kernel *owns*, or what it can *coordinate without owning*? Resolve in favor of the latter.

---

*Constitution draft complete. See `OCBRAIN_KERNEL_CONSTITUTION_RATIONALE.md` for section-by-section reasoning, the comparison against the source Directive, the Constitution/Architecture/Roadmap separation, deferred decisions, naming review, and self-critique.*
