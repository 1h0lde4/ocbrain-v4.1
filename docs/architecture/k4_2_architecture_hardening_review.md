# OCBrain K4.2 — Final Architecture Hardening Review

**Date:** July 24, 2026
**Role:** Official OCBrain Architecture Maintainer
**Task type:** Architecture hardening — clarification only, no expansion
**Documents reviewed:** Constitution, KERNEL_ARCHITECTURE_v1.0, K4, K4.1 Final Consolidated, K4.2 Authoritative, K5 Future, FUTURE_RESEARCH_VAULT

---

## Executive Summary

14 architectural concepts were evaluated against the existing architecture. **12 of 14 are already covered by existing mechanisms** and require no changes. **2 of 14 justify minimal clarifications** — small additions to existing sections that eliminate ambiguity without introducing new concepts, infrastructure, or contracts.

| # | Concept | Verdict | Rationale |
|:---|:---|:---|:---|
| 1 | Cognitive Session | **REJECT** | Already exists as `CognitiveContext` |
| 2 | Cognitive Transaction Boundary | **REJECT** | Already exists via Plan Compilation seam + EventStream immutability |
| 3 | Cognitive Artifact Versioning | **REJECT** | Already exists via `supersedes` + `lifecycle_state` + replay version-pinning |
| 4 | Confidence Provenance | **ACCEPT (clarify)** | Minimal clarification to §9 — no new mechanism |
| 5 | Planner Search Budget | **REJECT** | Already covered by `BudgetGovernor` — implementation detail |
| 6 | Cancellation Semantics | **REJECT** | Already covered by `CancellationToken` + lifecycle states |
| 7 | Intent Stability | **ACCEPT (clarify)** | Minimal clarification to §13 — formalizes existing pattern |
| 8 | Capability Discovery Caching | **REJECT** | Already permitted under Law 2 + §3 caching principle |
| 9 | Reflection Boundary | **REJECT** | Already distinguished by ReflectionWorker vs EvaluatorWorker |
| 10 | Reasoning Evidence | **REJECT** | Already covered by `derived_from` + `ProvenanceRecord` + `justification` |
| 11 | Cognitive Snapshot | **REJECT** | Already covered by `EventStream.create_checkpoint()` |
| 12 | Evolution Simulation | **REJECT** | Deferred to FR-0013 by design |
| 13 | Cognitive Invariants | **REJECT** | Already defined in K4 §16 (9 invariants) |
| 14 | K5 Forward Compatibility | **REJECT** | Already reserved in K5 document |

---

## Detailed Analysis

---

### 1. Cognitive Session — REJECTED

**Question:** Should the architecture formally define a Cognitive Session?

**Answer:** No. The concept already exists under a different name with full specification.

**Existing mechanisms:**

| Mechanism | Source | Coverage |
|:---|:---|:---|
| `CognitiveContext` | K4.1 Part IV | Per-request lifecycle: created at Intent Interpretation, discarded at Response assembly. Mutable only by owner. Ephemeral — does not satisfy Resource Protocol. |
| `ExecutionContext.session_id` | Kernel Architecture §7.2 | Correlates related requests across invocations |
| K4 §1 session lifecycle | K4 §1 | "Spans exactly 1 Intent-to-Response cycle. Ephemeral; no life before Intent or after Response assembly." |
| `CognitiveContextView` | K4.1 Part IV | Scoped projection with `delegation_chain` for service consumption |

Introducing a "Cognitive Session" as an independent Resource would:
- Duplicate `CognitiveContext` (K4.1 Part IV)
- Violate the ephemeral nature K4 §1 establishes
- Create a second correlation identity alongside `session_id`
- Violate Law 9 (Single Source of Truth)

**Conclusion:** The existing `CognitiveContext` + `ExecutionContext.session_id` pair already provides exactly the session semantics the architecture requires. No change needed.

---

### 2. Cognitive Transaction Boundary — REJECTED

**Question:** Does the Cognitive Front-End require an explicit transaction boundary?

**Answer:** No. The existing architecture already provides clear boundaries through three mechanisms.

**Existing mechanisms:**

| Boundary | Mechanism | Source |
|:---|:---|:---|
| Reasoning begins | `CognitiveContext` creation at Intent Interpretation | K4.1 Part IV |
| Artifacts may change | Throughout the reasoning pipeline (draft → interpreted/verified) | K4.2 §13 |
| Artifacts become frozen | Plan Compilation seam: `ExecutionPlan` → `WorkflowDefinition` | K4 §15 |
| Reasoning becomes immutable | `EventStream` append-only with `StreamEvent` (`frozen=True`) | Kernel Architecture §15.2 |
| Replay interaction | K4.2 §8: "replay must resolve any memory lookup against the `KnowledgeEntry` version that was active at the time" | K4.2 §8 |

The Plan Compilation seam (K4 §15) is already the explicit transaction boundary between reasoning and execution. Introducing a second transaction system would violate the "single seam" principle (K4.2 §1 line 23: "Nothing in this document opens a second seam").

**Conclusion:** The existing Plan Compilation seam + EventStream immutability + CognitiveContext lifecycle already constitute a complete transaction boundary. No change needed.

---

### 3. Cognitive Artifact Versioning — REJECTED

**Question:** Should Intent, Goal, and ExecutionPlan carry explicit revision history?

**Answer:** No. The existing architecture already uses immutable replacement, not in-place versioning.

**Existing mechanisms:**

| Concept | Mechanism | Source |
|:---|:---|:---|
| Replacement | `KnowledgeEntry.supersedes` | Kernel Architecture §11.5 |
| Lifecycle | `CognitiveArtifact.lifecycle_state` (domain-specific per subtype) | K4.1 Part IV |
| Replay pinning | "Every promoted/superseded entry therefore needs a timestamp or version marker a replay can pin to" | K4.2 §8 |
| Provenance | `CognitiveArtifact.derived_from` + event correlation IDs | K4.2 §10 |
| Rollback | "Rollback is a new write that restores the prior `truth_status`/content and marks the promoted entry `deprecated` — history is never deleted, only superseded" | K4.2 §8 |

The architecture deliberately uses **immutable replacement** (create successor → mark predecessor `superseded`) rather than in-place versioning. This is consistent with:
- `StreamEvent` immutability (frozen dataclass)
- K4 §16 invariant: "reflection never mutates history"
- Constitution Part IV invariant: "Every resource carries identity, lifecycle, and provenance"

Adding explicit revision history would duplicate the `supersedes` + `derived_from` chain that already provides complete version traceability.

**Conclusion:** Immutable replacement via `supersedes` + `derived_from` + lifecycle states is sufficient. No change needed.

---

### 4. Confidence Provenance — ACCEPTED (minimal clarification)

**Question:** Does confidence itself require architectural provenance?

**Answer:** A minimal clarification is justified. The confidence chain (§9) is well-defined but does not explicitly state that confidence adjustments should be traceable to their contributing factors for calibration purposes.

**What exists:**
- K4.2 §9: Full confidence propagation chain from `IntentHypothesis.score` → `Goal.confidence` → `ExecutionPlan.confidence`
- K4.2 §10: Provenance table using `derived_from`, `ProvenanceRecord`, existing fields
- K4 §8: Brier-style calibration tracking predicted vs. actual outcomes
- K4.2 §10: "No new provenance mechanism anywhere in this table"

**What is missing:** §9 does not explicitly state that each adjustment point in the confidence chain should be **explainable** — i.e., that when confidence is lowered by schema validation (§4) or adjusted by capability-match quality (§9), the *reason* for the adjustment should be traceable through the existing provenance system.

**Proposed clarification to §9** (one paragraph, no new mechanism):

> **Confidence explainability.** Each adjustment point in the confidence chain above is traceable through the existing provenance system (`derived_from`, event correlation IDs, §10) — not through a separate confidence-specific audit trail. When a downstream stage adjusts confidence (e.g., schema-validation failure lowers `Goal.confidence`, §4; capability-match quality influences `ExecutionPlan.confidence`, §5), the adjustment reason is carried by the same event that records the state transition (§11, §13), not by a dedicated confidence-provenance structure. This preserves calibration explainability (the calibration system, K4 §8, can trace *why* a predicted confidence diverged from actual outcome) without introducing a second provenance mechanism.

**Why this is acceptable:**
- Extends §9, does not create new mechanism
- Explicitly reuses `derived_from` + events (§10's own principle)
- Enables calibration explainability (K4 §8's existing responsibility)
- Implementation-neutral — does not specify scoring algorithms
- Does not introduce duplication

---

### 5. Planner Search Budget — REJECTED

**Question:** Does planning require architectural budgeting?

**Answer:** No. This is already covered and is an implementation detail.

**Existing mechanisms:**

| Concept | Mechanism | Source |
|:---|:---|:---|
| Compute budget | `BudgetGovernor` | Kernel Architecture, K4.1 §9 |
| Depth limits | `RecursionGovernor` | K4.1 Part V |
| Planning timeout | `CancellationToken` with timer-triggered cancellation | Kernel Architecture §7.4 |
| Exploration limits | `Planner._alternative_plans(top_n=2)` | K4 §5 |
| Budget exhaustion | "a decomposition that can't complete within budget, produces `status: 'impasse'`" | K4.2 §5 |

Maximum planning depth, branch limits, and compute budgets are **implementation parameters** of the Planner, governed by `BudgetGovernor` and `RecursionGovernor`. They do not affect deterministic behavior — determinism is a property of orchestration, not components (Constitution Part II).

**Conclusion:** Existing governors already constrain planning. Specific limits are implementation tuning, not architecture. No change needed.

---

### 6. Cancellation Semantics — REJECTED

**Question:** Does the architecture need explicit cancellation/interruption handling?

**Answer:** No. Cancellation is already fully specified.

**Existing mechanisms:**

| Scenario | Mechanism | Source |
|:---|:---|:---|
| User cancellation | `CancellationToken.cancel()` | Kernel Architecture §7.4 |
| Superseded request | `lifecycle_state → superseded` | K4.2 §13 |
| Worker interruption | Workers check `context.cancellation_token.is_cancelled` | Kernel Architecture §7.4 |
| Draining | `SHUTTING_DOWN` lifecycle drains via cancellation tokens | K4.1 Part VII |
| Replay implications | Cancellation events recorded in `EventStream` | Law 2 (Explicit State) |
| Governance implications | Governance already evaluated before cancellation takes effect | Template Method pattern |

**Conclusion:** The `CancellationToken` + lifecycle state machines + EventStream already cover all cancellation scenarios. No change needed.

---

### 7. Intent Stability — ACCEPTED (minimal clarification)

**Question:** Should Intent become immutable after Goal Formation?

**Answer:** The existing architecture already implies this through the lifecycle state machine, but it is not stated as an explicit invariant. A one-sentence clarification strengthens deterministic replay.

**What exists:**
- K4.2 §13: `draft → interpreted → [clarification_pending → clarified] → superseded`
- K4 §16: "reflection never mutates history"
- K4.2 §2: Clarification overwrites `selected`, with event trail preserving both original and correction

**What is ambiguous:** §13 defines the lifecycle transitions but does not explicitly state that an Intent in `interpreted` state is **immutable** — i.e., that reinterpretation creates a successor Intent rather than modifying the existing one.

**Proposed clarification to §13** (one sentence after the Intent lifecycle):

> An Intent that has reached `interpreted` is immutable — reinterpretation (whether triggered by clarification, replanning, or Supervisor-driven revision) creates a **successor** Intent with its own `resource_id` and `derived_from` pointing at the predecessor, and transitions the predecessor to `superseded`. This preserves deterministic replay: the original Intent and its event trail remain unmodified regardless of subsequent reinterpretation.

**Why this is acceptable:**
- Formalizes a pattern already implied by `superseded` lifecycle + `derived_from`
- Strengthens deterministic replay guarantee (Constitution Law 4)
- Does not create a new mechanism — uses existing `supersedes`/`derived_from`
- Consistent with K4 §16 "reflection never mutates history"
- Consistent with K4.2 §8 version-pinned replay requirement

---

### 8. Capability Discovery Caching — REJECTED

**Question:** Should capability discovery permit bounded caching?

**Answer:** No architectural change needed. This is already permitted.

**Existing mechanisms:**
- K4.2 §3 (User Cognitive Model): "cached with a short TTL, purely as a performance measure"
- Kernel Architecture §3.1 Law 2: Caches allowed inside capabilities/workers, but consultations and cache returns must emit events
- Constitution Law 2 (Explicit State): Cache hits are still events

The same principle applies to capability discovery: implementation may cache resolution results with a short TTL as long as Law 2 is satisfied. This is an implementation decision, not an architectural one.

**Conclusion:** Existing caching principle (§3, Law 2) already covers this. No change needed.

---

### 9. Reflection Boundary — REJECTED

**Question:** Should Reflection distinguish between planning reflection and execution reflection?

**Answer:** No. This distinction already exists as separate workers.

**Existing mechanisms:**

| Worker | Scope | Source |
|:---|:---|:---|
| `ReflectionWorker` | Post-execution: consumes `EvaluationRecord`, `ExecutionPlan`, event trail. Proposes memory writes or revised Goals. | K4 §7 |
| `EvaluatorWorker` | Correctness/calibration: produces `EvaluationRecord` with quality scores and Brier calibration. Never edits evaluated artifacts. | K4 §8 |
| `SupervisorWorker` | Monitoring/recovery: initiates retries, escalates failures. Loop prevention: never retries unchanged rejected plan. | K4 §9 |

These three workers already represent different responsibilities, different learning signals, and different governance paths. Creating additional sub-distinctions (planning-reflection vs. execution-reflection) within `ReflectionWorker` would be a premature decomposition — K4 §7 already scopes reflection as "post-execution only."

**Conclusion:** The existing worker separation already provides this boundary. No change needed.

---

### 10. Reasoning Evidence — REJECTED

**Question:** Should reasoning artifacts expose a unified evidence structure?

**Answer:** No. The existing provenance system already provides this without a dedicated structure.

**Existing mechanisms:**

| Evidence type | Existing mechanism | Source |
|:---|:---|:---|
| Justification | `ExecutionPlan.justification` | K4 §6 |
| Provenance | `CognitiveArtifact.derived_from` + `ProvenanceRecord` | K4.2 §10, K1.6 |
| Confidence | `Intent.confidence`, `Goal.confidence`, `ExecutionPlan.confidence` | K4.2 §9 |
| Constraints | `Constraint.rationale` + `Constraint.source` | K4.2 §12 |
| Rejected alternatives | `Intent.hypotheses` (full list preserved), `Goal.alternatives` | K4.2 §2, §12 |
| Supporting context | `ContextBlock` + `ContradictionGroup` | Kernel Architecture §13.1 |

K4.2 §10 explicitly states: "No new provenance mechanism anywhere in this table — every row reuses `derived_from`, `ProvenanceRecord`, or an existing field. This is deliberate: provenance that requires its own bespoke storage per artifact type is itself a Single-Source-of-Truth risk."

Introducing a unified evidence structure would violate this exact principle.

**Conclusion:** The existing distributed provenance system is the architecture's deliberate choice. No change needed.

---

### 11. Cognitive Snapshot — REJECTED

**Question:** Does reasoning rollback require an architectural snapshot concept?

**Answer:** No. The existing architecture already provides the required mechanisms.

**Existing mechanisms:**

| Capability | Mechanism | Source |
|:---|:---|:---|
| System-level snapshots | `EventStream.create_checkpoint(name, payload)` | Kernel Architecture §15.1 |
| Replay with version-pinning | "replay must resolve any memory lookup against the `KnowledgeEntry` version that was active at the time" | K4.2 §8 |
| Planner recovery | `SupervisorWorker` retry-via-reinvocation | K4 §9 |
| Workspace snapshots | FR-0001 (Future Research — explicitly deferred) | FUTURE_RESEARCH_VAULT |

Introducing a separate "Cognitive Snapshot" would duplicate `EventStream.create_checkpoint()` and the replay version-pinning mechanism. FR-0001 already reserves workspace-level snapshots as a future research item with proper lifecycle.

**Conclusion:** `EventStream.create_checkpoint()` + version-pinned replay already provides this. No change needed.

---

### 12. Evolution Simulation — REJECTED

**Question:** Should Evolution include a simulation stage between Candidate and Validation?

**Answer:** No. This is explicitly deferred and the current architecture is sufficient.

**Existing mechanisms:**
- `ValidationGate` with held-out improvement scoring (K4.2 §6, §8): already validates candidates against improvement evidence before promotion
- FR-0013 (Simulation Mode): explicitly deferred to Future Research with proper lifecycle
- K4.2 §16 item 4: "The three-tier Learning/Adaptation/Evolution model (§8) is genuinely new and untested... flagged as the piece most likely to need revision after real implementation contact (specifically K4.2.6)"

The architecture deliberately defers simulation until evidence from K4.2.6 implementation proves it necessary (Constitution Law 8: Evidence over Assumption). Adding it now would be speculative expansion.

**Conclusion:** `ValidationGate` with held-out scoring is the current safeguard. Simulation is correctly deferred to FR-0013. No change needed.

---

### 13. Cognitive Invariants — REJECTED

**Question:** Should the Cognitive Front-End define architectural invariants comparable to Kernel Laws?

**Answer:** No new section needed. K4 §16 already defines exactly these invariants.

**Existing invariants (K4 §16):**

| # | Invariant | Source |
|:---|:---|:---|
| 1 | Every plan has a goal | K4 §16 |
| 2 | Every goal has an owner | K4 §16 |
| 3 | Every step explainable | K4 §16 |
| 4 | Planning never executes | K4 §16 |
| 5 | Execution never plans | K4 §16 |
| 6 | Reflection never mutates history | K4 §16 |
| 7 | Evaluation never changes facts | K4 §16 |
| 8 | Cognitive Runtime never bypasses Governance | K4 §16 |
| 9 | A rejected/escalated plan is not silently retried as-is | K4 §16 |

The proposed examples ("Intent never executes", "Planner never writes memory", "Reflection never mutates history", "Execution never performs reasoning") are either already covered (invariants 4-7) or derivable from existing invariants + K4.2 §1 boundaries.

K4.2 §4's new Goal Formation Boundary (added during this session) additionally formalizes the cognition/execution separation for Goal Formation specifically.

Creating a second invariant list would duplicate K4 §16 and risk divergence (Law 9 violation).

**Conclusion:** K4 §16 already covers this. The Goal Formation Boundary in §4 extends it for Goal Formation specifically. No additional invariants section needed.

---

### 14. K5 Forward Compatibility — REJECTED

**Question:** Should K4.2 reserve architectural extension points for K5?

**Answer:** No additional reservations needed. K5 already identifies its own extension points.

**K5 extension points already documented:**

| Extension Point | K5 Section | K4.2 Compatibility |
|:---|:---|:---|
| `PlannerHint` for Self Model | K5 §2 | ✅ `PlannerHint` already defined in K4.2 §5 |
| `CapabilityRegistry` `capability_kind` for reasoning strategies | K5 §7 | ✅ Existing registry, new tag only |
| Causal graph edge types | K5 §3 | ✅ Graph Memory vocabulary extension, no K4.2 impact |
| `ProactiveInitiationGovernor` | K5 §9 | ✅ Reserved governance slot, no K4.2 impact |
| Shared `ValidationGate` for N domains | K5 §10 | ✅ K4.2 §6 already specifies this |
| Ontology merge/split | K5 §5 | ✅ Uses `supersedes`/`deprecated`, already in K4.2 §8 |

K4.2's existing mechanisms (`PlannerHint`, `ValidationGate`, `derived_from`, `supersedes`, lifecycle states) are already the extension points K5 builds on. No additional reservation is needed.

**Conclusion:** K5 already identifies its own extension points, all compatible with K4.2. No change needed.

---

## Accepted Changes — Exact Wording

### Change 1: Confidence Explainability (§9)

**Location:** K4.2 §9, after the confidence propagation chain diagram (after line ~272).

**Wording to add:**

> **Confidence explainability.** Each adjustment point in the confidence chain above is traceable through the existing provenance system (`derived_from`, event correlation IDs, §10) — not through a separate confidence-specific audit trail. When a downstream stage adjusts confidence (e.g., schema-validation failure lowers `Goal.confidence`, §4; capability-match quality influences `ExecutionPlan.confidence`, §5), the adjustment reason is carried by the same event that records the state transition (§11, §13), not by a dedicated confidence-provenance structure. This preserves calibration explainability (the calibration system, K4 §8, can trace *why* a predicted confidence diverged from actual outcome) without introducing a second provenance mechanism.

**Why it does not violate previous architecture:** Restates §10's principle ("No new provenance mechanism") applied specifically to confidence. Creates no new mechanism.

**Why it does not introduce duplication:** Explicitly reuses `derived_from` + events.

---

### Change 2: Intent Immutability After Interpretation (§13)

**Location:** K4.2 §13, after the Intent lifecycle line (after line ~375).

**Wording to add:**

> An Intent that has reached `interpreted` is immutable — reinterpretation (whether triggered by clarification, replanning, or Supervisor-driven revision) creates a **successor** Intent with its own `resource_id` and `derived_from` pointing at the predecessor, and transitions the predecessor to `superseded`. This preserves deterministic replay: the original Intent and its event trail remain unmodified regardless of subsequent reinterpretation.

**Why it does not violate previous architecture:** Formalizes the pattern already implied by `superseded` lifecycle + `derived_from` + K4 §16 invariant 6.

**Why it does not introduce duplication:** Uses existing `supersedes`/`derived_from` mechanism.

---

## Validation

| Question | Answer |
|:---|:---|
| Is every accepted concept architecturally justified? | ✅ Yes — both clarify existing mechanisms |
| Does an equivalent mechanism already exist for rejected concepts? | ✅ Yes — all 12 rejections cite specific existing mechanisms |
| Do accepted changes extend existing mechanisms instead of creating new ones? | ✅ Yes — both reuse `derived_from`, events, lifecycle states |
| What is the minimal architectural change? | 2 paragraphs added to existing sections |
| Do changes preserve deterministic replay? | ✅ Yes — Change 2 explicitly strengthens it |
| Do changes preserve Kernel boundaries? | ✅ Yes — no Kernel modification |
| Do changes preserve Governance authority? | ✅ Yes — no governance modification |
| Do changes preserve the Constitution? | ✅ Yes — strengthen Laws 2, 4, 6 |
| Do changes introduce duplication? | ✅ No — both explicitly reuse existing mechanisms |
| Are changes implementation-neutral? | ✅ Yes — no code, no pseudocode, no scoring algorithms |

---

## Compatibility Verification

| Document | Compatible? |
|:---|:---|
| OCBRAIN_KERNEL_CONSTITUTION.md | ✅ |
| PROJECT_INSTRUCTIONS.md | ✅ |
| OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md | ✅ |
| OCBRAIN_K4_1_COGNITIVE_RUNTIME_FOUNDATION.md | ✅ |
| OCBRAIN_K4_1_X_DELEGATION_ARCHITECTURE_AUTHORITATIVE.md | ✅ |
| OCBRAIN_K5_FUTURE_COGNITIVE_EVOLUTION_ARCHITECTURE.md | ✅ |

No completed milestone requires redesign. No existing interface becomes incompatible.
