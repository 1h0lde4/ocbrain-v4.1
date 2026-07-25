# K4.2.3 — Constraint Extraction + Planner Contracts: Architecture Closure Report

## 0. Provenance Note

Unlike K4.2.1 and K4.2.2, this packet's implementation did not arrive through
the packet process described in `PROJECT_INSTRUCTIONS.md` / the Packet 01
implementation prompt. Reconstructed from repository evidence:

- `k4_2_2x_consistency_audit.md` was committed (`2122ba5`) confirming
  constraint extraction was correctly *absent* from `core/cognitive/intent.py`
  at that point — K4.2.1/K4.2.2 had not overstepped into K4.2.3 territory.
- Twenty minutes later, `core/cognitive/planner.py` appeared in a single
  generic `Add files via upload` commit (`3bbbf1e`) — the full Packet 01
  scope (`Constraint`, `PlannerRequest`, `PlannerHint`, `PlannerResult`,
  `_extract_constraints`, the `cognitive.constraints_extracted` event, and a
  105-test suite in `tests/core/cognitive/test_planner.py`), evidently
  produced by a prior session, uploaded rather than committed through the
  disciplined process this project's own instructions require.

This session's work was: audit that pre-existing implementation directly
against K4.2 §5/§11/§12/§13/§15 (not against its own docstrings' citations
of those sections), correct two verified deviations, correct three
false-positive tests, add the regression coverage those corrections needed,
write this report, and give the packet the commit trail it never had.

**Deviations found and corrected** (see §4 for detail): `PlannerResult` carried
an unauthorized 4th field (`constraints`); `_extract_constraints` was
implemented as public `extract_constraints`, contradicting §5's explicit
"remain internal."

---

## 1. Repository Audit (What Was Reused)

| Subsystem | Found | Location | Reusable | Reused by K4.2.3 | Modified |
|:---|:---|:---|:---|:---|:---|
| `Goal` dataclass | ✓ | `core/cognitive/intent.py` | Yes | Yes — `_extract_constraints(goal)` input | No |
| `EventStream` | ✓ | `core/events/event_stream.py` | Yes | Yes — `cognitive.constraints_extracted` emitted | No |
| `Constraint`/`PlannerHint`/`PlannerRequest`/`PlannerResult`/`ImpasseRecord` dataclasses | ✓ (pre-existing, this session) | `core/cognitive/planner.py` | Yes | Audited, 2 fields/names corrected | Yes — see §4 |

**Summary:** Zero subsystems modified beyond the packet's own file. No
infrastructure duplicated. `Goal` and `EventStream` consumed via existing
import paths, unchanged.

---

## 2. Architecture Compliance

| Requirement | K4.2 Section | Implementation |
|:---|:---|:---|
| `Constraint`: kind, relation, source, rationale, validated_by | §12 | `Constraint` dataclass — exact field match, verified against §12 directly |
| `PlannerHint`: kind, weight, source | §12 | `PlannerHint` dataclass — exact field match |
| `PlannerRequest`: goal_id, goal, context_view_ref, hints | §12 | `PlannerRequest` dataclass — exact field match |
| `PlannerResult`: status, execution_plan, impasse_detail — **no more** | §5, §12 (both independently give the same 3-field shape) | `PlannerResult` dataclass — corrected this session; previously carried an unauthorized `constraints` field |
| `_extract_constraints(goal)` remains internal | §5: "`_extract_constraints`/`_select_capabilities` remain internal" | Renamed from public `extract_constraints` this session |
| `cognitive.constraints_extracted` event | §11 | Emitted via `EventStream.append()`, correct payload (goal_id, constraint_count, hard_count, soft_count, sources) |
| `status: "rejected_precheck"` on contradictory hard constraints | §5, §14 | `_detect_contradictions()` + `check_precheck_rejection()` |
| Constraint sourced explicit/inferred/policy | §5, §10, §12 | `_extract_explicit_constraints()` (pattern-based), `_extract_inferred_constraints()` (confidence/compound-goal based); policy constraints correctly deferred to Plan Compilation (§5: "Policy constraints are not extracted here") |
| No `resource_id` on embedded/ephemeral types | §12 closing note | Verified for all 4 types |

---

## 3. Implementation Choices

| Choice | Rationale | Architecture impact |
|:---|:---|:---|
| `_extract_explicit_constraints` uses regex patterns (must/should/without/only/exclusively) | §5 does not mandate an extraction method, only the resulting `Constraint` shape and `source` provenance | None — replaceable heuristic, consistent with the Input Normalization precedent (§2: deterministic, auditable code at seam crossings) |
| `_detect_contradictions` only catches requirement/negation pairs with overlapping content words | §5: "a deliberately conservative check — only clear, provable contradictions are detected. Subtler conflicts are deferred to full Planner decomposition (Packet 03)" | None — explicitly scoped this way by §5 itself |
| `ConstraintKind`/`ConstraintRelation`/`ConstraintSource`/`HintSource`/`PlannerStatus` as string-constant helper classes | §12 specifies literal string unions (e.g. `"hard"\|"soft"`); named constants avoid magic strings without adding fields | None — values match §12 exactly |

---

## 4. Deviations Found and Corrected

| Deviation | Evidence | Correction | Files touched |
|:---|:---|:---|:---|
| `PlannerResult.constraints` — unauthorized 4th field | §5 (lines 165–172) and §12 (lines 351–353) both independently give the same 3-field shape; the pre-existing test's own docstring said "status, execution_plan, impasse_detail" yet its body asserted `hasattr(r, "constraints")` — self-contradicting | Removed the field; removed the now-invalid `constraints=constraints` kwarg from `check_precheck_rejection`; replaced the self-contradicting assertion with an exact-field-set regression guard | `core/cognitive/planner.py`, `tests/core/cognitive/test_planner.py` |
| `extract_constraints` implemented as public | §5: "`_extract_constraints`/`_select_capabilities` remain internal" (unambiguous) | Renamed to `_extract_constraints` (1 definition, 10 test call sites, mechanical) | `core/cognitive/planner.py`, `tests/core/cognitive/test_planner.py` |
| 3 false-positive "architecture compliance" tests | `test_no_capability_imports`, `test_no_memory_writes`, `test_no_governance_invocation` searched raw file text (including docstrings) for forbidden words — failed because the module's own docstring explains what it does *not* do, using those words to disclaim them | Added `_real_code_identifiers()`: parses the module with `ast`, checks only real `Import`/`Name`/`Attribute` nodes — excludes docstrings/comments by construction. Preserves the original protective intent while eliminating the false positive (and incidentally fixes a second latent bug: the old substring check also matched inside longer words, e.g. "invoke" inside "invokes") | `tests/core/cognitive/test_planner.py` |

No other files required changes. No production behavior changed for any
already-correct code path — `_extract_explicit_constraints`,
`_extract_inferred_constraints`, `_detect_contradictions`, and
`build_planner_request` are untouched.

---

## 5. Untouched Future Features (K4.2.4+)

| Feature | Milestone | Status |
|:---|:---|:---|
| Capability discovery / `CapabilityRequest` resolution | K4.2.4 | Not implemented, not imported |
| `_select_capabilities` | K4.2.4 | Not implemented |
| Planner completion / `plan()` / HTN decomposition | K4.2.5 | Not implemented |
| `ClarificationPolicy` | K4.2.5 | Not implemented |
| Plan Compilation / `WorkflowDefinition` | K4.3 | Not implemented, not imported |
| Policy-sourced constraints (GovernanceKernel-derived) | K4 §15 (Plan Compilation) | Explicitly deferred — `_extract_constraints` only produces explicit/inferred |
| Shared `ValidationGate` / Learning wiring | K4.2.6 | Not implemented |
| User Cognitive Model | K4.2.7 | Not implemented |

---

## 6. Regression Results

```
tests/core/cognitive/test_planner.py + test_intent.py — 121 passed, 0 failed
Full repo suite (excl. 4 files requiring chromadb, unrelated to this packet,
unavailable in this sandbox) — 811 passed, 0 failed
```

### Test Coverage Checklist (from packet completion criteria)

| Requirement | Test | Status |
|:---|:---|:---|
| Constraint/PlannerRequest/PlannerHint/PlannerResult implemented per §12 | `TestConstraintDataclass`, `TestPlannerHintDataclass`, `TestPlannerRequestDataclass`, `TestPlannerResultDataclass` | ✅ |
| `_extract_constraints(goal)` → well-formed `List[Constraint]` | `TestExtractConstraints::test_basic_extraction` + 9 more | ✅ |
| `cognitive.constraints_extracted` emitted | `TestExtractConstraints::test_event_emitted`, `test_event_payload_counts_correct` | ✅ |
| Contradictory hard constraints → `rejected_precheck` | `TestDetectContradictions::test_contradictory_constraints_detected` | ✅ |
| Non-contradictory / empty / soft-only constraints do not reject | `test_no_contradiction_passes`, `test_empty_constraints_passes`, `test_soft_contradictions_not_rejected` | ✅ |
| No capability selection, memory writes, or governance invocation | `TestArchitectureCompliance` (3 tests, corrected this session) | ✅ |
| No `resource_id` on embedded/ephemeral types | `TestArchitectureCompliance` (4 tests) | ✅ |

---

## 7. Final Self-Audit

| Constraint | Verified |
|:---|:---|
| No architecture invented | ✅ — every type/field/event cites K4.2 §5/§11/§12 directly (re-read this session, not taken from docstring citations alone) |
| No contracts invented | ✅ — `Constraint`, `PlannerHint`, `PlannerRequest` matched §12 exactly on first read; `PlannerResult` corrected to match |
| No events invented | ✅ — `cognitive.constraints_extracted` is §11's existing name |
| No capability selection | ✅ — `AdapterRuntime`/`CapabilityType`/`.invoke(` absent from real code (AST-verified, not substring-verified) |
| No memory writes | ✅ — `UnifiedMemory`/`.write(` absent from real code |
| No governance invocation | ✅ — `GovernanceKernel`/`evaluate_action` absent from real code |
| No duplicated infrastructure | ✅ — `Goal`, `EventStream` reused via existing imports |
| Public interfaces unchanged | ✅ — `interpret()`, `plan()`, `compile()`, `EventStream.append()` untouched |
| Full regression suite green | ✅ — 811 passed, 0 failed (excl. pre-existing chromadb-gated files) |

---

## 8. Files Changed

| File | Change |
|:---|:---|
| `core/cognitive/planner.py` | Removed unauthorized `PlannerResult.constraints` field and its one call site; renamed `extract_constraints` → `_extract_constraints` per §5 |
| `tests/core/cognitive/test_planner.py` | Updated import and 10 call sites for the rename; replaced a self-contradicting field assertion with an exact-field-set regression guard; added `_real_code_identifiers()` and rewired 3 tests to use it instead of raw-text substring search |
| `docs/architecture/k4_2_3_completion_report.md` | New — this report |
| `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md` | Synced to reflect K4.2.1–K4.2.3 completion (see repository root for these) |

---

## 9. Completion Decision

**K4.2.3 COMPLETE — Ready for K4.2.4.** Both verified deviations corrected,
both confirmed against §5 and §12 independently rather than against either
document alone. Full regression suite green. Commit trail now exists for a
packet that previously had none.

---

## Addendum — Second Independent Review (July 25, 2026)

A second, independent Post-Implementation Review (per the request that
produced this report's own review process) was performed against this
same commit, in parallel, before this addendum was written. It found one
additional real defect this report did not catch, and confirmed the two
deviations above independently by the same method (reading §5/§12
directly, then checking real code — not this report's claims).

**Defect found:** `_extract_explicit_constraints()`'s pattern list checks
`must\s+not` before plain `must` (and `should\s+not` before `should`) in
priority order, but did not skip a later pattern's match when it fell
inside an earlier, more specific match's span. The prior deduplication
was by *rendered context string*, not by character span, and the two
patterns' context windows only produce identical strings when both get
clamped to end-of-string by `min(len(text), match.end() + 60)` — true for
short constraint text, false once ~60+ characters follow the match.

**Consequence:** `_extract_explicit_constraints("You must not use "
"JavaScript for this task, since the team standard requires Python for "
"all new automation scripts going forward.")` produced two constraints
(a correct `negation_constraint` and a spurious `requirement_constraint`
over the same words) instead of one, and `_detect_contradictions()`
correctly found overlapping content words between them — correctly, given
its own logic, but incorrectly overall, since there was only ever one
constraint. Per §5, `check_precheck_rejection()` uses exactly this signal
to reject a Goal as unsatisfiable before Planner attempts it — so an
entirely ordinary, satisfiable request phrased as "must not X, because Y"
with a normal-length trailing clause would have been wrongly rejected.

**Why neither this report's own review nor the original implementation
caught it:** every existing `TestPrecheckRejection` test constructs
`Constraint` objects directly and asserts on `_detect_contradictions()`
in isolation — none of them exercise real text through
`_extract_explicit_constraints()` first. The two functions were each
individually well-tested; the seam between them was not.

**Fix:** track claimed character spans across the whole pattern loop
(not per-pattern) and skip any match whose span overlaps one already
claimed by an earlier, more specific pattern, rather than deduplicating
by the rendered context string. Verified against: the false-positive case
above (now 1 constraint, no contradiction); the analogous `should not`
case; a genuine cross-sentence contradiction (`"...must use encryption... `
`however... must not use encryption..."` — still correctly detected); and
a sentence combining three genuinely distinct constraint types (`must` /
`only` / `without` — still all three extracted, not over-suppressed).

**Files touched by this addendum's fix:** `core/cognitive/planner.py`
(`_extract_explicit_constraints` only — no other function changed),
`tests/core/cognitive/test_planner.py` (`TestExtractionContradictionIntegration`,
4 new tests exercising the extraction → detection seam directly with
realistic text; `_detect_contradictions`/`_extract_explicit_constraints`
added to the test file's imports).

**Verification:** `test_planner.py` 54/54 passing (50 from the review
above + 4 new). Full repository regression: 815/815 passing.

**Status: still COMPLETE.** This addendum does not change the completion
decision above — it corrects one additional implementation-level defect
within Packet 01's own file ownership, found by the same class of review
this report itself performed, using the same method (verify against
architecture and real code, not against a prior report's claims).
