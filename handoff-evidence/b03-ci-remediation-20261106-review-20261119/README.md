# Independent review of the B03 CI remediation delta, and the refreshed final report (2026-11-19)

Governing document: `/handoff.md` (repository root), **section 0b**. Read it first.

This directory is separate from `../b03-ci-remediation-20261106/` (local-lab evidence and hosted baseline) and from
`../b03-ci-remediation-20261106-hosted-run2/` (the hosted run 2 artifacts). Both of those were left **byte-identical**; this one adds
the review that handoff v5.1 could not obtain (U8) and the refreshed final report A to J.

## Layout

| File | Content |
|---|---|
| `independent_review_report_b0a1143_a1aaffc.md` | The fresh reviewer's report, verbatim. Model output, not an authority. Verdict: **APPROVE WITH CONDITIONS**, no BLOCKER; findings R1 to R8. |
| `FINAL_REPORT_A-J_20261119.md` | The refreshed final report in the assignment's A to J format. Decision: **NO-GO / INCOMPLETE**. |
| `spot_checks_20261119.sh.txt` | The script of the continuing session's own checks of findings R1 and R4 (stored as `.sh.txt` like the `.py.txt` files elsewhere). It works on a `git archive` copy and never touches the checkout. |
| `spot_check_R1_output.txt`, `spot_check_R4_output.txt` | Its raw outputs. |
| `SHA256SUMS` | SHA-256 of every other file in this directory. `sha256sum -c SHA256SUMS` must pass. |

## How the review came about (so the next session does not repeat it)

- The stored brief was reused with the repository path and tip adjusted (`review_brief.txt` was a scratchpad copy of the reviewer-facing
  text of `../b03-ci-remediation-20261106-hosted-run2/review/review_request_b0a1143_a1aaffc.md`; the committed brief is the original).
- Four attempts on 2026-11-18 and 2026-11-19 (00:36, 10:45, 18:15, 01:30 the next day) were cut off by HTTP 429 ("5-hour limit";
  stated resets 05:30, 15:40, 23:10, 06:30). The first ran about six minutes and delivered nothing; the second and third ended at
  once; the fourth ran 46 tool calls (about 7.5 minutes) and also delivered nothing. That fourth agent was then **resumed once**, with
  a message asking it to deliver its report, after the limit had reset (2026-11-19 12:33). That produced the report in this directory.
- The agents left scratch directories and files in the session scratchpad (`mutcopy`, `rcopy`, `skiplab2`, `review2`, `review4`,
  `venv_review`, `mut.py`, `mut2.py`, `snip.py`). They are not evidence and are not committed.
- The harness's safety classifier timed out while reviewing that agent's actions. The continuing session therefore checked, before
  using the report: the repository checkout at `b2fe9a3` is clean (`git status --porcelain` empty, reflog shows only the clone and the
  checkout); the remote tips are unchanged (`tmp/b03-ci-remediation-handoff-20261112` `b2fe9a3`, `integration/b03-ci-remediation-20261106`
  `a1aaffc`, PR #86 head `a887e148`).

## What the continuing session did with each finding

"REPRODUCED" = the continuing session re-ran the check itself. "NOT REPRODUCED" = the reviewer's claim, taken as a claim.

| ID | Sev (reviewer) | Status | Evidence |
|---|---|---|---|
| R1 | MEDIUM | **REPRODUCED** | `spot_check_R1_output.txt`: appending `--deselect tests/core/sandbox/test_docker_backend.py` to the pytest command: 31 config tests still pass (the mutant is not caught). Structural gap in the guard; it says nothing against run 2 itself, whose counts are consistent with the Docker tests having run (xfailed 1 to 9 = the 8 contract tests ran; the only Docker skip is A9). That is indirect: the `-q` output has no per-file lines. |
| R2 | MEDIUM | **CONFIRMED from the hosted output**, one number corrected | The A9 skip is in run 2's output (`test_docker_backend.py:895`, "requires gcc-multilib"). The reviewer wrote "12 namespace skips"; the hosted output has **14** (4 `test_allowed_hosts` + 1 `test_docker_backend` + 14 `test_namespace_backend` = 19, as in handoff v5.1). **Caution on the proposed fix:** installing `gcc-multilib` alone would make A9 run, and A9 hardcodes the image `ocbrain-test/base:local`, which CI does not provision (handoff U4), so it would fail with "no such object". The alternative (an explicit allow-list of accepted skips with reasons) or provisioning that tag are owner decisions (N2). |
| R3 | LOW | NOT REPRODUCED | Reviewer's scratch mutant. |
| R4 | LOW | **REPRODUCED** | `spot_check_R4_output.txt`: the real `run:` block exits 0 for an ANSI-coloured SKIPPED line, a reason on a continuation line, and a whitespace-only file (and 1 for the plain line and the empty file). Hosted output is plain (no TTY), so this is a robustness gap, not an observed failure. |
| R5 | LOW | NOT REPRODUCED | Reviewer's scratch mutants. |
| R6 | LOW | = handoff N6 (already open) | Floating tag `python:3.12-slim`; digest recorded after the fact. |
| R7 | NIT | = handoff U17 (already open) | Stale "busybox" wording at the three places listed. |
| R8 | NIT, pre-existing | **CONFIRMED by reading** | `git show a887e148:.github/workflows/ci.yml` has `branch = '$BRANCH'` at line 50 already: not introduced by this work. Not exploited here. |

Reviewer answers that matter for the decision: the N1 test parses YAML and pins exactly four `if: always()` uploads (answer 4); the skip step's two matched reasons are the real ones in the test files (answer 2); no masking of failures in the step order (answer 3); the protected files have no diff vs `a887e148` (answer 7; the continuing session re-ran `git diff --quiet` on 2026-11-19: rc=0, and D10 sha256 `51caa5d6...f158316`).

## Dispositions (PROPOSED; none is decided, none is implemented)

No code, workflow or test file was changed by this session. Fixing R1, R2, R4, R5 (and N6, U17, F8) is a CI/docs hardening round: it is
outside D-1's authorization, and a push to `integration/**` starts a new hosted run, so it needs the owner's explicit go. Until then
the review's condition ("fix or explicitly accept R1 and R2") stays **open**.

## Limits of this review (from the reviewer's own list, plus the continuing session's)

Not verified by anyone: the `pull_request` trigger for `b01-base` (run 2 was a push); a real Docker preflight or Docker-backed run
outside the hosted one; the mapping of the three pinned action SHAs to tags; the AF_ALG-present branch of the seccomp test locally;
the A2 test as a non-root runner with sudo; Python 3.12 specifically; the full suite; mutation of the preflight script's own logic. The
review is **static plus scratch mutation** by a model agent; it is independent of the author's session, not of the model family.
