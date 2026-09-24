"""
core/capabilities/capability.py — K2.3 Capability Model

Capability represents WHAT the system can do (LLM completion, embedding,
web search, ...). It is provider-independent: nothing about a Capability
says which concrete backend fulfills it. Adapter (this module) represents
HOW a capability is fulfilled by one specific provider.

This module defines:
    - CapabilityType: known capability type identifiers. Only LLM_COMPLETION
      has a real, registered Adapter this session (K2.3) -- the rest are
      declared so the framework's shape matches the target architecture
      (K2.3 prompt's own "Capability represents what the system can do"
      examples), not because they have working implementations yet. See
      the K2.3 Capability Runtime Report for the explicit scope decision.
    - CapabilityRequest / CapabilityResult: the request/response shape
      every Adapter speaks, deliberately mirroring the success/output/
      error/metadata shape already established by WorkerResult
      (core/workers/base.py), RouteResult (core/model_router.py), and
      WorkflowResult (core/workflow/runtime.py) -- one consistent Result
      convention across the whole runtime, not a new one invented here.
    - CapabilityContract: the metadata a CapabilityRegistry stores. Pure
      data -- it does not execute anything ("Registry owns metadata. It
      does NOT execute" -- K2.3 session prompt, Capability Registry
      section).
    - Adapter: a Protocol (structural typing), not an ABC -- consistent
      with K1.6's Resource Model decision (§3: "Resource is a Protocol,
      not an ABC, and definitely not a mixin") and this project's stated
      preference for composition over inheritance. Any object with these
      attributes/methods satisfies the contract; nothing needs to inherit
      from a base class to be a valid Adapter.

Architecture:
    OCBRAIN_K1_6_RESOURCE_MODEL.md §3 — Protocol-based Resource decision,
    applied the same way here for Adapter.
    K2.3 session prompt — Capability Model, Adapter Model.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from core.capabilities.descriptors import (
    ALL_STATUSES,
    CapabilityStatus,
    OperationSpec,
    SUCCESS_STATUSES,
    SIDE_EFFECT_VALUES,
    SideEffect,
    validate_operations,
)


class CapabilityType:
    """Known capability type identifiers.

    Plain string constants, not an Enum -- new capability types are added
    by any future session registering a new CapabilityContract; an Enum
    would require editing this file for every addition, which is exactly
    the kind of closed-set friction the Constitution's Law of
    Replaceability (K1.6-referenced) warns against for anything meant to
    be extended over time.

    Only LLM_COMPLETION has a registered CapabilityContract + real
    Adapters as of K2.3 (see main.py composition root and the K2.3
    Capability Runtime Report). The remainder are declared -- not
    registered -- so the type namespace matches the shape the K2.3 prompt
    itself specifies ("Capability represents what the system can do.
    Examples: LLM Completion, Embedding Generation, Web Search, Browser
    Automation, File Access, Memory Search, Graph Traversal, Image
    Generation, Tool Invocation, External API"). Registering empty/fake
    Adapters for these now, with no real backend to test against, would
    be exactly the kind of unproven speculative structure K1.6's Resource
    Model audit explicitly rejected fields for ("Zero evidence anywhere
    in the codebase that this is used").
    """
    LLM_COMPLETION = "llm_completion"
    EMBEDDING = "embedding"                  # declared, not registered
    WEB_SEARCH = "web_search"                # declared, not registered
    BROWSER_AUTOMATION = "browser_automation"  # declared, not registered
    FILE_ACCESS = "file_access"              # declared, not registered
    MEMORY_SEARCH = "memory_search"          # declared, not registered
    GRAPH_TRAVERSAL = "graph_traversal"      # declared, not registered
    IMAGE_GENERATION = "image_generation"    # declared, not registered
    TOOL_INVOCATION = "tool_invocation"      # declared, not registered
    EXTERNAL_API = "external_api"            # declared, not registered

    # Capability-foundation identities (ADR-CAP-01, PROPOSED). Semantic
    # identities only -- implementation-, adapter-, model- and provider-
    # neutral. Declared here like every other type; REGISTERED (contract +
    # adapters) only by main.py when [capabilities] foundation_enabled is
    # true (default false), so K4.2 discovery behavior is unchanged until
    # the adoption decision in ADR-CAP-03 is made.
    #
    # FILE_READING is *semantic reading of an already-authorized artifact*.
    # It is not FILE_ACCESS: FILE_ACCESS (above) stays the declared,
    # unregistered ACCESS layer (Workspace §G.5/§I) and is not activated.
    TEXT_GENERATION = "text_generation"            # produce/transform prose
    STRUCTURED_REASONING = "structured_reasoning"  # structured analysis
    FILE_READING = "file_reading"                  # artifact -> structured document


@dataclass
class CapabilityRequest:
    """Input to a single capability invocation.

    payload is intentionally a free-form dict rather than a per-capability
    typed dataclass: with only one capability type actually implemented
    this session, a typed-per-capability request hierarchy would be
    designed against a sample size of one. Adapters document which keys
    they read (see each Adapter's own docstring).
    """
    capability_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    # ADR-CAP-01: the named mode of the capability to run (e.g.
    # "summarize"). "" = the contract's default operation (or, for a
    # legacy contract that declares no operations, the one implicit
    # operation). Deliberately NOT called operation_id -- that name is
    # already taken (ADR-K4.2-H-08 / ADR-KERNEL-01) for plan lineage.
    operation: str = ""


@dataclass
class CapabilityResult:
    """Output of a single capability invocation.

    Deliberately the same success/output/error/metadata shape as
    WorkerResult, RouteResult, and WorkflowResult elsewhere in this
    codebase -- one Result convention, not a new one.
    """
    success: bool
    output: Any = None
    error: str = ""
    adapter_used: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # ADR-CAP-02 (additive): machine-readable outcome, see
    # descriptors.CapabilityStatus. Empty = derived from ``success`` so
    # every pre-existing construction site keeps working unchanged.
    status: str = ""
    # ADR-CAP-02 (additive): where this result came from. AdapterRuntime
    # stamps the runtime-known facts (capability, operation, contract
    # version, adapter identity/version, trace id) so an adapter cannot
    # forget them; adapters add implementation facts (reader, model,
    # provider, source references). Provenance is *evidence about
    # origin*, never a verification verdict.
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.status:
            self.status = (CapabilityStatus.OK if self.success
                           else CapabilityStatus.FAILED)
        elif self.status not in ALL_STATUSES:
            raise ValueError(f"unknown CapabilityResult.status {self.status!r}")
        elif self.success != (self.status in SUCCESS_STATUSES):
            raise ValueError(
                f"CapabilityResult inconsistent: success={self.success} "
                f"but status={self.status!r}")

    @classmethod
    def of(cls, status: str, *, output: Any = None, error: str = "",
           **kwargs: Any) -> "CapabilityResult":
        """Build a result whose ``success`` is derived from ``status`` so
        the two can never disagree."""
        return cls(success=status in SUCCESS_STATUSES, output=output,
                   error=error, status=status, **kwargs)


@dataclass
class CapabilityContract:
    """Pure metadata describing one capability type. Holds no execution
    logic and no reference to any concrete Adapter instance -- the
    Registry indexes Adapters separately (registry.py), keeping "what
    this capability is" strictly separate from "who currently fulfills
    it", per the K2.3 prompt's own Capability/Adapter split.

    is_general_purpose (K4.2-H1 D2, ADR-K4.2-H-02): declares this
    capability a fallback candidate for capability discovery
    (core/cognitive/planner.py discover_capabilities()) regardless of
    lexical match strength against a CapabilityDiscoveryRequest --
    e.g. LLM_COMPLETION can plausibly attempt almost any text-shaped
    subgoal even when its own description shares no tokens with the
    subgoal's description. This is a discovery-time ranking signal
    only (specific matches always dominate general-purpose ones -- see
    discover_capabilities()'s specificity-dominance ordering); it does
    not change registration, adapter resolution, or execution. No
    Planner-side hard-coded capability_type routing is introduced --
    the registry remains the single dynamic source of what is
    "general-purpose" (D2: "No hard-coded routing").
    """
    capability_type: str
    description: str
    required_resources: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    is_general_purpose: bool = False
    # ── ADR-CAP-01 / ADR-CAP-02 (additive; every default preserves the
    # pre-existing behavior of a contract that sets none of them) ──────
    # ``version`` above is the semver of THIS CONTRACT: a major bump means
    # the semantics changed; adapters declare which major they implement.
    # It is not an adapter, model or provider version.
    operations: Tuple[OperationSpec, ...] = ()
    default_operation: str = ""
    # Descriptive only. Metadata is never enforcement; GovernanceKernel and
    # the sandbox enforce (Workspace §G.2: AdapterRuntime is not the
    # governance boundary).
    side_effects: str = SideEffect.UNSPECIFIED

    def operation_names(self) -> Tuple[str, ...]:
        return tuple(op.name for op in self.operations)

    def get_operation(self, name: str = "") -> Optional[OperationSpec]:
        """Resolve an operation by name. ``""`` selects the default
        (explicit ``default_operation``, else the first declared). None
        when the contract declares no such operation."""
        if not self.operations:
            return None
        wanted = name or self.default_operation or self.operations[0].name
        for op in self.operations:
            if op.name == wanted:
                return op
        return None

    def structural_problems(self) -> List[str]:
        """Validation problems in the additive descriptor fields (empty =
        valid). Pre-existing fields are not re-validated here."""
        problems = validate_operations(
            self.capability_type, self.operations, self.default_operation)
        if self.side_effects not in SIDE_EFFECT_VALUES:
            problems.append(
                f"{self.capability_type}: unknown side_effects "
                f"{self.side_effects!r}")
        return problems


@runtime_checkable
class Adapter(Protocol):
    """Structural contract every concrete Adapter satisfies.

    Deliberately mirrors core/provider_mesh.py's already-proven Provider
    ABC shape (health_score, cooldown_until, is_available/mark_success/
    mark_failure) rather than inventing a new health-tracking convention
    -- that pattern is validated, tested, and already carries real
    production traffic for LLM generation. Adapter generalizes it to any
    capability_type, and execute() carries a CapabilityRequest/Result
    instead of a raw prompt string.
    """
    adapter_name: str
    capability_type: str
    health_score: int
    cooldown_until: float

    async def execute(self, request: CapabilityRequest,
                       resources: "ResourceManager") -> CapabilityResult:
        ...

    def is_available(self) -> bool:
        ...

    def mark_success(self) -> None:
        ...

    def mark_failure(self, cooldown_seconds: int = 60) -> None:
        ...


class BaseAdapter:
    """Optional convenience base implementing Adapter's health/cooldown
    bookkeeping identically to provider_mesh.Provider, so concrete
    adapters don't each reimplement it. Adapters are not required to
    inherit from this -- Adapter is a Protocol, and anything with the
    right shape (e.g. a test double) satisfies it without inheriting
    anything, consistent with "composition over inheritance, Protocol
    over ABC" (K1.6 §3).
    """
    adapter_name: str = "base"
    capability_type: str = ""
    # ADR-CAP-02 optional identity/compatibility attributes. Not part of
    # the Adapter Protocol (adding attributes there would break
    # isinstance() for existing structural adapters); read defensively
    # with getattr() by CapabilityRegistry / AdapterRuntime.
    adapter_version: str = ""
    # Contract major (or major.minor) this adapter implements; "" = not
    # declared (legacy). A declared major that differs from the
    # contract's is a registration error, so a contract-breaking change
    # cannot be silently paired with an old implementation.
    implements_contract: str = ""
    # Operations this adapter implements; empty = all declared ones.
    supported_operations: Tuple[str, ...] = ()

    def __init__(self):
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
