"""
tests/test_k2_2_retrieval_cutover.py — K2.2 Retrieval Runtime Completion
(Canonical Retrieval Cutover) test suite.

Covers, per the K2.2 session's explicit testing requirements:
  - RetrievalContextBuilder is now the production path
  - GraphRAGPipeline executes during retrieval (graph expansion reaches
    assemble_context()'s actual output, not just the pipeline in isolation)
  - RetrievalFusionEngine is compatibility only — proven behaviorally
    (graph-expanded results reach it too), not just structurally
  - Legacy callers still function (Orchestrator/PlannerWorker call shape)
  - Context quality unchanged or improved
  - Provenance survives the cutover
  - Contradiction detection still functions through the full path
  - No regression in UnifiedMemory (covered by the full existing
    test_unified_memory.py suite, unmodified by this session; this file
    adds a light direct check rather than duplicating that coverage)

Architecture references: KERNEL_ARCHITECTURE_v1.0.md §13,
K2_IMPLEMENTATION_PLAN.md K2.2.
"""

import pytest

from core.memory.unified_memory import UnifiedMemory
from core.memory.assembly import ContextAssemblyEngine
from core.memory.retrieval.fusion import RetrievalFusionEngine
from core.memory.retrieval.graphrag import GraphRAGPipeline
from core.memory.retrieval.context import RetrievalContextBuilder
from core.memory.backends.sqlite_graph import SQLiteGraphBackend


# ── ContextAssemblyEngine uses the canonical pipeline ──────────────────────────

class TestContextAssemblyEngineUsesCanonicalPipeline:

    def test_engine_constructs_canonical_pipeline_components(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        assert isinstance(engine._graphrag, GraphRAGPipeline)
        assert isinstance(engine._context_builder, RetrievalContextBuilder)

    @pytest.mark.asyncio
    async def test_output_format_and_layer_grouping_preserved(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        await memory.write(content="Timeout is set to 30 seconds",
                            content_type="interaction", truth_status="verified",
                            layer_hint="l1")
        await memory.write(content="General knowledge about network timeouts",
                            content_type="interaction", truth_status="verified",
                            layer_hint="l2")
        await memory.write(content="Fix: raise the timeout to 60 seconds",
                            content_type="interaction", truth_status="verified",
                            layer_hint="l3", procedure_name="timeout_fix")

        result = await engine.assemble_context("timeout")

        assert "### RELEVANT KNOWLEDGE (Semantic)" in result
        assert "### PROVEN FIX PATTERNS (Procedural)" in result
        assert "### RECENT EPISODES (Timeline)" in result
        assert "raise the timeout to 60 seconds" in result

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty_string(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        result = await engine.assemble_context("no_possible_match_xyz123")
        assert result == ""

    @pytest.mark.asyncio
    async def test_return_type_and_optional_embedding_signature_unchanged(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        await memory.write(content="timeout example entry", content_type="interaction")
        result_no_embedding = await engine.assemble_context("timeout")
        result_explicit_none = await engine.assemble_context("timeout", query_embedding=None)
        assert isinstance(result_no_embedding, str)
        assert isinstance(result_explicit_none, str)


# ── GraphRAGPipeline genuinely executes: expansion reaches the final string ────

class TestGraphExpansionReachesAssembleContextOutput:
    """The differentiator between legacy and canonical: a related entry
    unreachable by vector/BM25 search alone, surfaced only via a graph
    edge, must appear in assemble_context()'s actual string output — not
    merely in GraphRAGPipeline's own isolated return value (already
    proven by test_graphrag.py; this proves the wiring carries it all
    the way through)."""

    @pytest.mark.asyncio
    async def test_graph_only_reachable_entry_appears_in_output(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "graph.db"))
        memory.register_graph_backend(graph_backend)

        seed_id = await memory.write(
            content="Radium was discovered by Marie Curie",
            content_type="interaction", truth_status="verified")
        related_id = await memory.write(
            content="Polonium was also discovered by Marie Curie",
            content_type="interaction", truth_status="verified")
        await graph_backend.add_edge(f"mem:{seed_id}", f"mem:{related_id}",
                                      "co_discovered", weight=0.8)

        # Construct the engine's own GraphRAGPipeline replacement with
        # vector_limit=1 (same technique test_graphrag.py's own integration
        # tests use) so the related entry is reachable ONLY via graph
        # expansion, proving expansion genuinely ran through this path.
        engine = ContextAssemblyEngine(memory)
        engine._graphrag = GraphRAGPipeline(memory, graph=graph_backend, vector_limit=1)

        result = await engine.assemble_context("Radium discovered")
        assert "Polonium" in result, (
            "graph-only-reachable entry must reach assemble_context()'s "
            "actual output, not just GraphRAGPipeline's own return value"
        )

    @pytest.mark.asyncio
    async def test_graceful_degradation_when_no_graph_backend_registered(self, tmp_path):
        # No register_graph_backend() call -- memory.graph is None.
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        assert memory.graph is None
        await memory.write(content="timeout entry with no graph backend at all",
                            content_type="interaction")
        # Must not raise, and must still return vector-only results --
        # identical coverage to the pre-K2.2 path when nothing is registered.
        result = await engine.assemble_context("timeout")
        assert "timeout entry with no graph backend at all" in result


# ── Contradiction detection and provenance survive the cutover ────────────────

class TestContradictionAndProvenanceSurviveCutover:
    """assemble_context() itself only returns a string (preserved contract —
    it never rendered contradiction/provenance detail even pre-K2.2), so
    these are checked at the Context object the same two internal calls
    produce, proving the DATA survives the cutover even though the string
    formatter's shape doesn't change."""

    @pytest.mark.asyncio
    async def test_contradiction_groups_populated_through_the_cutover_path(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        e1 = await memory.write(content="The deployment window is Tuesday at 2pm",
                                 content_type="interaction", truth_status="verified")
        e2 = await memory.write(content="The deployment window is Thursday at 2pm",
                                 content_type="interaction", truth_status="verified")
        await memory.update(e1, {"contradicts": [e2]})
        await memory.update(e2, {"contradicts": [e1]})

        evidence_set = await engine._graphrag.retrieve("deployment window")
        context = engine._context_builder.build(evidence_set)

        assert len(context.contradiction_groups) >= 1, (
            "contradiction detection must still fire through the exact "
            "two calls assemble_context() makes internally"
        )

    @pytest.mark.asyncio
    async def test_provenance_populated_through_the_cutover_path(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        await memory.write(content="Fix: increase the connection pool size",
                            content_type="interaction", source="incident-4471",
                            truth_status="verified", confidence=0.95)

        evidence_set = await engine._graphrag.retrieve("connection pool")
        context = engine._context_builder.build(evidence_set)

        assert len(context.blocks) >= 1
        block = context.blocks[0]
        assert block.provenance is not None
        assert block.provenance.source == "incident-4471"
        assert block.provenance.confidence == pytest.approx(0.95)


# ── RetrievalFusionEngine: compatibility façade only, genuinely delegating ────

class TestRetrievalFusionEngineIsCompatibilityOnly:
    """Proves delegation behaviorally, not just structurally: a plain
    facade that called UnifiedMemory.search() directly could never surface
    a graph-only-reachable entry. If fuse_search() does, it is genuinely
    routing through GraphRAGPipeline."""

    def test_constructs_graphrag_pipeline_internally(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        fusion = RetrievalFusionEngine(memory)
        assert isinstance(fusion._graphrag, GraphRAGPipeline)

    @pytest.mark.asyncio
    async def test_fuse_search_surfaces_graph_only_reachable_entry(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "graph.db"))
        memory.register_graph_backend(graph_backend)

        seed_id = await memory.write(content="Quarterly revenue report published",
                                      content_type="interaction", truth_status="verified")
        related_id = await memory.write(content="Contains a material restatement note",
                                         content_type="interaction", truth_status="verified")
        await graph_backend.add_edge(f"mem:{seed_id}", f"mem:{related_id}", "relates_to")

        fusion = RetrievalFusionEngine(memory)
        fusion._graphrag = GraphRAGPipeline(memory, graph=graph_backend, vector_limit=1)

        results = await fusion.fuse_search("Quarterly revenue report", top_k=10)
        contents = [r.entry.content for r in results]
        assert any("material restatement" in c for c in contents), (
            "RetrievalFusionEngine must delegate to the canonical pipeline, "
            "not call UnifiedMemory.search() directly (K2.2 Rule 3)"
        )

    @pytest.mark.asyncio
    async def test_returns_search_result_shape_unchanged(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        fusion = RetrievalFusionEngine(memory)
        await memory.write(content="a plain entry for shape checking",
                            content_type="interaction")
        results = await fusion.fuse_search("plain entry", top_k=5)
        assert len(results) >= 1
        r = results[0]
        assert hasattr(r, "entry") and hasattr(r, "composite_score")
        assert hasattr(r, "bm25_score") and hasattr(r, "vector_score")
        assert hasattr(r, "recency_score")


# ── Legacy callers still function ──────────────────────────────────────────────

class TestLegacyCallersStillFunction:
    """Simulates the exact call shape used by core/orchestrator.py:333 and
    core/workers/planner.py:124 — the only two real production callers."""

    @pytest.mark.asyncio
    async def test_orchestrator_call_shape(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        await memory.write(content="orchestrator-relevant entry about timeouts",
                            content_type="interaction")
        # Orchestrator.handle(): `memory_context = await context_assembler.assemble_context(query)`
        memory_context = await engine.assemble_context("timeouts")
        assert isinstance(memory_context, str)
        assert "orchestrator-relevant entry" in memory_context

    @pytest.mark.asyncio
    async def test_planner_worker_call_shape(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        engine = ContextAssemblyEngine(memory)
        await memory.write(content="planner-relevant entry about scheduling",
                            content_type="interaction")
        # PlannerWorker: same call shape, query positional, no embedding.
        result = await engine.assemble_context("scheduling")
        assert isinstance(result, str)


# ── No regression in UnifiedMemory ─────────────────────────────────────────────

class TestNoUnifiedMemoryRegression:
    """UnifiedMemory itself was not modified this session beyond the
    additive `graph` property (§ session report). Full regression coverage
    is the existing, unmodified test_unified_memory.py suite; this is a
    light direct sanity check that write()/search() still behave normally
    when exercised through the new call path."""

    @pytest.mark.asyncio
    async def test_write_and_search_still_work_directly(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        await memory.write(content="direct write/search sanity check",
                            content_type="interaction")
        results = await memory.search(query="sanity check", limit=5)
        assert len(results) >= 1

    def test_graph_property_defaults_to_none_and_reflects_registration(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m"))
        assert memory.graph is None
        graph_backend = SQLiteGraphBackend(str(tmp_path / "graph.db"))
        memory.register_graph_backend(graph_backend)
        assert memory.graph is graph_backend
