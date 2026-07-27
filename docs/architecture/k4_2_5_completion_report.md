# K4.2.5 Completion Report — Planner Completion (Packet 03)

## 0. Provenance and Discrepancies Found

Read before implementation: every file under `docs/architecture/` (per
this packet's own planning-phase mandate), `core/cognitive/planner.py`
and `tests/core/cognitive/test_planner.py` as they exist after Packets
01–02's review passes, `core/governance/governance_kernel.py`,
`core/governance/orchestration_governor.py`, and `main.py`'s composition
root. Three architecture-vs-repository gaps were found — reported here,
not silently resolved or invented around.

**Gap 1 — Skill/SkillRuntime infrastructure does not exist.** This
packet's task spec calls for "skill preconditions wired into
decomposition." A repository-wide search for `class Skill\b`,
`skill_preconditions`, `class SkillRuntime` found nothing anywhere in
`core/`. There is no Skill system to wire into. Decomposition is written
to be extensible for this later — each `PlanStep` carries a
`capability_type` a future precondition check could gate on — but no
stand-in Skill system was fabricated to have something to check against.

**Gap 2 — `CapabilityRegistry.resolve()` / `CapabilityResolver.select()`
appear a third time.** K4's own illustrative pseudocode for
`Planner.plan()` (§5) contains `capabilities = self._select_capabilities(
candidate_steps) # via CapabilityRegistry.resolve() — unmodified`, and
K4.2 §15's *original* K4.2.4 entry (before Packet 02's correction) made
the closely related claim about a `CapabilityResolver.select()`/
`ServiceProfile` match. Both describe the same non-existent API this
packet already resolved once, in K4.2 §15, during Packet 02's
discrepancy-resolution phase. Not re-corrected a third time in the same
document: K4 §5's pseudocode is illustrative source material this
packet's real implementation supersedes, not live-authoritative text this
packet's own scope licenses editing (unlike K4.2 §15's K4.2.4 entry,
which directly described *this codebase's* K4.2.4, and was Packet 02's
own subject). Noted here for the record rather than silently left
unaddressed.

**Gap 3 — `OrchestrationGovernor` had no rule-extension mechanism, and
`ClarificationPolicy` was itself never previously implemented.**
Resolved per explicit direction received during this packet's planning
phase: extend `OrchestrationGovernor.evaluate()` with a second,
independent check reading plain `action.metadata` values (mirroring the
existing `worker_type` pattern exactly), not a generic rule registry, not
a new governor, not an import of the `ClarificationPolicy` class into the
governance layer. Full reasoning is documented in both
`core/cognitive/planner.py` (`ClarificationPolicy`'s docstring) and
`core/governance/orchestration_governor.py` (module and method
docstrings).

## 1. Scope

Implemented: `ClarificationPolicy`, `ExecutionPlanLifecycle`, `PlanStep`,
`ExecutionPlan` (K4 §6 / K4.2 §12); the full decomposition pipeline —
`_decompose` (LLM-assisted, reusing `provider_mesh` per the same
precedent as Intent Interpretation, K4.2.1), `_sequence`,
`_fallback_paths`, `_estimate_confidence`, `_alternative_plans`,
`_justify` (K4 §5's named pseudocode steps); `_detect_impasse` producing
Packet 01's `ImpasseRecord`; `plan()`, the module-level orchestrating
entry point; and the `OrchestrationGovernor` extension for
`ClarificationPolicy` evaluation, including the "escalate exactly once"
bound (K4.2 §14).

Not implemented, by explicit boundary (this packet's own task spec, and
K4.2 §2's own placement of the confidence check "at the Plan Compilation
gate"): Plan Compilation itself, the governance gate's actual wiring of
`plan()`'s output into a live `evaluate_action()` call (built and tested
standalone, ready for that future packet to invoke), and anything K4.2.6+
(shared ValidationGate, learning wiring).

## 2. Design Decisions Flagged as Implementation Judgment (Not Architecture-Cited)

- **`plan()` does not call governance.** K4.2 §2 places the
  ClarificationPolicy check "at the Plan Compilation gate" (K4 §15) — a
  separate, not-yet-built stage. K4's own pseudocode for `plan()` never
  calls governance either. `plan()` produces `ExecutionPlan.confidence`
  correctly; a future Plan Compilation packet is what invokes
  `ClarificationPolicy`/`OrchestrationGovernor` against it. Verified end
  to end by `TestPlannerGovernanceIntegration`, which constructs the
  handoff explicitly rather than asserting `plan()` does something it
  correctly does not do.
- **`plan()` is a module-level function, not a `Planner` class method.**
  K4 §5's "`Planner.plan(...)`" dot-notation is read as informal —
  consistent with every other entry point already established in this
  file (`build_planner_request`, `discover_capabilities`, etc.), rather
  than introducing a class construct nothing else here uses.
- **`_decompose` applies a `min_score=0.01` relevance floor** when
  calling `discover_capabilities` (Packet 02's own default is `0.0` —
  rank, don't filter). Found necessary during test-writing: without it,
  any registered capability with at least one adapter would count as a
  "candidate" for every step regardless of actual relevance, which would
  make impasse detection fire only on a completely empty registry rather
  than on "nothing here actually fits" — the outcome K4.2 §5/§14 actually
  describe. This is decomposition-side filtering; `discover_capabilities`
  itself is unchanged, and its own direct callers still get its original,
  correct default behavior.
- **`_sequence` and `_fallback_paths` are conservative near-no-ops.**
  Neither algorithm is specified anywhere read in K4/K4.2 beyond naming
  the step and its inputs. `_sequence` preserves decomposition's own
  proposed order rather than reordering without a specified rule (same
  reasoning as `_capability_match_score` not incorporating constraints
  into capability matching, Packet 02). `_fallback_paths` leaves
  `error_branch` unset: same-step retry is already `RetryPolicy`'s job
  (an existing, separate `WorkflowNode` field), and assigning a
  *different* step as a fallback target needs a selection rule this
  packet has no basis to invent.
- **`_alternative_plans` substitutes second-ranked candidates rather than
  re-decomposing.** A second LLM pass would double provider calls and
  introduce a second, unjustified source of non-determinism. Substituting
  an already-discovered second-best candidate for one step is a real,
  if narrow, "genuinely different plan," grounded in what discovery
  already found.
- **`_estimate_confidence` uses the weakest step's score.** No formula is
  specified; "confidence is bounded by the least-supported step" is
  consistent with K4.2 §9's general confidence-propagation philosophy
  (don't let one strong step mask a weak one).

## 3. Tests

`test_planner.py`: 115/115 passing (54 carried from Packet 01, 25 from
Packet 02, 36 new). `test_k2_4_governance.py`: 48/48 passing (40 existing,
8 new). Full repository regression: 884/884 passing.

Coverage: all four new dataclasses; decomposition (single-step,
multi-step, provider-failure degradation, unparseable-completion
degradation, the relevance-floor fix); sequencing and fallback-path
pass-through; confidence estimation (bounds, weakest-step-determines-
overall); alternative-plan generation (none-available, generation,
`top_n` respected); justification text; impasse detection (none, present,
attempted-capabilities aggregation); the full `plan()` pipeline
end-to-end for all three `PlannerStatus` outcomes, including that
precheck rejection short-circuits before decomposition is ever attempted
(provider mock asserted never called); determinism across repeated
calls; and the Planner→Governance handoff for both escalation and the
bounded-rejection ("stalled") case.

Two issues self-caught during test-writing, both fixed before commit: the
relevance-floor gap above (Design Decisions §2), and an initial test that
put contradictory constraint text in a Goal's `raw_request` field rather
than `description` — `_extract_constraints` only falls back to
`raw_request` when `description == "unknown"`, so the test's own
assumption was wrong, not the code.

## 4. Completion Decision

**K4.2.5 COMPLETE — ready for Packet 04 (K4.2.6, Shared ValidationGate +
Learning Wiring).** Neither Packet 01's nor Packet 02's exports were
modified (`OrchestrationGovernor`'s pre-existing `worker_type` behavior
is unchanged and regression-tested). All three gaps found are documented,
not hidden, and none blocks correct implementation of this packet's own
scope.
