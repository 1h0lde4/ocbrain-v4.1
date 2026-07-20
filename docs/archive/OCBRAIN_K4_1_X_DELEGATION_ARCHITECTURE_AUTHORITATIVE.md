# OCBrain K4.1.x — Delegation Architecture (Authoritative)
## Separating Policy from Mechanism in Cognitive Service Delegation

**Date:** July 19, 2026
**Status:** Architecture Only. Zero code, zero implementation, zero repository modifications, zero interface freezing, zero placeholder APIs.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md`, `PROJECT_INSTRUCTIONS.md`, and K4. Baseline: `OCBRAIN_K4_1_COGNITIVE_SERVICE_ARCHITECTURE.md` ("the Service Architecture") and `OCBRAIN_K4_1_RECURSIVE_SERVICE_COMPOSITION.md` ("the Recursive Composition document"). This document is additive to both except in the two places named explicitly in §1, where a prior decision is changed and justified per the three-part test this session requires.

---

## 1. Architectural Assessment

The concern is well-founded, and it's worth being precise about exactly where it manifested rather than treating it abstractly. In the Recursive Composition document, `CognitiveServiceRuntime` did three genuinely different kinds of work inside one component: it decided whether a request violated a cycle rule (a policy judgment), it separately consulted `RecursionGovernor` and `BudgetGovernor` directly rather than through the Kernel's own unified governance gate (an inconsistency, not just a style issue), and it mechanically constructed context and invoked the target (the part that actually belonged there). Left alone, every future delegation concern this session lists — trust, admission, priorities, scheduling — would have been tempted to land in the same component, for the same reason: it was the only place delegation-specific logic had anywhere to go. That's the God Runtime risk, concretely.

**Two decisions from prior documents change as a result. Both are named here, with the three-part justification this session requires; nothing else in the Service Architecture or Recursive Composition documents is reversed.**

**Change 1 — `CognitiveServiceRuntime` is renamed `DelegationEngine` and stripped of all policy logic.**
- *Why the previous decision becomes insufficient:* it owned both the judgment ("does this violate a rule") and the mechanism ("how do I carry this out"), which is exactly the coupling that produces unbounded growth over time — every new policy concern had no other home to go to.
- *Why the new one preserves every Kernel principle:* it makes delegation strictly follow LAW 1 (Governance Before Capability) the same way every other governed action in the system already does — through one call to `GovernanceKernel.evaluate_action()`, not a special-cased, delegation-only path. Nothing about the Kernel's frozen ownership boundaries changes; `GovernanceKernel` was already the sole policy authority, this just stops delegation from being the one exception to that.
- *Why it is more future-proof:* a new delegation policy, whatever it turns out to be a decade from now, becomes a new Governor or a new rule inside an existing one — zero change to `DelegationEngine` itself. Under the previous design, every new policy dimension would have required `DelegationEngine`'s own code to grow, which is the definition of the risk this session raised.

**Change 2 — Cycle prevention moves from inline logic inside the (old) `CognitiveServiceRuntime` to `GovernanceKernel`, specifically into `OrchestrationGovernor`.**
- *Why the previous decision becomes insufficient:* it was a policy decision (is this action allowed) implemented as ordinary code inside a mechanism component, invisible to `GovernanceKernel` and inconsistent with how every other permission decision in the system is made and audited.
- *Why the new one preserves every Kernel principle:* `OrchestrationGovernor` already exists as a *named, specified-but-unbuilt* governor — `PROJECT_INSTRUCTIONS.md` §6.1 lists it among the five required governors, and K1's own audit confirmed it was one of two still genuinely absent from the live `GovernanceKernel`. This document isn't inventing new governance surface area; it's supplying the first concrete use case for a slot that was already reserved. That's a stronger, more evidence-grounded placement than adding a new governor name would have been.
- *Why it is more future-proof:* cycle prevention, and any future orchestration-shape policy (priorities, scheduling — see §2), now lives exactly where `PROJECT_INSTRUCTIONS.md` already said orchestration-level recursion concerns should live, closing rather than adding to the open governor-naming reconciliation K1 §4 already flagged.

Everything else — the Registry, `ServiceProfile`, the Find/Call shape, `CognitiveContext`, the delegation chain as a per-invocation list, the recursive walkthrough — stands unchanged.

---

## 2. Policy vs. Mechanism Analysis

**A working test, stated once so it doesn't need re-deriving for every item:**

- **Policy** answers *"is this allowed?"* It's evaluable purely from context/state, without performing the action, and a violation means outright rejection. Belongs in `GovernanceKernel`, as a Governor.
- **Mechanism** answers *"how is this carried out, once approved?"* Belongs in `DelegationEngine`.
- **Operational signal** answers *"is this likely to succeed right now?"* — a different question from either of the above. It doesn't gate permission; it informs the *reasoning* that picks a target in the first place. Belongs where it already lives: `CognitiveService.health()` (Service Architecture §3), feeding Planner's or a Service's own alternative-generation, not a hard gate.

Applied to every item this session listed:

| Concern | Bucket | Verdict |
|---|---|---|
| Recursion (depth) | Policy | Already `RecursionGovernor`, unchanged, reused per K1.5 §4's precedent |
| Cycles | Policy | `OrchestrationGovernor` — see §1, Change 2 |
| Trust | Policy | `AgentGovernor`'s existing "permission matrix" scope (COMPLETE_UNIFIED_STUDY_V3.md's original design intent) is the natural home once designed — see §13. Not fully designed here; placement is |
| Admission (per-invocation eligibility) | Policy | Same governor as trust — a check against a service's current `lifecycle_state`/`trust_status`, not a new concept; distinct from the Service Architecture's registration-time Admission Test, which is unchanged |
| Budgets | Policy | Already `BudgetGovernor`, unchanged |
| Health | Operational signal, not policy | See test above — stays in `health()`, feeds reasoning, isn't a hard gate. A minimal exception is worth naming: nothing here forbids a light circuit-breaker convention (OmniRoute's pattern, already flagged as valuable prior art) sitting alongside `health()` — but that's a resilience mechanism, not a permission gate, and isn't designed further here |
| Priorities | Policy, future slot | No evidence of need yet (nothing in any document to date describes concurrent, competing delegation requests). Housed under `OrchestrationGovernor`'s reserved scope when evidence arrives; not designed now |
| Scheduling | Policy, future slot | Same as priorities |
| Enterprise restrictions | Rejected for now | See below |
| Licensing | Rejected for now | See below |
| Tenancy | Rejected for now | See below |
| Future governance rules | N/A | This is simply the extensibility property itself, not an item to place |

**On enterprise restrictions, licensing, and tenancy — pushback, stated directly.** Nothing in this project's own stated identity supports treating these as near-term architectural concerns. The Kernel Constitution's own Part I says plainly that OCBrain "is not a product" and Part VI's Non-Goals explicitly exclude "another cloud service" as a required posture; nothing in `PROJECT_INSTRUCTIONS.md` or any prior architecture document describes multi-tenant or licensed deployment as part of the system's identity. Building a `TenancyGovernor` now, against zero real requirements, would very likely get the shape wrong — there's no evidence yet of what OCBrain's tenancy model would even look like — and a wrong speculative design costs *more* long-term stability than not building it, because it would need redesigning the moment real evidence arrived anyway. This is not a refusal to take the ten-year horizon seriously; it's the opposite. The way this architecture achieves ten-year stability isn't by pre-building every conceivable policy today — it's by making sure that whenever tenancy, licensing, or anything else genuinely becomes necessary, adding it costs exactly one new Governor and zero changes anywhere else. §14 demonstrates this concretely rather than just asserting it.

---

## 3. Delegation Architecture

```text
Planner  or  [a Cognitive Service, mid-reason()]
      │  decides WHAT to delegate — unchanged, Service Architecture §4
      ▼
GovernanceKernel.evaluate_action(action_type="service_delegation", ...)
      │  ONE call — the same Template Method every governed action in
      │  the system already uses (AbstractCognitiveWorker.execute()).
      │  Internally may consult RecursionGovernor (depth),
      │  OrchestrationGovernor (cycle-freedom — §1), AgentGovernor
      │  (trust/admission, once built — §13), BudgetGovernor (spend).
      │  REJECT/ESCALATE short-circuits here, exactly as elsewhere.
      ▼  (approved)
DelegationEngine  — mechanism only, zero policy logic (§5)
      │  construct scoped CognitiveContextView (+ delegation_chain)
      │  emit cognitive.service_delegated
      ▼
ExecutionRuntime.invoke(...)  — Kernel, unchanged
      ▼
[Target Service].reason(...)  →  CognitiveArtifact
      │
      └── returned to caller; recursion (§ Recursive Composition doc)
          unchanged — a Service receiving control back may itself
          issue a new delegation request through the identical path
```

The single load-bearing change from the Recursive Composition document's own diagram: what was two separate, direct governor consultations inside the mediator is now one call to the same gate everything else in the system already passes through.

---

## 4. Delegation Policy Layer

**Is this a new, parallel policy system? No — this session's own framing already points at the right answer:** *"The architecture should make adding a future policy equivalent to adding another Governance rule: extension, not redesign."* `GovernanceKernel` already is that mechanism. There is no new "Delegation Policy Layer" as a distinct architectural concept — there is `GovernanceKernel`, doing what it already does, now correctly covering delegation the way it already covers memory writes, plan compilation, and self-modifying curation actions.

**Ownership.** Unchanged — `GovernanceKernel`, Kernel-owned, one of the five frozen boundaries. Nothing about this document touches that ownership.

**Responsibilities added, not a new component:** evaluating delegation-specific policy, via `OrchestrationGovernor` (cycle-freedom, and the reserved future scope for priorities/scheduling) and `AgentGovernor` (trust/admission, once designed).

**Lifecycle.** Governors register at startup, exactly as the existing three live governors already do (K1 §1.1's composition-root pattern) — no new lifecycle model.

**Interfaces, architecturally, not implementation:** a delegation request is expressed to `evaluate_action()` as an action with metadata (`target_service_id`, `subgoal`, `current_delegation_chain`) — the same shape every other governed action already provides context for, not a bespoke schema.

---

## 5. Delegation Engine

**Renamed from `CognitiveServiceRuntime`.** Its remaining responsibilities, once policy is fully removed: accept an *already-approved* delegation request, construct the scoped `CognitiveContextView` (including the extended `delegation_chain`, Recursive Composition §5), emit `cognitive.service_delegated`, invoke via `ExecutionRuntime`, return the resulting Cognitive Artifact. Nothing else.

**Why "Engine," not "Runtime."** Both were considered. "Runtime" — deliberately chosen in the Recursive Composition document — connotes a hosting, coordinating system with its own state and lifecycle, appropriate to a component that was, at the time, also making decisions. Once policy is stripped out, what's left is a narrow, stateless, repeatable input→output transformation — carry out an approved request — which "Engine" describes more accurately. The rename tracks a real change in what the component *is*, not just a preference. ("Engine" already coexists safely with other prefixed components in this codebase — `GraphEngine` — the same way multiple `*Runtime` components already coexist; disambiguated by prefix, not a naming collision.)

**Shape, restated:** its only entrypoint is something like `DelegationEngine.execute(approved_request) -> CognitiveArtifact` — deliberately taking an *already-approved* request, not a raw one, making it structurally impossible for it to skip the governance gate, the same way `AbstractCognitiveWorker.execute()`'s Template Method makes governance-skipping structurally impossible for ordinary workers.

**Ownership.** Cognitive Runtime layer, alongside Planner and Plan Compiler — not registered, not swappable, not itself a `Resource` (K1.6). Unchanged from the prior document beyond the rename.

---

## 6. Delegation Graph

**Should the per-invocation delegation chain become a graph? The chain itself: no. The whole-session structure: it already is one — but it doesn't need to be built or stored as a new object.**

Two different things were being asked about under one name, and separating them resolves the question cleanly. The `delegation_chain` field on `CognitiveContextView` (Recursive Composition §5) represents *one invocation's own lineage* — a path, correctly a list, needed for cycle-checking and scoped context. Discovery consulting Knowledge, Simulation, and Workspace separately produces *three separate invocations*, each with its own correctly-linear chain — the branching the session describes is real, but it's a property of the *aggregate* of many invocations, not of any single one's lineage.

That aggregate — the full tree or graph of everything a session delegated to, across every branch — **is a reconstructable view, not a new persisted object.** Every delegation already emits a `cognitive.service_delegated` event (§3) carrying parent, target, and chain-at-time-of-call; every Cognitive Artifact already carries `derived_from` provenance (Service Architecture §6, reusing `KnowledgeEntry.derived_from`'s convention). The full delegation graph for a session is exactly what querying `EventStream` plus following `derived_from` chains already produces. Building a separately-maintained graph structure would create a second source of truth for information the event log already holds — precisely what Law 9 (Single Source of Truth) exists to prevent.

**Relationships, as requested:**
- **`CognitiveContext`:** doesn't own or need the full graph — it only ever cares about its own request's in-flight artifacts (Service Architecture §6, unchanged).
- **`ExecutionContext`:** its `causal_chain` (K1.5 §3.3) remains the per-invocation lineage; the graph is the union of many `causal_chain`s reconstructed after the fact, not a new field there.
- **`EventStream`:** the actual source of truth. One small, additive note: `cognitive.service_delegated` payloads should carry enough to make reconstruction cheap (parent id, target id, chain-so-far) — a payload-completeness note, not a new event type.
- **Provenance:** artifact-level provenance (`derived_from` — which artifacts fed into which) and invocation-level provenance (the delegation graph — which services were called by which) are complementary, both reconstructable, neither requiring new persisted structure.

---

## 7. Ownership Boundaries

Extending the Recursive Composition document's table — only the changed cells are shown.

| Layer | Owns (revised) | Never owns (revised) |
|---|---|---|
| **Kernel — `GovernanceKernel`** | Delegation policy evaluation (cycle-freedom via `OrchestrationGovernor`, trust/admission via `AgentGovernor` once built), in addition to everything it already owned | Deciding *which* service a delegation targets — that stays with the requesting component's own reasoning, unchanged |
| **Cognitive Runtime (core) — `DelegationEngine`** | Mechanical execution of an *already-approved* delegation only | Any policy evaluation whatsoever — this is the corrected boundary; previously this row implicitly included policy logic |

No other row changes. The Kernel's frozen five-boundary list (Governance, Memory, Workflow, Execution, Event) is untouched — this document extends the *scope* of what `GovernanceKernel` evaluates, not its ownership category.

---

## 8. Updated Cognitive Runtime Model

Unchanged in shape from the Service Architecture and Recursive Composition documents: Intent Interpreter, Planner, Plan Compiler, ReflectionWorker, EvaluatorWorker, SupervisorWorker remain fixed core components; `CognitiveService` remains the single generic registered contract; `CognitiveContext` remains request-scoped, non-persisted. The one addition: `DelegationEngine` is now explicitly documented as owning zero policy logic, consistent with every other core component's own separation from `GovernanceKernel` (Planner reasons, it doesn't self-authorize; Plan Compiler translates, it doesn't self-authorize; `DelegationEngine` now matches this pattern exactly rather than being the one exception).

---

## 9. Updated Service Composition Model

The recursive walkthrough from the Recursive Composition document §8 is unchanged in shape (Planner → Discovery-like service → Knowledge-like service → Simulation-like service → Artifact), with one correction to how each hop is drawn: every arrow now passes through the single `evaluate_action()` gate (§3's diagram) rather than the two-governor direct-consultation shown previously. Branching (one service consulting several others) is now explicitly represented as multiple independent invocations from that service, each following the identical path, each producing its own event and its own artifact, reconciled afterward via `derived_from` when the calling service's own artifact cites all of them.

---

## 10. Updated Invariants

The Recursive Composition document's eight invariants, revised where the God-Runtime fix changes them; unlisted ones carry forward unchanged.

- Invariant 6 ("never invoked twice in the same chain") — **unchanged in substance**, enforcement mechanism changes from inline code to `OrchestrationGovernor` (§1).
- Invariant 7 ("the mediator never makes a delegation decision") — **strengthened, renamed**: *"`DelegationEngine` never evaluates policy of any kind — every delegation it carries out has already passed `GovernanceKernel.evaluate_action()`."* Previously this component also did inline policy checks, which is itself a form of the thing it claimed not to do; that gap is now closed.
- Invariant 8 (trust-chain minimum, not maximum) — **unchanged in substance**, now explicitly placed as `AgentGovernor` scope rather than floating (§13).

**New, added by this refinement:**

9. **Every delegation-specific policy is expressed as a Governor or a rule inside one — never as conditional logic inside `DelegationEngine`.** The structural rule this whole document exists to establish, made a standing, checkable invariant rather than left as a one-time design decision.
10. **A component whose own code must change to support a new policy is a mechanism component that has acquired policy responsibility, and is out of compliance with Invariant 9.** A generalizable test for catching a future God-Runtime recurrence, not specific to `DelegationEngine`.

---

## 11. Failure Containment

No new mechanism. A failed delegation (target errors, times out, is unreachable) resolves to a failed `WorkerResult` at the `ExecutionRuntime` boundary — the same containment `AbstractCognitiveWorker.execute()` already guarantees for every worker invocation, and the same `return_exceptions=True` discipline K1's audit confirmed already holds at the fan-out level. The caller (Planner or a Service) sees a failure, not a crash, and may choose an alternative candidate via the existing `alternatives`/`confidence` mechanism (Service Architecture §4) or hand off to `SupervisorWorker`'s existing retry-via-reinvocation (K4 §9) — both already-established paths, neither reinvented here.

---

## 12. Explainability

Every question this session listed is answerable from mechanisms already established, none newly invented for this purpose:

| Question | Answered by |
|---|---|
| Why was this service invoked? | `cognitive.service_delegated` event payload (subgoal, justification) |
| Which service produced this artifact? | `CognitiveArtifact.produced_by` (Service Architecture §6) |
| Which delegation consumed the budget? | `BudgetGovernor`'s tracking, correlated via request id |
| Which service failed? | Ordinary worker-failure events, correlated to the delegation event (§11) |
| Which service was retried? | A second `cognitive.service_delegated`/invocation event, distinguishable by timestamp, per Supervisor's existing retry pattern |
| Which branch produced the final answer? | Reconstructed from `EventStream` plus `derived_from` chains — the Delegation Graph, §6 |

---

## 13. Trust Implications

The principle from the Recursive Composition document stands: a delegation chain's effective trust is the minimum trust of any member, never the maximum. What changes here is placement, not substance — trust composition is now explicitly a **policy** question (§2's test), belonging inside `GovernanceKernel`, most plausibly as part of `AgentGovernor`'s already-intended "permission matrix" scope (its original design description explicitly includes this kind of concern). It is still not fully designed: the actual scoring/composition mechanics need real, differently-trusted services to design correctly against, and building them now against zero evidence would repeat exactly the mistake §2 argues against for tenancy and licensing. What this document adds is confidence about *where* the eventual mechanism belongs, which is enough to unblock K4.2 without needing the mechanism itself finished first.

---

## 14. Future Extensibility

Stress-tested against the scenario list directly, to demonstrate rather than assert the claim:

- **Hundreds of services:** the Registry and `ServiceProfile` matching (Service Architecture §4) don't change shape at any scale; only the semantic-matching cost grows, already flagged as a deferred, evidence-gated optimization there.
- **Third-party / community-developed / user-created / AI-generated services:** all register through the identical `CognitiveService` contract, all start at whatever `trust_status` the Truth Framework assigns new entries (Service Architecture §5), all execute inside the same sandboxing regardless of origin (PI §14.1). Nothing about *how* a service came to exist changes how it's discovered, delegated to, or governed.
- **Enterprise-only, licensed, or tenant-scoped services, if they ever exist:** per §2, this needs exactly one new Governor (or a rule inside `AgentGovernor`) the day real requirements exist — zero change to `DelegationEngine`, the Registry, `ServiceProfile`, or any existing Governor. This is the concrete proof of the claim in §2, not a repetition of it.
- **Cloud vs. local services:** already orthogonal — a service's `reason()` may itself call cloud-backed Capabilities via the existing Provider Mesh (PROJECT_INSTRUCTIONS §10), which has nothing to do with how the service itself is discovered or delegated to.

---

## 15. ADR Candidates

Enumerated only.

1. **ADR-K4.1-16** — `CognitiveServiceRuntime` is renamed `DelegationEngine` and stripped of all policy logic; its sole entrypoint accepts only already-approved requests (§1, §5).
2. **ADR-K4.1-17** — Cycle prevention for delegation moves to `OrchestrationGovernor`, filling an already-reserved, previously-unbuilt governor slot rather than introducing a new one (§1).
3. **ADR-K4.1-18** — All delegation-specific policy (present and future) is expressed as Governors or rules inside existing Governors — never as conditional logic inside `DelegationEngine` — codified as a standing invariant, not just a one-time decision (§10).
4. **ADR-K4.1-19** — The "Delegation Graph" is a reconstructable view over `EventStream` and `derived_from` chains, not a new persisted object (§6).
5. **ADR-K4.1-20** — Enterprise restrictions, licensing, and tenancy are explicitly deferred pending real evidence; the architecture's readiness for them is demonstrated via the Governor-extension pattern rather than pre-built (§2, §14).
6. **ADR-K4.1-21** — Trust composition for delegation chains is placed under `AgentGovernor`'s reserved scope; enforcement mechanics remain undesigned pending real, differently-trusted services (§13).

---

## 16. Impact on Future K4.x Milestones

- **K4.2 (Planner):** unchanged from the Recursive Composition document's note — Planner's delegation call and any Service's own delegation call must be the same call shape. Now additionally: that shape is a request to `GovernanceKernel.evaluate_action()` followed by `DelegationEngine.execute()`, not a direct call to `DelegationEngine` alone — worth designing correctly from the start rather than retrofitting the gate in later.
- **K4.3 (Plan Compiler / Governance Gate):** whoever designs the Plan Compilation governance gate should be aware `OrchestrationGovernor` and `AgentGovernor` are now also live consumers of `evaluate_action()`, alongside whatever `action_type="plan_compile"` already does — same entrypoint, different action types, no interaction required beyond that.
- **K4.6 (Supervisor):** unchanged — Supervisor's retries route through the identical path, now including the governance gate, for the same consistency reason already noted in the Recursive Composition document.
- **No impact identified** on K4.4 (Reflection/Evaluation) or K4.5 (Memory Integration).

---

## 17. Closing Assessment

The substance of what changed here is real, not cosmetic: delegation now follows the exact same governance discipline as every other action in the system, with no carve-out, and the mechanism component left over is small enough that it's hard to imagine what would need to be removed from it later — which is itself a decent test that the separation landed in the right place.

One thing is worth saying plainly, in the same spirit as this document's own instruction to challenge assumptions rather than just execute them. This is the fourth consecutive architecture-only document in this session, and across all four, exactly zero lines of code exist and zero Cognitive Services have been built. Every decision in this document — including the ones I'm confident are correct — is reasoned from precedent and first principles, not from any actual friction encountered building something. That's not a reason to have done this session differently; the God Runtime risk was real, and getting the policy/mechanism boundary right *before* a component accretes responsibility is cheaper than fixing it after. But it is a reason to treat this document's own framing seriously: it calls itself the final refinement before K4.2, and I'd endorse that framing on the merits, not just because it's how the request was worded. The next question this architecture actually needs isn't a fifth design pass — it's what K4.2 discovers when Planner's decomposition logic first has to call `evaluate_action()` for real. If something here doesn't hold up under that contact, that's better evidence than anything a fifth paper review would produce.

---

*Delegation Architecture (Authoritative) complete. No implementation performed, no repository files modified, no interfaces frozen. Two prior decisions changed, both justified per §1; everything else in the Service Architecture and Recursive Composition documents stands. Ready for K4.2.*
