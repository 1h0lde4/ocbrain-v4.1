# CompiledVerificationSpecification — Design Proposal (not yet implemented)

**Date:** 22 September 2026
**Status:** PROPOSED. Same discipline as the VerificationMethod checkpoint: design first, reviewed if needed, implemented only after. Nothing in `core/verification/` changes as a result of this document.
**Grounding:** mission Sec10 (the field list this type must satisfy) and Sec9 (the requirement-gap gate compilation exists to enforce), read directly against every existing type it would reference: `policy.py` (`VerificationRequirements`/`Policy`/`Strategy`/`Profile`, read in full for this), `rubric.py` (`Rubric`/`Criterion`/`CriterionDependency`/`CriterionApplicability`), `obligation.py`, `inspection.py`, `method.py` (this session's own prior work), `target.py`.

## What "compile" actually does

A pure function, not a stored-and-mutated object under construction: `compile(requirements, policy, profile, rubric, criteria, dependencies, obligations, inspection_plans, target, method_registry) -> Union[CompiledVerificationSpecification, CompilationFailure]`. Mission Sec10's own line is the test: "A specification that cannot be compiled into a satisfiable verification plan is not a valid executable verification. It is an unresolved specification" — so compilation either succeeds with a complete, internally-consistent artifact, or it fails explicitly with named reasons. No partial/degraded compiled spec; that is exactly the "unresolved specification" case Sec9 requires representing honestly rather than smoothing over.

## Reference vs. embed, resolved per type, not by one blanket rule

This module's own established convention is "reference, don't embed" (evidence.py's provenance chain, `Rubric.criteria: Tuple[CriterionId, ...]`), but applying it required actually checking whether each referenced type currently has an identity to reference — not all of them do:

| Input | Has an ID today? | Compiled spec holds |
|---|---|---|
| `Rubric`, `Criterion`, `CriterionDependency` | yes (`rubric_id`, `criterion_id`) | reference (id + the rubric's own `version`/`fingerprint`, already on `Rubric`) |
| `VerificationObligation` | yes (`obligation_id`) | reference |
| `InspectionPlan`/`InspectionStep` | yes | reference |
| `VerificationMethod` | yes (`method_id`, built this session) | reference |
| `VerificationTargetSnapshot` | yes (`target_id` + `fingerprint`) | reference |
| `VerificationRequirements` | **no** — no id/version field exists on it today | embedded directly (it's small, and there is nothing to reference yet) |
| `VerificationPolicy` | yes (`policy_id`) | reference |
| `VerificationProfile` | has a `name` (an enum, not an opaque id) | reference by `name` |

`VerificationRequirements` having no identity is a real gap, not a choice made here — mission Sec66 requires "no mixed-version VerificationRun," which presumes requirements have *some* stable identity to pin a run against. Embedding sidesteps needing one today; it does not fix the actual gap. Flagged in "Open questions," not silently patched by adding an id field to `policy.py` as a side effect of this document.

## Compilation checks

Extends the admissibility check the VerificationMethod proposal already sketched (Revision 2 Sec2) from "one step" to "the whole spec":

```
STATIC (compile-time):
    every InspectionStep.method_reference resolves to a registered
        VerificationMethod (already specified, VerificationMethod Rev.2)
    every required VerificationCapability is registered
        (not that its adapters are currently healthy -- runtime's job)
    every Criterion's applicability/evidence_requirement is internally
        consistent (rubric.py's own validate_dependency_graph(), reused
        here, not reimplemented)
    every Obligation's rubric_id resolves to the Rubric being compiled
    Rubric.lock_state is COMPILED or LOCKED (DRAFT/VALIDATED cannot compile --
        matches this session's own Phase 1 fix: VALIDATED itself now requires
        real validation, and COMPILED is the next state up from it)
    VerificationPolicy's constraints (minimum_shape_for, forbidden_methods)
        are not violated by what Requirements/Strategy selected
    target kind, if declared on any selected VerificationMethod, is
        compatible with the actual target (provisional, same caveat as
        VerificationMethod Rev.2 Sec9 -- no target-kind taxonomy exists yet)

RESULT ON FAILURE:
    CompilationFailure(reasons: Tuple[str, ...]) -- named, specific,
    never a bare False. Each reason names which check failed and for
    which id, matching mission Sec9's requirement-gap vocabulary
    (missing / ambiguous / unrepresentable / incorrectly modeled).
```

## Critical/non-compensable criteria — a real gap, not resolved here

Mission Sec52 requires non-compensable criteria (a critical check whose failure can't be averaged away). Checked directly: **`Criterion` has no criticality field today** (`criterion_id`, `rubric_id`, `description`, `applicability`, `evidence_requirement` — confirmed by direct re-read, nothing else). This isn't something `CompiledVerificationSpecification` can supply on its own two ways, each with a real tradeoff:

- Add a field to `Criterion` itself (`rubric.py`) — criticality travels with the criterion's own definition, which is arguably where it belongs, but it's a change to already-tested, already-Phase-1-reconciled code, not something to fold into this proposal as a side effect.
- Give `CompiledVerificationSpecification` its own `critical_criterion_ids: FrozenSet[CriterionId]`, decided at compile time rather than at criterion-authoring time — no change to `rubric.py`, but the same criterion could then be "critical" in one compiled spec and not another, which may or may not be the intended semantics.

Not resolving this here on purpose — it's a decision about `Criterion`'s own design, not about compilation, and deserves the same explicit call-out VerificationMethod's `VerificationCapability` gap got rather than a default picked quietly.

## Proposed shape

```
identity.py addition:
    CompiledVerificationSpecificationId

compiled_specification.py (new):
    CompilationFailure (dataclass):
        reasons: Tuple[str, ...]

    CompiledVerificationSpecification (frozen dataclass):
        spec_id: CompiledVerificationSpecificationId
        compiled_at: datetime
        target_id: TargetId
        target_fingerprint: VerificationTargetFingerprint
        execution_identity: Optional[str]       # provisional -- no
            # execution/attempt-id binding exists anywhere in
            # core/verification/ yet (confirmed absent from every type
            # built this session); Phase 13's job to wire for real
        requirements: VerificationRequirements   # embedded -- see table above
        policy_id: Optional[str]
        profile_name: Optional[VerificationProfileName]
        rubric_id: RubricId
        rubric_version: str
        rubric_fingerprint: str
        obligation_ids: Tuple[ObligationId, ...]
        criterion_ids: Tuple[CriterionId, ...]
        inspection_plan_ids: Tuple[InspectionPlanId, ...]
        method_ids: Tuple[VerificationMethodId, ...]
        assurance_scope: str                     # mission Sec7.4: assurance is
            # always scoped -- free text for now, same "not enough real
            # examples yet" reasoning VerificationMethod Rev.2 gave payload
        known_assumptions: Tuple[AssumptionId, ...]   # assumption.py, this session

    def compile(requirements, policy, profile, rubric, criteria,
                dependencies, obligations, inspection_plans, target,
                method_registry) -> Union[CompiledVerificationSpecification,
                                           CompilationFailure]:
        ...
```

`critical_criterion_ids` deliberately not in the sketch above until the open question is settled.

## Also found: a stale comment, fixed separately from this design

`policy.py`'s own docstrings say `required_dimensions`/`selected_methods` are placeholders because "`VerificationMethod` not yet built in code" (lines 58-61, 111) -- no longer true as of this session's earlier work. This is a documentation fix, not a design decision, so it's committed on its own rather than bundled into this proposal's outcome.

## Open questions (not decided here)

1. Where does criticality/non-compensability live -- `Criterion` itself, or the compiled spec? (above)
2. `VerificationRequirements` has no stable identity -- embed forever, or does `policy.py` eventually need an id/version field? Embedding works today; doesn't resolve mission Sec66 in general.
3. Should `VerificationStrategy.selected_methods: FrozenSet[str]` (plain strings, predates `VerificationMethod`) become `FrozenSet[VerificationMethodId]` now that real ids exist? Out of scope for this document -- it's an existing, already-tested contract from round 2, not something to change as a side effect of designing something else.

## Next step

If the shape above (minus the two open items) is confirmed, implementation is `identity.py` + `compiled_specification.py` + the `compile()` function + tests on both runners. Not started.
