"""Reliability/flakiness tests — §51-52 of the Slice 2 brief."""

from __future__ import annotations

import pytest

from eval_lab.contracts.enums import ConfidenceLevel, EvaluatorResultStatus
from eval_lab.contracts.reliability import FlakinessClassification, FlakinessSuspectedCause, ReliabilityObservation
from eval_lab.contracts.serialization import ContractValidationError


def test_one_successful_run_is_not_reliability():
    """The amendment's own invariant, checked directly: a single-run
    observation is constructible (n=1 is not rejected) but its rate is
    not something a reader should treat as a reliability claim -- there
    is no field here that would let it be mistaken for anything but n=1."""
    single = ReliabilityObservation(task_id="t1", run_statuses=(EvaluatorResultStatus.PASS,))
    assert single.n == 1
    assert single.pass_at_1_rate == 1.0  # correct arithmetic, but n=1 is visible right alongside it
    assert single.to_dict()["n"] == 1  # a report reading this dict has no excuse to drop n


def test_pass_at_1_rate_computed_from_raw_statuses_not_stored_separately():
    statuses = (EvaluatorResultStatus.PASS,) * 15 + (EvaluatorResultStatus.FAIL,) * 5
    obs = ReliabilityObservation(task_id="t1", run_statuses=statuses)
    assert obs.n == 20
    assert obs.n_pass == 15
    assert obs.pass_at_1_rate == pytest.approx(0.75)


def test_reliability_requires_at_least_one_run():
    with pytest.raises(ContractValidationError, match="reliability_requires_runs"):
        ReliabilityObservation(task_id="t1", run_statuses=())


def test_flakiness_requires_at_least_one_suspected_cause_including_unknown():
    with pytest.raises(ContractValidationError, match="flakiness_requires_suspected_cause"):
        FlakinessClassification(task_id="t1", suspected_causes=frozenset(), confidence=ConfidenceLevel.LOW)

    # UNKNOWN is an explicitly legitimate answer, not a validation failure
    fc = FlakinessClassification(task_id="t1", suspected_causes=frozenset({FlakinessSuspectedCause.UNKNOWN}), confidence=ConfidenceLevel.LOW)
    assert FlakinessSuspectedCause.UNKNOWN in fc.suspected_causes


def test_flakiness_does_not_default_to_agent_unreliability():
    """§52: 'do not simply label every variance agent unreliability' --
    confirmed at the type level: multiple non-agent causes are
    representable and equally valid choices, not a fallback."""
    fc = FlakinessClassification(
        task_id="t1", suspected_causes=frozenset({FlakinessSuspectedCause.TOOL_NONDETERMINISM, FlakinessSuspectedCause.TIMING_SENSITIVITY}),
        confidence=ConfidenceLevel.MEDIUM,
    )
    assert FlakinessSuspectedCause.AGENT_NONDETERMINISM not in fc.suspected_causes


def test_flakiness_rejects_non_enum_confidence():
    with pytest.raises(ContractValidationError, match="confidence_not_enum_member"):
        FlakinessClassification(task_id="t1", suspected_causes=frozenset({FlakinessSuspectedCause.UNKNOWN}), confidence="low")
