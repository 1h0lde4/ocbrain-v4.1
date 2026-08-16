# K4.2-H1 — Contract Evolution Foundation — Completion Report

**Date:** August 16, 2026
**Packet:** K4.2-H1 (Decisions D1, D2, D4, D5, D6, D8, D9)
**Status:** COMPLETE

---

## 0. Provenance of this packet

Two independent lineages of prior work fed into this packet, discovered and reconciled at the start of this session rather than either being blindly executed or discarded:

1. `docs/architecture/K4_2_CONTRACT_EVOLUTION_AND_DIAGNOSTIC_ARCHITECTURE_SPECIFICATION.md` (1203 lines) — a live-git-audited, evidence-tagged spec, explicitly framed as "not self-executing... subject to Moncif's review."
2. `docs/architecture/implementation_plan - K42 v1-0 FINAL PRE-FREEZE ARCHITECTURE SPECIFICATION frozen.md` (840 lines, titled "K4.2 v1.0 — FINAL IMPLEMENTATION-ALIGNMENT CORRECTION PASS") — produced from a static extracted-archive snapshot (no `.git` access), self-described as `READY TO FREEZE`.

Both were committed to the repository in the same upload (commit `3cb8b7d`, "Add files via upload") but do not cross-reference each other. Before any implementation began, every specific line-number and structural claim in the second document's H1 implementation spec (§10) was independently verified against the live repository — not taken on either document's word. All checked claims were confirmed exact (e.g. `discover_capabilities()` at `planner.py:639`, `compile()` at `compiler.py:257`, `_attempt_retry()` at `supervisor.py:248`) or off by an explainable one-line anchor-point convention, not an error. One internal inconsistency was found in the frozen document's own illustrative pseudocode (see §5 below) and corrected against its stated intent rather than copied mechanically, per that document's own "implementation guidance, not rigid patch instructions" framing.

The one substantive process disagreement between the two documents — whether H1 requires review before implementation — was resolved by direct instruction, not silently: the `[RECONCILE-PENDING]` marker handling (D6) was explicitly overridden from "remove" to "preserve, with explicit deferred status," and H1 proceeded only after explicit sign-off on scope.

---

## 1. Architecture Approval

**APPROVED** for the seven H1-scoped decisions (D1, D2, D4, D5, D6, D8, D9). No contradiction was found that blocks implementation. D6 required explicit direction on marker handling (received) rather than defaulting to the specification's own suggestion.

## 2. H1 Implementation Status

**COMPLETE.**

## 3. Files Changed

**Core (9 files):**
- `core/capabilities/capability.py` — `CapabilityContract.is_general_purpose`
- `core/cognitive/recovery.py` — **new** — `OperationRecoveryBudget`
- `core/cognitive/intent.py` — `RawRequest` frozen; `CognitiveArtifact`/`Intent`/`Goal` gain `caused_by`; K42-001 fix; `trace_id` in three events
- `core/cognitive/planner.py` — `CapabilityMatch`, `CapabilityDiscoveryResult`; `discover_capabilities()` rewrite (K42-002 fix); `_decompose()`/`_estimate_confidence()` updated for the new type; `ExecutionPlan.caused_by`; `operation_id`/`trace_id`/`stage_tag` in `plan()` and its sub-stage events; `PlannerResult.operation_id`
- `core/cognitive/compiler.py` — `operation_id`/`trace_id` in `compile()`'s two events
- `core/cognitive/learning.py` — `CognitiveDecision.caused_by`, `LearningRecord.caused_by`; `ContentDomain` D6 deferral note
- `core/orchestrator.py` — `max_recovery_attempts` constructor param; `OperationRecoveryBudget` creation; Planner re-plan loop (impasse-only); budget threaded to `SupervisorWorker`; `cognitive.planner_impasse_terminal` emission
- `core/workers/supervisor.py` — `_attempt_retry()` budget-aware, legacy path preserved unchanged when no budget supplied
- `main.py` — `LLM_COMPLETION` registration gains `is_general_purpose=True`; `max_recovery_attempts` read from config and threaded to `Orchestrator`

**Config (1 file):** `config/settings.toml` — `[runtime] max_recovery_attempts = 3`

**Documentation (4 files):**
- `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` — §6 marker preserved + deferred-status note (D6)
- `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md` (new DEBT-011) — synced

**ADRs (7 new files):** `docs/architecture/decisions/ADR_K4_2_H_0{1,2,4,5,6,8,9}_*.md`, plus `ADR_INDEX.md` updated.

**Tests (7 files, 44 new tests):**
- `tests/core/cognitive/test_recovery.py` — **new**, 9 tests
- `tests/test_orchestrator_recovery.py` — **new**, 7 tests (includes the mandatory H1-G5 integration test)
- `tests/test_supervisor_worker.py` — +4 tests
- `tests/core/cognitive/test_intent.py` — +10 tests, 1 corrected assertion (`test_no_ontology_degrades_gracefully` had been asserting the K42-001 bug as correct)
- `tests/core/cognitive/test_planner.py` — +9 tests, 11 pre-existing tests updated for the `CapabilityDiscoveryResult` return type (none weakened — each still asserts the same property against the new shape)
- `tests/core/cognitive/test_compiler.py` — +2 tests
- `tests/core/cognitive/test_learning.py` — +5 tests

## 4. Contracts Changed

`CapabilityContract` (+`is_general_purpose`), `CognitiveArtifact`/`Intent`/`Goal`/`ExecutionPlan`/`CognitiveDecision`/`LearningRecord` (+`caused_by`), `RawRequest` (frozen), `PlannerResult` (+`operation_id`), `discover_capabilities()` return type (`List[CapabilityContract]` → `CapabilityDiscoveryResult`). New: `CapabilityMatch`, `CapabilityDiscoveryResult`, `OperationRecoveryBudget`.

## 5. Invariants Added / Corrections Made to the Specification

- **Recovery Invariant** (D5): one `OperationRecoveryBudget` per operation; Planner and Supervisor consume the same instance; no hidden retry universe.
- **REJECTED_PRECHECK is never retried.** The frozen specification's own illustrative re-plan loop did not distinguish `IMPASSE` from `REJECTED_PRECHECK`. `_extract_constraints()`/`check_precheck_rejection()` are fully deterministic (no LLM call) — retrying a precheck rejection is provably guaranteed to reproduce the identical result, wasting the shared budget on an outcome that can never change. Implemented so only `IMPASSE` enters the loop.
- **General-purpose fallback bypasses `min_score` at the inclusion stage, not just in ranking.** The frozen specification's own illustrative discovery-flow snippet gated *all* candidates — general-purpose included — behind `if score >= min_score`, which would have left K42-002 unfixed for exactly the realistic-phrasing/zero-score scenario it exists to fix (also silently referenced two undefined helper functions, `_classify_tier`/`_apply_specificity_dominance`, and an unspecified `threshold`). Implemented per D2's stated prose intent instead of the snippet literally, per the specification's own "implementation guidance, not rigid patch instructions" framing — documented explicitly in `discover_capabilities()`'s docstring and in ADR-K4.2-H-02.
- **`[RECONCILE-PENDING]` preserved, not removed** (D6) — explicit override of the specification's own suggestion, per direction.

## 6. Tests Added

44 new tests (listed in §3). Full list available via `git diff --stat` on the `tests/` paths above.

## 7. Test Results

```
$ python3 -m pytest tests/ -q --tb=no
34 failed, 1156 passed, 1 warning in 97.64s
```

34 failures are the pre-existing, environment-only set (sandbox has no `huggingface.co` access) — confirmed by exact set comparison (`comm -13`/`comm -23`) against a true baseline captured by stashing all H1 changes and re-running, not by count-matching alone. Zero new failures, zero pre-existing failures resolved or changed. 1112 pre-existing passing tests + 44 new = 1156.

## 8. Recovery Verification

`tests/test_orchestrator_recovery.py::TestSharedRecoveryBudget::test_same_budget_instance_reaches_supervisor_after_replan_attempts` forces two Planner re-plan consumptions via a mocked `plan()` sequence (`IMPASSE`, `IMPASSE`, `READY_FOR_COMPILATION`), then a compilation rejection, and asserts the `OperationRecoveryBudget` object that reaches `SupervisorWorker` shows `internal_recovery_used == 2` — a value only possible if it is the *same instance* Orchestrator's re-plan loop consumed, not two independently-constructed budgets with matching configuration. Bounded termination independently verified (`test_budget_exhaustion_terminates_replan_loop`: exactly `1 + max_recovery_attempts` `plan()` calls, never more).

## 9. Capability Verification

`tests/core/cognitive/test_planner.py::TestGeneralPurposeFallback::test_general_purpose_bypasses_min_score` reproduces the exact K42-002 scenario (realistic non-overlapping phrasing against the real `LLM_COMPLETION` contract, `min_score=0.01`) and confirms it is now returned as the top match with `evidence["general_fallback"] == True`. `test_specificity_dominance_ranks_specific_above_general` confirms a genuine lexical match still outranks the fallback. `test_fallback_mechanism_is_not_hard_coded_to_one_name` proves the mechanism is generic (an arbitrarily-named capability, never seen elsewhere in the codebase, gets the identical fallback treatment).

## 10. Provenance Verification

`tests/core/cognitive/test_intent.py::TestCausalProvenance` and `tests/core/cognitive/test_planner.py::test_caused_by_independent_of_derived_from` confirm `derived_from` and `caused_by` can be populated simultaneously and independently, and that `caused_by` defaults to `None`.

## 11. Trace Verification

`test_each_plan_call_generates_a_fresh_operation_id`, `test_each_compile_call_generates_a_fresh_operation_id` (same `trace_id`, different `operation_id` per call); `test_event_includes_trace_and_stage_tag` (same `operation_id`, different `stage_tag` — `capability_discovery:{subgoal_ref}` — across repeated discovery calls within one `_decompose()` pass). The re-plan-retains-trace-but-changes-operation_id criterion is proven at the Orchestrator level, where the loop actually lives, via `PlannerResult.operation_id` surfaced on the terminal `cognitive.planner_impasse_terminal` event.

## 12. Remaining Issues (genuine, not exhaustive busywork)

1. **No live trigger for Supervisor's worker-retry recovery action.** `core/orchestrator.py`'s K4.2 branch never checks `wf_result.success` after `WorkflowRuntime.execute()` — there is currently no code path that invokes `SupervisorWorker` with a `failed_worker_result` after a workflow execution failure. The budget-sharing mechanism is correct and tested at the contract level; the production trigger for the *second* of the two v1.0 recovery actions doesn't exist yet. Not in H1's exact-modules table; flagged rather than built, since designing it requires decisions (how `retry_worker_type`/`retry_parameters` get constructed) not specified anywhere.
2. **`ContentDomain`/K4.1-L reconciliation remains genuinely open** (D6, by design — see `KNOWN_ISSUES.md` DEBT-011).
3. **`IMPLEMENTATION_TRACKER.md`**, referenced by both source documents, does not exist in this repository (only `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`/`KNOWN_ISSUES.md`/`PROJECT_INDEX.md` do). Documentation sync in this packet targeted the files that actually exist; noted here rather than silently working around it.
4. Two of the H1 stop-condition-adjacent decisions in this report (§5) required deviating from the frozen specification's own example code to satisfy its *stated* intent. Both are flagged above and in their respective ADRs, not buried in a diff.

## 13. H1 Freeze Recommendation

**READY FOR H1 FREEZE.**

All eleven acceptance-gate items (H1-G1 through H1-G11) verified: Goal semantic preservation (H1-G1); `CapabilityDiscoveryResult` canonical and Planner-consumed (H1-G2); specificity/general ranking (H1-G3); budget counts and exhausts correctly (H1-G4); same instance shared by Planner and Supervisor, proven by integration test (H1-G5); `trace_id`/`operation_id`/`stage_tag` semantics correct (H1-G6); `derived_from`/`caused_by` semantically separate (H1-G7); Learning reconciliation deliberately, explicitly incomplete rather than silently resolved (H1-G8); all pre-existing tests remain green by exact set comparison (H1-G9); H1-relevant architecture invariants pass — no K5 boundary crossed, no new public entrypoint, no Kernel modification, no forbidden practice introduced, confirmed by direct diff audit (H1-G10); `CapabilityMatch.evidence` extensible without changing its semantic contract (H1-G11).
