"""
core/memory/retrieval/graphrag/pipeline.py — Session 5.5 GraphRAG Foundation.

GraphRAGPipeline implements the research-guided pipeline shape:

    Query -> Intent Analysis -> Memory Retrieval -> Graph Expansion
          -> Ranking -> Evidence Consolidation -> Context Assembly

as one orchestrating class over already-existing, already-tested
components -- it does not reimplement retrieval (delegates entirely to
UnifiedMemory.search(), mirroring RetrievalFusionEngine's own principle),
traversal (delegates to a pluggable TraversalStrategy), or ranking
(delegates to a pluggable RankingStrategy).

GraphRAG returns evidence. It NEVER invokes a reasoning model (research
guidance #3) -- retrieve() returns an EvidenceSet; what a caller does with
it (feed to a worker, render into a prompt) is entirely outside this
module's concern.

Graceful degradation (research guidance #7) is the pipeline's central
invariant, not an edge case: every failure mode below (no graph backend
registered, no graph-eligible seeds this query, traversal raising, a stale
graph_node_id pointing at a deleted entry) falls through to "return
whatever vector-only evidence UnifiedMemory.search() found," never to an
exception.

Known limitation (see Session 5.5 Architecture Decision / Technical Debt):
GraphBackend.get_neighbors() is outgoing-edges-only, and GraphIndexer's
edges are memory-node -> entity-node (one direction). This means depth-2+
traversal through an entity node currently finds nothing (entity nodes
have no outgoing edges), so "other memories sharing an entity" retrieval
isn't reachable yet even though the pipeline is structurally ready for it
the moment GraphBackend gains a bidirectional/incoming-edges primitive.
Nodes are still resolved and, when they correspond to a KnowledgeEntry
(the "mem:" prefix), become Evidence; non-entry nodes (e.g. "entity:...")
are traversal waypoints only, not evidence, in this session.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from core.memory.retrieval.graphrag.evidence import Evidence, EvidenceSet
from core.memory.retrieval.graphrag.intent import IntentAnalyzer, PassthroughIntentAnalyzer
from core.memory.retrieval.graphrag.ranking import RankingStrategy, WeightedRankingStrategy
from core.memory.retrieval.graphrag.traversal import BFSTraversalStrategy, TraversalStrategy

if TYPE_CHECKING:
    from core.memory.backends.base import GraphBackend
    from core.memory.unified_memory import UnifiedMemory

logger = logging.getLogger("ocbrain.memory.graphrag.pipeline")

_MEM_NODE_PREFIX = "mem:"   # must match GraphIndexer.node_id_for()'s convention


class GraphRAGPipeline:
    """Independent retrieval subsystem, not "graph search".

    Constructor injection only (mirrors RetrievalFusionEngine and
    GraphIndexer): every dependency is passed in, nothing is fetched from
    a module-level singleton. `graph` is Optional and typically None
    unless the caller has one registered with UnifiedMemory -- passing
    None is exactly how graceful degradation to vector-only retrieval is
    exercised, not a special case.
    """

    def __init__(self,
                 memory: "UnifiedMemory",
                 *,
                 graph: Optional["GraphBackend"] = None,
                 intent_analyzer: Optional[IntentAnalyzer] = None,
                 traversal: Optional[TraversalStrategy] = None,
                 ranking: Optional[RankingStrategy] = None,
                 vector_limit: int = 10,
                 traversal_max_depth: int = 2,
                 traversal_max_nodes: int = 25) -> None:
        self._memory = memory
        self._graph = graph
        self._intent = intent_analyzer or PassthroughIntentAnalyzer()
        self._traversal = traversal or BFSTraversalStrategy()
        self._ranking = ranking or WeightedRankingStrategy()
        self.vector_limit = vector_limit
        self.traversal_max_depth = traversal_max_depth
        self.traversal_max_nodes = traversal_max_nodes

    async def retrieve(self,
                        query: str,
                        *,
                        limit: int = 10,
                        query_embedding: Optional[List[float]] = None) -> EvidenceSet:
        """Run the full pipeline. Never raises due to graph unavailability
        or emptiness -- see module docstring."""

        # ── Stage 1: Intent Analysis ────────────────────────────────────
        intent = await self._intent.analyze(query)

        # ── Stage 2: Memory Retrieval (vector/lexical/metadata) ─────────
        # Delegates entirely to UnifiedMemory.search() (BM25+vector+RRF+
        # composite scoring, PI §8.3/§8.4) -- no duplicate retrieval logic.
        search_results = await self._memory.search(
            query=intent.search_query,
            limit=self.vector_limit,
            query_embedding=query_embedding,
        )

        evidence_by_id: Dict[str, Evidence] = {
            sr.entry.entry_id: Evidence(
                entry=sr.entry,
                score=sr.composite_score,
                retrieval_method="vector",
            )
            for sr in search_results
        }

        # ── Stage 3: Graph Expansion (graceful degradation is the default
        #     path here, not an exception path) ─────────────────────────
        graph_available = self._graph is not None
        if self._graph is not None:
            node_to_seed_entry_id = {
                sr.entry.graph_node_id: sr.entry.entry_id
                for sr in search_results if sr.entry.graph_node_id
            }
            seed_node_ids = list(node_to_seed_entry_id.keys())

            if seed_node_ids:
                try:
                    expansions = await self._traversal.expand(
                        seed_node_ids, self._graph,
                        max_depth=self.traversal_max_depth,
                        max_nodes=self.traversal_max_nodes,
                    )
                except Exception as e:
                    logger.warning(
                        "GraphRAGPipeline: traversal failed, falling back "
                        "to vector-only evidence (non-blocking): %s", e)
                    graph_available = False
                    expansions = []

                for exp in expansions:
                    if not exp.node_id.startswith(_MEM_NODE_PREFIX):
                        # Entity (or other non-entry) node: a traversal
                        # waypoint, not itself retrievable evidence in this
                        # session -- see module docstring's known
                        # limitation on edge directionality.
                        continue
                    target_entry_id = exp.node_id[len(_MEM_NODE_PREFIX):]
                    edge_weight = (exp.node or {}).get("weight", 1.0)

                    if target_entry_id in evidence_by_id:
                        # Consolidation: already found via vector search --
                        # enrich with graph provenance, never duplicate.
                        existing = evidence_by_id[target_entry_id]
                        if existing.graph_distance is None or exp.distance < existing.graph_distance:
                            existing.graph_distance = exp.distance
                            existing.path = exp.path
                            existing.seed_entry_id = node_to_seed_entry_id.get(exp.seed_node_id)
                            existing.score_breakdown["edge_confidence"] = edge_weight
                        continue

                    try:
                        target_entry = await self._memory.read(target_entry_id)
                    except Exception as e:
                        logger.warning(
                            "GraphRAGPipeline: reading expanded entry %s "
                            "failed (non-blocking, skipping): %s",
                            target_entry_id[:8], e)
                        continue
                    if target_entry is None:
                        # Stale graph node pointing at a deleted entry --
                        # skip, don't fail the whole retrieval over it.
                        continue

                    evidence_by_id[target_entry_id] = Evidence(
                        entry=target_entry,
                        retrieval_method="graph",
                        graph_distance=exp.distance,
                        path=exp.path,
                        seed_entry_id=node_to_seed_entry_id.get(exp.seed_node_id),
                        score_breakdown={"edge_confidence": edge_weight},
                    )
            # else: graph registered, but nothing this query was
            # graph-eligible to expand from -- graph_available stays True
            # (the subsystem was consulted and functioned; it simply had
            # no eligible seeds, which is a population/eligibility fact,
            # not a graph failure).

        # ── Stage 4: Ranking ─────────────────────────────────────────────
        ranked = self._ranking.rank(list(evidence_by_id.values()))

        # ── Stage 5: Evidence Consolidation ──────────────────────────────
        # Already folded into Stage 3 above (merge-on-target_entry_id) --
        # kept as an explicit, separately-named stage in this docstring/
        # pipeline shape per the research guidance, even though the
        # dedup work itself happens during expansion for efficiency
        # (no second pass needed over what's already a dict keyed by
        # entry_id).

        # ── Stage 6: Context Assembly ────────────────────────────────────
        # Deliberately NOT done here as a string -- EvidenceSet.
        # as_context_blocks() is the assembly primitive; this method
        # returns the EvidenceSet itself so a caller controls final
        # formatting and decides whether/how to hand it to a reasoning
        # model (GraphRAG never does that itself).
        return EvidenceSet(query=query, items=ranked[:limit], graph_available=graph_available)
