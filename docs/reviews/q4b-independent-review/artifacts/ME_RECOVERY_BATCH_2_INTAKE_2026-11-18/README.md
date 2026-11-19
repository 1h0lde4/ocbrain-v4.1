# ME recovery batch 2: retrieval and intake record (2026-11-18)

**Status: records only.** This package changes no disposition. The Q4-b brief is not validated, the review
disposition stays OPEN, NO PASS, and no mission is closed. It adds new files only; no earlier file in the
review directory is edited. Docs-only; no code, test, probe or Docs-service write was performed.

## 1. Authority and baselines

- Owner instructions in the chat on 2026-11-18, in order: "Use the token to retrieve all you need"; four
  file uploads (intakes I001 to I004); "you can push" (accepted scope: this docs-only addendum plus
  `handoff.md` version 1.1, to this branch only, no PR, nothing to `main`).
- The token is the owner's, supplied in the chat's user preferences. It was used only for read-only GitHub
  API calls, passed per request, and is not stored, logged or written into any file here. Its expiry as reported
  to the handoff is 2026-11-23; rotation stays the owner's action.
- Branch `docs/q4b-independent-review-evidence-nov2026`; handoff base `2491ae4`; tip before this batch
  `27c595d9c8f1` (verified on the remote at the start of the session). `origin/main` is now `6f9344476958`.
  Main's movement since the handoff base is the DEBT-025 API-auth work and documentation (PRs #87, #94, #108,
  #109, #110); it touches no file under `docs/reviews` (see `verify/MAIN_DRIFT_SINCE_2491ae4.txt`).
- Review baselines (`16d663a`, `ed3d141`, `2491ae4`, probes on `4a4783c`/`f13bfde`) are unchanged. Main's
  change set includes `interface/api.py`, so HTTP-layer findings were produced on older baselines and are
  NOT re-checked here.

## 2. What was retrieved by GitHub and repository searches

### 2.1 The three Doc exports (ME-01 to ME-03): LOCATED in the repository

Branch `docs/verification-3cb-evidence-snapshots-nov2026`, commit `3146c647a4ba6af186f6c3931fe2cdb840054865`
(2026-11-09, no open PR seen), directory `docs/architecture/verification-3cb-evidence-snapshots/`, holds
Markdown and DOCX exports of: Q2/Q5 pack (platform rev 28), Q4 brief (rev 13), Q4-b brief (rev 19).

- VERIFIED: all six files recomputed from the committed bytes (`git archive` of the pinned commit) match that
  branch's own `SHA256SUMS`, and sizes match its manifest. Full hashes and sizes are in
  `verify/SNAPSHOT_BRANCH_VERIFY_OUTPUT.txt`.
- VERIFIED (read-only Docs reads, three calls, no edits): the manifest's Doc ids map to the handoff's links:
  `a8a1f900-2bb0-46ad-8ead-e055cf939aa9` = `MpmCtTRoaiHKQiQkJNCJLG` (Q4-b brief),
  `b5227c99-327f-483d-b726-3f93d37b8265` = `PNJZ381PjSfzMiKeYcaAvg` (pack),
  `85f80a7c-c273-4902-b8f1-fe009d3a3de5` = `HYVpzUxz9PspA4hmUcPLHS` (Q4 brief).
- NOT VERIFIED: the statement in that branch's README/MANIFEST that the files are Docs-service exports that were
  not retyped by a model. It is the committing session's assertion. The Docs reads here did not show the attached
  export copies, so the service-side hashes could not be compared. Whether the Docs have advanced past those
  revisions was not checked.
- Supersedes handoff v1, which said these Docs were not in the repository. They are, on a separate unmerged
  branch. This review did not copy them into this branch (custody is an owner decision, ME-04).

### 2.2 D1/D2 wording (ME-12): LOCATED on an unmerged PR branch, with a conflict

- PR #83 branch `docs/fz-freeze-decision-register-oct2026` at `dda84f294d4cb0429e82e740ab43252529a7a86a`:
  `KNOWN_ISSUES.md` records "FZ-D1 ACCEPTED, option (a)" (keep `handle() -> str`, add a structured internal
  result consumed by the API) and "FZ-D2 ACCEPTED, option (i)" (stalled and hard-deadline generations are
  failures, partial text kept in `metadata["partial_output"]`), dated Oct 16, 2026, with FZ-01 still OPEN.
  Verbatim lines and the PR author's 2026-11-02 comment are in `verify/PR83_D1_D2_EXTRACT.txt`.
- `origin/main` at `6f9344476958` contains no FZ-D1/FZ-D2 text (count 0). The PR #83 comment itself says the
  decisions are not main-branch records until the PR is reconciled or merged, and that no implementation owner
  or human review is recorded.
- CONFLICT, not resolved here: the Q4-b brief rev 19 treats the D1 contract choice as undecided, whereas PR #83
  records option (a) as accepted. The owner must say which record governs.
- AMBIGUITY, not resolved here: "D2" has at least three referents in this repository: FZ-D2 above; the
  Verification D2 (FAILED is a process/outcome result status, not a VerificationVerdict), which the brief cites;
  and a K4.2 decision numbered D2 (not traced in this batch). Which one the mission means is an owner statement.

### 2.3 CI artifacts and logs: platform data exists, sandbox cannot download

With the token, the artifact download endpoints for artifacts 12857857088 and 12173949037 and the run-log endpoint
for run 40781867485 each answered with a redirect (the artifacts and logs are not expired). The redirect hosts
(`productionresultssa2/0.blob.core.windows.net`, `results-receiver.actions.githubusercontent.com`) cannot be
resolved from the sandbox (DNS failure; an allowed host resolved normally as a control). No bytes were
retrieved by this route. The owner-delivered intakes below supplied the four raw artifact zips.

### 2.4 Repository-wide searches (read-only)

- All remote branch refs fetched (124 branches per the API). The four CI run/artifact ids appear only in this
  review branch's own files; no other ref carries CI bytes.
- A path-name pattern scan of all refs for probe, log and diff files identified no original probe outputs and
  no diff output for `4a4783c`/`f13bfde` (hits belonged to unrelated workstreams). It was a file-name match
  only, not a content search, and is not exhaustive: ME-06 outputs and ME-08 stay NOT FOUND.
- Gists: 0. Releases: 0. Issue/PR comments: 66 (keyword hits in PR #93, #83 and #103 comments; only the #83
  comment is relevant, see 2.2). Review comments: 35 (no hits).
- PR #81 head is unchanged at `647b63e`; issue #105 is unchanged (open, unassigned, one comment dated 2026-11-02).

## 3. Owner uploads (intake register: `intake/INTAKE_REGISTER.tsv`, `intake/ZIP_MEMBERS.tsv`)

Received files are preserved unmodified in `received/` (byte-identical to the uploads, checked with `cmp`).
Register paths are sandbox-absolute and are kept as recorded. Recomputation: `verify/verify_intake.py`;
recorded output: `verify/VERIFY_OUTPUT.txt` (exit 0).

| ID | File | Bytes | SHA-256 |
|----|------|-------|---------|
| I001 | ME07_CI_ARTIFACTS_PARTIAL_RECOVERY.zip | 23283 | 3519af68f418d46d63ddc0ea77572b3541301cee50cf7ff725077807d19af0ef |
| I002 | ME06_PROBE_SCRIPTS_MEMBER_VERIFIED.zip | 9342 | 0a024a85a2f95df1c4c72cb8869db56521d88e89e15860081438c27ff3b7c4dc |
| I003 | drift-report.zip | 2318 | 6651320038614d52604eabdf505e88b36cb7b5f0a9826acd51cdc168c6cc4301 |
| I004 | pytest-output.zip | 1164 | 0a271629118a2b5005756bf81a75f4284cdb126869d694ef99b7b01e23bba52e |

### I001 (ME-07): partial recovery of CI artifacts

- Contents: raw `pytest-output.zip` and `drift-report.zip` for run 40781867485 (commit `4a4783c`) and run
  39226693573 (commit `f13bfde`), the sender's extracted copies, sender hash lists, `API_METADATA.json`,
  `ACQUISITION_NOTES.md`. No `workflow-logs.zip` for either run, no `run-metadata.json`.
- VERIFIED: all four raw zips match the platform digest and size captured earlier by authenticated API in
  `ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/api/` (independent of the sender), match the sender's hash lists,
  pass zip integrity, and every inner member matches the sender's extracted copy. Run to commit mapping is taken
  from this review's own run records: both runs are attempt 1, event push, branch main, conclusion success.
- Content: run `4a4783c`: 2073 passed, 14 skipped, 1 xfailed, exit code 0. Run `f13bfde`: 2058 passed,
  14 skipped, 1 xfailed, exit code 0. The two drift reports differ only in their generation timestamp.
- LIMIT: the pytest output is progress characters and a final summary; it names no tests and gives no per-file
  counts. It supports "the full suite passed in CI" and nothing narrower. It does not confirm the "170 tests on
  `4a4783c`" figure (a subset claim) and does not satisfy the six-file log requirement.
- ASSERTED by the sender, not verified: acquisition was done through a connected GitHub integration in another
  container; decoded per-job logs were retrieved but not preserved (character counts only in the notes).
  Artifact expiry for the `4a4783c` pair is listed as 2027-01-26 in the sender's metadata.

### I002 (ME-06): probe scripts, member-verified

- Contents: `probe_main.py` to `probe_main5.py`, `README.md` (the six original members) and the sender's
  `RECOVERY_MANIFEST.txt`. The outer archive is a repack (9342 B); the original `files.zip` (8443 B,
  `73c4e524...`) is NOT recovered. The sender says the members came from a library archive `files(7).zip`
  that this review has not seen; that is asserted.
- VERIFIED: sizes and SHA-256 of all six members match this review's Batch 1 record of the original
  `files.zip` (`ME_RECOVERY_BATCH_1/acquisition_records/search_logs/S05_archive_verification.txt`). Four of them
  (`probe_main.py` to `probe_main4.py`) also match the full hashes the Q4-b brief carries (one occurrence each,
  `verify/SNAPSHOT_BRANCH_VERIFY_OUTPUT.txt`). `probe_main5.py` and `README.md` have no hash in the brief and
  match only the Batch 1 record.
- NOT delivered: the probe outputs. The sender's README says the quoted results were produced on `f13bfde`
  (P1 to P6), re-run on `4a4783c` (P1 to P8), with P9 on `4a4783c` only; none of those outputs is in the package.
- Custody note: handoff v1 decision D-08 kept the owner's original scripts out of this branch. The owner
  authorized this push, which was described as including the scripts, so the package is committed as received.

### I003 and I004 (ME-07): the `4a4783c` pair delivered again

Byte-identical to the corresponding raw zips inside I001 (outer bytes, inner members and digests). They add no
new content. The sender did not state the acquisition route, so the repetition is recorded as a second delivery,
not as independent corroboration.

## 4. Still not recovered or not established

- Probe outputs (ME-06) and diff output for `4a4783c` and `f13bfde` (ME-08); original captures for ME-05.
- Run-level `workflow-logs.zip` for both runs (ME-07). Routes: owner runs
  `gh api repos/1h0lde4/ocbrain-v4.1/actions/runs/<id>/logs` per run, or allows the two blocked hosts in the
  sandbox network settings so the retrieval can be repeated here.
- Independent corroboration of the Doc exports' provenance (ME-01 to ME-03).
- Owner statements: which record governs the D1 contract choice; which D2 the mission means; whether section
  10.3 of the Q4 brief is the decision ledger; whether the snapshot branch satisfies the custody direction.
- Everything this review lists as blocked pending authorization (consumer assessments, probe re-execution on the
  current main, any test run) remains blocked. None was started.

## 5. Method, read-only operations and limits

- GitHub: authenticated read-only GET requests only (run, artifact, job and log redirects; PR #81 and #83;
  open-PR list; issue and review comments; gists; releases; branches; repository size) plus `git fetch` and
  `git archive`/`git show` against remote refs. Public clone was used for the branch itself.
- Docs: three `read` calls on the Docs projects named in 2.1. No create, update, export or delete.
- No test, probe, benchmark or code execution against the repository was performed. `verify_intake.py` reads
  the received zips in memory and existing repo records only; it uses no network.
- Everything quoted as "verified" is a recomputation in this session from the named bytes. Statements about how
  the sender or the snapshot session produced their files are recorded as asserted.

## 6. Files in this package

- `README.md` (this record); `ME_STATUS_ADDENDUM_2.tsv` (new status rows, same columns as
  `../ME_STATUS_DIMENSIONS.tsv`, which is left unchanged);
- `received/` (I001 to I004 as received); `intake/` (toolkit register and member listing);
- `verify/` (`verify_intake.py`, `VERIFY_OUTPUT.txt`, `SNAPSHOT_BRANCH_VERIFY_OUTPUT.txt`,
  `PR83_D1_D2_EXTRACT.txt`, `MAIN_DRIFT_SINCE_2491ae4.txt`);
- `SHA256SUMS.txt` (covers every file above except itself). Check with
  `cd <this directory> && sha256sum -c SHA256SUMS.txt`.
