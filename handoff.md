# Session Handoff

Workstream: OCBrain Verification / Critic / Evidence subsystem, branch `feature/verification-critic-evidence-phase-c`.
Language rule from the user: **always respond in English, never French** (the user wrote some early messages in French).

---

## 1. Handoff Metadata

- Handoff version: 1
- Created at: 2026-10-02 (session date)
- Workstream: Verification contract layer (`core/verification/`), audit of side work, repair, and contract Batches 2, 3A, 3B
- Task identifier: audit of side work `ead305d..` → repair → Batch 2 (Evidence) closeout → Batch 3A → Batch 3B
- Source session purpose: audit the side-work commits on the Verification branch, repair what the audit found, then implement the next approved contract batches in small, separately committed steps
- Transfer status: see section 19
- Governing contract: `PROJECT_INSTRUCTIONS.md` (repo root; copy at `docs/architecture/PROJECT_INSTRUCTIONS.md`). It was delivered in the same first message as the audit prompt and governs this workstream.

---

## 2. Original Starting Prompt

The first user message contained `PROJECT_INSTRUCTIONS.md` (see section 1) followed by the prompt below, verbatim. It announced that the side-work prompts would be supplied next; they were (see Appendix A for faithful extractions).

````text
Branch: `feature/verification-critic-evidence-phase-c`
The Verification branch has been updated by side work performed outside your current Verification task sequence.
I will provide you with the prompts used for that side work. Treat those prompts as the intended specification for the changes.
Your job now is not to continue implementing the next Verification batch. Your job is to audit the side work already present on this branch and determine whether it is correctly implemented, complete, regression-free, and free of subtle bugs.
Required approach

1. First inspect the actual current repository state:
   * current branch and HEAD;
   * recent commits;
   * files changed by the side work;
   * diff against the branch state before the side work;
   * existing Verification changes already present.
2. Read the side-work prompts I provide and derive their exact intended requirements.
3. Reconcile prompt → implementation → tests → actual behavior.
Do not assume the implementation is correct because:
   * the prompt says it should be;
   * the commit message says it is;
   * tests pass;
   * documentation claims completion.
4. Look specifically for:
   * missing requirements;
   * incorrect interpretations of the prompt;
   * semantic/concept conflation;
   * broken invariants;
   * edge cases;
   * backwards-compatibility regressions;
   * unsafe defaults;
   * hidden state;
   * incorrect error handling;
   * false-success paths;
   * weakened provenance/authority boundaries;
   * identity or lifecycle mistakes;
   * duplicated or conflicting abstractions;
   * tests that pass without actually proving the intended invariant.
5. Run the relevant focused tests, the Verification test suites, and an appropriate broader regression suite.
6. Add small adversarial tests locally when needed to prove a suspected weakness. Do not modify production code merely to make a test pass.
7. Check that the side work did not accidentally pull in later Verification phases, runtime integration, C-MoE, or unrelated architectural changes.

Evidence standard
For every finding, distinguish clearly between:

* Confirmed bug — reproduced or directly demonstrated.
* Missing requirement — explicitly required by the supplied prompt but absent.
* Potential weakness — plausible concern not yet demonstrated.
* No issue found — implementation matches the requirement and evidence supports it.

Do not invent bugs merely because something could theoretically be designed differently.
Important
The side-work prompts are the specification to audit, but they do not override the repository's frozen Verification architecture or existing authoritative contracts. Where a prompt conflicts with the frozen architecture, identify the conflict explicitly instead of silently accepting it.
Do not begin another feature batch until this audit is complete.
Final report
Return:
1. Side-work scope
What commits/files were actually introduced.
2. Requirement reconciliation
For each major requirement from the supplied prompts: `PASS / PARTIAL / FAIL`.
3. Bugs / gaps
For every issue, give:

* severity;
* exact file/location;
* why it is wrong;
* reproduction/evidence;
* required correction.

4. Regression results
Focused Verification tests, stdlib mirror, and broader suite results, including unrelated pre-existing failures.
5. Architecture check
Confirm whether the side work remains compatible with the frozen Verification architecture and did not pull future-phase scope forward.
6. Verdict
State only one of:

* CLEAN — safe to continue
* FIXES REQUIRED — do not continue yet

Do not modify or commit anything unless a confirmed defect must be fixed to complete the audit. If fixes are required, keep them strictly limited to the audited side work and report them separately.
````

---

## 3. Subsequent User Instructions / Corrections

Quoted wording is exact where wording matters; otherwise a faithful summary. Later items supersede earlier ones only where stated. Order note: S3 (the second repair prompt, containing "Do not push yet") actually arrived **after** S4 ("Push to repo"), which had already been executed; the rows are grouped by topic, not strictly by arrival time. Short "Continue" messages are omitted.

| # | Instruction | Effect |
|---|---|---|
| S1 | Supplied two side-work prompts: **Batch 1** (ClaimDependency, AssumptionSource, AssumptionStatus, ReferenceQuality) and **Batch 2** (MinimumSufficientEvidence, EvidenceReference, EvidenceObservation, EvidenceTransformation, EvidenceBundle). Treat as the spec to audit, subordinate to the frozen architecture. | Appendix A |
| S2 | Repair prompt: remove "only the strategy↔method consistency enforcement introduced by `c09f924`"; keep the duplicate-ID and `InspectionStep.plan_id` fixes; "do not silently change `VerificationStrategy.selected_methods` to IDs"; add a regression test where `method_id != method_type`; fix the new mypy error with a "local and semantic-neutral" change. Batch 2 evidence is "still WIP"; "Do not claim Batch 2 is complete"; "`EvidenceTransformation` must not claim to enforce authority/integrity/certainty/provenance-strength rules that its fields cannot actually observe"; "Do not invent an ordinal ordering for `EvidenceDirectness`"; do not invent the observation-coverage state contracts; "do not duplicate `CriterionEvidenceRequirement` inside `MinimumSufficientEvidence`". | Done (D-01..D-08) |
| S3 | Second repair prompt (A–D): same repair; "Do not add arbitrary new metadata vocabularies ... First determine whether an existing authoritative contract already defines them"; "Do not add authority semantics to `EvidenceObservation`"; "Do not create a global Evidence registry or new IDs solely for symmetry"; commit discipline: keep repair and Evidence WIP logically separate; "Do not push yet". | Done; the "do not push yet" arrived after S4 had already been executed |
| S4 | "Push to repo" | Pushed `d0e3eb0` |
| S5 | Disposition: G1 fixed, G9 fixed, G3 "correctly narrowed", G4 fixed, G5 "correctly deferred", G6/G7 "substantially repaired", **G8 deferred** ("not an architectural blocker"). Record state as: Batch 1 complete; CompiledSpecification hardening repaired and validated; Batch 2 Evidence partially implemented/WIP with deferred items explicitly recorded; G8 deferred hardening debt. Continue with Evidence "rather than reopen G8". "the GitHub credential that was pasted earlier must be revoked/rotated before any further authenticated push." | D-10, D-11 |
| S6 | Sequence: push `1d9bed9`, `624482e` → final audit of the full stack (confirm no `c09f924` regression, Batch 1 correct, Evidence matches the frozen architecture, no circular-evidence bypass, tests prove the invariants, no new broad-suite regression, docs match reality; "desired outcome is CLEAN / READY TO CONTINUE, not another redesign") → finish Batch 2's decided work → next contract batch. | Done |
| S7 | Push `e6fb2c9 → 61e00e1 → 3496ede`; "Do not merge anything into `main` yet." Reconcile the inventory before implementation ("the next batch should therefore be based on the reconciled inventory, not the current tracker counts"). Next cluster: **A — `VerificationConstruct` / `ConstructValidity`**, then 3B (`VerificationObservation` + coverage), then 3C (`CriterionResult` + process/outcome results). Precise wording for test claims: **"no new failures were introduced relative to the audited baseline"** (the 9 pre-existing failures were not individually re-investigated). | Done through 3B |
| S8 | **3A approved**, frozen shape `Rubric.construct: VerificationConstruct`; `VerificationConstruct.description` only (non-empty after normalization, no `construct_id`/category/domain/metric/unit); `ConstructValidity(rubric_fingerprint, status: ConstructValidityStatus)`; status closed enum `NOT_EVALUATED / SUPPORTED / CONTESTED / UNSUPPORTED`; "`ConstructValidity` must never participate in the identity or fingerprint of the `Rubric` it evaluates"; no stability/confidence/verdict/consistency/score fields, tests must show semantic separation; scope "strictly" construct + validity + Rubric integration + tests. **"also, always use english, never french."** | Done |
| S9 | 3A "technically complete" but "not merge-ready" until the `Rubric.construct` disposition is closed (Required vs Optional with an explicit statement of when `None` is valid). Then reconcile the tracker, then freeze 3B scope = `VerificationObservation` + five coverage types + absence states at the "observation/evidence-input contract layer", no stability/scoring/confidence/verdict generation/provenance-lineage/C-MoE. "Keep everything unpushed for now." "The immediate next task is not more coding." | Done (D-20) |
| S10 | **3B approved**: five independent coverage types, each `fraction: Optional[float]` in [0,1] + required `scope: str` (`None` = unknown); four absence states; `OBSERVED_ABSENT` requires `inspected=True` + authorized inspection for the relevant surface + producer-declared `coverage_sufficient=True`, no numeric threshold; test the invariant "in both directions"; **`VerificationObservation` deferred** (named but undefined in the frozen architecture); `VerificationAssurance.coverage` unchanged, no implied equivalence with `VerificationCoverage`. `Rubric.construct` closed as required; the surviving required-construct mutant is equivalent and the contract must not be weakened. Work stays local, separated into its own commits. | Done |
| S11 | "Push the Done work then create a handoff file so the remaining work can be completed in a new session." | This handoff; push executed (section 7) |

---

## 4. Goal, Scope & Success Criteria

### Goal
Bring the Verification contract layer (`core/verification/`) forward in small, audited, separately committed batches that stay compatible with the frozen Verification architecture (V1/V2/V3), without runtime integration.

### In scope (done in this session)
Audit of the side work → repair of `compile()` hardening and mypy regression → Batch 2 Evidence reconciliation and closeout for its decided scope → inventory reconciliation → Batch 3A (construct/validity) → Batch 3B (coverage + absence).

### Out of scope (explicit, still binding)
Runtime integration, `EvaluatorWorker`/`WorkflowRuntime` integration, C-MoE, `VerifiedState`, result provenance/lineage, policy precedence, new execution/attempt identity infrastructure, `VerificationObservation` (until defined), verifier stability, scoring/confidence/verdict generation, merging into `main`, pushing without an explicit user instruction.

### Success criteria for any further batch (as practiced)
1. Live-state proof first; reconcile against the frozen architecture; label every non-architectural choice `IMPLEMENTATION JUDGMENT`.
2. Tests in `tests/test_verification_contracts.py` **and** the stdlib mirror `tests/verification_run_tests_stdlib.py`, in sync (same count).
3. Mutation-checked: break each rule once and confirm a test fails.
4. mypy clean on `core/verification`; import-all clean.
5. Sequential broader suite: "no new failures relative to the audited baseline `ead305d`".
6. Code+tests in one logical commit; tracker/docs in a separate commit; patches exported; nothing pushed unless asked.

---

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Audit the side work, report PASS/PARTIAL/FAIL, bugs, regressions, architecture check, verdict | Original prompt | VERIFIED (delivered) | Audit report + later final audit | Verdict history: FIXES REQUIRED → repaired → READY TO CONTINUE |
| R2 | Remove strategy↔method check from `c09f924`, keep other fixes, add `method_id != method_type` regression | S2/S3 | VERIFIED | `1e1e9d9`; 3 regression tests fail on `c09f924`, pass after | |
| R3 | Fix new mypy error | S2/S3 | VERIFIED | `1e1e9d9`; touched files mypy-clean | Also typed the registry lookup (D-02) |
| R4 | Evidence contracts reconciled, no invented architecture | S2/S3/S5 | VERIFIED (decided scope) | `d0e3eb0`, `1d9bed9`, `e6fb2c9`, `61e00e1` | Batch 2 closed for decided scope; rows 18/20/49 still ◐ |
| R5 | No circular-evidence bypass | Batch 2 prompt #10, S6 | VERIFIED | `1d9bed9` (reference), `e6fb2c9` (lineage laundering) | Criterion-only bindings cannot apply the claim-scoped guard (documented) |
| R6 | Final stack audit CLEAN / READY | S6 | VERIFIED | Final audit; verdict READY TO CONTINUE after fix | |
| R7 | Inventory reconciled against code | S7 | VERIFIED | `86d8527`; table counts parsed | Depth of each contract's tests not re-audited row by row |
| R8 | Batch 3A scope exactly as approved | S8 | VERIFIED | `eb09480` | |
| R9 | `Rubric.construct` disposition closed | S9/S10 | VERIFIED | `cb5f55c`, `f2b7fda` | Required |
| R10 | Batch 3B scope exactly as approved | S10 | VERIFIED | `dfbeffb`, `6428f2e` | |
| R11 | `OBSERVED_ABSENT` gate tested both directions | S10 | VERIFIED | `TestObservationAbsence`; 28 mutants, 27 caught, 1 equivalent | |
| R12 | Keep work local until asked; separate commits | S9/S10 | VERIFIED | Pushed only on explicit instruction (S4, S6/S7, S11) | |
| R13 | English only | S8 | VERIFIED | | |
| R14 | Token must be rotated before further pushes | S5 | **OPEN** | The same token still worked on every push through S11 | Not recorded here; user action required |
| R15 | Next batches: 3C (`CriterionResult` + process/outcome results) | S7/S9 | OPEN | Scope not yet proposed or approved | |
| R16 | `VerificationObservation` | S10 | DEFERRED | Needs a definition from the user | |
| R17 | G8 hardening debt | S5 | DEFERRED | Tracker §9 | Not registered in `KNOWN_ISSUES.md` (see 15) |
| R18 | Do not merge into `main` | S7 | VERIFIED (not merged) | `origin/main` untouched | |

---

## 6. Current Verified State

**VERIFIED** (at code commit `dfbeffb`; `6428f2e` adds only a tracker document):
- `tests/test_verification_contracts.py`: **385 passed**; stdlib mirror: **385/385 OK**.
- mypy on all of `core/verification` (27 files): **no issues**. (It had 1 pre-existing error, `rubric.py:145`, removed by Batch 3A.)
- Import-all of `core.verification.*`: OK, no cycles.
- Broader suite, sequential: **1879 passed, 9 failed, 4 errors**; audited baseline `ead305d`: 1699 passed, 9 failed, 4 errors; the failing set is identical (13 entries, section 13): **no new failures relative to the audited baseline**. The 13 were not individually re-investigated.
- Mutation checks: Batch 2 evidence 31/31 caught; 3A 13/13 caught; required-construct 2/3 caught + 1 equivalent; 3B 27/28 caught + 1 equivalent.

**Tracker state** (`docs/architecture/verification-critic-evidence-system-phase-c-semantic-pipeline-reconciliation.md`, parsed): **38 ✅, 5 ◐, 14 ❌ of 57**.
- ◐ rows: 2 `VerificationTarget`, 33 `VerificationConfidence` (older partial/architecturally-satisfied); 18 `EvidenceReference`, 20 `EvidenceTransformation`, 49 `MinimumSufficientEvidence` (decided scope done, architecture-named parts deferred).
- ❌ rows: 1 `VerificationRequest`, 3 `VerificationContext`, 10 `CriterionResult`, 24 `VerificationObservation` (deferred: undefined), 30 `ProcessVerificationResult`/`OutcomeVerificationResult`, 35 `VerificationRun`, 36 `VerificationStep`, 38 `VerificationTrace`, 39 `DecisionTrace`, 41 `VerificationBudget`, 42 `EscalationRequest`, 43 `AdjudicationRecord`, 50 `BlindVerificationContext`, 51 `PolicyPrecedence`.

**IMPLEMENTED BUT NOT FULLY VERIFIED:** nothing outstanding.
**PROPOSED:** 3C scope (not yet drafted).
**DEFERRED:** see section 15 and tracker §9.
**UNKNOWN:** why each of the 13 shared failures fails (probably environment: `chromadb` and `sentence-transformers` are not installed in the sandbox).

Active architectural constraints: frozen V1/V2/V3 architecture; no ordinal ordering of `EvidenceDirectness`; `ConstructValidity` never part of a rubric's identity; absence is never inferred from silence; coverage quantities independent; nothing runtime.

---

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1` (public)
- Remote: `origin` = `https://github.com/1h0lde4/ocbrain-v4.1.git`
- Branch: `feature/verification-critic-evidence-phase-c`
- Base branch: `main`; merge-base with `main` = `5954e44`
- HEAD before handoff / **transfer commit**: `6428f2e2c20a9a50f70be8e3bb3b427e31e2a712` (docs: record Batch 3B in the Phase C tracker). Implementation state is complete at `dfbeffb37d52c55ac68a39e8b1843844389f421a`; `6428f2e` only updates the tracker.
- Handoff commit: the commit that adds this file (find it with `git log -1 -- handoff.md` on the branch); its parent is the transfer commit `6428f2e`. A file cannot contain its own commit hash.
- Working tree before handoff: clean.
- Remote push status: all 17 commits since `ead305d` were pushed on explicit user instruction; remote branch = `6428f2e` before the handoff commit.
- `main` (not touched): was `4ab5345` at handoff time. Branch vs main: 89 commits only in `main`, 46 only in the branch. A read-only `git merge-tree` dry run showed **one conflict, in `KNOWN_ISSUES.md`** (docs); `main` has not touched `core/verification`, the Verification tests, or the tracker since the merge-base. `main` keeps moving, so recompute before relying on this.
- Submodules / nested repos: none relevant.

Commits since the audited baseline `ead305d` (oldest first):

| SHA | Subject | Origin |
|---|---|---|
| `7dd602c` | Implement Verification epistemic spine completion | Side work (Batch 1) |
| `c09f924` | Harden CompiledVerificationSpecification (…strategy-method consistency…) | Side work, **no prompt supplied**; Fix 3 later reverted |
| `0ab0335` | WIP: Implement Phase 4 evidence contracts … Tests pending | Side work (Batch 2 WIP) |
| `1e1e9d9` | Revert strategy<->method check from c09f924; fix mypy regression | This session |
| `d0e3eb0` | wip: reconcile Phase 4 evidence contracts with the frozen architecture (NOT complete) | This session |
| `1d9bed9` | wip: apply check_not_circular in claim-bound EvidenceReference.verify_against | This session |
| `624482e` | docs: record post-audit Verification status and explicit Batch 2 deferrals | This session |
| `e6fb2c9` | wip: keep check_not_circular from being laundered through EvidenceTransformation | This session |
| `61e00e1` | docs: close Batch 2 Evidence for its decided scope; correct tracker count | This session |
| `3496ede` | docs: record known drift in the Phase C inventory table | This session |
| `86d8527` | docs: reconcile the Phase C inventory table against code and tests | This session |
| `eb09480` | Implement Batch 3A: VerificationConstruct and ConstructValidity | This session |
| `0d1cf6e` | docs: record Batch 3A in the Phase C tracker | This session |
| `cb5f55c` | Make Rubric.construct required (Batch 3A disposition) | This session |
| `f2b7fda` | docs: record the Rubric.construct decision and reconcile Batch 3A tracker state | This session |
| `dfbeffb` | Implement Batch 3B: five coverage types and observation-absence states | This session |
| `6428f2e` | docs: record Batch 3B in the Phase C tracker | This session |

Commit-message correction: `dfbeffb`'s message says "64 tests". The real number is **33 tests per file (385 − 352), 66 across the two files**. It is already pushed, so it was not amended. (3A's "30 tests" means 30 per file.)

---

## 8. Active Files / Modified Files / Artifacts

Production (`core/verification/`):
- `construct.py` (new, 3A): `VerificationConstruct`, `ConstructValidityStatus`, `ConstructValidity`.
- `coverage.py` (new, 3B): `TaskCoverage`, `VerificationCoverage`, `CriterionCoverage`, `EvidenceCoverage`, `ObservationCoverage`.
- `absence.py` (new, 3B): `ObservationAbsenceState`, `ObservationAbsence` (imports `InspectionAuthorization` from `epistemic.py`).
- `evidence.py` (reworked): `ProvenanceCompleteness`, `EvidenceBindingError`, `EvidenceReference`, `EvidenceObservation`, `TransformationType`, `EvidenceTransformation`, `EvidenceBundle`, `MinimumSufficientEvidence`; pre-existing `EvidenceSource`, `EvidenceItem`, `check_not_circular` untouched.
- `rubric.py`: `Rubric.construct: VerificationConstruct` (required, before `lock_state`, runtime type-checked).
- `compiled_specification.py`: net change vs baseline = duplicate-ID detection, `InspectionStep.plan_id` validation, docstring, one neutral `VerificationMethodId(...)` wrap at the registry lookup.
- `claim.py`, `assumption.py`, `reference.py`, `identity.py`: Batch 1 (`ClaimDependency`, `AssumptionSource`, `AssumptionStatus`, `ReferenceQuality`), **untouched since `7dd602c`**.
- `epistemic.py` (`VerificationAssurance`, `InspectionAuthorization`, `ObservationAuthority`): **untouched**; `VerificationAssurance.coverage: float` deliberately unchanged.
- `core/verification/__init__.py` is empty by convention: no re-exports.

Tests: `tests/test_verification_contracts.py` (pytest) and `tests/verification_run_tests_stdlib.py` (stdlib mirror). Both must stay in sync, same count.

Docs: `docs/architecture/verification-critic-evidence-system-phase-c-semantic-pipeline-reconciliation.md` (the tracker; §9 holds the status register, decision records, and deferral tables). Frozen architecture: `…-architecture-v1.md`, `…-v2-frozen.md`, `…-v3-final.md`.

Artifacts outside the repo: patch copies in `/mnt/user-data/outputs/verification-*` (copies only, not needed; the pushed branch is authoritative). `/tmp/audit/*` scratch scripts are gone with the sandbox; Appendix B reproduces the useful ones.

---

## 9. Changes Made

**Compile repair (`1e1e9d9`).** Removed only the strategy↔method consistency check (it compared `VerificationStrategy.selected_methods`, documented in `policy.py` as method names/types, with `InspectionStep.method_reference`, a registry key; valid specs failed whenever `method_id != method_type`). Renamed the shadowing loop variable; typed the registry lookup. Replaced 3 tests that encoded the wrong assumption with 3 `method_id != method_type` regression tests.

**Evidence (Batch 2), decided scope.**
- `EvidenceReference`: reuses `EvidenceSource`; no content field; claim and/or criterion binding required; blank source/locator rejected; `verify_against(item)` also applies `check_not_circular` for a claim-bound reference.
- `EvidenceObservation`: id-only binding + `ProvenanceCompleteness`; no authority of its own; `verify_against` rejects an `Interpretation`.
- `EvidenceTransformation`: lineage (`source_*`, type, version, producer, `result_*`) and categorical rules only (no ordering): no upgrade into `DIRECT`; `MODEL_INTERPRETATION` permanent (v1 §16); provenance never silently `COMPLETE`; `verify_against` ties the record to the real items and blocks laundering a restatement flag through lineage (`CircularEvidenceError`).
- `EvidenceBundle`: immutable tuple of `EvidenceItem`s (all six statuses preserved), unique ids, claim and/or criterion binding, `check_not_circular` for a bound claim.
- `MinimumSufficientEvidence`: declarative set of evidence ids needed to reconstruct a claim/criterion decision, `verify_against(bundle)` containment check; status-blind; not the count floor.

**3A.** `VerificationConstruct(description)`; `ConstructValidityStatus` values are namespaced `construct_*` (see D-17); `ConstructValidity(rubric_fingerprint, status)` rejects a non-`ConstructValidityStatus` status; `Rubric.construct` required.

**3B.** Five coverage types (distinct frozen types, no shared base, no container); `ObservationAbsenceState`; `ObservationAbsence` with the `OBSERVED_ABSENT` gate.

**Tracker.** Corrected the "Built" count (it overstated by one since `ead305d`), re-marked 16 stale ❌ rows as built, recorded decisions and deferral tables in §9.

---

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| D-01 | Revert `c09f924` strategy↔method check; keep duplicate-ID and `plan_id` fixes | IMPLEMENTED | User (S2) | `1e1e9d9` + tests | Only if the representation of `selected_methods` (names vs ids) is formally decided |
| D-02 | Type the registry lookup `VerificationMethodId(step.method_reference)` (runtime no-op) | IMPLEMENTED | Needed for the "mypy clean on touched files" criterion; matches the existing `compile()` signature | `1e1e9d9` | If `method_reference` representation changes |
| D-03 | `EvidenceTransformation` enforces only categorical rules over its own fields; adds `source_provenance`/`result_provenance` | IMPLEMENTED | S2/S3 + v1 §16 | `d0e3eb0` | A per-type table for `DIRECT → DIRECT` is added by the architecture |
| D-04 | `DIRECT → DIRECT` via a non-model transformation is **accepted** and left to evidence construction/assessment | IMPLEMENTED (boundary, tested) | Frozen text only says "never silently upgraded to DIRECT" and "MODEL_INTERPRETATION permanent" | Audit G3 was partly retracted | User asks for a per-type table (new architecture decision) |
| D-05 | Restatement flag is inherited through lineage (`verify_against`) | IMPLEMENTED | Batch 2 prompt #10 | `e6fb2c9`, reproduced bypass | — |
| D-06 | No new evidence metadata vocabularies (scope, validity window, relevance, specificity, integrity, correlation group, independence level, sensitivity); `VerificationAssurance.assurance_scope`/`independence_level`/`integrity_verified` are assurance-level and not aliased | DEFERRED | S3 + investigation | No authoritative definition exists | Consuming layer defines them; user decides placement (extend `EvidenceItem` vs companion) |
| D-07 | Observation-absence states belong to the coverage layer, not Batch 2 | DELIVERED in 3B | S2 | `dfbeffb` | — |
| D-08 | Batch 2 closed for its decided scope; rows 19, 21 ✅; 18, 20, 49 stay ◐ | ACCEPTED | S5/S6 | `61e00e1` | Deferred parts defined |
| D-09 | `MinimumSufficientEvidence` layout is IMPLEMENTATION JUDGMENT (architecture gives only the purpose); privacy/cost dimensions not represented | ACCEPTED | S2 | tracker row 49 | Sensitivity metadata exists |
| D-10 | G8 (Batch 1 test weakness, no runtime enum enforcement, `ClaimDependency` without consumer) = deferred hardening debt | DEFERRED | User (S5) | Tracker §9 | A hardening pass is scheduled |
| D-11 | Do not register G8 in `KNOWN_ISSUES.md` yet | DEFERRED | Avoid `DEBT-` id collisions with ids added on `main` | `main` has added DEBT ids | At merge/rebase time |
| D-12 | Inventory reconciliation is status-only (class in code + test references) | IMPLEMENTED | S7 | `86d8527` | Depth audit requested |
| D-13 | `VerificationConstruct` = `description` only, no identity, `str.strip()` emptiness | IMPLEMENTED | User (S8) | `eb09480` | Construct becomes independently addressable |
| D-14 | `ConstructValidity` refers to a rubric by fingerprint **value** only | IMPLEMENTED | User (S8) | `eb09480` | — |
| D-15 | `ConstructValidity.status` must be a `ConstructValidityStatus`; verdicts are rejected, not coerced | IMPLEMENTED | S8 invariant 4 | `eb09480` | — |
| D-16 | Behavioural "stability ↔ validity independence" tests deferred: no verifier-stability contract exists | DEFERRED | Investigation | Tracker §9 | A stability contract is built |
| D-17 | `ConstructValidityStatus` string values are namespaced `construct_*`; member names as approved | IMPLEMENTED | User accepted (S9) | `str`-Enum equality collision with `VerificationVerdict.UNSUPPORTED = "unsupported"` was reproduced | — |
| D-18 | `Rubric.construct` is **required**, no construct-less state (DRAFT included); placed before `lock_state` | IMPLEMENTED | User delegated the choice (S9); closed (S10) | `cb5f55c`; scratch experiment: required broke 50 tests, DRAFT-only-optional 38; no production callers | User explicitly reverses |
| D-19 | Locking a rubric does not require any `ConstructValidity` status | ACCEPTED | S9 | Decision record in tracker §9 | A policy decision is made |
| D-20 | Five coverage types: distinct frozen types, no shared base, no container; `fraction: Optional[float]`, no default; required `scope` | IMPLEMENTED | User (S10) | `dfbeffb` | — |
| D-21 | `OBSERVED_ABSENT` gate (inspected + same-surface authorized `InspectionAuthorization` + declared `coverage_sufficient`), strict `is True`; other states ungated; no defaults for `state`/`inspected`/`coverage_sufficient` | IMPLEMENTED | User (S10) | `dfbeffb` | A sufficiency definition is added |
| D-22 | `ObservationAbsenceState`/`ObservationAbsence` names are IMPLEMENTATION JUDGMENT (v1 §21 vs v2 §13 use "Observation Coverage" for two things) | ACCEPTED | S10 | | — |
| D-23 | `VerificationObservation` deferred | DEFERRED | User (S10) | Only a name in the v1 contract list | The user supplies a definition |
| D-24 | Process: separate code and docs commits; export patches; do not push unless asked; never merge into `main` | ACCEPTED | User | | — |

---

## 11. Investigation Already Performed

| Area | Inspected | Result | Revisit trigger |
|---|---|---|---|
| Side-work commits `7dd602c`, `c09f924`, `0ab0335` | Full diffs, prompts reconciled | Findings G1–G9 (audit); G1/G9 fixed, G3 narrowed, G4/G6/G7 repaired, G5 deferred, G8 deferred | Remote branch moves |
| `compile()` before/after | Differential test on baseline and HEAD over valid/invalid scenarios | Only intended behaviour changes (duplicate ids, unknown `plan_id`) | `compiled_specification.py` changes |
| Frozen architecture text | v1 §15/§16/§21, v2 §9/§13/§14/§16/§24/§25/§44, v3 | Evidence chain, provenance vocabulary, absence rule, MSE purpose are defined; metadata vocabularies, `VerificationObservation` fields, "sufficient" are **not** | Architecture changes |
| Existing contracts for metadata vocabularies | Whole `core/` grep for scope/specificity/integrity/sensitivity/validity/correlation/independence/relevance | No evidence-level definition; only assurance-level free fields | New contract appears |
| Production callers of `Rubric(...)` | `grep` across `core/` | None outside tests (so required `construct` is test-only breakage) | Callers appear |
| `str`-Enum value collisions | All 33 enums in `core/verification` | `UNSUPPORTED` collided (fixed by namespacing); the four absence values collide with nothing | New enums |
| Tracker inventory | Parsed all 57 rows vs classes in code | 16 stale ❌ rows re-marked | Rows change |
| `main` divergence | `git merge-tree` dry run (read-only) | One docs conflict: `KNOWN_ISSUES.md` | `main` moves |
| Broader suite | Sequential runs at several heads vs baseline | Same 13 failing entries every time | Dependencies installed |

Not investigated: the root cause of each of the 13 shared failures; depth of every contract's tests for the 16 re-marked rows; the three `main` ADRs (`ADR_CTX_01_…`, `ADR_INDEX`, `ADR_KERNEL_06_VERIFIABLE_HYPOTHESIS_PROVENANCE`), one of which may bear on Verification provenance.

---

## 12. Failed Attempts / Dead Ends

| Approach | Result | Retry? |
|---|---|---|
| `c09f924` strategy↔method consistency | Rejected valid specs; reverted | No |
| Audit finding G3 stated as "DIRECT→DIRECT through any transformation is a bug" | Over-claimed vs the frozen text; partly retracted (D-04) | No |
| `Rubric.construct` as `Optional[...] = None` (3A first implementation) | Deviation from the approved shape; replaced by required (D-18) | No |
| `ConstructValidityStatus` with natural string values | `==` and dict-key collision with `VerificationVerdict.UNSUPPORTED`; fixed (D-17) | No |
| Running two full test suites in parallel | Produced one flaky sandbox test failure (`test_cancel_kills_all_descendant_processes`); passes alone and sequentially | Run suites sequentially |
| `mypy core/verification` without flags | Fails: the checkout directory name is not a valid package name | Use the command in section 14 |
| `grep -n` over the tracker with `cut -c` | Invalid UTF-8 output (emoji split) | Read the tracker with Python `encoding="utf-8"` |
| Converter-based mirror generation with multi-line `assert` | Unsupported | Keep each `assert` on one line in new tests |
| Stdlib mirror calling `_assurance(...)` | Name does not exist at module level in the mirror | Build the object inline (see `_c3_result`) |
| Mutation runner with non-unique replacement patterns | Silent no-op risk | Assert `count(old) == 1` before replacing |

---

## 13. Verification Evidence

Commands (run from the repo root; see section 14 for flags):
- `python3 -m pytest tests/test_verification_contracts.py -q -p no:cacheprovider -o addopts=""` → **385 passed** (history: 205 baseline → 260 → 315 → 318 → 321 → 351 → 352 → 385).
- `python3 tests/verification_run_tests_stdlib.py` → **Ran 385 tests … OK**.
- `MYPYPATH=. python3 -m mypy --explicit-package-bases --namespace-packages --ignore-missing-imports --follow-imports=silent core/verification/*.py` → **Success: no issues found in 27 source files**.
- Import-all loop over `pkgutil.iter_modules(core.verification.__path__)` → OK.
- `python3 -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors -o addopts=""` at `dfbeffb` code state → **9 failed, 1879 passed, 1 warning, 4 errors** (baseline `ead305d`: 9 failed, 1699 passed, 4 errors).
- Patch series applied cleanly on the previous remote head each time and passed.

The 13 failing/erroring entries, identical at the baseline `ead305d` and at HEAD (known, **not** Verification failures; probably environmental, not individually re-investigated):

```text
ERROR tests/test_break_concurrency.py
ERROR tests/test_break_empty_db.py
ERROR tests/test_break_security.py
ERROR tests/test_system_ctrl.py
FAILED tests/core/cognitive/test_intent_security.py::TestCtxAuth001ParserAcceptance::test_injection_shaped_completion_line_is_not_accepted_as_a_hypothesis
FAILED tests/test_audit_fixes.py::TestA7SystemController::test_accepts_normal_targets
FAILED tests/test_audit_fixes.py::TestA7SystemController::test_open_app_uses_safe_platform_apis
FAILED tests/test_audit_fixes.py::TestA7SystemController::test_open_app_with_injection_raises
FAILED tests/test_audit_fixes.py::TestA7SystemController::test_rejects_empty_target
FAILED tests/test_audit_fixes.py::TestA7SystemController::test_rejects_flag_like_target
FAILED tests/test_audit_fixes.py::TestA7SystemController::test_rejects_shell_metacharacters
FAILED tests/test_module_factory_security.py::test_desc_field_cannot_break_out_of_generated_source
FAILED tests/test_module_factory_security.py::test_name_field_also_uses_safe_literal_substitution
```

Limitations: the broader suite was not re-run after the docs-only commit `6428f2e` (it changes only the tracker); the mutation checks cover the rules listed in section 6, not every line.

---

## 14. Environment / Tooling Assumptions

- Python 3.12.3 in the sandbox (repo declares `requires-python >= 3.11`). Installed for the suite: pytest 9.1.1, pytest-asyncio 1.4.0, pytest-mock 3.16.0, mypy 2.3.1, datasketch, fastapi, httpx, aiohttp, pydantic, scipy, rich, PyYAML, trafilatura, and the other lightweight requirements. **Not installed:** `chromadb`, `sentence-transformers` (likely cause of several shared failures). The pytest warning "Unknown config option: asyncio_mode" is expected.
- A full-suite run **rewrites tracked files** (`data/context.sqlite`, `config/models.toml`, `config/settings.toml`). After every run: `git checkout -- data config` and confirm `git status --short` is empty. Never commit them.
- `git` commits in the sandbox used `-c user.name="Claude" -c user.email="noreply@anthropic.com"`.
- The repository is public: `git clone` and `git fetch` need no credentials. Pushing needs a credential; **the user's GitHub token was pasted into their claude.ai preferences and into the chat, so it must be treated as exposed. It still worked for pushes at the end of this session. It is not recorded here. Do not push unless the user explicitly asks, and remind them to revoke and rotate it.** Pass any credential as a one-off `http.extraheader`, never stored in git config, and push only the feature branch, fast-forward, never force.
- Network in the sandbox was limited to GitHub/npm/pypi style hosts.

---

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Options | Disposition | May work continue? |
|---|---|---|---|---|
| Token exposure (R14) | Same token worked at the last push | User revokes and rotates | OPEN, user action | Yes, but no pushes without explicit instruction |
| 3C scope not drafted | S7/S9 name `CriterionResult` + process/outcome results | Read the architecture text for rows 10 and 30, draft a bounded scope, get approval | OPEN | This is the next step |
| `VerificationObservation` undefined | Only a name in the v1 contract list | User defines it, or it stays deferred | DEFERRED | Yes |
| v1 §15 evidence metadata placement | No authoritative vocabulary | Extend `EvidenceItem` or add a companion, after the consuming layer exists | DEFERRED | Yes |
| `DIRECT → DIRECT` per-type table | Architecture silent | Add only on a user decision | DEFERRED | Yes |
| Definition of "sufficient" coverage | Architecture silent | Keep producer-declared boolean | DEFERRED | Yes |
| `VerificationAssurance.coverage` ↔ `VerificationCoverage` relation | Architecture silent | Leave unlinked | DEFERRED | Yes |
| G8 hardening debt | Tracker §9 | Dedicated hardening pass | DEFERRED | Yes |
| Merging with `main` | 89 behind, 46 ahead, one docs conflict in `KNOWN_ISSUES.md` | Decide merge path, register debts with non-colliding ids, re-run suites | NOT AUTHORIZED | Yes |
| The 13 shared failures | Not investigated | Install missing deps and re-run, or investigate individually | OPEN, optional | Yes |
| Three ADRs added on `main` | Not read | Read before 3C/provenance-related work | OPEN | Yes |
| Invisible format characters count as non-blank | Same `str.strip()` rule everywhere in the package | Package-wide decision | Known limitation | Yes |

---

## 16. Relevant Information / References

- Governing contract: `PROJECT_INSTRUCTIONS.md` (sections 0, 14.4, 16.3–16.5, 18.4.8–18.4.12, 24).
- Frozen architecture: `docs/architecture/verification-critic-evidence-system-architecture-v1.md`, `…-v2-frozen.md`, `…-v3-final.md`. Key text: v1 §15/§16 (evidence chain and metadata), v1 §21 and v2 §13 (absence states, five coverage fields), v2 §9 (construct validity), v2 §14 (provenance completeness, transformation safety), v2 §16 (per-surface authorization), v2 §24/§25 (Reference/Oracle, Assumption), v2 §44 (minimum sufficient evidence).
- Design proposals and earlier phases: `…-compiledverificationspecification-design-proposal.md`, `…-finding-critique-design-proposal.md`, `…-verificationmethod-design-proposal.md`, `…-phase-0-reality-audit.md`, `…-phase-1-contract-reconciliation.md`.
- Tracker: `…-phase-c-semantic-pipeline-reconciliation.md`, in particular §9 (status register, decision records for `Rubric.construct`, 3A and 3B deferral tables).
- Conventions to keep: frozen dataclasses; identity wrappers are `NewType("...", str)` in `identity.py`, added only for independently addressable objects; no re-exports in `__init__.py`; label non-architectural choices `IMPLEMENTATION JUDGMENT`; never claim more than the evidence shows; a `str`-Enum member compares equal to any other `str`-Enum member with the same value, so check for value collisions when adding enums.
- Repository cautions: `check_not_circular` has no callers outside the new evidence contracts' `verify_against` methods and tests (pre-existing).

---

## 17. Next Steps

1. **Resume and verify** (section 18). Do not change code until the state matches this handoff.
2. **Batch 3C scope (rows 10 and 30: `CriterionResult`, `ProcessVerificationResult`/`OutcomeVerificationResult`).** Where: read the frozen architecture text for these (grep the three architecture docs and the tracker rows), plus existing `VerificationResult`/`VerificationVerdict` in `verdict.py` and `Criterion*` in `rubric.py`. Why: it is the next step the user ordered. Prerequisite: the user's approval of a bounded scope before any code; expect `VerificationObservation`-style gaps where the architecture only names a type. Verification: a short scope proposal listing what is architecture, what is judgment, what is deferred, and one question for the user.
3. **Implement 3C** with the standard discipline (section 4): live-state proof, contract matrix, tests in both files, mutation check, mypy, import-all, sequential broader suite vs baseline, code commit then docs commit, tracker row updates, patches, no push.
4. **Later clusters** (each needs an approved scope): rows 1 and 3 (`VerificationRequest`, `VerificationContext`), 50 and 51 (`BlindVerificationContext`, `PolicyPrecedence`), 35/36/38/39 (Run/Step/Trace/DecisionTrace), 41 (`VerificationBudget`), 42/43 (`EscalationRequest`, `AdjudicationRecord`), 24 (`VerificationObservation`, after a definition).
5. **Before any merge:** user revokes/rotates the token; decide the merge path with `main`; register G8 and any other debts in `KNOWN_ISSUES.md` with non-colliding `DEBT-` ids; re-run the Verification suites and the broader suite after merging `main`; keep the code/docs commit separation.
6. **Optional hardening (G8)** once the user schedules it: replace string-blacklist tests in Batch 1 with field-level rejection tests, add runtime enum checks for `Assumption.status` / `Reference.quality` (as 3A does for `ConstructValidity.status`), decide a consumer for `ClaimDependency`.

---

## 18. Resume Instructions

First actions in a fresh session:
1. Read `PROJECT_INSTRUCTIONS.md`, then this file completely. Answer in English.
2. `git fetch origin`; confirm branch `feature/verification-critic-evidence-phase-c` contains `6428f2e` (`git merge-base --is-ancestor 6428f2e origin/feature/verification-critic-evidence-phase-c`) and that `git log -1 -- handoff.md` is the handoff commit whose parent is `6428f2e`.
3. Check out the branch; `git status --short` must be empty.
4. Re-run section 13's pytest, stdlib mirror and mypy commands; expect 385 / 385 / clean. If anything differs, resolve it before touching code and correct this handoff.
5. Do not re-run investigations listed in section 11 unless a revisit trigger fired.
6. Begin at Next Step 2 (3C scope proposal). Wait for the user's approval before implementing.

Do not: push, merge into `main`, rewrite published history, or use the exposed token without the user's explicit instruction.

---

## 19. Transfer Status

**TRANSFER READY**, conditional on the post-push verification below. Conditions satisfied at the time of writing: original prompt and later instructions preserved; requirement, decision and investigation ledgers present; verified state recorded with exact commands; implementation checkpoint `6428f2e` committed and pushed (remote verified); no material uncommitted work; next action defined.

Remaining step for the session that creates this file: commit it, push the branch, and verify that `origin/feature/verification-critic-evidence-phase-c` contains the handoff commit. If that verification fails, the status must be downgraded to the appropriate `TRANSFER INCOMPLETE — …` value.

Non-repository state: none required for continuation. Scratch tooling is reproduced in Appendix B; the 13-entry baseline failing set is in section 13; the token is deliberately not stored anywhere.

---

## Appendix A — Side-work prompts (faithful extraction, not verbatim)

The two side-work prompts were each several hundred lines. Their operative requirements, exclusions and acceptance criteria are preserved here; they were audited, and the frozen architecture overrides them where they conflict.

**Batch 1 — Epistemic Spine** (repository `1h0lde4/ocbrain-v4.1`, branch HEAD when prepared `ead305dbcff4e2d62da53c9fa30f04ca250ecead`, 205/205 contract tests then):
- Implement exactly `ClaimDependency`, `AssumptionSource`, `AssumptionStatus`, `ReferenceQuality`, with the minimum integration to make each real (no orphan types). Do not redesign the architecture.
- `ClaimDependency`: immutable edge "which claim depends on which"; not truth/support/authority; reconcile with `ClaimOrigin.DERIVED`, `derived_from`, `caused_by` without a competing lineage system; reject direct self-dependency; no whole-graph cycle detection, no traversal, no identity wrapper unless independently addressable.
- `AssumptionSource`: structured (not one opaque string), says where an assumption came from, never implies authority; kept distinct from `ObservationAuthority`, `InspectionAuthorization`, `VerificationAssurance`; integrated with `Assumption` without breaking `description`/`relied_upon_for`.
- `AssumptionStatus`: its own axis; vocabulary source-reconciled and labelled IMPLEMENTATION JUDGMENT if unspecified; no ordinal trust scale; unknown ≠ rejected, unknown ≠ confirmed, challenged ≠ verified failure; not `VerificationVerdict`; no implicit conversions; no lifecycle engine; must survive serialization; historical receipts must not be rewritten.
- `ReferenceQuality`: preserves `ReferenceKind`/`content_summary`/`source`; quality ≠ correctness ≠ authority ≠ freshness ≠ GroundTruth; no "highest quality wins"; no ordinal score unless required; integrated with `Reference`.
- Attacks A–G that must remain impossible: dependency→proof, provenance→authority, verdict→assumption status, quality→GroundTruth, quality→correctness, provenance laundering, unknown-state collapse.
- Identity via `NewType(..., str)` only where needed; all contracts `@dataclass(frozen=True)`; no generic base classes; no later-batch concepts.
- Tests in both test files (stdlib mirror in sync) covering each concept plus adversarial and integration tests; docs updated without claiming the subsystem complete; one logical commit "Implement Verification epistemic spine completion"; then STOP (no Batch 2).

**Batch 2 — Evidence contracts** (`MinimumSufficientEvidence`, `EvidenceReference`, `EvidenceObservation`, `EvidenceTransformation`, `EvidenceBundle`): preserve the chain `Claim → Evidence → Source → exact Locator → Observation` with criterion binding; reuse `EvidenceDirectness`/`EvidenceStatus`; preserve the architecture's evidence metadata where applicable (locator, source identity, scope, producer, `observed_at`, `retrieved_at`, validity window, directness, relevance, specificity, integrity, provenance, correlation group, independence level, sensitivity); provenance completeness `COMPLETE/PARTIAL/UNKNOWN/BROKEN`, never silently complete; `Observation → Interpretation → Claim` vs `Observation → Evidence`; exact source+locator binding, no vague citations; `EvidenceObservation` reuses `ObservationAuthority`; transformation lineage and no silent strengthening (directness, authority, provenance, integrity, certainty), **no ordinal on `EvidenceDirectness`**; keep `check_not_circular`; preserve the six evidence states and the four absence states; immutable bundle preserving contradictory evidence, membership implies nothing; `MinimumSufficientEvidence` is a declarative requirement distinct from `EvidenceStatus.SUFFICIENT`; no raw payloads; no new identities for symmetry; no registry; no execution identity; GraphRAG `Evidence` unchanged. Tests (pytest + mirror) for all of the above plus adversarial cases. Out of scope: execution, assessment/aggregation, the five coverage types, `CriterionResult`, `VerificationObservation`, Run/Step/Trace, runtime, C-MoE, `VerifiedState`, result lineage, policy precedence, registry, execution identity. One logical commit; report changed files, pytest, mirror, unrelated failures, hash, and confirmation that no later-phase work was included.

What the audit established about these prompts is in sections 3, 10 and 11 (notably: Batch 2 prompt item 12 assumed an absence-state type that did not exist; the Batch 1 §4 "no orphaned types" vs §5.4 "no traversal" tension for `ClaimDependency`).

---

## Appendix B — Reusable tooling (these scripts lived in `/tmp`, outside the repo)

**Pytest → stdlib-mirror converter** (used to generate the mirror for new test classes; asserts must be single-line; `with pytest.raises(X):` must be on one line):

```python
import re
def convert(src: str) -> str:
    out = []
    for line in src.split("\n"):
        m = re.match(r"^(\s*)assert (.*)$", line)
        w = re.match(r"^(\s*)with pytest\.raises\((.*)\):$", line)
        cls = re.match(r"^class (Test\w+):$", line)
        if cls: out.append(f"class {cls.group(1)}(unittest.TestCase):")
        elif w: out.append(f"{w.group(1)}with self.assertRaises({w.group(2)}):")
        elif m:
            ind, e = m.group(1), m.group(2)
            if e.rstrip().endswith(("(", ",")): raise SystemExit("multi-line assert: " + line)
            if e.startswith("not "): out.append(f"{ind}self.assertFalse({e[4:]})")
            elif e.endswith(" is not None"): out.append(f"{ind}self.assertIsNotNone({e[:-12]})")
            elif e.endswith(" is None"): out.append(f"{ind}self.assertIsNone({e[:-8]})")
            elif " == " in e:
                if e.count(" == ") != 1 or " != " in e: raise SystemExit("ambiguous ==: " + line)
                a, b = e.split(" == ", 1); out.append(f"{ind}self.assertEqual({a}, {b})")
            elif " != " in e:
                a, b = e.split(" != ", 1); out.append(f"{ind}self.assertNotEqual({a}, {b})")
            elif " is " in e: a, b = e.split(" is ", 1); out.append(f"{ind}self.assertIs({a}, {b})")
            elif " not in " in e: a, b = e.split(" not in ", 1); out.append(f"{ind}self.assertNotIn({a}, {b})")
            elif " in " in e and " for " not in e: a, b = e.split(" in ", 1); out.append(f"{ind}self.assertIn({a}, {b})")
            else: out.append(f"{ind}self.assertTrue({e})")
        else: out.append(line)
    return "\n".join(out)
```

Insert the converted block before `if __name__ == "__main__":` in the mirror, and add any new imports to both files' import blocks.

**Mutation runner** (break one rule at a time; every mutant must make the suite fail, or be justified as equivalent):

```python
import subprocess
def run(path, good, muts):           # muts: [(name, old, new)]
    for name, old, new in muts:
        assert good.count(old) == 1, name          # unique pattern, else the mutant is a silent no-op
        open(path, "w").write(good.replace(old, new, 1))
        r = subprocess.run(["python3", "-m", "pytest", "tests/test_verification_contracts.py",
                            "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-x"], capture_output=True, text=True)
        print(("CAUGHT   " if r.returncode else "SURVIVED ") + name)
    open(path, "w").write(good)                     # always restore, then `cmp` against a saved copy
```

**Baseline comparison for the broader suite:**

```bash
git worktree add --detach /tmp/wt_base ead305d
(cd /tmp/wt_base && python3 -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors -o addopts="" > /tmp/base.log 2>&1)
python3 -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors -o addopts="" > /tmp/head.log 2>&1
for f in base head; do grep -E "^(FAILED|ERROR)" /tmp/$f.log | sed 's/ - .*//' | sort > /tmp/${f}_fail.txt; done
comm -13 /tmp/base_fail.txt /tmp/head_fail.txt   # new failures (must be empty)
git worktree remove --force /tmp/wt_base; git checkout -- data config   # restore files rewritten by the suite
```

**Live-state check for the tracker counts:**

```python
import re; from collections import Counter
rows = [re.split(r"\s*\|\s*", l) for l in open(F, encoding="utf-8") if re.match(r"^\| \d+ \|", l)]
print(Counter(r[3] for r in rows))        # expect {'✅': 38, '◐': 5, '❌': 14}
```
