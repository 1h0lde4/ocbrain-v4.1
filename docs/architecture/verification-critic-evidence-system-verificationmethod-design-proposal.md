# VerificationMethod — Design Proposal (not yet implemented)

**Date:** 22 September 2026
**Status:** PROPOSED. This document establishes the contract before any code is written, per standing practice — a design checkpoint, not a coding ticket. Nothing in `core/verification/` changes until this (or a corrected version of it) is confirmed.
**Grounding:** Answers below are derived from three concrete sources already in this repository, not invented fresh — `docs/architecture/verification-critic-evidence-system-architecture-v1.md` §17/§42 (the original Method design and contract-prep list), `-v2-frozen.md` §11 (the Method-vs-Dimension correction), and the existing `core/capabilities/` module (`registry.py`, `capability.py`, `adapter_runtime.py`), which already solves a structurally identical problem for LLM/tool capabilities and is the pattern mission §22 requires Verification to reuse rather than reinvent.

---

## 1. Method vs. an individual verification run

Not the same object, and not modeled as one. `VerificationMethod` is a **reusable, versioned declaration of a kind of check** — analogous to `CapabilityContract` (`core/capabilities/capability.py`): it says what a method *is capable of*, holds no execution logic, and has no reference to any specific target, criterion, or evidence. An actual application of a method to a specific criterion/target — one invocation — is a later, separate concept (`VerificationStep`, Phase 7, not this phase). This mirrors `CapabilityContract` vs. one `CapabilityRequest`/`CapabilityResult` pair, and mirrors this module's own established pattern: `Rubric` (reusable, versioned, lockable) vs. a specific criterion check against it are already kept apart the same way.

## 2. Capability, algorithm, or both

**Declarative capability, not the algorithm itself** — matching `CapabilityContract` holding "pure metadata... no execution logic" while `Adapter` (a `Protocol`) is the actual invocable thing. Proposed split:

- `VerificationMethod` — pure metadata: what this kind of check can do, what it needs, what it costs. No `execute()`.
- `VerifierAdapter` (a `Protocol`, matching `core/capabilities/capability.py`'s `Adapter`) — the actual invocable implementation. `async def verify(self, request, resources) -> VerificationMethodResult`, plus the same `is_available()`/`mark_success()`/`mark_failure()`/`health_score`/`cooldown_until` shape `Adapter` already has (borrowed from `provider_mesh.Provider`) — a flaky external verifier should degrade and cool down exactly like a flaky LLM provider does today; no reason to invent a second health-tracking convention.

A given `VerificationMethod` can have zero, one, or several registered `VerifierAdapter`s, the same way a `CapabilityContract` can have zero, one, or several `Adapter`s (`CapabilityRegistry.validate()` already treats zero adapters as a non-fatal but surfaced condition — the same behavior applies here).

## 3. Inputs, outputs, evidence requirements

Mirrors `CapabilityRequest`/`CapabilityResult`, with the verification-specific additions those don't need:

```
VerificationMethodRequest:
    method_type: str
    target: ...              # what's being checked (existing target.py types)
    criterion_id: CriterionId
    payload: Dict[str, Any]  # method-specific, same free-form choice CapabilityRequest makes
    trace_id: str

VerificationMethodResult:
    outcome: MethodOutcome    # NOT a bare bool — see 9. below; this is the one field
                              # that cannot just copy CapabilityResult's success: bool
    observation: Optional[ObservationId]   # links to observation.py, built this session
    evidence: Tuple[EvidenceId, ...]       # links to evidence.py
    adapter_used: str
    duration_ms: float
    metadata: Dict[str, Any]
```

`CapabilityResult.success: bool` is deliberately not reused as-is: master-prompt §50 forbids `UNKNOWN`/`NOT_RUN`/`BLOCKED`/`UNAVAILABLE` ever collapsing into a boolean pass/fail, which is exactly what a plain `success: bool` would do. Everything else about the shape is a direct copy of the established Result convention.

What a method actually declares it needs/produces, on the contract itself (metadata, not runtime): supported target types, required evidence directness (`DIRECT`/`INDIRECT`/`DERIVED`/`MODEL_INTERPRETATION`, from `evidence.py`), and `required_capability_type: Optional[str]` — see 5.

## 4. Authorization

Two different authorization questions, not one, and the existing ownership decision already answers both:

- **Verification's own findings never require governance pre-authorization to exist** — v1 §32 ("`Verification → facts/findings/confidence/evidence/verdict → Governance`. One direction only. Verification never calls into `GovernanceKernel` to authorize anything") and confirmed unchanged in v1's own Component Ownership Matrix (`GovernanceKernel` row: "Required Change: None"). A method concluding "criterion X failed" doesn't ask permission to conclude that.
- **A method's underlying action, when it does one, is not exempt.** Mission §21/§22 are explicit that verification is read-only by default and gains no special execution authority "because it is only verifying." Reconciliation: when a `VerifierAdapter`'s `verify()` needs to reach outside the process (filesystem, network, a tool, a model call), it does so *by requesting the relevant capability from the existing `CapabilityRegistry`/`AdapterRuntime`* — the same governed path any other caller uses, with whatever authorization that path already enforces. Verification doesn't get a bypass lane; it also doesn't reimplement governance to get one.

## 5. Capability availability

Not reinvented — deferred to the registry that already does this. `VerificationMethod.required_capability_type: Optional[str]` (e.g. `CapabilityType.FILE_ACCESS`, `CapabilityType.TOOL_INVOCATION`, or `None` for a check that needs nothing outside the current process — pure in-memory/deterministic). At compile time (§6 below) and at strategy-selection time, availability is a query against the *existing* `CapabilityRegistry.get_adapters(capability_type)` / `.validate()` — not a second registry tracking the same fact. A method requiring a capability with zero registered adapters is unavailable now, the same condition `CapabilityRegistry.validate()` already surfaces for any other capability.

## 6. Admissibility for a CompiledVerificationSpecification

`InspectionStep.method_reference: str` already exists (built round 3) specifically as "a plain-string forward reference to the not-yet-built `VerificationMethod`" — this proposal is what resolves that reference. Compilation (mission §10, not yet built — `CompiledVerificationSpecification` is still open) checks, per step: (a) `method_reference` resolves to a registered `VerificationMethod`; (b) that method's declared supported target types include the step's actual target type; (c) `required_capability_type`, if set, currently has ≥1 available adapter per `CapabilityRegistry`. Any failure is a compile-time rejection or an explicit `BLOCKED`/`UNAVAILABLE` marking on that step — never a silent skip, per the same fail-closed rule every other part of this system already follows.

## 7. Immutable / versioned

Frozen dataclass, `version: str` field — the same as every other type in `core/verification/` so far (all fourteen-plus modules are `@dataclass(frozen=True)`; `CapabilityContract` itself is not frozen, but internal consistency with this module's own unbroken convention outweighs matching that one detail of the external template). A changed method definition gets a new version, the same rule `rubric.py`/`policy.py` already follow for their own versioned contracts — no in-place semantic mutation of a method other code may already hold a reference to (the exact reasoning `CapabilityRegistry.register_capability()`'s own docstring already gives for rejecting re-registration).

## 8. Local vs. future external/expert methods

No structural split needed — this is the one question where the existing pattern's answer is "you're not going to need a second type." `Adapter`'s shape already handles this uniformly today: `provider_mesh.Provider`, which `Adapter`/`BaseAdapter` explicitly mirror, already covers local and remote (LLM provider) backends through the identical interface, differing only in the metadata each declares (latency, cost, availability) — not in structure. A future human-review method or an external verification service is just another `VerifierAdapter` implementation with `external_access_needed=True` and a higher `cost_latency_class` declared on its `VerificationMethod` contract; nothing about the registry, the Protocol, or the compile-time admissibility check (§6) needs to know the difference.

## 9. What gets recorded on execute / fail / unavailable / insufficient

This is the field mission §50 makes non-negotiable, and the one place this proposal deliberately does not copy `CapabilityResult` verbatim (§3). Proposed `MethodOutcome` (not a bare bool):

```
EXECUTED_SUPPORTS   # ran, evidence supports the criterion
EXECUTED_REFUTES    # ran, evidence contradicts the criterion
EXECUTED_INCONCLUSIVE
NOT_RUN
BLOCKED             # e.g. missing capability/authorization (§5/§6)
UNAVAILABLE         # adapter exists but is_available() is False (cooldown, health)
EXECUTION_FAILED    # the adapter raised/crashed — an infrastructure failure, never PASS
INSUFFICIENT        # ran, but evidence produced doesn't meet the criterion's evidence requirement
```

`EXECUTION_FAILED` existing as its own value, separate from `EXECUTED_REFUTES`, is the direct implementation of master-prompt §50's core rule applied to this one type: a crashed verifier is not evidence against the criterion, and must not be aggregated as if it were.

---

## What this proposal deliberately leaves open

- The exact `VerificationMethodType` string constants (mirroring `CapabilityType`'s plain-string, not-Enum approach, for the same extensibility reason its docstring gives) — a short list matching v1 §17's priority order, filled in at implementation time, not designed in the abstract here.
- Where dimension classification (`StateVerification`/`TransitionVerification`/`InvariantVerification`, already built) attaches. v2 §11 is explicit that method and dimension are orthogonal and should be classified independently **on a `VerificationFinding`**, not nested — `VerificationFinding` doesn't exist yet (Phase 5), so this proposal does not resolve exactly how a method's dimension-applicability metadata and a specific finding's dimension classification relate. Flagged, not guessed at.
- `CompiledVerificationSpecification`'s full shape — §6 above says only what admissibility checking needs from `VerificationMethod`; the rest of that type is out of scope here.

## Next step

If this is confirmed (as-is or amended), implementation is: `identity.py` (`VerificationMethodId`), a new `method.py` (`VerificationMethod`, `VerificationMethodType`, `VerificationMethodRequest`, `VerificationMethodResult`, `MethodOutcome`, `VerifierAdapter` Protocol), tests on both runners, then — separately — the compile-time admissibility check itself once `CompiledVerificationSpecification` is designed. Not started; awaiting confirmation on the above.
