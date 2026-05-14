import logging
from typing import List
from .retrieval.fusion import fusion_engine

logger = logging.getLogger("ocbrain.memory.assembly")

class ContextAssemblyEngine:
    """
    Goal-aware Context Assembly.
    Builds the final context string from multi-tier memories.
    """
    def assemble_context(self, query: str, query_embedding: List[float] = None) -> str:
        # 1. Retrieve fused memories
        memories = fusion_engine.fuse_search(query, query_embedding, top_k=10)
        
        # 2. Group by tier
        episodic = [m for m in memories if m["tier"] == "L1"]
        semantic = [m for m in memories if m["tier"] == "L2"]
        procedural = [m for m in memories if m["tier"] == "L3"]
        
        # 3. Format sections
        sections = []
        
        if semantic:
            sections.append("### RELEVANT KNOWLEDGE (Semantic)")
            for m in semantic:
                sections.append(f"- {m['content']}")
        
        if procedural:
            sections.append("### PROVEN FIX PATTERNS (Procedural)")
            for m in procedural:
                sections.append(f"- {m['content']}")
                
        if episodic:
            sections.append("### RECENT EPISODES (Timeline)")
            for m in episodic:
                sections.append(f"[{m['timestamp']}] {m['content']}")

        return "\n\n".join(sections)

# Global singleton
context_assembler = ContextAssemblyEngine()
