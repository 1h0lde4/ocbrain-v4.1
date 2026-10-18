# Session Handoff (v3)

> Transfer record per `PROJECT_INSTRUCTIONS.md` §18.4.8. **Replaces v1 and v2** — their statements that R6 is unfixed, that R7 is not started, and about open alerts are **superseded**. **A temporary record, not an authority** (§18.4.9): verify against the live repo first. **Do not merge this file to `main`** — `git rm handoff.md` before any PR.

## 1. Handoff Metadata

- Handoff version: 3.2 — Oct 16 decisions recorded; freeze-manifest DRAFT v0.1 written (criteria proposed, verdict NOT rendered); PR #25 closed; PR #79 synced. (v3.1 corrected two earlier wrong framings: chromadb was already decided; PR #25 was stale)
- Created at: 2026-10-15 00:28 UTC
- Workstream: CodeQL-findings triage and its follow-ups — **the engineering work is done**; what remains is decisions, merges, and the freeze-manifest
- Source session purpose: continue after another session's report (§3) — fix R6, sweep R7, reconcile that report against live data
- Transfer status: §19

## 2–3. Original Starting Prompt / Subsequent Instructions


Verbatim, typos preserved:

```
first, Merge Packet G's branch first, then we'll start by checking few bugs revealed by github's codeQL:
1-  Incomplete URL substring sanitization found in tests/test_parser.py:18 and tests/test_module_factory.py :120  and tests/test_context.py :64.
2- Uncontrolled data used in path expression found in many places (to be found later) such as learning/trainer.py :61  and learning/scheduler.py :162 and core/module_factory.py :49
3- Information exposure through an exception found in core/brain_api.py :113  and  interface/api.py :529  and interface/api.py :160
only once these are finished do we start the freeze-manifest
```


**Further instructions since v2:**
- "Continue" / "Continuer" (repeatedly).
- **Moncif pasted a report written by another session** (it picked up the v2 handoff, but was blocked: HTTP 403 creating a branch, no DNS from its container — it pushed nothing) **with no instruction text.** *Interpretation (mine, not stated by him):* carry out the step that report recommends — a test-first R6 branch from fresh `main` — and verify its claims instead of trusting them. If that reading was wrong, say so.
- Standing instructions (unchanged): the freeze decision rests on current executable reality + reproducible verification; the freeze-manifest only after the CodeQL work; `main` changes only on his explicit instruction (he authorised the Packet G merge; nothing since); `enforce_admins: false` was his choice; own mistakes reported plainly; genuine policy forks put to him.

## 4. Goal, Scope & Success Criteria

**Goal now:** land or decide the finished work, get Moncif's decisions on the open policy items, then (with his go-ahead) the freeze-manifest.
**In scope:** PR #79; the Dependabot / alert-count questions; an optional docs PR for the audit trail; the freeze-manifest *if he says go*.
**Out of scope without him:** merging to `main`; the chromadb/Dependabot decision; changing the `DEBT-032` pin.
**Success:** each item in §17 either done or explicitly deferred by Moncif.

## 5. Requirement Ledger

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| R1 | Merge Packet G | **DONE** | PR #26 → `b1e4184`, 5/5 checks green |
| R2 | Category 1 | **DONE** | Alerts #30–#32 dismissed ("used in tests") by Moncif; my analysis agrees |
| R3 | Category 2 — 3 named sites | **DONE** | Traced guarded; since `fixed` |
| R4 | Category 2 — "many places" | **DONE upstream** | 30 `py/path-injection` alerts `fixed` (`acc43b7` `module_child()` + `6dee2b2`); verified by execution (76/76 containment tests) |
| R5 | Category 3 | **DONE upstream** | 3 `py/stack-trace-exposure` alerts `fixed` |
| R6 | `PrivacyGuard.wipe_module_data` deletion sink | **FIXED — PR #79 open, awaiting Moncif** | §6, §7 |
| R7 | Sweep for other destructive sinks | **DONE, with stated caveats** | `R7_DESTRUCTIVE_SINK_SWEEP_OCT2026.md` + `r7_destructive_sink_sweep.py` (this branch) |
| R8 | Freeze-manifest | **IN PROGRESS — `FREEZE_MANIFEST_DRAFT_488129b.md` (DRAFT v0.1); owner said proceed with a pinned SHA, explicit evidence, predeclared criteria, no verdict until reconciled** | Criteria §3 await owner ratification; §4 evidence inventory filled; §5 gate unanswered |
| R9 | Decisions only Moncif can make | **OPEN** | §15 |

## 6. Current Verified State

**VERIFIED (by running it / live API):**
- **R6 is real and fixed.** On unfixed code the new tests give **8 failed / 6 passed** — and I checked the failures are for the right reason (the decoy directory outside `data/` was actually *deleted*, for both a `../../decoy_dir` and an absolute-path payload; no invalid name raised). After the fix: **14 passed.** Full suite **2012 passed, 1 xfailed**; `test_module_name_containment.py` 76/76; `check_drift.py` 15/15.
- **PR #79 CI** (head `e54b2c6`): CodeQL: success, tests: success, drift-and-ownership: success, Analyze (python): success, Analyze (actions): success. Mergeability: `mergeable=None`, state `unknown` (GitHub computes this lazily; null/unknown means re-check). Based on `main` @ `1d813bd`; `main` has since moved.
- **R6 is *latent*, not live:** no production caller of `wipe_module_data`/`wipe_all`; the old test stubbed the method and called `shutil.rmtree` itself, so it tested the standard library.
- **R7 sweep:** 133 filesystem-mutating call sites in 197 production files → `CONST` 62, `GUARDED` 28, `STATE` 24, `PARAM` 19. Recall check: the known-bad `privacy.py` site is `PARAM` on old `main`, `GUARDED` on PR #79's branch. **No second unguarded, externally-reachable destructive sink found in what the heuristic can see.** Read and found sound: `modules/system_ctrl._safe_path` (`resolve()` + `relative_to(SAFE_ROOT)`). `PUT /config` mutable keys are `{ollama_host, debug, log_level, web_ui_port, auto_update}` — none path-valued. Latent output-path sinks with **zero callers**: `SqliteArchive.export_jsonl`, `ShadowCollector.export_training_dataset`.
- **CodeQL (live API): 37 alerts — 33 fixed, 4 dismissed.**
- **Dependabot security alerts (live): 7 open.** The other session's claims check out: all three `chromadb` advisories list **no patched version**, and `0.5.3` is inside every affected range; `sentence-transformers` is affected `< 5.6.0`. **Not new:** the repo's own record already states it — `DEBT-032`'s Oct 6 owner addendum says the vulnerable ranges run through `1.5.9` and no patched version exists. The owner's decision there: keep `0.5.3`, an *embedded-only* security boundary, explicit reopen trigger; #65/#70 (Oct 10) are recorded and `pyproject.toml` is pinned (PR #73). **This was settled before I raised it** — I wrongly presented it as open.

**Claims in the other session's report, checked:** R6 still on `main` ✓ · the old test stubs the method ✓ · Dependabot facts ✓ · "34 fixed + 4 dismissed" ✗ vs. the live API (33 + 4) — **but it matches the repo's own text** (`KNOWN_ISSUES.md` header, `CURRENT_STATE.md`), so this is a docs-vs-API mismatch of one alert that I could not resolve · its R7 table was preliminary (it said so) and is superseded by the AST sweep · "revoke the admin token" ✓ agree.

**INFERRED, not proven:** that CodeQL's silence on R6 is because it has no reachable taint source; that the sandbox-backend and `STATE` sinks are safe (classified, **not traced**).
**UNKNOWN:** the origin of `main`'s `1 xfailed`; whether `main`'s CI is green now; what PR #25 contains.

## 7. Git / Repository Checkpoint

- Repo `github.com/1h0lde4/ocbrain-v4.1` (**public**); remote `origin`. `origin/main` at handoff: `3f8ef97`; highest `DEBT-` id on `main`: **DEBT-041** (my R6 row takes `DEBT-042` on the PR branch — **re-check live; collisions with concurrent sessions have happened 3×**).

| Branch | Head | vs `main` | Contents | PR |
|---|---|---|---|---|
| `security/privacy-wipe-containment-oct2026` | `bcbe574` | **synced to `main` @ `488129b`, 0 behind** (merged cleanly; all register rows verified; full suite 2082 passed / 1 xfailed; drift 15/15) | **R6**: `core/privacy.py` (CRLF), `tests/test_privacy.py` (CRLF), `KNOWN_ISSUES.md` (+1 row `DEBT-042`) | **#79 open** — merge on Moncif's word |
| `security/codeql-findings-sep2026` | transfer commit `02c798a5086dce32cbb172845d7269e5b5efe1d2` (+ this file on top) | behind 47, ahead 8 | audit trail: working notes, R7 write-up + sweep script, +3 end-to-end export tests (`tests/test_brain_export_security.py`), Packet E correction | **none** |

PR #79's commits:
- `47b0b8e` test(privacy): real tests for wipe_module_data, incl. exploit-first containment (RED against current code)
- `ee1f6ed` fix(privacy): route wipe_module_data() through module_child() -- close an unguarded rmtree sink
- `e54b2c6` docs(register): DEBT-042 -- record the PrivacyGuard.wipe_module_data() sink fixed in this PR

Working tree clean at transfer; everything above is pushed and was verified local == remote.

## 8. Active Files

`core/privacy.py`, `tests/test_privacy.py` (**both CRLF — edit byte-aware**), `core/module_paths.py` (the helper), `KNOWN_ISSUES.md`; on the audit branch: `docs/Bugs Hunt & fix reports/{CODEQL_FINDINGS_SEP2026_WORKING_NOTES.md, R7_DESTRUCTIVE_SINK_SWEEP_OCT2026.md, r7_destructive_sink_sweep.py, PACKET_E_…_WORKING_NOTES_SEP2026.md}`.

## 9. Changes Made

R6 fix + tests + register row (PR #79); R7 sweep script + write-up; corrections to my own Packet E notes. No other production code changed.

## 10. Decisions & Rationale

| ID | Decision | Rationale |
|---|---|---|
| D1 | R6 on a **fresh branch from `main`**, not the stale audit branch | The other session's advice; keeps the PR minimal and reviewable |
| D2 | **Replace** the vacuous `test_wipe_module_data`, not add beside it | It tested `shutil.rmtree`, and passes against any implementation — false assurance |
| D3 | Exploit payloads must resolve inside `tmp_path` | A red run *executes* the exploit; a bare `"/etc"` would be `rmtree("/etc")` on unfixed code (`Path("a") / "/etc" == Path("/etc")`). Written into the test file's header |
| D4 | Relative import (`from .module_paths import …`) | Matches `privacy.py`'s existing `from .config import …` |
| D5 | `DEBT-042` severity "Low (latent) — **proposed**, not decided" | Severity is Moncif's call in this register (DEBT-038: "decided Sept 29") |
| D6 | Keep the 3 end-to-end export tests alongside `main`'s guard-level ones | They prove the *harm* can't occur, not just that a guard fires |
| D7 | Leave Dependabot PRs and the chromadb pin alone | His decision (§15 U1) |

## 11. Investigation Already Performed

R6 (reproduce → fix → gate); the R7 AST sweep and its triage (§6; every `PARAM` site read); `system_ctrl._safe_path`; `PUT /config` keys; callers of `export_jsonl` / `export_training_dataset` (zero); live CodeQL and Dependabot data; the other session's claims (§6). **Not inspected:** the sandbox-backend sinks beyond their origin tags; the 24 `STATE` sinks individually; the diffs of `acc43b7`/`6dee2b2`/PRs #34–#39; PR #25's contents; why Dependabot's alert count rose 4→7 (duplicate CVEs, likely a second manifest); the `1 xfailed`.

## 12. Failed Attempts / Dead Ends / Lessons

| What happened | Lesson |
|---|---|
| **An empty/zero result came from a broken command, twice.** (a) after a container reset, `grep -c` counted the empty output of failing `git` commands → "0 callers"; (b) the pattern `(def\|\.)_?export\(` cannot match `def _export(` (a space) | An empty result is evidence only once the command is shown *capable of matching*. Show exit statuses; test a pattern on a known hit |
| A drafted test would have run `rmtree("/etc")` on unfixed code | See D3 |
| My first sweep over-reported (counted `write_text` *content* as a path; matched `trafilatura.extract`) | Run a heuristic, read its output, refine, **re-run a recall check** |
| `privacy.py` is CRLF; a naive rewrite would have changed every line | `git ls-files --eol`; edit with `newline=""` |
| Duplicated a fix `main` already had (earlier) | `git fetch` and grep `origin/main` *before* building |
| Alert snapshots changed 3× in one session; handoffs went stale in hours | Re-fetch first; generate volatile facts from APIs |
| Misjudged "a few minutes ago" (really ~21 h) | Read the timestamps against the server clock |
| Packet E missed `learning/crawler.py:12` (grep omitted `learning/`); treated `trafilatura` as heavy ML | Search the whole tree, then narrow; check a package's footprint |
| Container reset **twice** (repo + Python env vanished) | Push after each logical step; §14's recipe works |
| `${var:0:7}`, `time`, `<(...)` fail | Tool shell is `/bin/sh` |
| A "clean" merge once dropped `DEBT-031…035` | After any merge, grep each `\| DEBT-NNN \|` header from both parents; reuse the gate (commit only if rows ✓ suite ✓ drift ✓) |

## 13. Verification Evidence

| Check | Result |
|---|---|
| R6 tests vs unfixed code | 8 failed / 6 passed; failures = decoys deleted / names not rejected |
| R6 tests after fix | 14 passed |
| Full suite on PR #79's branch (before the docs-only register commit) | 2012 passed, 1 xfailed, exit 0 |
| `test_module_name_containment.py` | 76 passed |
| `check_drift.py` | 15/15 PASS |
| PR #79 CI | CodeQL: success, tests: success, drift-and-ownership: success, Analyze (python): success, Analyze (actions): success |
| R7 sweep recall check | known-bad site `PARAM` on old `main` → `GUARDED` on the fix branch |

## 14. Environment / Tooling Assumptions


- OS: Ubuntu 24.04.4 LTS. Python 3.12.3, pytest 9.1.1, chromadb 0.5.3 (the `requirements.txt` pin, `DEBT-032`), fastapi 0.141.1, **trafilatura 2.3.0 (now required)**; **`torch`, `transformers`, `sentence-transformers` are NOT installed.** That is the sandbox class every baseline here was measured in.
- Containers reset — **this has now happened twice** (repo + Python env both vanished; only what was pushed survived). Rebuild:
  ```
  mkdir -p /home/claude/audit && cd /home/claude/audit && git clone https://github.com/1h0lde4/ocbrain-v4.1.git repo
  cd repo && git checkout security/codeql-findings-sep2026
  grep -vE "^sentence-transformers" requirements.txt > /tmp/req_minimal.txt   # keeps trafilatura
  pip install --no-cache-dir --break-system-packages -r /tmp/req_minimal.txt
  ```
  **Never plain `pip install -r requirements.txt`** (it pulls `sentence-transformers` → `torch`).
- Running the suite mutates tracked runtime state; revert before committing: `git checkout -- config/ data/context.sqlite`.
- Tool shell is `/bin/sh`. `sed` with `#` delimiter breaks on text containing `#`.
- **Credential:** a GitHub PAT with `repo` + admin on the repo is needed to push and for the API; supplied by Moncif per session; **never write it to any file or commit** (public repo). Push pattern: `git push "https://<TOKEN>@github.com/1h0lde4/ocbrain-v4.1.git" <branch> 2>&1 | sed "s#<TOKEN>#***#g"`.
  - **The token in Moncif's saved `userPreferences` is the old, revoked one** — a fresh session will see it and get HTTP 401. He must update it or paste a new one.
  - The replacement was pasted in plaintext into a chat and has admin scope on a public repo — **recommend he rotate/revoke it when the work is done.**
  - Works: repo read/write, PRs, branch protection, **code-scanning read, Dependabot-alert read**. **Untested:** code-scanning *write* (dismissals — Moncif did those in the UI).


## 15. Unresolved Questions / Risks / Blockers

| ID | Item | Needs |
|---|---|---|
| U1 | ~~Dependabot vs. `DEBT-032`~~ — **RESOLVED by the owner** (`DEBT-032` Oct 6 addendum; #65/#70; PR #73). Open Dependabot PRs #33/#32/… stay open *by design* until the compatibility study; closing them is his call, not a question | none |
| U2 | **Docs-vs-API CodeQL count** (docs: 34 fixed; API: 33). Which is right? | Moncif / a docs fix |
| U3 | **PR #25 is not an active competing effort — it is a stale (Sept 24) automated Jules PR that would delete 185 lines of `CURRENT_STATE.md`** and asserts all core kernel blockers are closed (contradicting the register). The real parallel work is the **FZ-01..07 series** (Oct 1 audit, baseline `ecddbff`); **the register lags merged code on FZ-02** (B2a #67, B2b #71 merged and their test docstrings cite **D1=(a), D2=(i) as decided**, while the register still says "OPEN — not started" / "none taken"; two outcomes are deliberately pinned `success=True`). See the scoping memo | Owner: close #25? |
| U4 | PR #79 vs. a moving `main` (mergeable state above) | Re-check |
| U5 | Sandbox-backend and `STATE` sinks classified, not traced; the sweep is heuristic with one validated recall sample | Optional follow-up |
| U6 | Latent output-path sinks (`export_jsonl`, `export_training_dataset`): confine to an export root if ever routed | When wired |
| U7 | Option: a drift check flagging new `rmtree`/`unlink` not via `module_child()` | Policy call |
| U8 | The token pasted in chat has **admin scope on a public repo — rotate it**; the saved `userPreferences` token is the old revoked one | Moncif |
| U9 | **Branch protection is stale in the docs:** live `enforce_admins` is **`true`** (PR #57 saw it Oct 5); my memory notes, `DEBT-033`'s register text, and v1–v3 of this handoff said admins are exempt | Update `DEBT-033`'s row; owner to confirm the intent |
| U10 | **The Oct 1 audit's original document is not recoverable** (searched every file ever added on any fetched ref and all issue/PR titles); reconstructed from the register + PRs #51/#53/#55/#57/#67/#71/#83 | Owner: does a copy exist? |
| U11 | Pending owner dispositions: **FZ-D3**, **`REM-004`** sufficiency, **`CTX-EXPORT-001`** classification, whether FZ-05/06/07 are blockers, the two pinned FZ-02 outcomes (**not accepted**), merges of PRs #83 and #79 | Owner |
| U12 | Register ↔ code gaps G1–G9 in the manifest §6 (FZ-02 lag; `CURRENT_STATE.md` Sept 23 verdict unreconciled; FZ-06 ≡ `DEBT-030` unlinked; …) | PR #83 fixes G1 |

**Dependabot (live):**

7 open.

| # | severity | package | CVE | affected range | first patched |
|---|---|---|---|---|---|
| #7 | critical | `chromadb` | CVE-2026-45833 | >= 0.4.17, <= 1.5.9 | None |
| #6 | high | `chromadb` | CVE-2026-45831 | >= 0.5.0, <= 1.5.9 | None |
| #5 | high | `chromadb` | CVE-2026-45830 | >= 0.4.17, <= 1.5.9 | None |
| #4 | critical | `sentence-transformers` | CVE-2026-68770 | < 5.6.0 | 5.6.0 |
| #3 | critical | `chromadb` | CVE-2026-45833 | >= 0.4.17, <= 1.5.9 | None |
| #2 | high | `chromadb` | CVE-2026-45831 | >= 0.5.0, <= 1.5.9 | None |
| #1 | high | `chromadb` | CVE-2026-45830 | >= 0.4.17, <= 1.5.9 | None |

**Open PRs (live):**

| PR | branch | title |
|---|---|---|
| #79 | `security/privacy-wipe-containment-oct2026` | fix(privacy): route wipe_module_data() through module_child() (latent rmtree sink) |
| #77 | `dependabot/github_actions/actions/upload-artif` | build(deps): bump actions/upload-artifact from 4.6.2 to 7.0.2 |
| #76 | `dependabot/github_actions/actions/download-art` | build(deps): bump actions/download-artifact from 4.3.0 to 8.0.2 |
| #33 | `dependabot/pip/chromadb-1.5.9` | build(deps): bump chromadb from 0.5.3 to 1.5.9 |
| #32 | `dependabot/pip/sentence-transformers-gte-3.0.0` | build(deps): update sentence-transformers requirement from <4.0,>=3.0.0 to >=3.0.0,<7.0 |
| #30 | `dependabot/github_actions/actions/checkout-7.0` | build(deps): bump actions/checkout from 4.4.0 to 7.0.1 |
| #29 | `dependabot/github_actions/actions/setup-python` | build(deps): bump actions/setup-python from 5.6.0 to 7.0.0 |
| #27 | `dependabot/github_actions/softprops/action-gh-` | build(deps): bump softprops/action-gh-release from 2.6.2 to 3.0.3 |
| #25 | `audit/kernel-v1-remaining-freezing-blockers-48` | Audit remaining freezing blockers for OCBrain Kernel v1.0 |

## 16. Relevant Information / References

`PROJECT_INSTRUCTIONS.md` §18.4.8/18.4.9/§23 · `KNOWN_ISSUES.md` (`DEBT-030…036` are this engagement's rows; `DEBT-038` is the `/distill` precedent for how a path-traversal fix is registered) · `core/module_paths.py` (docstring: `.isidentifier()` is not a filesystem boundary and CodeQL doesn't treat it as one) · `docs/Bugs Hunt & fix reports/` · CI: `tests` + `drift-and-ownership` required on `main`, strict, admins exempt. Context: Moncif (`1h0lde4`/"N4Z") decides; terse "Continue" = go ahead; **other Claude sessions land PRs on `main` constantly.**

## 17. Next Steps

1. **Verify the transfer** (§18); rebuild the environment if the container reset (§14).
2. **PR #79:** already synced with `main` @ `488129b` (0 behind, gates green; CI result recorded in the manifest §4). If `main` has moved again, re-sync and re-verify (per-row register check). **Merge only on Moncif's instruction.**
3. **Put U2, U8 and the PR #25 question to Moncif.** (U1 is already decided in the repo. Don't merge #33; closing Dependabot PRs is his call.)
4. *If he wants the audit trail on `main`:* on `security/codeql-findings-sep2026` do `git rm handoff.md`, merge `main`, open a docs+tests PR; wait for the 5 checks; merge only on his word.
5. **Freeze-manifest:** continue from `docs/Bugs Hunt & fix reports/FREEZE_MANIFEST_DRAFT_488129b.md` — its §10 lists the steps (ratify §3 criteria → re-run the FZ-01 repro → answer the §5 gate → reconcile §6 → owner dispositions for §8 → re-pin and re-run → only then the verdict).
6. *Optional:* trace the sandbox/`STATE` sinks (U5); the drift-check idea (U7).

## 18. Resume Instructions

1. `git fetch origin`; confirm both branches exist at the heads in §7 (the audit branch plus this file on top).
2. Compare this file's claims with the live repo/APIs — **the repo wins**; correct this file.
3. Begin at §17 step 2.

## 19. Transfer Status

**TRANSFER READY** — everything finished is pushed and verified (local == remote on both branches); what remains is decisions and merges that are Moncif's, plus the freeze-manifest on his go-ahead.
