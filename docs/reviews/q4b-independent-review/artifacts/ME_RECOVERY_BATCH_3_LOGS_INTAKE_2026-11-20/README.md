# ME recovery batch 3: workflow log intake record (2026-11-20)

**Status: records only.** This package changes no disposition. The Q4-b brief is not validated, the review disposition stays
OPEN, NO PASS, and no mission is closed. It adds new files only; nothing in the earlier batches is edited. Docs-only: no
code, test, probe or Docs-service action was performed, and no workflow was run or re-run.

## 1. Authority and baselines

- Owner instructions in the chat, in order: a report that GitHub permissions were granted (the retrieval was retried:
  the download hosts still did not resolve from the sandbox, and the token still worked, scopes `repo`, `workflow`
  and others, expiry 2026-11-23 01:11 UTC); three uploads (I005 to I007 below); "U may", answering the assistant's
  request to push one follow-up addendum (new files only: the intake records, the three archives as received, the
  recovery and verification scripts with recorded output, new ME status rows) plus `handoff.md` version 1.2, to this
  branch only. It does not authorize a PR, a merge, a push to `main`, a test or probe run, owner decisions, or any change to findings.
- Branch `docs/q4b-independent-review-evidence-nov2026`; tip before this batch `766610b2ce55` (handoff v1.1), verified
  on the remote at the start of this batch; base `2491ae4`. `origin/main` is now `2ebf76a39f03`.
- Main moved again since handoff v1.1 (`6f93444`): CI workflow action-pin bumps (`ci.yml`, `release.yml`), a privacy
  containment change (`core/privacy.py`, `tests/test_privacy.py`) and documentation; nothing under `docs/reviews`
  (`verify/MAIN_DRIFT_SINCE_6f93444.txt`). The logs below describe two earlier runs of the earlier `ci.yml`.

## 2. Owner uploads (intake register: `intake/INTAKE_REGISTER.tsv`, cumulative, I001 to I007)

Received files are in `received/`, unmodified (byte-identical to the uploads, checked with `cmp`). I001 to I004 are
in the Batch 2 package. Register paths are sandbox-absolute and kept as recorded. Recomputation:
`verify/verify_logs_intake.py`; recorded output `verify/VERIFY_OUTPUT.txt` (33 of 33 checks, exit 0).

| ID | File | Bytes | SHA-256 |
|----|------|-------|---------|
| I005 | workflow-logs.zip | 60308 | d19632ef317a4a0466ea122ca9ee34a718da45475b9982cb13e3b5bd9cc059f8 |
| I006 | workflow-logs_1.zip | 29923 | a0f3f3d5f2e87b7e3c948676befd14f685ad92d297ac06378f0a3b93e03240cb |
| I007 | workflow-logs-39226693573.zip | 28934 | c1a9ef268ba848d876645030beba01f523df967ff8b336aa44d79186c2668cd0 |

### I005: not a readable zip as delivered (run 40781867485 content, damaged)

- The file is the zip's bytes passed through a text re-encoding (the effect of a Windows PowerShell `>` redirect of
  binary output): a UTF-16LE byte-order mark, every byte decoded as an OEM cp850 character, every lone CR or LF
  turned into CRLF, one extra CRLF appended. Exact original bytes cannot be recovered from it, because the redirect
  discarded which line terminator each CR/LF was.
- The central directory survived intact (it contains no CR/LF): its member names, CRC32 values and uncompressed
  sizes equal I006's exactly (check in `verify/VERIFY_OUTPUT.txt`). So I005 is the same archive as I006, damaged.
- DERIVED recovery (`recover/recover_ps_redirect_members.py`, output `recover/RECOVERY_OUTPUT.txt`): 2 of 4 members were
  reconstructed and accepted only because compressed size, uncompressed size and CRC32 match the central directory:
  the two small runner `system.txt` members. They are byte-identical to I006's clean members. The two large step
  logs were NOT recovered (`0_tests.txt`: search budget exhausted after 3,000,042 nodes; `1_drift-and-ownership.txt`: the one
  candidate found failed the CRC32). Derived output is not original bytes and is not committed here.
- The upload could not be fixed by this review. A clean re-export (I006) was supplied instead.

### I006: clean re-export, run 40781867485 (commit `4a4783c47ac37971a7d51ab3d7ab6fc904a37106`)

  - `0_tests.txt`: 87837 bytes, CRC32 a1556ede
  - `tests/system.txt`: 569 bytes, CRC32 354d3af6
  - `1_drift-and-ownership.txt`: 43614 bytes, CRC32 6b304cb8
  - `drift-and-ownership/system.txt`: 583 bytes, CRC32 e5cea529

- VERIFIED: valid zip (exactly 29,923 bytes, the size predicted from I005's end-of-archive record), every member's
  data matches its CRC32, member CRC32/sizes equal those in I005's central directory.
- VERIFIED: the full head SHA appears in both job logs; the runners named in the `system.txt` members (1000001879
  `tests`, 1000001878 `drift-and-ownership`) equal the API job records captured in Batch 1; log timestamps fall inside
  the API job windows.
- VERIFIED: tests job summary `2073 passed, 14 skipped, 1 xfailed, 2 warnings in 72.66s`; all 41 non-empty lines of the
  earlier `pytest-output` artifact (I001) appear verbatim in the log.

### I007: clean export, run 39226693573 (commit `f13bfdefcdd197ed1f966de0b1f93037a4168af4`; run id given only in the file name)

  - `0_drift-and-ownership.txt`: 41148 bytes, CRC32 e187e53f
  - `drift-and-ownership/system.txt`: 583 bytes, CRC32 1c05f9ad
  - `1_tests.txt`: 85722 bytes, CRC32 ca0c221b
  - `tests/system.txt`: 569 bytes, CRC32 8eb01f67

- VERIFIED: valid zip, every member's data matches its CRC32; the full head SHA appears in both job logs; runners 1000001425
  (`tests`) and 1000001426 (`drift-and-ownership`) equal the API job records; log timestamps fall inside the API job windows.
- VERIFIED: tests job summary `2058 passed, 14 skipped, 1 xfailed, 2 warnings in 104.00s`; all 38 non-empty lines of the
  earlier `pytest-output` artifact appear verbatim in the log.

### What the two tests logs say, and do not say

- Test step in both: `pytest tests/ -q --tb=short` (the whole `tests/` directory, quiet mode), exit code recorded, then
  `scripts/ci_test_gate.py` reports an empty list of known environmental failures still failing and "Test gate passed:
  no unlisted failures, no errors". With no failing test in either run, the known-failure allowlist concealed nothing in these runs.
- The `4a4783c` run has 15 more passing tests than the `f13bfde` run (2073 versus 2058); the logs do not say which tests.
- Neither log names a test file (zero mentions of `test_verification`; no PASSED/FAILED markers). They support "the
  full suite passed in CI" and nothing narrower. They do NOT confirm the "170 tests on `4a4783c`" figure or any six-file subset.
- NOT VERIFIED: the sender's export route (not stated), and equality with the platform's original log archives
  (the platform publishes no digest for log archives and the download hosts are unreachable from the sandbox).
  The `drift-and-ownership` logs were checked for identity and timing only, their content was not analysed.

## 3. Still not recovered or not established

- A per-file or per-test attestation for the "170 tests" claim: would need a verbose run (a separate authorization) or an
  owner explanation of the figure.
- Probe outputs (ME-06) and diff output for `4a4783c` and `f13bfde` (ME-08); original captures for ME-05.
- Independent corroboration of the Doc exports' provenance (ME-01 to ME-03).
- Owner statements: which record governs the D1 contract choice; which D2 the mission means; whether section 10.3 of the
  Q4 brief is the decision ledger; custody (ME-04). Nothing was decided or inferred here.
- HTTP-layer findings (`interface/api.py`) were produced on older baselines and are not re-checked on the current `main`.

## 4. Method, read-only operations and limits

- Read-only: the received zips and existing repo records are read in memory; no network is used by the scripts.
  GitHub use this batch: a token validity and scope check, and `git fetch` (nothing else beyond the earlier batches).
- The recovery search guides itself with the shape of GitHub Actions log lines (timestamp at each line start). It can
  only ever accept a candidate that matches CRC32 and both sizes from the intact central directory.
- A corrupted copy of I006 makes `verify_logs_intake.py` exit 1 (false-green check, run once during preparation, not recorded).
- Statements about how senders produced files are recorded as asserted.

## 5. Files in this package

- `README.md` (this record); `ME_STATUS_ADDENDUM_3.tsv` (new status rows, same columns as `../ME_STATUS_DIMENSIONS.tsv`, which is unchanged);
- `received/` (I005 to I007 as received); `intake/` (cumulative register and member listing);
- `recover/` (`recover_ps_redirect_members.py`, `RECOVERY_OUTPUT.txt`);
- `verify/` (`verify_logs_intake.py`, `VERIFY_OUTPUT.txt`, `MAIN_DRIFT_SINCE_6f93444.txt`);
- `SHA256SUMS.txt` (every file above except itself). Check with `cd <this directory> && sha256sum -c SHA256SUMS.txt`.
