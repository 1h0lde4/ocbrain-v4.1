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


class ModelRouterAdapter(BaseAdapter):
    """Wraps an existing ModelRouter instance. Reads
    request.payload["module_name"], request.payload["subtask"], and
    request.payload["context"] (the same three positional arguments
    ModelRouter.route() already takes) -- chosen to keep the request
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

        if not module_name:
            return CapabilityResult(
                success=False,
                error="ModelRouterAdapter requires payload['module_name']",
                adapter_used=self.adapter_name,
            )

        start = time.time()
        route_result = await self._model_router.route(module_name, subtask, context)
        duration_ms = (time.time() - start) * 1000

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
