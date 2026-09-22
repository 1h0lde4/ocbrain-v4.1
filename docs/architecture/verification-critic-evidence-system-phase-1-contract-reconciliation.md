# Verification / Critic / Evidence System — Phase 1 Contract Reconciliation

**Date:** 22 September 2026
**Scope:** Phase 1 ("Contract reconciliation") per the September 2026 master implementation prompt. Reads every current `core/verification/` contract field-by-field, not class-name presence, per that prompt's own instruction not to preserve stale fields simply because they existed on the branch.
**What this reuses rather than redoes:** `docs/architecture/verification-critic-evidence-system-phase-c-semantic-pipeline-reconciliation.md` (7 Sept 2026) already did a full field-level read of the 11 files that existed at that point, against `v1`/`v2-frozen` in full, with no contradiction found. `core/verification/` does not exist on `main` (confirmed, Phase 0), so none of those 11 files could have changed since — the 32 commits merged in during Phase 0 are provably incapable of touching a path absent from `main`. That prior audit stands; it is not re-derived here. This document's actual scope is what that one could not have covered: the three files (`obligation.py`, `rubric.py`, `inspection.py`) and the `identity.py` additions that landed after it, on 7 Sept, as the Phase 2 implementation round (commit `34925d9`) — plus an independent direct read of `verification-critic-evidence-system-architecture-v3-final.md` itself, rather than relying solely on the prior document's reading of it.

---

## 1. Type-inventory delta since the Sept 7 table

Against the 57-row inventory in the reconciliation doc above, rows that changed status:

| # | Type | Was | Now | Where |
|---|---|---|---|---|
| 4 | `VerificationObligation` | ❌ | ✅ | `obligation.py` |
| 5 | `Rubric` | ❌ | ✅ | `rubric.py` |
| 6 | `Criterion` | ❌ | ✅ | `rubric.py` |
| 7 | `CriterionDependency` | ❌ | ✅ | `rubric.py` |
| 8 | `CriterionApplicability` | ❌ | ✅ | `rubric.py` |
| 9 | `CriterionEvidenceRequirement` | ❌ | ✅ | `rubric.py` |
| 14 | `InspectionPlan` | ❌ | ✅ | `inspection.py` |
| 15 | `InspectionStep` | ❌ | ✅ | `inspection.py` |

**8 of 57 rows moved ❌ → ✅ this round. Running total: 24 of 57 fully ✅ (plus the same 2 ◐ as before).** Row 10 (`CriterionResult`) and row 11 (`CompiledVerificationSpecification`) remain ❌ as the Sept 7 doc already anticipated — deliberately not built in this round, correctly deferred to Phase 6-7 (Run/Result/Coverage), not an omission.

## 2. Field-level fidelity check — the three new files against their own design spec

The Sept 7 document's §5 was itself the design these three files were built against. Checking implementation against that design, not just against the general architecture:

- **`obligation.py` — matches, and one respect exceeds the spec.** All four fields plus the 7-value `DerivationSource` match verbatim. The spec asked for a constructor that "does not silently accept an override that erases" the explicit-user-authority distinction; the actual implementation goes further — `carries_explicit_user_authority` is a computed property with no backing field at all, so there is no field to pass a conflicting value into in the first place. Structurally stronger than what was asked for, not just compliant with it.
- **`inspection.py` — matches exactly.** Field-for-field identical to the design (`InspectionPlan`: `plan_id`/`obligation_id`/`criterion_id`/`steps`; `InspectionStep`: `step_id`/`plan_id`/`method_reference`/`description`). `method_reference` as a plain-string forward reference follows the established `policy.py` precedent as specified. `InspectionPlan.__post_init__` requires at least one step — not explicitly demanded by the design doc, but directly satisfies master-prompt §20 ("no empty 'best effort' plan may receive a valid execution status"). No LLM-call requirement anywhere, confirmed in code, matching v1 §14's filesystem-check example.
- **`identity.py`** — `ObligationId`, `InspectionPlanId`, `InspectionStepId` all present, exactly as promised.

## 3. Two findings — deviations from spec, not confirmations

**F1 — `Rubric.construct_note` is not what the design spec asked for.** The Sept 7 design specified a forward-reference field: `construct: Optional["VerificationConstruct"]`, chosen specifically "so Rubric doesn't need a breaking migration when it lands." What was actually built is `construct_note: Optional[str] = None` — a different field name, and a plain free-text note rather than a forward-typed reference to the future `VerificationConstruct`/`ConstructValidity` (row 47, still ❌). The module's own docstring justifies this by analogy to `policy.py`'s string-placeholder pattern for `VerificationMethod` — but that precedent is for a field whose *eventual* value is itself string-like (a method name/tag); `VerificationConstruct` is architected as a structured type, not a tag, so the analogy doesn't transfer cleanly. Practical consequence: when row 47 is eventually built, `Rubric` will still need a field addition (or a rename-and-deprecate of `construct_note`) — the exact breaking-migration cost the original design chose this field specifically to avoid. Not a functional bug today; a design-intent deviation worth a decision before row 47 is built, not after.

**F2 — the `VALIDATED` lock state is not actually gated by validation.** `rubric.py` exports `validate_dependency_graph()` as a free-standing function, and separately, `Rubric.advance_to(RubricLockState.VALIDATED)` performs only a lock-state-ordering check (strict single-step, via `can_advance_to`). Nothing calls `validate_dependency_graph()` as a precondition of that transition — a caller can construct a `Rubric`, skip validation entirely, and call `advance_to(VALIDATED)` successfully. The state name asserts something the code does not enforce. This is the same category of risk master-prompt §14/§50 warn about generally (a status label reading as an answer that was never actually checked) — not yet a live bug, since nothing in this branch currently calls `advance_to` from an unvalidated state, but a structural gap that will produce exactly that bug the first time something does. Whether the fix belongs inside `advance_to()` itself (call the validator, raise on failure) or is intentionally left to the orchestration layer that will eventually call it is a design decision, not something this document resolves unilaterally.

## 4. Independent re-read of `v3-final.md`

Read directly, not solely through the Sept 7 document's summary of it. No disagreement found with that document's reading — Parts 1-5 (new architecture, reconfirmation-of-v2 table, 28-attack adversarial audit, consistency audit, phase-boundary audit) are consistent with how the Sept 7 doc used them, and nothing in Part 1's "Contract preparation — additions" list names anything the 8-row delta above doesn't already account for (that list is `shape`/`policy`/`target`/`dimension`/`retention`/`control` scope — round 2, already ✅ before this session).

## 5. What Phase 1 still has open

This pass closes the gap the Sept 7 audit couldn't have covered (the three new files) and independently re-confirms `v3-final.md`. It does not attempt the remaining ❌ rows' own field-by-field design work — `Claim`/`Assumption`/`Reference`/`Oracle` (Phase 3), `VerificationMethod`/`Dimension` proper (Phase 5), `Critique`/`VerificationFinding` (Phase 5), the five `*Coverage` types (Phase 6), `VerificationRun`/`Step`/`Trace` (Phase 7), `EscalationRequest`/`AdjudicationRecord` (Phase 9), event contracts (Phase 12), `BlindVerificationContext`, `PolicyPrecedence` — those still need their own design pass each, in the master prompt's own phase order, not compressed into this document.

**Before Phase 2/3 work resumes on this branch:** F1 and F2 above need a decision from Moncif — not blocking Phase 1 itself, but cheap to resolve now rather than after more code is built on top of `Rubric`.
