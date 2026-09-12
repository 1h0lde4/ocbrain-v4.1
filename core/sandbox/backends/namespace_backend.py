"""core/sandbox/backends/namespace_backend.py — rootless namespace/cgroup
sandbox backend (Phase 1, the "runc rootless" option from the source
report §13 point 4: "Choisir mode (runc rootless ou docker run)").

Why this backend and not Docker: `docker`, `runc`, and `podman` were all
verified absent (`which docker runc podman` -> nothing) in the environment
this was built and tested in. What WAS empirically verified present and
working here: Linux user/mount/pid/net namespaces via `unshare`, cgroup v1
memory+pids controllers under /sys/fs/cgroup (writable), and
PR_SET_NO_NEW_PRIVS via prctl. That is exactly the primitive set `runc`
itself is built on -- this implements that named option directly, rather
than writing a Docker-specific backend that could not be executed or
verified in this environment (PI's own "empirical verification over
document trust" -- see docs/architecture/
sandbox-execution-fabric-existing-code-reconciliation.md).

A DockerBackend implementing this same SandboxBackend interface (using
`docker run` against a real daemon) is a natural, additive follow-up on a
host that actually has Docker -- nothing here should need to change for
that to slot in; AdmissionGate and the contracts are backend-agnostic.

Isolation model, each point independently verified against this exact
environment before being relied on (see the reconciliation for the
narrower claims this superseded):
    - `unshare --user --map-root-user --mount --pid --fork --net`: a fresh
      net namespace with no further configuration has ONLY loopback -- no
      route out at all (verified: a raw TCP connect attempt from inside
      returns ENETUNREACH). That satisfies PI §14.1's network-deny-by-
      default requirement for free, rather than via an explicit firewall
      rule that could be misconfigured.
    - cgroup v1 memory + pids controllers, one pair of cgroups per handle.
      Joined via `preexec_fn` in the OUTER (not-yet-namespaced) process,
      deliberately BEFORE `unshare` is even exec'd -- cgroup membership is
      inherited across fork()/exec() by default in v1, which sidesteps any
      ambiguity about which PID a `cgroup.procs` write refers to once a
      *new* PID namespace exists (writing a namespace-relative PID like `1`
      into a cgroup created outside that namespace is not something to
      rely on without re-deriving kernel semantics from scratch).
    - PR_SET_NO_NEW_PRIVS is set inside _ns_init.py, before exec, so a
      setuid binary inside the jail cannot regain privileges.
    - Cancellation kills the whole OS process GROUP (`start_new_session`
      + `os.killpg`), not just the top-level `unshare` process -- verified
      empirically that killing only the tracked PID can leave the
      namespaced descendant (which `unshare --fork` re-execs into) as an
      orphan with no external killer once it's inside its own PID
      namespace.

What this does NOT provide yet (tracked, not silently assumed away):
    - seccomp-bpf syscall filtering (nsjail/bubblewrap-style). no_new_privs
      is set but a syscall allowlist is not -- report §12's adversarial
      bench should be re-run once that lands.
    - Non-empty SandboxPolicy.allowed_hosts. AdmissionGate rejects any
      request that names one rather than silently running with full
      network access.
"""
import asyncio
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field

from core.sandbox.backend import SandboxBackend
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

_NS_INIT = os.path.join(os.path.dirname(__file__), "_ns_init.py")
_CGROUP_MEM_ROOT = "/sys/fs/cgroup/memory"
_CGROUP_PIDS_ROOT = "/sys/fs/cgroup/pids"
# Base rootfs bind-mounted read-only into every sandbox so ordinary
# interpreters/binaries resolve inside the chroot. Also the set of
# top-level names artifact collection skips -- see _collect_artifacts.
_BASE_ROOTFS_NAMES = frozenset({"bin", "lib", "lib64", "usr"})

_CAPS = RuntimeCapabilities(
    backend_name="namespace",
    supported=frozenset(
        {
            SandboxCapability.USER_NAMESPACE,
            SandboxCapability.MOUNT_NAMESPACE,
            SandboxCapability.PID_NAMESPACE,
            SandboxCapability.NET_NAMESPACE,
            SandboxCapability.CGROUP_MEMORY,
            SandboxCapability.CGROUP_PIDS,
            SandboxCapability.NO_NEW_PRIVS,
            SandboxCapability.FILESYSTEM_JAIL,
            SandboxCapability.NETWORK_DENY_DEFAULT,
        }
    ),
)


@dataclass
class _RunState:
    """Mutable, backend-internal bookkeeping for one handle. Deliberately
    NOT one of the frozen public contracts -- this never leaves the
    backend."""

    mem_cgroup: str
    pids_cgroup: str
    workspace_dir: str
    process: subprocess.Popen | None = None
    pgid: int | None = None
    state: SandboxState = SandboxState.PENDING
    cancel_requested: bool = False


def _write(path: str, value: str) -> None:
    with open(path, "w") as f:
        f.write(value)


def _read(path: str, default: str = "0") -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class NamespaceBackend(SandboxBackend):
    def __init__(
        self,
        cgroup_mem_root: str = _CGROUP_MEM_ROOT,
        cgroup_pids_root: str = _CGROUP_PIDS_ROOT,
    ) -> None:
        self._cgroup_mem_root = cgroup_mem_root
        self._cgroup_pids_root = cgroup_pids_root
        self._handles: dict[str, _RunState] = {}

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return _CAPS

    async def create(self, request: SandboxRequest) -> SandboxHandle:
        handle_id = f"ns-{uuid.uuid4().hex[:12]}"
        os.makedirs(request.policy.workspace_dir, exist_ok=True)

        mem_cgroup = os.path.join(self._cgroup_mem_root, f"ocbrain-sandbox-{handle_id}")
        pids_cgroup = os.path.join(self._cgroup_pids_root, f"ocbrain-sandbox-{handle_id}")
        os.makedirs(mem_cgroup, exist_ok=True)
        os.makedirs(pids_cgroup, exist_ok=True)
        _write(
            os.path.join(mem_cgroup, "memory.limit_in_bytes"),
            str(request.policy.memory_limit_mb * 1024 * 1024),
        )
        _write(os.path.join(mem_cgroup, "memory.swappiness"), "0")
        _write(os.path.join(pids_cgroup, "pids.max"), str(request.policy.max_pids))

        self._handles[handle_id] = _RunState(
            mem_cgroup=mem_cgroup,
            pids_cgroup=pids_cgroup,
            workspace_dir=request.policy.workspace_dir,
            state=SandboxState.PROVISIONING,
        )
        return SandboxHandle(
            handle_id=handle_id,
            request_id=request.request_id,
            backend_name="namespace",
            state=SandboxState.PROVISIONING,
        )

    async def run(self, handle: SandboxHandle, request: SandboxRequest) -> SandboxResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_sync, handle, request)

    def _run_sync(self, handle: SandboxHandle, request: SandboxRequest) -> SandboxResult:
        state = self._handles[handle.handle_id]
        state.state = SandboxState.RUNNING

        argv = [
            "unshare",
            "--user",
            "--map-root-user",
            "--mount",
            "--pid",
            "--fork",
            "--net",
            "--",
            sys.executable,
            _NS_INIT,
            state.workspace_dir,
            *request.policy.read_only_paths,
            "--",
            *request.command,
        ]

        def _join_cgroups() -> None:
            # Runs in the child, in the ORIGINAL namespaces, before exec
            # into `unshare` -- see module docstring for why this ordering
            # matters.
            pid = str(os.getpid())
            _write(os.path.join(state.mem_cgroup, "cgroup.procs"), pid)
            _write(os.path.join(state.pids_cgroup, "cgroup.procs"), pid)

        started = time.monotonic()
        exit_code: int | None = None
        stdout_b = b""
        stderr_b = b""
        reason = TerminationReason.ERROR

        try:
            proc = subprocess.Popen(
                argv,
                preexec_fn=_join_cgroups,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=request.env or None,
            )
            state.process = proc
            state.pgid = os.getpgid(proc.pid)

            try:
                stdout_b, stderr_b = proc.communicate(timeout=request.policy.timeout_sec)
                exit_code = proc.returncode
                reason = self._classify(exit_code, state)
            except subprocess.TimeoutExpired:
                self._killpg(state.pgid)
                try:
                    stdout_b, stderr_b = proc.communicate(timeout=3)
                except Exception:
                    pass
                reason = TerminationReason.TIMEOUT
                exit_code = None
        finally:
            state.state = SandboxState.TERMINATED

        duration = time.monotonic() - started
        artifacts = self._collect_artifacts(state.workspace_dir)

        return SandboxResult(
            handle_id=handle.handle_id,
            exit_code=exit_code,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
            termination_reason=reason,
            duration_sec=duration,
            artifacts=artifacts,
        )

    def _hit_memory_limit(self, state: "_RunState") -> bool:
        failcnt = _read(os.path.join(state.mem_cgroup, "memory.failcnt"))
        return failcnt.isdigit() and int(failcnt) > 0

    def _classify(self, exit_code: int | None, state: "_RunState") -> TerminationReason:
        """Check the cgroup's own failcnt FIRST, before looking at the exit
        code shape at all. Empirically discovered while testing this: when
        the memory limit is hit, the OOM killer can strike ANY process in
        the chain sharing this cgroup (unshare itself, not just the final
        payload -- unshare, its --fork child, and the payload all inherit
        the same cgroup membership across fork()/exec()). That sometimes
        surfaces as unshare exiting with an ordinary POSITIVE status
        (it caught its child dying and reported an error itself) rather
        than the directly-tracked process being signal-killed. Trusting
        the kernel's own memory.failcnt counter is what's actually
        reliable here -- inferring OOM purely from exit-code sign was the
        bug, not a mistaken test."""
        if self._hit_memory_limit(state):
            return TerminationReason.RESOURCE_EXCEEDED
        if exit_code is None:
            return TerminationReason.ERROR
        if exit_code < 0:
            return TerminationReason.CANCELLED if state.cancel_requested else TerminationReason.ERROR
        return TerminationReason.COMPLETED

    def _killpg(self, pgid: int | None) -> None:
        if pgid is None:
            return
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _collect_artifacts(self, workspace_dir: str) -> ArtifactManifest:
        files: list[tuple[str, str, int]] = []
        if not os.path.isdir(workspace_dir):
            return ArtifactManifest()
        for entry in sorted(os.listdir(workspace_dir)):
            if entry in _BASE_ROOTFS_NAMES:
                # These are bind-mount points for the read-only base
                # rootfs (see _ns_init.py). Their content is namespace-
                # local and disappears with the mount namespace, but we
                # skip them explicitly rather than relying on that
                # implicitly (PI LAW 4 -- Determinism Over Magic).
                continue
            full = os.path.join(workspace_dir, entry)
            for root, _dirs, names in os.walk(full) if os.path.isdir(full) else [(workspace_dir, [], [entry])]:
                for name in names:
                    path = os.path.join(root, name)
                    try:
                        rel = os.path.relpath(path, workspace_dir)
                        files.append((rel, _sha256_of(path), os.path.getsize(path)))
                    except OSError:
                        continue
        return ArtifactManifest(files=tuple(files))

    async def cancel(self, handle: SandboxHandle) -> None:
        state = self._handles.get(handle.handle_id)
        if state is None:
            return
        state.cancel_requested = True
        self._killpg(state.pgid)

    async def destroy(self, handle: SandboxHandle) -> None:
        state = self._handles.pop(handle.handle_id, None)
        if state is None:
            return
        self._killpg(state.pgid)
        for cgroup_dir in (state.mem_cgroup, state.pids_cgroup):
            for _attempt in range(5):
                try:
                    os.rmdir(cgroup_dir)
                    break
                except OSError:
                    time.sleep(0.05)  # cgroup may not be empty yet
        shutil.rmtree(state.workspace_dir, ignore_errors=True)

    async def inspect(self, handle: SandboxHandle) -> SandboxState:
        state = self._handles.get(handle.handle_id)
        return state.state if state else SandboxState.PENDING
