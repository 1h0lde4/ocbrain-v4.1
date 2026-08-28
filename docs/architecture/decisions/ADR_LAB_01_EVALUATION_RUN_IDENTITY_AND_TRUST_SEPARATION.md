# ADR-LAB-01: Evaluation Run Identity & Three-Layer Trust Separation

**Status:** PROPOSED — pending human review before Slice 2 (contracts) begins
**Date:** August 28, 2026
**Author:** Agent Evaluation & Reliability Lab research session (parallel track, branch `eval-lab/research-and-architecture`)
**Scope:** New `eval_lab/` package (not yet created). Does not modify `core/`, `evals/`, or any file owned by K4.2 or the Execution Reliability Track.

---

## 1. Context

The Agent Evaluation & Reliability Lab mission (three successive drafts; this ADR follows the final "Master" draft) requires a durable `EvaluationRun` object and an identity model that keeps `task_id` / `task_instance_id` / `execution_instance_id` / `evaluation_run_id` fully distinct. This repository already has direct evidence of what happens when adjacent-but-distinct identity concepts get collapsed: `KNOWN_ISSUES.md` DEBT-015 exists specifically because `trace_id` is generated fresh per HTTP request with no client-supply mechanism, so a retry is indistinguishable from a new operation system-wide. The Lab must not repeat that mistake in its own identity model, and cannot assume DEBT-015 will be resolved before the Lab needs its own identifiers.

The mission also requires a "three-layer trust model": subject truth (what the environment/runtime actually contains), trajectory truth (what the agent did), and evaluation truth (what an evaluator concluded). These must not collapse — an evaluator must never be able to rewrite trajectory truth, and a subject must never be able to write evaluation truth.

## 2. Decision

- `EvaluationRun` is the primary durable object. It **references** (by ID) rather than embeds: `BenchmarkDefinition` → `BenchmarkVersion` → `TaskDefinition` → `TaskVersion` → `EvaluationCase` → `ExecutionReference` → `Trajectory` → `EvaluatorResult[]`.
- Full identity set, all kept distinct, none collapsed for convenience: `evaluation_run_id`, `experiment_id`, `benchmark_id`+`benchmark_version`, `task_id`+`task_version`, `task_case_id`, `task_instance_id`, `execution_instance_id`, `environment_id`+`environment_version`, `agent_id`+`agent_version`, `runtime_version`, `model_provider`+`model_name`+`model_configuration_hash`, `evaluation_definition_id`+`evaluation_definition_version`, `evaluator_version(s)`, `seed`, `timestamp`.
- The Lab mints its own `execution_instance_id` at the point it invokes a subject, independent of whatever the runtime's own `trace_id` does. This is a deliberate non-dependency on DEBT-015: the Lab needs stable identity now, and DEBT-015's proposed `Operation`/`ExecutionAttempt` model is explicitly deferred pending its own ADR in the Execution Reliability Track — the Lab cannot and should not wait for it, but should adopt it as its `execution_instance_id` source once (if) it lands, rather than maintaining two competing identity schemes indefinitely.
- Trust separation is enforced structurally, not just by convention: `Trajectory` records are append-only once an `EvaluationRun` closes; `EvaluatorResult` is a separate, additively-versioned record type that references a `Trajectory` by ID and hash rather than being embedded in it. There is no code path in which writing an `EvaluatorResult` can mutate the `Trajectory` it scores.
- Historical `EvaluationRun` records are immutable. A corrected or re-run evaluation produces a new `EvaluationRun`, not an overwrite.

## 3. Consequences

- Every future contract in Slice 2 must carry the full identity set above; a contract missing `task_instance_id` vs. `execution_instance_id` as separate fields should be treated as a review-blocking defect, not a simplification.
- The Lab's identity model and DEBT-015's eventual identity model will temporarily coexist as two related-but-separate systems. This is accepted as a known, documented seam (see the research report's Open Questions, §7) rather than resolved by having the Lab either depend on or duplicate the Execution Reliability Track's unfinished work.
- Immutability means storage cost only grows; no in-place correction path exists. Retention/redaction policy (data governance) is separate from immutability and is addressed in ADR-LAB-04.

## 4. Alternatives considered

- **Reuse the runtime's `trace_id` directly as `execution_instance_id`**: rejected. DEBT-015 documents that `trace_id` does not currently survive retries as a stable operation identity — adopting it as-is would import that exact defect into the Lab's own reliability measurements (a retried task would look like N independent runs rather than 1 run with N attempts).
- **Collapse `task_id`/`task_instance_id` since most tasks in Slice 2's initial benchmark will only ever have one instantiation**: rejected. The mission is explicit that one `TaskDefinition` must support many independent `EvaluationCase`/`execution_instance_id` combinations (this is required for reliability measurement — 20 runs of the same task need 20 distinct execution instances under one task definition). Collapsing them now would require a breaking migration the first time reliability testing (Slice 7) is implemented.
