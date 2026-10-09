# Session Handoff (v2)

> Transfer record per `PROJECT_INSTRUCTIONS.md` §18.4.8. **Replaces v1** — v1's statements about open alerts and "Category 2 in progress" are superseded and must not be relied on. **This is a temporary record, not an authority** (§18.4.9): verify it against the live repo before trusting it. **Do not merge this file to `main`** — `git rm handoff.md` before opening any PR, after promoting anything durable into `KNOWN_ISSUES.md` / the working notes.

## 1. Handoff Metadata

- Handoff version: 2
- Created at: 2026-10-09 08:45 UTC (container clock, checked equal to GitHub's server time earlier in the session)
- Workstream: CodeQL-findings triage — now essentially closed upstream — plus the follow-ups it surfaced; the gate before the Kernel v1.0 freeze-manifest
- Source session purpose: carry out Moncif's instruction in §2; ended by his instruction "update the finished work to repo, as for the remaining work, create a handoff file so we can complete it in a new session"
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

- "Continue" (repeatedly).
- Supplied a replacement GitHub token after the first one returned HTTP 401 (**value deliberately not recorded**, §14).
- "Push the Done work then create a handoff file" (produced v1).
- "Continue, speed up the work for the risk of container reset".
- **Latest:** "update the finished work to repo, as for the remaining work, create a handoff file so we can complete it in a new session" — this file. Consequently **no new code work was done after that instruction**: the `core/privacy.py` finding (§6, R6) is described and left for the next session.

Standing instructions from earlier in the engagement that still govern:

- *"the freeze decision should be based on current executable reality plus reproducible verification, not on the age or apparent completeness of the previous audit."*
- Sequencing (§2, last line): the freeze-manifest starts **after** the CodeQL work. By CodeQL's own state that gate is now met (R1–R5) — **but ask Moncif before starting the manifest**, and see §15 U1: another session may already be doing part of it.
- `main` changes only on his explicit instruction (he authorised exactly one thing: the Packet G merge, done). Everything else is branch work.
- He chose `enforce_admins: false` on `main`'s branch protection (his own pushes bypass the required checks; PRs need `tests` + `drift-and-ownership`).
- He redefined "Packet G" as implementation against Packet F's debts; the *original* "final debt re-triage + freeze manifest" is what is now simply "the freeze-manifest" and is **not done**.
- He wants own mistakes reported plainly and genuine policy forks put to him rather than guessed.

## 4. Goal, Scope & Success Criteria

**Goal of the remaining work.** (a) Close the one concrete gap this workstream found that CodeQL did not (R6). (b) Check that "every module-name path is routed through `module_child()`" is true in practice, not only per CodeQL. (c) Hand the freeze-manifest a clean input list.

**In scope:** R6 (a decoy-proven fix of the latent deletion sink); a systematic sweep for other unguarded destructive sinks; recording the Dependabot/chromadb tension for Moncif; getting this branch's finished content into a PR.

**Out of scope until Moncif says so:** merging anything to `main`; the freeze-manifest itself; deciding the chromadb/Dependabot question (it needs his call).

**Success:** R6 fixed with a test that fails first and passes after; sweep recorded; the branch merged-with-main, suite green, drift 15/15, `handoff.md` removed, PR open with all required checks green.

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Merge Packet G | §2 | **VERIFIED DONE** | PR #26 → `b1e4184`; 5/5 checks green first | |
| R2 | Category 1 | §2.1 | **DONE** | Alerts #30–#32 dismissed ("used in tests") **by Moncif** | My analysis agrees (list membership, not substring) — working notes |
| R3 | Category 2: 3 named examples | §2.2 | **DONE** | Traced guarded; alerts since `fixed` | |
| R4 | Category 2: "many places" | §2.2 | **DONE UPSTREAM; one residual (R6)** | 30 `py/path-injection` alerts `fixed`; fix = `acc43b7` (`module_child()`) + `6dee2b2` (`/import` confinement) | I verified by execution (76/76 containment tests) and a raw-join sweep, **not** by reading the fixes line by line |
| R5 | Category 3 | §2.3 | **DONE UPSTREAM** | 3 `py/stack-trace-exposure` alerts `fixed` | Verified via CodeQL state only |
| R6 | *(new)* `PrivacyGuard.wipe_module_data` latent deletion sink | found this session | **OPEN — not proven by test, not fixed** | §6 | Zero production callers → latent |
| R7 | Sweep for other unguarded destructive sinks | follows from R6 | **NOT STARTED** | — | My raw-join grep was heuristic (§11) |
| R8 | Freeze-manifest | §2 | **UNBLOCKED by sequencing; needs Moncif's go-ahead** | — | Overlap check first (§15 U1) |
| R9 | Push finished work + handoff | §3 | **DONE** | Pushed and verified | This file |

## 6. Current Verified State

**VERIFIED (by running it):**
- CodeQL: 37 alerts — 33 fixed, 4 dismissed. Last fix `2026-10-05T07:31Z`.
- `tests/test_module_name_containment.py`: **76/76 pass** (in a sandbox *with* `trafilatura`; without it all 51 tests that use the `sandbox` fixture error — §14).
- Full suite on this branch's tree (`e8c71a5`; later commits are docs-only): **`1970 passed, 1 xfailed`**, exit 0. `scripts/check_drift.py`: **15/15 PASS**. (`1535/0` — the old baseline — no longer applies.)
- This branch's 3 end-to-end export tests pass against `main`'s code and failed against the pre-fix code (the exploit was real; PR #34 closed it).
- `KNOWN_ISSUES.md` after the merge with `main`: every `DEBT-` header from both parents present, no duplicates (checked per-row, not by trusting the merge).

**R6 — the open finding (verified by reading + grep; NOT yet by a test):**
```python
# core/privacy.py — unchanged on main since 2026-06-30; no module_child
def wipe_module_data(self, module_name: str):
    import shutil
    for folder in ["data/raw", "data/chunks"]:
        p = Path(__file__).parent.parent / folder / module_name
        if p.exists():
            shutil.rmtree(p)
```
No containment on a `shutil.rmtree` — the CTX-EXPORT-001 class. `module_name="../../.."` resolves above the repo root. **Reachability today: none** — `git grep "wipe_module_data|wipe_all"` over production code on `main` finds only the definitions; `tests/test_privacy.py` (~lines 28–42) *stubs* `wipe_module_data` with a lambda, so the real function is never run by a test. Classify: latent sink, **UNPROVEN as live**; it becomes live if anything wires it to an endpoint. Re-run the freshness check (§17 step 2a) before acting — `main` moves hourly.

**INFERRED, not proven:** that CodeQL's silence on R6 is because it has no reachable taint source; that `results_count=3` in CodeQL's latest 43-rule analysis of `main` is the three dismissed alerts.

**UNKNOWN:** the origin of the `1 xfailed` on `main` (not mine; the repo previously stated it had no xfail convention); whether `main`'s CI is green right now; the content of PR #25 and the Dependabot advisories (I read titles/CVE ids only).

## 7. Git / Repository Checkpoint

- Repo: `github.com/1h0lde4/ocbrain-v4.1` (**public**); remote `origin` (https).
- Branch: `security/codeql-findings-sep2026`; branched from `main` @ `b1e4184`; already merged with `main` once (`e8c71a5`, resolving the single test-file conflict — both test blocks kept).
- **Transfer commit** (pushed, verified local == remote): `8d62d98cf10b048ed67d15f8765be30485b9c509`. The **handoff commit** is the one adding this v2 file; its parent is the transfer commit (find it: `git log -1 -- handoff.md`).
- `origin/main` at handoff: `8c0ea037e2152d9f4bb5150d35c6bb5ea817957d` — branch is **21 behind, 6 ahead**.
- Working tree clean at transfer. No submodules.
- The branch is **no longer red** (unlike v1's checkpoint): its tests pass once `trafilatura` is installed.
- Branch content vs `main`: the working-notes file, +3 end-to-end export tests (`tests/test_brain_export_security.py`), a postscript/final-disposition in the notes, a Packet E notes correction, and this handoff. **No production code differs from `main`.** No PR is open for it.

## 8. Active Files / Artifacts

| File | Why it matters |
|---|---|
| `docs/Bugs Hunt & fix reports/CODEQL_FINDINGS_SEP2026_WORKING_NOTES.md` | Category 1/2 analysis, postscript, **final disposition**, the R6 write-up, corrections |
| `docs/Bugs Hunt & fix reports/PACKET_E_TEST_SUITE_BASELINE_WORKING_NOTES_SEP2026.md` | Now carries my correction (missed `learning/crawler.py:12`; trafilatura is light) |
| `tests/test_brain_export_security.py` | +3 end-to-end tests, complementary to `main`'s guard-level `TestExportModuleNameValidation` |
| `core/privacy.py` (`wipe_module_data`, line ~24) | **The R6 target** — unmodified |
| `core/module_paths.py` | The shared helper; read its docstring first. Signature (verify): `module_child(root: Path, module_name: str, suffix: str = "") -> Path`, raises `InvalidModuleName`; also `validate_module_name()` |
| `tests/test_module_name_containment.py` | `main`'s containment suite across the sinks — read how it registers sinks; R6 may belong here |
| `tests/test_privacy.py` | Stubs `wipe_module_data` — does not cover the real function |

## 9. Changes Made

Documentation, tests, and a merge only. **No production behaviour changed on this branch.** (The `isidentifier()` export fix I once planned was never applied — `main` already had it.)

## 10. Decisions & Rationale

| ID | Decision | Status | Rationale | Reopen if |
|---|---|---|---|---|
| D1 | Keep this branch's 3 end-to-end export tests alongside `main`'s guard-level ones | Session judgment | `main`'s asserts the guard fires; mine prove the *harm* can't occur (decoy exfiltration; bundle written outside `EXPORTS`) — a refactor could keep the guard yet leak via the output filename. Matches the project's own import-side test style | Moncif prefers fewer tests |
| D2 | Install `trafilatura` in the sandbox | Environment, reversible | Light, no `torch`; required by `main`'s new tests | — |
| D3 | Do **not** fix R6 now | Per Moncif's latest instruction | He asked to push finished work and hand off the rest | — |
| D4 | No `DEBT-` row yet for R6 | Deliberate | Highest id on `main` is `DEBT-041` and collisions with concurrent sessions happened three times — register-check and take the live max at write time | — |
| D5 | "Fixed in CodeQL" is a claim to verify, not a fact | Working principle | The tool's model ≠ the code; R6 is the proof | — |

## 11. Investigation Already Performed

| Area | Result | Evidence |
|---|---|---|
| Category 1 (3 sites) | False positive | `core/parser.py:41` `re.findall`; `get_sources() -> list[str]`; `get_entity() -> list[str]` |
| The 3 named Category 2 sites | Guarded (and since `fixed`) | Traces in the notes; guards re-checked on `main` |
| `export_module()` | Was exploitable (test-proven); fixed by PR #34; my tests pass on `main` | Notes postscript |
| `core/module_paths.py` | Read; careful design (canonicalizes, direct-child only, symlink-aware, error text doesn't echo input) | Docstring states `.isidentifier()` isn't a boundary and CodeQL doesn't treat it as one |
| `module_child` adoption | Used in `brain_export`(8), `module_factory`(2), `module_registry`(2), `learning/` cleaner(3) crawler(2) distiller(2) evaluator(3) finetuner(2) gap_detector(7) trainer(4) | `git grep -c module_child` |
| Raw-join sweep | Found **one**: `core/privacy.py:26` (R6) | Heuristic regex (below) — **weak evidence of absence** |
| CodeQL alert history | 37 alerts: 33 fixed, 4 dismissed, 0 open; Category 3 = 3 fixed | API |
| Dependabot / open PRs | Listed (titles, CVE ids only) | §15 |

The sweep's pattern covered `(MODULES_DIR|MODULES|DATA_RAW|DATA_CHUNKS|DATA_CLEAN|MODELS_DIR) / …name`, `/ module_name`, `/ req.(module_)?name` in `core learning interface modules`. It **would miss**: other root names, `os.path.join(...)`, f-string paths (`f"modules/{name}"`), `Path(x) / some_id` where the variable isn't called `name`, and non-module-name identifiers.

**Explicitly NOT inspected:** the diffs of `acc43b7`/`6dee2b2`/PR #34–#39; routes `/executions/{execution_id}`, `/update/install`, `/rollback`, `PUT /config`; any destructive sink other than R6; PR #25's contents; current `CURRENT_STATE.md`.

## 12. Failed Attempts / Dead Ends / Lessons

| What happened | Lesson |
|---|---|
| Spent effort on an `export_module()` fix `main` already had (a concurrent session fixed it while I worked) | **Before building a fix, `git fetch` and grep `origin/main` for it.** This duplicated work once; it can again |
| My alert snapshot changed three times in one session; v1 of this handoff went stale in hours | Treat every alert list / SHA / PR number here as a snapshot; **re-fetch first** |
| Misjudged when Moncif's dismissals happened ("minutes ago" — actually ~21 h) | Read the timestamps *and* compare with the server clock |
| Packet E dependency matrix missed `learning/crawler.py:12` | My grep omitted `learning/`; scope your searches to the whole tree, then narrow |
| Treated `trafilatura` as "heavy ML" | Check a package's actual footprint before excluding it from an environment class |
| Pushed to diagnose a credential problem as a git config issue | It was an expired token — test auth with a plain `curl` to the API first |
| A self-confirming `echo "(empty = none changed)"` printed beside a non-empty diff | Read the command's real output; never write the conclusion into the command |
| Container reset lost an unpushed commit once | Push after each logical step |
| `${var:0:7}`, `time`, `<(...)` fail | Tool shell is `/bin/sh` |
| A "clean" `git merge` once silently dropped `DEBT-031…035` (earlier in the engagement) | After any merge, grep each `| DEBT-NNN |` header; this session's gating script (commit only if rows ✓, suite ✓, drift ✓) worked well — reuse it |

## 13. Verification Evidence

| Command / scope | Result | Limits |
|---|---|---|
| `pytest tests/test_brain_export_security.py` after resolving the merge | 10 passed | — |
| Full suite on the merged tree (`e8c71a5`) | `1970 passed, 1 xfailed`, exit 0 | Not re-run on today's `main` |
| `tests/test_module_name_containment.py` | 76 passed (with `trafilatura`); 51 errors without | — |
| `check_drift.py` | 15/15 | — |
| CodeQL REST API | §6 | Snapshot |

## 14. Environment / Tooling Assumptions

- OS: Ubuntu 24.04.4 LTS. Python 3.12.3, pytest 9.1.1, chromadb 0.5.3 (the `requirements.txt` pin, `DEBT-032`), fastapi 0.141.1, **trafilatura 2.3.0 (now required)**; **`torch`, `transformers`, `sentence-transformers` are NOT installed.** That is the sandbox class every baseline here was measured in.
- Containers can reset. Rebuild:
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

| ID | Issue | Evidence | Continue without resolving? |
|---|---|---|---|
| U1 | **Overlap with another session's freeze work.** Open PR #25 ("Audit remaining freezing blockers…") plus an `FZ-xx` numbering (FZ-02/B2a/B2b, FZ-03) in recent commits and PRs #45/#61/#71 suggest others are enumerating freeze blockers | PR table below; commit titles | **No — read PR #25 and `CURRENT_STATE.md` before starting the manifest** |
| U2 | **Dependabot security alerts: three of four are on `chromadb`, the package pinned to `0.5.3` by `DEBT-032`** (and one is on `sentence-transformers`). Open PR #33 bumps chromadb `0.5.3 → 1.5.9`. The pin exists so CI tests what `release.yml` ships; bumping `requirements.txt` alone would recreate the very test/release divergence `DEBT-032` fixed (in reverse). Commits `bc27d8d` / `8284149` on `main` mention a "DEBT-032 embedded-only boundary" — **I have not read them or the advisories**, so I do **not** know whether the CVEs affect embedded-only use | table below | **Moncif's decision.** Don't merge #33 or touch the pin without also changing `release.yml`, re-verifying the fixture reads and the suite, and assessing the CVEs |
| U3 | PR #32 relaxes the `sentence-transformers` upper bound — it touches the ML-stack boundary | PR table | Moncif's call |
| U4 | Five Actions-bump PRs (#27–#31): the SHA-pinned Actions are being updated by the Dependabot setup from `DEBT-035` — as designed. Several are **major** jumps; check that `upload-artifact` and `download-artifact` move to compatible majors (they may not in these PRs) | PR table | Review as a set |
| U5 | R6 severity: latent, **not** live. Don't overstate; don't understate (it's a bare `rmtree`) | §6 | — |
| U6 | The R7 sweep is open-ended; heuristic grep has false negatives | §11 | Yes |
| U7 | `main` moves hourly; this branch is behind | §7 | Re-merge before any PR |
| U8 | Token hygiene (§14) | — | — |

**Dependabot security alerts (live at handoff):**

4 open.

| # | severity | package | CVE | summary |
|---|---|---|---|---|
| #4 | critical | `sentence-transformers` | CVE-2026-68770 | sentence-transformers local model loading bypasses trust_remote_code and execute |
| #3 | critical | `chromadb` | CVE-2026-45833 | ChromaDB has a code injection vulnerability |
| #2 | high | `chromadb` | CVE-2026-45831 | ChromaDB's SimpleRBACAuthorizationProvider doesn't check which tenant, database, |
| #1 | high | `chromadb` | CVE-2026-45830 | ChromaDB allows any authenticated users to arbitrarily read, write, update, or d |

**Open PRs (live at handoff):**

| PR | branch | title |
|---|---|---|
| #61 | `tools/live-check-repeat-runs` | tools: repeated live-check runs with provenance and a pre-registered comparison (draft) |
| #45 | `chore/live-check-runbook` | docs: live draft-plan check — runbook, first valid result (llama3, n=11), corrections |
| #33 | `dependabot/pip/chromadb-1.5.9` | build(deps): bump chromadb from 0.5.3 to 1.5.9 |
| #32 | `dependabot/pip/sentence-transformers-gte-3.0.0` | build(deps): update sentence-transformers requirement from <4.0,>=3.0.0 to >=3.0.0,<7.0 |
| #31 | `dependabot/github_actions/actions/download-art` | build(deps): bump actions/download-artifact from 4.3.0 to 8.0.1 |
| #30 | `dependabot/github_actions/actions/checkout-7.0` | build(deps): bump actions/checkout from 4.4.0 to 7.0.1 |
| #29 | `dependabot/github_actions/actions/setup-python` | build(deps): bump actions/setup-python from 5.6.0 to 7.0.0 |
| #28 | `dependabot/github_actions/actions/upload-artif` | build(deps): bump actions/upload-artifact from 4.6.2 to 7.0.1 |
| #27 | `dependabot/github_actions/softprops/action-gh-` | build(deps): bump softprops/action-gh-release from 2.6.2 to 3.0.3 |
| #25 | `audit/kernel-v1-remaining-freezing-blockers-48` | Audit remaining freezing blockers for OCBrain Kernel v1.0 |

## 16. Relevant Information / References

- `PROJECT_INSTRUCTIONS.md` (§18.4.8/18.4.9 handoff & recovery; §23 branch/commit rules). `KNOWN_ISSUES.md` (register; highest `DEBT-` id on `main` at handoff: **DEBT-041** — verify live). `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md` (maintained by other sessions; can lag).
- `docs/Bugs Hunt & fix reports/PACKET_{C,D,E,F,G}_*` — prior packets (on `main`). `DEBT-030…036` are this engagement's rows.
- CI: `.github/workflows/ci.yml` (`tests` gates on new failures vs `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`; `drift-and-ownership` runs `scripts/check_drift.py`); branch protection on `main`: `tests` + `drift-and-ownership`, strict, admins exempt.
- API: `GET /repos/1h0lde4/ocbrain-v4.1/{code-scanning/alerts, code-scanning/analyses?ref=refs/heads/main, dependabot/alerts, pulls}`.
- **Context.** Moncif (`1h0lde4`, also commits as "N4Z") owns the repo and decides; terse "Continue" = go ahead. Packets C→G of the Kernel v1.0 freeze audit are complete and merged (PR #26). **Other Claude sessions land PRs on `main` constantly.** Conventions: register-check before tracing; prove with a test or a trace, don't assert; long explanatory commit messages; separate commits per logical change; push immediately.

## 17. Next Steps

1. **Verify the transfer** (§18); read this file fully; confirm the §14 environment (rebuild if the container reset).
2. **Re-run the freshness checks on `origin/main`** (it will have moved):
   a. `git show origin/main:core/privacy.py` — is R6 still unguarded? any `module_child`?
   b. `git grep -nE "wipe_module_data|wipe_all" origin/main` — still zero production callers?
   c. `git log origin/main --oneline -15` and the open-PR list — has anyone started R6/R7/the manifest?
   **If R6 has been fixed upstream, record that and skip to step 5.**
3. **Merge `origin/main` into the branch**; verify `KNOWN_ISSUES.md` per-row (grep every `| DEBT-NNN |` from both parents — don't trust "clean"); run full suite + drift; revert `config/` & `data/context.sqlite`; commit + push (use the gating script pattern: commit only if rows ✓ suite ✓ drift ✓).
4. **R6, exploit-first** — new file `tests/test_privacy_wipe_containment.py`, or a sink entry in `tests/test_module_name_containment.py` if its structure fits (read it first). Sketch (**verify the class/singleton names**):
   ```python
   def test_wipe_module_data_cannot_delete_outside_data_dirs(tmp_path, monkeypatch):
       import core.privacy as priv
       fake = tmp_path / "fake_repo"
       (fake / "core").mkdir(parents=True)
       (fake / "data" / "raw" / "legit").mkdir(parents=True)
       (fake / "data" / "chunks" / "legit").mkdir(parents=True)
       decoy = fake / "decoy_dir"; decoy.mkdir(); (decoy / "keep.txt").write_text("x")
       monkeypatch.setattr(priv, "__file__", str(fake / "core" / "privacy.py"))   # function reads Path(__file__)
       assert (fake / "data" / "raw" / "../../decoy_dir").resolve() == decoy.resolve()   # self-check: not passing for the wrong reason
       try: priv.PrivacyGuard().wipe_module_data("../../decoy_dir")                      # or the module's singleton
       except Exception: pass
       assert (decoy / "keep.txt").exists()
   ```
   **Watch it FAIL on the current code** (that is the proof), add a positive control (`"legit"` is still wiped from both dirs), then fix.
5. **R6 fix:** replace the raw join with `module_child(<root>/folder, module_name)` (read `core/module_paths.py` first for exact semantics, including how it treats a not-yet-existing child — the current code guards with `p.exists()`). Fail closed: an invalid name must raise before anything is deleted. Run the file, then the full suite and drift. Commit; **push immediately**.
6. **R7 sweep, destructive sinks first:** list every `shutil.rmtree`, `os.remove`, `unlink`, `rmdir`, `shutil.move/copytree`, `open(..., "w")`, `extractall` in production code and trace each argument's origin. Also non-module-name identifiers (`execution_id`, rollback/update names). Record results in the working notes; prove any real finding with a failing test first.
7. **Brief Moncif** on U1–U4 (the Dependabot/chromadb tension especially).
8. **PR for this branch:** `git rm handoff.md`; re-merge `main`; open a PR; wait for the 5 checks (`tests`, `drift-and-ownership`, `CodeQL`, `Analyze (python)`, `Analyze (actions)`); **merge only on his instruction.**
9. **Freeze-manifest — only with his go-ahead, after reading PR #25 and `CURRENT_STATE.md`.** A fresh, evidence-first reconciliation of the register against live `main`: `DEBT-032…036` statuses, R6/R7 outcomes, CTX-AUTH-001b (implemented upstream), ADR-KERNEL-07 (proposed), `DEBT-025` (unauthenticated control plane), `DEBT-033` (admin bypass), the chromadb CVE question, and the Kernel v1.0 verdict. Same discipline: verify against live state.

## 18. Resume Instructions

1. `git fetch origin`; confirm `security/codeql-findings-sep2026` exists on the remote at the transfer commit `8d62d98cf10b048ed67d15f8765be30485b9c509` plus the handoff commit.
2. Verify the remote branch contains `handoff.md`.
3. Compare this file's claims with the live repo/APIs. **If they disagree, the repo wins — correct this file** (§18.4.9).
4. Resolve mismatches before changing code.
5. Begin at §17 step 2.

## 19. Transfer Status

**TRANSFER READY** — all finished work is pushed and verified, the unfinished work is fully specified with an exploit-first test sketch, and the first action is exact.

Not defects: the branch is behind `main`; R6 is intentionally unfixed (handoff instruction); no PR is open.
