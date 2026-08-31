"""Result/aggregate/metric/comparison tests — §19, §56-58 of the Slice 2 brief."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.enums import EvaluatorResultStatus, EvidenceCapturePolicy, EvidenceOrigin, TrustClassification
from eval_lab.contracts.evidence import Evidence, EvidenceFreshness
from eval_lab.contracts.result import ComparisonResult, EvaluationAggregate, EvaluationResult, EvaluatorRelationship, MetricObservation
from eval_lab.contracts.serialization import ContractValidationError

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _evidence() -> Evidence:
    return Evidence(evidence_id="ev1", origin=EvidenceOrigin.ENVIRONMENT_GENERATED, trust_classification=TrustClassification.VALIDATED,
                     capture_policy=EvidenceCapturePolicy.FULL, freshness=EvidenceFreshness(captured_at=NOW), state_predicate_description="x")


@pytest.mark.parametrize("status", [EvaluatorResultStatus.PASS, EvaluatorResultStatus.FAIL, EvaluatorResultStatus.PARTIAL])
def test_pass_fail_partial_require_evidence(status):
    with pytest.raises(ContractValidationError, match="result_requires_evidence"):
        EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=status, score=0.5, confidence="high", evidence=())


@pytest.mark.parametrize("status", [EvaluatorResultStatus.INSUFFICIENT_EVIDENCE, EvaluatorResultStatus.NOT_EVALUATED, EvaluatorResultStatus.ERROR])
def test_abstention_error_not_evaluated_do_not_require_evidence(status):
    r = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=status, score=None, confidence="low", evidence=())
    assert r.status == status


def test_score_none_is_distinct_from_score_zero():
    r_none = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                               score=None, confidence="high", evidence=(_evidence(),))
    r_zero = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.FAIL,
                               score=0.0, confidence="high", evidence=(_evidence(),))
    assert r_none.score is None
    assert r_zero.score == 0.0
    assert r_none.score != r_zero.score  # explicitly: None and 0.0 must never be conflated


def test_score_out_of_range_rejected():
    with pytest.raises(ContractValidationError, match="score_out_of_range"):
        EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                          score=1.5, confidence="high", evidence=(_evidence(),))


def test_evaluator_relationship_type_validated():
    with pytest.raises(ContractValidationError, match="invalid_evaluator_relationship_type"):
        EvaluatorRelationship(related_evaluator_id="e2", related_evaluator_version=1, relationship_type="unrelated_nonsense")


def test_metric_observation_negative_n_rejected():
    with pytest.raises(ContractValidationError, match="negative_n"):
        MetricObservation(metric_name="pass_rate", value=0.5, n=-1)


def test_comparison_requires_matching_metric_names():
    with pytest.raises(ContractValidationError, match="mismatched_metric_names"):
        ComparisonResult(
            baseline_metric=MetricObservation(metric_name="pass_rate", value=0.7, n=20),
            candidate_metric=MetricObservation(metric_name="latency_ms", value=500, n=20),
        )


def test_incomparable_without_caveats_rejected():
    with pytest.raises(ContractValidationError, match="incomparable_requires_caveats"):
        ComparisonResult(
            baseline_metric=MetricObservation(metric_name="pass_rate", value=0.7, n=20),
            candidate_metric=MetricObservation(metric_name="pass_rate", value=0.9, n=5),
            is_comparable=False,
        )


def test_raw_delta_computed_not_stored_redundantly():
    cmp = ComparisonResult(
        baseline_metric=MetricObservation(metric_name="pass_rate", value=0.70, n=20),
        candidate_metric=MetricObservation(metric_name="pass_rate", value=0.85, n=20),
    )
    assert cmp.raw_delta == pytest.approx(0.15)


def test_one_result_does_not_equal_aggregate_does_not_equal_comparison():
    """§19's critical invariant, checked as an actual type-level fact:
    the three types are not interchangeable and not subclasses of each
    other."""
    r = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                          score=1.0, confidence="high", evidence=(_evidence(),))
    agg = EvaluationAggregate(evaluation_run_id="run1", per_dimension={"d": r}, overall_status=EvaluatorResultStatus.PASS)
    cmp = ComparisonResult(baseline_metric=MetricObservation(metric_name="m", value=1, n=1),
                            candidate_metric=MetricObservation(metric_name="m", value=1, n=1))
    assert type(r) is not type(agg) is not type(cmp)
    assert not isinstance(r, type(agg)) and not isinstance(agg, type(cmp))
