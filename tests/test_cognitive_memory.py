import pytest
import asyncio
from core.memory.cognitive_vault import cognitive_vault
from core.memory.graph.graph_engine import graph_engine
from core.memory.retrieval.fusion import RetrievalFusionEngine
from core.memory.unified_memory import get_unified_memory
from core.memory.assembly import context_assembler
from core.governance.memory_governor import memory_governor

# K2.2 note (fixed this session, see docs/reports/K2_2_RETRIEVAL_CUTOVER_REPORT.md):
# this file's `from core.memory.retrieval.fusion import fusion_engine` line
# failed collection entirely -- fusion_engine (a module-level singleton) was
# removed in Session 3B, well before K2.2; RetrievalFusionEngine has taken
# constructor injection ever since. cognitive_vault and graph_engine (below)
# were NOT broken -- both are real, still-functioning legacy modules, just
# no longer the store RetrievalFusionEngine/ContextAssemblyEngine read from
# (that's UnifiedMemory now, a separate store from cognitive_vault since the
# migration). test_retrieval_fusion / test_context_assembly write their own
# data into UnifiedMemory directly for that reason, rather than relying on
# test_cognitive_storage_and_provenance's cognitive_vault writes, which the
# current retrieval path cannot see.

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
    # K2.2 fix: get_neighbors() returns a list of dicts
    # ({"target_id", "relation", "target_type", "weight"}), not tuples --
    # the original n[0]/n[1] indexing raised KeyError against a dict.
    assert any(n["target_id"] == "FIX_01" and n["relation"] == "resolved_by"
               for n in neighbors)

@pytest.mark.asyncio
async def test_retrieval_fusion():
    # K2.2 fix: RetrievalFusionEngine has no module-level singleton (Session
    # 3B); construct it with the process UnifiedMemory instance, the same
    # one context_assembler (below) uses, and write this test's own data
    # into it -- cognitive_vault's data above is not visible to it.
    memory = get_unified_memory()
    await memory.write(content="Provider mesh failed due to timeout on Ollama(llama3)",
                        content_type="interaction", truth_status="verified")
    fusion = RetrievalFusionEngine(memory)
    results = await fusion.fuse_search("timeout")
    assert len(results) > 0
    assert any("timeout" in r.entry.content.lower() for r in results)

@pytest.mark.asyncio
async def test_context_assembly():
    memory = get_unified_memory()
    await memory.write(content="Recent episode: timeout occurred during provider call",
                        content_type="interaction", truth_status="verified",
                        layer_hint="l1")
    # K2.2 fix: assemble_context() is async (Session 3B); the original
    # call was missing await entirely, which would have returned a
    # coroutine object rather than a string.
    context_str = await context_assembler.assemble_context("timeout")
    assert "### RECENT EPISODES" in context_str
    assert "timeout" in context_str.lower()

@pytest.mark.asyncio
async def test_governance_limits():
    # Try to add a very low confidence memory
    is_valid = memory_governor.validate_ingestion({"confidence": 0.1, "content": "Bad data"})
    assert not is_valid
