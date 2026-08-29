# ADR-LAB-04: Benchmark & Evaluator Versioning, Historical Immutability

**Status:** PROPOSED — pending human review before Slice 5 (persistence) begins
**Date:** August 28, 2026
**Author:** Agent Evaluation & Reliability Lab research session (parallel track, branch `eval-lab/research-and-architecture`)
**Scope:** New `eval_lab/benchmarks/` and `eval_lab/storage/` packages (not yet created).

---

## 1. Context

The mission requires that benchmark versions and evaluator versions behave like immutable release artifacts, that historical `EvaluationRun` results are never recomputed and overwritten, and that benchmark cases carry a lifecycle (draft → candidate → validated → benchmark → protected → deprecated) so that arbitrary developer test cases don't silently become trusted regression ground truth.

The August 2026 contamination literature (research report §2) reinforces why this matters beyond internal hygiene: audits of well-known public benchmarks have found double-digit-percentage contamination, and the "SWE-bench illusion" finding specifically showed models succeeding on SWE-bench by recollection rather than reasoning. An internal OCBrain benchmark that quietly mutates over time, or that gets exposed to the same models being evaluated against it (e.g., via `KnowledgeEvent`/memory ingestion), would be vulnerable to the same failure mode at a smaller scale — and would be *harder* to notice, since there's no external community to publish an audit of OCBrain's own private benchmark.

## 2. Decision

- Benchmarks are versioned artifacts: publishing `benchmark-v2` never mutates `benchmark-v1`. A historical `EvaluationRun` references the exact `benchmark_version` it was run against, permanently.
- Evaluators are versioned independently of benchmarks: `evaluator_id` + `evaluator_version` + `configuration_hash`. A historical `EvaluationResult` remains interpretable after evaluator logic changes because it records exactly which evaluator version produced it — it is never silently recomputed under a newer evaluator and overwritten.
- Benchmark case lifecycle: `draft → candidate → validated → benchmark → protected → deprecated`. Only `validated` or later cases may be referenced by a `protected` regression suite. A `draft` case created by one contributor's ad hoc test does not automatically become trusted ground truth.
- Benchmark partitions, per the mission's contamination-defense requirement: `development / validation / public-regression / private-holdout / adversarial`. Private-holdout content is excluded from any path that could feed back into model training or memory ingestion (this needs a concrete technical control once `eval_lab`'s storage layer exists — see Consequences).
- All of the above is enforced by making mutation of a published version structurally unavailable (new version required for any change), not by convention or code review alone.

## 3. Consequences

- Storage grows monotonically — there is no "clean up old benchmark versions" path implied by this ADR, since a historical run's interpretability depends on its exact version remaining available. Retention/archival policy (as opposed to mutation) is a separate, later decision.
- Before Slice 5 ships, someone needs to confirm the concrete mechanism that keeps `private-holdout` content out of `core/memory/` (L0–L4) ingestion paths — this ADR states the requirement but does not yet specify the enforcement mechanism, since that depends on how OCBrain's memory ingestion pipeline actually works and this slice did not inspect it in that depth. Flagged as a Slice 5 prerequisite, not resolved here.
- A future contributor asking "why do we have five near-identical benchmark files" should find the answer in this ADR (immutable versions, not iterative edits) rather than needing to ask.

## 4. Amendment (2026-08-28): Coverage, Difficulty, Lineage, and Deployment Vocabulary

This extends §2's versioning/immutability decision; it does not change it.

**Coverage is now first-class, not implied by a pass rate.** A `CoverageProfile` records what a benchmark actually exercises (task families, tools, capabilities, failure modes, mutation types) so that a high score on a narrow suite is never silently read as broad capability. "Benchmark²" (arXiv:2601.03986) makes exactly this argument for public LLM benchmarks — quality metrics for the benchmark itself, not just for what it measures — and it applies at least as directly to a small internal suite, which is easier to accidentally leave narrow.

**Declared difficulty is separated from observed difficulty.** A task's stated difficulty (metadata set when it was authored) and its measured difficulty (failure rate, variance, judge uncertainty, recovery frequency once it's actually been run many times) are different fields, not one field that gets overwritten. Confusing them would mean a task's own metadata quietly becomes a self-fulfilling claim rather than an observation.

**Provenance/data lineage is now traceable end-to-end.** Every reported number should be traceable: experiment → benchmark version → task → case → environment → execution → trajectory → evidence → oracle → evaluator version → result. This isn't new in spirit (§2 already requires immutable versioned references at each layer) — what's new is treating "where did this number come from" as a query the storage layer must be able to answer directly, not just something reconstructable in principle from the versioned references.

**Deployment-validity vocabulary is reserved, not implemented.** Per the report's §7a.9 and "Beyond Static Leaderboards" (arXiv:2606.19704), `predictive_validity` (does in-sample benchmark rank predict out-of-sample/production rank) and `deployment_gap` are named here so that the eventual production-trace-to-benchmark pipeline (mission §58, explicitly POST-KERNEL-FREEZE) inherits vocabulary instead of reinventing it under different names when that work actually starts. No online/production-comparison mechanism is built in this slice.

## 5. Alternatives considered (amendment)

- **Treat a benchmark's declared difficulty as sufficient, skip tracking observed difficulty until there's a specific need**: rejected — the whole point of running the same case repeatedly (already required by ADR-LAB-01/§2's reliability requirements) is that observed difficulty is a byproduct of data that's already being collected; not recording it discards evidence for free.
- **Wait until Slice 2 contracts exist to design the lineage query, since "it's just following the existing versioned references"**: rejected as the default — per the earlier "wait for DEBT-004/005 before building the adapter" alternative already rejected in ADR-LAB-02, deferring a load-bearing capability until it's inconvenient not to have it tends to mean it never gets built cleanly.

## 6. Alternatives considered (original)

- **Version only benchmarks, treat evaluator logic as always-current ("the latest evaluator is the correct one")**: rejected. This is precisely what the mission's evaluator-versioning requirement forbids, and it would make regression analysis unreliable — a "regression" detected between two runs could be an actual behavior change or just an evaluator logic change, and the two must be distinguishable.
- **Allow in-place correction of an `EvaluationRun` when a bug in the original evaluator is found**: rejected. Correcting a bug produces a new evaluator version and a new evaluation of the same trajectory under that version — not a rewrite of the historical record. The historical (buggy) result stays, annotated as superseded, so the audit trail of "we used to think X" is not lost.
- **Skip the lifecycle for the initial internal benchmark ("it's just our own smoke tests, we don't need `draft`/`validated`/`protected` for that")**: rejected as a starting shortcut — the mission's acceptance criteria (§106 final draft) explicitly requires a regression suite to detect a deliberately degraded implementation, and that guarantee is only meaningful if the cases used for it are known to be `validated`, not whatever happened to be lying around in `draft`.
