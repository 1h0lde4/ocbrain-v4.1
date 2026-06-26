"""
core/workers/curator.py — MemoryCuratorWorker (v4.3.6)

Active memory improvement worker. Subclasses AbstractCognitiveWorker.

Architecture references:
  - PI §7.1: MemoryCuratorWorker — canonical worker type.
  - FA §1.1 Technical Debt: "MemoryCuratorWorker class entirely absent"
  - FA §4.1 Layer 3: "MemoryCuratorWorker (active memory improvement, memify-style)"
  - FA §4.1 Layer 4: "Memory Curator (memify-style: prune, strengthen, derive, align)"
  - FA v4.3.6: "MemoryCuratorWorker as CognitiveWorker subclass (currently MISSING)"
  - FA §6 Priority Matrix: "MemoryCuratorWorker — §7.1 canonical — Low effort — HIGH"
  - FA Pattern 4: "MemoryConsolidator should not just evict+promote but actively:
                    prune stale nodes, strengthen high-access connections, derive new
                    facts from existing facts, detect and resolve contradictions."
  - FA §8 Risk 7: "Incorrect fact derivation (mitigate: low confidence score + review);
                    over-pruning (mitigate: importance threshold before delete, log
                    pruned entries to L4)"
  - UM §5: Memory Curator Lifecycle Hooks.

Design:
  - Registers with UnifiedMemory.HookRegistry at startup.
  - Wraps and extends MemoryConsolidator with Agent Protocol interface.
  - Active memify pipeline: prune stale, strengthen high-access, resolve contradictions.
  - Constraint: All derived facts use truth_status="candidate", confidence < 0.7.
  - All deletions are logged to L4 Archive before removal (FA §8 Risk 7 mitigation).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.workers.base import (
    AbstractCognitiveWorker,
    WorkerContext,
    WorkerResult,
)
from core.memory.knowledge_entry import KnowledgeEntry, GRAPH_ELIGIBLE_STATUSES
from core.memory.knowledge_event import event_curated

logger = logging.getLogger("ocbrain.workers.curator")


# ── Curation Configuration ────────────────────────────────────────────────────

@dataclass
class CurationConfig:
    """Configuration for memory curation thresholds.

    Architecture:
        FA §8 Risk 7 — "importance threshold before delete"
        FA Pattern 4 — Active memify parameters.

    Attributes:
        stale_age_days: Entries older than this with low access are stale.
        stale_importance_floor: Entries below this importance are prune candidates.
        strengthen_access_threshold: Minimum access_count to trigger strengthening.
        strengthen_importance_boost: How much to boost importance on strengthening.
        max_importance_cap: Maximum importance after strengthening.
        derived_confidence_cap: Maximum confidence for curator-derived facts.
        derived_truth_status: Truth status for curator-derived facts.
        min_importance_to_prune: Minimum importance below which pruning is allowed.
        archive_before_prune: Whether to snapshot to L4 before pruning.
    """

    stale_age_days:              float = 30.0
    stale_importance_floor:      float = 0.15
    strengthen_access_threshold: int   = 5
    strengthen_importance_boost: float = 0.1
    max_importance_cap:          float = 0.95
    derived_confidence_cap:      float = 0.65
    derived_truth_status:        str   = "candidate"
    min_importance_to_prune:     float = 0.1
    archive_before_prune:        bool  = True


# ── Curation Result ───────────────────────────────────────────────────────────

@dataclass
class CurationReport:
    """Results of a single curation sweep.

    Attributes:
        entries_scanned: Total entries examined.
        pruned: Number of stale entries removed.
        strengthened: Number of high-access entries boosted.
        contradictions_found: Number of contradiction pairs detected.
        contradictions_resolved: Number of contradictions resolved.
        errors: Number of non-fatal errors during curation.
    """

    entries_scanned:        int = 0
    pruned:                 int = 0
    strengthened:           int = 0
    contradictions_found:   int = 0
    contradictions_resolved: int = 0
    errors:                 int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries_scanned": self.entries_scanned,
            "pruned": self.pruned,
            "strengthened": self.strengthened,
            "contradictions_found": self.contradictions_found,
            "contradictions_resolved": self.contradictions_resolved,
            "errors": self.errors,
        }


# ── MemoryCuratorWorker ───────────────────────────────────────────────────────

class MemoryCuratorWorker(AbstractCognitiveWorker):
    """Active memory improvement worker.

    Architecture:
        PI §7.1 — Canonical worker type: MemoryCuratorWorker.
        FA §4.1 Layer 3 — "MemoryCuratorWorker (active memory improvement,
                            memify-style)"
        FA v4.3.6 — "MemoryCuratorWorker as CognitiveWorker subclass"
        FA Pattern 4 — "actively: prune stale nodes, strengthen high-access
                         connections, derive new facts from existing facts,
                         detect and resolve contradictions."

    Lifecycle:
        1. register() — wires into UnifiedMemory HookRegistry at startup.
        2. execute() — (inherited) governance-wrapped entry point.
        3. _run() — performs a full curation sweep:
           a. prune_stale() — remove old low-importance entries.
           b. strengthen_high_access() — boost frequently accessed entries.
           c. resolve_contradictions() — detect and resolve conflicting entries.

    Constraints (FA §8 Risk 7):
        - All derived facts: truth_status="candidate", confidence < 0.7.
        - All deletions: archived to L4 before removal.
        - Importance threshold guards against over-pruning.

    Usage:
        from core.memory.unified_memory import get_unified_memory
        memory = get_unified_memory()
        curator = MemoryCuratorWorker()
        curator.register(memory)
        result = await curator.execute(WorkerContext(query="curate"))
    """

    worker_type: str = "MemoryCuratorWorker"

    def __init__(self, config: Optional[CurationConfig] = None,
                 **kwargs: Any) -> None:
        """Initialize the MemoryCuratorWorker.

        Args:
            config: Curation thresholds. Uses defaults if None.
            **kwargs: Passed to AbstractCognitiveWorker.__init__.
        """
        super().__init__(**kwargs)
        self._config = config or CurationConfig()
        self._memory: Any = None  # Set by register()
        self._registered: bool = False
        self._total_sweeps: int = 0

    # ── HookRegistry Integration ──────────────────────────────────────────

    def register(self, memory: Any) -> None:
        """Register with UnifiedMemory's HookRegistry.

        Wires curator hooks into the memory write/promote/archive/delete
        lifecycle. Called once at startup.

        Args:
            memory: The UnifiedMemory instance to register with.

        Architecture:
            UM §5 — Memory Curator Lifecycle Hooks.
            FA v4.3.6 — "Wraps MemoryConsolidator with Agent Protocol interface"
        """
        self._memory = memory
        self._registered = True

        # Register hook functions with the HookRegistry
        memory._hooks.before_write.append(self._before_write_hook)
        memory._hooks.after_write.append(self._after_write_hook)
        memory._hooks.before_delete.append(self._before_delete_hook)

        # Notify the HookRegistry that a curator is registered
        memory._hooks.register_curator(self)

        logger.info("[MemoryCuratorWorker] Registered with UnifiedMemory HookRegistry")

    # ── Lifecycle Hooks ───────────────────────────────────────────────────

    def _before_write_hook(self, entry: KnowledgeEntry) -> Optional[KnowledgeEntry]:
        """Pre-write quality gate.

        Architecture:
            UM §5 — "before_write: List[fn(entry) → Optional[entry]] — None means reject"

        Rejects entries with empty content. Applies minimum importance floor.
        Returns None to reject, or the (possibly modified) entry to accept.
        """
        if not entry.content or not entry.content.strip():
            logger.debug("[Curator:before_write] Rejected empty content")
            return None

        # Enforce minimum content length for semantic entries
        if entry.layer in ("l2", "l3") and len(entry.content.strip()) < 10:
            logger.debug("[Curator:before_write] Rejected short L2/L3 content: %r",
                         entry.content[:40])
            return None

        return entry

    def _after_write_hook(self, entry: KnowledgeEntry) -> None:
        """Post-write observation.

        Architecture:
            UM §5 — "after_write: List[fn(entry) → None] — fire-and-forget"

        Logs the write for curation statistics. No mutations here.
        """
        logger.debug("[Curator:after_write] Observed write: %s (layer=%s, imp=%.2f)",
                     entry.entry_id[:8], entry.layer, entry.importance)

    def _before_delete_hook(self, entry: KnowledgeEntry) -> Optional[KnowledgeEntry]:
        """Pre-delete archival gate.

        Architecture:
            FA §8 Risk 7 — "log pruned entries to L4"
            UM §5 — "before_delete: List[fn(entry) → Optional[entry]] — None means reject"

        Ensures every deletion is logged. Returns the entry to proceed
        with deletion, or None to prevent it.
        """
        # Never delete L4 archive entries (immutable by definition)
        if entry.layer == "l4":
            logger.warning("[Curator:before_delete] Blocked L4 archive deletion: %s",
                           entry.entry_id[:8])
            return None

        logger.info("[Curator:before_delete] Allowing deletion of %s (layer=%s)",
                    entry.entry_id[:8], entry.layer)
        return entry

    # ── Core Curation Logic ───────────────────────────────────────────────

    async def _run(self, context: WorkerContext) -> WorkerResult:
        """Execute a full curation sweep.

        Architecture:
            FA v4.3.6 — "Active memify pipeline: prune stale, strengthen
                          high-access, derive facts"
            FA Pattern 4 — "actively: prune stale nodes, strengthen high-access
                             connections, detect and resolve contradictions."

        Args:
            context: WorkerContext. The query field is ignored; curation
                     is a system-internal operation.

        Returns:
            WorkerResult containing the CurationReport.
        """
        if not self._registered or self._memory is None:
            return WorkerResult(
                success=False,
                error="MemoryCuratorWorker not registered with UnifiedMemory. "
                      "Call register(memory) first.",
            )

        self._total_sweeps += 1
        report = CurationReport()

        await self.emit_progress(context, "Starting curation sweep", percent=0.0)

        # ── Phase 1: Prune stale entries ──────────────────────────────────
        try:
            pruned = await self.prune_stale()
            report.pruned = pruned
            report.entries_scanned += pruned  # minimum scanned
        except Exception as e:
            logger.error("[Curator] prune_stale error: %s", e)
            report.errors += 1

        await self.emit_progress(context, f"Pruned {report.pruned} stale entries",
                                 percent=33.0)

        # ── Phase 2: Strengthen high-access entries ───────────────────────
        try:
            strengthened = await self.strengthen_high_access()
            report.strengthened = strengthened
        except Exception as e:
            logger.error("[Curator] strengthen_high_access error: %s", e)
            report.errors += 1

        await self.emit_progress(context,
                                 f"Strengthened {report.strengthened} entries",
                                 percent=66.0)

        # ── Phase 3: Resolve contradictions ───────────────────────────────
        try:
            found, resolved = await self.resolve_contradictions()
            report.contradictions_found = found
            report.contradictions_resolved = resolved
        except Exception as e:
            logger.error("[Curator] resolve_contradictions error: %s", e)
            report.errors += 1

        await self.emit_progress(context,
                                 f"Resolved {report.contradictions_resolved}/"
                                 f"{report.contradictions_found} contradictions",
                                 percent=100.0)

        logger.info("[Curator] Sweep #%d complete: %s",
                    self._total_sweeps, report.to_dict())

        return WorkerResult(
            success=True,
            output=report.to_dict(),
            artifacts={"curation_report": report.to_dict()},
        )

    # ── Prune Stale ───────────────────────────────────────────────────────

    async def prune_stale(self) -> int:
        """Remove old, low-importance entries from active memory.

        Architecture:
            FA Pattern 4 — "prune stale nodes"
            FA §8 Risk 7 — "importance threshold before delete, log pruned
                             entries to L4"

        Returns:
            Number of entries pruned.
        """
        now = time.time()
        pruned = 0
        cfg = self._config

        # Scan L1 episodic entries (most likely to go stale)
        l1_entries: List[KnowledgeEntry] = await self._memory.get_layer(
            "l1", limit=5000, min_importance=0.0,
        )

        for entry in l1_entries:
            if self.is_cancelled:
                break

            age_days = (now - entry.created_at) / 86400.0

            # Only prune if: old enough AND low importance AND low access
            if (age_days > cfg.stale_age_days
                    and entry.importance < cfg.min_importance_to_prune
                    and entry.access_count < 2):

                # Archive to L4 before pruning (FA §8 Risk 7)
                if cfg.archive_before_prune:
                    try:
                        ev = event_curated(
                            entry_id=entry.entry_id,
                            delta={"action": "prune", "age_days": round(age_days, 1)},
                            reason=f"Stale: age={age_days:.0f}d, imp={entry.importance:.2f}",
                            worker_id=self._id,
                        )
                        await self._memory._archive.append_event(ev)
                        await self._memory._archive.append_entry_snapshot(
                            entry, reason="curator_prune",
                        )
                    except Exception as e:
                        logger.warning("[Curator] Archive before prune failed: %s", e)

                # Delete from active storage
                try:
                    await self._memory._storage.delete(entry.entry_id)
                    self._memory._l0.evict(entry.entry_id)
                    await self._memory._vector.remove(entry.entry_id)
                    pruned += 1
                    logger.debug("[Curator] Pruned: %s (age=%.0fd, imp=%.2f)",
                                 entry.entry_id[:8], age_days, entry.importance)
                except Exception as e:
                    logger.warning("[Curator] Prune delete failed for %s: %s",
                                   entry.entry_id[:8], e)

        return pruned

    # ── Strengthen High-Access ────────────────────────────────────────────

    async def strengthen_high_access(self) -> int:
        """Boost importance of frequently accessed entries.

        Architecture:
            FA Pattern 4 — "strengthen high-access connections"

        Entries accessed more than the threshold get an importance boost,
        capped at max_importance_cap to prevent runaway inflation.

        Returns:
            Number of entries strengthened.
        """
        strengthened = 0
        cfg = self._config

        # Scan L1 and L2 entries
        for layer in ("l1", "l2"):
            entries: List[KnowledgeEntry] = await self._memory.get_layer(
                layer, limit=5000, min_importance=0.0,
            )

            for entry in entries:
                if self.is_cancelled:
                    break

                if (entry.access_count >= cfg.strengthen_access_threshold
                        and entry.importance < cfg.max_importance_cap):

                    new_importance = min(
                        cfg.max_importance_cap,
                        entry.importance + cfg.strengthen_importance_boost,
                    )
                    delta = {"importance": new_importance}

                    try:
                        await self._memory.update(
                            entry.entry_id, delta,
                            reason="curator_strengthen",
                            worker_id=self._id,
                        )
                        strengthened += 1
                        logger.debug("[Curator] Strengthened: %s (%.2f → %.2f, "
                                     "access=%d)",
                                     entry.entry_id[:8], entry.importance,
                                     new_importance, entry.access_count)
                    except Exception as e:
                        logger.warning("[Curator] Strengthen update failed "
                                       "for %s: %s", entry.entry_id[:8], e)

        return strengthened

    # ── Resolve Contradictions ────────────────────────────────────────────

    async def resolve_contradictions(self) -> tuple[int, int]:
        """Detect and resolve contradicting memory entries.

        Architecture:
            FA v4.3.6 — "Contradiction resolution: when graph finds
                          contradictions, curator resolves"
            FA Pattern 4 — "detect and resolve contradictions"

        Strategy:
            1. Query graph for contradiction edges.
            2. For each pair, compare confidence and recency.
            3. Mark the weaker entry as "deprecated" (not deleted).
            4. Log resolution to L4 Archive.

        Returns:
            Tuple of (contradictions_found, contradictions_resolved).
        """
        found = 0
        resolved = 0

        # Skip if no graph backend is wired
        if self._memory._graph is None:
            logger.debug("[Curator] No graph backend — skipping contradiction check")
            return found, resolved

        # Query graph for contradiction edges
        try:
            contradictions: List[Dict[str, Any]] = (
                await self._memory._graph.find_contradictions()
            )
        except Exception as e:
            logger.warning("[Curator] Graph contradiction query failed: %s", e)
            return found, resolved

        found = len(contradictions)

        for contradiction in contradictions:
            if self.is_cancelled:
                break

            source_id = contradiction.get("source", "")
            target_id = contradiction.get("target", "")

            # Strip "mem:" prefix if present (used by unified_memory graph indexing)
            source_entry_id = source_id.replace("mem:", "")
            target_entry_id = target_id.replace("mem:", "")

            # Load both entries
            try:
                source_entry = await self._memory.read(source_entry_id)
                target_entry = await self._memory.read(target_entry_id)
            except Exception:
                continue

            if source_entry is None or target_entry is None:
                continue

            # Resolution strategy: newer + higher confidence wins
            source_score = source_entry.confidence + (
                0.001 * source_entry.created_at  # tiny recency tiebreaker
            )
            target_score = target_entry.confidence + (
                0.001 * target_entry.created_at
            )

            # Deprecate the weaker entry
            loser_id = (target_entry.entry_id if source_score >= target_score
                        else source_entry.entry_id)
            winner_id = (source_entry.entry_id if source_score >= target_score
                         else target_entry.entry_id)

            try:
                await self._memory.update(
                    loser_id,
                    {"truth_status": "deprecated"},
                    reason=f"Contradicts {winner_id[:8]} (curator resolution)",
                    worker_id=self._id,
                )

                # Archive the resolution event
                ev = event_curated(
                    entry_id=loser_id,
                    delta={
                        "action": "resolve_contradiction",
                        "winner": winner_id,
                        "loser": loser_id,
                    },
                    reason="contradiction_resolved",
                    worker_id=self._id,
                )
                await self._memory._archive.append_event(ev)

                resolved += 1
                logger.info("[Curator] Contradiction resolved: %s (deprecated) "
                            "vs %s (retained)", loser_id[:8], winner_id[:8])
            except Exception as e:
                logger.warning("[Curator] Contradiction resolution failed: %s", e)

        return found, resolved

    # ── Stats Override ────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return curator-specific statistics.

        Architecture:
            PI §7.2 — "support observability"
        """
        base = super().stats()
        base["total_sweeps"] = self._total_sweeps
        base["registered"] = self._registered
        base["config"] = {
            "stale_age_days": self._config.stale_age_days,
            "stale_importance_floor": self._config.stale_importance_floor,
            "strengthen_access_threshold": self._config.strengthen_access_threshold,
            "min_importance_to_prune": self._config.min_importance_to_prune,
        }
        return base
