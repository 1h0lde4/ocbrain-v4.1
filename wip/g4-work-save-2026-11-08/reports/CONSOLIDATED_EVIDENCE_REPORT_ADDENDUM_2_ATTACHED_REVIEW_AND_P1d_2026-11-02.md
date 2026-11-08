# Addendum 2 to the Consolidated Evidence Report — check of an attached review (`7705231e`) and proposal P1d — 2026-11-02

Addendum to `CONSOLIDATED_EVIDENCE_REPORT_P1_P2_P3_EXECUTION_2026-11-01.md` (sha256 `561f22648a36df52cf1cdc546f00cc37ed758f0098a12f93ede0ad77d3fb9050`) and to its Addendum 1 (`CONSOLIDATED_EVIDENCE_REPORT_ADDENDUM_1_P1_PUSHED_2026-11-01.md`, sha256 `eba20d6661df735a75c273eb458519055f38b07f48b97b234287e6eece53d382`). Neither is edited. Evidence: `I38`–`I42` in `g4_attachment_7705231e_check_and_p1d_evidence_I38-I42.zip` (sha256 `713a138c45928a994deb119ca7798d19fa8c6297fb513b0f347aea12057970a6`, delivered beside this addendum). `I43`, the author's mechanical check of this addendum, is delivered as a separate file because it checks the text that cites the bundle's hash.

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This addendum changes no repository, no pull request and no decision item.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what an attached text says; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **The attached review's verifiable claims hold** [OBSERVED, I39]: the REV2 history, the literal failure of the handoff's own step 2 of section 18 and of the section 7 lookup, the PR #90 figures (3 ahead, 96 behind, 7 files, 28 files changed on `main` since the base, 0 overlap), and DEBT-042 recorded as OPEN on `main`.
2. **Its main point is right, and it widens my open finding F1** (Addendum 1). I had listed the section 7 lookup as a minor residual and treated step 2 of section 18 as explained by the P1b sentence. Run literally, step 2 still expects "exactly one later commit" whose parent is the transfer commit; the pushed tip's parent is the handoff commit, and the file's rule below it says a failed step 2 means TRANSFER INCOMPLETE. An explanatory sentence is not a repair of an executable instruction. I record this as **F7, OPEN**.
3. **P1c as built does not address it** [OBSERVED, I39]: its only hunk (`@@ -504,9 +504,9 @@`) changes only lines inside the entry added by P1/P1b; the handoff-commit line of section 7 (line 359) and step 2 of section 18 (line 526) are not touched.
4. **I built a replacement proposal, P1d, and did not apply it** [OBSERVED, I40, I42]. It is a documentation-only patch that identifies the handoff commit by hash and makes step 2 tolerate later commits that change only `handoff.md`. It applies cleanly to the pushed tree and passes a simulation. Nothing was committed or pushed.
5. **Two mistakes of mine in this step are disclosed in §5.** Neither changed a commit, ref, working file or the remote.
6. **Not accepted or checked here:** the attachment's recommended dispositions for D-1…D-11, its entry-point and ledger recommendation, and its rebase advice. They are another assistant's recommendations; they stay with you.

## 2. What was received

A text file, `7705231e-attachment.txt` (12,463 bytes, sha256 `809667f2dcefa5239a01da82a2d87f8f24a3e3dcb5e2e421148f3006c60326cf`), sent without instructions. It is another assistant's review: a finding about P1b, recommended dispositions for D-1…D-11, a recommendation to make the REV3 documents the next-session entry point, advice on PR #90, and a statement that it had not seen Addendum 1 or the P1c patch. Its sentences "My decision: …" are that assistant's, not yours. It is input to verification, not evidence: nothing was accepted because it was stated.

## 3. Claims checked

| Claim in the attachment | Result | Evidence |
|---|---|---|
| REV2 history is the transfer commit `eca2b96…`, then `51564e34…`, then `d963daa5…` | **Verified**: the tip `d963daa502de4220411d0d0c2f19f67b3ec2682b` has parent `51564e34c18e5cc908cf517000ebc9bd41eaf194`, whose parent is `eca2b96521fba8cf792ea16a58be997e4f949356`; the live remote tip is the same | I39 |
| Step 2 of section 18 still expects one later commit whose parent is `eca2b96…`; the tip's parent is `51564e34…` | **Verified**: step 2 (file line 526) reads "it should contain exactly one later commit, the handoff commit, whose parent is `eca2b96…`" and "If the branch tip is not the handoff commit … the transfer is INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED"; line 545 repeats the rule | I39 |
| The section 7 `git log --oneline -1 -- handoff.md` now returns `d963daa5` | **Verified**; `git log --diff-filter=A --oneline -- handoff.md` returns `51564e3` | I39 |
| P1b's sentence does not override the executable instructions | **Agreed [DERIVED]**: the sentence explains the mismatch; it does not change what step 2 tells a resumer to check | I39 |
| PR #90: 3 ahead, 96 behind; 7 changed files; 28 files changed on `main` since the base; no overlap | **Verified**: `diverged`, ahead 3, behind 96, merge base `f13bfdefcdd197ed1f966de0b1f93037a4168af4`; 7 files; 28 files; overlap 0; `main` is `2491ae469edd6ef1267a14604c4f8f40d698f7ea` | I39 (the 28 is new; earlier I measured no overlap, not the count) |
| `KNOWN_ISSUES.md` records DEBT-042 as OPEN and it concerns FTS query-syntax escaping | **Verified** on `main` (lines 15 and 68) | I39 |
| "No immediate rebase recommended" | A recommendation, not a fact. It agrees with the path-overlap result; whether to rebase is the PR owner's call | I39 |
| D-1…D-11 dispositions; REV3 as single entry point; REV3 D-2/D-5 wording; "exact original `handoff(1).md` and REV3 ZIP must be supplied and hash-checked" | **Not checked** against the ledgers or the REV3 prompt in this step; recommendations only | — |

**Original wording that P1d would replace**, kept here so the original claim is preserved (it also stays in the history of commit `51564e34…`): in step 2, "(the branch must contain it; it should contain exactly one later commit, the handoff commit, whose parent is `eca2b96521fba8cf792ea16a58be997e4f949356`). If the branch tip is not the handoff commit or the handoff file is missing on the remote, **the transfer is INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED**"; in section 7, "Handoff commit: the commit that adds this file (`git log --oneline -1 -- handoff.md` on the branch). Its own hash cannot be stored inside the file."

## 4. Proposal P1d (replaces P1c; not applied)

`P1d_handoff_section7_18_and_wording_PROPOSED.patch` (sha256 `1ee754eea65759cffca30af65dfb735079aefd2f133ba8fe09880eb19ee66442`): five lines replaced (5 insertions, 5 deletions), all in `handoff.md` [OBSERVED, I40]. It contains:

1. **Section 7:** the handoff commit is named by hash (`51564e34…`) with the lookup `git log --diff-filter=A --oneline -- handoff.md`, and the file says that the path-filtered `git log -1` now returns the later commit.
2. **Step 2 of section 18:** verify the transfer commit as before; verify that `51564e34…` is on the branch and that its parent is `eca2b96…`; list the commits after it; `git diff --name-only 51564e34… <tip>` must list only `handoff.md`; report each follow-up commit and its scope. The transfer is INCOMPLETE if the handoff commit is missing or its parent differs, if a later commit changes another path, or if `handoff.md` is missing on the remote. It no longer depends on a commit count.
3. **The entry's "Effect on this file's own checks" sentence** is rewritten without a count, so it cannot go stale again.
4. **Reviewer wording from Addendum 1 (F3, F4, F5)**, on the same two lines as in P1c (the parallel-draft bullet and the limited-supersession bullet).

**Verification:** `git apply --check` exit 0 on the pushed tree; the proposed file has 19 level-2 headings, 547 lines, no CR (I40). A dangling commit built from the pushed tip plus P1d, with a temporary index and no ref, passes the proposed step 2 commands: the handoff commit's parent is `eca2b96…`, it is an ancestor of the simulated tip, two commits follow it, only `handoff.md` changed, and the hash-based lookup returns `51564e3` (I42; the simulation commit is `8c15739ad3e3792008b5bb0fd795e17a09889b62`, unreferenced, in this session's clone only).

**Why it needs your explicit approval:** P1/P1b added a provenance entry. P1d changes the executable verification instructions of the transferred handoff. The original wording is preserved in history and above, and the change is documentation-only, but it changes what a resuming session is told to check. **Unlike P1b, I recommend an independent-context review of the exact P1d text before any push.** Apply P1d or P1c, not both: their hunks overlap.

## 5. Mistakes of mine in this step

- **I38 (kept):** my first check script did not set a path variable, so three checks (the P1c hunk check, the file counts on `main` and the overlap) printed nothing useful. I39 reran the whole script with the variable set; the results are in §3. I38 is not altered.
- **I40 (kept):** my build script for P1d contained a stray `git read-tree --empty`, a leftover from a simulation idea I dropped. It emptied the clone's index, so `git status` showed 600 lines. A comment in the same script also claimed a simulation that did not run. I restored the index with `git read-tree HEAD` (I41): status 0 lines, 0 tracked files missing, `handoff.md` blob unchanged, branch and `HEAD` `d963daa502de4220411d0d0c2f19f67b3ec2682b` unchanged, remote tip unchanged. No commit, branch, working file or remote ref was affected. The real simulation is I42. Neither replaces the other.

## 6. Gates and open findings

Exactly one status per gate, for this addendum's scope.

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Attached review treated as unverified input; its verifiable claims checked | **PASS** | I39 | claims in §3 re-measured from the repository; recommendations not adopted |
| No ref, commit, working file or remote changed | **PASS** | I41, I42 | index restored; one unreferenced simulation commit exists in the clone's object store |
| P1d proposal built, applies, simulated | **PASS** | I40, I42 | apply-check exit 0; simulation passes |
| Own errors disclosed and kept | **PASS** | §5 | I38 and I40 not altered |
| G4/freeze invariants | **PASS** | §1 | statuses stated unchanged |
| **Overall result (this addendum's scope)** | **PASS** | | qualified by the open findings below; same-model-family reviewer only; the attachment's other recommendations not checked |

| Finding | Status | Note |
|---|---|---|
| F1–F5 (Addendum 1) | **OPEN** | wording residuals in the pushed entry; P1d includes F3–F5 and rewrites the sentence F1/F2 concern |
| **F7** (new; widens F1) | **OPEN** | step 2 of section 18 and its INCOMPLETE rule fail when followed literally on the pushed branch; fix proposed (P1d), not applied |
| F6 (Addendum 1) | not changed | author date carried by the amend; metadata only |

Addendum 1's overall PASS concerned the execution as you authorized it, and stands for that scope; its qualifications now include F7.

## 7. Decisions for you

1. **P1d:** approve it (my recommendation, with an independent review of its exact text before the push), approve P1c only, or leave the pushed text as it is with F1–F5 and F7 OPEN. If you approve, I apply it as one new commit, push as a non-force fast-forward, verify with an explicit refspec, and record it.
2. **D-1…D-11, the next-session entry point and the ledger wording:** unchanged and yours. The attachment's recommendations are not ratified by this addendum.
3. **PR #90 rebase:** the PR owner's call; none is authorized or done.

Rollback of anything pushed earlier is unchanged (Addendum 1 §7). Nothing was pushed in this step.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
