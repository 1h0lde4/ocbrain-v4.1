import time

import pytest

from core.runtime.execution_budget import (
    ExecutionBudget,
    ExecutionPolicy,
    _THROUGHPUT_HISTORY,
    record_observed_throughput,
)


def test_default_budget_matches_old_hardcoded_60s_shape():
    """Un-budgeted callers must see unchanged behavior: no extension, and a
    ceiling equal to the old hardcoded constant unless config overrides it."""
    budget = ExecutionPolicy.default_budget()
    assert budget.hard_ceiling_s == 60.0
    assert budget.max_extension_s == 0.0
    assert budget.remaining_extension_s == 0.0


def test_short_request_not_treated_as_long_form():
    """§20 regression guard: long_form=False must be indistinguishable in
    shape from default_budget(), regardless of other kwargs passed."""
    budget = ExecutionPolicy.for_generation(
        provider="ollama", model="mistral", estimated_output_tokens=5000, long_form=False
    )
    assert budget.hard_ceiling_s == 60.0
    assert budget.max_extension_s == 0.0


def test_long_form_with_no_history_uses_conservative_fallback():
    budget = ExecutionPolicy.for_generation(
        provider="ollama", model="never-seen-model", estimated_output_tokens=1700, long_form=True
    )
    assert budget.startup_deadline_s == 10.0
    assert budget.progress_deadline_s == 45.0
    assert budget.absolute_ceiling_s == 300.0
    assert 0 < budget.hard_ceiling_s <= budget.absolute_ceiling_s
    assert budget.max_extension_s > 0


def test_long_form_with_no_estimate_still_produces_bounded_budget():
    budget = ExecutionPolicy.for_generation(provider="ollama", model="mistral", long_form=True)
    assert budget.hard_ceiling_s > 0
    assert budget.hard_ceiling_s <= budget.absolute_ceiling_s


def test_long_form_uses_historical_throughput_when_available():
    record_observed_throughput("ollama", "fast-model", tokens_per_sec=100.0)
    budget = ExecutionPolicy.for_generation(
        provider="ollama", model="fast-model", estimated_output_tokens=1700, long_form=True
    )
    # 1700 tokens / 100 tok/s = 17s generation + safety margin, comfortably
    # under a slow-throughput estimate for the same token count.
    slow_budget = ExecutionPolicy.for_generation(
        provider="ollama", model="genuinely-never-seen", estimated_output_tokens=1700, long_form=True
    )
    assert budget.hard_ceiling_s < slow_budget.hard_ceiling_s


def test_throughput_history_ignores_non_positive_samples():
    record_observed_throughput("ollama", "flaky-model", tokens_per_sec=0.0)
    record_observed_throughput("ollama", "flaky-model", tokens_per_sec=-5.0)
    assert _THROUGHPUT_HISTORY.get("ollama:flaky-model") is None


def test_hard_ceiling_never_exceeds_absolute_ceiling_even_with_huge_estimate():
    budget = ExecutionPolicy.for_generation(
        provider="ollama", model="never-seen", estimated_output_tokens=10_000_000, long_form=True
    )
    assert budget.hard_ceiling_s <= budget.absolute_ceiling_s


# ── ExecutionBudget accounting ──────────────────────────────────────────────


def _budget(hard=1.0, absolute=10.0, max_ext=5.0, startup=1.0, progress=1.0) -> ExecutionBudget:
    return ExecutionBudget(
        startup_deadline_s=startup,
        progress_deadline_s=progress,
        hard_ceiling_s=hard,
        absolute_ceiling_s=absolute,
        max_extension_s=max_ext,
    )


def test_is_hard_expired_false_immediately_after_creation():
    b = _budget(hard=5.0)
    assert not b.is_hard_expired()


def test_is_hard_expired_true_after_ceiling_elapses():
    b = _budget(hard=0.05)
    time.sleep(0.08)
    assert b.is_hard_expired()


def test_grant_extension_bounded_by_max_extension():
    b = _budget(hard=1.0, absolute=100.0, max_ext=3.0)
    assert b.grant_extension(10.0)  # request more than allowed
    assert b.extension_consumed_s == 3.0
    assert b.hard_ceiling_s == 4.0  # 1.0 initial + 3.0 granted
    assert b.remaining_extension_s == 0.0


def test_grant_extension_bounded_by_absolute_ceiling():
    b = _budget(hard=8.0, absolute=10.0, max_ext=100.0)
    assert b.grant_extension(50.0)
    assert b.hard_ceiling_s == 10.0  # clamped to absolute_ceiling_s, not 58.0
    assert b.hard_ceiling_s <= b.absolute_ceiling_s


def test_grant_extension_fails_once_exhausted():
    b = _budget(hard=1.0, absolute=100.0, max_ext=2.0)
    assert b.grant_extension(2.0)
    assert not b.grant_extension(1.0)  # nothing left
    assert b.remaining_extension_s == 0.0


def test_grant_extension_rejects_non_positive_request():
    b = _budget()
    assert not b.grant_extension(0.0)
    assert not b.grant_extension(-5.0)


def test_in_grace_period_true_immediately_after_grant():
    b = _budget(hard=1.0, absolute=100.0, max_ext=5.0)
    b.grant_extension(2.0)
    assert b.in_grace_period()


def test_in_grace_period_false_after_it_elapses():
    b = _budget(hard=1.0, absolute=100.0, max_ext=5.0)
    b.grant_extension(0.05)
    time.sleep(0.08)
    assert not b.in_grace_period()


def test_in_grace_period_false_before_any_extension():
    b = _budget()
    assert not b.in_grace_period()
