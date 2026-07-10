"""
core/runtime/execution_runtime.py — ExecutionRuntime (K2.1)

The service that constructs and invokes one Worker for one unit of work.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §7.1 — ExecutionRuntime.
    Constitution Law 1 — Bounded Autonomy (governance in template method).
    Constitution Law 2 — Explicit State (lifecycle events).
    Constitution Law 11 — Failure Containment (never raises).

Design:
    - Constructs a fresh Worker instance per invoke() call (ADR-003).
    - Creates ExecutionContext with WorkingMemory.
    - Delegates to Worker.execute() (template method handles governance).
    - Captures WorkerResult.
    - Cleans up WorkingMemory.
    - Returns WorkerResult — NEVER raises (failures are result values).
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from core.governance.governance_kernel import GovernanceKernel, get_governance_kernel
from core.events.event_stream import EventStream, get_event_stream
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_context import ExecutionContext
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.working_memory import WorkingMemory
from core.workers.base import WorkerResult

logger = logging.getLogger("ocbrain.runtime.execution")


class ExecutionRuntime:
    """The service that constructs and invokes one Worker for one unit of work.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §7.1 — ExecutionRuntime.

    Owns:
        - Worker instantiation (via WorkerRegistry)
        - ExecutionContext creation and propagation
        - WorkingMemory allocation and cleanup
        - Failure containment at the single-execution level
        - Cancellation propagation

    Does NOT own:
        - Multi-step coordination (WorkflowRuntime)
        - Retries across executions (WorkflowRuntime)
        - Worker implementation (Worker subclass)
        - Governance evaluation (Worker's template method)

    Contract:
        async def invoke(worker_type, context=None, **kwargs) -> WorkerResult
        Never raises — failures become WorkerResult(success=False).
    """

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        governance: Optional[GovernanceKernel] = None,
        event_stream: Optional[EventStream] = None,
    ) -> None:
        """Initialize the ExecutionRuntime.

        Args:
            worker_registry: Registry of constructable Worker types.
            governance: GovernanceKernel for worker DI. Uses singleton if None.
            event_stream: EventStream for worker DI. Uses singleton if None.
        """
        self._registry = worker_registry
        self._governance = governance or get_governance_kernel()
        self._event_stream = event_stream or get_event_stream()
        self._total_invocations: int = 0
        self._total_failures: int = 0
        logger.info("ExecutionRuntime initialized (registry: %s types)",
                     len(worker_registry.list_types()))

    async def invoke(
        self,
        worker_type: str,
        context: Optional[ExecutionContext] = None,
        *,
        query: str = "",
        session_id: str = "",
        parent_worker_id: str = "",
        workflow_id: str = "",
        causal_chain: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkerResult:
        """Invoke a Worker for one unit of work.

        Architecture:
            KERNEL_ARCHITECTURE_v1.0.md §7.1 — ExecutionRuntime.invoke().
            Law 11 — Failure Containment: never raises past this boundary.

        Lifecycle:
            1. Resolve worker_type via WorkerRegistry
            2. Construct Worker instance (DI: governance, event_stream)
            3. Create or reuse ExecutionContext with WorkingMemory
            4. Worker.execute(context) — governance and events handled inside
            5. Capture WorkerResult
            6. Clean up WorkingMemory
            7. Return WorkerResult (never raises)

        Args:
            worker_type: Registered worker type name.
            context: Pre-built ExecutionContext. If None, one is created from kwargs.
            query: Query string (used if context is None).
            session_id: Session correlation ID (used if context is None).
            parent_worker_id: Parent worker ID for Supervisor pattern.
            workflow_id: Enclosing workflow ID.
            causal_chain: Parent execution IDs for replay.
            metadata: Additional execution metadata.

        Returns:
            WorkerResult — always. Never raises.
        """
        start_time = time.time()
        self._total_invocations += 1

        # ── Step 1: Resolve worker type ──────────────────────────────────
        worker_cls = self._registry.get(worker_type)
        if worker_cls is None:
            self._total_failures += 1
            logger.error("ExecutionRuntime: unknown worker type '%s'. "
                         "Registered: %s", worker_type,
                         self._registry.list_types())
            return WorkerResult(
                success=False,
                error=f"Unknown worker type: '{worker_type}'",
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"worker_type": worker_type},
            )

        # ── Step 2: Construct Worker instance (ADR-003: ephemeral) ───────
        try:
            worker = worker_cls(
                governance=self._governance,
                event_stream=self._event_stream,
            )
        except Exception as e:
            self._total_failures += 1
            logger.error("ExecutionRuntime: failed to construct '%s': %s",
                         worker_type, e, exc_info=True)
            return WorkerResult(
                success=False,
                error=f"Worker construction failed: {e}",
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"worker_type": worker_type},
            )

        # ── Step 3: Create/reuse ExecutionContext ────────────────────────
        if context is None:
            context = ExecutionContext(
                request_id=str(uuid.uuid4()),
                worker_id=worker.worker_id,
                session_id=session_id or str(uuid.uuid4()),
                causal_chain=causal_chain or [],
                working_memory=WorkingMemory(),
                governance_state={"recursion_depth": 0},
                cancellation_token=CancellationToken(),
                workflow_id=workflow_id,
                parent_worker_id=parent_worker_id,
                metadata={
                    "query": query,
                    **(metadata or {}),
                },
            )
        else:
            # Ensure worker_id is set on the context
            context.worker_id = worker.worker_id

        # ── Step 4: Execute via template method ──────────────────────────
        # Worker.execute() handles governance + events internally.
        # We pass a WorkerContext bridge for backward compatibility.
        try:
            worker_context = context.to_worker_context()
            result = await worker.execute(worker_context)
        except Exception as e:
            # This should never happen — Worker.execute() catches all
            # exceptions. But if it does, we contain it here.
            self._total_failures += 1
            logger.error("ExecutionRuntime: unexpected exception from "
                         "'%s'.execute(): %s", worker_type, e, exc_info=True)
            result = WorkerResult(
                success=False,
                error=f"Unexpected execution error: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # ── Step 5: Emit runtime event ───────────────────────────────────
        try:
            await self._event_stream.append(
                event_type="execution.completed",
                source="ExecutionRuntime",
                payload={
                    "request_id": context.request_id,
                    "worker_type": worker_type,
                    "worker_id": worker.worker_id,
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                    "error": result.error if not result.success else "",
                },
            )
        except Exception as e:
            logger.warning("ExecutionRuntime: event emission failed: %s", e)

        # ── Step 6: Clean up WorkingMemory ───────────────────────────────
        try:
            context.working_memory.clear()
        except Exception as e:
            logger.warning("ExecutionRuntime: WorkingMemory cleanup failed: %s", e)

        # ── Step 7: Record metrics ───────────────────────────────────────
        if not result.success:
            self._total_failures += 1

        result.metadata["worker_type"] = worker_type
        result.metadata["request_id"] = context.request_id

        return result

    def stats(self) -> Dict[str, Any]:
        """Return runtime statistics for observability."""
        return {
            "total_invocations": self._total_invocations,
            "total_failures": self._total_failures,
            "registered_workers": self._registry.list_types(),
        }
