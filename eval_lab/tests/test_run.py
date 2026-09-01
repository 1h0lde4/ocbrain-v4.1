"""EvaluationRun tests — the capstone contract. §71 cross-field invariants,
§56-57 evaluator disagreement, §75 error/failure/status separation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.enums import ConfidenceLevel, EvaluationStatus, EvaluatorResultStatus, EvidenceCapturePolicy, EvidenceOrigin, TrustClassification, FaultDomain
from eval_lab.contracts.evidence import Evidence, EvidenceFreshness
from eval_lab.contracts.result import EvaluationResult
from eval_lab.contracts.run import EvaluationRun, ExecutionReference
from eval_lab.contracts.serialization import ContractValidationError

from eval_lab.tests import fixtures as fx

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _evidence() -> Evidence:
    return Evidence(evidence_id="ev1", origin=EvidenceOrigin.ENVIRONMENT_GENERATED, trust_classification=TrustClassification.VALIDATED,
                     capture_policy=EvidenceCapturePolicy.FULL, freshness=EvidenceFreshness(captured_at=NOW), state_predicate_description="x")


def test_minimal_run_from_fixtures_is_valid():
    run = fx.minimal_run()
    assert run.status == EvaluationStatus.COMPLETED
    assert run.results


def test_multiple_evaluators_can_disagree_without_overwriting_each_other():
    """§56: 'oracle = PASS, judge = FAIL, human = PARTIAL simultaneously.'
    This is the single most direct test of that requirement."""
    oracle_result = EvaluationResult(evaluator_id="oracle_1", evaluator_version=1, dimension="correctness",
                                      status=EvaluatorResultStatus.PASS, score=1.0, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))
    judge_result = EvaluationResult(evaluator_id="judge_1", evaluator_version=1, dimension="correctness",
                                     status=EvaluatorResultStatus.FAIL, score=0.2, confidence=ConfidenceLevel.MEDIUM, evidence=(_evidence(),))
    human_result = EvaluationResult(evaluator_id="human_1", evaluator_version=1, dimension="correctness",
                                     status=EvaluatorResultStatus.PARTIAL, score=0.5, confidence=ConfidenceLevel.HIGH, evidence=(_evidence(),))

    run = fx.minimal_run(results=(oracle_result, judge_result, human_result))

    statuses = {r.evaluator_id: r.status for r in run.results}
    assert statuses == {
        "oracle_1": EvaluatorResultStatus.PASS,
        "judge_1": EvaluatorResultStatus.FAIL,
        "human_1": EvaluatorResultStatus.PARTIAL,
    }, "all three must survive simultaneously, none overwriting another"
    assert len(run.results) == 3


def test_fault_status_requires_fault_domain():
    with pytest.raises(ContractValidationError, match="fault_status_requires_fault_domain"):
        fx.minimal_run(status=EvaluationStatus.ERROR, fault_domain=None, results=())


def test_fault_domain_requires_fault_status():
    with pytest.raises(ContractValidationError, match="fault_domain_without_fault_status"):
        fx.minimal_run(status=EvaluationStatus.COMPLETED, fault_domain=FaultDomain.EVALUATOR)


@pytest.mark.parametrize("domain", list(FaultDomain))
def test_every_fault_domain_is_representable_on_an_errored_run(domain):
    """The amendment invariant list (#21-24): subject != environment !=
    oracle != evaluator != judge != data != integrity != infrastructure
    failure. Every single one must be constructible as the cause of a
    FAILED run, not just a curated subset."""
    run = fx.minimal_run(status=EvaluationStatus.FAILED, fault_domain=domain, results=())
    assert run.fault_domain == domain


def test_evaluator_crash_is_not_subject_failure():
    """The specific discriminating case the amendment repeatedly calls
    out: an evaluator crashing must be representable WITHOUT implying the
    subject (the agent under test) failed the task."""
    run = fx.minimal_run(status=EvaluationStatus.ERROR, fault_domain=FaultDomain.EVALUATOR, results=())
    assert run.fault_domain == FaultDomain.EVALUATOR
    assert run.fault_domain != FaultDomain.SUBJECT
    # No field on EvaluationRun asserts "subject succeeded" or "subject
    # failed" independently of fault_domain -- confirming the contract
    # doesn't smuggle in an implicit subject-failure claim via `status`
    # alone. status=ERROR here says nothing about the subject at all.


def test_incomplete_oracle_reference_rejected():
    with pytest.raises(ContractValidationError, match="incomplete_oracle_reference"):
        fx.minimal_run(oracle_id="or_1", oracle_version=None)


def test_incomplete_simulator_reference_rejected():
    with pytest.raises(ContractValidationError, match="incomplete_simulator_reference"):
        fx.minimal_run(simulator_id="sim_1", simulator_version=None)


def test_complete_oracle_reference_is_valid():
    run = fx.minimal_run(oracle_id="or_1", oracle_version=1)
    assert run.oracle_id == "or_1" and run.oracle_version == 1


def test_abstained_result_with_score_rejected_at_run_level():
    abstained_with_score = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d",
                                             status=EvaluatorResultStatus.INSUFFICIENT_EVIDENCE, score=0.5,
                                             confidence=ConfidenceLevel.LOW, evidence=())
    with pytest.raises(ContractValidationError, match="abstained_result_has_score"):
        fx.minimal_run(results=(abstained_with_score,))


def test_abstained_result_without_score_is_valid():
    abstained_clean = EvaluationResult(evaluator_id="e1", evaluator_version=1, dimension="d",
                                        status=EvaluatorResultStatus.INSUFFICIENT_EVIDENCE, score=None,
                                        confidence=ConfidenceLevel.LOW, evidence=())
    run = fx.minimal_run(results=(abstained_clean,))
    assert run.results[0].score is None


def test_execution_reference_completed_before_started_rejected():
    with pytest.raises(ContractValidationError, match="completed_before_started"):
        ExecutionReference(execution_instance_id="e1", agent_id="ocbrain", agent_version="v1", runtime_version="r1",
                            started_at=NOW, completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_run_requires_evaluation_case_id():
    with pytest.raises(ContractValidationError, match="run_requires_evaluation_case_id"):
        fx.minimal_run(evaluation_case_id="")


def test_full_run_is_json_serializable():
    import json
    run = fx.minimal_run()
    payload = json.dumps(run.to_dict())
    reloaded = json.loads(payload)
    assert reloaded["evaluation_run_id"] == "run_smoke"
    assert reloaded["status"] == "completed"


def test_run_references_evaluation_definition_by_id_and_version_not_embedded():
    """Correction pass (1): EvaluationRun previously embedded the full
    EvaluationDefinition object, inconsistent with how benchmark,
    environment, oracle, and simulator are all handled on this same type
    (id+version reference pairs). Now fixed to match."""
    run = fx.minimal_run(evaluation_definition_id="ed_1", evaluation_definition_version=3)
    assert run.evaluation_definition_id == "ed_1"
    assert run.evaluation_definition_version == 3
    d = run.to_dict()
    assert d["evaluation_definition_id"] == "ed_1"
    assert d["evaluation_definition_version"] == 3
    # the run must not carry an embedded object -- no "evaluation_definition"
    # key (the old field name) should exist anywhere in the serialized output
    assert "evaluation_definition" not in d


def test_run_evaluation_definition_reference_survives_later_version_publication():
    """A later version of the same EvaluationDefinition existing elsewhere
    must not retroactively change what this historical run recorded it
    used -- the run only ever held the id+version pair, never a live
    reference to a mutable/evolving object, so there is nothing for a
    later publication to retroactively alter."""
    run_v1 = fx.minimal_run(evaluation_definition_id="ed_1", evaluation_definition_version=1)
    # Simulate "a v2 of ed_1 now exists elsewhere" -- nothing about run_v1
    # changes, because it never held anything but the identity pair.
    run_v2 = fx.minimal_run(evaluation_run_id="run_smoke_2", evaluation_definition_id="ed_1", evaluation_definition_version=2)
    assert run_v1.evaluation_definition_version == 1
    assert run_v2.evaluation_definition_version == 2
    assert run_v1.evaluation_definition_version != run_v2.evaluation_definition_version


def test_incomplete_evaluation_definition_reference_rejected():
    with pytest.raises(ContractValidationError, match="incomplete_evaluation_definition_reference"):
        fx.minimal_run(evaluation_definition_id="ed_1", evaluation_definition_version=None)
    with pytest.raises(ContractValidationError, match="incomplete_evaluation_definition_reference"):
        fx.minimal_run(evaluation_definition_id=None, evaluation_definition_version=1)


def test_run_without_evaluation_definition_reference_is_still_valid():
    """The reference is optional -- Slice 2 does not require every run to
    have one, only that if present, it's complete (both fields, not one)."""
    run = fx.minimal_run()
    assert run.evaluation_definition_id is None and run.evaluation_definition_version is None
