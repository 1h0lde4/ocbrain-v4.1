"""
modules/embedding_fn.py - ChromaDB embedding function selection.

Production deployments can use sentence-transformers. Test and recovery
environments must still start without downloading model weights, so this module
keeps a deterministic hash embedding fallback with the same ChromaDB contract.
"""
from __future__ import annotations

import hashlib
import math
import re

_cache: dict[str, object] = {}

_MODEL_MAP = {
    "coding": "sentence-transformers/all-MiniLM-L6-v2",
    "web_search": "sentence-transformers/all-MiniLM-L6-v2",
    "knowledge": "sentence-transformers/all-mpnet-base-v2",
    "system_ctrl": "sentence-transformers/all-MiniLM-L6-v2",
    "default": "sentence-transformers/all-MiniLM-L6-v2",
}


def get_embedding_function(module_name: str):
    """Return a ChromaDB-compatible embedding function for a module."""
    from chromadb.utils import embedding_functions as ef

    model_name = _MODEL_MAP.get(module_name, _MODEL_MAP["default"])
    if model_name not in _cache:
        try:
            _cache[model_name] = ef.SentenceTransformerEmbeddingFunction(
                model_name=model_name
            )
        except (ImportError, ValueError):
            _cache[model_name] = HashEmbeddingFunction()
    return _cache[model_name]


class HashEmbeddingFunction:
    """Small deterministic embedding fallback accepted by ChromaDB."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def __call__(self, input):
        return [self._embed(str(text)) for text in input]

    def name(self) -> str:
        return "ocbrain-hash-embedding"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
