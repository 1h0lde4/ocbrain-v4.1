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

## 4. Alternatives considered

- **Version only benchmarks, treat evaluator logic as always-current ("the latest evaluator is the correct one")**: rejected. This is precisely what the mission's evaluator-versioning requirement forbids, and it would make regression analysis unreliable — a "regression" detected between two runs could be an actual behavior change or just an evaluator logic change, and the two must be distinguishable.
- **Allow in-place correction of an `EvaluationRun` when a bug in the original evaluator is found**: rejected. Correcting a bug produces a new evaluator version and a new evaluation of the same trajectory under that version — not a rewrite of the historical record. The historical (buggy) result stays, annotated as superseded, so the audit trail of "we used to think X" is not lost.
- **Skip the lifecycle for the initial internal benchmark ("it's just our own smoke tests, we don't need `draft`/`validated`/`protected` for that")**: rejected as a starting shortcut — the mission's acceptance criteria (§106 final draft) explicitly requires a regression suite to detect a deliberately degraded implementation, and that guarantee is only meaningful if the cases used for it are known to be `validated`, not whatever happened to be lying around in `draft`.
