import json
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ocbrain.memory.cognitive_vault")

class CognitiveVault:
    """
    Unified multi-tier storage for the Cognitive Memory Runtime.
    Tiers:
      - L1: Episodic (Events, Decisions)
      - L2: Semantic (Facts, Concepts)
      - L3: Procedural (Workflows, Fixes)
      - L4: Archive (Raw provenance)
    """
    def __init__(self, storage_dir: str = ".data/memory/cognitive"):
        self.storage_dir = storage_dir
        self.entries: List[Dict[str, Any]] = []
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_path(self):
        return os.path.join(self.storage_dir, "vault_v4.json")

    def _load(self):
        path = self._get_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
                logger.info(f"[CognitiveVault] Loaded {len(self.entries)} multi-tier entries.")
            except Exception as e:
                logger.error(f"[CognitiveVault] Error loading vault: {e}")

    def _save(self):
        path = self._get_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            logger.error(f"[CognitiveVault] Error saving vault: {e}")

    def add_entry(self, 
                  content: str, 
                  tier: str, 
                  source: str, 
                  confidence: float = 1.0, 
                  embedding: Optional[List[float]] = None,
                  derived_from: Optional[List[str]] = None,
                  meta: Optional[dict] = None) -> str:
        """
        Adds an entry to a specific cognitive tier with full provenance.
        """
        if tier not in ["L1", "L2", "L3", "L4"]:
            raise ValueError(f"Invalid tier: {tier}")

        entry_id = str(uuid.uuid4())
        entry = {
            "id": entry_id,
            "tier": tier,
            "content": content,
            "source": source,
            "confidence": confidence,
            "importance": 1.0,
            "access_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "embedding": embedding,
            "derived_from": derived_from or [],
            "validation_state": "validated",
            "meta": meta or {}
        }

        self.entries.append(entry)
        self._save()
        logger.info(f"[CognitiveVault] Added {tier} entry: {content[:50]}...")
        return entry_id

    def get_tier(self, tier: str) -> List[Dict[str, Any]]:
        return [e for e in self.entries if e["tier"] == tier]

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        for e in self.entries:
            if e["id"] == entry_id:
                return e
        return None

    def search_keyword(self, query: str, tier: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Naive substring search (to be replaced by FTS5 in Phase 4)."""
        query_lower = query.lower()
        candidates = self.get_tier(tier) if tier else self.entries
        results = []
        for e in candidates:
            if query_lower in e["content"].lower():
                results.append(e)
        return results[:top_k]

# Global singleton
cognitive_vault = CognitiveVault()
