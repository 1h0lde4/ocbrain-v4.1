# K4.2-H2 Parallel Implementation — Coordination Guide

Four Claude sessions implement D3, D7, D11, and D12 concurrently, with zero contact with each other. This directory and `docs/architecture/h2_packet_ownership.json` exist so that works without anyone stepping on anyone else — each session gets a self-contained brief, an exclusive file-ownership scope, and a mechanical check (`scripts/check_packet_ownership.py`) that enforces the scope instead of just documenting it.

If you are one of the four sessions: go read your own brief (`D3_CAPABILITY_DISCRIMINATION.md`, `D7_TERMINAL_IMPASSE_CLOSEOUT.md`, `D11_LANGUAGE_SUPPORT.md`, or `D12_TRACKING_HARDENING.md`) — it's self-contained. The rest of this file is mostly for whoever merges the four branches back together afterward.

## The four branches

| Packet | Branch | Brief | Status stub |
|---|---|---|---|
| D3 | `h2/d3-capability-discrimination` | `D3_CAPABILITY_DISCRIMINATION.md` | `../h2_status/D3_STATUS.md` |
| D7 | `h2/d7-terminal-impasse-closeout` | `D7_TERMINAL_IMPASSE_CLOSEOUT.md` | `../h2_status/D7_STATUS.md` |
| D11 | `h2/d11-language-support` | `D11_LANGUAGE_SUPPORT.md` | `../h2_status/D11_STATUS.md` |
| D12 | `h2/d12-tracking-hardening` | `D12_TRACKING_HARDENING.md` | `../h2_status/D12_STATUS.md` |

All four were created from the same commit — the one that added this directory, `scripts/check_drift.py`, and the D10 pre-H2 baseline. D10's own full packet (wiring `check_drift.py` into the normal pytest run) and the final cross-packet integration packet are **not** part of this parallel batch — both are sequenced *after* these four land, per the dependency graph in `docs/Bugs Hunt & fix reports/K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md` section 6.

## The design principle, restated

None of the four packets touches a file another packet, or a later integration step, would also need to touch. Concretely: **`CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md`, `docs/architecture/decisions/ADR_INDEX.md`, `PROJECT_INDEX.md`, and `tests/conftest.py` are off limits to all four packets, without exception.** This is what makes true zero-contact parallelism safe: four sessions racing to edit the same file is a guaranteed collision; four sessions each writing to their own exclusive files, then one later pass consolidating, isn't.

## Test & drift baseline at the point these branches were created

Record this here once, so no packet brief needs to guess it or re-derive it independently:

- **Full suite:** 1174 passed / 34 failed. The 34 are a known, pre-existing, environment-only class (this sandbox cannot reach `huggingface.co`) — not something any H2 packet is expected to fix. Any *new* failure beyond these 34 needs an explanation, not a shrug.
- **Drift baseline:** `scripts/check_drift.py` — 9/9 PASS (one documented exception applied: `core/orchestrator.py`'s `cognitive.planner_impasse_terminal` emission). See `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json` for the full captured report.

## What happens after all four land (the integration step)

This is deliberately **not** one of the four parallel packets — it runs sequentially, by a human or a fifth Claude session, after D3/D7/D11/D12 all have a pushed branch with a `COMPLETE` status stub. Broad shape (full detail: readiness plan section 13):

1. `git fetch` all four branches.
2. Merge each into a working branch (or directly into `main`, if that's the chosen process) **one at a time**, not all at once — re-run the full test suite and `scripts/check_drift.py` after each merge, not just at the end. Because the four packets' *code* changes are file-disjoint by construction, these merges should be conflict-free at the code level. The one place a conflict is actually plausible is if two packets' branches both happened to touch the same *newly-created* shared-adjacent file by mistake — which is exactly what `check_packet_ownership.py` run per-branch before merging is meant to catch first.
3. Read all four status stubs (`docs/architecture/h2_status/*.md`). Use them, not guesswork, to write the consolidated update to `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, and `docs/architecture/decisions/ADR_INDEX.md` (folding in D3's possible `ADR_K4_2_H_03`, D7's `ADR_K4_2_H_07`, D11's `ADR_K4_2_H_11`, and D12's `ADR_K4_2_H_10`/`ADR_K4_2_H_12`).
4. If D12's status stub says `IMPLEMENTATION_TRACKER.md` was created, verify it doesn't duplicate what `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md` already say before merging it in.
5. Re-run `scripts/check_drift.py` against the fully-merged state — this is the real "after H2" comparison the D10-full packet's `tests/test_architecture_drift.py` should then wire in permanently.
6. Only then: full H2-G1 through H2-G9 acceptance-gate pass (canonical spec section 13; also reproduced in the readiness plan section 18), K4.2 v1.0 freeze consideration.

## If a packet reports BLOCKED

Don't try to unblock it as part of merging the other three. Merge what's clean, record what's blocked (from its status stub) in the integration report, and treat the blocker as its own follow-up — the same "stop and flag, don't silently resolve" discipline this whole project runs on.
