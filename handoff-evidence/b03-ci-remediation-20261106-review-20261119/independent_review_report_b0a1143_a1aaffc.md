# Independent review of `b0a1143..a1aaffc` (fresh agent, delivered 2026-11-19)

Provenance: the hand-back of a fresh subagent (agentId `afdcc946371ae2bb0`), briefed with the stored brief
`../b03-ci-remediation-20261106-hosted-run2/review/review_request_b0a1143_a1aaffc.md` (reviewer-facing text only; repository path and
tip adjusted; no author conclusions in it). It is **model output, not a user message and not an authority**. The block below the
line is transcribed verbatim from the hand-back by the continuing session; nothing in it was edited. How the review came about, what
the continuing session checked in it, and which findings it reproduced: `README.md` in this directory.

The reviewed range's code delta is `164a078`, `0bee402`, `a1aaffc` (the commits between them that only add documentation or evidence
are `5d2ef7b`, `70cae67`, `32b8f65`). The agent worked on a scratch `git archive` of `a1aaffc`, not on the repository checkout.

---

```text
Verdict: APPROVE WITH CONDITIONS. No blocker found. R1 and R2 (the CI can go green with Docker-backed tests not executed) should be fixed or explicitly accepted by the owner before the green run is treated as proof.

FINDINGS
ID | Sev | file:line | Problem | Evidence | Fix
R1 | MEDIUM | .github/workflows/ci.yml:159-163, 186-201; tests/test_ci_workflow_config.py:149-156 | The step "Assert the Docker-backed tests ran" only greps for two skip wordings. It does not assert the Docker tests executed, and no test pins the pytest command beyond the -r flags. | Scratch mutations: narrowing the target to one file, appending `--deselect tests/core/sandbox/test_docker_backend.py`, or `--ignore=` of that file each leave all 31 config tests green. No SKIPPED line would appear, so the step passes. | Pin the whole pytest argv in a test. Add a positive check (junitxml, or a passed count for test_docker_backend.py and the contract file greater than 0), or rename the step.
R2 | MEDIUM | tests/core/sandbox/test_docker_backend.py:890-895; ci.yml:190-191 | The A9 AF_VSOCK int-0x80 bypass test is skipped on hosted CI ("requires gcc-multilib"). The comment says such skips are "judged on their own reason", but nothing enforces that. | Hosted pytest-output of run 43644902316 lists it as skipped. 4 allowed_hosts and 12 namespace skips (cgroup v1) also never run on hosted. | Install gcc-multilib in the job, or add an explicit allow-list of accepted skips.
R3 | LOW | tests/core/sandbox/test_seccomp.py:271-277 | On a kernel without AF_ALG the production AF_ALG test skips. The default-table wiring of apply_denylist() is then unpinned. | Scratch copy where the apply_denylist default omits AF_ALG but the table is intact: 19 passed, 1 skipped, no failure. Removing AF_ALG from the table fails 2 tests. | Assert "socket(family=38)" is in the probe's `applied` list, or assert the signature default `is DENIED_SOCKET_FAMILIES`.
R4 | LOW | ci.yml:192-201 | Skip-step regex and guard are brittle. | Verified rc=0 for whitespace-only output, dots-only output and crash text. Also rc=0 for `FORCE_COLOR=1` output (`ESC[33mSKIPPED` defeats `^SKIPPED`), a reason on a continuation line, and a grep exit 2 (treated as "no match"). These pass only because the gate runs first. | Add `--color=no` to pytest. Require the summary line in this step. Use `grep -a` after stripping ANSI.
R5 | LOW | tests/test_ci_workflow_config.py (gaps) | Weakenings that still pass all 31 config tests. | (g) `defaults.run.shell: bash {0}` drops `-e`; the drift step (ci.yml:37-38, `check_drift.py; echo`) would then mask a failure. (k) `echo 0 > pytest-exit-code.txt`. (e, f) `if-no-files-found: ignore` or a changed upload path. (h) unpinned action refs. (s) reverting the image to python:3.12-alpine (only the hosted preflight catches it). | Pin the shell, PIPESTATUS, upload paths, if-no-files-found, SHA pins and the slim image.
R6 | LOW | ci.yml:81 | The floating tag python:3.12-slim is not digest-pinned, and the pull is unauthenticated Docker Hub. | The hosted preflight log shows "Downloaded newer image". The digest is recorded only after the fact. The 3 retries at 5s do not help a rate limit. It fails closed (red), never falsely green. | Pin by digest, or accept the drift consciously.
R7 | NIT | ci.yml:108; scripts/ci_docker_preflight.py:193; tests/test_ci_docker_preflight.py:612 | Stale busybox wording left from the image switch. | Line 612 says "busybox in CI", which is now false. | Reword.
R8 | NIT (pre-existing, not in the delta) | ci.yml:46-56 | The branch name is interpolated into Python source (`branch = '$BRANCH'`). | With GITHUB_HEAD_REF=`x'+__import__('os').system(...)+'` the injected expression was evaluated (TypeError raised after the call). Impact is bounded: pull_request (not _target), contents: read, no secrets, and PR code already runs in the job. | Read it from os.environ.

ANSWERS
1. Image switch. `grep -rn 'python:3.12-alpine'` outside handoff finds only the history comment at ci.yml:74. The constants, help string (preflight.py:289), test IMAGE (test_ci_docker_preflight.py:39) and the reason string (test_ci_workflow_config.py:457) are all slim. Only the stale wording in R7 remains. No vacuous pass found on slim: the lookup uses `[ -x ] && [ ! -d ]` on the container PATH, and the probes require a numeric 19-digit `%N`. The hosted preflight JSON shows executables_rc=0, capabilities_rc=0, digest_run_rc=0.
2. N4 skip step. Real pytest 9.2.0 format is `SKIPPED [N] path:line: reason`. It was confirmed from the hosted output and from a real run of both Docker test files with no daemon (85 skipped), against which the extracted `run:` block exits 1. The matched reasons are exactly the real ones: test_docker_backend.py:82-84 ("requires a reachable Docker daemon") and test_network_isolation_contract.py:114,118 ("requires the test image"). The only other in-test skip (contract:1023) is not Docker related. The step alone can pass on crash, truncated or whitespace-only output (R4), but the Gate step before it requires exit code 0 or 1, a summary line and at least one passed test. Different wording on a new Docker skip would slip through (R1, R4).
3. Ordering and propagation. With no `shell:`, GitHub uses `bash -e {0}` (no pipefail); explicit `shell: bash` is `bash --noprofile --norc -eo pipefail {0}`, per the docs I fetched. "Run test suite" does `set +e`, reads PIPESTATUS[0] straight after the tee pipeline and exits 0 by design. The gate then decides. If the preflight fails, pytest is skipped, the uploads still run and the job is red. If pytest fails, the gate fails the job. The mypy step ends in `[ ] && [ ]` under `set +e`. No masking found.
4. N1 test. It parses YAML (yaml.safe_load), requires exactly 4 `uses: actions/upload-artifact@` steps, and requires `str(if) == "always()"`. Scratch mutants `${{ always() }}`, `always() && true`, `success() || always()` and a removed `if` each fail at least one test. The removed-`if` case fails the N1 test itself. For the other three, the first failure shown was the older conditionals test, which uses the same strict equality. It does not pin if-no-files-found or the upload paths (R5).
5. 164a078. I re-verified F1-F7, F9, F10 and F11 against the code. F1: `_host_root_prefix` with `sudo -n`, pytest.fail rather than skip, and a mountinfo assertion. F2: `_CONTAINER_PATH` equals `_build_container_env({})["PATH"]` (docker_backend.py:249-253), and a test pins it. F3: the digest run. F4: the probes. F5: mkfifo is required, and the second ratchet catches a new `tail` in a sh -c script, as do dropping mkfifo and dropping the probe flag (mutants all failed). F6, F7 and F11 are present. No regression found. NIT: the smoke runs omit DockerBackend's --read-only, memory and pids flags, and request env can override PATH.
6. test_seccomp. It discriminates when the kernel has AF_ALG. Without the filter, the control returns 0 and the filtered errno would be 0, so it fails. A synthetic probe class covers the broken-filter shapes. The AF_INET stand-in test covers the discriminating branch on every kernel. The skip fires only when the unfiltered control already returned 97, and the filter-installed and control assertions run before the skip. A missing libseccomp fails loudly (probe rc != 0). The vacuity gap is R3. The hosted run shows no skip for this test, so it passed there.
7. Integrity. `git diff --name-status a887e148 HEAD` outside handoff-evidence shows only ci.yml, handoff.md, the new preflight script and two new tests, test_docker_backend.py and test_seccomp.py. Blob hashes are identical for D10 (83f34cd2), ci_test_gate.py (93425174), requirements.txt (b9785ae3), `_sandbox_network.py` (ac1543a1) and `test_sandbox_network_guards.py` (fd1e622c). `git diff --quiet a887e148 HEAD -- core docs scripts/ci_test_gate.py 'requirements*'` returns 0.
8. Workflow security. Permissions are `contents: read` only, there is no pull_request_target, and there are no `${{ }}` expressions. The actions are SHA-pinned and unchanged from a887e148. Only R8 and the pull-rate point in R6.
9. Other. R1 and R2 above. The 9 xfails are strict and typed by design, and `-rfEs` does not list them.

COMMANDS RUN (venv outside the repo, Python 3.13.18, pytest 9.2.0, on a scratch `git archive` of a1aaffc)
- `pytest tests/test_ci_workflow_config.py tests/test_ci_docker_preflight.py -q`: 100 passed.
- `pytest tests/core/sandbox/test_seccomp.py tests/test_ci_test_gate.py -rs`: 86 passed, 1 skipped (the AF_ALG production test; this kernel 6.18.44 has no AF_ALG).
- `pytest tests/core/sandbox/test_docker_backend.py tests/core/sandbox/test_network_isolation_contract.py -rfEs`: 25 passed, 85 skipped (no daemon).
- Seccomp mutants: the AF_ALG table entry removed gave 2 failed, 17 passed, 1 skipped; the default-argument weakening gave 19 passed, 1 skipped.
- 23 workflow mutants with `pytest tests/test_ci_workflow_config.py`; results are in the findings above.
- A real pytest skip-format experiment, including `FORCE_COLOR=1`.
- The extracted skip-step `run:` block executed under `bash -e` against real output and 8 variants.
- Unauthenticated GitHub API reads of run 43644902316. All three jobs concluded success on a1aaffc3 (a push to integration/b03-ci-remediation-20261106), including every step. The sha256 of the four artifact zips in the author's evidence folder matches the API `digest` fields. The hosted pytest output reads "2400 passed, 19 skipped, 9 xfailed".

COULD NOT VERIFY
- The pull_request trigger for b01-base. The hosted run was a push event, so merge-ref delivery of the new trigger is untested.
- A real Docker preflight or Docker-backed test run. There is no daemon here and Docker Hub is unreachable, so only the fake-docker tests ran.
- The SHA-to-tag mapping of the three actions. The proxy blocked the actions/* API calls.
- The AF_ALG-present branch of the seccomp test locally. I relied on hosted evidence that it did not skip.
- The A2 test as a non-root runner with sudo.
- The full suite, Python 3.12 specifically, and mutation of the preflight script's own logic. The author's mutants were not reviewed.
- Hosted job logs. That endpoint needs auth, and I used the author's copies only for context.
```
