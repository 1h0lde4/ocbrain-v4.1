"""
core/memory/knowledge_event.py — v4.3.4.92 Knowledge Event Audit Model

KnowledgeEvent: the lifecycle audit record (what happened to a KnowledgeEntry).
Distinct from KnowledgeEntry (what is known).

Architecture references:
  - Update Unified Memory Migration Design §2: "Separate KnowledgeEntry From KnowledgeEvent"
  - FA §5.4: "Knowledge Event Model — Merge into event backbone"
  - PI LAW 2: "All meaningful cognitive activity must emit immutable events"

Design constraints:
  - KnowledgeEvent is NEVER used as primary storage.
  - KnowledgeEvent is an audit log entry — append-only, immutable once written.
  - Every mutation to a KnowledgeEntry produces exactly one KnowledgeEvent.
  - Events are written to L4 Archive via ArchiveBackend.append_event().
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Exhaustive event type catalog, aligned with ArchiveBackend.query_events()
EVENT_TYPES = {
    "created",       # New KnowledgeEntry written
    "updated",       # KnowledgeEntry fields modified
    "accessed",      # KnowledgeEntry read (for access_count tracking)
    "promoted",      # Entry moved from lower to higher layer (L1→L2)
    "archived",      # Entry snapshot written to L4
    "contradicted",  # Entry flagged as conflicting with another
    "merged",        # Two entries consolidated into one
    "deprecated",    # truth_status set to "deprecated"
    "deleted",       # Entry removed from active storage
    "curated",       # MemoryCuratorWorker modified the entry
}


@dataclass(frozen=True)
class KnowledgeEvent:
    """Immutable audit record for a single KnowledgeEntry lifecycle change.

    Architecture:
        FA §4.1 Layer 1 — EventStream backbone.
        PI LAW 2 — Every major operation must be observable and replayable.
        UM §2 — KnowledgeEvent is the audit record, never the primary object.

    Attributes:
        event_id: Unique identifier for this event.
        event_type: One of EVENT_TYPES.
        entry_id: The KnowledgeEntry this event refers to.
        timestamp: Unix epoch when the event occurred.
        worker_id: Which worker produced this event.
        workflow_id: Which workflow context, if any.
        delta: For 'updated' events, the fields that changed.
        from_layer: For 'promoted' events, the source layer.
        to_layer: For 'promoted' events, the destination layer.
        reason: Human-readable explanation.
        metadata: Additional context.
    """

    event_id:    str            = field(default_factory=lambda: str(uuid.uuid4()))
    event_type:  str            = "created"
    entry_id:    str            = ""
    timestamp:   float          = field(default_factory=time.time)
    worker_id:   str            = ""
    workflow_id: str            = ""
    delta:       Dict[str, Any] = field(default_factory=dict)
    from_layer:  str            = ""
    to_layer:    str            = ""
    reason:      str            = ""
    metadata:    Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, "event_type", "created")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSONL/SQLite storage."""
        import json
        return {
            "event_id":    self.event_id,
            "event_type":  self.event_type,
            "entry_id":    self.entry_id,
            "timestamp":   self.timestamp,
            "worker_id":   self.worker_id,
            "workflow_id": self.workflow_id,
            "delta":       json.dumps(self.delta, default=str),
            "from_layer":  self.from_layer,
            "to_layer":    self.to_layer,
            "reason":      self.reason,
            "metadata":    json.dumps(self.metadata, default=str),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeEvent":
        """Deserialize from dict."""
        import json

        def _j(v: Any, default: Any) -> Any:
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except Exception:
                    return default
            return v if v is not None else default

        return cls(
            event_id=    d.get("event_id", str(uuid.uuid4())),
            event_type=  d.get("event_type", "created"),
            entry_id=    d.get("entry_id", ""),
            timestamp=   float(d.get("timestamp", time.time())),
            worker_id=   d.get("worker_id", ""),
            workflow_id= d.get("workflow_id", ""),
            delta=       _j(d.get("delta"), {}),
            from_layer=  d.get("from_layer", ""),
            to_layer=    d.get("to_layer", ""),
            reason=      d.get("reason", ""),
            metadata=    _j(d.get("metadata"), {}),
        )

    def __repr__(self) -> str:
        return (f"KnowledgeEvent(type={self.event_type}, "
                f"entry={self.entry_id[:8] if self.entry_id else '?'}, "
                f"worker={self.worker_id or '-'})")


# ── Factory Functions ─────────────────────────────────────────────────────────
# These match the exact signatures imported by unified_memory.py (line 36-39):
#   from core.memory.knowledge_event import (
#       KnowledgeEvent, event_created, event_updated, event_promoted, event_archived,
#   )

def event_created(entry_id: str, *,
                  worker_id: str = "", workflow_id: str = "",
                  reason: str = "entry_written") -> KnowledgeEvent:
    """Factory for 'created' events. Called by UnifiedMemory.write()."""
    return KnowledgeEvent(
        event_type="created", entry_id=entry_id,
        worker_id=worker_id, workflow_id=workflow_id, reason=reason,
    )


def event_updated(entry_id: str, *,
                  delta: Optional[Dict[str, Any]] = None,
                  reason: str = "", worker_id: str = "") -> KnowledgeEvent:
    """Factory for 'updated' events. Called by UnifiedMemory.update()."""
    return KnowledgeEvent(
        event_type="updated", entry_id=entry_id,
        delta=delta or {}, reason=reason, worker_id=worker_id,
    )


def event_promoted(entry_id: str, *,
                   from_layer: str = "", to_layer: str = "",
                   reason: str = "consolidation_promote") -> KnowledgeEvent:
    """Factory for 'promoted' events. Called by UnifiedMemory.consolidate()."""
    return KnowledgeEvent(
        event_type="promoted", entry_id=entry_id,
        from_layer=from_layer, to_layer=to_layer, reason=reason,
    )


def event_archived(entry_id: str, *,
                   reason: str = "snapshot",
                   worker_id: str = "") -> KnowledgeEvent:
    """Factory for 'archived' events. Called on L4 snapshot writes."""
    return KnowledgeEvent(
        event_type="archived", entry_id=entry_id,
        reason=reason, worker_id=worker_id,
    )


def event_curated(entry_id: str, *,
                  delta: Optional[Dict[str, Any]] = None,
                  reason: str = "",
                  worker_id: str = "memory_curator") -> KnowledgeEvent:
    """Factory for 'curated' events. Called by MemoryCuratorWorker."""
    return KnowledgeEvent(
        event_type="curated", entry_id=entry_id,
        delta=delta or {}, reason=reason, worker_id=worker_id,
    )
