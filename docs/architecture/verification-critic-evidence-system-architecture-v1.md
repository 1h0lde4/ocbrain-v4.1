# Verification / Critic / Evidence System — Architecture (v1)

**Status:** Draft frozen architecture, produced in this chat session from the static repository snapshot plus two research passes (see companion files). Not yet confirmed against a live repository pull. Two decisions below are marked provisional pending a full read of files this session only partially inspected.

---

## 1. Purpose

Give OCBrain a runtime trust substrate that keeps `ASSERTION → OBSERVATION → EVIDENCE → VERIFICATION → VERDICT → GOVERNANCE DECISION` distinct at every step, with provenance attached at each transition, so the system can say *why* something is trusted and not just *that* it is.

## 2. Scope

Verification of cognitive artifacts (plans, claims, decisions), runtime artifacts (tool calls, results, completion claims), reasoning artifacts (intermediate conclusions, postconditions), and memory artifacts (candidate knowledge). Rubric-driven, multi-verifier, deterministic-first.

## 3. Non-Goals

Not C-MoE, Context Compiler, Memory/Learning, Governance, Runtime, or the Evaluation Lab. Not building any V2/high-assurance item (§40) in v1 code. Not another broad research sweep — this document is a synthesis of the two prior findings files, not new investigation.

## 4. Architectural Principles

- Deterministic-first: never use a model judge for something the runtime can establish directly.
- Multiple narrow verifiers beat one universal judge (real 2026 precedent: Fara's Alignment/Rubric/Multimodal split).
- Self-report is not runtime proof — closing this gap in `EvaluatorWorker` is the single most concrete thing this architecture does.
- Evidence support and evidence attribution are different axes; passing one says nothing about the other (ProvenanceGuard, arXiv:2606.18037).
- Confidence ≠ assurance ≠ authorization ≠ task completeness ≠ verification completeness. Five different words, five different fields, never collapsed into one score.
- Historical receipts are immutable; new evidence supersedes, never edits.

## 5. Current Repository Context (summary)

252 Python files, ~49,800 LOC, real CI/ADRs/freeze audits. No existing verifier/critic/rubric/receipt infrastructure — greenfield. `EvaluatorWorker`, `ReflectionWorker`, `SupervisorWorker`, and a retrieval-scoped `graphrag.Evidence` already exist. `GovernanceKernel` structurally enforces evaluation via template method — bypass is not merely discouraged, it's not wired up as possible. C-MoE is not implemented; capability selection is deferred future work. Full detail in `verification-critic-evidence-system-phase-a-findings.md`.

## 6. Existing Adjacent Infrastructure

See the Component Ownership Matrix (§39) for the full list. The two components this architecture makes explicit decisions about are `EvaluatorWorker` and `graphrag.Evidence` — both below.

## 7. EvaluatorWorker Decision — KEEP AS MEASUREMENT-ONLY

**Provisional — based on ~45 of 297 lines read.** `EvaluatorWorker` keeps its current scope: one `EvaluationRecord` per execution, objective measurement, "evaluation never changes facts." It remains the source of event-grounded measurement.

The Verification System becomes independent and owns everything `EvaluatorWorker` explicitly disclaims — claim verification, evidence, critique, uncertainty. The one required change: `EvaluatorWorker`'s fallback to `context.parameters` when no `workflow.completed`/`worker.completed` event exists must stop silently trusting the caller. That path routes through the Verification System instead, which returns `INSUFFICIENT_EVIDENCE` rather than a trusted value. This is a staged migration — `EvaluatorWorker` keeps working throughout; only the fallback branch changes owner. Before writing the actual migration ticket, read the full 297 lines; a partial read shouldn't be the basis for a merged change.

## 8. GraphRAG Evidence Decision — KEEP + WRAP

`core/memory/retrieval/graphrag/evidence.py` is untouched. Its `Evidence`/`EvidenceSet` become one concrete `EvidenceSource` implementation in the canonical model (`source_type: RETRIEVAL`, carrying `retrieval_method` as a sub-field). An adapter/projection lifts GraphRAG evidence into the canonical `EvidenceItem` shape (§15) when it's used as verification input, adding the exact-locator and attribution machinery GraphRAG's retrieval-scoped design never needed. No second class named `Evidence` gets shipped.

## 9. Execution Identity Dependency — real gap, explicitly tracked

Runtime should own `task_id`, `execution_id`, `attempt_id`, `step_id`, `worker_id`, `artifact_id`+version+hash, `environment_id`. Verification references these; it never invents its own identity hierarchy. The repository does not yet have a stable `Operation`/`ExecutionAttempt` concept (tracked as `DEBT-015`). This is a genuine, currently-unresolved dependency, not a detail this architecture can define around: full execution-instance isolation (§29, §41) cannot be guaranteed until Runtime ships a stable identifier. The minimum v1 workaround: Verification requests *some* stable identifier for the current unit of work from Runtime, even a coarser one than the eventual model, and documents the isolation guarantee as weaker until `DEBT-015` closes.

## 10. Task Mutation Model

```
Task Mutation → Impact Analysis → {obligations, criteria, claims, evidence, results, decisions}
                                        ↓
                        each classified: PRESERVE / REUSE / RECHECK / INVALIDATE / SUPERSEDE / CANCEL
```

Mechanism: every `VerificationObligation`, `Criterion`, and `EvidenceItem` carries the fingerprint(s) of what it was checked against (task version, plan version, artifact hash, `environment_id`, rubric version). On mutation, compare fingerprints — anything whose dependency fingerprint changed gets `RECHECK` at minimum. This fingerprint-comparison model is v1. Understanding *why* something changed well enough to selectively preserve partial results (full "semantic delta propagation") is v2 — v1 is allowed to over-invalidate (recheck more than strictly necessary) rather than risk under-invalidating.

## 11. Verification Lifecycle

```
CREATED → READY → ASSIGNED → IN_PROGRESS →
   { VERIFIED, PARTIALLY_VERIFIED, CONTRADICTED, UNSUPPORTED, INSUFFICIENT_EVIDENCE, UNVERIFIABLE } →
   { ESCALATED, INVALIDATED, SUPERSEDED, EXPIRED, REQUIRES_REVERIFICATION, CANCELLED }
```

`VERIFIED` is not a permanent state — it can transition to `REQUIRES_REVERIFICATION` via the invalidation graph (§10) or `CONTRADICTED` via new conflicting evidence (§26). Non-monotonic by design.

## 12. Verification Obligations

Generated, where possible, deterministically rather than invented by a model: from explicit user requirements and constraints, plan-step outputs (Planner already knows what a step is supposed to produce), postconditions on `WorkflowNode`, capability contracts, and system invariants. Model-generated obligations remain available for genuinely underspecified cases but are the fallback, not the default.

## 13. Rubric / Criteria Architecture

`Rubric` / `Criterion` / `CriterionDependency` / `CriterionApplicability` / `CriterionEvidenceRequirement` / `CriterionResult`. Versioned, fingerprinted, validated, compiled, and **locked** before a run starts — no silent mid-run edits. Validation rejects phantom, duplicate, overlapping, contradictory, impossible, out-of-scope, and no-evidence-path criteria before compilation succeeds. This directly mirrors RuVerBench's category-level (not aggregate) scoring precedent (§13 of the research file).

## 14. Inspection Plans

```
Obligation → Criteria → Inspection Plan → observations/queries/tests/retrieval → Evidence → Assessment → Verdict
```

An `InspectionPlan` for "artifact X exists" is a filesystem check — no model call anywhere in that path. Plans are generated per-criterion from the verification-method registry (§17), not assumed to always require an LLM.

## 15. Evidence Architecture

`EvidenceSource` / `EvidenceItem` / `EvidenceReference` / `EvidenceObservation` / `EvidenceTransformation` / `EvidenceBundle`. Fields: exact locator, source identity, scope, producer, `observed_at`, `retrieved_at`, validity window, **directness** (`DIRECT` / `INDIRECT` / `DERIVED` / `MODEL_INTERPRETATION`), relevance, specificity, integrity, provenance, `correlation_group`, `independence_level`, sensitivity classification. Explicit states: unavailable / invalid / irrelevant / insufficient / sufficient / contradictory — never collapsed to a boolean.

## 16. Evidence Provenance & Exact Binding

```
Claim C7 → Evidence E14 → Source S2 → Locator L9 → Observation O4
```

— never just `Claim C7 → Source S2`. Locators: page/paragraph/span, table/cell, code line range, JSON path, DB row, API field, event ID, tool-result field. Transformation lineage (raw → retrieved → normalized → extracted → derived → claim-mapped) is preserved end to end; a model summary's `directness` field permanently reads `MODEL_INTERPRETATION`, never silently upgraded to `DIRECT`. This is the architecture's answer to the single strongest research finding this pass: exact attribution is a harder, separate problem from generic support (ProvenanceGuard's source-plus-relation accuracy collapsing to 0.229 on hard cases while support F1 stayed at 0.846).

## 17. Verification Methods

Priority order: deterministic (schema/hash/file-existence/test-execution/DB-query) → tool-backed (filesystem/repo/env/API observation) → evidence-backed semantic (support/contradiction/entailment/attribution) → independent model verification (critic/verifier) → process → outcome → safety/policy. Each method declares supported target types, evidence types, required tools, external-access needs, deterministic/stochastic, cost/latency class, known blind spots, and applicability conditions — a strategy layer selects by these declarations rather than hard-coded branching, and always tries deterministic first.

## 18. Critic Architecture

A disconfirmation engine, structurally separate from both the generator and the verdict-maker. Outputs: `unsupported_claim`, `missing_evidence`, `hidden_assumption`, `logic_gap`, `contradiction`, `scope_violation`, `false_completion`, `wrong_attribution`, `possible_counterexample`. A critique is an input to verification, not a verdict — `Critique ≠ VerificationResult ≠ Verdict`, three different objects.

## 19. Independence

Dimensions recorded per verifier invocation: context, evidence, retrieval, model, reasoning-path, tool, source, deterministic. "Different prompt, same model, same context" does not count as independent — this directly reflects the 2026 LLM-judge reliability finding that internal consistency and correctness are separate properties (arXiv:2606.19544).

## 20. Process / Outcome Verification

`ProcessVerificationResult` and `OutcomeVerificationResult` are separate objects. Correct process + external blocker → process `VERIFIED`, outcome `FAILED`, `failure_control: UNCONTROLLABLE`. Bad process + lucky success → process `FAILED`, outcome `VERIFIED`. `CONTROLLABLE` / `UNCONTROLLABLE` / `MIXED` / `UNKNOWN` is an orthogonal verification finding — it informs Governance/Supervisor but is never itself a governance decision.

## 21. Observation Coverage

`NOT_OBSERVED` / `OBSERVED_ABSENT` / `OBSERVATION_INCOMPLETE` / `OBSERVATION_COVERAGE_UNKNOWN`, kept distinct. Directly motivated by the false-success research (arXiv:2606.09863): an agent that always self-reports success shows exactly why "we didn't see a failure" must never collapse into "there was no failure."

## 22. Temporal Verification

Fields: `observed_at`, `effective_at`, `verified_at`, `decision_at`, `valid_from`, `valid_until`, `expires_at`, `freshness_requirement`, `state_version`. Timing classes: `PRE_ACTION` / `IN_FLIGHT` / `POST_ACTION` / `POST_EXECUTION` / `RETROSPECTIVE`. No temporal-logic engine in v1: Causal Past Logic's guard language (arXiv:2605.20923) is real and directly relevant research, but it solves a problem OCBrain's runtime doesn't have yet — the mandatory 4-process model (Main/Worker Pool/Webhook/Task Runner) isn't a distributed multi-agent system with independently-evolving causal histories. Timestamps plus freshness windows cover v1. Promote if the runtime becomes genuinely concurrent-multi-agent.

## 23. Confidence / Uncertainty / Abstention

`confidence`, `uncertainty`, `abstention`, `coverage`, `limitations` — five distinct fields, never one number. `INSUFFICIENT_EVIDENCE` / `UNVERIFIABLE` / `ESCALATE` are successful abstention outcomes, not verifier failures, and are measured as their own quality dimension (§38).

## 24. Verification Assurance

`VerificationBasis` / `VerificationAssurance`, kept separate from confidence. v1 values: `MODEL_ONLY`, `EVIDENCE_GROUNDED`, `MULTI_VERIFIER`, `DETERMINISTIC`, `RUNTIME_OBSERVED`. `ATTESTED` is reserved but unused in v1 — it needs Proof-of-Execution-style infrastructure (arXiv:2607.05397) this system doesn't have. Invariant: a high-confidence `MODEL_ONLY` result never outranks a lower-confidence `DETERMINISTIC` one.

## 25. Verdict Model

Canonical states: `VERIFIED` / `PARTIALLY_VERIFIED` / `CONTRADICTED` / `UNSUPPORTED` / `INSUFFICIENT_EVIDENCE` / `UNVERIFIABLE` / `CONDITIONAL` / `ESCALATE` / `UNSAFE_TO_VERIFY` / `NOT_APPLICABLE`. Truth status, verification status, and decision status are three separate fields — e.g. `truth=UNKNOWN`, `verification=INSUFFICIENT_EVIDENCE`, `decision=GATHER_MORE_EVIDENCE`, never merged.

## 26. Conflict Resolution

Conflict types: `SOURCE_CONFLICT` / `TEMPORAL_CONFLICT` / `SCOPE_CONFLICT` / `OBSERVATION_CONFLICT` / `MEASUREMENT_CONFLICT` / `AUTHORITY_CONFLICT` / `MODEL_DISAGREEMENT`. Resolved by source quality, directness, integrity, temporal validity, independence, scope, and authority — never by averaging. Non-monotonic: new contradictory evidence can move `VERIFIED → CONTRADICTED`.

## 27. Verification Receipts

Immutable per run: request/verification/task/execution/attempt/target IDs, rubric ID+version+fingerprint, criteria, claims, evidence references, observations, methods used, verifier identity/version, model/provider/version, policy version, confidence, assurance, uncertainty, verdict, coverage, contradictions, limitations, timestamps, artifact/environment identities, replayability class, provenance. New evidence never edits a receipt — it produces a new receipt that supersedes the old one; the old one remains the historical record of what was believed at the time.

## 28. Replay / Reproducibility

`FULLY_REPLAYABLE` / `PARTIALLY_REPLAYABLE` / `NON_REPLAYABLE`, recorded honestly per receipt — a receipt depending on a live external call or a non-deterministic model sample is never marked `FULLY_REPLAYABLE`.

## 29. Caching / Freshness

Cache key: task + execution + attempt + criterion + claim + evidence + artifact-version + environment + rubric-version + policy-version. A cached `VERIFIED` is never reused across execution instances even for byte-identical claim text — this is where §9's execution-identity gap most directly bites, and is the reason that gap is flagged rather than quietly worked around.

## 30. Runtime Integration

No new execution engine. `VerificationRun`/`VerificationStep` reuse the existing durable-workflow machinery (checkpoint/retry/timeout/cancel) rather than inventing a parallel one. Authoritative observations come from `EventStream.query()`, the same channel `EvaluatorWorker` already uses.

## 31. Event Integration

Minimal v1 set, deliberately trimmed from the larger list circulated earlier — emitting events nobody consumes yet is itself a violation of the "avoid unnecessary events" principle: `verification.requested`, `verification.completed`, `verification.contradiction_found`, `verification.escalated`, `verification.invalidated`. Finer-grained events (`obligation_created`, `evidence_requested`, `criterion_checked`, `confidence_updated`) are deferred until a real consumer needs that resolution.

## 32. Governance Boundary

`Verification → facts/findings/confidence/evidence/verdict → Governance → allow/deny/escalate`. One direction only. Verification never calls into `GovernanceKernel` to authorize anything; Governance never originates a verification finding it didn't receive from Verification.

## 33. C-MoE Boundary

Not implemented in the repository (confirmed). v1 exposes exactly one narrow, stable contract: `request_verification(target, assurance_level) -> VerificationResult`. No routing, orchestration, or repair logic lives inside Verification.

## 34. Context Boundary

Verification exposes verified/rejected/uncertain/stale/contradictory/critical evidence plus provenance and limitations as typed data. It does not implement compression. Its actual job for the long-trajectory problem: mark which evidence is criterion-critical, so that whatever eventually compresses context knows what it cannot afford to drop.

## 35. Memory Boundary

`Candidate Memory → Verification → (confidence, evidence, provenance, invalidation) → Memory promotion policy`. Memory owns storage and promotion; Verification never writes to memory tables directly.

## 36. Evaluation Lab Boundary

Verification emits receipts, telemetry, outcomes, and verifier metadata. It does not run population-level benchmarks. §38 (meta-evaluation) measures single-verifier reliability; a future Evaluation Lab would measure system-wide reliability across many tasks — genuinely different scope, not a naming difference.

## 37. Security

Threats: prompt injection via evidence, evidence poisoning, provenance spoofing, tool-output forgery, verifier self-preference, correlated-verifier failure, memory contamination, receipt tampering. v1 defense is structural, not policy-based: evidence is a typed `EvidenceItem`, never concatenated into a reasoning prompt as unstructured trusted text — the type boundary *is* the defense, which is the only thing that scales given AgentDojo's current published attack-success rates against undefended agents. v2: cryptographic receipt integrity, TEE/zkVM-backed attestation.

## 38. Meta-Evaluation

Interface-only in v1: accuracy, false-acceptance, false-rejection, calibration, abstention quality, stability, position/verbosity/self-preference bias, drift, regression, human/inter-verifier agreement — defined as properties any verifier method must expose. Golden corpus seeded with a real case, not a synthetic one: **G-0001**, the Aug 12, 2026 incident where a session's own report claimed "86/86 passing, production-ready" against a repository showing zero actual diff. Full meta-evaluation harness is Phase K; the interface and G-0001 are v1.

## 39. Component Ownership Matrix

| Component | Current Responsibility | Verification Interaction | Ownership | Required Change | V1/V2 |
|---|---|---|---|---|---|
| `EvaluatorWorker` | Event-grounded `EvaluationRecord`, measurement-only | Superseded as verdict source; kept as one measurement input | `EvaluatorWorker` (measurement); Verification (verdicts) | Fallback path routes through `INSUFFICIENT_EVIDENCE` (§7) | V1 |
| `ReflectionWorker` | Writes reflection as `KnowledgeEntry` | Consumes Verification findings as reflection input | `ReflectionWorker` | None | V1 |
| `SupervisorWorker` | Reacts to `CompilationResult` REJECT/ESCALATE | Gains a verification-escalation trigger | `SupervisorWorker` | Add trigger path | V1 |
| `graphrag.Evidence` | Retrieval-scoped provenance | Wrapped as one `EvidenceSource` type | GraphRAG (unchanged); Verification (adapter) | Adapter/projection only | V1 |
| Event Backbone | Records lifecycle events | Primary authoritative-observation channel | Event Backbone | Possibly new `verification.*` types (§31) | V1 |
| `GovernanceKernel` + governors | Template-method-enforced authorization | Consumes Verification output as input | `GovernanceKernel` | None | V1 |
| `BudgetGovernor` | Correct logic; `DEBT-007` — counters unwired | `VerificationBudget` should reuse this, not duplicate it | `BudgetGovernor` | `DEBT-007` fix is a prerequisite | V1, blocked on `DEBT-007` |
| Execution/attempt identity | Not implemented (`DEBT-015`) | Verification requires a stable per-unit-of-work ID | Runtime (future) | New Runtime contract | V1 dependency — currently a gap |
| C-MoE | Not implemented | Narrow future contract only | C-MoE (future) | None now | Interface-only |
| Context Compiler | Existence unconfirmed | Marks criterion-critical evidence for it | Unclear/future | None now | Interface-only |
| Evaluation Lab | Existence unconfirmed | Emits receipts/telemetry as future input | Unclear/future | None now | Interface-only |

## 40. V1 / V2 Split

| Capability | V1 | V2 | Reason |
|---|---|---|---|
| Deterministic verification | ✓ | | Always preferred first; cheapest, highest-confidence |
| Runtime observation via events | ✓ | | Already the available authoritative channel |
| Evidence model + exact binding | ✓ | | Load-bearing (ProvenanceGuard finding) |
| Provenance / transformation lineage | ✓ | | Required for any credible receipt |
| Rubric engine + validation | ✓ | | Real 2026 precedent (RuVerBench) |
| Critic (disconfirmation) | ✓ | | Cheap relative to value; CRITIC/Reflexion research |
| Multi-verifier, process/outcome split | ✓ | | Matches Fara's shipped architecture |
| Confidence / uncertainty / abstention | ✓ | | The core distinction this system exists for |
| Task mutation (fingerprint-based) | ✓ | | Needed from day one or verdicts are untrustworthy immediately |
| Verifier meta-evaluation (interface + G-0001) | ✓ | | Real case already exists; interface is cheap |
| Causal-visibility / vector-clock verification | | ✓ | Real research, but no distributed multi-agent runtime exists yet to need it |
| Cryptographic proof-of-execution / TEE / zkVM | | ✓ | High cost; local-first single-operator system lacks the adversarial-operator threat model that motivates it |
| Full temporal-logic engine | | ✓ | Freshness windows cover v1; promote if true concurrency arrives |
| Cross-agent / mission-level verification | | ✓ | No multi-agent mission concept in the runtime yet |
| Set-valued / conformal-prediction verdicts | | ✓ | Scalar confidence + explicit abstention is sufficient for v1 |
| Trained false-success classifier | | ✓ | Real technique, needs labeled trajectory data OCBrain doesn't have yet; v1 uses rule-based triage |

## 41. Architecture Risks

| Risk | Impact | Likelihood | Mitigation | Owner | V1/V2 |
|---|---|---|---|---|---|
| No stable execution/attempt identity | Execution-instance isolation not fully enforceable | Medium-high until fixed | Explicit dependency tracking; Verification doesn't claim isolation it can't back | Runtime | V1 blocker for full isolation |
| `BudgetGovernor` counters unwired | Verification budget enforcement is theoretical | Medium | Reuse once fixed, don't duplicate | Runtime/Governance | V1 blocker for real enforcement |
| `EvaluatorWorker` only partially read | Migration ticket detail could be wrong | Low-medium | Full file read required before implementing | Verification (Phase C) | V1 |
| Model-authored rubrics | Phantom/overlapping criteria | Medium | Mandatory validation stage before lock | Verification | V1 |
| Correlated verifiers | False confidence from shared bias, not real independence | Medium | `independence_level` required to reflect genuine diversity | Verification | V1 |
| Evidence-as-instruction injection | Evidence text steering a reasoning verifier | Medium-high (AgentDojo: unresolved industry-wide) | Structural type boundary, not a prompt-level rule | Verification | V1 |

## 42. Contract Preparation (Phase C)

`VerificationRequest`, `VerificationTarget`, `VerificationContext`, `VerificationObligation`, `Rubric`, `Criterion`, `CriterionDependency`, `CompiledVerificationSpecification`, `Claim`, `ClaimDependency`, `InspectionPlan`, `InspectionStep`, `EvidenceSource`, `EvidenceItem`, `EvidenceReference`, `EvidenceObservation`, `EvidenceTransformation`, `EvidenceBundle`, `VerificationMethod`, `VerificationCapability`, `VerificationObservation`, `VerificationFinding`, `Critique`, `CounterArgument`, `Contradiction`, `CriterionResult`, `ProcessVerificationResult`, `OutcomeVerificationResult`, `CoverageResult`, `VerificationResult`, `VerificationVerdict`, `VerificationConfidence`, `VerificationAssurance`, `VerificationRun`, `VerificationStep`, `VerificationReceipt`, `VerificationTrace`, `DecisionTrace`, `VerificationPolicy`, `VerificationBudget`, `EscalationRequest`, `AdjudicationRecord`. Which become a `type` vs. `schema` vs. `enum` vs. `aggregate` is a Phase C decision informed by the repository's existing conventions, not fixed here.

## 43. Implementation Plan

Phase C (Contracts) → D (Core Verification: obligations, rubric compilation, method registry, aggregation, lifecycle) → E (Evidence/Provenance) → F (Deterministic Verifiers) → G (Critic/Semantic Verification) → H (Iterative/bounded verification loops, escalation, abstention) → I (Runtime/Event Integration) → J (C-MoE narrow interfaces only) → K (Reliability/Adversarial: golden corpus starting from G-0001, fault injection, meta-evaluation harness). Sequence is a default, not a lock — adjust if Phase C reveals a better dependency order.

## 44. Acceptance Criteria (v1 "done")

Rubric validation actually rejects phantom/overlapping criteria (tested, not asserted). `EvaluatorWorker` migration ticket filed against the full file, not the partial read. GraphRAG adapter implemented without modifying `graphrag/evidence.py`. Execution-identity gap is tracked as an explicit Runtime-owned ticket, not silently worked around. Golden corpus contains G-0001. Deterministic-first ordering enforced in the strategy engine, not just documented. Receipts are append-only. No V2 item (§40 right column) has production code in v1.

## Architecture Decision Records to create

`ADR: EvaluatorWorker boundary (measurement-only, staged fallback migration)` · `ADR: GraphRAG Evidence integration (keep+wrap)` · `ADR: Canonical Evidence model shape` · `ADR: Execution identity ownership and the DEBT-015 dependency` · `ADR: V1/V2 high-assurance split` · `ADR: Receipt immutability and supersession model`.

---

## Self-Review — Pass 1 (completeness, separation, duplication, truth boundaries, execution safety, mutation, evidence, uncertainty, runtime, governance)

Completeness: the v1 scope (§4–§38) covers every load-bearing concept from both research files, with two gaps left explicit rather than papered over (§9, and `DEBT-007`) instead of quietly assumed solved. Separation: Verification/Governance/Runtime/C-MoE/Context/Memory/Evaluation-Lab boundaries are each stated as one-directional data flows (§32–§36). Duplication: no second Runtime, Governance, or budget engine — the ownership matrix (§39) makes reuse explicit rather than implicit. Truth boundaries: `EvaluatorWorker`'s fallback is the one concrete place self-report could have silently become fact, and it's closed (§7). Execution safety: scoped by design (§29) but genuinely weaker than claimed until `DEBT-015` closes — flagged, not hidden. Mutation: fingerprint-based invalidation (§10). Evidence: exact binding plus lineage (§16). Uncertainty: five distinct fields, never one score (§23). Runtime: deterministic-first is an ordering rule in the strategy layer (§17), not a suggestion. Governance: one-directional, no fabrication either way (§32).

## Self-Review — Pass 2 (missing transitions, identifiers, provenance/invalidation edges, failure states, authority boundaries, versions, freshness, concurrency, replay, scope, coverage, escalation, meta-eval path)

Two real gaps found on this pass, not corrected here because they're implementation detail, not architecture: (1) `VerificationRun` concurrency/idempotency behavior is asserted ("reuses durable-workflow machinery") but not specified at the lock/retry level — that's a Phase D question. (2) `EscalationRequest`/`AdjudicationRecord` (§36, §41 of the source mission) are named as contract types (§42) but don't yet have their own lifecycle the way `VerificationObligation` does (§11) — also Phase D. Everything else checked (identifiers, provenance edges, invalidation edges, failure states, authority boundaries, versions, freshness, replay, scope, coverage, meta-eval path) has an explicit answer somewhere above.

## Self-Review — Pass 3 (adversarial)

- Agent reports success → system trusts it: **No** — the `EvaluatorWorker` fallback closure (§7) exists specifically for this.
- Agent fabricates evidence → system accepts it: **Mitigated, not eliminated** — evidence typing and integrity fields (§15) plus the critic pass (§18) raise the bar; a sufficiently convincing fabrication could still pass one verifier, which is why multi-verifier independence (§19) is the real defense and it's probabilistic, not absolute.
- Retrieved text injects instructions → verifier obeys it: **No**, by construction — evidence is structured data (§37), never concatenated as trusted free text.
- Stale evidence → authorizes a current action: **No** — freshness fields (§22) plus mutation invalidation (§10).
- Execution A's evidence → validates execution B: **Genuine, tracked gap** — depends on `DEBT-015` resolution (§9). Not solved by this architecture alone.
- Correlated verifiers → false confidence: **Mitigated, not eliminated** — `independence_level` (§19) is required to reflect real diversity, but the 2026 judge-reliability research shows even genuinely different judges can share systematic biases.
- Bad rubric → correct-looking PASS: **No** — mandatory validation before lock (§13).
- Missing observation → false negative claim: **No** — `OBSERVATION_COVERAGE` (§21) distinguishes not-observed from observed-absent explicitly.
- Verifier crashes → PASS: **No** — fail-closed by principle (§4); a crash is `FAILED`.
- Task mutates → old verification stays valid: **No** — invalidation graph (§10).
- Receipt changes → historical truth rewritten: **No** — receipts immutable, superseded not edited (§27).
- Model confidence → mistaken for evidence: **No** — confidence/assurance are separate fields specifically to prevent this (§23–24).
- Verification → accidentally becomes authorization: **No** — one-directional governance boundary (§32).

## Final Output

**A. Phase B Status:** `ARCHITECTURE READY FOR CONTRACTS`, with one explicit, named, tracked exception: execution-instance isolation (§9, §29, Pass 3) is architecturally correct but not yet fully enforceable until `DEBT-015` closes. That's stated as a Phase C/Runtime prerequisite, not smoothed over — a frozen v1 architecture should account for what's actually resolved, not pretend everything is.

**B–O.** Covered inline above: architecture summary (§1–4), canonical diagram (reuse the one from the prior mission document — it matches this architecture and doesn't need redrawing), ownership matrix (§39), EvaluatorWorker/GraphRAG decisions (§7–8), execution identity dependency (§9), task mutation model (§10), V1/V2 split (§40), contract prep (§42), event prep (§31), migration strategy (§7, §39 row), architecture risks (§41), self-review findings (three passes above), Phase C implementation plan (§43).
