"""eval_lab/contracts/benchmark.py — benchmark definition, versioning, coverage.

Implements ADR-LAB-04 (versioning/immutability, coverage, difficulty,
contamination) and §14-15, §46-47, §63 of this Slice's brief. CoverageProfile
and difficulty metadata live here rather than their own files: both exist
*to describe a benchmark*, and a benchmark is the only thing they're ever
attached to in Slice 2 -- splitting them out would add file-navigation
overhead without a domain reason (§7's "do not blindly instantiate every
noun as a class" cuts against a 1:1 file-per-noun layout, not just a
1:1 class-per-noun layout).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.enums import LifecycleState, BENCHMARK_CASE_LIFECYCLE
from eval_lab.contracts.identifiers import (
    BenchmarkId,
    BenchmarkVersion,
    CURRENT_SCHEMA_VERSION,
    SchemaVersion,
)
from eval_lab.contracts.serialization import ContractValidationError, enum_value, nested


@dataclass(frozen=True)
class DifficultyMetadata:
    """Per §41/§47: declared difficulty (set at authoring time) and
    observed difficulty (measured after repeated runs) are separate
    fields, never one field that gets overwritten -- overwriting would
    make the task's own metadata a self-fulfilling claim instead of an
    observation. `observed_*` fields are None until Slice 7 (reliability
    engine, not built in Slice 2) actually populates them from repeated
    runs; this contract only reserves the place for that data to live."""

    declared_difficulty: str | None = None  # free-text/tier, e.g. "easy"/"medium"/"hard"
    observed_failure_rate: float | None = None
    observed_variance: float | None = None
    observed_run_count: int = 0

    def __post_init__(self) -> None:
        if self.observed_failure_rate is not None and not (0.0 <= self.observed_failure_rate <= 1.0):
            raise ContractValidationError(
                "observed_failure_rate_out_of_range",
                f"observed_failure_rate must be in [0.0, 1.0], got {self.observed_failure_rate}.",
            )
        if self.observed_run_count < 0:
            raise ContractValidationError("negative_observed_run_count", "observed_run_count cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "declared_difficulty": self.declared_difficulty,
            "observed_failure_rate": self.observed_failure_rate,
            "observed_variance": self.observed_variance,
            "observed_run_count": self.observed_run_count,
        }


@dataclass(frozen=True)
class CoverageProfile:
    """Per §40/§46: what a benchmark actually exercises, so a high score
    on a narrow suite is never silently read as broad capability (research
    report §7a's "Benchmark-squared" citation). Each field is a set of
    free-text tags rather than a closed enum -- the *dimensions themselves*
    (task families, failure modes, tools, ...) are fixed by this schema,
    but their *values* are open-ended and repository-specific; a closed
    enum here would need updating every time OCBrain gains a new tool or
    worker type, which is exactly the kind of coupling a contract layer
    should avoid."""

    task_families: frozenset[str] = field(default_factory=frozenset)
    goal_types: frozenset[str] = field(default_factory=frozenset)
    constraint_types: frozenset[str] = field(default_factory=frozenset)
    capabilities: frozenset[str] = field(default_factory=frozenset)
    tools: frozenset[str] = field(default_factory=frozenset)
    workers: frozenset[str] = field(default_factory=frozenset)
    planning_modes: frozenset[str] = field(default_factory=frozenset)
    failure_modes: frozenset[str] = field(default_factory=frozenset)
    mutation_types: frozenset[str] = field(default_factory=frozenset)
    safety_policies: frozenset[str] = field(default_factory=frozenset)
    environments: frozenset[str] = field(default_factory=frozenset)
    models_providers: frozenset[str] = field(default_factory=frozenset)

    def to_dict(self) -> dict[str, Any]:
        return {k: sorted(v) for k, v in {
            "task_families": self.task_families, "goal_types": self.goal_types,
            "constraint_types": self.constraint_types, "capabilities": self.capabilities,
            "tools": self.tools, "workers": self.workers, "planning_modes": self.planning_modes,
            "failure_modes": self.failure_modes, "mutation_types": self.mutation_types,
            "safety_policies": self.safety_policies, "environments": self.environments,
            "models_providers": self.models_providers,
        }.items()}


@dataclass(frozen=True)
class ContaminationMetadata:
    """Per §63/§87 (research report): tracks what a benchmark/case may
    have been exposed to. Booleans rather than a single "contaminated"
    flag, since exposure to different things (training data vs. agent
    memory vs. judge context) has different implications and a future
    reader needs to know which."""

    training_exposure_known: bool = False
    agent_memory_exposure_known: bool = False
    judge_exposure_known: bool = False
    development_exposure: bool = False
    is_holdout: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "training_exposure_known": self.training_exposure_known,
            "agent_memory_exposure_known": self.agent_memory_exposure_known,
            "judge_exposure_known": self.judge_exposure_known,
            "development_exposure": self.development_exposure,
            "is_holdout": self.is_holdout,
            "note": self.note,
        }


@dataclass(frozen=True)
class BenchmarkVersionRecord:
    """One immutable published version of a BenchmarkDefinition. Per
    ADR-LAB-04 §2: "publishing benchmark-v2 never mutates benchmark-v1" --
    enforced here by frozen=True plus BenchmarkDefinition never exposing a
    mutator, only `publish_new_version()` (below) which returns a new
    BenchmarkDefinition rather than mutating the existing one in place."""

    benchmark_id: BenchmarkId
    version: BenchmarkVersion
    description: str
    task_ids: frozenset[str]
    coverage: CoverageProfile
    contamination: ContaminationMetadata
    published_at: datetime
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "version": self.version,
            "description": self.description,
            "task_ids": sorted(self.task_ids),
            "coverage": nested(self.coverage),
            "contamination": nested(self.contamination),
            "published_at": self.published_at.isoformat(),
            "schema_version": str(self.schema_version),
        }


@dataclass(frozen=True)
class BenchmarkDefinition:
    """The current-version view of a benchmark. `versions` holds every
    published BenchmarkVersionRecord, oldest first; `current_version`
    always points at the last element -- kept as an explicit field (rather
    than a `versions[-1]` property) so a historical EvaluationRun can
    record `benchmark_version` as a plain value even after later versions
    are published, per ADR-LAB-04 §2's "a historical EvaluationRun
    references the exact benchmark_version it was run against,
    permanently."""

    benchmark_id: BenchmarkId
    versions: tuple[BenchmarkVersionRecord, ...]
    lifecycle_state: LifecycleState = LifecycleState.DRAFT

    def __post_init__(self) -> None:
        if not self.versions:
            raise ContractValidationError("benchmark_requires_at_least_one_version", "versions cannot be empty.")
        for i, v in enumerate(self.versions):
            if v.benchmark_id != self.benchmark_id:
                raise ContractValidationError(
                    "version_benchmark_id_mismatch",
                    f"versions[{i}].benchmark_id ({v.benchmark_id}) != benchmark_id ({self.benchmark_id}).",
                )
        version_numbers = [v.version for v in self.versions]
        if version_numbers != sorted(version_numbers):
            raise ContractValidationError(
                "versions_not_monotonic", "versions must be ordered oldest-to-newest by version number."
            )
        if self.lifecycle_state not in BENCHMARK_CASE_LIFECYCLE:
            raise ContractValidationError(
                "invalid_benchmark_lifecycle_state",
                f"{self.lifecycle_state} is not a valid benchmark lifecycle state.",
            )
        # NOTE (considered, not enforced): whether a PROTECTED benchmark
        # must also be a holdout (contamination.is_holdout=True) was
        # considered as a cross-field invariant here. Rejected: a
        # legitimate PROTECTED benchmark can be a public regression suite
        # that is deliberately *not* a holdout. Enforcing is_holdout=True
        # would reject a valid configuration; see "Problems Discovered"
        # in the Slice 2 final report for the fuller reasoning.

    @property
    def current_version(self) -> BenchmarkVersionRecord:
        return self.versions[-1]

    @property
    def schema_version(self) -> SchemaVersion:
        """Delegates to the current version's schema_version. Per §68,
        every serialized contract needs schema_version discoverable at a
        uniform, predictable top-level place -- a future deserializer
        should not need to know, per contract type, whether that means a
        real top-level field or digging into a nested version record."""
        return self.current_version.schema_version

    def publish_new_version(self, new_version: BenchmarkVersionRecord) -> "BenchmarkDefinition":
        """Returns a new BenchmarkDefinition with the version appended.
        Does not mutate self -- self.versions is a tuple on a frozen
        dataclass, so there is no other way to do this, which is the
        point (ADR-LAB-04 §2)."""
        if new_version.version <= self.current_version.version:
            raise ContractValidationError(
                "new_version_not_greater",
                f"new version {new_version.version} must be greater than current "
                f"{self.current_version.version}.",
            )
        return BenchmarkDefinition(
            benchmark_id=self.benchmark_id,
            versions=self.versions + (new_version,),
            lifecycle_state=self.lifecycle_state,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "versions": [v.to_dict() for v in self.versions],
            "lifecycle_state": enum_value(self.lifecycle_state),
            "schema_version": str(self.schema_version),
        }
