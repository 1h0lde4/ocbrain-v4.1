import logging
from typing import Dict, Any, List

logger = logging.getLogger("ocbrain.governance.memory")

class MemoryGovernor:
    """
    Enforces safety, quality, and growth limits on the cognitive memory system.
    """
    def __init__(self, max_entries: int = 5000, quality_threshold: float = 0.6):
        self.max_entries = max_entries
        self.quality_threshold = quality_threshold
        self.stats = {
            "quarantined_count": 0,
            "rejected_count": 0,
            "consolidation_runs": 0
        }

    def validate_ingestion(self, entry: Dict[str, Any]) -> bool:
        """
        Checks if a new memory entry meets the quality floor.
        """
        confidence = entry.get("confidence", 0.0)
        if confidence < self.quality_threshold:
            logger.warning(f"[MemoryGovernor] Entry rejected: Confidence {confidence} below threshold {self.quality_threshold}")
            self.stats["rejected_count"] += 1
            return False
        
        # Check for empty content
        if not entry.get("fact") and not entry.get("content"):
            return False
            
        return True

    def check_growth_limits(self, current_count: int) -> bool:
        """
        Returns True if the system can accept more memories.
        """
        if current_count >= self.max_entries:
            logger.error(f"[MemoryGovernor] Memory capacity reached ({current_count}/{self.max_entries})")
            return False
        return True

    def detect_contradiction(self, new_fact: str, existing_memories: List[Dict[str, Any]]) -> bool:
        """
        Placeholder for contradiction detection logic.
        Will use semantic similarity to find potential conflicts.
        """
        # Logic to be expanded in Phase 5
        return False

    def quarantine_unstable(self, entry: Dict[str, Any]):
        """
        Moves high-risk or low-confidence memories to a quarantine state.
        """
        entry["validation_state"] = "quarantined"
        self.stats["quarantined_count"] += 1
        logger.info(f"[MemoryGovernor] Memory {entry.get('id')} quarantined for review.")

# Global singleton
memory_governor = MemoryGovernor()
