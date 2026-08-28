# ADR-LAB-03: Evaluator Layering, Evidence Model & Judge Calibration

**Status:** PROPOSED — pending human review before Slice 4 (deterministic evaluation) or Slice 11 (judge abstraction) begin
**Date:** August 28, 2026
**Author:** Agent Evaluation & Reliability Lab research session (parallel track, branch `eval-lab/research-and-architecture`)
**Scope:** New `eval_lab/evaluators/` package (not yet created).

---

## 1. Context

The mission requires a layered evaluator architecture (deterministic → structural/semantic → LLM judge → human) with every result carrying score, status, evaluator identity/version, confidence, and evidence — and explicitly forbids treating an LLM judge as ground truth.

The August 2026 external research sweep (see the accompanying research report, §2) makes the judge-trust requirement concrete rather than aspirational: current literature documents five specific, measured judge biases (position, verbosity — 15–30 point score inflation, self-preference — 10–25% self-family inflation, format, calibration drift), and a 2026 RAND Corporation study found frontier judges exceeding 50% error rates on adversarial bias benchmarks despite ~80% accuracy on easy cases. Independently, WildClawBench's hybrid-protocol argument (deterministic + semantic + injected-error checks, none alone sufficient) corroborates the mission's layering from outside the mission's own drafting.

## 2. Decision

- Four evaluator layers, in strict order of default trust: **deterministic** (exact state predicates, schema validation, artifact hashes, test execution, budget/checkpoint checks) > **structural/semantic** (plan completeness, tool suitability, recovery quality — may combine deterministic checks with lightweight scoring) > **LLM judge** (only where the first two are insufficient) > **human review** (for inconclusive or judge-disagreement cases).
- Every `EvaluatorResult` carries: `score`, `status` (`PASS`/`FAIL`/`PARTIAL`/`INCONCLUSIVE`/`ERROR`/`TIMEOUT`/`CANCELLED`/`NOT_EVALUATED` — never a bare boolean), `evaluator_id`+`evaluator_version`, `confidence`, and `evidence` (event IDs, state predicates, artifact hashes — never a bare number with no supporting reference).
- Judge identity is a versioned tuple: `(judge_model_id, rubric_version, prompt_template_hash)`. Any change to any element is treated as an eval-suite migration (re-run affected historical comparisons' baseline where feasible; never silently reinterpret old scores under the new judge).
- Default judge posture: **cross-family** (the judge is never the same model family as the subject under evaluation, to structurally avoid self-preference bias) and **both-orderings pairwise comparison** where the evaluation is comparative, to average out position bias rather than trust a single ordering.
- A judge result's confidence is a first-class field, separate from its score. Low-confidence judge output, or judge output that disagrees with a deterministic or human-validated result, routes to human review rather than being averaged in or silently trusted.
- Gold-standard hierarchy, as a default (not an absolute rule — documented exceptions are permitted where justified in a specific evaluator's own definition): environment ground truth > deterministic verifier > validated human reference > calibrated LLM judge > uncalibrated LLM judge.

## 3. Consequences

- No evaluator in Slice 4 (deterministic) needs any model call at all — this is intentional and lets the first real vertical slice (per the mission's own acceptance criteria) prove PASS/FAIL/PARTIAL/ERROR discrimination without incurring judge cost or judge-reliability risk at all.
- Slice 11 (judge abstraction) inherits a non-negotiable minimum bar: no judge ships without a versioned identity tuple and a documented cross-family default. A judge PR that hardcodes a same-family judge/subject pair should be treated as a defect, not a shortcut.
- Human review is a required escape valve, not an optional nice-to-have — an evaluation pipeline with no path to `INCONCLUSIVE → human review` is incomplete under this ADR even if every automated layer works.

## 4. Alternatives considered

- **Single aggregate score per run**: rejected — explicitly forbidden by the mission (multiple drafts), and independently a bad idea given the judge-bias evidence above: an aggregate hides exactly the kind of disagreement (e.g., deterministic FAIL + judge PASS) that most needs surfacing, not averaging away.
- **Treat a single well-prompted judge as sufficient once "calibrated once"**: rejected. The RAND finding that calibration on easy cases does not predict reliability on hard/adversarial cases means a one-time calibration pass is not evidence of ongoing reliability; recalibration cadence is required (left as an open question in the research report rather than fixed here, since OCBrain has no existing human-labeling workflow to calibrate against yet).
- **Skip cross-family judging when only one model provider is configured (a plausible early local-first setup)**: rejected as a default, but explicitly left as a documented, visible exception rather than silently accepted — a same-family judge configuration should require an explicit `acknowledged_self_preference_risk=True`-style flag in the evaluator definition, not be the silent default.
