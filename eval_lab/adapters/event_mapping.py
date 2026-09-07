"""eval_lab/adapters/event_mapping.py — runtime event_type -> canonical mapping.

Built strictly from actual producer code inspected during Slice 3
discovery (core/workers/base.py, core/workflow/runtime.py,
core/runtime/progress.py) as of commit 13b86f8 on main -- not invented,
not extrapolated beyond what was actually read. See
docs/reports/EVAL_LAB_SLICE3_TRACE_ADAPTER_DISCOVERY_AND_DESIGN.md for the
full discovery narrative and mapping-table rationale this module
implements.

Three producer families were found, with genuinely different identity
shapes -- this module does not paper over that:

- **Worker lifecycle** (core/workers/base.py, AbstractCognitiveWorker):
  worker.started/progress/completed/failed/cancelled/rejected/escalated.
  source = worker_id (f"{worker_type}:{uuid4hex8}", stable per worker
  instance). Emission is explicitly best-effort -- a try/except around
  the EventStream.append() call swallows failures with only a log
  warning, so absence of a terminal worker event is not proof the worker
  didn't complete (see trace_normalizer.py's terminality handling).

- **Workflow/root-execution level** (core/workflow/runtime.py,
  WorkflowRuntime): workflow.started/completed, execution.completed/failed.
  Two seemingly-overlapping "the whole thing is done" signals
  (workflow.completed and execution.completed) were found emitted from
  the same method at different points; discovery did not fully establish
  whether they are ever semantically redundant, so both are treated as
  independent completion evidence rather than one being assumed
  derivable from the other.

- **Graph-aware node-level progress** (core/runtime/progress.py,
  ProgressMonitor -- the DEBT-016 side that actually reaches
  EventStream): execution.progress, execution.node.status/completed/failed,
  execution.recovery.started. Carries real parent_id causal structure
  (ExecutionNode.parent_id) the adapter uses for CausalReference edges.

A fourth source -- the model-router-facing watchdog
(core/runtime/execution_watchdog.py, core/runtime/progress_monitor.py,
DEBT-016's other side) -- was confirmed during discovery to emit *nothing*
to EventStream at all (zero references to event_stream/.append() in
either file). It produces real effects (cancellation via
CancellationToken) with no EventStream evidence trail. This is not a
second schema to normalize; it is a confirmed evidence gap, documented
here rather than papered over -- see NO_EVENTSTREAM_FOOTPRINT below.
"""

from __future__ import annotations

from eval_lab.contracts.trajectory import TrajectoryEventType

# Runtime event_type (string, as it appears in StreamEvent.event_type) ->
# canonical TrajectoryEventType. Absence from this dict is not an error --
# unmapped event_types normalize to UNKNOWN with raw_type_name preserved
# (per TrajectoryEventType's own controlled-extensibility design, Slice 2).
RUNTIME_EVENT_TYPE_MAP: dict[str, TrajectoryEventType] = {
    # --- Worker lifecycle (core/workers/base.py) ---
    "worker.started": TrajectoryEventType.WORKER,
    "worker.progress": TrajectoryEventType.OBSERVATION,
    "worker.completed": TrajectoryEventType.WORKER,
    # Confirmed distinct from worker.completed(success=False) during
    # discovery: worker.failed payload carries {error, error_type} and
    # fires from an exception handler -- a genuine crash, not a
    # controlled negative result.
    "worker.failed": TrajectoryEventType.FAILURE,
    "worker.cancelled": TrajectoryEventType.CANCELLATION,
    # payload: {reason, governor} -- a governance-layer rejection.
    "worker.rejected": TrajectoryEventType.FAILURE,
    # payload: {reason, governor} -- escalation is an exceptional
    # handling path; RECOVERY is the closest existing category rather
    # than inventing a governance-specific one for two event types.
    "worker.escalated": TrajectoryEventType.RECOVERY,

    # --- Workflow / root-execution level (core/workflow/runtime.py) ---
    # No existing TrajectoryEventType cleanly represents "the workflow
    # began executing" -- left unmapped deliberately (falls through to
    # UNKNOWN with raw_type_name="workflow.started" preserved) rather
    # than forcing a poor-fit category. This is a real gap in the
    # original Slice 2 vocabulary (designed from the mission's abstract
    # list, before real producer names were known), disclosed rather
    # than hidden.
    "workflow.completed": TrajectoryEventType.COMPLETION,
    "execution.completed": TrajectoryEventType.COMPLETION,
    "execution.failed": TrajectoryEventType.FAILURE,

    # --- Graph-aware node-level (core/runtime/progress.py) ---
    "execution.progress": TrajectoryEventType.OBSERVATION,
    "execution.node.status": TrajectoryEventType.STATE_TRANSITION,
    # "node" (ExecutionGraph/ExecutionNode) and "worker" (AbstractCognitiveWorker)
    # are related but not identical runtime concepts; WORKER is the
    # closest existing category for "a unit of execution completed."
    "execution.node.completed": TrajectoryEventType.WORKER,
    "execution.node.failed": TrajectoryEventType.FAILURE,
    "execution.recovery.started": TrajectoryEventType.RECOVERY,
}

# event_types that are intentionally left unmapped (fall through to
# UNKNOWN) with the specific reason recorded, so a future maintainer
# doesn't mistake the omission for an oversight.
DELIBERATELY_UNMAPPED: dict[str, str] = {
    "workflow.started": (
        "No existing TrajectoryEventType represents 'execution began' at "
        "the whole-workflow level; forcing a fit (e.g. PLAN, COMPILATION) "
        "would overclaim precision the original enum design didn't intend "
        "for this specific runtime concept."
    ),
}

# Confirmed during Slice 3 discovery: this producer has no EventStream
# footprint at all. Not a mapping gap -- an evidence gap. The adapter
# cannot normalize what was never emitted.
NO_EVENTSTREAM_FOOTPRINT = {
    "component": "model-router-facing watchdog (core/runtime/execution_watchdog.py, "
                  "core/runtime/progress_monitor.py -- DEBT-016's other side)",
    "finding": "Zero references to event_stream or EventStream.append() in either file. "
               "Produces real runtime effects (cancellation via CancellationToken) "
               "with no durable evidence trail visible to EventStream.",
    "adapter_implication": "The trace adapter cannot represent watchdog-triggered "
                            "cancellations from this source as trajectory evidence -- "
                            "there is nothing in EventStream to normalize. If such a "
                            "cancellation occurs, the only visible effect may be an "
                            "absence of further worker events, which the adapter must "
                            "not interpret as evidence of anything specific (see "
                            "trace_normalizer.py's terminality-unknown handling).",
}


def map_event_type(runtime_event_type: str) -> TrajectoryEventType:
    """Look up the canonical TrajectoryEventType for a runtime event_type
    string. Always returns a value -- unmapped types return UNKNOWN,
    never raise. Per Slice 2's controlled-extensibility design
    (TrajectoryEvent.raw_type_name), the caller is responsible for
    preserving the original string alongside this classification."""
    return RUNTIME_EVENT_TYPE_MAP.get(runtime_event_type, TrajectoryEventType.UNKNOWN)
