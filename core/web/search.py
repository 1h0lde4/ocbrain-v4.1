import abc
from typing import List

class SearchEngine(abc.ABC):
    @abc.abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[str]:
        """
        Search the internet and return top_k URLs.
        """
        pass

class DuckDuckGoSearch(SearchEngine):
    """
    Placeholder for DuckDuckGo search implementation.
    In a real system, you would use a library like `duckduckgo-search`.
    """
    async def search(self, query: str, top_k: int = 5) -> List[str]:
        # TODO: Implement actual DuckDuckGo search logic using a web scraping library or API
        # Returning dummy URLs for pipeline structural integrity
        print(f"[Search] Querying '{query}' (top_k={top_k})")
        return [f"https://example.com/search?q={query.replace(' ', '+')}&rank={i}" for i in range(1, top_k + 1)]

class SearchOrchestrator:
    def __init__(self, engine: SearchEngine):
        self.engine = engine
        
    def set_engine(self, engine: SearchEngine):
        self.engine = engine

    async def execute_search(self, query: str, top_k: int = 5) -> List[str]:
        return await self.engine.search(query, top_k)
