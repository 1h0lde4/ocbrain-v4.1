# ADR-K4.2-H-09: Causal Provenance — derived_from vs. caused_by

**Status:** ACCEPTED
**Date:** August 16, 2026
**Author:** K4.2-H1 packet (Contract Evolution Foundation)
**Scope:** `core/cognitive/intent.py` (`CognitiveArtifact`, `Intent`, `Goal`), `core/cognitive/planner.py` (`ExecutionPlan`), `core/cognitive/learning.py` (`LearningRecord`, `CognitiveDecision`).

---

## 1. Context

`derived_from: List[str]` (artifact/resource lineage) existed on every `CognitiveArtifact`. Nothing distinguished "what prior artifact this one was formed from" from "what event *caused* this one to be formed" — a distinction recovery-derived artifacts (e.g. a re-plan triggered by an impasse event) need: the new plan is *derived from* the same Goal as the failed attempt, but *caused by* the impasse event, not the Goal itself.

## 2. Decision

- `caused_by: Optional[str] = None` — a single `EventStream` event_id, or `None`. Added to the `CognitiveArtifact` Protocol and to `Intent`, `Goal`, `ExecutionPlan` (the types that fully implement it).
- `CognitiveDecision` and `LearningRecord` also gain `caused_by`, per the specification's exact instruction — **not** retrofitted into full `CognitiveArtifact` conformance (they have no `resource_id`/`produced_by`/`derived_from` and this ADR does not add those; scope is exactly the one field named).
- The fields are kept strictly independent: `derived_from` never contains event IDs; `caused_by` never contains artifact/resource IDs. `caused_by` is `None` for the overwhelming majority path (ordinary, non-recovery artifact formation) — populating it is not required.

## 3. Consequences

- Verified directly: `derived_from` and `caused_by` can be populated simultaneously and independently on `Intent`/`Goal`/`ExecutionPlan` (`TestCausalProvenance`, `test_caused_by_independent_of_derived_from`), and `caused_by` defaults to `None` everywhere it was added.
- `Intent`/`Goal` continue to satisfy the `CognitiveArtifact` `runtime_checkable` Protocol after gaining the field (confirmed — Protocol satisfaction requires every attribute to be present).
- No recovery-path code in this packet actually populates `caused_by` yet (H1 adds the field and its semantics; wiring a recovery re-plan's `ExecutionPlan.caused_by` to the triggering impasse event_id is not part of the exact-modules table and is left for the future work that will actually exercise the Orchestrator re-plan loop's diagnostic surface further).

## 4. Alternatives considered

- **A single `provenance: Dict[str, Any]` field covering both concerns**: rejected — collapsing artifact lineage and event causality into one loosely-typed dict is exactly the kind of ambiguity this decision exists to remove.
