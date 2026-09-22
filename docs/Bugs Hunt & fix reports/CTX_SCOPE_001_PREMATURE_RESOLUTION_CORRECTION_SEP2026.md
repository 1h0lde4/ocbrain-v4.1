# CTX-SCOPE-001 — Premature-Resolution Correction (Sept 16-17, 2026)

## What happened

An earlier session this same day (branch `fix/ctx-scope-001-live-callers-sep2026`,
based on `main` @ `e9a9cde`) built a full CTX-SCOPE-001 remediation:
wired the three previously-tracked live call sites, plus found and fixed
two further live gaps (`set_long_term_memories_string()`'s single
process-global field, `classifier.py:45`'s misattributed-dormant
`boost_module()` call), with tests, an ADR, and synced tracking docs.
Before pushing, a fetch-first check surfaced that `main` had moved
substantially — a separate, independently-run session had, in parallel,
built and merged **PR #14** (`fix/ctx-scope-001-caller-wiring`), wiring
the same three originally-tracked sites, and the tracking docs had
already been synced to say **"CTX-SCOPE-001 is resolved."**

Direct verification against `origin/main`'s actual code — not the
tracking docs' own claim — found that PR #14's work was itself correct
and well-reasoned for what it covered, but did not include either of
the two additional findings the other session had independently
discovered. Both were confirmed still live and unaddressed on current
`main`. The "resolved" claim was therefore premature: a real,
live cross-execution leak (long-term-memory content, and the
classifier's module-usage boost) existed on `main`, documented as
closed.

## Reconciliation, not a merge

Rather than attempt to merge two independently-written, overlapping
implementations of the same wiring, a fresh branch
(`fix/ctx-scope-001-long-term-memory-and-classifier-sep2026`) was built
off current `main`, carrying forward only what PR #14 didn't already
have: the `boost_module()`/`set_long_term_memories_string()`/
`set_long_term_memories()` scope-keyed storage redesign in
`core/context.py`, the `classifier.py` fix, and their tests — all of
which apply cleanly since PR #14 never touched those two files. Two
small edits were made on top of PR #14's own (unmodified, correct)
implementation: `core/workers/planner.py`'s `_run()` needed its
existing `scope` computation moved earlier so the long-term-memory call
could use it too (PR #14 only computed it where `.save()` needed it),
and `interface/api.py`'s `classifier.label()` call site needed the new
`scope=` argument now that the function accepts one.
`core/workers/capability_executor.py` was deliberately left untouched,
deferring to PR #14's own explicit reasoning for that exact call site
(safe today by accident, not by design; not a confirmed live site) —
the same standard this project applies to `entities`/`get_entity()`.

## Documentation correction, not silent rewrite

`KNOWN_ISSUES.md`, `CURRENT_STATE.md` (both its summary table and its
historical narrative — the latter left in place, with a dated
correction appended, per this project's own established
strikethrough-and-append convention rather than silent editing), and
the remediation register (REM-006 moved back from the Resolved table
to Tier 1, since wiring being complete is not the same claim as the
full adversarial/concurrency proof suite having been run) were all
corrected to reflect the true state: wiring is now genuinely complete
across both passes, the finding is not resolved, full suite 1,512
passed / 1 failed (the same pre-existing, unrelated CTX-AUTH-001
marker).

One thing deliberately not done: the "Decided, Sept 13, 2026 (Moncif,
explicit)" text in `CURRENT_STATE.md` was left intact rather than
struck through. That was a correctly-made decision on the information
available to that session at the time — the problem was that the
information was incomplete, not that the decision was wrong given it.

## Verdict

Not issued. Per the governing task's own completion criteria, a
verdict requires the adversarial/concurrency/lifecycle proof suite
(mission doc §8-34) to exist and pass first — for either pass's
wiring. That work has not started.
