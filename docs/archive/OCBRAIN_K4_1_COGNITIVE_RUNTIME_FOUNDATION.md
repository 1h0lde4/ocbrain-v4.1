# OCBrain K4.1 — Cognitive Runtime Foundation

**Date:** July 19, 2026
**Status:** Architecture Only — zero code, zero implementation, zero repository modifications, per instruction.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md` and `PROJECT_INSTRUCTIONS.md`. Extends `OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` (hereafter "K4") rather than superseding it — K4 §1–§19 remain the design for what this document calls the *core* Cognitive Runtime; nothing here changes them. Everything below is Architecture Specification (Constitution Part VIII), freely revisable without amending either governing document.
**Method:** No repository access performed this session. Per this session's own instruction, the five frozen Kernel ownership boundaries (Governance, Memory, Workflow, Execution, Adapter/Capability, Event) are treated as the already-verified baseline K4 §0 established on July 18, 2026, and are not the target of this milestone. Cross-document consistency — this session's brief against K4 and the Constitution — was checked directly; one discrepancy was found and is reported below rather than silently resolved.

---

## 0. Scope Correction and Carried-Forward Status

Two things worth stating before any design starts, in the same spirit K4 §0 and K1.5 §0 already established: report discrepancies, don't silently resolve them, and don't let them block architecture-only work.

**K3 status.** This session's brief says the work "continues after the completion of the Kernel milestones (K1 through K3.5.1)" — carefully not claiming K3 itself. That phrasing is consistent with K4 §0's own finding: K3.5 and K3.5.1 are genuinely complete; K3 (Kernel Compliance Audit) itself was `⬜ Next` in `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md` as of K4's session and, absent a newer status document, is treated as still open here. This doesn't block K4.1, for the same reason it didn't block K4: this document performs zero Kernel modification and depends only on the ownership boundaries K4 §0 already verified. It does mean the same caveat K4 §0 raised still applies: K3 should complete, or be explicitly and deliberately deferred by you, before any code lands from K4.2 onward.

**Roadmap renumbering.** This session's brief inserts a new milestone — "Cognitive Runtime Foundation" — at position K4.1, colliding with K4 §19's own numbering, where K4.1 already meant "Intent + Goal primitives." Side by side:

| Old (K4 §19) | New (this session's brief) |
|---|---|
| K4.1 — Intent + Goal primitives | K4.1 — Cognitive Runtime Foundation |
| K4.2 — ExecutionPlan + Planner (decomposition only) | K4.2 — Intent Interpretation / Goal Formation / Planner |
| K4.3 — Plan Compiler + Governance Gate | K4.3 — Execution Plans / Plan Compiler / Governance Gate |
| K4.4 — ReflectionWorker + EvaluatorWorker (read-only) | K4.4 — Reflection / Evaluation |
| K4.5 — Memory Integration | K4.5 — Memory Integration |
| K4.6 — SupervisorWorker | K4.6 — Supervisor |
| K4.7 — Full pipeline integration test | K4.7 — End-to-End Cognitive Pipeline |

This is not a clean insert-and-shift. New K4.2 folds old K4.1 (Intent+Goal) together with the *decomposition* half of old K4.2 (Planner); new K4.3 picks up the *compilation* half of old K4.2 (ExecutionPlan as an artifact) together with old K4.3 (Plan Compiler + Gate). The new numbering is adopted as authoritative below, since it is the more recent, explicitly-labeled "Updated Roadmap." But the exact scope boundary between new-K4.2 and new-K4.3 — specifically, whether ExecutionPlan-the-artifact is designed alongside Planner (K4.2) or alongside the Compiler that consumes it (K4.3) — is a genuine, open reconciliation this document does not resolve, because resolving it means designing Planner and the Compiler, which is explicitly out of scope here. Flagging it now so the K4.2 session opens with the boundary decided on purpose, not by drift.

**What's taken as given vs. designed here.** Given, per instruction: the five frozen Kernel ownership boundaries, and everything K4 §1–§19 already designed for the core reasoning pipeline. Designed here: how that core pipeline sits inside a larger, extensible whole — which is what §1 onward is about.

---

## 1. The Foundational Decision

The single decision everything below hangs on: **Cognitive Runtime Extensions require no new Kernel-facing execution mechanism.** They are additional producers into the same Plan→Compile→Execute seam K4 already built (K4 §1, §6: the Cognitive Runtime "produces a `WorkflowDefinition`... never touches a storage backend, never emits an `EventStream` event under its own authority"). Whatever an Extension's own internal reasoning is, the moment it needs to affect the world outside itself, that need is expressed the same way the core Planner already expresses it — as steps folded into a compiled plan, gated by the same governance check, executed by the same `WorkflowRuntime`.

This makes the Extension Model (§9) a **reasoning-composition problem** — how does the core Cognitive Runtime recognize when to delegate reasoning, and how does it fold the result back in — rather than an **execution problem**, which K4 already solved. It is also the concrete, mechanical answer to the design principle stated in this session's brief: "the addition of future Cognitive Runtime Extensions should require extension, not redesign." If Extensions needed their own path into the Kernel, every new Extension category would be a candidate for a second, uncoordinated execution stack — precisely the "build without wiring" failure this project has already hit twice (`RetrievalContextBuilder`/`GraphRAGPipeline` disconnection, K1.5 §0; the Worker layer disconnection, K1 §1). Closing that door structurally, rather than trusting future sessions to remember not to open it, is the point of this document.

---

## 2. What the Cognitive Runtime Is — *Deliverable 1*

**Definition, unchanged from K4 §1, restated at the layer this document adds:** the Cognitive Runtime is the layer that decides what should happen; the Kernel is the layer that makes what's decided actually happen, safely, governed, and replayably. This document does not revise that sentence — it specifies what sits *inside* "the layer that decides," now that "decides" can mean either the core pipeline (Intent Interpreter → Planner → Plan Compiler, with Reflection/Evaluation/Supervision around it, all per K4) or a registered Extension's specialized reasoning.

**Begins:** at Intent Interpretation. A clarification worth making explicit, because this session's own layered diagram ("Applications → Intent → Cognitive Runtime → ...") could be read as placing Intent's formal production outside the Cognitive Runtime: it does not. What Applications hand the Cognitive Runtime is an unstructured request; **Intent**, as a first-class artifact, is still minted by Intent Interpretation inside the Cognitive Runtime, exactly as K4 §2 already specified ("produces: Intent (raw, timestamped)"). The diagram depicts Intent's *origin* (a user's raw want), not a relocation of who produces the formal object. This preserves Constitution Invariant 1 ("the kernel does not act on intent it has not first attempted to understand") without contradiction.

**Ends:** at Response synthesis, unchanged from K4 §2 — delivery is interface-layer plumbing outside both the Cognitive Runtime and the Kernel.

**Owns**, extending K4 §1's list by exactly one item: intent interpretation, goal formation, planning, plan compilation (the translation step, not execution), reflection, evaluation, supervision — and now, **recognizing when a Goal or sub-Goal falls inside a registered Extension's declared domain, delegating to it, and folding its returned artifact back into the reasoning in progress.**

**Never owns**, extending K4 §1's list by exactly one item: memory persistence, governance, workflow execution, capability execution, event persistence — and now, **the internal reasoning logic of any given Extension.** The Cognitive Runtime coordinates delegation; it does not reach inside an Extension's own decision-making any more than the Kernel reaches inside a Worker's own `_run()`. This is the same boundary K4 already drew around workers, held one layer up.

---

## 3. Ownership Boundaries — *Deliverable 2*

| Layer | Owns | Never owns |
|---|---|---|
| **Applications** | Intent capture from the user, response presentation, session/UX state | Any reasoning, any execution, any governance |
| **Cognitive Runtime (core)** | Intent interpretation, goal formation, planning, plan compilation, reflection, evaluation, supervision, Extension delegation/coordination | Memory persistence, governance enforcement, workflow/capability execution, event persistence, an Extension's internal reasoning |
| **Cognitive Runtime Extensions** | Specialized reasoning within one declared domain (discovery, workspace, skill, knowledge, agent, learning — and future, unnamed domains), expressed as Cognitive Artifacts | Kernel execution of any kind, governance enforcement, another Extension's domain, direct memory writes, a second door into `WorkflowRuntime` |
| **Kernel** | Governance, event durability, memory persistence, workflow/worker/capability execution — unchanged from K4 §0's frozen boundaries | Reasoning, planning, goal formation, Extension coordination |
| **Capabilities** | Concrete, schedulable units of work, via Adapters | Any judgment about whether or when they should run |

Every row has exactly one owner for each responsibility it lists; nothing above appears in two rows. The one boundary worth stating explicitly because it is new: **Extensions sit inside the Cognitive Runtime's layer, not between it and the Kernel.** This session's brief diagrams Extensions as a stage below the Cognitive Runtime and above the Kernel; §9 explains why that placement, read as a mandatory serial stage every request passes through, is revised — Extensions are optional, delegated-to peers the core Cognitive Runtime consults, not a pipeline stage everything flows through.

---

## 4. A Terminology Note: Extensions Don't Provide "Capabilities"

This session's brief describes Extensions as providing "specialized cognitive capabilities." Read informally that's harmless, but K1.5 §1 froze **Capability** (capital-C) as a precise term — "an abstract, schedulable unit of work, defined by its contract, independent of what satisfies it" — owned by the Kernel's `CapabilityRegistry`. Reusing that word for what an Extension provides would collide with a term this project has already gone to real trouble to disambiguate (K1.5's entire §1.2 is collapsed synonyms, argued one by one). It's also inaccurate: a Capability is executed; what an Extension provides is *reasoned with*.

This document does not mint a competing noun for the sake of having one. What an Extension exposes is precise enough already once §5 names it: a `CognitiveExtension`-satisfying **reasoning surface**, scoped to one domain. "Capability" stays exactly what K1.5 already made it.

---

## 5. Architectural Contracts for Extensions — *Deliverable 3*

**Decision: one generic `CognitiveExtension` Protocol, not a closed set of per-domain contracts** (no separate Discovery contract, Workspace contract, Knowledge contract, and so on).

**Why not per-domain contracts.** A closed set of named contracts requires the core Cognitive Runtime's own code to enumerate known Extension categories. Adding a genuinely novel one — this session's own examples: Simulation Runtime, Creativity Runtime, Robotics Runtime, something with no name yet — would then require touching the core Cognitive Runtime to add a matching contract type. That is exactly the redesign this document exists to make unnecessary.

**Why a single Protocol works.** This project has already solved a structurally identical problem once: K1.6 rejected a taxonomy of Resource base classes in favor of `Resource` as a single structural Protocol, satisfied by whatever happens to have the right shape. The same resolution applies one layer up. It is also independently validated in the research corpus already adopted into this project's roadmap: `mims-harvard/ToolUniverse`'s "AI-Tool Interaction Protocol" — a minimal two-operation interface, `Find Tool` / `Call Tool` — lets any model use any of 1,000+ registered tools with no bespoke per-tool integration (`OCBRAIN_EXTERNAL_REPO_STUDY_V2.md`, Cluster G). `CognitiveExtension` is that pattern, one layer up: a `describe()` ("Find") half and a `reason()` ("Call") half.

**Illustrative shape** (fields only, not a frozen schema — matching K4 §6's own convention for `ExecutionPlan`):

```text
CognitiveExtension (Protocol — structurally satisfied, not inherited):
    resource_id:      str   # identity, per the K1.6 Resource convention
    name:              str
    version:           str   # Law of Contract Stability
    domain_scope:      str   # free-form/structured descriptor, used for delegation matching
    lifecycle_state:   str   # registered -> active -> degraded -> deprecated (own enum, per K1.6 §4)
    trust_status:      str   # reuses the existing unknown->candidate->verified->conflicted->deprecated
                              # Truth Framework -- not a new one (see below)
    dependencies:      list[str]   # declared Capability/Kernel-service needs, least privilege

    async def describe(self) -> ExtensionDescriptor: ...   # the "Find" half
    async def reason(self, subgoal, context_view) -> CognitiveArtifact: ...  # the "Call" half
    async def health(self) -> HealthStatus: ...
```

Precision that a closed set of named contracts would have offered — e.g., "a Discovery-shaped result looks like X" — is not lost; it moves to `domain_scope` plus whatever concrete Cognitive Artifact subtype (§8) a given Extension chooses to mint. That is per-Extension precision without a closed taxonomy, the same trade K1.6 already made for Resources.

**Relationship to the Kernel's `CapabilityContract`.** Distinct on purpose. A Capability is a unit the Kernel schedules and executes. A `CognitiveExtension` is a reasoning surface the Cognitive Runtime consults and delegates to. An Extension's own effects on the world still flow through ordinary Capabilities, via the seam in §1 — it never gets its own execution path.

**Relationship to the K1.6 Resource Protocol.** `CognitiveExtension` satisfies `Resource` — it has identity, a version, a lifecycle — the same way K1.6 §3 concluded future `CapabilityMetadata` and `Workflow` state would. It is a registered, structural thing, not a reasoning output, which is why it is *not* a Cognitive Artifact (§8 draws that line precisely).

**Trust, not a new mechanism.** `trust_status` reuses the existing Truth Framework rather than inventing a parallel one — the same recommendation already made for skill trust tiers (`OCBRAIN_EXTERNAL_REPO_STUDY.md` §7, item 2, itself citing `sickn33/antigravity-awesome-skills`' risk-tiering). This matters concretely here, because this session's brief names "Community-developed runtimes" and "User-created runtimes" among future Extension sources — exactly the third-party-content case the Truth Framework and `SkillSpector`-style pre-registration scanning (`OCBRAIN_EXTERNAL_REPO_STUDY.md` §1, "Adopt Immediately") already have an answer for. An Extension is not exempt from LAW 1 or LAW 3 for being a reasoning module rather than code — registration into `ACTIVE` should require the same validation discipline already recommended for Skills, and every consequential effect an Extension leads to still executes inside the Kernel's existing sandboxing (PI §14.1), because it reaches the world through the same seam every other action does.

**Extension Admission Test.** Structurally modeled on the Kernel's own three-gate Admission Test (Constitution Part V), not a new invention, to prevent this layer from acquiring its own scope-creep problem:

- *Gate 1 — Necessity:* Does this genuinely require judgment about a distinct domain — not just execution of a well-defined task? Could the core Cognitive Runtime's existing components (Planner, Reflection, Evaluation, Supervision) reasonably absorb it as a general capability instead?
- *Gate 2 — Placement:* Could this be satisfied by an ordinary Kernel Capability or Skill? Could it be satisfied by extending an *existing* Extension's declared scope rather than minting a new one?
- *Gate 3 — Durability:* Will this still be a coherent, distinct reasoning domain in ten years, or is it a narrow, temporary need better served as a Skill?

---

## 6. CognitiveContext — *Deliverable 4*

**Should it exist? Yes**, for three reasons: K4 §10 already established the need for the core pipeline under the name "Working Cognitive State"; inventing a second, parallel concept for Extension-visibility would violate Law of Single Source of Truth; and without it, Extensions would either need raw access to Planner/Reflection's internals (violating Separation of Concerns) or would have to reconstruct context from Memory searches on every delegation, losing exactly the in-flight, not-yet-promoted artifacts that are the point of having a working context at all.

**Naming.** This document adopts **`CognitiveContext`** — the term this session's brief uses — as canonical going forward, superseding "Working Cognitive State" as a label (K4 §10's content is otherwise unchanged; nothing about ownership, scope, or contents is redesigned here). The rename is justified, not cosmetic churn: "Working Cognitive State" was scoped narrowly to the core pipeline in K4 §10; now that Extensions need controlled visibility into it, a name shared with this document's own vocabulary keeps one concept under one name rather than two names quietly drifting apart across documents.

**Ownership.** The core Cognitive Runtime, exclusively — nothing else may write to it, including any Extension (see Invariant 6, §10).

**Lifecycle.** Per-request: created when Intent Interpretation begins, discarded when Response is assembled. This is a different lifecycle than the Cognitive Runtime's own service-level one (§7) — request-scoped state versus process-scoped service, mirroring the split K1.5 §1.2 already drew between "Kernel State" and "Runtime State" one layer down.

**Mutability.** Append/overwrite freely during the request, by the owning core Cognitive Runtime only; immutable to everything else once written, matching K4 §10's existing rule.

**Persistence.** None by default — `CognitiveContext` has no `search()` method and no storage path of its own, same as K4 §10 established. Only specific artifacts it holds get individually written through `UnifiedMemory.write()` when Reflection or Evaluation decide they're worth keeping.

**Cleanup.** Unconditional at request end, plus LRU eviction pressure, mirroring `WorkerContext.working_memory`'s established pattern (K1.5 §6).

**Contents.** Unchanged from K4 §10: the current Intent, the current Goal, the in-progress or most recent ExecutionPlan, the most recent EvaluationRecord/ReflectionRecord for this request.

**Extension visibility — the one genuine extension to K4 §10.** Extensions never receive the raw, mutable `CognitiveContext`. They receive a scoped, read-mostly **projection** — illustratively, a `CognitiveContextView` — carrying only what's relevant to the delegated sub-Goal. This reuses the exact discipline K1.6 already established for `KnowledgeEntry` → `Context`/`ContextBlock` ("deliberately does NOT embed a raw KnowledgeEntry... independent of storage implementation"), applied one layer up: a projection, never an embedded live reference. It is also the same shape `PrimisAI/nexus`'s per-entity scoped replay validated externally — restoring or exposing only the turns relevant to one entity, not the whole state (`OCBRAIN_EXTERNAL_REPO_STUDY_V2.md`, Cluster D).

**Resource classification.** `CognitiveContext` does **not** satisfy the `Resource` Protocol — no persistence-worthy identity, no lifecycle beyond one request. It stays in K1.6's "ephemeral parameter object" category, alongside `WorkerContext`, one layer up.

---

## 7. Runtime Lifecycle — *Deliverable 5*

**Should the Cognitive Runtime have its own lifecycle, separate from `CognitiveContext`'s per-request one? Yes, but minimal.** The justification is narrow and concrete: because Extensions can be registered, become unreachable, or fail independently (Failure Containment, Constitution Law 11), the Cognitive Runtime needs *some* notion of "am I accepting requests" that is not itself gated by any single Extension's availability — the core pipeline (Intent Interpreter, Planner, Plan Compiler, Reflection, Evaluation, Supervision) has zero mandatory dependency on any Extension being present, and its lifecycle must reflect that.

**States** (three, deliberately not four — see below):

| State | Meaning | Transition in | Transition out |
|---|---|---|---|
| `INITIALIZING` | Extension Registry populating at composition-root time; no Intent accepted yet | Process start | Registry population completes |
| `READY` | Accepting Intent; the core pipeline runs regardless of how many registered Extensions are currently reachable | `INITIALIZING` completes | Shutdown signal |
| `SHUTTING_DOWN` | No new Intent accepted; in-flight `CognitiveContext`s drained via the existing `cancellation_token` mechanism (K1.5 §4) — no second cancellation mechanism | `READY` + shutdown signal | Process exit |

**Why no `DEGRADED` state.** A fourth, explicitly-tracked "degraded" state was considered and rejected: degradation is a property of *individual Extensions*, tracked per-Extension via `health()` (§5), not a property of the Cognitive Runtime as a whole. Making it a top-level state would either (a) require some arbitrary threshold of Extension unavailability to trigger it, inventing a rule with no evidence behind it, or (b) tempt the core pipeline into treating Extension unavailability as something that gates its own readiness — the opposite of what Failure Containment requires. Composed, per-Extension health is queryable without needing a fourth state.

**Ownership.** The composition root constructs and owns the Cognitive Runtime's lifecycle state, the same place `main.py` already owns `GovernanceKernel`/`EventStream` construction today (K1 §1.1).

**Invariants.** No Intent is accepted before `READY`. Extension unavailability, alone, never transitions the Cognitive Runtime out of `READY`. Transition to `SHUTTING_DOWN` drains via the existing cancellation mechanism only.

---

## 8. Cognitive Artifacts — *Deliverable 6*

**"Cognitive Artifact" is established here as a named specialization of the K1.6 Resource Protocol** — the shared shape every output of Cognitive Runtime reasoning (core or Extension) must satisfy. This is the piece that makes the Extension Model tractable: without a shared shape, every future Extension would invent its own bespoke output type with no common contract for explainability, provenance, or promotion into Memory to build against.

**Shared shape** (illustrative, not a frozen schema):

```text
CognitiveArtifact (a specialization of the K1.6 Resource Protocol):
    resource_id:      str
    produced_by:       str        # which Runtime or Extension minted it -- Invariant 3, §10
    derived_from:      list[str]  # provenance chain, reusing KnowledgeEntry.derived_from's
                                    # existing convention (K4 §7)
    lifecycle_state:   str        # draft -> final -> superseded; domain-specific per concrete type
    # concrete subtypes add their own fields on top of this shared shape
```

**Known initial members, per this session's own list:** Intent, Goal, ExecutionPlan, ReflectionRecord, EvaluationRecord. Their detailed field-level design remains exactly where the renumbered roadmap (§0) already puts it — K4.2 for Intent/Goal/Planner's ExecutionPlan output, K4.4 for Reflection/EvaluationRecord — this document commits only to the shared shape above, not to finishing their design early.

**The category stays open.** A future Extension may mint a wholly new Cognitive Artifact subtype — a hypothetical Discovery Runtime's "DiscoveryReport," a hypothetical Knowledge Runtime's "KnowledgeGraphDelta" — without any change to the core Cognitive Runtime's code, as long as it satisfies the shared shape above. This is the direct artifact-layer analog of MetaGPT's "typed artifact flow" pattern, already flagged as valuable in the research corpus (`OCBRAIN_FUTURE_ARCHITECTURE.md`, Domain A): each producer emits a typed artifact that becomes the next consumer's input, never unstructured text passed hand to hand.

**What stays out of the category, on purpose.** `Evidence`, `Context`, `ContextBlock`, and `ProvenanceRecord` remain the wrapper/projection types K1.6 §3 deliberately excluded from the Resource Protocol. A Cognitive Artifact may *reference* them by ID (an ExecutionPlan citing the Context it was planned against) but never embeds them — the same identity-by-reference discipline K1.6 §6 already made a standing rule.

---

## 9. The Extension Model — *Deliverable 7*

**Discovery and registration.** Mirrors the existing `CapabilityRegistry` population pattern exactly (K1.5 §5): Extension implementations satisfying `CognitiveExtension` register into an **Extension Registry** at composition-root time, the same moment Capabilities and Workers are registered today. Hot-reloading or dynamic runtime registration is explicitly not designed here — consistent with this session's own "do not implement placeholder versions" instruction, and with K1.5 §5's identical deferral for Capability hot-reload ("a Cognitive Phase concern that consumes a stable registry, not something the registry itself needs to support yet").

**Invocation.** Reuses `ExecutionRuntime`/`WorkflowRuntime` — no new Kernel mechanism, per §1. Concretely: an Extension is invoked asynchronously (matching the codebase's async-first convention throughout), honors the same `cancellation_token` propagation already established (K1.5 §4), and its invocation is itself subject to the same budget/recursion governors as any other nested reasoning step — an Extension delegating to another Extension, or reasoning at unbounded length, is exactly the uncontrolled recursive pattern `RecursionGovernor` already exists to prevent (PI §6.2), and nothing here exempts Extensions from it.

**Delegation.** During Planning (or during Supervision's failure-recovery reasoning, K4 §9), the core Cognitive Runtime recognizes a sub-Goal whose domain matches a registered Extension's `domain_scope`, hands that sub-Goal off along with a scoped `CognitiveContextView` (§6), and receives back a Cognitive Artifact (§8) that folds into the reasoning already in progress. This is deliberately left as part of Planner's own (already LLM-assisted, per K4 §5) reasoning rather than a separate matching service — a separate "Extension Orchestrator" was considered and rejected, since Planner (at plan time) and Supervisor (at recovery time) already cover the two moments delegation is needed, and a third component would duplicate authority (the same reasoning K4 §3 already used to reject a standalone Decision Engine).

**When more than one Extension could plausibly handle a sub-Goal**, this document does not introduce a new Resolver. Planner already produces `alternatives` and `confidence` on its `ExecutionPlan` output (K4 §5–6); ambiguity about which Extension to consult is handled the same way any other planning ambiguity is — as parallel candidate sub-plans, with Evaluation later determining which performed better — rather than inventing a health/cost/latency-ranked Extension Resolver on the `CapabilityResolver` model before there is any evidence multiple competing Extensions of the same domain will actually exist. This is a deliberate lean, not a settled answer; §13 flags it explicitly for K4.2 to confirm or override.

**Illustrative walkthrough** (Skill Runtime is not designed here — this is a worked example to make the mechanism concrete, nothing more). Say a future Skill Runtime Extension exists, satisfying `CognitiveExtension`, with `domain_scope` covering "skill creation, evolution, and validation." Planner, decomposing a Goal, recognizes a sub-Goal like "no existing Capability satisfies this Task well" and delegates it to Skill Runtime's `reason()`, passing a scoped `CognitiveContextView`. Skill Runtime's own internal reasoning — out of scope here, but this project's own research corpus already has a design for it, Microsoft SkillOpt's validation-gated textual edit algorithm, already flagged as the primary mechanism for v4.3.9 Instinct→Skill Learning (`OCBRAIN_EXTERNAL_REPO_STUDY.md` §1, §8) — produces a Cognitive Artifact: a candidate Skill definition. That artifact still requires `EvaluatorWorker` approval and a `GovernanceKernel` evaluation before it becomes a real, registered Kernel Capability. **Nothing about `CapabilityRegistry` or `WorkflowRuntime` changes to support this.** A new Capability enters exactly the way any Capability enters today, through governed registration — only its proposal now originates from delegated cognitive reasoning instead of a human hand-authoring a `.skill.md` file.

**Proposing versus registering.** Generalizing the walkthrough: Extensions may *propose* new Kernel Capabilities; they may never *register* one directly. Registration remains Kernel-owned and governed, consistent with Invariant 8 of the Constitution ("recommendations sourced from outside a single instance are never self-executing") applied to recommendations sourced from *inside* the instance but outside the Kernel's own trust boundary.

**How entirely new runtime categories get added without redesign — the concrete answer.** Adding a wholly new category — Simulation Runtime, Creativity Runtime, anything not yet named — requires exactly three things: (1) an implementation structurally satisfying `CognitiveExtension`, (2) registration into the Extension Registry at composition-root time, (3) a `domain_scope` descriptor precise enough for Planner's delegation logic to find it. None of the three touches the core Cognitive Runtime's own code, the Kernel, or any other Extension. That is the mechanical content of "closed for redesign, open for extension."

**Explicitly rejected, with reasons:**
- *A dedicated Extension Orchestrator, separate from Planner/Supervisor* — duplicated authority; rejected above.
- *A separate Extension event bus, parallel to the existing `cognitive.*` namespace (K4 §12)* — would reopen the exact "two full stacks, one disconnected" failure this project has already hit twice (K1.5 §0); Extensions emit through the same worker-lifecycle event path every existing worker already uses.
- *Hot-reload / dynamic runtime registration* — no evidence yet justifies the added complexity; deferred per Law of Evidence over Assumption, same treatment K1.5 §5 already gave Capability hot-reload.
- *A closed enum of Extension domains* — directly contradicts the openness this session's brief requires; `domain_scope` is a descriptor, not a fixed set of tags.

---

## 10. Architectural Invariants — *Deliverable 8*

Terse, in the style of Constitution Part IV — properties that must hold, not principles about what things are.

1. **Reasoning never executes.** The Cognitive Runtime and every registered Extension may only produce Cognitive Artifacts; only the Kernel, via `WorkflowRuntime`/`ExecutionRuntime`/`AdapterRuntime`, executes anything with real-world effect.
2. **Execution never reasons.** A compiled `WorkflowDefinition` is fixed; nothing at execution time originates a new Goal or plan. A step that reveals the need for more reasoning returns control to Supervisor, which requests a new planning cycle — it does not reason in place.
3. **Every real-world effect flows through exactly one seam:** Plan Compilation → `WorkflowDefinition` → Kernel execution. No Extension is granted, or may construct, a second door into `WorkflowRuntime`.
4. **The Cognitive Runtime never hardcodes knowledge of a specific Extension's identity or type.** Its code references the `CognitiveExtension` contract only; an Extension's presence or absence must never require a matching code change in the core Cognitive Runtime.
5. **The Cognitive Runtime never bypasses Governance, including on an Extension's behalf.** Every consequential action an Extension's reasoning leads to — a proposed Capability, a memory write, a plan compilation — re-enters through `evaluate_action()` exactly as any other action does.
6. **A `CognitiveContext`, or a scoped projection of one, is visible only for the duration of the request that created it.** No Extension, and no component of the core Cognitive Runtime, retains a reference past that boundary.
7. **Every delegation from the core Cognitive Runtime to an Extension is itself explainable** — which Extension was invoked, why, and what it returned are first-class facts in the artifact trail, never an untracked implementation detail.
8. **A failing, unavailable, or low-trust Extension degrades capability in a bounded, describable way.** It never blocks or fails reasoning that doesn't depend on it — Constitution Law 11 (Failure Containment), one layer up.
9. **No single Extension, current or future, is load-bearing for the Cognitive Runtime's own definition of itself** — direct mirror of Constitution Invariant 9, one layer up.

**Reconciliation with K4 §16.** Invariants 1, 2, and 5 above generalize K4 §16's "planning never executes," "execution never plans," and "the Cognitive Runtime never bypasses Governance" from the core pipeline to the whole Cognitive Runtime, Extensions included. K4 §16's remaining invariants — every plan has a goal, goal provenance to intent, non-mutation of execution history by Reflection, no fact-changing by Evaluation, no silent retry of a rejected plan — are pipeline-specific refinements that still hold unchanged once K4.2–K4.6 build the components they govern.

---

## 11. ADR Candidates — *Deliverable 9*

Enumerated only, per instruction.

1. **ADR-K4.1-01** — Cognitive Runtime Extensions require no new Kernel-facing execution mechanism; they compose through the existing Plan Compilation seam (§1, §9).
2. **ADR-K4.1-02** — `CognitiveExtension` is a single generic Protocol, not a closed set of per-domain contracts (§5).
3. **ADR-K4.1-03** — `CognitiveContext` is the canonical rename of K4 §10's Working Cognitive State, extended to be Extension-visible via scoped, read-mostly projections only (§6).
4. **ADR-K4.1-04** — The Cognitive Runtime's service-level lifecycle (three states, degradation computed per-Extension rather than tracked as a fourth top-level state) is distinct from `CognitiveContext`'s per-request lifecycle (§7).
5. **ADR-K4.1-05** — Cognitive Artifact is established as a named specialization of the K1.6 Resource Protocol; Extensions may mint new artifact subtypes without core-Cognitive-Runtime changes (§8).
6. **ADR-K4.1-06** — Extensions may propose but never directly register new Kernel Capabilities; proposals route through existing governance/approval paths (§9).
7. **ADR-K4.1-07** — Extension trust reuses the existing Truth Framework and `SkillSpector`-style pre-registration validation rather than a parallel mechanism (§5).
8. **ADR-K4.1-08** — An Extension Admission Test, structurally modeled on Constitution Part V, gates what qualifies as a legitimate new Extension category versus an ordinary Capability or Skill (§5).

---

## 12. Future Documentation — *Deliverable 10*

Recommended only, each gated on a precondition — not created now, per the same discipline the Pressure Test already applied to premature document types (`OCBRAIN_KERNEL_CONSTITUTION_PRESSURE_TEST.md` §9).

1. **Cognitive Runtime Constitution** — once K4.2–K4.7 have shipped and survived real implementation contact. Drafting it now would repeat the exact timing risk the Kernel Constitution's own self-critique already named (principles encoded ahead of practice).
2. **`CognitiveExtension` Protocol Reference** — once the first real Extension exists. K1.6's own Interface Freeze rule applies unchanged: not frozen before anything has used it.
3. **Cognitive Artifact Schema Reference** — once K4.2–K4.4 fix concrete field sets for Intent, Goal, ExecutionPlan, ReflectionRecord, and EvaluationRecord.
4. **Extension Authoring Guide** — once the first real Extension is built, most plausibly Skill Runtime or Discovery Runtime given their direct connection to already-adopted research (SkillOpt; the Skill_Seekers-style acquisition pipeline).
5. **No new ADR-log document type.** The candidates in §11 belong in the existing `ARCHITECTURE_DECISIONS.md` mechanism (PI §18.4.2/§18.5) — inventing a separate one would repeat what the Pressure Test already rejected once.

---

## 13. Closing Assessment

The renumbering collision in §0 is the one factual issue worth carrying forward with weight — not because it blocks anything here, but because new-K4.2's exact scope (does it own ExecutionPlan-the-artifact, or does new-K4.3?) is currently undecided rather than designed, and undecided-by-drift is exactly the failure mode this project's documentation discipline exists to prevent.

Two things in this document are judgment calls, not settled conclusions, and are named as such rather than smoothed over: how Planner's delegation-matching actually decides "this sub-Goal belongs to Extension X" is deliberately left to K4.2, since designing it here would mean designing Planner, which is out of scope; and leaning on Planner's existing `alternatives`/`confidence` machinery to handle multiple candidate Extensions, rather than building a dedicated Resolver, is a minimal choice made in the absence of evidence that competing same-domain Extensions will actually be common — K4.2 should either confirm this or override it deliberately, not inherit it by default.

On sequencing: no further pure-design pass is recommended before K4.2. The same judgment call was made once already in this project's own history — K1.6 §8 found that a proposed multi-session design sequence (K1.7–K1.11) was mostly redundant with work already done, and that implementation contact was a better source of the next real question than continued paper review. Nothing in this session changes that lesson; if anything, the foundation above is narrower and more mechanically settled (one seam, one contract, one artifact category) than K1.6's own starting point was. Recommend K4.2 proceed next, with the two flagged judgment calls decided explicitly in that session rather than left implicit.

---

*K4.1 complete. No implementation performed, no Kernel files modified, no Extension built or named beyond the illustrative walkthrough in §9. Ready for K4.2 (Intent Interpretation / Goal Formation / Planner, per the renumbered roadmap in §0) once the two open items in this section are either resolved or deliberately deferred.*
