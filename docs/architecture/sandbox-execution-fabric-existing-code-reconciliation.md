# Sandbox / Execution Fabric — Existing-Code Reconciliation

**Status:** Reconciliation complete. Ready to inform a revised kickoff prompt (report §15) for Phase 1 implementation.
**Date:** September 11, 2026
**Scope:** Read/reconcile pass triggered by `docs/research/sandbox-execution-fabric/deep-research-report.md` (external deep-research report on sandbox/execution-fabric design; fact-checked and corrected for 5 errors prior to this pass — see §1). Corresponds to the report's own §3 ("l'état de l'hôte/du dépôt") existing-code check, performed here against the live repository rather than deferred into Phase 1 implementation.
**Method:** Fresh read of `main` (this branch's base). Documentation-first per `PROJECT_INSTRUCTIONS.md` §18.4.1: `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, `IMPLEMENTATION_ROADMAP.md` checked for sandbox/execution/watchdog/validationgate mentions before touching source. Targeted full reads (not class-name grep alone) of `core/runtime/`, `core/capabilities/`, `core/cognitive/learning.py`, `core/skills/skill_interface.py`, `modules/system_ctrl/module.py`, `modules/coding/module.py`, `core/events/event_stream.py`, `core/workers/`. No runtime code touched — this is a design/reconciliation pass only, per the Architecture Freeze Principle.

---

## 1. Corrections applied to the source report

Five factual errors, checked against primary sources and corrected in place in `docs/research/sandbox-execution-fabric/deep-research-report.md` (this same commit):

1. **nsjail license:** MIT → Apache-2.0 (narrative mention and comparison-table row both fixed).
2. **nsjail "dernier commit 2021" / reduced-maintenance claim:** unsupported — the repo shows discussion activity into 2025–2026 — removed and replaced.
3. **Firecracker device count:** "5 devices" is contested even within Firecracker's own materials (main site says 5, the repo's own FAQ says 6, having added `virtio-balloon`). Both mentions updated to reflect the discrepancy rather than assert a single stale number.
4. **OpenHands/Sysbox row:** corrected a license conflation — OpenHands itself is open-source; the proprietary tier is Sysbox Enterprise Edition, which is itself reportedly being discontinued as a standalone product in favor of the open Community Edition.
5. **Daytona:** removed an unexplained, unsupported "(mobile)" tag; added the independently-verified June 2026 closed-source transition, since the report's "Proprietary" table classification is correct but recent, and worth dating.

## 2. What already exists — inventory against the report's proposed contracts

Legend: **Extend** = build on top of this · **Reuse philosophy** = same approach, new implementation · **Publish through** = route new events here · **Collision risk** = no functional overlap but name is contested · **Greenfield** = nothing exists.

| Report proposes | Closest existing thing | Where | Verdict |
|---|---|---|---|
| `SandboxPolicy` / `RuntimeCapabilities` (timeout, memory, import restrictions) | `SkillExecutionConfig` — `mode` (default `"inline"`), `timeout_sec`, `memory_limit_mb`, `allowed_imports` | `core/skills/skill_interface.py:24` | **Extend.** Declared on skill metadata; confirmed by repo-wide grep to be read nowhere else — a real but currently inert rudiment, not a false lead. |
| Deny-by-default execution / admission | Action allowlist (`ACTION_HANDLERS`) + path jail (`SAFE_ROOT` / `_safe_path()`) | `modules/system_ctrl/module.py` | **Reuse philosophy, not code.** Same-process jail, not container/VM isolation — the report's own threat model already goes further. Has one documented, fixed vulnerability class (shell-injection, "A7 audit fix") worth reading before designing the new admission chain — same failure mode is easy to reintroduce. |
| `ExecutionEvent` | `EventStream` — the event-sourced backbone | `core/events/event_stream.py` | **Publish through.** Almost certainly what the report's own placeholder term "Event Backbone" (§3) was gesturing at without knowing the real name. No case found for a second, parallel event system. |
| `ExecutionRequest` / `ExecutionHandle` / `ExecutionResult` | `ExecutionContext`, `ExecutionRuntime`, `ExecutionOutcome`, `ExecutionBudget`, `ExecutionPolicy`, `ExecutionWatchdog` / `GraphExecutionWatchdog`, `ExecutionGraph`, `ExecutionNode`, `ExecutionRegistry` | `core/runtime/*.py` | **Collision risk — no functional overlap.** This family invokes in-process `Worker` objects for workflow orchestration (`ExecutionRuntime`'s own docstring: "constructs and invokes one Worker for one unit of work"). Nothing to do with sandboxed code execution. Namespace decision in §3. |
| GitHub-sourced "capabilities" (SBOM/Sigstore admission chain) | `CapabilityRegistry`, `CapabilityRequest`, `CapabilityResult`, `CapabilityContract`, `CapabilityType`, plus planner-side `CapabilityDiscoveryRequest` / `CapabilityMatch` | `core/capabilities/`, `core/cognitive/planner.py` | **Collision risk — no functional overlap.** Existing usage is entirely about routing a request to a registered orchestration capability. Different concern, same word. Naming decision in §3. |
| Admission gate before execution | `validation_gate()` | `core/cognitive/learning.py:377` | **Collision risk — name is taken.** Gates learning/cognitive decisions through `GovernanceKernel.evaluate_action()`. Notably a single async function, not a class. |
| `ArtifactManifest` | `CognitiveArtifact` (Protocol) | `core/cognitive/intent.py:54` | **No real overlap** — different layer entirely, name proximity only. |
| Container/VM isolation backend (Docker/gVisor/Kata/Firecracker) | — | — | **Confirmed greenfield.** Zero hits for docker/firecracker/gvisor/kata/microvm anywhere in application code (`*.py`, excluding tests). |
| `CoderWorker` as a consumer | Not yet built | `KNOWN_ISSUES.md` still lists it under Future Cognitive Workers; absent from `core/workers/` | **No integration target exists yet.** Building the fabric ahead of its primary consumer is defensible (infrastructure before consumer), but it means Phase 1 can't be integration-tested against a real caller. |

## 3. Naming decisions

Recorded here so they aren't re-litigated per file during implementation:

- **New contracts live under a `Sandbox*` prefix, in a new `core/sandbox/` package — not `Execution*`.** `core/runtime/` already owns `Execution*` for workflow-node orchestration. Recommend `SandboxRequest` / `SandboxHandle` / `SandboxResult` / `SandboxEvent` in place of the report's `Execution*`-prefixed names. `SandboxPolicy` (the report's own name) survives unchanged — it doesn't collide, and it's the name that should eventually point at `SkillExecutionConfig`'s replacement/superset.
- **"Capability" is avoided for the GitHub-admission concept.** Recommend "extension" or "external package" (e.g. `ExtensionManifest` rather than an implicit `CapabilityManifest`) to keep distance from `core/capabilities/`'s existing, unrelated meaning.
- **"ValidationGate" is avoided.** Recommend `AdmissionGate` (or `SandboxAdmissionGate`) for whatever gates a `SandboxRequest` before execution.
- **"Sandbox" itself is kept, deliberately.** It's the report's central term, it's directionally correct (this genuinely is a stronger, different kind of sandbox than `system_ctrl`'s path jail), and avoiding it would fight the report's own vocabulary for no real benefit. The distinction from the existing lighter-weight sandbox should be one documented sentence in the new code's module docstring, not a renaming exercise.

## 4. Non-blocking observations

- The repository's actual current state is considerably busier than the report's own framing assumed: a Kernel v1.0 freeze audit is open (`NOT_FREEZE_READY`, pending a classification decision on DEBT-020), and a Context Engineering Security Audit has five unresolved regressions (DEBT-019). Neither blocks sandbox-fabric work; both are worth knowing about before assuming `main` is quiet.
- `core/runtime/watchdog_decision.py`'s recent unification (`ADR_KERNEL_02_WATCHDOG_UNIFICATION`, Sept 5 2026 — two independent Watchdog implementations collapsed into one shared, pure `decide()` function behind a `ProgressSignal` Protocol) is a useful precedent if the sandbox fabric ends up needing its own resource-limit watchdog: the same split (pure decision function + typed signal Protocol) rather than a third bespoke implementation.
- No tracking-doc sync (`CURRENT_STATE.md` / `KNOWN_ISSUES.md` / `IMPLEMENTATION_ROADMAP.md`) was performed as part of this reconciliation — those live on `main` and are out of scope for a `sandbox-fabric`-branch commit under this project's branch-per-layer discipline. Recommend a dedicated sync pass once Phase 1 actually lands.

## 5. Recommendation

Ready to fire an updated version of the report's §15 kickoff prompt, incorporating: the five corrections (§1), the namespace decision (`core/sandbox/`, `Sandbox*` prefix, §3), the two reuse targets (`SkillExecutionConfig`, `EventStream`, §2), and the two renamed concepts ("extension" instead of "capability"; `AdmissionGate` instead of `ValidationGate`). No blocker found that would delay Phase 1 (Docker/OCI backend, per the report's own plan).

## 6. Phase 1 progress (update, September 11 2026)

Phase 1 was started in this same session, in this same environment. One environment fact changed the plan: `docker`, `runc`, and `podman` were all verified absent here (`which` found none of them), so the "docker run" half of §13 point 4's "runc rootless ou docker run" choice was not available to build or test. The "runc rootless" half was: `unshare` (user/mount/pid/net namespaces), cgroup v1 (memory, pids controllers, writable), and `PR_SET_NO_NEW_PRIVS` via `prctl` were all empirically verified present and working before any production code was written.

**Built and passing (36/36 tests, 3 consecutive clean runs, no leaked cgroups or processes after `destroy()`):**

- `core/sandbox/contracts.py` — all Phase 1 contracts (`SandboxPolicy`, `SandboxRequest`, `SandboxHandle`, `RuntimeCapabilities`, `ArtifactManifest`, `SandboxResult`, `SandboxEvent`), frozen dataclasses, fail-closed `__post_init__` validation.
- `core/sandbox/backend.py` — the `SandboxBackend` ABC (create/run/cancel/destroy/inspect).
- `core/sandbox/admission.py` — `AdmissionGate`-equivalent `check_admission()`, deny-by-default; rejects any request naming `allowed_hosts` since no Phase 1 backend enforces an allowlist yet.
- `core/sandbox/events.py` — thin adapter publishing `SandboxEvent` through the real `EventStream` (`core/events/event_stream.py`), not a parallel bus. Verified against a real `SQLiteEventStore` on a temp DB, not just a mock.
- `core/sandbox/backends/stub_backend.py` — the report's own anticipated "stub minimal" for interface tests; claims zero `SandboxCapability` values so `AdmissionGate` structurally refuses to admit real work to it.
- `core/sandbox/backends/namespace_backend.py` + `_ns_init.py` — the real, working Phase 1 backend. Empirically verified, each as its own adversarial test: `echo Hello` runs; `/root` (absent in the jail) fails cleanly; an absolute symlink to `/etc/passwd` created before chroot resolves inside the jail afterward, not to the host file; the same holds for `../../etc/passwd`-style traversal; a fresh net namespace has no route out at all (`ENETUNREACH`) with zero firewall rules needed; a memory-limit violation is detected via the cgroup's own `memory.failcnt` and reported as `RESOURCE_EXCEEDED`; a fork bomb is stopped by `pids.max`; a timeout terminates a long-running command; `cancel()` kills the entire OS process group and leaves nothing orphaned; produced files are collected as artifacts with a real sha256, and the read-only base-rootfs bind points are not mistaken for artifacts.

**Two real bugs found and fixed by these tests, not papered over:**

1. `cancel()`'s result was classified `COMPLETED` instead of `CANCELLED` for a `SIGKILL`-terminated process — fixed by tracking `cancel_requested` on the backend's internal run-state.
2. OOM detection assumed the memory-limit violation always surfaces as a negative (signal-killed) exit code on the directly-tracked process. Empirically false: when the limit is hit, the kernel's OOM killer can strike *any* process sharing the cgroup (it's inherited across fork/exec across the whole `unshare` → `_ns_init.py` → payload chain), which sometimes surfaces as `unshare` itself exiting with an ordinary *positive* status after catching its child's death. Fixed by checking the cgroup's own `memory.failcnt` first, unconditionally, rather than inferring OOM from exit-code sign.

**Deliberately not attempted here (needs a host with Docker, tracked rather than silently skipped):**

- A `DockerBackend` implementing the same `SandboxBackend` interface via `docker run` — nothing in the interface or contracts should need to change for this to slot in.
- Enforcing a non-empty `SandboxPolicy.allowed_hosts` (currently rejected by `AdmissionGate` rather than silently ignored) — tracked as `KNOWN_ISSUES.md` DEBT-023.
- Mermaid diagrams (report §15 point 10) and a French-language design-doc pass.

No tracking-doc sync (`CURRENT_STATE.md` / `KNOWN_ISSUES.md` / `IMPLEMENTATION_ROADMAP.md`, all on `main`) was performed as part of this Phase 1 push, consistent with §4 above. (Since resolved — see §7.)

## 7. DEBT-022 closed: seccomp-bpf denylist + UTS namespace (update, September 12 2026)

`core/sandbox/backends/_seccomp.py` binds directly to `libseccomp.so.2` (found already present in the build environment — `ldconfig -p | grep seccomp`) via ctypes, rather than hand-rolling raw BPF instructions: for a security boundary, leaning on a widely-used, independently-audited library is the right trade, not a shortcut. Default-ALLOW with a curated ~29-syscall denylist (`ptrace`, `mount`/`umount2`, kernel-module and `kexec` syscalls, clock manipulation, keyring syscalls, `bpf()`, `perf_event_open`, `userfaultfd`, nested `unshare`/`setns`, among others), `SCMP_ACT_ERRNO(EPERM)` rather than `SCMP_ACT_KILL` so a blocked call looks like an ordinary permission failure a program can handle. Loaded in `_ns_init.py` after the setup phase's own bind-mounts (which need `mount()`) and after chroot, so the *payload* is what's actually restricted, not the setup code — order was verified, not assumed, same as everything else in this document.

One assumption from Phase 1 was checked and found wrong in the process: `seccomp_load()` was assumed to need `PR_SET_NO_NEW_PRIVS` set first for an unprivileged caller. Empirically false for this specific configuration — a process that is only *namespace*-mapped root (via `--map-root-user`) already has the equivalent of `CAP_SYS_ADMIN` within its own user namespace, so `seccomp_load()` succeeds either order here. `no_new_privs` is still set first regardless, as ordinary defense-in-depth, not because this configuration requires it.

`--uts` was added to the `unshare` invocation alongside this (same file, same pass): hostname/domainname changes inside the sandbox no longer leak to the host — verified via `socket.sethostname()` inside vs. `socket.gethostname()` on the host, before and after.

8 new tests (4 in `test_namespace_backend.py`, 4 in `test_seccomp.py`), 44/44 total passing, 3 consecutive clean runs, zero leaked cgroups/processes confirmed after a settle delay. mypy clean across all 10 `core/sandbox/*.py` files. `RuntimeCapabilities` now includes `SECCOMP` and `UTS_NAMESPACE`. `KNOWN_ISSUES.md` DEBT-022 should be moved to Resolved in the next tracking-doc sync.

## 8. DEBT-023 closed: `allowed_hosts` via veth + named-netns + forward proxy (update, September 12 2026)

Scoped and built as its own pass, per explicit direction, not mixed into DEBT-022 or the Docker backend.

**What it is:** `core/sandbox/backends/_net_proxy.py` is a stdlib-only HTTP/HTTPS-CONNECT-aware forward proxy. `NamespaceBackend._setup_allowlisted_network()` (called from `create()` only when `request.policy.allowed_hosts` is non-empty) creates a *named* network namespace (`ip netns add`) and a veth pair, fully configures both ends — IPs, interfaces up, loopback up — and starts the proxy on the host-side peer IP, all **before** the sandbox process exists at all. The sandbox side gets no default route: it can reach *only* the directly-connected peer IP, structurally, by the absence of a route — not by a firewall rule that could be misconfigured (the same "deny by construction, not by policy" property the deny-all path already had). `_run_sync()` then launches the payload via `ip netns exec <ns> unshare ... ` (no `--net` flag — the namespace is already provided) and injects `HTTP_PROXY`/`HTTPS_PROXY` (both cases) pointing at the proxy. `AdmissionGate` now admits a non-empty `allowed_hosts` against `NamespaceBackend` specifically, gated on a new `SandboxCapability.NETWORK_ALLOWLIST` — a synthetic-capability test (`test_allowed_hosts_rejected_without_the_specific_capability`) confirms the gate checks for that exact capability, not merely "any network isolation."

**What it is *not*, stated precisely so it isn't overclaimed later:** this is **HTTP(S)-host allowlisting via a forward proxy that the payload must respect (or be pointed at)** — it is not a general, protocol-agnostic network allowlist. A raw non-HTTP TCP or UDP connection to an "allowed" host is still blocked, because only the proxy's own port is reachable at all; nothing routes anywhere else. This is an intentional, disclosed scope boundary matching the report's own worked example (`pip install`, which is HTTP(S)), not a gap discovered after the fact.

**Environment-discovered, not assumed:** `iproute2` (`ip netns`, `ip link`) was absent from the build environment the same way `docker`/`runc`/`podman` were — installed via `apt-get install iproute2` (Ubuntu archive) before writing any code against it, and now a genuinely new system dependency for any real deployment host, on top of `libseccomp.so.2` from §7. The named-netns-first approach (configure fully, then launch the payload into it via `ip netns exec`) was chosen specifically to avoid a race that moving a veth end into an *already-running* `unshare --net` process's namespace would have created — verified empirically (the bare veth-pair-into-existing-netns approach was tried and worked, but the race it would introduce under real concurrent load was reasoned through, not risked; the named-netns-first version was tested instead and adopted).

**Tests:** `test_net_proxy.py` (5, unit-level: plain-HTTP and CONNECT forwarding to a real local server with a real response relayed back, both request styles rejected for a disallowed host with the real target never dialed, exact case-insensitive host matching). `test_allowed_hosts.py` (4, full integration through `NamespaceBackend`: an allowed host is reached through the whole veth/proxy chain by a real sandboxed `urllib` fetch; the same fetch is rejected when the real target isn't on the list; the deny-all path is confirmed completely unaffected; `destroy()` leaves no netns, veth, or listening proxy behind). `test_admission.py` updated: the old test asserting `allowed_hosts` is *always* rejected is gone (it encoded the behavior this section just changed) — replaced with one confirming `NamespaceBackend` now admits it, and one confirming a backend with network isolation but *without* `NETWORK_ALLOWLIST` specifically is still rejected. 54/54 total across the whole `core/sandbox/` suite, 2 consecutive clean runs, zero leaked cgroups/netns/veth interfaces/processes after a settle delay, mypy clean across all 11 files (two `Optional`-narrowing issues the type checker caught in the new code, fixed with explicit asserts rather than silenced).

Docker backend (step 3 of the stated sequence) remains untouched and deliberately out of scope here — it gets its own backend-security comparison before inheriting anything from this pass, not an assumption carried over by default.

## 9. CVE-2026-31431 ("Copy Fail"): AF_ALG/AF_VSOCK blocked (update, September 13 2026)

Found in the course of researching the Docker-backend security comparison that step 3 calls for — the comparison itself is still pending, but this took priority the moment it surfaced, since it's a live gap in code already shipped from this same branch, not a future-work item.

**What it is:** CVE-2026-31431 ("Copy Fail," CVSS 7.8, CERT-EU advisory 2026-005) is a logic flaw in the kernel's `algif_aead` module (the AEAD path of the AF_ALG crypto socket interface), rooted in a 2017 in-place-optimization commit, allowing a controlled 4-byte page-cache write reachable by any unprivileged local user who can open an `AF_ALG` socket. Public PoCs target setuid binaries (`su`, `sudo`) in the page cache — the on-disk file is untouched, so file-integrity monitoring alone won't see it. Explicitly documented as working *inside* containers and namespaces, since it's a kernel-level page-cache issue, not something namespace isolation stops on its own. Upstream fix merged 1 April 2026; distribution rollout was still incomplete as of the sources found. Docker/Moby independently shipped the identical mitigation in their default seccomp profile (moby/moby PR #52501): block `AF_ALG` and `AF_VSOCK` socket creation specifically.

**Why `DENIED_SYSCALLS` (§7) couldn't express this:** that list blocks syscalls by name, unconditionally. The exploit's first step is an ordinary `socket()` call with `AF_ALG` as the address-family argument — and `socket()` itself must stay allowed, since this sandbox's own DEBT-023 network-allowlist proxy depends on ordinary `AF_INET` sockets working. Blocking `socket()` outright wasn't an option; blocking it only for specific argument values was the actual fix, via libseccomp's `seccomp_rule_add_array()` (the array-pointer form of argument-conditioned rules — chosen over the true-variadic `seccomp_rule_add()` because ctypes binds C varargs unreliably, and this is exactly the kind of security-critical code where "unreliable" isn't acceptable).

**Verified honestly, not just claimed:** this host's kernel (6.18.44) doesn't expose `AF_ALG` at all — `socket(38, ...)` fails with `EAFNOSUPPORT` *before any seccomp filter is even loaded*, confirmed by a dedicated test (`test_af_alg_is_unreachable_on_this_host_regardless_of_seccomp`) rather than left as an assumption. That means the exact CVE scenario can't be exercised here to prove the fix blocks it. What *was* verified directly: the argument-filtering mechanism itself, using `AF_INET` as a stand-in — a family that does exist on this host, temporarily configured as the "denied family," confirmed blocked, while `AF_UNIX` remained unaffected (selective blocking by argument value, not a blanket `socket()` block). The same mechanism, with `AF_ALG`'s value in place of `AF_INET`'s, is what the production `DENIED_SOCKET_FAMILIES` list relies on — proven correct in general, applied to a specific case that couldn't be independently re-confirmed on this particular host. Anyone deploying this on a host where `AF_ALG` genuinely exists should re-run the CVE scenario directly rather than trust this substitution blindly.

Also confirmed: ordinary networking is unaffected -- `test_ordinary_sockets_still_work_after_apply` covers `AF_INET`/`AF_UNIX` directly, and the full `test_allowed_hosts.py` suite (which exercises real `AF_INET` sockets through the whole veth/proxy chain) still passes unchanged, since `socket()` itself was never touched.

4 new tests, 58/58 total across `core/sandbox/`, 2 consecutive clean runs, mypy clean across all 11 files.

**Addendum, same day: the `socketcall(2)` bypass Docker's own fix also covers.** moby/moby PR #52501 (the same CVE fix) additionally denies `socketcall(2)` — the legacy 32-bit/compat syscall multiplexer through which `socket()` and friends can be reached under a different syscall number entirely, bypassing a filter that only conditions the native `socket` syscall. Investigated directly, not left as a documented-but-unverified gap: `gcc-multilib` was installed and a small C helper built, using `MAP_32BIT` + inline `int $0x80` to invoke `socketcall(SYS_SOCKET, [AF_INET, ...])` on this build host — mirroring the same technique Docker/Moby's own `AF_ALG_socketcall_int80` test uses. Baseline (no filter): the call reaches the kernel normally. With a test filter loaded that blocks `AF_INET` via the native `socket` syscall (the same mechanism `DENIED_SOCKET_FAMILIES` uses) but declares no other architecture: the process was killed by `SIGSYS` the moment the int-0x80 syscall arrived — libseccomp's own safety net for a syscall tagged with an architecture (`x86`/32-bit compat) that was never explicitly added to the filter, independent of and prior to evaluating any rule at all. This is a *different* mechanism from Docker's explicit multi-architecture allowlist (`SCMP_ARCH_X86_64`/`X86`/`X32`, all declared, with `socketcall` denied by name within them), but empirically confirmed to reach the same safe outcome here: the bypass does not work against this filter, for a reason that was verified rather than assumed. `socketcall` is now also added to `DENIED_SYSCALLS` directly (resolves to nothing on this host's native table and is skipped, per the same safe pattern every other unresolvable name already follows) — defense-in-depth for the case above, and a real mitigation on any host where it *does* resolve, not a fix for a gap that was actually open. This distinction — a difference in *mechanism*, not a gap in *outcome* — is exactly the kind of thing worth stating precisely rather than either claiming false equivalence with Docker's approach or overstating a risk that testing didn't actually find.

## 10. DockerBackend (DEBT-021): A3/A4/A5/D12 implemented and tested, everything host-dependent left explicitly open (update, September 21 2026)

The addendum (9 verified gaps, A1–A9) and the companion 28-item checklist (A1–A9/B1–B4/C1–C3/D1–D12) referenced by `sandbox-fabric-dockerbackend-implementation-prompt.md` now exist and are source-verified against `d53b164` by their own author — but as of this update neither file is committed to this repository; both were supplied directly to this session and are not yet at a path this doc can cite. Closing that specific gap (committing them under `docs/architecture/`, which the base prompt's own Definition of Done already authorizes) was not part of what this update does — noted here so it isn't silently forgotten, not assumed to have happened.

**What this update could not do, stated first because it governs everything below:** the environment this was written in has no `docker` binary, no daemon socket, and no network route to any image registry (registry endpoints are outside this environment's egress allowlist). That is the same absence §"DockerBackend Implementation Prompt" itself already discloses for this branch's history generally — re-confirmed directly rather than assumed inherited. Consequently Phase 0 (host inventory) was not run, no container has ever been created, and none of A1/A2/A6/A9, C1–C3, or the runtime half of D1–D11 has been exercised against anything real.

**What this update did do:** `core/sandbox/backends/docker_backend.py` implements the full `SandboxBackend` interface (`create`/`run`/`cancel`/`destroy`/`inspect`), addressing the addendum's design questions directly rather than deferring them:

- **A3** — image reference is backend-private (`OCBRAIN_SANDBOX_DOCKER_IMAGE` / constructor arg), never a `SandboxRequest` field; resolved to a `RepoDigests` digest once per backend instance and cached, via `docker inspect`.
- **A4** — environment is built from an explicit minimal base plus `request.env`, not `dict(os.environ)`; in allowlist mode the proxy variables (`HTTP_PROXY`/`http_proxy`/`HTTPS_PROXY`/`https_proxy`) are forced to the enforced endpoint *after* `request.env` is applied, so a request can't redirect itself around the proxy.
- **A5** — `allowed_imports` stays unenforced, deliberately: the `docker create` argument builder simply has no parameter for it, so it is structurally impossible for it to influence the generated container, matching `NamespaceBackend`'s existing (also-unenforced) behavior rather than inventing Docker-only cosmetic filtering.
- **A6 / D2 / D3 / D4** (construction-time half only) — the argument builder never emits `--privileged`, `--cap-add`, `--device`, or any host-namespace-sharing flag; always emits `--read-only` plus an explicit `rw` workspace bind; maps each `read_only_paths` entry to its own `:ro` bind; names and labels each container for collision-free cleanup, with no new `SandboxHandle` field.
- **D12** — zero `SandboxCapability` values added to `contracts.py` this session (none of the gates that would earn one have passed); `RuntimeCapabilities.supported` is `frozenset()`, matching addendum B2 exactly. `AdmissionGate.check_admission()` — called, not reimplemented (B3) — already makes this self-enforcing: it requires `FILESYSTEM_JAIL`/`CGROUP_MEMORY`/`CGROUP_PIDS` unconditionally, so every request is rejected before any `DockerBackend` method below `capabilities` is ever reached.

**Verified honestly, not just claimed:** 13 tests in `tests/core/sandbox/test_docker_backend.py` need no Docker daemon at all and pass for real in this environment — `capabilities` is empty, `check_admission()` rejects every request against it, the constructor refuses to start without an image reference, `SandboxRequest` has no `image` field, the env-builder's proxy-precedence invariant (A4), and seven checks on the `docker create` argument list itself (no privileged/host-namespace/cap-add/device flags, `--read-only` present, `--security-opt no-new-privileges` present, read-only-path binds correct, workspace bind correct, name/label present, `allowed_imports` provably inert). That is real, executable evidence for the *argument construction* half of A5/A6/D2/D3/D4 — it is explicitly **not** evidence that Docker's daemon actually honors any of it at runtime, which needs `docker inspect` on a live container and has not been obtained.

A further 8 tests (`create()`/`run()` end to end, root-filesystem read-only enforcement, `cancel()` against a real parent/child/grandchild process tree, C1's OOM-vs-exit-137 distinction via `State.OOMKilled`, artifact collection, double-`destroy()` idempotency, `inspect()` side-effect-freedom, two concurrent sandboxes) are written — a representative subset of `NamespaceBackend`'s own adversarial suite, not yet the full one-for-one parity Phase 6 ultimately wants — and are individually `@pytest.mark.skipif`-gated on a reachable daemon, rather than the base prompt's literal "skip the whole file" wording. That is a deliberate, disclosed deviation, made so the 13 daemon-independent tests above aren't skipped alongside them; every one of the 8 has SKIPPED, not passed, in every environment this has run in so far.

**Left explicitly open, not silently assumed closed:**
- Phase 0 host inventory (daemon identity/endpoint, CVE-2026-31431 fix-date, `userns-remap`, `no-new-privileges` default, AppArmor/SELinux, iproute2, kernel/cgroup version+driver — A7/A8) — not run.
- A1 (`NET_NAMESPACE` alongside `NETWORK_ALLOWLIST`), A2 (`MOUNT`/`PID`/`UTS_NAMESPACE` gates), A6/A9 (runtime privilege-surface and `AF_VSOCK` confirmation), C1–C3 (real OOM classification, network bypass paths, socketcall/compat regression) — none exercised.
- `create()`'s network wiring for `allowed_hosts` calls the existing `AllowlistProxy` (B3) but sets `network_mode="bridge"` as an explicit placeholder — flagged inline with `TODO(host-verify)` — not the isolated no-default-route network Phase 5 actually requires; this is unreachable via `AdmissionGate` today regardless, since `NETWORK_ALLOWLIST` isn't claimed.
- D11 (concurrency): `destroy()`'s `dict.pop` and `cancel()`'s `dict.get` are individually atomic under `asyncio`'s single-threaded event loop, which rules out the crudest corruption, but no per-handle lock was added, and the checklist's actual race-pair tests (`run()+cancel()`, `run()+destroy()`, `cancel()+destroy()`, repeated `cancel()`/`destroy()`) were not run. Recorded as open, not as "probably fine."

**Regression, and one unrelated finding along the way:** `tests/core/sandbox` as a whole: 68 passed, 12 skipped, 0 failed after this change (up from the prior 54/1-flaky/4 baseline — the +21 is exactly this session's 13+8 new tests). `git status` confirms exactly two new, untracked files (`core/sandbox/backends/docker_backend.py`, `tests/core/sandbox/test_docker_backend.py`) and nothing else touched. mypy clean on both new files (`--explicit-package-bases`, one real `str | None` issue it caught in the image-ref handling, fixed with a typed local variable rather than an unchecked assert). The single pre-existing failure noted in an earlier pass on this branch (`test_net_proxy.py::test_connect_to_allowed_host_tunnels_real_data`) was re-run independently three times outside this change: passed twice, then a *different* assertion in the same file (`test_plain_http_to_allowed_host_is_forwarded`) failed once — real, pre-existing timing flakiness in a file this work never touches, not something this session fixed or caused.

## 11. Docker actually installed and exercised in-session — real Phase 0 + A3/D1/D4/D6/D7/D8/D9/D10/D12/C1 evidence, A1/A2/A9/C2/C3/D11 still open (update, September 21 2026, later same day)

Prompted directly: `docker.io` (29.1.3, Ubuntu's own `noble-updates/universe` package, not Docker's own repo — that domain isn't reachable here either) installs cleanly via `apt-get`, pulling in `containerd`, `runc`, `iptables`/`nftables`, and `iproute2` as dependencies (iproute2 specifically was *not* present before this — Phase 0 item 6 was previously unverifiable for want of the tool itself, not just the daemon). **Environment quirk, not a Docker one:** `dockerd`/`containerd` started in the background do not survive past the end of the shell invocation that started them — this sandbox's command tool appears to reap the whole process tree between separate invocations, filesystem state (including the container-image store) is unaffected. Practical consequence: every check below starts both daemons fresh in the same command as the check itself; nothing here should be read as "the daemon has been running continuously."

**Phase 0, obtained directly, not inferred:** local `unix:///var/run/docker.sock`, not remote (A7) — `DOCKER_HOST` unset, `docker version` client and server versions match. `docker info`'s `SecurityOptions` is `["name=seccomp,profile=builtin"]` only — no `userns` entry, confirming userns-remap is off by default here, matching the DEBT-021 security-comparison doc's existing finding, now re-confirmed directly rather than carried over. No `/etc/docker/daemon.json` — stock defaults throughout. `aa-status` (now installed, as an `apparmor` package dependency of `docker.io`) reports directly: **"apparmor not present."** No `getenforce` binary at all — no SELinux userspace. `ip -V` → iproute2-6.1.0. Kernel `6.18.44-fc-v37`, `Cgroup Version: 1`, `Cgroup Driver: cgroupfs`, `Storage Driver: overlayfs` (all from `docker info` directly, matching the values `uname`/`/proc/self/cgroup` already gave outside Docker).

**A3, corrected by real evidence:** `docker import` (used here in place of a registry pull, since none is reachable — a plain tar of this environment's own `/bin /sbin /lib /lib64 /usr /etc`, tagged `ocbrain-test/base:local`) *does* populate `RepoDigests` for a locally-tagged image in this Docker version — contrary to this file's own earlier assumption that only a registry-pulled image would have one. `_resolve_image_digest()` was not changed; it simply worked, resolving to `ocbrain-test/base@sha256:8d81...`, identical (and cached) on a second call. This has only been confirmed for `docker import`; `docker build` is a different code path and was not tested — the assumption as written should still be treated as unconfirmed for that path specifically.

**D1/D4/D6/D8/D9/D10/D12 — the real `DockerBackend` class, not a hand-rolled CLI probe, run end to end against a live daemon:** `create()` → `SandboxHandle` in `PROVISIONING`; `run()` on `("echo", "hello...")` → `exit_code=0`, `TerminationReason.COMPLETED`, correct stdout captured, state moves to `TERMINATED`; `inspect()` called three times in a row returns identical state (D8); `destroy()` then a second `destroy()` on the same handle — the second is a no-op, not an exception (D6). All of `tests/core/sandbox/test_docker_backend.py`'s 21 tests pass with `OCBRAIN_SANDBOX_DOCKER_IMAGE=ocbrain-test/base:local` set — the 13 that always could, plus all 8 that were previously skip-gated: echo/exit-code, read-only-root-write-fails, cancel-vs-process-tree, the OOM-vs-exit-137 distinction, artifact hashing, double-destroy, inspect-idempotence, two-concurrent-creates-don't-collide.

**C1, independently cross-checked outside pytest, since this is the one the addendum is most insistent about not inferring:** two containers, same 16 MB memory limit. One actually exhausted via a real allocation, killed by the cgroup: `docker inspect` reports `OOMKilled=true ExitCode=137`. The other sent an ordinary `docker kill --signal SIGKILL` after a plain `sleep`: `OOMKilled=false ExitCode=137`. Identical exit code, opposite `OOMKilled` — direct, non-pytest confirmation that exit code alone cannot carry this distinction, and that `_classify()`'s actual check (`State.OOMKilled` first, exit code only after) reads the field that does.

**A6, runtime half, not just the argument list:** `docker inspect` on a container `DockerBackend.create()` actually produced: `Privileged=false`, `CapAdd=null`, `PidMode=""`, `IpcMode=private`, `UTSMode=""`, `NetworkMode=none`, `ReadonlyRootfs=true`, `SecurityOpt=["no-new-privileges"]`, `Devices=[]`, `Binds` containing only the workspace mount. Every one of A6's named exclusions, confirmed from the daemon's own state, not the request that asked for it.

**Left open, still, deliberately not attempted this pass:** A1 (`NET_NAMESPACE`/`NETWORK_ALLOWLIST` — no network policy was exercised; `create()`'s network wiring still has its `network_mode="bridge"` placeholder from §10, untouched), A2 (no dedicated `MOUNT`/`PID`/`UTS_NAMESPACE` test — A6's check above is suggestive for PID/IPC/UTS but isn't the same as A2's own defined gate), A9 (`AF_VSOCK`/`AF_ALG`/`socketcall` — not attempted), C2 (network bypass paths — nothing to bypass yet, no proxy was wired up), C3 (32-bit/compat regression — not attempted), D11 (the two-concurrent-creates test passed, but the checklist's actual race pairs — `run()+cancel()`, `run()+destroy()`, `cancel()+destroy()`, repeated `cancel()`/`destroy()` — were not run, and no per-handle lock exists). And unchanged from §10: this remains a Firecracker microVM sandbox, ephemeral between separate sessions, ad hoc in its process lifetime within one — real evidence about *this* environment, not a substitute for whatever host OCBrain actually deploys `DockerBackend` against in production.

## 12. A1 (real, closed) + A2 (real, closed) + A9 (real, and NOT closed — a genuine seccomp bypass) (update, September 23 2026)

**A1** — a fail-closed invariant now lives in `docker_backend.py` itself, not only a test: `_check_a1_paired_capability_invariant()` runs at *import time* against `_CAPS` and raises if `NETWORK_ALLOWLIST` is ever present without `NET_NAMESPACE` alongside it — so a future change that adds one without the other breaks the import, not just a test that could bit-rot unnoticed. Three tests: the invariant holds for the current (empty) `_CAPS`; it actually raises when constructed with the violating combination (a fail-closed check that's never observed firing isn't verified — this is that observation); `NET_NAMESPACE` alone (no `NETWORK_ALLOWLIST`) is confirmed *not* to trip it, since A1 only constrains one direction.

**A2**, tested directly against a real running container, not inferred from `HostConfig`:
- *Mount:* a `tmpfs` mounted on the **host** *after* the container was already running does not appear in the container's own `/proc/self/mountinfo`.
- *PID:* `kill -0 <real host PID>` from inside the container fails (the PID doesn't resolve in the container's own namespace); the host PID has no corresponding entry under the container's `/proc` either.
- *UTS:* the container's hostname (Docker's own default — the short container ID) differs from the host's actual hostname; a same-process attempt to change it fails outright ("Operation not permitted") — no `CAP_SYS_ADMIN` inside a non-`--cap-add` container, a direct consequence of A6 already confirmed in §11, not a new capability check.

All three formalized as tests. One real bug surfaced and fixed while writing them: `create()` only calls `docker create`, not `docker start` — the container exists but isn't running yet, so `docker exec`-based probes against a freshly-`create()`d handle failed until the tests explicitly started the container first. Not a `docker_backend.py` bug — `run()` itself does start the container correctly — but a real gap in how these particular tests used the backend, caught by actually running them rather than assuming the approach was fine.

**A9 — tested, and the honest result is a real, reproducible bypass, not a clean pass:**

Direct `socket(AF_VSOCK, ...)` from inside a container: blocked, `EPERM` — Docker's builtin seccomp profile is doing something for AF_VSOCK specifically (`AF_ALG` is a separate, harder-to-read case: it fails with `EAFNOSUPPORT` both inside and outside any container, because this kernel doesn't compile in the AF_ALG crypto subsystem at all — that block predates and has nothing to do with Docker, exactly the trap A9 warns against reading as a seccomp win).

The actual A9/C3 question — the legacy 32-bit `socketcall(2)` compat entry point — took two attempts to test correctly, and the first one is worth recording as a mistake, not hiding: an initial probe called `syscall(102, ...)` directly via ctypes from a 64-bit Python process. That "succeeded" (returned 0) both inside and outside a container, which looked like a bypass — until checking what file descriptor 0 actually *was* (`/proc/self/fd/0` → `/dev/null`, the container's already-closed stdin) revealed the real explanation: **102 is `getuid()` on the native x86_64 syscall table, not `socketcall`** — the "successful bypass" was a syscall-number mixup returning the process's own UID (0, root), not a socket at all. `socketcall` as syscall 102 is specifically the IA32 (32-bit) ABI's assignment, reachable from a 64-bit process only through the legacy `int $0x80` compat entry point, and only correctly if the pointer arguments actually live in 32-bit-representable address space — which means a genuinely 32-bit-compiled (`-m32 -static`) binary, not inline `int $0x80` asm bolted onto a 64-bit one (tried that too; it returns `EFAULT`, because a 64-bit stack address truncates to garbage under the compat layer's 32-bit pointer handling).

With a real, statically-linked 32-bit binary (`gcc -m32 -static`, `gcc-multilib`/`libc6-dev-i386` installed for this) issuing `int $0x80` with `eax=102, ebx=SYS_SOCKET, ecx=&{AF_VSOCK, SOCK_STREAM, 0}`, and every result checked against `/proc/self/fd/N` (a real socket resolves to `socket:[inode]`; nothing else does) rather than trusted as a plausible-looking return value:

- Raw host: `AF_VSOCK` via `int $0x80` → **succeeds**, confirmed `socket:[6027]`. `AF_ALG` via the same path → fails, `EAFNOSUPPORT` (consistent with the kernel-level absence already established — the probe methodology reads the same on both families, which is itself part of why it's trustworthy).
- **Inside a real Docker container: `AF_VSOCK` via `int $0x80` also succeeds — confirmed `socket:[6965]`, a genuine socket, while the direct 64-bit `socket(AF_VSOCK, ...)` syscall in the same container is blocked.** `AF_ALG` still fails identically inside, for the same kernel reason as outside.

That is a real seccomp bypass on this host: whatever rule blocks `AF_VSOCK` on the native `socket()` syscall does not also cover the same operation reached through the IA32 compat multiplexer. It has not been closed here, and this update does not attempt to close it — the addendum's Phase 4 explicitly names "honest not-closed" as an acceptable outcome and a silent pass as the actual failure mode. Two things temper, without erasing, the finding: (1) this host has no AppArmor active at all (§11) — Docker's own upstream mitigation history for this class of issue leans on an AppArmor rule precisely because a seccomp-only block has this kind of gap, so a host with AppArmor enabled may already close this exact path through a different layer, untested here; (2) the C3 half of this question — whether closing the compat path (e.g. via a custom seccomp profile blocking `int $0x80` entirely, or the specific socketcall subcall) would break legitimate 32-bit/compat workloads — was not attempted, since no fix was attempted. Not yet formalized as a `pytest` test (it needs `gcc-multilib` and a compiled artifact, not just Python) — recorded here as a manually-reproduced, fully-instrumented result instead, reproducible from the exact commands above; deliberately not automated this pass rather than done partially.

## 13. A9 mitigation attempt: a custom seccomp profile does not close it here; the real fix needs an LSM this host doesn't have (update, September 24 2026)

Externally-sourced research (checked, not taken on faith) confirmed §12's finding is a known, named upstream issue: **moby/moby#53551**, "Prevent containers from using the 32-bit `socketcall(2)` path to create `AF_VSOCK` sockets... by adding AppArmor and SELinux policy rules," shipped in **Docker Engine 29.8.0** — this host runs `docker.io` **29.1.3**, before the fix existed at all. The root cause, from the PR's own description: seccomp/BPF filters syscall arguments by reading registers directly; the compat `socketcall(2)` entry passes its real arguments (domain, type, protocol) behind a **userspace pointer** that BPF cannot dereference, so no seccomp rule can condition on "AF_VSOCK via socketcall" the way the existing rule already does for the direct `socket()` syscall. Only an LSM hook (`security_socket_create()`, which fires after the kernel has resolved the actual arguments, regardless of which syscall ABI reached it) can. A related, earlier fix for the AF_ALG case (~29.4.x) replaced an even earlier attempt at a **blanket** seccomp deny of `socketcall` entirely, specifically because that broke legitimate 32-bit programs — the exact tradeoff this update independently arrives at below, now confirmed as prior, documented upstream experience rather than a fresh guess.

**The mitigation this update tried, in detail, because it seemed like it should work and didn't:** downloaded the real upstream default profile (`moby/profiles/seccomp/default.json`, sha256 `785b2429...`), confirmed `socketcall` sits in its large unconditional `SCMP_ACT_ALLOW` rule (all 32-bit compat syscalls have to live somewhere, and BPF can't filter this one by argument — this is the same allow that makes the bypass possible at all), and produced a patched copy with `socketcall` programmatically removed from that rule (sha256 `4fc17aab...`, one rule touched, verified no other rule still names it, verified no rule was left with an empty name list). Loading it via `docker create --security-opt seccomp=<file>` and re-running the exact §12 probe: **the bypass was still open.** Two sanity checks rule out "the profile silently isn't being applied": `/proc/self/status` inside the container shows `Seccomp: 2` (filter mode active) under this profile, and removing an ordinary 64-bit syscall (`mkdir`) from the same rule, by the same mechanism, *does* correctly block it (`EPERM`) — so the loading and enforcement path works; it specifically does not reach the IA32-compat path for `socketcall`. Also tried explicitly setting `"architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_X86", "SCMP_ARCH_X32"]` in place of the source file's `archMap` convenience field (Docker rejects having both set at once) — no change. `strace -f` inside the container (added to the local test image, along with `--cap-add SYS_PTRACE` for that one diagnostic run only) confirms the kernel is genuinely processing the call as `socket(AF_VSOCK, SOCK_STREAM, 0) = 3` — a real, successful socket creation, not an artifact of the probe or of strace's own decoding. The exact reason the X86 sub-architecture rule doesn't take effect for this one syscall was not isolated further — recorded as an open question, not silently written off as "should work."

**Conclusion drawn from that, stated plainly:** a hand-patched Docker seccomp profile is not a mitigation this backend can rely on for this bypass, on this class of host. The only mitigation actually confirmed to work (upstream's own) requires an LSM. `docker_backend.py` now encodes that as a precondition rather than pretending otherwise: `_lsm_active()` checks for AppArmor or SELinux being active on the host at all (it does **not** — and says so in its own docstring — confirm the specific deny rule is loaded; that needs verifying against whatever a real deployment host actually runs). On this host it returns `False`, honestly. No capability claim depends on it yet (nothing is claimed at all — B2), so this is a standing precondition for future work, not a behavior change today: whenever a future gate would claim anything whose safety assumes this bypass is closed, it must check `_lsm_active()` (and, eventually, the specific loaded policy) first, not just the Docker version.

The exploit itself is now a permanent test rather than a one-off manual finding: `test_a9_af_vsock_socketcall_bypass_is_consistent_with_lsm_state` compiles the real `gcc -m32 -static` probe, runs it in a live container, and asserts exactly one direction — when `_lsm_active()` is `False`, the bypass must be observably open, matching today's honest state; if that silently stopped being true without a matching code/doc update, the test fails loudly rather than passing quietly. It does not assert the reverse (LSM present → bypass closed), since presence alone doesn't confirm the specific rule. Gated on a real `gcc-multilib` toolchain being available (separately from the Docker-daemon gate), since it needs a genuinely 32-bit-compiled binary — the inline `int $0x80` approach from a 64-bit process, tried first, returns `EFAULT`: its stack pointers aren't representable in the 32-bit address space the compat layer expects. 28/28 tests in this file pass; mypy clean.

## 14. C2: real network isolation, replacing the `network_mode="bridge"` placeholder (update, September 24 2026)

`_ensure_sandbox_network()` creates (idempotently — "already exists" from a racing concurrent call is treated as success, not an error) a shared `docker network create --internal -o com.docker.network.bridge.enable_icc=false` network and returns its gateway IP. `create()` now attaches `allowed_hosts` requests to this network instead of `"bridge"`, and binds `AllowlistProxy` (B3 — the existing one, not a new mechanism) to the real gateway IP instead of `127.0.0.1`, so the sandboxed container reaches the proxy over the one hop Docker gives it to the host, with no NAT rule (that's what `--internal` withholds) carrying it any further.

Verified directly, first by hand (`docker network create`/`docker run` probes) and then through the real `DockerBackend` class end to end, hitting genuine external hosts the same way `test_net_proxy.py` already does:

- **Allowed host reaches the real server.** `https://example.com/` through the tunnel completes — TLS handshake and all — and gets a real HTTP response from example.com's own server. (Worth recording precisely: that response is a 403, from example.com itself, unrelated to anything here — confirmed by checking for `urllib.error.HTTPError`, which only happens after a successful tunnel+TLS+request round-trip, versus `URLError`, which is what an actual tunnel rejection produces. Conflating "the tunnel worked" with "the target liked the request" would have been a real evaluation mistake; kept the distinction explicit in the test.)
- **Disallowed host is rejected at the tunnel**, before ever reaching a real server — `403` from the proxy itself, `URLError`, not `HTTPError`.
- **Direct connection cannot bypass the proxy** — a raw `socket.connect()` to `example.com`'s real IP, no proxy involved, fails outright (no route — same `--internal` mechanism as §12's namespace probes, now exercised through actual `allowed_hosts` traffic rather than a no-network default).
- **The Docker gateway offers no alternate route** — the gateway IP *is* the proxy's own bind address by design, but nothing else routes through it: a connection to a different, unlistened port on that same gateway IP is refused outright, not silently forwarded anywhere.
- **A sibling sandbox container is unreachable** — two `DockerBackend` instances, both attached to the shared network, cannot reach each other directly (`enable_icc=false`); confirmed with a real listener in one container and a connection attempt from another, which times out rather than connecting. Addresses the addendum's "another reachable container acting as a bridge" concern at the network-creation level rather than per-request.
- **`request.env` cannot redirect the enforced proxy** — re-confirmed end to end through the real backend (A4's logic was already tested in isolation; this exercises the same invariant through actual container creation and a real HTTP_PROXY read-back inside the container).

One thing found and *not* fixed, because it's outside this file's boundary: the first attempt at the "allowed host" test used a plain `http://` URL and got `403` from the proxy for *both* the allowed and disallowed host — `_net_proxy.py`'s plain-HTTP path (`_handle_plain_http`), not its CONNECT path, and not something this session modifies. Re-tested against HTTPS/CONNECT instead — "the mechanism every HTTPS client... uses," per that file's own docstring, and the path `test_net_proxy.py` itself already exercises — where everything above passed cleanly. Left as an observation for whoever next touches `_net_proxy.py`, not chased further here.

6 new tests, all passing; 34/34 in this file total. Full `core/sandbox` regression: 92 passed, the same single pre-existing `test_net_proxy.py` flakiness as every prior pass (this run's exact form: a short read — `Content-Length: 2` received, body not yet arrived when the test asserts — matching the mechanism guessed at earlier and now directly confirmed by the assertion output itself). mypy clean on both files.

## 15. D11: the actual race pairs, run for real (update, September 24 2026)

No per-handle lock was added (§10/§11 already disclosed this); what follows is what asyncio's own single-threaded event-loop atomicity does and doesn't cover, checked rather than assumed either way.

Five race pairs, each run against the real `DockerBackend` class:

- **`run()` + `cancel()` concurrently**: `cancel()` fired mid-`run()`; the awaited `run()` call correctly returns `TerminationReason.CANCELLED`.
- **`run()` + `destroy()` concurrently**: `destroy()` does not raise; the concurrent `run()` call does not hang (returned well within its own timeout) and comes back `TerminationReason.ERROR` — the container was pulled out from under it, and that is reported honestly rather than mis-reported as a clean completion. No orphaned container afterward (`docker ps -a` filtered on the container ID: empty).
- **`cancel()` + `destroy()` concurrently** (`asyncio.gather`, genuinely simultaneous dispatch): neither raises.
- **Repeated `cancel()`/`destroy()`**, including `cancel()` called twice in a row and `cancel()` called *after* `destroy()` has already removed the handle: none of it raises.
- **`inspect()` mid-`run()`**: three calls while the container is actively running, all correctly report `RUNNING`, no blocking, and the eventual `run()` result is unaffected (`COMPLETED`).

`run()+destroy()` and `cancel()+destroy()` were re-run repeatedly with tighter timing (0.3s instead of 1s before the concurrent call, closer to the actual race window) specifically because a single pass isn't enough evidence for a timing-dependent claim — 10 additional trials across both pairs, all consistent, no exceptions, no orphans in any of them. The full D11 test group itself was then run twice more after being written, and the complete `test_docker_backend.py` file three times total across this update — 39/39 every time, no flakes, no orphaned containers left in `docker ps -a` afterward in any run.

Full `core/sandbox` regression: 98 passed, 0 failed — including, this run, the previously-flaky `test_net_proxy.py` test, which happened to pass this time (consistent with genuine intermittency, not a claim that it's now fixed — this session still hasn't touched that file). mypy clean on both files.

This closes out the last item from the 28-item checklist's testing/implementation work (A1–A9, B1–B4, C1–C3, D1–D12) with real, repeated evidence. `_CAPS` is still `frozenset()` — closing D11 is evidence a capability *could* now be claimed with real backing, not a claim by itself; see the session note on which specific capabilities have enough evidence behind them and which still have gaps (`NO_NEW_PRIVS` needs the runtime `/proc/self/status` check the base prompt's own Phase 2 asks for, not just the request-level `HostConfig.SecurityOpt` already confirmed in §11; `CGROUP_PIDS` needs an actual fork-bomb-style adversarial test, not just the `--pids-limit` flag being present; `FILESYSTEM_JAIL`/root-read-only needs an adversarial write attempt through the real backend, not just `HostConfig.ReadonlyRootfs` already confirmed). Deliberately left as an open, explicit decision rather than made unilaterally in the same pass that just finished the checklist itself.

## 16. Closing the last three capability gaps, then `_CAPS` (update, September 25 2026)

The three gaps §15 left open, each closed with real, adversarial evidence against the live daemon:

- **`NO_NEW_PRIVS`**: `grep NoNewPrivs /proc/self/status` run *inside* the running container (the base prompt's own Phase 2 method) via the real `DockerBackend.run()` — `NoNewPrivs: 1`, the runtime property itself, not the create request's `HostConfig.SecurityOpt` already confirmed in §11.
- **`CGROUP_PIDS`**: a deliberately low ceiling (`max_pids=8`) so a failure can't consume real host resources. A bounded burst spawns until creation fails: 7 children succeed (PID 1 plus 7 is exactly 8), the 8th fails. While still under that pressure — not after the main process exits, which was this update's own first mistake, caught the same way A2's `create()`-doesn't-`start()` mistake was: the container was already stopped by the time the check ran — a fresh `docker exec` still succeeds. `destroy()` is clean; `pgrep -f "sleep 15"` on the host afterward finds nothing (the one `pgrep` match in an earlier, cruder check was the grep command's own command-line text matching itself, not a real leak — worth recording since it looked like one for a moment).
- **`FILESYSTEM_JAIL`**: the full attack surface, not just `ReadonlyRootfs=true` — a workspace write succeeds; a write to `/etc`, to an unrelated path (`/usr`), through a `/workspace/../etc/passwd` traversal, and through a symlink planted inside the workspace pointing at `/etc/passwd` are all denied with `EROFS`; the workspace remains writable afterward. The read-only-root design defeats traversal and symlink-escape without any dedicated path-canonicalization logic of its own — both just resolve onto the same read-only filesystem everything else outside the workspace already sits on.

**`_CAPS` now claims nine of the twelve `SandboxCapability` values** — `MOUNT_NAMESPACE`, `PID_NAMESPACE`, `UTS_NAMESPACE` (§12), `NET_NAMESPACE`, `NETWORK_ALLOWLIST` (§14), `CGROUP_MEMORY` (§12), and the three closed above. Each is commented in `docker_backend.py` itself with exactly which reconciliation section backs it, not left to this document alone. Deliberately absent: `USER_NAMESPACE` (no userns-remap on this daemon — claiming it would misrepresent the host), `SECCOMP` (would imply protection against the specific bypass §13 found and did not close — B1's own rule), `NETWORK_DENY_DEFAULT` (checked `admission.py` directly before deciding — it's never actually consulted there, and D12's bar for a new claim is a demonstrated cross-backend need, not "Docker can also do this").

**This is a real behavior change, not just a documentation update**, worth stating plainly: `AdmissionGate.check_admission()` requires `FILESYSTEM_JAIL`/`CGROUP_MEMORY`/`CGROUP_PIDS` unconditionally and `NET_NAMESPACE`/`NETWORK_ALLOWLIST` when `allowed_hosts` is set — all five are now claimed, so a realistic `SandboxRequest` is, for the first time, actually admitted through the normal path instead of rejected before any `DockerBackend` method is reached. That boundary is tested directly, both directions, against the real `check_admission()` (never reimplemented): a basic request is admitted; a networked request is admitted; the same request against a deliberately incomplete capability set (missing just `CGROUP_PIDS`) is still rejected, proving the admitted cases aren't admitted unconditionally.

Every docstring and comment in `docker_backend.py` that said `UNVERIFIED`, described `capabilities` as empty, or claimed a request "has never executed via the normal admission-gated path" has been updated to point at the section that now backs it — a stale "unverified" claim sitting next to code that has, in fact, been verified is its own kind of inaccuracy, and this file existing to avoid exactly that kind of drift was the point of writing this reconciliation doc down as it went rather than only at the end.

Test changes, recorded per the testing-discipline rule that existing tests change only when the frozen contract's expected behavior actually changes, with the reason stated: three tests whose entire premise was "capabilities is empty" (`test_capabilities_start_empty`, `test_empty_capabilities_means_admission_gate_rejects_everything`, `test_no_new_sandbox_capability_claimed_yet`) were rewritten, not deleted, to assert the new true state instead — the premise changed, not the standard. Two genuinely new tests were added alongside them for the admission boundary's other two cases (a networked request; a deliberately-incomplete capability set).

44/44 tests in this file now; full `core/sandbox` regression: 103 passed, 0 failed. mypy clean on both files. This is the actual completion point: **the backend's declared security capabilities are backed by adversarial runtime evidence, and the admission layer enforces those claims** — not merely "DockerBackend is implemented." The A9 finding stays exactly as `_lsm_active()` and its regression test already record it — real, unmitigated, permanently represented — regardless of anything above; nothing in this section touches it.


## 17. D10 remediated; C2 downgraded to FAIL and `NETWORK_ALLOWLIST` withdrawn after a cross-sandbox egress finding (update, September 29 2026)

Two results, deliberately kept separate: a lifecycle defect class that is now fixed and verified (D10), and a stronger, unrelated isolation failure that is *not* fixed and is recorded here as its own finding.

### 17.1 D10 — remediated

§15/§16 recorded D10 as passing on the strength of container-orphan checks after the D11 race pairs. The checklist's D10 requires one test per failure point (creation, network setup, start, execution, timeout, cancellation, external disappearance, daemon/API failure), each asserting no leftover labeled resource, and names "testing only the happy-path `destroy()`" as the forbidden shortcut. A fresh audit found the earlier evidence too thin for that, and found real defects behind it, reproduced against the unmodified code:

1. **Proxy listener leak.** `create()` called `proxy.start()` before spawning `docker create`; only a *nonzero exit* stopped it. If the spawn itself raised, the listener stayed alive and accepting connections with no handle anywhere that could stop it.
2. **Workspace leak.** A failed `create()` left behind the workspace directory it had just made (nonzero `docker create`, and network-setup failure).
3. **Handle dropped before removal was confirmed.** `destroy()` popped the handle first and ignored `docker rm`'s outcome, so an unspawnable or failing `rm` orphaned the container, the proxy and the workspace with no handle left to retry from.
4. **Container with no handle.** A container genuinely created before a failure or cancellation could not be found again. This one was not shown in the red run (the proxy check fires first there); it is established by mutation M2 below.

**Fix** (`docker_backend.py` only): every resource acquired in `create()` is now either cleaned immediately or retained in a destroyable handle. The container is removed by its backend-private name and *absence is confirmed* by a label query — a `None` (could not look) is never confused with `[]` (nothing there). A workspace is removed only if that call created it; a pre-existing caller-owned one is never touched. `destroy()` retains the handle and raises `DockerBackendError` when removal cannot be confirmed, stops the host-side proxy regardless, and removes the workspace only once the container is confirmed gone.

**Behavior change to note:** `destroy()` can now raise (`DockerBackendError`) where it used to return silently, and a second call retries.

**Evidence.**

- Red, tests against the *unmodified* source: 6 of 16 failed, each for the intended reason (workspace leak ×2, live proxy listener ×3, raw `FileNotFoundError` with the handle already dropped); 10 passed, i.e. timeout, cancellation, external removal (mid-run and before run), execution failure, start failure, run-start failure and artifact-copy cleanup were already correct. A first red run was mostly noise because of a test-helper off-by-one (`_docker_cmd` never matched, so the injector never fired); it was fixed and the red phase redone.
- Green: all D10 tests pass. Every injecting test asserts the injection actually fired (`.hits`), so none passes vacuously.
- Mutation checks, each breaking one mechanism in a throwaway copy and restoring it byte-identical: M1 (`_abort_create` skips `proxy.stop()`) caught by 4 tests; M2 (skips by-label removal) caught by the 2 after-container tests; M3 (unconditional workspace removal) caught by the pre-existing-workspace guard; M4 (drops the handle when unconfirmed) and M5 (fake "confirmed gone") each caught by the daemon-unreachable test; M6 (`destroy()` skips `proxy.stop()`) caught by 9 tests.
- Final state after this section's other changes (§17.3): DockerBackend file 59/59; full `core/sandbox` 118/118 (the previously flaky `test_net_proxy` test happened to pass this run — intermittency is unresolved, not fixed); mypy clean on both files; after the run 0 containers, 0 endpoints on the shared network, 0 artifact temp dirs.

**Honesty note.** The failures are *simulated at the CLI-call boundary* (`asyncio.create_subprocess_exec` patched for specific `docker` invocations). They exercise this backend's own cleanup invariant; they are not evidence about how Docker or its daemon behaves when it actually fails.

**Scope of the D10 closure.** Closed for: containers, proxy listeners, workspace (host bind source), artifact temp directories, and per-sandbox endpoints on the shared network. **Not decided here:** the lifecycle of the shared network *object* itself (persist vs remove). The frozen documents are silent, and §17.2 makes it a question for the network redesign, so no contract is encoded either way; an earlier draft of this remediation encoded "shared network = persistent infrastructure" and was reverted before it entered the baseline.

### 17.2 Finding: one sandbox can use another sandbox's egress proxy (proposed `DEBT-039`)

- **Observed:** with two concurrent sandboxes holding different allowlists, sandbox B obtained a tunnel to a host that only A's allowlist permits, by connecting to A's proxy on the shared gateway.
- **Expected:** a sandbox's outbound policy is enforced independently of its siblings (invariant in §17.4).
- **Evidence** (reproduction attached verbatim in §17.7): A allows `example.com`; B allows `example.org`.

| Probe, from inside B | Result |
|---|---|
| B's own proxy → `example.com` (not in B's allowlist) | `403 Forbidden` (control: B's policy works) |
| B's own proxy → `example.org` (in B's allowlist) | `200 Connection Established` (control: upstream egress works, so a 200 is meaningful) |
| **A's proxy → `example.com` (in A's allowlist only)** | **`200 Connection Established`** |

- **Likely mechanism (hypothesis from reading the code, consistent with the result, not separately verified):** every sandbox's `AllowlistProxy` binds the one shared network's gateway IP; the gateway is reachable from every container on that network; the proxy does not identify which sandbox is calling; `enable_icc=false` constrains container-to-container traffic, not container-to-gateway traffic.
- **Caveats, stated rather than hidden:** in the reproduction B was *given* A's port through `request.env`. Discovering it by scanning the gateway is expected to be feasible (an ephemeral port on a local bridge) but was **not demonstrated**. Requires two concurrent networked sandboxes. Only `CONNECT` tunnelling was tried. Single-sandbox behavior is unaffected as far as §14 tested it. Whether an `AF_VSOCK` socket (A9) offers an additional way out is untested.
- **Severity:** not formally assigned (the project's audit method defines none for this finding). It is blocking for the `NETWORK_ALLOWLIST` claim.
- **Why §14/C2 missed it:** the C2 bullets covered a raw connection bypassing the proxy, the gateway as a route *beyond* the host, a sibling *container* as a relay (ICC), and `request.env` overrides. A sibling's *proxy* was never a tested path.

### 17.3 Dispositions

| Item | Status | Note |
|---|---|---|
| D10 | **Closed** (scope in §17.1) | Network-object lifecycle explicitly undecided |
| C2 | **FAIL** | The observed behavior contradicts the intended per-sandbox isolation property; §14's results stand only for the paths it tested |
| `NETWORK_ALLOWLIST` | **Withdrawn** | Removed from `_CAPS` (8 of 12 at this point; 7 of 12 after §17.8). `check_admission()` again rejects a request that sets `allowed_hosts`. Re-earn only with a passing concurrent A/B test |
| `NET_NAMESPACE` | **Withdrawn** (§17.8) | Claim/evidence withdrawal only: implementation unchanged, no direct committed test yet |
| A1 | Mechanism retained | The import-time paired-claim invariant is unchanged and still tested (it fires when violated); it holds trivially again |
| Sandbox-security closeout | **Not issued** | No overall closeout may say the network-isolation claims passed |

Direct callers that bypass admission and call `create()` with `allowed_hosts` still reach the network path; `create()` was deliberately not given a backend-local refusal (no second policy surface, addendum B3). Admission, driven by `_CAPS`, is the guard.

**Test changes, recorded per the testing-discipline rule** (existing tests change only where the frozen contract's expected result changes, with the reason stated): the capability-set test drops `NETWORK_ALLOWLIST` and lists it among the deliberately absent; the claimed-count assertion moves 9 → 8; the networked-request admission test's expectation flips from *admitted* to *rejected* (the contract changed: the claim was withdrawn); the A1 comment no longer says both claims are held. One D10 test — the one that encoded the reverted persistence decision — was deleted; that is removing an assertion of a contract we chose not to adopt, not weakening a check of existing behavior. Everything else about D10 coverage is unchanged.

### 17.4 Invariant for the network-redesign workstream

> A sandbox must not be able to reach or use another sandbox's egress proxy, directly or indirectly, and its outbound policy must be enforced independently of sibling sandboxes.

That workstream may legitimately modify `_net_proxy.py` and the network topology. A per-sandbox network/proxy binding is one plausible direction, not a decision; the redesign should be worked from the invariant, not from an assumed implementation. Its regression gate is a **concurrent A/B test with deliberately different allowlists**, of the shape in §17.7, that must show B cannot obtain A's egress.

### 17.5 Separate follow-ups (not conflated with §17.2)

- After a failed `docker start` spawn, `run()` leaves the handle's state at `RUNNING` although nothing started (D6/D8 bookkeeping; the handle remains destroyable).
- Create-unwind residual: if the daemon is unreachable during the unwind itself, an already-created container cannot be confirmed removed and has no handle; it stays enumerable by the `ocbrain.sandbox=true` label.
- Test hygiene: a D10 test that fails midway can leave containers behind (a finalizer removing containers created during the test would prevent it).
- The test module's docstring still says every daemon-gated test is skipped; that has not been true for some time.
- `test_net_proxy.py` remains intermittently flaky (`test_plain_http_to_allowed_host_is_forwarded`, and earlier a different assertion). Together with the plain-HTTP 403 seen in the C2 work, the plain-HTTP path of `_net_proxy.py` has two separate unexplained behaviors; neither has been diagnosed.
- `handoff.md` §5 is stale on D10 (now closed with new evidence), C2 (PASS → FAIL) and `NETWORK_ALLOWLIST` (withdrawn).

### 17.6 Proposed `KNOWN_ISSUES.md` entry (not applied — outside this workstream's file boundary)

> **DEBT-039 (proposed; `DEBT-038` was registered on `main` for the `/distill` `module_name` path traversal, PRs #37 and #38, so this takes the next free id) — cross-sandbox egress via a sibling's proxy.** DockerBackend's sandboxes share one network whose gateway hosts every sandbox's `AllowlistProxy`; sandbox B was observed tunnelling to a host permitted only by sandbox A's allowlist (reconciliation §17.2). `NETWORK_ALLOWLIST` withdrawn from `DockerBackend._CAPS`; C2 FAIL. Fix needs a network/proxy redesign (may touch `_net_proxy.py`); regression gate is a concurrent A/B test with different allowlists.

### 17.7 Reproduction (verbatim scratch script, not part of the test suite) and its output

```python
"""Scratch probe (NOT in the repo): can sandbox B (allowlist {example.org}) use
sandbox A's proxy (allowlist {example.com}) via the shared gateway?"""
import asyncio, sys, shutil
sys.path.insert(0, "/home/claude/ocbrain-v4.1")
from core.sandbox.backends.docker_backend import DockerBackend
from core.sandbox.contracts import SandboxPolicy, SandboxRequest

B_SCRIPT = r'''
import os, socket, urllib.parse
def connect_via(host, port, target):
    try:
        s = socket.create_connection((host, port), timeout=8)
        s.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
        s.settimeout(12)
        line = s.recv(300).split(b"\r\n")[0]; s.close(); return line.decode()
    except Exception as e:
        return "ERR " + repr(e)
own = urllib.parse.urlparse(os.environ["HTTPS_PROXY"])
a_port = int(os.environ["A_PORT"])
print("1 B's OWN proxy -> example.com  (NOT in B's allowlist):", connect_via(own.hostname, own.port, "example.com:443"))
print("2 B's OWN proxy -> example.org  (in B's allowlist)    :", connect_via(own.hostname, own.port, "example.org:443"))
print("3 A's proxy     -> example.com  (in A's allowlist only):", connect_via(own.hostname, a_port, "example.com:443"))
'''

async def main():
    be = DockerBackend(image_ref="ocbrain-test/base:local")
    for d in ("/tmp/xsb-A", "/tmp/xsb-B"): shutil.rmtree(d, ignore_errors=True)
    reqA = SandboxRequest(command=("sleep", "40"), policy=SandboxPolicy(workspace_dir="/tmp/xsb-A", allowed_hosts=("example.com",), timeout_sec=60))
    hA = await be.create(reqA)
    runA = asyncio.ensure_future(be.run(hA, reqA))
    await asyncio.sleep(1.5)
    a_port = be._handles[hA.handle_id].proxy.port
    reqB = SandboxRequest(command=("python3", "-c", B_SCRIPT), env={"A_PORT": str(a_port)},
                          policy=SandboxPolicy(workspace_dir="/tmp/xsb-B", allowed_hosts=("example.org",), timeout_sec=60))
    hB = await be.create(reqB)
    resB = await be.run(hB, reqB)
    print(f"[A's proxy port = {a_port}]")
    print(resB.stdout.strip() or "(no stdout)")
    if resB.stderr.strip(): print("stderr:", resB.stderr.strip()[:300])
    await be.cancel(hA); await runA
    await be.destroy(hA); await be.destroy(hB)

asyncio.run(main())
```

Output observed (September 29 2026, Docker 29.1.3, the `docker import`-built test image):

```
[A's proxy port = 45573]
1 B's OWN proxy -> example.com  (NOT in B's allowlist): HTTP/1.1 403 Forbidden
2 B's OWN proxy -> example.org  (in B's allowlist)    : HTTP/1.1 200 Connection Established
3 A's proxy     -> example.com  (in A's allowlist only): HTTP/1.1 200 Connection Established
```

### 17.8 Amendment (same day): `NET_NAMESPACE` withdrawn

`NET_NAMESPACE` is removed from the asserted capability set; `_CAPS` is now **7 of 12** (`MOUNT_NAMESPACE`, `PID_NAMESPACE`, `UTS_NAMESPACE`, `CGROUP_MEMORY`, `NO_NEW_PRIVS`, `CGROUP_PIDS`, `FILESYSTEM_JAIL`). Under addendum B2 a capability needs a gate of its own, and none exists: its only cited evidence was the C2 set, which tests egress paths rather than namespace separation. The scratch observation that a container's netns inode differs from the host's is useful but is not a committed test, so it does not earn the claim.

This is a **claim/evidence withdrawal, not a statement that Docker failed to create a network namespace.** The implementation is unchanged.

The three statuses are kept distinct:

| Item | Status |
|---|---|
| `NET_NAMESPACE` | Implementation fact awaiting a direct gate |
| `NETWORK_ALLOWLIST` | Withdrawn: observed behavior contradicts the claimed invariant (§17.2) |
| C2 | FAIL pending a network-boundary redesign and regression proof |

**Future gate (not added in this change):** at minimum, (a) a sandbox's network namespace is distinct from the host's, and (b) concurrently created sandboxes have pairwise-distinct network namespaces.

**Separation rule:** passing that gate re-earns `NET_NAMESPACE` *only*. It does not resurrect `NETWORK_ALLOWLIST` or C2, and DEBT-039 stays open. (A1's existing paired-claim invariant already makes `NET_NAMESPACE` a *prerequisite* for ever claiming `NETWORK_ALLOWLIST` again; necessary is not sufficient.)

**Effects:** `check_admission()` still rejects any request that sets `allowed_hosts`, now on the `NET_NAMESPACE` check first. Tests changed only where the contract changed: the capability-set test (8 → 7, `NET_NAMESPACE` added to the deliberately-absent list) and its count assertion. No test was deleted or weakened.


## 18. Closeout audit: the 28-item matrix, B and D12 audits (September 29 2026)

**Verdict: the original prompt's completion standard (§15) is NOT met. `sandbox-fabric` is explicitly incomplete.** After reconciling against the literal checklist (step 2, September 30 2026) the tally was 21 PASS, 2 FAIL (C2, D11), 3 BLOCKED (A1, C3, D9), 1 UNVERIFIED (A9), 1 NON-COMPLIANT (B4); D11 was then resolved at step 3 (§19.1), leaving 22 PASS, 1 FAIL (C2), 3 BLOCKED (A1, C3, D9), 1 UNVERIFIED (A9), 1 NON-COMPLIANT (B4). At step 5 (§19.4) the user formally accepted the `handoff.md` exception, so B4 is now EXCEPTION ACCEPTED, which is not a PASS: the final tally is **22 PASS, 1 FAIL (C2), 3 BLOCKED (A1, C3, D9), 1 UNVERIFIED (A9), 1 EXCEPTION ACCEPTED (B4)**, and the completion decision (§19.4) is Outcome 2: `sandbox-fabric` remains explicitly incomplete. **On October 6 2026 D11 was reopened as DEFECT IDENTIFIED (§19.1) and closed the same day on new evidence (fix PR #68): the tally is again 22 PASS, 1 FAIL (C2), 3 BLOCKED (A1, C3, D9), 1 UNVERIFIED (A9), 1 EXCEPTION ACCEPTED (B4), summing to 28; Result 2 is unchanged.** An earlier draft of this section counted 24 PASS; four statuses (A9, B4, D9, D11) moved because, where my earlier judgment and the checklist's literal text disagreed, the checklist wins. No overall sandbox-security closeout is issued, and none may say the network-isolation claims passed.

This audit was made against the frozen checklist's *literal* text, not the handoff's ledger (§5 of `handoff.md`), because D10 had already shown that ledger could over-claim. It found the ledger's evidence thinner than stated in several places, added tests for every checklist-required verification that had none, and found four product defects (D4, D5, and two in D6), now fixed.

### 18.1 What the audit found

**Product defects (reproduced against the unmodified code, then fixed):**

1. **D5 — artifact collection hangs on a FIFO.** A sandbox that runs `mkfifo` in its workspace blocked collection indefinitely: `_sha256_of` does a synchronous `open()`, which blocks forever on a FIFO with no writer, stalling the *whole event loop*. Fix: only regular files are hashed. (Mutation M7 re-creates the hang.)
2. **D6 — a second `run()` re-executed the command.** `docker start` on an exited container silently restarts it. Fix: a handle can be run at most once (`DockerBackendError` otherwise).
3. **D6 — cancel-before-run mislabeled a later run.** `cancel()` set its flag unconditionally, so a run that then completed normally was reported `CANCELLED`. Fix: the flag is set only while the sandbox is actually running; the `docker kill` stays unconditional (the D11 race tests depend on it).
4. **D4 — `request_id` was in neither the container name nor its labels**, though D4 requires it. Fix: an `ocbrain.request_id` label.

**Behavior changes visible to callers** (all inside the existing contract's shape): a second `run()` on a handle raises; `cancel()` before `run()` no longer taints it; and, from §17, `destroy()` can raise when removal cannot be confirmed.

**Evidence that was weaker than its name or the ledger said (fixed by adding tests, not by changing code):** `test_artifacts_collected_with_real_sha256` never checked a hash (only that a filename appeared); `test_cancel_kills_full_process_tree` would pass vacuously if the grandchild never started (`None == None`); A3, A6 and D2 had only construction-level or ad hoc evidence; D6 had one of its six cases; C1 lacked the same-exit-code cancel case; D8 checked bookkeeping equality, not the container itself.

**Not a product defect, recorded because it bit this audit:** my first C1 test assumed `kill -9 $$` from a container's PID 1 would produce exit 137; a PID 1 shell ignores its own SIGKILL. Corrected before any conclusion was drawn from it.

**Recorded behavior, not a fix:** a *relative* symlink that escapes the workspace makes `docker cp` itself refuse (`invalid symlink`), so the manifest is empty — nothing escapes, but every artifact is lost silently. Absolute and directory symlinks are rejected by the collector's containment check while legitimate files survive.

**Corrections to the handoff ledger:** its B-numbering was a guess; the checklist's is B1 = `SECCOMP` is not CVE-specific protection, B2 = capabilities empty until earned, B3 = no second policy surface, B4 = file-touch boundary. C3 was filed "NOT APPLICABLE (moot)" but the item has no N/A clause, so it is BLOCKED. D10, C2, A1 and the capability count were superseded by §17. Step 2 then re-read A9, B4, D9 and D11 against their literal text and moved all four (matrix below): a passing test does not override a stated prohibition (D11), an invariant that holds only because nothing runs is not a verification (D9), a procedural item whose probe came back negative is not a clean PASS (A9), and an allow-list is checked against the diff, not against intent (B4).

### 18.2 The 28-item verification matrix

Classification: A = verified gap, B = traceability rule, C = gate extension, D = implementation requirement. All symbols are in `core/sandbox/backends/docker_backend.py` and all tests in `tests/core/sandbox/test_docker_backend.py` unless stated. "Mutation Mn" means the fix or guard was broken in a throwaway copy and the named test failed.

Status vocabulary: the original prompt's PASS / FAIL / BLOCKED (N/A is not used), extended at step 2 by **UNVERIFIED** (the requirement's property is not established: evidence absent, partial, or negative without being a clean FAIL of the item as worded) and **NON-COMPLIANT** (a traceability rule whose literal test is not met, with an exception pending formal acceptance). Step 5 (§19.4) adds one more: **EXCEPTION ACCEPTED** (a traceability rule whose literal test is not met and whose exception the user has formally accepted; it is neither a PASS nor compliance with the rule as worded). D9 is BLOCKED and is therefore also unverified. A further status, **DEFECT IDENTIFIED** (October 6 2026), marks an item that was accepted and whose evidence was later contradicted: it is not accepted until the fix is merged and the verification is clean. It was used once, for D11, and cleared on October 6 2026.

| ID | Class | Status | Evidence | File/Symbol | Public/Policy Surface | Host Dependency | Notes |
|---|---|---|---|---|---|---|---|
| A1 | A | **BLOCKED** | Invariant enforced at import and tested (`test_a1_*`: holds; fires when violated). The required verification, an allowlist request admitted and reaching the proxy path, is impossible while both claims are withdrawn (§17, §17.8) | `_CAPS`, `_check_a1_paired_capability_invariant` | capability claims withdrawn | none | Unblocks only after the DEBT-039 redesign and a `NET_NAMESPACE` gate; the mechanism itself is sound |
| A2 | A | PASS | `test_a2_mount_…`, `test_a2_pid_…`, `test_a2_uts_…` (real host mount, real host PID, hostname) | `_CAPS` | claims MOUNT/PID/UTS_NAMESPACE | none | Claimed on their own tests, not "Docker uses namespaces" |
| A3 | A | PASS | `test_a3_independent_backends_resolve_the_identical_immutable_digest`, `test_a3_image_like_env_cannot_change_what_runs` (M14), `test_sandbox_request_has_no_image_field` | `_resolve_image_digest`, constructor | none: no `image` field | image must carry local RepoDigests | Verified only for a `docker import` image; `docker build` path untested |
| A4 | A | PASS | `test_a4_host_only_env_var_is_absent_and_request_env_is_present_in_the_container` (M18), `test_c2_env_cannot_redirect_the_enforced_proxy`, env-builder unit tests | `_build_container_env` | none | none | Verifies env ordering only; says nothing about egress enforcement (C2 FAIL) |
| A5 | A | PASS | `test_a5_a_restrictive_allowed_imports_value_still_runs_unimpeded`, `test_create_args_ignores_allowed_imports` | `_build_create_args` (structural: no such parameter) | none | none | Option (a), non-enforcement preserved; a documentation test, not a security property |
| A6 | A | PASS | `test_a6_runtime_inspect_shows_no_privilege_or_host_sharing[False/True]` (M13) asserts `Privileged`, `CapAdd`, `PidMode`/`IpcMode`/`UTSMode`/`NetworkMode`, `Devices`, mounts, `ReadonlyRootfs` from a live `docker inspect`; plus the construction test | `_build_create_args` | none | Docker version | Effective state, not just the request |
| A7 | A | PASS | §18.4 evidence line: local unix socket, context `default`, `DOCKER_HOST` unset | Phase 0 | n/a | this daemon | Findings apply to this daemon only |
| A8 | A | PASS | §18.4 evidence line: kernel 6.18.44-fc-v50, cgroup v1, `cgroupfs` | Phase 0 | n/a | this kernel/cgroup | Conclusions scoped to that combination; the kernel drifts within a session (v37→v42→v49→v50) |
| A9 | A | **UNVERIFIED** | Literal requirement: probe `AF_VSOCK` as its own step and record it independently of `AF_ALG`. **`AF_VSOCK`:** probe run (`test_a9_af_vsock_socketcall_bypass_is_consistent_with_lsm_state`; §12): `socket(AF_VSOCK)` through `socketcall(2)` (`int $0x80`) creates a real socket inside a real container, so protection is NOT established (bypass observed open). **`AF_ALG`:** not exercisable, `EAFNOSUPPORT` (this kernel does not provide it), so nothing is established either way | `_lsm_active`, `_CAPS` (`SECCOMP` absent) | `SECCOMP` unclaimed | kernel lacks `AF_ALG`; no LSM policy loaded; Docker 29.1.3 predates the upstream fixes | UNVERIFIED describes the *protection*, not whether testing happened: the `AF_VSOCK` probe was run and its result is negative. Nothing here may be read as "`AF_VSOCK` blocked" |
| B1 | B | PASS | `test_capabilities_reflect_exactly_the_evidence_backed_set` asserts `SECCOMP` absent; the bypass is tracked separately as A9 (UNVERIFIED; the `AF_VSOCK` bypass was observed open) | `_CAPS` | none | none | The two facts are kept independent |
| B2 | B | PASS | `_CAPS` started `frozenset()` (commit history). Every claim traces to a test: MOUNT/PID/UTS to the A2 tests; CGROUP_MEMORY to `test_oom_kill_reported_as_resource_exceeded_not_inferred_from_exit_code`; NO_NEW_PRIVS to `test_no_new_privs_runtime_proc_status`; CGROUP_PIDS to `test_cgroup_pids_enforced_and_container_stays_controllable`; FILESYSTEM_JAIL to `test_filesystem_jail_full_attack_surface` | `_CAPS` | 7 of 12 claimed | none | `NETWORK_ALLOWLIST` and `NET_NAMESPACE` withdrawn (§17, §17.8). The FILESYSTEM_JAIL test's name overclaims (no `/dev/shm`, `/proc`, `/sys` or mount attempts) |
| B3 | B | PASS | Source review: imports and uses `AllowlistProxy`; defines no parallel admission function, proxy or request/result shape; admission is consumed through `capabilities` | module | none | none | The `--internal` Docker network is topology, not a policy standing in for the proxy; the redesign may revisit it |
| B4 | B | **EXCEPTION ACCEPTED** (`handoff.md` only; accepted at step 5, §19.4; was NON-COMPLIANT; not a PASS) | §18.6. Literal allow-list: `docker_backend.py`, private helpers, the test file, additive `SandboxCapability` entries, "this checklist/addendum". Outside it in the workstream's own commits: **`handoff.md`** (no authority; created on explicit user instruction and required by the project's handoff protocol) and the reconciliation document (authorized by the base prompt's Definition of Done, which outranks the checklist, but not named in B4's list) | whole diff | n/a | none | Was NON-COMPLIANT at step 2. The user formally accepted the `handoff.md` exception at step 5 (§19.4): an accepted exception, not compliance with the allow-list. The branch-level diff also now contains `main` merged in (`68fd460`, `565ea3a`), so a literal `git diff --stat` on the branch cannot match the list; B4 was evaluated on the workstream's own commits, selected by author |
| C1 | C | PASS | `test_oom_kill_reported_as_resource_exceeded_not_inferred_from_exit_code`, `test_c1_ordinary_sigkill_with_exit_137_is_not_resource_exceeded`, `test_c1_cancel_with_exit_137_is_cancelled_not_resource_exceeded` (M17: the `exit_code == 137` shortcut is caught) | `_classify` | none | cgroup v1 `OOMKilled` | Same exit code, opposite classification, from inspected state |
| C2 | C | **FAIL** | §17.2: with concurrent sandboxes holding different allowlists, sandbox B obtained a tunnel through A's proxy on the shared gateway. The six C2 bullet tests pass and stand only for what they tested | `create()` network path, shared gateway, `_net_proxy.py` (not touched) | `NETWORK_ALLOWLIST` withdrawn | Docker `--internal` network | Filed as proposed DEBT-039; the invariant and regression gate are in §17.4 |
| C3 | C | **BLOCKED** | Requires two outcomes recorded together: bypass closed and a benign compat probe still working. The first cannot be obtained: nothing closes the bypass on this host | Phase 4 step, report | none | needs a host with an active AppArmor or SELinux policy and a Docker release containing the socketcall fix | Not N/A (the item has no such clause). Nothing is reported closed |
| D1 | D | PASS | `test_create_args_workspace_is_the_writable_mount`, `test_artifacts_collected_with_real_sha256` (file retrievable), `test_d5_manifest_hash_and_size_match_an_independent_recomputation`, `test_root_filesystem_is_read_only`, `test_filesystem_jail_full_attack_surface` (write to an undocumented path fails) | `_build_create_args` | none | none | Mapping documented in the builder |
| D2 | D | PASS | `test_d2_read_only_path_rejects_write_delete_create_and_symlink_escape` (M12): write, modify, delete and create all fail; absolute and relative symlinks cannot reach a host secret; host side untouched | `_build_create_args` (`:ro` bind) | none | none | One declared path exercised; several behave identically by construction |
| D3 | D | PASS | `test_root_filesystem_is_read_only`, `test_filesystem_jail_full_attack_surface` (writes to `/etc`, `/usr`, `..` traversal and symlink escape all denied; workspace stays writable) | `_build_create_args` (`--read-only`) | none | none | The first test alone is weak (asserts only a nonzero exit); the jail test carries it |
| D4 | D | PASS | `test_d4_create_args_label_carries_the_request_id` and `test_d4_abandoned_labeled_container_is_found_and_removed_by_a_cleanup_pass` (M10), `test_two_concurrent_sandboxes_do_not_collide`, D11 | `_build_create_args`, `create()` | none: no `SandboxHandle` field | none | Fixed this audit (§18.1, item 4) |
| D5 | D | PASS | `test_d5_manifest_hash_and_size_match_an_independent_recomputation`, `test_d5_absolute_symlinks_are_rejected_while_legitimate_artifacts_survive` (M11), `test_d5_relative_escaping_symlinks_never_reach_the_manifest`, `test_d5_non_regular_files_neither_hang_collection_nor_enter_the_manifest` (M7) | `_collect_artifacts` | none | none | Fixed this audit. Not attacked: extraction races, hard links, workspace size. Relative escaping symlinks empty the manifest silently |
| D6 | D | PASS | One test per case: `test_d6_run_before_create_is_a_defined_error`, `test_d6_double_run_is_a_defined_error_not_a_second_execution` (M8), `test_d6_cancel_before_run_is_a_no_op_that_does_not_taint_the_later_run` (M9), `test_d6_cancel_after_terminate_is_a_no_op`, `test_double_destroy_is_idempotent`, `test_d6_inspect_after_destroy_reports_a_defined_sandbox_state` | `run`, `cancel`, `destroy`, `inspect` | none | none | Two cases fixed this audit. The state left `RUNNING` after a failed `docker start` spawn is a separate follow-up (§17.5) |
| D7 | D | PASS | `test_d7_cancel_reaches_a_grandchild_that_was_provably_alive_before` (M15): proves the grandchild was alive and advancing before, then stopped, and the container is not running | `cancel` | none | none | Supersedes the weaker `test_cancel_kills_full_process_tree` (kept, and made event-based in §19.2). A cancel that lands while `docker start` is still in flight is covered by `test_d7_cancel_during_an_in_flight_start_cannot_be_escaped_by_the_workload` (M23–M26, §19.2) |
| D8 | D | PASS | `test_d8_inspect_never_touches_the_container_itself` (M16): `docker inspect` shows a created container stays created and an exited one stays exited across repeated `inspect()` | `inspect` | none | none | By construction `inspect()` only reads bookkeeping |
| D9 | D | **UNVERIFIED — BLOCKED** | Literal verification: a full-lifecycle test (success, cancel, failure) that emits only known event types in the expected order. It cannot be run because **no lifecycle-event producer exists**: `core/sandbox/events.py` defines `EventStream`, but nothing in the repo publishes to it (`NamespaceBackend` included) and nothing outside tests imports `core.sandbox`. Established: `docker_backend.py` publishes nothing and introduces no event type (`test_no_new_contracts_py_enum_members_added`) | module | none | repository: no producer or integration layer | Not a PASS: the invariant holds only vacuously and the required test is unperformed. Unblocking needs a decision: DockerBackend (and arguably every backend) publishing through `EventStream`, or an amendment to D9 |
| D10 | D | PASS | §17.1: 15 failure-injection tests, red then green, mutations M1–M6 | `create`, `destroy`, `_abort_create`, `_remove_container` | none | none | Scope and simulated-failure honesty note in §17.1; network-object lifecycle undecided |
| D11 | D | **PASS** (resolved at step 3, §19.1; reopened as DEFECT IDENTIFIED and re-closed on October 6 2026 with the fix of PR #68, §19.1) | Literal text: invariant "no interleaving produces two internal records for one handle, or a container with none"; forbidden shortcut "a lock so coarse it serializes unrelated sandboxes, or no lock at all". It was FAIL: reproduced against the unmodified code that `destroy()` forgot the record before the removal finished (a container with no record), that a second concurrent `destroy()` returned early, and that under failure only one caller was told. Now the record is kept until removal is confirmed and `destroy()` runs under a per-handle `asyncio.Lock`. Six tests `test_d11_*` (record present while a destroy is in flight; a second destroy does not return early; failure reaches every caller; concurrent destroys are serialized, not repeated; one sandbox's destroy does not wait on another's; two concurrent runs execute once) plus the five original race pairs; mutations M19–M22 | handle bookkeeping (`_handles`, `_DockerRunState.lock`, `destroy`) | none | none | The lock is mandatory under the frozen checklist, and its removal is caught by exactly one test (M19); the invariant itself is repaired by retaining the record. `run()` and `cancel()` deliberately take no lock. Caller-visible: concurrent destroys wait for the earlier one, and `inspect()` during a destroy reports the real state. **Reopened and re-closed October 6 2026 (§19.1):** under load, `run()`+`destroy()` could return `COMPLETED`/137 instead of `ERROR`; fixed by a causal `destroy_requested` marker (PR #68), with forced-interleaving tests, a clean loaded verification and mutations M1 to M6 |
| D12 | D | PASS | §18.7 | `contracts.py` (unchanged) | none | none | |

### 18.3 Test summary

- **Repository baseline:** `sandbox-fabric`, `76fb1c0` at session start; nothing under `core/sandbox/` other than `docker_backend.py` differs from `d53b164`.
- **Tests:** the DockerBackend file went from 44 at the handoff to **81** (87 after §19.1; 88 after §19.2): 15 D10 tests (§17), 22 closeout-audit tests, and the §17 capability-set tests updated where the contract changed (§17.3, §17.8).
- **Mutation checks:** 18 deliberate breakages (M1–M18; 26 after §19.1 and §19.2, M19–M26), each caught by the intended test, each source restored byte-identical. Several failures were re-run with full tracebacks to confirm they failed for the intended reason.
- **Final regression:** DockerBackend file 81/81; mypy clean on both files; 0 containers, 0 shared-network endpoints and 0 artifact temp dirs afterwards; the 7 out-of-scope files byte-identical.
- **Pre-existing failure:** `tests/core/sandbox/test_net_proxy.py` is intermittently flaky in a file this workstream never touches. Three different tests in it have now failed at different times (`test_plain_http_to_allowed_host_is_forwarded`, `test_connect_to_allowed_host_tunnels_real_data`, and an earlier different assertion). The full suite last ran 139 passed, 1 failed, the failure being that file's. Not diagnosed; not called environmental.
- **One unidentified failure:** a single DockerBackend-file run showed 1 failed / 78 passed; I did not capture which test. It did not recur in the 11 runs that followed (4 full-file runs, 6 runs of the 40 most timing-sensitive tests, one full-suite run), so it is unexplained, not resolved.
- Temp-dir note: two `ocbrain-docker-artifacts-*` directories were left by the two runs where the FIFO hang was induced on purpose (the hung subprocess was killed before its cleanup). The fixed code left none across all later runs.

### 18.4 Host summary (fresh, this session)

| Fact | Value |
|---|---|
| Daemon / runtime | Docker Engine 29.1.3 (API 1.52), `io.containerd.runc.v2` / `runc` |
| Endpoint certified | local unix socket `/var/run/docker.sock` (root:docker), context `default`, `DOCKER_HOST` unset; not rootless, not remote |
| Kernel | 6.18.44-fc-v50 (a Firecracker microVM; the value drifted v37→v42→v49→v50 during this workstream) |
| cgroups | v1, driver `cgroupfs`; storage driver `overlayfs` |
| `userns-remap` | not enabled (`SecurityOptions` lists only `name=seccomp,profile=builtin`) |
| `no-new-privileges` | not a daemon default (no `daemon.json`); applied per container and verified effective (`NoNewPrivs: 1`) |
| AppArmor / SELinux | AppArmor not compiled in, modules disabled; SELinux compiled in and listed in the active LSM stack (`lockdown,capability,landlock,selinux,bpf`) with **no policy loaded** |
| iproute2 | 6.1.0 |
| CVE / fix state | The installed Docker predates the upstream `AF_ALG` fix and the socketcall/`AF_VSOCK` fix (moby/moby #52537 and #53551, per the sources recorded in §12), so this daemon does not contain them; the observed bypass is consistent with that. `AF_ALG` is not exercisable because this kernel does not provide it |
| Image / registry | test image built with `docker import`; no registry reachable, so `docker build` and pull-by-digest paths are untested |

### 18.5 Scope summary

- **Files changed by this workstream:** `docker_backend.py`, `test_docker_backend.py`, the reconciliation document; earlier, the addendum, the checklist and `handoff.md` (§18.6).
- **Public interfaces changed:** none; `contracts.py` is byte-identical to the base. Caller-visible behavior changed as listed in §18.1.
- **Policy surfaces changed:** none.
- **Capability surface:** `_CAPS` started empty, reached 9 of 12 in §16, and is **7 of 12** after §17 and §17.8.

### 18.6 B audit

- **B1 PASS.** `SECCOMP` is not claimed; the bypass is tracked as its own FAIL (A9).
- **B2 PASS.** Each of the 7 claims traces to a named passing test (matrix, B2). Two earlier claims were withdrawn because their evidence did not hold up.
- **B3 PASS.** No parallel admission, proxy, or request/result shape exists in `docker_backend.py`.
- **B4 EXCEPTION ACCEPTED (`handoff.md` only; was NON-COMPLIANT until step 5, §19.4).** Files touched by the workstream's own commits (merges from `main` excluded, selected by author): `docker_backend.py`, `test_docker_backend.py`, the reconciliation document, the checklist, the addendum, and `handoff.md`. B4's literal list allows the first two, "this checklist/addendum", and additive capability entries. The reconciliation document is authorized by the base prompt's Definition of Done ("the reconciliation addendum"), which outranks the checklist, but B4's list does not name it. **`handoff.md` is on no allow-list**: it was created on explicit user instruction and the project's handoff protocol requires it, which makes it an exception, not compliance. None of `SandboxBackend`, `NamespaceBackend`, `_ns_init.py`, `_seccomp.py`, `_net_proxy.py`, `admission.py` or `contracts.py` differs from the base. Two further notes: the base prompt asks for a *short* addendum to the reconciliation document and §§10–18 are a full evidence trail; and the branch-level diff now includes `main` merged in by the user, so B4 can only be evaluated on the workstream's own commits. The `handoff.md` exception was formally accepted at step 5 (§19.4); that is an accepted exception, not compliance with the allow-list, and the acceptance names `handoff.md` only.

### 18.7 D12 audit

**PASS.** `contracts.py` has an empty diff against the base (`d53b164`), so no enum entry was added at all. `SandboxRequest` has no `image` field and `SandboxHandle` gained no field (both tested). The D4 label needed no new public surface. The only additions are private helpers, labels and one private capability-set change.

### 18.8 Remaining blockers and decisions

**Blockers, with the evidence needed to resolve each:**

1. **C2 / DEBT-039:** a network-boundary redesign; evidence is a passing concurrent A/B test with different allowlists (§17.4).
2. **A1:** blocked on item 1 and on a `NET_NAMESPACE` gate.
3. **`NET_NAMESPACE`:** a direct committed test that a sandbox's netns differs from the host's and that concurrently created sandboxes have pairwise-distinct netns; passing it does not resurrect `NETWORK_ALLOWLIST` or C2 (§17.8).
4. **A9 / C3:** a host with an active AppArmor or SELinux policy and a Docker release containing the socketcall fix; evidence is the exploit probe blocked plus a benign 32-bit/compat probe still working; `AF_ALG` additionally needs a kernel that exposes it.

**Untested or unattacked, not claimed:** `docker build` `RepoDigests`; hard links and workspace size in artifact collection; whether an `AF_VSOCK` socket has anywhere to connect on a real host; `FILESYSTEM_JAIL` vectors beyond those tested (`/dev/shm`, `/proc`, `/sys`, mount attempts).

**Further unresolved items, recorded at step 2 (the literal checklist wins over my earlier judgments):**

- **A9 UNVERIFIED.** To move: a host with an active AppArmor or SELinux policy and a Docker release containing the socketcall fix, where the `AF_VSOCK` probe is blocked; `AF_ALG` additionally needs a kernel that exposes it. `SECCOMP` stays unclaimed meanwhile.
- **D9 UNVERIFIED — BLOCKED.** Needs a lifecycle-event producer to exist. The decision is whether backends (DockerBackend, and arguably `NamespaceBackend`) publish through `EventStream`, which is implementation work and, per LAW 2, a package-wide gap, or whether D9 is amended. Until then the required test cannot be written.
- **D11** was FAIL at step 2 and is resolved in §19.1 (PASS).
- **B4 NON-COMPLIANT at step 2; resolved at step 5 as EXCEPTION ACCEPTED (§19.4).** It could close only by formal acceptance of the `handoff.md` exception (and of the reconciliation document's status under B4's list), or by removing `handoff.md` from the workstream. The acceptance given names `handoff.md` only.

**Follow-ups, unchanged from §17.5 and not conflated with any FAIL:** state left `RUNNING` after a failed `docker start` spawn; the create-unwind residual; a finalizer to keep failing D10 tests from leaving containers; the test module's stale docstring (still says every daemon-gated test is skipped); `test_net_proxy.py` flakiness and the two unexplained plain-HTTP behaviors; `handoff.md` §5 is stale; the proposed `KNOWN_ISSUES.md` entry (§17.6) has not been applied.


## 19. D11 resolved; the evidence gap; the completion decision (September 30 2026)

### 19.1 D11 — is a synchronization primitive mandatory?

**Question (from the step-3 direction):** decide from the actual implementation and the checklist whether the required primitive is mandatory, and do not let passing tests override an explicit "no lock at all" prohibition.

**What each authority says.** The base prompt is silent on concurrency. The addendum (which outranks the checklist) requires that `run()+cancel()`, `run()+destroy()`, `cancel()+destroy()`, repeated `cancel()`/`destroy()` and `inspect()` mid-transition "must not orphan containers or corrupt handle bookkeeping", and asks for "just race-safe backend bookkeeping"; it does not mention a lock. The frozen checklist operationalizes that with an invariant (no interleaving produces two internal records for one handle, *or a container with none*) and a forbidden shortcut (a lock so coarse it serializes unrelated sandboxes, *or no lock at all*).

**Determination.** Yes, under the frozen checklist a lock is mandatory to claim D11: the prohibition is explicit and the checklist is the binding operational text, so passing tests cannot stand in for it. But the decision did not have to rest on the wording alone. Read against the addendum's own standard, **the implementation was not race-safe**, and the earlier tests had missed it.

**What was wrong (each reproduced against the unmodified code, with the real `docker rm` merely delayed so the interleaving is deterministic):**

1. `destroy()` popped the handle's record *before* awaiting the container's removal, so for the whole removal there was a container with no internal record. That is the checklist's invariant, violated by design.
2. A second concurrent `destroy()` found no record and returned "success" while the removal was still in flight.
3. Under a failing daemon, only the first of two concurrent callers was told; the second returned `None`.

The five original D11 race-pair tests passed because they fire the pairs but never widen the window inside `destroy()`. Passing tests were genuinely not evidence here, which is the point of the direction.

**Fix.** The record is kept until the container's removal is confirmed and only then forgotten (also if the coroutine is cancelled part-way). `destroy()`'s multi-await sequence (remove, confirm, stop proxy, forget) runs under a **per-handle** `asyncio.Lock`; a caller that waited re-checks that its record is still present and returns if an earlier `destroy()` already finished, so it neither repeats the removal nor returns before it completes. If the earlier attempt failed the record is still there, and the waiting caller makes and reports its own attempt. `run()` and `cancel()` deliberately do **not** take the lock: cancelling a run, or destroying a running sandbox, must be able to interrupt it.

**An honest nuance about the lock.** The invariant is repaired by *retaining the record*. The lock's own observable effect is serialization (one removal; waiting callers observe its completion), and mutation M19 (no lock) is caught by exactly one test. Today's destroy steps are idempotent, so correctness without the lock would largely hold; the lock is required by the checklist, makes the critical section's atomicity explicit, and would be necessary the moment a non-idempotent step is added. Both halves are needed: a lock without record retention cannot even be reached, because the second caller finds nothing to wait on.

**Evidence.** Six new tests (named in the D11 row of §18.2): three failed and three passed against the unmodified code (the passes are two-runs-once and independent-sandboxes, which describe behavior that was already right, and serialized-not-repeated, which passes only by accident there and gets its teeth from M19). After the fix the whole DockerBackend file is 87/87. Mutations: M19 no lock (caught by the serialization test), M20 record forgotten before removal (caught by the three red tests), M21 one global lock (caught by the independence test), M22 no re-check after acquiring the lock (caught by the serialization test); source restored byte-identical each time.

**Caller-visible behavior changes:** concurrent `destroy()` calls on one handle now wait for the earlier one; `inspect()` during an in-flight destroy reports the real state instead of `PENDING`; and, from §17, `destroy()` can raise when removal cannot be confirmed.

**Not covered by this resolution:** a lock in one event loop does not protect against several processes managing the same daemon (out of scope; the label scheme is the cross-process cleanup path); and whether a `cancel()` that lands while `docker start` is still in flight can be lost is investigated separately under the evidence gap, because it is a cancellation question, not a bookkeeping one.

**Result: D11 FAIL → PASS.**

**D11 — DEFECT IDENTIFIED (October 6 2026).** The step-3 PASS above is reopened. Unloaded verification passed, but loaded concurrent `run()`/`destroy()` execution can nondeterministically return `COMPLETED` with exit 137 instead of the required `ERROR`. Reproduced independently on the pre-D7 `sandbox-fabric` tip (`23fff0b`). Fix tracked by the dedicated D11 PR (`fix/d11-destroy-causal-classification`). **D11 is not accepted until the fix is merged and the loaded verification is clean.** The step-3 text above is kept unedited as the historical record.

- **How it was found.** During verification of the D7 test fix (PR #64), one full `tests/core/sandbox` run in 15 failed in `test_d11_run_plus_destroy_concurrently_no_hang_no_orphan`: `assert COMPLETED == ERROR`, `exit_code=137`. It did not reproduce unloaded (0 in 60 standalone runs, 0 in 15 with `docker start` delayed by 0 to 3 s).
- **Reproduction.** With 6 concurrent workers and 3 CPU burners on a 1-core VM: 17 failures in 48 runs on the D7 branch, and 3 in 36 on the untouched `sandbox-fabric` tip `23fff0b`, so it is independent of the D7 change.
- **Mechanism (code read).** `destroy()` kills and removes the container that `run()` is waiting on. `run()` then reads the exit code and calls `_classify`. If the container is already removed, the read yields nothing and the result is `ERROR`; if the read lands between the kill and the removal, it sees exit 137 and the result is `COMPLETED`, because nothing records that `destroy()` caused the kill. The outcome depends on timing, against the checklist's "asserting a consistent outcome each time".
- **Why step 3 missed it.** The five original race pairs and the six step-3 tests ran unloaded and fire `destroy()` about 0.5 s after `run()` without controlling the order of the removal and the exit-code read; the step-3 mutations (M19 to M22) concerned the record and the lock, not the classification.
- **What this does not change.** The lock and record-retention determination above stands; in the loaded loops no container was left behind afterwards. The defect is in the outcome classification.

**D11 — CLOSED on new evidence (October 6 2026).** The defect above is fixed and verified; D11 returns to PASS on the evidence below, with the reopening kept in the record.

- **Fix.** PR #68 (merge commit `f544afd`, fix commit `62ffbd0`): `destroy()` records a per-handle `destroy_requested` marker before its first await and only for a RUNNING handle; `_classify` consults it with fixed causal precedence (OOM kill, requested cancel, requested destroy, missing exit code, normal completion). Exit 137 alone decides nothing.
- **Both sides of the race.** A test that forces the old failing interleaving with events (the read returns 137 while the container still exists) was red 8 of 8 on the unfixed code (`COMPLETED == ERROR`) and green 15 of 15 after; the opposite order (nothing to read) also gives `ERROR`. A workload that SIGKILLs itself stays `COMPLETED` with exit 137; destroying one sandbox leaves another's outcome unchanged; cancel then destroy gives `CANCELLED`; a failed destroy of a never-run handle does not mislabel a later run.
- **Loaded verification.** The same load that reproduced the defect (6 concurrent workers, 3 CPU burners, 1-core VM): 0 failures in 36 runs of the original run+destroy test, against 17 in 48 and 3 in 36 before the fix.
- **Mutation testing of the marker and the classifier.** Six mutants (classifier ignores the marker; marker set after the removal; exit 137 alone means ERROR; global marker; destroy beating cancel; marker set for any handle state) were each caught, source restored byte-identical each time. The first form of the "set too late" mutant was a syntax error, so it was invalid and was redone.
- **Full suite.** `tests/core/sandbox`: 6 consecutive runs of 153 passed on the fix branch, then 6 more on the exact tree that PR #64 (the D7 heartbeat test fix) and the fix produce together (tree `4e4a632dd4fcccd53e72074d8b21a02c0f42c6cb`, which the merge commit `0411e6c` reproduced exactly), plus 20 targeted runs of each heartbeat test with 0 failures. Zero containers, network endpoints and temp directories were left after each batch; mypy and the drift check were clean.
- **Limits, stated.** The loaded verification is one load profile on one 1-core host (36 runs); a full-suite run under load was not done; the verdict is about the classification race, not a proof of every possible interleaving. No known-failures entry was added and no assertion was weakened.

### 19.2 The cancel-during-start race, and the unexplained failure

**What was being explained.** One DockerBackend-file run showed 1 failed / 78 passed right after heavy container churn; I did not capture which test, so the output is lost. The step-4 hypothesis was a start/cancel lifecycle race: `run()` marks the handle `RUNNING` before `docker start` has completed, and a `cancel()` in that window sends `docker kill` at a container that is not running yet.

**Intended state machine.** `SandboxState` has four members and D12 forbids adding more, so "starting" and "cancelling" can only be *private phases of `RUNNING`*: PROVISIONING, then `run()` makes it RUNNING (including start-in-flight until the container is actually running), then TERMINATED on exit or kill. `cancel()`'s contract ("kill a running sandbox and every descendant; idempotent") does not promise to wait for a start, and it must not: that would reintroduce the serialization D11 forbids. So `cancel()` records intent and sends its immediate kill; `run()` owns enforcement.

**Reproduction (deterministic).** `test_d7_cancel_during_an_in_flight_start_cannot_be_escaped_by_the_workload` delays the real `docker start` and asserts six facts in order: the start is blocked; the container is still `created`; `cancel()` is invoked in that interval and returns promptly (it is not serialized behind the start); a `docker kill` ran while the start was pending, against a container that had not started; the start then completes; and the workload is not left running, with `run()` reporting `CANCELLED`, exit code 137, and `inspect()` `TERMINATED`. On the unmodified code facts 1–3 held and the next failed: the start completed after `cancel()` and the workload was still running.

**The same mechanism breaks tests that already existed.** With a scratch plugin (not committed) that makes every `docker start` 1.5s late, **4 of the 10 existing cancel tests failed on the unmodified code**: `test_cancel_kills_full_process_tree`, `test_d10_cancellation_then_destroy_leaves_nothing`, `test_c1_cancel_with_exit_137_is_cancelled_not_resource_exceeded` and `test_d7_cancel_reaches_a_grandchild_that_was_provably_alive_before`. They all passed with no injection. That is the failure class of the unexplained one-off.

**Status of the original failure, stated precisely.** The *mechanism* is established and reproduced. That it *caused* the one-off failure is **not proven**: the failing test was not captured, and I cannot reproduce a failure I cannot name. What is documented: it did not recur across 9 full-file runs, 3 full-suite runs and 6 runs of the 40 most timing-sensitive tests since; and the fix removes the failure class under injected latency. Two silent failures during this investigation are recorded as process lessons: a call whose Docker daemon was not up (a cold start after a VM restart) with its output discarded, so every Docker-gated test was skipped ("10 skipped") and nothing was run; and the unnamed one-off itself. Both are now guarded: abort if the daemon is not ready, never discard the start script's output, always capture failures by name.

**Fix.** `cancel()` on a `RUNNING` handle records intent (a private `asyncio.Event`) and sends the immediate kill as before. `run()` starts `_enforce_cancellation`, which waits for that event and then re-sends `docker kill` every 50 ms until the container is dead (`run()` cancels it in a `finally`). No new public state, no lock, and `cancel()` never waits. Residual semantics: the workload may execute for roughly one enforcement interval plus the kill's latency (tens of milliseconds) after a delayed start lands; cancellation prevents it running to completion, it cannot un-start a start already in flight.

**Alternatives compared.** Record intent and enforce in `run()` (chosen). An explicit startup state plus polling `docker inspect` for "running" would add private state and calls for the same effect. Locking `run()` and `cancel()` together was rejected: `cancel()` would no longer be able to interrupt the operation it cancels. Having `cancel()` wait for the start was rejected and is guarded by a mutant (below).

**Evidence.** Mutations: M23 (`cancel()` does not record intent), M24 (the enforcer kills once), M25 (the enforcer is never started), each caught by "the start completed after cancel() and the workload is still running"; M26, the rejected design where `cancel()` waits, caught by "cancel() blocked on the in-flight start". Source restored byte-identical each time. After the fix, all cancel tests pass normally and with every `docker start` 1.5 s and 3.0 s late.

**Test changes, with reasons.** `test_cancel_kills_full_process_tree` and `test_d7_cancel_reaches_a_grandchild_that_was_provably_alive_before` replaced fixed sleeps with waiting for the grandchild itself and awaiting `run()` before reading. Both are strictly stronger: the old process-tree test could pass vacuously when the grandchild never started, and it failed under a slow start because the workload wrote a heartbeat in the milliseconds before enforcement landed.

### 19.3 Step-4 results, as of this section

| Check | Result |
|---|---|
| DockerBackend targeted suite | 88/88 on three consecutive runs, failures captured by name, none |
| mypy (both files) | clean |
| Orphans after every run | 0 containers, 0 shared-network endpoints, 0 artifact temp dirs |
| Full `tests/core/sandbox` | 147 passed, 0 DockerBackend failures |
| Frozen files | the 7 out-of-scope files byte-identical |

**`test_net_proxy.py` flake, recorded separately from any DockerBackend result.** Run alone, the file failed in **3 of 6** runs: `test_plain_http_to_allowed_host_is_forwarded` twice and `test_connect_to_allowed_host_tunnels_real_data` once. Run inside the full suite it usually passes (this run: 147/147), which hides how frequent it is. Neither `_net_proxy.py` nor its test file is touched by this workstream, the cause is undiagnosed, and it is not called environmental. It belongs with the network redesign (`_net_proxy.py` is in that workstream's scope), together with the two unexplained plain-HTTP behaviors already recorded in §17.5.

### 19.4 Step 5: the completion decision (October 2 2026)

**Decision: Outcome 2. `sandbox-fabric` remains explicitly incomplete.** Outcome 1 (every checklist requirement evidenced) is not reachable: 22 of the 28 checklist items are PASS and six are not. No overall sandbox-security closeout is issued, and none may say that the network-isolation claims passed (§17.3). The user's instruction calls this "Issue 2"; it is the second of the two outcomes laid down for step 5.

**Decisions recorded, verbatim from the user's instruction of October 2 2026** (opened with "Defaults. Apply the four decisions below:"):

> 1. B4 — Formally accept the `handoff.md` exception and document it explicitly in §19.4. Do not represent this as general compliance with the authorized-file list.
> 2. D9 — Leave it BLOCKED. Do not open a new workstream to make backends publish through `EventStream` as part of this closure.
> 3. DEBT-039 — Confirm this ID and prepare to record it, together with the corresponding DEBT-021 update, on a separate branch/PR, because `KNOWN_ISSUES.md` is outside the `sandbox-fabric` scope.
> 4. Network redesign — Do not open it now. Leave it as future work independent of this closure.
>
> Now write §19.4 and close Step 5 with Issue 2: sandbox-fabric remains explicitly incomplete.

**The six items that are not PASS, with the exact blocker for each** (statuses as directed; the full matrix is §18.2):

| ID | Status | Exact blocker | What would move it | Tracked as |
|---|---|---|---|---|
| A1 | **BLOCKED** | Both capability claims it pairs are withdrawn (`NETWORK_ALLOWLIST`, `NET_NAMESPACE`), so its required verification (an allowlist request admitted and reaching the proxy path) cannot be run | The network redesign, and a direct committed `NET_NAMESPACE` gate (§17.8) | DEBT-039 (network redesign). The paired-claim invariant mechanism itself is sound and tested |
| A9 | **UNVERIFIED** | The `AF_VSOCK` probe was run and is negative (the `socketcall(2)` bypass is open on this host); `AF_ALG` is not exercisable because this kernel lacks it. Protection is established for neither | The same LSM-enabled host as C3 (an active AppArmor or SELinux policy, and a Docker release containing the socketcall fix); `AF_ALG` additionally needs a kernel that exposes it. `SECCOMP` stays unclaimed | Host dependency; not registered as a debt |
| B4 | **EXCEPTION ACCEPTED** | `handoff.md` is on no allow-list in B4's literal text | Nothing further: the exception is accepted (below) | n/a |
| C2 | **FAIL** | Sandbox B obtained a tunnel through sandbox A's proxy on the shared gateway (§17.2; reproduction in §17.7) | The network redesign, and a passing concurrent A/B test with deliberately different allowlists (§17.4) | DEBT-039, dependent on the network redesign |
| C3 | **BLOCKED** | It requires two outcomes recorded together: the exploit probe blocked and a benign compat probe still working. The first cannot be obtained on this host. Not N/A: the item has no N/A clause | The same LSM-enabled host as A9 | Host dependency; not registered as a debt |
| D9 | **UNVERIFIED — BLOCKED** | No lifecycle-event producer exists: `core/sandbox/events.py` defines `EventStream`, nothing in the repository publishes to it (`NamespaceBackend` included), and nothing outside tests imports `core.sandbox`. The required full-lifecycle event test cannot be written | A decision either to make backends publish through `EventStream` (and then run the test) or to amend D9. Neither is opened by this closure | Not registered as a debt |

**Final tally** (the Status column of §18.2): 22 PASS (A2–A8, B1–B3, C1, D1–D8, D10–D12), 1 FAIL (C2), 3 BLOCKED (A1, C3, D9; D9 is also unverified and is counted once), 1 UNVERIFIED (A9), 1 EXCEPTION ACCEPTED (B4); 22 + 1 + 3 + 1 + 1 = 28. The accepted B4 exception does not make B4 a PASS and is not what keeps the workstream incomplete; A1, A9, C2, C3 and D9 do.

**B4: the accepted exception, stated narrowly.** What was accepted: the presence of `handoff.md` among the files touched by this workstream's own commits, although B4's literal allow-list (`docker_backend.py`, private helpers, the test file, additive `SandboxCapability` entries, "this checklist/addendum") does not include it. The file was created on explicit user instruction, and the project's handoff protocol requires a handoff. What this is not: it is not general compliance with the authorized-file list, not a precedent for any other file, and not an extension of B4's list. The acceptance as given names `handoff.md` only. The reconciliation document's standing is unchanged by it: as recorded in §18.6, that document is authorized by the base prompt's Definition of Done (which outranks the checklist) but is not named in B4's list, and this section does not stretch the user's acceptance to cover it. Everything else in §18.6 stands: none of `SandboxBackend`, `NamespaceBackend`, `_ns_init.py`, `_seccomp.py`, `_net_proxy.py`, `admission.py` or `contracts.py` differs from the base.

**What step 5 did not change.** No code, test, capability claim or contract changed. `_CAPS` is still 7 of 12 (`NETWORK_ALLOWLIST` and `NET_NAMESPACE` remain withdrawn; `NETWORK_DENY_DEFAULT`, `SECCOMP` and `USER_NAMESPACE` remain unclaimed). The only edits are in this document: the §18 headline, the status vocabulary, the B4 row (§18.2), the B4 bullets (§18.6, §18.8), and this subsection. The frozen addendum and checklist were not touched.

**DEBT-039 and DEBT-021: confirmed, to be recorded on a separate branch/PR (not applied here).** `KNOWN_ISSUES.md` is outside this workstream's file boundary, so nothing was written to it. The id DEBT-039 is confirmed for the cross-sandbox egress finding (`DEBT-038` is `main`'s `/distill` `module_name` path traversal, PRs #37 and #38). The word "proposed" attached to DEBT-039 in §17.2, §17.6 and the §18 notes is superseded as to the id, not as to registration, which is still pending. The DEBT-039 entry to record is the one in §17.6. The corresponding DEBT-021 update, as a draft for that PR: DEBT-021's entry on `main` still says there is no Docker-backed implementation; it should instead say that a Docker-backed implementation exists on branch `sandbox-fabric` (`core/sandbox/backends/docker_backend.py`) and is **explicitly incomplete** per §19.4 of this document (22 of 28 checklist items PASS; A1, A9, C2, C3 and D9 open; B4 an accepted exception), with the claimed capability set at 7 of 12 and the network-isolation claims withdrawn pending DEBT-039. The entry should not say the debt is resolved.

**Remaining follow-up work, none of it part of this closure and none to be started inside it:**

1. Record DEBT-039 and the DEBT-021 update in `KNOWN_ISSUES.md` on a separate branch/PR (authorized; not yet done).
2. Network redesign (C2, A1, the `NET_NAMESPACE` gate, and the `test_net_proxy.py` flake with its two unexplained plain-HTTP behaviors, §17.5 and §19.3): a future workstream, independent of this closure, worked from the §17.4 invariant. Not opened.
3. An LSM-enabled host with a Docker release containing the socketcall fix, to settle A9 and C3; a kernel exposing `AF_ALG` for the rest of A9. Not scheduled.
4. D9: a later decision between a lifecycle-event producer and an amendment to D9. Not opened.
5. The §17.5 follow-ups, unchanged (state left `RUNNING` after a failed `docker start` spawn, the create-unwind residual, a finalizer for failing D10 tests, the stale test-module docstring).
6. `handoff.md` version 2 still describes step 5 as open and lists the four decisions above as pending; this subsection supersedes that. It was not edited, to keep this closure's change set to this document, and it needs a refresh or retirement when the next session picks up one of the items above.

**Verification of this step.** Documentary: the Status column of §18.2 was parsed after the edit: 28 rows; 22 PASS, 1 FAIL (C2), 1 EXCEPTION ACCEPTED (B4), BLOCKED for A1 and C3, UNVERIFIED for A9, and "UNVERIFIED — BLOCKED" for D9, which the tally counts once, under BLOCKED, as §18 always has. That is 22 + 1 + 1 + 3 + 1 = 28, matching the tally above. The commit's diff contains this document only; `core/`, `tests/`, the frozen addendum and checklist, `handoff.md` and `KNOWN_ISSUES.md` are unchanged.

**Addendum (October 6 2026).** D11 was reopened as DEFECT IDENTIFIED (§19.1) after this decision was recorded. The final tally above was superseded while D11 was open and holds again now that D11 is closed on new evidence (§19.1); the decision itself (Outcome 2, `sandbox-fabric` explicitly incomplete) and every other status are unchanged.
