"""Trajectory tests — §19-20, §37-42 original architecture; §34-43 Slice 2 brief."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.enums import CausalRelationType, OrderingRelation
from eval_lab.contracts.serialization import ContractValidationError
from eval_lab.contracts.trajectory import (
    BranchPoint,
    CausalReference,
    Checkpoint,
    CounterfactualEvaluation,
    EvaluationBranch,
    Intervention,
    SharedPrefix,
    Trajectory,
    TrajectoryEvent,
    TrajectoryEventType,
    TrajectorySnapshot,
)

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _event(seq: int, **overrides) -> TrajectoryEvent:
    defaults = dict(trajectory_event_id=f"ev{seq}", event_type=TrajectoryEventType.TOOL_CALL,
                     raw_type_name="tool.bash", occurred_at=NOW, monotonic_sequence=seq)
    defaults.update(overrides)
    return TrajectoryEvent(**defaults)


def test_trajectory_requires_sequence_order():
    with pytest.raises(ContractValidationError, match="events_not_in_sequence_order"):
        Trajectory(trajectory_id="t1", execution_instance_id="e1", events=(_event(1), _event(0)))


def test_trajectory_in_order_is_valid():
    traj = Trajectory(trajectory_id="t1", execution_instance_id="e1", events=(_event(0), _event(1), _event(2)))
    assert len(traj.events) == 3


def test_unknown_event_type_preserves_raw_type_name():
    """§35: the controlled extensibility boundary -- an event type the
    enum doesn't recognize yet becomes UNKNOWN without losing information."""
    ev = _event(0, event_type=TrajectoryEventType.UNKNOWN, raw_type_name="future.exotic_thing")
    d = ev.to_dict()
    assert d["event_type"] == "unknown"
    assert d["raw_type_name"] == "future.exotic_thing"


def test_concurrent_events_do_not_force_false_total_order():
    """§37: a sequence number is not permission to assume causal order --
    two adjacent events may be explicitly marked CONCURRENT."""
    e0 = _event(0)
    e1 = _event(1, ordering_relation_to_previous=OrderingRelation.CONCURRENT)
    traj = Trajectory(trajectory_id="t1", execution_instance_id="e1", events=(e0, e1))
    assert traj.events[1].ordering_relation_to_previous == OrderingRelation.CONCURRENT


def test_causal_references_distinguish_relation_types():
    """§38: caused_by != derived_from != related_to -- confirmed by
    constructing both on the same event without collapsing them."""
    ev = _event(1, causal_references=(
        CausalReference(relation=CausalRelationType.CAUSED_BY, target_event_id="ev0"),
        CausalReference(relation=CausalRelationType.DERIVED_FROM, target_event_id="ev0"),
    ))
    relations = {c.relation for c in ev.causal_references}
    assert relations == {CausalRelationType.CAUSED_BY, CausalRelationType.DERIVED_FROM}


def test_negative_duration_rejected():
    with pytest.raises(ContractValidationError, match="negative_duration"):
        _event(0, duration_ms=-5.0)


def test_checkpoint_progress_bounds():
    with pytest.raises(ContractValidationError, match="expected_progress_out_of_range"):
        Checkpoint(checkpoint_id="cp1", trajectory_id="t1", state_predicate_description="x", expected_progress=1.5)


def test_checkpoint_progress_is_not_assumed_linear():
    """§42/§43: checkpoint 3 of 5 is not automatically 60% -- each
    checkpoint's own expected_progress is independent."""
    cps = [
        Checkpoint(checkpoint_id="cp1", trajectory_id="t1", state_predicate_description="setup done", expected_progress=0.1),
        Checkpoint(checkpoint_id="cp2", trajectory_id="t1", state_predicate_description="core logic done", expected_progress=0.8),
        Checkpoint(checkpoint_id="cp3", trajectory_id="t1", state_predicate_description="cleanup done", expected_progress=0.85),
    ]
    progresses = [c.expected_progress for c in cps]
    assert progresses != sorted(range(len(progresses)))  # not a naive linear i/N sequence
    assert progresses[1] - progresses[0] > progresses[2] - progresses[1]  # big jump then small jump -- non-linear, as intended


def test_branch_not_yet_executed_has_no_branch_trajectory():
    snap = TrajectorySnapshot(snapshot_id="s1", trajectory_id="t1", event_boundary_id="ev1",
                               state_reference="ref1", reproducibility_context="seed=1", created_at=NOW)
    sp = SharedPrefix(parent_trajectory_id="t1", shared_event_ids=("ev0", "ev1"))
    bp = BranchPoint(branch_point_id="bp1", snapshot=snap)
    branch = EvaluationBranch(branch_id="b1", shared_prefix=sp, branch_point=bp, branch_label="variant-a")
    assert branch.branch_trajectory_id is None, "Slice 2 defines branches, does not execute them (§40, §2 scope boundary)"


def test_counterfactual_evaluation_never_claims_causal_certainty():
    """§41: 'do not encode causal certainty into the contract' -- there is
    no field that lets a caller assert a proven cause; only a hedged note."""
    snap = TrajectorySnapshot(snapshot_id="s1", trajectory_id="t1", event_boundary_id="ev1",
                               state_reference="ref1", reproducibility_context="seed=1", created_at=NOW)
    bp = BranchPoint(branch_point_id="bp1", snapshot=snap)
    interv = Intervention(intervention_id="iv1", branch_point=bp, intervention_type="remove_tool", description="remove bash")
    cf = CounterfactualEvaluation(counterfactual_evaluation_id="cf1", baseline_trajectory_id="t1", intervention=interv)
    assert "correlational" in cf.causal_confidence_note
    assert not hasattr(cf, "proven_cause")
    assert not hasattr(cf, "causal_certainty")
