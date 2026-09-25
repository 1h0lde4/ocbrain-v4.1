# HANDOFF — Capability Foundation, Mission 1

**Branch:** `feature/capability-foundation-mission1`
**Status: DRAFT. Not reviewed. Not merged. Not pushed to origin, and not
pushable from this session** — per standing policy (production git actions
are deferred to Claude Code or the GitHub web UI, not run from this chat)
and because every GitHub token seen in this conversation was flagged as
exposed and never used. Everything below exists only as the attached
git bundle until you retrieve it.

## What this is

Ten commits (nine mine + one merge of `origin/main`) on top of
`main@2192b93` (Sept 17, 2026), merged forward to `main@fbd8cc8` (after
PR #20). Implements the three capabilities the mission asked for
(`TEXT_GENERATION`, `STRUCTURED_REASONING`, `FILE_READING`) as additive
extensions to the K2.3 capability runtime, registered only behind
`[capabilities] foundation_enabled = false` (default) — **merging this as
it stands changes zero observable production behavior.**

Read first: `docs/Bugs Hunt & fix reports/
CAPABILITY_FOUNDATION_MISSION1_COMPLETION_REPORT.md` (a standalone copy is
attached alongside this file) — it has the full A–R account, the exact
file manifest, test numbers, and the final quality-gate checklist. Then
`docs/architecture/CAPABILITY_FOUNDATION.md` for the narrative architecture,
and `docs/architecture/decisions/ADR_CAP_01/02/03_*.md` (Status: DRAFT) for
the formal decision record — ADR-CAP-03 in particular documents a real,
measured interaction with ADR-K4.2-H-13 that is the reason the feature flag
exists and should be read before ever setting it to `true`.

## Retrieving the branch

You already have a clone of `github.com/1h0lde4/ocbrain-v4.1` with `main`
reasonably current (this bundle's prerequisites are `main@2192b93` and
`main@5954e44` — both are ordinary points on `main`'s history, so any clone
with `main` fetched past mid-September 2026 has them). From inside that
clone:

```bash
git fetch /path/to/capability-foundation-mission1.bundle \
  feature/capability-foundation-mission1:feature/capability-foundation-mission1
git checkout feature/capability-foundation-mission1
```

Verified in this session: a genuinely fresh `git clone` of the public repo,
followed by exactly the two commands above, produces a working tree with
all ten commits and the correct file content (spot-checked). If your clone
predates those two prerequisite commits, `git fetch origin main` first.

To review commit-by-commit rather than as one diff:

```bash
git log --oneline main..feature/capability-foundation-mission1
git show <commit>          # any one commit
git diff main..feature/capability-foundation-mission1   # the whole delta
```

The nine commits are individually scoped and independently reviewable (see
each one's own message): (1) descriptor/status/lifecycle/provenance model,
(2) `WorkflowRuntime` predecessor handoff, (3) discovery integration,
(4) the three capabilities + 179 tests, (5) the feature-flag wiring,
(6) the three ADRs + architecture doc + two corrections (an ADR-status
label, the pypdf security floor), (7) the four tracking-doc syncs,
(8) the completion report, (9) a self-caught fix to an inflated test count
in five of the files from commits 6–8 (855 → 827 — see that commit's own
message for exactly how it happened and why it's a new commit rather than
an amend).

## Before merging

1. Run `pytest tests/capability_foundation` (179 tests, ~5s) and the
   targeted baseline the completion report's §M names (827 passed / 1
   pre-existing, unrelated failure expected — `TestCtxAuth001ParserAcceptance`,
   tracked separately as CTX-AUTH-001b, present on `main` independent of
   this branch).
2. Run `python scripts/check_drift.py` (15/15 expected).
3. Decide ADR-CAP-01/02/03's disposition (accept/reject/revise) — they are
   Status: DRAFT specifically because that decision is yours, not this
   session's.
4. Leave `foundation_enabled = false` unless/until ADR-CAP-03's open
   question (the `general_purpose_only` interaction) is resolved — see
   that ADR and `KNOWN_ISSUES.md`'s new DEBT-030.

## What's genuinely unfinished (not hidden — see the completion report §Q)

- `Orchestrator.handle()` has no artifact-ingress path, so `FILE_READING`
  is not reachable from a live request yet (DEBT-029).
- The isolated PDF/DOCX/XLSX reader subprocess has process-level isolation
  only, not Sandbox Fabric's namespace/seccomp hardening (DEBT-029).
- A whole-repository `pytest` run was not completed — this sandbox is
  missing `fastapi`/`chromadb` (pre-existing, unrelated to this branch).
- `file_access` itself remains declared and unregistered; this mission
  does not decide its future.

## Credentials

Two GitHub tokens appeared in this conversation (one in an uploaded
`github.env`, one in a preferences field) — both flagged as exposed,
neither used for any git operation in this session. Rotate both at
`github.com/settings/tokens` before doing anything else with this branch.

## Attached in this delivery

- `capability-foundation-mission1.bundle` — the git bundle (fetch as above).
- `CAPABILITY_FOUNDATION_MISSION1_COMPLETION_REPORT.md` — standalone copy
  of the same file committed at `docs/Bugs Hunt & fix reports/` on the
  branch, for reading without fetching the bundle first.
- This file.
