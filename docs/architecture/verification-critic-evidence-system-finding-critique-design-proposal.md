# VerificationFinding / Critique / CounterArgument / Contradiction — Design Proposal (not yet implemented)

**Date:** 22 September 2026
**Status:** PROPOSED. Same discipline as the two prior checkpoints (`VerificationMethod`, `CompiledVerificationSpecification`): design first, nothing in `core/verification/` changes until this is confirmed.
**Scope correction made while researching this:** these four are not a new architectural direction — they are rows 25-28 of the original 57-row type inventory (`docs/architecture/verification-critic-evidence-system-phase-c-semantic-pipeline-reconciliation.md`), already scoped to "Phase 5" there. A fifth type, `VerificationDimension` itself, turns out to be a genuine prerequisite this document also resolves — `dimension.py`'s own docstring says outright that it "is not yet built in code," and `VerificationFinding` cannot carry a dimension classification without it existing.

**Grounding:** `v1.md` §18 (the Critique/disconfirmation-engine design, unchanged in `v2-frozen.md` §16 except one addition) and §42 (the full type-ordering list); `v2-frozen.md` §11 (the Method/Dimension independence rule this whole layer exists to implement); `dimension.py`'s own docstring (confirms `VerificationDimension` is the missing prerequisite, not an assumption).

---

## 1. `VerificationDimension` — the prerequisite `dimension.py` names but doesn't build

Mission §16's own list: process, outcome, correctness, completeness, groundedness, compliance, safety, state, transition, invariant. Unlike `VerificationMethodType` (plain string constants, deliberately open-ended — new verification *techniques* can always be invented), this is a **closed `Enum`**: mission §16 gives a specific, finite list, not an extensible category, and `dimension.py`'s existing `StateVerification`/`TransitionVerification`/`InvariantVerification` are explicitly framed as "precision subtypes" of three of these ten values, not independent concepts — they only make sense once the ten-value parent exists to attach to.

```
VerificationDimension(str, Enum):
    PROCESS, OUTCOME, CORRECTNESS, COMPLETENESS, GROUNDEDNESS,
    COMPLIANCE, SAFETY, STATE, TRANSITION, INVARIANT
```

## 2. `VerificationFinding` — method and dimension as two independent classifications

`v2-frozen.md` §11, verbatim reasoning: "`DeterministicVerifier` is a method. `ProcessVerification` is a dimension... a single dimension can be checked by multiple methods, and a single method can serve multiple dimensions. Phase C contracts should model these as two independent classifications on a `VerificationFinding`, not a nested hierarchy." That sentence is the entire design for this field pair — not reinterpreted here, just implemented:

```
VerificationFinding(frozen):
    finding_id: VerificationFindingId
    criterion_id: CriterionId
    method_id: VerificationMethodId        # the "method" axis
    dimension: VerificationDimension       # the "dimension" axis -- independent, not nested
    disposition: FindingDisposition        # SUPPORTS / REFUTES / INCONCLUSIVE
    observation_ids: Tuple[ObservationId, ...]
```

`disposition` is deliberately new, not reused from `method.py`'s `MethodDisposition` (CONCLUSIVE/INCONCLUSIVE/INSUFFICIENT), because they answer different questions and this session already made the mistake of conflating them once. `MethodDisposition` says whether the method's *execution* was clean; `FindingDisposition` says whether the *result*, once produced, supports or refutes the criterion. This is exactly the field the `VerificationMethod` Revision 2 review correctly ejected from `MethodResult` ("support/refute is derived later from the produced observation/evidence against the criterion") — `VerificationFinding` is that "later."

`observation_ids` references `observation.py`'s `Observation` (built this session) directly, not `EvidenceId` — consistent with `method.py`'s own `VerificationMethodResult.observations`, and consistent with Observation->Evidence promotion staying a distinct, later step (Phase 4) that this layer doesn't collapse into itself either.

## 3. `Critique` — the disconfirmation engine's output, taxonomy taken verbatim

`v1.md` §18 (unchanged into v2 except one addition already covered by `evidence.py`'s existing circular-evidence check): "A disconfirmation engine, structurally separate from both the generator and the verdict-maker... A critique is an input to verification, not a verdict — `Critique != VerificationResult != Verdict`, three different objects." Nine named outputs, taken as the literal enum, not re-derived:

```
CritiqueFindingType(str, Enum):
    UNSUPPORTED_CLAIM, MISSING_EVIDENCE, HIDDEN_ASSUMPTION, LOGIC_GAP,
    CONTRADICTION, SCOPE_VIOLATION, FALSE_COMPLETION, WRONG_ATTRIBUTION,
    POSSIBLE_COUNTEREXAMPLE
```

Three of the nine already have (or, per this document, will have) a dedicated structured type elsewhere in this codebase rather than being just a label: `HIDDEN_ASSUMPTION` -> `assumption.py`'s `Assumption` (already built, Phase 2); `CONTRADICTION` -> `Contradiction` (below); `POSSIBLE_COUNTEREXAMPLE` -> `CounterArgument` (below). The other six (unsupported_claim, missing_evidence, logic_gap, scope_violation, false_completion, wrong_attribution) get no dedicated type here — nothing in `v1`/`v2` calls for one, and inventing structured sub-objects for six labels with no cited design would be exactly the kind of unrequested scope this project's own review process keeps catching.

```
Critique(frozen):
    critique_id: CritiqueId
    finding_type: CritiqueFindingType
    target_claim_id: ClaimId
    description: str
    contradiction_id: Optional[ContradictionId] = None      # required iff finding_type == CONTRADICTION
    counter_argument_id: Optional[CounterArgumentId] = None  # required iff finding_type == POSSIBLE_COUNTEREXAMPLE
    hidden_assumption_id: Optional[AssumptionId] = None      # required iff finding_type == HIDDEN_ASSUMPTION
```

Each optional reference is valid if and only if its matching `finding_type` is set -- the same "required iff this enum value" pattern already used for `Claim.source_observation_id` (claim.py) and `VerificationMethodResult.disposition` (method.py), applied here for the same reason: a `CONTRADICTION`-typed critique with no `contradiction_id` would be a label asserting detail the object doesn't actually carry.

## 4. `Contradiction` and `CounterArgument` — distinct structured types, not just labels

Both are claim-vs-claim, not claim-vs-evidence -- evidence bearing against a claim is already expressible as "the evidence supports a different claim that conflicts with this one" (via `claim.py`'s existing `ClaimOrigin.INTERPRETED_OBSERVATION` chain), so routing everything through `Claim` keeps one comparison shape instead of two.

```
Contradiction(frozen):
    contradiction_id: ContradictionId
    first_claim_id: ClaimId
    second_claim_id: ClaimId
    description: str
    # __post_init__: first_claim_id != second_claim_id -- a claim cannot
    # contradict itself; that's a different problem (evidence.py's
    # existing circular-evidence check), not this type's job.

CounterArgument(frozen):
    counter_argument_id: CounterArgumentId
    target_claim_id: ClaimId
    alternative_explanation: str
    supporting_observation_ids: Tuple[ObservationId, ...] = ()
```

`CounterArgument` is deliberately weaker than `Contradiction`: it doesn't assert the target claim is *false*, only that a plausible alternative exists that would undermine it if true -- matching `POSSIBLE_COUNTEREXAMPLE`'s own name (possible, not proven) versus `CONTRADICTION`'s flat assertion of conflict.

## 5. Explicitly not in this document

- **`CriterionResult`, `ProcessVerificationResult`/`OutcomeVerificationResult`, `CoverageResult`, `VerificationResult`, `VerificationVerdict`, `VerificationConfidence`** -- the next rows after this layer in `v1.md` §42's own ordering. Aggregating multiple `VerificationFinding`s (possibly informed by `Critique`s) into a per-criterion result is real design work this document doesn't attempt.
- **Wiring `receipt.py` to actually carry contradictions/limitations.** `v1.md` §14 lists these as receipt fields; checked directly and `receipt.py` has neither field today. Out of scope here -- that's a change to an existing, already-tested Phase-1 type, the same category of decision this session has consistently flagged rather than made as a side effect of building something else.
- **`EvidenceSource`/`EvidenceReference`/`EvidenceObservation`/`EvidenceTransformation`/`EvidenceBundle`** -- also present in `v1.md` §42's full list, also apparently unbuilt (`evidence.py` has `EvidenceItem`/`EvidenceDirectness`/`EvidenceStatus` only, checked directly), but they weren't named in the request that produced this document and pulling them in would be scope creep beyond Finding/Critique/CounterArgument/Contradiction.

## 6. Shape summary

```
identity.py additions:
    VerificationFindingId, CritiqueId, ContradictionId, CounterArgumentId

dimension.py addition:
    VerificationDimension (Enum, 10 values)

finding.py (new):
    FindingDisposition (Enum): SUPPORTS, REFUTES, INCONCLUSIVE
    VerificationFinding (frozen dataclass)

critique.py (new):
    CritiqueFindingType (Enum, 9 values, verbatim from v1 Sec18)
    Contradiction (frozen dataclass)
    CounterArgument (frozen dataclass)
    Critique (frozen dataclass) -- references the two above plus
                                    assumption.py's existing Assumption
```

## Next step

If confirmed, implementation is `identity.py` + `dimension.py` (the `VerificationDimension` addition) + `finding.py` + `critique.py`, tests on both runners -- same sequence as the prior two checkpoints. Not started.
