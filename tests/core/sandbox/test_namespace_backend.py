"""tests/core/sandbox/test_namespace_backend.py — Sandbox Fabric Phase 1,
NamespaceBackend adversarial tests.

Architecture Sources:
    core/sandbox/backends/namespace_backend.py
    docs/research/sandbox-execution-fabric/deep-research-report.md §12
        (adversarial test bench) and the kickoff-prompt success criteria
        (§15, "Critères de réussite")

Coverage (each maps directly to a §15 success criterion):
    - echo Hello runs and returns output
    - an illegal path (/root, which does not exist inside the jail) fails
      cleanly, never surfaces host content
    - an absolute symlink created before chroot, pointing at a real host
      file, resolves INSIDE the jail after chroot, not to the host file
    - a relative path-traversal attempt is contained the same way
    - network egress is denied by default (no allowed_hosts configured)
    - a memory-limit violation is killed and reported as RESOURCE_EXCEEDED
    - a fork bomb is blocked by the pids cgroup once max_pids is hit
    - a timeout terminates a long-running command well before it would
      finish on its own
    - cancel() kills every descendant process, not just the top-level one
      (this is the specific failure mode found empirically while building
      this: killing only the tracked PID can orphan the process `unshare
      --fork` re-execs into, once it's inside its own PID namespace)
    - produced files are collected as artifacts with a real sha256, and
      the read-only base-rootfs bind mounts are not mistaken for artifacts

Skipped entirely (rather than failing) on a host without unshare + a
writable cgroup v1 memory controller -- see _namespaces_available().
"""
import asyncio
import hashlib
import os
import subprocess
import sys
import time

import pytest

from core.sandbox.backends.namespace_backend import NamespaceBackend
from core.sandbox.contracts import SandboxPolicy, SandboxRequest, TerminationReason


def _namespaces_available() -> bool:
    try:
        r = subprocess.run(
            ["unshare", "--user", "--map-root-user", "--net", "--fork", "--", "true"],
            capture_output=True,
            timeout=5,
        )
        return (
            r.returncode == 0
            and os.path.isdir("/sys/fs/cgroup/memory")
            and os.access("/sys/fs/cgroup/memory", os.W_OK)
        )
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _namespaces_available(),
    reason="requires unshare + a writable cgroup v1 memory controller",
)


@pytest.fixture
def backend():
    return NamespaceBackend()


@pytest.fixture
def workspace(tmp_path):
    d = tmp_path / "ws"
    d.mkdir()
    return str(d)


@pytest.mark.asyncio
async def test_echo_hello_runs_and_returns_output(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10)
    request = SandboxRequest(command=("echo", "Hello"), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.succeeded, f"stderr={result.stderr!r}"
        assert result.stdout.strip() == "Hello"
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_illegal_path_access_fails_cleanly(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10)
    request = SandboxRequest(command=("ls", "/root"), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.exit_code != 0
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_symlink_escape_is_contained(backend, workspace):
    os.symlink("/etc/passwd", os.path.join(workspace, "evil_link"))
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10)
    request = SandboxRequest(command=("cat", "/evil_link"), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert "root:" not in result.stdout, "host /etc/passwd leaked through a symlink"
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_path_traversal_is_contained(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10)
    request = SandboxRequest(
        command=("cat", "../../../../../../../../etc/passwd"), policy=policy
    )
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert "root:" not in result.stdout, "path traversal escaped the chroot"
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_network_egress_denied_by_default(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10)
    code = (
        "import socket,sys\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.settimeout(3)\n"
        "r = s.connect_ex(('8.8.8.8', 53))\n"
        "sys.exit(0 if r != 0 else 1)\n"
    )
    request = SandboxRequest(command=(sys.executable, "-c", code), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.exit_code == 0, (
            f"connect_ex succeeded -- network was NOT blocked. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_memory_limit_kills_oversized_allocation(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=15, memory_limit_mb=20)
    code = "x = bytearray(200*1024*1024)\nprint('ALLOCATED_200MB')\n"
    request = SandboxRequest(command=(sys.executable, "-c", code), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert "ALLOCATED_200MB" not in result.stdout
        assert result.termination_reason == TerminationReason.RESOURCE_EXCEEDED, (
            f"exit_code={result.exit_code} stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_pids_limit_blocks_fork_bomb(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=15, max_pids=8)
    code = (
        "import os, time\n"
        "children = []\n"
        "try:\n"
        "    for _ in range(200):\n"
        "        pid = os.fork()\n"
        "        if pid == 0:\n"
        "            time.sleep(3)\n"
        "            os._exit(0)\n"
        "        children.append(pid)\n"
        "    print('FORKED_ALL_200')\n"
        "except OSError as e:\n"
        "    print('FORK_BLOCKED_AT', len(children), e.errno)\n"
    )
    request = SandboxRequest(command=(sys.executable, "-c", code), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert "FORKED_ALL_200" not in result.stdout, "pids.max did not stop the fork bomb"
        assert "FORK_BLOCKED_AT" in result.stdout, (
            f"expected a caught OSError before 200 forks; stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_timeout_terminates_long_running_command(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=1.5)
    request = SandboxRequest(command=("sleep", "30"), policy=policy)
    handle = await backend.create(request)
    try:
        started = time.monotonic()
        result = await backend.run(handle, request)
        elapsed = time.monotonic() - started
        assert result.termination_reason == TerminationReason.TIMEOUT
        assert elapsed < 10, "timeout enforcement took far longer than the configured limit"
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_cancel_kills_all_descendant_processes(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=60)
    request = SandboxRequest(command=("sleep", "50"), policy=policy)
    handle = await backend.create(request)

    run_task = asyncio.create_task(backend.run(handle, request))
    await asyncio.sleep(1.0)  # let the subprocess actually reach the sleep

    await backend.cancel(handle)
    result = await asyncio.wait_for(run_task, timeout=10)
    assert result.termination_reason in (
        TerminationReason.TIMEOUT,
        TerminationReason.ERROR,
        TerminationReason.CANCELLED,
    )

    leftover = subprocess.run(
        ["pgrep", "-f", "sleep 50"], capture_output=True, text=True
    ).stdout.split()
    assert leftover == [], f"orphaned process(es) survived cancel(): {leftover}"

    await backend.destroy(handle)


@pytest.mark.asyncio
async def test_artifacts_are_collected_with_real_hashes(backend, workspace):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10)
    content = "hello artifact"
    code = f"open('output.txt', 'w').write({content!r})\n"
    request = SandboxRequest(command=(sys.executable, "-c", code), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.succeeded, f"stderr={result.stderr!r}"

        names = [f[0] for f in result.artifacts.files]
        assert "output.txt" in names
        entry = next(f for f in result.artifacts.files if f[0] == "output.txt")
        _, sha256_hex, size = entry
        assert size == len(content)
        assert sha256_hex == hashlib.sha256(content.encode()).hexdigest()

        # the read-only base rootfs bind points must not appear as "artifacts"
        assert not any(n.startswith(("bin/", "lib/", "usr/")) for n in names)
    finally:
        await backend.destroy(handle)
