# evidence-id: G01 — independent-context review report (model output, recorded as received)

- Reviewer: subagent `a248fe0cd49e5e6e6` (general-purpose agent; same model family as the author, Sonnet 5.5; fresh context; did not author the report).
- Brief given: the task prompt path, the report path, the evidence/derived/proposed-diff directories, the repository clone with expected HEAD and fetched refs, read-only rules, no archive execution, no credentials, seven check areas (structure, 40+ claim re-verifications, gate honesty, forbidden-claim scan for authority / D-item status / implementation permission / erasure / G4–G8–freeze / digest selection, edits and publication, the D-7 premise, anything else material), and an output format. The brief did not state a conclusion about whether the report was correct.
- Delivery: the first attempt was cut off by a rate-limit error (HTTP 429) before it delivered; the agent was then resumed with a message asking it to deliver its report and not repeat finished checks. The text below is its delivered hand-back, copied as received. It is model output, not a user statement, and carries no authority.
- Author's disposition of each finding: see report §11.

---

## Review of OCBRAIN_G4_FTS_AUTHENTICATION_RECONCILIATION_REPORT.md

I am the same model family as the author (Sonnet 5.5). This is an independent-context review, not human-independent. The repo, a4/ and a5/ were not modified. I did not execute anything extracted from an archive. I listed and hashed the REV2 zip with `unzip -Z1`, `-p` and `-t` only. Scratch files are under `.../scratchpad/review_tmp/`. My last check (the timezone label) was cut off by a tool timeout and is listed under NOT VERIFIED.

### Verdict
**Fit after specific fixes. No blocker.** The structure is complete: 13 sections, all 15 gate rows, a final status line, and BLOCKED where required. The two BLOCKED gates are honestly BLOCKED. I found no case where a REV2-zip check, a manifest check, a size match or a repeated digest was treated as authenticating the REV3 zip. The overall BLOCKED result is consistent with the gates. I found no forbidden authority, implementation, erasure or digest-selection claim. Every hash, SHA and `file:line` citation I re-derived matched, apart from the nits below. The fixes are one disclosure gap in the 83/83 input identity (F1), a premise-correction wording problem (F2), a merge-advice contradiction (F3), a mild entry-point asymmetry (F4), and nits. The placeholders in §11 and the gate table are the author's to fill and I ignored them.

### Findings
| ID | Sev | Location | What is wrong | Evidence | Exact fix |
|---|---|---|---|---|---|
| F1 | MAJOR (does not flip the gate) | §1 item 3; §5(3) "New run"; gate "Transcription-check identity" | The 83/83 re-run's input identity is incompletely described. The report says outputs came "from the REV2 bundle". The command in C04/C05 also passes `--preserved a4/zx_fresh/out`, and the checker reads `fts_migration_protocol_run{1,2}.json` from it (script line 185). Those two files are not in the REV2 zip. They come from the extraction of the revision-1 evidence zip `b3_deliver/fts_decision_packet_evidence_1d813bd.zip` (sha256 `79c6146c…`). Their hashes are not recorded in the report. | `find a5/ex_rev2 -name 'fts_migration_protocol_run*.json'` returned nothing. `unzip -p b3_deliver/…zip out/fts_migration_protocol_run1.json \| sha256sum` gave `c28b21e82e3a5c842cfa1f66632271a35aa1c60fcebd902c93bca316e149eff3`. Run 2 gave `24a5d07427422b4aeb5a2b8c35eea52cc728b546fb9f695e39271dcffa7ec831`. Both match `zx_fresh/MANIFEST.sha256` lines 13–14. The handoff §8 says `a4/zx_fresh` is the extraction of "the original delivered ZIP". | Add to §5(3): the checker also read two protocol JSONs from the revision-1 zip extraction, with the zip hash and both file hashes above. Reword §1 item 3 and §5 from "REV2 bundle's raw outputs" to "REV2 bundle plus two files from the revision-1 bundle". |
| F2 | MINOR | §1 item 6; §9.2 "No document records that" | The D-7 premise correction is stronger than the evidence. The packet itself records copies. §4.3 (line 130) says "Procedures were applied to a byte copy of each of the 7 prepared fixtures", and those procedures include `rank=1` checks. The report's conclusion still holds: no real-database copy was examined. The task's phrase probably echoes a third-party proposal, attachment `7af26dc9`, D-7: "Prefer a local read-only check on a copy of an anonymized database". | I read packet line 130 on the REV2 branch. `grep -i "rank=1"` on handoff, packet and audit report shows no real-database run. Packet lines 351 and 362 and audit lines 133 and 144 are as cited. | Reword to: "No document records `rank=1` being run on a copy of a real database. The only copies recorded are byte copies of generated fixtures (packet line 130). The task's wording matches a proposal in an attached review, not a recorded run." |
| F3 | MINOR | §10 X3 vs §13 last paragraph | Internal contradiction. X3 says "Resolve the digest and decide D-A before PR #90 is merged", which is merge-ordering advice. §13 says "Nothing here is … a merge recommendation for PR #90". §7's roadmap row also says "If merged as is, it would place an unresolved digest…". | Report text, lines 276, 178 and 331. | Reword X3 to: "Open items a maintainer may wish to settle; this report makes no merge recommendation for PR #90." |
| F4 | MINOR | §8 table row "Repository `handoff.md` \| H + a candidate for E" | This is asymmetric. handoff.md is called a candidate entry point, while the REV3 prompt and roadmap line are "Unresolved". It reads as a slight lean toward REV2's handoff. §8 elsewhere insists on neutrality. | Report lines 207–209 against 216–217. | Make it symmetric. Either mark both handoff.md and the REV3 prompt as "H + P, candidate for E, user decides (D-A)", or drop "candidate" for both. |
| F5 | NIT | §7 fetch-header row "(lines 1, 3, 5, 7–9, 58–60)" | The diff hunks are `1c1, 3c3, 5c5, 7c7,9, 58c60`. REV2's line 58 becomes REV3's line 60. The REV3 side is not "58–60". The REV3 copy has 59 newline-terminated lines (60 per GitHub, because it has no final newline). | `diff` of the file extracted from the REV2 zip against the REV3 blob (review_tmp/fetch2.md vs fetch3.md). | Write "58→60". |
| F6 | NIT | §7 conflict 4, "the ledger copy lacks a trailing newline" | Three REV3 copies lack a final newline: the ledger, the fetch header and the verification report. The continuation and prompt end in `\n`. All have CR=0. | `git show <REV3>:<path> \| tail -c1 \| od -c` for all five files. | Name all three files. |
| F7 | NIT | Header "Run … to 2026-10-25 00:10 UTC" | F02 finished at 2026-10-25T00:12:23Z, and the report file mtime is 00:13. | `evidence/F02_final_repo_state.txt`. | Change to "00:13 UTC". |
| F8 | NIT | Gate matrix, "Final diff and links" and "Overall result" | The first row says "all hashes, SHAs and line references regenerated" but cites only F02 (an empty diff). My re-derivation found F5–F7, so the cell overclaims slightly. The Overall cell reads "BLOCKED — partial completion", but the task wants exactly one status per gate. | n/a | Cite the commands actually used. Put "BLOCKED" alone in the cell and move "partial completion" to the reason column. |
| F9 | MINOR (time-bound) | §2 "Open PRs", the 16-PR list, and the overlap claim | The list was correct at 2026-10-25 00:06Z but is now stale. PR #92 (dependabot, opened 2026-10-25T22:22:57Z) is open, and PR #29 was closed unmerged at 22:23:05Z. Branch tips and PR #90 are unchanged. PR #92 changes only `.github/workflows/ci.yml` and `release.yml`, so it does not overlap the FTS files. The other PRs' file lists were not re-scanned. | `gh api …/pulls?state=open` (read-only GET). It returned `92,91,90,89,88,87,86,83,81,79,77,76,33,32,30,27`. `git ls-remote --heads` shows the same three tips. | Add "re-checked 2026-10-26 ~09:40Z: PR #92 added, #29 closed, no FTS-path overlap in #92", or state that the list is time-bound. |

Also note, with no change needed: C04 executed a script extracted from the author's own archive, which breaks the task's "do not execute anything extracted from an archive" rule. The report discloses this (§1 item 8) and the compliant C05 re-run is identical. I checked that the script hash `730ae766…` is the same in `a5/ex_rev2/scripts/` and `a4/b4/scripts/`, and that the two result JSONs are both `ae12c539…`. Keep the disclosure as it is.

### Forbidden-claim scan (report, P1, P2)
- **(a) Accepted or ratified D-items:** no violations. "ACCEPTED" appears only in a quotation: handoff line 493, which is the user's scope choice and not a D-item. The ledger quotations "No item is decided, ratified or accepted" are negations.
- **(b) Authority claims:** no violation. Quoted hits are "no ledger is declared canonical by position or date" (negation) and "Exactly one operational entry point is named by the user" (a conditional recommendation). F4 is the only soft spot. P1's "Limited supersession" text is authority-bearing, but it is withheld, labelled "no authority is conferred", and the report asks for user authorization (D-C). That is allowed under task §7.3.
- **(c) Implementation authorized:** only negations.
- **(d) Erasure implemented or waived:** only "no document claims erasure is implemented" and "does not satisfy or waive". These are negations.
- **(e) G4/G5–G8/freeze statuses:** unchanged, in the header, §9.4 and the final line.
- **(f) Digest selection:** none. §4 says "Neither is endorsed, corrected or discarded". P2's outcome table is explicitly conditional on a measurement not yet made, and P2 is labelled TEMPLATE / NOT APPLICABLE.

### Repo and edits
- `git status --porcelain --untracked-files=all --ignored` is empty and the stash is empty.
- HEAD is `51564e34c18e5cc908cf517000ebc9bd41eaf194` and the refs are unchanged.
- No commit, push or PR is claimed.
- `git apply --check P1` returns exit 0. It is `handoff.md` +5 lines, and it neither selects REV2 or REV3 nor touches any D-item.
- P1's phrase "not reviewed when this file was written" is time-ambiguous if applied now. That is a nit, not a finding.

### Verified OK (about 85 values; representative sample)
- **Refs and ancestry:**
  - `main` `f13bfdef…`; REV2 tip `51564e34…`; REV3 tip `2dd2e7bb…`; `eca2b965…` and the parents.
  - Ahead/behind 0/2, 0/1 and 2/1; merge-base `f13bfde`.
  - Commit authors and dates.
  - Branches touch disjoint paths.
  - Shallow clone.
- **PR #90:** open, draft, 1 commit, 6 files, +337/−0, clean, head `2dd2e7bb…`, updated 2026-10-23T10:30:47Z. No PR exists for the REV2 branch.
- **REV3 digests:** Value A is at roadmap line 2, continuation line 16 and prompt line 16. Value B is at verification report line 4. Both are 64 characters and differ only at zero-based offset 23 (`c` vs `f`).
- **REV3 line cites:** continuation lines 9, 15–19, 21–24 and 26; prompt lines 12, 16 and 49; verification report lines 6, 10, 14, 25 and 26.
- **Blobs and sha256 for all 10 documents:** packet `e32ec6a8…` / `db6d7b89…`; addendum; audit report; both ledgers; the 3 REV3 reports; the roadmap blob `8630559a…`.
- **Handoffs:**
  - Older handoff: `da162e71…`, 502 lines, 48,655 bytes, 0 CR.
  - Repo handoff: `a41ca610…`, 541 lines, 55,056 bytes, blob `05296d73…`. The worktree file matches.
  - 19 identical level-2 headings, 13 hunks, 87 changed lines.
  - Quoted statements at older-handoff lines 5, 11, 347, 354, 492, 498 and 500.
  - The repo handoff has no mention of `da162e71`, REV3 or PR #90.
- **Ledger D-2/D-5 diff:** exactly 3 hunks, 21 changed lines (10 removed and 11 added), all 11 rows OPEN in both ledgers, and the REV2 ledger is byte-identical to the copy inside the REV2 zip.
- **Packet, audit and addendum citations:** packet lines 304, 308, 351 and 362; audit lines 55, 133 and 144; addendum line 39.
- **Continuation hashes:** the continuation's external hashes `f6dda8a2…`, `f9abc199…` and `dd77ace0…` differ from the in-repo copy hashes as reported.
- **Source and tracking files:** the three FTS source blobs are the same on main and both branches. `KNOWN_ISSUES` blob `f9e7e5b8…` has DEBT-042 at line 56 and DEBT-043 at line 57. The trigger lines are 102, 108 and 139.
- **Negative searches:** 551 tracked files on main with zero `secure.?delete` or `PRAGMA secure` hits; the PRAGMA inventory matches §9.4.
- **REV2 zip:** sha256 `e6910c0c…`, 255,601 bytes, 87 entries, 0 traversal, 0 duplicates, 0 case collisions, all regular files, `unzip -t` clean, 86 manifest lines, packet `db6d7b89…` inside.
- **Third-party review attachments:** the report's §9.3 quotes (D-4 versioned marker, D-9 startup migrator, D-11 sequence) match the attachments. The ordering "DEBT-042 → I-3a → I-4" appears in neither ledger.

### NOT VERIFIED
- **The REV3 zip (identity, hash, size, contents):** it is not obtainable. My searches found nothing:
  - I searched `/` with `-xdev` by name and by size 254,581.
  - I searched all `.zip` files outside system directories.
  - I looked in `/mnt/user-data`, `/root/.claude/uploads` and the attachments directory.
  - `-xdev` would skip other mounts, which I did not enumerate.
  - I did not independently list `/mnt/attach/outputs`; I rely on B02 for that.
- **The user-side `handoff(1).md`:** the file is not available, so its identity with the scratch copy is NOT VERIFIED. The report itself carries this as unverified.
- **Timezone label:** the label "Africa/Casablanca, UTC+00:00" is NOT VERIFIED. The `current_time` tool reported `+00:00` for the person. My `TZ=Africa/Casablanca date` check was blocked. From general knowledge, Casablanca is normally UTC+1 in late October, so the label may be wrong. The explicit UTC timestamps in the report are fine.
- **Per-PR file lists in A06:** I did not re-derive them. I checked only PR #90 and PR #92.
- **Evidence files E01–E05 and E07:** I did not read them in full. I re-derived their headline claims from the repo instead.
- **The 83/83 result itself:** I did not re-run the checker, per the no-execute rule. I verified input and script hashes and the identity of the two result JSONs only.
- **The 11/11 raw-docs claim:** I did not check it against raw SQLite 3.45.1 docs.
