"""
core/capabilities/adapters/openai_compat_adapter.py — K2.3

Third-tier LLM_COMPLETION fallback, wrapping
core/provider_mesh.py's GenericOpenAICompatibleProvider directly. Only
actually attempted by AdapterRuntime if both ModelRouterAdapter and
OllamaAdapter fail or are unavailable -- GenericOpenAICompatibleProvider
already refuses to activate against its own default localhost:8080
endpoint unless global.openai_compat_url is explicitly configured (see
provider_mesh.py's is_available() override), so in an unconfigured
deployment this adapter correctly reports unavailable rather than
attempting a connection nobody asked for.
"""
from __future__ import annotations

import time

from core.capabilities.capability import BaseAdapter, CapabilityRequest, CapabilityResult, CapabilityType
from core.capabilities.resource import ResourceManager
from core.provider_mesh import GenericOpenAICompatibleProvider


class OpenAICompatAdapter(BaseAdapter):
    adapter_name = "OpenAICompatAdapter"
    capability_type = CapabilityType.LLM_COMPLETION

    def __init__(self, endpoint: str = "http://localhost:8080/v1",
                 model: str = "local-model"):
        super().__init__()
        self._provider = GenericOpenAICompatibleProvider(endpoint=endpoint,
                                                           model=model)

    def is_available(self) -> bool:
        # Delegate to the wrapped provider's own configuration-aware
        # availability check rather than duplicating its logic.
        return super().is_available() and self._provider.is_available()

    async def execute(self, request: CapabilityRequest,
                       resources: ResourceManager) -> CapabilityResult:
        prompt = request.payload.get("subtask") or request.payload.get("prompt")
        if not prompt:
            return CapabilityResult(
                success=False,
                error="OpenAICompatAdapter requires payload['subtask'] or "
                      "payload['prompt']",
                adapter_used=self.adapter_name,
            )

        start = time.time()
        try:
            answer = await self._provider.generate(prompt)
        except Exception as e:
            return CapabilityResult(
                success=False,
                error=f"GenericOpenAICompatibleProvider error: {e}",
                adapter_used=self.adapter_name,
                duration_ms=(time.time() - start) * 1000,
            )

        return CapabilityResult(
            success=True,
            output=answer,
            adapter_used=self.adapter_name,
            duration_ms=(time.time() - start) * 1000,
        )
