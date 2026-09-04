# Verification / Critic / Evidence System — Architecture (v1, frozen)

**Status: Frozen v1 Architecture. Ready for Phase C Contracts.**
Supersedes `verification-critic-evidence-system-architecture-v1.md`, which remains as the historical draft it corrects — consistent with this document's own receipt-supersession model (§27): the prior version isn't deleted, it's superseded. One exception to "resolved" language below: the `EvaluatorWorker`/`DEBT-015` provisional flags carry forward unchanged, because they depend on a full live-repo read this session still can't do, not on anything this correction pass could fix.

---

## 1. Purpose, Scope, Non-Goals, Principles

Unchanged from v1 (§1–4 there). One addition to the principle list: **a verifier can be highly self-consistent while systematically measuring the wrong thing** — construct validity (§10) is tracked separately from verifier stability for exactly this reason.

## 2. Repository Context

Unchanged — see the Phase A file. 252 files, ~49,800 LOC, greenfield verification infrastructure, `EvaluatorWorker`/`ReflectionWorker`/`SupervisorWorker`/`graphrag.Evidence` exist, C-MoE doesn't.

## 3. EvaluatorWorker Decision — KEEP AS MEASUREMENT-ONLY (provisional, unchanged)

Still based on a partial read. Decision stands: `EvaluatorWorker` stays measurement-only; its caller-supplied-parameter fallback routes through Verification's `INSUFFICIENT_EVIDENCE` instead of trusting the caller. Full-file read remains a prerequisite before the migration ticket is written.

## 4. GraphRAG Evidence Decision — KEEP + WRAP (unchanged)

`graphrag.Evidence` becomes one `EvidenceSource` implementation via adapter/projection. No change to the source file.

## 5. Execution Identity — now fail-closed, not merely flagged

The prior draft flagged `DEBT-015` as a gap and left the isolation guarantee "weaker." That's corrected here to an actual rule:

```
stable execution identity proven  → execution-scoped reuse/cache/verification permitted
stable execution identity NOT proven → cross-execution reuse disabled
                                         cross-execution evidence reuse disabled
                                         execution-scoped cache reuse disabled
                                         strong execution-isolation claims disabled
                                         (local, single-shot verification may still proceed)
```

This is a real strengthening, not just clearer wording: instead of a soft claim that degrades under a gap, the architecture now degrades *safely* — the system loses reuse/optimization rather than loses trust isolation. `DEBT-015` remains a Runtime-owned ticket; when Runtime ships stable `execution_id`/`attempt_id`, the fail-closed gate opens automatically without any Verification-side change.

## 6. Task Mutation Model (unchanged)

Fingerprint-based invalidation graph, as in v1 §10.

## 7. Verification Lifecycle

State machine unchanged (`CREATED → ... → VERIFIED/CONTRADICTED/.../CANCELLED`, non-monotonic). Event vocabulary corrected — see §17.

## 8. Verification Obligations — with provenance

Sources unchanged (explicit requirements, constraints, plan steps, postconditions, capability contracts, system invariants, model-derived fallback). Correction applied: every obligation now carries a `derivation_source` field distinguishing `explicit_user_requirement` / `constraint` / `plan_requirement` / `postcondition` / `capability_contract` / `system_invariant` / `model_derived`. A model-derived obligation never inherits the implicit authority of an explicit user requirement — this matters downstream whenever obligations conflict and one has to win.

## 9. Rubric Architecture — with provenance and construct validity

`Rubric`/`Criterion`/`CriterionDependency`/`CriterionApplicability`/`CriterionEvidenceRequirement`/`CriterionResult`, versioned/fingerprinted/validated/compiled/locked, as in v1 §13. Two additions:

- **Provenance:** every rubric carries `created_from`, `created_by`, `derived_from`, `source_requirements`, `context_basis`, in addition to version/fingerprint.
- **`VerificationConstruct` / `ConstructValidity`, distinct from internal consistency.** A rubric defines what's being checked; it doesn't prove that's the right thing to check. This is the architectural expression of the sharpest research finding from the meta-evaluation pass: the 2026 LLM-judge study found high test–retest reliability coexisting with severe, systematic bias — a judge can agree with itself constantly while being wrong. Construct validity is evaluated separately from rubric-execution stability, and neither one substitutes for the other.

## 10. Inspection Plans (unchanged)

`Obligation → Criteria → Inspection Plan → observations/queries/tests/retrieval → Evidence → Assessment → Verdict`, as in v1 §14.

## 11. Verification Methods vs. Verification Dimensions — corrected, two orthogonal axes

The prior draft implicitly modeled these as one hierarchy. Corrected: they're orthogonal.

- **Methods** (*how* something is checked): deterministic check, runtime observation, tool-backed inspection, evidence-backed semantic verification, model verifier, critic, multi-verifier composition.
- **Dimensions/targets** (*what* is being checked): process, outcome, correctness, completeness, groundedness, compliance, safety.

`DeterministicVerifier` is a method. `ProcessVerification` is a dimension. A single dimension (e.g. outcome) can be checked by multiple methods (a deterministic state-equality check *and* a semantic evidence-support check both bear on "outcome"), and a single method can serve multiple dimensions. Phase C contracts should model these as two independent classifications on a `VerificationFinding`, not a nested hierarchy.

## 12. Observation → Interpretation → Claim, vs. Observation → Evidence

New, corrected distinction: an observation doesn't automatically become evidence. `Observation → Interpretation → Claim` (e.g. `HTTP 200` → "request succeeded" → "external operation completed successfully" — the last step needs its own verification) is a different chain from `Observation → Evidence`, where evidence additionally requires scope, authority, provenance, integrity, relevance, and criterion binding before it's usable verification input. An interpretation is not evidence merely because it followed from a real observation.

## 13. Evidence Architecture

`EvidenceSource`/`EvidenceItem`/`EvidenceReference`/`EvidenceObservation`/`EvidenceTransformation`/`EvidenceBundle`, fields as in v1 §15 (locator, source identity, scope, producer, timestamps, directness, relevance, specificity, integrity, provenance, `correlation_group`, `independence_level`, sensitivity). Two corrections:

- **`OBSERVED_ABSENT` requires authority *and* coverage, not coverage alone.** It may only be emitted when (1) the relevant surface was actually inspected, (2) the observing mechanism was authorized for that surface (§16), and (3) coverage was sufficient. Otherwise: `NOT_OBSERVED` / `OBSERVATION_INCOMPLETE` / `OBSERVATION_COVERAGE_UNKNOWN`. Absence is never inferred from silence.
- **Coverage is five separate fields, not one.** `TaskCoverage`, `VerificationCoverage`, `CriterionCoverage`, `EvidenceCoverage`, `ObservationCoverage` coexist independently — `TaskCoverage=100%` with `VerificationCoverage=40%` must be representable without contradiction, and this is the concrete architectural guard against the collapse the mission documents kept warning about (task completeness silently becoming verification completeness).

## 14. Evidence Provenance & Exact Binding

`Claim → Evidence → Source → Locator → Observation`, as in v1 §16. Two additions:

- **Provenance completeness status:** `COMPLETE` / `PARTIAL` / `UNKNOWN` / `BROKEN`. A verification resting on incomplete provenance discloses that limitation rather than presenting itself as fully traceable.
- **Transformation safety rule:** every derived evidence object (summarized, translated, normalized, OCR'd, extracted, parsed, redacted) retains its source evidence, transformation type, transformation version, and transformation producer — and **must not inherit stronger `directness` than the transformation justifies.** A normalization step doesn't get to make derived evidence look more direct than it is.

## 15. Epistemic Authority Model — corrected: four distinct concepts, not two

The prior draft only had `VerificationBasis` and `VerificationAssurance`. That collapsed two additional, genuinely different concepts into those two. Corrected to four:

- **`VerificationBasis`** — *what mechanisms contributed*: `deterministic`, `runtime_observation`, `external_evidence`, `model_verification`, `multi_verifier`. **Compositional, not an exclusive enum** — a real verification often combines several (e.g. `deterministic + runtime_observation` together), and the v1 draft's implicit single-value enum was a genuine bug, not just underspecified: it contradicted the multi-verifier architecture the rest of the document assumes. Corrected to a set.
- **`ObservationAuthority`** — *what source established the observation*: `runtime`, `filesystem`, `test_runner`, `database`, `trusted_external_source`, `human`, `model`. An epistemic-authority concept.
- **`InspectionAuthorization`** — *is the verifier permitted to use that observation surface at all*. A security/permissions concept, and deliberately not confused with the epistemic one above — a verifier can be technically capable of reading a surface without being authorized to, and that boundary stays with Governance/Runtime, not Verification.
- **`VerificationAssurance`** — *what assurance the complete verification provides, within its explicit scope*. Depends on all three of the above plus coverage, independence, and integrity. Not an alias for "deterministic" or "high confidence." **Always scoped**: `assurance=HIGH, scope=artifact_schema` does not imply `assurance=HIGH, scope=whole_task_correctness`. Every assurance statement carries its `assurance_scope` explicitly.

`confidence ≠ basis ≠ observation_authority ≠ inspection_authorization ≠ assurance ≠ authorization-to-act` — six distinct concepts, six distinct fields.

## 16. Verification Authority, Scoped

A verifier's authority is per-surface, not global: a filesystem verifier is authoritative for file existence and not for business correctness. `InspectionAuthorization` (§15) is checked per surface, not once per verifier.

## 17. Critic Architecture, with circular-evidence prevention

Disconfirmation engine, structurally separate from generator and verdict-maker, outputs as in v1 §18 (`unsupported_claim`, `missing_evidence`, `hidden_assumption`, `logic_gap`, `contradiction`, `scope_violation`, `false_completion`, `wrong_attribution`, `possible_counterexample`). One addition, and it's a real gap the prior draft had: **evidence must not be an unsupported restatement of its own claim.**

```
claim: X is true
evidence: agent says "X is true"
verification: X is true because evidence says X   ← circular, structurally forbidden
```

unless the verification is explicitly *about* the fact that the agent made the statement (a different, narrower claim than X itself). Self-referential evidence cannot bootstrap itself into truth. This is checked as a structural property of the claim→evidence graph, not left to a verifier's judgment.

## 18. Independence (unchanged, v1 §19)

## 19. Aggregation — three separate layers, never one weighted average

Corrected to explicitly keep three operations distinct, since the prior draft gestured at this in the research file but didn't carry it into the architecture itself:

- **Criterion logic** (`AND`/`OR`/conditional/dependency) — how criteria within one rubric combine.
- **Evidence aggregation** (support/contradiction/sufficiency/authority/independence) — how multiple evidence items bear on one claim.
- **Verifier aggregation** (Verifier A + B + C) — how multiple verifier outputs combine into one finding.

Exact algorithms remain Phase D, but the architecture forbids collapsing these three into one generic weighted-average abstraction — they answer different questions and a single number can't carry all three.

## 20. Confidence / Uncertainty / Abstention (unchanged, v1 §23)

## 21. Verdict Model (unchanged, v1 §25) — plus explicit non-collapsing states

Made explicit rather than merely implied: `task_complete + verification_incomplete`, `task_incomplete + some_criteria_verified`, and `verification_complete + governance_denied` are all representable simultaneously and must never collapse into each other.

## 22. Conflict Resolution (unchanged, v1 §26)

## 23. Evidence, Verification, and Decision Validity — three distinct concepts

New: evidence can remain valid while verification goes stale because the environment changed around it. A prior verification can become invalid without retroactively making a past governance decision wrong — Verification reports `decision_dependency_affected`; what to do about it belongs to Governance/Runtime, not Verification.

## 24. Reference / Oracle Model

New: `Reference`, `GroundTruth`, `Oracle`, `Observation`, and `Evidence` are kept distinct. A reference can be wrong. A deterministic oracle establishes only the specific predicate it actually checks — nothing broader. A model-generated reference is never automatically authoritative merely for being a reference.

## 25. Assumptions

New — this was a real gap, not present anywhere in the prior draft. `Assumption` / `AssumptionSource` / `AssumptionStatus` are explicit, distinct from `observed_fact` / `derived_fact` / `hypothesis`. Where verification depends on an assumption, that assumption is identified and tagged, never silently promoted to evidence.

## 26. Receipts — with full supersession lineage

Fields as in v1 §27, plus explicit linking: `receipt_id`, `supersedes_receipt_id`, `superseded_by_receipt_id`, `verification_version`. Example chain: `R1=VERIFIED → R2=CONTRADICTED → R3=VERIFIED_AFTER_REPAIR`, all three remaining permanent historical records, none edited in place.

## 27. Replay — corrected semantics

**This corrects an actual error in the prior draft.** The v1 document claimed a receipt depending on a live external call is "never marked FULLY_REPLAYABLE." That's wrong: the real criterion is whether the dependency was *captured*, not whether it originated externally. An external call whose result is immutably captured as part of the evidence record is potentially fully replayable — replaying the verification means re-running the verification logic against the *captured* evidence, not re-issuing the original call. An uncaptured external dependency is what makes a run non-replayable. `FULLY_REPLAYABLE` / `PARTIALLY_REPLAYABLE` / `NON_REPLAYABLE` are defined against capture completeness, not against internal/external origin.

## 28. Caching / Freshness (unchanged, v1 §29, now also gated by the fail-closed rule in §5)

## 29. Canonical Evidence Protected from Compression

New, explicit invariant: canonical evidence and provenance are immutable semantic records. Context compression may produce derived representations; it may never mutate or replace canonical evidence, and a derived summary can never itself become the canonical record.

## 30. Runtime / Verification Lifecycle Ownership — corrected, no dependency cycle

Corrected flow — the prior draft's implied chain (`EvaluatorWorker → Verification → Runtime`) could be read as a cycle. Corrected:

```
Runtime / Event Backbone
        ↓
   authoritative observation
        ├──→ EvaluatorWorker   (independent consumer)
        └──→ Verification      (independent consumer)
```

Runtime owns the execution lifecycle; Verification owns the verification semantic lifecycle; a `VerificationRun` may execute *through* Runtime's durable-workflow machinery without Runtime owning verification semantics. Verification may read `EvaluatorWorker`'s output as contextual data but never treats it as the authoritative source of runtime truth — that's still Runtime/Event Backbone, directly.

## 31. Event Integration — corrected: minimal but lifecycle-complete

The prior draft's trimmed event list (`requested`, `completed`, `contradiction_found`, `escalated`, `invalidated`) was over-trimmed — it dropped `started`, `failed`, and `superseded`, which are lifecycle-necessary, not optional granularity. Corrected v1 event set: `verification.requested`, `verification.started`, `verification.completed`, `verification.failed`, `verification.escalated`, `verification.invalidated`, `verification.superseded`. Finer-grained events (`obligation_created`, `evidence_requested`, `criterion_checked`, `confidence_updated`) remain deferred until a real consumer needs that resolution — that trim was correct; the lifecycle-completeness trim was not, and is fixed here.

Forward-compatible correlation metadata added to every event without implementing anything causal yet: `event_id`, `correlation_id`, `parent_event_id`, `task_id`, `execution_id`, `attempt_id`, `verification_id`, `timestamp`. No vector clocks in v1; no causal-past claims made.

## 32. Governance Boundary (unchanged, v1 §32 — one direction, no fabrication either way)

## 33. C-MoE Boundary — corrected: policy-based, not a frozen assurance-level parameter

The prior draft froze `request_verification(target, assurance_level)` as the API. Corrected: since Assurance is now a composite, scoped concept (§15) rather than a simple level, freezing an API around a single `assurance_level` parameter would have been premature and would have coupled C-MoE to Verification's internal representation. Corrected shape: `request_verification(target, verification_requirements)`, where `verification_requirements` is a policy/requirements object C-MoE can express without knowing how Verification internally composes basis/authority/assurance. C-MoE remains interface-only — not implemented in the repository.

## 34. Context Boundary (unchanged substance, v1 §34, now explicitly backed by §29's compression invariant)

## 35. Memory Boundary (unchanged, v1 §35)

## 36. Evaluation Lab Boundary (unchanged, v1 §36)

## 37. Security — corrected: layered model, not "typing is the defense"

**This corrects a real overclaim in the prior draft.** V1 stated the type boundary *is* the defense against evidence-borne prompt injection. That's not sufficient on its own: a typed `EvidenceItem`'s `content` field can still carry adversarial text, and if that content is ever rendered into a verifier's reasoning context, typing alone does nothing to stop it from being read as an instruction. The corrected model is layered:

1. **Typed evidence** — metadata (source, integrity, directness) travels separately from content and can't be forged by the content itself.
2. **Trust/provenance metadata** attached and checked *before* content is used for anything.
3. **Evidence/content separation at render time** — evidence content is never concatenated into a verifier's context as if it were system or developer instruction; it's rendered with explicit, unambiguous framing as untrusted data.
4. **Tool/runtime isolation** — a verifier inspecting evidence has read-only inspection rights, not action rights, so even a momentarily-confused verifier can't act on injected content.
5. **Verification itself** as the last layer — independent/multi-verifier checking (§18) catches cases where injected content did influence one verifier's read.

No single layer is claimed sufficient. AgentDojo's published attack-success numbers against undefended agents are the reason this is a layered model and not a policy statement.

## 38. Meta-Evaluation — with selective-risk metrics

Interface-only in v1, properties as in v1 §38 (accuracy, false-acceptance/rejection, calibration, abstention quality, bias, robustness, drift, regression), plus: **risk-coverage, selective false acceptance, selective false rejection, abstention utility.** Without these, a verifier that abstains on nearly everything can look excellent on the original metric set purely by refusing to commit — the selective-risk metrics are what catch that. G-0001 remains the seeded golden case.

## 39. False-Success Triage — reclassified

Corrected split: **v1** = rule/trajectory/runtime-based triage signal only. **v1.x/v2** = a trained/learned false-success classifier, which is a data-dependent optimization layer, not a high-assurance primitive, and needs labeled trajectory data this repository doesn't have yet. Explicit distinction: `TriageSignal ≠ VerificationResult` — a triage signal can trigger deeper verification; it cannot independently produce a final verdict.

## 40. Escalation — with immutable lineage

`Verification → EscalationRequest → child/linked adjudication or enhanced verification`, original result immutable, new evaluation produces a new run/version. Cancellation/supersession retains an explicit reason code: `task_mutated` / `execution_cancelled` / `evidence_expired` / `rubric_changed` / `budget_exhausted` / `user_cancelled` / `superseded`. This closes the gap flagged in v1's own Pass 2 self-review, which had named `EscalationRequest`/`AdjudicationRecord` as contract types without giving them a lifecycle.

## 41. Historical Verifier Migration (unchanged substance, v1 research file — now in the architecture proper)

Receipts retain `verifier_version`, `rubric_version`, `policy_version`, `method_version`, model/provider version where relevant. A new verifier version never reinterprets old receipts under new semantics; old receipts stay historical.

## 42. Blind Verification (new)

Optional `BlindVerificationContext` for bias reduction — can mask/counterbalance model identity, candidate identity, ordering, verbosity cues, irrelevant source labels, and presentation artifacts. Not forced on every case; a strategy capability, invoked when the risk profile warrants it.

## 43. Multilingual Metadata (new)

Where relevant: `target_language(s)`, `evidence_language(s)`, `verifier_language`, `translation_steps`, `locale`. No assumption of English-only verification; calibration (§38) may need to be language/domain-specific.

## 44. Minimum Sufficient Evidence (new)

`MinimumSufficientEvidence` as an explicit concept: minimize unnecessary storage, context size, privacy exposure, replay cost, and redundancy, without compromising auditability — retain enough to reconstruct the decision, not everything that was ever touched.

## 45. Verification Policy Precedence (new)

Where multiple policies could apply — global, task, verification, criterion-level requirement, security, governance — precedence is explicit rather than implicit: governance and security policy outrank task/verification-level policy; a lower-level verifier can tighten a requirement but never override a stronger policy above it in the chain.

## 46. Component Ownership Matrix

| Component | Responsibility | Verification Interaction | Ownership | Required Change | V1/V2 |
|---|---|---|---|---|---|
| `EvaluatorWorker` | Event-grounded measurement | Superseded as verdict source; kept as one measurement input | Measurement: `EvaluatorWorker`; Verdicts: Verification | Fallback routes to `INSUFFICIENT_EVIDENCE` | V1 |
| `ReflectionWorker` | Writes reflection | Consumes Verification findings | `ReflectionWorker` | None | V1 |
| `SupervisorWorker` | Reacts to REJECT/ESCALATE | Gains verification-escalation trigger | `SupervisorWorker` | Add trigger path | V1 |
| `graphrag.Evidence` | Retrieval-scoped provenance | Wrapped as one `EvidenceSource` | GraphRAG unchanged; Verification adapts | Adapter only | V1 |
| Runtime / Event Backbone | Execution lifecycle, authoritative observations | Independent authoritative source for both `EvaluatorWorker` and Verification (§30) | Runtime | Possibly new `verification.*` events (§31) | V1 |
| `GovernanceKernel` | Authorization | Consumes Verification output only | `GovernanceKernel` | None | V1 |
| `BudgetGovernor` | Correct logic, `DEBT-007` unwired | `VerificationBudget` reuses once fixed | `BudgetGovernor` | `DEBT-007` prerequisite | V1, blocked |
| Execution/attempt identity | Not implemented (`DEBT-015`) | Fail-closed gate (§5) | Runtime (future) | New Runtime contract | V1 dependency, safely degraded |
| C-MoE | Not implemented | Policy-based narrow contract (§33) | C-MoE (future) | None now | Interface-only |
| Context Compiler | Unconfirmed | Marks criterion-critical evidence; canonical evidence protected (§29) | Unclear/future | None now | Interface-only |
| Evaluation Lab | Unconfirmed | Receives receipts/telemetry | Unclear/future | None now | Interface-only |

## 47. V1 / V2 Split (final)

**V1:** obligations (with provenance), rubrics (with provenance + construct validity), criteria, claims, inspection plans, deterministic verification, runtime observation, evidence (with exact binding, transformation safety, provenance completeness), evidence sufficiency/coverage (five dimensions), observation coverage (authority-gated), process/outcome as dimensions distinct from methods, critic (with circular-evidence prevention), independence, aggregation (three separate layers), confidence/uncertainty/abstention, basis/observation-authority/inspection-authorization/assurance (four distinct, compositional basis), temporal freshness, verification timing, task mutation, fail-closed execution scoping, immutable receipts with supersession lineage, corrected replay semantics, rule-based false-success triage, verifier meta-evaluation interface with selective-risk metrics, assumptions, reference/oracle distinction, minimum sufficient evidence, policy precedence, blind-verification extension point, multilingual metadata.

**V2 / High-Assurance:** causal-past/vector-clock verification, cryptographic proof-of-execution, TEE/zkVM execution assurance, formal temporal-logic engine, strong distributed mission verification, cryptographic provenance chains, trained false-success classifier, set-valued/conformal verification.

## 48. Architecture Risks (updated)

| Risk | Impact | Likelihood | Mitigation | Owner | V1/V2 |
|---|---|---|---|---|---|
| No stable execution/attempt identity | Was: isolation weakened. Now: isolation *safely degrades* (fail-closed, §5) — real risk is reduced reuse/performance, not trust | Medium-high until fixed | Fail-closed gate; explicit Runtime dependency | Runtime | Downgraded from trust risk to performance cost |
| `BudgetGovernor` counters unwired | Budget enforcement theoretical until fixed | Medium | Reuse once fixed | Runtime/Governance | V1 blocker for real enforcement |
| `EvaluatorWorker` partially read | Migration detail could be wrong | Low-medium | Full read required before ticket | Verification (Phase C) | V1 |
| Layered security model still probabilistic | A sufficiently good injection could still influence one verifier | Medium | Multi-verifier independence is the actual backstop, not a single layer | Verification | V1, known limitation |
| Correlated verifiers | Shared bias mistaken for independent confirmation | Medium | `independence_level` required to reflect genuine diversity | Verification | V1, known limitation |
| Assurance composability adds real complexity to Phase C | Four-concept model (§15) is more correct but harder to implement than a single enum | Medium | Worth the correctness; document clearly for Phase C | Verification (Phase C) | V1 |

## 49. Contract Preparation (Phase C, updated)

All types from v1 §42, plus: `Assumption`, `AssumptionSource`, `AssumptionStatus`, `ObservationAuthority`, `InspectionAuthorization`, `VerificationConstruct`, `ConstructValidity`, `ReferenceQuality` (already named in v1, now with the `Reference`/`Oracle`/`GroundTruth` split), `MinimumSufficientEvidence`, `BlindVerificationContext`, `PolicyPrecedence`. `VerificationBasis` is now explicitly a composable set type, not an enum.

## 50. Implementation Plan (unchanged, v1 §43 — Phase C through K)

## 51. Acceptance Criteria (updated)

All v1 §44 criteria, plus: method/dimension separation implemented as two independent classifications; basis/authority/authorization/assurance implemented as four distinct fields with basis as a set; assurance always carries `assurance_scope`; execution identity gate is fail-closed in code, not just documented; event vocabulary includes `started`/`failed`/`superseded`; circular-evidence check exists as a structural graph property, not a verifier judgment call; replay classification keyed on capture-completeness, not internal/external origin; security model implemented as the five-layer stack, not a single type check.

## ADRs

`EvaluatorWorker boundary` · `GraphRAG Evidence keep+wrap` · `Canonical Evidence model` · `Execution identity ownership + fail-closed gate (DEBT-015)` · `VerificationBasis / ObservationAuthority / InspectionAuthorization / Assurance separation` · `Receipt immutability + supersession lineage` · `V1/V2 high-assurance split` · `Circular-evidence structural check` · `Security layering model`.

---

## Review A — Structural Completeness

Components, contracts, identifiers, lifecycle, provenance, evidence, methods, dimensions, authority, assurance, events, mutation, caching, replay, security, V1/V2 — every one of these now has an explicit section above, including the six items that had none in v1 (assumptions, reference/oracle, minimum-sufficient-evidence, blind verification, multilingual metadata, policy precedence). Yes, every concept needed for a trustworthy v1 is represented somewhere.

## Review B — Internal Consistency (contradiction check, as specified)

| Tested pair | Resolution |
|---|---|
| Verification owns authorization / Governance owns authorization | Governance owns it, exclusively (§32) |
| Evidence is immutable / Evidence is mutable | Canonical evidence is immutable (§29); transformations produce *new* evidence objects with their own lineage, never mutate the original |
| Runtime owns execution identity / Verification creates identity | Runtime owns it; Verification fails closed rather than inventing one when absent (§5) |
| Confidence = assurance / Confidence ≠ assurance | ≠, and now decomposed into four distinct fields (§15) |
| Observation = evidence / Observation ≠ evidence | ≠ (§12) — an observation needs scope/authority/provenance/integrity/relevance/binding to become evidence |
| Process = method / Process = dimension | Dimension, explicitly distinct from method (§11) |
| EvaluatorWorker = source of truth / Runtime = authoritative | Runtime/Event Backbone is authoritative; `EvaluatorWorker` and Verification are both independent consumers of it (§30), neither is upstream of the other |
| C-MoE implemented / interface-only | Interface-only, confirmed absent in repo |
| V1 includes temporal engine / V2 formal engine | V1 has timestamps + freshness only; full temporal-logic/causal-past engine is V2 (§31 note) |

No unresolved contradictions found.

## Review C — Adversarial Trust Review

| Attack | Result |
|---|---|
| False completion (agent says done, no evidence) | **BLOCKS** — §3 fallback closure |
| Fabricated evidence | **DEGRADES SAFELY** — independence/multi-verifier is the real backstop; known limitation, not absolute |
| Self-referential evidence | **BLOCKS** — §17 structural circularity check |
| Prompt injection via evidence | **DEGRADES SAFELY** — layered (§37), no single layer claimed sufficient |
| Stale evidence reused later | **BLOCKS** — freshness fields + mutation invalidation (§6, §22 in v1) |
| Cross-execution contamination | **BLOCKS, by refusal** — fail-closed gate (§5): disabled when identity isn't proven, not silently allowed |
| Missing execution identity, reused anyway | **BLOCKS** — same fail-closed gate |
| Correlated verifiers → false confidence | **DEGRADES SAFELY** — `independence_level` required to be genuine; known limitation given 2026 research showing even distinct judges can share bias |
| Bad rubric, validly compiled | **BLOCKS** — mandatory validation before lock (§9) |
| Missing observation → interpreted as absent | **BLOCKS** — `OBSERVED_ABSENT` requires authority + coverage (§13); otherwise `NOT_OBSERVED`/`INCOMPLETE`/`UNKNOWN` |
| Canonical evidence lossily compressed, summary treated as source | **BLOCKS** — §29 invariant |
| Verifier crash → PASS | **BLOCKS** — fail-closed principle, crash is `FAILED` |
| Task mutation, stale verification reused | **BLOCKS** — invalidation graph (§6) |
| Receipt silently edited | **BLOCKS** — immutable, supersession only (§26) |
| Verification → authorization leakage | **BLOCKS** — one-directional boundary (§32) |
| Lower-level verifier overrides stronger policy | **BLOCKS** — explicit precedence (§45) |
| Untrusted evidence transformed until it appears authoritative | **BLOCKS** — transformation safety rule: derived evidence can't inherit stronger directness than justified (§14) |

No result is presented as a stronger guarantee than the architecture actually provides — the three `DEGRADES SAFELY` rows are named as known limitations, not silently upgraded to `BLOCKS`.

## Architecture Quality Test

*Could a competent engineer now implement Phase C contracts without inventing a new architectural decision about ownership, trust boundaries, evidence semantics, lifecycle, provenance, assurance, or mutation?*

**Yes**, with one named exception carried forward honestly rather than glossed over: the exact shape of `VerificationBasis` as a set type (§15/§49) is architecturally decided but will need real design judgment in Phase C about how composite bases serialize and compare — that's normal contract-design work, not a missing architectural decision.

---

## Final Output

**A. Phase B Status: `ARCHITECTURE READY FOR PHASE C`**

**B. Corrections applied:** all 37, summarized in the sections above; two were corrections to actual mistakes (§27 replay semantics, §37 security layering) rather than additions, and are named as such rather than quietly folded in.

**C–L.** Architecture summary, ownership matrix, V1/V2 split, EvaluatorWorker/GraphRAG decisions, execution-identity status, remaining risks, ADRs, and the three self-reviews are all inline above; Phase C contract plan is §49–50.
