# OCBrain K5 — Future Cognitive Evolution Architecture

**Date:** July 20, 2026
**Status:** Architecture Only — reserved future capabilities, not a build plan. Zero code, zero implementation, zero modification to any existing document. K4.2 is treated as frozen throughout; nothing below changes it.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md` and `PROJECT_INSTRUCTIONS.md`. Extends K4, K4.1, K4.1.x, and K4.2 without contradicting any of them.

---

## 0. Basis & Housekeeping

The mandatory review was performed against the same verified file set confirmed one session-turn ago (`/mnt/project/`, unchanged since): the Constitution and its Rationale/Pressure Test, K1/K1.5/K1.6, K4, K4.1, K4.1.x, and the K4.2 authoritative specification produced this session. One naming note, trivial and not a repeat of the earlier K4.1-L gap: this task references "`OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE.md`"; the actual file produced this session is `OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` — same document, same content, informal reference.

**Inherited caveat, not resolved here.** K4.2 §0 flagged its own Learning Architecture section as `[RECONCILE-PENDING]` against three K4.1 documents (Service Architecture, Recursive Composition, K4.1-L) not available in this project's file set. Several proposals below extend K4.2's Learning/Evolution machinery further; they inherit that same pending-reconciliation status. This is noted once here rather than repeated at every reference.

**Standing constraint for this entire document.** K4.2 is frozen. Every item below is either (a) an observation about where a capability already lives in the existing architecture, (b) a capability explicitly deferred to K5 or later with a stated reason, or (c) a speculative idea tracked but not recommended for scheduling. Nothing here proposes a change to any K4.2 contract, state machine, or invariant.

---

## 1. Classification Framework

Four categories, applied consistently to every topic below, per the task's own requirement to distinguish them rather than present everything as equally actionable:

| Category | Meaning |
|---|---|
| **Architectural Observation** | Already substantially covered by existing architecture; naming it clarifies ownership, it doesn't create new work |
| **Recommended** | Genuinely new, evidence-supportable, with a clear integration path; appropriately sequenced at K5+ |
| **Speculative** | Motivated but not yet evidence-supportable; tracked, not scheduled |
| **Deferred (prerequisite-gated)** | Legitimate but explicitly blocked on something else finishing first |

**Summary, before the detail** — the single most important finding of this document, stated up front rather than buried: of the eight requested topics, **three resolve mostly to "already covered, implement K4.2 and its already-planned dependencies thoroughly"** rather than "build something new." This is not a disappointing result — per the Constitution's Law of Evidence over Assumption, an architecture that doesn't need eight new subsystems to answer eight new questions is a *stronger* one, not a weaker one.

| Topic | Verdict |
|---|---|
| 1. Self Model | Recommended (K5, early) |
| 2. World Model | Mostly Architectural Observation; one small vocabulary extension Recommended |
| 3. Meaning Representation Layer | Recommended, but K6+ and evidence-gated |
| 4. Active Concept Discovery | Recommended, prerequisite-gated on K4.2 ontology evolution having real mileage |
| 5. Hypothesis / Belief Revision | Split — cheap version Recommended (K5, near-term); formal version Speculative |
| 6. Reasoning Strategy Selection | Recommended as a roadmap slot; not buildable until multiple real strategies exist |
| 7. Intent Semantics Preservation | Mostly Architectural Observation; one small Constraint-model extension Recommended |
| 8. Temporal Intent | Split — urgency/deadline/duration Architectural Observations; recurring/long-term objective surfaces one significant, deliberately under-specified Recommended item |

---

## 2. Self Model

*Verdict: Recommended (K5, early)*

| Dimension | Content |
|---|---|
| Motivation | Capability health, budget, and calibration state are each already tracked somewhere (`CapabilityResolver`'s own scoring, `BudgetGovernor`, `EvaluatorWorker`'s calibration tracking) but nowhere aggregated into something the Cognitive Runtime can consult to ask "am I well-positioned to attempt this right now" |
| Architectural ownership | A read-mostly projection, identical in *kind* to the User Cognitive Model (K4.2 §3) — assembled on demand from existing Kernel state, never a new persisted store |
| Interactions | Feeds `Planner` exclusively via the existing `PlannerHint` mechanism (K4.2 §5) — e.g. a "degraded capacity, prefer a simpler plan" hint. Never a direct input to `CapabilityResolver`/`ServiceProfile` matching itself, which stays owned where it already is |
| Governance | None, as long as it stays advisory-only. Self-Model-driven autonomous self-throttling (as opposed to hinting) would be a materially different, higher-risk capability requiring its own gate — explicitly out of scope here |
| Replay | Assembled from *live, transient* state — a past decision informed by a Self-Model-sourced hint must have that hint's snapshot captured at emission time; replay must never re-query current Kernel state to reconstruct a past one. Reuses the exact principle already established for Evolution-tier `KnowledgeEntry` versioning (K4.2 §8) |
| Event model | One new event, `cognitive.self_model_assembled`, carrying the snapshot above — no new emission mechanism |
| Memory | None by default (assembled, not persisted). Periodic snapshotting for trend analysis is a plausible later refinement, explicitly not proposed now — no evidence of need |
| Learning | None directly; could later explain calibration misses (K4.2 §2 meta-learning) but isn't required for that to function |
| Implementation risks | Scope creep — the requested field list is ten items long; recommend starting with the three or four fields `Planner`'s decisions can actually be shown to use (provider health, budget remaining, active capability set), adding more only with evidence, per the same "prove every field" discipline K1.6 already applied to `Resource` |
| Why not K4.2 | Several source fields (planner performance, calibration state) don't exist as meaningful data before K4.2 has run and accumulated real `EvaluationRecord`s; building the aggregator before the data exists is premature |

---

## 3. World Model

*Verdict: Mostly Architectural Observation; one small vocabulary extension Recommended*

| Dimension | Content |
|---|---|
| Motivation | OCBrain reasons about its operating environment (interpreter versions, repo structure, operational constraints), currently scattered across ordinary memory with no explicit "this is environment knowledge" typing |
| Architectural ownership | **Not a new subsystem.** Graph Memory (already specified, `OCBRAIN_FUTURE_ARCHITECTURE.md` §4.3.5.1, confirmed still not fully wired into the live path per K1.5 §0) plus L3 `KnowledgeEntry`, populated with a new content category — not a new storage mechanism |
| Interactions | Differs from User Model (facts *about the user*, not the environment); is a typed *subset* of general Memory, not a parallel store; **is** what the Knowledge Graph becomes once populated with this content type, not a separate index sitting beside it; differs from Capability Registry, which describes what OCBrain can *do*, not what *is true* |
| Governance | Unchanged — ordinary `memory_write` gate (Learning tier, K4.2 §8) for new facts; Evolution-tier only if a genuinely new environment-modeling *category*, not just a fact, is introduced |
| Replay | Unchanged — ordinary `KnowledgeEntry` versioning |
| Event model | No new events — ordinary memory-write events already cover this |
| Memory | One genuinely new piece: a recognized **causal** edge type (`causes` / `depends_on` / `enables`) in Graph Memory's relationship vocabulary, since neither existing type (`contradicts`/`supports`) captures causal structure |
| Learning | Reuses the existing Evolution Pipeline — no new mechanism |
| Implementation risks | Low, since almost nothing here is genuinely new; the real risk is treating this as license to build a new subsystem when the honest answer is "finish wiring Graph Memory as already planned" |
| Why not K4.2 | Entirely contingent on Graph Memory being wired into the live retrieval path — already known to not be true (K1.5 §0) and outside K4.2's own scope (Cognitive Front-End, not Memory) |

---

## 4. Meaning Representation Layer

*Verdict: Recommended, but K6+ rather than early K5 — gated on real evidence*

| Dimension | Content |
|---|---|
| Motivation | `Goal.structured_form` (K4.2 §4) is schema-validated but per-Goal and per-category — it provides no shared, stable representation *space* that different Goals can be positioned within, which genuine cross-goal operations (analogy, transfer, multilingual grounding) require. Directly informed by the already-reviewed research corpus: LITE's task-embedding approach, rat-sql's schema linking, tranX's grammar-constrained generation |
| Architectural ownership | A new, parallel embedding/representation space, analogous in *kind* to L2 Semantic Memory's existing embedding mechanism (`PROJECT_INSTRUCTIONS.md` §8.3) but indexing Intent/Goal artifacts rather than knowledge content — reuses L2's existing mechanism for a new content type, not a sixth memory layer |
| Interactions | Sits alongside, never instead of, `Goal.structured_form` — the schema-validated structure remains what `Planner`/`EvaluatorWorker` check against; the embedding is an additional index used only for cross-goal retrieval/comparison, never for validation |
| Governance | None new — a read-only retrieval index, same posture as L2 today |
| Replay | **The one real, non-obvious risk in this topic:** an embedding computed at time T from a model version available at T may not reproduce from a different model version later. Requires an explicit embedding-model-version field stored alongside every vector, so replay can distinguish "the representation changed because the model changed" from "the meaning genuinely differs" |
| Event model | One new event on index write, `cognitive.meaning_representation_indexed` — no new emission mechanism |
| Memory | A new, parallel, *derived and rebuildable* index — `Goal.structured_form`/`KnowledgeEntry` remain the source of truth |
| Learning | Could feed Active Concept Discovery (§5) — semantic clustering over this space is a plausible mechanism for that topic's merge/split operations. Worth sequencing this before Active Concept Discovery if both are pursued |
| Implementation risks | The highest-complexity item in this document — a real embedding/training pipeline, evaluation of whether it measurably improves the capabilities it targets, and the versioning discipline above |
| Why not K4.2 | `structured_form` already covers basic operation; no evidenced near-term need exists in the current roadmap for multilingual, analogical, or transfer capability specifically — building this speculatively ahead of that evidence is the premature-complexity pattern this project consistently declines |

---

## 5. Active Concept Discovery

*Verdict: Recommended, prerequisite-gated on K4.2's ontology evolution having real mileage*

| Dimension | Content |
|---|---|
| Motivation | K4.2's Evolution Pipeline (§8) is reactive/bottom-up — categories emerge from accumulated evidence, but nothing actively examines the whole ontology for merge/split/abstraction opportunities |
| Architectural ownership | An extension to `ReflectionWorker`'s already-established role ("critique outputs, detect inconsistencies, validate reasoning," K4 §7) — critique applied to the ontology itself, not a new worker type |
| Interactions | Merge/split reuse the existing deprecation/`supersedes` mechanism (K4.2 §8) — merged/split entries become `deprecated`, superseded by the new entry(ies); existing references resolve through the deprecation chain, never rewritten retroactively |
| Governance | **Higher-stakes than ordinary Evolution-tier promotion — a new, named safeguard:** merge/split of already-*verified* (not merely candidate) ontology entries must always require explicit human approval, never pass the ordinary auto-gated `ValidationGate` alone, given the larger blast radius (many past and future Goals reference the affected categories) |
| Replay | Identical requirement to K4.2 §8's existing one — unaffected by later merges/splits |
| Event model | `cognitive.ontology_node_merged` / `cognitive.ontology_node_split` — variants of the existing `cognitive.ontology_evolved` event (K4.2 §11), not a new namespace |
| Memory | None new — same L3 store, same versioning |
| Learning | This *is* a learning mechanism — Evolution-tier, reusing the shared `ValidationGate` a further time |
| Implementation risks | Incorrect merges are the primary risk — silently conflating two genuinely different categories degrades interpretation broadly, not just for one Goal. Mitigated by the mandatory-approval requirement above, not by automation alone |
| Why not K4.2 | Nothing meaningful to merge or split exists until the ontology has accumulated enough real, evidence-driven entries for structural patterns to be visible at all — sequenced strictly after K4.2's baseline Evolution Pipeline has run in production |

---

## 6. Hypothesis / Belief Revision

*Verdict: Split — cheap version Recommended (K5, near-term); formal version Speculative*

| Dimension | Content |
|---|---|
| Motivation | An impasse (K4.2 §5/§14) is currently treated as a *capability* gap; it never reconsiders whether the underlying *intent interpretation* was the actual problem, even though `Intent.alternatives` (K4.2 §2) sits there, already computed, unused once Planning begins |
| Architectural ownership | **Not a new subsystem** — a refinement to `SupervisorWorker`'s already-established Goal-refinement responsibility (K4.2 §4/§9/§14) |
| Interactions | On impasse or plan rejection, `SupervisorWorker` first checks whether promoting the next-ranked `Intent.alternatives` entry and re-running Goal Formation produces a more plannable `Goal`, before falling back to full re-interpretation or human escalation via `ClarificationPolicy` (K4.2 §2/§9) |
| Governance | None new — a specific strategy inside an already-governed retry path |
| Replay | Reuses the existing confidence-propagation and provenance chain (K4.2 §9/§10) — no new mechanism, just a new *reason* a Goal transitions to `refinement_pending` (K4.2 §13) |
| Event model | No new event strictly required — visible as an ordinary Goal-lifecycle transition correlated with the existing `cognitive.planner_impasse` and `cognitive.goal_refined` events (K4.2 §11) |
| Memory | None new |
| Learning | A recurring pattern ("hypothesis N was right whenever hypothesis 1 hit this kind of impasse") is a natural Evolution Pipeline input — noted as a future feed, not built separately |
| Implementation risks | Low for the cheap version. The *formal* version (explicit probability distributions, Bayesian updates in the style of `mindreader`'s probabilistic-programming approach, K4.2-R R2) is speculative, flagged, and not recommended pending evidence the cheap heuristic proves insufficient — e.g. domains with a large or continuous hypothesis space rather than a short discrete N-best list |
| Why not K4.2 | `Intent.alternatives` already survives to Plan Compilation (K4.2 §15's invariant); actively reconsidering them mid-Planning needs `SupervisorWorker` and the impasse pattern to exist and be exercised first — sequenced after, not parallel to, K4.2 |

---

## 7. Reasoning Strategy Selection

*Verdict: Recommended as a roadmap slot; not buildable until multiple real strategies exist*

| Dimension | Content |
|---|---|
| Motivation | `Planner._decompose()` (K4 §5, K4.2 §5) implicitly uses one fixed strategy today; genuinely selecting among strategies for different Goal shapes is a distinct, meta-level capability |
| Architectural ownership | **Reuses the existing Skill/Capability system — no new registry.** A reasoning strategy is a specially-tagged Capability (`capability_kind: "reasoning_strategy"`), registered in the same `CapabilityRegistry` (K1.5), discoverable via the same Capability Discovery mechanism (K4.2 §5/§8) — the meta-level twin of treating a Skill as an HTN-style "method" (K4.2 §5) |
| Interactions | Selection informed by `PlannerHint` plus whatever calibration data Self Model (§2) or `EvaluationRecord` history provides about which strategies performed well for similar Goal shapes — no new selection mechanism, reuses existing Capability Discovery matching |
| Governance | None new — ordinary Capability registration/validation (`SkillSpector`-style scanning, already established) applies identically |
| Replay | Identical to any other Capability selection — already captured in `ExecutionPlan.justification` (K4 §6) |
| Event model | No new events — `cognitive.capabilities_discovered` (K4.2 §11) already covers strategy-Capability resolution as a special case |
| Memory | None new |
| Learning | Strategy-performance-by-Goal-shape is a natural Adaptation-tier target once real data exists — feeds the shared `ValidationGate`, not a new mechanism |
| Implementation risks | Low architecturally, since it reuses everything. The real risk is premature scheduling: exactly one strategy is implemented today, so "selection" has nothing yet to select among |
| Why not K4.2 | No second or third strategy exists, and no evidence yet indicates which Goal shapes would benefit from which — a selector with one candidate isn't a selector |

---

## 8. Intent Semantics Preservation

*Verdict: Mostly Architectural Observation; one small Constraint-model extension Recommended*

| Dimension | Content |
|---|---|
| Motivation | The stated concern (Goal "book flight" losing Intent's true objective of cost minimization) is legitimate as stated, but K4.2's existing `Constraint` model already has a `kind: "soft"` category built for exactly this — "minimize cost" is a soft `Constraint`, not a gap |
| Architectural ownership | No new component. The one genuine, narrow gap: `Constraint` currently represents *satisfaction checks* ("was this honored"), not an *optimization objective* that actively drives ranking among multiple valid candidate plans |
| Interactions | A small, additive `Constraint` subtype (e.g. `relation: "optimizes"`) consumed by `_alternative_plans()`/`_estimate_confidence()` (K4 §5) when ranking otherwise-valid candidates — never a hard gate, which stays `EvaluatorWorker`'s correctness dimension |
| Governance | None new |
| Replay | None new — provenance-tracked exactly like any other `Constraint` (K4.2 §10) |
| Event model | None new — covered by the existing `cognitive.constraints_extracted` event (K4.2 §11) |
| Memory | None |
| Learning | None directly, though repeated objective-Constraint patterns for a given user are exactly what the User Cognitive Model (K4.2 §3) is already designed to accumulate |
| Implementation risks | Very low — an additive field on an existing, additive-by-design contract (Law of Contract Stability), not new architecture |
| Why not K4.2 | No evidence yet that plan-ranking-by-objective is needed in practice — K4.2's `_alternative_plans` ranking is confidence-based only today; add this once real usage shows that's insufficient, not speculatively |

---

## 9. Temporal Intent

*Verdict: Split — urgency/deadline/duration Architectural Observations; recurring/long-term objective surfaces one significant, deliberately under-specified Recommended item*

| Dimension | Content |
|---|---|
| Motivation | Intent carries temporal structure the current model doesn't explicitly name |
| Architectural ownership | **Urgency** → an existing `PlannerHint` kind (K4.2 §5) — nothing new. **Deadline** → an existing hard `Constraint` with a temporal predicate — nothing new. **Expected duration** → `Planner`'s own estimate on `ExecutionPlan`, not extracted from Intent — nothing new. **Recurring/long-term objective** → genuinely new: not representable by a per-request `Goal`'s lifecycle (K4.2 §13, which ends at `superseded`), since a standing objective persists across many future sessions rather than being closed by one |
| Interactions | The recurring/long-term case connects directly to the User Cognitive Model's already-specified `recurring_objectives` field (K4.2 §3) — today that field is *passive*, descriptive knowledge. What's raised here is whether it should become *active*: autonomously initiating future work when a recognized pattern recurs |
| Governance | **The one item in this entire document closest to tension with the stated principles, named rather than smoothed over.** Autonomous initiation from a recognized pattern is a materially different governance posture than responding to a request, and directly implicates the Law of Bounded Autonomy and the Law of User Sovereignty ("nothing is adopted, shared, or acted on without the user's visibility and, where consequential, consent"). A provisional name — `ProactiveInitiationGovernor` — is placed here only as a marker for future, dedicated design work. **It is not specified by this document, and nothing here should be read as having decided its shape** |
| Replay | No new implications for urgency/deadline/duration. For recurring/long-term objectives, *if* they ever trigger autonomous action, every triggered action needs the identical replayable justification as any human-initiated one — no exception for "the system decided on its own" |
| Event model | `cognitive.recurring_pattern_recognized` for the passive/observational side only (Learning-tier, safe) — deliberately no event for autonomous triggering, since that capability isn't being specified here |
| Memory | The passive side reuses the User Cognitive Model's existing `recurring_objectives` field — no new store |
| Learning | Passive recognition is an ordinary Learning-tier signal (K4.2 §8), reusing the shared pipeline |
| Implementation risks | Low for the passive/observational half. **High, and explicitly out of scope for this document, for the active/autonomous half** — named as a distinct, future, separately-gated capability, not bundled in as a simple field |
| Why not K4.2 | Urgency/deadline/duration need no new K4.2 work at all. Recurring/long-term objective *tracking* is representable today; *acting* on it autonomously is deliberately deferred pending its own dedicated governance design — the highest-stakes idea in this document, and it deserves a focused future pass, not a subsection here |

---

## 10. Cross-Cutting Findings

Three patterns recur across the eight topics, worth naming once rather than re-observing per topic:

**`PlannerHint` is almost always the right minimal extension point.** Self Model, urgency, and reasoning-strategy selection all resolve to "feed an existing advisory mechanism," not "build a new one." This is the strongest evidence in this document that K4.2's binding-Constraint/advisory-Hint split (K4.2 §5) was the correct design choice, not merely a convenient one.

**The shared `ValidationGate` (K4.2 §6/§16) keeps generalizing.** Skills, Intent Ontology, User Cognitive Model, and now (prospectively) Active Concept Discovery and Reasoning Strategy performance all reuse it. This is exactly the "one Evolution Pipeline, N content domains" principle K4.2 §3 already named explicitly — every new K5+ learning-adjacent capability should be checked against this gate before proposing a new one, not after.

**Roughly half of what was asked for is already built, contingent on two things finishing:** K4.2 itself shipping with real usage behind it (unblocks Active Concept Discovery, Belief Revision, Reasoning Strategy Selection, the Constraint-objective extension), and Graph Memory actually being wired into the live path (unblocks World Model) — a dependency that predates and sits outside K4.2 entirely.

---

## 11. Principle Compliance Check

Every **Recommended** item checked against the six stated principles; only deviations are called out, since silent compliance isn't informative on its own.

| Principle | Status |
|---|---|
| User Sovereignty | Holds for all Recommended items. The one flagged exception (Temporal Intent's autonomous half, §9) is explicitly *not* specified here for exactly this reason, and any future design must be opt-in-only per this same Law |
| Determinism | Holds — every item's replay implications were checked individually; Meaning Representation Layer's model-versioning requirement (§4) is the one place this needed an explicit new discipline, not just a restatement |
| Replayability | Holds — every item reuses the existing `derived_from`/`supersedes`/version-pinning mechanisms; none introduces a second history |
| Governance | Holds — every governed action reuses an existing gate or governor; the one new safeguard (Active Concept Discovery's mandatory-approval-on-merge/split, §5) is an *addition* to existing rigor, not a relaxation |
| Single Source of Truth | Holds — the shared `ValidationGate` finding (§10) is itself a direct instance of this principle applied prospectively, before three more copies could accumulate |
| Extension over Specialization | Holds — zero new Kernel components proposed anywhere in this document; every Recommended item is a field, an event, a rule inside an existing governor, or a reuse of an existing worker's role |

---

## 12. K5+ Roadmap Sketch — Speculative, Non-Binding

Offered as a sequencing sketch only, itself subject to the same evidence-gating this whole document applies to individual topics — not a committed roadmap.

```text
K5.1   Self Model (minimal field set: provider health, budget remaining,
       active capability set) — feeds Planner via existing PlannerHint
K5.2   Intent Semantics — objective-typed Constraint (small, additive)
K5.3   Hypothesis / Belief Revision (cheap version — SupervisorWorker
       reuse of Intent.alternatives on impasse/rejection)
K5.4   [external dependency] Graph Memory wired into live path
       (already-planned work, not new to this document)
       → unblocks: World Model content-typing + causal edge type
K5.5   Active Concept Discovery — gated on K4.2's Evolution Pipeline
       having real production mileage
K5.6   Reasoning Strategy Selection — gated on a second real strategy
       existing to select against
K6+    Meaning Representation Layer — evidence-gated; revisit only if
       multilingual/analogical/transfer needs are actually demonstrated
Flagged, not scheduled:
       Temporal Intent's autonomous/proactive-initiation half — needs
       its own dedicated governance-design document before any
       scheduling decision, per §9
```

---

## 13. What This Document Does Not Do

Stated explicitly, per the task's own framing: this document changes nothing in K4.2 — no contract, state machine, event name, or invariant from `OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` is revised. It proposes zero new Kernel components and zero new memory layers. It does not design `ProactiveInitiationGovernor` — it names the gap and the governing Laws that must constrain whatever eventually fills it, and stops there deliberately. It does not resolve the `[RECONCILE-PENDING]` status K4.2 §0 already flagged against K4.1-L/Service Architecture/Recursive Composition — anything above that touches Learning-Architecture-adjacent territory inherits that same open status.

---

*Future roadmap sketch complete. No code generated, no existing document modified, no K4.2 decision reopened. Ready for prioritization once K4.2 implementation (K4.2.1 onward) produces the real usage evidence several items above are explicitly gated on.*
