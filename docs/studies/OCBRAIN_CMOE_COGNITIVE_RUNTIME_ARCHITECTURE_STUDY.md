# OCBrain C-MoE — Cognitive Runtime Architecture Study
## Final Architecture, Research, Reconciliation & Implementation-Plan Study

> **Renamed and corrected Aug 29, 2026.** This document was originally titled around "K4.3 — Cognitive Runtime / C-MoE," accepting its governing prompt's premise that C-MoE is the milestone immediately following K4.2. A follow-up study, `OCBRAIN_KERNEL_COMPLETION_STUDY.md`, found this premise wrong: no canonical document defines a "K4.3" milestone, and every authoritative source (`IMPLEMENTATION_ROADMAP.md`, and this document's own primary source `OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md`) consistently places C-MoE **after Kernel v1.0 freeze**, not immediately after K4.2. Kernel v1.0 is not yet frozen — see the Kernel Completion Study for the two specific, still-open decisions blocking it.
>
> **What this means for the document below:** its technical architecture — the expert model, routing mechanics, WorkGraph, outcome contract, memory scope model, task-mutation handling, and the reality-grounding sub-study's conclusions — is not invalidated and remains this project's most detailed C-MoE design work. What is wrong is the framing that it is "K4.3," that it follows K4.2 directly, and any implementation sequencing that assumed the Kernel was already a settled foundation to build on. Read this document as **post-Kernel-freeze C-MoE architecture research**, not as a numbered next milestone. Its own MVP/Packet-0 sequencing (§93/§96) should be re-read through that lens: several of its "Packet 0" items (checkpoint/resume, the dispatch-bridge generalization) are, per the Kernel Completion Study, more precisely Kernel-completion work than C-MoE work — the two documents agree on *what* needs to happen, and now correctly agree on *when* relative to Kernel freeze too.


**Status:** Research complete. Architecture proposed. **Not implemented. Do not begin K4.3 implementation from this document alone — it requires ADR ratification first, per its own recommendation in §96.**
**Date:** August 28, 2026
**Repository state studied:** `main`, HEAD at time of writing includes the `feature/execution-progress-inspection` merge (K4.4 watchdog baseline, commit `7ca7f35` and follow-ons) and the five same-day "K4.2 completion" commits (`0259e7e`…`71d937a`) that flipped `use_k42_frontend` to `true`. Both are treated as ground truth for this study; see §83.
**Scope:** Research, reconciliation, and architecture proposal only, per the governing task. No code was changed in the repository as part of this study. This document, its ADR follow-ons, and routine tracking-doc synchronization (CURRENT_STATE.md / KNOWN_ISSUES.md, §83) are the only repository writes associated with it.
**Author:** Claude (K4.3-CMoE-study session) — evidence-classified per §92.

---

## How to read this document

Every numbered section below corresponds to the deliverable table of contents in the governing task, **with one explicit, honest exception**: while drafting §44–90, two closely-related topics earned their own heading beyond the governing task's 100-item list (§46 "Memory != Task State," a short bridge into the formal model, and §63 "Health != Capability Fit," a direct corollary of Expert Performance History), and the three separately-listed metrics topics (canonical items 88–90) are presented together under one heading, §90, because they share one short, tightly-coupled treatment. Net effect: sections **1–45 and 91–100 match the governing task's numbering exactly**; sections **46–90 are topic-complete but carry two extra headings and one three-way merge relative to the canonical list**. Rather than physically reorder ~1,150 lines and every internal cross-reference to force exact number parity — a high-risk operation for a low-value cosmetic gain — this mapping table makes every canonical item locatable directly:

| Canonical # | Topic | Found at | | Canonical # | Topic | Found at |
|---|---|---|---|---|---|---|
| 46 | State vs Knowledge vs Evidence vs Decision | §55 | | 69 | Adaptive Learning Boundary | §71 |
| 47 | Controlled Result Promotion | §47 | | 70 | Capability/Skill Evolution Boundary | §72 |
| 48 | Memory Write Authority | §48 | | 71 | User Cognitive Model | §73 |
| 49 | Memory Read Authority | §49 | | 72 | Proactive Optimization/Fable | §74 |
| 50 | Contradiction/Supersession | §50 | | 73 | Claude Opus Behavioral Target | §75 |
| 51 | Authority/Precedence | §51 | | 74 | C-MoE vs Neural MoE | §76 |
| 52 | Freshness/Temporal Validity | §52 | | 75 | Determinism | §77 |
| 53 | Memory Correction/Deletion | §53 | | 76 | Governance | §78 |
| 54 | Memory Poisoning | §54 | | 77 | Human Approval | §79 |
| 55 | Cross-Project Boundaries | §56 | | 78 | Observability | §80 |
| 56 | Cross-Task Result Sharing | §57 | | 79 | OCBrain Studio Compatibility | §81 |
| 57 | Artifact Lineage | §58 | | 80 | External Research Findings | §82 |
| 58 | Artifact Version/Compatibility | §59 | | 81 | GitHub/Open-Source Findings | §83 |
| 59 | Partial Reuse | §60 | | 82 | Previous OCBrain Study Reconciliation | §84 |
| 60 | Expert Lifecycle | §61 | | 83 | Current Repository Audit | §85 |
| 61 | Expert Performance History | §62 | | 84 | Architecture Ownership Matrix | §86 |
| 62 | Security/Instruction Hierarchy | §64 | | 85 | Architectural Risks | §87 |
| 63 | Secrets Isolation | §65 | | 86 | Failure Matrix | §88 |
| 64 | Cognitive Provenance | §66 | | 87 | Evaluation Strategy | §89 |
| 65 | Context Compiler Boundary | §67 | | 88 | Wasted-Work Metrics | §90 (merged) |
| 66 | Evaluation & Reliability Boundary | §68 | | 89 | Contamination Metrics | §90 (merged) |
| 67 | Verification Boundary | §69 | | 90 | Goal-Drift Metrics | §90 (merged) |
| 68 | Reflection Boundary | §70 | | 91–100 | (all remaining topics) | §91–100, exact match |

This document's own §-cross-references throughout the text point to **its own section numbers** (the right-hand column above), not the canonical numbers — this table exists solely to answer "where is canonical item N," not to be memorized before reading further. Each section states, inline, what kind of evidence backs its claims: **[FACT]** (directly observed in this repository's code, tests, or documents — re-verified in this session, not carried over from memory), **[STUDY]** (a conclusion already reached by a prior OCBrain study, reconciled here), **[EXT]** (external academic or open-source evidence, freshly gathered), **[INFER]** (architectural inference drawn from the above), or **[DECISION]** (a design choice this study is making, with its trade-off stated). Where prior OCBrain research already answered a question well, this study says so and cites it rather than re-deriving it from nothing — see §82. Where prior research or the standing architecture documents turn out to be wrong or incomplete, this study says that explicitly and replaces it, per the governing task's final instruction.

A note on evidence provenance for this specific session: three internal documents did almost all of the heavy lifting this study reconciles against —`OCBRAIN_RELIABILITY_DURABLE_EXECUTION_ARCHITECTURE_STUDY.md` (Aug 21, cited throughout as **RS**), `OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md` (Aug 22, cited as **CS**), and `WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md` (Aug 26, cited as **WE**). None of the three had been elevated to an ADR or a `docs/studies/` deliverable at the time this session began. This study's job is to reconcile them against each other, against the code as it stands today (which moved twice since RS/CS were written — see §83), against the Kernel Constitution, against the newly-specified planning-feedback/task-mutation/project-memory scope that RS and CS did not cover, and against fresh external research.

---

# 1. Executive Summary

**[INFER]** OCBrain K4.3 is not a new execution engine, a second Planner, or a generic workflow product feature. It is the **Cognitive Runtime**: the component with standing authority to decide, continuously and at runtime, what should happen next to bring a Planner-authored `ExecutionPlan` into satisfied reality — given the plan, the current state of execution, the pool of available experts, and everything that has actually happened so far. Its formal name inside OCBrain is **C-MoE**, a **system-level Cognitive Mixture of Experts** — a term borrowed from neural MoE for its shape (a gate, a pool of specialists, sparse activation) but not its mechanism (no gradients, no token-level dispatch, no differentiable gate — see §74).

Four findings from this study should change how the project thinks about K4.3 before a single line of implementation is written:

1. **[FACT]** The bridge that currently lets a `WorkflowNode` reach an executing worker (`core/workers/capability_executor.py`, "Runtime Integration Task 4") only works today because exactly one `capability_type` (`llm_completion`) is registered anywhere in the system. Its own docstring says so: *"If a second capability_type is ever registered, this worker does not [scale]."* C-MoE's entire reason for existing is to route across **more than one** expert. This means the current dispatch path is not a foundation K4.3 builds on top of — it is a load-bearing single-capability assumption that **must** be replaced as part of K4.3's minimum viable scope, not after it. This is the single most concrete, code-verified architectural risk this study found (§85, §93).
2. **[FACT]** A primitive form of exactly the "Plan Reality Feedback" loop this study was asked to design already exists and already ships: `ExecutionPlan.caused_by` (an `Optional[str]` event ID, ADR-K4.2-H-09) is populated when a plan resulted from the Orchestrator's K4.2-branch re-plan loop reacting to a `cognitive.planner_impasse` event (added the same day as the `use_k42_frontend` flip — §83). This is not a green field. K4.3's Plan Reality Feedback contract (§8) is this mechanism's generalization, not a new invention.
3. **[FACT]** K4.2 stopped being a feature-flagged experiment and became the live default path in the last 24 hours of repository history relative to this study (`use_k42_frontend: true`, verified independently against the full test suite — 1,331 passed / 34 failed, all 34 pre-existing and environment-only, zero regressions from the flip). K4.3 is now being designed against what production traffic actually produces, which is a materially stronger position than designing against an opt-in experiment.
4. **[STUDY][FACT]** Two prior, unpublished internal studies (RS and CS, see front matter) already did most of the deep mechanical design work for the routing/runtime half of this problem, in the same evidence-first style this document uses, and reached conclusions this study largely upholds: WorkGraph as live realization distinct from ExecutionPlan-as-strategy (§16); a single-node Work Graph as the correct K4.3 MVP boundary, full distributed graphs deferred (§93–94); `model_router.py`'s bootstrap→shadow→native state machine as the reference pattern for any future capability-maturity lifecycle (§60); and the Watchdog/Supervisor/C-MoE authority split validated with one correction (§33–34). What neither prior study did — because neither was scoped to — is the planning-feedback contract, task mutation, or the Project/Discussion/memory-scope architecture this task also requires. That is this study's original contribution, built on RS/CS's mechanics rather than duplicating them.

The proposed architecture (§92) keeps C-MoE strictly bounded: it is a **routing and adaptation authority**, not a second Kernel, not a second Planner, and not an early implementation of Verification, Reflection, or Adaptive Learning. It owns one live artifact (the WorkGraph), one state machine (per work-unit runtime state), one contract (structured Capability Outcome), and one feedback channel back to Planner (Plan Reality Feedback). Everything else — memory scoping, project/discussion isolation, result promotion, durability — is modeled as infrastructure C-MoE *consumes* through governed contracts, not infrastructure it *owns*.

The Minimum Viable K4.3 (§93) is deliberately small: single work unit, single expert per step, structured outcomes, one feedback-triggered replan path, hard task isolation, and a resolved dispatch bridge. The Full K4.3 target (§94) adds composition, multi-expert disagreement handling, and the four-scope memory model. Distributed C-MoE, full Verification/Reflection/Learning runtimes, and Studio itself are explicitly out of scope (§95) and, where a matching Future Research Item already exists (FR-0004 Work Graphs), this study advances it from Research to Architecture Proposal rather than inventing a parallel concept.

---

# 2. Historical Definition of K4.3

**[STUDY]** Before this task, K4.3 existed in the repository in three incompatible states simultaneously, which is itself a finding (§85, "naming traps"):

| Source | What it actually says K4.3 is | Status |
|---|---|---|
| `docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md` and its byte-identical duplicate `k4_3_implementation_transition.md` | Despite the filename, this 455-line document (dated July 24, 2026) is entirely a packet-by-packet implementation plan for K4.2 (Packets 01–09: constraint extraction, capability discovery, planner completion, plan compilation, learning, user model, reflection/evaluation, supervisor, integration). It mentions "K4.3" exactly once, as a forward reference to "Cognitive Runtime (C-MoE)" citing "Evolution Directive §277–303." | **[FACT]** Misnamed. This is the completed K4.2 plan, not K4.3 architecture. Both copies should be renamed (e.g. to `K4_2_IMPLEMENTATION_TRANSITION.md`) as part of this study's documentation cleanup — see §98. |
| `OCBrain Architecture Evolution Directive.md` (**AED**), §277–303 | The actual origin of C-MoE in this project: a short conceptual sketch (Kernel = permanent substrate; Capabilities = Cognitive Experts; C-MoE = dynamic multi-expert selection; a Work Graph; a placeholder Capability Outcome Contract; an explicitly deferred future "Execution Reliability & Observability" subsystem) written as *architectural direction*, not a specification. Everything downstream (K4 §6, K5, RS, CS) traces back to this. | **[STUDY]** Genuinely the seed of K4.3, but it predates the Kernel Constitution, predates any implementation, and — per its own framing — was never meant to be implemented as written. Treated here as directional evidence, not settled architecture (matching the governing task's §121 instruction not to preserve prior conclusions merely because they are prior). |
| RS and CS (this study's main reconciliation partners) | Two deep, unpublished, un-ADR'd internal studies that already treat "K4.3 = C-MoE" as settled and design against it in detail. | **[STUDY]** The most mechanically correct existing material. Reconciled throughout this document rather than repeated. |

**[DECISION]** This study adopts the governing task's framing without alteration: **K4.3 = Cognitive Runtime = C-MoE.** Every other historical fragment is subordinate to that framing and is either reconciled into it or explicitly superseded.

---

# 3. Why K4.3 = Cognitive Runtime / C-MoE

**[INFER]** K4.2's own architecture (`OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md`) ends at `ExecutionPlan` — a **[FACT]** re-verified dataclass (`core/cognitive/planner.py`) carrying `resource_id, produced_by, goal_id, steps: List[PlanStep], confidence, alternatives, justification, lifecycle_state, caused_by, general_purpose_only`, where `PlanStep` is deliberately minimal (`step_id, description, capability_type, error_branch`). That minimalism is not an oversight — the code's own docstring is explicit that Plan Compiler's job is to reduce this richer reasoning "down to the single concrete sequence WorkflowRuntime already knows how to run," and that *which* worker actually executes a given `capability_type` is compilation's job, not Planner's.

This creates a structural gap that nothing currently owns: **the space between "here is a plan expressed as capability types" and "here is a worker actually running."** Today that gap is bridged by a single-purpose hack (§85). Architecturally, it should be owned by a component whose entire job is: given this step's declared `capability_type`, the current pool of experts that could satisfy it, their eligibility and history, and what has already happened in this task, decide **which actual expert(s) run now**, and after they run, decide **what happens next**. That is C-MoE. K4.2 answers "what should be done." K4.3 answers "who does it, right now, given reality, and what do we do when reality disagrees with the plan." Those are different questions requiring different authority, which is why they are different milestones rather than a bigger K4.2.

---

# 4. Planner vs C-MoE vs Execution

**[DECISION — validated, not merely preserved]** The four-way separation the governing task offers as a hypothesis is correct, and this study did not find a reason to collapse or rearrange it:

```
Planner            = strategic plan generation (K4.2, existing)
C-MoE              = adaptive operational realization of the plan (K4.3, this study)
Workflow/Execution = execution substrate (K2.2 legacy + K4.4 watchdog baseline, existing)
Verification       = determines whether the resulting reality satisfies intent (future milestone)
```

**[FACT]** This maps cleanly onto code that already exists on both sides of the K4.3 gap: `core/cognitive/planner.py::plan()` produces `ExecutionPlan` (Planner side); `core/workflow/runtime.py` (`WorkflowRuntime`) and `core/runtime/execution_runtime.py` (`ExecutionRuntime`) already execute compiled `WorkflowDefinition`s (Execution side). C-MoE is genuinely the missing middle, not a relabeling of either existing side.

**[INFER]** The distinguishing test between Planner and C-MoE is **when** each is allowed to decide something and **on what information**. Planner decides *before* any step has executed, using the goal, constraints, static capability metadata, and — per the reconciled finding below — a bounded, factual `RealityBrief`. C-MoE decides *during and after* execution, using everything Planner had plus what has actually happened. A component that makes a "which expert" decision before any execution has started is doing planning-adjacent work (arguably still Planner's, or Plan Compiler's); a component that makes that decision in light of a `WorkerResult`, a `FailureType`, or a partial outcome is doing C-MoE's job. This test is used throughout §17–30 to keep routing-mechanism proposals on the correct side of the line.

**[STUDY — reconciled from the companion Reality-Grounding sub-study]** A dedicated sub-study (`OCBRAIN_K4_3_REALITY_GROUNDING_SUBSTUDY.md`) investigated whether Planner should plan against more than static capability metadata, given a **[FACT, independently re-verified there]** confirmed gap: `core/cognitive/planner.py::plan(request, registry, ...)` takes exactly those two inputs today — no prior WorkGraph outcome, no Project Memory, no expert-health signal reaches it. That sub-study's verdict, adopted here: **adopt with modification.** Planner gains one new, conditional, read-only input — a `RealityBrief`, assembled by a thin "Reality Assembly" function that is explicitly a pre-Context-Compiler stub (§67), never a C-MoE responsibility and never a standing fourth authority alongside Memory/C-MoE/Context Compiler. The sub-study explicitly rejected two tempting alternatives: an iterative Planner↔C-MoE "dialogue" (a two-participant recursive loop, forbidden in spirit by `PROJECT_INSTRUCTIONS.md` §5's ban on uncontrolled recursive agent loops, and lacking any principled termination/convergence condition), and a new standing "Reality/State Layer" component (fails the Kernel Admission Test's Gate 1 — it is retrieval-and-filtering over Memory and capability health, not a new irreducible coordination responsibility). The one new C-MoE-side obligation this adds is a **feasibility pass**: after Planner drafts a plan against its `RealityBrief`, C-MoE's own eligibility funnel (§20) runs once against the draft's declared `capability_type`s before execution starts, producing a `FeasibilityResult` that either clears the plan or sends it back to Planner for a new version (§11) — never a dialogue round. `ExecutionPlan` gains one field, `based_on_snapshot: Optional[str]`, following the exact convention `caused_by` already established. Full detail, the ownership table, and the explicit K4.3-scope classification live in the sub-study; this paragraph is its incorporation point.

---

# 5. Core C-MoE Principle

**[DECISION]** Adopted verbatim as the design's north star, because it survives every stress-test this study ran against it (§26, §87):

> **C-MoE must optimize for successful realization of the current authorized goal, not merely successful execution of the current plan.**

**[INFER]** This principle has one direct, non-negotiable implementation consequence: C-MoE must never be permitted to report `FAILED` at the *goal* level solely because one *plan* or one *expert invocation* failed. It must be structurally required to ask "is the goal still reachable via a different route" before it is permitted to surface failure upward. This is why the Capability Outcome Contract (§30) separates step-level and expert-level outcomes from goal-level ones, and why "goal drift" gets its own metric category (§90) rather than being folded into ordinary failure-rate tracking.

---

# 6. Closed-Loop Runtime Model

**[STUDY — reconciled]** Per §4's incorporation of the Reality-Grounding sub-study, the loop gains one conditional step *before* its first edge, which the sub-study's §7 specifies must be skippable for simple, no-project, no-side-effect requests rather than run unconditionally:

```
Goal → [conditional: Reality Assembly → RealityBrief] → Planner → Plan
     → [C-MoE feasibility pass, reusing §20's eligibility funnel] → (feasible ↓ / infeasible → new Plan version)
     → C-MoE realization loop (unchanged, below)
```

This pre-loop step is deliberately thin: it is a single request/response, never a dialogue, and its output is restricted to facts and evidence (§55) — the moment it contains a strategic recommendation rather than a fact, it has become a second Planner, which is exactly the failure mode this addition must not reintroduce. The loop below, which is C-MoE's actual ongoing runtime authority once execution has started, is unchanged by this addition.

**[DECISION]** The closed loop from the governing task is adopted with ownership assigned per transition — the governing task explicitly asks who owns each edge, and leaving that unanswered was one of RS's central complaints about the pre-Kernel-Constitution architecture (RS §D, "authority fragmentation"):

| Transition | Owner | Evidence |
|---|---|---|
| Goal → Planner → Plan | Planner | **[FACT]** existing, `plan()` |
| Plan → C-MoE | Orchestrator handoff | **[DECISION]** new, K4.3 |
| select / compose / adapt / execute | **C-MoE** (decision) → **ExecutionRuntime** (mechanics) | **[DECISION]** — C-MoE decides *what*, ExecutionRuntime performs *how*, matching Kernel Constitution Law 3 (Separation of Concerns) |
| Runtime reality → structured outcome | Expert / adapter, surfaced through ExecutionRuntime | **[DECISION]**, contract in §30 |
| C-MoE interprets outcome → decision | **C-MoE**, sole owner | **[DECISION]** — this is C-MoE's one truly exclusive authority; see §32 for why this must not be shared |
| continue / adapt / route / compose / modify graph / request info / request verification / recover / replan / suspend / terminate | **C-MoE proposes, GovernanceKernel authorizes** | **[DECISION]**, per Kernel Law 1 (Bounded Autonomy) — no C-MoE decision executes ungoverned; see §76 |

**[INFER]** The one edge worth calling out explicitly: "C-MoE interprets outcome → decision" must be a single-writer operation per work unit. Two independent authorities racing to interpret the same outcome (e.g., Supervisor and C-MoE both reacting to the same `WorkerResult`) is exactly the "duplicate recovery authority" failure mode this study spends §33–34 and §85 resolving.

---

# 7. Goal Preservation

**[DECISION]** Adopted as a hard invariant, stated precisely to be testable rather than aspirational:

> Replanning may change strategy, decomposition, capabilities, execution order, and the remaining Work Graph, but must preserve the active authorized `goal_id` (and its governing constraints) unless the user explicitly changes them, cancels them, or governance makes them impossible.

**[FACT]** This is directly checkable against existing code: `ExecutionPlan.goal_id` is already a field, and `ExecutionPlan.caused_by` already exists to link a recovery re-plan back to the impasse that caused it. **[DECISION]** The concrete, automatable test this study proposes: for any two plan versions `Plan(v)` and `Plan(v+1)` where `v+1` was produced by a C-MoE-triggered replan (not a user-initiated task mutation, see §10), `Plan(v+1).goal_id == Plan(v).goal_id` must hold, and any test suite covering the replan path should assert this directly. A goal-level change may *only* originate from a user-initiated mutation (§10) or an explicit governance ruling, never from C-MoE's own replan trigger. This turns "goal preservation" from a principle into a unit-testable contract, which the governing task's §112 (goal-drift metrics) requires.

---

# 8. Plan Reality Feedback

**[FACT]** This is the section where the "do not restart research from zero" instruction pays off most directly, because the contract already exists in miniature. Confirmed in code (`core/cognitive/planner.py`, `ExecutionPlan` docstring):

> `caused_by` (K4.2-H1 D9, ADR-K4.2-H-09): `Optional[str]` event_id. None for a plan produced by the ordinary `plan()` path; populated when this plan resulted from a recovery re-plan (Orchestrator's K4.2-branch re-plan loop) triggered by a specific prior impasse event.

And, from the same-day G1–G7 upload (§83): a new `cognitive.planner_impasse` event is now actually emitted at the point where the Orchestrator's re-plan loop fires.

**[DECISION]** This is the seed of `PlanRealityFeedback`, not a different mechanism. The governing task's proposed field list is a reasonable superset, but this study's job is to find the *minimum correct* one (per the task's own instruction), and the minimum correct one is smaller than the proposal, because several of the proposed fields are already event-log-derivable rather than needing to live in a new struct:

| Proposed field | Disposition | Reasoning |
|---|---|---|
| `task_id`, `goal_id`, `goal_version` | **Keep** | Needed for the goal-preservation test in §7; `goal_version` is new (goals do not currently version — see §11) |
| `plan_id`, `plan_version` | **Keep**, map to `ExecutionPlan.resource_id` / a new integer version | `resource_id` already exists; version is new |
| `current_runtime_state` | **Reference, don't embed** | This is the WorkGraph's own state (§16) — feedback should carry a WorkGraph snapshot reference, not a duplicate copy, to avoid two sources of truth for the same state (Kernel Law 9) |
| `completed_work` / `pending_work` / `failed_work` | **Keep, as WorkGraph node-ID sets, not free text** | Making these structured (sets of node IDs with a status enum) rather than prose is what lets Planner's replan actually skip already-done work mechanically (§12) rather than merely being told about it |
| `partial_results` | **Keep, by reference to Resource IDs**, not embedded payloads | Avoids duplicating potentially large artifacts inside an event |
| `failure_reasons` | **Keep, typed as `FailureType`** (already exists — WE, §32) not free text |
| `discovered_facts` | **Keep**, but scoped: these are candidate **Evidence** (§56), not yet **Knowledge** — see the State/Knowledge/Evidence/Decision separation in §55 |
| `invalidated_assumptions` | **Keep**, expressed as WorkGraph-node invalidation reasons (§13), not a separate list |
| `active_constraints` / `changed_constraints` | **Only `changed_constraints` is new** — active constraints already live on `Goal`; feedback need only carry the diff |
| `unavailable_capabilities` / `available_alternatives` | **Keep**, sourced from CapabilityRegistry health state (§64), not duplicated |
| `evidence` / `verification_status` | **Keep `verification_status` as an enum stub** (`UNVERIFIED` default) — full Verification is out of scope (§77) but the field must exist so Verification has somewhere to write later without a schema migration |
| `resource_usage` / `remaining_budget` | **Keep**, sourced from `ExecutionBudget` (already exists, K4.4) |
| `recommended_next_action` | **Keep, as a closed enum**, not free text — this is C-MoE's structured recommendation to Planner, and an open string here would recreate the exact "opaque LLM decided" problem §80 forbids |

**[DECISION]** Net result: `PlanRealityFeedback` is real, but it is mostly a **typed view over the WorkGraph and event log at the moment C-MoE requests replanning**, not a new duplicate state container. This keeps it consistent with Kernel Law 2 (Explicit State) and Law 9 (Single Source of Truth) — the feedback object is a projection, not a second copy of truth.

---

# 9. Goal Evolution

**[DECISION]** Goal evolution (system-triggered, via §8) and user task mutation (user-triggered, §10) must be kept as distinct code paths even though both eventually produce a new `Goal`/`Plan` version, because they have different authority sources and different validity rules:

| | Goal evolution (this section) | User task mutation (§10) |
|---|---|---|
| Trigger | C-MoE-detected impasse (`cognitive.planner_impasse`) | User message |
| Who may change `goal_id`'s *content* | Nobody — content is frozen | The user, explicitly |
| Who may change the *strategy* | C-MoE requests, Planner executes | Planner, directed by the diff in §10 |
| Governing invariant | §7 (goal preserved) | §10 (impact analysis before discard) |

**[INFER]** Conflating these two paths was flagged by RS as a risk category ("silent goal degradation") even though RS did not have the task-mutation scope available to name it this precisely. Keeping them as two entry points into the *same* versioning mechanism (§11) rather than two versioning mechanisms is what prevents that conflation from becoming two divergent implementations.

---

# 10. User Task Mutation

**[DECISION]** User task mutation is modeled as a typed diff against the active `Goal`, not as a new conversational turn re-entering Planner from scratch. Adopting the governing task's mutation categories with one merge (BRANCH/MERGE are promoted to their own primitive, §15, rather than being mutation categories, because they produce a second lineage rather than modifying the first):

```
ADD · REMOVE · MODIFY · RESTRICT · RELAX · PRIORITIZE · REORDER · REPLACE
```

**[INFER]** The hard part is not the taxonomy, it is distinguishing a *correction* ("no, that's not what I meant") from a *change* ("actually, change the requirement") at intake, because they demand opposite reuse behavior: a correction implies the prior interpretation was **never valid** (everything derived from it is `INVALID`, §12), while a change implies the prior interpretation **was valid at the time** and remains partially reusable (§12's `STALE`/`REUSABLE` middle ground). **[DECISION]** This study does not recommend trying to classify correction-vs-change purely from message text at the C-MoE layer — that is Intent/Constraint-extraction's job (K4.2, existing `core/cognitive/intent.py`), which already produces a structured `Goal`. C-MoE's mutation handling should consume Intent's classification (a new boolean or enum: `is_correction`), not re-derive it from the raw message. This keeps the boundary from §16 clean: K4.2 still decides "what did the user mean," K4.3 only decides "what does this mean for the plan and graph that already exist."

---

# 11. Goal Ancestry

**[DECISION]** Goals gain an explicit version chain, mirroring the pattern `ExecutionPlan.caused_by` already established for plans:

```python
@dataclass
class Goal:
    ...
    version: int = 1
    parent_goal_id: Optional[str] = None       # None for v1
    derived_from: Optional[str] = None          # event_id: impasse OR user-mutation event
    relationship: Optional[GoalRelationship] = None  # supersedes | preserves | narrows | expands | conflicts_with
```

**[FACT]** `Goal` does not currently version (confirmed: no `version` field surfaced in any of the planner/intent code paths read during this study, and none of RS/CS/AED mention one — this is a genuine gap, not a rediscovery of something that exists). **[INFER]** This is a small, additive, backward-compatible change (default `version=1`, `parent_goal_id=None` for every goal created today), which matters because it means goal versioning can ship in the MVP (§93) without touching any existing `Goal` consumer that doesn't care about lineage.

---

# 12. Plan Impact Analysis

**[DECISION]** Adopting a five-state classification, deliberately trimmed from the governing task's eight-state suggestion — this study could not find a code-level or research-level justification for keeping `CANCELLED` and `NEW` as *impact-analysis* outcomes rather than ordinary WorkGraph node states (§16), so they are removed from this enum and left as WorkGraph states instead, per the Kernel Law 9 instinct of not representing the same fact two ways:

```
VALID                  — unaffected by the change, reusable as-is
REUSABLE               — affected but the existing result still satisfies the new goal
STALE                  — was valid, dependencies changed, needs revalidation before reuse
DEPENDENCY_BROKEN      — a transitive dependency (§13) was invalidated; this node inherits that
REQUIRES_RECOMPUTATION — confirmed invalid, must redo
```

**[INFER]** The trade-off this study makes explicitly: `REUSABLE` and `STALE` are genuinely different actions (use immediately vs. cheaply re-verify before use), and collapsing them (as a simpler 3-state VALID/STALE/INVALID model would) would remove exactly the distinction the governing task's §12 (efficient recomputation) needs to make its cost/benefit trade-off decidable. Five states is the minimum that keeps that decision mechanical rather than requiring judgment calls per node.

---

# 13. Dependency-Aware Invalidation

**[DECISION]** Mandatory, and only tractable because the WorkGraph (§16) is a DAG by construction. Propagation rule: when a node's classification (§12) becomes `REQUIRES_RECOMPUTATION`, every node with a directed edge *from* that node inherits `DEPENDENCY_BROKEN` (not `REQUIRES_RECOMPUTATION` directly — the distinction matters because a `DEPENDENCY_BROKEN` node may still resolve to `REUSABLE` once its dependency is recomputed, if its own output doesn't actually depend on the *value* that changed, only on the *fact that the upstream node ran*). **[INFER]** This is standard DAG reachability (transitive closure over the "depends-on" edge set), not a novel algorithm — the governing task's explicit warning against "simplistic file-level or node-level diffing that ignores dependencies" is satisfied by doing the propagation over the WorkGraph's real edges rather than, e.g., string-matching step descriptions.

---

# 14. Efficient Recomputation

**[DECISION]** C-MoE makes the trust-vs-recompute trade-off using three inputs, each already available or cheaply derivable: (1) the node's classification from §12, (2) the node's **result confidence** at the time it was produced (§20 — confidence is not one number, and this is specifically *result* confidence, not routing confidence), and (3) the cost of recomputation (expert cost/latency metadata, §17). **[DECISION]** Concrete rule proposed for the MVP: a `STALE` node is revalidated (cheap: a targeted verification or a diff-check against current constraints) rather than blindly reused *or* blindly recomputed, whenever revalidation cost is materially lower than recomputation cost — which for most research/retrieval-style steps it is, and for most generation steps it is not (regenerating text is often cheaper than a rigorous check that old text still satisfies new constraints). This is stated as a starting heuristic, not a learned policy — full cost-aware learning is explicitly deferred (§70, Adaptive Learning boundary).

---

# 15. Branch / Rollback / Merge

**[DECISION]** Modeled as WorkGraph-level operations, not as new Goal or Plan primitives — a branch is two live WorkGraphs sharing a `parent_goal_id` and a common ancestor node set, not two goals:

| User utterance | WorkGraph operation |
|---|---|
| "Try another approach but keep this one" | Fork WorkGraph at current frontier → two active graphs, same `goal_id`, `branch_id` A and B |
| "Go back to the previous approach" | Reactivate a previously-forked (not necessarily completed) branch; deactivate current |
| "Compare these two approaches" | Both branches run to a comparable checkpoint; C-MoE requests a synthesis/aggregation composition (§27) over both outputs |
| "Use the best parts of both" | Explicit merge: a new node whose inputs are both branches' outputs, routed to a synthesis expert |

**[DECISION]** Branching is included in the **Full K4.3 target** (§94), not the MVP (§93). Justification: everything upstream of branching (goal ancestry §11, impact analysis §12, dependency invalidation §13) is a hard MVP dependency for branching to be safe, but branching itself adds no new *authority* question — it is a WorkGraph shape question, cleanly separable, and the governing task's own MVP framing (§105 in the original draft, "smallest implementation that honestly deserves the name C-MoE") does not require multi-branch reasoning to be honest about single-branch adaptive routing.

---

# 16. Planner / WorkGraph Relationship

**[DECISION — validated from CS, not re-derived]** CS's central hypothesis is upheld without modification, because it survives this study's own adversarial pass (§87) and because it maps cleanly onto the `ExecutionPlanLifecycle` states that already exist in code but are not yet driven by anything:

> `ExecutionPlan` = Planner's strategy (a hypothesis about how to reach the goal). `WorkGraph` = C-MoE's live realization of that strategy (what is actually, currently true about execution).

**[FACT]** This is not a purely conceptual claim — it is directly supported by code that already exists but is unused: `ExecutionPlanLifecycle = {draft, compiled, executing, completed, failed, superseded}`, with the Planner-side docstring confirming *"Packet 03 (Planner) only ever produces DRAFT — the remaining states belong to Plan Compilation and WorkflowRuntime."* No component currently drives `compiled → executing → completed/failed/superseded`. **[DECISION]** C-MoE is the natural owner of that transition sequence: it is the component that knows, in real time, whether the plan it received is still executing, has completed, has failed outright, or has been superseded by a replan. This gives C-MoE a concrete, existing enum to drive rather than inventing a parallel status field — directly satisfying Kernel Law 9.

**[DECISION]** WorkGraph mutation primitives, scoped to what the MVP actually needs (full list validated against CS's more exhaustive treatment, trimmed of primitives with no near-term consumer):

```
add_node · remove_node · replace_node · mark_invalid (propagates per §13)
add_verification_node · cancel_node · resume_from_checkpoint
```

Explicitly **not** included in K4.3: generic `split`/`join`/`branch`/`merge` graph algebra as a WorkGraph primitive — those are expressed at the higher branching layer (§15) using the primitives above, not as first-class graph operations. This is the concrete answer to the governing task's repeated warning against "accidentally creating another generic workflow engine": the WorkGraph's primitive vocabulary is deliberately smaller than a general DAG-editing API.

---

# 17. Expert Model

**[FACT]** Today, exactly one thing is a registered `capability_type` in the entire system: `llm_completion` (confirmed via `CapabilityExecutorWorker`'s own docstring, which states this is "the only capability_type registered anywhere in this repository today," cross-checked against `CapabilityRegistry`'s contents). Every other candidate "expert" the governing task lists — worker, adapter, tool, skill, model, specialized agent, composite capability — exists as an *architectural category* but not yet as something C-MoE would have more than one of to route between.

**[DECISION]** OCBrain needs exactly one common expert abstraction, not a taxonomy of expert *kinds*, because routing does not care what an expert *is made of* — it cares what an expert *contracts to do*. Proposed `ExpertDescriptor`, deliberately separating **semantic** fields (used for candidate generation/eligibility, §18) from **operational** fields (used for scoring/composition, §19), which is the direct fix for the K4.2 `description`-overload defect (K42-002, already fixed once — §83 — but worth generalizing so it cannot recur at the expert layer):

```python
@dataclass
class ExpertDescriptor:
    # Identity
    expert_id: str
    kind: ExpertKind            # capability | worker | adapter | tool | skill | model | composite
    version: str

    # Semantic (candidate generation / eligibility — never used for execution)
    specialization: List[str]           # capability_type(s) this expert can satisfy
    semantic_description: str           # matching signal — separate from any execution payload, by design
    context_requirements: ContractSchema

    # Operational (scoring / composition — never used for matching)
    input_contract: ContractSchema
    output_contract: ContractSchema
    permissions: PermissionScope
    resource_cost: CostEstimate
    latency_estimate: LatencyEstimate

    # Health & history (routing signals, §19)
    health: HealthState
    maturity_stage: MaturityStage        # bootstrap | shadow | native — reused from model_router.py, §60
    reliability_history: ReliabilitySummary
    provenance: str
```

**[INFER]** This is not a new pattern for the codebase — it is the same semantic/operational split the very-recent G1 fix (§83) just applied to `Goal.structured_form` (`description` for the literal request, `semantic_description` for matching signal). Applying the identical split at the expert layer, before a second `capability_type` is ever registered, is cheap insurance against the K42-002 failure mode recurring one layer up.

---

# 18. Capability Discovery vs C-MoE

**[DECISION — boundary held, not re-litigated]** RS and CS both already drew this line correctly and this study did not find a reason to move it: K4.2's `CapabilityDiscoveryRequest` / `discover_capabilities()` answers *"what could potentially help, in principle, independent of current runtime state"* — a candidate-generation function over static metadata. C-MoE answers *"given the plan, current WorkGraph state, and what has already happened, what should actually run now."* **[FACT]** The handoff point is exactly `PlanStep.capability_type` → `CapabilityRegistry` lookup: Discovery produces the *set* of experts declaring that specialization; C-MoE's routing (§19–21) narrows that set to *one or more selections*, using information Discovery never had (current health, current WorkGraph position, current budget remaining). **[INFER]** The failure mode the governing task warns against — "K4.2 discovery should not silently become K4.3 routing" — is concretely prevented by making this a hard interface boundary: Discovery is called once, at plan time, and never again for the same step; C-MoE may call it again only if it needs a *new* candidate pool (e.g., after `NeedCapability`, §28), which is itself a loggable, distinguishable event from ordinary routing.

---

# 19. Routing Policy vs Mechanism

**[DECISION]** Kept as two separate, independently-versionable artifacts, because conflating them is exactly what produced the K4.2 `description`-overload problem one layer up (routing *policy* — "prefer high-confidence, low-cost experts" — got baked into the *mechanism* — raw Jaccard scoring — with no way to change one without touching the other):

- **Routing Mechanism** = the deterministic function `(candidates, signals) → ranked_list` — code, versioned, tested like code.
- **Routing Policy** = the *weights and thresholds* the mechanism applies (how much cost matters vs. confidence vs. latency) — data, versioned like data, changeable without a code deploy.

**[INFER]** This separation is what makes routing auditable per Kernel Law 6 (Explainability): a routing decision can be explained as "mechanism M applied policy P to candidate set C, producing ranking R," and P can be inspected and changed independently of proving M is still correct.

---

# 20. Candidate Generation / Eligibility

**[DECISION]** Three-stage funnel, each stage independently testable:

```
Candidate Generation  →  Hard Eligibility Filter  →  Soft Ranking  →  Fallback Chain
(from CapabilityRegistry,   (permissions, contract      (routing signals,      (if selected
 scoped by capability_type)  compatibility, health)       §19-24)                 candidate fails)
```

**[DECISION]** Hard eligibility is a **deny-list of disqualifiers**, not an allow-list of requirements, matching WE's already-adopted pattern (`policies.yaml`-style allow/deny/require schema, identified in prior OCBrain capability-architecture research as directly reusable): permission mismatch, contract incompatibility, and `health == UNAVAILABLE` disqualify; nothing else does at this stage. Soft ranking is where §21–24's signals apply. **[DECISION]** Fallback depth is capped at a small constant (proposed: 3) as part of the cognitive budget (§43) — an unbounded fallback chain is a retry-storm risk this study's failure matrix (§87) flags explicitly.

---

# 21. Routing Signals

**[DECISION]** Classified per the governing task's own four-way split, because forcing every candidate signal through this classification is what prevents scope creep into a full learned-routing system prematurely:

| Signal | Classification |
|---|---|
| Permission compatibility, contract compatibility, health | **Hard constraint** (§20) |
| Declared specialization match | **Eligibility filter** |
| Historical success rate, verification quality, latency, resource cost, availability | **Routing signal** (soft-ranked, §19) |
| Deterministic candidate-ID ordering | **Tie-breaker** (§75) |
| Learned routing weight adjustment from outcome history | **Future learned signal** — explicitly deferred, §70 |

**[INFER]** "Risk," "diversity," and "expected information gain" (all listed in the governing task) are real signals but this study found no code-level or research-level basis for including them in the *first* implementation — they require either a cost-of-failure model (risk) or a multi-candidate exploration policy (diversity, information gain) that nothing in the current architecture computes yet. They are named explicitly in §70 as future-learned-signal candidates rather than silently dropped.

---

# 22. Confidence Model

**[DECISION]** Five distinct confidences, never collapsed into one number, because the K4.2 clarification-escalation defect this repository already lived through (§83's DEBT-013/ADR-K4.2-H-13 history: a `0.0` fallback confidence score triggering escalation regardless of *why* it was zero) is a direct, already-experienced instance of exactly the failure the governing task warns about here:

```
routing confidence          — how sure the router is that this expert is the right choice
expert confidence           — how sure the expert itself is in its own output
result confidence           — how sure C-MoE is the output is correct, post-hoc
verification confidence     — how sure Verification is (stub value until Verification exists, §77)
plan/goal-satisfaction conf. — how sure C-MoE is the *goal*, not just this step, is on track
```

**[DECISION]** These are five separate fields, never averaged into a composite score. A `LowConfidence` outcome (§28) must always name *which* of the five is low — an expert can have high expert-confidence and low routing-confidence (the router picked poorly) or the reverse (the right expert, correctly identified, is itself unsure), and the correct C-MoE response differs in each case (reroute vs. request-verification, respectively). Collapsing these was the exact mechanism behind the DEBT-013-adjacent escalation bug; keeping them separate is a direct, evidence-backed lesson from this repository's own history.

---

# 23. Abstention

**[DECISION]** C-MoE must have a first-class `abstain` outcome, not just `route` or `fail`, with three sub-modes matching the confidence model in §22:

```
route                    — normal case, confidence adequate
route_low_confidence     — proceed but flag result_confidence downstream as provisional
abstain                  — decline to route; escalate per §82 (human approval boundary)
request_information      — abstain specifically because a missing fact (not a missing expert) blocks routing
```

**[INFER]** The governing task's framing — "a forced bad routing decision is not necessarily preferable to a controlled abstention" — is directly validated by this repository's DEBT-013 history: the bug there was precisely a forced low-confidence continuation where an honest abstention (or a correctly-scoped exemption, which is what ADR-K4.2-H-13 eventually shipped) was the right call. Abstention is therefore not a new philosophy for this project; it is the generalization of a fix this project already had to make once.

---

# 24. Cold Start

**[DECISION]** An expert with no `reliability_history` (§17) is not penalized to zero — it is scored using **[FACT, reused from model_router.py]** the same `bootstrap` stage semantics `core/model_router.py` already uses for models: conservative confidence, category-inherited statistics where a broader `ExpertKind`/specialization category has history even if this specific `expert_id` doesn't, and eligibility for selection only when hard constraints (§20) are satisfied and no better-proven alternative exists. **[INFER]** This reuses `model_router.py`'s `bootstrap → shadow → native` maturity states directly (§60) rather than inventing a parallel cold-start concept — an expert's `maturity_stage` field (§17) *is* its cold-start status, unifying two things the governing task lists separately (§64 Expert Lifecycle and §24 Cold Start) into one mechanism.

---

# 25. Exploration vs Exploitation

**[DECISION]** Explicitly deferred as a *learned policy* (§70), but the architecture must not foreclose it: `maturity_stage == "shadow"` (§24, reused from `model_router.py`) already means "being evaluated in parallel without being trusted for final output" — which *is* a form of exploration, just not an adaptive/bandit-style one. **[DECISION]** K4.3 ships the shadow-evaluation mechanism (already proven at the model layer, generalized to experts); K4.3 does **not** ship a policy that decides *when* to explore a shadow candidate over a proven one for a live task — that decision requires outcome-history-driven learning, which belongs to the Adaptive Learning boundary (§70).

---

# 26. Risk-Adjusted Routing

**[DECISION]** Deferred to Full K4.3 (§94), not MVP, with the architectural hook reserved: `ExpertDescriptor.resource_cost` and a step-level `reversibility` flag (new, small addition to `PlanStep` — whether this step's side effects can be undone) are sufficient inputs for a risk-adjusted decision (expected-value routing, §24's example) once someone writes the policy, but this study did not find a strong enough case to justify writing that policy as part of MVP: the MVP has, by construction (§93), only one registered expert type worth routing between at ship time, which makes risk-adjusted *selection between multiple experts* untestable until a second expert exists. **[DECISION]** The `reversibility` flag ships in the MVP regardless (cheap, and directly useful for §82's human-approval-checkpoint logic, which does need it immediately) even though the routing policy that would consume it for risk-adjustment does not.

---

# 27. Expert Composition

**[DECISION]** Four composition primitives for K4.3, chosen as the minimum set that covers every composition pattern this study found actual evidence for (RS/CS's own composition sections, plus the AgentTether/multi-agent-failure literature, §80):

```
sequential        A → B                         (B's input includes A's output)
primary+fallback  A, else B if A fails           (§20's fallback chain, formalized)
primary+verifier  A → verify(A)                  (§77's verification hook, not full Verification)
parallel+aggregate A ∥ B → synthesize(A, B)       (§15's "use the best of both," §26's disagreement)
```

**[DECISION]** Explicitly **not** in K4.3: `critic → correction` loops (A → critic B → correction A) and unrestricted recursive composition. **[INFER]** This is a direct, evidence-backed exclusion: the AgentTether paper (arXiv:2607.06273, verified genuine via independent search — §80) exists specifically because "existing automatic remedies address only part of this problem: blind retry adds no diagnosis" — i.e., naive critic-correction loops without a diagnosis/localization step are a known, published failure mode, not merely an OCBrain concern. Building a correction loop correctly requires the diagnosis machinery AgentTether and the internal Watchdog Evolution report (WE) both treat as a distinct, non-trivial concern — appropriately deferred to a Reflection-adjacent milestone (§70) rather than folded into K4.3's composition primitives under time pressure.

---

# 28. Expert Disagreement

**[DECISION]** Disagreement is a structured runtime state (`WorkGraph` node status `DISAGREEMENT`), not an exception path, entered whenever a `parallel+aggregate` composition (§27) produces outputs that fail a similarity/consistency check. Resolution order, cheapest first:

```
1. Higher routing-confidence expert wins outright, if the gap exceeds a threshold
2. Escalate to a verifier composition (§27), if one is eligible
3. Escalate to the user (§82) if the disagreement bears on a high-impact decision
4. Trigger replanning (§8) if disagreement reveals the plan's premise itself was wrong
```

**[INFER]** Aggregation (blending both answers) is deliberately *not* the default resolution — the "Wrong but Useful: Trajectory Value Beyond Answer Correctness" line of research (surfaced during this study's academic sweep, arXiv:2608.14375) is a caution flag worth naming even without deep engagement: a wrong trajectory can still carry salvageable signal, but *blending* two disagreeing outputs by default risks producing a third, novel, unverified answer neither expert actually endorsed. Escalation-first is the safer default; blending is available only as an explicit composition choice (§27), never an automatic disagreement resolution.

---

# 29. Information-Gain Outcomes

**[DECISION]** `InformationGain` is a first-class Capability Outcome (§30), distinct from `PartialResult` — the governing task's own example (a research expert finding an API limitation with no direct solution) is not a partial answer to the original question, it is a *complete* answer to a *different, newly-relevant* question. **[INFER]** Classifying it as `PartialResult` would cause C-MoE to try to "complete" it by routing to more experts on the same step; classifying it as `InformationGain` correctly routes it to Planner as replan-triggering evidence (§8's `discovered_facts`) instead. This is a precise, non-obvious distinction the governing task is right to insist on, and getting it wrong would directly cause the "false success" / "misleading output" failure modes in the failure matrix (§87).

---

# 30. Capability Outcome Contract

**[DECISION]** Ten outcomes, added to (not replacing) the eight the AED already sketched as placeholders — this study evaluated all eight governing-task-suggested additions and kept the four with an evidenced, distinct C-MoE response, dropping the other four for lack of one:

```
Completed                  NeedInformation           LowConfidence (§22, §23)
PartialResult              NeedUserInput             InformationGain (§29)
Failed                     NeedReplan                ContradictoryEvidence (= Disagreement, §28, unified rather than duplicated)
NeedCapability             RetrySuggested            ResourceExhausted (maps directly to ExecutionBudget/WE, §33)
```

**[DECISION]** Rejected from the governing task's extended list, with reasons: `VerificationRequired` (folded into `verification_status` on the outcome, not a separate top-level outcome — it's an attribute of any outcome, not an outcome itself); `PolicyBlocked` (this is a **governance** result, not a **capability** outcome — an expert never produces this, GovernanceKernel does, so it belongs on the decision layer in §6's table, not this contract); `Unavailable` (already covered — this is a hard-eligibility filter outcome from §20, occurring *before* an expert ever runs, so it cannot be a post-execution outcome); `Deferred`/`NoProgress` (both are describable as `PartialResult` with zero delta plus a `WorkGraph` timestamp check — adding dedicated enum values for them would violate the governing task's own instruction not to create "an enormous enum without semantic necessity").

**[INFER]** The load-bearing distinction, restated precisely because it is the single most-repeated warning in the governing task: **`Failed` means the expert could not produce output. `PartialResult`, `LowConfidence`, and `InformationGain` all mean the expert produced output that does not, by itself, satisfy the goal.** These are never interchangeable, and no code path may collapse the latter three into the former for convenience — doing so is precisely how "false success" and "misleading output" enter the failure matrix (§87).

---

# 31. Runtime State Machine

**[DECISION]** Per-work-unit (not per-task) state machine, because a task's WorkGraph will eventually contain many work units in different states simultaneously (§16), so a single task-level state would immediately need to become "the state of whichever unit is most interesting," which is not a state machine, it's a summary. Ten states, each with owner/exit/events specified:

| State | Entry condition | Owner | Emits | Exit → |
|---|---|---|---|---|
| `NEW` | Node added to WorkGraph | C-MoE | `workgraph.node_created` | `READY` |
| `READY` | Dependencies satisfied (§13) | C-MoE | — | `ROUTING` |
| `ROUTING` | Candidate generation begins (§20) | C-MoE | `routing.decision` (§84) | `RUNNING` or `ABSTAINED` |
| `RUNNING` | Expert invoked | ExecutionRuntime | `execution.started` | `OBSERVING` |
| `OBSERVING` | Outcome received, pre-interpretation | C-MoE | `execution.outcome` | per §30's outcome → next state |
| `WAITING_FOR_INFORMATION` | `NeedInformation`/`NeedUserInput` | C-MoE | `cognitive.info_requested` | `READY` once satisfied |
| `VERIFYING` | Verification requested (§77 stub) | C-MoE → Verification (future) | `verification.requested` | `COMPLETED` or `REPLANNING` |
| `REPLANNING` | `NeedReplan` or impasse (§8) | C-MoE → Planner | `cognitive.planner_impasse` (**[FACT]**, exists today) | `READY` on new plan version |
| `SUSPENDED` | User pause (§35) or budget exhaustion | GovernanceKernel-authorized | `execution.suspended` | `READY` on resume |
| `COMPLETED` / `FAILED` / `CANCELLED` | Terminal | C-MoE | `workgraph.node_terminal` | — |

**[INFER]** `ABSTAINED` (§23) is a distinct terminal-adjacent state, not folded into `FAILED` — an abstention is a *decision*, not an *outcome*, and conflating the two would make it impossible to distinguish "the router chose not to act" from "an expert tried and could not" in replay (Kernel Law 4, Determinism).

---

# 32. Goal Satisfaction / Completion Contract

**[DECISION]** Four layers, kept distinct because the governing task's own example (a successful file write is not proof the objective was achieved) is exactly the gap between the bottom two layers:

```
execution complete   — every WorkGraph node reached a terminal state
plan complete        — every PlanStep has a corresponding completed node
artifact complete    — the artifact(s) named by the plan exist and are well-formed
goal satisfied        — Verification (or, until it exists, an explicit user/governance confirmation) confirms the artifact(s) actually meet the goal's intent
```

**[DECISION]** Status enum for the task as a whole (distinct from the per-node state machine in §31): `COMPLETED | COMPLETED_WITH_WARNINGS | PARTIALLY_SATISFIED | BLOCKED | FAILED | ABANDONED | CANCELLED | REQUIRES_USER`. Until Verification exists (§77), "goal satisfied" is **capped at `COMPLETED_WITH_WARNINGS`** by construction — C-MoE is explicitly forbidden from self-certifying full `COMPLETED` status for the goal layer without either a real Verification result or explicit user confirmation, because self-certified completion is precisely the "false success" failure mode (§87) and precisely the pattern this project's own operating history (`KNOWN_ISSUES.md`, "completion reports cannot be trusted without verification") warns against most forcefully. This is one of the few places this study encodes an operating principle from `PROJECT_INSTRUCTIONS.md`/prior session history directly into a data contract rather than leaving it as a norm.

---

# 33. Recovery Authority

**[DECISION — validated with one correction]** The governing task's hypothesized five-way split is upheld, with the Supervisor/C-MoE boundary tightened based on a **[FACT]** direct code finding this study made that RS/CS/WE did not have (their timestamps predate the relevant merge):

```
Watchdog         = "Are we making progress / violating execution budget?"          (existing, K4.4)
WorkflowRuntime  = "Can this operation execute safely, mechanically?"              (existing)
Supervisor       = "What CLASS of recovery is needed (retry/reroute/escalate)?"    (existing, worker-level)
C-MoE            = "What COGNITIVE action should happen next, given the goal?"     (new, K4.3)
Governance       = "Is that action allowed?"                                       (existing)
```

**[FACT]** The correction: `KNOWN_ISSUES.md` DEBT-016 (logged the same day as the watchdog merge, §83) documents that **two independent `ExecutionWatchdog`/`ProgressMonitor` implementations still coexist** (`core/runtime/watchdog.py`+`progress.py`, graph-aware, vs. `core/runtime/execution_watchdog.py`+`progress_monitor.py`, standalone for `model_router`) — the commit RS/CS/WE all point to as "the fix" (`7ca7f35`) made the two implementations *internally consistent with each other*, but did not *unify* them, and DEBT-016's own text warns "will drift again." **[DECISION]** This is a pre-K4.3 blocker, not a K4.3 design question: C-MoE cannot cleanly consume "watchdog signal" as a single input if two watchdog implementations can independently and divergently decide a work unit has stalled. Resolving DEBT-016 (unifying to one implementation) is added to this study's proposed implementation sequence (§96) as a Packet-0 prerequisite, ahead of any C-MoE code.

---

# 34. Watchdog Boundary

**[DECISION]** Confirmed and sharpened: Watchdog answers a **binary, mechanical** question (progress/no-progress, budget ok/violated) using **[FACT]** metrics that already exist (`ExecutionBudget`, `ProgressMonitor` — confirmed present in `KNOWN_ISSUES.md`'s DEBT-015/016 entries and WE's own audit). It does not, and must not, decide *why* progress stalled or *what to do about it* — those are C-MoE questions (§33). **[INFER]** The governing task's stated origin story for the watchdog (fixed timeouts incorrectly killing legitimate long-running LLM work) is itself evidence for keeping this boundary strict: the fix that resolved that problem was making the *progress signal* smarter (tracking actual token/step progress instead of wall-clock time), not making the *watchdog* cognitively smarter. Generalizing that lesson: any temptation to have Watchdog make a routing-flavored decision ("this expert seems slow, try a different one") should be resisted — that is a C-MoE decision consuming a Watchdog *signal*, never a Watchdog decision.

---

# 35. User Control Operations

**[DECISION]** A closed vocabulary of task-control intents, resolved by K4.2's existing intent-classification layer (not re-implemented in C-MoE), each mapped to a specific, existing-or-proposed mechanism:

| Intent | Mechanism |
|---|---|
| stop / cancel | WorkGraph node(s) → `CANCELLED` (§31), budget released (§40) |
| pause / resume | `SUSPENDED` state (§31); resume re-enters at `READY`, not `NEW` — no re-execution of completed work |
| change | User task mutation (§10) |
| undo / rollback | Branch/rollback (§15) |
| branch / compare / merge | §15 |
| "ignore the previous instruction" | Treated as a **correction** (§10), not a mutation — everything derived from the ignored instruction is `INVALID`, not `STALE` |
| "do both" | Parallel+aggregate composition trigger (§27) at the goal level, not merely the expert level |
| "start over" | Explicit, user-authorized exception to Goal Preservation (§7) — the one case where a new `goal_id` (not just a new version) is created deliberately |

---

# 36. Cancellation / Supersession

**[DECISION]** Every WorkGraph node and every `PlanRealityFeedback` (§8) carries the `plan_version` it was produced under. **[INFER]** A late-arriving result is accepted only if its `plan_version` matches the *current* plan version at the moment it arrives — this is a single integer comparison, not a distributed-systems protocol, precisely because task execution is single-node in the MVP scope (§93; distributed multi-node C-MoE is explicitly deferred, §95). **[DECISION]** A stale-version result is not silently dropped — it is logged as a `late_stale_result` event (feeding the contamination metric, §90) and, if its content still carries information-gain value (§29) for the *current* plan, may be offered to Planner as evidence, but never accepted as an execution outcome against a superseded plan.

---

# 37. Durability / Replay / Idempotency

**[STUDY][FACT]** This is RS's and WE's home territory, and this study defers to their mechanical conclusions almost entirely rather than re-deriving them, with one status update: **DEBT-003 ("Checkpoint/resume not implemented") is confirmed still open** as of this session's fresh `KNOWN_ISSUES.md` read — the K4.4 watchdog merge did not close it, and nothing in the same-day G1–G7 upload touches it either. **[DECISION]** OCBrain's realistic durability guarantee for K4.3, stated precisely rather than aspirationally: **effectively-once, through idempotency keys, not exactly-once.** WE's own recommended mechanism — a stable `operation_id` generated once per user intent (distinct from `trace_id`, which regenerates per HTTP request today) — is adopted as-is (§39). **[EXT]** This mirrors, almost field-for-field, the pattern independently converged on by Temporal (workflow ID as a dedup key; activities retry individually) and Restate (idempotency key rejecting events from a superseded attempt) — cited in WE and independently confirmed current during this study's fresh research pass. **[DECISION]** Checkpointing (closing DEBT-003) is a **hard prerequisite** for any C-MoE claim of "resumable long-running execution," and is sequenced ahead of C-MoE routing logic in the implementation plan (§96), not alongside it — routing is meaningless to resume correctly if the graph it was routing over cannot itself be reconstructed after a crash.

---

# 38. Event Causality

**[DECISION]** Every C-MoE-emitted event carries: `event_id, parent_event_id, task_id, execution_id, attempt_id, plan_version, work_graph_version`. **[FACT]** `caused_by` (§8) is the existing precedent for `parent_event_id` at the plan layer; this generalizes it to every event C-MoE emits, not only replan-triggering ones. **[INFER]** This is not a new causality *model* — OCBrain's event-sourcing law (Kernel Law 2) already requires every meaningful action to be an event; this section's contribution is specifically the *fields* needed to reconstruct a decision chain across the goal-evolution and task-mutation paths this study adds (§9), which plain timestamp ordering cannot do once concurrent tasks (§40) are in play.

---

# 39. Execution Identity

**[STUDY]** RS already did the hard thinking here via its **Scope** concept (a Kernel-owned execution-isolation Resource, deliberately distinct from "conversation," which the Kernel Constitution's Non-Goals explicitly excludes as a primitive — **[FACT]**, re-confirmed this session: *"the kernel has no concept of 'conversation' as a primitive, only Intent and Resources"*, Part VI). **[DECISION]** This study adopts RS's Scope/Mission framing and layers the governing task's requested identity fields onto it without inventing a competing concept:

```
user_id → project_id → discussion_id → task_id → execution_id → attempt_id
                                          ↑
                                   maps 1:1 onto RS's "Scope" Resource
```

**[DECISION]** `operation_id` (§37, WE's proposal) is generated once per **task_id**, not per attempt or per HTTP request — this is the field that makes idempotency actually work across retries, and it is the single most concrete, already-researched, ready-to-implement piece of this entire identity model.

---

# 40. Task Isolation

**[DECISION]** Hard invariant, enforced structurally rather than by convention: a WorkGraph, its checkpoints, its `PlanRealityFeedback` history, and its cognitive-budget accounting are all keyed by `task_id` (§39) and **[FACT, Constitution-grounded]** nothing in the Kernel's own data model provides an implicit cross-task read path — Resources are the only state the kernel holds (Part II), and Resources are scoped by identity, not globally enumerable by default. **[INFER]** This means task isolation in K4.3 is largely a *default*, not a *feature that must be built*: the risk is not "the kernel leaks task state," it is "a convenience shortcut in C-MoE's own implementation queries across `task_id`s without an explicit, governed reason to" (§101's "isolation by default, explicit reuse by design" principle, foreshadowed here).

---

# 41. Concurrency

**[DECISION]** Multiple simultaneous tasks (`Task A running, Task B running, Task C paused`) are supported by construction once §39–40 hold, because nothing in the per-task WorkGraph/state-machine/budget model requires global mutual exclusion — each task's C-MoE reasoning operates entirely within its own `task_id` scope. **[DECISION]** The one genuinely shared-state concern is **routing signal aggregation** (§21's historical-success-rate style signals) — if Task A's outcome updates an expert's `reliability_history` (§17) while Task B is mid-routing-decision for the same expert, that update must be atomic and must not block Task B's read. **[INFER]** This is a standard read-mostly, append-only statistics update pattern (similar to `model_router.py`'s existing query-count/maturity tracking, §60), not a novel concurrency problem — reusing that existing mechanism for expert-level statistics, rather than designing a new one, is the recommended approach.

---

# 42. Shared Resource Semantics

**[DECISION]** Three explicit categories, because collapsing them is precisely how "shared infrastructure implies shared task context" mistakes happen:

```
shared stateless resource   — a model endpoint, a tool adapter: safe to share, carries no task memory
task-local state             — WorkGraph, feedback history, checkpoints: never shared, ever
global resource statistics   — reliability_history, maturity_stage: shared, but append-only and task-attributed (§41), never mutated to reflect one task's private context
```

---

# 43. Resource / Cognitive Budget

**[DECISION]** Cognitive budget is tracked **separately** from execution budget (existing `ExecutionBudget`, K4.4), because a routing decision that costs nothing in execution time can still be expensive in LLM-router calls, replans, or context-construction tokens — conflating the two would let a task exhaust its *execution* budget while its *routing overhead* silently dominates actual cost, which the governing task explicitly flags as a risk ("C-MoE must not accidentally spend more resources deciding what to do than executing the task"). Proposed controls, each a hard ceiling checked by GovernanceKernel before the next routing step, not a soft target:

```
max_routing_steps_per_task        max_expert_fanout_per_step
max_replans_per_task              max_verification_calls_per_task
max_routing_context_tokens        max_cognitive_latency_per_decision
```

**[DECISION]** Budget hierarchy (task → project → user → system) is named but only the **task** level ships in the MVP (§93) — project/user/system-level budget pooling requires the memory-scope architecture (§45) to exist first, since "project budget" presupposes a Project is a real, addressable scope, which it is not yet (§44).

---

# 44. Projects and Discussions

**[DECISION — the central new contribution of this study]** Neither RS, CS, nor any existing architecture document models Projects/Discussions, because neither was asked to — this is genuinely new ground, and it is the section where getting the Kernel Constitution boundary right matters most. **[FACT, Constitution-grounded]** Part VI is unambiguous: *"the kernel has no concept of 'conversation' as a primitive"*; Part VII places "an assistant," "a research tool," and by direct extension "a discussion" or "a project," at the **Application/Workflow layer**, explicitly *"built on OCBrain, never as OCBrain."*

**[DECISION]** Therefore: **Project and Discussion are Application-layer groupings over a Kernel-primitive Resource, not new Kernel Laws, Invariants, or primitives.** The Kernel primitive underneath both is RS's **Scope** (§39). A Discussion *is* one Scope (one `task_id` lineage). A Project *is* a named, persistent grouping of Scopes that share a `project_id`, plus one additional Kernel-visible thing a bare Discussion does not have: a **Project Memory** resource (§45) that member Scopes may read from and, subject to promotion rules (§47), write to.

```
OCBrain Kernel (unaware of "project" or "discussion" as concepts)
   owns: Resources, Scopes, Events, Capabilities
        │
Application Layer (Kernel Constitution Part VII — this is where these concepts live)
   │
   ├── Normal Discussion  = one Scope, task-isolated (§40), no project_id
   │
   └── Project
         ├── Project Memory (a Resource, §45)
         └── Discussion A, B, C  = Scopes sharing project_id, each still task-isolated (§40)
```

**[INFER]** This resolves what would otherwise be a direct Kernel Constitution violation: implementing "Project" as a new Kernel-level primitive (a new Law, a new Resource *type* with special kernel-native sharing rules) would fail Gate 1 of the Kernel Admission Test (Part V) — it is not "genuinely about coordination, governance, resource lifecycle, event routing, or intent validation," it is a product/UX concept riding on top of those. Modeling it as an ordinary Resource (Project Memory) that ordinary governed read/write rules already cover is what lets it pass the Admission Test cleanly.

---

# 45. Memory Scope Model

**[DECISION]** Four scopes, validated against the governing task's proposal, with one important reconciliation this study makes explicit: **this axis is orthogonal to, not a replacement for, OCBrain's existing L0–L4 memory-*type* hierarchy** (Working/Episodic/Semantic/Procedural/Archive, `PROJECT_INSTRUCTIONS.md` §8). L0–L4 answers "what *kind* of memory is this" (a fact, an episode, a procedure); the scope model below answers "*who* can see this memory." A single Episodic memory can live at Discussion scope, Project scope, or Global scope — the two axes multiply, they do not compete:

```
                    L0 Working   L1 Episodic   L2 Semantic   L3 Procedural   L4 Archive
Discussion scope         ✓            ✓             –              –             –
Project scope            –            ✓             ✓              ✓             –
Global User scope        –            –             ✓              ✓             ✓
Reusable Evidence        –            ✓             ✓              –             –
```

**[DECISION]** Contents per scope, adopted from the governing task with no material change (it is already well-reasoned and this study found no gap):

- **Global User Memory** — explicit preferences, stable facts, communication style, approved conventions, recurring workflows, user-level constraints, the User Cognitive Model (§71).
- **Project Memory** — requirements, architecture decisions, artifacts, verified facts, dependencies, conventions, known issues, project constraints, promoted discussion conclusions.
- **Discussion/Task State** — current goal, plan, WorkGraph, temporary assumptions, intermediate results, checkpoints, pending operations — this is exactly the task-local state of §40, restated in memory-scope vocabulary.
- **Reusable Knowledge/Evidence** — verified documents, verified findings, tested API contracts, benchmark results, validated artifacts — originates in one task, promotable (§47) for use anywhere, subject to verification/provenance requirements.

---

# 46. Memory != Task State

**[DECISION]** Enforced by construction, not by convention, using the object-type distinction from §55: an `Event` ("Expert A failed") is never itself a Memory write. A Memory write requires an explicit promotion step (§47) that transforms an Event or a Decision into Knowledge with its own provenance record. **[INFER]** The governing task's own example is the cleanest test: "Expert A failed" is an event; "Expert A is unreliable for task type X" is a *derived belief* that requires aggregating multiple such events with a confidence-worthy sample size before it is fit to become Knowledge (§60's reliability history is exactly this aggregation, already scoped correctly — it lives at the expert-statistics layer, not as a promoted memory).

---

# 47. Controlled Result Promotion

**[DECISION]** A single promotion pipeline, not scope-specific ad hoc rules, because a uniform pipeline is what makes promotion auditable (Kernel Law 6):

```
Result → classify (provenance, confidence, verification status) → propose scope
       → REQUIRE: verification OR explicit user approval, whichever the target scope demands (below)
       → write, with full provenance record (§56)
```

**[DECISION]** Approval requirements by target scope, strictest at the top because blast radius increases with scope:

| Target scope | Requires |
|---|---|
| Temporary (stays in Discussion) | Nothing — this is just normal task state, no promotion needed |
| Task-reusable (same Discussion, later use) | Nothing extra |
| Project Memory | Provenance + a confidence floor; **no user approval required** for low-sensitivity technical facts (e.g., "project uses PostgreSQL"), **explicit approval required** for anything classified sensitive (§56) |
| Global User Memory | **Always** explicit user approval or an unambiguous, repeated, high-confidence observation pattern (§71) — never a single inference from one task |
| Cross-project | **Always** explicit user action (§57) — no automatic path exists |

**[INFER]** "The system should not automatically turn every generated statement into durable truth" (governing task's own framing) is enforced exactly by making the *default* action "stays temporary" and every wider scope an opt-in step with its own bar, rather than making promotion the default and exclusion the exception.

---

# 48. Memory Write Authority

**[DECISION]** C-MoE and Planner may **propose** promotions; only GovernanceKernel may **authorize** a write to Project or Global scope, per Kernel Law 1 (Bounded Autonomy) applied literally — "propose" and "authorize" are different verbs on purpose, mirroring §6's routing-decision table. Discussion-scope (task-local) writes require no such authorization, matching the low blast radius already established in §47's table.

---

# 49. Memory Read Authority

**[DECISION]** Read access is enforced *before* context assembly, not filtered after retrieval — i.e., a Discussion in Project A is never handed a raw query interface into Project B's memory that happens to return nothing; it has no interface to Project B's memory at all, by scope construction (§44). **[INFER]** This "deny by construction rather than filter by policy" approach is directly preferable per Kernel Law 2 (Explicit State): a system that *could* query anything but is filtered has a harder-to-audit failure surface than a system that structurally cannot query outside its authorized scope set.

---

# 50. Contradiction / Supersession

**[DECISION]** Adopted verbatim from the governing task, because CS already validated an identical vocabulary for plan/goal versioning (§9, §11) and reusing it for memory keeps the whole document internally consistent rather than introducing a second status vocabulary:

```
active · superseded · invalidated · provisional · verified · unverified
supersedes · replaces · invalidates · depends_on · derived_from · verified_by
```

**[DECISION]** When a Project-scope decision is superseded, dependent Project-memory entries are re-evaluated using the *exact same* dependency-propagation mechanism as WorkGraph invalidation (§13) — `depends_on` edges over memory entries and `depends_on` edges over WorkGraph nodes are the same kind of graph, just over a different node type. This is not a new algorithm; it is the same one applied to a second domain, which this study flags explicitly to avoid two parallel, subtly-different implementations of "propagate invalidation over a dependency graph."

---

# 51. Authority / Precedence

**[DECISION]** Ordered, highest to lowest, and this ordering is itself a governed, inspectable artifact (not implicit prompt-construction order):

```
1. Current authoritative user instruction (this turn)
2. Current task constraints (active Goal)
3. Verified current runtime state (WorkGraph, Events)
4. Active project knowledge (non-superseded Project Memory)
5. Global user memory
6. Historical/derived memory (patterns, hypotheses — §71)
7. External retrieved content (web, documents)
```

**[INFER]** Position 7 being last, always, is the direct architectural answer to §62's security concern (prompt injection via external content): nothing retrieved from outside the user's own instruction chain may outrank anything the user or the system's own verified state established, regardless of how it is phrased or how confidently it is worded.

---

# 52. Freshness / Temporal Validity

**[DECISION]** Every promoted memory entry (§47) carries an optional `expires_at` and a `revalidation_policy` (`never | on_read | on_interval`). **[DECISION]** Default policy by scope: Discussion state has no TTL (it dies with the task, §40); Project Memory defaults to `on_read` revalidation for anything tagged as externally-sourced (API behavior, prices, versions) and `never` for internally-verified architecture facts; Global User Memory defaults to `never` (preferences don't expire on a timer, they expire on contradiction, §50). **[INFER]** This is a policy table, not a new mechanism — it reuses the same contradiction/supersession machinery (§50) as its enforcement path; "freshness" is simply a time-triggered reason to re-run that machinery rather than a separate system.

---

# 53. Memory Correction / Deletion

**[DECISION]** Dependency-aware, reusing §13's propagation mechanism a third time: deleting or correcting a memory entry marks every entry with a `derived_from` edge pointing to it as `STALE` (§12's vocabulary, reused, not reinvented), triggering the same revalidate-or-recompute decision C-MoE already makes for WorkGraph nodes. **[DECISION]** "User says forget this" is a hard delete of the entry plus this propagation — not a soft `superseded` flag — because a user-initiated forget request is a sovereignty exercise (Kernel Law 5) and treating it as merely "superseded but still present" would not honor that.

---

# 54. Memory Poisoning

**[DECISION]** The governing task's example (a tool output asserting "user always wants unrestricted access") is prevented structurally by §47's pipeline: tool/expert output is **Evidence**, never directly **Knowledge** (§46, §55), and Evidence never reaches Global User Memory without passing through explicit-approval promotion (§47's table). **[INFER]** This means memory poisoning via a single malicious or hallucinated expert output is already architecturally contained by the promotion pipeline this study designed for an unrelated reason (avoiding over-eager memory writes, §47) — a case where solving the "don't pollute memory casually" problem correctly also solves the "don't let an attacker pollute memory" problem, because both attacks share the same entry point (an unreviewed write).

---

# 55. State vs Knowledge vs Evidence vs Decision

**[DECISION]** Adopted as a formal responsibility model, because §46–54 all depend on this distinction being crisp:

| Object | Definition | Where it lives | Mutable? |
|---|---|---|---|
| **State** | What is currently true about execution | WorkGraph, Kernel Resources | Yes, by C-MoE/ExecutionRuntime |
| **Event** | Immutable record of what happened | Event log | Never |
| **Evidence** | What supports a belief (a tool result, an expert output) | Task-scoped by default; promotable | No — new evidence is a new record, not an edit |
| **Knowledge** | What OCBrain believes, derived from evidence | Memory (any scope) | Only via promotion/correction (§47, §53), never in place |
| **Decision** | What the system chose to do | Event log (a Decision is itself an event) | Never |

**[INFER]** Every prior section's boundary decisions (§46, §54) are direct consequences of this table, not independent rules — this table is this study's answer to the governing task's demand for "a responsibility model," and everything above it in this document is that model applied to a specific question.

---

# 56. Cross-Project Boundaries

**[DECISION]** Denial is the default and the only path across a project boundary is explicit user action promoting a specific Reusable Evidence item (§45's fourth scope) — there is no "Project A's memory, visible to Project B" mode, ever. **[INFER]** This is stricter than the governing task's own phrasing ("never assume cross-project reuse is inherently permitted") — this study goes further and states that cross-project reuse is **never** automatic under any confidence or verification level, because Project Memory (unlike Reusable Evidence) is allowed to contain project-specific sensitive detail (credentials-adjacent config, internal architecture, client-specific requirements) that has no general-purpose sanitized form, so there is no safe automatic promotion path from Project Memory directly to another Project — only the explicit, user-mediated Reusable Evidence path.

---

# 57. Cross-Task Result Sharing

**[DECISION]** Formalized exactly as the governing task specifies: Task B receives `X + provenance + validity + verification_status + origin_task/project`, never Task A's execution state. **[FACT]** This is directly implementable using the artifact-lineage fields already proposed in §58 plus the promotion pipeline of §47 — no new mechanism is needed beyond composing the two.

---

# 58. Artifact Lineage

**[DECISION]** Every artifact (code, document, report, dataset, generated output) carries:

```python
@dataclass
class ArtifactProvenance:
    artifact_id: str
    produced_by_task: str
    produced_by_node: str          # WorkGraph node ID
    produced_by_expert: str
    derived_from: List[str]        # other artifact_ids
    verified_by: Optional[str]     # verification event, once §77 exists
    superseded_by: Optional[str]
    used_by: List[str]             # tasks that consumed this artifact (populated on read, §57)
    environment: EnvironmentSnapshot  # library versions etc., §59
```

**[INFER]** This is the same `Event`/`Decision`-traceable pattern established in §38 (Event Causality) applied to a longer-lived object; it deliberately reuses field-naming conventions (`produced_by`, `derived_from`) already present on `ExecutionPlan` itself (§4), so an engineer already familiar with `ExecutionPlan`'s provenance fields does not need to learn a second vocabulary for artifacts.

---

# 59. Artifact Version / Compatibility

**[DECISION]** `ArtifactProvenance.environment` (§58) captures the minimum needed to detect the governing task's exact example (an artifact produced under library v1 must not be silently treated as valid under v2): declared dependency versions at production time. **[DECISION]** Compatibility checking itself is **not** a K4.3 mechanism — K4.3's job is to make the *staleness detectable* (the data exists to check), not to *automate the check* (that requires per-artifact-type compatibility logic — a code artifact's compatibility check is nothing like a research-finding's). This is deliberately left as a Verification-boundary concern (§77): C-MoE can request "verify this artifact is still compatible," it does not implement compatibility rules itself.

---

# 60. Partial Reuse

**[DECISION]** Directly satisfied by §12's five-state classification already being per-node rather than per-task: "10 facts, 7 valid, 3 stale" is not a special case requiring new machinery, it is the ordinary output of running §12's classification independently over ten WorkGraph or memory-evidence nodes. **[INFER]** This section exists in the governing task primarily to confirm that §12 was designed granularly enough — it was, so no new mechanism is proposed here; this is a validation, not a gap.

---

# 61. Expert Lifecycle

**[DECISION — reusing model_router.py wholesale]** **[FACT, re-verified this session]** `core/model_router.py` already implements exactly this lifecycle for models, with concrete, code-confirmed thresholds: `SHADOW_PROMOTE_MIN_QUERIES = 500`, `SHADOW_PROMOTE_THRESHOLD = 0.85` (maturity score), gating a `bootstrap → shadow → native` promotion that only fires once *both* conditions hold — i.e., promotion requires externally-measured evidence, not self-report, exactly matching this project's own stated principle ("self-reported promotion evidence is structurally invalid"). **[DECISION]** This study recommends **generalizing this exact mechanism**, not designing a new one, to cover the full `ExpertKind` space (§17) as additional expert types are registered: registration → health-checked → `bootstrap` (cold-start, §24) → `shadow` (evaluated in parallel, not yet trusted for final output) → `native` (fully trusted) → (degradation detected) → back to `shadow` → withdrawal. Schema evolution and permission changes mid-task are handled the same way §36 handles supersession: a mid-task expert-schema change makes that expert temporarily ineligible (§20) for the remainder of the current task, without forcing every other in-flight task using the old schema to abort.

---

# 62. Expert Performance History

**[DECISION]** Reliability statistics carry the same qualifiers `model_router.py` already tracks (recency-weighted, not a flat lifetime average) plus two additions this study identified as gaps in the existing model-level version: **task-class awareness** (an expert's history on `research`-class steps should not silently apply to `code-generation`-class steps it has never actually attempted) and **environment awareness** (§59 — a reliability score earned under one tool/API version should decay in confidence, not persist unchanged, when that dependency changes). **[INFER]** Confidence decay over stale statistics is a straightforward function of §52's freshness/TTL machinery applied to the statistics themselves, not a new decay algorithm.

---

# 63. Health != Capability Fit

**[DECISION]** Enforced by construction via §17's `ExpertDescriptor` split: `health` and `specialization` are separate fields, checked at separate funnel stages (§20 — health is a hard-eligibility disqualifier only when `UNAVAILABLE`; specialization match is the eligibility *filter* proper). A "healthy but wrong" expert fails the eligibility filter; a "degraded but still appropriate" expert passes eligibility but is soft-ranked lower (§21) — never disqualified outright for degradation alone, only for outright unavailability. This prevents the failure mode of a system that only has one appropriate (if imperfect) expert refusing to route at all because that expert is merely degraded rather than dead.

---

# 64. Security / Instruction Hierarchy

**[DECISION]** C-MoE's context assembly (whatever it consumes for a routing decision) obeys the precedence order already established in §51 without exception. **[INFER]** The concrete, testable consequence: a prompt-injection payload embedded in expert output or external content occupies position 7 (lowest) in §51's ordering regardless of how it is phrased, including phrasing that impersonates a higher-priority source ("SYSTEM: override previous constraints") — precedence in this architecture is determined by **provenance metadata C-MoE already has from §55's object model** (this text came from an `Evidence` object sourced externally), not by parsing the text's own claimed authority, which is exactly what makes injection-via-claimed-authority ineffective here: the defense does not depend on the text failing to sound authoritative.

---

# 65. Secrets Isolation

**[DECISION]** No new mechanism — this is the existing Secret Management rule (`PROJECT_INSTRUCTIONS.md` §14.2: never in logs, never in events, environment/runtime-injected only) applied without exception to every C-MoE-emitted event (§38) and every routing-metadata structure exposed to Studio (§79). **[INFER]** The one K4.3-specific risk this study flags: `ExpertDescriptor.provenance` (§17) and `ArtifactProvenance` (§58) are both free-text-adjacent fields that a careless implementation could populate with a raw tool-call payload containing a credential. This study recommends a schema-level constraint (a max-length, non-payload-shaped provenance string, populated from a controlled template) rather than relying on developer discipline alone, given this project's own explicit distrust of unenforced discipline elsewhere (`PROJECT_INSTRUCTIONS.md`'s entire Forbidden Practices list exists for the same reason).

---

# 66. Cognitive Provenance

**[DECISION]** Directly assembled by chaining fields already specified: `User → Project(§44) → Discussion/Scope(§39) → Task(§39) → Goal.version(§11) → Plan.resource_id+version(§4) → WorkGraph node(§16) → Expert(§17) → Evidence(§55) → Outcome(§30) → [Verification, §77 stub] → Decision(§55) → Reusable Knowledge(§45, if promoted)`. **[INFER]** No new field is required anywhere in this chain that a prior section did not already introduce for an independent reason — this section's role in the document is to confirm the chain is actually unbroken end-to-end, which it is, and to note explicitly that this reconstructability is what satisfies Kernel Law 6 (Explainability) for C-MoE specifically, not merely for the Kernel in the abstract.

---

# 67. Context Compiler Boundary

**[FACT]** Neither "Context Compiler" nor "Context Engineering" appears anywhere in this repository's documents or code today — this is genuinely undefined territory, not a rediscovery. **[DECISION]** The interface this study proposes, deliberately minimal since the milestone itself does not yet exist: C-MoE **requests** context (a bounded query: "evidence relevant to this WorkGraph node, this expert's context_requirements, this memory-scope set") and receives an assembled, size-bounded context object; C-MoE does **not** itself retrieve memory, compress history, or rank evidence relevance — those verbs belong to whatever eventually implements Context Compiler. **[INFER]** Until that milestone exists, this interface is satisfied by a thin pass-through (current memory-retrieval code, called directly), which is acceptable *only* because the interface boundary — not the implementation quality behind it — is what this study is responsible for fixing in place now, so that Context Compiler can later replace the pass-through without C-MoE's call site changing.

---

# 68. Evaluation & Reliability Boundary

**[FACT]** Also genuinely undefined in this repository today — no "Evaluation & Reliability Lab" exists. **[DECISION]** C-MoE's obligation is limited to **emitting** the structured events and outcomes (§30, §84) a future Evaluation & Reliability Lab would need to compute metrics like this study's own §88–90 — C-MoE does not compute regression detection, aggregate reliability scores, or benchmark results itself. **[INFER]** This is the same "emit, don't own" pattern as §67; the two boundaries are structurally identical (a future milestone consumes C-MoE's event stream) and this study treats them as one design pattern applied twice, not two separate integration problems.

---

# 69. Verification Boundary

**[DECISION]** C-MoE can **request** verification (a `VERIFYING` state transition, §31, and a `verification_status` field on outcomes, §22/§30) without implementing verification logic itself. Until a real Verification Runtime exists, "verification" resolves to one of two stubs: an explicit user confirmation, or a cheap, narrowly-scoped C-MoE-internal check (e.g., "does this artifact parse / does this file exist") that is explicitly logged as `verification_status: STUB_CHECK_ONLY`, never conflated with genuine Verification. **[INFER]** This distinction matters directly for §32's Goal Satisfaction Contract: a stub check is never sufficient grounds for full `COMPLETED` status at the goal layer, only for `COMPLETED_WITH_WARNINGS` — reusing that section's cap rather than introducing a separate rule.

---

# 70. Reflection Boundary

**[DECISION]** Out of scope, with one explicit exception already covered: expert disagreement resolution (§28) may escalate to a verifier composition (§27), which is Verification-adjacent, not Reflection. True Reflection (retrospective critique across multiple past trajectories, not a single current outcome) requires historical trajectory storage this study does not propose building. **[DECISION]** The interface reserved for the future: Reflection, once it exists, reads the same Event/Decision log (§38, §55) C-MoE already produces — no new export mechanism is needed, only a consumer.

---

# 71. Adaptive Learning Boundary

**[DECISION]** The line drawn precisely, because this is the boundary the governing task worries about most explicitly (§25, §70 in the earlier draft's numbering; this study treats it as one coherent boundary): **routing using existing evidence** (§17's `reliability_history`, §61's expert lifecycle, all of which are already-measured, externally-verified statistics) is in scope for K4.3. **Learning new routing behavior** — updating routing *weights* (§19's Policy) from outcomes via any optimization process, bandit algorithm, or fine-tuning — is out of scope. **[INFER]** The `model_router.py` precedent (§61) is instructive here specifically because it already draws this exact line correctly in production: its maturity thresholds are fixed constants an engineer set, not learned parameters, even though the *inputs* to the promotion decision (query count, measured maturity) are dynamically observed. K4.3's routing policy should follow the identical pattern — dynamically-observed inputs, statically-set policy — until Adaptive Learning is a real, separately-scoped milestone.

---

# 72. Capability / Skill Evolution Boundary

**[STUDY]** Prior OCBrain capability-architecture research (the ~90-repository sweep, `OCBRAIN_EXTERNAL_REPO_STUDY.md` V1–V3, and the large-scale capability architecture research brief already committed to `docs/archive/research/`) already answered the mechanism half of this question — `.procedural`/`.executable` skill subtypes, `SKILL.md` spec adoption, `ai-capability-registry`'s allow/deny/require `policies.yaml` schema as directly reusable. **[DECISION]** This study's only addition is the trigger condition: C-MoE emits `NeedCapability` (§30) when no eligible expert exists (§20 finds an empty candidate set after eligibility filtering) — this event is C-MoE's entire interface to capability evolution. What happens after that event (fail, ask user, discover a resource, construct a skill) is **not** K4.3's decision; K4.3 only needs to emit the event with enough structure (the unsatisfied `capability_type`, the step's contract requirements) for a future capability-acquisition subsystem to act on it. **[DECISION]** For K4.3 itself, `NeedCapability` with no downstream acquisition subsystem resolves to `abstain` + escalate to user (§23, §82) — a safe, honest default that does not pretend to solve a problem this milestone does not own.

---

# 73. User Cognitive Model

**[FACT]** This is not greenfield — `core/cognitive/user_model.py` already exists (K4.2.7, confirmed via memory of prior sessions and consistent with the very-recent G4 fix in §83, which wired `assemble_user_cognitive_model()`'s output into `PlannerHint`s for the first time). **[DECISION]** This study recommends **no new user-model mechanism** — the existing K4.2.7 component, now actually reachable from the orchestrator as of the G4 fix, already provides what C-MoE needs (user-level routing hints, e.g. a stated tool preference). **[DECISION]** The one addition K4.3 requires: the existing model's outputs must be labeled with the confidence tier the governing task specifies (`explicit | observed | derived | hypothesized | approved`), if they are not already — this study did not have direct sight of `user_model.py`'s current output schema and flags this as an **open question requiring direct verification** (§99) before implementation, rather than asserting a fact this session did not confirm.

---

# 74. Proactive Optimization / Fable Direction

**[DECISION]** Not implemented in K4.3, exactly per the governing task's own caution — but this study can now be specific about *why* the prerequisites are not yet satisfied, rather than deferring generically: proactive optimization requires (a) cross-task pattern detection, which requires (b) Global User Memory actually accumulating recurring-workflow observations, which requires (c) the promotion pipeline (§47) to be live and used, which requires (d) K4.3 shipping at all. **[DECISION]** The concrete architectural prerequisite this study adds to the roadmap: every promoted Global User Memory entry (§47) should be tagged with a `workflow_signature` (a coarse hash of the step/capability-type sequence that produced it) from day one, even though nothing consumes that tag until a future Opportunity Detector exists — this is the one piece of forward-compatible schema this study recommends adding now, because retrofitting it onto already-promoted memory later is materially harder than including it at promotion time. Everything else in the observation → hypothesis → candidate optimization → suggestion → approval pipeline is left as pure future work with no K4.3-side hook required.

---

# 75. Claude Opus Behavioral Target

**[DECISION]** Handled with the discipline the governing task demands: no claims about proprietary internals are made anywhere in this document. **[INFER]** The observable qualities named (decomposition, specialization, selective tool use, long-horizon coherence, iterative correction, verification, robust completion) map onto this study's own sections as follows, and *only* this mapping — not any claim about how a specific product achieves them — is asserted:

| Observable quality | OCBrain component responsible |
|---|---|
| Strong decomposition | Planner (K4.2, existing) |
| Effective specialization / selective tool use | C-MoE routing (§17–24) |
| Long-horizon coherence | Goal preservation + WorkGraph durability (§7, §37) |
| Iterative correction | Replanning loop (§8) + expert composition (§27) |
| Verification | Verification boundary (§69) — deferred, hooked not implemented |
| Robust completion | Goal Satisfaction Contract (§32) |
| Adaptive behavior | Outcome-driven routing (§30) using existing, not learned, signals (§71) |

No single component is credited with all of these; the governing task's own warning ("do not attribute everything to C-MoE") is satisfied by this table spreading responsibility across Planner, C-MoE, Memory, and the deferred Verification boundary rather than concentrating it in one place.

---

# 76. C-MoE vs Neural MoE

**[EXT]** Freshly researched this session. The analogy holds at the level of **shape**: a gating function selecting a sparse subset of a larger specialist pool, evaluated against real, current research spanning the foundational architecture (Jacobs et al., 1991, hierarchical mixture of local experts) through modern sparse LLM MoE (Shazeer et al., 2017, top-k sparse gating; Switch Transformer, Fedus et al. 2022, top-1; Mixtral, top-2-of-8; DeepSeekMoE's fine-grained-plus-shared-expert design) and alternate dispatch directions (Expert Choice Routing, Zhou et al., NeurIPS 2022 — experts select tokens rather than tokens selecting experts, guaranteeing load balance by construction).

**[INFER]** The analogy breaks at the level of **mechanism**, in three specific, load-bearing ways this study identifies rather than merely asserting:

1. **No gradient.** Neural MoE specialization emerges from backpropagation over millions of routing decisions; C-MoE's routing signals (§21) are hand-specified and threshold-gated (§61's `model_router.py` pattern), not learned end-to-end. Nothing in K4.3 trains a router.
2. **Load balancing is a non-goal.** Neural MoE load-balancing losses exist to keep GPU utilization even across experts of *equal* intended value; OCBrain's routing goal is correctness for a specific task, not throughput symmetry — an expert being selected 95% of the time because it is genuinely the right expert 95% of the time is a *success*, not an imbalance to correct. Importing a load-balancing auxiliary objective into C-MoE would actively fight its actual goal.
3. **Expert Choice Routing's "experts pick tasks" framing is a genuinely useful borrowable idea**, not merely a broken analogy: an `ExpertDescriptor` advertising eligibility/fit (§17's `specialization` field) *is* a form of expert-side declaration rather than pure central-router scoring, and this study's candidate-generation stage (§20) already leans this direction by filtering on declared specialization before any central ranking occurs.

---

# 77. Determinism

**[DECISION]** Every non-deterministic input to a routing decision — candidate ordering, tie-breaking, any LLM-participation in routing — is bounded exactly as the governing task demands: candidate ordering is sorted by a stable key (`expert_id`) before scoring, never by insertion or hash order; ties are broken by the same stable key, never by re-invoking a model; if an LLM ever participates in a routing decision (not required by the MVP, §93, but not architecturally forbidden for Full K4.3, §94), its output is treated as **one scored input among several**, never as the decision itself — the actual selection remains a deterministic function over that score plus every other signal, and the LLM's contribution is logged as structured metadata (a signal value, not a narrative) per §84. **[INFER]** This directly satisfies the governing task's sharpest warning on this topic: *"the router LLM decided" must never become the only explanation for a critical system action* — under this design it cannot, because the LLM's output is never itself the decision, only an input the deterministic mechanism (§19) scores like any other signal.

---

# 78. Governance

**[DECISION]** Every C-MoE authority listed in the governing task is a proposal, never a self-authorization, per Kernel Law 1: routing decisions, expert eligibility for permission-gated experts, memory access crossing scope (§49), task mutation acceptance (§10), result promotion (§47–48), capability acquisition triggers (§72), and any external side effect. **[FACT]** The existing `OrchestrationGovernor`/`MemoryGovernor`/`AgentGovernor`/`EvolutionGovernor` set (`PROJECT_INSTRUCTIONS.md` §6.1) is the enforcement point for all of these — K4.3 does not need a new Governor type, it needs each existing Governor to gain C-MoE-specific evaluation rules (e.g., `MemoryGovernor` gains a rule for §49's scope-crossing checks; `OrchestrationGovernor` gains recursion/fan-out limits for §43's cognitive budget). **[DECISION]** This is explicitly *not* a new sixth Governor — adding one without a Gate-1 justification (Kernel Admission Test, Part V) would fail the Constitution's own test, since every one of these checks already fits inside an existing Governor's stated responsibility.

---

# 79. Human Approval

**[DECISION]** Approval checkpoints, each mapped to an existing mechanism rather than a new UI concept: destructive side effects and expensive operations gate through `OrchestrationGovernor`'s existing approval-checkpoint mechanism (`PROJECT_INSTRUCTIONS.md` §6.1); capability acquisition (§72) and cross-project sharing (§56) always require explicit user action by this study's own design, not merely a governance gate; global-memory promotion (§47) requires approval except for the narrow high-confidence-repeated-observation exception already specified there; significant goal changes (a new `goal_id`, not merely a new version, §35's "start over") always require the explicit user trigger already established in §35; high-impact branch selection (§15, when branches diverge on something consequential) escalates through the same disagreement-resolution path as expert disagreement (§28), reusing that mechanism rather than inventing a parallel one.

---

# 80. Observability

**[DECISION]** For every routing decision, C-MoE emits one structured `routing.decision` event carrying: the work unit reference, the candidate set (by `expert_id`, not full descriptors — avoid event bloat), eligibility outcomes per candidate, routing signal values that fed the ranking, the selected expert(s), a **closed-vocabulary** selection-reason code (never free text — reusing §77's "LLM output is a signal, not a narrative" rule), the governance result, the execution outcome once known, the next decision taken, any WorkGraph changes, any replan trigger, any verification request, and final disposition. **[INFER]** No chain-of-thought is exposed at any point in this event — every field is either an ID, an enum, or a numeric score, which is both a privacy/IP boundary and, not incidentally, exactly what §77's determinism argument already required these fields to be.

---

# 81. OCBrain Studio Compatibility

**[FACT]** "OCBrain Studio" (called "Integration Studio" in `OCBRAIN_KERNEL_CONSTITUTION_RATIONALE.md`, explicitly marked as **not** constitutional — "pure tooling, has no principle-level content of its own") already has a live consumer relationship established: the very recent `EXECUTION_PROGRESS_INSPECTION_IMPLEMENTATION_REPORT.md` (part of the same watchdog-fix branch merge, §83) states directly that its SSE-streamed execution snapshots and ordered events exist partly so *"OCBrain Studio views [can consume] the same snapshots and ordered events."* **[DECISION]** K4.3 does not implement Studio, but §80's `routing.decision` event schema is designed to be a drop-in additional event type on that same already-existing SSE/snapshot stream — no new transport, no new consumer contract, just a new event shape flowing through infrastructure the watchdog work already built and is already labeled as Studio-facing.

---

# 82. External Research Findings

**[EXT]** Consolidated from this session's fresh academic sweep (all sources independently retrieved this session, not carried from any prior document):

| Topic | Finding | K4.3 relevance |
|---|---|---|
| ReAct (Yao et al., ICLR 2023, arXiv:2210.03629) | Interleaving reasoning traces with actions lets a model "induce, track, and update action plans... and handle exceptions" from environment feedback | Foundational precedent for the reasoning-observation-action loop C-MoE runs per work unit (§6); OCBrain's version is system-level (routing among distinct expert processes) rather than token-level, per §76 |
| Reflexion (Shinn et al., 2023) | A discrete post-generation Critic evaluates output against constraints and produces natural-language correction feedback | The pattern this study deliberately does **not** adopt wholesale for K4.3 (§27, §70) — full critic-correction loops are Reflection-boundary work, not C-MoE composition |
| AgentBench (Liu et al., 2024) | Multi-environment benchmark (8 environments) for agent decision-making; identifies poor long-term reasoning and instruction-following as primary obstacles to usable agents | Motivates this study's insistence on structured, typed outcomes (§30) over free-text agent narration as the mechanism for long-horizon reliability |
| τ-bench / τ²-bench (Yao et al. 2024; Barres et al. 2025) | τ-bench's `pass^k` metric measures reliability across repeated trials, not single-run success; τ²-bench extends to a **dual-control** setting (Dec-POMDP) where both agent and user can act on shared state | τ²-bench's dual-control framing is direct, independent validation that user task mutation mid-execution (§10) is a first-class, actively-researched problem, not an OCBrain-specific edge case |
| RouterEval (Huang et al., EMNLP Findings 2025, arXiv:2503.10657) | A capable router over a large candidate pool can exceed the best single candidate's performance — a "model-level scaling up" effect | Supports this study's emphasis on routing-mechanism quality (§19) as a first-order investment, not a secondary concern behind expert quality |
| Multi-agent failure taxonomy (Cemri et al., NeurIPS 2026, "Why do multi-agent LLM systems fail?") | Systematic failure categories exist across multi-agent systems generally | Cited as corroborating evidence for this study's own Failure Matrix (§88) being a necessary artifact, not cited for its specific category list, which this study did not verify in depth |
| AgentTether (arXiv:2607.06273, verified genuine via independent search) | "Blind retry adds no diagnosis; outcome feedback says whether a run failed" but not why — proposes graph-guided failure localization | Direct evidence against naive critic-correction loops (§27) and for this study's insistence that outcomes carry structured failure reasons (§30), not just success/fail |
| AgentRewind (Zhuang et al., arXiv:2608.14380, verified genuine) | Aligned checkpoints of agent context *and* environment state enable rewind-and-resume after unrecoverable early errors | Directly informs §37's durability stance — checkpointing must cover environment state, not just agent/plan state, a nuance this study's own §37 treatment inherits from this paper via WE |
| Plan-repair literature (local vs. global replan, "adaptive assignment of remedial steps" — Chen et al. 2025, Aghzal et al. 2026) | Established three-way taxonomy: local spot-correction, global full replan, remedial-step assignment | Directly adopted as the shape of §8's replan trigger — C-MoE's `NeedReplan` outcome should be able to request any of these three scopes, not always trigger a full replan |
| Neural MoE lineage (Jacobs 1991 → Shazeer 2017 → Switch/Mixtral/DeepSeekMoE → Expert Choice Routing, NeurIPS 2022) | See §76 in full | Grounds the C-MoE/neural-MoE analogy precisely, including where it breaks |

---

# 83. GitHub / Open-Source Findings

**[EXT]** Freshly researched this session, current as of August 2026:

| System | What it actually solves | OCBrain relevance |
|---|---|---|
| **LangGraph** | Explicitly positioned by its own docs (checked live, July 2026) as "the orchestration runtime: durable execution, streaming, human-in-the-loop, and persistence" — distinct from LangChain (agent abstractions) and LangSmith (tracing/eval). Ships its own "Studio" for visual workflow prototyping. | Closest existing analog to what K4.3 + the existing K4.4 watchdog baseline together aim at. Its explicit three-way split (framework / runtime / observability platform) independently validates this study's own insistence on keeping Planner, C-MoE, and Studio as separate concerns (§3–4, §81) rather than one monolith. |
| **Composio** (27k+ GitHub stars, 1,089 toolkits / 20,000+ tools via one MCP endpoint as of August 2026) | Solves **authenticated tool connectivity** — managed OAuth, credential lifecycle, per-connection permission scoping — for external services (Gmail, Slack, GitHub, etc.) | **Adjacent, not competing.** Composio-style connectivity is a plausible *source* feeding `CapabilityRegistry` (an adapter that happens to broker external auth), not a substitute for C-MoE's cognitive routing decision. This study recommends treating any future OCBrain external-tool integration as a Composio-style Adapter (Kernel Constitution Part VII) registered into the same `ExpertDescriptor` model (§17), not as a parallel routing system. |
| **AutoGen / CrewAI / LangGraph ecosystem positioning (2026 landscape)** | Multi-agent orchestration frameworks with different philosophies: AutoGen (conversation-driven), CrewAI (role-based teams), LangGraph (graph-based, durable) | Reinforces this study's choice (§16) of a graph-based (WorkGraph), not conversation-driven, model for C-MoE — the graph-based approach is the one the wider ecosystem has converged toward for exactly the durability/replayability reasons OCBrain's own Kernel Laws already require independently. |
| **Composio's own "State Management" framing** ("stateful architectures that allow an agent to pause, wait for human input for days, and resume exactly where it left off") | Names precisely the DEBT-003 gap this study inherited from RS (§37) as an industry-recognized, actively-solved-elsewhere problem, not a uniquely hard OCBrain problem | Reinforces urgency on closing DEBT-003 as a K4.3 prerequisite (§96), since the pattern for solving it is now well-established externally, not experimental |

**[DECISION]** Resource2Skill, Datalayer Agent Skills, and Open Agent Skills are **not** re-researched fresh in this session — per this study's own evidence-reuse discipline (§92), the prior large-scale capability-architecture research brief already committed to `docs/archive/research/` covers these in more depth than a fresh, shallow re-search would add, and §72 already states the only new thing K4.3 needs from that body of work (the `NeedCapability` trigger condition).

---

# 84. Previous OCBrain Study Reconciliation

**[STUDY]** Full reconciliation table against RS and CS, the two studies this document draws on most heavily:

| Prior conclusion | Source | This study's disposition |
|---|---|---|
| Watchdog / Supervisor / C-MoE authority split | CS, AED | **Upheld**, with one correction (§33 — DEBT-016's un-unified duplicate implementations) |
| Single-node Work Graph is the correct K4.3 MVP boundary; distributed graphs deferred | CS | **Upheld verbatim** (§93–94) |
| `model_router.py`'s maturity state machine as the reference pattern for capability/expert lifecycle | CS, and independently, this project's own stated principle | **Upheld and generalized** (§61) |
| Identity model: Scope as the Kernel-facing execution-isolation primitive, distinct from "conversation" | RS | **Upheld and extended** to explicitly host Project/Discussion at the Application layer (§39, §44 — RS did not have the Project/Discussion scope available to extend to, since it predates this task's memory-scope requirements) |
| DEBT-003 (checkpoint/resume) as the central durability gap | RS | **Upheld and re-confirmed still open** via a fresh `KNOWN_ISSUES.md` read this session (§37) |
| `operation_id` stable-per-intent, distinct from per-request `trace_id` | WE | **Upheld verbatim**, adopted into the identity model (§39) |
| `Operation` / `ExecutionAttempt` / `ExecutionSnapshot` / `RecoveryDecision` proposed schema | WE (DEBT-015, proposed not implemented) | **Upheld as the checkpointing schema K4.3's durability prerequisite (§37, §96) should implement**, not redesigned |
| Capability Outcome Contract placeholder (8 states) | AED | **Extended, not replaced** — four new states added with evidenced justification, four candidate additions explicitly rejected (§30) |

**[INFER]** No conclusion from RS or CS was overturned outright by this study. The one *correction* (DEBT-016, §33) is a fact that postdates both studies, not a disagreement with their reasoning — this is a case of the world (the codebase) moving after the research was written, not the research being wrong when it was written. This matters for how the reconciliation should be read: RS and CS remain good research; this study's job was to catch up to code that changed after them and to build the genuinely new sections (Projects/Discussions/Memory/Task-mutation) neither was scoped to cover.

---

# 85. Current Repository Audit

**[FACT]** Direct, this-session code and document verification, organized by the governing task's own audit categories:

| Item | Implemented? | Integrated? | Reachable? | Tested? | Canonical path? |
|---|---|---|---|---|---|
| `ExecutionPlan` / `PlanStep` | Yes | Yes | Yes (K4.2 now default, §83) | Yes | Yes |
| `ExecutionPlan.caused_by` (proto-Plan-Reality-Feedback) | Yes | Yes | Only via the K4.2-branch re-plan loop | Untested by dedicated test as of this session's audit — **flagged**, §98 | Partial |
| `ExecutionPlanLifecycle` (`compiled/executing/completed/failed/superseded`) | Enum exists | **No** — nothing drives these transitions | No | No | No — this is the exact gap C-MoE fills (§16) |
| `CapabilityExecutorWorker` (WorkflowNode→worker bridge) | Yes | Yes | Yes | Yes (per its own scope) | **Yes, but single-capability-type only** — see §93's blocking finding |
| `CapabilityRegistry` / `AdapterRuntime._rank_adapters()` | Yes | Yes | Yes | Presumed yes (not independently re-verified this session) | Yes, for the one registered capability type |
| `model_router.py` bootstrap/shadow/native state machine | Yes, with concrete thresholds (`SHADOW_PROMOTE_MIN_QUERIES=500`, `SHADOW_PROMOTE_THRESHOLD=0.85`) | Yes | Yes | Presumed yes | Yes, for models specifically |
| `ExecutionBudget` / `ProgressMonitor` / `ExecutionWatchdog` | Yes, but **duplicated** (DEBT-016) | Partially — internally consistent post-merge, not unified | Yes | Yes | **No — two canonical paths, which is itself the defect** |
| Checkpoint/resume (DEBT-003) | **No** | — | — | — | — |
| `Operation`/`ExecutionAttempt`/`ExecutionSnapshot` (DEBT-015) | **No — researched and proposed only** | — | — | — | — |
| User Cognitive Model (K4.2.7) | Yes (per prior-session record) | Yes, as of the G4 fix (§83) | Yes | Presumed yes | Yes |
| Project / Discussion as addressable scopes | **No** | — | — | — | — |
| Memory scope model (Global/Project/Discussion/Reusable) | **No** | — | — | — | — |
| `use_k42_frontend` flag | Set to `true` | Yes | Yes | Yes — independently re-verified this session against the full suite (1,331 passed / 34 failed, all pre-existing) | Yes, now the default |

**[INFER]** The audit's single most important row is `ExecutionPlanLifecycle`: an enum that already names exactly the state machine K4.3 needs to drive, sitting unused in code today. This is strong, direct evidence that K4.3's runtime state machine (§31) is not speculative architecture invention — it is completing something the K4.2 authors already anticipated and named but explicitly, deliberately, left for a later milestone to implement (per that code's own docstring, quoted in §16).

---

# 86. Architecture Ownership Matrix

**[DECISION]** The formal matrix the governing task requires:

| Component | Owns | Can decide | Cannot decide | Mutates | Consumes | Emits |
|---|---|---|---|---|---|---|
| **GovernanceKernel** | Authorization | Whether any proposed action executes | What action to propose | Nothing directly | Proposals from every other row | Authorization events |
| **CapabilityRegistry** | Expert metadata catalog | Nothing (a registry, not a decider) | — | Registration state | `ExpertDescriptor`s | Registration events |
| **CapabilityResolver / AdapterRuntime** | Static candidate ranking at plan/compile time | Which experts are *candidates* | Which candidate *runs now* | Nothing | Registry contents | — |
| **Planner** | `ExecutionPlan` | Strategy, decomposition | Runtime routing, execution order at runtime | `Goal`, `ExecutionPlan` | `Goal`, `PlanRealityFeedback` (§8) | New plan versions |
| **Plan Compiler** | `WorkflowDefinition` | How a `PlanStep` maps to a `WorkflowNode` | Which expert satisfies it at runtime | `WorkflowDefinition` | `ExecutionPlan` | Compiled workflow |
| **C-MoE Router** | Routing decision | Which expert(s) run now, next action (§6) | Whether the action is *allowed* (Governance's job) | `WorkGraph` node state | `ExecutionPlan`, `WorkGraph`, outcomes, memory (read) | `routing.decision`, outcome interpretations |
| **WorkGraph** | Live execution realization | — (a state container, not a decider) | — | Itself, only via C-MoE | Plan, outcomes | `workgraph.*` events |
| **WorkflowRuntime / ExecutionRuntime** | Execution mechanics | Whether an operation is *safe* to run mechanically | What to run next cognitively | Process/execution state | Routing decisions | `execution.*` events |
| **SupervisorWorker** | Worker-level recovery classification | Retry class for a worker failure | Cognitive next-action (C-MoE's job) | Worker retry state | `WorkerResult` | Recovery-class events |
| **ExecutionWatchdog / ProgressMonitor** | Progress/budget signal | Progress-ok vs. violated (binary) | Recovery action | Nothing (read-only signal) | Execution telemetry | `progress.*` / budget-violation events |
| **Memory (all scopes)** | Durable knowledge (§55) | — | Anything (it is data, not an actor) | Itself, via promotion (§47–48) only | Promotion proposals | Memory-write events |
| **Context Compiler** (future, §67) | Context assembly | What context to include | Routing itself | Nothing execution-relevant | Memory, WorkGraph state | Context objects |
| **Verification** (future, §69) | Outcome-vs-intent judgment | Whether intent is satisfied | Routing, execution | `verification_status` fields | Artifacts, outcomes | Verification results |
| **Reflection / Learning** (future, §70–71) | Cross-trajectory critique / policy improvement | Future routing *policy* changes | Current-task routing | Routing policy (future) | Event/decision log | Policy proposals |
| **Studio** (future, §81) | Visualization | Nothing (read-only consumer) | — | Nothing | All event streams | UI state only |

---

# 87. Architectural Risks / Things That May Be Messing With K4.3

**[FACT — the highest-confidence, most concrete finding of this entire study]** **The `WorkflowNode.worker_type` ↔ `WorkerRegistry` dispatch bridge is a single-capability-type hack, by its own author's own documented admission, and C-MoE cannot ship without replacing it.** `CapabilityExecutorWorker`'s docstring states the mechanism directly: `compiler.py::_compile_step()` sets `WorkflowNode.worker_type = PlanStep.capability_type` verbatim; `WorkerRegistry.get(worker_type)` resolves by exact string match against *registered worker class names*; the bridge works today only because a worker class exists whose `worker_type` class attribute happens to literally equal the one and only registered `capability_type` string (`llm_completion`). The docstring itself states this does not scale to a second registered `capability_type`. This is not a hypothetical risk — it is a **confirmed, present-tense blocker**: C-MoE's core value (routing among more than one expert for a given step) cannot be exercised through the current dispatch path at all, regardless of how well-designed C-MoE's routing logic is, because there is nowhere for a second candidate to be dispatched *to*.

Full risk register, each item classified by whether this study found direct evidence for it or is naming it as a hypothesis to guard against:

| Risk | Status | Evidence |
|---|---|---|
| **Static dispatch bridge assumes exactly one capability_type** | **[FACT] — confirmed, blocking** | `capability_executor.py` docstring, direct read |
| **Duplicate Watchdog/ProgressMonitor implementations** | **[FACT] — confirmed, non-blocking but must precede C-MoE** | `KNOWN_ISSUES.md` DEBT-016, direct read |
| **Checkpoint/resume absent** | **[FACT] — confirmed, blocking for any durability claim** | `KNOWN_ISSUES.md` DEBT-003, direct read |
| Planner/C-MoE leakage | **[INFER] — guarded against, not yet observed** | §4's timing-based test is the specific guard |
| Supervisor/C-MoE overlap | **[INFER] — guarded against via §33's tightened boundary** | — |
| CapabilityResolver/C-MoE dual authority | **[INFER] — guarded against via §86's ownership matrix** (Resolver ranks *candidates*, C-MoE selects *now*) | — |
| WorkGraph ownership ambiguity | **[INFER] — resolved by §86** (C-MoE is sole mutator) | — |
| Goal drift under replanning pressure | **[INFER] — mitigated by §7's testable invariant**, not yet empirically measured (no implementation exists to measure) | — |
| Uncontrolled recursion / routing loops | **[INFER] — bounded by §43's hard cognitive-budget ceilings** | — |
| Nondeterministic routing via LLM participation | **[INFER] — bounded by §77** | — |
| Stale project knowledge silently reused | **[INFER] — mitigated by §50/§52's supersession + freshness machinery** | — |
| Cross-task / cross-project contamination | **[INFER] — mitigated structurally by §40/§56**, not by runtime filtering | — |
| Uncontrolled memory promotion | **[INFER] — mitigated by §47's default-temporary pipeline** | — |
| Scope creep from adjacent future milestones (Verification, Reflection, Learning, Studio) | **[INFER] — actively resisted by §67–71, §81's "emit, don't own" pattern** | — |
| The two "K4.3" transition documents being mislabeled K4.2 work | **[FACT] — confirmed, cosmetic but should be fixed** | Direct diff/read, §2 |

---

# 88. Failure Matrix

**[DECISION]** Covering the governing task's full list, condensed into a table where every row answers all six required questions (detector, decision-owner, produced state, emitted events, work preserved/invalidated, governance-required):

| Failure | Detector | Decision owner | Work preserved? | Governance required? |
|---|---|---|---|---|
| Wrong expert selected | C-MoE (post-outcome, low result confidence) | C-MoE → reroute | Yes (§12, `REUSABLE` classification of any real sub-output) | No |
| Expert unavailable / degraded / timeout | Watchdog (progress) + eligibility filter (§20) | C-MoE (reroute to fallback, §20) | Yes | No |
| Expert partial result | Expert itself (`PartialResult`, §30) | C-MoE (continue vs. compose, §27) | Yes | No |
| False success | Verification (once it exists) or user | C-MoE, capped at `COMPLETED_WITH_WARNINGS` without real Verification (§32) | Yes (artifact kept, status downgraded) | No |
| Contradictory experts | Disagreement detector (§28) | C-MoE, escalation ladder (§28) | Yes, both outputs kept as evidence | Only if escalated to user |
| New information invalidates plan assumption | C-MoE, via `InformationGain` (§29) | Planner (replan, §8) | Yes, becomes replan input | No |
| Routing loop / retry storm | Cognitive budget ceiling (§43) | GovernanceKernel (hard stop) | Partial — completed nodes kept | **Yes** |
| Graph / context explosion | Cognitive budget (§43) / WorkGraph size ceiling | GovernanceKernel | Partial | **Yes** |
| Budget exhaustion | `ExecutionBudget` (existing) | GovernanceKernel → `SUSPENDED` (§31) | Yes, checkpointed (once §37 ships) | **Yes** |
| Governance rejection of a proposed action | GovernanceKernel | GovernanceKernel | Yes, action simply not taken | **Yes, by definition** |
| User changes goal / constraint | Intent layer (K4.2) | C-MoE + Planner, via §10 mutation path | Impact-analyzed (§12), not blanket-preserved or blanket-discarded | No, unless the change conflicts with a standing constraint |
| User cancels / pauses | Explicit control intent (§35) | GovernanceKernel-authorized state change | Yes | No |
| Resume after crash | Checkpoint mechanism (§37, once built) | C-MoE, re-entering at `READY` per node | Yes, exactly to last checkpoint | No |
| Duplicate submission / concurrent tasks | `operation_id` idempotency (§39) | ExecutionRuntime (reject duplicate) | N/A | No |
| New discussion accidentally inherits state | Structural — should be **impossible**, not merely detected (§40) | — | — | — |
| Stale project knowledge reused | Freshness/supersession check (§50, §52) | C-MoE (flags before use) | Superseded entry kept for audit, not deleted | No |
| Cross-task / cross-project contamination | Structural — should be **impossible** (§40, §56) | — | — | — |
| Memory poisoning | Promotion pipeline gate (§47, §54) | GovernanceKernel (approval requirement) | N/A — never promoted | **Yes** |
| Late stale result | `plan_version` mismatch (§36) | ExecutionRuntime (reject/log) | Logged as evidence, not accepted as outcome | No |
| Duplicate side effect | `operation_id` idempotency (§39) | ExecutionRuntime | N/A | No |
| Failed verification | Verification (future) | C-MoE (downgrade status, possibly replan) | Yes | No |
| Low confidence result | `LowConfidence` outcome (§30), confidence model (§22) | C-MoE (abstain or flag, §23) | Yes, flagged provisional | No |
| Expert version / schema change mid-task | Expert lifecycle (§61) | C-MoE (ineligibility for remainder of task only) | Yes, for in-flight tasks using the old schema | No |

---

# 89. Evaluation Strategy

**[DECISION]** Evaluated at the six levels the governing task specifies, each with a concrete, non-vague measurement rather than a restated aspiration:

| Level | Measured by |
|---|---|
| Router-level | Precision/recall of the eligibility filter (§20) against a hand-labeled candidate set; abstention rate (§23) vs. ground-truth "should have abstained" cases |
| Runtime-level | Fraction of impasses (§8) resolved by local replan vs. global replan (§82's research taxonomy) — a system replanning globally for every local hiccup is over-reacting |
| Goal-level | The §7 automated test (`Plan(v+1).goal_id == Plan(v).goal_id` across every non-user-triggered replan) run as a CI gate, not a manual review |
| Resource-level | Cognitive budget consumption (§43) as a fraction of total task cost — flags a router that "thinks" more than it "does" |
| Isolation-level | Zero tolerance: any cross-task or cross-project read observed in testing is a release blocker, not a tunable metric |
| Reliability-level | `pass^k`-style repeated-trial success rate (adopted directly from τ-bench, §82) rather than single-run success, applied to the MVP's own test scenarios (§97) |

**[EXT]** The `pass^k` metric's direct applicability here — repeated trials of the same scenario, scored on the fraction that succeed every time, not just once — is the single most directly reusable piece of external methodology this study's research sweep found, and it is adopted without modification.

---

# 90. Wasted-Work Metrics · Contamination Metrics · Goal-Drift Metrics

**[DECISION]** Three explicit, separately-tracked metric families, per the governing task's insistence that these not be folded into a single generic "quality" score:

**Wasted work:** redundant expert invocations for a `VALID`-classified (§12) step, tokens spent on a replan that produces an identical plan to the one it replaced, verification calls against already-`VERIFIED` evidence. **[DECISION]** The specific, falsifiable claim this study commits to for evaluation: **a user task mutation (§10) affecting one branch of a multi-step plan must cost less, in expert invocations and tokens, than restarting the task from zero** — measured directly, per mutation test case (§97), not asserted.

**Contamination:** any Task A data observed in Task B's context, event log, or WorkGraph; any Project A memory observed in Project B's grounding/routing context (§sub-study §10); a superseded plan version's output accepted as current (§36). **[DECISION]** Target: zero observed instances in testing, treated as a correctness bug, not a tunable rate, consistent with the Isolation-level evaluation in §89.

**Goal drift:** measured via §7's automated invariant, plus a secondary, harder-to-automate check: for a task that underwent N replans, whether the *final* artifact still addresses the *original* goal's constraints, not merely the *most recently modified* plan's constraints — this requires either a Verification stub (§69) or manual review in the MVP, and this study is explicit that the harder check is not fully automatable until Verification is real.

---

# 91. Current State vs Target State

**[DECISION]** Full matrix per the governing task's requested area list, evidence-tagged:

| Area | Current State | Evidence | K4.3 Target | Gap | Action |
|---|---|---|---|---|---|
| Planner | Goal+constraints+registry → `ExecutionPlan`, single-pass, no reality input | [FACT] `plan()` signature | Consumes conditional `RealityBrief` (§4 amendment) | Reality Assembly does not exist | Build thin stub (Packet 1, §96) |
| Capability Discovery | Static candidate generation, K42-002 fixed | [FACT] KNOWN_ISSUES.md, code diff | Unchanged, feeds C-MoE's candidate pool | None | None |
| CapabilityResolver / AdapterRuntime | Ranks candidates statically | [STUDY] CS | Unchanged authority, consumed by C-MoE (§86) | None — boundary already correct | None |
| Expert abstraction | Only `capability_type` string exists; no `ExpertDescriptor` | [FACT] single registered type | `ExpertDescriptor` (§17) | Full gap | Build (Packet 2) |
| C-MoE | **Does not exist** | [FACT] | Full runtime per §6, §31 | Full gap | Core of this milestone |
| Routing / dispatch | **Blocked** — single-capability-type hack | [FACT] `capability_executor.py` docstring | Generalized dispatch (§93) | **Blocking gap** | Packet 0, before anything else |
| WorkGraph | `ExecutionPlanLifecycle` enum exists, undriven | [FACT] | Live, C-MoE-owned (§16) | Enum exists, nothing drives it | Build (Packet 3) |
| Outcome Contract | 8-state AED placeholder | [STUDY] AED | 10-state (§30) | Extension, not replacement | Build (Packet 2) |
| Goal preservation / replanning | `caused_by` + `planner_impasse` event exist | [FACT] this session | Generalized to `PlanRealityFeedback` (§8) | Partial — proto-mechanism exists | Extend (Packet 4) |
| Task mutation | None | [FACT] | §10's diff mechanism | Full gap | Build (Packet 5) |
| Task/execution identity | `trace_id` regenerates per request | [STUDY][FACT] RS, WE | Stable `operation_id` per task (§39) | Confirmed gap | Build (Packet 0, alongside dispatch fix) |
| Discussion/Project scope | No addressable Project/Discussion concept | [FACT] | §44's Application-layer model | Full gap | Build (Packet 6) |
| Global/Project memory | L0-L4 exists (memory *type*), no scope axis | [FACT] existing UnifiedMemory architecture | §45's orthogonal scope model | Full gap on the scope axis | Build (Packet 6) |
| Result promotion | None | [FACT] | §47's pipeline | Full gap | Build (Packet 6) |
| Watchdog/Supervisor | Exist, but duplicated (DEBT-016) | [FACT] KNOWN_ISSUES.md | Unified, C-MoE-consumed signal (§33-34) | Confirmed, must precede C-MoE | Packet 0 |
| Durability | DEBT-003 open, DEBT-015 proposed-only | [FACT] KNOWN_ISSUES.md | Checkpoint/resume live (§37) | Confirmed, blocking for durability claims | Packet 0/1 |
| Verification/Reflection/Learning | Do not exist | [FACT] | Stub interfaces only (§69-71) | Intentional — not this milestone's gap to close | None beyond stubs |
| Context Compiler | Does not exist | [FACT] | Stub only (§67, §sub-study) | Intentional | Thin stub (Packet 1) |
| Governance | Existing Governors, no C-MoE-specific rules | [FACT] existing `PROJECT_INSTRUCTIONS.md` §6.1 | Extended rules, no new Governor (§78) | Rule additions only | Extend (throughout) |
| Determinism / Observability | Existing event-sourcing discipline | [FACT] Kernel Law 2 | `routing.decision` event (§80) added to existing SSE stream (§81) | Additive | Build (Packet 2-3) |
| Studio | SSE/snapshot plumbing exists, no Studio UI | [FACT] `EXECUTION_PROGRESS_INSPECTION_IMPLEMENTATION_REPORT.md` | Unchanged — K4.3 emits, does not build Studio | None for K4.3 | None |

---

# 92. Proposed K4.3 Architecture

**[DECISION]** Consolidated final architecture, synthesizing every decision above:

```
                              ┌─────────────────────────────┐
                              │   Kernel (unchanged)         │
                              │   GovernanceKernel authorizes │
                              │   every proposal below        │
                              └──────────────┬────────────────┘
                                              │ authorizes
User Goal (Discussion, optionally in a Project — Application layer, §44)
   │
   ├─[conditional]→ Reality Assembly (thin, Context-Compiler stub, §sub-study) → RealityBrief
   │                                                                                  │
   ▼                                                                                  │
Planner (K4.2, existing) ◄────────────────────────────────────────────────────────────┘
   │  consumes: Goal, Constraints, CapabilityRegistry, RealityBrief
   ▼
ExecutionPlan (existing type, +based_on_snapshot)
   │
   ▼
C-MoE feasibility pass (§20's eligibility funnel, reused) ──infeasible──► Planner (new plan version)
   │ feasible
   ▼
┌─────────────────────────── C-MoE / Cognitive Runtime (NEW — this milestone) ───────────────────────────┐
│                                                                                                          │
│   WorkGraph (live realization, §16) ── owns node states (§31) ── drives ExecutionPlanLifecycle (§16)    │
│         │                                                                                                │
│         ▼                                                                                                │
│   Candidate Generation → Eligibility → Soft Ranking → Fallback (§20)                                     │
│         │                                                                                                │
│         ▼                                                                                                │
│   Routing Decision (§19, deterministic mechanism + versioned policy) ── emits routing.decision (§80)     │
│         │                                                                                                │
│         ▼                                                                                                │
│   ── dispatched via a GENERALIZED bridge (replacing the single-capability-type hack, §85/§93) ──         │
│         │                                                                                                │
└─────────┼──────────────────────────────────────────────────────────────────────────────────────────────┘
          ▼
   ExecutionRuntime / WorkflowRuntime (existing) ── executes ── Expert(s)
          │
          ▼
   Capability Outcome (§30, 10-state contract)
          │
          ▼
   C-MoE interprets outcome ──┬─ continue / adapt / compose / route (§27) / abstain (§23)
                               ├─ NeedReplan → PlanRealityFeedback (§8) → Planner (goal preserved, §7)
                               ├─ NeedCapability → capability-evolution trigger (§72, stub only)
                               ├─ VERIFYING → Verification stub (§69)
                               └─ COMPLETED / FAILED / SUSPENDED (§31-32)

Memory (orthogonal to all of the above, §45):
   Global User Memory ←promotion(§47)← Project Memory ←promotion← Discussion/Task State
                                                              ↑
                                                    Reusable Evidence (cross-cutting, §45)
   All reads/writes governed (§48-49); all scoped by task_id/project_id (§39-40, §56)
```

**[INFER]** Every box in this diagram was justified independently in an earlier section; nothing here is introduced for the first time at the diagram stage.

---

# 93. Minimum Viable K4.3

**[DECISION]** The smallest implementation that honestly earns the name C-MoE, incorporating the reality-grounding sub-study's own MVP recommendation (its §13, item 4):

```
Packet 0 (prerequisite, not C-MoE itself, but blocking):
    - Replace the single-capability-type dispatch hack (§85/§87) with a real
      WorkflowNode → ExpertDescriptor → invocation path that works for N ≥ 2
      registered capability types
    - Unify the duplicate Watchdog/ProgressMonitor implementations (DEBT-016, §33)
    - Implement checkpoint/resume (DEBT-003, §37), using the already-proposed
      Operation/ExecutionAttempt/ExecutionSnapshot schema (DEBT-015, WE)
    - Introduce stable per-task operation_id (§39), distinct from per-request trace_id

Packet 1 (MVP core):
    - ExpertDescriptor (§17), minimal fields only
    - Reality Assembly stub + conditional RealityBrief (sub-study §6-7) — thin,
      read-only, facts-only
    - C-MoE feasibility pass reusing the eligibility funnel (§20, sub-study §6)
    - Single work-unit runtime state machine (§31)
    - 10-state Capability Outcome Contract (§30)
    - PlanRealityFeedback, generalizing the existing caused_by/planner_impasse
      mechanism (§8)
    - Goal versioning + the automated goal-preservation test (§7, §11)
    - routing.decision event (§80), riding the existing SSE stream (§81)
```

**[DECISION]** Explicitly excluded from MVP even though designed above: expert composition beyond primary+fallback (§27's other three primitives), branching (§15), the full four-scope memory model (§45 — MVP needs only task-local state, since Project/Global scope requires Packet 6, sequenced after MVP), disagreement resolution beyond simple confidence comparison (§28's escalation ladder past step 1). **[INFER]** This MVP is honest specifically because it cannot be satisfied by relabeling the existing static dispatch — Packet 0's dispatch-bridge replacement is a hard, structural prerequisite that forces at least two real, distinct experts to exist and be routed between before "K4.3 shipped" can be claimed, which directly prevents the single most tempting shortcut this study's audit surfaced (§85).

---

# 94. Full K4.3 Target

**[DECISION]** Everything designed in this study but excluded from MVP: full expert composition (§27), branching/rollback/merge (§15), the complete four-scope memory model with promotion pipeline (§45–58), Projects and Discussions as addressable scopes (§44), task mutation with full impact analysis (§9–13), expert disagreement's full escalation ladder (§28), cognitive budget hierarchy beyond task-level (§43), and risk-adjusted routing (§26) once a second genuinely-costed expert exists to make it testable.

---

# 95. Deferred / Not K4.3

**[DECISION]** Named with reasons, not as a dumping ground, per the governing task's explicit instruction:

```
Full Verification Runtime         — §69's stub is sufficient for K4.3; a real one is a separate
                                     milestone with its own architecture question (what does
                                     "satisfies intent" mean per artifact type)
Full Reflection Runtime           — §70; requires historical trajectory storage not designed here
Full Adaptive Learning            — §71; requires an optimization/bandit policy this study
                                     deliberately did not design, following model_router.py's own
                                     precedent of fixed-threshold, not learned, promotion
Distributed multi-node C-MoE      — every mechanism in this study (WorkGraph, identity, checkpointing)
                                     is explicitly single-node; FR-0002/FR-0003 in the Future Research
                                     Vault already track the distributed direction separately
Context Compiler (full)           — §67's stub suffices; the real thing is a separate milestone
Evaluation & Reliability Lab      — §68; C-MoE emits events, does not build the Lab
OCBrain Studio (the UI itself)    — §81; C-MoE emits Studio-consumable events onto already-existing
                                     infrastructure, does not build Studio
Proactive optimization / Fable    — §74; only the workflow_signature tagging prerequisite ships
Full capability/skill acquisition — §72; only the NeedCapability trigger ships, resolving to
                                     abstain+escalate until a real acquisition subsystem exists
Distributed Work Graph (FR-0004)  — this study advances FR-0004 from Research to Architecture
                                     Proposal for the single-node case only; the distributed
                                     extension FR-0004 originally implied remains Research-status
```

---

# 96. Proposed Implementation Sequence

**[DECISION]** Ordered so every dependency precedes its consumer, per packet:

| Packet | Objective | Dependencies | Key contracts | Exit criteria |
|---|---|---|---|---|
| 0a | Unify Watchdog/ProgressMonitor (DEBT-016) | None | — | Single implementation, both call sites migrated, existing tests still green |
| 0b | Checkpoint/resume (DEBT-003) via Operation/ExecutionAttempt/ExecutionSnapshot (DEBT-015) | 0a (needs one progress signal to checkpoint against) | `Operation`, `ExecutionAttempt`, `ExecutionSnapshot` | A killed-and-restarted task resumes without repeating completed side effects |
| 0c | Stable per-task `operation_id` | 0b | — | Idempotency test: duplicate submission of the same task produces one execution, not two |
| 0d | Generalize the dispatch bridge beyond one `capability_type` | 0a–0c not required, but must land before Packet 1 | `ExpertDescriptor`-lite | A second, real capability_type can be registered and dispatched to, in a test |
| 1 | Reality Assembly stub + `RealityBrief` | 0d | `RealityBrief`, `RealitySnapshot` | Planner receives a non-empty brief for a project-scoped test task; empty/skipped for a trivial one |
| 2 | Expert Model + Outcome Contract + Runtime State Machine | 1 | `ExpertDescriptor` (full), 10-state outcome enum, §31's state machine | Two registered experts, C-MoE routes between them, both outcome paths tested |
| 3 | WorkGraph + `ExecutionPlanLifecycle` wiring | 2 | WorkGraph mutation primitives (§16) | `ExecutionPlanLifecycle` transitions are driven end-to-end for the first time |
| 4 | Plan Reality Feedback + goal versioning + preservation test | 3 | `PlanRealityFeedback`, `Goal.version` | §7's automated invariant passes as a CI gate |
| 5 | Task mutation + impact analysis | 4 | §12's classification, §13's propagation | A mutation test demonstrably costs less than restart (§90's wasted-work claim) |
| 6 | Memory scope model + Project/Discussion + promotion pipeline | 5 (needs goal/plan versioning to attribute promoted knowledge correctly) | §45–58's full contract set | Cross-discussion sharing works within a project; cross-project sharing is confirmed impossible in a test |

**[INFER]** Packet 0 is four sub-packets, not one, and all four are prerequisites this study did *not* invent for K4.3 — they are pre-existing, already-logged debt (DEBT-003, DEBT-015, DEBT-016) plus one already-identified blocking risk (the dispatch bridge). K4.3's *own* new architecture does not begin until Packet 1.

---

# 97. Testing Plan

**[DECISION]** Mapped directly onto the governing task's category list, each with a concrete first test rather than a restated category name:

```
Routing:      given 2 eligible experts + 1 ineligible, the ineligible one never appears
              in a routing.decision event's candidate set
Runtime:      a NeedReplan outcome produces a new Plan version with an unchanged goal_id
Goal evolution: an ADD-only mutation preserves every VALID-classified prior node untouched
Reuse:        a REUSABLE-classified node is not re-executed; its result is reused directly
Isolation:    two concurrently running tasks in the same project never observe each other's
              WorkGraph state, verified by direct query attempt (must fail/return empty)
Durability:   kill the process mid-task, restart, confirm resume without duplicate side effects
Security:     a crafted expert-output payload claiming elevated authority is confirmed to
              rank at precedence position 7 (§51), never higher, in a routing decision
Determinism:  the same routing inputs, replayed, produce the same candidate ordering and
              the same tie-break, twice
Resource use: a mutation-handling test measures and asserts lower token/call cost than
              an equivalent restart-from-zero baseline (§90)
```

---

# 98. Migration / Legacy Cleanup Requirements

**[DECISION]** Explicit, per the governing task's own audit categories:

```
Can remain as-is:      K2.2 PlannerWorker path (now explicitly LEGACY/COMPATIBILITY per the
                        G7 flag flip, §83) — not touched by K4.3, kept for rollback safety
Must change:            core/workers/capability_executor.py's single-capability-type dispatch
                        (Packet 0d, §96) — this is the one piece of "working" code this study
                        recommends replacing outright, not extending
Must be removed:        Nothing wholesale — no dead code was identified whose removal is a
                        K4.3 prerequisite
Compatibility bridge:   The K2.2 legacy path itself, kept deliberately as a bridge/rollback
                        path per the existing DEBT-017 acceptance (streaming bypasses K4.2 —
                        already accepted as low-severity, unrelated to K4.3)
Dangerous to keep:      The two duplicate Watchdog/ProgressMonitor implementations (DEBT-016)
                        — "dangerous" specifically because C-MoE's own recovery-signal
                        consumption (§33) requires exactly one canonical signal source
Documentation cleanup:  Rename both copies of the misnamed "K4_3_IMPLEMENTATION_TRANSITION.md"
                        (§2) to reflect their actual K4.2 content, to prevent a future
                        session from repeating this study's own initial confusion
```

---

# 99. Open Questions

**[DECISION]** Left open deliberately, not resolved by assertion:

1. The exact granularity of `expert_availability_summary` inside a `RealityBrief` (sub-study §12) — deferred to the Packet 1 implementer, who will have real data this study does not.
2. Whether `core/cognitive/user_model.py`'s current output already carries the `explicit/observed/derived/hypothesized/approved` confidence tiers this study's §73 assumes it should — **flagged as requiring direct verification before Packet 6**, not assumed either way, since this session did not read that file directly.
3. Whether the cognitive-budget ceilings proposed in §43 (`max_routing_steps_per_task` etc.) should have universal default values or be project-configurable from day one — this study leans toward universal-first (consistent with §71's "fixed constants before learned policy" principle) but does not treat this as settled.
4. Whether a `FeasibilityResult` containing only `degraded_warnings` should surface to the user pre-execution or only log — explicitly a product decision, not an architecture one (sub-study §12).
5. Whether the existing `AdapterRuntime._rank_adapters()` should be refactored to directly produce `ExpertDescriptor`-shaped output, or whether a translation layer should sit between them — this study did not have sight of `_rank_adapters()`'s current implementation and flags this as a Packet 2 investigation item rather than guessing at its current shape.

---

# 100. Final Recommendations

1. **Do not begin K4.3 implementation from this document directly.** Ratify it through the existing ADR mechanism first (`docs/architecture/decisions/`, DRAFT → REVIEW → APPROVED), consistent with `PROJECT_INSTRUCTIONS.md` §20.5's requirement that major architectural decisions accumulate into ADRs — this study is the Architecture Proposal, not the Approval.
2. **Execute Packet 0 (§96) before writing any C-MoE-specific code.** All four of its sub-packets are pre-existing, already-logged debt or an already-confirmed blocking risk, not new scope this study invented — deferring them further only makes Packet 1 harder to build cleanly on top of.
3. **Treat this document and its companion sub-study together as one Architecture Proposal artifact.** The main study incorporates the sub-study's conclusion at §4 and §6; do not implement one without the other, since the MVP (§93) explicitly bundles the reality-grounding mechanism into Packet 1.
4. **Rename the two misnamed "K4_3_IMPLEMENTATION_TRANSITION.md" files** (§2, §98) as a small, immediate documentation-hygiene fix, independent of when Packet 0 begins.
5. **Advance FR-0004 (Work Graphs) from Research to Architecture Proposal status** in the Future Research Vault, scoped explicitly to the single-node case this study designed — its distributed extension remains Research-status.
6. **Update `KNOWN_ISSUES.md`** to cross-reference DEBT-003, DEBT-015, and DEBT-016 against this study's Packet 0 (§96), so a future session immediately understands these are now K4.3-blocking rather than merely open.
7. **The single fact most worth carrying forward if nothing else from this document is remembered:** the current `WorkflowNode` dispatch mechanism cannot route to more than one expert. Every other conclusion in this study assumes that gets fixed first.

---

## Final Required Conclusion — Self-Check

The governing task requires this study to precisely answer a specific set of questions before it can be considered complete. Answered directly, each with a pointer to its full treatment:

> **What exactly is OCBrain K4.3?** The Cognitive Runtime — a system-level Cognitive Mixture of Experts (C-MoE) with standing authority to decide, at runtime, what should happen next to bring a Planner-authored `ExecutionPlan` into satisfied reality. (§1, §3)

> **Why is it fundamentally different from K4.2?** K4.2 decides *what should be done*, before any execution, from static metadata plus (per the reconciled sub-study) a bounded reality brief. K4.3 decides *who does it, right now*, using everything Planner had plus what has actually happened. Different questions, different authority, different timing. (§4)

> **Why is C-MoE the core of K4.3?** Because the gap between "a plan expressed as capability types" and "a worker actually running" is currently bridged by a single-capability-type hack (§85, §87) that cannot survive a second registered expert — something must own real-time expert selection and adaptation, and nothing currently does. (§3)

> **How does C-MoE bring a plan to reality?** Via the closed loop in §6: route → execute → interpret outcome → continue/adapt/compose/replan, with every transition's owner explicitly assigned.

> **How does it handle reality diverging from the plan?** Structured outcomes (§30) distinguish failure from insufficient-success; a `NeedReplan` outcome triggers Plan Reality Feedback (§8) rather than a bare failure signal.

> **How does it communicate structured feedback to Planner?** `PlanRealityFeedback` (§8), generalizing the `ExecutionPlan.caused_by`/`cognitive.planner_impasse` mechanism that already exists in code today.

> **How does Planner replan without losing the goal?** The automated invariant in §7: every non-user-triggered replan must preserve `goal_id`, enforced as a testable contract, not a norm.

> **How does the system react when the user changes the task?** A typed diff against the active Goal (§10), routed through five-state impact analysis (§12) and dependency-aware invalidation (§13) — never a blanket restart, never a blanket preservation.

> **How does it preserve useful previous work while avoiding unnecessary recomputation?** §12's five-state classification plus §14's cost-aware reuse-vs-recompute heuristic, measured directly against a restart baseline (§90).

> **How are goal, plan, graph, artifact and task versions related?** Goal ancestry (§11) and plan versioning (§4's `caused_by`, extended) both feed a WorkGraph that tracks live realization (§16); artifacts carry their own lineage (§58) referencing the plan/node/expert that produced them — one consistent provenance chain (§66).

> **How do normal discussions and Projects coexist?** Both are Application-layer groupings over the Kernel's existing Scope primitive (§44) — Discussion is one Scope; Project is a named grouping of Scopes plus a Project Memory resource. Neither is a new Kernel primitive.

> **How do Project discussions share relevant knowledge without inheriting each other's active execution state?** The four-scope memory model (§45) plus the hard rule that Discussion/Task State never crosses task boundaries (§40) while Project Memory and Reusable Evidence explicitly can, subject to the promotion pipeline (§47).

> **How does Global User Memory allow OCBrain to know the user without contaminating task state?** Promotion to Global scope requires the strictest bar in §47's table — explicit approval or repeated high-confidence observation, never a single task's inference — and reads are structurally scoped (§49), not filtered post-hoc.

> **How can this eventually enable proactive optimization and the Fable direction?** Via the `workflow_signature` tagging prerequisite (§74) on promoted Global memory — the only forward-compatible hook this study adds now, with the full pipeline explicitly deferred (§95).

> **How does C-MoE select, compose, and replace experts?** Candidate generation → eligibility → soft ranking → fallback (§20), four composition primitives (§27), and the lifecycle/health model reused directly from `model_router.py` (§61).

> **How are routing confidence, expert confidence, result confidence and goal-satisfaction confidence distinguished?** Five separate, never-averaged fields (§22), a direct lesson from this project's own DEBT-013-adjacent history.

> **How does C-MoE abstain when it cannot route safely?** A first-class `abstain` outcome with three sub-modes (§23), preferred over a forced low-confidence routing decision.

> **How are concurrency, cancellation, late results and stale executions handled?** Per-task scoping by construction (§39–41), `plan_version`-checked late-result rejection (§36), and `operation_id`-based idempotency (§39).

> **How are durable execution and side effects made safe?** Effectively-once via idempotency keys, not exactly-once (§37) — an honest guarantee, not an aspirational one — sequenced as a hard MVP prerequisite (§93, Packet 0), not a K4.3-time nice-to-have.

> **How are memory, artifacts and evidence governed?** The State/Knowledge/Evidence/Decision model (§55) plus the promotion pipeline (§47) — nothing becomes durable Knowledge without passing through a governed step.

> **How are security, scope, provenance and instruction hierarchy enforced?** A fixed, provenance-based precedence order (§51) that never lets externally-sourced content outrank the user or verified state, regardless of how it is phrased (§64).

> **How does C-MoE interact with Context Engineering, Verification, Reflection, Learning and the Evaluation & Reliability Lab without swallowing those milestones?** A uniform "emit, don't own" pattern (§67–71): C-MoE requests or emits structured signals; each future milestone consumes them without C-MoE ever implementing their logic.

> **How does the architecture remain deterministic, auditable, governable, resource-aware and observable?** Stable-key ordering and LLM-as-signal-not-decision (§77), no new Governor beyond extended rules on existing ones (§78), a two-tier budget with hard ceilings (§43), and one structured event type per routing decision (§80).

> **What is the smallest implementation that is genuinely C-MoE?** §93 — and it cannot be satisfied by relabeling existing code, because Packet 0 forces the single-capability-type dispatch hack to be replaced before Packet 1 can even begin.

> **What is the complete realistic K4.3 target?** §94.

> **What must explicitly remain outside K4.3?** §95, with each exclusion's reason stated, not merely asserted.
