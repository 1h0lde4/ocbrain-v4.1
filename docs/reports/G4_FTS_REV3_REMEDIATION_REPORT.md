# OCBrain G4–FTS Remediation — Rev 3 Amendments (Implementation & Verification Report)

**Date:** November 5, 2026
**Scope:** Rev 3 Amendments 1–12 on top of Session 4C (Rev 2) — SQLite WAL runtime gate, migration lifecycle separation, integrity validation battery, content-row identity invariants, mutation atomicity, secure-delete disposition, multi-database inventory, FTS configuration audit, search regression, checkpoint policy, failure recovery, restricted acceptance gates.
**Status of the repository:** no git repository in this workspace; all changes are uncommitted file edits. See §12 for the complete touched-file list.

---

## 0. Executive verdict (Amendment 12 — restricted, honest)

**The Rev 3 remediation implementation itself is complete and all 105 new gate tests pass — but the deployment certification as a whole CAN and MUST NOT be stated as "IMPLEMENTATION COMPLETE — ALL GATES PASS", because the production SQLite runtime of this installation is AFFECTED by the FTS5/WAL defect class and is not certifiable under the Rev 3 contract.**

Verdict precisely:

| Claim | Status |
| --- | --- |
| Rev 3 code (gates, lifecycle, checks, tests) implemented | ✅ DONE — evidence §10 |
| All 7 Rev 3 gate suites pass on this machine | ✅ 105/105 |
| Baseline suites unaffected | ✅ 109/109 (same test count as pre-Rev 3) |
| **Production runtime certified under Amendment 1** | ❌ **REFUSED** — SQLite 3.50.4 (CPython 3.14.3 build) is inside the affected range (3.7.0 … 3.51.2; fixed 3.51.3; backports 3.44.6 / 3.50.7), with no vendor-build provenance registered |
| Release readiness claim | **Blocked on Plan R1 (§4)** — remediation performed, readiness NOT reported as full; the memory service reports `ready_degraded_runtime_not_supported` until the runtime is fixed |

What "affected runtime" means for users of this installation (measured, not assumed — see §9 RF-2):

1. after **any successful DELETE** on an external-content FTS5 table, the documented `INSERT INTO fts(fts, rank) VALUES('integrity-check', 1)` command returns *"database disk image is malformed"* even though `PRAGMA integrity_check` passes on the whole file; **and**
2. the freed docid **remains MATCH-findable on the raw FTS surface** (stale index entry) while the content row is gone — the public search surface stays correct only because `search_text()` filters via its `ke.rowid = fts.rowid` JOIN.

Both are consequences of the SQLite build, not of repository code (raw-SQLite probes, independent of this repo, are in Appendix A). The remediation contract (fail-closed migration gate, identity/integrity checks, ledger, restore-after-fault behavior) all behave correctly under fault injection **on the affected runtime too**; that is exactly why the certification refusal is not a code defect claim — it is a runtime deployment condition with a documented repair plan (§4).

---

## 1. Amendment 1 — WAL runtime compatibility gate (P0)

**Implemented.** `core/memory/sqlite_runtime.py` decides fail-closed from: (a) the affected range table (3.7.0–3.51.2; 3.51.3 fixed; documented backports 3.44.6 and 3.50.7), (b) documented-backport matching, (c) registered vendor-build provenance. A vendor build is only accepted with **complete** provenance (`source_id`, `distribution`, `evidence_url`, `verified_on`); partial/absent provenance fails closed.

- Runtime inventory (`sys.version`/`sqlite3.sqlite_version`/`sqlite_version()`/`sqlite_source_id()`/OS/machine/build provenance/`connection_model`/`automatic_checkpoint_config`) is collected and attached to readiness state.
- An affected runtime **never** reports full readiness: status is `ready_degraded_runtime_not_supported`.
- Escape hatch is **documented, test-environment-only**, and explicit: env `OCBRAIN_MEMORY_RUNTIME_ACK=acknowledge` lets construction proceed under acknowledgment while readiness stays not-full. Production default (and invalid values) fail closed to `enforce`.
- Provenance is configurable: `config/settings.toml` `[memory] wal_gate.approved_vendor_builds` (commented template shipped); `load_configured_vendor_provenance()` loads it; env var overrides settings; journal-mode garbage values resolve to `enforce`.
- Constructor refuses with a clear, actionable error (upgrade path, backports, provenance registration — pointing at §4 of this report).

**Gate suite:** `tests/test_g4_rev3_runtime_gate.py` — **30 passed** (version matrix, provenance completeness, enforce/acknowledge constructor semantics, settings fallback/resolution rules, inventory keys).

This machine's verdict (measured at every gate run): affected — Python 3.14.3 bundled SQLite `3.50.4`, source id `2025-07-30 19:33:53 4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3`; not a documented backport; no provenance record.

---

## 2. Amendment 2 — migration execution separated from readiness (P0)

**Implemented.**

- **Constructor = validation-only.** `SQLiteStorageBackend._init_or_validate_sync()`: absent database → canonical initialize; `current` → proceed (subject to the Am-1 runtime gate); `legacy_pending_migration` / `invalid` → refuse with `MemoryReadinessError` carrying an encapsulated remediation string ("stop all processes using this database, then run: `ocbrain memory-migrate --db <path>`"). **Zero mutation** on refusal — proven by a byte-level schema/data snapshot test (`validation-only startup zero-mutation snapshot proof`).
- **Dedicated maintenance entry point** following the repo's actual CLI architecture (click group with subcommands; local-only on purpose — maintenance runs with the app stopped):
  - `ocbrain memory-migrate --db <path>` (default from `config.get("memory.database")`, fallback `.data/memory/unified.db`) — prints the deployment contract, runs the runner, renders the step table (steps, ledger row, checkpoint, WAL figures).
  - `ocbrain memory-doctor --db <path>` — runs the full validation battery read-only (prefers read-only connections, with writable fallback; see RF-1).
  - `ocbrain memory-verify --db <path>` — focused whole-DB + FTS verification.
- **Maintenance lifecycle implemented in `core/memory/sqlite_migration.py::run_maintenance_migration`** in exactly the contracted order: gate quiescence → advisory file lock (+ `BEGIN IMMEDIATE`) → **re-read migration state after locking** → apply (canonical trigger swap + additive indexes) → FTS external-content `rebuild` → verify (identity + full integrity + retrieval + FK) → per-database ledger row → **commit** → success reported only after commit → optional post-commit `TRUNCATE` checkpoint, recorded honestly (never forced).
- Concurrency: two independent **subprocess** runners racing on one database serialize at exactly one of two outcomes — `{migrated, already_applied}` with no double-migration and no double ledger row (real child process via `tests/_g4_migration_child.py`; the refactored child re-raises exceptions without swallowing `SystemExit`).
- **Deployment contract documented** (§5) and printed by `memory-migrate` before any action.

**Gate suite:** `tests/test_g4_rev3_migration_lifecycle.py` — **12 passed** (plus per-database ledger coverage for Amendment 7: two independent DB files, each with its own lifecycle and its own ledger).

---

## 3. Amendment 3 — integrity validation is real, not a heartbeat (P0/P1)

**Implemented in `core/memory/sqlite_integrity.py`.** Four independent checks with measured costs, each result carrying status/scope/detail/duration:

1. **Whole-database `PRAGMA integrity_check`** (structural/b-tree).
2. **`PRAGMA foreign_key_check`** (honest `not_applicable` when no FKs exist).
3. **FTS5 `integrity-check(rank=1)`** — the real external-content consistency command (see RF-1 for the writable-connection requirement, RF-2 for the affected-runtime behavior after DELETE).
4. **Real `MATCH` probes** (`check_fts_retrieval`) with controlled token pairs `(token, must_match)`.

Additionally:

- **Pre-migration structural check** (Amendment 3 §B): `run_maintenance_migration` runs the whole-database structural check BEFORE any modification; on corruption it stops, classifies `preserved_corrupt`, and **preserves the database untouched** (zero-rebuild policy damage recovery).
- **Scoped results + measured costs**; no check is silent or unmeasured.
- **Cost contract:** readiness validation (`validate_readiness`) ≠ full validation: full validation runs only in the maintenance path and on demand; heartbeats/ordinary startup never pay the `rank=1` rebuild-scale cost (spied: heartbeat path doesn't invoke it).
- **Damage-detection proof:** with sync triggers dropped and content drifted, the `rank=1` command does NOT pass (it raises — recorded as `error`, which is in the failed set), while whole-DB `PRAGMA integrity_check` still passes — demonstrating the two checks are independent and why both are required.

**Gate suite (together with Amendments 4/6/8):** `tests/test_g4_rev3_sqlite_contract.py` — **31 passed**.

---

## 4. Amendment 4 — content-row identity invariants (P0)

**Implemented (`verify_content_row_identity`).** Every identity-bearing check runs and may fail loudly:

- the content table is **not `WITHOUT ROWID`**,
- **no `rowid`/`oid`/`_rowid_` shadow columns** declared,
- **rowids are unique** (unique index over `rowid` semantics verified via real queries),
- an identity FAIL case is exercised intrinsically (check must report fail, readiness must refuse).

**Disposition — the OPEN item stays OPEN on purpose:** the external-content FTS design *depends* on the content table's implicit rowid staying stable. The persistent, structural risk (future `WITHOUT ROWID` migration; external tooling rewriting the table / export-import renumbering) is **not resolved by this remediation and is not authorized to be resolved by a table rewrite**: no `VACUUM`, no table rebuild was performed or is permitted by this work (static audit asserts prod code never issues VACUUM; `VACUUM INTO` is audited-against, not enabled). The residual risk is **registered in the debt ledger as DEBT-045** (this report's internal id **DBT-R3-IDENTITY**), including what would have to be true before any rewrite could be considered.

- **Backups**: exclusively through the SQLite **Online Backup API** (`create_online_backup`) — identity-preserving, consistent snapshot; backup identity is re-verified by tests. `run_maintenance_migration` protocol offers it; no file-copy backup is used anywhere.

**Gate suite:** covered inside `tests/test_g4_rev3_sqlite_contract.py` (identity checks, fail cases, OPEN-risk wording, backup API identity).

---

## 5. Amendment 5 — mutation atomicity under failure (P0)

**Implemented/proven via SQLite authorizer fault injection** (`tests/test_g4_rev3_mutation_atomicity.py` — 7 passed). Method (empirically verified before writing the tests):

- **INSERT path** → deny `SQLITE_INSERT` (action 18) on the virtual `knowledge_entries_fts` (fires for `ke_ai`'s insert and `ke_au`'s pair);
- **UPDATE path** → same INSERT denial (the canonical `ke_au` expresses update-through-external-content as the documented `'delete'` + INSERT pair — the pre-Rev 3 raw `UPDATE knowledge_entries_fts SET …` pattern is gone, so the INSERT denial is the correct instrument for the update path);
- **DELETE path** → deny `SQLITE_DELETE` (action 9) on the virtual table (`ke_ad`).

Guarantees verified per path:

- the mutation **fails loudly** (authorizer "not authorized"), never silently;
- **full rollback: zero partial rows** — content table AND FTS mirror rows unchanged (mirror snapshots are scoped `WHERE id IN (SELECT rowid FROM knowledge_entries)` because FTS `_data` legitimately carries structural rows id=1 etc.);
- database remains **rank=1-consistent** after every rejected mutation (no delete ever happened, so the strict pass claim holds);
- **retry of the same operation succeeds** once the injected fault is removed, through the public API.

Also: a deliberate dead end discovered and documented — denying `SQLITE_READ` on an FTS shadow `rowid` does not fail loudly; it causes **silent desync**. It is recorded (§9 RF-3) and forbidden as an injection instrument.

---

## 6. Amendment 6 — secure-delete disposition (P1)

**Investigation only; NOT enabled.** `PRAGMA secure_delete` current values inventoried on the actual runtime (build default `0`; memory-backend connections unset it explicitly to the build default in the connection inventory) — **both stay OFF**. No setting change was made anywhere (prod-code audit: no assignment). The question "does enabling secure_delete affect FTS index handling of deleted rows?" is answered by runtime evidence: **on the affected runtime the deletion anomaly (RF-2) exists with secure_delete OFF; no claim is made about ON behavior, and enabling it is NOT authorized by this remediation.** The investigation findings are recorded (this report §7–§9); the regulatory question ("deleted-content erasure guarantees") remains an open policy item for the owner, tracked alongside DEBT-045's context. Tests: `tests/test_g4_rev3_sqlite_contract.py` (secure-delete read-only coverage).

---

## 7. Databases of the memory subsystem — inventory (Amendment 7; measured Nov 5, 2026)

Enumerated from the actual deployment on this machine (sizes as measured; `context.sqlite` lives outside `.data/`):

| Database (path) | Subsystem / layer | Managed by | Carries the FTS trigger contract? | Rev 3 migration state (Nov 5) | Ledger file? |
| --- | --- | --- | --- | --- | --- |
| `.data/memory/unified.db` (77,824 B) | L1 episodic (`SQLiteStorageBackend`, shared singleton via `get_unified_memory(".data/memory")`) | memory storage | **YES** — `knowledge_entries` + `knowledge_entries_fts` external content | **migrated** — `ocbrain memory-migrate` executed Nov 5, outcome `migrated`, ledger row `mlc_v1_fts_external_content_trigger_contract`, checkpoint `busy=0` | yes (`_ocbrain_memory_migrations`) |
| `.data/memory/archive.db` (45,056 B) | L4 audit (`SQLiteArchiveBackend`) | memory archive | no (plain tables, no FTS5 table exists) | n/a (no contract to migrate) | no |
| `.data/memory/graph.db` (32,768 B) | L3 knowledge graph (`GraphEngine` via `core/memory/backends/sqlite_graph.py`) | memory graph | no | n/a | no |
| `.data/events/stream.db` (32,768 B) | event stream (`SQLiteEventStore`) | events | no | n/a | no |
| `.data/runtime_state.sqlite` (24,576 B) | runtime state store (`core/runtime/state.py`) | runtime | no | n/a | no |
| `data/context.sqlite` (32,768 B) | working context (`ContextMemory`, `core/context.py`) | context | no | n/a | no |
| (chroma / per-module query context dirs) | expected by the remediation plan's inventory template | modules | — | **do not exist in this deployment snapshot** (verified by directory walk) | — |

Honest consequences:

1. Exactly **one** database in this deployment carries the FTS external-content trigger contract (`unified.db`); it was migrated through the real CLI command (see §5 of the deployment steps below), and its per-database ledger proves the lifecycle.
2. The lifecycle/ledger machinery has additionally been proven against **two independent database files** whose only shared trait is the contract (lifecycle suite's `TestPerDatabaseLedgers`) — the "per-file ledger" guarantee is not a singleton accident.
3. Multiple migrations of the *same* logical store under different prefixes would each carry their own ledger — no process-global flag stands in for per-database truth.

---

## 8. Checkpoint policy (Amendment 10) — disposition & inventory

**No global policy change was made or is authorized by this remediation.**

- **Automatic checkpointing:** SQLite's default `wal_autocheckpoint=1000` **pages per connection** stays as is for every memory-backend connection. Verified live (a real backend connection reads back `journal_mode=wal`, `wal_autocheckpoint=1000`) and by static audit (no assignment of `PRAGMA wal_autocheckpoint = …` anywhere in `core/` or `interface/`; no backend writes the pragma at all).
- **Explicit checkpoint sites — the complete list (`EXPLICIT_CHECKPOINT_SITES`, static-audited against source by the test suite):**
  1. `core/runtime/state.py` — `PRAGMA wal_checkpoint(TRUNCATE)` in the runtime state store's read-modify-write repair paths (2 executing sites; this database is NOT memory-managed),
  2. `core/memory/sqlite_migration.py` — the maintenance runner's **post-commit** `TRUNCATE` checkpoint inside the verified-quiescence maintenance window.
  The memory backends (`sqlite_storage`, `sqlite_archive`, graph engine) run **no explicit checkpoints** — asserted by test.
- **Scheduling owners recorded:** automatic — SQLite autocheckpoint per connection (any writer may trigger it); explicit — only the maintenance runner (and the unrelated runtime-state repair paths).
- **busy-handling:** a blocked TRUNCATE cannot evict readers; the runner records `busy=…` honestly and never forces (`report.checkpoint["note"]`).

**Gate suite:** `tests/test_g4_rev3_policy_disposition.py` — **7 passed** (inventory keys, static execution-site audit exactly `{state.py: 2, sqlite_migration.py: 1}`, no-backend-checkpoints, no `PRAGMA wal_autocheckpoint` assignment, live default intact, maintenance checkpoint honesty).

---

## 9. Findings register (ordered by decision impact)

 tracked ids: RF-* are this report's runtime/implementation findings; DBT-R3-IDENTITY maps to the debt-ledger DEBT-045.

### RF-2 — affected SQLite build leaves deleted external-content FTS docs MATCH-findable and breaks the `rank=1` command (OPEN — blocks runtime certification; deferred to Plan R1)

Reproduced **independent of repository code** (raw probes; Appendix A):

- after a successful `DELETE` on an external-content FTS5 table on SQLite **3.50.4**: `SELECT … MATCH '<deleted-token>'` **still returns the freed rowid**; `SELECT count(*) FROM fts` returns 0; the `_data` mirror row is gone; the documented `integrity-check(rank=1)` command returns *"database disk image is malformed"*; whole-database `PRAGMA integrity_check` passes.
- the stale match is tied to the freed docid: rows freshly written afterward with unrelated content **do not inherit** the stale tokens;
- the **public** surface (`search_text()` → `UnifiedMemory.search()`) stays correct purely because of its `ke.rowid = fts.rowid` JOIN filter (dangling rowids have no content row).

Disposition: **not fixable inside this repo** — this is the affected-build symptom class the Amendment 1 gate exists for. The test suites encode it honestly: conditional assertions keyed on `classify_wal_safety().wal_safe` (affected-build expectations documented as findings; fixed builds must satisfy the strict forms — see `TestRuntimeFindingRank1AfterDelete`, `TestRuntimeFindingStaleMatchAfterDelete`). This is the load-bearing basis of the §0 certification refusal.

### RF-1 — `FTS5 integrity-check(rank=1)` requires a WRITABLE connection (documented SQLite behavior; repository resolved)

On every SQLite build, that command is implemented as an `INSERT` on the FTS shadow; a read-only connection refuses it with *"attempt to write a readonly database"*. Repository consequence: `memory-verify` opens its verification connection read-write (visible note in the CLI: checks themselves remain non-mutating — the only eligible "write" is the integrity-check command); `memory-doctor` prefers read-only connections as long as they suffice, with a writable fallback so the FTS-internal check can run. Recorded so no future "read-only everywhere" refactoring silently drops FTS-internal verification.

### RF-3 — authorizer denial of SQLITE_READ on FTS shadow rowid silently desyncs (documented; forbidden instrument)

Denying `SQLITE_READ` targeting an FTS shadow row (via the test authorizer) does NOT raise: the FTS sync proceeds while its reads return nothing, entering a silent desync. Furnished as a finding both for the test-harness guidelines ("denials of READ must never be used as a fault-injection instrument for FTS sync paths") and as a caution for any production feature that instruments FTS reads.

### RF-4 — click dispatch swallowed the first subcommand token (pre-existing CLI defect; fixed)

The repo's click group defined a positional `[QUERY]` argument on the group itself; as a click parsing effect the first positional token (e.g. `memory-migrate`) was captured by the group argument instead of resolving the registered subcommand — **all subcommands were unreachable** through normal invocation. Fixed via `SubcommandFirstGroup(click.Group)` (`interface/cli.py`): when the first argument token names a registered subcommand, `parse_args` hides the positional argument for that parse and the subcommand resolves; the group callback still runs afterwards (`ctx.params.setdefault("query", None)`). A regression was kept: the group positional still works for the ordinary single-query invocation. Verified by CLI smoke (`g4_smoke2_cli.py`, rc 0) for all three maintenance commands.

### RF-5 — CLI report renderer crashed on legacy Windows consoles over `→` (found in this pass; fixed)

`_print_migration_report` used the Unicode arrow `→` in the WAL-bytes line; on a cp1252 legacy console without UTF-8 forcing, rich crashed with `UnicodeEncodeError` **after** the migration had succeeded and its output was printed. Fixed by using ASCII (`->`) in the new report helper. (Pre-existing, non-Rev-3 lines with `→` at `interface/cli.py` 166/175/530 were left untouched — out of remediation scope; they predate this work and are not maintenance-path code.)

### DBT-R3-IDENTITY — hidden rowid persistence risk (OPEN by design; registered as DEBT-045)

See §6/Amendment 4. The identity of external-content FTS rows rests on implicit content-table rowids. This is safe under SQLite's documented operation (rowids survive VACUUM; VACUUM INTO preserves them; nothing rewrites the table here) but structurally fragile against future schema rewrites (`WITHOUT ROWID`) or external export/import cycles. No rewrite is authorized; the risk is ledgered with explicit leave-as-is rationale and verification paths (`verify_content_row_identity` at value-adding moments).

---

## 10. Which acceptance gates passed (restricted verdict matrix)

Verdict vocabulary: **PASS** = implementation + tests satisfy the amendment's acceptance conditions on this machine; **PASS (runtime-conditional)** = passes with honest conditional encoding of the affected-runtime findings; **BLOCKED** = cannot be claimed regardless of code, per Amendment 12, until Plan R1 completes.

| Gate | Amendments | Evidence (all from `python -m pytest <suite>` on this machine) | Verdict |
| --- | --- | --- | --- |
| **Gate 0** — runtime compatibility gate | Am 1 | `test_g4_rev3_runtime_gate.py` — 30/30 | **PASS (enforces refusal on affected builds)** — runtime itself is affected; certification sense = BLOCKED until R1 |
| **Gate 1A** — migration lifecycle & readiness | Am 2 (+7 lifecycle) | `test_g4_rev3_migration_lifecycle.py` — 12/12 (incl. subprocess concurrency, zero-mutation startup refusal) | **PASS** |
| **Gate 3A** — integrity/validation contract | Am 3 (+4, 6, 8) | `test_g4_rev3_sqlite_contract.py` — 31/31 (damage injection, FK, identity incl. fail-cases + OPEN-risk text, config audit, trigger audit incl. legacy/missing/unknown, heartbeat cost cap, no-VACUUM, backup identity, secure-delete read-only) | **PASS (runtime-conditional)** |
| **Gate 4A** — mutation atomicity | Am 5 | `test_g4_rev3_mutation_atomicity.py` — 7/7 (3 paths × rollback/no-partial/consistency/retry + runtime finding) | **PASS (runtime-conditional)** |
| **Gate 5A** — secure-delete disposition | Am 6 | (inside Gate 3A suite; no change shipped) | **PASS** (investigation-only disposition honored) |
| **Gate 6A** — search regression across both surfaces | Am 8/9 | `test_g4_rev3_search_regression.py` — 8/8 (UPSERT-path retirements strict on BOTH surfaces; DELETE-path retirement strict on the public surface, runtime-scoped on the direct surface; token identity via rowid; integrity agreement after revisions; runtime-finding encoding) | **PASS (runtime-conditional)** |
| **Gate 7A** — checkpoint policy & failure recovery | Am 10/11 | `test_g4_rev3_policy_disposition.py` — 7/7; `test_g4_rev3_failure_recovery.py` — 10/10 (SQLITE_FULL-equivalent fault matrix: all in-tx faults roll back everything and the retry succeeds; the post-commit checkpoint fault keeps the committed migration honestly failed-as-run and the retry returns `already_applied`; space-estimate honesty incl. `'an estimate, NOT a guarantee (Amendment 11)'` in `estimate_basis` carried into the ledger) | **PASS** |
| **Dependent baseline** | regression safety | `test_session4c_architecture.py` + `test_unified_memory.py` — **109/109** (same test count as the pre-Rev 3 baseline; two Session 4C tests retargeted to the Rev 3 contract, §11) | **PASS** |

**Combined total: 214/214.** No failing or skipped test in the affected set.

### The verdict statement operates under Amendment 12

Per Amendment 12 the final verdict CANNOT be "IMPLEMENTATION COMPLETE — ALL GATES PASS" while the production SQLite runtime is affected. This report therefore claims exactly:

- **Implementation complete** (all twelve amendments implemented and test-covered),
- **Certification refused for the affected runtime** — deployment readiness is `ready_degraded_runtime_not_supported` until Plan R1 executes; the acknowledgment escape is test-environment-only and must not be used for production certification,
- Findings RF-1..RF-5 and DBT-R3-IDENTITY disclosed with dispositions — nothing scrubbed, nothing rewritten to look clean.

---

## 11. Changes made to pre-existing suites (why they changed and what they now assert)

1. `tests/test_session4c_architecture.py::TestPhase2HiddenIssueFTS5TriggerBug`
   - `test_ke_au_trigger_uses_documented_delete_insert_pattern` — the source under test was `_init_sync`, which no longer exists (the DDL moved to the canonical contract). Now asserts the canonical contract (`CANONICAL_TRIGGER_DDL["ke_au"]`): no raw `UPDATE knowledge_entries_fts`, exactly the `'delete'`-command + INSERT pair, and the `ke_ai/ke_au/ke_ad` name set.
   - `test_existing_database_is_migrated_on_reopen` → **behavior changed by design (Amendment 2)**: ordinary construction of a legacy database must now **refuse** (`MemoryReadinessError`), then `run_maintenance_migration` migrates, then the backend opens normally and the original post-conditions hold (`'delete'` in `ke_au` SQL; UPSERT revision semantics work; old token unsearchable).
2. `tests/test_session4c_architecture.py::TestDeferredIssuesRationale::test_issue7_metadata_search_deferred_to_v438` — the "USING fts5(" source probe was keyed to the inline DDL location; retargeted to `CANONICAL_FTS_DDL` with the same rationale intact (metadata is persistently NOT an indexed column).
3. Collection-safety discovery (deployment-impacting, resolved): importing `core.orchestrator` eagerly constructs the `ContextAssemblyEngine(get_unified_memory())` singleton, which builds `SQLiteStorageBackend` on the repo's real `.data/memory/unified.db`. Pre-Rev 3, that constructor silently migrated. Post-Rev 3, it **refuses** a legacy database — a hardware-level fail-closed posture that surfaces as an import-time error until the deployment runs its one-time maintenance migration. Resolution on this machine: followed the documented deployment contract — stopped nothing (no processes were running), ran `ocbrain memory-migrate --db .data/memory/unified.db` (outcome `migrated`, ledger row recorded, checkpoint `busy=0`), and re-ran the suite. This is the documented operator flow for the upgrade — it is recorded here because any Python process that imports the orchestrator path (API, agent, tests) will hit the same refusable state before maintenance runs, and that is the intended fail-closed behavior.

---

## 12. Files touched (all uncommitted — this workspace is not a git repo)

Production:

- `core/memory/backends/sqlite_storage.py` — constructor gate/ack/readiness integration (validation-only `_init_or_validate_sync`; `_resolve_configured_gate_mode`; provenance wiring; never full readiness on affected runtime).
- `core/memory/sqlite_migration.py` — `run_maintenance_migration` (fault_injection hook, quiescence, locks, re-read-post-lock, apply/rebuild/verify/ledger/commit/checkpoint), `inspect_migration_state`, `read_migration_ledger`, `estimate_migration_space`, `create_online_backup`, `collect_checkpoint_inventory`, `EXPLICIT_CHECKPOINT_SITES`, `REPRESENTATIVE_SPACE_FACTOR`.
- `core/memory/sqlite_integrity.py` — the four-check battery, `validate_readiness`/`run_full_integrity_validation`, `verify_content_row_identity`, config/trigger/secure-delete readers, cost accounting.
- `core/memory/sqlite_contract.py` — canonical DDL, `MIGRATION_ID_V1`, `MemoryReadinessError`, `KNOWN_LEGACY_DEFINITIONS`, readiness result types.
- `core/memory/sqlite_runtime.py` — `classify_wal_safety` + `load_configured_vendor_provenance` + runtime/connection inventories.
- `interface/cli.py` — three local maintenance commands (`memory-migrate`, `memory-doctor`, `memory-verify`), `_memory_db_path`, `_open_verify_connection`, `_print_migration_report`, `_MIGRATION_DEPLOYMENT_CONTRACT`, `SubcommandFirstGroup` dispatch fix, ASCII-safe WAL line.
- `config/settings.toml` — `[memory]` section (`wal_gate_mode = "enforce"`; commented vendor-provenance template).
- `tests/conftest.py` — test-env-only `OCBRAIN_MEMORY_RUNTIME_ACK=acknowledge` setdefault + `enforce_runtime_gate` fixture (documented; not a production escape).

Tests:

- `tests/test_g4_rev3_runtime_gate.py` (30)
- `tests/test_g4_rev3_migration_lifecycle.py` (12) + `tests/_g4_migration_child.py` (subprocess child)
- `tests/test_g4_rev3_sqlite_contract.py` (31)
- `tests/test_g4_rev3_mutation_atomicity.py` (7)
- `tests/test_g4_rev3_search_regression.py` (8)
- `tests/test_g4_rev3_failure_recovery.py` (10)
- `tests/test_g4_rev3_policy_disposition.py` (7)
- `tests/test_session4c_architecture.py` (2 retargets + 1 source-check retarget; net test count unchanged)

Registers/docs:

- `KNOWN_ISSUES.md` — new sync note + **DEBT-045** (DBT-R3-IDENTITY; hidden-rowid persistence risk).
- this report.

---

## 13. Remediation Plan R1 — runtime upgrade steps (the certification blocker)

For an affected build (this machine: CPython 3.14.3 + SQLite 3.50.4), choose ONE:

1. **Preferred — full runtime upgrade:** move the interpreter/bundled SQLite to **≥ 3.51.3** (pull a newer Python build, e.g. 3.14.x with 3.51.3+, or upgrade `sqlite3` via the distribution's packaging where applicable), OR
2. **Documented backport:** install one of the fixed backport builds (**3.50.7** or **3.44.6** — the range names apply to the 3.50/3.44 patch lines), OR
3. **Vendor build with provenance:** a vendor build is only certifiable when its provenance record is registered in `config/settings.toml` `[memory] wal_gate.approved_vendor_builds` with **all** fields (`source_id`, `distribution`, `evidence_url`, `verified_on`) — partial records fail closed.

After installing the fixed runtime:

1. **Maintenance window:** stop and drain ALL OCBrain processes on this machine (API, workers, one-off scripts — anything importing the orchestrator path constructs the memory singleton). Nothing may open the DB until step 5.
2. **Backup:** `create_online_backup` (already scripted; never file-copy).
3. **Verify current state:** `ocbrain memory-doctor --db .data/memory/unified.db` → expect `current`, all four checks pass, `total_cost_s` finite.
4. **Migrate (already done here, idempotent):** `ocbrain memory-migrate --db .data/memory/unified.db` → `already_applied` expected; ledger stays single-row.
5. **Re-verify under the FIXED runtime (this is the certification step):** re-run the seven Rev 3 gate suites WITHOUT `OCBRAIN_MEMORY_RUNTIME_ACK` (enforce mode must accept the new runtime), plus the two baseline suites. The runtime-conditional finding tests (`TestRuntimeFindingRank1AfterDelete`, `TestRuntimeFindingStaleMatchAfterDelete`) must assert the strict fixed-build forms; `classify_wal_safety().wal_safe` must be true.
6. **Deployment readiness:** the memory service reports `ready` (no longer degraded); only now may any "all gates pass" claim be written into release notes.
7. **If a corruption ever appears before step 5:** stop everything; do NOT repair in place; take file-level copies only for forensics (never delete/trim `-wal`/`-shm`); treat as a preserved_corrupt case via the maintenance runner.

Note: because RF-2's symptoms only appear after deletions, a database that has never taken a DELETE under 3.50.4 is not exempt — the anomaly class is the reason for the whole gate, and clean-so-far is not evidence.

---

## 14. Deployment contract (Amendment 2 §C) — verbatim from the CLI

```
Deployment contract (Amendment 2 §C): migration runs ONLY with all
OCBrain processes stopped and drained on this machine. Live mutations
during migration invalidate its locks; the final WAL checkpoint would
be silently undone by a concurrently opened connection.
```

Operator steps: (1) stop/drain; (2) `memory-doctor --db <path>` (state snapshot); (3) optionally `create_online_backup`; (4) `memory-migrate --db <path>`; (5) re-open/verify. The runner enforces an advisory lock file (`<db>.ocbrain_migrate.lock`) on top of `BEGIN IMMEDIATE`; a second concurrent runner exits with `already_applied` (proven cross-subprocess).

---

## 15. Space-estimate basis (Amendment 11)

`estimate_migration_space` reports honest, measured pages (`page_size`, `page_count`, `freelist_pages`, `content_bytes_measured`) plus an envelope: `estimate_extra_bytes = content-table bytes × REPRESENTATIVE_SPACE_FACTOR (2.0, measured on synthetic datasets for WAL growth + FTS index rebuild envelope)` and the actual `free_bytes` of the target volume with a plain boolean `sufficient_free_estimate`. The basis string is contractual: *"...an estimate, NOT a guarantee (Amendment 11)"*, and it travels into the report AND the durable ledger row (`pre_checks_json.space.estimate_basis`) — asserted by test. No maintenance step refuses purely on the boolean; it informs operators and is recorded.

---

## Appendix A — raw probes (evidence scripts, temp workspace `…\Temp\opencode\`)

| Script | Purpose (measured facts) |
| --- | --- |
| `g4_probe1..4.py` | authorizer action codes (SQLITE_INSERT=18 / SQLITE_DELETE=9), rank=1 semantics, runner hook trace |
| `g4_auth_probe.py` | the exact denial surface per path + full authorizer call log |
| `g4_delete_probe.py` | after a successful repo-path DELETE on 3.50.4: rank=1 → error while global check passes |
| `g4_evacuate_probe.py` | raw SQLite: single/total DELETE → rank=1 "malformed" (repro, build-dependent) |
| `g4_stale_match_probe.py` | raw SQLite: MATCH still returns the deleted docid; `count(*)`=0; `_data` mirror gone |
| `g4_reuse_probe.py` | stale hit tied to the freed docid; fresh content does not inherit old tokens; JOIN-filtered public view is clean |
| `g4_smoke1.py` | full lifecycle smoke (enforce refusal → ack → fresh init → legacy refusal → maintenance sequence/ledger/commit/checkpoint/WAL/backup identity) |
| `g4_smoke2_cli.py` | all three CLI commands end-to-end on a real DB (rc 0) |

## Appendix B — reproduction commands

```bash
# all new gate suites (env OCBRAIN_MEMORY_RUNTIME_ACK=acknowledge is set by conftest)
python -m pytest tests/test_g4_rev3_runtime_gate.py tests/test_g4_rev3_migration_lifecycle.py \
                  tests/test_g4_rev3_sqlite_contract.py tests/test_g4_rev3_mutation_atomicity.py \
                  tests/test_g4_rev3_search_regression.py tests/test_g4_rev3_failure_recovery.py \
                  tests/test_g4_rev3_policy_disposition.py -q

# certification run on a FIXED runtime: drop the acknowledgment first
OCBRAIN_MEMORY_RUNTIME_ACK= python -m pytest tests/test_g4_rev3_runtime_gate.py -q   # expect enforce-mode acceptance

# baselines
python -m pytest tests/test_session4c_architecture.py tests/test_unified_memory.py -q
```
