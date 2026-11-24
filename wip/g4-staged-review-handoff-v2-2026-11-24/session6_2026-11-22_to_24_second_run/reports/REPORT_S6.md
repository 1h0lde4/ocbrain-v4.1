STAGE S6 (run 3): COMPLETE

F, G(4) and H statuses below are mine. The compact REPORT_S6.md left by the previous run was an input, not authority. I read the earlier runs of this same stage: harness/, rows/, evidence/, summary.tsv, summary_prior1.tsv, evidence_prior1/, REPORT_S6.md and REPORT_S6_prior_1.md. I did not open pkg/optional_item_I/; I only saw its file names in the directory listing and in SHA256SUMS.txt.

Stage dir: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a9/stage_S6/
New run-3 material is under stage_S6/run3/ (harness/, evidence/, rows/, summary.tsv, logs). The earlier files are untouched.

## 1. Package integrity
- The full SHA-256 of package/g4_rev3_independent_review_package.zip is 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286. This equals the authoritative value in the preamble.
- stage_S6/pkgcopy.zip has the same hash.
- In pkg/review_package, `sha256sum -c` of the 5 non-optional files in SHA256SUMS.txt gave 5 OK: README_FIRST_REVIEW_BRIEF.md, base/handoff.md, rev2/verify_block.sh, rev3 patch, rev3/verify_block_rev3.sh.
- The 2 optional_item_I entries were deliberately not checked or opened.
- Nothing from the package was executed directly. The harness copies the block and substitutes only lines 4, 6 and 7 (CANON, T, H).

## 2. What I re-ran
- I re-ran 48 rows through a copy of the earlier harness, with W repointed to run3/.
- That covers every H row from H221 to H39, F01–F09, and G01–G12 plus the IDN string check.
- I added 6 rows (H40–H42, G13–G15), described below.
- **Earlier-run only, not re-run by me:** H01–H21 (21 rows). Their classifications are taken from summary.tsv.
- All 45 overlapping rows reproduced the earlier classification exactly (a join of column 5 of summary.tsv against run3/summary.tsv showed zero differences). The IDN identity_normalisation output also matched.
- **Counts for the 66 rows in summary.tsv:** 25 correct PASS, 29 correct FAIL, 6 FALSE PASS, 6 false FAIL, 0 anomalies. The run-3 re-runs give 15, 21, 6 and 6 over the 48 re-run rows, which includes the 3 new ones.
- **FALSE PASS rows:** H23, H24, H25, H27f, H29, H34. All six reproduced.
- **Controls:** H23c, H25c and H34c reproduced as correct FAIL. The same remote state is correctly rejected when the graft, replace ref or subdirectory run is removed.
- **False FAIL rows (minor):** H221 (depth-1 shallow verifier), H223 (depth-3 shallow), H26b (`log.follow=true` with a rename-add), H27b (CRLF in ls-remote output, which real git never emits), H27e (trailing space in `%P`, which real git never emits), H33 (valid chain, run from `docs/`). All six reproduced. H224 (depth 4) is a correct PASS.

### Judgement of each FALSE PASS against the contract
**H23 (graft) and H24 (replace ref).**
- **Setup:** the remote chain is T→X→H→c1, and the clone has a graft or `git replace --graft` that makes H's parent T.
- **Contract clause 2:** "its parent is exactly T". The remote parent is X, so the correct outcome is FAIL.
- **What the block checked:** line 25 (`git show -s --format=%P "$H"`), line 26 (`git log --diff-filter=A`) and line 28 (`rev-list`) read the local object graph. That graph honours grafts and replace refs.
- **Control:** H23c returns the correct FAIL.
- **Limitation:** needs a graft file or `refs/replace/*` in the verifier's own clone. The block's refspec does not fetch replace refs, so a stale replace ref left in the clone from earlier work is the plausible route.

**H25 (replace of the tip tree).**
- **Setup:** the remote tip turns handoff.md into a symlink, and the clone replaces that tree with one holding a regular file.
- **Contract clause 3:** "handoff.md in the tip's tree is a regular, non-symlink… (mode 100644)". The remote tree holds a symlink, so the correct outcome is FAIL.
- **What the block checked:** line 21 (`git ls-tree "$TIP"`) read the replaced tree.
- **Control:** H25c returns the correct FAIL.

**H29 (simulated git failure).**
- **Setup:** c1 changes handoff.md and zz.txt. The wrapper makes `git diff-tree` print only the first line (`handoff.md`) and then exit 128.
- **Contract clause 2:** "each… changes `handoff.md` and no other path". c1 changes zz.txt, so the correct outcome is FAIL.
- **What the block checked:** line 30 compares only the stdout of the `$(…)` substitution. The exit status inside the substitution is ignored.
- **Result:** the PASS line then states "each a single-parent child changing handoff.md alone", which is false.
- **Limitation:** the failure is simulated. H30 tried real corruption (a deleted tree object) but failed on a different check, so it does not show the same behaviour with real git.
- **Related row:** H28e shows the same exit-status blindness on a valid remote, where a PASS is contract-correct.

**H34 (cwd dependence).**
- **Setup:** root handoff.md is a symlink at the tip, docs/handoff.md is a regular file added in H, and the block is run from `docs/`.
- **Contract clause 3:** root handoff.md must be regular, so the correct outcome is FAIL.
- **What the block checked:** `git ls-tree "$TIP" -- handoff.md` and the `git log … -- handoff.md` pathspec are cwd-relative, so line 21 looked at docs/handoff.md.
- **Control:** H34c, run from the clone root, gives the correct FAIL.
- **Related false FAIL:** H33 is a valid chain run from `docs/`, which fails.

**H27f (reclassified).**
- **Setup:** the wrapper appends a third word to the ls-remote line. The remote chain and tip are valid.
- **Reading against the contract:** every contract clause holds for the real remote, so PASS is contract-correct. The earlier harness expected FAIL because of the comment "exactly one ref with the exact name".
- **What the block checked:** `live()` (line 12) does not check `$#`.
- **Result:** it is NOT a contract false PASS and I do not count it as substantive. It is a hardening gap and a mild overstatement of the line-9 comment (claim C13 in the claim table).

## 3. Criteria table (one status each; the justification follows each row)

| Criterion | Status |
|---|---|
| F: the unavoidable race | PASS |
| G(4): step-2 prose and block comments against the block | FAIL |
| H: shell and git pitfalls in the block | FAIL |

**F: PASS.**
- All of F01–F09, H36–H38 and H40–H41 behaved as the prose says.
- A move after the final ls-remote still yields PASS (F02 valid commit, F03 invalid commit). This matches "PASS means only … at that final observation … the remote cannot be locked afterwards".
- A move between the observations, before #2 or after the fetch, gives FAIL (F04, F06, F08, F09).
- ABA, where the remote moves away and returns before #2, gives PASS (F07). That is consistent with the final-observation wording.
- A move before the fetch gives PASS on the new tip (F05).
- Non-substantive caveats: "still the verified tip" (step 2) suggests continuity, but F07 shows non-continuity is undetected. That is harmless because a tip hash identifies history. "PASS at <UTC>" is the print time, after LIVE2 and a rev-list. "PASS means only…" says nothing about the local-object dependency in H23–H25, which is not a race issue.

**G(4): FAIL.**
- Substantive items, from the claim table: C1, C2, C4/C5/C12, C8, C9, C10, C11 and C14.
- The block's own FAIL messages never print the URL or credentials, and userinfo credentials stay out of the output (G01, G02, G05).
- git's own stderr does print the query-string token (G04, 3 occurrences), and the identity check accepts URLs whose real connect host differs from the canonical host (G13, G14).
- The following prose claims are contradicted by H23–H25, H29, H33/H34, H14/H10/H11 and H26b:
  - "against the remote, not local objects"
  - "handoff.md is a regular file"
  - "commit by commit … changes handoff.md alone"
  - "documentation-only change"
  - "no longer depend on the path-filtered git log"

**H: FAIL.**
- Reproduced contract false PASSes: H23, H24, H25 (grafts and replace refs), H29 (exit status inside `$( )` ignored, with simulated truncated output) and H34 (cwd-relative pathspecs).
- These cover three pitfall classes: replace and graft refs, command-substitution failures, and cwd dependence.
- Checked and held (correct outcomes):
  - `set --` side effects, word splitting and globbing with IDIFS/glob files in the cwd (H31).
  - rev-list ordering with equal and backwards timestamps (H03, H04).
  - diff-tree renames and copies (H05–H08, H16, H17).
  - Empty commits (H12) and merges (H18–H20).
  - Mode-only changes, which stay unflagged when the tip mode is 100644 (H09, H10).
  - Unset or empty command substitutions (H28a–H28d, H28f, H28g, H36–H38, H40–H42).
  - `log.follow` and `diff.renames` config (H26a PASS), with H26b a minor false FAIL.
  - Depth-4 shallow clone (H224).

## 4. G(4) claim table

"Reasoning only" means the claim was checked by reading the block, not by any run. "NOT RUN" means I did not test it.

| # | Quote | Location | How tested | Classification | Substantive |
|---|---|---|---|---|---|
| C1 | "Verify the checkpoint against the remote branch, not against local objects" | patch L30 | H23, H24, H25 (OBSERVED false PASS), H23c, H25c as controls | overstated: the chain and tree checks read the local object store, which honours grafts and replace refs | yes |
| C2 | "Run the block below as a script (`bash verify.sh`) from a clone…"; block L1 "from a clone of the repository" | patch L30; block L1 | H33 (false FAIL), H34 (false PASS), H34c | understated: it must be run from the clone root, which the prose never says | yes (H34) |
| C3 | "the SSH forms and a trailing `.git` are accepted" | patch L30 | G08–G10, G12 and IDN (accepted at the identity check; the SSH transport itself was never run) | supported by execution (identity-string level) | no |
| C4 | "credentials in the URL are ignored and never printed"; block L15 comment "credentials in the host part are dropped, so they are neither compared nor printed" | patch L30, L47; block L15 | G01, G02, G05 and G06: no token in output (OBSERVED). G04 (`?token=DUMMYTOKEN-xyz`): git prints it 3 times on stderr (OBSERVED) | supported for userinfo; inaccurate for any credential not in userinfo, and git's own diagnostics are not under the block's control | yes (G04) |
| C5 | "a fork, mirror or proxy URL fails the identity check by design"; "the configured URL is not printed because it may carry credentials" (block L16 message) | patch L30; block L15–16 | G11 and G15 are rejected. G13 (`https://u@127.0.0.1:1#@127.0.0.1:2/o/r`) and G14 (`…:1?x@…:2/o/r`) are ACCEPTED at the identity check while git's connect error shows it connects to port 1. G07 stderr: git prints the host and path | the identity check is string normalisation, not host comparison, so the claim is inaccurate for `#` or `?` before an `@`; the "not printed" claim holds only for the block's own lines | yes (G13/G14) |
| C6 | "The block checks, in this order: …" | patch L30 | read against block L15–36; FAIL-line order in G04 stdout | supported (reasoning plus G04 output order). The prose omits the `--diff-filter=A` "H adds handoff.md" check, which is harmless | no |
| C7 | "each `git ls-remote` must succeed and return exactly one ref with the exact branch name"; block L9 comment | patch L30; block L9–13 | H36, H37, H38, H40, H41, H42 (correct FAIL); H27b (false FAIL); H27f (extra token accepted) | partly supported; "exactly" is overstated, because L12 does not check `$#` | no (minor) |
| C8 | "handoff.md is a regular file (mode 100644) in the remote tree" | patch L30; block L21–22 | H09, H25 (false PASS), H34 (false PASS), H25c, H34c | inaccurate under a replace ref or a non-root cwd | yes |
| C9 | "the transfer commit and the handoff commit are ancestors… the handoff commit's parent is exactly the transfer commit" | patch L30; block L23–25 | H23, H24 (OBSERVED false PASS), H23c | overstated | yes |
| C10 | "commit by commit, that every later commit is a single-parent child of the previous one that changes `handoff.md` alone" | patch L30; block L28–33 | H05–H08, H12, H13, H18–H20 (correct FAIL); H29 (false PASS, simulated); H23/H24 | supported for real git in tested cases; inaccurate when diff-tree fails after partial output | yes (H29) |
| C11 | "Each follow-up commit it lists is a documentation-only change to `handoff.md`; report them." | patch L30 | H14 (content wiped to empty: PASS), H10 (mode flip and back: PASS), H11 (symlink flip and back: PASS) | overstated: the block checks the path only, not the nature of the change | yes (claim the block does not satisfy) |
| C12 | "It must print a `PASS` line with a UTC time" | patch L30 | H28h (stub date exits 1: prints "PASS at : …") | unsatisfied only if `date` fails. Under the strictest reading the claim is not met | minor, my judgement |
| C13 | "`PASS` means only that the remote tip was the verified tip at that final observation: it does not read what any later commit wrote inside `handoff.md`, and the remote cannot be locked afterwards"; block L2 | patch L30; block L2 | F02, F03, F07 and the F-row classifications | supported by execution. "Only" understates what the PASS also asserts, which is non-material | no |
| C14 | "and last, that the live remote tip is still the verified tip" | patch L30; block L35–36 | F04, F06, F08, F09 (FAIL), F07 (ABA PASS) | supported by execution; "still" suggests continuity that is not checked | no (minor) |
| C15 | "Any `FAIL` line, or no `PASS`, means the transfer is INCOMPLETE" | patch L30; block L38 | every FAIL row prints the line and exits 1; 0 anomalies in summary.tsv | supported by execution | no |
| C16 | §7: "`git log --diff-filter=A --format='%H %P %s' -- handoff.md` … expected: that hash, then the transfer commit as its only parent" | patch L8 | H01 (same command, synthetic repo); H15, H16, H26b show config and rename sensitivity | supported in the synthetic case; the real repository history was not available | no (the real-repo outcome is UNTESTABLE here) |
| C17 | §16: "Section 7 and step 2 … no longer depend on the number of commits after the transfer commit" | patch L21 | H02 (zero follow-ups), H21 (40 follow-ups), H01 | supported by execution | no |
| C18 | §16: "…or on the path-filtered `git log`" | patch L21 | reading: block L26 is `git log --diff-filter=A … -- handoff.md`; H26b (result depends on `log.follow`), H15 | inaccurate or overstated. The block still uses a path-filtered log; the prose may mean only the older `git log --oneline -1 -- handoff.md` | yes (claim not satisfied; ambiguous reading noted) |
| C19 | §7 and §16 provenance statements (branch tips, commit dates, draft PR #90, a later commit adding the entry) | patch L8, L19–21 | none | UNTESTABLE from the package | not applicable |
| C20 | (not claimed in the prose) output sanitization of commit subjects | block L31 | H35: the subject is echoed raw, with `^M^[[2K^[[1GPASS at …` in stdout. The block still exits 1 and prints "TRANSFER INCOMPLETE", and there is no line starting PASS in the raw stream | no claim made; terminal display spoofing is possible. Not a contract false PASS, so not substantive | no (observation) |

## 5. Findings register (substantive)

All findings are classified OBSERVED unless marked otherwise. Raw output for each is in run3/evidence/<row>/ (stdout, stderr, rc, git_calls.log) or run3/evidence/G/. The commands and scripts are run3/harness/rows_h2.sh, rows_g.sh and rows_g2.sh, driven by lib.sh and wrapgit.sh.

**S6-1: Graft or replace ref gives a false PASS (rows H23, H24, H25).**
- **Source:** block L21, L25, L26 and L28.
- **Conditions:** git 2.43.0; the clone has `.git/info/grafts` (H23), `git replace --graft` (H24) or `git replace <tree>` (H25).
- **Commands:** `bash run3/harness/rows_h2.sh`; the rows are built by the harness.
- **Output:** `PASS at 2026-11-23T09:2x:…Z: remote tip 0fe3d994…; handoff commit 347873a3…` for H23 and H24 (invalid remote T→X→H→c1). For H25 the tip had a symlink for handoff.md.
- **Expected versus actual:** expected FAIL ("parent exactly T"; "regular file"). Actual PASS, rc 0. Controls H23c and H25c give FAIL.
- **Severity and impact:** high for the cardinal invariant. The "verify against the remote, not local objects" claim is not true.
- **Limitation:** needs a graft or replace ref present in the verifier's clone. Not fetched by the block's refspec.
- **Substantive:** yes.

**S6-2: Exit status inside `$( )` ignored; partial output accepted (row H29).**
- **Source:** block L30 (also L25, L26).
- **Conditions:** wrapper makes `git diff-tree` print only the first line (`handoff.md`) then exit 128 for the commit that also changes zz.txt.
- **Output:** `PASS at … 2 follow-up(s), each a single-parent child changing handoff.md alone`, rc 0.
- **Expected versus actual:** expected FAIL under contract clause 2 ("no other path"). Actual PASS.
- **Limitation:** simulated git failure. H30 attempted real corruption but failed at another check, so H30 does not reproduce this with real git. H28e shows the same blindness on a valid remote, where PASS is contract-correct.
- **Substantive:** yes (the brief names this technique in item A(ii)).

**S6-3: cwd dependence gives a false PASS and a false FAIL (rows H34, H33).**
- **Source:** block L21 and L26.
- **Conditions:** the block is run from a subdirectory of the clone.
- **Output:** H34 PASS despite a root symlink. H33 FAIL ("handoff.md is not a regular file") on a valid chain.
- **Expected versus actual:** H34 should FAIL under clause 3. Controls: H34c (run from the clone root) gives the correct FAIL.
- **Limitation:** H34 needs a contrived tree (root symlink plus a regular docs/handoff.md).
- **Substantive:** yes. The prose says only "from a clone".

**S6-4: Query-string token printed by git (row G04).**
- **Source:** block L17 and L18 (`git fetch` and `git ls-remote` stderr).
- **Conditions:** origin is `https://127.0.0.1:1/o/r?token=DUMMYTOKEN-xyz` (dead loopback port, proxies off, dummy token).
- **Output:** G04.stderr, 3 times: `fatal: unable to access 'https://127.0.0.1:1/o/r?token=DUMMYTOKEN-xyz/': Failed to connect…`. The block's own stdout does not print the token, and the identity FAIL line is present.
- **Expected versus actual:** the prose says "never printed". Actual: printed. git does redact userinfo (G01, G02, G05: 0 occurrences), but not a query-string credential.
- **Limitation:** the output comes from git, not the block's echo. Item E (credential protection) is in another stage, so this is overlapping evidence for G(4) only.
- **Substantive:** yes. A reproduced credential output, and a claim not satisfied.

**S6-5: Identity check accepts a URL whose connect host differs from the canonical host (rows G13, G14).**
- **Source:** block L15 (`auth=${rest%%/*}; ${auth##*@}`).
- **Conditions:** `https://u@127.0.0.1:1#@127.0.0.1:2/o/r` and `https://127.0.0.1:1?x@127.0.0.1:2/o/r`, with CANON set to `https://127.0.0.1:2/o/r`.
- **Output:** no "not the canonical" line (identity_FAIL_line=0). git's connect error shows it connected to 127.0.0.1 port 1, the pre-`#`/`?` host.
- **Expected versus actual:** "a fork, mirror or proxy URL fails the identity check" and the block's comment "dropped … the host part" are not true here.
- **Limitation:** no full end-to-end false PASS against an HTTPS server was built (no TLS server). So this is NOT RUN as a full false PASS; what is established is acceptance at the identity check with a different connect target. The end-to-end consequence is DERIVED. The related G03/G15/IDN cases failed closed.
- **Substantive:** yes (a claim the block does not satisfy).

**S6-6: "documentation-only" claim (rows H14, H10, H11).**
- **Source:** patch L30, last sentence.
- **Output:** PASS with an empty handoff.md (H14), after mode flips (H10), and after a symlink flip and back (H11).
- **Expected versus actual:** the block checks only the path, not the nature of the change.
- **Limitation:** the tip must still be 100644 and a regular file.
- **Substantive:** yes (claim not satisfied; contract-correct PASS in every case).

**S6-7: "no longer depend on … the path-filtered git log" (claim C18).**
- **Source:** patch L21; block L26.
- **Evidence:** DERIVED from reading block L26 plus OBSERVED H26b (a rename-add with `log.follow=true` gives a false FAIL).
- **Ambiguity:** the claim may mean only the §7 `-1` form.
- **Substantive:** yes by the strict reading; see C18.

## 6. Minor findings
- **False FAILs:** H221, H223 (shallow verifier clone, depth 1 and 3), H26b (`log.follow=true`), H27b (CRLF), H27e (trailing space) and H33 (subdirectory).
- **H27f:** hardening gap only. The extra ls-remote word is accepted because `$#` is not checked.
- **H28h:** the PASS line prints with an empty time when `date` fails.
- **H28i:** the PASS line loses its count when the second rev-list fails.
- **H35:** raw ESC and CR from a commit subject reach the terminal.
- **Identity checks that fail closed** (not defects): trailing slash, explicit port, `http`, upper-case host.

## 7. Not run, unreviewed or limited
- Full end-to-end false PASS through the `#` or `?` identity trick (S6-5): NOT RUN, no TLS server.
- SSH transport itself: only identity-string handling was tested (GIT_SSH_COMMAND=/bin/false).
- `url.<base>.insteadOf`, `http.proxy` and proxy environment effects on identity: NOT RUN.
- Case-variant filenames and gitlink entries for D: not in this stage's scope and not run here.
- Patch integrity G(1)–(3) (byte identity, clean apply, unrelated changes), and A–E and I: other stages.
- The real repository's history: not available, so the section-7 hash claims are UNTESTABLE here.
- H01–H21: taken from the earlier run, not re-run by me.

## 8. Environment
git 2.43.0; GNU bash 5.2.21(1)-release; Python 3.13.18 (not used to read package files); Linux 6.18.44. Every run used `env -i` with a minimal PATH, GIT_CONFIG_GLOBAL=/dev/null, GIT_CONFIG_SYSTEM=/dev/null, GIT_TERMINAL_PROMPT=0, fixed author and committer, dummy credentials, local bare origins, and loopback dead port 127.0.0.1:1 or :2 (NO_PROXY=127.0.0.1). No public network traffic.

## 9. Declaration
I am a Claude model sub-agent (Sonnet 5.5, claude-sonnet-5-5) in an independent context, from the same model family as the author. I am not a human. Tools: Bash, Read, Glob and Grep-style local inspection. I had no contact with the author's results. I did read the earlier runs of this same stage, as stated at the top. Date: 2026-11-23 (UTC).

## 10. Reproducibility
- Harness: stage_S6/run3/harness/lib.sh and wrapgit.sh.
- Rows: rows_h2.sh (H221–H35), rows_f.sh (F01–F09), rows_g.sh (G01–G12), rows_h3.sh (H36–H39 and the IDN string check), rows_g2.sh (G13–G15), rows_h4.sh (H40–H42).
- Run from stage_S6/run3: `bash harness/rows_h2.sh; bash harness/rows_f.sh; bash harness/rows_g.sh; bash harness/rows_g2.sh; bash harness/rows_h3.sh; bash harness/rows_h4.sh`.
- Output goes to run3/summary.tsv, run3/evidence/<row>/ and run3/evidence/G/ and IDN/.
- The earlier tables of record are stage_S6/summary.tsv (66 rows) and stage_S6/harness/RUN_ALL.sh.

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
