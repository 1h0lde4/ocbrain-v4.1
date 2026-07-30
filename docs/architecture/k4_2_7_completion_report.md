# Packet 05 — K4.2.7: User Cognitive Model — Completion Report

**Status:** Completed
**Date:** July 30, 2026
**Architecture:** OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md §3 (User
Cognitive Model), §11 (Event Integration), §15 (K4.2.7 roadmap entry).
**Module:** `core/cognitive/user_model.py` (new)
**Dependencies:** Packet 04 (K4.2.6), completed and merged.

---

## §0. Corrections Found (documented, not silently applied)

### 0.1 — Packet 04's own cross-packet prediction was incomplete

`k4_2_6_completion_report.md` §6 predicted Packet 05 would need exactly one governance
addition — `"user_model_promote"` — with "no other change to `core/cognitive/learning.py`."
Re-reading K4.2 §3 directly (not from memory of the prior packet) shows this undersold the
requirement:

> "Writes (promotion of new/revised entries): gated identically to Intent Ontology promotion,
> via two new `EvolutionGovernor.SELF_MODIFYING_ACTIONS` strings — `user_model_propose`,
> `user_model_promote`."

Two strings, not one — independently corroborated by `OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`'s
own Packet 05 scope, which lists both by name. §3 also states User Model writes emit
`cognitive.user_model_updated` (confirmed by its own dedicated row in §11's Event Integration
table — `PreferenceUpdated → cognitive.user_model_updated → New`), distinct from
`cognitive.ontology_evolved`, which `validation_gate()` was emitting unconditionally for every
Evolution-tier domain. Both required small, additive extensions to `validation_gate()` — see
§2.1 below for the exact design and why it stays backward-compatible with Skill/Intent Ontology.

### 0.2 — A supplementary context document repeated the same incomplete claim

A second document, separate from `docs/architecture/`, was supplied mid-session asserting
Packet 04 "intentionally does not register `user_model_promote`... Packet 05 is the first real
caller. Therefore this packet should add `user_model_promote`... **Nothing else in ValidationGate
should change.**" This is the same undercount as §0.1, stated more emphatically. Per this
project's own rule — architecture documents are the single source of truth; when things
disagree, architecture wins — this packet followed the verified text of K4.2 §3/§11 (two action
strings, a dedicated event) rather than the supplementary document's claim. This was flagged to
the user directly, with citations, before implementation proceeded. Everything else in that
document (reuse `validation_gate()`, no duplicate gate, no planning/execution/memory-storage
work, one-directional dependencies, commit-don't-push) matched the architecture and was followed.

---

## 1. Architecture Compliance Matrix

| Architecture Requirement (K4.2 §) | Implementation Location | Status |
|---|---|---|
| §3: read-mostly projection over L1/L3 preference/pattern entries | `assemble_user_cognitive_model()` | Implemented |
| §3: seven illustrative fields (expertise, terminology_preferences, preferred_abstraction_level, communication_style, preferred_output_formats, recurring_objectives, behavioral_patterns) | `UserCognitiveModelProjection` | Implemented |
| §3: "Reads: ungated, ordinary memory search" | `UnifiedMemory.get_layer()`, no governance call on the read path | Implemented |
| §3: writes "gated identically to Intent Ontology promotion" via `validation_gate()` | `validation_gate()` reused directly, no wrapper | Implemented |
| §3: two new `EvolutionGovernor.SELF_MODIFYING_ACTIONS` — `user_model_propose`/`user_model_promote` | `governance_kernel.py` | Implemented |
| §3: `procedure_name` scoped to a `user_model:*` namespace | `procedure_name_for()`, `validation_gate()`'s new `procedure_name` passthrough | Implemented |
| §3: privacy — "fully inspectable... at any time" | `list_user_model_entries()` | Implemented |
| §3: privacy — "...and deletable... at any time" | `delete_user_model_entry()` (reuses `UnifiedMemory.delete()`, unmodified) | Implemented |
| §3: privacy — "governed by the same write-path... no separate, ungoverned backdoor" | No write call anywhere in `user_model.py`; verified by `TestArchitectureCompliance::test_no_direct_memory_write_call` | Implemented & tested |
| §3: privacy — "excluded from... any future cross-instance advisory mechanism" | No such mechanism exists (confirmed by search); `cross_instance_excluded_metadata()` offered as a forward-looking convention; verified structurally by `test_no_cross_instance_coupling_anywhere_in_core` | Implemented (structural verification only — see §2.4) |
| §3: "cached with a short TTL, purely as a performance measure" | Not built — see §2.3 | Explicitly deferred, documented |
| §11: `cognitive.user_model_updated` event | Domain-conditional emission in `validation_gate()`'s Evolution-tier APPROVE path | Implemented & tested |
| Explicitly forbidden: new governors | No new `Governor` subclass anywhere; two vocabulary additions to the existing `EvolutionGovernor` | Verified |
| Explicitly forbidden: new memory layers | L0-L4 untouched; one `CONTENT_TYPE_ROUTES` entry added (routing, not a new layer) | Verified |
| Explicitly forbidden: duplicate validation logic / another promotion gate | `user_model.py` has no write function at all; `validation_gate()` is the only gate | Verified |
| No public interface may change unless objectively incorrect | `validation_gate()`'s two new parameters are additive with safe defaults; all 40 pre-existing K4.2.6 tests pass unmodified | Verified |

---

## 2. Design Decisions Flagged as Implementation Judgment

1. **`validation_gate()` extensions are additive, not a redesign.** Two new keyword-only
   parameters — `is_new_entry: bool = True` and `procedure_name: Optional[str] = None` — plus
   one internal branch (the Evolution-tier promotion event name, conditional on
   `content_domain`). Both parameters default to values that reproduce Skill/Intent Ontology's
   exact prior behavior: `is_new_entry` is ignored outside `content_domain == USER_MODEL`;
   `procedure_name` defaults to `None`, exactly as it was implicitly `None` (never passed) before
   this packet. All 40 of Packet 04's own tests pass with zero modification, confirming this.

2. **Propose-vs-promote mapping.** K4.2 §3 lists the two strings in the order
   "new/revised entries... user_model_propose, user_model_promote" but doesn't state the mapping
   directly. This packet maps `is_new_entry=True` (default) → `"user_model_propose"` and
   `is_new_entry=False` → `"user_model_promote"` — chosen because it lets the "revision" case
   reuse the exact `f"{domain}_promote"` string Skill/Intent Ontology already use for their one
   action, making it the *smaller* of the two possible mappings to implement (only the "new"
   case needs a genuinely new string), and because "propose" reads more naturally as introducing
   something not previously captured than as revising something already confirmed.

3. **No caching layer built for the projection.** K4.2 §3 says the projection may be "cached with
   a short TTL, purely as a performance measure" — explicitly optional, naming no TTL value,
   size, or write-invalidation policy. Building one would mean inventing all three, which is
   exactly the "speculative, uncited implementation detail" this project's standards reject.
   `assemble_user_cognitive_model()` is instead a pure function of current memory state (no
   internal state of its own) — which is what makes it "cacheable" in the first place. Any future
   caller wanting a TTL cache can wrap this function without needing it to change.

4. **"Excluded from cross-instance advisory" is verified structurally, not at runtime.** No
   cross-instance mechanism exists anywhere in this codebase (confirmed by repository-wide
   search), so there is nothing to test a real exclusion against. `TestArchitectureCompliance`
   instead asserts no code in `core/` (other than this module's own docstring, which legitimately
   discusses the invariant in prose) couples `user_model` to anything `cross_instance`-named.
   `cross_instance_excluded_metadata()` is offered as a convention for a caller's `metadata` dict,
   not enforced — `user_model.py` doesn't call `validation_gate()` itself (see §2.5), so it has no
   write call to attach the tag to automatically.

5. **No write wrapper function in `user_model.py`.** A supplementary document (§0.2) suggested
   building "promotion through ValidationGate" as part of this module's responsibilities. Packet 04
   deliberately did not build per-domain wrapper functions for Skill or Intent Ontology either
   (`k4_2_6_completion_report.md`); adding one here — rather than having callers use the shared
   gate directly, exactly as `TestValidationGateSharedCodePath` already does in Packet 04's own
   tests — would be the "another promotion gate" duplication K4.2 §3 itself warns against. This
   module owns the read-side projection and the two privacy operations genuinely specific to this
   domain; writing goes through `validation_gate()` directly, with no intermediary.

6. **Dict-field convention (`metadata={"model_key": ...}`).** §3's field list names
   `expertise`/`terminology_preferences` as inherently keyed (per-domain, per-concept) but
   specifies no schema for how a `KnowledgeEntry` should carry that key. `KnowledgeEntry.metadata`
   is the existing, generic mechanism for exactly this (already used by Packet 04's
   `content_domain` tagging); this packet's convention (`metadata={"model_key": "<key>"}`,
   documented in the module docstring) reuses it rather than inventing a new field.

7. **Assembly precedence: L3 always beats L1, regardless of recency.** A promoted (L3) entry —
   one that already cleared `validation_gate()`'s held-out-improvement, contradiction, and
   governance checks — is treated as more authoritative than a routine (L1) one for the same
   field/key, even if the L1 entry is more recent. Within a layer, most-recently-`updated_at`
   wins. Both are tested explicitly (`test_l3_beats_l1_on_conflict_even_if_l1_is_newer`).

8. **No wiring into Intent Interpretation/Goal Formation.** K4.2 §3 describes this as the
   architecture's eventual intent, and `core.cognitive.planner` already carries a pre-existing,
   unused `HintSource.USER_MODEL` constant from Packets 01-03 anticipating it — but this specific
   integration is not named in Packet 05's own scope, and touching `planner.py`/`intent.py` would
   be moving a later packet's responsibility into this one. Confirmed via `HintSource` remains
   untouched; `test_does_not_import_worker_modules` also asserts this module never imports
   `core.cognitive.planner` or `core.cognitive.intent`.

---

## 3. Files Modified

### New
- `core/cognitive/user_model.py` — `UserCognitiveModelProjection`, `assemble_user_cognitive_model`,
  `list_user_model_entries`, `delete_user_model_entry`, `procedure_name_for`,
  `cross_instance_excluded_metadata`, plus the namespace/field constants.
- `tests/core/cognitive/test_user_model.py` — 34 tests.
- `docs/architecture/k4_2_7_completion_report.md` — this report.

### Modified
- `core/cognitive/learning.py` — `validation_gate()` gained `is_new_entry`/`procedure_name`
  (additive, default-preserving) and a domain-conditional Evolution-tier promotion event.
  Docstring updated to document both precisely.
- `core/governance/governance_kernel.py` — added `"user_model_propose"`/`"user_model_promote"` to
  `EvolutionGovernor.SELF_MODIFYING_ACTIONS`; comment updated to record the correction from
  K4.2.6's single-string prediction.
- `core/memory/unified_memory.py` — added `"user_model": "l3"` to `LayerRouter.CONTENT_TYPE_ROUTES`
  (one entry; every other route untouched).
- `tests/core/cognitive/test_learning.py` — replaced
  `test_user_model_not_yet_registered_rejects_even_if_approved` (now obsolete, since this packet
  legitimately registers those actions) with three tests: `test_user_model_propose_for_new_entry`,
  `test_user_model_promote_for_revision`, and `test_unregistered_action_type_defensive_guard`
  (preserving the original guard-verification intent via a temporarily patched registry instead
  of a permanently-unregistered domain). `MockMemory.write()` extended to capture `procedure_name`.
  Net: 40 → 42 tests, all passing.
- `tests/test_session4b_memory_hardening.py` — updated
  `test_layer_router_content_type_routes_unmodified`'s snapshot count (14 → 15) with a docstring
  explaining the one legitimate, cited addition — following that same file's own precedent
  (`test_memory_curator_worker_file_untouched`) for how to update an "unmodified" guard when a
  later session makes a real, justified change rather than accidental drift.
- `docs/architecture/IMPLEMENTATION_TRACKER.md` — Packet 05 entry marked Completed; summary header
  synchronized (Phase C complete, 6/9 packets done).
- `docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md` and its identical duplicate
  `docs/architecture/k4_3_implementation_transition.md` — Packet 05 status marker updated.

### Deleted
- None.

---

## 4. Interface Stability Audit

- `validation_gate()`'s existing 12 parameters, return type, and all documented behavior for
  `ContentDomain.SKILL`/`INTENT_ONTOLOGY` are unchanged — verified by all 40 pre-existing K4.2.6
  tests passing without modification.
- The two new parameters are keyword-only (matching the function's existing `*`-only signature)
  and both have defaults, so no existing call site anywhere (there are none outside tests, since
  this is the first real caller of the domain) could break.
- `core/cognitive/user_model.py`'s public names are all new; no backward-compatibility surface
  to preserve.
- `EvolutionGovernor.SELF_MODIFYING_ACTIONS` remains a plain `set[str]`; re-confirmed (as in
  Packet 04) that no test asserts its exact contents, so the two additions are non-breaking.
- `GovernanceAction`/`GovernanceResult`/`GovernanceVerdict`/`UnifiedMemory.write()`/`get_layer()`/
  `delete()` signatures were read directly from source before use, not assumed.

---

## 5. Validation Results

- **`tests/core/cognitive/test_user_model.py`:** 34/34 passing.
- **`tests/core/cognitive/test_learning.py`:** 42/42 passing (40 pre-existing unmodified + 2 net
  new after replacing the one obsolete test with three).
- **`tests/test_k2_4_governance.py`:** re-run after the second `SELF_MODIFYING_ACTIONS` edit;
  still 48/48, no exact-set assertion exists to break.
- **`tests/test_session4b_memory_hardening.py`:** the one affected test updated and passing;
  full file re-run clean.
- **Full repository regression:** 998/998 passing. Same 4 pre-existing chromadb-related collection
  errors as every prior session in this campaign (`test_break_concurrency.py`,
  `test_break_empty_db.py`, `test_break_security.py`, `test_system_ctrl.py` — `chromadb` not
  installed in this sandbox), unrelated to this packet. 964 (prior baseline) + 34 new = 998.
- **Lint:** `pyflakes` clean on every touched/new file.
- **Architecture verification:** see Compliance Matrix (§1). `TestArchitectureCompliance` in
  `test_user_model.py` asserts no new `Governor` subclass, no new memory layer, no direct
  `memory.write()`/`KnowledgeEntry(` construction (no write backdoor), no import from
  `core.workers`/`core.cognitive.planner`/`core.cognitive.intent` (one-directional dependencies),
  and no `cross_instance`+`user_model` coupling anywhere else in `core/`.
- **Governance verification:** both new action types confirmed registered; the Evolution-tier
  "never automatic" default (escalate) and the `is_new_entry` propose/promote split both verified
  against a real `GovernanceKernel`, not a mock, mirroring Packet 04's own approach.
- **Documentation verification:** `IMPLEMENTATION_TRACKER.md`, both transition-doc copies, and this
  report are mutually consistent (Packet 05 Completed, July 30, 2026, same file list).

---

## 6. Cross-Packet Contract (for Packet 07 and later)

- `assemble_user_cognitive_model()` and `UserCognitiveModelProjection` are stable, importable
  (`from core.cognitive.user_model import assemble_user_cognitive_model, UserCognitiveModelProjection`).
- `list_user_model_entries()`/`delete_user_model_entry()` are the sanctioned privacy-invariant
  operations; no other module should construct its own deletion/inspection path for this domain.
- Writing a User Cognitive Model entry means calling `validation_gate()` directly with
  `content_domain=ContentDomain.USER_MODEL`, the appropriate `tier`, and (for Evolution-tier)
  `is_new_entry`/`procedure_name` — there is no `user_model.py` wrapper to call instead.
- `HintSource.USER_MODEL` (pre-existing, `core/cognitive/planner.py`) is confirmed correct and
  ready for whichever future packet wires the projection into Intent Interpretation/Goal
  Formation — not built by this packet, and no packet in the current roadmap is yet assigned to
  build it. Flagged here as an open item, per this project's practice of surfacing gaps rather
  than assuming they're covered.
- No caching layer exists around `assemble_user_cognitive_model()` — a future caller needing one
  (e.g. for latency under Packet 08's Supervisor cycle) can wrap the function; K4.2 §3 names no
  TTL/eviction policy for this packet to have built one against.

---

## 7. Final Checklist

```
Packet Review Result
Architecture Compliance         PASS
Implementation Completeness     PASS
Interface Stability             PASS
Documentation Synchronization   PASS
Test Suite                      PASS
Ready for Integration           YES
Architecture Drift Detected     NO
Breaking Changes Introduced     NO
```
