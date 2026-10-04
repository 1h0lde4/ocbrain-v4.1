# Session Handoff

> Transfer record per `PROJECT_INSTRUCTIONS.md` §18.4.8. **This is a temporary transfer record, not an authority** (§18.4.9): verify it against the live repository before trusting it. **Do not merge this file to `main`** — promote anything durable into `KNOWN_ISSUES.md` / the working notes, then `git rm handoff.md` before opening a PR.

## 1. Handoff Metadata

- Handoff version: 1
- Created at: 2026-10-03 19:05 UTC (container clock; checked equal to GitHub's server time)
- Workstream: CodeQL findings triage (three alert categories) — the explicit gate before the Kernel v1.0 freeze-manifest
- Task identifier: CodeQL code-scanning alerts on `1h0lde4/ocbrain-v4.1` (37 total: 29 open, 4 dismissed, 4 fixed at handoff time; ids in §16). Working notes: `docs/Bugs Hunt & fix reports/CODEQL_FINDINGS_SEP2026_WORKING_NOTES.md`
- Source session purpose: execute Moncif's instruction in §2 (merge Packet G, then triage/fix the CodeQL findings). The session was ended by his instruction "Push the Done work then create a handoff file".
- Transfer status: §19

## 2. Original Starting Prompt

Verbatim, typos preserved:

```
first, Merge Packet G's branch first, then we'll start by checking few bugs revealed by github's codeQL:
1-  Incomplete URL substring sanitization found in tests/test_parser.py:18 and tests/test_module_factory.py :120  and tests/test_context.py :64.
2- Uncontrolled data used in path expression found in many places (to be found later) such as learning/trainer.py :61  and learning/scheduler.py :162 and core/module_factory.py :49
3- Information exposure through an exception found in core/brain_api.py :113  and  interface/api.py :529  and interface/api.py :160
only once these are finished do we start the freeze-manifest
```

## 3. Subsequent User Instructions / Corrections

- "Continue" (repeatedly) — go-ahead on the proposed next step each time.
- Supplied a replacement GitHub token after the previous one began returning HTTP 401. **The value is deliberately not recorded here** (§14).
- Final instruction: **"Push the Done work then create a handoff file"** — this file is its product. Note what it did *not* ask for: the pending fix was not applied (§9, §10).

Standing instructions from earlier in the same engagement that still govern this work:

- *"the freeze decision should be based on current executable reality plus reproducible verification, not on the age or apparent completeness of the previous audit."*
- Sequencing: the freeze-manifest starts **only after** the CodeQL work (§2, last line).
- `main` is changed only on his explicit instruction. He explicitly authorised exactly one thing: merging Packet G (done, PR #26). Everything else happens on branches.
- He chose `enforce_admins: false` on `main`'s branch protection: his own pushes bypass the required checks; PRs need `tests` + `drift-and-ownership`.
- He redefined "Packet G" as *implementation against Packet F's debts*. The original Packet G — "final debt re-triage + freeze manifest" — is what is now called the freeze-manifest and is **still not done**.
- He wants own mistakes reported plainly, and genuine policy forks put to him rather than guessed (he answered the admin-exemption question via tap-options).

## 4. Goal, Scope & Success Criteria

**Goal.** Give each of the three CodeQL alert categories a justified disposition (false positive with evidence / real and fixed with a proving test / tracked debt), so the freeze-manifest is written against a state where these are settled.

**In scope.** The three categories; for Category 2, the "many places (to be found later)" search — CodeQL's own alert list is the authoritative source (§16 table), not grep.

**Out of scope.** The freeze-manifest (queued behind this). Dependabot's open alerts (§15, flagged not investigated). `interface/api.py` having no authentication (already tracked, `DEBT-025`). Merging anything to `main`.

**Success criteria.** Every open alert classified; every *real* one fixed at its sink with a test that fails before and passes after; any remaining false positives dismissed with recorded evidence (Moncif has already dismissed #30–#32 and #36 himself); suite green; a PR whose required checks pass; register updated without duplicating existing rows; `handoff.md` removed before the PR.

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Merge Packet G's branch | §2 | **VERIFIED DONE** | PR #26 → merge commit `b1e4184`; 5/5 checks green before merging (`tests`, `drift-and-ownership`, `CodeQL`, `Analyze (python)`, `Analyze (actions)`) | Done by this session via the API with a real PR |
| R2 | Category 1 triage | §2.1 | **DONE** | Notes §Category 1; commit `d4f8236`; alerts #30–#32 are `dismissed` ("used in tests") by `1h0lde4` — §16 resolved table | **Moncif dismissed them himself.** Nothing left to do |
| R3 | Category 2: the 3 named examples | §2.2 | **DONE** | Notes §Category 2 | All three guarded; traced, not assumed. **Re-checked against `origin/main`'s current code** (§11): guards present; `module_factory.py`, `scheduler.py`, `trainer.py` unchanged since this branch's base |
| R4 | Category 2: the "many places" | §2.2 | **IN PROGRESS** | 29 open alerts at handoff time (§16) | The 3 named examples traced safe (the table marks those still matching by file:line); export-side proven blocked on `main`; 15 **UNCLASSIFIED** |
| R5 | Category 3 | §2.3 | **DONE UPSTREAM** | Alerts #33–#35 are `state=fixed` in CodeQL | Not done by this session; I verified only CodeQL's state, **not the fixing code** |
| R6 | Freeze-manifest | §2 | **BLOCKED by Moncif's own sequencing** | — | Do not start before R4 is finished unless he says otherwise |
| R7 | Push done work + create handoff | §3 | This file | Push verified: local HEAD == remote `94030f5` | — |

## 6. Current Verified State

**VERIFIED (by running it this session):**
- `export_module()` was genuinely exploitable on the pre-fix code: two tests added on this branch **fail** against this branch's `core/brain_export.py` (a decoy outside `modules/` ended up in a bundle that was itself written outside `data/exports/`). The application's own log confirmed it: `Exported '../decoy_area' → …/data/exports/../decoy_area_<ts>.ocbrain`.
- The same tests **pass 3/3 against `origin/main`'s code** (throwaway `git worktree`, `origin/main` @ `2e5cfc0`) — PR #34's fix closes exactly that exploit.
- Suite on this branch's code: **1536 passed, 2 failed — and the 2 failures are exactly the two exploit tests**. Baseline was 1535 passed; +3 new tests. `scripts/check_drift.py`: 15/15 PASS.
- CodeQL's API, **two snapshots in one session**: earlier, 32 open alerts all analysed at `main` @ `2e5cfc0`; at handoff time 29 open, analysed at `69df55f`, after Moncif dismissed #30–#32 and #36 and #19 was fixed (§16). Alert ids/lines **changed between snapshots** (a CodeQL re-analysis alone reshuffled them, even for files I verified unchanged) — never treat the table as stable.
- No GitHub token string (classic-PAT prefix) anywhere in the working tree at checkpoint time (the repo is **public**).

**IMPLEMENTED BUT NOT VERIFIED:** nothing. No production code was changed on this branch.

**INFERRED, not proven** (carry these as hypotheses):
- CodeQL's `py/path-injection` does **not** treat `str.isidentifier()` or dict-membership guards (`in _orchestrator.modules`) as sanitizers. Basis: the `brain_export.py` alerts stayed open on post-fix code although the exploit is demonstrably blocked (Moncif's own dismissal of #36, `brain_export.py:161`, as "false positive" is consistent with this — not proof). **Consequence: an open `py/path-injection` alert does not by itself mean an unfixed vulnerability.**
- Category 3 is closed *in code*. Basis: CodeQL state only.

**DEFERRED:** Dependabot alerts (§15). **BLOCKED:** freeze-manifest. **UNKNOWN:** whether the 17 unclassified alerts hide a real gap; whether the token can dismiss alerts.

## 7. Git / Repository Checkpoint

- Primary repository: `github.com/1h0lde4/ocbrain-v4.1` (**public**)
- Remote: `origin` (https)
- Branch: `security/codeql-findings-sep2026`
- Base: branched from `main` @ `b1e4184` (Packet G's merge)
- HEAD before handoff / **transfer commit**: `94030f50dc02533b1155ef23d10dd65aebb7cf4c`
- Handoff commit: the commit that adds `handoff.md`; its parent is the transfer commit above. (A file cannot contain its own commit hash — find it with `git log -1 -- handoff.md`.)
- `origin/main` at handoff time: `ecddbff6968c55ed50661ef28caaef5bb1270bf4` — this branch is **32 commits behind and 3 ahead**. `main` moved *during* this session (see `git log HEAD..origin/main`).
- Working tree at transfer: clean. No relevant untracked or ignored files. No submodules.
- Remote push status: implementation checkpoint pushed; verified `git rev-parse HEAD == git rev-parse origin/security/codeql-findings-sep2026`.
- **The branch is intentionally RED** at this checkpoint (the two exploit-proving tests fail against its own pre-fix code) and CI's `tests` job will show red on pushes to it. That is expected, not a regression.

## 8. Active Files / Modified Files / Artifacts

| File | State | Why it matters |
|---|---|---|
| `docs/Bugs Hunt & fix reports/CODEQL_FINDINGS_SEP2026_WORKING_NOTES.md` | added | Category 1 analysis; Category 2 reachability traces for the 3 named examples; postscript on `main` overtaking the branch |
| `tests/test_brain_export_security.py` | +3 tests, fixture `export_sandbox`, helper `_attempt_export` | The exploit proof; likely **redundant** with PR #34's own additions to this same file |
| `core/brain_export.py` | **unmodified** here | `main`'s copy carries the fix (`isidentifier` guard at the top of `export_module()` and of `import_module()`) |
| `interface/api.py` `POST /export`; `core/brain_api.py` `/export` route | unmodified | The **two** HTTP entry points into the one `export_module()` sink — why the fix belongs at the sink |
| `core/module_registry.py:24` | unmodified | Origin of `_orchestrator.modules` keys: `for path in sorted(MODULES_DIR.iterdir())` |

Nothing required for continuation exists only outside the pushed repository.

## 9. Changes Made

- **Behaviour/production code: none.**
- **Tests:** `test_export_path_traversal_cannot_write_bundle_outside_exports_dir`, `test_export_path_traversal_cannot_exfiltrate_files_from_outside_modules_dir`, `test_legitimate_module_name_still_exports` (positive control). They stub `config.get_module_state` and `brain_version_manager.get_state` so they are hermetic and cannot touch live config.
- **Docs:** the working-notes file above.
- **Not done on purpose:** the `isidentifier()` fix in `export_module()`. Moncif asked to push what was *done*; and, before that mattered, discovery showed `main` already has it. **Do not re-apply it** — reconcile with `main` instead (§17).

## 10. Decisions & Rationale

| ID | Decision | Status | Rationale | Reopen if |
|---|---|---|---|---|
| D1 | Fix path traversal **at the sink** (`export_module`), not at endpoints | Session judgment; consistent with CTX-EXPORT-001's precedent; **matches what `main` did** | Two HTTP routes reach one sink; an endpoint fix would leave the other open | A caller appears that bypasses `export_module` |
| D2 | Validate with `name.isidentifier()` | Project convention (`module_factory.create()`, `import_module()`) | Project explicitly kept one convention; all 7 real `modules/` dir names are identifiers | Legitimate non-identifier module names are ever needed |
| D3 | Exploit test uses traversal `../decoy_area` | Settled | Output path `EXPORTS/..` = `data/` exists, so the write *also* succeeds. A first design (`../victim_area/decoy`) would have passed on unfixed code for the wrong reason (`ZipFile()` fails on a nonexistent parent) | — |
| D4 | Stub the two config singletons in the tests | Settled | Hermetic; avoids the repo-state drift the suite otherwise causes | — |
| D5 | Push a deliberately RED checkpoint | Per `PROJECT_INSTRUCTIONS.md` §23.3 (checkpoint ≠ complete) | The failing tests *are* the evidence; the container reset had already cost one unpushed commit | — |
| D6 | Category 1: no code change | Settled | `in` on a `list[str]` is exact membership, not substring search | CodeQL alert text shows a different expression |
| D7 | Leave `/export`'s 500-vs-400 error mapping alone | **Deferred** | Overlaps Category 3 ownership; `main` since changed this code | — |
| D8 | Treat "open alert" ≠ "unfixed" until classified | Working hypothesis (§6, inferred) | Basis in §6 | Evidence that CodeQL does model `isidentifier` |

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| Category 1, 3 locations | read all three; checked the real types | **False positive ×3** | `core/parser.py:41` `urls = _URL_RE.findall(text)` (`re.findall` → list); `core/config.py:169` `get_sources(...) -> list[str]`; `core/context.py:178` `get_entity(...) -> list[str]` | — |
| `module_factory.create()` (alert `:49`) | whole function | **Guarded.** Single linear function; `isidentifier()` before the path join; no branch skips it | read in full; **re-checked on `origin/main`: file identical to this branch's base, `isidentifier` present** | A new early-return/branch before the check |
| `scheduler.trigger_module()` (alert `:162`, `rmtree`) | callers + origin of `module_name` | **Guarded.** Sole caller: `interface/api.py` `POST /train/{module_name}`, which does `if module_name not in _orchestrator.modules: 404` first. Keys come from `MODULES_DIR.iterdir()` — real single-segment dir names; POSIX listings never yield `.`/`..` | `git grep trigger_module(`; `core/module_registry.py:24`; `main.py:400`; **re-checked on `origin/main`: the `/train` guard and the `iterdir()`-built registry are still present; `scheduler.py` and `trainer.py` unchanged** | A second caller of `trigger_module()` |
| `trainer.prepare()` (alert `:61`) | callers | **Guarded by the same chain.** Two callers, both in `scheduler.py` (`for name in self.registry` and `trigger_module`) | `git grep trainer.prepare(` | A caller outside `scheduler.py` |
| `export_module()` | endpoint, request model, function body, both callers | **Was exploitable; proven by test; fixed on `main`** (PR #34) | §6 | — |
| CodeQL API | open + fixed alert lists, analysed commit | §6 and §16 | API responses | Re-fetch — `main` has moved |
| Whole-codebase grep for `module_name`/`name` used as a path component | one grep | ~14 hits across `core/brain_export.py`, `module_factory.py`, `module_registry.py`, `privacy.py` and `learning/{cleaner,crawler,distiller,finetuner,gap_detector,trainer}.py`. **Superseded by the alert table** — use that | — | — |

**Explicitly NOT inspected:** every alert marked UNCLASSIFIED in §16; the `/import`, `/distill`, `/executions/{id}`, `/update/install`, `/rollback`, `PUT /config` routes (route list enumerated, not analysed); the *code* of PRs #35/#36/#37/#39 (commit messages only); `/export`'s behaviour on `main` beyond the exploit test.

## 12. Failed Attempts / Dead Ends

| Approach | Result | Cause / evidence | Retry? |
|---|---|---|---|
| First exploit-test design (`../victim_area/decoy`) | Rejected before running | Would pass on unfixed code for the wrong reason: output parent `data/victim_area` doesn't exist → `ZipFile()` raises → no bundle | No |
| Diagnosing the push failures as a git/credential-helper problem | Wasted several steps | The real cause was an **expired token** (HTTP 401 on API and git endpoints). Check `curl -s -o /dev/null -w '%{http_code}'` against the API **first** | Check auth first next time |
| Local-only commit of the Category 1 analysis | **Lost** in a container reset | Never pushed; rebuilt after re-verifying facts. Lesson: push each finding immediately | — |
| `${sha:0:7}` (bash substring) in a shell block | `Bad substitution` | The tool shell is `/bin/sh`, not bash. Also unavailable: `time`, `<(…)` | Avoid bashisms |
| A literal `echo "(empty above = none changed)"` next to a diff | Misleading — printed even though the diff showed 4 changed files | An unconditional echo is not a result. **Read the command's actual output** | Don't write self-confirming echoes |
| Earlier-engagement merge scripts | Silently dropped `DEBT-031…035` once | Assumed two rows were adjacent in the file; a "clean" `git merge` is not proof. After any merge, grep **each** `| DEBT-NNN |` header individually | See `KNOWN_ISSUES.md` sync-chain |

## 13. Verification Evidence

| Command / scope | Result | Limits |
|---|---|---|
| `pytest tests/test_brain_export_security.py` on this branch's pre-fix code | `..FF.` — 2 pre-existing pass, 2 exploit tests **fail**, control passes | — |
| Same 3 added tests vs `origin/main` @ `2e5cfc0` in a throwaway worktree | **3 passed** | Run against `2e5cfc0`, not today's `main` |
| `pytest -q --tb=no -p no:cacheprovider` (full suite), tree = `d4f8236` + the test additions (code-identical to the transfer commit; the later commit only added markdown) | **1536 passed, 2 failed** — the two exploit tests | Not run against current `main` |
| `python3 scripts/check_drift.py` | 15/15 PASS, exit 0 | — |
| CodeQL REST API (`code-scanning/alerts`) | §6, §16 | Snapshot; `main` moved afterwards |
| PR #26 CI before merge | 5/5 success | — |

## 14. Environment / Tooling Assumptions

- OS: Ubuntu 24.04.4 LTS; Python 3.12.3; pytest 9.1.1; chromadb 0.5.3 (the pin in `requirements.txt`); fastapi 0.141.1; **`torch`, `sentence-transformers`, `trafilatura` are NOT installed.** Every baseline in this engagement was measured in this *minimal-dependency* class — do not change it casually.
- **The container can reset** (it did once, mid-session: repo, branches and the Python environment all vanished; only what was pushed survived).
- Rebuild:
  ```
  mkdir -p /home/claude/audit && cd /home/claude/audit && git clone https://github.com/1h0lde4/ocbrain-v4.1.git repo
  cd repo && git checkout security/codeql-findings-sep2026
  grep -vE "^(sentence-transformers|trafilatura)" requirements.txt > /tmp/req_minimal.txt
  pip install --no-cache-dir --break-system-packages -r /tmp/req_minimal.txt
  ```
  **Never plain `pip install -r requirements.txt`** — it pulls torch-scale packages and changes the environment class.
- Running the full suite **mutates tracked runtime-state files**; revert before committing: `git checkout -- config/ data/context.sqlite`.
- Tool shell is `/bin/sh` (no bashisms). `sed` with `#` as delimiter breaks on replacement text containing `#`; use `|`.
- **Credential:** a GitHub PAT with `repo` + admin on `1h0lde4/ocbrain-v4.1` is required to push and for the API. It is supplied by Moncif per session and **must never be written to any file or commit** (repo is public). Push pattern: `git push "https://<TOKEN>@github.com/1h0lde4/ocbrain-v4.1.git" <branch> 2>&1 | sed "s#<TOKEN>#***#g"`.
  - **The token in Moncif's saved `userPreferences` is the old, revoked one (HTTP 401).** A fresh session will see that stale value in its prompt. Moncif must update it (Settings → Profile) or paste a new one.
  - The replacement token was pasted in plaintext into a chat and has admin scope on a public repo — **recommend he revoke/rotate it once this work is done.**
  - Observed to work with the current token: repo read/write, branch protection, PR create/merge, **code-scanning read**, Dependabot read. **Untested:** code-scanning *write* (needed to dismiss alerts).

## 15. Unresolved Questions / Risks / Blockers

| ID | Issue | Evidence | Safe to continue without resolving? |
|---|---|---|---|
| U1 | 15 of 29 open alerts are UNCLASSIFIED (§16) | table | Yes — it *is* the work |
| U2 | Does CodeQL model `isidentifier()` / membership guards? (Inferred "no".) If not, either dismiss-with-evidence or restructure to a CodeQL-recognised containment check (e.g. `resolve()` + `is_relative_to(base)` or `normpath`+`startswith`) so alerts clear for the right reason. **Which shapes CodeQL recognises is unverified** — a cheap experiment on a throwaway PR would settle it | §6 | Yes |
| U3 | **Moncif is working the alert list in the GitHub UI in parallel**: he dismissed #30–#32 ("used in tests") and #36 ("false positive") on 2026-10-02 ~00:44Z. Whether this session's token can dismiss via API is still untested | §16 resolved table | **Re-fetch before classifying; don't redo or contradict his dismissals; ask before dismissing anything else** |
| U4 | `main` moves several times an hour (other sessions). Alert list and every SHA here are snapshots | `origin/main` moved during this session | Re-fetch before acting |
| U5 | PR #39 (`8cae589`, "stop returning raw exception text in caller-visible answers (`[Error in <module>: …]`)") touches the inline-error behaviour that Packet D's `DEBT-029` / finding D-5 reasoned about in `PlannerWorker` | commit message only | Check `DEBT-029`'s text still matches `planner.py` on `main` |
| U6 | Dependabot open alerts (snapshot below). Out of scope here; GitHub also announces "3 vulnerabilities (1 critical, 2 high)" on every push | below | Yes, but **don't let them be forgotten** |
| U7 | Severity honesty: the export traversal's write side is constrained (fixed `_<ts>.ocbrain` suffix, parent dir must exist, creates rather than overwrites); the read side is bounded (`weights/active`, `knowledge.db`, `data/evals/<name>.json`, ≤100 `data/raw/<name>/*.json`); reachable only via the unauthenticated loopback API (`DEBT-025`). Medium/Low-Medium — **not** comparable to CTX-EXPORT-001's arbitrary deletion | §10 D-notes | — |
| U8 | Keep or drop this branch's 3 tests — likely redundant with PR #34's | — | Yes |
| U9 | CI `tests` is red on this branch by design | §7 | Yes |

Dependabot snapshot:

3 open.

| # | severity | package | CVE | summary |
|---|---|---|---|---|
| #3 | critical | `chromadb` | CVE-2026-45833 | ChromaDB has a code injection vulnerability |
| #2 | high | `chromadb` | CVE-2026-45831 | ChromaDB's SimpleRBACAuthorizationProvider doesn't check which tenant, database, |
| #1 | high | `chromadb` | CVE-2026-45830 | ChromaDB allows any authenticated users to arbitrarily read, write, update, or d |

## 16. Relevant Information / References

**CodeQL open alerts — snapshot** (API; analysed commit `69df55f`; fetched 2026-10-03 19:05 UTC). Status column = what *this session* established, nothing more:

| # | rule | severity | location | status (this session) |
|---|---|---|---|---|
| #1 | `py/path-injection` | high | `core/brain_export.py:63` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #2 | `py/path-injection` | high | `core/brain_export.py:96` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #3 | `py/path-injection` | high | `core/brain_export.py:97` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #4 | `py/path-injection` | high | `core/brain_export.py:101` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #5 | `py/path-injection` | high | `core/brain_export.py:105` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #6 | `py/path-injection` | high | `core/brain_export.py:106` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #7 | `py/path-injection` | high | `core/brain_export.py:108` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #8 | `py/path-injection` | high | `core/brain_export.py:112` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #9 | `py/path-injection` | high | `core/brain_export.py:113` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #10 | `py/path-injection` | high | `core/brain_export.py:117` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #11 | `py/path-injection` | high | `core/brain_export.py:119` | export-side: BLOCKED on main (exploit tests pass 3/3) |
| #12 | `py/path-injection` | high | `core/brain_export.py:177` | import-side: UNVERIFIED (zip-slip fix claimed by a commit message; not tested here) |
| #37 | `py/path-injection` | high | `core/module_factory.py:45` | UNCLASSIFIED |
| #20 | `py/path-injection` | high | `core/module_factory.py:52` | UNCLASSIFIED |
| #21 | `py/path-injection` | high | `core/module_factory.py:68` | UNCLASSIFIED |
| #22 | `py/path-injection` | high | `core/module_factory.py:70` | UNCLASSIFIED |
| #23 | `py/path-injection` | high | `core/module_factory.py:74` | UNCLASSIFIED |
| #24 | `py/path-injection` | high | `core/module_registry.py:60` | UNCLASSIFIED |
| #13 | `py/path-injection` | high | `learning/distiller.py:172` | UNCLASSIFIED |
| #14 | `py/path-injection` | high | `learning/distiller.py:183` | UNCLASSIFIED |
| #15 | `py/path-injection` | high | `learning/evaluator.py:91` | UNCLASSIFIED |
| #16 | `py/path-injection` | high | `learning/evaluator.py:94` | UNCLASSIFIED |
| #17 | `py/path-injection` | high | `learning/finetuner.py:22` | UNCLASSIFIED |
| #18 | `py/path-injection` | high | `learning/finetuner.py:96` | UNCLASSIFIED |
| #25 | `py/path-injection` | high | `learning/scheduler.py:162` | SAFE (traced; notes §Category 2) |
| #26 | `py/path-injection` | high | `learning/trainer.py:34` | UNCLASSIFIED |
| #27 | `py/path-injection` | high | `learning/trainer.py:37` | UNCLASSIFIED |
| #28 | `py/path-injection` | high | `learning/trainer.py:58` | UNCLASSIFIED |
| #29 | `py/path-injection` | high | `learning/trainer.py:61` | SAFE (traced; notes §Category 2) |

Counts: UNCLASSIFIED: 15, export-side blocked: 11, import-side unverified: 1, safe (traced): 2. Re-fetch the live list: `GET /repos/1h0lde4/ocbrain-v4.1/code-scanning/alerts?state=open&per_page=100` (and `state=fixed`). Dismiss (after U3): `PATCH …/code-scanning/alerts/{n}` with `{"state":"dismissed","dismissed_reason":"false positive","dismissed_comment":"…"}`.

**Resolved alerts at handoff time** (dismissed or fixed; generated from the API). Category 3 is the three `py/stack-trace-exposure` rows (your `:529`/`:160` — line numbers shifted by the fixes):

| # | state | rule | location | detail |
|---|---|---|---|---|
| #19 | fixed | `py/path-injection` | `core/module_factory.py:45` | fixed at 2026-10-02T00:03:49Z |
| #30 | dismissed | `py/incomplete-url-substring-sanitization` | `tests/test_context.py:64` | dismissed **used in tests** by `1h0lde4` at 2026-10-02T00:43:59Z |
| #31 | dismissed | `py/incomplete-url-substring-sanitization` | `tests/test_module_factory.py:120` | dismissed **used in tests** by `1h0lde4` at 2026-10-02T00:44:00Z |
| #32 | dismissed | `py/incomplete-url-substring-sanitization` | `tests/test_parser.py:18` | dismissed **used in tests** by `1h0lde4` at 2026-10-02T00:44:01Z |
| #33 | fixed | `py/stack-trace-exposure` | `interface/api.py:178` | fixed at 2026-09-29T12:37:34Z |
| #34 | fixed | `py/stack-trace-exposure` | `interface/api.py:544` | fixed at 2026-09-29T12:37:34Z |
| #35 | fixed | `py/stack-trace-exposure` | `core/brain_api.py:113` | fixed at 2026-09-27T18:37:28Z |
| #36 | dismissed | `py/path-injection` | `core/brain_export.py:161` | dismissed **false positive** by `1h0lde4` at 2026-10-02T00:44:14Z |

**Repository artifacts**
- `PROJECT_INSTRUCTIONS.md` — the governing contract (§18.4.8 handoff, §18.4.9 fresh-session recovery, §23 branch/commit rules).
- `KNOWN_ISSUES.md` — the register. Highest `DEBT-` id on `origin/main` at handoff: **DEBT-038** — **verify live before assigning a number**; collisions with concurrent sessions happened three times this engagement. Rows from this engagement: `DEBT-030…036` (Packets C/D/F), `DEBT-038` is another session's `/distill` fix.
- `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md` — maintained by other sessions; can lag `main`.
- `docs/Bugs Hunt & fix reports/PACKET_{C,D,E,F,G}_*` — prior packets' prompts, working notes, closing reports (all on `main` via PR #26).
- `.github/workflows/ci.yml` (`tests` gates on new failures vs `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`; `drift-and-ownership` runs `scripts/check_drift.py`), `release.yml`, `dependabot.yml`.
- ADRs under `docs/architecture/decisions/` (CTX-AUTH-001b was implemented on `main` by another session as ADR-KERNEL-06; ADR-KERNEL-07 is PROPOSED, flag-off).

**Broader engagement context (compact).** Moncif (`1h0lde4`; also commits as "N4Z") owns the repo and makes the calls; terse "Continue" = go ahead. Packets C→G of the Kernel v1.0 freeze audit are complete and merged (PR #26): governance/identity/provenance, durability/retry/concurrency, test baseline, dependency/CI/release governance, then implementation of its four debts (`DEBT-032…035`). Branch protection on `main` is live (`tests`, `drift-and-ownership`, strict, admins exempt). **Other Claude sessions land PRs on `main` continuously** (this session saw #34–#41 land). Working conventions: check the register *before* tracing; evidence-first (prove with a test or a trace, don't assert); long explanatory commit messages; separate commits per logical change; push immediately.

## 17. Next Steps

1. **Verify the transfer** (§18). Read this file fully.
2. **Environment** — confirm the §14 fingerprint; rebuild if the container reset.
3. **Reconcile with `main` before anything else** — `git fetch origin && git merge origin/main`. Expect a **conflict in `tests/test_brain_export_security.py`** (both sides appended). Read `main`'s added tests first. If they already cover (a) bundle written outside `EXPORTS` and (b) decoy exfiltration from outside `modules/`, **drop this branch's 3 tests** (cleanest); otherwise keep them, taking care over duplicate names (`SECRET`, `export_sandbox`, `_attempt_export`, `SimpleNamespace`). After the merge, verify `KNOWN_ISSUES.md` by grepping **each** `| DEBT-NNN |` header, not by trusting "clean".
4. **Re-baseline** — full suite + `check_drift.py` on the merged tree; revert `config/` / `data/context.sqlite`. Record results. Expected: green.
5. **Re-fetch CodeQL's alert list** and diff it against §16.
6. **Classify the UNCLASSIFIED `py/path-injection` alerts by sink, not one by one.** For each: parameter origin → where it's validated → reachability from an HTTP route (`git grep` the callers). Guarded → record the trace. Unguarded and reachable → write the **decoy exploit test first and watch it fail** (D3's lesson), fix at the sink with `isidentifier()` (project convention), watch it pass. Look at `/import` and the others in §11 "not inspected".
7. **Decide the alert strategy** (U2): dismiss-with-evidence vs. a CodeQL-recognised containment helper. Test on a throwaway PR if choosing the latter.
8. Category 1 is **already dismissed by Moncif**. For any *further* dismissal, ask first and reuse his reasons (`used in tests` / `false positive`) for consistency.
9. **Register:** record what's new without duplicating existing rows (check first). Push after each logical step.
10. `git rm handoff.md`; open a PR to `main`; wait for the 5 checks; **merge only on Moncif's instruction**.
11. **Only then** the freeze-manifest. It needs a fresh, evidence-first reconciliation of the full register against live `main`; the statuses of `DEBT-032…036`; CTX-AUTH-001b (now implemented) and ADR-KERNEL-07 (proposed); and the Kernel v1.0 verdict. Apply the same "verify against live state" discipline — `main` is moving fast.

## 18. Resume Instructions

1. `git fetch origin` and confirm branch `security/codeql-findings-sep2026` exists on the remote at the transfer commit `94030f50dc02533b1155ef23d10dd65aebb7cf4c` (+ the handoff commit on top).
2. Verify the remote branch actually contains `handoff.md`.
3. Compare this file's claims to the live repository (SHAs, alert counts, file contents). **If they disagree, the repository wins — correct this file, don't "choose whichever is convenient"** (§18.4.9).
4. Resolve mismatches before changing code.
5. Begin at §17 step 3. Do not redo §11 unless something changed.

## 19. Transfer Status

**TRANSFER READY** — all material work is committed and pushed, the checkpoint was verified against the remote, and the next action is exact.

Caveats the receiver must not mistake for defects: the branch is **intentionally RED** (§7) and **behind `main`** (§7); the one pending code change (the sink fix) is already on `main`, so step 3 is a reconciliation, not an implementation.
