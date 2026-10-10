# Session Handoff (version 3, 2026-10-09)

> Versions 1 and 2 of this file are retained verbatim below the marker "ARCHIVED: earlier handoff content". Where they disagree with this version, this version and the live repository win; the earlier text is a transfer record, not an authority (`PROJECT_INSTRUCTIONS.md` §18.4.9).

## 1. Handoff Metadata

- Handoff version: 3
- Created at: 2026-10-09
- Workstream: Verification / Critic / Evidence System: state reconciliation after the 3C-A closure and the 3C-B design block
- Task identifier: reconciliation of the complete master prompt against the live repository
- Source session purpose: began as the independent review of Batch 3C-A (read-only), then source reconciliation for 3C-B, then this repository reconciliation
- Transfer status: **TRANSFER INCOMPLETE — LOCAL COMMIT ONLY** (see §19)

## 2. Original Starting Prompt

The prompt that started this workstream phase, verbatim:

``````text
The incomplete prompt I uploaded previously is **NOT** the final complete master prompt.

The complete version you need to use is **the one I have uploaded with this message**. Treat that document as the authoritative complete master prompt for this task.

The previous 695-line document is an earlier/truncated version of the specification. It ends partway through the semantic pipeline and must **not** be used as the basis for completing or extending the work.

### Required sequence

**1. First, read the complete uploaded master prompt in full.**

Do not start implementing anything yet.

**2. Then perform a full repository reconciliation against the work already done.**

Reconcile the complete master prompt against:

* the current repository state;
* the current `main`;
* the existing Verification branch and its commits;
* the contracts/tests already implemented;
* all relevant parallel branches that are expected to merge into `main`;
* current Runtime / WorkflowRuntime / Event Backbone state;
* EvaluatorWorker and other adjacent workers;
* Evaluation Lab work;
* current `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, roadmap, and relevant ADRs.

Do not assume that previous reports, branch descriptions, test counts, or handoffs are still accurate. **Prove the actual state first, then reconcile it.**

### 3. Do not silently overwrite existing work.

Identify precisely:

* what from the complete master prompt is already implemented;
* what is partially implemented;
* what is scaffolded;
* what is missing;
* what has changed since the earlier handoff;
* what conflicts with other parallel branches;
* what must be preserved for the eventual merge into `main`.

Where two branches contain overlapping work, determine ownership and compatibility before changing either.

### 4. Do not start a new implementation architecture.

The complete master prompt is the specification to reconcile against the repository.

Do not redesign the Verification system merely because the current repository differs from the prompt.

If a genuine contradiction exists, document it explicitly and classify it as:

`IMPLEMENTATION GAP / REPOSITORY CHANGE / ARCHITECTURAL CONFLICT / DEPENDENCY / DEFERRED WORK`

Do not patch around architectural contradictions silently.

### 5. After reconciliation, update the repository state documentation.

Update the appropriate:

* `CURRENT_STATE.md`
* `KNOWN_ISSUES.md`
* roadmap/status documents
* Verification-specific documentation/ADRs

so that they describe the **actual verified state**, not the old reported state.

Do not merely update a progress number. Record the actual implemented/partial/missing state of the Verification subsystem.

### 6. Preserve branch topology.

Do not merge unrelated branches simply to reconcile the work.

The existing Verification implementation branch should remain the primary working branch unless the live repository proves that another topology is required.

Branches that will eventually merge into `main` must be treated as future integration constraints.

### 7. Produce a complete reconciliation report.

The report must show:

* current repository baseline;
* branch topology;
* Verification branch state;
* contracts already implemented;
* tests already implemented;
* semantic pipeline status;
* Runtime/WorkflowRuntime integration status;
* Evaluation Lab overlap;
* parallel-branch dependencies/conflicts;
* exact remaining implementation work;
* exact deferred work;
* any architecture/document discrepancies.

### 8. Create a fresh-session handoff after reconciliation.

Once the reconciliation is complete and the repository/documentation state has been updated, create a **self-contained handoff document for a new Claude session**.

That handoff must include:

* verified repository baseline;
* current branch/HEAD;
* branch topology and future merge considerations;
* exact Verification implementation state;
* completed contracts;
* completed tests;
* current semantic pipeline position;
* remaining batches;
* dependencies;
* allowed scope;
* out-of-scope items;
* acceptance criteria;
* known risks;
* unresolved blockers;
* exact next task.

The new session must be able to resume from the handoff without relying on this conversation.

### Critical rule

**Do not begin the next implementation batch until the complete master prompt has been read, the repository has been reconciled against it, the state documentation has been corrected, and the fresh-session handoff has been created.**

This reconciliation is itself an important Verification milestone. Accuracy of repository state takes precedence over speed.
``````

(The earlier independent-review brief for Batch 3C-A, which began the session, was a separate task. It was read-only, frozen at `fe338ed`, and told the reviewer to use no credentials. Its outcome is recorded in §3 and §6.)

## 3. Subsequent User Instructions / Corrections

1. 3C-A: **ACCEPTED / GATE SATISFIED (qualified)**; F1–F7 comparison UNVERIFIED because the implementer's review report and mutation harness were unavailable to the independent reviewer. Move to 3C-B, carrying M2, M3 and M6 as follow-ups. The 16-of-165 accepted combinations are a property of the implementation, not derivable from S13 alone; keep that explicit.
2. 3C-B rulings D1–D5 (ratified 2026-10-05) and D6–D10 (ratified after the master-prompt reconciliation); full text in `docs/architecture/verification-critic-evidence-system-phase-c-semantic-pipeline-reconciliation.md` §10.
3. Open design items ODI-3C-B-01/02/03 and the unresolved questions must not be silently resolved. No code, placeholder enum or speculative contract until they are closed.
4. M9 is informational and non-blocking.
5. Process: the authoritative tracking record is repo-resident, so the implementer session incorporates the ratification and pushes it; the independent review session stays read-only.
6. Do not reconstruct unavailable mission sections from secondary mentions.
7. This task (§2): the uploaded file is the authoritative complete master prompt; reconcile first; correct the state docs; produce a report and a self-contained handoff; do not start the next implementation batch before all of that is done.
8. No credential is to be used for the review or the reconciliation. A GitHub token sits in the user preferences in plaintext; it was not used. The user was advised to remove and rotate it.

## 4. Goal, Scope & Success Criteria

### Goal
Reconcile the repository's real Verification state against the master prompt, correct the state documentation, and hand off cleanly.

### In scope
Read-only audit; correction of `CURRENT_STATE.md`, `KNOWN_ISSUES.md` and the Phase C tracker; a reconciliation report; this handoff.

### Out of scope
Any implementation batch, 3C-B design resolution, `EvaluatorWorker` or `WorkflowRuntime` changes, merging branches, the F1/F2 wording and divergence-figure docs items (authorized earlier but separate), pushing without authorization.

### Success criteria
State docs match the verified state; the report lists baseline, topology, contracts, tests, pipeline, Runtime status, Lab overlap, conflicts, remaining and deferred work, and discrepancies; a new session can resume from this file alone.

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Read the complete master prompt in full | prompt §2 step 1 | VERIFIED | 4,317-line file inspected; it is the §0–§117 master prompt, not the truncated continuation | the §100–§112 sections were extracted for the matrix |
| R2 | Reconcile against repo, main, branch, contracts/tests, parallel branches, Runtime, workers, Lab, state docs | step 2 | VERIFIED | report §1–§9 | broader suite not re-run |
| R3 | Do not silently overwrite existing work | step 3 | VERIFIED | no source file changed; old handoff retained verbatim | |
| R4 | No new architecture; classify contradictions | step 4 | VERIFIED | report §9 | |
| R5 | Update CURRENT_STATE, KNOWN_ISSUES, roadmap/status docs, Verification docs | step 5 | IMPLEMENTED (local commit, not pushed) | commit `7607bdd` | `IMPLEMENTATION_ROADMAP.md` has no Verification entry and was left unchanged |
| R6 | Preserve branch topology | step 6 | VERIFIED | no merge, rebase or branch change | |
| R7 | Complete reconciliation report | step 7 | IMPLEMENTED (local commit, not pushed) | `docs/reports/verification-state-reconciliation-2026-10-09.md`, commit `12d0383` | |
| R8 | Fresh-session handoff | step 8 | IMPLEMENTED (local commit, not pushed) | this file | |
| R9 | Do not begin the next implementation batch | critical rule | VERIFIED | no code touched | |
| R10 | Record the M4 correction | earlier hold on M4 | **NEEDS CONFIRMATION** | the corrected crash wording is in `CURRENT_STATE.md` | previously held for separate authorization; the user's step 5 arguably covers it; drop the hunk if not |

## 6. Current Verified State

**VERIFIED**
- `origin/main` `27d918d` (2026-10-09); Verification branch tip `fe338ed`; 137 only-in-main / 52 only-in-branch; merge-base `5954e44`; `main` changed 85 files since, none in Verification paths.
- `core/verification/`: 26 modules, 104 classes/enums, contracts only; no importer outside the package, its tests and documentation.
- Tests on `fe338ed` (run 2026-10-09): pytest 424 passed; stdlib mirror 424 OK; `mypy` clean on 28 files.
- §100 domain model (46 names): 23 implemented, 4 under another name, 6 partial, 13 not implemented (report §4).
- Pipeline: complete through `CriterionResult`; aggregation and decision layers absent (report §5).
- `EvaluatorWorker` on `main` still uses the caller-supplied `goal_completed` fallback; no `INSUFFICIENT_EVIDENCE`.
- `WorkflowRuntime`: DAG, node-boundary checkpointing and `resume()` implemented and tested; no persistent node cache, replay engine, partial execution or external hooks.
- `DEBT-015` and `DEBT-007` open. No `verification.*` events on `main`.

**IMPLEMENTED BUT NOT VERIFIED:** the documentation corrections (local commit only; not reviewed by anyone else).
**PROPOSED:** none. **DEFERRED:** V2/high-assurance, `VerifiedState`, C-MoE, Lab, Context, Memory integration.
**BLOCKED:** Batch 3C-B (design-blocked, ODIs open).
**UNKNOWN:** broader-suite results at `fe338ed`; status of the archived DEBT-020 completion-gate branch; the Phase 0–14 master implementation prompt; the Parallel Implementation Mission past §13.

## 7. Git / Repository Checkpoint

- Primary repository: `https://github.com/1h0lde4/ocbrain-v4.1` (public)
- Branch: `feature/verification-critic-evidence-phase-c`; reviewed tip `fe338ed`
- Base branch: `main` at `27d918d`
- Work done in a **separate local clone** (sandbox, ephemeral) on local branch `recon/verification-state-2026-10-09`, created from `fe338ed`; it is not on the remote.
- Transfer commits (sandbox-clone hashes; applying the patches elsewhere assigns new hashes): state docs `7607bdd`, report `12d0383`. The patch series has three files, in that order, the third being the handoff commit.
- Handoff commit: the commit that adds this file (the next commit on that branch; run `git log -1 -- handoff.md`). A file cannot contain its own hash.
- Parent of the handoff commit: `12d0383` (in the sandbox clone)
- Working tree status: the review checkout is clean at `fe338ed`; the work clone is clean after its commits.
- Relevant untracked/ignored files: none in the work clone.
- Submodules: none.
- Remote push status: **NOT PUSHED** (no push authorization; no credential used)
- Remote verification status: not applicable

## 8. Active Files / Modified Files / Artifacts

Modified: `CURRENT_STATE.md` (line 155), `KNOWN_ISSUES.md` (DEBT-018 row), `docs/architecture/verification-critic-evidence-system-phase-c-semantic-pipeline-reconciliation.md` (section 10 appended), `handoff.md` (this version prepended).
Added: `docs/reports/verification-state-reconciliation-2026-10-09.md`.
Deleted: none.
Non-repository artifacts needed for recovery: the three `git format-patch` files supplied with this handoff (the commits exist only in the sandbox clone). They apply to `fe338ed` with `git am`.
Review documents (outside the repo): `3C-A-independent-review.md`, `3C-B-D5-mission-reconciliation.md`, `3C-B-D5-mission-recovery-record.md`, `3C-B-source-reconciliation-study-2.md`, `3C-B-Decision-Rulings-D6-D10-draft.md`, `implementer-handoff-note-3C-A-closure-and-3C-B-record.md`.

## 9. Changes Made

Documentation only. `CURRENT_STATE.md` and `KNOWN_ISSUES.md` now give the verified state (tests, commit history by batch, what exists, what is absent, crash semantics as enforced, adjacent-system findings, source-integrity note). The tracker gains section 10 (3C-A closure, D1–D10, ODIs, M9, branch position). The report and this handoff are new. No behavior, schema, contract, governance, security or test change.

## 10. Decisions & Rationale

- 3C-A accepted (qualified). The crash rule stays (Option A), an IMPLEMENTATION JUDGMENT inside the master prompt's allowed outcomes (§104-J, §93), stricter than §93.
- D1–D10 as in tracker §10. Reopen only on a verified contradiction, changed dependency, governance/security concern, higher authority, or explicit user request.
- This reconciliation did **not** make the F1/F2 wording changes or touch `IMPLEMENTATION_ROADMAP.md` (no Verification entry) .

## 11. Investigation Already Performed

Inspected: all remote branches (64; path scan against Verification-relevant paths); `main` since the merge-base; the Lab branch's oracle files and ADR_LAB_06; `core/workflow/runtime.py` and `definition.py` on `main`; `core/workers/evaluator.py` on `main`; `KNOWN_ISSUES.md`/`CURRENT_STATE.md` on `main` and the branch; the whole `core/verification/` package by import-time inspection; the uploaded master prompt (headings, §100, §102, §110–§112, mechanical phrase search). Do not repeat these unless the repository has moved. Not inspected in depth: the archived DEBT-020 branch; Runtime behavior beyond a static read.

## 12. Failed Attempts / Dead Ends

- Searching git history and all refs for the mission text: not found (never committed). Do not retry.
- Using fuzzy name matching for the §100 table gave false positives; the table in the report is hand-mapped and checked against real classes.
- My first cleanup deleted 17 tracked `.pyc` files in the review checkout; they were restored with `git restore`. Avoid `find ... -delete` on `__pycache__` in this repo.
- Early documentation drafts carried wrong dates (Oct 7) and a stale `main` tip; corrected before commit. Use `date -u` and re-fetch before dating anything.

## 13. Verification Evidence

All run 2026-10-09 unless noted.
- `cd <checkout> && git checkout --detach fe338ed && python -m pytest tests/test_verification_contracts.py -q -p no:cacheprovider` → 424 passed.
- `python tests/verification_run_tests_stdlib.py` → 424 tests, OK.
- `python -m mypy --explicit-package-bases core/verification` → no issues in 28 source files.
- `git rev-list --left-right --count origin/main...origin/feature/verification-critic-evidence-phase-c` → 137 / 52.
- `git diff --name-only $(git merge-base ...) origin/main` → 85 files, 0 in Verification paths.
- `git grep` for importers of `core.verification` outside the package, tests and docs → none.
- The broader suite was **not** run. Do not quote the implementer's earlier figures (9 failed, 1918 passed, 4 errors) as verified.

## 14. Environment / Tooling Assumptions

Python 3.12.3, pytest 9.1.1, mypy (latest at install), in a venv outside the repo. `mypy core/verification` needs `--explicit-package-bases`. Never put `sleep 50` in a command line (an old test uses a global `pgrep`). Run suites one at a time. Clone without credentials. No secret is recorded here.

## 15. Unresolved Questions / Risks / Blockers

- ODI-3C-B-01/02/03; no-conclusion representation; `CoverageResult` vocabulary; evidence-reference fields and derivation for `failure_control` (3C-B; design-blocked; do not guess).
- M9: code "mission §N" citations unverified; the Phase 0–14 master implementation prompt and the Parallel Implementation Mission past §13 are not available. Work may continue without them.
- The M4 hunk in `CURRENT_STATE.md` needs the user's confirmation (R10).
- `main` keeps moving; one known `KNOWN_ISSUES.md` merge conflict; `CURRENT_STATE.md` auto-merges but was edited on both sides.
- Unmerged DEBT-020 completion-gate branch overlaps the EvaluatorWorker; examine before touching it.
- Risk: every figure in the state docs (divergence, tip) drifts; always re-measure.

## 16. Relevant Information / References

`PROJECT_INSTRUCTIONS.md` (§16.4, §16.5, §18.4.9); `docs/architecture/verification-critic-evidence-system-architecture-v3-final.md` (v1/v2 incorporated by reference); the Phase C tracker (§9 audit register, §10 this reconciliation); `docs/reports/verification-state-reconciliation-2026-10-09.md`; ADR_LAB_06 on `eval-lab/research-and-architecture`; the master prompt (`Pasted_markdown_10_.md`, §100 domain model and §110–§112 acceptance criteria).

## 17. Next Steps

1. Obtain the user's explicit authorization to push, then push the documentation commits to the Verification branch (or apply the patches there with `git am`). Why: the state docs are only local now. Verify: `git ls-remote` shows the new tip, and `git diff fe338ed..<tip> --stat` lists exactly the 5 files above.
2. Ask the user whether the M4 hunk stays (R10).
3. Separate docs-only items, only if authorized: F1 wording (tracker rule 3 and the `ValueError` text at `criterion_result.py:199-201`), F2 wording (`rubric_fingerprint` docstring, `criterion_result.py:132-135`), refreshed divergence figures.
4. Resolve the 3C-B decision surface from source (ODI-01/02/03 and the three questions). No code until closed.
5. Only then plan the next batch; candidates that do not obviously depend on 3C-B should be checked against ODI-3C-B-02 (lifecycle ownership) first.

## 18. Resume Instructions

1. Verify the branch: `git fetch origin` then `git rev-parse origin/feature/verification-critic-evidence-phase-c` (expect `fe338ed` unless step 1 above was done).
2. Check whether the reconciliation commits are on the remote; if not, apply the supplied patches to a branch from `fe338ed` (`git am`), do not rebuild them by hand.
3. Re-run the baseline commands in §13 and compare. Re-measure divergence with `main`.
4. Resolve any mismatch before changing anything. Do not trust this handoff over the repository.
5. Begin at §17 step 1.

## 19. Transfer Status

**TRANSFER INCOMPLETE — LOCAL COMMIT ONLY.** The reconciliation work exists as local commits in a sandbox clone and as patch files; nothing is pushed. Not marked TRANSFER READY.

---

# ARCHIVED: earlier handoff content (versions 1–2), retained verbatim

# Session Handoff

Workstream: OCBrain Verification / Critic / Evidence subsystem, branch `feature/verification-critic-evidence-phase-c`.
Language rule from the user: **always respond in English, never French** (the user wrote some early messages in French).

---

## 1. Handoff Metadata

- Handoff version: 2 (updated 2026-10-03). Version-1 content is preserved; additions are in sections titled "Update 2", and the few in-place corrections are marked `[corrected 2026-10-03]`.
- Created at: 2026-10-02 (session date)
- Updated at: 2026-10-03 (Step 0 re-verification, 3C scope study, Batch 3C-A implementation, review groundwork)
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
| S12 | **Resume prompt (2026-10-03).** Resume on the same branch; "Respond in English only." Authority order: `PROJECT_INSTRUCTIONS.md` (§18.4.9), this handoff ("a transfer record, not an authority"), v3-final ("frozen architecture; v2-frozen is history only"). **Step 0, no code changes:** fetch; confirm transfer commit `6428f2e`, that `ef79856` is its child, local HEAD = remote, `main` at `4ab5345`; check the tree; re-run the 385 tests, mypy, the stdlib mirror; explain "13" vs "9" and classify each failure per §16.4; use "no new failures relative to the audited baseline" "only if the comparison actually supports it"; "If the repo contradicts the handoff, correct the handoff, report the mismatch and stop". **Standing constraints:** D-01..D-24; "Do not invent ordinal orderings or vocabularies. Check for an existing authoritative contract first. Label every gap-filling choice IMPLEMENTATION JUDGMENT"; out of scope: runtime integration, C-MoE, verifier stability, scoring/confidence, provenance/lineage, policy precedence, execution-identity infrastructure, G8, unrelated fixes. "Do NOT push, merge main, rewrite history or force-push. The main divergence (89 behind / 46 ahead, KNOWN_ISSUES.md conflict) is a separate decision for me." The pasted GitHub token "is treated as compromised and is not stored anywhere"; if a push is later authorized: fetch first, credentials by environment variable or one-off URL, never persisted in `.git/config`. "Do not rewrite" `dfbeffb`'s "64 tests" message (true count 66). Appendix A is a faithful extraction, not verbatim. **Task: "BATCH 3C SCOPE PROPOSAL ONLY (CriterionResult + process and outcome results)"** — "No code and no commits", nine-step packet through the compliance matrix, then stop for approval; content: study with [FACT]/[ARCH]/[AUDIT]/[INFER]/[REC] tags, existing-code audit, proposed frozen shape and what each type must NOT contain, explicit deferrals, test plan, open questions. | Step 0 and the proposal were delivered; see Update 2 in sections 6, 11, 13 |
| S13 | **Disposition of the 3C proposal.** "I would **not approve the whole proposed 3C implementation as written**"; split it. **3C-A (`CriterionResult`) — approve after a few corrections:** (1) "Do not allow 'attempted but no verdict'": `NOT_ATTEMPTED → no verdict`, `BLOCKED → no verdict`, `ATTEMPTED → must have a VerificationVerdict`; an attempt that cannot be established uses an existing fail-closed verdict (e.g. `INSUFFICIENT_EVIDENCE`, `UNVERIFIABLE`). (2) "Do not invent 'SKIPPED'." (3) "`CriterionResult` must remain a per-criterion result, not a mini aggregation engine" (no AND/OR, majority, weighted averages, worst-of); "It stores the result produced by a later layer." (4) `rubric_fingerprint` is defensible but must be labeled `IMPLEMENTATION JUDGMENT`. (5) "Do not require `finding_ids` unless source evidence supports it." Added invariant: "`CriterionResult` must be composable into future coverage/aggregation/VerifiedState views, but must not perform or own those aggregations itself." **3C-B (process/outcome) — "do not implement yet":** v1 §20 uses `FAILED`, which is not in `VerificationVerdict`, and it "cannot be silently 'fixed' by mapping" to `CONTRADICTED` or `UNSUPPORTED` ("not necessarily equivalent semantics"); `failure_control` ownership "is not sufficiently established" (the source calls it an "orthogonal verification finding"). Correct conclusion about v3: "V3 does not independently specify the 3C result contracts. V1/V2 contain the relevant semantics. The exact implementation shape remains unresolved." Keep out of 3C: `VerifiedState`, `CoverageResult`, continuous checkpoint verification, C-MoE integration (and `VerificationRun/Step/Trace`, `DecisionTrace`, aggregation, events, escalation). | Batch 3C-A implemented (Update 2); 3C-B blocked |
| S14 | **Disposition of the 3C-A checkpoint.** `NOT_APPLICABLE` under `ATTEMPTED`: "accept, provisionally and explicitly"; do not add another axis. Tracker row 10's rejection of reusing `VerificationResult` is "well-founded"; the `MethodExecutionState` correction "should stay"; the `INCONCLUSIVE` collision stays "a separate pre-existing finding". Before calling 3C-A closed: an independent adversarial review that "challenge[s] these invariants rather than merely reread the implementation" — state machine (attempt_state × verdict × execution_failure), `NOT_APPLICABLE`, failure semantics ("the one I would scrutinize most": "If it is an implementation judgment, it should remain labeled as such rather than silently becoming constitutional behavior"), findings, fingerprint ("genuinely part of criterion-result identity, or only useful provenance metadata?"), aggregation boundary, mirror parity ("behavior rather than merely test count"), documentation. "I would update handoff.md now" with the four outstanding corrections. 3C-B: "Keep it completely untouched"; next is "a source-reconciliation batch, not an implementation batch" resolving only what `FAILED` means in the frozen architecture, who owns `failure_control`, and what authority v1 §20 has — "No placeholder enum, no speculative owner, no guessed authority model." Sequence: "3C-A → independent adversarial review → resolve/document review findings → close 3C-A → source-reconciliation study for 3C-B → only then design 3C-B." "I would not change the 3C-A code merely to 'perfect' it further unless the independent review finds a concrete architectural contradiction." | Treated as binding (the user phrases dispositions as "I would …"). Handoff updated (this file); a docstring-only label change was made under the failure-semantics instruction (D-29, D-34) |
| S15 | "You are authorised to push to repo" (2026-10-03). | The work branch `feature/verification-critic-evidence-phase-c` was pushed after `git fetch`: fast-forward `ef79856..d40f000`, no force, `main` not touched. The credential was supplied as a one-off `http.extraHeader` for that command only and was not persisted (checked: nothing in `.git/config`). Remote verified with `git ls-remote`. A status-only follow-up commit records this and is pushed the same way. The authorization is **not standing** |

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
| R14 | Token must be rotated before further pushes | S5 | **OPEN** | The same token still worked on every push through S11 and again for the 2026-10-03 push (S15; taken from the user's claude.ai preferences, passed as a one-off header, not stored here) | User action required: revoke and rotate it, and remove it from the preferences |
| R15 | Next batches: 3C (`CriterionResult` + process/outcome results) | S7/S9 | IN PROGRESS | [corrected 2026-10-03] Scope proposed (S12), split by S13 into R19 (3C-A) and R20 (3C-B) | |
| R16 | `VerificationObservation` | S10 | DEFERRED | Needs a definition from the user | |
| R17 | G8 hardening debt | S5 | DEFERRED | Tracker §9 | Not registered in `KNOWN_ISSUES.md` (see 15) |
| R18 | Do not merge into `main` | S7 | VERIFIED (not merged) | `origin/main` untouched | |
| R19 | Batch 3C-A: `CriterionResult` exactly as approved (S13) | S13 | IMPLEMENTED (self-verified only; independent review pending) | Commits `4c93878`, `99f3acd`, `a0b9da5` (pushed 2026-10-03); section 13 Update 2 | Not closed (R27) |
| R20 | Batch 3C-B: no code, no placeholder types | S13/S14 | BLOCKED (no code exists) | Tracker §9; `grep` finds no `ProcessVerificationResult`/`OutcomeVerificationResult`/`FailureControl` in code | Needs the source-reconciliation study (R29) |
| R21 | ATTEMPTED requires a verdict; NOT_ATTEMPTED/BLOCKED carry none; no SKIPPED | S13 | IMPLEMENTED (self-verified) | Oracle over 165 combinations, 0 mismatches; mutants M01–M04, M19 caught | |
| R22 | `CriterionResult` computes nothing and is composable by later layers | S13 | IMPLEMENTED (self-verified) | No public callables/properties (tested); imports only `identity` and `verdict` (tested); mutants M20, M22, M27 caught; throwaway higher-level view composed results | |
| R23 | `rubric_fingerprint` labeled IMPLEMENTATION JUDGMENT | S13 | VERIFIED | Module docstring, tracker §9 rule 9 | Identity-vs-provenance question is in R27 |
| R24 | `finding_ids` not required | S13 | IMPLEMENTED (self-verified) | Tests pin empty allowed for every state and verdict; mutants M23/M24 caught | |
| R25 | `NOT_APPLICABLE` under `ATTEMPTED` | S14 | ACCEPTED PROVISIONALLY | Tracker §9 rule 8 | Reviewer to confirm against v1 §25 |
| R26 | Crash rule (`execution_failure` ⇒ ATTEMPTED + UNVERIFIABLE) labeled as judgment, not constitutional | S14 | LABELED; DECISION OPEN | `a0b9da5` (docstrings, tracker); AST identical without docstrings | Options in tracker §9 (keep and label / weaken / drop the field) |
| R27 | Independent adversarial review of 3C-A across the eight areas before closure | S14 | OPEN | Tracker §9 "Closure conditions" | Cannot be done by the implementer; evidence gathered so far is preparation only |
| R28 | Update `handoff.md` with the four corrections | S14 | IMPLEMENTED (this update) | Section 11, 13, 14 Update 2 and in-place corrections | |
| R29 | Source-reconciliation study for 3C-B: meaning of `FAILED`, owner of `failure_control`, authority of v1 §20 | S14 | OPEN (next after R27) | Tracker §9 | No code; no placeholder enum, owner or authority model |
| R30 | Do not push, merge `main`, rewrite history or force-push | S12 (push authorized later by S15) | VERIFIED | Until S15 nothing was pushed (remote `ef79856`). After S15 only the work branch was pushed: fast-forward, no force; `main` untouched by this session; no history rewritten | The `main` divergence remains the user's separate decision (now 91 / 51, one `KNOWN_ISSUES.md` conflict) |

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
**PROPOSED:** [corrected 2026-10-03] 3C scope was proposed and split: 3C-A implemented locally, 3C-B BLOCKED (Update 2 below).
**DEFERRED:** see section 15 and tracker §9.
**UNKNOWN:** [corrected 2026-10-03 — RESOLVED, see Update 2 below and section 13] why each of the 13 shared failures fails. Originally: probably environment (`chromadb` and `sentence-transformers` not installed).

Active architectural constraints: frozen V1/V2/V3 architecture; no ordinal ordering of `EvidenceDirectness`; `ConstructValidity` never part of a rubric's identity; absence is never inferred from silence; coverage quantities independent; nothing runtime.

### Update 2 (2026-10-03) — state at local HEAD (code commit `4c93878`; `99f3acd` and `a0b9da5` change only documentation and docstrings)

**VERIFIED:**
- Contract tests: **424 passed**; stdlib mirror: **424 OK** (39 new tests in each, matching per-class counts 5/21/10/3). mypy on `core/verification`: no issues in **28** files. Import-all: 27 modules OK.
- Broader suite, sequential: **9 failed, 1918 passed, 4 errors** (1879 + 39 new passes); the failing set is identical to the pre-change HEAD. "No new failures relative to the audited baseline `ead305d`" is supported: the failing sets match, apart from one transient failure in one baseline run (section 13).
- **"13" versus "9" is one reference point, not 4 new failures:** the 13 entries are **9 `FAILED` + 4 collection `ERROR`s**; the earlier "9" counted only the `FAILED` ones.
- **Causes of the 13 (established from the tracebacks):** 12 are environmental in this sandbox — `ModuleNotFoundError: chromadb` (the 4 collection errors, 6 `TestA7SystemController` tests and 2 `test_module_factory_security` tests). 1 is a known, registered product defect — the CTX-AUTH-001 test documents itself as "currently expected to fail", and `KNOWN_ISSUES.md` records CTX-AUTH-001 as partially resolved. None touches `core/verification`. `chromadb` was **not** installed, so that those 12 pass once it is available is **unverified**.
- Tracker (parsed): **39 ✅, 5 ◐, 13 ❌ of 57** (row 10 re-marked ✅; row 30 stays ❌ and is blocked).
- Mutation checks on `criterion_result.py`: 30 mutants, 29 caught, 1 equivalent (proved equivalent over the full 165-point input domain).

**IMPLEMENTED BUT NOT INDEPENDENTLY VERIFIED:** Batch 3C-A (`core/verification/criterion_result.py`: `CriterionAttemptState`, `CriterionResult`). All evidence so far was produced by the implementer.
**BLOCKED:** Batch 3C-B (`ProcessVerificationResult`, `OutcomeVerificationResult`, `FailureControl`) pending architecture reconciliation. No code exists for it.
**OPEN DECISION:** whether the crash rule (`execution_failure` ⇒ ATTEMPTED + UNVERIFIABLE) stays as labeled, is weakened, or the field is dropped (section 15).
**UNKNOWN:** whether the 12 `chromadb`-dependent tests pass in an environment that has it.

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

### Update 2 (2026-10-03) — checkpoint, pushed and verified

- At resume the remote branch was `ef79856` (verified by `git fetch`) and `main` was `4ab5345`; divergence from `main` at `ef79856` was 89 behind / 47 ahead (89/46 at `6428f2e`; the extra commit is the handoff commit itself, so the "46" in the version-1 text refers to the transfer commit).
- **`main` moved on its own, not by this session:** `4ab5345` → `69df55f`, two docs commits (PR #47, "register DEBT-039 and update DEBT-021"); only `KNOWN_ISSUES.md` changed (3 lines); no Verification path was touched. Branch vs `main` is now **91 only in `main`, 51 only in the branch**. A read-only `git merge-tree --write-tree` dry run of `origin/main` with the pushed branch reports **one conflict, in `KNOWN_ISSUES.md`** (docs), as before.
- New commits on top of `ef79856`, **pushed 2026-10-03** (oldest first):

| SHA (at time of writing) | Subject | Notes |
|---|---|---|
| `4c93878` | Implement Batch 3C-A: CriterionResult and CriterionAttemptState | Code + 39 tests in each test file |
| `99f3acd` | docs: record Batch 3C-A in the Phase C tracker; block 3C-B | Tracker only |
| `a0b9da5` | docs: label the crash rule as implementation judgment; add 3C-A closure conditions | Docstrings in `criterion_result.py` + tracker; the AST is identical with docstrings stripped |
| `d40f000` | docs: update the handoff for Batch 3C-A (handoff version 2) | The handoff commit for Update 2; **verified on the remote** |
| (follow-up) | docs: record the push of Batch 3C-A in the handoff | Status-only; find it with `git log -1 -- handoff.md` |

- Patches: the series is exported with `git format-patch ef79856..HEAD` into `/mnt/user-data/outputs/` (outside the repository; regenerate it from the branch if the sandbox is gone). A series applies cleanly onto `ef79856` with `git am`; the tree is identical to the local branch.
- Remote push status: **pushed** on the user's explicit authorization (S15): `ef79856..d40f000`, fast-forward, no force. Remote verification: `git ls-remote origin refs/heads/feature/verification-critic-evidence-phase-c` returned `d40f000`, equal to local HEAD, and `git merge-base --is-ancestor d40f000 origin/feature/verification-critic-evidence-phase-c` is true. The status-only follow-up commit is pushed the same way.
- Working tree: clean at every commit. After every full-suite run the four rewritten tracked files were restored (`git checkout -- data config`).
- Risk (resolved 2026-10-03): the work was local-only until the push above; the patches are no longer needed for transfer.

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

### Update 2 (2026-10-03) — files

- **Added:** `core/verification/criterion_result.py` — `CriterionAttemptState` (NOT_ATTEMPTED / BLOCKED / ATTEMPTED; values `criterion_not_attempted` / `criterion_blocked` / `criterion_attempted`) and `CriterionResult` (`criterion_id`, `rubric_fingerprint`, `attempt_state`, `verdict`, `execution_failure`, `finding_ids`). Imports only `.identity` and `.verdict`. Its docstrings label which rules are architectural and which are IMPLEMENTATION JUDGMENT.
- **Modified:** `tests/test_verification_contracts.py` and `tests/verification_run_tests_stdlib.py` (+294 lines each): new imports (`ast`, `importlib`, `inspect`, `pkgutil`, `Enum`, `core.verification as _cv_pkg`, `criterion_result as _cr_module`, `CriterionAttemptState`, `CriterionResult`), helpers `_cr`, `_cr_other_str_enum_values`, and classes `TestCriterionAttemptState` (5), `TestCriterionResult` (21), `TestCriterionResultBoundaries` (10), `TestCriterionResultAndRubricIdentity` (3).
- **Modified:** the Phase C tracker (rows 10 and 30, count footer, a dated §4 correction, a dated correction to the "exact rule" claim near line 102, and the §9 records: 3C-A, the decision record, the rule-provenance table, the closure conditions, the deferral table, and the 3C-B block).
- **Unchanged on purpose:** `verdict.py`, `receipt.py`, `rubric.py`, `coverage.py`, `absence.py`, `finding.py`, `method.py` and every other existing contract (asserted for `VerificationResult`, `VerificationAssurance`, `VerificationReceipt`).
- **Not updated (precedent from 3A/3B):** `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, `PROJECT_INDEX.md`. The pre-existing `INCONCLUSIVE` collision is recorded only in the tracker.

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

### Update 2 (2026-10-03) — changes made

- **Behavior / interface:** a new, independent result contract. `ATTEMPTED` requires a `VerificationVerdict`; `NOT_ATTEMPTED` and `BLOCKED` carry none; `verdict` has no default; `execution_failure` is valid only on an ATTEMPTED result whose verdict is UNVERIFIABLE (IMPLEMENTATION JUDGMENT, not mandated); nothing is coerced from a verdict, `MethodExecutionState`, `FindingDisposition`, `ConstructValidityStatus` or a string. No methods or properties; no score, confidence, assurance, coverage, provenance or identity fields.
- **Schema / architecture / governance / security changes:** none to existing types. No runtime wiring.
- **Test changes:** 39 new tests in each file; mirror block generated from the pytest block (see Appendix B).
- **Documentation changes:** tracker as above; this handoff.

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
| D-25 | Split Batch 3C into 3C-A (`CriterionResult`) and 3C-B (process/outcome results + `FailureControl`) | ACCEPTED | User (S13) | Tracker §9 | The user reunites them |
| D-26 | `CriterionResult` is **not** a scoped `VerificationResult` | ACCEPTED | User (S14: "well-founded") | Probe: building a result for a never-inspected criterion through `VerificationResult` needs an authorized `VerificationAssurance` and a numeric `confidence` (`None` raises) — fabricated values | The architecture defines `CriterionResult` as `VerificationResult`-shaped, or `VerificationResult` is redesigned |
| D-27 | Three attempt states with namespaced values; ATTEMPTED ⇒ verdict required, NOT_ATTEMPTED/BLOCKED ⇒ none; no SKIPPED; no verdict default | ACCEPTED (IMPLEMENTATION JUDGMENT, approved) | User (S13) | Tests; oracle 0/165 mismatches; mutants M01–M04, M16–M19, M25 caught | The frozen architecture defines criterion-level states |
| D-28 | `NOT_APPLICABLE` counts as an ATTEMPTED verdict (evaluated, applicability determined) | ACCEPTED PROVISIONALLY | User (S14) | Tracker §9 rule 8 | The frozen architecture requires another axis, or the independent review contradicts it |
| D-29 | Crash rule: `execution_failure` ⇒ ATTEMPTED + UNVERIFIABLE | IMPLEMENTED as IMPLEMENTATION JUDGMENT; **decision open** | User (S14: label it; do not let it become constitutional) | The architecture requires only "a crash never becomes a pass" and says "a crash is `FAILED`"; v1 §23 calls UNVERIFIABLE "not a verifier failure"; the mapping is inherited from `verdict.py`, which cites no source | The 3C-B reconciliation of `FAILED`; the independent review |
| D-30 | `rubric_fingerprint` is bound by value and participates in equality and hash | IMPLEMENTED (IMPLEMENTATION JUDGMENT) | User (S13: "defensible") | Facts in tracker §9 | The review decides binding vs provenance metadata |
| D-31 | `finding_ids` optional, unchecked against real findings, not coupled to `attempt_state` | IMPLEMENTED | User (S13) | Tests; mutants M23/M24 caught | The architecture establishes a findings requirement |
| D-32 | Out of 3C: `CoverageResult`, `VerifiedState`, continuous checkpoint verification, C-MoE integration, Run/Step/Trace, DecisionTrace, aggregation, events, escalation, receipt wiring | ACCEPTED | User (S13) | Tracker §9 deferral table | The user schedules them |
| D-33 | 3C-B stays untouched; next is a source-reconciliation study only (meaning of `FAILED`, owner of `failure_control`, authority of v1 §20); no placeholder enum, speculative owner or guessed authority | ACCEPTED | User (S14) | Tracker §9 | The user's instruction |
| D-34 | Do not change 3C-A code merely to perfect it; only a concrete architectural contradiction found by the independent review reopens it. (A docstring-only relabel was made under the S14 failure-semantics instruction; behavior is unchanged.) | ACCEPTED | User (S14) | `a0b9da5`: AST identical with docstrings stripped | — |
| D-35 | The pre-existing `str`-enum value collision (`MethodDisposition.INCONCLUSIVE == FindingDisposition.INCONCLUSIVE`; `unknown` also shared) stays a separate finding, out of 3C | ACCEPTED | User (S14) | Tracker §9 deferral table | A dedicated fix batch |
| D-36 | v3 "does not independently specify the 3C result contracts"; v1/v2 hold the semantics (v1 §20 stays authoritative); the exact shape is unresolved | ACCEPTED | User (S13) | v3 preserves earlier architecture by reference | The 3C-B reconciliation |
| D-37 | Push the work branch (fast-forward, no force), supplying the credential per command and never persisting it | IMPLEMENTED | User (S15; the conditions came from S12) | `git ls-remote` = `d40f000` = local HEAD; nothing in `.git/config` | One-time authorization; each later push needs a fresh instruction |

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

Not investigated (the root causes of the 13 shared failures were established on 2026-10-03; see Update 2 below): depth of every contract's tests for the 16 re-marked rows; the three `main` ADRs (`ADR_CTX_01_…`, `ADR_INDEX`, `ADR_KERNEL_06_VERIFIABLE_HYPOTHESIS_PROVENANCE`), one of which may bear on Verification provenance.

### Update 2 (2026-10-03) — investigation already performed

| Area | Inspected | Result | Revisit trigger |
|---|---|---|---|
| Branch/commit state at resume | `git fetch`; ancestry of `6428f2e`/`ef79856`; local vs remote HEAD; `main`; tree | Remote tip `ef79856`, parent `6428f2e`; `main` `4ab5345`; divergence 89/47 = 89/46 + the handoff commit; tree clean. No contradiction with the handoff | The remote moves |
| "13" vs "9" baseline failures | Full suite at HEAD and at `ead305d`, sequential | 13 = 9 `FAILED` + 4 collection `ERROR`s; the "9" counted `FAILED` only; the failing sets are identical; passes 1879 vs 1699 differ by 180 = 385 − 205 contract tests | The baseline changes |
| Causes of the 13 | Tracebacks | 12 × `ModuleNotFoundError: chromadb` (collection errors in `test_break_concurrency`, `test_break_empty_db`, `test_break_security`, `test_system_ctrl`; 6 `TestA7SystemController`; 2 `test_module_factory_security`). 1 × the CTX-AUTH-001 test, documented as "currently expected to fail", registered in `KNOWN_ISSUES.md` (partially resolved). `chromadb` was not installed to confirm that the 12 pass with it | Install `chromadb<1.0` in an environment and re-run |
| Flaky `tests/core/sandbox/test_namespace_backend.py::test_cancel_kills_all_descendant_processes` | 10 isolated runs (5 at each commit), a deliberate stray `sleep 50`, the failure message | Passes 10/10 in isolation; the test uses a global `pgrep -f "sleep 50"` and fails with "orphaned process(es)" whenever any other process has that string in its command line (a stray `sleep 50`, or a shell whose command line contains it). One baseline run failed while the investigator's own monitoring command `sleep 50; ls …` was running. **That this was the matched process is likely but not proven** (the mechanism reproduces; the PIDs were not tied to it) | Never run suites concurrently, and keep `sleep 50` out of command lines near a run |
| 3C architecture study | v1 §13, §20, §23, §25, §42; v2 §9, §11, §19, §21; v3 §1, §5; `verdict.py`, `finding.py`, `dimension.py`, `receipt.py`, `observation.py`, `method.py`, `absence.py`, `coverage.py`, `rubric.py`, `shape.py`, `identity.py`, `epistemic.py` | `CriterionResult`/process/outcome results are *named* in lists only; v1 §20 is the only definition of process/outcome separation and `failure_control`, and v2/v3 neither restate nor revoke it; `FAILED` is not a canonical verdict state (v1 §25); a method-level `MethodExecutionState` already existed (the earlier tracker claim of no such axis was stale); `VerificationResult` reuse forces a fabricated assurance and confidence; `failure_control` appears nowhere in code; `CriterionCoverage` is a rubric-level quantity; no `CoverageResult` tracker row exists although v1 §42 lists it | The architecture text changes |
| Crash / failure semantics | v1 Self-Review Pass 3 (line 270), v1 §23 (line 124), v2 Review C (line 322), `verdict.py`, tracker line 102 | Architecture: a crash never becomes a pass ("fail-closed") and "a crash is `FAILED`" (not a canonical verdict); UNVERIFIABLE is a "successful abstention outcome, not a verifier failure". Code: `execution_failure` ⇒ UNVERIFIABLE with no cited source. The tracker's "exact rule" claim (line 102) overstated this and now carries a dated correction | The 3C-B reconciliation of `FAILED` |
| `str`-enum value collisions in `core/verification` | Scan of every `str` enum | `MethodDisposition.INCONCLUSIVE == FindingDisposition.INCONCLUSIVE` is `True`; `unknown` is shared (e.g. `ProvenanceCompleteness.UNKNOWN`); `blocked`, `not_run`, `verified`, `not_applicable` are taken, which is why `CriterionAttemptState` values are namespaced | A dedicated fix batch |
| 3C-A review groundwork (preparation, **not** the independent review) | Oracle over all 165 valid-type combinations; mirror regeneration; throwaway higher-level view; `dataclasses.fields` facts | 0 oracle mismatches (16 accepted: NOT_ATTEMPTED 1, BLOCKED 1, ATTEMPTED 14); the mirror block regenerates byte-for-byte from the pytest block, test names identical and ordered, 55/55 assertions and 18/18 raises preserved; a throwaway view consumed results and needed no change to the type; `rubric_fingerprint` participates in `__eq__` and `__hash__` | The independent review |

Not investigated: whether `CoverageResult` (v1 §42) should get a tracker row; the other v1 §42 names against the tracker (only `CoverageResult` was checked); any v1 §20 text beyond the quoted lines; `KNOWN_ISSUES.md` beyond the CTX-AUTH-001 line.

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
| Mutation runner that lets Python reuse bytecode (2026-10-03) | Two consecutive same-size mutants written within one second can be served the previous `.pyc`: one kill was attributed to the wrong test (the counts happened to match) | Run `python3 -B` with `PYTHONDONTWRITEBYTECODE=1` and delete `core/verification/__pycache__/criterion_result*` before every mutant run; check *which* test killed each mutant, not only the count |
| `pkill -f "sleep 50"` inside the same shell command | Killed the invoking shell, because its own command line contains the pattern | Do not; wait for processes to exit |
| Starting the second suite run in the background from a tool call that then ended | The run died partway and produced no result | Run each suite in the foreground, one at a time (or `setsid nohup` and poll) |
| Loading a mutated copy of a dataclass module with `exec` without registering it in `sys.modules` | The `@dataclass` decorator failed | Register the module in `sys.modules` first (used for the equivalence proof, Appendix B) |
| Reusing `VerificationResult` as `CriterionResult` (the 2026-09-07 tracker recommendation) | Forces a fabricated authorized assurance and a numeric confidence | Do not retry (D-26) |

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

### Update 2 (2026-10-03) — verification evidence

Step 0 (resume), all from the repo root, no code changes:
- `git fetch origin`; `git merge-base --is-ancestor 6428f2e origin/feature/verification-critic-evidence-phase-c` → yes; `git rev-parse ef79856^` → `6428f2e`; `git log -1 -- handoff.md` → `ef79856`; remote tip = local HEAD = `ef79856`; `origin/main` = `4ab5345`; `git status` clean.
- pytest (section 13 command) → **385 passed in 0.63s**; stdlib mirror → **Ran 385 tests, OK**; mypy → **no issues in 27 source files** (mypy 2.4.0 here vs 2.3.1 in version 1); import-all → 26 modules OK.
- Broader suite at HEAD → **9 failed, 1879 passed, 1 warning, 4 errors in 36.44s** (identical to this file's figures). At `ead305d` (a detached worktree) → **10 failed, 1698 passed, 4 errors in 33.96s**; the extra failure is the flaky `test_cancel_kills_all_descendant_processes` (section 11); a first baseline attempt died partway and was discarded. After the run, `git checkout -- data config` restored four rewritten files (`config/sources.toml` was the one version 1 did not list).

Batch 3C-A:
- `python3 -m pytest tests/test_verification_contracts.py -q -p no:cacheprovider -o addopts=""` → **424 passed**; `python3 tests/verification_run_tests_stdlib.py` → **Ran 424 tests, OK**; mypy → **no issues in 28 source files**; import-all → **27 modules OK**.
- Broader suite after the change → **9 failed, 1918 passed, 1 warning, 4 errors in 35.51s**; `comm` of the failing sets against the pre-change HEAD → empty both ways.
- Mutation (Appendix B harness, 30 mutants): **29 caught, 1 survived (M06), proved equivalent** by running the original and mutated classes over all 165 valid-type combinations (3 states × 11 verdict values × 5 failure values): 0 differences; the original accepts exactly 16. M06 removes the `attempt_state is not ATTEMPTED` clause of the crash check, which is redundant because invariant 3 already forces `verdict=None` for unevaluated states. A "permissive stub" with all validation removed (`__post_init__` does nothing) fails **12 of the 39** new tests (the harness prints it); the remaining 27 are acceptance and structure tests that rightly still pass.
- Patches: `git format-patch ef79856..HEAD`; applied with `git am` onto a detached worktree at `ef79856` → clean, 424 passed, tree identical to the local branch.
- `a0b9da5` (docstrings and tracker): AST identical with docstrings stripped (script in Appendix B); 424/424, mypy clean. The broader suite was **not** re-run after `a0b9da5` or this handoff update (documentation only).

- Push (2026-10-03, S15): `git fetch` first; fast-forward confirmed (`git merge-base --is-ancestor origin/<branch> HEAD`); `git push origin HEAD:refs/heads/feature/verification-critic-evidence-phase-c` with a one-off `http.extraHeader` (no URL token, no config) → `ef79856..d40f000`; afterwards `git config --get-regexp 'extraheader|credential'` and `.git/config` held nothing; `git ls-remote` (no credentials) → branch `d40f000`, `main` `69df55f`; `git fetch` then remote branch == local HEAD.

Limitations: self-verification only (the independent review is open); the 12 `chromadb`-dependent tests were not run with `chromadb`; mirror parity is shown by derivation (the converter is validated on 347 pre-existing mirror lines with 0 differences) and by both suites passing, not by an independent re-implementation; the mutation set covers the rules listed above, not every line.

---

## 14. Environment / Tooling Assumptions

- Python 3.12.3 in the sandbox (repo declares `requires-python >= 3.11`). Installed for the suite: pytest 9.1.1, pytest-asyncio 1.4.0, pytest-mock 3.16.0, mypy 2.3.1, datasketch, fastapi, httpx, aiohttp, pydantic, scipy, rich, PyYAML, trafilatura, and the other lightweight requirements. **Not installed:** `chromadb`, `sentence-transformers` (likely cause of several shared failures). The pytest warning "Unknown config option: asyncio_mode" is expected.
- A full-suite run **rewrites tracked files** (`data/context.sqlite`, `config/models.toml`, `config/settings.toml`, `config/sources.toml` [corrected 2026-10-03: `sources.toml` was missing from this list]). After every run: `git checkout -- data config` and confirm `git status --short` is empty. Never commit them.
- `git` commits in the sandbox used `-c user.name="Claude" -c user.email="noreply@anthropic.com"`.
- The repository is public: `git clone` and `git fetch` need no credentials. Pushing needs a credential; **the user's GitHub token was pasted into their claude.ai preferences and into the chat, so it must be treated as exposed. It still worked for pushes at the end of this session. It is not recorded here. Do not push unless the user explicitly asks, and remind them to revoke and rotate it.** Pass any credential as a one-off `http.extraheader`, never stored in git config, and push only the feature branch, fast-forward, never force.
- Network in the sandbox was limited to GitHub/npm/pypi style hosts.

### Update 2 (2026-10-03) — environment

- The sandbox was **fresh** on resume (no installed tools). Reinstall with `pip install --break-system-packages pytest pytest-asyncio pytest-mock mypy datasketch fastapi httpx aiohttp pydantic scipy rich PyYAML trafilatura aiofiles beautifulsoup4 click feedparser requests tomli tomli-w "uvicorn[standard]"` — **without** `chromadb` and `sentence-transformers`, which is the origin of the 12 environmental failures. Versions seen: Python 3.12.3, pytest 9.1.1, pytest-asyncio 1.4.0, pytest-mock 3.16.0, **mypy 2.4.0** (version 1 recorded 2.3.1; the results are the same).
- Network: `git clone` and `git fetch` of the public repo work without credentials. The user's token was used **once**, on the user's explicit authorization (S15), as a one-off `http.extraHeader` for the push; it is not stored here and nothing was written to `.git/config`. It was still visible in the user's claude.ai preferences, and it still authenticated, so R14 remains open (revoke, rotate, and remove it from the preferences).
- Never run a suite concurrently with another, and keep the string `sleep 50` out of command lines that run beside the suite (section 11).
- Scratch tooling (`mkmirror.py`, `mutate.py`, the oracle/parity/AST checks) lived in `/home/claude/tools` outside the repository; it is reproduced in Appendix B.

---

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Options | Disposition | May work continue? |
|---|---|---|---|---|
| Token exposure (R14) | Same token worked at the last push; still visible in the user's claude.ai preferences at resume (2026-10-03); used once, with authorization (S15), as a one-off header for the push; not stored here | User revokes and rotates, and removes it from preferences | OPEN, user action | Yes, but no pushes without explicit instruction |
| 3C scope | [corrected 2026-10-03] Proposed and split (S13): 3C-A implemented locally, 3C-B blocked | See the Update 2 rows below | SUPERSEDED | Yes |
| `VerificationObservation` undefined | Only a name in the v1 contract list | User defines it, or it stays deferred | DEFERRED | Yes |
| v1 §15 evidence metadata placement | No authoritative vocabulary | Extend `EvidenceItem` or add a companion, after the consuming layer exists | DEFERRED | Yes |
| `DIRECT → DIRECT` per-type table | Architecture silent | Add only on a user decision | DEFERRED | Yes |
| Definition of "sufficient" coverage | Architecture silent | Keep producer-declared boolean | DEFERRED | Yes |
| `VerificationAssurance.coverage` ↔ `VerificationCoverage` relation | Architecture silent | Leave unlinked | DEFERRED | Yes |
| G8 hardening debt | Tracker §9 | Dedicated hardening pass | DEFERRED | Yes |
| Merging with `main` | [updated 2026-10-03] 91 behind, 51 ahead (was 89/46); `main` gained two docs commits (DEBT-039, DEBT-021), only `KNOWN_ISSUES.md` changed; still one docs conflict in `KNOWN_ISSUES.md` | Decide merge path, register debts with non-colliding ids, re-run suites | NOT AUTHORIZED | Yes |
| The 13 shared failures | [corrected 2026-10-03] Causes established: 12 × `ModuleNotFoundError: chromadb`, 1 × known CTX-AUTH-001 test (section 11) | Install `chromadb<1.0` and re-run to confirm the 12 pass | RESOLVED as to cause; the 12 remain unverified with `chromadb` | Yes |
| Three ADRs added on `main` | Not read | Read before 3C/provenance-related work | OPEN | Yes |
| Invisible format characters count as non-blank | Same `str.strip()` rule everywhere in the package | Package-wide decision | Known limitation | Yes |
| **Crash rule is judgment, not mandated** (`execution_failure` ⇒ ATTEMPTED + UNVERIFIABLE) | Architecture: a crash never becomes a pass; "a crash is `FAILED`"; UNVERIFIABLE is "not a verifier failure" (v1 Self-Review Pass 3, v1 §23, v2 Review C). Code inherits the mapping from `verdict.py`, which cites no source | (a) keep and label — consistent with `VerificationResult`; (b) weaken to "never positive", which needs a definition of "positive" (itself a judgment); (c) drop `execution_failure` from `CriterionResult` until `FAILED` is reconciled | OPEN DECISION (reviewer/user); labeled; code unchanged | Yes; it must be decided or explicitly carried before 3C-A is closed |
| `FAILED`, `failure_control` ownership, authority of v1 §20 | `FAILED` is not in v1 §25; `failure_control` is an "orthogonal verification finding"; v3 incorporates earlier architecture by reference | Source-reconciliation study (no code) | BLOCKED (3C-B) | Yes, for everything except 3C-B; no placeholder types |
| Independent adversarial review of 3C-A | Only implementer-produced evidence exists | A reviewer other than the implementer challenges the eight areas in tracker §9 | OPEN | The next step |
| Local-only commits; sandbox resets | [corrected 2026-10-03] Pushed on authorization (S15); remote verified at `d40f000` | — | RESOLVED | Yes |
| 12 `chromadb`-dependent tests (some security-relevant: `TestA7SystemController`, `test_module_factory_security`) never ran here | `ModuleNotFoundError` | Install `chromadb<1.0` in a full environment | OPEN, optional | Yes |
| Pre-existing `str`-enum value collisions in `core/verification` | `MethodDisposition.INCONCLUSIVE == FindingDisposition.INCONCLUSIVE`; `unknown` shared | Namespace the values in a dedicated batch | DEFERRED | Yes |
| `CoverageResult` (v1 §42) has no tracker row | Tracker row scan | Add a row on a user decision | OPEN, minor | Yes |

---

## 16. Relevant Information / References

- Governing contract: `PROJECT_INSTRUCTIONS.md` (sections 0, 14.4, 16.3–16.5, 18.4.8–18.4.12, 24).
- Frozen architecture: `docs/architecture/verification-critic-evidence-system-architecture-v1.md`, `…-v2-frozen.md`, `…-v3-final.md`. Key text: v1 §15/§16 (evidence chain and metadata), v1 §21 and v2 §13 (absence states, five coverage fields), v2 §9 (construct validity), v2 §14 (provenance completeness, transformation safety), v2 §16 (per-surface authorization), v2 §24/§25 (Reference/Oracle, Assumption), v2 §44 (minimum sufficient evidence).
- Design proposals and earlier phases: `…-compiledverificationspecification-design-proposal.md`, `…-finding-critique-design-proposal.md`, `…-verificationmethod-design-proposal.md`, `…-phase-0-reality-audit.md`, `…-phase-1-contract-reconciliation.md`.
- Tracker: `…-phase-c-semantic-pipeline-reconciliation.md`, in particular §9 (status register, decision records for `Rubric.construct`, 3A and 3B deferral tables).
- Conventions to keep: frozen dataclasses; identity wrappers are `NewType("...", str)` in `identity.py`, added only for independently addressable objects; no re-exports in `__init__.py`; label non-architectural choices `IMPLEMENTATION JUDGMENT`; never claim more than the evidence shows; a `str`-Enum member compares equal to any other `str`-Enum member with the same value, so check for value collisions when adding enums.
- Repository cautions: `check_not_circular` has no callers outside the new evidence contracts' `verify_against` methods and tests (pre-existing).

Update 2 references: v1 "Self-Review — Pass 3 (adversarial)" (crash is `FAILED`), v1 §20 (process/outcome separation, `failure_control`), v1 §23 (UNVERIFIABLE is a successful abstention outcome), v1 §25 (canonical verdicts), v2 "Review C", v3 Part 1 §5; tracker §9 for the 3C-A rule-provenance table, closure conditions and deferral table; `core/verification/criterion_result.py` docstrings.

---

## 17. Next Steps

> **[Update 2, 2026-10-03]** Items 2 and 3 below are superseded by the Update 2 list at the end of this section (3C-A is implemented; 3C-B is blocked). Items 1 and 4–6 still stand.

1. **Resume and verify** (section 18). Do not change code until the state matches this handoff.
2. **Batch 3C scope (rows 10 and 30: `CriterionResult`, `ProcessVerificationResult`/`OutcomeVerificationResult`).** Where: read the frozen architecture text for these (grep the three architecture docs and the tracker rows), plus existing `VerificationResult`/`VerificationVerdict` in `verdict.py` and `Criterion*` in `rubric.py`. Why: it is the next step the user ordered. Prerequisite: the user's approval of a bounded scope before any code; expect `VerificationObservation`-style gaps where the architecture only names a type. Verification: a short scope proposal listing what is architecture, what is judgment, what is deferred, and one question for the user.
3. **Implement 3C** with the standard discipline (section 4): live-state proof, contract matrix, tests in both files, mutation check, mypy, import-all, sequential broader suite vs baseline, code commit then docs commit, tracker row updates, patches, no push.
4. **Later clusters** (each needs an approved scope): rows 1 and 3 (`VerificationRequest`, `VerificationContext`), 50 and 51 (`BlindVerificationContext`, `PolicyPrecedence`), 35/36/38/39 (Run/Step/Trace/DecisionTrace), 41 (`VerificationBudget`), 42/43 (`EscalationRequest`, `AdjudicationRecord`), 24 (`VerificationObservation`, after a definition).
5. **Before any merge:** user revokes/rotates the token; decide the merge path with `main`; register G8 and any other debts in `KNOWN_ISSUES.md` with non-colliding `DEBT-` ids; re-run the Verification suites and the broader suite after merging `main`; keep the code/docs commit separation.
6. **Optional hardening (G8)** once the user schedules it: replace string-blacklist tests in Batch 1 with field-level rejection tests, add runtime enum checks for `Assumption.status` / `Reference.quality` (as 3A does for `ConstructValidity.status`), decide a consumer for `ClaimDependency`.

### Update 2 (2026-10-03) — current next steps, in order

1. **Resume and verify** (section 18, Update 2). Do not change code until the state matches this file.
2. **Independent adversarial review of 3C-A**, by someone other than the implementer, challenging the eight areas in tracker §9 "Closure conditions" (state machine, `NOT_APPLICABLE`, failure semantics, findings, fingerprint, aggregation boundary, mirror parity, documentation). Use the oracle in Appendix B (edit its crash line to test alternatives). Expected verification: the reviewer's findings, each with evidence.
3. **Decide the crash rule** (section 15): keep and label, weaken, or drop the field. Prerequisite: the review, and awareness that the `FAILED` question is the same one 3C-B must reconcile.
4. **Resolve or document each review finding. Do not change 3C-A code** unless the review finds a concrete architectural contradiction (D-34).
5. **Close 3C-A** in the tracker (status change only after steps 2–4).
6. **Source-reconciliation study for 3C-B**, no code: what `FAILED` means in the frozen architecture, who owns `failure_control`, what authority v1 §20 has. No placeholder enum, speculative owner or guessed authority model (D-33).
7. **Only then design 3C-B**, with a scope proposal and approval first.
8. Items 4–6 of the version-1 list (later clusters, before any merge, G8 hardening) are unchanged. Pushing needs the user's explicit instruction each time (given on 2026-10-03 for the 3C-A work; not standing).

---

## 18. Resume Instructions

> **[Update 2, 2026-10-03]** The 3C-A work is on the remote branch (pushed 2026-10-03 and verified; tip `d40f000` plus a status-only follow-up commit). A fresh checkout gives the Update 2 state: 424 tests / 424 mirror / mypy clean on 28 files. The counts in steps 2 and 4 below describe `ef79856` (version 1).

First actions in a fresh session:
1. Read `PROJECT_INSTRUCTIONS.md`, then this file completely. Answer in English.
2. `git fetch origin`; confirm branch `feature/verification-critic-evidence-phase-c` contains `6428f2e` (`git merge-base --is-ancestor 6428f2e origin/feature/verification-critic-evidence-phase-c`) and that `git log -1 -- handoff.md` is the handoff commit whose parent is `6428f2e`.
3. Check out the branch; `git status --short` must be empty.
4. Re-run section 13's pytest, stdlib mirror and mypy commands; expect 385 / 385 / clean. If anything differs, resolve it before touching code and correct this handoff.
5. Do not re-run investigations listed in section 11 unless a revisit trigger fired.
6. Begin at Next Step 2 (3C scope proposal). Wait for the user's approval before implementing.

Do not: push, merge into `main`, rewrite published history, or use the exposed token without the user's explicit instruction.

### Update 2 (2026-10-03) — additional resume steps

7. Re-run: pytest → 424 passed; stdlib mirror → 424 OK; mypy → no issues in 28 files; import-all → 27 modules. Confirm `git log -1 -- handoff.md` is the latest status commit and that `main` has not moved again (it was `69df55f`).
8. Begin at Update 2 Next Step 2 (the independent review). Do not re-run the investigations in section 11 (Update 2) unless a revisit trigger fired.
9. Do not: push, merge `main`, rewrite history, force-push, or use the exposed token, without explicit instruction.

---

## 19. Transfer Status

> **[Update 2, 2026-10-03] Current status: TRANSFER READY**, with one stated condition. Satisfied and verified: the 3C-A implementation commit (`4c93878`), the documentation commits (`99f3acd`, `a0b9da5`) and the handoff-version-2 commit (`d40f000`) were pushed to `origin/feature/verification-critic-evidence-phase-c` on the user's authorization (S15) and verified with `git ls-remote` (remote = local HEAD = `d40f000`; fast-forward, no force). Condition: this status edit is a follow-up, status-only commit; it is pushed the same way and `git ls-remote` must show it as the branch tip. If it is not on the remote, the transfer is still ready through `d40f000` and only this status text is missing. Non-repository state: none required for continuation (the tooling is in Appendix B). Not closed: 3C-A still awaits the independent review.

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

### Update 2 (2026-10-03) — tooling used (these lived in `/home/claude/tools`, outside the repo)

**`mkmirror.py` — pytest → stdlib-mirror converter.** Supersedes the version-1 converter. Validated by regenerating 347 existing mirror lines (`TestConstructValidityStatus`, `TestConstructValidity`, `TestConstructValidityAndRubricIdentity`, `TestCoverageTypes`, `TestCoverageIndependence`, `TestObservationAbsenceState`, `TestObservationAbsence`): **0 differences**. It refuses ambiguous asserts and unhandled `pytest` usage. Usage: `convert(block)` on the new pytest classes, then insert the result before `if __name__ == "__main__":` in the mirror.

```python
"""pytest-style test source -> unittest mirror source. Refuses anything it cannot convert unambiguously."""
import re, sys

OPS = [" is not ", " not in ", " == ", " != ", " is ", " in "]

def top_level_ops(e):
    depth, quote, i, hits = 0, None, 0, []
    while i < len(e):
        ch = e[i]
        if quote:
            if ch == "\\": i += 2; continue
            if ch == quote: quote = None
        elif ch in "\"'": quote = ch
        elif ch in "([{": depth += 1
        elif ch in ")]}": depth -= 1
        elif depth == 0:
            for op in OPS:
                if e.startswith(op, i):
                    hits.append((i, op)); i += len(op) - 1; break
        i += 1
    return hits

def split_top(e, op, idx):
    return e[:idx].strip(), e[idx+len(op):].strip()

def conv_assert(expr):
    e = expr.strip()
    for bad in (" and ", " or "):
        if bad in _strip_nested(e): return f"self.assertTrue({e})"
    if e.startswith("not "): return f"self.assertFalse({e[4:].strip()})"
    hits = top_level_ops(e)
    if len(hits) == 0: return f"self.assertTrue({e})"
    if len(hits) > 1: raise SystemExit(f"ambiguous assert ({len(hits)} top-level operators): {e}")
    idx, op = hits[0]; a, b = split_top(e, op, idx)
    if op == " == ": return f"self.assertEqual({a}, {b})"
    if op == " != ": return f"self.assertNotEqual({a}, {b})"
    if op == " is not ": return f"self.assertIsNotNone({a})" if b == "None" else f"self.assertIsNot({a}, {b})"
    if op == " is ": return f"self.assertIsNone({a})" if b == "None" else f"self.assertIs({a}, {b})"
    if op == " not in ": return f"self.assertNotIn({a}, {b})"
    if op == " in ": return f"self.assertIn({a}, {b})"
    raise SystemExit("unreachable")

def _strip_nested(e):
    out, depth, quote = [], 0, None
    for ch in e:
        if quote:
            if ch == quote: quote = None
            continue
        if ch in "\"'": quote = ch; continue
        if ch in "([{": depth += 1; continue
        if ch in ")]}": depth -= 1; continue
        if depth == 0: out.append(ch)
    return "".join(out)

def convert(text):
    out = []
    for line in text.split("\n"):
        m = re.match(r"^(\s*)assert (.+)$", line)
        if m:
            e = m.group(2)
            if e.rstrip().endswith(("(", "[", "{", ",", "\\")) : raise SystemExit(f"multi-line assert not supported: {line}")
            out.append(f"{m.group(1)}{conv_assert(e)}"); continue
        m = re.match(r"^(\s*)with pytest\.raises\((.+)\):\s*$", line)
        if m: out.append(f"{m.group(1)}with self.assertRaises({m.group(2)}):"); continue
        m = re.match(r"^class (Test\w+):\s*$", line)
        if m: out.append(f"class {m.group(1)}(unittest.TestCase):"); continue
        if "pytest" in line and not line.lstrip().startswith("#"): raise SystemExit(f"unhandled pytest usage: {line}")
        out.append(line)
    return "\n".join(out)

if __name__ == "__main__":
    sys.stdout.write(convert(open(sys.argv[1], encoding="utf-8").read()))
```

**`mutate.py` — mutation harness for `criterion_result.py`** (30 mutants; M06 is the proven-equivalent one). It asserts a unique match before each replacement, deletes `__pycache__/criterion_result*` and runs `python3 -B` with `PYTHONDONTWRITEBYTECODE=1` before every run (see section 12), restores the source and checks its SHA-256 at the end. Adapt `SRC` and the `-k` filter for a new module.

```python
import subprocess, shutil, hashlib, sys
SRC="/home/claude/ocbrain/core/verification/criterion_result.py"
orig=open(SRC,encoding="utf-8").read(); h0=hashlib.sha256(orig.encode()).hexdigest()
def sub(old,new): return ("sub",old,new)
M=[
("M01 ATTEMPTED may have no verdict (the ruled-out third state)", sub('            if self.verdict is None:\n                raise ValueError(\n                    "an ATTEMPTED','            if False:\n                raise ValueError(\n                    "an ATTEMPTED')),
("M02 unevaluated states may carry any verdict", sub('        elif self.verdict is not None:\n            raise ValueError(\n                f"a {self.attempt_state.name}','        elif False:\n            raise ValueError(\n                f"a {self.attempt_state.name}')),
("M03 BLOCKED may carry a verdict", sub('        elif self.verdict is not None:\n            raise','        elif self.verdict is not None and self.attempt_state is CriterionAttemptState.NOT_ATTEMPTED:\n            raise')),
("M04 NOT_ATTEMPTED may carry a verdict", sub('        elif self.verdict is not None:\n            raise','        elif self.verdict is not None and self.attempt_state is CriterionAttemptState.BLOCKED:\n            raise')),
("M05 crash coupling removed entirely", sub('        if self.execution_failure is not None and (\n            self.attempt_state is not CriterionAttemptState.ATTEMPTED\n            or self.verdict is not VerificationVerdict.UNVERIFIABLE\n        ):','        if False:')),
("M06 crash coupling: ATTEMPTED-state clause dropped", sub('            self.attempt_state is not CriterionAttemptState.ATTEMPTED\n            or self.verdict is not VerificationVerdict.UNVERIFIABLE\n','            self.verdict is not VerificationVerdict.UNVERIFIABLE\n')),
("M07 crash coupling inverted", sub('or self.verdict is not VerificationVerdict.UNVERIFIABLE','or self.verdict is VerificationVerdict.UNVERIFIABLE')),
("M08 criterion_id check removed", sub('if not isinstance(self.criterion_id, str) or not self.criterion_id.strip():','if False:')),
("M09 rubric_fingerprint check removed", sub('if not isinstance(self.rubric_fingerprint, str) or not self.rubric_fingerprint.strip():','if False:')),
("M10 attempt_state type check removed", sub('if not isinstance(self.attempt_state, CriterionAttemptState):','if False:')),
("M11 verdict type check removed", sub('if self.verdict is not None and not isinstance(self.verdict, VerificationVerdict):','if False:')),
("M12 execution_failure type check removed", sub('if self.execution_failure is not None and not isinstance(\n            self.execution_failure, VerificationExecutionFailure\n        ):','if False:')),
("M13 finding_ids tuple check removed", sub('if not isinstance(self.finding_ids, tuple):','if False:')),
("M14 finding_ids element type check removed", sub('if not isinstance(finding_id, str):','if False:')),
("M15 finding_ids blank element check removed", sub('if not finding_id.strip():','if False:')),
("M16 BLOCKED value collides with MethodExecutionState", sub('BLOCKED = "criterion_blocked"','BLOCKED = "blocked"')),
("M17 NOT_ATTEMPTED value collides with MethodExecutionState", sub('NOT_ATTEMPTED = "criterion_not_attempted"','NOT_ATTEMPTED = "not_run"')),
("M18 ATTEMPTED value collides with VerificationVerdict", sub('ATTEMPTED = "criterion_attempted"','ATTEMPTED = "verified"')),
("M19 SKIPPED invented", sub('    ATTEMPTED = "criterion_attempted"\n','    ATTEMPTED = "criterion_attempted"\n    SKIPPED = "criterion_skipped"\n')),
("M20 mini-aggregator method added", sub('    def __post_init__(self) -> None:','    def worst_of(self):\n        return self.verdict\n\n    def __post_init__(self) -> None:')),
("M21 confidence field added", sub('    finding_ids: Tuple[VerificationFindingId, ...] = ()\n','    finding_ids: Tuple[VerificationFindingId, ...] = ()\n    confidence: float = 0.0\n')),
("M22 computed property added", sub('    def __post_init__(self) -> None:','    @property\n    def is_positive(self) -> bool:\n        return self.verdict is VerificationVerdict.VERIFIED\n\n    def __post_init__(self) -> None:')),
("M23 finding_ids required for ATTEMPTED (ruled out)", sub('        if not isinstance(self.finding_ids, tuple):','        if self.attempt_state is CriterionAttemptState.ATTEMPTED and not self.finding_ids:\n            raise ValueError("findings required")\n        if not isinstance(self.finding_ids, tuple):')),
("M24 invented invariant: unevaluated cannot have findings", sub('        if not isinstance(self.finding_ids, tuple):','        if self.attempt_state is not CriterionAttemptState.ATTEMPTED and self.finding_ids:\n            raise ValueError("no findings when unevaluated")\n        if not isinstance(self.finding_ids, tuple):')),
("M25 verdict gets a default (reached by omission)", sub('    verdict: Optional[VerificationVerdict]\n    execution_failure','    verdict: Optional[VerificationVerdict] = None\n    execution_failure')),
("M26 verdict check loosened to any str", sub('not isinstance(self.verdict, VerificationVerdict):','not isinstance(self.verdict, str):')),
("M27 coverage import added (boundary)", sub('from .identity import CriterionId, VerificationFindingId\n','from .identity import CriterionId, VerificationFindingId\nfrom .coverage import CriterionCoverage\n')),
("M28 criterion_id: whitespace accepted", sub('or not self.criterion_id.strip():','or not self.criterion_id:')),
("M29 rubric_fingerprint: whitespace accepted", sub('or not self.rubric_fingerprint.strip():','or not self.rubric_fingerprint:')),
("M30 attempt_state coercion from str", sub('        if not isinstance(self.attempt_state, CriterionAttemptState):','        if isinstance(self.attempt_state, str) and not isinstance(self.attempt_state, CriterionAttemptState):\n            object.__setattr__(self, "attempt_state", CriterionAttemptState(self.attempt_state))\n        if not isinstance(self.attempt_state, CriterionAttemptState):')),
]
def _clean():
    import glob, os
    for f in glob.glob("/home/claude/ocbrain/core/verification/__pycache__/criterion_result*"): os.remove(f)
def run():
    _clean()
    r=subprocess.run(["python3","-B","-m","pytest","tests/test_verification_contracts.py","-q","-x","--tb=no","-p","no:cacheprovider","-o","addopts=","-k","CriterionAttemptState or CriterionResult"],cwd="/home/claude/ocbrain",capture_output=True,text=True,env={**__import__("os").environ,"PYTHONDONTWRITEBYTECODE":"1"})
    out=r.stdout+r.stderr; fails=[l for l in out.split("\n") if l.startswith("FAILED") or l.startswith("ERROR")]
    return r.returncode, (fails[0][:110] if fails else out.strip().split("\n")[-1][:80])
killed=0; survived=[]
try:
    for name,(kind,old,new) in M:
        assert orig.count(old)==1, f"pattern not unique/found for {name}: {orig.count(old)}"
        open(SRC,"w",encoding="utf-8").write(orig.replace(old,new))
        rc,info=run()
        if rc!=0: killed+=1; print(f"KILLED   {name}\n           by {info.replace('FAILED tests/test_verification_contracts.py::','')}")
        else: survived.append(name); print(f"SURVIVED {name}")
    # permissive stub: __post_init__ does nothing
    i=orig.index("    def __post_init__"); open(SRC,"w",encoding="utf-8").write(orig[:i]+"    def __post_init__(self) -> None:\n        pass\n")
    _clean()
    r=subprocess.run(["python3","-B","-m","pytest","tests/test_verification_contracts.py","-q","--tb=no","-p","no:cacheprovider","-o","addopts=","-k","CriterionAttemptState or CriterionResult"],cwd="/home/claude/ocbrain",capture_output=True,text=True)
    print("\nPERMISSIVE STUB (all validation removed):", r.stdout.strip().split("\n")[-1])
finally:
    open(SRC,"w",encoding="utf-8").write(orig)
assert hashlib.sha256(open(SRC,encoding="utf-8").read().encode()).hexdigest()==h0
print(f"\nmutants: {len(M)}  killed: {killed}  survived: {len(survived)} {survived}\nsource restored byte-identical: True")
```

**State-machine oracle (independent of the implementation; vary the crash line to test alternatives):**

```python
import itertools
from core.verification.criterion_result import CriterionResult as R, CriterionAttemptState as S
from core.verification.verdict import VerificationVerdict as V, VerificationExecutionFailure as F
def oracle(state, verdict, failure):
    if state is S.ATTEMPTED and verdict is None: return False
    if state is not S.ATTEMPTED and verdict is not None: return False
    if failure is not None and not (state is S.ATTEMPTED and verdict is V.UNVERIFIABLE): return False  # IMPLEMENTATION JUDGMENT
    return True
def impl(state, verdict, failure):
    try: R("c1", "fp", state, verdict, failure); return True
    except (ValueError, TypeError): return False
dom = list(itertools.product(S, [None] + list(V), [None] + list(F)))
print(len(dom), sum(impl(*d) for d in dom), [d for d in dom if oracle(*d) != impl(*d)])   # expect 165 16 []
```

**Docstring-only proof (AST identical once docstrings are stripped):**

```python
import ast
def stripped(path):
    t = ast.parse(open(path, encoding="utf-8").read())
    for n in ast.walk(t):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) and isinstance(b[0].value.value, str):
                n.body = b[1:] or [ast.Pass()]
    return ast.dump(t)
# git show <old>:core/verification/criterion_result.py > /tmp/before.py ; compare stripped(before) == stripped(after)
```

**Mirror parity check:** regenerate the mirror block with `convert()` from the 3C-A section of `tests/test_verification_contracts.py` (from the `# Batch 3C-A -- CriterionResult` banner to the end of the file) and compare it byte for byte with the same section of `tests/verification_run_tests_stdlib.py`; compare the ordered `test_*` names; compare the counts of `assert` lines with `self.assert*` calls (55/55) and of `pytest.raises` with `assertRaises` (18/18).

**Equivalence proof for a surviving mutant:** load the original and the mutated source as modules registered in `sys.modules` (section 12), then compare outcomes (`ok` or the exception type) over the full finite domain, as in the oracle above.
