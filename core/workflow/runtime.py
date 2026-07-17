"""
core/workflow/runtime.py — WorkflowRuntime (K2.2)

Coordinates a DAG of ExecutionRuntime invocations.

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.
    KERNEL_ARCHITECTURE_v1.0.md §7.1 — ExecutionRuntime (delegated to).

Design:
    - Interprets WorkflowDefinition at execution time.
    - Invokes workers through ExecutionRuntime (never directly).
    - Tracks per-node status in WorkflowInstance.
    - Handles retries per RetryPolicy.
    - Emits workflow lifecycle events.
    - Returns WorkflowResult — NEVER raises.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.events.event_stream import EventStream, get_event_stream
from core.runtime.execution_context import ExecutionContext
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.cancellation import CancellationToken
from core.runtime.working_memory import WorkingMemory
from core.workers.base import WorkerResult
from core.workflow.definition import (
    NodeStatus,
    RetryPolicy,
    WorkflowDefinition,
    WorkflowNode,
)

logger = logging.getLogger("ocbrain.workflow.runtime")


# ── Workflow Instance ─────────────────────────────────────────────────────────

@dataclass
class WorkflowNodeState:
    """Runtime state for a single workflow node."""
    node_id: str = ""
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[WorkerResult] = None
    attempts: int = 0
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class WorkflowResult:
    """Aggregated result of a workflow execution.

    Attributes:
        success: True if all executed nodes succeeded.
        workflow_id: ID of the workflow definition.
        instance_id: Unique ID for this execution.
        node_results: Per-node results keyed by node_id.
        output: The primary output (from the last executed node).
        error: Error message if workflow failed.
        duration_ms: Total wall-clock duration.
        metadata: Additional result data.
    """
    success: bool = True
    workflow_id: str = ""
    instance_id: str = ""
    node_results: Dict[str, WorkerResult] = field(default_factory=dict)
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Workflow Runtime ──────────────────────────────────────────────────────────

class WorkflowRuntime:
    """Coordinates a DAG of ExecutionRuntime invocations.

    Architecture:
        KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.

    Owns:
        - Workflow creation and lifecycle
        - Execution ordering (DAG traversal)
        - Per-node retry logic
        - Workflow-level events
        - Error branch routing

    Does NOT own:
        - Worker execution (ExecutionRuntime)
        - Governance evaluation (Worker template method)
        - Worker implementation (Worker subclass)

    Contract:
        async def execute(definition, **kwargs) -> WorkflowResult
        Never raises — failures become WorkflowResult(success=False).
    """

    def __init__(
        self,
        execution_runtime: ExecutionRuntime,
        event_stream: Optional[EventStream] = None,
    ) -> None:
        self._execution_runtime = execution_runtime
        self._event_stream = event_stream or get_event_stream()
        self._total_executions: int = 0
        self._total_failures: int = 0
        logger.info("WorkflowRuntime initialized")

    async def execute(
        self,
        definition: WorkflowDefinition,
        *,
        query: str = "",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> WorkflowResult:
        """Execute a workflow definition.

        Architecture:
            KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.
            Failure Containment principle: never raises.

        Lifecycle:
            1. Validate workflow definition
            2. Create instance state
            3. Execute nodes in DAG order starting from entry_node
            4. For each node: invoke via ExecutionRuntime with retry
            5. On failure: route to error_branch if defined
            6. Aggregate results into WorkflowResult
            7. Emit workflow events

        Args:
            definition: The workflow DAG to execute.
            query: The originating query (passed to workers).
            session_id: Session correlation ID.
            metadata: Additional context.
            cancellation_token: For workflow-level cancellation.

        Returns:
            WorkflowResult — always. Never raises.
        """
        start_time = time.time()
        self._total_executions += 1
        instance_id = str(uuid.uuid4())
        cancel_token = cancellation_token or CancellationToken()

        # ── Step 1: Validate ─────────────────────────────────────────────
        errors = definition.validate()
        if errors:
            self._total_failures += 1
            return WorkflowResult(
                success=False,
                workflow_id=definition.workflow_id,
                instance_id=instance_id,
                error=f"Invalid workflow: {'; '.join(errors)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # ── Step 2: Initialize instance state ────────────────────────────
        node_states: Dict[str, WorkflowNodeState] = {
            node.node_id: WorkflowNodeState(node_id=node.node_id)
            for node in definition.nodes
        }
        node_results: Dict[str, WorkerResult] = {}

        # ── Step 3: Emit workflow.started ─────────────────────────────────
        await self._emit_event("workflow.started", {
            "workflow_id": definition.workflow_id,
            "instance_id": instance_id,
            "name": definition.name,
            "entry_node": definition.entry_node,
            "node_count": len(definition.nodes),
        })

        # ── Step 4: Execute DAG from entry_node ──────────────────────────
        try:
            last_result = await self._execute_from(
                definition=definition,
                node_id=definition.entry_node,
                node_states=node_states,
                node_results=node_results,
                query=query,
                session_id=session_id,
                instance_id=instance_id,
                metadata=metadata or {},
                cancel_token=cancel_token,
            )
        except Exception as e:
            # Should never happen — _execute_from contains failures.
            # But if it does, we contain it here.
            logger.error("WorkflowRuntime: unexpected error: %s", e, exc_info=True)
            self._total_failures += 1
            return WorkflowResult(
                success=False,
                workflow_id=definition.workflow_id,
                instance_id=instance_id,
                node_results=node_results,
                error=f"Unexpected workflow error: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # ── Step 5: Aggregate result ─────────────────────────────────────
        # Workflow success is defined by whether execution terminated along
        # a successful path -- i.e. the outcome of `last_result`, which is
        # whatever _execute_from actually returned last (it follows
        # error_branch redirection on failure, so a node that failed but
        # was recovered via its error_branch surfaces here as a success --
        # that redirection is the entire point of error_branch, and a
        # workflow that recovered must not be reported as failed).
        #
        # This also correctly handles the cancellation case: a pre-
        # cancelled token makes _execute_from return
        # WorkerResult(success=False, error="Workflow cancelled") before
        # touching node_states/node_results at all, so those two
        # collections stay empty/PENDING -- checking them (as an earlier
        # version of this method did) reports success=True for a workflow
        # that never ran. Checking last_result.success avoids that: an
        # empty node_results with a failed last_result correctly reports
        # failure.
        success = last_result.success if last_result is not None else True
        duration_ms = (time.time() - start_time) * 1000

        if not success:
            self._total_failures += 1

        result = WorkflowResult(
            success=success,
            workflow_id=definition.workflow_id,
            instance_id=instance_id,
            node_results=node_results,
            output=last_result.output if last_result else None,
            error=last_result.error if last_result and not last_result.success else "",
            duration_ms=duration_ms,
            metadata={"query": query, "session_id": session_id},
        )

        # ── Step 6: Emit workflow.completed ──────────────────────────────
        await self._emit_event("workflow.completed", {
            "workflow_id": definition.workflow_id,
            "instance_id": instance_id,
            "success": success,
            "duration_ms": duration_ms,
            "nodes_executed": len(node_results),
        })

        return result

    async def _execute_from(
        self,
        definition: WorkflowDefinition,
        node_id: str,
        node_states: Dict[str, WorkflowNodeState],
        node_results: Dict[str, WorkerResult],
        query: str,
        session_id: str,
        instance_id: str,
        metadata: Dict[str, Any],
        cancel_token: CancellationToken,
    ) -> Optional[WorkerResult]:
        """Execute a node and its successors recursively.

        Returns the result of the last executed node.
        """
        if cancel_token.is_cancelled:
            return WorkerResult(success=False, error="Workflow cancelled")

        node = definition.get_node(node_id)
        if node is None:
            return WorkerResult(success=False, error=f"Node '{node_id}' not found")

        state = node_states[node_id]
        if state.status != NodeStatus.PENDING:
            # Already executed (possible in DAGs with merging paths)
            return node_results.get(node_id)

        # ── Execute this node with retry ─────────────────────────────────
        state.status = NodeStatus.RUNNING
        state.started_at = time.time()

        result = await self._execute_node_with_retry(
            node=node,
            query=query,
            session_id=session_id,
            instance_id=instance_id,
            metadata=metadata,
            cancel_token=cancel_token,
            node_states=node_states,
        )

        state.result = result
        state.completed_at = time.time()
        node_results[node_id] = result

        if result.success:
            state.status = NodeStatus.COMPLETED
        else:
            state.status = NodeStatus.FAILED
            # Route to error branch if defined
            if node.error_branch:
                logger.info("WorkflowRuntime: node '%s' failed, routing to "
                            "error_branch '%s'", node_id, node.error_branch)
                return await self._execute_from(
                    definition, node.error_branch, node_states,
                    node_results, query, session_id, instance_id,
                    metadata, cancel_token,
                )
            return result

        # ── Execute successors ───────────────────────────────────────────
        successors = definition.get_successors(node_id)
        if not successors:
            return result

        last_result = result
        for succ_id in successors:
            last_result = await self._execute_from(
                definition, succ_id, node_states, node_results,
                query, session_id, instance_id, metadata, cancel_token,
            )
        return last_result

    async def _execute_node_with_retry(
        self,
        node: WorkflowNode,
        query: str,
        session_id: str,
        instance_id: str,
        metadata: Dict[str, Any],
        cancel_token: CancellationToken,
        node_states: Dict[str, WorkflowNodeState],
    ) -> WorkerResult:
        """Execute a single node with retry logic."""
        policy = node.retry_policy
        state = node_states[node.node_id]
        last_result = None

        for attempt in range(1 + policy.max_retries):
            state.attempts = attempt + 1

            if cancel_token.is_cancelled:
                return WorkerResult(success=False, error="Cancelled during retry")

            # Build context for this node
            ctx = ExecutionContext(
                session_id=session_id,
                workflow_id=instance_id,
                metadata={
                    "query": query,
                    "node_id": node.node_id,
                    "node_config": node.config,
                    "attempt": attempt + 1,
                    **metadata,
                },
                governance_state={"recursion_depth": 0},
                cancellation_token=cancel_token,
            )

            result = await self._execution_runtime.invoke(
                worker_type=node.worker_type,
                context=ctx,
            )
            last_result = result

            if result.success:
                return result

            # Check if retryable
            if attempt < policy.max_retries:
                if policy.retryable_errors:
                    if not any(err in result.error for err in policy.retryable_errors):
                        break  # Not retryable
                # Backoff
                delay = min(
                    policy.backoff_seconds * (policy.backoff_multiplier ** attempt),
                    policy.max_backoff_seconds,
                )
                logger.info("WorkflowRuntime: node '%s' attempt %d failed, "
                            "retrying in %.1fs: %s",
                            node.node_id, attempt + 1, delay, result.error)
                await asyncio.sleep(delay)

        return last_result or WorkerResult(success=False, error="No attempts made")

    async def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit a workflow lifecycle event. Failures are logged, never raised."""
        try:
            await self._event_stream.append(
                event_type=event_type,
                source="WorkflowRuntime",
                payload=payload,
            )
        except Exception as e:
            logger.warning("WorkflowRuntime: event emission failed: %s", e)

    def stats(self) -> Dict[str, Any]:
        """Return runtime statistics."""
        return {
            "total_executions": self._total_executions,
            "total_failures": self._total_failures,
        }
