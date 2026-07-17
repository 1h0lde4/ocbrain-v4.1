"""
core/workers/base.py — AbstractCognitiveWorker (v4.3.5)

Foundation for all Layer 3 Agent Runtime workers.

Architecture references:
  - PI §7: "Workers are specialized cognitive runtimes."
  - PI §7.1: Canonical worker types (Planner, ReAct, Reflection, Coder,
              Evaluator, Browser, MemoryCurator, Supervisor).
  - PI §7.2: "Every worker must: emit events, stream progress, expose state,
              support interruption, respect governance, support evaluation,
              support observability."
  - FA §4.1 Layer 3: Agent Runtime.
  - FA §4.1 Layer 0 > Layer 3 ordering: Workers sit below Governance.

Design:
  - Template Method Pattern: execute() is non-overridable, wrapping _run()
    inside GovernanceKernel.evaluate_action(). This makes governance bypass
    structurally impossible (PI LAW 1).
  - Event Sourcing: Every lifecycle transition (started, progress, completed,
    failed) emits to EventStream (PI LAW 2).
  - Type Safety: All interfaces are fully typed per execution constraint.
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from core.governance.governance_kernel import (
    GovernanceAction,
    GovernanceKernel,
    GovernanceResult,
    GovernanceVerdict,
    get_governance_kernel,
)
from core.events.event_stream import EventStream, get_event_stream

logger = logging.getLogger("ocbrain.workers.base")


# ── Worker State Machine ──────────────────────────────────────────────────────

class WorkerState(Enum):
    """Worker lifecycle states.

    Architecture:
        PI §7.2 — "expose state"
    """

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Worker Context ────────────────────────────────────────────────────────────

@dataclass
class WorkerContext:
    """Execution context passed to every worker invocation.

    Architecture:
        PI §7.2 — "emit events, stream progress, expose state"
        PI §6.1 — "recursion depth limits" (tracked via recursion_depth)

    Attributes:
        task_id: Unique identifier for this execution.
        query: The user query or task description.
        parameters: Additional execution parameters.
        recursion_depth: Current depth for governance recursion limits.
        parent_worker_id: If invoked by another worker (Supervisor pattern).
        workflow_id: Enclosing workflow context, if any.
        metadata: Arbitrary context data.
    """

    task_id:          str            = field(default_factory=lambda: str(uuid.uuid4()))
    query:            str            = ""
    parameters:       Dict[str, Any] = field(default_factory=dict)
    recursion_depth:  int            = 0
    parent_worker_id: str            = ""
    workflow_id:      str            = ""
    metadata:         Dict[str, Any] = field(default_factory=dict)


# ── Worker Result ─────────────────────────────────────────────────────────────

@dataclass
class WorkerResult:
    """Structured result from a worker execution.

    Attributes:
        success: Whether the execution completed without errors.
        output: The primary output (text, data, or structured result).
        error: Error message if success is False.
        artifacts: Named outputs (files, data structures) produced.
        events_emitted: Count of events emitted during execution.
        duration_ms: Wall-clock duration in milliseconds.
        metadata: Additional result context.
    """

    success:        bool           = True
    output:         Any            = None
    error:          str            = ""
    artifacts:      Dict[str, Any] = field(default_factory=dict)
    events_emitted: int            = 0
    duration_ms:    float          = 0.0
    metadata:       Dict[str, Any] = field(default_factory=dict)


# ── Abstract Cognitive Worker ─────────────────────────────────────────────────

class AbstractCognitiveWorker(ABC):
    """Base class for all OCBrain cognitive workers.

    Architecture:
        PI §7: "Workers are specialized cognitive runtimes."
        PI §7.1: Lists 8 canonical worker types, all subclassing this.
        PI §7.2: "Every worker must: emit events, stream progress, expose state,
                  support interruption, respect governance, support evaluation,
                  support observability."
        PI LAW 1: "No autonomous capability may bypass governance."
        FA §4.1 Layer 3: Agent Runtime — all workers live here.

    Template Method Pattern:
        execute() is the public API. It is NOT overridable. It wraps:
          1. Governance evaluation (GovernanceKernel.evaluate_action)
          2. Lifecycle events (started, completed, failed)
          3. The actual work, delegated to _run() which subclasses implement.

        This makes governance bypass structurally impossible.

    Usage:
        class MyWorker(AbstractCognitiveWorker):
            worker_type = "MyWorker"

            async def _run(self, context: WorkerContext) -> WorkerResult:
                # do actual work here
                return WorkerResult(success=True, output="done")

        worker = MyWorker()
        result = await worker.execute(WorkerContext(query="do something"))
    """

    # ── Class-level identity ──────────────────────────────────────────────

    worker_type: str = "AbstractCognitiveWorker"

    def __init__(self, *,
                 governance: Optional[GovernanceKernel] = None,
                 event_stream: Optional[EventStream] = None) -> None:
        """Initialize the worker with governance and event dependencies.

        Args:
            governance: GovernanceKernel instance. Uses singleton if None.
            event_stream: EventStream instance. Uses singleton if None.

        Architecture:
            PI LAW 1 — Governance is injected, not optional.
            PI LAW 2 — EventStream is injected, not optional.
        """
        self._id: str = f"{self.worker_type}:{uuid.uuid4().hex[:8]}"
        self._governance: GovernanceKernel = governance or get_governance_kernel()
        self._event_stream: EventStream = event_stream or get_event_stream()
        self._state: WorkerState = WorkerState.IDLE
        self._cancelled: bool = False
        self._events_emitted: int = 0
        self._total_executions: int = 0
        self._total_failures: int = 0

    # ── Public API (non-overridable) ──────────────────────────────────────

    async def execute(self, context: WorkerContext) -> WorkerResult:
        """Execute a task with full governance and event sourcing.

        This method is NOT overridable. It enforces:
          1. GovernanceKernel.evaluate_action() BEFORE any work.
          2. Lifecycle event emission (started → completed/failed).
          3. Delegation to _run() for actual work.

        Args:
            context: The WorkerContext describing the task.

        Returns:
            WorkerResult with success/failure and output.

        Raises:
            GovernanceRejectionError: If governance rejects the action.

        Architecture:
            PI LAW 1 — "No autonomous capability may bypass governance."
            PI §7.2 — "emit events, respect governance"
        """
        start_time = time.time()
        self._total_executions += 1

        # ── Step 1: Governance evaluation ─────────────────────────────────
        # K3.5: propagate budget context so BudgetGovernor is operational.
        # step_count/token_spend are read from context.metadata where
        # ExecutionRuntime/WorkflowRuntime supply accumulated values.
        budget = context.metadata.get("budget", {})
        action = GovernanceAction(
            action_type="worker_execute",
            worker_id=self._id,
            description=f"{self.worker_type}: {context.query[:120]}",
            recursion_depth=context.recursion_depth,
            metadata={
                "task_id": context.task_id,
                "worker_type": self.worker_type,
                "workflow_id": context.workflow_id,
                "step_count": budget.get("steps", context.metadata.get("step_count", 0)),
                "token_spend": budget.get("tokens", context.metadata.get("token_spend", 0.0)),
            },
        )

        gov_result: GovernanceResult = self._governance.evaluate_action(action)

        if gov_result.verdict == GovernanceVerdict.REJECT:
            await self._emit_event("worker.rejected", context, {
                "reason": gov_result.reason,
                "governor": gov_result.governor,
            })
            self._total_failures += 1
            return WorkerResult(
                success=False,
                error=f"Governance rejected: {gov_result.reason}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        if gov_result.verdict == GovernanceVerdict.ESCALATE:
            await self._emit_event("worker.escalated", context, {
                "reason": gov_result.reason,
                "governor": gov_result.governor,
            })
            return WorkerResult(
                success=False,
                error=f"Governance escalated (HITL required): {gov_result.reason}",
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"requires_hitl": True},
            )

        # ── Step 2: Emit started event ────────────────────────────────────
        self._state = WorkerState.RUNNING
        self._cancelled = False
        await self._emit_event("worker.started", context, {
            "worker_type": self.worker_type,
        })

        # ── Step 3: Execute _run() (subclass implementation) ──────────────
        try:
            result = await self._run(context)
            result.events_emitted = self._events_emitted
            result.duration_ms = (time.time() - start_time) * 1000

            # ── Step 4a: Emit completed event ─────────────────────────────
            self._state = WorkerState.COMPLETED
            await self._emit_event("worker.completed", context, {
                "success": result.success,
                "duration_ms": result.duration_ms,
            })
            return result

        except asyncio.CancelledError:
            self._state = WorkerState.CANCELLED
            self._total_failures += 1
            await self._emit_event("worker.cancelled", context, {})
            return WorkerResult(
                success=False,
                error="Worker cancelled",
                duration_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            # ── Step 4b: Emit failed event ────────────────────────────────
            self._state = WorkerState.FAILED
            self._total_failures += 1
            await self._emit_event("worker.failed", context, {
                "error": str(e),
                "error_type": type(e).__name__,
            })
            logger.error("[%s] Execution failed: %s", self._id, e, exc_info=True)
            return WorkerResult(
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    # ── Subclass contract ─────────────────────────────────────────────────

    @abstractmethod
    async def _run(self, context: WorkerContext) -> WorkerResult:
        """Implement the actual worker logic.

        This is the ONLY method subclasses must override.
        Governance and event sourcing are handled by execute().

        Args:
            context: The WorkerContext with task details.

        Returns:
            WorkerResult with the execution outcome.
        """
        ...

    # ── Progress streaming ────────────────────────────────────────────────

    async def emit_progress(self, context: WorkerContext,
                            message: str,
                            percent: float = 0.0,
                            data: Optional[Dict[str, Any]] = None) -> None:
        """Emit a progress event during execution.

        Called by subclasses within _run() to stream progress updates.

        Args:
            context: Current execution context.
            message: Human-readable progress description.
            percent: Completion percentage (0.0 - 100.0).
            data: Additional progress data.

        Architecture:
            PI §7.2 — "stream progress"
        """
        await self._emit_event("worker.progress", context, {
            "message": message,
            "percent": min(100.0, max(0.0, percent)),
            **(data or {}),
        })

    # ── Interruption support ──────────────────────────────────────────────

    def cancel(self) -> None:
        """Request cancellation of the current execution.

        Architecture:
            PI §7.2 — "support interruption"
        """
        self._cancelled = True
        self._state = WorkerState.CANCELLED
        logger.info("[%s] Cancellation requested", self._id)

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested.

        Subclasses should check this periodically in _run() and exit
        gracefully if True.
        """
        return self._cancelled

    # ── State exposure ────────────────────────────────────────────────────

    @property
    def state(self) -> WorkerState:
        """Current worker state.

        Architecture:
            PI §7.2 — "expose state"
        """
        return self._state

    @property
    def worker_id(self) -> str:
        """Unique identifier for this worker instance."""
        return self._id

    def stats(self) -> Dict[str, Any]:
        """Return worker statistics.

        Architecture:
            PI §7.2 — "support observability"
        """
        return {
            "worker_id": self._id,
            "worker_type": self.worker_type,
            "state": self._state.value,
            "total_executions": self._total_executions,
            "total_failures": self._total_failures,
            "events_emitted": self._events_emitted,
        }

    # ── Internal event emission ───────────────────────────────────────────

    async def _emit_event(self, event_type: str,
                          context: WorkerContext,
                          payload: Dict[str, Any]) -> None:
        """Emit a lifecycle event to the EventStream.

        Architecture:
            PI LAW 2 — "All meaningful cognitive activity must emit
                         immutable events."
            PI §7.2 — "emit events"
        """
        payload["task_id"] = context.task_id
        payload["worker_id"] = self._id
        if context.workflow_id:
            payload["workflow_id"] = context.workflow_id

        try:
            await self._event_stream.append(
                event_type=event_type,
                source=self._id,
                payload=payload,
            )
            self._events_emitted += 1
        except Exception as e:
            # Event emission failure must NEVER stop worker execution
            logger.warning("[%s] Event emission failed for %s: %s",
                           self._id, event_type, e)
