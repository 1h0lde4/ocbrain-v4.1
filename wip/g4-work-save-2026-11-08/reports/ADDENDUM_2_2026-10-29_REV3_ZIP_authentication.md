# Addendum 2 — 2026-10-29 — The REV3 ZIP was supplied and measured

Addendum to `OCBRAIN_G4_FTS_AUTHENTICATION_RECONCILIATION_REPORT.md` (sha256 `a331f6b2b242b2c031b7a84c66ef178d64b940df228545483ed15a0e8abc8318`) and to Addendum 1 (2026-10-28, sha256 `cb4cd825b2046c68403a25874da7d203d171e922559392075d2af0aa903f76b6`). The earlier report is not edited. This addendum records what the supplied archive shows and lists exactly which statements of the report and of Addendum 1 it supersedes. Evidence: `I01`–`I14` (commands, UTC times, exit status, unaltered output), delivered in `g4_rev3_zip_authentication_evidence_I01-I14.zip` (sha256 `fe76697be7a446d5d09e53aa1cf398447f8c9b954053ab380e8ea4b2119a7d1d`) beside this addendum; I10–I14 were recorded on 2026-10-30 (see §9). `I15` (first mechanical check of this text, which failed on two points and is kept) and `I16` (the final run) are delivered as separate files because they check this text, which cites the bundle's hash.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. No file in the repository was changed, and no commit, push, PR update or merge was made.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what a document says; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **The supplied file's digest is Value B.** The attached `…D2_D5_FETCH_HEADER_REV3.zip` is 254,581 bytes and its SHA-256 is `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc` [OBSERVED, I01, I02]. An exact string comparison says it equals Value B (the verification report's) and does not equal Value A (the roadmap's, the continuation's and the next-session prompt's); it differs from A at zero-based offset 23 only (one-based position 24). I did not choose between the values by repetition or plausibility; the measurement decides it for these bytes.
2. **So the three records of A do not match the measured bytes.** If the supplied file is the artifact REV3 describes, A is a transcription error at offset 23. The consistency checks in §4 support that the supplied file is that artifact (size, entry counts, the three-file difference from the earlier bundle, and two inner-file digests that REV3 recorded separately). They do not prove it: identity rests on the user's attachment and those consistencies.
3. **The archive is intact and as described.** 87 entries, no unsafe paths, `unzip -t` clean, `MANIFEST.sha256` verifies 86/86 with nothing unlisted or missing, extracted into a new empty directory and never executed [OBSERVED, I02, I03].
4. **Relative to my REV2 bundle exactly three files differ** (`MANIFEST.sha256`, `report/decision_ledger_1d813bd_OPEN.md`, `docs/doc_fetch_quotations_as_returned.md`); file names are identical (87 = 87); the packet, audit report, checker script and run outputs are byte-identical [OBSERVED, I04].
5. **The 83/83 transcription check passes**, but not on the archive's data alone. It ran my own pre-packaging copy of the script (hash `730ae766…`, identical to the copy inside the archive, which I did not execute) on: the exact packet bytes (commit `51564e3`, `db6d7b89…`, equal to the archive's copy); the archive's `out/` files; two protocol-run JSONs (`fts_migration_protocol_run1.json`, `…run2.json`) taken from the earlier revision-1 bundle, which are not in this archive's `out/`; and a read-only git worktree at `1d813bd`. The result JSON (`ae12c539ee7296595d535c01e4ae50c7337981d720b24082ee58522537d9f257`) is byte-identical to my earlier run and to the archive's own `out/rev2_numbers_check_run4.json` [OBSERVED, I06 and the file hashes in I04].
6. **The two formerly BLOCKED gates now pass**, one of them as a qualified PASS (§6). The overall result is determined in §6. Nothing here resolves G4 or any D-item.

## 2. Identity and measurement [OBSERVED]

| Item | Value | Evidence |
|---|---|---|
| File as supplied | `/mnt/user-data/attachments/d441201d-0373-573d-8f64-186072f858d3/b5f4720b-fts_decision_packet_errata_evidence_1d813bd_D2_D5_FETCH_HEADER_REV3.zip` (regular file, 1 link, mode 600) | I01 |
| File time | 2026-10-29 08:36:47Z, which [DERIVED] corresponds to when the user attached it | I01 |
| Size | 254,581 bytes (matches the recorded size) | I01 |
| SHA-256 | `f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc` | I01, I02 |
| Equals Value A / B | A: **False**; B: **True** (exact comparison) | I02 |
| Differs from A at | zero-based position 23 only (one-based 24): `c` in A, `f` measured | I02 |
| Type | "Zip archive data, at least v2.0, deflate" | I01 |

Provenance limit: the digest identifies these bytes. It was not produced by me, and I cannot see how the user's copy was created or transferred; the user said it is the REV3 ZIP.

**Judgment call, flagged for the user [DERIVED].** The task (§5.3) lists "provenance is inadequate" among the reasons to mark original-artifact authentication BLOCKED, and says a correct hash does not by itself show the bytes are the historically intended artifact. I judged the available provenance adequate for a **qualified** PASS because: there is exactly one candidate in the attachments directory (I01) and no competing file of the same name there; the size and the entry and manifest counts equal what REV3 recorded; the digest equals one of the two recorded values (B); two inner-file digests that REV3 recorded separately (continuation lines 21–22) equal the archive's inner files; and the three-file difference REV3 states matches the observed difference from the earlier bundle. What I cannot observe is the chain of custody from the packaging run to the user's copy. A stricter reading would hold *Original ZIP authentication* at BLOCKED until that chain is documented (for example, the `sha256sum` line the user recorded when the file was created or downloaded); the overall result would then be BLOCKED again, and the gates and proposals that depend on the artifact's identity (archive integrity and contents, the REV3-packet transcription gate, the ZIP part of the comparison, P2 and P3) would be BLOCKED or conditional too; the observations themselves would not change.

## 3. Archive safety and integrity [OBSERVED]

- **Inspected without extraction first** (Python `zipfile` listing; nothing executed): 87 entries, 87 regular files, 0 directory entries; 0 absolute, backslash or drive paths; 0 parent-traversal paths; 0 duplicate names; 0 case collisions; 0 symlinks; 0 special-mode entries; 0 encrypted entries; no ZIP comment; compressed 241,591 bytes, uncompressed 1,272,348 (ratio 5.27); largest entry `out/fts_commit_boundary_run1.json` (121,672 bytes); `testzip()` returned no bad member; `unzip -t` exit 0 [I02].
- **Extracted** into a new, empty directory (`a6/ex_rev3`): 87 regular files, 0 non-regular, 0 symlinks [I03].
- **Manifest** (`MANIFEST.sha256`, 86 lines; compared with the archive, not independent proof of intent): `sha256sum -c` exit 0, 86 OK, 0 failed; no file present but unlisted (other than the manifest itself); no listed file missing [I03].
- Limits: the manifest lives inside the archive; a passing manifest does not authenticate the archive. Nothing extracted from the archive was executed; the checker run in §1 item 5 used my own source copy of the script and read the archive's files only as data.

## 4. Checking REV3's claims against the archive

| REV3 claim (where) | Result | Evidence |
|---|---|---|
| ZIP SHA-256 is B and size 254,581 (verification report lines 4–5) | **Matches** | I01, I02 |
| ZIP SHA-256 is A (roadmap line 2; continuation line 16; prompt line 16) | **Does not match** (offset 23) | I02 |
| 87 archive entries; 86 manifest entries (report line 6; continuation line 18) | **Matches** | I02, I03 |
| 0 absolute or parent-traversal paths (report line 12) | **Matches** (and the further checks in §3) | I02 |
| `sha256sum -c MANIFEST.sha256`: 86/86 OK (report line 14) | **Matches** (my own run) | I03 |
| Packet and audit-report hashes unchanged (report lines 17, 25–26) | **Matches**: `report/…packet…REV2_PROPOSED.md` = `db6d7b89b0ec7a32341fe9749cbea46f55f713f16392783b311d96f582857ee2` and `report/evidence_audit_report_1d813bd.md` = `2dc09f0d1d89d2613d1dd56d3e0a34753492319efd1018c7ef295b0faad028af`, both equal to the copies in the repository at `51564e3` | I04 |
| Exactly three inner files changed relative to the earlier archive; none added or removed (report line 18) | **Matches**, taking "the earlier archive" to be my REV2 bundle (`e6910c0c…`): differing files are `MANIFEST.sha256`, `report/decision_ledger_1d813bd_OPEN.md`, `docs/doc_fetch_quotations_as_returned.md`; names identical | I04 |
| Revised ledger SHA-256 `f6dda8a2515b4e91…` and fetch-quotation header SHA-256 `f9abc19929958da8…` (continuation lines 21–22) | **Match** the archive's inner files (`f6dda8a2515b4e9117906e3982cd0dcc6f338c84318ab62d1e2970c9d6c12c16`; `f9abc19929958da8d4fda8b9235447860956d4f38dc3e3290f02dd0531b75ecc`) | I04 |
| The in-repo copies differ from those digests because the connector normalised line endings (REV3's explanation) | **Partly observed**: each archive file equals its in-repo copy plus exactly one final newline, and neither side contains a CR. REV3's connector explanation itself cannot be tested from here. | I05 |
| Fresh-extraction verification report SHA-256 `dd77ace0e170c336…` (continuation line 23) | **Cannot be checked from the ZIP**: the README (line 25) says the verification report and the handoff are delivered beside the ZIP, not inside it. The in-repo copy hashes to `1fc6999b…`; the disk original was not supplied. | I05, README |
| Final 83/83 transcription check on packet `db6d7b89…`; the packaging pass did not re-run it (continuation lines 20 and 26; prompt line 49; report line 25) | **Consistent**, and now run: 83/83, exit 0, with the inputs listed in §1 item 5; result JSON `ae12c539ee7296595d535c01e4ae50c7337981d720b24082ee58522537d9f257`, byte-identical to my earlier run and to the archive's `out/rev2_numbers_check_run4.json` | I06 |
| "11/11 passages found in the raw 3.45.1 docs" (ledger D-2/D-5 wording; archive `docs/raw_sqlite_docs_verification.md`) | **Partially independent**: eleven expected fragments, chosen by me from the verification file (including two single tokens, `SQLITE_CORRUPT_VTAB` and `secure-delete`, and the phrase "earlier than 3.42.0"), are all present in the archive's raw HTML excerpts (second, corrected run, I08). My first attempt found 9/11 because my checker inserted a space before punctuation after inline tags; the raw HTML shows both passages verbatim, so that was a flaw in my check, recorded as it happened (I07). Limit: the excerpts are inside the archive; I did not re-verify that they come from the signed Ubuntu `sqlite3-doc` package, and the live sqlite.org pages were not read. | I07, I08 |

Nothing in these results makes any evidence "correct" beyond the checks run: they show transcription and archive consistency, not that the probes' conclusions are right.

## 5. What this addendum supersedes

The earlier report and Addendum 1 stand as records as of their stated times. Only the statements below are superseded; each is quoted from the file.

| Where | Superseded statement | Now |
|---|---|---|
| Report §1, line 14 | "**Overall result: BLOCKED — partial completion.** Two mandatory gates are BLOCKED because the REV3 ZIP is not available to this session: original-ZIP authentication and archive integrity of that ZIP." | The ZIP was supplied; both gates are PASS (§6, the first with a stated qualifier). The overall result is stated in §6. |
| Report §4 (line 116) | "**Gate status: original-ZIP authentication — BLOCKED.** Missing: the REV3 ZIP itself (or an unaltered `sha256sum` output on it with provenance)." | The ZIP was supplied and hashed (§2); qualified PASS (§6). The "smallest unblocker" it names was done. |
| Report §5, "Gate statuses" (line 139) | "archive integrity and contents — **BLOCKED** (for the REV3 ZIP; the REV2 ZIP passed as a reference only)." | **PASS** for the REV3 ZIP (§3, §4, §6). |
| Report §8 matrix, REV3 evidence ZIP row (line 217) | "S, immutable, **unauthenticated** \| not available" | Supplied and measured; identity as the intended artifact is supported, not proven. The authority category S is unchanged. |
| Report §8 (line 230) | "someone with the REV3 ZIP must hash it (§4)." | Done (I01, I02). |
| Report §10, X2 (line 280) | "2, blocked by the missing measurement, on a branch owned by PR #90 \| **Withheld.** … (not a patch; cannot be completed)" | The measurement exists. P2 is now completed (as a proposal) and P3 is proposed (§7); both stay **withheld** until the user authorizes a target and a path. |
| Report §1 item 1 (line 18); §12 gate *Original ZIP authentication* (line 327); §4 | "The REV3 ZIP cannot be authenticated here." / BLOCKED | Qualified **PASS**: the ZIP was supplied, identified and hashed (§2). The gate's own wording is "original identified and hashed, or explicitly BLOCKED". The identity of the bytes as the intended artifact is supported, not proven. |
| Report §1 item 1 (line 18) | "Both recorded digests are therefore preserved, and neither is selected." | Both strings stay preserved where they are recorded in the repository. For the supplied bytes the measurement selects B. |
| Report §1 item 2 (line 19); §4 (line 114); §7 conflict 1 (line 189) | "only hashing the actual ZIP resolves it" / "Neither is endorsed, corrected or discarded." / "Digest: A against B inside REV3 (§4)." | Resolved **by measurement** for the supplied bytes: B matches, A does not. The report's statement "Repetition across files is not evidence" stands. |
| Report §1 item 3 (line 20) | "…and it says nothing about the REV3 ZIP." | True of that earlier run. A separate run on this archive's data now exists (I06, §1 item 5). |
| Report §5(1) (line 125) and §5(2) (line 129) | "REV3 ZIP: BLOCKED (§4)." / "REV3 ZIP: BLOCKED. REV3's own claims of '87 entries / 86 manifest entries / 86/86 OK' … are unverifiable here." | Checked and matching (§3, §4). The claims that concern files outside the ZIP (the verification report's disk original) remain unverifiable. |
| Report §7, verification-report row (line 180) | "Every statement about the ZIP is unverifiable here." | Statements about the ZIP are checked in §4; those about files outside it are not. |
| Report §7, REV2-ZIP row (line 186) | "REV3 ZIP is a different, later, unavailable bundle" … "cannot be checked without the ZIP." | The ZIP is supplied; the three-file claim matches (I04). |
| Report §7 conflict 4 (line 192) | "…but the disk files are not available to confirm it." | For the ledger and the fetch header: the archive file equals the in-repo copy plus one final newline (observed, I05); REV3's connector explanation is not testable. For the verification report: the disk original was not supplied; unchanged. |
| Report §12, Overall result (line 339) | "**BLOCKED** … partial completion: two mandatory gates are BLOCKED (original-ZIP authentication; archive integrity), so the result cannot be PASS; every other gate passed" | See §6 and §8; the result is stated there after the review. |
| Report §12 (lines 327, 328, 330) | *Original ZIP authentication* BLOCKED; *Archive integrity and contents* BLOCKED; *REV2/REV3 comparison* reason "contents of the REV3 ZIP not compared (unavailable)" | See §6. The comparison gate now also covers the ZIP's contents (I04, I05). |
| Report §12 line 329 | "…the REV3 claim is qualified as unverified" (transcription-check identity) | The claim is now consistent with a run on the archive's inputs (I06, with the other inputs named in §1 item 5). |
| Report §13 (line 347) and (line 352) | **Unknown:** "the digest and identity of the actual REV3 ZIP" / smallest missing evidence item 1 "The REV3 ZIP attached to a session…" | The digest is known (B). Identity as the intended artifact is supported, not proven. The missing evidence was supplied. |
| Addendum 1 §1 and §3 | "*Original ZIP authentication* and *Archive integrity and contents* stay **BLOCKED**. The two digest records … remain unresolved; neither is selected." / "What would unblock the two BLOCKED gates" | Done; see §1 and §6 here. |
| Addendum 1 §2 | the `main` snapshot (`6e411877…`, "51 behind, 1 ahead", the PR list) | Stale: see §9 for the re-measured state. |

## 6. Gate matrix after this addendum

Exactly one status per gate. "Evidence" cites the report's IDs and this addendum's. A qualifier, where one applies, is in the Reason cell; the status cell carries only the allowed word.

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Live repository and PR inventory | **PASS** | report A01–A08, F01–F03; H02–H03; I10–I12, I14 | unchanged by this request; `main` has moved at least three times since the report (`f13bfde` → `6e41187` → `7bb0ce2` → `16d663a`) and the re-measured state is recorded (§9); PR data is time-bound |
| Target and scope | **PASS** | A09; I10 | no write target was used; this request also made no repository write |
| Original ZIP authentication | **PASS** | I01, I02 | qualified PASS: bytes measured; digest = Value B ≠ Value A; identity of the bytes as the intended artifact is supported by consistency checks (§4), not proven; the stricter reading and the chain-of-custody gap are stated in §2 |
| Archive integrity and contents | **PASS** | I02–I08 | safe inspection, 86/86 manifest, no unlisted or missing file, content compared with the REV2 bundle and with REV3's claims; limits in §3, §4 |
| Transcription-check identity | **PASS** | C01–C05, I06 | new 83/83 on the exact packet bytes, a hash-recorded script not taken from the archive, the archive's `out/` files, and the other inputs named in §1 item 5 |
| REV2/REV3 comparison | **PASS** | report E01–E04, D03; I04, I05 | the REV3 repository files and now the REV3 ZIP contents are compared |
| Handoff provenance | **PASS** | report D01–D03, E07 | unchanged: the user-side `handoff(1).md` was not supplied, so its identity with the scratch copy stays unverified |
| Document-authority analysis | **PASS** | report §7, §8 | unchanged; no authority change; D-A and D-B remain with the user |
| D-1 through D-11 preservation | **PASS** | report E06, E04; G01, G03; this addendum | all OPEN in both ledgers; nothing promoted |
| Product and debt boundaries | **PASS** | report A06–A08, E05, E06, F03; H02–H04; I11, I12 | no implementation or policy change; overlap claims revalidated 2026-10-26 and 2026-10-28, and on 2026-10-30 only for the three FTS source blobs on `main`, the paths changed on `main`, and PRs #100 and #101; all qualified by scope |
| Edits, if any | **PASS** | I09, I10, I13 | no repository edit was made or eligible; P2 (completed) and P3 are proposals only |
| Final diff and links | **PASS** | I09, I10, I13 | repository diff empty (I10); P3 `git apply --check` OK in a scratch directory before and after its condition note was added (I09, I13); no links or publication exist |
| Independent review | **PASS** | §8; report G01, G03 | fresh-context review in two passes on this addendum; same model family, not human-independent; the post-review edits it did not see and its stated limits are in §8 |
| G4/freeze invariants | **PASS** | §1, §9 | statuses stated unchanged |
| **Overall result** | **PASS** | | every mandatory gate above is PASS under the stated qualifiers; depends on the judgment call in §2 (stricter reading: BLOCKED); not a statement that G4 is resolved or freeze-ready |

## 7. Proposals (not applied; no authorization is implied)

- **P2 (completed)** — `P2_digest_discrepancy_erratum_COMPLETED_PROPOSED.md` (sha256 `0c9fa6362e6a3ae57534f2df6e7d4bae6f45dbf8ba1fa89ed51023b3a38c71f7`): the earlier conditional template with the measurement filled in (outcome: equals B), and a table recording the four elements any correction must carry: original claim, verified observation, affected file/revision, reason. A new erratum file for the REV3 branch; category 2 on files owned by draft PR #90.
- **P3** — `P3_rev3_digest_value_A_to_B.patch` (sha256 `9a27fcf2d5801e802dca7e818a917404c4fd4185c395afa1f0ca30483cafcc60` with the note): replaces Value A with Value B at the three places that record A (`IMPLEMENTATION_ROADMAP.md` line 2; `G4_FTS_CORRECTNESS_CONTINUATION_REV3.md` line 16; `NEXT_SESSION_PROMPT_REV3.md` line 16). 3 files, 3 one-line hunks, one character each; `git apply --check` exits 0 in a scratch directory holding the originals, and applying it there yields exactly the intended text (I09). **Condition:** P3 may be applied only together with P2, or with a commit message or erratum that records the original claim (A and its locations), the verified observation (the measurement), the affected file and revision, and the reason. Applied alone it would silently replace every occurrence of a wrong digest, which the task forbids. The patch file now carries this condition as a note above its first file header (git ignores it; the diff body is byte-identical, I13), so its hash changed from `d70f712ef71bba3ffc219c8bef588f4e25c2a7f003e5ffa4f9532265fd5d72a7` (the version I09 and the first review pass checked) to the value above; the second review pass checked the new version.
- **P1** (the `handoff.md` provenance note) is unchanged and still withheld.
- All three are withheld until the user authorizes a target and a path. They are category 2/3 changes on the branch of PR #90 (author `1h0lde4`). They do not touch any D-item, ledger, G4–G8 status or the choice of entry point (D-A).

## 8. Independent review

**Reviewer:** a fresh-context subagent (`aa2b43dbf5a8381b3`), same model family as the author, so this is an independent-context review and not a human-independent one. In pass 2 it was given the files and the checks to run, not the conclusion (pass 1's briefing is in the session transcript). The earlier reviewer of the 13-section report is recorded in that report's §11 and in evidence G01/G03; this section covers Addendum 2 only. Usage-limit interruptions occurred earlier in the session and were handled by resuming the reviewer.

| Pass | Reviewed | Verdict | Findings (reviewer's severities) | Disposition |
|---|---|---|---|---|
| 1 | the first draft of this addendum, P2 (completed), P3 | fit after specific fixes | F1–F3 MAJOR (83/83 input wording; P3 against the task's digest-replacement rule; a bundle claim that was false at the time), F4–F9 MINOR, F10–F11 NIT | all eleven verified by the author where checkable and applied. One deliberate deviation: the F8 qualifier sits in the Reason cell, not the status cell, because the task fixes the status vocabulary; the reviewer agreed in pass 2. |
| 2 | the revised addendum, P2, P3 with its condition note, the I01–I13 bundle | fit after minor fixes; no blocker, no major | N1–N3 MINOR (an overstated sentence on the stricter reading; "moved twice" against §9; five stale report statements missing from §5), N4–N7 NIT | all seven checked by the author (report lines 116, 139, 217, 230, 280, 339; PR #90 author login; I13 timing) and applied. |

In pass 2 the reviewer re-measured the §9 state with read-only API calls at 2026-10-30 08:56Z and found nothing moved since I10–I12 (its live `mergeable_state` for PR #90 was "behind" where I10 recorded "unknown"; GitHub computes that field lazily and no claim here depends on it). It also confirmed the bundle manifest (26/26), the P3 apply-check in its own scratch copy, the quotes and line numbers in §5, and a forbidden-claim scan (no D-item decided, no authority or entry point granted, no implementation cleared, no freeze readiness, no commit, push or PR implied).

**What the reviewer did not see:** the N1–N7 text changes; the one clause added to P2 (N7), which changed P2's hash; the addition of I14 (a read-only record of the four `main` tips named in §9, added because the first mechanical check found one full SHA without a recorded source); the rebuilt and renamed bundle I01–I14 (hash in the header; manifest re-verified by the author after extracting it into a new directory); the bundle and P2 hashes in the header and §7; and this section with the two cells it fills. These are corrections the reviewer asked for and record-keeping; the author checked them mechanically (I15, I16). They were not reviewed again.

**What the reviewer could not verify:** the user's wording and the attach time (they rest on the session record); the chain of custody of the user's copy; whether the revision-1 bundle behind the two protocol-run JSONs is the one the user received; that my pre-packaging script copy is the one used before packaging beyond its hash matching the archive's copy; the seventeen PRs not re-scanned on 2026-10-30.

**Result:** the gate is PASS with those limits. The overall result is PASS on the reading that every mandatory gate passes under the stated qualifiers. It depends on the flagged judgment call in §2: under the stricter reading the overall result would be BLOCKED. It is a statement about this reconciliation task, not about G4: it does not resolve G4, decide any D-item, clear any implementation, or declare freeze readiness.

## 9. What remains, and what this does not show

**Decisions that are still the user's:** D-A (which document directs the next session); D-B (REV2 or REV3 ledger wording for D-2/D-5); whether to authorize P1, and P2 and/or P3 (with the §7 condition); D-1…D-11 (all OPEN).

**Still unknown or unverified:** the user-side `handoff(1).md` (not supplied); the disk original of the REV3 verification report (`dd77ace0…`); whether the revision-1 archive behind the two protocol-run inputs of the checker (Addendum 1 / report §5) is the archive the user received; how the user's copy of the REV3 ZIP was created and transferred; real database sizes, legacy states and ghost prevalence; behaviour on other SQLite builds; whether the Ubuntu documentation excerpts come from the signed package (not re-verified here).

**Time-bound repository state, re-measured 2026-10-30 08:50–08:51Z [OBSERVED, I10–I14]** (read-only GitHub API calls and local `git` reads; nothing fetched into or written to the clone; the `sqlite_storage.py` line in I10 is a 404 from a wrong path, kept unaltered, and I11 holds the valid blob measurement):

- Working clone: branch `docs/g4-fts-errata-handoff-oct2026`, HEAD `51564e34c18e5cc908cf517000ebc9bd41eaf194`; `git status --porcelain` empty, `git diff` and `git diff --cached` empty, stash 0. The remote tip of that branch is the same commit.
- `main` is `16d663ac8449965f774033da46d5063506a772a7` (merge of PR #97, 2026-10-29T23:00:46Z). It was `7bb0ce2fd4b9557e56258f66d9f3e6b0e7bdca68` (merge of PR #96, 2026-10-29T10:50:01Z) and, at 2026-10-28 14:10Z, `6e411877e426646f3c40892c75f407991b4d235b` (merge of PR #89); at the original audit it was `f13bfdefcdd197ed1f966de0b1f93037a4168af4`. `main` is 59 commits ahead of `f13bfde`.
- The three FTS source blobs on `main` are unchanged: `core/memory/backends/sqlite_storage.py` `ed0cbae6…`, `core/memory/knowledge_entry.py` `0d5e0716…`, `core/memory/unified_memory.py` `eb2bbe17…`. The files changed on `main` since `f13bfde` are `KNOWN_ISSUES.md`, `core/context.py`, `core/merger.py`, `core/orchestrator.py`, `core/workers/planner.py`, `interface/api.py` and six test files; none matches `sqlite_storage`, `unified_memory`, `knowledge_entry` or `core/memory/`. The DEBT-042 row is still present in `KNOWN_ISSUES.md` on `main` (now line 62; it was line 56 in Addendum 1). I did not re-read the register beyond that row.
- REV3 branch tip is still `2dd2e7bb05db949a6156266cfa3430c58de09922`: 1 commit ahead and 59 behind `main` (diverged). PR #90 is open, draft, head `2dd2e7bb…`, base `f13bfde…`, last updated 2026-10-23T10:30:47Z.
- Open PRs are 101, 100, 94, 93, 92, 91, 90, 88, 87, 86, 83, 81, 79, 77, 76, 33, 32, 30, 27 (19). New since Addendum 1: #100 and #101 (both DEBT-014; they touch `core/cognitive/learning.py`, `scripts/check_drift.py` and two test files; no FTS-relevant path). I did not re-scan the other seventeen on this date; their last path scan was Addendum 1's.
- The REV3 archive README still names `main` as `f13bfde…`, which is historical.

**What this does not show:** it does not close G4, does not show the probes' conclusions are right, does not make any D-item decided, does not clear any implementation, does not declare freeze readiness, and says nothing about the physical-erasure requirement (RD-10, DEL-1…4), which stays outstanding.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
