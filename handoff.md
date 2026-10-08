# Session Handoff — ADR-KERNEL-07 (creative content-anchor detector): live draft-plan evidence, repeated runs, merge governance

> Branch `handoff/adr-kernel-07-live-check-oct2026` holds this file and **one preserved artifact**
> (`handoff/premerge_guard.py`, see §8). It is a transfer record, **not** an authority, and must **not** be merged into
> `main` (PROJECT_INSTRUCTIONS §18.4.8.10). Verify everything below against the live repository before relying on it
> (§18.4.9). **No secrets are recorded here; the GitHub token is deliberately omitted** (handling in §14).
> A different workstream's handoff exists at `handoff/codeql-remediation-sep2026` (another session); it is unrelated except
> that both sessions act on the same fast-moving `main`.

## 1. Handoff Metadata
- Handoff version: 1
- Created at: 2026-10-05T21:30Z by the sandbox clock (`main`'s `CURRENT_STATE.md` shows syncs dated Oct 5, 2026)
- Workstream: ADR-KERNEL-07 — creative content-anchor detector (slice 1, flag **off**): live draft-plan evidence → repeated runs → containment decision → merge/reconcile
- Identifiers: PR **#41** (merged), PR **#45** (open, frozen by instruction), PR **#61** (draft); ADR `docs/architecture/decisions/ADR_KERNEL_07_CREATIVE_CONTENT_ANCHOR_DETECTOR.md`
- Source session purpose: study `OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md` → implement → resolve D-5 → merge → obtain live evidence → build repeated-run tooling
- Transfer status: §19

## 2. Original Starting Prompt
Verbatim, the entire task text: **`study then start implementation`**

Attachments in that first message (referenced, not reproduced):
- `OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md` — committed **unmodified** at `docs/studies/OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md` (byte-identity was audited).
- `PROJECT_INSTRUCTIONS.md` (OCBrain v4.x governing contract; tracked at `PROJECT_INSTRUCTIONS.md` and `docs/architecture/PROJECT_INSTRUCTIONS.md`) — **read it first**; §18.4.8–18.4.9 define this handoff and its recovery.
- A project file `github.env` containing a GitHub token — **not reproduced; see §14.**

## 3. Subsequent User Instructions / Corrections
Messages marked *(review)* were pasted by Moncif as review text; he then acted on or confirmed them. Exact wording is kept where it governs.

1. *(review)* "I would **not let Claude implement this ADR unchanged yet**." Four issues: gate placement vs the study; `WorkflowRuntime.resume()` treated as established; stateless slice vs `clarification_attempt` semantics; lexical signal vs material sufficiency. "**Do not call Slice 1 a general Intent Sufficiency solution. Call it the first narrow detector/vertical slice toward that capability.**"
2. *(review)* D-5 must be answered "from repository evidence", options A (amend DRIFT-10), B (another existing seam), C (detect early, decide at the existing gate), D (pure Intent-level, no governance).
3. **Moncif, decision:** "I choose Option C." Recorded verbatim in the ADR: "*Resolved: Option C. The content-anchor detector executes before planning as a pure, non-governing observation. Its result is carried through planning to the existing Plan Compilation boundary, where the existing OrchestrationGovernor evaluates it alongside ClarificationPolicy. No new clarification gate or new governance boundary is introduced. An ESCALATE result may surface a detector-specific clarification question, paired with the concrete interpreted plan/intent required by K4.2.*" "**Final architectural decision: C. No K4.2 supersession.**"
4. **Token:** "use token to update repo: [omitted]" → later "revoke before further use" → then Moncif: "**You can still use the token indefinitely until expired, the previous instruction was false**" → "now you can push and merge, use same token".
5. *(review)* Sequence: "D-1 → D-2 → D-3 → D-4 → live behavior check of draft-plan risk → final ADR reconciliation → merge decision." "I would not reopen D-5." The 16 FAILED + 8 ERROR sandbox failures "should stay explicitly characterized as pre-existing/untriaged."
6. *(review, confirming)* D-1 PROPOSED, D-2 PROPOSED, D-3 DEFERRED, D-4 DEFERRED, D-5 DECIDED, live behavior UNKNOWN. "I would **not** change the ADR further, change code, or add containment at this stage." "**'merge-ready' does not mean 'architecturally accepted'**."
7. *(review, after PR #41 merged)* Order: (1) close the merge-governance defect (guard fails hard + `enforce_admins`); (2) run `live_check_draft_plan.py`; (3) reconcile `CURRENT_STATE.md`/`KNOWN_ISSUES.md`/roadmap "from verified state rather than assumptions" **after** the live check; (4) keep failure accounting split; (5) then move on.
8. **Moncif:** "push the live_check_draft_plan.py --json live.json and all relevant files, i'll run it through codespace".
9. **Moncif:** results pasted, plus "yes, it was mistral, i've removed mistral and installed llama3 now, here are the new results:".
10. *(review)* Before the commit: state "22 attempts / 21 successful / 1 timeout"; preserve model identity; limits prominent; **separate** "hypothesis refuted" from "behavior desirable"; decide behavior independently of the experiment; "Merging it enables nothing" is too absolute. "I would choose B for the current slice: ask the clarification question and suppress the redundant plan payload/display." Sequence: "commit evidence + corrected ADR/validator → decide A/B/C/D → update tests → CI → then decide whether PR #45 becomes the accepted implementation."
11. **Moncif:** "do that on main or the branch?" (ambiguous; answered: never on `main`, which is protected).
12. **Moncif:** pasted `ollama show llama3` / `ollama list` output (tail first, then complete).
13. *(review)* "I would not merge PR #45 yet." "**Choose Option B: perform 2–3 additional harness runs.**" ⚠ **Naming collision:** here "Option B" = *repeated runs*; elsewhere "B" = the *containment* option "question only". Always say "repeated runs" / "containment B". "I would keep 5767066 untouched… **No merge, no Option B code changes to PR #45, and no ADR status change yet.**" The `live.json` timestamp check "is secondary… bundle it into the repeated-run capture."
14. **Moncif (this handoff):** "Update the done work to the repo, then create a handoff file for a fresh session to continue the remaining work."

## 4. Goal, Scope & Success Criteria
**Goal.** Bring ADR-KERNEL-07's slice 1 from "merged, flag-off, PROPOSED, with one-run evidence" to a *decided* state: evidence robust enough to choose a containment option, PR #45 resolved, state docs reconciled.
**In scope.** Repeated live runs and their comparison; recording evidence (evidence record + ADR §10.4); the containment decision (A–D) and, if chosen, its implementation as a **separate PR from `main`**; updating/merging PR #45 and #61 through the guard; reconciling state docs from verified state.
**Out of scope / do not touch without Moncif.** Accepting ADR-KERNEL-07 (status stays PROPOSED); enabling `creative_content_anchor_enabled`; D-3 (session identity / cross-turn lifecycle — its own future ADR) and D-4; editing the Constitution documents; the CodeQL workstream; fixing `_fts_escape` or the UX defects inside the experiment's PRs.
**Success.** (a) ≥2 valid repeated runs compared per the pre-registered protocol, with provenance, recorded honestly (PASS/FAIL/REVIEW as computed, thresholds not moved); (b) containment chosen **explicitly by Moncif** and implemented separately with tests/CI; (c) #45 updated from `main`, re-verified, merged via the guard — or consciously not; (d) `CURRENT_STATE.md`/`KNOWN_ISSUES.md`/roadmap updated from verified state; (e) ADR status changes only on Moncif's explicit acceptance.

## 5. Requirement Ledger
| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Study, then implement slice 1 ADR-first, flag-off | #0/§2 | VERIFIED | PR #41 merged (`ecddbff`); 75 tests + 1 strict xfail; drift 15/15; CI green | merged behind `creative_content_anchor_enabled=false` |
| R2 | Name it a narrow detector, not intent sufficiency | §3.1 | IMPLEMENTED | module/ADR renamed "Creative Content-Anchor Detector"; blind spots pinned in `TestKnownLimits` | |
| R3 | D-5 = Option C (no new gate; K4.2 preserved) | §3.3 | VERIFIED | ADR §10.3 verbatim; test: feature adds no governance evaluation | |
| R4 | ADR stays PROPOSED; merge ≠ acceptance | §3.6 | IMPLEMENTED | ADR status line; index row | Moncif-only to change |
| R5 | D-1/D-2 PROPOSED; D-3/D-4 DEFERRED | §3.6 | IMPLEMENTED | ADR §8 table | acceptance pending Moncif |
| R6 | Merge governance: guard fails closed + `enforce_admins` | §3.7 | VERIFIED | `premerge_guard.py` 25 self-tests, 8/8 mutations; protection diff: 1 of 12 fields changed | guard preserved in this branch |
| R7 | Run the live check; record evidence | §3.7–3.9 | IMPLEMENTED (not merged) | PR #45; llama3 run: 11 plans, median 7, 0 single-step | one run only |
| R8 | Evidence record accurate (attempts accounting, identity, limits, separated conclusions) | §3.10 | IMPLEMENTED (in #45) | commits `4c197fd`, `0526054`, `5767066` | |
| R9 | No containment until demonstrated/decided | §3.5–3.6 | OPEN | options A–D in the result record | Moncif decides |
| R10 | 2–3 repeated runs with provenance captured automatically | §3.13 | **tooling IMPLEMENTED; runs OPEN** | PR #61: 28 tests, 17 mutations; protocol pre-registered | needs Moncif's Codespace |
| R11 | Keep PR #45 head at `5767066` until the runs are done | §3.13 | IN FORCE | remote head `5767066` at handoff | lift only after the runs |
| R12 | Do not merge #45 on green CI alone | §3.10, 3.13 | IN FORCE | | |
| R13 | Reconcile state docs after the live evidence | §3.7 | OPEN (deliberately deferred) | `main`'s `CURRENT_STATE.md`/`KNOWN_ISSUES.md`/roadmap have **no** mention of this workstream | actively maintained by other sessions |
| R14 | Keep failure accounting split | §3.5,3.7 | IN FORCE | §6 | |
| R15 | Do not bundle `_fts_escape`, period-joining, story-specific examples into the experiment | §3.10 | IN FORCE | none fixed | track in `KNOWN_ISSUES.md` at R13 |
| R16 | Never store the token | handling | IN FORCE | token absent from repo/PRs/notes (greps) | |
| R17 | Push done work; write this handoff | §3.14 | see §19 | | |

## 6. Current Verified State
**VERIFIED**
- `main` = `8b0fee2659a21b0dc8e3ad28ffc1f8751b6faa0a`; contains PR #41's merge `ecddbff6968c55ed50661ef28caaef5bb1270bf4` (ancestor check passed). `creative_content_anchor_enabled = false` on `main` (`config/settings.toml:28`); `ollama_host` unchanged. Since PR #41 the only `config/settings.toml` change on `main` is an unrelated `import_root` comment.
- **The product code behind the live-check findings was unchanged on `main` since PR #41 as of `main`@`8b0fee2`** (⚠ **`main` has since advanced to `58d079f`; `core/orchestrator.py` changed in an unrelated region — see §15 item 11**): `core/orchestrator.py`, `core/cognitive/*`, `core/governance/*`, `scripts/live_check_draft_plan.py`, `core/provider_mesh.py`, `core/prompt`, `core/memory`, `core/config.py` — no diff. So run 1's findings still describe today's code.
- Branch protection on `main`: required checks `tests` + `drift-and-ownership`, **strict**, **`enforce_admins` ON**, force-push disallowed. Direct pushes to `main` are impossible; CI runs only for `pull_request` into `main` (and `push` to `main`, `h2/**`, `integration/**`), so a PR stacked on a non-`main` base gets **no CI**.
- PR #45 (`chore/live-check-runbook`) head `5767066`, CI green, open, **35 commits behind `main`**; PR #61 (`tools/live-check-repeat-runs`) head `258a58a46779a7f23ed3655953c8b74befe0fd9b`, draft, CI green. Both dry-run-merge **cleanly** into current `main` (`git merge-tree`, exit 0; no file overlap for #45 despite 30 files changed on `main` since its base).
- The first valid live run (details §13): llama3, 11 requests, 22 attempts = 21 successful + 1 timeout (request 1's *interpretation* call, irrelevant to the steps).

**IMPLEMENTED BUT NOT VERIFIED (against live behavior)**
- Everything in PR #61 has only been exercised with a fake harness/runner; **no live repeated run exists yet**.

**PROPOSED** — D-1 ("verify" = *Intent Verification*; asking the user is one mechanism), D-2 (flag stays off; enabling is a measured experiment); the ADR itself.
**DEFERRED** — D-3 (session identity / cross-turn state → own ADR), D-4 (Test D, strict `xfail`, depends on D-3).
**BLOCKED** — repeated runs: need Moncif's Codespace (Ollama + `llama3:latest`); no model provider exists in the authoring sandbox.
**UNKNOWN** — whether the structural findings are stable across runs; the containment choice; whether the run-1 model is unchanged since (`ollama list` said "37 hours ago"; run timestamp not captured); behavior under the **new CI test gate** (§15).

**Failure accounting (kept split).** In the authoring sandbox `main` shows 16 FAILED + 8 ERROR (24 IDs), identical with and without this work. The 16 FAILED are in **none** of `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`, yet CI was green → they are sandbox artifacts (pip hit "no space left on device") **under the CI gate as it was** — re-verify under the new gate (§15). The 8 collection ERRORs are uncharacterized. None is attributable to this work.

## 7. Git / Repository Checkpoint
- Primary repository: `github.com/1h0lde4/ocbrain-v4.1`; remote `origin`; base branch `main`
- This handoff's branch: `handoff/adr-kernel-07-live-check-oct2026`, cut from `main` @ `8b0fee2659a21b0dc8e3ad28ffc1f8751b6faa0a`
- HEAD before handoff (`main`): `8b0fee2659a21b0dc8e3ad28ffc1f8751b6faa0a`
- **Transfer commits** (the implementation state being transferred): `main`@`8b0fee2` (includes #41 merge `ecddbff`); PR #45 head `5767066` (commits `e701655`, `23531ab`, `d0aaa67`, `4c197fd`, `0526054`, `5767066`; base `4ab5345`); PR #61 head `258a58a` (one commit on `main`@`80a1bb8`)
- Handoff commit: the head of this branch (a file cannot contain its own hash); verify with `git ls-remote origin refs/heads/handoff/adr-kernel-07-live-check-oct2026`
- Parent commit of the handoff commit: `8b0fee2659a21b0dc8e3ad28ffc1f8751b6faa0a` (verify: `git rev-parse <handoff-head>^`)
- Working tree at handoff: clean except the two files this branch adds (`handoff.md`, `handoff/premerge_guard.py`)
- Relevant untracked/ignored: none required. Not preserved by design: mutation-test scripts that lived in `/tmp` (method in §12/§14), `/mnt/user-data/outputs/README-*.md` and `reconcile_audit.py` (superseded; `reconcile_audit.py`'s UNKNOWN assertions are obsolete)
- Submodules: none
- Push/verification status: see §19; always re-verify with `git ls-remote`

## 8. Active Files / Modified Files / Artifacts
**Merged to `main` (PR #41):** `core/cognitive/content_anchor.py` (pure detector; imports no governance — AST-tested), `core/cognitive/compiler.py` (additive keyword-only `content_anchor=None`, merged into the **existing** `plan_compile` action), `core/governance/orchestration_governor.py` (content-anchor rule, own key `content_anchor_score`, evaluated before `ClarificationPolicy`), `core/orchestrator.py` (CRLF; observe → carry → surface ESCALATE only when from `OrchestrationGovernor` **and** anchor missing), `main.py`, `config/settings.toml`, ADR + `ADR_INDEX.md` row, the study (unmodified), `scripts/live_check_draft_plan.py` (harness), `tests/core/cognitive/test_creative_content_anchor.py` (75 + 1 strict xfail), `tests/test_live_check_draft_plan.py` (17).
**PR #45 (open; evidence/runbook; docs+tests only; harness change is docstring-only, AST-proven):** `docs/studies/OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RUNBOOK_OCT2026.md` (procedure, validity checker, troubleshooting), `docs/studies/OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RESULT_OCT2026.md` (the evidence record: provenance, validity checks, 83-step table, reading, options A–D), ADR §10.4 + index row updated (UNKNOWN → OBSERVED for one model), `tests/test_live_check_runbook_validator.py` (8; extracts and runs the validator **from the runbook itself**), `scripts/live_check_draft_plan.py` docstring.
**PR #61 (draft; tooling):** `scripts/live_check_repeat.py`, `docs/studies/OCBRAIN_LIVE_CHECK_REPEAT_RUNS_PROTOCOL_OCT2026.md` (**pre-registered** criteria), `tests/test_live_check_repeat.py` (28).
**This branch:** `handoff/premerge_guard.py` — the fail-closed pre-merge guard. It was **only** in `/mnt/user-data/outputs`; it is required for safe merges (§14) so it is preserved here. Self-test: `python3 handoff/premerge_guard.py --self-test` → 25/25.

## 9. Changes Made
- **Behavior (merged, flag off):** detector → carried to the existing Plan Compilation gate → ESCALATE → response = request text (echoed) + ≤5 truncated draft-plan steps + a specific question. With the flag off nothing changes. **No new governance evaluation anywhere** (test: the sequence is identical on vs off).
- **Interfaces:** one additive keyword-only argument on `compile()`; additive `content_anchor_score` in the `plan_rejected` event; new events `cognitive.content_anchor_observed`, `orchestrator.clarification_requested`.
- **Governance/security:** `enforce_admins` enabled on `main` via the narrow endpoint (diff of the whole protection config: 1 of 12 fields changed; required checks and `strict` untouched). Verified the **setting**, never attempted a bypass.
- **Docs/evidence (#45):** see §8. **Tooling (#61):** see §8.
- **Not changed:** product code beyond PR #41; Constitution documents; `CURRENT_STATE.md`/`KNOWN_ISSUES.md`/roadmap; the ADR's status.

## 10. Decisions & Rationale
| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| DL1 | D-5 = Option C (pure pre-plan detector; decision at the existing compile gate) | **DECIDED** | Moncif | K4.2 doc "No dedicated clarification gate — reaffirmed"; `plan()` makes one unconditional model call; ADR §10 | only if Moncif explicitly supersedes K4.2 |
| DL2 | Slice 1 = narrow detector, not intent sufficiency; stateless, no bounded retry | IMPLEMENTED | reviews 1–2 | unreachable bound removed | when D-3 supplies an attempt carrier |
| DL3 | D-1/D-2 PROPOSED; D-3/D-4 DEFERRED | recorded | reviews (endorsed) | ADR §8 | Moncif's explicit acceptance/rejection |
| DL4 | No containment applied; options A (`plan_steps=[]`), B (question only), C (3-step cap + join fix), D (keep) | **OPEN** | Moncif | result record; reviews lean B | repeated runs + Moncif's explicit choice |
| DL5 | Containment, if any, goes in a **separate PR from `main`** (not on #45, not stacked) | PROPOSED | Claude, unconfirmed | stacked PRs get no CI; no file overlap | Moncif prefers one PR |
| DL6 | Merge only via the guard; never bypass; `enforce_admins` ON | IN FORCE | Moncif's sequence | incident §12 | none |
| DL7 | PR #45 frozen at `5767066` until the runs finish; not merged on green CI alone | IN FORCE | Moncif | §3.13 | runs done |
| DL8 | Tooling in its own draft PR #61 (harness unchanged) | IMPLEMENTED | Claude | keeps #45 untouched | |
| DL9 | Repeated-run criteria **pre-registered** (C1–C4, thresholds, lexicon) before any data | IMPLEMENTED | Claude | protocol doc; test pins doc ↔ code constants | any post-data change must be reported as post-hoc |
| DL10 | Handoff on its own branch, guard preserved beside it | IMPLEMENTED | Claude | follows the sibling handoff's convention | |

## 11. Investigation Already Performed
| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| K4.2 clarification decision | `docs/architecture/OCBRAIN_K4_2_…_AUTHORITATIVE.md` | "No dedicated clarification gate — reaffirmed"; evaluated at Plan Compilation | ADR §10.1 | K4.2 superseded |
| DRIFT-10/11 | `scripts/check_drift.py` | DRIFT-10 is a derived AST rule; DRIFT-11 restricts *importers*, not signatures | ADR §3 | drift rules change |
| `plan()` cost | `core/cognitive/planner.py` | one unconditional model call (`_decompose`); `compile()` none | ADR §10.2 | planner changes |
| `resume()` | `core/workflow/runtime.py` | needs a `WorkflowDefinition` + instance; N/A pre-plan and at compile | ADR §7 | a post-plan carrier is designed (D-3) |
| Entry governance | `core/orchestrator.py` | `handle()` opens with a request-authorization evaluation (`ORCHESTRATOR_ACTION_TYPE`) — authorization, not a clarification seam | ADR §10.2 correction | |
| Interpretation | `core/cognitive/intent.py:1090` | `structured_form["description"] = intent.raw_request`: the "interpretation" **is the request**; only real signal is the hypothesis category label | ADR §10.4 | Intent stage changes |
| Providers | `core/provider_mesh.py` | both modules → Ollama `localhost:11434`, model `llama3` by default; OpenAI-compat fallback has **no API-key support** and is fixed to `localhost:8080/v1`; only `{model,prompt,stream:false}` is sent → **sampling uncontrolled** | runbook, result record | provider changes |
| Prompt cache / memory | `core/prompt/cache.py`, `interpret_request` | cache in-process only; with no memory passed, falls back to the global singleton → a first run creates **empty** `.data/memory/{unified,archive}.db` (git-ignored; 0 rows) | measured in a scratch checkout | |
| FTS5 | `core/memory/backends/sqlite_storage.py::_fts_escape` | fails on **9 of 14** realistic queries against real SQLite FTS5 (`.`,`,`,`/`,`%`,`=`,`&`,`$`,`?`); quoting every token fails 0/14; documented only for `?` in `docs/reports/SESSION4B_REPORT.md` | reproduced; seen live on "Write a 500 word story." | fix PR |
| CI/protection | `.github/workflows/ci.yml` (as of `2e5cfc0`/`4ab5345`), protection API | triggers above; **gate semantics may have changed** (`scripts/ci_test_gate.py`, FZ-07/B9, Oct 4) | KNOWN_ISSUES.md on `main` | before relying on any CI-gate claim |
| State docs | `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, roadmap on `main` | actively maintained; **no** mention of this workstream | grep | before R13 |
| Run 1 | Moncif's console output | see §13; **not investigated:** the 60 s timeout's cause (cold start suspected) | | |
| Not investigated | the `Graphify` check seen on later PRs; run-1's `live.json`/`live.meta.txt` (never supplied); other models | | | |

## 12. Failed Attempts / Dead Ends
- **Pre-plan governed gate** (original slice 1): contradicts K4.2's reaffirmed decision → replaced by Option C. Do not reintroduce.
- **`resume()` as the clarification carrier:** not applicable (no workflow instance exists at detection or compile).
- **Bounded retry (`attempt`/`max_escalations`) in a stateless slice:** unreachable → removed.
- **Stacked PR on a non-`main` base:** no CI (`pull_request: branches: [main]`). Don't.
- **Inline "final guard" that printed but did not abort:** a stale-`main` PR merged because the token is admin and `enforce_admins` was off → **fixed** by `premerge_guard.py` + `enforce_admins`. (Merged content was then verified byte-for-byte; no harm.)
- **Validator heuristic "interpretation == request ⇒ failure":** wrong (it is the normal shape); would have rejected the first valid run. Fixed with a regression test; the test now extracts the snippet from the runbook.
- **"Touches no memory":** false (see §11); corrected in the harness docstring and runbook.
- **Mutation testing contaminated by stale bytecode:** same-size edits within one mtime second leave stale `.pyc` loaded. **Always** run mutation suites with `PYTHONDONTWRITEBYTECODE=1`, clear the module's `__pycache__` before each run, and require the unmutated baseline to pass first. The 9 Option C mutations behind the merged ADR claim were re-verified this way (all caught, identical counts).
- **My expectation of single-step "redundant" plans** and my claim that the plan input is "the interpretation, not the raw request": both wrong; corrected in the ADR.
- **My first call count (23)** was wrong; it is 22 attempts (21 + 1).
- **Shell gotchas that cost turns:** `/bin/sh` is plain `sh` (no `${v:0:7}`, `<(…)`, `PIPESTATUS`); nested heredocs with the same terminator break; a single tool command over 300 s is killed (bound CI-polling loops to ≤ ~160 s).

## 13. Verification Evidence
- PR #41 (merged): tests/drift/CodeQL green; scratch merge onto then-`main`: 0 conflicts, 12 files byte-identical; `+92` passing tests vs its parent with an identical failing-ID set (24, sandbox).
- Tests: `test_creative_content_anchor.py` 75 + 1 strict xfail; `test_live_check_draft_plan.py` 17; `test_live_check_runbook_validator.py` 8; `test_live_check_repeat.py` 28. Targeted regression on #61: **603 passed, 1 xfailed**; `check_drift.py` **15/15** everywhere run.
- Mutation checks (all caught by real assertions): Option C **9** (re-verified safely), harness **4**, runbook validator **2 + 1 added after a gap**, guard **8** (25 self-tests, incl. a replay of the real incident), repeat tool **17**.
- **Live run 1** (llama3 via Ollama, Codespace; console output only): LIVE, no `degraded` rows; 22 attempts = 21 ok (12.4–38.5 s) + 1 `TimeoutError` at 60,138 ms (request 1's interpretation call; the FTS5 warning's position after 12 calls corroborates the ordering). Steps per plan **7, 6, 7, 7, 5, 11, 5, 7, 9, 7, 12** (83 total, median 7, **0 single-step**, 9/11 over the 5-step display cap). No step names a concrete subject/genre/premise (one reader, Claude); most steps generic workflow; a minority presuppose form/process (character profiles/backstories, thesis + sources, "beta readers", "joke database/algorithm"). The harness's `speculative` label was **saturated 11/11 — not evidence**.
- **Model identity (post hoc, from Moncif):** `llama3:latest`, ID `365c0bd3c000`, 4.7 GB, arch `llama`, **8.0B**, ctx 8192, emb 4096, **Q4_0**, Meta Llama 3 (Apr 18, 2024) license. Valid for run 1 only if unchanged since.
- **Not verified:** any repeated run; stability across sampling; other models.
- Distinguish: passed / failed / skipped / blocked — the repeated runs are **blocked**; the 16+8 sandbox failures are **environmental/uncharacterized** (not product failures).

## 14. Environment / Tooling Assumptions
- **Authoring sandbox:** Linux, Python 3.12.3, **no model provider, no Ollama**; network allowlist includes `github.com`, `api.github.com`, PyPI; `pip install -r requirements.txt` previously hit ENOSPC (so some deps are missing → the 24 sandbox failures). `/bin/sh` only. 300 s per tool command.
- **Test-run churn (DEBT-012):** running the suite rewrites tracked `data/context.sqlite`, `config/models.toml`, `config/sources.toml`, `config/settings.toml`. **Before staging:** `git checkout -- data/context.sqlite config`, then `git add <explicit paths>` — never `git add -A` (it swept churn into a commit once). Check `git diff main -- config/settings.toml` shows only intended lines.
- **CRLF files:** `core/orchestrator.py`, `main.py`, some docs/ADR index — edit with Python preserving `\r\n`.
- **Codespace (Moncif):** Ollama serving `llama3:latest` (8.0B Q4_0, ID `365c0bd3c000`); `pip install -r requirements.txt`; the run writes git-ignored `.data/memory/*.db`; keep `live_runs/` out of git (the tool tries to add it to `.git/info/exclude`).
- **The GitHub token (value deliberately not recorded):** it lives in the project's `github.env`. Moncif authorised its use for this repo's pushes/PRs/merges ("valid until it expires"). It has **admin** scope and was exposed in chat — rotation is Moncif's call. Rules: never write it into any file, commit, PR body, note or memory; pass it per command only, e.g. `git -c http.extraheader="Authorization: Basic $(printf 'x-access-token:%s' "$TOK" | base64 -w0)" push …`, and mask it in output. If unsure whether it is still authorised, ask.
- **Merge procedure (required):** fetch → `python3 handoff/premerge_guard.py --repo 1h0lde4/ocbrain-v4.1 --pr N --expect-head <40-char sha> --require-enforce-admins` (dry-run; exit 0 only if open, not draft, head SHA matches, `mergeable_state` clean, head contains the base tip, every required check success) → only then `--merge` (merge commit, pinned SHA). Exit 1 = fix and re-verify; exit 2 = cannot verify. PRs behind `main` must be brought up to date (merge `main` in, re-verify) — never rely on admin override.
- **Concurrency:** other sessions merge to `main` continuously (35 commits in a few days). Re-fetch immediately before any decision; `main`'s state docs are being edited by others.

## 15. Unresolved Questions / Risks / Blockers
1. **Containment A–D** — open. Reviews and Claude's reading lean **B (question only)**; **never explicitly confirmed by Moncif**. Needs the repeated-run result first. Safe to continue other steps without it.
2. **Repeated runs** — blocked on Moncif's Codespace. Until then the findings rest on **one stochastic run** (sampling uncontrolled). Conclusions: "observed", not "robust".
3. **Is the run-1 model unchanged since?** — consistent with, not proof; the new batch records `ollama list` before/after, so future runs settle this.
4. **PR #45 is 35 commits behind `main`** and must be updated (merge `main` in) before it can merge; bringing it up to date brings the **new CI test gate** (`scripts/ci_test_gate.py`, FZ-07/B9). My earlier claim that CI "fails only on `FAILED` lines outside the known-environmental list; `ERROR`s are ungated" predates it — **re-read the gate before relying on that claim**, and re-check whether the 16 sandbox FAILED IDs still pass in CI.
5. **State-doc reconciliation (R13)** — `main`'s docs are silent on this workstream; they are also being edited by others → re-read before editing, keep edits minimal, verified-state only.
6. **Known defects not fixed:** `_fts_escape` (9/14 realistic queries; broader than SESSION4B's `?`); the response joins steps as "story.; 2."; the question's example text ("a noir mystery, a cozy fantasy…") is story-specific for every artifact kind; the "interpretation" line is an echo (ADR already says so). Track them in `KNOWN_ISSUES.md`; fix in separate PRs only if Moncif asks.
7. **ADR acceptance** — only Moncif; D-1/D-2 acceptance pending.
8. **Token exposure** — admin-scope token in chat transcripts; rotation pending Moncif.
9. **`Graphify` check** appears on newer PRs (not required, not investigated).
10. The repeat protocol's thresholds are **partly calibrated on run 0** (stated in the protocol); only C1 was an independent hypothesis.
11. **`main` moved after this handoff was cut** (cut from `8b0fee2`; `main` was `58d079f` when checked, via PR #63 / issue #62). The change touches `core/orchestrator.py` **only in the post-execution workflow-failure answer** (a failed workflow's raw error text is no longer returned; the answer is now `WorkflowFailure (ref …)`), plus `core/error_ref.py` and `tests/test_workflow_failure_disclosure.py`. I inspected the diff: it does **not** touch the content-anchor observe/carry/ESCALATE code or the compile-ESCALATE branch, so run 1's findings are not affected *as far as this diff shows* — but the earlier "unchanged since PR #41" claim no longer holds for `core/orchestrator.py`. Re-check per §18 step 3; `main` will keep moving. Dry-run merges of #45 and #61 against `58d079f`: both **clean**; #45 is now 38 commits behind, #61 is behind as well.

## 16. Relevant Information / References
`PROJECT_INSTRUCTIONS.md` (§0.3 status vocabulary; §16.5 closure criteria; §18.4.8–18.4.9 handoff/recovery) · ADR `docs/architecture/decisions/ADR_KERNEL_07_…` (§8 dispositions, §10 D-5 evidence, §10.4 live-check evidence) · `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` · `OCBRAIN_KERNEL_CONSTITUTION*.md` (line 99 = Invariant 1; RATIONALE §2 calls the "where genuinely ambiguous" qualifier an untested hedge; PRESSURE_TEST glossary: "verify" = Intent Verification) · `docs/reports/SESSION4B_REPORT.md` (FTS5 `?` gap) · `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt` · `.github/workflows/ci.yml`, `scripts/ci_test_gate.py` · the sibling handoff `handoff/codeql-remediation-sep2026`.
Important commands: `python scripts/live_check_draft_plan.py --json live.json` (single run); `python scripts/live_check_repeat.py run --runs 3 --out live_runs` / `compare live_runs/<batch_id>` (PR #61); `python scripts/check_drift.py` (expect 15/15).

## 17. Next Steps (in order)
1. **Verify state** (§18). Confirm `5767066` is still #45's head; if it moved, find out who moved it and why before anything else.
2. **Moncif runs the repeated batch** in the Codespace (this is the gating action):
   ```bash
   git fetch origin && git checkout tools/live-check-repeat-runs      # or main, once PR #61 is merged
   pip install -r requirements.txt
   ollama list        # must show llama3:latest, ID 365c0bd3c000 (if not, STOP and report)
   python scripts/live_check_repeat.py run --runs 3 --out live_runs   # ~7–8 min/run; preflight aborts a bad setup
   python scripts/live_check_repeat.py compare live_runs/<batch_id>
   ```
   Do not edit config or pull/remove models during the batch. Send back the whole `live_runs/<batch_id>/` directory (`meta.json`, `run*.json`, `report.md`, `compare.json`).
3. **Fresh session:** validate the batch (≥2 valid runs; model id unchanged; commit/dirty recorded). Report the **C1–C4 verdicts exactly as computed**; do not move thresholds (any change = post-hoc, reported with the original verdicts). For REVIEW, read the printed steps.
4. **Record the evidence** (this lifts the "keep #45 untouched" constraint, only after step 3): merge `main` into `chore/live-check-runbook` (dry-run is clean today), re-verify, then update the result record (runs, provenance, stability) and ADR §10.4. No ADR status change.
5. **Ask Moncif to choose containment A–D explicitly.** If a change is chosen: separate branch from `main` → code + tests only (`core/orchestrator.py`, `tests/core/cognitive/test_creative_content_anchor.py`) → CI → draft PR. For B: pass `plan_steps=[]` and drop the echoed interpretation; update `TestClarificationResponse` and the orchestrator "question and plan" test; consider the artifact-specific example text and join fix as separate items.
6. **Decide merges via the guard**: #45 (after 4) and #61 (tooling; decide whether it belongs on `main`).
7. **Reconcile state docs from verified state:** add this workstream to `CURRENT_STATE.md` (ADR-KERNEL-07 merged, flag off, PROPOSED), `KNOWN_ISSUES.md` (`_fts_escape` breadth, the UX defects, the unrepeated-run caveat if still true), roadmap as appropriate. Re-read the files on `main` first.
8. Only then consider moving on from ADR-KERNEL-07.

## 18. Resume Instructions
1. `git fetch origin`; read `PROJECT_INSTRUCTIONS.md` §18.4.8–18.4.9 and this file completely.
2. Verify, don't trust: `main` head and that `ecddbff` is its ancestor; `git ls-remote` for `chore/live-check-runbook` (expect `5767066`), `tools/live-check-repeat-runs` (expect `258a58a…`) and this handoff branch; PR states (#41 merged, #45 open, #61 draft); branch protection still requires `tests` + `drift-and-ownership`, strict, `enforce_admins` on.
3. Re-check what moved: `git log --oneline 8b0fee2..origin/main`; whether `core/orchestrator.py`, `core/cognitive/*`, `core/governance/*`, `core/provider_mesh.py` or the harness changed (if yes, the run-1 findings need re-qualifying); whether `CURRENT_STATE.md`/`KNOWN_ISSUES.md` now mention this workstream.
4. Resolve any material mismatch with this handoff **before** changing anything; correct this file if the repository contradicts it.
5. Begin at §17 step 2 (or step 3 if Moncif has already returned a batch).

## 19. Transfer Status
**TRANSFER READY** — conditional on the remote check in §18 step 2 (handoff branch head on the remote equals the local head). Implementation checkpoints are pushed (`main` contains #41; #45 head `5767066`; #61 head `258a58a`); the only outside-repo artifact needed (`premerge_guard.py`) is preserved on this branch; the next action (the repeated batch) is defined with exact commands. Everything not in the repo is documented and reproducible: the repeated runs are the *next action itself*, not missing state.
