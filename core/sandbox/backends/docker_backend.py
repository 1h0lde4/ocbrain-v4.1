"""core/sandbox/backends/docker_backend.py — Docker-daemon sandbox backend
(Sandbox Fabric, DEBT-021).

Architecture references:
    docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt.md
        (`d53b164` — committed, frozen, not edited by this work)
    sandbox-fabric-dockerbackend-implementation-prompt-addendum.md
        (frozen — 9 verified gaps (A1-A9), 4 carried-forward rules
        (B1-B4), 3 gate extensions (C1-C3), 12 implementation
        requirements (D1-D12); not yet committed to this repo as of
        this session — see reconciliation §10)
    sandbox-fabric-dockerbackend-implementation-checklist.md
        (frozen — per-item file/symbol/invariant/test/forbidden-shortcut
        mapping of the addendum; not yet committed to this repo either)

STATUS — history, then current state. This file was first written
(2026-09-21) with no Docker daemon reachable at all — every method
existed only to satisfy the interface, `capabilities` was `frozenset()`,
and "implemented" explicitly did not mean "verified" anywhere in it. A
later session in the same kind of environment installed `docker.io`
(Ubuntu's own package; Docker's own repo isn't reachable either) and
got a real daemon running, which changed what was possible: reconciliation
§§11-16 record, in order, real Phase 0 host inventory, A3/D-lifecycle
verification against a live daemon, the A9 seccomp-bypass finding (real,
reproducible, NOT mitigated — see `_lsm_active()` below), C2's full
network-isolation implementation and bypass testing, D11's concurrency
races, and finally the three remaining capability-evidence gaps
(NO_NEW_PRIVS/CGROUP_PIDS/FILESYSTEM_JAIL) closed with real adversarial
tests against the running container. `_CAPS` below reflects that, as
amended by reconciliation §17 — seven of the twelve `SandboxCapability`
values, each with its own adversarial runtime evidence, not a Docker
configuration knob assumed to imply one. `NETWORK_ALLOWLIST`, claimed as
of §16, was WITHDRAWN in §17: a concurrent A/B test showed one sandbox
can obtain egress through another sandbox's proxy on the shared
gateway, so per-sandbox egress enforcement is not demonstrated. `NET_NAMESPACE`
was withdrawn too (§17.8): it has no direct test of its own. Read
`_CAPS`'s own comment before trusting any individual claim; read
reconciliation §16 and §17 for the full evidence trail.

One consequence worth stating plainly, since it's a real behavior
change and not just a documentation update: `AdmissionGate.
check_admission()` requires `FILESYSTEM_JAIL`/`CGROUP_MEMORY`/
`CGROUP_PIDS` unconditionally, so a realistic non-networked
`SandboxRequest` is admitted through the normal admission-gated path.
A request that sets `allowed_hosts` additionally requires
`NET_NAMESPACE` and `NETWORK_ALLOWLIST`; with both withdrawn
(§17, §17.8) such a request is REJECTED at admission again. Both directions
of that boundary are tested, not just asserted here.

Still genuinely open, not silently treated as closed: A1/A2/A6's
runtime halves are covered, but A9 (the socketcall(2)/AF_VSOCK seccomp
bypass) was investigated and NOT mitigated — this host has no AppArmor
or SELinux, and the seccomp-only mitigation this session tried does
not work (see `_lsm_active()`'s own docstring for the full account).
`SECCOMP` is deliberately absent from `_CAPS` for exactly that reason.
C2's network isolation is real and tested, but Phase 5's remaining
adversarial depth (beyond what §14 covers) and C3's 32-bit-compat
regression question (moot without an attempted fix) remain
unaddressed. `USER_NAMESPACE` is absent because this daemon has no
userns-remap configured — claiming it would misrepresent the host, not
just this code.

Scope discipline (addendum B4 / base prompt Definition of Done): this
file, its own small private helpers, tests/core/sandbox/
test_docker_backend.py, and additive-only SandboxCapability entries in
contracts.py (none added — every value `_CAPS` claims below already
existed) are the whole authorized surface. SandboxBackend,
NamespaceBackend, _ns_init.py, _seccomp.py, and _net_proxy.py are read
from (imported, in _net_proxy's case — addendum B3) but never modified.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field

from core.sandbox.backend import SandboxBackend
from core.sandbox.backends._net_proxy import AllowlistProxy
from core.sandbox.contracts import (
    ArtifactManifest,
    RuntimeCapabilities,
    SandboxCapability,
    SandboxHandle,
    SandboxRequest,
    SandboxResult,
    SandboxState,
    TerminationReason,
)

# Addendum B2: each value here requires its own passing gate,
# individually — not Docker configuration knobs, demonstrated security
# properties. As of reconciliation §17, seven of the twelve
# SandboxCapability values have real, adversarial, runtime evidence
# (see that section for the full account; this comment is the
# short form):
#   MOUNT_NAMESPACE, PID_NAMESPACE, UTS_NAMESPACE  -- §12 (A2): a host
#       mount made after the container starts is invisible inside it;
#       a real host PID can't be signaled or seen; the container's
#       hostname is independent and can't be changed from inside.
#   CGROUP_MEMORY -- §12 (C1): a real OOM kill is distinguishable from
#       an ordinary SIGKILL via State.OOMKilled, not inferred from the
#       exit code.
#   NO_NEW_PRIVS -- §16: /proc/self/status on the running container
#       itself (the base prompt's actual Phase 2 method), not just the
#       create request's HostConfig.
#   CGROUP_PIDS -- §16: a bounded process-creation burst reaches the
#       configured ceiling, further creation fails, the container
#       stays exec-able while still under pressure, destroy() is
#       clean, no host-side process leak.
#   FILESYSTEM_JAIL -- §16: the actual attack surface, not just
#       ReadonlyRootfs=true — workspace write succeeds; root
#       filesystem write, an unrelated path, a `..` traversal, and a
#       symlink pointing out of the workspace are all denied
#       (EROFS); the workspace remains writable afterward.
#
# Deliberately NOT claimed:
#   NETWORK_ALLOWLIST -- WITHDRAWN (it was claimed as of §16). §17:
#       with two concurrent sandboxes holding different allowlists,
#       sandbox B obtained a tunnel to a host only A's allowlist
#       permits, by connecting to A's proxy on the shared gateway.
#       Per-sandbox egress enforcement is not demonstrated. Re-earn it
#       only with a concurrent A/B regression test that passes.
#   NET_NAMESPACE -- WITHDRAWN (§17.8). Docker does build a separate
#       network namespace per container, and nothing here changes that:
#       this withdraws the CLAIM, not the implementation. It has no
#       direct committed test (its only cited evidence was the C2 set,
#       which tests egress paths, not namespace separation). Re-earn it
#       only with a test that the sandbox's netns differs from the
#       host's AND that concurrently created sandboxes have distinct
#       netns. Passing that re-earns NET_NAMESPACE alone: it does not
#       resurrect NETWORK_ALLOWLIST or C2 (DEBT-038 stays open).
#   USER_NAMESPACE -- no userns-remap configured on this daemon (§11);
#       claiming it would misrepresent the host, not just this code.
#   SECCOMP -- claiming it would imply protection against the
#       specific CVE-2026-31431 bypass this session found and did NOT
#       close (§13); B1's own rule is exactly that SECCOMP must never
#       be claimed to imply that.
#   NETWORK_DENY_DEFAULT -- admission.py never actually consults it
#       (checked directly before adding anything here), and the
#       addendum's own D12 test for a new claim is a demonstrated
#       cross-backend need, not "Docker can also do this."
_CAPS = RuntimeCapabilities(
    backend_name="docker",
    supported=frozenset(
        {
            SandboxCapability.MOUNT_NAMESPACE,
            SandboxCapability.PID_NAMESPACE,
            SandboxCapability.UTS_NAMESPACE,
            SandboxCapability.CGROUP_MEMORY,
            SandboxCapability.NO_NEW_PRIVS,
            SandboxCapability.CGROUP_PIDS,
            SandboxCapability.FILESYSTEM_JAIL,
        }
    ),
)


def _check_a1_paired_capability_invariant(caps: RuntimeCapabilities) -> None:
    """Addendum A1. admission.py's check_admission() runs two independent
    fail-closed checks for a request with allowed_hosts set: NET_NAMESPACE
    must be supported ("backend cannot isolate network at all") *and*
    NETWORK_ALLOWLIST must be supported ("only supports deny-all network
    policy") — checked separately, so claiming one without the other
    leaves allowed_hosts functionally broken even though both this
    module's own tests and Phase 5's own suite might otherwise pass.

    Enforced here at import time, not only in a test that could bit-rot:
    if a future change ever adds NETWORK_ALLOWLIST to _CAPS without
    NET_NAMESPACE alongside it, importing this module raises immediately
    rather than shipping a backend that silently can't do what it claims.
    """
    if SandboxCapability.NETWORK_ALLOWLIST in caps.supported:
        if SandboxCapability.NET_NAMESPACE not in caps.supported:
            raise AssertionError(
                "addendum A1: NETWORK_ALLOWLIST claimed without NET_NAMESPACE — "
                "admission.py's check_admission() would reject every "
                "allowed_hosts request regardless of what NETWORK_ALLOWLIST "
                "itself does; add NET_NAMESPACE to _CAPS alongside it"
            )


_check_a1_paired_capability_invariant(_CAPS)

# Addendum A3: image reference is backend-private configuration, never a
# field on SandboxRequest. Environment variable, not a hardcoded default —
# there is no globally-correct default image for arbitrary sandboxed
# workloads, and guessing one would be exactly the kind of silent
# assumption PI LAW 4 (Determinism Over Magic) rules out.
_IMAGE_REF_ENV_VAR = "OCBRAIN_SANDBOX_DOCKER_IMAGE"

# The container-visible mountpoint for SandboxPolicy.workspace_dir.
_WORKSPACE_MOUNT = "/workspace"


class DockerBackendError(RuntimeError):
    """Raised for any docker_backend.py failure. Deliberately not a new
    exception hierarchy mirrored anywhere else — callers already handle
    SandboxResult's own TerminationReason.ERROR for run()-time failures;
    this is only raised for create()/inspect()-time failures that have no
    SandboxResult to carry them, matching where NamespaceBackend lets
    exceptions propagate rather than swallowing them (PI's "no silent
    exception swallowing")."""


# --------------------------------------------------------------------
# Pure functions — no Docker daemon required. Real, run-now tests live
# in tests/core/sandbox/test_docker_backend.py.
# --------------------------------------------------------------------


def _build_container_env(
    request_env: dict[str, str],
    *,
    base_env: dict[str, str] | None = None,
    proxy_url: str | None = None,
) -> dict[str, str]:
    """Addendum A4.

    Deliberately NOT `dict(os.environ); env.update(request.env)` —
    NamespaceBackend's own precedent (confirmed by reading it directly),
    carried here only as a documented, deliberate NON-choice: a
    container is a different trust boundary than a namespace on the
    same host, so full host-process-environment inheritance is not
    something to copy silently. Starts from an explicit minimal base
    (a bare PATH, if the caller doesn't override it), layers
    `request_env` on top, then — only when `proxy_url` is given (i.e.
    only in allowlist mode) — forces every case-variant of the HTTP(S)
    proxy variables to `proxy_url` AFTER `request_env` has already been
    applied. That ordering is the entire point: a request cannot smuggle
    its own HTTP_PROXY value past this and redirect egress around the
    enforced proxy (checklist A4's actual test).
    """
    env: dict[str, str] = (
        dict(base_env)
        if base_env is not None
        else {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
    )
    env.update(request_env)
    if proxy_url is not None:
        for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
            env[key] = proxy_url
    return env


def _build_create_args(
    *,
    container_name: str,
    request_id: str,
    image_digest: str,
    command: tuple[str, ...],
    env: dict[str, str],
    workspace_dir: str,
    read_only_paths: tuple[str, ...],
    memory_limit_mb: int,
    max_pids: int,
    network_mode: str = "none",
) -> list[str]:
    """`docker create` argv. Addendum A6 / D2 / D3 / D4 — and A5's
    decision is structural here, not a comment: `SandboxPolicy.
    allowed_imports` is not a parameter of this function at all, so it
    is physically impossible for it to influence the generated args
    (checklist A5's chosen option: preserve NamespaceBackend's existing
    non-enforcement, unchanged, rather than inventing Docker-only
    filtering that would just look like enforcement).

    A6 — never present, on principle, not by omission: `--privileged`,
    `--pid=host`, `--ipc=host`, `--uts=host`, `--network=host`,
    `--cap-add`, `--device`, any Docker/container-runtime socket mount.
    `network_mode` defaults to `"none"` — the caller must explicitly ask
    for anything else; `create()` only does so when `allowed_hosts` is
    set (see `_ensure_sandbox_network()`).
    D3 — image root filesystem stays read-only (`--read-only`); the
    workspace bind mount is the one explicit writable path.
    D2 — each `read_only_paths` entry becomes its own `:ro` bind at the
    same in-container path.
    D4 — `container_name` (backend-private, derived from a uuid4 by the
    caller) becomes both the Docker container name and an
    `ocbrain.sandbox=true` label, and the request's `request_id` becomes
    an `ocbrain.request_id` label, so an abandoned container is
    enumerable for cleanup by backend or by request without
    SandboxHandle needing a new field (D12).

    Construction-time only: this proves the ARGUMENT LIST never asks for
    any of the above. It does not prove Docker's daemon actually honors
    every one of them at runtime; that is asserted from `docker inspect`
    on a live container by test_a6_runtime_inspect_shows_no_privilege_or_
    host_sharing (reconciliation §18).
    """
    args = [
        "docker",
        "create",
        "--name",
        container_name,
        "--label",
        "ocbrain.sandbox=true",
        "--label",
        f"ocbrain.container_name={container_name}",
        "--label",
        f"ocbrain.request_id={request_id}",
        "--read-only",
        "--network",
        network_mode,
        "--memory",
        f"{memory_limit_mb}m",
        "--pids-limit",
        str(max_pids),
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{workspace_dir}:{_WORKSPACE_MOUNT}:rw",
        "-w",
        _WORKSPACE_MOUNT,
    ]
    for path in read_only_paths:
        args += ["-v", f"{path}:{path}:ro"]
    for key, value in env.items():
        args += ["-e", f"{key}={value}"]
    args.append(image_digest)
    args.extend(command)
    return args


def _sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _lsm_active() -> bool:
    """Addendum A9/C3 — host precondition, not a mitigation this file can
    implement itself.

    Direct `socket(AF_VSOCK, ...)` is blocked by Docker's own default
    seccomp profile. It is NOT the only way to ask the kernel for that
    socket: the legacy 32-bit `socketcall(2)` compat entry point
    (reachable from a 64-bit container via `int $0x80`) can still
    create one. This was reproduced and verified directly (real socket,
    confirmed via `/proc/self/fd` showing `socket:[inode]`, not a
    plausible-looking return value) — see reconciliation doc §12/§13.

    A custom seccomp profile removing "socketcall" from the allow-list
    was tried here and does NOT close this: the profile genuinely loads
    and enforces (confirmed by using the identical mechanism to block
    an ordinary 64-bit syscall, `mkdir`, successfully) — it just does
    not reach the IA32-compat path for this syscall specifically on
    this host, for reasons not fully isolated (see §13's account of
    what was and wasn't ruled out; it is not simply a missing
    `architectures` declaration -- that was tried too). Root cause
    aside, the empirical result is unambiguous: seccomp alone, via
    Docker's `--security-opt seccomp=`, is not a reliable mitigation
    for this specific bypass on this host, and this file does not ship
    one that only *looks* like it works.

    Upstream Docker's own fix for the equivalent AF_ALG case (and,
    later, this exact AF_VSOCK case — moby/moby#53551, Engine 29.8.0)
    is an LSM policy rule (AppArmor's `deny network alg`-style rule, or
    an SELinux `vsock_socket` deny), specifically because an LSM hooks
    `security_socket_create()` — which fires regardless of which
    syscall ABI reached it — rather than filtering syscall arguments
    the way seccomp/BPF does. That is the only mitigation this
    investigation found to actually work, and it requires a real LSM.

    This function is the resulting precondition: any future capability
    claim whose safety depends on the AF_VSOCK bypass being closed
    (there are none yet — see B2) MUST check this first, not merely
    confirm the Docker version is new enough. It checks for AppArmor or
    SELinux being active on the *host* at all -- it does NOT confirm
    the specific deny rule is actually loaded in the profile a given
    container runs under, which would need a real Phase-0 session to
    verify against an actual deployment target. Treat a True return
    here as "an LSM is present, worth checking further," not as "this
    bypass is closed."
    """
    try:
        with open("/sys/module/apparmor/parameters/enabled") as f:
            if f.read().strip() == "Y":
                return True
    except OSError:
        pass
    try:
        import subprocess as _subprocess

        out = _subprocess.run(["getenforce"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip() in ("Enforcing", "Permissive"):
            return True
    except (OSError, FileNotFoundError):
        pass
    return False


_SANDBOX_NETWORK_NAME = "ocbrain-sandbox-net"
# How often run() re-sends `docker kill` once a cancel has been requested and the
# container has not died yet (it may not have started: reconciliation §19.2).
_CANCEL_ENFORCE_INTERVAL_SEC = 0.05


async def _ensure_sandbox_network() -> str:
    """Addendum C2 / base prompt Phase 5. Creates (idempotently) the
    shared, `--internal` Docker network every sandboxed container's
    `allowed_hosts` traffic goes through, and returns its gateway IP —
    a real address on the host once the network exists, reachable from
    inside a container attached to it without any route to the
    internet.

    `--internal` is what gives "no default route out": Docker adds no
    NAT/masquerade rule for an internal network, so a container on it
    can reach the gateway (the host's own bridge interface — a direct
    L2/L3 hop, not something NAT forwards onward) and nothing beyond
    it. `enable_icc=false` additionally blocks sandbox containers from
    reaching each other directly on the same bridge — the addendum's
    "another reachable container acting as a bridge" concern — since
    every sandbox created with `allowed_hosts` set lands on this one
    shared network.

    Verified directly (see reconciliation §14): a container on this
    network reaches the gateway; reaches nothing else (`ENETUNREACH`);
    cannot reach a sibling container on the same network (ICC).

    Idempotent: "already exists" from `docker network create` is
    treated as success, not an error — concurrent create() calls are
    expected to race here.
    """
    inspect = await asyncio.create_subprocess_exec(
        "docker",
        "network",
        "inspect",
        _SANDBOX_NETWORK_NAME,
        "--format",
        "{{(index .IPAM.Config 0).Gateway}}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await inspect.communicate()
    if inspect.returncode == 0:
        gateway = stdout.decode("utf-8", errors="replace").strip()
        if gateway:
            return gateway

    create = await asyncio.create_subprocess_exec(
        "docker",
        "network",
        "create",
        "--internal",
        "-o",
        "com.docker.network.bridge.enable_icc=false",
        _SANDBOX_NETWORK_NAME,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, create_stderr = await create.communicate()
    if create.returncode != 0 and b"already exists" not in create_stderr:
        raise DockerBackendError(
            f"could not create {_SANDBOX_NETWORK_NAME!r}: "
            f"{create_stderr.decode('utf-8', errors='replace').strip()}"
        )

    inspect2 = await asyncio.create_subprocess_exec(
        "docker",
        "network",
        "inspect",
        _SANDBOX_NETWORK_NAME,
        "--format",
        "{{(index .IPAM.Config 0).Gateway}}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout2, stderr2 = await inspect2.communicate()
    if inspect2.returncode != 0:
        raise DockerBackendError(
            f"created {_SANDBOX_NETWORK_NAME!r} but could not inspect it: "
            f"{stderr2.decode('utf-8', errors='replace').strip()}"
        )
    gateway = stdout2.decode("utf-8", errors="replace").strip()
    if not gateway:
        raise DockerBackendError(f"{_SANDBOX_NETWORK_NAME!r} has no gateway in its IPAM config")
    return gateway


# --------------------------------------------------------------------
# Backend-private bookkeeping (mirrors NamespaceBackend's _RunState —
# never one of the frozen public contracts; never leaves this file).
# --------------------------------------------------------------------


@dataclass
class _DockerRunState:
    container_id: str
    container_name: str
    workspace_dir: str
    state: SandboxState = SandboxState.PENDING
    cancel_requested: bool = False
    proxy: AllowlistProxy | None = None
    # D11: serializes the multi-await sequences that must not interleave
    # (today: destroy()'s remove -> confirm -> stop proxy -> forget).
    # PER HANDLE, never global: destroying one sandbox must not wait on
    # another (test_d11_destroying_one_sandbox_does_not_wait_for_another).
    # cancel() and run() deliberately do NOT take it: cancelling a run, or
    # destroying a running sandbox, has to be able to interrupt it.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # D7/D11 (§19.2): set by cancel() on a RUNNING handle. run() owns
    # enforcement from then on, so a cancel that lands while `docker start`
    # is still in flight cannot be escaped by the workload starting later.
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class DockerBackend(SandboxBackend):
    """Docker-daemon SandboxBackend. See the module docstring and
    `_CAPS`'s own comment before trusting any individual capability
    claim — seven of twelve are backed by real adversarial evidence,
    three were never earned, two (NETWORK_ALLOWLIST, NET_NAMESPACE)
    were withdrawn in §17, and A9's seccomp bypass is real and
    unmitigated (`_lsm_active()`)."""

    def __init__(self, image_ref: str | None = None) -> None:
        """`image_ref` is backend-private configuration (addendum A3),
        never read from SandboxRequest. Fails at construction time if no
        image is configured, rather than silently deferring the failure
        to the first create() call."""
        resolved_ref = image_ref or os.environ.get(_IMAGE_REF_ENV_VAR)
        if not resolved_ref:
            raise ValueError(
                "DockerBackend needs an image reference: pass image_ref= "
                f"or set {_IMAGE_REF_ENV_VAR}"
            )
        self._image_ref: str = resolved_ref
        self._resolved_digest: str | None = None
        self._handles: dict[str, _DockerRunState] = {}

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return _CAPS

    # -- A3: image resolution -------------------------------------

    async def _resolve_image_digest(self) -> str:
        """Addendum A3. Resolves the backend-private image reference to
        an immutable digest via `docker inspect`, once, and caches it —
        checklist A3's own test is "two create() calls resolve to the
        identical digest". Requires the image to already carry
        RepoDigests locally — verified this way in reconciliation §11:
        `docker import` (used there in place of a registry pull, none
        being reachable in that environment) populates RepoDigests for
        a locally-tagged image too, contrary to what this docstring
        originally assumed. `docker build`'s RepoDigests behavior
        remains untested — this constraint stays documented rather
        than silently resolved to something floating for that path.

        Verified: resolves correctly and caches (identical digest on a
        second call) against a real daemon — reconciliation §11.
        """
        if self._resolved_digest is not None:
            return self._resolved_digest
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            "--format",
            "{{index .RepoDigests 0}}",
            self._image_ref,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise DockerBackendError(
                f"could not resolve digest for {self._image_ref!r}: "
                f"{stderr.decode('utf-8', errors='replace').strip()}"
            )
        digest = stdout.decode("utf-8", errors="replace").strip()
        if not digest or digest == "<no value>":
            raise DockerBackendError(
                f"{self._image_ref!r} has no local RepoDigests — pull it "
                "by digest before configuring it here rather than "
                "resolving a floating tag at sandbox-creation time"
            )
        self._resolved_digest = digest
        return digest

    # -- SandboxBackend interface -----------------------------------

    async def create(self, request: SandboxRequest) -> SandboxHandle:
        """Verified against a real daemon (reconciliation §§11, 14, 16, 17):
        the full create()/run()/inspect()/destroy() lifecycle and
        failure-path cleanup (D10). A request with `allowed_hosts` is
        NOT admitted through AdmissionGate — NETWORK_ALLOWLIST is
        withdrawn (§17: one sandbox can use another's egress proxy) —
        so calling create() directly with `allowed_hosts` bypasses that
        gate and runs a network path whose per-sandbox enforcement is
        not demonstrated. See the module docstring for what's still
        open (A9)."""
        handle_id = f"docker-{uuid.uuid4().hex[:12]}"
        container_name = f"ocbrain-sandbox-{handle_id}"
        workspace_dir = request.policy.workspace_dir
        # Only a directory THIS call creates may be removed if create()
        # fails; a caller-owned, pre-existing workspace is never touched.
        workspace_created_here = not os.path.exists(workspace_dir)
        proxy: AllowlistProxy | None = None

        # D10 invariant: every resource acquired below is either cleaned
        # immediately (the except branch) or, on success, retained in a
        # handle that stays destroyable (`self._handles`). Never neither.
        try:
            os.makedirs(workspace_dir, exist_ok=True)

            image_digest = await self._resolve_image_digest()

            proxy_url: str | None = None
            network_mode = "none"
            if request.policy.allowed_hosts:
                # Addendum B3: the EXISTING AllowlistProxy, never a parallel
                # proxy or policy mechanism. NETWORK_ALLOWLIST is WITHDRAWN
                # from _CAPS (reconciliation §17), so AdmissionGate does not
                # admit requests that reach this branch; it stays reachable
                # only by calling create() directly. Every sandbox's proxy
                # binds the one shared gateway, so per-sandbox egress
                # enforcement is NOT demonstrated under concurrency (§17).
                gateway_ip = await _ensure_sandbox_network()
                proxy = AllowlistProxy(bind_ip=gateway_ip, allowed_hosts=request.policy.allowed_hosts)
                port = proxy.start()
                proxy_url = f"http://{gateway_ip}:{port}"
                network_mode = _SANDBOX_NETWORK_NAME

            env = _build_container_env(request.env, proxy_url=proxy_url)
            args = _build_create_args(
                container_name=container_name,
                request_id=request.request_id,
                image_digest=image_digest,
                command=request.command,
                env=env,
                workspace_dir=workspace_dir,
                read_only_paths=request.policy.read_only_paths,
                memory_limit_mb=request.policy.memory_limit_mb,
                max_pids=request.policy.max_pids,
                network_mode=network_mode,
            )

            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await proc.communicate()
            except BaseException:
                # Cancelled or failed mid-create: don't leave the docker
                # client running (it could still finish creating the
                # container after the cleanup below has looked for it).
                if proc.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        proc.kill()
                    await proc.wait()
                raise
            if proc.returncode != 0:
                raise DockerBackendError(
                    f"docker create failed: {stderr.decode('utf-8', errors='replace').strip()}"
                )
            container_id = stdout.decode("utf-8", errors="replace").strip()
        except BaseException:
            await self._abort_create(
                container_name=container_name,
                proxy=proxy,
                created_workspace=workspace_dir if workspace_created_here else None,
            )
            raise

        self._handles[handle_id] = _DockerRunState(
            container_id=container_id,
            container_name=container_name,
            workspace_dir=workspace_dir,
            state=SandboxState.PROVISIONING,
            proxy=proxy,
        )
        return SandboxHandle(
            handle_id=handle_id,
            request_id=request.request_id,
            backend_name="docker",
            state=SandboxState.PROVISIONING,
        )

    async def run(self, handle: SandboxHandle, request: SandboxRequest) -> SandboxResult:
        """Verified end to end against a real daemon — echo/exit-code,
        timeout, real HTTPS traffic through the network-isolation path,
        and the D11 concurrency races (reconciliation §§11, 14, 15)."""
        state = self._handles.get(handle.handle_id)
        if state is None:
            raise DockerBackendError(
                f"run() called for unknown handle {handle.handle_id!r} — create() first"
            )
        if state.state is not SandboxState.PROVISIONING:
            # D6: `docker start` on an exited container silently re-executes
            # the command, so a second run() must be an error, not a re-run.
            raise DockerBackendError(
                f"run() called on handle {handle.handle_id!r} in state "
                f"{state.state.name}; a handle can be run at most once"
            )
        state.state = SandboxState.RUNNING
        started = time.monotonic()

        enforcer = asyncio.ensure_future(self._enforce_cancellation(state))
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "start",
                "-a",
                state.container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            timed_out = False
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=request.policy.timeout_sec
                )
            except asyncio.TimeoutError:
                timed_out = True
                await self._kill_container(state.container_id)
                stdout, stderr = b"", b""
        finally:
            enforcer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await enforcer

        state.state = SandboxState.TERMINATED
        artifacts = await self._collect_artifacts(state)

        if timed_out:
            return SandboxResult(
                handle_id=handle.handle_id,
                exit_code=None,
                stdout="",
                stderr="sandbox timed out",
                termination_reason=TerminationReason.TIMEOUT,
                duration_sec=time.monotonic() - started,
                artifacts=artifacts,
            )

        exit_code = await self._inspect_exit_code(state.container_id)
        reason = await self._classify(state, exit_code)
        return SandboxResult(
            handle_id=handle.handle_id,
            exit_code=exit_code,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            termination_reason=reason,
            duration_sec=time.monotonic() - started,
            artifacts=artifacts,
        )

    async def cancel(self, handle: SandboxHandle) -> None:
        """Addendum D7. `docker kill` signals PID 1 in the container;
        Docker's own cgroup teardown reaches descendants. Verified
        directly against a real parent/child/grandchild process tree
        (reconciliation §11) — the checklist's specific concern (a
        descendant surviving because only the top-level PID was
        signaled) does not reproduce. Also exercised concurrently with
        run() and destroy() (D11, §15) — see this class's docstring
        before assuming anything beyond what those sections cover."""
        state = self._handles.get(handle.handle_id)
        if state is None:
            return
        if state.state is SandboxState.RUNNING:
            # D6: only a run that is actually running can be cancelled. A
            # flag set before run() would later mislabel a run that finished
            # normally as CANCELLED. The kill below stays unconditional and
            # harmless when nothing is running (D11 depends on it).
            state.cancel_requested = True
            # D7/D11 (§19.2): the kill below finds nothing to kill if the
            # container has not started yet. Recording the intent hands
            # enforcement to run(); cancel() itself never waits for start.
            state.cancel_event.set()
        await self._kill_container(state.container_id)

    async def destroy(self, handle: SandboxHandle) -> None:
        """Idempotent: an unknown handle, or a container that is already
        gone, is already-clean and is not an error (checklist D6/D10's
        double-destroy requirement).

        D11: the handle's record is KEPT until the container's removal is
        confirmed, so there is never a container without a record (the
        checklist's invariant) and inspect() keeps reporting the real
        state while the removal is in flight. Concurrent destroy() calls
        on one handle are serialized by its own lock (never a global one);
        a caller that waited re-checks that the record is still there and
        returns if the earlier destroy() already finished, so it neither
        repeats the removal nor returns before it is done. If the earlier
        attempt failed, the record is still there and the waiting caller
        makes -- and reports -- its own attempt.

        D10: "already gone" is CONFIRMED (a label query that succeeds and
        finds nothing), never inferred from `docker rm` having been
        called or having exited. If removal cannot be confirmed -- the
        daemon or CLI failed -- the record is retained and
        DockerBackendError is raised, so a later destroy() can finish the
        job. The host-side proxy listener is stopped either way (it
        depends on nothing in the daemon); the workspace is removed only
        once the container is confirmed gone. If this coroutine is
        cancelled part-way, the record is likewise never forgotten.

        Verified against a real daemon, including under deterministic
        latency injection (D11 tests, reconciliation §19) and injected CLI
        failure (D10 tests -- simulated at the CLI-call boundary, so
        evidence about this backend's cleanup logic, not about daemon
        behavior)."""
        state = self._handles.get(handle.handle_id)
        if state is None:
            return
        async with state.lock:
            if self._handles.get(handle.handle_id) is not state:
                return  # an earlier destroy() finished while this one waited
            gone = await self._remove_container(state.container_name)
            if state.proxy is not None:
                state.proxy.stop()
                state.proxy = None
            if not gone:
                raise DockerBackendError(
                    f"could not confirm removal of container {state.container_name!r}; "
                    "the handle is retained -- call destroy() again once docker is reachable"
                )
            self._handles.pop(handle.handle_id, None)  # only now: the container is confirmed gone
            shutil.rmtree(state.workspace_dir, ignore_errors=True)

    async def inspect(self, handle: SandboxHandle) -> SandboxState:
        """Read-only by construction (D8) — only ever reads the local
        bookkeeping dict, the same shape as NamespaceBackend's own
        inspect(). Never calls anything capable of starting, restarting,
        or mutating a container."""
        state = self._handles.get(handle.handle_id)
        return state.state if state else SandboxState.PENDING

    # -- private helpers ---------------------------------------------

    async def _enforce_cancellation(self, state: _DockerRunState) -> None:
        """D7/D11 (§19.2). cancel() may land while `docker start` is still
        in flight, when its single `docker kill` finds a container that is
        not running yet and does nothing. Once cancel intent exists, keep
        killing until run() has finished with the container (run() cancels
        this task in a `finally`), so the workload cannot escape
        cancellation by starting afterwards. Costs nothing until a cancel
        is requested; never holds the handle lock, so it cannot serialize
        anything (D11)."""
        await state.cancel_event.wait()
        while True:
            with contextlib.suppress(OSError):
                await self._kill_container(state.container_id)
            await asyncio.sleep(_CANCEL_ENFORCE_INTERVAL_SEC)

    async def _container_ids_for(self, container_name: str) -> list[str] | None:
        """Ids of every container, in ANY state, carrying this run's
        `ocbrain.container_name` label (D4). Returns None -- not [] --
        when that could not be determined, so "nothing there" and "could
        not look" are never confused (D10)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "ps",
                "-a",
                "-q",
                "--no-trunc",
                "--filter",
                f"label=ocbrain.container_name={container_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await proc.communicate()
        except OSError:
            return None
        if proc.returncode != 0:
            return None
        return stdout.decode("utf-8", errors="replace").split()

    async def _remove_container(self, container_name: str) -> bool:
        """Removes the container by its backend-private name (which is
        known before any docker call, so this works even when create()
        was interrupted before an id came back) and returns True iff its
        absence is CONFIRMED afterwards. `docker rm`'s own exit status is
        deliberately not what decides that."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except OSError:
            pass  # not a decision point: confirmation below settles it
        return await self._container_ids_for(container_name) == []

    async def _abort_create(
        self, *, container_name: str, proxy: AllowlistProxy | None, created_workspace: str | None
    ) -> None:
        """Best-effort unwind of a create() that failed part-way (D10).
        Residual limit, stated rather than hidden: if the daemon is
        unreachable during this unwind itself, a container that was
        already created cannot be confirmed removed and has no handle to
        retain it in -- it stays enumerable through the
        `ocbrain.sandbox=true` label, which is what D4 put it there for."""
        if proxy is not None:
            proxy.stop()
        await self._remove_container(container_name)
        if created_workspace is not None:
            shutil.rmtree(created_workspace, ignore_errors=True)

    async def _kill_container(self, container_id: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "kill",
            "--signal",
            "SIGKILL",
            container_id,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

    async def _docker_inspect_format(self, container_id: str, fmt: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            "--format",
            fmt,
            container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await proc.communicate()
        return stdout.decode("utf-8", errors="replace")

    async def _inspect_exit_code(self, container_id: str) -> int | None:
        out = (await self._docker_inspect_format(container_id, "{{.State.ExitCode}}")).strip()
        return int(out) if out.lstrip("-").isdigit() else None

    async def _inspect_oom_killed(self, container_id: str) -> bool:
        out = await self._docker_inspect_format(container_id, "{{.State.OOMKilled}}")
        return out.strip() == "true"

    async def _classify(self, state: _DockerRunState, exit_code: int | None) -> TerminationReason:
        """Addendum C1. Checks the container's own OOMKilled field FIRST,
        before looking at exit_code shape at all — exit code 137
        (SIGKILL) is produced by a genuine OOM kill AND by an ordinary
        cancel()/timeout kill, and the two are not distinguishable from
        the exit code alone (checklist's explicit forbidden shortcut:
        `if exit_code == 137: return RESOURCE_EXCEEDED`). Verified
        directly, independent of pytest (reconciliation §12): a real
        OOM gives OOMKilled=true/ExitCode=137; an ordinary SIGKILL gives
        OOMKilled=false/ExitCode=137 — same exit code, opposite flag,
        confirming exit code alone genuinely cannot carry this."""
        if await self._inspect_oom_killed(state.container_id):
            return TerminationReason.RESOURCE_EXCEEDED
        if state.cancel_requested:
            return TerminationReason.CANCELLED
        if exit_code is None:
            return TerminationReason.ERROR
        return TerminationReason.COMPLETED

    async def _collect_artifacts(self, state: _DockerRunState) -> ArtifactManifest:
        """Addendum D5. `docker cp` out to a host temp dir, then
        normalize/hash on the host side — never trusts a
        container-reported file list, and rejects (does not follow) any
        entry whose resolved real path escapes the copied root, so a
        symlink written inside the sandbox can't point the collector at
        an arbitrary host path. `docker cp`'s own behavior here is
        exercised in every real test run in reconciliation §§11-16.
        Adversarially targeted in §18 with absolute, relative, nested and
        directory symlinks and a FIFO: absolute/directory symlinks are
        rejected here by the containment check; a relative symlink that
        escapes makes `docker cp` itself refuse (`invalid symlink`), which
        yields an EMPTY manifest -- nothing escapes, but every artifact is
        lost silently (recorded in §18, not treated as a pass of anything
        beyond the no-escape invariant). Not attacked: extraction races,
        hard links, or workspace size."""
        tmp_root = tempfile.mkdtemp(prefix="ocbrain-docker-artifacts-")
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "cp",
                f"{state.container_id}:{_WORKSPACE_MOUNT}/.",
                tmp_root,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode != 0:
                return ArtifactManifest()

            files: list[tuple[str, str, int]] = []
            real_root = os.path.realpath(tmp_root)
            for root, _dirs, names in os.walk(tmp_root, followlinks=False):
                for name in names:
                    path = os.path.join(root, name)
                    real_path = os.path.realpath(path)
                    if os.path.commonpath([real_root, real_path]) != real_root:
                        continue  # symlink resolves outside the copied root — reject
                    if not os.path.isfile(real_path):
                        # A FIFO/socket/device the sandbox created: opening it to
                        # hash it blocks (a FIFO with no writer blocks forever),
                        # and a synchronous open() here would stall the whole
                        # event loop. Only regular files are artifacts.
                        continue
                    try:
                        rel = os.path.relpath(path, tmp_root)
                        files.append((rel, _sha256_of(path), os.path.getsize(path)))
                    except OSError:
                        continue
            return ArtifactManifest(files=tuple(files))
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)
