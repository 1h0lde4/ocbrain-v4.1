"""
core/workers/supervisor.py — SupervisorWorker (Packet 08).

Architecture:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §4  (Worker Evolution — SupervisorWorker "does not exist yet ...
             specified in §9"; must be stateless like every other worker)
        §9  (Supervision Architecture — monitoring, failure recovery,
             escalation, termination, loop prevention; the load-bearing
             principle: "Supervisor decides *how* to respond to a
             failure; GovernanceKernel decides *whether* the resulting
             action is permitted... Supervisor has none of its own
             [authority] to duplicate, by design")
        §12 (Event Integration — cognitive.supervision_escalated)
        §15 (Governance Integration — "Supervisor may hand a revised
             Goal back to Planner ... it must not resubmit the same
             rejected ExecutionPlan unchanged")
        §16 (Runtime Invariants, item 9 — "A rejected or escalated plan
             is not silently retried as-is")
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 08 — Supervisor Worker.

Packet: Packet 08 — Supervisor Worker.

Scope:
    SupervisorWorker(AbstractCognitiveWorker) has two independent
    responsibilities, kept structurally separate:

    (1) React to a compilation-gate outcome (a CompilationResult from
        core/cognitive/compiler.py, Packet 06). REJECT and
        REJECTED_PRECHECK are surfaced as a failed WorkerResult with no
        retry attempted, ever — not bounded by a counter, but
        structurally: this code path contains no call that could
        resubmit the same ExecutionPlan. ESCALATE is additionally
        surfaced via cognitive.supervision_escalated (K4 §12), the one
        event this packet introduces.

    (2) Retry a failed worker invocation via ExecutionRuntime.invoke()
        (K4 §9's own described mechanism; core/runtime/execution_runtime.py
        already has a parent_worker_id parameter documented "for
        Supervisor pattern" — this packet is that pattern's first use,
        not a new addition to ExecutionRuntime). Bounded by an explicit,
        caller-supplied attempt count (Supervisor itself holds no state
        — K4 §4). This is a *second* attempt, layered above whatever
        per-node retries WorkflowRuntime already performed on its own
        via WorkflowNode.retry_policy (confirmed by reading
        core/workflow/runtime.py's _execute_node_with_retry() — node-
        level retry already exists and is not this packet's job to
        duplicate).

Explicitly forbidden (K4 §9, §16):
    - A second governance authority. Every retry Supervisor initiates
      re-enters through ExecutionRuntime.invoke() -> Worker.execute() ->
      the exact same evaluate_action() path everything else already
      uses. Supervisor evaluates nothing itself.
    - Retrying a plan Governance has already rejected or escalated
      (K4 §16 invariant 9) — enforced structurally (see (1) above), not
      by a counter that could be miscalibrated.
    - Terminating a running WorkflowRuntime execution (K4 §9:
      "RecursionGovernor/cancellation-token territory, unchanged").

Explicitly NOT in scope (future work):
    - Actually handing a revised Goal back to Planner (K4 §15 describes
      this as Supervisor's eventual recovery path for a rejected plan,
      but Planner has no mechanism today to accept feedback from a
      prior attempt — building one is not this packet's job). This
      packet surfaces the rejection; it does not attempt to recover
      from it by generating a new plan.
    - An actual HITL approval queue. GovernanceKernel's own docstring
      already says what a caller should do on ESCALATE: "queue for HITL
      approval" — but no queue, UI, or approval workflow exists anywhere
      in this repository, and building one is explicitly out of scope
      (matching this repository's own stated policy of not inventing
      substitutes for systems that don't exist yet). Emitting
      cognitive.supervision_escalated *is* the surfacing this packet is
      responsible for.
    - Retry backoff/jitter scheduling. ExecutionRuntime.invoke() is
      called once per SupervisorWorker._run() invocation; scheduling a
      delayed retry is an orchestration concern for whatever eventually
      calls Supervisor repeatedly (Packet 09 or later), not something
      this stateless worker does itself.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.cognitive.compiler import CompilationResult, CompilationStatus
from core.runtime.execution_runtime import ExecutionRuntime
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult


class SupervisorOutcome:
    """SupervisorWorker's own decision, returned in WorkerResult.output["outcome"].

    Not a GovernanceVerdict — Supervisor produces no verdict of its own
    (K4 §9: it has no authority to duplicate). This describes what
    Supervisor *did* in response to a verdict or failure it observed.
    """

    ESCALATED = "escalated"
    REJECTED = "rejected"
    RETRY_INITIATED = "retry_initiated"
    RETRY_EXHAUSTED = "retry_exhausted"
    NO_ACTION = "no_action"


def _classify_compilation_outcome(
    compilation_result: Optional[CompilationResult],
) -> Optional[str]:
    """Pure function: CompilationResult -> SupervisorOutcome | None.

    Returns None for a successful compilation (nothing to supervise) or
    when no compilation_result was given. K4 §16 invariant 9 is enforced
    by *what SupervisorWorker does with this return value* (see
    _run()'s REJECTED/ESCALATED branches, which contain no retry call at
    all), not by this function — classification and the "never retry"
    guarantee are deliberately kept as two separate concerns so the
    guarantee cannot be weakened by a future change to this function
    alone.
    """
    if compilation_result is None:
        return None
    if compilation_result.status == CompilationStatus.ESCALATED:
        return SupervisorOutcome.ESCALATED
    if compilation_result.status in (
        CompilationStatus.REJECTED,
        CompilationStatus.REJECTED_PRECHECK,
    ):
        return SupervisorOutcome.REJECTED
    return None  # COMPILED — nothing to supervise


class SupervisorWorker(AbstractCognitiveWorker):
    """Reacts to compilation-gate outcomes and retries failed worker
    invocations. See module docstring for full architecture citations
    and scope.
    """

    worker_type = "SupervisorWorker"

    def __init__(self, *, execution_runtime: Optional[ExecutionRuntime] = None,
                 **kwargs: Any) -> None:
        """Args:
            execution_runtime: Used for the retry path only. Unlike
                UnifiedMemory/GovernanceKernel/EventStream, there is no
                singleton getter for ExecutionRuntime — it requires a
                WorkerRegistry, which is composition-root-owned
                (core/runtime/worker_registry.py; populated explicitly in
                main.py, not auto-discovered). SupervisorWorker does not
                construct one itself, which would mean inventing a
                registry-population scheme that is not this packet's
                job. If None, the retry path (2) is unavailable and
                _run() reports that plainly rather than silently doing
                nothing (see _attempt_retry()); path (1), reacting to a
                CompilationResult, works regardless.
            **kwargs: forwarded to AbstractCognitiveWorker.__init__
                (governance, event_stream).
        """
        super().__init__(**kwargs)
        self._execution_runtime = execution_runtime

    async def _run(self, context: WorkerContext) -> WorkerResult:
        """Two independent input paths (see module docstring). Exactly
        one is exercised per call; a compilation_result requiring
        surfacing takes precedence and short-circuits — a plan that was
        rejected is not simultaneously eligible for a worker-level retry.

        Path (1): context.parameters["compilation_result"] — a
        CompilationResult (core/cognitive/compiler.py). REJECT/
        REJECTED_PRECHECK/ESCALATE are surfaced; COMPILED falls through
        to path (2) with nothing to do there either unless
        failed_worker_result is also given.

        Path (2): context.parameters["failed_worker_result"] — a
        WorkerResult with success=False from some prior invocation.
        Retries it via ExecutionRuntime.invoke(), bounded by
        context.parameters["max_supervisor_retries"] (default 1) and
        context.parameters["supervisor_retry_attempt"] (default 0,
        caller-tracked — Supervisor holds no state of its own, K4 §4).
        Also requires context.parameters["retry_worker_type"] (the
        worker_type string to re-invoke) and, optionally,
        context.parameters["retry_parameters"] (threaded through to the
        retried worker's own WorkerContext.parameters via
        ExecutionContext.metadata["parameters"] —
        core/runtime/execution_context.py's to_worker_context() bridge).

        Neither input given: WorkerResult(success=True, outcome="no_action").
        """
        compilation_result = context.parameters.get("compilation_result")
        if compilation_result is not None:
            if not isinstance(compilation_result, CompilationResult):
                return WorkerResult(
                    success=False,
                    error="SupervisorWorker's context.parameters['compilation_result'] "
                          "must be a CompilationResult instance.",
                )
            outcome = _classify_compilation_outcome(compilation_result)
            if outcome is not None:
                return await self._surface_compilation_outcome(
                    context, compilation_result, outcome)
            # outcome is None: COMPILED successfully. Nothing to surface
            # from this input; fall through in case a retry was ALSO
            # requested (e.g. Supervisor invoked once with both a
            # successful compilation and an unrelated prior failure to
            # retry — an unusual but not incoherent combination).

        failed_result = context.parameters.get("failed_worker_result")
        if failed_result is not None:
            return await self._attempt_retry(context, failed_result)

        return WorkerResult(
            success=True,
            output={"outcome": SupervisorOutcome.NO_ACTION},
        )

    async def _surface_compilation_outcome(
        self,
        context: WorkerContext,
        compilation_result: CompilationResult,
        outcome: str,
    ) -> WorkerResult:
        """K4 §16 invariant 9's actual enforcement point: this method
        contains no call to compile(), ExecutionRuntime, or
        WorkflowRuntime — a rejected or escalated plan is structurally
        unretriable from here, not merely uncalled by convention."""
        governance_result = compilation_result.governance_result
        payload: Dict[str, Any] = {
            "outcome": outcome,
            "governance_reason": governance_result.reason if governance_result else None,
            "governance_verdict": (
                governance_result.verdict.value if governance_result else None
            ),
        }
        if outcome == SupervisorOutcome.ESCALATED:
            # The one new event this packet introduces (K4 §12).
            # REJECTED relies on the standard worker.completed/failed
            # events every worker already gets, plus this structured
            # output — cognitive.plan_rejected (Packet 06) already
            # recorded the underlying governance verdict itself; nothing
            # here would add new information as its own event.
            await self._emit_event("cognitive.supervision_escalated", context, payload)
        return WorkerResult(success=False, output=payload,
                             artifacts={"compilation_result": compilation_result.to_dict()})

    async def _attempt_retry(
        self, context: WorkerContext, failed_result: Any,
    ) -> WorkerResult:
        max_retries = int(context.parameters.get("max_supervisor_retries", 1))
        attempt = int(context.parameters.get("supervisor_retry_attempt", 0))

        if attempt >= max_retries:
            return WorkerResult(
                success=False,
                output={"outcome": SupervisorOutcome.RETRY_EXHAUSTED, "attempts": attempt},
            )

        retry_worker_type = context.parameters.get("retry_worker_type")
        if self._execution_runtime is None or not retry_worker_type:
            return WorkerResult(
                success=False,
                error="SupervisorWorker requires an injected ExecutionRuntime and "
                      "context.parameters['retry_worker_type'] to retry a failed "
                      "worker invocation.",
            )

        retry_parameters = context.parameters.get("retry_parameters", {})
        # ExecutionRuntime.invoke() has no `parameters` kwarg directly —
        # ExecutionContext.to_worker_context() reads
        # metadata["parameters"] into WorkerContext.parameters (confirmed
        # by reading core/runtime/execution_context.py directly).
        retry_result: WorkerResult = await self._execution_runtime.invoke(
            retry_worker_type,
            query=context.query,
            workflow_id=context.workflow_id,
            parent_worker_id=self._id,
            metadata={"parameters": retry_parameters},
        )

        return WorkerResult(
            success=retry_result.success,
            output={
                "outcome": SupervisorOutcome.RETRY_INITIATED,
                "attempt": attempt + 1,
                "retry_success": retry_result.success,
            },
            artifacts={"retry_result": retry_result},
        )
