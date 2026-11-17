# Notes of the continuing session, 2026-11-15 to 2026-11-17 (workstream: B03 CI remediation, PR #86)

Read `/handoff.md` section 0a first. This file holds the detail behind it.

**Status of this file: these are checks by the session that continued from Handoff v5. They are NOT the independent review.**
That session read the handoff first, so it is not independent. U8/R10 (independent re-review of `0bee402` and `a1aaffc`) stays INCOMPLETE.

## 1. Independent-review attempts (all failed, nothing was reviewed)

The brief is `review/review_request_b0a1143_a1aaffc.md`. It was sent to a fresh general-purpose agent five times. Each attempt ended at once with
`You've hit your 5-hour limit` (HTTP 429, error type `rate_limit`) and produced no output. Nothing in this repository derives from those agents.

| # | Turn time (UTC, approximate) | Reset time the error reported |
|---|---|---|
| 1 | 2026-11-15 about 16:40 | 9:30pm |
| 2 | 2026-11-16 00:15 | 5:10am |
| 3 | 2026-11-16 08:25 | 1:20pm |
| 4 | 2026-11-16 13:33 | 6:30pm |
| 5 | 2026-11-16 23:15 | 4:10am |

Every retry made after a stated reset time failed again with a new reset time, so the limit is not simply "wait until the stated time". The next
session should expect the same, check the account's usage first, and record INCOMPLETE if the agent is again unavailable (handoff section 12 records the same
pattern from the earlier session: three failures, then a resumed agent finished).

## 2. Targeted checks of `164a078`, `0bee402`, `a1aaffc` (not independent)

### 2.1 The handoff against the live repository and remote (2026-11-15; remote and PR state re-checked on 2026-11-16 and again just before the push on 2026-11-17)

- Remote tips: `tmp/b03-ci-remediation-handoff-20261112` = `7e50dee0e14b25eed3bcd449be16128681a63a8e`; `integration/b03-ci-remediation-20261106` = `a1aaffc3088ab70dc69c1de1d3c4f0d59bc37c38`; `sandbox-network-isolation/b03-capacity-ipv6-guards` = `a887e14881670fae2e4c6828a47a268c4a9d2296`.
- Trees: `164a078` = `b6beea40…`, `0bee402` = `10d9b699…`, `a1aaffc` = `0209f75e…`, matching handoff section 0 and section 7.
- `git diff --name-only 164a078 7e50dee` outside `handoff.md` and `handoff-evidence/`: `.github/workflows/ci.yml`, `scripts/ci_docker_preflight.py`, `tests/test_ci_docker_preflight.py`, `tests/test_ci_workflow_config.py` (0bee402 and a1aaffc, as documented).
- `git diff --quiet a887e148 -- <D10 list, scripts/ci_test_gate.py, core/, requirements.txt, the two B03 files>`: no difference. D10 list sha256 `51caa5d6d79c790162d1d97095a00c94127b337c26ad5d420ce400e47f158316`.
- PR #86: open, not merged, head `a887e148`, base `e2266603`, `updated_at` 2026-11-02T14:37:24Z (unchanged through 2026-11-17).
- Hosted runs on the remediation branch: only `43643507359` (failure) and `43644902316` (success).
- `sha256sum -c SHA256SUMS` of the OLD evidence directory: one mismatch, `local/T1_test_suite_side_effect_config_diff.patch`. This is the CRLF caveat the handoff already documents (section 8); it is not a content change.

### 2.2 Does the skip-assertion regex match the real skip reasons?

Regex in `ci.yml` (step "Assert the Docker-backed tests ran"): `^SKIPPED .*(requires a reachable Docker daemon|requires the test image)`.

| Source | Reason string | Matched |
|---|---|---|
| `tests/core/sandbox/test_docker_backend.py:82-84` (`_needs_docker`) | `requires a reachable Docker daemon` | yes |
| `tests/core/sandbox/test_network_isolation_contract.py:116` and `:120` (`_docker_ready`) | `requires a reachable Docker daemon` | yes |
| `tests/core/sandbox/test_network_isolation_contract.py:118` | `requires the test image '<image>' locally (...)` | yes (prefix `requires the test image`) |
| `tests/core/sandbox/test_docker_backend.py:890` (`_needs_32bit_toolchain`) | `requires gcc-multilib (a real 32-bit static toolchain)` | no, on purpose (a toolchain skip, judged on its own reason) |

Pytest's `-rs` line format on the hosted run is `SKIPPED [1] path:line: reason` (see the hosted `pytest-output.txt`), which the `^SKIPPED ` anchor matches.
The step's `run:` block was extracted from `ci.yml` and executed on the real hosted output: exit 0, "no Docker-prerequisite skips" (`verification/skip_step_rerun_on_hosted_output.txt`).
Limit: only skips with those two phrases are caught. A future skip about Docker with different wording would not be.

### 2.3 Does the N1/N4 test pin do what it says? Mutation check on a scratch copy of the tree at `7e50dee`

Script `review/mutate_n1_n4.py.txt`, output `review/n1_n4_mutation_output.txt`. Python 3.13.18 venv with pytest and pyyaml, outside the repository. Each mutant edits `.github/workflows/ci.yml` in a fresh `git archive HEAD` copy and runs `tests/test_ci_workflow_config.py -x`.

| Mutant | Result |
|---|---|
| M0 baseline | 31 passed |
| M1 remove `if: always()` from the docker-preflight upload | KILLED |
| M2 `if: ${{ always() }}` | KILLED (the test compares the string `always()` exactly) |
| M3 `if: always() && false` | KILLED |
| M4 remove the missing/empty-output guard | KILLED |
| M5 drop `requires the test image` from the regex | KILLED |
| M6 regex that matches nothing | KILLED |
| M7 `grep` reads another file | KILLED |

8 variants tried, 7 mutants, 7 killed. This covers only the mutants tried; it is not a proof of completeness. The N1 test parses the YAML (not text grep), counts uploads by `uses: actions/upload-artifact@...` and requires exactly 4 with `if == "always()"`.
An upload done by some other action or by a shell command would not be counted by it.

### 2.4 CI tests

`python -m pytest tests/test_ci_workflow_config.py tests/test_ci_docker_preflight.py -q -p no:cacheprovider` in a scratch venv (Python 3.13.18; pytest, pyyaml): **100 passed, 1 warning** (unknown config option `asyncio_mode`, because pytest-asyncio is not installed in that venv). This is Python 3.13, not the CI's 3.12.

### 2.5 Findings from reading the changed files (none blocks anything)

| ID | Severity | Location | Finding |
|---|---|---|---|
| S1 | NIT | `.github/workflows/ci.yml:108` | Comment says the probes exercise "the busybox features the tests depend on". The image is now Debian (`python:3.12-slim`, GNU coreutils). |
| S2 | NIT | `scripts/ci_docker_preflight.py:193` | Comment about "Applet FEATURES ... a stripped busybox". Still true as a general remark about minimal images, but no longer the CI image. |
| S3 | NIT | `tests/test_ci_docker_preflight.py:612` | Docstring says "GNU here, busybox in CI". CI is GNU too since `0bee402`. |

Not edited: a comment-only change is a new commit, so it would need a new push and a new hosted run, and D-1's authorized scope was the image string, the test image constant and "necessary image-specific preflight adjustments". Left for the owner (a docs/comment round, like F8 / D-15).
The remaining `alpine` references in the changed files are legitimate: the product default `alpine:3` in `DockerBackend` and the tests' `os.environ.get(..., "alpine:3")` fallbacks, and history comments explaining why alpine was rejected.

### 2.6 Hosted run 2 (`43644902316`) step conclusions, read from the public API on 2026-11-16

`tests` (job 132600378060): the API listed 13 steps (numbers 1 to 10 and 19 to 21; it did not list 11 to 18), all `completed`/`success`, in this order: Set up job, Checkout, Set up Python, Install dependencies, **Docker preflight and test-image provisioning**, Upload Docker preflight report, **Run test suite**, Upload full test output, **Gate on pytest exit code, errors and unlisted failures**, **Assert the Docker-backed tests ran**, then the post steps and Complete job.
`typecheck-b03` (132600378311): success, including "mypy on the B03 files (default and --strict)". `drift-and-ownership` (132600378424): success.

## 3. The artifacts of run 2

See `README.md` in this directory. Result: all four artifact zips match GitHub's digests byte for byte, and their contents agree with the handoff (preflight `passed`, 2400 passed / 19 skipped / 9 xfailed, DRIFT 15/15, mypy clean). The pytest output shows no failure at all, so the D10 allowlist was not used by this run.
The 19 skips: 4 in `test_allowed_hosts.py` and 14 in `test_namespace_backend.py` (cgroup v1), 1 in `test_docker_backend.py:895` (gcc-multilib). The production AF_ALG test is not in the skip list, so it ran and passed on the hosted kernel.

## 4. Network facts established

- The artifact endpoint `https://api.github.com/repos/1h0lde4/ocbrain-v4.1/actions/artifacts/<id>/zip` answered an unauthenticated request with HTTP 302 to `productionresultssa8.blob.core.windows.net` (a signed URL; not stored here).
- The session's proxy refused the connection to that host (`CONNECT tunnel failed, response 403`). Not worked around. The artifacts were therefore supplied by the user, as the bundle.
- WebSearch/WebFetch and the git proxy are unaffected. Pushes to the repository work through the session's git proxy.

## 5. State that exists outside this repository (cannot be reproduced from it)

- `independent_review_report_164a078.md` (the fresh static reviewer's APPROVE WITH CONDITIONS on `164a078`, cited by handoff section 0): kept outside the repository by the previous session. **Not available to the continuing session; the user may still hold it.** Only `handoff-evidence/b03-ci-remediation-20261106/review/independent_review_report_b0a1143.md` is in the repository.
- The final report A to J delivered to the user on 2026-11-15 (decision NO-GO) through SendUserFile: not in the repository, not available to the continuing session.
- The original assignment text (U15): never available.
- Artifacts of run 1 (`43643507359`, the alpine failure): not collected.
