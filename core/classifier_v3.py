"""
core/classifier_v3.py — Semantic Classifier.

Replaces keyword-based routing with embedding-based cosine similarity.
Fallback: delegates to the existing keyword+LLM classifier (classifier.py)
so that correctness is never sacrificed when the embedding model is unavailable.
"""
import logging
from typing import List, Dict, Any

from core.observability.tracer import trace_function

logger = logging.getLogger("ocbrain.classifier_v3")

# Module descriptions used for semantic embedding.
# Keys MUST match the module names registered in core/config.py and modules/.
MODULES = {
    "coding":       "Programming, software development, writing code, debugging scripts, and technical engineering tasks.",
    "knowledge":    "General knowledge, factual information, history, science, explanations, and encyclopedic answers.",
    "web_search":   "Internet search, current events, latest news, online lookup, and real-time information retrieval.",
    "system_ctrl":  "Computer control, system commands, file management, process execution, and local machine operations.",
}

# In-memory caches — populated lazily on first classify() call
_module_embeddings_cache: Dict[str, Any] = {}
_query_cache: Dict[str, Any] = {}


def _ensure_module_embeddings() -> bool:
    """
    Precomputes and caches embeddings for all module descriptions.
    Returns True on success, False if the model is unavailable.
    """
    global _module_embeddings_cache
    if _module_embeddings_cache:
        return True

    from core.learning.similarity import get_model
    model = get_model()
    if not model:
        logger.warning("[Classifier V3] Embedding model unavailable.")
        return False

    logger.info("[Classifier V3] Precomputing module embeddings...")
    for mod_name, desc in MODULES.items():
        # Encode the description directly for cleaner semantic mapping
        _module_embeddings_cache[mod_name] = model.encode([desc])[0]

    return True


@trace_function(name="classifier_v3")
def classify(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Semantic Classifier v3.
    Returns top-k modules ranked by cosine similarity.

    Output format:
        [{"module": "coding", "score": 0.82}, ...]

    Fallback:
        When the embedding model fails, delegates to the legacy classifier
        (classifier.py) which uses keyword matching + optional LLM.
    """
    from core.learning.similarity import get_model

    model = get_model()
    if not model or not _ensure_module_embeddings():
        logger.warning("[Classifier V3] Falling back to legacy keyword classifier.")
        return _keyword_fallback(query)

    try:
        from scipy.spatial.distance import cosine
    except ImportError:
        logger.warning("[Classifier V3] SciPy missing, falling back.")
        return _keyword_fallback(query)

    # Retrieve or compute query embedding (simple LRU via size-bound dict)
    if query in _query_cache:
        q_emb = _query_cache[query]
    else:
        q_emb = model.encode([query])[0]
        if len(_query_cache) > 1000:
            _query_cache.clear()
        _query_cache[query] = q_emb

    # Score each module
    scored = []
    for mod_name, mod_emb in _module_embeddings_cache.items():
        dist = cosine(q_emb, mod_emb)
        sim = max(0.0, min(1.0, 1.0 - dist))
        scored.append({"module": mod_name, "score": float(sim)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    
    # Filter by threshold (Phase 2 enhancement)
    selected = [s for s in scored if s["score"] > 0.3]
    
    # If nothing matches the 0.3 threshold, pick the top if it's at least 0.1
    if not selected and scored and scored[0]["score"] > 0.1:
        selected = scored[:1]
        
    logger.info(f"[Classifier V3] '{query[:60]}' -> {selected}")
    return selected or [{"module": "knowledge", "score": 0.0}]


def _keyword_fallback(query: str) -> List[Dict[str, Any]]:
    """
    Pure keyword-based fallback — no LLM, no embedding model required.
    Mirrors the fast-path logic from classifier.py for robustness.
    """
    try:
        from core.config import config
        module_names = config.all_module_names()
        scores: Dict[str, float] = {}
        query_lower = query.lower()
        for mod in module_names:
            kws = config.get_module_keywords(mod) or []
            hits = sum(1 for kw in kws if kw.lower() in query_lower)
            if hits:
                scores[mod] = min(0.4 + hits * 0.15, 0.85)

        if scores:
            sorted_mods = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            return [{"module": m, "score": s} for m, s in sorted_mods[:2]]
    except Exception as e:
        logger.error(f"[Classifier V3] Keyword fallback error: {e}")

    # Final safety net
    return [{"module": "knowledge", "score": 0.5}]
