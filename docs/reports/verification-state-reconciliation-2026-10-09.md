# Verification subsystem: state reconciliation (2026-10-09)

Status: read-only audit plus documentation corrections. Nothing here changes code. The documentation corrections were committed and then pushed to the Verification branch as a fast-forward on the user's authorization.

## 0. Basis and source identity

- **Specification supplied:** the uploaded file `Pasted_markdown_10_.md` (4,317 lines). It is "Final Parallel Research + Implementation Mission, Canonical Master Prompt for Claude Code", §0–§117, the same text supplied earlier in the conversation, and the document the Phase A findings cite. Treated as the specification, as instructed.
- **It is not the continuation of the truncated "Parallel Implementation Mission and Repository Reconciliation Protocol"** (which stops mid-§13). The file contains none of that prompt's opening sentence or its v3 Part 1 concepts (`VerificationShape`, `POINTWISE`, `VerificationProfile`, `DEBT-015`, `WorkflowRuntime`, `VerifiedState` do not occur). The truncated prompt's §14 onward therefore remain unavailable.
- **Consequence for open items:** the six 3C-B questions and M9 are not closed by this file. A mechanical search of it found none of the phrases the repo's code attributes to "the mission" (for example "What had to be true for this verification statement to hold"). `docs/architecture/verification-critic-evidence-system-phase-0-reality-audit.md` (line 4) refers to a separate "September 2026 master implementation prompt" with "Phase 0–14 numbering"; that prompt is not in the repository and has not been recovered.
- **Method:** `git fetch` of all remotes, `git diff`/`git grep` against `origin/main` and `fe338ed`, import-time class inspection of `core/verification`, and fresh test runs. Commands are listed in the handoff.

## 1. Repository baseline

| Item | Verified value |
|---|---|
| `origin/main` | `27d918d`, 2026-10-09 (merge of PR #71) |
| Verification branch | `feature/verification-critic-evidence-phase-c`, tip `fe338ed` (2026-10-03), unchanged since the independent review |
| Divergence | 137 commits only on `main`, 52 only on the branch; merge-base `5954e44` |
| `main` changes since the merge-base | 85 files; **none** under `core/verification/` or the two Verification test files |
| Known merge friction | `KNOWN_ISSUES.md` conflicts; `CURRENT_STATE.md` auto-merges (documentation only) |
| Tests (run today on `fe338ed`) | pytest 424 passed; stdlib mirror 424 OK; `mypy` clean on 28 files |
| Not re-run | the broader suite. The implementer's last report (9 failed, 1918 passed, 4 errors; 12 need `chromadb`, 1 is CTX-AUTH-001) is unverified by me. |
| Runtime callers of `core/verification` | none; the only reference outside the package and its tests is documentation |

## 2. Branch topology and merge-impact map

64 remote branches (excluding `main`); 41 carry commits not on `main`. Path scan against Verification-relevant paths (verification, runtime/workflow, events, workers, GraphRAG evidence, eval-lab, governance):

| Branch | Ahead / behind | Interaction | Note |
|---|---|---|---|
| `feature/verification-critic-evidence-phase-c` | 52 / 137 | baseline | the primary working branch |
| `eval-lab/research-and-architecture` | 10 / 169 | **POSSIBLE_INTERACTION** | carries `eval_lab/contracts/oracle.py` (`OracleDefinition`, `OracleValidation`) and ADR_LAB_06 (status PROPOSED). No import in either direction. The convergence-not-duplication position is recorded in the Phase C tracker §6; no code decision has been made. |
| `archive/fix-debt-020-completion-semantics-sep2026` | 3 / 210 | **POSSIBLE_INTERACTION** | unmerged DEBT-020 completion-gate work (`CompletionStatus`, a single evaluator) touching `core/workers/evaluator.py`, `core/workflow/runtime.py`, `core/workflow/definition.py`, `core/runtime/execution_outcome.py`. It overlaps the EvaluatorWorker fallback question. Not examined in depth; examine before changing `EvaluatorWorker`. |
| `security/freeze-reconciliation-sep2026`, `feature/capability-foundation-mission1`, `integration/capability-foundation-mission1` | 1 each | **POSSIBLE_INTERACTION** | each touches `core/workflow/runtime.py` and `definition.py`. Relevant only if Verification is ever wired into `WorkflowRuntime`. |
| `archive/pr-03-fix-adaptive-semaphore-instability-jun2026` | 1 / 548 | NO_INTERACTION in practice | touches `core/runtime/resilience.py` only |
| the other 34 unmerged branches (sandbox, CTX/auth, security, dependabot, audits) | — | NO_INTERACTION | no Verification-relevant paths changed |
| `main` | — | integration base | changed `learning/evaluator.py` (not the EvaluatorWorker), `core/runtime/resilience.py`, `core/governance/orchestration_governor.py`; none touch Verification |

No branch changes `core/verification/`, `core/events/` or `core/memory/retrieval/graphrag/evidence.py` relative to its own merge-base. `main` also has an unrelated flat `VerificationStatus` enum in `core/workspace/domain.py` (the repo's own `CURRENT_STATE.md` records it as non-authoritative); there is no class of that name in `core/verification/`.

## 3. Verification branch state

- `core/verification/`: 26 modules, 104 classes/enums, contracts only. Behavior in the package is limited to construction-time validation.
- Commit history by batch: see `CURRENT_STATE.md` (rounds `a4eddc4`…`ec3ab5e`; Batch 1 `7dd602c`; Batch 2 closed `61e00e1`; Batch 3A; Batch 3B; Batch 3C-A `4c93878`).
- Batch 3C-A: accepted Oct 5, 2026 after an independent review (qualified; F1–F7 comparison unverified).
- State documents corrected in this change: `CURRENT_STATE.md` line 155 (it said "three rounds", 205 tests, and described the crash rule backwards), `KNOWN_ISSUES.md` DEBT-018 row (205 tests, nine rounds), Phase C tracker §10 added.

## 4. Domain-model reconciliation (master prompt §100, 46 names)

Counts: {'IMPLEMENTED': 23, 'IMPLEMENTED (other name)': 4, 'PARTIAL': 6, 'NOT IMPLEMENTED': 13} | classes/enums in package: 104 | modules: 26. The "other name" and "partial" rows are my mapping; the exact-name rows were verified against the imported classes.

| §100 name | Status | Evidence / mapping |
|---|---|---|
| `VerificationRequest` | NOT IMPLEMENTED | no class of that name or equivalent |
| `VerificationTarget` | PARTIAL | `VerificationTargetSnapshot` + `VerificationTargetFingerprint` only; no target abstraction |
| `VerificationContext` | NOT IMPLEMENTED | no class of that name or equivalent |
| `VerificationObligation` | IMPLEMENTED | `obligation.py` |
| `VerificationRubric` | IMPLEMENTED (other name) | `Rubric` in `rubric.py` (my mapping, by retained semantics) |
| `VerificationCriterion` | IMPLEMENTED (other name) | `Criterion` in `rubric.py` (my mapping, by retained semantics) |
| `CriterionDependency` | IMPLEMENTED | `rubric.py` |
| `CompiledVerificationSpecification` | IMPLEMENTED | `compiled_specification.py` |
| `Claim` | IMPLEMENTED | `claim.py` |
| `ClaimComponent` | NOT IMPLEMENTED | no class of that name or equivalent |
| `ClaimDependency` | IMPLEMENTED | `claim.py` |
| `EvidenceItem` | IMPLEMENTED | `evidence.py` |
| `EvidenceBundle` | IMPLEMENTED | `evidence.py` |
| `EvidenceSource` | IMPLEMENTED | `evidence.py` |
| `EvidenceReference` | IMPLEMENTED | `evidence.py` |
| `EvidenceObservation` | IMPLEMENTED | `evidence.py` |
| `EvidenceTransformation` | IMPLEMENTED | `evidence.py` |
| `EvidenceRequirement` | IMPLEMENTED (other name) | `CriterionEvidenceRequirement` in `rubric.py` (my mapping, by retained semantics) |
| `VerificationMethod` | IMPLEMENTED | `method.py` |
| `VerificationCapability` | IMPLEMENTED | `method.py` |
| `VerificationObservation` | IMPLEMENTED (other name) | `Observation` in `observation.py` (my mapping, by retained semantics) |
| `VerificationFinding` | IMPLEMENTED | `finding.py` |
| `Critique` | IMPLEMENTED | `critique.py` |
| `CounterArgument` | IMPLEMENTED | `critique.py` |
| `Contradiction` | IMPLEMENTED | `critique.py` |
| `CriterionResult` | IMPLEMENTED | `criterion_result.py` |
| `ProcessVerificationResult` | NOT IMPLEMENTED | no class of that name or equivalent |
| `OutcomeVerificationResult` | NOT IMPLEMENTED | no class of that name or equivalent |
| `CoverageResult` | NOT IMPLEMENTED | no class of that name or equivalent |
| `VerificationResult` | IMPLEMENTED | `verdict.py` |
| `VerificationVerdict` | IMPLEMENTED | `verdict.py` |
| `VerificationConfidence` | PARTIAL | scalar `confidence: float` on `VerificationResult`; no calibration/threshold metadata |
| `VerificationEscalation` | NOT IMPLEMENTED | no class of that name or equivalent |
| `VerificationPolicy` | IMPLEMENTED | `policy.py` |
| `VerificationBudget` | NOT IMPLEMENTED | no class of that name or equivalent |
| `VerificationPlan` | PARTIAL | `InspectionPlan`/`InspectionStep` exist; the strategy-output plan does not |
| `VerificationRun` | NOT IMPLEMENTED | no class of that name or equivalent |
| `VerificationStep` | NOT IMPLEMENTED | no class of that name or equivalent |
| `VerificationReceipt` | IMPLEMENTED | `receipt.py` |
| `VerificationTrace` | NOT IMPLEMENTED | no class of that name or equivalent |
| `DecisionTrace` | NOT IMPLEMENTED | no class of that name or equivalent |
| `ReferenceQuality` | IMPLEMENTED | `reference.py` |
| `VerifierVersion` | PARTIAL | `VerificationMethod.version` string field; no separate type |
| `RubricVersion` | PARTIAL | `Rubric.version` string field; no separate type |
| `CalibrationMetadata` | NOT IMPLEMENTED | no class of that name or equivalent |
| `ReplayMetadata` | PARTIAL | `Replayability` enum on `VerificationReceipt` only |

Also implemented but not named in §100: `Oracle`, `GroundTruth`, `Assumption`, the five `*Coverage` types, `ObservationAbsence`, `VerificationConstruct`/`ConstructValidity`, `MinimumSufficientEvidence`, `CriterionAttemptState`, and the shape/target/retention/control contracts.

## 5. Semantic pipeline position (master prompt §57 chain)

Requirement → **Obligation ✔** → **Rubric/Criterion ✔** → **Claim ✔** (no `Predicate` type) → **EvidenceRequirement ✔** → **Evidence ✔** → **Observation ✔** → **VerificationMethod ✔** → **VerificationFinding ✔** → **CriterionResult ✔ (3C-A)** → AggregateVerdict ✗ (3C-B, design-blocked) → Decision ✗ (`DecisionTrace` not built).

Engine-level items in the master prompt (§28 method registry, §30 strategy engine, §32 verification loop, §46 aggregation, §47 dependency graph, §65 caching, §68 durable runs, §74 events, §81–§83 meta-evaluation and golden corpus) are not implemented; only their contracts are partly present. The prompt's §110–§112 acceptance criteria for implementation and testing are **not met**; the architecture criteria are met at the document level only.

## 5a. Result lifecycle (note for ODI-3C-B-02)

There is no lifecycle enum in the package. The existing execution-failure states are method-level (`MethodExecutionState.EXECUTION_FAILED`, `VerificationExecutionFailure` causes). Frozen v1 §11 has no `FAILED` state, v2 §31 restores a `verification.failed` event, and master §66 lists `FAILED` in the result lifecycle.

## 6. WorkflowRuntime audit (master prompt: "does the hook already exist?")

Inspected `origin/main:core/workflow/runtime.py` and `definition.py`.

| Required capability | Documented? | Implemented? | Where | Tested? |
|---|---|---|---|---|
| DAG execution | yes (`PROJECT_INSTRUCTIONS` §6.2) | **yes** | `_execute_from`, `_continue_to_successors` (diamond-merge handling) | yes (`tests/test_workflow_runtime.py`) |
| Checkpointing | yes (§6.2; DEBT-003, ADR-KERNEL-03) | **yes**, at every node boundary | `_save_checkpoint`, `get_checkpoint` | yes |
| Execution resumption | yes | **yes** | `resume()`; interrupted/failed nodes reset to PENDING; budget not restored | yes |
| Node caching | yes (§6.4: persistent, deterministic cache keys) | **partial**: completed node results are reused on `resume()` only; no persistent cache or cache keys | `resume()` | resume reuse only |
| Replay | yes (§6.2, §12.3) | **not found** in `WorkflowRuntime`; resume from a checkpoint is not a deterministic replay | — | — |
| Partial / diff-aware re-execution | yes (§6.4) | **no** | — | — |
| Node-level lifecycle hooks | yes ("observability hooks", §6.2) | **internal only**: `_emit_event` (`workflow.started`, `workflow.resumed`, `workflow.completed`); no subscription or hook API | `_emit_event` | — |

Conclusion: "existing hook plus narrow wiring" is **not proven**. A checkpoint boundary exists; the hook surface does not. Classification: DEPENDENCY, deferred.

## 7. Adjacent systems

- **EvaluatorWorker (`origin/main:core/workers/evaluator.py`): IMPLEMENTATION GAP.** `goal_completed` comes from the latest `workflow.completed` event when present; otherwise it comes from a caller-supplied `goal_completed` override (default False). There is no `INSUFFICIENT_EVIDENCE` or verdict vocabulary in the file. The recorded decision (v2/v3: measurement-only, close the fallback) is **not implemented**.
- **Event Backbone:** no `verification.*` event type on `main`. Verification lifecycle events are unbuilt.
- **GraphRAG evidence:** `core/memory/retrieval/graphrag/evidence.py` exists on `main`; `core/verification/` does not reference GraphRAG, so the "keep and wrap" adapter is not built.
- **Execution identity (DEBT-015):** still open; the contracts carry optional `execution_id`/`attempt_id` and nothing in the package generates identity.
- **Budget (DEBT-007):** still open; `VerificationBudget` is unbuilt.

## 8. Evaluation Lab overlap

`OracleDefinition` (Lab, proposed) and `Oracle` (Verification, built) share a name and concern. No code coupling exists. The Phase C tracker §6 states convergence of concepts with preserved subsystem ownership; the Lab ADRs are PROPOSED, so there is nothing yet to be incompatible with. Classification: DEPENDENCY (revisit if the Lab branch merges).

## 9. Discrepancies and classification

| # | Finding | Class |
|---|---|---|
| 1 | `CURRENT_STATE.md`/`KNOWN_ISSUES.md` described 3 rounds / 205 tests; the branch has 424 tests and Batches 1–3C-A | REPOSITORY CHANGE (documentation drift); corrected here |
| 2 | `CURRENT_STATE.md` described the crash rule backwards (`UNVERIFIABLE`-only-on-verifier-crash) | IMPLEMENTATION GAP in documentation (M4); corrected here. **This was previously held for separate authorization (M4); this change makes the correction. Drop that hunk if the correction was not intended.** |
| 3 | Tracker and handoff still call the crash-rule decision open | stale status (M8); superseded by tracker §10 |
| 4 | EvaluatorWorker caller-supplied fallback still present | IMPLEMENTATION GAP (outside the package) |
| 5 | `WorkflowRuntime` lacks a persistent node cache, replay, partial execution and hooks that `PROJECT_INSTRUCTIONS` §6 requires | IMPLEMENTATION GAP (Runtime-owned) / DEPENDENCY |
| 6 | `receipt.py` lacks the version, target, evidence and limitations bindings (master §59, v1 §14) | IMPLEMENTATION GAP (planned later batches) |
| 7 | 3C-B result types undefined; ODI-3C-B-01/02/03 and three questions open | DEFERRED WORK (design-blocked) |
| 8 | Code "mission §N" citations do not match the supplied master prompt; the Phase 0–14 prompt is unrecovered | ARCHITECTURAL source discrepancy (M9, informational) |
| 9 | The uploaded prompt is not the continuation of the truncated prompt | source discrepancy |
| 10 | Branch is 137 behind `main`; one known documentation merge conflict | DEPENDENCY |
| 11 | `MethodDisposition.INCONCLUSIVE == FindingDisposition.INCONCLUSIVE` (same string value) | known, recorded in the tracker |
| 12 | Unmerged DEBT-020 completion-gate branch overlaps the EvaluatorWorker | DEPENDENCY |
| 13 | The repo tracks 17 `.pyc` files under `tests/__pycache__` (Python 3.14) | hygiene, outside scope |

## 10. Exact remaining Verification work (contracts)

`VerificationRequest`, `VerificationContext`, `ClaimComponent`, `ProcessVerificationResult`/`OutcomeVerificationResult`/`CoverageResult` and result aggregation (3C-B), `VerificationRun`/`Step`/`Trace`, `DecisionTrace`, `EscalationRequest`/`AdjudicationRecord`, event contracts, `VerificationBudget`, `BlindVerificationContext`, `PolicyPrecedence`, calibration and replay metadata, receipt bindings. Then, beyond contracts: engine, evidence subsystem behavior, deterministic and semantic verifiers, runtime/event integration.

## 11. Deferred

V2/high-assurance items (causal visibility, attestation, temporal logic, conformal verdicts, learned false-success detection), `VerifiedState`, C-MoE integration, Evaluation Lab, Context and Memory integration.

## 12. Boundaries kept

No branch merged, rebased or force-pushed; only the Verification branch was updated, by fast-forward. No source file changed. The user-supplied token was used solely for that push. The review checkout stayed clean at `fe338ed`.

## 13. What I did not verify

The broader test suite; the full DEBT-020 archived branch; whether DEBT-020 is closed or superseded on `main`; Runtime behavior beyond the static trace above; the content of any prompt not supplied (the Phase 0–14 master implementation prompt; the Parallel Implementation Mission past §13).
