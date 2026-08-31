"""Task/instance/case + environment tests — §12-13 of the Slice 2 brief."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eval_lab.contracts.benchmark import DifficultyMetadata
from eval_lab.contracts.enums import LifecycleState
from eval_lab.contracts.environment import EnvironmentDefinition, EnvironmentInstance
from eval_lab.contracts.serialization import ContractValidationError
from eval_lab.contracts.task import EvaluationCase, TaskDefinition, TaskDefinitionVersionRecord, TaskInstance

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _task_version(v: int = 1) -> TaskDefinitionVersionRecord:
    return TaskDefinitionVersionRecord(
        task_id="t1", version=v, instruction="do X", goal="X done", constraints=(),
        available_capabilities=frozenset(), available_tools=frozenset(), expected_state_description="X exists",
        expected_artifact_types=frozenset(), tags=frozenset(), difficulty=DifficultyMetadata(), published_at=NOW,
    )


def test_one_definition_many_instances():
    """§12: 'one task definition -> many task instances -> many evaluation
    runs' -- confirmed representable: same task_id/task_version, distinct
    task_instance_ids and seeds."""
    td = TaskDefinition(task_id="t1", versions=(_task_version(),))
    instances = [
        TaskInstance(task_instance_id=f"ti_{i}", task_id=td.task_id, task_version=td.current_version.version, seed=i)
        for i in range(20)
    ]
    assert len({i.task_instance_id for i in instances}) == 20
    assert all(i.task_id == "t1" for i in instances)


def test_task_instance_distinct_from_evaluation_case():
    ti = TaskInstance(task_instance_id="ti_1", task_id="t1", task_version=1, seed=1)
    ec = EvaluationCase(evaluation_case_id="case_1", task_instance_id="ti_1", environment_instance_id="ei_1")
    assert ti.task_instance_id != ec.evaluation_case_id
    assert ec.task_instance_id == ti.task_instance_id  # case correctly references the instance


def test_task_mutation_scenario_is_optional_description_not_structured_diff():
    """Confirms §18/§43: Slice 2 represents mutation as a description
    field, does not implement diff execution."""
    ti = TaskInstance(task_instance_id="ti_1", task_id="t1", task_version=1, seed=1,
                       mutation_scenario_description="constraint C changed from A+B+C to A+B+D")
    assert "A+B+D" in ti.to_dict()["mutation_scenario_description"]


def test_task_versions_must_be_monotonic():
    with pytest.raises(ContractValidationError, match="versions_not_monotonic"):
        TaskDefinition(task_id="t1", versions=(_task_version(2), _task_version(1)))


def test_evaluation_case_lifecycle_validation():
    with pytest.raises(ContractValidationError, match="invalid_case_lifecycle_state"):
        EvaluationCase(evaluation_case_id="c1", task_instance_id="ti1", environment_instance_id="ei1",
                        lifecycle_state=LifecycleState.CALIBRATING)  # not valid for benchmark-case-shaped objects


def test_environment_definition_distinct_from_instance():
    d = EnvironmentDefinition(environment_id="e1", version=1, description="sandbox",
                               available_tools=frozenset({"bash"}), initial_state_specification="empty")
    i1 = EnvironmentInstance(environment_instance_id="ei1", environment_id="e1", environment_version=1, created_at=NOW)
    i2 = EnvironmentInstance(environment_instance_id="ei2", environment_id="e1", environment_version=1, created_at=NOW)
    assert i1.environment_instance_id != i2.environment_instance_id
    assert i1.environment_id == i2.environment_id == d.environment_id
