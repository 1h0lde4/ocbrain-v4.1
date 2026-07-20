# OCBrain K4.1 — Cognitive Runtime Layer Architecture
## Consolidated and Authoritative

**Date:** July 19, 2026
**Status:** Architecture Only. Zero code, zero implementation, zero repository modifications, zero interface freezing, zero placeholder APIs.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md`, `PROJECT_INSTRUCTIONS.md`, and K4 (`OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md`), whose own component design — Intent Interpreter, Planner, Plan Compiler, ReflectionWorker, EvaluatorWorker, SupervisorWorker as the fixed core — is inherited here, restated for completeness, and not redesigned.
**Supersedes, in full:** `OCBRAIN_K4_1_COGNITIVE_RUNTIME_FOUNDATION.md`, `OCBRAIN_K4_1_COGNITIVE_SERVICE_ARCHITECTURE.md`, `OCBRAIN_K4_1_RECURSIVE_SERVICE_COMPOSITION.md`, `OCBRAIN_K4_1_X_DELEGATION_ARCHITECTURE_AUTHORITATIVE.md`. All four should be archived once this is accepted — see Part XIII. This document does not reference them section-by-section; it states the current, final architecture directly, as if written once.

---

## Part 0 — Preface

This is a consolidation, not a fifth addition. Four prior documents designed this layer incrementally — a foundation, then a rename from Extensions to Services with a richer discovery mechanism, then recursive composition, then a policy/mechanism separation fixing a God-Object risk in the delegation mediator. Each was correct as far as it went, and each was also partial: terminology drifted (Extension → Service), a component was renamed twice (CognitiveServiceRuntime → DelegationEngine), and invariants were revised in place three times. Reading them in sequence shows the reasoning; reading them together, as source material for one document, shows a few places where the reasoning can be stated once, cleanly, and a few places worth re-examining with fresh eyes now that the whole shape is visible at once. Part IX records what that re-examination actually found — some things confirmed, one or two things sharpened, nothing overturned.

**What's inherited unchanged from K4, not re-derived:** the core pipeline's component list, the Working-Cognitive-State-turned-`CognitiveContext` per-request lifecycle rules, the `cognitive.*` event namespace, the reuse of `KnowledgeEntry.procedure_name`/`layer="l3"` for promoted plans. These are stated where needed for completeness but are K4's decisions, not reopened here.

---

## Part I — Governing Principle and Identity

**Governing principle, stated once because it turns out to govern everything below it:** *judgment and mechanism are never the same component.* This repeats at every layer already built in this system, and this document's own central fix (Part V) is one more instance of a pattern, not a new idea — a Worker's governance-evaluation-then-`_run()`, a Plan's Planner-decides-then-Plan-Compiler-translates, a Delegation's decide-then-approve-then-execute. Nothing in the Cognitive Runtime both decides whether an action is permitted and carries it out.

**The Cognitive Runtime.** The layer that decides what should happen; the Kernel is the layer that makes what's decided actually happen, safely, governed, and replayably (K4 §1, unchanged). It begins at Intent Interpretation — the raw request an Application hands it is not yet a first-class artifact; Intent Interpretation is what produces one. It ends at Response synthesis; delivery is interface-layer plumbing outside both layers.

**Owns:** intent interpretation, goal formation, planning, plan compilation (translation, not execution), reflection, evaluation, supervision, and coordinating delegation to registered Cognitive Services.
**Never owns:** memory persistence, governance policy of any kind, workflow/capability execution, event persistence, a Service's internal reasoning, or knowledge of a specific Service's identity or category — in code or in reasoning templates.

**Terminology, settled once.** What used to be called a "Cognitive Runtime Extension" is a **Cognitive Service** — the rename removed a real, not merely cosmetic, asymmetry (an "Extension" implies something bolted onto a base system; the Kernel's own `UnifiedMemory`-with-swappable-`StorageBackend`s precedent, worked through in full in Part III, shows the correct shape is a fixed core with a genuinely generic, symmetric periphery). One disambiguation rule, stated once: K1.5 already uses bare "Service" for Kernel-layer coordination components (`GovernanceService`, `EventService`, etc.). Unqualified "Service" always means that. This layer's concept is always written in full — "Cognitive Service."

---

## Part II — The Cognitive Pipeline

Inherited from K4; restated at the level of detail this document needs for completeness, not redesigned.

**Intent Interpretation.** Raw request → `Intent` (a Cognitive Artifact, Part IV). Genuinely separate from Goal Formation, not a phase of it — see Part IX for why this survives fresh scrutiny.

**Goal Formation.** `Intent` → `Goal`, the verified, disambiguated target state. Separate from both Intent Interpretation (verification is a distinct act from parsing) and Planning (a Goal is not yet a plan).

**Planner.** `Goal` → `ExecutionPlan`: decomposition, capability selection (via the Kernel's existing `CapabilityRegistry.resolve()`, unmodified), Cognitive Service delegation-matching (Part III), sequencing, confidence and alternatives. Planner reasons; it never executes, never discovers new capabilities on its own authority, never installs, never manages memory directly.

**Plan Compiler.** `ExecutionPlan` → `WorkflowDefinition` — the Kernel's own existing execution contract. The one-directional seam that makes "planning never executes" structural rather than conventional: `WorkflowDefinition`s never compile back into `ExecutionPlan`s. Gated by governance before it produces anything (Part V).

**Architecturally-distinct, not necessarily three separate calls.** These three stages are three distinct *responsibilities*, each producing its own artifact with its own identity and provenance (`Goal.derived_from` cites the `Intent` it verifies, per the Cognitive Artifact shape in Part IV) — this is an architecture-level claim. Whether one implementation later does intent-parsing and goal-verification in a single LLM call is an *implementation* question the Constitution's own Part VIII already reserves for below this layer. Collapsing the architectural distinction would remove the ability to reuse, replace, or independently evolve any one of the three without touching the others — the same reason Plan Compiler stays separate from Planner.

**Full flow, stated once:**

```text
User Request
     │
     ▼
Intent Interpretation  →  Intent
     │
     ▼
Goal Formation  →  Goal
     │
     ▼
Planner  →  ExecutionPlan  (may delegate sub-goals — Part V)
     │
     ▼
GovernanceKernel.evaluate_action(action_type="plan_compile")
     │
     ▼
Plan Compiler  →  WorkflowDefinition
     │
     ▼
Kernel execution (WorkflowRuntime → ExecutionRuntime → AdapterRuntime)
     │
     ▼
Reflection / Evaluation  →  ReflectionRecord / EvaluationRecord   (K4.4, future)
     │
     ▼
Response
```

---

## Part III — Cognitive Services

**The contract.** One generic Protocol, structurally satisfied, never inherited — not six or sixteen named contracts. Any closed set requires the core Cognitive Runtime's own code to know category names in advance, which is precisely what "closed for redesign, open for extension" forbids.

```text
CognitiveService (Protocol):
    resource_id:      str
    name:              str
    version:           str
    profile:           ServiceProfile
    lifecycle_state:   str    # registered -> active -> degraded -> deprecated
    trust_status:      str    # reuses the existing Truth Framework
    dependencies:      list[str]

    async def describe(self) -> ServiceProfile: ...  # "Find"
    async def reason(self, subgoal, context_view) -> CognitiveArtifact: ...  # "Call"
    async def health(self) -> ServiceHealth: ...
```

**Discovery — `ServiceProfile`.** A single free-form `domain_scope` string cannot carry what discovery actually needs; the dimensions are independent, so the fields are independent:

```text
ServiceProfile:
    description:  str         # free text — the primary matching substrate
    accepts:       list[str]   # open-ended goal/task-shape tags, never a closed enum
    produces:      list[str]   # Cognitive Artifact subtype(s), same vocabulary as Part IV
    requires:      list[str]   # CognitiveContext/Capability needs, feeds context scoping
    examples:      list[str]   # optional, for few-shot matching
```

Matching is Planner's own reasoning (already LLM-assisted for decomposition), applied to registered profiles — not a new "Matcher" component, which would either duplicate Planner's semantic judgment or require a second, disconnected reasoning path. Operational signal (cost, latency, calibration track record) lives in `health()`, not the static profile — it changes continuously and would stale-date a registration-time description. When more than one service plausibly matches, Planner's existing `alternatives`/`confidence` mechanism handles the ambiguity; no dedicated Resolver exists for this, by the same reasoning that avoided a dedicated Matcher.

**Registry.** A static index, populated at composition-root time — mirrors the Kernel's own `CapabilityRegistry` population exactly. Hot-reload is explicitly not designed; no evidence yet justifies it.

**Service Admission Test** — a registration-time, one-time question, modeled structurally on the Kernel's own three-gate Admission Test (Constitution Part V): Necessity (does this genuinely require domain judgment, not just execution of a defined task), Placement (could an existing service's scope, or an ordinary Capability, satisfy this instead), Durability (a coherent domain in ten years, or a narrow need better served as a Skill).

**Invocation eligibility** is a different, smaller question — is *this specific, already-admitted* service *currently* fit to be invoked (its `lifecycle_state` is `active`, its `trust_status` clears whatever bar applies) — evaluated every call, as part of the same governance gate every delegation passes through (Part V), not a second admission ceremony.

**Trust.** Reuses the existing Truth Framework (`unknown → candidate → verified → conflicted → deprecated`) rather than a parallel mechanism — third-party, community-developed, user-created, and AI-generated services all register at whatever status a new, unverified entry gets, and all execute inside the same sandboxing regardless of origin.

---

## Part IV — Context and Artifacts

**`CognitiveContext`** (the canonical name; superseded name was "Working Cognitive State"). Owned exclusively by the core Cognitive Runtime. Per-request lifecycle: created at Intent Interpretation, discarded at Response assembly. Mutable only by its owner, immutable to everything else. No `search()` method, no persistence of its own — only specific artifacts it holds get individually written through `UnifiedMemory.write()` when Reflection or Evaluation judge them worth keeping. Holds the current Intent, Goal, in-progress or most recent `ExecutionPlan`, most recent `ReflectionRecord`/`EvaluationRecord`. Does not satisfy the Resource Protocol (K1.6) — no persistence-worthy identity, no lifecycle beyond one request; it stays in the same "ephemeral parameter object" category as `WorkerContext`.

**`CognitiveContextView`.** What a Cognitive Service actually receives — never the raw `CognitiveContext`. A scoped, read-mostly projection, built from the target's declared `requires`, carrying one field beyond what `CognitiveContext` itself holds: `delegation_chain: list[str]` — a projection of the Kernel's own `ExecutionContext.causal_chain`, extended by one entry per delegation hop. This reuses the exact "projection, never a raw reference" discipline K1.6 established for `KnowledgeEntry` → `Context`/`ContextBlock`, one layer up.

**Cognitive Artifact.** The shared output shape for anything the Cognitive Runtime or a Service produces — a named specialization of the Resource Protocol:

```text
CognitiveArtifact (specializes Resource, K1.6):
    resource_id:      str
    produced_by:       str        # which Runtime component or Service minted it
    derived_from:      list[str]  # provenance chain, KnowledgeEntry.derived_from's convention
    lifecycle_state:   str        # draft -> final -> superseded, domain-specific per subtype
```

Known members: `Intent`, `Goal`, `ExecutionPlan`, `ReflectionRecord`, `EvaluationRecord` — field-level design for each stays with whichever K4.2+ milestone owns it (Part X). The category is explicitly open: a Service may mint a new subtype without any change to the core Cognitive Runtime, as long as it satisfies the shape above; a `ServiceProfile.produces` entry names a subtype from this same vocabulary, not a separate taxonomy. `Evidence`, `Context`, `ContextBlock`, and `ProvenanceRecord` are deliberately **not** Cognitive Artifacts — K1.6 already excluded them from the Resource Protocol on purpose, and that exclusion is preserved here without re-argument.

---

## Part V — Delegation Architecture

**The full pipeline, the single form used at every depth:**

```text
Planner  or  [a Cognitive Service, mid-reason()]
      │  decides WHAT to delegate — Planner's or a Service's own reasoning
      ▼
GovernanceKernel.evaluate_action(action_type="service_delegation", ...)
      │  ONE call — the same Template Method every governed action in the
      │  system already uses. Internally may consult RecursionGovernor
      │  (depth), OrchestrationGovernor (cycle-freedom), AgentGovernor
      │  (trust/admission), BudgetGovernor (spend). REJECT/ESCALATE
      │  short-circuits here, exactly as everywhere else.
      ▼  (approved)
DelegationEngine — mechanism only, zero policy logic
      │  build CognitiveContextView (+ delegation_chain), emit
      │  cognitive.service_delegated
      ▼
ExecutionRuntime.invoke(...) — Kernel, unchanged
      ▼
[Target Service].reason(...)  →  CognitiveArtifact
      │
      └── returned to caller; the caller (Planner or a Service) may issue
          a further delegation request through the identical path —
          recursion is not a special case, it is the same call re-entered
```

**`DelegationEngine`** (superseded names, in order: `CognitiveServiceRuntime`, briefly). Lives in the Cognitive Runtime layer, alongside Planner and Plan Compiler — not registered, not swappable, not a Resource. Its entire job, once policy was removed: accept an already-approved request, construct the scoped context, emit the event, invoke, return the artifact. "Engine" rather than "Runtime" tracks a real change, not a relabeling — once it does zero deciding, "Runtime" (which connotes a hosting, stateful system) overstates what's left; "Engine" (a narrow, repeatable transformation) is accurate. It calls the Kernel's `ExecutionRuntime`; it is not part of the Kernel, and nothing about the Kernel's frozen ownership of workflow/capability execution changes.

**Governance integration — the policy/mechanism split.** A working test, applied once to settle every case rather than argued per-item: **Policy** answers "is this allowed" and can be evaluated from context alone, without performing the action — it lives in `GovernanceKernel`, as a Governor. **Mechanism** answers "how is this carried out, once approved" — it lives in `DelegationEngine`. **Operational signal** answers "is this likely to succeed right now" — it doesn't gate permission, it informs the reasoning that picks a target; it lives in `health()`.

| Concern | Bucket | Home |
|---|---|---|
| Recursion depth | Policy | `RecursionGovernor` (existing) |
| Cycles | Policy | `OrchestrationGovernor` — named in `PROJECT_INSTRUCTIONS.md` §6.1, one of two governors K1's audit found still unbuilt; this is its first concrete use case, not a new governor invented for this purpose |
| Trust / invocation eligibility | Policy | `AgentGovernor`'s "permission matrix" scope — also named, also unbuilt; placement only, mechanics deferred (below) |
| Budget | Policy | `BudgetGovernor` (existing) |
| Health / cost / latency | Operational signal | `CognitiveService.health()`, feeds Planner's/a Service's own reasoning, never a hard gate |
| Priorities, scheduling | Policy, future slot | No evidence of need yet — reserved under `OrchestrationGovernor`, not designed |
| Enterprise restrictions, licensing, tenancy | Rejected for now | See below |

**On enterprise/licensing/tenancy, stated plainly.** Nothing in this project's stated identity — local-first, not a product, not a cloud service (Constitution Part I, Part VI) — supports building these now. A `TenancyGovernor` built against zero real requirements would very likely get the shape wrong, and a wrong speculative design costs more decade-scale stability than not building it, because it would need redesigning the moment real evidence arrived regardless. The architecture's readiness for this is what the Governor-extension pattern already buys: one new Governor, zero change anywhere else, whenever it's actually needed. That's the concrete proof, not an assertion — see Part XI.

**Recursive composition.** Not a special mode — the same pipeline above, re-entered. A Service's own `reason()` call may issue a new delegation request through the identical `evaluate_action()` → `DelegationEngine` → `ExecutionRuntime` path used at the top level, which is why nothing new was needed at the Kernel level: this is the exact nested-execution pattern K1.5 §4 already established `RecursionGovernor` covers for a Worker triggering a sub-workflow, one level deeper. Planner ownership survives recursion precisely because a Service's own delegation requests are *local* — scoped to the sub-goal it was itself assigned — never a second locus of *global* decomposition; the overall Goal, Plan, and compiled `WorkflowDefinition` remain solely Planner's and Plan Compiler's.

**Cycle prevention.** Two mechanisms, complementary: exact chain-membership checking (is the target already present in the caller's `delegation_chain` — immediate rejection, evaluated by `OrchestrationGovernor`) and depth/budget limiting (the necessary backstop for long, non-repeating chains cycle detection alone can't catch).

**Delegation Graph.** Not a new persisted object. The per-invocation `delegation_chain` (a list, correct for its purpose — one invocation's own lineage) and the full session's branching delegation activity (a tree, real, but an *aggregate* of many invocations, not a property of any single one) are different things; the aggregate is a reconstructable *view* over `EventStream`'s `cognitive.service_delegated` events plus `derived_from` provenance chains, not a separately-maintained structure — building one would create a second source of truth for what the event log already holds.

**Trust composition.** A delegation chain's effective trust is the minimum of any member's trust, never the maximum — a principle, placed under `AgentGovernor`'s reserved scope, with enforcement mechanics explicitly not designed: they need real, differently-trusted services to get right, and inventing them now would repeat the exact mistake the enterprise/tenancy rejection above argues against.

**Failure containment.** No new mechanism. A failed delegation resolves to a failed `WorkerResult` at the `ExecutionRuntime` boundary, the same containment every worker invocation already gets. The caller sees a failure, not a crash, and may choose an alternative via Planner's existing `alternatives` mechanism or hand off to Supervisor's retry-via-reinvocation (K4 §9) — both already established, neither reinvented here.

**Explainability.**

| Question | Answered by |
|---|---|
| Why was this service invoked? | `cognitive.service_delegated` payload (subgoal, justification) |
| Which service produced this artifact? | `CognitiveArtifact.produced_by` |
| Which delegation consumed the budget? | `BudgetGovernor`'s tracking, correlated via request id |
| Which service failed? | Worker-failure events, correlated to the delegation event |
| Which service was retried? | A second delegation event, distinguishable by timestamp |
| Which branch produced the final answer? | Reconstructed from `EventStream` + `derived_from` — the Delegation Graph |

---

## Part VI — Runtime Lifecycle

Three states, deliberately not four:

| State | Meaning |
|---|---|
| `INITIALIZING` | Service Registry populating at composition-root time; no Intent accepted |
| `READY` | Accepting Intent; runs regardless of how many registered services are currently reachable |
| `SHUTTING_DOWN` | No new Intent accepted; in-flight `CognitiveContext`s drained via the existing cancellation-token mechanism, no second one |

No `DEGRADED` top-level state: degradation is a property of individual services (`health()`), never of the Cognitive Runtime as a whole — making it a top-level state would either invent an arbitrary threshold with no evidence behind it, or tempt the core pipeline into treating service unavailability as something that gates its own readiness, which Failure Containment forbids.

---

## Part VII — Ownership Boundaries

The full table, assembled once from what had been scattered across four documents' incremental diffs.

| Layer | Owns | Never owns |
|---|---|---|
| **Applications** | Intent capture, response presentation, session/UX state | Any reasoning, execution, or governance |
| **Cognitive Runtime (core)** — Intent Interpreter, Goal Formation, Planner, Plan Compiler, ReflectionWorker, EvaluatorWorker, SupervisorWorker, `DelegationEngine` | Intent/goal/plan production, reflection, evaluation, supervision, mechanical delegation execution | Memory persistence, governance policy of any kind, workflow/capability execution, event persistence, a Service's internal reasoning, which service a delegation targets when the request originates from a Service rather than Planner |
| **Cognitive Services** | Specialized reasoning within one declared, self-described domain; requesting further delegation for a sub-portion of their own assigned reasoning | Kernel execution of any kind, governance enforcement, another service's domain, a second door into `WorkflowRuntime`, direct invocation of another service |
| **`GovernanceKernel`** | All policy evaluation — plan compilation, memory writes, self-modifying curation, and now delegation (recursion, cycles, trust/admission, budget) | Deciding *what* to delegate or *how* to mechanically carry it out |
| **Kernel (Workflow/Execution/Adapter Runtimes, EventStream, `UnifiedMemory`)** | Governance, event durability, memory persistence, workflow/worker/capability execution | Reasoning, planning, goal formation, delegation coordination |
| **Capabilities** | Concrete, schedulable units of work via Adapters | Any judgment about whether or when they run |

---

## Part VIII — Invariants

Renumbered and de-duplicated; several were revised in place across the prior documents, and only the final form appears here.

1. Reasoning never executes — the Cognitive Runtime and every Service may only produce Cognitive Artifacts; only the Kernel executes anything with real-world effect.
2. Execution never reasons — a compiled `WorkflowDefinition` is fixed; a step revealing the need for more reasoning returns control to Supervisor for a new planning cycle.
3. Every real-world effect flows through exactly one seam: Plan Compilation → `WorkflowDefinition` → Kernel execution, or Delegation → `evaluate_action()` → `DelegationEngine` → `ExecutionRuntime` — the same shape, twice, never a third path.
4. The Cognitive Runtime never hardcodes knowledge of a specific service's identity or category — in code or in reasoning templates.
5. The Cognitive Runtime never bypasses Governance, on its own behalf or a Service's — every consequential action re-enters through `evaluate_action()`.
6. A `CognitiveContext`, or a scoped projection of one, is visible only for the duration of the request that created it.
7. Every delegation, at any depth, is itself explainable — which service, why, what it returned.
8. A failing, unavailable, or low-trust service degrades capability boundedly; it never blocks reasoning that doesn't depend on it.
9. No single Cognitive Service is load-bearing for the Cognitive Runtime's own definition of itself.
10. A service is never invoked twice within the same active delegation chain.
11. `DelegationEngine` never evaluates policy of any kind — everything it carries out has already passed `evaluate_action()`.
12. Every delegation-specific policy is expressed as a Governor or a rule inside one — never as conditional logic inside `DelegationEngine`.
13. A component whose own code must change to support a new policy has acquired policy responsibility it shouldn't have — the standing, generalizable test for a future God-Object recurrence, not specific to any one component.
14. A delegation chain's effective trust is the minimum of any member's, never the maximum.

---

## Part IX — Fresh Re-Validation

Answered directly, per the instruction to attempt to invalidate rather than assume.

**Is `DelegationEngine` still the correct abstraction?** Yes. Folding it into Planner would mix judgment and mechanism inside one component — the exact thing Part I's governing principle forbids. Folding it into `ExecutionRuntime` would push a Cognitive-Runtime-layer concept (`CognitiveContextView`) across the frozen Kernel boundary. Its separate existence is what lets the boundary hold.

**Is the Registry correctly scoped?** Yes, unchanged since first designed — nothing since has surfaced a reason to touch it.

**Is recursive composition complete?** Yes, and consolidation is what made this fully explicit: the same single pipeline (Part V) now visibly handles a Planner-initiated delegation and a Service-initiated one identically, which was true across the prior two documents but never stated as one diagram until now.

**Are Governance responsibilities complete?** Complete in *placement* (every policy concern has a named home, existing or reserved), not complete in *mechanism* (trust composition and any future priority/scheduling rules remain undesigned, on purpose — Part V).

**Is `EventStream` still the correct source of truth?** Yes — nothing challenges its Kernel ownership or its role as the reconstruction source for the Delegation Graph.

**Is the delegation graph correctly treated as a reconstructed view?** Yes, re-checked directly: every explainability question in Part V's table resolves without a new persisted structure.

**Are ownership boundaries minimal?** Checked for an orphan — a component or field nothing else references — and none was found. Everything introduced across the four prior documents connects to something else (`ServiceProfile.produces` to the Artifact vocabulary, `delegation_chain` to both cycle detection and scoped context, `CognitiveContextView` to least-privilege invocation).

**Can any component become smaller?** `DelegationEngine` cannot, without losing the layer-boundary role above. Planner's delegation-matching was reconsidered once more and still isn't worth extracting into its own component, for the same reason as before: it's Planner's existing reasoning, applied to one more input source, not a new capability needing its own home.

**Has any God-Object tendency survived?** One worth naming and resolving explicitly: does `GovernanceKernel`, now evaluating recursion, cycles, trust, budget, plan compilation, and memory writes, become the next God Object? No — and the reason is structural, not reassurance. `GovernanceKernel`'s own code doesn't grow with each new policy; it stays a fixed `evaluate_action()` entrypoint dispatching to a *registry* of pluggable Governor classes, exactly the same shape as `CapabilityRegistry` not becoming a "God Registry" as more capabilities register into it. The correct refinement of "every component should become smaller over time" is: a component's own fixed responsibilities should never grow, but the *data or registrations* it manages may grow indefinitely. `DelegationEngine` violated the first half before this consolidation; `GovernanceKernel` never has.

---

## Part X — K4 Roadmap Validation

**K4.2 — Intent Interpretation, Goal Formation, Planner.** Remains three distinct responsibilities (Part II, Part IX). Planner does not absorb either of the other two.

**K4.3 — Plan Compiler, Governance Gate.** Unchanged in scope. Worth designing aware that `OrchestrationGovernor` and `AgentGovernor` are now also live consumers of `evaluate_action()` alongside `action_type="plan_compile"` — same entrypoint, different action types.

**K4.4 — Reflection, Evaluation.** Unchanged in scope. Worth designing aware that "which branch produced this" (Part V's Explainability table) is answered via the Delegation Graph reconstruction — Reflection/Evaluation consumers should assume that reconstruction is available to them, not build a second way to answer the same question.

**K4.5 — Memory Integration.** Unchanged in scope, inherited from K4. Any new Cognitive Artifact subtype a Service mints follows the identical promotion path as `Intent`/`Goal`/`ExecutionPlan` when judged worth keeping.

**K4.6 — Supervisor, Recovery.** Unchanged. Supervisor's retries route through the identical `evaluate_action()` → `DelegationEngine` path as any other delegation, for consistency.

The roadmap needs no adjustment.

---

## Part XI — Future Extensibility

Stress-tested against the decade-scale scenario list directly:

- **Hundreds of services:** Registry and `ServiceProfile` matching don't change shape at any count; only matching cost grows, an already-flagged, evidence-gated future optimization.
- **Third-party, community-developed, user-created, AI-generated services:** all register through the identical contract, all start at whatever trust status a new entry gets, all execute inside the same sandboxing. How a service came to exist doesn't change how it's discovered, delegated to, or governed.
- **Enterprise-only, licensed, or tenant-scoped services, if ever needed:** exactly one new Governor, zero change to `DelegationEngine`, the Registry, `ServiceProfile`, or any existing Governor — the concrete demonstration of the rejection in Part V, not a repeated assertion of it.
- **Cloud vs. local services:** already orthogonal — a service's `reason()` may call cloud-backed Capabilities via the existing Provider Mesh, unrelated to how the service itself is discovered or delegated to.

---

## Part XII — ADR Candidates

Consolidated and de-duplicated from across all four prior documents; superseded intermediate versions (e.g., an earlier ADR naming `CognitiveServiceRuntime`) are not repeated.

1. Cognitive Runtime Extensions/Services require no new Kernel-facing execution mechanism — they compose through the existing Plan Compilation / Delegation seam.
2. `CognitiveService` is a single generic Protocol; "Service" is disambiguated from K1.5's Kernel-layer usage by always being written in full.
3. `CognitiveContext` (renamed from Working Cognitive State) is Service-visible only via scoped, read-mostly `CognitiveContextView` projections.
4. Cognitive Runtime service-level lifecycle (three states) is distinct from `CognitiveContext`'s per-request lifecycle.
5. Cognitive Artifact is a named specialization of the Resource Protocol; Services may mint new subtypes without core changes.
6. Services may propose, never directly register, new Kernel Capabilities.
7. Service trust reuses the existing Truth Framework and Service Admission Test rather than a parallel mechanism.
8. `ServiceProfile` (description/accepts/produces/requires) replaces a single `domain_scope` field; operational signals live in `health()`, not the static profile.
9. Recursive composition is mediated exclusively through the same delegation pipeline used at the top level; direct service-to-service invocation is rejected.
10. "Service stack" is satisfied by projecting the Kernel's existing `ExecutionContext.causal_chain`; no new context object exists.
11. Cycle prevention is an explicit, chain-based Governor check, complementary to depth/budget limiting.
12. `CognitiveServiceRuntime` is renamed `DelegationEngine` and stripped of all policy logic; its sole entrypoint accepts only already-approved requests.
13. Cycle prevention moves to `OrchestrationGovernor`, filling an already-reserved, previously-unbuilt governor slot.
14. All delegation-specific policy, present and future, is expressed as Governors or Governor rules — never as conditional logic inside `DelegationEngine` — a standing invariant, not a one-time decision.
15. The Delegation Graph is a reconstructable view over `EventStream` and `derived_from` chains, never a new persisted object.
16. Enterprise/licensing/tenancy concerns are explicitly deferred pending real evidence; readiness for them is demonstrated via the Governor-extension pattern, not pre-built.
17. Trust composition for delegation chains is placed under `AgentGovernor`'s reserved scope; enforcement mechanics remain undesigned pending real, differently-trusted services.

---

## Part XIII — Supersession and Closing Assessment

**What this replaces.** `OCBRAIN_K4_1_COGNITIVE_RUNTIME_FOUNDATION.md`, `OCBRAIN_K4_1_COGNITIVE_SERVICE_ARCHITECTURE.md`, `OCBRAIN_K4_1_RECURSIVE_SERVICE_COMPOSITION.md`, and `OCBRAIN_K4_1_X_DELEGATION_ARCHITECTURE_AUTHORITATIVE.md` should all be archived once this is accepted. This document was written to stand alone precisely so that archiving them is a clean replacement, not a merge left for later — the failure mode this project already lives with once, in the Constitution's own 9-versus-11-law discrepancy, is not one worth risking a second time on this layer.

**What genuinely changed by looking at all four together, rather than just merging them.** Three things: the Intent/Goal/Planner separation now has an explicit, evidence-based justification rather than an inherited assumption (Part II, Part IX); the distinction between registration-time Service Admission and per-call invocation eligibility is now named and separated, where it was previously implicit (Part III); and `GovernanceKernel`'s immunity to the same God-Object failure that hit `DelegationEngine` is now stated as a structural fact with a reason, not left as an unstated assumption a careful reader would have had to verify themselves (Part IX). Everything else here is consolidation — real, and worth doing once, but not new discovery, and it would be dishonest to present it as more than that.

**What's still genuinely open**, carried forward rather than lost in the consolidation: trust-composition enforcement mechanics (Part V), whether `ServiceProfile` plus semantic matching holds up once real services exist to test it against (Part III), whether Intent-level — pre-Goal — service discovery is ever needed (not designed, not ruled out), and whether delegation-specific recursion depth should ever differ from the Kernel's general nested-execution limit. None are blockers; all are the kind of question implementation contact answers better than another design pass.

**On the pass itself.** This document's own framing — final architecture pass, not another addition — is correct, and worth affirming on the merits rather than only because it was asked for. Five architecture-only documents, in sequence, produced one real structural fix (the policy/mechanism separation in the fourth) and one useful synthesis (the governing principle in Part I, visible only once all four were read together) — genuine value, but a decreasing amount of it per document, which is itself the signal that the next real question belongs to K4.2, not to a sixth document. Recommend K4.2 begin next, building directly on this specification, with no further K4.1-layer design work scheduled ahead of it.

---

*Consolidated architecture complete. No implementation performed, no repository files modified, no interfaces frozen. This document is the sole authoritative reference for the Cognitive Runtime layer above K4's core pipeline; the four documents it supersedes should be archived, not read alongside it.*
