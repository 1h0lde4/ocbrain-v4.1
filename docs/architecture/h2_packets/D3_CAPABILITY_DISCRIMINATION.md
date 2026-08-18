# K4.2-H2 / D3 — Capability Discrimination Acceptance Suite

**You are one of four Claude sessions implementing K4.2-H2 in parallel, with zero contact with the other three.** This brief is self-contained — you should not need the rest of the conversation history that produced it. If anything here seems to assume context you don't have, treat that as a reason to stop and re-read the cited files, not to guess.

**Your branch:** `h2/d3-capability-discrimination`. Work only on this branch. Do not push to `main`. Do not merge anything into `main` yourself — a later, separate integration step handles that.

**Ownership is mechanically enforced, not just documented.** Before you consider this packet done, run:
```
python3 scripts/check_packet_ownership.py --packet D3
```
It must print `PASS`. If it prints a `VIOLATION`, you have touched a file outside this packet's scope — stop and reconsider before proceeding, don't override the check.

---

## Context you need

Read these, in order, before writing anything:
1. `CURRENT_STATE.md` and `IMPLEMENTATION_ROADMAP.md` — confirm H1 is FROZEN and H2 is the active milestone (it should already say this; if it doesn't, STOP — something has changed since this brief was written, and you should report the discrepancy rather than proceed).
2. `docs/Bugs Hunt & fix reports/K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md`, section 8 (D3 Packet) — the fuller version of what follows, with the cross-milestone dependency graph for context.
3. `docs/architecture/h2_packet_ownership.json` — the file-ownership manifest this brief's boundaries come from.
4. `tests/core/cognitive/test_planner.py`, the `TestGeneralPurposeFallback` class — H1 already built two of the six behaviors this packet needs; read them before writing anything new so you extend the established pattern rather than inventing a third style.
5. `core/cognitive/planner.py`'s `discover_capabilities()` and the `CapabilityContract`/`CapabilityMatch`/`CapabilityDiscoveryResult` dataclasses (also in this file).

## Objective

Prove, with a genuinely distinct second capability class, that capability discovery discriminates correctly — not just that it doesn't crash. Deliver `tests/test_capability_discrimination.py`.

## Allowed files

- `tests/test_capability_discrimination.py` (new)
- `docs/architecture/h2_status/D3_STATUS.md` (your status stub — see "How to report done" below)
- `docs/Bugs Hunt & fix reports/K4_2_H2_D3_COMPLETION_REPORT.md`
- `docs/architecture/decisions/ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md` (this slot has been reserved since H1 — use it if this packet's work merits an ADR, e.g. if the open question below resolves to "yes, a real gap exists")
- `core/cognitive/planner.py` — **conditionally only**, see "Open question" below. Do not touch it otherwise.

Nothing else. In particular: not `core/cognitive/intent.py`, not `core/cognitive/compiler.py`, not `core/orchestrator.py`, not `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`/`KNOWN_ISSUES.md`/`docs/architecture/decisions/ADR_INDEX.md`/`PROJECT_INDEX.md`/`tests/conftest.py` — those five-plus-conftest are off limits to *all four* parallel packets without exception; a later integration step consolidates them.

## Frozen contracts you must not change

`min_score=0.01` (H1 kept this deliberately un-weakened; this packet doesn't get to weaken it either). `CapabilityMatch`'s existing evidence fields. `is_general_purpose`'s existing semantics (fallback, not override — H1's Decision 2).

## The six required behaviors

Three source documents label these slightly differently (this brief's own A–F, the original H1 packet's "Test 1–6", the canonical spec's "Cases A–E + dynamic registration") — the substance is identical across all three; use the labels below.

| Label | Behavior | Notes |
|---|---|---|
| A — General-purpose fallback | A broad request with no specific match is rescued by the general-purpose capability | H1's `test_general_purpose_bypasses_min_score` already covers this against the real `LLM_COMPLETION` capability. Use a **test-only** general-purpose capability here instead, so this suite doesn't depend on production capability wording. |
| B — Specificity dominance | A genuinely distinct specific capability outranks the general-purpose fallback | H1's `test_specificity_dominance_ranks_specific_above_general` already does this with a test-only `flight_booking` contract — reuse that pattern. |
| C — Unsupported request | Neither capability is selected for a request outside both their semantics | **Not covered by any existing H1 test.** New coverage. |
| D — Registration-order independence | Registering the two test capabilities in the opposite order does not change which one wins | **Not covered by any existing H1 test.** See "Open question" — don't assume the answer, test it. |
| E — Dynamic registration | Adding the second capability requires zero changes to `planner.py` | Should follow naturally from registry-based discovery — write the test as a genuine proof, not an assumption. |
| F — Evidence | The winning `CapabilityMatch` exposes *why* it won | H1 already asserts on `evidence["specificity_tier"]`/`evidence["general_fallback"]` inline within other tests — give this its own explicitly named test here. |

Use test-only capability contracts, constructed and registered inside this test file's own scope (a local `CapabilityRegistry` instance, not the production one). Do not add a real production capability type merely to satisfy this suite.

## Open question — resolve it, don't assume it

Does the current `discover_capabilities()` scoring already guarantee order-independence (Case D), or does it have an implicit "first capability at max score wins" tie-break that depends on registration order? This was genuinely unknown when this brief was written — writing Case D's test is how you find out.

- If Case D passes against the unmodified current implementation: done, move on.
- If it fails and needs more than a trivial, clearly-deterministic tie-break fix in `planner.py`: **stop before writing that fix.** Write `ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md` first, explaining the gap, why the fix is needed, and what it changes. Only then touch `planner.py`, and only the minimal change the ADR describes.

## Tests

The six behaviors above, each independently named and assertable. A boundary test confirming the test-only capabilities never touch the production registry. Run everything against the real `discover_capabilities()` — do not mock it.

## Stop conditions

- Case D requiring a non-trivial `planner.py` change (see above).
- Any of A/B/C/E/F revealing `discover_capabilities()` doesn't behave as H1's freeze review described — that would mean either this brief or the freeze review has stale information, and is worth flagging explicitly rather than silently working around.

## How to report done

1. Run `python3 scripts/check_packet_ownership.py --packet D3` — must print `PASS`.
2. Run `python3 -m pytest tests/test_capability_discrimination.py -v` — all passing.
3. Run `python3 -m pytest tests/ -q --tb=no` — compare against the known baseline noted in `docs/architecture/h2_packets/README.md`. Any *new* failure beyond that baseline needs an explanation in your completion report, not a silent shrug.
4. Run `python3 scripts/check_drift.py --quiet` — should still be 9/9 PASS (one expected exception). If not, don't fix it by editing the checker or the target code without understanding why first.
5. Write `docs/architecture/h2_status/D3_STATUS.md` (see template below).
6. Write `docs/Bugs Hunt & fix reports/K4_2_H2_D3_COMPLETION_REPORT.md` following this project's nine-step packet completion-report convention.
7. Commit on `h2/d3-capability-discrimination`. Push that branch only:
   `git push https://<token>@github.com/1h0lde4/ocbrain-v4.1.git HEAD:h2/d3-capability-discrimination`
   (token used transiently as a one-off push URL argument only, never stored in `.git/config`, per this project's standing convention).

### `D3_STATUS.md` template

```markdown
# D3 Status

**State:** COMPLETE | BLOCKED | PARTIAL
**Branch:** h2/d3-capability-discrimination @ <commit sha>
**Ownership check:** PASS/FAIL (paste output)
**Tests added:** N, all passing / X failing (list)
**Regression check:** <passed>/<failed> vs baseline of <N> — new failures explained below or none
**Drift check:** 9/9 PASS | N violations (list)
**Open question resolution:** Case D passed unmodified / required planner.py change (ADR: ...)
**ADR created:** yes (ADR_K4_2_H_03_...) / no, not needed
**Notes for the integration packet:** <anything the person merging branches should know>
```
