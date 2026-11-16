# Intake procedure for owner-supplied evidence (ME items)

Review disposition remains OPEN - NO PASS. This procedure covers receiving and recording files only. It runs no probe or test, changes no finding or inventory status, and edits nothing in `ME_RECOVERY_BATCH_1/` or in any earlier artifact.

## Steps on receipt
1. Put the files in a scratch folder. Do not open and re-save them.
2. Run `python3 me_intake.py --dest <intake dir outside any repository> --me <ME item> --label "<what the sender says it is>" --revision "<asserted revision or date>" --sender-note "<asserted details>" <files>`. One call per ME item. The tool reads each file once, hashes those exact bytes, copies them unchanged (read-only copy), re-hashes the copy, and appends rows to `INTAKE_REGISTER.tsv` (and `ZIP_MEMBERS.tsv` for zip files). Existing rows are never rewritten.
3. Keep the sender's own fields (filename, revision, time, notes) as asserted in the register; they stay UNVERIFIED until checked against something independent.
4. Any inspection copy (for example a text extraction) is made separately and recorded with its own hash and its relationship to the original. The original hash is never replaced by the derivative's.
5. When the source publishes a digest (GitHub does for Actions artifact archives), pass it with `--expect-sha256`; the match or mismatch is recorded in the notes. It applies to the raw archive only, never to extracted files; extracted files are checked against the member hashes in `ZIP_MEMBERS.tsv`.
6. Write a new acquisition-status file next to the register (do not edit the Batch 1 mapping). Statuses use the Batch 1 vocabulary: RECOVERED, PARTIALLY RECOVERED, LOCATED, NOT FOUND, INACCESSIBLE, NOT RECOVERABLE, NOT INVESTIGATED. NOT RECOVERABLE needs a dated statement from the owner or original author, not silence.

## Item-specific checks (record results, do not draw conclusions)
| ME item | On receipt, record |
|---|---|
| ME-01 to ME-03 | filename; byte count and SHA-256 as received; format; revision the sender saw. Compare the byte count with the platform-reported sizes in `OWNER_EVIDENCE_REQUEST.md` and note any difference without treating it as an error. A file that shows a revision other than the expected 19, 28 or 13 is recorded as received at that revision. |
| ME-05 | which capture it is (rev 17 outline, rev 10 change view, section 22 record); a screenshot is recorded as a screenshot |
| ME-06 to ME-08 | the commit it claims to belong to; any command, environment or timestamp it carries, as asserted; no inference of a successful run from a file's presence |
| ME-07, ME-13 | each GitHub output file: HTTP status and rate-limit lines from the saved headers; whether it contains any check run or workflow run for the two commits; any zip log archive via `ZIP_MEMBERS.tsv` |
| ME-04, ME-12 | the statement text verbatim, its date, and its series label; no interpretation |

## Tested
The script was run on synthetic files in scratch space: SHA-256 equals `sha256sum`; copies are byte-identical (CRLF line endings preserved); source files unchanged; ids continue across calls; zip members recorded in memory; a non-zip file with a .zip name is flagged; a missing path aborts the whole call before anything is copied or recorded. Not tested: the overwrite-refusal branch, non-Linux platforms, files larger than memory (the tool reads each file whole). The synthetic test files are not part of this toolkit.
