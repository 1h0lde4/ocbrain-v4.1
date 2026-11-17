# Brief for the independent review of `b0a1143..a1aaffc` (reusable, verbatim)

Status: this brief was sent five times (2026-11-15 to 2026-11-16) and never ran: every attempt ended with HTTP 429, "5-hour limit"
(see `../second_session_notes_20261117.md`, section 1). It is stored so the next session can send it again unchanged.
Before re-sending: adjust the repository path if the checkout is not at `/home/claude/ocbrain-v4.1`, and re-check that the
tip is still `7e50dee` or later (`git log b0a1143..a1aaffc` is the reviewed range and does not move).
Send it to a FRESH agent that has not seen the work. Do not paste the author's conclusions into it. If the usage limit recurs,
record the review as INCOMPLETE; do not substitute a self-review.

---

You are an independent reviewer. You have not seen the work you are reviewing. Do a rigorous, adversarial, READ-ONLY review of a CI/test change set and report findings. Do not modify, commit, stage, or push anything in the repository. Do not print, request, or use any credentials. Do not try to pull Docker images (Docker Hub is unreachable here).

REPOSITORY: /home/claude/ocbrain-v4.1 (shallow clone, branch tmp/b03-ci-remediation-handoff-20261112, HEAD 7e50dee). Public GitHub repo 1h0lde4/ocbrain-v4.1.

WHAT TO REVIEW: the code delta `git diff b0a1143..a1aaffc` (three commits: 164a078, 0bee402, a1aaffc). Commit b0a1143 was reviewed before; these three were NOT. Files of interest: .github/workflows/ci.yml, scripts/ci_docker_preflight.py, tests/test_ci_docker_preflight.py, tests/test_ci_workflow_config.py, tests/core/sandbox/test_seccomp.py, tests/core/sandbox/test_docker_backend.py. Read the full commit messages (`git log b0a1143..a1aaffc`). Ignore handoff.md and handoff-evidence/ as evidence of correctness: they are the author's own claims, not proof. You may read them for context only.

INTENDED REQUIREMENTS (judge the change set against these):
A. The CI job must provision the exact Docker test image in the same daemon pytest uses, record digest/image ID, and fail explicitly if anything is missing. No fallback image, no mocks, no skips introduced to get green, and nothing added to the known-failure allowlist docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt (must be byte-identical to commit a887e148; scripts/ci_test_gate.py must also be unchanged).
B. The AF_ALG seccomp test must test the production filter directly in an isolated subprocess with an unfiltered control case and a filter-installed check; no policy weakening; any conditional skip needs a verifiable reason.
C. PRs targeting sandbox-network-isolation/b01-base must run normal PR CI; keep the `main` pull_request trigger and the `integration/**` push trigger; no event-specific bypass, no workflow_dispatch, no continue-on-error, no job-level `if`; keep the four artifact uploads (docker-preflight, pytest-output, drift-report, mypy-b03) with `if: always()`; a narrow mypy job covering exactly the two B03 files.
D. Out of scope and must be unchanged vs a887e148: everything under core/, docs/, scripts/ci_test_gate.py, requirements*, the two B03 files (core/sandbox/backends/_sandbox_network.py and tests/core/sandbox/test_sandbox_network_guards.py).
E. Commit 0bee402 switches the CI image from python:3.12-alpine to python:3.12-slim (owner-approved decision). Commit a1aaffc adds (N1) a test pinning `if: always()` on exactly four upload steps and (N4) makes the "Assert the Docker-backed tests ran" step fail when /tmp/pytest-output.txt is missing or empty.

SPECIFIC QUESTIONS (answer each explicitly with evidence file:line):
1. Image switch: is every reference to the old image gone (workflow, tests, constants, comments, help strings, docs inside the changed files)? Are any alpine/busybox-specific assumptions still baked into the preflight, its probes, or its tests that are wrong for a Debian-based slim image? Anything in the preflight that could pass vacuously on the slim image?
2. N4 skip step: read the real `run:` block. Can the step pass when pytest did not run, when the output file is empty/truncated, when pytest crashed before printing a summary, or when the SKIPPED-line regex does not match the real pytest `-rfEs` format (check the pytest short-test-summary format for skipped tests, including multi-line and `SKIPPED [N]` forms)? Which skip reasons does it match, and are those the right strings from the actual test files (grep tests/core/sandbox/test_docker_backend.py and test_network_isolation_contract.py for the real skip reasons)? Could a Docker-prerequisite skip use different wording and slip through?
3. Step ordering and failure propagation in the `tests` job: if pytest fails, does the gate still run and does the job end red? If the preflight fails, does pytest still run? Can any step exit 0 while masking a failure (tee pipelines without pipefail, `|| true`, `; true`, exit-code files, shell options)? Check the exact shell and `set` flags GitHub uses for `run:` with and without an explicit `shell:`.
4. N1 test: does it truly pin `if: always()` on every upload step and "exactly four"? Is it robust to YAML forms (`if: ${{ always() }}`, `if: always() && ...`, `if: success() || always()`), or could a weakened workflow still satisfy it? Does the test parse YAML or grep text?
5. 164a078: it was meant to address the earlier review findings (executables lookup on DockerBackend's container PATH, container also started from the resolved RepoDigest, capability probes `date +%s%N`/`sleep 0.01`/`head -c 1`, mkfifo required, A2 test using `sudo -n`, etc.). Re-verify each against the actual code. Any regression or new defect?
6. tests/core/sandbox/test_seccomp.py: does the production AF_ALG test discriminate (would it fail if apply_denylist() did not block AF_ALG)? Is the skip condition sound (skip only when the unfiltered control already returns EAFNOSUPPORT)? Any way the control and the filtered check could both pass vacuously?
7. Allowlist/gate integrity: confirm by command that D10 list, ci_test_gate.py, core/, requirements*, and the two B03 files have no diff vs a887e148.
8. Security of the workflow file itself: permissions, untrusted input in `run:` blocks, pinned action versions, anything that grants more than `contents: read`.
9. Anything else you find that could make the CI green while the thing it claims to check did not run.

You MAY run, from a virtualenv created OUTSIDE the repository (e.g. under the scratchpad/tmp dir; pip works through a proxy), the narrow CI tests: `python -m pytest tests/test_ci_workflow_config.py tests/test_ci_docker_preflight.py -q` (install only what those need, e.g. pytest, pyyaml, and whatever they import; if collection fails for missing deps, say so). You may also mutate a SCRATCH COPY of the repo (copy to a temp dir) to test whether the tests catch regressions; never mutate the original checkout. You may read the hosted run metadata with unauthenticated reads, e.g. `curl -sS https://api.github.com/repos/1h0lde4/ocbrain-v4.1/actions/runs/43644902316/jobs` (job/step conclusions only; the log endpoint needs auth).

OUTPUT FORMAT (plain text, under ~1200 words, no preamble):
- Verdict: APPROVE / APPROVE WITH CONDITIONS / REJECT, in one line.
- Findings table: ID | severity (BLOCKER/HIGH/MEDIUM/LOW/NIT) | file:line | what is wrong | evidence | recommended fix. Number them R1, R2, ...
- Answers to questions 1-9, each 1-4 sentences with evidence.
- Commands you ran with their outcomes (exact test counts).
- What you could NOT verify and why.
Do not pad. Do not praise. If you find nothing for an item, say "no finding" and what you checked.
