"""
core/capabilities/adapters/ollama_adapter.py — K2.3

The "pure" LLM_COMPLETION adapter: wraps core/provider_mesh.py's
OllamaProvider directly (reused, not reimplemented -- Law of Contract
Stability), with no module-maturity layer in between. Demonstrates the
Capability/Adapter/Resource chain working end-to-end against a real
provider, independent of ModelRouterAdapter's legacy-compatibility role.

Registered as a fallback behind ModelRouterAdapter in main.py's adapter
list for LLM_COMPLETION -- if the maturity-tracked path is unavailable
for some reason, AdapterRuntime falls through to this adapter rather
than failing the capability outright, the same fallback discipline
provider_mesh.generate_with_fallback() already applies one layer down.
"""
from __future__ import annotations

import time

from core.capabilities.capability import BaseAdapter, CapabilityRequest, CapabilityResult, CapabilityType
from core.capabilities.resource import ResourceManager
from core.provider_mesh import OllamaProvider


class OllamaAdapter(BaseAdapter):
    """Reads request.payload["subtask"] as the prompt (falls back to
    payload["prompt"] for direct, non-module-shaped callers). Binds a
    ModelResource via ResourceManager for the (host, model) pair actually
    used, per the K2.3 prompt's Resource Binding flow (ExecutionRuntime
    -> ResourceManager -> Capability -> Adapter -> Provider).
    """
    adapter_name = "OllamaAdapter"
    capability_type = CapabilityType.LLM_COMPLETION

    def __init__(self, model: str = "mistral",
                 host: str = "http://localhost:11434"):
        super().__init__()
        self._model = model
        self._host = host
        self._provider = OllamaProvider(model=model)

    async def execute(self, request: CapabilityRequest,
                       resources: ResourceManager) -> CapabilityResult:
        prompt = request.payload.get("subtask") or request.payload.get("prompt")
        if not prompt:
            return CapabilityResult(
                success=False,
                error="OllamaAdapter requires payload['subtask'] or "
                      "payload['prompt']",
                adapter_used=self.adapter_name,
            )

        # Real resource binding, not a decorative call: this is the same
        # (host, model) pair self._provider actually uses -- the
        # ResourceManager now has an identified, queryable record of it.
        model_resource = resources.bind_model_resource(
            model_tag=self._model, host=self._host)
        resources.get_http_client_resource()  # asserted available; provider_mesh's shared client is what OllamaProvider ultimately uses

        start = time.time()
        try:
            answer = await self._provider.generate(prompt)
        except Exception as e:
            return CapabilityResult(
                success=False,
                error=f"OllamaProvider error: {e}",
                adapter_used=self.adapter_name,
                duration_ms=(time.time() - start) * 1000,
            )

        return CapabilityResult(
            success=True,
            output=answer,
            adapter_used=self.adapter_name,
            duration_ms=(time.time() - start) * 1000,
            metadata={"model_resource_id": model_resource.resource_id},
        )
