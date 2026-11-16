# ME-07 controlled acquisition: owner-side instructions

Review disposition remains OPEN - NO PASS. This adds to `OWNER_EVIDENCE_REQUEST.md` section 3 (which stays as issued) and corrects the commit-to-run pairing that circulated in a recent assessment. **Do not re-run any workflow** (a new run is new evidence, not recovery), and do not send any token.

## 1. Which run belongs to which commit (VERIFIED from the saved run records, `ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/api/run_*_detail.body`)
| Commit | Run id | Attempt | Run created (UTC) | Artifact to preserve | Optional second artifact |
|---|---|---|---|---|---|
| `4a4783c` (`4a4783c47ac37971a7d51ab3d7ab6fc904a37106`) | 40781867485 | 1 | 2026-10-28T22:41:17Z | `pytest-output` id 12857857088, 1,164 bytes, `sha256:0a271629118a2b5005756bf81a75f4284cdb126869d694ef99b7b01e23bba52e` | `drift-report` id 12857053468, 2,318 bytes, `sha256:6651320038614d52604eabdf505e88b36cb7b5f0a9826acd51cdc168c6cc4301` |
| `f13bfde` (`f13bfdefcdd197ed1f966de0b1f93037a4168af4`) | 39226693573 | 1 | 2026-10-19T08:59:17Z | `pytest-output` id 12173949037, 893 bytes, `sha256:7d63a9caa0f9e745d72f6d708d3b89c92db2af81c90cf466a30169cdd8566a06` | `drift-report` id 12174022650, 2,319 bytes, `sha256:3a0049d338dc22628501dde6351fe51e95902e2fdcf781016ec8b3d9cf0aba30` |
Both runs: workflow `CI`, event `push`, branch `main`, repository `1h0lde4/ocbrain-v4.1`. The pairing in the assessment (`f13bfde` with run 40781867485 and 893 bytes; `4a4783c` with run 39226693573 and 1,164 bytes) is swapped; the run records show the reverse. The digests are what GitHub reported for the stored artifact archives. I hold no artifact bytes yet.

## 2. Why raw archives and extracted files are separate evidence
`gh run download` extracts files, and a hash of an extracted file is not a hash of the original archive, so the GitHub digest could not be checked against it. Please preserve the raw archives first and extract copies afterwards.

## 3. Commands (bash, zsh, Git Bash or WSL; untested with your authentication)
Do not use PowerShell redirection (`>`) for the `.zip` downloads: it can re-encode binary output. If a command fails, send the error text.
```
R=1h0lde4/ocbrain-v4.1
mkdir -p ME07_CI_ACQUISITION/RUN_40781867485_4a4783c/{raw,extracted,rendered} ME07_CI_ACQUISITION/RUN_39226693573_f13bfde/{raw,extracted,rendered}
```
Run `4a4783c`:
```
cd ME07_CI_ACQUISITION/RUN_40781867485_4a4783c
gh api repos/$R/actions/runs/40781867485 > run-metadata.json
gh api repos/$R/actions/runs/40781867485/artifacts > artifact-metadata.json
gh api repos/$R/actions/artifacts/12857857088/zip > raw/pytest-output.zip
gh api repos/$R/actions/artifacts/12857053468/zip > raw/drift-report.zip
gh api repos/$R/actions/runs/40781867485/logs > raw/workflow-logs.zip
gh run view 40781867485 -R $R --log > rendered/workflow-logs.txt
sha256sum raw/*.zip > raw/SHA256SUMS
cd ../..
```
Run `f13bfde`:
```
cd ME07_CI_ACQUISITION/RUN_39226693573_f13bfde
gh api repos/$R/actions/runs/39226693573 > run-metadata.json
gh api repos/$R/actions/runs/39226693573/artifacts > artifact-metadata.json
gh api repos/$R/actions/artifacts/12173949037/zip > raw/pytest-output.zip
gh api repos/$R/actions/artifacts/12174022650/zip > raw/drift-report.zip
gh api repos/$R/actions/runs/39226693573/logs > raw/workflow-logs.zip
gh run view 39226693573 -R $R --log > rendered/workflow-logs.txt
sha256sum raw/*.zip > raw/SHA256SUMS
cd ../..
```
Then, for each run, make extracted copies without touching `raw/`:
```
unzip -o raw/pytest-output.zip -d extracted/pytest-output
unzip -o raw/drift-report.zip -d extracted/drift-report
(cd extracted && find . -type f -exec sha256sum {} \;) > extracted/SHA256SUMS
```
Also record, in `ACQUISITION_NOTES.md` inside `ME07_CI_ACQUISITION/`: the acquisition date, time and time zone; the exact commands used (copy them); anything that failed or returned HTTP 410 (expired logs) or 404. Send the whole `ME07_CI_ACQUISITION/` folder, preferably as one zip made after everything is saved, plus the original `.zip` files unmodified.

## 4. What I will verify on receipt (recording results, not interpreting them)
1. SHA-256 of each raw artifact zip against the GitHub digest above (match or mismatch, reported individually).
2. Member inventory and per-member hashes of each raw zip (computed in memory), then each extracted file against the matching member hash.
3. `run-metadata.json`: `head_sha` equals the full commit SHA, run id, attempt, workflow, event, branch, conclusion.
4. Whether the raw log archive's job names and timestamps agree with the job records captured earlier (`api/run_*_jobs.body`).
5. The rendered log is recorded as a derivative of the log archive, with its own hash.

## 5. What the result can and cannot show
It can show what GitHub's CI recorded for the repository's full test suite on each commit and that the preserved bytes match GitHub's digest. It cannot show the original author's six-file "170 passed" run, the probe outputs, or the diff output, so ME-06 and ME-08 and the six-file part of ME-07 stay as recorded. A `pytest-output` artifact does not by itself support the reported "170 passed", and a matching digest does not show that the contents support any finding.

## 6. What stays prohibited
No workflow re-runs, no commits, pushes, branches or PRs, no edits to existing packages, no findings closed, and no reading of a successful CI run as a pass.
