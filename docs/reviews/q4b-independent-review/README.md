# Q4-b independent adversarial review: evidence record (docs only)

**Disposition: OPEN, NO PASS.** This directory preserves the independent review of OCBrain's Q4-b brief and the recovery work for its missing primary evidence. It is a documentation record: it contains no code, changes no test, and authorizes no implementation, merge, ownership assignment or owner decision. The review's findings, statuses and conclusions are exactly those in the reports; nothing was reworded for this commit.

## What is here
- `artifacts/` is a byte-for-byte mirror of the review session's output folder (163 files). `.gitattributes` in this directory sets `* -text`, so no line-ending conversion applies and every SHA-256 in the manifests verifies as committed.
  - Reports (revision order): `INTERIM_REVIEW_REPORT.md` (r1), `..._r2.md`, `..._r3.md`, `INTERIM_REVIEW_REPORT_r4_SUPPLEMENT.md`, `REVIEW_NOTE_r5..r8`, `CONSOLIDATED_EVIDENCE_REGISTER_r9.md`, `CONSOLIDATED_EVIDENCE_REGISTER_r9_1.md` (current consolidated register).
  - Missing-evidence work: `Q4B_MISSING_EVIDENCE_INVENTORY.md` (ME-01 to ME-15), `ME_RECOVERY_BATCH_1/` (acquisition package), `ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB/` (authenticated read-only GitHub verification), `GITHUB_GOVERNANCE_SNAPSHOT_2026-11-13/` (separate governance record), `ME_STATUS_DIMENSIONS.tsv` (discovery, acquisition, integrity, sufficiency per item).
  - Owner-facing: `OWNER_EVIDENCE_REQUEST.md`, `ME07_OWNER_ACQUISITION_INSTRUCTIONS.md`. Tooling: `ME_INTAKE_TOOLKIT/` (hashing and recording of received files).
  - Bundles (`q4b_*.zip`, `ME_RECOVERY_BATCH_1.zip`) hold the probes, outputs and logs behind r1 to r9.1.
- Repository root `handoff.md` (this branch only) is the session handoff for resuming the remaining work.

## Verify integrity
Run `sha256sum -c` on any package's own list, for example `(cd artifacts/ME_RECOVERY_BATCH_1 && sha256sum -c manifests/SHA256SUMS.txt)`, `(cd artifacts/ME_RECOVERY_BATCH_1_ADDENDUM_AUTH_GITHUB && sha256sum -c manifests/SHA256SUMS.txt)`, `(cd artifacts/GITHUB_GOVERNANCE_SNAPSHOT_2026-11-13 && sha256sum -c SHA256SUMS.txt)`, `(cd artifacts/ME_INTAKE_TOOLKIT && sha256sum -c SHA256SUMS.txt)`. `artifacts/ARCHIVE_MANIFEST_r9_1.tsv` lists SHA-256 for the r1 to r9 reports and bundles (columns: file, sha256, description; paths relative to `artifacts/`).

## Not in this directory
The owner's original upload `files.zip` (five probe scripts and a README; SHA-256 `73c4e52440d018d86194e9ccb0db7feb72224263caf5754a5045b30c750d2222`) is not committed: the original author recorded those scripts as outside the repository, and this record does not change that. The three source Claude Docs (Q4-b brief, Q2/Q5 decision pack, Q4 brief) and any exports of them are also not here; no export bytes were obtained (see `Q4B_MISSING_EVIDENCE_INVENTORY.md` and `ME_RECOVERY_BATCH_1/reports/BATCH_1_FINAL_REPORT.md`).
