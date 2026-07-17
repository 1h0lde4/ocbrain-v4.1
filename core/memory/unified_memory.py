"""
core/memory/unified_memory.py — UnifiedMemory (v4.3.4.9)

Single authoritative memory source. Assembles L0-L4 backends.
All memory operations go through this class — no parallel write paths.

Architecture (MEMORY_MIGRATION_DESIGN_V2.md §3):
  L0: WorkingMemory   — LRU in-process cache (<1ms, ephemeral)
  L1: EpisodicMemory  — SQLiteStorageBackend (primary CRUD, FTS5)
  L2: SemanticMemory  — InMemoryVectorBackend (BM25 + embeddings)
  L3: GraphMemory     — SQLiteGraphBackend (v4.3.5, wired later)
  L4: Archive         — SQLiteArchiveBackend (immutable audit log)

Curator hooks (§7, v4.3.6): before/after write/promote/archive/delete.
These are no-ops until MemoryCuratorWorker registers itself at startup.

Composite scoring (ADR-006, §8.4):
  score = α_recency * recency_decay + α_importance * importance + α_relevance * relevance
"""

import asyncio
import logging
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.governance.governance_kernel import GovernanceKernel

from core.memory.backends.base import (
    ArchiveBackend, GraphBackend, L0Cache, StorageBackend, VectorBackend,
)
from core.memory.backends.sqlite_storage import SQLiteStorageBackend
from core.memory.backends.memory_vector import InMemoryVectorBackend
from core.memory.backends.sqlite_archive import SQLiteArchiveBackend
from core.memory.graph.graph_indexer import GraphIndexer
from core.memory.graph.eligibility import GraphEligibilityPolicy
from core.memory.graph.entity_extractor import EntityExtractor
from core.memory.knowledge_entry import KnowledgeEntry, LAYERS
from core.memory.knowledge_event import (
    KnowledgeEvent,
    event_created, event_updated, event_promoted, event_deleted,
)

logger = logging.getLogger("ocbrain.memory.unified")


# ── L0 Working Memory (LRU) ───────────────────────────────────────────────────

class _LRUWorkingMemory(L0Cache):
    """
    In-process LRU cache. Never persisted.
    Entries are lost on restart — this is intentional (L0 is ephemeral context).
    """

    def __init__(self, maxsize: int = 500):
        self._cache:   OrderedDict = OrderedDict()
        self._maxsize: int         = maxsize
        self._hits:    int         = 0
        self._misses:  int         = 0

    def put(self, entry_id: str, entry: KnowledgeEntry) -> None:
        if entry_id in self._cache:
            self._cache.move_to_end(entry_id)
        self._cache[entry_id] = entry
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)   # evict LRU

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        if entry_id not in self._cache:
            self._misses += 1
            return None
        self._cache.move_to_end(entry_id)
        self._hits += 1
        return self._cache[entry_id]

    def evict(self, entry_id: str) -> None:
        self._cache.pop(entry_id, None)

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            "size":    len(self._cache),
            "maxsize": self._maxsize,
            "hits":    self._hits,
            "misses":  self._misses,
            "hit_rate": round(self._hits / max(1, self._hits + self._misses), 3),
        }


# ── Curator Hook Registry ─────────────────────────────────────────────────────

@dataclass
class HookRegistry:
    """
    Extension points for MemoryCuratorWorker (v4.3.6).
    All hooks are no-ops until CuratorWorker registers at startup.

    Hook signatures:
      before_write:  fn(entry) → Optional[KnowledgeEntry]  — None means reject write
      after_write:   fn(entry) → None                       — fire-and-forget observation
      before_delete: fn(entry) → Optional[KnowledgeEntry]  — None means block deletion
      after_delete:  fn(entry) → None                       — fire-and-forget observation
      before/after_promote and before/after_archive reserved for future phases.

    Hook lifecycle is owned entirely by HookRegistry.
    No external component should append to hook lists directly.
    """
    before_write:   List[Callable] = field(default_factory=list)
    after_write:    List[Callable] = field(default_factory=list)
    before_promote: List[Callable] = field(default_factory=list)
    after_promote:  List[Callable] = field(default_factory=list)
    before_archive: List[Callable] = field(default_factory=list)
    after_archive:  List[Callable] = field(default_factory=list)
    before_delete:  List[Callable] = field(default_factory=list)
    after_delete:   List[Callable] = field(default_factory=list)
    # Internal registration flag — not part of equality or repr
    _curator_registered: bool = field(default=False, repr=False, compare=False)

    def register_curator(self, curator: Any) -> None:
        """Wire all MemoryCuratorWorker hook functions into this registry.

        This is the single, centralised place where hook population happens.
        MemoryCuratorWorker.register() calls this method; the curator never
        appends to hook lists directly (dependency inversion).

        Registration order is deterministic:
          1. before_write  — quality gate (reject empty/short content)
          2. after_write   — observation (logging)
          3. before_delete — archival gate (block L4 deletion, log all others)

        Duplicate registration is blocked: a second call is a no-op with a warning.

        Args:
            curator: MemoryCuratorWorker instance that exposes the hook callables.
        """
        if self._curator_registered:
            logger.warning(
                "HookRegistry: duplicate curator registration blocked "
                "(curator is already registered)"
            )
            return

        self.before_write.append(curator._before_write_hook)
        self.after_write.append(curator._after_write_hook)
        self.before_delete.append(curator._before_delete_hook)

        # Use object.__setattr__ because dataclass fields are set in __init__,
        # but _curator_registered was initialised as False; we update it directly.
        object.__setattr__(self, "_curator_registered", True)

        logger.info(
            "HookRegistry: MemoryCuratorWorker hooks wired "
            "(before_write=%d, after_write=%d, before_delete=%d)",
            len(self.before_write), len(self.after_write), len(self.before_delete),
        )

    def unregister_curator(self) -> None:
        """Remove all curator hooks and reset the registration flag.

        Used in testing and future hot-reload scenarios.  The curator is the
        sole hook provider in the current architecture, so clearing the lists
        is safe and complete.
        """
        if not self._curator_registered:
            return
        self.before_write.clear()
        self.after_write.clear()
        self.before_delete.clear()
        object.__setattr__(self, "_curator_registered", False)
        logger.info("HookRegistry: MemoryCuratorWorker hooks removed")

    @property
    def curator_registered(self) -> bool:
        """True once register_curator() has successfully wired the curator."""
        return self._curator_registered


# ── Layer Router ──────────────────────────────────────────────────────────────

class LayerRouter:
    """
    Routes writes to the appropriate memory layer.
    Priority: explicit layer_hint > content_type rules > importance threshold > default.
    """

    CONTENT_TYPE_ROUTES: Dict[str, str] = {
        "session":    "l1",
        "event":      "l1",
        "observation":"l1",
        "interaction":"l1",
        "fact":       "l2",
        "concept":    "l2",
        "knowledge":  "l2",
        "web_knowledge":"l2",
        "entity":     "l2",   # graph-indexed independently via is_graph_eligible()
                              # when truth_status qualifies -- NOT a layer route
        "skill":      "l2",
        "procedure":  "l2",
        "audit":      "l4",
        "provenance": "l4",
        "quarantined":"l4",
    }

    def route(self, content: str, content_type: str = "",
               importance: float = 0.5, trust_score: float = 1.0,
               layer_hint: Optional[str] = None,
               procedure_name: Optional[str] = None) -> str:

        # 1. Explicit override wins
        if layer_hint and layer_hint in LAYERS:
            return layer_hint

        # 2. Quarantine anything untrustworthy
        if trust_score < 0.2:
            return "l4"

        # 3. Content-type routing
        if content_type in self.CONTENT_TYPE_ROUTES:
            return self.CONTENT_TYPE_ROUTES[content_type]

        # 4. Importance + length heuristics
        if importance < 0.2 and len(content) < 80:
            return "l0"   # ephemeral scratch
        if importance >= 0.8 and len(content) >= 100:
            return "l2"

        # 5. Default: episodic
        return "l1"


# ── Search Result ─────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    entry:           KnowledgeEntry
    composite_score: float
    bm25_score:      float = 0.0
    vector_score:    float = 0.0
    recency_score:   float = 0.0

    def __lt__(self, other: "SearchResult") -> bool:
        return self.composite_score < other.composite_score


# ── Unified Memory ────────────────────────────────────────────────────────────

class UnifiedMemory:
    """
    Single authoritative memory source for OCBrain.

    All reads and writes go through this class.
    No component should write to a backend directly.

    Usage:
        memory = UnifiedMemory()
        entry_id = await memory.write("Paris is the capital of France",
                                       content_type="fact", importance=0.8)
        results  = await memory.search("capital of France", limit=5)
        entry    = await memory.read(entry_id)
        stats    = memory.stats()
    """

    def __init__(self,
                 storage:  Optional[StorageBackend] = None,
                 vector:   Optional[VectorBackend]  = None,
                 graph:    Optional[GraphBackend]   = None,
                 archive:  Optional[ArchiveBackend] = None,
                 l0_maxsize: int = 500,
                 archive_all: bool = False,
                 db_prefix: str = ".data/memory",
                 governance: Optional["GovernanceKernel"] = None):
        self._l0      = _LRUWorkingMemory(maxsize=l0_maxsize)
        self._storage = storage  or SQLiteStorageBackend(f"{db_prefix}/unified.db")
        self._vector  = vector   or InMemoryVectorBackend()
        self._graph:         Optional[GraphBackend] = None   # set via register_graph_backend()
        self._graph_indexer: Optional[GraphIndexer] = None   # Session 5.25
        self._archive = archive  or SQLiteArchiveBackend(f"{db_prefix}/archive.db")
        self._router  = LayerRouter()
        self._hooks   = HookRegistry()
        self._archive_all = archive_all  # snapshot every entry on write
        self._governance: Optional["GovernanceKernel"] = governance  # K3.5: explicit injection

        self._write_count   = 0
        self._search_count  = 0
        logger.info("UnifiedMemory ready (L0=%d cap, archive_all=%s, governance=%s)",
                    l0_maxsize, archive_all, governance is not None)

        # Constructor-provided graph goes through the same registration path
        # as main.py's explicit register_graph_backend() call, so there is
        # exactly one place GraphIndexer gets built regardless of entry point.
        if graph is not None:
            self.register_graph_backend(graph)

    # ── Governance integration (K3.5) ──────────────────────────────────────

    def register_governance(self, governance: "GovernanceKernel") -> None:
        """Wire GovernanceKernel into this memory instance.

        K3.5 Kernel Hardening — Constitution Law 1 (Bounded Autonomy).
        Called from the composition root (main.py) after both singletons
        exist. Mirrors register_graph_backend() and register_curator().

        Explicit injection, not hidden singleton lookup — preserves
        constructor testability and avoids hidden global dependencies.

        Args:
            governance: GovernanceKernel instance from the composition root.
        """
        if self._governance is not None:
            logger.warning("UnifiedMemory: duplicate governance registration blocked")
            return
        self._governance = governance
        logger.info("UnifiedMemory: GovernanceKernel registered (memory writes governed)")

    # ── Curator integration ───────────────────────────────────────────────

    def register_curator(self, curator: Any) -> None:
        """Called by MemoryCuratorWorker (v4.3.6) at startup."""
        self._hooks.register_curator(curator)

    def register_graph_backend(self, graph: GraphBackend, *,
                                eligibility_policy: Optional[GraphEligibilityPolicy] = None,
                                entity_extractor: Optional[EntityExtractor] = None) -> None:
        """Wire in the graph backend (main.py Step 6; also test call sites).

        Session 5.25: also constructs the GraphIndexer that owns eligibility/
        extraction/sync/removal for this backend. eligibility_policy and
        entity_extractor are optional — omitting both preserves the exact
        pre-5.25 default behavior (TruthStatusEligibilityPolicy delegating to
        entry.is_graph_eligible(), NullEntityExtractor producing no entities)
        so every existing call site (`register_graph_backend(graph)`, one
        positional arg) keeps working unchanged.
        """
        self._graph = graph
        self._graph_indexer = GraphIndexer(
            graph, eligibility_policy=eligibility_policy, entity_extractor=entity_extractor)
        logger.info("UnifiedMemory: GraphBackend registered (L3 active)")

    @property
    def graph(self) -> Optional[GraphBackend]:
        """The registered GraphBackend, or None if register_graph_backend()
        has not been called. Read-only — registration via
        register_graph_backend() is the only way to set it, preserving
        this class's own "single owner of retrieval, nothing reaches
        into a backend directly" principle for external readers too.

        Added K2.2 (Retrieval Runtime cutover): GraphRAGPipeline needs the
        registered backend at construction time; this is the minimal
        public accessor for that, following the existing
        curator_registered property's pattern in this same class.
        """
        return self._graph

    async def _sync_graph(self, entry: KnowledgeEntry) -> None:
        """Shared by write() and update(): ask GraphIndexer to create/update/
        remove entry's graph node, then persist any node_id change back onto
        the canonical entry in L1 storage. GraphIndexer never touches L1
        itself (KnowledgeEntry remains canonical — Session 5.25 frozen
        architecture); this method is the one place that boundary is
        crossed, and only to persist an id, never entry content.

        Non-blocking: any exception here must never fail write()/update().
        """
        if self._graph_indexer is None:
            return
        try:
            node_id = await self._graph_indexer.sync(entry)
        except Exception as e:
            logger.warning("Graph sync failed (non-blocking): %s", e)
            return
        if node_id != entry.graph_node_id:
            entry.graph_node_id = node_id
            try:
                await self._storage.update(entry.entry_id, {"graph_node_id": node_id})
            except Exception as e:
                logger.warning(
                    "Persisting graph_node_id failed (non-blocking, graph "
                    "and storage may drift until next sync): %s", e)

    # ── Write ─────────────────────────────────────────────────────────────


    async def write(self,
                    content:        str,
                    content_type:   str = "",
                    layer_hint:     Optional[str] = None,
                    source:         str = "",
                    importance:     float = 0.5,
                    confidence:     float = 1.0,
                    trust_score:    float = 1.0,
                    tags:           Optional[List[str]] = None,
                    metadata:       Optional[Dict[str, Any]] = None,
                    worker_id:      str = "",
                    workflow_id:    str = "",
                    derived_from:   Optional[List[str]] = None,
                    procedure_name: Optional[str] = None,
                    embedding:      Optional[List[float]] = None,
                    entry_id:       Optional[str] = None,
                    summary:        str = "",
                    truth_status:   Optional[str] = None,
                    ) -> str:
        """
        Write a knowledge entry to the appropriate memory layer.
        Returns entry_id.

        truth_status: Session 5.5 Graph Population Strategy. Optional,
        defaults to KnowledgeEntry's own default ("unknown") when omitted --
        this parameter is purely additive; every existing call site is
        unaffected. Lets a caller that already trusts what it's writing
        (e.g. a future verification workflow) mark it graph-eligible
        ("verified"/"candidate") at write time, without a new autonomous
        promotion mechanism -- nothing changes truth_status on its own
        behalf; a caller must explicitly opt in per entry. Invalid values
        raise ValueError via KnowledgeEntry's own __post_init__ validation
        (TRUTH_STATUS enum, core/memory/knowledge_entry.py) -- not
        re-validated here, to avoid a second, driftable source of truth.

        Event flow:
          before_write hooks → L1 storage → L2 vector (if semantic) →
          L4 archive event → after_write hooks

        `summary` is an existing KnowledgeEntry field (FTS5-indexed
        alongside `content` and `tags` — see knowledge_entries_fts in
        sqlite_storage.py). Callers that have a natural structural split
        between a primary searchable body (`content`) and a secondary
        searchable label (`summary`) — e.g. an interaction's answer vs.
        its originating query — can use it instead of concatenating both
        into `content`. Both fields remain independently full-text
        searchable; neither is required.
        """
        # ── K3.5: Governance evaluation (Law 1 — Bounded Autonomy) ─────────
        # Runs BEFORE layer routing, entry construction, or any backend write.
        # If governance is not registered (tests, legacy paths), writes
        # proceed ungoverned — matching the permissive-when-absent pattern
        # established by BudgetGovernor and OrchestrationGovernor.
        if self._governance is not None:
            from core.governance.governance_kernel import (
                GovernanceAction, GovernanceVerdict,
            )
            gov_action = GovernanceAction(
                action_type="memory_write",
                worker_id=worker_id or "UnifiedMemory",
                description=f"memory_write: {content[:120]}",
                metadata={
                    "entry": {
                        "confidence": confidence,
                        "fact": content,
                        "content": content,
                    },
                    "current_count": self._write_count,
                    "content_type": content_type,
                    "layer_hint": layer_hint,
                    "importance": importance,
                },
            )
            gov_result = self._governance.evaluate_action(gov_action)

            if gov_result.verdict == GovernanceVerdict.REJECT:
                logger.warning(
                    "[UnifiedMemory] Write rejected by %s: %s",
                    gov_result.governor, gov_result.reason,
                )
                # Law 2 — Explicit State: emit event so rejection is observable.
                try:
                    ev = event_created(
                        entry_id or "rejected",
                        worker_id=worker_id, workflow_id=workflow_id,
                    )
                    # Reuse the archive's event infrastructure for the
                    # rejection record. The event payload carries the
                    # governance reason; the event_type distinguishes it.
                    from core.memory.knowledge_event import KnowledgeEvent
                    reject_ev = KnowledgeEvent(
                        event_type="memory_write_rejected",
                        entry_id=entry_id or "",
                        worker_id=worker_id,
                        workflow_id=workflow_id,
                        payload={
                            "reason": gov_result.reason,
                            "governor": gov_result.governor,
                            "content_preview": content[:80],
                        },
                    )
                    await self._archive.append_event(reject_ev)
                except Exception as e:
                    logger.warning("memory_write_rejected event emission failed: %s", e)
                return ""

            if gov_result.verdict == GovernanceVerdict.ESCALATE:
                logger.info(
                    "[UnifiedMemory] Write escalated by %s: %s",
                    gov_result.governor, gov_result.reason,
                )
                try:
                    from core.memory.knowledge_event import KnowledgeEvent
                    escalate_ev = KnowledgeEvent(
                        event_type="memory_write_escalated",
                        entry_id=entry_id or "",
                        worker_id=worker_id,
                        workflow_id=workflow_id,
                        payload={
                            "reason": gov_result.reason,
                            "governor": gov_result.governor,
                            "content_preview": content[:80],
                        },
                    )
                    await self._archive.append_event(escalate_ev)
                except Exception as e:
                    logger.warning("memory_write_escalated event emission failed: %s", e)
                return ""

        layer = self._router.route(
            content=content, content_type=content_type,
            importance=importance, trust_score=trust_score,
            layer_hint=layer_hint, procedure_name=procedure_name,
        )

        entry_kwargs = dict(
            entry_id=       entry_id or str(uuid.uuid4()),
            layer=          layer,
            content=        content,
            summary=        summary,
            importance=     max(0.0, min(1.0, importance)),
            confidence=     max(0.0, min(1.0, confidence)),
            trust_score=    max(0.0, min(1.0, trust_score)),
            source=         source,
            worker_id=      worker_id,
            workflow_id=    workflow_id,
            tags=           tags or [],
            metadata=       dict(metadata or {}),
            derived_from=   derived_from or [],
            procedure_name= procedure_name,
        )
        if truth_status is not None:
            entry_kwargs["truth_status"] = truth_status
        entry = KnowledgeEntry(**entry_kwargs)
        if content_type:
            entry.metadata["content_type"] = content_type

        # ── before_write hooks ────────────────────────────────────────────
        for hook in self._hooks.before_write:
            try:
                result = hook(entry)
                if asyncio.iscoroutine(result):
                    result = await result
                if result is None:
                    logger.debug("write rejected by before_write hook")
                    return ""
                entry = result
            except Exception as e:
                logger.warning("before_write hook error: %s", e)

        # ── L0: pure ephemeral working memory ─────────────────────────────
        # Populated immediately for layer=="l0" (no storage write at all).
        # For l1, L0 population is deferred to the end of write() -- see the
        # final "L0 cache coherence" block below for why.
        if layer == "l0":
            self._l0.put(entry.entry_id, entry)

        # ── L1: primary storage (always, except pure L0 ephemeral) ────────
        if layer != "l0":
            await self._storage.write(entry)

        # ── L2: vector index (semantic layers) ────────────────────────────
        if layer in ("l2", "l3"):
            try:
                await self._vector.index(
                    entry.entry_id, entry.content, embedding=embedding
                )
            except Exception as e:
                logger.warning("Vector indexing failed (non-blocking): %s", e)

        # ── Graph indexing: orthogonal index, NOT a memory layer ───────────
        # Architectural decision: the graph is an index over UnifiedMemory's
        # canonical entries (comparable to the vector/BM25/FTS5 indexes),
        # not a destination layer of its own. Any entry in any layer that is
        # graph-eligible gets indexed; layer never gates this.
        # Session 5.25: eligibility/extraction/sync now owned by
        # GraphIndexer (core/memory/graph/graph_indexer.py), not inlined
        # here — see _sync_graph() above.
        await self._sync_graph(entry)

        # ── L4: archive the creation event ────────────────────────────────
        try:
            ev = event_created(entry.entry_id,
                                worker_id=worker_id, workflow_id=workflow_id)
            await self._archive.append_event(ev)
            if self._archive_all:
                await self._archive.append_entry_snapshot(entry, reason="write")
        except Exception as e:
            logger.warning("Archive write failed (non-blocking): %s", e)

        # ── L0 cache coherence ──────────────────────────────────────────────
        # Populated last, after every storage mutation for this write() call
        # has completed -- including the graph_node_id backref above, which
        # runs its own separate self._storage.update() after the initial L1
        # write. Populating L0 any earlier (e.g. right after the L1 write)
        # would cache a snapshot that predates that update, so a subsequent
        # read() could return an entry missing graph_node_id even though the
        # database and the graph itself both already have it (Session 4C
        # established the same principle for created_at after UPSERT; this
        # is the same class of bug, newly reachable now that graph indexing
        # is no longer gated to unreachable layer=="l3" writes).
        # Storage failures upstream already raised before reaching here, so
        # no phantom-entry risk; reloading from storage (not the in-memory
        # object) guarantees L0 matches exactly what's persisted.
        if layer == "l1":
            persisted = await self._storage.read(entry.entry_id)
            self._l0.put(entry.entry_id, persisted if persisted is not None else entry)

        # ── after_write hooks ──────────────────────────────────────────────
        for hook in self._hooks.after_write:
            try:
                result = hook(entry)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.debug("after_write hook error: %s", e)

        self._write_count += 1
        return entry.entry_id

    # ── Read ──────────────────────────────────────────────────────────────

    async def read(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Read by entry_id. Checks L0 cache first, then L1 storage."""
        cached = self._l0.get(entry_id)
        if cached:
            return cached
        entry = await self._storage.read(entry_id)
        if entry:
            self._l0.put(entry_id, entry)
        return entry

    # ── Search ────────────────────────────────────────────────────────────

    async def search(self,
                     query:           str,
                     limit:           int = 10,
                     layer:           Optional[str] = None,
                     min_importance:  float = 0.0,
                     query_embedding: Optional[List[float]] = None,
                     include_deprecated: bool = False,
                     ) -> List[SearchResult]:
        """
        Hybrid search across L1 + L2 with composite scoring (ADR-006).

        1. L2 VectorBackend: BM25 + optional embeddings via RRF
        2. L1 StorageBackend: FTS5 keyword search
        3. Merge by entry_id, deduplicate
        4. Re-rank by composite score (recency × importance × relevance)
        5. Return top-k SearchResult objects
        """
        self._search_count += 1
        candidates: Dict[str, SearchResult] = {}

        # ── L2 hybrid search ──────────────────────────────────────────────
        try:
            vector_hits = await self._vector.search_hybrid(
                query=query, query_embedding=query_embedding,
                top_k=limit * 3
            )
            for rank, (entry_id, vec_score) in enumerate(vector_hits):
                entry = await self.read(entry_id)
                if entry is None:
                    continue
                if not include_deprecated and not entry.is_searchable():
                    continue
                if layer and entry.layer != layer:
                    continue
                if entry.importance < min_importance:
                    continue
                candidates[entry_id] = SearchResult(
                    entry=entry,
                    composite_score=0.0,
                    bm25_score=vec_score,
                    vector_score=vec_score,
                )
        except Exception as e:
            logger.warning("L2 vector search failed (non-blocking): %s", e)

        # ── L1 FTS5 search ─────────────────────────────────────────────────
        try:
            fts_hits = await self._storage.search_text(
                query=query, limit=limit * 3,
                layer=layer, min_importance=min_importance
            )
            for entry in fts_hits:
                if not include_deprecated and not entry.is_searchable():
                    continue
                if entry.entry_id in candidates:
                    # Merge: boost entries found in both L1 and L2
                    candidates[entry.entry_id].bm25_score = max(
                        candidates[entry.entry_id].bm25_score, 0.5
                    )
                else:
                    candidates[entry.entry_id] = SearchResult(
                        entry=entry, composite_score=0.0, bm25_score=0.5
                    )
        except Exception as e:
            logger.warning("L1 FTS5 search failed (non-blocking): %s", e)

        # ── Composite scoring (ADR-006) ────────────────────────────────────
        now = time.time()
        for sr in candidates.values():
            age_hours = (now - sr.entry.accessed_at) / 3600
            recency   = 0.99 ** age_hours
            relevance = max(sr.bm25_score, sr.vector_score)
            sr.recency_score   = recency
            sr.composite_score = (
                0.25 * recency +
                0.25 * sr.entry.importance +
                0.50 * relevance
            )

        ranked = sorted(candidates.values(), reverse=True)[:limit]
        return ranked

    # ── Update (partial) ──────────────────────────────────────────────────

    async def update(self, entry_id: str, delta: Dict[str, Any],
                      reason: str = "", worker_id: str = "") -> bool:
        """Partial update + archive delta event.

        Session 5.25: also re-syncs the graph. Before this change, update()
        never touched self._graph at all — an entry whose truth_status
        moved from "unknown" to "verified" via update() (the intended path
        for curator/verification workflows) would never get a graph node
        even once the graph backend and eligibility gate were otherwise
        working, because only write() had graph logic. This closes that gap
        using the same GraphIndexer.sync() write() now uses, so create and
        update go through one code path.
        """
        ok = await self._storage.update(entry_id, delta)
        if ok:
            self._l0.evict(entry_id)   # invalidate cache
            try:
                ev = event_updated(entry_id, delta=delta,
                                    reason=reason, worker_id=worker_id)
                await self._archive.append_event(ev)
            except Exception as e:
                logger.debug("Archive update event failed: %s", e)
            if self._graph_indexer is not None:
                entry = await self.read(entry_id)
                if entry is not None:
                    await self._sync_graph(entry)
        return ok

    # ── Delete ────────────────────────────────────────────────────────────

    async def delete(self, entry_id: str,
                     reason: str = "", worker_id: str = "") -> bool:
        """Delete an entry from all active memory layers.

        Deletion orchestration order (UM §5, FA §8 Risk 7):
          1. Load entry — must exist to proceed
          2. before_delete hooks — None return blocks deletion
          3. Archive: deletion event + entry snapshot (data preserved in L4)
          4. Remove L3 graph node (if entry has graph_node_id and graph active)
          5. Remove L2 vector index
          6. Remove L1 storage record
          7. Evict L0 cache (always — even if earlier steps failed)
          8. after_delete hooks — fire-and-forget

        Returns:
            True  — entry found and successfully deleted.
            False — entry not found, OR blocked by a before_delete hook.

        Non-blocking failures:
            Steps 3–5 are non-blocking: partial failures are logged but do not
            abort the delete.  L1 removal (step 6) is the authoritative deletion;
            if it fails, False is returned even though earlier steps may have run.
        """
        # 1. Load entry
        entry = await self.read(entry_id)
        if entry is None:
            logger.debug("delete: entry %s not found", entry_id[:8] if entry_id else "?")
            return False

        # 2. Execute before_delete hooks
        for hook in self._hooks.before_delete:
            try:
                result = hook(entry)
                if asyncio.iscoroutine(result):
                    result = await result
                if result is None:
                    logger.info(
                        "delete: blocked by before_delete hook for %s",
                        entry_id[:8],
                    )
                    return False
                entry = result   # hook may return a (possibly modified) entry
            except Exception as e:
                logger.warning("before_delete hook error: %s", e)

        # 3. Archive deletion event + snapshot (data is preserved in L4 before removal)
        try:
            ev = event_deleted(entry_id, reason=reason, worker_id=worker_id)
            await self._archive.append_event(ev)
            await self._archive.append_entry_snapshot(entry, reason="delete")
        except Exception as e:
            logger.warning("Archive deletion event failed (non-blocking): %s", e)

        # 4. Remove L3 graph node (non-blocking; graph_node_id may not be set)
        # Session 5.25: routed through GraphIndexer.remove() (owns removal),
        # rather than calling self._graph directly here.
        if entry.graph_node_id and self._graph_indexer is not None:
            deleted_from_graph = await self._graph_indexer.remove(entry)
            if not deleted_from_graph:
                logger.debug(
                    "Graph node %s not found during delete of %s "
                    "(may have been removed already)",
                    entry.graph_node_id, entry_id[:8],
                )

        # 5. Remove L2 vector index (non-blocking)
        try:
            await self._vector.remove(entry_id)
        except Exception as e:
            logger.debug("Vector removal for %s: %s", entry_id[:8], e)

        # 6. Remove L1 storage record (authoritative deletion)
        try:
            await self._storage.delete(entry_id)
        except Exception as e:
            logger.warning("Storage deletion failed for %s: %s", entry_id[:8], e)

        # 7. Evict L0 cache (always)
        self._l0.evict(entry_id)

        # 8. Execute after_delete hooks (fire-and-forget)
        for hook in self._hooks.after_delete:
            try:
                result = hook(entry)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.debug("after_delete hook error: %s", e)

        return True

    # ── Archive helpers (public API for workers) ──────────────────────────

    async def archive_event(self, event: KnowledgeEvent) -> None:
        """Write a KnowledgeEvent to the L4 archive.

        Public API that lets workers emit audit events without accessing the
        archive backend directly (dependency inversion compliance).
        Failures are logged but not raised (archive is non-blocking).
        """
        try:
            await self._archive.append_event(event)
        except Exception as e:
            logger.warning("archive_event failed: %s", e)

    async def archive_snapshot(self, entry: KnowledgeEntry,
                                reason: str = "snapshot") -> None:
        """Write an entry snapshot to the L4 archive.

        Public API for workers that need to snapshot an entry without
        accessing the archive backend directly.
        """
        try:
            await self._archive.append_entry_snapshot(entry, reason=reason)
        except Exception as e:
            logger.warning("archive_snapshot failed: %s", e)

    # ── Graph delegation (public API for workers) ─────────────────────────

    async def find_contradictions(self) -> List[Dict[str, Any]]:
        """Return pairs of mutually-contradicting graph nodes.

        Delegates to the active graph backend.  Returns an empty list when no
        graph backend is registered — callers do not need to check graph_active.

        Returns:
            List of dicts with keys: node_a (str), node_b (str).
        """
        if self._graph is None:
            return []
        try:
            return await self._graph.find_contradictions()
        except Exception as e:
            logger.warning("find_contradictions failed: %s", e)
            return []

    # ── Consolidate ───────────────────────────────────────────────────────

    async def consolidate(self, min_importance: float = 0.3,
                           promote_to_semantic: bool = True) -> Dict[str, int]:
        """
        Promote high-importance L1 entries to L2 semantic index.
        Evict low-importance L1 entries past age threshold.

        Returns: {"l1_promoted": N, "l1_evicted": N}
        """
        promoted = 0
        evicted  = 0

        l1_entries = await self._storage.get_by_layer("l1", limit=5000)
        now = time.time()

        for entry in l1_entries:
            age_days = (now - entry.created_at) / 86400

            if entry.importance >= 0.7 and promote_to_semantic:
                # Promote to L2 by indexing in vector backend
                await self._vector.index(entry.entry_id, entry.content)
                # Emit promote event to archive
                try:
                    ev = event_promoted(entry.entry_id,
                                         from_layer="l1", to_layer="l2")
                    await self._archive.append_event(ev)
                except Exception:
                    pass
                promoted += 1

            elif entry.importance < min_importance and age_days > 7:
                # Evict old low-importance entries
                await self._storage.delete(entry.entry_id)
                self._l0.evict(entry.entry_id)
                await self._vector.remove(entry.entry_id)
                evicted += 1

        logger.info("Consolidation: promoted=%d, evicted=%d", promoted, evicted)
        return {"l1_promoted": promoted, "l1_evicted": evicted}

    # ── Layer access ──────────────────────────────────────────────────────

    async def get_layer(self, layer: str, limit: int = 100,
                         min_importance: float = 0.0) -> List[KnowledgeEntry]:
        """Retrieve entries from a specific layer."""
        return await self._storage.get_by_layer(
            layer=layer, limit=limit, min_importance=min_importance
        )

    async def get_by_truth_status(self, truth_status: str,
                                   limit: int = 100) -> List[KnowledgeEntry]:
        """Retrieve entries by truth_status (for curator workflows)."""
        return await self._storage.get_by_truth_status(truth_status, limit=limit)

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Synchronous stats snapshot — safe to call from health monitors."""
        return {
            "writes": self._write_count,
            "searches": self._search_count,
            "l0": self._l0.stats(),
            "graph_active": self._graph is not None,
        }

    async def full_stats(self) -> Dict[str, Any]:
        """Async full stats from all backends."""
        storage_stats = await self._storage.stats()
        vector_stats  = await self._vector.stats()
        archive_stats = await self._archive.stats()
        graph_stats   = await self._graph.stats() if self._graph else {"active": False}
        total = storage_stats.get("total", 0)
        return {
            "total":   total,
            "writes":  self._write_count,
            "searches":self._search_count,
            "l0":      self._l0.stats(),
            "l1":      storage_stats,
            "l2":      vector_stats,
            "l3":      graph_stats,
            "l4":      archive_stats,
        }

    # ── Legacy migration helpers (temporary, removed after M6) ───────────

    async def import_from_vault(self, vault: Any) -> int:
        """Import entries from legacy MemoryVault. Returns count imported."""
        count = 0
        for e in getattr(vault, "entries", []):
            try:
                await self.write(
                    content=    e.get("fact", "") or e.get("content", ""),
                    content_type="fact",
                    source=     e.get("source", "legacy:vault"),
                    importance= float(e.get("confidence", 0.5)),
                    tags=       e.get("type", "").split(",") if e.get("type") else [],
                    metadata=   {"legacy_id": e.get("id", ""),
                                  "migrated_from": "MemoryVault"},
                    entry_id=   e.get("id"),
                )
                count += 1
            except Exception as ex:
                logger.warning("vault import skip: %s", ex)
        logger.info("Imported %d entries from MemoryVault", count)
        return count

    async def import_from_cognitive_vault(self, vault: Any) -> int:
        """Import entries from legacy CognitiveVault. Returns count imported."""
        count = 0
        tier_to_layer = {"L1": "l1", "L2": "l2", "L3": "l2", "L4": "l4"}
        for e in getattr(vault, "entries", []):
            try:
                tier  = e.get("tier", "L1")
                layer = tier_to_layer.get(tier, "l1")
                await self.write(
                    content=    e.get("content", ""),
                    layer_hint= layer,
                    source=     e.get("source", "legacy:cognitive"),
                    importance= float(e.get("confidence", 0.5)),
                    trust_score=float(e.get("confidence", 0.5)),
                    metadata=   {"legacy_id": e.get("id", ""),
                                  "legacy_tier": tier,
                                  "migrated_from": "CognitiveVault"},
                    entry_id=   e.get("id"),
                )
                count += 1
            except Exception as ex:
                logger.warning("cognitive vault import skip: %s", ex)
        logger.info("Imported %d entries from CognitiveVault", count)
        return count


# ── Module-level singleton ────────────────────────────────────────────────────

_unified_memory: Optional[UnifiedMemory] = None


def get_unified_memory(db_prefix: str = ".data/memory") -> UnifiedMemory:
    """Return (or create) the shared UnifiedMemory singleton."""
    global _unified_memory
    if _unified_memory is None:
        _unified_memory = UnifiedMemory(db_prefix=db_prefix)
    return _unified_memory
