# G4 FTS Correctness — REV3 Repository Continuation

**Record date:** 2026-10-23 UTC  
**Workstream:** G4 FTS correctness and migration safety; evidence audit and decision preparation  
**Status:** PROPOSED / decision-gated. This record is not an ADR, acceptance record, or implementation authorization.

## 1. Authority and relationship to the prior handoff

The exact original full handoff remains a separately preserved attachment named handoff(1).md, SHA-256 da162e71d6bd0b92650134eceb6af1ecfa430484ac08b179d7aaa48a97fa716d. Attach it to the next session and verify that hash. It contains the original 19 sections and embeds the original task prompt. It is deliberately not copied into Git through a text-normalizing connector, because line-ending conversion could violate the verified byte-identity of the embedded prompt. Its earlier transfer-status section is historical; the user subsequently asked for a repository documentation checkpoint. That later request authorizes this documentation transfer only; it does not authorize a product fix, a migration design, a requirement ratification, or a freeze-readiness claim.

The evidence ZIP remains outside Git, as required by the original evidence-preservation note. Upload the exact ZIP to the next session before relying on any raw output.

## 2. Exact REV3 evidence artifact

- Archive: fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip
- SHA-256: f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc
- Size: 254,581 bytes
- Manifest: 86 entries; fresh extraction and manifest validation passed 86/86.
- Final packet-text SHA-256: db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2
- Final transcription checker: 83/83 against that packet text. This is a transcription/self-consistency gate, not independent correctness proof. Revision-1 independent derivation remains 385/387 because the 50k-row duration is 0.410–0.501 s, not a single 0.41 s value.
- Revised D-2/D-5 ledger SHA-256: f6dda8a2515b4e9117906e3982cd0dcc6f338c84318ab62d1e2970c9d6c12c16
- Revised fetch-quotation header SHA-256: f9abc19929958da8d4fda8b9235447860956d4f38dc3e3290f02dd0531b75ecc
- Fresh-extraction verification report SHA-256: dd77ace0e170c3367a8423d775a9fd091e4bfa8a813f1a4a6c366f107b15ecb5
- Archival pre-REV3 handoff SHA-256: da162e71d6bd0b92650134eceb6af1ecfa430484ac08b179d7aaa48a97fa716d

The report explicitly discloses that the final packaging pass did not rerun the 83/83 checker. Do not describe the check as having been rerun in that pass. The hashes listed here for the ledger, quotation header, verification report and handoff identify their preserved external disk files. The text copies added to this branch were normalized to LF by the file-content connector and therefore have different byte hashes; the REV3 ZIP and its contents remain the byte-preserved evidence authority.

## 3. What REV3 changed

D-2 now clarifies that SQLite 3.42.0 is a compatibility floor only if the FTS5 secure-delete option is selected; it does not independently establish OCBrain's product-wide minimum SQLite version. Only SQLite 3.45.1/Python 3.12.3 was tested in the audit.

D-5 retains the recommendation to keep physical erasure separate. This does not satisfy or waive RD-10 / DEL-1…4; the secure-delete integrity-check anomaly remains unexplained, and VACUUM is not an erasure guarantee.

The fetch-quotation header identifies fetch-tool section numbering as historical rather than authoritative. Raw SQLite 3.45.1 documentation excerpts were verified locally; the live sqlite.org pages were not read raw because the shell received HTTP 403.

## 4. Evidence claims and limits that must survive

- The unchanged historical API produced a stale-posting/ghost-row state in 3/3 fresh-database histories, beginning with the first delete. The unchanged constructor repaired none of 7 prepared fixtures.
- Plain FTS5 integrity-check and PRAGMA integrity_check do not establish consistency between an external-content index and its content table; the tested rank=1 FTS5 check does.
- Python executescript() commits a pending transaction before executing the script under the tested transaction mode; do not plan a migration as a single executescript() following BEGIN.
- Migration-state checks based only on trigger-body recognition or a marker can miss a stranded/corrupt state. The evidence-backed recommendation for D-4 is to perform rank=1 verification inside the migration transaction; this recommendation remains OPEN until the maintainer ratifies it.
- Atomicity: 0 mixed states in 300 observations, but only 2 of 250 kills fell in the ambiguous commit window. This is weak sampling, not proof under power loss.
- Concurrency: exactly one migrator in 15/15 races; a waiter failed with database is locked after 20.05 s. At 50k rows the observed lock was 0.49–0.57 s. This does not establish the production operating model.
- V1/V2 pass the RC tests and are satisfiability diagnostics, not negative controls.
- Real database inventory, sizes, prevalence, power-loss behavior, contender crash, four-process end-to-end behavior and constructor-path migration remain UNKNOWN or UNTESTED. No FIXED PRODUCT evidence exists.

## 5. Live repository reconciliation performed for this continuation

The live default branch was main at f13bfdefcdd197ed1f966de0b1f93037a4168af4 when checked on 2026-10-23. The following file blobs were identical at baseline 1d813bdae320bf34110c29836c81dc901c601c9b, later reference 488129b8768a88a3d21dfd80b1f5407d50aba908, and live main:

| File | Blob SHA |
|---|---|
| core/memory/backends/sqlite_storage.py | ed0cbae6b54d157a2afb22e391c56da20acc118a |
| core/memory/knowledge_entry.py | 0d5e07163acd8e152c312dbbb233e3bcb1094965 |
| tests/test_session4c_architecture.py | 327c703c56465972674bf4cd8ce8348cb5b3c0ca |
| docs/architecture/PROJECT_INSTRUCTIONS.md | e2cf94704a742ff865221af9db5f0c2fca51f133 |

KNOWN_ISSUES.md did change since the old baseline; current main has DEBT-042 (_fts_escape() query-syntax escaping) and DEBT-043. DEBT-042 is a distinct issue in the same source file and must not be conflated with FTS-A2 stale external-content postings.

At check time, open PRs #88, #87, #83, #81, #79 and #89 also touched CURRENT_STATE.md or KNOWN_ISSUES.md. This branch intentionally avoids editing those conflict-prone files. It updates the roadmap and places the G4-specific truth in this dedicated record; reconcile the shared tracking files once those concurrent changes have been reconciled. PR #89 changes context persistence/orchestrator/planner/tests and KNOWN_ISSUES.md, but does not change sqlite_storage.py. Re-check all live refs before relying on any of these snapshot claims.

## 6. Remaining decisions — every item still OPEN

| ID | Required maintainer decision |
|---|---|
| D-1 | Pull the FTS batch forward, keep it at I-4, or defer it |
| D-2 | Minimum supported SQLite version(s) and how the product obtains SQLite |
| D-3 | RD-13 classification of OBS-LC-1/2/3 |
| D-4 | Migration-state recognition/verification mechanism |
| D-5 | Keep physical erasure separate from FTS correctness remediation |
| D-6 | Ratify the evidence labels |
| D-7 | Real-database fixtures and coverage |
| D-8 | Owner of documentation corrections |
| D-9 | Concurrency operating model |
| D-10 | Policy for unrecognised, malformed or newer migration state |
| D-11 | Owner and sequence for overlapping isolation work in sqlite_storage.py |

The ledger recommendation is limited to D-4 (rank=1 verification inside the transaction) and D-5 (keep physical erasure separate). Both remain OPEN. The implementation-planning blockers include D-2, D-4, D-9, D-10, D-11, constructor integration, and unknown real-database sizes. None of this authorizes a product migration.

## 7. Required next-session sequence

1. Verify the attached REV3 ZIP SHA-256 before extraction; list archive paths before extracting into a new empty directory; validate all 86 manifest entries.
2. Re-check main, the three FTS files above, KNOWN_ISSUES.md, CURRENT_STATE.md, and all overlapping open PRs. Do not restore the old 1d813bd state or assume f13bfde remains the current tip.
3. Read this continuation, the archived 19-section handoff, the revised ledger, quotation header and verification report before further investigation. Do not rerun probes whose revisit triggers have not occurred.
4. Prepare a maintainer decision pack for D-1…D-11: current evidence, allowed alternatives, explicit consequence/dependency, recommendation, confidence, and what proof would be needed to close each item. Recommendations remain PROPOSED; do not mark ledger items ACCEPTED.
5. Do not start implementation until the maintainer records the required decisions and explicitly authorizes a separately bounded implementation batch. No changes to product code, tests, CI, xfails, allowlists or freeze status are authorized by this continuation.

## 8. Governing state

**G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.** The repository checkpoint is documentation-only and is not an acceptance or freeze-readiness claim.
