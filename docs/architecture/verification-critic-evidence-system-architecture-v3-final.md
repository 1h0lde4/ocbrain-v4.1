# Verification / Critic / Evidence System — Architecture (v1, frozen, final)

**Status: Frozen v1 Architecture. Ready for Phase C Contracts.**
Supersedes `verification-critic-evidence-system-architecture-v2-frozen.md`. This pass adds genuinely new architecture (below) and re-verifies everything from v2 via audit tables rather than restating unchanged sections — a 30-row table that says "unchanged, see v2 §X" is more honest than 30 paragraphs that repeat v2 verbatim to look thorough.

---

## Part 1 — New architecture this round

### 1. Verification Shape: POINTWISE / PAIRWISE / SET_LEVEL

Not previously defined (see correction above). `VerificationShape` is a new axis, orthogonal to method (§11 v2) and dimension (§11 v2): **POINTWISE** (default — one target checked against criteria) / **PAIRWISE** (A vs. B compared directly) / **SET_LEVEL** (ranking or selection among a set). POINTWISE remains the default for ordinary verification; PAIRWISE/SET_LEVEL are invoked only when the task genuinely is a comparison — never forced onto ordinary single-target verification.

### 2. Pairwise Consistency — distinct from order bias

Two different failure modes, kept as two different checks:

- **Order bias** — does swapping the presentation order of A and B change the verdict for *that one comparison*? A robustness property of a single judgment. Mitigated by bidirectional evaluation (`BlindVerificationContext`, v2 §42) — run both orderings, compare.
- **Pairwise / cycle consistency** — across *multiple* comparisons, do they form a coherent relation? `A>B, B>C, C>A` is a cycle, not a set of independently-fine judgments — it means the comparisons don't jointly describe anything coherent. This is only detectable at `SET_LEVEL`, not from any single pairwise judgment in isolation.

`PairwiseConsistency` is added as a verifier meta-evaluation dimension. The pipeline the architecture defines: `pairwise judgment → comparison relation → consistency/transitivity analysis → aggregation`. The exact aggregation algorithm (how to resolve a detected cycle — simple tournament, Bradley-Terry-style rank estimation, or something else) is explicitly Phase D, not decided here.

### 3. Requirements / Policy / Strategy / Profile — four distinct concepts

A real gap: v2 used `verification_requirements` as a C-MoE-facing parameter name (v2 §33) without architecting it as one of four genuinely different things:

- **`VerificationRequirements`** — what the caller actually needs verified, and to what rigor, expressed declaratively.
- **`VerificationPolicy`** — system-level constraints on what's permitted or required, set by Governance/system configuration, not by the caller (e.g. "safety-critical claims always require multi-verifier composition").
- **`VerificationStrategy`** — the internal method-selection logic (v2 §17, §32) that decides which methods, how many verifiers, how deep — informed by both Requirements and Policy, plus risk/cost.
- **`VerificationProfile`** — a stable, named, external-facing bundle. This recovers something the *original* mission document specified (`LIGHT` / `STANDARD` / `HIGH_ASSURANCE` policy classes) that never actually made it into the architecture until now. C-MoE requests a `VerificationProfile` or raw `VerificationRequirements` — it never manipulates `VerificationStrategy` internals directly, which sharpens the C-MoE boundary correction from v2 §33 rather than replacing it.

### 4. Verification Target Snapshot / Fingerprint

`VerificationTargetSnapshot` / `VerificationTargetFingerprint` — the frozen, exact version of what was evaluated (content hash, version, timestamp), distinct from the live/current version of that same logical target. Mostly a naming exercise: this makes explicit what the fingerprint-based mutation model (v2 §6) was already implicitly doing, so Phase C has an actual named type instead of an implied one.

### 5. State / Transition / Invariant Verification

Three subtypes under the existing dimension taxonomy (v2 §11): `StateVerification` ("does X exist / is X true now"), `TransitionVerification` ("did action A correctly change S1→S2"), `InvariantVerification` ("did constraint X remain true throughout"). Adds precision to "outcome" and "process" without introducing new top-level concepts.

### 6. Retention: Evidence / Receipt / Source, kept separate

`EvidenceRetention` / `ReceiptRetention` / `SourceRetention` as independent policies. Evidence can be pruned for storage or privacy reasons (v2 §44, minimum sufficient evidence) while its receipt remains. Explicit consequence chain: evidence expires → historical receipt still stands as the record of what was concluded → but current replayability degrades (v2 §27) and exact re-verification of that specific claim may require gathering evidence again from scratch, not resuming from the old record.

### 7. Idempotency / concurrency — semantics, not implementation

A real requirement the architecture should state even though the mechanism is Phase D: verification requests are keyed for idempotency on `(request_id, target_fingerprint, profile_version)`. Duplicate or concurrent requests against the same key must never corrupt a receipt, evidence record, or result — "no corruption" is the architectural invariant; the locking/dedup mechanism itself is Phase D/Phase C detail, same judgment call as v2's Pass 2 self-review already made about this.

### 8. Controls taxonomy for the golden corpus

Extends G-0001 (v2 §38) rather than replacing it: the corpus should contain **positive**, **negative**, **ambiguous**, **partial**, and **adversarial** controls as standard categories. This matters concretely for one new invariant worth stating explicitly: **abstention on a genuinely ambiguous or insufficient-evidence control case is scored as correct behavior, not as a defect.** Without ambiguous/partial controls in the corpus, a verifier that never abstains can look artificially better than one that abstains appropriately — this is the architectural fix for that.

### Meta-evaluation matrix — updated

Added to v2 §38's dimension list: position bias, candidate-order sensitivity, score-range sensitivity, pairwise consistency, cycle consistency, transitivity, epistemic-marker sensitivity (does hedging language like "I think" get misread as a quality signal), declared-vs-observed independence (does a verifier's claimed independence level match what's empirically measured). None of these collapse into one generic "bias" metric — each is its own row.

### Contract preparation — additions

To v2 §49's list: `VerificationShape`, `PairwiseConsistency`, `VerificationRequirements`, `VerificationPolicy`, `VerificationStrategy`, `VerificationProfile`, `VerificationTargetSnapshot`, `VerificationTargetFingerprint`, `StateVerification`, `TransitionVerification`, `InvariantVerification`, `EvidenceRetention`, `ReceiptRetention`, `SourceRetention`, `ControlCase` (with `control_type: positive|negative|ambiguous|partial|adversarial`).

---

## Part 2 — Reconfirmation of prior corrections (v2, audited against the live document rather than restated)

| Area | Status |
|---|---|
| Trust chain (assertion→observation→evidence→verification→assessment→verdict→authorization) distinct | Unchanged, v2 §1, §32 |
| Epistemic model (basis/observation authority/inspection authorization/assurance/confidence/uncertainty) distinct | Unchanged, v2 §15 |
| Verification structure (requirements→obligations→rubric→criteria→claims→inspection plan→methods→dimensions→assessment→verdict) distinct | Unchanged, v2 §8–§11, §25; **Requirements** now further split per Part 1 §3 above |
| Runtime dependency direction (Runtime/Event Backbone → observation → EvaluatorWorker / Verification, independently) | Unchanged, v2 §30 |
| Execution identity fail-closed | Unchanged, v2 §5 |
| EvaluatorWorker: measurement-only, fallback closed, full-read still a prerequisite | Unchanged, v2 §3 — still provisional for the same honest reason |
| GraphRAG: keep+wrap, no duplicate `Evidence` name | Unchanged, v2 §4 |
| VerificationBasis compositional, VerificationAssurance scoped, confidence≠assurance | Unchanged, v2 §15 |
| Observation → Interpretation → Claim, vs. Observation → Evidence | Unchanged, v2 §12 |
| Security: layered (typed evidence + provenance metadata + content/instruction separation + safe rendering + tool isolation + verification), not "typing alone" | Unchanged, v2 §37 |
| Evidence provenance chain, exact binding, transformation safety | Unchanged, v2 §14; transformation rule (no inherited directness beyond justified) unchanged |
| Coverage: Task/Verification/Criterion/Evidence/Observation kept separate | Unchanged, v2 §13 |
| `OBSERVED_ABSENT` requires inspection + authorization + coverage | Unchanged, v2 §13 |
| Construct validity vs. verifier stability | Unchanged, v2 §9 |
| Rubric provenance | Unchanged, v2 §9 |
| Aggregation: criterion logic / evidence aggregation / verifier aggregation kept separate | Unchanged, v2 §19; **pairwise consistency added as a fourth, separate property** — not a fourth aggregation layer, a distinct check |
| Assumptions distinct from observed/derived fact | Unchanged, v2 §25 |
| Reference/GroundTruth/Oracle distinct | Unchanged, v2 §24 |
| Receipt model + supersession lineage | Unchanged, v2 §26 |
| Replay semantics keyed on capture, not internal/external origin | Unchanged, v2 §27 — this is the corrected version; still correct |
| Evidence / Verification / Decision validity, three-way split | Unchanged, v2 §23 |
| Task mutation → impact analysis → preserve/reuse/recheck/invalidate/supersede/cancel, over-invalidate not under-invalidate | Unchanged, v2 §6 |
| Cache fail-closed on unproven identity | Unchanged, v2 §5, §28 |
| Escalation lineage, immutable original, reason codes | Unchanged, v2 §40 |
| Governance boundary, one-directional | Unchanged, v2 §32 |
| C-MoE: interface-only, policy/requirements-based | Unchanged in spirit, v2 §33; **now expressed via Profile/Requirements per Part 1 §3**, which is a sharpening, not a reversal |
| Context boundary, canonical evidence protected from compression | Unchanged, v2 §29, §34 |
| Memory boundary | Unchanged, v2 §35 |
| Evaluation Lab boundary | Unchanged, v2 §36 |
| False-success triage ≠ VerificationResult, learned classifier is V1.x/V2 | Unchanged, v2 §39 |
| Confidence/uncertainty/abstention separate; abstention is a legitimate outcome | Unchanged, v2 §20; **now reinforced by the ambiguous-control scoring rule (Part 1 §8)** |
| V1/V2 boundary (causal visibility, cryptographic attestation, formal temporal logic, distributed mission verification, learned false-success, conformal verdicts all V2) | Unchanged, v2 §47 |

Nothing above required correction. This is a genuine finding, not an assumption: v2 held up.

---

## Part 3 — Adversarial audit (28 attacks)

Attacks 1–18 restate v2 Review C (v2 document, "Review C") under the same numbering as this round's prompt — results unchanged, not re-derived:

| # | Attack | Result |
|---|---|---|
| 1–18 | False completion, fabricated evidence, self-referential evidence, injection, stale evidence, cross-execution contamination, unproven-identity reuse, correlated verifiers, bad rubric, mid-run rubric change, incomplete observation claimed absent, verifier crash, task mutation reuse, receipt editing, authorization inference, policy-level override | Unchanged from v2 Review C — 15 BLOCKS, 2 DEGRADES SAFELY (fabricated evidence, correlated verifiers), all named as such, none upgraded |
| 19 | Pairwise cycle (A>B, B>C, C>A) treated as coherent | **BLOCKS** — new: `PairwiseConsistency` check (Part 1 §2) exists specifically for this |
| 20 | Swapping A/B changes the pairwise verdict | **DEGRADES SAFELY** — mitigated via bidirectional evaluation, not eliminated; order bias is measured, not architecturally impossible |
| 21 | Score-range change alters the verdict | **DEGRADES SAFELY** — same category as other presentation-sensitivity biases; monitored via meta-evaluation (Part 1, updated matrix), not hard-blocked |
| 22 | "I am uncertain" treated as evidence of poor quality | **BLOCKS** — new explicit invariant (Part 1 §8): abstention on an ambiguous/insufficient-evidence control scores as correct, not as failure |
| 23 | Language change silently changes reliability | **KNOWN LIMITATION** — multilingual metadata exists (v2 §43) but per-language calibration data may simply not exist yet; disclosed, not hidden |
| 24 | Compression destroys critical evidence | **BLOCKS** — v2 §29, reconfirmed unchanged |
| 25 | Historical receipt reinterpreted under verifier v2 semantics | **BLOCKS** — v2 §41, reconfirmed unchanged |
| 26 | External evidence replayed without a captured snapshot | **BLOCKS** — v2 §27 (the corrected version), reconfirmed unchanged |
| 27 | Assumption silently becomes evidence | **BLOCKS** — v2 §25, reconfirmed unchanged |
| 28 | Model-generated reference silently becomes ground truth | **BLOCKS** — v2 §24, reconfirmed unchanged |

No known limitation is presented as a guarantee. Four items (20, 21, 23, and the "DEGRADES SAFELY, unchanged" pair from 1–18) remain honestly probabilistic rather than solved — that's the correct state for bias mitigation, not a gap to close before freezing.

## Part 4 — Consistency audit (targeted at what actually changed)

v2's own consistency review (nine tested pairs) isn't re-derived — nothing in Part 1 touches those nine terms in a way that could have reopened them. Checked specifically for *new* potential contradictions introduced by this round's additions:

- `VerificationRequirements` (caller-supplied) vs. `VerificationPolicy` (system-supplied) vs. `VerificationStrategy` (internal): no overlap — one is input from the caller, one is input from the system, one is Verification's own decision logic that consumes both. No case where two of these could disagree about who owns the same field.
- `VerificationShape` (POINTWISE/PAIRWISE/SET_LEVEL) vs. `VerificationMethod` (v2 §11): orthogonal, confirmed — a PAIRWISE verification can still use a deterministic method (e.g. comparing two file hashes) or a model verifier; shape doesn't imply method.
- Pairwise consistency vs. the existing "aggregation must stay in three separate layers" rule (v2 §19): pairwise consistency is a **property checked before aggregation**, not a fourth aggregation layer — stated explicitly in Part 1 §2 to prevent exactly this ambiguity.

No contradictions found.

## Part 5 — Phase boundary audit

No production verifier, critic, evidence store, rubric engine, runtime worker, event handler, C-MoE, context compiler, memory system, or evaluation lab has been implemented. This document and its predecessors are architecture and documentation only — confirmed by the simple fact that every artifact produced this session has been a `.md` file.

## Final Architecture Quality Test

*Could a competent engineer implement Phase C contracts without inventing a new architectural decision about ownership, trust boundaries, evidence semantics, lifecycle, provenance, identity, assurance, mutation, requirements/policy/strategy, or pairwise verification semantics?*

**Yes.** Every category named in that question now has an explicit section, including the one added this round (requirements/policy/strategy/profile) and the one before that (pairwise). The remaining open items are correctly Phase D/C implementation judgment calls (exact aggregation algorithms, exact locking mechanism, exact serialization of a compositional `VerificationBasis`) — normal contract-design work, not missing architecture.

---

## Final Output

**A. Phase B Status: `ARCHITECTURE READY FOR PHASE C`** — and I'd treat this as the actual freeze. Two correction rounds in a row have each found real, non-overlapping substance (37 corrections including one bug and one overclaim, then 8 more including a genuinely useful new axis), which is exactly what you'd expect from healthy review converging — but the ratio in *this* round (8 new ideas against 50 reconfirmation sections) is the signal that the marginal architecture-level find rate is dropping. That's a good sign to build, not a reason to run a third correction pass looking for a ninth.

**B–N.** Covered inline: the pairwise correction (Part 1 §1–2), architecture summary and ownership matrix (unchanged from v2, see that document), V1/V2 boundary (unchanged, v2 §47, new items in Part 1 are all V1), execution identity/`DEBT-015` (unchanged, v2 §5), architecture risks (unchanged, v2 §48), ADR list (v2's list plus one new entry: `ADR: Verification shape and pairwise consistency`, and one new entry: `ADR: Requirements/Policy/Strategy/Profile separation`), structural/trust-boundary/adversarial/phase-boundary reviews (Parts 2–5 above), Phase C contract plan (v2 §49–50 plus Part 1's contract additions).
