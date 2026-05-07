import pytest
import asyncio
from core.memory.cognitive_vault import cognitive_vault
from core.memory.graph.graph_engine import graph_engine
from core.memory.retrieval.fusion import fusion_engine
from core.memory.assembly import context_assembler
from core.governance.memory_governor import memory_governor

@pytest.mark.asyncio
async def test_cognitive_storage_and_provenance():
    # Add an episodic memory
    eid = cognitive_vault.add_entry(
        content="Provider mesh failed due to timeout on Ollama(llama3)",
        tier="L1",
        source="system_event",
        confidence=1.0
    )
    
    # Add a procedural fix derived from that event
    fid = cognitive_vault.add_entry(
        content="Increase Ollama timeout to 60s",
        tier="L3",
        source="upgrade_planner",
        derived_from=[eid]
    )
    
    entry = cognitive_vault.get_entry(fid)
    assert entry["tier"] == "L3"
    assert eid in entry["derived_from"]

@pytest.mark.asyncio
async def test_graph_relationships():
    # Link a failure to a fix in the graph
    graph_engine.add_node("EVT_01", "event", "OllamaTimeout")
    graph_engine.add_node("FIX_01", "fix", "TimeoutIncrease")
    graph_engine.add_edge("EVT_01", "FIX_01", "resolved_by")
    
    neighbors = graph_engine.get_neighbors("EVT_01")
    assert any(n[0] == "FIX_01" and n[1] == "resolved_by" for n in neighbors)

@pytest.mark.asyncio
async def test_retrieval_fusion():
    # Search for "timeout"
    results = fusion_engine.fuse_search("timeout")
    # Should find the episodic memory added in the first test
    assert len(results) > 0
    assert any("timeout" in r["content"].lower() for r in results)

@pytest.mark.asyncio
async def test_context_assembly():
    context_str = context_assembler.assemble_context("timeout")
    assert "### RECENT EPISODES" in context_str
    assert "timeout" in context_str.lower()

@pytest.mark.asyncio
async def test_governance_limits():
    # Try to add a very low confidence memory
    is_valid = memory_governor.validate_ingestion({"confidence": 0.1, "content": "Bad data"})
    assert is_valid == False

if __name__ == "__main__":
    asyncio.run(test_cognitive_storage_and_provenance())
    asyncio.run(test_graph_relationships())
    asyncio.run(test_retrieval_fusion())
    asyncio.run(test_context_assembly())
    asyncio.run(test_governance_limits())
    print("Cognitive Memory tests passed!")
