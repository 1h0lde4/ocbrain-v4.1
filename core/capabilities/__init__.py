"""
core/capabilities/ — K2.3 Capability Runtime.

Capability: what the system can do (provider-independent).
Adapter: how a capability is fulfilled by one specific provider.
Resource: state an Adapter needs, with identity and lifecycle
    (extends the K1.6-frozen Resource Model).
CapabilityRegistry: metadata only -- registration/discovery/lookup.
AdapterRuntime: execution -- selection, fallback, failure isolation.

See K2_3_CAPABILITY_RUNTIME_REPORT.md for the full design rationale,
scope decisions, and what remains legacy/out-of-scope this session.
"""
from core.capabilities.capability import (
    Adapter,
    BaseAdapter,
    CapabilityContract,
    CapabilityRequest,
    CapabilityResult,
    CapabilityType,
)
from core.capabilities.registry import CapabilityRegistry, CapabilityRegistrationError
from core.capabilities.resource import HTTPClientResource, ModelResource, ResourceManager
from core.capabilities.adapter_runtime import AdapterRuntime

__all__ = [
    "Adapter", "BaseAdapter", "CapabilityContract", "CapabilityRequest",
    "CapabilityResult", "CapabilityType", "CapabilityRegistry",
    "CapabilityRegistrationError", "HTTPClientResource", "ModelResource",
    "ResourceManager", "AdapterRuntime",
]
