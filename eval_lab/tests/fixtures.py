"""eval_lab/tests/fixtures.py — shared contract fixture builders.

Per §78 of the Slice 2 brief: contract-level fixtures only, nothing here
executes an agent, a tool, or a model. Plain factory functions (not
pytest fixtures via `@pytest.fixture`) so a test can call `minimal_task()`
and then mutate/rebuild exactly the variant it needs, rather than being
tied to one fixture shape per test module.
"""

from __future__ import annotations

from datetime import datetime, timezone

from eval_lab.contracts.benchmark import (
    BenchmarkDefinition,
    BenchmarkVersionRecord,
    ContaminationMetadata,
    CoverageProfile,
    DifficultyMetadata,
)
from eval_lab.contracts.enums import (
    ConfidenceLevel,
    EvaluationStatus,
    EvaluatorResultStatus,
    EvaluatorType,
    EvidenceCapturePolicy,
    EvidenceOrigin,
    LifecycleState,
    TrustClassification,
)
from eval_lab.contracts.environment import EnvironmentDefinition, EnvironmentInstance
from eval_lab.contracts.evaluation_input import EvaluationInputSnapshot
from eval_lab.contracts.evaluator import EvaluationDefinition, EvaluatorDefinition, EvaluatorMetrics, JudgeIdentity
from eval_lab.contracts.evidence import Evidence, EvidenceFreshness
from eval_lab.contracts.oracle import OracleDefinition, OracleProbeCase, OracleValidation
from eval_lab.contracts.population import EvaluationPopulation, Experiment
from eval_lab.contracts.result import EvaluationResult
from eval_lab.contracts.run import EvaluationBudget, EvaluationRun, ExecutionReference
from eval_lab.contracts.simulator import SimulatorAuditSample, SimulatorReliability, UserSimulatorDefinition
from eval_lab.contracts.task import EvaluationCase, TaskDefinition, TaskDefinitionVersionRecord, TaskInstance
from eval_lab.contracts.trajectory import Trajectory, TrajectoryEvent, TrajectoryEventType

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


def minimal_benchmark(*, lifecycle: LifecycleState = LifecycleState.DRAFT, version: int = 1) -> BenchmarkDefinition:
    v = BenchmarkVersionRecord(
        benchmark_id="bench_smoke", version=version, description="smoke benchmark",
        task_ids=frozenset({"task_smoke"}), coverage=CoverageProfile(task_families=frozenset({"smoke"})),
        contamination=ContaminationMetadata(), published_at=NOW,
    )
    return BenchmarkDefinition(benchmark_id="bench_smoke", versions=(v,), lifecycle_state=lifecycle)


def protected_benchmark() -> BenchmarkDefinition:
    return minimal_benchmark(lifecycle=LifecycleState.PROTECTED)


def minimal_task() -> TaskDefinition:
    v = TaskDefinitionVersionRecord(
        task_id="task_smoke", version=1, instruction="write hello world to out.txt", goal="out.txt contains 'hello world'",
        constraints=("must not use network",), available_capabilities=frozenset({"filesystem"}),
        available_tools=frozenset({"bash"}), expected_state_description="out.txt exists with expected content",
        expected_artifact_types=frozenset({"file"}), tags=frozenset({"smoke"}),
        difficulty=DifficultyMetadata(declared_difficulty="easy"), published_at=NOW,
    )
    return TaskDefinition(task_id="task_smoke", versions=(v,))


def minimal_environment() -> tuple[EnvironmentDefinition, EnvironmentInstance]:
    d = EnvironmentDefinition(
        environment_id="env_smoke", version=1, description="deterministic sandbox",
        available_tools=frozenset({"bash"}), initial_state_specification="empty tmp dir",
    )
    i = EnvironmentInstance(environment_instance_id="ei_smoke", environment_id="env_smoke", environment_version=1, created_at=NOW)
    return d, i


def minimal_case() -> EvaluationCase:
    return EvaluationCase(evaluation_case_id="case_smoke", task_instance_id="ti_smoke", environment_instance_id="ei_smoke")


def minimal_task_instance() -> TaskInstance:
    return TaskInstance(task_instance_id="ti_smoke", task_id="task_smoke", task_version=1, seed=42)


def minimal_evidence(**overrides) -> Evidence:
    defaults = dict(
        evidence_id="ev_smoke", origin=EvidenceOrigin.ENVIRONMENT_GENERATED,
        trust_classification=TrustClassification.VALIDATED, capture_policy=EvidenceCapturePolicy.FULL,
        freshness=EvidenceFreshness(captured_at=NOW), state_predicate_description="out.txt contains 'hello world'",
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def deterministic_evaluator() -> EvaluatorDefinition:
    return EvaluatorDefinition(
        evaluator_id="eval_det", evaluator_version=1, evaluator_type=EvaluatorType.DETERMINISTIC,
        measurement_target="file content matches expected string exactly", configuration_hash="cfg_det_v1",
    )


def judge_evaluator(*, cross_family: bool = True) -> EvaluatorDefinition:
    ji = JudgeIdentity(
        judge_model_id="judge-model-x", rubric_version="rubric_v1", prompt_template_hash="tmpl_hash_1",
        configuration_hash="judge_cfg_1", cross_family_from_subject=cross_family,
        self_preference_risk_acknowledged=not cross_family,
    )
    return EvaluatorDefinition(
        evaluator_id="eval_judge", evaluator_version=1, evaluator_type=EvaluatorType.JUDGE,
        measurement_target="plan quality", configuration_hash="cfg_judge_v1", judge_identity=ji,
    )


def minimal_oracle_with_validation() -> tuple[OracleDefinition, OracleValidation]:
    od = OracleDefinition(
        oracle_id="or_smoke", oracle_version=1, verification_rules_description="exit code 0 and expected stdout",
        input_expectations_description="stdout of the bash tool", output_semantics_description="pass/fail",
        is_deterministic=True,
    )
    probes = (
        OracleProbeCase(probe_case_id="p_good", probe_type="known_good", expected_verdict="pass", actual_verdict="pass"),
        OracleProbeCase(probe_case_id="p_bad", probe_type="known_bad", expected_verdict="fail", actual_verdict="fail"),
    )
    ov = OracleValidation(oracle_id="or_smoke", oracle_version=1, probe_cases=probes, validated_at=NOW, validated_by="test-suite")
    return od, ov


def minimal_simulator_with_reliability() -> tuple[UserSimulatorDefinition, SimulatorReliability]:
    sd = UserSimulatorDefinition(
        simulator_id="sim_smoke", simulator_version=1, scenario_reference="scenario_smoke_v1",
        model_identity_description="judge-model-x as simulated user",
    )
    samples = (
        SimulatorAuditSample(conversation_id="c1", deviated_from_script=False),
        SimulatorAuditSample(conversation_id="c2", deviated_from_script=False),
    )
    sr = SimulatorReliability(simulator_id="sim_smoke", simulator_version=1, audit_samples=samples, audited_at=NOW, audited_by="test-suite")
    return sd, sr


def minimal_trajectory(n_events: int = 3) -> Trajectory:
    events = tuple(
        TrajectoryEvent(
            trajectory_event_id=f"tev_{i}", event_type=TrajectoryEventType.TOOL_CALL,
            raw_type_name="tool.bash", occurred_at=NOW, monotonic_sequence=i,
        )
        for i in range(n_events)
    )
    return Trajectory(trajectory_id="traj_smoke", execution_instance_id="exec_smoke", events=events)


def minimal_result(*, status: EvaluatorResultStatus = EvaluatorResultStatus.PASS, score: float | None = 1.0) -> EvaluationResult:
    ev = minimal_evidence() if status in (EvaluatorResultStatus.PASS, EvaluatorResultStatus.FAIL, EvaluatorResultStatus.PARTIAL) else None
    return EvaluationResult(
        evaluator_id="eval_det", evaluator_version=1, dimension="goal_satisfaction",
        status=status, score=score, confidence=ConfidenceLevel.HIGH, evidence=(ev,) if ev else (),
    )


def minimal_population() -> EvaluationPopulation:
    return EvaluationPopulation(
        population_id="pop_smoke", sampling_frame_description="all validated smoke cases",
        selection_method="full", selection_reason="smoke test", included_cases=frozenset({"case_smoke"}),
    )


def minimal_experiment() -> Experiment:
    return Experiment(
        experiment_id="exp_smoke", hypothesis="candidate evaluator matches baseline on smoke cases",
        population_id="pop_smoke", comparison_family="slice2-smoke", stopping_rule="fixed N, no early stopping",
        planned_n=1,
    )


def minimal_execution_reference() -> ExecutionReference:
    return ExecutionReference(
        execution_instance_id="exec_smoke", agent_id="ocbrain", agent_version="v4.1",
        runtime_version="k4.2", started_at=NOW, completed_at=NOW,
    )


def minimal_evaluation_input() -> EvaluationInputSnapshot:
    return EvaluationInputSnapshot(
        evaluator_id="eval_det", evaluator_version=1, evaluation_definition_id="ed_smoke",
        trajectory_id="traj_smoke", included_event_ids=None, capture_policy=EvidenceCapturePolicy.FULL,
    )


def minimal_run(**overrides) -> EvaluationRun:
    defaults = dict(
        evaluation_run_id="run_smoke", evaluation_case_id="case_smoke", task_instance_id="ti_smoke",
        benchmark_id="bench_smoke", benchmark_version=1, environment_id="env_smoke", environment_version=1,
        environment_instance_id="ei_smoke", execution_reference=minimal_execution_reference(),
        status=EvaluationStatus.COMPLETED, created_at=NOW, results=(minimal_result(),),
    )
    defaults.update(overrides)
    return EvaluationRun(**defaults)
