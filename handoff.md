# Session Handoff

> **Version 2.** It supersedes version 1 (the DockerBackend implementation handoff), which is still in git history: `git show 9310155:handoff.md`. Version 1's section 2 holds the original DockerBackend implementation prompt verbatim; read it if you need that root contract. Everything below is about the **closure of the `sandbox-fabric` reconciliation**.

## 1. Handoff Metadata

- Handoff version: 2
- Created at: 2026-10-01 (the session ran 2026-09-29 through 2026-10-01)
- Workstream: closing the `sandbox-fabric` reconciliation (DockerBackend, DEBT-021). Steps 1 to 4 of the closure sequence are done. Step 5, the completion decision, is open.
- Task identifiers: DEBT-021 (DockerBackend); DEBT-039 (proposed, **not yet registered anywhere**: the cross-sandbox egress finding, formerly written "DEBT-038" until `main` registered that id for the `/distill` traversal)
- Source session purpose: carry out the user's closure sequence (section 2), which grew out of a D10 remediation and a closeout audit.
- Transfer status: see section 19.

## 2. Original Starting Prompt

Preserved verbatim. This is the user's instruction that defines this workstream (the earlier DockerBackend implementation prompt is in version 1; see the note above).

> Next is not another feature. Finish and close the `sandbox-fabric` reconciliation first.
> Sequence
> 1. Freeze the current five commits locally.
> Create a `git bundle` now as the recovery point. Do not push or merge yet.
> 2. Reconcile §18 against the literal checklist.
> Update the matrix so it explicitly records:
>
> * A9 = UNVERIFIED
> * C3 = BLOCKED
> * D9 = UNVERIFIED/BLOCKED, because no lifecycle-event producer exists
> * B4 = exception/non-compliant unless formally accepted
> * D11 = FAIL/pending design decision unless the checklist is changed
>
> 3. Resolve D11.
> This is the main substantive architectural question. Determine from the actual implementation and checklist whether the required synchronization primitive is mandatory. Do not let passing tests override an explicit “no lock at all” prohibition.
> 4. Close the evidence gap.
> Reproduce or conclusively document the unexplained DockerBackend failure. Then rerun:
>
> * DockerBackend targeted suite
> * mypy
> * orphan check
> * full suite
>
> Record the known `test_net_proxy.py` flake separately from any DockerBackend failure.
> 5. Make the completion decision.
> There are only two legitimate outcomes:
>
> * all checklist requirements are evidenced → sandbox-fabric complete
> * D11/B4/A9/D9/C3 remain unresolved → sandbox-fabric remains explicitly incomplete, with the exact debt/blocker recorded.
>
> Only after that should you push to repo

The governing documents are in the repo: `docs/architecture/PROJECT_INSTRUCTIONS.md`; the base prompt `docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt.md` (hierarchy position 1); the addendum `…-prompt-addendum.md` (2); the frozen 28-item checklist `docs/architecture/sandbox-fabric-dockerbackend-implementation-checklist.md` (3). **The addendum and checklist are frozen: do not modify them.**

## 3. Subsequent User Instructions / Corrections

In order. Wording preserved where it changed what was built or recorded.

1. **D10 go-ahead, with a scope correction.** Fix D10 first, but "do not yet touch `_CAPS`, declare the sandbox closed, or write the final closeout." Allowed files: the DockerBackend module and its test file. Required invariant: "Every resource acquired before a failure is either: 1. cleaned immediately, or 2. retained in a handle that remains destroyable." Cover create, network setup, container start, timeout, external container disappearance, daemon/API failure; "one explicit test per D10 failure point"; "no reliance on a happy-path destroy() test". For the shared network: "do not silently change its lifecycle just to make D10 green." A simulated spawn failure "is evidence of the cleanup path, not evidence that Docker itself produced that failure." Rotating the plaintext Git credential is "security hygiene, not part of the DockerBackend authorized patch."
2. **The cross-sandbox finding.** "Record it as a separate security finding, mark C2 FAIL, and do not redesign the network inside this workstream." `NETWORK_ALLOWLIST` withdrawn for concurrent sandboxes until isolation is demonstrated; `NET_NAMESPACE` must not be presented as sufficient evidence of network isolation; revert the "shared network = acceptable persistent infrastructure" decision; the redesign is a new workstream that may modify `_net_proxy.py` and the topology, "worked from an explicit invariant" (section 10, DEC-5); "do not issue an overall sandbox-security closeout that says the network isolation claims passed"; the `docker start`→`RUNNING` defect and the create-unwind residual stay separate follow-ups.
3. **`NET_NAMESPACE` withdrawn.** "Withdraw `NET_NAMESPACE` until it has a direct committed test": `_CAPS` becomes 7 of 12; implementation unchanged ("a claim/evidence withdrawal, not a statement that Docker failed to create a network namespace"); add the dedicated regression gate *later* (netns distinct from the host's; concurrently created sandboxes have distinct netns); "passing the future `NET_NAMESPACE` test must not resurrect the `NETWORK_ALLOWLIST` or C2 claims."
4. **The closure sequence** (section 2). Statuses to record at step 2 are in that text.
5. **"push to repo"**: I found the remote already contained all five commits (the user had merged my bundle, and `main`, into the remote branch). Nothing needed pushing.
6. **"continue Steps 2"**, then **"Step 3 (D11) is next"**.
7. **Guidance on step 4** (key points): establish the intended state machine first (`PENDING → STARTING → RUNNING → CANCELLING/CANCELLED`); the test must establish six facts (start blocked before completion; `cancel()` invoked in that interval; the cancel path runs while start is pending; the start completes afterwards; the workload is demonstrably still running; the backend reports what the contract promises); "don't fix the test by simply making `cancel()` wait for `start()` unless that is the intended lifecycle contract"; compare fixes (record intent; explicit startup state plus a post-start check; locking `run()`/`cancel()` together, to be avoided); "D11 should stay PASS while Step 4 is investigated independently."
8. **"push the finished work to repo, then create a handoff to complete the remaining work in a new session."** This file is that handoff.

## 4. Goal, Scope & Success Criteria

### Goal
Close the `sandbox-fabric` reconciliation by making the **step-5 completion decision** and recording the exact debts and blockers.

### In scope
- Writing the completion decision into the reconciliation document (`docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`), as a new subsection after §19.3.
- Collecting the user decisions listed in section 17.
- Pushing the resulting commits.

### Out of scope (do not do these inside this workstream)
- The network redesign (C2, DEBT-039). It is a new workstream.
- Any change to `_net_proxy.py`, `NamespaceBackend`, `_ns_init.py`, `_seccomp.py`, `admission.py` or `contracts.py`.
- Modifying the frozen addendum or checklist.
- The Dependabot findings on the default branch (see section 15).
- Editing `KNOWN_ISSUES.md` without the user's go-ahead (it is outside the file boundary; see section 17).

### Success criteria
There are two legitimate outcomes (user's wording, section 2). **Outcome 1 is not reachable:** six checklist items cannot be evidenced as PASS in this environment or by this workstream alone (section 5). So the expected result is **Outcome 2: `sandbox-fabric` remains explicitly incomplete, with the exact debt or blocker recorded for each unresolved item.**

## 5. Requirement Ledger

### Closure sequence

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| S1 | Freeze the five commits in a `git bundle`, no push or merge | DONE | `sandbox-fabric-021a3b4.bundle` (verified; restores to `021a3b4`). It is now stale: everything is on the remote |
| S2 | Reconcile §18 with the literal checklist (A9, C3, D9, B4, D11) | DONE | commit `97aac38`; §18.2 legend and rows |
| S3 | Resolve D11 | DONE | D11 FAIL to PASS: `9e1378b`, `bbdb717`; reconciliation §19.1 |
| S4 | Evidence gap: explain the unexplained failure; rerun suite, mypy, orphans, full suite; record the `test_net_proxy.py` flake separately | DONE, with a caveat | `b8a76c5`, `2e8c74c`; §19.2 and §19.3. The mechanism is reproduced; that it caused the one-off failure is **unproven** (the failing test was not captured) |
| S5 | Completion decision | **OPEN** | not written |

### The 28 checklist items (reconciliation §18.2 is authoritative; this is a copy)

**PASS (22):** A2, A3, A4, A5, A6, A7, A8, B1, B2, B3, C1, D1 to D8, D10, D11, D12.

**Not PASS (6), each with its exact blocker:**

| ID | Status | Exact blocker / what unblocks it |
|---|---|---|
| A1 | BLOCKED | Needs `NETWORK_ALLOWLIST` and `NET_NAMESPACE` re-earned: the DEBT-039 redesign and a direct `NET_NAMESPACE` gate. The paired-claim invariant mechanism itself is sound and tested |
| A9 | UNVERIFIED | `AF_VSOCK` probe was run and is **negative** (bypass open via `socketcall(2)` on this host); `AF_ALG` is not exercisable (the kernel lacks it). Needs a host with an active AppArmor or SELinux policy and a Docker release containing the socketcall fix. `SECCOMP` stays unclaimed |
| B4 | NON-COMPLIANT | `handoff.md` is on no allow-list. Closes only by the user's **formal acceptance** of the exception (and of the reconciliation document's status under B4's list), or by removing `handoff.md` |
| C2 | FAIL | DEBT-039: sandbox B obtained a tunnel through sandbox A's proxy on the shared gateway (reconciliation §17.2, reproduction in §17.7). Needs the network redesign and a passing concurrent A/B test |
| C3 | BLOCKED | Needs the same host as A9: the exploit probe blocked **and** a benign compat probe still working, recorded together. Not N/A: the item has no N/A clause |
| D9 | UNVERIFIED, BLOCKED | No lifecycle-event producer exists anywhere (`NamespaceBackend` included; nothing outside tests imports `core.sandbox`). Needs a decision: backends publish through `EventStream`, or D9 is amended |

`_CAPS` is **7 of 12**: `CGROUP_MEMORY`, `CGROUP_PIDS`, `FILESYSTEM_JAIL`, `MOUNT_NAMESPACE`, `NO_NEW_PRIVS`, `PID_NAMESPACE`, `UTS_NAMESPACE`. Absent: `NETWORK_ALLOWLIST` and `NET_NAMESPACE` (withdrawn), `NETWORK_DENY_DEFAULT`, `SECCOMP`, `USER_NAMESPACE` (never earned).

## 6. Current Verified State

**VERIFIED** (all at HEAD `2e8c74c`; evidence in section 13):
- DockerBackend targeted suite: 88/88 on three consecutive runs.
- Full `tests/core/sandbox`: 147 passed in one run.
- mypy clean on `docker_backend.py` and `test_docker_backend.py`.
- 0 containers, 0 shared-network endpoints, 0 artifact temp dirs after every run.
- The 7 out-of-scope files are byte-identical to the base.
- Local HEAD equals `origin/sandbox-fabric` (unauthenticated `git ls-remote`).

**IMPLEMENTED BUT NOT VERIFIED:** nothing known.

**PROPOSED (not accepted or registered):** DEBT-039 as the id for the cross-sandbox finding, with the text in reconciliation §17.6; the §17.5 follow-ups as separate debts.

**BLOCKED / UNVERIFIED / FAIL:** the six items in section 5.

**UNKNOWN:** the identity of the single unreproduced DockerBackend failure (section 11); the cause of the `test_net_proxy.py` flake (section 15).

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1`, remote `origin` = `https://github.com/1h0lde4/ocbrain-v4.1.git`
- Branch: `sandbox-fabric`; base branch: `main` (the user has merged `main` into the branch twice, `68fd460` and `565ea3a`)
- Implementation and docs checkpoint ("transfer commit"): **`2e8c74c`**, pushed and verified. The remote moved `f64fe5d` → `2e8c74c`.
- Commits pushed this session, oldest first: `97aac38` (§18 reconciled), `9e1378b` (D11 code), `bbdb717` (D11 docs), `b8a76c5` (cancel-during-start code), `2e8c74c` (§19.2 and §19.3 docs).
- Earlier workstream commits (D10, the withdrawals, the closeout audit; `e41299a`, `4eb818f`, `a59c979`, `fa06317`, `021a3b4`) reached the remote through the user's merge of the bundle.
- Handoff commit: the commit that last touched this file. Find it with `git log -1 --format=%H -- handoff.md`. Its parent is `2e8c74c`.
- Working tree status: clean when this file was written.
- Untracked and ignored relevant files: none.
- Remote push status: implementation checkpoint pushed and verified by an unauthenticated `git ls-remote`.

## 8. Active Files / Modified Files / Artifacts

- `core/sandbox/backends/docker_backend.py`: the implementation. Its docstrings cite the reconciliation sections that verify them.
- `tests/core/sandbox/test_docker_backend.py`: 88 tests; about 20 need no daemon, the rest are gated per test on a reachable daemon.
- `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`: the evidence narrative. **Read §§17, 18 and 19 first.** §17 is D10 and the cross-sandbox finding; §18 is the 28-item matrix and the B and D12 audits; §19.1 is D11; §19.2 and §19.3 are the cancel race, the unexplained failure and the step-4 results.
- `docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt-addendum.md` and `…-checklist.md`: frozen.
- `handoff.md`: this file.
- Not in the repo and not reproducible from it: the scratch pytest plugin and mutation helper (section 14, reproduced there); the `.bundle` file (delivered to the user).

## 9. Changes Made

Since version 1 (details in reconciliation §§17 to 19):

- **D10:** `create()` now cleans or retains every resource acquired before a failure; `destroy()` confirms removal before forgetting a handle. Fixed a live proxy listener left with no handle, a leaked workspace directory, and a handle dropped before removal was confirmed.
- **Capabilities:** `NETWORK_ALLOWLIST` and `NET_NAMESPACE` withdrawn from `_CAPS` (9 → 7). `check_admission()` therefore rejects any request that sets `allowed_hosts`.
- **Closeout-audit defects (D4, D5, D6):** a `request_id` label; non-regular files (a sandbox-made FIFO hung artifact collection) are no longer hashed; a second `run()` raises instead of re-executing; `cancel()` before `run()` no longer mislabels a later run.
- **D11:** the handle record is kept until removal is confirmed, and `destroy()` runs under a **per-handle** `asyncio.Lock`; `run()` and `cancel()` take no lock.
- **Cancel during start:** `cancel()` records intent (a private `asyncio.Event`) and `run()` enforces it by re-sending `docker kill` every 50 ms until the container is dead.
- **Caller-visible behavior changes:** a second `run()` raises `DockerBackendError`; concurrent `destroy()` calls on a handle wait for the earlier one; `destroy()` can raise `DockerBackendError` when removal cannot be confirmed (the handle is then retained); `inspect()` during an in-flight destroy reports the real state, not `PENDING`.
- **No schema, contract or policy changes.** `contracts.py` is byte-identical to the base.
- **Tests:** 44 at version 1 → 88. 26 mutation checks in total, each caught by the intended test.

## 10. Decisions & Rationale

| ID | Decision | Status | Authority / rationale | Reopen condition |
|---|---|---|---|---|
| DEC-1 | D10 remediation stays strictly inside the DockerBackend module and its tests | Settled | User instruction | n/a |
| DEC-2 | `NETWORK_ALLOWLIST` withdrawn from `_CAPS` | Settled | Observed cross-sandbox egress contradicts the claim; capabilities are earned (B2) | A passing concurrent A/B test with different allowlists |
| DEC-3 | `NET_NAMESPACE` withdrawn (claim only; implementation unchanged) | Settled | No direct committed test; its only evidence was the C2 set. A scratch check showed the netns differs from the host's but is not a committed test | A committed test that the netns differs from the host's and that concurrent sandboxes have distinct netns. Passing it re-earns `NET_NAMESPACE` alone |
| DEC-4 | The shared network's lifecycle (persist vs remove) is **undecided**; an earlier "persistent infrastructure" draft was reverted | Settled as undecided | User instruction: it belongs to the redesign | The redesign workstream |
| DEC-5 | C2 = FAIL; DEBT-039 is a separate security finding and a new workstream. The invariant to preserve, verbatim: "A sandbox must not be able to reach or use another sandbox's egress proxy, directly or indirectly, and its outbound policy must be enforced independently of sibling sandboxes." Its regression gate is a concurrent A/B test with deliberately different allowlists, of the shape in reconciliation §17.7. A per-sandbox network/proxy binding is one plausible direction, not a decision | Settled | User instruction | n/a |
| DEC-6 | Statuses A9 UNVERIFIED, C3 BLOCKED, D9 UNVERIFIED/BLOCKED, B4 NON-COMPLIANT. Note: A9's `AF_VSOCK` probe was run and was negative, so UNVERIFIED describes the *protection*, not whether testing happened | Settled | User instruction; the checklist's literal text wins over earlier judgments | A host or decision that changes the evidence |
| DEC-7 | D11 = PASS via record retention plus a per-handle lock | Settled | Base prompt silent; addendum requires race-safe bookkeeping; the checklist forbids "no lock at all". The pop-first `destroy()` had violated the invariant | The checklist is amended, or a new interleaving is shown unsafe |
| DEC-8 | Cancel enforcement lives in `run()`; `cancel()` never waits for start and no lock is added | Settled | Public `SandboxState` fixed by D12; the cancel contract does not promise to wait; waiting would reintroduce the serialization D11 forbids (mutant M26 guards it) | The contract changes |
| DEC-9 | `DEBT-039`, not `DEBT-038`, for the cross-sandbox finding | **Proposed** by the assistant, no objection so far | `main` registered DEBT-038 (the `/distill` `module_name` traversal, PRs #37 and #38) | The user picks another id |
| DEC-10 | Tests assert **effective** state (docker inspect, in-container behavior, host filesystem), not the request that was built | Settled | The prompt's requested, accepted, effective distinction | n/a |

## 11. Investigation Already Performed

| Area | Inspected | Result | Revisit trigger |
|---|---|---|---|
| Authority for each audited item | Base prompt, addendum and checklist read literally for A9, B4, C3, D9, D11 | Statuses reconciled (§18) | A checklist amendment |
| Possible LSM on this host | Kernel config, `/sys/kernel/security/lsm`, `/proc/self/attr/current` | AppArmor is not compiled in and `nomodule` is set; SELinux is compiled in and listed in the active LSM stack with **no policy loaded**; a policy load was not attempted (risk to the VM, defaults permissive) | A host that has a policy loaded |
| Cross-sandbox proxy reach | Scratch A/B probe | B reached A's proxy (reconciliation §17.7). Port discovery by scanning was **not** demonstrated (B was handed the port) | The redesign |
| Artifact collector | Absolute, relative, nested and directory symlinks; a FIFO | Absolute and directory symlinks rejected; a relative escaping symlink makes `docker cp` refuse, so the manifest is empty (silent loss); the FIFO hung collection (fixed) | Hard links, extraction races, workspace size (not attacked) |
| Lifecycle ordering (D6) | Run-before-create, double run, cancel-before-run, cancel-after-terminate, double destroy, inspect-after-destroy | Two defects fixed, four already correct | n/a |
| Event producers (D9) | `grep` across the repo | None publishes; `EventStream` exists | A producer is added |
| The unexplained failure | See below | Mechanism reproduced; causation unproven | The failing test is captured |
| DEBT id collision | `KNOWN_ISSUES.md` on the remote tip | DEBT-038 taken; the next free id is DEBT-039 | n/a |
| Remote history | `git log` of the remote tip | The user merged my bundle and `main` into `sandbox-fabric` | n/a |

**The unexplained failure, exactly.** One DockerBackend-file run showed 1 failed / 78 passed right after a mass `docker rm -f`, and I had not captured which test. The mechanism that explains the class is a `cancel()` landing while `docker start` is in flight (reconciliation §19.2). Under a scratch plugin that delays every `docker start` by 1.5 s, 4 of the 10 existing cancel tests failed on the unmodified code. After the fix they pass at 1.5 s and 3.0 s. It did not recur in 9 full-file runs, 3 full-suite runs and 6 timing-sensitive subset runs since. **Do not claim it is explained as the cause**: only the mechanism is established.

## 12. Failed Attempts / Dead Ends

| Approach | Result | Cause | Retry? |
|---|---|---|---|
| A combined D5 symlink test requiring `legit.txt` in the manifest | Empty manifest | A relative escaping symlink makes `docker cp` itself refuse; the collector then returns an empty manifest | No: split into two tests |
| First C1 test using `kill -9 $$` from a container's PID 1 | Exit 0, not 137 | A PID 1 shell ignores its own SIGKILL | No: kill from a child and re-exit with its status |
| First red phase for D10 | Mostly noise | A test-helper off-by-one (`_docker_cmd` slice) meant the injector never fired | No: every injecting test now asserts the injection fired (`.hits`) |
| Running the D5 FIFO test in-process | Would hang the whole suite | `_sha256_of` does a synchronous `open()`, which blocks the event loop, so `wait_for` can never fire | No: the test runs in a subprocess with a hard timeout |
| Sourcing `start_docker.sh` with its output discarded | All Docker-gated tests silently skipped ("10 skipped"); no result was valid | The VM had restarted and the daemon was not up | **Never discard the start script's output; abort if the daemon is not ready** |
| Bash arrays and `base64 -w0` assumptions | Syntax error | The shell is `dash` | Use POSIX `sh`, or call `bash -c` explicitly |
| Pushing before checking the remote | Would have attempted a non-fast-forward | The user had already merged the bundle | Always `git fetch` first and only push if the remote is an ancestor of HEAD |
| A custom seccomp profile to close the `AF_VSOCK` bypass (version 1) | Bypass stayed open | seccomp cannot filter `socketcall(2)` arguments (they sit behind a userspace pointer); only an LSM hook can | Only on a host with an active LSM policy |

## 13. Verification Evidence

Commands run in `/home/claude/ocbrain-v4.1` (the Docker daemon must be up first; section 14):

- `python3 -m pytest tests/core/sandbox/test_docker_backend.py -q --asyncio-mode=auto -p no:cacheprovider` → **88 passed**, three consecutive runs (~55 s each).
- `python3 -m pytest tests/core/sandbox -q --asyncio-mode=auto -p no:cacheprovider -rf --tb=short` → **147 passed** in one run, 0 DockerBackend failures. An earlier full-suite run (140 tests, before the later work) showed 139 passed and 1 failed, the failure being `test_net_proxy.py`.
- `python3 -m mypy core/sandbox/backends/docker_backend.py tests/core/sandbox/test_docker_backend.py --ignore-missing-imports --explicit-package-bases` → Success.
- Orphan check after each run: `docker ps -aq | wc -l` = 0; shared-network endpoints empty; `ls -d /tmp/ocbrain-docker-artifacts-*` empty.
- **`test_net_proxy.py` alone, 6 runs: 3 failed.** `test_plain_http_to_allowed_host_is_forwarded` twice and `test_connect_to_allowed_host_tunnels_real_data` once. Inside the full suite it usually passes, which hides the frequency. Neither it nor `_net_proxy.py` is touched by this workstream.
- Mutation checks M1 to M26, each caught by the intended test and each restoring the source byte-identical (summarized in §17.1, §18.3, §19.1 and §19.2).
- Remote verification: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/sandbox-fabric` = `2e8c74c171ac298cc84065a8f96dda34bf126bd5` at the time of the push.

## 14. Environment / Tooling Assumptions

- Ubuntu 24.04; kernel `6.18.44-fc-v50` (a Firecracker microVM; the value **drifts** within a session: v37 → v42 → v49 → v50); Python 3.12; Docker Engine 29.1.3 (Ubuntu's `docker.io`); cgroup v1 with `cgroupfs`; no AppArmor; iproute2 6.1.0; no `daemon.json`.
- **The VM can restart mid-session.** The filesystem and the Docker image survive; the daemon does not. Re-run the start script at the top of every call that needs Docker, and read its output:

```sh
#!/bin/sh
if ! docker info > /dev/null 2>&1; then
    containerd > /var/log/containerd.log 2>&1 &
    sleep 3
    dockerd > /var/log/dockerd.log 2>&1 &
    i=0
    while [ $i -lt 20 ]; do
        docker info > /dev/null 2>&1 && break
        i=$((i + 1))
        sleep 1
    done
fi
docker info > /dev/null 2>&1 && echo "docker: ready" || echo "docker: FAILED -- $(tail -8 /var/log/dockerd.log)"
```

  It lives at `/home/claude/start_docker.sh` in the session container only (recreate it). Source it with `. /home/claude/start_docker.sh`, then **abort if it does not print `docker: ready`**. A cold start after a restart can take longer than the 20-second wait.
- Install, if absent: `apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io gcc-multilib libc6-dev-i386`; `pip install pytest pytest-asyncio mypy --break-system-packages`. No registry is reachable (`registry-1.docker.io` and `ghcr.io` return 403).
- Test image (not in git; rebuild it): `tar -C / -c --exclude=proc --exclude=sys --exclude=dev --exclude=tmp --exclude=run --exclude=home/claude --exclude=mnt --exclude=var/lib/docker --exclude=var/lib/containerd bin sbin lib lib64 usr etc | docker import - ocbrain-test/base:local`, then `export OCBRAIN_SANDBOX_DOCKER_IMAGE=ocbrain-test/base:local`.
- The shell is `dash`.
- Scratch tooling used for the evidence (not in the repo): a **mutation helper** that replaces one exact string in `docker_backend.py` (asserting it matches exactly once), runs the targeted tests, and restores the file from a saved copy, checking its sha256; and a **slow-start pytest plugin** loaded with `PYTHONPATH=/tmp python3 -m pytest -p slowstart_plugin …`:

```python
import asyncio, pytest
@pytest.fixture(autouse=True)
def _slow_docker_start(monkeypatch):
    real = asyncio.create_subprocess_exec
    async def fake(*argv, **kw):
        if len(argv) >= 2 and argv[0] == "docker" and argv[1] == "start":
            await asyncio.sleep(1.5)
        return await real(*argv, **kw)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake)
```

- **Credentials.** No secret is stored in the repo, in this file, or in memory. The user's **preferences field contains a plaintext GitHub token**; the user has said it should be rotated and removed. It was used only for push operations the user explicitly asked for, passed per command via `git -c http.extraheader=…`, never written to git config or a remote URL, and never printed. Do not copy it anywhere. If you need to push, either use a token the user pastes for that push or get an explicit instruction to use the preferences one.
- Network egress from the container is allowlisted: package registries, `github.com`, `api.github.com`, `raw.githubusercontent.com`, and a few others.

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Options | Safe to continue without it? |
|---|---|---|---|
| **B4 acceptance** | `handoff.md` is outside B4's literal allow-list; the branch diff also contains `main` merged by the user | Formally accept the exception, or remove `handoff.md` (the project's handoff protocol requires one) | Yes for the decision document; the status stays NON-COMPLIANT |
| **D9 path** | No event producer exists | (a) backends (DockerBackend, arguably `NamespaceBackend`) publish through `EventStream`: implementation work, LAW 2 | Yes: record as BLOCKED |
| **DEBT-039 registration** | Not in `KNOWN_ISSUES.md`; proposed text in reconciliation §17.6 | Add on a separate branch or PR, or with the user's go-ahead | Yes |
| **`DEBT-021` status in `KNOWN_ISSUES.md`** | The entry on the remote still says there is no Docker-backed implementation | Update it to reflect "implemented, explicitly incomplete" | Yes |
| **Network redesign (C2)** | §17.2, §17.4 and §17.7 | New workstream: may touch `_net_proxy.py` and the topology; invariant in DEC-5; plausible direction is a per-sandbox network and proxy binding | Yes |
| **`test_net_proxy.py` flake** | 3 of 6 standalone runs failed; two different tests; cause undiagnosed | Diagnose inside the redesign workstream | Yes (recorded separately) |
| **A9 / C3 host** | See section 5 | A host with an active LSM policy and Docker ≥ the fix release; a kernel exposing `AF_ALG` | Yes |
| Unattacked or untested | `docker build` `RepoDigests`; artifact hard links and workspace size; `FILESYSTEM_JAIL` vectors (`/dev/shm`, `/proc`, `/sys`, mount attempts); whether an `AF_VSOCK` socket can connect anywhere on a real host; port discovery of a sibling proxy by scanning | Optional follow-ups | Yes |
| Follow-ups from §17.5 | `RUNNING` is left after a failed `docker start` spawn; the create-unwind residual if the daemon is down during the unwind; a finalizer so failing D10 tests do not leave containers; the stale module docstring in the test file that says every daemon test is skipped; a relative escaping symlink empties the manifest silently | Separate debts | Yes |
| **Dependabot** | Every push prints "3 vulnerabilities (1 critical, 2 high)" on the default branch; never investigated | Needs the user's go-ahead; a different workstream | Yes |
| `handoff.md` version 1 §5 is stale | Superseded by this file | n/a | Yes |

## 16. Relevant Information / References

- Reconciliation document: `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md` §§17 to 19.
- The frozen checklist and addendum (paths in section 2). The checklist's literal item text is what the statuses are judged against.
- `docs/architecture/PROJECT_INSTRUCTIONS.md`: §18.4.8 is the handoff format used here.
- Upstream references recorded in §12 of the reconciliation document: `moby/moby#52537` (the earlier `AF_ALG` fix) and `moby/moby#53551` (the socketcall/`AF_VSOCK` fix, Engine 29.8.0). The installed Docker 29.1.3 predates both.
- `main`'s DEBT-038 is the `/distill` `module_name` path traversal (PRs #37 and #38).
- Version 1 of this handoff: `git show 9310155:handoff.md`.

## 17. Next Steps

In order.

1. **Resume and verify** (section 18). No code change is expected in this workstream.
2. **Ask the user for four decisions** (one message): (a) accept or reject the `handoff.md` B4 exception; (b) for D9, whether to keep it BLOCKED or open a workstream to make backends publish through `EventStream`; (c) whether to confirm `DEBT-039` and authorize registering it, and updating `DEBT-021`, in `KNOWN_ISSUES.md` (outside the file boundary: separate branch or PR, or an explicit go-ahead); (d) whether to open the network-redesign workstream now.
3. **Write the completion decision** as a new subsection after §19.3 of the reconciliation document (§19.4): state **Outcome 2, explicitly incomplete**, and carry the six items of section 5 with their exact blocker and the evidence that would unblock each. Record the user's decisions from step 2 verbatim. Update the §18 headline to point at it.
4. If the user authorizes it, make the `KNOWN_ISSUES.md` changes on a separate branch or PR, not on `sandbox-fabric`.
5. **Commit, then push** with the fast-forward guard (section 18, step 3), and verify with an unauthenticated `git ls-remote`.
6. Do **not** start the network redesign, the `EventStream` work or the A9/C3 host work inside this workstream.

Expected verification for step 3: the matrix tally in §18.2 (22 PASS, 1 FAIL, 3 BLOCKED, 1 UNVERIFIED, 1 NON-COMPLIANT) still sums to 28 and matches the new subsection.

## 18. Resume Instructions

1. Check out `sandbox-fabric`; `git fetch origin sandbox-fabric`; confirm `git log -1 --format=%H -- handoff.md` is an ancestor of, or equal to, `HEAD`, and that `2e8c74c` is an ancestor of `HEAD`.
2. Confirm the remote: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/sandbox-fabric` is at or beyond the handoff commit. If the remote has moved ahead (the user merges into this branch from their own machine), **fast-forward local to it before committing anything**.
3. Before any push: `git fetch`; push only if `origin/sandbox-fabric` is an ancestor of `HEAD`. If it is not, **stop and report; never force.**
4. Read the reconciliation document §§17 to 19 before trusting any status in this file; the repository is the authority and this file is a transfer record.
5. If you will run any test, recreate the Docker host first (section 14) and confirm the daemon prints `docker: ready`.
6. Begin from section 17, step 2. Do not reconstruct completed work.

## 19. Transfer Status

**TRANSFER INCOMPLETE — HANDOFF NOT PUSHED at the moment this file was written.** The implementation checkpoint (`2e8c74c`) **is** pushed and verified. This becomes **TRANSFER READY** when `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/sandbox-fabric` shows a commit at or beyond the one returned by `git log -1 --format=%H -- handoff.md`. The session pushes the handoff commit immediately after writing it, so if you are reading this file from the remote, that criterion is met and this paragraph is simply out of date.

Condition by condition: original task preserved (section 2, verbatim); material instructions preserved (section 3); scope and success criteria (section 4); requirements accounted for (section 5, all 5 steps and all 28 items); current state verified (section 6, with a fresh full run); decisions preserved (section 10); investigation and failed approaches recorded (sections 11 and 12); verification recorded (section 13); environment assumptions recorded (section 14); all material work in Git: yes; implementation checkpoint pushed: yes; handoff committed: yes, immediately after this file is written; exact next action defined: yes (section 17).
