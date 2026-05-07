import hashlib
import json
import time
import logging
from typing import Optional, Any

logger = logging.getLogger("ocbrain.efficiency")

class PromptCache:
    """
    In-memory (or later Redis) cache for LLM responses.
    Reduces cost by preventing redundant calls for identical prompts.
    """
    def __init__(self, ttl: int = 3600):
        self._cache = {} # hash -> (response, expiry)
        self.ttl = ttl

    def _hash(self, model: str, prompt: str, options: dict) -> str:
        data = json.dumps({"m": model, "p": prompt, "o": options}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, model: str, prompt: str, options: dict = {}) -> Optional[str]:
        h = self._hash(model, prompt, options)
        entry = self._cache.get(h)
        if entry:
            response, expiry = entry
            if time.time() < expiry:
                logger.debug(f"[PromptCache] HIT: {h[:8]}")
                return response
            else:
                del self._cache[h]
        return None

    def set(self, model: str, prompt: str, response: str, options: dict = {}):
        h = self._hash(model, prompt, options)
        self._cache[h] = (response, time.time() + self.ttl)
        logger.debug(f"[PromptCache] SET: {h[:8]}")

# Global singleton
prompt_cache = PromptCache()

class ModelTier:
    """
    Logic for routing queries between Small (Cheap/Fast) and Large (Expensive/Smart) models.
    """
    SMALL = "mistral" # e.g. Mistral 7B / Phi-3
    LARGE = "gpt-4"   # e.g. OpenAI / Claude / Local Llama 70B

    @staticmethod
    def decide_model(complexity_score: float) -> str:
        """
        Complexity 0.0 -> 0.4: Small
        Complexity 0.5 -> 1.0: Large
        """
        if complexity_score > 0.5:
            return ModelTier.LARGE
        return ModelTier.SMALL

async def cost_aware_call(provider_mesh, model: str, prompt: str, **kwargs) -> Any:
    """
    Wraps LLM calls with caching and cost tracking.
    """
    # 1. Check Cache
    cached = prompt_cache.get(model, prompt, kwargs)
    if cached:
        return cached

    # 2. Call Provider
    # Note: provider_mesh implementation details assumed here
    response = await provider_mesh.call(model, prompt, **kwargs)

    # 3. Cache Result
    if response:
        prompt_cache.set(model, prompt, response, kwargs)
    
    return response
