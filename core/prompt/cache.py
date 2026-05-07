import hashlib
import time
import logging
from typing import Dict, Tuple

logger = logging.getLogger("ocbrain.prompt.cache")

# Simple in-memory cache: hash -> (response, timestamp)
_prompt_cache: Dict[str, Tuple[str, float]] = {}

def compress_context(text: str, max_words: int = 100) -> str:
    """
    Context compression to reduce token usage and improve consistency.
    Extracts key information. This is a heuristic mock.
    """
    # Remove multiple spaces/newlines
    import re
    cleaned = re.sub(r'\s+', ' ', text).strip()
    
    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned
        
    # Simple compression: take first N/2 and last N/2 words to preserve head/tail context
    half = max_words // 2
    compressed = ' '.join(words[:half]) + " ... [COMPRESSED] ... " + ' '.join(words[-half:])
    return compressed

async def cached_generate(provider, prompt: str, ttl_seconds: float = 3600.0) -> str:
    """
    Checks cache before generation. Compresses prompt context to save tokens.
    """
    # 1. Compress prompt if it's exceedingly long
    # We assume 'prompt' has clear boundaries, but for safety we compress
    # any monolithic blocks of text if they are huge. 
    compressed_prompt = compress_context(prompt, max_words=500)
    
    # 2. Hash prompt
    prompt_hash = hashlib.sha256(compressed_prompt.encode('utf-8')).hexdigest()
    
    # 3. Check cache
    now = time.time()
    if prompt_hash in _prompt_cache:
        cached_response, timestamp = _prompt_cache[prompt_hash]
        if now - timestamp < ttl_seconds:
            logger.debug("[PromptCache] Cache hit!")
            return cached_response
        else:
            logger.debug("[PromptCache] Cache expired.")
            del _prompt_cache[prompt_hash]
            
    # 4. Miss -> Call provider
    logger.debug(f"[PromptCache] Cache miss. Calling {provider.name}...")
    response = await provider.generate(compressed_prompt)
    
    # 5. Store in cache
    # Prevent unbound memory growth
    if len(_prompt_cache) > 1000:
        _prompt_cache.clear()
        
    _prompt_cache[prompt_hash] = (response, now)
    
    return response
