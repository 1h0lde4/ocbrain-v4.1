# ADR-K4.2-H-01: Layered Semantic Authority

**Status:** ACCEPTED
**Date:** August 16, 2026
**Author:** K4.2-H1 packet (Contract Evolution Foundation)
**Scope:** `core/cognitive/intent.py` — `RawRequest`, `Intent.raw_request`, `Goal.structured_form`.

---

## 1. Context

Two independent audit sessions, working from different repository snapshots and different methodologies (one a live `git`-informed read, one a static-archive read), converged on the same confirmed defect (K42-001): `_validate_structured_form()` populated `Goal.structured_form["description"]` from `intent.selected.label if intent.selected else "unknown"` — an intent-hypothesis *label* (e.g. `"novel"`), or the literal string `"unknown"`, never the user's actual request. `intent.raw_request` sat one line below, unused.

This is a Layered Semantic Authority violation: `RawRequest → Intent → Goal` is supposed to be a chain of increasingly-refined interpretation, not a chain where a downstream layer's diagnostic label leaks backward into a field whose whole purpose is preserving the user's actual content.

## 2. Decision

- `RawRequest` is frozen (`@dataclass(frozen=True)`) — the immutable base layer.
- `Intent.raw_request: str` is documented, explicitly, as a *captured string value* from `RawRequest.text`, never a live/nested `RawRequest` reference.
- `Goal.structured_form["description"]` is populated unconditionally from `intent.raw_request`, dropping the `intent.selected.label if ... else "unknown"` branch entirely (it had no correct use — `raw_request` is always available on a constructed `Intent`).
- Downstream cognitive stages consume `Goal`, not `RawRequest` directly. The existing `_extract_constraints()` fallback through `Goal.structured_form` is not a boundary violation — it reads `Goal`, not `RawRequest`.

## 3. Consequences

- K42-001 is fixed. Verified independently against live code this session (`core/cognitive/intent.py:566-570`), not just accepted on the strength of two prior reports.
- `tests/core/cognitive/test_intent.py::TestValidateStructuredForm::test_no_ontology_degrades_gracefully` had been silently asserting the bug as correct behavior (`description == "novel:test"`); corrected to assert the fix.
- The compound-goal override (`form_goals()`, `structured_form["description"] = part_text`) is untouched — it substitutes a different, still-correct value (the specific sub-part) and was never part of the confirmed defect.

## 4. Alternatives considered

- **Unifying the compound-goal override with the fixed single-request path** (suggested as a "nice to have" by one of the two source audits): rejected for H1 — not in the approved modules table, and doing it would be exactly the kind of unrequested scope-widening H1 was explicitly told to avoid.
