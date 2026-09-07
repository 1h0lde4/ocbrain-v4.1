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
from core.runtime.execution_budget import ExecutionBudget
from core.runtime.execution_graph import ExecutionStatus
from core.runtime.execution_graph import execution_registry
from core.runtime.progress import ProgressMonitor
from core.runtime.watchdog import GraphExecutionWatchdog
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
    """Runtime state for a single workflow node.

    attempt_id (Kernel Blocker B... resolution scope note: this is
    Blocker A's I3/I6, not Blocker B): a stable, opaque identifier for the
    current execution attempt, distinct from `attempts` (a bare retry
    count). Per I3's contract ("opaque, persistent, location-independent
    identifier with stable equality semantics"), a counter alone cannot
    serve this role -- "attempt #2" before a process restart and "attempt
    #2" after one are not distinguishable by count alone. Regenerated
    fresh on each retry, alongside (not replacing) `attempts`, which
    keeps its existing meaning and existing call sites unchanged.
    """
    node_id: str = ""
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[WorkerResult] = None
    attempts: int = 0
    attempt_id: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Checkpoint-safe serialization (DEBT-003, ADR-KERNEL-03).

        NodeStatus is a plain Enum (not str-subclassed, unlike
        watchdog_decision.WatchdogVerdict/CancelReason) -- .value is
        extracted explicitly rather than relying on json.dumps's
        default=str fallback, which would instead produce the unparseable
        "NodeStatus.PENDING" rather than "pending".
        """
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "result": _worker_result_to_dict(self.result),
            "attempts": self.attempts,
            "attempt_id": self.attempt_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowNodeState":
        return cls(
            node_id=data.get("node_id", ""),
            status=NodeStatus(data.get("status", NodeStatus.PENDING.value)),
            result=_worker_result_from_dict(data.get("result")),
            attempts=data.get("attempts", 0),
            attempt_id=data.get("attempt_id", ""),
            started_at=data.get("started_at", 0.0),
            completed_at=data.get("completed_at", 0.0),
        )


def _worker_result_to_dict(result: Optional[WorkerResult]) -> Optional[Dict[str, Any]]:
    if result is None:
        return None
    return {
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "artifacts": result.artifacts,
        "events_emitted": result.events_emitted,
        "duration_ms": result.duration_ms,
        "metadata": result.metadata,
        # execution_detail (K4.4's structured ExecutionOutcome) is
        # deliberately NOT restored on resume -- see ADR-KERNEL-03 "What
        # was explicitly not done". A resumed node's cached result reports
        # success/output/error/artifacts/metadata faithfully; the original
        # attempt's detailed failure classification (FailureType, provider,
        # watchdog_verdict, etc.) is not reconstructed. Round-tripping it
        # would mean either serializing the whole nested ExecutionOutcome
        # (a second, parallel checkpoint schema to keep in sync with that
        # module) or reconstructing it partially and risking a
        # not-quite-right object being mistaken for the original --
        # returning None here is the honest choice, not a silent gap.
    }


def _worker_result_from_dict(data: Optional[Dict[str, Any]]) -> Optional[WorkerResult]:
    if data is None:
        return None
    return WorkerResult(
        success=data.get("success", False),
        output=data.get("output"),
        error=data.get("error", ""),
        artifacts=data.get("artifacts") or {},
        events_emitted=data.get("events_emitted", 0),
        duration_ms=data.get("duration_ms", 0.0),
        metadata=data.get("metadata") or {},
    )


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

    @staticmethod
    def default_budget_for(query: str) -> ExecutionBudget:
        """The ExecutionBudget used for a workflow execution when the
        caller doesn't supply one via metadata["execution_budget"].

        Extracted as its own method (previously inline in execute()) so
        the absolute_ceiling_s / hard_ceiling_s relationship is directly
        unit-testable — see tests/test_workflow_runtime.py
        TestWorkflowRuntimeWatchdogReconciliation. absolute_ceiling_s must
        exceed hard_ceiling_s, not equal it: ExecutionBudget.grant_extension()
        clamps to (absolute_ceiling_s - hard_ceiling_s), so equal values
        silently make every extension request a no-op regardless of
        max_extension_s — a real bug found while tracing DEBT-016
        (ADR-KERNEL-02); this method is the fix.
        """
        word_count = len(query.split())
        hard_ceiling = 600.0 if word_count >= 500 else 300.0
        max_extension = 240.0
        return ExecutionBudget(
            startup_deadline_s=10.0,
            progress_deadline_s=45.0,
            hard_ceiling_s=hard_ceiling,
            absolute_ceiling_s=hard_ceiling + max_extension,
            max_extension_s=max_extension,
        )

    async def execute(
        self,
        definition: WorkflowDefinition,
        *,
        query: str = "",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> WorkflowResult:
        """Execute a workflow definition from the start.

        Architecture:
            KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.
            Failure Containment principle: never raises.

        Args:
            definition: The workflow DAG to execute.
            query: The originating query (passed to workers).
            session_id: Session correlation ID.
            metadata: Additional context.
            cancellation_token: For workflow-level cancellation.

        Returns:
            WorkflowResult — always. Never raises.
        """
        instance_id = str(uuid.uuid4())
        node_states: Dict[str, WorkflowNodeState] = {
            node.node_id: WorkflowNodeState(node_id=node.node_id)
            for node in definition.nodes
        }
        return await self._run(
            definition, instance_id, node_states, {},
            query=query, session_id=session_id, metadata=metadata,
            cancellation_token=cancellation_token,
        )

    async def resume(
        self,
        definition: WorkflowDefinition,
        instance_id: str,
        *,
        query: str = "",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> WorkflowResult:
        """Resume a previously-interrupted execution from its last checkpoint.

        DEBT-003 / ADR-KERNEL-03: WorkflowRuntime.execute() checkpoints
        node_states after every node boundary (via _save_checkpoint, called
        from _execute_from). This loads the most recent checkpoint for
        `instance_id`, reconstructs node_states/node_results from it, and
        re-enters the same DAG traversal _run()/_execute_from() already
        use for a fresh execute() call -- already-COMPLETED/FAILED nodes
        are skipped (their cached result is reused, not re-run) purely as
        a consequence of _execute_from's existing
        `if state.status != PENDING: return cached result` check; nothing
        node-traversal-specific needed to be added for that to work.

        Safety-critical exception: a node whose last known status was
        RUNNING (or the not-currently-reachable CANCELLED) is reset to
        PENDING and re-executed from scratch, never resumed "in place".
        Whether that node's underlying work actually finished before the
        crash is unknowable from here, and this project's Verification
        principle applies directly: a status of RUNNING is not evidence of
        completion, so it must not be treated as one.

        The ExecutionBudget is NOT restored from the checkpoint -- resume
        always starts a fresh budget via default_budget_for(). Preserving
        "remaining time across an unknown period of downtime" is
        ambiguous (too strict if the process was down 2 seconds, too
        lenient if it was down 2 hours) and is deliberately not attempted
        here; the caller may still pass their own
        metadata["execution_budget"], same as execute().

        Known, accepted limitation, not a silent gap: re-executing a node
        that already produced an external side effect before the crash
        (e.g. sent an email, wrote a file) will repeat that side effect.
        General side-effect idempotency is DEBT-015 sub-item (7),
        explicitly deferred, proposed-only future architecture -- DEBT-003
        solves durability of *state*, not idempotency of *effects*.

        Returns:
            WorkflowResult with success=False and a descriptive error (not
            an exception) if no checkpoint exists for `instance_id`, or if
            the checkpoint's workflow_id doesn't match `definition`.
        """
        checkpoint_name = self._checkpoint_name(instance_id)
        checkpoint = await self._event_stream.get_checkpoint(checkpoint_name)
        if checkpoint is None:
            return WorkflowResult(
                success=False, workflow_id=definition.workflow_id,
                instance_id=instance_id,
                error=f"No checkpoint found for instance '{instance_id}' -- cannot resume",
            )

        payload = checkpoint.payload or {}
        checkpointed_workflow_id = payload.get("workflow_id")
        if checkpointed_workflow_id != definition.workflow_id:
            return WorkflowResult(
                success=False, workflow_id=definition.workflow_id,
                instance_id=instance_id,
                error=(f"Checkpoint workflow_id mismatch: checkpoint is for "
                       f"'{checkpointed_workflow_id}', definition given is "
                       f"'{definition.workflow_id}'"),
            )

        node_states: Dict[str, WorkflowNodeState] = {}
        node_results: Dict[str, WorkerResult] = {}
        for node_id, state_data in payload.get("node_states", {}).items():
            state = WorkflowNodeState.from_dict(state_data)
            if state.status in (NodeStatus.RUNNING, NodeStatus.CANCELLED):
                state.status = NodeStatus.PENDING
                state.result = None
            node_states[node_id] = state
            if state.result is not None:
                node_results[node_id] = state.result
        # A node present in `definition` but absent from the checkpoint
        # (e.g. the definition was extended since the crash) starts fresh.
        for node in definition.nodes:
            if node.node_id not in node_states:
                node_states[node.node_id] = WorkflowNodeState(node_id=node.node_id)

        return await self._run(
            definition, instance_id, node_states, node_results,
            query=query, session_id=session_id, metadata=metadata,
            cancellation_token=cancellation_token,
            resumed_from=checkpoint_name,
        )

    def _checkpoint_name(self, instance_id: str) -> str:
        return f"workflow:{instance_id}"

    async def _save_checkpoint(
        self, instance_id: str, workflow_id: str,
        node_states: Dict[str, WorkflowNodeState],
    ) -> None:
        """Best-effort durable checkpoint after a node boundary (DEBT-003).

        Never raises: a checkpoint-write failure must not take down a
        workflow that is otherwise executing correctly. This mirrors
        _emit_event's existing failure-containment pattern in this same
        class, not a new convention.
        """
        try:
            await self._event_stream.create_checkpoint(
                self._checkpoint_name(instance_id),
                payload={
                    "workflow_id": workflow_id,
                    "instance_id": instance_id,
                    "node_states": {nid: s.to_dict() for nid, s in node_states.items()},
                    "saved_at": time.time(),
                },
            )
        except Exception as e:
            logger.warning("WorkflowRuntime: checkpoint write failed for "
                            "instance '%s': %s", instance_id, e)

    async def _run(
        self,
        definition: WorkflowDefinition,
        instance_id: str,
        node_states: Dict[str, WorkflowNodeState],
        node_results: Dict[str, WorkerResult],
        *,
        query: str = "",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        resumed_from: Optional[str] = None,
    ) -> WorkflowResult:
        """Shared execution engine behind both execute() and resume().

        Lifecycle:
            1. Validate workflow definition
            2. Build/seed graph + watchdog for this instance
            3. Emit workflow.started or workflow.resumed
            4. Execute nodes in DAG order starting from entry_node
               (already-COMPLETED/FAILED nodes in node_states are skipped
               by _execute_from's own PENDING check -- see resume()'s
               docstring)
            5. Aggregate results into WorkflowResult
            6. Emit workflow.completed

        Returns:
            WorkflowResult — always. Never raises.
        """
        start_time = time.time()
        self._total_executions += 1
        cancel_token = cancellation_token or CancellationToken()
        execution_id = (metadata or {}).get("execution_id") or instance_id
        graph = execution_registry.create(
            execution_id, title=(metadata or {}).get("execution_title") or definition.name
        )
        execution_registry.attach_event_stream(self._event_stream)
        monitor = ProgressMonitor(graph, self._event_stream)
        budget = (metadata or {}).get("execution_budget")
        if not isinstance(budget, ExecutionBudget):
            budget = self.default_budget_for(query)
        watchdog = GraphExecutionWatchdog(graph, budget, cancel_token, monitor)
        await monitor.record_status(
            graph.root.node_id, ExecutionStatus.RUNNING,
            summary="Execution resumed" if resumed_from else "Execution started",
            current_action="Preparing execution",
        )
        for workflow_node in definition.nodes:
            await graph.add_node(
                node_id=workflow_node.node_id,
                parent_id=graph.root.node_id,
                operation_type="worker",
                title=workflow_node.config.get("title", workflow_node.worker_type),
            )
        if resumed_from:
            # Seed the fresh ExecutionGraph (execution-inspection UI) so a
            # resumed run doesn't misleadingly show every node as PENDING
            # the instant it starts -- graph state here is purely a
            # reporting surface, node_states above (not this) is what
            # _execute_from actually reads to decide what to skip.
            for node_id, state in node_states.items():
                if state.status == NodeStatus.COMPLETED:
                    await monitor.record_completion(node_id, summary="Restored from checkpoint")
                elif state.status == NodeStatus.FAILED:
                    await monitor.record_failure(node_id, (state.result.error if state.result else "") or "Restored from checkpoint (failed)")
        watchdog.start()

        # ── Step 1: Validate ─────────────────────────────────────────────
        errors = definition.validate()
        if errors:
            self._total_failures += 1
            await watchdog.stop()
            return WorkflowResult(
                success=False,
                workflow_id=definition.workflow_id,
                instance_id=instance_id,
                error=f"Invalid workflow: {'; '.join(errors)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # ── Step 2: Emit workflow.started / workflow.resumed ─────────────
        await self._emit_event("workflow.resumed" if resumed_from else "workflow.started", {
            "workflow_id": definition.workflow_id,
            "instance_id": instance_id,
            "name": definition.name,
            "entry_node": definition.entry_node,
            "node_count": len(definition.nodes),
            **({"checkpoint": resumed_from,
                "nodes_already_done": sum(
                    1 for s in node_states.values()
                    if s.status in (NodeStatus.COMPLETED, NodeStatus.FAILED))}
               if resumed_from else {}),
        })

        # ── Step 3: Execute DAG from entry_node ──────────────────────────
        run_metadata = {
            **(metadata or {}), "instance_id": instance_id,
            "execution_id": execution_id,
        }
        try:
            last_result = await self._execute_from(
                definition=definition,
                node_id=definition.entry_node,
                node_states=node_states,
                node_results=node_results,
                query=query,
                session_id=session_id,
                instance_id=instance_id,
                metadata=run_metadata,
                cancel_token=cancel_token,
            )
        except Exception as e:
            # Should never happen — _execute_from contains failures.
            # But if it does, we contain it here.
            logger.error("WorkflowRuntime: unexpected error: %s", e, exc_info=True)
            self._total_failures += 1
            await watchdog.stop()
            return WorkflowResult(
                success=False,
                workflow_id=definition.workflow_id,
                instance_id=instance_id,
                node_results=node_results,
                error=f"Unexpected workflow error: {e}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # ── Step 4: Aggregate result ─────────────────────────────────────
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

        await monitor.record_status(
            graph.root.node_id,
            ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
            summary="Execution completed" if success else "Execution failed",
            current_action="",
        )
        await self._emit_event(
            "execution.completed" if success else "execution.failed",
            {
                "execution_id": execution_id,
                "node_id": graph.root.node_id,
                "status": "completed" if success else "failed",
                "summary": "Execution completed" if success else "Execution failed",
            },
        )
        await watchdog.stop()

        result = WorkflowResult(
            success=success,
            workflow_id=definition.workflow_id,
            instance_id=instance_id,
            node_results=node_results,
            output=last_result.output if last_result else None,
            error=last_result.error if last_result and not last_result.success else "",
            duration_ms=duration_ms,
            metadata={"query": query, "session_id": session_id,
                      "execution_id": execution_id,
                      "budget": budget},
        )

        # ── Step 5: Emit workflow.completed ──────────────────────────────
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
        visited: Optional[set] = None,
    ) -> Optional[WorkerResult]:
        """Execute a node and its successors recursively.

        `visited` tracks which nodes THIS traversal (this one top-level
        call to _run(), including everything it recurses into) has already
        passed through -- defaults to a fresh empty set on the outermost
        call. This is a different question from `state.status !=
        PENDING`, and conflating them was a real bug (found by this
        session's own tests, DEBT-003 / ADR-KERNEL-03): a diamond-shaped
        DAG (A -> B, A -> C, B -> D, C -> D) correctly reaches D twice in
        one traversal -- once via B (where D actually executes and then
        recurses into D's own successors) and once via C (where D must
        short-circuit, since D's successors were already reached via the
        B path, and running them again would be wrong). But
        checkpoint-restored resume (resume(), below) starts some nodes
        already marked COMPLETED without this traversal ever having
        visited them -- their `state.status != PENDING` alone looks
        identical to "already handled this traversal," so the old code
        returned the cached result and stopped, silently never visiting
        that node's successors at all. `visited` disambiguates the two: a
        node not yet in `visited` gets its successors walked regardless of
        whether it needed fresh execution or was already done: only a
        SECOND encounter within the same traversal short-circuits.

        Returns the result of the last executed node.
        """
        if visited is None:
            visited = set()
        if cancel_token.is_cancelled:
            return WorkerResult(success=False, error="Workflow cancelled")

        node = definition.get_node(node_id)
        if node is None:
            return WorkerResult(success=False, error=f"Node '{node_id}' not found")

        state = node_states[node_id]
        first_visit_this_traversal = node_id not in visited
        visited.add(node_id)

        if state.status != NodeStatus.PENDING:
            if not first_visit_this_traversal:
                # Genuine diamond-merge revisit: successors already
                # reached via whichever path got here first.
                return node_results.get(node_id)
            # First time this traversal has reached this node, but it's
            # already done -- a checkpoint-restored node (DEBT-003). Reuse
            # its cached result, but still continue into its successors,
            # exactly as freshly completing it would.
            cached = node_results.get(node_id)
            if state.status == NodeStatus.FAILED:
                if node.error_branch:
                    return await self._execute_from(
                        definition, node.error_branch, node_states, node_results,
                        query, session_id, instance_id, metadata, cancel_token, visited,
                    )
                return cached
            return await self._continue_to_successors(
                definition, node_id, cached, node_states, node_results,
                query, session_id, instance_id, metadata, cancel_token, visited,
            )

        # ── Execute this node with retry ─────────────────────────────────
        state.status = NodeStatus.RUNNING
        state.started_at = time.time()
        execution_id = metadata.get("execution_id", instance_id)
        graph = execution_registry.get(execution_id)
        if graph is not None:
            monitor = ProgressMonitor(graph, self._event_stream)
            await monitor.record_status(
                node_id, ExecutionStatus.RUNNING,
                summary=f"Running {node.worker_type}",
                current_action=f"Executing {node.worker_type}",
            )

        result = await self._execute_node_with_retry(
            node=node,
            query=query,
            session_id=session_id,
            workflow_id=definition.workflow_id,
            metadata=metadata,
            cancel_token=cancel_token,
            node_states=node_states,
        )

        state.result = result
        state.completed_at = time.time()
        node_results[node_id] = result

        if result.success:
            state.status = NodeStatus.COMPLETED
            if graph is not None:
                await monitor.record_completion(
                    node_id, summary=f"{node.worker_type} completed"
                )
            # DEBT-003 / ADR-KERNEL-03: durable checkpoint at this node
            # boundary, after status is finalized but before recursing
            # into successors, so a crash during the *next* node still
            # leaves this one correctly recorded as done.
            await self._save_checkpoint(instance_id, definition.workflow_id, node_states)
        else:
            state.status = NodeStatus.FAILED
            if graph is not None:
                await monitor.record_failure(node_id, result.error or "Execution failed")
            await self._save_checkpoint(instance_id, definition.workflow_id, node_states)
            # Route to error branch if defined
            if node.error_branch:
                logger.info("WorkflowRuntime: node '%s' failed, routing to "
                            "error_branch '%s'", node_id, node.error_branch)
                return await self._execute_from(
                    definition, node.error_branch, node_states,
                    node_results, query, session_id, instance_id,
                    metadata, cancel_token, visited,
                )
            return result

        return await self._continue_to_successors(
            definition, node_id, result, node_states, node_results,
            query, session_id, instance_id, metadata, cancel_token, visited,
        )

    async def _continue_to_successors(
        self,
        definition: WorkflowDefinition,
        node_id: str,
        result: Optional[WorkerResult],
        node_states: Dict[str, WorkflowNodeState],
        node_results: Dict[str, WorkerResult],
        query: str,
        session_id: str,
        instance_id: str,
        metadata: Dict[str, Any],
        cancel_token: CancellationToken,
        visited: set,
    ) -> Optional[WorkerResult]:
        """Shared by both `_execute_from` exit paths that need to keep
        walking the DAG: a node that just now completed, and a node that
        was already COMPLETED (checkpoint-restored) on its first visit
        this traversal. `result` is returned unchanged if there are no
        successors, matching both callers' prior inline behavior."""
        successors = definition.get_successors(node_id)
        if not successors:
            return result

        last_result = result
        for succ_id in successors:
            last_result = await self._execute_from(
                definition, succ_id, node_states, node_results,
                query, session_id, instance_id, metadata, cancel_token, visited,
            )
        return last_result

    async def _execute_node_with_retry(
        self,
        node: WorkflowNode,
        query: str,
        session_id: str,
        workflow_id: str,
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
            state.attempt_id = str(uuid.uuid4())

            if cancel_token.is_cancelled:
                return WorkerResult(success=False, error="Cancelled during retry")

            # Build context for this node
            # workflow_id = definition.workflow_id (canonical, matches
            # workflow lifecycle events and EvaluatorWorker lookups).
            # The per-execution instance_id is in metadata["instance_id"]
            # for tracing.
            ctx = ExecutionContext(
                session_id=session_id,
                workflow_id=workflow_id,
                metadata={
                    "query": query,
                    "node_id": node.node_id,
                    "node_config": node.config,
                    "attempt": attempt + 1,
                    "attempt_id": state.attempt_id,
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
