# eval_lab — Agent Evaluation & Reliability Lab

**This directory is a reserved namespace, not yet an implementation.** No contracts, adapters, or evaluators exist here yet — this is Slice 1 output only (research + architecture + ADRs). See:

- `docs/reports/AGENT_EVALUATION_RELIABILITY_LAB_RESEARCH_AND_ARCHITECTURE_REPORT.md` — full research sweep, repository ground truth, and proposed architecture.
- `docs/architecture/decisions/ADR_LAB_01..04_*.md` — four proposed ADRs (identity/trust separation, runtime boundary/trace adapter, evaluator layering/judge calibration, benchmark/evaluator versioning). All `PROPOSED`, pending review.

## Why this exists as an empty package already

Named here deliberately, ahead of any code, so a parallel session doesn't independently reinvent this namespace under a colliding name (this repository already has one naming collision to learn from: `core/workers/evaluator.py`'s `EvaluatorWorker` is a different, existing concept — an in-loop, single-task self-assessment worker, not this Lab. See ADR-LAB-02 for why `eval_lab/` lives at top level instead of under `core/`).

## What comes next (Slice 2, not started)

Contracts: `BenchmarkDefinition`, `TaskDefinition`, `EvaluationCase`, `EvaluationRun`, `ExecutionReference`, `Trajectory`, `TrajectoryEvent`, `Checkpoint`, `EvaluatorDefinition`, `EvaluationResult`, `Evidence`, `FailureRecord`, `Experiment`. Not implemented until the four ADRs above have been reviewed.

## Invariant this package must always satisfy

Nothing under `core/` may import from `eval_lab/`. OCBrain's runtime must be able to execute a task with this entire directory deleted.
