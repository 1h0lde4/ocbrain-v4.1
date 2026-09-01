"""eval_lab/contracts/run.py — EvaluationRun, ExecutionReference, EvaluationBudget.

Implements §9-11, §53 of this Slice and ADR-LAB-01's central decision:
EvaluationRun references (never embeds) the full chain from benchmark
down to result, per ADR-LAB-01 §2. This is the type every other module in
this package ultimately exists to be referenced *from* -- it is
deliberately the last contract module written and the one with the
heaviest cross-field validation, since §71's cross-contract invariants
mostly cash out here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from eval_lab.contracts.enums import EvaluationStatus, FaultDomain, ReproducibilityLevel
from eval_lab.contracts.evaluation_input import EvaluationInputSnapshot
from eval_lab.contracts.failure import FailureRecord
from eval_lab.contracts.identifiers import (
    AgentId,
    AgentVersion,
    BenchmarkId,
    BenchmarkVersion,
    CURRENT_SCHEMA_VERSION,
    EnvironmentId,
    EnvironmentInstanceId,
    EnvironmentVersion,
    EvaluationCaseId,
    EvaluationDefinitionId,
    EvaluationDefinitionVersion,
    EvaluationRunId,
    ExecutionInstanceId,
    ExperimentId,
    FutureRuntimeOperationRef,
    OracleId,
    OracleVersion,
    RuntimeVersion,
    SchemaVersion,
    SimulatorId,
    SimulatorVersion,
    TaskInstanceId,
    TrajectoryId,
)
from eval_lab.contracts.result import EvaluationResult
from eval_lab.contracts.serialization import ContractValidationError, nested, nested_list


@dataclass(frozen=True)
class EvaluationBudget:
    """Per §53: subject/evaluation/judge budgets kept separate (§53's own
    "Separate: subject budget / evaluation budget / judge budget"). No
    enforcement -- this Slice does not implement a runner that could
    enforce anything (§53: "No enforcement")."""

    subject_wall_time_seconds: float | None = None
    subject_model_calls: int | None = None
    subject_tool_calls: int | None = None
    subject_tokens: int | None = None
    evaluation_wall_time_seconds: float | None = None
    judge_calls: int | None = None
    judge_tokens: int | None = None
    storage_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_wall_time_seconds": self.subject_wall_time_seconds,
            "subject_model_calls": self.subject_model_calls,
            "subject_tool_calls": self.subject_tool_calls,
            "subject_tokens": self.subject_tokens,
            "evaluation_wall_time_seconds": self.evaluation_wall_time_seconds,
            "judge_calls": self.judge_calls,
            "judge_tokens": self.judge_tokens,
            "storage_bytes": self.storage_bytes,
        }


@dataclass(frozen=True)
class ExecutionReference:
    """Per §9/ADR-LAB-01 §2: the Lab's own execution identity, minted
    independently of runtime `trace_id` and explicitly not standing in
    for DEBT-015. `future_runtime_operation_ref` is always constructible
    (defaults to an empty `FutureRuntimeOperationRef()`), giving Slice 3+
    a field to eventually populate without a breaking migration, per this
    Slice's §9: "Instead provide a future mapping seam.\""""

    execution_instance_id: ExecutionInstanceId
    agent_id: AgentId
    agent_version: AgentVersion
    runtime_version: RuntimeVersion
    started_at: datetime
    completed_at: datetime | None = None
    reproducibility_level: ReproducibilityLevel = ReproducibilityLevel.NON_REPRODUCIBLE
    future_runtime_operation_ref: FutureRuntimeOperationRef = field(default_factory=FutureRuntimeOperationRef)

    def __post_init__(self) -> None:
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ContractValidationError(
                "completed_before_started", "completed_at cannot be earlier than started_at (§73)."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_instance_id": self.execution_instance_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "runtime_version": self.runtime_version,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "reproducibility_level": self.reproducibility_level.value,
            "future_runtime_operation_ref": self.future_runtime_operation_ref.to_dict(),
        }


@dataclass(frozen=True)
class EvaluationRun:
    """The primary durable object (ADR-LAB-01 §2). References, does not
    embed, the full chain: benchmark/version, evaluation_case,
    execution_reference, trajectory, evaluation_definition/version, oracle,
    simulator, evaluation_input, results, failures. Persistence itself is
    Slice 2-out-of-scope (§10: "Persistence itself is NOT implemented");
    this contract is designed so a future persistence layer can store one
    of these durably without needing any of its referenced objects loaded
    in memory (§26/§72: reference validity does not require the
    referenced object to be resolvable right now).

    Correction pass note: this type originally embedded the full
    `EvaluationDefinition` object (`evaluation_definition:
    EvaluationDefinition | None`) rather than referencing it by identity --
    inconsistent with every other definitional object on this same class
    (benchmark, environment, oracle, simulator are all id+version pairs).
    `EvaluationDefinition` already carries its own
    `evaluation_definition_id`/`evaluation_definition_version` identity
    (evaluator.py) specifically so it *can* be referenced this way; the
    embedding was an oversight, not a documented exception, and is fixed
    below to `evaluation_definition_id`/`evaluation_definition_version`.

    `results` is a tuple (not a dict keyed by evaluator) specifically so
    that §56's requirement -- oracle=PASS, judge=FAIL, human=PARTIAL, held
    simultaneously -- is representable without an evaluator_id key
    collision forcing one to overwrite another when two results happen to
    share an evaluator_id at different versions.
    """

    evaluation_run_id: EvaluationRunId
    evaluation_case_id: EvaluationCaseId
    task_instance_id: TaskInstanceId
    benchmark_id: BenchmarkId
    benchmark_version: BenchmarkVersion
    environment_id: EnvironmentId
    environment_version: EnvironmentVersion
    environment_instance_id: EnvironmentInstanceId
    execution_reference: ExecutionReference
    status: EvaluationStatus
    created_at: datetime

    experiment_id: ExperimentId | None = None
    trajectory_id: TrajectoryId | None = None
    evaluation_definition_id: EvaluationDefinitionId | None = None
    evaluation_definition_version: EvaluationDefinitionVersion | None = None
    oracle_id: OracleId | None = None
    oracle_version: OracleVersion | None = None
    simulator_id: SimulatorId | None = None
    simulator_version: SimulatorVersion | None = None
    evaluation_input: EvaluationInputSnapshot | None = None
    results: tuple[EvaluationResult, ...] = ()
    failures: tuple[FailureRecord, ...] = ()
    fault_domain: FaultDomain | None = None
    """Set when status is FAILED/ERROR/TIMEOUT; per the amendment
    invariants, this is what keeps "subject failed" distinguishable from
    "evaluator crashed" at the run level, not just within FailureRecord."""
    budget: EvaluationBudget = field(default_factory=EvaluationBudget)
    schema_version: SchemaVersion = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        # §71 cross-field invariant: "EvaluationRun => references a valid
        # EvaluationCase" -- Slice 2 cannot check the case actually exists
        # (no persistence/registry to check against), but it can and does
        # check the reference is present and non-empty.
        if not self.evaluation_case_id:
            raise ContractValidationError("run_requires_evaluation_case_id", "evaluation_case_id cannot be empty.")

        # Same both-or-neither pairing discipline as oracle_id/oracle_version
        # and simulator_id/simulator_version below -- added by the
        # correction pass alongside converting this from an embedded object
        # to a reference pair.
        if (self.evaluation_definition_id is None) != (self.evaluation_definition_version is None):
            raise ContractValidationError(
                "incomplete_evaluation_definition_reference",
                "evaluation_definition_id and evaluation_definition_version must both be set or both be None.",
            )

        # §75: a run can be status=ERROR, fault_domain=EVALUATOR without
        # implying subject_failure=True -- enforced here as "a fault
        # status requires a fault_domain to be set," which is the
        # structural half of that separation.
        fault_statuses = (EvaluationStatus.FAILED, EvaluationStatus.ERROR, EvaluationStatus.TIMEOUT)
        if self.status in fault_statuses and self.fault_domain is None:
            raise ContractValidationError(
                "fault_status_requires_fault_domain",
                f"status={self.status.value} requires fault_domain to be set (§75: "
                "a run can be ERROR/EVALUATOR without being SUBJECT/failed).",
            )
        if self.status not in fault_statuses and self.fault_domain is not None:
            raise ContractValidationError(
                "fault_domain_without_fault_status",
                f"fault_domain is set but status={self.status.value} is not a fault status.",
            )

        # §71: "oracle-backed protected case => oracle identity + validation
        # state exists" -- Slice 2 checks the identity-pairing half (both
        # oracle_id and oracle_version set together, or neither); actual
        # OracleValidation existence is a persistence-layer/registry check
        # this contract cannot perform without a registry to query.
        if (self.oracle_id is None) != (self.oracle_version is None):
            raise ContractValidationError(
                "incomplete_oracle_reference", "oracle_id and oracle_version must both be set or both be None."
            )
        if (self.simulator_id is None) != (self.simulator_version is None):
            raise ContractValidationError(
                "incomplete_simulator_reference",
                "simulator_id and simulator_version must both be set or both be None.",
            )

        # §71: "ABSTAINED evaluation => score cannot silently be treated as
        # ordinary PASS/FAIL" -- checked at the run level across all
        # results, since a run could otherwise report an overall status
        # that quietly ignores an abstaining evaluator.
        for r in self.results:
            if r.status.value == "insufficient_evidence" and r.score is not None:
                raise ContractValidationError(
                    "abstained_result_has_score",
                    f"EvaluationResult for {r.evaluator_id} has status=INSUFFICIENT_EVIDENCE "
                    "but a non-None score; abstention must not carry a score that could be "
                    "silently read as an ordinary verdict.",
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_run_id": self.evaluation_run_id,
            "evaluation_case_id": self.evaluation_case_id,
            "task_instance_id": self.task_instance_id,
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "environment_id": self.environment_id,
            "environment_version": self.environment_version,
            "environment_instance_id": self.environment_instance_id,
            "execution_reference": nested(self.execution_reference),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "experiment_id": self.experiment_id,
            "trajectory_id": self.trajectory_id,
            "evaluation_definition_id": self.evaluation_definition_id,
            "evaluation_definition_version": self.evaluation_definition_version,
            "oracle_id": self.oracle_id,
            "oracle_version": self.oracle_version,
            "simulator_id": self.simulator_id,
            "simulator_version": self.simulator_version,
            "evaluation_input": nested(self.evaluation_input),
            "results": nested_list(list(self.results)),
            "failures": nested_list(list(self.failures)),
            "fault_domain": self.fault_domain.value if self.fault_domain else None,
            "budget": nested(self.budget),
            "schema_version": str(self.schema_version),
        }
