# K4.2-H2 / D7 — Terminal Impasse Diagnostic Closeout

**You are one of four Claude sessions implementing K4.2-H2 in parallel, with zero contact with the other three.** This brief is self-contained.

**Your branch:** `h2/d7-terminal-impasse-closeout`. Work only on this branch. Do not push to `main`.

**Ownership is mechanically enforced.** Before finishing, run:
```
python3 scripts/check_packet_ownership.py --packet D7
```
It must print `PASS`.

---

## This packet is verification, not implementation — read this before doing anything else

An independent freeze-review session already checked this directly against the code: `core/orchestrator.py`'s re-plan loop emits `cognitive.planner_impasse_terminal` via `self._emit_event(...)` with `trace_id`, `operation_id`, `interaction_id`, `goal_id`, `impasse_detail`, and `recovery_budget_state` in the payload. `scripts/check_drift.py`'s DRIFT-07 check explicitly whitelists this exact emission site as the one documented architectural exception (`docs/architecture/h2_packet_ownership.json` and `scripts/check_drift.py`'s `DRIFT_07_EXCEPTIONS` both reference it). H1's `TestTerminalImpasseEvent` (in `tests/test_orchestrator_recovery.py`) already tests it, including that it does *not* fire on a non-terminal outcome.

**Your job is to independently re-confirm this yourself** — do not just trust this brief's summary, the same way the freeze review didn't trust the completion report's summary without re-deriving it. Concretely:

1. Read `core/orchestrator.py`'s re-plan loop yourself. Confirm the emission call, its payload fields, and that it only fires on budget exhaustion (not on every impasse).
2. Read `tests/test_orchestrator_recovery.py::TestTerminalImpasseEvent` yourself. Confirm it actually exercises this, not just claims to.
3. Compare the payload against the canonical spec's H2-G3 criterion: *"Terminal impasse diagnostic: `cognitive.planner_impasse_terminal` emitted with full payload"* (`docs/architecture/implementation_plan - K42 v1-0 FINAL PRE-FREEZE ARCHITECTURE SPECIFICATION frozen.md`, section 13). Decide for yourself whether "full payload" is satisfied by what exists, or whether something is genuinely missing.

## If your independent check agrees H2-G3 is already satisfied

Write a short closeout ADR (`docs/architecture/decisions/ADR_K4_2_H_07_TERMINAL_IMPASSE_CLOSEOUT.md`, this slot has been reserved since H1) citing the exact file/line and test that satisfy H2-G3, so a future session doesn't re-open this. Do not add any code.

**Explicitly out of scope, even if it seems like an improvement:** per-attempt (non-terminal) impasse event emission. The canonical spec's D7 language is "terminal impasse," singular — not "every impasse." If you believe richer per-attempt diagnostics are genuinely needed, that's new scope requiring its own ADR and roadmap entry from Moncif, not something to fold into this closeout.

## If your independent check disagrees — finds a real gap

**Stop. Do not fix it yourself in this packet.** This packet's manifest entry explicitly forbids touching `core/orchestrator.py` (`docs/architecture/h2_packet_ownership.json`). If you find H2-G3 is genuinely not satisfied, write that finding clearly into your status stub and completion report instead, and mark the packet BLOCKED, not COMPLETE. A human decision is needed before this packet's scope changes.

## Allowed files

- `docs/architecture/h2_status/D7_STATUS.md`
- `docs/architecture/decisions/ADR_K4_2_H_07_TERMINAL_IMPASSE_CLOSEOUT.md`

Nothing else — in particular not `core/orchestrator.py`, and not `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md`/`KNOWN_ISSUES.md`/`docs/architecture/decisions/ADR_INDEX.md`/`PROJECT_INDEX.md`/`tests/conftest.py` (deferred to the sequential integration packet for all four parallel packets).

## How to report done

1. `python3 scripts/check_packet_ownership.py --packet D7` — must print `PASS`.
2. Write `docs/architecture/h2_status/D7_STATUS.md`:

```markdown
# D7 Status

**State:** COMPLETE (verified, no code change needed) | BLOCKED (real gap found)
**Branch:** h2/d7-terminal-impasse-closeout @ <commit sha>
**Ownership check:** PASS/FAIL
**Independent verification result:** <what you found, citing file/line>
**ADR created:** ADR_K4_2_H_07_TERMINAL_IMPASSE_CLOSEOUT.md
**If BLOCKED:** <exact gap, and why it's out of this packet's authorized scope to fix>
```

3. Commit and push only this branch:
   `git push https://<token>@github.com/1h0lde4/ocbrain-v4.1.git HEAD:h2/d7-terminal-impasse-closeout`
