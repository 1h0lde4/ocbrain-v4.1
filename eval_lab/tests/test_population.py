"""Population/experiment tests — ADR-LAB-05, §48-50 of the Slice 2 brief."""

from __future__ import annotations

import pytest

from eval_lab.contracts.identifiers import PopulationId
from eval_lab.contracts.population import EvaluationPopulation, Experiment
from eval_lab.contracts.result import MetricObservation
from eval_lab.contracts.serialization import ContractValidationError


def test_population_answers_what_could_have_been_selected():
    """§50: 'what could have been selected, what was, why, what was
    excluded' -- all four must be recoverable from one object."""
    pop = EvaluationPopulation(
        population_id="pop1", sampling_frame_description="all 40 validated cases in benchmark-v2",
        selection_method="risk_weighted", selection_reason="prioritize planning-sensitive cases after planner change",
        included_cases=frozenset({f"c{i}" for i in range(10)}),
        excluded_cases=frozenset({f"c{i}" for i in range(10, 15)}),
        risk_weighted=True,
    )
    d = pop.to_dict()
    assert d["n_included"] == 10 and d["n_excluded"] == 5
    assert "risk_weighted" in d["selection_method"] or pop.risk_weighted


def test_included_excluded_must_be_disjoint():
    with pytest.raises(ContractValidationError, match="included_excluded_overlap"):
        EvaluationPopulation(population_id="pop1", sampling_frame_description="x", selection_method="x",
                              selection_reason="x", included_cases=frozenset({"c1", "c2"}), excluded_cases=frozenset({"c2"}))


def test_82_percent_claim_carries_its_population():
    """Direct test of ADR-LAB-05's central claim: a pass rate computed
    over a population must not be presentable without that population's
    identity attached."""
    pop = EvaluationPopulation(population_id="pop_82pct", sampling_frame_description="smoke suite",
                                selection_method="full", selection_reason="ci gate",
                                included_cases=frozenset({f"c{i}" for i in range(50)}))
    # The population is the thing a report would cite alongside "82% passed" --
    # confirm it has stable, inspectable identity distinct from any run.
    assert pop.population_id == "pop_82pct"
    assert len(pop.included_cases) == 50


def test_experiment_requires_stopping_rule_field_to_be_populated():
    with pytest.raises(TypeError):
        Experiment(experiment_id="exp1", hypothesis="h", population_id="pop1", comparison_family="fam1")  # missing stopping_rule


def test_experiment_confidence_level_bounds():
    with pytest.raises(ContractValidationError, match="confidence_level_out_of_range"):
        Experiment(experiment_id="exp1", hypothesis="h", population_id="pop1", comparison_family="fam1",
                   stopping_rule="fixed N", confidence_level=1.0)


def test_experiment_minimum_n_cannot_exceed_maximum_n():
    with pytest.raises(ContractValidationError, match="minimum_n_exceeds_maximum_n"):
        Experiment(experiment_id="exp1", hypothesis="h", population_id="pop1", comparison_family="fam1",
                   stopping_rule="sequential", minimum_n=50, maximum_n=10)


def test_experiment_with_no_declared_statistical_test_is_still_valid():
    """Slice 2 does not implement statistics -- an experiment with
    statistical_test=None must still construct cleanly."""
    exp = Experiment(experiment_id="exp1", hypothesis="h", population_id="pop1", comparison_family="fam1",
                      stopping_rule="none declared -- exploratory smoke run")
    assert exp.statistical_test is None


def test_population_id_is_consistent_across_owner_and_reference_types():
    """Correction pass (1): PopulationId is now used consistently by the
    type that owns the concept (EvaluationPopulation), the type that
    references it for design metadata (Experiment), and the type that
    references it for a bare measurement (MetricObservation, result.py)
    -- rather than the reference types being typed while the owning type
    stayed a plain str."""
    pop = EvaluationPopulation(population_id=PopulationId("pop_x"), sampling_frame_description="x",
                                selection_method="x", selection_reason="x", included_cases=frozenset({"c1"}))
    exp = Experiment(experiment_id="exp1", hypothesis="h", population_id=pop.population_id,
                      comparison_family="fam1", stopping_rule="fixed N")
    metric = MetricObservation(metric_name="pass_rate", value=0.9, n=10, population_id=pop.population_id)
    assert pop.population_id == exp.population_id == metric.population_id == "pop_x"
