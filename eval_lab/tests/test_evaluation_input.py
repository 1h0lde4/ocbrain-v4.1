"""Evaluation input snapshot tests — §22, §28, §76 of the Slice 2 brief."""

from __future__ import annotations

import pytest

from eval_lab.contracts.enums import EvidenceCapturePolicy
from eval_lab.contracts.evaluation_input import EvaluationInputSnapshot
from eval_lab.contracts.serialization import ContractValidationError


def test_none_means_full_trajectory_distinct_from_empty_tuple():
    full = EvaluationInputSnapshot(evaluator_id="e1", evaluator_version=1, evaluation_definition_id="ed1",
                                    trajectory_id="t1", included_event_ids=None, capture_policy=EvidenceCapturePolicy.FULL)
    none_shown = EvaluationInputSnapshot(evaluator_id="e1", evaluator_version=1, evaluation_definition_id="ed1",
                                          trajectory_id="t1", included_event_ids=(), capture_policy=EvidenceCapturePolicy.REDACTED)
    assert full.to_dict()["included_event_ids"] is None
    assert none_shown.to_dict()["included_event_ids"] == []
    assert full.included_event_ids is not none_shown.included_event_ids


def test_two_evaluators_can_have_distinct_views_of_same_run():
    """§76: a deterministic evaluator and a human reviewer may see
    different views of the same run's trajectory -- both snapshots
    reference the same trajectory_id but differ in scope/policy."""
    deterministic_view = EvaluationInputSnapshot(
        evaluator_id="e_det", evaluator_version=1, evaluation_definition_id="ed1",
        trajectory_id="t1", included_event_ids=None, capture_policy=EvidenceCapturePolicy.FULL,
    )
    human_view = EvaluationInputSnapshot(
        evaluator_id="e_human", evaluator_version=1, evaluation_definition_id="ed1",
        trajectory_id="t1", included_event_ids=("ev3", "ev4"), capture_policy=EvidenceCapturePolicy.REDACTED,
        curation_note="redacted per privacy policy; only final two steps shown",
    )
    assert deterministic_view.trajectory_id == human_view.trajectory_id
    assert deterministic_view.included_event_ids != human_view.included_event_ids
    assert deterministic_view.capture_policy != human_view.capture_policy


def test_rejects_duplicate_included_event_ids():
    with pytest.raises(ContractValidationError, match="duplicate_included_event_ids"):
        EvaluationInputSnapshot(evaluator_id="e1", evaluator_version=1, evaluation_definition_id="ed1",
                                 trajectory_id="t1", included_event_ids=("ev1", "ev1"),
                                 capture_policy=EvidenceCapturePolicy.FULL)
