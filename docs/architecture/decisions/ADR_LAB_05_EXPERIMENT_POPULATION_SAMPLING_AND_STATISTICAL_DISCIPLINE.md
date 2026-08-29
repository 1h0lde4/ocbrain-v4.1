# ADR-LAB-05: Experiment Population, Sampling & Statistical Discipline

**Status:** PROPOSED — pending human review before Slice 2 (contracts) begins
**Date:** August 28, 2026 (added by the measurement-completeness amendment; not part of the original four Slice 1 ADRs)
**Author:** Agent Evaluation & Reliability Lab research session (parallel track, branch `eval-lab/research-and-architecture`)
**Scope:** New `eval_lab/experiments/` package (not yet created).

---

## 1. Context

None of the original four ADRs address how runs get sampled, compared, or aggregated once they exist — that gap is what this ADR fills. It's a genuinely separate decision from identity (ADR-LAB-01), the runtime boundary (ADR-LAB-02), evaluator/judge trust (ADR-LAB-03), or benchmark/evaluator versioning (ADR-LAB-04): all four of those are about producing a trustworthy *single* result; this one is about not fooling yourself once you have *many* of them.

Current research gives concrete reasons this needs its own discipline rather than "just report the pass rate":

- An ICML 2025 position paper (arXiv:2503.01747) argues standard confidence-interval statistics are routinely misapplied below a few hundred datapoints — exactly the sample-size regime a new internal OCBrain benchmark will likely start in.
- Current practitioner practice already differentiates by sample size (arXiv:2602.10144): a 30-datapoint benchmark gets run ~10× per model to average out sampling noise; a 12,000+-example one gets run once. There is no single correct N — it depends on what's being measured.
- "Benchmark²" (arXiv:2601.03986) argues benchmarks need their own quality metrics (reliability, discriminability), not just an assumption that any existing suite is well-constructed.
- Pervasive label errors in benchmark test sets are documented, not hypothetical (Northcutt et al. 2021, NeurIPS) — a population built on an unvalidated case set inherits that case set's errors silently.

## 2. Decision

- `EvaluationPopulation` is a distinct object from `EvaluationCase`. A case is one task instantiation. A population is the explicit, recorded set of cases an experiment actually draws its conclusion from: `sampling_frame`, `selection_method`, `selection_reason`, `included_cases`, `excluded_cases`. "82% of selected cases passed" is a population-scoped claim and must never be reported as if it were "82% overall capability" — the population is part of the number, not a footnote.
- `Experiment` records, as required metadata rather than enforced statistics in this slice: `hypothesis`, `variables`, `controls`, `comparison_family` (which other comparisons share this experiment's multiple-comparison budget), `statistical_test` (if any), `confidence_level`/`alpha` (if applicable), `stopping_rule`, `planned_N`, `minimum_N`, `maximum_N`. An experiment that doesn't declare a stopping rule is implicitly declaring "run, look, run again, look, stop when favorable" — which the mission explicitly calls out as the failure mode to avoid.
- Baseline/candidate comparisons require explicit comparability metadata before a delta is presented as meaningful: same benchmark version, same or explicitly-compatible case population, compatible environment, compatible evaluator versions, documented model/configuration differences. Where these don't hold, the report states the comparison is limited or non-comparable rather than printing a simple delta next to two numbers that aren't measuring the same thing.
- Statistical uncertainty reporting scales to sample size, not to how confident the report would like to sound: below a few hundred datapoints (per the ICML 2025 position paper above), default to reporting raw counts, point estimates, and qualitative uncertainty rather than a computed confidence interval that the sample doesn't support. Repeated-trial designs (pass@k / pass^k) are preferred specifically because they don't require CLT-style assumptions to be meaningful at small N.
- No statistical engine (automatic significance testing, automatic multiple-comparison correction, sequential-analysis tooling) is implemented in this slice. The fields above exist so Slice 2's contracts don't need a breaking migration when that engine is eventually built.

## 3. Consequences

- A future contributor who wants to add "just compute a p-value" to a comparison has to first populate `comparison_family` and declare whether this comparison is part of a family already being corrected for — the metadata forces the multiple-comparisons question to be asked, even before any actual correction is implemented.
- Small internal benchmarks (the likely starting size for OCBrain's own suite, per the mission's §76 initial-benchmark scope) will mostly report counts and qualitative reliability language rather than confidence intervals, until the suite is large enough for CLT-based statistics to mean anything. This is a deliberate consequence of §2, not an oversight to fix later.
- `EvaluationPopulation` adds a layer of indirection between "cases exist" and "an experiment used N of them" — this is necessary overhead, not incidental complexity; without it, selection bias (which cases got included, and why) is invisible in the eventual report.

## 4. Alternatives considered

- **Skip `EvaluationPopulation`, let `Experiment` reference `EvaluationCase` IDs directly**: rejected. This is exactly what makes selection bias invisible — a raw list of case IDs used doesn't record *why* those cases and not others, or what was excluded and why, which is the information needed to catch a cherry-picked comparison after the fact.
- **Implement a real statistics package now (confidence intervals, significance tests) since the fields already exist**: rejected — explicitly out of scope per the mission (§50 of the final brief: build the data foundation, not the full statistical package), and premature given OCBrain's own benchmark doesn't exist yet to know what sample sizes it will actually produce.
- **Apply CLT-based confidence intervals uniformly regardless of N, since it's simpler than sample-size-dependent logic**: rejected on direct evidence (arXiv:2503.01747) that this specific simplification is a documented, named failure mode in the field this Lab is being built to avoid repeating.
