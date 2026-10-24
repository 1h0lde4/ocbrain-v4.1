# G4 / FTS correctness — independent evidence audit report

**Status: PROPOSED audit record. Read-only. Documentation-only outputs.** G4 stays **OPEN · High · freeze-blocking**; G5–G8 **HELD**; freeze readiness **NOT DECLARED**. This audit changes no product code, test, workflow, allowlist or xfail, opens no branch or PR, pushes nothing, and authorises no implementation.

Audit date 2026-10-20/21 · evidence tree `1h0lde4/ocbrain-v4.1` @ `1d813bdae320bf34110c29836c81dc901c601c9b` · Python 3.12.3 · SQLite 3.45.1 · git 2.43.0 · Linux 6.18.44 x86_64 (2 vCPU, 8 GB), one machine.

---

## 1. Inputs obtained, with hashes

| Input | Role | sha256 |
|---|---|---|
| `fts_decision_packet_evidence_1d813bd.zip` (79,260 bytes, 29 files) | the evidence bundle under audit | `79c6146c609a76548260f261f05692d32bbd32f44694b430a096a48a079d2721` |
| `g4_fts_correctness_batch_decision_packet_1d813bd_PROPOSED.md` (264 lines) | packet, revision 1 (also inside the zip) | `4d24d7666d6e076c46b95926e5a3745175f2369479257b65939b803412a13ce3` |
| `addendum_evidence_labels_PROPOSED.md` (25 lines) | addendum, revision 1 (inside the zip) | `14184571a12694f443c53d5c8b83107a117125be814d527d0aa2e45f7d173ffd` |
| `abe17d13-g4_batch1_isolation_contract_spec_PROPOSED.md` | the PROPOSED spec | `0bf4148775ae6e20456327cb6009b42b9e6e8fc8b350a0acb4115a0ec653fa44` |
| `c017d8ee-attachment.txt` | the task prompt | `f7949f94cddfa85643e6401bcfb8535b68fa64c53ed5f54c1c7c3579231bb65d` |
| `batch1_review_response_1d813bd.md` | delivered report quoted by the packet | `1699456359e9ad4c3bb28a97e0ead8452d5808362ff90d555bfa29d1dec33b20` (matches the value the packet quotes; found by the derivation, check `static/hash/delivered-response-report`) |

The task names "four artifacts"; I read them as packet, spec, addendum and zip (the manifest is inside the zip). Recorded in `inputs/INPUT_HASHES.txt`. None was modified; all work used copies.

## 2. Phase 0 — integrity and reproduction

| Step | Command (scripts outside the extraction directory; `python -I`; paths as arguments) | Result |
|---|---|---|
| Hash originals | `sha256sum` | table above |
| Inspect before extracting | `unzip -l` / `unzip -Z1` | 29 file entries, no absolute paths or `..` |
| Extract into a fresh empty directory | `unzip` into a new directory | done |
| Verify the manifest | `sha256sum -c MANIFEST.sha256` | **28 / 28 OK, 0 failed**; the 29 files = 28 listed + `MANIFEST.sha256`; **no unlisted file** |
| Re-run the figure script | `packet_numbers_check.py <out.json> <preserved out dir>` | **72 / 72 pass; the new output file is byte-identical to the bundle's own output** — but see §5, AF-02: this script hard-codes its expectations and asserts only `<0.05 / <0.2 / <1.0` s for durations, so it measures self-consistency, not independence |
| Re-run the three documented probes in fresh disposable directories on a fresh detached worktree | `fts_integrity_semantics_probe.py`, `fts_legacy_ordering_probe.py`, `fts_migration_protocol_probe.py` (exit 0) | **ordering: identical** to run 2 and run 3 after ignoring the harness block; **integrity: identical** to run 2 and to run 1-as-run; **protocol: identical except** which of two racing processes performed the migration (`…/workers[i]/performed`, 2–6 paths); aggregate race counts identical; timings differ (informational) |
| Mixed-case defect and as-run output | `out/fts_legacy_ordering_run1_as_run_vocab_case_bug.json` preserved in the bundle; this audit did not touch it | confirmed present, labelled superseded; runs 2 and 3 corrected |
| Integrity probe consistent with its original | compare | identical (lower-case vocabulary, unaffected by the defect) |
| Preserved ordering runs | `cmp` | run 2 and run 3 are **byte-identical** (sha256 `314a993a…`), not merely identical after ignoring keys (the ignore list in the comparison is generic; the file has no timing keys) |
| Re-run the earlier contract matrix | `fts_contract_tests.py` from the preserved script copy, new disposable directory | exit 0; PASS/FAIL matrix and RC-07 counters **identical** to the two preserved runs; V0: LD 4 PASS, RC 4 PASS / 5 FAIL, PE 5 FAIL |

## 3. Independent derivation of every quoted figure (new)

`scripts/independent_derivation.py` parses the packet's own markdown (tables and prose), derives each quantity from the raw probe JSON, the repository checkout and the spec, and compares. A claim it cannot find in the packet is a failure, not a skip. Run over: preserved set A (ordering run 2, integrity run 2, protocol runs 1+2), preserved set B (ordering run 3, same others), the fresh reproduction (single protocol run, timings informational), and the contract matrices of two preserved runs plus the re-run.

**387 checks · 385 passed · 2 failed.** The two failures are the **same finding** in the two preserved sets (§5 AF-02).

| Packet claim group | Derived from | Checks (A / B / repro) | Status |
|---|---|---|---|
| §3.2 procedure table: 6 procedures × (rank=1 after, fixtures with discrepancy, rank=1 after W, ghosts per fixture, exceptions, false negatives) | `fts_legacy_ordering_run{2,3}.json`, repro | 53 / 53 / 53 | all pass |
| §3.2 readings: vacuity guard 7/7, 119 operations, rebuild-cleans-all, idempotency 7/7, F4 (one ghost match, malformed error), F5 seeds and 150-operation histories | same | included above | pass |
| §3.2 item 5 VACUUM: 0 rowids changed in 4 cells; gap maps; 2 of 4 had gaps; ghosts not removed | same | included above | pass (explanation added, rev 2 §4.8) |
| §5.1 five states; §5.2 eight cells × 7 steps, retrieval correct in 56 step-cells, anomaly shape, `PRAGMA integrity_check` end states; §7 runtime identity | `fts_integrity_semantics_run2.json`, repro | 42 / 42 / 42 | all pass |
| §3.3 seed state, exceptions 4/4, hard exits 4/4, non-atomic contrast, race 5/5 both variants, sizes, busy timeout | `fts_migration_protocol_run{1,2}.json`, repro | 21 / 21 / 10 | pass **except** the 50k-row duration |
| §3.3 durations 1k / 10k | same | within | pass (0.008–0.009 s, 0.07–0.08 s) |
| **§3.3 duration 50k: "0.41 s (two runs)"** | same | — | **FAIL: raw values 0.501 s and 0.410 s → 0.41–0.50 s** |
| §2 anchors (file:line), history, grep negatives, spec cross-references (I-4 quote, lines 428–435, INV-17, RM-22, RD-13, RD-10, DEL-1, DEL-4, §9.4, §10), delivered-report hash | worktree, `git`, spec, hash search | 26 | pass; two **informational** notes: a sixth commit/merge `6b8b0af` exists; default `git log -- path` hides `6b8b0af` and `984e640`; the file is 372/372 CRLF lines |
| §3.1 / §6 earlier evidence: LD 4/4 on every variant, RC 4 PASS / 5 FAIL on shipped, RC all pass on V1/V2, PE shipped 5/5 fail, PE-04 residue, RC fail set | contract matrices | 8 / 8 / 8 (three matrices) | all pass |

**Transcription check of the new rev 2 figures (new): `scripts/rev2_numbers_check.py`.** For each new figure quoted in packet rev 2 (R1 histories and product-path counts, R2 fault/torn-WAL/SIGKILL counts, R3 state dispositions and costs, R4 transaction facts, R5 concurrency figures, VACUUM controls, durations, history/digest facts) it derives the quantity from the raw probe JSON (or from `git`) and compares it with the author's expected literal, **and** requires the literal string used in the packet text to be present. Its expectations are hard-coded, so like `packet_numbers_check.py` it demonstrates that the packet transcribes the outputs faithfully, not that the outputs are right; that independence rests on the probes themselves, the source excerpts and the earlier independent derivation. Packet checked in runs 1 and 2: sha256 `6a15f26016313145319ee3b79adb92aab2fa3d9fe3c959e95d6ca3583f9e60f1`; run 3: sha256 `4685970bdbbf25b675504fb623312df5149e50f068c7a633087a08b09ef80eb9` (after the raw-docs provenance edits); **run 4 (final): the packet as delivered**, sha256 `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2` (after the timing-variability note in §5).
- **Run 1: 80 / 83.** The three failures were **defects of the checker, not of the packet**: two text patterns that did not match the packet's actual wording (`F4 (post-commit): state exactly post …` was searched with a capital S; `48 raw ghost rowids, 7 false positives` was searched without "raw"), and one JSON key lookup that used a name that does not exist in the classifier output (S5 drift keys are `explicit_verify_detects_drift` and `clean_after_explicit_repair`). In each case the derived value already equalled the expected value or the key was absent, so no figure in the packet was wrong. Run 1's output (`out/rev2_numbers_check_run1.json`, sha256 `05616b62…`) and the script as used for it (`scripts/superseded/rev2_numbers_check_as_used_for_run1.py`) are preserved; its stdout was not saved (the JSON holds the full result).
- **Run 2: 83 / 83** after the three checker corrections (`out/rev2_numbers_check_run2.json`, stdout `out/rev2_numbers_check_stdout_run2.txt`). No packet text was changed between runs 1 and 2.
- **Run 3: 83 / 83** on the text after the documentation-provenance edits (`out/rev2_numbers_check_run3.json`).
- **Run 4: 83 / 83** on the final packet text (`out/rev2_numbers_check_run4.json`, stdout `out/rev2_numbers_check_stdout_run4.txt`); the packet changed after run 2 only in documentation-provenance wording and one timing-variability note — no figure changed.

Repository re-checks done directly (not through the script): the two documentation conflicts (`docs/reports/SESSION4C_REPORT.md:142`; `docs/reports/context-compiler-remediation-register.md:75` "Confirmed live" vs `docs/reports/ARCHITECTURE_HARDENING_SESSION_REPORT.md:170` "dead code") are present at the baseline and unchanged at the current tip.

## 4. Evidence-model reconstruction (Phase 1) — summary

Full model: packet rev 2 §2 and the rev 2 addendum. Three product-state labels only (HISTORICAL BASELINE with OBSERVED/STATIC, NEGATIVE CONTROL, FIXED PRODUCT); purpose and evidence kind are separate axes; "protocol-feasibility" is a purpose. The raw evidence was **not** reclassified: no output file was edited, and every as-run file is preserved; only the descriptions in the new documents changed. Findings are AF-05 and AF-01 below.

## 5. Findings

Fields per the project's audit method: ID · component/path · observed · expected contract · evidence · impact class · disposition · status · residual. The project has not formally defined a severity scale for this audit, so none is invented; "impact class" says only what kind of correction it is. Status vocabulary: OPEN · CORRECTED IN REV 2 (PROPOSED, **unratified**) · VERIFIED · DEFERRED · ACCEPTED RISK. "Corrected in rev 2" means a proposed documentation correction exists; it does not mean ratified or closed.

| ID | Where | Observed | Expected | Evidence | Impact class | Disposition / status | Residual |
|---|---|---|---|---|---|---|---|
| AF-01 | packet §6 FTS-A2 baseline cell; §3.2 | "OBSERVED: 7/7 legacy fixtures fail `rank=1`" reports **prepared initial states** (raw SQL; synthetic histories), presented in a baseline column | separate the initial state from operations run through the unchanged implementation | new probes `fts_baseline_product_path` (7/7: the unchanged constructor repairs nothing; the product API workload equals the raw-SQL result) and `fts_baseline_fresh_api_history` (fresh DB, API only: ghost state in 3/3 histories; canonical-trigger control clean 3/3) | provenance / classification | rev 2 §4.2, §7, addendum §3.5 — CORRECTED IN REV 2 | real legacy databases not examined (UNKNOWN) |
| AF-02 | packet §3.3 duration row; §9 G-5; and the check script | "0.41 s (two runs)" at 50k rows; raw runs are 0.410 s and 0.501 s; `packet_numbers_check.py` asserted only `<1.0 s` and so could not detect it | quoted range equals the raw range | `independent_derivation` checks `preserved/protocol 3.3/duration-50000-rows` ×2; raw `protocol_migrate_s` | figure error | rev 2 §4.9, G-5 — CORRECTED IN REV 2 | timings are container-specific |
| AF-03 | packet §2 history row | "identical in all four commits that touched the file"; full history has **five** (merge `6b8b0af` omitted; its 348/348 line change is a line-ending conversion identical to its second parent); plain `git log -- path` shows three; file is all CRLF | state how history was enumerated | `git log --full-history`, per-version trigger extraction (identical body in all five and at the baseline) | omission / precision | rev 2 §3 — CORRECTED IN REV 2 | databases created outside this history UNKNOWN |
| AF-04 | packet §3.2 item 5 (VACUUM) | "0 rowids changed … not guaranteed, only observed" — true, but unexplained; the stability exists because the table has an index | explain, and show the property fails without one | `fts_vacuum_rowid_control_run1.json`: index-less table 1,4→1,2; index-less FTS shape → `rank=1` malformed + wrong retrieval; product shape preserved; mechanism `src/insert.c:3050-3063` @3.45.1 | explanation gap | rev 2 §4.8 — CORRECTED IN REV 2 | other SQLite versions UNTESTED |
| AF-05 | packet §6; addendum §2 item 2 and §3 | purpose and label mixed: V1/V2 (they **pass**) called "negative-control-style"; TR/A/RT, fault injection and race called "negative-control-style or feasibility" | three labels only; purpose is a separate axis | text of the originals | classification | rev 2 §2, addendum rev 2 §3 — CORRECTED IN REV 2; ratification = D-6 | maintainer may prefer the old wording |
| AF-06 | packet §3.3, §8 item 4 | only four **pre-commit** points tested; no post-commit termination; ambiguous commit outcome unaddressed | pre-commit failure → exact pre-state; ambiguous commit → verified complete pre or post; post-commit case added; no rollback required after commit | `fts_commit_boundary_run1.json` (Part A 10/10; Part B 40 variants; Part C 250 SIGKILL trials: pre 237, post 13, mixed 0) | omission | rev 2 §4.4, §5.2 — CORRECTED IN REV 2 | only 2 real kills landed in the commit window; 0/150 "targeted" kills did; power loss untested |
| AF-07 | packet §4.2 / G-4 | "UNVERIFIED for the product path" with no grounding of what the product connection does | ground the transaction semantics | `fts_txn_boundary_run1.json` T1–T10 on `_connect()`; CPython `Doc/library/sqlite3.rst` v3.12.3 | ungrounded gate | rev 2 §4.6, §5.4 — partly CORRECTED; **constructor path remains UNVERIFIED** | no product code was changed |
| AF-08 | packet §4.3 | marker mechanism "undecided"; no state table; "body-keyed detection" criticised but replacement not specified | five dispositions; both alternatives; fail-closed behaviour | `fts_state_classifier_run1.json` (10 states × 2 backends) | omission | rev 2 §4.5, §5.3 — CORRECTED IN REV 2; choice = D-4 / D-10 | policy for unrecognised/malformed/newer states is the maintainer's |
| AF-09 | packet §10 | writers during migration and readers on other connections listed UNTESTED; 2-process/5-trial race only | an explicit concurrency contract | `fts_concurrency_run1.json` C1–C6 | omission | rev 2 §4.7, §5.5 — CORRECTED IN REV 2 (feasibility only) | contender crash, mixed old/new code, four-process end-to-end UNTESTED |
| AF-10 | packet §5.1 and §10 (doc provenance) | FTS5/VACUUM wording obtained through a fetch tool (disclosed); the §6.3 quotation was shorter than the page; the task requires that ratification-critical wording not rest on a fetch-tool summary | verify at source where reachable | Python docs: **raw** `sqlite3.rst` @ v3.12.3 and @ the 3.12 branch tip. FTS5 behaviour: **raw** `fts5_storage.c`/`fts5_main.c` @ 3.45.1. FTS5 and `lang_vacuum` wording: **raw HTML of the SQLite 3.45.1 docs** from the signature-verified Ubuntu package (`docs/raw_sqlite_docs_verification.md`; 11/11 passages present; `out/rawdocs/rawdocs_check_run3.json`). The shell still gets 403 from sqlite.org, so the **live pages are unread raw**; the fetch tool's section numbers for the live page (§6.7/§6.12/§6.13) differ from the 3.45.1 docs (§6.6/§6.11/§6.12) | provenance + citation error (section numbers) | rev 2 §3.1 — CORRECTED IN REV 2 (heading ids cited) | wording for any other SQLite version, and the live pages, remain to be re-read per declared version (D-2) |
| AF-11 | packet §5 | the plain check is not an acceptance criterion — correct; the reason was only observed | state the source-level reason | `fts5_storage.c:964-966`; `fts5_main.c:1579-1581, 2978`: `PRAGMA integrity_check` also never compares with the content table | completeness | rev 2 §6 | — |
| AF-12 | `README.md` of the bundle | tree digest `624b0e3f…` presented as the tree's identity; it is worktree-path dependent (the `.git` pointer file is hashed): `46cacae3…` for another clean worktree of the same commit; 544 other files byte-identical, digest excluding that file `bbb5f945…` | record a path-independent identity | `tree_digest_compare_run1.json` | provenance | rev 2 §14, README | — |
| AF-13 | packet §3.2 head / README | "run 2 = run 3 after ignoring timing keys": the ordering files are byte-identical and contain no timing keys | accurate description | `cmp` | informational | noted | — |
| AF-14 | packet G-7 | overlap list omits **DEBT-042** (`_fts_escape`, `sqlite_storage.py:363-372`), registered on `main` after the baseline | current-tip facts in gates | `KNOWN_ISSUES.md` @ `f13bfde` | omission | rev 2 §3, G-7, G-10, D-11 — CORRECTED IN REV 2 | owner/sequence unassigned |

No finding invalidates a conclusion of revision 1. AF-01 and AF-06 strengthen it; AF-02, AF-03, AF-04, AF-05, AF-12 are precision corrections.

## 6. Source and documentation verification (Phase 2)

| Item | At source? | Where |
|---|---|---|
| Python 3.12 `executescript` commits a pending transaction; legacy mode; DDL no longer commits (3.6); defaults | **yes — raw** | CPython tag `v3.12.3`, `Doc/library/sqlite3.rst` lines 1542-1550 and 2603-2701 (file sha256 `f5be72345d2d37ffa53a82058b6054ed9052dda816a2e84639b96172fe3183b7`) |
| FTS5 `rank=1` is what compares an external-content index with its table; `PRAGMA integrity_check` does not | **yes — raw source and runtime** | SQLite tag `version-3.45.1`: `ext/fts5/fts5_storage.c` 964-966 (sha256 `3bc1cd00…`), `ext/fts5/fts5_main.c` 1579-1581, 2978 (sha256 `09db2446…`) |
| VACUUM rowid renumbering mechanism | **yes — raw source and runtime** | `src/insert.c` 3050-3063 @ 3.45.1 (sha256 `1592b84d…`) |
| FTS5 docs `#external_content_tables` (§4.4.3), `#the_delete_command` (§6.3), `#the_integrity_check_command` (§6.6), `#the_rebuild_command` (§6.11), `#the_secure_delete_configuration_option` (§6.12); `lang_vacuum` §3 `#how_vacuum_works` | **yes — raw HTML of the 3.45.1 docs** (not the live pages) | `sqlite3-doc_3.45.1-1ubuntu2.8_all.deb` sha256 `9a97bea1…f699`; chain: signed `InRelease` → `Packages.gz` → deb; `fts5.html` sha256 `9307f6fa…8d4d`, `lang_vacuum.html` sha256 `c5f201dd…ad2f`; verbatim sections `docs/raw_html_excerpts_sqlite3-doc_3.45.1-1ubuntu2.8.txt`. Live URLs for reference: `https://www.sqlite.org/fts5.html`, `https://www.sqlite.org/lang_vacuum.html` (**not** read raw: HTTP 403 from the shell; the fetch tool's summary agrees on wording but numbers sections differently) |
| Python `sqlite3` docs at the live URL `https://docs.python.org/3.12/library/sqlite3.html` | **yes — raw source of the page** (the rendered HTML was not read) | `Doc/library/sqlite3.rst` @ `v3.12.3` and @ the `3.12` branch tip `bb130d8…` (2026-10-20): both `executescript` entries and the 'Transaction control' section byte-identical |
| Repo static anchors, trigger bodies, `ke_au` migration, new-DB DDL, constructor, `executescript`, connection config, history, migration test | yes — read at `1d813bd` and re-derived | packet rev 2 §3 |
| Current-tip freshness | yes — unauthenticated fetch of `main` | tip `f13bfdef…` (2026-10-19 08:59 UTC), 30 commits ahead; the three relevant files identical; `488129b8…` is merge PR #80, an ancestor, not the tip |

## 7. New probes (all throw-away databases; product code untouched; every output reports `repo_unchanged: true`)

| Probe → output | What it establishes | Kind |
|---|---|---|
| `fts_baseline_product_path_probe` → `fts_baseline_product_path_run1.json` | reopening and API workload on the 7 prepared fixtures | OBSERVED (unchanged product) |
| `fts_baseline_fresh_api_history_probe` → `fts_baseline_fresh_api_history_run1.json` | the unchanged product creates the ghost state from a fresh database | OBSERVED (unchanged product); control = probe variant |
| `fts_txn_boundary_probe` → `fts_txn_boundary_run1.json` | transaction semantics on `_connect()`; `executescript` hazard; new-DB init | OBSERVED (probe on product connection class) |
| `fts_state_classifier_probe` → `fts_state_classifier_run1.json` | 10 state dispositions × 2 marker backends; drift the marker cannot see; costs | OBSERVED (probe artefact) |
| `fts_commit_boundary_probe` → `fts_commit_boundary_run1.json` (+ progress JSONL) | F0–F4, torn-WAL simulation, 250 SIGKILL trials | OBSERVED / SIMULATED |
| `fts_concurrency_probe` → `fts_concurrency_run1.json` | C1–C6 | OBSERVED; C6 extrapolation EXTRAPOLATED |
| `fts_vacuum_rowid_control_probe` → `fts_vacuum_rowid_control_run1.json` | VACUUM rowid controls | OBSERVED + STATIC |
| `tree_digest_compare` → `tree_digest_compare_run1.json` | worktree digest dependence | OBSERVED |
| `independent_derivation` → `independent_derivation_preserved_run1.json` | 387 checks | derived |

Disclosures: (a) the first attempt of the commit-boundary probe was cut short by a container restart and produced no result file; the series was resumed from its progress file twice (a fingerprint check guards the resume), so its 250 trials span several container boots and the interrupted attempt is not counted; (b) probe scaffolding bugs fixed during development (an early draft of Part B opened the database before reading raw WAL bytes; dead code removed) did not leave results in the outputs; (c) one of the probe helpers' wording ("targeted around commit") overstates what the series achieved — 0 of 150 targeted kills landed in the commit window; (d) all runs used the system interpreter, no virtual environment.

## 8. Assertions: reproduced / passed / failed / untested

| Assertion | Status |
|---|---|
| Bundle manifest "28/28" | **REPRODUCED, passed** (fresh extraction) |
| "72/72 derived" | **REPRODUCED (72/72, byte-identical output)** — self-consistency only; **independent derivation: 385/387**, 2 failed = AF-02 |
| Probe outputs reproducible in a fresh worktree/directory | **REPRODUCED** (identical, except which of two racing processes won, and timings) |
| Earlier LD/RC/PE matrix | **REPRODUCED** (identical in 3 runs) |
| Mixed-case defect preserved; corrected runs identical | **CONFIRMED** |
| Packet rev 2 transcribes its new figures from the raw outputs | **PASSED 83/83 on run 4 (final packet text)** (run 1: 80/83, three checker defects; runs 2 and 3: 83/83 on earlier text states; all disclosed in §3); self-consistency of transcription only |
| Legacy-state defect through the unchanged product | **OBSERVED** (new) |
| Atomic pre/post behaviour incl. post-commit | **OBSERVED / SIMULATED**; ambiguous window weakly sampled |
| Concurrency contract | **OBSERVED (probe)**; contender crash, mixed code, four-process end-to-end **UNTESTED** |
| Constructor-path integration | **UNVERIFIED** |
| Other SQLite versions / platforms / Python versions | **UNTESTED** |
| Real databases | **UNKNOWN** |
| Power loss | **UNTESTED** |
| FTS5/VACUUM doc wording | **VERIFIED at the raw 3.45.1 docs** (11/11 passages; chain of custody in `docs/raw_sqlite_docs_verification.md`); **live sqlite.org pages UNVERIFIED** (not read raw); other SQLite versions' wording **UNTESTED** |
| Secure-delete anomaly | **UNKNOWN** |

## 9. Blockers to implementation planning (none stops the documentation)

1. Minimum supported SQLite version not decided; one runtime only (D-2, G-2).
2. Migration-state mechanism and the policy for unrecognised/malformed/newer states not decided (D-4, D-10).
3. Constructor integration unverified; where the migration runs (constructor vs explicit startup step) in the four-process runtime is a design decision (G-4, G-9).
4. Startup behaviour on busy-timeout exhaustion not decided (D-9).
5. Real database sizes and legacy states unknown (G-5, D-7).
6. Overlapping work in `sqlite_storage.py` / `unified_memory.py` (I-3a, DEBT-042) has no assigned owner or sequence (G-7, G-10, D-11).
7. SQLite documentation wording: verified at the raw 3.45.1 docs only; the live pages and the wording for any other supported version must be re-read once D-2 declares the versions (not a blocker for the decision packet; a gate for ratifying wording-dependent claims).
No blocker of the kind "archive unavailable", "figure fails derivation (beyond AF-02)", "product transaction behaviour not grounded in source" or "migration state not recognisable" remains: the archive was available, one figure is a corrected range, the Python transaction behaviour is grounded in source and observation, and the states are recognisable by exact normalised body plus marker.

## 10. Limits

One SQLite build, one interpreter, one machine; throw-away databases; probe artefacts are not OCBrain code; timings are container-specific and vary run to run (the state-classifier cost probe, executed three times, gave `rank=1` verification 0.048 / 0.061 / 0.030 s at 10k rows and 0.243 / 0.267 / 0.155 s at 50k rows; the packet quotes the bundled run and now says so; lock-hold and rebuild durations were each measured in repeated reps and are reported as ranges); extrapolations are labelled; nothing here is acceptance evidence for a fix.
