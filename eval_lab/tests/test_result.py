"""Result/aggregate/metric/comparison tests — §19, §56-58 of the Slice 2 brief,
plus correction-pass coverage for immutability (Correction 2) and metric
lineage (Correction 3)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from eval_lab.contracts.enums import ConfidenceLevel, EvaluatorResultStatus, EvidenceCapturePolicy, EvidenceOrigin, TrustClassification
from eval_lab.contracts.evidence import Evidence, EvidenceFreshness
from eval_lab.contracts.result import (
    ComparisonResult,
    EvaluationAggregate,
    EvaluationResult,
    EvaluatorRelationship,
    EvaluatorRelationshipType,
    MetricObservation,
)
from eval_lab.contracts.serialization import ContractValidationError

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _evidence() -> Evidence:
    return Evidence(evidence_id="ev1", origin=EvidenceOrigin.ENVIRONMENT_GENERATED, trust_classification=TrustClassification.VALIDATED,
                     capture_policy=EvidenceCapturePolicy.FULL, freshness=EvidenceFreshness(captured_at=NOW), state_predicate_description="x")


@pytest.mark.parametrize("status", [EvaluatorResultStatus.PASS, EvaluatorResultStatus.FAIL, EvaluatorResultStatus.PARTIAL])
def test_pass_fail_partial_require_evidence(status):
    with pytest.raises(ContractValidationError, match="result_requires_evidence"):
        EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=status, score=0.5, confidence=ConfidenceLevel.HIGH, evidence=())


@pytest.mark.parametrize("status", [EvaluatorResultStatus.INSUFFICIENT_EVIDENCE, EvaluatorResultStatus.NOT_EVALUATED, EvaluatorResultStatus.ERROR])
def test_abstention_error_not_evaluated_do_not_require_evidence(status):
    r = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=status, score=None, confidence=ConfidenceLevel.LOW, evidence=())
    assert r.status == status


def test_score_none_is_distinct_from_score_zero():
    r_none = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                               score=None, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))
    r_zero = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.FAIL,
                               score=0.0, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))
    assert r_none.score is None
    assert r_zero.score == 0.0
    assert r_none.score != r_zero.score  # explicitly: None and 0.0 must never be conflated


def test_score_out_of_range_rejected():
    with pytest.raises(ContractValidationError, match="score_out_of_range"):
        EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                          score=1.5, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))


def test_confidence_rejects_non_enum_value():
    """Correction pass (4): confidence was a raw str with manual
    membership checking; now ConfidenceLevel, enforced by isinstance."""
    with pytest.raises(ContractValidationError, match="confidence_not_enum_member"):
        EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                          score=1.0, confidence="high", evidence=(_evidence(),))


def test_evaluator_relationship_type_is_a_closed_enum():
    """Correction pass (5): relationship_type was a raw str with manual
    membership checking; now EvaluatorRelationshipType."""
    rel = EvaluatorRelationship(related_evaluator_id="e2", related_evaluator_version=1, relationship_type=EvaluatorRelationshipType.CONTRADICTORY)
    assert rel.to_dict()["relationship_type"] == "contradictory"
    with pytest.raises(ContractValidationError, match="relationship_type_not_enum_member"):
        EvaluatorRelationship(related_evaluator_id="e2", related_evaluator_version=1, relationship_type="unrelated_nonsense")


def test_metric_observation_negative_n_rejected():
    with pytest.raises(ContractValidationError, match="negative_n"):
        MetricObservation(metric_name="pass_rate", value=0.5, n=-1)


def test_metric_observation_carries_population_lineage():
    """Correction pass (3): MetricObservation previously had no reference
    back to which population it was computed over -- only recoverable
    indirectly via an enclosing ComparisonResult.experiment_id, and not
    at all for a standalone metric. population_id closes that gap."""
    m = MetricObservation(metric_name="pass_rate", value=0.82, n=50, population_id="pop_smoke_v3")
    assert m.population_id == "pop_smoke_v3"
    assert m.to_dict()["population_id"] == "pop_smoke_v3"


def test_metric_observation_population_id_defaults_to_none_not_a_fake_value():
    m = MetricObservation(metric_name="pass_rate", value=0.5, n=10)
    assert m.population_id is None


def test_two_metrics_from_different_populations_are_not_silently_conflated():
    """The population_id field, once populated, makes it possible for a
    reader to notice two metrics came from different populations --
    ComparisonResult does not enforce they match (a common legitimate
    comparison is baseline vs. candidate over the *same* population), but
    the information needed to check is no longer absent."""
    m1 = MetricObservation(metric_name="pass_rate", value=0.70, n=20, population_id="pop_a")
    m2 = MetricObservation(metric_name="pass_rate", value=0.85, n=20, population_id="pop_b")
    cmp = ComparisonResult(baseline_metric=m1, candidate_metric=m2)
    assert cmp.baseline_metric.population_id != cmp.candidate_metric.population_id
    assert cmp.baseline_metric.population_id == "pop_a" and cmp.candidate_metric.population_id == "pop_b"


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
                          score=1.0, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))
    agg = EvaluationAggregate(evaluation_run_id="run1", per_dimension={"d": r}, overall_status=EvaluatorResultStatus.PASS)
    cmp = ComparisonResult(baseline_metric=MetricObservation(metric_name="m", value=1, n=1),
                            candidate_metric=MetricObservation(metric_name="m", value=1, n=1))
    assert type(r) is not type(agg) is not type(cmp)
    assert not isinstance(r, type(agg)) and not isinstance(agg, type(cmp))


def test_evaluation_aggregate_per_dimension_is_actually_immutable():
    """Correction pass (2): per_dimension was a plain dict on a frozen
    dataclass -- frozen=True blocked reassignment but not in-place
    mutation. Now a MappingProxyType; this test proves the mutation
    itself is what's blocked, not just attribute reassignment (which was
    already blocked before and would not have caught this bug)."""
    r = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                          score=1.0, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))
    agg = EvaluationAggregate(evaluation_run_id="run1", per_dimension={"d": r}, overall_status=EvaluatorResultStatus.PASS)

    assert isinstance(agg.per_dimension, MappingProxyType)
    with pytest.raises(TypeError):
        agg.per_dimension["d"] = r  # in-place mutation must fail, not just attribute reassignment
    with pytest.raises(TypeError):
        agg.per_dimension["new_key"] = r  # adding a new key must also fail


def test_evaluation_aggregate_equality_unaffected_by_mappingproxy_wrapping():
    """Confirms the immutability fix didn't break equality semantics --
    two aggregates built from equivalent dicts must still compare equal."""
    r = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                          score=1.0, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))
    agg1 = EvaluationAggregate(evaluation_run_id="run1", per_dimension={"d": r}, overall_status=EvaluatorResultStatus.PASS)
    agg2 = EvaluationAggregate(evaluation_run_id="run1", per_dimension={"d": r}, overall_status=EvaluatorResultStatus.PASS)
    assert agg1 == agg2


def test_evaluation_aggregate_serializes_deterministically_after_immutability_fix():
    r = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d", status=EvaluatorResultStatus.PASS,
                          score=1.0, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))
    agg = EvaluationAggregate(evaluation_run_id="run1", per_dimension={"d": r}, overall_status=EvaluatorResultStatus.PASS)
    import json
    d = agg.to_dict()
    assert isinstance(d["per_dimension"], dict)  # MappingProxyType converted back to plain dict for serialization
    json.dumps(d)  # must not raise
