STAGE S6: COMPLETE (review of REV3 block and patch: item F, item G part 4, item H)

SUBSTANTIVE FINDINGS: yes (3 reproduced false PASS mechanisms in item H, plus 5 patch-prose claims contradicted or overstated, one of which includes reproduced output of a credential by git itself).

## 1. Package integrity
- Authoritative SHA-256 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286.
- I computed the full SHA-256 of the original zip, of my copy (pkg_copy.zip) and of a fresh re-extraction (pkg2/). All three matched. SHA256SUMS.txt: 7 of 7 members OK. pkg/ and pkg2/ are identical (diff -r). The original zip was never modified.
- The stage directory is /tmp/claude-0/-home-claude/3adcc49e-2c16-5b57-97ab-65b038335fc4/scratchpad/a9/stage_S6/. The prior attempt's report is kept as REPORT_S6_prior_1.md and was treated as unverified.
- Package files were only read or copied. Each block copy differed from the original only in the CANON=, T= and H= values, and mkblock checks that three lines changed. The one exception is the Part 1 identity table, where CANON was left at the original value, so only T and H changed (the tool printed "changed 2 lines (expected 3)" for that block). Python reading package files was not needed.

## 2. Criteria table (one status each)
| Criterion | Status | Basis |
|---|---|---|
| F. Race between last observation and reading PASS; prose accuracy | PASS (with one dependency, see below) | F01–F09. The race is real and unavoidable, and the prose states it accurately. The word "verified" in "was the verified tip" is only as good as the H findings. |
| G part 4. Prose and technical-claim consistency | FAIL | Findings S6-G4-01 to S6-G4-05 (claims contradicted by execution). |
| H. Shell and git pitfalls | FAIL | Findings S6-H-01 to S6-H-03 (reproduced false PASS). |

## 3. Item F: rows tested (evidence/F_summary.tsv, raw evidence/F0*.{out,err,rc})
| Row | Scenario | Result |
|---|---|---|
| F01 | Baseline, stable remote | PASS |
| F02 | Remote branch moved immediately after the final `ls-remote` answer, before PASS is printed | Block prints PASS naming the old tip. The remote tip afterwards is a different commit (655e512ac0a7 vs verified ed0f940d5711). Unavoidable race observed. |
| F03 | Moved after the 1st `ls-remote` | FAIL "moved during verification" |
| F04 | Moved between fetch and 1st `ls-remote` | FAIL "live remote tip differs from the fetched tip" |
| F05 | Moved during the structural checks | FAIL |
| F06 | Moved away after the 1st `ls-remote` and back before the final one | PASS. The check is a point comparison of identical tips, not continuity. |
| F07 | 3 s latency after the final answer is obtained | PASS line time is about 3 s later than the observation. Natural gap is about 13 ms (F07b, 10 runs). |
| F08empty, F08garbage | Last follow-up replaces handoff.md with an empty file or random bytes | PASS, and the follow-up is listed. Confirms the block never reads content. |
| F09 | stdout closed | Exit 0 with no PASS line printed. The contract is met, so this is minor. |

F assessment of the prose "`PASS` means only that the remote tip was the verified tip at that final observation: it does not read what any later commit wrote inside `handoff.md`, and the remote cannot be locked afterwards":
- Supported by execution: F02 (cannot be locked) and F08 (content not read).
- Understated: no. Overstated: no.
- Wording notes (minor):
  - The UTC time in the PASS line is taken when the line is printed, not when the final observation was made (F07). The prose does not claim otherwise.
  - "still the verified tip" is a point comparison (F06).
  - Whether `ls-remote` and `fetch` can be served by different replicas of a real server is unverifiable here.
- Dependency: "verified" is only true in a clone without replace refs, grafts or a subdirectory cwd (S6-H-01 to S6-H-03).

## 4. Item H: rows tested
About 100 rows, in evidence/H_summary.tsv, evidence/H2_summary.tsv and evidence/final_summary.txt. Raw output per row is evidence/<ROW>.{out,err,rc}. Everything ran with real bash and real git 2.43.0 in synthetic repositories, plus a `git` wrapper only where stated. "FP" below means reproduced false PASS.

| Group | Rows | Result |
|---|---|---|
| Baselines, rev-list ordering (commit dates opposite to topological, 2030/2026 non-monotone) | H01–H04 | PASS as required |
| Wrong-shape history: merge tip; other path; rename or copy with `diff.renames=copies`/`true`; gitlink with and without `diff.ignoreSubmodules=all`; empty commit | H11, H12, H13a–d, H13e2/e3, H15 | FAIL as required |
| Mode-only changes (+x then −x) | H14a | PASS as required |
| Tip left at 100755 | H14b | FAIL as required |
| handoff.md already present in T | H18 | FAIL as required |
| Shallow clones: depth 1, depth 50, `.git/shallow` hiding a parent | H23a–d | Fail closed; depth 50 PASS |
| Environment: IFS=x and tab/newline, SHELLOPTS errexit/nounset/noglob/posix/pipefail, GLOBIGNORE=*, script args `a b *`, LC_ALL=C and en_US.UTF-8, cwd containing files named `100644`, `blob`, `*`, `handoff.md*`, `refs` | H05a–t | PASS, no effect |
| Follow-up changing handoff.md plus a path named `a b`, ` handoff.md`, `-rf`, `*`, `x?`, `[ab]`, a name with CR, a name with LF, `handoff.md<LF>`, `handoff.md ` | H33_1–10 | All FAIL as required |
| Real remote ref pitfalls: extra branch `zz/refs/heads/<BR>`; BR deleted with only the tail-match branch left; unrelated extra branches | H29a, H29c, H36 | Correct (FAIL, PASS, FAIL) |
| Wrapper-faked `ls-remote`: empty output, non-zero exit after a good line, two lines, first field `-n`/`-e`/`-E` | H24c, H24e, H24j, H24d-n/-e/-E | FAIL as required |
| Grafts, replace refs, mirror clone, symlink tip, subdirectory cwd | H21b, H21c2, H21e, H21g, H22a2, H39b | FP (see S6-H-01 to S6-H-03) |
| Controls for the above | H21a, H21d2, H21f, H21h, H22b2, H39c | FAIL as required |

H21f is a control: a graft was present but `GIT_GRAFT_FILE=/dev/null`. Its description in the TSV mislabels it "plain".

Set-up artefacts to ignore (not real tests): the first version of H13e (gitlink was not committed; redone as H13e2/e3), H33_11 (no commit was created), the first versions of H22a, H24g/H24h and H35a, and the first H39a (block file absent; redone in final_checks.sh).

## 5. Item G part 4: claim table
Class key: E = supported by execution evidence I produced; R = supported only by reasoning; C = contradicted; U = unverifiable in this blinded setting (no repository or history was available).

| # | Claim (location) | Class | Evidence |
|---|---|---|---|
| 1 | "credentials in the URL are ignored and never printed" (patch step 2) | C | `https://<token>@host/...` is accepted by the identity check (I08). When the server asks for a password, git itself prints "fatal: could not read Password for 'https://DUMMYTOKEN-xyz@127.0.0.1:PORT': terminal prompts disabled" (U02, W6). Query and path tokens are printed by git too (W1–W3). Userinfo of the form user:token is anonymised by git (U01, U03, U04, W4, W5). The identity check ignores credentials as claimed (I07, I08). |
| 2 | "credentials in the host part are dropped, so they are neither compared nor printed" (block line 15 comment) | E for the block's own output, C as a whole-run statement | Across all runs no block stdout contained the token or the configured URL (0 files); the stdout text only contains the CANON constant. The token appeared on git's stderr (claim 1). |
| 3 | "the configured URL is not printed because it may carry credentials" (block line 16 message) | E for the block's own text, C for the whole run | Same as claim 2. Git prints the URL on stderr in W1–W3. |
| 4 | "a fork, mirror or proxy URL fails the identity check by design" (patch step 2) | C for look-alikes, E for the classic ones | Rejected as claimed: `github.com@evil` (I09), `evil/x@github.com` (I10), uppercase scheme or host (I11, I12), trailing slash (I13), `:443` (I14), `http` (I15), ssh with password (I16), query (I17), `.git.git` (I18), `git@github.com:/…` (I19), ssh port (I20), path traversal (I25), empty URL (I26). Accepted by the identity check: `https://HOST#@github.com/…` and `https://HOST?@github.com/…` (I21, I22). Git really contacts HOST: the fork server got 3 requests and the canonical server 0 (T3_hash, T3_query, V1). The backslash form is accepted by the check but git contacted the canonical host (V3), so no discrepancy there. Proxy and transparent-mirror behaviour outside the URL string was not tested (U). |
| 5 | "the SSH forms and a trailing `.git` are accepted" (patch step 2) | E, with narrowing | Accepted: scp-like and `ssh://git@github.com/…`, each with and without `.git` (I01–I06). Other SSH shapes are rejected (I16, I20). "The SSH forms" means exactly those two. |
| 6 | "Verify the checkpoint against the remote branch, not against local objects" (patch step 2) | C | The structural checks read local objects through local replace refs, grafts and a cwd-relative pathspec. See S6-H-01 to S6-H-03. |
| 7 | "Run the block … from a clone whose origin is the canonical repository" (patch step 2) | C for subdirectories | False PASS from `docs/` (H39b); false FAIL from `docs/` on a valid chain (H39a). |
| 8 | "the fetched branch tip against the live remote tip (each `git ls-remote` must succeed and return exactly one ref with the exact branch name)" (patch step 2 and block line 9 comment) | E for conformant git output, C for simulated non-conformant output | Real git: tail-matching branch or tag gives two lines and FAIL (H29a, H29b); failing or empty `ls-remote` gives FAIL (H24c, H24e). Simulated non-conformant lines are accepted: a space inside the name (H24k), a second ref on the same line (H24l), a glob name when a matching file exists in cwd (H24m), an extra invalid-UTF-8-only line (H24i). Cause: `set -- $out` (unquoted) and `grep -c .`. |
| 9 | The listed order of checks (patch step 2) | E, incomplete | Matches the code order. The prose list omits the check that H is the commit that adds handoff.md (block line 26). |
| 10 | "that `handoff.md` is a regular file (mode 100644) in the remote tree" (patch step 2) | E, C under poisoning | H14b, H22b2; contradicted by H22a2. |
| 11 | "every later commit is a single-parent child of the previous one that changes `handoff.md` alone" (patch step 2) | E, C under poisoning | H11–H15 hold (this includes the diff-tree options, mode-only changes and empty commits); contradicted by H21b, H21c2, H21e, H21g. |
| 12 | "It must print a `PASS` line with a UTC time" (patch step 2) | E | F01. The time is the print time (F07). |
| 13 | "`PASS` means only … and the remote cannot be locked afterwards" (patch step 2; block lines 1–2) | E | F02, F08. |
| 14 | "Any `FAIL` line, or no `PASS`, means … INCOMPLETE" (patch step 2) | E, with a presentation weakness | Every FAIL run ends with the TRANSFER INCOMPLETE line, except runs where the shell aborts (H05p dash, H05s CRLF, rc 2, no PASS). A hostile follow-up subject can hide FAIL lines on a terminal (S6-O-01). |
| 15 | "Each follow-up commit it lists is a documentation-only change to `handoff.md`" (patch step 2) | C if read literally | The block checks the path set only. Random bytes in handoff.md are listed and PASS (F08garbage). |
| 16 | "they no longer depend on the number of commits after the transfer commit or on the path-filtered `git log`" (patch section 16, last-but-one bullet) | Count part E; `git log` part C if read literally | Any number of follow-ups works (H02, H03, H04). The block still runs `git log --diff-filter=A … -- handoff.md` (line 26). Its verdict depends on history shape and user config: false FAIL for delete and re-add (H16), false FAIL with `log.follow=true` on a rename-added handoff (H19c). A charitable reading refers only to the old `git log --oneline -1 -- handoff.md`. |
| 17 | Section 7: "`git log --diff-filter=A --format='%H %P %s' -- handoff.md` … (expected: that hash, then the transfer commit as its only parent)" | E in synthetic repos | Prints "H T handoff" (final_summary.txt). Config sensitivity as in claim 16. |
| 18 | Section 7: "`git log --oneline -1 -- handoff.md` therefore returns that later commit, not the handoff commit" | E in synthetic repos | Returns the latest follow-up ("followup 3"). The statement about the real branch is U. |
| 19 | Section 16 provenance statements (commit `2dd2e7bb…`, dates, "not mentioned in … `51564e34…`", "later documentation-only commits") | U | The package has no history or repository. |
| 20 | What has and has not been tested | n/a | No claim of that kind exists in the added patch lines or the block comments (grep, final_summary.txt). |

## 6. Findings register (substantive)

### S6-H-01. FALSE PASS through local replace refs
1. Id: S6-H-01
2. Location: rev3/verify_block_rev3.sh lines 21–26, 28–30 (`git ls-tree`, `git merge-base`, `git show -s`, `git log`, `git rev-list`, `git diff-tree` all honour `refs/replace/*`). Patch lines 53–62.
3. Conditions: the clone has `refs/replace/<remote-tip-or-chain-commit>`. Realistic route: a clone made with `git clone --mirror` imports `refs/replace/*` that someone with write access pushed to the remote (H21g).
4. Commands and inputs:
   - H21c2: remote chain T→H→P→M, where M is a merge commit (parents P and a side commit). Locally `git replace M X`, where X is a single-parent twin with the same tree.
   - H21g: the same remote, with `refs/replace/M` pushed to origin, then `git clone --mirror`, then the block with only CANON, T and H changed.
   - H22a2: remote tip has `handoff.md` as a symlink (120000); local replace ref maps it to a regular-file twin.
5. Output:
   - H21c2: `PASS at …: remote tip 94acd9e9…; … 2 follow-up(s), each a single-parent child changing handoff.md alone`, rc 0. `git cat-file -p` on the real remote tip shows two `parent` lines.
   - H21g: PASS, rc 0.
   - H22a2: PASS, rc 0.
6. Expected: FAIL (a merge tip, or a symlink tip, violates contract points 2 and 3). Actual: PASS.
   - Controls, all FAIL: H21a (clean clone), H21d2 and H22b2 (`GIT_NO_REPLACE_OBJECTS=1`), H21h (ordinary clone of the same remote).
7. Severity: High for the cardinal invariant (PASS with the contract unmet), but it needs a poisoned clone. Impact: the block checks fetched objects as seen through local object substitution, not the remote's real objects.
8. Class: OBSERVED (FALSE PASS).
9. Limitations: the poisoned state is created by the tester or by a mirror clone plus a hostile push. A plain clone is not affected (H21h). The block's own fetch never imports `refs/replace`.
10. Substantive under the acceptance contract: yes (a reproduced false PASS). It also contradicts prose claim 6.

### S6-H-02. FALSE PASS through grafts
1. Id: S6-H-02
2. Location: same lines as S6-H-01 (git reads the graft file for every history walk).
3. Conditions: `.git/info/grafts` (git 2.43.0 still honours it; `GIT_NO_REPLACE_OBJECTS=1` does not disable it).
4. Commands and inputs: the merge-tip remote of H21; `echo "<M> <P>" > .git/info/grafts`.
5. Output:
   - H21b (graft, plain environment): PASS, rc 0, with the same "each a single-parent child" line.
   - H21e (graft plus `GIT_NO_REPLACE_OBJECTS=1`): PASS, rc 0.
6. Expected: FAIL. Actual: PASS. Control H21f (`GIT_GRAFT_FILE=/dev/null`): FAIL.
7. Severity: High for the invariant, narrow preconditions; the graft file is a local administrator or developer artefact.
8. Class: OBSERVED (FALSE PASS).
9. Limitations: git 2.43.0 only. Newer git versions may deprecate grafts. Not tested there.
10. Substantive: yes.

### S6-H-03. FALSE PASS (and false FAIL) when run from a clone subdirectory
1. Id: S6-H-03
2. Location: lines 21 and 26 (`git ls-tree "$TIP" -- handoff.md` and `git log … -- handoff.md` take cwd-relative pathspecs); line 62 (`diff-tree` prints root-relative names).
3. Conditions: cwd is a subdirectory of the clone.
4. Commands and inputs:
   - H39b: H adds both `handoff.md` and `docs/handoff.md`; a follow-up makes root `handoff.md` executable (100755). The block is run from `clone/docs`.
   - H39a: valid chain, run from `clone/docs`.
5. Output:
   - H39b: PASS rc 0. The control H39c (same remote, run from the clone root) gives FAIL "handoff.md is not a regular file (mode 100644, blob)".
   - H39a: FAIL "handoff.md is not a regular file" on a valid chain.
6. Expected: H39b FAIL, H39a PASS. Actual: the opposite.
7. Severity: Medium. The false PASS layout is contrived (a second `docs/handoff.md` added in H). The false FAIL from any subdirectory is the common case.
8. Class: OBSERVED (FALSE PASS; also FALSE FAIL).
9. Limitations: a single contrived layout for the false PASS.
10. Substantive: yes (reproduced false PASS). It also contradicts prose claim 7 ("from a clone", which does not require the root).

### S6-G4-01. Credential claim contradicted (git's own output)
1. Id: S6-G4-01
2. Location: patch step 2 ("credentials in the URL are ignored and never printed"); block line 15 and line 16 comments.
3. Conditions: origin is `https://<token>@host/org/repo(.git)` (an accepted form) and the server answers 401, so git wants a password; or the token sits in the query or path of a non-accepted form.
4. Commands and inputs: local TLS server with Basic auth (scripts/httpsd.py), dummy token DUMMYTOKEN-xyz, no proxies, loopback only. Rows U02, W6, W1, W2, W3.
5. Output (stderr, from git):
   - U02 and W6: `fatal: could not read Password for 'https://DUMMYTOKEN-xyz@127.0.0.1:PORT': terminal prompts disabled`, printed three times per run.
   - W1: `fatal: repository 'https://127.0.0.1:PORT/org/repo.git?token=DUMMYTOKEN-xyz/' not found`.
   - W2: `fatal: repository 'https://127.0.0.1:PORT/DUMMYTOKEN-xyz/repo.git/' not found`.
   - W3: `fatal: unable to access 'https://127.0.0.1:1/org/repo.git?token=DUMMYTOKEN-xyz/': Failed to connect …`.
6. Expected: no credential or URL printed anywhere in the run. Actual: printed by git on stderr. The block's own stdout never contains it.
7. Severity: High for the output-secrecy contract (credential output reproduced). Token-as-username is a common PAT form.
8. Class: OBSERVED (SECRET OUTPUT; PROSE INACCURACY).
9. Limitations: git 2.43.0 and curl 8.5.0. The token-as-username leak needs a server that demands a password. User:token userinfo is anonymised by git in all tested messages (U01, U03, U04, W4, W5).
10. Substantive: yes (output of a credential; claim not satisfied).

### S6-G4-02. "Fork, mirror or proxy URL fails the identity check by design" contradicted
1. Id: S6-G4-02
2. Location: patch step 2; block lines 15–16.
3. Conditions: origin is `https://HOST#@github.com/1h0lde4/ocbrain-v4.1` or `https://HOST?@github.com/…`. The URL parser in the block takes everything before the first `/` as authority and strips up to the last `@`.
4. Commands and inputs: identity table I21 and I22 (wrapper returns the URL from `git remote get-url`), and real-transport rows T3_hash, T3_query and V1 (a fork server with identical history and no auth; the canonical server on another port).
5. Output: I21 and I22 are accepted by the identity check. In T3_hash, T3_query and V1 the identity message is not printed; the fork server received 3 requests and the canonical server 0.
6. Expected: identity rejection. Actual: accepted, while git talks to a different host.
7. Severity: High if a fork can then serve identical history (that is the FALSE PASS case of brief items A(iv) and B).
8. Class: OBSERVED for the identity acceptance and the real connection target. DERIVED for the end-to-end false PASS.
9. Limitations: an end-to-end PASS through a fork was not obtained, because my git-http-backend based test server does not answer `GET /` (the `#` form drops the path); verdicts were FAIL for that reason. The `\@` form went to the canonical host (V3).
10. Substantive: yes (prose claim contradicted by execution).

### S6-G4-03. "against the remote branch, not against local objects"
Same evidence as S6-H-01, S6-H-02 and S6-H-03. The checks run on locally stored objects through replace refs, grafts and cwd-relative pathspecs. Class: OBSERVED. Substantive: yes (claim not satisfied).

### S6-G4-04. "no longer depend on … the path-filtered `git log`"
1. Id: S6-G4-04
2. Location: patch line 21; block line 26.
3. Conditions: block run on histories where handoff.md is deleted and re-added in follow-ups, or added by rename with `log.follow=true`.
4. Commands and inputs: H16, H19a/b/c.
5. Output: H16 FAIL "handoff.md was not added by the handoff commit"; H19c FAIL (the same with `log.follow=true`); H19a and H19b PASS.
6. Expected: verdict independent of a path-filtered `git log`. Actual: the verdict depends on it and on user config.
7. Severity: Low (false FAIL only); the prose is overstated.
8. Class: OBSERVED (PROSE INACCURACY if read literally).
9. Limitations: a charitable reading refers only to the older `git log --oneline -1 -- handoff.md` command.
10. Substantive: borderline by the letter (a claim the block does not satisfy), minor in practice.

### S6-G4-05. "Each follow-up commit it lists is a documentation-only change to `handoff.md`"
1. Id: S6-G4-05
2. Location: patch line 30.
3. Conditions: a follow-up replaces handoff.md content with anything.
4. Commands and inputs: F08empty, F08garbage.
5. Output: PASS, with `follow-up: <hash> rewrite handoff (garbage)` listed.
6. Expected (if the claim were enforced): FAIL or a content check. Actual: path-only check; the same prose says the block does not read content.
7. Severity: Low (wording).
8. Class: OBSERVED.
9. Limitations: only a path-level notion of "documentation-only" is verifiable.
10. Substantive: borderline by the letter, minor in practice.

### S6-O-01. Commit subject printed unsanitised (incidental, class OTHER)
- Block line 31 prints `git log --format='%H %s'` of each follow-up.
- Rows H34a and H34c: a subject containing CR, a fake `PASS at …` line and `ESC[8m` goes to stdout raw; `cat -v` shows `^MPASS at …^[[8m`.
- A simulated terminal view (CR overwrite plus conceal) of H34c shows a single visible `PASS at …` line with the FAIL and TRANSFER INCOMPLETE lines concealed (evidence/H34c.rendered.txt).
- Raw output never starts a line with PASS in the failing chain, and the exit status is 1. The terminal rendering is DERIVED (my emulator); the raw bytes are OBSERVED. The attacker needs push access to the canonical branch.
- Not substantive under the stated contract; reported for the owner's decision.

## 7. Minor findings
- Observed false FAIL: delete and re-add of handoff.md (H16); `log.follow=true` (H19c); a harmless tag `refs/tags/refs/heads/<BR>` on the remote breaks verification (H29b); CR at the end of a fake `ls-remote` line (H24d, simulated); URL with a trailing newline or CR in the config value (H35a2, H35b; fetch or identity fails); run from a subdirectory (H39a); run with `sh` (dash: `set -o pipefail` illegal, rc 2, H05p); block saved with CRLF (rc 2, H05s). In the last two there is no TRANSFER INCOMPLETE line, only the missing PASS.
- Exit 0 with no PASS line when stdout is closed (F09).
- The exit status of command substitutions is ignored for rev-list, diff-tree, ls-tree, show and log (H27, simulated with forced exit 1; harmless because outputs are compared). Real git does not print complete correct output and then fail, so I could not reach this with real git.
- PASS line time is print time (F07). The prose list of checks omits the "added by H" check. "The SSH forms" means exactly two forms.
- I24 in my own table has a wrong expectation: `https://evil.example:x@github.com/…` is userinfo on host github.com, so accepting it is correct.
- IFS, SHELLOPTS, GLOBIGNORE, locale, cwd globs, shallow clones and special path names caused no false PASS (H05, H23, H33).

## 8. Not reviewed or not verified
- Items A, B, C, D, E, I (other stages). Identity and credential checks here are limited to what prose claims of G part 4 assert; I did not enumerate B and E cases.
- Parts 1–3 of G (embedded block identical, patch applies, unrelated changes): not redone; no failure observed incidentally.
- Section 7 and 16 factual claims about real branch history (U): no repository access by design.
- A real github.com connection, proxies, `http.proxy`, `insteadOf` rewriting of origin, SSH transport (ssh binary absent: `cannot run ssh`), GPG-signed commits and `log.showSignature`, partial clones with lazy trees, replicas of real servers, SHA-256 repositories, other git versions or shells.
- An end-to-end false PASS through a fork via `#@` (not obtained).
- The H27, H24i/k/l/m rows rely on the wrapper (simulated outputs).

## 9. Environment and tools
git 2.43.0, GNU bash 5.2.21, Python 3.13.18, curl 8.5.0, OpenSSL 3.0.13, dash as /bin/sh, Linux 6.18. Every run used `env -i` with GIT_CONFIG_GLOBAL=/dev/null, GIT_CONFIG_SYSTEM=/dev/null, GIT_TERMINAL_PROMPT=0, fixed author and committer, no proxy variables, NO_PROXY=127.0.0.1, loopback only. Dummy token DUMMYTOKEN-xyz only. Local servers (self-signed certificate, `scripts/httpsd.py` wrapping git-http-backend) were stopped after use.

## 10. Declaration
I am a Claude model sub-agent (Sonnet 5.5) with an independent context, from the same model family as the author; not a human. Tools: shell, file read, edit and write, git, python3. I had no contact with the author's test results or other stages' results. The prior attempt's report (REPORT_S6_prior_1.md) was not relied on. Date: 2026-11-14 (tests run 2026-11-13 and finished 2026-11-14).

## 11. Reproducibility (all under /tmp/claude-0/-home-claude/3adcc49e-2c16-5b57-97ab-65b038335fc4/scratchpad/a9/stage_S6/)
Run in this order with `bash scripts/<name>` from that directory, after extracting the package copy into pkg2/ and checking SHA256SUMS.txt:
- scripts/lib.sh (sourced helpers; world builder, mkblock that substitutes only CANON/T/H, runblock)
- scripts/F_race.sh (item F; uses wrap/git, wrap/advance.sh and back.sh, which it generates)
- scripts/H_pitfalls.sh, then scripts/H2_fixes.sh (item H; H2 contains corrected rows and the replace, graft and mirror-clone rows)
- scripts/G4_claims.sh (identity table, Part 2 credentials on loopback TLS, Part 3 `#@` forms; starts scripts/httpsd.py)
- scripts/G4b_claims.sh (git's own messages for query and path tokens, `#@` against a no-auth fork server)
- scripts/final_checks.sh (subdirectory rerun, section 7 commands, leak scan, prose grep for testing claims)
- Row tables: evidence/F_summary.tsv, H_summary.tsv, H2_summary.tsv, G4_summary.tsv, G4b_summary.tsv, final_summary.txt. Status notes: evidence/PROGRESS_F.txt, PROGRESS_H.txt, PROGRESS_G4.txt. Raw output per row: evidence/<ROW>.out/.err/.rc. Index: evidence/INDEX.txt. Report stub: REPORT_S6.md.

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
