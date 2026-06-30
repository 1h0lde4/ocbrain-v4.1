import logging
from typing import List, Dict, Any
from .trust import trust_manager
from .quarantine import quarantine
from core.memory.mem_vault import MemoryVault

logger = logging.getLogger("ocbrain.web_learning.pipeline")

class WebLearningPipeline:
    """
    Controlled pipeline: Search -> Extraction -> Quarantine -> Validation -> Memory.
    """
    def __init__(self):
        self.vault = MemoryVault()

    async def process_search_query(self, query: str):
        """
        Main entry for learning from a query.
        """
        logger.info(f"[WebLearning] Triggering learning cycle for: {query}")
        
        # 1. Search (Mock or real web_search module call)
        results = await self._search(query)
        
        for result in results:
            url = result.get("url")
            trust = trust_manager.get_trust_score(url)
            
            if trust < 0.4:
                logger.warning(f"[WebLearning] Skipping low-trust source: {url}")
                continue

            # 2. Extraction
            content = await self._extract(result)
            if not content:
                continue
            
            # 3. Quarantine
            quarantine.add(content, url, trust)
            
            # 4. Immediate validation attempt (optional for speed)
            await self.validate_and_integrate()

    async def validate_and_integrate(self):
        """
        Reviews quarantined items and moves them to long-term memory if valid.
        """
        pending = quarantine.get_pending()
        for item in pending:
            # Cross-verify or use LLM to validate truthfulness
            is_valid = await self._validate(item)
            
            if is_valid:
                logger.info(f"[WebLearning] Knowledge VALIDATED. Moving to Memory: {item['content'][:50]}...")
                self.vault.add_entry(
                    fact=item["content"],
                    summary="Learned from web",
                    confidence=item["trust_score"],
                    embedding=[0.0]*384, # Placeholder for actual embedding
                    type="web_learned",
                    source=item["source"]
                )
                trust_manager.record_validation_result(item["source"], True)
            else:
                logger.warning(f"[WebLearning] Knowledge REJECTED: {item['content'][:50]}")
                trust_manager.record_validation_result(item["source"], False)

    async def _search(self, query: str) -> List[Dict[str, Any]]:
        # This would call the web_search module
        # Placeholder for demonstration
        return [{"url": "https://wikipedia.org/wiki/AI", "snippet": "Artificial Intelligence is..."}]

    async def _extract(self, result: Dict[str, Any]) -> str:
        # Extracts clean text from snippet or page
        return result.get("snippet", "")

    async def _validate(self, item: Dict[str, Any]) -> bool:
        """
        Uses a separate validation logic (e.g. LLM consensus) to verify knowledge.
        """
        # For Phase 4, we require high trust score + consistency
        return item["trust_score"] > 0.7

# Global singleton
learning_pipeline = WebLearningPipeline()
