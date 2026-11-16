# ME_RECOVERY_BATCH_1

Evidence-recovery package for the Q4-b review inventory (ME-01 to ME-15). Status PARTIALLY COMPLETE; review disposition OPEN - NO PASS. Start with `reports/BATCH_1_FINAL_REPORT.md`.

- `originals/`: intentionally holds no document files (no export bytes were preserved); each folder explains why.
- `historical_evidence/`: one STATUS.md per target (nothing original recovered).
- `acquisition_records/`: export call log and Docs read transcriptions (operator transcriptions, derivative); raw GitHub captures saved by `curl` (`.body` and `.headers.txt`); search logs S01-S06.
- `manifests/`: `ACQUISITION_MANIFEST.tsv`, `SHA256SUMS.txt`, `ME_RECOVERY_MAPPING.tsv`, `SOURCE_SEARCH_REGISTER.tsv`.
- `reports/`: document export, historical evidence, archive integrity, unrecovered evidence, final report.
Hash classes: files under `acquisition_records/source_metadata/*.body|*.headers.txt` are original byte captures of GitHub responses made in this batch (new supporting records, not historical evidence). Everything else is a derivative or report.
