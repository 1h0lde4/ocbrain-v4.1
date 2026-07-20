# OCBrain K4.1 — Recursive Cognitive Service Composition

**Date:** July 19, 2026
**Status:** Architecture Only — extends `OCBRAIN_K4_1_COGNITIVE_SERVICE_ARCHITECTURE.md` ("the Service Architecture"). Zero code, zero implementation, zero repository modifications, zero interface freezing, per instruction.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md`, `PROJECT_INSTRUCTIONS.md`, and K4. Additive to the Service Architecture document — nothing below contradicts or supersedes it; §7–§9 restate the specific fields and invariants that grow as a result of this addition.

---

## 0. Verdict

Recursive Cognitive Service composition should become an explicit architectural property — but the reason it's affordable to add now, rather than a reason to defer it, is that it costs almost nothing new to build. A service delegating to another service is, mechanically, the same nested-execution pattern the Kernel already handles for a Worker that triggers a sub-workflow (K1.5 §4), governed by the same `RecursionGovernor` that already exists. What genuinely is new is small and cheap: one thin, non-deciding coordination component, one additional field on the already-existing scoped context projection, and an explicit cycle check. Nothing about this requires a new Kernel mechanism, a new governor, or a new persistent object.

---

## 1. Direct vs. Mediated Invocation — *Deliverable answer to Question 4*

Two shapes were evaluated.

**Direct (a service calls another service's `reason()` method itself, peer-to-peer):** rejected. Checked against every factor named:

| Factor | Direct | Mediated (through a common runtime layer) |
|---|---|---|
| Loose coupling | A service must know *how* to invoke another — auth, context construction, error handling | A service expresses only *what it needs*; the mechanics are someone else's job |
| Discoverability | Each service would need its own path to the registry, or hardcode who it calls | Reuses the exact same Registry + `ServiceProfile` matching (Service Architecture §4) at every depth, no special case |
| Future user-/community-created services | A third-party service author has to correctly implement safe invocation themselves | A third-party author only implements `reason()`; invocation safety is centrally provided, not trusted to every author |
| Service replacement | Calling code embeds a dependency on a specific service's identity — replacing it means finding every caller | Nothing ever references a specific service by identity outside the registry; replacement is transparent |
| Observability | Every service would need to correctly self-instrument every outbound call | One mediator, one guaranteed emission point, no possibility of a silent hop |
| Governance | Recursion/budget checks would have to be reimplemented, correctly, inside every service | Checked once, centrally, the same way for every service regardless of trust level |
| Lifecycle management | Each service tracks which others currently exist and are healthy, duplicating the registry | The registry remains the single index; nothing else needs to track it |

Every factor favors mediation, and none favor direct calling strongly enough to accept its costs. **Decision: all inter-service delegation passes through a common layer — introduced in §3 as `CognitiveServiceRuntime`.**

---

## 2. Why Mediation Costs Almost Nothing New

This is the headline finding of this document, in the same register as the Service Architecture's own headline finding (§1 there: Extensions/Services need no new Kernel-facing mechanism).

K1.5 §4 already answered a structurally identical question for the Kernel's own nested execution: *"Nested execution (a Worker that itself triggers a sub-workflow) is a `WorkflowRuntime` invoking `ExecutionRuntime` invoking a Worker whose own logic calls back into `WorkflowRuntime` — this needs a recursion-depth check at that specific re-entry point, which is exactly what `RecursionGovernor` (already live) is for. No new mechanism needed, just confirming the existing governor covers this path once it's reachable."*

A Cognitive Service, once invoked, is already realized as an ordinary Worker invocation through `ExecutionRuntime` (Service Architecture §7, unchanged: "invocation reuses `ExecutionRuntime`/`WorkflowRuntime` — no new Kernel mechanism"). A Service asking for help from another Service is therefore not a new *kind* of recursion — it's the exact same re-entrant pattern K1.5 §4 already covers, one level deeper. `RecursionGovernor` doesn't need to be taught anything new; it just needs to keep being consulted at the new re-entry point, which is precisely what §3's coordinator does.

This also settles a scope question before it becomes a design temptation: none of what follows proposes touching the Kernel. `RecursionGovernor`, `BudgetGovernor`, `ExecutionRuntime`, `EventStream` are used exactly as they already exist. Everything new in this document lives at the Cognitive Runtime layer.

---

## 3. `CognitiveServiceRuntime` — *Deliverable answer to Question 1*

**What it is.** A thin, non-deciding coordination component, living inside the core Cognitive Runtime alongside Planner and Plan Compiler — not registered as a Cognitive Service itself, not swappable, not a `Resource` (K1.6). It is the single mandatory path through which every delegation — Planner-to-Service or Service-to-Service — is mechanically executed once a target has already been chosen.

**What it does, precisely:**
1. Accepts `(target_service_id, subgoal, current_delegation_chain)` from a caller (Planner or a currently-executing Service).
2. Checks the target against the current chain for a cycle (§6) — rejects immediately if found.
3. Checks recursion depth and budget against the existing `RecursionGovernor`/`BudgetGovernor` — no new governor, the same re-entry-point pattern K1.5 §4 already established.
4. Constructs the scoped `CognitiveContextView` for the target, including the extended delegation chain (§5).
5. Emits a `cognitive.service_delegated` event (extending the existing `cognitive.*` namespace, K4 §12) — carrying who delegated, to whom, why, and the resulting chain depth.
6. Invokes the target via `ExecutionRuntime`, unchanged.
7. Returns the resulting Cognitive Artifact to the caller.

**What it explicitly does not do: it never decides which service to call.** That judgment — the semantic match against registered `ServiceProfile`s — stays exactly where the Service Architecture put it: with Planner's own reasoning (Service Architecture §4), or, symmetrically, with a Service's own reasoning about its own sub-need. `CognitiveServiceRuntime` receives a decision already made; it never makes one.

**Why this doesn't reopen the rejected "Extension/Service Orchestrator."** Worth resolving explicitly rather than leaving for a careful reader to notice: K4.1 §9 and the Service Architecture §7 both rejected a dedicated Orchestrator on the ground that it would duplicate Planner's delegation-*deciding* authority. `CognitiveServiceRuntime` does something categorically different — it has zero deciding authority over *what* gets delegated, only mechanical authority over *how* a delegation, once decided, is safely and observably carried out. This is the same split already drawn between Planner (decides) and Plan Compiler (mechanically translates, decides nothing) in K4 §1 — `CognitiveServiceRuntime` is the delegation-layer counterpart to Plan Compiler, not a second Planner.

**On the naming.** "Runtime" deliberately echoes the Kernel's `ExecutionRuntime`/`WorkflowRuntime` family, because the job is structurally analogous — construct and invoke, mechanically, at a defined re-entry point. It is not a Kernel component and owns nothing the Ownership Boundaries table (§7) doesn't already assign it: it lives inside "Cognitive Runtime (core)," calls the Kernel's `ExecutionRuntime`, and modifies nothing about the Kernel's own ownership of workflow/capability execution.

**A genuine open risk worth flagging here rather than burying it: trust doesn't automatically compose correctly through a chain.** A low-trust, community-registered service delegating to a verified, high-trust service could otherwise look, from the outside, like a request that originated from the trusted end of the chain. This document doesn't fully resolve the mechanics — that needs more than zero real services to get right — but the direction worth recording now is a simple, checkable principle: **a delegation chain's effective trust is the minimum trust of any member in it, never the maximum.** Full enforcement mechanics are left to whoever eventually builds the Trust/Admission machinery in practice; the principle is recorded here so it isn't rediscovered as a surprise later. Flagged again in §12.

---

## 4. Planner Ownership, Precisely Stated — *Deliverable answer to Question 2*

The proposed separation — Planner owns global decomposition/workflow construction/execution planning, a Service owns only reasoning inside its delegated domain — is **necessary but not, as stated, sufficient.** Stated alone, it leaves an unanswered question: if a Service's assigned reasoning genuinely needs help from another domain, what happens? Silently blocking it contradicts the premise of this whole exercise; letting it informally reach outside its boundary undermines the separation entirely.

The precision that makes the separation sufficient: **a Service's own request for further delegation is local, not global.** It is local in the sense that it only ever concerns the sub-goal that Service was itself assigned — it is never permitted to reopen or reshape the overall Goal, the overall Plan, or the compiled `WorkflowDefinition`, all of which remain solely Planner's and Plan Compiler's responsibility. A Service recognizing that its own assigned piece needs further breakdown is not a second locus of *global* decomposition — it's the same recursive pattern any decomposition process naturally has (a sub-problem that itself has sub-problems), resolved through the identical Registry + matching + governed-invocation mechanism Planner itself uses, never through private knowledge of which other service to call. With that addition stated explicitly, the separation holds.

---

## 5. Delegation Chain — Not a New Context Object — *Deliverable answer to Question 5*

Every field this session listed was checked individually against what already exists, rather than assumed to need a new container:

| Requested field | Already has a home | Where |
|---|---|---|
| request id | Yes | `ExecutionContext.request_id` (K1.5 §3.3) |
| cancellation token | Yes | `ExecutionContext.cancellation_token`, already propagated to Service invocation (Service Architecture §7) |
| execution budget | Yes | `BudgetGovernor` (existing, though its accumulation gap is a separately-tracked, pre-existing item — not something this document needs to fix) |
| deadline | Yes | Folds into the cancellation token per K1.5 §4: "a timeout is a cancellation triggered by a timer... no separate mechanism needed" |
| tracing information | Yes | `EventStream`'s existing event emission, extended with the new `cognitive.service_delegated` event (§3) |
| recursion depth | Yes | `RecursionGovernor`, unmodified |
| parent service / service stack | **No — genuinely new** | See below |

Only one field genuinely lacks a home, and it doesn't need a new object either: `ExecutionContext.causal_chain` already exists specifically for "the scoped-replay pattern already flagged as future work" (K1.5 §3.3) — a Kernel-owned, per-invocation lineage record. The "service stack" this session asks about is that same lineage, applied to this specific case, not a new concept requiring new infrastructure.

**Concretely:** a `delegation_chain: list[str]` field is added to the scoped `CognitiveContextView` (Service Architecture §6) — a read-only *projection* of the relevant segment of the Kernel-tracked `causal_chain`, following the identical "projection, never a raw reference" discipline K1.6 established for `KnowledgeEntry` → `Context`/`ContextBlock`, reused again here. It is not stored on `CognitiveContext` itself (which stays request-scoped and doesn't need per-hop chain data for its own purpose) and it is not a new standalone context type. `CognitiveServiceRuntime` appends the target's `resource_id` to the caller's current chain before constructing the view handed to the next hop.

---

## 6. Cycle Prevention — *Deliverable answer to Question 6*

Two mechanisms, doing different jobs, both needed:

1. **Exact cycle detection** (new, cheap, given §5's chain is already tracked): before invoking a target, `CognitiveServiceRuntime` checks whether the target's `resource_id` already appears in the current `delegation_chain`. If it does, the request is rejected immediately — Discovery→Knowledge→Discovery is caught on the *second* attempted re-entry, not after burning through a depth budget.
2. **Depth/budget limits** (existing, reused, per §2): catches the case cycle detection can't — a long chain that never literally repeats a service but still grows unbounded (A→B→C→D→E→...). Cycle detection and depth limiting are complementary, not redundant: one is a precise, immediate check for literal repetition; the other is the necessary backstop for everything else.

No new governor, no new limit-configuration surface. If evidence eventually shows Cognitive Service chains need a different depth allowance than other nested execution, that's a parameterization of the existing governor — not designed here, no evidence yet that it's needed.

---

## 7. Updated Ownership Boundaries

Extends the Service Architecture's table (itself extending K4.1 §3). Only the affected rows are restated.

| Layer | Owns (addition) | Never owns (addition) |
|---|---|---|
| **Cognitive Runtime (core)** | `CognitiveServiceRuntime` — mechanical mediation of every delegation, at any depth | Deciding *which* service a delegation targets when the request originates from a Service rather than Planner (that judgment stays with the requesting component's own reasoning) |
| **Cognitive Services** | Requesting further delegation for a sub-portion of its own assigned reasoning, via `CognitiveServiceRuntime` | Direct invocation of another Cognitive Service; knowledge of any other service's identity outside what the Registry returns for a given request |

Nothing about the Kernel row, the Applications row, or the Capabilities row changes.

---

## 8. Service Delegation Model — Recursive Version

Extends Service Architecture §7. Registration, invocation-reuses-`ExecutionRuntime`, and the rejected-alternatives list (dedicated Orchestrator, parallel event bus, hot-reload, closed domain enum) are unchanged; §3 above resolves why a mediator now exists without reopening the Orchestrator rejection.

```text
Planner
  │  "sub-goal G1 needs domain-specific reasoning"
  ▼
CognitiveServiceRuntime.delegate(target=Discovery-like-service, G1, chain=[])
  │  cycle check: pass (empty chain)   ·  depth/budget check: pass (existing governors)
  ▼
[Discovery-like service].reason(G1, context_view{chain=["discovery-id"]})
  │  mid-reasoning, recognizes it needs a sub-answer from another domain
  ▼
CognitiveServiceRuntime.delegate(target=Knowledge-like-service, G1a, chain=["discovery-id"])
  │  cycle check: pass ("knowledge-id" not yet in chain)
  ▼
[Knowledge-like service].reason(G1a, context_view{chain=["discovery-id","knowledge-id"]})
  │  needs one more hop
  ▼
CognitiveServiceRuntime.delegate(target=Simulation-like-service, G1a-i, chain=["discovery-id","knowledge-id"])
  ▼
[Simulation-like service].reason(...)  →  CognitiveArtifact
  │
  └── artifact propagates back up through each caller, ending with Planner
       folding the fully-resolved result into the plan it's building
```

This is exactly the shape the session's own example describes (Discovery → Knowledge → Simulation → Artifact), using the mediator at every hop and demonstrating the cycle check catching an attempted Discovery→Knowledge→Discovery loop on the second re-entry rather than after any wasted depth budget.

---

## 9. New and Revised Invariants — *Deliverable answer to Question 7*

The session's five candidates, each accepted, rejected, or redesigned as instructed — plus additions this analysis surfaced.

1. **"Cognitive Services never bypass the Service Runtime."** *Accepted, unchanged.*
2. **"Cognitive Services never directly reference concrete service implementations."** *Accepted — but this generalizes an invariant that already existed one layer up (Service Architecture Invariant 4: the core Cognitive Runtime never hardcodes a specific service's identity). This extends that same rule to Services delegating to *other* Services, closing the gap this session exists to close.*
3. **"Every service delegation is observable."** *Accepted, generalized — Service Architecture Invariant 7 already said this for core-Runtime-to-Service delegation; it now applies uniformly to Service-to-Service delegation as well, satisfied by §3's mandatory event emission at every hop.*
4. **"Recursive reasoning must remain bounded."** *Accepted — satisfied by reusing `RecursionGovernor`/`BudgetGovernor` (§2, §6), with the addition below making the mechanism explicit rather than just the outcome.*
5. **"Service composition never changes Planner ownership."** *Accepted, redesigned for precision (§4): restated as — service composition never creates a second locus of *global* goal decomposition; a service's own delegation requests remain local to its assigned sub-goal, and the overall Goal, Plan, and compiled `WorkflowDefinition` remain solely Planner's and Plan Compiler's.*

**New, surfaced by this analysis:**

6. **A Cognitive Service is never invoked twice within the same active delegation chain** — the explicit, mechanically-checkable form of cycle prevention (§6), distinct from the depth/budget backstop.
7. **`CognitiveServiceRuntime` never makes a delegation decision — it only executes one already made by the requesting component's own reasoning.** Makes the judgment/mechanism split in §3 a standing, checkable rule rather than something explained once in prose and left to erode.
8. **A delegation chain's effective trust is the minimum trust of any member in it, not the maximum** — records the direction from §3's flagged risk as a principle, pending full enforcement design once real services exist to test it against.

---

## 10. ADR Candidates

Enumerated only.

1. **ADR-K4.1-11** — Recursive Cognitive Service composition is an explicit architectural property, mediated exclusively through `CognitiveServiceRuntime`; direct service-to-service invocation is rejected (§1).
2. **ADR-K4.1-12** — `CognitiveServiceRuntime` reuses the Kernel's existing `ExecutionRuntime`/`RecursionGovernor`/`BudgetGovernor` unmodified; no new Kernel mechanism or governor is introduced (§2).
3. **ADR-K4.1-13** — "Service stack" is satisfied by projecting the existing `ExecutionContext.causal_chain` into a new `delegation_chain` field on `CognitiveContextView`; no new context object is introduced (§5).
4. **ADR-K4.1-14** — Cycle prevention is an explicit, chain-based check, distinct from and complementary to depth/budget limiting (§6).
5. **ADR-K4.1-15** — Delegation-chain trust composes as a minimum, not a maximum, across members — principle recorded, enforcement mechanics deferred (§3, §9).

---

## 11. Impact on Future K4.x Milestones

- **K4.2 (Planner):** Planner's delegation logic (Service Architecture §4) and `CognitiveServiceRuntime.delegate()` should be designed as the same call path Planner uses for its own top-level delegation — there should not end up being two different code shapes for "Planner delegates" versus "a Service delegates deeper." Worth stating explicitly now so K4.2 doesn't accidentally build a Planner-only mechanism that then needs retrofitting.
- **K4.6 (Supervisor):** Supervisor's own delegation (K4 §9 — failure-recovery reasoning) should route through the identical `CognitiveServiceRuntime`, not a separate path, for the same consistency reason.
- **No impact identified** on K4.3 (Plan Compiler/Governance Gate), K4.4 (Reflection/Evaluation), or K4.5 (Memory Integration) — none of them own delegation logic, and nothing here changes what they consume or produce.

---

## 12. Closing Assessment

One thing genuinely designed here rather than merely renamed: the conclusion that recursive composition is nearly free precisely because it reuses K1.5 §4's already-established nested-execution pattern rather than requiring anything new at the Kernel level. That's the load-bearing insight; if it turns out to be wrong once a second and third real service actually exist and try to delegate to each other, most of this document is what needs revisiting, not just a detail inside it.

Two things are explicitly left open rather than resolved, consistent with not designing ahead of evidence: the trust-composition principle in §3/§9 is a direction, not an enforcement mechanism — it needs real, differently-trusted services to design against correctly, and inventing the mechanics now would be exactly the kind of speculative architecture this project's own laws warn against. And whether recursion depth for Cognitive Service chains specifically should differ from the Kernel's general nested-execution limit is unanswered — there's no evidence yet either way.

No further design pass is recommended before K4.2. This document's job was to determine whether recursive composition belongs in the architecture and, if so, make it cheap — both are done, and the remaining open items are the kind implementation contact resolves better than more paper review would.

---

*Recursive composition addendum complete. No implementation performed, no repository files modified, no interfaces frozen. Additive to the Service Architecture document — nothing in that document or in K4.1 is contradicted. Ready for K4.2 with delegation now specified as a single mechanism usable at any depth, per §11.*
