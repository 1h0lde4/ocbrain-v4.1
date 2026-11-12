# Evidence for the B03 CI remediation workstream (local lab evidence only)

Workstream `sandbox-network-isolation`, PR #86 (B03). Branch `integration/b03-ci-remediation-20261106`.
Governing document for the handoff: `/handoff.md` (repository root). Read it first.

**Nothing in this directory is GitHub-hosted evidence of the remediation branch.** The remediation
branch has never run on GitHub Actions. The only hosted material here is the *baseline* (runs on the
PR #86 head, before the remediation) and one unrelated PR-event run used as partial context. Every
`L*`, `F*`, `R*`, `M*`, `D*`, `I*` file was produced in an ephemeral local lab (see `handoff.md` section 14),
and the stand-in Docker image used there is NOT the CI image `python:3.12-alpine`.

A SHA-256 manifest of every file here is `SHA256SUMS` (regenerate with `sha256sum -c SHA256SUMS`).

## local/ (what each file is; "final" = produced on code commit 164a078 or later unless noted)

| Prefix | Content | Status |
|---|---|---|
| `B1`, `B2`, `B3` | Pristine PR #86 head (a887e148) run in the same lab: 124 failed. Before/after failing-set diff. | baseline |
| `F1_*` | Full pytest, `-rfEs`, code at b0a1143: 49 failed, ~2316 passed. | superseded by F4 |
| `F1a`, `F2a` | The discarded `-rs`-only run and its gate output: the gate fails with "N failed but 0 distinct FAILED node ID(s)". Kept as evidence of why `-rfEs` is required. | evidence of a defect that was fixed |
| `F2`, `F3_*` | Gate on the b0a1143 run (15 unlisted sandbox-local failures, exit 1) and the same run against a scratchpad-only extended allowlist (exit 0). | superseded by F4 for the counts; F3 shows the gate logic |
| `F4_*` | **Final-tree full pytest (49 failed, 2362 passed, 6 skipped, 9 xfailed), gate output (exit 1, 15 unlisted), the new skip-assertion step's real run block executed on that output (exit 0), failing-set comparison, git status before/after.** | final |
| `G1_*` | Scope diff vs PR head, D10 sha256 and 34 entries unchanged, B03 inertness. Produced at b0a1143; the unchanged claims were re-checked at 164a078 (see handoff section 13). | final claims re-checked |
| `D1_*`, `D2_*` | Drift DRIFT-01..15 (D1 at b0a1143, D2 final tree): all PASS, exit 0. | final = D2 |
| `I1`, `I2` | Import orders in fresh interpreters (3.12 and 3.13). I2 final. | final = I2 |
| `M1`, `M2`, `M3` | mypy on the two B03 files (default and `--strict`, mypy 2.4.0): clean; M2 negative control (the step exits 1 on a type error); M3 final tree. | final = M3 |
| `L1`-`L3a` | Real-daemon preflight cases against stand-in images: absent image fails at provision; present image passes; image without python3 fails at smoke. `L2a`/`L3a` are caught/discarded defective stand-ins. | at b0a1143 behaviour |
| `L4`, `L5` | Docker backend tests (96 passed, 1 skipped) and contract suite (5 passed, 8 xfailed) against the PREVIOUS stand-in image (no `mkfifo`). | superseded by R2 |
| `L6` | An image without python3: 17 tests fail (the "second layer" of the image prerequisite). | evidence |
| `L7` | New preflight vs the previous stand-in: fails at smoke naming `mkfifo` (a gap the earlier required-list missed). | final behaviour |
| `L8` | New preflight (probes + mkfifo + digest run) vs the rebuilt stand-in: PASS. | final behaviour |
| `L9` | New preflight vs an image whose `date` prints a literal `N`: fails at smoke, probe named. | final behaviour |
| `R1` | Docker tests as a NON-ROOT user without sudo, code at b0a1143: exactly 1 failure, the host-mount test (`test_a2_...`): reviewer finding F1 confirmed. | evidence of the defect |
| `R2` | Docker tests as a non-root user WITH passwordless sudo (a hosted-runner-like setup), final code: 101 passed, 1 skipped (gcc-multilib), 8 xfailed. | final |
| `R3` | The same A2 test as non-root WITHOUT sudo, final code: fails loudly with an explicit precondition message (no skip, no pass). | final |
| `T1` | Diff of `config/*.toml` that the test suite rewrites as a side effect (restored with `git checkout -- config/`; in no commit). | hygiene note |
| `U1`, `U2` | B03 unit tests (224 passed); `tests/core/sandbox` directory run at b0a1143 (8 failed namespace-backend, sandbox-local). | superseded by F4 |

## api/ (GitHub, read unauthenticated; the ambient token is invalid)

| File | Content |
|---|---|
| `pr86.json`, `final/pr86_final.json` | PR #86 state: open, head a887e148, base b01-base e2266603 (final: `mergeable_state` unstable, updated 2026-11-02). |
| `runs_head.json`, `runs_branch.json`, `jobs_42223596080.json`, `jobs_42223622852.json`, `logs/*` | The hosted baseline: runs 42223596080 and 42223622852 (push on the evidence branch, CI failure), tests job 127911372535, drift job 127911372979. |
| `final/runs_latest.json`, `final/jobs_pr_run.json`, `final/job_pr_*.log` | Run 42501282719: a `pull_request` event for an unrelated branch into main. Partial context only: shows the packet-ownership step under a real PR event printing "not one of this manifest's declared packet branches ... skipping cleanly". It is NOT a run of the B03 or remediation branch. |

## mutants/, lab/, scripts/, review/

Python files here carry a `.py.txt` suffix on purpose: the B03 inertness pin (`test_nothing_in_the_repository_imports_the_guard_module_yet`) scans every `*.py` in the repository for references to the guard module, and `mutate_all.py` names it. Rename to `.py` outside the repository tree to run them.

- `mutants/mutate_all.py.txt` + `mutate_all_run.txt`: 87 mutants over a scratch copy of the final code (44 preflight, 36 workflow-config, 7 production seccomp): 87/87 killed. The other `mutate_*.py.txt` files and `*_run*.txt` are the earlier suites at b0a1143 (superseded; one workflow survivor and one preflight survivor found there were fixed).
- `lab/`: `up.sh` (start containerd then dockerd), `mkrootfs.sh` (builds the stand-in rootfs; the tarball itself is not stored, it is reproducible).
- `scripts/`: `run_final.sh` (the final-tree acceptance run), `run_full.sh`, mypy step variants, `unlisted15.txt` (the 15 sandbox-local failures that are not on the D10 list).
- `review/independent_review_report_b0a1143.md`: the independent reviewer's report, verbatim (it reviewed b0a1143, not 164a078).
