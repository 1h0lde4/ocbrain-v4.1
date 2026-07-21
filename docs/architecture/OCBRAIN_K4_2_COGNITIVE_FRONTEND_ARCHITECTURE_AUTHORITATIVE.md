# OCBrain K4.2 — Cognitive Front-End Architecture (Authoritative Specification)

**Date:** July 20, 2026
**Status:** AUTHORITATIVE — architecture freeze. Supersedes `OCBRAIN_K4_2_R_COGNITIVE_FRONTEND_RESEARCH.md` for all decisions restated or refined here. Zero code, zero implementation, zero repository modifications.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md` (11-law) and `PROJECT_INSTRUCTIONS.md`. Extends `OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` ("K4"), `OCBRAIN_K4_1_COGNITIVE_RUNTIME_FOUNDATION.md` ("K4.1"), and `OCBRAIN_K4_1_X_DELEGATION_ARCHITECTURE_AUTHORITATIVE.md` ("K4.1.x"). Nothing here contradicts any FINAL decision in those documents; every extension is marked as such.

---

## 0. Reconciliation & Basis — Read This Before Treating Anything Below as Settled

Per the mandatory first step, every document in `/mnt/project/` (this session's mirror of `docs/architecture/`) was reviewed before writing anything: the Constitution and its Rationale and Pressure Test, the Draft 0.9 predecessor, K1 (Kernel Audit), K1.5 (Service Model), K1.6 (Resource Model), K4, K4.1, K4.1.x, the three external-repo studies, `COMPLETE_UNIFIED_STUDY_V3.md`, `OCBRAIN_FUTURE_ARCHITECTURE.md`, and this session's own `OCBRAIN_K4_2_R_COGNITIVE_FRONTEND_RESEARCH.md`. That is the complete, verified set — confirmed by directory listing, not assumed.

**A real gap, reported rather than resolved silently.** This task names two source documents by title — "OCBrain K4 Final Learning Architecture" and "OCBrain K4.1 Final Learning Architecture" — that do not exist under those names, or any recognizably close name, anywhere in the reviewed set. The closest matches are `OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` (K4) and the K4.1 pair (Foundation + Delegation Authoritative). Separately, prior-session context (carried in working memory of this project, not as a document in hand) references three additional K4.1 documents by name — a "Cognitive Service Architecture" document, a "Recursive Service Composition" document, and a "K4.1-L" Cognitive Learning Architecture document — none of which are present in the reviewed set either. K4.1.x itself cites the first two as its own baseline ("`OCBRAIN_K4_1_COGNITIVE_SERVICE_ARCHITECTURE.md` ('the Service Architecture') and `OCBRAIN_K4_1_RECURSIVE_SERVICE_COMPOSITION.md` ('the Recursive Composition document')"), confirming they exist somewhere, just not here.

**Consequence, stated precisely.** Everything in this document about the Front-End's shape, the Intent/Goal/Constraint/Capability/Planner contracts, the Confidence Lifecycle, Provenance, Events, Data Contracts, State Machines, and Failure Handling is built directly from fully-reviewed source and is offered as authoritative now. Section 6 (Learning Architecture) and the Cognitive Service-internals references throughout are **reconstructed** from K4 §7/§13, the already-adopted Instinct→Skill/SkillOpt pipeline, K4.1.x's summary of Delegation policy, and this session's own K4.2-R findings — not from a full read of K4.1-L or the Service Architecture document. Anywhere this reconstruction might plausibly conflict with content in those unseen documents, it is flagged inline with a **[RECONCILE-PENDING]** marker rather than presented as settled. **Recommendation:** supply K4.1-L, the Service Architecture document, and the Recursive Composition document for a short, targeted reconciliation pass before this document's Learning Architecture and Service-facing sections are treated as equally final to the rest. Nothing below should block that pass, and nothing below is expected to require a large revision if that pass finds a genuine conflict — the reconstruction was done conservatively, reusing existing mechanisms rather than inventing new ones, for exactly this reason.

---

## 1. Cognitive Front-End — Top-Level Specification

**Responsibilities.** Unchanged from K4 §1's Core Principle: the Cognitive Front-End decides what should happen; the Kernel makes it happen, governed and replayably. The Front-End owns intent interpretation, goal formation, and (inside `Planner`) constraint extraction, capability discovery, decomposition, and sequencing. It owns none of: memory persistence, governance enforcement, workflow/capability execution, or event persistence.

**Boundaries.** The Front-End's only path to real-world effect is the single seam K4 §1/§6 already established: `ExecutionPlan` → Plan Compilation (K4.3, unchanged) → `WorkflowDefinition` → Kernel execution. Nothing in this document opens a second seam.

**Subsystems.** Five pipeline stages, realized inside the seven components K4 §3 already fixed (Intent Interpreter, `Planner`, Plan Compiler, ReflectionWorker, EvaluatorWorker, SupervisorWorker, `CognitiveContext`) plus one new cross-cutting resource, the User Cognitive Model (§3), which is a memory projection, not an eighth component:

| Stage | Owner | Component count change |
|---|---|---|
| Input Normalization | `Intent Interpreter` | None — sub-step |
| Intent Interpretation | `Intent Interpreter` | None — sub-step |
| Goal Formation | `Intent Interpreter` | None — sub-step (K4.1 §2 already places Goal-minting here) |
| Constraint Extraction | `Planner` | None — sub-step |
| Capability Discovery | `Planner` | None — sub-step |
| Decomposition/Sequencing | `Planner` | None — unchanged from K4 §5 |

Zero new Kernel-registered components. Every addition in this document is either a new field on an existing artifact, a new sub-step inside an existing method, or a new rule inside an existing governor — the same discipline K4.2-R §4.2 already applied, held constant here.

**Lifecycle.** The Front-End shares the Cognitive Runtime's three-state service lifecycle (`INITIALIZING` → `READY` → `SHUTTING_DOWN`, K4.1 §7) verbatim. It does not get its own.

**Interfaces — extended from two to three, with justification.** K4 §1 named two public entrypoints ("two, deliberately"): `plan(goal) -> ExecutionPlan` and `compile(plan) -> WorkflowDefinition`. Neither is revised. A third is now formalized: **`interpret(raw_request) -> Goal`**, covering Input Normalization → Intent Interpretation → Goal Formation. This is not a reopening of "two, deliberately" — K4 §1 named the two entrypoints that existed once `Planner` and Plan Compiler had been specified; it never claimed no third could exist, and K4.1 §2 already noted Applications hand the Front-End "an unstructured request," implying an entry point for exactly this without formalizing its signature. `interpret()` closes that gap. **The seam count is unchanged** — `interpret()` and `plan()` never touch Kernel execution; only `compile()` does. Full public surface, fixed at three: `interpret()`, `plan()`, `compile()`.

---

## 2. Intent Interpreter

Not a classifier. A governed cognitive subsystem whose sole output is a `Goal` (via `Intent`), carrying its own confidence and provenance at every step.

**Input Normalization.** The one sub-step that is ordinary, deterministic code — not model-assisted reasoning — by deliberate design: it is the seam where arbitrary, possibly adversarial input first enters the system, and Law of Determinism plus LAW 3 (Isolation) both favor a narrow, auditable, non-LLM function here. Responsibilities: encoding/whitespace normalization, modality detection, and a lightweight prompt-injection/malformed-input screen — reusing the same screening discipline already adopted for the Knowledge Acquisition pipeline (`OCBRAIN_EXTERNAL_REPO_STUDY.md` §5, Skill_Seekers-derived), now applied at the *front* door instead of only the knowledge-ingestion door. Output: a canonical `RawRequest`. Rejected input (malformed, injection-flagged) never reaches Intent inference — logged as a distinct failure category (§14), not silently passed through with degraded confidence.

**Intent inference — multi-hypothesis, not single-label.** Produces a ranked N-best `IntentHypothesis` list (§12), reusing the existing `context_assembler`/`RetrievalFusionEngine` path for context — no new retrieval mechanism. Per K4.2-R §3 Finding 1 (validated independently by rat-sql's schema linking and tranX's grammar-constrained generation), hypotheses are scored against the Intent Ontology's structured categories where a match exists, and degrade to a looser, lower-confidence open-category hypothesis where none does — never to unstructured free text as the *only* representation.

**Multi-dimensional intent representation.** `Intent.dimensions` is deliberately small — `category` (matched ontology entry, or "novel"), `modality` (`task_request` | `information_query` | `feedback_on_prior_interaction` | `clarification_response`), `complexity_estimate` (a cheap, coarse signal `Planner` may consume as a `PlannerHint`, §5). A larger dimension set was considered and rejected: no evidence anywhere in the reviewed corpus supports more granularity than this, and inventing it now would repeat exactly the mistake K1.6 §2 already flagged and avoided for `Resource` fields ("prove every field or reject it").

**Confidence estimation.** Per-hypothesis `score`, plus one `selected` hypothesis and a `confidence` value for it. Calibration (predicted-confidence vs. actual-outcome) is EvaluatorWorker's existing responsibility (K4 §8, Metaculus/Brier-inspired), not reimplemented here.

**Multiple competing hypotheses.** Carried as `Intent.hypotheses`, never discarded before Plan Compilation (this is the new invariant already stated in K4.2-R §5.1 and reaffirmed in §15 below).

**Clarification policy.** No dedicated clarification gate — **reaffirmed, not re-derived**, from K4.2-R §4.5's reasoning: low confidence propagates through `Goal.confidence` into `ExecutionPlan.confidence`; the *existing* Plan Compilation gate (K4 §15) carries one new `OrchestrationGovernor` rule that can `ESCALATE` on low confidence; `SupervisorWorker`'s existing escalation-surfacing shows the human a concrete plan with its stated interpretation, not an abstract disambiguation question. This document formalizes the rule itself as a named, versioned **`ClarificationPolicy`** — Policy data (Constitution glossary: "a specific, declared rule constraining what a capability or resource may do"), owned by `GovernanceKernel` like any other Policy, evaluated by the `OrchestrationGovernor` rule, not a new component or a new gate. See §9 for the full confidence-propagation model and §14 for the bounded-retry safeguard this policy requires.

**Intent selection.** `Intent.selected` defaults to the top-ranked hypothesis; if escalation occurs and the human clarifies, `selected` is overwritten with the clarified result and the event trail (§11) preserves both the original ranking and the correction, satisfying provenance (§10) without any special-cased storage.

**Intent memory.** Session-current `Intent` lives in `CognitiveContext` (K4.1 §6, unchanged). Raw history continues in L1 Episodic Memory exactly as before. Promoted patterns live in L3 as Intent Ontology entries (§6, §8) — no new memory layer.

**Intent provenance.** `derived_from` (K1.6 convention) plus the originating event's correlation ID — reused, not reinvented.

**Intent learning / evolution / ontology evolution.** Specified fully in §6 (Learning Architecture) and §8 (Evolution); cross-referenced here rather than restated.

**Meta-learning — scoped narrowly and deliberately.** Defined as learning that adjusts the *tunable parameters of the learning pipeline itself* — confidence thresholds, clustering parameters for instinct→ontology promotion — informed by whether past promotions actually improved calibration (the same Brier-style tracking EvaluatorWorker already does, K4 §8). Meta-learning **never** touches structural mechanisms (the pipeline shape, the gate algorithm, the governor set) — only their parameters — and is itself gated through the identical governance path as everything else in §8, via one new action-type string: `meta_parameter_adjust`. This is the narrowest possible scope that still satisfies the directive's requirement, deliberately, per Law of Evidence over Assumption: nothing in the reviewed corpus supports a broader mandate.

**Failure modes.**

| Mode | Handling |
|---|---|
| No hypothesis clears the confidence floor | Proceeds with the highest-scored hypothesis anyway (never a hard stop at this stage — cheap, local reasoning continues); confidence is low enough that `ClarificationPolicy` will very likely escalate at Plan Compilation |
| Near-tied top hypotheses | Both carried as `alternatives`; `Planner` may explore more than one in parallel if budget allows, or proceeds on the top-ranked with alternates logged for Reflection |
| Malformed/adversarial input | Rejected at Input Normalization, before Intent inference runs at all; logged as a distinct failure category, never reaches `Planner` |

---

## 3. User Cognitive Model

**What it is, structurally.** Not a new `Resource`, not a new registry, not a standalone artifact with its own identity and lifecycle. It is a **read-mostly projection** — the same shape K1.6 §3 already established for `Context`/`ContextBlock` and K4.1 §6 already established for `CognitiveContextView`: assembled fresh (or cached with a short TTL, purely as a performance measure) from querying **L1 raw preference/pattern signals and L3 promoted preference/pattern `KnowledgeEntry` records**, never a live, independently-persisted object of its own. This keeps the "don't invent a new artifact type when memory already covers it" discipline intact for a third domain (Skills, Intent Ontology, now User preferences).

**Contents (fields, illustrative):** per-domain `expertise` (not global — a user may be expert in one area and a novice in another), `terminology_preferences`, `preferred_abstraction_level`, `communication_style`, `preferred_output_formats`, `recurring_objectives`, `behavioral_patterns` — each backed by one or more L3 `KnowledgeEntry` records with `procedure_name` scoped to a `user_model:*` namespace, `truth_status` in the existing Truth Framework, and `derived_from` pointing at the qualifying interaction history.

**How it evolves.** The identical Evolution Pipeline used for Skills and the Intent Ontology (§8), applied a third time to a third content domain — instinct accumulation from session behavior → periodic clustering → SkillOpt-style validation gate → governed promotion. This genericity is a deliberate, named design principle, not three coincidentally-similar mechanisms: **one Evolution Pipeline, three content domains.** Restated once here; not re-derived per domain.

**How it influences interpretation.** Consulted **read-only** during Intent Interpretation and Goal Formation as context that biases hypothesis ranking and schema selection toward the user's known terminology and patterns. It is never the sole determinant of a hypothesis's rank, and every case where it materially shifted a ranking is provenance-tracked (§10) — so a wrong interpretation traceable to an over-fit User Cognitive Model entry is correctable, not silently repeated.

**Governance boundaries.** Reads: ungated, ordinary memory search (same as any context assembly). Writes (promotion of new/revised entries): gated identically to Intent Ontology promotion, via two new `EvolutionGovernor.SELF_MODIFYING_ACTIONS` strings — `user_model_propose`, `user_model_promote`.

**Privacy guarantees.** Three, stated as invariants, not aspirations: (1) fully inspectable and deletable by the user at any time — a direct instance of the Law of User Sovereignty ("the user... owns everything it knows"); (2) **excluded by default from any future cross-instance advisory mechanism** (the Constitution Pressure Test's "Cross-Instance Advisory Layer," §8, `OCBRAIN_KERNEL_CONSTITUTION_PRESSURE_TEST.md` §2 tension 3, §12 risk 4) — this is a concrete, useful boundary given that mechanism's own sovereignty-erosion risk is explicitly still open and unresolved; (3) governed by the same write-path as everything else — no separate, ungoverned "personalization" backdoor.

---

## 4. Goal Formation

**Goal object:** per K4.2-R §4.4/§4.6, `structured_form` is schema-validated against the matched Intent Ontology category, never a bare NL string internally; degrades to a looser structure with lower confidence when no match exists.

**Goal hierarchy — distinguished precisely from `Planner`'s decomposition, which is a different granularity.** A single compound *request* may mint more than one Goal at Goal Formation time (`Goal.sub_goals: List[str]`, references only) when the request is already recognizable as independently-plannable pieces — e.g., "audit the memory system and then propose a migration plan" is two Goals before `Planner` ever runs. `Planner`'s own decomposition (K4 §5, unchanged) operates **within** one Goal, breaking it into ordered `PlanStep`s. Conflating these two levels was a real risk worth naming explicitly and closing.

**Goal refinement.** Two paths, both reusing existing mechanisms: (1) the governance-escalation/clarification path (§2, §9) when confidence is low; (2) `SupervisorWorker` handing a revised Goal back to `Planner` after a rejected or failed Plan Compilation (K4 §9/§15, unchanged) — never the same rejected artifact resubmitted as-is (K4 §16's existing invariant, unchanged).

**Goal validation.** `EvaluatorWorker`'s correctness dimension, extended (as already noted in K4.2-R §4.7) with schema-validation against the matched ontology entry's grammar.

**Goal confidence.** Inherited from `Intent.confidence`, adjusted by the validation outcome above. Full propagation model in §9.

**Goal evolution — distinguished from Intent Ontology evolution.** Intent Ontology evolution (§6, §8) discovers **new categories**. Goal evolution is narrower: refining the **schema** already associated with an *existing* category (e.g., discovering that a "security audit" goal category needs an optional `scope` field it didn't originally have). This is Adaptation-tier, not Evolution-tier, in the §8 taxonomy — refining within a category is a materially lower-stakes change than discovering a new one, and the governance weight should reflect that.

**Intent → Goal relationship.** One Intent mints one or more Goals (via the hierarchy split above); every Goal carries `intent_id` provenance back to the Intent that produced it. Unchanged from K4.1 §2's original placement, now fully specified.

---

## 5. Planner Interface

`Planner` receives structured cognitive artifacts — never raw language — per instruction. This section specifies the contract; K4 §5's internal pseudocode (`_decompose`, `_sequence`, `_fallback_paths`, `_estimate_confidence`, `_alternative_plans`, `_justify`) is unchanged, and `_extract_constraints`/`_select_capabilities` remain internal (K4.2-R §4.2's Gate-1 reasoning, reaffirmed rather than re-litigated).

**Planner contract:** `Planner.plan(request: PlannerRequest) -> PlannerResult` (formalizes K4 §1's already-named `plan(goal) -> ExecutionPlan` public entrypoint with a fuller input/output shape).

**Planner inputs — `PlannerRequest` (illustrative):**

```text
PlannerRequest:
    goal_id:        str
    goal:            Goal              # or a resolved reference
    context_view_ref: str               # a CognitiveContextView (K4.1 §6) — never embedded
    hints:            List[PlannerHint]  # advisory, never enforced — see below
```

**Planner hints — new, and deliberately distinct from `Constraint`.** A `Constraint` (§4.7 of K4.2-R, unchanged) is **binding and checkable** — `EvaluatorWorker` can fail a plan against it. A `PlannerHint` is **advisory only** — it influences `Planner`'s own internal choices (how many `_alternative_plans` to generate, whether to bias toward speed vs. thoroughness) but is never validated or enforced, and a plan can never "fail" a hint, only under- or over-weight it. Sourced from `Intent.dimensions.complexity_estimate` and from the User Cognitive Model (§3) — e.g., a user who consistently prefers terse answers yields a `PlannerHint` biasing toward fewer, more direct steps. Keeping this distinction crisp prevents hints from silently becoming a second, unaccountable constraint system.

```text
PlannerHint:
    kind:    str    # e.g. "prefer_speed", "prefer_thoroughness", "prefer_terse_output"
    weight:   float  # advisory strength, never a hard threshold
    source:   str    # "intent_dimension" | "user_model"
```

**Planner outputs — `PlannerResult` (illustrative):**

```text
PlannerResult:
    status:            str    # "ready_for_compilation" | "impasse" | "rejected_precheck"
    execution_plan:      Optional[ExecutionPlan]   # present iff status == ready_for_compilation
    impasse_detail:       Optional[ImpasseRecord]    # present iff status == impasse — see §4.9, K4.2-R
```

**Constraint handling.** Unchanged from K4.2-R §4.7 — `_extract_constraints(goal)` produces the `List[Constraint]` attached to the in-progress `ExecutionPlan`, sourced explicit/inferred/policy.

**Capability requests.** Unchanged from K4.2-R §4.8 — one `CapabilityRequest` per sub-goal, resolved against the existing `CapabilityRegistry`/`CognitiveService` Registry pair, never a third registry.

**Failure handling.** An empty or all-below-threshold capability resolution, or a decomposition that can't complete within budget, produces `status: "impasse"` — routed through the Soar-derived impasse→subgoaling pattern (K4.2-R §4.9, unchanged): `Planner` inserts a "resolve this impasse" `PlanStep`, which may in turn delegate to a skill-creation-capable `CognitiveService` per the K4.1 §9 walkthrough. `status: "rejected_precheck"` covers cases `Planner` can determine are hopeless before even attempting decomposition (e.g., a Goal whose hard `Constraint`s are mutually contradictory) — surfaced immediately rather than spending a full decomposition attempt on a provably-unsatisfiable Goal.

**Boundary, stated once, precisely.** Three owners, three artifacts, one seam each: Intent Interpreter owns everything up to `Goal`; `Planner` owns everything from `Goal` to `ExecutionPlan`; Plan Compiler (K4.3, unchanged) owns everything from `ExecutionPlan` to `WorkflowDefinition`.

---

## 6. Learning Architecture

**[RECONCILE-PENDING — see §0.]** Reconstructed from K4 §7/§13, the already-adopted Instinct→Skill/SkillOpt pipeline, and K4.2-R §4.10 — not from a full read of K4.1-L.

Eight requested signal sources, each mapped to a concrete mechanism, all funneling into the single Evolution Pipeline (§8):

| Source | Mechanism | Trust |
|---|---|---|
| Explicit corrections | HITL modify/reject events at the Plan Compilation gate (K4 §15) | Highest |
| Implicit feedback | Whether the user proceeds without complaint vs. immediately re-corrects | Lower — inferred, not stated |
| Execution outcomes | `EvaluatorWorker`'s `EvaluationRecord` | High |
| Planner replanning | `SupervisorWorker`'s retry-via-reinvocation events, correlated to detect recurring triggers | Medium |
| User behavior | User Cognitive Model evolution (§3) | Medium |
| Long-term usage | Intent/Goal Ontology evolution (§8) | Medium |
| Reflection | `ReflectionWorker`'s `ReflectionRecord` | High |
| Governance validation | The gate every signal above must clear before promotion — see below | N/A (this *is* the gate) |

**Determinism and auditability, stated as mechanism, not aspiration.** Every signal above is an Event (Law 2) before it is ever a memory write. Every promotion is a `UnifiedMemory.write()` call under `GovernanceKernel` (K4 §13's existing pattern). Nothing learns silently: an entry either passed the validation gate and was written, with its full trigger-signal trail intact via `derived_from`, or it wasn't written at all.

**One shared gate, not three parallel copies — a named risk, closed here.** Skills (v4.3.9), the Intent Ontology (§8), and the User Cognitive Model (§3) all reuse "the SkillOpt-style validation gate." If implemented as three independent copies of the same accept/reject logic, that's exactly the kind of hidden duplication `PROJECT_INSTRUCTIONS.md` §20.5 warns against and a Law of Single Source of Truth violation waiting to happen. **This document specifies one shared `ValidationGate` function, parameterized by content-domain, used by all three promotion paths.** Flagged explicitly in Final Validation (§16) as the risk it closes.

---

## 7. Cognitive Memory

No new memory layer. Every requested memory type maps onto the existing L0–L4 model (`PROJECT_INSTRUCTIONS.md` §8.1):

| Requested type | Maps to |
|---|---|
| Intent Memory | Session-current: `CognitiveContext`. Raw history: L1. Promoted patterns: L3 (Intent Ontology, §8) |
| Goal Memory | Same shape as Intent Memory, one level down |
| Preference Memory | Raw signals: L1 (individual events). Promoted: L3 (User Cognitive Model entries, §3) |
| Pattern Memory | **Not a fourth thing** — the collective name for L3 procedural/ontology entries across all three domains (Skills, Intent Ontology, User Cognitive Model) |
| Provenance | `ProvenanceRecord` + `derived_from` chains (K1.6, K4 §7) — unchanged |
| Retrieval strategy | Existing hybrid BM25 + semantic + RRF (`PROJECT_INSTRUCTIONS.md` §8.3), unchanged. One additive signal: intent-category matching may also consult a learned task-embedding (per the LITE precedent, K4.2-R R1) alongside BM25/semantic — an additional ranking input, not a new retrieval mechanism |
| Memory consolidation | `MemoryCuratorWorker`'s existing active-memify methods (`prune_stale`, `strengthen_high_access`, `resolve_contradictions` — K4 §4/§15), now also operating over Intent Ontology and User Cognitive Model entries, not only general knowledge |
| Forgetting policy | Same decay-unless-reaffirmed mechanism as general L1 importance decay (`PROJECT_INSTRUCTIONS.md` §8.4) — unreaffirmed Intent/Preference entries decay in confidence over time, consistent with the independently-converged "active memory improvement" pattern (`OCBRAIN_FUTURE_ARCHITECTURE.md` Pattern 4; also independently rediscovered by unrelated small projects noted in `OCBRAIN_EXTERNAL_REPO_STUDY_V3.md`'s Helix-AGI finding) |
| Evolution policy | See §8 — not duplicated here |

---

## 8. Evolution

Mandatory section. Three tiers, escalating governance weight, one shared mechanism underneath (§6):

| Tier | What changes | Example | Governance |
|---|---|---|---|
| **Learning** | New instance data within existing categories/schemas | A session's Intent matches an existing ontology category; a raw preference signal is recorded | Existing `memory_write` gate only (K3.5) — routine |
| **Adaptation** | Parameters of an existing category/schema tuned | Confidence threshold recalibrated (meta-learning, §2); an ontology entry's schema gains an optional field (Goal evolution, §4); a User Cognitive Model entry strengthened by repeated confirmation | Shared `ValidationGate` (§6) — accept only on strict, held-out improvement |
| **Evolution** | A new category/structure is created | A genuinely novel Intent Ontology category is promoted; a new Skill is created to resolve an impasse | `ValidationGate` **and** `EvolutionGovernor.SELF_MODIFYING_ACTIONS` **and**, for anything touching Constitution/Kernel-level structure, the Part VIII amendment process — never automatic |

**Discovery of new intent/goal archetypes; ontology evolution.** Both Evolution-tier, both the same instinct-accumulation → clustering → gate → promote pipeline (§6), generalized once and reused across content domains rather than re-specified per domain.

**Promotion criteria.** Strict improvement on a held-out score (SkillOpt's own gating algorithm, already adopted) **plus** a contradiction-check against Graph Memory before write (K4.2-R's R7 finding) — an Evolution-tier candidate that would silently supersede a verified entry is blocked, not promoted quietly.

**Governance approval.** Tier-appropriate per the table above — never uniform, never skippable.

**Rollback strategy.** Every promotion is a versioned `KnowledgeEntry` write carrying `supersedes`, logged immutably to L4. Rollback is a new write that restores the prior `truth_status`/content and marks the promoted entry `deprecated` — history is never deleted, only superseded (the same deprecation-not-deletion discipline the Constitution Pressure Test already established for contract changes, Law of Contract Stability, applied here to memory content instead of interfaces).

**Evolution must never violate kernel determinism — the concrete requirement, not just the slogan.** An Evolution-tier change may alter what *future* requests resolve to; it must never retroactively change the recorded justification for a *past* decision. This has a specific technical consequence: **`EventStream` replay must resolve any memory lookup against the `KnowledgeEntry` version that was active at the time the original event occurred, not the current version.** Every promoted/superseded entry therefore needs a timestamp or version marker a replay can pin to — this is a requirement on the existing replay mechanism, not a new one, and is called out explicitly in §16.

---

## 9. Confidence Lifecycle

A single propagation chain, stated once, referenced everywhere else rather than re-derived:

```text
Intent.hypotheses[i].score  (per-hypothesis, from Intent Interpretation)
        │
        ▼  (selected hypothesis's confidence, inherited)
Goal.confidence  (adjusted by schema-validation outcome, §4)
        │
        ▼  (informs, alongside capability-match quality and decomposition completeness)
ExecutionPlan.confidence  (Planner._estimate_confidence(), K4 §5, unchanged)
        │
        ▼  (evaluated by the ClarificationPolicy rule, §2)
[ Plan Compilation governance gate — may ESCALATE here, K4 §15 ]
        │
        ▼  (Kernel Execution — "confidence" is not a Kernel-layer concept; K4 §16's
        │   "execution never plans/reasons" invariant means execution either
        │   succeeds or fails, it does not carry a confidence value of its own)
EvaluationRecord.actual_outcome  vs.  EvaluationRecord.predicted_confidence
        │        (post-hoc comparison — this IS calibration, K4 §8, unchanged)
        ▼
ReflectionRecord  (may propose an Adaptation-tier confidence-threshold
                   recalibration if systematic miscalibration is detected —
                   routed through meta-learning, §2, §8)
```

**How confidence influences clarification.** Fully answered by §2's `ClarificationPolicy`: the *only* point confidence can trigger a human-facing pause is the existing Plan Compilation gate. No other stage in this chain independently decides to interrupt.

---

## 10. Provenance

| Artifact | Provenance mechanism |
|---|---|
| Intent | `derived_from` + originating event correlation ID |
| Goal | `intent_id` (§4) + `derived_from` |
| Constraints | `Constraint.source` (explicit/inferred/policy) + `rationale` field (K4.2-R §4.7, unchanged) |
| Capability selection | `CapabilityRequest.description` + the resolved candidate's own registry entry, correlated via the `cognitive.capabilities_discovered` event (§11) |
| Planner decisions | `ExecutionPlan.justification` (K4 §6, unchanged) + `PlannerResult.impasse_detail` where applicable |

No new provenance mechanism anywhere in this table — every row reuses `derived_from`, `ProvenanceRecord`, or an existing field. This is deliberate: provenance that requires its own bespoke storage per artifact type is itself a Single-Source-of-Truth risk.

---

## 11. Event Integration

**Reconciliation note.** The directive's example event names (`IntentDetected`, `IntentClarified`, `GoalCreated`, `GoalRefined`, `IntentLearned`, `IntentOntologyExtended`, `PreferenceUpdated`) use PascalCase with no namespace. K4 §12 already established a deliberate, existing convention — dot-namespaced, snake_case, `cognitive.*` — consistent with the Kernel's own `workflow.*` events. Per Constitution Law of Single Source of Truth, this document maps every requested event onto the existing convention rather than introducing a second naming scheme:

| Requested (directive) | Actual event name | Status |
|---|---|---|
| IntentDetected | `cognitive.intent_interpreted` | Already exists (K4 §12) |
| — | `cognitive.intent_hypotheses_generated` | Already added (K4.2-R §4.13) |
| IntentClarified | `cognitive.intent_clarified` | **New** |
| GoalCreated | `cognitive.goal_formed` | Already exists (K4 §12) |
| GoalRefined | `cognitive.goal_refined` | **New** |
| — | `cognitive.constraints_extracted` | Already added (K4.2-R §4.13) |
| — | `cognitive.capabilities_discovered` | Already added (K4.2-R §4.13) |
| — | `cognitive.planner_impasse` | **New** — emitted on `PlannerResult.status == "impasse"` |
| IntentLearned | `cognitive.pattern_learned` | **New** — generalized across Skills/Intent Ontology/User Model (Learning tier, §8) |
| IntentOntologyExtended | `cognitive.ontology_evolved` | **New** — generalized (renamed from K4.2-R's narrower `cognitive.intent_ontology_evolved` to cover all three Evolution-tier domains under one name) |
| PreferenceUpdated | `cognitive.user_model_updated` | **New** |

All emit through the existing worker-lifecycle event path (K4.1 §9) — no new emission mechanism.

---

## 12. Data Contracts

Illustrative fields only, per this document's own architecture-only scope — not frozen implementation schemas.

```text
Intent (CognitiveArtifact):
    resource_id, raw_request, hypotheses: List[IntentHypothesis],
    selected: IntentHypothesis, confidence: float,
    dimensions: {category, modality, complexity_estimate},
    ontology_ref: Optional[str], derived_from: List[str],
    lifecycle_state: str

IntentHypothesis:
    label: str, embedding_ref: Optional[str], score: float

Goal (CognitiveArtifact):
    resource_id, intent_id, structured_form: dict,
    sub_goals: List[str], alternatives: List[str],
    confidence: float, lifecycle_state: str

Constraint (embedded, not a Resource):
    kind: "hard"|"soft", relation: "satisfies"|"partially_satisfies"|"conflicts_with",
    source: "explicit"|"inferred"|"policy", rationale: str,
    validated_by: Optional[str]

CapabilityRequest (ephemeral parameter object):
    subgoal_ref, description, applicable_constraints: List[Constraint],
    context_view_ref

PlannerRequest (ephemeral parameter object):
    goal_id, goal: Goal, context_view_ref, hints: List[PlannerHint]

PlannerHint (embedded, not a Resource):
    kind: str, weight: float, source: "intent_dimension"|"user_model"

PlannerResult (ephemeral parameter object):
    status: "ready_for_compilation"|"impasse"|"rejected_precheck",
    execution_plan: Optional[ExecutionPlan], impasse_detail: Optional[ImpasseRecord]

CognitiveDecision (the shared shape logged at ANY GovernanceKernel evaluation
                    originating from the Cognitive Front-End — generalizes
                    plan_compile, intent_ontology_promote, user_model_promote,
                    meta_parameter_adjust into one consistent log shape):
    action_type: str, subject_ref: str, verdict: "proceed"|"reject"|"escalate",
    reason: str, evaluated_at: timestamp

LearningRecord (the shared shape produced by any Learning/Adaptation/
                Evolution-tier event, §8):
    tier: "learning"|"adaptation"|"evolution", content_domain: str,
    trigger_signals: List[str], gate_result: CognitiveDecision,
    resulting_entry_ref: Optional[str]
```

`Intent` and `Goal` satisfy the K1.6 Resource Protocol. `Constraint` and `PlannerHint` are embedded field-sets, not independently identified. `CapabilityRequest` and `PlannerRequest`/`PlannerResult` are ephemeral parameter objects (K1.6's fourth category) — constructed, consumed, discarded within one invocation. `CognitiveDecision` and `LearningRecord` are log/record shapes, written as part of an Event or a `KnowledgeEntry`, not independent Resources with their own registry.

---

## 13. State Machines

**Intent lifecycle:**
`draft → interpreted → [clarification_pending → clarified] → superseded`
(`clarification_pending`/`clarified` only entered if `ClarificationPolicy` escalates, §2/§9; otherwise `interpreted → superseded` directly once its `Goal` is formed.)

**Goal lifecycle:**
`draft → verified → [refinement_pending → refined] → compiled → superseded`
(`refinement_pending`/`refined` only entered on validation failure or Supervisor-driven revision, §4; `compiled` is set once Plan Compilation, K4.3, accepts the resulting `ExecutionPlan`.)

**Learning lifecycle** (shared across all three Evolution-tier content domains, §6/§8):
`observed → accumulated (instinct) → candidate (clustered) → gated (in ValidationGate) → [promoted | rejected]`
(`promoted` entries may later transition to `deprecated` via the rollback mechanism, §8 — never deleted.)

Each state transition is an Event (Law 2) — no silent transitions anywhere in any of the three machines.

---

## 14. Failure Handling

| Failure mode | Handling |
|---|---|
| Ambiguity (low/tied confidence) | Carried as `alternatives`; resolved via `ClarificationPolicy` at Plan Compilation if it crosses the escalation threshold (§2, §9) — never resolved by silently picking a winner without logging the alternates |
| Conflicting goals (within one compound request) | Split at Goal Formation via `Goal.sub_goals` (§4) rather than forced into one incoherent Goal; each planned independently |
| Missing information | Surfaces as low `Goal.confidence` (incomplete `structured_form`) — same path as ambiguity, not a separate mechanism |
| Planner rejection (`status: "rejected_precheck"`) | Provably-unsatisfiable Goal (e.g., contradictory hard `Constraint`s) — surfaced immediately, no wasted decomposition attempt |
| Planner impasse (`status: "impasse"`) | Soar-derived impasse→subgoaling (K4.2-R §4.9) — routes through Capability Discovery and, if nothing resolves it, Skill Runtime delegation (K4.1 §9) |
| Governance rejection | `GovernanceVerdict.REJECT`/`ESCALATE` at Plan Compilation (K4 §15, unchanged) |
| Clarification loops | **New safeguard, specified here:** the escalation path is itself bounded — a `Goal` that has already been through one clarification cycle and is escalated again on the *same underlying ambiguity* is not re-escalated indefinitely; it is handed to `SupervisorWorker` as a stalled case after a small, configured retry ceiling, reusing `RecursionGovernor`'s existing bounded-loop principle rather than inventing a second one |
| Recovery | `SupervisorWorker`'s existing retry-via-reinvocation (K4 §9) for execution-side failures; Goal refinement (§4) for reasoning-side failures — never the same rejected artifact resubmitted unchanged (K4 §16, unchanged) |

---

## 15. Implementation Roadmap

```text
K4.2.1  Intent Interpreter — Input Normalization + multi-hypothesis
        Objective:    canonical RawRequest -> ranked, confidence-scored
                        IntentHypothesis list
        Modules:       core/cognitive/intent.py (new: normalization,
                        hypothesis generation)
        Interfaces:     Intent, IntentHypothesis dataclasses (§12)
        Dependencies:    none beyond existing context-assembly path
        Validation:      given a fixed query set, produces stable, well-formed
                        hypothesis lists; malformed-input fixture set is
                        rejected at normalization, never reaches inference

K4.2.2  Goal Formation — structured representation + hierarchy
        Objective:    Intent -> one or more Goal objects, schema-validated
                        against Intent Ontology where matched
        Modules:       core/cognitive/intent.py (Goal Formation logic)
        Interfaces:     Goal dataclass (§12), interpret() public entrypoint (§1)
        Dependencies:    K4.2.1
        Validation:      compound-request fixture set correctly splits into
                        multiple Goals; schema-validation failure correctly
                        lowers confidence rather than hard-failing

K4.2.3  Constraint Extraction + Planner request/result contracts
        Objective:    Constraint data model wired into Planner.
                        _extract_constraints(); PlannerRequest/PlannerResult
                        formalized
        Modules:       core/cognitive/planner.py
        Interfaces:     Constraint, PlannerRequest, PlannerHint,
                        PlannerResult (§12)
        Dependencies:    K4.2.2
        Validation:      given a Goal, produces a well-formed ConstraintSet;
                        contradictory-hard-constraint fixture correctly
                        yields rejected_precheck

K4.2.4  Capability Discovery refinements  [regression-gated]
        Objective:    description-and-schema matching + staged exposure,
                        layered onto the EXISTING, UNMODIFIED
                        CapabilityResolver.select()/ServiceProfile match
        Modules:       core/cognitive/planner.py (CapabilityRequest handling)
        Interfaces:     CapabilityRequest (§12)
        Dependencies:    K4.2.3; K3 (Kernel Compliance Audit) status resolved
                        or explicitly deferred, per K4 §0/K4.1 §0's carried
                        caveat -- this is the first milestone touching a
                        live resolution path
        Validation:      resolves to the same-or-better candidate set as
                        today's exact-match baseline on a fixed sub-goal
                        description test set

K4.2.5  Planner completion — HTN reframing + impasse handling
        Objective:    Skill preconditions wired into _decompose(); impasse
                        ->subgoaling path; ClarificationPolicy rule added
                        to OrchestrationGovernor
        Modules:       core/cognitive/planner.py, core/governance/
                        governance_kernel.py (new rule, not new governor)
        Interfaces:     ImpasseRecord, ClarificationPolicy (§2, §5)
        Dependencies:    K4.2.4
        Validation:      full Intent -> ... -> ExecutionPlan pipeline
                        produces an uncompiled ExecutionPlan; low-confidence
                        fixture correctly escalates exactly once, not
                        repeatedly (bounded-loop check, §14)

K4.2.6  Shared ValidationGate + Learning/Adaptation/Evolution wiring
        Objective:    one shared gate function serving Skill promotion,
                        Intent Ontology evolution, and User Cognitive Model
                        promotion -- not three parallel implementations
        Modules:       core/cognitive/learning.py (new, shared)
        Interfaces:     LearningRecord, CognitiveDecision (§12)
        Dependencies:    K4.2.5; existing v4.3.9 Instinct->Skill pipeline
        Validation:      a synthetic recurring-pattern fixture promotes only
                        after clearing ValidationGate; a contradiction
                        fixture is correctly blocked pre-promotion; the same
                        gate function is confirmed to serve all three
                        content domains via one code path, not three

K4.2.7  User Cognitive Model
        Objective:    read-mostly projection over L1/L3 preference/pattern
                        entries; write path through K4.2.6's shared gate
        Modules:       core/cognitive/user_model.py (new)
        Interfaces:     User Cognitive Model projection shape (§3)
        Dependencies:    K4.2.6
        Validation:      projection assembly is stable and cacheable;
                        promoted entries are correctly excluded from any
                        cross-instance advisory path (currently
                        nonexistent, so this validates as "no such path
                        touches this data," not a runtime check)
```

K4.2.1–K4.2.3 have zero live-path interaction and may proceed immediately. K4.2.4 onward carries the same K3-dependency caveat K4 §0 and K4.1 §0 already flagged, still open as of this document.

---

## 16. Final Validation

A deliberate self-critique pass, not a token gesture — six findings, each either resolved above or explicitly flagged as an open risk.

1. **Duplication risk, closed.** Three Evolution-tier promotion paths (Skills, Intent Ontology, User Cognitive Model) all cite "the SkillOpt-style gate." Left unspecified, this becomes three parallel implementations drifting apart over time — a Single-Source-of-Truth violation waiting to happen. **Closed** by specifying one shared `ValidationGate` (§6, §16 item here, K4.2.6) rather than leaving it implicit.
2. **New public entrypoint, checked against the seam principle.** `interpret()` (§1) adds a third public method to a Cognitive Runtime that K4 §1 described as having "two, deliberately." Verified explicitly: neither `interpret()` nor `plan()` touches Kernel execution — only `compile()` does. The seam count (one) is unchanged; only the *named public surface* grew, closing a gap K4 §1 left implicit rather than reopening a decision K4 §1 actually made.
3. **Kernel-boundary check.** Walked every new mechanism in this document (Input Normalization, User Cognitive Model, `ValidationGate`, meta-learning, `ClarificationPolicy`) against the Kernel's frozen ownership boundaries (K4 §0): none touches a storage backend directly, none bypasses `UnifiedMemory.write()`, none bypasses `GovernanceKernel`. No Kernel violation found.
4. **The three-tier Learning/Adaptation/Evolution model (§8) is genuinely new and untested.** Unlike most of this document, it isn't a direct restatement of something already decided elsewhere — it's a new classification imposed on existing mechanisms. Flagged, per this project's own K1.6 §8 precedent, as the piece most likely to need revision after real implementation contact (specifically K4.2.6) rather than another design pass now.
5. **Scalability note.** The User Cognitive Model projection (§3) re-queries L1/L3 on assembly; as preference-entry count grows this is the same class of concern already flagged for L2 semantic memory at scale (`OCBRAIN_FUTURE_ARCHITECTURE.md` §1.1) — mitigated identically, via a short-TTL cache, not a new mechanism.
6. **Scope-creep risk on Input Normalization.** A pure-code, pre-reasoning stage is an easy place for "just one more normalization rule" to accumulate indefinitely. No structural fix proposed beyond naming the risk — the existing Admission Test (Constitution Part V) applies to any proposal to grow it, same as everywhere else.

**Unresolved by design, not by oversight:** the §0 reconciliation gap. This document is offered as authoritative for everything except the parts explicitly marked **[RECONCILE-PENDING]**, and those parts were built conservatively — by reuse of already-existing mechanisms rather than invention — specifically so that a future reconciliation pass against K4.1-L, the Service Architecture document, and the Recursive Composition document is likely to find confirmation rather than conflict.

---

*Architecture freeze complete for the sections built from fully-reviewed source. No code generated, no Kernel files modified, no interfaces implemented. Ready for K4.2.1 once K3's status is resolved or deliberately deferred (§15), and for a short reconciliation pass against K4.1-L / Service Architecture / Recursive Composition once those documents are supplied (§0).*
