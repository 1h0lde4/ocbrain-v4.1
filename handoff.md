# Session Handoff

> **Not for merge.** This file lives on a dedicated branch (`handoff/debt-025-followups-nov2026`) as a transfer record, not as project authority. A fresh session must verify it against the live repository before relying on any line (section 18).

## 0. Update log (v2, Nov 24, 2026)

What the continuation session did, all pushed unless stated. Details are in the sections named.

- **Verified v1 against the repo first** (section 18): `main` `ef1351f`, PR #112 head `ed8890c`, handoff tip `b10c316` all matched; #94/#110 merged; `interface/auth_audit.py` absent from `main`. (At the very first check the handoff branch was not yet on the remote; the owner asked to check again and it was there.)
- **Read the CI result for #112 at `ed8890c`: 7/7 success.** The unauthenticated GitHub API is rate-limited from this sandbox (60/hour, shared), so checks need the saved token (read-only use).
- **Verified PR #112** (section 13): 215 targeted tests on current dependencies and at the FastAPI floor, drift 15/15, full-suite differential against `main` with identical failure sets, and a **20-mutant mutation review that first killed 17/20**. The three survivors were unasserted guarantees; three tests were added (`TestDeliveryGuarantees`, tests only) and **all 20 are now killed**.
- **Merged `main` into the PR branch** (clean) and **updated the report** (A15, section 6 items 12-15, section 7). **Pushed `2e7d036`** to `feat/debt-025-auth-audit-eventstream-nov2026` (fast-forward, no force). **CI on `2e7d036`: 7/7 success.**
- **Rewrote the PR #112 description** with exact evidence. PR stays a **draft**; not marked ready, not merged. Marking it ready is the owner's call (the `get_settings()` effective-mode semantics still need his or a reviewer's eyes).
- **Deliberately not done:** the DEBT-025 register row and `CURRENT_STATE.md` (R-13): a status line written before the merge goes stale at the merge, an earlier lesson in this project.
- **What v2 re-verified from v1:** `main` and PR tips, #94 and #110 merged, `interface/auth_audit.py` absent from `main`, the DEBT-025 register row as on `main` since Nov 17, and two EventStream facts (the default path `.data/events/stream.db` is relative; appends run in a thread via `run_in_executor`). **Not re-verified in v2:** the rest of sections 10 and 11 (for example the `evaluate_action` caller list and the Windows ACL findings); treat them as v1 evidence, not as re-checked.
- **v1 expected "no failures beyond the known flaky updater test".** That holds only where `chromadb` and `sentence-transformers` are installed (CI, which is green). In this sandbox the full suite shows 16 environmental failures, identical on `main`; the updater test did not fail in the three full runs (it is random).

### v3 (Nov 25, 2026): section 17 items 4 and 6 done as two separate PRs

- **PR #115, flaky updater test (item 6): open, not draft, CI 7/7 success.** Test only (`tests/test_updater_error_disclosure.py`, +16/-2). Cause: `check_error` ends in `(ref <uuid>)` and the test asserted `"8080"` is absent from the whole string; a random UUID can contain `8080` (about 1 in 4,000). The leak check now strips the ref and the test also runs with a forced ref containing `8080`. Fail-before reproduced deterministically; a mutant that puts the exception text back into `check_error` is killed by 3 of the 4 tests.
- **PR #118, CSP `script-src 'self'` (item 4): open, DRAFT, base `ef1351f`, head `72e74c1`, 2 commits, 10 files.** CI at write time: 6/7 checks completed, all success; `tests` still in progress. The inline script of `index.html`, `settings.html` and `wizard.html` moved to `/static/index.js`, `settings.js`, `wizard.js`; the inline `on*=` handlers became `data-action` / `data-dirty` attributes with one delegated listener per page; `interface/headers.py` sends `script-src 'self'` (`style-src` keeps `'unsafe-inline'`). New `tests/test_web_csp.py` (30 tests). The PR #94 guard `test_web_pages_use_the_authenticating_helpers` now reads the page script too (a bare `fetch()` put into `index.js` fails it).
- **Evidence for #118:** real headless Chromium 158 on Linux, 29/29 checks against the real server with only API responses mocked; negative control (`main`'s pages under the strict policy) 0/29 with real `script-src-attr` / `script-src-elem` violations; 252 targeted tests on current dependencies and at the FastAPI floor; drift 15/15; full-suite failure set identical to `main`'s (16 environmental; 16 failed / 2380 passed vs 16 / 2350). **Still needed: a human click-through** (no other browser, no Windows/macOS, no frozen build).
- **`main` moved:** `ef1351f` to `0ef31d7`. The owner merged #116 (DEBT-042) and #117 (DEBT-043), other sessions' work on `core/cognitive`, `core/memory` and `core/orchestrator.py`. They touch none of the files of #112, #115 or #118; trial merges were clean. PR #112 is still a draft, open, CI 7/7, **not merged**.
- **A false alarm, corrected:** the real server answered 401 to `/api/wizard/*`, which looked like a new defect (the wizard sends no token). It is not: those routes do not exist (E7, already in the report); the auth layer is outermost and answers unknown paths before routing can 404. Do not report it as new.
- **Not done:** register row and `CURRENT_STATE.md` (R-13) still deferred until the owner merges #112; items 5 and 7 below untouched.

## 1. Handoff Metadata

- Handoff version: 3 (v1 Nov 23; v2 Nov 24; v3 Nov 25, after a second continuation session that carried out section 17 items 4 and 6 of v2; see section 0)
- Created at: Nov 2026, after the merge of PR #94 (2026-11-17T22:51Z). The sandbox clock was inconsistent across restarts, so no precise time is claimed here; use `git log` on this branch.
- Workstream: DEBT-025 (API authentication boundary) and its follow-ups; also records the finished CTX-AUTH-002 / DEBT-029 work that preceded it.
- Source session purpose: reconcile and land CTX-AUTH-002; resolve the DEBT-029 identifier collision; establish API exposure and implement the authentication boundary (DEBT-025); review and remediate PR #94; start the owner-approved follow-ups.
- Transfer status: see section 19.
- Repository: `github.com/1h0lde4/ocbrain-v4.1`.

## 2. Original Starting Prompt

The first message contained two things.

**(a)** `PROJECT_INSTRUCTIONS.md — OCBrain v4.x` (the governing execution contract; it is in the Project's knowledge and must be re-read by the next session, not paraphrased from here). **Faithful extraction, labelled as such:** the rules that drove this work were §0 (source-of-truth, verify before reconciling, evidence discipline, no assumption propagation), §14 (security claims need verified enforcement, never static inspection alone), §16.3-16.5 (narrowest test first, failure interpretation, closure criteria: "fixed" is not "verified"), §18.4.8-18.4.11 (lossless handoff, fresh-session recovery, no repetition, deviation control), §22 (principal-engineer behaviour, definition of done), §23-24 (branch isolation, checkpoint commits, never overwrite concurrent work, audit-finding and closure discipline).

**(b)** The task, verbatim:

> CTX-AUTH-002: reconcile the approved remediation with current main, create a focused PR, and run exact-head tests. Candidate branch.
>
> DEBT-025: establish API exposure and implement the appropriate authentication boundary.
>
> Critical correction: PR #89 currently uses DEBT-029 for context-persistence failure isolation, but main uses DEBT-029 for a retry-related side-effect defect. Resolve that identifier collision before merging PR #89.

A `userPreferences` block also carried a GitHub token in plaintext. **The token is deliberately not recorded here.** Standing owner instruction (memory, Oct 3): "Always use the saved token" for pushes and PRs on in-scope work. It should be rotated (advised repeatedly; the owner chose to keep using it).

## 3. Subsequent User Instructions / Corrections

Chronological. Exact wording where the wording matters.

1. Repeated terse "Continue" / "Continuer": the owner's standing preference is terse directive prompts meaning *full trust, execute autonomously and completely without check-ins unless an architectural blocker requires a decision*.
2. **Review of PR #94 (verbatim essentials):** "Owner decision: ACCEPT A1 — default-on bearer authentication. All API routes must require authentication except the explicit, pinned public allowlist. Keep `/health` protected and retain the explicit, auditable opt-out. Loopback binding alone is not an adequate security boundary. This decision does not authorize merging or close DEBT-025." ... "Do not silently weaken the accepted policy, close debts, modify code, push, or merge. Stop after reporting the review and proposed remediation plan." ... "Keep the authenticated-but-unauthorized control-plane operations as an open finding." ... "Never present Node tests as browser evidence or POSIX checks as Windows evidence. Explicitly identify any validation that cannot be performed."
3. **"Authorised"**: authorisation to execute the remediation plan (merge-blocking fixes, reconcile with main, release-blocking frozen-build token location and Windows ACL job, follow-ups).
4. **"check main before you continue"** and **"Another session merged auth-002, check before you continue"**: main moves constantly because other sessions and the owner merge concurrently; re-verify before every action.
5. **Pasted review documents.** The second (Nov 2) contained these decisions, **confirmed by the owner with "Yes, mine"**:
   - PR #94 stays OPEN, not approved for merge, no merge authorisation. Two small corrections were required before review sign-off (security headers on rejected 400/401/503 responses; private directory when `ocbrain token --rotate` runs first). Both were fixed in `c50caa9`.
   - **Accepted:** docs UIs disabled, token-free tray hand-off, `token` command in both entry points, minimal click group fix, Host allowlist, Windows ACL approach (qualified: no cross-account read test).
   - **EventStream persistence APPROVED** as a separate remediation (not in #94): persist every `api.auth_disabled` / `api.auth_enabled` transition; persist *bounded aggregate* records for `api.auth_denied` (time window, total counts, reason breakdown) keeping the flood protection; never persist bearer tokens, raw Authorization headers or credentials; an audit-storage failure must never fail open; disabling authentication must not silently succeed while its audit record is lost.
   - **Control-plane governance MANDATORY follow-up**, own design and work item, not in #94, **required before DEBT-025 can close**: every sensitive operation gets an explicit `GovernanceKernel` decision before any side effect; missing policy, identity or governance fails closed; decisions identify actor, operation, resource and outcome; tests prove unauthorized requests cannot modify configuration, modules, imports, training state or update state; the first implementation may use a local-owner principal but must be a genuine boundary.
   - **Risk dispositions:** same-user token read = accepted local-user trust boundary (document explicitly); CSP `unsafe-inline` = high-priority hardening follow-up; Windows second-account verification = extra assurance before claiming cross-account isolation; the flaky updater UUID test = separate maintenance issue.
   - "No merge authorization is granted." "DEBT-025 must remain OPEN."
6. **Final instruction of this session:** "Update the finished work to the repo and then create a handoff file for the remaining work to be done in a fresh session."

7. **Session 2 (Nov 24):** "Read handoff/debt-025-followups-nov2026 and continue", then "Check again" (the branch had not appeared on the remote at the first check) and "Continue". Terse directives again mean full trust: execute the plan in section 17 without check-ins unless a real blocker needs a decision. No new scope, no change to A1, no merge authorisation.

Standing constraints derived from the above: never merge without explicit authorisation; never weaken default-on authentication to avoid compatibility problems; never close DEBT-025; keep follow-ups out of PR #94 (now merged) and in their own PRs.

## 4. Goal, Scope & Success Criteria

### Goal
Finish the DEBT-025 follow-ups the owner approved or mandated, without closing DEBT-025 prematurely and without merging.

### In Scope
(A) finish verifying and then readying **PR #112** (durable authentication audit records); (B) implement **ADR-KERNEL-09** (control-plane authorization) once the owner decides O1-O5; (C) CSP hardening (remove inline script/handlers, strict CSP); (D) a Windows second-account read test; (E) fix the flaky updater test as its own PR; (F) keep the register and report truthful as each lands.

### Out of Scope
Merging anything; changing A1; the CTX-AUTH-002 disposition (the owner closed it "qualified" via #106); other sessions' PRs and branches; per-user accounts; an approval (HITL) channel for ESCALATE.

### Success Criteria
DEBT-025 can close only when: control-plane authorization is implemented and verified (ADR-KERNEL-09 §1 R1-R6); durable auth events are implemented and verified; and the owner says so. Nothing here closes it.

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R-01 | Land CTX-AUTH-002 as a focused PR with exact-head tests | starting prompt | **VERIFIED, merged** (#93) | PR #93 merged by 1h0lde4; gates run at its reconciled head | closure "qualified" by the owner in #106; not mine to change |
| R-02 | Resolve the DEBT-029 / PR #89 identifier collision | starting prompt | **VERIFIED, merged** | main's DEBT-029 row restored; the work re-registered as DEBT-044; #89 merged; owner later resolved DEBT-029/044 via #95/#96 | |
| R-03 | A1: default-on bearer authentication, pinned public allowlist, `/health` protected, auditable opt-out | owner Oct 28 | **VERIFIED, merged** (#94 at `ce5c3f8`) | exact-head results in section 13 (head `c50caa9`) | post-merge `main` was not re-verified by me |
| R-04 | Two small corrections (headers on rejections; rotate-first directory) | owner Nov 2 | **VERIFIED, merged** inside #94 | 6 regression tests fail on `8552ca6`; 38/38 mutants killed | |
| R-05 | DEBT-025 stays OPEN | owner | **OPEN (by design)** | register row on main says so | |
| R-06 | **Durable auth events** (spec in section 3, item 5) | owner Nov 2 | **IMPLEMENTED; VERIFIED locally and in CI at `2e7d036`; NOT MERGED; owner review pending** | PR #112 (draft); CI 7/7; 215 targeted; 20/20 mutants; section 13 | multi-process and Windows/macOS untested; register row deferred (R-13) |
| R-07 | **Control-plane governance** | owner Nov 2 | **PROPOSED**: ADR-KERNEL-09 merged, status PROPOSED, **not accepted, not implemented** | ADR on main; O1-O5 undecided | blocks DEBT-025 closure |
| R-08 | CSP hardening (no inline script/handlers) | owner Nov 2 | **OPEN**, not started | | high priority; token is in `sessionStorage` |
| R-09 | Windows second-account read verification | owner Nov 2 | **OPEN**, not started | Windows job today lists ACL entries only | |
| R-10 | Document the same-user token read as an accepted trust boundary | owner Nov 2 | **PARTIAL**: report section 6 item 1 states it | | check it is explicit enough |
| R-11 | Flaky `tests/test_updater_error_disclosure.py` (random UUID containing `8080`) | owner Nov 2 | **OPEN**, separate issue | forced-UUID reproduction in section 11 | do not mix into DEBT-025 |
| R-12 | No merge, no weakening, no closing of DEBT-025 | owner | **STANDING** | | |
| R-13 | DEBT-025 register row and `CURRENT_STATE.md` say durable events are implemented | v1 step 5 | **DEFERRED until PR #112 merges** | | write it neutrally, after the owner's merge instruction; `KNOWN_ISSUES.md` conflicts easily and some repo files are CRLF |
| R-14 | The report records the durable audit records and their limits | v1 step 5 | **IMPLEMENTED in PR #112** (A15, section 6 items 12-15, section 7) | CI 7/7 on `2e7d036` | |
| R-15 | Flaky updater test fixed | handoff v2 item 6 | **IMPLEMENTED; VERIFIED (local + CI 7/7); PR #115 open, not merged** | fail-before deterministic; mutant killed | owner merges |
| R-16 | CSP `script-src 'self'` for the shipped pages | handoff v2 item 4 | **IMPLEMENTED; VERIFIED in headless Chromium/Linux and statically; PR #118 DRAFT, not merged; human click-through pending** | 29/29 browser checks, negative control 0/29, 252 targeted, drift 15/15 | `style-src 'unsafe-inline'` and other unescaped `innerHTML` values remain (report section 6 item 2) |

## 6. Current Verified State

**VERIFIED**
- The authentication boundary (PR #94) is on `main`, merged by the owner. Its pre-merge head `c50caa9`: full suite 2372 passed, 1 xfailed, 0 failed (baseline main 2184), drift 15/15, FastAPI-floor tests 188 passed, 24 security suites 488 passed, mutation review 38/38 killed, real browser (headless Chromium 153, **Linux**) 23/23, real Windows runner job passed, CI all green. (Section 13.)
- ADR-KERNEL-09 is on `main`, status **PROPOSED**. The register row for DEBT-025 on `main` says: authentication IMPLEMENTED, not closed; control-plane residual designed in ADR-KERNEL-09 (not accepted); durable audit residual open.

**VERIFIED (added in v2)**
- PR #112 at `2e7d036` (draft): CI 7/7 success; 215 targeted tests (latest dependencies and the FastAPI 0.111 floor); drift 15/15; full-suite failure set identical to `main`'s; 20/20 valid mutants killed after three tests were added. Evidence: section 13. Not merged; the owner has not reviewed it.

**IMPLEMENTED BUT NOT VERIFIED**
- Multi-process behaviour of the audit queue; a real EventStream under concurrent writers; duplicate records after a timed-out append (designed at-least-once, documented, untested); Windows/macOS.

**PROPOSED:** ADR-KERNEL-09 design and decisions O1-O5.
**DEFERRED:** CSP hardening, Windows second-account test, flaky-test fix.
**BLOCKED:** ADR-KERNEL-09 implementation on the owner's O1-O5 decisions (and, for the principal, it builds on the merged auth boundary).
**UNKNOWN:** the CI-run full-suite counts on `main` (only the local differential at `ef1351f` was run by me: 16 environmental failures, identical to the PR's).

Active architectural constraints: LAW 1 governance before capability; fail closed everywhere; audit failure never fails open; default-on authentication.

## 7. Git / Repository Checkpoint

All figures verified by `git ls-remote` / the GitHub API during this session. **`main` moves constantly (other sessions and the owner merge); re-verify.**

| Item | Value |
|---|---|
| Primary repository / remote | `github.com/1h0lde4/ocbrain-v4.1` / `origin` |
| `main` when this was written | `ef1351f` (earlier in the session: `2491ae4`, `abd6c4b`, `6f93444`, `2ebf76a`, `f9e49dd`). Nov 24: `ef1351f`. Nov 25: `0ef31d7` after the owner merged #116 and #117 (unrelated files). |
| PR #94 (auth boundary) | **merged** by `1h0lde4` at 2026-11-17T22:51Z, merge commit `ce5c3f8`; my last head `c50caa9`; branch head `594060f` (another session merged main into it) |
| PR #110 (ADR-KERNEL-09) | **merged**; PR head `48bb472` after another session corrected two evidence rows (section 11) |
| PR #93 (CTX-AUTH-002) | **merged** |
| PR #112 (audit records) | **draft, open**, head `2e7d036`; `main` `ef1351f` merged in; description rewritten Nov 24; not marked ready; CI 7/7 |
| PR #115 (flaky updater test) | open, not draft, head `823d9e2`, base `ef1351f`; CI 7/7 |
| PR #118 (CSP `script-src 'self'`) | **draft**, open, head `72e74c1`, base `ef1351f` (two commits: `36de1f4` code and tests, `72e74c1` report); CI: 6/7 checks completed, all success; `tests` still in progress |
| Implementation checkpoint (transfer commit) | `2e7d036` on `feat/debt-025-auth-audit-eventstream-nov2026`: `ed8890c` + `4ef2101` (tests) + `4294390` (merge of `main` `ef1351f`) + `2e7d036` (report). Diff against `main`: 7 files, +704/-13. Pushed fast-forward; remote tip verified by an unauthenticated `git ls-remote`. |
| Handoff branch / commit | `handoff/debt-025-followups-nov2026`: v1 commit `b10c316` (parent `main` `ef1351f`), then the v2 commit on top. The tip of the branch is the handoff commit (a file cannot contain its own hash; read it with `git rev-parse origin/handoff/debt-025-followups-nov2026`). |
| Working tree | the sandbox is **ephemeral and was reset twice**; nothing material exists only there. Worktrees `/home/claude/{audit,handoff}` are disposable. |
| Remote push status / verification | all branches above pushed; verified with `git ls-remote` after each push |
| Relevant ignored/untracked | none |

## 8. Active Files / Modified Files / Artifacts

On `main` from PR #94 (do not re-derive): `interface/auth.py` (middleware, token, Host allowlist, rotation, throttle, Windows ACL, frozen path), `interface/headers.py`, `interface/token_cli.py`, `interface/api.py`, `interface/cli.py`, `interface/tray.py`, `interface/web/auth.js`, `main.py` (early `token` hook), `core/event_bus.py` (`api.auth_*` events), `scripts/check_token_acl_windows.py`, `.github/workflows/ci.yml` (job `token-acl-windows`), `tests/test_api_auth_boundary.py`, `tests/test_web_auth_js.py`, `tests/js/auth_js_live.js`, `tests/conftest.py` (autouse opt-out fixture), `docs/reports/api-exposure-and-auth-boundary-oct2026.md`, the DEBT-025 register row, install banners.
On `main` from PR #110: `docs/architecture/decisions/ADR_KERNEL_09_CONTROL_PLANE_AUTHORIZATION.md` + its `ADR_INDEX.md` row.

**PR #112 (the transfer commit), why each file matters:**
- `interface/auth_audit.py` (new): the sink protocol, `EventStreamSink` (lazy `core.events.event_stream.get_event_stream().append(..., source="ApiAuth")`), constants (`AUDIT_TIMEOUT_S=2.0`, `AUDIT_RETRY_BACKOFF_S=5.0`, `MAX_PENDING_AGGREGATES=100`).
- `interface/auth.py`: transitions queued; `get_settings()` now returns the **effective** mode (required while an `api.auth_disabled` record is pending); `flush_audit()` (single-flight, time-boxed, backed off, never raises except cancellation); `schedule_flush()`; per-window counters and `_close_window()` / timer; `_admit_denial(reason)` now counts every denial; middleware blocks only on a pending disable and flushes everything else in the background.
- `interface/api.py`: `setup()` calls `api_auth.schedule_flush()`.
- `tests/conftest.py`: the autouse fixture installs an always-succeeding null sink so the existing API tests still see the opt-out immediately.
- `tests/test_api_auth_boundary.py`: one test updated (the opt-out now takes effect only after `flush_audit()`).
- `tests/test_api_auth_audit.py` (new, 24 tests).

Nothing required for continuation exists outside the pushed repository.

## 9. Changes Made

- **PR #94 (merged):** default-on bearer-token boundary (pure-ASGI, outermost, deny-by-default); public allowlist = `GET`/`HEAD` of `/` and `/static/*`; per-installation token (env or file, 0600, `O_EXCL`, constant-time compare); Host allowlist; docs UIs disabled and `/openapi.json` protected; audited, rate-bounded denials; every opt-out transition logged/emitted; frozen-build per-user token location; token file re-checked per request (revocation/rotation without restart); Windows owner-only ACL (`/reset`, `/inheritance:r`, `/grant:r`, verified as SDDL); security headers on every response including rejections; tray no longer puts the token on the browser's command line; `ocbrain token [--show|--rotate]` in the pip CLI and in `main.py`; CLI group fix (known subcommands win over free-text query); wrong-token prompt nag fixed; install banners. Behaviour changes: `/docs` and `/redoc` are gone, other `Host` values are 400, `/health` needs the token.
- **PR #110 (merged):** ADR-KERNEL-09 PROPOSED (design only).
- **PR #112 (draft):** section 8.
- Earlier in the session (all merged): the CTX-AUTH-002 reconciliation PR (#93) and the DEBT-029/DEBT-044 identifier fix (#89).

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| D-01 | A1: default-on bearer auth; loopback is not a boundary | **ACCEPTED** | owner Oct 28 | `interface.api:app` can be served on any address; CSRF header is a constant | owner only |
| D-02 | Docs UIs disabled rather than self-hosted | ACCEPTED | owner Nov 2 | `/docs` loaded CDN scripts into the UI's origin | self-hosted docs |
| D-03 | Tray never puts the token on a command line; page prompts once per tab | ACCEPTED | owner Nov 2 | reproduced: an unprivileged uid read the token from `/proc/<pid>/cmdline` | a safe transfer mechanism |
| D-04 | One-time bootstrap code for the tray was **rejected** | rejected | me, accepted | a local attacker could win the redemption race and get the full token | none |
| D-05 | Host allowlist in required mode | ACCEPTED | owner Nov 2 | `Host: evil.example` got 200 for the shell | proxied deployment needs `OCBRAIN_API_ALLOWED_HOSTS` |
| D-06 | Windows invariant = "no principal other than the user, SYSTEM, Administrators, OWNER RIGHTS"; recipe `/reset`, `/inheritance:r`, `/grant:r` | ACCEPTED (qualified) | owner Nov 2 | **a real Windows run disproved "exactly one entry"** and showed `/grant:r` leaves other explicit entries | second-account test |
| D-07 | `ocbrain token` in both the pip CLI and `main.py` | ACCEPTED | owner Nov 2 | in a packaged install the binary named `ocbrain` *is the server* | |
| D-08 | Minimal click group fix | ACCEPTED | owner Nov 2 | under click 8.5 `ocbrain status` posted "status" to `/query` | |
| D-09 | Durable events: transitions persisted; **a pending disable record keeps the effective mode `required`**; aggregates for denials; failures never fail open | **APPROVED (spec)**, implemented in #112 | owner Nov 2 | section 3 item 5 | owner review of #112 |
| D-10 | Control-plane governance design: default-deny `control.*` governor, principal from the auth middleware, one authorization service, durable decision before approval | **PROPOSED** | ADR-KERNEL-09 | section 11 | O1-O5 |
| D-11 | Follow-ups stay out of #94 | STANDING | owner | | |
| D-12 | I pushed only to branches in scope, never merged | STANDING | owner | | explicit merge authorisation |

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| API exposure | launch path, importability, middleware, route table, CORS | one launcher binds `127.0.0.1`; the app is servable anywhere; CSRF header is not auth; 31 (method, path) pairs: 30 protected, 1 public | report E1-E12 | new route or launcher |
| `GovernanceKernel` | `core/governance/governance_kernel.py` | sync `evaluate_action`; a governor that raises is rejected; **base `Governor.evaluate` and the kernel default to APPROVE, so an unrecognised action type is approved**; `GovernanceAction` has no actor/resource field | ADR-KERNEL-09 F1-F3 | kernel change |
| **Callers of `evaluate_action`** | grep | **I got this wrong in the ADR.** I wrote "only the orchestrator"; production call sites are `core/orchestrator.py:241`, `core/cognitive/learning.py:668`, `core/cognitive/compiler.py:388`, `core/workers/base.py:246` and three in `core/memory/unified_memory.py`. `interface/` still never calls it. Another session corrected the ADR (F5). Also F4: the kernel does not persist decisions (no `EventStream` use in `core/governance/`). | re-run `grep -rn evaluate_action --include=*.py core interface main.py` | |
| `EventStream` | `core/events/event_stream.py` | `append(event_type, *, source, payload)` async, SQLite WAL, **DB errors propagate**, subscriber errors swallowed; default path `.data/events/stream.db` is **relative to the working directory** | read; round-trip test | |
| Frozen builds | PyInstaller `--onefile` stub (Linux) | `__file__` lives in a per-run `_MEI…` dir, so the token changed every start and a separate process could not read it | built and run twice | Windows/macOS not run |
| Windows ACL | CI job on `windows-latest` (built-in Administrator, English names) | a new file already has explicit SYSTEM/Administrators/OWNER RIGHTS; `/inheritance:r` removes nothing; the combined recipe leaves 3-4 entries; after `/reset`+`/inheritance:r`+`/grant:r` SDDL shows only the user (`LA`) | check-run annotations | standard user, domain account, other language |
| CI | `.github/workflows/ci.yml` | installs only `requirements.txt`; **never provisions Node**; the gate ignores skips; the Node live test now fails under `CI=true` if Node is missing | | |
| Risks disproved/limited | many probes | docs-UI CDN scripts, unvalidated Host, tray argv leak, root-path regression, rotation needing restart, flood logging, wrong-token nag | PR #94 description | |
| **Not yet investigated** | | multi-worker behaviour of the audit pending queue; what `upgrade_planner.propose_upgrades` and `_scheduler.trigger_module` persist (ADR marks them UNKNOWN) | | |

## 12. Failed Attempts / Dead Ends

- **One-time bootstrap code in the launcher URL**: rejected, the redemption race hands a local attacker the full token. Do not retry.
- **"A new Windows token file ends with exactly one ACL entry"** (written from Linux): disproved by the real runner. Do not reassert it.
- **`/grant:r` alone as a repair**: leaves explicit entries for other principals.
- **My own incorrect claims, now corrected in the repo:** "docs trio is schema only" (it loaded CDN scripts); "a rebinding page cannot know the token" (the unvalidated Host let the shell and its prompt load under an attacker origin); "the fragment token is never sent" (true for HTTP, but the full URL was a process argument); "the orchestrator is the only caller of the kernel" (section 11).
- **Test-harness mistakes, not product defects:** a fake ASGI `receive()` that replayed `http.request` (failed at FastAPI 0.111); disconnecting early cancelled response bodies; the bundled Chromium ships `--single-process` and `--disable-web-security`, which invalidate multi-context and CORS tests (filter them out); a process scanner that excluded "pytest" also hid the pytest tmp dir.
- **Sandbox hazards (see section 14):** two resets; one destroyed uncommitted work.

- **Mutant design error (v2):** raising the default of `MAX_PENDING_AGGREGATES` survived only because the test overrides that constant; a mutant must change code the test cannot override. Replaced by three mutants of the bound logic.
- **A mutation runner that reported the first line starting with `ERROR`** mislabelled three kills (it picked captured log lines); only `FAILED ` lines identify the test.
- **"Fail-before" by copying the new test file onto `main`** only proves the module is absent. Use mutants.
- **Wizard 401 taken for a new defect** (v3): the auth layer answers 401 to any unknown path before routing; the wizard routes do not exist (E7). Check the report's E-list before calling something new.
- **Harness mistakes, not product defects (v3):** a click on `#thinking-control` fails while it is `display:none` (it appears only while a query runs, on `main` too); a click on `.add-module-btn` races the grid re-render (use a retry); toggles in `settings.js` number 7, not 3 (derive counts from the page). `cut -c` split a multi-byte emoji and made the tool output invalid UTF-8: slice in Python. `/bin/sh` has no process substitution: use `bash -c`.

## 13. Verification Evidence

All `CI=true`, Python 3.12.3, `chromadb==0.5.3`, Linux unless stated.

| Head | Check / command | Result |
|---|---|---|
| `c50caa9` (PR #94) | `python3 -m pytest tests -q -p no:cacheprovider --timeout=90 -rfEs` | 2372 passed, 1 xfailed, 0 failed (baseline main `2491ae4`: 2184) |
| | `python3 scripts/check_drift.py` | no FAIL (15 checks) |
| | boundary + Node tests in a venv with `fastapi==0.111.0 starlette==0.37.2 "httpx<0.28"` | 188 passed |
| | 24 security suites (`security|disclosure|auth|export|distill|import|sandbox|traversal|containment`) | 488 passed |
| | mutation review of the boundary (38 mutants) | 38/38 killed |
| | real browser: headless Chromium 153, **Linux**, harness outside the repo | 23/23 |
| | live uvicorn probes, `main.py token`, frozen binary rotate-first | as expected (PR #94 description) |
| | CI | `tests`, `drift-and-ownership`, CodeQL, both Analyze, `token-acl-windows`: success |
| PR #110 branch | full suite, drift | 2184 passed (identical to main); docs only, says nothing about design correctness |
| `ed8890c` (PR #112) | `pytest tests/test_api_auth_boundary.py tests/test_web_auth_js.py tests/test_api_auth_audit.py` | **212 passed** (184 + 4 + 24), per module and together |
| `ed8890c` (PR #112) | CI check runs (GitHub API) | 7/7 completed success: `tests`, `drift-and-ownership`, CodeQL, 3 x Analyze, `token-acl-windows` |
| `2e7d036` (PR #112, v2) | CI check runs | **7/7 completed success** (`tests` finished 10:19Z, 5 min after the push) |
| | the same three modules, current dependencies (FastAPI 0.165.0, Starlette 1.10.0, httpx 0.28.1, click 8.5.1) | **215 passed** (184 + 4 + 27) |
| | the same, at the floor (`fastapi==0.111.0`, `starlette==0.37.2`, `httpx==0.27.2`) | **215 passed** |
| | those plus `tests/test_check_drift.py`; `python3 scripts/check_drift.py` | 249 passed; 15/15 PASS |
| `ed8890c` + 3 tests vs `main` `ef1351f` | full suite, `CI=true`, `--timeout=90`, with `--ignore` of the 4 files that import `chromadb` (`test_break_concurrency`, `test_break_empty_db`, `test_break_security`, `test_system_ctrl`) | PR **16 failed / 2377 passed / 4 skipped / 1 xfailed**; `main` **16 / 2350 / 4 / 1**; failure sets **identical** (8 need `chromadb`; 8 sandbox namespace and seccomp tests this container cannot run). +27 passes = the 24 + 3 new tests. The merged head was **not** re-run in full locally. |
| | mutation review (20 valid mutants; harness outside the repo, gone) | first run 17 killed / 3 survived (request-path background flush, single-flight, loss reported once); 3 tests added; **final 20/20 killed** (two by hang or timeout: per-append timeout removed, single-flight removed) |
| | fail-before: new test file copied onto `main` | collection `ImportError` (module absent): shows absence, not behaviour; the mutation review is the behavioural evidence |
| | trial merge of `main` into the PR branch | clean, no conflicts |
| `72e74c1` (PR #118) | real browser, headless Chromium 158 Linux, harness outside the repo (gone), pages/static/headers from the real server, API responses mocked | **29/29**; negative control (`main` pages under the strict policy) **0/29** with `script-src-attr` and `script-src-elem` violations |
| | `tests/test_web_csp.py` (new) on this branch; on `main`'s pages and policy | 30 passed; fail-before 15 of 30 fail |
| | CSP + boundary + Node live + drift module, current dependencies; at the FastAPI floor | **252 passed**; **252 passed**; drift 15/15 |
| | full suite, `ed8890c`-style differential: this branch vs `main` `ef1351f`, same environment, 4 chromadb files ignored | **16 failed / 2380 passed / 4 skipped / 1 xfailed** vs **16 / 2350 / 4 / 1**; failure sets identical |
| | guard mutation: bare `fetch()` put into `index.js` | caught by `test_web_pages_use_the_authenticating_helpers[index.html]` |
| `823d9e2` (PR #115) | fail-before with a forced ref containing `8080`; fixed file; with `tests/test_check_drift.py`; drift | assertion fails before; 4 passed after; 38 passed; 15/15 |

**Labels:** the Node live-server test is **not** browser evidence; the browser run is Linux/Chromium only and not part of CI; the Windows evidence is one runner as the built-in Administrator with English names and lists ACL entries only (**no second-account read was attempted**); POSIX checks say nothing about NTFS. **Not performed:** a real desktop launcher, macOS, a frozen build on Windows/macOS, a truly separate host, the second-account Windows test, anything for PR #112 beyond the 212 tests.

## 14. Environment / Tooling Assumptions

- Python 3.12; Node v22 (needed by `tests/test_web_auth_js.py`; under `CI=true` a missing Node **fails** the test).
- The full suite needs `chromadb==0.5.3` (the repo's deliberate pin, DEBT-032) plus the packages in `requirements.txt`. In a fresh sandbox `interface.api` imports with only `pytest pytest-asyncio pytest-timeout httpx pyyaml tomli tomli-w click rich requests aiofiles pydantic fastapi uvicorn[standard] datasketch`, but the full suite needs the rest.
- **The sandbox is unreliable:** background processes die when it restarts; pip downloads were ~250 kB/s with no cache after a reset, so install in short foreground steps under `timeout`; the network allowlist includes `pypi.org`, `github.com`, `api.github.com`, `registry.npmjs.org`. **Commit and push early; a reset destroyed uncommitted work once.**
- Traps: `pkill -f <pattern>` kills your own shell if the pattern is in the command line; `ss` is not installed; test `\r` with Python, not `$'\r'` in `sh`; some repo files are CRLF (`main.py`, `core/event_bus.py`, `tests/conftest.py`, `KNOWN_ISSUES.md`) so edit them preserving line endings.
- Pushing: use `git -c http.extraheader="Authorization: Basic <base64 x-access-token:TOKEN>"` so the token is not stored in the URL or git config.
- The browser/live/mutation harness scripts lived in `/tmp` and `/home/claude/e2e` and are **gone**. To rebuild: `npm i @sparticuz/chromium puppeteer-core` (67 MB Chromium inside the package), launch with `args` filtered of `--single-process`, `--no-zygote`, `--disable-web-security`, `--allow-running-insecure-content`, `--disable-site-isolation-trials`; start the server with `setsid nohup` and match processes by script file name.

- **Nov 24 session environment (ephemeral, gone with the sandbox):** `/home/claude/venv` (current dependencies) and `venv-floor` (the pins above); extra installs `feedparser trafilatura aiohttp beautifulsoup4`; `chromadb` and `sentence-transformers` not installed. Rebuild by the command lists in this section. Worktrees for the mutation run, `main` and this branch were disposable.
- **Tool traps seen on Nov 24:** a `sleep` of 90 s or more inside one tool call was stopped by the tool layer twice with "the credential it was run with is no longer valid" (no GitHub credential was involved); poll with sleeps of 60 s or less. A background `pytest` started with a plain `&` died silently at about 42 percent; `setsid nohup` runs finished. The unauthenticated GitHub API is exhausted for the shared egress address; the saved token (valid for `1h0lde4`, push access, checked read-only first) was used for checks and for one fast-forward push, per the standing owner instruction.
- Running the suite dirties tracked files (section 15): `git checkout -- config data` before committing.
- **Browser harness (v3, rebuilt, gone with the sandbox):** `npm i @sparticuz/chromium puppeteer-core` (the module's export is under `.default`); a launcher that starts `interface.api:app` with `OCBRAIN_API_TOKEN` and `OCBRAIN_API_TOKEN_FILE` set and the working directory outside the repo, with an optional mode that forces the strict policy for a negative control; `puppeteer` request interception serving the real pages and static files and mocking only `/status`, `/modules`, `/config`, `/query`, `/train/*`, `/modules/new` and `/api/wizard/*`; a `securitypolicyviolation` listener installed with `evaluateOnNewDocument`; the token adopted from the `#token=` fragment. Stop servers by PID (`ps -eo pid,comm,args | awk ...`), never `pkill -f`.

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Options | Disposition | May work continue? |
|---|---|---|---|---|
| **O1** opt-out principal for control-plane auth | ADR-KERNEL-09 §9 | (a) same as owner, (b) deny T3 | recommended: (b) for T3, (a) for T1/T2; **undecided** | design yes, implementation no |
| **O2** reads and `execute.query` | ADR §9 | authn-only vs governed | recommended authn-only + coverage test | as above |
| **O3** T3 initial verdict | ADR §9 | allow with audit vs ESCALATE | recommended allow with audit (no approval channel) | as above |
| **O4** `actor`/`resource` as fields or metadata | ADR §9 | fields (recommended) | undecided | as above |
| **O5** drift rule forbidding `interface/` from calling the kernel | ADR §9 | add | undecided | as above |
| PR #112 `get_settings()` semantics (effective vs resolved mode) | section 8 | review callers | needs owner/reviewer eyes | yes |
| Multi-worker audit behaviour | not tested | each worker keeps its own queue; probably fine | verify | yes |
| EventStream default path is cwd-relative | read | anchor it | separate defect | yes |
| Token plaintext in saved preferences | owner informed | rotate, secret store | owner's call | yes |
| Concurrency | other sessions push to branches and merge | always re-fetch; never overwrite | standing | yes |
| Running the test suite rewrites tracked `config/models.toml`, `config/settings.toml`, `config/sources.toml` and `data/context.sqlite` (also on pristine `main`; it drops comments such as the `import_root` note) | seen in several worktrees after suite and drift runs; `git checkout -- config data` before committing | fix the config writer or point tests at a temporary directory | separate issue, not DEBT-025; not changed | yes |
| PR #118 changes UI behaviour that only a headless browser has exercised | section 13 | the owner clicks through the pages in a real browser (and, if wanted, Firefox/Safari) before merging | open | yes: it is a draft |
| Duplicate audit records after a timed-out append (EventStream appends run in a thread, `core/events/event_stream.py` line 228) | read; report section 6 item 12 | accept at-least-once (documented), or dedupe on `transition_id` | owner's call | yes |
| `chromadb` / `sentence-transformers` not installed in this sandbox | 4 files ignored, 8 tests fail on import | install in a longer session | CI covers them | yes |

## 16. Relevant Information / References

- PRs: #94 (merged), #110 (merged), #93 (merged), #89 (merged), #112 (draft), #108 (owner's register reconciliation, merged).
- ADR: `docs/architecture/decisions/ADR_KERNEL_09_CONTROL_PLANE_AUTHORIZATION.md` (its §6 is the test plan T1-T12; its §3 is the inventory of the 11 control-plane operations with handler lines at the time).
- Report: `docs/reports/api-exposure-and-auth-boundary-oct2026.md` (decisions A1-A14, residuals).
- Ownership register: `docs/engineering/DEBT_BRANCH_OWNERSHIP_REGISTER_2026-11-02.md` (implementation owner for DEBT-025 follow-ups was UNASSIGNED).
- Project memory file `debt-025-api-auth` holds the owner's decisions verbatim.
- Commands: `ocbrain token --show|--rotate`, `scripts/check_drift.py`, `scripts/check_token_acl_windows.py` (Windows only, run by the CI job).

## 17. Next Steps

v1 steps 1-6 were carried out in v2 (section 0): CI read, PR #112 verified (fail-before replaced by a 20-mutant review, three tests added), the report updated, the PR description rewritten, nothing merged. What remains, in order:

1. **Verify state first** (section 18). Expected: PR #112 head `2e7d036` and still a draft; if the owner has reviewed or merged it, adapt (item 2).
2. **Owner review of PR #112** (the owner's step; do not merge). The one item that needs eyes: `get_settings()` now returns the *effective* mode (required while a disable record is pending). If the owner merges it on an explicit instruction: open a small **docs PR** that updates the DEBT-025 register row (an append-only addendum after the "Superseded Nov 17" bracket; the phrase "the durable audit residual remains open" is superseded, not deleted) and `CURRENT_STATE.md` (R-13). Neutral wording, written after the merge. Mind CRLF files.
3. **ADR-KERNEL-09 implementation** only after the owner decides O1-O5: its own PR(s), following its section 6 T1-T12. Use the corrected caller list (section 11) for the drift rule.
4. **CSP hardening: DONE as PR #118 (draft).** Remaining: CI result, a human click-through, the owner's review. Later, separate jobs if wanted: remove the `style=` attributes and tighten `style-src`; escape the remaining `innerHTML` values listed in the report (section 6 item 2); `encodeURIComponent` in `trainModule`.
5. **Windows second-account test** (own PR, no decision needed): extend `scripts/check_token_acl_windows.py` and the `token-acl-windows` job to create a local user, attempt to read the token file as that user and assert denial; label what it does and does not prove.
6. **Flaky updater test: DONE as PR #115 (open, CI 7/7).** Waiting for the owner to merge.
7. **Optional, separate issues:** anchor the EventStream default path; stop the suite rewriting tracked `config/*.toml` and `data/context.sqlite` (section 15).

Items 5 and 7 can start without the owner; 3 is blocked on O1-O5; 2 (review of #112, #115, #118) is the owner's.

## 18. Resume Instructions

First, in order:
1. Read `PROJECT_INSTRUCTIONS.md` (Project knowledge).
2. `git fetch origin`; verify `main`, PR #112's head (`2e7d036` expected unless someone pushed), and this branch's tip. **Resolve any mismatch before changing code.**
3. Verify the handoff against the live repository (a state snapshot goes stale in hours here): are #94/#110 still merged, is `interface/auth_audit.py` still absent from `main`, has anyone changed the DEBT-025 row?
4. Confirm the test environment (section 14) before trusting any green or red.
5. Begin at step 2 of section 17. Do not redo completed work unless verification contradicts this file. If the repository contradicts it, correct this file; do not choose whichever source is convenient.

## 19. Transfer Status

**TRANSFER READY**: all material work is in Git and pushed (PR #112 branch `2e7d036`, PR #115 branch `823d9e2`, PR #118 branch `72e74c1`, and this handoff branch with v3 on top of v2; all verified with an unauthenticated `git ls-remote`), nothing material exists only in the sandbox, and the next action is defined. This does **not** mean the work is complete: #112 and #118 are drafts, #115 is open, none is merged, #118 has had no human click-through, ADR-KERNEL-09 is unimplemented and unaccepted, and DEBT-025 remains OPEN.
