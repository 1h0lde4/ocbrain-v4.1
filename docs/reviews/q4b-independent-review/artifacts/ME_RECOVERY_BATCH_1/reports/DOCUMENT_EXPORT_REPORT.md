# Document export report (Workstream A)

Review disposition remains OPEN - NO PASS. Labels: VERIFIED, REPORTED, INFERRED, UNVERIFIED, NOT FOUND, INACCESSIBLE, NOT EXECUTED. **No document export was preserved. Documents that could not be exported as preserved bytes: all three.** No SHA-256 over delivered export bytes exists for any of them, and none is claimed.

Method common to all: the platform's `export` verb through the Docs tool; responses reach only the operator's context; there is no programmatic path to save them (details and options in `acquisition_records/original_export_responses/EXPORT_CALL_LOG.md`). No retyped, reconstructed, converted, screenshot or copied-text substitute was created.

| Field | Q4-b brief | Q2/Q5 decision pack | Q4 brief (section 10.3 ledger) |
|---|---|---|---|
| Identity | VERIFIED by platform read: artifact `MpmCtTRoaiHKQiQkJNCJLG`, slug `a8a1f900-2bb0-46ad-8ead-e055cf939aa9`, tab `746fc00f-f273`, node `c9bfd0a8-bd8a` | REPORTED from the preceding task: artifact `PNJZ381PjSfzMiKeYcaAvg`, slug `b5227c99-327f-483d-b726-3f93d37b8265`, tab `0c2d3cb2-caa3`, node `4a3bfaae-440e` | REPORTED from the preceding task: artifact `HYVpzUxz9PspA4hmUcPLHS`, slug `85f80a7c-c273-4902-b8f1-fe009d3a3de5`, tab `abbce208-6540`, node `35e76bcb-57e5` |
| Expected revision | 19 | 28 | 13 |
| Observed revision in this batch | 19 (VERIFIED: export response and `atRev` reads report 19 as latest) | not observed in this batch (size probes carry no revision); last observed 28 in the preceding task (REPORTED) | not observed in this batch; last observed 13 in the preceding task (REPORTED) |
| Export attempted | markdown, full: delivered inline; docx and pdf size probes | markdown, docx, pdf size probes only | markdown, docx, pdf size probes only |
| Platform-reported size (bytes) | markdown 71,911 (delivered, not preserved); docx 36,774; pdf 1,336,013 | markdown 26,238; docx 15,843; pdf 472,480 | markdown 54,262; docx 26,408; pdf 805,476 |
| Original bytes preserved / SHA-256 | none / NOT OBTAINED | none / NOT OBTAINED | none / NOT OBTAINED |
| Export response preserved | transcription of metadata only (EXPORT_CALL_LOG.md E01); payload not preserved | transcription of refusal metadata only (E02, E06, E08) | transcription of refusal metadata only (E03, E07, E09) |
| Filename, MIME, acquisition time (UTC) | not preserved; time not recorded | n/a | n/a |
| Acquisition status | INACCESSIBLE (delivered to the operator, no way to preserve) | LOCATED (full payload not requested: same preservation limit) | LOCATED (same) |

## Why the pack and the Q4 brief were probed, not exported in full
The Q4-b brief export showed the platform delivers the whole payload inline and that nothing here can land it on disk. Requesting the pack and Q4 brief payloads (about 35,000 and 73,000 base64 characters for markdown, far more for pdf) would have added no preservable evidence; the size probes record availability instead. This is a choice of the operator and is recorded as such; it is not a platform refusal.

## Derived observations (no assessment made)
- The brief itself records that the Docs export returns inline base64 only, that no content hash or repository copy of the three Docs was produced, and that block ids and per-block hashes are its integrity record (REPORTED, brief rev 19 text; located by text search). This batch's E01 is consistent with that statement.
- The Q4-b brief's Markdown size was reported at a smaller figure in the brief's own text for an earlier revision; the current platform figure is 71,911 bytes at revision 19 (REPORTED figure not re-read in full this batch).

## Remaining limitations and what would resolve them
1. Exports are obtainable by an owner download from the claude.ai interface (Word, PDF or Markdown), uploaded unmodified; hashes then describe those uploaded bytes. 2. Or a harness that saves tool results as files. 3. Or owner authorization of a platform-side write path (creating a blob inside the document), which changes the source document and was not used. Which route to use is an owner decision; this batch makes none.
