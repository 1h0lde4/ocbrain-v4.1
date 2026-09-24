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

STATUS — written with no Docker daemon reachable (2026-09-21 session).
Mirrors NamespaceBackend's own honesty about its build environment: that
module's docstring records that `docker`/`runc`/`podman` were all
verified absent when it was written. The same is true here, still.
Concretely, in the container this file was authored in: no `docker`
binary, no daemon socket, no route to any image registry (registry
domains are outside this environment's network egress allowlist).

What that means for this file, precisely (do not read past this list
without it — it governs every method below):
  - `capabilities` below is `frozenset()` and MUST STAY that way until
    Phases 0-5 of the base prompt actually pass on a real host with a
    real daemon (addendum B2). AdmissionGate.check_admission() already
    makes this self-enforcing: with an empty capability set, EVERY
    request is rejected before any backend method below is ever
    reached (it requires FILESYSTEM_JAIL/CGROUP_MEMORY/CGROUP_PIDS
    unconditionally — see core/sandbox/admission.py). Nothing in this
    file adds a redundant guard on top of that; AdmissionGate is
    already the single, existing gate (addendum B3).
  - create()/run()/cancel()/destroy()/inspect() below are written to
    the letter of the base prompt + addendum + checklist, but NONE of
    them has ever been executed against a live daemon. "Implemented"
    is not "verified" anywhere in this file — see reconciliation §10
    for the honest, itemized accounting of what that does and doesn't
    cover.
  - Two small pure functions, `_build_container_env` (A4) and
    `_build_create_args` (A6/D2/D3/D4/D12 — plus proves A5's decision
    structurally), need no Docker daemon at all and ARE exercised by
    real, passing tests in tests/core/sandbox/test_docker_backend.py.
    Everything else in that test file that needs a live container is
    individually skipped in this environment — see that file's own
    docstring for why the skip is per-test, not whole-file.

Scope discipline (addendum B4 / base prompt Definition of Done): this
file, its own small private helpers, tests/core/sandbox/
test_docker_backend.py, and additive-only SandboxCapability entries in
contracts.py (none added by this session — see B2 above) are the whole
authorized surface. SandboxBackend, NamespaceBackend, _ns_init.py,
_seccomp.py, and _net_proxy.py are read from (imported, in
_net_proxy's case — addendum B3) but never modified.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass

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

# Addendum B2: starts empty, stays empty until Phase 0-5 gates pass on a
# real host. See module docstring — this is not a placeholder to fill in
# casually; each value requires its own passing gate, individually, per
# the checklist.
_CAPS = RuntimeCapabilities(backend_name="docker", supported=frozenset())


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
    for anything else, and today (capabilities empty) nothing calls this
    with anything else.
    D3 — image root filesystem stays read-only (`--read-only`); the
    workspace bind mount is the one explicit writable path.
    D2 — each `read_only_paths` entry becomes its own `:ro` bind at the
    same in-container path.
    D4 — `container_name` (backend-private, derived from a uuid4 by the
    caller) becomes both the Docker container name and an
    `ocbrain.sandbox=true` label, so an abandoned container is
    enumerable for cleanup without SandboxHandle needing a new field
    (D12).

    Construction-time only: this proves the ARGUMENT LIST never asks for
    any of the above. It does not prove Docker's daemon actually honors
    every one of them at runtime — that needs `docker inspect` on a live
    container (checklist A6's own required test), which this function
    cannot perform and this session could not run.
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


class DockerBackend(SandboxBackend):
    """Docker-daemon SandboxBackend. See module docstring before editing
    or trusting anything below it — capabilities is empty and every
    method is unverified against a live daemon."""

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
        RepoDigests locally (i.e. pulled from a registry, not only
        locally built) — a real constraint this backend imposes
        deliberately rather than silently resolving to something
        floating; documented here since it has never been exercised
        against a real registry in this session.

        UNVERIFIED beyond argument construction: never run against a
        real daemon.
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
        """UNVERIFIED. See module docstring. Also: AdmissionGate rejects
        every request before this is ever reached today (capabilities is
        empty) — this method exists to satisfy the interface and encode
        the addendum's requirements, not because it is reachable yet."""
        handle_id = f"docker-{uuid.uuid4().hex[:12]}"
        container_name = f"ocbrain-sandbox-{handle_id}"
        os.makedirs(request.policy.workspace_dir, exist_ok=True)

        image_digest = await self._resolve_image_digest()

        proxy: AllowlistProxy | None = None
        proxy_url: str | None = None
        network_mode = "none"
        if request.policy.allowed_hosts:
            # Addendum B3: the EXISTING AllowlistProxy, never a parallel
            # proxy or policy mechanism. Wired for when NET_NAMESPACE +
            # NETWORK_ALLOWLIST are actually earned (A1) — AdmissionGate
            # rejects any request that would reach this branch today, so
            # it has never executed.
            proxy = AllowlistProxy(bind_ip="127.0.0.1", allowed_hosts=request.policy.allowed_hosts)
            port = proxy.start()
            proxy_url = f"http://127.0.0.1:{port}"
            # TODO(host-verify): "bridge" is a placeholder. Phase 5 /
            # C2 require the sandbox side to have NO route out except
            # the proxy peer — NamespaceBackend's no-default-route veth
            # pattern needs a genuine Docker-network equivalent
            # (addendum's own Phase 5 §1: "isolated Docker network with
            # no default route out"), not plain bridge mode. Left
            # explicit rather than silently shipped as if it were
            # already that isolated network.
            network_mode = "bridge"

        env = _build_container_env(request.env, proxy_url=proxy_url)
        args = _build_create_args(
            container_name=container_name,
            image_digest=image_digest,
            command=request.command,
            env=env,
            workspace_dir=request.policy.workspace_dir,
            read_only_paths=request.policy.read_only_paths,
            memory_limit_mb=request.policy.memory_limit_mb,
            max_pids=request.policy.max_pids,
            network_mode=network_mode,
        )

        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            if proxy is not None:
                proxy.stop()
            raise DockerBackendError(
                f"docker create failed: {stderr.decode('utf-8', errors='replace').strip()}"
            )
        container_id = stdout.decode("utf-8", errors="replace").strip()

        self._handles[handle_id] = _DockerRunState(
            container_id=container_id,
            container_name=container_name,
            workspace_dir=request.policy.workspace_dir,
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
        """UNVERIFIED. See module docstring."""
        state = self._handles.get(handle.handle_id)
        if state is None:
            raise DockerBackendError(
                f"run() called for unknown handle {handle.handle_id!r} — create() first"
            )
        state.state = SandboxState.RUNNING
        started = time.monotonic()

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
        """Addendum D7. UNVERIFIED against a real process tree — never
        run. `docker kill` signals PID 1 in the container; Docker's own
        cgroup teardown is relied on to reach descendants. This is
        exactly what the checklist warns NOT to trust without a direct
        parent/child/grandchild test against a live daemon — that test
        is written in tests/core/sandbox/test_docker_backend.py, marked
        needing a real daemon, and has never run."""
        state = self._handles.get(handle.handle_id)
        if state is None:
            return
        state.cancel_requested = True
        await self._kill_container(state.container_id)

    async def destroy(self, handle: SandboxHandle) -> None:
        """UNVERIFIED. Idempotent by construction: a missing handle or an
        already-gone container are both treated as already-clean
        (checklist D6/D10's double-destroy requirement), not errors."""
        state = self._handles.pop(handle.handle_id, None)
        if state is None:
            return
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "rm",
            "-f",
            state.container_id,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if state.proxy is not None:
            state.proxy.stop()
        shutil.rmtree(state.workspace_dir, ignore_errors=True)

    async def inspect(self, handle: SandboxHandle) -> SandboxState:
        """Read-only by construction (D8) — only ever reads the local
        bookkeeping dict, the same shape as NamespaceBackend's own
        inspect(). Never calls anything capable of starting, restarting,
        or mutating a container."""
        state = self._handles.get(handle.handle_id)
        return state.state if state else SandboxState.PENDING

    # -- private helpers ---------------------------------------------

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
        `if exit_code == 137: return RESOURCE_EXCEEDED`). UNVERIFIED:
        never exercised against a real OOM event or a real concurrent
        cancel() race."""
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
        an arbitrary host path. UNVERIFIED: `docker cp`'s own behavior
        here has never been exercised against a real daemon; this is
        this backend's best-effort defense, not a confirmed-safe
        result."""
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
                    try:
                        rel = os.path.relpath(path, tmp_root)
                        files.append((rel, _sha256_of(path), os.path.getsize(path)))
                    except OSError:
                        continue
            return ArtifactManifest(files=tuple(files))
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)
