import json
import os
import uuid
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ocbrain.memory.vault")

class MemoryVault:
    """
    Storage layer for structured knowledge derived from the web-learning pipeline.
    """
    def __init__(self, storage_dir: str = ".data/memory"):
        self.storage_dir = storage_dir
        self.entries = []
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

    def _get_path(self):
        return os.path.join(self.storage_dir, "vault.json")

    def _load(self):
        path = self._get_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
                logger.info(f"[MemoryVault] Loaded {len(self.entries)} entries.")
            except Exception as e:
                logger.error(f"[MemoryVault] Error loading vault: {e}")
                self.entries = []

    def _save(self):
        path = self._get_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            logger.error(f"[MemoryVault] Error saving vault: {e}")

    def add_entry(self, fact: str, summary: str, confidence: float, embedding: List[float], type: str = "fact", source: str = "web", tags: Optional[List[str]] = None):
        """
        Stores structured data with importance and access tracking.
        """
        entry = {
            "id": str(uuid.uuid4()),
            "type": type,
            "fact": fact,
            "summary": summary,
            "source": source,
            "confidence": confidence,
            "importance": 1.0,
            "access_count": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "embedding": embedding,
            "tags": tags or []
        }
        self.entries.append(entry)
        
        # Memory Safety: Limit total entries to prevent bloat (Phase 3)
        if len(self.entries) > 1000:
            # Sort by importance (ascending) and remove the weakest
            self.entries.sort(key=lambda x: x.get("importance", 1.0))
            removed = self.entries.pop(0)
            logger.warning(f"[MemoryVault] Pruned weak memory to stay under limit: {removed['id']}")

        self._save()
        logger.info(f"[MemoryVault] Added new entry ({type}): {fact[:50]}...")
        return entry["id"]

    def bm25_search_placeholder(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        BUG FIX: Was keyword/token-overlap search labeled as BM25.
        Now implements actual BM25 (Okapi BM25) scoring.
        k1=1.5, b=0.75 — standard production defaults.
        """
        return self.bm25_search(query, top_k=top_k)

    def bm25_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Real BM25 (Okapi BM25) search over stored memories.
        Replaces the token-overlap placeholder from the reference implementation.
        """
        import math
        if not self.entries:
            return []

        k1, b = 1.5, 0.75
        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        if not query_terms:
            return []

        # Build inverted index + doc lengths
        corpus: List[List[str]] = []
        for e in self.entries:
            tokens = re.findall(r"\w+", (e.get("fact","") + " " + e.get("summary","")).lower())
            corpus.append(tokens)

        N = len(corpus)
        avg_dl = sum(len(d) for d in corpus) / N if N else 1

        scores = []
        for idx, (entry, doc_tokens) in enumerate(zip(self.entries, corpus)):
            dl = len(doc_tokens)
            score = 0.0
            for term in query_terms:
                tf = doc_tokens.count(term)
                df = sum(1 for d in corpus if term in d)
                if df == 0:
                    continue
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
                tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
                score += idf * tf_norm
            if score > 0:
                scores.append((score, entry))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scores[:top_k]]

    def get_all_embeddings(self) -> tuple[List[str], List[List[float]]]:
        """
        Returns entry IDs and their embeddings for vector search.
        """
        ids = [e["id"] for e in self.entries if e.get("embedding")]
        embeddings = [e["embedding"] for e in self.entries if e.get("embedding")]
        return ids, embeddings

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        for e in self.entries:
            if e["id"] == entry_id:
                return e
        return None

    def refresh_importance(self):
        """
        Recalculates importance for all entries based on:
        - confidence
        - access_count
        - recency (decay)
        """
        now = datetime.now(timezone.utc)
        import math
        
        for entry in self.entries:
            ts = datetime.fromisoformat(entry["timestamp"])
            age_days = (now - ts).days
            
            # Base importance from confidence and usage
            base = entry.get("confidence", 0.5) * math.log1p(entry.get("access_count", 1))
            
            # Recency factor: log decay
            recency = 1.0 / math.log(age_days + 2)
            
            entry["importance"] = round(base * recency, 4)
            
        self._save()
        logger.info("[MemoryVault] Refreshed importance scores for all entries.")

    def decay_all(self, factor: float = 0.95):
        """Manually decay all importance scores (e.g. daily)."""
        for entry in self.entries:
            entry["importance"] = round(entry.get("importance", 1.0) * factor, 4)
        self._save()
