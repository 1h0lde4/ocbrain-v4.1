"""
VerificationMethod / VerificationCapability (mission Sec16, Sec17, Sec21,
Sec41-46; v1.md Sec17/Sec42; v2-frozen.md Sec11; Phase 3/5 -- method
capability). Implements the design confirmed in
docs/architecture/verification-critic-evidence-system-verificationmethod-design-proposal.md
(Revision 2) after a review cycle -- see that document for the reasoning
behind every choice below; this module doesn't re-derive it.

Three layers, not two, matching v1.md Sec42's own contract list rather
than silently dropping one of it:

    VerificationMethod        "verify file exists" -- what kind of check
        requires ->
    VerificationCapability     filesystem_observation -- verification-
                                domain classification (mission Sec21:
                                is this read-only, passive, an active
                                probe, or mutating)
        maps to (when execution needs to leave the process) ->
    Kernel CapabilityContract   FILE_ACCESS -- core/capabilities/,
                                unchanged, reused not reimplemented

VerificationMethod is pure metadata, mirroring core/capabilities/
capability.py's CapabilityContract -- it holds no execution logic.
VerifierAdapter (a Protocol, mirroring that same module's Adapter) is
the actual invocable thing. Deliberately NOT routed through
AdapterRuntime's ranked-fallback selection: substituting which LLM
provider answers a prompt is epistemically neutral; substituting which
verifier rendered a judgment is not (mission Sec46), and a receipt has
to record which one actually ran. A verifier's own underlying capability
calls (e.g. an actual FILE_ACCESS read) may still go through ordinary
AdapterRuntime fallback -- that is a different, lower-stakes
substitution than substituting the verifier itself.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable

from .evidence import EvidenceDirectness
from .identity import (
    CriterionId,
    ObservationId,
    VerificationCapabilityId,
    VerificationMethodId,
)
from .target import VerificationTargetSnapshot


class InspectionClass(str, Enum):
    """Mission Sec21: verification is read-only by default: classify
    inspection methods distinctly rather than treating "verifying" as
    one undifferentiated activity level."""
    READ_ONLY_INSPECTION = "read_only_inspection"
    PASSIVE_OBSERVATION = "passive_observation"
    ACTIVE_PROBE = "active_probe"
    MUTATING_ACTION = "mutating_action"


class CostLatencyClass(str, Enum):
    INSTANT = "instant"
    FAST = "fast"
    MODERATE = "moderate"
    SLOW = "slow"


class MethodExecutionState(str, Enum):
    """What happened when a method was invoked -- never conflated with
    what the result means (that's MethodDisposition, below, and further
    still, an eventual Assessment). Mission Sec50: none of NOT_RUN,
    BLOCKED, UNAVAILABLE may silently become a positive result through
    omission, defaulting, or aggregation."""
    NOT_RUN = "not_run"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    EXECUTION_FAILED = "execution_failed"
    EXECUTED = "executed"


class MethodDisposition(str, Enum):
    """Only meaningful when MethodExecutionState is EXECUTED. This is
    the method's own report on its execution's completeness/clarity --
    it is NOT a support/refute judgment against any criterion. That
    comparison needs the criterion's actual requirement (and possibly
    evidence from other methods too), so it belongs to Assessment
    (Phase 4, not built), never here. Design doc Sec1."""
    CONCLUSIVE = "conclusive"
    INCONCLUSIVE = "inconclusive"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class VerificationCapability:
    """A verification-domain classification of an inspection ability --
    not a raw Kernel capability. May require zero underlying Kernel
    capabilities (a pure in-process check needs nothing outside the
    process to reach for)."""
    capability_id: VerificationCapabilityId
    name: str
    inspection_class: InspectionClass
    typical_evidence_directness: EvidenceDirectness
    underlying_capability_types: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("VerificationCapability requires a non-empty name")


@dataclass(frozen=True)
class VerificationMethod:
    """Pure metadata describing a kind of verification check -- mirrors
    CapabilityContract (core/capabilities/capability.py) in holding no
    execution logic and no reference to any concrete VerifierAdapter
    instance. Reusable and versioned: a changed method definition is a
    new version, not an in-place mutation (matching rubric.py/policy.py's
    own versioning convention already established in this module)."""
    method_id: VerificationMethodId
    method_type: str  # plain string constant, matching CapabilityType's
                       # own not-an-Enum extensibility reasoning
    description: str
    version: str
    produces_evidence_directness: EvidenceDirectness
    external_access_needed: bool
    is_deterministic: bool
    cost_latency_class: CostLatencyClass
    required_capabilities: Tuple[VerificationCapabilityId, ...] = ()
    applicable_target_kinds: Tuple[str, ...] = ()  # provisional: target.py
        # has no target-kind taxonomy yet (design doc Sec9) -- empty
        # means "no declared restriction", not "matches nothing"
    known_blind_spots: Tuple[str, ...] = ()
    applicability_conditions: str = ""

    def __post_init__(self) -> None:
        if not self.method_type or not self.method_type.strip():
            raise ValueError("VerificationMethod requires a non-empty method_type")
        if not self.description or not self.description.strip():
            raise ValueError("VerificationMethod requires a non-empty description")
        if not self.version or not self.version.strip():
            raise ValueError("VerificationMethod requires a non-empty version")
        if self.external_access_needed and not self.required_capabilities:
            raise ValueError(
                f"VerificationMethod {self.method_id!r} has "
                f"external_access_needed=True but declares no "
                f"required_capabilities -- external access has to go "
                f"through some capability"
            )


@dataclass
class VerificationMethodRequest:
    """Input to a single method invocation. payload is intentionally
    free-form (design doc Sec11) -- a conscious, revisitable choice
    given how few concrete methods exist yet, not an unexamined copy of
    CapabilityRequest's own reasoning for the same shape."""
    method_id: VerificationMethodId
    target: VerificationTargetSnapshot
    criterion_id: CriterionId
    payload: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.method_id or not str(self.method_id).strip():
            raise ValueError("VerificationMethodRequest requires a non-empty method_id")


@dataclass
class VerificationMethodResult:
    """Output of a single method invocation. execution_state and
    disposition are deliberately separate fields (design doc Sec1) --
    collapsing them was Revision 1's core mistake. observations, not
    evidence: a method produces raw Observation references
    (observation.py); promoting one into Evidence needs scope,
    authority, provenance, and criterion-binding this module has no
    business asserting on a method's behalf (design doc Sec10)."""
    execution_state: MethodExecutionState
    disposition: Optional[MethodDisposition] = None
    observations: Tuple[ObservationId, ...] = ()
    adapter_used: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.execution_state is MethodExecutionState.EXECUTED:
            if self.disposition is None:
                raise ValueError(
                    "VerificationMethodResult with execution_state=EXECUTED "
                    "must report a disposition -- an executed method that "
                    "reaches no conclusion, however weak, is INSUFFICIENT, "
                    "not silently undetermined"
                )
            if (self.disposition in (MethodDisposition.CONCLUSIVE, MethodDisposition.INCONCLUSIVE)
                    and not self.observations):
                raise ValueError(
                    f"disposition={self.disposition.value} requires at "
                    f"least one observation -- {self.disposition.value} "
                    f"with nothing observed is a contradiction"
                )
        else:
            if self.disposition is not None:
                raise ValueError(
                    f"disposition is only meaningful when execution_state "
                    f"is EXECUTED, not {self.execution_state.value} -- a "
                    f"method that didn't run, was blocked, was "
                    f"unavailable, or failed cannot also report how "
                    f"conclusive its (nonexistent) result was"
                )
            if self.observations:
                raise ValueError(
                    f"execution_state={self.execution_state.value} means "
                    f"the method produced no result -- it cannot carry "
                    f"observations"
                )


@runtime_checkable
class VerifierAdapter(Protocol):
    """Structural contract every concrete verifier implementation
    satisfies -- mirrors core/capabilities/capability.py's Adapter
    (same health_score/cooldown_until/is_available/mark_success/
    mark_failure shape, itself mirroring core/provider_mesh.py's
    Provider) so a flaky external verifier degrades and cools down
    exactly like a flaky LLM provider does today, with no second
    health-tracking convention invented for this module.

    Deliberately NOT invoked through AdapterRuntime.invoke()'s ranked
    fallback -- a caller holding a VerifierAdapter reference calls it
    directly and reports UNAVAILABLE itself if is_available() is False,
    rather than risking a silent substitution to a different verifier
    (design doc Sec6/Sec7).
    """
    adapter_name: str
    method_id: VerificationMethodId
    health_score: int
    cooldown_until: float

    async def verify(self, request: VerificationMethodRequest,
                      resources: Any) -> VerificationMethodResult:
        ...

    def is_available(self) -> bool:
        ...

    def mark_success(self) -> None:
        ...

    def mark_failure(self) -> None:
        ...


class BaseVerifierAdapter:
    """Optional convenience base implementing VerifierAdapter's health/
    cooldown bookkeeping identically to BaseAdapter (capability.py) --
    not required; VerifierAdapter is a Protocol, and anything with the
    right shape satisfies it without inheriting anything."""
    adapter_name: str = "base"
    method_id: str = ""

    def __init__(self) -> None:
        self.health_score = 100
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.cooldown_until = 0.0

    def is_available(self) -> bool:
        return time.time() >= self.cooldown_until

    def mark_success(self) -> None:
        self.consecutive_failures = 0
        self.health_score = min(100, self.health_score + 5)

    def mark_failure(self, cooldown_seconds: int = 60) -> None:
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        self.health_score = max(0, self.health_score - 20)
        delay = cooldown_seconds * (2 ** (self.consecutive_failures - 1))
        self.cooldown_until = time.time() + min(delay, 3600)
