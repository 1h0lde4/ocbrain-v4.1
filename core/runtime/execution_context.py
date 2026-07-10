"""
core/runtime/execution_context.py — ExecutionContext (K2.1)

The canonical data object threading through one execution.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §7.2 — ExecutionContext.
    ADR-001 — ExecutionContext replaces WorkerContext.

Design:
    - Immutable after creation except for WorkingMemory writes during execution.
    - Fields are additive-only across versions — no field will be removed.
    - Replaces the earlier WorkerContext prototype.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.runtime.cancellation import CancellationToken
from core.runtime.working_memory import WorkingMemory


@dataclass
class ExecutionContext:
    """The canonical data object threading through one execution.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §7.2 — ExecutionContext frozen fields.
        ADR-001 — Replaces WorkerContext (deprecated).

    Attributes:
        request_id: Unique per request (UUID).
        worker_id: Assigned by ExecutionRuntime.
        session_id: Correlates related requests.
        causal_chain: Parent execution IDs for replay.
        working_memory: Scoped scratch space (L0).
        governance_state: Budget counters, step counts, recursion depth.
        cancellation_token: Cooperative cancellation.
        workflow_id: Set by WorkflowRuntime if in a workflow.
        parent_worker_id: Set if invoked by SupervisorWorker.
        metadata: Extensible context data.
    """

    request_id:         str                = field(default_factory=lambda: str(uuid.uuid4()))
    worker_id:          str                = ""
    session_id:         str                = field(default_factory=lambda: str(uuid.uuid4()))
    causal_chain:       List[str]          = field(default_factory=list)
    working_memory:     WorkingMemory      = field(default_factory=WorkingMemory)
    governance_state:   Dict[str, Any]     = field(default_factory=dict)
    cancellation_token: CancellationToken  = field(default_factory=CancellationToken)
    workflow_id:        str                = ""
    parent_worker_id:   str                = ""
    metadata:           Dict[str, Any]     = field(default_factory=dict)

    # ── Convenience: bridge to legacy WorkerContext ─────────────────────

    @property
    def task_id(self) -> str:
        """Backward-compatible alias for request_id.

        WorkerContext used task_id; ExecutionContext uses request_id.
        This property ensures existing code referencing context.task_id
        continues to work during the migration period.

        Compatibility shim — will be removed after K2.4.
        """
        return self.request_id

    @property
    def query(self) -> str:
        """Backward-compatible alias reading query from metadata.

        WorkerContext had a top-level query field. ExecutionContext stores
        it in metadata['query'] instead (the query is a parameter of the
        request, not a structural field of the execution).

        Compatibility shim — will be removed after K2.4.
        """
        return self.metadata.get("query", "")

    @property
    def recursion_depth(self) -> int:
        """Backward-compatible alias reading recursion_depth from governance_state.

        WorkerContext had a top-level recursion_depth field. ExecutionContext
        stores it in governance_state['recursion_depth'].

        Compatibility shim — will be removed after K2.4.
        """
        return self.governance_state.get("recursion_depth", 0)

    def to_worker_context(self) -> "WorkerContext":
        """Create a legacy WorkerContext from this ExecutionContext.

        Compatibility shim for code that still expects WorkerContext.
        Workers should migrate to accepting ExecutionContext directly.

        Returns:
            A WorkerContext populated from this ExecutionContext's fields.
        """
        from core.workers.base import WorkerContext
        return WorkerContext(
            task_id=self.request_id,
            query=self.metadata.get("query", ""),
            parameters=self.metadata.get("parameters", {}),
            recursion_depth=self.governance_state.get("recursion_depth", 0),
            parent_worker_id=self.parent_worker_id,
            workflow_id=self.workflow_id,
            metadata=self.metadata,
        )
