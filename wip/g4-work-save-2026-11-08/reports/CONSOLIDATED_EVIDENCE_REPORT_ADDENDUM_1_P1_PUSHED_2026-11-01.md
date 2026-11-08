# Addendum 1 to the Consolidated Evidence Report — P1 pushed with P1b — 2026-11-01

Addendum to `CONSOLIDATED_EVIDENCE_REPORT_P1_P2_P3_EXECUTION_2026-11-01.md` (sha256 `561f22648a36df52cf1cdc546f00cc37ed758f0098a12f93ede0ad77d3fb9050`), which is not edited. This addendum supersedes that report only where it says P1 is local and held (its §1 items 3 and 5 as to P1, §3 P1 row, §6, and the gate rows "P1 pushed and remote verified" and "Overall result" in its §7); everything else in it stands. Evidence: `I32`–`I36` in `g4_p1_p1b_push_and_report_checks_evidence_I29-I36.zip` (sha256 `34953430085df836553e77f487dcb07343200b60dbc53e306a36994347779a65`, delivered beside this addendum; it also holds `I29`–`I31`, the three runs of the report's own check). `I37`, the author's mechanical check of this addendum, is delivered as a separate file because it checks the text that cites the bundle's hash.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This addendum documents a documentation-only push; it resolves neither G4 nor any decision item.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what an agent or document says; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **P1, with P1b folded in, is pushed and verified** [OBSERVED, I34, I35]. The REV2 branch `docs/g4-fts-errata-handoff-oct2026` moved from `51564e34c18e5cc908cf517000ebc9bd41eaf194` to `d963daa502de4220411d0d0c2f19f67b3ec2682b` by a fast-forward push without force. The remote tip equals the local tip; the parent is `51564e34…`; only `handoff.md` changed (+6 lines, no deletions); the remote `handoff.md` blob equals the local one (`f3434b71516445856e106b5e12d48801b643d057`).
2. **With the push, all authorized changes are done:** P2 and P3 on the REV3 branch (earlier report), P1 plus P1b on the REV2 branch (this addendum).
3. **An independent-context review of the pushed commit found no false statement and no status change** [REPORTED, §4]. It raised one minor point and four nits about the new wording. I did not change the pushed text. The fixes are proposed as a separate patch (P1c), not applied, because they go beyond what you authorized.
4. **Nothing else changed** [OBSERVED, I35]: the REV3 branch is still at `9407db5a01acea9684f158caa8107fb71611a102`; PR #90 is still open and draft with 3 commits and 7 files; `main` is still `2491ae469edd6ef1267a14604c4f8f40d698f7ea`; no pull request exists for the REV2 branch; no local backup branch was pushed.
5. **Statuses unchanged:** G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED; D-1…D-11 OPEN; no implementation authorized.

## 2. Your decision and what was executed

Decision [OBSERVED in this session, 2026-11-01 about 23:46 local, UTC+00:00]: you answered the question about the held P1 commit with "Push P1 plus P1b (Recommended)". I read it as: apply the proposed consistency sentence, and push both as a non-force fast-forward to the REV2 branch, and nothing more.

| Step | Result | Evidence |
|---|---|---|
| Pre-flight | clean tree, stash 0; live remote tip still `51564e34…`; local P1 commit `f3995bdc…` one ahead with that parent; `git apply --check` of P1b exit 0; REV3 tip and `main` unchanged; backup branch `wip-backup-rev2-local-f3995bd` made (local only) | I32 |
| Apply P1b and fold into P1 | the unpushed P1 commit was amended (not a third commit) so that the branch holds exactly two commits after the transfer commit `eca2b96521fba8cf792ea16a58be997e4f949356`, as the P1b sentence says; `git diff --check` clean; 19 level-2 headings; 547 lines; no CR; numstat `6 0 handoff.md`; message `p1_commit_v3.txt` | I33 |
| Push | `51564e3..d963daa` fast-forward; exit 0 | I34 |
| Verification | tip = local; blob equal; two commits after `eca2b96`; only `handoff.md` in the diff; the new entry present once; REV3 tip and `main` unchanged; 0 remote `wip-backup*` branches; PR #90 unchanged | I35 |

Final SHAs: `f3995bdc…` (P1 as held) is replaced by `d963daa502de4220411d0d0c2f19f67b3ec2682b`; it is not on any pushed ref. The commit's author date is `2026-10-31T15:16:16+00:00`, carried from the first P1 commit by the amend; its committer date is `2026-11-01T23:47:48+00:00` [OBSERVED]. This is metadata only.

**A flaw in my own verification, kept:** `I34` also contains a verification block that is wrong. It ran `git fetch origin <branch>` without a refspec, which does not update `origin/<branch>`, so its blob and history comparisons used the stale ref and printed `51564e34…` and a blob mismatch. The push result and the live `ls-remote` lines in `I34` were not affected. I redid the verification properly in `I35` (explicit refspec). `I34` is not altered; neither replaces the other.

## 3. What the pushed commit contains

The six added lines are one parent bullet and five sub-bullets in the "Relevant Information / References" section of `handoff.md` (text in the format-patch in the bundle): the earlier handoff revision and its sha256 (`da162e71d6bd0b92650134eceb6af1ecfa430484ac08b179d7aaa48a97fa716d`), a limited supersession of that revision's transfer-status statements only, the parallel REV3 set (branch and draft PR #90), the "Effect on this file's own checks" sentence (P1b), and "Not decided by this entry". The commit message states that the P1b text was not independently reviewed before the push (§4 now covers it).

## 4. Review of the pushed commit

**Reviewer:** the same fresh-context subagent as before (`aa2b43dbf5a8381b3`), same model family as the author, so independent-context and not human-independent. It was asked after the push, read-only, and made no change. Its hand-back is model output with no authority; the table is my record of it, with its severity labels as it gave them in this run.

Verdict [REPORTED]: the commit does what its message says; no false statement, no secret, no status or authority change. It verified, among other things: the diff touches only `handoff.md` (6/0); the quoted strings and line numbers of the earlier handoff and of the REV3 files; two commits after `eca2b96`; `git log --diff-filter=A -- handoff.md` returns `51564e34…`.

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| F1 | MINOR | Run literally, the `git log --oneline -1 -- handoff.md` of the file's section 7 now prints `d963daa…`, not `51564e34…`; the new sentence says it "refers to" `51564e34…`, which leaves that literal mismatch unexplained | **OPEN** — fix in P1c (not applied) |
| F2 | NIT | "The branch therefore holds two commits" goes stale if the branch grows; the exemption is self-certifying | **OPEN** — fix in P1c |
| F3 | NIT | "not reviewed in the session that first wrote this file" is trivially true (the first version predates the REV3 set by about ten hours) and may point at the wrong event | **OPEN** — fix in P1c |
| F4 | NIT | the pinned commit `2dd2e7bb…` is no longer the REV3 tip (`9407db5a…`) | **OPEN** — fix in P1c |
| F5 | NIT | "remain a valid historical record" can read as endorsement of the earlier ledgers | **OPEN** — fix in P1c |
| F6 | NIT | the author date is carried from the first P1 commit | not changed; metadata only |

**P1c** is `P1c_handoff_review_wording_PROPOSED.patch` (sha256 `3dabe97140b9b39f576592cea99bc8397406884055227de7cf97498eab279d5d`): three changed lines, all inside the entry P1/P1b added; `git apply --check` exit 0 on the pushed tree; not applied [OBSERVED, I36]. Whether to apply it is your decision.

**Not checked by the reviewer, and not by me:** your decision message beyond its text; which session wrote which version of the earlier handoff; whether the earlier handoff in this session's scratch directory is the user-side `handoff(1).md`; the pushed REV3 commits beyond their cited lines; any CI result; whether "nothing else in the earlier revision is replaced" holds for every statement of the earlier revision (it checked five quoted statements). The P1b text was reviewed only after the push; it was not reviewed before.

## 5. Updated gate matrix

Exactly one status per gate. Rows 1–3 and 5–7 restate or replace the report's rows; the last row replaces its "Overall result".

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Authorization for the P1 plus P1b push | **PASS** | §2 | your answer "Push P1 plus P1b" in this session; scope limited to the REV2 branch |
| Pre-flight before applying P1b and pushing | **PASS** | I32 | tips, tree, apply-check |
| P1b applied and folded into P1 (local) | **PASS** | I33 | one file, +6 lines, headings and CR checked |
| P1 pushed and remote verified | **PASS** | I34, I35 | remote tip = `d963daa…`; verified with an explicit refspec after the first verification block proved flawed |
| Independent review of the pushed commit | **PASS** | §4 | independent-context, same model family, run after the push; one minor point and four nits open (F1–F5) |
| Changes limited to authorized scope | **PASS** | I35 | `handoff.md` only; REV3 tip, `main` and PR #90 unchanged; no PR for REV2; no force; no backup branch pushed |
| G4/freeze invariants | **PASS** | §1, §6 | statuses stated unchanged |
| **Overall result (P1, P2, P3 execution)** | **PASS** | | every gate passes; qualified by: F1–F5 open (P1c proposed, not applied); the P1b text reviewed only after the push; review by the same model family only; the post-review wording edits of the REV3 erratum checked mechanically only (report §5) |

## 6. What did not change, and what is still open

D-1…D-11 (all OPEN), the choice of next-session entry point, and the REV2/REV3 ledger-wording choice for D-2 and D-5 stay with you. The entry-point sentence in `IMPLEMENTATION_ROADMAP.md` line 2 on PR #90's branch is untouched and its authorization is still not evidenced. PR #90 is `behind` `main` by 96 commits (3 ahead) as of the last measurement, with no path overlap; rebasing it is not authorized and not done. Open items for you: (1) apply P1c or not; (2) the decisions above; (3) the PR #90 owner's call on rebasing. Completing P1–P3 improves the record. It does not resolve the FTS5 defect, accept a migration contract, or authorize implementation.

## 7. How to review and how to roll back

- Review: `git fetch origin && git show d963daa502de4220411d0d0c2f19f67b3ec2682b`; the same commit is in the bundle as a format-patch.
- Roll back the REV2 change with a new commit, not a force-push: `git revert d963daa502de4220411d0d0c2f19f67b3ec2682b` (documentation-only).
- The earlier REV3 rollback (`git revert 9407db5a…` then `git revert 9bb2443b…`) is unchanged.
- Local backup branches `wip-backup-rev2-local-2a557ed`, `wip-backup-rev2-local-f3995bd` and `wip-backup-rev3-local-4456905` exist only in this session's clone.

## 8. Limits

- The reviewer is the same model family; no human review has happened.
- I did not re-review the P1b text before the push; the review in §4 is after the fact.
- The chain of custody of the REV3 ZIP and the user-side `handoff(1).md` are unchanged unknowns (Addenda 2 and 3).
- CI and branch-protection behaviour were not examined. GitHub again printed a notice of 7 vulnerabilities (3 critical, 4 high) on the default branch during the push; it is unrelated and was not investigated.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
