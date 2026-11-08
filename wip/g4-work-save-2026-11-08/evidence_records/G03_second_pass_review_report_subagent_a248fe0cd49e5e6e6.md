# evidence-id: G03 — second-pass independent-context review (model output, recorded as received)

- Reviewer: the same subagent as G01, `a248fe0cd49e5e6e6` (same model family as the author, Sonnet 5.5). Resumed with a narrow brief: re-read the passages edited after G01, re-verify the new factual claims, re-run the forbidden-claim scan over the whole report plus P1 and P2, confirm the repository is unchanged. §11 and the Independent-review gate row were still placeholders when it ran.
- Delivery: the first resume attempt failed on a rate limit (HTTP 429); the retry on 2026-10-27 delivered the report below, copied as received. It is model output, not a user statement, and carries no authority.
- Author's disposition of N1–N4: see report §11.

---

## Second-pass review of the corrected report

I am the same model family as the author (Sonnet 5.5). This is an independent-context review, not human-independent. I ran read-only commands only. I did not apply P1, run `git apply` without `--check`, or execute anything from an archive.

### Verdict: FIT (nits only)
Every correction I asked for was made and is accurate. I found no new blocker, major or minor problem. The edits did not introduce any forbidden wording or any contradiction in the corrected passages. Four nit-level residues remain, listed below. They are optional and do not change any gate.

### Re-verified (all match the report)
- **Protocol-run files:** `fts_migration_protocol_run1.json` is `c28b21e82e3a5c842cfa1f66632271a35aa1c60fcebd902c93bca316e149eff3` and `run2.json` is `24a5d07427422b4aeb5a2b8c35eea52cc728b546fb9f695e39271dcffa7ec831`.
  - The hashes are the same whether read from inside the revision-1 zip or from `a4/zx_fresh/out`.
  - They match `a4/zx_fresh/MANIFEST.sha256` lines 13–14.
  - The checker's only `A.preserved` use is script line 185.
  - The files are not in the REV2 zip, as I found in the first pass.
- **Revision-1 zip:** `b3_deliver/fts_decision_packet_evidence_1d813bd.zip` is sha256 `79c6146c609a76548260f261f05692d32bbd32f44694b430a096a48a079d2721` and 79,260 bytes.
- **Fetch-header hunks:** the diff gives `1c1, 3c3, 5c5, 7c7,9, 58c60` (REV2 line 58 becomes REV3 line 60). That matches the report's "REV2 lines 1, 3, 5, 7 and 58 against REV3 lines 1, 3, 5, 7–9 and 60" and "59 newline-terminated lines, 60 by the hosting count". I verified this in the first pass and G02 re-confirms it.
- **Final newlines:** the ledger, the fetch header and the verification report lack a final newline. The roadmap, continuation and prompt end in `\n`. All have CR=0.
- **PR state:**
  - The open PRs are `92,91,90,89,88,87,86,83,81,79,77,76,33,32,30,27`.
  - PR #29 is closed and unmerged (closed 2026-10-25T22:23:05Z).
  - PR #92 is the dependabot `actions/setup-python` bump (created 2026-10-25T22:22:57Z). It changes only 2 files, both workflows.
  - PR #90 is open, draft, head `2dd2e7bb…`, 1 commit, 6 files, updated 2026-10-23T10:30:47Z.
  - PR #91 is titled "fix(test): enforce registry roots and isolate config (DEBT-012)".
- **F03 path scan:** I re-ran it live over all 16 PRs. No PR matches `sqlite_storage|unified_memory|knowledge_entry|core/memory/`. The tracking-file list matches §2: KNOWN_ISSUES.md in #91, #89, #88, #87, #83, #81 and #79; CURRENT_STATE.md also in #88; IMPLEMENTATION_ROADMAP.md in #90. No PR has more than 100 files (#91 has 15), so pagination does not matter.
- **Attachment quotation:** attachment `7af26dc9` line 136 reads: "Use a local copy of a real database for the read-only `rank=1` consistency check, inside a rolled-back transaction…". The §9.2 and §1 item 6 excerpt is accurate, and the report correctly calls it a proposal.
- **P1:** `git apply --check` exits 0, and `--stat` shows `handoff.md | 5 +++++`. The new phrase "That set was not reviewed in the session that wrote this file" fixes the time ambiguity I flagged. P1 still selects neither REV2 nor REV3 and touches no D-item.
- **Repository:** the repo is unchanged.
  - HEAD is `51564e34c18e5cc908cf517000ebc9bd41eaf194`.
  - `status --porcelain --ignored` has 0 lines.
  - Both diffs are empty and the stash count is 0.
  - The local and remote refs are unchanged: `main` is `f13bfdef…` and the REV3 tip is `2dd2e7bb…`.
  - The reflog shows only the two earlier commits.
  - The report claims no commit, push or PR.
- **G01:** the evidence file carries the 9 findings F1–F9 and records the model-family limitation. I only spot-checked it, not line by line.

### Forbidden-claim scan (whole report, P1, P2)
No violations:
- **Accepted or decided D-items:** none. Quoted ledger text "No item is decided, ratified or accepted" and the handoff's "ACCEPTED by the user (scope choice)" are quotations.
- **Authority and entry point:** the new §8 labels are symmetric and conditional. The REV3 prompt reads "H + P (operational wording); candidate for E only if the user decides (D-A)" and the repository handoff.md reads "H + P (transfer record); candidate for E only if the user decides (D-A)". The roadmap line stays "Unresolved". "No ledger is declared canonical" is a negation. D-A is posed as a question to the user.
- **X3 and the roadmap row:** the new X3 reads "open items a maintainer may wish to settle… no merge recommendation for PR #90". The roadmap row says "records a digest that conflicts with another record on the same branch… no user authorization is evidenced". Neither contradicts §13's "not a merge recommendation", so my earlier F3 contradiction is resolved.
- **Implementation:** only negations.
- **Erasure:** only "does not satisfy or waive" and "no document claims erasure is implemented".
- **Status line:** G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED stays intact in the header, §9.4 and the final line.
- **Digest:** neither value is picked. P2 is a conditional template and says so.

### New findings (all NIT, optional)
| ID | Severity | Location | Problem | Evidence | Fix |
|---|---|---|---|---|---|
| N1 | NIT | §10, the P1 summary paragraph (line 284) | The summary still says "not reviewed when this file was written", while P1 now says "not reviewed in the session that wrote this file". | `grep` of the report against the P1 patch. | Use the P1 wording in the summary. |
| N2 | NIT | §2 row "Time of inventory" (line 33) and §3 intro (line 57) | Both still state "user zone Africa/Casablanca, UTC+00:00" and "the user's zone is UTC+00:00" as fact. The header (line 4) now says that label is unverified. | Report lines 4, 33 and 57. | Add "(label unverified)" in both places, or drop the zone from them. |
| N3 | NIT | §12 gate rows | "Live repository and PR inventory" and "Product and debt boundaries" do not cite F03, the refresh. "Final diff and links" still cites only F02 and says "all hashes, SHAs and line references regenerated". The Overall cell still reads "BLOCKED — partial completion". This is my earlier F8, which was not addressed. §1 item 7 and §9.4 still cite only the 00:06 UTC revalidation, though §2 has the refresh. | Report lines 302, 311, 313 and 316. | Add F03 and G02 to the evidence cells. Put "BLOCKED" alone in the Overall cell and move "partial completion" to the reason column. |
| N4 | NIT | §8, REV3 next-session prompt row | The label "H" (historical source) sits oddly with its own rationale, "an instruction set for a future session". The task defines H as "not treated as current instructions by default". It is symmetric with handoff.md, so there is no neutrality issue. | Report lines 210 and 212, and the task's §8 category table. | Either keep the label and add a clause saying that "H" here means "retained for provenance until the user decides D-A", or use "P (operational wording)" for both rows. |

### Could not verify
- The REV3 ZIP (identity, hash, contents), which is not obtainable.
- The user-side `handoff(1).md`.
- The timezone label "Africa/Casablanca". My check was blocked in the first pass.
- That the revision-1 zip is the archive the user received. The report says so itself.
- The 83/83 result and the "byte-identical to `b4/out`" claim. I did not re-run the checker or re-diff those directories this pass. I relied on C05 and on my first-pass checks.
- §11 and the Independent review row, which are still placeholders.
