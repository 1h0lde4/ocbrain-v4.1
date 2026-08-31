"""Oracle/simulator trust tests — ADR-LAB-06, §30-32 of the Slice 2 brief."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.oracle import OracleDefinition, OracleProbeCase, OracleValidation
from eval_lab.contracts.serialization import ContractValidationError
from eval_lab.contracts.simulator import SimulatorAuditSample, SimulatorReliability, UserSimulatorDefinition

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def test_deterministic_oracle_still_requires_validation_object():
    """ADR-LAB-06 §1: 'even fully deterministic oracles can produce false
    positives' -- is_deterministic=True must not exempt an oracle from
    OracleValidation existing as a concept (it's still a constructible,
    required-when-used object regardless of the flag)."""
    od = OracleDefinition(oracle_id="o1", oracle_version=1, verification_rules_description="test suite exit code",
                           input_expectations_description="program output", output_semantics_description="pass/fail",
                           is_deterministic=True)
    assert od.is_deterministic is True
    # OracleValidation is a separate, still-required object -- constructing
    # the oracle alone does not imply it has been validated.
    with pytest.raises(ContractValidationError, match="oracle_validation_requires_probe_cases"):
        OracleValidation(oracle_id="o1", oracle_version=1, probe_cases=())


def test_oracle_validation_completeness_tracks_actual_verdicts():
    probes_incomplete = (
        OracleProbeCase(probe_case_id="p1", probe_type="known_good", expected_verdict="pass", actual_verdict=None),
    )
    ov_incomplete = OracleValidation(oracle_id="o1", oracle_version=1, probe_cases=probes_incomplete)
    assert ov_incomplete.is_complete is False, "a probe with no recorded actual_verdict means validation isn't done"

    probes_complete = (
        OracleProbeCase(probe_case_id="p1", probe_type="known_good", expected_verdict="pass", actual_verdict="pass"),
    )
    ov_complete = OracleValidation(oracle_id="o1", oracle_version=1, probe_cases=probes_complete)
    assert ov_complete.is_complete is True


def test_oracle_validation_detects_mismatched_probe():
    """A false-positive probe where the oracle's actual verdict disagrees
    with the expected verdict must be visible via probes_matching_expectation,
    per the Meta ARE 'Verifying the Verifier' pattern ADR-LAB-06 cites."""
    probes = (
        OracleProbeCase(probe_case_id="p1", probe_type="false_positive_probe", expected_verdict="fail", actual_verdict="pass"),
    )
    ov = OracleValidation(oracle_id="o1", oracle_version=1, probe_cases=probes)
    assert ov.probes_matching_expectation == 0, "the oracle failed this probe -- must be visible, not silently averaged away"


def test_simulator_deviation_rate_matches_aura_methodology():
    """Mirrors the AURA tau-bench-Airline audit cited in ADR-LAB-06 §1
    (11/50 = 22% deviation) at a smaller scale to confirm the computation."""
    samples = tuple(SimulatorAuditSample(conversation_id=f"c{i}", deviated_from_script=(i < 11)) for i in range(50))
    sr = SimulatorReliability(simulator_id="s1", simulator_version=1, audit_samples=samples)
    assert sr.deviation_rate == pytest.approx(0.22)


def test_simulator_reliability_requires_nonempty_audit_samples():
    with pytest.raises(ContractValidationError, match="simulator_reliability_requires_audit_samples"):
        SimulatorReliability(simulator_id="s1", simulator_version=1, audit_samples=())


def test_simulator_definition_defaults_include_known_failure_modes():
    """A simulator that hasn't explicitly considered failure modes should
    not silently look like it checked and found none -- default is the
    two named modes from the research report, not an empty set."""
    sd = UserSimulatorDefinition(simulator_id="s1", simulator_version=1, scenario_reference="ref", model_identity_description="model-x")
    assert "sycophancy" in sd.known_failure_modes_considered
    assert "unrealistic_persona_consistency" in sd.known_failure_modes_considered
