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
from typing import Any, Dict, List, Optional

from core.capabilities.capability import Adapter, CapabilityContract
from core.capabilities.descriptors import (
    CapabilityLifecycle,
    DISCOVERABLE_LIFECYCLES,
    LIFECYCLE_VALUES,
    LifecycleRecord,
    OperationRef,
    TypeSpec,
    contract_major,
    implements_contract_major,
)

logger = logging.getLogger("ocbrain.capabilities.registry")


class CapabilityRegistrationError(Exception):
    """Raised when an Adapter is registered for a capability_type that
    has no CapabilityContract yet, or a contract is registered twice."""


class CapabilityRegistry:
    def __init__(self):
        self._contracts: Dict[str, CapabilityContract] = {}
        self._adapters: Dict[str, List[Adapter]] = {}
        # ADR-CAP-02: runtime lifecycle state per capability type. Absent
        # entry == ACTIVE, so every pre-existing registration behaves
        # exactly as before.
        self._lifecycle: Dict[str, LifecycleRecord] = {}

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
        problems = contract.structural_problems()
        if problems:
            raise CapabilityRegistrationError(
                "Invalid CapabilityContract: " + "; ".join(problems))
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
        self._check_adapter_compatibility(capability_type, adapter)
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

    # ── ADR-CAP-02: compatibility, replacement, lifecycle, descriptors ──────

    def _check_adapter_compatibility(self, capability_type: str,
                                     adapter: Adapter) -> None:
        """Fail closed when an adapter *declares* something incompatible with
        the contract it is being registered under. Undeclared (legacy)
        adapters are accepted unchanged."""
        name = getattr(adapter, "adapter_name", adapter)
        contract = self._contracts[capability_type]

        declared = getattr(adapter, "implements_contract", "") or ""
        if declared:
            adapter_major = implements_contract_major(declared)
            registry_major = contract_major(contract.version)
            if adapter_major is None or registry_major is None:
                raise CapabilityRegistrationError(
                    f"Adapter '{name}' declares implements_contract="
                    f"{declared!r} / contract version {contract.version!r}: "
                    f"cannot compare majors.")
            if adapter_major != registry_major:
                raise CapabilityRegistrationError(
                    f"Adapter '{name}' implements contract major "
                    f"{adapter_major} but capability '{capability_type}' is "
                    f"at contract {contract.version} (major {registry_major}) "
                    f"-- incompatible; not registering.")

        supported = tuple(getattr(adapter, "supported_operations", ()) or ())
        if supported:
            unknown = [o for o in supported
                       if o not in contract.operation_names()]
            if unknown:
                raise CapabilityRegistrationError(
                    f"Adapter '{name}' declares unsupported-by-contract "
                    f"operation(s) {unknown} for '{capability_type}' "
                    f"(declared: {list(contract.operation_names())}).")

    def deregister_adapter(self, capability_type: str,
                           adapter: "str | Adapter") -> bool:
        """Remove one implementation, leaving the capability's identity and
        contract untouched. The replace-an-implementation path is
        register_adapter(new) + deregister_adapter(old).

        ``adapter`` is the adapter's ``adapter_name`` (removes the FIRST
        registered adapter with that name -- names are unique per capability by
        convention, but legacy registrations that reuse a name are still
        accepted, so this never guesses beyond one) or the adapter instance
        itself (exact). Returns whether anything was removed."""
        adapters = self._adapters.get(capability_type)
        if not adapters:
            return False
        for i, a in enumerate(adapters):
            hit = (a is adapter) if not isinstance(adapter, str) \
                else getattr(a, "adapter_name", None) == adapter
            if hit:
                del adapters[i]
                logger.info("[CapabilityRegistry] Deregistered adapter '%s' "
                            "from capability '%s'",
                            getattr(a, "adapter_name", a), capability_type)
                return True
        return False

    def set_lifecycle(self, capability_type: str, state: str, *,
                      reason: str = "", replaced_by: str = "") -> None:
        if capability_type not in self._contracts:
            raise CapabilityRegistrationError(
                f"Cannot set lifecycle of unknown capability "
                f"'{capability_type}'.")
        if state not in LIFECYCLE_VALUES:
            raise CapabilityRegistrationError(
                f"Unknown lifecycle state {state!r}.")
        if (self._lifecycle.get(capability_type, LifecycleRecord()).state
                == CapabilityLifecycle.RETIRED
                and state != CapabilityLifecycle.RETIRED):
            raise CapabilityRegistrationError(
                f"Capability '{capability_type}' is RETIRED (terminal).")
        self._lifecycle[capability_type] = LifecycleRecord(
            state=state, reason=reason, replaced_by=replaced_by)

    def get_lifecycle(self, capability_type: str) -> LifecycleRecord:
        return self._lifecycle.get(capability_type, LifecycleRecord())

    def is_discoverable(self, capability_type: str) -> bool:
        return self.get_lifecycle(capability_type).state in DISCOVERABLE_LIFECYCLES

    @staticmethod
    def _adapter_available(adapter: Adapter) -> bool:
        checker = getattr(adapter, "is_available", None)
        if checker is None:
            return True
        try:
            return bool(checker())
        except Exception:
            return False

    def describe(self, capability_type: str) -> Optional[Dict[str, Any]]:
        """Machine-readable, JSON-serializable projection of one capability:
        identity, contract version, operations (with structured I/O),
        lifecycle, and the implementations currently registered. Assembled
        from existing registry state -- there is no second store, and this is
        not a selector: it ranks and chooses nothing."""
        contract = self._contracts.get(capability_type)
        if contract is None:
            return None
        adapters = self._adapters.get(capability_type, [])
        return {
            "capability_type": contract.capability_type,
            "contract_version": contract.version,
            "description": contract.description,
            "is_general_purpose": contract.is_general_purpose,
            "side_effects": contract.side_effects,
            "default_operation": (
                contract.get_operation("").name
                if contract.get_operation("") else ""),
            "operations": [op.to_dict() for op in contract.operations],
            "lifecycle": self.get_lifecycle(capability_type).to_dict(),
            "implementations": [
                {
                    "adapter_name": getattr(a, "adapter_name", type(a).__name__),
                    "adapter_version": getattr(a, "adapter_version", ""),
                    "implements_contract": getattr(a, "implements_contract", ""),
                    "supported_operations": list(
                        getattr(a, "supported_operations", ()) or ()),
                    "available": self._adapter_available(a),
                }
                for a in adapters
            ],
        }

    def describe_all(self) -> List[Dict[str, Any]]:
        return [d for d in (self.describe(c) for c in sorted(self._contracts))
                if d is not None]

    def _structured_candidates(self, require_adapters: bool):
        for capability_type in sorted(self._contracts):
            if not self.is_discoverable(capability_type):
                continue
            if require_adapters and not self._adapters.get(capability_type):
                continue
            yield capability_type, self._contracts[capability_type]

    def find_consumers(self, value_type: TypeSpec, *,
                       require_adapters: bool = True) -> List[OperationRef]:
        """Operations that can structurally accept a value of ``value_type``.
        Input/output *compatibility* only -- no scoring, no selection."""
        found: List[OperationRef] = []
        for capability_type, contract in self._structured_candidates(
                require_adapters):
            for op in contract.operations:
                if any(t.accepts(value_type) for t in op.inputs):
                    found.append(OperationRef(capability_type, op.name))
        return found

    def find_producers(self, required_type: TypeSpec, *,
                       require_adapters: bool = True) -> List[OperationRef]:
        """Operations whose output structurally satisfies ``required_type``."""
        found: List[OperationRef] = []
        for capability_type, contract in self._structured_candidates(
                require_adapters):
            for op in contract.operations:
                if any(required_type.accepts(t) for t in op.outputs):
                    found.append(OperationRef(capability_type, op.name))
        return found

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
