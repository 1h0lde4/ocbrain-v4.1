"""
tests/test_context_builder.py — Session 5.6 Retrieval Context Builder.

Covers:
  HeuristicTokenCounter      — basic counting behavior
  MinHashDuplicateDetector   — near-duplicate grouping, O(n), no pairwise compare
  RetrievalContextBuilder:
    - empty input
    - no duplicates/no contradictions: order preserved, one block per item
    - duplicate consolidation: merged_entry_ids, no second block created
    - contradiction grouping: pairwise, transitive (3+), deterministic group_id,
      a contradicts[] reference to an entry NOT in this EvidenceSet (no error)
    - supports[] carried through without creating a group
    - token budgeting: partial truncation, dropped_entry_ids includes merged
      members, budget=None means nothing dropped
    - provenance preservation (all fields)
    - determinism (same input -> identical output across repeated calls)
    - decoupling: GraphRAGPipeline is never imported by anything in this
      package except as a source of the Evidence/EvidenceSet TYPE
    - end-to-end integration with a real GraphRAGPipeline
"""

import pytest

from core.memory.knowledge_entry import KnowledgeEntry
from core.memory.unified_memory import UnifiedMemory
from core.memory.backends.sqlite_graph import SQLiteGraphBackend

from core.memory.retrieval.graphrag.evidence import Evidence, EvidenceSet
from core.memory.retrieval.graphrag.pipeline import GraphRAGPipeline

from core.memory.retrieval.context.builder import RetrievalContextBuilder
from core.memory.retrieval.context.duplicates import MinHashDuplicateDetector
from core.memory.retrieval.context.token_counter import HeuristicTokenCounter


def _entry(**overrides) -> KnowledgeEntry:
    defaults = dict(content="Default content for context builder tests", truth_status="verified")
    defaults.update(overrides)
    return KnowledgeEntry(**defaults)


def _evidence(**entry_overrides) -> Evidence:
    score = entry_overrides.pop("score", 0.5)
    method = entry_overrides.pop("retrieval_method", "vector")
    return Evidence(entry=_entry(**entry_overrides), score=score, retrieval_method=method)


# ═══════════════════════════════════════════════════════════════════════════
# HeuristicTokenCounter
# ═══════════════════════════════════════════════════════════════════════════

class TestHeuristicTokenCounter:

    def test_empty_string(self):
        assert HeuristicTokenCounter().count("") == 0

    def test_proportional_to_length(self):
        counter = HeuristicTokenCounter(chars_per_token=4.0)
        assert counter.count("a" * 40) == 10

    def test_minimum_one_token_for_nonempty(self):
        assert HeuristicTokenCounter().count("a") >= 1


# ═══════════════════════════════════════════════════════════════════════════
# MinHashDuplicateDetector
# ═══════════════════════════════════════════════════════════════════════════

class TestMinHashDuplicateDetector:

    def test_empty_list(self):
        assert MinHashDuplicateDetector().group([]) == {}

    def test_identical_content_groups_together(self):
        e1 = _evidence(entry_id="a", content="OCBrain is a cognitive operating system built for local-first governance")
        e2 = _evidence(entry_id="b", content="OCBrain is a cognitive operating system built for local-first governance")
        result = MinHashDuplicateDetector().group([e1, e2])
        assert result["a"] == result["b"]

    def test_distinct_content_does_not_group(self):
        e1 = _evidence(entry_id="a", content="OCBrain uses SQLite for episodic memory storage")
        e2 = _evidence(entry_id="b", content="Completely unrelated topic about weather patterns in autumn")
        result = MinHashDuplicateDetector().group([e1, e2])
        assert result["a"] != result["b"]

    def test_first_seen_becomes_the_group_key(self):
        e1 = _evidence(entry_id="first", content="identical text for grouping test purposes here")
        e2 = _evidence(entry_id="second", content="identical text for grouping test purposes here")
        result = MinHashDuplicateDetector().group([e1, e2])
        assert result["first"] == "first"
        assert result["second"] == "first"


# ═══════════════════════════════════════════════════════════════════════════
# RetrievalContextBuilder
# ═══════════════════════════════════════════════════════════════════════════

class TestRetrievalContextBuilderBasics:

    def test_empty_evidence_set(self):
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q"))
        assert len(ctx) == 0
        assert ctx.truncated is False
        assert ctx.total_tokens == 0

    def test_no_duplicates_one_block_per_item_order_preserved(self):
        items = [
            _evidence(entry_id="a", content="first distinct memory about topic alpha", score=0.9),
            _evidence(entry_id="b", content="second distinct memory about topic beta", score=0.7),
            _evidence(entry_id="c", content="third distinct memory about topic gamma", score=0.5),
        ]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert len(ctx) == 3
        assert [b.primary_entry_id for b in ctx.blocks] == ["a", "b", "c"]

    def test_graph_available_carried_through(self):
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", graph_available=True))
        assert ctx.graph_available is True


class TestConsolidation:

    def test_duplicate_content_merges_into_one_block(self):
        items = [
            _evidence(entry_id="a", content="OCBrain persists memory using SQLite backends locally", score=0.9),
            _evidence(entry_id="b", content="OCBrain persists memory using SQLite backends locally", score=0.7),
        ]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert len(ctx) == 1
        assert ctx.blocks[0].primary_entry_id == "a"   # higher-ranked (first) survives
        assert ctx.blocks[0].merged_entry_ids == ["b"]

    def test_dropped_reporting_includes_merged_members(self):
        items = [
            _evidence(entry_id="a", content="x" * 40, score=0.9),
            _evidence(entry_id="b", content="x" * 40, score=0.7),   # duplicate of a
        ]
        ctx = RetrievalContextBuilder(default_token_budget=1).build(EvidenceSet(query="q", items=items))
        assert set(ctx.dropped_entry_ids) == {"a", "b"}


class TestContradictionGrouping:

    def test_pairwise_contradiction_grouped(self):
        items = [
            _evidence(entry_id="a", content="claim one", contradicts=["b"], score=0.9),
            _evidence(entry_id="b", content="claim two", score=0.8),
        ]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert len(ctx.contradiction_groups) == 1
        assert set(ctx.contradiction_groups[0].entry_ids) == {"a", "b"}
        block_a = next(b for b in ctx.blocks if b.primary_entry_id == "a")
        block_b = next(b for b in ctx.blocks if b.primary_entry_id == "b")
        assert block_a.contradiction_group_id == block_b.contradiction_group_id is not None

    def test_transitive_contradiction_group_of_three(self):
        items = [
            _evidence(entry_id="a", content="claim one", contradicts=["b"], score=0.9),
            _evidence(entry_id="b", content="claim two", contradicts=["c"], score=0.8),
            _evidence(entry_id="c", content="claim three", score=0.7),
        ]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert len(ctx.contradiction_groups) == 1
        assert set(ctx.contradiction_groups[0].entry_ids) == {"a", "b", "c"}

    def test_contradiction_reference_outside_evidence_set_is_not_an_error(self):
        items = [_evidence(entry_id="a", content="claim one", contradicts=["nonexistent-entry"], score=0.9)]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))   # must not raise
        assert ctx.contradiction_groups == []
        assert ctx.blocks[0].contradiction_group_id is None

    def test_no_contradiction_between_unrelated_evidence(self):
        items = [
            _evidence(entry_id="a", content="claim one", score=0.9),
            _evidence(entry_id="b", content="claim two", score=0.8),
        ]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert ctx.contradiction_groups == []

    def test_contradictions_are_never_resolved_both_blocks_survive(self):
        """Explicit regression guard for 'group only, never resolve.'"""
        items = [
            _evidence(entry_id="a", content="claim one", contradicts=["b"], score=0.9),
            _evidence(entry_id="b", content="claim two", contradicts=["a"], score=0.8),
        ]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert len(ctx) == 2   # neither dropped, neither merged, both present

    def test_group_id_deterministic_regardless_of_order(self):
        items_a = [
            _evidence(entry_id="x", content="claim one", contradicts=["y"], score=0.9),
            _evidence(entry_id="y", content="claim two", score=0.8),
        ]
        items_b = list(reversed(items_a))
        ctx1 = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items_a))
        ctx2 = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items_b))
        assert ctx1.contradiction_groups[0].group_id == ctx2.contradiction_groups[0].group_id

    def test_supports_carried_through_without_grouping(self):
        items = [
            _evidence(entry_id="a", content="claim one", supports=["b"], score=0.9),
            _evidence(entry_id="b", content="claim two", score=0.8),
        ]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert ctx.contradiction_groups == []   # supports never creates a contradiction group
        block_a = next(b for b in ctx.blocks if b.primary_entry_id == "a")
        assert block_a.supports == ["b"]


class TestTokenBudget:

    def test_no_budget_nothing_dropped(self):
        items = [_evidence(entry_id=f"e{i}", content=f"distinct memory content number {i} " * 30,
                            score=1.0 - i * 0.1) for i in range(5)]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert ctx.truncated is False
        assert len(ctx) == 5

    def test_partial_truncation_keeps_highest_ranked(self):
        items = [
            _evidence(entry_id="high", content="a" * 40, score=0.9),
            _evidence(entry_id="low", content="b" * 40, score=0.1),
        ]
        # budget fits exactly one block's ~10 tokens
        ctx = RetrievalContextBuilder(default_token_budget=10).build(EvidenceSet(query="q", items=items))
        assert ctx.truncated is True
        assert [b.primary_entry_id for b in ctx.blocks] == ["high"]
        assert "low" in ctx.dropped_entry_ids

    def test_total_tokens_matches_included_blocks_only(self):
        items = [_evidence(entry_id="a", content="x" * 40, score=0.9)]
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=items))
        assert ctx.total_tokens == ctx.blocks[0].token_count


class TestProvenancePreservation:

    def test_all_provenance_fields_present(self):
        entry = _entry(entry_id="a", source="test_source", worker_id="w1", workflow_id="wf1",
                        confidence=0.8, trust_score=0.9)
        ev = Evidence(entry=entry, score=0.5, retrieval_method="graph", graph_distance=2,
                       seed_entry_id="seed-1")
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=[ev]))
        prov = ctx.blocks[0].provenance
        assert prov.source == "test_source"
        assert prov.worker_id == "w1"
        assert prov.workflow_id == "wf1"
        assert prov.confidence == 0.8
        assert prov.trust_score == 0.9
        assert prov.retrieval_method == "graph"
        assert prov.graph_distance == 2
        assert prov.seed_entry_id == "seed-1"
        assert prov.verification_history is None   # reserved, not fabricated

    def test_context_block_never_exposes_raw_knowledge_entry(self):
        ctx = RetrievalContextBuilder().build(EvidenceSet(query="q", items=[_evidence(entry_id="a")]))
        block = ctx.blocks[0]
        assert not hasattr(block, "entry")
        assert not any(isinstance(v, KnowledgeEntry) for v in vars(block).values())


class TestDeterminism:

    def test_identical_input_produces_identical_output(self):
        items = [
            _evidence(entry_id="a", content="claim one", contradicts=["b"], score=0.9),
            _evidence(entry_id="b", content="claim two", score=0.8),
        ]
        builder = RetrievalContextBuilder()
        ctx1 = builder.build(EvidenceSet(query="q", items=list(items)))
        ctx2 = builder.build(EvidenceSet(query="q", items=list(items)))
        assert [b.primary_entry_id for b in ctx1.blocks] == [b.primary_entry_id for b in ctx2.blocks]
        assert ctx1.contradiction_groups[0].group_id == ctx2.contradiction_groups[0].group_id


class TestDecoupling:

    def test_context_builder_module_does_not_import_graphrag_pipeline(self):
        """Architectural invariant guard: RetrievalContextBuilder must not
        depend on GraphRAG internals beyond the Evidence/EvidenceSet types."""
        import ast
        from pathlib import Path
        builder_path = Path(__file__).parent.parent / "core" / "memory" / "retrieval" / "context" / "builder.py"
        tree = ast.parse(builder_path.read_text())
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert "core.memory.retrieval.graphrag.pipeline" not in imported_modules


class TestEndToEndIntegration:

    @pytest.mark.asyncio
    async def test_full_pipeline_to_context(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m1"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m1_graph.db"))
        memory.register_graph_backend(graph_backend)
        await memory.write(content="OCBrain context builder end to end integration test",
                            content_type="interaction", truth_status="verified")

        pipeline = GraphRAGPipeline(memory, graph=graph_backend)
        evidence = await pipeline.retrieve("context builder integration test")

        builder = RetrievalContextBuilder()
        context = builder.build(evidence)

        assert isinstance(context, __import__(
            "core.memory.retrieval.context.context", fromlist=["Context"]).Context)
        assert len(context) >= 1
        assert context.graph_available == evidence.graph_available
