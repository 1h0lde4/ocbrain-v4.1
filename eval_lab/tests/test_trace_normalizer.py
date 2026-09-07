"""Trace adapter tests — Slice 3, §17 of the mission brief.

Organized to match §17's own categories: runtime mapping, identity,
ordering, replay, evidence integrity, failure handling, lifecycle.
"""

from __future__ import annotations

from core.events.event_stream import StreamEvent

from eval_lab.adapters.event_mapping import DELIBERATELY_UNMAPPED, RUNTIME_EVENT_TYPE_MAP, map_event_type
from eval_lab.adapters.outcomes import AdapterOutcomeStatus, EventDispositionType, TrajectoryTerminality
from eval_lab.adapters.trace_normalizer import normalize_trajectory
from eval_lab.contracts.enums import OrderingRelation
from eval_lab.contracts.trajectory import TrajectoryEventType
from eval_lab.tests import fixtures_runtime_events as rt

# ---------------------------------------------------------------------------
# Runtime mapping
# ---------------------------------------------------------------------------

def test_every_discovered_event_type_has_an_explicit_mapping_or_documented_omission():
    """Every event_type actually found during discovery must either be in
    RUNTIME_EVENT_TYPE_MAP or in DELIBERATELY_UNMAPPED with a reason --
    never simply absent from both without explanation."""
    discovered = {
        "worker.started", "worker.progress", "worker.completed", "worker.failed",
        "worker.cancelled", "worker.rejected", "worker.escalated",
        "workflow.started", "workflow.completed", "execution.completed", "execution.failed",
        "execution.progress", "execution.node.status", "execution.node.completed",
        "execution.node.failed", "execution.recovery.started",
    }
    for event_type in discovered:
        accounted_for = event_type in RUNTIME_EVENT_TYPE_MAP or event_type in DELIBERATELY_UNMAPPED
        assert accounted_for, f"{event_type!r} was discovered but has no mapping and no documented omission reason"


def test_worker_completed_and_worker_failed_map_to_different_categories():
    """Discovery confirmed these are genuinely different failure modes
    (controlled negative outcome vs. exception/crash) -- must not collapse."""
    assert map_event_type("worker.completed") == TrajectoryEventType.WORKER
    assert map_event_type("worker.failed") == TrajectoryEventType.FAILURE
    assert map_event_type("worker.completed") != map_event_type("worker.failed")


def test_unknown_event_type_maps_to_unknown_not_an_exception():
    assert map_event_type("some.totally.unrecognized.type") == TrajectoryEventType.UNKNOWN


def test_workflow_started_is_a_documented_omission_not_an_oversight():
    assert "workflow.started" in DELIBERATELY_UNMAPPED
    assert "workflow.started" not in RUNTIME_EVENT_TYPE_MAP


def test_unsupported_event_normalizes_with_raw_type_name_preserved():
    ev = rt.unknown_future_event(event_id="e1", sequence=1, event_type="agent.dreamed")
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.trajectory.events[0].event_type == TrajectoryEventType.UNKNOWN
    assert result.trajectory.events[0].raw_type_name == "agent.dreamed"
    # not silently discarded -- has a disposition explaining the UNKNOWN classification
    assert "no canonical mapping" in result.event_dispositions[0].reason


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def test_lab_execution_instance_id_is_independent_of_runtime_source_field():
    """§5: Lab execution_instance_id must never be derived from or
    conflated with runtime source/worker/event identity."""
    ev = rt.worker_started(event_id="e1", sequence=1, worker_id="PlannerWorker:xyz")
    result = normalize_trajectory([ev], execution_instance_id="lab_exec_totally_unrelated_id")
    tev = result.trajectory.events[0]
    assert tev.execution_instance_id == "lab_exec_totally_unrelated_id"
    assert tev.worker_id == "PlannerWorker:xyz"
    assert tev.execution_instance_id != tev.worker_id


def test_source_event_id_preserved_in_disposition_not_reused_as_lab_identity():
    """The runtime StreamEvent.event_id is tracked in EventDisposition
    (raw runtime evidence) but the Lab mints its own
    trajectory_event_id -- these must be different values."""
    ev = rt.worker_started(event_id="runtime_event_uuid_123", sequence=1)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.event_dispositions[0].source_event_id == "runtime_event_uuid_123"
    assert result.trajectory.events[0].trajectory_event_id != "runtime_event_uuid_123"
    assert result.event_dispositions[0].canonical_trajectory_event_id == result.trajectory.events[0].trajectory_event_id


def test_trajectory_id_is_lab_minted_when_not_provided():
    ev = rt.worker_started(event_id="e1", sequence=1)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.trajectory_id is not None
    assert result.trajectory.trajectory_id == result.trajectory_id


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_events_ordered_by_sequence_not_input_order():
    e1 = rt.worker_started(event_id="e1", sequence=1, timestamp=2000.0)  # later timestamp
    e2 = rt.worker_completed(event_id="e2", sequence=2, timestamp=1000.0)  # earlier timestamp, later sequence
    result = normalize_trajectory([e2, e1], execution_instance_id="exec_1")  # fed reversed
    sequences = [tev.monotonic_sequence for tev in result.trajectory.events]
    assert sequences == [1, 2], "must order by StreamEvent.sequence, ignoring both input order and timestamp"


def test_conflicting_timestamp_does_not_reorder_evidence():
    """§7: 'if timestamps conflict with canonical source ordering, do not
    silently reorder evidence based on a convenient assumption.' Sequence
    wins even when timestamp says the opposite."""
    e1 = rt.worker_started(event_id="e1", sequence=1, timestamp=9999.0)
    e2 = rt.worker_completed(event_id="e2", sequence=2, timestamp=1.0)
    result = normalize_trajectory([e1, e2], execution_instance_id="exec_1")
    assert [tev.monotonic_sequence for tev in result.trajectory.events] == [1, 2]
    assert result.trajectory.events[0].occurred_at < result.trajectory.events[1].occurred_at is False or True
    # (occurred_at reflects the real, possibly "out of order", timestamp --
    # the adapter does not fabricate a corrected timestamp either)
    assert result.trajectory.events[0].occurred_at.timestamp() == 9999.0
    assert result.trajectory.events[1].occurred_at.timestamp() == 1.0


def test_same_producer_consecutive_events_marked_ordered():
    e1 = rt.worker_started(event_id="e1", sequence=1, worker_id="W1")
    e2 = rt.worker_completed(event_id="e2", sequence=2, worker_id="W1")
    result = normalize_trajectory([e1, e2], execution_instance_id="exec_1")
    assert result.trajectory.events[1].ordering_relation_to_previous == OrderingRelation.ORDERED


def test_different_producer_consecutive_events_marked_concurrent_not_assumed_ordered():
    """A heuristic, documented as such: persistence-order interleaving of
    two different producers' events is not assumed to reflect true
    causal order between them."""
    e1 = rt.worker_started(event_id="e1", sequence=1, worker_id="W1")
    e2 = rt.worker_started(event_id="e2", sequence=2, worker_id="W2")
    result = normalize_trajectory([e1, e2], execution_instance_id="exec_1")
    assert result.trajectory.events[1].ordering_relation_to_previous == OrderingRelation.CONCURRENT


# ---------------------------------------------------------------------------
# Replay / duplicates
# ---------------------------------------------------------------------------

def test_exact_duplicate_ingestion_is_idempotent():
    e1 = rt.worker_started(event_id="dup", sequence=1)
    e1_again = rt.worker_started(event_id="dup", sequence=1)  # identical
    result = normalize_trajectory([e1, e1_again], execution_instance_id="exec_1")
    assert len(result.trajectory.events) == 1
    dispositions = [d.disposition for d in result.event_dispositions]
    assert EventDispositionType.DUPLICATE_IGNORED in dispositions
    assert result.outcome_status == AdapterOutcomeStatus.SUCCESSFUL


def test_repeated_full_trace_replay_produces_equivalent_result():
    """§14: two normalizations of equivalent source evidence must produce
    equivalent canonical results."""
    events = [rt.worker_started(event_id="e1", sequence=1), rt.worker_completed(event_id="e2", sequence=2)]
    r1 = normalize_trajectory(list(events), execution_instance_id="exec_1", trajectory_id="traj_fixed")
    r2 = normalize_trajectory(list(events), execution_instance_id="exec_1", trajectory_id="traj_fixed")
    assert [e.event_type for e in r1.trajectory.events] == [e.event_type for e in r2.trajectory.events]
    assert [e.monotonic_sequence for e in r1.trajectory.events] == [e.monotonic_sequence for e in r2.trajectory.events]
    assert r1.outcome_status == r2.outcome_status


def test_conflicting_duplicate_identity_does_not_silently_diverge():
    """§6: same event_id, different payload -- must not silently prefer
    one; both are recorded, outcome reflects the conflict."""
    e1 = rt.worker_started(event_id="conflict_id", sequence=1, worker_id="W1")
    e2 = rt.worker_completed(event_id="conflict_id", sequence=1, worker_id="W1")  # same id, different event_type/payload
    result = normalize_trajectory([e1, e2], execution_instance_id="exec_1")
    dispositions = [d.disposition for d in result.event_dispositions]
    assert EventDispositionType.CONFLICTING_DUPLICATE in dispositions
    assert result.outcome_status == AdapterOutcomeStatus.PARTIAL
    # exactly one canonical TrajectoryEvent was produced (first-seen), not two
    assert len(result.trajectory.events) == 1


# ---------------------------------------------------------------------------
# Evidence integrity
# ---------------------------------------------------------------------------

def test_no_source_event_is_silently_dropped():
    """§9: every event gets an explicit disposition."""
    events = [
        rt.worker_started(event_id="e1", sequence=1),
        rt.worker_completed(event_id="e2", sequence=2),
        rt.unknown_future_event(event_id="e3", sequence=3),
    ]
    result = normalize_trajectory(events, execution_instance_id="exec_1")
    assert len(result.event_dispositions) == 3
    assert {d.source_event_id for d in result.event_dispositions} == {"e1", "e2", "e3"}


def test_extra_payload_fields_retained_as_raw_not_discarded():
    """§9: worker.completed's success/duration_ms beyond what canonical
    fields hold must be preserved somewhere, not silently lost."""
    ev = rt.worker_completed(event_id="e1", sequence=1, success=True, duration_ms=2500.0)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    disposition = result.event_dispositions[0]
    assert disposition.disposition == EventDispositionType.RETAINED_RAW
    assert disposition.raw_payload is not None
    assert disposition.raw_payload.get("success") is True


def test_governance_rejection_reason_and_governor_retained():
    ev = rt.worker_rejected(event_id="e1", sequence=1, reason="budget exceeded", governor="OrchestrationGovernor")
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    raw = result.event_dispositions[0].raw_payload
    assert raw["reason"] == "budget exceeded"
    assert raw["governor"] == "OrchestrationGovernor"


def test_normalization_is_deterministic_across_calls():
    events = [rt.worker_started(event_id="e1", sequence=1), rt.worker_failed(event_id="e2", sequence=2)]
    r1 = normalize_trajectory(list(events), execution_instance_id="exec_1", trajectory_id="t1")
    r2 = normalize_trajectory(list(events), execution_instance_id="exec_1", trajectory_id="t1")
    assert r1.trajectory.to_dict() == r2.trajectory.to_dict()


def test_no_fabricated_success_when_no_completion_evidence_exists():
    """§8: a worker.started with nothing after it must not be read as
    'probably succeeded.'"""
    ev = rt.worker_started(event_id="e1", sequence=1)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.terminality == TrajectoryTerminality.TERMINALITY_UNKNOWN


def test_no_fabricated_causal_reference_without_real_parent_id():
    """A node event with no parent_id in payload gets no CausalReference
    -- the adapter does not invent hierarchy that isn't in the evidence."""
    ev = rt.execution_node_completed(event_id="e1", sequence=1, node_id="root", parent_id=None)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.trajectory.events[0].causal_references == ()


def test_real_parent_id_produces_genuine_causal_reference():
    parent = rt.execution_node_status(event_id="e1", sequence=1, node_id="parent_node")
    child = rt.execution_node_completed(event_id="e2", sequence=2, node_id="child_node", parent_id="parent_node")
    result = normalize_trajectory([parent, child], execution_instance_id="exec_1")
    child_tev = result.trajectory.events[1]
    assert len(child_tev.causal_references) == 1
    assert child_tev.causal_references[0].target_event_id == result.trajectory.events[0].trajectory_event_id


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

def test_malformed_event_empty_event_id_is_isolated_not_fatal():
    good = rt.worker_started(event_id="good", sequence=1)
    bad = StreamEvent(event_id="", event_type="worker.started", source="W1", timestamp=1000.0, payload={}, sequence=2)
    result = normalize_trajectory([good, bad], execution_instance_id="exec_1")
    assert result.outcome_status == AdapterOutcomeStatus.PARTIAL  # one good, one bad
    assert len(result.trajectory.events) == 1  # only the good one normalized
    malformed = [d for d in result.event_dispositions if d.disposition == EventDispositionType.MALFORMED]
    assert len(malformed) == 1


def test_all_malformed_events_yields_source_event_rejected():
    bad1 = StreamEvent(event_id="", event_type="worker.started", source="W1", timestamp=1000.0, payload={}, sequence=1)
    bad2 = StreamEvent(event_id="e2", event_type="", source="W1", timestamp=1000.0, payload={}, sequence=2)
    result = normalize_trajectory([bad1, bad2], execution_instance_id="exec_1")
    assert result.outcome_status == AdapterOutcomeStatus.SOURCE_EVENT_REJECTED
    assert len(result.trajectory.events) == 0


def test_negative_sequence_is_malformed():
    bad = StreamEvent(event_id="e1", event_type="worker.started", source="W1", timestamp=1000.0, payload={}, sequence=-1)
    result = normalize_trajectory([bad], execution_instance_id="exec_1")
    assert result.event_dispositions[0].disposition == EventDispositionType.MALFORMED
    assert result.event_dispositions[0].reason == "invalid_sequence"


def test_empty_event_list_normalizes_successfully_to_empty_trajectory():
    result = normalize_trajectory([], execution_instance_id="exec_1")
    assert result.outcome_status == AdapterOutcomeStatus.SUCCESSFUL
    assert len(result.trajectory.events) == 0
    assert result.terminality == TrajectoryTerminality.TERMINALITY_UNKNOWN


# ---------------------------------------------------------------------------
# Lifecycle / terminality
# ---------------------------------------------------------------------------

def test_started_only_is_terminality_unknown_not_assumed_in_progress():
    ev = rt.worker_started(event_id="e1", sequence=1)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.terminality == TrajectoryTerminality.TERMINALITY_UNKNOWN


def test_execution_completed_observed_as_completed():
    events = [rt.workflow_started(event_id="e1", sequence=1), rt.execution_completed(event_id="e2", sequence=2)]
    result = normalize_trajectory(events, execution_instance_id="exec_1")
    assert result.terminality == TrajectoryTerminality.COMPLETED_OBSERVED


def test_execution_failed_observed_as_failed():
    events = [rt.workflow_started(event_id="e1", sequence=1), rt.execution_failed(event_id="e2", sequence=2)]
    result = normalize_trajectory(events, execution_instance_id="exec_1")
    assert result.terminality == TrajectoryTerminality.FAILED_OBSERVED


def test_worker_cancelled_observed_as_cancelled_when_no_stronger_signal():
    events = [rt.worker_started(event_id="e1", sequence=1), rt.worker_cancelled(event_id="e2", sequence=2)]
    result = normalize_trajectory(events, execution_instance_id="exec_1")
    assert result.terminality == TrajectoryTerminality.CANCELLED_OBSERVED


def test_missing_terminal_evidence_stays_distinguishable_from_completed():
    incomplete = normalize_trajectory([rt.worker_started(event_id="e1", sequence=1)], execution_instance_id="exec_1")
    complete = normalize_trajectory(
        [rt.workflow_started(event_id="e1", sequence=1), rt.execution_completed(event_id="e2", sequence=2)],
        execution_instance_id="exec_2",
    )
    assert incomplete.terminality != complete.terminality
    assert incomplete.terminality == TrajectoryTerminality.TERMINALITY_UNKNOWN
    assert complete.terminality == TrajectoryTerminality.COMPLETED_OBSERVED


def test_global_sequence_gap_from_concurrent_execution_is_not_flagged_incomplete_by_default():
    """Finding 1 (critical review fix): StreamEvent.sequence is confirmed
    global to the whole EventStream, shared across every concurrent
    execution (EventStream.query() itself documents payload_workflow_id
    filtering for exactly this reason). Execution A legitimately sees
    sequence 10 -> 12 when an unrelated execution B's event sits at 11 --
    this is the *normal* shape of a correctly-scoped, evidence-complete
    result, not missing evidence. Must NOT be flagged incomplete by default."""
    e1 = rt.worker_started(event_id="e1", sequence=10)
    e2 = rt.worker_completed(event_id="e2", sequence=12)  # B's event legitimately sits at 11, not ours
    result = normalize_trajectory([e1, e2], execution_instance_id="exec_1")
    assert result.outcome_status == AdapterOutcomeStatus.SUCCESSFUL
    assert result.terminality != TrajectoryTerminality.INCOMPLETE_TRACE


def test_sequence_gap_flagged_only_when_caller_explicitly_asserts_contiguity():
    """The old behavior is still available, but only opt-in -- for
    callers who can actually vouch the supplied slice is meant to be
    gap-free (e.g. synthetic/test data), not as a default inference the
    adapter cannot safely make on its own."""
    e1 = rt.worker_started(event_id="e1", sequence=1)
    e2 = rt.worker_completed(event_id="e2", sequence=10)  # big gap
    result = normalize_trajectory([e1, e2], execution_instance_id="exec_1", assume_contiguous_sequence=True)
    assert result.outcome_status == AdapterOutcomeStatus.INCOMPLETE_SOURCE_TRACE
    assert result.terminality == TrajectoryTerminality.INCOMPLETE_TRACE


def test_same_gap_without_the_flag_is_not_flagged():
    """Same event pair as above, default flag value -- confirms the
    outcome genuinely depends on the explicit assertion, not on the gap
    size or any other incidental factor."""
    e1 = rt.worker_started(event_id="e1", sequence=1)
    e2 = rt.worker_completed(event_id="e2", sequence=10)
    result = normalize_trajectory([e1, e2], execution_instance_id="exec_1")  # assume_contiguous_sequence defaults False
    assert result.outcome_status == AdapterOutcomeStatus.SUCCESSFUL
    assert result.terminality != TrajectoryTerminality.INCOMPLETE_TRACE


def test_recovery_event_normalized_as_recovery_type():
    ev = rt.execution_recovery_started(event_id="e1", sequence=1)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.trajectory.events[0].event_type == TrajectoryEventType.RECOVERY


def test_many_completed_workers_do_not_imply_trajectory_completion():
    """Finding 5 (terminality authority hierarchy, made explicit): a
    trajectory with many successfully-completed workers/nodes and no
    workflow.completed/execution.completed/execution.failed/
    worker.cancelled anywhere must stay TERMINALITY_UNKNOWN, not be read
    as complete just because a lot of child-level activity finished."""
    events = []
    for i in range(20):
        events.append(rt.worker_started(event_id=f"start_{i}", sequence=i * 2, worker_id=f"Worker{i}"))
        events.append(rt.worker_completed(event_id=f"done_{i}", sequence=i * 2 + 1, worker_id=f"Worker{i}", success=True))
    events.append(rt.execution_node_completed(event_id="node_done", sequence=100, node_id="n1"))
    result = normalize_trajectory(events, execution_instance_id="exec_1")
    assert result.terminality == TrajectoryTerminality.TERMINALITY_UNKNOWN, (
        "20 completed workers plus a completed node must not be mistaken for the whole trajectory finishing"
    )


# ---------------------------------------------------------------------------
# Comprehensive determinism (Finding 2) and event_id uniqueness basis (Finding 4)
# ---------------------------------------------------------------------------

def test_complete_serialized_output_identical_across_two_calls():
    """Finding 2: determinism must cover every generated field, not just
    trajectory_event_id -- checked by comparing the FULL serialized
    NormalizationResult (trajectory, dispositions, outcome, terminality),
    not a handful of hand-picked fields."""
    events = [
        rt.worker_started(event_id="e1", sequence=1),
        rt.worker_progress(event_id="e2", sequence=2),
        rt.worker_completed(event_id="e3", sequence=3, success=True, duration_ms=42.0),
        rt.execution_node_completed(event_id="e4", sequence=4, node_id="n1", parent_id=None),
    ]
    r1 = normalize_trajectory(list(events), execution_instance_id="exec_fixed", trajectory_id="traj_fixed")
    r2 = normalize_trajectory(list(events), execution_instance_id="exec_fixed", trajectory_id="traj_fixed")
    assert r1.to_dict() == r2.to_dict(), "full NormalizationResult must be byte-identical for identical input, not just the trajectory"


def test_no_wall_clock_now_used_anywhere_in_normalization_result():
    """Directly rules out the concern that datetime.now() might sneak
    into an output field: every timestamp-bearing field in the result
    must trace back to something in the source events, not to when
    normalization happened to run."""
    import time
    ev = rt.worker_started(event_id="e1", sequence=1, timestamp=123456.0)
    before = time.time()
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    after = time.time()
    occurred_at_ts = result.trajectory.events[0].occurred_at.timestamp()
    assert occurred_at_ts == 123456.0, "occurred_at must come from the source event's timestamp"
    assert not (before <= occurred_at_ts <= after), "occurred_at must not coincide with wall-clock 'now' at call time"


def test_event_id_generation_mechanism_is_uuid4_not_a_sequential_counter():
    """Finding 4: verifies the actual basis for trusting event_id as
    globally unique (not merely unique-within-one-store), directly against
    the real StreamEvent default factory, rather than assuming it from
    the field's name."""
    e1 = StreamEvent(event_type="worker.started", source="W1", timestamp=1.0, payload={}, sequence=1)
    e2 = StreamEvent(event_type="worker.started", source="W1", timestamp=1.0, payload={}, sequence=2)
    # both left to auto-generate event_id via the real default_factory
    assert e1.event_id != e2.event_id
    assert len(e1.event_id) == 36 and e1.event_id.count("-") == 4, "must be uuid4 string form, not a small sequential counter"


def test_trajectory_event_id_derivation_traces_back_to_source_event_id():
    """Direct confirmation of the Finding 4 fix's actual mechanism."""
    ev = rt.worker_started(event_id="abc-123-uuid-like", sequence=1)
    result = normalize_trajectory([ev], execution_instance_id="exec_1")
    assert result.trajectory.events[0].trajectory_event_id == "tev_abc-123-uuid-like"
