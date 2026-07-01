"""
core/memory/backends/base.py — v4.3.4.91 Memory Abstraction Layer
Abstract backend interfaces. All UnifiedMemory dependencies go through
these — never against concrete implementations directly.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.knowledge_entry import KnowledgeEntry
    from core.memory.knowledge_event import KnowledgeEvent


class StorageBackend(ABC):
    """Primary CRUD + text search (L1 Episodic layer)."""

    @abstractmethod
    async def write(self, entry: "KnowledgeEntry") -> str: ...

    @abstractmethod
    async def read(self, entry_id: str) -> "Optional[KnowledgeEntry]": ...

    @abstractmethod
    async def update(self, entry_id: str, delta: Dict[str, Any]) -> bool: ...

    @abstractmethod
    async def delete(self, entry_id: str) -> bool: ...

    @abstractmethod
    async def search_text(self, query: str, limit: int = 10,
                           layer: Optional[str] = None,
                           min_importance: float = 0.0,
                           truth_status: Optional[str] = None
                           ) -> "List[KnowledgeEntry]": ...

    @abstractmethod
    async def get_by_layer(self, layer: str, limit: int = 100,
                            min_importance: float = 0.0) -> "List[KnowledgeEntry]": ...

    @abstractmethod
    async def get_by_truth_status(self, truth_status: str,
                                   limit: int = 100) -> "List[KnowledgeEntry]": ...

    @abstractmethod
    async def count(self, layer: Optional[str] = None) -> int: ...

    @abstractmethod
    async def stats(self) -> Dict[str, Any]: ...

    async def close(self) -> None:
        pass


class VectorBackend(ABC):
    """Embedding index + hybrid search (L2 Semantic layer)."""

    @abstractmethod
    async def index(self, entry_id: str, content: str,
                     embedding: Optional[List[float]] = None) -> None: ...

    @abstractmethod
    async def remove(self, entry_id: str) -> None: ...

    @abstractmethod
    async def search_bm25(self, query: str,
                           top_k: int = 10) -> List[Tuple[str, float]]: ...

    @abstractmethod
    async def search_vector(self, query_embedding: List[float],
                             top_k: int = 10) -> List[Tuple[str, float]]: ...

    async def search_hybrid(self, query: str,
                             query_embedding: Optional[List[float]] = None,
                             top_k: int = 10,
                             rrf_k: int = 60) -> List[Tuple[str, float]]:
        """Default RRF fusion. Subclasses may override."""
        bm25_hits = await self.search_bm25(query, top_k=top_k * 2)
        bm25_ranks = {eid: i for i, (eid, _) in enumerate(bm25_hits)}
        vec_ranks: Dict[str, int] = {}
        if query_embedding:
            vec_hits = await self.search_vector(query_embedding, top_k=top_k * 2)
            vec_ranks = {eid: i for i, (eid, _) in enumerate(vec_hits)}
        all_ids = set(bm25_ranks) | set(vec_ranks)
        fused = []
        for eid in all_ids:
            score = (1.0 / (rrf_k + bm25_ranks.get(eid, top_k * 2)) +
                     1.0 / (rrf_k + vec_ranks.get(eid, top_k * 2)))
            fused.append((eid, score))
        fused.sort(key=lambda x: x[1], reverse=True)
        return fused[:top_k]

    @abstractmethod
    async def stats(self) -> Dict[str, Any]: ...

    async def close(self) -> None:
        pass


class GraphBackend(ABC):
    """Entity-relationship knowledge graph (L3 Graph layer)."""

    @abstractmethod
    async def add_node(self, node_id: str, node_type: str, name: str,
                        properties: Optional[Dict[str, Any]] = None) -> str: ...

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def add_edge(self, source: str, target: str, relation: str,
                        weight: float = 1.0,
                        properties: Optional[Dict[str, Any]] = None) -> int: ...

    @abstractmethod
    async def get_neighbors(self, node_id: str,
                             relation: Optional[str] = None,
                             limit: int = 50) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def search_nodes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def find_contradictions(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its incident edges.

        Returns:
            True  — node existed and was deleted.
            False — node not found; no-op.
        """
        ...

    @abstractmethod
    async def stats(self) -> Dict[str, Any]: ...

    async def close(self) -> None:
        pass


class ArchiveBackend(ABC):
    """Immutable append-only audit log (L4 Archive layer)."""

    @abstractmethod
    async def append_event(self, event: "KnowledgeEvent") -> None: ...

    @abstractmethod
    async def append_entry_snapshot(self, entry: "KnowledgeEntry",
                                     reason: str = "") -> None: ...

    @abstractmethod
    async def query_events(self,
                            entry_id: Optional[str] = None,
                            event_type: Optional[str] = None,
                            worker_id: Optional[str] = None,
                            since: float = 0.0,
                            until: float = 0.0,
                            limit: int = 100) -> "List[KnowledgeEvent]": ...

    @abstractmethod
    async def replay(self, since: float = 0.0) -> "AsyncIterator[KnowledgeEvent]": ...

    @abstractmethod
    async def export_jsonl(self, path: str, since: float = 0.0) -> int: ...

    @abstractmethod
    async def stats(self) -> Dict[str, Any]: ...

    async def close(self) -> None:
        pass


class L0Cache(ABC):
    """In-process LRU working memory. Never persisted."""

    @abstractmethod
    def put(self, entry_id: str, entry: "KnowledgeEntry") -> None: ...

    @abstractmethod
    def get(self, entry_id: str) -> "Optional[KnowledgeEntry]": ...

    @abstractmethod
    def evict(self, entry_id: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def stats(self) -> Dict[str, Any]: ...
