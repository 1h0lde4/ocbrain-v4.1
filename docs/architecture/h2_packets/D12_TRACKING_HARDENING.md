# K4.2-H2 / D12 — Implementation Tracking Hardening (parallel-safe scope)

**You are one of four Claude sessions implementing K4.2-H2 in parallel, with zero contact with the other three.** This brief is self-contained.

**Your branch:** `h2/d12-tracking-hardening`. Work only on this branch. Do not push to `main`.

**Ownership is mechanically enforced.** Before finishing, run:
```
python3 scripts/check_packet_ownership.py --packet D12
```
It must print `PASS`.

---

## Read this before assuming you know D12's scope

If you've seen `docs/Bugs Hunt & fix reports/K4_2_H2_READINESS_AND_IMPLEMENTATION_PLAN.md` section 12, that version of D12 is **broader** than what you're authorized to do here. That version assumed D12 could record D3/D7/D10/D11's completion status in `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md` — which a zero-contact parallel session genuinely cannot do honestly, because you have no way to know whether the other three packets have finished, or what they actually delivered. Writing "D3 complete" into a shared tracking file when you can't verify that is worse than not writing it at all.

This brief's scope is deliberately narrower. The full tracking sync happens in the sequential integration packet, after all four branches actually exist and can be inspected together — not here.

## Your two jobs

### Job 1 — Resolve the `IMPLEMENTATION_TRACKER.md` question

This file is referenced by name in `PROJECT_INSTRUCTIONS.md`, the original H1 implementation packet, and this task's own instructions — but it does not exist in the repository. Both the H1 completion report and an independent freeze review already noticed this and declined to silently resolve it.

Decide, and justify your decision in `docs/architecture/h2_status/D12_STATUS.md`:
- **(a) Create it**, scoped narrowly enough not to duplicate `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`'s existing purpose (for example: a packet-level ledger — packet ID, commit, ADR, verification status, one line each — that those two higher-level files summarize rather than repeat). If you create it, it's a new file — no collision risk with anything else.
- **(b) Formally decline**, recording in your status stub *why* the two existing files already serve this purpose and a dedicated tracker would be redundant.

Either is an acceptable outcome. Silence is not — record the decision either way.

### Job 2 — Draft the reserved ADRs

Two ADR slots have been reserved since H1 for H2's documentation-adjacent decisions:
- `ADR_K4_2_H_10_DRIFT_TOOLING_RECORD.md` — records the D10 baseline-capability decision already made and implemented (the checker's design, the DRIFT-07 exception, the heuristic-vs-mechanical distinction for DRIFT-06/09). Read `scripts/check_drift.py`'s own docstrings and `docs/architecture/D10_PRE_H2_DRIFT_BASELINE.json` before writing this — it should reflect what was actually built, not a generic description.
- `ADR_K4_2_H_12_TRACKING_HARDENING.md` — records your own Job 1 decision and its rationale.

Follow this project's existing ADR format (see any `ADR_K4_2_H_0X_*.md` file for the template) and lifecycle (`DRAFT → REVIEW → APPROVED → IMPLEMENTED → FINAL`) — these land as `DRAFT`, since they haven't gone through review yet.

## Allowed files

- `docs/architecture/h2_status/D12_STATUS.md`
- `docs/architecture/decisions/ADR_K4_2_H_10_DRIFT_TOOLING_RECORD.md`
- `docs/architecture/decisions/ADR_K4_2_H_12_TRACKING_HARDENING.md`
- `IMPLEMENTATION_TRACKER.md` — only if your Job 1 decision is to create it

Nothing else. In particular, **do not touch** `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md`, `docs/architecture/decisions/ADR_INDEX.md`, or `PROJECT_INDEX.md` — even though "tracking hardening" sounds like it should include these, updating them correctly requires knowing what D3/D7/D11 actually delivered, which you can't know. They're deferred to the sequential integration packet, for all four parallel packets equally. Do not add your new ADRs to `ADR_INDEX.md` yourself — the integration packet does that for all new ADRs from all packets in one consolidated pass, to avoid four sessions concurrently appending to the same list.

## How to report done

1. `python3 scripts/check_packet_ownership.py --packet D12` — must print `PASS`.
2. Write `docs/architecture/h2_status/D12_STATUS.md`:

```markdown
# D12 Status

**State:** COMPLETE | BLOCKED
**Branch:** h2/d12-tracking-hardening @ <commit sha>
**Ownership check:** PASS/FAIL
**IMPLEMENTATION_TRACKER.md decision:** created (scoped as: ...) | declined (because: ...)
**ADRs drafted:** ADR_K4_2_H_10_..., ADR_K4_2_H_12_... (status: DRAFT)
**Notes for the integration packet:** <anything about how to fold these ADRs into ADR_INDEX.md, or IMPLEMENTATION_TRACKER.md's format if created>
```

3. Commit and push only this branch:
   `git push https://<token>@github.com/1h0lde4/ocbrain-v4.1.git HEAD:h2/d12-tracking-hardening`
