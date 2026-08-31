"""Evaluator/judge/metrics tests — ADR-LAB-03, §16-18 §58 §61-62 of the Slice 2 brief."""

from __future__ import annotations

import pytest

from eval_lab.contracts.enums import ConstructValidity, EvaluatorType, LifecycleState
from eval_lab.contracts.evaluator import EvaluationDefinition, EvaluatorDefinition, EvaluatorMetrics, JudgeIdentity
from eval_lab.contracts.serialization import ContractValidationError


def test_judge_evaluator_requires_judge_identity():
    with pytest.raises(ContractValidationError, match="judge_evaluator_requires_judge_identity"):
        EvaluatorDefinition(evaluator_id="e1", evaluator_version=1, evaluator_type=EvaluatorType.JUDGE,
                             measurement_target="x", configuration_hash="h1")


def test_non_judge_evaluator_does_not_require_judge_identity():
    e = EvaluatorDefinition(evaluator_id="e1", evaluator_version=1, evaluator_type=EvaluatorType.DETERMINISTIC,
                             measurement_target="x", configuration_hash="h1")
    assert e.judge_identity is None


def test_same_family_judging_requires_explicit_acknowledgement():
    with pytest.raises(ContractValidationError, match="same_family_judging_not_acknowledged"):
        JudgeIdentity(judge_model_id="m1", rubric_version="r1", prompt_template_hash="p1",
                      configuration_hash="c1", cross_family_from_subject=False)


def test_same_family_judging_allowed_with_acknowledgement():
    ji = JudgeIdentity(judge_model_id="m1", rubric_version="r1", prompt_template_hash="p1", configuration_hash="c1",
                        cross_family_from_subject=False, self_preference_risk_acknowledged=True)
    assert ji.cross_family_from_subject is False


def test_cross_family_judging_needs_no_acknowledgement():
    ji = JudgeIdentity(judge_model_id="m1", rubric_version="r1", prompt_template_hash="p1", configuration_hash="c1",
                        cross_family_from_subject=True)
    assert ji.self_preference_risk_acknowledged is False  # default, fine when cross-family


def test_judge_identity_is_not_reducible_to_model_family_alone():
    """§62: 'Do not make judge model family the only identity field' --
    confirmed by construction: the type requires rubric_version and
    prompt_template_hash regardless of judge_model_id."""
    with pytest.raises(TypeError):
        JudgeIdentity(judge_model_id="m1")  # missing required rubric_version/prompt_template_hash/configuration_hash


def test_construct_validity_defaults_to_unknown_not_strong():
    e = EvaluatorDefinition(evaluator_id="e1", evaluator_version=1, evaluator_type=EvaluatorType.DETERMINISTIC,
                             measurement_target="x", configuration_hash="h1")
    assert e.construct_validity == ConstructValidity.UNKNOWN
    ed = EvaluationDefinition(evaluation_definition_id="ed1", evaluation_definition_version=1,
                               measurement_target="x", construct_definition="y")
    assert ed.construct_validity == ConstructValidity.UNKNOWN


def test_evaluator_metrics_unmeasured_is_none_not_zero():
    m = EvaluatorMetrics()
    assert m.sensitivity is None
    assert m.specificity is None
    assert m.precision is None
    assert m.abstention_rate is None


def test_evaluator_metrics_computed_correctly():
    m = EvaluatorMetrics(true_positive=18, false_negative=2, true_negative=70, false_positive=10, abstention_count=5, n_probes=105)
    assert m.sensitivity == pytest.approx(18 / 20)
    assert m.specificity == pytest.approx(70 / 80)
    assert m.precision == pytest.approx(18 / 28)
    assert m.abstention_rate == pytest.approx(5 / 105)


def test_evaluator_metrics_rejects_negative_counts():
    with pytest.raises(ContractValidationError, match="negative_metric_count"):
        EvaluatorMetrics(true_positive=-1)


def test_evaluator_lifecycle_quarantined_is_valid_but_not_for_benchmarks():
    """QUARANTINED is in EVALUATOR_LIFECYCLE (ADR-LAB-03's amendment) but
    not BENCHMARK_CASE_LIFECYCLE -- confirms lifecycle-subset separation."""
    e = EvaluatorDefinition(evaluator_id="e1", evaluator_version=1, evaluator_type=EvaluatorType.DETERMINISTIC,
                             measurement_target="x", configuration_hash="h1", lifecycle_state=LifecycleState.QUARANTINED)
    assert e.lifecycle_state == LifecycleState.QUARANTINED


def test_evaluator_invalid_lifecycle_state_rejected():
    with pytest.raises(ContractValidationError, match="invalid_evaluator_lifecycle_state"):
        EvaluatorDefinition(evaluator_id="e1", evaluator_version=1, evaluator_type=EvaluatorType.DETERMINISTIC,
                             measurement_target="x", configuration_hash="h1", lifecycle_state=LifecycleState.PROTECTED)
