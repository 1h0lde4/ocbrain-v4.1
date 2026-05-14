import asyncio
import os
import shutil

import pytest

from core.provider_mesh import generate_with_fallback, Provider
from interface.api import QueryResponse


@pytest.mark.asyncio
async def test_api_response_contract():
    # Verify QueryResponse model structure
    resp = QueryResponse(
        success=True,
        answer="Hello world",
        data={"query": "test"},
        meta={"ver": "1.0"},
    )
    assert resp.success is True
    assert resp.answer == "Hello world"
    assert "query" in resp.data

@pytest.mark.asyncio
async def test_provider_mesh_hardening():
    class MockProvider(Provider):
        def __init__(self, name, should_fail=False):
            super().__init__()
            self._name = name
            self.should_fail = should_fail
        
        @property
        def name(self):
            return self._name
        
        async def generate(self, prompt):
            if self.should_fail:
                raise RuntimeError("Failed")
            return "Success"

    p1 = MockProvider("P1", should_fail=True)
    p2 = MockProvider("P2", should_fail=False)
    
    # First attempt should fail p1 and succeed with p2
    result = await generate_with_fallback([p1, p2], "test prompt")
    assert result == "Success"
    assert p1.health_score < 100
    assert p1.consecutive_failures == 1
    assert not p1.is_available()

    # Second attempt should skip p1 (cooldown) and use p2
    # We'll mock sorted to verify p1 isn't even tried
    result2 = await generate_with_fallback([p1, p2], "test prompt")
    assert result2 == "Success"

@pytest.mark.asyncio
async def test_memory_hybrid_retrieval():
    from core.memory.mem_vault import MemoryVault
    from core.memory.hybrid_retrieval import HybridRetriever

    test_dir = ".data/test_memory"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    vault = MemoryVault(storage_dir=test_dir)
    # Add some entries
    vault.add_entry(
        fact="The sky is blue",
        summary="Sky color",
        confidence=0.9,
        embedding=[0.1] * 384,
    )
    vault.add_entry(
        fact="Grass is green",
        summary="Grass color",
        confidence=0.8,
        embedding=[0.2] * 384,
    )
    
    retriever = HybridRetriever(vault)
    results = retriever.hybrid_search("What color is the sky?")
    
    assert len(results) > 0
    assert "sky" in results[0]["fact"].lower()
    assert results[0]["access_count"] == 2  # 1 (init) + 1 (retrieval)

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    asyncio.run(test_api_response_contract())
    asyncio.run(test_provider_mesh_hardening())
    print("Tests passed!")
