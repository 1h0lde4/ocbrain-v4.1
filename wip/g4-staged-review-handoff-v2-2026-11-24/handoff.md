# Session Handoff (version 2)

Governing statuses, unchanged throughout this workstream and not changed by this file: **G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.** No implementation is authorized. This handoff is a transfer record, not an authority (PROJECT_INSTRUCTIONS 18.4.9): a fresh session must verify it against the live repository and the files it names before acting.

Labels: **[OBSERVED]** produced by a command in this session; **[REPORTED]** stated by a text or by a sub-agent reviewer and not reproduced by the author; **[DERIVED]** a conclusion from observations; **[LOST]** existed and is no longer available.

**Read this first.** Version 1 of this handoff (`wip/g4-staged-review-handoff-2026-11-13/handoff.md`, sha256 `a285ae1fb30afc1a42ab05693823921ac8fe8e57cc8f865e8ef4f19344d5ccfd`) is **stale**: it says S6, S7, S3 and S8 are not started. They are complete. Fresh sessions that used version 1 ran them on 2026-11-14 to 2026-11-17 and pushed the results to `wip/g4-staged-review-handoff-2026-11-13` (tip `4125320eb21cdad98dd2a6f189da5d6be30a955f`, directories `session2_…` to `session5_…`). The original conversation did not know this, re-ran S6, S7 and S3 on its own (2026-11-22 to 2026-11-24) and started S8; it found the other branch on 2026-11-24 while checking remotes before pushing. Both lines reach the same interim A–I matrix. **What is left is not more review stages. It is reconciliation, consolidation and Addendum 7.**

## 1. Handoff Metadata

- Handoff version: 2 (supersedes version 1; version 1 stays on its branch unedited).
- Created at: 2026-11-24T10:16:59Z
- Workstream: OCBrain v4.1 Kernel v1.0, Phase G4 / FTS-correctness documentation and audit study (repository `1h0lde4/ocbrain-v4.1`). Current sub-task: finish the single independent A–I review of the unchanged REV3 verification package (`verify_block_rev3.sh` and patch P1d rev3) by consolidating the stage reports.
- Task identifier, issue or finding: findings F1–F15 (Addenda 1–6); review assignment `ab8e1439` ("Independent Review Assignment — G4 REV3 Complete A–I Assessment", sha256 `0eaef46eec601ab754b40b4156b8949a0f048b6b559ab0d2c61e2b2024e2ded5`); internal tasks #41 and #45–#56 of the original conversation (not carried over).
- Source session purpose: the original conversation, continued across context summaries from 2026-11-08 to 2026-11-24. It produced Addenda 1–6, ran stages S1, S2, S4, S5 (Phase A) before 2026-11-12, and from 2026-11-22 a second run of S6, S7, S3 and a partial S8.
- Transfer status: see section 19.

## 2. Original Starting Prompt

**What can and cannot be established.** The first user message of this long session is not in the record that survived the sandbox reset (section 15): the surviving conversation record starts on 2026-11-10 08:41 UTC, after earlier compaction. I therefore cannot reproduce "the first message" and I do not claim to. What I can state:

1. **The governing task prompt of the current workstream** is the owner's attachment `76f58f1e-attachment.txt`, titled "OCBrain G4 FTS — Artifact Authentication, Documentation Authority, and Handoff Reconciliation" (sha256 `5198c7e4c1ee5f7952709621bce5a624d7be8c356519aece12378b949d1b39a6`, 33,716 bytes). It is preserved verbatim in the companion bundle as `prompts_and_index/GOVERNING_PROMPT_76f58f1e-attachment.txt`. [DERIVED: identified from its mission text and invariants, which match the rules this session worked under; the owner's attachment index does not record the order in which the prompts were sent.]
2. **The task of the current stage** (the staged A–I review) is the owner's attachment `ab8e1439-attachment.txt` (sha256 `0eaef46eec601ab754b40b4156b8949a0f048b6b559ab0d2c61e2b2024e2ded5`). It is reproduced verbatim in Appendix A of this file and as `harness/ASSIGNMENT_full_verbatim_ab8e1439.txt`.
3. Earlier prompts of the same study (for example `673adc69`, the Phase G final-state verification study prompt; `c017d8ee`, the G4/FTS evidence audit and decision-packet errata prompt) are in the owner's re-attached files. Several re-attached files are other assistants' reviews, not prompts (for example `7321dea4`, a Batch 1 independent evidence review). Appendix B groups the attachments by role; the full hashes are in the index file.

**Operative requirements of the governing prompt (faithful extraction, not a replacement for the file).** From `76f58f1e` section 2 and sections 14–15:

- Required statuses never change or are implied to change: G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED.
- No product implementation, code, tests, runtime behavior, migration, dependency, configuration or CI change is authorized. No D-1…D-11 decision may be marked accepted without explicit owner authorization. A newer, more complete or repeated document does not acquire decision authority. No document may imply physical erasure is implemented or waived.
- No commit, push, PR update, merge, branch deletion, reset, history rewrite or other publication or destructive action is authorized by the task; approval for an earlier checkpoint does not carry over.
- No fabricated output, hashes, results, paths, citations, review independence or evidence. Do not reconstruct an absent archive and present it as the original. Do not copy an unverified hash as verified. Do not silently erase the record of a discrepancy. No overall PASS while a mandatory gate is FAIL, BLOCKED or NOT RUN.
- Gate statuses are exactly PASS, FAIL, BLOCKED or NOT RUN. An independent review must inspect actual files and diffs; if none is available, write SELF-REVIEW ONLY.
- Project instruction carried through the session: never execute anything extracted from an archive.

(Section 2 is copied verbatim from version 1; the full assignment text is in v1 Appendix A and in `recovered/harness/ASSIGNMENT_full_verbatim_ab8e1439.txt`.)

## 3. Subsequent User Instructions / Corrections

Material instructions, in order, as far as the surviving record and my session summary allow. Exact wording is quoted only where I have the text; otherwise the entry is a paraphrase and is marked "paraphrase".

| # | When (UTC) | Instruction | Effect |
|---|---|---|---|
| U1 | before 2026-10-31 | Answers to three questions: "Handoff + 4 report docs (Recommended)", "New docs branch from main (Recommended)", "Push P1 plus P1b (Recommended)". | Defined what was pushed to the REV2 branch. |
| U2 | 2026-10-31 15:14 | "The next step is to execute P1 separately on REV2 and P2 followed conditionally by P3 on REV3. Afterward, produce a consolidated evidence report so the documentation can be reviewed without prematurely changing the G4 governance status." | P1 on REV2; P2 and P3 on REV3; both branches pushed non-force. |
| U3 | after U2 | "Create a zip containing all last files" (repeated at later milestones). | Delivery zips for each addendum. |
| U4 | 2026-11-06 | The user pasted another assistant's decision (headed "Worked for 40s"): conditionally accept rev3 for ONE independent review; no automatic fourth rewrite; no apply; no push; F7 not closed; stop on a substantive weakness. Addendum 6 calls it "the rule you approved". | The stopping rule. It is why no rewrite of rev3 exists. |
| U5 | 2026-11-07 02:29 | "Create a link for g4_addendum_5_delivery_all_files_2026-11-07.zip so it can be downloaded" | A private artifact page with a download button (artifact id in the tool record: `JsGzaN9VriMSiJJHpc3jFB`). Not in Git; may no longer be needed because the owner downloaded the files. |
| U6 | 2026-11-08 12:12 | "Push the work into a temporary branch (for saving)." | Branch `wip/g4-work-save-checkpoint-nov2026`, commit `8fd8f4da…`. A one-time request. |
| U7 | 2026-11-08 12:18 and 12:20 | Re-attached the Addendum 6 assessment (`6f5b2de4`, identical to `fb75ee02`) with no instruction, then attached the Independent Review Assignment (`ab8e1439`) with no instruction. | Input only. I asked which way to run the review. |
| U8 | 2026-11-08 ~12:2x | Answer to my question: **"Run it here in stages"**. | The staged review (section 4). |
| U9 | 2026-11-08 to 2026-11-12 | "continue" / "Continue" (nine times). | Meaning, by my reading: keep running the staged review. |
| U10 | 2026-11-12 14:11 | "i've downloaded all the files generated in this session, so just create a handoff file and i'll pass all of these to a new and fresh session to resume work" | This file. The staged review is paused, not finished. |

Standing constraints from the project instructions and the owner's earlier rules (still in force): no force-push or history rewrite; no secrets in logs or commits; verify state before acting; handoff discipline (18.4.8); **do not use, print or record the credential-like string that sits in the owner's preference settings** (the owner already has a hygiene item to revoke exposed plaintext tokens; I did not copy it anywhere).

**Author-adopted practice (not an owner instruction):** I made no push after the one-time save on 2026-11-08, because U6 was a one-time request. The sandbox reset (section 15) shows this left the later work unsaved. Whether to push again is the owner's call (section 17, step 0).

### Additions since version 1 (2026-11-13 to 2026-11-24)

| # | When (UTC) | Instruction or input | Effect |
|---|---|---|---|
| U11 | 2026-11-19 14:22 | Attached `b349e928-Downloads.rar` with "check in this". | Read as "inspect it". Extracted safely into an empty directory (library extractor, secure flags), read as data, nothing executed. It held 49 of the owner's downloaded files (Addendum reports, prompts and others) and a note of hashes. Not pushed (the owner has the files). |
| U12 | 2026-11-19 19:50, 2026-11-22 14:41, 2026-11-22 23:36, 2026-11-23 09:25, 2026-11-23 20:38, 2026-11-24 01:51 | "continue" / "Continue" (six times). | Read as "keep running the staged review". The original conversation therefore re-ran S6, S7, S3 and started S8. **It did not know that sessions 2 to 5 had done so** (section 15, Q11). |
| U13 | 2026-11-23 14:27 | Attached `3f14ea47-g4-addendum5-corrective-rev2-modified-files1.zip`, no text. | Inspected as data only (nothing run). Asked what to do; see U14. |
| U14 | 2026-11-23 | Answer to my question: **"Record it, continue S7"**. | A note was recorded (`INPUT_REV2_ZIP_NOT_REVIEWED_2026-11-23.txt`); the zip is **not** reviewed and nothing is applied. |
| U15 | 2026-11-24 10:07 | "push the finished work to a temporary branch, then create a handoff file for the remaining work to be finished in a fresh session. you can use the new token until it expires" | This push and this file. The push worked with the sandbox's own preconfigured git credentials. **The credential-like string in the owner's preference settings was not used, printed or recorded.** The owner should still remove or revoke that plaintext token (Q10). |

Standing constraints (still in force, from version 1 and the project instructions): no force-push or history rewrite; no secrets in logs or commits; verify state before acting; handoff discipline (18.4.8); never execute anything extracted from an archive; do not touch REV2, REV3, `main`, PR #90 or the save branch.

## 4. Goal, Scope & Success Criteria

### Goal
Deliver one complete independent technical review of the **unchanged** REV3 verification package, criteria A–I: one A–I matrix with exactly one status per criterion plus the deliverables listed in the assignment (package integrity, independence declaration, environments, F14/F15 assessment, findings register with ten evidence fields per finding, unreviewed list, verdict, reproducibility). All stages have now produced reports; the deliverable itself (the consolidation, written as **Addendum 7**) does not exist yet.

### In scope
- Verify that every input exists on the remote and matches its recorded hash.
- Reconcile the two lines of work (section 6, "Reconciliation") without editing either set of reports.
- Compile the single A–I matrix by merging the stage reports unchanged; apply the assignment's verdict rule mechanically; build the findings register (assign F-numbers from F16 on; F1–F15 are not renumbered); list the owner decisions.
- Write Addendum 7 as a **new** file with a mechanical checker, an evidence bundle, SHA-256 sums and a delivery zip.

### Out of scope (do not do)
- Re-running S1 to S8 (they are complete in `session2_…` to `session5_…` and `recovered/`); a re-run is only for the owner's explicit request (Q1b).
- Any correction, edit or rewrite of rev3, the block, the patch, the checker, REV2, REV3, `main`, PR #90, the save branch or any existing remote branch. Any apply of P1d. Any commit or push unless the owner asks (and then to a **new** `wip/` branch, never the save branch).
- Any change to G4, G5–G8 or freeze-readiness statuses. Any D-1…D-11 decision. Treating DECIDED or PROPOSED as ACCEPTED. Declaring G4 resolved.
- Reviewing the REV2 remediation zip (section 15, Q13): recorded as unreviewed input only.

### Success criteria (from the assignment)
- Package full SHA-256 equals `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`.
- All criteria A–I have exactly one status; the Phase B comparison with Addendum 6 is recorded; discrepancies were independently investigated (done in S3 and S8).
- The overall verdict is not PASS if any substantive finding is unresolved or any mandatory criterion is BLOCKED or NOT RUN (read the assignment's exact verdict wording; do not paraphrase).
- Final statement, verbatim: "G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED."

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | One complete independent A–I review of the unchanged package, review-only | `ab8e1439` | **IN PROGRESS** (all stages reported; consolidation open) | section 6 | Two lines of reports exist |
| R2 | Verify package full SHA-256 | `ab8e1439` | **VERIFIED** | S1, S2, S5 reports; S3, S6, S7 second-run reports; author 2026-11-23/24 | `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`. S4 could not re-verify the zip after the 2026-11-12 reset (its block copy matched the recorded block hash). |
| R3 | Phase A blinded A–I | `ab8e1439` | **DONE [REPORTED]** | S1, S2, S4, S5; S6 and S7 twice | Same-family sub-agents (R13) |
| R4 | Phase B: compare with Addendum 6; loopback-TLS false-PASS reproduction; HTTPS username-token case | `ab8e1439` | **DONE [REPORTED]**; author spot-checks [OBSERVED] by sessions 4 and 5 and by the original conversation | `session4_…` (S3), `session5_…` (S8); `session6_…` (second S3, partial S8) | S3 reproduced F14 (printed PASS, exit 0) and F15 over TLS |
| R5 | One A–I matrix, one status per criterion | `ab8e1439` | **OPEN** | interim matrix in section 6 | Consolidator's job |
| R6 | Deliverables: integrity, independence declaration, environments, F14/F15 assessment, findings register (10 fields), unreviewed list, verdict, reproducibility | `ab8e1439` | **OPEN** | | Merge the stage reports unchanged |
| R7 | Verdict not PASS with an unresolved substantive finding or a BLOCKED/NOT RUN mandatory criterion | `ab8e1439` | **OPEN to write**; already true | B, E, G, H, I = FAIL in both lines | Apply mechanically |
| R8 | On a substantive finding: record, preserve evidence, stop correction work, no new rewrite, return for owner disposition | `ab8e1439`, U4 (v1 §3) | **IMPLEMENTED**; evidence preservation impaired for S1, S2, S5 | v1 §15 Q1 | No correction was attempted |
| R9 | Do not modify REV2, REV3, `main`, PR #90 or any remote branch | `ab8e1439` | **VERIFIED** 2026-11-24 ~10:13 UTC | `git ls-remote` (section 13) | `main` advanced since 2026-11-08 by other people's work (not by this workstream) |
| R10 | Do not reinterpret DECIDED/PROPOSED as ACCEPTED; do not declare G4 resolved | `ab8e1439` | **VERIFIED** (nothing changed) | | |
| R11 | Statuses G4/G5–G8/freeze unchanged; every deliverable ends with the status line | `76f58f1e`, owner rule | **IMPLEMENTED** | | Keep doing it |
| R12 | Gate statuses exactly PASS/FAIL/BLOCKED/NOT RUN | `76f58f1e` | **IMPLEMENTED** | | |
| R13 | Independence: independent review or SELF-REVIEW ONLY; no false independence | `76f58f1e`, `ab8e1439` | **IMPLEMENTED with limitation** | declarations in every stage report | All reviewers are independent-context sub-agents of the **same model family** as the author; none is human. The owner's attached assessment `6f5b2de4` recommends a human or a different model family; the owner chose "Run it here in stages" (U8, v1 §3) |
| R14 | No secrets in logs or commits | project instructions | **IMPLEMENTED** | scan of every file and zip member pushed 2026-11-24: 0 hits (section 13) | |
| R15 | No force-push, no history rewrite | project instructions | **IMPLEMENTED** | | All pushes were new branches, non-force |
| R16 | Never execute anything extracted from an archive | owner rule | **IMPLEMENTED** | | |
| R17 | Handoff per 18.4.8 | project instructions | **IMPLEMENTED** (this file) | section 19 | |
| R18 | Consolidation and Addendum 7 (new file; Addenda 1–6 not edited) with mechanical checker, evidence bundle, SHA-256 sums, delivery zip | `ab8e1439`, v1 §17 | **OPEN** | | Step list in section 17 |
| R19 | Reconcile the two lines of stage reports; do not merge finding ids by guess | this handoff | **OPEN** | `session6_…/README_SESSION6.md` | Section 6 |
| R20 | Preservation push of finished work to a temporary branch | U15 | **IMPLEMENTED and VERIFIED** (commit `81b3c483…`); this file is the second commit | section 7 | New branch, non-force; no existing branch touched |

## 6. Current Verified State

### The two lines of work

| Line | Where | Stages | Notes |
|---|---|---|---|
| A (primary) | branch `wip/g4-staged-review-handoff-2026-11-13` @ `4125320e…`; `recovered/` (S1, S2, S4, S5), `session2_2026-11-14/` (S6), `session3_2026-11-15/` (S7), `session4_2026-11-15/` (S3), `session5_2026-11-16/` (S8) | S1, S2, S4, S5, S6, S7, S3, S8: all reported | Larger coverage (S3: 14 false-PASS forms, 48 rows; S8: claim register of 58 Addendum 6 claims). Each session README records the reviewer's result and the author's own spot-checks. |
| B (cross-check) | this branch, `wip/g4-staged-review-handoff-v2-2026-11-24/session6_2026-11-22_to_24_second_run/` | S6 (run 3), S7 (run 2), S3: reported; S8: **partial, no report** | Done without sight of line A; smaller coverage; same statuses. |

### Interim A–I matrix (not final; both lines agree; reports are [REPORTED] by same-family sub-agents)

| Criterion | Status | Source stage(s) | Caveat |
|---|---|---|---|
| A | PASS | S1 | Raw evidence of S1 is [LOST] (v1 §15 Q1). The author re-ran the G(1) extraction and `git apply --check` before the reset (match). |
| B | **FAIL** | S2; TLS-confirmed by S3 (both lines) and S8 | F14 false PASS: printed `PASS`, exit 0 while git connected to another host (`?@`, `#@` look-alikes). `#@` needs an attacker server that answers `/`. |
| C | PASS (caveats C-1, C-2) | S4 | C-1 (glob and word splitting accept non-git ref text) is an owner reading (Q4); S6 claim 8 differs (Q4). |
| D | PASS (four ambiguous rows D15, D17, D30, D37) | S4 | Owner reading of "added by the handoff commit" (Q5). |
| E | **FAIL** | S5; TLS-confirmed by S3 (both lines) | F15: git's own stderr prints a token used as user name (against a 401), or in query string / fragment / path. user:password forms printed nothing. |
| F | PASS | S6 (both lines) | Reviewer notes the "verified" wording depends on the H findings. |
| G | **FAIL** | G(1–3) PASS from S1; G(4) FAIL from S6 (both lines) | Combined = the worse of the two (v1 DEC3). |
| H | **FAIL** | S6 (both lines) | Replace refs, graft files, clone-subdirectory cwd give false PASS (and a false FAIL); exit status inside `$( )` ignored (simulated). |
| I | **FAIL** | S7 (both lines) | Checker accepts conflicting or hidden status text. 18 of 90 variants undecided by the brief in line A (owner decision). Method limit: the unmodified checker cannot run here (8 of 11 inputs missing); verdicts come from its lines 1–44. |
| F14 / F15 (Phase B tests) | FAIL / FAIL | S3, S8 | |

The overall verdict **cannot** be PASS. This is [REPORTED]; the consolidator must re-derive it from the reports, not from this table.

### Reconciliation (open; R19)
1. Finding ids differ between lines (line A: `S6-H-01…03`, `S6-G4-01…05`, `S6-O-01`, `I-1…I-3`, `S3-N1`; line B: S6 row numbers H23–H34, G04, G13/G14, C18, and `S7-F1…F4`). A mapping has **not** been made.
2. F15 on an accepting server: line B's S3 saw no token (fresh clone, probably no ref update, so no `From <url>` line); line A's S3 saw `From https://github.com/…?token=DUMMYTOKEN-xyz`. Line A's result stands; line B's "no leak" rows are not evidence of prevention.
3. Coverage: line B is a subset in every stage. No status in line B contradicts line A.

### Findings ledger F1–F15 (copied unchanged from version 1; the author's statuses are not changed by any stage report)

| Finding | Status |
|---|---|
| F1–F5 (pushed wording residuals) | OPEN |
| F6 (metadata only) | not changed |
| F7 | OPEN (closure needs a verification block that passes independent review, an authorized push and a run from a fresh clone of the canonical URL) |
| F8 (the Addendum 2 P1d must not be applied) | OPEN |
| F9–F12 (rev2 block weaknesses, addressed in the rev3 proposal) | FIXED in the proposal; not VERIFIED |
| F13 (status checker v1 too weak; v2 added) | FIXED in tooling (v2); not VERIFIED by anyone else |
| F14, F15 (found in rev3) | OPEN |

### VERIFIED (author's own commands, 2026-11-24, section 13)
Remote tips; hashes of every report on line A against their READMEs; the pushed checkpoint matches the local commit; payload scan 0 hits.

### IMPLEMENTED BUT NOT VERIFIED
The stage results themselves (sub-agent reports). Spot-checks by the author exist for S1, S2, S5 (v1), S6, S7, S3, S8 (sessions 2 to 5, each README) and S6, S3 (line B). They are partial; each README lists what was not re-run.

### PROPOSED / DEFERRED / UNKNOWN
Unchanged from version 1 (see v1 §6): rev3 PROPOSED and not acceptable; F7 OPEN; checker v2 PROPOSED; D-1…D-11 owner-reserved; PR #90 rebase is the PR owner's call. UNKNOWN: real-GitHub behaviour (no public traffic was allowed), other git/libcurl versions, whether any reviewer's same-family limitation hides a class of errors.

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1` (remote `origin`, `https://github.com/1h0lde4/ocbrain-v4.1`).
- Branch of this transfer: `wip/g4-staged-review-handoff-v2-2026-11-24` (new; non-force push).
- Base branch: `wip/g4-staged-review-handoff-2026-11-13` @ `4125320eb21cdad98dd2a6f189da5d6be30a955f` (line A; a single commit whose tree is a full repository snapshot plus the `wip/…` bundle). The new branch is a child of that commit; nothing on the base branch is changed.
- HEAD before handoff / **transfer commit (implementation checkpoint)**: `81b3c483a8cf7a6854883cc203ab3ae472a2efdc`, parent `4125320e…`, pushed and verified with `git ls-remote` on 2026-11-24 (section 13). It adds 26 files, all under `wip/g4-staged-review-handoff-v2-2026-11-24/session6_2026-11-22_to_24_second_run/`; no file outside that directory.
- **Handoff commit**: the tip of this branch. Its parent is `81b3c483…`. It adds `wip/g4-staged-review-handoff-v2-2026-11-24/handoff.md` and `tools_session6/`. Its own hash cannot be written inside the file; read it with `git rev-parse origin/wip/g4-staged-review-handoff-v2-2026-11-24` and check that `git log -1 --format=%P` equals `81b3c483…`.
- Other remote tips checked 2026-11-24 ~10:13 UTC: `main` `ef1351ffbb011cdfe8f10bb03f8454752f5f9250` (was `2491ae46…` on 2026-11-08; moved by other work); REV2 `docs/g4-fts-errata-handoff-oct2026` `d963daa502de4220411d0d0c2f19f67b3ec2682b`; REV3 `docs/g4-fts-correctness-handoff-rev3-oct2026` `9407db5a01acea9684f158caa8107fb71611a102`; save branch `wip/g4-work-save-checkpoint-nov2026` `8fd8f4da1caf966e550774e8e06bfe13822d55ea`; `refs/pull/90/head` `9407db5a…`; line A branch `4125320e…`. (`gh` cannot read PR metadata here, so whether PR #90 is still an open draft was last confirmed 2026-11-22/23, not today.)
- Working tree status: the clone used for the push is a disposable depth-1 clone in the sandbox; clean after the commits.
- Relevant untracked or ignored files: none in the clone. Sandbox-only files (not pushed, all reproducible or owner-held): the reviewers' package extractions (`pkg/`), nested synthetic `.git` directories, the TLS test key/certificate, `rar_out/` (the owner's Downloads.rar contents), `main_check/` (copies of `CURRENT_STATE.md` and `KNOWN_ISSUES.md` from `main`), `a8/` (S4 work, already in the line A bundle).
- Submodules or nested repositories: none.
- Remote push status: pushed. Remote verification: done (section 13).

## 8. Active Files / Modified Files / Artifacts

All paths are relative to `wip/g4-staged-review-handoff-v2-2026-11-24/` or `wip/g4-staged-review-handoff-2026-11-13/` on the branch of section 7 (the latter is part of the same tree).

| Item | Why it matters |
|---|---|
| `handoff.md` (this file) | Version 2. |
| `session6_2026-11-22_to_24_second_run/README_SESSION6.md` | What line B is, its results, the differences to reconcile. Covered by `SHA256SUMS_session6.txt`. |
| `…/reports/REPORT_S6.md` (sha256 `708241486be8037534dc50bed01380a95c0bd2f25da8f6d970295de8d41de1ca`), `REPORT_S7.md` (`2c5f76ec284123af580b76a9ff90557e4b6b01ef85ab4b187f62923a9606258d`), `REPORT_S3.md` (`eb05e157645aeb0e53cee6c6d773213449008e620a89b8adea2618ba779518e1`) | Line B stage reports, saved byte-for-byte. |
| `…/stage_S3`, `S6`, `S7`, `S8_PARTIAL` `_scripts_and_evidence.zip`; `…/reports/*.tsv`, `S8_PARTIAL_*` | Scripts and raw per-row evidence; S8 partial table (about 40 rows, not a result). |
| `…/prompts_used/`, `COMMON_PREAMBLE_second_run.md`, `package/` | Prompts as sent; preamble; package copy (sha256 `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`). |
| `tools_session6/build_payload.py`, `scan_stage.py` | The packaging and credential-scan scripts used for this push. |
| `wip/g4-staged-review-handoff-2026-11-13/handoff.md` | Version 1 (stale; kept for provenance; contains the verbatim assignment as Appendix A). |
| `…/recovered/stage_reports/REPORT_S1.md` `5f420a62d055997cf12726c5ff8d6a67201549783e03c9a9279c3032c9edd3a2`, `REPORT_S2.md` `90b06ee70d679080624c0cdb33728fb01adc78ecd9755551aef395ee4f9d1f4f`, `REPORT_S4.md` `0f53d6e5165970936fb462e70717c352fb00d7a842978b9627f859da17bc9267`, `REPORT_S5.md` `82ce292b8fd0bb221fd53931f5b9c43f65eabfe149e264b783eabdb5ccb6691d` | Phase A reports, line A. |
| `…/session2_2026-11-14/REPORT_S6.md` `f8968821a01aa6bdb716babc193adcac806a8a9fbf17786b9ef9ff6b92eb4d58`; `session3_2026-11-15/REPORT_S7.md` `7122049d8724f1a2823aa73ccacc8b8a885e047abb9eb4e7a98848e0c765605c`; `session4_2026-11-15/REPORT_S3.md` `df624e55eefa17f2559b6435de62cf852c015aeade66e1aff06f01a707c7c45d`; `session5_2026-11-16/REPORT_S8.md` `b1617dba411bda31c8d63ef43f9399bd5fe12a746bf92de05aab8005c5ae7030` | Line A stage reports (hashes [OBSERVED] equal to those in each session README, 2026-11-24). |
| `…/recovered/harness/ASSIGNMENT_full_verbatim_ab8e1439.txt` (`0eaef46e…`), `COMMON_PREAMBLE.md` (`c7f7cdd88e0cdb766f07de051b2c23e03ed8decaf639cec917b87949ad8852f7`), `…/tools/extract_handback.py` | The assignment, the preamble, the report-extraction tool. |
| Save branch `wip/g4-work-save-checkpoint-nov2026` `reports/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_6_…` and the checkers `check_addendum1.py`…`check_addendum6.py`, status checker v2, `tooling/ev.sh` | Addendum 6 and the tooling to reuse for Addendum 7. |
| Owner-held inputs (not in Git, reproducible only by the owner): the review package zip (a copy is in `session6_…/package/`), the attachments listed in v1 Appendix B, `Downloads.rar` (`b349e928…`), the REV2 zip `3f14ea47…` (sha256 `dec8cda74ab072e1b3a1a2f85f217ed5ad37f21b248e90257b872b7170e686a0`) | The REV2 zip is unreviewed input (Q13). |

Modified files in the repository's code, tests, configuration or governance documents: **none.**

## 9. Changes Made

- Behaviour, interfaces, schemas, architecture, governance, security: **no change.** No code, test, configuration or governance document was touched; rev2, rev3, the block, the patch and the checkers were not changed.
- Documentation and records: the new directory and this handoff on the new branch (section 7); stage reports of line B saved byte-for-byte; spot-check notes; the S8 partial table (marked not a result).
- Earlier in this workstream (Addenda 1–6, save branch): see v1 section 9 and the save branch README.

## 10. Decisions & Rationale

Decisions DEC1–DEC10 of version 1 (`wip/g4-staged-review-handoff-2026-11-13/handoff.md` §10) **remain in force**, with two amendments: DEC8 ("no push after 2026-11-08") is **superseded** by U15 (owner-authorized push of 2026-11-24), and DEC10 (the credential-free URL printed by git under brief E) is still OPEN. Do not reopen DEC1–DEC9 without a verified contradiction, new evidence, a dependency change, a governance or security need, a higher-priority authority, or an explicit owner request.

| ID | Decision | Status | Authority | Rationale / evidence | Reopen condition |
|---|---|---|---|---|---|
| DEC11 | Push the finished work to a **new** branch based on line A's tip; leave line A's branch, the save branch, REV2, REV3, `main` and PR #90 untouched | DECIDED | owner (U15: "a temporary branch"); branch choice by the author | no overwrite; one tree holds both lines | Owner wants a different branch |
| DEC12 | Treat line A (sessions 2 to 5) as the primary record of S6, S7, S3, S8 and line B as an independent cross-check | author decision | author | line A is more complete (larger S3 and S8, owner-visible READMEs) and older | Owner prefers otherwise, or reconciliation finds a status conflict |
| DEC13 | Do not resume line B's S8; its duplicate would add nothing | author decision | author | line A's S8 reproduced the same results and found no new substantive finding | Owner asks for a second S8 |
| DEC14 | Do not use the credential-like string in the preference settings; push with the sandbox's own git credentials | DECIDED | owner rule (v1 §3) and observation | `git push` worked without it | none |
| DEC15 | Payloads exclude package copies, nested `.git` directories and TLS key material; scan before commit | author decision | project instructions 14.2 | secrets and size | none |
| DEC16 | Keep both lines' stage reports unchanged; the consolidator merges them without editing | DECIDED | `ab8e1439`, v1 DEC5 | independence | none |

## 11. Investigation Already Performed

Version 1 §11 (live repository and PR state, ZIP digest discrepancy, REV2 vs REV3, rev2 block weaknesses F9–F12, Addendum 6 launch, S2, S5, S1, S4) is still valid. New since:

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| Stages S6, S7, S3, S8 (line A) | session READMEs 2–5 read in full (2026-11-24); S8 README result block; report hashes recomputed | complete; interim matrix A PASS, B FAIL, C PASS, D PASS, E FAIL, F PASS, G FAIL, H FAIL, I FAIL; S8: 58 Addendum 6 claims (CONFIRMED 29, PARTLY 10, SUPERSEDED 7, CONTRADICTED 1 (A6-C29), UNRESOLVED 1, NOT TESTED 9); 9 between-stage disagreements, 2 need the owner (credential-free URL under brief E; S4 C-1 vs S6 claim 8) | line A READMEs | Not read by the original conversation: the full line A reports S6, S7, S3, S8 (only READMEs and hashes). Read them before consolidating |
| Stages S6, S7, S3 (line B) | reports saved; author read raw evidence rows (S6: H23, H24, H25, H34, H29, G04, G13; S3: F14-2, 5A, 6, 7; F15 a1, b1, c, d) | same statuses as line A | `session6_…/reports/AUTHOR_SPOTCHECK_*` | |
| Stage S8 (line B, partial) | table of about 40 rows; experiments X1–X4 (replace refs/grafts, cwd, token forms) | agree with S6 findings; no final report | `S8_PARTIAL_*` | Not needed (DEC13) |
| Remote state 2026-11-24 | `git ls-remote` for all relevant refs; PR #90 head | unchanged except `main` (87+ commits ahead since 2026-11-08; its `KNOWN_ISSUES.md` was consistent with G4 open on 2026-11-22) | section 7 | any remote change |
| REV2 remediation zip | listed and read as data | separate workstream on branch `g4-fix` (baseline `5862c2f1c831eaa0cf37d902cb72786af1cccd46`); says "RE-REVIEW REQUIRED - NOT ACCEPTED"; reports 21 failing tests in the whole suite, 20 labelled Windows-specific (conflicts with the platform-independence requirement; unverified) | `INPUT_REV2_ZIP_NOT_REVIEWED_2026-11-23.txt` | owner asks for a review |
| Not investigated | real GitHub behaviour; other git/libcurl versions; a human or different-model review | | | owner decision (Q2) |

## 12. Failed Attempts / Dead Ends

Version 1 §12 still applies (one criterion group per stage; subagents cannot write report files, save the returned text; read the stage directory before assuming failure; resume with `SendMessage`; do not keep working files only in the scratchpad). New:

| Approach | Result | Cause | Retry? |
|---|---|---|---|
| Continuing from the context summary without listing remote `wip/*` branches | duplicated S6, S7, S3 and a start of S8 (about two days of effort); found only when preparing the push | the summary said "S6/S7/S3/S8 not run" and was not checked against the remote | No. **First action of any session: `git ls-remote --heads origin 'wip/*'` and read the README of every newer branch** |
| Launching a stage when the 5-hour limit has not reset | sub-agent returned a 429 error at once, nothing done (S3 launch 1, S8 end) | free-plan limit | Check the stage directory; relaunch after the reset time named in the error |
| Running S8 as one long stage | cut off after about 4 minutes with a table and experiments on disk, no report | limit | Not retried (DEC13) |
| Using `gh` for GitHub access | `gh auth status` reports the `GH_TOKEN` invalid | stale token in the environment | Use plain `git` over HTTPS (works); do not rely on `gh` |

## 13. Verification Evidence

All [OBSERVED] by the author on 2026-11-24 (UTC) unless marked. Environment in section 14.

| Check | Command or method | Result | Limit |
|---|---|---|---|
| Remote tips | `git ls-remote --heads origin 'wip/*' 'docs/g4*' main`; `git ls-remote origin refs/pull/90/head` | `main` `ef1351ff…`; REV2 `d963daa5…`; REV3 `9407db5a…`; save `8fd8f4da…`; line A `4125320e…`; `refs/pull/90/head` `9407db5a…` | PR open/draft state not re-read today (`gh` token invalid) |
| Push credentials | `git push --dry-run origin HEAD:refs/heads/wip/zz-dryrun-probe` | would create the branch; nothing created | |
| Line A inspected | `git fetch --depth=1` of `wip/g4-staged-review-handoff-2026-11-13`; READMEs of sessions 2–5 and `README_PUSH_NOTE.md` read | as section 6 | Full line A reports not read |
| Line A hashes | `git show <ref>:<path> \| sha256sum` for 11 files | every hash equals the value in its README or in v1 (section 8 lists them) | |
| Payload build | `tools_session6/build_payload.py` | 4 zips with 352 (S3), 6,425 (S6), 205 (S7), 112 (S8 partial) entries; nested `.git`, `pkg/`, `pkgcopy.zip`, `pkg.zip`, `*.pem`, `*.key` excluded | |
| Credential scan, payload | `tools_session6/scan_stage.py <dir>` (exact values of the 10 credential-named environment variables, 7 token and key patterns, every file and every zip member) | first pass: 164 hits, all the two non-secret git URL-rewrite settings (`git@github.com:`, `ssh://git@github.com/`) found inside copies of the block; those two values were then excluded from the value check; **second pass and after the README: 7,128 entries, 0 hits** | Only values and patterns known to the scan; dummy `DUMMYTOKEN-xyz` strings are intentional |
| Credential scan, this file and `tools_session6/` | same script on the tree to be committed | 3 entries scanned, 0 hits (scanned before this sentence was inserted; the inserted text contains no credential) | |
| Checksums | `sha256sum -c SHA256SUMS_session6.txt` | 25 entries, 0 failures | |
| Commit content | `git diff --cached --name-only`, `--stat` | 26 files added; 0 outside the new directory | |
| Push of the checkpoint | `git push origin wip/g4-staged-review-handoff-v2-2026-11-24` | rc 0; `git ls-remote` shows the branch at `81b3c483a8cf7a6854883cc203ab3ae472a2efdc`, equal to local HEAD | |
| Stage results | sub-agent reports; author's reading of raw rows (line B S6, S3) | [REPORTED] plus partial [OBSERVED] | Same model family; no human review |

Not run: any repository test (no code changed); any re-run of S1, S2, S4, S5; any run of the real checker (`check_addendum4.py` needs 8 inputs absent here).

## 14. Environment / Tooling Assumptions

- Sandbox: Linux 6.18.x, git 2.43.0, bash 5.2.21, Python 3.13.18; curl/libcurl 8.5.0 with OpenSSL 3.0.13 (S3's environment); `ip` not installed (S3 brings `lo` up with a SIOCSIFFLAGS ioctl); `unshare -rn` works; binding 127.0.0.1:443 works as root.
- Test method for F14/F15: loopback only, network namespace, proxy variables removed (`NO_PROXY=127.0.0.1`), `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0`, self-signed certificate with SAN `github.com`, `evil.test`, `127.0.0.1`, `http.curloptResolve` through `GIT_CONFIG_COUNT/KEY/VALUE`, `git http-backend` behind a Python TLS server, dummy credentials only. Block copies differ from the original only in the `T=`/`H=` (and, for synthetic origins, `CANON=`) lines. Results are specific to git 2.43.0 and libcurl 8.5.0.
- GitHub access: plain `git` over HTTPS works with the sandbox's preconfigured credentials (do not print them). `gh` fails (its `GH_TOKEN` is invalid). `commit.gpgsign` is true with an empty signing-key file; commits still succeed; signature verification is not configured.
- Sub-agent reviewers: free-plan 5-hour usage limit cuts a run off after about 2 to 13 minutes of heavy use; resets seen 1:30 UTC and 6:50 UTC; subagents cannot write report files (save the returned text with `tools/extract_handback.py`).
- Secrets: none are recorded here. The credential-like string in the owner's preference settings is neither used nor copied.

## 15. Unresolved Questions / Risks / Blockers

| # | Issue | Evidence | Options | Disposition | Safe to continue? |
|---|---|---|---|---|---|
| Q1 | **Lost raw evidence of S1, S2, S5** (sandbox reset 2026-11-12). Their reports are [REPORTED] without surviving raw evidence. B and E are corroborated by retained TLS evidence (S3, both lines); A and G(1–3) rest on S1's report plus the author's pre-reset re-run of the G(1) extraction | v1 §15 Q1 | accept; or the owner orders regeneration as new runs (never replacing the reports) | open; owner's | Yes |
| Q2 | Same-family reviewers; the owner's assessment `6f5b2de4` recommends a human or a different model family | | continue; give the package to a human or another model | owner's | Yes, state the limitation |
| Q3 | Does a credential-free URL printed by git (`From https://github.com/…`) violate brief E literally? | S2-04, S1-I1, S4 INC-1, S5 F-S5-3; S8 | owner reading | open; E is FAIL regardless | Yes |
| Q4 | S4's C-1 versus S6 claim 8 (ls-remote text real git never emits) | S4, S6, S8 | owner reading | open; do not change a stage status silently | Yes |
| Q5 | Four ambiguous D rows (D15, D17, D30, D37) | S4 | owner reading of "added by the handoff commit" | open | Yes |
| Q6, Q7 | TLS reproductions of F14 and of item E | v1 | — | **CLOSED** by S3 (line A session 4, line B) and S8 | — |
| Q8 | S4 could not re-verify the package zip after the reset | S4 §1 | accept | open | Yes |
| Q9 | Owner decisions: one bounded correction of rev3; who performs the review; adopting checker v2; D-1…D-11; next-session entry point and ledger wording; PR #90 rebase | Addendum 6 §6 | | owner's | Yes |
| Q10 | A plaintext credential string sits in the owner's preference settings | system record | owner removes or revokes it | not used or recorded | Yes |
| Q11 | Two lines of work exist (the original conversation duplicated sessions 2 to 5) | section 6 | DEC12; owner may prefer otherwise | open | Yes |
| Q12 | Finding ids differ between lines; no mapping yet | section 6 | build it mechanically in the consolidation | open | Yes |
| Q13 | REV2 remediation zip (`g4-fix`, not accepted by its own governance line); 20 of 21 failing tests labelled Windows-specific vs the platform-independence requirement | `INPUT_REV2_ZIP_NOT_REVIEWED_2026-11-23.txt` | owner decides whether to review it separately | unreviewed input | Yes (not part of A–I) |
| Q14 | F15 on an accepting server: line B saw no token, line A saw `From <url>?token=…` | section 6 | line A stands; optionally test a fetch that updates a ref | open | Yes |
| Q15 | 18 undecided criterion-I rows (line A S7): how fenced, quoted or hidden status text should be treated | `session3_…` | owner reading | open | Yes |
| Q16 | S8 found Addendum 6's sentence that the brief guards against an accidental wrong remote, not a hostile environment, is **not in the brief** (A6-C29 CONTRADICTED); also narrow "attacker model" understated (URL credentials are sent to the other host) | `session5_…` | Addendum 7 records the correction explicitly; Addendum 6 is not edited | open | Yes |
| Q17 | `main` advanced 87 commits since 2026-11-08; project-state statements in Addendum 7 need a fresh read of `CURRENT_STATE.md` and `KNOWN_ISSUES.md` | section 7 | re-read before writing | open | Yes |

## 16. Relevant Information / References

- **Version 1 §16** (package contents and hashes, block facts for line 15/16, the F14 method on libcurl, the brief items A–I, project memory) is still accurate; read it. The package contents: brief `README_FIRST_REVIEW_BRIEF.md`, `base/handoff.md`, `rev2/verify_block.sh`, `rev3/verify_block_rev3.sh` (38 lines, sha256 `e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53`), the P1d rev3 patch, `optional_item_I/` (Addendum 4 and `check_addendum4.py`).
- **Assignment** (verbatim): `wip/g4-staged-review-handoff-2026-11-13/recovered/harness/ASSIGNMENT_full_verbatim_ab8e1439.txt` (also v1 Appendix A). Governing prompt `76f58f1e`: `…/recovered/prompts_and_index/GOVERNING_PROMPT_76f58f1e-attachment.txt`.
- **Addendum 6** and the earlier addenda, the checkers and the status checker v2: the save branch `wip/g4-work-save-checkpoint-nov2026` (`reports/`, `tooling/`).
- **Line A READMEs** (read first): `session2_2026-11-14/README_SESSION2.md`, `session3_2026-11-15/README_SESSION3.md`, `session4_2026-11-15/README_SESSION4.md`, `session5_2026-11-16/README_SESSION5.md`, `README_PUSH_NOTE.md`.
- **Project instructions:** `PROJECT_INSTRUCTIONS.md` in the repository (18.4.8 handoff, 18.4.9 fresh-session recovery, 16.5 closure criteria, 24 audit discipline). **Project memory:** Moncif's project "ocbrain" holds the audit history to 2026-10-24 and the G4 standing requirements.
- **Checker caution:** S7 showed the criterion-I checker (`check_addendum4.py`) accepts conflicting or hidden status text (unanchored substring test at line 26, universal-newline last-line test, no scan for duplicate status lines). Do not treat a checker PASS as proof that Addendum 7's status lines are right; test them with exact string comparison.

## 17. Next Steps

There is **no owner decision needed before step 1.** (Version 1's step 0, the push question, is done: U15.) Do not run S1 to S8 again.

1. **Verify** per section 18. Expected result: remote tips as in section 7; both lines present. Resolve any mismatch first and record it.
2. **Read the primary record in full.** The original conversation read only the READMEs and hashes of line A's S6, S7, S3, S8. Read `session2_…/REPORT_S6.md`, `session3_…/REPORT_S7.md`, `session4_…/REPORT_S3.md`, `session5_…/REPORT_S8.md`, then `recovered/stage_reports/REPORT_S1.md`, `REPORT_S2.md`, `REPORT_S4.md`, `REPORT_S5.md`. Then read line B's README and reports for deltas only. Expected: the section 6 matrix.
3. **Reconcile (R19).** Build a mechanical table mapping every finding id of both lines to one record; keep stage-local ids as aliases; mark anything that appears in one line only. Do not edit any report. Verification: every finding id in both registers appears once.
4. **Compile the A–I matrix and the verdict (R5, R7).** One status per criterion from the stage reports, quoted unchanged, line A primary. Read the assignment's verdict rule and apply it mechanically. Expected: not PASS. Do not average or soften; where a status depends on an owner reading (C, D, I) keep the reported status and flag it.
5. **Findings register (R6).** Assign F-numbers from F16 on to every new finding (substantive and minor), with the ten evidence fields taken from the stage reports (by reference plus a compact table). F1–F15 keep their numbers and the author's statuses (section 6 of v1, copied below).
6. **Owner decisions list.** Q3, Q4, Q5, Q9, Q13, Q15, Q16 and any reading of the brief that the stages left open. Do not decide them.
7. **Write Addendum 7 (R18)** as a **new** file (Addenda 1–6 are not edited) with: package integrity; independence declaration (same-family sub-agents, no human); environments; F14/F15 assessment; the matrix; the register; the unreviewed list (include: real GitHub, other git/libcurl versions, IPv6 and other URL variants, credential helpers, the lost raw evidence of S1, S2, S5); the verdict; reproducibility; the explicit correction of Addendum 6's A6-C29 sentence and of any other CONTRADICTED or SUPERSEDED claim (Q16); the line A / line B reconciliation. Add a mechanical checker (reuse `check_addendum6.py` and the status checker v2 from the save branch **and** an exact string test for the last line, because of the checker caution in section 16), an evidence bundle, `SHA256SUMS`, and a delivery zip.
8. **Verify Addendum 7:** recompute every hash cited, re-run the checker and the exact last-line test, re-read every status statement, confirm the three governing statuses are unchanged. Expected: the file ends with exactly the required statement (section 4).
9. **Return to the owner** with the decisions in step 6. Do not start a correction of rev3, the checker or the patch. Do not push unless asked; if asked, push to a **new** `wip/` branch (non-force), scan first, and never touch the save branch, line A's branch, REV2, REV3, `main` or PR #90.

## 18. Resume Instructions

First actions of the next session, in order:

1. Read the repository's `PROJECT_INSTRUCTIONS.md`, then this file completely, then `recovered/harness/COMMON_PREAMBLE.md` (on line A's tree).
2. `git fetch origin wip/g4-staged-review-handoff-v2-2026-11-24` and check it out. Verify: the tip's parent is `81b3c483a8cf7a6854883cc203ab3ae472a2efdc` and that commit's parent is `4125320eb21cdad98dd2a6f189da5d6be30a955f`.
3. Verify the remote: `git ls-remote origin refs/heads/main refs/heads/docs/g4-fts-errata-handoff-oct2026 refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026 refs/heads/wip/g4-work-save-checkpoint-nov2026 refs/heads/wip/g4-staged-review-handoff-2026-11-13 refs/pull/90/head`. Expected: `main` `ef1351ff…` or later (record the new tip; an advance alone is not a contradiction), `d963daa5…`, `9407db5a…`, `8fd8f4da…`, `4125320e…`, `9407db5a…`.
4. **List newer branches:** `git ls-remote --heads origin 'wip/*'`. If any branch exists that this file does not name, read its README before anything else (a previous session lost two days to this, section 12).
5. Verify checksums: `sha256sum -c` of `SHA256SUMS_session6.txt` (inside `session6_…`), of each `SHA256SUMS_session2…5.txt` and of the root `SHA256SUMS.txt` of line A's `wip/…` directory, each from its own directory; verify the package hash `391eb0a0…ce2286` and the report hashes in section 8.
6. Resolve any material mismatch before changing anything; record it as a deviation (18.4.11).
7. Begin at section 17, step 2.

Do not repeat completed work; do not edit any report; do not change any status.

## 19. Transfer Status

**TRANSFER READY**

Basis (checked at the time of writing, section 13): the implementation checkpoint `81b3c483…` is committed, pushed and verified on the remote; this handoff is committed in the next commit on the same branch (pushed and verified by the author after writing; a fresh session must re-verify per section 18); the original prompt and the later instructions are preserved; the requirement, decision and investigation records are present; the exact next action is defined.

Limits, disclosed so that nothing is misread (none blocks the remaining work):
- The stage reports are [REPORTED] by same-family sub-agents; no human reviewed them.
- Raw evidence of S1, S2 and S5 is [LOST] (Q1). Their statuses rest on the reports; B and E are also supported by retained S3 evidence.
- Line A's full reports for S6, S7, S3, S8 were not read by the author of this file (only READMEs and hashes); step 2 of section 17 requires it.
- Owner-held inputs are not in Git except the package copy (section 8); the REV2 zip is unreviewed input.
- This is a work-in-progress transfer of an **unfinished** review, not a completed review and not a verification result.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
