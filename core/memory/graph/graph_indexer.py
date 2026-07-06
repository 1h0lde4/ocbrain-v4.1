"""
core/memory/graph/graph_indexer.py — Session 5.25 Graph Index Foundation.

GraphIndexer is the ONLY thing that talks to GraphBackend. It owns:
  - eligibility        (via GraphEligibilityPolicy)
  - entity extraction   (via EntityExtractor)
  - synchronization     (create/update collapse into sync(); see below)
  - consistency         (dedup guard on repeated syncs; stale-node cleanup)
  - removal             (remove())

UnifiedMemory owns knowledge/lifecycle/retrieval and is the only thing that
persists graph_node_id back onto the canonical KnowledgeEntry (in L1
storage) — GraphIndexer computes the id and hands it back; it never writes
to L1 itself. This mirrors the frozen Session 5.25 architecture:

    UnifiedMemory.write()/update()/delete()
            |
            v
    Storage (L1, canonical)  --->  Vector Index (L2)
            |
            +----------------->  Graph Index (this module)
            |
            +----------------->  Archive (L4)

Failure isolation: every GraphBackend call in this module is wrapped in
try/except. A graph failure degrades to "no graph update happened" — it
never propagates to the caller. Knowledge persistence (L1) is always
authoritative; the graph is best-effort, by design (Session 5 established
this for write(); this module extends the same guarantee to update() and
delete()).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional

from core.memory.graph.eligibility import (
    EligibilityResult,
    GraphEligibilityPolicy,
    TruthStatusEligibilityPolicy,
)
from core.memory.graph.entity_extractor import EntityExtractor, NullEntityExtractor

if TYPE_CHECKING:
    from core.memory.backends.base import GraphBackend
    from core.memory.knowledge_entry import KnowledgeEntry

logger = logging.getLogger("ocbrain.memory.graph_indexer")


class GraphIndexer:
    """Derived-index synchronizer between UnifiedMemory and GraphBackend.

    Not a public UnifiedMemory API surface — instantiated and owned
    internally by UnifiedMemory.register_graph_backend(). Workers never
    touch this directly (mirrors the existing "no private backend access"
    rule for _storage/_vector/_archive/_graph — see
    tests/test_unified_memory.py::test_no_private_backend_in_public_api).
    """

    def __init__(self,
                 graph: "GraphBackend",
                 *,
                 eligibility_policy: Optional[GraphEligibilityPolicy] = None,
                 entity_extractor: Optional[EntityExtractor] = None) -> None:
        self._graph = graph
        self._policy = eligibility_policy or TruthStatusEligibilityPolicy()
        self._extractor = entity_extractor or NullEntityExtractor()

    # ── Node-id derivation (GraphIndexer-owned mapping) ────────────────────
    # KnowledgeEntry.graph_node_id stores whatever this class computes;
    # UnifiedMemory never derives a node_id itself. Convention preserved
    # from the pre-5.25 inline implementation (f"mem:{entry_id}") so
    # existing data / tests that assume this shape keep working.

    @staticmethod
    def node_id_for(entry_id: str) -> str:
        return f"mem:{entry_id}"

    @staticmethod
    def _entity_node_id(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
        return f"entity:{slug}" if slug else "entity:unnamed"

    # ── Synchronization ─────────────────────────────────────────────────────

    async def sync(self, entry: "KnowledgeEntry") -> Optional[str]:
        """Create-or-update entry's graph representation.

        Create and update are the same operation here because
        GraphBackend.add_node() is INSERT OR REPLACE at the storage layer
        (verified against GraphEngine._init_db / add_node) — calling it
        again with the same node_id safely overwrites properties without a
        separate update_node() method.

        Returns the node_id if the entry is (now) graph-indexed, else None.
        Never raises — every failure degrades to None (write behavior
        unaffected, matching Session 5's established graph-is-best-effort
        guarantee).
        """
        try:
            result: EligibilityResult = self._policy.evaluate(entry)
        except Exception as e:
            logger.warning(
                "GraphIndexer: eligibility policy raised, treating as "
                "ineligible (non-blocking): %s", e)
            result = EligibilityResult(False, f"policy error: {e}")

        if not result.eligible:
            # If this entry WAS graph-indexed before and has since become
            # ineligible (e.g. truth_status moved unknown->verified->
            # deprecated), clean up the stale node rather than leaving an
            # orphan the graph can no longer explain.
            if entry.graph_node_id:
                await self.remove(entry)
            return None

        node_id = self.node_id_for(entry.entry_id)
        try:
            await self._graph.add_node(
                node_id=node_id, node_type="memory_entry",
                name=entry.content[:80],
                properties={
                    "l2_entry_id": entry.entry_id,
                    "source": entry.source,
                    "importance": entry.importance,
                    "truth_status": entry.truth_status,
                },
            )
        except Exception as e:
            logger.warning("GraphIndexer: add_node failed (non-blocking): %s", e)
            return None

        try:
            entities = await self._extractor.extract(entry)
        except Exception as e:
            logger.warning(
                "GraphIndexer: entity extraction failed, indexing memory "
                "node only (non-blocking): %s", e)
            entities = []

        for entity in entities:
            try:
                await self._sync_entity_edge(node_id, entity)
            except Exception as e:
                logger.warning(
                    "GraphIndexer: entity sync failed for %r (non-blocking): %s",
                    entity.name, e)

        return node_id

    async def _sync_entity_edge(self, source_node_id: str, entity: Any) -> None:
        entity_node_id = self._entity_node_id(entity.name)
        await self._graph.add_node(
            node_id=entity_node_id, node_type=entity.entity_type,
            name=entity.name, properties=dict(entity.properties),
        )
        # Dedup guard: GraphEngine's edges table is an intentional multigraph
        # (duplicate (source,target,relation) triples are allowed by design —
        # "callers that want upsert semantics must implement that at a higher
        # layer", per graph_engine.py's own docstring). sync() can run many
        # times for the same entry (every update() call now triggers a
        # re-sync — see UnifiedMemory._sync_graph), so without this check a
        # long-lived entry would accumulate one duplicate edge per update.
        existing = await self._graph.get_neighbors(source_node_id, relation=entity.relation)
        if any(n.get("target_id") == entity_node_id for n in existing):
            return
        await self._graph.add_edge(source_node_id, entity_node_id, entity.relation)

    # ── Removal ──────────────────────────────────────────────────────────────

    async def remove(self, entry: "KnowledgeEntry") -> bool:
        """Remove entry's graph node. Incident edges are removed by
        GraphBackend.delete_node() itself (verified: GraphEngine's
        delete_node removes incident edges — see
        tests/test_unified_memory.py::test_graph_engine_delete_node_removes_incident_edges).

        Never raises. Returns True only if a node was actually deleted.
        """
        if not entry.graph_node_id:
            return False
        try:
            return await self._graph.delete_node(entry.graph_node_id)
        except Exception as e:
            logger.warning("GraphIndexer: delete_node failed (non-blocking): %s", e)
            return False

    # ── Recovery ─────────────────────────────────────────────────────────────

    async def rebuild(self, entries: Iterable["KnowledgeEntry"]) -> Dict[str, int]:
        """Re-derive the graph from canonical KnowledgeEntry records.

        Recovery contract (Session 5.25 "Recovery" objective): the graph
        holds nothing that isn't reproducible from L1 storage, because
        KnowledgeEntry is canonical and the graph is a derived index (the
        frozen architecture at the top of this file). Given any iterable of
        the system's current entries, this replays sync() over each one.

        Does NOT clear the backend's existing nodes/edges first —
        GraphBackend's ABC has no clear-all method by design (traversal/
        storage concerns only; wiping a whole graph is an operational
        action, not a per-call primitive). A caller that wants a
        byte-for-byte rebuild should delete the graph.db file (or truncate
        its tables) before calling rebuild() with a fresh GraphIndexer
        pointed at the recreated backend. See the Session 5.25 Technical
        Debt Report for why a dedicated "wipe" primitive is deferred.
        """
        counts = {"synced": 0, "skipped": 0, "failed": 0}
        for entry in entries:
            try:
                node_id = await self.sync(entry)
                counts["synced" if node_id else "skipped"] += 1
            except Exception as e:
                logger.warning(
                    "GraphIndexer: rebuild sync failed for %s (non-blocking): %s",
                    getattr(entry, "entry_id", "?")[:8], e)
                counts["failed"] += 1
        return counts
