"""
core/capabilities/registry.py — K2.3 Capability Registry

Registry responsibilities per the K2.3 session prompt: registration,
discovery, validation, capability lookup, adapter resolution, lifecycle
management. "The registry owns metadata. It does NOT execute." -- that
last sentence is load-bearing: CapabilityRegistry has no execute()/
invoke() method anywhere in this file. Execution is AdapterRuntime's job
(adapter_runtime.py), matching the same Registry/Runtime split K1.5
already established for WorkerRegistry vs. ExecutionRuntime
(OCBRAIN_K1_5_KERNEL_API_SERVICE_MODEL.md §2.1: "Registry answers 'what
exists,' Resolver answers 'which one, right now'").

Composition-root-only registration, no auto-discovery -- consistent with
the same rule already applied to WorkerRegistry
(core/runtime/worker_registry.py) and explicitly required by the K2.3
prompt ("No global state. No singleton lookups. No hidden dependencies").
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from core.capabilities.capability import Adapter, CapabilityContract

logger = logging.getLogger("ocbrain.capabilities.registry")


class CapabilityRegistrationError(Exception):
    """Raised when an Adapter is registered for a capability_type that
    has no CapabilityContract yet, or a contract is registered twice."""


class CapabilityRegistry:
    def __init__(self):
        self._contracts: Dict[str, CapabilityContract] = {}
        self._adapters: Dict[str, List[Adapter]] = {}

    def register_capability(self, contract: CapabilityContract) -> None:
        """Register a capability type's metadata. Must happen before any
        register_adapter() call for that capability_type -- an Adapter
        with no declared Capability is a configuration error, not
        something to infer silently (LAW 4, Determinism Over Magic)."""
        if contract.capability_type in self._contracts:
            raise CapabilityRegistrationError(
                f"Capability '{contract.capability_type}' already registered "
                f"-- re-registration would silently replace metadata other "
                f"code may already hold a reference to.")
        self._contracts[contract.capability_type] = contract
        self._adapters.setdefault(contract.capability_type, [])
        logger.info("[CapabilityRegistry] Registered capability: %s",
                    contract.capability_type)

    def register_adapter(self, capability_type: str, adapter: Adapter) -> None:
        """Register one Adapter as a fulfiller of capability_type.
        Adapters are appended in priority order -- AdapterRuntime tries
        them in registration order (subject to health/availability
        ranking), matching provider_mesh.py's existing, proven ordering
        convention for LLM providers."""
        if capability_type not in self._contracts:
            raise CapabilityRegistrationError(
                f"Cannot register adapter '{getattr(adapter, 'adapter_name', adapter)}' "
                f"for unknown capability '{capability_type}' -- call "
                f"register_capability() first.")
        self._adapters[capability_type].append(adapter)
        logger.info("[CapabilityRegistry] Registered adapter '%s' for "
                    "capability '%s'",
                    getattr(adapter, "adapter_name", adapter), capability_type)

    def get_contract(self, capability_type: str) -> Optional[CapabilityContract]:
        return self._contracts.get(capability_type)

    def get_adapters(self, capability_type: str) -> List[Adapter]:
        """Returns a *copy* of the adapter list -- callers must not be
        able to mutate the registry's own list by mutating what this
        returns."""
        return list(self._adapters.get(capability_type, []))

    def list_capabilities(self) -> List[str]:
        return list(self._contracts.keys())

    def validate(self) -> List[str]:
        """Returns a list of validation problems (empty = valid).
        A capability with zero registered adapters is not an error by
        itself (a capability may be declared ahead of having a backend --
        see CapabilityType's docstring) but is worth surfacing."""
        problems = []
        for capability_type, adapters in self._adapters.items():
            if not adapters:
                problems.append(
                    f"Capability '{capability_type}' has no registered "
                    f"adapters (declared but unfulfilled)")
        return problems

    def stats(self) -> Dict[str, int]:
        return {
            "total_capabilities": len(self._contracts),
            "total_adapters": sum(len(a) for a in self._adapters.values()),
            "unfulfilled_capabilities": len(self.validate()),
        }
