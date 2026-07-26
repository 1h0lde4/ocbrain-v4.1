# K4.2.4 Completion Report — Capability Discovery (Packet 02)

## 0. Provenance and Discrepancies Found

Before implementation, every file under `docs/architecture/` was read (per
this packet's own Step 1), plus `core/cognitive/planner.py` and
`tests/core/cognitive/test_planner.py` as they exist after Packet 01's
review passes. Two architecture-level discrepancies were found during
that reading — reported here rather than silently resolved either way,
per the Repository Precedence Rule and this project's standing practice.

**Discrepancy 1 — `CapabilityRequest` name collision.** K4.2 §12 defines
`CapabilityRequest (ephemeral parameter object): subgoal_ref, description,
applicable_constraints: List[Constraint], context_view_ref`. A completely
different type with the identical name already exists at
`core/capabilities/capability.py`: the K2.3 execution-time input to one
`Adapter.execute()` call (`capability_type, payload, trace_id, metadata`).
The two serve unrelated purposes — one asks an Adapter to actually do
something, the other asks the registry what might be able to. §12 assigns
the name without evident awareness the name was already taken. Neither
type is renamed here: doing so would be an unauthorized interface change
this packet isn't positioned to make unilaterally (the K2.3 type has its
own established consumers; the K4.2 type's exact name comes directly from
the cited architecture section). Resolved by clear docstring
disambiguation and confirming the two are never imported into the same
namespace anywhere in this codebase. Worth a deliberate rename decision in
a future architecture-evolution session.

**Discrepancy 2 — `CapabilityRegistry.resolve()` and the "CognitiveService
Registry" do not exist.** K4.1 Part III's prose says capability selection
happens "via the Kernel's existing `CapabilityRegistry.resolve()`,
unmodified"; K4.2 §12 says capability requests are "resolved against the
existing `CapabilityRegistry`/`CognitiveService` Registry pair, never a
third registry." `core/capabilities/registry.py`'s actual public API is
`register_capability`, `register_adapter`, `get_contract`, `get_adapters`,
`list_capabilities`, `validate`, `stats` — no `resolve()` method exists.
A repository-wide search for `ServiceRegistry`/`CognitiveServiceRegistry`
found zero results — the "CognitiveService Registry" K4.1 Part III
describes conceptually (Part III, "Registry": "a static index, populated
at composition-root time... mirrors the Kernel's own `CapabilityRegistry`
population exactly") was never implemented. This implementation queries
`CapabilityRegistry` using its real, existing methods, and does not query
a CognitiveService Registry — not because this packet skips a
requirement, but because there is nothing there to query, and inventing a
stand-in would be exactly the "unproven speculative structure" this
codebase's own precedent (`CapabilityType`'s declared-not-registered
types, `capability.py`) explicitly rejects building ahead of evidence.

## 1. Scope

Implemented exactly and only: `CapabilityRequest` dataclass,
`build_capability_request()`, deterministic description-based matching
(`_tokenize`, `_capability_match_score`), `discover_capabilities()`, and
the `cognitive.capabilities_discovered` event. Not implemented, by
explicit task boundary: capability selection, ranking down to a single
winner, execution, provider invocation, planning, memory access,
governance access, worker invocation — all confirmed absent by both
static (AST/identifier) and behavioral tests.

## 2. Architecture Compliance Matrix

See the Step 4 matrix already produced and delivered for this packet in
conversation, reproduced in summary: all 8 mapped requirements —
`CapabilityRequest` shape, registry querying, matching, published-schema
candidates, event emission, boundary non-violation, reuse of existing
types — are Implemented; querying the CognitiveService Registry is marked
Not Applicable per Discrepancy 2 above.

## 3. Design Decisions Flagged as Implementation Judgment (Not Architecture-Cited)

- **Matching formula:** token-overlap (Jaccard similarity over
  non-stopword tokens) between `CapabilityRequest.description` and each
  `CapabilityContract.description`. No formula is specified anywhere read
  in K4.2 or this packet's task spec — only that discovery be
  "deterministic" and "description-and-schema" based. Token overlap is
  simple, auditable, and consistent with this module's existing
  precedent (`_extract_explicit_constraints`'s own plain-regex approach),
  rather than introducing a new mechanism (e.g. embeddings) nothing asked
  for.
- **Constraints not incorporated into the match score.** `applicable_constraints`
  is carried on `CapabilityRequest` and round-trips correctly (tested),
  but does not currently influence `_capability_match_score`. Hard
  constraints are frequently negative ("must not use X"); naively mixing
  their text into a positive token-overlap score risks inappropriately
  boosting a capability's relevance to the very thing it's constrained
  against. No architecture section specifies how constraints should
  factor into scoring. Rather than invent an unevidenced heuristic (or
  reach for an LLM call, which would break the determinism requirement),
  constraints are structurally available to a future, more deliberate
  refinement but do not currently affect ranking. Flagged, not hidden.
- **Adapter-registered filtering.** Capabilities with zero registered
  adapters (`CapabilityRegistry`'s own "declared but unfulfilled"
  category) are excluded from candidates. Not explicitly mandated, but
  directly supported by the registry's own `validate()` treating this as
  a distinct, worth-surfacing state — a "candidate" nothing can execute
  isn't a useful candidate for whatever selects next.

## 4. Tests

79/79 passing in `test_planner.py` (54 carried over from Packet 01 + 25
new). Full repository regression: 840/840 passing. Coverage: dataclass
construction, `build_capability_request` (subgoal_ref derivation,
description extraction, constraint pass-through, missing-structured-form
handling), matching determinism and bounds, registry integration
(relevant match, adapter-exclusion, ranking, empty registry, no-match
case, min_score filtering), event emission and payload shape, determinism
across repeated calls, and a behavioral (not text-search) confirmation
that no `Adapter.execute()` is ever called.

One self-caught issue during test-writing: an initial architecture-
boundary test used a raw substring search over the module's source text
and would have false-failed on this very report's own docstring language
— the same class of bug found and fixed during the Packet 01 review.
Replaced with a behavioral check before it was ever committed.

## 5. Completion Decision

**K4.2.4 COMPLETE — Ready for Packet 03 (K4.2.5, Planner Completion).**
Packet 01's exports were not modified. Both discrepancies found are
documented, not hidden, and neither blocks correct implementation of this
packet's own scope.
