"""
core/capabilities/adapter_runtime.py — K2.3 Adapter Runtime

AdapterRuntime is the execution service (CapabilityRegistry is metadata-
only, per registry.py's docstring). Responsibilities per the K2.3
session prompt: adapter selection, provider selection, adapter lifecycle,
execution delegation, failure isolation, fallback support, capability
diagnostics.

The selection/fallback/health-ranking logic below is a deliberate, direct
generalization of core/provider_mesh.py's generate_with_fallback() --
already a proven, production-tested pattern for exactly this problem
(try healthy adapters in ranked order, fall back on failure, respect
cooldowns, never leave every adapter unavailable without a forced
choice). Re-deriving a different selection algorithm from scratch here
would violate the Kernel Constitution's Law of Evidence over Assumption
("a pattern... converged on is preferred over one adopted for being
new") for no benefit -- the two problems (which LLM provider, which
capability adapter) are the same shape.

Failure containment: invoke() never raises. Every failure path returns a
CapabilityResult(success=False, ...), matching ExecutionRuntime.invoke()
and WorkflowRuntime.execute()'s established never-raise contract
elsewhere in this runtime (Kernel Constitution, Law of Failure
Containment).
"""
from __future__ import annotations

import dataclasses
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from core.capabilities.capability import Adapter, CapabilityRequest, CapabilityResult
from core.capabilities.descriptors import (
    CapabilityStatus,
    FALLTHROUGH_STATUSES,
    INVOCABLE_LIFECYCLES,
    OperationSpec,
    REQUEST_LEVEL_STATUSES,
)
from core.capabilities.registry import CapabilityRegistry
from core.capabilities.resource import ResourceManager

logger = logging.getLogger("ocbrain.capabilities.adapter_runtime")


class AdapterRuntime:
    def __init__(self, registry: CapabilityRegistry,
                 resource_manager: ResourceManager,
                 event_stream=None):
        self._registry = registry
        self._resources = resource_manager
        self._event_stream = event_stream
        self._total_invocations = 0
        self._total_failures = 0

    async def invoke(self, capability_type: str,
                      request: Optional[CapabilityRequest] = None,
                      **payload) -> CapabilityResult:
        """Invoke a capability. Accepts either a pre-built
        CapabilityRequest or payload=... kwargs for convenience callers
        (mirrors ExecutionRuntime.invoke()'s query=... convenience
        parameter, core/runtime/execution_runtime.py).

        ADR-CAP-02 additions (all inert for a legacy contract that declares
        no operations and for legacy adapters that return only
        success/error):

          * operation resolution + fail-closed validation against the
            contract (unknown operation / missing required payload key ->
            INVALID_REQUEST, no adapter is called);
          * lifecycle gate (DISABLED / RETIRED -> UNAVAILABLE);
          * adapters that declare supported_operations are only offered
            operations they implement;
          * status-aware failure handling: a *request-level* status
            (unsupported / malformed / unreadable / ...) is not an adapter
            fault -- it never degrades adapter health. UNSUPPORTED and
            DEPENDENCY_UNAVAILABLE fall through to the next adapter; the
            other request-level statuses are returned immediately;
          * runtime-known provenance is stamped onto every result.
        """
        self._total_invocations += 1
        start = time.time()

        if request is None:
            request = CapabilityRequest(capability_type=capability_type,
                                         payload=payload)

        contract = self._registry.get_contract(capability_type)
        if contract is None:
            self._total_failures += 1
            return CapabilityResult.of(
                CapabilityStatus.UNAVAILABLE,
                error=f"Unknown capability type '{capability_type}' -- "
                      f"no CapabilityContract registered.",
                duration_ms=(time.time() - start) * 1000,
            )

        lifecycle_of = getattr(self._registry, "get_lifecycle", None)
        if lifecycle_of is not None:
            record = lifecycle_of(capability_type)
            if record.state not in INVOCABLE_LIFECYCLES:
                self._total_failures += 1
                return CapabilityResult.of(
                    CapabilityStatus.UNAVAILABLE,
                    error=f"Capability '{capability_type}' is "
                          f"{record.state}"
                          + (f" ({record.reason})" if record.reason else "")
                          + (f"; replaced by '{record.replaced_by}'"
                             if record.replaced_by else "") + ".",
                    duration_ms=(time.time() - start) * 1000,
                )

        operation_spec: Optional[OperationSpec] = None
        if contract.operations:
            operation_spec = contract.get_operation(request.operation)
            if operation_spec is None:
                self._total_failures += 1
                return CapabilityResult.of(
                    CapabilityStatus.INVALID_REQUEST,
                    error=f"Capability '{capability_type}' has no operation "
                          f"'{request.operation}' (declared: "
                          f"{list(contract.operation_names())}).",
                    duration_ms=(time.time() - start) * 1000,
                    provenance=self._base_provenance(
                        capability_type, request.operation, contract,
                        request),
                )
            missing = [k for k in operation_spec.requires
                       if _is_missing(request.payload.get(k))]
            if missing:
                self._total_failures += 1
                return CapabilityResult.of(
                    CapabilityStatus.INVALID_REQUEST,
                    error=f"Operation '{capability_type}.{operation_spec.name}' "
                          f"requires payload key(s) {missing}.",
                    duration_ms=(time.time() - start) * 1000,
                    provenance=self._base_provenance(
                        capability_type, operation_spec.name, contract,
                        request),
                )
            if request.operation != operation_spec.name:
                # Resolve the default so adapters always see a concrete name.
                request = dataclasses.replace(
                    request, operation=operation_spec.name)

        adapters = self._registry.get_adapters(capability_type)
        if not adapters:
            self._total_failures += 1
            return CapabilityResult.of(
                CapabilityStatus.UNAVAILABLE,
                error=f"Capability '{capability_type}' has no registered "
                      f"adapters.",
                duration_ms=(time.time() - start) * 1000,
            )
        if operation_spec is not None:
            adapters = [
                a for a in adapters
                if not getattr(a, "supported_operations", ())
                or operation_spec.name in a.supported_operations]
            if not adapters:
                self._total_failures += 1
                return CapabilityResult.of(
                    CapabilityStatus.UNAVAILABLE,
                    error=f"No registered adapter of '{capability_type}' "
                          f"implements operation '{operation_spec.name}'.",
                    duration_ms=(time.time() - start) * 1000,
                    provenance=self._base_provenance(
                        capability_type, operation_spec.name, contract,
                        request),
                )

        ranked = self._rank_adapters(adapters)
        operation_name = operation_spec.name if operation_spec else request.operation

        last_error = "no adapters attempted"
        hard_failures = 0
        declined: List[Tuple[str, CapabilityResult]] = []
        for adapter in ranked:
            adapter_name = getattr(adapter, "adapter_name", type(adapter).__name__)
            attempt_start = time.time()
            try:
                result = await adapter.execute(request, self._resources)
            except Exception as e:
                last_error = f"{adapter_name}: {type(e).__name__}: {e}"
                hard_failures += 1
                self._mark_failure(adapter)
                await self._emit_event("adapter.failed", {
                    "capability_type": capability_type,
                    "operation": operation_name,
                    "adapter": adapter_name,
                    "error": last_error,
                    "trace_id": request.trace_id,
                })
                continue

            duration_ms = (time.time() - attempt_start) * 1000
            if result.success:
                self._mark_success(adapter)
                result.adapter_used = result.adapter_used or adapter_name
                result.duration_ms = result.duration_ms or duration_ms
                self._stamp_provenance(result, adapter, adapter_name,
                                       capability_type, operation_name,
                                       contract, request)
                await self._emit_event("adapter.invoked", {
                    "capability_type": capability_type,
                    "operation": operation_name,
                    "contract_version": contract.version,
                    "adapter": adapter_name,
                    "adapter_version": getattr(adapter, "adapter_version", ""),
                    "status": result.status,
                    "duration_ms": duration_ms,
                    "trace_id": request.trace_id,
                })
                return result

            if result.status in REQUEST_LEVEL_STATUSES:
                # The adapter answered correctly; the *request* cannot be
                # fulfilled (by it). No health penalty, no cooldown.
                result.adapter_used = result.adapter_used or adapter_name
                result.duration_ms = result.duration_ms or duration_ms
                self._stamp_provenance(result, adapter, adapter_name,
                                       capability_type, operation_name,
                                       contract, request)
                await self._emit_event("adapter.declined", {
                    "capability_type": capability_type,
                    "operation": operation_name,
                    "adapter": adapter_name,
                    "status": result.status,
                    "error": result.error,
                    "trace_id": request.trace_id,
                })
                if result.status in FALLTHROUGH_STATUSES:
                    declined.append((adapter_name, result))
                    continue
                self._total_failures += 1
                return result

            hard_failures += 1
            last_error = result.error or f"{adapter_name} returned success=False"
            self._mark_failure(adapter)
            await self._emit_event("adapter.failed", {
                "capability_type": capability_type,
                "operation": operation_name,
                "adapter": adapter_name,
                "status": result.status,
                "error": last_error,
                "trace_id": request.trace_id,
            })

        self._total_failures += 1
        if declined and hard_failures == 0:
            # Every adapter declined the same request without fault: report
            # the most informative decline (first, i.e. highest ranked), not a
            # generic "all adapters failed".
            first = declined[0][1]
            first.metadata["adapters_declined"] = [
                {"adapter": n, "status": r.status} for n, r in declined]
            return first
        return CapabilityResult(
            success=False,
            error=f"All {len(ranked)} adapter(s) failed for "
                  f"'{capability_type}'. Last: {last_error}",
            duration_ms=(time.time() - start) * 1000,
            metadata={"adapters_tried": [
                getattr(a, "adapter_name", type(a).__name__) for a in ranked]},
            provenance=self._base_provenance(
                capability_type, operation_name, contract, request),
        )

    @staticmethod
    def _base_provenance(capability_type: str, operation: str,
                         contract, request: CapabilityRequest) -> Dict[str, Any]:
        return {
            "capability_type": capability_type,
            "operation": operation,
            "contract_version": getattr(contract, "version", ""),
            "trace_id": request.trace_id,
        }

    @classmethod
    def _stamp_provenance(cls, result: CapabilityResult, adapter: Adapter,
                          adapter_name: str, capability_type: str,
                          operation: str, contract,
                          request: CapabilityRequest) -> None:
        """The runtime is the authority on identity facts: these keys
        overwrite whatever an adapter put there (an adapter may add its own
        implementation facts under other keys)."""
        result.provenance.update(cls._base_provenance(
            capability_type, operation, contract, request))
        result.provenance["adapter"] = {
            "name": adapter_name,
            "version": getattr(adapter, "adapter_version", ""),
        }

    def _rank_adapters(self, adapters: List[Adapter]) -> List[Adapter]:
        """Health/availability ranking -- direct generalization of
        provider_mesh._provider_available/_provider_health, applied to
        the Adapter Protocol instead of Provider."""
        available = [a for a in adapters if self._is_available(a)]
        if not available:
            # All in cooldown -- pick whichever recovers soonest, exactly
            # matching provider_mesh.generate_with_fallback's forced-
            # choice fallback rather than failing outright.
            soonest = min(adapters, key=lambda a: getattr(a, "cooldown_until", 0))
            logger.warning("[AdapterRuntime] All adapters in cooldown for "
                            "this request; forced choice: %s",
                            getattr(soonest, "adapter_name", soonest))
            return [soonest]
        return sorted(available, key=self._health, reverse=True)

    @staticmethod
    def _is_available(adapter: Adapter) -> bool:
        checker = getattr(adapter, "is_available", None)
        if checker is None:
            return True
        try:
            return bool(checker())
        except Exception:
            logger.warning("[AdapterRuntime] availability check failed for %s",
                            getattr(adapter, "adapter_name", adapter))
            return False

    @staticmethod
    def _health(adapter: Adapter) -> int:
        return int(getattr(adapter, "health_score", 100))

    @staticmethod
    def _mark_success(adapter: Adapter) -> None:
        marker = getattr(adapter, "mark_success", None)
        if marker is not None:
            marker()

    @staticmethod
    def _mark_failure(adapter: Adapter) -> None:
        marker = getattr(adapter, "mark_failure", None)
        if marker is not None:
            marker()

    async def _emit_event(self, event_type: str, payload: dict) -> None:
        if self._event_stream is None:
            return
        try:
            await self._event_stream.append(
                event_type=event_type, source="AdapterRuntime", payload=payload)
        except Exception as e:
            logger.warning("[AdapterRuntime] event emission failed: %s", e)

    def stats(self) -> dict:
        return {
            "total_invocations": self._total_invocations,
            "total_failures": self._total_failures,
            **self._registry.stats(),
        }


def _is_missing(value: Any) -> bool:
    """A required payload key counts as missing when absent, None, or an
    empty str/list/tuple/dict. (0 and False are real values.)"""
    if value is None:
        return True
    if isinstance(value, (str, list, tuple, dict)) and len(value) == 0:
        return True
    return False
