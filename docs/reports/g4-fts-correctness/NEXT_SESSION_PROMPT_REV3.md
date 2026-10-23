# Fresh-session prompt — OCBrain G4 FTS correctness / migration-safety blockers

**Task date:** 2026-10-23  
**Repository:** 1h0lde4/ocbrain-v4.1  
**Scope:** evidence-first decision preparation. No implementation is authorized.

## Mandatory inputs

Read, in this order:

1. docs/reports/g4-fts-correctness/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md
2. The exact original full handoff attachment, handoff(1).md, SHA-256 da162e71d6bd0b92650134eceb6af1ecfa430484ac08b179d7aaa48a97fa716d. Confirm the file hash. Do not substitute a line-ending-normalized copy: the embedded original task prompt was verified byte-identical and must remain so. The prior handoff's transfer-status paragraph is historical; the REV3 continuation records the later user-directed documentation checkpoint.
3. docs/reports/g4-fts-correctness/decision_ledger_1d813bd_OPEN_D2_D5_REV2.md
4. docs/reports/g4-fts-correctness/doc_fetch_quotations_as_returned_HEADER_REV2.md
5. docs/reports/g4-fts-correctness/fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md
6. The exact externally preserved ZIP fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip uploaded by the user to this session. Verify SHA-256 f9ee626551e5175a7ba0893c336a77917b8be1b4078903cc6ac5853ad7e509cc and size 254,581 bytes. If it is not attached or does not match, stop evidence-dependent claims and report the precise blocker. Do not fabricate/reconstruct raw outputs.

## First actions: establish live state, do not assume carried claims

- Discover current origin/main / GitHub default-branch tip and repository working state. Never assume the old baseline 1d813bdae320bf34110c29836c81dc901c601c9b, later ref 488129b8768a88a3d21dfd80b1f5407d50aba908, or snapshot f13bfdefcdd197ed1f966de0b1f93037a4168af4 is still the current tip.
- Re-check the current blob/content for core/memory/backends/sqlite_storage.py, core/memory/knowledge_entry.py, tests/test_session4c_architecture.py, and check current KNOWN_ISSUES.md, CURRENT_STATE.md, IMPLEMENTATION_ROADMAP.md, and all open PRs/branches that touch the FTS or overlapping context/isolation work.
- Verify archive paths before extracting into a fresh empty directory and run sha256sum -c MANIFEST.sha256. Keep the ZIP and raw outputs immutable. Distinguish historical baseline, negative-control diagnostics, protocol-feasibility probes, and fixed-product evidence; the last category is still UNEXERCISED.
- Do not rerun all probes by habit. Follow the original handoff's explicit revisit triggers; prefer reuse of preserved outputs and live current source.

## Deliverable: owner decision pack for D-1…D-11

For every decision, provide (a) exact question, (b) alternatives that are actually available, (c) evidence for and against each alternative, (d) consequences/dependencies, (e) recommendation and confidence, (f) what evidence would invalidate the recommendation, and (g) the exact wording needed for the maintainer's ledger/ADR entry. Mark every recommendation PROPOSED. Do not record or imply that the user accepted a choice.

- D-1: pull the FTS batch forward, keep it at I-4, or defer.
- D-2: minimum SQLite version(s) and SQLite acquisition/runtime policy.
- D-3: RD-13 classification of OBS-LC-1/2/3.
- D-4: migration-state mechanism and verification.
- D-5: whether physical erasure stays separate from FTS correctness remediation.
- D-6: evidence-label ratification.
- D-7: real-database fixtures and coverage.
- D-8: owner for documentation corrections.
- D-9: concurrency operating model, including busy-timeout exhaustion.
- D-10: handling of unrecognised, malformed, or newer migration state.
- D-11: owner and sequence for I-3a/I-4 and DEBT-042 overlap in sqlite_storage.py.

At minimum, carry forward these constraints:
- FTS-A2 stale-posting state was observed through the unchanged API in 3/3 fresh-database histories from the first delete; the unchanged constructor repaired none of the 7 prepared fixtures.
- rank=1 FTS5 integrity verification catches external-content table/index disagreement in the tested build. Ordinary integrity-check and PRAGMA integrity_check are not substitutes.
- executescript() can commit a pending transaction first under the tested Python 3.12.3 / connection mode; migration statements must be explicitly ordered inside the intended transaction.
- Marker-only and trigger-body-only migration-state checks are insufficient in the observed stranded state. D-4's in-transaction rank=1 check is a recommendation, not an accepted decision.
- Atomicity evidence is limited: 0 mixed states in 300 observations, but only 2/250 kills landed in the ambiguous commit window. Concurrency was 15/15 one-migrator races, with a waiting contender timing out after 20.05 s. Do not generalise these disposable-database results to production.
- Only SQLite 3.45.1 / Python 3.12.3 were tested. The FTS5 secure-delete option's 3.42.0 introduction does not by itself set the product's minimum version; its integrity-check anomaly remains unexplained.
- D-5's recommendation is to keep physical erasure separate; that does not satisfy RD-10 / DEL-1…4, and VACUUM is not an erasure guarantee.
- The rev-2 transcription checker passed 83/83 on final packet text SHA db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2. Do not claim the checker was re-run in the REV3 packaging pass. The fresh extraction report says 86/86 manifest entries passed.
- Real database prevalence/size, constructor migration integration, power loss, contender crash, four-process end-to-end and a multi-version SQLite matrix remain unknown or untested.

## Governance and out-of-scope constraints

- Do not modify product code or tests, ci.yml, environmental allowlists, xfails, runtime contracts or migration code.
- Do not create an implementation branch, start a migration implementation, change freeze state, or mark any decision ACCEPTED.
- Do not merge this documentation PR or silently decide D-1…D-11. The current task is analysis and a recommendation pack for the maintainer.
- Preserve raw evidence, original inputs, original handoff and the REV3 ZIP byte-for-byte.
- Before ending, report exact refs and hashes, artifacts inspected, checks actually run, checks not run, residual uncertainty, and one next action for the maintainer.

## Acceptance criteria

1. The packet hash and all 86 manifest entries are independently validated from the attached ZIP.
2. Current main and open overlapping work are freshly checked; stale refs are clearly marked as historical.
3. Each D-1…D-11 has one internally consistent recommendation with evidence, dependencies and explicit unresolved owner decisions.
4. Recommendation language never becomes acceptance language. G4 remains OPEN · High · freeze-blocking; G5–G8 remain HELD; freeze readiness remains NOT DECLARED.
5. No product implementation or test changes occur.
