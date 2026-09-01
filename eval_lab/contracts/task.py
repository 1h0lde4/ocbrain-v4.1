"""eval_lab/contracts/task.py — task definition, instance, and evaluation case.

Implements §12 of this Slice and §56-57 of the research report amendment.
The three-level chain (TaskDefinition -> TaskInstance -> EvaluationCase)
is the concrete implementation of §12's requirement: "one task definition
-> many task instances -> many evaluation runs." Keeping these distinct is
not optional per ADR-LAB-01 -- collapsing task_id and task_instance_id is
exactly the kind of identity-merging DEBT-015 shows the cost of at the
runtime layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.benchmark import DifficultyMetadata
from eval_lab.contracts.enums import LifecycleState, BENCHMARK_CASE_LIFECYCLE
from eval_lab.contracts.identifiers import (
    CURRENT_SCHEMA_VERSION,
    EvaluationCaseId,
    SchemaVersion,
    TaskId,
    TaskInstanceId,
    TaskVersion,
)
from eval_lab.contracts.serialization import ContractValidationError, frozen_mapping, nested, enum_value


@dataclass(frozen=True)
class TaskDefinitionVersionRecord:
    """One immutable published version of a task, mirroring
    BenchmarkVersionRecord's shape and immutability policy (ADR-LAB-04)."""

    task_id: TaskId
    version: TaskVersion
    instruction: str
    goal: str
    constraints: tuple[str, ...]
    available_capabilities: frozenset[str]
    available_tools: frozenset[str]
    expected_state_description: str
    expected_artifact_types: frozenset[str]
    tags: frozenset[str]
    difficulty: DifficultyMetadata
    published_at: datetime
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "version": self.version,
            "instruction": self.instruction,
            "goal": self.goal,
            "constraints": list(self.constraints),
            "available_capabilities": sorted(self.available_capabilities),
            "available_tools": sorted(self.available_tools),
            "expected_state_description": self.expected_state_description,
            "expected_artifact_types": sorted(self.expected_artifact_types),
            "tags": sorted(self.tags),
            "difficulty": nested(self.difficulty),
            "published_at": self.published_at.isoformat(),
            "schema_version": str(self.schema_version),
        }


@dataclass(frozen=True)
class TaskDefinition:
    """Current-version view of a task, same versioning shape as
    BenchmarkDefinition (see benchmark.py for the rationale)."""

    task_id: TaskId
    versions: tuple[TaskDefinitionVersionRecord, ...]
    lifecycle_state: LifecycleState = LifecycleState.DRAFT

    def __post_init__(self) -> None:
        if not self.versions:
            raise ContractValidationError("task_requires_at_least_one_version", "versions cannot be empty.")
        for i, v in enumerate(self.versions):
            if v.task_id != self.task_id:
                raise ContractValidationError(
                    "version_task_id_mismatch", f"versions[{i}].task_id != task_id."
                )
        version_numbers = [v.version for v in self.versions]
        if version_numbers != sorted(version_numbers):
            raise ContractValidationError("versions_not_monotonic", "versions must be ordered oldest-to-newest.")
        if self.lifecycle_state not in BENCHMARK_CASE_LIFECYCLE:
            raise ContractValidationError(
                "invalid_task_lifecycle_state", f"{self.lifecycle_state} is not a valid task lifecycle state."
            )

    @property
    def current_version(self) -> TaskDefinitionVersionRecord:
        return self.versions[-1]

    @property
    def schema_version(self) -> SchemaVersion:
        """Delegates to the current version's schema_version -- same
        reasoning and same fix as BenchmarkDefinition (benchmark.py)."""
        return self.current_version.schema_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "versions": [v.to_dict() for v in self.versions],
            "lifecycle_state": enum_value(self.lifecycle_state),
            "schema_version": str(self.schema_version),
        }


@dataclass(frozen=True)
class TaskInstance:
    """One concrete instantiation of a TaskDefinition version -- distinct
    from TaskDefinition (§12: a definition can have many instances) and
    distinct from EvaluationCase (an instance is "this task, this seed, this
    environment"; a case additionally carries evaluation-specific
    configuration and, optionally, a mutation scenario -- §57 of the
    research report amendment keeps "benchmark task" and "evaluation case"
    separate for exactly this reason)."""

    task_instance_id: TaskInstanceId
    task_id: TaskId
    task_version: TaskVersion
    seed: int | None
    mutation_scenario_description: str | None = None
    """Per §18/§43 (task mutation): a plain description in Slice 2 --
    structured goal/constraint/plan-diff representation is explicitly
    future work (this Slice's §43: "Do not implement mutation execution"),
    so this field exists to be *set* by a future producer without this
    contract needing to model the diff structure itself yet."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_instance_id": self.task_instance_id,
            "task_id": self.task_id,
            "task_version": self.task_version,
            "seed": self.seed,
            "mutation_scenario_description": self.mutation_scenario_description,
        }


@dataclass(frozen=True)
class EvaluationCase:
    """The evaluable scenario/configuration (§12: "not the active runtime
    object"). References a TaskInstance plus an EnvironmentInstance
    (environment.py) plus whatever evaluation-specific configuration
    applies -- kept intentionally thin in Slice 2 (`configuration` is a
    free-form mapping) since the concrete configuration shape depends on
    evaluator/oracle choices this slice does not execute."""

    evaluation_case_id: EvaluationCaseId
    task_instance_id: TaskInstanceId
    environment_instance_id: str
    configuration: dict[str, Any] = field(default_factory=dict)
    lifecycle_state: LifecycleState = LifecycleState.DRAFT

    def __post_init__(self) -> None:
        if self.lifecycle_state not in BENCHMARK_CASE_LIFECYCLE:
            raise ContractValidationError(
                "invalid_case_lifecycle_state", f"{self.lifecycle_state} is not a valid case lifecycle state."
            )
        # Correction pass: `configuration` was a plain mutable dict on a
        # frozen dataclass -- see serialization.frozen_mapping's docstring.
        object.__setattr__(self, "configuration", frozen_mapping(self.configuration))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_case_id": self.evaluation_case_id,
            "task_instance_id": self.task_instance_id,
            "environment_instance_id": self.environment_instance_id,
            "configuration": dict(self.configuration),
            "lifecycle_state": enum_value(self.lifecycle_state),
        }
