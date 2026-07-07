"""
core/memory/retrieval/context/builder.py — Session 5.6 Retrieval Context
Builder.

RetrievalContextBuilder transforms an EvidenceSet (Session 5.5) into a
Context. Deliberately independent of GraphRAGPipeline (see Session 5.6
Architecture Decision: GraphRAGPipeline must not depend on this, and this
must not depend on GraphRAG internals) -- a caller composes:

    evidence = await graph_rag.retrieve(query)
    context  = context_builder.build(evidence)

Algorithm (all O(n), documented per-stage in the Session 5.6 Performance
Report -- nothing here is quadratic):
  1. Consolidation: MinHash/LSH duplicate grouping (DuplicateDetector),
     first-seen-wins since Evidence arrives pre-ranked -- O(n).
  2. Contradiction grouping: union-find over blocks' contradicts[]/
     supports[] relations -- O(n * small-constant) with path compression.
     Groups only; never resolves (no contradiction is ever dropped,
     merged, or judged).
  3. Token budgeting: single greedy pass over the already-deterministic
     rank order -- O(n), no re-sort.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from core.memory.retrieval.context.context import (
    Context, ContextBlock, ContradictionGroup, ProvenanceRecord,
)
from core.memory.retrieval.context.duplicates import DuplicateDetector, MinHashDuplicateDetector
from core.memory.retrieval.context.token_counter import HeuristicTokenCounter, TokenCounter

if TYPE_CHECKING:
    from core.memory.retrieval.graphrag.evidence import Evidence, EvidenceSet

logger = logging.getLogger("ocbrain.memory.context.builder")


class RetrievalContextBuilder:
    """Organizes Evidence into Context. Performs no reasoning: never
    resolves a contradiction, never summarizes, never generates an answer.

    Constructor injection only (same convention as GraphRAGPipeline,
    GraphIndexer, RetrievalFusionEngine): every dependency passed in,
    nothing fetched from a module-level singleton.
    """

    def __init__(self,
                 *,
                 duplicate_detector: Optional[DuplicateDetector] = None,
                 token_counter: Optional[TokenCounter] = None,
                 default_token_budget: Optional[int] = None) -> None:
        self._duplicates = duplicate_detector or MinHashDuplicateDetector()
        self._tokens = token_counter or HeuristicTokenCounter()
        self.default_token_budget = default_token_budget

    def build(self,
              evidence_set: "EvidenceSet",
              *,
              token_budget: Optional[int] = None) -> Context:
        budget = token_budget if token_budget is not None else self.default_token_budget

        if not evidence_set.items:
            return Context(query=evidence_set.query, graph_available=evidence_set.graph_available)

        # ── Stage 1: Consolidation (dedup) — O(n) ───────────────────────
        group_key_for = self._duplicates.group(evidence_set.items)
        blocks_by_key: Dict[str, ContextBlock] = {}
        block_order: List[str] = []   # preserves input (rank) order of first appearance

        for evidence_item in evidence_set.items:   # already rank-ordered by RankingStrategy
            key = group_key_for.get(evidence_item.entry_id, evidence_item.entry_id)
            if key in blocks_by_key:
                # Duplicate of an already-seen (higher- or equal-ranked)
                # block — fold in, never create a second block for it.
                blocks_by_key[key].merged_entry_ids.append(evidence_item.entry_id)
                continue
            block = self._to_block(evidence_item)
            blocks_by_key[key] = block
            block_order.append(key)

        blocks: List[ContextBlock] = [blocks_by_key[k] for k in block_order]

        # ── Stage 2: Contradiction grouping (organize only) — O(n) ──────
        contradiction_groups = self._group_contradictions(blocks)

        # ── Stage 3: Token budgeting — O(n), single greedy pass ─────────
        total_tokens = 0
        dropped_entry_ids: List[str] = []
        included_blocks: List[ContextBlock] = []
        for block in blocks:
            block.token_count = self._tokens.count(block.content)
            if budget is not None and total_tokens + block.token_count > budget:
                dropped_entry_ids.extend(block.all_entry_ids)
                continue
            total_tokens += block.token_count
            included_blocks.append(block)

        return Context(
            query=evidence_set.query,
            blocks=included_blocks,
            contradiction_groups=contradiction_groups,
            total_tokens=total_tokens,
            token_budget=budget,
            truncated=len(dropped_entry_ids) > 0,
            dropped_entry_ids=dropped_entry_ids,
            graph_available=evidence_set.graph_available,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_block(evidence_item: "Evidence") -> ContextBlock:
        entry = evidence_item.entry
        provenance = ProvenanceRecord(
            source=entry.source,
            worker_id=entry.worker_id,
            workflow_id=entry.workflow_id,
            confidence=entry.confidence,
            trust_score=entry.trust_score,
            truth_status=entry.truth_status,
            retrieval_method=evidence_item.retrieval_method,
            graph_distance=evidence_item.graph_distance,
            graph_path=[{"relation": h.relation, "node_id": h.node_id} for h in evidence_item.path],
            seed_entry_id=evidence_item.seed_entry_id,
        )
        return ContextBlock(
            primary_entry_id=entry.entry_id,
            content=entry.content,
            score=evidence_item.score,
            importance=entry.importance,
            provenance=provenance,
            contradicts=list(entry.contradicts),
            supports=list(entry.supports),
        )

    @staticmethod
    def _group_contradictions(blocks: List[ContextBlock]) -> List[ContradictionGroup]:
        """Union-find over contradicts[] relations. Deterministic group_id
        (keyed by the lexicographically smallest member entry_id) so the
        same cluster always produces the same id regardless of processing
        order — required for replayability (PI LAW 2/LAW 4), and makes
        results directly assertable in tests.

        Only relations pointing at ANOTHER block actually present in this
        Context matter — a contradicts[] id for an entry that wasn't
        retrieved this query is simply not actionable here and is not an
        error; nothing is fabricated for it.
        """
        if len(blocks) < 2:
            return []

        entry_id_to_block_id: Dict[str, str] = {}
        for b in blocks:
            entry_id_to_block_id[b.primary_entry_id] = b.primary_entry_id
            for merged_id in b.merged_entry_ids:
                entry_id_to_block_id[merged_id] = b.primary_entry_id

        parent: Dict[str, str] = {b.primary_entry_id: b.primary_entry_id for b in blocks}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                # Smaller id always wins as root -> deterministic regardless
                # of union order.
                if ra < rb:
                    parent[rb] = ra
                else:
                    parent[ra] = rb

        for block in blocks:
            for other_id in block.contradicts:
                target_block_id = entry_id_to_block_id.get(other_id)
                if target_block_id and target_block_id != block.primary_entry_id:
                    union(block.primary_entry_id, target_block_id)

        members_by_root: Dict[str, List[str]] = {}
        for b in blocks:
            root = find(b.primary_entry_id)
            members_by_root.setdefault(root, []).append(b.primary_entry_id)

        groups: List[ContradictionGroup] = []
        block_by_id = {b.primary_entry_id: b for b in blocks}
        for root, members in sorted(members_by_root.items()):
            if len(members) < 2:
                continue   # not actually grouped with anything present
            group_id = f"contradiction:{root}"
            for m in members:
                block_by_id[m].contradiction_group_id = group_id
            groups.append(ContradictionGroup(group_id=group_id, entry_ids=sorted(members)))

        return groups
