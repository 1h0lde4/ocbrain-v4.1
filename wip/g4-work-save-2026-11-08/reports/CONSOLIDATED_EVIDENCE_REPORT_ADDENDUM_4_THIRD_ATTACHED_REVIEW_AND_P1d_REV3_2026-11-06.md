# Addendum 4 to the Consolidated Evidence Report — third attached review (`af046c14`) and P1d revision 3 — 2026-11-06

Addendum to `CONSOLIDATED_EVIDENCE_REPORT_P1_P2_P3_EXECUTION_2026-11-01.md` (sha256 `561f22648a36df52cf1cdc546f00cc37ed758f0098a12f93ede0ad77d3fb9050`), Addendum 1 (`eba20d6661df735a75c273eb458519055f38b07f48b97b234287e6eece53d382`), Addendum 2 (`4003be115020ec7c2e8269c954f82babf90696ed52fbe5875cf6dd141579d938`) and Addendum 3 (`50d9aa28b2ab748870d2c45a6836e1437b0ab2cea095386566861e01d50bd668`). None is edited. Evidence: `I51`–`I64` in `g4_attachment_af046c14_p1d_rev3_block_tests_evidence_I51-I64.zip` (sha256 `7f3bc8f6fbc380448e827b550049db89559e83ad8a92ac3b4be6a1043b87ac36`, delivered beside this addendum). `I65`, `I66` and `I67`, the author's mechanical checks of this addendum, are delivered as separate files because they check the text that cites the bundle's hash: `I65` is the first run and failed on one point (the checker looked for "NOT VERIFIED" in capitals, the text says "not VERIFIED"; I changed the checker, not the text); `I66` is the passing rerun; `I67` is the passing rerun on the final text, after this sentence was added. None replaces another. The work ran on 2026-11-03 (`I51`–`I55`), 2026-11-04 (`I56`, first reviewer attempt), 2026-11-05 (`I57`–`I61`) and 2026-11-06 (`I62`–`I64`).

**Governing statuses, unchanged:** G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED. No implementation authorized. This addendum changes no repository, no pull request and no decision item.

Labels: **[OBSERVED]** produced in this run (evidence ID); **[REPORTED]** what an attached text says; **[DERIVED]** a conclusion from observations.

## 1. Result in brief

1. **The attached review is right about all three weaknesses of P1d revision 2, and I reproduced each one myself** [OBSERVED, I60, I61]. In throw-away synthetic repositories, the revision 2 block printed PASS when the remote branch moved right after its only `ls-remote` call (F9, scenario s12), when `git ls-remote` printed the correct ref and then exited with status 7 (F10, s13), and when `handoff.md` had become a symbolic link (F11, s14). It also printed PASS when `origin` was a fork with identical history (s16), when the only `ls-remote` call that matters was the last one and it failed (s17, my addition: revision 2 makes just one call) and when `handoff.md` was executable (s19, my addition). That is six false PASSes in 20 scenarios.
2. **I built revision 3 and did not apply it** [OBSERVED, I62]. The block (38 lines, sha256 `e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53`) gives the required result in 20 of 20 scenarios, with no false PASS and no false FAIL [OBSERVED, I60]. The patch (sha256 `98468b11c2f88cfe6637f1a1f6ee88a089f60a3957a6cf6d1ea3d1522f7c2cb0`) applies to the pushed tree, and the block inside it is byte-identical to the tested file, both in the patch and in the proposed `handoff.md`.
3. **The unmodified block text, extracted from the proposed `handoff.md`, prints PASS on the real remote branch** in my working clone and in a fresh clone of the canonical URL, and four deliberately wrong copies print FAIL with no PASS line [OBSERVED, I63].
4. **I replaced my own first candidate before delivering it** (section 5). Candidate A could print the configured `origin` URL, and so a credential, in a FAIL line. I found it by checking the prose claim "never printed" against the block's behaviour [OBSERVED, I53, I59]. The final block never prints the URL. Candidate A and its evidence (`I51`–`I56`) are kept.
5. **An independent-context review of revision 3 was not completed.** Two attempts were terminated by API rate-limit errors before the reviewer returned a report [OBSERVED, I57]. Revision 3 is therefore **SELF-REVIEW ONLY**. F7 stays OPEN.
6. **Nothing was pushed, applied or committed** [OBSERVED, I64]: `HEAD` and the remote REV2 tip are still `d963daa502de4220411d0d0c2f19f67b3ec2682b`; the clone is clean; PR #90 is unchanged.
7. **Statuses unchanged:** G4 OPEN · High · freeze-blocking; G5–G8 HELD; freeze readiness NOT DECLARED; D-1…D-11 OPEN; no implementation authorized.

## 2. What was received

A text file, `af046c14-attachment.txt` (9,007 bytes, sha256 `42396b9f8ddc9009ffa2cceec458b490317df0cf0ddffccad188199189792cc3`), sent without instructions. It is another assistant's "Independent assessment of Addendum 3": three further weaknesses of P1d revision 2 (F9, F10, F11), five requested new scenarios (s12–s16), a requirement to check that `origin` is the canonical repository, a revised authorization table, and a recommended sequence. Its recommendations are that assistant's, not yours. It is input to verification, not evidence.

## 3. Claims checked

| Claim in the attachment | Result | Evidence |
|---|---|---|
| F9: the revision 2 block prints PASS if the remote moves after the live-tip query | **Verified**: s12 gives PASS under revision 2 with one `ls-remote` call and the remote tip advanced to a commit that changes `KNOWN_ISSUES.md` | I60, I61 |
| F10: `git ls-remote … \| cut -f1` hides a transport failure | **Verified**: s13 gives PASS under revision 2 while `ls-remote` exits 7 | I60, I61 |
| F11: `git cat-file -e` accepts a symbolic link at `handoff.md` | **Verified**: s14 gives PASS under revision 2; the remote tree entry is mode 120000 | I60, I61 |
| s15, `handoff.md` replaced by a directory, must fail | **Met by revision 2 only incidentally** (its path-list checks fail, not a type check); revision 3 fails it on the mode check, the intended reason | I60, I61 |
| s16, a fork or other unintended remote, must be rejected | **Verified as a gap**: revision 2 has no identity check and gives PASS; revision 3 fails | I60 |
| The block should establish that `origin` is the canonical repository | **Adopted** in revision 3, with its limits stated in section 8 | I60, I59 |
| The block, not the prose, should be what is tested, with byte identity between patch and tested block | **Done** for revision 3 with `cmp` against both the patch and the proposed file | I62 |
| The 11 original scenarios still hold | **Verified** for revision 3 (s01–s11 as required) | I60 |
| Revision 2's embedded block is byte-identical to the tested one (sha256 `014fad4792ab082448fc48f3328c49ceb67bf551261ac828cb4a81527336519f`) | **Consistent with my own record** from Addendum 3; that hash is the revision 2 block in this bundle's hash list | I64 |
| Archive integrity: an outer archive and an inner archive, with 7 and 15 manifest entries | **Not checked**: I was not sent that archive | — |
| Its authorization table (P1d of Addendum 2 rejected, P1c not authorized, revision 2 held, application not authorized) | A recommendation. It agrees with my own findings F8 and F7; it is not an authorization from you | — |

## 4. P1d revision 3 (replaces revision 2, P1d and P1c; not applied)

`P1d_rev3_handoff_section7_18_verification_block_PROPOSED.patch` (sha256 `98468b11c2f88cfe6637f1a1f6ee88a089f60a3957a6cf6d1ea3d1522f7c2cb0`): 46 insertions and 5 deletions, all in `handoff.md`; `git apply --check` exit 0 on the pushed tree; the proposed file has 19 level-2 headings and no CR [OBSERVED, I62]. It differs from revision 2 only in the block and in the prose of step 2 of the file's section 18; the section 7 line and the F3, F4, F5 wording are as in revision 2.

**What the block adds to revision 2** (each item has a scenario in the table below):

1. `set -o pipefail`, and a `live()` function that requires `git ls-remote` to succeed and to return exactly one line whose ref name is exactly the branch (F10; s13, s18, s20).
2. A final `ls-remote` after every ancestry and per-commit check; it must equal the verified tip, so the PASS line is dated and means "the remote tip was the verified tip at that observation" (F9; s07, s12, s17).
3. `git ls-tree` on the remote tip: `handoff.md` must be mode 100644, type blob (F11; s09, s14, s15, s19).
4. `origin` must be the canonical repository, `https://github.com/1h0lde4/ocbrain-v4.1`; the SSH forms and a trailing `.git` are accepted; credentials in an `https` URL are dropped before the comparison; the FAIL line does not print the URL (s16, identity tests).

**Tests** [OBSERVED, I60, I61; synthetic repositories; git 2.43.0, GNU bash 5.2.21, I64]. Each scenario was built fresh for each block; the harness substituted only the `T=`, `H=` and `CANON=` lines.

| Scenario | Required | Revision 2 | Revision 3 |
|---|---|---|---|
| s01 baseline, no follow-up commit | PASS | PASS | PASS |
| s02 one later handoff-only commit | PASS | PASS | PASS |
| s03 three later handoff-only commits | PASS | PASS | PASS |
| s04 a later commit changes another file | FAIL | FAIL | FAIL |
| s05 another file changed and then reverted | FAIL | FAIL | FAIL |
| s06 handoff commit local, not an ancestor | FAIL | FAIL | FAIL |
| s07 remote moves between fetch and live check | FAIL | FAIL | FAIL |
| s08 merge commit in the sequence | FAIL | FAIL | FAIL |
| s09 `handoff.md` missing from the tree | FAIL | FAIL | FAIL |
| s10 wrong parent for the handoff commit | FAIL | FAIL | FAIL |
| s11 remote branch missing | FAIL | FAIL | FAIL |
| s12 remote moves right after the first `ls-remote` (F9) | FAIL | PASS (false) | FAIL |
| s13 `ls-remote` prints the correct ref, exits 7 (F10) | FAIL | PASS (false) | FAIL |
| s14 `handoff.md` is a symbolic link (F11) | FAIL | PASS (false) | FAIL |
| s15 `handoff.md` is a directory | FAIL | FAIL (incidental) | FAIL |
| s16 `origin` is a fork with identical history | FAIL | PASS (false) | FAIL |
| s17 only the final `ls-remote` fails | FAIL | PASS (false) | FAIL |
| s18 a stray second ref ends with the branch ref | FAIL | FAIL | FAIL |
| s19 `handoff.md` has mode 100755 | FAIL | PASS (false) | FAIL |
| s20 real branch missing, only a tail-matching ref exists | FAIL | FAIL | FAIL |

Totals: 20 scenarios; revision 2: 6 mismatches (all false PASS); revision 3: 0 mismatches. `I61` confirms from the left-over scenario directories that each shim and marker really engaged (for example, in s12 revision 2 made one `ls-remote` call and revision 3 made two; the tree entries were 120000, 040000 and 100755 in s14, s15 and s19).

**Identity and leak tests** [OBSERVED, I59]: 20 URL forms extracted from the block text itself (canonical forms with and without credentials; other owners; a `-fork` name; `https://evil.example/@github.com/…`; `https://github.com@evil.example/…`; ssh and http forms with credentials; a query string with a token; a mirror path). The final block: 0 of 20 differ from the expected identity result and the dummy token appears in 0 of 20 outputs. Candidate A: 5 of 20 differ and the token appears in 5 outputs. End to end, the whole block against dead loopback ports with proxies disabled (no traffic left the machine): the dummy token appeared in 0 of 3 outputs for the final block and in 2 of 3 for candidate A.

**Real execution** [OBSERVED, I63]: the block text extracted from the proposed `handoff.md` (same sha256 as the tested file) prints `PASS at 2026-11-06T12:47:27Z …` in the working clone and `PASS at 2026-11-06T12:47:29Z …` in a fresh no-checkout clone of `https://github.com/1h0lde4/ocbrain-v4.1`, listing the one follow-up `d963daa5…`. Four modified copies, run in the fresh clone, each print FAIL and no PASS line: handoff commit set to the REV2 tip, transfer commit set to the REV3 tip, a branch name that does not exist, and a canonical URL set to a fork name. This tests the checkpoint and the block against the live branch before any revision 3 text is pushed; it does not show that the text is on the branch.

## 5. Changes and mistakes of mine in this step

- **F12, candidate A (superseded before delivery).** Draft 1 of the block (sha256 `80f6c77b80ca88a33f3a56e29af928f46998450434a87c56df6e0bfbb22a2055`) printed the `origin` URL in its FAIL line and rejected the canonical repository when it was reached with a credential in the URL; `I53` shows 4 of 15 cases with the dummy token in the output. I saw this before running any harness (a probe showed that `git remote get-url` returns a credentialed URL as configured), kept draft 1, and added a line that drops credentials from an `https` URL before the comparison; that is candidate A (sha256 `4423b51291334af718e72f3fd41489473895e491b7eb016015e4a9608ac28b83`; harness, patch and real-remote evidence in `I51`–`I55`). `I53` tests both drafts. Later, while checking the prose against the block, I found that the prose claim "never printed" was still overstated: other URL forms with credentials were still printed. `I59` shows the leak in 5 of 20 unit cases and 2 of 3 end-to-end runs. I changed one line (`I58`: the FAIL line now names the canonical URL and says the configured URL is not printed) and reran everything on the final block (`I59`–`I63`). Candidate A, its patch and its evidence are kept and marked superseded; the candidate A patch must not be applied.
- **Reviewer attempts, not completed (`I57`).** I sent revision 3 to a fresh-context reviewer twice, with the block, the contract and no test results. Both runs were terminated by an API rate-limit error. The first left 72 scratch entries and the second 41, with no report and no saved PASS output. I did not treat any leftover as a finding or as evidence.
- **PR check (`I55`, `I63`):** the PR #90 line of my script used `gh pr view`, which needs GraphQL and is blocked in this environment (HTTP 403). It is an environmental limit of my check, not a product failure. `I56` and `I64` read the same fields over REST: state open, draft, head `9407db5a01acea9684f158caa8107fb71611a102`, 3 commits, 7 files.
- Nothing in the repository, on any remote or in any pull request was changed.

## 6. Gates and open findings

Exactly one status per gate, for this addendum's scope (checking the attachment, building and testing the revision 3 proposal without applying it).

| Gate | Status | Evidence | Reason |
|---|---|---|---|
| Attached review treated as unverified input; its verifiable claims checked | **PASS** | I60, I61, I59 | section 3 |
| F9, F10, F11 reproduced against revision 2 | **PASS** | I60, I61 | s12, s13, s14 give PASS where FAIL is required |
| Revision 3 block tested on positive and negative scenarios | **PASS** | I60, I59 | 20 of 20 as required; 20 identity cases; 3 end-to-end leak runs |
| Revision 3 patch built, applies, block byte-identical to the tested block | **PASS** | I62 | apply-check exit 0; `cmp` exit 0 against the patch and the proposed file |
| Unmodified block run on the real remote and negative controls | **PASS** | I63 | working clone and fresh canonical clone; four controls FAIL |
| No ref, commit, working file, pull request or remote changed | **PASS** | I64 | `HEAD` and remote tip `d963daa5…`, status 0, PR #90 unchanged |
| G4/freeze invariants | **PASS** | section 1 | statuses stated unchanged |
| **Overall result (this addendum's scope)** | **PASS** | | **SELF-REVIEW ONLY** for the revision 3 text; qualified by the open findings below and the limits in section 8 |

Not part of this scope and **not done:** an independent-context review of the exact revision 3 text. It is a precondition for applying revision 3 (section 7).

| Finding | Status | Note |
|---|---|---|
| F1–F5 (Addendum 1) | **OPEN** | pushed wording residuals; revision 3 carries the fixes |
| F7 (Addendum 2) | **OPEN** | the pushed step 2 and section 7 fail when followed literally; fix proposed (revision 3), not applied. Closure criterion: independent-context review of the exact text, authorized push, then the block run successfully from a fresh clone of the canonical URL after the push |
| F8 (Addendum 3) | **OPEN** | the P1d of Addendum 2 must not be applied |
| **F9, F10, F11** (new, from the attachment) | **FIXED in the proposal (revision 3); not VERIFIED** | defects of the unapplied revision 2; reproduced in `I60`, fixed and tested in revision 3; independent review not done |
| **F12** (new, mine) | **FIXED in the proposal (revision 3 final); not VERIFIED** | candidate A could print a credential; found by me, fixed before delivery (`I59`) |
| F6 (Addendum 1) | not changed | metadata only |

## 7. Decisions for you

1. **P1d revision 3:** approve it, or not. If you approve, I first retry an independent-context review of the exact text (it did not complete, section 5) and fix what it finds; then I apply revision 3 as one new commit with the attribution trailers, push as a non-force fast-forward, run the block from a fresh clone of the canonical URL, and record it. Apply revision 3 or nothing: revision 2, the P1d of Addendum 2, P1c and the candidate A patch must not be applied.
2. **A stopping rule, my suggestion.** This is the third rewrite of the step 2 check (P1d, revision 2, revision 3) after the explanatory sentence P1b, and the block is about 40 lines. Each review found cases the previous tests did not cover, which is what adversarial checks do, but the returns are diminishing. I suggest: revision 3, one independent review, and the limits in section 8 accepted as stated. The cheaper alternative is to leave the pushed text as it is with F7 OPEN; the cost is that step 2 of the file's section 18 fails when followed literally. Which one is yours to choose.
3. **D-1…D-11, the next-session entry point and the ledger wording** stay with you; no recommendation in any attachment is adopted by this addendum.
4. **PR #90 rebase:** the PR owner's call; none is authorized or done.

Nothing was pushed in this step; rollback of earlier pushes is unchanged (section 7 of Addendum 1).

## 8. Limits

- Revision 3 is self-review only; the earlier reviewer was the same model family in any case, and the tests are synthetic.
- PASS means only that the remote tip was the verified tip at the final observation; the remote cannot be locked afterwards. The block checks paths, modes and graph shape, not what a later commit writes inside `handoff.md`. A legitimate later change that also touches another file fails by design and needs a new handoff revision.
- The identity check guards against an accidental wrong remote. It reads the local git configuration, so it is not a defence against a hostile local environment. It fails closed (a false FAIL, never a false PASS) for a mirror or proxy URL, a trailing slash, a different letter case, or an explicit port; a Claude session whose `origin` is such a URL must verify from a clone of the canonical URL. A stray extra ref that ends with the branch ref also makes it fail (s18).
- The leak tests cover the block's own output and the messages of this git version in three dead-port cases, with a dummy token; they do not cover every git version or transport.
- The block needs network access and an `origin` remote, and the hashes are written into it.
- Not examined: CI and branch-protection behaviour; the chain of custody of the REV3 ZIP and the user-side `handoff(1).md`; the attachment's archive claims.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
