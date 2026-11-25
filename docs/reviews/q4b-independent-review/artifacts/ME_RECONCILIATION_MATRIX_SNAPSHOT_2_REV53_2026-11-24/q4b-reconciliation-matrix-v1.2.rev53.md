# Q4B Independent Review: Decision & Evidence Reconciliation Matrix

**Version 1.2, working draft** (revises v1.1; adopts the findings of an external review of v1.1, each verified against the repository first). Update 2026-11-23: the owner identified the governing D1 and D2 records and the decision ledger, and designated the custody location (RD1 to RD4), and authorized AZ1 and received its result (RD5); nothing else changed since the repository snapshot at revision 21. Date: 2026-11-21.

**Disposition: OPEN / NO PASS.**

## Reference state

- Evidence branch: `docs/q4b-independent-review-evidence-nov2026`, tip `ecdc416` (handoff version 1.2). Not merged into `main`; no PR.
- Snapshots branch holding the Doc exports: `docs/verification-3cb-evidence-snapshots-nov2026`, tip `3146c64`. Not merged; no PR seen.
- `main` as last checked (2026-11-21, 11:40 UTC; re-confirmed during the v1.2 revision): `ef1351f`. Earlier references: `2491ae4` (branch base), `6f93444` (handoff v1.1), `2ebf76a` (v1.0 reference), `f9e49dd` (PR #83 merge).
- Every repository-state statement below is point-in-time. `main` moved several times during this review. Re-check before relying on it.

## What changed from v1.1

| # | Change | Verification |
| --- | --- | --- |
| 1 | RD5, MI-08 and AC05 corrected. The six-file selection (brief section 18) and a derived count of 170 collected tests on `16d663a` are now recorded. The v1.1 statement that nothing shows whether 170 is a file subset was too strong and is withdrawn. Passing on both commits stays unverified. | Inventory ME-07 row and brief rev 19 section 18. Both checked in this revision. |
| 2 | E15 and section 5: PR #103 added (documentation-only architecture roadmap; no change to the HTTP path). | Merge `1753b10`, 2026-11-20 00:55Z; the roadmap file is on `main`. |
| 3 | E22 and section 5: PR #112 added (draft authentication-audit work on the same boundary as R04). v1.1 omitted it although it was created 2026-11-20 18:43Z. Raw PR #81 state recorded. | GitHub API read during this revision. |
| 4 | Section 8 carries every open item MI-01 to MI-12. MI-10 to MI-12 had been dropped. | Cross-checked against the missing-evidence register. |
| 5 | E19 and section 8 say "files presented as Doc exports". | Their production method is asserted, not verified. |
| 6 | AZ4 split into AZ4 (PR creation), AZ5 (merge) and AZ6 (further pushes). | Adopted from the external review. |
| 7 | E23 and Appendix B added: the external review recorded as asserted, and repository paths, immutable commit references and SHA-256 values. | Appendix B. |
| 8 | RD1 notes the G4 D1 to D11 series as another D1 label. | `KNOWN_ISSUES.md` on `main`. |

## Earlier change log (v1.0 to v1.1)

| # | Change | Reason |
| --- | --- | --- |
| 1 | Decision IDs renamed D to RD and missing-item IDs M to MI (Appendix A). | v1.0 IDs collide with the Verification rulings D1 to D10, the 3C-A review findings M1 to M9 and the handoff decision ledger D-01 to D-16. |
| 2 | `main` reference updated; PR #83 is now merged, so the FZ-D1/FZ-D2 record is on `main`. RD1 and RD2 now name their candidate records. | The v1.0 text said only that multiple records were unreconciled. |
| 3 | Evidence E17 to E22 added; E07, E13, E15, E16 made precise. | Missing established evidence and overstated precision. |
| 4 | Missing items MI-03 and MI-09 to MI-12 added. | ME-05 captures, provenance corroboration, original `files.zip` and execution-dependent items were not listed. |
| 5 | Reassessment names its baselines and separates the API-auth, privacy, CI-pin and documentation changes; PR #81 closure recorded. | The API-auth merge is the change most relevant to the HTTP layer. |
| 6 | Authorization requests AZ1 to AZ4 separated from decisions. | They need a grant, not a ruling. |
| 7 | Gate status and an "evidence so far" column added. | Shows where each gate stands. |

## 1. Purpose and governing rules

This document reconciles the Q4B review into four categories: established evidence; missing or insufficient evidence; decisions requiring an authorized decision-maker; acceptance criteria required before the disposition can change.

Rules:

- A successful integrity check does not establish substantive correctness.
- A successful test run does not establish that a separately claimed test scope was covered.
- A damaged original artifact remains damaged even when its contents can be partly reconstructed from another export.
- A missing artifact cannot be treated as a passing result.
- A decision marked DECIDED or PROPOSED must not be represented as ACCEPTED without the required acceptance evidence.
- **Asserted is not verified.** A statement by a sender, a committing session or a document about how a file was produced is recorded as ASSERTED until independently checked.
- **Repository text is not owner confirmation.** A decision recorded in a repository file shows what the repository says. Whether it is the decision the mission refers to is for the authorized decision-maker.
- **Point-in-time.** Every repository-state claim carries its check time.
- The review remains OPEN / NO PASS until all applicable closure criteria are met.

Status vocabulary for evidence: VERIFIED (recomputed or re-read in this review), ASSERTED, NOT VERIFIED, NOT FOUND, UNRECOVERABLE.

## 2. Decision reconciliation matrix

Decision authority: RD1 to RD3 require an explicit governance decision. RD4 requires custody and provenance confirmation. RD5 requires source attribution and technical verification. No decision-maker is assigned by this document where the handoff does not establish one. Candidates below are listed to make the question answerable. None is chosen here.

### RD1. Which D1 record governs?

Current state: identified by the owner on 2026-11-23 (see the owner statement below). Candidate records considered:

| Candidate | What it says | Where |
| --- | --- | --- |
| (a) FZ-D1, accepted, option (a), dated Oct 16, 2026 | Preserve the public `handle() -> str` contract and provide a structured internal result consumed by the API. Stated as a decision, not as an implementation claim. FZ-01 stays OPEN. | `KNOWN_ISSUES.md` on `main` since PR #83 merged (`f9e49dd`, 2026-11-20); earlier only on the PR #83 branch. |
| (b) Q4-b brief, platform rev 19 | Treats the D1 public-result contract choice as not yet made, reading `KNOWN_ISSUES.md` on `main` before the PR #83 merge. | Export on the snapshots branch. |
| (c) Owner statement of 2026-10-29 | The choice of the public-result contract was still to be decided explicitly. | Project working notes; not located in the repository. |
| (d) Verification D1 (3C-B tracker rulings D1 to D10) | v1 section 20 stays the authoritative semantic source. | A different D1 under the same label. The G4 documentation handoff also has its own D1 to D11 series (all OPEN per KNOWN\_ISSUES.md). |

Tension to settle: (a) is dated Oct 16, while (b) and (c) date from Oct 29 or later. Possible readings, none chosen: (b) and (c) predate awareness of the record in (a); they concern a different question; (a) was recorded but is to be re-decided.

Required resolution: identify the exact governing record (path, section, date, revision) and whether it supersedes others. Closure evidence: explicit identification by the authorized decision-maker with a traceable source reference. Owner statement, 2026-11-23 (answer to a single-choice question in the review chat): the governing D1 record is FZ-D1 option (a), accepted Oct 16, 2026 and now on main. The question offered three choices: FZ-D1 option (a); the Q4-b brief treating D1 as undecided; the Verification D1. This identifies the governing record. It does not decide RD2 to RD5, does not implement FZ-01 (still OPEN) and does not change the disposition. The source is a chat answer and is not yet recorded in the repository, because the push token has expired. The Q4-b brief rev 19 treatment of D1 as undecided now conflicts with this statement and needs revising under the owner's direction; that has not been done.

### RD2. Which D2 is intended?

Current state: identified by the owner on 2026-11-23 (see the owner statement below). Candidate records considered:

| Candidate | What it says | Where |
| --- | --- | --- |
| (a) FZ-D2, accepted, option (i) | Stalled and hard-deadline generations are failures (`success=False`); partial text is kept in `metadata["partial_output"]`, not as successful `output`. Covers those outcome classes only. `EMPTY_RESPONSE` and `COMPLETED_WITH_PARTIAL_OUTPUT` remain unaccepted. | `KNOWN_ISSUES.md` on `main` since `f9e49dd`. |
| (b) Verification D2 | FAILED is a process/outcome result status, never a VerificationVerdict. The Q4-b brief cites "FAILED under D2". | 3C-B tracker. |
| (c) K4.2 D2 | The general-purpose fallback decision. Not traced in this review. | K4.2 decision records. |

Required resolution: identify the precise D2 artifact and its intended scope, distinct from similarly named material. Closure evidence: exact artifact reference and confirmation of intended applicability. Owner statement, 2026-11-23 (answer to a single-choice question in the review chat): the D2 the mission means is FZ-D2 option (i), accepted Oct 16, 2026 and now on main: stalled and hard-deadline generations are failures. The question offered three choices: FZ-D2 option (i); the Verification D2; the K4.2 D2. This identifies the intended D2. It covers the stalled and hard-deadline outcome classes only; EMPTY\_RESPONSE and COMPLETED\_WITH\_PARTIAL\_OUTPUT remain unaccepted. It does not decide RD3 to RD5, does not implement FZ-01 (OPEN) or complete FZ-02 (partially implemented), and does not change the disposition. The source is a chat answer and is not yet recorded in the repository, because the push token has expired. The Q4-b brief cites FAILED under D2, which reads as the Verification D2; that is a different D2 from the one the owner named, so the brief's D2 references need review under the owner's direction. That has not been done.

### RD3. Is Q4 brief section 10.3 the authoritative ledger?

Current state: identified by the owner on 2026-11-23 (see the owner statement below). Facts that framed the question:

- Section 10.3 of the Q4 brief (platform rev 13) is headed "Candidate decision ledger (all candidates; none accepted)". By its own heading it lists candidates, not accepted decisions.
- The snapshot README labels that brief "Q4 candidates and the decision ledger (section 10.3)". That label comes from the committing session.
- The same brief also cites a different "tracker section 10.3" (the Phase C tracker, item "Unresolved"). Two different sections carry the same number.
- The review handoff keeps its own decision ledger (section 10, D-01 to D-16). It records this review's decisions, not the Verification ones.

Required resolution: determine whether Q4 brief section 10.3 is the governing ledger, a summary of another ledger, or a historical reference, and name the controlling source if it is not authoritative. Closure evidence: explicit authority decision with a reference to the controlling ledger and version. Owner statement, 2026-11-23 (answer to a single-choice question in the review chat): the authoritative decision ledger is Q4 brief section 10.3. The question offered three choices: that section; the Phase C tracker decision record; the review handoff's own decision ledger. By its own heading the section is a candidate ledger in which none is accepted. The statement therefore makes it the authoritative record of the candidates; it does not accept any candidate. The owner's identifications of the D1 and D2 records (RD1, RD2) are not entered in that ledger. Whether the ledger is to be updated to record them is for the owner; that has not been done. The source is a chat answer and is not yet recorded in the repository, because the push token has expired.

### RD4. Who holds custody of the exports?

Current state: the owner designated the custody location on 2026-11-23 (see the owner statement below). No custodian is named, and the chain of custody and the production method are not established. Facts:

- Exports of the three Docs exist on the snapshots branch (commit `3146c64`, 2026-11-09). The bytes are verified against that branch's manifest (E19). That the files were made by the Docs service and not retyped is ASSERTED by the committing session.
- The source Docs live in the Docs service. The owner holds the original `files.zip`. This review keeps received files unmodified in its Batch 1 to 3 packages.
- The owner's 2026-10-29 direction asked for exported snapshots on a reviewed, documentation-only branch with a SHA-256 per file. Whether the snapshots branch meets it, and whether it was reviewed, is not established.

Required resolution: name the custodian, the transfer history and the preservation location of the originals. Closure evidence: named custodian, provenance record, transfer evidence and preserved originals with verified hashes. Owner statement, 2026-11-23 (answer to a single-choice question in the review chat): the custodian of the Doc exports is the snapshots branch (docs/verification-3cb-evidence-snapshots-nov2026), with no named person. The question offered three choices: the owner; the snapshots branch with no named person; someone else. This designates the custody location. It does not name a responsible person, show a transfer history, or establish how the exports were produced. A branch can be rewritten or deleted, so the immutable reference that matters is commit 3146c647a4ba6af186f6c3931fe2cdb840054865, which this matrix cites. The branch is unmerged and has no pull request, whether it was reviewed is not established, and the Docs may have advanced past the exported revisions. RD4 therefore stays open for a named custodian or an explicit acceptance that none is named. The source is a chat answer and is not yet recorded in the repository, because the push token has expired.

### RD5. Where did the 170-test figure originate?

Current state: the source, the selection and the count are identified, and the claim was reproduced on 2026-11-24 in an owner-authorized verbose run (AZ1; see E24). The original execution logs are still not located. Three separate things:

- **Selection (VERIFIED as stated in the source).** Brief section 18 ("Revalidation against `main` `4a4783c`", Tests) names six targeted files: `test_execution_runtime`, `test_supervisor_worker`, `test_evaluator_worker`, `test_workflow_runtime`, `test_workflow_failure_disclosure`, `test_scheduler_failure_containment`. It states 170 passed on `4a4783c`, the same count as on `f13bfde`. Its runtime-audit baseline row says the same for `f13bfde` and labels it OBSERVED by the brief's author.
- **Count (DERIVED on another baseline).** Per-file counts recorded from this review's own runs on `16d663a` (37, 29, 26, 35, 8, 35) total 170 collected tests. One of them, `test_workflow_failure_disclosure::test_a_successful_workflow_run_is_unchanged`, needs the real embedding model and failed in that environment, so "170 passed" was not reproduced as a pass count (inventory, ME-07).
- **Claim on the two commits (NOT VERIFIED against original logs; REPRODUCED on 2026-11-24, see E24).** No original log shows 170 passed on `4a4783c` or on `f13bfde`. Both CI runs ran the whole `tests/` directory in quiet mode with zero failures, which is consistent with the six files passing. But 14 skipped and 1 xfailed are not attributed to files, so 170 passes cannot be derived from them.

Required resolution: locate the original command, versions, environment (including whether the embedding model was available), per-file pass and fail counts and logs for the six-file selection on `4a4783c` and `f13bfde`, or correct or withdraw the claim. Closure evidence: those logs with their SHA-256, or an explicit correction or withdrawal. Owner statement, 2026-11-24 (answer to a single-choice question in the review chat): a verbose run of the six identified files (AZ1) is authorized, on 4a4783c and f13bfde. The question offered three choices: withdraw the claim; keep it open while the owner supplies the original logs; authorize the run. Result (E24): 170 passed on each commit with the same per-file counts, in a non-CI environment. This reproduces the claim; it does not recover the original logs. The run is not yet recorded in the repository, because the push token has expired.

### Authorization requests (not decisions)

| ID | Request | Status |
| --- | --- | --- |
| AZ1 | A verbose run of the six identified files (per-file results) on each of `4a4783c` and `f13bfde`, with the environment recorded, to test the 170 claim. | Authorized 2026-11-24 (owner, chat); executed, see E24 |
| AZ2 | Finding-specific verification on current `main` (R07). | Not authorized. |
| AZ3 | A content-level repository search for the probe outputs and diff output (beyond the file-name scan already done). | Not authorized. |
| AZ4 | Creating a PR for the evidence branch or the snapshots branch. | Not authorized. |
| AZ5 | Merging either branch. | Not authorized. |
| AZ6 | Any further push to either branch. The owner's token expired on 2026-11-23 (checked at 10:18 UTC: HTTP 401); a new token and fresh authorization are needed. | Not authorized. |

## 3. Evidence reconciliation matrix

| ID | Evidence or claim | Result | Status | Limitation |
| --- | --- | --- | --- | --- |
| E01 | Batch 3 package integrity | `SHA256SUMS.txt`: 12 of 12 entries verify. | VERIFIED | Integrity only. |
| E02 | Batch 3 package identity | A fresh clone is identical to the source; received ZIPs are byte-identical to the uploads. | VERIFIED | Does not establish original-export correctness. |
| E03 | I005 | First log export, damaged by a text re-encoding (UTF-16, OEM code page, CRLF); kept as received. | VERIFIED | Not a clean archive. Never to be presented as one. |
| E04 | I006 and I007 | Clean ZIPs: integrity test passes, every member matches its CRC32; full head SHAs, runner ids and time windows match the run and job records. | VERIFIED | Cleanliness is not substantive acceptance. Equality with the platform's original log bytes is not verifiable (no digest published; download hosts unreachable from the sandbox). Sender's export route not stated. |
| E05 | I005 against I006 | Central-directory values (names, CRC32, sizes) identical; the 2 small members derived from I005 are byte-identical to I006's. | VERIFIED | The 2 large members were not recovered. Derived output is not original. |
| E06 | Batch 3 verification script | 33 of 33 checks pass, exit 0 (recorded). | VERIFIED | Limited to its asserted checks. |
| E07 | Corruption test | One flipped bit in a copy of I006 makes the script exit 1. | VERIFIED (run once) | Not recorded in the repository; one scenario only. |
| E08 | Batch 1 | 51 of 51 manifest entries verify. | VERIFIED | Package integrity only. |
| E09 | Batch 2 | 13 of 13 checksum entries verify; its verification script was re-run in a fresh clone on 2026-11-18 (exit 0). | VERIFIED | Package integrity only. |
| E10 | Run 40781867485 (`4a4783c`) | `2073 passed, 14 skipped, 1 xfailed` in 72.66s; exit 0. | VERIFIED | Quiet mode; no test files named; 14 skipped and 1 xfailed not attributed to files. |
| E11 | Run 39226693573 (`f13bfde`) | `2058 passed, 14 skipped, 1 xfailed` in 104.00s; exit 0. | VERIFIED | Same limitation. |
| E12 | Test gate | "Test gate passed" with an empty known-failure list in both runs. The allowlist concealed nothing because nothing failed. | VERIFIED (log text) | Not independent proof of correctness or scope. |
| E13 | Fresh-clone verification | The batch 3 script (which runs the recovery script in fast mode) was re-run in a fresh clone: 33 of 33, exit 0. | VERIFIED at the time | Committed output files come from the working tree before the commit. The clone re-run output was reported in the session, not saved. |
| E14 | Git scope | Commit `7ccb028` adds 13 files, all inside the batch 3 directory; `ecdc416` modifies only `handoff.md`. | VERIFIED (`git diff --name-status`) | Re-check against the actual diff if reassessed. |
| E15 | Repository state | `main` at `ef1351f` as last checked. Since `2ebf76a` only PR #83 and PR #88 merged (documentation; no non-doc file; review directory untouched). Since the base `2491ae4`: DEBT-025 API-auth (PR #94, Nov 17; 20 non-doc files), CI action-pin bumps, privacy containment (PR #79) and documentation-only PRs #87, #103 (architecture roadmap proposal; no change to the HTTP path), #108 to #111, #83 and #88. | VERIFIED (point-in-time) | HTTP-layer findings were not re-checked on any of these revisions. |
| E16 | Credential scan | Patterns for GitHub token prefixes, bearer-style headers, `x-access-token` and private-key headers over package files and decoded members of the received ZIPs: 0 hits. I005 was scanned as raw bytes only (it cannot be opened as a ZIP); the same log content was scanned in full through I006. The handoff was scanned separately. | VERIFIED (point-in-time) | Scan method and output were not committed. That is a gap. |
| E17 | Raw CI artifacts (I001; I003 and I004 are duplicates) | The four raw ZIPs (pytest-output and drift-report, both runs) match the platform digests and sizes captured earlier by authenticated API; inner members match. | VERIFIED | Strongest integrity evidence for CI. Content is progress characters. Sender's route asserted. |
| E18 | Run records | Run 40781867485 is `4a4783c`; run 39226693573 is `f13bfde`; both attempt 1, push to `main`, success. | VERIFIED | Records captured earlier; not re-fetched. |
| E19 | Files presented as Doc exports (ME-01 to ME-03) | Six files on the snapshots branch match that branch's manifest and `SHA256SUMS`; the Doc ids map to the claude.ai links (Q4-b brief rev 19, pack rev 28, Q4 brief rev 13). | Bytes VERIFIED; production method ASSERTED | Branch unmerged, no PR. The Docs read did not show the attached export copies. Platform revisions may have advanced; earlier revisions are not archived. |
| E20 | Probe scripts (I002) | The six original members match this review's Batch 1 record of the original `files.zip`; four also match the full hashes in the Q4-b brief. | VERIFIED | Outputs not delivered. Original outer `files.zip` not recovered. Sender's source archive asserted. |
| E21 | FZ-D1/FZ-D2 record | On `main` since `f9e49dd`: FZ-D1 option (a), FZ-D2 option (i), dated Oct 16; FZ-01 OPEN; FZ-02 partially implemented. | VERIFIED (repository text) | Repository text is not owner confirmation of which D1 or D2 the mission means. |
| E22 | PR and issue states | PR #81 (DEBT-028 concurrency lock, head `647b63e`) CLOSED unmerged on 2026-11-20 22:01Z. PR #83 merged 2026-11-20. Issue #105 open, unassigned, one comment (Nov 2). Raw snapshot: PR #81 state closed, merged false, merged\_by none, closed\_at 2026-11-20T22:01:12Z, head 647b63e734792b8375c0f96593407ee651af5840. PR #112 (draft, open; created 2026-11-20 18:43:52Z; head ed8890c272ff0d70369c5b6d551e7fb857e13bf6; base main 2ebf76a; 4 ahead and 7 behind current main) adds durable authentication audit records in the EventStream (DEBT-025 follow-up). It changes interface/api.py, interface/auth.py, interface/auth\_audit.py and three test files, says verification is incomplete, and is not main-branch evidence. Open PRs at the check: #112, #107, #102, #91, #90, #86, #33, #32; only #112 was examined. | VERIFIED (point-in-time) | v1.1 omitted PR #112 although it existed when v1.1 was checked. The raw API snapshot is not preserved as a file in the repository. The data read does not show who closed #81 or why. Consequences for DEBT-028-related review items not assessed. |
| E23 | External review of v1.1 (supplied by the owner in the chat) | Says it confirmed the branch tips and the main change-set by read-only GitHub access, reported four corrections and recommended v1.2. It says it did not recompute hashes, re-run scripts, run probes or run tests. | ASSERTED (its own statement); its four corrections were each verified here | Not an independent acceptance (AC10). Its repository checks agree with this revision's checks. PR #94 file totals differ by method (22 here, 30 there); the non-doc count is 20 in both. |
| E24 | AZ1 verbose run of the six identified files (owner-authorized 2026-11-24) | 170 passed on 4a4783c (11.57s) and 170 passed on f13bfde (7.49s). Per-file counts 37, 29, 26, 35, 8 and 35 on both commits. test\_a\_successful\_workflow\_run\_is\_unchanged passed on both. Environment: Python 3.12.3; the package versions CI installed for each commit, installed without dependency resolution; torch, transformers and sentence-transformers not installed; no network path to Hugging Face. Each commit extracted with git archive; pytest -v --tb=short. | VERIFIED (executed in this review) | Not the CI environment (CI used Python 3.12.15 and the full CUDA and torch stack). It reproduces the claim; it does not recover the original logs. The inventory's note that this test needed the embedding model and failed on 16d663a is environment-dependent; its cause here is not established. Output and environment records are not yet in the repository. |

### Evidence classification

- Integrity evidence: E01 to E05, E08, E09, E17 to E20.
- Execution and reproducibility evidence: E06, E07, E10 to E13.
- Repository and change-scope evidence: E14, E15, E21, E22. E23 is an external review of v1.1: asserted, no recomputation, not an acceptance.
- Security screening evidence: E16.
- **Substantive review acceptance: not established.**

None of these categories substitutes for another.

## 4. Missing-evidence register

| ID | Missing artifact or evidence | Current state | Required action | Acceptance condition |
| --- | --- | --- | --- | --- |
| MI-01 | Probe outputs (ME-06) | NOT FOUND. Scripts are located (E20). The sender's README says results were produced on `f13bfde` (P1 to P6), re-run on `4a4783c` (P1 to P8), with P9 on `4a4783c` only. | Locate the originals or establish they are irretrievable; record filenames, generating commands and provenance. | Originals verified, or their absence formally documented with its review impact. |
| MI-02 | Diff output for `4a4783c` and `f13bfde` (ME-08) | NOT FOUND. | Recover the original, or decide whether a diff regenerated from git for two immutable commits is acceptable. A regenerated diff is derived, not original. | Reproducible diff tied to immutable revisions, or formally declared unavailable with impact documented. |
| MI-03 | Original captures for revision-1 preservation (ME-05) | NOT FOUND. The snapshot manifest says earlier revisions are not archived. | Locate the captures or document the loss. | Captures verified, or the limitation accepted by the authorized reviewer. |
| MI-04 | D1 authority reference | Resolved by the owner statement of 2026-11-23 (RD1); repository record pending. | Complete RD1. | One governing record identified. |
| MI-05 | D2 identity reference | Resolved by the owner statement of 2026-11-23 (RD2); repository record pending. | Complete RD2. | Intended D2 identified. |
| MI-06 | Ledger authority | Resolved by the owner statement of 2026-11-23 (RD3); repository record pending. | Complete RD3. | Controlling ledger identified. |
| MI-07 | Export custody record | Custody location designated by the owner on 2026-11-23 (RD4): the snapshots branch, no named person; chain of custody not established. | Establish custodian and chain of custody. | Provenance traceable. |
| MI-08 | 170-test source | Selection identified; claim reproduced on 2026-11-24 (AZ1, E24); original execution logs not located (RD5). | Locate the original execution logs and environment record for the six-file selection, or correct or withdraw the claim. | Claim substantiated, corrected or withdrawn. |
| MI-09 | Independent corroboration of the Doc exports' production method | NOT DONE. | Compare service-side hashes of the attached export copies with the committed ones (a session that can see them), or obtain the owner's confirmation of the method. | Corroborated, or accepted as asserted by the decision-maker. |
| MI-10 | Original outer `files.zip` (8,443 bytes) | NOT RECOVERED. The members were re-delivered inside a repack (I002). | Obtain the original from its holder. | Original hashed on receipt, or its absence accepted. |
| MI-11 | Execution-dependent items (ME-14, ME-15) | NOT RUN. | Only in a separately authorized batch. | Executed and recorded, or dispositioned. |
| MI-12 | Platform-level equality for the log archives | NOT VERIFIABLE (no digest is published; hosts unreachable). | Record as a limitation, or retrieve the archives by an allowed route and compare with I006 and I007. | Equality shown, or limitation accepted. |

### Treatment of missing evidence

Outcomes must remain distinct: FOUND AND VERIFIED; FOUND BUT NOT VERIFIED; NOT FOUND; UNRECOVERABLE; NOT APPLICABLE with documented justification. **NOT FOUND must never be converted into PASS.**

## 5. Current-main reassessment

HTTP-layer findings were produced on older baselines. `main` has since advanced, so they need a separate current-state reassessment.

### Baselines

- Review baselines named in the handoff: `16d663a`, `ed3d141`, `2491ae4` (branch base). The per-finding mapping is recovered under R01.
- CI and probe commits: `4a4783c`, `f13bfde`.
- Current `main`: `ef1351f` (as last checked).

### Changes on `main` since the base (`2491ae4`)

| Change group | Evidence | Relevance to assess |
| --- | --- | --- |
| DEBT-025 API-auth boundary | PR #94, merge `ce5c3f8` (2026-11-17): 20 non-doc files including `interface/api.py`, auth and header modules, three new events in `core/event_bus.py`, a token subcommand in `main.py`. | Highest. It changes the request path. |
| CI action-pin bumps | `ci.yml`, `release.yml` (merged 2026-11-17 to 2026-11-19). | Future CI evidence comes from a different workflow than the I006 and I007 logs. |
| Privacy containment | PR #79, merge `2ebf76a` (2026-11-20): `core/privacy.py`, `tests/test_privacy.py`. | Logging, collection and evidence visibility. |
| Documentation reconciliations | PRs #87, #103, #108, #109, #110, #111, #83 and #88. PR #103 adds an architecture roadmap proposal (docs/architecture/OCBRAIN\_V2\_UNIFIED\_COGNITIVE\_RUNTIME\_ROADMAP.md) that does not change the HTTP request path. PR #83 records FZ-D1/FZ-D2. PR #88 records the owner-directed response-path disposition (DEBT-043: K4.2 pairing retained, containment option C-plus). | Stated contracts and assumptions; the response-path disposition may bear on HTTP-layer findings. |
| PR #81 closed unmerged | DEBT-028 concurrency-lock fix, closed 2026-11-20 22:01Z. | The fix is not on `main`; DEBT-028 stays open or deferred per its last comment. |
| Concurrent open work, not on main | PR #112 (draft, open, created 2026-11-20 18:43Z): durable authentication audit records in the EventStream. Changes interface/api.py, interface/auth.py, interface/auth\_audit.py and three test files; 4 commits ahead and 7 behind main. | Same boundary as R04. Unfinished and unmerged: not main-branch evidence. Track it for changes to the findings' preconditions. |

### Reassessment items

| ID | Item | Required verification | Acceptance criterion |
| --- | --- | --- | --- |
| R01 | Historical finding inventory | Recover every HTTP-layer finding from the prior review with its baseline. | Complete inventory with source references. |
| R02 | Source applicability | Compare the relevant implementation at each baseline and at current `main`. | Every finding classified: unchanged, affected, resolved, regressed or no longer applicable. |
| R03 | CI action-pin changes | Determine whether they alter the verification environment or the interpretation of earlier CI evidence. | Impact explicitly assessed. |
| R04 | API-auth boundary (DEBT-025) | Trace how the new authentication boundary changes the HTTP request path, error responses and the findings' preconditions. Keep the draft PR #112 out of main-branch evidence. | Per-finding effect documented. |
| R05 | Privacy change | Check effects on HTTP behavior, evidence visibility, logging or collection. | Relevant effects documented; unrelated ones excluded. |
| R06 | Documentation changes | Check whether changed documents alter the stated contract or review assumptions, including FZ-D1/FZ-D2 and the DEBT-043 disposition. | Document and source discrepancies identified. |
| R07 | Current test evidence | Execute or obtain authorized, finding-specific tests against the current revision (needs AZ2). | Results tied to the exact commit and test selection. |
| R08 | Finding disposition | Review each finding against source and test evidence. | Each finding has an evidence-supported disposition. |

A finding must not be marked resolved merely because its associated test suite passes.

## 6. Proposed closure sequence

| Gate | Scope | Exit condition | Status (2026-11-21) |
| --- | --- | --- | --- |
| 0. Preserve evidence | Keep received archives and damaged originals unchanged; keep manifests and verification output; keep derived artifacts separate. | Inventory and preservation record complete. | Largely met. Gaps: scan record, negative-test record and clone re-run outputs not saved (AC13). |
| 1. Resolve authority | RD1, RD2, RD3, with source references. | One unambiguous governing record set. | Open. |
| 2. Provenance and test claims | RD4, RD5; correlate CI runs with exact revisions. | Every material claim substantiated, corrected or withdrawn. | Open. Run-to-commit correlation done (E18). |
| 3. Recover missing evidence | MI-01 to MI-03, MI-09 to MI-12. | Available, or its absence formally assessed and accepted as a limitation. | Open. |
| 4. Reassess current `main` | R01 to R08. | Every HTTP-layer finding has a defensible current-state disposition. | Not started (needs AZ2). |
| 5. Independent disposition | The independent reviewer evaluates authority, evidence completeness, provenance, test-scope validity, historical-to-current applicability and remaining limitations. | Explicit, evidence-supported disposition recorded. | Not started. |

## 7. Final acceptance criteria

The review may be considered for PASS only when all applicable conditions are satisfied.

| ID | Requirement | Status | Evidence so far |
| --- | --- | --- | --- |
| AC01 | D1 governing record identified and accepted. | PROVISIONALLY MET (owner statement; repository record pending) | Owner statement 2026-11-23, chat answer: FZ-D1 option (a). Not yet recorded in the repository. |
| AC02 | D2 intended record identified and accepted. | PROVISIONALLY MET (owner statement; repository record pending) | Owner statement 2026-11-23, chat answer: FZ-D2 option (i). Not yet recorded in the repository. |
| AC03 | Authoritative ledger established. | PROVISIONALLY MET (owner statement; repository record pending) | Owner statement 2026-11-23, chat answer: Q4 brief section 10.3. It lists candidates only, none accepted. Not yet recorded in the repository. |
| AC04 | Export custody and provenance established. | OPEN (custody location designated; no named custodian; provenance asserted) | Owner statement 2026-11-23, chat answer: the snapshots branch, no named person. Chain of custody and production method not established; branch unmerged, no PR. Not yet recorded in the repository. |
| AC05 | 170-test claim substantiated, corrected or withdrawn. | PROVISIONALLY MET (reproduced in a non-CI environment; repository record pending) | Reproduced 2026-11-24: 170 passed on 4a4783c and on f13bfde (E24). Original execution logs not located. Not yet recorded in the repository. |
| AC06 | Probe outputs recovered or formally dispositioned. | OPEN | Scripts located; outputs NOT FOUND. |
| AC07 | Diff output recovered or formally dispositioned. | OPEN | NOT FOUND. |
| AC08 | Current-main HTTP-layer reassessment completed. | OPEN | Not started. |
| AC09 | All findings have evidence-backed dispositions. | OPEN | None recorded. |
| AC10 | Independent reviewer records explicit acceptance. | OPEN | None. |
| AC11 | Doc-export production method corroborated, or accepted as asserted by the decision-maker. | OPEN | Asserted only (MI-09). |
| AC12 | Authorization requests AZ1 to AZ6 decided and recorded. | OPEN | All not authorized. |
| AC13 | Evidence-record gaps closed: scan method and output, negative-test record and clone re-run outputs saved. | OPEN | See E07, E13, E16. |

An accepted limitation is not automatically a technical PASS. Any limitation that affects the ability to establish correctness or completeness must stay visible in the final disposition.

## 8. Current formal disposition

**OPEN / NO PASS**

### What is established

- Package integrity checks pass for Batches 1 to 3.
- Received archives are preserved; the damaged first log export is kept as received and identified as damaged.
- The recorded verification script passes its assertions, and the corruption negative test behaved as expected.
- Raw CI artifacts match their platform digests. Run-level logs for both runs are clean ZIPs consistent with the run and job records and with the artifacts.
- Both runs passed their full test suite in CI with the gate passing.
- Six files presented as Doc exports exist on the snapshots branch; their bytes match that branch's manifest; their production method is asserted.
- The FZ-D1/FZ-D2 record is on `main`.

### What is not established

- The D1 and D2 records were identified by the owner on 2026-11-23 (RD1, RD2); those statements are not yet in the repository.
- What the ledger records: Q4 brief section 10.3 was named the authoritative ledger on 2026-11-23 (RD3), but it lists candidates only and none is accepted; that statement is not yet in the repository.
- Export custody beyond the owner's designation of the snapshots branch (no named custodian, no review or merge) and independent corroboration of the exports' production method (RD4, MI-09).
- The original execution logs behind the 170 claim (RD5, MI-08). The claim was reproduced on 2026-11-24 in a non-CI environment (AZ1, E24); that reproduction is not yet in the repository.
- The probe outputs, the diff output and the revision-1 captures (MI-01 to MI-03).
- The original outer `files.zip` (MI-10).
- The execution-dependent items ME-14 and ME-15 (MI-11).
- Equality of the received log archives with the platform's original bytes (MI-12).
- Current-main HTTP-layer finding dispositions (R01 to R08).
- Formal independent acceptance.

### Change-control boundary

This document authorizes documentation and evidence reconciliation only. It does not authorize: new implementation work; new branches or pull requests; merges, rebases or closures; additional test execution (AZ1, AZ2); or changes to the existing review disposition. Any such activity requires separate explicit authorization.

**Final rule:** evidence integrity is necessary but not sufficient for review acceptance. The disposition remains OPEN / NO PASS until the acceptance criteria are satisfied and the independent reviewer records the result.

## Appendix A. ID mapping, v1.0 to v1.1

| v1.0 | v1.1 | Note |
| --- | --- | --- |
| D1, D2, D3, D4, D5 | RD1, RD2, RD3, RD4, RD5 | Same questions; candidates and facts added. |
| M01, M02 | MI-01, MI-02 | Unchanged in substance. |
| M03, M04, M05, M06, M07 | MI-04, MI-05, MI-06, MI-07, MI-08 | Cross-references to RD1 to RD5. |
| (new) | MI-03, MI-09, MI-10, MI-11, MI-12 | Added. |
| E01 to E16 | E01 to E16 | E07, E13, E15, E16 made precise. |
| (new) | E17 to E22 | Added. |
| R01, R02, R03 | R01, R02, R03 | Same. |
| R04 (privacy) | R05 | Renumbered. |
| R05 (documentation) | R06 | Renumbered. |
| R06 (current tests) | R07 | Renumbered. |
| R07 (disposition) | R08 | Renumbered. |
| (new) | R04 (API-auth boundary) | Added. |
| AC01 to AC10 | AC01 to AC10 | Evidence-so-far column added. |
| (new) | AC11, AC12, AC13 | Added. |
| v1.1 AZ4 | AZ4, AZ5, AZ6 | Split: PR creation, merge, further pushes. |
| (new in v1.2) | E23, Appendix B | Added. |

## Appendix B. Source references

Paths are relative to `docs/reviews/q4b-independent-review/artifacts/` on the evidence branch unless stated. B1 says where each item lives and which commit holds it; B2 lists SHA-256 values.

### B1. Locations and immutable references

| Evidence | Location | Immutable reference |
| --- | --- | --- |
| E01, E02, E06, E07, E13, E14 | `ME_RECOVERY_BATCH_3_LOGS_INTAKE_2026-11-20/` (`SHA256SUMS.txt`, `verify/VERIFY_OUTPUT.txt`) | Transfer commit `7ccb028c5f320d9ff6182ad6f5f8311afe4c4d00`; handoff v1.2 `ecdc4160da6b42049e0aa4d774062fc00eb56ea8` |
| E03, E05 | Same directory: `received/I005__workflow-logs.zip`, `recover/RECOVERY_OUTPUT.txt` | `7ccb028c5f32` (full ID above) |
| E04, E10, E11, E12 | Same directory: `received/I006__workflow-logs_1.zip`, `received/I007__workflow-logs-39226693573.zip` | `7ccb028c5f32` |
| E08 | `ME_RECOVERY_BATCH_1/manifests/SHA256SUMS.txt` | Transfer commit `8cce19c0a33dcbc67b71c7559e98732fbc9239db`; first files in `9824d0d4dfba52093ecde4a47bac2b5017389304` |
| E09, E17, E20 | `ME_RECOVERY_BATCH_2_INTAKE_2026-11-18/` (`received/I001` to `I004`, `SHA256SUMS.txt`) | `8ff6deceddd438c7b41bc8cfe46bea0c4cf3354d` |
| E15 | Batch 2 `verify/MAIN_DRIFT_SINCE_2491ae4.txt`; Batch 3 `verify/MAIN_DRIFT_SINCE_6f93444.txt`. Later movement (PR #83, PR #88) was read live and not saved. | `main` `ef1351ffbb011cdfe8f10bb03f8454752f5f9250`; base `2491ae469edd6ef1267a14604c4f8f40d698f7ea` |
| E18 | `ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/api/` (`run_*_detail.body`, `run_*_jobs.body`, `run_*_artifacts.body`) | Batch 1 commits `9824d0d4dfba` and `8cce19c0a33d` |
| E19 | Snapshots branch, `docs/architecture/verification-3cb-evidence-snapshots/` | `3146c647a4ba6af186f6c3931fe2cdb840054865` |
| E20 | Batch 1 `acquisition_records/search_logs/S05_archive_verification.txt`; Batch 2 `received/I002` | `9824d0d4dfba`, `8ff6deceddd4` |
| E21 | `KNOWN_ISSUES.md` lines 169 and 170 on `main`; extract in Batch 2 `verify/PR83_D1_D2_EXTRACT.txt` | PR #83 merge `f9e49dd0b71cf223f0775caa8c5e6f79bc918de1` |
| E22 | GitHub API reads, not preserved as a file in the repository (gap) | PR #81 head `647b63e734792b8375c0f96593407ee651af5840`; PR #112 head `ed8890c272ff0d70369c5b6d551e7fb857e13bf6`; PR #103 merge `1753b10721f5af21050c6808338c40e55937eb69`; PR #94 merge `ce5c3f807e7f72d59ff77ad84e92f4bc8ce38c79` |
| RD5, MI-08 | `Q4B_MISSING_EVIDENCE_INVENTORY.md` (ME-07 and ME-14 rows); Q4-b brief rev 19, section 18, on the snapshots branch | Inventory in `9824d0d4dfba`; brief in `3146c647a4ba` |

### B2. Hash register (SHA-256)

| Item | Bytes | SHA-256 |
| --- | --- | --- |
| Batch 1 `manifests/SHA256SUMS.txt` |  | `68933e66075389e7fdf996edaf1847306bd040d06190387186d0ac3630e256dd` |
| Batch 2 `SHA256SUMS.txt` |  | `1cc49d857a35069b33888ed98b07ae0bd48605075a7a46d238da2376177f9ea0` |
| Batch 3 `SHA256SUMS.txt` |  | `b0f5db0e6cfee897620cb0000928045dec85c99d0c865075b173425456892f8d` |
| `Q4B_MISSING_EVIDENCE_INVENTORY.md` | 16,417 | `761ca944d18d5b7c545e5ac5b9d3cd3ad83259a2f9aab28b9f3e0eabd0bb07b7` |
| I001 `ME07_CI_ARTIFACTS_PARTIAL_RECOVERY.zip` | 23,283 | `3519af68f418d46d63ddc0ea77572b3541301cee50cf7ff725077807d19af0ef` |
| I002 `ME06_PROBE_SCRIPTS_MEMBER_VERIFIED.zip` | 9,342 | `0a024a85a2f95df1c4c72cb8869db56521d88e89e15860081438c27ff3b7c4dc` |
| I003 `drift-report.zip` | 2,318 | `6651320038614d52604eabdf505e88b36cb7b5f0a9826acd51cdc168c6cc4301` |
| I004 `pytest-output.zip` | 1,164 | `0a271629118a2b5005756bf81a75f4284cdb126869d694ef99b7b01e23bba52e` |
| I005 `workflow-logs.zip` (damaged) | 60,308 | `d19632ef317a4a0466ea122ca9ee34a718da45475b9982cb13e3b5bd9cc059f8` |
| I006 `workflow-logs_1.zip` | 29,923 | `a0f3f3d5f2e87b7e3c948676befd14f685ad92d297ac06378f0a3b93e03240cb` |
| I007 `workflow-logs-39226693573.zip` | 28,934 | `c1a9ef268ba848d876645030beba01f523df967ff8b336aa44d79186c2668cd0` |
| Probe member `probe_main.py` | 8,419 | `a761827d450591ddf2d0589b0a65428c5c1703a52f1b1ec4b19b66bfdd87e395` |
| Probe member `probe_main2.py` | 3,343 | `dc69e68f7818a77b09611fdf6c5a2cfd3c58805d6836fdd18efa6a016535110e` |
| Probe member `probe_main3.py` | 2,279 | `e1aee93306461167996380d5dd783e525fee780bd6897ee3511d134c6ad1154c` |
| Probe member `probe_main4.py` | 4,668 | `5ef869ee74f6749e0a65b937b799582a2750e01513e116eb9ee7c0e51a9f23ed` |
| Probe member `probe_main5.py` | 1,676 | `403f6c37853fe8db33a128d22a8f56faaf2ce96511c7016f862bb60ebe522a11` |
| Probe member `README.md` | 1,309 | `fc5ba8aeb31db4a4983600a32233a64c3755ec5c7249b4c8c9e536e1916d5681` |
| Snapshots branch `SHA256SUMS` |  | `89ef4f9f8a3abdbb19679be9154ab9d307400cadf6275cae9e8d191f88d79957` |
| Pack rev 28 `.md` | 26,238 | `cff38e1da17d67c0fda0bdcf8c68d2d6a787b31a107b2828991a525aa698f2b2` |
| Pack rev 28 `.docx` | 15,843 | `4ed5c2c6433693fc79f0492a79112ad609d3de5f16099b2343213620c4b721da` |
| Q4 brief rev 13 `.md` | 54,262 | `cb171f72ef0c0df24379de353095235b4314f110b8f787ceda7fa56777c29641` |
| Q4 brief rev 13 `.docx` | 26,408 | `e92ab6f67efcbc9a1920f19bb0c8e495134ca2e55b225e3461a46f37dd5e72b9` |
| Q4-b brief rev 19 `.md` | 71,911 | `886a208246dd3f8319c4cc4fc1d5a46f147eb3e2fd9c8bd76769cabb7445ef4a` |
| Q4-b brief rev 19 `.docx` | 36,774 | `3d849bd8c0e94a885d6179b25fc5f89e6b1f672cb60e3dbc2fe3476175dfaed1` |
