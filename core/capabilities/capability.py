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
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


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


@dataclass
class CapabilityContract:
    """Pure metadata describing one capability type. Holds no execution
    logic and no reference to any concrete Adapter instance -- the
    Registry indexes Adapters separately (registry.py), keeping "what
    this capability is" strictly separate from "who currently fulfills
    it", per the K2.3 prompt's own Capability/Adapter split.
    """
    capability_type: str
    description: str
    required_resources: List[str] = field(default_factory=list)
    version: str = "1.0.0"


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
