import logging
from typing import Dict, Any
from core.learning.similarity import semantic_similarity
from core.memory.mem_vault import MemoryVault

logger = logging.getLogger("ocbrain.memory.dedup")

def deduplicate_and_merge(new_entry: Dict[str, Any], vault: MemoryVault, similarity_threshold: float = 0.9) -> bool:
    """
    Checks if the new entry is extremely similar to an existing entry in the vault.
    If similarity > 0.9, it merges the entries (e.g., updates timestamp, expands tags)
    instead of creating a duplicate.
    
    Returns True if merged, False if it is a novel entry.
    """
    # Quick keyword pre-filter could be used here to avoid O(N) comparisons
    # For now, we do a linear scan over recent or relevant entries
    
    for existing in vault.entries:
        sim = semantic_similarity(new_entry["fact"], existing["fact"])
        if sim > similarity_threshold:
            logger.info(f"[Dedup] Found duplicate (sim={sim:.2f}). Merging into {existing['id']}")
            
            # Merge logic:
            existing["timestamp"] = new_entry["timestamp"]
            
            if new_entry["confidence"] > existing["confidence"]:
                existing["confidence"] = new_entry["confidence"]
                
            existing_tags = set(existing.get("tags", []))
            new_tags = set(new_entry.get("tags", []))
            existing["tags"] = list(existing_tags.union(new_tags))

            # Phase 3 Enhancements:
            existing["access_count"] = existing.get("access_count", 1) + 1
            # Boost importance slightly on reinforcement
            existing["importance"] = min(2.0, existing.get("importance", 1.0) + 0.1)
            
            vault._save()
            return True
            
    return False
