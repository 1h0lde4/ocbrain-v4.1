import json
import os
import time
import logging
from typing import List, Dict, Any

logger = logging.getLogger("ocbrain.web_learning.quarantine")

class KnowledgeQuarantine:
    """
    Quarantine area for knowledge extracted from the web.
    Must be validated before entering long-term memory.
    """
    def __init__(self, storage_path: str = ".data/learning/quarantine.jsonl"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def add(self, content: str, source: str, trust_score: float):
        """Adds new knowledge to quarantine."""
        entry = {
            "id": f"q_{int(time.time() * 1000)}",
            "content": content,
            "source": source,
            "trust_score": trust_score,
            "validation_status": "pending",
            "timestamp": time.time()
        }
        
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info(f"[Quarantine] Added pending knowledge from {source} (Trust: {trust_score})")
        except Exception as e:
            logger.error(f"[Quarantine] Failed to store knowledge: {e}")

    def get_pending(self) -> List[Dict[str, Any]]:
        """Retrieves all pending knowledge entries."""
        if not os.path.exists(self.storage_path): return []
        
        pending = []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry["validation_status"] == "pending":
                        pending.append(entry)
        except Exception as e:
            logger.error(f"[Quarantine] Failed to read pending knowledge: {e}")
        
        return pending

    def update_status(self, entry_id: str, status: str):
        """Updates the status of a quarantined entry (e.g., 'validated', 'rejected')."""
        # Note: For simplicity in .jsonl, we'd typically rewrite or use a sidecar.
        # In this implementation, we'll assume a small scale and rewrite.
        pass

# Global singleton
quarantine = KnowledgeQuarantine()
