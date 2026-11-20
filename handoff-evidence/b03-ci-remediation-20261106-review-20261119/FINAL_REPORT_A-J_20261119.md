# Final report A to J: PR #86 (B03) CI and security verification remediation

Refreshed 2026-11-19. It supersedes the report delivered on 2026-11-15, which predates the hosted run 2 evidence and is **not** in the
repository (handoff U18(b)). Vocabulary: PASS / FAIL / INCOMPLETE / DEFERRED. Evidence paths are relative to `handoff-evidence/`.
"Re-run today" means re-run by the session that wrote this report on 2026-11-19; everything else is taken from the handoff, the hosted
artifacts, or the independent review, and says so.

## A. Final decision

**NO-GO. INCOMPLETE.** Do not merge PR #86 on this evidence. This workstream merged, closed, retargeted, re-ran or cancelled nothing;
PR #86 was not touched (re-read 2026-11-19 12:35Z: open, head `a887e148`, base `e2266603`, `updated_at` 2026-11-02, `mergeable_state` "unstable").

The user's merge gate of 2026-11-14 against the evidence:

| Condition | Status |
|---|---|
| "the exact reviewed PR head has all required checks passing" | **FAIL.** PR #86's head `a887e148` has never run the remediated workflow; the fix exists only on `integration/b03-ci-remediation-20261106` (head `a1aaffc`). PR #86's own `tests` check is still the old failure (run `42223596080`). |
| Docker preflight succeeds | PASS on `a1aaffc` (run 2), not on PR #86's head |
| pytest, gate and skip checks execute and pass | PASS on `a1aaffc` (run 2), not on PR #86's head |
| evidence artifacts retrievable | PASS for run 2 (four artifacts, SHA-256 equal to GitHub's digests); not collected for run 1 |
| no unresolved blocking findings | **Cannot be affirmed.** The independent review found no BLOCKER, but its two MEDIUM conditions (R1, R2) are neither fixed nor accepted by the owner. The security alerts are unclassified. |

Closed since the 2026-11-15 report: artifacts retrievable and hash-verified (run 2); an independent review of the code delta exists
(APPROVE WITH CONDITIONS).

## B. Baseline

Hosted run `42223596080` (push to `integration/b03-ci-evidence-20261106`, head `a887e148` = the PR #86 head content), conclusion
failure: **76 failed, 2213 passed, 27 skipped, 1 xfailed.** 75 failures `no such object: alpine:3` in
`tests/core/sandbox/test_docker_backend.py`, 1 in `tests/core/sandbox/test_seccomp.py` (the AF_ALG test). Source: handoff section 11 and
`b03-ci-remediation-20261106/api/logs/primary_tests.log`; not re-read for this report.

## C. Root-cause findings

1. The Docker test image was never provisioned in the job's own daemon (75 failures).
2. The AF_ALG test asserted a host property rather than the property its name claims (seccomp-enforced); one failure.
3. `pull_request` did not cover `sandbox-network-isolation/b01-base`, and the two B03 files had no remote type check.
4. Found by hosted run 1: the first image choice `python:3.12-alpine` failed the preflight (`date +%s%N has no nanoseconds`, busybox).
   Fixed by the owner-approved switch to `python:3.12-slim` (D-1).

## D. Changes

Versus `a887e148`, six code files; nothing under `core/`, `docs/`, `requirements*`, `scripts/ci_test_gate.py`, or the two B03 files.

| Commit | Tree | What |
|---|---|---|
| `fc26681`, `fd52405`, `be4b99d`, `b0a1143` | | preflight, config tests, AF_ALG test, `-rfEs`, A2 test (the range an earlier independent review covered) |
| `164a078` | `b6beea40` | acts on that review (executables on DockerBackend's container PATH, digest run, capability probes, `mkfifo`, `sudo -n` for A2, skip-assertion step) |
| `0bee402` | `10d9b699` | image `python:3.12-slim` (D-1) |
| `a1aaffc` | `0209f75e` | N1: test pins `if: always()` on exactly four uploads; N4: skip step fails on a missing or empty pytest output |
| `5d2ef7b`, `70cae67`, `32b8f65`, `7e50dee`, `b2fe9a3` | | documentation and evidence only |

## E. Verification

| Check | Where | Result |
|---|---|---|
| Hosted jobs of run 2 (`tests` 132600378060, `typecheck-b03` 132600378311, `drift-and-ownership` 132600378424) | run conclusion re-read from the GitHub API today; job ids from the handoff; the reviewer read all three jobs' steps | all success; run 2 = `43644902316`, head `a1aaffc` |
| Docker preflight | artifact `docker-preflight` | `passed`; `python:3.12-slim` = `sha256:5e2bdb1b...4fa5b`; 19 required executables; probes on |
| pytest | artifact `pytest-output` | **2400 passed, 19 skipped, 9 xfailed, 0 failed**, exit code 0 |
| The 19 skips | re-counted today from the artifact | 4 `test_allowed_hosts` + 14 `test_namespace_backend` (cgroup v1) + 1 `test_docker_backend:895` (`gcc-multilib`); none is a Docker-prerequisite skip; none is the AF_ALG test |
| Gate and skip step on the hosted output | `hosted-run2/verification/` | both exit 0 |
| Drift | artifact `drift-report` | 15/15 PASS |
| mypy | artifact `mypy-b03` | default and `--strict` clean on the two B03 files (mypy 2.4.0) |
| Artifact hashes | `hosted-run2/GITHUB_DIGESTS.sha256`; the API's digest list re-read today | the four zips equal GitHub's digests (`sha256sum -c` of both evidence manifests run on 2026-11-17 when this session first verified the transfer: all OK, plus the one known CRLF mismatch in the older directory); today's API digest prefixes match |
| Config and preflight tests at `a1aaffc` | re-run today (config tests, Python 3.13) / the reviewer (both files) | 31 passed / 100 passed |
| Independent review of `164a078`, `0bee402`, `a1aaffc` | `b03-ci-remediation-20261106-review-20261119/` | **APPROVE WITH CONDITIONS**, no BLOCKER; R1 and R4 reproduced today |
| Local-lab evidence of the earlier code state | `b03-ci-remediation-20261106/` | unchanged; not repeated |

Indirect, not direct: the `-q` output has no per-file progress lines, so "the Docker-backed tests ran" rests on the counts (xfailed 1 to
9, the 8 contract tests; 75 formerly failing tests no longer fail; no Docker skip) and "the AF_ALG production test ran" on its absence
from the skip list and from the failures.

## F. GitHub Actions evidence

| Run | Event, branch | Head (tree) | Result |
|---|---|---|---|
| `43643507359` | push, `integration/b03-ci-remediation-20261106` | `32b8f659` (`28ab4137`) | **failure** at the Docker preflight (`python:3.12-alpine`). Stays a failed run. Artifacts not collected. |
| `43644902316` | push, same branch | `a1aaffc` (`0209f75e`) | **success** (section E) |

PR-event evidence: **none for the remediation.** Run 2 was a push, so merge-ref delivery of the new `b01-base` trigger is untested
(reviewer, "could not verify"). Indirect context only: run `42501282719` (an unrelated branch into `main`) shows the packet-ownership
step skipping cleanly under a real `pull_request` event. Item 14 of the evidence package (PR #86 state) is current as of section A.

## G. D10 reconciliation

Unchanged: `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt` sha256 `51caa5d6d79c790162d1d97095a00c94127b337c26ad5d420ce400e47f158316`,
34 entries; `scripts/ci_test_gate.py` unchanged. `git diff --quiet a887e148 HEAD` over the list, the gate, `core/`, `requirements*` and the two
B03 files returned 0 today. Run 2 did not need the list (nothing failed). Nothing was added to it; the 15 sandbox-local lab failures that
the lab-only gate run flagged do not occur on hosted CI and were not added either.

## H. B03 acceptance reconciliation

B03 stays inert: no change under `core/`, to `_sandbox_network.py`, or to `test_sandbox_network_guards.py` (diff rc=0, section G). The hosted
type check of the two B03 files is clean. No wiring into `DockerBackend.create()`, no `_CAPS`/`SandboxCapability` change, no
DEBT-039/DEBT-040 closure and no TC-13/TC-15/G4/G6 claim is made anywhere in this workstream. The B03 acceptance table in
`docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md` (section 22) was **not** re-derived for this report; no new
acceptance claim is made.

## I. Remaining gaps

| Gap | State |
|---|---|
| PR #86's head has never run the remediated workflow; the CI fix is on another branch (F12/U9, D-13) | OPEN, owner decision |
| PR-event proof for the B03 branch (R6) | INCOMPLETE, owner decision |
| Security alerts: code scanning and Dependabot return 403; the push response mentioned 7 default-branch vulnerabilities (3 critical, 4 high), unclassified | INCOMPLETE (needs working API access or an export from the owner) |
| Review conditions R1, R2 (MEDIUM): the CI can go green with Docker-backed tests not executed (deselected file; A9 skipped for `gcc-multilib`). Installing `gcc-multilib` alone would make A9 fail (it hardcodes the unprovisioned image `ocbrain-test/base:local`, handoff U4) | OPEN, owner decision (N2) |
| R3 to R5 (LOW), N3, N5 (named in the handoff, not described there), N6 / R6 (pin the image digest), U17 / R7 (stale "busybox" wording), F8 / D-15 (stale doc reference) | OPEN or DEFERRED, owner decisions |
| Evidence items 4 to 7, 9, 11 to 13 exist for run 2 (head `a1aaffc`), none for PR #86's own head; artifacts of run 1 not collected | INCOMPLETE |
| State outside the repository: `independent_review_report_164a078.md` and the 2026-11-15 report (this one replaces the latter in the repository); the original assignment text (U15; section 2 of the handoff stays an extraction) | INCOMPLETE |
| Review limits: static plus scratch mutation; no real Docker run outside the hosted one; Python 3.12 not exercised; the preflight script's own logic not mutated by the reviewer | stated |

## J. Recommendation

Keep **NO-GO / INCOMPLETE**. In this order, all owner decisions; none requires a merge here:

1. How the CI fix reaches PR #86's head or `b01-base`, and whether to open a PR into `b01-base` for the PR-event proof (D-13/U9). Until
   then no hosted result speaks for PR #86 itself.
2. Whether to accept or fix R1 and R2, and whether to bundle R3 to R5, N6, U17 and F8 into one hardening round. That round changes CI
   files, so proving it needs a push to `integration/**` and a new hosted run: it needs an explicit go.
3. The security alerts: an export, or a token that can read code scanning and Dependabot, then a classification.
4. Revoke the GitHub token that is pasted in clear text in the saved Claude preferences (handoff sections 0, 0a); it was not used here.
