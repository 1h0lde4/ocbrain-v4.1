# FTS correctness batch — decision packet, REVISION 2 (PROPOSED, read-only, documentation-only errata)

**Status: PROPOSED. A decision packet, not an implementation authorization.**
G4 stays **OPEN · High · freeze-blocking**. G5–G8 stay **HELD**. Freeze readiness is **NOT DECLARED**. Nothing here closes, ratifies or accepts anything. No product code, test, workflow, allowlist or the strict ADR-KERNEL-07 D-4 xfail was touched; no branch, PR or push exists.

- Evidence tree: `1h0lde4/ocbrain-v4.1` @ `1d813bdae320bf34110c29836c81dc901c601c9b` (detached, clean, throw-away worktree; read-only). Everything labelled OBSERVED below was run against that tree, **Python 3.12.3, SQLite library 3.45.1 (`2024-01-30 16:01:20 e876e51a…`), Linux x86_64, one machine**.
- Supersedes nothing: revision 1 (`g4_fts_correctness_batch_decision_packet_1d813bd_PROPOSED.md`, sha256 `4d24d7666d6e076c46b95926e5a3745175f2369479257b65939b803412a13ce3`) and its addendum (sha256 `14184571a12694f443c53d5c8b83107a117125be814d527d0aa2e45f7d173ffd`) are preserved unedited. This file is a **separate, additive errata revision**; where it disagrees with revision 1, §C says why.
- Companions: `addendum_evidence_labels_REV2_PROPOSED.md`, `evidence_audit_report_1d813bd.md` (maps every quoted figure to its raw output), `decision_ledger_1d813bd_OPEN.md`, `README.md`, `MANIFEST.sha256`.
- Repository freshness (checked read-only, unauthenticated, 2026-10-20): `origin/main` = `f13bfdefcdd197ed1f966de0b1f93037a4168af4` (30 commits after the baseline). Between `1d813bd` and that tip, **`core/memory/backends/sqlite_storage.py`, `core/memory/knowledge_entry.py` and `tests/test_session4c_architecture.py` are byte-identical**; no file under `core/` changed. The commit `488129b8768a88a3d21dfd80b1f5407d50aba908` named in the task is a **merge of PR #80 (2026-10-16), an ancestor of the tip, not the tip**. One new documentation fact bears on this batch (DEBT-042, §3 and G-7).

---

## C. Change log against revision 1

| ID | Change | Why (evidence) |
|---|---|---|
| C-1 | **Provenance.** The "legacy fixtures" are separated into *prepared initial states* and *operations run through the unchanged historical implementation*; two new observations added (§4.2). | Revision 1 labelled "7/7 legacy fixtures fail `rank=1`" as a baseline observation, but those states were prepared (several with raw SQL). New probes: a **fresh** database created by the real constructor and driven **only** through `write`/`update`/`delete` reaches the ghost state in 3/3 histories; the unchanged constructor repairs none of the 7 prepared fixtures; the API workload reproduces the raw-SQL results 7/7. |
| C-2 | **Atomicity and ambiguous commit outcome** (§4.4, §5.2). Adds post-commit termination (exception and hard exit), a 250-trial SIGKILL series, a 40-variant torn-WAL simulation; defines what is claimed and what is not. | Revision 1 tested only four pre-commit points. 0 mixed states in 300 observations; ambiguous window sampled only twice by real kills (disclosed). |
| C-3 | **State dispositions** (§4.5, §5.3): ten states × two marker backends; the two alternatives presented side by side; trigger-body substring is never completion evidence. | The stranded state and a marker-invisible drift state are both observed. Choice stays with the maintainer (D-4, D-10). |
| C-4 | **Transaction boundary** (§4.6, §5.4): `executescript()` after `BEGIN` commits first; explicit ordered statements on the product's own connection work; new-DB init and existing-DB migration are different paths. | Observed T1–T10. A standalone SQL probe does **not** prove the constructor path (still UNVERIFIED). |
| C-5 | **Concurrency contract** (§4.7, §5.5): lock contention, the 20 s busy timeout, 2/4/6 processes, older-snapshot readers, writer traffic, holder killed, restart. | Revision 1 listed these as UNTESTED. They are now feasibility evidence, still not product evidence. |
| C-6 | **Evidence model** (§2, addendum rev 2): three product-state labels only; purpose and evidence kind are separate axes; V1/V2 re-classified as test-satisfiability, not negative controls; "fails-before/passes-after" retired. | Revision 1's matrix and addendum mixed label and purpose. |
| C-7 | **Duration figures corrected** (§4.9): 50k rows "0.41 s (two runs)" → **0.41–0.50 s** (0.410 and 0.501); lock hold including `rank=1` verification and marker: 0.49–0.57 s. | Independent derivation: the packet's own raw outputs. The original check script asserted only loose upper bounds for durations and could not see this. |
| C-8 | **VACUUM explanation** (§4.8): observed rowid stability is explained by the existence of an index on the table (SQLite 3.45.1 `src/insert.c` 3050–3063) and shown to fail for an index-less table. Still not guaranteed. | New control probe; source reading. |
| C-9 | **History precision** (§3): five commits touch the file under full history (incl. merge `6b8b0af`); plain `git log -- <path>` shows three. `ke_ad` body identical in all of them. The file is entirely CRLF. | `git log --full-history`; per-version trigger extraction. |
| C-10 | **Documentation provenance** (§3.1, §14): what was verified at raw source; the FTS5 / VACUUM wording is now verified against the **raw HTML of the SQLite 3.45.1 docs** (signature-verified Ubuntu package; `docs/raw_sqlite_docs_verification.md`) instead of a fetch-tool summary; section numbers corrected (cited by heading id); live `sqlite.org` pages still not read raw. | Required by the audit method. |
| C-11 | **New facts**: `PRAGMA integrity_check` never compares an external-content index with its content table (`fts5_main.c:2978` passes 0); the worktree tree digest depends on the worktree path. | Source reading; digest comparison. |
| C-12 | Gates and ledger extended (G-9, G-10; D-9, D-10, D-11); gaps updated (§11). | §10, §11, ledger. |

---

## 0. One-page summary (revised)

| Question | Answer from the evidence | Label / kind |
|---|---|---|
| Is there a retrieval-correctness defect in the FTS index? | Yes. The unchanged product, on a fresh database, driven only through its own API, produces stale postings, ghost matches and a failing `rank=1` check (3/3 histories); plain `integrity-check` and `PRAGMA integrity_check` do not see it. | HISTORICAL BASELINE — OBSERVED |
| Is it a content-exposure path? | Not shown. Logical deletion (LD-01..04) passes on every variant (tested through `SQLiteStorageBackend` only). The defect is index correctness (RC) plus physical residue (PE). | HISTORICAL BASELINE — OBSERVED (earlier bundle, re-run byte-identical) |
| Does the unchanged product repair legacy ghost states by itself? | No. Reopening 7 prepared legacy fixtures with the unchanged constructor changes nothing; the API workload ends in the same ghost state as raw SQL did (7/7). | HISTORICAL BASELINE — OBSERVED |
| Does a trigger fix alone repair legacy databases? Does `rebuild` alone suffice? | No / No (T and R fail 7/7 workload checks). | NEGATIVE CONTROL — OBSERVED |
| Does swap + rebuild repair legacy states and stay clean? | Yes on 7/7 prepared fixtures × 119 operations, and the canonical trigger keeps three fresh API histories clean. These are results about a PROPOSED protocol on probe artefacts. | n/a — probe artefact |
| Can the migration be atomic on the product's own connection? | Yes with explicit ordered statements (`BEGIN IMMEDIATE` … `COMMIT`); **no** with `executescript()` after `BEGIN` (it commits first). The constructor path itself is unchanged and **UNVERIFIED**. | OBSERVED (probe on `_connect()`); product path UNVERIFIED |
| What happens if the process dies around COMMIT? | In 300 observations (5 exception points, 5 hard-exit points, 250 SIGKILLs, 40 torn-WAL variants) the database was always a verified complete pre- or post-state, never mixed; retry converged; a further run was a no-op. Only 2 real kills landed while COMMIT was in flight. | OBSERVED / SIMULATED; limits in §4.4 |
| Is a trigger-body test, or a marker, enough? | No to the trigger body (stranded state invisible). A marker alone is not enough either: drift after the marker is invisible to it. Both are observed. | OBSERVED |
| Concurrency? | Exactly one migrator in 15/15 multi-process races; contenders wait up to the 20 s busy timeout, then fail with `database is locked`; an older-snapshot connection cannot upgrade to writer and fails immediately; readers see the pre-state until they finish. | OBSERVED (probe) |
| Is the secure-delete `integrity-check` anomaly explained? | No; excluded from acceptance criteria. | UNKNOWN |
| Is the batch ready to implement? | No. Gates §10 are open (minimum SQLite version, marker choice, constructor integration, concurrency policy, real-DB size, RD-13/I-4, isolation-overlap owner). | BLOCKED on maintainer decisions |

---

## 1. Three decisions, kept separate (unchanged)

| # | Decision | Owner | Stand |
|---|---|---|---|
| A | Should the FTS work be **specified**? | maintainer | This packet is the specification (PROPOSED), bounded and read-only. |
| B | Should the batch be **prioritised / pulled forward** (RD-13, spec §12 row I-4)? | maintainer | OPEN (ledger D-1). |
| C | Is the proposed migration **sufficiently proven to implement**? | maintainer, after §10 gates | Not yet. |

---

## 2. Evidence model (new)

**Axis 1 — product-state label. Exactly three exist. Nothing else is a label.**

| Label | Meaning | Sub-kinds |
|---|---|---|
| **HISTORICAL BASELINE** | what the actual, unchanged product does or contains at `1d813bd` | **OBSERVED** (it was run) · **STATIC** (it was read in source) |
| **NEGATIVE CONTROL** | a deliberately disabled or incomplete fix, on throw-away data, showing that a test or measurement can detect incompleteness | — |
| **FIXED PRODUCT** | the actual implementation at an immutable commit, against the same tests | none exists: **UNEXERCISED** |

A result about the PROPOSED protocol applied to a probe artefact, or about a diagnostic variant, **has no product-state label**; tables write it as *n/a — probe artefact*. "Protocol-feasibility evidence" is a description of purpose, not a fourth label.

**Axis 2 — purpose of an experiment** (descriptive): baseline characterisation · negative control · test-satisfiability (do variants V1/V2/V3 satisfy the RC tests?) · protocol feasibility · static grounding · measurement validation.

**Axis 3 — kind of evidence**: OBSERVED · STATIC · SIMULATED (e.g. torn WAL by truncation) · SYNTHETIC-PRECONDITION (a prepared initial state) · EXTRAPOLATED · UNTESTED · UNKNOWN · UNVERIFIED · PROPOSED · BLOCKED · OPEN.

**Terminology audit.** *baseline* — kept, restricted to the label above. *Negative control* — only T (trigger-only), R (rebuild-only), the non-atomic variant and detect-before-lock qualify; **V1/V2 are not negative controls** (they pass; they show which tests a trigger fix could satisfy); TR/A/RT are not negative controls either. *fails-before / passes-after* — not used in revision 1's text; retired in favour of one result column per label. *verified* — reserved for checks that were executed; "verified at 1d813bd" in revision 1's §2 meant "read at source" and is now written STATIC. *fixed product* — always UNEXERCISED here.

---

## 3. Repository grounding (STATIC at 1d813bd; re-verified by independent derivation)

| Fact | Anchor | Kind |
|---|---|---|
| External-content FTS5 table over `knowledge_entries` (`content`, `summary`, `tags`; `content_rowid='rowid'`); `entry_id TEXT PRIMARY KEY` ⇒ the FTS key is the implicit rowid, and the table has an automatic unique index plus six explicit indexes. | `core/memory/backends/sqlite_storage.py:59-93` | STATIC |
| `ke_ai` plain insert; `ke_au` = `'delete'` command + insert (Session 4C); **`ke_ad` = `DELETE FROM knowledge_entries_fts WHERE rowid=old.rowid`**. | `:95-109` | STATIC |
| Existing migration pattern: detect on trigger body (`"'delete'" not in trigger_sql`), `DROP`/`CREATE` through `executescript`, no rebuild, no marker, no `user_version`. | `:125-148` | STATIC |
| Schema and migration run in the **constructor** (`_init_sync`), once per backend instance, through `executescript` (which commits first). Every process that opens the backend runs it. | `:42-46, :56-148` | STATIC |
| Per-call connections (`_connect`): WAL, `synchronous=NORMAL`, `timeout=20.0`; legacy transaction control (`isolation_level=''`). | `:48-54` | STATIC + OBSERVED (T-probe reads the live connection) |
| `search_text` joins FTS to content on `rowid`; `delete()` is a plain `DELETE FROM knowledge_entries`. | `:253-294`, `:243-251` | STATIC |
| `ke_ad` body is identical in **all five commits** that touch the file under `git log --full-history` — `81d3069`, `42818a7`, `984e640`, `6b8b0af` (a merge; 348/348 changed lines against its first parent = whole-file line-ending conversion, identical to its second parent) and `da99c12` — and at the baseline. Plain `git log -- <path>` shows only three of them (`da99c12`, `42818a7`, `81d3069`); revision 1's four omitted the merge. The file is CRLF throughout (372/372 lines). | `git log --full-history`; per-version extraction | STATIC (this file only; databases created outside this history are UNKNOWN) |
| No use of `rebuild`/`optimize`/`user_version` on the FTS table under `core/`; no `secure_delete` in any `*.py`. | grep at 1d813bd | STATIC (negative result = evidence, not proof) |
| Existing migration test covers `ke_au` only; it does not check index contents. | `tests/test_session4c_architecture.py:515-578` | STATIC |
| Docs conflicts (maintainer-owned): `docs/reports/SESSION4C_REPORT.md:142` ("tested and confirmed not affected … left untouched") is contradicted by §4; `docs/reports/context-compiler-remediation-register.md:75` (REM-012 "Confirmed live") vs `docs/reports/ARCHITECTURE_HARDENING_SESSION_REPORT.md:170` ("dead code"). | file:line | STATIC |
| **New:** `KNOWN_ISSUES.md` on `main` (tip `f13bfde`) registers **DEBT-042**: `SqliteStorage._fts_escape()` (same file, `:363-372`) leaves most FTS5 query-syntax characters unescaped. A different FTS defect (query syntax), same file and same table as this batch. | `KNOWN_ISSUES.md` @ f13bfde | STATIC (tip only; not at the baseline) |

### 3.1 Documentation and source provenance (for ratification)
| Claim used | Verified how | Status |
|---|---|---|
| Python 3.12 `executescript()` implicitly commits a pending transaction "regardless of the value of `isolation_level`"; DDL no longer commits implicitly (3.6); `autocommit=LEGACY_TRANSACTION_CONTROL` is the default | **raw source** `Doc/library/sqlite3.rst` at CPython tag `v3.12.3` (lines 1542-1550, 2603-2701; file sha256 `f5be7234…e3183b7`); the `executescript` entries and the 'Transaction control' section are byte-identical at the `3.12` branch tip (`bb130d8…`, 2026-10-20) | verified at source (the rendered live page was not read) |
| FTS5 `#the_integrity_check_command` (§6.6 in the 3.45.1 docs): for an external-content table the index is compared with the content table "only if the value specified for the rank column is 1" | (a) **raw HTML of the 3.45.1 docs** (passage present; also agrees with two earlier fetch-tool quotations); (b) **SQLite 3.45.1 source**: `ext/fts5/fts5_storage.c:964-966` (`bUseCksum = … eContent==FTS5_CONTENT_EXTERNAL && iArg`), `fts5_main.c:1579-1581` (`rank` value → `iArg`), and `fts5_main.c:2978` (the `PRAGMA integrity_check` hook passes `0`) | wording verified at the raw 3.45.1 docs; behaviour verified at source and at runtime |
| FTS5 `#the_delete_command` (§6.3) `'delete'` with non-matching values: "the results may be unpredictable … some full-text index entries may not be correctly deleted, or FTS5 may try to remove index entries that do not exist" | **raw HTML of the 3.45.1 docs** (passage present, complete); consistent with the two fetch-tool quotations | wording verified at the raw 3.45.1 docs |
| FTS5 `#the_rebuild_command` (§6.11); `#the_secure_delete_configuration_option` (§6.12: default 0; first available in 3.42.0; without it old index entries "remain in the database file until they are eventually removed by merge operations"; core `PRAGMA secure_delete = 1` is also needed against file-level recovery); `#external_content_tables` (§4.4.3: the `AFTER DELETE` trigger example uses `'delete'` with the old values) | **raw HTML of the 3.45.1 docs** | wording verified at the raw 3.45.1 docs |
| VACUUM "may change the ROWIDs of entries in any tables that do not have an explicit INTEGER PRIMARY KEY" | **raw HTML** of `lang_vacuum.html` in the 3.45.1 docs (§3 `#how_vacuum_works`; the page is silent about `VACUUM INTO` and rowids) + upstream `test/e_vacuum.test` (`EVIDENCE-OF: R-17495-17419`, text returned by a tool) + `src/insert.c` @ 3.45.1 | wording verified at the raw 3.45.1 docs; mechanism at source |

**Chain of custody for the SQLite wording:** signed Ubuntu archive index (`InRelease`, `gpgv` good) → `Packages.gz` hash → `sqlite3-doc_3.45.1-1ubuntu2.8_all.deb` sha256 `9a97bea1…f699` → raw `fts5.html` / `lang_vacuum.html` (`docs/raw_sqlite_docs_verification.md`; verbatim sections in `docs/raw_html_excerpts_sqlite3-doc_3.45.1-1ubuntu2.8.txt`; 11/11 expected passages present). **Section numbers are those of the 3.45.1 docs;** the fetch tool had reported other numbers for the live page (§6.7, §6.12, §6.13 for integrity-check, rebuild, secure-delete), so this packet cites heading ids. **Not done:** the live `sqlite.org` pages were not read raw (the shell gets 403), no SQLite version other than 3.45.1 was checked, and the rendered live Python page was not read; the wording must be re-read for each version that D-2 declares.

---

## 4. What the evidence shows

### 4.1 Earlier evidence retained
LD 4/4 PASS on every variant. RC on the shipped schema: 4 PASS / 5 FAIL (RC-04, 05, 07, 08, 09). PE fails **5/5** on the shipped schema; on V1 PE-01..04 still fail and only PE-05 passes (residue beyond the trigger fix; PE-04, the overwrite via the already-fixed `ke_au`, leaves residue as well). Diagnostic variants V1 (new delete command after) and V2 (before) pass all nine RC tests; V3 (FTS5 secure-delete on) passes PE but fails RC-09 (the anomaly). **Re-run in this audit from the preserved script in a fresh disposable directory: the PASS/FAIL matrix and the RC-07 counters are identical to the two preserved runs.** Purpose: V1/V2/V3 are *test-satisfiability* diagnostics, not negative controls and not the fixed product.

### 4.2 Provenance of the legacy states (new; resolves C-1)
| Fixture | How the initial state was produced | Kind of the initial state | Run through the unchanged historical implementation |
|---|---|---|---|
| F1 ghost postings for rowids that no longer exist | prepared with raw SQL on the shipped schema | SYNTHETIC-PRECONDITION | reopen with the real constructor; API workload W |
| F2 / F3 ghost at a reused rowid (disjoint / overlapping token) | prepared with raw SQL | SYNTHETIC-PRECONDITION | same |
| F4 pre-4C database | historical raw-UPDATE `ke_au`, then opened by the real product | partly product behaviour: the 4C `ke_au` migration is the real constructor | same |
| F5a/b/c random 150-operation histories (seeds 20261013, 7, 99) | raw-SQL operations on the shipped schema | SYNTHETIC-PRECONDITION | same |

Observed with the **unchanged** implementation (`out/fts_baseline_product_path_run1.json`, `out/fts_baseline_fresh_api_history_run1.json`):
- **Reopening** each of the 7 prepared fixtures with the real constructor repairs nothing (fingerprint unchanged, 7/7). The **API workload** W (13/15/15/9/13/9/45 = 119 operations through `write`/`update`/`delete`) throws 0 exceptions and ends in exactly the state raw SQL produced (raw ghost rowids 13/8/9/2/53/94/181, `rank=1` failing; 7/7).
- **No preparation at all:** a brand-new database created by the real constructor, then 150 random operations through `write` (insert and upsert), `update` and `delete` only. Seeds 20261013 / 7 / 99: first discrepancy at the first delete (operations 3, 14, 2); 148 / 137 / 149 of 150 operations leave a discrepancy; 0 exceptions; end state 113 / 93 / 68 raw ghost rowids, 10 / 20 / 12 live rows, `plain integrity-check` ok, `rank=1` failing (malformed). The false-positive totals (387 / 620 / 893) sum per-operation measurements and are *not* counts of distinct entries.
- **Attribution control** (probe variant on a throw-away database; not product, not a fix): the same three histories with the canonical `ke_ad` installed on the empty database before the first operation — 0 discrepancies, 0 ghost rowids, `rank=1` ok, 3/3.

So: the shipped product itself creates the defective state (HISTORICAL BASELINE — OBSERVED). What remains synthetic is *only* that real legacy databases in the field were not examined (UNKNOWN).

### 4.3 Legacy fixtures × procedures (revision 1 §3.2, numbers re-derived and unchanged)
Procedures were applied to a byte copy of each of the 7 prepared fixtures. Workload W: update and delete every live row, then insert/upsert/delete rows reusing the fixture's tokens; measured after every operation against an index-independent reference.

| Procedure | Role (purpose / label) | `rank=1` clean right after (of 7) | Fixtures with any discrepancy during W | `rank=1` clean after W | Raw ghost postings after W (F1…F5c) | Exceptions | FN |
|---|---|---|---|---|---|---|---|
| N none | HISTORICAL BASELINE (initial state) | 0 | 7 | 0 | 13/8/9/2/53/94/181 | 0 | 0 |
| T trigger swap only | NEGATIVE CONTROL | 0 | 7 | 0 | 2/1/1/0/34/92/92 | 0 | 0 |
| R rebuild only | NEGATIVE CONTROL | 7 | 7 | 0 | 11/7/8/2/19/2/89 | 0 | 0 |
| TR, A (one transaction), RT | n/a — probe artefact (feasibility of the PROPOSED protocol) | 7 | **0** | **7** | 0 in all | 0 | 0 |

A `rebuild` after W returned every cell to a clean state. Readings (each limited to what was observed): both operations are needed; order TR/A/RT made no observable difference; a `'delete'` issued while the index was inconsistent (doc §6.3) raised no exception in 119 T operations on 3.45.1 but left ghost postings that a later rebuild cleared — **UNTESTED** on other versions and states; the second protocol run was a no-op with an identical fingerprint (7/7); F4 reproduces the historical raw-UPDATE `ke_au` (summary update raised `database disk image is malformed`).

### 4.4 Atomicity and ambiguous commit outcome (new; resolves C-2)
Protocol under test (probe artefact `migrate_with_marker`, `scripts/b4lib.py`): `BEGIN IMMEDIATE` → classify **inside** the lock → act → `rebuild` → `rank=1` verification → write marker → `COMMIT`, explicit statements only, on connections configured like the product's. Fault points: **F0** after BEGIN+detect · **F1** after trigger swap · **F2** after rebuild · **F3** before commit · **F4** after commit. No rollback is attempted after a successful commit.

| Part | What was done | Result |
|---|---|---|
| A. exact seam (seed: legacy `ke_ad`, 34 ghost rowids, 21 false positives, `rank=1` failing) | each point × exception × hard process exit (`os._exit(9)`), then retry, then a third run | F0–F3: connection not in a transaction, state **exactly pre**, `PRAGMA integrity_check` ok, retry clean, third run no-op — 8/8. **F4 (post-commit): state exactly post, retry = no-op, third run no-op — 2/2.** |
| B. torn commit, **SIMULATED** (WAL of a committed run: 444,992 bytes = 32-byte header + 108 frames of 4,120 bytes; commit frame = the last one, index 107) | 40 variants: truncation at frame boundaries and inside frames/headers, plus the intact WAL; main file byte-identical to its pre-run copy (WAL below the 1000-frame auto-checkpoint) | 39 truncated variants → **pre**; the intact WAL → **post**; 0 mixed; integrity ok; retries converge. A truncation test shows what SQLite recovers from a WAL, not what a disk loses on power failure (see §11). |
| C. SIGKILL stress (20,004-row seed; protocol lasts ≈0.13 s) | 100 uniformly timed + 150 "targeted around the commit" kills, each followed by classification, retry, third run | 250 trials: **pre 237, post 13, mixed 0**; all integrity checks ok; all retries clean; all third runs no-op. |

**Honest limits of Part C.** Only **2 of 250** kills (both from the uniform series) happened while `COMMIT` was in flight: one ended **pre**, one **post**. **None of the 150 "targeted" kills landed in the window** (all ended at F1/F2); why the targeting missed was not investigated. The commit window is ≈2–3 ms wide; the deterministic F4 cases and Part B, not Part C, carry the post-commit and torn-commit claims. The series was resumed twice after container restarts (progress file with a fingerprint check; the first interrupted attempt produced no output and is disclosed, not discarded silently).

**How an ambiguous outcome is bounded (PROPOSED requirement).** The caller that issued `COMMIT` and then died, lost its connection, or received an exception **cannot know** whether the transaction committed. The protocol never asks: the next start (any process) opens a **fresh** connection, takes `BEGIN IMMEDIATE`, classifies the state, and either performs the migration (state pre) or does nothing (state post), then proves the result with `rank=1`. In every observation the classified state was a complete pre or post state, never a mixture. Consequently: no rollback is required, or relied upon, after a successful commit; a failure *before* a successful commit leaves exactly the pre-state; the retry converges; a further run is a no-op.

### 4.5 State dispositions (new; resolves C-3)
`scripts/b4lib.py: trigger_state / marker_state / disposition`; results `out/fts_state_classifier_run1.json`. Trigger text is compared after whitespace normalisation to **exactly** the legacy form or the canonical form; **a trigger-body substring is never evidence of completion.** Two marker backends were probed: a table `ocbrain_schema_migrations(migration_id, version, trigger_sha256, verified_rank1 CHECK=1, recorded_at)` and `PRAGMA user_version`.

| Your five states | Probe states | Trigger / marker | Index | Disposition (probe artefact) | Observed |
|---|---|---|---|---|---|
| 1. legacy trigger, no accepted record | S1 | legacy / absent | ghosted | swap + rebuild + verify + record | clean, second run no-op (both backends) |
| 2. canonical trigger, accepted record | S2 | canonical / accepted | clean | no-op | unchanged |
| 3. canonical trigger, missing or untrusted record | S3a (index clean) · **S3b (index ghosted — the stranded state)** · S3c (record present but untrusted: wrong digest/unverified) | canonical / absent or untrusted | clean · **ghosted (48 raw ghost rowids, 7 false positives)** · ghosted (1) | complete: rebuild + verify + record | all end clean; S3b is repaired only because the marker's absence forces the rebuild |
| 4. missing/unrecognised trigger, or malformed metadata | S4a trigger absent · S4b trigger unrecognised · S4c marker malformed · S4d marker newer than the code | — | ghosted / clean | S4a: recreate + rebuild + verify + record · **S4b, S4c, S4d: REFUSE (fail closed), state untouched** | as stated; refusal repeats on every start |
| 5. trigger/index disagreement | S3b (above) · **S5: canonical trigger, accepted marker, index drifted (1 ghost rowid)** | canonical / accepted | drifted | classifier says **no-op** — the marker cannot see drift; an explicit `rank=1` verification **detected** it and a rebuild **repaired** it | drift detected and repaired |

Costs (this machine): classification 27 µs; `rank=1` verification 0.048 s at 10k rows, 0.243 s at 50k rows (one run; two later re-executions of the same probe on this machine gave 0.061 s / 0.030 s at 10k rows and 0.267 s / 0.155 s at 50k rows — treat these as order-of-magnitude, not as a budget). Whether "refuse" (S4b/c/d) is the right policy is a maintainer decision (D-10); the probe's choice is an artefact.

### 4.6 Transaction boundary on the product's connection (new; resolves C-4)
`out/fts_txn_boundary_run1.json` (Python 3.12.3). The product connection, obtained by calling `SQLiteStorageBackend._connect()` unchanged: `isolation_level=''`, `autocommit=LEGACY_TRANSACTION_CONTROL`, WAL, `synchronous=NORMAL`, busy timeout 20,000 ms, `foreign_keys=1`.

| # | Observation | Consequence |
|---|---|---|
| T1 | Explicit `BEGIN IMMEDIATE` + DDL statements stay in one transaction; `ROLLBACK` undoes them | the swap can be transactional |
| **T2** | **`executescript()` after `BEGIN IMMEDIATE` commits the pending transaction first**; a later `rollback()` did not undo the `DROP`/`CREATE` | `executescript` must not be used inside a migration transaction |
| T2b | a failure inside `executescript` after the `DROP` left the trigger **absent** | the existing pattern is not atomic |
| T3 | DDL without `BEGIN` autocommits (visible to other connections at once); `INSERT … 'rebuild'` without `BEGIN` opens an implicit transaction that must be committed | explicit `BEGIN` is needed for DDL and for rebuild |
| T4 | `rebuild` inside an explicit transaction works | one transaction can hold swap, rebuild, verify |
| T5 | closing a connection with an open transaction rolls it back | exception-safe |
| T6 | `PRAGMA user_version` is transactional (inside 1, rollback 0, commit 1) | usable as a same-transaction marker |
| T7 | with `autocommit=False` `executescript` did not commit — but the product does not use that mode and changing it is a design change | not a recommendation |
| **T8** | a deferred transaction that read, then tried to write after another connection committed, failed at once with `database is locked` (0.0 s, **not** after the timeout) | start the write transaction with `BEGIN IMMEDIATE`, never upgrade a read |
| T9 | **new-database initialisation**: the 11 product DDL statements extracted from the source, with only the `ke_ad` block replaced and the marker added, create a database that differs from a product-created one only by `ke_ad` and the marker table; the **historical** constructor opened on it changes nothing; the historical API workload on it is clean (17 operations, 0 discrepancies) | new-DB init and existing-DB migration are different paths; rolling compatibility with unchanged code is observed |
| T10 | `migrate_with_marker` run on `_connect()`: success → post; faults at F0, F2, F3 → pre; F4 → post; retry converges; third run no-op | feasible on the product connection |

This is a probe on the product's connection class. It is **not** evidence about the constructor path: `_init_sync` runs through `executescript`, once per backend instance, in every process; no product code was changed here. **UNVERIFIED for the product path (G-4).**

### 4.7 Concurrency (new; resolves C-5)
`out/fts_concurrency_run1.json`; the protocol of §4.4 on the product's connection settings; 20 s busy timeout.

| Case | Setup | Observed |
|---|---|---|
| C1 | N = 2, 4, 6 processes released together, 5 trials each | exactly one process performed the migration in **15/15** trials; 0 errors; final state clean; slowest process ≤ 0.34 s |
| C2a | holder keeps the write lock ≈ 3 s | contender waited 3.14 s, then no-op, no error |
| **C2b** | holder keeps it 25 s | contender failed with `OperationalError: database is locked` after **20.05 s**; the holder's commit was clean; a later retry = no-op |
| C3 | holder SIGKILLed while a contender waits | contender saw the exact pre-state, performed the migration, final state clean |
| C4 | a reader holds an **older WAL snapshot** | reader sees the pre-state until its transaction ends; `wal_checkpoint(PASSIVE)` while it is open: busy 0, 590 frames, 0 checkpointed (blocked); the reader's write attempt fails at once (0.0001 s) with `database is locked`; a new transaction sees the post-state; after the reader ends the checkpoint completes 601/601 |
| C5 | writer traffic starting at 0 / 0.2 / 0.5 / 1.0 s after the migrator, 2 trials each | 8/8 error-free; final state clean; row counts match; a writer ran inside the migration window in 3 trials; slowest writer operation 0.18 s |
| C6 | lock hold (BEGIN IMMEDIATE → COMMIT, including rebuild, `rank=1` verification, marker), 3 repetitions | 5k rows 0.045–0.070 s (WAL 0.68 MB); 20k rows 0.174–0.232 s (2.43 MB); 50k rows 0.491–0.565 s (7.2 MB). **EXTRAPOLATED**, not measured: 20 s would be reached near 1.9 million rows on this machine; hardware, schema and content change that |

Two-process/five-trial results of revision 1 remain feasibility evidence; these extend, not replace, them. UNTESTED: process crash of a *contender*; the four-process runtime end to end; mixed old-code and new-code processes operating at the same time; power loss.

### 4.8 VACUUM and rowids (corrected; resolves C-8)
Documentation: VACUUM "may change the ROWIDs" of tables without an explicit INTEGER PRIMARY KEY. Revision 1 observed 0 changes in 4 cells and concluded "only observed". **New controls** (`out/fts_vacuum_rowid_control_run1.json`):

| Table | Result after `VACUUM` (rowids 1,4 before) |
|---|---|
| `t(x)` — no index | **renumbered** (1,4 → 1,2) |
| `t(x TEXT PRIMARY KEY)` — automatic index | preserved |
| `t(k INTEGER PRIMARY KEY, x)` | preserved |
| `t(x)` + `CREATE INDEX` | preserved |
| the product's `knowledge_entries` (real constructor, canonical `ke_ad`), gaps made by deletes | preserved; `rank=1` ok before and after |
| external-content FTS5 over an index-less table | **rowids renumbered; `rank=1` fails (malformed); retrieval wrong** |
| `VACUUM INTO`, no-index and indexed | preserved in both on 3.45.1 |

Mechanism, from SQLite 3.45.1 `src/insert.c` (`xferOptimization`, used by VACUUM): lines 3050-3063 — an `INTEGER PRIMARY KEY` copies the rowid (`OP_Rowid`); otherwise `else if( pDest->pIndex==0 && !(db->mDbFlags & DBFLAG_VacuumInto) )` renumbers (`OP_NewRowid`); otherwise it preserves (`OP_Rowid`). The product's rowids survived because `entry_id TEXT PRIMARY KEY` creates an index. **That is an implementation detail, not a documented guarantee, and removing every index would break the FTS key under VACUUM.** Any physical-erasure plan that uses VACUUM must keep its own index-agreement check.

### 4.9 Durations (corrected; resolves C-7)
| Quantity (50,000 rows) | Value | Source |
|---|---|---|
| swap + rebuild + verify, two original runs | **0.410 s and 0.501 s** (quoted range corrected from "0.41 s") | `fts_migration_protocol_run{1,2}.json` |
| same, one reproduction run here | 0.425 s | `repro_out` |
| write-lock hold incl. marker (C6) | 0.491–0.565 s | `fts_concurrency_run1.json` |
| 1k / 10k rows (original runs) | 0.008–0.009 s / 0.07–0.08 s (re-derived: inside the quoted ranges) | same |

Real database sizes are UNKNOWN; all timings are container-specific.

---

## 5. Proposed protocol and what it must and must not claim

### 5.1 Three operations (PROPOSED, unchanged)
1. **Correct the trigger** — `ke_ad` uses the documented external-content pattern (`'delete'` with the old values; FTS5 docs `#external_content_tables`, `AFTER DELETE` trigger example). Prevents future divergence only.
2. **Rebuild the existing index** — `INSERT INTO knowledge_entries_fts(knowledge_entries_fts) VALUES('rebuild')` (FTS5 docs `#the_rebuild_command`). Removes legacy ghosts from both historical sources (shipped `ke_ad`; pre-4C `ke_au`).
3. **Verify** — `INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rank) VALUES('integrity-check', 1)` plus an index-independent reference (§6).

### 5.2 Atomicity and ambiguous commit (PROPOSED requirement)
Swap, rebuild, verification and any marker are **one write transaction**, started with `BEGIN IMMEDIATE`, with the migration decision taken **inside** the lock; no content mutation between swap and rebuild. **R2-a** a failure before a successful commit leaves the exact pre-state (trigger text, content rows, FTS shadow tables). **R2-b** if the commit outcome is ambiguous (process death, lost connection, exception from `COMMIT`), the next start observes a verified complete pre- or post-state, never a mixture. **R2-c** a retry converges; a further run is a no-op. **R2-d** no rollback is required, or issued, after a successful commit. **R2-e** the four pre-commit checkpoints (F0–F3) are tested by exception *and* hard process exit, plus a post-commit termination case (F4).

### 5.3 State dispositions — two alternatives, **the choice is the maintainer's (D-4)**
Never treat a trigger-body substring as proof of completion. The same acceptance tests apply to both.

| | Alternative 1 — prove atomicity on every path, no marker | Alternative 2 — a versioned marker recorded in the same transaction **after** verification |
|---|---|---|
| Claim | the canonical trigger exists only together with a verified index, because no path can commit one without the other | the marker is the record that the verified migration committed |
| What it needs | proof on **every** path: the constructor, every historical starting state, crash and kill, and any other code that could ever swap the trigger separately (the 4C `ke_au` migration style does) | marker creation in the same transaction as the verified state; a version number; defined behaviour for missing, corrupt, untrusted and newer markers; new-DB initialisation that writes the marker in the same DDL transaction |
| Observed | S3b (stranded) is invisible to a body-keyed check; with this alternative it can only be handled by running the `rank=1` check at every start (0.24 s at 50k rows) | S3b repaired because the marker is absent; **S5 (drift after the marker) is invisible to the marker** |
| Marker mechanisms probed | — | table (structured: version, trigger digest, verified flag, time; one extra schema object, ignored by unchanged code, T9) or `PRAGMA user_version` (transactional, T6; one integer; no existing use under `core/`, STATIC) |
| Common limit | **A marker does not replace atomicity**, and neither alternative replaces an explicit `rank=1` verification inside the migrating transaction | |

Missing/unrecognised trigger or malformed/newer metadata: the probe fails closed (D-10 asks whether that is the intended policy).

### 5.4 Transaction mechanics (PROPOSED requirement)
**R4-a** `executescript()` is never called after `BEGIN` (T2). **R4-b** the migration is explicit, ordered statements on the product's own connection (`_connect()` settings). **R4-c** `BEGIN IMMEDIATE`, never a deferred read-then-write (T8). **R4-d** new-database initialisation and existing-database migration are two paths, tested separately, and must produce the same final schema (T9). **R4-e** a standalone SQL probe is **not** evidence that the constructor path works; only a test through the real constructor on the intended code is.

### 5.5 Concurrency contract (PROPOSED requirement)
**R5-a** detection happens inside the write lock; detect-before-lock duplicates the rebuild (revision 1, 5/5). **R5-b** a process that cannot get the lock within the 20 s busy timeout receives `database is locked`; that error means *"not migrated by me"* and must never be read as *"already migrated"*; what startup then does (retry, wait, fail the process) is D-9. **R5-c** the migrating connection is fresh; a connection holding an older snapshot cannot become the writer and fails at once, bypassing the timeout (C4, T8). **R5-d** readers on older snapshots see the pre-state until they finish and delay checkpointing, not the commit. **R5-e** after any fault, restart re-classifies under the lock. **R5-f** the contract is tested with ≥2 and ≥4 processes, a killed holder, a holder longer than the timeout, an older-snapshot reader and concurrent writers.

### 5.6 Not proposed here
Enabling FTS5 `secure-delete`; any VACUUM-based erasure; any change to `ke_au`/`ke_ai`; any change to the rejection log; any change to `_fts_escape()` (DEBT-042).

---

## 6. Verification model — three measurements, kept apart

| # | Measurement | Command | What it shows |
|---|---|---|---|
| 1 | Internal FTS index integrity | `INSERT INTO fts(fts) VALUES('integrity-check')` and `PRAGMA integrity_check` | Does **not** compare an external-content index with the content table. Source: `fts5_storage.c:964-966` (comparison only when the rank value is non-zero) and `fts5_main.c:2978` (the `PRAGMA` hook passes 0). |
| 2 | Index vs authoritative content | `INSERT INTO fts(fts, rank) VALUES('integrity-check', 1)` **plus** an index-independent retrieval reference and a raw `MATCH` check for row ids absent from the content table | Detects ghosts. `rank=1` alone is not the acceptance criterion; the independent reference is also required. |
| 3 | The unexplained secure-delete anomaly | §6.1 | Characterised, not explained. |

Observed on the shipped schema (`out/*integrity_semantics*`): plain ok and `rank=1` malformed after a middle-row delete (1 ghost rowid); max-row delete + insert at the reused rowid → plain ok, `rank=1` malformed, 1 false positive; after `rebuild` ok/ok; same operations with the V1 trigger ok/ok. **A plain-only check cannot be an acceptance criterion.** Run-to-run: the preserved integrity runs are identical, and a fresh reproduction here is identical.

### 6.1 The secure-delete anomaly — characterised, not explained (unchanged, re-derived)
8 cells = core `PRAGMA secure_delete` {0,1} × FTS5 `secure-delete` option {off,on} × `ke_ad` {shipped, V1}, 7-step workload. With the option off no `'delete'` command trips the check; with it on both forms report malformed from the first `'delete'` command until `rebuild`; retrieval stayed correct (0 false positives/negatives in 56 step-cells); the core pragma made no difference. The product does not enable the option. No explanation is offered; the anomaly is **excluded** from this batch's acceptance criteria. Separately, the FTS5 documentation itself states (`#the_secure_delete_configuration_option`, raw 3.45.1 docs) that without the option old full-text entries stay in the database file until merges remove them and can be used to reconstruct deleted rows, and that file-level recovery also needs the core `PRAGMA secure_delete = 1`; this is why physical erasure stays a separate requirement (RD-10, ledger D-5) and why this batch does not enable the option.

---

## 7. Acceptance matrix (PROPOSED; packet-local IDs FTS-A1…A7, **not** spec RM IDs and **not** G4 isolation closure)

Columns follow §2. The last column is *not* a label.

| ID | Requirement (all PROPOSED) | HISTORICAL BASELINE @1d813bd | NEGATIVE CONTROL | FIXED PRODUCT | Supporting probe evidence (no product-state label) |
|---|---|---|---|---|---|
| FTS-A1 | After delete/update the index agrees with content: RC-04, 05, 07, 08, 09 pass; RC-01..03, 06 and LD-01..04 keep passing; `rank=1` mandatory in RC-09 | OBSERVED: RC 5 FAIL / 4 PASS; LD 4/4 PASS (matrix re-run identical) | OBSERVED: T and R fail workload checks (7/7) | **UNEXERCISED** | test-satisfiability: V1, V2 pass all RC; V3 fails RC-09 |
| FTS-A2 | A legacy database is repaired by migration: `rank=1` ok, 0 ghosts, 0 false positives, **0 false negatives** | OBSERVED: fresh-constructor + API histories reach the ghost state (3/3); the unchanged constructor repairs none of 7 prepared fixtures; API workload = raw-SQL result (7/7). STATIC: no migration exists. Initial states of F1–F5c are SYNTHETIC-PRECONDITION | OBSERVED: T and R leave or re-create the state | **UNEXERCISED** | TR/A/RT: 7/7 clean on prepared fixtures |
| FTS-A3 | Migration is atomic **and** its commit outcome is recoverable: failure before commit → exact pre-state; ambiguous commit → verified pre or post; retry converges; a further run is a no-op; no rollback after commit | not applicable (no such migration). STATIC: the existing migration style is `executescript`, non-atomic | OBSERVED: non-atomic variant strands new-trigger/old-index (48 ghost rowids) and body-keyed detection reports "migrated" | **UNEXERCISED** | F0–F3 exception and hard exit → pre (8/8); F4 → post (2/2); 250 SIGKILLs + 40 torn-WAL variants: 0 mixed |
| FTS-A4 | Migration is idempotent and race-safe under the concurrency contract §5.5 | not applicable | OBSERVED: detect-before-lock lets both of two processes migrate (5/5) | **UNEXERCISED** | exactly one migrator 15/15 (2, 4, 6 processes); 20 s timeout, killed holder, older-snapshot reader, writer traffic observed |
| FTS-A5 | Post-migration update/delete of legacy rows stays correct (workload W equivalent) | OBSERVED: shipped schema fails W 7/7 and fresh histories 3/3 | OBSERVED: T fails 7/7 | **UNEXERCISED** | A/TR/RT 0 discrepancies; canonical trigger on fresh histories 3/3 clean |
| FTS-A6 | Version matrix recorded and passing for the declared minimum and other supported runtimes (§8) | **UNTESTED** except 3.45.1 | — | **UNEXERCISED** | — |
| FTS-A7 | Repo, migration, tests and documentation agree (incl. `SESSION4C_REPORT.md:142`, REM-012) | STATIC: they disagree | — | **UNEXERCISED** | — |

**An FTS fix merged alone does not close any G4 isolation requirement (INV-01…22 are unchanged by this batch).** FTS-A1…A7 concern retrieval correctness of one index, not identity or authorization.

---

## 8. SQLite compatibility matrix — minimum supported version left OPEN

3.45.1 is one tested runtime, **not** a support policy.

| Dimension | Required treatment | Observed here |
|---|---|---|
| Runtime identity | Record `sqlite3.sqlite_version` as loaded by the **Python application** (and `sqlite_source_id()`), not the CLI version | 3.45.1; source id `2024-01-30 16:01:20 e876e51a…`; Python 3.12.3 system interpreter |
| FTS5 | Verify FTS5 is compiled in per runtime | yes (`ENABLE_FTS5`) |
| Core `PRAGMA secure_delete` | Record the build default **and** the value in effect | build default **1** on a new connection (compile option `SECURE_DELETE`); the product does not set it |
| FTS5 secure-delete option | Record support (3.42.0, default 0) and whether enabled | supported; not enabled by the product |
| Compatibility | Test the declared minimum and other relevant runtimes, on existing fixtures | **UNTESTED** — one runtime |
| Python `sqlite3` transaction semantics | Record interpreter version and transaction-control mode | 3.12.3, legacy mode; semantics differ by Python version (docs, §3.1) |

Per the docs, a table that used the FTS5 `secure-delete` option cannot be read by FTS5 older than 3.42.0 until rebuilt; that is a compatibility constraint, not a reason to mandate secure-delete here.

---

## 9. Required tests (PROPOSED specification)

1. **RC regression set:** RC-04, 05, 07, 08, 09 pass; RC-01..03, 06, LD-01..04 retained; `rank=1` mandatory in RC-09.
2. **Legacy fixtures (generated, disposable):** F1–F5c plus databases built from the historical schema of `81d3069`/`42818a7`; **and** histories produced only through the product API on a fresh database (§4.2). Maintainer-supplied real databases are optional and owner-controlled; none was examined.
3. **Migration correctness:** after migration `rank=1` ok, 0 raw ghost row ids, 0 false positives, 0 false negatives, workload W equivalent clean.
4. **Fault injection:** F0–F3 by exception **and** hard exit; **F4 post-commit termination by exception and hard exit**; exact pre-state (trigger SQL, content rows, FTS shadow tables) or verified post-state; retry converges; a further run is a no-op; **ambiguous-commit** cases: SIGKILL series and torn-WAL simulation, outcome always complete pre or post.
5. **State dispositions:** every row of §4.5 for the chosen alternative, including S3b, S5 and the refusal states.
6. **Transaction mechanics:** a test that fails if `executescript()` is used between `BEGIN` and `COMMIT` in the migration; a test through the **real constructor** (new DB and existing DB separately); the same final schema from both paths.
7. **Concurrency:** §5.5 cases at the declared database sizes (≥2 and ≥4 processes; holder longer than the 20 s timeout; killed holder; older-snapshot reader; concurrent writers).
8. **Idempotency:** second run no-op; repeated rebuild logically identical (physical identity observed, not required).
9. **Delete-before-rebuild** on a disposable legacy fixture, only to characterise the FTS5 docs' `#the_delete_command` warning per supported SQLite version; the production migration must not need it.
10. **Version matrix** per §8.
11. **Negative controls** for FTS-A1/A2/A3/A4: trigger-only, rebuild-only, non-atomic, detect-before-lock.
12. **Index/content agreement after VACUUM** if any physical-erasure plan uses it (§4.8), including an index-less variant to show the check is sensitive.

---

## 10. Implementation gates (all OPEN)

| Gate | Question | Why |
|---|---|---|
| G-1 | RD-13 / spec §12 I-4: pull the batch forward, keep it at I-4, or defer? | Decision B. |
| G-2 | Minimum supported SQLite version(s) and how the product obtains its SQLite | §8; every observation is one build. |
| G-3 | Migration-state mechanism (§5.3): atomicity-only, or a versioned marker (table / `user_version`); policy for unrecognised, malformed, newer metadata | S3b, S5. |
| G-4 | Constructor integration: where the migration runs (constructor vs explicit startup step) given `_init_sync` uses `executescript` per process. **Partly grounded now**: explicit statements on `_connect()` work (T1–T10) and `executescript` after `BEGIN` does not (T2). The constructor path itself is **UNVERIFIED** (no product code changed). | §4.6. |
| G-5 | Real database sizes and startup budget | Lock hold 0.49–0.57 s at 50k rows here; extrapolated 20 s at ≈1.9 M rows; real sizes UNKNOWN. |
| G-6 | The DDL for **new** databases in `_init_sync` changes in step with the migration, else a new database is created with the old `ke_ad` and migrated at its first reopen | T9. |
| G-7 | Overlap in `sqlite_storage.py` and `unified_memory.py` with isolation work (spec lines 428-435, I-3a) **and** DEBT-042 (`_fts_escape`, `:363-372`) on `main`: owner and sequence not assigned | merge planning. |
| G-8 | Owner of the documentation corrections (`SESSION4C_REPORT.md:142`; REM-012 live vs dead) | FTS-A7. |
| **G-9** | Startup behaviour on busy-timeout exhaustion and in the four-process runtime (main, worker pool, webhook, task runner each construct the backend) | §5.5 / D-9. |
| **G-10** | Isolation-overlap owner/sequence (restates G-7 as a gate) | D-11. |

---

## 11. Evidence gaps and risks (UNKNOWN / UNTESTED — none converted into an assumption)

| Item | State |
|---|---|
| Other SQLite versions (below and above 3.42.0), other platforms, other Python versions | UNTESTED |
| Real databases (size, legacy states, whether ghosts exist) | UNKNOWN; none examined |
| Product-path integration of the atomic protocol (constructor, four-process runtime) | UNVERIFIED |
| Power loss / disk-level torn writes. WAL with `synchronous=NORMAL` is consistent after a process kill but a committed transaction may be lost after a power failure (SQLite WAL documentation, not re-tested here). Process kills and WAL truncation do not test the disk | UNTESTED |
| Window of a real kill *during* `COMMIT`: 2 samples | weakly sampled |
| Contender crash, mixed old/new code operating concurrently, four-process end-to-end | UNTESTED |
| The §6.3 ordering risk as a general guarantee | UNTESTED beyond 7 fixtures on one build |
| The secure-delete anomaly | UNKNOWN (characterised only) |
| Crash inside the existing `executescript` migration path of the shipped product | UNTESTED (only the PROPOSED protocol and a pattern probe, T2b, were exercised) |
| FTS5/VACUUM documentation wording | verified at the **raw 3.45.1 docs** (signature-verified package); live `sqlite.org` pages not read raw; other SQLite versions' wording UNTESTED (re-read per version declared in D-2) |
| Fixtures from databases created outside this repository's history | UNKNOWN |

A read-only check the maintainer **may** run on a **copy** of a real database, inside a rolled-back transaction, to learn whether legacy ghosts exist: `INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rank) VALUES('integrity-check', 1);` (an error means disagreement). Nothing here depends on that being run.

---

## 12. Maintainer decisions

None is made here. `decision_ledger_1d813bd_OPEN.md` lists D-1…D-11 with options, owner, status (all **OPEN**), what evidence supports which option, and what approval is still required. The rejection-log retention question is **not** part of this batch.

## 13. What this packet does not do

It does not change G4–G8 status or imply freeze readiness; does not choose D1/D2/D3; does not authorise implementation, a branch, a PR or a push; does not edit product code, tests, `ci.yml`, the allowlist, the ADR-KERNEL-07 D-4 xfail, the PROPOSED spec, the delivered response report (sha256 `1699456359e9ad4c3bb28a97e0ead8452d5808362ff90d555bfa29d1dec33b20`), revision 1, its addendum or any earlier bundle; presents no probe result as acceptance evidence for a fix; and does not treat FTS-A1…A7 as G4 isolation closure.

## 14. Reproduction, harness corrections and disclosures

See `README.md` (commands, environment, hashes) and `evidence_audit_report_1d813bd.md`. Disclosures: (1) revision 1's ordering-probe run 1 used a mixed-case vocabulary word and is preserved as run; (2) the first attempt of the commit-boundary probe was interrupted by a container restart and produced no output; the final series was resumed twice from a progress file, so its trials span several container boots; (3) the harness tree digest hashes a worktree's `.git` pointer file, so the same commit in two clean worktrees gives two digests (`624b0e3f…` original worktree, `46cacae3…` audit worktree); the 544 other files are byte-identical (digest excluding that file `bbb5f945…`); (4) the original check script `packet_numbers_check.py` re-runs 72/72, but it asserts only loose upper bounds for durations and hard-codes its other expectations — it demonstrates self-consistency, not independence, which is why the independent derivation (385/387; the two failures are the same duration finding in two result sets) was added; (5) the FTS5 / VACUUM wording was first obtained through a summarising fetch tool and was later verified against the raw HTML of the SQLite 3.45.1 docs (§3.1; `docs/raw_sqlite_docs_verification.md`); the fetch tool's section numbers for the live page differ from the 3.45.1 docs, which is why heading ids are cited; the live pages remain unread raw; (6) the transcription check of this packet's figures (`scripts/rev2_numbers_check.py`) failed 3 of 83 on its first run because of checker defects and passed 83/83 afterwards (details in the audit report §3); (7) limits: one SQLite build, interpreter and machine; throw-away databases only; probe artefacts, not product code.
