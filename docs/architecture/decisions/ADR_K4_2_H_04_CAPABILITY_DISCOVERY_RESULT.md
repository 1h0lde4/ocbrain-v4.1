# ADR-K4.2-H-04: Canonical CapabilityDiscoveryResult

**Status:** ACCEPTED
**Date:** August 16, 2026
**Author:** K4.2-H1 packet (Contract Evolution Foundation)
**Scope:** `core/cognitive/planner.py` — `CapabilityMatch`, `CapabilityDiscoveryResult`, `discover_capabilities()`, `_decompose()`, `_estimate_confidence()`.

---

## 1. Context

Pre-H1, `discover_capabilities()` returned a bare `List[CapabilityContract]` — ranked, but with no way for a caller to see *why* a candidate ranked where it did, or to distinguish "strong match" from "included only as a fallback" (a distinction ADR-K4.2-H-02's fix depends on being visible downstream).

## 2. Decision

- `CapabilityMatch`: `capability_type`, `contract`, `relevance_score`, `subgoal_ref`, `is_general_purpose`, `evidence: Dict[str, Any]`. `capability_type` is a top-level field (mirroring `CapabilityContract`), so existing `.capability_type` access in downstream consumers (`_alternative_plans()`, `_detect_impasse()`) needed no logic changes at all.
- `CapabilityDiscoveryResult`: `matches: List[CapabilityMatch]`, `subgoal_ref`, plus `.contracts` (a legacy-shape `List[CapabilityContract]` projection) and `.top_match` (highest-ranked, or `None`) convenience properties.
- `discover_capabilities()` returns `CapabilityDiscoveryResult`, not a bare list. All callers are internal to `core/cognitive/planner.py` (confirmed by repository-wide search) — no external caller shape to preserve.
- `evidence` is diagnostic/explanatory metadata only, never a second decision authority; `relevance_score` and the discovery-time specificity-dominance ordering remain the canonical ranking signal.
- `_estimate_confidence()` reads `CapabilityMatch.relevance_score` directly instead of rebuilding a `CapabilityDiscoveryRequest` and recalling `_capability_match_score()` — mathematically identical (the cached score already is that exact computation against the same step description), just without redundant recomputation.

## 3. Consequences

- `PlannerResult`/`ExecutionPlan` construction is unaffected — `_decompose()` unwraps `.matches` at its own call site, keeping the `(PlanStep, candidates)` tuple shape the rest of the module already expected, now with `candidates: List[CapabilityMatch]`.
- H1-G11 (evidence extensible without changing the semantic contract): only evidence keys with a real signal behind them in v1.0 are populated (`lexical_score`, `specificity_tier`, `general_fallback`) — `domain_match`/`schema_match`/`embedding_score`/`language_match` are not fabricated ahead of the H2 signals that would back them.
- Eleven pre-existing tests in `tests/core/cognitive/test_planner.py` (`TestDiscoverCapabilities`, `TestEstimateConfidence`, `TestPlannerResultDataclass`, `TestCapabilityDiscoveryArchitectureCompliance`) were updated for the new return shape; none were weakened — each now asserts the same property against the new type.

## 4. Alternatives considered

- **Collapsing `CapabilityDiscoveryResult` back to `List[CapabilityContract]` before the Planner consumes it**: rejected — this was explicitly the pre-H1 failure mode the architecture named (scores and evidence silently discarded before the Planner ever sees them).
