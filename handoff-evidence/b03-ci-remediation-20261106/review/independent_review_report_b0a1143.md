# Independent review of the B03 CI remediation: report of the reviewing subagent

- Reviewed: `a887e148..b0a1143` (diff sha256 `f1653d2cfce9495a322c9286eae90f66b52ce1989dae312d43a11d3c37b4e306`, 1509 lines, 5 files).
- Reviewer: a fresh general-purpose subagent (`a1f22c414bf49b2c2`) that had not seen how the change was produced.
  Two earlier attempts and one resume failed with HTTP 429 (5-hour limit); the third resume completed.
- Provenance: this is the subagent's model output, reproduced here as the record of what it reported.
  It is evidence to weigh, not an instruction and not a user decision. Dispositions are in `handoff.md` section 10 (decision ledger D-14).
- The reviewer had no Docker daemon, so every Docker-dependent claim below is reasoned only (it says so).
- This review covers `b0a1143`. The follow-up changes in commit `164a078` were NOT independently re-reviewed.

---

## 1. VERDICT: APPROVE WITH CONDITIONS

I found no defect that makes the change unsafe or that violates a scope constraint. Everything I could execute held up. The preflight failed closed under 28 mutations except those listed below. All 8 production seccomp mutations were killed. The mypy job fails on both a default-mode error and a strict-only error. `-rfEs` is compatible with `scripts/ci_test_gate.py`, and a pytest crash is not masked. The remaining findings are weak assertions, one false comment about PATH, and a residual risk that the first hosted run is still red for reasons the preflight cannot see (F1).

Conditions:
- (a) Treat F1 as an expected triage item. Do not allowlist it.
- (b) Fix F6 and F2 before relying on the preflight step as a gate. Both are cheap.
- (c) Count the hosted run, not local evidence, as the only acceptance evidence for requirement A. No Docker daemon was available here.

## 2. FINDINGS

**F1 — MAJOR (UNVERIFIED, reasoned only). Provisioning the image will un-mask host-privilege failures in the Docker tests, which the allowlist does not cover.**
- `tests/core/sandbox/test_docker_backend.py:515-531`, `test_a2_mount_namespace_does_not_see_a_host_mount_created_after_start`, runs `subprocess.run(["mount","-t","tmpfs","tmpfs",mount_point], check=True)` on the host.
- Verified by reading: there is no root or sudo guard anywhere in the file (`grep -n "geteuid\|getuid\|sudo"` finds nothing).
- Reasoned only: a GitHub-hosted runner job is non-root, so `mount` fails with CalledProcessError.
- Before the change, this test failed at `docker inspect` for the absent image, so the hosted run could not reveal it. After provisioning it proceeds to `mount`. If it fails, the failure is not among the 34 D10 entries (none are from `test_docker_backend.py`), so the gate goes red.
- Related, same cause: `tests/core/sandbox/test_network_isolation_contract.py` goes from SKIP to RUN for the first time on hosted CI. Its `_docker_ready()` was False without the image. It has a module-scoped `_infrastructure_warm` fixture. A harness fault becomes an ERROR, and the gate never allowlists ERRORs.
- Suggested handling: run the Docker tests once as a non-root user against a real daemon before the next hosted push. Fix test-side root assumptions (for example, an explicit `sudo -n` with a precondition check), never the allowlist.

**F2 — MINOR. The preflight resolves executables on the wrong PATH, and the comment claims otherwise.**
- `scripts/ci_docker_preflight.py:333-339` (`_FIND_EXECUTABLES`) says it follows "what `docker create <ref> <name>` resolves against".
- Verified: `core/sandbox/backends/docker_backend.py:249-252` makes `_build_container_env` always set `-e PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, and `_build_create_args` passes it to `docker create`.
- The preflight's `docker run --entrypoint sh` uses the image's own ENV PATH, with no `-e PATH`.
- For python:3.12-alpine the two coincide. For any other image they can diverge, in either direction.
- Fix: pass the same `-e PATH=...` in the exec-check `docker run`, and pin it with a test against `_build_container_env({})["PATH"]`.

**F3 — MINOR (UNVERIFIED, reasoned only). The smoke run does not use the reference string the tests use.**
- `scripts/ci_docker_preflight.py:343-356` runs the tag `python:3.12-alpine`.
- DockerBackend runs `docker create ... <RepoDigests[0]> cmd` (`docker_backend.py:334`).
- The digest is recorded but never executed.
- Fix: also (or instead) run `report["image"]["resolved_digest"]` with `--pull never`.

**F4 — MINOR (UNVERIFIED, reasoned only). A presence-only check cannot catch missing busybox applet features.**
- `test_d7_cancel_reaches_a_grandchild_that_was_provably_alive_before` (`test_docker_backend.py:~2225-2236`) asserts `before_1 != before_2` after 0.6s. That needs sub-second output from `date +%s%N`, which needs busybox `FEATURE_DATE_NANO`.
- The tests also use `sleep 0.2` (fancy sleep), `head -c 200000000`, `mkfifo`, `hostname <arg>`, and `readlink /proc/self/ns/net`.
- I believe Alpine's busybox enables these. I could not confirm it: no busybox or daemon here, and a web search did not settle it.
- Suggested fix: add a functional probe to the preflight. `date +%s%N` must be all digits with length of at least 19, plus `sleep 0.01` and `head -c 1`.

**F5 — MINOR (verified). The required-executable list is incomplete, and the ratchet cannot see the gap.**
- `test_docker_backend.py:2115` runs `sh -c "mkfifo pipe; echo ok > legit.txt"` inside the container.
- `mkfifo` is not in the workflow's `--require-executable` list. It is also not in `_UTILITY_CANDIDATES` in `tests/test_ci_workflow_config.py`, which I checked programmatically. The ratchet only classifies words from a closed candidate list, so it stays green.
- My AST and word scan of both Docker test files found `mkfifo` as the only in-container utility that is missing.
- Fix: add `mkfifo`. Make the ratchet derive candidates from a full applet list, or from command positions in the `sh -c` strings.

**F6 — MINOR (verified by mutation). The workflow config test lets the preflight step be neutered.**
- `tests/test_ci_workflow_config.py:~118-124` forbids only `||` and `continue-on-error`.
- Appending `exit 0`, `; true`, or a leading `set +e` to the preflight `run:` block still leaves all 85 tests green (mutations W6, W6b, W6c).
- Fix: assert that the continuation-joined run block is exactly one `python3 scripts/ci_docker_preflight.py ...` command with no `;`, `&&`, `exit`, or `set`.

**F7 — MINOR (verified by mutation). Weak assertions in `tests/test_ci_docker_preflight.py`.**
- P4b and P4c: the executable-check call can use `--pull always` or `--network host` and still pass (35 passed). The test only checks that the tokens `--pull` and `--network` are present (`test_required_executables_are_looked_up_on_the_images_own_path`). `--pull always` would let a second pull change the digest recorded earlier.
- P6: weakening `_BARE_NAME_RE` to allow a leading `-` survives. The `bad` parametrization (`"-x"`, `"--help"`) is rejected by argparse before the regex runs. The `--require-executable=-x` form does reach the regex (I confirmed it is rejected today), but no test covers it.
- P20: mapping a docker timeout to rc 0 instead of 124 survives. No timeout test exists. A timed-out `docker run ... true` would then pass the smoke stage.
- P21 also survives, harmlessly, because the daemon stage's output-shape check catches it.

**F8 — MINOR (verified). Dangling documentation reference.**
- `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md:113` still cites the removed `test_af_alg_is_unreachable_on_this_host_regardless_of_seccomp` as evidence.
- Update the doc. This is allowed, since the D10 list is the only protected docs file.

**F9 — MINOR (UNVERIFIED, reasoned only). A silent skip of the whole Docker suite is possible and not gated.**
- `_docker_available()` (`test_docker_backend.py:70-79`) and the contract file's `_docker_ready()` use 5s and 10s timeouts at import time. A slow daemon turns every Docker test into a SKIP. The gate does not fail on skips. `-rs` only makes the skips visible.
- Suggested fix: after pytest, fail if a skip reason contains "requires a reachable Docker daemon" or "requires the test image". The preflight has already proven both.
- Related: `docker pull` from shared GitHub runner IPs can hit Docker Hub rate limits. A 3×5s retry would not help. The failure would be explicit and fail-closed, but flaky.

**F10 — NIT (verified). Duplicate definition.** `_preflight_required_executables` is defined twice in `tests/test_ci_workflow_config.py` (lines 167 and 203, identical). Remove one.

**F11 — NIT.**
- `_FIND_EXECUTABLES` treats an empty PATH component as `/name`, not the current directory. It is irrelevant for Alpine's PATH.
- `--image=-foo` is not validated, but it fails closed (I ran it: `FAIL [daemon]` here).
- The mypy job leaves pytest unpinned (`pytest>=8.0.0`). The evidence venv had pytest 9.2.0 and mypy 2.4.0. A future pytest release could break `--strict` independently of the code.
- A test comment claims "seen against a minimal image", which is not reproducible from the repo.

**F12 — NIT (UNVERIFIED, reasoned only). Delivery note.**
- A `pull_request` event runs the workflow from the merge ref. The new trigger therefore only affects PR #86 once this `ci.yml` is in PR #86's head or in `b01-base`. The integration branch alone gives CI through the `integration/**` push trigger.

**Probe validity (angle 4), no defect.**
- The probe runs `core.sandbox.backends._seccomp.apply_denylist()` from the production module in a separate subprocess. It has an unfiltered control, `/proc/self/status` `Seccomp` and `Seccomp_filters` checks, and AF_UNIX and AF_INET controls.
- On this kernel (6.18.44) AF_ALG returns errno 97 unfiltered. I verified this directly, so the skip reason is measured, not assumed.
- On this kernel AF_VSOCK is created unfiltered and returns EPERM filtered, so that test discriminates.
- The kernel-independent test proves the rule matches value 38. The AF_ALG-with-production-table path is only discriminating on a kernel that provides AF_ALG. On a no-AF_ALG kernel it skips with the verified reason. Mutation S4 shows this limit.

## 3. MUTATIONS RUN

Run on a `git archive HEAD` copy in the scratchpad. The real tree stayed clean (`git status --short` empty). Test IDs are abbreviated.

| Mutation | Tests run | Result |
|---|---|---|
| P1 skip identity stage | preflight | killed |
| P2 pull failure ignored | preflight | killed |
| P3 smoke `--pull missing` | preflight | killed |
| P4 exec check drops `--network none` | preflight | killed |
| P4b exec check `--pull always` | preflight | **survived** |
| P4c exec check `--network host` | preflight | **survived** |
| P5 snippet drops dir exclusion | preflight | killed |
| P5b snippet `-x` to `-e` | preflight | killed |
| P5c snippet never reports missing | preflight | killed |
| P6 bare-name regex allows leading `-` | preflight | **survived** |
| P7 main returns 0 on failure | preflight | killed |
| P8 report not written on failure | preflight | killed |
| P9 accept `<no value>` digest | preflight | killed |
| P10 fallback `alpine:3` after failed pull | preflight | killed |
| P11 pull attempts ignored | preflight | killed |
| P12 smoke stage skipped | preflight | killed |
| P13 executables never checked | preflight | killed |
| P14 image-id regex accepts anything | preflight | killed |
| P15 daemon check accepts rc≠0 | preflight | killed |
| P16 pull rc ignored | preflight | killed |
| P20 timeout mapped to rc 0 | preflight | **survived** |
| P21 docker-not-found mapped to rc 0 | preflight | **survived** (caught only by the output-shape check) |
| P22 exec check runs `alpine:3` | preflight | killed |
| P23 identity digest queried on `alpine:3` | preflight | killed |
| P24 report omits digest | preflight | killed |
| P25 exec check result ignored | preflight | killed |
| P26 zero pull attempts allowed | preflight | killed |
| S1 drop AF_VSOCK from production table | seccomp | killed |
| S2 AF_ALG errno to EPERM | seccomp | killed (also killed when running only the AF_ALG test) |
| S3 socket-family loop disabled | seccomp | killed |
| S4 production path silently drops AF_ALG | seccomp | **survived** (skip on this kernel; only a kernel with AF_ALG discriminates) |
| S4b AF_ALG removed from table, AF_ALG test alone | seccomp | skipped (same limit) |
| S5 filter never loaded | seccomp | killed (AF_ALG test alone also killed, before the skip branch) |
| S6 AF_VSOCK errno to EAFNOSUPPORT | seccomp | killed |
| S7 rule on arg1 | seccomp | killed |
| S8 blanket socket() deny | seccomp | killed |
| T1–T8 test-helper mutations (drop Seccomp==2, drop filter+1, drop AF_UNIX control, treat non-discriminating as enforced, accept any control errno, no-op apply, drop errno assertion, table pin accepts anything) | seccomp | all 8 killed |
| W1 drop b01-base | workflow config + gate | killed |
| W2 wildcard trigger | workflow config + gate | killed |
| W3 workflow_dispatch | workflow config + gate | killed |
| W4 drop `integration/**` | workflow config + gate | killed |
| W5 continue-on-error on preflight | workflow config + gate | killed |
| W6 `exit 0` appended to preflight | workflow config + gate | **survived** |
| W6b `; true` appended to preflight | workflow config + gate | **survived** |
| W6c `set +e` prefix on preflight | workflow config + gate | **survived** |
| W7 `if` on pytest step | workflow config + gate | killed |
| W8 literal `alpine:3` image | workflow config + gate | killed |
| W9 drop `hostname` from required list | workflow config + gate | killed |
| W10 image set to busybox | workflow config + gate | survived. The runtime preflight would catch it because python3 is required. |
| W11 `-rfEs` to `-rs` | workflow config + gate | killed |
| W12 preflight ordered after pytest | workflow config + gate | killed |
| W13 mypy `--strict` removed | workflow config + gate | killed |
| W14 mypy gate `\|\| true` | workflow config + gate | killed |
| W15 mypy unpinned | workflow config + gate | killed |
| W16 job-level `if` | workflow config + gate | killed |
| W17 permissions widened | workflow config + gate | killed |
| W18 gate step `\|\| true` | workflow config + gate | killed (by the existing `tests/test_ci_test_gate.py`) |
| W19 pytest path narrowed to `tests/core` | workflow config + gate | survived. Pre-existing weakness, not introduced here. |
| W20 artifact renamed | workflow config + gate | killed |
| W21 mypy FILES widened | workflow config + gate | killed |
| W22 continue-on-error on mypy step | workflow config + gate | killed |
| mypy type error in the production B03 file | executed the real workflow step script | step rc=1 (default=1, strict=1) |
| mypy strict-only error in the B03 test file | executed the real workflow step script | step rc=1 (default=0, strict=1) |
| mypy absent from PATH | executed the real workflow step script | step rc=1 (127/127) |

Other executed checks:
- Gate and pytest-step checks, run on a scratch pytest tree:
  - `-rfEs` gives FAILED, ERROR and SKIPPED lines, and the gate parses them.
  - `-rs` gives "1 failed but 0 distinct FAILED node ID(s)", which confirms the code comment.
  - A pytest run that exits 3 leaves 3 in the exit-code file, and the gate fails.
- The real preflight against this host, which has no daemon: `FAIL [daemon]`, rc=1, report written.
- The extracted workflow preflight step with the image variable set: rc=1, `FAIL [daemon]`.
- The same step with the image variable unset: rc=2, a usage error, with no default image.
- Test results at HEAD: `tests/test_ci_workflow_config.py` + `tests/test_ci_docker_preflight.py`, 53 passed. `tests/core/sandbox/test_seccomp.py`, 19 passed and 1 skipped (the AF_ALG skip). `tests/test_ci_test_gate.py` (scratch copy), 67 passed. `scripts/check_drift.py` (scratch copy), all PASS, rc=0.

## 4. CONSTRAINT CHECK

- **B03 inert, no change under `core/`: PASS.** `git diff --name-only a887e148..HEAD` lists exactly 5 files, none under `core/`. The two B03 files are byte-identical (`git diff --quiet` between a887e148 and HEAD).
- **No wiring into `DockerBackend.create()`, no `_CAPS`/`SandboxCapability` change, no `NETWORK_ALLOWLIST` change: PASS.** `core/` is untouched (same diff).
- **No changes to PR #86: PASS for the repo diff** (the branch is separate). The remote PR itself is unverified.
- **No changes to secrets or permissions: PASS.** `permissions: contents: read` is unchanged and pinned by a test. `git diff a887e148..HEAD -- .github | grep secrets\.` finds nothing.
- **No `workflow_dispatch`: PASS.** The triggers are exactly push and pull_request (parsed YAML, plus test and mutation W3).
- **No `continue-on-error`: PASS.** The grep over the diff finds none.
- **No job-level `if` that skips things: PASS.** The only new conditionals are two `if: always()` on artifact uploads.
- **D10 allowlist unchanged: PASS.** `git diff --quiet` is clean, and it still has 34 entries.
- **`scripts/ci_test_gate.py` unchanged: PASS.**
- **No added dependencies: PASS.** `requirements.txt` and `pyproject.toml` are untouched. `mypy==2.4.0` is installed only inside the new CI job.
- **Triggers kept: PASS.** `main` pull_request and `main`/`h2/**`/`integration/**` push remain, and `sandbox-network-isolation/b01-base` is added exactly (no wildcard).
- **Artifact uploads kept: PASS.** `drift-report` and `pytest-output` remain. `docker-preflight` and `mypy-b03` are added.
- **Narrow mypy step: PASS.** It covers exactly the two B03 files, runs default and `--strict`, and failed on both kinds of error in the mutations above.

## 5. WHAT I COULD NOT VERIFY

- **Docker behavior:** there is no daemon (`docker info` fails here). I could not run any Docker-backed test, the preflight against a real pull, `docker create` with the RepoDigests ref, the busybox applet behavior in python:3.12-alpine (F4), the contract suite going from SKIP to RUN (F1, F9), or Docker Hub rate limits. Everything about these is reasoned only.
- **GitHub semantics:** whether the hosted runner runs as non-root (F1), and merge-ref workflow selection for PR #86 (F12). Both are reasoned only.
- **Remote state:** PR #86 itself and the hosted CI results.
- **AF_ALG enforcement on a kernel that provides AF_ALG:** this kernel has none. On a no-AF_ALG kernel enforcement is covered only by the table pin and the stand-in test. Mutation S4 survives there, as noted.
- **Scratch cleanup:** a recursive `rm -rf` in the scratchpad was blocked by a safety check and I did not retry it. Scratch directories `gate_run_a`, `gate_run_b` and `tree` under `/tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/review/` remain. They are scratch only, and nothing in the repository was modified.
