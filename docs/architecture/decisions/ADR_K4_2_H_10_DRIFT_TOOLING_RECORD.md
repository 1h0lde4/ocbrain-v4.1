# ADR-K4.2-H-10: Architecture-Drift Verification Tooling (D10 Baseline Record)

**Status:** ACCEPTED (promoted from DRAFT at K4.2-H2 integration, Aug 22, 2026 — this ADR only records already-built, already-working tooling rather than proposing a new change; `scripts/check_drift.py` ran 9/9 PASS repeatedly throughout integration, both before and after merging all four H2 packets plus the out-of-band ADR-K4.2-H-13 fix)
**Date:** August 19, 2026
**Author:** K4.2-H2-D12 packet (Tracking & Documentation Hardening)
**Scope:** `scripts/check_drift.py`; `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json`

---

## 1. Context

The frozen pre-freeze architecture specification (`docs/architecture/implementation_plan -
K42 v1-0 FINAL PRE-FREEZE ARCHITECTURE SPECIFICATION frozen.md`, section 9, "Final Drift
Verification Contract (Corrected)") defines nine architecture-drift checks, DRIFT-01
through DRIFT-09. The K4.2-H2 readiness plan (`docs/Bugs Hunt & fix reports/
K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md`, section 3 / D10 packet) authorized a
*minimum baseline capability* ahead of full H2 implementation: capture a "before H2"
snapshot now, so it can be diffed against an "after H2" snapshot once D3/D7/D11 land.
Full CI wiring is explicitly a separate, later packet ("D10 full"), sequenced after the
four H2 parallel packets land (`docs/architecture/h2_packets/README.md`).

This ADR records what was actually built for that baseline, per this packet's Job 2 —
it documents an existing implementation, not a new decision.

## 2. Decision

`scripts/check_drift.py` implements exactly the nine spec-defined checks via AST-based
static analysis over `core/` — no additional checks beyond the frozen spec's nine, no
type-checker or import-resolution machinery.

- **DRIFT-01 through DRIFT-05, DRIFT-08:** mechanical AST checks (import restrictions,
  construction-site restrictions for the six canonical contract dataclasses, a direct
  method-call restriction). DRIFT-08 is explicitly the "[CORRECTED]" version per the
  frozen spec, exempting `tests/*.py`.
- **DRIFT-06** (no hard-coded capability-type strings in Planner routing) and **DRIFT-09**
  (no unauthorized shared-contract producer) are implemented as documented, conservative
  heuristics, per the script's own docstring — the frozen spec itself only describes these
  two loosely ("literal string analysis", "producer source analysis"). A VIOLATION from
  either is specified to be "a prompt for a human read, not proof of an actual architecture
  break," not an automatic failure verdict.
- **DRIFT-07** (`cognitive.*` events emitted only from `core/cognitive/` or
  `core/workers/`) has exactly one declared, spec-traceable exception today:
  `(core/orchestrator.py, cognitive.planner_impasse_terminal)`, justified by the frozen
  plan's own §9 "DRIFT-07 Exception" and owned by D7's terminal-impasse diagnostic work.
  The exception mechanism requires every entry be traceable to a specification section —
  it is a declared allow-list, not an ad hoc bypass.
- Output: JSON to stdout (or `--out FILE.json`); `--quiet` suppresses only the stderr
  human-readable summary. Exit code 0 iff every check is PASS (a documented exception
  still counts as PASS for DRIFT-07); 1 if any check reports a VIOLATION.

**Baseline result:** `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json`, captured
2026-08-18T06:29:04Z — 9/9 PASS, zero violations. This packet independently re-ran
`scripts/check_drift.py` on `h2/d12-tracking-hardening` (2026-08-19T07:42 UTC, same
commit as the baseline) and reproduced 9/9 PASS with an identical per-check outcome —
confirming zero drift between baseline capture and this session, and confirming the
committed JSON artifact reflects a script that was actually executed, not hand-written.

## 3. Consequences

- **Update (Aug 22, 2026, K4.2-H2-D10 packet, merged into main):** the item below is
  resolved — full CI wiring now exists as `.github/workflows/ci.yml`, gating on
  `pytest` (against a documented known-environmental-failures reference list, not raw
  exit code) plus this same `check_drift.py` (now DRIFT-01..15). Not
  `tests/test_architecture_drift.py` as anticipated below — the actual implementation
  extended the existing `tests/test_check_drift.py` instead, which already had the
  right AST-fixture conventions to build on. See
  `docs/Bugs Hunt & fix reports/K4_2_H2_D10_COMPLETION_REPORT.md` for the full record,
  including independent adversarial validation in
  `K4_2_H2_FINAL_INDEPENDENT_AUDIT.md` §10.
- ~~Full CI wiring (automatic invocation in the standard pytest run, e.g. a
  `tests/test_architecture_drift.py`) remains explicitly out of scope for this baseline
  capability — that is the separate "D10 full" packet, sequenced after D3/D7/D11/D12
  land, per `h2_packets/README.md`.~~
- DRIFT-06 and DRIFT-09's heuristic nature is a recorded, deliberate trade-off: a future
  VIOLATION from either needs a human read before being treated as a real architecture
  break. This ADR exists partly so a future session does not "tighten" these into false
  mechanical certainty without deliberately re-deciding that trade-off first.
- The DRIFT-07 exception set is a single hard-coded tuple set in the script; any future
  exception must be added there with an inline spec citation, the same way the one
  existing entry is justified — this ADR is part of that citation trail.

## 4. Alternatives considered

- **Type-checker- or import-graph-based analysis**, instead of AST-name-based static
  analysis: rejected for legibility, per LAW 4 (Determinism Over Magic). The script's own
  docstring states the accepted cost directly — a call routed through an aliased import,
  or an intermediate variable of the same runtime type but a different static name, will
  not be caught. This is the deliberate, inspectable trade-off, not an oversight.
- **Wiring into CI as part of this same baseline packet**: rejected — out of the D10
  baseline's declared scope. Deferred by design to the sequential "D10 full" packet, per
  the H2 readiness plan's dependency ordering (D10 full runs after the four parallel
  packets, not alongside them).

