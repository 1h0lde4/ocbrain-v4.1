# G4 / FTS correctness — decision ledger (every item OPEN)

**Status: PROPOSED.** This ledger records decisions that belong to the maintainer. **No item is decided, ratified or accepted here.** A "recommendation" appears only where the evidence supports one; where the evidence cannot settle a choice the entry says *none*, and lists what each option would cost. G4 stays **OPEN · High · freeze-blocking**; G5–G8 **HELD**; freeze readiness **NOT DECLARED**. D1/D2/D3 (the FZ-01/02/05 contract decisions) are **not** touched by this ledger.

Evidence tree `1d813bdae320bf34110c29836c81dc901c601c9b`; current `main` tip observed `f13bfdefcdd197ed1f966de0b1f93037a4168af4` (core files relevant here unchanged). References: packet rev 2 (`…_REV2_PROPOSED.md`), audit report (`evidence_audit_report_1d813bd.md`), spec (`abe17d13-…`).

| ID | Decision | Owner | Status |
|---|---|---|---|
| D-1 | Pull the FTS batch forward (RD-13 / spec §12 I-4) / keep at I-4 / defer | maintainer | **OPEN** |
| D-2 | Minimum supported SQLite version(s); how the product obtains its SQLite | maintainer | **OPEN** |
| D-3 | RD-13: classify OBS-LC-1/2/3 | maintainer | **OPEN** |
| D-4 | Migration-state mechanism | maintainer | **OPEN** |
| D-5 | Physical erasure stays separate (RD-10, DEL-1…4) | maintainer | **OPEN** |
| D-6 | Ratify the three evidence labels and addendum rev 2 | maintainer | **OPEN** |
| D-7 | Supply real-database fixtures / run the read-only check (optional) | maintainer | **OPEN** |
| D-8 | Owner of documentation corrections | maintainer | **OPEN** |
| D-9 | Concurrency operating model (new) | maintainer | **OPEN** |
| D-10 | Policy for unrecognised, malformed or newer migration state (new) | maintainer | **OPEN** |
| D-11 | Owner and sequence for overlapping isolation work (new) | maintainer | **OPEN** |

---

## D-1 — Pull forward, keep at I-4, or defer
- **Options:** (a) standalone, separately verifiable batch (spec §12 I-4 note, §9.4); (b) keep inside I-4; (c) defer.
- **Evidence bearing:** the batch closes **no** G4 isolation requirement (INV-01…22 unchanged). The defect is **reachable through ordinary use of the unchanged product**: a fresh database driven only through `write`/`update`/`delete` reached the ghost state in 3/3 histories, from the first delete; so any real database that ever deleted an entry through the API may carry it (UNKNOWN for real databases). It is not shown to be a content-exposure path (LD 4/4 PASS). It touches `sqlite_storage.py`, which later isolation batches (I-3a) also touch, and `main` now carries DEBT-042 against the same file. The migration is a legacy-data operation whose gates (D-2, D-4, D-9, D-10, G-4) are open.
- **Recommendation:** none. The evidence says the defect accumulates until the trigger is fixed; it cannot say whether that outranks isolation work.
- **Still required:** the maintainer's choice and, if (a), resolution of D-2, D-4, D-9, D-10, D-11 and the constructor-integration question (G-4) before implementation.

## D-2 — Minimum supported SQLite version
- **Options:** declare a floor and test it; require the application to bundle/pin a specific SQLite; declare "whatever Python loads" and test a list.
- **Evidence bearing:** only 3.45.1 (Python 3.12.3) was tested. Version-dependent facts found: FTS5 secure-delete option introduced 3.42.0 (compat constraint, FTS5 docs `#the_secure_delete_configuration_option`, §6.12 in the 3.45.1 docs, read raw); VACUUM rowid behaviour depends on an `xferOptimization` detail (3.45.1 source); Python's `sqlite3` transaction semantics depend on the Python version; core `secure_delete` default is a build property (1 here, compile option `SECURE_DELETE`).
- **Recommendation:** none on the number. Whatever is declared must record `sqlite3.sqlite_version` and `sqlite_source_id()` as loaded by the application and be run through FTS-A6 (migration on existing fixtures per runtime).
- **Documentation wording:** verified at the raw 3.45.1 docs only (`docs/raw_sqlite_docs_verification.md`); the live pages and the wording for every version the policy declares must be re-read.
- **Still required:** declared policy; other SQLite builds (not available in this audit); execution of the matrix; wording re-read per declared version.

## D-3 — RD-13: OBS-LC-1/2/3
- **Options:** register as new findings; attach to an existing issue; keep as study observations.
- **Evidence bearing:** neither `KNOWN_ISSUES.md` at the baseline nor at the tip contains an entry for the `ke_ad` ghost/stale-posting condition (negative grep, evidence not proof; DEBT-042 is a different FTS defect, query-syntax escaping). OBS-LC-1/2 are now reproduced through the unchanged API on a fresh database, not only through prepared fixtures. OBS-GOV-2, also in RD-13, is **not** part of this batch.
- **Recommendation:** none.
- **Still required:** the classification; if registered, an ID and owner.

## D-4 — Migration-state mechanism
- **Options:** **1.** prove atomicity on every path, no marker; **2.** a versioned marker recorded in the same transaction after verification (table `ocbrain_schema_migrations`, or `PRAGMA user_version`). Presented side by side in packet rev 2 §5.3.
- **Evidence bearing:** a trigger-body test is **insufficient** (stranded state S3b invisible to it, 48 ghost rowids). A marker is **insufficient alone** (drift after the marker, S5, invisible to it; the explicit `rank=1` check detected and repaired it). Both marker backends worked on the product connection; `user_version` is transactional (T6) and unused under `core/` (STATIC); the table adds one schema object that unchanged code ignores (T9). Unchanged code opened on a new-state database changes nothing and its API workload stays clean (T9).
- **Recommendation (evidence-supported part only):** under **either** alternative, run `rank=1` verification (plus the independent reference) **inside** the migrating transaction (0.048 s at 10k rows, 0.243 s at 50k in the bundled run; re-executions varied 0.030–0.061 s and 0.155–0.267 s — order of magnitude only). **The choice between 1 and 2 is not supported by the evidence and stays with the maintainer.**
- **Still required:** the choice; for alternative 1, a proof of atomicity on every path (constructor, crash, kill, any other code that could swap the trigger separately); for alternative 2, the marker schema/versioning decision and new-DB initialisation in the same transaction.

## D-5 — Physical erasure stays separate (RD-10, DEL-1…4)
- **Scope kept apart:** DB files, WAL/sidecars, FTS shadow data, archives, vector/graph copies, backups.
- **Evidence bearing:** the FTS5 documentation itself (`#the_secure_delete_configuration_option`, raw 3.45.1 docs) says old full-text entries stay in the database file until merges remove them and can be used to reconstruct deleted rows, and that file-level recovery also needs the core `PRAGMA secure_delete = 1`; a trigger fix does not remove residue (PE-01…04 still fail on V1); the FTS5 secure-delete variant passes PE but fails RC-09 and its `integrity-check` anomaly is **unexplained**; VACUUM keeps rowids only because the table has an index, an implementation detail (rev 2 §4.8), and does not remove ghost postings.
- **Recommendation (evidence-supported):** keep physical erasure a separate requirement under RD-10; do **not** enable FTS5 secure-delete as a fix while the anomaly is unexplained; do **not** claim VACUUM as erasure; keep the anomaly out of this batch's acceptance criteria.
- **Still required:** the maintainer's RD-10 policy.

## D-6 — Ratify the evidence labels and addendum rev 2
- **Options:** (a) ratify rev 2 (three product-state labels; purpose and evidence kind as separate axes; V1/V2/V3 as test-satisfiability, not negative controls); (b) keep revision 1's wording; (c) amend.
- **Evidence bearing:** revision 1 called V1/V2 "negative-control-style" although they pass; a negative control must fail (definition in the review).
- **Recommendation:** none beyond noting that (a) matches the written definition.
- **Still required:** ratification; nothing in this audit depends on it.

## D-7 — Real-database fixtures (optional)
- **Options:** supply anonymised copies; run the read-only check on a copy (inside a rolled-back transaction): `INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rank) VALUES('integrity-check', 1);` (an error means disagreement); supply nothing.
- **Evidence bearing:** real legacy states, sizes and ghost presence are UNKNOWN; extrapolated lock hold reaches 20 s near 1.9 M rows on this machine (EXTRAPOLATED).
- **Recommendation:** none; nothing in the packet depends on it, but G-5 (size and startup budget) cannot close without it.

## D-8 — Owner of documentation corrections
- **Items:** `docs/reports/SESSION4C_REPORT.md:142` (says `ke_ad` is "not affected", contradicted by observation); REM-012 (`context-compiler-remediation-register.md:75`, "Confirmed live") vs `ARCHITECTURE_HARDENING_SESSION_REPORT.md:170` (`WebLearningPipeline` "dead code"); and, for the packet itself, AF-01…AF-14 of the audit report (rev 2 is a proposed correction, unratified).
- **Evidence bearing:** the documents are unchanged between the baseline and the tip.
- **Recommendation:** none. **Still required:** an owner; no document is edited by this audit.

## D-9 — Concurrency operating model (new)
- **Options:** (a) fail startup when the migration lock is not obtained within the busy timeout; (b) bounded retry with backoff; (c) one designated process migrates before the others start (main process before worker pool, webhook, task runner); (d) other.
- **Evidence bearing:** exactly one migrator in 15/15 races (2, 4, 6 processes); a contender waits up to the 20 s busy timeout and then fails with `database is locked` (observed 20.05 s) — that error means "not migrated by me", never "already migrated"; a connection holding an older snapshot cannot become the writer and fails immediately; readers on older snapshots see the pre-state and block checkpointing, not the commit; lock hold 0.49–0.57 s at 50k rows (extrapolated 20 s near 1.9 M). The product's four processes each construct the backend (STATIC). Untested: contender crash, mixed old/new code, four-process end-to-end, power loss.
- **Recommendation:** none. Constraint supported by the evidence: whichever model is chosen, `database is locked` from the migration attempt must be handled explicitly and tested.
- **Still required:** the choice; tests per packet rev 2 §9 item 7.

## D-10 — Unrecognised, malformed or newer migration state (new)
- **Options:** fail closed (the probe's behaviour: refuse and leave untouched); log and continue unmigrated; attempt repair; different handling per state.
- **Evidence bearing:** S4b (unrecognised trigger), S4c (malformed marker), S4d (newer marker) were refused without touching state and refused again on every start; S4a (trigger absent) was recreated and rebuilt.
- **Recommendation:** none; the policy must be explicit and tested for every row of the state table (rev 2 §4.5).
- **Still required:** the policy.

## D-11 — Owner and sequence for overlapping isolation work (new)
- **Options:** FTS batch first; isolation I-3a first; same branch; coordinated sequence with an explicit merge order.
- **Evidence bearing:** spec §12 rows I-3a and I-4 both list `sqlite_storage.py` (and `unified_memory.py`); spec lines 428–435 note the overlap; DEBT-042 (`_fts_escape`, `sqlite_storage.py:363-372`) is registered on `main` against the same file. No owner or order exists.
- **Recommendation:** none. **Still required:** an owner and a sequence before any implementation planning.

---

## Not decided here
No decision above is made; no status of G4–G8 changes; no implementation, branch, PR or push is authorised; the ADR-KERNEL-07 D-4 xfail, `ci.yml` and the allowlist are untouched.
