"""Failure/error tests — §44-45 of the Slice 2 brief, and reuse of the
existing core.runtime.execution_outcome.FailureType taxonomy."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.enums import FaultDomain
from eval_lab.contracts.failure import EVALUATION_FAILURE_CATEGORIES, ErrorEnvelope, FailureRecord, FailureType, Severity
from eval_lab.contracts.serialization import ContractValidationError

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def test_failure_type_is_the_actual_runtime_enum_not_a_copy():
    """Confirms genuine reuse, not a Lab-owned enum that happens to have
    the same member names -- this must be the literal object imported
    from core/runtime/execution_outcome.py."""
    import core.runtime.execution_outcome as runtime_module
    assert FailureType is runtime_module.FailureType


def test_subject_failure_can_carry_runtime_failure_type():
    fr = FailureRecord(failure_record_id="f1", fault_domain=FaultDomain.SUBJECT, category="timeout",
                        description="worker exceeded execution budget", occurred_at=NOW,
                        runtime_failure_type=FailureType.HARD_DEADLINE)
    assert fr.runtime_failure_type == FailureType.HARD_DEADLINE


def test_infrastructure_failure_can_carry_runtime_failure_type():
    fr = FailureRecord(failure_record_id="f1", fault_domain=FaultDomain.INFRASTRUCTURE, category="provider_error",
                        description="model provider returned 503", occurred_at=NOW,
                        runtime_failure_type=FailureType.PROVIDER_FAILURE)
    assert fr.runtime_failure_type == FailureType.PROVIDER_FAILURE


@pytest.mark.parametrize("domain", [FaultDomain.ORACLE, FaultDomain.EVALUATOR, FaultDomain.JUDGE, FaultDomain.DATA, FaultDomain.INTEGRITY, FaultDomain.ENVIRONMENT])
def test_non_runtime_domains_reject_runtime_failure_type(domain):
    """These fault domains don't exist in the runtime's own vocabulary --
    a FailureRecord must not be constructible claiming otherwise."""
    with pytest.raises(ContractValidationError, match="runtime_failure_type_wrong_domain"):
        FailureRecord(failure_record_id="f1", fault_domain=domain, category="x", description="x", occurred_at=NOW,
                      runtime_failure_type=FailureType.STALLED)


def test_evaluation_failure_categories_defined_for_lab_specific_domains():
    """Confirms every non-runtime fault domain has its own Lab-owned
    category vocabulary (not left to fall back on FailureType, which
    doesn't cover them)."""
    for domain in (FaultDomain.ENVIRONMENT, FaultDomain.ORACLE, FaultDomain.EVALUATOR, FaultDomain.JUDGE, FaultDomain.DATA, FaultDomain.INTEGRITY):
        assert domain in EVALUATION_FAILURE_CATEGORIES
        assert len(EVALUATION_FAILURE_CATEGORIES[domain]) > 0


def test_error_envelope_rejects_non_enum_severity():
    with pytest.raises(ContractValidationError, match="severity_not_enum_member"):
        ErrorEnvelope(error_code="E1", domain=FaultDomain.DATA, message="x", severity="catastrophic")


def test_error_envelope_valid_severities():
    for sev in (Severity.WARNING, Severity.ERROR, Severity.CRITICAL):
        ee = ErrorEnvelope(error_code="E1", domain=FaultDomain.DATA, message="x", severity=sev)
        assert ee.severity == sev
        assert ee.to_dict()["severity"] == sev.value
