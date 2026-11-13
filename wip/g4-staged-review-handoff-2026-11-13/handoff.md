# Session Handoff

Governing statuses, unchanged throughout this session and not changed by this file: **G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.** No implementation is authorized. This handoff is a transfer record, not an authority (PROJECT_INSTRUCTIONS 18.4.9): a fresh session must verify it against the live repository and the companion files before acting.

Labels used below: **[OBSERVED]** produced by a command in this session; **[REPORTED]** stated by a text or by a sub-agent reviewer and not reproduced by the author; **[DERIVED]** a conclusion from observations; **[LOST]** existed during the session and is no longer available (section 15).

## 1. Handoff Metadata

- Handoff version: 1
- Created at: 2026-11-13T09:08:27Z
- Workstream: OCBrain v4.1 Kernel v1.0, Phase G4 / FTS-correctness documentation and audit study. Current sub-task: one complete independent A–I review of the unchanged REV3 verification package (the `verify_block_rev3.sh` block and patch P1d rev3), run here in stages.
- Task identifier, issue or finding: findings F1–F15 (Addenda 1–6); review assignment `ab8e1439` ("Independent Review Assignment — G4 REV3 Complete A–I Assessment"); internal tasks #41 and #45–#49.
- Source session purpose: documentation reconciliation of the G4 FTS handoff, then proposal and review of a stronger handoff verification block (rev3), then the staged independent review of that block.
- Transfer status: **TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED.** This file and the companion bundle exist only as files that the owner downloaded; neither is committed or pushed. Section 19 gives the full state. The owner chose a file-based transfer on 2026-11-12 ("i've downloaded all the files generated in this session, so just create a handoff file and i'll pass all of these to a new and fresh session").

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

## 4. Goal, Scope & Success Criteria

### Goal
Complete one independent technical review of the **unchanged** REV3 verification package, criteria A–I, in two phases: Phase A blinded (original package only, no Addendum 6), Phase B adversarial comparison with Addendum 6 and the F14/F15 evidence. Deliver one A–I matrix with exactly one status per criterion plus the deliverables listed in Appendix A (package integrity, independence declaration, environment, F14/F15 assessment, findings register with ten evidence fields per finding, unreviewed list, verdict, reproducibility).

### In scope
- Running the remaining review stages (S6, S7 in Phase A; S3, S8 in Phase B), consolidating the stage reports unchanged, applying the assignment's verdict rule mechanically, and writing Addendum 7.
- Recording any substantive finding, preserving its evidence, and returning it for owner disposition.

### Out of scope (do not do)
- Any correction, edit or rewrite of rev3, the block, the patch, REV2, REV3, `main`, PR #90 or any remote branch. Any apply of P1d. Any commit or push unless the owner asks.
- Any change to G4, G5–G8 or freeze-readiness statuses. Any D-1…D-11 decision. Any reinterpretation of DECIDED or PROPOSED as ACCEPTED. Declaring G4 resolved.

### Success criteria (from the assignment)
- Package full SHA-256 equals `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`.
- All criteria A–I have exactly one status; Phase B comparison with Addendum 6 is recorded; discrepancies are independently investigated.
- The overall verdict is not PASS if any substantive finding is unresolved or any mandatory criterion is BLOCKED or NOT RUN. A report marked IN PROGRESS is not a completed review.
- Final statement: "G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED."

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | One complete independent A–I review of the unchanged package, review-only | `ab8e1439` | **IN PROGRESS** | Stage reports S1, S2, S4, S5 (companion bundle) | A, B, C, D, E and G(1–3) reviewed; F, G(4), H, I not run |
| R2 | Verify package full SHA-256 | `ab8e1439` | **VERIFIED** (S1, S2, S5); S4 partial | S1/S2/S5 reports section 1 | S4 verified it before the reset and could not re-verify the zip afterwards (its block copy matched the recorded block hash) |
| R3 | Phase A blinded A–I | `ab8e1439` | **IN PROGRESS** | Section 6 matrix | S6 (F, G(4), H) and S7 (I) not started |
| R4 | Phase B: compare with Addendum 6; full loopback-TLS false-PASS reproduction; HTTPS username-token case | `ab8e1439` | **OPEN (NOT RUN)** | none | S3 and S8 not started. S2 (Phase A) already reproduced a printed PASS on loopback TLS (REPORTED) |
| R5 | One A–I matrix, one status per criterion | `ab8e1439` | **OPEN** | Interim matrix in section 6 | Compile after all stages |
| R6 | Deliverables: integrity, independence declaration, environments, F14/F15 assessment, findings register (10 fields), unreviewed list, verdict, reproducibility | `ab8e1439` | **OPEN** | | Merge stage reports unchanged |
| R7 | Verdict not PASS with an unresolved substantive finding or a BLOCKED/NOT RUN mandatory criterion | `ab8e1439` | **OPEN** | | Already true: B and E FAIL; F, G(4), H, I NOT RUN |
| R8 | On a substantive finding: record, preserve evidence, stop correction work, no new rewrite, return for owner disposition | `ab8e1439`, U4 | **IMPLEMENTED, evidence preservation impaired** | | No correction was attempted. Raw evidence of S1, S2 and S5 was lost in the reset ([LOST], section 15) |
| R9 | Do not modify REV2, REV3, `main`, PR #90 or any remote branch | `ab8e1439` | **VERIFIED** 2026-11-12 | `recovered/verification_2026-11-12_post_reset.txt` | Tips unchanged since 2026-11-08 |
| R10 | Do not reinterpret DECIDED/PROPOSED as ACCEPTED; do not declare G4 resolved | `ab8e1439` | **VERIFIED** (nothing changed) | | |
| R11 | Statuses G4/G5–G8/freeze unchanged; every deliverable ends with the status line | `76f58f1e`, owner rule | **IMPLEMENTED** | | Keep doing it |
| R12 | Gate statuses exactly PASS/FAIL/BLOCKED/NOT RUN | `76f58f1e` | **IMPLEMENTED** | | |
| R13 | Independence: independent review or SELF-REVIEW ONLY; no false independence | `76f58f1e`, `ab8e1439` | **IMPLEMENTED with limitation** | stage report declarations | Reviewers are independent-context sub-agents of the **same model family** as the author; not human. The owner's attached assessment recommends a human or a different model family (`6f5b2de4`). Owner has not decided otherwise than U8 |
| R14 | No secrets in logs or commits; do not use the credential-like string in the preference settings | project instructions | **IMPLEMENTED** | scan 2026-11-12 (section 13) | |
| R15 | No force-push, no history rewrite | project instructions | **IMPLEMENTED** | | |
| R16 | Never execute anything extracted from an archive | owner rule | **IMPLEMENTED** | | Reviewers copied block files out and ran only copies; package files were never executed in place |
| R17 | Handoff per 18.4.8 | project instructions | **IN PROGRESS** | this file | Transfer status in section 19 |

## 6. Current Verified State

### Staged review: stage table (reconstructed from the conversation record; the original ledger file was lost)

| Stage | Scope | Phase | Status | Result |
|---|---|---|---|---|
| S2 | B URL parsing and identity | A | COMPLETE | **B = FAIL** |
| S5 | E credential confidentiality (non-TLS) | A | COMPLETE | **E = FAIL** |
| S1 | package integrity, A, G(1–3) | A | COMPLETE | **A = PASS; G(1) PASS, G(2) PASS, G(3) PASS** |
| S4 | C and D | A | COMPLETE | **C = PASS** (caveats C-1, C-2); **D = PASS** (four ambiguous rows) |
| S6 | F + G(4) prose claims + H | A | **NOT STARTED** | |
| S7 | I (may open `optional_item_I/`) | A | **NOT STARTED** | |
| S3 | F14/F15 loopback TLS reproductions | B | **NOT STARTED** | |
| S8 | comparison with Addendum 6, discrepancies | B | **NOT STARTED** | |

### Interim A–I matrix (from completed stages only; not the final matrix)

| Criterion | Interim status | Source | Note |
|---|---|---|---|
| A | PASS | S1 | rev2 false PASS in (i) (two variants), (ii), (iii), (iv), (vi) and print-then-fail form of (v); rev3 correct FAIL in all, correct PASS on 3 baselines; scenarios built only |
| B | **FAIL** | S2 | false PASS for `?@` and `#@` origins, printed `PASS`, exit 0, against a loopback TLS git server |
| C | PASS (caveats) | S4 | 63 rows; C-1 (low, not a contract false PASS) would turn C into FAIL under a literal reading of the prose; C-2 minor false FAIL |
| D | PASS | S4 | 42 rows; D15, D17, D30, D37 contract-ambiguous, not decided |
| E | **FAIL** | S5 | git itself prints dummy tokens (27 of 68 rows); block's own lines never did |
| F | NOT RUN | | S6 |
| G | NOT RUN (G(1–3) PASS; G(4) NOT RUN) | S1; S6 | combined G is the worse of the two parts: not final |
| H | NOT RUN | | S6 |
| I | NOT RUN | | S7 |

**Mechanical consequence:** the overall verdict cannot be PASS. B and E are FAIL, and F, G(4), H, I and Phase B are NOT RUN. The review is **IN PROGRESS**, not a completed review. If it were complete as of today, rev3 would still fail its contract (B, E).

### VERIFIED (by commands run in this session, 2026-11-12 UTC, evidence in `recovered/verification_2026-11-12_post_reset.txt`)
- Remote tips: `main` `2491ae469edd6ef1267a14604c4f8f40d698f7ea`; REV2 `d963daa502de4220411d0d0c2f19f67b3ec2682b`; REV3 `9407db5a01acea9684f158caa8107fb71611a102`; save branch `8fd8f4da1caf966e550774e8e06bfe13822d55ea`. All equal to the values recorded on 2026-11-08.
- PR #90 (REST API): open, draft, base `main`, head `docs/g4-fts-correctness-handoff-rev3-oct2026` at `9407db5a…`, 3 commits, 7 files, `mergeable: true`, `mergeable_state: behind` (main has advanced 89 commits past the merge base `f13bfdefcdd197ed1f966de0b1f93037a4168af4`).
- Save branch: 201 added files; the 200 blobs listed in its `SHA256SUMS.txt` all verify (200 OK, 0 failures).
- Recovered stage reports have the same SHA-256 that I recorded for them before the reset, for S1 (`5f420a62…`), S2 (`90b06ee7…`) and S5 (`82ce292b…`). S4 (`0f53d6e5…`) had no earlier recorded hash.

### IMPLEMENTED BUT NOT VERIFIED
- Verification block rev3 (`verify_block_rev3.sh`, sha256 `e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53`, 38 lines) and patch P1d rev3 (sha256 `98468b11c2f88cfe6637f1a1f6ee88a089f60a3957a6cf6d1ea3d1522f7c2cb0`): **PROPOSED, not applied, not acceptable as it stands.** F9–F12: fixed in the proposal, not verified. F13: fixed in tooling (checker v2), not verified by anyone else.

### Reviewer findings, all [REPORTED] by independent-context sub-agents unless stated
- **F14, false PASS (S2-01…S2-03):** line 15 cuts the URL authority only at `/`. Origins `https://evil.test?@github.com/1h0lde4/ocbrain-v4.1`, `https://evil.test#@github.com/…`, `https://127.0.0.1:18443?@github.com/…`, `https://user:DUMMYTOKEN-xyz@127.0.0.1:18443?@github.com/…` and `https://2130706433?@github.com/…` were accepted as canonical; against a loopback TLS smart-HTTP server (net namespace, name mapping by `http.curloptResolve`, `GIT_SSL_CAINFO`, only `T=`/`H=` lines substituted) the **unmodified block printed `PASS at …` and exited 0** while the server saw `Host: evil.test`, `Host: 127.0.0.1:18443` or `Host: 127.0.0.1`. Negative controls (`https://github.com@evil.test/…`, `https://127.0.0.1:18443/…`) failed correctly. The `\@`, `%2f@`, `/@` forms did **not** reproduce it in this environment (git 2.43.0, libcurl 8.5.0): libcurl contacted github.com. [I spot-checked the raw stdout, server request logs, exit codes, block diff and token scan of the TLS pass before the reset; those files are now lost.]
- **F15, secret output (S5: F-S5-1, F-S5-2):** git itself prints a token that is the URL user name (`could not read Password for 'http://TOKEN@127.0.0.1:18101'`, three times per run, local 401 server) and tokens in a query string, fragment or path suffix (`unable to access '…?token=TOKEN/'`). 27 of 68 rows. The block's own echo lines never printed the token. [I spot-checked ten rows before the reset.]
- **New, not yet numbered in the F-series:** F-S5-3 (git prints `From <url>` on every fetch that updates a ref, including a PASS run; a path token appeared in a PASS run, row S13); F-S5-4 (the prose claims "credentials in the URL are ignored and never printed" and "the configured URL is not printed" are contradicted at run level); S2-04, S1-I1 and S4 INC-1 (git prints the credential-stripped URL on transport failure; whether a URL without credentials counts as a violation of brief item E is an owner/consolidation decision); S4 C-1 (the `grep -c .` and unquoted `set -- $out` pair accepts ref-line text that real git cannot emit; low); S4 C-2 and S2 minor false FAILs (real tail-matching refs, upper-case host, trailing slash and so on fail closed); S1 M2 (a failed final `ls-remote` also prints "the remote branch moved during verification (now unknown)"); S1 M4 (an unchanged §19 line of the handoff still says its own hash cannot be recorded). **Assign F-numbers when the stage reports are consolidated (Addendum 7); do not renumber F1–F15.**
- Still not reproduced by anyone: the canonical `https://TOKEN@github.com/…` 401 case (DERIVED from the same git code path as the http case; needs a TLS server, stage S3).

### Findings ledger (author's statuses, unchanged by the stage reports, which are inputs to Addendum 7)

| Finding | Status |
|---|---|
| F1–F5 (pushed wording residuals) | OPEN |
| F6 (metadata only) | not changed |
| F7 | OPEN (closure needs a verification block that passes independent review, an authorized push and a run from a fresh clone of the canonical URL) |
| F8 (the Addendum 2 P1d must not be applied) | OPEN |
| F9–F12 (rev2 block weaknesses, addressed in the rev3 proposal) | FIXED in the proposal; not VERIFIED |
| F13 (status checker v1 too weak; v2 added) | FIXED in tooling (v2); not VERIFIED by anyone else |
| F14, F15 (found in rev3) | OPEN |

### PROPOSED / DEFERRED / UNKNOWN
- PROPOSED: rev3 block and P1d rev3 patch; decisions D-1…D-11 (all OPEN, untouched); checker v2 adoption (owner's choice).
- DEFERRED: any correction of rev3 (needs the owner's go-ahead after a complete review); the PR #90 rebase (PR owner's call).
- UNKNOWN: results of F, G(4), H, I; the TLS reproduction by an independent stage; whether the author's own printed-PASS reproduction can be made (NOT RUN).

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1`
- Remote: `https://github.com/1h0lde4/ocbrain-v4.1`
- Branch: no work branch exists for this handoff. Relevant branches: REV2 `docs/g4-fts-errata-handoff-oct2026`; REV3 `docs/g4-fts-correctness-handoff-rev3-oct2026` (PR #90, draft); save branch `wip/g4-work-save-checkpoint-nov2026`.
- Base branch: `main` at `2491ae469edd6ef1267a14604c4f8f40d698f7ea` ("Merge pull request #106 from 1h0lde4/docs/ctx-auth-002-closure-oct2026"). REV2 and REV3 are based on `f13bfdefcdd197ed1f966de0b1f93037a4168af4`, 89 commits behind main.
- HEAD before handoff: the sandbox clone `/home/claude/ocbrain-v4.1` is a fresh clone on `main` `2491ae46…` (the earlier clone, worktrees and the local save branch were lost in the reset). Remote-tracking refs for REV2, REV3 and the save branch were fetched on 2026-11-12.
- Transfer commit (implementation checkpoint): none for this stage; no implementation exists. REV2's own transfer commit is `eca2b96521fba8cf792ea16a58be997e4f949356` (2026-10-24) and its handoff commit is `51564e34c18e5cc908cf517000ebc9bd41eaf194`; the REV2 tip is `d963daa502de4220411d0d0c2f19f67b3ec2682b` (one follow-up commit of 2026-10-31 15:16 UTC, P1/P1b).
- Handoff commit: **none** (this file is not committed).
- Parent commit of handoff commit: not applicable.
- Working tree status: clean (fresh clone, `main`). No uncommitted repository work exists.
- Relevant untracked files: none in the repository. Companion files are outside the repository (section 8).
- Relevant ignored files: none.
- Submodules or nested repositories: none known.
- Remote push status: the only push of this study's work after the REV2/REV3 pushes of 2026-10-31/11-01 is the save branch of 2026-11-08 (commit `8fd8f4da1caf966e550774e8e06bfe13822d55ea`, parent `main` `2491ae46…`, 201 files under `wip/g4-work-save-2026-11-08/`, non-force). Nothing was pushed after that.
- Remote verification status: remote tips, PR #90 and the save branch blobs re-verified 2026-11-12 (section 6).

| Branch / PR | Tip | Content |
|---|---|---|
| REV2 | `d963daa502de4220411d0d0c2f19f67b3ec2682b` | 3 commits over base; 5 files: `handoff.md` (mode 100644, blob `f3434b71516445856e106b5e12d48801b643d057`) plus packet REV2, evidence-label addendum REV2, decision ledger, audit report |
| REV3 (PR #90) | `9407db5a01acea9684f158caa8107fb71611a102` | 3 commits (`2dd2e7bb…` preserve REV3 handoff and next-session gate; `9bb2443b…` P2 digest-discrepancy erratum; `9407db5a…` P3 digest Value A→B at three locations); 7 files, +391 lines |
| Save branch | `8fd8f4da1caf966e550774e8e06bfe13822d55ea` | `reports/` (11 files, Addenda 1–6 and earlier reports), `evidence_records/` (120, records through I81), `evidence_bundles/` (10 zips), `proposed_patches/` (10), `verification_blocks_and_tests/` (9), `tooling/` (37), `review_package/` (1 zip), README and `SHA256SUMS.txt` |

## 8. Active Files / Modified Files / Artifacts

**Repository files modified in this session segment: none.** Earlier segments changed only REV2 (P1/P1b) and REV3 (P2/P3), both pushed non-force before 2026-11-08.

**Companion bundle** (`g4_staged_review_handoff_bundle_2026-11-13.zip`; the owner receives it with this file). Everything the next session needs that is not in the repository or in the owner's earlier downloads:

| Path in the bundle | What it is | Why it matters | SHA-256 |
|---|---|---|---|
| `handoff.md` | this file | entry point | (in `SHA256SUMS.txt`) |
| `recovered/stage_reports/REPORT_S1.md` | S1 final report | A and G(1–3) | `5f420a62d055997cf12726c5ff8d6a67201549783e03c9a9279c3032c9edd3a2` |
| `recovered/stage_reports/REPORT_S2.md` | S2 final report | B, F14 | `90b06ee70d679080624c0cdb33728fb01adc78ecd9755551aef395ee4f9d1f4f` |
| `recovered/stage_reports/REPORT_S4.md` | S4 final report | C, D | `0f53d6e5165970936fb462e70717c352fb00d7a842978b9627f859da17bc9267` |
| `recovered/stage_reports/REPORT_S5.md` | S5 final report | E, F15 | `82ce292b8fd0bb221fd53931f5b9c43f65eabfe149e264b783eabdb5ccb6691d` |
| `recovered/harness/COMMON_PREAMBLE.md` | the rules every reviewer stage must read (reconstructed byte-exactly: 6,711 bytes, the size recorded before the reset) | the Phase A independence, safety, evidence and report rules | `c7f7cdd88e0cdb766f07de051b2c23e03ed8decaf639cec917b87949ad8852f7` |
| `recovered/harness/ASSIGNMENT_full_verbatim_ab8e1439.txt` | the review assignment | governing task of this stage (also Appendix A) | `0eaef46eec601ab754b40b4156b8949a0f048b6b559ab0d2c61e2b2024e2ded5` |
| `recovered/harness/prompts_used/` | the four sub-agent prompts as sent (S2 final-report pass, S5, S1, S4) | templates for S6, S7, S3, S8 | S2 `0a27398b…`, S5 `ffef50b0…`, S1 `ed2e370c…`, S4 `0de84325…` |
| `recovered/prompts_and_index/GOVERNING_PROMPT_76f58f1e-attachment.txt` | governing prompt | section 2 | `5198c7e4c1ee5f7952709621bce5a624d7be8c356519aece12378b949d1b39a6` |
| `recovered/prompts_and_index/attachments_index_saved-uploads.jsonl` | the owner's upload index (name, size, sha256 per attachment) | Appendix B | `480de7cba9a4e0ad4faf69fb5f18fe4e4b557e46af51f34202f6a2eb8464a862` |
| `recovered/stage_S4_work/stage_S4_scripts_and_evidence.zip` | S4 scripts and evidence (812 files); `work/` excluded | the only reviewer evidence that survived | `86776be97a8425856a941c1d22d05e8e524937392962cd6d2fa1104fc6e5a84a` |
| `recovered/verification_2026-11-12_post_reset.txt` | commands and output of the post-reset verification | section 13 | `410ad54a202e258b4f13b122320c2fa5997a45f1e6efcb6a50607715629d0679` |
| `tools/extract_handback.py` | script that recovered the reports from the conversation record | repeat the method | in `SHA256SUMS.txt` |
| `SHA256SUMS.txt` | hashes of every file in the bundle | integrity | |

**Files the owner already holds** (re-attached to this session on 2026-11-12; hashes in Appendix B and the index file): the review package `g4_rev3_independent_review_package.zip` (sha256 `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`); `verify_block_rev3.sh`; the patch; the Addendum 4, 5, 6 reports and delivery zips with their evidence bundles; the original REV3 ZIP (`…D2_D5_FETCH_HEADER_REV3.zip`, sha256 `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc`, 254,581 bytes; it equals "Value B" of the digest erratum). Addenda 1–3, the earlier reports and all evidence records I01–I81 are in the save branch (not in the owner's re-attached list).

**Not in the bundle and not in Git (lost, section 15):** the raw evidence and scripts of stages S1, S2 and S5; evidence records I82–I88; the working ledger and launch log; the earlier scratch directories.

## 9. Changes Made

- **Repository:** none in this session segment.
- **Behavior, interfaces, schema, architecture, governance, security:** none.
- **Tests and documentation in the repository:** none.
- **Review work products created** (outside the repository): the four stage reports; the S4 evidence; this handoff and bundle. Reviewer reports were saved from the sub-agents' hand-back text, extracted byte-for-byte from the conversation record; I did not edit them. The sub-agent harness refuses report files written by sub-agents ("Subagents should return findings as text, not write report files"); S1, S2, S4 and S5 therefore returned their reports as text.
- **Earlier changes (for orientation):** REV2 got P1 and P1b (commit `d963daa5…`). REV3 got P2 and P3 (`9bb2443b…`, `9407db5a…`). The save branch was added on 2026-11-08. Addenda 1–6 and their evidence are in the save branch and the owner's downloads.

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Rationale / evidence | Reopen condition |
|---|---|---|---|---|---|
| DEC1 | Run the independent review here, in stages, with sub-agent reviewers | DECIDED (owner U8) | owner | owner's answer "Run it here in stages" | Owner prefers a human or a different model family; the stage reports record the same-family limitation |
| DEC2 | Split the review into eight stages: Phase A S2 (B), S5 (E non-TLS), S1 (A + integrity + G(1–3)), S4 (C, D), S6 (F, G(4), H), S7 (I); Phase B S3 (TLS reproductions), S8 (comparison) | author decision | author | a single sub-agent run ends on the usage limit after about 2–13 minutes, so one stage fits one window | A better partition |
| DEC3 | G is split: G(1–3) patch integrity in S1; G(4) prose-claim comparison in S6; combined G = the worse of the two | author decision | author | the brief's item G has patch-integrity and prose parts | Owner reads G otherwise |
| DEC4 | Phase A reviewers must not read author results (preamble rule) | author decision under the assignment's blinding rule | `ab8e1439` | blinded phase | none |
| DEC5 | Stage reports are accepted as returned and are consolidated unchanged; the author spot-checks but does not edit them | author decision | `ab8e1439` | independence | none |
| DEC6 | When the sub-agent harness refused a report file, I saved the returned text byte-for-byte instead of asking the agent to work around the refusal | author decision | tool refusal | respects the harness rule | none |
| DEC7 | rev3 stays PROPOSED and not acceptable; no rewrite; F7 stays OPEN | DECIDED by the stopping rule U4 | owner (U4) | F14, F15 and the stage findings | Owner allows one bounded correction after a complete review |
| DEC8 | No push after 2026-11-08 | author-adopted | author | U6 was a one-time request | Owner asks for a push (recommended in section 17, step 0) |
| DEC9 | D-1…D-11, the next-session entry point, the ledger wording and the PR #90 rebase stay with the owner | DECIDED (owner-reserved) | owner / PR owner | project rules | none |
| DEC10 | Treat "git prints a URL without credentials" as a possible E violation only for the consolidator and owner to rule on; E is FAIL regardless because tokens were printed | OPEN | owner | brief E says no URL "including messages printed by git itself" | Owner's reading of E |

Do not reopen DEC1–DEC9 without one of: a verified contradiction, new evidence that invalidates the basis, a dependency change, a governance or security need, a higher-priority authority, or an explicit owner request.

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| Live repository and PR state | remote tips, REV2/REV3 diffs, PR #90 (REST), save branch blobs | consistent with 2026-11-08 records | `recovered/verification_2026-11-12_post_reset.txt` | any remote change |
| REV3 ZIP authentication, digest discrepancy | earlier sessions (Addenda 1–2, P2/P3) | the supplied ZIP's SHA-256 is Value B `f9ee6265…e509cc`; Value A differs at one character (offset 23) and was recorded wrongly in three places; REV3 P3 corrected it | save branch `reports/`, REV3 erratum | new evidence about the original ZIP |
| REV2 vs REV3, authority matrix, D-1…D-11 audit | Addenda 1–3 | no decision promoted; details in the reports | save branch | any claim of decision authority |
| Rev2 block weaknesses F9–F12, rev3 block, checker v1/v2 | Addenda 4–5 | rev3 addresses the rev2 scenarios tested (23 leak cases, s01–s16); proposal only | Addendum 4, 5 | reviewer findings |
| Fifth independent-context launch | Addendum 6 | partial report; F14, F15 reported; author reproduced mechanisms on loopback (string level, libcurl destination, token leaks over http) | Addendum 6, I76–I81 | |
| Stage S2, criterion B | 93 string-level forms plus 8 http forms; whole-block runs without a git server; simulated transport; real loopback TLS git server | B = FAIL (F14 reproduced) | `REPORT_S2.md` (raw evidence lost) | |
| Stage S5, criterion E | 68 rows over http, dead ports, local paths, ssh double, insteadOf | E = FAIL (F15 reproduced; more shapes) | `REPORT_S5.md` (raw evidence lost) | |
| Stage S1, criterion A and patch integrity | 14 scenarios (plus baselines) against rev2 and rev3; extraction and `git apply --check` | A PASS; G(1–3) PASS | `REPORT_S1.md` (raw evidence lost); the author independently re-ran the G(1) extraction and `git apply --check` before the reset (match) | |
| Stage S4, criteria C and D | 63 ls-remote rows, 42 handoff.md rows | C PASS (caveats), D PASS (4 ambiguous) | `REPORT_S4.md`; evidence zip in the bundle | |
| Not yet investigated | criteria F, G(4), H, I; Phase B | | | |

## 12. Failed Attempts / Dead Ends

| Approach | Result | Cause | Retry? |
|---|---|---|---|
| Single sub-agent run for a whole review stage | ended by the 5-hour usage limit after about 2–13 minutes (nine launches over five stages, plus five earlier launches) | plan-level limit | No. Keep one criterion group per stage; require an early provisional report |
| Asking sub-agents to write `REPORT_<stage>.md` | the Write tool refused ("Subagents should return findings as text…") | harness policy | No workaround. Take the returned text and save it by extraction |
| Assuming that a limit error means instant failure | wrong: runs lasted 2–11 minutes before the limit; partial work was on disk | I read the error and not the file timestamps | Read the stage directory first |
| `SendMessage` to resume a cut-off agent | works after the limit window resets; the resumed agent keeps its context and returns the report as text | | Yes, preferred over a fresh launch |
| Keeping all working files in the scratchpad only | the sandbox rebuild wiped it ([LOST]) | no push or delivery of the stage work | No. Deliver or push (with the owner's permission) after each stage |
| A download link inside an artifact | blocked by the viewer | artifact sandbox | Use the `downloads` capability; or just send the file |

## 13. Verification Evidence

Post-reset verification (author, 2026-11-12 ~23:57 UTC, git 2.43.0): all of it is in `recovered/verification_2026-11-12_post_reset.txt`.

| Check | Command (summary) | Result |
|---|---|---|
| Remote tips | `git ls-remote origin refs/heads/main …` | four tips as in section 6: passed |
| REV2/REV3 contents | `git log`, `git diff --stat` against the merge base | REV2 5 files; REV3 7 files: passed |
| PR #90 | `gh api repos/1h0lde4/ocbrain-v4.1/pulls/90` | open, draft, 3 commits, 7 files, head `9407db5a…`: passed. (`gh pr view` fails here: the GraphQL route is blocked; use the REST API) |
| Save branch integrity | `git archive` to a temp dir, `sha256sum -c SHA256SUMS.txt` | 200 OK, 0 failed: passed |
| Recovered stage reports | extraction from the conversation record; hash comparison with the hashes recorded before the reset | S1, S2, S5 equal: passed; S4 not comparable |
| Preamble reconstruction | 6,711 bytes equal to the size recorded before the reset | size matches; no pre-reset hash was recorded, so equality of content is **not** proven |
| Secret scan of the bundle | pattern scan for GitHub token shapes | see the line at the end of section 13 |

Not performed after the reset: the author did **not** spot-check the S4 report against its evidence (S4 is [REPORTED] only). Pre-reset spot checks of S2, S5 and S1 (records I86, I87, I88, now lost) agreed with those reports on the points listed in section 6.

Stage-level evidence is in the four reports: each lists its commands, rows and tool versions. Tool versions seen: git 2.43.0 (libcurl-gnutls 8.5.0, GnuTLS 3.8.3), GNU bash 5.2.21, Python 3.13.16 (3.13.18 after the reset), curl 8.5.0, OpenSSL 3.0.13.

Secret scan of the bundle (2026-11-13T09:08:27Z): seven credential patterns (GitHub token shapes `gh[opsu]_…` and `github_pat_…`, AWS key id, PEM private-key header, `Authorization:` header, `x-access-token:`, `sk-…`) over 820 members: every file plus all 812 members of the S4 zip, read as data and never executed. One hit: `recovered/stage_reports/REPORT_S1.md` line 80, `x-access-token:DUMMYTOKEN-xyz`, a synthetic test string used by reviewer S1 and not a credential. No real secret found. The credential-like string that sits in the owner's preference settings was not used, copied or recorded anywhere.

## 14. Environment / Tooling Assumptions

- Sandbox: Linux x86_64 (kernel 6.18.44), root, `unshare -rn` available (loopback-only net namespace), binding 127.0.0.1:443 works as root. Real `ssh` and OpenSSH are not installed (reviewers used a logging ssh double).
- Network: egress through an allowlist; outbound HTTPS only via the session proxy. Reviewers must unset proxy variables for loopback tests and use `NO_PROXY=127.0.0.1`.
- Git config for tests: `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0`, fixed author and committer variables.
- Sub-agents: independent-context sub-agents of the same model (`claude-sonnet-5-5`), spawned with the Agent tool; each run is cut by a 5-hour plan limit after a few minutes; limit windows reopen later (observed reset times: 5:30am, 1:20pm, 2am, 1:40pm, 6:40pm UTC on various days). `SendMessage` to the agent id resumes it. Sub-agents cannot write report files; they return text.
- `gh`: `gh pr view` (GraphQL) is blocked; `gh api` REST works.
- The scratchpad directory is **not durable**. Copy anything that must survive.
- No secrets are needed for any stage. Never put a token into a URL used for tests; use dummy strings (`DUMMYTOKEN-xyz`).

## 15. Unresolved Questions / Risks / Blockers

| # | Issue | Evidence | Options | Disposition | Safe to continue without resolution? |
|---|---|---|---|---|---|
| Q1 | **Sandbox reset.** Between 2026-11-12 00:49 and 09:02 UTC the whole scratchpad was wiped (the S4 reviewer reported the same mid-run; its Python also changed from 3.13.16 to 3.13.18). **Lost:** raw evidence and scripts of S1, S2, S5 (the S2 TLS server and 93-form harness, the S5 token matrix, the S1 case harness); records I82–I88; the ledger and launch log; all earlier scratch directories and delivery working copies; the local clone state. **Kept:** remote branches (including the save branch with I01–I81), the owner's downloads, the four reports (recovered), S4's scripts and evidence, the prompts. | this file; `ls` after the reset | (a) accept the reports as the record; (b) re-run S1/S2/S5 later to regenerate raw evidence, as new runs with new ids, never replacing the original reports; (c) push the bundle to the save branch (owner's permission) | Owner's call | Yes, for S6, S7, S3, S8. The reports of S1, S2 and S5 are [REPORTED] without surviving raw evidence; say so in Addendum 7 |
| Q2 | **Reviewer independence.** All stages are same-family sub-agents; the owner's attached assessment recommends a human or a different model family. | `6f5b2de4` | continue as decided (U8); or give the package to a human; or a different model | Owner's choice (not re-asked) | Yes, with the limitation stated |
| Q3 | **Do URLs without credentials printed by git violate brief E?** S2-04, S1-I1, S4 INC-1, S5 F-S5-3 | `REPORT_S5.md` | owner rules | open | Yes: E is FAIL regardless |
| Q4 | **S4's C-1** (glob and word-splitting accept non-git ref text; C reported PASS with the caveat that a literal reading would make it FAIL) | `REPORT_S4.md` | keep PASS with caveat; or owner reads it as FAIL | open; do not change the stage's status silently | Yes |
| Q5 | **Ambiguous D rows** D15, D17, D30, D37 | `REPORT_S4.md` | owner's reading of "added by the handoff commit" | open | Yes |
| Q6 | **TLS reproductions by an independent stage** (F14 printed PASS; canonical HTTPS username-token 401) | S3 not run | run S3 | open | Required for the assignment's Phase B |
| Q7 | **Item E also needs TLS** (S5 ran non-TLS only) | `REPORT_S5.md` section 2 | S3 | open | |
| Q8 | **S4 package-integrity limitation** (zip not re-verified after the reset) | `REPORT_S4.md` section 1 | accept, or re-run S4's integrity step | open | Yes |
| Q9 | **Owner decisions still open:** one bounded correction of rev3; who performs the review; adopting checker v2; D-1…D-11; next-session entry point and ledger wording; the PR #90 rebase (the PR owner's call) | Addendum 6 section 6 | | owner's | Yes, nothing depends on them yet |
| Q10 | **Credential-like string in the owner's preference settings** | system record | owner revokes or removes it | not used or recorded here | Yes |

## 16. Relevant Information / References

- **Save branch** `wip/g4-work-save-checkpoint-nov2026` (commit `8fd8f4da…`): start with its `README_WIP_CHECKPOINT.md`, then `reports/CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_6_REVIEWER_LAUNCH_5_FINDINGS_ON_REV3_2026-11-08.md`, then Addendum 5, 4. It also holds the review package, the block variants, the checkers (`check_addendum1.py`…`check_addendum6.py`, the v2 status checker) and the recorder `tooling/ev.sh`.
- **Addendum 6 evidence IDs:** I76 (launch-5 limit error), I77 (author reproduction of the reported findings), I78 (partial report as left), I79 (state after launch 5), I80/I81 (mechanical checks of Addendum 6).
- **Review package contents** (8 members: the 7 files below plus the package's own `SHA256SUMS.txt`, sha256 prefix `c25c0424837d`; package and member hashes re-verified by the author on 2026-11-13, and by S1/S2/S5 in their stages): brief `README_FIRST_REVIEW_BRIEF.md` (items A–I), `base/handoff.md` (sha256 `9e33cf1a47e8cc050ce91b4e7a29164dd617363c8e3f6154d3b842795edc6d55`, 547 lines), `rev2/verify_block.sh` (no CANON line, no pipefail), `rev3/verify_block_rev3.sh` (38 lines), `rev3/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch` (3 hunks, no `diff --git` header), `optional_item_I/` (Addendum 4 and `check_addendum4.py`; open only in stage S7).
- **Block facts for later stages:** line 15 is the URL normalization `case "$URL" in git@github.com:*) …;; ssh://git@github.com/*) …;; https://*) rest=${URL#https://}; auth=${rest%%/*}; URL=https://${auth##*@}${rest#"$auth"};; esac`; line 16 compares `${URL%.git}` with `CANON=https://github.com/1h0lde4/ocbrain-v4.1` and never prints the configured URL; `git fetch` and `git ls-remote` stderr is not suppressed (lines 10, 17, 18, 35). The patch prose at patch line 30 says "credentials in the URL are ignored and never printed" and "a fork, mirror or proxy URL fails the identity check by design"; the block comment on line 15 says credentials "are neither compared nor printed". Addendum 6 section 4 already corrects my earlier "never printed" statements.
- **Method for F14 on libcurl:** libcurl ends the authority at `/`, `?` or `#`; git appends `/info/refs?service=…` to the URL string, so for `?@` the request target is `/?@github.com/…/info/refs&service=…` and for `#@` it is `/`. The `\@` form contacted github.com in S2's environment.
- **Brief items** (package brief): A six REV2 cases; B canonical identity and look-alikes; C `git ls-remote` handling; D `handoff.md` integrity; E credential protection (no remote URL, credential or token in any output, including git's own messages); F the unavoidable race between the final observation and reading PASS, and whether the patch prose states the guarantee accurately; G patch integrity (the embedded block is byte-identical; the patch applies cleanly; no unrelated changes; prose claims checked); H shell and git pitfalls (word splitting, globbing, `set --`, `pipefail`, command substitution, `rev-list` ordering, `diff-tree` options); I lower priority, how `check_addendum4.py` handles the governing status line.
- **Project memory** (Moncif's project "ocbrain") holds the audit history up to 2026-10-24; this file adds the November state.

## 17. Next Steps

0. **Owner decision first (one question):** may the new bundle be pushed (non-force) to the existing save branch so that the stage reports survive another reset? The reset showed the risk. Until the owner says yes, do not push. Alternative: the owner keeps the bundle.
1. **Verify before anything else** (section 18).
2. **Rebuild the working directory:** unzip the review package from the owner's file (verify its sha256 `391eb0a0…ce2286`), read the brief, copy `recovered/harness/COMMON_PREAMBLE.md`, create stage directories `stage_S6`, `stage_S7`, `stage_S3`, `stage_S8`. Do **not** put author results (Addendum 6, these stage reports) where a Phase A reviewer can read them: Phase A prompts must say "read nothing outside the package and your own directory".
3. **Stage S6 (Phase A): criterion F, G(4) prose claims, criterion H.** Use `prompts_used/` as the template. Scope text: F "Evaluate criterion F exactly as specified in the original package" (the race and the accuracy of the prose guarantee); G(4) "Check every relevant claim against the actual implementation and observed execution… URL credential handling, output sanitization, false-PASS prevention, canonical repository identity, what has and has not been tested… distinguish claims supported by execution evidence from claims supported only by reasoning"; H "Evaluate criterion H exactly as specified in the original package". Expected verification: one status for F, one for G(4), one for H; ten-field findings register.
4. **Stage S7 (Phase A): criterion I** (the only stage allowed to open `optional_item_I/`).
5. **Stage S3 (Phase B): independent TLS reproduction of F14 and the HTTPS username-token F15 case.** Design from the planning notes: one self-signed certificate with SAN DNS:github.com and IP:127.0.0.1; `git http-backend` behind a loopback TLS server (S2's server mapped `/?@github.com/<repo>/…` and `/` back to the repository); `GIT_CONFIG_COUNT/KEY/VALUE` with `http.curloptResolve=github.com:443:127.0.0.1`; `GIT_SSL_CAINFO` to the certificate; a net namespace (`unshare -rn`); the block copy has only its `T=` and `H=` lines substituted, as S2 did (`CANON` stays the real canonical value, which is why `github.com` has to be mapped to loopback by `curloptResolve`). Also answer the open case `https://TOKEN@github.com/…` against a 401. Phase B reviewers may read Addendum 6 and `REPORT_S2.md`/`REPORT_S5.md`.
6. **Stage S8 (Phase B):** compare the Phase A results with Addendum 6 and the F14/F15 evidence, investigate discrepancies independently (do not adopt the author's conclusions).
7. **Run each stage as a sub-agent** (Agent tool, `general-purpose`). Expect the usage limit to cut it off. Then wait for the reset and use `SendMessage` to the agent id with "resume, write the early report, then return the complete report as text". Save the returned text with `tools/extract_handback.py` as `stage_<id>/REPORT_<id>.md` and hash it. Spot-check a few raw rows yourself and record them.
8. **Compile** one A–I matrix by merging the stage reports unchanged. Apply the verdict rule mechanically. Keep the reports' wording where they disagree; list disagreements (Q3, Q4, Q5) as discrepancies for the owner.
9. **Write Addendum 7** (new file; do not edit Addenda 1–6), with a mechanical checker (reuse `check_addendum6.py` and the v2 status checker from the save branch), an evidence bundle, SHA-256 sums and a delivery zip. Assign F-numbers to the new findings. End with the required status line.
10. **Return to the owner** with the decisions in Q9. Do not start a correction of rev3, and do not push, unless the owner says so.

## 18. Resume Instructions

First actions of the next session:

1. Read `PROJECT_INSTRUCTIONS.md` (the project's own), then this file completely, then `recovered/harness/COMMON_PREAMBLE.md`.
2. Verify the refs: `git ls-remote origin refs/heads/main refs/heads/docs/g4-fts-errata-handoff-oct2026 refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026 refs/heads/wip/g4-work-save-checkpoint-nov2026`. Expected: `2491ae469edd6ef1267a14604c4f8f40d698f7ea`, `d963daa502de4220411d0d0c2f19f67b3ec2682b`, `9407db5a01acea9684f158caa8107fb71611a102`, `8fd8f4da1caf966e550774e8e06bfe13822d55ea`. (`main` may have advanced; that alone is not a contradiction: record the new tip.) PR #90 should be open and draft with head `9407db5a…`.
3. Verify the bundle: `sha256sum -c SHA256SUMS.txt`. Verify the review package hash. Verify the recovered report hashes against section 8.
4. Resolve any mismatch before doing anything else, and record the deviation.
5. Ask the owner the single question in section 17, step 0, then continue from step 2.

Do not repeat completed work: S1, S2, S4 and S5 are done. Do not re-run them unless the owner asks for regenerated evidence (Q1b). Do not edit the stage reports. Do not change any status.

## 19. Transfer Status

**TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED**

Reasons, so that nothing is misread:
- This handoff and the companion bundle are not committed or pushed. They exist as files the owner downloads. By the owner's choice (U10) no push was made.
- The four stage reports and the S4 evidence exist only in the bundle (and in the conversation record). They are not in Git.
- Raw evidence for stages S1, S2 and S5 is lost (section 15, Q1).
- The staged review is incomplete (S6, S7, S3, S8 not run); this is a work-in-progress handoff, not a completed review.
- Repository state is verified and unchanged; no repository work is uncommitted.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.

## Appendix A. The current assignment, verbatim (`ab8e1439-attachment.txt`, sha256 `0eaef46eec601ab754b40b4156b8949a0f048b6b559ab0d2c61e2b2024e2ded5`)

~~~~~text
Independent Review Assignment — G4 REV3 Complete A–I Assessment

1. Assignment

Perform a complete, independent technical review of the unchanged REV3 verification package.

The objective is to determine whether REV3 satisfies its stated contract and whether its verification block can reliably establish the canonical repository identity without producing false PASS results or exposing credentials.

This is a review-only assignment.

Do not implement corrections, edit the repository, alter the package, create commits, push branches, or modify pull requests.

2. Source material

Obtain the following from the immutable temporary branch and the Addendum 5 delivery:

- The complete original review package under "review_package/".
- The exact REV3 patch and verification block.
- The package manifest and integrity information.
- Addendum 5 and its referenced evidence.

Verify the package's full SHA-256 against its authoritative recorded value. Do not rely on a matching filename or truncated hash.

Use a scratch directory or isolated clone for testing. Preserve the original files byte-for-byte.

3. Independence and review protocol

Declare your reviewer identity, model family or human-review status, tools, and execution environment.

Perform the review in two phases.

Phase A — blinded independent assessment

Use the original REV3 package without consulting Addendum 6's conclusions.

Evaluate every criterion A–I using the definitions and acceptance conditions in the original package.

Do not assume that previous findings are correct or that an earlier reviewer completed the work correctly.

Phase B — adversarial comparison

After recording Phase A, inspect Addendum 6 and its F14/F15 evidence.

Compare your independent findings with the reported findings.

Independently investigate discrepancies. Do not automatically adopt the author's conclusions.

4. Mandatory technical requirements

A. REV2 and REV3 regression assessment

Reproduce the relevant cases specified in the original review package.

Determine whether the REV3 modification actually resolves the reported REV2 defects.

Record exact commands, inputs, outputs, exit codes, and environment details.

B. Repository identity and URL parsing

Examine how the verification block extracts and validates the Git remote identity.

Test URL parsing boundaries, including:

- Canonical GitHub HTTPS URL.
- User information before the host.
- "?@" and "#@" forms.
- "/@" and path/query boundary variants.
- Backslash and percent-encoded authority variants.
- Other relevant URL normalization and parsing ambiguities.

Where safe, use loopback-only servers to establish the difference between the host accepted by the identity check and the host contacted by Git.

Critical acceptance condition: A verification block must never report PASS when the actual Git destination is not the intended canonical repository.

C. Remaining original criterion

Evaluate criterion C exactly as specified in the original package. Do not substitute a narrower interpretation.

D. Remaining original criterion

Evaluate criterion D exactly as specified in the original package. Preserve all required evidence and provenance.

E. Credential confidentiality

Examine the complete execution path, including:

- Verification-block output.
- Git stdout and stderr.
- Shell error handling.
- Failed authentication.
- Dead or unreachable endpoints.
- URL user-information credentials.
- Query-string credentials.
- Error propagation and logging.

Use dummy credentials exclusively.

Test locally. Never submit credentials to a public GitHub endpoint.

Critical acceptance condition: No dummy credential embedded in a remote URL may appear in captured output or generated evidence artifacts.

F. Remaining original criterion

Evaluate criterion F exactly as specified in the original package.

G. Prose and technical-claim consistency

Check every relevant claim against the actual implementation and observed execution.

Pay particular attention to claims involving:

- URL credential handling.
- Output sanitization.
- False-PASS prevention.
- Canonical repository identity.
- What has and has not been tested.

Distinguish claims supported by execution evidence from claims supported only by reasoning.

H. Remaining original criterion

Evaluate criterion H exactly as specified in the original package.

I. Remaining original criterion

Evaluate criterion I exactly as specified in the original package.

5. F14 and F15 adversarial verification

Independently investigate both findings.

F14 — false PASS

Establish whether a crafted remote URL can cause the verification block to accept GitHub identity while Git connects to another host.

Where feasible, reproduce the complete false-PASS execution using a loopback TLS server with controlled repository history.

Record:

- The exact remote URL.
- The identity check's parsed result.
- The actual network destination.
- The server's request log.
- The block's printed result and exit code.

If the complete reproduction is not feasible, clearly identify what was established and what remains unverified.

F15 — secret output

Establish whether Git's own error messages expose credentials embedded in a remote URL.

Test username and query-string credential forms with dummy tokens and loopback servers.

Capture stdout and stderr separately, then examine all combined output.

Record whether the credential appears and identify the exact output path.

Do not claim that credential output is universally prevented merely because selected test cases show no leaks.

6. Evidence requirements

Every substantive finding must include:

1. Finding identifier.
2. Exact source location.
3. Reproduction conditions.
4. Commands and inputs.
5. Raw or minimally transformed output.
6. Expected versus actual behavior.
7. Severity and impact.
8. Evidence classification: OBSERVED, REPORTED, or DERIVED.
9. Reproduction limitations.
10. Whether the finding is substantive under the package's acceptance contract.

Do not present self-reported conclusions as independent proof.

Do not silently omit failed, incomplete, or inconclusive tests.

7. Required final deliverable

Produce one completed A–I review matrix.

Each criterion must have exactly one status:

- PASS
- FAIL
- BLOCKED
- NOT RUN

For every status, provide the associated evidence references and reasoning.

Also provide:

- Package integrity verification.
- Reviewer independence declaration.
- Environment and tool versions.
- Complete F14/F15 assessment.
- Findings register, including any newly discovered findings.
- Explicit list of unreviewed or unverified matters.
- Overall verdict.
- Reproducibility instructions.

The overall verdict must not be PASS if any substantive finding remains unresolved or any mandatory criterion is BLOCKED or NOT RUN.

A report marked IN PROGRESS is not a completed review.

8. Stopping and governance rules

This assignment grants no implementation authority.

If a substantive finding is discovered:

- Record it.
- Preserve the relevant evidence.
- Stop any proposed correction work.
- Do not prepare or apply another rewrite.
- Return the findings for owner disposition.

Do not modify REV2, REV3, main, PR #90, or any remote branch.

Do not reinterpret DECIDED as ACCEPTED or PROPOSED as ACCEPTED.

Do not declare G4 resolved.

9. Final reporting statement

Conclude with:

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.

The deliverable is a completed independent assessment, not an implementation proposal or an authorization request.
~~~~~

## Appendix B. Attachments the owner re-attached on 2026-11-12 (from the owner's upload index; the full hashes are in `recovered/prompts_and_index/attachments_index_saved-uploads.jsonl`)

| Attachment | Role as far as I can tell (from its first line) | sha256 prefix |
|---|---|---|
| `76f58f1e` | **governing task prompt** (artifact authentication, documentation authority, handoff reconciliation) | `5198c7e4c1ee` |
| `ab8e1439` | **the Independent Review Assignment** | `0eaef46eec60` |
| `673adc69` | Phase G final-state verification and reconciliation study prompt (read-only; baseline `main` = `8b0fee26…`) | `ebef348ab63a` |
| `c017d8ee` | G4/FTS correctness evidence audit and decision-packet errata prompt (baseline `1d813bda…`) | `f7949f94cddf` |
| `7321dea4` | an assistant's Batch 1 independent evidence review (input) | `f0684a93f142` |
| `0c5de411` | independent review of the Batch 1 response bundle | `9cae6a763bf6` |
| `d156fbec`, `5352cdbf`, `d0bde757`, `72baa259`, `865e7d97`, `b2f6a6c5`, `38637bd8`, `4faa6fa1`, `96759cb3`, `7af26dc9`, `fba8a2e6`, `7e35531d` | other assistants' replies about the G4 work: G4 scope and authorization findings, remediation decisions, a static review of the proposal, a retraction about duplicated archive entries (`96759cb3`), a checkpoint verification of the REV2 branch (`7af26dc9`), the ZIP-hash discrepancy (`fba8a2e6`), and a drafting recommendation (`7e35531d`). Input only; no authority | see index |
| `af046c14`, `3bce0bf2`, `7705231e`, `cc2745a2` | other assistants' reviews: of Addendum 3 (`af046c14`), of the P1d block (`3bce0bf2`: false-PASS weaknesses), of the REV2 history and P1b (`7705231e`), and a revised provenance recommendation (`cc2745a2`). Input only | `42396b9f8ddc`, `9c5753c49127`, `809667f2dcef`, `d33f34430bed` |
| `6f5b2de4`, `fb75ee02` | assessment of Addendum 6 (identical files; recommends leaving rev3 unchanged and finishing the review with a human or a different model family) | `42e439322322` |
| `6fc67af1` | reconciliation outcome (keep the REV2 handoff branch as the canonical checkpoint for now) | `46e0f92566aed` |
| `b5f4720b…REV3.zip` | the original REV3 ZIP (Value B) | `f9ee626551e5` |
| `bd0bce1a…review_package.zip` | the independent review package | `391eb0a06784` |
| `236f482a…verify_block_rev3.sh`, `459a1648…PROPOSED.patch` | rev3 block, P1d rev3 patch | `e1ccd6a7e5b1`, `98468b11c2f8` |
| Addendum 4, 5, 6 reports, evidence and delivery zips, checker scripts, I65–I67 | earlier deliverables, as downloaded by the owner | see index |

The assessments of other assistants are input to verification, never evidence of a finding and never an owner decision.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
