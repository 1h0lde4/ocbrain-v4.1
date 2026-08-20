# ADR-K4.2-H-03: Capability Discrimination — Registration-Order Tie-Break

**Status:** ACCEPTED
**Date:** August 20, 2026
**Author:** K4.2-H2-D3 packet (Capability Discrimination Acceptance Suite)
**Scope:** `core/cognitive/planner.py` (`discover_capabilities()`'s ranking sort only).

---

## 1. Context

D3's brief (`docs/architecture/h2_packets/D3_CAPABILITY_DISCRIMINATION.md`) posed an explicit open question rather than assuming an answer: does `discover_capabilities()`'s specificity-dominance ranking already guarantee registration-order independence, or does it have an implicit "first-registered-at-max-score wins" tie-break?

Writing the acceptance suite's Case D tests (`tests/test_capability_discrimination.py::TestRegistrationOrderIndependence`) answered this empirically, in two parts:

- **The realistic case** (two specific capabilities with genuinely different `relevance_score` against a request) passed against the unmodified implementation. `discover_capabilities()`'s sort key, `(is_general_purpose, -relevance_score)`, is a total order whenever scores differ — insertion order cannot matter.
- **The edge case** (two specific capabilities engineered to score float-identically against a probe request — verified as a genuine exact tie, not a near-tie, before asserting anything) failed. Python's `list.sort` is stable; with no third key, an exact tie within the same `is_general_purpose` group silently resolves to `scored`'s insertion order, which is `registry.list_capabilities()` order, which is registration order. Registering `torque_calibration_procedure` before `sequence_verification_procedure` made the former win; the reverse order made the latter win — identical registry contents, identical scores, different winner.

This is a genuine, if currently dormant, violation of the K4.2-H2 "registration order does not affect semantics" invariant. It is dormant in production today because `main.py` registers exactly one capability (`llm_completion`) — a tie requires at least two same-group candidates — but the gap is real and becomes reachable the moment a second capability is registered with scoring that happens to tie another's for some request.

## 2. Decision

- `discover_capabilities()`'s ranking sort gains a third key: `capability_type`, alphabetical. Full key: `(is_general_purpose, -relevance_score, capability_type)`.
- This key activates only when the first two components are equal — i.e., only on an exact `is_general_purpose` + `relevance_score` tie. Every ranking this codebase's pre-D3 tests exercised involves no such tie (confirmed: the full pre-existing suite, 1174 tests, passes identically before and after this change — see the D3 completion report's regression evidence), so this change is invisible to all of them.
- Per the packet's own decision tree ("if it fails because of a trivial deterministic tie-break: make the smallest safe correction" / "if fixing it requires changing CapabilityMatch semantics, scoring semantics, public API, discovery architecture, or unrelated modules: STOP"), this was applied directly rather than escalated further, because it changes none of those five things:
    - `CapabilityMatch`'s fields are unchanged.
    - `_capability_match_score()` (the scoring formula) is unchanged.
    - `discover_capabilities()`'s signature and return type are unchanged.
    - No new component, boundary, or architectural concept is introduced.
    - Only `core/cognitive/planner.py` is touched.

## 3. Consequences

- Registration order is now provably irrelevant to ranking outcome in all cases, not just the non-tied ones — `tests/test_capability_discrimination.py::TestRegistrationOrderIndependence::test_exact_score_tie_does_not_depend_on_registration_order` pins down both the order-independence and the specific deterministic rule (alphabetically-first `capability_type` wins an exact tie) as a permanent regression guard.
- The chosen tie-break (alphabetical) is arbitrary in the sense that no particular capability_type is architecturally privileged — it was chosen only for being simple, always available (every `CapabilityContract` has a `capability_type`), and independent of any incidental runtime detail like registration order or object identity.
- No consumer of `CapabilityDiscoveryResult` observes any behavioral change outside the exact-tie case: `.matches`, `.top_match`, `.contracts` all keep their existing shapes and existing (non-tied) ordering.
- `evidence`'s contents (`lexical_score`, `specificity_tier`, `general_fallback`) are unaffected — this ADR changes only which already-scored, already-classified candidate sorts first when two are otherwise indistinguishable.

## 4. Alternatives considered

- **Leave it undocumented/unfixed, noting the gap only in `KNOWN_ISSUES.md`**: rejected. `KNOWN_ISSUES.md` is off-limits to this packet by the H2 ownership manifest, and — more importantly — the fix is trivial enough (one added sort-key component) that deferring it would trade a one-line, zero-risk correction for an open determinism gap sitting directly on a frozen-adjacent contract's ranking behavior, for no offsetting benefit.
- **A registration-sequence counter as the tie-break** (explicitly preserving "first registered wins" as documented, intentional behavior rather than replacing it): rejected — this is exactly the behavior D3 was asked to determine was or wasn't acceptable, and "does not affect semantics" (the packet's own success criterion) reads as a requirement that ties resolve independently of registration order, not merely that the existing order-dependence be labeled on purpose.
- **Escalating to a full architecture review** (treating any `discover_capabilities()` change as inherently non-trivial because the function is frozen-adjacent): rejected as disproportionate — the packet's own decision tree anticipates exactly this "trivial, clearly-deterministic tie-break" category and authorizes a direct minimal fix for it, reserving escalation for changes that touch `CapabilityMatch` semantics, scoring semantics, the public API, or the discovery architecture, none of which this change does.
