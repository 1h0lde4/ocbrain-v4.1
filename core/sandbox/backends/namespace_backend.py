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

New dependency as of DEBT-023's closure: `iproute2` (the `ip` CLI) for
named-netns/veth management. Not present by default in the build
environment either -- installed via `apt-get install iproute2` (Ubuntu
archive, an already-allowed network egress target) before this was
written; a real deployment host needs it too. `iproute2` is close to
universal on modern Linux (Docker itself depends on it), so this is a
low-risk addition, but it is a genuinely new requirement, not an
assumption -- worth a line in whatever installs this project's system
packages.

A DockerBackend implementing this same SandboxBackend interface (using
`docker run` against a real daemon) is a natural, additive follow-up on a
host that actually has Docker -- nothing here should need to change for
that to slot in; AdmissionGate and the contracts are backend-agnostic.

Isolation model, each point independently verified against this exact
environment before being relied on (see the reconciliation for the
narrower claims this superseded):
    - `unshare --user --map-root-user --mount --pid --fork --net --uts`: a
      fresh net namespace with no further configuration has ONLY loopback
      -- no route out at all (verified: a raw TCP connect attempt from
      inside returns ENETUNREACH). That satisfies PI §14.1's network-deny-
      by-default requirement for free, rather than via an explicit
      firewall rule that could be misconfigured. `--uts` (added alongside
      seccomp below) isolates hostname/domainname changes from the host.
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
    - A default-ALLOW seccomp-bpf denylist (core/sandbox/backends/
      _seccomp.py, closing KNOWN_ISSUES.md DEBT-022) is loaded right
      before exec, blocking ptrace, mount/umount2, kernel-module and
      kexec syscalls, clock manipulation, keyring syscalls, bpf(),
      perf_event_open, userfaultfd, and nested unshare/setns, among
      others -- see that module for the full list and the rationale for
      denylist-over-allowlist in Phase 1. Ordering matters and was
      verified, not assumed: the setup phase's own bind-mounts need
      `mount()` and run before the filter loads, so the payload -- not
      the setup code -- is what actually gets blocked from mounting.
    - Cancellation kills the whole OS process GROUP (`start_new_session`
      + `os.killpg`), not just the top-level `unshare` process -- verified
      empirically that killing only the tracked PID can leave the
      namespaced descendant (which `unshare --fork` re-execs into) as an
      orphan with no external killer once it's inside its own PID
      namespace.
    - A non-empty SandboxPolicy.allowed_hosts (closing KNOWN_ISSUES.md
      DEBT-023) is honored via a named, pre-configured network namespace
      + veth pair + an allowlist-enforcing forward proxy (core/sandbox/
      backends/_net_proxy.py) on the host-side peer -- built and
      configured BEFORE the sandbox process ever starts, specifically to
      avoid any race between "namespace exists" and "namespace is
      configured" that reconfiguring an already-unshared --net namespace
      from outside would risk. The sandbox side gets no default route,
      so structurally -- not via a firewall rule -- it can reach nothing
      except that one proxy IP (verified: ENETUNREACH to everything
      else). This is HTTP(S)-only (HTTP CONNECT tunneling, matching how
      `pip` and most well-behaved clients already respect HTTP_PROXY/
      HTTPS_PROXY) -- not a general arbitrary-protocol host allowlist. A
      raw non-HTTP TCP/UDP connection to an allowed host is still
      blocked, since only the proxy port itself is reachable at all.

What this does NOT provide yet (tracked, not silently assumed away):
    - The seccomp denylist is a curated Phase 1 set (core/sandbox/
      backends/_seccomp.py's DENIED_SYSCALLS), not a claim of matching
      any specific reference profile exactly, and not a strict allowlist
      -- tightening further is a natural, tracked follow-up once there is
      real operational experience about what sandboxed workloads call.
    - Protocol-agnostic allowed_hosts enforcement (see above -- HTTP(S)
      via CONNECT only, by design, not yet a general allowlist).
"""
import asyncio
import hashlib
import itertools
import os
import shutil
import signal
import subprocess
import sys
import threading
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
            SandboxCapability.UTS_NAMESPACE,
            SandboxCapability.CGROUP_MEMORY,
            SandboxCapability.CGROUP_PIDS,
            SandboxCapability.NO_NEW_PRIVS,
            SandboxCapability.SECCOMP,
            SandboxCapability.FILESYSTEM_JAIL,
            SandboxCapability.NETWORK_DENY_DEFAULT,
            SandboxCapability.NETWORK_ALLOWLIST,
        }
    ),
)

_subnet_counter = itertools.count()
_subnet_lock = threading.Lock()


def _alloc_subnet() -> tuple[str, str]:
    """Allocate a distinct /30 within 10.200.0.0/16 for one sandbox's veth
    pair. A monotonic counter, not random -- collisions would be a
    genuinely confusing bug to chase (two sandboxes crosstalking their
    'isolated' networks), and a counter makes that structurally
    impossible up to ~16k concurrent allocations rather than merely
    unlikely."""
    with _subnet_lock:
        idx = next(_subnet_counter)
    base = (idx * 4) % 65536  # always a multiple of 4 -> never overflows a /30 into the next octet
    octet3, octet4 = (base // 256) % 256, base % 256
    return f"10.200.{octet3}.{octet4 + 1}", f"10.200.{octet3}.{octet4 + 2}"


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
    netns_name: str | None = None
    veth_host: str | None = None
    proxy: AllowlistProxy | None = None
    proxy_host_ip: str | None = None


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

        if request.policy.allowed_hosts:
            self._setup_allowlisted_network(handle_id, request.policy.allowed_hosts)

        return SandboxHandle(
            handle_id=handle_id,
            request_id=request.request_id,
            backend_name="namespace",
            state=SandboxState.PROVISIONING,
        )

    def _setup_allowlisted_network(self, handle_id: str, allowed_hosts: tuple[str, ...]) -> None:
        """Named netns + veth pair, fully configured BEFORE the sandbox
        process ever starts -- avoids any race between "namespace exists"
        and "namespace is configured" that setting up a veth into an
        already-unshared --net namespace would have. The sandbox side
        gets no default route, so it can reach ONLY the directly-
        connected host peer (verified empirically: no route = ENETUNREACH
        to anything else, no firewall rule needed for that part) --
        structural denial, not a rule that could be misconfigured. The
        proxy (core/sandbox/backends/_net_proxy.py) on that peer IP is
        the only thing the sandbox can reach, and it enforces
        allowed_hosts itself.
        """
        state = self._handles[handle_id]
        token = uuid.uuid4().hex[:6]
        netns_name = f"sbx-{token}"
        veth_host = f"vh{token}"
        veth_sbx = f"vs{token}"
        host_ip, sbx_ip = _alloc_subnet()

        subprocess.run(["ip", "netns", "add", netns_name], check=True)
        subprocess.run(
            ["ip", "link", "add", veth_host, "type", "veth", "peer", "name", veth_sbx], check=True
        )
        subprocess.run(["ip", "link", "set", veth_sbx, "netns", netns_name], check=True)
        subprocess.run(["ip", "addr", "add", f"{host_ip}/30", "dev", veth_host], check=True)
        subprocess.run(["ip", "link", "set", veth_host, "up"], check=True)
        subprocess.run(
            ["ip", "netns", "exec", netns_name, "ip", "addr", "add", f"{sbx_ip}/30", "dev", veth_sbx],
            check=True,
        )
        subprocess.run(
            ["ip", "netns", "exec", netns_name, "ip", "link", "set", veth_sbx, "up"], check=True
        )
        subprocess.run(
            ["ip", "netns", "exec", netns_name, "ip", "link", "set", "lo", "up"], check=True
        )

        proxy = AllowlistProxy(host_ip, allowed_hosts)
        proxy.start()

        state.netns_name = netns_name
        state.veth_host = veth_host
        state.proxy = proxy
        state.proxy_host_ip = host_ip

    async def run(self, handle: SandboxHandle, request: SandboxRequest) -> SandboxResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_sync, handle, request)

    def _run_sync(self, handle: SandboxHandle, request: SandboxRequest) -> SandboxResult:
        state = self._handles[handle.handle_id]
        state.state = SandboxState.RUNNING

        # Always start from a full copy of this process's own environment
        # (equivalent to env=None's inherit-everything, just explicit) so
        # PATH etc. survive -- _ns_init.py's own `mount` subprocess calls
        # need PATH lookup to work. request.env applies on top as
        # overrides, not a wholesale replacement; proxy vars (allowlist
        # mode only) are layered on top of that.
        env = dict(os.environ)
        env.update(request.env)

        if state.netns_name is not None:
            assert state.proxy is not None, "netns_name set implies _setup_allowlisted_network ran"
            proxy_url = f"http://{state.proxy_host_ip}:{state.proxy.port}"
            for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                env[var] = proxy_url
            argv = [
                "ip",
                "netns",
                "exec",
                state.netns_name,
                "unshare",
                "--user",
                "--map-root-user",
                "--mount",
                "--pid",
                "--fork",
                "--uts",
                "--",
                sys.executable,
                _NS_INIT,
                state.workspace_dir,
                *request.policy.read_only_paths,
                "--",
                *request.command,
            ]
        else:
            argv = [
                "unshare",
                "--user",
                "--map-root-user",
                "--mount",
                "--pid",
                "--fork",
                "--net",
                "--uts",
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
                env=env,
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
        if state.proxy is not None:
            state.proxy.stop()
        if state.veth_host is not None:
            # deletes both ends of the pair, on whichever side they
            # currently live (host side and the netns-moved peer)
            subprocess.run(["ip", "link", "delete", state.veth_host], capture_output=True)
        if state.netns_name is not None:
            subprocess.run(["ip", "netns", "delete", state.netns_name], capture_output=True)
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
