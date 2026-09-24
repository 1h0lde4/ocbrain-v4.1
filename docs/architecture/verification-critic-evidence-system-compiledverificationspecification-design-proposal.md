# CompiledVerificationSpecification — Design Proposal (Revision 2, not yet implemented)

**Date:** 22 September 2026
**Status:** PROPOSED, revised. Revision 1 named two prerequisites rather than resolving them. Both are now resolved: `VerificationRequirements` identity is implemented (`policy.py`, commit `af81965`), and criterion criticality placement is decided below, using the actual test raised against Revision 1 rather than picked arbitrarily. `VerificationStrategy.selected_methods` stays untouched, as directed. Still nothing in `compiled_specification.py` exists — this remains the checkpoint.

## Prerequisite 1: `VerificationRequirements` identity — resolved, implemented

`requirements_id: str`, auto-generated (`uuid4`), added directly to `policy.py`. Closes a gap that was already latent in existing code, not a new concern invented for this proposal: `VerificationStrategy.derived_from_requirements` has been an "opaque reference" since round 2 with nothing principled to point at. No separate version field — `VerificationRequirements` is frozen and never revised post-construction (unlike `Rubric`, which explicitly progresses through lock states because it *is* meant to be iteratively refined pre-lock); a fresh id per instance already gives identity and an implicit version marker together. Full reasoning and the two new tests are in that commit, not repeated here.

Consequence for this document: `CompiledVerificationSpecification` still embeds `VerificationRequirements` rather than referencing it by id — no registry exists yet to resolve a bare id against, so a reference alone would be unresolvable. But the embedded copy now carries `requirements_id`, so a receipt or audit record has something concrete to cite even without a registry. Embedding for practicality, explicit identity for citability — not a tradeoff between them.

## Prerequisite 2: criterion criticality — resolved, on the compiled spec, not on `Criterion`

Resolved using the actual test posed against Revision 1: **whether `criterion_id` is supposed to have invariant meaning across specifications.** Checked, not assumed, against three sources:

1. **The frozen architecture never established criterion-level criticality.** Direct search of `v1.md`, `v2-frozen.md`, `v3-final.md`, and the Sept 7 reconciliation doc for "critical"/"non-compensable" found it used exactly twice, both times about something else: "criterion-*critical evidence*" (v1 §14 — which *evidence*, within establishing one criterion, is load-bearing) and "safety-*critical claims*" (v3 Part 1 §3, `VerificationPolicy`'s own worked example — claims, driving *policy*, not a property stored on a criterion). Mission §52's "critical criteria... non-compensable" language is newer than all four documents and hasn't been reconciled against them until now.
2. **`VerificationPolicy` already models escalation this way.** Its own docstring example — "safety-critical claims always require multi-verifier composition" — is policy deciding how much rigor a given kind of claim needs, not the claim (or criterion) declaring its own importance. Criticality-for-aggregation is the same shape of decision: how much a failure matters is a judgment about *this verification effort's* assurance goal, which is exactly what `VerificationRequirements`/`VerificationPolicy`/`VerificationProfile` exist to carry, not what `Rubric`/`Criterion` exist to carry.
3. **`Rubric` is built to be reusable, not single-use.** Its lock-state progression, versioning, and "reference, don't embed" convention are exactly the infrastructure you'd want if the same rubric (a security checklist, say) gets compiled against many different targets over time — under different profiles, different stakes, potentially different criticality each time. Baking criticality into `Criterion` would mean the *same* authorization check is permanently critical (or permanently not) everywhere it's ever used, which contradicts the reusability the rest of `rubric.py` was clearly designed for.

**Decision: `criterion_id` keeps invariant meaning (what the check *is* never changes); criticality is a property of the compiled spec, not the criterion.** `CompiledVerificationSpecification.critical_criterion_ids: FrozenSet[CriterionId]` — validated as a subset of the spec's own `criterion_ids`, so a critical id that isn't actually part of this spec is a construction error, not a silent inconsistency.

No change to `rubric.py`/`Criterion` — the question was whether touching Phase-1 code was warranted, and the answer that fell out of checking is no.

## Revised shape

Only the two prerequisite-related lines changed from Revision 1; everything else (compile-time/runtime split, reference-vs-embed table for the other inputs, `CompilationFailure`) carries over unchanged:

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
        execution_identity: Optional[str]        # still provisional, Phase 13's job
        requirements: VerificationRequirements    # embedded; now carries requirements_id (prereq 1)
        policy_id: Optional[str]
        profile_name: Optional[VerificationProfileName]
        strategy: VerificationStrategy            # embedded, same reasoning as requirements --
                                                    # no registry to reference against either
        rubric_id: RubricId
        rubric_version: str
        rubric_fingerprint: str
        obligation_ids: Tuple[ObligationId, ...]
        criterion_ids: Tuple[CriterionId, ...]
        critical_criterion_ids: FrozenSet[CriterionId]   # subset of criterion_ids (prereq 2)
        inspection_plan_ids: Tuple[InspectionPlanId, ...]
        method_ids: Tuple[VerificationMethodId, ...]
        assurance_scope: str
        known_assumptions: Tuple[AssumptionId, ...]

    def compile(requirements, policy, profile, strategy, rubric, criteria,
                dependencies, obligations, inspection_plans, target,
                method_registry, critical_criterion_ids=frozenset()
                ) -> Union[CompiledVerificationSpecification, CompilationFailure]:
        ...
```

`critical_criterion_ids` is a `compile()` parameter, not derived automatically from anything — matching the decision above that criticality is asserted by whoever is compiling (informed by `VerificationPolicy`/`VerificationRequirements`), not inferred from the criteria themselves.

## No longer open

Both Revision 1 items are resolved above. Carried over from the original proposal, still open on its own terms: whether `VerificationStrategy.selected_methods: FrozenSet[str]` should become `FrozenSet[VerificationMethodId]` — untouched here, per direction, since changing an existing tested contract wasn't what either design pass was for.

## Next step

`identity.py` addition, then `compiled_specification.py`, then tests on both runners, matching the same sequence `VerificationMethod` followed. Not started.
