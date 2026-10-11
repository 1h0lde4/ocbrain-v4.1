# Session Handoff

> Read first. **Handoff version 3, refreshed 2026-10-11** (documentation-only refresh of version 2, commit `275fc03`, which is preserved in git history). Everything the owner asked for in this workstream is **merged and verified on `main`** (through `1d813bd`); nothing material exists only locally. What remains is **owner-run and pending by decision**: the dependency compatibility study, then one consolidated registry update covering Dependabot alerts #1-#7 (§17b). Sections below keep their version-2 content; what changed is marked **[v3 update]**. Live repository state outranks this file wherever they differ (§18).

## 1. Handoff Metadata

- Handoff version: 3 (documentation-only refresh of version 2, commit `275fc03`, preserved in git history). Version 2 covered the session that began from `handoff/codeql-remediation-sep2026` @ `20ad523`; that earlier handoff remains the record for its own scope and was not modified.
- Created at: 2026-10-07 (UTC; see the commit timestamp of this file). Version 3 refreshed 2026-10-11 (UTC; see the commit timestamp of the version 3 commit).
- Workstream: security-finding remediation continuation. CodeQL `py/path-injection` closure (PRs #46, #56), DEBT-037 follow-up (PR #63), registry reconciliation (PRs #58, #66), dependency-alert decisions (issues #65, #70).
- Task identifiers: PRs #46, #56, #58, #63, #66 (merged); #44 (closed, superseded); issues #54, #62 (closed, completed), #65 and #70 (open). Added in version 3: PRs #73 and #74 (merged); Dependabot alerts #1-#7 (open, inventoried).
- Source session purpose: continue the CodeQL/Dependabot remediation from the pushed handoff, under the owner's step-by-step authorizations. Version 3 additionally covers the continuation in which the owner ruled on #70 and #65, authorized PRs #73 and #74, and ruled on Dependabot #5-#7 (S16-S20).
- Transfer status: see §19.

## 2. Original Starting Prompt

The first message of the session was the full text of `PROJECT_INSTRUCTIONS.md` (OCBrain v4.x; the repository copy is `docs/architecture/PROJECT_INSTRUCTIONS.md`, also at the repo root) followed by the task prompt below, preserved **verbatim**. The saved user preference in that message carried a credential; its value is intentionally not reproduced here.

```text
You are continuing an OCBrain repository workstream from a pushed handoff.
Repository:
`github.com/1h0lde4/ocbrain-v4.1`
Start by establishing live state. Do not trust stale documentation, prior summaries, or this prompt over the repository, remote branches, PR state, CI, and actual tests.
Current known baseline:

* `main`: `4ab5345`
* Handoff branch: `handoff/codeql-remediation-sep2026`
* Handoff commit: `20ad523`
* The handoff was corrected after a fresh state re-check.
* The handoff is the authoritative transfer artifact for this workstream, but live repository state outranks it where they differ.

Important completed state:

* PRs #34 through #39 merged.
* PR #40 merged: updater error text.
* PR #42 merged: `/modules/new` 400 install-path issue.
* PR #43 merged: register step that had previously appeared pending.
* No merge was performed in the immediately preceding session.
* Three URL-substring CodeQL alerts were dismissed as "used in tests".
* One `extractall` CodeQL alert was dismissed as a false positive.
* Open CodeQL findings currently reported: 29 `py/path-injection` alerts, with no other open rule.
* PR #44 changes `/import` path handling and currently has a failing CodeQL check. It was not authored or modified by the preceding session. Do not touch it until ownership is explicitly established.

Known decisions/background:

* The correct debt reference from the preceding session is `DEBT-038`, not `DEBT-039`.
* The previously claimed zip-slip vulnerability was retracted after direct validation; do not resurrect that claim.
* The handoff records other investigated dead ends and the exact test baseline/commands.

Open decisions requiring investigation before implementation:

1. What should be done with the 29 remaining `py/path-injection` findings?
2. Should the `_safe_extractall` helper remain, and if so, what is its justified contract?
3. Should `module_name` be validated in every shared primitive, or only at the appropriate trust boundary?
4. How should the Dependabot `chromadb` alerts be handled given that:
   * the project intentionally pins `chromadb==0.5.3`
   * there is currently no patched version satisfying the relevant alert
   * the pin is deliberate, not accidental

Untraced areas:

* `PlannerWorker.WorkerResult.error`
* `crawler` / `cleaner` / `gap_detector` call paths
* an apparently unused webhook model in `core/brain_api.py`

Required operating protocol:

1. Read the handoff completely.
2. Verify remote/main/branch/PR/CI state before drawing conclusions.
3. Check `KNOWN_ISSUES` and relevant canonical architecture/decision documents before proposing fixes.
4. Treat code, actual tests, CI, and repository state as higher authority than stale docs.
5. Distinguish PROPOSED from accepted decisions.
6. Do not modify unrelated work.
7. Do not touch PR #44 until ownership is established.
8. Do not make a vulnerability claim without reproducer/evidence.
9. Do not merge anything without the established merge-governance process and green required checks.
10. Preserve the exact test baseline from the handoff and report deltas rather than inventing a new baseline.
11. Before making implementation changes, produce a concise investigation/disposition for each open decision.
12. Work in a dedicated branch; do not commit directly to `main`.
13. At the end of the session, produce a complete handoff if continuation remains necessary.

Transfer requirement:
A fresh Claude session must obtain the current transfer token from the coordinator before proceeding beyond initial live-state verification. Do not invent a token and do not reuse an old one.
The first useful output should be a verified state report plus a disposition table for the four open decisions and the three untraced areas. Do not start fixing findings merely because they appear in CodeQL.
```

## 3. Subsequent User Instructions / Corrections

Chronological. Quotation marks mean exact wording; "extraction" means a faithful condensation (the full text lives in the conversation, and the binding parts are recorded in the issues/PRs named).

| # | Instruction (owner) | Effect |
|---|---|---|
| S1 | Extraction: **"Work only on PR #46 (`acc43b7`) and only on the `module_child()` findings raised by Graphify."** Reproduce the nested-symlink case and the loop case on every testable Python (3.11/3.12 vs 3.13); compare to the documented direct-child contract; smallest change; loops must become the fixed `InvalidModuleName`; regression tests for ordinary / `my-module` / alias-to-sibling / nested / outside / loop / hostile / suffix; re-run the full PR suite and the combined #44+#46 trial merge. Acceptance included: **"Do not claim CodeQL is fixed; CodeQL must be treated as unverified until a fresh analysis confirms it."** | PR #46 fix (`53cf604`). |
| S2 | **"Always Use the saved token"** (the saved token had returned 401). Later in the session: a replacement credential was pasted by the owner (value not recorded). During the #46 reconciliation: **"Do not use, store, or reproduce any credential/token. Any credential previously exposed should be rotated separately."** Later: **"You can always keep using the token, stop writing the warning."** | Credential handling (see §14). The latest instruction governs: keep using the supplied credential; do not repeat warnings. |
| S3 | **"Proceed with option 2 once."** Reshape the path barrier to string `os.path.realpath` plus `candidate.startswith(base + os.sep)`, fold the `os.stat()` loop probe into the validated flow, preserve semantics, regression tests, commit only if correct, plain fast-forward push; report SHA / files / tests / CodeQL / whether alerts disappeared, decreased or merely moved. **"Do not dismiss any CodeQL alert yet. If this single reshape attempt still leaves the alerts, stop and report the evidence."** | `a3e97e0`. |
| S4 | Reconcile #46 with current `main` safely: verify head/base/main/clean tree first, update through GitHub's update-branch (no force, no rewrite), verify ancestry, unchanged meaning, tests, CI. **Do not merge yet.** | `30b584a`. |
| S5 | **"I would now authorize merge #46, with one condition: merge the exact current head 30b584a…."** Then six post-merge steps (main points to the merge commit; #46 merged; merged tree contains the reviewed files; wait for fresh `main` CodeQL; report whether the 29 alerts reduced; **"Do not claim those 29 are resolved until GitHub's post-merge analysis actually shows it."**). | Merge `a21711e`. |
| S6 | Do only the #44 re-evaluation: no code changes, no merge; do not infer #12 resolved from textual overlap; "require fresh CodeQL evidence"; report ownership, blockers, evidence needed. | #44 report. |
| S7 | **"#44 is superseded. Do not repair, update, merge, or dismiss anything on #44."** Close it only as a disposition (do not alter its code); leave alert #12 open; create a new **explicitly owned** work item for `/import` on baseline `80a1bb8`; record five accepted design decisions **before** implementation (see D-54 in §10); scope discipline (no module-name work, no `PlannerWorker`, no `chromadb`, no unrelated API/config change, no alert dismissal); required evidence incl. fresh CodeQL on the final commit and before/after alert accounting. **"#12 is considered fixed only if a fresh CodeQL analysis of the final commit no longer reports that alert and does not replace it with equivalent/new path-injection findings."** Docs update only afterwards, in a separate PR. | #44 closed, #54 created, PR #56. |
| S8 | **"Change brain_export.py and brain_api.py to LF, so the whole project use one type."** | Mechanical LF commit `4934f91` (only those two files; see §9). |
| S9 | **"Continue"** / **"Continuer"** (several times). The session's practice: when the owner had been asked for an explicit go-ahead on a named exact head, "Continue" was treated as that go-ahead (done for #56 at `f43df2e`); otherwise "Continue" meant proceed with the stated next step. When in doubt, ask for exact-head authorization. | Operating interpretation. |
| S10 | **"Merge #58."** plus ruling **D58: ACCEPT, merge PR #58 as-is**, and: after #58, keep two workstreams separate: (1) PlannerWorker error leak: reproduce, establish exact contract, minimal fix, mutation/regression verification; (2) DEBT-032 (`chromadb`): **"make a boundary/architecture decision first; do not install or alter dependency behavior merely to make the debt disappear."** **"I would not reopen or merge #44 as part of this cleanup."** | #58 merged (`710917c`). |
| S11 | Decision 1: **"Approve and merge #63."** Decision 2 (DEBT-032): keep `chromadb==0.5.3`, document the boundary as embedded-only with a reopen trigger, split the `pyproject.toml` range into its own item, **"Do not dismiss the Dependabot alerts yet."** Sequence: merge #63; re-run `main` verification/CodeQL; close DEBT-037 against the merged commit; record the DEBT-032 decision and reopen trigger; open the separate Chroma hygiene item; then the registry-doc PR; **"Leave the K4.2 empty-answer gap untouched; it is correctly scoped as a separate issue."** | #63 merged (`58d079f`), #65 created, PR #66 opened. |
| S12 | **"Do a reconcilliayion first before merging #66"** | Reconciliation; four corrections to #66's own text (R1-R4 in §11). |
| S13 | **"Merge #66 at `8284149`."** **"Give alert #4 its own work item."** **"After merge, do the post-merge verification against the resulting `main` and record the final commit/check/alert state."** Also: "the remaining limitation, no raw CI log counts, is explicitly disclosed rather than presented as fact." | #66 merged (`73faf22`), issue #70 created. |
| S14 | Owner's state summary: **"The clean sequencing from here is #70 exposure assessment first, while #65 remains a separate dependency-policy decision. No dependency upgrade or security dismissal should be inferred from the current evidence."** | #70 assessment posted (comment). |
| S15 | **"Push the finished work to repo and prepare a handoff file to resume work in a new session"** | This file. |
| S16 | #70: **"i lean towards 1 and 3, we'll be doing a study later on to see the compatible versions of all requirements"**. #65: **"pin it for now, once the study is done we'll update it too"** | Recorded as owner decisions on issues #70 and #65 (`issuecomment-6096538561`, `issuecomment-6096538690`) before any implementation; #65 implemented as PR #73. |
| S17 | **"Ok for 1,2 and 3"**, answering three items: (1) merge PR #73 at exact head `c9662cd`; (2) open the narrow registry PR afterwards; (3) open a work item for the K4.2 empty-answer gap | (1) PR #73 merged `77e2e82`. (2) PR #74 opened (head `3569399`). (3) **Not executed as a new item:** the gap is already registered as FZ-01 (§10 D-FZ01), and a duplicate would contradict the project's no-duplicate-findings rule (§24.1 of `PROJECT_INSTRUCTIONS.md`). Reported to the owner; the owner has not asked for a separate GitHub issue. |
| S18 | **"Continue"** | Taken as the go-ahead for the exact head `3569399` that had just been named (practice S9). Required checks `tests` and `drift-and-ownership` and head sha were verified first; PR #74 merged `1d813bd`. |
| S19 | Extraction (full wording is in the conversation; the binding parts are recorded in issue #65 comment `issuecomment-6109033966`): **"fold #5–#7 into the consolidated registry update after the study. Do not create a separate registry note now, and do not dismiss any alerts."** Reasons given: #5-#7 are distinct alert records (one per advisory per manifest) and are to be inventoried individually; the registry update must cover alerts #1-#7 (advisory IDs, affected manifest paths, statuses, the existing ChromaDB disposition) and preserve earlier evidence and decision history; the creation time and PR #73's merge are consistent with `pyproject.toml` having become resolvable to Dependabot, to be recorded as the likely explanation and not as a proven mechanism. Required outcome: all seven alerts open and undismissed; the embedded-only ChromaDB decision unchanged; no duplicate issue; the update explicitly accounts for #5-#7 and distinguishes verified facts from inference. **Condition:** **"if the post-study registry update is no longer going ahead, add a short dated interim note instead. The alert inventory should not remain knowingly incomplete while the team treats it as authoritative."** | Recorded in the #65 comment; nothing else changed. |
| S20 | Extraction: bring this handoff up to date now, **limited to documentation and verified project state**; revalidate the baseline first (`main` still `1d813bd`); reconcile §17 explicitly (completed, superseded or still pending, with evidence) while preserving historical decisions; record the security state by reference to the #65 inventory comment, keeping verified facts separate from the unconfirmed explanation; preserve the outstanding decisions (the study as prerequisite, D-032, the #70 decision, FZ-01 blocked on D1); **no code changes, registry updates, new issues, alert dismissals or unrelated workstream changes; do not claim the compatibility study is complete**; afterwards report the exact commit or file revision, sections changed, evidence checked and unresolved §17 steps. | This refresh (version 3). |

Standing rules that came up repeatedly (treat as binding): no merge without the owner's explicit go-ahead for an exact head; merge with the GitHub `sha` guard; update-branch only on a PR the session owns and only when asked; never dismiss a CodeQL or Dependabot alert without a recorded owner decision; keep workstreams separate; claim "fixed" only from a fresh analysis.

**[v3 update] Added standing rules (S19, S20):** do not dismiss any of Dependabot #1-#7; do not create a separate registry note, issue or alert action for #5-#7 before the study unless S19's fallback condition applies; never claim the compatibility study is complete without the owner's evidence; a documentation refresh changes documentation only.

## 4. Goal, Scope & Success Criteria

### Goal
Carry the owner's two open decisions to a recorded outcome without conflating them: **#70** (is the repo exposed to CVE-2026-68770 via `sentence-transformers`, and what to do) and **#65** (make the declared `chromadb` constraint truthful). Keep the K4.2 and registry follow-ups separate.

### In Scope
Presenting the #70 assessment and its options for an owner decision; recording the decision; later registry follow-ups; opening a work item for the K4.2 gap if the owner wants one; any dependency change **only after** a recorded owner decision.

### Out of Scope
Dismissing any alert; merging Dependabot PRs #32/#33 as a side effect; touching other PRs (#25, #45, #61 and the Dependabot PRs #27-#31; #67 and #71 from other sessions have already merged); reopening #44; `PlannerWorker` or `/import` code (closed); line-ending normalization of other files unless asked.

### Success Criteria
Owner decision on #70 recorded (issue comment and, afterwards, a narrow registry PR); #65 resolved by an owner-chosen form with a check that pins the agreement; Dependabot #1-#4 dispositions only per recorded decisions; every claim backed by fresh evidence.

**[v3 update]** Both goals above are met: the #70 verdict and the #65 form are recorded (S16) and #65 is implemented as PR #73. Success criteria now in force: (a) the consolidated registry update, after the owner's compatibility study, accounts for Dependabot alerts #1-#7 per S19; (b) until then all seven alerts stay open and undismissed; (c) the `chromadb` pin, the `sentence-transformers` upgrade direction and the Dependabot PRs #32/#33 are revisited only with that study's results and an explicit owner decision.

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | `module_child()` result is a direct child of root after canonicalization; nested/outside targets rejected | S1 | VERIFIED | PR #46 merged `a21711e`; 54 helper tests on Python 3.11-3.14 | alias to a sibling is accepted and returns the canonical target (documented) |
| R2 | Loops/resolution failures raise only `InvalidModuleName` | S1 | VERIFIED | same tests; 45-scenario differential, 0 divergences, positive control 11 | `Path.resolve()` stopped raising on loops in 3.13 |
| R3 | CodeQL barrier reshaped once; alerts accounted | S3 | VERIFIED | `a3e97e0`: 0 results (was 1 on `acc43b7`, 2 on `53cf604`) | |
| R4 | #46 reconciled with `main` without rewrite | S4 | VERIFIED | `30b584a`, tree `e0017db1...` equals GitHub's merge-ref tree | |
| R5 | #46 merged at the exact head; post-merge verification | S5 | VERIFIED | `main` analysis of `a21711e`: 28 of 29 fixed, #12 open | |
| R6 | #44 re-evaluated read-only, then closed as superseded | S6, S7 | VERIFIED | closing comment on #44; branch untouched at `c53cecc` | its CodeQL: alerts #38, #39 |
| R7 | Owned work item with D1-D5 recorded before implementation | S7 | VERIFIED | issue #54 (closed, completed) | |
| R8 | `/import` boundary; #12 fixed only by fresh analysis | S7 | VERIFIED | PR #56 merged `41fa85a`; `main` analysis 2026-10-05T07:31Z: #12 `fixed`, 0 open | |
| R9 | `brain_export.py`, `brain_api.py` converted to LF | S8 | VERIFIED | commit `4934f91`; blobs equal base with CRs stripped | other files untouched |
| R10 | Registry docs in a separate PR after a definitive state | S7 | VERIFIED | PR #58 merged `710917c` | |
| R11 | PlannerWorker leak: reproduce, contract, minimal fix, mutation/regression | S10, S11 | VERIFIED | issue #62, PR #63 merged `58d079f`; 3 of 8 tests fail pre-fix; 7 mutants caught | DEBT-037 CLOSED for the traced set (register, #66) |
| R12 | DEBT-032 decision recorded (embedded-only, reopen trigger) | S11 | VERIFIED | PR #66 merged `73faf22` | Dependabot #1-#3 left open |
| R13 | Separate hygiene item for the `pyproject.toml` range | S11 | VERIFIED (item created) | issue #65 | [v3 update] the fix itself is VERIFIED: PR #73 merged `77e2e82` (exact pin, owner's form per S16); #65 stays open as the revisit tracker |
| R14 | Reconcile before merging #66 | S12 | VERIFIED | four corrections R1-R4 (§11), pushed `8284149` | |
| R15 | Alert #4 gets its own work item; assessment | S13, S14 | VERIFIED (item and assessment posted) | issue #70 + comment `issuecomment-6061327562` | [v3 update] owner decision RECORDED (S16): option 1 now plus option 3 as unscheduled direction, `issuecomment-6096538561`; alert #4 stays open |
| R16 | Post-merge verification recorded | S13 | VERIFIED | §13 | |
| R17 | K4.2 empty-answer gap kept separate and untouched | S11 | VERIFIED untouched | `core/orchestrator.py` K4.2 branch unchanged | [v3 update] CORRECTION: the gap is the already-registered FZ-01 (OPEN, BLOCKED on D1), so a tracked item does exist; no duplicate was created (§10 D-FZ01) |
| R18 | No CodeQL/Dependabot alert dismissed by this work | S3, S7, S11 | VERIFIED | the 4 dismissed code-scanning alerts are all from 2026-10-02 by `1h0lde4`; Dependabot #1-#4 open [v3 update: #1-#7 open, 0 fixed, 0 dismissed, 0 auto-dismissed, per-state reads at `1d813bd`] | |
| R19 | Original: obtain the coordinator transfer token before proceeding past live-state verification | §2 | NOT OBTAINED | never provided; never invented | work proceeded on the owner's explicit step-by-step directives; see §15 |
| R20 | Original open decision 1 (29 findings) | §2 | VERIFIED resolved | #46 fixed 28, #56 fixed #12 | |
| R21 | Original open decision 2 (`_safe_extractall`) | §2 | DISPOSITION PRESENTED, never formally ruled | helper kept unchanged; strictness verified (stdlib silently rewrites `../../evil.txt`, helper refuses the whole bundle); not touched by #46/#56 | keep unless the owner says otherwise |
| R22 | Original open decision 3 (`module_name` validation placement) | §2 | VERIFIED implemented | #46: containment at every sink (`module_child()`), naming at the boundary | accepted by merge |
| R23 | Original open decision 4 (`chromadb` alerts) | §2 | ACCEPTED | D-032 below | |
| R24 | Untraced: PlannerWorker error | §2 | VERIFIED traced and fixed | #63 | |
| R25 | Untraced: crawler/cleaner/gap_detector | §2 | VERIFIED traced | only `learning/scheduler.py` loops over `self.registry`; recorded in the DEBT-038 addendum (#58) | |
| R26 | Untraced: webhook model in `core/brain_api.py` | §2 | TRACED, **not recorded in the register** | `EventSubscribeRequest(event, webhook_url)` is referenced nowhere else in the repo; no route, no test | reported to the owner in the first disposition; add a register note if wanted |
| R27 | #70 owner verdict recorded | S16 | VERIFIED | `issuecomment-6096538561`: option 1 now, option 3 as unscheduled direction | upgrade not scheduled; alert #4 open |
| R28 | #65 pin implemented as its own PR with an agreement check | S16, S17 | VERIFIED | PR #73 merged `77e2e82` (2026-10-10T10:45:43Z); `tests/test_chromadb_pin_agreement.py`, 4 tests; 2 of 4 fail on the pre-fix `pyproject.toml`; 10 of 10 mutants caught (local sandbox); CI `tests` green on head and merge commit | pin is provisional (study); the Android p4a list is not covered |
| R29 | Registry PR recording the #65/#70 decisions | S17, S18 | VERIFIED | PR #74 merged `1d813bd` (2026-10-10T11:51:35Z; head `3569399`); CI green on head and merge commit; `check_drift.py` exit 0 | written from a Dependabot read taken before #5-#7 existed (see R30, §12) |
| R30 | Dependabot #5-#7: inventory, fold into the post-study registry update; no separate note, issue or dismissal | S19 | INVENTORIED (verified); registry accounting PENDING by decision | #65 comment `issuecomment-6109033966`; per-state API reads at `1d813bd`: open 7, fixed 0, dismissed 0, auto-dismissed 0 | pending the study (R31); fallback in S19 |
| R31 | Consolidated registry update after the study, covering alerts #1-#7 | S19 | OPEN (blocked on the study) | none yet | do not do early; interim note only under S19's fallback |
| R32 | Dependency compatibility study of all requirements | S16 | NOT STARTED by this workstream; owner-run, future | no evidence of completion | **do not claim complete** |
| R33 | K4.2 gap: no duplicate work item | S17 | VERIFIED | FZ-01 row in `KNOWN_ISSUES.md` @ `1d813bd`: OPEN, BLOCKED on D1 | D1 undecided |
| R34 | Handoff refreshed to verified state, documentation only | S20 | VERIFIED by the version 3 commit | §19; only `handoff.md` changed | |

## 6. Current Verified State

**[v3 update, verified live 2026-10-11. This block supersedes the version 2 state below wherever they differ.]**

### VERIFIED (v3)
- `main` = `1d813bdae320bf34110c29836c81dc901c601c9b` (PR #74, this workstream; parents `77e2e82` and `3569399`). No commits followed it at the refresh. Before it: `77e2e82` (PR #73, this workstream), then `27d918d` (PR #71, another session). CI on `1d813bd`: `tests`, `drift-and-ownership` and both `Analyze` jobs success.
- Code scanning on `main`: 0 open, 34 fixed, 4 dismissed (unchanged; none dismissed by this work).
- Dependabot, per-state reads (open / fixed / dismissed / auto-dismissed = 7 / 0 / 0 / 0): #1-#3 `chromadb` on `requirements.txt` (GHSA-2wm9-hf6c-p5cr high, GHSA-xph7-9rjv-w5fr high, GHSA-36p7-vc44-83pf critical; created 2026-09-26); #4 `sentence-transformers` on `pyproject.toml` (GHSA-jhr6-gm9c-rqjv critical; created 2026-10-04); #5-#7 `chromadb` on `pyproject.toml` (the same three advisories as #1-#3; created 2026-10-10 at 10:46:47-48Z, about a minute after PR #73's merge at 10:45:43Z). No patched `chromadb` version exists (vulnerable ranges run through 1.5.9). All seven open, none dismissed. Full inventory: issue #65 comment `issuecomment-6109033966` (its wording that PR #73 merged "the same minute" was imprecise; the original comment is unedited and was corrected at the source by the follow-up comment `issuecomment-6109187922`; the timestamps above are exact). One read with `state=all` returned an empty list; the per-state reads are the authority.
- `pyproject.toml`, `requirements.txt` and every `pip install` line in `release.yml` pin `chromadb==0.5.3` (PR #73); `tests/test_chromadb_pin_agreement.py` enforces that they agree.
- Issues #65 (3 comments) and #70 (2 comments) are open, with the owner's decisions recorded: #70 `issuecomment-6096538561` (assessment `issuecomment-6061327562`); #65 `issuecomment-6096538690` (decision), `issuecomment-6096739729` (PR #73 merge note), `issuecomment-6109033966` (#5-#7 decision and inventory).
- Registry on `main`: the Oct 10 sync entries and the DEBT-032 addendum (PR #74) record the #65 pin and the #70 boundary decision and map the K4.2 gap to FZ-01. They were written from a Dependabot read taken before #5-#7 existed (the alerts were created 10:46Z; PR #74 merged 11:51Z) and say only that #1-#4 are still open. That is true but incomplete; by decision S19 it is **not** corrected before the study (fallback: S19).
- FZ-01 in `KNOWN_ISSUES.md` @ `1d813bd`: **OPEN -- BLOCKED on D1** (not started; batches B3/B4); depends on FZ-02. FZ-02's row on `main` reads **OPEN -- BLOCKED on D2** (not started; batch B2) although PRs #67 and #71 (FZ-02 branches) have merged; that is another workstream and was **not evaluated**.
- Open PRs: #25, #27-#33, #45, #61 (unchanged; none touched).
- Unchanged and in force: D-032 (`chromadb` embedded-only boundary and its reopen trigger), the #70 decision, `/import` and `/brain/v2/import` refuse until `global.import_root` is set, the opaque workflow-failure answer text.

### IMPLEMENTED BUT NOT VERIFIED (v3)
- None.

### PROPOSED / OPEN (v3)
- Why #5-#7 appeared (**inference only**): PR #73's exact pin plausibly made `pyproject.toml` resolvable to Dependabot. The timing is consistent with that; Dependabot's resolution logic was not examined.
- The compatibility study: **not started by this workstream and not complete**; owner-run; the prerequisite for the consolidated registry update.

### DEFERRED (v3)
- The consolidated registry update covering alerts #1-#7 (after the study; fallback S19); any disposition of Dependabot #1-#7; the `sentence-transformers` upgrade (direction accepted, unscheduled); the revisit of the `chromadb` pin; Dependabot PRs #32/#33; a register note for `EventSubscribeRequest`; CRLF normalization of other files.

### BLOCKED (v3)
- FZ-01 on D1 (not this workstream). The consolidated registry update on the study.

### UNKNOWN (v3)
- Everything listed as UNKNOWN in the version 2 state, plus: Dependabot's resolution mechanism for #5-#7; what the Android p4a step resolves for `chromadb` and `sentence-transformers` (the p4a list names them without versions).

**[Version 2 state, kept for the record (as of 2026-10-09). Where it differs from the block above, the v3 block wins.]**

Verified from live reads at the end of the session (`main` @ `27d918d`; this handoff branch is based on `8c0ea03`, see §7):

### VERIFIED
- `main` = `27d918db18d7d748b91b2a8babafb7339108da70` (PR #71, FZ-02/B2b, another session; it touches only `core/capabilities/adapters/model_router_adapter.py` and two FZ-02 test files, with no overlap with this workstream). The commit before it, `8c0ea03`, is PR #67 (also FZ-02, another session). CI on `27d918d`: `tests`, `drift-and-ownership`, both `Analyze` jobs green.
- Code scanning on `main`: **0 open, 34 fixed, 4 dismissed**; latest CodeQL analysis `27d918d` (2026-10-09T08:37Z; the analyses of `8c0ea03` were equivalent): Python 3 results (the 3 dismissed ones), actions 0. The 4 dismissed: #30, #31, #32 `py/incomplete-url-substring-sanitization` ("used in tests"), #36 `py/path-injection` ("false positive"); all by `1h0lde4` on 2026-10-02; none by this work.
- Merged by this workstream: #46, #56, #58, #63, #66 (SHAs in §7). #44 closed unmerged. Issues #54 and #62 closed (completed); #65 and #70 open.
- Dependabot: #1, #2 (high), #3 (critical) on `chromadb`; #4 (critical) on `sentence-transformers`. All open, none dismissed or fixed.
- Behavior change in force: **`/import` and `/brain/v2/import` refuse until `global.import_root` is set** in `config/settings.toml` (commented-out example ships). Failure answers of the workflow-runtime branch are now `Sorry, I encountered an internal error: WorkflowFailure (ref <uuid>)`.
- Shipped `config/settings.toml` has `[runtime] use_k42_frontend = true`, so a default deployment takes the K4.2 branch, which never reads `wf_result.error`.

### IMPLEMENTED BUT NOT VERIFIED
- None. Every change is merged and was verified by fresh analysis or tests.

### PROPOSED
- #70 verdict: *conditionally exposed in principle (the flaw pattern is present in `sentence-transformers` 3.4.0/3.4.1, which a resolver picks), not reachable through any OCBrain input path found, practical exposure needs write access to the process working directory*. Options in §10/§17. **The owner has not decided.**

### DEFERRED
- #65 (declared `chromadb` constraint); Dependabot #1-#4 dispositions; the K4.2 empty-answer gap; registry reference to #70; a register note for `EventSubscribeRequest`; CRLF normalization of other files.

### BLOCKED
- Nothing technically; all remaining items wait on owner decisions.

### UNKNOWN
- CI's raw test counts (the sandbox cannot reach the Actions log host); the launch working directory per deployment; what the Android p4a step resolves; the two models' hub `modules.json` (Hugging Face host unreachable); why Dependabot PR #33's CI is green under `chromadb==1.5.9` given DEBT-032's finding that 0.6.3 breaks fixtures (not analyzed).

## 7. Git / Repository Checkpoint

**[v3 update, 2026-10-11]**
- `main`: `1d813bdae320bf34110c29836c81dc901c601c9b`; the remote `main` equalled this at the refresh and no later commits existed. Ancestry: `73faf22` is an ancestor of `77e2e82`, which is an ancestor of `1d813bd`.
- Handoff branch `handoff/security-remediation-oct2026`: version 2 tip `275fc03698968fed72647dff28ec0a114a47e45f` (parent `8c0ea03`). The version 3 commit is the new tip; its hash cannot be stated inside the file, and its parent is `275fc03`. The branch was not rebased onto `main`. This refresh changes `handoff.md` only.
- Transfer commit (last implementation or documentation commit of this workstream): `1d813bdae320bf34110c29836c81dc901c601c9b` (merge of PR #74).
- Working tree, stashes and local-only commits: the sandbox repository holds only pushed work (`fix/chromadb-pin-oct2026` @ `c9662cd` and `docs/register-65-70-decisions-oct2026` @ `3569399`, both on the remote and merged, deliberately not deleted); no stashes.
- Merge commits added by this continuation, both on `main`:

| PR | Merge commit | Merged (UTC) | Reviewed head | Tree |
|---|---|---|---|---|
| #73 | `77e2e829ad2dbdacbfa063760293a543c131662a` | 2026-10-10 10:45:43 | `c9662cd02b75558d14044105b4c496e07b629a1e` (one commit) | `1f1912ab3a5dc150b57cf9481d93d50ffb7a1e08` |
| #74 | `1d813bdae320bf34110c29836c81dc901c601c9b` | 2026-10-10 11:51:35 | `3569399606576003ff49c52ce8cbd0165ef3c1b6` (one commit) | `1c367d766fd10e58d845d13975eb534599228804` |

In both cases `main`'s tree equals the reviewed head's tree (the merge added nothing). Merges used the GitHub `sha` guard and the merge-commit method.

**[Version 2 checkpoint, kept for the record]**


- Primary repository: `github.com/1h0lde4/ocbrain-v4.1` (public). Remote: `origin` = `https://github.com/1h0lde4/ocbrain-v4.1.git`.
- Branch carrying this file: `handoff/security-remediation-oct2026`. Base branch: `main`.
- HEAD before handoff (= base of the handoff commit): `8c0ea037e2152d9f4bb5150d35c6bb5ea817957d`. `main` advanced to `27d918db18d7d748b91b2a8babafb7339108da70` (PR #71) while this file was being written; the handoff branch was **not** rebased (it carries only `handoff.md` and `handoff_artifacts/`, which cannot conflict).
- Transfer commit (last commit of this workstream): `73faf222e0b6cefcf5a79b7ef9420acf60f497ab` (merge of PR #66). It is an ancestor of `main` @ `27d918d`.
- Handoff commit: the tip of `handoff/security-remediation-oct2026` (a commit cannot contain its own hash; its parent is `8c0ea03`).
- Working tree: all five sandbox worktrees were clean; 0 stashes; 0 commits existed only locally (every local branch tip is on a remote branch).
- Relevant untracked/ignored files: none (the scripts in `handoff_artifacts/` are committed on this branch).
- Submodules: none.
- Remote push status: this file is delivered by the branch itself; its presence on the remote branch is the proof of the push. The pushing session also compared the remote tip with its local tip.
- Merge commits of this workstream, all on `main`:

| PR | Merge commit | Merged (UTC) | Reviewed head | Tree |
|---|---|---|---|---|
| #46 | `a21711eb093d39d4757fa5fcc659e4530378bf61` | 2026-10-04 00:43:53 | `30b584a61256177b19ac34fe62fad83353c12025` (commits `acc43b7`, `53cf604`, `a3e97e0`, update-merge `30b584a`) | `e0017db1a9e5e60732c20733b08c09e1fb63f78d` |
| #56 | `41fa85a89753af95e4a1cc9754cd53c29252fed0` | 2026-10-05 07:29:57 | `f43df2e66d6409afa2372736ce00960b2dd3b9c4` (commits `4934f91` LF, `6dee2b2` fix, update-merge `f43df2e`) | `dca8920d6d564a451ae5b5bf1e600468faab10dc` |
| #58 | `710917c214fc92b63e3ca4c1a55c9f12d542b982` | 2026-10-05 07:44:58 | `40bbfff6403d66fa61602b84b82f8d7d347cc09b` | `1d25694912ce347d203a61cc6aff46d190965722` |
| #63 | `58d079f7963e09d49309f8e8bade00f71c2ef40f` | 2026-10-06 20:00:31 | `7e4ac1b43548ce6445ba8da083fa94eea3683078` (commits `6684a9b`, `7e4ac1b`) | `efc27db3095b2bb098c4e56188bb09fc1c23f4e8` |
| #66 | `73faf222e0b6cefcf5a79b7ef9420acf60f497ab` | 2026-10-07 20:46:40 | `8284149e5714cddec4488fb5b912e7287e3bcd7d` (commits `bc27d8d`, `8284149`) | `e5797a0e2cdc7edc453a9659a37f38121aba9318` |

In every case `main`'s tree equals the reviewed head's tree (the merge added nothing). #44: closed unmerged, head `c53ceccc35c8558d435fa683fd7d758f2b70b3fc`, branch left in place.

## 8. Active Files / Modified Files / Artifacts

Repository files changed by this workstream (all merged):

| File | Why it matters |
|---|---|
| `core/module_paths.py` | `module_child()`: `os.path.realpath` strings, `startswith(base.rstrip(os.sep) + os.sep)`, direct-child check, `os.stat()` ELOOP probe. Do not change its contract without the owner. |
| `tests/test_module_paths_direct_child.py` | 54 tests for that contract; runs on bare pytest (imports only the helper). |
| `core/brain_export.py` (LF) | `BundlePathError`, `import_root()`, `resolve_bundle_path()`; `import_module()` resolves first, probes existence second. |
| `core/brain_api.py` (LF), `interface/api.py` | both import routes map `BundlePathError` to HTTP 400 with fixed text. |
| `config/settings.toml` | commented-out `import_root` example (default: imports refused). |
| `tests/test_import_bundle_boundary.py` | 63 tests for D1-D5, traversal, sibling-prefix, symlinks, no existence oracle, sink and both routes. |
| `tests/test_brain_export_security.py`, `tests/test_module_name_containment.py` | existing tests adapted to configure an import root (one `ValueError` assertion tightened). |
| `core/orchestrator.py` (CRLF, preserved) | workflow-failure branch returns the opaque-ref text; event payload still carries the raw error. |
| `core/error_ref.py` | new `log_text_and_ref()`. |
| `tests/test_workflow_failure_disclosure.py` | 8 tests for contract C1-C4 (fixture renamed `RAW_FAILURE_TEXT` after CodeQL alert #43). |
| `KNOWN_ISSUES.md`, `CURRENT_STATE.md` | registry addenda: DEBT-019, DEBT-032, DEBT-037, DEBT-038; sync entries Oct 5 and Oct 6. |

Non-repository state (all reproducible):
- GitHub issues: #54, #62 (closed), #65, #70 (open); the #70 assessment comment `https://github.com/1h0lde4/ocbrain-v4.1/issues/70#issuecomment-6061327562`; the disposition comment on #44.
- `handoff_artifacts/` on this branch (copied from the ephemeral sandbox `/tmp`, **sandbox paths inside them must be adapted**): `repro_symlinks.py` (nested-symlink and loop matrix), `diff_helpers.py` (old-vs-new helper differential, 45 scenarios), `mut.py` (ten import-boundary mutants), `mut2.py` (seven workflow-failure mutants), `repro_planner_error.py` (the leak reproducer), `st_assessment.md` (the #70 assessment text).
- Sandbox venvs and wheel downloads in `/tmp` are ephemeral and not preserved.

**[v3 update] Files changed by the continuation (all merged):**

| File | Why it matters |
|---|---|
| `pyproject.toml` | the `chromadb` entry is now `"chromadb==0.5.3"` (PR #73); the file is LF |
| `tests/test_chromadb_pin_agreement.py` | new, 4 tests; `requirements.txt` is the reference declaration; the version number is not hard-coded; the Android p4a list in `release.yml` is not covered |
| `KNOWN_ISSUES.md`, `CURRENT_STATE.md` | Oct 10 sync entries and the DEBT-032 addendum (PR #74); both LF; additive |

Non-repository state added: issue comments `issuecomment-6096538561` (#70), `issuecomment-6096538690`, `issuecomment-6096739729`, `issuecomment-6109033966` and the timing correction `issuecomment-6109187922` (#65); the merged branches `fix/chromadb-pin-oct2026` and `docs/register-65-70-decisions-oct2026`, left in place on the remote. The mutation script used for PR #73 lived in the ephemeral sandbox and is **not** committed; the ten mutants are listed in §13 so it can be recreated. `handoff_artifacts/` is unchanged.

## 9. Changes Made

- **PR #46 (`core/module_paths.py`):** every module-name filesystem path goes through `module_child()`. Final contract: canonical string path must be strictly under the root and exactly one component deep; a symlink to a nested descendant or outside is refused; a symlink to another direct child is accepted and returns the canonical target; loops are refused on every Python version (the `os.stat()` ELOOP probe is the detector because neither `realpath()` nor, from 3.13, `Path.resolve()` raises on loops). The first form (`resolve()` + `parent`) was flagged by CodeQL; the `realpath` + `startswith` form was not.
- **PR #56:** `/import` boundary (decisions D1-D5, §10). Behavior change: imports refused until `global.import_root` is set. `core/brain_export.py` and `core/brain_api.py` converted CRLF to LF in a separate mechanical commit.
- **PR #63:** the workflow-runtime failure answer no longer contains `wf_result.error`; it is `Sorry, I encountered an internal error: WorkflowFailure (ref <uuid>)`, and the raw text is logged under that ref. Internal channels unchanged.
- **PRs #58, #66:** registry/state documentation, purely additive. DEBT-037 marked `CLOSED against 58d079f for the traced set`; DEBT-032 records the embedded-only decision and reopen trigger; both sync entries note Dependabot #4 as not yet assessed and label the full-suite figures as local sandbox runs.
- No schema, governance or runtime-topology change. No dependency was changed. No alert was dismissed.

**[v3 update]**
- **PR #73:** `pyproject.toml` `chromadb>=0.4.0,<1.0` became `chromadb==0.5.3`, so the three declarations agree; new `tests/test_chromadb_pin_agreement.py`. No runtime code changed. No dependency was installed or upgraded.
- **PR #74:** documentation only: new Oct 10 sync entries in `KNOWN_ISSUES.md` and `CURRENT_STATE.md`, and a DEBT-032 addendum (the row's earlier text is a byte-identical prefix; the row still has 5 cells). It records the #65 pin, the #70 boundary decision and the mapping of the K4.2 gap to FZ-01.
- Decision records were posted on issues #70 and #65 (§8). No alert was dismissed; no issue was created.
- This refresh changes `handoff.md` only.

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| D-46a | Containment for module names is decided on canonical strings at the sinks; the identifier rule stays at the entry boundary | ACCEPTED (merge) | owner merge of #46 | tests; differential; CodeQL | module directories legitimately nest, or a sink needs non-direct-child names |
| D-46b | A name symlinked to another direct child is accepted (aliasing); stricter variant not applied | ACCEPTED (merge) | flagged to the owner, merged | test `test_symlink_to_another_direct_child_returns_the_canonical_target` | aliasing becomes a problem |
| D-54 | **D1** no configured import root: refuse, no `data/exports` fallback. **D2** a relative `bundle_path` is relative to the root, never the CWD. **D3** `.ocbrain` suffix required. **D4** containment uses the #46-proven shape, not `resolve()` + `is_relative_to()` unless CodeQL is shown to accept it. **D5** the suffix is defense in depth, not the containment proof. | ACCEPTED | owner, recorded in issue #54 before implementation | PR #56, fresh CodeQL | owner request |
| D-54n | Implementation notes (nested paths allowed below the root; suffix checked case-sensitively on the canonical path; relative configured root resolved against the project root; HTTP 400 for both refusal kinds; `.exists()` kept) | ACCEPTED by merge only (never individually decided) | flagged in #54 and the PR | tests | owner request |
| D-62 | Contract C1-C4 (answer text `WorkflowFailure (ref <uuid>)`; text logged under the ref; internal event payload / `WorkerResult.error` / tracing unchanged; sibling branch still returns only the class name) applied at the caller boundary, plus `log_text_and_ref()` | ACCEPTED | DEBT-037 / `core/error_ref.py` rule, owner "Approve and merge #63" | PR #63 | a new caller-visible error site is found |
| D-LF | Convert only `core/brain_export.py` and `core/brain_api.py` to LF | ACCEPTED | owner S8 | commit `4934f91` | owner asks for a project-wide normalization (114 other tracked files, plus 2 with mixed endings, are CRLF in the index at `8c0ea03`; recount) |
| D-032 | Keep `chromadb==0.5.3`; the security boundary is **embedded-only** (`PersistentClient` only, no server/`HttpClient`/`trust_remote_code` path); reopen the assessment if server mode, HTTP client access or an equivalent remote execution/authentication surface appears; Dependabot #1-#3 **not dismissed** until the declaration is truthful | ACCEPTED | owner, 2026-10-06 | PR #66 | trigger conditions above |
| D-65 | The `pyproject.toml` range (`chromadb>=0.4.0,<1.0`) is a separate hygiene item; make the supported version explicit | PROPOSED (form undecided) -> [v3] superseded by D-65b | owner S11; issue #65 | `requirements.txt:4` and `release.yml` pin `==0.5.3` | owner chooses the form |
| D-70 | Alert #4 is its own work item; exposure not yet decided | OPEN -> [v3] superseded by D-70b | owner S13/S14; issue #70 | assessment comment | owner verdict |
| D-X | Merge only on an explicit owner go-ahead for an exact head, with the GitHub `sha` guard; merge method is a merge commit | ACCEPTED (process) | owner practice | all five merges | owner changes the process |
| D-65b | [v3] Pin `chromadb==0.5.3` exactly in `pyproject.toml` for now; revisit after the compatibility study | ACCEPTED | owner S16 | issue #65 `issuecomment-6096538690`; PR #73 | the study reports compatible versions |
| D-70b | [v3] Option 1 (boundary decision) now plus option 3 (upgrade to a release outside the vulnerable range) as the direction, **unscheduled**; alert #4 stays open and is not dismissed | ACCEPTED | owner S16 | issue #70 `issuecomment-6096538561` | any reopen trigger (model identifiers become configurable or user-supplied; models loaded from local directories; a feature creates directories in the process working directory; the working directory becomes writable by untrusted parties; `trust_remote_code` introduced); the study's outcome |
| D-FOLD | [v3] Fold Dependabot #5-#7 into the consolidated post-study registry update; no separate note now, no duplicate issue, no dismissal; fallback: a short dated interim note if the update no longer goes ahead | ACCEPTED | owner S19 | issue #65 `issuecomment-6109033966` | the post-study update is cancelled (fallback applies) or the owner changes it |
| D-FZ01 | [v3] The K4.2 empty-answer gap is the already-registered FZ-01; no separate item or issue | VERIFIED finding (not a new decision) | no-duplicate-findings rule (§24.1 of `PROJECT_INSTRUCTIONS.md`) and the register | FZ-01 row, `KNOWN_ISSUES.md` @ `1d813bd` | the owner asks for a GitHub tracker issue, or D1 is decided |
| D-GO | [v3] "Continue" is the go-ahead for an exact head only when that head was just named and the head sha and `mergeable_state == clean` with the required checks (`tests`, `drift-and-ownership`) are re-verified first; advisory neutral checks (`Graphify Formal Verification`: neutral when a PR changes no functions) do not block | ACCEPTED (process; practice S9, applied for #74) | owner practice | PR #74; branch protection requires only `tests` and `drift-and-ownership` | the owner changes the process |

#70 options (all PROPOSED, none done): (1) record a boundary decision with reopen triggers (model identifiers become configurable or user-supplied; models loaded from local directories; a feature that creates directories at the process working directory; a working directory writable by untrusted parties; `trust_remote_code` introduced); (2) bound the range below 3.4.0 (3.1.0-3.3.1 gate only on `trust_remote_code`), which is a dependency-policy change needing compatibility testing; (3) upgrade: behavior changes only in 6.0.0+ (5.6.0 adds only a `FutureWarning`); 6.x needs Python >=3.10 (repo floor is 3.11) but is a 3-to-6 major jump; (4) leave #4 open until decided.

**[v3 update] #70 options resolved by the owner (S16):** options 1 and 3 chosen (3 as direction, unscheduled); options 2 (bound the range below 3.4.0) and 4 (leave open) not chosen. Note carried forward for the study: the advisory's fix version is 5.6.0, but 5.6.0 only adds a `FutureWarning`; the gate behavior itself changes in 6.0.0, and 6.x needs Python >= 3.10 (repo floor is 3.11) and is a 3-to-6 major jump.

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| `module_child()` on nested symlink and loops | the PR #46 helper at `acc43b7` on Python 3.11.15, 3.12.3, 3.13.13, 3.14.4 | nested target accepted (wrong); loops leak `RuntimeError` on 3.11/3.12 and are silently accepted on 3.13/3.14 | `handoff_artifacts/repro_symlinks.py` | Python minimum or `pathlib` behavior changes |
| CodeQL barrier recognition | `acc43b7` (`resolve()` + `is_relative_to`), `53cf604` (`os.stat` probe), `a3e97e0` (`realpath` + `startswith`) | first two flagged (1, then 2 alerts); the third 0 | analyses on `refs/pull/46/head` | CodeQL query-pack update |
| PR #44 | head `c53cecc`, its CodeQL, ownership signals | 2 new alerts (#38 `brain_export.py:64`, #39 `:230`); no analysis combined with `main`; ownership unclear (session-authored commit, a human-attributed update-merge) | closing comment on #44 | none (closed) |
| `/import` flow | both routes, sink, tests | only two non-test callers of `import_module()` | PR #56 | a third caller appears |
| PlannerWorker leak | planner handler, `runtime.py:653-654`, orchestrator branches, shipped flag | reproduced on `main`; reached only when `runtime.use_k42_frontend` is false/unset; the shipped config sets it true | `handoff_artifacts/repro_planner_error.py`, issue #62 | K4.2 branch changes |
| crawler/cleaner/gap_detector | all non-test callers on `main` | only loops over `self.registry` in `learning/scheduler.py`; `/train/{module_name}` guarded by membership and is the only caller of `trigger_module` | DEBT-038 addendum (#58) | scheduler changes |
| webhook model | whole repo | `EventSubscribeRequest` referenced only by its definition (`core/brain_api.py:69`) | grep | a subscribe route is added (then `webhook_url` needs SSRF validation) |
| `chromadb` usage | whole repo | exactly one client construction, `chromadb.PersistentClient` at `modules/base.py:68`; no `HttpClient`, server, `trust_remote_code` | DEBT-032 addendum | server mode introduced |
| `chromadb` advisories | the three Dependabot alerts via API | #3 (GHSA-36p7-vc44-83pf): authenticated request to the server REST endpoint; #2 (GHSA-xph7-9rjv-w5fr): `SimpleRBACAuthorizationProvider`; #1 (GHSA-2wm9-hf6c-p5cr): authenticated cross-tenant access; vulnerable ranges run through 1.5.9, no patched version | Dependabot API | advisory text changes |
| `chromadb` declarations | `requirements.txt`, `pyproject.toml`, workflows | `requirements.txt:4` and `release.yml:35,84,137` pin `==0.5.3`; `pyproject.toml:45` says `>=0.4.0,<1.0` | issue #65 | declarations change |
| `sentence-transformers` gate | wheels 3.0.0-3.4.1, 5.5.0, 5.6.0, 6.0.0, 6.1.0 (source only; no torch, nothing executed) | 3.0.x: no custom-module loading; 3.1.0-3.3.1: `if trust_remote_code:`; **3.4.0, 3.4.1: `trust_remote_code or os.path.exists(model_name_or_path)`**; 5.6.0 only adds a `FutureWarning`; 6.0.0 removes the short-circuit | issue #70 comment | a new release changes the gate |
| What the gate tests | 3.4.1 `__init__` and `_load_sbert_model` | the identifier is rebound only to `sentence-transformers/<name>`, never to the cache path, so `os.path.exists` tests the identifier relative to the process working directory | #70 comment | version change |
| sentence-transformers routes in the repo | non-test code | three routes: `core/learning/similarity.py:20` (literal), `core/memory/backends/memory_vector.py:121` (only `InMemoryVectorBackend()` with no argument at `core/memory/unified_memory.py:289`), `modules/embedding_fn.py:32` (fixed `_MODEL_MAP`); no config key; no non-test caller passes a name; no cache/offline configuration | #70 comment | model names become configurable |
| CI vs sandbox | `scripts/ci_test_gate.py`, `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt` | CI tolerates only a 34-test Hugging Face-connectivity manifest and passed on each merge commit; the sandbox lacks `chromadb`, so its failing set is different (8) | `tests` check success; raw counts unreadable | host allowlist changes |
| Reconciliation of #66 | all its claims vs live state | four corrections: R1 label sandbox figures; R2 three sentence-transformers routes, not two; R3 shipped `use_k42_frontend = true`; R4 clarify the Oct 5 entries' unlabeled figures | commit `8284149` | n/a |
| Dependabot PRs #32, #33 | titles, files, head checks (read-only) | #33 bumps `chromadb` to 1.5.9 in `pyproject.toml` (`<2.0`) and `requirements.txt`; #32 widens `sentence-transformers` to `>=3.0.0,<7.0`; both created 2026-09-26 on an old base, `mergeable unknown`, `tests` green | PR API | **not evaluated further**; do not merge |
| K4.2 gap vs the register (v3) | `core/orchestrator.py` K4.2 sites; the FZ table in `KNOWN_ISSUES.md` @ `1d813bd` | the gap is FZ-01 (same condition: `wf_result.output or ""`, no failure channel); FZ-01 is OPEN, BLOCKED on D1, depends on FZ-02 | FZ-01 row | D1 decided or FZ-01's status changes |
| Dependabot #5-#7 (v3) | Dependabot API, per-state reads at `1d813bd` | same three advisory IDs as #1-#3, manifest `pyproject.toml`, created 2026-10-10 10:46:47-48Z (about a minute after PR #73's merge at 10:45:43Z); cause inferred, not confirmed | #65 `issuecomment-6109033966` | Dependabot's resolution behavior is examined |
| Neutral Graphify check on PR #73 (v3) | check-run output on `c9662cd`; branch protection | concluded neutral because no PR-changed functions were verified; advisory; required checks are only `tests` and `drift-and-ownership` | check-run output; branch protection read | Graphify becomes a required check |

Not investigated: the other open PRs (#25, #45, #61, #27-#31); how the K4.2 branch could return an empty answer; the `system_ctrl` module's confinement (not re-audited); runtime behavior of any exploit (nothing was executed).

## 12. Failed Attempts / Dead Ends

| Approach | Result | Cause / evidence | Retry? |
|---|---|---|---|
| `resolve()` + `is_relative_to` / `.parent` as the containment barrier | CodeQL flagged it (alerts on `acc43b7`, `53cf604`, and #44's #38/#39) | CodeQL does not treat that shape as a barrier | No; use `realpath` + `startswith(base + os.sep)` |
| Relying on `Path.resolve()` to raise on symlink loops | wrong on 3.13+ | behavior changed in 3.13 | No; probe with `os.stat()` (ELOOP) |
| A test fixture constant named `SECRET` passed into a logging helper | CodeQL alert #43 (`py/clear-text-logging-sensitive-data`) on PR #63 only | name-based "secret" classification; the production path was not flagged | Avoid secret-like names for fake error strings |
| Long background jobs / `sleep` over about 280 s in one tool call | process killed or call timed out | the tool kills background children between calls and caps a call at 300 s | Use foreground runs and short polls |
| Reading the Actions job log | blocked | egress allowlist excludes `productionresultssa1.blob.core.windows.net` | Ask the owner to allow the host, or use the check conclusion only |
| Fetching Hugging Face hub files | blocked (`HTTP 000`) | host not in the allowlist | same |
| Unauthenticated GitHub API for PR/alert reads | rate limit exhausted on the shared IP | 60/hour | Use the credential |
| `sh`-isms in tool commands (`<(...)`, `$'...'`, `${v:0:7}`) | syntax errors aborted whole scripts | the shell is dash | Write portable shell or run Python |
| Greps that silently misled | wrong class picked (`_BM25Index`), `head` truncation, `git grep` pathspec glob dropped `requirements.txt`, `awk` early exit | review output, assert on counts | Verify with a positive control |
| A saved credential in user preferences | returned 401 | revoked/dead | n/a; use what the owner supplies |
| "Zip-slip" claim | retracted in the earlier handoff | direct validation showed stdlib sanitizes; `_safe_extractall` is strictness, not a fix | Do not resurrect |
| The Dependabot API once returned an empty list | transient | repeat and per-state queries returned all four alerts | treat a single empty read as suspect |
| [v3] Merge guard requiring every check to be `success` | aborted the first PR #73 merge attempt (`Graphify Formal Verification` is `neutral`) | guard too strict; neutral is not failure | Gate on head sha, `mergeable_state == clean` and the required checks; fail only on failure, cancelled or timed-out checks |
| [v3] Shell polling loop using `[ $? -eq 0 ] && break` around a Python poll | exited on the first in-progress iteration | Python exited 0 while checks were still running | Poll inside the Python script |
| [v3] Dependabot read with `state=all` | returned `[]` once | cause not established; per-state reads were consistent (7 / 0 / 0 / 0) | Read per state |
| [v3] Handoff v2 claim that the K4.2 gap "has no work item" | wrong | the register already tracks it as FZ-01 | Check the FZ table in `KNOWN_ISSUES.md` before proposing a new item |
| [v3] PR #74's text asserted only Dependabot #1-#4 | incomplete | the Dependabot read behind it predated #5-#7 (created 10:46Z; #74 merged 11:51Z) and was not repeated before writing | Re-read Dependabot before asserting an inventory |
| [v3] Calling #5-#7 "duplicates" | imprecise wording | they are distinct per-manifest alert records (S19) | Say "same advisory, different manifest" |

## 13. Verification Evidence

All counts below are from the **local minimal-dependency sandbox (no `chromadb`)** unless stated; CI's raw counts were not readable. Full-suite command (from the earlier handoff):

```text
python3 -m pytest -q --no-header -p no:cacheprovider -rfE tests/ --ignore=tests/test_break_concurrency.py --ignore=tests/test_break_empty_db.py --ignore=tests/test_break_security.py --ignore=tests/test_system_ctrl.py
```

| Check | Scope | Result |
|---|---|---|
| Full suite, baselines and branches | pristine `main` @ `80a1bb8`; PR #56 head; `main` @ `e438387`; `main` @ `8b0fee2`; PR #63 head; `main` @ `58d079f` | 8 failed / 1813 passed; 8 / 1943; 8 / 1880; 8 / 1943; 8 / 1951; 8 / 1951 (4 skipped, 1 xfailed in each). The failing set was identical every time (8 tests needing `chromadb`; per the earlier handoff, 6 in `TestA7SystemController` and 2 in `test_module_factory_security`). Not re-run at `8c0ea03`. |
| `tests/test_module_paths_direct_child.py` | Python 3.11.15, 3.12.3, 3.13.13, 3.14.4 | 54 passed on each; 12 of 44 original tests failed against the pre-fix helper |
| `tests/test_import_bundle_boundary.py` + neighbors | same four interpreters | 63 new tests; neighbors pass (201 passed, 4 skipped in the targeted set); ten mutants all caught |
| `tests/test_workflow_failure_disclosure.py` + planner/disclosure suite | same four interpreters | 62 of 62; 3 of 8 new tests fail against the unfixed orchestrator; seven mutants all caught |
| Differential, old vs new `module_child()` | 45 filesystem scenarios x 4 interpreters | 0 divergences; positive control against the pre-fix helper: 11 |
| CodeQL (GitHub, fresh analyses) | `a3e97e0` 0; `f43df2e` 0; `7e4ac1b` 0; `main` @ `a21711e` 28 of 29 fixed, #12 open; `main` @ `41fa85a` (2026-10-05 07:31Z) #12 fixed, 0 open; `main` @ `58d079f`, `73faf22`, `8c0ea03` and `27d918d`: 0 open | no new alert created since 2026-10-02 |
| GitHub CI | every merge commit and `main` @ `27d918d` | `tests`, `drift-and-ownership`, `Analyze` jobs success (raw counts unread) |
| `scripts/check_drift.py` | on both docs PR branches | exit 0, 15 of 15 rules PASS |
| Structural checks | each merge | `main` tree equals the reviewed head's tree; reviewed files byte-identical; PR patch-id unchanged by update-branch (`#46` `fe9d5cf689646b13`, `#56` `8906d195c056cf65`) |
| [v3] `tests/test_chromadb_pin_agreement.py` | Python 3.12.3 sandbox, bare `pytest` | 4 passed; against `main`'s pre-fix `pyproject.toml`: 2 failed, 2 passed |
| [v3] Mutation check of that test | ten mutants, each applied to a copy and reverted: M1 `requirements.txt` pin drifts to 0.5.4; M2 `requirements.txt` unpinned; M3 `requirements.txt` range; M4 `requirements.txt` entry removed; M5 `pyproject.toml` back to the old range; M6 `pyproject.toml` pin 0.6.3; M7 `pyproject.toml` entry removed; M8 one `release.yml` line drifts; M9 one `release.yml` line unpinned; M10 all `release.yml` lines lose `chromadb` | baseline pass; 10 of 10 caught; files restored |
| [v3] `scripts/check_drift.py` | on both PR branches | exit 0 each |
| [v3] GitHub CI | PR #73 head `c9662cd` and merge `77e2e82`; PR #74 head `3569399` and merge `1d813bd` | `tests`, `drift-and-ownership` and both `Analyze` jobs success on each; `CodeQL` success on the PR heads; `Graphify Formal Verification` neutral on #73 (advisory); raw counts unread |
| [v3] Code scanning | `main` at `1d813bd` | 0 open, 34 fixed, 4 dismissed |
| [v3] Dependabot | per-state API reads at `1d813bd`, repeated at this refresh | open 7, fixed 0, dismissed 0, auto-dismissed 0 |
| [v3] Structural checks | PRs #73 and #74 | `main`'s merge tree equals the reviewed head's tree in both; #73 vs `27d918d`: `pyproject.toml` +1/-1 and the new test file +82; #74 vs `77e2e82`: `CURRENT_STATE.md` +1, `KNOWN_ISSUES.md` +2/-1, LF preserved, the DEBT-032 row's old text a byte prefix of the new, still 5 cells |

Limitations: no exploit code was executed; raw CI logs and Hugging Face files were unreachable; counts are not CI's.

**[v3 update] Limitations:** the full test suite was **not** re-run for version 3 or for PRs #73/#74 beyond CI; the test figures above are local sandbox runs, not CI's; no exploit code was executed; this refresh itself ran only reads (git, GitHub API) and wrote `handoff.md`.

## 14. Environment / Tooling Assumptions

- Sandbox: Ubuntu, system Python 3.12.3; `uv` venvs for 3.11.15, 3.13.13, 3.14.4 under `/tmp` (ephemeral). Dependencies installed ad hoc: `pytest pytest-asyncio pydantic tomli tomli-w pyyaml fastapi httpx aiofiles requests rich click datasketch feedparser beautifulsoup4 trafilatura`; `chromadb` is not installed.
- **The full suite rewrites `config/settings.toml`, `config/models.toml`, `config/sources.toml` and `data/context.sqlite`.** Restore them (`git checkout -- config/ data/context.sqlite`) before any commit and re-check intended edits.
- Line endings: `core/brain_export.py` and `core/brain_api.py` are now LF; `core/orchestrator.py` is CRLF and must stay CRLF unless the owner asks; check with a byte count in Python, never with `$'\r'` under `sh`.
- Git identity used for commits: `Claude (sandboxed session) <noreply@anthropic.com>`. Push without force; merge method is a merge commit; use `"sha"` in the merge call and `expected_head_sha` in update-branch.
- Credential: **not recorded here by design.** It is supplied by the owner (user preferences or pasted in the conversation) and used through an HTTP header (`git -c http.extraheader=...`, `Authorization: Bearer ...`) without writing it to files, remotes or output. A previously saved credential returned 401. Owner instruction on handling: S2.
- Network: egress allowlist includes `github.com`, `api.github.com`, PyPI and `pythonhosted`; it does **not** include the Actions log host or `huggingface.co`. Unauthenticated GitHub API calls are rate-limited on the shared IP.
- Tool limits: 300 s per call; background processes do not survive the call.
- Other sessions are active on `main` (FZ-02, FZ-03, FZ-07 etc.); `main` moved repeatedly during this session.

**[v3 update]**
- The continuation ran in a fresh sandbox: Python 3.12.3, `pytest` installed ad hoc (no `pytest-asyncio`; pytest printed an unknown-config-option warning, probably the asyncio setting, not checked; harmless); the version 2 virtual environments under `/tmp` were gone.
- `github.com` and `api.github.com` were reachable. Credential handling is unchanged: supplied by the owner in user preferences, used through an HTTP header, never written to files or this handoff.
- Git identity for commits: `Claude (sandboxed session) <noreply@anthropic.com>`; pushes without force; merges with the `sha` guard, merge-commit method.

## 15. Unresolved Questions / Risks / Blockers

| # | Item | Evidence / state | Safe to continue without it? |
|---|---|---|---|
| U1 | **#70 verdict** and the critical Dependabot alert #4 (CVE-2026-68770, CVSS 9.8) | assessment posted; proposed verdict conditional-low; unverified premises: hub `modules.json` of the two models, deployment working directory, p4a resolution | Yes for other work; do not dismiss or upgrade without the owner's decision |
| U2 | **#65** form of the `chromadb` declaration | `pyproject.toml:45` permits 0.6.3 while `requirements.txt`/`release.yml` pin 0.5.3 | Yes |
| U3 | **Dependabot PRs #32 and #33 are open** and would change exactly what #65/#70 decide (`chromadb` to 1.5.9, `sentence-transformers` range to `<7.0`); #33's CI `tests` is green, which is unreconciled with DEBT-032's finding that 0.6.3 breaks the knowledge fixtures | read-only look only | **Do not merge either** before the owner decides #65/#70; analyze why #33's CI is green first |
| U4 | **K4.2 empty-answer gap** has no work item | the K4.2 branch returns `wf_result.output or ""` on failure | Yes; ask the owner whether to open one |
| U5 | The coordinator **transfer token** required by the original prompt was never provided or invented | work was directed step by step by the owner | New session: follow the new prompt's own requirement |
| U6 | The registry's #66 sync entry mentions #65 but not #70; no register note for `EventSubscribeRequest` | by design (kept decoupled) | Yes; do after the #70 decision |
| U7 | CI raw counts unknown; the `chromadb` 8-failure set exists only in the sandbox | host blocked | Yes |
| U8 | After PR #56 both import routes **refuse** until `global.import_root` is configured; a deployment must set it | commented example in `config/settings.toml` | Owner/operator action |
| U9 | CTX-EXPORT-001 remains open: signature/checksum/content validation, `overwrite=True` semantics, TOCTOU between containment check and `ZipFile` open, freeze classification | register | Yes |
| U10 | 114 tracked files are CRLF in the index (plus 2 mixed), counted at `8c0ea03`; the count was 117 before the LF commits | `git ls-files --eol` | Yes; only if the owner asks |
| U11 | Open PRs not from this workstream were not examined: #25, #45, #61 (owner's account) and the Dependabot GitHub-Actions bumps #27-#31 (the pip PRs #32 and #33 are covered in U3). The open-PR list at the end of the session was exactly #25, #27-#33, #45, #61 | titles and branch names only | Do not touch |
| U12 | Pre-existing, out of scope: Graphify notes that an `async` route calls the synchronous importer | advisory, unverified | Yes |

**[v3 update] Disposition of the items above (verified 2026-10-11):**
- U1: RESOLVED by decision (S16): option 1 now plus option 3 as unscheduled direction; alert #4 open. The unverified premises behind the assessment remain unverified.
- U2: RESOLVED: exact pin (PR #73); issue #65 stays open as the post-study tracker.
- U3: STILL OPEN: Dependabot PRs #32 and #33 are open and untouched; do not merge them before the study and an owner decision; why #33's CI is green is still unanalyzed.
- U4: SUPERSEDED: the gap is FZ-01 (OPEN, BLOCKED on D1); no new item.
- U5: UNCHANGED: no coordinator transfer token was provided or asked for in this continuation.
- U6: PARTLY SUPERSEDED: the Oct 10 sync entries (PR #74) reference #65 and #70; the optional `EventSubscribeRequest` register note is still absent.
- U7-U12: UNCHANGED.

**New items (v3):**
- U13: Dependabot #5-#7 are not accounted for in the registry. Deferred by decision S19 to the post-study consolidated update (fallback: dated interim note). Safe to continue without it: yes.
- U14: the cause of #5-#7 is inferred only (see §6).
- U15: the compatibility study has no scope, owner or date recorded in the repository and is not started by this workstream. Safe to continue without it: yes, for everything except the consolidated registry update and any dependency change.
- U16: FZ-02's register row (BLOCKED on D2, not started) versus merged PRs #67 and #71: observed, not evaluated, not this workstream.
- U17: the `chromadb` pin is provisional; the Android p4a `--requirements` list in `release.yml` names `chromadb` and `sentence-transformers` without versions and is not covered by the pin test.
- U18: two imprecisions were found. (a) PR #74's registry text predates the #5-#7 inventory (§12): STILL OPEN, deferred by S19 to the post-study update. (b) The #65 comment `issuecomment-6109033966` said PR #73 merged "the same minute" as the alerts (merge 10:45:43Z; alerts 10:46:47-48Z, about 64-65 seconds later): CORRECTED at the source by the follow-up comment `issuecomment-6109187922` (original comment not edited or deleted; no other conclusion or decision changed).

## 16. Relevant Information / References

- Repository documents: `docs/architecture/PROJECT_INSTRUCTIONS.md`, `KNOWN_ISSUES.md` (DEBT-019, DEBT-032, DEBT-037, DEBT-038 and the Oct 5 / Oct 6 sync entries), `CURRENT_STATE.md`, `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`, `scripts/ci_test_gate.py`, `scripts/check_drift.py`, the earlier handoff on branch `handoff/codeql-remediation-sep2026` (`20ad523`).
- Issues: #54 (D1-D5, closed), #62 (contract C1-C4, closed), #65 (chromadb hygiene), #70 (alert #4, assessment comment `https://github.com/1h0lde4/ocbrain-v4.1/issues/70#issuecomment-6061327562`).
- Code anchors on `main`: `core/module_paths.py::module_child`; `core/brain_export.py::resolve_bundle_path`, `import_root`; `core/orchestrator.py` workflow-failure branch (search `WorkflowFailure (ref`); `core/error_ref.py::log_text_and_ref`; `modules/base.py:68` (`PersistentClient`); `requirements.txt:4`, `pyproject.toml:45-46`, `release.yml:35,84,137`.
- Dependabot: #1 GHSA-2wm9-hf6c-p5cr, #2 GHSA-xph7-9rjv-w5fr, #3 GHSA-36p7-vc44-83pf (all `chromadb`, no patched version); #4 GHSA-jhr6-gm9c-rqjv / CVE-2026-68770 (`sentence-transformers` below 5.6.0; the declared range `>=3.0.0,<4.0` is at `pyproject.toml:46` and `requirements.txt:17`).
- Cautions: never treat a green CodeQL result as proof of safety (the evidence is tests plus mutation checks); a sandbox test count is not CI's; re-check `main` before any action because other sessions merge continuously.

**[v3 update] Additional references:** PRs #73 (merge `77e2e82`) and #74 (merge `1d813bd`); issue comments `issuecomment-6096538561` (#70 decision), `issuecomment-6096538690`, `issuecomment-6096739729`, `issuecomment-6109033966` and the timing correction `issuecomment-6109187922` (#65); `tests/test_chromadb_pin_agreement.py`; the FZ table in `KNOWN_ISSUES.md` (FZ-01 and FZ-02 rows); `KNOWN_ISSUES.md` DEBT-032 and its Oct 10 addendum. Caution carried forward: re-read Dependabot per state before asserting any inventory.

## 17. Next Steps

1. **Verify state first** (§18). *Why:* `main` moves. *Verification:* the commands in §18. **[v3 status: COMPLETED. State verified at the start of the continuation (`main` `27d918d`, handoff tip `275fc03`, alerts, PR list) and again at this refresh (`main` `1d813bd`).]**
2. **Put the #70 assessment and options in front of the owner and wait for a verdict.** *Where:* issue #70. *Prerequisite:* none. *Expected:* a recorded decision (boundary decision, bounded range, or upgrade path). Do not change dependencies or dismiss #4 before it. **[v3 status: COMPLETED. Verdict recorded (S16): `issuecomment-6096538561`. No dependency change and no dismissal followed.]**
3. **Get the owner's form for #65** (exact pin vs bounded range; single source of truth) and, if asked, implement it as its own PR with a check that pins the agreement across `pyproject.toml`, `requirements.txt` and `release.yml`. Dismissal of Dependabot #1-#3 only afterwards, by explicit decision. **[v3 status: COMPLETED. Form chosen (exact pin) and implemented: PR #73 merged `77e2e82`. Dismissal of Dependabot #1-#3 was **not** done and is not authorized; those alerts, and #5-#7, stay open.]**
4. **Before touching Dependabot PRs #32/#33:** analyze them under the #65/#70 decisions (why #33's CI is green despite DEBT-032's fixture finding; what `<7.0` would let a resolver pick). Merge only on explicit authorization. **[v3 status: STILL PENDING, unchanged. PRs #32 and #33 are open and untouched; the analysis was not done. In practice it belongs to the owner's compatibility study.]**
5. **Ask whether to open a work item for the K4.2 empty-answer gap** (U4); do not fix it unasked. **[v3 status: COMPLETED and SUPERSEDED. Asked; the owner said ok, but the gap is the already-registered FZ-01, so no new item was created (§10 D-FZ01). A GitHub tracker issue only if the owner asks.]**
6. **After the #70/#65 decisions,** one narrow registry PR: reference #70 and #65 in the sync entry, record the decisions, optionally add the `EventSubscribeRequest` note. Same additive style and checks as #58/#66 (additive diff, pipe counts, LF, `scripts/check_drift.py`). **[v3 status: COMPLETED with caveats. PR #74 merged `1d813bd` and records the #65 and #70 decisions. The optional `EventSubscribeRequest` note was **not** added, and #5-#7 are not covered (inventoried afterwards; deferred by S19 to the post-study consolidated update).]**
7. Optional, only if asked: project-wide LF normalization as its own mechanical PR. **[v3 status: STILL PENDING (optional). Not asked.]**

### 17b. Next steps (version 3)

1. **Verify state first** (§18, version 3 values). *Why:* `main` moves and other sessions merge continuously.
2. **Wait for the owner's compatibility study.** It is owner-run; do not start it unasked and never report it complete without the owner's evidence. *Prerequisite:* none. *Expected:* the owner reports compatible versions of all requirements.
3. **After the study and an explicit owner go-ahead: one consolidated registry update**, as its own PR on a dedicated branch from current `main`. It covers Dependabot alerts #1-#7 (advisory IDs, affected manifest paths, statuses, the D-032 disposition), separates verified facts from the inference about #5-#7, preserves earlier text additively, and records the study's outcome and whatever the owner then decides for the `chromadb` pin form and the `sentence-transformers` direction. *Verification:* the same checks as PRs #58, #66 and #74 (additive diff, LF, table cell counts, `scripts/check_drift.py` exit 0, CI green on the exact head) and a fresh per-state Dependabot read.
4. **Fallback (S19):** if the owner says the post-study registry update is no longer going ahead, add a short dated interim note covering #1-#7 instead, in a narrow docs PR.
5. **Dependabot PRs #32 and #33:** do not merge or alter; analyze only under the study and an explicit owner decision.
6. **FZ-01 / D1:** not this workstream; do not fix unasked; open a tracker issue only if the owner asks.
7. **Optional, only if asked:** project-wide LF normalization as its own mechanical PR; the `EventSubscribeRequest` register note.
8. **Never without an explicit owner decision for that exact item:** dismiss a Dependabot or CodeQL alert, change or install a dependency, merge a PR.

## 18. Resume Instructions

**[v3] First actions, in order:**
1. `git fetch origin`, then verify the branch and this file: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/main refs/heads/handoff/security-remediation-oct2026`; read this file from `origin/handoff/security-remediation-oct2026`. At the refresh `main` was `1d813bdae320bf34110c29836c81dc901c601c9b` and the version 2 handoff tip was `275fc03`; the version 3 commit is the tip of the handoff branch.
2. Verify that `main` contains the transfer commit: `git merge-base --is-ancestor 1d813bd origin/main`, and note newer commits from other sessions (`git log 1d813bd..origin/main`).
3. Re-read live state through the API with the owner-supplied credential, **per state** for Dependabot: issues #65 (3 comments) and #70 (2 comments) open; Dependabot alerts #1-#7 open (open 7, fixed 0, dismissed 0, auto-dismissed 0); code scanning on `main` 0 open / 34 fixed / 4 dismissed unless `main` changed; open PRs #25, #27-#33, #45, #61.
4. Compare with the v3 block of §6; resolve any material mismatch (and correct this file) before acting.
5. Begin at §17b step 2. Do not repeat the investigations in §11 unless the listed trigger has occurred.
6. Do not merge, dismiss, upgrade or install anything without an explicit owner decision for that exact item, and do not claim the compatibility study complete.

**[Version 2 resume instructions, kept for the record; their ancestry check still holds because `73faf22` is an ancestor of `1d813bd`]**

First actions, in order:
1. `git fetch origin` then verify the branch and this file: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/main refs/heads/handoff/security-remediation-oct2026`; read this file from `origin/handoff/security-remediation-oct2026`.
2. Verify that `main` contains `73faf222e0b6cefcf5a79b7ef9420acf60f497ab` (`git merge-base --is-ancestor 73faf22 origin/main`) and note any newer commits from other sessions (`git log 73faf22..origin/main`).
3. Re-read live state through the API with the owner-supplied credential: issues #65 and #70 (open), Dependabot alerts #1-#4 (open), code-scanning alerts on `main` (expected 0 open / 34 fixed / 4 dismissed unless `main` changed), open PRs (#32 and #33 still open?).
4. Compare against §6; resolve any material mismatch (and correct this file) before acting.
5. Begin at §17 step 2. Do not repeat the investigations in §11 unless the trigger listed there has occurred.
6. Do not merge, dismiss, upgrade or install anything without an explicit owner decision for that exact item.

## 19. Transfer Status

TRANSFER READY

Basis (version 3): all work of this workstream is merged and verified on `main` through `1d813bd`; this documentation-only refresh is committed on `handoff/security-remediation-oct2026` and pushed (its presence on the remote branch is the proof, and the pushing session compared the remote tip with its local tip); no material work exists only locally (0 local-only commits, 0 stashes); the exact next action is defined (§17b step 2, §18). Residual items that a new session cannot resolve alone: the owner-run compatibility study and the consolidated registry update that waits on it, the Dependabot dispositions, Dependabot PRs #32/#33, and FZ-01 (blocked on D1). The coordinator-token requirement from the original prompt (R19, U5) was never satisfied and is recorded, not hidden.

*Version 2's basis for `TRANSFER READY` (kept for the record):* all work of that workstream merged and verified on `main`; the sandbox-only scripts committed under `handoff_artifacts/`; exact next action defined.
