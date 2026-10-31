# Session Handoff

## 1. Handoff Metadata

- Handoff version: 1
- Created at: 2026-10-24 (UTC); first written 2026-10-23 as a file-only handoff, updated here for the repository checkpoint
- Workstream: G4 FTS correctness and migration safety (Kernel v1.0 Phase G read-only verification study)
- Task identifier: "OCBrain G4 / FTS Correctness — Evidence Audit and Decision-Packet Errata" (prompt attachment `c017d8ee-attachment.txt`, sha256 `f7949f94cddfa85643e6401bcfb8535b68fa64c53ed5f54c1c7c3579231bb65d`, 15,404 bytes)
- Source session purpose: read-only independent evidence audit of the revision-1 FTS decision packet, addendum, spec and evidence ZIP; then a documentation-only PROPOSED errata revision under new names
- Governing state (unchanged by this session): **G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED; no implementation authorised**
- Branch / checkpoint: `docs/g4-fts-errata-handoff-oct2026` (documentation-only; not merged; no PR); transfer commit `eca2b96521fba8cf792ea16a58be997e4f949356`
- Transfer status: **TRANSFER READY** with documented, user-accepted non-repository state (see §19)

## 2. Original Starting Prompt

Verbatim copy of `c017d8ee-attachment.txt` (sha256 `f7949f94cddfa85643e6401bcfb8535b68fa64c53ed5f54c1c7c3579231bb65d`), spliced in by script; the hash was checked before writing.

~~~~text
OCBrain G4 / FTS Correctness — Evidence Audit and Decision-Packet Errata

Workstream: G4 FTS correctness and migration safety
Task type: Read-only evidence audit followed by a proposed documentation-only revision
Baseline: "1d813bdae320bf34110c29836c81dc901c601c9b"
Later known repository reference: "488129b8768a88a3d21dfd80b1f5407d50aba908"
Authorization: No implementation authorization has been granted.

1. Objective

Perform an independent, evidence-first review of all four supplied artifacts. Verify the evidence bundle, reconcile the FTS decision packet with its evidence-label addendum, verify the relevant technical claims against primary sources and repository history, and prepare a new proposed errata revision that resolves the review findings.

The goal is to produce a trustworthy, reproducible, maintainer-ready decision packet and an explicit list of remaining decisions and verification gates.

Do not start by editing documents. First establish what was delivered, what the evidence actually demonstrates, and what remains unverified.

2. Immutable project constraints

These constraints apply throughout this task:

- G4 remains OPEN · High · freeze-blocking.
- G5–G8 remain HELD.
- Freeze readiness remains NOT DECLARED.
- The three evidence categories—Historical baseline, Negative control, and Fixed product—must remain distinct.
- Protocol-feasibility evidence is a description of the purpose of an experiment, not a fourth product-state category.
- No product fix has been authorized.
- No requirement is ratified or accepted by this task.
- No FTS fix, physical-erasure change, authorization change, or unrelated remediation is in scope.
- Do not create a product implementation branch, modify product code, open a PR, push commits, or merge anything.
- Preserve the supplied source artifacts and all existing as-run evidence byte-for-byte.

3. Phase 0 — Establish identity and verify the evidence bundle

Before drawing conclusions, identify the exact four inputs and calculate SHA-256 hashes of their original files.

Record the filename, SHA-256, byte size and, where available, repository commit or provenance for each artifact.

For the ZIP:

1. Inspect its archive listing before extraction.
2. Extract it into a fresh, isolated temporary directory. Never extract over an earlier evidence directory.
3. Read its "README.md" and "MANIFEST.sha256".
4. Verify every manifest entry against the freshly extracted files.
5. Locate and inspect the figure-derivation script, its inputs, its expected environment and the preserved as-run outputs.
6. Run the documented reproduction procedure in the stated environment if available. Record the exact commands, interpreter/runtime versions, exit codes, stdout/stderr and resulting hashes.
7. Independently re-derive every numerical result quoted by the packet from the raw outputs. Check denominators, exclusions, fixture counts, false-positive/false-negative counts, operation counts, timing keys, case normalization, and run-to-run equivalence.
8. Confirm that the corrected ordering runs are reproducible and that the disclosed mixed-case harness defect and original as-run output remain preserved.
9. Verify that the corrected integrity-probe output is consistent with the preserved original output, with any differences explained.

The delivery reportedly passed 28/28 manifest checks and 72/72 derived-figure checks. Treat those figures as unverified claims until you have independently reproduced them from the exact supplied archive.

If the archive is unavailable, corrupt, incomplete, or cannot be run in the available environment, report the precise blocker and stop claims that depend on the missing evidence. Do not reconstruct missing results from the prose, generate substitute outputs and present them as originals, or mark an unexecuted check as passing.

4. Phase 1 — Reconstruct the evidence model

For every major claim and every acceptance-matrix row, identify:

- The precise source artifact, output file and test or probe ID.
- The exact implementation under test and its immutable commit, if applicable.
- Whether the claim comes from runtime observation, static source inspection, a synthetic fixture precondition, a diagnostic variant, or a proposed protocol experiment.
- The observed result and the independent reproduction status.
- The conclusion that the evidence supports.
- The conclusion that it does not support.
- Remaining uncertainty and the next required evidence.

Apply these evidence rules consistently.

Historical baseline: Evidence about the actual pre-fix implementation at the stated base commit. Label runtime behavior "OBSERVED" and source inspection "STATIC". Do not present a source-level inference as an executed behavior.

Negative control: A deliberately disabled, incomplete, or permissive implementation used on disposable data to determine whether a test can detect a defect. This is not historical product evidence and not fixed-product verification.

Fixed product: The actual corrected product at an immutable commit, run against the same accepted tests. The supplied packet states that this evidence does not yet exist.

Protocol-feasibility evidence: Results from TR/A/RT, transaction probes, fault injection, or race experiments on disposable databases. Record this as the purpose of the experiment, not as a product-state label.

Specifically review FTS-A2. A prepared legacy fixture failing "rank=1" establishes the fixture's inconsistent initial state. It does not, by itself, establish historical-product behavior. Separate initial-condition evidence from operations actually executed through the unchanged historical implementation.

Inspect the matrix and prose for inconsistent uses of “baseline,” “fails-before,” “passes-after,” “negative control,” “verified,” and “fixed product.” Correct the terminology in the new revision without reclassifying the original raw evidence silently.

5. Phase 2 — Independently verify technical claims

Use internet research and read-only repository inspection. Prefer primary documentation and exact source files over summaries, secondary articles, or generated text.

SQLite and Python sources

Verify the cited behavior directly in:

- SQLite FTS5 documentation: https://www.sqlite.org/fts5.html
- SQLite VACUUM documentation: https://www.sqlite.org/lang_vacuum.html
- Python 3.12 sqlite3 documentation: https://docs.python.org/3.12/library/sqlite3.html

Consult the relevant sections for external-content FTS5 triggers, the "'delete'" command and old indexed values, "integrity-check" with "rank=1", "rebuild", FTS5 "secure-delete", VACUUM and implicit ROWIDs, and Python transaction control and "executescript()".

Record exact sections and source URLs. Do not rely on a fetch-tool summary for ratification-critical wording.

Repository history and current implementation

Read-only inspect the baseline and current repository state. Verify:

- The "ke_ai", "ke_au" and "ke_ad" trigger bodies.
- The existing "ke_au" migration.
- How new-database DDL is initialized.
- Constructor-time transaction handling, "executescript()" calls and connection configuration.
- Per-call connections, WAL mode, busy timeout and commit behavior.
- The exact history of "sqlite_storage.py" relevant to the trigger changes.
- The existing migration tests and their coverage gaps.
- The current-main freshness comparison and whether relevant files changed since the baseline.
- The cited documentation conflicts, including "SESSION4C_REPORT.md:142" and the REM-012 live/dead-code conflict.

Use the actual current branch/commit discovered during this task; do not assume that "488129b8768a88a3d21dfd80b1f5407d50aba908" is still the current tip.

A GitHub source read establishes source content at that ref, not live runtime behavior. Preserve that distinction.

6. Phase 3 — Resolve the five technical errata items

Prepare a new version of the decision packet. Keep the original packet, specification, addendum, archive, manifest and raw outputs unchanged.

R1 — Evidence provenance

Make historical runtime observations, static facts, synthetic-fixture preconditions, negative controls, protocol-feasibility results and fixed-product acceptance evidence unmistakable.

Keep the three product-state labels unchanged. Fix FTS-A2 as necessary. Do not let a synthetic fixture result stand in for an actual historical-product run.

R2 — Atomicity and ambiguous commit outcomes

Use a correct transaction-outcome invariant:

- A failure before successful commit must leave the exact pre-migration state.
- If the commit outcome is ambiguous, reopening must reveal either a complete, verified pre-migration state or a complete, verified post-migration state, never a mixed state.
- Retry must converge safely to the verified post-migration state.
- A further migration invocation must be a no-op.

Retain the four pre-commit fault-injection checkpoints, tested by exception and hard process exit. Add a post-commit termination case and explain how ambiguous commit outcomes are handled or bounded.

Do not require rollback after a transaction that actually committed successfully.

R3 — Migration-state recognition

Specify the required disposition for each of these states:

- Legacy trigger and no accepted migration-completion record.
- Canonical trigger and accepted completion record.
- Canonical trigger but missing or untrusted completion record.
- Missing or unrecognized trigger or malformed migration metadata.
- A state where trigger and index consistency disagree.

Never treat a trigger-body substring alone as proof that rebuild and verification have completed.

Present both viable alternatives:

1. Prove that detection, trigger replacement, rebuild, verification and state transition are atomic across every supported product path.
2. Use a versioned migration-state marker, recorded in the same transaction after successful verification.

If proposing a marker, specify creation, versioning, missing/corrupt marker behavior and compatibility with new databases. A marker does not replace atomicity.

The choice remains a maintainer decision.

R4 — Actual product transaction boundary

Do not use "executescript()" after beginning the explicit migration transaction if the call can commit that pending transaction.

Design the new migration using explicit, ordered statements on the intended product connection. Verify transaction behavior under the actual Python and sqlite3 transaction configuration.

Distinguish initialization of brand-new databases from migration of existing databases. New databases must be created with the canonical delete trigger and the intended migration state; existing databases must undergo the defined migration and verification.

Do not claim that a standalone SQL probe proves the actual constructor path safe.

R5 — Concurrency contract

Require an explicit operating model:

- Exclusive migration with a defined and enforced method of excluding active writers; or
- Supported concurrent operation with tests for active readers and writers.

Define behavior for lock contention, the 20-second busy timeout, two or more processes opening the same database, reader connections with older WAL snapshots, restart and retry after injected faults.

The existing two-process, five-trial results remain protocol-feasibility evidence, not full product acceptance.

7. Phase 4 — Reconcile the acceptance matrix and decision ledger

Keep FTS-A1–A7 as packet-local IDs. Do not equate passing them with G4 identity-isolation closure.

Preserve and refine requirements for:

- RC regression tests and LD positive controls.
- Legacy fixtures F1–F5 and historical-schema fixtures.
- Index/content agreement, raw ghost row IDs and an independent reference.
- Fault injection, recovery and ambiguous commit outcome.
- Idempotency, repeated startup and concurrent migration.
- The declared SQLite version matrix and runtime identification through the Python application's "sqlite3.sqlite_version".
- Post-migration update/delete workload and rowid/token reuse.
- Documentation alignment and named ownership.

The plain FTS5 integrity check alone is insufficient where the packet requires external-content comparison. Verify use of "rank=1" and independent reference checks.

Keep physical erasure (PE / RD-10 / DEL-1–4) separate. Do not enable FTS5 "secure-delete", recommend VACUUM as an erasure guarantee, or claim that this batch erases data from WAL files, backups, archives, graph/vector stores or every other copy. Keep the unexplained secure-delete anomaly excluded from this batch's acceptance criteria.

Produce a maintainer decision ledger for D-1–D-8. Each item must have a recommendation if evidence supports one, its owner, current status, options, rationale and the exact evidence or approval still required. Do not make maintainer-owned choices on the maintainer's behalf.

8. Phase 5 — Produce and verify the new revision

Deliver a new, separately named proposed revision. Do not overwrite or silently amend the originals.

Expected deliverables:

1. A new proposed FTS decision packet/errata with a concise change log.
2. A revised evidence-label addendum only if the review demonstrates that changes are needed there.
3. An evidence audit report mapping each quoted figure and material claim to its exact evidence output and verification status.
4. A maintainer decision ledger with explicit OPEN items, owners to be assigned, choices and gating evidence.
5. A new SHA-256 manifest covering all files in the new delivery.
6. A fresh-extraction verification report showing manifest results, reproduction commands, numerical checks, failures and limitations.
7. A concise handoff stating what is ready for maintainer decision and what blocks the next milestone.

The manifest and audit report must not describe a check as passed if it was not executed. Preserve all original hashes and as-run evidence.

9. Scope and stop conditions

This task is documentation-only. Do not modify product source, product tests, CI allowlists, ADR decisions, freeze-blocking statuses or the historical report. Do not make a PR or push.

Stop and report a precise blocker if the archive is unavailable, figures fail independent derivation, the supported SQLite runtime policy cannot be established, the migration state cannot be unambiguously recognized, the product transaction behavior is not grounded in source, or the overlapping isolation work lacks an owner/sequence disposition.

Do not invent missing facts. Do not claim implementation authorization. Do not convert a proposed recommendation into an accepted decision.

10. Required final response

Report:

1. Which of the original artifacts were obtained, with hashes.
2. Whether the archive was freshly extracted and verified.
3. The number of numerical assertions independently reproduced, the number passed, and all failures or untested claims.
4. The most material technical corrections and their evidence.
5. New files created with hashes.
6. The remaining maintainer decisions, each explicitly "OPEN" where unresolved.
7. Any blockers to implementation planning.
8. Confirmation that product code was not changed, no PR was opened, and no implementation was authorized.

End with the unchanged status:

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
~~~~

## 3. Subsequent User Instructions / Corrections

After the prompt above the user sent **no further instruction, correction or scope change**; only the single word "continue" (2026-10-20 13:38, 18:29, 21:33; 2026-10-21 09:06, 17:43; 2026-10-22 08:37, 14:16; 2026-10-23 00:03 UTC). Nothing in those messages amends the prompt.

**Later instruction (2026-10-23 10:52 UTC): "update to repo, we'll continue in a fresh session".** This is the only later instruction that changes anything. Because the prompt (§2) said "Do not … push commits", the harness denied the first clone attempt and I asked which files and which branch. The user's answers (2026-10-24) were:
- What to push: **"Handoff + 4 report docs (Recommended)"** — option text shown to the user: "handoff.md at the repo root, plus the packet, addendum, audit report and ledger under a docs folder. Text only, about 145 KB; the zip and probe outputs stay out of the repo."
- Which branch: **"New docs branch from main (Recommended)"** — option text: "docs/g4-fts-errata-handoff-oct2026, created from the current main tip; documentation files only", with my stated limits "push only: no PR, no merge, nothing touching main or any product file".

Effect: the prompt's no-push constraint is lifted **only** for this documentation-only checkpoint branch. Every other prompt constraint stays (no product change, no PR, no merge, no implementation authorisation, no choice among D1/D2/D3 or the ledger items).

Standing constraints carried from earlier segments of this workstream (still in force; preserved as constraints, not as new scope):
- The user's preferences field contains a credential string. It was **not used**, is **not recorded here**, and repository access in this workstream was unauthenticated and read-only.
- Do not change the ADR-KERNEL-07 D-4 xfail, `ci.yml` or the allow-list; do not choose D1/D2/D3 (FZ-01/02/05); do not issue a freeze verdict.
- Immediately preceding task in the chain (already satisfied by the revision-1 packet, which this task audits): attachment `7e35531d-attachment.txt`, sha256 `e57321ffcb22bd8fc1bf9a9d13fdb33ad359a463ee46b8e1b1c55e8b9dfbe0d4`.

## 4. Goal, Scope & Success Criteria

### Goal
Establish what was delivered, what the evidence actually demonstrates and what remains unverified; reconcile the FTS decision packet with its evidence-label addendum; verify the technical claims at primary sources and repository history; produce a trustworthy, reproducible, maintainer-ready **proposed** errata revision and an explicit list of remaining decisions and verification gates.

### In Scope
Phases 0–5 of the prompt: input hashing and fresh extraction; reproduction and independent re-derivation of every quoted figure; evidence-model reconstruction; verification of FTS5 / VACUUM / Python 3.12 `sqlite3` wording and of repository history and current state; errata items R1–R5; acceptance-matrix and decision-ledger reconciliation; deliverables 1–7; the 8-point final response.

### Out of Scope (must not be changed)
Product source, product tests, CI allow-lists, ADR decisions, freeze-blocking statuses, the historical report, any FTS fix, physical-erasure change, authorization change or unrelated remediation; creating an implementation branch, opening a PR, pushing or merging; making any maintainer-owned choice; ratifying or accepting any requirement.

### Success Criteria
Every criterion of prompt §3 (Phase 0) executed or reported as blocked; evidence model applied consistently; R1–R5 resolved in a new separately named packet with a change log; the matrix and ledger reconciled with every maintainer choice left OPEN; a manifest, an audit report and a fresh-extraction verification report that do not describe an unexecuted check as passed; originals preserved byte-for-byte; the final response ends with the unchanged status line.

## 5. Requirement Ledger

| ID | Requirement (prompt ref.) | Status | Evidence | Notes |
|---|---|---|---|---|
| P0-1 | Hash the four originals; record name, sha256, size, provenance (§3) | VERIFIED | `inputs/INPUT_HASHES.txt`; audit report §1 | ZIP `79c6146c…d2721` (79,260 B); packet rev 1 `4d24d766…13ce3`; addendum rev 1 `14184571…3ffd`; spec `0bf41487…fa44` |
| P0-2 | Inspect archive listing before extraction (§3.1) | VERIFIED | audit §2 | 29 files, no absolute / `..` paths |
| P0-3 | Fresh isolated extraction (§3.2) | VERIFIED | audit §2; `a4/zx_fresh` | never extracted over earlier evidence |
| P0-4 | Read README and MANIFEST (§3.3) | VERIFIED | audit §2 | |
| P0-5 | Verify every manifest entry — claimed 28/28 (§3.4) | VERIFIED | `sha256sum -c`: 28/28 OK; 29 files = 28 + MANIFEST; no unlisted file | claim reproduced |
| P0-6 | Locate figure script, inputs, environment, as-run outputs (§3.5) | VERIFIED | `packet_numbers_check.py`; preserved `out/` | |
| P0-7 | Run documented reproduction; record commands, versions, exit codes, hashes (§3.6) | VERIFIED | audit §2; `out/repro/*` | identical except which racing process won, and timings |
| P0-8 | Independently re-derive every quoted number — claimed 72/72 (§3.7) | VERIFIED with 1 finding | `independent_derivation.py`: **385/387** (2 failures = one finding, AF-02: 50k-row duration is 0.41–0.50 s, not 0.41 s); `packet_numbers_check.py` re-run 72/72 (self-consistency only) | claim "72/72" reproduced as self-consistency, **not** as independence |
| P0-9 | Corrected ordering runs reproducible; mixed-case defect and as-run output preserved (§3.8) | VERIFIED | runs 2 and 3 byte-identical (`314a993a…`); `…run1_as_run_vocab_case_bug.json` untouched | |
| P0-10 | Integrity-probe output consistent with preserved original (§3.9) | VERIFIED | compare: identical | |
| P1-1 | Evidence model per claim/row; three labels; protocol-feasibility = purpose (§4) | IMPLEMENTED (ratification OPEN: D-6) | packet rev 2 §2; addendum rev 2; audit §4 | V1/V2 reclassified as test-satisfiability (they pass; a negative control must fail) |
| P1-2 | Fix FTS-A2: separate prepared-fixture initial state from operations through the unchanged implementation (§4, R1) | IMPLEMENTED | packet rev 2 §4.2; `out/fts_baseline_*` | fresh DB + API-only histories reach the ghost state 3/3; unchanged constructor repairs 0/7 prepared fixtures; API workload = raw-SQL result 7/7 |
| P1-3 | Terminology audit: baseline / fails-before / passes-after / negative control / verified / fixed product (§4) | IMPLEMENTED | addendum rev 2 §3 | "fails-before/passes-after" retired; "verified" reserved for executed checks |
| P2-1 | Verify FTS5, VACUUM and Python 3.12 sqlite3 docs at source; exact sections and URLs; no fetch-summary reliance (§5) | PARTIAL — VERIFIED at raw 3.45.1 docs and raw Python rst; **live sqlite.org pages not read raw** | `docs/raw_sqlite_docs_verification.md`; `out/rawdocs/rawdocs_check_run3.json` (11/11) | shell gets 403 from sqlite.org; wording for other SQLite versions UNTESTED (D-2) |
| P2-2 | Read-only repo inspection: triggers, `ke_au` migration, new-DB DDL, constructor, `executescript`, connection config, history, migration tests, freshness, doc conflicts (§5) | VERIFIED (STATIC; GitHub reads establish source at a ref, not runtime) | packet rev 2 §3; audit §2/§6 | tip `f13bfde`, 30 commits ahead; relevant files identical; `488129b` = PR #80 merge, an ancestor, not the tip |
| R1 | Evidence provenance (§6) | IMPLEMENTED | packet rev 2 §2, §4.2 | |
| R2 | Atomicity and ambiguous commit outcome; keep 4 pre-commit checkpoints (exception + hard exit); add post-commit case; no rollback after commit (§6) | IMPLEMENTED (feasibility evidence only) | `out/fts_commit_boundary_run1.json`: Part A 10/10; Part B 40 torn-WAL variants (39 pre, 1 post, 0 mixed; SIMULATED); Part C 250 SIGKILL trials (pre 237, post 13, mixed 0) | only 2 kills landed in the commit window; weakly sampled |
| R3 | Five migration-state dispositions; both alternatives; marker spec; choice is maintainer's (§6) | IMPLEMENTED; **choice OPEN (D-4, D-10)** | `out/fts_state_classifier_run1.json` (10 states × 2 backends); packet rev 2 §4.5, §5.3 | stranded state S3b and marker-invisible drift S5 both observed |
| R4 | No `executescript()` after BEGIN; explicit ordered statements on the product connection; new-DB vs existing-DB; standalone probe ≠ constructor path (§6) | IMPLEMENTED; **constructor path UNVERIFIED** | `out/fts_txn_boundary_run1.json` T1–T10 | `executescript()` after `BEGIN IMMEDIATE` commits first (T2) |
| R5 | Concurrency contract (§6) | IMPLEMENTED (feasibility only); **operating model OPEN (D-9)** | `out/fts_concurrency_run1.json` C1–C6 | contender crash, mixed old/new code, four-process end-to-end UNTESTED |
| P4-1 | FTS-A1–A7 packet-local; not G4 isolation closure (§7) | IMPLEMENTED | packet rev 2 §7 | |
| P4-2 | Preserve/refine RC/LD, F1–F5, rank=1 + independent reference, fault injection, idempotency, SQLite version matrix via `sqlite3.sqlite_version`, post-migration workload, docs alignment (§7) | IMPLEMENTED (as PROPOSED requirements) | packet rev 2 §7, §9 | SQLite minimum version OPEN (D-2) |
| P4-3 | Keep physical erasure separate; no secure-delete enabling; no VACUUM-as-erasure; secure-delete anomaly excluded (§7) | IMPLEMENTED | packet rev 2 §6.1; ledger D-5 | anomaly UNEXPLAINED |
| P4-4 | Decision ledger D-1–D-8 with recommendation where evidence supports, owner, status, options, rationale, required evidence (§7) | IMPLEMENTED (D-1…D-11; **all OPEN**) | `report/decision_ledger_1d813bd_OPEN.md` | owners left "maintainer / to be assigned" |
| P5-1 | New proposed packet/errata with change log (§8.1) | IMPLEMENTED | `report/g4_fts_correctness_batch_decision_packet_1d813bd_REV2_PROPOSED.md` (sha256 `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2`), change log C-1…C-12 | |
| P5-2 | Revised addendum if needed (§8.2) | IMPLEMENTED | `report/addendum_evidence_labels_REV2_PROPOSED.md` | needed: revision 1 mixed label and purpose |
| P5-3 | Evidence audit report mapping figures/claims to outputs and status (§8.3) | IMPLEMENTED | `report/evidence_audit_report_1d813bd.md` (AF-01…AF-14, assertion ledger) | |
| P5-4 | Decision ledger (§8.4) | IMPLEMENTED | as P4-4 | |
| P5-5 | New SHA-256 manifest of the delivery (§8.5) | VERIFIED | `MANIFEST.sha256` (86 entries) inside the zip; 86/86 OK on fresh extraction | |
| P5-6 | Fresh-extraction verification report (§8.6) | IMPLEMENTED | `fresh_extraction_verification_report.md` + log + script (beside the zip) | commit-boundary and concurrency probes NOT re-run there (stated) |
| P5-7 | Concise handoff (§8.7) | IMPLEMENTED | this file | |
| C-1 | Constraints: no product-code change, no PR, no implementation authorisation, originals byte-for-byte (§2, §9); no push **except** the user-authorised documentation checkpoint branch (see §3) | VERIFIED | read worktree clean at `1d813bd` before/after every probe run (`repo_unchanged: true`); originals never edited; `git diff --stat origin/main eca2b96521fba8cf792ea16a58be997e4f949356` = 4 added files, all under `docs/studies/g4-fts-errata-oct2026/`; remote `main` still `f13bfde…` after the push | |
| T-1 | Update the repo so a fresh session can continue (user, 2026-10-23); scope and branch per §3 | VERIFIED for the transfer commit | `eca2b96521fba8cf792ea16a58be997e4f949356` pushed to `docs/g4-fts-errata-handoff-oct2026`; `git ls-remote` returned the same hash; handoff commit follows (§7) | the zip, probe outputs and verification report stay outside the repo by the user's choice |
| C-2 | Final response items 1–8 and the exact closing status line (§10) | given in the session's final reply (not part of this file) | | |

## 6. Current Verified State

**VERIFIED (executed)**
- Original ZIP: 28/28 manifest entries OK on fresh extraction; "72/72" reproduced as self-consistency only; independent derivation 385/387, the two failures being the same 50k-row duration finding (0.410 s and 0.501 s measured; packet said 0.41 s).
- Revision-1 probes reproduce in fresh disposable directories (identical except which of two racing processes performed the migration, and timings); the LD/RC/PE matrix reproduces (LD 4 PASS; RC 4 PASS / 5 FAIL on the shipped trigger; PE 5 FAIL on shipped).
- The unchanged product (`SqliteStorage` via its own API, fresh database, 3 seeded 150-operation histories) reaches the stale-posting ("ghost") state from the first delete; the canonical-trigger control stays clean 3/3; the unchanged constructor repairs none of the 7 prepared legacy fixtures; plain `integrity-check` and `PRAGMA integrity_check` pass while `rank=1` fails (source: `fts5_storage.c:964-966`, `fts5_main.c:2978`).
- `executescript()` after `BEGIN IMMEDIATE` commits the pending transaction first (product connection: legacy transaction control, WAL, busy timeout 20 s).
- Probe-artefact protocol (explicit statements, `BEGIN IMMEDIATE`, classify inside the lock, `rank=1` verify before commit): pre-commit failures leave the exact pre-state; post-commit leaves the verified post-state; 0 mixed in 300 observations; exactly one migrator in 15/15 races; lock hold 0.49–0.57 s at 50k rows.
- FTS5/VACUUM documentation wording at the raw HTML of the SQLite 3.45.1 docs (11/11 passages); Python `executescript` behaviour at raw `sqlite3.rst` (tag `v3.12.3` and `3.12` branch tip: identical relevant text).
- Final bundle: fresh extraction 86/86; rev-2 transcription check 83/83; every re-executed probe identical to the bundled output except timing keys.

**IMPLEMENTED BUT NOT VERIFIED**: none of the documents is ratified; revision 2's labels and corrections are PROPOSED.

**PROPOSED**: errata packet rev 2; addendum rev 2; the migration protocol (a probe artefact, not a design of record); every ledger recommendation.

**DEFERRED**: all implementation; D-1…D-11.

**BLOCKED** (for implementation planning, not for the documents): see §15.

**UNKNOWN / UNTESTED**: real databases (size, legacy state, whether ghosts exist); other SQLite versions, platforms, Python versions; constructor-path integration; four-process end-to-end; contender crash; mixed old/new code; power loss; the unexplained secure-delete `integrity-check` anomaly; live sqlite.org page wording.

Active architectural constraints: LAW 1–5 and the 4-process runtime model of `PROJECT_INSTRUCTIONS.md`; the migration must be atomic and replayable; physical erasure stays a separate requirement.

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1`
- Remote: `https://github.com/1h0lde4/ocbrain-v4.1` (the session's attached-repository access was used; no credential from the user's preferences was used or recorded)
- Branch: `docs/g4-fts-errata-handoff-oct2026` (new; documentation-only; not merged; no PR opened)
- Base branch: `main` @ `f13bfdefcdd197ed1f966de0b1f93037a4168af4` (confirmed at clone time and again before the push; remote `main` re-read after the push and unchanged). The study's evidence baseline is `1d813bdae320bf34110c29836c81dc901c601c9b`; the branch is based on the main tip, **not** on the baseline.
- HEAD before the handoff commit: `eca2b96521fba8cf792ea16a58be997e4f949356`
- Transfer commit (the implementation checkpoint): `eca2b96521fba8cf792ea16a58be997e4f949356` — adds the four report documents under `docs/studies/g4-fts-errata-oct2026/`; pushed; `git ls-remote origin refs/heads/docs/g4-fts-errata-handoff-oct2026` returned the same hash
- Handoff commit: the commit that adds this file (`git log --oneline -1 -- handoff.md` on the branch). Its own hash cannot be stored inside the file.
- Parent commit of the handoff commit: `eca2b96521fba8cf792ea16a58be997e4f949356`
- Working tree status at the transfer commit: clean
- Relevant untracked / ignored files: none
- Submodules / nested repositories: none touched
- Remote push status: transfer commit pushed (exit 0, new branch only). The handoff commit is pushed immediately after this file is written; the resuming session must verify it (§18).
- Remote verification status: transfer commit verified; `main` unchanged; handoff commit to be re-verified by the resuming session

## 8. Active Files / Modified Files / Artifacts

No product file was modified, added or deleted.

**In the repository (branch `docs/g4-fts-errata-handoff-oct2026`):**

| Path | sha256 | Commit |
|---|---|---|
| `docs/studies/g4-fts-errata-oct2026/g4_fts_correctness_batch_decision_packet_1d813bd_REV2_PROPOSED.md` | `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2` | `eca2b96521fba8cf792ea16a58be997e4f949356` |
| `docs/studies/g4-fts-errata-oct2026/addendum_evidence_labels_REV2_PROPOSED.md` | `2cf514539e245e5941cda3b5a962f1f0d7b6478f723a9980c2f85c092c4fc920` | `eca2b96521fba8cf792ea16a58be997e4f949356` |
| `docs/studies/g4-fts-errata-oct2026/evidence_audit_report_1d813bd.md` | `2dc09f0d1d89d2613d1dd56d3e0a34753492319efd1018c7ef295b0faad028af` | `eca2b96521fba8cf792ea16a58be997e4f949356` |
| `docs/studies/g4-fts-errata-oct2026/decision_ledger_1d813bd_OPEN.md` | `ed188b17d1b9f328a9ffc6c048a74b18c67c50507c99c22b3edfbf5e221cf719` | `eca2b96521fba8cf792ea16a58be997e4f949356` |
| `handoff.md` (this file) | not stable (a file cannot contain its own hash) | handoff commit |

**NOT in the repository — by the user's choice (§3), non-repository state:** the evidence bundle `fts_decision_packet_errata_evidence_1d813bd.zip` (sha256 `e6910c0cc6eb1acefaaf369ce46599856a169228a3060b6492687c8fd70b9c3d`, 255,601 bytes, 86 manifest entries: README, manifest, probe scripts, probe outputs, raw-docs excerpts, input hashes) and the fresh-extraction verification report (sha256 `dde7edab9d9b735b6e3b589f87d9344dffd64e6eae6475827748a6dacd4c48a2`), its log (`5b47184b…0815`) and script (`8d6b4145…8a0b`). They were delivered to the user as files. **The four documents above cite paths inside that bundle (`README.md`, `out/…`, `scripts/…`, `docs/…`); those paths do not resolve inside the repository.** If a check needs the bundle, the user must supply it; verify it against the hash above.

**Session-local provenance (ephemeral; not durable):** the deliverables were produced under `/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a4/`:

| Artifact | Path | sha256 | Why it matters |
|---|---|---|---|
| Delivery bundle | `final/fts_decision_packet_errata_evidence_1d813bd.zip` | `e6910c0cc6eb1acefaaf369ce46599856a169228a3060b6492687c8fd70b9c3d` | everything below the `report/`, `docs/`, `scripts/`, `out/`, `inputs/` roots, with `README.md` and `MANIFEST.sha256` (86 entries) |
| Packet rev 2 | `b4/report/g4_fts_correctness_batch_decision_packet_1d813bd_REV2_PROPOSED.md` | `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2` | the proposed errata |
| Addendum rev 2 | `b4/report/addendum_evidence_labels_REV2_PROPOSED.md` | `2cf51453…c920` | evidence-label model |
| Audit report | `b4/report/evidence_audit_report_1d813bd.md` | `2dc09f0d…28af` | figure/claim mapping, AF-01…AF-14 |
| Decision ledger | `b4/report/decision_ledger_1d813bd_OPEN.md` | `ed188b17…f719` | D-1…D-11, all OPEN |
| Verification report (outside zip) | `final/fresh_extraction_verification_report.md` + `fresh_extraction_verification_log.txt` + `fresh_extraction_verify_script.sh` | see delivery listing | fresh-extraction results and what was not re-run |
| This handoff | `final/handoff.md` | see delivery listing | |
| Probe scripts and outputs | inside the zip (`scripts/`, `out/`) | `MANIFEST.sha256` | reproduction |

External resources required for full reproduction (not in the repository): the original delivered ZIP (hash in `inputs/INPUT_HASHES.txt`; `a4/zx_fresh` is its extraction), a detached read-only worktree at `1d813bd` (`a4/wt_audit`; reproducible from the repository), and the Ubuntu package `sqlite3-doc_3.45.1-1ubuntu2.8_all.deb` (sha256 `9a97bea1852d867a8d19ee061b97e71c5ab53e7edd09ed7cb30f8f813109f699`; reproducible from the Ubuntu pool). Superseded scratch builds (`a4/deliver/…zip`, `a4/prebuild2_superseded.zip`, `a4/MANIFEST_prebuild*_superseded.sha256`, `a4/verify`, `a4/verify2`) were never delivered.

## 9. Changes Made

- **Product:** none.
- **Repository (documentation only):** commit `eca2b96521fba8cf792ea16a58be997e4f949356` adds four documents under `docs/studies/g4-fts-errata-oct2026/`; the handoff commit adds `handoff.md` at the repo root. No other file.
- **Documents (new, PROPOSED):** the four report files above plus README, manifest, scripts and outputs. Originals untouched.
- **Most material corrections to revision 1** (evidence in the audit report §5 and packet §C):
  1. AF-01 / C-1: "7/7 legacy fixtures fail rank=1" described *prepared* states; now separated from behaviour of the unchanged product (fresh-DB API histories reach the ghost state 3/3; the unchanged constructor repairs 0/7).
  2. AF-02 / C-7: 50k-row duration "0.41 s (two runs)" → 0.41–0.50 s; the original check script could not detect this (loose bounds).
  3. AF-06 / C-2: atomicity invariant restated to cover ambiguous commit outcomes; post-commit case added; no rollback required after commit.
  4. C-4 / R4: `executescript()` after `BEGIN` commits first; explicit ordered statements required; standalone SQL probe does not prove the constructor path.
  5. C-3 / R3: ten migration states observed; trigger-body check is blind to the stranded state; a marker is blind to drift after the marker; `rank=1` verification inside the transaction catches both.
  6. C-5 / R5: concurrency contract grounded as feasibility evidence.
  7. AF-05 / C-6: V1/V2 are test-satisfiability diagnostics, not negative controls; "fails-before/passes-after" retired.
  8. AF-03 / C-9: five commits touch `sqlite_storage.py` under full history (default `git log` shows three).
  9. AF-14: DEBT-042 (`_fts_escape`, same file) registered on `main` after the baseline was missing from the overlap list.
  10. AF-10: FTS5/VACUUM wording now verified at the raw 3.45.1 docs; the fetch tool's section numbers for the live page differ (cite heading ids).
  11. C-8 / AF-04: observed VACUUM rowid stability is explained by the existence of an index on the table (SQLite 3.45.1 `src/insert.c:3050-3063`) and fails for an index-less table.
- **Interfaces / schema / governance / security:** none changed. The marker table `ocbrain_schema_migrations` and the migration protocol exist only inside probe artefacts.

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Evidence | Reopen condition |
|---|---|---|---|---|---|
| DEC-1 | Keep the three product-state labels; treat protocol-feasibility as purpose | PROPOSED (D-6 ratifies) | prompt §2/§4 | addendum rev 2 | maintainer prefers old wording |
| DEC-2 | Classify V1/V2 as test-satisfiability (not negative controls) | PROPOSED (D-6) | definition: a negative control must fail | RC tests pass on V1/V2 | maintainer keeps old label |
| DEC-3 | Verification model: plain check is not acceptance; `rank=1` plus independent reference | PROPOSED | source + runtime | `fts5_storage.c:964-966`, `fts5_main.c:2978` | a verified contradiction |
| DEC-4 | Both migration-state alternatives presented; no choice made | OPEN (D-4) | prompt R3 | S3b, S5 observations | maintainer decides |
| DEC-5 | Physical erasure stays separate; secure-delete not enabled; anomaly excluded | PROPOSED (D-5) | prompt §7 | PE fails on V1; FTS5 docs state old entries remain until merges | RD-10 policy |
| DEC-6 | Documentation-only; no probe artefact is treated as product code | settled for this task | prompt §9 | | user authorises implementation |
| DEC-7 | Hash-circularity avoided: verification report and handoff delivered beside the zip | settled | design | | |

Alternatives rejected: calling V1/V2 "negative-control-style" (mixes label and purpose); using fetch-tool summaries as wording authority; recording unexecuted checks as passed.

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| Original bundle | listing, manifest, README, scripts, outputs | 28/28; reproduces | audit §2 | bundle changes |
| FTS trigger behaviour | shipped `ke_ad`, canonical form, V1/V2/V3 variants | shipped `ke_ad` leaves stale postings; canonical clean | contract matrix, ordering/integrity runs | trigger changes |
| Unchanged product path | constructor, API workloads, 7 fixtures, fresh histories | ghost state reached by ordinary use; constructor repairs nothing | `out/fts_baseline_*` | `sqlite_storage.py` changes |
| Source of `integrity-check` | `fts5_storage.c`, `fts5_main.c` @3.45.1 | `rank=1` is the only external-content comparison; `PRAGMA integrity_check` passes 0 | `docs/source_excerpts_raw.txt` | other SQLite versions |
| VACUUM rowids | docs, `insert.c`, controls | preserved only because the table has an index | `fts_vacuum_rowid_control_run1.json` | other versions / schema change |
| Python transaction semantics | `sqlite3.rst` raw @ tag and tip; product `_connect()` | legacy control; `executescript` commits first | `fts_txn_boundary_run1.json` | Python version change |
| Commit-boundary | exceptions, hard exits, torn WAL, SIGKILL | 0 mixed | `fts_commit_boundary_run1.json` | any change to the protocol |
| Concurrency | races, timeouts, snapshots, writer traffic | one migrator; contender waits then fails with `database is locked` | `fts_concurrency_run1.json` | operating model chosen |
| Repo history/freshness | full history of `sqlite_storage.py`, tip `f13bfde` | five commits; relevant files identical to baseline | packet §3 | main moves on in these files |
| Docs conflicts | `SESSION4C_REPORT.md:142`; REM-012 vs `ARCHITECTURE_HARDENING_SESSION_REPORT.md:170` | present at baseline and tip | audit §2 | docs edited |
| Not investigated | real databases; other SQLite builds; power loss; four-process end-to-end; constructor-path behaviour under the change; live sqlite.org pages | — | — | maintainer supplies / authorises |

## 12. Failed Attempts / Dead Ends

| Approach | Result | Cause | Retry? |
|---|---|---|---|
| WebFetch summaries as the wording authority for FTS5/VACUUM | wording obtained but unverifiable; section numbers differed from the 3.45.1 docs | summarising model; shell 403 from sqlite.org | no — use raw docs (done) |
| First commit-boundary run | interrupted by container restarts, no output | long run | resumed twice from a progress file (disclosed) |
| `rev2_numbers_check.py` run 1 | 80/83 | checker defects (two text patterns, one key name) | corrected; runs 2–4 pass; run 1 preserved |
| `rawdocs_extract.py` runs 1–2 | heading attribution wrong | anchors read from `<a>` tags / heuristic | corrected in run 3; presence results identical in all |
| Tree-digest comparison across worktrees | digests differ (`624b0e3f…` vs `46cacae3…`) | harness hashes the `.git` pointer file | explained; 544 other files identical |
| Packet draft said PE fails "4 of 5" on shipped | wrong | miscount | corrected to 5/5 |
| First clone of the repo (2026-10-24) | denied by the harness: the prompt said no push and the user's instruction named neither files nor branch | scope unspecified | asked; retried after the user's explicit answer (§3) |
| Two scratch builds of the zip | superseded before delivery | later additions (raw-docs evidence; timing note) | not delivered |
| Revision-1 ordering run 1 (earlier segment) | mixed-case vocabulary defect | harness | preserved as run; runs 2/3 corrected |

## 13. Verification Evidence

| Check | Command (abridged) | Result |
|---|---|---|
| Original ZIP manifest | `sha256sum -c MANIFEST.sha256` on a fresh extraction | 28/28 OK |
| Rev-1 figure script | `packet_numbers_check.py` | 72/72 (self-consistency) |
| Independent derivation | `independent_derivation.py` | 385/387; 2 failed = AF-02 |
| Rev-2 transcription check | `rev2_numbers_check.py` | run 1 80/83 (checker defects); runs 2, 3, 4 83/83 |
| Raw-docs passage check | `rawdocs_extract.py` | 11/11 present |
| Final zip fresh extraction | script `fresh_extraction_verify_script.sh` | 86/86 OK; no unlisted/missing; 83/83; 72/72; 11/11; five probes re-executed: identical except timing keys (state-classifier cost) |
| Worktree unchanged | `git rev-parse HEAD`; `git status --porcelain` | `1d813bd…`; 0 lines before and after |
| Not executed in the final verification | commit-boundary probe, concurrency probe, independent derivation, revision-1 probes | stated in the verification report §2 |

Failures and limits: AF-02; checker defects above; timing variability (classifier cost 0.029–0.061 s at 10k rows over four executions).

## 14. Environment / Tooling Assumptions

Python 3.12.3 (`python3.12 -I`), SQLite 3.45.1 (source id `2024-01-30 16:01:20 e876e51a…`), git 2.43.0, Ubuntu 24.04.5, Linux 6.18.x x86_64, 2 vCPU, 8 GB; `gpgv` with `/usr/share/keyrings/ubuntu-archive-keyring.gpg`; no network access from the shell to sqlite.org (HTTP 403). No secrets required or stored. Reads were unauthenticated; the one push used the session's attached-repository access (no credential from the user's preferences). Git identity in the clone: `Claude <noreply@anthropic.com>`. Probes need a disposable directory (basename `disposable_probe_*`, ≥4 path components, not inside a work tree) and a detached worktree at `1d813bd`.

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Options | Disposition | May work continue? |
|---|---|---|---|---|
| Minimum supported SQLite version(s) (D-2) | only 3.45.1 tested; secure-delete option from 3.42.0; VACUUM rowid behaviour is an implementation detail | declare a floor / bundle a pinned SQLite / test a list | OPEN — maintainer | planning blocked |
| Migration-state mechanism and policy for unrecognised/malformed/newer states (D-4, D-10) | S3b, S5 observed | atomicity-only vs versioned marker | OPEN — maintainer | planning blocked |
| Constructor integration and where the migration runs in the 4-process runtime (G-4, G-9) | `_init_sync` uses `executescript`; probe on `_connect()` only | explicit startup step vs constructor | UNVERIFIED — needs implementation authorisation to test | planning blocked |
| Busy-timeout exhaustion behaviour / concurrency operating model (D-9) | contender fails with `database is locked` after 20 s | fail startup / bounded retry / single designated migrator | OPEN | planning blocked |
| Real database sizes and legacy states (D-7, G-5) | extrapolated 20 s lock hold near 1.9 M rows (EXTRAPOLATED) | maintainer supplies copies or runs the read-only check | UNKNOWN | optional; G-5 cannot close without it |
| Overlapping work: I-3a vs I-4 in `sqlite_storage.py` / `unified_memory.py`; DEBT-042 (D-11, G-7, G-10) | spec §12; `KNOWN_ISSUES.md` @ `f13bfde` | FTS first / I-3a first / coordinated | OPEN — no owner/sequence | planning blocked |
| Live sqlite.org wording and other versions' wording | raw only for 3.45.1 | re-read per declared version | UNVERIFIED | gate for ratifying wording-dependent claims |
| Secure-delete `integrity-check` anomaly | characterised, unexplained | none | UNKNOWN; excluded from acceptance | yes |
| Power loss; contender crash; mixed old/new code; four-process end-to-end | not tested | — | UNTESTED | yes, for the documents |
| The four committed documents cite bundle paths that are not in the repo | by the user's choice (§3) | re-supply the bundle when needed | ACCEPTED by the user (scope choice); doc cross-references unresolved inside the repo | yes |
| Pull the batch forward / keep / defer (D-1); RD-13 classification (D-3); label ratification (D-6); doc-correction owner (D-8) | ledger | — | OPEN — maintainer | yes |

The task's own stop conditions (prompt §9): archive unavailable — no; figures fail derivation — one corrected range (AF-02); supported SQLite runtime policy cannot be established — **yes, it is a decision (D-2), so implementation planning is blocked, the documents are not**; migration state cannot be recognised — it can (exact normalised body plus marker, `rank=1`); product transaction behaviour not grounded — grounded in source and observation; overlapping isolation work lacks an owner/sequence — **yes (D-11)**.

## 16. Relevant Information / References

- Governing documents: `PROJECT_INSTRUCTIONS.md` (sections 0, 14.4, 16.4–16.5, 18.4.8, 24); PROPOSED spec `abe17d13-g4_batch1_isolation_contract_spec_PROPOSED.md` (sha256 `0bf4148775ae6e20456327cb6009b42b9e6e8fc8b350a0acb4115a0ec653fa44`; §12 rows I-3a/I-4; RD-10, RD-13; DEL-1…4; INV-17; RM-22).
- Repository anchors (baseline): `core/memory/backends/sqlite_storage.py` (trigger DDL, `_init_sync`, `_connect`), `tests/test_session4c_architecture.py:515-578` (`ke_au` migration test only), `docs/reports/SESSION4C_REPORT.md:142`, `docs/reports/context-compiler-remediation-register.md:75`, `docs/reports/ARCHITECTURE_HARDENING_SESSION_REPORT.md:170`, `KNOWN_ISSUES.md` @ tip (DEBT-042).
- Read-only check the maintainer **may** run on a **copy** of a real database, in a rolled-back transaction: `INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rank) VALUES('integrity-check', 1);` (an error = disagreement).
- Docs: `https://www.sqlite.org/fts5.html` (`#external_content_tables`, `#the_delete_command`, `#the_integrity_check_command`, `#the_rebuild_command`, `#the_secure_delete_configuration_option`), `https://www.sqlite.org/lang_vacuum.html` (`#how_vacuum_works`), `https://docs.python.org/3.12/library/sqlite3.html`.
- Cautions: the harness tree digest is worktree-path dependent; default `git log -- path` hides two commits of `sqlite_storage.py`; the file is CRLF; probe artefacts are not product code.
- **Related documents and earlier revision (provenance only; no authority is conferred or changed by this entry).**
  - *Earlier revision of this handoff.* A first version of this file was written on 2026-10-23 as a file-only handoff and delivered as a file. Its sha256 is `da162e71d6bd0b92650134eceb6af1ecfa430484ac08b179d7aaa48a97fa716d` (502 lines; the same 19 level-2 headings as this file), as computed from the session scratch copy and as recorded in the REV3 branch (`docs/reports/g4-fts-correctness/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` line 24; `NEXT_SESSION_PROMPT_REV3.md` line 12, where it is called `handoff(1).md`). Whether the user-side attachment is byte-identical to that scratch copy has not been independently established.
  - *Limited supersession, transfer-status statements only.* The earlier revision states "TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED" (its metadata line and §19) and "the repository contains no work of this workstream" (its §19); its §7 records no branch, no transfer commit and no push; its §18 step 3 tells a resumer not to look for a branch or commit. Those statements described the state before this branch existed. For *repository state* they are replaced by §7, §18 and §19 of this file. Nothing else in the earlier revision is replaced: its verbatim original prompt, ledgers, investigation record, failed attempts and verification evidence remain a valid historical record.
  - *Parallel draft.* Branch `docs/g4-fts-correctness-handoff-rev3-oct2026` (commit `2dd2e7bb05db949a6156266cfa3430c58de09922`, committed 2026-10-23T10:30:25Z) and draft PR #90 hold a separate REV3 documentation set, created before this checkpoint. That set was not reviewed in the session that first wrote this file; a later audit session compared it with this REV2 set (evidence outside this repository). This file does not select it, supersede it or depend on it.
  - *Effect on this file's own checks.* This entry was added after the handoff commit (`51564e34c18e5cc908cf517000ebc9bd41eaf194`). The branch therefore holds two commits after the transfer commit `eca2b96521fba8cf792ea16a58be997e4f949356`: `51564e34…`, then the commit that adds this entry. The "exactly one later commit" of §18 step 2 and the `git log --oneline -1 -- handoff.md` of §7 refer to `51564e34…`; a branch tip that differs from it only for this reason does not make the transfer INCOMPLETE.
  - *Not decided by this entry:* which document is the entry point for a future session; the authority of either ledger; any of D-1…D-11; G4–G8 status; freeze readiness; any implementation.

## 17. Next Steps

1. **Maintainer:** read the packet (`REV2`) and ledger; decide D-1…D-11 (each is OPEN); verification: record each decision in the ledger or an ADR. Prerequisite: none.
2. **Maintainer (optional):** supply anonymised database copies or run the read-only `rank=1` check (D-7). Expected: ghost presence and sizes become known; G-5 can then close.
3. **Maintainer:** declare the SQLite floor and how the product obtains SQLite (D-2); then re-read FTS5/VACUUM wording at the live pages for each declared version; verification: re-run `rawdocs_extract.py` against that version's docs.
4. **Maintainer:** choose the migration-state alternative and the policy for unrecognised/malformed/newer states (D-4, D-10); choose the concurrency model (D-9); assign owner and sequence for I-3a / I-4 / DEBT-042 (D-11).
5. **Only after 1–4 and an explicit implementation authorisation:** plan a separately verifiable batch; the packet §9 lists the required tests (constructor-path tests, four-process end-to-end, per-version matrix, fault injection including post-commit, idempotency, concurrent open, post-migration workload). Nothing in this handoff authorises it.
6. **Documentation owners (D-8):** correct `SESSION4C_REPORT.md:142` and reconcile REM-012; none edited here.

## 18. Resume Instructions

Follow `PROJECT_INSTRUCTIONS.md` §18.4.9. The handoff is a transfer record, not an authority.

1. `git fetch origin`; check out `docs/g4-fts-errata-handoff-oct2026`; confirm `handoff.md` is at the repo root and read it completely.
2. Verify the transfer commit is present and unchanged: `git cat-file -t eca2b96521fba8cf792ea16a58be997e4f949356` and `git ls-remote origin refs/heads/docs/g4-fts-errata-handoff-oct2026` (the branch must contain it; it should contain exactly one later commit, the handoff commit, whose parent is `eca2b96521fba8cf792ea16a58be997e4f949356`). If the branch tip is not the handoff commit or the handoff file is missing on the remote, **the transfer is INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED**: say so before doing anything else.
3. Verify scope: `git diff --stat $(git merge-base origin/main HEAD) HEAD` must list only `handoff.md` and the four files under `docs/studies/g4-fts-errata-oct2026/`. Any other file is an unexpected change to investigate.
4. Verify the four documents' sha256 against §8.
5. Check whether `origin/main` has moved since `f13bfde…` in `core/memory/backends/sqlite_storage.py`, `core/memory/knowledge_entry.py` or `tests/test_session4c_architecture.py` (they were byte-identical to the evidence baseline when checked). If they changed, re-verify the "current tip" statements in packet §3 before relying on them.
6. Do not look for the evidence bundle in the repo; ask the user for it only if a check requires it (hash in §8).
7. Do not reopen settled items (§10) or repeat investigations (§11) unless the stated condition occurs.
8. Begin from the first uncompleted step in §17 (a maintainer decision). Nothing in this file authorises implementation, a PR, a merge, or any choice among the ledger items.

## 19. Transfer Status

**TRANSFER READY** — for a documentation-only transfer, with the non-repository state below documented and **explicitly accepted by the user**.

Conditions of `PROJECT_INSTRUCTIONS.md` §18.4.8.9, as they apply:
- Original task preserved verbatim (§2); later instructions and the user's approvals recorded (§3); requirement, decision and investigation ledgers (§5, §10, §11); failed attempts (§12); verification evidence (§13); exact next action (§17, §18).
- Implementation checkpoint committed and pushed: `eca2b96521fba8cf792ea16a58be997e4f949356` on `docs/g4-fts-errata-handoff-oct2026`; remote hash verified equal; remote `main` verified unchanged.
- Handoff committed and pushed as the next commit on the same branch (its own hash cannot be recorded here; verification procedure in §18 step 2).
- Non-repository state: the evidence bundle and the verification report/log/script (§8). The user chose to keep them out of the repository when offered the alternative of pushing the full bundle (option text in §3). The documents' cross-references into the bundle therefore do not resolve in the repo; this is a known, accepted limitation, not a defect to repair silently.
- This is a checkpoint, not a completion claim: nothing is merged, ratified or accepted.

If step 2 of §18 fails, treat the status as **TRANSFER INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED**.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
