STAGE S4: COMPLETE (criteria C and D)

SUBSTANTIVE FINDINGS (per package contract definition): no. One non-contract observation (C-1) is flagged for owner judgement below.

Working directory: /tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S4/
No REPORT file was written (the harness refuses report files from subagents). This message is the complete report.

## 1. Package integrity, and a disclosed environment reset

- Verified in this session, before the reset:
  - The zip copy's full SHA-256 was 391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286, which matches the authoritative value in full.
  - `sha256sum -c SHA256SUMS.txt` reported all 7 files OK.
  - `rev3/verify_block_rev3.sh` was 38 lines with SHA-256 e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53.
- Disclosure: part-way through, the whole scratchpad was emptied. The package copy, `pkg/`, the preamble, `a8/` and my provisional report file were gone, and no copy of the package survives on the machine. The Python patch version also changed from 3.13.16 to 3.13.18, which suggests the sandbox was rebuilt.
- What I did about it:
  - I rebuilt `work/block_orig.sh` from the full block text that `cat -A` had printed earlier in this session.
  - Its SHA-256 is e1ccd6a7e5b1b70f7c9b9055e77e8b4c60648d88f6b7aea402e10e55d2604d53, identical in full to the recorded package value, and it has 38 lines.
  - I therefore treat the block under test as byte-identical to the package file. The package zip itself could not be re-verified after the reset.
- I did not re-extract the patch, `base/handoff.md`, rev2 or item I. They are not needed for C and D. The brief and preamble were used from what I read earlier in the session.
- In every row, `diff` against the block shows only lines 4, 6 and 7 (`CANON=`, `T=`, `H=`) changed. The check is saved per row in `evidence/{C,D}/blocks/<id>.changedlines`.

## 2. Criteria table

| Criterion | Status | Evidence and reasoning |
|---|---|---|
| C. `git ls-remote` handling | PASS, with caveats C-1 and C-2 | 63 rows in `evidence/C/SUMMARY.tsv`. Every row shows exactly 2 `git ls-remote` calls, and no other call is made. For every failed call and every output real git can produce (zero lines, two lines, other or differently cased names, tail-matching refs, wrong or different hash, exit non-zero after a correct ref, SIGPIPE, an unreachable remote), no PASS was printed. All required checks ran and held for the tested rows. I do not claim this holds for every possible input. C-1 and C-2 are not contract false PASSes (see section 4). If the owner reads the prose claim "return exactly one ref with the exact branch name" literally for arbitrary text, C-1 would change this status to FAIL. |
| D. `handoff.md` integrity | PASS (4 contract-ambiguous rows noted) | 42 rows built as real git repositories and run with real git (no wrapper), in `evidence/D/SUMMARY.tsv`. Symlink, directory, 100755, gitlink, similar names, different case, rename-away, deletion, merge in chain, extra paths, empty commit and wrong H lineage all gave FAIL. The controls and the contract-valid variants gave PASS. No false PASS and no unambiguous false FAIL. |

## 3. Table of all rows tested

Raw outputs per row: `evidence/C/<id>.{stdout,stderr,rc,wlog}` and `evidence/D/<id>.{stdout,stderr,rc,graph.txt,tiptree.txt}`. Classification is computed by `lib.sh classify`. A PASS must have exactly one PASS line and exit 0. A FAIL must have exit 1 and a last line of exactly `TRANSFER INCOMPLETE — REMOTE CHECKPOINT NOT VERIFIED`. No row printed an inconsistent result.

### Item C rows (63)

Rows built in `scripts/run_C.sh`. Synthetic chain: c0 → T (2362b75…) → H (2af89519…) → F1 (tip, 0af81c75…). Spare branch F2 is a954745a…. WRAP_MODEn selects the behaviour of the n-th `ls-remote` call. "1st" is the call in `live()` before the tip comparison, and "2nd" is the final call (LIVE2). Contract clauses: brief C, and contract item 4 (the live tip equals the verified tip at the final observation).

| Rows | How built | Printed (stdout / stderr), exit | Correct outcome and why | Class |
|---|---|---|---|---|
| W01 | Real git, both calls | `follow-up:` line, then `PASS at …`; stderr empty; 0 | PASS: contract met | correct PASS |
| W02, W05, W07, W09 (1st) and W03, W06, W08, W10 (2nd), W04 (both) | Wrapper: correct ref printed then exit 1; ref plus stderr "fatal" and exit 128; no stdout and exit 128; ref then SIGPIPE | `FAIL: git ls-remote failed or did not return exactly one matching ref` (1st) or `FAIL: the final git ls-remote failed …` and `FAIL: the remote branch moved during verification (now unknown)` (2nd); then `TRANSFER INCOMPLETE …`; stderr only the simulated fatal text; 1 | FAIL: brief C and contract 4, a failed call must never yield PASS | correct FAIL (9 rows) |
| W11 (1st), W12 (2nd) | Wrapper: zero lines, exit 0 | FAIL lines as above; 1 | FAIL | correct FAIL |
| W13, W14 | Wrapper: same ref line twice | FAIL; 1 | FAIL (not exactly one ref) | correct FAIL |
| W15–W18 | Wrapper: correct line plus `refs/heads/other` (other line first or second, 1st or 2nd call) | FAIL; 1 | FAIL by the block's stated rule (fail-closed) | correct FAIL |
| W19, W20 | Wrapper: only `refs/heads/other` with the right hash | FAIL; 1 | FAIL | correct FAIL |
| W21, W22 | Wrapper: `Docs/` capitalised ref name | FAIL; 1 | FAIL | correct FAIL |
| W23, W24 | Wrapper: `refs/heads/zz/refs/heads/<BR>` only (simulated tail match) | FAIL; 1 | FAIL | correct FAIL |
| W25, W26 | Wrapper: `refs/heads/zz/<BR>` only (the brief's example form) | FAIL; 1 | FAIL | correct FAIL |
| W27, W28 | Wrapper: name with an extra suffix `X` | FAIL; 1 | FAIL | correct FAIL |
| W29, W30 | Wrapper: right name, a different hash than the fetched tip (T) | `FAIL: live remote tip (<T>) differs from the fetched tip (<F1>)` (1st) or `FAIL: the remote branch moved during verification (now <T>)` (2nd); 1 | FAIL | correct FAIL |
| W32 | Wrapper: 12-character abbreviated hash | FAIL; 1 | FAIL | correct FAIL |
| W33 | Wrapper: empty hash field | FAIL; 1 | FAIL | correct FAIL |
| W39 | Wrapper: correct line plus a whitespace-only line | FAIL; 1 | FAIL (two non-empty lines) | correct FAIL |
| W42 | Wrapper: ref plus 200,000 other ref lines | FAIL; 1 | FAIL | correct FAIL |
| W44 | Wrapper: ref plus a `ref^{}` line | FAIL; 1 | FAIL | correct FAIL |
| W45 (1st), W46 (2nd) | Real `ls-remote` after the branch was deleted on origin (zero lines, exit 0) | FAIL; 1 | FAIL | correct FAIL |
| W47 (1st), W48 (2nd) | Real `ls-remote` while the origin path is unavailable (real exit 128) | FAIL; stderr git `fatal: '<origin path>' does not appear to be a git repository …` (283 bytes); 1 | FAIL | correct FAIL |
| W49 (1st), W50 (2nd) | Origin tip moved to F2 before the call | `FAIL: live remote tip (F2) differs from the fetched tip (F1)` (W49) or `FAIL: … moved during verification (now F2)` (W50); 1 | FAIL | correct FAIL |
| W31 | Wrapper: hash upper-cased | FAIL (string mismatch); 1 | Not producible by git; remote conformant | fail-closed FAIL (minor) |
| W37 | Wrapper: CRLF line ending (`$2` keeps the `\r`) | FAIL; 1 | Not producible by git; remote conformant | fail-closed FAIL (minor) |
| W34 | Wrapper: NUL byte between hash and tab | PASS; stderr bash warning "ignored null byte in input"; 0 | Not producible by git; remote conformant | tolerated PASS |
| W35, W36, W38, W40, W43 | Wrapper: leading/trailing blanks and tab padding; space instead of tab; empty lines around the ref; a third field after the name; ref plus 5 MB of empty lines | PASS; stderr empty; 0 | Not producible by git; remote conformant | tolerated PASS (5 rows) |
| W41 | Wrapper: correct line, exit 0, warning on stderr | PASS; stderr has the warning (35 bytes); 0 | PASS | correct PASS |
| W51 | Wrapper: 1st call prints `<hash><TAB>refs/*/*/*`, and a path `refs/heads/docs/g4-fts-errata-handoff-oct2026` exists in cwd | PASS; stderr empty; 0 | Contract met, because the 2nd call is real and the remote is conformant. The name check was nevertheless satisfied by glob expansion (see C-1) | PASS observed; see C-1 |
| W52 | Wrapper: 1st call prints ONE line holding two ref pairs | PASS; stderr empty; 0 | Same reasoning (see C-1) | PASS observed; see C-1 |
| R01 | Real origin with an extra branch `refs/heads/zz/refs/heads/<BR>`. Real `ls-remote` returns 2 lines | FAIL lines, plus `follow-up:` line; stderr empty; 1 | Contract holds (the real branch exists and its tip is right), so PASS is arguably correct. The block fails closed | false FAIL (minor, C-2) |
| R02 | Real origin: `<BR>` deleted after clone, only the tail-match branch exists | FAIL (fetch fails; stderr 78 bytes); 1 | FAIL | correct FAIL |
| R03, R04 | Real origin: lightweight or annotated tag `refs/tags/refs/heads/<BR>` | FAIL; stderr from fetch: `From <origin path>` and `* [new tag] …` (226 bytes); 1 | As R01 | false FAIL (minor, C-2) |
| R05 | Real origin: extra branch `Docs/g4-…` (case variant) | PASS; 0 | PASS | correct PASS |
| R06 | Real origin: `pack-refs --all` | PASS; 0 | PASS | correct PASS |
| R07 | Real origin: stale packed ref (F1) plus newer loose ref (F2); tip F2 | PASS; 0 | PASS | correct PASS |
| R08 | Real origin: extra branch `<BR>-2` | PASS; 0 | PASS | correct PASS |
| R09 | Real origin: extra branch `refs/heads/zz/<BR>` (the brief's literal tail example) | PASS; 0 (real `ls-remote` does not tail-match this name) | PASS | correct PASS |
| R10 | Real origin: `<BR>` deleted after clone, only `refs/heads/zz/<BR>` exists | FAIL; 1 | FAIL | correct FAIL |
| R12 | Real origin: `refs/heads/<BR>` is a symbolic ref to the spare branch (F2) | PASS; 0 | PASS | correct PASS |

Counts: 42 correct FAIL, 8 correct PASS (W01, W41, R05–R09, R12), 6 tolerated PASS (W34, W35, W36, W38, W40, W43), 2 fail-closed (W31, W37), 3 false FAIL (R01, R03, R04), 2 non-contract PASS rows (W51, W52).

### Item D rows (42)

Built in `scripts/run_D.sh`. T is the transfer commit and H the handoff commit, chosen per row. Contract clauses: brief D, and contract items 2 and 3.

| Rows | How built | Printed, exit | Correct outcome and why | Class |
|---|---|---|---|---|
| D01, D02, D03 | H only; H plus one follow-up; H plus two follow-ups (each edits handoff.md only) | `follow-up:` lines and `PASS`; 0 | PASS | correct PASS |
| D04, D05 | Symlink (120000) in a follow-up; H itself adds a symlink | `FAIL: handoff.md is not a regular file (mode 100644, blob) in the remote tree`; 1 | FAIL, contract 3 | correct FAIL |
| D06 | Follow-up replaces the file with a directory `handoff.md/inner.txt` | same FAIL; 1 | FAIL | correct FAIL |
| D07, D08 | Mode-only change to 100755 in a follow-up; H adds 100755 | same FAIL; 1 | FAIL | correct FAIL |
| D09, D10 | Gitlink (160000) in a follow-up; H adds a gitlink | same FAIL; 1 | FAIL | correct FAIL |
| D11 | Only `handoff.md.bak` | `FAIL: handoff.md is not a regular file…`, plus `FAIL: handoff.md was not added by the handoff commit`; 1 | FAIL | correct FAIL |
| D12a–f | Only `Handoff.md`, `HANDOFF.MD`, `handoff.MD`, `'handoff.md '` (trailing space), `handoff.mdx`, `' handoff.md'` (leading space) | same FAILs; 1 | FAIL | correct FAIL (6 rows) |
| D13 | Follow-up changes handoff.md and adds `Handoff.md` | `FAIL: <c> does not change handoff.md alone`; 1 | FAIL, contract 2 | correct FAIL |
| D14 | `Handoff.md` decoy already in T; H adds `handoff.md` (both in the tip tree) | PASS; 0 | PASS | correct PASS |
| D15 | A follow-up deletes handoff.md, a later one re-adds it | `FAIL: handoff.md was not added by the handoff commit`; 1 | Contract ambiguous: H adds, but a second add exists | ambiguous; observed FAIL (fail-closed) |
| D16 | Follow-up renames `handoff.md` → `handoff2.md` | FAIL (not a regular file); 1 | FAIL | correct FAIL |
| D17 | H adds `handoff.md` by renaming `old_handoff.md` from T | PASS; 0 | Ambiguous: rename-in is an add of the path | ambiguous; observed PASS |
| D18 | T already adds `handoff.md`; H only modifies it | `FAIL: handoff.md was not added by the handoff commit`; 1 | FAIL, contract 2 | correct FAIL |
| D19 | H does not touch handoff.md; a later commit adds it | same FAIL; 1 | FAIL | correct FAIL |
| D20 | Clean merge M in the chain (F1 and S1 both children of H, each editing handoff.md only; graph in `D20.graph.txt`) | `FAIL: <c> is not a single-parent child of <prev>` (two lines); 1 | FAIL | correct FAIL |
| D21 | Merge of a side branch rooted at T | FAIL (not a single-parent child); 1 | FAIL | correct FAIL |
| D22 | Follow-up changes handoff.md and docs/a.txt | `FAIL: <c> does not change handoff.md alone`; 1 | FAIL | correct FAIL |
| D23 | chmod +x in F1, chmod -x in F2 (tip 100644) | PASS; 0 | PASS: each commit changes handoff.md only; tip is regular | correct PASS |
| D24 | Empty follow-up commit | FAIL (does not change handoff.md alone); 1 | FAIL | correct FAIL |
| D25 | File → symlink in F1, symlink → file in F2 (tip regular) | PASS; 0 | PASS: contract 3 constrains only the tip | correct PASS |
| D26 | Only `sub/handoff.md` | FAIL (not a regular file at the root); 1 | FAIL | correct FAIL |
| D27 | H is a merge commit (parents T and X) that adds handoff.md | `FAIL: the parents of the handoff commit are not exactly the transfer commit`; 1 | FAIL | correct FAIL |
| D28 | Extra commit T2 between T and H | same FAIL; 1 | FAIL | correct FAIL |
| D29 | H adds handoff.md and also docs/c.txt | PASS; 0 | PASS: contract does not restrict H's other paths | correct PASS |
| D30 | `handoff.md` added in c0, deleted in T, re-added by H | `FAIL: handoff.md was not added by the handoff commit`; 1 | Ambiguous | ambiguous; observed FAIL |
| D31 | Gitlink in F1, regular file again in F2 | PASS; 0 | PASS: tip regular | correct PASS |
| D32 | H adds 100755, F1 chmod -x | PASS; 0 | PASS | correct PASS |
| D33 | Follow-up tree with RAW mode 100664 (written with `hash-object --literally`) | `FAIL: <c> does not change handoff.md alone`; 1 | Git canonicalises 100664 to 100644 when reading, so `ls-tree` and `diff-tree` see an empty change. It is equivalent to D24, not a mode test | correct FAIL (by apparent empty change) |
| D34 | Linear chain built via a side branch and reset (control) | PASS; 0 | PASS | correct PASS |
| D35 | Merge M with parents (F1, H) (redundant parent) | `FAIL: <c> is not a single-parent child of <prev>`; 1 | FAIL | correct FAIL |
| D36 | Follow-up deletes handoff.md | FAIL (not a regular file); 1 | FAIL | correct FAIL |
| D37 | H adds handoff.md with a RAW tree mode 100664 (confirmed present in the tree object) | PASS; 0 | Ambiguous: git reads it as 100644 | ambiguous; observed PASS |

Counts: 28 correct FAIL, 10 correct PASS (D01, D02, D03, D14, D23, D25, D29, D31, D32, D34), 4 ambiguous (D15 FAIL, D17 PASS, D30 FAIL, D37 PASS). stderr is empty in all D rows.

Harness corrections, so the record is straight: my first D14 (decoy in a separate commit between T and H) and first D20 (merge conflicted, graph was linear, PASS) were construction mistakes of mine. Both were rebuilt and re-run. D33 and D37 were first built with `mktree`, which normalises modes, then rebuilt with raw trees. Final evidence reflects the corrected rows only.

## 4. Findings register

**C-1: line-count and word-splitting check accepts output that does not contain "exactly one ref with the exact branch name"**
1. Id: C-1.
2. Location: `rev3/verify_block_rev3.sh` lines 11–12 (`grep -c .` counts non-empty lines; unquoted `set -- $out` with globbing on) and the prose claim in the patch step 2 ("each `git ls-remote` must succeed and return exactly one ref with the exact branch name").
3. Conditions: a simulated 1st `ls-remote` output that real git cannot emit.
4. Commands: `bash scripts/run_C.sh`, rows W51 (mode `glob`, with a matching path created in cwd) and W52 (mode `oneline_two`); also the tolerance rows W34, W35, W36, W38, W40, W43. Wrapper: `work/wrap/git`.
5. Output: `evidence/C/W51.stdout` and `evidence/C/W52.stdout` each end with `PASS at 2026-11-12T09:07:05Z: remote tip 0af81c75…; handoff commit 2af89519… on docs/g4-fts-errata-handoff-oct2026; 1 follow-up(s) …`; exit 0.
6. Expected vs actual: expected FAIL under the literal prose, actual PASS. The remote was conformant and the 2nd (final) call was real, so the contract outcome was correct.
7. Severity: Low.
8. Classification: OBSERVED with simulated input. The mechanism is DERIVED from the code.
9. Limitations: real git cannot emit these lines (ref names cannot contain spaces or `*`). W51 also needs an attacker-chosen path in cwd. A non-git remote could advertise such lines, but the origin identity check restricts that. I did not test any real non-git server.
10. Substantive under the contract? No. It is not a false PASS, because the contract's conditions held at the final genuine observation. I flag it because the prose is stronger than the code for arbitrary text.

**C-2 (minor, false FAIL): a real tail-matching ref or tag on the remote blocks PASS**
- Rows R01, R03 and R04. Real `ls-remote origin refs/heads/<BR>` returns two lines when the remote also has a ref ending in `/refs/heads/<BR>`, for example the branch `zz/refs/heads/<BR>` or the tag `refs/tags/refs/heads/<BR>`. The block FAILs (exit 1, three or four `FAIL:` lines).
- Contract-wise the checkpoint is intact, so this is a false FAIL.
- Anyone with push rights could cause it. It is fail-closed, not a safety problem.
- In R03 and R04, `git fetch` also auto-followed the tag and printed `* [new tag] …` on stderr.
- Evidence: `evidence/C/R01.*`, `R03.*`, `R04.*`.

**INC-1 (incidental, belongs to item E, which another stage covers): git's own stderr prints the origin URL**
- Rows I1, I2 and I3 (`scripts/run_incidental.sh`, evidence in `evidence/INC/`).
- I1 is a PASS run (exit 0) where the remote had moved since the clone. git's `fetch` printed `From <origin URL>` and `0af81c7..a954745 docs/… -> origin/docs/…` to stderr. The origin here was a local path. For the canonical GitHub URL this would be `From https://github.com/1h0lde4/ocbrain-v4.1` (DERIVED, not run).
- Rows W47 and W48 show the same for failures: `fatal: '<origin path>' does not appear to be a git repository`.
- That conflicts with the brief's item E wording ("no remote URL … in any output, including messages printed by git itself"). It is not secret for the canonical URL.
- I2 and I3 used `http://` and `https://user:DUMMYTOKEN-xyz@127.0.0.1:1/x.git` with proxies unset. git printed `unable to access 'http://127.0.0.1:1/x.git/'` and the credentials were stripped. `grep DUMMYTOKEN` over all evidence found nothing.
- I tested only those two forms.

No unreproduced suspicions.

## 5. Unreviewed and unverified

- Items A, B, E, F, G, H and I (other stages), beyond the incidental observations above.
- Real ssh/https transports for `ls-remote`. I used local-path and dead-loopback origins only.
- Protocol-v2 specifics, `uploadpack.hideRefs`, `GIT_NAMESPACE`, `transfer.fsckObjects`, ref names on real servers, and timeouts.
- A genuine race where the remote moves between the two calls (only wrapper or pre-move simulations: W49, W50).
- Case-insensitive filesystem clones. The block reads the object database, not the worktree.
- `diff.renames`, `core.quotepath` and other config effects. All runs used `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` set to `/dev/null`.
- Grafts, replace refs and shallow clones (item H).
- Submodule setups with `.gitmodules`.
- Very large or deep histories.
- Raw non-canonical tree modes beyond 100664.
- The patch and `base/handoff.md` (not used in this stage). The package zip was not re-verified after the reset.
- Combined stdout and stderr interleaving was not captured. They are separate files only, because several rows mutate the origin.

## 6. Environment and tool versions

- git 2.43.0
- GNU bash 5.2.21(1)-release
- Python 3.13.16 before the reset and 3.13.18 after it. Python was used only for `python3 -I` one-liners that edit scripts or tree bytes.
- Linux 6.18.44-fc-v378, x86_64
- No curl was used.
- `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`, `GIT_TERMINAL_PROMPT=0`, fixed author and committer, `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` set to 2026-01-01T00:00:00Z.
- Proxy variables were unset for every block run. Only local paths and the dead loopback port 127.0.0.1:1 were touched. No public network traffic.

## 7. Declaration

- Claude model sub-agent (Sonnet 5.5, model id claude-sonnet-5-5). Independent context. Same model family as the author, as stated in my prompt. Not a human.
- Tools: Bash, Read, Write, Edit and other file tools. No web or network use.
- Phase A: I read only the common preamble and the package. I did not read other scratchpad directories, other stage directories, `/home/claude`, any repository or any author report.
- Contact with the author's results: none. The coordinator's resume message gave no results.
- Date: 2026-11-12 (UTC).

## 8. Reproducibility

Directory: `/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad/a8/stage_S4/`

- `scripts/lib.sh`: environment, `run_block`, `classify` and `index` helpers. It substitutes only `CANON=`, `T=` and `H=` via `sed`, and records the changed-line count.
- `scripts/run_C.sh`: item C, 63 rows. Output goes to `evidence/C/` (including `SUMMARY.tsv`, `hashes.txt` and `blocks/`).
- `scripts/run_D.sh`: item D, 42 rows. Output goes to `evidence/D/`, plus `*.graph.txt` and `*.tiptree.txt` per row.
- `scripts/run_incidental.sh`: I1, I2 and I3, writing `evidence/INC/INC_SUMMARY.txt`. It needs the C hashes, so run C first.
- `work/wrap/git`: wrapper first in PATH, calling `/usr/bin/git` by absolute path, with the ls-remote modes listed above.
- `work/block_orig.sh`: the block under test, SHA-256 e1ccd6a7…04d53.
- `evidence/INDEX.txt`: one line per evidence file.

To reproduce: put the block file with that SHA-256 at `work/block_orig.sh`, then run `bash scripts/run_C.sh; bash scripts/run_D.sh; bash scripts/run_incidental.sh`.

G4 remains OPEN · High · freeze-blocking unless separately resolved through the required owner decisions and verification process. G5–G8 remain HELD. Freeze readiness is NOT DECLARED.
