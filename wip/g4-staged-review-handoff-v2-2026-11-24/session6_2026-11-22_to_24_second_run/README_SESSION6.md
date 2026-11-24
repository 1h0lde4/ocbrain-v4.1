# Session 6 addendum — a second, independent run of S6, S7 and S3, and a partial S8 (2026-11-22 to 2026-11-24)

**Read this first.** Sessions 2 to 5 (directories `session2_2026-11-14` … `session5_2026-11-16` on the branch `wip/g4-staged-review-handoff-2026-11-13`, tip `4125320eb21cdad98dd2a6f189da5d6be30a955f`) had already completed S6, S7, S3 and S8 by 2026-11-17. The conversation that produced this directory did not know that. It continued from its own context summary, re-ran S6, S7 and S3 from scratch and started S8, and found the other branch on 2026-11-24 ~10:15 UTC while checking remotes before pushing. To the author's knowledge the reviewers of these runs did not see sessions 2 to 5 (their prompts and file lists exclude them), so the runs are independent of them in that sense (same model family, same package, same preamble idea). Nothing on the other branch is changed by this push. **This directory is a duplicate run and a cross-check, not the primary record.** The primary record of S6, S7, S3, S8 is sessions 2 to 5.

The review is **not finished**: the stage reports have not been consolidated, no Addendum 7 exists, and the mechanical verdict has not been written. See `../handoff.md`.

## Files
| File | What it is |
|---|---|
| `reports/REPORT_S6.md` | S6 reviewer's final report (run 3 of the stage), saved byte-for-byte from the session record. 23,331 bytes, sha256 `708241486be8037534dc50bed01380a95c0bd2f25da8f6d970295de8d41de1ca`. |
| `reports/REPORT_S7.md` | S7 report (run 2), same method. 9,259 bytes, sha256 `2c5f76ec284123af580b76a9ff90557e4b6b01ef85ab4b187f62923a9606258d`. |
| `reports/REPORT_S3.md` | S3 report, same method. 11,986 bytes, sha256 `eb05e157645aeb0e53cee6c6d773213449008e620a89b8adea2618ba779518e1`. |
| `reports/AUTHOR_SPOTCHECK_S6_2026-11-23.txt`, `reports/AUTHOR_SPOTCHECK_S3_2026-11-24.txt` | What the author read in the reviewers' saved evidence. These are readings of files, not re-runs. |
| `reports/INPUT_REV2_ZIP_NOT_REVIEWED_2026-11-23.txt` | Record of an owner attachment (a delta from the separate `g4-fix` remediation work). Unreviewed input; nothing applied. |
| `reports/S3_SUMMARY.tsv`, `S6_summary.tsv`, `S7_SUMMARY_TABLE.tsv` | Row tables of the three stages (copies of the files inside the zips). |
| `reports/S8_PARTIAL_COMPARISON.tsv`, `S8_PARTIAL_comparison_rows.txt` | The unfinished S8 reviewer's comparison table (about 40 rows). **Not a result**: the reviewer was cut off by the usage limit before returning a report. |
| `stage_S3_…zip`, `stage_S6_…zip`, `stage_S7_…zip`, `stage_S8_PARTIAL_…zip` | Scripts, row tables and raw per-row evidence of each stage. Excluded on purpose: package copies, the synthetic repositories' `.git` directories, and the throw-away TLS key and certificate (reproducible with `stage_S3/setup.sh`). Credential scan of every file and every zip member: 0 hits (exact values of the 10 credential-named environment variables and token patterns; two non-secret git URL-rewrite settings were excluded from the value check). Dummy values such as `DUMMYTOKEN-xyz` are intentional test data. |
| `prompts_used/` | The prompts as sent to the sub-agent reviewers (S6 runs 1 to 3, S7 runs 1 and 2, S3, S8). The S3 prompt file is dated 2026-11-23 in its name; it was launched on 2026-11-24. |
| `COMMON_PREAMBLE_second_run.md`, `package/` | The preamble used (only the package path differs from the first one) and a copy of the review package (sha256 `391eb0a06784153af4591d6bbfdc0af87edce0f17dd2e2aae0a7593794ce2286`). |

## How the stages ran
The reviewers are independent-context sub-agents of the same model family as the author (Sonnet 5.5), not humans. Their reports are [REPORTED]. The free-plan usage limit cut several runs off: S6 launches 1 and 2 and S7 launch 1 (S6 launch 2 had finished its work on disk but lost its report), S3 launch 1 (nothing done), S8 (after about 4 minutes, with a comparison table and four experiments on disk, before any report). Each cut-off stage was re-launched with a resumption note; the final reports are the last runs' hand-backs.

## Results of this second run ([REPORTED] unless marked)
| Criterion / test | Status | Main basis |
|---|---|---|
| F (the unavoidable race) | PASS | race is real; prose states it accurately |
| G part 4 (prose claims) | FAIL | claims about "documentation-only", "no longer depends on the path-filtered log" and credential/identity handling are unmet or overstated (C18, G13/G14, G04, H10/H11/H14 in the S6 numbering) |
| H (shell and git pitfalls) | FAIL | false PASS through graft files and replace refs (H23, H24, H25), through an ignored exit status inside `$( )` (H29, simulated), cwd-relative pathspecs (H34 false PASS, H33 false FAIL) |
| I (status checker) | FAIL | status-line test is an unanchored substring test (checker line 26); last-line test breaks on U+2028, U+0085, form feed, lone CR; no scan for duplicate or conflicting status lines; gate-table test checks only the status-word set |
| S3 F14 (false PASS) | FAIL | printed `PASS`, exit 0, while git talked to `evil.test` or `127.0.0.1` for `?@` origins; `#@` only against a server that answers `/`; a URL credential was sent to the other host after a 401 |
| S3 F15 (secret output) | FAIL | git's own stderr printed the dummy token for user-name-only against 401 (`could not read Password`), and in query-string and fragment origins (`repository '…' not found`) |

The A–I matrix these runs support, merged with the Phase A reports of S1, S2, S4, S5 (`recovered/stage_reports/`): A PASS · B FAIL · C PASS (caveats) · D PASS (four ambiguous rows) · E FAIL · F PASS · G FAIL · H FAIL · I FAIL. This **equals** the interim matrix recorded in `session5_2026-11-16/README_SESSION5.md`. The overall verdict cannot be PASS. It is an interim matrix, not the final one.

## Differences from sessions 2 to 5 that someone must reconcile (not yet done)
1. **Coverage.** The first line's S3 ran 14 false-PASS forms and 48 evidence rows; this run ran 8 F14 cases and 8 F15 cases. Its S6 and S7 reports are shorter than sessions 2 and 3.
2. **F15 on an accepting server.** This run's S3 cases with a 200 server printed no token. Session 4's S3 and the author's re-run there saw `From https://github.com/…?token=DUMMYTOKEN-xyz` on `git fetch` against an accepting server. The likely cause is that this run's clones were fresh, so the fetch updated no ref and printed no `From` line. That is an untested explanation. **Do not read this run's "no leak on 200" rows as showing prevention**; session 4's result stands.
3. **S3 label.** The case id `F15-c-200` in this run is a misnomer (that server answered 404; the 200 variant is `F15-c-lenient`).
4. **S6/S7 finding ids** differ from sessions 2 and 3 (`S6-H-01…03`, `S6-G4-01…05`, `S7 I-1…I-3`). A mapping has not been made. Do not merge by guess.
5. **Spot-checks.** The author read evidence for S6 and S3 (files above). A spot-check of S7 was done in the conversation, and no file of it was kept; treat S7 of this run as [REPORTED] only.

## Not done
S8 (this run's version) has no report. Sessions 2 to 5 have its report, so S8 is not a gap. Consolidation, the finding register with F-numbers, Addendum 7, the mechanical verdict and the delivery bundle are open. No code, rev2, rev3, checker or patch was changed; no `main`, PR #90 or save-branch update.

G4 OPEN · High · freeze-blocking. G5–G8 HELD. Freeze readiness NOT DECLARED.
