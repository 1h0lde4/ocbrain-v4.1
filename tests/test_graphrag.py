"""
tests/test_graphrag.py — Session 5.5 GraphRAG Foundation.

Covers:
  Evidence / EvidenceSet    — data model behavior
  BFSTraversalStrategy      — multi-hop expansion, max_depth/max_nodes,
                              no revisits, failure isolation, the
                              documented entity-node dead-end limitation
  WeightedRankingStrategy   — vector-hit base score reuse, graph-only
                              neutral relevance, additive graph terms,
                              deterministic tie-breaking
  PassthroughIntentAnalyzer — no-op stage
  GraphRAGPipeline (integration, real UnifiedMemory + SQLiteGraphBackend):
    - graceful degradation: no graph backend at all
    - graph registered but no eligible seeds this query
    - consolidation: vector+graph hit for the same entry appears once
    - direct memory->memory edge traversal + provenance completeness
    - traversal failure isolation
    - stale graph_node_id (deleted entry) skipped gracefully
    - pluggable traversal/ranking/intent are genuinely swappable
    - limit is respected
    - entity nodes never become Evidence themselves
"""

import pytest

from core.memory.knowledge_entry import KnowledgeEntry
from core.memory.unified_memory import UnifiedMemory
from core.memory.backends.sqlite_graph import SQLiteGraphBackend
from core.memory.graph.entity_extractor import RegexEntityExtractor
from core.memory.graph.graph_indexer import GraphIndexer

from core.memory.retrieval.graphrag.evidence import Evidence, EvidenceSet
from core.memory.retrieval.graphrag.intent import PassthroughIntentAnalyzer, QueryIntent
from core.memory.retrieval.graphrag.pipeline import GraphRAGPipeline
from core.memory.retrieval.graphrag.ranking import RankingStrategy, WeightedRankingStrategy
from core.memory.retrieval.graphrag.traversal import (
    BFSTraversalStrategy, TraversalStrategy, TraversalResult,
)


def _entry(**overrides) -> KnowledgeEntry:
    defaults = dict(content="Default content", truth_status="verified")
    defaults.update(overrides)
    return KnowledgeEntry(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# Evidence / EvidenceSet
# ═══════════════════════════════════════════════════════════════════════════

class TestEvidenceSet:

    def test_len_and_iter(self):
        items = [Evidence(entry=_entry(entry_id="a")), Evidence(entry=_entry(entry_id="b"))]
        es = EvidenceSet(query="q", items=items)
        assert len(es) == 2
        assert [e.entry_id for e in es] == ["a", "b"]

    def test_entry_ids(self):
        items = [Evidence(entry=_entry(entry_id="x")), Evidence(entry=_entry(entry_id="y"))]
        es = EvidenceSet(query="q", items=items)
        assert es.entry_ids() == ["x", "y"]

    def test_as_context_blocks_shape_and_limit(self):
        items = [Evidence(entry=_entry(entry_id=f"e{i}"), score=float(i)) for i in range(5)]
        es = EvidenceSet(query="q", items=items)
        blocks = es.as_context_blocks(max_items=2)
        assert len(blocks) == 2
        assert set(blocks[0].keys()) >= {
            "entry_id", "content", "source", "truth_status",
            "importance", "score", "retrieval_method", "graph_distance", "path",
        }

    def test_graph_available_default_false(self):
        assert EvidenceSet(query="q").graph_available is False


# ═══════════════════════════════════════════════════════════════════════════
# BFSTraversalStrategy
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def graph(tmp_path) -> SQLiteGraphBackend:
    return SQLiteGraphBackend(str(tmp_path / "graph.db"))


class TestBFSTraversal:

    @pytest.mark.asyncio
    async def test_expand_single_hop(self, graph):
        await graph.add_node("A", "memory_entry", "A")
        await graph.add_node("B", "memory_entry", "B")
        await graph.add_edge("A", "B", "relates_to")
        results = await BFSTraversalStrategy().expand(["A"], graph, max_depth=1, max_nodes=10)
        assert len(results) == 1
        assert results[0].node_id == "B"
        assert results[0].distance == 1
        assert results[0].path[0].relation == "relates_to"
        assert results[0].seed_node_id == "A"

    @pytest.mark.asyncio
    async def test_expand_multi_hop(self, graph):
        await graph.add_node("A", "memory_entry", "A")
        await graph.add_node("B", "memory_entry", "B")
        await graph.add_node("C", "memory_entry", "C")
        await graph.add_edge("A", "B", "relates_to")
        await graph.add_edge("B", "C", "relates_to")
        results = await BFSTraversalStrategy().expand(["A"], graph, max_depth=2, max_nodes=10)
        by_id = {r.node_id: r for r in results}
        assert by_id["B"].distance == 1
        assert by_id["C"].distance == 2
        assert [h.node_id for h in by_id["C"].path] == ["B", "C"]

    @pytest.mark.asyncio
    async def test_max_depth_respected(self, graph):
        await graph.add_node("A", "memory_entry", "A")
        await graph.add_node("B", "memory_entry", "B")
        await graph.add_node("C", "memory_entry", "C")
        await graph.add_edge("A", "B", "relates_to")
        await graph.add_edge("B", "C", "relates_to")
        results = await BFSTraversalStrategy().expand(["A"], graph, max_depth=1, max_nodes=10)
        assert {r.node_id for r in results} == {"B"}

    @pytest.mark.asyncio
    async def test_max_nodes_respected(self, graph):
        await graph.add_node("A", "memory_entry", "A")
        for i in range(10):
            await graph.add_node(f"N{i}", "memory_entry", f"N{i}")
            await graph.add_edge("A", f"N{i}", "relates_to")
        results = await BFSTraversalStrategy().expand(["A"], graph, max_depth=1, max_nodes=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_never_revisits_seed_node(self, graph):
        await graph.add_node("A", "memory_entry", "A")
        await graph.add_node("B", "memory_entry", "B")
        await graph.add_edge("A", "B", "relates_to")
        await graph.add_edge("B", "A", "relates_to")   # cycle back to seed
        results = await BFSTraversalStrategy().expand(["A"], graph, max_depth=3, max_nodes=10)
        assert "A" not in {r.node_id for r in results}

    @pytest.mark.asyncio
    async def test_entity_node_is_a_dead_end(self, graph):
        """Documents the known limitation: edges are memory-node ->
        entity-node only (one direction). An entity node has no outgoing
        edges, so expansion from it finds nothing -- this is expected
        behavior today, not a bug, and this test locks it in so a future
        change to edge directionality is a deliberate decision, not an
        accidental behavior change."""
        await graph.add_node("mem:A", "memory_entry", "A")
        await graph.add_node("entity:radium", "concept", "Radium")
        await graph.add_edge("mem:A", "entity:radium", "mentions")
        results = await BFSTraversalStrategy().expand(["mem:A"], graph, max_depth=3, max_nodes=10)
        assert {r.node_id for r in results} == {"entity:radium"}   # nothing beyond it

    @pytest.mark.asyncio
    async def test_empty_seed_list(self, graph):
        assert await BFSTraversalStrategy().expand([], graph) == []

    @pytest.mark.asyncio
    async def test_failure_isolation(self):
        class _FailingGraph:
            async def get_neighbors(self, *a, **kw):
                raise RuntimeError("boom")
        results = await BFSTraversalStrategy().expand(["A"], _FailingGraph(), max_depth=1, max_nodes=10)
        assert results == []   # must not raise


# ═══════════════════════════════════════════════════════════════════════════
# WeightedRankingStrategy
# ═══════════════════════════════════════════════════════════════════════════

class TestWeightedRanking:

    def test_vector_hit_uses_precomputed_score_as_base(self):
        entry = _entry(entry_id="v1", importance=0.5)
        ev = Evidence(entry=entry, score=0.42, retrieval_method="vector")
        ranked = WeightedRankingStrategy().rank([ev])
        assert ranked[0].score_breakdown["base_composite"] == 0.42

    def test_graph_only_hit_gets_neutral_relevance_base(self):
        entry = _entry(entry_id="g1", importance=0.5)
        ev = Evidence(entry=entry, retrieval_method="graph", graph_distance=1)
        ranked = WeightedRankingStrategy().rank([ev])
        expected_base = entry.composite_score(relevance=0.0)
        assert ranked[0].score_breakdown["base_composite"] == pytest.approx(expected_base)

    def test_closer_graph_distance_scores_higher(self):
        close = Evidence(entry=_entry(entry_id="close"), retrieval_method="graph", graph_distance=1)
        far   = Evidence(entry=_entry(entry_id="far"),   retrieval_method="graph", graph_distance=5)
        ranked = WeightedRankingStrategy().rank([far, close])
        assert ranked[0].entry_id == "close"

    def test_truth_status_bonus_ordering(self):
        verified = Evidence(entry=_entry(entry_id="v", truth_status="verified"),
                             retrieval_method="graph", graph_distance=1)
        conflicted = Evidence(entry=_entry(entry_id="c", truth_status="conflicted"),
                               retrieval_method="graph", graph_distance=1)
        ranked = WeightedRankingStrategy().rank([conflicted, verified])
        assert ranked[0].entry_id == "v"

    def test_deterministic_tie_break_by_entry_id(self):
        a = Evidence(entry=_entry(entry_id="aaa"), score=0.5, retrieval_method="vector")
        b = Evidence(entry=_entry(entry_id="bbb"), score=0.5, retrieval_method="vector")
        # Force identical base scores by giving both zero importance/confidence spread
        a.entry.importance = b.entry.importance = 0.5
        ranked1 = WeightedRankingStrategy().rank([b, a])
        ranked2 = WeightedRankingStrategy().rank([a, b])
        assert [e.entry_id for e in ranked1] == [e.entry_id for e in ranked2]

    def test_graph_signal_never_displaces_pure_vector_base(self):
        """A pure vector hit (no graph_distance) must rank by its base
        composite_score alone -- graph terms are strictly additive
        elsewhere, never subtracted from a non-graph-connected item."""
        entry = _entry(entry_id="pv", truth_status="unknown")
        ev = Evidence(entry=entry, score=0.6, retrieval_method="vector")
        ranked = WeightedRankingStrategy().rank([ev])
        assert ranked[0].score == pytest.approx(0.6)   # no graph/truth terms applied when absent-by-default weight bases are 0


# ═══════════════════════════════════════════════════════════════════════════
# PassthroughIntentAnalyzer
# ═══════════════════════════════════════════════════════════════════════════

class TestPassthroughIntentAnalyzer:

    @pytest.mark.asyncio
    async def test_search_query_equals_raw_query(self):
        intent = await PassthroughIntentAnalyzer().analyze("what is OCBrain")
        assert intent.search_query == intent.raw_query == "what is OCBrain"
        assert intent.metadata == {}


# ═══════════════════════════════════════════════════════════════════════════
# GraphRAGPipeline — integration
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphRAGPipelineIntegration:

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_graph_backend(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m1"))
        await memory.write(content="OCBrain is a cognitive operating system",
                            content_type="interaction")
        pipeline = GraphRAGPipeline(memory, graph=None)
        result = await pipeline.retrieve("cognitive operating system")
        assert result.graph_available is False
        assert len(result) >= 1
        assert all(e.retrieval_method == "vector" for e in result)

    @pytest.mark.asyncio
    async def test_graph_registered_but_no_eligible_seeds(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m2"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m2_graph.db"))
        memory.register_graph_backend(graph_backend)
        # truth_status defaults to "unknown" -> not graph-eligible
        await memory.write(content="an ordinary unverified entry",
                            content_type="interaction")
        pipeline = GraphRAGPipeline(memory, graph=graph_backend)
        result = await pipeline.retrieve("ordinary unverified entry")
        assert result.graph_available is True   # graph was consulted
        assert all(e.graph_distance is None for e in result)   # nothing to expand from

    @pytest.mark.asyncio
    async def test_direct_edge_traversal_and_provenance(self, tmp_path):
        """Proves the expansion+consolidation MECHANISM end-to-end using a
        direct memory->memory edge added straight through GraphBackend --
        nothing in production code creates such edges today (see the
        Session 5.5 Architecture Decision on edge directionality), but the
        pipeline must correctly traverse and attribute provenance for one
        if it exists, since a future edge type may add exactly this."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m3"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m3_graph.db"))
        memory.register_graph_backend(graph_backend)

        seed_id = await memory.write(content="Radium was discovered by Marie Curie",
                                      content_type="interaction", truth_status="verified")
        related_id = await memory.write(content="Polonium was also discovered by Marie Curie",
                                         content_type="interaction", truth_status="verified")
        seed_node = f"mem:{seed_id}"
        related_node = f"mem:{related_id}"
        await graph_backend.add_edge(seed_node, related_node, "co_discovered", weight=0.8)

        pipeline = GraphRAGPipeline(memory, graph=graph_backend, vector_limit=1)
        # vector_limit=1 forces only the seed to be vector-retrieved (it's
        # the better lexical match for this query), so `related` can only
        # be found via graph expansion -- proving expansion actually ran.
        result = await pipeline.retrieve("Radium discovered")

        assert result.graph_available is True
        related_evidence = next((e for e in result if e.entry_id == related_id), None)
        assert related_evidence is not None, "related entry should be reachable via graph expansion"
        assert related_evidence.retrieval_method == "graph"
        assert related_evidence.graph_distance == 1
        assert related_evidence.seed_entry_id == seed_id
        assert related_evidence.path[0].relation == "co_discovered"
        assert related_evidence.score_breakdown["edge_confidence"] == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_consolidation_merges_vector_and_graph_hit(self, tmp_path):
        """An entry found by BOTH vector search and graph traversal must
        appear exactly once, enriched with graph provenance -- not twice."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m4"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m4_graph.db"))
        memory.register_graph_backend(graph_backend)

        seed_id = await memory.write(content="quantum computing breakthrough research",
                                      content_type="interaction", truth_status="verified")
        also_vector_hit_id = await memory.write(
            content="quantum computing breakthrough announcement",
            content_type="interaction", truth_status="verified")
        await graph_backend.add_edge(f"mem:{seed_id}", f"mem:{also_vector_hit_id}",
                                      "relates_to")

        pipeline = GraphRAGPipeline(memory, graph=graph_backend, vector_limit=10)
        result = await pipeline.retrieve("quantum computing breakthrough")

        matches = [e for e in result if e.entry_id == also_vector_hit_id]
        assert len(matches) == 1   # never duplicated
        assert matches[0].graph_distance == 1   # enriched with graph provenance
        assert matches[0].retrieval_method == "vector"   # keeps the stronger original signal

    @pytest.mark.asyncio
    async def test_traversal_failure_isolation(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m5"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m5_graph.db"))
        memory.register_graph_backend(graph_backend)
        await memory.write(content="entry with a seed graph node",
                            content_type="interaction", truth_status="verified")

        class _BrokenTraversal(TraversalStrategy):
            async def expand(self, seed_node_ids, graph, max_depth=2, max_nodes=25):
                raise RuntimeError("traversal exploded")

        pipeline = GraphRAGPipeline(memory, graph=graph_backend, traversal=_BrokenTraversal())
        result = await pipeline.retrieve("entry with a seed graph node")
        assert result.graph_available is False   # traversal failed -> visibly False
        assert len(result) >= 1                  # still returns vector-only evidence

    @pytest.mark.asyncio
    async def test_stale_graph_node_pointing_at_nonexistent_entry(self, tmp_path):
        """A graph edge pointing at a node_id with no corresponding
        KnowledgeEntry in canonical storage (the orphaned-node case a real
        rebuild/cleanup gap could produce) must be skipped gracefully, not
        raise. Points at a fabricated id that was never written, rather
        than writing-then-deleting a real entry -- the latter would still
        be visible via UnifiedMemory's L0 cache unless evicted through the
        public delete() path, which would defeat the point of simulating
        genuine staleness."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m6"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m6_graph.db"))
        memory.register_graph_backend(graph_backend)

        seed_id = await memory.write(content="seed entry for stale node test",
                                      content_type="interaction", truth_status="verified")
        fake_entry_id = "00000000-0000-0000-0000-000000000000"
        await graph_backend.add_node(f"mem:{fake_entry_id}", "memory_entry", "ghost")
        await graph_backend.add_edge(f"mem:{seed_id}", f"mem:{fake_entry_id}", "relates_to")

        pipeline = GraphRAGPipeline(memory, graph=graph_backend)
        result = await pipeline.retrieve("seed entry for stale node test")   # must not raise
        assert fake_entry_id not in result.entry_ids()

    @pytest.mark.asyncio
    async def test_custom_traversal_and_ranking_are_swappable(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m7"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m7_graph.db"))
        memory.register_graph_backend(graph_backend)
        await memory.write(content="entry for pluggability test",
                            content_type="interaction", truth_status="verified")

        class _NoOpTraversal(TraversalStrategy):
            async def expand(self, seed_node_ids, graph, max_depth=2, max_nodes=25):
                return []   # deliberately finds nothing, to prove it's actually used

        class _ReverseRanking(RankingStrategy):
            def rank(self, evidence):
                return list(reversed(evidence))

        pipeline = GraphRAGPipeline(
            memory, graph=graph_backend,
            traversal=_NoOpTraversal(), ranking=_ReverseRanking(),
        )
        result = await pipeline.retrieve("entry for pluggability test")
        assert result.graph_available is True
        assert all(e.graph_distance is None for e in result)   # NoOpTraversal really ran

    @pytest.mark.asyncio
    async def test_limit_is_respected(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m8"))
        for i in range(5):
            await memory.write(content=f"limit test entry number {i}",
                                content_type="interaction")
        pipeline = GraphRAGPipeline(memory, graph=None, vector_limit=10)
        result = await pipeline.retrieve("limit test entry", limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_entity_nodes_never_become_evidence(self, tmp_path):
        """Regression guard for the documented limitation: an
        entity-extracted node is a traversal waypoint, never itself
        retrievable Evidence, in this session."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m9"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m9_graph.db"),)
        memory.register_graph_backend(graph_backend, entity_extractor=RegexEntityExtractor())

        seed_id = await memory.write(content="Marie Curie discovered Radium.",
                                      content_type="interaction", truth_status="verified")
        pipeline = GraphRAGPipeline(memory, graph=graph_backend)
        result = await pipeline.retrieve("Marie Curie discovered Radium")
        assert all(not eid.startswith("entity:") for eid in result.entry_ids())
