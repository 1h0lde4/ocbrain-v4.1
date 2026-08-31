"""Benchmark versioning/immutability/lifecycle tests — §79 'Versioning' + ADR-LAB-04."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.benchmark import (
    BenchmarkDefinition,
    BenchmarkVersionRecord,
    ContaminationMetadata,
    CoverageProfile,
    DifficultyMetadata,
)
from eval_lab.contracts.enums import LifecycleState
from eval_lab.contracts.serialization import ContractValidationError

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _version(v: int) -> BenchmarkVersionRecord:
    return BenchmarkVersionRecord(
        benchmark_id="b1", version=v, description=f"v{v}", task_ids=frozenset({"t1"}),
        coverage=CoverageProfile(), contamination=ContaminationMetadata(), published_at=NOW,
    )


def test_publish_new_version_does_not_mutate_original():
    bd = BenchmarkDefinition(benchmark_id="b1", versions=(_version(1),))
    bd2 = bd.publish_new_version(_version(2))
    assert bd.current_version.version == 1, "original BenchmarkDefinition must be unchanged"
    assert bd2.current_version.version == 2
    assert bd is not bd2


def test_publish_new_version_rejects_non_increasing_version():
    bd = BenchmarkDefinition(benchmark_id="b1", versions=(_version(2),))
    with pytest.raises(ContractValidationError, match="new_version_not_greater"):
        bd.publish_new_version(_version(1))
    with pytest.raises(ContractValidationError, match="new_version_not_greater"):
        bd.publish_new_version(_version(2))  # equal also rejected, not just lesser


def test_benchmark_requires_at_least_one_version():
    with pytest.raises(ContractValidationError, match="benchmark_requires_at_least_one_version"):
        BenchmarkDefinition(benchmark_id="b1", versions=())


def test_benchmark_version_id_mismatch_rejected():
    mismatched = BenchmarkVersionRecord(
        benchmark_id="WRONG_ID", version=1, description="x", task_ids=frozenset(),
        coverage=CoverageProfile(), contamination=ContaminationMetadata(), published_at=NOW,
    )
    with pytest.raises(ContractValidationError, match="version_benchmark_id_mismatch"):
        BenchmarkDefinition(benchmark_id="b1", versions=(mismatched,))


def test_benchmark_versions_must_be_monotonic_on_construction():
    with pytest.raises(ContractValidationError, match="versions_not_monotonic"):
        BenchmarkDefinition(benchmark_id="b1", versions=(_version(2), _version(1)))


def test_invalid_lifecycle_state_rejected():
    """LifecycleState.CALIBRATING is valid for evaluators/oracles but not
    for benchmarks (BENCHMARK_CASE_LIFECYCLE excludes it) -- confirms the
    lifecycle-subset-per-object-family design actually works."""
    with pytest.raises(ContractValidationError, match="invalid_benchmark_lifecycle_state"):
        BenchmarkDefinition(benchmark_id="b1", versions=(_version(1),), lifecycle_state=LifecycleState.CALIBRATING)


def test_protected_lifecycle_is_a_valid_benchmark_state():
    bd = BenchmarkDefinition(benchmark_id="b1", versions=(_version(1),), lifecycle_state=LifecycleState.PROTECTED)
    assert bd.lifecycle_state == LifecycleState.PROTECTED


def test_difficulty_metadata_declared_vs_observed_are_independent_fields():
    dm = DifficultyMetadata(declared_difficulty="hard", observed_failure_rate=0.1, observed_run_count=5)
    d = dm.to_dict()
    assert d["declared_difficulty"] == "hard"
    assert d["observed_failure_rate"] == 0.1
    # confirms declared didn't get silently overwritten by observed or vice versa
    assert dm.declared_difficulty == "hard" and dm.observed_failure_rate == 0.1


def test_difficulty_metadata_rejects_out_of_range_failure_rate():
    with pytest.raises(ContractValidationError, match="observed_failure_rate_out_of_range"):
        DifficultyMetadata(observed_failure_rate=1.2)
