"""
core/capabilities/adapters/model_router_adapter.py — K2.3

DOCUMENTED COMPATIBILITY WRAPPER (K2.3 session prompt, Legacy Module
Migration: "Modules may temporarily remain as compatibility wrappers.
However: Every compatibility wrapper must be documented." -- this
docstring is that documentation).

What this wraps and why:
    core/model_router.py's ModelRouter is not simple request/response
    plumbing -- it owns a real, tested, production behavior this session
    was not asked to touch and should not put at risk: a per-module
    bootstrap -> shadow -> native maturity lifecycle, with training-pair
    recording, EMA maturity scoring, promotion, and regression rollback
    (SHADOW_PROMOTE_THRESHOLD, REGRESSION_THRESHOLD, etc.). None of this
    is mentioned anywhere in the K2.3 prompt, and the prompt's "Frozen
    Architecture" section is explicit that architectural issues found
    mid-session should produce an ADR, not a silent redesign.

    Rather than rip this out and replace it with a generic LLM adapter
    (which would delete real, working promotion/rollback logic the K2.3
    prompt never asked to remove), this adapter satisfies the new
    Adapter Protocol by delegating directly to the existing, unmodified
    ModelRouter singleton. This is what makes
    "Workers depend only on Capabilities... Legacy module dispatch is no
    longer part of the canonical runtime" true in the sense that matters
    -- PlannerWorker no longer imports or calls ModelRouter directly
    (core/workers/planner.py's _dispatch_module now goes through
    AdapterRuntime) -- without gambling with a maturity-tracking system
    this session has no evidence-based mandate to change.

    ModelRouterAdapter is registered FIRST in main.py's adapter list for
    CapabilityType.LLM_COMPLETION, so it is AdapterRuntime's default
    choice in production; OllamaAdapter/OpenAICompatAdapter (this same
    package) exist alongside it as the "pure" Capability/Adapter path
    with no maturity-tracking behavior attached, proving the abstraction
    works end-to-end against a real, unwrapped provider -- not only as a
    proxy for legacy code.

Sunset horizon: recommended in the K2.3 Legacy Dispatch Migration Report
-- once ModelRouter's maturity/promotion logic is itself reviewed and
either kept as a deliberate CapabilityResolver-level policy or migrated,
this wrapper can be removed. Not scheduled this session (K3, per the
K2.3 prompt's own Governance ADR precedent of deferring architecture
changes discovered mid-session rather than making them unilaterally).
"""
from __future__ import annotations

import time

from core.capabilities.capability import BaseAdapter, CapabilityRequest, CapabilityResult, CapabilityType
from core.capabilities.resource import ResourceManager
from core.model_router import ModelRouter
from core.runtime.execution_outcome import ExecutionOutcome, FailureType

# FZ-02 / batch B2a. Outcomes whose adapter-level result is deliberately left
# exactly as it was (success=True): stalled / hard-deadline / completed-with-
# partial-output. Their semantics (decision D2) change in B2b, not here, and
# tests/test_fz02_provider_failure.py pins them until then.
_UNCHANGED_PENDING_B2B = frozenset({
    FailureType.STALLED,
    FailureType.HARD_DEADLINE,
    FailureType.COMPLETED_WITH_PARTIAL_OUTPUT,
})

# Fixed, opaque messages: this string can reach end users (the planner raises it
# and the orchestrator renders it), so it never carries exception text, hosts or
# URLs. The provider's own opaque error reference is appended when present.
_FAILURE_MESSAGES = {
    FailureType.PROVIDER_FAILURE: "model provider failure",
    FailureType.EMPTY_RESPONSE: "model returned an empty response",
    FailureType.CANCELLED: "model execution was cancelled",
    FailureType.VALIDATION_ERROR: "model request failed validation",
    FailureType.OTHER_FAILURE: "model execution failed",
}


class ModelRouterAdapter(BaseAdapter):
    """Wraps an existing ModelRouter instance. Reads
    request.payload["module_name"], request.payload["subtask"],
    request.payload["context"], and request.payload["scope"] (CTX-SCOPE-001;
    optional, defaults to "" -- unscoped/legacy shared behavior, matching
    ModelRouter.route()'s own default) -- chosen to keep the request
    shape a direct, obvious mirror of the wrapped call, not a new
    convention invented for its own sake.
    """
    adapter_name = "ModelRouterAdapter"
    capability_type = CapabilityType.LLM_COMPLETION

    def __init__(self, model_router: ModelRouter):
        super().__init__()
        self._model_router = model_router

    async def execute(self, request: CapabilityRequest,
                       resources: ResourceManager) -> CapabilityResult:
        module_name = request.payload.get("module_name")
        subtask = request.payload.get("subtask", "")
        context = request.payload.get("context")
        scope = request.payload.get("scope", "")

        if not module_name:
            return CapabilityResult(
                success=False,
                error="ModelRouterAdapter requires payload['module_name']",
                adapter_used=self.adapter_name,
            )

        start = time.time()
        route_result = await self._model_router.route(module_name, subtask, context, scope=scope)
        duration_ms = (time.time() - start) * 1000

        # FZ-02 / B2a: this used to return success=True unconditionally and never
        # read execution_detail, so a failed generation completed as a success.
        # Only a real ExecutionOutcome is classified; a RouteResult without one
        # (every route() branch except the monitored long-form stream) is
        # unchanged. Fail closed: anything that is not SUCCESS and not in the
        # pinned set is a failure, including types route() cannot emit today.
        detail = route_result.execution_detail
        if (isinstance(detail, ExecutionOutcome)
                and detail.failure_type != FailureType.SUCCESS
                and detail.failure_type not in _UNCHANGED_PENDING_B2B):
            return self._failure_result(route_result, detail, duration_ms)

        return CapabilityResult(
            success=True,
            output=route_result.answer,
            adapter_used=self.adapter_name,
            duration_ms=duration_ms,
            metadata={
                "source": route_result.source,
                "similarity": route_result.similarity,
                "route_latency_ms": route_result.latency_ms,
            },
        )

    def _failure_result(self, route_result, detail: ExecutionOutcome,
                        duration_ms: float) -> CapabilityResult:
        failure_type = detail.failure_type
        failure_value = getattr(failure_type, "value", str(failure_type))
        error = _FAILURE_MESSAGES.get(
            failure_type, f"model execution did not complete ({failure_value})")
        error_id = (detail.detail or {}).get("error_id", "")
        if error_id:
            error = f"{error} (ref {error_id})"
        metadata = {
            "source": route_result.source,
            "similarity": route_result.similarity,
            "route_latency_ms": route_result.latency_ms,
            "failure_type": failure_value,
            "retryable": detail.retryable,
        }
        if error_id:
            metadata["error_id"] = error_id
        if detail.model:
            metadata["model"] = detail.model
        if detail.partial_output:
            # Preserved for the result channel (D1); never placed in `output`,
            # so a failed generation cannot be consumed as content.
            metadata["partial_output"] = detail.partial_output
        return CapabilityResult(
            success=False,
            output=None,
            error=error,
            adapter_used=self.adapter_name,
            duration_ms=duration_ms,
            metadata=metadata,
        )
