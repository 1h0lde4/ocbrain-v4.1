"""
core/capabilities/resource.py — K2.3 Resource Binding

Extends the Resource Model frozen in K1.6 (OCBRAIN_K1_6_RESOURCE_MODEL.md).
That document's central finding was that most existing objects were
*already* correctly NOT unified under one Resource base, and that only
objects with genuine independent identity and lifecycle should satisfy
the Resource Protocol -- KnowledgeEntry being the one proven case, with
future CapabilityMetadata and Workflow state as the other two anticipated
cases. This module is that anticipated case arriving: concrete Resources
an Adapter needs to do its job.

Per K1.6 §2's discipline ("prove every field... reject unproven"), the
two Resource types implemented here are the two with actual evidence in
the codebase:
    - HTTPClientResource: wraps core.runtime.network.client, a real,
      already-shared, already-lifecycle-managed (close_client()) global
      httpx.AsyncClient every network-calling Adapter needs.
    - ModelResource: represents one (host, model_tag) binding an LLM
      Adapter is currently using -- real because
      core/provider_mesh.py's OllamaProvider already carries exactly
      these two fields (self.model, self._host) per instance today; this
      just gives that pairing an explicit, identified, Resource-shaped
      existence instead of being two constructor arguments with no
      independent identity.

GPU, Filesystem, Browser Session, Database, MCP Server (also named as
examples in the K2.3 prompt) are not implemented here -- there is no
Adapter in this session's actual scope that needs them (only
LLM_COMPLETION is registered, per capability.py's CapabilityType
docstring). Declaring Resource types with no consumer would repeat
exactly the mistake K1.6 found and corrected in the original Resource
field audit.
"""
from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ResourceLifecycle:
    """Lifecycle values for Resources defined in this module. Per K1.6 §4
    ("each Resource type owns its own lifecycle enum; the Protocol only
    owns the guarantee that one exists"), this is NOT a universal
    lifecycle shared by every Resource type in the system -- it is the
    one CapabilityResource-family types in this module use.
    """
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    CLOSED = "closed"


@dataclass
class HTTPClientResource:
    """Resource wrapping the shared core.runtime.network.client
    singleton. identity/lifecycle/version/dependencies/trust/provenance
    fields per K1.6 §3's Resource Protocol. Note (DEBT-009, resolved
    July 22, 2026): the ratified Constitution's Invariant 4 is
    three-field (identity/lifecycle/provenance); version/dependencies/
    trust here are an additive K2.3 engineering choice, not a
    Constitution-mandated shape. See KNOWN_ISSUES.md."""
    resource_id: str = "http-client-shared"
    lifecycle_state: str = ResourceLifecycle.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = 0.0
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    trust: float = 1.0
    provenance: str = "core.runtime.network.client"

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ModelResource:
    """Resource representing one (host, model_tag) LLM binding.

    resource_id is deterministic (f"model:{host}:{model_tag}") so
    repeated binds of the same host+model return the same Resource
    identity rather than minting a new one per call -- consistent with
    K1.6 §6's "cross-resource references are always by ID" rule and
    avoiding unbounded Resource growth for what is, in practice, a small
    fixed set of (host, model) pairs actually used in any one deployment.
    """
    resource_id: str
    model_tag: str
    host: str
    lifecycle_state: str = ResourceLifecycle.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = 0.0
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=lambda: ["http-client-shared"])
    trust: float = 1.0
    provenance: str = "core.provider_mesh"

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class ResourceManager:
    """Owns Resource lifetime and binding, per the K2.3 prompt's flow:
    ExecutionRuntime -> ResourceManager -> Capability -> Adapter -> Provider.

    No global state, no singleton lookup from inside an Adapter -- an
    Adapter is handed a ResourceManager instance explicitly by
    AdapterRuntime.execute() and calls get_http_client_resource() /
    bind_model_resource() on it, consistent with the K2.3 prompt's
    explicit "No global state. No singleton lookups. No hidden
    dependencies" instruction for Resource Binding.
    """

    def __init__(self):
        self._resources: Dict[str, Any] = {}
        http_resource = HTTPClientResource()
        self._resources[http_resource.resource_id] = http_resource

    def get_http_client_resource(self) -> HTTPClientResource:
        return self._resources["http-client-shared"]

    def bind_model_resource(self, model_tag: str, host: str) -> ModelResource:
        resource_id = f"model:{host}:{model_tag}"
        existing = self._resources.get(resource_id)
        if existing is not None:
            return existing
        resource = ModelResource(resource_id=resource_id, model_tag=model_tag,
                                  host=host)
        self._resources[resource_id] = resource
        return resource

    def get(self, resource_id: str) -> Optional[Any]:
        return self._resources.get(resource_id)

    def stats(self) -> Dict[str, Any]:
        return {
            "total_resources": len(self._resources),
            "resource_ids": list(self._resources.keys()),
        }
