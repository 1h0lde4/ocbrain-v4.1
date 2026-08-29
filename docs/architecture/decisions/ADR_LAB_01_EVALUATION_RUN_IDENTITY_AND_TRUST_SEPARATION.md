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

## 4. Amendment (2026-08-28): Six-Layer Trust Model

**This amendment extends, and does not replace, §2's decision.** The original three-layer model (subject / trajectory / evaluation) is retained as a summary view; this amendment makes it explicit that "subject" and "trajectory" were themselves compressing two further distinctions that the research sweep (see the accompanying report, §7a) showed matter in practice:

```
1. SUBJECT       — the agent/system being evaluated
2. ENVIRONMENT   — the world/state the subject operates in (was implicit inside "subject truth")
3. TRAJECTORY    — what the subject actually did
4. ORACLE        — objective mechanisms interpreting resulting state (was implicit inside "evaluator")
5. EVALUATOR     — the interpretation/scoring layer built on top of oracle output
6. EXPERIMENT    — how runs are sampled, compared, and aggregated (new; see ADR-LAB-05)
7. INTEGRITY     — cross-cutting: can 1–6 be trusted not to have been altered (see ADR-LAB-06)
```

The reason to split oracle from evaluator specifically: current research (Meta's ARE and Gaia2 work, cited in the report) documents real cases of the *verifier itself* being gamed, independent of anything the scoring/interpretation layer built on top of it does wrong. Folding both into one "evaluator" concept, as the original ADR did, would make an oracle-level failure indistinguishable from an evaluator-level failure in the identity/provenance model — which directly contradicts this ADR's own §2 decision that trust separation should be structural, not just conventional. `EvaluationRun` now references an `oracle_id`+`oracle_version` (see ADR-LAB-06) in addition to `evaluator_version(s)`, kept as separate fields for the same reason `task_id` and `task_instance_id` are kept separate: because a future contributor needs to be able to tell which layer produced which part of the evidence.

No identity field from §2 is removed or renamed by this amendment. This is additive.

## 5. Alternatives considered (amendment)

- **Leave oracle folded into evaluator, treat the split as a Slice 2 implementation detail**: rejected. The identity model is exactly the layer where this needs to be decided now — adding `oracle_id` to a contract after `EvaluationResult` already ships without it is a breaking migration, the same argument §2 already makes for not collapsing `task_instance_id`/`execution_instance_id`.

## 6. Alternatives considered (original)

- **Reuse the runtime's `trace_id` directly as `execution_instance_id`**: rejected. DEBT-015 documents that `trace_id` does not currently survive retries as a stable operation identity — adopting it as-is would import that exact defect into the Lab's own reliability measurements (a retried task would look like N independent runs rather than 1 run with N attempts).
- **Collapse `task_id`/`task_instance_id` since most tasks in Slice 2's initial benchmark will only ever have one instantiation**: rejected. The mission is explicit that one `TaskDefinition` must support many independent `EvaluationCase`/`execution_instance_id` combinations (this is required for reliability measurement — 20 runs of the same task need 20 distinct execution instances under one task definition). Collapsing them now would require a breaking migration the first time reliability testing (Slice 7) is implemented.
