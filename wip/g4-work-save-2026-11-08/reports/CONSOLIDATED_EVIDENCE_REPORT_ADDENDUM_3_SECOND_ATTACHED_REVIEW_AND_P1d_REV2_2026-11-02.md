# Addendum 3 to the Consolidated Evidence Report — second attached review (`3bce0bf2`) and P1d revision 2 — 2026-11-02

Addendum to `CONSOLIDATED_EVIDENCE_REPORT_P1_P2_P3_EXECUTION_2026-11-01.md` (sha256 `561f22648a36df52cf1cdc546f00cc37ed758f0098a12f93ede0ad77d3fb9050`), Addendum 1 (`eba20d6661df735a75c273eb458519055f38b07f48b97b234287e6eece53d382`) and Addendum 2 (`4003be115020ec7c2e8269c954f82babf90696ed52fbe5875cf6dd141579d938`). None is edited. Evidence: `I44`–`I48` in `g4_attachment_3bce0bf2_p1d_rev2_block_tests_evidence_I44-I48.zip` (sha256 `3ebd79aef18f91f78b60ea910929e10a4a88ed79d9fe9a7f25152b3dcbf141da`, delivered beside this addendum). `I49` and `I50`, the author's mechanical checks of this addendum, are delivered as separate files because they check the text that cites the bundle's hash: `I49` is the first run and failed on one point (a reference to section 16.5 of the project instructions, written with the section sign, was read as a section of this addendum; the wording was changed), `I50` is the passing rerun; neither replaces the other.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This addendum changes no repository, no pull request and no decision item.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what an attached text says; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **The attached review is right about P1d, and my own tests show how.** P1d as I delivered it in Addendum 2 has no ancestry check, no per-commit scope check, no comparison of the fetched tip with the live remote, and no test that `handoff.md` is in the remote tree [OBSERVED, I44]. In the eight scenarios that must fail, P1d's checks would give a **false PASS in five** (a file changed and then reverted; the handoff commit present locally but not an ancestor of the remote tip; the remote moving after the fetch; a merge commit; `handoff.md` missing from the tree) [OBSERVED, I45]. They would also give a **false FAIL on the baseline** (no follow-up commits), a defect the review did not name. I record this as **F8** (§6).
2. **I built P1d revision 2 and did not apply it** [OBSERVED, I46]. It replaces P1d (and P1c). The §7 line names the handoff commit by full hash with `git log --diff-filter=A --format='%H %P %s'`; step 2 of section 18 becomes a 25-line verification block, embedded in the proposed text, that checks the remote branch directly.
3. **The block was tested before being proposed** [OBSERVED, I45, I47]: 11 scenarios in throw-away synthetic repositories, every one as expected (3 PASS, 8 FAIL), and the unmodified block prints PASS on the real remote branch, both in my working clone and in a fresh no-checkout clone. The block inside the proposed patch is byte-identical to the tested one (same sha256).
4. **Nothing was pushed, applied or committed** [OBSERVED, I47]: `HEAD` and the remote REV2 tip are still `d963daa502de4220411d0d0c2f19f67b3ec2682b`; the clone is clean. F7 stays OPEN.
5. **Statuses unchanged:** G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED; D-1…D-11 OPEN; no implementation authorized.

## 2. What was received

A text file, `3bce0bf2-attachment.txt` (8,556 bytes, sha256 `9c5753c49127c98e77e4a4fb700b0a4e2367b438a522df3fc55c7d41412bd586`), sent without instructions. It is another assistant's review of P1d: four verification weaknesses, a list of failure scenarios to test, a view on the §7 wording and the F3–F5 changes, a remark on the index incident, and a recommended disposition ("revise before review; no push authorization yet"). Its recommendations are that assistant's, not yours. It is input to verification, not evidence.

## 3. Claims checked

| Claim | Result | Evidence |
|---|---|---|
| P1d proves ancestry only with `git rev-parse H^` and `git cat-file -t T`, which are local-object checks | **Verified**: P1d has no `is-ancestor` check; the only `merge-base` in its text is the existing step 3 | I44 |
| P1d's scope test is one cumulative `git diff --name-only H tip`, so a file changed and reverted escapes it | **Verified, and demonstrated**: scenario s05 gives PASS under P1d's checks and FAIL under the block | I44, I45 |
| P1d does not compare the fetched ref with the live remote and does not test the remote tree for `handoff.md` | **Verified**: no `cat-file -e`, no live-versus-fetched comparison; scenarios s07 and s09 give a false PASS | I44, I45 |
| The §7 lookup should print the full SHA and parent | **Agreed and applied in rev2** (`--format='%H %P %s'`) | I44, I46 |
| REV3 reached `9407db5a…` through P3, committed on 1 November | **Verified**: committer date `2026-11-01T14:12:28+00:00` | I44 |
| Its table of F3–F5 | **Partly wrong**: it attaches my label F3 to the "historical record, not endorsed" change (that is F5), calls the commit-count rewrite F5 (that is F1/F2), and has F4 right. The substance of the changes it endorses is unchanged | I44 |
| `git read-tree HEAD` restores the original index only if it was clean beforehand | **Correct, and the limit is stated in §5** | I41, I44 |
| Its closure criterion for F7: independent review, push, then successful execution from a fresh remote checkout | **Adopted as the criterion** (consistent with "fixed" versus "verified" in section 16.5 of the project instructions) | §6 |
| Its recommendations for D-1…D-11 | The attachment itself says they were proposals; not adopted or checked here | — |

## 4. P1d revision 2 (replaces P1d and P1c; not applied)

`P1d_rev2_handoff_section7_18_verification_block_PROPOSED.patch` (sha256 `b058780be6e388409c1cad12df6facf4606ebcd371fdd05e0c2c336a0c535003`): 33 insertions and 5 deletions, all in `handoff.md`; `git apply --check` exit 0 on the pushed tree; the proposed file has 19 level-2 headings and no CR [OBSERVED, I46]. Contents:

1. **Section 7:** the handoff commit is named by full hash with its parent, found with `git log --diff-filter=A --format='%H %P %s' -- handoff.md`; the file says that the path-filtered `git log -1` now returns the later commit.
2. **Step 2 of section 18:** a block (sha256 `014fad4792ab082448fc48f3328c49ceb67bf551261ac828cb4a81527336519f`) that fetches the branch with an explicit refspec; compares the fetched tip with the live `ls-remote` result; tests `git cat-file -e <tip>:handoff.md`; requires `git merge-base --is-ancestor` for both the transfer commit and the handoff commit; requires the handoff commit's parents to be exactly the transfer commit; requires `handoff.md` to be added by the handoff commit; and walks every later commit in order, requiring a single-parent child of the previous one whose `git diff-tree` path list is `handoff.md` alone. It prints `PASS` or `TRANSFER INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED`.
3. **The entry's "Effect on this file's own checks" sentence** is rewritten without a commit count.
4. **F3, F4 and F5 wording**, as in P1d.

**Tests** [OBSERVED, I45; synthetic repositories; git 2.43.0, GNU bash 5.2.21, I48]:

| Scenario | Expected | Block | P1d as delivered |
|---|---|---|---|
| s01 original transfer and handoff, no follow-up | PASS | PASS | FAIL (false FAIL) |
| s02 one later handoff-only commit | PASS | PASS | PASS |
| s03 three later handoff-only commits | PASS | PASS | PASS |
| s04 a later commit changes another file | FAIL | FAIL | FAIL |
| s05 another file changed and then reverted | FAIL | FAIL | PASS (false PASS) |
| s06 handoff commit exists locally, not an ancestor of the remote tip | FAIL | FAIL | PASS (false PASS) |
| s07 remote moves between fetch and live check | FAIL | FAIL | PASS (false PASS) |
| s08 merge commit in the sequence | FAIL | FAIL | PASS (false PASS) |
| s09 `handoff.md` missing from the remote tree | FAIL | FAIL | PASS (false PASS) |
| s10 wrong parent for the handoff commit | FAIL | FAIL | FAIL |
| s11 remote branch missing | FAIL | FAIL | FAIL |

**Real execution** [OBSERVED, I47]: the unmodified block prints `PASS: handoff commit 51564e34… on docs/g4-fts-errata-handoff-oct2026; 1 follow-up(s), each a single-parent child changing handoff.md alone` in the working clone and in a fresh no-checkout clone of the remote, listing the one follow-up `d963daa5…`. This tests the checkpoint and the block's logic against the live branch before any P1d text is pushed; it does not show that the P1d text is on the branch.

**Limits of the block:** it checks paths and graph shape, not what a later commit writes inside `handoff.md`; a legitimate later change that also touches another file will fail it by design and needs a new handoff revision; it needs network access and an `origin` remote; the hashes are written into it; the scenarios are synthetic and a fresh independent review has not yet read it.

## 5. The index incident, stated precisely

`git read-tree HEAD` rebuilds the index from `HEAD`; it recovers the earlier index only if the earlier index equalled `HEAD`. What is recorded: the last status before the incident was 0 lines (`I36`, 2026-11-01 23:51Z); the steps between then and the stray command were read-only for the index (`I37` a Python check, `I38`/`I39` fetches of remote-tracking refs and API reads, `I40` apply-check and numstat); the incident output shows 556 staged-deletion lines and 44 untracked lines, which matches an emptied index against 556 tracked files in `HEAD` (`I41`, `I44`). After the repair: 0 status lines, `git diff HEAD --stat` empty, `git diff --cached --stat` empty, 556 tracked files [OBSERVED, I44]. So the working files equal `HEAD`, and no unstaged difference existed. What cannot be proved: that no staged-only change existed that was not also in the working tree before the incident; I know of none, and no commit, branch, remote ref or working file was affected.

## 6. Gates and open findings

Exactly one status per gate, for this addendum's scope.

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Attached review treated as unverified input; its verifiable claims checked | **PASS** | I44, I45 | §3 |
| P1d revision 2 built, applies, and its block identical to the tested block | **PASS** | I46 | apply-check exit 0; same sha256 |
| Block tested on positive and negative scenarios | **PASS** | I45 | 11 of 11 as expected |
| Unmodified block run on the real remote branch | **PASS** | I47 | working clone and fresh clone |
| No ref, commit, working file, pull request or remote changed | **PASS** | I47 | `HEAD` and remote tip `d963daa5…`, status 0 |
| G4/freeze invariants | **PASS** | §1 | statuses stated unchanged |
| **Overall result (this addendum's scope)** | **PASS** | | qualified by the open findings below; synthetic tests; same-model-family review only; the exact rev2 text is not yet independently reviewed |

| Finding | Status | Note |
|---|---|---|
| F1–F5 (Addendum 1) | **OPEN** | pushed wording residuals; rev2 carries the fixes |
| F7 (Addendum 2) | **OPEN** | the pushed step 2 and section 7 fail when followed literally; fix proposed (rev2), not applied. Closure criterion: independent-context review of the exact text, authorized push, then the block run successfully from a fresh remote checkout after the push |
| **F8** (new) | **OPEN** | P1d as I delivered it in Addendum 2 could give five false PASSes and a false FAIL on the baseline; it **must not be applied**; superseded by rev2 as a proposal |
| F6 (Addendum 1) | not changed | metadata only |

## 7. Decisions for you

1. **P1d revision 2:** approve it, or not. If you approve, I send the exact text to the independent-context reviewer first, fix what it finds, then apply it as one new commit, push as a non-force fast-forward, run the block from a fresh clone of the pushed branch, and record it. Apply P1d revision 2 or nothing: P1c and the P1d of Addendum 2 should not be applied.
2. **D-1…D-11, the next-session entry point and the ledger wording** stay with you; no recommendation in either attachment is adopted by this addendum.
3. **PR #90 rebase:** the PR owner's call; none is authorized or done.

Nothing was pushed in this step; rollback of earlier pushes is unchanged (Addendum 1 §7).

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
