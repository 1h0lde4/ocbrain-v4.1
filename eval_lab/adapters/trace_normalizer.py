"""eval_lab/adapters/trace_normalizer.py — the Slice 3 trace adapter.

Per ADR-LAB-02: consumes core.events.event_stream.StreamEvent (the pure,
stdlib-only dataclass -- verified safe to import the same way
core.runtime.execution_outcome.FailureType was in Slice 2's failure.py;
StreamEvent itself has zero OCBrain-internal imports). Does NOT import
EventStream/EventStore (the stateful service classes with sqlite3/asyncio
coupling) -- this function takes an already-retrieved iterable of events,
so eval_lab/ never touches a database connection, an event loop, or any
runtime service object. Whatever calls this (a future Slice, not this
one) is responsible for actually calling EventStream.replay()/query() and
handing the results here.

This module is a deterministic transformation: same input events (same
identity, same sequence, same payloads) always produce the same
NormalizationResult. It does not orchestrate workers, execute evaluators,
score anything, or write back to any runtime infrastructure.
Per core.events.event_stream.StreamEvent's own docstring ("Globally unique
event identifier") and its generation mechanism (`field(default_factory=
lambda: str(uuid.uuid4()))`, client-side, not a per-store sequential
counter): `event.event_id` is trusted as globally unique across any set
of StreamEvents this adapter might ever be handed, including from
multiple distinct EventStream instances/files, not merely unique within
one store's own UNIQUE constraint (which is a secondary integrity check
on top of, not the source of, that uniqueness). This is the basis for
deriving `trajectory_event_id` directly from `event_id` (Finding 4,
verified against the actual generation mechanism rather than assumed from
the field being named "event_id") -- see
test_event_id_generation_mechanism_is_uuid4_not_a_sequential_counter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from core.events.event_stream import StreamEvent  # pure dataclass, stdlib-only, zero coupling -- see module docstring

from eval_lab.adapters.event_mapping import map_event_type
from eval_lab.adapters.outcomes import (
    AdapterOutcomeStatus,
    EventDisposition,
    EventDispositionType,
    NormalizationResult,
    TrajectoryTerminality,
)
from eval_lab.contracts.enums import CausalRelationType, OrderingRelation
from eval_lab.contracts.failure import ErrorEnvelope, Severity
from eval_lab.contracts.identifiers import ExecutionInstanceId, TrajectoryId, new_object_id
from eval_lab.contracts.enums import FaultDomain
from eval_lab.contracts.trajectory import CausalReference, Trajectory, TrajectoryEvent, TrajectoryEventType

# Producers whose payload may include a `parent_id` establishing real
# causal/hierarchical structure, per discovery of core/runtime/progress.py's
# ExecutionNode.parent_id. Only these event_types are checked for it --
# treating an incidental "parent_id"-shaped key on an unrelated payload as
# a causal edge would be exactly the kind of fabricated relationship §8
# forbids.
_NODE_LEVEL_EVENT_TYPES = frozenset({
    "execution.progress", "execution.node.status", "execution.node.completed",
    "execution.node.failed", "execution.recovery.started",
})

# Fields the adapter knows how to fold into existing TrajectoryEvent
# fields rather than treating as "extra" raw payload. Confirmed from
# actual producer payload shapes during discovery -- see event_mapping.py.
_KNOWN_MAPPABLE_PAYLOAD_KEYS = frozenset({
    "worker_id", "workflow_id", "task_id", "node_id", "parent_id",
})

_TERMINAL_TYPES_COMPLETION = frozenset({TrajectoryEventType.COMPLETION})
_TERMINAL_TYPES_FAILURE = frozenset({TrajectoryEventType.FAILURE})
_TERMINAL_TYPES_CANCELLATION = frozenset({TrajectoryEventType.CANCELLATION})
# Deliberately excludes TrajectoryEventType.WORKER: per event_mapping.py,
# worker.completed/execution.node.completed map to WORKER, not COMPLETION,
# specifically so one worker/node finishing cannot be read as the whole
# trajectory finishing. This is the trajectory-vs-child-operation
# terminality authority rule, made explicit here rather than left as an
# emergent property of the mapping table alone -- see
# test_many_completed_workers_do_not_imply_trajectory_completion for the
# direct check that this actually holds, not just that it's documented.


@dataclass(frozen=True)
class _ProcessedEvent:
    trajectory_event: TrajectoryEvent | None  # None if not normalized (malformed/rejected/duplicate)
    disposition: EventDisposition


def _is_malformed(event: StreamEvent) -> str | None:
    """Returns a reason string if malformed, else None. Deliberately
    narrow: a well-typed StreamEvent instance with semantically invalid
    contents (empty event_id/event_type, non-positive sequence) is what
    "malformed" means here -- a wrong Python type entirely would fail
    before this function is even reached, at the type-hint boundary."""
    if not event.event_id:
        return "empty_event_id"
    if not event.event_type:
        return "empty_event_type"
    if event.sequence is None or event.sequence < 0:
        return "invalid_sequence"
    if event.timestamp is None or event.timestamp < 0:
        return "invalid_timestamp"
    return None


def _extract_raw_payload(event: StreamEvent) -> dict | None:
    """Whatever's in payload beyond the keys the adapter already folds
    into canonical TrajectoryEvent fields. None (not an empty dict) when
    there's genuinely nothing left over, so RETAINED_RAW vs. NORMALIZED
    disposition reflects reality rather than always firing."""
    if not event.payload:
        return None
    leftover = {k: v for k, v in event.payload.items() if k not in _KNOWN_MAPPABLE_PAYLOAD_KEYS}
    return leftover or None


def normalize_trajectory(
    events: Iterable[StreamEvent],
    execution_instance_id: ExecutionInstanceId,
    trajectory_id: TrajectoryId | None = None,
    *,
    assume_contiguous_sequence: bool = False,
) -> NormalizationResult:
    """Normalize a batch of runtime StreamEvents into a Slice 2 Trajectory.

    Ordering (§7): sorted by `event.sequence` -- the authoritative order
    per discovery (SQLite AUTOINCREMENT primary key, assigned atomically
    at persist time under single-writer access). Never by input iteration
    order, never by wall-clock timestamp (which is stored but not
    load-bearing for order).

    Identity (§6): deduplicated by `event.event_id` (fresh uuid4 minted
    per StreamEvent construction; the store enforces a UNIQUE constraint
    at persistence time, so genuine duplicates reaching this function
    mean either a re-ingested overlapping window or a genuine anomaly --
    both handled explicitly, never silently).

    `assume_contiguous_sequence`: **False by default, and this default
    matters.** `StreamEvent.sequence` is confirmed (via
    core/events/event_stream.py) to be a single AUTOINCREMENT counter
    global to the entire store -- shared by every producer, every
    execution, every workflow. `EventStream.query()` itself documents a
    `payload_workflow_id` filter for exactly this reason: the realistic
    way a caller gets "this execution's events" is to filter a shared
    global stream down, which produces perfectly normal, evidence-complete
    results with non-contiguous sequence numbers (execution A's events at
    global sequence 10 and 12, with an unrelated execution B's event
    legitimately sitting at 11). Treating that as missing evidence would
    have been a real, unsafe defect -- caught in review before this went
    further, not shipped. Only pass True when the caller can actually
    vouch that the supplied events represent a genuinely contiguous slice
    (e.g. synthetic/test data, or a caller-side guarantee this function
    has no way to verify on its own) -- when True, a gap becomes positive,
    reportable evidence of incompleteness; when False (default), gaps are
    not inspected for this purpose at all, because in the normal
    scoped-query case they carry no such meaning.
    """
    trajectory_id = trajectory_id or TrajectoryId(new_object_id("traj"))
    event_list = sorted(events, key=lambda e: e.sequence)

    seen_by_id: dict[str, StreamEvent] = {}
    node_id_to_trajectory_event_id: dict[str, str] = {}
    processed: list[_ProcessedEvent] = []
    errors: list[ErrorEnvelope] = []

    try:
        prev_source: str | None = None
        for event in event_list:
            malformed_reason = _is_malformed(event)
            if malformed_reason is not None:
                processed.append(_ProcessedEvent(
                    trajectory_event=None,
                    disposition=EventDisposition(
                        source_event_id=event.event_id or "<empty>",
                        disposition=EventDispositionType.MALFORMED,
                        reason=malformed_reason,
                        raw_payload=dict(event.payload) if event.payload else None,
                    ),
                ))
                continue

            if event.event_id in seen_by_id:
                prior = seen_by_id[event.event_id]
                if prior.payload == event.payload and prior.event_type == event.event_type:
                    processed.append(_ProcessedEvent(
                        trajectory_event=None,
                        disposition=EventDisposition(
                            source_event_id=event.event_id,
                            disposition=EventDispositionType.DUPLICATE_IGNORED,
                            reason="identical event_id and payload already ingested; idempotent skip",
                        ),
                    ))
                else:
                    # §6: differing payload under the same event_id is a
                    # genuine integrity concern. Neither occurrence is
                    # silently preferred; the first-seen stays canonical
                    # (already in the trajectory), this one is flagged.
                    processed.append(_ProcessedEvent(
                        trajectory_event=None,
                        disposition=EventDisposition(
                            source_event_id=event.event_id,
                            disposition=EventDispositionType.CONFLICTING_DUPLICATE,
                            reason="same event_id previously seen with a different payload or event_type",
                            raw_payload=dict(event.payload) if event.payload else None,
                        ),
                    ))
                continue

            seen_by_id[event.event_id] = event

            canonical_type = map_event_type(event.event_type)
            causal_refs: tuple[CausalReference, ...] = ()
            if event.event_type in _NODE_LEVEL_EVENT_TYPES:
                parent_node_id = event.payload.get("parent_id")
                if parent_node_id and parent_node_id in node_id_to_trajectory_event_id:
                    causal_refs = (CausalReference(
                        relation=CausalRelationType.CAUSED_BY,
                        target_event_id=node_id_to_trajectory_event_id[parent_node_id],
                    ),)

            # Ordering heuristic (§7, documented as a heuristic, not a
            # certain fact): events from the same producer (source) are
            # genuinely sequential from that producer's own perspective.
            # Events from a different producer than the previous one
            # cannot be assumed causally ordered just because persistence
            # serialized them -- parallel workers' events interleave in
            # sequence order without that reflecting true causal order
            # between them.
            ordering = OrderingRelation.ORDERED if (prev_source is None or prev_source == event.source) else OrderingRelation.CONCURRENT
            prev_source = event.source

            # Deterministic, not random: derived directly from the source
            # event's own stable identity, per §14 ("two normalizations of
            # equivalent source evidence must produce equivalent canonical
            # results"). A random uuid4() here would fail that requirement
            # outright -- caught by test_normalization_is_deterministic_across_calls.
            # As a side benefit, a trajectory_event_id is now trivially
            # traceable back to the exact source event it came from.
            trajectory_event_id = f"tev_{event.event_id}"
            duration_ms = event.payload.get("duration_ms") if isinstance(event.payload.get("duration_ms"), (int, float)) else None

            tev = TrajectoryEvent(
                trajectory_event_id=trajectory_event_id,
                event_type=canonical_type,
                raw_type_name=event.event_type,
                occurred_at=datetime.fromtimestamp(event.timestamp, tz=timezone.utc),
                monotonic_sequence=event.sequence,
                ordering_relation_to_previous=ordering,
                worker_id=event.source or None,
                execution_instance_id=execution_instance_id,
                causal_references=causal_refs,
                summary=f"{event.event_type} from {event.source}",
                duration_ms=float(duration_ms) if duration_ms is not None else None,
            )

            node_id = event.payload.get("node_id")
            if node_id:
                node_id_to_trajectory_event_id[node_id] = trajectory_event_id

            raw_leftover = _extract_raw_payload(event)
            disposition_type = EventDispositionType.RETAINED_RAW if raw_leftover else EventDispositionType.NORMALIZED
            processed.append(_ProcessedEvent(
                trajectory_event=tev,
                disposition=EventDisposition(
                    source_event_id=event.event_id,
                    disposition=disposition_type,
                    reason=(
                        f"mapped {event.event_type!r} -> {canonical_type.value}"
                        if canonical_type != TrajectoryEventType.UNKNOWN
                        else f"no canonical mapping for {event.event_type!r}; classified UNKNOWN, raw_type_name preserved"
                    ),
                    raw_payload=raw_leftover,
                    canonical_trajectory_event_id=trajectory_event_id,
                ),
            ))
    except Exception as exc:  # noqa: BLE001 -- adapter-boundary catch-all, converted to an explicit fatal outcome per §11/§19
        return NormalizationResult(
            execution_instance_id=execution_instance_id,
            trajectory_id=trajectory_id,
            trajectory=None,
            outcome_status=AdapterOutcomeStatus.FATAL_ADAPTER_FAILURE,
            terminality=TrajectoryTerminality.TERMINALITY_UNKNOWN,
            event_dispositions=tuple(p.disposition for p in processed),
            errors=(ErrorEnvelope(
                error_code="ADAPTER_INTERNAL_ERROR",
                domain=FaultDomain.INFRASTRUCTURE,
                message=f"{type(exc).__name__}: {exc}",
                severity=Severity.CRITICAL,
                recoverable=False,
            ),),
        )

    trajectory_events = tuple(p.trajectory_event for p in processed if p.trajectory_event is not None)
    trajectory = Trajectory(trajectory_id=trajectory_id, execution_instance_id=execution_instance_id, events=trajectory_events)

    dispositions = tuple(p.disposition for p in processed)
    outcome_status = _determine_outcome_status(dispositions)
    terminality = _determine_terminality(trajectory_events)
    if assume_contiguous_sequence:
        incomplete = _has_sequence_gap(event_list)
        if incomplete and outcome_status == AdapterOutcomeStatus.SUCCESSFUL:
            outcome_status = AdapterOutcomeStatus.INCOMPLETE_SOURCE_TRACE
        if incomplete and terminality != TrajectoryTerminality.COMPLETED_OBSERVED:
            terminality = TrajectoryTerminality.INCOMPLETE_TRACE
    # else: gaps are not inspected. StreamEvent.sequence is a global,
    # store-wide counter (confirmed against core/events/event_stream.py);
    # a gap in an arbitrary or execution-scoped subset (e.g. from
    # EventStream.query(payload_workflow_id=...)) is the *normal* shape
    # of a complete, correctly-filtered result, not evidence of anything
    # missing. Inferring incompleteness here by default would have been
    # exactly the kind of false signal capable of poisoning downstream
    # reliability measurements -- caught in review, fixed before Slice 4.

    return NormalizationResult(
        execution_instance_id=execution_instance_id,
        trajectory_id=trajectory_id,
        trajectory=trajectory,
        outcome_status=outcome_status,
        terminality=terminality,
        event_dispositions=dispositions,
        errors=(),
    )


def _determine_outcome_status(dispositions: tuple[EventDisposition, ...]) -> AdapterOutcomeStatus:
    if not dispositions:
        return AdapterOutcomeStatus.SUCCESSFUL  # empty input is not an error; see test coverage
    bad = [d for d in dispositions if d.disposition in (
        EventDispositionType.MALFORMED, EventDispositionType.REJECTED, EventDispositionType.CONFLICTING_DUPLICATE,
    )]
    if bad and len(bad) == len(dispositions):
        return AdapterOutcomeStatus.SOURCE_EVENT_REJECTED
    if bad:
        return AdapterOutcomeStatus.PARTIAL
    if any(d.disposition == EventDispositionType.UNSUPPORTED for d in dispositions):
        return AdapterOutcomeStatus.UNSUPPORTED_EVIDENCE
    return AdapterOutcomeStatus.SUCCESSFUL


def _determine_terminality(trajectory_events: tuple[TrajectoryEvent, ...]) -> TrajectoryTerminality:
    """Per §12/§8: never infer completion merely because ingestion
    stopped. Only classifies as observed-complete/failed/cancelled when a
    mapped event of that type genuinely exists in the evidence.

    Terminality authority hierarchy (Finding 5, made explicit rather than
    left implicit in the mapping table): only events whose canonical
    TrajectoryEventType is COMPLETION, FAILURE, or CANCELLATION can
    determine *trajectory-level* terminality. WORKER-typed events --
    which is what worker.completed and execution.node.completed map to --
    describe a child operation finishing, not the whole trajectory. A
    trajectory with a hundred successfully-completed workers and no
    workflow.completed/execution.completed/execution.failed/
    worker.cancelled event anywhere is still TERMINALITY_UNKNOWN, not
    COMPLETED_OBSERVED -- see
    test_many_completed_workers_do_not_imply_trajectory_completion.
    """
    types_present = {e.event_type for e in trajectory_events}
    if types_present & _TERMINAL_TYPES_COMPLETION:
        return TrajectoryTerminality.COMPLETED_OBSERVED
    if types_present & _TERMINAL_TYPES_FAILURE:
        return TrajectoryTerminality.FAILED_OBSERVED
    if types_present & _TERMINAL_TYPES_CANCELLATION:
        return TrajectoryTerminality.CANCELLED_OBSERVED
    return TrajectoryTerminality.TERMINALITY_UNKNOWN


def _has_sequence_gap(event_list: list[StreamEvent]) -> bool:
    """A genuine, positive signal of missing evidence (distinct from
    simply lacking a terminal event): consecutive sequence numbers more
    than 1 apart mean something between them was never ingested here.
    Does not distinguish 'never emitted' from 'emitted but not included
    in this batch' -- both are 'incomplete' from this adapter's vantage."""
    sequences = sorted({e.sequence for e in event_list if e.sequence is not None})
    return any(b - a > 1 for a, b in zip(sequences, sequences[1:]))
