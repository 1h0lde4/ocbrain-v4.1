"""
learning/embedder.py — Embeds clean chunks and upserts into each module's ChromaDB.
"""
import time
from pathlib import Path
from learning.chunker import Chunk


def ingest_chunks(module_name: str, chunks: list[Chunk], registry: dict):
    """
    Embed and write chunks into the named module's ChromaDB collection.
    registry: the loaded dict of {name: BaseModule} from module_registry.
    """
    if not chunks:
        return

    module = registry.get(module_name)
    if module is None:
        print(f"[embedder] Module '{module_name}' not found in registry.")
        return

    texts     = [c.text for c in chunks]
    metadatas = [
        {
            "timestamp":     c.timestamp,
            "quality_score": c.quality_score,
            "source_url":    c.source_url,
            "source_type":   c.source_type,
            "module":        module_name,
        }
        for c in chunks
    ]
    module.ingest(texts, metadatas)
    print(f"[embedder] Ingested {len(chunks)} chunks into '{module_name}'")
