"""
tests/core/cognitive/test_recovery.py — K4.2-H1 D5 (ADR-K4.2-H-05).

Unit tests for OperationRecoveryBudget itself. The mandatory integration
test proving Planner/Supervisor actually SHARE one instance in a real
Orchestrator.handle() invocation lives in
tests/test_orchestrator_recovery.py (H1-G5) -- per the architecture's own
instruction, this budget-object unit suite is necessary but not
sufficient on its own.
"""
import dataclasses

import pytest

from core.cognitive.recovery import OperationRecoveryBudget


class TestOperationRecoveryBudgetCreation:
    def test_default_max_attempts_is_three(self):
        """The default of 3 is a configuration default, not an
        architectural constant -- config/settings.toml [runtime]
        max_recovery_attempts is the actual source of truth at runtime
        (see main.py / core/orchestrator.py); this dataclass default is
        just what applies when a caller constructs one without
        specifying a value."""
        budget = OperationRecoveryBudget()
        assert budget.max_total_recovery_attempts == 3
        assert budget.internal_recovery_used == 0

    def test_custom_max_attempts(self):
        budget = OperationRecoveryBudget(max_total_recovery_attempts=7)
        assert budget.max_total_recovery_attempts == 7

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(OperationRecoveryBudget)


class TestOperationRecoveryBudgetConsumption:
    def test_remaining_starts_at_max(self):
        budget = OperationRecoveryBudget(max_total_recovery_attempts=3)
        assert budget.remaining == 3
        assert budget.exhausted is False

    def test_consume_decrements_remaining(self):
        budget = OperationRecoveryBudget(max_total_recovery_attempts=3)
        assert budget.consume() is True
        assert budget.remaining == 2
        assert budget.internal_recovery_used == 1

    def test_consume_returns_false_once_exhausted(self):
        budget = OperationRecoveryBudget(max_total_recovery_attempts=2)
        assert budget.consume() is True
        assert budget.consume() is True
        assert budget.exhausted is True
        assert budget.remaining == 0
        # The decisive exhaustion behavior: a third consume() must not
        # succeed, and must not go negative.
        assert budget.consume() is False
        assert budget.internal_recovery_used == 2, (
            "a failed consume() must not still increment the counter"
        )
        assert budget.remaining == 0

    def test_zero_max_attempts_is_immediately_exhausted(self):
        """Edge case: a budget configured with zero attempts permits no
        recovery at all -- the first consume() must fail, not raise."""
        budget = OperationRecoveryBudget(max_total_recovery_attempts=0)
        assert budget.exhausted is True
        assert budget.remaining == 0
        assert budget.consume() is False

    def test_remaining_never_negative(self):
        """Defensive: even if internal_recovery_used were somehow to
        exceed the max (e.g. a future bug elsewhere), remaining must
        clamp at zero, not go negative."""
        budget = OperationRecoveryBudget(
            max_total_recovery_attempts=2, internal_recovery_used=5,
        )
        assert budget.remaining == 0
        assert budget.exhausted is True

    def test_repeated_consumption_sequence(self):
        """Exercises the exact sequence the H1-G5 integration test
        depends on: N consumes tracked precisely, in order."""
        budget = OperationRecoveryBudget(max_total_recovery_attempts=3)
        results = [budget.consume() for _ in range(5)]
        assert results == [True, True, True, False, False]
        assert budget.internal_recovery_used == 3
        assert budget.remaining == 0
