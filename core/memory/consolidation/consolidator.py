import logging
import asyncio
from core.memory.cognitive_vault import cognitive_vault

logger = logging.getLogger("ocbrain.memory.consolidation")

class MemoryConsolidator:
    """
    Background engine for memory cleanup, distillation, and forgetting.
    """
    def __init__(self, decay_rate: float = 0.95):
        self.decay_rate = decay_rate
        self._is_running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        if self._is_running:
            return
        self._is_running = True
        logger.info("[Consolidator] Memory consolidation engine active.")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _loop(self):
        try:
            while self._is_running:
                try:
                    await self.run_consolidation()
                except Exception as e:
                    logger.error(f"[Consolidator] Loop error: {e}")
                await asyncio.sleep(3600) # Run every hour
        except asyncio.CancelledError:
            raise

    async def run_consolidation(self):
        logger.info("[Consolidator] Starting memory consolidation run...")
        self._apply_adaptive_forgetting()
        self._merge_duplicates()
        self._distill_episodic_to_semantic()
        logger.info("[Consolidator] Consolidation run complete.")

    def _apply_adaptive_forgetting(self):
        """Decays importance of all memories."""
        for entry in cognitive_vault.entries:
            # Importance decays, but access_count protects it
            # High-access memories stay important longer
            age_factor = 0.99 
            entry["importance"] = round(entry["importance"] * age_factor, 4)
            
            # If importance is too low, prune it (unless it's L4 Archive)
            if entry["importance"] < 0.1 and entry["tier"] != "L4":
                logger.info(f"[Consolidator] Pruning low-value memory: {entry['id']}")
                cognitive_vault.entries.remove(entry)
        
        cognitive_vault._save()

    def _merge_duplicates(self):
        # Logic to find semantic duplicates and merge them
        pass

    def _distill_episodic_to_semantic(self):
        """
        Takes recent L1 Episodic memories and extracts stable L2 Semantic facts.
        """
        # This would typically involve an LLM call to summarize a series of events
        pass

# Global singleton
consolidator = MemoryConsolidator()
