# Session Handoff — DEBT-042 / DEBT-043 remediation (ADR-KERNEL-07 response path)

> This file lives on the temporary branch `tmp/debt-042-043-checkpoint-oct2026` together with the owner's directive
> (`handoff/directive_verbatim.md`) and the two patch files (`handoff/patches/`). It is a transfer record, **not an authority**,
> and the branch must **never be merged into `main`** (PROJECT_INSTRUCTIONS §18.4.8.10). Verify everything below against the live
> repository before relying on it (§18.4.9). **No secrets are recorded here.** An older handoff for the earlier ADR-KERNEL-07
> workstream exists on `handoff/adr-kernel-07-live-check-oct2026`; it is **stale** and must not be revived.

## 1. Handoff Metadata
- Handoff version: 3 (v2 rewrote a first draft lost with the sandbox, see §12; v3 records the successful push and a refreshed live preflight of 2026-11-15)
- Created at: sandbox clock `2026-11-15T16:42Z` (UTC)
- Workstream: ADR-KERNEL-07 response-path remediation — **DEBT-042** (FTS5 literal queries) and **DEBT-043** (truthful, bounded clarification response), under the owner's *Final Remediation Directive*
- Governing task text: `handoff/directive_verbatim.md` (two messages; part 1 is cut off mid-sentence in §3.4, part 2 completes it; part 2's **§5.4 is a proposed replacement specification**, not recovered original wording)
- Source session purpose: live preflight, then the three deliverables (decision-record PR, DEBT-042 PR, DEBT-043 PR), all unmerged, with evidence for independent review
- **Transfer status: `TRANSFER READY`** (§19): the temporary branch `tmp/debt-042-043-checkpoint-oct2026` is pushed and verified on the remote (the first push attempt, made without a credential, had failed — §7). The work is also preserved in a git bundle and patches delivered to the owner as session outputs.

## 2. Original Starting Prompt
The directive, verbatim: **`handoff/directive_verbatim.md`** (parts 1 and 2). Read it first and in full; this handoff summarizes it, it does not replace it. Material properties of the text: part 1 ends mid-sentence ("Do not add"); §5.4 is a *proposed replacement*; the directive forbids merging, force-pushing, enabling the detector by default, declaring freeze readiness, and requesting or exposing credentials.

## 3. Subsequent User Instructions / Corrections
1. "Continue" (several times): proceed with the directive without asking the owner to repeat decisions it already contains.
2. Part 2 of the directive supplied ("this is the continuation to the prompt").
3. "Update the finished work to the repo, then create a handoff file so we can resume the remaining work in a fresh session."
4. **Latest:** "Push the work to a temporary branch then create the handoff file."
Standing owner decisions that bear on this workstream (do not re-open): K4.2 pairing retained for this response path; containment option **C-plus** selected for implementation (owner-directed, dated 2026-10-19; A, B, D not selected); D-5 architectural "Option C" (2026-09-29) is a *different* decision and unchanged; ADR-KERNEL-07 stays **PROPOSED**; DEBT-042 and DEBT-043 stay **OPEN** until a later closure PR; nothing is merged in this task.

## 4. Goal, Scope & Success Criteria
**Goal.** Complete the narrow remediation of DEBT-042 and DEBT-043 and reconcile the records, with evidence sufficient for independent review and eventual closure.
**In scope.** (1) decision-record PR (PR #88 exists remotely); (2) DEBT-042 implementation+test PR; (3) DEBT-043 implementation+test PR — separately scoped, independent of each other and of the documentation PR.
**Out of scope.** D-5 placement, governance sequence, K4.2 text, ADR status, D-1..D-4, debt statuses in the code PRs, a new semantic-validation subsystem, any added model call, the separate G4 FTS work (§11).
**Success (directive §9).** Three separately scoped, reproducible deliverables; behaviour matches the recorded disposition; real integration boundaries exercised; docs no longer present superseded decisions as current; limitations explicit. Implementation, verification, acceptance, closure and freeze readiness are separate states.

## 5. Requirement Ledger
| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Live preflight before editing | §2 | **VERIFIED on 2026-10-19 and refreshed on 2026-11-15; must be repeated before opening PRs** | §6, §11 | `main` is now `6f93444…`, 148 commits past the base; 17 open PRs, none touching the code files in scope |
| R2 | Decision-record PR | §3.3 | **IMPLEMENTED, remote only**: PR #88, branch head `e634c41…` (re-read with `git ls-remote` on 2026-11-15); CI green + guard dry-run OK on 2026-10-21 | §15 | **conflicts with current `main`** (CURRENT_STATE.md, KNOWN_ISSUES.md); needs a §5.4-status follow-up |
| R3 | DEBT-042 implementation + tests | §4 | **IMPLEMENTED + VERIFIED locally** (commit `14481bf…`); **no PR** (no credential) | §13 | patch applies to the base and to current `main` |
| R4 | DEBT-043 implementation | §5 | **IN PROGRESS**: production code in WIP commit `6d56b93…`; tests not written; **16 existing tests fail** | §6, §15 | |
| R5 | §5.5 tests 1–12 via the real Orchestrator | §5.5 | **OPEN** | — | list in §17 step 4 |
| R6 | Evidence per deliverable | §7 | DEBT-042 done locally; DEBT-043 OPEN; **remote CI for both OPEN** | §13 | |
| R7 | Independent review packages | §8 | **OPEN** | — | reviewer ≠ author session |
| R8 | No merge / no force-push / never request or expose credentials | §1 | **IN FORCE** | — | |
| R9 | Closure-documentation PR | §1 | **NOT STARTED** | — | only after authorized merges + post-merge verification |
| R10 | Keep PR #88's ADR §10.5 truthful about §5.4 | §5.4 | **OPEN** | §15.3 | it says the safe-failure response is "specified by the owner's directive (§5.4)" without saying it is a proposed replacement |

## 6. Current Verified State
**VERIFIED**
- Remote `main` = `6f93444769587a62fd79279fff6de3f140600222` (GitHub API + `git fetch`, 2026-11-15); the directive's base `f13bfde…` is **148 commits behind** (an earlier read the same day saw `2491ae4…`; `main` keeps moving). On current `main` DEBT-042 is OPEN; the DEBT-043 row was already updated by another session (commit `383dbb6`, 2026-11-02) to "C-plus selected by owner on 2026-10-19 (recorded in unmerged PR #88); implementation/verification remain OPEN". **PR #88 is not merged** (its head is not an ancestor of `main`) and ADR §10.5 is **not** on `main`.
- DEBT-042 candidate `14481bfa27ba89c21c5f53cc401385a41798e425` on base `f13bfdefcdd197ed1f966de0b1f93037a4168af4`: evidence in §13 (re-run after the sandbox reset).
- `git merge-tree` dry-runs of both code branches **and** the temp branch into `6f93444`: **clean** (2026-11-15); both patches `git apply --check` cleanly on the base and on `6f93444`. `main`'s diff to `core/orchestrator.py` since the base does **not** touch the content-anchor/clarification region (0 changed lines match), and its change to `core/cognitive/planner.py` (CTX-AUTH-002) is constraint extraction only, not `_decompose`'s degrade fallback. The merged result was **not** tested.
**IMPLEMENTED BUT NOT VERIFIED** — DEBT-043 production code (§9). Observed only: ad-hoc rendering for story/essay/joke and the degrade fallback; **16 tests fail** (§15.2); nothing else run.
**PROPOSED** — §5.4 safe-failure wording (owner's proposed replacement); the intent-statement, plan-header and per-artifact question wording are **the author's**, not owner-specified.
**BLOCKED** — remote writes (§19). **UNKNOWN** — remote CI of any candidate (none was triggered: the temp branch has no PR); behaviour of the merged candidates on `6f93444` (not tested); whether `main`'s 148 new commits change the planner's/orchestrator's behaviour in ways the diff scan above would not show.

## 7. Git / Repository Checkpoint
- Repository `github.com/1h0lde4/ocbrain-v4.1`, remote `origin`, base branch `main`; recorded base for both code branches `f13bfdefcdd197ed1f966de0b1f93037a4168af4`.
- Branches (the two `fix/…` branches exist only in the sandbox and in the bundle; **on the remote only the temporary branch exists** — verified with `git ls-remote`):
  | Branch | Commit(s) | Content |
  |---|---|---|
  | `fix/debt-042-fts5-literal-query-oct2026` | `14481bfa27ba89c21c5f53cc401385a41798e425` | DEBT-042, complete (3 files) |
  | `fix/debt-043-truthful-clarification-response-oct2026` | `6d56b933d0cc3e95c96a65ccfa6788793dab617e` | DEBT-043 **WIP** (2 production files) |
  | `tmp/debt-042-043-checkpoint-oct2026` (the "temporary branch") | `59579e5` (DEBT-042, cherry-pick), `dd77a81` (DEBT-043 WIP, cherry-pick), then the handoff commit (head of the branch — `git rev-parse` it) | both pieces stacked, **for preservation only, never for a PR** |
- Transfer commits (the implementation state being transferred): `14481bf…` and `6d56b93…` (identical file contents to `59579e5`/`dd77a81`). The handoff commit's parent is `dd77a81`.
- Working tree at handoff: clean apart from what the temp branch adds. Tests rewrite four tracked files (§14); they were restored with `git checkout --` before every commit.
- **Remote push status.** 1st attempt (no credential available): `GIT_TERMINAL_PROMPT=0 git push origin tmp/debt-042-043-checkpoint-oct2026:refs/heads/tmp/debt-042-043-checkpoint-oct2026` → `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. 2nd attempt, after the owner explicitly instructed the session to use the project token (value not recorded here): API credential check HTTP 200 (login `1h0lde4`); the same push **succeeded** (`new branch`). **Remote verification:** `git ls-remote origin refs/heads/tmp/debt-042-043-checkpoint-oct2026` returned `1c4cd99715b43382852056f417ec579a7e05efa8`, equal to the local head at that time (the handoff v2 commit; this v3 update is a later commit on the same branch — its pushed head is whatever `git ls-remote` returns now). The credential was used only per command with masked output; **it should be rotated once no longer needed** (it had been flagged as exposed earlier in the project). An unrelated remote branch `tmp/b03-ci-remediation-handoff-20261112` belongs to another session.
- Preserved outside the repository (§18.4.8.13): `ocbrain-remediation.bundle` (the three branches, prerequisite `f13bfde`), `0001-DEBT-042-fts5-literal-queries.patch`, `0002-WIP-DEBT-043-c-plus-response.patch`, `directive_verbatim.md`, `handoff.md`, `SHA256SUMS.txt` — delivered as session outputs; the patches and the directive are also committed on the temp branch.

## 8. Active Files / Modified Files / Artifacts
**DEBT-042 (`14481bf`)** — `core/memory/backends/sqlite_storage.py` (**CRLF file**; `import re`, constant `_FTS_UNBINDABLE_CHARS`, `_fts_escape` rewritten + documented contract; `search_text`/schema/triggers/ranking untouched); `tests/test_debt042_fts5_literal_queries.py` (new, 61 tests); `tests/test_session4b_memory_hardening.py` (one test rewritten, D8).
**DEBT-043 WIP (`6d56b93`)** — `core/cognitive/content_anchor.py` (LF; the clarification-response section at the end of the file replaced); `core/orchestrator.py` (**CRLF**; import + the ESCALATE-surfacing block).
**Not yet touched but required (§15.1):** `scripts/live_check_draft_plan.py`, `scripts/live_check_repeat.py`, `tests/test_live_check_draft_plan.py`, `tests/test_live_check_repeat.py`.

## 9. Changes Made
**DEBT-042.** Every whitespace-separated token becomes one double-quoted FTS5 string with embedded `"` doubled; NUL and lone surrogates removed; still an SQL bound parameter. Semantics (in the docstring): tokens stay implicitly AND-ed; plain words match as before; a token the tokenizer splits (`file.txt`, `C++`) matches as an adjacent phrase; punctuation-only tokens add no terms (FTS5 treats an empty phrase as neutral inside an AND) and a query with no terms matches nothing; empty/whitespace-only queries keep the established unfiltered contract (handled in `search_text` before escaping). **One intentional semantic change:** bare `AND`/`OR`/`NOT`/`NEAR` are now literal terms, not operators.
**DEBT-043 (WIP).**
- `render_clarification_response(assessment, *, request_text="", plan_steps=()) -> ClarificationRendering(text, paired, steps_shown, steps_total, failure_reason)`; `build_clarification_response` is a thin string wrapper; its old `interpretation=` keyword is **replaced** by `request_text=` (used only to recognise the planner's degrade fallback; never displayed).
- Intent statement derives only from detector data ("I understand this as a request for a story. It doesn't say what the story should be about."); the raw request is **not** echoed as an "interpretation" (by K4.2-H1 `structured_form["description"]` *is* the raw request).
- Plan: ≤ `_MAX_STEPS_SHOWN = 3` (was 5) genuine steps, separate numbered lines, plan order, header `Provisional draft plan (not checked or approved; not yet tailored to a subject; first N of M steps):`; no padding; list markers stripped; omitted steps stated as omitted.
- Genuine plan: non-string/empty steps skipped; **planner degrade fallback detected** — `planner._decompose` answers a failed/unparsable model call with ONE step equal to the goal description (or `"unspecified"`); that is the request echoed back, so it counts as *no genuine plan*.
- Question: artifact-specific for the detector's real vocabulary (story, poem, essay, song, joke) + generic fallback; no story-specific example; no "is enough" claim (the detector needs ≥ 2 content tokens); keeps the real `"surprise me"` way-out (backed by `_DELEGATION`) and the stateless "send it again" instruction (D-3).
- Safe failure: `SAFE_FAILURE_MESSAGE` = the owner's proposed wording; `failure_reason` ∈ {`no_usable_intent`, `no_usable_plan`}.
- Orchestrator: render **first**; paired → existing event `orchestrator.clarification_requested` (+ additive `plan_steps_shown`, `plan_steps_total`) and the paired text; not paired → existing event `orchestrator.query_failed` (`error_type="ClarificationPairingUnavailable"`, reason code only) and the safe-failure text. `execution_plan.steps` is read via `getattr`/`list(… or [])` so a missing plan cannot raise. No new governance evaluation, gate, model call or outcome type; everything before the block is unchanged.

## 10. Decisions & Rationale
| ID | Decision | Status | Authority | Reopen condition |
|---|---|---|---|---|
| D1 | K4.2 pairing retained; C-plus selected (A, B, D not) | DECIDED | owner directive §3.2 (2026-10-19) | owner revises |
| D2 | D-5 architectural Option C stays; no new gate | DECIDED | ADR §10.3 (2026-09-29) | owner supersedes K4.2 |
| D3 | DEBT-042: quote **every** token, double `"`, strip NUL/surrogates, keep AND semantics | IMPLEMENTED | author, from probes on real SQLite 3.45.1 | owner prefers other semantics |
| D4 | `AND/OR/NOT/NEAR` become literal terms (the single intentional semantic change) | IMPLEMENTED — **needs owner awareness** | author; directive §4.1 forbids silent operator behaviour | owner wants operator support |
| D5 | Punctuation-only / no-term queries match nothing; empty queries keep the unfiltered contract | IMPLEMENTED | author; preserves the prior effective result (no L1 candidates) without an error | — |
| D6 | DEBT-043: intent statement from detector data; no raw-request echo | WIP | author; directive §5.1 | owner wants other wording |
| D7 | Degrade-fallback plan = "no genuine plan" (single step equal to the request or `unspecified`) | WIP | author; directive §5.2/§5.4 | a `PlanStep` provenance flag appears |
| D8 | The test that pinned the old `?` limitation asserted only `"?" in escaped` (true for broken and fixed code); replaced by a real FTS5 check and renamed | IMPLEMENTED | author | — |
| D9 | Safe failure is a presentation failure reported with the existing `query_failed` event, not a new outcome | WIP | author; directive §5.4 "smallest justified change" | owner prefers another event/outcome |
Do not let a fresh session silently re-litigate D1/D2 (owner decisions).

## 11. Investigation Already Performed
| Area | Result | Revisit trigger |
|---|---|---|
| FTS5 semantics (real SQLite 3.45.1, production table shape) | an empty phrase is neutral in an AND; only NUL and lone surrogates still break a quoted token; no expression-depth limit up to 1000 tokens; an undoubled embedded `"` was a real bug | SQLite version change |
| `search_text` contract | empty/whitespace query → unfiltered, by importance; filters/ranking/deprecation unchanged | — |
| Callers | `UnifiedMemory.search` is the only production caller of `search_text` (its callers: `intent.py:1386`, `learning.py:354`, `retrieval/graphrag/pipeline.py:102`, `scripts/integration_check.py:84`); its L1 FTS5 leg has a broad `except` (non-blocking warning) — **unchanged and tested** | — |
| CI | `pytest tests/ -q --tb=short`, then `scripts/ci_test_gate.py` with `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`; ubuntu-latest, Python 3.12 | — |
| Open-PR overlap | 2026-10-19 (11 open PRs): #81 edits `KNOWN_ISSUES.md` next to the DEBT-043 row; #83/#79 conflicted with `main` on it; no branch/PR addressed either debt. **Refreshed 2026-11-15 (GitHub API, 17 open PRs):** the only overlap with the files this workstream touches is `KNOWN_ISSUES.md` (#107, #102, #91, #83, #81, #79) and, for the docs PR, #88 itself; **no open PR touches** `core/orchestrator.py`, `core/cognitive/content_anchor.py`, `core/memory/backends/sqlite_storage.py`, `core/memory/unified_memory.py`, the harness/repeat tool or their tests; no existing branch/PR addresses DEBT-042/043 other than #88's documentation | repeat before opening PRs |
| G4 FTS correctness (other session; branches `docs/g4-fts-correctness-handoff-rev3-oct2026`, `docs/g4-fts-errata-handoff-oct2026`) | a **different** workstream (stale postings / ghost rows after delete, migration safety) in the same file area; docs-only branches; it says DEBT-042 is a distinct issue; DEBT-042's diff touches only `_fts_escape`, one import and one constant | if G4 starts editing `sqlite_storage.py` |
| Planner fallback | `planner._decompose` returns ONE step = goal description (or `"unspecified"`) on a failed/unparsable model call | planner change |
| Orchestrator ESCALATE block | `handle()` returns `str`; events `orchestrator.clarification_requested` / `orchestrator.query_failed`; the SupervisorWorker invoke before the block is unchanged | **`orchestrator.py` changed on `main` — re-read** |
| Not investigated | runtime effect of `main`'s 148 new commits on either path; remote CI | |

## 12. Failed Attempts / Dead Ends
- **The sandbox filesystem was reset twice during this task.** The first set of local commits (`7602d27…` DEBT-042, `ad21824…` DEBT-043 WIP) and the first handoff draft were lost; everything was **recreated from the session's own text with identical content** (the DEBT-042 patch is byte-for-byte the same size, 25467 bytes) and re-verified (§13); the commit SHAs above are the new ones. Lesson: persist artifacts to the outputs folder immediately.
- `pip install -r requirements.txt` in the foreground (> 270 s) times out and a `nohup … &` background install is killed when the tool call ends. What worked: install in groups — `pytest pytest-asyncio`; the light packages; `chromadb==0.5.3` (four test modules import it at collection); then **`scipy>=1.11,<1.14`** (chromadb pins `numpy<2`; the latest scipy needs numpy ≥ 2 and breaks collection with `numpy has no attribute 'long'`).
- `/bin/sh` is plain `sh`: no `time`, `<(…)`, `$'\r'`, `${v:0:7}`. `cut -c` splits multibyte UTF-8 (tool error "not valid UTF-8"); pytest output may contain NUL (`grep -a`).
- A first `_fts_escape` edit via a string trick corrupted the function's last line; fixed by writing the tail explicitly (always `ast.parse` and print the tail).
- My first NEAR test expectation was wrong (`NEAR(cats dogs)` splits on whitespace into `NEAR(cats` and `dogs)`, i.e. the phrase "near cats" AND "dogs").
- Anonymous GitHub API calls from the sandbox are rate-limited; use `git ls-remote`/`git fetch` for read-only checks.

## 13. Verification Evidence
**DEBT-042 — candidate `14481bf…`, base `f13bfde…`; Python 3.12.3, SQLite 3.45.1, pytest 9.2.0, pytest-asyncio 1.4.1, chromadb 0.5.3, scipy 1.13.1, numpy 1.26.4.** All re-run after the second sandbox reset.
| Check | Result |
|---|---|
| New tests on the **unmodified** code (pre-fix reproduction, real FTS5) | **37 of 61 fail**; of the original 14 queries **9 fail** (indices 2,3,4,5,7,8,9,10,13: `Write a 500 word story.`, `what's the capital of France?`, `tell me a joke, please`, `python 3.11 vs 3.12`, `50% of users`, `cost = $5 & tax`, `path /home/user/file.txt`, `user@example.com`, `re: meeting notes; agenda`) |
| Same tests on the fix | **61 passed** |
| Memory test files (new + `test_session4b…` + `test_session4c…`) | 134 passed |
| Full suite, baseline `main f13bfde` (`pytest tests/ -q --tb=short`) | **exit 0 — 2072 passed, 1 xfailed** (54.3 s) |
| Full suite, candidate | **exit 0 — 2133 passed, 1 xfailed** (50.3 s): +61; the strict D-4 `xfail` preserved |
| CI gate, locally (`scripts/ci_test_gate.py --output … --exit-code-file … --allowlist docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`) | exit 0: "Test gate passed: no unlisted failures, no errors, exit code acceptable." |
| `python scripts/check_drift.py` | exit 0; 30 PASS lines, 0 FAIL lines |
| Tracked files rewritten by the test run (DEBT-012 churn): `data/context.sqlite`, `config/models.toml`, `config/sources.toml`, `config/settings.toml` | **mutated** (hashes differ before/after); restored with `git checkout --` before committing; no other untracked files besides the new test |
| Dry-run merge into current `main` | clean (merged result not re-tested) |
| Remote CI | **NOT RUN** (no push possible) |
**DEBT-043 WIP (`6d56b93…`):** `tests/core/cognitive/test_creative_content_anchor.py` + `tests/test_live_check_draft_plan.py` + `tests/test_live_check_repeat.py` → **16 failed, 138 passed, 1 xfailed** (exact list in §15.2). Nothing else run.

## 14. Environment / Tooling Assumptions
- Python 3.12; SQLite ≥ 3.45 with FTS5; packages as in §12. `core/orchestrator.py` and `core/memory/backends/sqlite_storage.py` are **CRLF** (a plain `str.replace` that writes LF rewrites every line); `content_anchor.py` and the tests are LF.
- Tests are async (`@pytest.mark.asyncio`); fixtures: `SQLiteStorageBackend(str(tmp_path/…/unified.db))`, `KnowledgeEntry(entry_id, layer, content, importance, created_at, updated_at, accessed_at, …)`, `UnifiedMemory(db_prefix=str(tmp_path/…))`; the L1 warning logger is `ocbrain.memory.unified`. Orchestrator test helpers (`TestOrchestrator`, `_plan()` building a real `ExecutionPlan`) live in `tests/core/cognitive/test_creative_content_anchor.py` — re-read them first.
- No credential is available; do not request one (directive §1).

## 15. Unresolved Questions / Risks / Blockers
1. **DEBT-043 breaks two other callers (observed):**
   - `scripts/live_check_draft_plan.py:187` calls `ca.build_clarification_response(` with the removed `interpretation=` keyword → the live-check harness breaks. Options: update the call to `request_text=` (recommended; the harness then measures the new response) or keep a deprecated, ignored `interpretation=`.
   - `scripts/live_check_repeat.py:60` has `DISPLAY_CAP = ca._MAX_STEPS_SHOWN`; changing the product cap to 3 would **silently change the pre-registered C2 criterion** ("≥ 7 plans over the 5-step cap"). The experiment's cap is historical and must stay 5: decouple (`DISPLAY_CAP = 5`, with a comment) and update the pinning test deliberately; declare this tooling change in the DEBT-043 PR.
2. **16 tests fail on the WIP** (verified 2026-11-15): `tests/core/cognitive/test_creative_content_anchor.py` — `TestClarificationResponse::test_pairs_interpretation_and_plan_with_a_specific_question`, `…::test_degrades_to_the_bare_question_without_context`, `…::test_model_text_is_flattened_truncated_and_capped`, `TestOrchestrator::test_a_form_only_request_is_answered_with_question_and_plan` (they pin the old text); `tests/test_live_check_draft_plan.py` — `TestOfflineSelfTest::test_profiles_land_where_designed[single-redundant|generic-generic|speculative-speculative]`, `…::test_offline_output_is_always_marked_not_evidence`, `…::test_shown_to_user_is_the_real_response_builder_output`, `TestLiveModeHonesty::test_all_degraded_live_run_is_never_evidence`, `…::test_healthy_live_run_is_evidence`, `…::test_main_exits_2_when_live_run_is_not_evidence`, `…::test_main_exits_0_offline`; `tests/test_live_check_repeat.py` — `test_real_worker_in_offline_mode_is_isolated_end_to_end`, `test_protocol_document_matches_the_tools_constants`, `test_constants_stay_in_sync_with_the_product_and_the_supplied_run`. Directive §5.5: do not weaken/delete/skip — **replace each pinned assertion with a stronger assertion of the new behaviour** and say so in the PR.
3. **PR #88** (open, unmerged) conflicts with current `main` in `CURRENT_STATE.md` and `KNOWN_ISSUES.md` (dry-run 2026-11-15; `main`'s DEBT-043 row was meanwhile reconciled by commit `383dbb6`), and its ADR §10.5 says the safe-failure response is "specified by the owner's remediation directive (§5.4)": it must say it is a *proposed replacement specification, not recovered original wording*, and record the implemented wording after DEBT-043 lands.
4. `main` moved 148 commits (it keeps moving); the dry-run merges are clean and `core/orchestrator.py`'s changes avoid the clarification region, but merged-result testing has **not** been done for either candidate.
5. The intent-statement/plan-header/question wording is the author's; the degrade-fallback detection is an equality heuristic (no provenance flag on `PlanStep`) — both need independent review. Residual product risk (recorded in ADR §10.5 on PR #88): displayed planner steps can still be generic or presuppose an unrequested process; C-plus does **not** validate them.
6. G4 FTS correctness (other session) may later edit `sqlite_storage.py`.
7. The project credential file no longer exists; the push of 2026-11-15 used the token on the owner's explicit instruction. Remote writes need an access path the **owner** provides — the session must not ask for one — and the token should be rotated when the work no longer needs it.
Continuing the DEBT-043 PR without resolving 1–2 is **not** safe; DEBT-042 can proceed independently.

## 16. Relevant Information / References
`handoff/directive_verbatim.md` · `PROJECT_INSTRUCTIONS.md` (§0.3, §16.5, §18.4.8–18.4.9) · ADR `docs/architecture/decisions/ADR_KERNEL_07_CREATIVE_CONTENT_ANCHOR_DETECTOR.md` (§10.3 D-5; §10.4 evidence and the Oct-17 correction; §10.5 exists only on PR #88) · `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` · `docs/studies/OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RESULT_OCT2026.md` · `docs/studies/OCBRAIN_LIVE_CHECK_REPEAT_RUNS_PROTOCOL_OCT2026.md` · `KNOWN_ISSUES.md` DEBT-042/043 · `core/cognitive/planner.py::_decompose` · the merge guard `handoff/premerge_guard.py` on `handoff/adr-kernel-07-live-check-oct2026` (merges only through it and only with explicit owner authorization — none is authorized here). Earlier workstream (merged): PRs #41 (`ecddbff`), #61 (`4b90ed9`), #45 (`3f8ef97`), #85 (`ef426e9`), #82 (`f13bfde`).

## 17. Next Steps (execution order)
1. **Verify state** (§18): refs, open PRs (heads/files/checks), overlaps with #86/#83/#81/#79 and anything newer, branches mentioning the debts.
2. **Create the PR branches from the pushed temp branch** (no bundle needed): `git fetch origin tmp/debt-042-043-checkpoint-oct2026`; make `fix/debt-042-fts5-literal-query-oct2026` by cherry-picking `59579e5` onto current `main`, and `fix/debt-043-truthful-clarification-response-oct2026` by cherry-picking `dd77a81` onto current `main` (their file contents equal the recorded `14481bf…`/`6d56b93…`). Pushing needs owner-provided access; do not ask for credentials in-session.
3. **DEBT-042:** merge/rebase onto current `main`; re-run the 61 new tests, the memory files, the **full suite + CI gate + `check_drift.py`** on the merged candidate; record the new tested SHA, counts and before/after hashes; open the PR (contract, pre-fix 9/14 reproduction, post-fix evidence, semantic change D4, residual risks); do **not** touch DEBT-042's status; request independent review.
4. **DEBT-043:** merge `main` into the WIP branch; re-read the ESCALATE block; resolve §15.1; replace the pinned tests (§15.2); write the §5.5 tests **through the real Orchestrator** with controlled doubles — (1) >3 steps → first 3 in order; (2) 1/2/3 steps, no padding; (3) empty and missing plan → safe failure, no detector question, `query_failed` event; (4) malformed step data (None, ints, empty strings); (5) absent/empty/unusable intent (assessment None / not in scope / empty artifact); (6) each artifact kind + generic fallback, no invented premise; (7) degrade-fallback single step equal to the request → safe failure, no echo-as-interpretation; (8) formatting (no `.; 2.`, no `1. 2.`, no empty entries); (9) flag disabled unchanged; (10) flag enabled follows the established path with no extra governance evaluation (the existing test must still pass); (11) other escalation causes never produce a content-anchor question; (12) events and terminal outcome (`clarification_requested` + additive keys on success; `query_failed` on failure); keep the strict D-4 `xfail`. Then full suite + gate + drift + before/after hashes; replace the WIP checkpoint with a reviewable commit (new commit, no history rewriting on shared branches); open the PR; do **not** touch DEBT-043's status.
5. **Independent review packages** for both PRs (directive §8). The reviewer must not be the author session.
6. **PR #88 follow-up** (docs only): update against current `main` (resolve CURRENT_STATE.md / KNOWN_ISSUES.md), state in ADR §10.5 that §5.4 is a proposed replacement, keep both debts OPEN and the ADR PROPOSED; no merge without the owner's explicit authorization via the guard.
7. **Closure-documentation PR** only after authorized merges and post-merge verification.

## 18. Resume Instructions
1. `git fetch origin`; read `PROJECT_INSTRUCTIONS.md` §18.4.8–18.4.9, `handoff/directive_verbatim.md` and this file completely.
2. Verify, don't trust: `git ls-remote origin refs/heads/main` (last seen `6f93444…`); that the temp branch `tmp/debt-042-043-checkpoint-oct2026` is on the remote (`1c4cd99…` or later); if it is not, restore the work from the bundle (`git bundle verify ocbrain-remediation.bundle && git fetch ocbrain-remediation.bundle 'refs/heads/*:refs/heads/*'`, needs `f13bfde` locally) or `git am` the patches; PR #88's head (`e634c41…` at last check).
3. Re-run the mechanical checks of §6/§13 on whatever you restored before relying on them. Rebuild the environment first if needed (§12, §14).
4. Resolve any material mismatch with this handoff first and correct this file if the repository contradicts it.
5. Begin at §17 step 1; do not reconstruct completed work (DEBT-042 is done locally; DEBT-043 production code exists as a WIP commit).

## 19. Transfer Status
**TRANSFER READY**
The temporary branch `tmp/debt-042-043-checkpoint-oct2026` — carrying the DEBT-042 candidate (`59579e5`, content-identical to `14481bf…`), the DEBT-043 WIP checkpoint (`dd77a81`, content-identical to `6d56b93…`), the owner's directive, the patches and this handoff — is pushed and verified on the remote (see §7). All material work is represented in Git on the remote; the exact next action is defined (§17); a bundle and patches are additionally delivered as session outputs. "Ready" means *recoverable and documented*, not *finished*: DEBT-042 awaits its PR and independent review, DEBT-043 is a WIP with 16 failing existing tests, and remote CI has not run on either. The branch is a transfer artifact and must never be merged.
