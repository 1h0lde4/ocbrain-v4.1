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
    Checks cache before generation. Compresses prompt context to reduce
    tokens sent to the provider.

    CTX-CACHE-001 fix: the cache key is hashed from the full, uncompressed
    `prompt`, not the compressed one. compress_context() keeps only the
    first/last max_words//2 words for anything over the threshold and
    discards the entire middle -- two genuinely different prompts sharing
    the same head and tail (a realistic shape whenever variable content
    sits between a fixed header and fixed footer, e.g. the Intent
    Hypothesis template's Context/Request block) previously hashed
    identically and collided, silently returning one caller's response to
    an unrelated caller. Compression still applies to what is actually
    sent to the provider below -- only cache-key identity changed.
    """
    # 1. Compress prompt if it's exceedingly long. This reduces tokens
    # sent to the provider only -- see the cache-key note above for why
    # it must not also be what determines cache identity.
    compressed_prompt = compress_context(prompt, max_words=500)

    # 2. Hash the full prompt (CTX-CACHE-001) -- not compressed_prompt.
    prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    
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
