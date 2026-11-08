# Consolidated Evidence Report — Execution of P1, P2 and P3 — 2026-11-01

Follows `OCBRAIN_G4_FTS_AUTHENTICATION_RECONCILIATION_REPORT.md` (sha256 `a331f6b2b242b2c031b7a84c66ef178d64b940df228545483ed15a0e8abc8318`), Addendum 1 (`cb4cd825b2046c68403a25874da7d203d171e922559392075d2af0aa903f76b6`), Addendum 2 (`c451cf381ce1b2155212d0f9443d9ca9cb56b8963d6af144023abe9602ba02c0`) and Addendum 3 (`84a09eb1642933f09f7118212a888928674cfb3f539e796c6dd8bf66edb5f564`). None of them is edited. Evidence for this report: `I17`–`I28` in `g4_p1_p2_p3_execution_evidence_I17-I28.zip` (sha256 `b54635048ca9489f86564ccbd4d4cec341baabcc1ea97af64f3b89991ba59715`), delivered beside this report; `I29`, `I30` and `I31`, the author's mechanical checks of this text, are delivered as separate files because they check the text that cites the bundle's hash: `I29` and `I30` are earlier runs that each failed (described in §11), `I31` is the passing rerun; none replaces another. Earlier evidence `I01`–`I16` is in the bundles delivered with Addenda 2 and 3.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This report documents documentation changes only; none of them resolves G4 or any decision item.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what a document or agent says; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **REV3 branch: P2 and P3 are executed and pushed** [OBSERVED, I26, I28]. The PR #90 branch `docs/g4-fts-correctness-handoff-rev3-oct2026` moved from `2dd2e7bb05db949a6156266cfa3430c58de09922` to `9407db5a01acea9684f158caa8107fb71611a102` by a fast-forward push of two commits: the erratum (`9bb2443b…`, one new file) and the digest correction (`9407db5a…`, three files, one character each). The remote tip equals the local tip; PR #90 is still open and draft, now with 3 commits and 7 changed files.
2. **P3 was applied only after P2, on verified conditions** [OBSERVED, I24]: the erratum commit was in place, the ZIP re-measured to Value B, the patch passed `git apply --check` on the live files, and the tree was clean.
3. **REV2 branch: P1 is applied and committed locally but NOT pushed** [OBSERVED, I22, I27, I28]. The remote REV2 tip is still `51564e34c18e5cc908cf517000ebc9bd41eaf194`; the local tip is `f3995bdc9c484bb43119440603c6cbe1aa70fb03`. The push is held because the independent review found that, pushed as written, the commit makes `handoff.md`'s own step 2 of its section 18 report the branch as `INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED` (§6). That is a deviation from "execute P1", recorded here, and it needs your decision.
4. **Nothing else changed:** no pull request was opened, updated by anything other than the branch push, merged or rebased; `main` was not touched; no force-push; no file outside the four REV3 paths and the one local REV2 path was changed.
5. **Statuses unchanged:** G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED; D-1…D-11 OPEN; no implementation authorized.

## 2. Instruction, authorization and scope

Your message of 2026-10-31 15:14 (UTC+00:00): "The next step is to execute P1 separately on REV2 and P2 followed conditionally by P3 on REV3. Afterward, produce a consolidated evidence report so the documentation can be reviewed without prematurely changing the G4 governance status."

How I read it, and where I stopped:

| Point | Reading |
|---|---|
| "execute" | apply, commit, and push as non-force fast-forwards to the two named branches only; the earlier proposals named the targets (`handoff.md` on REV2; a new erratum file and three digest records on REV3) |
| "separately" | P1 on the REV2 branch (the clone), P2 and P3 on the REV3 branch (a separate worktree); no mixing |
| "conditionally" | P3 only with P2 in place and a message recording A, B, locations, measurement and reason (the rule that a wrong digest is not silently replaced) |
| Not authorized, not done | opening or changing a PR other than the branch push into the existing draft #90, merging, rebasing or merging `main` into PR #90, any `main` change, any force-push, committing this report |
| Deviation | P1 not pushed (§6) |

## 3. What was executed

| Change | Reviewed SHA (as the reviewer saw it) | Final SHA | Files | Pushed |
|---|---|---|---|---|
| P1 — provenance note | `2a557ed019039c654d70b7e421bc88bb8b1fa2b5` (parent `51564e34…`) | `f3995bdc9c484bb43119440603c6cbe1aa70fb03` | `handoff.md` +5 lines | **No (held)** |
| P2 — digest-discrepancy erratum | `fc7f8a84f6d6702021e71ad0021f87e3dcbe648c` (parent `2dd2e7bb…`) | `9bb2443b6eb03ae296f24dfc45b4bbab706c9c54` | new `docs/reports/g4-fts-correctness/DIGEST_DISCREPANCY_ERRATUM_REV3.md`, 54 lines | Yes |
| P3 — Value A → Value B | `44569055df1a2d87e504ae2898f1c17cb50d0a6e` | `9407db5a01acea9684f158caa8107fb71611a102` (parent `9bb2443b…`) | `IMPLEMENTATION_ROADMAP.md`, `G4_FTS_CORRECTNESS_CONTINUATION_REV3.md`, `NEXT_SESSION_PROMPT_REV3.md`: 1 line, 1 character each | Yes |

The final SHAs differ from the reviewed ones because the reviewer's findings were applied before pushing, by amending my own unpushed commits and re-picking P3 on top (§5). What differs: P1, the commit message only (tree identical, I27); P2, six lines of the erratum wording (I25); P3, nothing except its parent. The pre-amend commits are kept as local, unpushed backup branches `wip-backup-rev2-local-2a557ed` and `wip-backup-rev3-local-4456905` (I28).

Cumulative change on the REV3 branch relative to the pre-push tip: 4 paths, +57/−3 lines [OBSERVED, I28]. The erratum's sha256 at the remote tip is `10c76dca183b6fb2e555f9f1dbd0a51c9dd1952e377baa410433478ee002a9a0`.

## 4. Evidence per change

**P2 (erratum).** Records Value A (`f9ee…0893c336…`) with its three locations, Value B (`f9ee…0893f336…`) with its location, the measurement (254,581 bytes; `sha256sum` = B; re-measured 2026-10-31 15:15Z, I21), the consistency checks that support but do not prove identity with the intended artifact, what is not established (no contemporaneous record of the packaging run; no claim about any earlier retained copy), the qualified result, and the four-element record required with any correction (original claim, verified observation, affected file/revision, reason). It states what it leaves unchanged. [OBSERVED, I23, I25]

**P3 (correction), conditions** [OBSERVED, I24]:

| Condition | Result |
|---|---|
| C1 the erratum commit is HEAD and its file exists | yes |
| C2 the ZIP, measured again, equals Value B | yes (`f9ee626551e5175a7ba0893f336a77917b8be1b4078903cc6ac5853ad7e509cc`, 254,581 bytes) |
| C3 `git apply --check` on the live files | exit 0 |
| C4 clean tree before | 0 changed paths |

After applying: 3 files, 3 insertions, 3 deletions; each file has exactly one differing line and one differing character; Value A occurs 0 times in the three files and once in the erratum; the verification report (which records B) was not touched; the entry-point sentence in `IMPLEMENTATION_ROADMAP.md` line 2 was not touched. The commit message records original claim, observation, affected file/revision and reason.

**P1 (provenance note), local** [OBSERVED, I21, I22]: `git apply --check` exit 0 on the REV2 tip before applying; the REV3 lines it cites (continuation line 24; `NEXT_SESSION_PROMPT_REV3.md` line 12) and the two strings it quotes from the earlier handoff were re-read first. The commit changes only `handoff.md` (+5 lines), leaves 19 level-2 headings, and has no CR.

**Final state** [OBSERVED, I28]: the clone and the worktree are clean, stash 0; the REV3 remote tip equals local; the REV2 remote tip is unchanged; `main` is `2491ae469edd6ef1267a14604c4f8f40d698f7ea`; the three FTS source blobs on `main` are unchanged (`ed0cbae6…`, `0d5e0716…`, `eb2bbe17…`); no path changed on `main` since `f13bfde` matches an FTS source pattern; no path changed on `main` overlaps the seven files of PR #90. PR #90 is `mergeable_state=behind`, diverged from `main` by 3 ahead and 96 behind [DERIVED: a path-overlap result, not a merge test].

## 5. Independent review and what happened to its findings

**Reviewer:** a fresh-context subagent (`aa2b43dbf5a8381b3`), same model family as the author, so independent-context, not human-independent. It reviewed the three local commits read-only before any push; it was interrupted once by a usage limit and resumed after the reset. Its raw hand-back is model output, is not in the evidence bundle, and I do not reproduce it; the table below is my record of its findings and what I did with each. **Outcome [DERIVED from what I did after the review]:** I pushed P2 and P3 after applying its wording findings, and held P1. I do not claim a count of the claims it checked, and I do not report its severity labels.

| ID | Finding (as I recorded it) | Disposition |
|---|---|---|
| N1 | After P1 the branch holds two commits after the transfer commit, so section 7 of `handoff.md` (handoff commit = the commit that adds the file, found with `git log --oneline -1 -- handoff.md`) and step 2 of its section 18 ("exactly one later commit", otherwise INCOMPLETE) no longer hold literally. My first P1 commit message also said section 7 of `handoff.md` records `51564e34`, which is false (verified: `handoff.md` at the REV2 tip contains no `51564e34`, `grep -c` = 0) | **Message corrected** (amended; tree identical, I27). **P1 push held.** A consistency sentence (P1b) is proposed, not applied, because it exceeds the text you authorized (§6) |
| N2 | In P1, "not reviewed in the session that wrote this file" can mislead now that the two sets have been compared | folded into P1b (not applied) |
| N3 | the erratum used the labels D-A/D-B, which exist only in the audit report outside Git | replaced by descriptions |
| N4 | the erratum's "the next commit" is positional | commit named by title |
| N5 | the erratum equated the verification report's "original extracted archive" with my REV2 bundle | now "taken to be" |
| N6 | the erratum's "Origin" line cites an instruction not recorded in the repository | now says so |
| N7 | "no contemporaneous record was available" had no stated scope | now "available to the audit session" |
| N8 | Addendum 3 was named without its hash | hash added |

I checked N1 against `handoff.md` at the REV2 remote tip myself before acting: its section 7 (lines 357–365) defines the handoff commit as the commit that adds the file; step 2 of its section 18 (line 520) says the branch "should contain exactly one later commit" and otherwise reports INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED; its section 19 (line 539) repeats the INCOMPLETE rule; the file contains no `51564e34` (0 matches). **What the reviewer did not see:** the N3–N8 wording edits and the rebuilt chain. I checked them mechanically (I25: against the reviewed P3 tree only the erratum file differs, six lines; P3's three-file change is unchanged). They were not reviewed again. **Not verified by anyone in this run:** your instruction message beyond its text in the conversation, the chain of custody of the ZIP, whether the audit session's user is the PR #90 author (`1h0lde4`), and any CI behaviour.

## 6. Held item and the decision it needs

**The problem.** Step 2 of section 18 of `handoff.md` tells a fresh session that the REV2 branch "should contain exactly one later commit, the handoff commit", and that if the tip "is not the handoff commit" the transfer is "INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED"; section 19 repeats it. Any commit on top of `51564e34`, including P1 exactly as authorized, makes that check fail literally. The cause is the commit's position, not its content.

**The options** (your decision; P1b is `P1b_handoff_consistency_sentence_PROPOSED.patch`, sha256 `47493c785d3df459365d0991f63dca0f04c1c1d1af2fd562b4907bf3629727fe`, `git apply --check` exit 0 on the local P1 tree, not applied):

| Option | Effect |
|---|---|
| A. Push P1 plus P1b (one added sentence saying the entry postdates the handoff commit, that two commits after the transfer commit are expected, and that this does not make the transfer INCOMPLETE; plus a clearer wording of one clause) | the handoff stays self-consistent; adds text you have not yet seen in a handoff |
| B. Push P1 exactly as authorized | the handoff's own check reports the branch as not verified until someone reads the commit message |
| C. Do not push P1 | REV2 stays at `51564e34`; the earlier handoff's provenance stays unrecorded in the branch |

My recommendation is A. Until you choose, nothing is pushed to the REV2 branch.

## 7. Gate matrix

Exactly one status per gate.

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Authorization and scope | **PASS** | §2; user message of 2026-10-31 15:14 | writes limited to the named branches; read as apply, commit and non-force push |
| Pre-flight verification | **PASS** | I21 | tips, clean tree, ZIP = B, P1 and P3 apply-checks, erratum path free |
| P2 executed on REV3 | **PASS** | I23, I25, I26 | erratum committed and pushed; reviewed before the push, with its wording fixes (N3–N8) checked mechanically only |
| P3 conditionally executed on REV3 | **PASS** | I24, I25, I26 | conditions C1–C4 met; one character per file |
| REV3 remote checkpoint verified | **PASS** | I26, I28 | remote tip = local tip; PR #90 head = tip |
| P1 applied (local commit) | **PASS** | I22, I27 | one file, +5 lines; message corrected |
| P1 pushed and remote verified | **BLOCKED** | I28; §6 | held pending your decision; remote REV2 tip still `51564e34…` |
| Commit contents match their messages and the evidence | **PASS** | §5; I25; I27 | the independent review found one message error (N1), corrected before any push; the erratum and P3 content match their messages (I24, I25) |
| Independent review | **PASS** | §5 | independent-context, same model family; post-review wording edits checked mechanically only |
| Changes limited to authorized scope | **PASS** | I28 | 4 REV3 paths, 1 local REV2 path; no PR action, merge, rebase, force-push or `main` change |
| G4/freeze invariants | **PASS** | §1, §8 | statuses stated unchanged |
| **Overall result** | **BLOCKED** | | partial completion: P2 and P3 done and verified; P1's push is held, so the overall result cannot be PASS |

## 8. What did not change

D-1…D-11 (all OPEN); D-A (entry point) and D-B (REV2 or REV3 ledger wording for D-2/D-5) stay with you; the entry-point sentence in `IMPLEMENTATION_ROADMAP.md` line 2 on PR #90's branch is untouched and its authorization is still not evidenced; the verification report was not touched; no FTS source, test or configuration file; no `main` change; the physical-erasure requirement stays outstanding. Completing P1–P3 improves the evidence record. It does not resolve the FTS5 defect, accept a migration contract, or authorize implementation: the next substantive G4 step remains your decisions D-1…D-11.

## 9. How to review, and how to roll back

- Review the REV3 change: `git fetch origin && git diff 2dd2e7bb05db949a6156266cfa3430c58de09922..9407db5a01acea9684f158caa8107fb71611a102`; `git show 9bb2443b6eb03ae296f24dfc45b4bbab706c9c54 9407db5a01acea9684f158caa8107fb71611a102`.
- Review P1: `commits_format_patch/0001-docs-handoff-record-provenance-of-the-earlier-handof.patch` in the bundle (the commit exists only in the working clone), and `proposals/P1b_handoff_consistency_sentence_PROPOSED.patch`.
- Roll back REV3: `git revert 9407db5a…` then `git revert 9bb2443b…` (newest first); both are documentation-only.
- P1: nothing to roll back remotely; if you decline it, the local commit can be discarded with your approval.

## 10. Limits and unknowns

- Chain of custody of the ZIP (Addenda 2 and 3): unchanged; the P2 erratum records the qualified result, not proof.
- Wording fixes made after the review were checked mechanically, not re-reviewed.
- The reviewer is the same model family; no human review has happened.
- The user-side `handoff(1).md` was never supplied; Library records described in an attached review are unverified (Addendum 3).
- CI or branch-protection behaviour on PR #90 was not examined.
- GitHub's push output also printed a notice of 7 vulnerabilities (3 critical, 4 high) on the default branch; it is unrelated to this work and was not investigated.
- `main` keeps moving; the figures in §4 are as of 2026-11-01 14:14Z (I28).

## 11. Mechanical check of this report

`I29` (first run, kept) failed on two points. (a) The checker read references to sections of `handoff.md`, which the first draft wrote with the section sign, as sections of this report; the wording now says "section N of `handoff.md`", so the two cannot be confused. (b) The checker treated interior fragments such as `0893c336` in `f9ee…0893c336…` as abbreviated prefixes with no source; it now skips a fragment preceded by an ellipsis. `I30` (second run, kept) failed on one point: my first description of (a) in this section reproduced the old section-sign tokens and so tripped the same check; the description was reworded. `I31` is the rerun on the final text.

What `I31` checks: placeholder tokens; headings 1–11; section references resolve to this report; the governing-status line and the final line; gate statuses are only PASS/FAIL/BLOCKED/NOT RUN, the P1-push gate is BLOCKED, and the overall result is consistent with the gates; every cited evidence ID has a file; every 40-hex id is a repository object or appears in the evidence; every 64-hex digest appears in the evidence or is the hash of a delivered file; abbreviated ids are prefixes of ids seen; eighteen figures are found again in the evidence they cite; and three phrases that have no source in this run are absent. What it does not check: that the report's reasoning is right, which is for its reviewer.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
