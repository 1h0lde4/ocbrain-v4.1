# VerificationMethod — Design Proposal (Revision 2, not yet implemented)

**Date:** 22 September 2026
**Status:** PROPOSED, revised. Revision 1 was reviewed and returned with 5 mandatory (P0) and 5 secondary (P1) corrections. All ten are addressed below — most by changing the design, two (target-kind taxonomy, method payload shape) by explicitly staying provisional rather than forcing a resolution the codebase doesn't support yet. Nothing in `core/verification/` has changed; this document is still the checkpoint, not the implementation.

**What changed and why, briefly, before the detail:** two of Revision 1's choices were genuine layering violations, verified against source rather than taken on the review's word — `adapter_runtime.py`'s forced-choice fallback (confirmed by direct read: `_rank_adapters()`, lines 141-149) means naively reusing it for verifier selection would silently substitute one verifier for another, which is exactly the kind of hidden-identity problem receipts exist to prevent. `target.py` (confirmed by direct read) has no target-kind taxonomy at all yet — Revision 1's admissibility check assumed one. Both are fixed below, not argued around.

---

## Corrections applied

### 1. `MethodOutcome` no longer conflates execution with assessment (P0-1)

Revision 1's `EXECUTED_SUPPORTS`/`EXECUTED_REFUTES` were semantic conclusions wearing an execution-outcome costume — exactly the `Method != Assessment != Verdict` collapse this whole system exists to prevent, and a collapse already cited the principle for in Revision 1 without noticing it was violated there too. Split into two independent fields:

```
MethodExecutionState:
    NOT_RUN
    BLOCKED
    UNAVAILABLE
    EXECUTION_FAILED
    EXECUTED

MethodDisposition (only meaningful when state is EXECUTED):
    CONCLUSIVE     -- the method completed cleanly, produced what its own
                      contract promised
    INCONCLUSIVE   -- executed, but the result is genuinely ambiguous at
                      the method's own level (e.g. a semantic search
                      found something possibly relevant, possibly not)
    INSUFFICIENT   -- executed, but didn't produce enough to constitute
                      a usable observation (e.g. a query returned zero rows
                      where the inspection plan needed at least one)
```

Disposition is about the method's own execution completeness/clarity — never "does this support or refute the criterion." That comparison needs the criterion's actual requirement and possibly evidence from other methods too, so it can only happen at assessment (Phase 4, not built), which is exactly why it can't live here.

### 2. Compile-time admissibility no longer checks dynamic adapter state (P0-2)

Confirmed by reading `adapter_runtime.py` directly: `is_available()` reflects `health_score`/`cooldown_until`, which change via `mark_success()`/`mark_failure()` — dynamic, not something a compiled spec should freeze against. Split:

```
COMPILE-TIME (static, checked once when a spec is compiled):
    method_reference resolves to a registered VerificationMethod
    target kind is declared-compatible (see 9, below -- provisional)
    every required VerificationCapability is itself registered
      (a VerificationCapability existing doesn't require any adapter
      to currently be healthy -- see 3)

RUNTIME (checked at actual invocation):
    the specific adapter selected is currently available
    (is_available()) -- no forced-choice substitution (see 6)
```

A compiled spec that later hits a cooldown'd adapter stays compiled; that one step reports `UNAVAILABLE` at invocation, not a compile-time rejection.

### 3. `VerificationCapability` reconciled — a real, distinct, middle layer (P0-3)

Revision 1 quietly dropped this despite it sitting in `v1.md` Sec42's own contract list alongside `VerificationMethod`. Reconciliation, using the review's own three-layer example as the actual test case:

```
VerificationMethod            "verify file exists"
    requires ->
VerificationCapability        filesystem_observation
    maps to (when execution needs to leave the process) ->
Kernel CapabilityContract     FILE_ACCESS  (core/capabilities/, unchanged)
```

The middle layer earns its place on more than naming: it's where mission Sec21's `READ_ONLY_INSPECTION` / `PASSIVE_OBSERVATION` / `ACTIVE_PROBE` / `MUTATING_ACTION` classification actually belongs. That's a verification-epistemics concept with no equivalent in the generic Kernel `CapabilityContract` (which serves the whole runtime, not just Verification, and has no notion of "does this probe risk mutating what it inspects"). Proposed shape:

```
VerificationCapability (frozen):
    capability_id: VerificationCapabilityId
    name: str                                  # "filesystem_observation", "runtime_event_query", ...
    inspection_class: InspectionClass          # mission Sec21's four values
    typical_evidence_directness: EvidenceDirectness   # evidence.py, already exists
    underlying_capability_types: Tuple[str, ...]      # Kernel CapabilityType strings; may be
                                                       # empty for a pure in-process check
                                                       # (nothing to reach outside the process for)
```

Both `VerificationMethod` and `VerificationCapability` live in `method.py` (one file) — tightly coupled the same way `Rubric`/`Criterion` share `rubric.py` and `InspectionPlan`/`InspectionStep` share `inspection.py`; this module's own established convention, not a new one.

### 4. Multiple capability dependencies (P0/P1-6)

Resolved as a consequence of 3: `VerificationMethod.required_capabilities: Tuple[VerificationCapabilityId, ...]` — plural by construction, since it references the new middle layer rather than a single Kernel capability string. No separate decision needed once 3 is accepted.

### 5. V1 Sec17 reconciliation table (P0-5)

| Sec17 requirement | Field | Status |
|---|---|---|
| target types | `applicable_target_kinds: Tuple[str, ...]` | provisional — see 9 |
| evidence types | `typical_evidence_directness` (on `VerificationCapability`, 3) + `produces_evidence_directness: EvidenceDirectness` (on `VerificationMethod` itself, for methods with no capability dependency) | covered |
| required tools | `required_capabilities` (3, 4) | covered |
| external access | `external_access_needed: bool` — on the **method**, not the adapter (P1-7, below) | covered |
| deterministic/stochastic | `is_deterministic: bool` | added — missing entirely from Revision 1, and load-bearing given the deterministic-first ladder is the architecture's central ordering rule |
| cost/latency | `cost_latency_class: CostLatencyClass` (new enum: `INSTANT`/`FAST`/`MODERATE`/`SLOW`) | added, was narrative-only before |
| blind spots | `known_blind_spots: Tuple[str, ...]` | added |
| applicability conditions | `applicability_conditions: str` | added — free text; conditions that aren't reducible to target-kind matching (e.g. "only applicable when the target has a prior committed state to compare against") don't fit a typed field yet |

### 6. Verifier selection does not inherit `AdapterRuntime`'s fallback (P0-4)

Confirmed directly: `AdapterRuntime._rank_adapters()` picks a forced substitute when everything's in cooldown, and `invoke()` falls through a ranked list on failure. Correct for "which LLM provider" (epistemically interchangeable). Wrong for "which verifier" — Verifier A and Verifier B can have different bias, independence, and applicability properties (mission Sec46), and a receipt has to record which one actually ran, not "one of a ranked set." Resolution: Verification's own invocation path calls a **specific** `VerifierAdapter` chosen by compilation/strategy, not a health-ranked list. If that specific adapter is unavailable, the result is `UNAVAILABLE` — never a silent substitute. Kernel capability calls a verifier makes underneath it (e.g. an actual `FILE_ACCESS` read) may still go through ordinary `AdapterRuntime` fallback — substituting *which filesystem backend* answers a read is a materially different, lower-stakes kind of substitution than substituting *which verifier* rendered a judgment.

### 7. `UNAVAILABLE` is now actually observable (P0/P1, follows from 6)

Direct consequence of 6: because Verification doesn't route verifier selection through `AdapterRuntime.invoke()`'s forced-choice ranking, checking `adapter.is_available()` itself before calling `execute()` makes `UNAVAILABLE` a real, reachable state rather than one `AdapterRuntime` would paper over.

### 8. `external_access_needed` moved to the method (P1-7)

Already folded into the table in 5 — it's a property of what the *method* requires, not an implementation detail of whichever adapter happens to fulfill it. A method needing outside access is that regardless of which adapter is registered against it.

### 9. Target-kind checking — deliberately left provisional (P1-9)

Confirmed by direct read: `target.py` today is `VerificationTargetFingerprint` + `VerificationTargetSnapshot` (`target_id: str`, fingerprint, `captured_at`) — no `ArtifactTarget`/`TaskTarget`/`FileTarget` kind hierarchy exists. `applicable_target_kinds: Tuple[str, ...]` is proposed as plain strings (matching this module's own established placeholder pattern — `InspectionStep.method_reference: str` did the same thing for the then-unbuilt `VerificationMethod`), and compile-time admissibility (2) treats an unset/empty value as "no declared restriction" rather than gating on a taxonomy that isn't there. Building the actual target-kind hierarchy is out of scope for this proposal; recorded as a boundary, not invented around.

### 10. Method produces Observations, not Evidence directly (P1-8)

Reconsidered per the review's caution, and consistent with what this session's own Phase 2 work already established: `Observation -> Evidence` is a promotion that needs scope, authority, provenance, and criterion-binding `evidence.py`/`observation.py` don't get for free — exactly why the master prompt's own phase list keeps "observation capture" and "evidence binding" as two separate Phase 4 line items, not one. `VerificationMethodResult.observations: Tuple[ObservationId, ...]` is now the primary output; the `evidence: Tuple[EvidenceId, ...]` field from Revision 1 is dropped. Promoting an Observation into Evidence is explicit, later, Phase 4 work — no adapter manufactures canonical Evidence as a side effect of running.

### 11. Free-form payload — kept, but as a conscious choice, not an inherited one (P1-10)

`CapabilityRequest.payload: Dict[str, Any]` is free-form because K2.3 had one real implementation and didn't want to design a hierarchy against a sample of one. Verification is deliberately building a semantic contract across several kinds of methods at once, which is a materially different situation — the same justification doesn't automatically transfer. Decision: keep free-form `payload: Dict[str, Any]` on `VerificationMethodRequest` for now regardless, because a typed-per-method-type request hierarchy would itself be designed against however many method types exist at the moment `method.py` is written, which is likely to be nearly as thin a sample. Flagged explicitly as revisitable once real method variety exists, not silently carried over.

### 12. Method/Dimension orthogonality — unchanged, confirmed correct

No change. `v2-frozen.md` Sec11 over `v1.md` Sec17's wording remains the right call, and the open question (exactly how a method's own dimension-applicability metadata meets a specific `VerificationFinding`'s dimension classification) stays open until `VerificationFinding` exists — not resolved here, same as Revision 1.

---

## Revised shape sketch

```
identity.py additions:
    VerificationMethodId, VerificationCapabilityId

method.py (new):
    InspectionClass (Enum): READ_ONLY_INSPECTION, PASSIVE_OBSERVATION,
                             ACTIVE_PROBE, MUTATING_ACTION   -- mission Sec21

    CostLatencyClass (Enum): INSTANT, FAST, MODERATE, SLOW

    MethodExecutionState (Enum): NOT_RUN, BLOCKED, UNAVAILABLE,
                                  EXECUTION_FAILED, EXECUTED

    MethodDisposition (Enum): CONCLUSIVE, INCONCLUSIVE, INSUFFICIENT

    VerificationCapability (frozen dataclass):
        capability_id, name, inspection_class,
        typical_evidence_directness, underlying_capability_types

    VerificationMethod (frozen dataclass):
        method_id, method_type: str,  # plain string constants, matching
                                       # CapabilityType's own not-an-Enum
                                       # extensibility reasoning
        description, version,
        required_capabilities: Tuple[VerificationCapabilityId, ...],
        applicable_target_kinds: Tuple[str, ...],   # provisional, see 9
        produces_evidence_directness: EvidenceDirectness,
        external_access_needed: bool,
        is_deterministic: bool,
        cost_latency_class: CostLatencyClass,
        known_blind_spots: Tuple[str, ...],
        applicability_conditions: str

    VerifierAdapter (Protocol, mirrors core/capabilities/capability.py's
                      Adapter -- health_score, cooldown_until,
                      is_available/mark_success/mark_failure -- but
                      selected individually, never through
                      AdapterRuntime's ranked fallback; see 6):
        adapter_name: str
        method_id: VerificationMethodId
        async def verify(request, resources) -> VerificationMethodResult

    VerificationMethodRequest (dataclass):
        method_id, target, criterion_id,
        payload: Dict[str, Any],   # conscious, revisitable choice; see 11
        trace_id

    VerificationMethodResult (dataclass):
        execution_state: MethodExecutionState,
        disposition: Optional[MethodDisposition],  # only when EXECUTED
        observations: Tuple[ObservationId, ...],   # not Evidence; see 10
        adapter_used: str,
        duration_ms: float,
        metadata: Dict[str, Any]
```

Frozen/versioned throughout, matching this module's own unbroken convention (unchanged from Revision 1; not revisited by the review).

## Still open, honestly

- Exact `applicable_target_kinds` values and whether admissibility checking on them is even enforced yet, pending a real target-kind taxonomy (9).
- Whether `payload` ever becomes typed per method-type (11) — revisit once several real methods exist, not before.
- Where a method's dimension-applicability metadata meets `VerificationFinding`'s dimension classification (12, carried over from Revision 1) — waits on Phase 5.

## Next step

Same as Revision 1's, now that the above is resolved: `identity.py` additions, then `method.py`, tests on both runners. Not started — this revision is the checkpoint now.
