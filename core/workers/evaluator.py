"""
core/workers/evaluator.py — EvaluatorWorker (Packet 07).

Architecture:
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md
        §4  (Worker Evolution — EvaluatorWorker "does not exist yet ...
             specified in §8")
        §8  (Evaluation Architecture — EvaluationRecord's exact schema,
             confidence-calibration responsibility)
        §12 (Event Integration — cognitive.evaluation_completed)
        §13 (Memory Integration — evaluation writes go through
             UnifiedMemory.write()'s already-governed path)
        §15 (Governance Integration — EvaluationRecord itself is not
             separately gated; only the standard per-worker execute()
             gate every AbstractCognitiveWorker already gets, plus
             UnifiedMemory.write()'s own internal governance, apply)
        §16 (Runtime Invariants — "Evaluation never changes facts")
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 07 — Reflection + Evaluation Workers.

Packet: Packet 07 — Reflection + Evaluation Workers (Evaluator half).

Scope:
    EvaluatorWorker(AbstractCognitiveWorker) produces exactly one
    EvaluationRecord per evaluated execution (K4 §8) and writes it to
    UnifiedMemory as a KnowledgeEntry for future calibration (K4 §13).
    Objective measurement only — "what happened", not "why" or "what
    should change" (Reflection's job, core/workers/reflection.py).

Repository-reality note (K4 §4/§14, confirmed by direct reading, not
assumed): WorkflowRuntime (core/workflow/runtime.py) is real, complete,
working code — it is simply not yet invoked automatically by anything in
the Cognitive Front-End (no packet through Packet 06 wires compile()'s
output into it; that wiring is future work, not this packet's). It does
emit real "workflow.completed" events with a real `success` boolean, and
each node's worker already emits standard worker.completed/worker.failed
events via the governed execute() path every worker already uses. This
worker reads those — when they exist — via EventStream.query(), which has
no workflow_id filter (core/events/event_stream.py's SQLiteEventStore
indexes only event_type/source/since/until), so filtering is done by
payload["workflow_id"] in Python, not a new persistence mechanism. When
no such events exist yet (e.g. a plan evaluated without ever having been
executed through WorkflowRuntime), explicit context.parameters overrides
are honored instead — see _run()'s docstring.

Explicitly forbidden (K4 §16, Packet 07 spec):
    - Reasoning about causes, patterns, or recommendations — Reflection's
      job (core/workers/reflection.py), not this module's.
    - Learning / memory-curation decisions — ValidationGate's job
      (Packet 04, core/cognitive/learning.py). Nothing here calls it.
    - Mutating the KnowledgeEntry/event it evaluates ("Evaluation never
      changes facts") — only ever writes NEW entries.

Explicitly NOT in scope (future work):
    - Automatic invocation after every WorkflowRuntime.execute() call.
      There is no autonomous trigger anywhere in this repository for any
      worker (PlannerWorker and MemoryCuratorWorker are both invoked
      explicitly today); this packet does not add one for Evaluator
      either. Wiring that belongs to a future integration packet.
    - A general-purpose "quality scoring" model. quality_score here is a
      narrow, explicitly-documented, deterministic proxy (see
      _build_evaluation_record()), not a claim of sophisticated grading —
      inventing one would be exactly the "speculative infrastructure"
      this packet's own instructions forbid.
"""
from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.cognitive.planner import ExecutionPlan
from core.events.event_stream import EventStream, StreamEvent, get_event_stream
from core.memory.unified_memory import UnifiedMemory, get_unified_memory
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult

# Implementation judgment (not separately cited in architecture text),
# analogous in spirit to Packet 06's ClarificationPolicy default: a
# starting point a caller may override via context.parameters, not a
# claim of empirically-validated tuning.
_DEFAULT_QUALITY_SCORE_WHEN_UNKNOWN = 0.0


@dataclass
class EvaluationRecord:
    """K4 §8's exact schema — one instance per evaluated execution.

    predicted_confidence and actual_outcome together are the
    (prediction, outcome) pair K4 §8 says EvaluatorWorker accumulates
    over time (queried from past EvaluationRecord entries in
    UnifiedMemory, never held in worker state — statelessness, K4 §4)
    to compute Brier-style calibration on demand.
    """

    resource_id:          str   = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id:               str   = ""
    goal_completed:        bool  = False
    quality_score:          float = 0.0
    reasoning_valid:        bool  = True
    tool_success_rate:      float = 0.0
    predicted_confidence:   float = 0.0
    actual_outcome:         bool  = False

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


async def _fetch_workflow_events(
    event_stream: EventStream,
    workflow_id: str,
    event_type: str,
    limit: int = 200,
) -> List[StreamEvent]:
    """Read-only lookup of events for a specific workflow_id.

    Uses EventStream.query()'s payload_workflow_id parameter for
    database-level filtering (indexed via json_extract in SQLite).
    No Python-level post-filtering required.
    """
    return await event_stream.query(
        event_type=event_type,
        payload_workflow_id=workflow_id,
        limit=limit,
    )


def _build_evaluation_record(
    plan: ExecutionPlan,
    workflow_completed_events: List[StreamEvent],
    worker_completed_events: List[StreamEvent],
    worker_failed_events: List[StreamEvent],
    overrides: Dict[str, Any],
) -> EvaluationRecord:
    """Pure computation: raw event lists + explicit overrides -> EvaluationRecord.

    Deliberately separated from _fetch_workflow_events()/EvaluatorWorker
    so the actual measurement logic is directly unit-testable without an
    EventStream, mirroring core/cognitive/compiler.py's own separation of
    pure mapping (_compile_step/_compile_workflow) from I/O orchestration
    (compile()).

    goal_completed / actual_outcome: taken from the most recent (index 0
    — SQLiteEventStore.query() orders sequence DESC) "workflow.completed"
    event's own `success` payload field when one exists; otherwise from
    overrides["goal_completed"] (default False). goal_completed and
    actual_outcome are the same underlying signal — K4 §8 names them
    separately because one is Evaluation's own headline field and the
    other is specifically the calibration input paired with
    predicted_confidence, not because they can diverge.

    tool_success_rate: completed / (completed + failed) among the node-
    level worker.completed/worker.failed events found for this
    workflow_id. Falls back to overrides["tool_success_rate"] if
    supplied, else 1.0 if the workflow itself succeeded with no worker
    events found, else 0.0 — a defensible default (a workflow cannot
    report success with unknown per-node reliability without some
    signal), not a claim of measurement where none exists.

    reasoning_valid, quality_score: no deterministic execution-only
    signal distinguishes "succeeded because the reasoning was sound" from
    "succeeded despite flawed reasoning", or measures output quality
    directly — no such measurement exists anywhere in this repository
    today, and building one is explicitly out of this packet's scope.
    Both default to a documented, narrow proxy (reasoning_valid defaults
    to goal_completed; quality_score defaults to tool_success_rate) and
    are overridden by an explicit, more-informed caller via
    context.parameters when available.
    """
    if workflow_completed_events:
        goal_completed = bool(workflow_completed_events[0].payload.get("success", False))
    else:
        goal_completed = bool(overrides.get("goal_completed", False))

    total_worker_events = len(worker_completed_events) + len(worker_failed_events)
    if "tool_success_rate" in overrides:
        tool_success_rate = float(overrides["tool_success_rate"])
    elif total_worker_events > 0:
        tool_success_rate = len(worker_completed_events) / total_worker_events
    else:
        tool_success_rate = 1.0 if goal_completed else _DEFAULT_QUALITY_SCORE_WHEN_UNKNOWN

    reasoning_valid = bool(overrides.get("reasoning_valid", goal_completed))
    quality_score = float(overrides.get("quality_score", tool_success_rate))
    actual_outcome = goal_completed

    return EvaluationRecord(
        plan_id=plan.resource_id,
        goal_completed=goal_completed,
        quality_score=quality_score,
        reasoning_valid=reasoning_valid,
        tool_success_rate=tool_success_rate,
        predicted_confidence=plan.confidence,
        actual_outcome=actual_outcome,
    )


class EvaluatorWorker(AbstractCognitiveWorker):
    """Objective, deterministic evaluation of one completed execution.

    See module docstring for architecture citations and scope. Answers
    "what happened" only — produces facts (EvaluationRecord), never
    recommendations (that is ReflectionWorker's job).
    """

    worker_type = "EvaluatorWorker"

    def __init__(self, *, memory: Optional[UnifiedMemory] = None,
                 **kwargs: Any) -> None:
        """Args:
            memory: UnifiedMemory instance. Uses the shared singleton if
                None, mirroring every other injected dependency in this
                codebase (governance, event_stream in the base class;
                memory in core/cognitive/learning.py's module functions).
            **kwargs: forwarded to AbstractCognitiveWorker.__init__
                (governance, event_stream).
        """
        super().__init__(**kwargs)
        self._memory: UnifiedMemory = memory or get_unified_memory()

    async def _run(self, context: WorkerContext) -> WorkerResult:
        """Evaluate one execution and write the result to memory.

        Required input: context.parameters["execution_plan"], an
        ExecutionPlan instance (the compiled plan being evaluated) — the
        source of plan_id and predicted_confidence (K4 §8).

        context.workflow_id (falling back to plan.resource_id, matching
        core/cognitive/compiler.py's workflow_id=plan.resource_id
        convention) identifies which WorkflowRuntime execution, if any,
        to read events from.

        Optional overrides via context.parameters, honored when no
        corresponding event signal exists (or always, for
        tool_success_rate/reasoning_valid/quality_score — see
        _build_evaluation_record()'s docstring for exact precedence):
            goal_completed, tool_success_rate, reasoning_valid,
            quality_score (all optional; see _build_evaluation_record).
        """
        plan = context.parameters.get("execution_plan")
        if not isinstance(plan, ExecutionPlan):
            return WorkerResult(
                success=False,
                error="EvaluatorWorker requires context.parameters['execution_plan'] "
                      "(an ExecutionPlan instance) to evaluate against.",
            )

        workflow_id = context.workflow_id or plan.resource_id

        workflow_completed = await _fetch_workflow_events(
            self._event_stream, workflow_id, "workflow.completed")
        worker_completed = await _fetch_workflow_events(
            self._event_stream, workflow_id, "worker.completed")
        worker_failed = await _fetch_workflow_events(
            self._event_stream, workflow_id, "worker.failed")

        record = _build_evaluation_record(
            plan, workflow_completed, worker_completed, worker_failed,
            overrides=context.parameters,
        )

        entry_content = (
            f"Evaluation of plan {plan.resource_id} (goal {plan.goal_id}): "
            f"{'succeeded' if record.goal_completed else 'did not complete'}, "
            f"tool_success_rate={record.tool_success_rate:.2f}, "
            f"quality_score={record.quality_score:.2f}, "
            f"predicted_confidence={record.predicted_confidence:.2f}."
        )
        entry_id = await self._memory.write(
            content=entry_content,
            content_type="evaluation",
            layer_hint="l1",
            source=self.worker_type,
            importance=0.4,
            confidence=1.0,
            truth_status="candidate",
            metadata=record.to_dict(),
            worker_id=self._id,
            workflow_id=workflow_id,
            derived_from=[plan.resource_id],
        )

        await self._emit_event("cognitive.evaluation_completed", context, {
            "evaluation_entry_id": entry_id,
            "plan_id": plan.resource_id,
            "goal_completed": record.goal_completed,
            "quality_score": record.quality_score,
        })

        return WorkerResult(
            success=True,
            output=record.to_dict(),
            artifacts={
                "evaluation_record": record.to_dict(),
                "evaluation_entry_id": entry_id,
            },
        )
