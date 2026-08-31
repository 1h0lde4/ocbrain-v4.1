"""Authorization/side-effect tests — §54, §68, §82 of the research report."""

from __future__ import annotations

import pytest

from eval_lab.contracts.authorization import ActionType, AuthorizationOutcome, SideEffectRecord
from eval_lab.contracts.serialization import ContractValidationError


def test_granted_authorization_requires_approval_reference():
    with pytest.raises(ContractValidationError, match="granted_authorization_requires_approval_reference"):
        SideEffectRecord(action_type=ActionType.DELETE, description="delete temp file", expected=True,
                          authorization=AuthorizationOutcome.REQUIRED_AND_GRANTED)


def test_granted_authorization_with_reference_is_valid():
    s = SideEffectRecord(action_type=ActionType.DELETE, description="delete temp file", expected=True,
                          authorization=AuthorizationOutcome.REQUIRED_AND_GRANTED, approval_reference="approval_123")
    assert s.approval_reference == "approval_123"


def test_denied_authorization_needs_no_approval_reference():
    s = SideEffectRecord(action_type=ActionType.DELETE, description="delete prod file", expected=False,
                          authorization=AuthorizationOutcome.REQUIRED_AND_DENIED)
    assert s.approval_reference is None


def test_matched_expectation_none_when_not_yet_observed():
    s = SideEffectRecord(action_type=ActionType.WRITE, description="write output file", expected=True)
    assert s.matched_expectation is None  # not yet checked, distinct from True/False


def test_matched_expectation_true_when_observed_matches():
    s = SideEffectRecord(action_type=ActionType.WRITE, description="write output file", expected=True, observed=True)
    assert s.matched_expectation is True


def test_unexpected_irreversible_side_effect_is_representable():
    """A task can succeed while committing an unexpected, unauthorized,
    irreversible side effect -- this must be representable as a single
    fact, not require inferring it from correctness fields elsewhere."""
    s = SideEffectRecord(action_type=ActionType.IRREVERSIBLE_SIDE_EFFECT, description="dropped a database table",
                          expected=False, observed=True, is_irreversible=True,
                          authorization=AuthorizationOutcome.REQUIRED_AND_UNKNOWN)
    assert s.matched_expectation is False
    assert s.is_irreversible is True
