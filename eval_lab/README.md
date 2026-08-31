# eval_lab — Agent Evaluation & Reliability Lab

**Slice 2 (contract foundation) is complete.** No trace adapter, evaluator execution, oracle/simulator execution, judge calls, persistence, CLI, or runtime integration exist yet — those are Slice 3+. This package currently contains value objects, identifiers, enums, validation, and serialization only.

- `docs/reports/AGENT_EVALUATION_RELIABILITY_LAB_RESEARCH_AND_ARCHITECTURE_REPORT.md` — full research sweep, repository ground truth, and architecture.
- `docs/architecture/decisions/ADR_LAB_01..06_*.md` — six ADRs. Still `Status: PROPOSED` in the repository even though the architecture was reviewed and approved for Slice 2 implementation — the conversational approval and the repository ADR status are intentionally kept separate (this Slice does not flip PROPOSED → ACCEPTED itself; see §82 of the Slice 2 brief).

## Package layout

```
eval_lab/
  __init__.py
  contracts/            # this Slice's actual deliverable
    identifiers.py      # NewType id/version/hash primitives, SchemaVersion
    enums.py            # shared status/lifecycle/fault-domain/type enums
    serialization.py     # ContractValidationError + minimal to_dict() helpers
    evidence.py          # Evidence, ArtifactReference, Provenance, IntegrityEvidence, human annotation
    benchmark.py         # BenchmarkDefinition/Version, CoverageProfile, DifficultyMetadata, contamination
    task.py              # TaskDefinition/Version/Instance, EvaluationCase
    environment.py       # EnvironmentDefinition, EnvironmentInstance
    oracle.py            # OracleDefinition, OracleValidation
    simulator.py         # UserSimulatorDefinition, SimulatorReliability
    evaluator.py         # EvaluatorDefinition, EvaluationDefinition, JudgeIdentity, EvaluatorMetrics
    authorization.py     # ActionType, AuthorizationOutcome, SideEffectRecord
    trajectory.py        # TrajectoryEvent, Trajectory, Snapshot/Branch/Checkpoint, Intervention/Counterfactual
    evaluation_input.py  # EvaluationInputSnapshot (exact evaluator-visible view)
    result.py            # EvaluationResult, EvaluationAggregate, MetricObservation, ComparisonResult
    population.py        # EvaluationPopulation, Experiment
    reliability.py       # ReliabilityObservation, FlakinessClassification
    failure.py           # FailureRecord, ErrorEnvelope (reuses core.runtime.execution_outcome.FailureType)
    run.py               # EvaluationRun, ExecutionReference, EvaluationBudget — the capstone contract
  tests/                 # 156 tests, all passing; see "Running the tests" below
```

17 contract modules rather than one-file-per-noun or a handful of god-modules — each maps to a real domain boundary from the approved architecture. Full type-by-type rationale and ADR traceability is in the Slice 2 implementation report; the short version: related concepts that always travel together (e.g. benchmark + its coverage/difficulty/contamination metadata) share a file, distinct trust-bearing concepts (oracle vs. evaluator vs. simulator) do not, even though they resemble each other structurally.

## Identity model

Every ID (`EvaluationRunId`, `TaskInstanceId`, `EvaluationCaseId`, `ExecutionInstanceId`, ...) is a `typing.NewType` over `str` — zero runtime cost, but a type checker rejects passing one where another is expected. Content/configuration hashes get their own NewTypes too, distinct from IDs (an id is assigned; a hash is derived). See `identifiers.py` and ADR-LAB-01.

`ExecutionInstanceId` is minted by the Lab itself, independent of the runtime's own `trace_id` — deliberately not standing in for the Execution Reliability Track's unimplemented DEBT-015 identity work. `FutureRuntimeOperationRef` is the documented, always-optional mapping seam for if/when that lands.

## Trust model

Six layers plus a cross-cutting one (ADR-LAB-01's amendment): Subject, Environment, Trajectory, Oracle, Evaluator, Experiment, and Integrity. Concretely: `OracleDefinition`/`OracleValidation` (oracle.py) are distinct from `EvaluatorDefinition` (evaluator.py) — an oracle's own false-positive/false-negative rate is tracked independently of what an evaluator built on top of it concludes, per real verifier-hacking precedent cited in ADR-LAB-06. `UserSimulatorDefinition`/`SimulatorReliability` (simulator.py) get the same treatment for multi-turn evaluation.

## Versioning

Benchmarks and tasks use a version-record pattern: `BenchmarkDefinition`/`TaskDefinition` hold a tuple of immutable, monotonically-versioned records; `publish_new_version()` returns a *new* definition object rather than mutating the existing one (frozen dataclasses make this the only option, which is the point — ADR-LAB-04). Evaluators/oracles/simulators use a simpler versioned-object pattern (no separate version-record wrapper) since they don't need historical content preserved the same way a benchmark's task list does. All serialized contracts expose `schema_version` (wire-format version, distinct from the domain object's own version) at a predictable top-level location regardless of which pattern the type uses.

## Serialization

No central framework — matches this repository's existing convention (`to_dict`/`from_dict` defined per-class throughout `core/`) rather than introducing one. `serialization.py` provides only the handful of genuinely repeated small helpers (`enum_value`, `nested`, `nested_list`) plus the shared `ContractValidationError` exception. Canonicalization policy: fixed explicit key order per `to_dict()`, enums as `.value`, `None` written explicitly rather than fields being omitted.

## Validation

Field-level (e.g. scores in `[0.0, 1.0]`, non-negative counts) and cross-field/cross-contract (e.g. a `JUDGE`-type evaluator requires `judge_identity`; a fault-status `EvaluationRun` requires `fault_domain`; an `INSUFFICIENT_EVIDENCE` result cannot carry a score) are both enforced in `__post_init__`, raising `ContractValidationError` with a short, stable, grep-able reason code as the first argument — not a generic `ValueError` with only prose.

## What existing OCBrain code is reused

Exactly one import: `core.runtime.execution_outcome.FailureType`, used in `failure.py` for `FailureRecord`s whose `fault_domain` is `SUBJECT` or `INFRASTRUCTURE`. Verified safe before importing: that module has zero OCBrain-internal imports (stdlib only) and defines a plain, stateless `class FailureType(str, Enum)` — not a service, connection, or worker instance, which is what the runtime/Lab boundary actually prohibits. `ORACLE`/`EVALUATOR`/`JUDGE`/`DATA`/`INTEGRITY` fault domains have no runtime equivalent (those concepts don't exist in the runtime's vocabulary) and use Lab-owned category vocabularies instead. This reuse decision is covered by an automated test (`test_dependency_boundary.py`), not just documentation — see below.

## Running the tests

Not auto-discovered by a bare `pytest` at repo root (root `pyproject.toml` scopes `testpaths` to `tests/`; this Slice deliberately did not modify shared repo configuration — see "Known limitations" in the Slice 2 report). Run explicitly:

```
pytest eval_lab/tests -v
```

156 tests, organized per contract module plus three cross-cutting files: `test_run.py` (cross-contract invariants — including the specific case of an oracle, judge, and human disagreeing on the same run without any of them overwriting another), `test_serialization_and_versioning.py` (JSON round-trips across every major type), and `test_dependency_boundary.py` (an *automated*, AST-based check — not just a claim in a doc — that `core/` never imports `eval_lab/`, and that `eval_lab/contracts/` only imports the one pre-approved, verified-safe internal module).

## What comes next (Slice 3, not started)

The trace adapter: normalizing `core.events.event_stream.EventStream` (primary source) plus `EventBus`/`KnowledgeEvent` (supplementary) into this package's `Trajectory`/`TrajectoryEvent` shape, per ADR-LAB-02. Also not started: evaluators that actually produce `EvaluationResult`s, oracle/simulator execution, persistence, CLI, and benchmark content.

## Invariant this package must always satisfy

Nothing under `core/` may import from `eval_lab/`. OCBrain's runtime must be able to execute a task with this entire directory deleted. Enforced by an automated test, not just stated here.
