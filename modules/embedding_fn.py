"""
modules/embedding_fn.py — Returns the right ChromaDB embedding function per module.
Loaded once and cached — sentence-transformers models stay in memory.
"""
from __future__ import annotations
from typing import Optional

_cache: dict[str, object] = {}

# NOTE: nomic-ai/nomic-embed-text-v1 requires trust_remote_code=True which
# ChromaDB's SentenceTransformerEmbeddingFunction does not support — it crashes
# the coding module on startup. Using all-MiniLM-L6-v2 for all modules.
# code-specific embeddings can be added later via a custom EmbeddingFunction subclass.
_MODEL_MAP = {
    "coding":      "sentence-transformers/all-MiniLM-L6-v2",
    "web_search":  "sentence-transformers/all-MiniLM-L6-v2",
    "knowledge":   "sentence-transformers/all-mpnet-base-v2",
    "system_ctrl": "sentence-transformers/all-MiniLM-L6-v2",
    "default":     "sentence-transformers/all-MiniLM-L6-v2",
}


def get_embedding_function(module_name: str):
    """Return a ChromaDB-compatible embedding function for the given module."""
    from chromadb.utils import embedding_functions as ef

    model_name = _MODEL_MAP.get(module_name, _MODEL_MAP["default"])
    if model_name not in _cache:
        _cache[model_name] = ef.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )
    return _cache[model_name]
