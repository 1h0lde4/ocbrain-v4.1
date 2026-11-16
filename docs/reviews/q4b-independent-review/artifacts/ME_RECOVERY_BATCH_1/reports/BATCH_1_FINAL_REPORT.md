# ME Recovery Batch 1: final report

**Status: PARTIALLY COMPLETE (not a successful recovery). Review disposition remains OPEN - NO PASS. Batch 1 does not authorize any change to that disposition.** Package date 2026-11-08. Labels: VERIFIED, REPORTED, INFERRED, UNVERIFIED, NOT FOUND, INACCESSIBLE, NOT EXECUTED.

## 1. Executive summary
Workstream A: the three source Claude Docs were investigated. The Q4-b brief's native Markdown export was delivered (revision 19, 71,911 bytes) but no way exists here to preserve the delivered bytes without retyping, so no export, no SHA-256 over delivered bytes and no decoded payload is in the package. Platform-reported sizes for markdown, docx and pdf of all three documents were recorded. Workstream B: no original historical artifact was recovered (revision 17 and 10 outputs; probe outputs, test logs and diff output for `4a4783c` and `f13bfde`); GitHub CI search was blocked by an API rate limit. Independent re-hashing of the existing archives found no discrepancy, and four of the six `files.zip` members match full hashes recorded in the brief. New byte-exact captures of GitHub pages were taken (ME-13, partial).

## 2. Documents successfully exported
None as preserved bytes. See `reports/DOCUMENT_EXPORT_REPORT.md`.

## 3. Historical evidence recovered
None (original). New supporting records only: GitHub page captures and Docs read transcriptions.

## 4. Located but inaccessible
GitHub CI evidence for both commits (API HTTP 403); export payloads (preservation limit); platform revision data for revisions 17 (readable) and 10 (inconclusive) without a capture mechanism.

## 5. Not found
Revision 17 outline output; revision 10 change views; raw section 22 evidence; revision 19 activity metadata (empty history); probe outputs, test logs and diff output for both commits; D2 definition text.

## 6. ME-01 to ME-15 acquisition summary
See `manifests/ME_RECOVERY_MAPPING.tsv` (each item once). INACCESSIBLE: ME-01, ME-07. LOCATED: ME-02, ME-03, ME-04, ME-05, ME-09, ME-10, ME-11, ME-12. NOT FOUND: ME-06, ME-08. PARTIALLY RECOVERED: ME-13. NOT INVESTIGATED: ME-14, ME-15 (execution evidence, out of scope). Original inventory statuses and classes are preserved verbatim; no finding or inventory status was changed. No item is NOT RECOVERABLE.

## 7. Archive verification
Performed from the actual files; see `reports/ARCHIVE_INTEGRITY_REPORT.md`. 19 of 19 `ARCHIVE_MANIFEST_r9_1.tsv` rows and 16 of 16 `ARCHIVE_MANIFEST.tsv` rows match; `files.zip` unchanged; four members match brief-recorded hashes.

## 8. Provenance limitations
Docs responses cannot be preserved byte-for-byte; every Docs record here is an operator transcription (derivative). Docs call times were not recorded. The pack and Q4 brief revisions were not re-observed in this batch. GitHub pages were captured with a browser-like user agent and exclude dynamic content. A hash match does not establish authorship or correctness.

## 9. Remaining evidence dependencies
Owner-supplied unmodified exports (or a capture mechanism) for ME-01 to ME-03; any surviving original outputs for ME-05 to ME-08; authorized or unthrottled GitHub API access for ME-07 and ME-13; owner decision records for ME-04 and ME-12; environment-dependent execution evidence for ME-14 and ME-15 in a separately authorized batch.

## 10. Work not performed
No probe, test, 170-test selection, embedding-model experiment, production-composition run or new verification experiment; no repository change, branch, push or PR action; no Claude Doc edit, comment, suggestion or blob; no credential use; no retyped, converted or reconstructed export; no regenerated diff or log; no resolution of D1, D2 or D6; no choice of which document is the ledger; no change to any finding.

## 11. Recommended next batch (not started)
A separately authorized batch to (a) receive owner-exported files and hash them as delivered; (b) obtain GitHub CI records with authorized access; (c) if desired, regenerate revision views with a capture mechanism, labelled as new supporting records; then (d) a decision-reconciliation workstream and (e) environment-dependent verification.

## Acceptance criteria
| ID | Result |
|---|---|
| A1 three documents individually investigated | met |
| A2 genuine exports acquired wherever accessible | NOT met: one delivered, none preserved |
| A3 SHA-256 describes delivered bytes | NOT met: no hash exists |
| A4 original export responses preserved | NOT met: transcriptions only |
| A5 revision 17 and 10 investigated | met (not found; 17 readable; 10 inconclusive) |
| A6 raw section 22 evidence investigated | met (not found) |
| A7 outputs for both commits investigated | met (not found; CI API inaccessible) |
| A8 every acquisition has a provenance record | met with limitation: Docs call times not recorded |
| A9 ME-01 to ME-15 mapped individually | met |
| A10 archive claims independently checked | met |
| A11 unrecovered items identified | met |
| A12 originals preserved unmodified | met for existing archives; no new originals recovered |
| A13 no unauthorized activity | met per the section 10 list |
| A14 deliverables consistent and inspectable | see `manifests/SHA256SUMS.txt`; consistency check recorded in the handoff |
