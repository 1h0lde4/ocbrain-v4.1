"""
tests/test_graph_indexer.py — Session 5.25 Graph Index Foundation.

Covers:
  GraphEligibilityPolicy  — default delegates to is_graph_eligible(),
                            confidence floor, AllOf/AnyOf composition
  EntityExtractor         — Null (no-op), Regex (real extraction)
  GraphIndexer.sync()     — create, idempotent upsert, entity/edge sync +
                            dedup on re-sync, stale-node cleanup on
                            eligibility loss, failure isolation
  GraphIndexer.remove()   — delete, missing graph_node_id, backend failure
  GraphIndexer.rebuild()  — replays sync() over a batch, tallies counts,
                            isolates a failing sync call, rebuild safety
                            (idempotent across repeated calls)
  UnifiedMemory integration:
    - write() still creates a node when eligible (regression-preserving)
    - update() NOW creates/removes a node when truth_status crosses the
      eligibility boundary (the gap this session closes — update() never
      touched the graph at all before Session 5.25)
    - delete() still removes the node (regression-preserving)
    - custom eligibility_policy / entity_extractor are genuinely swappable
      at the register_graph_backend() call site
"""

import pytest

from core.memory.knowledge_entry import KnowledgeEntry
from core.memory.unified_memory import UnifiedMemory
from core.memory.backends.sqlite_graph import SQLiteGraphBackend
from core.memory.graph.eligibility import (
    GraphEligibilityPolicy, TruthStatusEligibilityPolicy, AllOf, AnyOf,
    EligibilityResult,
)
from core.memory.graph.entity_extractor import (
    EntityExtractor, NullEntityExtractor, RegexEntityExtractor, ExtractedEntity,
)
from core.memory.graph.graph_indexer import GraphIndexer


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def graph(tmp_path) -> SQLiteGraphBackend:
    return SQLiteGraphBackend(str(tmp_path / "graph.db"))


def _entry(**overrides) -> KnowledgeEntry:
    defaults = dict(content="Default test content", truth_status="verified")
    defaults.update(overrides)
    return KnowledgeEntry(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# GraphEligibilityPolicy
# ═══════════════════════════════════════════════════════════════════════════

class TestTruthStatusEligibilityPolicy:

    def test_default_matches_is_graph_eligible(self):
        policy = TruthStatusEligibilityPolicy()
        assert policy.evaluate(_entry(truth_status="verified")).eligible is True
        assert policy.evaluate(_entry(truth_status="unknown")).eligible is False

    def test_result_is_truthy_falsy(self):
        policy = TruthStatusEligibilityPolicy()
        assert bool(policy.evaluate(_entry(truth_status="candidate"))) is True
        assert bool(policy.evaluate(_entry(truth_status="conflicted"))) is False

    def test_confidence_floor_rejects_low_confidence(self):
        policy = TruthStatusEligibilityPolicy(min_confidence=0.8)
        low  = _entry(truth_status="verified", confidence=0.5)
        high = _entry(truth_status="verified", confidence=0.9)
        assert policy.evaluate(low).eligible is False
        assert policy.evaluate(high).eligible is True

    def test_default_confidence_floor_is_permissive(self):
        """min_confidence=0.0 default must be behaviorally identical to
        pre-5.25 (no confidence gating at all) -- additive, not a change."""
        policy = TruthStatusEligibilityPolicy()
        assert policy.evaluate(_entry(truth_status="verified", confidence=0.0)).eligible is True


class TestPolicyComposition:

    def test_allof_requires_every_subpolicy(self):
        permissive  = TruthStatusEligibilityPolicy(min_confidence=0.0)
        impossible  = TruthStatusEligibilityPolicy(min_confidence=1.1)
        combo = AllOf(permissive, impossible)
        assert combo.evaluate(_entry(truth_status="verified")).eligible is False

    def test_allof_all_pass(self):
        combo = AllOf(TruthStatusEligibilityPolicy(), TruthStatusEligibilityPolicy(min_confidence=0.1))
        assert combo.evaluate(_entry(truth_status="verified", confidence=1.0)).eligible is True

    def test_anyof_requires_one_subpolicy(self):
        impossible = TruthStatusEligibilityPolicy(min_confidence=1.1)
        combo = AnyOf(impossible, TruthStatusEligibilityPolicy())
        assert combo.evaluate(_entry(truth_status="verified")).eligible is True

    def test_anyof_none_pass(self):
        combo = AnyOf(TruthStatusEligibilityPolicy(min_confidence=1.1))
        assert combo.evaluate(_entry(truth_status="verified")).eligible is False


# ═══════════════════════════════════════════════════════════════════════════
# EntityExtractor
# ═══════════════════════════════════════════════════════════════════════════

class TestEntityExtractors:

    @pytest.mark.asyncio
    async def test_null_extractor_always_empty(self):
        result = await NullEntityExtractor().extract(_entry(content="Paris France Anything"))
        assert result == []

    @pytest.mark.asyncio
    async def test_regex_extractor_finds_capitalized_phrases(self):
        entry = _entry(content="Marie Curie discovered Radium in a lab.")
        result = await RegexEntityExtractor().extract(entry)
        assert "Marie Curie" in [e.name for e in result]

    @pytest.mark.asyncio
    async def test_regex_extractor_caps_at_max_entities(self):
        entry = _entry(content="Alpha Beta. Gamma Delta. Epsilon Zeta. Eta Theta.")
        result = await RegexEntityExtractor(max_entities=2).extract(entry)
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_regex_extractor_empty_content(self):
        assert await RegexEntityExtractor().extract(_entry(content="")) == []

    @pytest.mark.asyncio
    async def test_regex_extractor_dedups_case_insensitively(self):
        entry = _entry(content="Paris is great. Paris is beautiful.")
        result = await RegexEntityExtractor().extract(entry)
        names_lower = [e.name.lower() for e in result]
        assert names_lower.count("paris") == 1

    @pytest.mark.asyncio
    async def test_regex_extractor_returns_extracted_entity_dataclass(self):
        entry = _entry(content="Radium was studied extensively.")
        result = await RegexEntityExtractor().extract(entry)
        assert all(isinstance(e, ExtractedEntity) for e in result)
        assert all(e.relation == "mentions" for e in result)


# ═══════════════════════════════════════════════════════════════════════════
# GraphIndexer.sync()
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphIndexerSync:

    @pytest.mark.asyncio
    async def test_sync_creates_node_for_eligible_entry(self, graph):
        indexer = GraphIndexer(graph)
        entry = _entry(entry_id="e1", truth_status="verified")
        node_id = await indexer.sync(entry)
        assert node_id == "mem:e1"
        assert await graph.get_node(node_id) is not None

    @pytest.mark.asyncio
    async def test_sync_returns_none_for_ineligible_entry(self, graph):
        indexer = GraphIndexer(graph)
        entry = _entry(entry_id="e2", truth_status="unknown")
        assert await indexer.sync(entry) is None
        assert await graph.get_node("mem:e2") is None

    @pytest.mark.asyncio
    async def test_sync_is_idempotent_upsert(self, graph):
        indexer = GraphIndexer(graph)
        entry = _entry(entry_id="e3", truth_status="verified", importance=0.3)
        await indexer.sync(entry)
        entry.importance = 0.9
        node_id = await indexer.sync(entry)
        node = await graph.get_node(node_id)
        assert node["properties"]["importance"] == 0.9

    @pytest.mark.asyncio
    async def test_sync_cleans_up_stale_node_on_eligibility_loss(self, graph):
        indexer = GraphIndexer(graph)
        entry = _entry(entry_id="e4", truth_status="verified")
        node_id = await indexer.sync(entry)
        entry.graph_node_id = node_id
        entry.truth_status = "deprecated"
        result = await indexer.sync(entry)
        assert result is None
        assert await graph.get_node(node_id) is None

    @pytest.mark.asyncio
    async def test_sync_with_entity_extractor_creates_edges(self, graph):
        indexer = GraphIndexer(graph, entity_extractor=RegexEntityExtractor())
        entry = _entry(entry_id="e5", truth_status="verified",
                        content="Marie Curie discovered Radium.")
        node_id = await indexer.sync(entry)
        neighbors = await graph.get_neighbors(node_id)
        assert len(neighbors) >= 1
        assert all(n["relation"] == "mentions" for n in neighbors)

    @pytest.mark.asyncio
    async def test_sync_does_not_duplicate_edges_on_resync(self, graph):
        indexer = GraphIndexer(graph, entity_extractor=RegexEntityExtractor())
        entry = _entry(entry_id="e6", truth_status="verified",
                        content="Marie Curie discovered Radium.")
        node_id = await indexer.sync(entry)
        await indexer.sync(entry)
        await indexer.sync(entry)
        neighbors = await graph.get_neighbors(node_id, limit=50)
        marie_id = GraphIndexer._entity_node_id("Marie Curie")
        marie_edges = [n for n in neighbors if n["target_id"] == marie_id]
        assert len(marie_edges) == 1

    @pytest.mark.asyncio
    async def test_sync_default_extractor_produces_no_edges(self, graph):
        """NullEntityExtractor is the default -- confirms Session 5.25
        ships a safe-by-default pipe, not opt-out entity extraction."""
        indexer = GraphIndexer(graph)
        entry = _entry(entry_id="e6b", truth_status="verified",
                        content="Marie Curie discovered Radium.")
        node_id = await indexer.sync(entry)
        assert await graph.get_neighbors(node_id) == []

    @pytest.mark.asyncio
    async def test_sync_failure_isolation_add_node_raises(self):
        class _FailingGraph:
            async def add_node(self, *a, **kw): raise RuntimeError("boom")
            async def get_neighbors(self, *a, **kw): return []
            async def add_edge(self, *a, **kw): raise RuntimeError("boom")
            async def delete_node(self, *a, **kw): return False
        indexer = GraphIndexer(_FailingGraph())
        entry = _entry(entry_id="e7", truth_status="verified")
        assert await indexer.sync(entry) is None   # must not raise

    @pytest.mark.asyncio
    async def test_sync_failure_isolation_policy_raises(self, graph):
        class _BadPolicy(GraphEligibilityPolicy):
            def evaluate(self, entry):
                raise RuntimeError("policy exploded")
        indexer = GraphIndexer(graph, eligibility_policy=_BadPolicy())
        entry = _entry(entry_id="e8", truth_status="verified")
        assert await indexer.sync(entry) is None   # must not raise

    @pytest.mark.asyncio
    async def test_sync_failure_isolation_extractor_raises(self, graph):
        class _BadExtractor(EntityExtractor):
            async def extract(self, entry):
                raise RuntimeError("extractor exploded")
        indexer = GraphIndexer(graph, entity_extractor=_BadExtractor())
        entry = _entry(entry_id="e9", truth_status="verified")
        # Memory node must still be created even though extraction failed.
        node_id = await indexer.sync(entry)
        assert node_id == "mem:e9"
        assert await graph.get_node(node_id) is not None


# ═══════════════════════════════════════════════════════════════════════════
# GraphIndexer.remove()
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphIndexerRemove:

    @pytest.mark.asyncio
    async def test_remove_deletes_existing_node(self, graph):
        indexer = GraphIndexer(graph)
        entry = _entry(entry_id="r1", truth_status="verified")
        node_id = await indexer.sync(entry)
        entry.graph_node_id = node_id
        assert await indexer.remove(entry) is True
        assert await graph.get_node(node_id) is None

    @pytest.mark.asyncio
    async def test_remove_no_graph_node_id_returns_false(self, graph):
        indexer = GraphIndexer(graph)
        entry = _entry(entry_id="r2", truth_status="unknown")
        assert entry.graph_node_id is None
        assert await indexer.remove(entry) is False

    @pytest.mark.asyncio
    async def test_remove_failure_isolation(self):
        class _FailingGraph:
            async def delete_node(self, node_id):
                raise RuntimeError("boom")
        indexer = GraphIndexer(_FailingGraph())
        entry = _entry(entry_id="r3", truth_status="verified", graph_node_id="mem:r3")
        assert await indexer.remove(entry) is False   # must not raise


# ═══════════════════════════════════════════════════════════════════════════
# GraphIndexer.rebuild()
# ═══════════════════════════════════════════════════════════════════════════

class TestGraphIndexerRebuild:

    @pytest.mark.asyncio
    async def test_rebuild_syncs_all_eligible_entries(self, graph):
        indexer = GraphIndexer(graph)
        entries = [
            _entry(entry_id=f"b{i}",
                   truth_status="verified" if i % 2 == 0 else "unknown")
            for i in range(6)
        ]
        counts = await indexer.rebuild(entries)
        assert counts == {"synced": 3, "skipped": 3, "failed": 0}

    @pytest.mark.asyncio
    async def test_rebuild_isolates_a_failing_sync_call(self, graph):
        """Defensive-depth check on rebuild()'s own try/except, independent
        of sync()'s own (separately tested) failure isolation."""
        indexer = GraphIndexer(graph)
        entries = [_entry(entry_id="ok1", truth_status="verified"),
                   _entry(entry_id="bad1", truth_status="verified"),
                   _entry(entry_id="ok2", truth_status="verified")]

        real_sync = indexer.sync
        async def flaky_sync(entry):
            if entry.entry_id == "bad1":
                raise RuntimeError("simulated failure")
            return await real_sync(entry)
        indexer.sync = flaky_sync

        counts = await indexer.rebuild(entries)
        assert counts["synced"] == 2
        assert counts["failed"] == 1

    @pytest.mark.asyncio
    async def test_rebuild_is_safe_to_run_twice(self, graph):
        """Rebuild safety: running rebuild() again over the same entries
        must not duplicate nodes or edges (relies on sync()'s upsert +
        dedup guarantees, exercised here at the batch level)."""
        indexer = GraphIndexer(graph, entity_extractor=RegexEntityExtractor())
        entries = [_entry(entry_id="s1", truth_status="verified",
                           content="Marie Curie discovered Radium.")]
        await indexer.rebuild(entries)
        counts_second = await indexer.rebuild(entries)
        assert counts_second["synced"] == 1
        neighbors = await graph.get_neighbors("mem:s1", limit=50)
        assert len(neighbors) == len({n["target_id"] for n in neighbors})


# ═══════════════════════════════════════════════════════════════════════════
# UnifiedMemory integration
# ═══════════════════════════════════════════════════════════════════════════

class TestUnifiedMemoryGraphIntegration:

    @pytest.mark.asyncio
    async def test_write_creates_graph_node_when_eligible(self, tmp_path):
        from unittest.mock import patch
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m1"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m1_graph.db"))
        memory.register_graph_backend(graph_backend)
        with patch("core.memory.knowledge_entry.GRAPH_ELIGIBLE_STATUSES",
                   {"unknown", "verified", "candidate"}):
            eid = await memory.write(content="graph indexer integration write test",
                                      content_type="interaction")
        entry = await memory.read(eid)
        assert entry.graph_node_id is not None
        assert await graph_backend.get_node(entry.graph_node_id) is not None

    @pytest.mark.asyncio
    async def test_update_creates_graph_node_when_truth_status_becomes_eligible(self, tmp_path):
        """THE gap this session closes: update() previously never touched
        the graph at all, so a curator/verification workflow flipping
        truth_status unknown->verified via update() would never produce a
        graph node, even with a working graph backend and eligibility gate."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m2"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m2_graph.db"))
        memory.register_graph_backend(graph_backend)

        eid = await memory.write(content="starts unverified", content_type="interaction")
        entry = await memory.read(eid)
        assert entry.graph_node_id is None   # truth_status defaults to "unknown"

        await memory.update(eid, {"truth_status": "verified"})
        entry_after = await memory.read(eid)
        assert entry_after.graph_node_id is not None
        assert await graph_backend.get_node(entry_after.graph_node_id) is not None

    @pytest.mark.asyncio
    async def test_update_removes_graph_node_when_truth_status_becomes_ineligible(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m3"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m3_graph.db"))
        memory.register_graph_backend(graph_backend)

        eid = await memory.write(content="starts verified", content_type="interaction")
        await memory.update(eid, {"truth_status": "verified"})
        node_id = (await memory.read(eid)).graph_node_id
        assert node_id is not None

        await memory.update(eid, {"truth_status": "deprecated"})
        assert await graph_backend.get_node(node_id) is None
        assert (await memory.read(eid)).graph_node_id is None

    @pytest.mark.asyncio
    async def test_update_without_graph_backend_still_succeeds(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m4"))
        eid = await memory.write(content="no graph backend at all", content_type="interaction")
        assert await memory.update(eid, {"importance": 0.7}) is True

    @pytest.mark.asyncio
    async def test_delete_still_removes_graph_node(self, tmp_path):
        """Regression guard: delete()'s graph removal, now routed through
        GraphIndexer.remove() instead of an inline self._graph call, must
        behave identically to the pre-5.25 implementation."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m5"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m5_graph.db"))
        memory.register_graph_backend(graph_backend)

        eid = await memory.write(content="starts verified for delete test",
                                  content_type="interaction")
        await memory.update(eid, {"truth_status": "verified"})
        node_id = (await memory.read(eid)).graph_node_id
        assert node_id is not None

        await memory.delete(eid)
        assert await graph_backend.get_node(node_id) is None

    @pytest.mark.asyncio
    async def test_custom_eligibility_policy_via_register_graph_backend(self, tmp_path):
        """Proves the policy is genuinely swappable at the UnifiedMemory
        call site, not hardcoded -- Session 5.25's central objective."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m6"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m6_graph.db"))

        class _NeverEligible(GraphEligibilityPolicy):
            def evaluate(self, entry):
                return EligibilityResult(False, "test policy: never eligible")

        memory.register_graph_backend(graph_backend, eligibility_policy=_NeverEligible())

        eid = await memory.write(content="test", content_type="interaction")
        await memory.update(eid, {"truth_status": "verified"})   # would normally index
        assert (await memory.read(eid)).graph_node_id is None

    @pytest.mark.asyncio
    async def test_custom_entity_extractor_via_register_graph_backend(self, tmp_path):
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m7"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m7_graph.db"))
        memory.register_graph_backend(graph_backend, entity_extractor=RegexEntityExtractor())

        eid = await memory.write(content="Marie Curie discovered Radium.",
                                  content_type="interaction")
        await memory.update(eid, {"truth_status": "verified"})
        entry = await memory.read(eid)
        neighbors = await graph_backend.get_neighbors(entry.graph_node_id)
        assert len(neighbors) >= 1

    @pytest.mark.asyncio
    async def test_rebuild_from_canonical_storage_via_get_layer(self, tmp_path):
        """End-to-end recovery proof: given entries pulled from
        UnifiedMemory's own canonical storage (get_layer), GraphIndexer can
        regenerate the graph from scratch -- the Session 5.25 'Recovery'
        objective, exercised against the real integration, not just the
        unit-level rebuild() tests above."""
        memory = UnifiedMemory(db_prefix=str(tmp_path / "m8"))
        graph_backend = SQLiteGraphBackend(str(tmp_path / "m8_graph.db"))
        memory.register_graph_backend(graph_backend)

        eid1 = await memory.write(content="entry one", content_type="interaction")
        eid2 = await memory.write(content="entry two", content_type="interaction")
        await memory.update(eid1, {"truth_status": "verified"})
        await memory.update(eid2, {"truth_status": "verified"})

        # Simulate graph loss (e.g. corrupted graph.db) followed by recovery
        # against a fresh backend, using UnifiedMemory's own indexer.
        fresh_graph = SQLiteGraphBackend(str(tmp_path / "m8_graph_rebuilt.db"))
        rebuild_indexer = GraphIndexer(fresh_graph)
        all_entries = await memory.get_layer("l1")
        counts = await rebuild_indexer.rebuild(all_entries)
        assert counts["synced"] == 2
        assert await fresh_graph.get_node(f"mem:{eid1}") is not None
        assert await fresh_graph.get_node(f"mem:{eid2}") is not None
