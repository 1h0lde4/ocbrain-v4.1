# ADR-K4.2-H-06: Learning Domain Contract — Frozen for H1, Reconciliation Explicitly Deferred

**Status:** ACCEPTED (as a deferral — this ADR resolves nothing about the underlying contradiction)
**Date:** August 16, 2026
**Author:** K4.2-H1 packet (Contract Evolution Foundation)
**Scope:** `core/cognitive/learning.py` — `ContentDomain`; `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` §6.

---

## 1. Context

`ContentDomain` (`SKILL`, `INTENT_ONTOLOGY`, `USER_MODEL`) is a closed three-value set. `OCBRAIN_K4_1_L_FINAL_LEARNING_ARCHITECTURE.md`'s `LearningCandidate` model is explicitly open-domain. K4.1-L outranks K4.2 in this repository's own document-precedence hierarchy (`PROJECT_INSTRUCTIONS.md` memory / document hierarchy), so an open model should prevail in a genuine conflict — but no reconciliation pass against K4.1-L has ever actually been performed. `OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` §0/§6 flag this themselves via a `[RECONCILE-PENDING]` marker.

## 2. Decision

- `ContentDomain` remains the current closed three-value set for H1 implementation purposes. H1 does not open it, does not add values, and does not perform the K4.1-L reconciliation.
- The `[RECONCILE-PENDING]` marker in `OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` §6 is **preserved, not deleted** — augmented with an explicit note that this remains a tracked deferral (pointing to `KNOWN_ISSUES.md` DEBT-011), not a decision resolved in K4.2's favor. Deleting the marker was the original specification's suggestion; explicitly overridden here per direction, precisely because a deleted marker gives a future reader no signal that anything is still open.
- `core/cognitive/learning.py`'s `ContentDomain` docstring itself now also states the deferral directly at the point of definition, for durability independent of the architecture doc.

## 3. Consequences

- `KNOWN_ISSUES.md` DEBT-011 tracks this explicitly.
- K4.2.6+ (Shared ValidationGate and Learning Wiring) remains blocked on a genuine K4.1-L reconciliation pass, per `IMPLEMENTATION_ROADMAP.md` — this ADR does not unblock it and is not a substitute for that pass.
- `tests/core/cognitive/test_learning.py::TestContentDomainD6` locks the set at exactly its current three values and size, so a future session cannot silently add a fourth value as a shortcut resolution.

## 4. Alternatives considered

- **Opening the domain model now, adopting K4.1-L's open-domain shape outright**: rejected — this is exactly the kind of unreviewed, one-sided resolution of a flagged document conflict this project's own practice forbids ("if two documents conflict, stop implementation... wait for a design decision").
- **Removing the `[RECONCILE-PENDING]` marker since H1 touches learning.py at all** (the original specification's own suggestion): rejected — explicitly, per direction. Touching an unrelated field (`caused_by`, ADR-K4.2-H-09) is not the same as performing the reconciliation the marker calls for.
