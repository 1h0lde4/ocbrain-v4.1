# Session Handoff

> **Version 3.** It supersedes version 2 (the closure of the `sandbox-fabric` reconciliation, steps 1 to 4 done, step 5 open), which is in git history: `git show fd7f057:handoff.md`. Version 1 (the DockerBackend implementation handoff, with the original implementation prompt verbatim in its section 2) is `git show 9310155:handoff.md`. **The closure is finished (Result 2). This version hands over the next piece of work: the network-redesign study for DEBT-039, which has not been started.**

## 1. Handoff Metadata

- Handoff version: 3
- Created at: 2026-10-03 (the closing session ran 2026-09-29 through 2026-10-03)
- Workstreams: (A) closing the `sandbox-fabric` reconciliation (DockerBackend, DEBT-021): **COMPLETE, Result 2, explicitly incomplete as a sandbox**; (B) the network-redesign study for DEBT-039 (checklist items C2 and A1): **OPEN, NOT STARTED**
- Task identifiers: DEBT-021, DEBT-039 (id confirmed by the user and registered on `main`), checklist items A1, A9, B4, C2, C3, D9
- Source session purpose: carry out the user's closure sequence, then the follow-ups the user ordered (section 3)
- Transfer status: section 19

## 2. Original Starting Prompt

The user instruction that defined workstream (A), preserved verbatim (it is also in version 2). The earlier DockerBackend implementation prompt is in version 1; the governing documents are in the repo (below).

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

Governing documents in the repo (on `sandbox-fabric`): `docs/architecture/PROJECT_INSTRUCTIONS.md`; the base prompt `docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt.md` (hierarchy position 1); the addendum `…-prompt-addendum.md` (2); the frozen 28-item checklist `docs/architecture/sandbox-fabric-dockerbackend-implementation-checklist.md` (3). **The addendum and checklist are frozen: do not modify them.** The evidence narrative is `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`.

## 3. Subsequent User Instructions / Corrections

Items 1 to 8 are in version 2, section 3 (`git show fd7f057:handoff.md`), with the wording that mattered. Their substance: D10 remediation inside the DockerBackend module and its tests only; the cross-sandbox finding recorded as a separate security finding with C2 = FAIL and no network redesign inside that workstream; `NET_NAMESPACE` withdrawn until it has a direct committed test; the closure sequence (section 2); "push to repo"; "continue Steps 2"; "Step 3 (D11) is next"; the guidance on step 4 (state machine first, six facts the test must establish, "don't fix the test by simply making `cancel()` wait for `start()`"); "push the finished work to repo, then create a handoff".

Since version 2, in order:

9. **"Defaults."** The user accepted the four defaults and gave them in these words (also recorded verbatim in reconciliation §19.4):
   1. "B4 — Formally accept the `handoff.md` exception and document it explicitly in §19.4. Do not represent this as general compliance with the authorized-file list."
   2. "D9 — Leave it BLOCKED. Do not open a new workstream to make backends publish through `EventStream` as part of this closure."
   3. "DEBT-039 — Confirm this ID and prepare to record it, together with the corresponding DEBT-021 update, on a separate branch/PR, because `KNOWN_ISSUES.md` is outside the `sandbox-fabric` scope."
   4. "Network redesign — Do not open it now. Leave it as future work independent of this closure."

   Also: close Step 5 with the second outcome, preserve the six non-PASS states exactly, "Do not modify unrelated code or scope", report the files, diff, decision and follow-up, and for any push "do not use or expose a plaintext token in the conversation".
10. **Stage 5 confirmed closed.** The user stated the authoritative state: Result 2; the matrix 22 PASS / 1 FAIL (C2) / 3 BLOCKED (A1, C3, D9) / 1 UNVERIFIED (A9) / 1 EXCEPTION ACCEPTED (B4); `_CAPS` = 7 of 12; "Do not extend B4 to the reconciliation document unless you explicitly decide to. The current acceptance names `handoff.md` only."; `a574091` is the correct completion commit, parent `fd7f057`; `KNOWN_ISSUES.md` stays a separate follow-up; "`handoff.md` v2 is stale and should be refreshed during the next session, not retroactively folded into Stage 5." The user also said the GitHub token in the preferences should be revoked, and gave this standing instruction: "Do not modify the Stage 5 decision or broaden B4 beyond the explicitly named `handoff.md`."
11. **"never ever answer in french even if the prompt is in french".** Standing. Reply in English.
12. **"use this token from now on: …"** (token deliberately not recorded here). This superseded the earlier "do not use the token" for the pushes, the pull request and the merge that followed. It does not make the token safe to store or print (section 14).
13. **The sequence after Stage 5** (the user's words, kept because the order matters): "Next should be the `KNOWN_ISSUES.md` PR, not implementation work. Recommended sequence: 1. Open PR `docs/known-issues-debt-039-debt-021` → `main`. 2. Review the diff and verify: only `KNOWN_ISSUES.md` changed; base is `4ab5345`; `DEBT-039` remains untriaged; `DEBT-021` correctly describes `DockerBackend` as incomplete; no accidental sandbox-fabric changes are included. 3. Run the documentation/CI checks required by the repository. 4. Merge the PR once green. 5. Refresh `handoff.md` v2 from the resulting remote state. 6. Only after that, start the network-redesign study, because DEBT-039 now establishes the documented dependency for C2/A1. I would not start LSM/A9/C3, D9, or Dependabot remediation yet; they are separate tracks and should retain their own evidence and branches." Steps 1 to 5 are done by this file. **Step 6 is next.**
14. "continue" (taken as: resume the open follow-up; it was **not** treated as authorization to merge or to start anything new), then "start" (start the handoff refresh, which this file is).

## 4. Goal, Scope & Success Criteria

### Goal
Workstream (A), the closure, is achieved: `sandbox-fabric` is formally reconciled as **explicitly incomplete**, each open item with its exact blocker. Workstream (B) is to **study** the network redesign that DEBT-039 requires, working from the invariant in reconciliation §17.4:

> A sandbox must not be able to reach or use another sandbox's egress proxy, directly or indirectly, and its outbound policy must be enforced independently of sibling sandboxes.

### In scope for (B)
- Reproduce and, where cheap, separately verify the finding (reconciliation §17.2 and §17.7). Its mechanism is a hypothesis from reading the code, not a verified fact.
- Design from the invariant, not from an assumed implementation. A per-sandbox network/proxy binding is "one plausible direction, not a decision".
- Decide the undecided shared-network lifecycle (DEC-4) as part of the design.
- Define the regression gate (a concurrent A/B test with deliberately different allowlists, shape in §17.7) and the direct `NET_NAMESPACE` gate (§17.8).
- The study may legitimately propose changes to `_net_proxy.py` and the network topology.

### Out of scope (do not do these)
- Starting an implementation without the user's explicit go-ahead: the user said "study".
- LSM-enabled host work (A9, C3), the D9 producer decision, Dependabot remediation: separate tracks with their own evidence and branches.
- Changing the Stage 5 decision, broadening B4, modifying the frozen addendum or checklist.
- Merging anything without an explicit instruction for that merge.

### Success criteria
- (A): met. See section 5.
- (B): **the user has not defined the deliverable.** Do not assume one. The first action of the study is to ask where the study should be recorded (a document under `docs/architecture/`, on which branch) and what "done" means for it. Any eventual claim that C2 or A1 is resolved needs the concurrent A/B regression to pass, and `NETWORK_ALLOWLIST` may be claimed again only after that (A1's paired-claim invariant also requires `NET_NAMESPACE`).

## 5. Requirement Ledger

### Closure sequence and follow-ups

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| S1 | Freeze the five commits in a `git bundle` | DONE | v2; the bundle is stale |
| S2 | Reconcile §18 with the literal checklist | DONE | `97aac38` |
| S3 | Resolve D11 | DONE (PASS) | `9e1378b`, `bbdb717`; reconciliation §19.1 |
| S4 | Evidence gap and reruns | DONE, caveat: mechanism reproduced, causation of the one unexplained failure unproven | `b8a76c5`, `2e8c74c`; §19.2, §19.3 |
| S5 | Completion decision | **DONE: Result 2** | `a574091`; reconciliation §19.4 |
| R1 | Push the closure work | VERIFIED | `origin/sandbox-fabric` = `a574091` before this handoff commit (unauthenticated `git ls-remote`) |
| R2 | B4: accept the `handoff.md` exception, narrowly; do not extend it | DONE | §19.4, §18.2; names `handoff.md` only |
| R3 | D9 stays BLOCKED, no `EventStream` workstream in this closure | HONORED | §19.4 |
| R4 | Register DEBT-039 and update DEBT-021 on a separate branch/PR | **VERIFIED, merged** | PR #47, merge commit `69df55f` on `main` |
| R5 | Do not open the network redesign inside the closure | HONORED | §19.4 |
| R6 | Refresh `handoff.md` from the remote state | DONE by this file; closes when pushed (section 19) | |
| R7 | Network-redesign study | **OPEN, not started** | section 17 |
| R8 | Do not start LSM/A9/C3, D9 or Dependabot yet | STANDING | section 3, item 13 |
| R9 | Reply in English | STANDING | item 11 |
| R10 | Revoke the GitHub token | **OPEN (user action)** | section 15 |

### The 28 checklist items (reconciliation §18.2 is authoritative; this is a copy)

**PASS (22):** A2, A3, A4, A5, A6, A7, A8, B1, B2, B3, C1, D1 to D8, D10, D11, D12.

| ID | Status | Exact blocker / what unblocks it |
|---|---|---|
| A1 | BLOCKED | Both paired claims (`NETWORK_ALLOWLIST`, `NET_NAMESPACE`) are withdrawn. Needs the DEBT-039 redesign and a direct `NET_NAMESPACE` gate. The paired-claim invariant mechanism is sound and tested |
| A9 | UNVERIFIED | `AF_VSOCK` probe run and negative (bypass open via `socketcall(2)`); `AF_ALG` not exercisable (kernel lacks it). Needs an LSM-enabled host (active AppArmor or SELinux policy) with a Docker release containing the socketcall fix. `SECCOMP` stays unclaimed |
| B4 | EXCEPTION ACCEPTED | `handoff.md` is on no allow-list; accepted by the user, `handoff.md` only. Not a PASS, not general compliance. The reconciliation document's standing is unchanged (authorized by the base prompt's definition of done, not named in B4's list) |
| C2 | FAIL | DEBT-039: B tunnelled through A's proxy on the shared gateway. Needs the redesign and a passing concurrent A/B test |
| C3 | BLOCKED | Needs the same host as A9: exploit probe blocked and a benign compat probe still working, recorded together. Not N/A |
| D9 | UNVERIFIED, BLOCKED | No lifecycle-event producer exists anywhere (nothing outside tests imports `core.sandbox`). Needs a decision: backends publish through `EventStream`, or D9 is amended. Not opened |

Tally: 22 + 1 FAIL + 3 BLOCKED (A1, C3, D9, counted once) + 1 UNVERIFIED (A9) + 1 EXCEPTION ACCEPTED (B4) = 28. `_CAPS` is **7 of 12**: `CGROUP_MEMORY`, `CGROUP_PIDS`, `FILESYSTEM_JAIL`, `MOUNT_NAMESPACE`, `NO_NEW_PRIVS`, `PID_NAMESPACE`, `UTS_NAMESPACE`. Absent: `NETWORK_ALLOWLIST` and `NET_NAMESPACE` (withdrawn), `NETWORK_DENY_DEFAULT`, `SECCOMP`, `USER_NAMESPACE` (never earned).

## 6. Current Verified State

**VERIFIED**
- `origin/sandbox-fabric` = `a574091` before this handoff's commit; `origin/main` = `69df55f`; branch `docs/known-issues-debt-039-debt-021` = `d379352`. (Unauthenticated `git ls-remote` on 2026-10-03.)
- PR #47 merged. Its required checks were green: `tests`, `drift-and-ownership`, CodeQL (Analyze actions, Analyze python), Graphify. Only `KNOWN_ISSUES.md` changed (+2 −1); base was `4ab5345`. `KNOWN_ISSUES.md` on `main` has one DEBT-039 row (priority "Not yet triaged — to be set in review") and the rewritten DEBT-021 row ("explicitly incomplete", "stays open", priority Low, "not on `main`").
- Code and tests are **unchanged since `2e8c74c`**: `git diff 2e8c74c HEAD -- core tests` is empty (the later commits touch only `handoff.md` and the reconciliation document). The test evidence below was produced at `2e8c74c` and still applies. **No test was rerun this session** because nothing but documentation changed.
- At `2e8c74c`: DockerBackend suite 88/88 on three consecutive runs; full `tests/core/sandbox` 147 passed in one run; mypy clean on `docker_backend.py` and `test_docker_backend.py`; 0 containers, 0 shared-network endpoints and 0 artifact temp dirs after every run.

**IMPLEMENTED BUT NOT VERIFIED:** nothing known.

**PROPOSED (not decided):** DEBT-039's priority and impact wording (left for the reviewer); the per-sandbox network/proxy binding as a design direction; the §17.5 follow-ups as separate debts.

**BLOCKED / UNVERIFIED / FAIL:** the six items in section 5.

**UNKNOWN:** the identity of the single unreproduced DockerBackend failure (v2 section 11); the cause of the `test_net_proxy.py` flake; the mechanism behind the C2 finding beyond the code-reading hypothesis; whether the 3 Dependabot findings on the default branch matter to the sandbox (never investigated).

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1`, remote `origin` = `https://github.com/1h0lde4/ocbrain-v4.1.git`
- Work branch: `sandbox-fabric`. Base branch: `main`.
- **Divergence:** `sandbox-fabric` is 36 commits ahead of and 27 behind `main` (merge-base `2e5cfc0`). The user merged `main` into `sandbox-fabric` twice (`68fd460`, `565ea3a`) and `main` has moved since (it now has the CodeQL work and PR #47). So **`sandbox-fabric`'s own `KNOWN_ISSUES.md` still carries the old DEBT-021 row and no DEBT-039**; `main`'s is the authoritative register. Merging `main` into `sandbox-fabric` is the user's call; do not do it unprompted.
- Implementation and docs checkpoint ("transfer commit"): **`a574091`**, pushed and verified. Parent `fd7f057` (handoff v2), then `2e8c74c`.
- Commits this session after v2: `a574091` (reconciliation §19.4 and the §18 edits).
- Handoff commit: the commit that last touched this file. Find it with `git log -1 --format=%H -- handoff.md`; its parent is `a574091`.
- `main` merge commit for PR #47: `69df55f` (parents `4ab5345`, `d379352`). The branch `docs/known-issues-debt-039-debt-021` still exists on the remote (not deleted).
- Working tree: clean when this file was written. No relevant untracked or ignored files.
- The local clone is `/home/claude/ocbrain-v4.1` in the session container only; reclone from the remote.

## 8. Active Files / Modified Files / Artifacts

- `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`: the evidence narrative. For workstream (B) read **§17** (17.2 the finding and its caveats, 17.4 the invariant, 17.5 separate follow-ups, 17.7 the verbatim reproduction script and output, 17.8 the `NET_NAMESPACE` withdrawal and its future gate), then §18 and §19 (**§19.4 is the completion decision**).
- `core/sandbox/backends/docker_backend.py`: the implementation. Around its create path it builds the shared network and constructs `AllowlistProxy(bind_ip=gateway_ip, allowed_hosts=…)` (found by search this session at roughly line 625; line numbers drift). I did not otherwise re-read it this session.
- `core/sandbox/backends/_net_proxy.py`: the existing `AllowlistProxy`, imported but never modified by DockerBackend (addendum B3). The redesign may legitimately change it. **Not read this session.**
- `tests/core/sandbox/test_net_proxy.py`: the flaky file (section 11). `tests/core/sandbox/test_docker_backend.py`: 88 tests.
- `KNOWN_ISSUES.md` (on `main`): DEBT-021, DEBT-038, DEBT-039 rows. It is about 174 KB with very long lines (a single row can run to tens of KB); use `grep … | cut -c1-200` and never print it whole.
- `handoff.md`: this file.
- Not in the repo and not reproducible from it: the scratch pytest plugin and mutation helper (v2 section 14); the stale `.bundle` file (delivered to the user earlier); a second, newer bundle of `a574091` (delivered to the user, also stale now that everything is pushed).

## 9. Changes Made

Since version 2:
- `a574091`: reconciliation §19.4 (completion decision, Result 2, the four decisions verbatim, the six non-PASS items with blockers, the narrow B4 acceptance); the §18 headline, the status vocabulary (new status `EXCEPTION ACCEPTED`), the B4 row, and the B4 bullets in §18.6 and §18.8. Documentation only.
- PR #47 / `69df55f` on `main`: DEBT-039 registered, DEBT-021 rewritten. `KNOWN_ISSUES.md` only.
- This file (version 3).
- **No code, test, capability, schema or contract change.** `_CAPS` is unchanged at 7 of 12.

Cumulative behavior changes of the DockerBackend workstream (v2 section 9): `create()` cleans or retains every acquired resource; `destroy()` confirms removal before forgetting a handle and runs under a per-handle lock; `cancel()` records intent and `run()` enforces it; a second `run()` raises `DockerBackendError`; `NETWORK_ALLOWLIST` and `NET_NAMESPACE` are withdrawn.

## 10. Decisions & Rationale

Settled earlier (v2 section 10), condensed: DEC-1 D10 stays inside the DockerBackend module and its tests. DEC-2 `NETWORK_ALLOWLIST` withdrawn. DEC-3 `NET_NAMESPACE` withdrawn (claim only; implementation unchanged); re-earned only by a direct committed test, and re-earning it does not resurrect `NETWORK_ALLOWLIST` or C2. DEC-4 the shared network's lifecycle (persist vs remove) is **undecided** and belongs to the redesign. DEC-5 C2 = FAIL; DEBT-039 is a separate security finding; the invariant (section 4) and the concurrent A/B gate. DEC-6 the A9/C3/D9/B4 statuses. DEC-7 D11 = PASS via record retention plus a per-handle lock. DEC-8 cancel enforcement lives in `run()`; `cancel()` never waits for start and no lock is added. DEC-10 tests assert effective state, not the built request.

New this session:

| ID | Decision | Status | Authority | Reopen condition |
|---|---|---|---|---|
| DEC-9 | The id is **DEBT-039** (not DEBT-038, which is `main`'s `/distill` `module_name` traversal, PRs #37/#38) | Settled | User confirmation | n/a |
| DEC-11 | `sandbox-fabric` completion = Result 2, explicitly incomplete | Settled | User | New evidence on a non-PASS item |
| DEC-12 | B4 exception accepted for `handoff.md` only | Settled | User | The user explicitly extends it |
| DEC-13 | D9 stays BLOCKED; no `EventStream` workstream within the closure | Settled | User | The user opens it |
| DEC-14 | The network redesign was not opened inside the closure; the user then listed the *study* as the step after the handoff refresh | Settled | User | n/a |
| DEC-15 | DEBT-039 and the DEBT-021 update go through a separate PR; DEBT-039's priority is left untriaged for the reviewer | Settled | User | n/a |
| DEC-16 | PR #47 was merged with a **merge commit** (the repo's recent convention, #40 and #43). The user did not name a method | Assistant's choice, no objection | n/a | The user prefers another method |
| DEC-17 | The merged PR branch was left undeleted (repo default) | Assistant's choice | n/a | The user asks for deletion |

## 11. Investigation Already Performed

| Area | Inspected | Result | Revisit trigger |
|---|---|---|---|
| Closure audit | Checklist read literally; the 28-item matrix; B and D12 audits | Reconciled (reconciliation §18, §19) | A checklist amendment |
| The C2 finding | Scratch A/B probe (reconciliation §17.7) | B reached A's proxy: `403`, `200`, `200` for the three probes. B was *handed* A's port; scanning for it was **not** demonstrated; only `CONNECT` was tried | The study |
| Mechanism | Code reading: each sandbox's `AllowlistProxy` binds the one shared network's gateway IP; `enable_icc=false` constrains container-to-container traffic, not container-to-gateway | **Hypothesis, not separately verified** | The study |
| Possible LSM on the dev host | Kernel config, `/sys/kernel/security/lsm` | AppArmor not compiled in; SELinux compiled in but no policy loaded; a policy load was not attempted | A host with a policy loaded |
| Artifact collector | Symlinks, a FIFO | Fixed or recorded in v2 | n/a |
| Event producers (D9) | `grep` across the repo | None publishes | A producer is added |
| `main` branch protection (GitHub API) | Rules for `main` | Required checks `tests` and `drift-and-ownership`; "strict" (branch must be up to date); no required reviews; admins enforced; no rulesets. CI runs on PRs to `main` and takes roughly four minutes. All three merge methods are allowed; `main` history uses merge commits | A rules change |
| `KNOWN_ISSUES.md` shape | Structure | Table columns: ID, Category, Description, Priority, Impact. Rows for DEBT-037, DEBT-038, DEBT-039 sit together in the Active table | n/a |
| Not inspected | `_net_proxy.py` internals; the shared-network creation code in `docker_backend.py`; the plain-HTTP path's two unexplained behaviors; Dependabot findings | | The study |

## 12. Failed Attempts / Dead Ends

Version 2's table (section 12) still stands: a combined D5 symlink test; a `kill -9 $$` PID 1 test; a noisy D10 red phase; running the FIFO test in-process; sourcing the Docker start script with output discarded; bash-isms in `dash`; pushing before checking the remote; a custom seccomp profile for the `AF_VSOCK` bypass (seccomp cannot filter `socketcall(2)` arguments). New this session:

| Approach | Result | Cause | Retry? |
|---|---|---|---|
| Pushing `a574091` with no credentials | `fatal: could not read Username` | No authentication is configured in the container | Not until the user supplies credentials (they did, section 3 item 12) |
| Counting statuses by the first word of the Status cell | Printed 22 / 1 / 2 / 2 / 1 | D9's status is `UNVERIFIED — BLOCKED` and the script bucketed it by its first word | The intended tally counts D9 **once, under BLOCKED**; say so when re-deriving it |

## 13. Verification Evidence

- Tally: the §18.2 Status column parsed after the edit: 28 rows; A1 and C3 BLOCKED, A9 UNVERIFIED, D9 `UNVERIFIED — BLOCKED`, C2 FAIL, B4 EXCEPTION ACCEPTED, 22 PASS (22 + 1 + 1 + 3 + 1 = 28 with D9 counted under BLOCKED).
- `git diff 2e8c74c HEAD -- core tests` → empty. `a574091` touches one file (the reconciliation document); `fd7f057` touches one file (`handoff.md`).
- Push of `a574091`: fast-forward `fd7f057..a574091`; `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/sandbox-fabric` returned `a57409130a9873fe4c40f984912e8fdfa1737e92` (unauthenticated).
- PR #47: opened (head `d379352`, base `4ab5345`, `main` tip unchanged at open); 1 file, 1 commit; required checks green; `mergeable_state` was `clean`; merged with a head-SHA guard as `69df55f`; afterwards `git ls-remote` showed `main` = `69df55f`, `git diff 4ab5345 origin/main` listed `KNOWN_ISSUES.md` only, and `grep -c '^| DEBT-039 |'` on `main`'s file returned 1.
- For all test, mypy, mutation (M1 to M26), orphan-check and `test_net_proxy.py` flake evidence, see version 2, section 13 and reconciliation §§17 to 19. **Standalone `test_net_proxy.py` failed 3 of 6 runs** (`test_plain_http_to_allowed_host_is_forwarded` twice, `test_connect_to_allowed_host_tunnels_real_data` once); inside the full suite it usually passes, which hides the frequency. DockerBackend does not touch it.

## 14. Environment / Tooling Assumptions

- Dev container (carried from version 2; **not re-observed this session**, because Docker was never started): Ubuntu 24.04; kernel `6.18.44-fc-v50` (a Firecracker microVM; the value drifts); Python 3.12; Docker Engine 29.1.3 (Ubuntu's `docker.io`); cgroup v1 with `cgroupfs`; no AppArmor; shell is `dash`. **The Docker daemon is not running in a fresh container**, and the VM can restart mid-session (the filesystem and the Docker image survive; the daemon does not). Workstream (B) will need Docker to reproduce the finding.
- Start script (recreate at `/home/claude/start_docker.sh`; source it with `. /home/claude/start_docker.sh`, **never discard its output, abort unless it prints `docker: ready`**; a cold start can exceed the 20 s wait):

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

- Install if absent: `apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io gcc-multilib libc6-dev-i386`; `pip install pytest pytest-asyncio mypy --break-system-packages`. No registry is reachable (`registry-1.docker.io`, `ghcr.io` return 403).
- Test image (not in git; rebuild): `tar -C / -c --exclude=proc --exclude=sys --exclude=dev --exclude=tmp --exclude=run --exclude=home/claude --exclude=mnt --exclude=var/lib/docker --exclude=var/lib/containerd bin sbin lib lib64 usr etc | docker import - ocbrain-test/base:local`, then `export OCBRAIN_SANDBOX_DOCKER_IMAGE=ocbrain-test/base:local`.
- Test commands: `python3 -m pytest tests/core/sandbox/test_docker_backend.py -q --asyncio-mode=auto -p no:cacheprovider` (about 55 s); the full `tests/core/sandbox` with `-rf --tb=short`; `python3 -m mypy core/sandbox/backends/docker_backend.py tests/core/sandbox/test_docker_backend.py --ignore-missing-imports --explicit-package-bases`. After each run, the orphan check: `docker ps -aq | wc -l` is 0, the shared network has no endpoints, and `ls -d /tmp/ocbrain-docker-artifacts-*` is empty.
- The reproduction script for the finding is verbatim in reconciliation §17.7. It uses `ocbrain-test/base:local` and writes under `/tmp/xsb-A` and `/tmp/xsb-B`.
- Network egress from the container is allowlisted: package registries, `github.com`, `api.github.com`, `raw.githubusercontent.com` and a few others. The GitHub REST API worked from the container for opening and merging a PR.
- **Credentials.** No secret is stored in the repo, in this file or in memory. The user pasted a GitHub personal access token into the chat (it is also in their preferences). It was used in this session for exactly three kinds of operation, all explicitly requested: pushing `sandbox-fabric`, pushing the PR branch, and the REST calls that opened, checked and merged PR #47. It was passed per command only (`git -c http.extraheader="Authorization: Basic …"` for git, `Authorization: Bearer …` for the API), output was redacted, nothing was written to git config, a remote URL or a file, and it was never printed. **Do not copy it anywhere.** The user has said twice that it should be revoked and it may already be. If a push or API call returns 401, stop and ask for new authentication. If authentication is missing, ask the user to supply it; do not look for it in memory or files.

## 15. Unresolved Questions / Risks / Blockers

| Item | Evidence | Options | Safe to continue without it? |
|---|---|---|---|
| **Study deliverable and branch** | The user said "start the network-redesign study" and nothing more | Ask: a document under `docs/architecture/`? on a new branch from `sandbox-fabric` or from `main`? | **No: ask first** |
| **Token revocation** | The token is in the user's preferences and in this conversation, and was used for several remote writes | The user revokes it and configures authentication in the environment | Yes, but nothing should be pushed without valid authentication |
| **DEBT-039 priority** | Row says "Not yet triaged — to be set in review" | A reviewer sets it; do not set it unprompted | Yes |
| **B4 and the reconciliation document** | The acceptance names `handoff.md` only | The user may extend it explicitly | Yes |
| **`sandbox-fabric` diverged from `main`** (36 ahead, 27 behind) | Section 7 | The user decides if and when to merge `main` in | Yes |
| **Redesign open questions** | DEC-4; scanning for a sibling's port not demonstrated; only `CONNECT` tried; plain-HTTP path has two unexplained behaviors; the mechanism is a hypothesis; whether an `AF_VSOCK` socket offers another route is untested | The study | It is the study |
| **D9** | No event producer | A later decision | Yes |
| **A9 / C3 host** | See section 5 | An LSM-enabled host plus a Docker release with the socketcall fix; a kernel with `AF_ALG` | Yes |
| **Dependabot** | Every push prints "3 vulnerabilities (1 critical, 2 high)" on the default branch; never investigated | A different workstream; needs the user's go-ahead | Yes |
| §17.5 follow-ups | `RUNNING` left after a failed `docker start` spawn; the create-unwind residual; a finalizer for failing D10 tests; the stale module docstring in the test file; a relative escaping symlink empties the manifest silently | Separate debts | Yes |
| Untested | `docker build` `RepoDigests`; artifact hard links and workspace size; `FILESYSTEM_JAIL` vectors (`/dev/shm`, `/proc`, `/sys`, mount attempts) | Optional | Yes |

## 16. Relevant Information / References

- Reconciliation document, §§17 to 19 (see section 8).
- `docs/architecture/PROJECT_INSTRUCTIONS.md`: §18.4.8 is the handoff format used here.
- `KNOWN_ISSUES.md` on `main`: DEBT-021 (rewritten), DEBT-038 (`/distill` traversal), DEBT-039 (this finding).
- PR #47: `https://github.com/1h0lde4/ocbrain-v4.1/pull/47`.
- Upstream references in reconciliation §12: `moby/moby#52537` (the earlier `AF_ALG` fix) and `moby/moby#53551` (the socketcall/`AF_VSOCK` fix, Engine 29.8.0). The installed Docker 29.1.3 predates both.
- Earlier handoffs: v1 `git show 9310155:handoff.md`; v2 `git show fd7f057:handoff.md`.
- Repository caution: the user's rule elsewhere in this project is that a merge needs an explicit instruction every time and the word "continue" is not authorization to merge. In this session PR #47 was merged only on the user's explicit "Open → verify → CI → merge" instruction.

## 17. Next Steps

In order. Step 1 and 2 are mandatory before any study work.

1. **Resume and verify** (section 18). No code change is expected from this step.
2. **Ask the user** (one message): where the study should live and on which branch, and what "done" means for it; and confirm that the study stops at a design with an evidence plan, with implementation only after a separate go-ahead. Expected verification: the answer is recorded in the next handoff or the study document.
3. **Recreate the Docker host** (section 14) and confirm `docker: ready`. Rebuild the test image.
4. **Reproduce the baseline.** Run the §17.7 probe on the current host and confirm the same three results (`403`, `200`, `200`). Why: the kernel and Docker drift; the study should start from a reproduced finding, not an inherited one. Also run `test_net_proxy.py` alone several times to establish the flake rate before changing anything.
5. **Read** `_net_proxy.py` and the network-setup and proxy-construction code in `docker_backend.py`. Establish where the proxy binds, how the shared network is created and removed, and how a proxy could identify its caller.
6. **Test the hypothesis separately** (§17.2 calls it unverified): does the proxy accept any caller on the gateway; is the port discoverable by scanning (not yet demonstrated); does plain HTTP behave like `CONNECT`; do the two unexplained plain-HTTP behaviors (§17.5) bear on the finding.
7. **Enumerate design options against the invariant**, with trade-offs and a migration path: a per-sandbox network and proxy binding is one candidate, a source-identity check in the proxy is another, and there may be more. None is a decision. Include the shared-network lifecycle decision (DEC-4).
8. **Specify the gates** the redesign must pass: the concurrent A/B test with deliberately different allowlists (shape in §17.7), and the direct `NET_NAMESPACE` gate (§17.8: netns distinct from the host's; concurrently created sandboxes have pairwise-distinct netns). Passing the second re-earns `NET_NAMESPACE` only.
9. **Write the study** where the user said, on its own branch. Keep it to the study: no code change unless the user authorizes it. Promote any durable result into `KNOWN_ISSUES.md` or `CURRENT_STATE.md` only through a separate PR.
10. **Push** the study branch with the fast-forward guard (section 18). Open a PR only when asked, and merge only on an explicit instruction.
11. Do **not** start A9/C3, D9, Dependabot or the §17.5 follow-ups inside this workstream.

Expected verification for step 4: the three probe lines match §17.7's output.

## 18. Resume Instructions

1. `git clone https://github.com/1h0lde4/ocbrain-v4.1.git` (public; read access needs no token); `git switch sandbox-fabric`. Confirm `git log -1 --format=%H -- handoff.md` is an ancestor of, or equal to, `HEAD`, and that `a574091` is an ancestor of `HEAD`.
2. Confirm the remote: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/sandbox-fabric refs/heads/main`. `sandbox-fabric` should be at or beyond the handoff commit; `main` should be at or beyond `69df55f`. If `sandbox-fabric` has moved ahead (the user merges into it from their own machine), **fast-forward local to it before committing anything.**
3. Confirm `main`'s register: `git show origin/main:KNOWN_ISSUES.md | grep -c '^| DEBT-039 |'` returns 1.
4. Read reconciliation §§17 to 19 before trusting any status in this file. The repository is the authority; this file is a transfer record.
5. Before any push: `git fetch`; push only if `origin/<branch>` is an ancestor of `HEAD`. If it is not, **stop and report; never force.**
6. Reply in English. Do not use, request, print or store the token (section 14).
7. Begin from section 17, step 2. Do not reconstruct completed work.

## 19. Transfer Status

**TRANSFER READY once this file is on the remote.** The implementation checkpoint (`a574091`) and `main` (`69df55f`) are pushed and verified. The criterion for this version: `git ls-remote https://github.com/1h0lde4/ocbrain-v4.1.git refs/heads/sandbox-fabric` shows a commit at or beyond the one returned by `git log -1 --format=%H -- handoff.md`. The session pushes the handoff commit immediately after writing it and verifies it, so if you are reading this file from the remote, that criterion is met and this paragraph is simply a description of how it was met.

Condition by condition: original task preserved (section 2, verbatim); material instructions preserved (section 3, with version 2 for items 1 to 8); scope and success criteria (section 4); requirements accounted for (section 5); current state verified (section 6); decisions (section 10); investigation and failed approaches (sections 11, 12); verification (section 13); environment (section 14); all material work in Git: yes; implementation checkpoint pushed: yes; handoff committed: immediately after this file is written; no secret recorded; exact next action defined: yes (section 17, step 1 then 2).
