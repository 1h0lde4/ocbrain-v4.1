# Sandbox Fabric — DockerBackend: Implementation Checklist

**Derived from:** `sandbox-fabric-dockerbackend-implementation-prompt.md` (`d53b164`) + `sandbox-fabric-dockerbackend-implementation-prompt-addendum.md` (frozen — not re-opened by this document). One checklist item per addendum item, A through D.
**Purpose:** bridge from "the specification is reconciled" to "here is exactly what implementation remains." Reference document only — no repository files touched or modified in producing this.
**Fields per item:** File/module · Symbol/code path · Required behavior · Invariant · Test/verification · Forbidden shortcut (where applicable).

---

## A — Verified gaps (9)

### A1. `NET_NAMESPACE` admission dependency
- **File/module:** `core/sandbox/backends/docker_backend.py` (new)
- **Symbol/code path:** `DockerBackend.capabilities`, consumed by `admission.py`'s `check_admission()`
- **Required behavior:** `supported` must include `NET_NAMESPACE` whenever it includes `NETWORK_ALLOWLIST`
- **Invariant:** `NETWORK_ALLOWLIST ∈ supported ⟹ NET_NAMESPACE ∈ supported`
- **Test/verification:** admission-layer test — a request with non-empty `allowed_hosts` is not rejected once both capabilities are declared together; integration test confirms the request actually reaches the proxy path
- **Forbidden shortcut:** declaring `NETWORK_ALLOWLIST` alone because deny-all tests still pass (deny-all never exercises this admission check)

### A2. Undefined namespace capabilities (`MOUNT`/`PID`/`UTS`)
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** `DockerBackend.capabilities` — no gate defined in Phases 2–5 for these three
- **Required behavior:** each of `MOUNT_NAMESPACE`, `PID_NAMESPACE`, `UTS_NAMESPACE` gets a defined test before being claimed, or is explicitly left unclaimed with a stated reason
- **Invariant:** no capability enters `supported` without a corresponding passing gate recorded somewhere (this document or a later revision)
- **Test/verification:** `PID_NAMESPACE` — container can't see/signal host PIDs; `MOUNT_NAMESPACE` — a mount made in-container isn't visible on the host and vice versa; `UTS_NAMESPACE` — `hostname` change in-container doesn't affect the host
- **Forbidden shortcut:** claiming any of the three "because Docker uses namespaces by default"

### A3. Docker image source unspecified
- **File/module:** `core/sandbox/backends/docker_backend.py` — **not** `contracts.py`
- **Symbol/code path:** backend-private config (e.g. `_DOCKER_IMAGE_REF`), resolved in `__init__`/`create()`
- **Required behavior:** image is fixed by backend configuration, resolved to an immutable digest before first use, digest recorded in create-time provenance
- **Invariant:** `SandboxRequest` gains no `image` field; nothing in the request can select or influence the image
- **Test/verification:** two `create()` calls resolve to the identical digest; a request supplying any image-like value (via `env` or elsewhere) has no effect on what runs
- **Forbidden shortcut:** reading an image ref out of `request.env` "temporarily"

### A4. `SandboxRequest.env` handling + inheritance fork
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** container env construction, vs. `NamespaceBackend`'s existing `env = dict(os.environ); env.update(request.env)` (precedent, not to copy silently)
- **Required behavior:** explicit minimal base env (recommended: not `os.environ`) plus `request.env`; in allowlist mode, `HTTP_PROXY`/`HTTPS_PROXY`/lowercase variants forced to the real `_net_proxy.py` endpoint *after* `request.env` is applied
- **Invariant:** no host-process env var reaches the container unless the chosen policy explicitly allows it; proxy vars in allowlist mode are never what `request.env` supplied
- **Test/verification:** set a host-only env var, assert absent in container; set `request.env["HTTP_PROXY"]` to something else in allowlist mode, assert the real proxy value wins
- **Forbidden shortcut:** `env=os.environ.copy()` "to match `NamespaceBackend`" without recording it as an intentional decision

### A5. `allowed_imports` — pre-existing dead field
- **File/module:** `core/sandbox/admission.py` (only if enforcement is chosen) or none (if non-enforcement is preserved)
- **Symbol/code path:** `SandboxPolicy.allowed_imports` — currently unread anywhere
- **Required behavior:** explicit recorded decision: (a) DockerBackend also doesn't enforce it (matches current state, no code change), or (b) real enforcement is implemented at the shared `admission.py` level, not Docker-only
- **Invariant:** `NamespaceBackend`'s current (non-)enforcement doesn't change as a side effect of this decision
- **Test/verification:** (a) test documenting a restrictive value still runs unimpeded; (b) test that a disallowed import is actually blocked
- **Forbidden shortcut:** Docker-only cosmetic filtering that looks like enforcement without actually restricting anything

### A6. Broader privilege surface ungated
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** container-creation call site
- **Required behavior:** never `--privileged`; never share host pid/ipc/net/uts namespaces; no `--cap-add` beyond an explicitly justified minimal set; no `--device`; no mounting the Docker/container-runtime socket; no undocumented host bind mounts
- **Invariant:** `docker inspect` on a live sandbox container shows `Privileged: false`, minimal `CapAdd`, and private (not `host`) namespace mode for pid/ipc/net/uts
- **Test/verification:** post-`create()` test asserting each `docker inspect` field above programmatically
- **Forbidden shortcut:** `--cap-add=SYS_ADMIN` or similar "to make mounting work" instead of using the intended mechanism

### A7. Daemon identity not recorded
- **File/module:** Phase 0 host-inventory step (pre-implementation, not `docker_backend.py`)
- **Symbol/code path:** `docker context show`; `$DOCKER_HOST` if set
- **Required behavior:** record whether the daemon is local-socket, rootless, or remote, and confirm which one Phases 0–5 actually certified
- **Invariant:** no Phase 0–5 finding is treated as applying to "Docker" in the abstract — only to the recorded daemon
- **Test/verification:** recorded evidence line, not a code test
- **Forbidden shortcut:** running Phase 0 against whatever daemon is reachable without recording which one

### A8. No kernel/cgroup inventory
- **File/module:** same Phase 0 step
- **Symbol/code path:** `uname -r`; `docker info --format '{{.CgroupDriver}} {{.CgroupVersion}}'`
- **Required behavior:** Phase 0 output additionally records host kernel version, cgroup version, cgroup driver
- **Invariant:** Phase 3/4 resource and CVE conclusions are scoped to the recorded kernel/cgroup combination only
- **Test/verification:** recorded evidence line, not a code test
- **Forbidden shortcut:** assuming cgroup v2 as "the modern default" without checking

### A9. `AF_VSOCK` untested
- **File/module:** Phase 4 verification step; informs `docker_backend.py`'s claimed `SECCOMP` scope, doesn't change its code
- **Symbol/code path:** `socket(AF_VSOCK, SOCK_STREAM, 0)` probe, same harness style as the existing `AF_ALG` probe
- **Required behavior:** run as its own separate step from the `AF_ALG` probe; record pass/fail independently
- **Invariant:** capability writeup never claims `AF_VSOCK` blocked on the strength of the `AF_ALG` result alone
- **Test/verification:** probe result recorded for both address families separately
- **Forbidden shortcut:** "`AF_ALG` blocked, so `VSOCK` probably is too"

---

## B — Traceability rules (4)
Not implementation gaps. "Required behavior" here means *must remain true throughout*, not *must be newly built*.

### B1. `SECCOMP` ≠ CVE-specific protection
- **File/module:** final capability writeup / reconciliation report
- **Symbol/code path:** `SandboxCapability.SECCOMP`
- **Required behavior:** claiming `SECCOMP` never implies the `AF_ALG`/`AF_VSOCK`/socketcall bypass is closed
- **Invariant:** `SECCOMP ∈ supported` and "CVE-2026-31431 bypass closed" tracked as two independent facts, never merged
- **Test/verification:** reconciliation-report review checklist item
- **Forbidden shortcut:** n/a — reporting discipline, not code

### B2. Capabilities empty until earned
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** `DockerBackend.capabilities` initialization
- **Required behavior:** `supported` starts empty; gains a value only once its own gate passes
- **Invariant:** every claimed capability traces to a passing test in this checklist
- **Test/verification:** this checklist itself, checked against the final `supported` set at review time
- **Forbidden shortcut:** copying `NamespaceBackend`'s static `_CAPS` set as a starting point "to get something working"

### B3. No second policy surface
- **File/module:** `core/sandbox/backends/docker_backend.py` — must call, not reimplement, `admission.py` and `backends/_net_proxy.py`
- **Symbol/code path:** `check_admission()`, `AllowlistProxy`, `SandboxPolicy`/`SandboxRequest`/`SandboxResult`
- **Required behavior:** `DockerBackend` calls these; it defines no parallel admission function, proxy, or request/result shape
- **Invariant:** nothing in `docker_backend.py` duplicates a responsibility already owned by `admission.py`/`_net_proxy.py`/`contracts.py`
- **Test/verification:** code review; `docker_backend.py` imports `AllowlistProxy`/`check_admission` rather than reimplementing them
- **Forbidden shortcut:** raw `iptables`/Docker-native network policy standing in for `_net_proxy.py`

### B4. File-touch boundary
- **File/module:** governs the whole diff, not one file
- **Symbol/code path:** n/a
- **Required behavior:** diff touches only `docker_backend.py`, small genuinely-necessary private Docker helpers, `tests/core/sandbox/test_docker_backend.py`, additive `SandboxCapability` entries, and this checklist/addendum
- **Invariant:** `git diff --stat` shows no changes to `SandboxBackend`, `NamespaceBackend`, `_ns_init.py`, `_seccomp.py`, `_net_proxy.py`, or anything outside that list
- **Test/verification:** `git diff --stat` reviewed against this exact allow-list before calling the work done
- **Forbidden shortcut:** a "one-line fix" to `namespace_backend.py`/`_net_proxy.py` bundled into the same commit

---

## C — Gate extensions (3)

### C1. OOM classification precision
- **File/module:** `core/sandbox/backends/docker_backend.py` (result classification) + `tests/core/sandbox/test_docker_backend.py`
- **Symbol/code path:** mapping from container exit state to `TerminationReason.RESOURCE_EXCEEDED` vs `.ERROR`
- **Required behavior:** classification inspects actual state (`docker inspect`'s `OOMKilled` field, or cgroup `memory.events`' `oom_kill` counter) — not exit code `137` alone (SIGKILL can come from cancellation too)
- **Invariant:** `RESOURCE_EXCEEDED` only returned when corroborated by container/cgroup inspection
- **Test/verification:** memory-limit test asserts `OOMKilled: true` read before classifying; separate `cancel()` test with the same exit code confirms it's *not* misclassified as `RESOURCE_EXCEEDED`
- **Forbidden shortcut:** `if exit_code == 137: return RESOURCE_EXCEEDED`

### C2. Network bypass coverage
- **File/module:** `tests/core/sandbox/test_docker_backend.py`
- **Symbol/code path:** container network config + `_net_proxy.py`'s `AllowlistProxy`
- **Required behavior:** beyond allowed/disallowed/deny-all, test: raw connection bypassing `HTTP_PROXY` entirely fails; Docker bridge/gateway isn't a usable route; another reachable container can't relay egress; `request.env`-supplied proxy values are overridden (ties to A4)
- **Invariant:** with allowlisting active, the proxy is the *only* path out, not merely "the proxy enforces its rules when used"
- **Test/verification:** one adversarial test per bullet above
- **Forbidden shortcut:** testing only that a disallowed HTTP request through the proxy is rejected, and calling that network isolation verified

### C3. Socketcall / 32-bit-compat distinction
- **File/module:** Phase 4 verification step + final reconciliation report
- **Symbol/code path:** `_compile_socketcall_probe` (`tests/core/sandbox/test_seccomp.py`), run against the live Docker profile
- **Required behavior:** record two separate outcomes — bypass closed, and a legitimate 32-bit/compat operation still functions
- **Invariant:** "bypass closed" never reported without the compat-workload result alongside it
- **Test/verification:** exploit probe (expect blocked) + one benign compat-path probe (expect it still works, or flag as regression if not)
- **Forbidden shortcut:** reporting "socketcall gate: closed" from the exploit probe alone

---

## D — Implementation requirements (12)

### D1. Filesystem mapping
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** container creation's mount/working-dir args — Docker equivalent of `_ns_init.py`'s bind-mount + `chroot` sequence
- **Required behavior:** explicitly define image rootfs (read-only base), `workspace_dir`'s container mount point, working directory, `read_only_paths` mapping, artifact-write location
- **Invariant:** mapping is documented before `create()` is implemented, not reverse-engineered from `docker run` defaults after the fact
- **Test/verification:** file written to the documented workspace mount is retrievable as an artifact; write to an undocumented path fails
- **Forbidden shortcut:** relying on Docker's default `WORKDIR` and discovering the real mapping from test failures

### D2. `read_only_paths` translation
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** per-path bind-mount construction from `SandboxPolicy.read_only_paths`
- **Required behavior:** each declared path becomes a `:ro` bind mount at the same in-container path
- **Invariant:** write attempts fail; a symlink inside a read-only path can't escape to an unintended host path
- **Test/verification:** write-attempt test per declared path; symlink-traversal adversarial test
- **Forbidden shortcut:** mounting the parent directory read-write and relying on convention

### D3. Root filesystem mutability
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** `--read-only` (or SDK equivalent) + explicit writable-mount list
- **Required behavior:** image-derived root read-only; only `workspace_dir` (and any declared temp area) writable
- **Invariant:** write to any path outside the declared writable set fails
- **Test/verification:** adversarial write test against a non-workspace path (e.g. `/etc/`)
- **Forbidden shortcut:** leaving root writable because `--read-only` "broke something," without isolating the real cause

### D4. Container identity
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** backend-private mapping from `SandboxHandle.handle_id`/`request_id` to Docker container ID/name; naming/labeling scheme
- **Required behavior:** `SandboxHandle` gains no new field; container name/label includes `request_id`; cleanup can enumerate abandoned containers by label
- **Invariant:** no collision between concurrent sandboxes; every container this backend creates is externally identifiable for cleanup
- **Test/verification:** two concurrent sandboxes don't collide; a cleanup pass finds and removes a deliberately-abandoned labeled container
- **Forbidden shortcut:** `request_id` alone as container name with no collision handling

### D5. Artifacts
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** artifact-collection routine feeding `ArtifactManifest`
- **Required behavior:** defined extraction mechanism; path normalization and traversal rejection; symlinks inside the artifact root not followed if they point outside it; SHA-256 over actually-retrieved bytes
- **Invariant:** no manifest entry resolves outside the declared artifact root
- **Test/verification:** adversarial symlink-outside-root test (expect rejection); hash-mismatch test vs. independently recomputed hash
- **Forbidden shortcut:** trusting a container-reported file list without independently walking/hashing

### D6. Lifecycle/state mapping
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** Docker container state → `SandboxState`/`TerminationReason` mapping
- **Required behavior:** no Docker-specific state value ever appears in `SandboxResult`/`SandboxHandle`; deterministic mapping for every Docker state
- **Invariant:** run-before-create, double-run, cancel-before-run, cancel-after-terminate, double-destroy, inspect-after-destroy all have defined tested behavior (error/no-op, never a crash or raw-state leak)
- **Test/verification:** one test per case in the invariant
- **Forbidden shortcut:** letting an unmapped Docker state surface as a raw string

### D7. Cancellation
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** `DockerBackend.cancel()`
- **Required behavior:** terminates the full process tree inside the container, not just the top-level process — same standard as `NamespaceBackend.cancel()`'s `_killpg`, different mechanism
- **Invariant:** after `cancel()` returns, no descendant of the original command survives
- **Test/verification:** parent/child/grandchild process tree, `cancel()`, verify nothing survives via host or Docker inspection
- **Forbidden shortcut:** treating `docker stop`'s return, or top-level PID disappearance, as sufficient evidence

### D8. `inspect()`
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** `DockerBackend.inspect()`
- **Required behavior:** read-only — never starts, restarts, or mutates the container or recorded state
- **Invariant:** repeated `inspect()` calls produce identical state absent real external change
- **Test/verification:** multiple `inspect()` calls on a stopped container; assert it stays stopped, no new events emitted
- **Forbidden shortcut:** a Docker SDK convenience call with an implicit restart side effect

### D9. Events
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** `core/sandbox/events.py`'s `EventStream`; `SandboxEventType` (`STARTED`/`PROVISIONED`/`RESOURCE_EXCEEDED`/`FINISHED`/`ERROR`)
- **Required behavior:** publishes only through existing event types; Docker container ID (if useful) goes in `detail`, not a new event type
- **Invariant:** no new `SandboxEventType` value introduced
- **Test/verification:** full-lifecycle test (success, cancel, failure) emits only known event types in expected order
- **Forbidden shortcut:** ad hoc `sandbox.docker.container_started`-style new event type

### D10. Failure-path cleanup
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** `create()`, `run()`, `cancel()`, `destroy()` and their internal error paths
- **Required behavior:** cleanup reliably removes container, network resources, temp mounts, proxy listeners across: creation failure, network-setup failure, start failure, execution failure, timeout, cancellation, external disappearance, daemon/API failure
- **Invariant:** `destroy()` idempotent; no orphaned resource with this run's label after any failure path
- **Test/verification:** one test per failure point, each asserting no leftover labeled resource
- **Forbidden shortcut:** testing only the happy-path `destroy()` after a successful run

### D11. Concurrency
- **File/module:** `core/sandbox/backends/docker_backend.py`
- **Symbol/code path:** backend-private handle/state bookkeeping
- **Required behavior:** `run()`+`cancel()`, `run()`+`destroy()`, `cancel()`+`destroy()`, repeated `cancel()`/`destroy()`, `inspect()` mid-transition don't corrupt state or orphan containers — no public contract change, just race-safe internals
- **Invariant:** no interleaving produces two internal records for one handle, or a container with none
- **Test/verification:** concurrency test firing these pairs near-simultaneously, asserting a consistent outcome each time
- **Forbidden shortcut:** a lock so coarse it serializes unrelated sandboxes, or no lock at all

### D12. No new public surface (consolidating constraint)
- **File/module:** `contracts.py` (additive-only) + `docker_backend.py`
- **Symbol/code path:** `SandboxRequest`, `SandboxHandle`, `SandboxCapability`
- **Required behavior:** no new field on `SandboxRequest`/`SandboxHandle`; no new admission/event/policy class; any new `SandboxCapability` value additive and cross-backend-justified
- **Invariant:** `contracts.py` diff shows only additive enum entries, nothing else
- **Test/verification:** `git diff` review of `contracts.py` at final reconciliation (ties to B4)
- **Forbidden shortcut:** adding `image: str | None = None` to `SandboxRequest` "to unblock development, clean up later"
