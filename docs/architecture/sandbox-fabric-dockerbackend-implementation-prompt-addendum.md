# Sandbox Fabric — DockerBackend Implementation Prompt: Pre-Implementation Addendum

> Reconstructed from the PDF originally supplied to this session
> (`sandbox-fabric-dockerbackend-implementation-prompt-addendum_1_.pdf`)
> and committed here verbatim (content unchanged) so that a future
> session does not depend on that upload being available again. See
> `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`
> §10 for the provenance note.

Amends: `sandbox-fabric-dockerbackend-implementation-prompt.md` (commit
`d53b164290c41ad9f3c000f14cbc82ddd64d5f63`). Does not edit that file —
a committed, ready-to-fire prompt stays as committed; corrections land
here instead, per the project's architecture-freeze convention (record
deviations, don't silently rewrite frozen material).

**Status:** Source-verified against `sandbox-fabric` at `d53b164` —
`core/sandbox/contracts.py`, `admission.py`, `backend.py`,
`backends/namespace_backend.py`, `backends/_ns_init.py` read directly.

**Scope discipline:** Nothing here authorizes touching `SandboxBackend`,
`NamespaceBackend`, `_ns_init.py`, `_seccomp.py`, `_net_proxy.py`, or
unrelated architecture. The DockerBackend session may still only
create `docker_backend.py`, its own small helpers,
`test_docker_backend.py`, additive `SandboxCapability` entries, and
this addendum — per the original prompt's own Definition of Done.

Every item is labeled **Verified** (a specific, checked fact about the
existing code or the committed prompt's actual text, with citation) or
**Required** (a design/test obligation for code that doesn't exist yet
— no claim about current state either way).

## A. Verified gaps — the committed prompt is silent on these

### A1. Admission-layer dependency: `NETWORK_ALLOWLIST` requires explicit `NET_NAMESPACE` claim

**Verified:** `admission.py`'s `check_admission()` runs two independent
fail-closed checks when `request.policy.allowed_hosts` is non-empty:

1. `NET_NAMESPACE` must be supported — otherwise rejected: "backend
   cannot isolate network at all."
2. `NETWORK_ALLOWLIST` must be supported — otherwise rejected: "only
   supports deny-all network policy."

This creates a hard dependency for Phase 5: a DockerBackend
implementation that claims `NETWORK_ALLOWLIST` but does not explicitly
claim `NET_NAMESPACE` will still reject every request using
`allowed_hosts`. The first admission check fires before the allowlist
check is reached, so the network-allowlist feature would be
functionally broken even if the Phase 5 implementation and its tests
otherwise pass.

**Required:** the Phase 5 capability work must establish that the
Docker backend explicitly claims every capability required by the
admission path it is intended to satisfy, including `NET_NAMESPACE`
alongside `NETWORK_ALLOWLIST`. This is an implementation dependency,
not an optional capability declaration.

### A2. Namespace capabilities beyond `USER_NAMESPACE` have no defined gate

**Verified:** Phase 2 (lines 42–49) covers only `USER_NAMESPACE` and
`NO_NEW_PRIVS`. `MOUNT_NAMESPACE`, `PID_NAMESPACE`, `UTS_NAMESPACE` —
all three exist in `SandboxCapability` and are all unconditionally
claimed by `NamespaceBackend` — appear nowhere in Phases 2–5. Phase 1
item 2 requires every capability to be added "only after its
corresponding gate below passes," which, read literally, means these
three can never be added: no phase defines what passing looks like for
them.

**Required:** either define a direct verification test for each
(container doesn't share the host mount namespace; can't see or
signal host PIDs; hostname/domainname changes stay container-local),
or explicitly decide DockerBackend won't claim them yet and say why.

### A3. Docker image source is unspecified

**Verified:** Phase 1 item 3 (line 37) writes the translation target
as `docker run <image> <command...>` — `<image>` is never defined
anywhere in Phases 0–6. `SandboxRequest` (`command`, `policy`,
`request_id`, `env`) and `SandboxPolicy` (`workspace_dir`,
`timeout_sec`, `memory_limit_mb`, `max_pids`, `allowed_imports`,
`allowed_hosts`, `read_only_paths`) both have no `image` field.

**Required:** image reference lives in backend-private configuration,
not on the public request. Resolve the configured reference to an
immutable digest before execution and record that resolved identity.
Callers must not be able to inject an arbitrary image via
`SandboxRequest`.

### A4. `SandboxRequest.env` handling is unaddressed, and existing precedent is a real design fork

**Verified:** Phase 1's six items (lines 35–40) cover `command`,
`RuntimeCapabilities`, events, `ArtifactManifest`, and additive-enum
rules — `env` isn't mentioned. `NamespaceBackend`'s actual current line
is `env = dict(os.environ); env.update(request.env)`: full
host-process-environment inheritance by default, `request.env` layered
on top as override, with no admission-time gating on env content
anywhere (`admission.py` has no env-related check at all).

**Required:** DockerBackend must deliberately choose and document its
env semantics rather than inherit whatever Docker's SDK/CLI default
happens to be. A container is a different trust boundary than a
namespace on the same host, so matching `NamespaceBackend`'s full-
inheritance precedent is not automatic — if intentionally required for
compatibility, that's a separately justified decision, not an accident
of Docker's defaults. In allowlist mode, `HTTP_PROXY`/`HTTPS_PROXY`/
lowercase variants must be forced to the real proxy endpoint **after**
`request.env` is applied, so a request can't redirect itself around
the enforced proxy.

### A5. `allowed_imports` is a pre-existing dead field, not a DockerBackend-specific gap

**Verified:** `SandboxPolicy.allowed_imports` exists; zero enforcement
anywhere in `admission.py` or `namespace_backend.py` (confirmed
directly — no match in either). This predates DockerBackend; it is
already true of the currently-deployed `NamespaceBackend` path.

**Required:** DockerBackend must make the same choice explicit rather
than silently inheriting the ambiguity — either preserve current
non-enforcement (documented as such), or implement and test real
enforcement. Do not build Docker-specific enforcement just to make the
field look honored.

### A6. Phase 2 doesn't cover the broader privilege surface

**Verified:** Phase 2 (lines 42–49) is scoped exactly to
`--userns-remap` and `--security-opt=no-new-privileges`. Nothing in
Phases 0–6 mentions `--privileged`, host PID/IPC/net/UTS namespace
sharing, `--cap-add`, device exposure, or mounted Docker/container-
runtime sockets.

**Required:** a dedicated gate confirming the container is started with
none of the above — a deliberately minimized capability surface, not
whatever falls out of implementation convenience.

### A7. Phase 0 confirms daemon reachability, not daemon identity

**Verified:** Phase 0 item 1 (line 22) is "confirm a real daemon is
reachable, not just the CLI installed." Nothing asks which daemon —
local Unix socket vs. rootless vs. remote API.

**Required:** Phase 0 must record the actual endpoint/security context
certified against. A remote or otherwise untrusted Docker API must not
silently qualify as the intended local sandbox runtime.

### A8. Phase 0 has no host kernel/cgroup inventory

**Verified:** Phase 0's six items (lines 22–27) cover Docker version,
the CVE fix-date check, `--userns-remap`, no-new-privileges,
AppArmor/SELinux, and iproute2 presence. None records host kernel
version, cgroup v1/v2, or cgroup driver.

**Required:** add these — the CVE and resource-limit guarantees
exercised in Phases 3–4 depend on host kernel/cgroup configuration,
not on Docker's own version alone.

### A9. `AF_VSOCK` has no explicit test of its own

**Verified:** Phase 4's title and Phase 0 item 2 both name
`AF_ALG`/`AF_VSOCK` together as the CVE-2026-31431 fix boundary. Phase
4 item 1's actual instruction only spells out `socket(AF_ALG, ...)`.

**Required:** test `socket(AF_VSOCK, ...)` directly and separately. A
successful `AF_ALG` block is not evidence that `AF_VSOCK` is also
blocked.

## B. Extensions to gates the prompt already states — not silent gaps

- Phase 3's OOM/PID re-run (real, lines 53–58) should additionally
  distinguish an actual cgroup OOM kill from an ambiguous
  exit-code-137-style signal — don't infer `RESOURCE_EXCEEDED` from
  the exit code alone; inspect container/cgroup state directly where
  available.
- Phase 5's network test (real, lines 73–78) already proves: an
  allowed host succeeds through the proxy, a disallowed host is
  rejected, deny-all has no route out. It does not prove a direct
  connection can't bypass the proxy entirely, that the Docker gateway
  can't serve as an alternate route, that another reachable container
  can't bridge egress, or that `request.env` can't redirect the proxy
  variables (see A4). These are additional adversarial angles on the
  same gate, not a new one.
- Phase 4 item 3's socketcall probe (real, line 66) should explicitly
  distinguish "is the bypass closed" from "are legitimate 32-bit/
  compat workloads broken." Docker's own documented mitigation history
  moved this from a blanket seccomp deny to AppArmor/SELinux rules
  specifically because the seccomp-only version broke 32-bit programs
  — a closed bypass that silently breaks compat workloads shouldn't be
  reported as a clean pass.
- Phase 4 item 4's rule that `SECCOMP` must not be claimed to imply
  protection against this specific bypass, Phase 1 item 2's
  empty-until-earned capability rule, the architectural
  no-second-policy-surface rule, and the Definition of Done's
  file-touch scope boundary are already stated plainly in the
  committed prompt and aren't restated here.

## C. Implementation requirements — design/test obligations for unwritten code

Not claims that the prompt is silent by omission the way Section A's
items are documented gaps — ordinary engineering requirements, carried
over from tracing `NamespaceBackend`'s actual behavior as the
precedent DockerBackend must either match or deliberately diverge
from:

- **Filesystem mapping.** `_ns_init.py` (confirmed directly)
  bind-mounts `/bin, /lib, /lib64, /usr` plus policy `read_only_paths`
  into the workspace read-only, then `chroot`s into it. Docker instead
  provides an image-derived root filesystem. DockerBackend must
  explicitly define the mapping between image rootfs, `workspace_dir`,
  the command's working directory, `read_only_paths`, and
  artifact-producing paths — and whether it preserves "the workspace
  is the execution filesystem root" or documents a deliberately
  different model.
- **`read_only_paths` translation.** Confirmed actively consumed by
  `NamespaceBackend`/`_ns_init.py` today. Docker must map each path
  explicitly and test read-only-enforcement, symlink/traversal
  resistance, and absence of unintended host-path exposure.
- **Root filesystem mutability.** `NamespaceBackend`'s model is
  read-only base plus explicit writable workspace (confirmed).
  Docker's default container root is otherwise writable. DockerBackend
  needs an explicit writable-filesystem policy and a test proving a
  payload can't turn an intended-read-only area into a writable
  host-backed path.
- **Container identity.** `SandboxHandle` (`handle_id`, `request_id`,
  `backend_name`, `state` — confirmed, no Docker ID field) stays as-is;
  the Docker container ID lives in backend-private state, named/
  labeled to avoid collisions and support cleanup of abandoned
  containers.
- **Artifacts.** `ArtifactManifest` stays `(relative_path, sha256_hex,
  size_bytes)` (confirmed). Docker must define extraction mechanism,
  path normalization, traversal/symlink rejection, and hashing over
  actually-retrieved bytes, and must never follow a sandbox-created
  symlink into an arbitrary host path.
- **Lifecycle/state mapping.** `TerminationReason` (`COMPLETED` /
  `TIMEOUT` / `RESOURCE_EXCEEDED` / `CANCELLED` / `ERROR`) and
  `SandboxState` (`PENDING` / `PROVISIONING` / `RUNNING` /
  `TERMINATED`) (both confirmed exactly) must not leak Docker's own
  richer state model into the public contract. Test run-before-create,
  double-run, cancel-before-run, cancel-after-terminate, double-
  destroy, inspect-after-destroy.
- **Cancellation.** `NamespaceBackend.cancel()` does
  `self._killpg(state.pgid)` — process-group kill, not single-PID
  (confirmed directly). Docker tests need a parent/child/grandchild
  tree and must verify no descendant survives, not just that
  `docker stop` returns or the top-level PID disappears.
- **`inspect()`.** Contract requires it side-effect-free; test that
  repeated calls don't start/restart/alter a container.
- **Events.** `SandboxEventType` (`STARTED` / `PROVISIONED` /
  `RESOURCE_EXCEEDED` / `FINISHED` / `ERROR`, confirmed exactly) is the
  only event surface — lifecycle results like cancellation/timeout go
  through existing event types and `detail`, not a new taxonomy.
- **Failure-path cleanup.** Exercise failure at container creation,
  network setup, start, execution, timeout, cancellation, external
  container disappearance, and daemon/API failure; verify no orphaned
  container/network/mount/proxy-listener/handle-state after each;
  `destroy()` stays idempotent.
- **Concurrency.** `run() + cancel()`, `run() + destroy()`,
  `cancel() + destroy()`, repeated `cancel()`/`destroy()`,
  `inspect()` mid-transition — must not orphan containers or corrupt
  handle bookkeeping. No contract change required, just race-safe
  backend bookkeeping.
- **No new public surface.** No `image` on `SandboxRequest`, no Docker
  ID on `SandboxHandle`, no second policy/admission/event mechanism.
  New `SandboxCapability` values only with a demonstrated
  cross-backend need.

Not included here: the observation that `NamespaceBackend._CAPS` is a
static, unconditionally-claimed set with no runtime gate of its own.
Real, but a separate cross-backend audit question, not a
DockerBackend-prompt gap — out of this addendum's scope unless that's
explicitly opened up.
