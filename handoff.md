# Session Handoff

> **Version 4 (workstream: B03 CI and security verification remediation, PR #86).** It supersedes version 3
> (the DockerBackend closure and the DEBT-039 study), which is in git history: `git show 1b829fc:handoff.md`
> (it is also the `handoff.md` at the PR #86 head `a887e148`). Version 3's workstreams are closed and are not
> touched by this one.
>
> **Read this file completely before changing anything.** It is a transfer record, not an authority
> (PROJECT_INSTRUCTIONS 18.4.9): verify it against the live repository first (section 18).
>
> Scope warning, repeated because it is the most likely way to go wrong: **nothing in this handoff has been
> verified on GitHub-hosted CI.** The remediation branch has never run on GitHub Actions. All verification below
> is local-lab verification, and the Docker image used in the lab is a stand-in, not the CI image.

## 1. Handoff Metadata

- Handoff version: 4
- Created at: 2026-11-12 (UTC). The session ran 2026-11-06 through 2026-11-12 and survived several context compactions and container resets.
- Workstream: `sandbox-network-isolation`, PR #86 (B03 inert capacity and IPv6 guard primitives): CI and security verification remediation.
- Task identifier: "Independent Remediation Assignment: PR #86 B03 CI and Security Verification" (user attachment, 2026-11-06 21:53).
- Source session purpose: carry out that assignment (Batches 1 to 5). Batches 1 to 4 are implemented and verified locally; Batch 5 (full acceptance) is complete locally but **the hosted part, the evidence package and the final A to J report are not done**.
- Repository: `1h0lde4/ocbrain-v4.1` (public). Remote: `origin` = `https://github.com/1h0lde4/ocbrain-v4.1`.
- Transfer status: section 19.

## 2. Original Starting Prompt

**LIMITATION, stated plainly: the verbatim text of the assignment attachment is NOT available to this session.** It was attached
to the user message of 2026-11-06 21:53, and the surviving conversation transcript only contains compaction summaries of it.
What follows is a **faithful extraction of the operative requirements**, rebuilt from the session's own summary of the
assignment, **not** the user's words. It is labelled as an extraction on purpose (PROJECT_INSTRUCTIONS 18.4.8.3). The user still holds
the original; when it is attached to the next session it should replace this section and should be compared with the requirement ledger
(section 5) for drift.

### Extraction of the assignment ("Independent Remediation Assignment: PR #86 B03 CI and Security Verification")

Context given by the user: hosted CI for PR #86 (head `a887e148`) failed with 76 failures. The session's own baseline
analysis found 75 in `tests/core/sandbox/test_docker_backend.py` ("no such object: alpine:3") and 1 in `tests/core/sandbox/test_seccomp.py` (an AF_ALG test).

Mission:

- **A. Docker test image provisioning in CI.** Provision the exact image reference, verify it is available to the same daemon, record the digest or image ID, fail explicitly. No fallback image, no mocks or skips, and nothing added to the D10 known-failure allowlist.
- **B. AF_ALG seccomp test correction.** Establish the invariant first (host-level versus seccomp-enforced). Test the production filter directly in an isolated subprocess, with a control case and a filter-installed check. Rename the test. No policy weakening and no silent skip; any conditional skip needs an independently verified reason.
- **C. CI trigger.** PRs targeting `sandbox-network-isolation/b01-base` must run the normal PR CI. Keep the `main` pull_request trigger and the `integration/**` push trigger. Verify packet ownership under a PR event. No event-specific bypass. Keep the artifacts. Add a narrow remote mypy step for the two B03 files.
- **D10 gate:** strict, with the 34-entry allowlist unchanged.
- **B03 scope:** stays inert. No wiring into `DockerBackend.create()`, no `_CAPS`/`SandboxCapability` change, no B11, no DEBT-039/DEBT-040 closure, no TC-13/TC-15/G4/G6 claims, no `NETWORK_ALLOWLIST` change.
- **Batches:** (1) baseline and diagnosis; (2) Docker provisioning; (3) AF_ALG; (4) CI integration; (5) full acceptance. Batch 5 comprises B03 unit tests, `tests/core/sandbox`, full pytest, D10 gate, DRIFT-01..15, B03 mypy, both import orders in fresh interpreters, applicable mutation tests, and workflow and artifact inspection.
- **Evidence package (15 items):** remediation summary; original failure classification; before and after workflow config; Docker logs and image identity; full pytest output; AF_ALG evidence; mypy output; import-cycle check; drift report; D10 output and unchanged-allowlist comparison; artifact inventory with SHA-256 manifest; commit and tree SHA per run; Actions run IDs and links; PR #86 state and head/base verification; remaining limitations. Artifacts must be downloaded, inspected and hashed against GitHub digests where available. Vocabulary: PASS / FAIL / INCOMPLETE / DEFERRED. **Any missing item means NO-GO.**
- **Final report format A to J:** A final decision; B baseline; C root-cause findings; D changes; E verification table; F GitHub Actions evidence; G D10 reconciliation; H B03 acceptance reconciliation; I remaining gaps; J recommendation.
- **Allowed:** a new isolated remediation branch (`integration/b03-ci-remediation-20261106`), minimal CI/test file changes, focused tests, local verification, commit, and **push of that dedicated branch to obtain push-triggered CI evidence provided this does not modify PR #86**.
- **Prohibited:** modify PR #86 or its source branch or metadata; merge PR #86 or the remediation branch; close or retarget any PR; touch unrelated branches or PRs; change D10 allowlist entries; rerun or cancel existing workflow runs; use `workflow_dispatch`; modify secrets, credentials or permissions; claim a check ran when it did not; broad cleanup.
- **User-owned decisions (never decide):** PR #86 merge or hold; the evidence-acceptance route; B05 go plus time box; B04 go; DG-1 and DG-2; B10/B11 (gated); Q34(1) to (4); a docs-only revision round. The user's earlier recommendations were explicitly NOT authorizations.

## 3. Subsequent User Instructions / Corrections

Chronological; wording preserved where it matters.

1. Earlier and still binding (from sessions before this assignment): "never ever answer in french even if the prompt is in french" (answer in English). The pasted GitHub token must never be printed or stored (the user said it needs revoking; it may be used per command until it expires and never stored). Commit and PR attribution lines (section 14). "B05, B04, DG-1 and DG-2 each need their own go" (2026-10-17). The B03 final artifact reconciliation task (2026-11-04) said no additional implementation is authorized until the user's explicit decisions; the 2026-11-06 assignment is the explicit authorization for this remediation workstream and is what this session acted on.
2. 2026-11-06 21:53: the assignment (section 2).
3. 2026-11-07 00:47, 11-07 12:35, 11-07 16:46, 11-07 20:43, 11-08 12:54 (with earlier files re-attached, including the git bundle), 11-09 01:37, 11-09 08:48, 11-09 14:19, 11-09 22:29, 11-10 08:34, 11-10 13:46, 11-10 21:24, 11-11 15:38, 11-11 20:54: bare "Continue" messages. No new instructions.
4. **2026-11-12 09:31, verbatim (typos preserved): "Update the work i to a temporary branch, then create the handoff file for tge remaining work".** Interpretation taken (this is an interpretation, not a confirmed instruction): push the work to a temporary remote branch, then write this handoff file for what remains. The temporary branch is `tmp/b03-ci-remediation-handoff-20261112` (a name chosen so that it matches **none** of the workflow's push triggers `main`, `h2/**`, `integration/**`, so pushing it started no CI run). **Pushing to the dedicated branch `integration/b03-ci-remediation-20261106`, which would start CI, was deliberately NOT done** (see D-12).

## 4. Goal, Scope & Success Criteria

### Goal

Make the hosted CI of PR #86 (B03) trustworthy and green for the right reasons: the Docker test image is provisioned and identified,
the AF_ALG seccomp test asserts the property its name claims, PRs into `sandbox-network-isolation/b01-base` run normal PR CI, and the B03 files are
type-checked remotely. B03 stays inert and the D10 gate stays strict and unchanged.

### In scope

`.github/workflows/ci.yml`, `scripts/ci_docker_preflight.py` (new), the CI tests, `tests/core/sandbox/test_seccomp.py`, and the minimal test-side fix to `tests/core/sandbox/test_docker_backend.py` (D-11). Verification, evidence and the final report.

### Out of scope (do not change)

PR #86 and its branch; anything under `core/`; `docs/` (in particular `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`, 34 entries, sha256 `51caa5d6d79c790162d1d97095a00c94127b337c26ad5d420ce400e47f158316`); `scripts/ci_test_gate.py`; `requirements*`; the two B03 files; secrets, permissions, workflow_dispatch; B04, B05, B10, B11, DG-1, DG-2, Q34; merging or retargeting any PR.

### Success criteria (the assignment's, restated)

All 15 evidence-package items demonstrated, including **hosted** Actions runs of the remediation branch with downloaded and hashed artifacts, and a PR-event proof. Any missing item means NO-GO. The final report A to J delivered.

## 5. Requirement Ledger

Status vocabulary here: VERIFIED-LOCAL means verified in the local lab only. **HOSTED-UNVERIFIED** means no GitHub run exists yet.

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R1 | Provision the exact Docker test image in the job's daemon, fail explicitly, no fallback/mocks/skips | Assignment A | IMPLEMENTED; VERIFIED-LOCAL; HOSTED-UNVERIFIED | `scripts/ci_docker_preflight.py`, `.github/workflows/ci.yml` (job `tests`), `local/L1..L3,L7..L9`, `mutants/mutate_all_run.txt` (44/44 preflight mutants killed) | Image is `python:3.12-alpine`, not the literal `alpine:3` (D-1: owner confirmation needed). |
| R2 | Record digest or image ID | Assignment A | IMPLEMENTED; VERIFIED-LOCAL; HOSTED-UNVERIFIED | preflight report JSON (`local/L8_report.json`), artifact `docker-preflight` (`if: always()`, `if-no-files-found: error`) | The hosted artifact does not exist yet. |
| R3 | Nothing added to the D10 allowlist; gate strict | Assignment D10 | VERIFIED | sha256 and 34 entries unchanged; `scripts/ci_test_gate.py` unchanged (`local/G1_*`, section 13) | Gate still exits 1 locally on 15 sandbox-local failures, correctly (section 6). |
| R4 | AF_ALG: establish the invariant, test the production filter in a subprocess with control and filter-installed check, rename, no weakening, no silent skip | Assignment B | IMPLEMENTED; VERIFIED-LOCAL with a stated limit; HOSTED-UNVERIFIED | `tests/core/sandbox/test_seccomp.py` (19 passed, 1 skipped), mutation S01..S07 and earlier T1..T8 killed | Invariant: SECCOMP-ENFORCED (D-2). The production AF_ALG test **skips in the lab** because this lab kernel has no AF_ALG (verified: the unfiltered control already returns EAFNOSUPPORT). The hosted kernel has AF_ALG (the hosted baseline log shows AF_ALG reachable unfiltered, `api/logs/primary_tests.log:1460`), so it should discriminate there; **not yet observed**. |
| R5 | PRs into `sandbox-network-isolation/b01-base` run normal PR CI; keep `main` PR trigger and `integration/**` push | Assignment C | IMPLEMENTED; VERIFIED-LOCAL (config tests); HOSTED-UNVERIFIED | `pull_request.branches: [main, 'sandbox-network-isolation/b01-base']`, 29 config tests, mutants W01..W04 | See F12 (section 15): a PR event uses the workflow file of the merge ref. |
| R6 | Verify packet ownership under a PR event; no event-specific bypass | Assignment C | PARTIAL | local: the real workflow step executed under PR-style and push-style env (`tests/test_ci_workflow_config.py`); hosted: run 42501282719 (an unrelated branch into `main`) shows the step under a real `pull_request` event printing "not one of this manifest's declared packet branches ... skipping cleanly" (`api/final/job_pr_drift_ownership.log`) | The B03 branch is not a packet branch, so the step skips by design. A hosted PR-event run of the remediation or B03 branch does not exist and needs a PR into b01-base, which the assignment does not list as allowed (D-13). |
| R7 | Keep artifacts; add narrow remote mypy step for exactly the two B03 files | Assignment C | IMPLEMENTED; VERIFIED-LOCAL; HOSTED-UNVERIFIED | job `typecheck-b03` (mypy 2.4.0, pytest 9.2.0 pinned; default and `--strict`), `local/M3_*`, negative control `local/M2_*` | |
| R8 | B03 stays inert, no scope violations | Assignment B03 scope | VERIFIED | `git diff --quiet a887e148 -- core/ ...` (section 13); the B03 inertness test passes (224 passed in the guard file) | |
| R9 | Batch 5: B03 unit tests, `tests/core/sandbox`, full pytest, gate, DRIFT-01..15, mypy, import orders, mutation tests | Assignment batches | VERIFIED-LOCAL | section 13 | Full pytest: 49 failed, 2362 passed, 6 skipped, 9 xfailed; all 49 are sandbox-environmental (34 on the D10 list + 15 unlisted, identical set to the pre-review run and to the pristine PR head's environmental failures). |
| R10 | Independent review by a separate agent | Assignment (high-stakes check) | PARTIAL | `handoff-evidence/b03-ci-remediation-20261106/review/independent_review_report_b0a1143.md`: APPROVE WITH CONDITIONS on `b0a1143` | The follow-up commit `164a078` was **not** independently re-reviewed. |
| R11 | Evidence package, 15 items | Assignment | PARTIAL | section 13 table | Hosted-dependent items are INCOMPLETE. |
| R12 | Artifacts downloaded, inspected, hashed against GitHub digests | Assignment | INCOMPLETE | none | Needs a hosted run and an authenticated artifact download; the ambient `GH_TOKEN` is invalid. |
| R13 | Final report A to J, decision label | Assignment | OPEN | none | Must stay NO-GO / INCOMPLETE while R1/R2/R4/R5/R6/R7/R11/R12 lack hosted evidence. |
| R14 | Do not modify PR #86, merge, retarget, rerun/cancel runs, dispatch workflows | Assignment prohibitions | VERIFIED (not violated) | PR #86 still open at head `a887e148`, base `e2266603`, updated 2026-11-02 (`api/final/pr86_final.json`) | `mergeable_state` reads "unstable"; that is a side effect of the earlier evidence-branch push (runs on `integration/b03-ci-evidence-20261106`), not of this work. |
| R15 | Standing: answer in English; never print or store the token | Standing instructions | VERIFIED (not violated) | secret scan of the evidence directory: no token patterns (only GitHub's own masked `AUTHORIZATION: basic ***` lines in hosted logs) | |

## 6. Current Verified State

### VERIFIED (local lab, with the commands in section 13)

- The preflight fails closed at the right stage for: an absent image, an image without python3, an image missing `mkfifo`, an image whose `date` lacks nanoseconds, a failed digest run. It passes on a complete image. Real-daemon runs `local/L1..L3, L7..L9`.
- The A2 host-mount test (`test_a2_mount_namespace_does_not_see_a_host_mount_created_after_start`) failed as a non-root user without sudo (reviewer finding F1 reproduced: `local/R1`, exactly 1 failure) and now passes as a non-root user with passwordless sudo (`local/R2`: 101 passed, 1 skipped, 8 xfailed across `test_docker_backend.py` + `test_network_isolation_contract.py`), and fails loudly with an explicit message when neither root nor sudo is usable (`local/R3`).
- Full suite on the final code (`local/F4_*`): **49 failed, 2362 passed, 6 skipped, 9 xfailed in 220 s.** The 49 are exactly the failing set of the earlier branch run; none is new relative to the pristine PR head; 75 tests that failed on the pristine PR head pass (the 75 `test_docker_backend.py` failures). The 6 skips: 4 in `test_allowed_hosts.py` (needs a writable cgroup v1 memory controller), 1 `test_docker_backend.py:895` (needs gcc-multilib), 1 the production AF_ALG test (lab kernel has no AF_ALG).
- The D10 gate on that run exits 1 with exactly **15** failures not on the D10 list (8 in `tests/core/sandbox/test_namespace_backend.py`, 1 `tests/test_context_scope_security.py`, 2 `tests/test_module_factory_security.py`, 4 `tests/test_planner_worker.py`). They are environmental to the lab sandbox (namespace sandboxing, offline HuggingFace) and **pass on the hosted baseline**; they also fail on the pristine PR head in the lab (`local/B1`). **They must NOT be added to the D10 list.** The lab-only extended-allowlist run (`local/F3_*`) shows the gate exits 0 when only those fail; that run used a scratchpad copy and is not a repository change.
- The new skip-assertion step, executed for real on the F4 output: exit 0, prints "no Docker-prerequisite skips" (`local/F4_skip_step_*`).
- mypy on the two B03 files: default and `--strict` exit 0 (mypy 2.4.0, clean venv). Both import orders pass in fresh interpreters (3.12 and 3.13). DRIFT-01..15 all PASS. D10 list, gate script, `core/`, `requirements.txt`, both B03 files unchanged vs `a887e148`.
- Mutation testing of the final code over a scratch copy: **87/87 killed** (`mutants/mutate_all_run.txt`).
- Independent review of `b0a1143`: APPROVE WITH CONDITIONS (R10). Its findings F1 to F12 and their dispositions: section 10, D-14.

### IMPLEMENTED BUT NOT VERIFIED

- Everything on hosted CI (R1, R2, R4, R5, R6 for the B03 branch, R7). No GitHub run of the remediation branch exists.
- The follow-up commit `164a078` has not been independently re-reviewed.

### PROPOSED / DEFERRED

- DEFERRED: reviewer finding F8, a stale reference in `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md:113` to the removed test `test_af_alg_is_unreachable_on_this_host_regardless_of_seccomp`. It is a docs change and a "docs-only revision round" is a user-owned decision (D-15).
- PROPOSED (needs the owner): the image decision D-1; opening a PR into b01-base for the PR-event proof (D-13); pushing to `integration/**` (D-12).

### UNKNOWN (cannot be known without a hosted run; each would show up in the first hosted run)

See section 15, items U1 to U9.

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1`. Remote: `origin` (`https://github.com/1h0lde4/ocbrain-v4.1`).
- Local branch: `integration/b03-ci-remediation-20261106` (created from the PR #86 head).
- **Remote branch holding the transfer: `tmp/b03-ci-remediation-handoff-20261112`** (temporary; matches no CI push trigger). The local branch was pushed to it with an explicit refspec; **no `integration/b03-ci-remediation-20261106` exists on the remote.**
- Base branch (what PR #86 targets): `sandbox-network-isolation/b01-base` = `e2266603cf215c301af4a6b47124b44730d41f0f`.
- Fork point = PR #86 head: `a887e14881670fae2e4c6828a47a268c4a9d2296`, tree `771633dbd05fdd4d03c21f525d71ceb98e57f186`.
- Commits on top of the fork point, oldest first:
  1. `fc26681bd440f1e13693d10a541ea5f0fc630b34` (tree `42a1aaac...`) wip checkpoint
  2. `fd5240546b889341fd0285ec75205558ac93c068` (tree `912aefb3...`) preflight no-fallback test distinguishes fallback from the product default
  3. `be4b99dc346e45a28172d415c0cde938dc5171cd` (tree `6f5f81f6...`) required executables extended, classification ratchet
  4. `b0a1143d494a0afdeda07b0d2fd7ea439fed782c` (tree `846b39ae...`) `-rfEs`, regression test. **This is the commit the independent review covered.**
  5. **`164a078bc5c8820b0f12c45614db704d78dde78f`, tree `b6beea4087d17d98e2fb45adce158deb7919853b`: the transfer commit** (the implementation state being transferred; it addresses the review findings; verified locally, not on hosted CI, not re-reviewed).
- Documentation and evidence commits (no code), in order after the transfer commit `164a078`:
  1. `5d2ef7b80e1d694219bd87fddc26e665132536ca`: adds `handoff-evidence/b03-ci-remediation-20261106/` (101 files, with `SHA256SUMS`).
  2. `70cae67ed3addd9e836866d92fa90bab9d780c65`: force-adds four hosted job logs that `.gitignore` (`*.log`, `logs/`) had excluded: `api/logs/primary_tests.log`, `api/logs/primary_drift.log`, `api/final/job_pr_tests.log`, `api/final/job_pr_drift_ownership.log`. `.gitignore` itself is unchanged. Without them this handoff's citation of `api/logs/primary_tests.log:1460` would not resolve in a clone.
  3. The handoff commit: the commit that modifies `handoff.md` (its own SHA cannot be written inside the file it contains). Find it with `git log -1 --format=%H -- handoff.md`; it is the tip of `tmp/b03-ci-remediation-handoff-20261112`. **Verify with `git ls-remote origin refs/heads/tmp/b03-ci-remediation-handoff-20261112`**, and check the chain: `git merge-base --is-ancestor 164a078bc5c8820b0f12c45614db704d78dde78f <tip>` and that `git diff --name-only 164a078 <tip>` lists only `handoff.md` and files under `handoff-evidence/`.
- Working tree at handoff: clean after the handoff commits (nothing relevant is untracked).
- Ignored files: none relevant.
- Submodules: none.
- A `git bundle` of the final state was also sent to the user as an out-of-repository copy (a bundle covering the earliest checkpoint `fc26681`, sha256 `f66d17c0b11db4625c5562805e60ac1b7df9a653ba1cf9cb1feb1c946341b7f2`, was sent on 2026-11-08; the closing message of this session sends a newer one).
- PR #86 (do not touch): open, head `a887e148`, base `b01-base` `e2266603`, title "B03: capacity and IPv6 guard primitives (inert; INV-7, INV-8, TC-14)".
- Baseline hosted runs (before the remediation, on the PR head content, push on branch `integration/b03-ci-evidence-20261106`): run `42223596080` (head a887e148, conclusion failure) and run `42223622852` (head e8250924, failure). Tests job `127911372535`, drift job `127911372979`.

## 8. Active Files / Modified Files / Artifacts

Modified or added versus the PR head `a887e148` (code, 6 files):

| File | Why it matters |
|---|---|
| `.github/workflows/ci.yml` | Trigger; job-level `OCBRAIN_SANDBOX_DOCKER_IMAGE: python:3.12-alpine`; preflight step (exactly one command); `docker-preflight` artifact; `-rfEs`; the "Assert the Docker-backed tests ran" step after the gate; new job `typecheck-b03`. |
| `scripts/ci_docker_preflight.py` (new, stdlib only) | Stages `daemon`, `provision`, `identity`, `smoke` (tag run, digest run, executable lookup on the DockerBackend PATH, `--probe-capabilities`). Report schema `ocbrain.ci.docker-preflight/1`, written on failure too. Exit 0/1/2. |
| `tests/test_ci_docker_preflight.py` (new, 69 tests) | Fake `docker` executable on PATH; real-`sh` execution of the lookup and probe snippets. |
| `tests/test_ci_workflow_config.py` (new, 29 tests) | Pins triggers, no bypass, flags, the single-command preflight and gate, the executable list (two ratchets), the skip-assertion step (executed for real), mypy job, packet ownership under PR and push env. |
| `tests/core/sandbox/test_seccomp.py` | AF_ALG test replaced: invariant comment block; `_probe`/`_verdict` helpers; 5 production-filter and stand-in tests plus `TestProbeInterpretation`. |
| `tests/core/sandbox/test_docker_backend.py` | Only `test_a2_mount_namespace_...` and the new `_host_root_prefix()` helper: `sudo -n` when not root, loud failure when neither is possible, asserts the host really has the mount. |

Documentation and evidence added by the handoff commits: `handoff.md` (this file) and `handoff-evidence/b03-ci-remediation-20261106/` (`README.md` is the index; `SHA256SUMS` the manifest of the other 104 files; verify with `cd handoff-evidence/b03-ci-remediation-20261106 && sha256sum -c SHA256SUMS`). Note the CRLF warning git prints for `local/T1_test_suite_side_effect_config_diff.patch`: it is a captured diff of `config/*.toml` whose content has CRLF; if a checkout normalizes it, that one file's hash in `SHA256SUMS` may differ without any real change. Python scripts in the evidence directory carry a `.py.txt` suffix **on purpose**: the B03 inertness pin scans every `*.py` file in the repository for references to the guard module, and an evidence script that names it turned that test red.

Not stored in the repository (reproducible): the stand-in Docker rootfs tarball (`lab/mkrootfs.sh` builds it), virtualenvs, the scratch mutation tree.

## 9. Changes Made

- **Docker provisioning (A).** CI now provisions `python:3.12-alpine` in the job's own daemon via `scripts/ci_docker_preflight.py`, before pytest, from the same job-level variable pytest reads, and uploads the report. The script inspects first, otherwise pulls with a bounded number of attempts (default 3, no fallback), re-checks presence, reads the image id and the very `docker inspect --format {{index .RepoDigests 0}}` answer `DockerBackend._resolve_image_digest` asks for, then starts containers `--pull never --network none -e PATH=<DockerBackend's container PATH>` by tag and by RepoDigest, looks up every `--require-executable` on that PATH (a POSIX-sh lookup that rejects directories and builtins), and with `--probe-capabilities` exercises `date +%s%N` (>=19 digits), `sleep 0.01`, `head -c 1`. The workflow requires: python3 sh sleep true echo printenv yes head grep date mv rm cat ln mkdir mkfifo hostname readlink ls.
- **AF_ALG (B).** The invariant is seccomp-enforced (not a host property). The old host-property test is removed. New tests run the production `core.sandbox.backends._seccomp.apply_denylist()` in a subprocess with an unfiltered control, a `/proc/self/status` `Seccomp`/`Seccomp_filters` check and AF_UNIX/AF_INET controls; a kernel-independent test proves the argument filter matches value 38 using a stand-in errno; the production AF_ALG test skips only when the unfiltered control already returned EAFNOSUPPORT (a verified reason). No policy change.
- **Trigger (C).** `pull_request.branches` gains the exact name `sandbox-network-isolation/b01-base`; `main` and the `integration/**` push trigger are kept; `permissions: contents: read` unchanged; no `workflow_dispatch`, no `continue-on-error`, no job-level `if`.
- **`-rfEs`.** `-rs` alone replaces pytest's default `-rfE`, the FAILED lines vanish and the unchanged gate fails with "N failed but 0 distinct FAILED node ID(s)". The workflow uses `-rfEs` (a comment and a regression test explain it).
- **Skip assertion.** A step after the gate fails the job if pytest reports a SKIPPED line whose reason is "requires a reachable Docker daemon" or "requires the test image" (the preflight has just proven both).
- **mypy job.** `typecheck-b03`: Python 3.12, `mypy==2.4.0 pytest==9.2.0`, `MYPYPATH=. mypy [--strict] --explicit-package-bases --follow-imports=silent <the two B03 files>`; both exit codes are kept and both must be 0; output uploaded as artifact `mypy-b03`.
- No schema, governance, event or architecture change. No change under `core/`.

## 10. Decisions & Rationale

Decision ledger. "Reopen" = the condition under which the decision may be revisited.

| ID | Decision | Status | Authority / rationale | Reopen condition |
|---|---|---|---|---|
| D-1 | CI image is `python:3.12-alpine`, not the literal `alpine:3`. | **PROPOSED; needs owner confirmation.** | Bare `alpine:3` has no python3; with it 17 tests fail instead of 75 (`local/L6`); about 15 tests launch `python3` in the container (note in `test_network_isolation_contract.py`). The assignment asked for "the exact image reference"; the exact reference needed is not the product default. | The owner names another image, or the hosted preflight shows a missing executable or applet feature. |
| D-2 | AF_ALG invariant is seccomp-enforced, host-level reachability is only the control. | ACCEPTED (assignment B: "establish the invariant first") | Verified: after `apply_denylist()`, `socket(AF_ALG)` fails EAFNOSUPPORT (97) and `socket(AF_VSOCK)` EPERM (1). The hosted baseline failure proves the host kernel has AF_ALG. | A kernel/libseccomp change that alters the errno table. |
| D-3 | Preflight is a separate fail-closed stdlib script with its own tests, not inline YAML. | ACCEPTED | Testable; fail-closed; report on failure. | n/a |
| D-4 | No fallback image, mocks or skips; nothing added to D10. | ACCEPTED (assignment) | Mutation-tested (P04, P10-class mutants killed). | A user instruction. |
| D-5 | The preflight step and the gate step are each exactly one command. | ACCEPTED | Reviewer F6: appending `exit 0`, `; true`, `set +e` otherwise neuters them. | n/a |
| D-6 | `-rfEs` (not `-rs`). | ACCEPTED | See section 9. | The gate's parser changes (it must not be changed silently). |
| D-7 | Executables are resolved on the PATH DockerBackend gives every container, and a container is also started from the resolved RepoDigest. | ACCEPTED | Reviewer F2, F3; verified `docker_backend.py:249-252` sets PATH explicitly. | n/a |
| D-8 | Capability probes (`--probe-capabilities`) in addition to presence checks. | ACCEPTED | Reviewer F4: presence of an applet does not prove `date +%s%N`, fractional `sleep`, `head -c`. Fail-closed if the hosted busybox lacks one (that would be a real finding). | The probes prove wrong on the hosted image. |
| D-9 | `mkfifo` required; second ratchet derives commands from `sh -c` scripts. | ACCEPTED | Reviewer F5; found independently with a real minimal image too. | n/a |
| D-10 | A skip-assertion step after the gate. | ACCEPTED | Reviewer F9: a slow daemon at import time would skip the whole Docker suite and still pass the gate. | n/a |
| D-11 | The A2 host-mount test uses `sudo -n` when not root and fails (never skips) if neither is possible. | ACCEPTED | Reproduced as a non-root user (`local/R1`); a hosted runner is non-root with passwordless sudo (reasoned, not yet observed). It is a test-side privilege assumption, not a change to what the test asserts. | If the hosted runner has no passwordless sudo, the test will fail loudly: then decide with the owner (never allowlist). |
| D-12 | Do **not** push to `integration/b03-ci-remediation-20261106` in this session; use `tmp/b03-ci-remediation-handoff-20261112`. | ACCEPTED for this session | The user's 2026-11-12 instruction said "a temporary branch". The assignment allows the integration push, but starting CI was not asked for in that instruction. | The owner confirms the CI push (it is allowed by the assignment). |
| D-13 | Do not open a PR into b01-base for the PR-event proof. | OPEN (needs the owner) | The assignment does not list it as allowed; it touches PR state. | The owner authorizes it, or a different route to a PR-event proof is chosen. |
| D-14 | Dispositions of the independent review (`b0a1143`): F1 fixed (D-11); F2 fixed (D-7); F3 fixed (D-7); F4 fixed (D-8); F5 fixed (D-9); F6 fixed (D-5); F7 fixed (tests for exact exec-check argv, `=`-form names, timeouts, option-like image); F8 **deferred** (D-15); F9 fixed (D-10); F10 fixed (duplicate removed); F11 fixed except two NITs (pytest pinned to 9.2.0; an empty PATH component and `--image=-foo` handled: option-like image now a usage error); F12 **open** (U9). | ACCEPTED | `review/independent_review_report_b0a1143.md` | A re-review disagrees. |
| D-15 | Do not edit `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md:113` (stale reference to the removed test). | DEFERRED | The docs-only revision round is user-owned; the assignment allowed only minimal CI/test changes. | The owner opens the docs round. |
| D-16 | `handoff.md` at the repository root is overwritten with version 4; version 3 stays in git history (`1b829fc`). | ACCEPTED | PROJECT_INSTRUCTIONS 18.4.9 reads `handoff.md` on the branch; version 3's workstreams are closed. | n/a |
| D-17 | Evidence is committed under `handoff-evidence/b03-ci-remediation-20261106/`, outside `docs/`, `core/`, `tests/`, `scripts/`, with python scripts as `.py.txt`. | ACCEPTED | The scratchpad is ephemeral; the guard-inertness test scans `*.py`. | The owner wants the evidence elsewhere. |
| D-18 | The final report decision label stays NO-GO / INCOMPLETE until the hosted items exist. | ACCEPTED (assignment: "any missing item means NO-GO") | | All 15 items demonstrated. |

## 11. Investigation Already Performed

| Area | Inspected | Result | Evidence | Revisit trigger |
|---|---|---|---|---|
| Hosted baseline | Runs 42223596080 / 42223622852, jobs, logs | 76 failed, 2213 passed, 27 skipped, 1 xfailed; 75 `no such object: alpine:3` + the AF_ALG test; the baseline log had no `-rs`, so hosted skip reasons are unknown | `api/logs/primary_tests.log`, `api/*.json` | A new hosted run |
| Docker image prerequisite | `DockerBackend._resolve_image_digest`, test files | Two layers: image absent from the daemon (75) and image content (python3 and the executables the tests run) | `local/L6`, `local/L7` | Image change |
| In-container executables | AST/word/shell-command scans of both Docker test files; real minimal image | The 19 names in the workflow list (`mkfifo` was missing at b0a1143) | two ratchets in `test_ci_workflow_config.py` | A test file change |
| Seccomp invariant | `_seccomp.py`, kernel behaviour | Seccomp-enforced; lab kernel lacks AF_ALG (unfiltered `socket(AF_ALG)` returns 97) | `tests/core/sandbox/test_seccomp.py` | Kernel change |
| Gate parsing | `scripts/ci_test_gate.py` | Parses FAILED/ERROR from the short summary; `-r` replaces the default; needs `-rfEs` | `local/F1a`, `local/F2a` | Gate change |
| Hosted runner facts | Baseline logs | `ubuntu-latest` = ubuntu-26.04, Python 3.12.16; AF_ALG reachable on the host | `api/logs/*` | Runner image change |
| PR-event behaviour | Run 42501282719 | Packet ownership step under a real `pull_request` event skips cleanly for a non-packet branch | `api/final/*` | A B03 PR-event run |
| Non-root Docker tests | Real daemon as `runner` (uid 1001) | 1 failure without sudo (A2), 0 with passwordless sudo | `local/R1..R3` | Hosted run |
| Mutation testing | 87 mutants on a scratch copy | 87/87 killed | `mutants/mutate_all_run.txt` | Any change to the three files |
| **Not investigated** | The hosted behaviour of busybox in `python:3.12-alpine`; Docker Hub rate limits from shared runner IPs; whether the hosted runner has 32-bit toolchains (decides whether `test_a9_...` runs); the contract suite under a real hosted daemon. | UNKNOWN | | First hosted run |

## 12. Failed Attempts / Dead Ends

| Approach | Result | Cause / evidence | Retry? |
|---|---|---|---|
| Using the ambient GitHub token (`GH_TOKEN`/`GITHUB_TOKEN`) for API calls | Invalid ("The token in GH_TOKEN is invalid"). The token pasted by the user earlier was blocked by the permission layer when put in a command line (credential-leak rule). | `gh auth status`; do not work around the block | No. Only unauthenticated reads work (public repo). **Git pushes work** through the session's git proxy without any token handling by the session (dry-run and the real push succeeded). |
| Authenticated artifact download | Not possible without a valid token | | After the owner provides working access |
| `-rs` instead of `-rfEs` | Gate reported "0 distinct FAILED node ID(s)" | `local/F1a`, `local/F2a` | No |
| Preflight test image `alpine:3` in the tests' IMAGE constant | A mutant "fallback to alpine:3" survived because `alpine:3` is the product default | fixed by using `python:3.12-alpine` in the tests | No |
| Workflow mutant: `mypy --strict` replaced by an `echo` that printed the same banner | Survived | fixed: tests assert the two exact invocation lines and the exact FILES string | No |
| A 21 GB host-rootfs import as the stand-in image | Filled the disk | replaced by a 78 MB minimal rootfs | No |
| Stand-in images missing libs or `command -v` builtins | The preflight correctly caught the defective images | `local/L2a`, `local/L3a` | No |
| Evidence Python scripts named `*.py` in the repository | Turned `test_nothing_in_the_repository_imports_the_guard_module_yet` red | renamed `.py.txt` (D-17) | No |
| Independent reviewer agent | Three attempts hit HTTP 429 (5-hour limit); the fourth (a resume) completed | | If the limit recurs, record the review as INCOMPLETE rather than substituting a self-review |
| The container resets unpredictably | Wiped uncommitted files and the scratchpad once | recovered from the transcript, re-ran everything; nothing from the lost run is cited as evidence | Commit early (done) |

## 13. Verification Evidence

All local lab unless stated. Directory: `handoff-evidence/b03-ci-remediation-20261106/`. Code under test = `164a078` unless a row says otherwise.

| Check | Command (cwd = repo root, Python 3.12.3 venv with `requirements.txt` unless noted) | Result |
|---|---|---|
| CI workflow config tests | `python -m pytest tests/test_ci_workflow_config.py -q` | 29 passed |
| Preflight tests | `python -m pytest tests/test_ci_docker_preflight.py -q` | 69 passed |
| Gate tests (unchanged file) | `python -m pytest tests/test_ci_test_gate.py -q` | 67 passed |
| Seccomp tests | `python -m pytest tests/core/sandbox/test_seccomp.py -q -rs` | 19 passed, 1 skipped (AF_ALG production test: lab kernel has no AF_ALG, verified) |
| B03 guard unit tests | `python -m pytest tests/core/sandbox/test_sandbox_network_guards.py -q` | 224 passed (after the evidence-script rename; one run failed with an evidence `.py` present, see section 12) |
| Combined repo-scanning check | the five files above in one run | 408 passed, 1 skipped |
| Docker tests, root, final code, rebuilt stand-in image | inside `run_final.sh` (full run) | `test_docker_backend.py` 0 failures in F4 |
| Docker tests, non-root with passwordless sudo | `su runner -c "cd /home/runner/work && OCBRAIN_SANDBOX_DOCKER_IMAGE=python:3.12-alpine pytest tests/core/sandbox/test_docker_backend.py tests/core/sandbox/test_network_isolation_contract.py -q -rfEs"` | 101 passed, 1 skipped, 8 xfailed in 88.8 s (`local/R2`) |
| A2 test, non-root without sudo | same with `-k test_a2_mount_namespace` | 1 failed, loud precondition message (`local/R3`); with the previous code `local/R1` shows the bare-mount failure |
| Full suite | `scripts/run_final.sh` (= `pytest tests/ -q --tb=short -rfEs`, `OCBRAIN_SANDBOX_DOCKER_IMAGE=python:3.12-alpine`, `HF_HUB_OFFLINE=1`) | **49 failed, 2362 passed, 6 skipped, 9 xfailed, 220 s**, exit 1 (`local/F4_full_pytest_*`) |
| Gate on that run, D10 unchanged | `python3 scripts/ci_test_gate.py --output ... --exit-code-file ... --allowlist docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt` | exit 1: exactly 15 failures not on the list (all sandbox-local); the same 15 as `scripts/unlisted15.txt` |
| Failing-set comparison | `local/F4_failing_set_comparison.txt` | F4 == earlier branch run F1 (49 each); 0 newly failing vs the pristine PR head; 75 fixed |
| Skip-assertion step | the step's real `run:` block against `F4_full_pytest_output.txt` | exit 0, "no Docker-prerequisite skips" (`local/F4_skip_step_*`) |
| mypy | the workflow step logic in a clean venv (mypy 2.4.0, pytest 9.2.0) | default 0, strict 0 (`local/M3_*`); negative control exits 1 (`local/M2_*`) |
| Import orders | fresh interpreters, 3.12 and 3.13, both orders | all OK (`local/I2`) |
| Drift | `python scripts/check_drift.py --out ...` | DRIFT-01..15 PASS, exit 0 (`local/D2_*`) |
| D10 and scope | `git diff --quiet a887e148 -- docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt scripts/ci_test_gate.py core/ requirements.txt core/sandbox/backends/_sandbox_network.py tests/core/sandbox/test_sandbox_network_guards.py`; `sha256sum` of the list | no difference; sha256 `51caa5d6d79c790162d1d97095a00c94127b337c26ad5d420ce400e47f158316`; 34 entries |
| Real-daemon preflight | `python3 scripts/ci_docker_preflight.py --image ... --probe-capabilities --require-executable ...` | `L8` PASS on the stand-in; `L7` fails naming `mkfifo`; `L9` fails naming `date +%s%N`; `L1` absent image fails at provision; `L3`/`L6` no python3 |
| Mutation | `python mutate_all.py <repo> <scratch> <python>` (the file is stored as `.py.txt`) | 87/87 killed |
| Secret scan of the evidence directory | pattern grep (tokens, keys, `Authorization`) | none (only GitHub-masked `AUTHORIZATION: basic ***`) |
| Remote verification | `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1 refs/heads/tmp/b03-ci-remediation-handoff-20261112` | tip equals the local transfer; see section 7 |

Hosted: **no run of the remediation branch.** Baseline hosted runs only (section 7).

Evidence-package item status (the assignment's 15): 1 summary: this file + the final report (OPEN); 2 failure classification: section 6/11 (DONE, local+hosted baseline); 3 before/after workflow config: `git diff a887e148..HEAD -- .github/workflows/ci.yml` (DONE); 4 Docker logs and image identity: local only, hosted INCOMPLETE; 5 full pytest output: local F4 DONE, hosted INCOMPLETE; 6 AF_ALG evidence: local DONE, hosted INCOMPLETE; 7 mypy: local DONE, hosted INCOMPLETE; 8 import-cycle: DONE; 9 drift: DONE local, hosted INCOMPLETE; 10 D10 output and unchanged comparison: DONE; 11 artifact inventory + SHA-256: local manifest DONE (`SHA256SUMS`), hosted artifacts INCOMPLETE; 12 commit and tree SHA per run: section 7 for commits, hosted runs INCOMPLETE; 13 Actions run IDs: baseline only, remediation INCOMPLETE; 14 PR #86 state: DONE (verified 2026-11-11); 15 limitations: section 15.

## 14. Environment / Tooling Assumptions

- The lab (ephemeral, resets unpredictably): Linux 6.18 container, Python 3.12.3 venv with `requirements.txt` (`$SCRATCHPAD/venv312`), a clean venv with only `mypy==2.4.0` and `pytest==9.2.0` for the mypy check, Python 3.13 for the import-order check, a local `containerd` + `dockerd` 29.9.2 started with `lab/up.sh` (start containerd first and confirm its socket, kill leftovers first with `pkill -9 dockerd; pkill -9 containerd`). The registry is unreachable from the lab, so the CI image is simulated by `lab/mkrootfs.sh` (python 3.12 from the host + GNU coreutils for the listed tools, imported and tagged `python:3.12-alpine` and `ocbrain-test/base:local`). **GNU coreutils, not busybox: the hosted image's busybox behaviour is not tested by anything in the lab.**
- Non-root lab user `runner` (uid 1001, docker group, optional passwordless sudo via `/etc/sudoers.d/runner-lab`, which was removed afterwards); `chmod 711` was applied to the `/tmp/claude-0...` parents so `runner` can execute the venv. These are lab-only and not part of the repository.
- Hosted runner facts (from the baseline logs): `ubuntu-latest` = ubuntu-26.04, Python 3.12.16, dependencies from `requirements.txt` (pytest unpinned there; the mypy job pins pytest 9.2.0).
- The full test suite rewrites tracked files `config/models.toml`, `config/settings.toml`, `config/sources.toml` as a side effect (a pre-existing hygiene issue, `local/T1_*`). **After any full run: `git checkout -- config/`.** None of it is in any commit.
- `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` is used in the lab because huggingface.co is blocked there; this is why the 15 sandbox-local failures differ from the hosted baseline.
- Commit attribution used: commits end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01RzVx1NSzXF1YokR8a8PPiA`; PR bodies end with `🤖 Generated with [Claude Code](https://claude.com/claude-code)` plus the session URL.
- Secrets: none stored here. The GitHub API needs a valid token for artifact downloads; the ambient one is invalid; git pushes work without one through the session's git proxy.

## 15. Unresolved Questions / Risks / Blockers

| ID | Issue | Evidence | Disposition / required verification | Can work continue without it? |
|---|---|---|---|---|
| U1 | **Image decision** (D-1): `python:3.12-alpine` instead of the literal `alpine:3`. | `local/L6` | Owner confirmation. | Yes, but the report must flag it. |
| U2 | Hosted pull, digest and busybox features (`date +%s%N`, fractional `sleep`, `head -c`, `mkfifo`, `hostname`, `readlink`) in `python:3.12-alpine`. | The probes and required list are fail-closed, but never run against the real image. | First hosted run. A failure here is a real finding, **not** an allowlist item. | Yes. |
| U3 | The contract suite (`test_network_isolation_contract.py`, 8 strict xfails) goes from SKIP to RUN for the first time on hosted CI; a strict xfail that XPASSes, or an ERROR in its module-scoped warm-up fixture, would fail the gate. | Locally with a stand-in image: 5 passed, 8 xfailed | First hosted run. | Yes. |
| U4 | `test_a9_...` (about `test_docker_backend.py:895`) hardcodes the image `ocbrain-test/base:local`. It is gated by a 32-bit toolchain (`gcc-multilib`). The baseline log had no `-rs`, so it is unknown whether it skips on hosted CI; if the runner has a 32-bit toolchain it would fail with "no such object: ocbrain-test/base:local" (not provisioned). | | First hosted `-rs` output. | Yes. |
| U5 | Docker Hub rate limits for `docker pull python:3.12-alpine` from shared runner IPs; 3 attempts 5 s apart is a short window. Fail-closed but possibly flaky. | | Observe; if it flakes, a registry mirror or pinned digest decision is the owner's. | Yes. |
| U6 | The hosted runner is assumed non-root with passwordless sudo (D-11). | reasoned | First hosted run; if wrong, A2 fails loudly. | Yes. |
| U7 | The production AF_ALG test has not been observed discriminating (the lab kernel lacks AF_ALG). The hosted kernel has AF_ALG. | `api/logs/primary_tests.log:1460` | First hosted run (`-rs` shows whether it ran). | Yes. |
| U8 | The independent review did not cover `164a078`. | | Re-run an independent reviewer on `git diff b0a1143..164a078` (and on this handoff's claims if desired). If the 5-hour limit recurs, record INCOMPLETE. | Yes. |
| U9 | **F12:** a `pull_request` event runs the workflow file from the merge ref. The new trigger only affects PR #86 once this `ci.yml` is in PR #86's head or in `b01-base`. Pushing the remediation branch gives CI only through the `integration/**` push trigger. | reviewer F12 | The owner decides how the CI change reaches `b01-base` (merge of the remediation branch is prohibited for this session). | Yes. |
| U10 | The PR-event proof for the B03 branch (R6) needs a PR into b01-base. | | D-13. | Yes, with R6 stated PARTIAL. |
| U11 | Authenticated artifact download and hashing against GitHub digests. | the ambient token is invalid | Needs a hosted run and working access. | No for R12. |
| U12 | Stale doc reference (reviewer F8). | `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md:113` | D-15. | Yes. |
| U13 | The 15 sandbox-local failures are not on D10 and would fail the gate in the lab; they pass on hosted CI. If one of them fails on the first hosted run it is a product/test issue to triage, **not** an allowlist item. | `local/F2`, `scripts/unlisted15.txt` | Hosted run. | Yes. |
| U14 | PR #86 `mergeable_state` is "unstable" because of runs on the evidence branch that PR #86's commits ran on (a side effect of an earlier push, not of this work). | `api/final/pr86_final.json` | Owner awareness. | Yes. |
| U15 | The verbatim original assignment text is missing from this transfer (section 2). | | The user attaches it. | Yes, but the transfer cannot be marked READY. |
| U16 | The user's 2026-11-12 instruction was interpreted (section 3, item 4). | | Confirm. | Yes. |

## 16. Relevant Information / References

- Governing: `PROJECT_INSTRUCTIONS.md` (project knowledge; sections 0, 14, 16, 18.4.8 to 18.4.11, 23, 24). Handoff procedure: 18.4.8.11. Closure discipline: 16.5 and 24.2 ("fixed" and "verified" are distinct; a deferral is not a closure).
- Code: `core/sandbox/backends/docker_backend.py` (`_resolve_image_digest`, `_build_container_env` which sets `PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, `_build_create_args`); `core/sandbox/backends/_seccomp.py` (`apply_denylist`, the denied-socket-family table: AF_ALG -> EAFNOSUPPORT, AF_VSOCK -> EPERM); `scripts/ci_test_gate.py` + `docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt`; `scripts/check_drift.py`; `scripts/check_packet_ownership.py` + `docs/architecture/h2_packet_ownership.json`.
- Tests: `tests/core/sandbox/test_network_isolation_contract.py` (8 strict-xfail tests behind a `needs_docker` gate; note "image must contain python3"); `tests/core/sandbox/test_sandbox_network_guards.py` (the B03 inertness pin scans all `*.py` files).
- GitHub: PR #86; baseline runs 42223596080, 42223622852; tests job 127911372535; drift job 127911372979; unrelated PR-event run 42501282719 (tests job 128794370306, drift/ownership job 128794370647).
- The reconciliation document referenced by the B03 acceptance: `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`.
- Cautions: the suite rewrites `config/*.toml` (restore with `git checkout -- config/`); never put an evidence `.py` file in the repository tree; do not run the full suite carelessly (about 4 minutes, needs the Docker lab for the Docker tests); do not change the D10 list or the gate.

## 17. Next Steps

In execution order. Steps marked OWNER need a user decision first.

1. **Verify** the transfer (section 18). Expected: the tip of `tmp/b03-ci-remediation-handoff-20261112` contains `164a078` and this file; the local tree is clean.
2. **OWNER (D-12): authorize the CI push.** The assignment already allows pushing the dedicated branch "provided this does not modify PR #86"; the user's last instruction named only a temporary branch, so confirm first. Then: `git push origin integration/b03-ci-remediation-20261106` from this state (it matches the `integration/**` push trigger and starts the `CI` workflow). Do not rerun or cancel anything, do not use `workflow_dispatch`, do not touch PR #86.
3. **Observe the first hosted run(s)** (unauthenticated reads work for run/job metadata and logs: `https://api.github.com/repos/1h0lde4/ocbrain-v4.1/actions/runs?branch=integration/b03-ci-remediation-20261106`). Record the run IDs and head/tree SHAs. Read the `-rfEs` output for: the Docker preflight step (image id, resolved digest, probes), every SKIPPED reason (U4), the 8 contract tests (U3), the A2 test (U6), the AF_ALG tests (U7), and whether the gate passes. Anything red that is not on D10 is **triaged, never allowlisted**.
4. If the hosted run shows a real defect, fix it minimally on the work branch (tests/CI only; no `core/`), re-run the local verification of section 13, commit, push the same branch. Keep a decision-ledger entry per change.
5. **Download the artifacts** (`drift-report`, `pytest-output`, `docker-preflight`, `mypy-b03`), inspect them, and hash them against GitHub's digests. This needs a valid token (U11): ask the owner for working access; do not print or store it.
6. Re-run the independent review on `b0a1143..164a078` and any later commits (U8) using a fresh agent that has not seen the work; record INCOMPLETE if the agent is unavailable.
7. **OWNER (D-13): the PR-event proof.** Either obtain authorization to open a PR into `sandbox-network-isolation/b01-base` from the remediation branch (not to merge it), or state R6 as PARTIAL with run 42501282719 as indirect context.
8. Assemble the 15-item evidence package (outside the repo, plus the SHA-256 manifest) and deliver the final report A to J with SendUserFile. The decision label stays NO-GO / INCOMPLETE unless every item is demonstrated, **including the hosted ones**. State the container-reset incident and that the pre-reset evidence was regenerated, the image decision (U1), and F8/F12 (U9, U12).
9. Do **not** merge, close or retarget anything. The merge/hold decision for PR #86 and the route by which the CI change reaches `b01-base` (U9) are the owner's.

## 18. Resume Instructions

First actions of the next session:

1. Read `PROJECT_INSTRUCTIONS.md` and this file completely.
2. Verify the branch and the transfer commit: `git fetch origin tmp/b03-ci-remediation-handoff-20261112`; `git rev-parse FETCH_HEAD`; `git merge-base --is-ancestor 164a078bc5c8820b0f12c45614db704d78dde78f FETCH_HEAD && echo ok`; `git cat-file -t 164a078bc5c8820b0f12c45614db704d78dde78f`; check `git rev-parse 164a078^{tree}` = `b6beea4087d17d98e2fb45adce158deb7919853b`.
3. Verify the remote with an unauthenticated read: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1 'refs/heads/tmp/*' 'refs/heads/integration/b03-*' 'refs/heads/sandbox-network-isolation/b03-capacity-ipv6-guards'` (expected: the temp branch present; **no** `integration/b03-ci-remediation-20261106`; the PR #86 head still `a887e148`).
4. Verify PR #86 is still open with head `a887e148` and base `e2266603`: `curl -sS https://api.github.com/repos/1h0lde4/ocbrain-v4.1/pulls/86`.
5. Verify the protected files against this handoff (section 13, "D10 and scope" command) and `sha256sum -c handoff-evidence/b03-ci-remediation-20261106/SHA256SUMS`.
6. Resolve any mismatch before changing anything. Then start from step 2 of section 17 only after the owner confirms (or, if the owner has already confirmed, from step 2), and do not redo the local verification unless the code changed.

## 19. Transfer Status

**TRANSFER INCOMPLETE — REQUIRED INFORMATION MISSING**

Reason, exactly one: the verbatim text of the original assignment attachment is not available to this session (section 2, U15). Everything else the completeness gate requires is satisfied: the implementation checkpoint `164a078` is committed and pushed to `tmp/b03-ci-remediation-handoff-20261112` and the remote tip was verified; this file and the evidence directory are committed and pushed; requirement, decision and investigation ledgers, failed attempts, verification evidence, environment assumptions and an exact next action are recorded; no material work exists only in the local working tree. The status becomes TRANSFER READY when the user attaches the original assignment text (replace section 2 with it and compare against section 5). Separately, and independent of this status: **the remediation itself is not complete and has no hosted-CI evidence.**
