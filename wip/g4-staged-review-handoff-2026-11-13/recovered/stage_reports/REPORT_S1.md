# STAGE S1 — FINAL REPORT (package integrity, criterion A, criterion G items 1-3)

Directory: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S1/
Date: 2026-11-12 (UTC). Run after the coordinator's resume message. The directory holds only a stale provisional stub `REPORT_S1.md` (first line "STAGE S1: IN PROGRESS"), written before the instruction not to write report files. It is superseded by this message and was not updated.

**SUBSTANTIVE FINDINGS (REV3 block, criteria A and G1-3): no.** One incidental observation, S1-I1 (git's own diagnostics print the remote URL), is substantive under the brief's literal wording ("any reproduced output of a credential or URL"). It belongs to item E and is handed to that stage. Details are in the findings register.

## 1. Package integrity
- Zip copied byte for byte. Full SHA-256 computed: `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`. This equals the authoritative value in the preamble (MATCH). Evidence: evidence/zip_sha256.txt.
- Extracted with `python3 -I` into pkg/review_package/. `sha256sum -c SHA256SUMS.txt` gave 7/7 OK (evidence/sha256sums_check.txt).
- Package contents (full listing in evidence/zip_listing.txt):

| File | Bytes | SHA-256 (from SHA256SUMS, all verified) | What it is |
|---|---|---|---|
| README_FIRST_REVIEW_BRIEF.md | 8166 | c74e752e…f629 | Review brief, items A-I |
| SHA256SUMS.txt | 776 | n/a | Checksums |
| base/handoff.md | 57663 | 9e33cf1a…6d55 | File the patch applies to (547 LF lines, no CR) |
| rev2/verify_block.sh | 1994 | 014fad47…519f | REV2 block. It has no `CANON=` line and no `set -o pipefail`. |
| rev3/verify_block_rev3.sh | 3453 | e1ccd6a7…4d53 | REV3 block under review (38 lines) |
| rev3/P1d_rev3_…_PROPOSED.patch | 12936 | 98468b11…0cb0 | Patch embedding the block and new prose into handoff.md (no `diff --git` header, 3 hunks) |
| optional_item_I/ (2 files) | 19091 / 14360 | d619b7c8…, 60d59bf5… | Item I only; not opened by me |

## 2. Criteria table (one status each)

| Criterion | Status | Evidence and reasoning |
|---|---|---|
| **A. REV2/REV3 regression assessment** (brief item A, six cases against both blocks) | **PASS** | All six cases (i)-(vi) ran against rev2 and rev3. rev2 gives a false PASS in (i) (two variants), (ii), (iii), (iv) and (vi), and in (v) when the failing call prints the correct ref first. rev3 gave a correct FAIL (exit 1) in every defect case, and a correct PASS on three valid baselines. rev3 failed closed in all of them. No rev3 false PASS was reproduced. S1-I1 does not change this status: it is a diagnostic-output issue for item E, not an A-case verdict. |
| **G(1). Embedded block byte-identical to rev3/verify_block_rev3.sh** | **PASS** | Two independent extractions are byte-identical (3453 bytes, sha256 e1ccd6a7…4d53). |
| **G(2). Patch applies cleanly to base/handoff.md** | **PASS** | `git apply --check` exit 0 in a scratch repo, and `patch -p1 --dry-run` exit 0. |
| **G(3). No unrelated changes** | **PASS** | Exactly three hunks, matching intended changes (a), (b) and (c). The reconstruction check held. Detail in section 5. |
| G(4) prose-claim comparison | NOT RUN | Assigned to another stage. |
| Items B, C, D, E, F, H, I | NOT RUN | Other stages. |

## 3. Criterion A: cases and results

**Method (all OBSERVED, none REPORTED or DERIVED).**
- Harness: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S1/scripts/run_cases.sh, with lib.sh and gitwrap.sh in the same directory.
- Each case gets a fresh throw-away bare origin and a clone. The branch is `docs/g4-fts-errata-handoff-oct2026`. T is a commit with README.md and other.txt, and H adds handoff.md. Synthetic T=f359390b…, H=62586941…, content follow-up f1=5ccef8cb….
- Only the `CANON=`, `T=` and `H=` lines of each block copy were substituted. rev2 has no CANON line, so only T and H. Every `block_subst.diff` shows only those lines differing (14 rev2 runs show 2 changed lines, 14 rev3 runs show 3). For rev3, CANON was the synthetic origin path without `.git`.
- Each block ran from inside the clone under `env -i PATH=<wrapper>:/usr/bin:/bin`, with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0` and fixed author/committer variables. No proxy variables and none of the sandbox's tokens were present. No network traffic; origins are local paths.
- A wrapper named `git`, first in PATH and calling /usr/bin/git, intercepts only `git ls-remote`. It can print the correct ref and then exit non-zero, fail silently, or run a hook that moves the remote branch before or after the Nth call. Other subcommands pass through untouched.
- Each run was classified against an independent post-run "oracle" of the final remote state (chain, paths touched, `handoff.md` mode). Fork identity is known by construction.
- The harness was run twice. Exit codes were identical for all 14 original scenarios (run 1 vs run 2). Run 2 added case A5d.
- Raw outputs: evidence/A/<case>/{rev2,rev3}.{stdout,stderr,combined,exit,lsremote_calls.log,oracle,block_subst.diff}. Summary: evidence/A/summary.tsv.

| Case | rev2: printed → exit → class | rev3: printed → exit → class |
|---|---|---|
| **C00a** baseline, tip = H (valid) | `PASS: handoff commit 62586941… 0 follow-up(s)…` → 0 → correct PASS | `PASS at <UTC time>: remote tip 62586941…` → 0 → correct PASS |
| **C00b** baseline, H + 1 follow-up (valid) | PASS → 0 → correct PASS | PASS → 0 → correct PASS |
| **C00c** baseline, H + 3 follow-ups (valid) | PASS → 0 → correct PASS | PASS → 0 → correct PASS |
| **A1 (i-a)** remote moves right after the 1st `ls-remote`; new tip (aad81f1d) changes other.txt | `follow-up: 5ccef8cb f1` / `PASS: handoff commit 62586941… 1 follow-up(s), each a single-parent child changing handoff.md alone` → 0 → **FALSE PASS**. Final remote tip: oracle says VIOLATION (touches other.txt). | `FAIL: the remote branch moved during verification (now aad81f1d…)` + `TRANSFER INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED` → 1 → **correct FAIL** (wrapper log: call #2 returned aad81f1d) |
| **A1 (i-b)** same, but the move is a force-push to unrelated history (7102e2dd) | PASS → 0 → **FALSE PASS** (oracle: not a child, multi-path, no `handoff.md`) | `FAIL: … moved during verification (now 7102e2dd…)` → 1 → **correct FAIL** |
| **A1x** (extra) move just before the 1st `ls-remote` | `FAIL: live remote tip (aad81f1d…) differs from the fetched tip (5ccef8cb…)` → 1 → correct FAIL | Same FAIL, plus the "moved during verification" FAIL → 1 → correct FAIL |
| **A1y** (extra, item-F territory) move after the 2nd call | The hook never fires (rev2 has one call). PASS → 0 → correct PASS (final state valid). | PASS at <time> → 0. Final remote state is a violation, because the move came after the last observation. This is the inherent race, not a false PASS under the contract's "at its final live observation". See minor M1. |
| **A2 (ii)** every `ls-remote` prints the correct ref then exits 3 | stderr "wrapper: simulated non-zero exit…"; `PASS: handoff commit …` → 0 → **FALSE PASS** (the pipe through `cut` swallows the status; there is no pipefail) | 4 FAIL lines (`git ls-remote failed or did not return exactly one matching ref`, `live remote tip (none) differs…`, `the final git ls-remote failed…`, `moved during verification (now unknown)`) + TRANSFER INCOMPLETE → 1 → **correct FAIL** |
| **A3 (iii)** `handoff.md` becomes a symlink (mode 120000) in a later commit | `follow-up: 51673e57 symlink handoff.md` / `PASS: … 2 follow-up(s)…` → 0 → **FALSE PASS** (oracle: mode 120000) | `FAIL: handoff.md is not a regular file (mode 100644, blob) in the remote tree` → 1 → **correct FAIL** |
| **A4 (iv)** origin is a fork/mirror (bare clone) with identical history | PASS → 0 → **FALSE PASS** (rev2 has no identity check) | `FAIL: origin is not the canonical repository (<CANON>); the configured URL is not printed because it may carry credentials` → 1 → **correct FAIL**. The fork path does not appear in the output (grep count 0). |
| **A5 (v)** only the final `ls-remote` fails, silently, exit 128 (rev2: its only call #1; rev3: call #2) | `FAIL: the remote branch does not exist` + `FAIL: live remote tip () differs…` → 1 → correct FAIL (via an empty LIVE, not an exit-status check) | `FAIL: the final git ls-remote failed or did not return exactly one matching ref` + `moved during verification (now unknown)` → 1 → **correct FAIL** |
| **A5b (v-b)** only the final `ls-remote` prints the correct ref then exits 3 | PASS → 0 → **FALSE PASS** (same defect as ii) | FAIL (final ls-remote failed) → 1 → **correct FAIL** |
| **A5c** (extra) only the FIRST `ls-remote` fails silently | FAIL (remote branch does not exist) → 1 | `FAIL: git ls-remote failed…` + `live remote tip (none) differs…` → 1 → correct FAIL |
| **A5d (v-c)**, NOT simulated: origin directory really removed (rev2: before its only call; rev3: after call #1) | git's own `fatal: '<origin path>' does not appear to be a git repository`; FAIL ×2 → 1 → correct FAIL | Same fatal text on stderr; `FAIL: the final git ls-remote failed…` + `moved during verification (now unknown)` → 1 → **correct FAIL** |
| **A6 (vi)** `handoff.md` mode 100755 in a later commit (`update-index --chmod=+x`) | `follow-up: ecf2cf81 chmod +x handoff.md` / `PASS: … 2 follow-up(s)…` → 0 → **FALSE PASS** (oracle: mode 100755) | `FAIL: handoff.md is not a regular file (mode 100644, blob) in the remote tree` → 1 → **correct FAIL** |

**Answers to the brief's A questions**
- rev2 gives the false PASS in (i), (ii), (iii), (iv), (vi) and in the print-then-fail form of (v). In the silent-failure form of (v) it fails correctly, but only through an empty LIVE.
- rev3 does not, in any case I built.
- The REV3 modification resolves each reported REV2 defect in the scenarios tested:
  - (i): the added final `live` call (LIVE2).
  - (ii) and (v): the `out=$(…) || return 1` status check, plus the exactly-one-ref check.
  - (iii) and (vi): the `ls-tree` mode check.
  - (iv): the CANON check.
- This is "resolved in these reproductions", not a universal claim. Moves after the final observation, and cases I did not build, are not covered.

## 4. Findings register

**S1-I1 — incidental, for item E: git's own diagnostics print the (credential-anonymised) remote URL; the block prints it unchanged**
1. ID: S1-I1.
2. Location: rev3/verify_block_rev3.sh lines 17, 18 and 35, where `git fetch` and `git ls-remote` stderr is not redirected. The claim at line 16 ("the configured URL is not printed") is made by the block's message, but git itself prints a URL.
3. Conditions: the transport to origin fails (dead loopback port); git 2.43.0 with the curl transport; clean environment, no proxies.
4. Commands: scripts/incidental_E_probe.sh. In a clone, `git remote set-url origin 'https://x-access-token:DUMMYTOKEN-xyz@127.0.0.1:1/1h0lde4/ocbrain-v4.1.git'` (and the `http://` form). CANON was set to `https://127.0.0.1:1/1h0lde4/ocbrain-v4.1`, T and H to synthetic hashes, and the block ran as in section 3.
5. Output (evidence/incidental_E/rev3_https.combined and rev3_http.combined), printed three times per run on stderr: `fatal: unable to access 'https://127.0.0.1:1/1h0lde4/ocbrain-v4.1.git/': Failed to connect to 127.0.0.1 port 1 after 0 ms: Couldn't connect to server`. DUMMYTOKEN occurrences in stdout+stderr: 0 in both forms. In A5d, git printed the local origin path (`fatal: '<path>' does not appear to be a git repository`).
6. Expected vs actual: the brief's item E says no remote URL may appear in any diagnostic output, "including messages printed by git itself". Actual: host and path appear, with the userinfo stripped by git. The dummy token was not printed in these two forms.
7. Severity and impact: not assessed. The credential was not printed in the forms tried, but a URL was. For item E to evaluate.
8. Classification: OBSERVED (incidental).
9. Limits: two URL forms only, one git version, curl transport, loopback port. No ssh, no credential in the path or query, no real network error variants.
10. Substantive under the contract: yes by the literal definition ("any reproduced output of a credential or URL"). Item E to decide. It does not affect the A or G(1-3) statuses above.

**Substantive findings against criteria A and G(1-3): none.**

**Minor findings**
- M1: A1y. If the remote moves after rev3's last `ls-remote`, rev3 prints PASS (exit 0) while the final remote state violates the contract. This is the inherent race of item F. The contract says "at its final live observation", so it is not a false PASS, but item F should check that the prose states the guarantee accurately.
- M2: When the final `ls-remote` fails, rev3 also prints `FAIL: the remote branch moved during verification (now unknown)` (cases A2, A5, A5b, A5d). Nothing moved; the call failed. This is a misleading diagnostic, a false-FAIL-class wording issue only.
- M3: rev2 case (v) as written has only one `ls-remote` call. "Only the final call fails" is therefore the same call as in (ii). The silent form fails correctly by accident (empty LIVE); the print-then-fail form is a false PASS.
- M4: Informational, not a patch change. Unchanged line 582 of the patched file (§19, base L541) still says "its own hash cannot be recorded here; verification procedure in §18 step 2". §7 now records the handoff hash.
- M5: rev3 FAIL output in A4 prints CANON. That is the canonical (public) constant, not the configured URL, so I do not count it as an output of the configured URL.

## 5. Criterion G(1-3): exact commands and results

**G(1)**
- `python3 -I scripts/g1_extract_compare.py pkg/review_package/rev3/P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch pkg/review_package/rev3/verify_block_rev3.sh evidence/G/block_extracted_from_patch.sh`
  - Exactly two fence lines (patch lines 32 and 71). 38 body lines, all with the `+   ` prefix. 0 CR bytes in patch or block. 3 non-ASCII bytes, the em dash in the last line.
  - Extracted block: 3453 bytes, sha256 e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53. Packaged block: the same value. BYTE-IDENTICAL: True.
- Second method: `sed -n '/^+   ```bash$/,/^+   ```$/p' <patch> | sed '1d;$d' | sed 's/^+   //'`, then `cmp` against the packaged block: IDENTICAL (exit 0), the same sha256.
- Evidence: evidence/G/G1_extract_compare.txt.

**G(2)**
- Scratch repo work/G/repo: copy of base/handoff.md (sha256 9e33cf1a47e8cc050ce91b4e7a29164dd617363c8e3f6154d3b842795edc6d55) committed as db23cc72…; patch sha256 98468b11c2f88cfe6637f1a1f6ee88a089f60a3957a6cf6d1ea3d1522f7c2cb0.
- `git apply --check ../p.patch`: exit 0 ("Checking patch handoff.md..."). `git apply --check --whitespace=error`: exit 0.
- `git apply --numstat --summary`: 46 insertions, 5 deletions, 1 file. Real `git apply` in the scratch repo: exit 0, only `handoff.md` modified, `git diff --check` clean, 0 added lines with CR.
- Patched file: 588 lines, sha256 f2dd44dc116f0aa02f18a1f46687f1d0c792c177a1db3a9e09f512cf6f61f38c.
- `patch -p1 --dry-run` on a pristine copy: "checking file handoff.md", exit 0.
- Evidence: evidence/G/G2_*.txt.

**G(3)** (`python3 -I scripts/g3_hunk_map.py <base> <patched> evidence/G/G3_applied_diff_U0.txt`; evidence/G/G3_hunk_map.txt)
- Exactly three hunks:
  - Hunk 1: base L359, 1 line replaced. It lies in "## 7. Git / Repository Checkpoint" (L351) and is the "- Handoff commit:" line. This is intended change (a).
  - Hunk 2: base L507-509, 3 lines replaced, in "## 16" under the entry "Related documents and earlier revision" (L505). They are the sub-bullets "Limited supersession", "Parallel draft" and "Effect on this file's own checks". The unchanged siblings are "Earlier revision" (L506) and "Not decided by this entry" (L510). This is intended change (b).
  - Hunk 3: base L526, 1 line (step 2) replaced by 42 lines in "## 18. Resume Instructions" (L521). That is prose, a blank line and the fenced block at patched L528-567. This is intended change (c).
- The reconstruction check was True. Base lines outside the hunks plus the hunk text equal the patched file. 543 base lines untouched, 5 removed, 46 added.
- Status-word scan of the changed prose (excluding the block): no G4/G5-G8/OPEN/CLOSED/HELD/freeze words. "TRANSFER INCOMPLETE", "VERIFIED" and "accepted" appear in rewritten bullets and step 2, which are inside the intended lines.
- The word-level diffs (evidence/G/G3_word_diff_prose.txt) show the intended hunks add new factual statements. An example is "the branch tip when this entry was prepared on 2026-10-31; the branch may have moved since". Whether such prose is accurate was not assessed (G(4) is another stage).
- Unrelated changes: none found.

## 6. Unreviewed, unverified or inconclusive
- Items B, C, D, E, F, H, I (other stages). G(4) prose-claim comparison (NOT RUN, assigned to another stage).
- A cases cover local-path remotes with a `git` wrapper. Not covered: real HTTPS/SSH transports, a real GitHub origin, genuine network races (the move is injected by a hook at a fixed moment), shallow clones, grafts, replace refs, rename/copy-detection edge cases (item H), URL look-alikes (item B).
- Not run: a case where the remote moves between the first and final `ls-remote` with a valid-looking new tip (the A1 variants were contract-violating), and double-failure combinations.
- The oracle is my own simple check (chain, paths touched, mode). It is not a proof of every contract clause (for example it does not independently check "H is the commit that adds handoff.md").
- Case (iv) uses a local bare-clone fork. A real GitHub fork is not available offline.
- `patch(1)` version was not recorded.

## 7. Environment and tools
- Linux 6.18.44-fc-v378. git 2.43.0. GNU bash 5.2.21(1)-release. Python 3.13.16 (run with `-I` whenever it read package files). `patch(1)` used for the dry run. curl was not used directly (git's curl transport only, to dead loopback ports). No local servers were started.
- Package files were never executed directly; block copies were made under work/.

## 8. Declaration
I am a Claude model sub-agent (Sonnet 5.5, model ID claude-sonnet-5-5) in an independent context. I am the same model family as the author and am not a human. Tools used: Bash, Read and Edit/Write (no report file). Contact with the author's results: none. I read only the package, COMMON_PREAMBLE.md and the prompts. The session context also carried a project-instructions text and a user-memory listing, neither of which I used. I did not open any other stage directory, repository, report or earlier-review text.

## 9. Reproducibility
Directory: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S1/
- `bash scripts/run_cases.sh` (needs scripts/lib.sh and scripts/gitwrap.sh). It rebuilds work/ and evidence/A/ and prints evidence/A/summary.tsv.
- `bash scripts/incidental_E_probe.sh` (item E probe, evidence/incidental_E/).
- `python3 -I scripts/g1_extract_compare.py <patch> <rev3 block> <out file>`.
- G(2) was run interactively with exactly the commands in section 5: `cp base/handoff.md work/G/repo/`, `git init`, `git add`, `git commit`, `git apply --check ../p.patch`, `git apply --check --verbose`, `git apply --check --whitespace=error`, `git apply --numstat --summary`, `git apply`, `patch -p1 --dry-run`. The outputs are saved in evidence/G/G2_*.txt, not in a script.
- `git diff -U0 > evidence/G/G3_applied_diff_U0.txt`, then `python3 -I scripts/g3_hunk_map.py pkg/review_package/base/handoff.md work/G/repo/handoff.md evidence/G/G3_applied_diff_U0.txt`.
- Full evidence index: evidence/INDEX.txt.

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
