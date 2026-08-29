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

## 4. Amendment (2026-08-28): Evaluator Lifecycle, Classifier Statistics, and Abstention

This amendment extends §2's evaluator layering; it does not change the four-layer order or the gold-standard hierarchy already decided there.

**Evaluator lifecycle.** Evaluators themselves now carry lifecycle state, parallel to (but distinct from) the benchmark-case lifecycle in ADR-LAB-04: `draft → candidate → calibrating → validated → trusted → quarantined → deprecated`. A newly written evaluator does not automatically produce results eligible for a `protected` benchmark case — it has to reach `validated` first, the same way a `draft` benchmark case does. `quarantined` is new relative to the case lifecycle: an evaluator that was `trusted` but is later found to disagree systematically with a deterministic or human-validated result moves to `quarantined`, not silently back to `draft` — the distinction matters because a quarantined evaluator's *historical* results stay attributable to it (ADR-LAB-04's immutability requirement), while a draft evaluator never had trusted results to begin with.

**Evaluators and oracles as classifiers.** Per the accompanying report's §7a.3–7a.4, both oracles and judges are ultimately verdict-producers against a (possibly incomplete) ground truth, and classifier statistics apply: true/false positive and negative rates, precision, recall. Two current findings motivate treating this as load-bearing rather than a nice-to-have: Browserbase's Universal Verifier work explicitly reports FPR/FNR/human-agreement for the verifier itself (not just the agent under test), and "Oracle Gap and Signal Fidelity" (arXiv:2607.17531) warns that an evaluator which abstains often can look artificially reliable — "a high-fallback mechanism [can] appear reliable merely because it seldom changes the reference." **Decision:** any evaluator or oracle backing a `protected` case reports sensitivity/specificity against a small labeled probe set (see ADR-LAB-06 for the oracle-specific version of this), and its abstention rate is tracked and reported alongside its accuracy, not omitted because it makes the number look worse.

**Selective evaluation / abstention.** `INSUFFICIENT_EVIDENCE` (already part of the status enum family) is elevated from "allowed" to "expected": an evaluator forced to choose between a low-confidence PASS/FAIL and an honest abstention should abstain, and abstention routes to human review exactly like `INCONCLUSIVE` does. This is the direct evaluator-side consequence of the abstention finding above — an evaluator whose incentive structure punishes abstention will learn to fabricate confidence instead.

**Judge prompt/rubric equivalence.** In addition to the judge identity tuple and cross-family/both-orderings defaults from §2, judges should be spot-checked for rubric-wording sensitivity: two rubrics that a human would read as requesting the same thing should not systematically produce different verdicts. This is a direct instance of the construct-validity concern (report §7a.2) applied specifically to judges — agreement between two prompt phrasings of the same rubric is evidence of measuring the intended construct; disagreement is evidence the judge is picking up on wording rather than the underlying property.

No element of §2's four-layer order, gold-standard hierarchy, or judge-identity-tuple decision is changed by this amendment.

## 5. Alternatives considered (amendment)

- **Track evaluator quality only in aggregate (overall accuracy), skip the sensitivity/specificity breakdown**: rejected — this is precisely the failure mode the cited "Oracle Gap and Signal Fidelity" paper warns about: an aggregate can hide a high-abstention evaluator that never actually contradicts anything.
- **Let a quarantined evaluator's historical results be silently excluded from reports rather than flagged**: rejected. Per ADR-LAB-04, historical results stay attributable to the evaluator version that produced them; quarantine changes what that evaluator is trusted to do *going forward*, not what already happened.

## 6. Alternatives considered (original)

- **Single aggregate score per run**: rejected — explicitly forbidden by the mission (multiple drafts), and independently a bad idea given the judge-bias evidence above: an aggregate hides exactly the kind of disagreement (e.g., deterministic FAIL + judge PASS) that most needs surfacing, not averaging away.
- **Treat a single well-prompted judge as sufficient once "calibrated once"**: rejected. The RAND finding that calibration on easy cases does not predict reliability on hard/adversarial cases means a one-time calibration pass is not evidence of ongoing reliability; recalibration cadence is required (left as an open question in the research report rather than fixed here, since OCBrain has no existing human-labeling workflow to calibrate against yet).
- **Skip cross-family judging when only one model provider is configured (a plausible early local-first setup)**: rejected as a default, but explicitly left as a documented, visible exception rather than silently accepted — a same-family judge configuration should require an explicit `acknowledged_self_preference_risk=True`-style flag in the evaluator definition, not be the silent default.
