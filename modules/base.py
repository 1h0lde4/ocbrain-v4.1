"""
modules/base.py — V2.1: LRU cache on retrieve(), async ChromaDB wrapper.
"""
import asyncio
import json
import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import chromadb

from core.runtime.resilience import CircuitBreaker

log = logging.getLogger(__name__)

# Module-level retrieval cache: (module_name, query_hash, k) → list[str]
# 128 slots, TTL enforced by timestamp in value tuple
_RETRIEVE_CACHE: dict[tuple, tuple] = {}
_CACHE_TTL_SEC  = 300   # 5 minutes — stale after this
_CACHE_MAX_SIZE = 128
_CACHE_LOCK = threading.RLock()


def _cache_get(key: tuple) -> Optional[list]:
    with _CACHE_LOCK:
        entry = _RETRIEVE_CACHE.get(key)
        if entry is None:
            return None
        chunks, ts = entry
        if time.time() - ts > _CACHE_TTL_SEC:
            del _RETRIEVE_CACHE[key]
            return None
        return chunks


def _cache_set(key: tuple, chunks: list):
    with _CACHE_LOCK:
        if len(_RETRIEVE_CACHE) >= _CACHE_MAX_SIZE:
            oldest = min(_RETRIEVE_CACHE, key=lambda k: _RETRIEVE_CACHE[k][1])
            del _RETRIEVE_CACHE[oldest]
        _RETRIEVE_CACHE[key] = (chunks, time.time())


@dataclass
class ModuleResult:
    answer: str
    confidence: float = 1.0
    source: str = "external"
    chunks_used: list = field(default_factory=list)
    latency_ms: int = 0


class BaseModule(ABC):
    name: str = "base"

    def __init__(self):
        self.root: Path = Path(__file__).parent / self.name
        self.root.mkdir(parents=True, exist_ok=True)

        for sub in ["weights/active", "weights/previous", "weights/pending"]:
            (self.root / sub).mkdir(parents=True, exist_ok=True)

        db_path = str(self.root / "knowledge.db")
        self._chroma_client = chromadb.PersistentClient(path=db_path)
        self.db  = self._get_or_create_collection()
        self._model = None
        self._loop  = None   # cached event loop ref for run_in_executor
        self.breaker = CircuitBreaker(self.name, threshold=3, reset_timeout=60.0)

    def _get_or_create_collection(self):
        from .embedding_fn import get_embedding_function
        return self._chroma_client.get_or_create_collection(
            name=self.name,
            embedding_function=get_embedding_function(self.name),
        )

    @abstractmethod
    async def run(self, task: str, context) -> ModuleResult: ...

    @abstractmethod
    async def run_own(self, task: str, context) -> ModuleResult: ...

    async def run_routed(self, task: str, context, router):
        return await self.breaker.call(router.route, self.name, task, context)

    def retrieve(self, query: str, k: int = 5) -> list[str]:
        """
        Synchronous retrieval with LRU cache.
        Cache key: (module_name, query_hash, k).
        ChromaDB query only runs on cache miss.
        """
        if k <= 0:
            return []

        cache_key = (self.name, hash(query), k)
        cached    = _cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            count = self.db.count()
            if count == 0:
                return []

            results = self.db.query(
                query_texts=[query],
                n_results=min(k, count),
                include=["documents", "metadatas"],
            )
            docs      = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            filtered  = []
            for doc, meta in zip(docs, metadatas):
                meta = meta or {}
                qs   = meta.get("quality_score", 0.5)
                if qs < 0.4:
                    continue
                filtered.append(doc)

            _cache_set(cache_key, filtered)
            return filtered

        except Exception as e:
            log.error(f"[{self.name}] retrieve error: {e}")
            return []

    async def retrieve_async(self, query: str, k: int = 5) -> list[str]:
        """
        Async wrapper — runs synchronous ChromaDB call in executor
        so it doesn't block the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.retrieve, query, k)

    def ingest(self, chunks: list[str], metadatas: Optional[list[dict]] = None):
        if not chunks:
            return
        if metadatas is None:
            metadatas = [{"timestamp": time.time(), "quality_score": 0.7}] * len(chunks)
        ids = [f"{self.name}_{abs(hash(c))}_{int(time.time())}" for c in chunks]
        try:
            self.db.upsert(documents=chunks, metadatas=metadatas, ids=ids)
            # Invalidate retrieval cache for this module on new ingest
            with _CACHE_LOCK:
                keys_to_drop = [k for k in _RETRIEVE_CACHE if k[0] == self.name]
                for k in keys_to_drop:
                    del _RETRIEVE_CACHE[k]
        except Exception as e:
            log.error(f"[{self.name}] ingest error: {e}")

    def load_weights(self, path: Path):
        try:
            new_model = self._load_lora(path)
            old_model = self._model
            self._model = new_model
            del old_model
            import shutil
            active  = self.root / "weights" / "active"
            prev    = self.root / "weights" / "previous"
            pending = self.root / "weights" / "pending"
            if active.exists() and any(active.iterdir()):
                if prev.exists():
                    shutil.rmtree(prev)
                shutil.copytree(active, prev)
            if pending.exists() and any(pending.iterdir()):
                if active.exists():
                    shutil.rmtree(active)
                shutil.copytree(pending, active)
        except Exception as e:
            log.error(f"[{self.name}] load_weights error: {e}")

    def _load_lora(self, path: Path):
        return None

    def save_training_pair(self, query: str, answer: str):
        from core.privacy import privacy
        if not privacy.can_save_training():
            return
        import uuid as _uuid
        out = Path(__file__).parent.parent / "data" / "raw" / self.name
        out.mkdir(parents=True, exist_ok=True)
        pair  = {"query": query, "answer": answer, "timestamp": time.time()}
        fname = out / f"{_uuid.uuid4()}.json"
        fname.write_text(json.dumps(pair, ensure_ascii=False))

    def health(self) -> dict:
        from core.config import config
        state = config.get_module_state(self.name)
        try:
            count = self.db.count()
            db_ok = True
        except Exception:
            count = 0
            db_ok = False
        return {
            "name":           self.name,
            "stage":          state.get("stage", "bootstrap"),
            "maturity_score": state.get("maturity_score", 0.0),
            "query_count":    state.get("query_count", 0),
            "db_ok":          db_ok,
            "kb_chunks":      count,
            "model":          state.get("bootstrap_model", "unknown"),
            "cache_entries":  self._cache_entry_count(),
        }

    def _cache_entry_count(self) -> int:
        with _CACHE_LOCK:
            return sum(1 for k in _RETRIEVE_CACHE if k[0] == self.name)

    def _build_prompt(self, task: str, chunks: list[str], context) -> str:
        ctx_str = context.format_for_prompt(5) if context else ""
        kb_str  = "\n\n".join(chunks) if chunks else "No relevant knowledge found."
        return (
            f"Conversation history:\n{ctx_str}\n\n"
            f"Relevant knowledge:\n{kb_str}\n\n"
            f"Task: {task}\n\nResponse:"
        )
