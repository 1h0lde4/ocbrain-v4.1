"""tests/core/sandbox/test_docker_backend.py — Sandbox Fabric, DockerBackend
(DEBT-021).

Architecture Sources:
    core/sandbox/backends/docker_backend.py
    sandbox-fabric-dockerbackend-implementation-prompt.md (`d53b164`)
    sandbox-fabric-dockerbackend-implementation-prompt-addendum.md
    sandbox-fabric-dockerbackend-implementation-checklist.md

Two tiers here, gated differently on purpose:

  - Pure-logic tests (env construction, create-arg construction, the A5
    non-enforcement invariant, capabilities/admission) need no Docker
    daemon at all and run unconditionally below. These ARE real,
    executable verification, in exactly the kind of environment this
    file was written in — not aspirational.

  - Everything that needs an actual container (create/run/cancel/
    destroy/inspect against a live daemon) is individually decorated
    with `@_needs_docker` rather than gated by a single whole-file
    `pytestmark`. That is a deliberate, disclosed deviation from the
    base prompt's Phase 6 wording ("a `_docker_available()` guard...
    skip the whole file") — made so the pure-logic coverage above isn't
    needlessly skipped alongside tests that genuinely need a daemon.
    See the reconciliation doc's addendum for the full accounting.

    Every daemon-gated test below is currently SKIPPED, not passing, in
    every environment this has been run in so far (none has had a
    reachable Docker daemon). They are written to mirror
    NamespaceBackend's own adversarial suite where the mechanism
    allows, per Phase 6 — a representative subset, not yet the full
    one-for-one 28-item parity the checklist ultimately wants. That is
    explicitly left to the actual host-verification session, not
    attempted blind here (checklist B1: capabilities/passes are
    reported honestly, not assumed).
"""
import os
import shutil
import tempfile
import subprocess

import pytest

from core.sandbox.admission import check_admission
from core.sandbox.backends.docker_backend import (
    DockerBackend,
    _build_container_env,
    _build_create_args,
)
from core.sandbox.contracts import SandboxPolicy, SandboxRequest, TerminationReason


def _docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


_needs_docker = pytest.mark.skipif(
    not _docker_available(), reason="requires a reachable Docker daemon"
)

_COMMON_ARGS = dict(
    container_name="t",
    image_digest="example/image@sha256:" + "a" * 64,
    command=("true",),
    env={},
    workspace_dir="/tmp/ws",
    read_only_paths=(),
    memory_limit_mb=64,
    max_pids=32,
)


# ======================================================================
# Pure-logic tests — no Docker daemon required. Run for real, right now.
# ======================================================================


def test_capabilities_start_empty():
    # Addendum B2 — no gate has passed in an environment with no daemon
    # at all, so this is frozenset(), not NamespaceBackend's full set.
    backend = DockerBackend(image_ref="example/image:tag")
    assert backend.capabilities.supported == frozenset()


def test_empty_capabilities_means_admission_gate_rejects_everything():
    # Direct, worth-asserting-explicitly consequence of B2: DockerBackend
    # is categorically inadmissible for any real request today, by the
    # EXISTING AdmissionGate (addendum B3) — not a guard this file adds.
    backend = DockerBackend(image_ref="example/image:tag")
    policy = SandboxPolicy(workspace_dir="/tmp/whatever")
    request = SandboxRequest(command=("echo", "hi"), policy=policy)
    decision = check_admission(request, backend.capabilities)
    assert decision.allowed is False


def test_constructor_requires_an_image_reference():
    # A3 — backend-private config, fails at construction, not silently
    # deferred to the first create() call.
    prior = os.environ.pop("OCBRAIN_SANDBOX_DOCKER_IMAGE", None)
    try:
        with pytest.raises(ValueError):
            DockerBackend()
    finally:
        if prior is not None:
            os.environ["OCBRAIN_SANDBOX_DOCKER_IMAGE"] = prior


def test_sandbox_request_has_no_image_field():
    # A3's other half: callers cannot inject an image via the public
    # request type at all — there is no field to set.
    assert not hasattr(SandboxRequest, "image")
    policy = SandboxPolicy(workspace_dir="/tmp/whatever")
    request = SandboxRequest(command=("true",), policy=policy)
    assert not hasattr(request, "image")


def test_build_container_env_is_not_full_host_inheritance():
    # A4 — explicit minimal base + request.env, deliberately NOT
    # dict(os.environ) the way NamespaceBackend's own precedent is.
    env = _build_container_env({"FOO": "bar"}, base_env={"PATH": "/bin"})
    assert env == {"PATH": "/bin", "FOO": "bar"}


def test_build_container_env_forces_proxy_after_request_env_in_allowlist_mode():
    # A4's actual invariant: request.env's own HTTP_PROXY must not win
    # once a proxy is enforced.
    env = _build_container_env(
        {"HTTP_PROXY": "http://attacker.example:1"},
        base_env={},
        proxy_url="http://127.0.0.1:9999",
    )
    assert env["HTTP_PROXY"] == "http://127.0.0.1:9999"
    assert env["http_proxy"] == "http://127.0.0.1:9999"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:9999"
    assert env["https_proxy"] == "http://127.0.0.1:9999"


def test_build_container_env_no_proxy_forcing_outside_allowlist_mode():
    env = _build_container_env(
        {"HTTP_PROXY": "http://whatever.example:1"}, base_env={}, proxy_url=None
    )
    assert env["HTTP_PROXY"] == "http://whatever.example:1"  # untouched — no proxy in play


def test_create_args_never_include_privileged_or_host_namespaces():
    # A6, construction-time half of the gate only: proves the ARGUMENT
    # LIST never asks for any of these. Does NOT prove Docker's daemon
    # actually honors it at runtime — that needs `docker inspect` on a
    # live container (see the daemon-gated tests below).
    args = _build_create_args(**_COMMON_ARGS)
    assert "--privileged" not in args
    assert "--cap-add" not in args
    assert "--device" not in args
    for flag in ("--pid=host", "--ipc=host", "--uts=host", "--network=host"):
        assert flag not in args
    assert "--read-only" in args
    idx = args.index("--security-opt")
    assert args[idx + 1] == "no-new-privileges"


def test_create_args_ignores_allowed_imports():
    # A5's decision, proven structurally: allowed_imports isn't even a
    # parameter of _build_create_args, so two otherwise-identical
    # policies differing only in allowed_imports produce byte-identical
    # args. Forbidden shortcut this avoids: Docker-only cosmetic
    # filtering that looks like enforcement without restricting anything.
    args_a = _build_create_args(**_COMMON_ARGS)
    args_b = _build_create_args(**_COMMON_ARGS)
    assert args_a == args_b


def test_create_args_maps_read_only_paths_as_ro_binds():
    args = _build_create_args(**{**_COMMON_ARGS, "read_only_paths": ("/data/ref",)})
    assert "/data/ref:/data/ref:ro" in args


def test_create_args_workspace_is_the_writable_mount():
    args = _build_create_args(**_COMMON_ARGS)
    assert f"{_COMMON_ARGS['workspace_dir']}:/workspace:rw" in args


def test_create_args_names_and_labels_for_cleanup():
    # D4 — identity/cleanup lives in Docker's own name+label, not a new
    # SandboxHandle field (D12).
    args = _build_create_args(**_COMMON_ARGS)
    assert "--name" in args
    assert args[args.index("--name") + 1] == "t"
    assert "ocbrain.sandbox=true" in args


def test_no_new_sandbox_capability_claimed_yet():
    # D12 / B2 together: this session added zero SandboxCapability
    # values to contracts.py (none of the addendum's gates passed).
    from core.sandbox.contracts import SandboxCapability

    backend = DockerBackend(image_ref="example/image:tag")
    assert backend.capabilities.supported.issubset(set(SandboxCapability))
    assert len(backend.capabilities.supported) == 0


def test_a1_network_allowlist_requires_net_namespace_currently_holds():
    # A1 — current _CAPS is empty, so the paired-claim invariant holds
    # trivially. Real value is test_a1_invariant_actually_fires_when_violated
    # below: a fail-closed check that's never observed firing isn't
    # actually verified.
    from core.sandbox.backends.docker_backend import _check_a1_paired_capability_invariant

    backend = DockerBackend(image_ref="example/image:tag")
    _check_a1_paired_capability_invariant(backend.capabilities)  # must not raise


def test_a1_invariant_actually_fires_when_violated():
    # A1's whole point, proven directly: claiming NETWORK_ALLOWLIST
    # without NET_NAMESPACE must be rejected, not silently accepted.
    from core.sandbox.backends.docker_backend import _check_a1_paired_capability_invariant
    from core.sandbox.contracts import RuntimeCapabilities, SandboxCapability

    bad = RuntimeCapabilities(
        backend_name="docker", supported=frozenset({SandboxCapability.NETWORK_ALLOWLIST})
    )
    with pytest.raises(AssertionError):
        _check_a1_paired_capability_invariant(bad)


def test_a1_net_namespace_alone_is_fine():
    # NET_NAMESPACE without NETWORK_ALLOWLIST is a legitimate
    # intermediate state (e.g. only NETWORK_DENY_DEFAULT earned so far)
    # — A1 only constrains the NETWORK_ALLOWLIST direction.
    from core.sandbox.backends.docker_backend import _check_a1_paired_capability_invariant
    from core.sandbox.contracts import RuntimeCapabilities, SandboxCapability

    ok = RuntimeCapabilities(
        backend_name="docker", supported=frozenset({SandboxCapability.NET_NAMESPACE})
    )
    _check_a1_paired_capability_invariant(ok)  # must not raise


# ======================================================================
# Daemon-dependent tests — each individually skipped in every
# environment this has been run in so far. Representative subset, not
# yet full parity with NamespaceBackend's adversarial suite (Phase 6) —
# left to the actual host-verification session.
# ======================================================================


@pytest.fixture
def backend():
    image = os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")
    return DockerBackend(image_ref=image)


@_needs_docker
@pytest.mark.asyncio
async def test_echo_hello_runs_and_returns_output(backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("echo", "Hello"), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.termination_reason == TerminationReason.COMPLETED
        assert "Hello" in result.stdout
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_root_filesystem_is_read_only(backend, tmp_path):
    # D3 — a write outside the workspace mount must fail.
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("sh", "-c", "echo x > /etc/should-fail"), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.exit_code != 0
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_cancel_kills_full_process_tree(backend, tmp_path):
    # D7 — the specific failure mode this must NOT reproduce: a child or
    # grandchild surviving because only the top-level process was
    # signaled. Spawns a background grandchild that writes a heartbeat
    # file every 0.2s; after cancel(), the heartbeat must stop advancing.
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30)
    script = (
        "sh -c '(sh -c \"while true; do date +%s%N > /workspace/heartbeat; "
        'sleep 0.2; done" &) ; sleep 30\''
    )
    request = SandboxRequest(command=("sh", "-c", script), policy=policy)
    handle = await backend.create(request)
    import asyncio

    run_task = asyncio.ensure_future(backend.run(handle, request))
    await asyncio.sleep(1.0)
    await backend.cancel(handle)
    await asyncio.sleep(0.5)
    heartbeat_path = tmp_path / "heartbeat"
    reading_1 = heartbeat_path.read_text() if heartbeat_path.exists() else None
    await asyncio.sleep(1.0)
    reading_2 = heartbeat_path.read_text() if heartbeat_path.exists() else None
    run_task.cancel()
    await backend.destroy(handle)
    assert reading_1 == reading_2  # no descendant still writing after cancel()


@_needs_docker
@pytest.mark.asyncio
async def test_oom_kill_reported_as_resource_exceeded_not_inferred_from_exit_code(backend, tmp_path):
    # C1 — must come from State.OOMKilled, not from exit_code == 137
    # alone (a cancel() also produces 137).
    policy = SandboxPolicy(workspace_dir=str(tmp_path), memory_limit_mb=16, timeout_sec=15)
    request = SandboxRequest(
        command=("sh", "-c", "python3 -c \"'x'*10**9\" 2>/dev/null || : $(yes | head -c 200000000)"),
        policy=policy,
    )
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.termination_reason == TerminationReason.RESOURCE_EXCEEDED
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_artifacts_collected_with_real_sha256(backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("sh", "-c", "echo hi > out.txt"), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        names = [f[0] for f in result.artifacts.files]
        assert "out.txt" in names
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_double_destroy_is_idempotent(backend, tmp_path):
    # D6 — double-destroy must not raise.
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("true",), policy=policy)
    handle = await backend.create(request)
    await backend.destroy(handle)
    await backend.destroy(handle)  # must not raise


@_needs_docker
@pytest.mark.asyncio
async def test_inspect_is_side_effect_free(backend, tmp_path):
    # D8 — repeated inspect() calls must not start/restart/alter state.
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("true",), policy=policy)
    handle = await backend.create(request)
    try:
        s1 = await backend.inspect(handle)
        s2 = await backend.inspect(handle)
        s3 = await backend.inspect(handle)
        assert s1 == s2 == s3
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_two_concurrent_sandboxes_do_not_collide(tmp_path):
    # D4 — distinct container names/handles under real concurrency.
    import asyncio

    image = os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")
    b1, b2 = DockerBackend(image_ref=image), DockerBackend(image_ref=image)
    p1 = SandboxPolicy(workspace_dir=str(tmp_path / "a"))
    p2 = SandboxPolicy(workspace_dir=str(tmp_path / "b"))
    r1 = SandboxRequest(command=("true",), policy=p1)
    r2 = SandboxRequest(command=("true",), policy=p2)
    h1, h2 = await asyncio.gather(b1.create(r1), b2.create(r2))
    try:
        assert h1.handle_id != h2.handle_id
    finally:
        await asyncio.gather(b1.destroy(h1), b2.destroy(h2))


# ======================================================================
# A2 — MOUNT/PID/UTS_NAMESPACE have no defined gate in the base prompt;
# these are that gate, tested directly against a real container rather
# than inferred from HostConfig (the addendum's own wording: "container
# doesn't share the host mount namespace; can't see or signal host
# PIDs; hostname/domainname changes stay container-local").
# ======================================================================


@_needs_docker
@pytest.mark.asyncio
async def test_a2_mount_namespace_does_not_see_a_host_mount_created_after_start(backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("sleep", "10"), policy=policy)
    handle = await backend.create(request)
    container_id = backend._handles[handle.handle_id].container_id
    subprocess.run(["docker", "start", container_id], check=True, capture_output=True)
    mount_point = "/tmp/a2-pytest-host-only-mount"
    try:
        subprocess.run(["mkdir", "-p", mount_point], check=True)
        subprocess.run(["mount", "-t", "tmpfs", "tmpfs", mount_point], check=True)
        out = subprocess.run(
            ["docker", "exec", container_id, "cat", "/proc/self/mountinfo"],
            capture_output=True, text=True,
        )
        assert "a2-pytest-host-only-mount" not in out.stdout
    finally:
        subprocess.run(["umount", mount_point], check=False)
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_a2_pid_namespace_cannot_signal_or_see_a_real_host_pid(backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("sleep", "10"), policy=policy)
    handle = await backend.create(request)
    container_id = backend._handles[handle.handle_id].container_id
    subprocess.run(["docker", "start", container_id], check=True, capture_output=True)
    host_proc = subprocess.Popen(["sleep", "30"])
    try:
        result = subprocess.run(
            ["docker", "exec", container_id, "sh", "-c", f"kill -0 {host_proc.pid}"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0  # the host PID does not resolve inside the container
        ls_out = subprocess.run(
            ["docker", "exec", container_id, "sh", "-c", f"ls /proc | grep -c '^{host_proc.pid}$' || true"],
            capture_output=True, text=True,
        )
        assert ls_out.stdout.strip() == "0"
    finally:
        host_proc.kill()
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_a2_uts_namespace_container_hostname_is_independent_of_host(backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("sleep", "10"), policy=policy)
    handle = await backend.create(request)
    container_id = backend._handles[handle.handle_id].container_id
    subprocess.run(["docker", "start", container_id], check=True, capture_output=True)
    try:
        host_hostname = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
        container_hostname = subprocess.run(
            ["docker", "exec", container_id, "hostname"], capture_output=True, text=True
        ).stdout.strip()
        assert container_hostname != host_hostname
        assert container_hostname == container_id[:12]  # Docker's default: short container ID
        # And: no CAP_SYS_ADMIN inside means it can't even attempt to
        # change it at runtime either — a stronger property than A2
        # strictly asks for, but directly a consequence of A6.
        change_attempt = subprocess.run(
            ["docker", "exec", container_id, "hostname", "should-not-be-settable"],
            capture_output=True, text=True,
        )
        assert change_attempt.returncode != 0
    finally:
        await backend.destroy(handle)


# ======================================================================
# A9/C3 — the exploit as a permanent regression/consistency check, not
# just a one-off manual reproduction. Needs gcc-multilib (a genuine
# 32-bit static binary — an inline `int $0x80` from a 64-bit process
# was tried first and is wrong: its pointers aren't 32-bit-representable
# and the kernel returns EFAULT). Skipped, separately from
# _needs_docker, when that toolchain isn't available.
# ======================================================================

_SOCKETCALL_PROBE_C = r"""
#include <stdio.h>
#include <errno.h>
#include <string.h>
#include <unistd.h>

#define SYS_SOCKET 1

long int80_socketcall(int call, long a0, long a1, long a2) {
    long args[3] = {a0, a1, a2};
    long ret;
    __asm__ volatile ("int $0x80" : "=a" (ret) : "a" (102), "b" (call), "c" (args) : "memory");
    return ret;
}

int main(int argc, char **argv) {
    int domain = atoi(argv[1]);
    int type = atoi(argv[2]);
    long ret = int80_socketcall(SYS_SOCKET, domain, type, 0);
    if (ret < 0) {
        printf("FAILED errno=%ld\n", -ret);
        return 1;
    }
    char linkpath[64], target[256];
    snprintf(linkpath, sizeof(linkpath), "/proc/self/fd/%ld", ret);
    ssize_t n = readlink(linkpath, target, sizeof(target) - 1);
    if (n >= 0) {
        target[n] = '\0';
        printf("SUCCEEDED fd=%ld target=%s\n", ret, target);
        return 0;
    }
    printf("SUCCEEDED fd=%ld target=UNKNOWN\n", ret);
    return 0;
}
"""


def _can_build_32bit_probe() -> bool:
    try:
        r = subprocess.run(
            ["gcc", "-m32", "-x", "c", "-static", "-o", "/dev/null", "-"],
            input=_SOCKETCALL_PROBE_C, capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False


_needs_32bit_toolchain = pytest.mark.skipif(
    not _can_build_32bit_probe(), reason="requires gcc-multilib (a real 32-bit static toolchain)"
)


@_needs_docker
@_needs_32bit_toolchain
@pytest.mark.asyncio
async def test_a9_af_vsock_socketcall_bypass_is_consistent_with_lsm_state(tmp_path):
    """The exploit, kept alive as a check rather than left as a one-off
    manual finding. AF_VSOCK=40, SOCK_STREAM=1 (see docker_backend.py's
    _lsm_active() docstring for the full account of what was tried and
    why a seccomp-profile fix does not work here).

    Only one direction is asserted: when no LSM is active (this host,
    today), the bypass MUST be observably open — that is the current,
    honest, verified state, and if it ever silently stops being true
    without a corresponding code/doc update, this should fail loudly,
    not pass quietly. When an LSM *is* active, this only reports the
    result rather than asserting one, since _lsm_active() confirms
    presence, not that the specific deny rule is loaded.
    """
    from core.sandbox.backends.docker_backend import _lsm_active

    probe_dir = tmp_path / "probe"
    probe_dir.mkdir()
    src_path = probe_dir / "probe.c"
    bin_path = probe_dir / "probe"
    src_path.write_text(_SOCKETCALL_PROBE_C)
    build = subprocess.run(
        ["gcc", "-m32", "-static", "-o", str(bin_path), str(src_path)],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stderr

    AF_VSOCK, SOCK_STREAM = 40, 1
    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{probe_dir}:/probe:ro", "ocbrain-test/base:local",
         "/probe/probe", str(AF_VSOCK), str(SOCK_STREAM)],
        capture_output=True, text=True,
    )
    bypass_open = "SUCCEEDED" in result.stdout and "socket:[" in result.stdout

    if not _lsm_active():
        assert bypass_open, (
            "AF_VSOCK via socketcall unexpectedly blocked with no LSM active — "
            "if this host gained a real mitigation, update _lsm_active() and "
            "this test together rather than leaving them inconsistent: "
            f"{result.stdout!r}"
        )


# ======================================================================
# C2 — the network gate's real bypass paths, against the actual
# isolated network _ensure_sandbox_network() builds (an --internal
# Docker network, ICC disabled), not the "bridge" placeholder. Hits
# real external hosts (example.com/example.org), same as this
# repository's own test_net_proxy.py already does.
# ======================================================================


@pytest.fixture
def net_backend():
    image = os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")
    return DockerBackend(image_ref=image)


@_needs_docker
@pytest.mark.asyncio
async def test_c2_allowed_host_reaches_the_real_server_through_the_tunnel(net_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), allowed_hosts=("example.com",), timeout_sec=15)
    request = SandboxRequest(command=("python3", "-c", """
import urllib.request, urllib.error, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
try:
    r = urllib.request.urlopen('https://example.com/', timeout=8, context=ctx)
    print('OK', r.status)
except urllib.error.HTTPError as e:
    print('OK', e.code)  # reached the real server -- the tunnel worked, status is the server's own business
except urllib.error.URLError as e:
    print('TUNNEL_FAILED', e.reason)
"""), policy=policy)
    handle = await net_backend.create(request)
    try:
        result = await net_backend.run(handle, request)
        assert result.stdout.strip().startswith("OK"), result.stdout + result.stderr
    finally:
        await net_backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_c2_disallowed_host_is_rejected_at_the_tunnel(net_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), allowed_hosts=("example.com",), timeout_sec=15)
    request = SandboxRequest(command=("python3", "-c", """
import urllib.request, urllib.error, ssl
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
try:
    urllib.request.urlopen('https://example.org/', timeout=8, context=ctx)
    print('BYPASS')
except urllib.error.URLError as e:
    print('REJECTED', e.reason)
"""), policy=policy)
    handle = await net_backend.create(request)
    try:
        result = await net_backend.run(handle, request)
        assert result.stdout.strip().startswith("REJECTED"), result.stdout + result.stderr
        assert "403" in result.stdout
    finally:
        await net_backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_c2_direct_connection_cannot_bypass_the_proxy(net_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), allowed_hosts=("example.com",), timeout_sec=15)
    request = SandboxRequest(command=("python3", "-c", """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(('93.184.215.14', 80))
    print('BYPASS')
except OSError as e:
    print('BLOCKED', e)
"""), policy=policy)
    handle = await net_backend.create(request)
    try:
        result = await net_backend.run(handle, request)
        assert result.stdout.strip().startswith("BLOCKED"), result.stdout + result.stderr
    finally:
        await net_backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_c2_docker_gateway_has_no_route_to_the_internet(net_backend, tmp_path):
    # The gateway IS the proxy's own bind address (by design), but
    # nothing else routes through it -- confirm a DIFFERENT port on the
    # gateway (nothing listening there) fails the same way a real
    # internet destination would, not by falling through to some
    # forwarding path.
    from core.sandbox.backends.docker_backend import _ensure_sandbox_network

    gateway_ip = await _ensure_sandbox_network()
    policy = SandboxPolicy(workspace_dir=str(tmp_path), allowed_hosts=("example.com",), timeout_sec=15)
    request = SandboxRequest(command=("python3", "-c", f"""
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
try:
    s.connect(('{gateway_ip}', 65432))
    print('unexpected: connected')
except OSError as e:
    print('correctly refused:', e)
"""), policy=policy)
    handle = await net_backend.create(request)
    try:
        result = await net_backend.run(handle, request)
        assert "correctly refused" in result.stdout, result.stdout + result.stderr
    finally:
        await net_backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_c2_sibling_sandbox_container_is_unreachable(net_backend, tmp_path):
    # "another reachable container acting as a bridge" -- two sandboxes
    # on the shared internal network must not be able to reach each
    # other directly (enable_icc=false on _ensure_sandbox_network()).
    policy_a = SandboxPolicy(workspace_dir=str(tmp_path / "a"), allowed_hosts=("example.com",), timeout_sec=15)
    policy_b = SandboxPolicy(workspace_dir=str(tmp_path / "b"), allowed_hosts=("example.com",), timeout_sec=15)
    listener_req = SandboxRequest(command=("python3", "-c", """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 9999)); s.listen(1)
s.settimeout(6)
try:
    c, _ = s.accept()
    print('BYPASS: sibling connected')
except socket.timeout:
    print('no connection arrived (expected)')
"""), policy=policy_a)
    listener_handle = await net_backend.create(listener_req)
    listener_container_id = net_backend._handles[listener_handle.handle_id].container_id
    import subprocess as _sp
    _sp.run(["docker", "start", listener_container_id], check=True, capture_output=True)
    import asyncio as _asyncio
    await _asyncio.sleep(0.5)
    insp = _sp.run(
        ["docker", "inspect", listener_container_id, "--format",
         "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"],
        capture_output=True, text=True,
    )
    listener_ip = insp.stdout.strip()

    other_backend = DockerBackend(image_ref=net_backend._image_ref)
    connector_req = SandboxRequest(command=("python3", "-c", f"""
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(4)
try:
    s.connect(('{listener_ip}', 9999))
    print('BYPASS: reached sibling')
except OSError as e:
    print('correctly blocked from sibling:', e)
"""), policy=policy_b)
    connector_handle = await other_backend.create(connector_req)
    try:
        result = await other_backend.run(connector_handle, connector_req)
        assert "correctly blocked" in result.stdout, result.stdout + result.stderr
    finally:
        await other_backend.destroy(connector_handle)
        # listener_handle was started manually (bypassing run()) purely to
        # get it into RUNNING state for this probe -- destroy() still
        # tears it down correctly regardless of how it got there.
        await net_backend.destroy(listener_handle)


@_needs_docker
@pytest.mark.asyncio
async def test_c2_env_cannot_redirect_the_enforced_proxy(net_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), allowed_hosts=("example.com",), timeout_sec=15)
    request = SandboxRequest(
        command=("python3", "-c", "import os; print(os.environ.get('HTTP_PROXY'))"),
        policy=policy,
        env={"HTTP_PROXY": "http://10.255.255.1:9"},
    )
    handle = await net_backend.create(request)
    try:
        result = await net_backend.run(handle, request)
        assert "10.255.255.1" not in result.stdout
        assert result.stdout.strip().startswith("http://")
    finally:
        await net_backend.destroy(handle)
