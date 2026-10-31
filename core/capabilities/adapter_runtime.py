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

import logging
import time
from typing import List, Optional

from core.capabilities.capability import Adapter, CapabilityRequest, CapabilityResult
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
        """
        self._total_invocations += 1
        start = time.time()

        if request is None:
            request = CapabilityRequest(capability_type=capability_type,
                                         payload=payload)

        contract = self._registry.get_contract(capability_type)
        if contract is None:
            self._total_failures += 1
            return CapabilityResult(
                success=False,
                error=f"Unknown capability type '{capability_type}' -- "
                      f"no CapabilityContract registered.",
                duration_ms=(time.time() - start) * 1000,
            )

        adapters = self._registry.get_adapters(capability_type)
        if not adapters:
            self._total_failures += 1
            return CapabilityResult(
                success=False,
                error=f"Capability '{capability_type}' has no registered "
                      f"adapters.",
                duration_ms=(time.time() - start) * 1000,
            )

        ranked = self._rank_adapters(adapters)

        last_error = "no adapters attempted"
        for adapter in ranked:
            adapter_name = getattr(adapter, "adapter_name", type(adapter).__name__)
            attempt_start = time.time()
            try:
                result = await adapter.execute(request, self._resources)
            except Exception as e:
                last_error = f"{adapter_name}: {type(e).__name__}: {e}"
                self._mark_failure(adapter)
                await self._emit_event("adapter.failed", {
                    "capability_type": capability_type,
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
                await self._emit_event("adapter.invoked", {
                    "capability_type": capability_type,
                    "adapter": adapter_name,
                    "duration_ms": duration_ms,
                    "trace_id": request.trace_id,
                })
                return result

            last_error = result.error or f"{adapter_name} returned success=False"
            self._mark_failure(adapter)
            await self._emit_event("adapter.failed", {
                "capability_type": capability_type,
                "adapter": adapter_name,
                "error": last_error,
                "trace_id": request.trace_id,
            })

        self._total_failures += 1
        return CapabilityResult(
            success=False,
            error=f"All {len(ranked)} adapter(s) failed for "
                  f"'{capability_type}'. Last: {last_error}",
            duration_ms=(time.time() - start) * 1000,
            metadata={"adapters_tried": [
                getattr(a, "adapter_name", type(a).__name__) for a in ranked]},
        )

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
