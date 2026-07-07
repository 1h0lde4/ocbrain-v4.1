"""
core/memory/retrieval/graphrag/traversal.py — Session 5.5 GraphRAG Foundation.

TraversalStrategy is a pluggable interface over GraphBackend.get_neighbors().
BFS is the only implementation today; the interface exists so DFS,
weighted/beam search, MCTS-guided, or a future semantic-edge-weighted
strategy are drop-in replacements with no change to the pipeline that calls
them (research guidance #4: "Traversal Must Be Pluggable").

Implementations must be pure consumers of GraphBackend's existing ABC
(get_neighbors) -- no new GraphBackend methods, no direct SQLite access.
GraphBackend itself stays storage/traversal-primitive-only; the traversal
*strategy* lives here, one layer up, per the same ownership split
Session 5.25 established for GraphIndexer.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Set

if TYPE_CHECKING:
    from core.memory.backends.base import GraphBackend

logger = logging.getLogger("ocbrain.memory.graphrag.traversal")


@dataclass
class TraversalHop:
    relation: str
    node_id: str


@dataclass
class TraversalResult:
    node_id: str
    distance: int
    path: List[TraversalHop] = field(default_factory=list)
    node: Dict[str, Any] = field(default_factory=dict)   # raw neighbor payload (target_type, weight, ...)
    seed_node_id: str = ""


class TraversalStrategy(ABC):
    """Expands outward from a set of seed graph node_ids."""

    @abstractmethod
    async def expand(self,
                      seed_node_ids: List[str],
                      graph: "GraphBackend",
                      max_depth: int = 2,
                      max_nodes: int = 25) -> List[TraversalResult]: ...


class BFSTraversalStrategy(TraversalStrategy):
    """Breadth-first expansion.

    Deterministic by construction (research guidance favors deterministic
    ranking/traversal): explores strictly in distance order, never
    revisits a node (a visited-set guards this even though GraphEngine's
    own multigraph could otherwise yield repeat edges), and stops at
    max_depth or max_nodes, whichever comes first.

    Failure isolation: a get_neighbors() failure on one frontier node is
    logged and skipped, not raised -- one bad node must not abort
    expansion for the rest of the frontier (consistent with GraphIndexer's
    non-blocking guarantees from Session 5.25).
    """

    async def expand(self,
                      seed_node_ids: List[str],
                      graph: "GraphBackend",
                      max_depth: int = 2,
                      max_nodes: int = 25) -> List[TraversalResult]:
        if not seed_node_ids or max_depth <= 0 or max_nodes <= 0:
            return []

        # `all_seed_ids` vs `visited` are deliberately separate: a node
        # being an original seed does NOT mean it can't be legitimately
        # *discovered* again via another seed's edge (e.g. two entries
        # returned by vector search that also happen to be directly
        # connected in the graph -- exactly the case GraphRAGPipeline's
        # consolidation step needs a TraversalResult for). What a seed
        # does NOT do is re-enter the frontier when discovered this way:
        # its own depth-0 frontier entry already covers its expansion
        # independently, so re-expanding from it a second time would only
        # duplicate work and risk two seeds bouncing off each other
        # indefinitely in a cyclic graph.
        all_seed_ids: Set[str] = set(seed_node_ids)
        visited: Set[str] = set()
        frontier: List[TraversalResult] = [
            TraversalResult(node_id=s, distance=0, path=[], seed_node_id=s)
            for s in seed_node_ids
        ]
        results: List[TraversalResult] = []
        depth = 0

        while frontier and depth < max_depth and len(results) < max_nodes:
            depth += 1
            next_frontier: List[TraversalResult] = []
            for current in frontier:
                if len(results) >= max_nodes:
                    break
                try:
                    neighbors = await graph.get_neighbors(current.node_id, limit=max_nodes)
                except Exception as e:
                    logger.warning(
                        "BFSTraversalStrategy: get_neighbors failed for %s "
                        "(non-blocking, treating as no neighbors): %s",
                        current.node_id, e)
                    continue
                for n in neighbors:
                    target_id = n.get("target_id")
                    if not target_id or target_id in visited:
                        continue
                    if target_id == current.seed_node_id:
                        # Cycled back to this branch's OWN originating seed
                        # -- not new information (trivially "reachable" from
                        # itself at distance 0); skip rather than report a
                        # spurious self-rediscovery. A DIFFERENT seed being
                        # reached here is NOT skipped -- see all_seed_ids
                        # check below, that's the genuinely useful case.
                        continue
                    visited.add(target_id)
                    hop = TraversalHop(relation=n.get("relation", ""), node_id=target_id)
                    result = TraversalResult(
                        node_id=target_id, distance=depth,
                        path=current.path + [hop],
                        node=n, seed_node_id=current.seed_node_id,
                    )
                    results.append(result)
                    if target_id not in all_seed_ids:
                        next_frontier.append(result)
                    if len(results) >= max_nodes:
                        break
            frontier = next_frontier

        return results[:max_nodes]
