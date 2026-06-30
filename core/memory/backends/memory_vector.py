"""
core/memory/backends/memory_vector.py — InMemoryVectorBackend (L2 Semantic)

Implements VectorBackend via in-memory BM25 + optional sentence-transformers.

Upgrade path (no changes to UnifiedMemory required):
  Phase 5: replace with ChromaVectorBackend when corpus > 100K entries
  Phase 5+: replace with QdrantVectorBackend for production scale

Design: real Okapi BM25 (k1=1.5, b=0.75), RRF fusion (k=60).
Embeddings optional — system degrades gracefully to BM25-only.
"""

import asyncio
import logging
import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from core.memory.backends.base import VectorBackend

logger = logging.getLogger("ocbrain.memory.backends.memory_vector")


class _BM25Index:
    """Okapi BM25 (k1=1.5, b=0.75). In-memory inverted index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b  = b
        self._docs:   Dict[str, List[str]] = {}   # entry_id → tokens
        self._idf:    Dict[str, float]     = {}   # term → IDF score
        self._avg_dl: float                = 0.0

    def _tokenise(self, text: str) -> List[str]:
        return [t.lower() for t in re.findall(r"\w+", text) if len(t) > 1]

    def add(self, entry_id: str, text: str) -> None:
        tokens = self._tokenise(text)
        self._docs[entry_id] = tokens
        self._rebuild_idf()

    def remove(self, entry_id: str) -> None:
        self._docs.pop(entry_id, None)
        if self._docs:
            self._rebuild_idf()

    def _rebuild_idf(self) -> None:
        n = len(self._docs)
        if n == 0:
            self._idf = {}
            self._avg_dl = 0.0
            return
        total_len = sum(len(toks) for toks in self._docs.values())
        self._avg_dl = total_len / n
        df: Dict[str, int] = defaultdict(int)
        for toks in self._docs.values():
            for term in set(toks):
                df[term] += 1
        self._idf = {
            term: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for term, freq in df.items()
        }

    def rank(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        if not self._docs:
            return []
        q_terms = self._tokenise(query)
        if not q_terms:
            return []
        scores: Dict[str, float] = defaultdict(float)
        for entry_id, tokens in self._docs.items():
            dl = len(tokens)
            tf_map: Dict[str, int] = defaultdict(int)
            for t in tokens:
                tf_map[t] += 1
            for term in q_terms:
                if term not in self._idf:
                    continue
                tf  = tf_map.get(term, 0)
                idf = self._idf[term]
                norm = self.k1 * (1 - self.b + self.b * dl / max(self._avg_dl, 1))
                scores[entry_id] += idf * (tf * (self.k1 + 1)) / (tf + norm)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    @property
    def size(self) -> int:
        return len(self._docs)


class InMemoryVectorBackend(VectorBackend):
    """
    L2 Semantic memory backend.

    Storage layout:
      _bm25:      BM25 index over all indexed content
      _embeddings: entry_id → List[float] (optional, sentence-transformers)

    Note: This is in-process. Entries are lost on restart.
    This is acceptable for Phase 3 — Phase 5 upgrades to Chroma/Qdrant.
    The issue is documented in KNOWN_ISSUES.md.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._bm25       = _BM25Index()
        self._texts:      Dict[str, str]          = {}   # entry_id → text
        self._embeddings: Dict[str, List[float]]  = {}   # entry_id → embedding
        self._model_name  = model_name
        self._model       = None       # lazy-loaded sentence transformer
        self._model_tried = False      # only attempt load once per session

    def _try_load_model(self) -> bool:
        """Attempt to load sentence-transformers model. Returns True if available."""
        if self._model_tried:
            return self._model is not None
        self._model_tried = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            logger.info("VectorBackend: sentence-transformers loaded (%s)", self._model_name)
            return True
        except ImportError:
            logger.info("VectorBackend: sentence-transformers not available; BM25-only mode")
            return False
        except Exception as e:
            logger.warning("VectorBackend: model load failed (%s); BM25-only mode: %s",
                           self._model_name, e)
            return False

    def _embed_sync(self, text: str) -> Optional[List[float]]:
        if not self._try_load_model() or self._model is None:
            return None
        try:
            return self._model.encode(text).tolist()
        except Exception as e:
            logger.debug("Embedding failed: %s", e)
            return None

    # ── VectorBackend implementation ──────────────────────────────────────

    async def index(self, entry_id: str, content: str,
                     embedding: Optional[List[float]] = None) -> None:
        loop = asyncio.get_event_loop()
        self._texts[entry_id] = content
        self._bm25.add(entry_id, content)

        if embedding is not None:
            self._embeddings[entry_id] = embedding
        elif self._try_load_model():
            # Compute embedding in thread so we don't block event loop
            emb = await loop.run_in_executor(None, self._embed_sync, content)
            if emb is not None:
                self._embeddings[entry_id] = emb

    async def remove(self, entry_id: str) -> None:
        self._texts.pop(entry_id, None)
        self._embeddings.pop(entry_id, None)
        self._bm25.remove(entry_id)

    async def search_bm25(self, query: str,
                           top_k: int = 10) -> List[Tuple[str, float]]:
        # BM25 is synchronous but fast (in-memory); no executor needed for small corpora
        return self._bm25.rank(query, top_k=top_k)

    async def search_vector(self, query_embedding: List[float],
                             top_k: int = 10) -> List[Tuple[str, float]]:
        if not self._embeddings:
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._cosine_rank, query_embedding, top_k
        )

    def _cosine_rank(self, query_emb: List[float],
                      top_k: int) -> List[Tuple[str, float]]:
        q_norm = math.sqrt(sum(x * x for x in query_emb))
        if q_norm == 0:
            return []
        scores = []
        for eid, emb in self._embeddings.items():
            if len(emb) != len(query_emb):
                continue
            dot  = sum(a * b for a, b in zip(query_emb, emb))
            norm = math.sqrt(sum(x * x for x in emb))
            if norm == 0:
                continue
            scores.append((eid, dot / (q_norm * norm)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    async def stats(self) -> Dict[str, Any]:
        return {
            "backend": "InMemoryVectorBackend",
            "indexed_docs": self._bm25.size,
            "docs_with_embeddings": len(self._embeddings),
            "model": self._model_name if self._model else "none (BM25-only)",
            "persistent": False,
        }
