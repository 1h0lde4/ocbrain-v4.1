# Fresh-extraction verification — D-2 / D-5 / fetch-quotation-header revision

**Subject:** `fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip`  
**SHA-256:** `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc`  
**Size:** 254,581 bytes  
**Archive entries:** 87 total: 86 files listed in `MANIFEST.sha256` plus the manifest itself.

## Checks run in this pass

1. The ZIP's SHA-256 and byte size were computed from the generated file.
2. ZIP integrity test passed (`unzip -t`).
3. Listed all archive entries before extraction; found **0** absolute or parent-traversal paths.
4. Extracted into a newly created empty directory.
5. Ran `sha256sum -c MANIFEST.sha256`: **86/86 OK**, 0 failures.
6. Compared the extracted file list to the manifest file list: no missing files and no unlisted files.
7. Asserted all ledger decisions D-1 through D-11 remain **OPEN**.
8. Compared the packet and audit report hashes with the prior delivered archive: both are unchanged.
9. Confirmed that, relative to the original extracted archive, exactly three inner-bundle files changed: `MANIFEST.sha256`, `report/decision_ledger_1d813bd_OPEN.md`, and `docs/doc_fetch_quotations_as_returned.md`. No files were added or removed.

## Content and scope notes

- The decision ledger clarifies that the 3.42.0 FTS5 secure-delete compatibility fact does **not**, by itself, establish OCBrain's minimum supported SQLite version. D-2 remains **OPEN** with no version recommendation.
- The D-5 recommendation remains **PROPOSED, not ratified**: keep physical erasure separate, do not use FTS5 secure-delete as a repair while its anomaly is unexplained, and do not claim VACUUM as erasure. D-5 remains **OPEN**, and RD-10 / DEL-1…4 remain outstanding.
- The fetch-quotation header distinguishes historical fetch-tool output from raw source text, documents the limited 3.45.1 raw-doc verification, and says to use heading IDs/raw packaged excerpts rather than treating the fetch-returned section numbers as authoritative.
- Packet SHA-256 remains `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2`; the packet text was not changed in this revision. The previously recorded 83/83 transcription check was not rerun in this packaging pass; this pass verified the unchanged packet hash and the rebuilt archive/manifest.
- Audit-report SHA-256 remains `2dc09f0d1d89d2613d1dd56d3e0a34753492319efd1018c7ef295b0faad028af`; the audit report was not edited in this pass.
- The previously supplied archive was preserved at its original path and was not overwritten. This remains documentation/evidence-bundle work only: no product code, tests, CI configuration, allow-list, xfail, repository branch, commit, PR, or push was changed or created.

**Status:** updated archive passes the fresh-extraction and manifest checks described above. This does not constitute a new execution of the product probes or a new 83/83 transcription-check run. G4 remains OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED.