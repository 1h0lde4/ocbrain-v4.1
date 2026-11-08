# OCBrain G4 FTS — Artifact Authentication, Documentation Authority and Handoff Reconciliation: report

**Task prompt:** `76f58f1e-attachment.txt` ("OCBrain G4 FTS — Artifact Authentication, Documentation Authority, and Handoff Reconciliation").
**Run:** 2026-10-24 15:56 UTC to 2026-10-25 00:13 UTC (draft); independent review and corrections on 2026-10-26 (evidence F03, G01, G02; last command finished 21:10 UTC). All times in this report are UTC. The harness labels the user's zone "Africa/Casablanca" with offset +00:00; that label was not independently verified, and no time in this report depends on it.
**Repository:** `1h0lde4/ocbrain-v4.1`, local clone `/home/claude/ocbrain-v4.1` (shallow), on branch `docs/g4-fts-errata-handoff-oct2026` at `51564e34c18e5cc908cf517000ebc9bd41eaf194`.
**Statuses (unchanged by this report):** G4 **OPEN · High · freeze-blocking**. G5–G8 **HELD**. Freeze readiness **NOT DECLARED**. No implementation is authorized.

Labels used below: **[OBSERVED]** a result I produced in this run (evidence ID given); **[REPORTED]** what a document or earlier session says; **[DERIVED]** a conclusion from observations; **[RECOMMENDATION]** advice, not authority. Evidence IDs refer to the files in `evidence/` (index in §3).

---

## 1. Executive disposition

**Overall result: BLOCKED — partial completion.** Two mandatory gates are BLOCKED because the REV3 ZIP is not available to this session: original-ZIP authentication and archive integrity of that ZIP. Everything that does not depend on it was completed. Nothing in the repository was changed.

Most consequential findings:

1. **The REV3 ZIP cannot be authenticated here.** No file with its name, its size (254,581 bytes) or "REV3 / D2_D5 / FETCH_HEADER" in its name exists anywhere in this container, the attachment directories or the delivery directory (B01–B03). Both recorded digests are therefore preserved, and neither is selected.
2. **The digest conflict is real and lives inside the REV3 branch itself** [OBSERVED, B04]. Value A (`…0893c336…`) appears in three files: `IMPLEMENTATION_ROADMAP.md` line 2, the continuation line 16 and the next-session prompt line 16. Value B (`…0893f336…`) appears once, in the verification report line 4. They differ only at zero-based offset 23 (`c` against `f`). Repetition across files is not evidence; only hashing the actual ZIP resolves it.
3. **The 83/83 transcription check was freshly re-run on the exact packet bytes in the repository.** The input was the packet at commit `51564e3`, sha256 `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2`. Result 83/83, exit 0, twice (C04, C05). This establishes the transcription of the packet's figures against the REV2 bundle's raw outputs and two protocol-run files carried over from the revision-1 bundle (§5(3)). It does not establish the correctness of those outputs, and it says nothing about the REV3 ZIP.
4. **The two handoffs are two revisions of one document** [OBSERVED, D01–D03]: the same 19 level-2 headings, 13 hunks, 87 changed lines, both embedding the original task prompt byte-for-byte (E07). The older one says "TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED"; the repository one says "TRANSFER READY". The repository handoff does not mention the older revision's hash, the REV3 branch or PR #90. REV3's prompt already labels the older transfer-status paragraph historical (line 12).
5. **There are two competing entry points for a future session and no user decision between them.** The repository `handoff.md` §18 and REV3's `NEXT_SESSION_PROMPT_REV3.md` plus a sentence added to `IMPLEMENTATION_ROADMAP.md` each direct a fresh session. Neither refers to the other. The REV3 roadmap sentence ("Begin the next session with the G4 REV3 continuation…") is authority-bearing wording inside draft PR #90. I made no selection.
6. **A premise in the task text is not supported as worded.** §9 says rank=1 "was run on a local copy" for D-7. No document records `rank=1` being run on a copy of a real database. The only copies recorded are byte copies of generated, disposable fixtures (packet line 130). Every document says real databases are UNKNOWN and none was examined; the `rank=1` check on a real copy is a procedure the maintainer *may* run (E06; packet lines 351, 362). The task's wording resembles a proposal in an attached review (`7af26dc9`, D-7: use a local copy for the read-only `rank=1` check), which is a proposal, not a recorded run. The disposition of D-7 is unaffected: it stays OPEN and optional.
7. **The overlap risk is unresolved, not cleared.** At 2026-10-25 00:06 UTC (A06, F01) and again at 2026-10-26 21:09 UTC (F03; 16 open PRs, now including #92 and without #29) none of the open PRs changes `sqlite_storage.py`, `unified_memory.py`, `knowledge_entry.py` or anything under `core/memory/`. DEBT-042 is still OPEN on `main` (`KNOWN_ISSUES.md` line 56). No branch name suggests DEBT-042 or I-3a work. This is a path-and-name scan, not an inspection of every branch.
8. **Disclosure.** The first 83/83 re-run (C04) executed a script extracted from my own REV2 zip. The task says not to execute anything extracted from an archive, and also (§6.2) allows re-running the original checker. I repeated the run from the pre-packaging source copy (C05); the two scripts are byte-identical (sha256 `730ae766abe0bb9c1712e15d732c0f97c126efa0cad4274d167618da3a53a315`) and the two outputs are byte-identical. Treat C05 as the compliant run.

---

## 2. Live-state baseline [OBSERVED]

| Item | Value | Evidence |
|---|---|---|
| Time of inventory | 2026-10-24T15:56:45Z (re-checks 2026-10-25T00:06:41Z and 2026-10-26T21:09Z); user zone as labelled by the harness: Africa/Casablanca, +00:00 (label unverified) | A01, F01, F03 |
| Repository | `https://github.com/1h0lde4/ocbrain-v4.1`; root `/home/claude/ocbrain-v4.1`; shallow clone; git identity `Claude <noreply@anthropic.com>` | A01 |
| Branch / HEAD | `docs/g4-fts-errata-handoff-oct2026` / `51564e34c18e5cc908cf517000ebc9bd41eaf194` | A01, F01 |
| Working tree | 0 changed, 0 untracked, 0 ignored, 0 staged, 0 stash entries — at the start, at 00:06 UTC, at the end (F02, 2026-10-25 00:12 UTC) and after the independent review (F03, 2026-10-26 21:09 UTC) | A02, F01, F02, F03 |
| `main` | `f13bfdefcdd197ed1f966de0b1f93037a4168af4` (merge of PR #82, committed 2026-10-19T08:59:13Z) | A03, A04 |
| REV2 branch | tip `51564e34c18e5cc908cf517000ebc9bd41eaf194`; 0 behind, 2 ahead of `main`; commits `eca2b96521fba8cf792ea16a58be997e4f949356` (docs) then `51564e3…` (handoff); merge-base `f13bfde…` | A04 |
| REV3 branch | `docs/g4-fts-correctness-handoff-rev3-oct2026`, tip `2dd2e7bb05db949a6156266cfa3430c58de09922` (committer N4Z, 2026-10-23T10:30:25Z); 0 behind, 1 ahead of `main`; merge-base `f13bfde…` | A03, A04 |
| Between the two branches | A…B = 2 / 1 (diverged from the same merge-base); changed paths do not overlap | A04, A05 |
| PR #90 | open, **draft**, author `1h0lde4`, head `2dd2e7bb…`, base `main` (`f13bfde…`), 1 commit, 6 changed files (+337 −0), mergeable clean, last updated 2026-10-23T10:30:47Z | A05, F01 |
| PR #90 files | modified `IMPLEMENTATION_ROADMAP.md` (+1); added `docs/reports/g4-fts-correctness/`: `G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` (90), `NEXT_SESSION_PROMPT_REV3.md` (66), `decision_ledger_1d813bd_OPEN_D2_D5_REV2.md` (91), `doc_fetch_quotations_as_returned_HEADER_REV2.md` (60), `fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md` (29) | A05 |
| PR for the REV2 branch | none (0 results for `head=1h0lde4:docs/g4-fts-errata-handoff-oct2026`) | F01 |
| Open PRs | At 2026-10-24/25 (A06, F01): 16 open — 91, 90, 89, 88, 87, 86, 83, 81, 79, 77, 76, 33, 32, 30, 29, 27. **Re-checked 2026-10-26T21:09Z (F03): 16 open — 92, 91, 90, 89, 88, 87, 86, 83, 81, 79, 77, 76, 33, 32, 30, 27.** PR #92 (dependabot, `actions/setup-python` bump, opened 2026-10-25T22:22:57Z) is new; PR #29 was closed unmerged at 2026-10-25T22:23:05Z. PR #91 (DEBT-012 test-config isolation) is newer than anything REV3 lists. This list is time-bound. | A06, F01, F03 |
| Open-PR overlap, path scan | Changed-file lists of every open PR matched against `sqlite_storage`, `unified_memory`, `knowledge_entry`, `core/memory/`: **no hits**, at both 2026-10-25 00:06Z (A06) and 2026-10-26 21:09Z (F03, 16 PRs including #92, whose files are only `.github/workflows/ci.yml` and `release.yml`). Tracking files: #91, #89, #88, #87, #83, #81, #79 touch `KNOWN_ISSUES.md`; #88 also `CURRENT_STATE.md`; #90 `IMPLEMENTATION_ROADMAP.md` (F03). | A06, F03 |
| `KNOWN_ISSUES.md` (`main` blob `f9e7e5b8d4a0a87a5364299410574a5c310c0153`) | DEBT-042 line 56: `SqliteStorage._fts_escape()` leaves FTS5 query-syntax characters unescaped (OPEN, reproduced, not fixed). DEBT-043 line 57 (content-anchor, different subject). No entry for the `ke_ad` stale-posting condition (search scope: that file at `origin/main`, patterns `fts|stale.posting|ke_ad|erasure|I-3a|I-4|RD-10|DEL-n`; only DEBT-042 lines matched). | A07 |
| FTS source on `main` | `core/memory/backends/sqlite_storage.py` blob `ed0cbae6b54d157a2afb22e391c56da20acc118a`; `knowledge_entry.py` `0d5e07163acd8e152c312dbbb233e3bcb1094965`; `unified_memory.py` `eb2bbe17f12889d8638512560226456a6d43c9bd`. The first two are the same blobs on both branches, at study baseline `1d813bd…` and at `488129b8768a88a3d21dfd80b1f5407d50aba908` (checked in my audit clone). Trigger text on `main`: `ke_au` uses the `'delete'` command (lines 102, 139); `ke_ad` is a plain `DELETE FROM knowledge_entries_fts WHERE rowid=old.rowid;` (line 108). | A08, E02, E03 |
| Remote branches | 92 heads; names matching `042|fts|escape|i-3a|isolation|erasure|memory|sqlite` are the two G4 branches and unrelated sandbox/DEBT-012/DEBT-029 branches (names only; contents not inspected) | A03, E06 |
| Limits | shallow clone (history before the boundary invisible); PR data via the REST API only (GraphQL is blocked in this environment); `gh` calls are read-only | A01, A05 |

**Target declaration (A09, written before any possible write).** The only branch that could ever have been edited was `docs/g4-fts-errata-handoff-oct2026` at `51564e34c18e5cc908cf517000ebc9bd41eaf194`. No repository path was pre-authorized for edits. The REV3 branch, PR #90 and `main` were read-only. Every output of this task lives outside the repository.

---

## 3. Evidence register

All files are in `evidence/` next to this report. Each records the exact command, UTC start and end, exit status and unaltered output. Times are UTC. (The recorder's header lines say "tz of user: Africa/Casablanca, UTC+00:00"; that is the harness's label, which was not independently verified, and no time here depends on it.)

| ID | What it records | Result in one line |
|---|---|---|
| A01 | baseline: date, root, remote (credentials redacted), branch, HEAD, shallow, identity, stash | branch and HEAD as in §2 |
| A02 | worktree status, ignored files, staged/unstaged diff | all empty |
| A03 | fetch of the three refs; `ls-remote` for `main`, `docs/g4*`; local refs | tips as in §2; 92 remote heads |
| A04 | ancestry: ahead/behind, merge-bases, parents, commits beyond `main` | as in §2 |
| A05 | PR #90 metadata and file list | draft, 6 files |
| A06 | all open PRs; per-PR path scan | no FTS-source overlap |
| A07 | `KNOWN_ISSUES.md` rows and search | DEBT-042 OPEN; no stale-posting entry |
| A08 | `git log` and blobs of the three FTS source files | unchanged since the baseline |
| A09 | target declaration | no write target in use |
| B01 | search for the REV3 ZIP and handoff candidates | none found |
| B02 | outputs directory and delivery directory | empty |
| B03 | search of this session's transcript for earlier file deliveries | none recoverable |
| B04 | every occurrence of the digest prefix on the REV3 branch; character comparison | A ×3, B ×1, offset 23 |
| C01 | zip and packet hashes in four places | all packet copies `db6d7b89…` |
| C02 | where earlier runs recorded which packet bytes they saw | audit report line 55, verification report line 49 |
| C03 | REV2 zip: listing, safety checks, integrity test, fresh extraction, manifest | 87 entries, 86/86 OK |
| C04 | 83-check re-run, script extracted from the REV2 zip, input = repo packet | 83/83, exit 0 |
| C05 | same re-run using the pre-packaging script copy | 83/83, exit 0, byte-identical to C04 |
| D01 | hashes, line counts, line endings and diff statistics of both handoffs | `da162e71…` / `a41ca610…` |
| D02 | transfer-status and provenance statements in both | see §6 |
| D03 | full diff, older to repository handoff | 13 hunks |
| E01 | REV3 blobs, roadmap diff, next-session prompt in full | see §7 |
| E02 | REV3 recorded hashes against the in-repo copies; REV3's source-blob claims against `main` | claims hold; copies differ from recorded external hashes |
| E03 | REV2 against REV3 ledger and fetch-quotation header | ledger differs in D-2 and D-5 only |
| E04 | scans for authority wording, decision-status wording and "3.42" | see §7, §8 |
| E05 | negative search: secure-delete, PRAGMA, VACUUM, FTS5 commands in tracked files | none for secure-delete |
| E06 | D-1…D-11 status rows in both ledgers; D-7 evidence; branch-name scan | all OPEN; no real DB examined |
| E07 | original prompt embedded verbatim in both handoffs | true for both |
| F01 | live re-check at 2026-10-25 00:06 UTC | no change |
| F02 | final diff and repository check, 2026-10-25 00:12 UTC | worktree, index, stash and refs unchanged; HEAD `51564e3…`; P1 `git apply --check` OK |
| F03 | re-check after the independent review, 2026-10-26 21:09 UTC: repository state, remote tips, all open PRs and their path scan, PR #29/#90/#92, P1 `git apply --check` | repository unchanged; PR set changed as noted in §2; no FTS-path overlap |
| G01 | the independent reviewer's hand-back, as received (model output) | findings F1–F9; see §11 |
| G02 | my re-derivation of the reviewer's findings F1, F2, F5, F6, F7 (commands and outputs) | F1, F2, F5, F6, F7 confirmed |
| G03 | the reviewer's second-pass hand-back, as received (model output) | "fit (nits only)"; nits N1–N4; see §11 |
| F04 | final consistency check of this report after all edits (placeholders, section list, final status line, evidence IDs present on disk, repository state) | see §12 (run last; output in `evidence/F04_final_consistency_check.txt`) |

Bulk outputs: `out/rev2_manifest_check.txt`, `out/rev2_numbers_check_task5.json` and `…_task5_nonarchive.json` (sha256 `ae12c539ee7296595d535c01e4ae50c7337981d720b24082ee58522537d9f257`), `out/repo_handoff_at_51564e3.md`, `out/ledger_rev2.md`, `out/ledger_rev3.md`, `out/fetch_rev3.md`.

---

## 4. Archive authentication — the REV3 ZIP

**Expected artifact** [REPORTED]: `fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip`, 254,581 bytes (name, digest and size: `G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` lines 15–17 and `NEXT_SESSION_PROMPT_REV3.md` line 16); 86 manifest entries (continuation line 18); 87 archive entries in total (verification report line 6).

**Search** [OBSERVED, B01–B03]. Scope: the whole container filesystem (one device, excluding `/proc`, `/sys`, `/usr`, `/lib`, `/opt`, `/var/lib`, `/snap`) for names matching `*REV3*`, `*D2_D5*`, `*FETCH_HEADER*`, `handoff*` and for any file of exactly 254,581 bytes; every `.zip` outside system directories; the user attachment directories (`/mnt/user-data/attachments`, `/mnt/user-data/uploads`, `/root/.claude/uploads`); the delivery directory `/mnt/user-data/outputs` (empty); this session's transcript (it holds no recoverable file deliveries). Result: no candidate. The only ZIPs of this lineage present are my REV2 bundle (255,601 bytes) and superseded scratch builds of it; none has the REV3 name or size. I did not substitute any of them, rebuild anything or repackage anything.

**Disposition of both recorded values** [OBSERVED, B04]:

| Value | String | Where recorded (live files at `2dd2e7bb…`) |
|---|---|---|
| A | `f9ee626551e5175a7ba0893c336a77917b8be1b4078903cc6ac5853ad7e509cc` | `IMPLEMENTATION_ROADMAP.md:2`; `docs/reports/g4-fts-correctness/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md:16`; `…/NEXT_SESSION_PROMPT_REV3.md:16` |
| B | `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc` | `docs/reports/g4-fts-correctness/fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md:4` (the report says the digest and size "were computed from the generated file", line 10; it prints no command output) |

Both are 64 hex characters. They differ at exactly one position, zero-based offset 23. Neither is endorsed, corrected or discarded. Which is right, if either, depends on hashing the actual bytes and on a provenance link between those bytes and the packaging run.

**Gate status: original-ZIP authentication — BLOCKED.** Missing: the REV3 ZIP itself (or an unaltered `sha256sum` output on it with provenance). Smallest unblocker: attach the ZIP to a session, or run `sha256sum fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip` where it lives and preserve the full line. If the result is A or B, `proposed_diffs/P2_digest_discrepancy_erratum_TEMPLATE_CONDITIONAL.md` says what to record. If it matches neither, authentication stays unresolved until provenance is investigated.

---

## 5. Archive and transcription verification

The task keeps three claims apart. They are kept apart here.

**(1) ZIP SHA-256.**
- REV3 ZIP: BLOCKED (§4).
- REV2 ZIP (a different artifact; used only for the transcription check): the copy in this session's scratch area hashes to `e6910c0cc6eb1acefaaf369ce46599856a169228a3060b6492687c8fd70b9c3d`, 255,601 bytes [OBSERVED, C01, C03]. That equals the value recorded in my earlier verification report and in the repository handoff §8. The copy is the source of the file I delivered; I cannot see the user-side downloaded copy, so identity with it is [REPORTED], not observed.

**(2) Archive, manifest and content integrity.**
- REV3 ZIP: BLOCKED. REV3's own claims of "87 entries / 86 manifest entries / 86/86 OK" [REPORTED: verification report lines 6 and 14; continuation line 18] are unverifiable here.
- REV2 ZIP [OBSERVED, C03]: 87 entries; 0 absolute or `..` paths; 0 duplicate names; 0 case collisions; all entries regular files (no symlinks or special entries); `unzip -t` clean; extracted into a new empty directory; `sha256sum -c MANIFEST.sha256` exit 0 with 86 OK and none failed; no unlisted and no missing file. Limits: the manifest lives inside the archive, so it is a comparison, not an independent proof of intent; the extraction was only read, never run. Hash and manifest checks say nothing about whether the probes' conclusions are right.

**(3) The 83/83 transcription check.**
- *What the earlier 83/83 saw* [REPORTED]: the audit report (line 55) records the packet text each run saw: runs 1–2 `6a15f26016313145…`, run 3 `4685970bdbbf25b6…`, run 4 and the fresh-extraction verification `db6d7b89…`; the result JSON stores only the packet's file name, not its hash (`rev2_numbers_check_run4.json` keys: `tool`, `packet`, `total`, `failed`, `checks`; C02). So the identity of run 4's input rests on that report text.
- *Byte identity of the packet* [OBSERVED, C01]: the packet bytes at commit `51564e3`, in my scratch copy, and inside the REV2 zip all hash to `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2`. REV3 records the same packet hash [REPORTED, continuation line 19; prompt line 49], but that is a claim about its own ZIP.
- *New run, exact input recorded* [OBSERVED, C04, C05]: input = the packet bytes from commit `51564e3` (`db6d7b89…`); script `rev2_numbers_check.py` sha256 `730ae766abe0bb9c1712e15d732c0f97c126efa0cad4274d167618da3a53a315`; `python3.12 -I`; the audit worktree at `1d813bdae320bf34110c29836c81dc901c601c9b` read-only (HEAD and 0 changes before and after each run); outputs, independent-derivation and contract-compare files from the extraction of the REV2 bundle (manifest-verified 86/86, C03; byte-identical to the pre-packaging `b4/out`); **and two further input files that are not in the REV2 bundle**: the checker's `--preserved` directory `a4/zx_fresh/out` supplies `fts_migration_protocol_run1.json` (sha256 `c28b21e82e3a5c842cfa1f66632271a35aa1c60fcebd902c93bca316e149eff3`) and `fts_migration_protocol_run2.json` (sha256 `24a5d07427422b4aeb5a2b8c35eea52cc728b546fb9f695e39271dcffa7ec831`; the checker reads them at script line 185). Both hashes are identical to those of the files at `out/fts_migration_protocol_run{1,2}.json` inside the revision-1 evidence archive `b3_deliver/fts_decision_packet_evidence_1d813bd.zip` (sha256 `79c6146c609a76548260f261f05692d32bbd32f44694b430a096a48a079d2721`, 79,260 bytes) and to lines 13–14 of `a4/zx_fresh/MANIFEST.sha256` (G02). I did not independently re-derive that this archive is the one the user received. Result: `83/83 checks passed`, exit 0; result JSON sha256 `ae12c539ee7296595d535c01e4ae50c7337981d720b24082ee58522537d9f257`, byte-identical to the bundled run-4 JSON, and identical between the extracted-script run (C04) and the source-script run (C05).
- *What this establishes:* every figure the checker covers is transcribed correctly from the REV2 bundle's raw probe outputs (and the two carried-over protocol-run files above) into the packet at `51564e3`. *What it does not establish:* that the raw outputs are correct (that rests on the probe code, source excerpts and the independent derivation); anything about the REV3 ZIP; anything about figures the 83 checks do not cover. The REV3 report itself says its packaging pass did not re-run the check (line 25, "was not rerun in this packaging pass"); that statement is consistent with what I found.
- *Standing caveat from the earlier audit:* the independent derivation of the revision-1 packet scored 385/387, and both failures are the same 50k-row duration finding (AF-02). That is historical and was not re-executed.

**Gate statuses:** archive integrity and contents — **BLOCKED** (for the REV3 ZIP; the REV2 ZIP passed as a reference only). Transcription-check identity — **PASS** (new run on exact bytes; the REV3 claim is explicitly qualified).

---

## 6. Handoff provenance

| Fact | Status | Evidence |
|---|---|---|
| The older handoff, as held in this session's scratch area (the file I delivered), has sha256 `da162e71d6bd0b92650134eceb6af1ecfa430484ac08b179d7aaa48a97fa716d`, 502 lines, 48,655 bytes, no carriage returns | OBSERVED | D01 |
| That hash equals the one REV3 records for `handoff(1).md` | OBSERVED (string match) | D01; continuation lines 9, 24; prompt line 12 |
| The user-side attachment `handoff(1).md` is byte-identical to that scratch copy | **UNVERIFIED** — the attachment is not available to this session | B01, B02 |
| Repository `handoff.md` at `51564e3` has sha256 `a41ca6101a7dfebc6bdb8d18b1abce7934a83b886ea0ce0d96f2dd739ef662df`, 541 lines, 55,056 bytes; git blob `05296d7339e7565116156cecaf047961c51b75ea`; working-tree file identical | OBSERVED | D01 |
| Same 19 level-2 headings; 13 diff hunks; 87 changed lines; no CR in either | OBSERVED | D01, D03 |
| The differences are: created/"first written" note; branch and transfer-commit lines; transfer status (INCOMPLETE → READY); the user's 2026-10-23 10:52 UTC instruction and the two approved options; §7 repository fields; §8 file table and hashes; §12 one added row; §15 one added risk row; §18 resume steps; §19 status | OBSERVED | D03 |
| Both carry "Handoff version: 1" | OBSERVED — a documentation gap: two different files share one version label | D02 |
| The older revision says "TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED" (line 11, line 498) and "the repository contains no work of this workstream" (line 500); its §7 says "Branch: none created", "not pushed — not authorised"; its §18 step 3 says "do not look for a branch or commit" (line 492) | OBSERVED | D02, D03 |
| Those older statements described an earlier state, not a contradiction of the repository's later state: when it was written the task forbade a branch, commit or push, and the user's push approval came later | DERIVED from D03 and the repository handoff §3 | D03 |
| The repository handoff says "first written 2026-10-23 as a file-only handoff, updated here" (line 6) but does **not** name the older revision's hash, does not mention REV3, PR #90 or `handoff(1).md` | OBSERVED (no match for `da162e71|rev3|REV3|2dd2e7|PR #90|N4Z`) | D02 |
| REV3's prompt already calls the older transfer-status paragraph "historical" and says the REV3 continuation "records the later user-directed documentation checkpoint" (line 12) | OBSERVED | E01 |
| REV3's prompt says the embedded original task prompt "was verified byte-identical" | The claim holds for both handoffs I hold: the prompt attachment (sha256 `f7949f94cddfa85643e6401bcfb8535b68fa64c53ed5f54c1c7c3579231bb65d`, 15,404 bytes) occurs verbatim inside §2 of each | E07 |
| The fresh-session instructions are unambiguous *within each document*, but there are two documents that each direct a fresh session (repository handoff §18: check out the REV2 branch; REV3 prompt: read the REV3 continuation, the older handoff and a ZIP). They do not refer to each other. | OBSERVED | D03, E01 |
| Broader supersession than the evidence supports: the REV3 roadmap sentence "Begin the next session with the G4 REV3 continuation and owner decision pack for D-1…D-11" and the continuation §7 "Required next-session sequence" read as operational entry-point instructions. No authorization designating REV3 as the entry point exists in anything I was given. | OBSERVED wording; the lack of authorization is [DERIVED] from the task text | E01 |

An earlier statement of mine in this session called the older handoff's stale status a hazard for a fresh session that follows REV3. That was overstated: REV3's prompt already flags that paragraph as historical (line 12). What remains is the missing cross-reference in the repository handoff, and the second entry point.

**Gate status: handoff provenance — PASS** under the gate's own wording (available files inspected and hashed; the unavailable attachment's hash is carried as unverified). **Proposed, withheld change:** `proposed_diffs/P1_handoff_provenance_note.patch` (see §10).

---

## 7. REV2 and REV3 compared, document by document

Revisions are exact commits and blob IDs. "REV2" = `51564e3`; "REV3" = `2dd2e7b`.

| Document | Revision / sha256 | Stated purpose and status | Relative to its counterpart | Support and conflicts |
|---|---|---|---|---|
| REV2 packet `docs/studies/g4-fts-errata-oct2026/g4_fts_correctness_batch_decision_packet_1d813bd_REV2_PROPOSED.md` | blob `e32ec6a8e3a8…`; `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2` | PROPOSED decision packet | No REV3 counterpart in the repository; REV3 *reports* the same packet hash | Figures transcribed correctly (C04/C05). Line 304: secure-delete "not enabled by the product"; line 308: 3.42.0 is "a compatibility constraint, not a reason to mandate secure-delete here"; lines 351, 362: real databases "UNKNOWN; none examined", rank=1 on a copy is something the maintainer "may run". |
| REV2 addendum `…/addendum_evidence_labels_REV2_PROPOSED.md` | blob `ebc42b574208…`; `2cf514539e245e5941cda3b5a962f1f0d7b6478f723a9980c2f85c092c4fc920` | PROPOSED labels; ratification is D-6 | none in REV3 repo files | Line 39: nothing ratified or accepted. |
| REV2 audit report `…/evidence_audit_report_1d813bd.md` | blob `829e1f620f6f…`; `2dc09f0d1d89d2613d1dd56d3e0a34753492319efd1018c7ef295b0faad028af` | historical report of the audit; AF-01…AF-14 dispositions proposed | none in REV3 repo files; REV3 reports this hash unchanged (verification report line 26) | Records which packet bytes each checker run saw (line 55). |
| REV2 ledger `…/decision_ledger_1d813bd_OPEN.md` | blob `988f7f91bf33…`; `ed188b17d1b9f328a9ffc6c048a74b18c67c50507c99c22b3edfbf5e221cf719` | PROPOSED register; "No item is decided, ratified or accepted here" | REV3 ledger is a copy with changes confined to D-2 and D-5 | All 11 rows OPEN; recommendations only on D-4 (rank=1 inside the transaction) and D-5. Identical, byte for byte, to the copy inside the REV2 zip (E03). |
| REV3 ledger `docs/reports/g4-fts-correctness/decision_ledger_1d813bd_OPEN_D2_D5_REV2.md` | blob `92a380920c6b…`; `9508f1ab630f48ae6935644f7d156ba1049bd85b84ea332a7c037d5c446252a2` (in-repo copy) | same status line | 3 hunks, 21 changed lines (E03): D-2 evidence/recommendation/doc-wording/still-required rewritten; D-2 options changed from one line to (a)(b)(c); D-5 gains an options line and sharper scope/"not ratified" wording; no trailing newline | All 11 rows OPEN; recommendations still only D-4 and D-5. New claims: the product does not enable FTS5 secure-delete (**supported** by the negative search E05: no match for `secure.?delete` or `PRAGMA secure` in any of 551 tracked files at `main`, all code/config types, plus packet line 304); "11/11 passages found in the raw 3.45.1 docs" (**supported** by the REV2 bundle's raw-docs verification; not re-run here). New alternatives (D-5 b, c) are options, not decisions. No caveat deleted. |
| REV3 fetch header `…/doc_fetch_quotations_as_returned_HEADER_REV2.md` | blob `dfee80ff350a…`; `3ddeba44ca5bce17364c9dc4b17923e08106a213b08992c9d3a80906fa5889e0` | archival record of fetch-tool output, marked non-authoritative | vs the file inside the REV2 zip (58 lines): 5 hunks (REV2 lines 1, 3, 5, 7 and 58 against REV3 lines 1, 3, 5, 7–9 and 60); everything else byte-identical (E03, G02; the REV3 copy has 59 newline-terminated lines and no final newline, 60 lines by the hosting count) | Adds the provenance and authority disclaimer and a 3.45.1 raw-docs note. Fetch-tool section numbers differ from the raw docs; heading IDs are the stable citations. |
| REV3 verification report `…/fresh_extraction_verification_report_D2_D5_fetch_header_REV3.md` | blob `23ce21a7c1b1…`; `1fc6999b126d943fff6a1bf40e8c69f47974cd6af5c07294a04ac17dd46153aa` | historical report on the REV3 archive | No REV2 counterpart in the repository (mine is outside it) | Line 4 holds Value B. Says the packet and audit-report hashes are unchanged and the 83/83 check was not re-run. Every statement about the ZIP is unverifiable here. |
| REV3 continuation `…/G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` | blob `f2725b85329846…`; `d821c218afbde5a8…` (sha256 prefix) | "PROPOSED / decision-gated; not an ADR, acceptance record, or implementation authorization" | counterpart in role: repository `handoff.md` | Source-blob claims all hold on `main` now (E02). "Open PRs #88, #87, #83, #81, #79, #89 also touched `CURRENT_STATE.md` or `KNOWN_ISSUES.md`" holds (A06) but is time-bound: PR #91 is newer. "PR #89 does not change `sqlite_storage.py`" holds (A06). Line 16 holds Value A. §7 (lines 80–85) gives a "Required next-session sequence". The evidence ZIP stays outside Git (line 11); the original handoff is a separately preserved attachment (line 9). |
| REV3 next-session prompt `…/NEXT_SESSION_PROMPT_REV3.md` | blob `ae828cb1223c…`; `5495ca46b1115e17…` | instruction set for a future session | counterpart in role: repository `handoff.md` §18 | Line 16 holds Value A and tells the next session to stop evidence-dependent claims if the ZIP is absent or does not match. Line 49 restates 83/83 for `db6d7b89…`. Operational wording; not a decision. |
| `IMPLEMENTATION_ROADMAP.md` (REV3) | blob `8630559a43a6…` (+1 line vs `main`) | living roadmap | the only REV3 change to an existing file | The added line 2 records Value A and says "Begin the next session with the G4 REV3 continuation…". It also says no implementation batch is cleared and keeps G4/G5–G8/freeze statuses. As written, the line records a digest that conflicts with another record on the same branch (§4) and contains an entry-point sentence for which no user authorization is evidenced (§8, D-A). |
| Repository `handoff.md` (REV2) | `a41ca610…ef662df` | transfer record; "a transfer record, not an authority" (its §18) | revision of the older handoff (§6) | See §6. |
| Older handoff `handoff(1).md` | `da162e71…716d` (scratch copy) | earlier revision | — | See §6. |
| REV2 evidence ZIP | `e6910c0c…c3d` | immutable evidence bundle | REV3 ZIP is a different, later, unavailable bundle (87 archive entries / 86 manifest entries each; 254,581 bytes [REPORTED] vs 255,601 bytes [OBSERVED]) | REV3's verification report says exactly three inner files changed (`MANIFEST.sha256`, `report/decision_ledger_1d813bd_OPEN.md`, `docs/doc_fetch_quotations_as_returned.md`). That fits the repository diffs above for the ledger and the fetch header, but cannot be checked without the ZIP. |

**Claim-level conflicts found (none is a contradiction of evidence):**
1. Digest: A against B inside REV3 (§4).
2. Two entry points (§6).
3. REV3's ledger D-2/D-5 wording against REV2's (§7 row above). The REV3 wording is more explicit; REV2 already said the same in substance (packet line 308; REV2 ledger D-2 "compat constraint").
4. REV3's in-repo copies hash differently from the digests REV3 records for the "preserved external disk files" (E02: ledger `9508f1ab…` against `f6dda8a2…`, header `3ddeba44…` against `f9abc199…`, report `1fc6999b…` against `dd77ace0…`). REV3 says the connector normalised line endings; the in-repo copies contain no CR and three of them (the ledger, the fetch header and the verification report) lack a final newline while the roadmap, continuation and prompt end with one (G02), which is consistent with that statement, but the disk files are not available to confirm it.
5. REV3's "open PRs" list omits #91 (time-bound, not an error).

Repetition of a claim across the documents was not used as support anywhere in this table.

---

## 8. Authority matrix [RECOMMENDATION — not an authorization]

Categories: **E** = current operational entry point; **H** = historical source; **P** = active proposal; **S** = supporting evidence; **R** = historical report; **X** = precisely identified superseded statement.

| Document | Recommended classification | Why (not from filename, date or completeness) |
|---|---|---|
| REV2 packet, addendum | P | self-described PROPOSED; decisions they raise (D-6 etc.) are OPEN |
| REV2 audit report | R (+ S for AF findings) | records what was checked and observed on specific dates |
| REV2 ledger | P | register of OPEN items; recommendations only on D-4, D-5 |
| REV3 ledger | P | same, with D-2/D-5 wording changed; the difference needs a document-by-document decision |
| REV3 fetch header | S (provenance of quoted tool output) | explicitly non-authoritative for wording |
| REV3 verification report | R | records what was claimed to have been checked on a ZIP I cannot see |
| REV3 continuation | P + R, **with operational wording** | proposal/status record whose §7 reads as instructions |
| REV3 next-session prompt | H + P (operational wording); candidate for E only if the user decides (D-A) | an instruction set for a future session; "H" here means retained for provenance until the user decides D-A, and it can only be an entry point if the user says so |
| REV3 roadmap line | **Unresolved**: authority-bearing wording in a living roadmap | contains an unresolved digest and an entry-point sentence |
| Repository `handoff.md` | H + P (transfer record); candidate for E only if the user decides (D-A) | a transfer record whose own §18 says it is not an authority; "H" here means retained for provenance until the user decides D-A |
| Older handoff `da162e71…` | H | earlier revision; only its transfer-status statements describe an outdated repository state (X, limited) |
| REV2 evidence ZIP | S, immutable | hash-recorded bundle |
| REV3 evidence ZIP | S, immutable, **unauthenticated** | not available |

**Recommended model, if the user adopts one.**
1. Evidence archives are immutable supporting evidence; their digests are recorded once, in one place, after measurement.
2. Packet, addendum and both ledgers stay PROPOSED; no ledger is declared canonical by position or date.
3. Exactly one operational entry point is named by the user; every other handoff or prompt is labelled "historical source" with a one-line pointer.
4. REV3's D-2/D-5 wording is adopted or rejected explicitly, section by section; the diff between the two ledgers is only those two sections plus an end-of-file newline.
5. Superseding statements, if any, name the exact statement replaced (P1 does this for the older handoff's transfer-status lines only).

**Smallest decisions needed from the user** (none is made here):
- D-A: Which document directs the next session: repository `handoff.md` §18, REV3's prompt/roadmap sentence, or a single index that points to both?
- D-B: May REV3's D-2/D-5 text replace the REV2 text (as a new ledger revision, keeping the old one)?
- D-C: Authorize P1 (a provenance note in `handoff.md`)? It is optional and does not depend on D-A.
Separately, and not a decision: someone with the REV3 ZIP must hash it (§4).

---

## 9. Decision-preservation audit

### 9.1 D-1 … D-11 [OBSERVED, E06]
Both ledgers list every row as **OPEN** (REV2 rows D-1…D-11; REV3 rows D-1…D-11). Neither ledger recommends anything except D-4 (evidence-supported part only: run `rank=1` plus an independent reference *inside* the migrating transaction) and D-5 (keep physical erasure separate). In every other row the recommendation field says "none". No document in either set (scan scopes in E04) says a D-item is accepted or ratified; the one use of "ACCEPTED" in the repository handoff (§15, line 493) refers to the user's scope choice about leaving the evidence bundle out of the repository, not to any D-item.

| Item | Source status and caveats | What REV3 changed | Unknown / not established |
|---|---|---|---|
| D-1 placement | OPEN; options: standalone batch / keep inside I-4 / defer; "the evidence says the defect accumulates until the trigger is fixed; it cannot say whether that outranks isolation work" | nothing | ranking against isolation work |
| D-2 SQLite floor | OPEN; only 3.45.1 on Python 3.12.3 tested; 3.42.0 is when the FTS5 secure-delete option appeared — that alone sets no product floor | wording expanded (§7); options (a)(b)(c) listed | any other SQLite build, Python version, platform; how the product obtains SQLite |
| D-3 RD-13 classification | OPEN; stale-posting tracked apart from DEBT-042 (a query-escaping defect in the same file); OBS-LC-1/2 reproduced through the unchanged API on a fresh database | nothing | classification, ID, owner |
| D-4 migration state | OPEN; atomicity-on-every-path against a versioned marker is the maintainer's choice; trigger-body test alone and marker alone are each insufficient | nothing | the choice |
| D-5 physical erasure | OPEN; recommendation (not ratified): keep it separate; does not satisfy or waive RD-10 / DEL-1…4; secure-delete anomaly unexplained; VACUUM not an erasure guarantee | wording expanded; options (a)(b)(c) listed | an erasure policy, scope and acceptance evidence; **no document claims erasure is implemented** (scan E04, E05) |
| D-6 labels | OPEN; the three product-state labels and separate axes are PROPOSED | nothing | ratification |
| D-7 real databases | OPEN, optional; **no real database was examined** | nothing | real sizes, legacy states, ghost prevalence; G-5 cannot close without them |
| D-8 doc owner | OPEN; two known doc conflicts (`SESSION4C_REPORT.md:142`, REM-012) | nothing | owner |
| D-9 concurrency | OPEN; options (a)–(d), one of them a designated startup migrator; races: exactly one migrator in 15/15 (2, 4, 6 processes), a waiter failed after 20.05 s | nothing | four-process end-to-end, contender crash, mixed old/new code |
| D-10 unknown states | OPEN; fail-closed is what the probe did (S4b/c/d refused, S4a recreated), not a policy | nothing | the policy |
| D-11 ownership/sequence | OPEN; options include FTS first, I-3a first, same branch, coordinated order; the specific order DEBT-042 → I-3a → I-4 appears in neither ledger | nothing | owner and order |

### 9.2 Premise correction for D-7
The task text (§9, D-7) says to preserve "the evidence limitation that there were no real database uploads and that rank=1 was run on a local copy, as previously reported." The first half holds. The second half is not supported: the packet says real databases are "UNKNOWN; none examined" (line 351) and that the check on a copy is something the maintainer "may run" (line 362); the ledger, audit report (lines 133, 144) and REV3 (continuation line 45) agree. The only copies any document records are byte copies of generated, disposable fixtures (packet line 130: "Procedures were applied to a byte copy of each of the 7 prepared fixtures"), and fresh databases created by the real constructor; the `rank=1` checks that were run used those. No document records `rank=1` being run on a copy of a real database. The task's wording resembles a proposal in an attached review (`7af26dc9`, D-7: "Use a local copy of a real database for the read-only `rank=1` consistency check"), which is a proposal, not a recorded run. No live-production or real-upload validation is evidenced. [G02, G01 F2]

### 9.3 Third-party proposals
A recent review (attached by the user in this session) proposed concrete dispositions for D-1…D-11. They are not in either ledger and were not adopted. Three of them go beyond the ledgers' evidence: D-4 "prefer a versioned marker", D-9 "designated startup migrator", and D-11 "DEBT-042 → I-3a → I-4". Each is one option among several; the ledgers expressly make no recommendation.

### 9.4 G4–G8, physical erasure, debt and sequence
- G4 remains OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED. Nothing here moves them.
- Physical erasure is not claimed as implemented anywhere in the sets I scanned. The ledgers and REV3 both keep RD-10 / DEL-1…4 outstanding. The product contains no use of the FTS5 secure-delete option (E05; scope: 551 tracked files at `main`; `*.py *.toml *.cfg *.ini *.yml *.yaml *.json *.sh`; zero matches for `secure.?delete` and `PRAGMA secure`; `*.md` files also have zero). Product PRAGMAs found (E05 lists them all): WAL and `synchronous=NORMAL` in several modules, `foreign_keys=ON`, `cache_size`/`temp_store` in `core/context.py`, and checkpoint/journal-mode pragmas in `core/runtime/state.py`; no `VACUUM` in product code under the pattern used. "Not found within this scope" is not "absent from the product everywhere": runtime-generated SQL strings and non-tracked configuration were not inspected.
- DEBT-042 / I-3a / I-4 overlap: revalidated at 2026-10-25 00:06 UTC and again at 2026-10-26 21:09 UTC (§2; A06, F01, F03): same source blobs as the baseline; no open PR touches the three files or `core/memory/`; no branch name points at DEBT-042 or I-3a work; DEBT-042 is OPEN on `main`. This does not resolve ownership, scope or sequencing (D-11).

### 9.5 Corrections to earlier statements in this session
- I wrote "the odds are about 10⁻³⁶" for two digests differing in one hex digit. The correct figure is about 8×10⁻⁷⁵ (960 / 16⁶⁴), and the wording "cannot" should have been "overwhelmingly unlikely". Neither changes the conclusion that only hashing the actual file settles the question.
- I called the digest check one of "the two decisions that remain". It is a verification task, not a decision.
- I described a fresh session following REV3's prompt as facing a stale handoff status. REV3's prompt already marks it historical (§6).

---

## 10. Change record

**No file in the repository was changed. No commit, push, PR update, merge, reset, clean, stash or branch operation was performed.** The working tree, index and refs are as they were (F02). The files produced by this task are outside the repository.

Every candidate change was classified before any editing, per the task's §10:

| # | Candidate | Category | Disposition |
|---|---|---|---|
| X1 | Note in repository `handoff.md` identifying the older revision (`da162e71…`) and limiting what of it is superseded (transfer-status statements only) | 3 — it declares a supersession | **Withheld.** Proposed diff: `proposed_diffs/P1_handoff_provenance_note.patch` (5 lines added after the "Cautions" bullet in §16; applies cleanly to `51564e3` with `git apply --check`; does not select REV2 or REV3, rank any ledger or touch any D-item) |
| X2 | Erratum or correction for the REV3 digest discrepancy | 2, blocked by the missing measurement, on a branch owned by PR #90 | **Withheld.** Conditional template: `proposed_diffs/P2_digest_discrepancy_erratum_TEMPLATE_CONDITIONAL.md` (not a patch; cannot be completed) |
| X3 | Remove or reword the REV3 roadmap/prompt entry-point sentence and the unresolved digest in the roadmap line | 3, on a user-owned draft PR | **Recommendation only.** These are open items a maintainer may wish to settle (the digest, D-A); this report makes no merge recommendation for PR #90. No diff prepared |
| X4 | Adopt REV3's D-2/D-5 text into the REV2 ledger, or the reverse | 3 | **Recommendation only** (decision D-B) |
| X5 | Time-bound statement in my earlier verification report §4 ("no branch, PR, commit or push was made") | 2, in an immutable delivered file outside the repository | **No edit.** The later user-approved push is recorded in `handoff.md` §3 and §7 |
| X6 | Register the `ke_ad` stale-posting condition in `KNOWN_ISSUES.md` | 4 (a classification decision, D-3) | **Out of scope** |

Objective factual corrections (category 1) within the authority of the target: none found, so none made. The P1 patch text, in short: *Earlier revision of this handoff — sha256 `da162e71…`, 502 lines, same 19 headings; limited supersession (its metadata line and §19 say "TRANSFER INCOMPLETE — HANDOFF NOT COMMITTED" and "the repository contains no work of this workstream"; its §7 records no branch, transfer commit or push; its §18 step 3 says not to look for a branch or commit); for repository state those are replaced by §7, §18 and §19 of this file; nothing else is replaced; parallel REV3 draft (`2dd2e7bb…`, PR #90) not reviewed in the session that wrote this file and neither selected nor superseded; not decided: entry point, ledger authority, any D-item, G4–G8, freeze, implementation.* Evidence for it: D01–D03, E01.

---

## 11. Independent review

**Outcome: a fresh-context review by a separate agent was performed, in two passes. It is not human-independent and not a second model family.** The reviewer (subagent `a248fe0cd49e5e6e6`) is the same model family as the author (Sonnet 5.5). It started with no knowledge of how the report was produced and did not author any change. The task (§14) accepts "a separate reviewer or a fresh-context review that did not author the changes"; this is the second kind. The result is therefore reported as an independent-context review, not as independent human verification.

**What it was given:** the task prompt (acceptance criteria); the report; the evidence, derived-file and proposed-diff directories; the repository clone with the baseline HEAD `51564e34c18e5cc908cf517000ebc9bd41eaf194` and the fetched refs; the rules (read-only on the repository and scratch trees, no execution of archive contents, no credentials, no network writes, `NOT VERIFIED` for anything unconfirmed, permitted paths: none); and the invariants to check (D-item status, document authority, implementation permission, physical-erasure claims, G4 status, G5–G8 status, freeze readiness, digest selection). It was told to re-derive claims itself and was not given a conclusion. Pass 2 was given the list of passages edited after pass 1.

**Process and limits, as they happened:** pass 1 was cut off by a rate-limit error (HTTP 429) before delivery; the agent was resumed once and delivered in full (G01). Its last check (the zone label) ended on a tool timeout. Pass 2 failed once on a rate limit and delivered on retry (G03). The reviewer did not re-run the 83/83 checker (it was told not to execute archive contents), did not read E01–E05 and E07 in full, did not re-derive every per-PR file list in pass 1 (it did re-run the full path scan in pass 2), and could not see the REV3 ZIP or the user-side `handoff(1).md`. Its verdicts: pass 1 "fit after specific fixes, no blocker"; pass 2 "fit (nits only)". Both passes explicitly ran the forbidden-claim scan (D-item status, authority and entry point, implementation permission, erasure, G4/G5–G8/freeze statuses, digest selection) over the report, P1 and P2 and found no violation, and both confirmed the repository unchanged.

**Findings and dispositions.** Each finding was re-derived by the author before acting (G02, F03); "accepted" means the report was changed.

| ID | Severity (reviewer) | Finding | Disposition |
|---|---|---|---|
| F1 | MAJOR (no gate flip) | the 83/83 input also included two protocol-run files from the revision-1 bundle (`--preserved a4/zx_fresh/out`) | confirmed (G02); accepted: §1 item 3, §5(3) now list both files with hashes and the revision-1 archive hash |
| F2 | MINOR | D-7 premise wording stronger than the evidence (the packet records byte copies of generated fixtures) | confirmed (packet line 130; attachment `7af26dc9` line 136); accepted: §1 item 6, §9.2 |
| F3 | MINOR | X3 and a roadmap-row sentence read as merge advice, contradicting §13 | accepted: X3 and the row reworded |
| F4 | MINOR | §8 labels asymmetric | accepted: both rows now "H + P …; candidate for E only if the user decides (D-A)" (pass 2 N4 refined the meaning of "H") |
| F5, F6, F7 | NIT | fetch-header hunk spec "58–60"; three files lack a final newline; header end time | confirmed (G02); accepted |
| F8 | NIT | gate-row evidence cells and Overall cell wording | accepted in the final edit (§12) |
| F9 | MINOR (time-bound) | open-PR list stale (#92 added, #29 closed) | confirmed (F03); accepted: §2, §1 item 7, §9.4 |
| zone | "NOT VERIFIED" | harness zone label vs Casablanca's usual offset | accepted: all times are UTC; the label is reported as unverified in the header, §2 and §3 |
| P1 nit | NIT | "not reviewed when this file was written" is time-ambiguous | accepted: P1 and the §10 summary now say "in the session that wrote this file"; `git apply --check` still exits 0 (F03) |
| N1–N4 (pass 2) | NIT | §10 summary phrase; zone label in §2/§3; §12 evidence cells and Overall cell; meaning of "H" | accepted |

**What the reviewer did not see.** The edits for N1–N4 and the text of this section and §12 were written after pass 2 and were not re-reviewed; the author checked them mechanically (placeholders removed, section structure, final status line, evidence IDs; see F04 in the register's last row). The author also found, before the review, four mis-cited lines in an earlier draft (the "87 entries / 86/86" citations and one count) and corrected them.

**Limitation to state plainly:** this review supports the claims it re-derived (about 85 values in pass 1) and the absence of forbidden wording. It does not make the REV3 ZIP authentic, does not verify the user-side `handoff(1).md`, and is not a substitute for the maintainer's own review.

---

## 12. Acceptance-gate matrix

Exactly one status per gate. A BLOCKED gate keeps the overall result from being PASS.

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Live repository and PR inventory | **PASS** | A01–A08, F01, F03 | state, full SHAs, worktree protections and discrepancies recorded; re-checked after the review (PR set changed: #92 added, #29 closed); shallow-clone and REST-only limits stated; PR data is time-bound |
| Target and scope | **PASS** | A09 | target declared before any write; no allowlisted path; no write occurred |
| Original ZIP authentication | **BLOCKED** | B01–B04 | the REV3 ZIP is not available; both digests preserved; neither selected |
| Archive integrity and contents | **BLOCKED** | C03 (reference only) | the REV3 ZIP cannot be inspected; the REV2 ZIP's clean result is not a substitute |
| Transcription-check identity | **PASS** | C01, C02, C04, C05, G02 | new 83/83 on hash-recorded exact packet bytes and a hash-recorded checker, with every other input identified (REV2-bundle files manifest-verified; two protocol-run files carried over from the revision-1 bundle, hashed); the REV3 claim is qualified as unverified |
| REV2/REV3 comparison | **PASS** | E01–E04, D03 | all six REV3 repository files and five REV2 files compared; contents of the REV3 ZIP not compared (unavailable) |
| Handoff provenance | **PASS** | D01–D03, E07 | the available copy hashed; the unavailable attachment's hash carried as unverified |
| Document-authority analysis | **PASS** | §7, §8 | classifications and recommendation given; no authority change; unresolved choices and smallest decisions stated |
| D-1 through D-11 preservation | **PASS** | E06, E04, G01, G03 | all OPEN in both ledgers; nothing promoted; D-7 premise corrected; reviewer scan found no promotion |
| Product and debt boundaries | **PASS** | A06, A07, A08, E05, E06, F01, F03 | no implementation or policy change; overlap claims revalidated twice (2026-10-25 and 2026-10-26) and qualified by scope |
| Edits, if any | **PASS** | F02, F03 | no repository edit was made or eligible; withheld changes have a diff (P1) and a template (P2); P1 and the report were corrected in the scratch area only |
| Final diff and links | **PASS** | F02, F03, G01, G02, G03, F04 | repository diff empty at F02 and F03; hashes, SHAs, blob IDs, counts and line citations re-derived from files and git objects by the author before the review (four mis-cited lines corrected), by the reviewer (about 85 values, G01, G03) and by the author again (G02); no links or publication exist to verify; residual limits in §13 |
| Independent review | **PASS** | G01, G03, §11 | a fresh-context review was performed in two passes; same model family, not human-independent; limits and the post-review edits it did not see are recorded in §11 |
| G4/freeze invariants | **PASS** | §1, §9.4, G01, G03 | statuses stated unchanged; reviewer confirmed in both passes |
| **Overall result** | **BLOCKED** | | partial completion: two mandatory gates are BLOCKED (original-ZIP authentication; archive integrity), so the result cannot be PASS; every other gate passed |

---

## 13. Remaining blockers and exact next actions

**Known:** the repository and PR state (§2); both digest records and where they sit (§4); the exact packet bytes behind a fresh 83/83 (§5); the relationship between the two handoffs (§6); the two ledgers differ only in D-2 and D-5 (§7); all 11 decisions are OPEN in both ledgers (§9).

**Unknown:** the digest and identity of the actual REV3 ZIP; whether the user-side `handoff(1).md` equals the scratch copy; whether the revision-1 archive used for two checker inputs is the archive the user received; real database sizes, legacy states and ghost prevalence; whether anyone intends REV3 to supersede any REV2 document.

**Withheld:** P1, P2, and any change to the REV3 files (§10).

**Smallest missing evidence or authorization, in the order that unblocks most:**
1. The REV3 ZIP attached to a session, or an unaltered `sha256sum` line for it plus a note on how it was produced → unblocks the two BLOCKED gates and lets P2 be completed.
2. A decision on D-A (which document directs the next session) and D-B (which ledger wording) → settles document authority without touching any D-1…D-11 item.
3. Optional authorization for P1.
4. D-1…D-11 stay with the maintainer; nothing in this report moves any of them.

Nothing here is an implementation authorization, a merge recommendation for PR #90, or a statement about freeze readiness.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
