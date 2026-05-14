import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("ocbrain.shadow")

class ShadowLearner:
    """
    Shadow Learning System: Records interactions to build high-quality datasets.
    """
    def __init__(self, storage_path: str = ".data/learning/shadow_dataset.jsonl"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def record_interaction(self, query: str, answer: str, module_name: str, confidence: float, meta: Optional[dict] = None):
        """
        Append a high-quality interaction to the shadow dataset.
        Only records if confidence > 0.7 (default).
        """
        if confidence < 0.7:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "answer": answer,
            "module": module_name,
            "confidence": confidence,
            "meta": meta or {}
        }

        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"[ShadowLearner] Failed to record interaction: {e}")

# Global singleton
shadow_learner = ShadowLearner()
