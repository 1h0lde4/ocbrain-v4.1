"""
core/provider_mesh.py — Multi-LLM Provider Abstraction.

Provides a unified interface for generating text from any LLM backend.
Uses safe_llm_call (Phase 1) for timeout + concurrency control.
Uses cached_generate (Phase 2) for prompt caching before hitting the backend.

Providers:
  - OllamaProvider: calls local Ollama HTTP API (same pattern as classifier.py)
  - GenericOpenAICompatibleProvider: any OpenAI-compatible endpoint

Never exposes raw provider calls — always goes through generate_with_fallback().
"""
import abc
import time
import logging
from typing import List

from core.observability.tracer import span
from core.config import config as _config
from core.runtime.network import client as _network_client

logger = logging.getLogger("ocbrain.provider_mesh")


class Provider(abc.ABC):
    def __init__(self):
        self.health_score = 100
        self.consecutive_failures = 0
        self.last_failure_time = 0
        self.cooldown_until = 0

    @abc.abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate a response for the given prompt."""
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    def is_available(self) -> bool:
        """Check if provider is in cooldown."""
        return time.time() >= self.cooldown_until

    def mark_success(self):
        self.consecutive_failures = 0
        self.health_score = min(100, self.health_score + 5)

    def mark_failure(self, cooldown_seconds: int = 60):
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        self.health_score = max(0, self.health_score - 20)
        
        # Exponential cooldown: 60s, 120s, 240s...
        delay = cooldown_seconds * (2 ** (self.consecutive_failures - 1))
        self.cooldown_until = time.time() + min(delay, 3600) # Max 1 hour
        logger.warning(f"[ProviderMesh] {self.name} penalized. Score: {self.health_score}. Cooldown: {int(delay)}s")


class OllamaProvider(Provider):
    """
    Calls the local Ollama HTTP API.
    Mirrors the pattern used by core/classifier.py for consistency.
    """
    def __init__(self, model: str = "llama3"):
        super().__init__()
        self.model = model
        self._host = _config.get("global.ollama_host") or "http://localhost:11434"
        self._reachable: bool | None = None  # cached reachability

    @property
    def name(self) -> str:
        return f"Ollama({self.model})"

    def is_available(self) -> bool:
        """Check cooldown AND whether Ollama server is reachable."""
        if time.time() < self.cooldown_until:
            return False
        # Quick sync probe (cached per session to avoid hammering)
        if self._reachable is False:
            return False
        return True

    async def generate(self, prompt: str) -> str:
        try:
            resp = await _network_client.post(
                f"{self._host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"OllamaProvider error: {e}") from e


class GenericOpenAICompatibleProvider(Provider):
    """
    Any OpenAI-compatible endpoint (e.g. LM Studio, llama.cpp server, vLLM).
    Calls the /v1/chat/completions endpoint.
    Set global.openai_compat_url in config to enable.
    """
    def __init__(self, endpoint: str = "http://localhost:8080/v1", model: str = "local-model"):
        super().__init__()
        self.endpoint = endpoint
        self.model = model

    @property
    def name(self) -> str:
        return f"OpenAICompat({self.model}@{self.endpoint})"

    def is_available(self) -> bool:
        """Only use GenericOpenAI if explicitly configured in config."""
        if time.time() < self.cooldown_until:
            return False
        # Don't try localhost:8080 unless user explicitly configured it
        configured_url = _config.get("global.openai_compat_url", "")
        if not configured_url and "localhost:8080" in self.endpoint:
            return False   # Skip unconfigured default endpoint
        return True

    async def generate(self, prompt: str) -> str:
        try:
            resp = await _network_client.post(
                f"{self.endpoint}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            choices = resp.json().get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return ""
        except Exception as e:
            raise RuntimeError(f"GenericOpenAICompatibleProvider error: {e}") from e


def resolve_provider(module_name: str) -> List[Provider]:
    """
    Returns an ordered list of providers for a given module name.
    Reads the bootstrap model from config, falls back to llama3.
    """
    try:
        state = _config.get_module_state(module_name)
        model = state.get("bootstrap_model", "llama3")
    except Exception:
        model = "llama3"

    return [
        OllamaProvider(model=model),
        GenericOpenAICompatibleProvider(),
    ]


async def generate_with_fallback(providers: List[Provider], prompt: str) -> str:
    """
    Tries each provider in order. On failure, falls back to the next.
    ALL calls go through the prompt cache before hitting the backend.
    Instruments each attempt with a 'provider_call' span.
    """
    if not providers:
        raise ValueError("No providers specified for generation.")

    from core.prompt.cache import cached_generate
    from core.runtime.limits import safe_llm_call

    # Rank providers by health score before attempting.  Some tests and plugin
    # integrations use lightweight provider-like objects instead of subclasses,
    # so provider health hooks are treated as an optional protocol.
    available_providers = sorted(
        [p for p in providers if _provider_available(p)],
        key=lambda x: _provider_health(x),
        reverse=True
    )

    if not available_providers:
        # If all are in cooldown, pick the one that recovers soonest
        soonest = min(providers, key=lambda x: getattr(x, "cooldown_until", 0))
        logger.warning(f"[ProviderMesh] All providers in cooldown. Forced choice: {soonest.name}")
        available_providers = [soonest]

    last_error = None
    for provider in available_providers:
        start_time = time.perf_counter()

        try:
            # safe_llm_call enforces the global semaphore + 30s timeout
            result = await safe_llm_call(cached_generate, provider, prompt)
            
            # Phase 2: Block empty responses
            if not result or not result.strip():
                raise ValueError("Provider returned an empty response.")

            latency = int((time.perf_counter() - start_time) * 1000)
            _provider_mark_success(provider)
            
            # Phase 4: Record health
            from core.meta.health_monitor import health_monitor
            health_monitor.record_provider_call(success=True, latency_ms=latency)
            
            with span("provider_call", provider=provider.name, latency_ms=latency, success=True):
                logger.info(f"[ProviderMesh] {provider.name} succeeded in {latency}ms")
            return result

        except Exception as e:
            last_error = e
            _provider_mark_failure(provider)
            latency = int((time.perf_counter() - start_time) * 1000)
            
            # Phase 4: Record health
            from core.meta.health_monitor import health_monitor
            health_monitor.record_provider_call(success=False, latency_ms=latency)

            with span("provider_call", provider=provider.name, latency_ms=latency, success=False, error=str(e)):
                logger.warning(f"[ProviderMesh] {provider.name} failed ({type(e).__name__}: {e}), trying next...")

    raise RuntimeError(f"All available {len(available_providers)} provider(s) failed. Last: {last_error}")


def _provider_available(provider) -> bool:
    checker = getattr(provider, "is_available", None)
    if checker is None:
        return True
    try:
        return bool(checker())
    except Exception:
        logger.warning("[ProviderMesh] availability check failed for %s", provider.name)
        return False


def _provider_health(provider) -> int:
    return int(getattr(provider, "health_score", 100))


def _provider_mark_success(provider) -> None:
    marker = getattr(provider, "mark_success", None)
    if marker is not None:
        marker()


def _provider_mark_failure(provider) -> None:
    marker = getattr(provider, "mark_failure", None)
    if marker is not None:
        marker()


async def graceful_generate_with_fallback(providers: List[Provider], prompt: str,
                                           fallback_message: str = "") -> str:
    """
    Like generate_with_fallback but returns a user-friendly message instead
    of raising when all providers fail (no LLM running).
    Used by modules that want to degrade gracefully.
    """
    try:
        return await generate_with_fallback(providers, prompt)
    except RuntimeError as e:
        logger.warning(
            "[ProviderMesh] No LLM available. "
            "Start Ollama: `ollama serve && ollama pull mistral`"
        )
        if fallback_message:
            return fallback_message
        return (
            "[No LLM available] "
            "To enable AI responses, start Ollama: `ollama serve` "
            "then pull a model: `ollama pull mistral`"
        )
