import pytest
import os
from core.memory.mem_vault import MemoryVault

def test_memory_vault_operations(temp_data_dir):
    vault_dir = os.path.join(temp_data_dir, "memory")
    vault = MemoryVault(storage_dir=vault_dir)
    
    # Test add
    entry_id = vault.add_entry(
        fact="The sky is blue.",
        summary="Sky color",
        confidence=0.9,
        embedding=[0.1, 0.2, 0.3],
        tags=["nature"]
    )
    
    assert len(vault.entries) == 1
    assert entry_id is not None
    
    # Test get
    entry = vault.get_entry(entry_id)
    assert entry is not None
    assert entry["fact"] == "The sky is blue."
    
    # Test persist
    vault2 = MemoryVault(storage_dir=vault_dir)
    assert len(vault2.entries) == 1
    
    # Test BM25 placeholder search
    results = vault.bm25_search_placeholder("sky")
    assert len(results) == 1
    assert results[0]["id"] == entry_id
    
    results_empty = vault.bm25_search_placeholder("ocean")
    assert len(results_empty) == 0
    
    # Test get_all_embeddings
    ids, embeddings = vault.get_all_embeddings()
    assert ids == [entry_id]
    assert embeddings == [[0.1, 0.2, 0.3]]
