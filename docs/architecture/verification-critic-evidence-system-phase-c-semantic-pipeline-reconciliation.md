# Verification / Critic / Evidence System — Phase C Semantic Pipeline Reconciliation & Design

**Status: Reconciliation complete. Design ready for Phase 2 implementation (Obligation → Rubric → Criterion → InspectionPlan).**
**Date:** September 7, 2026
**Scope:** The read/reconcile/design pass explicitly queued by `CURRENT_STATE.md`'s September 5, 2026 sync ("Explicitly scoped next as a read/reconcile/design pass, re-establishing the exact frozen source of truth first — not an implementation session") and by `KNOWN_ISSUES.md` DEBT-018's matching note.
**Method:** Full read of `verification-critic-evidence-system-architecture-v2-frozen.md` (not excerpts), plus every v1 section it points to as "unchanged" rather than restates (§13/§14 Rubric/InspectionPlan detail, §36 Evaluation Lab Boundary, §42 base contract list). Every one of the 11 existing `core/verification/*.py` files read field-by-field, not just class-name greps. All six `ADR_LAB_0{1-6}` documents read in full. This document corrects and supersedes the equivalent analysis given in-conversation earlier in this session, per this project's own `PROJECT_INSTRUCTIONS.md` §20.6 (Evidence-First Reconciliation) — one conclusion below (the eval-lab boundary) is materially stronger than what was said in chat, because it's now grounded in the actual ADR text instead of contract docstrings alone.

---

## 1. The pipeline, as frozen

```
Requirement
  → VerificationObligation (derivation_source tracked)
  → Rubric → Criterion (versioned, fingerprinted, validated, locked)
  → InspectionPlan → InspectionStep (per-criterion, from the method registry)
  → Observation → Interpretation → Claim          [a SEPARATE chain from:]
  → Observation → Evidence                         [scope+authority+provenance+integrity+relevance+binding required]
  → Assessment → VerificationResult / VerificationVerdict
  → VerificationReceipt (immutable, supersession lineage)
```

Source: v1 §12-16, v2 §8-13 (v2 restates §8/§9/§12/§13 with corrections; §10/§14/§15-in-part are "unchanged" pointers back to v1 — both were read, not just the pointer).

Two chains that must never collapse into one (v2 §12, restated because it is the single most load-bearing distinction for this phase): an observation becoming an *interpretation* becoming a *claim* is not the same operation as an observation becoming *evidence*. `HTTP 200 → "request succeeded" → "external operation completed successfully"` is the first chain, and the last step still needs its own verification. Evidence additionally requires scope, authority, provenance, integrity, relevance, and criterion binding before it is usable verification input — an interpretation is not evidence merely for having followed a real observation.

---

## 2. Complete type inventory — every named contract, current status

Legend: ✅ built and tested · ◐ partially built · ❌ not built. File column is `core/verification/<file>` unless noted.

| # | Type | Status | Where | Notes |
|---|---|---|---|---|
| 1 | `VerificationRequest` | ❌ | — | |
| 2 | `VerificationTarget` | ◐ | `target.py` | Superseded in shape by `VerificationTargetFingerprint`+`VerificationTargetSnapshot` (v3 §4) — the plain type was never meant to survive as a third thing; treat as satisfied |
| 3 | `VerificationContext` | ❌ | — | |
| 4 | `VerificationObligation` | ✅ | `obligation.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: **This phase's primary deliverable** |
| 5 | `Rubric` | ✅ | `rubric.py` | Built and tested; status reconciled 2026-09-30. Its `construct` field carries the built `VerificationConstruct` (row 47, Batch 3A) and is REQUIRED — a Rubric has no construct-less state, DRAFT included (decision record in §9). Original planning note: **This phase's primary deliverable** |
| 6 | `Criterion` | ✅ | `rubric.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: **This phase's primary deliverable** |
| 7 | `CriterionDependency` | ✅ | `rubric.py` | Built and tested; status reconciled 2026-09-30 against code and test references. |
| 8 | `CriterionApplicability` | ✅ | `rubric.py` | Built and tested; status reconciled 2026-09-30 against code and test references. |
| 9 | `CriterionEvidenceRequirement` | ✅ | `rubric.py` | Built and tested; status reconciled 2026-09-30 against code and test references. |
| 10 | `CriterionResult` | ❌ | — | Should reuse `VerificationResult`'s shape (verdict/assurance/confidence), scoped to one criterion — not a fifth parallel result type |
| 11 | `CompiledVerificationSpecification` | ✅ | `compiled_specification.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: The output of Rubric lock/compile (§9, §16 satisfiability) |
| 12 | `Claim` | ✅ | `claim.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: Phase 3 |
| 13 | `ClaimDependency` | ✅ | `claim.py` | Batch 1: `ClaimDependencyType` (RELIES_ON/PRESUPPOSES), immutable edge with self-dep guard. Reconciled against `ClaimOrigin`/`derived_from`/`caused_by` — non-overlapping |
| 14 | `InspectionPlan` | ✅ | `inspection.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: **This phase's primary deliverable** — see §5 below re: its Method dependency |
| 15 | `InspectionStep` | ✅ | `inspection.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: **This phase's primary deliverable** |
| 16 | `EvidenceSource` | ✅ | `evidence.py` | |
| 17 | `EvidenceItem` | ✅ | `evidence.py` | Circular-evidence check (`check_not_circular`) tested and confirmed structural, not a judgment call |
| 18 | `EvidenceReference` | ◐ | `evidence.py` | Batch 2, decided scope implemented and tested: exact source (reuses `EvidenceSource`) + non-empty locator + claim/criterion binding, `verify_against(item)` drift check plus `check_not_circular` for a claim-bound reference. No payload field. NOT enforced: that a locator is genuinely *exact*. v1 §15 metadata (scope, validity window, relevance, specificity, integrity, correlation_group, independence_level, sensitivity) not carried — open decision |
| 19 | `EvidenceObservation` | ✅ | `evidence.py` | Batch 2: binds evidence→`Observation` by id + provenance completeness; carries no authority of its own; `verify_against` rejects an `Interpretation` |
| 20 | `EvidenceTransformation` | ◐ | `evidence.py` | Batch 2, decided scope implemented: lineage + categorical rules only (no ordinal on `EvidenceDirectness`): no upgrade into DIRECT, MODEL_INTERPRETATION permanent (v1 §16), provenance never silently COMPLETE; `verify_against` also stops a restatement flag being dropped through lineage (circular evidence cannot be laundered). Authority/integrity/certainty NOT enforced (no fields). DIRECT→DIRECT via non-model transformation deliberately left to higher layers |
| 21 | `EvidenceBundle` | ✅ | `evidence.py` | Batch 2: immutable tuple of `EvidenceItem`s (all six statuses preserved, no filtering), applies `check_not_circular` for a bound claim; membership implies no support/verdict |
| 22 | `VerificationMethod` | ✅ | `method.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: Phase 5. `policy.py`/`dimension.py` already use string placeholders for method names in anticipation (see §4) |
| 23 | `VerificationCapability` | ✅ | `method.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: Phase 5 |
| 24 | `VerificationObservation` | ❌ | — | Phase 4. Distinct from the three dimension refinements already built (row 27). **Deferred, not just unbuilt:** the frozen architecture names it (v1 contract list) but defines no fields or semantics, so implementing it would be invention; needs a definition first (Batch 3B excluded it by decision) |
| 25 | `VerificationFinding` | ✅ | `finding.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: Phase 5 — the type meant to carry method+dimension as two independent classifications (v2 §11) |
| 26 | `Critique` | ✅ | `critique.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: Phase 5 |
| 27 | `CounterArgument` | ✅ | `critique.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: Phase 5 |
| 28 | `Contradiction` | ✅ | `critique.py` | Built and tested; status reconciled 2026-09-30 against code and test references. Original planning note: Phase 5 |
| 29 | Five `*Coverage` types (Task/Verification/Criterion/Evidence/Observation) | ✅ | `coverage.py`, `absence.py` | Batch 3B: five distinct frozen types, no shared base, no container, each `fraction: Optional[float]` in [0,1] (None = unknown) + required `scope`; any combination representable (task 1.0 with verification 0.4). The four observation-absence states (`ObservationAbsenceState`) and the `ObservationAbsence` record with the OBSERVED_ABSENT gate are in `absence.py`. `VerificationAssurance.coverage` is untouched, with no equivalence to `VerificationCoverage`. Original note: v2 §13's explicit fix for the "task completeness silently becoming verification completeness" collapse |
| 30 | `ProcessVerificationResult` / `OutcomeVerificationResult` | ❌ | — | |
| 31 | `VerificationResult` | ✅ | `verdict.py` | |
| 32 | `VerificationVerdict` | ✅ | `verdict.py` | 10 members — see §4 |
| 33 | `VerificationConfidence` | ◐ | `verdict.py` | Exists as a plain `float` field on `VerificationResult`, not its own type — architecturally sufficient per v2 §20 ("unchanged, v1 §23"); no v1/v2 text demands a wrapper type |
| 34 | `VerificationAssurance` | ✅ | `epistemic.py` | `assurance_scope` mandatory, enforced in `__post_init__`, tested |
| 35 | `VerificationRun` | ❌ | — | Phase 7 |
| 36 | `VerificationStep` | ❌ | — | Phase 7 |
| 37 | `VerificationReceipt` | ✅ | `receipt.py` | Supersession lineage confirmed real (returns new object via `dataclasses.replace`, never mutates) |
| 38 | `VerificationTrace` | ❌ | — | Phase 7 |
| 39 | `DecisionTrace` | ❌ | — | |
| 40 | `VerificationPolicy` (+ the v3 four-way split) | ✅ | `policy.py` | `VerificationRequirements`/`Policy`/`Strategy`/`Profile`, all four, matching v3 Part 1 §3 near-verbatim in the docstrings |
| 41 | `VerificationBudget` | ❌ | — | Blocked on `DEBT-007` (BudgetGovernor counters unwired) per v2's own risk table §48 — not this phase's job to unblock |
| 42 | `EscalationRequest` | ❌ | — | Phase 9 |
| 43 | `AdjudicationRecord` | ❌ | — | Phase 9 |
| 44 | `Assumption` / `AssumptionSource` / `AssumptionStatus` | ✅ | `assumption.py` | Batch 1: `AssumptionSourceKind` (5 values) + `AssumptionSource` (structured provenance, no authority inference) + `AssumptionStatus` (UNEXAMINED/CHALLENGED/CONFIRMED/REJECTED — distinct from `VerificationVerdict`). `Assumption.source` optional, `Assumption.status` defaults to UNEXAMINED |
| 45 | `ObservationAuthority` | ✅ | `epistemic.py` | |
| 46 | `InspectionAuthorization` | ✅ | `epistemic.py` | `VerificationAssurance.__post_init__` refuses to construct over an unauthorized surface — enforced, not documented |
| 47 | `VerificationConstruct` / `ConstructValidity` | ✅ | `construct.py` | Batch 3A: `VerificationConstruct` (single `description` field, no identity), `ConstructValidityStatus` (NOT_EVALUATED / SUPPORTED / CONTESTED / UNSUPPORTED — IMPLEMENTATION JUDGMENT, string values namespaced `construct_*` to avoid colliding with `VerificationVerdict.UNSUPPORTED`), `ConstructValidity` (`rubric_fingerprint` + `status`; refers to the rubric by value only, never part of its identity). Integrated as the required field `Rubric.construct`. Original note: needed alongside Rubric (row 5) — v2 §9's sharpest addition |
| 48 | `Reference` / `GroundTruth` / `Oracle` / `ReferenceQuality` | ✅ | `reference.py`, `oracle.py` | `Reference`/`GroundTruth`/`Oracle` already implemented. Batch 1: `ReferenceQuality` (UNASSESSED/LOW/MODERATE/HIGH) added to `Reference` as default-UNASSESSED field. Quality ≠ correctness ≠ authority ≠ GroundTruth |
| 49 | `MinimumSufficientEvidence` | ◐ | `evidence.py` | Batch 2, decided scope implemented: declarative set of evidence ids required to reconstruct a claim/criterion decision + pure `verify_against(bundle)` containment check. Status-blind; not the count floor (`CriterionEvidenceRequirement`). Layout is IMPLEMENTATION JUDGMENT (v2 §44 names the purpose only); privacy/cost dimensions not represented yet |
| 50 | `BlindVerificationContext` | ❌ | — | `shape.py`'s own docstring already flags this as the order-bias mitigation it deliberately didn't build |
| 51 | `PolicyPrecedence` | ❌ | — | `policy.py`'s own docstring already flags this as the thing `VerificationPolicy` is "the input to," not yet built |
| 52 | `VerificationBasis` (composable set) | ✅ | `epistemic.py` | `FrozenSet[BasisComponent]`, rejects empty, tested |
| 53 | `VerificationShape` / `ComparisonRelation` / `PairwiseConsistency` | ✅ | `shape.py` | Cycle-membership invariant (`cycle_members` non-empty iff `CYCLE_DETECTED`) enforced and tested |
| 54 | `VerificationTargetFingerprint` / `Snapshot` | ✅ | `target.py` | `is_stale_against` tested against both matching and diverging fingerprints |
| 55 | `StateVerification` / `TransitionVerification` / `InvariantVerification` | ✅ | `dimension.py` | Transition requires differing states, invariant window ordering — both enforced and tested |
| 56 | `EvidenceRetention` / `ReceiptRetention` / `SourceRetention` | ✅ | `retention.py` | Three genuinely independent types confirmed (not one parametrized class) |
| 57 | `ControlType` / `ControlCase` | ✅ | `control.py` | `expected_abstention` structurally forbidden on POSITIVE/NEGATIVE cases — enforced, matches G-0001's own lesson |

**Built: 38 of 57 listed rows fully ✅ (five more ◐: `VerificationTarget` and `VerificationConfidence` partially/architecturally-satisfied; and `EvidenceReference`, `EvidenceTransformation`, `MinimumSufficientEvidence`, whose decided scope is implemented but whose architecture-named parts are deferred — see §9). 14 rows remain ❌.** *Inventory reconciled 2026-09-30:* 16 rows previously marked ❌ were found built in code and tests and were re-marked; before that the header overstated ✅ by one since `ead305d` (said 16, table had 15). This table is now the baseline for sizing later batches. Batch 1 (epistemic spine completion) added rows 13, 44, 48; Batch 2 (Evidence) closed rows 19 and 21 and brought rows 18, 20, 49 to their decided scope. *Count correction:* this header previously overstated ✅ by one since `ead305d` (it said 16; the table had 15 ✅ rows); it now matches the table. This is a more precise count than `KNOWN_ISSUES.md`'s own "~15 of ~90" — the difference is granularity (that figure appears to count at the "named concept in prose" level; this table counts at the "class in code" level, e.g. `VerificationRequirements`/`Policy`/`Strategy`/`Profile` as four rows, not one). Both are honest counts of the same underlying reality; neither supersedes the other.

---

## 3. Field-level fidelity check (not just "the class exists")

Spot-verified by reading full file contents, not grepping class names:

- `VerificationAssurance.__post_init__` rejects construction with empty `assurance_scope` *and* rejects construction over an unauthorized `InspectionAuthorization` — both v2 §15 invariants are load-bearing in code, not comments.
- `VerificationResult.__post_init__` rejects any `execution_failure` paired with a verdict other than `UNVERIFIABLE` — the exact "a verifier crash cannot become PASS" rule from v2 §37/Review C, enforced.
- `VerificationReceipt.superseded_by()` returns a new frozen instance via `dataclasses.replace`; the original is structurally untouched — v2 §26's immutability claim is a checkable property, confirmed.
- `PairwiseConsistency.__post_init__` enforces `cycle_members` populated if and only if `status == CYCLE_DETECTED` — the A>B, B>C, C>A cycle-detection requirement (mission §46) has a real structural guard, not just a status label.
- `ControlCase.__post_init__` refuses `expected_abstention=True` on `POSITIVE`/`NEGATIVE` cases — the "abstention on AMBIGUOUS/PARTIAL is correct behavior" invariant (mission §87) is enforced, not just documented in the golden corpus.

No contradiction between code and the frozen architecture was found anywhere in the 11 files.

---

## 4. Reusable infrastructure Phase 2 must not duplicate

- **`identity.py` already declares `RubricId`, `CriterionId`, `ClaimId`, `EvidenceId`, `ObservationId`** as `NewType` wrappers, unused until now. Phase 2 should consume these, not invent parallel ones. Two are genuinely missing and need adding to this file: `ObligationId`, `InspectionPlanId`.
- **`VerificationVerdict` (`verdict.py`) already has all eight of the obligation-closure states this phase needs** — `VERIFIED`, `PARTIALLY_VERIFIED`, `CONTRADICTED`, `UNSUPPORTED`, `INSUFFICIENT_EVIDENCE`, `UNVERIFIABLE`, `NOT_APPLICABLE`, `ESCALATE` — plus `CONDITIONAL` and `UNSAFE_TO_VERIFY`. `CriterionResult` and obligation closure should carry this enum directly. The genuinely missing piece sits one layer up: an **attempt-status** axis (`NOT_RUN` / `SKIPPED` / `BLOCKED`) distinct from `VerificationExecutionFailure`'s existing `TIMEOUT`/`TOOL_FAILURE`/`VERIFIER_CRASH`/`BUDGET_EXHAUSTED` — "never attempted" and "attempted, got verdict X" are different axes and neither existing enum currently names the first one.
- **The "string placeholder for an unbuilt taxonomy" pattern is already established, not something to invent.** `policy.py`'s `VerificationRequirements.required_dimensions: FrozenSet[str]` and `VerificationStrategy.selected_methods: FrozenSet[str]` both use plain strings with a docstring explicitly flagging them as deliberate placeholders for `VerificationDimension`/`VerificationMethod`, which don't exist in code yet. `InspectionPlan`'s own forward-reference to a not-yet-built `VerificationMethod` (§5 below) should follow this exact precedent, not a new one.
- **`VerificationResult`'s existing shape** (`verdict` + `assurance` + `confidence` + optional `execution_failure`) is close enough to what `CriterionResult` needs that `CriterionResult` should most likely be `VerificationResult` scoped to one `criterion_id`, not a fifth independent result type. Phase 2 should decide this explicitly rather than let it happen by accident.

---

## 5. Design: Obligation → Rubric → Criterion → InspectionPlan

**`VerificationObligation`** (new file, `obligation.py`)
- `obligation_id: ObligationId` (new identity.py entry)
- `derivation_source: DerivationSource` — new enum: `explicit_user_requirement | constraint | plan_requirement | postcondition | capability_contract | system_invariant | model_derived` (v2 §8, verbatim)
- `description: str`, `source_reference: str` (what requirement/constraint/plan-step this traces to)
- `rubric_id: Optional[RubricId]` — set once a rubric is compiled against it
- Invariant to enforce in `__post_init__`: a `model_derived` obligation must never be constructible with a field that implies it carries the same authority as `explicit_user_requirement` — concretely, an `authority_weight`-style field (if one is added later) should default lower for `model_derived` and the constructor should not silently accept an override that erases the distinction.

**`Rubric` / `Criterion`** (new file, `rubric.py`)
- `Rubric`: `rubric_id: RubricId`, `version: str`, `fingerprint: str`, `created_from`, `created_by`, `derived_from`, `source_requirements: Tuple[str, ...]`, `context_basis: str` (v2 §9's provenance fields, all five), `criteria: Tuple[CriterionId, ...]` (reference, don't embed — matches this codebase's own established pattern per `policy.py`'s docstring), `lock_state: RubricLockState` (new enum: `DRAFT | VALIDATED | COMPILED | LOCKED`), `construct: Optional["VerificationConstruct"]` (forward reference; full type is row 47, out of this phase's scope, but the *field* should exist now so Rubric doesn't need a breaking migration when it lands) *[Superseded by Batch 3A: `VerificationConstruct` is built and `Rubric.construct` is now a required `VerificationConstruct` — see the decision record in §9. The original plan is left as written.]*
- `Criterion`: `criterion_id: CriterionId`, `rubric_id: RubricId`, `description`, `applicability: CriterionApplicability`, `evidence_requirement: CriterionEvidenceRequirement`, `dependencies: Tuple[CriterionId, ...]`
- `CriterionDependency`: dependency-graph edge with a type (`REQUIRES` / `BLOCKS` / other — Phase 2 decision, not fixed by architecture)
- Validation (v1 §13, mission §15-16): reject phantom, duplicate, contradictory, impossible, out-of-scope, and no-evidence-path criteria *before* `lock_state` can reach `COMPILED`. Dependency-cycle rejection is a graph check, same shape as `PairwiseConsistency`'s cycle detection in `shape.py` — reuse that pattern, don't reinvent cycle-detection logic a second time in this file.

**`InspectionPlan` / `InspectionStep`** (new file, `inspection.py`)
- `InspectionPlan`: `plan_id: InspectionPlanId` (new identity.py entry), `obligation_id: ObligationId`, `criterion_id: CriterionId`, `steps: Tuple[InspectionStepId, ...]`
- `InspectionStep`: `step_id`, `plan_id`, `method_reference: str` (placeholder per §4 above — a plain string tag, not a `VerificationMethod` object, until Phase 5), `description`
- No `__post_init__` invariant currently requires an LLM call anywhere in this path (v1 §14: "an InspectionPlan for 'artifact X exists' is a filesystem check") — Phase 2's tests should include at least one plan whose steps are all deterministic, to keep this true in code, not just in the docstring.

---

## 6. Eval-Lab boundary: resolved, not merely assumed

The in-conversation version of this analysis earlier in this session said the boundary was "plausible but not demonstrated." Having now read all six ADR-LAB documents in full, it is demonstrated:

**Timing.** All six ADRs are dated August 28, 2026. The Verification Phase C contracts (`a4eddc4`) were committed September 4, 2026 — six days later. `core/verification/` did not exist yet when these ADRs were written. The absence of any cross-reference is a sequencing fact, not an oversight — and it's checkable that the eval-lab authors *do* actively check for naming collisions when aware of them: `ADR_LAB_02` explicitly rejected nesting the Lab under `core/evaluation/` specifically because `core/workers/evaluator.py`'s `EvaluatorWorker` already used that vocabulary, citing this exact repository's own `DEBT-016` (two watchdog implementations) as the cautionary precedent for what unreconciled same-name-different-concept code costs.

**Operating level.** `ADR_LAB_01`'s six-layer trust model names its own subject as "the agent/system being evaluated," sourced (`ADR_LAB_02`) primarily from `EventStream`, supplementarily from `EvaluatorWorker`/`ReflectionWorker` output — Verification is not listed as an input at all, currently. Eval-lab evaluates trajectories and agent behavior broadly; Verification establishes whether one specific claim about one specific target holds within one bounded run. These are different objects under evaluation, not the same object evaluated twice.

**The Oracle/Evidence naming overlap is convergence, not duplication, and the earlier in-chat framing of it as "meta-level, evaluating Verification itself" was not quite right — corrected here rather than left standing.** `ADR_LAB_06`'s `OracleDefinition` and Verification's future `Oracle` (mission §17, v2-frozen §24) are parallel, independently-arrived-at implementations of the same well-established pattern (a mechanism establishing ground truth, kept distinct from the interpretation layer built on top of it), motivated by literally the same cited incidents (Meta's ARE/Gaia2 verifier-gaming research appears as justification in both `ADR_LAB_06` and this repository's own Verification architecture). Eval-lab's gold-standard hierarchy (`environment ground truth > validated deterministic oracle > validated human reference > validated user simulator > calibrated LLM judge > uncalibrated LLM judge`) and Verification's own (`environment ground truth > deterministic verifier > validated human reference > calibrated LLM judge > uncalibrated LLM judge`, v2 §37/ADR-LAB-03-equivalent) are the same ordering in substance. Two teams solving the same well-documented problem the same way is exactly what this project's own §18.6 ("favor architectural convergence over novelty") calls a good sign, not a collision to resolve.

**One constructive, non-blocking follow-up — not required for this phase or Phase 3:** `ADR_LAB_02`'s trace adapter already plans to consume `EvaluatorWorker`/`ReflectionWorker` output as "one input feature on the trajectory, never as an evaluation result." Once Verification's `verification.*` events (v2 §31) exist, they are a natural, low-effort addition to that same adapter, on the same terms. Worth a one-line note in a future `ADR_LAB_02` amendment or a short Verification-side ADR when that day comes — not something this phase needs to build or decide.

**Conclusion: no boundary decision is required from Moncif to proceed with Phase 2 or Phase 3.** The one open item — confirming the Oracle/Evidence convergence reading above — is worth a single sentence added to either ADR set before `Reference`/`Oracle`/`GroundTruth` (row 48) gets built, so this reasoning doesn't have to be reconstructed from two branches' git history again later. That is a documentation action, not an architecture change, and does not block anything in this document.

---

## 7. What this phase deliberately does not do

Per `PROJECT_INSTRUCTIONS.md`'s Architecture Freeze Principle and this project's own recorded decision that the current session is reconciliation/design, not implementation:

- No code in `core/verification/` is modified or added by this document.
- `Claim`/`Assumption`/`Reference`/`Oracle` (Phase 3), `VerificationMethod`/`Dimension` proper (Phase 5), the five `*Coverage` types (Phase 6), and everything downstream remain exactly as open as `KNOWN_ISSUES.md` DEBT-018 already states — this document does not silently narrow that list, only the four rows in §1/§5 above.
- `VerificationBudget` stays blocked on `DEBT-007` — not re-litigated here.
- No claim in this document is a green light for Verification *runtime integration* — `CURRENT_STATE.md`'s September 5 sync sequencing (integration stays post-Kernel-freeze/post-C-MoE) is unaffected; everything above is contract/design work on the isolated feature branch, per the same distinction already drawn earlier this session.

---

## 8. Recommendation

Proceed to Phase 2: implement `obligation.py`, `rubric.py`, `inspection.py`, plus the two `identity.py` additions (`ObligationId`, `InspectionPlanId`), with tests, on `feature/verification-critic-evidence-phase-c`. Hold `Claim`/`Assumption`/`Reference`/`Oracle` (Phase 3) for the one-sentence ADR cross-reference noted in §6 — not blocking, but cheap to do first.

---

## 9. Status register after the side-work audit (2026-09-30)

Recorded from the review disposition; this is a state record, not a completion claim for the Verification subsystem.

| Item | State |
|---|---|
| Batch 1 (epistemic spine: `ClaimDependency`, `AssumptionSource`, `AssumptionStatus`, `ReferenceQuality`) | Complete |
| `CompiledVerificationSpecification` hardening | Repaired and validated: duplicate-ID detection and `InspectionStep.plan_id` validation kept; the strategy↔method consistency check was removed. `VerificationStrategy.selected_methods` (method names/types, `policy.py`) and `InspectionStep.method_reference` (registry reference) stay separate; how they relate is still an open design question |
| Batch 2 Evidence (rows 18–21, 49) | **Closed for its decided scope** after the final branch audit. All five contracts are implemented and tested; rows 19 and 21 are ✅, rows 18, 20, 49 stay ◐ because architecture-named parts are deferred (table below). This is not a claim that the Verification subsystem, or all V1 evidence semantics, are complete |
| G8 — Batch 1 hardening | Deferred hardening debt, not an architectural blocker |

**Batch 2: enforced** (only what each contract's own fields can observe; the record-vs-item checks run when `verify_against` is called, no registry exists to run them automatically): exact source + non-empty locator + claim/criterion binding; observation binding by id with no authority of its own (an `Interpretation` is rejected); transformation lineage with categorical rules only (no upgrade into `DIRECT`, `MODEL_INTERPRETATION` permanent, provenance never silently `COMPLETE`); immutable `EvidenceBundle` preserving all six `EvidenceStatus` values; `check_not_circular` applied by a claim-bound `EvidenceReference` (`verify_against`), a claim-bound `EvidenceBundle`, and, through lineage, `EvidenceTransformation.verify_against` (a derived item cannot drop its source's restatement flag); `MinimumSufficientEvidence` as a declarative retention/reconstructability set, distinct from `CriterionEvidenceRequirement` and `EvidenceStatus.SUFFICIENT`.

**Batch 2: deferred, explicitly**

| Deferred item | Why | Owner layer |
|---|---|---|
| Observation-absence states (`NOT_OBSERVED` / `OBSERVED_ABSENT` / `OBSERVATION_INCOMPLETE` / `OBSERVATION_COVERAGE_UNKNOWN`) | Coverage contracts, not evidence contracts | **Delivered in Batch 3B** (`absence.py`) |
| Scope, validity window, relevance, specificity, integrity, correlation group, independence level, sensitivity on evidence | Named by v1 §15 / v2 §13 but no vocabulary is defined by any authoritative contract; `VerificationAssurance.assurance_scope`/`independence_level`/`integrity_verified` are assurance-level, not evidence-level, and are not aliased | Decide with the consuming layer |
| Authority / integrity / certainty rules in `EvidenceTransformation` | The contract has no fields to observe them | Evidence construction / assessment |
| `DIRECT` → `DIRECT` through a non-model transformation | Architecture gives no per-type table; accepted and tested as a documented boundary | Evidence construction / assessment |
| Claim-scoped circularity for criterion-only references/bundles | No claim id to test | Assessment |
| Privacy-exposure and cost dimensions of `MinimumSufficientEvidence` | Need the deferred sensitivity metadata | Later batch |

**G8 (deferred hardening debt):** tautological or string-blacklist tests in Batch 1; no runtime enforcement of enum-typed fields on `Assumption.status` / `Reference.quality`; `ClaimDependency` has no consuming contract yet. Not yet registered in `KNOWN_ISSUES.md` to avoid picking a `DEBT-` id that may collide with the ids already added on `main`; register at merge time.

**Inventory drift: resolved (2026-09-30).** The 16 rows that were marked ❌ although their classes exist (rows 4–9, 11, 12, 14–15, 22–23, 25–28) were re-verified against `core/verification/` and the test files and re-marked; `Rubric` (row 5) was ◐ because its `construct` field forward-referenced the then-unbuilt `VerificationConstruct` (row 47); Batch 3A built it and cleared the one remaining `mypy` error in `core/verification` (`rubric.py:145`). `Rubric` was then closed to ✅ once its `construct` became required (decision record below). Reconciliation method: class defined in `core/verification/*.py` plus test references in `tests/test_verification_contracts.py` / `tests/verification_run_tests_stdlib.py`; the depth of each contract's tests was not re-audited row by row. Remaining ❌ rows after Batch 3B: 1, 3, 10, 24, 30, 35, 36, 38, 39, 41, 42, 43, 50, 51 (14 rows).

**Batch 3A (VerificationConstruct / ConstructValidity): implemented** (approved scope only). Frozen shape: `Rubric.construct: VerificationConstruct` (required, see the decision record); `VerificationConstruct.description`; `ConstructValidity(rubric_fingerprint, status: ConstructValidityStatus)`. Invariants enforced and mutation-tested: all three are immutable; `VerificationConstruct` has no identity; `ConstructValidity` holds the rubric only by fingerprint value, so it can neither alter nor participate in the identity of the rubric it assesses; its `status` must be a `ConstructValidityStatus` (a verdict is rejected, not coerced), with no stability/confidence/verdict/consistency/score field. Deferred or open, deliberately:

| Item | Why |
|---|---|
| Behavioral "changing verifier stability must not change construct validity (and vice versa)" tests | No verifier-stability contract exists in `core/verification` yet, so there is nothing to vary. Separation is established structurally now (no such fields, no coercion from verdicts, disjoint status values) and the behavioral test belongs with the stability concept |
| Whether a `Rubric` may exist/lock without a `construct` | **Resolved** (decision record below): it may not exist without one, DRAFT included |
| Status vocabulary | IMPLEMENTATION JUDGMENT: v2 §9 defines no closed vocabulary; string values are namespaced `construct_*` because `VerificationVerdict.UNSUPPORTED == "unsupported"` would otherwise compare equal to `ConstructValidityStatus.UNSUPPORTED` (reproduced) |
| Invisible format characters (e.g. zero-width space) counted as non-blank | Same `str.strip()` rule as every other contract in the package; not a 3A-specific gap |

**Decision record — `Rubric.construct` is required** (status: DECIDED to close the 3A disposition, on the reviewer's instruction to choose one explicit contract; reversible before merge).

- *Contract:* `construct: VerificationConstruct`, no default. `None` is never valid, in any lock state. A `Rubric` cannot be built without stating what it claims to measure; the type is checked at runtime.
- *Alternative rejected:* `Optional[...] = None`, valid only while DRAFT and required from VALIDATED. It would permit DRAFT objects that can only be replaced, never completed (`advance_to` does not supply a construct), and it adds a state-dependent invariant.
- *Why required:* `fingerprint` and `criteria` are already required from construction, so rubric content is complete at construction and lifecycle states gate validation; the construct is part of that content. A construct-less rubric would carry a fingerprint that does not cover its own definition, and the same fingerprint could then denote objects with and without a construct. The approved 3A shape also specified it as required.
- *Cost, measured:* no production code constructs a `Rubric` (only tests do), so the breaking change was test-only: 24 fixtures (pytest and mirror) gained an explicit construct, and `construct` was placed before `lock_state` (no caller passes `lock_state` positionally). Cheapest now, before callers exist.
- *Not decided:* requiring a construct says nothing about whether its validity has been assessed; locking a rubric does not require any `ConstructValidity` status (including `SUPPORTED`). `ConstructValidity` still never participates in the rubric's identity.

**Batch 3B (coverage types and observation-absence states): implemented** (approved scope only). `coverage.py`: `TaskCoverage`, `VerificationCoverage`, `CriterionCoverage`, `EvidenceCoverage`, `ObservationCoverage` — five distinct frozen types with no shared base and no container; each carries `fraction: Optional[float]` in [0,1] (None means unknown; no default; bool and NaN rejected) and a required non-blank `scope`. `absence.py`: `ObservationAbsenceState` (the four states) and `ObservationAbsence`. Invariant, enforced and tested in both directions: `OBSERVED_ABSENT` is constructible only when `inspected is True`, an `InspectionAuthorization` for the *same surface* is present with `authorized is True`, and the producer-declared `coverage_sufficient is True`; the other three states do not acquire any of these requirements, and `state`, `inspected` and `coverage_sufficient` have no defaults so absence cannot be reached by omission. Mutation-checked (28 mutants, 27 caught, 1 equivalent). Deferred or open, deliberately:

| Item | Why |
|---|---|
| `VerificationObservation` (row 24) | Named in the frozen architecture, never defined; defining it now would be invention. Needs a definition first |
| Numeric definition of "sufficient" coverage | v2 §13 says "sufficient" without defining it. 3B uses a producer-declared boolean (`coverage_sufficient`) and no threshold; the contract enforces consistency but cannot check the declaration is honest |
| Relationship of `VerificationAssurance.coverage` (a scoped float) to `VerificationCoverage` | Not defined by the architecture; both left unchanged and unlinked |
| Link between `ObservationAbsence` records and the `ObservationCoverage` quantity | Not defined; no field connects them (`OBSERVATION_COVERAGE_UNKNOWN` is not enforced to match `fraction=None`) |
| State-specific rules beyond the OBSERVED_ABSENT gate (e.g. whether `NOT_OBSERVED` may carry `inspected=True`) | The frozen text imposes none; adding them would be invention |
| Denominators of the five coverage quantities | The architecture names the quantities but not what each is a fraction of; each value states its own `scope`. The one-line meaning of each type in `coverage.py` is IMPLEMENTATION JUDGMENT |
| Names `ObservationAbsenceState` / `ObservationAbsence` | IMPLEMENTATION JUDGMENT: v1 §21 uses "Observation Coverage" for the four states while v2 §13 uses `ObservationCoverage` for one of five quantities, so the state enum is named apart |
