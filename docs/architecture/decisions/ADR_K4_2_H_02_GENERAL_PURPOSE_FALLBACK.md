# ADR-K4.2-H-02: General-Purpose Capability Fallback

**Status:** ACCEPTED
**Date:** August 16, 2026
**Author:** K4.2-H1 packet (Contract Evolution Foundation)
**Scope:** `core/capabilities/capability.py`, `core/cognitive/planner.py` (`discover_capabilities()`), `main.py`.

---

## 1. Context

K42-002 (confirmed independently by two audit sessions): Capability Discovery's Jaccard token-overlap scoring returns `0.0` for realistic task phrasings against the sole registered `LLM_COMPLETION` contract's description ("Generate text from a prompt via a language model."). `_decompose()` calls `discover_capabilities()` with `min_score=0.01`, filtering out every such zero-score candidate — producing an empty candidate list, and a spurious impasse, for essentially any realistic query, regardless of what the user actually asked for.

## 2. Decision

- `CapabilityContract` gains `is_general_purpose: bool = False`.
- `discover_capabilities()` includes a capability with `is_general_purpose=True` as a fallback candidate *regardless* of `min_score` — the whole point of the flag. Every other capability is still filtered by `min_score` exactly as before.
- Ranking applies specificity dominance: strong specific > weak specific > general-purpose fallback. Any non-general-purpose match that cleared `min_score` (however weak) outranks every general-purpose-only match.
- No Planner-side hard-coded capability-type routing. The registry (`is_general_purpose`) remains the single dynamic source of what counts as general-purpose — proven behaviorally (`TestGeneralPurposeFallback::test_fallback_mechanism_is_not_hard_coded_to_one_name`) with an arbitrarily-named capability, not by searching source text for the literal string `"llm_completion"`.
- `main.py`'s real `LLM_COMPLETION` registration sets `is_general_purpose=True` — without this, the flag exists in the type system but never fires.

## 3. Consequences

- K42-002 is fixed. Verified end-to-end: a realistic non-overlapping phrasing ("book a flight to Tokyo next week") against a registry containing only the real `LLM_COMPLETION` contract now returns it as the top (only) match, `evidence["general_fallback"] == True`.
- Every pre-existing test whose fixture implicitly relied on the *old* behavior (a zero-overlap capability being filtered out) was auditing exactly the scenario this ADR changes on purpose; three were found and updated to use an explicit non-general-purpose fixture instead, preserving what they actually test (min_score genuinely filters ordinary capabilities) rather than weakening the assertion.
- `evidence["specificity_tier"]`'s strong/weak split (0.5 cutoff) is diagnostic-only, not a filtering or ranking threshold — evidence is explicitly not a second source of truth (see ADR-K4.2-H-04).

## 4. Alternatives considered

- **Gating the general-purpose exemption behind `min_score` too** (as the specification's own illustrative pseudocode literally did): rejected — this would leave K42-002 unfixed for the exact scenario it exists to fix. Documented explicitly in `discover_capabilities()`'s own docstring as a deliberate deviation from the example code, per the specification's "implementation guidance, not rigid patch instructions" framing.
- **A configurable numeric threshold for specificity tiering**: rejected — D2 explicitly warns against hard-coding a new architecture-level threshold; the tier label is cosmetic only.
