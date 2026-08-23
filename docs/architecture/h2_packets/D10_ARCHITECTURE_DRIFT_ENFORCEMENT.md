# D10 — Full Architecture Drift & CI Enforcement

**Branch:** `h2/d10-drift-enforcement`
**Prerequisite:** D3/D7/D11/D12 all merged onto `main` (confirmed at `dc31789` before this packet starts)
**This packet is post-integration, not part of the original four-way parallel batch.**

## Mission

Extend the D10 minimum baseline (`scripts/check_drift.py`, DRIFT-01..09, captured pre-H2 in
`docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json`) into the full enforcement layer the frozen
spec's "Final Drift Verification Contract" section describes, wire it into CI, and verify it
against the now-fully-integrated H2 state (D3/D7/D11/D12 all present on `main`).

This is infrastructure work, not a feature or a redesign. No H1 contract changes. No H3.

## Required enforcement areas (see `scripts/check_drift.py`'s module docstring for the full
mapping from each area below to its specific new check)

- **D10-A — Canonical construction:** extend beyond RawRequest/Goal/ExecutionPlan/
  CapabilityDiscoveryResult/CompilationResult/OperationRecoveryBudget (already DRIFT-04/08) to
  also cover `CapabilityDiscoveryRequest` and `PlannerRequest` — both genuinely used in this
  codebase (confirmed by direct repository search before assuming either name or shape), each
  with construction sites verified individually rather than assumed to fit the existing
  single-owner-file pattern.
- **D10-B — Frozen entrypoints:** `interpret_request`/`plan`/`compile` importable as callables
  only from their one confirmed production caller.
- **D10-C — Governance boundary:** extend DRIFT-05's existing `evaluate_action()` check (currently
  supervisor.py only) to Intent Interpretation and Planner, without altering DRIFT-05 itself.
- **D10-D — Capability/Adapter boundary:** already covered by DRIFT-02 (forbids
  `core.capabilities.adapter_runtime` imports from `core/cognitive/*.py`) — confirmed, not
  reimplemented.
- **D10-E — Recovery authority:** detect a second, differently-named class implementing
  `OperationRecoveryBudget`'s exact `consume()`/`remaining`/`exhausted` surface outside
  `core/cognitive/recovery.py` — verified this doesn't collide with the legitimate, differently-
  shaped `RetryPolicy` (a config dataclass with no such methods) already used by the workflow
  layer and by `ExecutionPlan`/`PlanStep`.
- **D10-F — Diagnostic/event emission:** already covered by DRIFT-07's existing string-literal-
  argument approach (not method-name-keyed) — confirmed, not reimplemented.
- **D10-G — Forbidden diagnostic transport:** the repository does have a second pub/sub system,
  `core/event_bus.py`'s `EventBus` — confirmed, by direct inspection of its event catalogue and
  every call site, to be a genuinely separate, non-overlapping mechanism (`module.*`/`learning.*`/
  `kb.*`/`brain.*` events; zero `cognitive.*` usage anywhere). New check added to keep it that way
  going forward, not because it's currently violated.
- **D10-H — H1 frozen contracts:** covered at the construction-confinement level via D10-A's
  checks; deep semantic/behavioral equivalence is explicitly out of scope for a static checker
  (documented as a limitation, not silently skipped).
- **D10-I — Packet ownership:** CI invokes `scripts/check_packet_ownership.py` directly; its logic
  is not reimplemented here.
- **D10-J — Architecture markers:** the `RECONCILE-PENDING` marker in
  `OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` must not silently disappear
  without `KNOWN_ISSUES.md` DEBT-011 being recorded as resolved.

## Constraints

- Preserve DRIFT-01..09 exactly as they are; add new checks, don't rewrite existing ones.
- Every new rule needs a positive test (valid architecture passes) and a negative test (a
  known-bad synthetic fixture is actually caught) — the dangerous failure mode this packet must
  avoid is a checker that passes both the current repo and a broken one.
- Reuse `check_packet_ownership.py`; do not duplicate its ownership logic.
- `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json` is a historical snapshot — read, never
  overwritten. A new, separately-named file records the post-H2 state.

## Completion

`docs/Bugs Hunt & fix reports/K4_2_H2_D10_COMPLETION_REPORT.md`. Final status: COMPLETE, BLOCKED,
or ADR REQUIRED. **Stop after D10 — do not perform a final H2 audit or start H3.**
