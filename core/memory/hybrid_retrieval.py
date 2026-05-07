import logging
from typing import List, Dict, Any
from core.memory.mem_vault import MemoryVault

logger = logging.getLogger("ocbrain.memory.hybrid")

try:
    from scipy.spatial.distance import cosine
except ImportError:
    cosine = None
    logger.warning("scipy not installed. Semantic search will fallback to naive search.")

class HybridRetriever:
    """
    Combines dense (semantic) and sparse (BM25 keyword) retrieval.
    """
    def __init__(self, vault: MemoryVault):
        self.vault = vault

    def semantic_search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if not cosine:
            return []
            
        ids, embeddings = self.vault.get_all_embeddings()
        if not ids:
            return []

        scored_results = []
        for entry_id, emb in zip(ids, embeddings):
            # Cosine distance is [0, 2]. Similarity is 1 - distance.
            dist = cosine(query_embedding, emb)
            sim = max(0.0, min(1.0, 1.0 - dist))
            scored_results.append((sim, entry_id))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for score, entry_id in scored_results[:top_k]:
            entry = self.vault.get_entry(entry_id)
            if entry:
                # Inject runtime similarity score for downstream reranking
                entry["_semantic_score"] = float(score)
                results.append(entry)
                
        return results

    def hybrid_search(self, query: str, query_embedding: List[float] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Combines BM25 and Semantic search using Reciprocal Rank Fusion (RRF).
        RRF(d) = sum_{r in R} 1 / (k + rank(d, r))
        """
        keyword_results = self.vault.bm25_search_placeholder(query, top_k=top_k * 3)
        semantic_results = []
        if query_embedding:
            semantic_results = self.semantic_search(query_embedding, top_k=top_k * 3)

        rrf_scores = {} # entry_id -> rrf_score
        k = 60 # RRF constant

        # Keyword ranks
        for i, entry in enumerate(keyword_results):
            entry_id = entry["id"]
            rrf_scores[entry_id] = rrf_scores.get(entry_id, 0.0) + (1.0 / (k + i + 1))

        # Semantic ranks
        for i, entry in enumerate(semantic_results):
            entry_id = entry["id"]
            rrf_scores[entry_id] = rrf_scores.get(entry_id, 0.0) + (1.0 / (k + i + 1))

        # Combine with Importance scoring
        final_results = []
        for entry_id, rrf_score in rrf_scores.items():
            entry = self.vault.get_entry(entry_id)
            if not entry:
                continue
            
            # Final score = RRF + normalized importance
            # Importance is [0, 1]. We weight it slightly to boost 'high value' memories.
            importance = entry.get("importance", 1.0)
            final_score = rrf_score + (importance * 0.01) 
            
            final_results.append((final_score, entry))

        final_results.sort(key=lambda x: x[0], reverse=True)
        
        # Increment access count for retrieved entries
        top_entries = [r[1] for r in final_results[:top_k]]
        for entry in top_entries:
            entry["access_count"] = entry.get("access_count", 0) + 1
        
        self.vault._save()
        return top_entries
