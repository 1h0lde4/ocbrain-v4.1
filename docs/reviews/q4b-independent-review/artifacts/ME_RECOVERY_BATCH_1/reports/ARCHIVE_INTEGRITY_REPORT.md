# Archive integrity report (B3)

Review disposition remains OPEN - NO PASS. Everything here was recomputed from the actual files at 2026-11-08T20:17:46Z (raw log: `acquisition_records/search_logs/S05_archive_verification.txt`). Neither archive nor manifest was modified. The previous operator's "all matched" statement is not relied on.

| Check | Result |
|---|---|
| `files.zip` (8,443 bytes) SHA-256 | `73c4e52440d018d86194e9ccb0db7feb72224263caf5754a5045b30c750d2222` (the value recorded in earlier reviews); zip test OK; six members |
| Members vs hashes printed in the Q4-b brief (rev 19, block `ma34sn5v797.49327`) | `probe_main.py`, `probe_main2.py`, `probe_main3.py`, `probe_main4.py`: full 64-hex SHA-256 values MATCH. `probe_main5.py` and `README.md`: the brief paragraph records no hash; computed `403f6c37853fe8db33a128d22a8f56faaf2ce96511c7016f862bb60ebe522a11` and `fc5ba8aeb31db4a4983600a32233a64c3755ec5c7249b4c8c9e536e1916d5681` are not independently corroborated |
| `ARCHIVE_MANIFEST_r9_1.tsv` (19 rows) | all 19 files present, 0 hash discrepancies |
| `ARCHIVE_MANIFEST.tsv` (16 rows) | all present, 0 discrepancies; its 16 rows carry identical hashes in the r9.1 manifest |
| Bundles | ten delivered zip archives were tested with `zipfile` and reported no errors |
| Files in the output folder not listed in the r9.1 manifest at check time | `ARCHIVE_MANIFEST_r9_1.tsv`, `CONSOLIDATED_EVIDENCE_REGISTER_r9_1.md`, `q4b_review_consolidated_register_r9_1.zip`, `Q4B_MISSING_EVIDENCE_INVENTORY.md`, `INVENTORY_MANIFEST.tsv` (the last four are covered by `INVENTORY_MANIFEST.tsv`, which this batch also re-checks) |

Limits: a hash match shows each file equals what the manifest recorded; it does not show the manifest or the earlier reports are correct or that the files were authored as described. The manifest is itself part of the review chain, not an independent original. No owner-issued hash of `files.zip` exists in the materials seen; the only independent anchor is the brief's recording of four member hashes.
