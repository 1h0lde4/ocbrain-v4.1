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
import asyncio
import glob
import hashlib
import json
import sys
import os
import pathlib
import shutil
import socket
import tempfile
import subprocess

import pytest

from core.sandbox.admission import check_admission
from core.sandbox.backends._net_proxy import AllowlistProxy
from core.sandbox.backends.docker_backend import (
    _SANDBOX_NETWORK_NAME,
    DockerBackend,
    DockerBackendError,
    _build_container_env,
    _build_create_args,
)
from core.sandbox.contracts import (
    SandboxHandle,
    SandboxPolicy,
    SandboxRequest,
    SandboxState,
    TerminationReason,
)


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
    request_id="req-test",
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


def test_capabilities_reflect_exactly_the_evidence_backed_set():
    # Reconciliation §17: seven values, each with its own adversarial
    # runtime evidence — not "whatever Docker configuration implies".
    # (NETWORK_ALLOWLIST and NET_NAMESPACE were claimed as of §16 and
    # withdrawn in §17 / §17.8.)
    from core.sandbox.contracts import SandboxCapability

    backend = DockerBackend(image_ref="example/image:tag")
    expected = frozenset(
        {
            SandboxCapability.MOUNT_NAMESPACE,
            SandboxCapability.PID_NAMESPACE,
            SandboxCapability.UTS_NAMESPACE,
            SandboxCapability.CGROUP_MEMORY,
            SandboxCapability.NO_NEW_PRIVS,
            SandboxCapability.CGROUP_PIDS,
            SandboxCapability.FILESYSTEM_JAIL,
        }
    )
    assert backend.capabilities.supported == expected
    # Deliberately absent, each for a stated reason (see _CAPS's own
    # comment): USER_NAMESPACE (no userns-remap on this daemon),
    # SECCOMP (A9's bypass is real and unmitigated), NETWORK_DENY_DEFAULT
    # (admission.py never actually consults it), NETWORK_ALLOWLIST
    # (WITHDRAWN, §17: one sandbox can use another's egress proxy),
    # NET_NAMESPACE (WITHDRAWN, §17.8: no direct committed test yet;
    # a claim withdrawal only -- the implementation is unchanged).
    for absent in (
        SandboxCapability.USER_NAMESPACE,
        SandboxCapability.SECCOMP,
        SandboxCapability.NETWORK_DENY_DEFAULT,
        SandboxCapability.NETWORK_ALLOWLIST,
        SandboxCapability.NET_NAMESPACE,
    ):
        assert absent not in backend.capabilities.supported


def test_admission_boundary_admits_a_realistic_request_now():
    # What used to be test_empty_capabilities_means_admission_gate_
    # rejects_everything, updated because the premise changed: capabilities
    # is no longer empty, so this is the opposite claim, checked against
    # the real, unmodified check_admission() (addendum B3) — not
    # reimplemented here.
    backend = DockerBackend(image_ref="example/image:tag")
    policy = SandboxPolicy(workspace_dir="/tmp/whatever")
    request = SandboxRequest(command=("echo", "hi"), policy=policy)
    decision = check_admission(request, backend.capabilities)
    assert decision.allowed is True


def test_admission_boundary_rejects_a_networked_request_because_the_claim_is_withdrawn():
    # Expected result CHANGED (was: admitted) because the contract changed:
    # NETWORK_ALLOWLIST was withdrawn in reconciliation §17 after a
    # concurrent A/B test showed one sandbox using another's egress proxy.
    # Fail-closed: a request naming allowed_hosts must be rejected at
    # admission, by the real, unmodified check_admission() (addendum B3).
    backend = DockerBackend(image_ref="example/image:tag")
    policy = SandboxPolicy(workspace_dir="/tmp/whatever", allowed_hosts=("example.com",))
    request = SandboxRequest(command=("echo", "hi"), policy=policy)
    decision = check_admission(request, backend.capabilities)
    assert decision.allowed is False
    assert "allowed_hosts" in decision.reason


def test_admission_boundary_rejects_when_a_required_capability_is_missing():
    # The negative half of the same boundary: an otherwise-identical
    # capability set missing just CGROUP_PIDS must still be rejected —
    # proves the admitted cases above aren't admitted unconditionally.
    from core.sandbox.contracts import RuntimeCapabilities, SandboxCapability

    incomplete = RuntimeCapabilities(
        backend_name="docker",
        supported=frozenset(
            {SandboxCapability.FILESYSTEM_JAIL, SandboxCapability.CGROUP_MEMORY}
        ),
    )
    policy = SandboxPolicy(workspace_dir="/tmp/whatever")
    request = SandboxRequest(command=("echo", "hi"), policy=policy)
    decision = check_admission(request, incomplete)
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


def test_no_new_contracts_py_enum_members_added():
    # D12: every value _CAPS claims already existed in SandboxCapability
    # before this work — the claimed set grew, but no new enum member
    # was added to earn it (checked against the live enum, not a
    # hardcoded copy of it).
    from core.sandbox.contracts import SandboxCapability

    backend = DockerBackend(image_ref="example/image:tag")
    assert backend.capabilities.supported.issubset(set(SandboxCapability))
    assert len(backend.capabilities.supported) == 7


def test_a1_network_allowlist_requires_net_namespace_currently_holds():
    # A1 — NETWORK_ALLOWLIST is withdrawn (reconciliation §17), so this
    # holds trivially again: nothing is claimed that needs the pairing.
    # The mechanism itself is unchanged and stays enforced at import
    # time. Real value is
    # test_a1_invariant_actually_fires_when_violated below: a
    # fail-closed check that's never observed firing isn't actually
    # verified.
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


# The grandchild's heartbeat is written ATOMICALLY (temp file, then rename). A bare
# `date > heartbeat` truncates the file before writing it, so a host-side read can
# land in that gap and see an empty file (measured at about 0.8% of reads), which made
# the D7 tests flaky. A rename replaces the file in one step, so a reader sees the
# previous value or the new one, never an empty file.
_HEARTBEAT_LOOP = (
    "while true; do date +%s%N > /workspace/.heartbeat.tmp "
    "&& mv -f /workspace/.heartbeat.tmp /workspace/heartbeat; sleep 0.2; done"
)


@_needs_docker
@pytest.mark.asyncio
async def test_cancel_kills_full_process_tree(backend, tmp_path):
    # D7 — the specific failure mode this must NOT reproduce: a child or
    # grandchild surviving because only the top-level process was
    # signaled. Spawns a background grandchild that writes a heartbeat
    # file every 0.2s; after cancel(), the heartbeat must stop advancing.
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30)
    script = f"sh -c '(sh -c \"{_HEARTBEAT_LOOP}\" &) ; sleep 30'"
    request = SandboxRequest(command=("sh", "-c", script), policy=policy)
    handle = await backend.create(request)
    import asyncio

    run_task = asyncio.ensure_future(backend.run(handle, request))
    heartbeat_path = tmp_path / "heartbeat"
    # Wait for the grandchild itself instead of assuming a `docker start`
    # latency (a fixed sleep made this pass vacuously when the grandchild
    # never started, and fail when the daemon was merely slow -- §19.2).
    for _ in range(300):
        if heartbeat_path.exists():
            break
        await asyncio.sleep(0.05)
    assert heartbeat_path.exists(), "vacuous: the grandchild never started"
    await backend.cancel(handle)
    # cancel() does not wait for the kill to land (and must not); run() ends when it has.
    await asyncio.wait_for(run_task, timeout=15)
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


# ======================================================================
# D11 -- the checklist's actual race pairs, run for real rather than
# reasoned about: run()+cancel(), run()+destroy(), cancel()+destroy(),
# repeated cancel()/destroy(), inspect() mid-transition. No per-handle
# lock exists (see reconciliation doc); these confirm what asyncio's
# single-threaded event loop's own atomicity does and doesn't cover,
# rather than assuming either way.
# ======================================================================


@pytest.fixture
def conc_backend():
    image = os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")
    return DockerBackend(image_ref=image)


@_needs_docker
@pytest.mark.asyncio
async def test_d11_run_plus_cancel_concurrently(conc_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30)
    request = SandboxRequest(command=("sleep", "20"), policy=policy)
    handle = await conc_backend.create(request)
    run_task = asyncio.ensure_future(conc_backend.run(handle, request))
    await asyncio.sleep(1.0)
    await conc_backend.cancel(handle)
    result = await run_task
    assert result.termination_reason == TerminationReason.CANCELLED
    await conc_backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_d11_run_plus_destroy_concurrently_no_hang_no_orphan(conc_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30)
    request = SandboxRequest(command=("sleep", "20"), policy=policy)
    handle = await conc_backend.create(request)
    container_id = conc_backend._handles[handle.handle_id].container_id
    run_task = asyncio.ensure_future(conc_backend.run(handle, request))
    await asyncio.sleep(0.5)
    await conc_backend.destroy(handle)  # must not raise
    result = await asyncio.wait_for(run_task, timeout=10)  # must not hang
    assert result.termination_reason == TerminationReason.ERROR
    check = subprocess.run(["docker", "ps", "-aq", "--filter", f"id={container_id}"], capture_output=True, text=True)
    assert check.stdout.strip() == ""  # no orphan left behind


@_needs_docker
@pytest.mark.asyncio
async def test_d11_cancel_plus_destroy_concurrently(conc_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30)
    request = SandboxRequest(command=("sleep", "20"), policy=policy)
    handle = await conc_backend.create(request)
    container_id = conc_backend._handles[handle.handle_id].container_id
    subprocess.run(["docker", "start", container_id], check=True, capture_output=True)
    results = await asyncio.gather(
        conc_backend.cancel(handle), conc_backend.destroy(handle), return_exceptions=True
    )
    assert all(r is None for r in results), results  # neither raised
    check = subprocess.run(["docker", "ps", "-aq", "--filter", f"id={container_id}"], capture_output=True, text=True)
    assert check.stdout.strip() == ""


@_needs_docker
@pytest.mark.asyncio
async def test_d11_repeated_cancel_and_destroy_including_after_destroy(conc_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30)
    request = SandboxRequest(command=("sleep", "20"), policy=policy)
    handle = await conc_backend.create(request)
    await conc_backend.cancel(handle)
    await conc_backend.cancel(handle)  # repeated cancel
    await conc_backend.destroy(handle)
    await conc_backend.cancel(handle)  # cancel after destroy -- must not raise
    await conc_backend.destroy(handle)  # double destroy -- must not raise


@_needs_docker
@pytest.mark.asyncio
async def test_d11_inspect_mid_run_does_not_block_or_mutate(conc_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=15)
    request = SandboxRequest(command=("sleep", "6"), policy=policy)
    handle = await conc_backend.create(request)
    run_task = asyncio.ensure_future(conc_backend.run(handle, request))
    await asyncio.sleep(1.0)
    states = [await conc_backend.inspect(handle) for _ in range(3)]
    assert states == [SandboxState.RUNNING] * 3
    result = await run_task
    assert result.termination_reason == TerminationReason.COMPLETED
    await conc_backend.destroy(handle)


# ======================================================================
# Closing the three remaining capability-evidence gaps before _CAPS
# claims anything: NO_NEW_PRIVS (runtime, not just the create request),
# CGROUP_PIDS (adversarial, bounded so a failure can't consume real
# host resources), FILESYSTEM_JAIL (the actual attack surface, not just
# ReadonlyRootfs=true).
# ======================================================================


@pytest.fixture
def cap_backend():
    image = os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")
    return DockerBackend(image_ref=image)


@_needs_docker
@pytest.mark.asyncio
async def test_no_new_privs_runtime_proc_status(cap_backend, tmp_path):
    # The base prompt's own Phase 2 method: /proc/self/status on the
    # RUNNING container, not HostConfig.SecurityOpt on the request.
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("sh", "-c", "grep NoNewPrivs /proc/self/status"), policy=policy)
    handle = await cap_backend.create(request)
    try:
        result = await cap_backend.run(handle, request)
        assert result.stdout.strip() == "NoNewPrivs:\t1"
    finally:
        await cap_backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_cgroup_pids_enforced_and_container_stays_controllable(cap_backend, tmp_path):
    # Deliberately low ceiling -- a failure here can't consume real
    # host resources. Proves: burst reaches the ceiling, further
    # creation fails, the container is still exec-able WHILE still
    # under pressure (not just before or after), and destroy() is
    # clean with no host-side leak.
    policy = SandboxPolicy(workspace_dir=str(tmp_path), max_pids=8, timeout_sec=20)
    script = (
        "import subprocess, time\n"
        "spawned = 0\n"
        "for i in range(200):\n"
        "    try:\n"
        "        subprocess.Popen(['sleep', '15'])\n"
        "        spawned += 1\n"
        "    except OSError:\n"
        "        break\n"
        "print('spawned:', spawned)\n"
        "time.sleep(4)\n"
    )
    request = SandboxRequest(command=("python3", "-c", script), policy=policy)
    handle = await cap_backend.create(request)
    container_id = cap_backend._handles[handle.handle_id].container_id
    run_task = asyncio.ensure_future(cap_backend.run(handle, request))
    await asyncio.sleep(2.0)
    probe = subprocess.run(
        ["docker", "exec", container_id, "echo", "still-controllable"], capture_output=True, text=True
    )
    assert probe.returncode == 0
    assert "still-controllable" in probe.stdout
    result = await run_task
    # max_pids=8 includes PID 1 itself, so at most 7 children succeed
    assert "spawned: 7" in result.stdout, result.stdout
    await cap_backend.destroy(handle)
    leftover = subprocess.run(["pgrep", "-f", "sleep 15"], capture_output=True, text=True)
    assert leftover.stdout.strip() == ""  # no host-side leak


@_needs_docker
@pytest.mark.asyncio
async def test_filesystem_jail_full_attack_surface(cap_backend, tmp_path):
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    script = r"""
import os, errno
results = {}
def attempt(label, fn):
    try:
        fn(); results[label] = 'OK'
    except OSError as e:
        results[label] = errno.errorcode.get(e.errno, e.errno)

attempt('workspace', lambda: open('/workspace/ok.txt', 'w').write('hi'))
attempt('root_etc', lambda: open('/etc/should-fail.txt', 'w').write('x'))
attempt('other_path', lambda: open('/usr/should-fail.txt', 'w').write('x'))
attempt('traversal', lambda: open('/workspace/../etc/passwd', 'w').write('x'))
os.symlink('/etc/passwd', '/workspace/evil_link')
attempt('symlink_escape', lambda: open('/workspace/evil_link', 'w').write('x'))
attempt('workspace_after', lambda: open('/workspace/ok2.txt', 'w').write('still fine'))
import json
print(json.dumps(results))
"""
    request = SandboxRequest(command=("python3", "-c", script), policy=policy)
    handle = await cap_backend.create(request)
    try:
        result = await cap_backend.run(handle, request)
        import json

        r = json.loads(result.stdout.strip())
        assert r["workspace"] == "OK"
        assert r["root_etc"] == "EROFS"
        assert r["other_path"] == "EROFS"
        assert r["traversal"] == "EROFS"
        assert r["symlink_escape"] == "EROFS"
        assert r["workspace_after"] == "OK"
    finally:
        await cap_backend.destroy(handle)


# ======================================================================
# D10 -- failure-path cleanup (checklist D10, "one test per failure
# point, each asserting no leftover labeled resource"; forbidden
# shortcut: "testing only the happy-path destroy() after a successful
# run").
#
# Invariant under test: every resource acquired before a failure is
# EITHER cleaned immediately OR retained in a handle that is still
# destroyable -- never neither.
#
# HONESTY NOTE on the injected failures below. They are SIMULATED at the
# boundary where this backend calls the docker CLI (asyncio.create_
# subprocess_exec is patched for specific invocations). They exercise
# the backend's own cleanup invariant. They do NOT claim that Docker or
# its daemon produced these failures, and a passing test here is not
# evidence about daemon behavior. Every injecting test asserts the
# injection actually fired (`.hits`), so it cannot pass vacuously.
#
# NOT asserted here: the lifecycle of the shared network OBJECT itself
# (persist vs remove). The frozen documents are silent, and the
# cross-sandbox finding in reconciliation §17 makes that a question for
# the network-redesign workstream, not something to settle by test now.
# What IS asserted: no sandbox ENDPOINT on that network outlives its
# container.
# ======================================================================


class _SimulatedFailedProcess:
    """Stands in for a docker CLI invocation that exits nonzero."""

    returncode = 1

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"", b"simulated docker failure"

    async def wait(self) -> int:
        return 1


class _FailsAfterRealSuccess:
    """Wraps a REAL, already-spawned docker process: lets it finish (so
    e.g. the container genuinely exists), then raises -- modelling a
    failure (or cancellation) that lands after docker did its work but
    before the backend recorded a handle for it."""

    def __init__(self, real_proc, exc_type):
        self._real = real_proc
        self._exc_type = exc_type

    @property
    def returncode(self):
        return self._real.returncode

    async def communicate(self):
        await self._real.communicate()
        raise self._exc_type("simulated: failure after the docker command had already succeeded")

    async def wait(self):
        return await self._real.wait()


class _DockerFailureInjector:
    """mode: "spawn_error" (the CLI cannot be spawned at all), "nonzero_
    exit" (the CLI runs and fails), or "fail_after_success" (the command
    really ran, then the caller-side await fails). `active` may be
    flipped off mid-test to model the failure clearing."""

    def __init__(self, monkeypatch, matches, mode, exc_type=RuntimeError, delay=0.0):
        self.active = True
        self.hits = 0
        real_exec = asyncio.create_subprocess_exec

        async def fake(*argv, **kwargs):
            if self.active and matches(argv):
                self.hits += 1
                if delay:
                    await asyncio.sleep(delay)  # widens the window so interleavings are deterministic
                if mode == "slow":
                    return await real_exec(*argv, **kwargs)  # the real command, just late
                if mode == "spawn_error":
                    raise FileNotFoundError("simulated: docker CLI could not be spawned")
                if mode == "nonzero_exit":
                    return _SimulatedFailedProcess()
                if mode == "fail_after_success":
                    return _FailsAfterRealSuccess(await real_exec(*argv, **kwargs), exc_type)
                raise AssertionError(f"unknown injection mode {mode!r}")
            return await real_exec(*argv, **kwargs)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake)


def _docker_cmd(*prefix):
    return lambda argv: tuple(argv[: len(prefix) + 1]) == ("docker", *prefix)


def _any_docker(argv):
    return bool(argv) and argv[0] == "docker"


def _shared_network_endpoints() -> set:
    r = subprocess.run(
        ["docker", "network", "inspect", _SANDBOX_NETWORK_NAME, "--format",
         "{{range $id, $c := .Containers}}{{$id}} {{end}}"],
        capture_output=True, text=True,
    )
    return set(r.stdout.split()) if r.returncode == 0 else set()


def _d10_snapshot() -> dict:
    ps = subprocess.run(
        ["docker", "ps", "-aq", "--no-trunc", "--filter", "label=ocbrain.sandbox=true"],
        capture_output=True, text=True, check=True,
    )
    return {
        "containers": set(ps.stdout.split()),
        "shared_network_endpoints": _shared_network_endpoints(),
        "artifact_tmpdirs": set(glob.glob(os.path.join(tempfile.gettempdir(), "ocbrain-docker-artifacts-*"))),
    }


def _assert_nothing_leaked(before: dict) -> None:
    after = _d10_snapshot()
    for key in before:
        assert after[key] - before[key] == set(), f"D10: leaked {key}: {after[key] - before[key]}"


@pytest.fixture
def d10_backend():
    image = os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")
    return DockerBackend(image_ref=image)


@pytest.fixture
def started_proxies(monkeypatch):
    """Records (bind_ip, port) of every AllowlistProxy started during the
    test, through the REAL start(). Listener liveness is then checked
    black-box, by connecting -- not by reading proxy internals."""
    started: list = []
    real_start = AllowlistProxy.start

    def recording_start(self, port=0):
        bound = real_start(self, port)
        started.append((self._bind_ip, bound))
        return bound

    monkeypatch.setattr(AllowlistProxy, "start", recording_start)
    return started


def _assert_no_live_listener(started: list) -> None:
    for ip, port in started:
        with pytest.raises(OSError):
            socket.create_connection((ip, port), timeout=1).close()


def _d10_request(tmp_path, command, *, networked=True, timeout_sec=20):
    policy = SandboxPolicy(
        workspace_dir=str(tmp_path / "ws"),  # does not exist yet: create() makes it
        allowed_hosts=("example.com",) if networked else (),
        timeout_sec=timeout_sec,
    )
    return SandboxRequest(command=command, policy=policy)


# ---- creation failure ------------------------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d10_creation_failure_docker_create_exits_nonzero(d10_backend, started_proxies, monkeypatch, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    inj = _DockerFailureInjector(monkeypatch, _docker_cmd("create"), "nonzero_exit")
    with pytest.raises(DockerBackendError):
        await d10_backend.create(request)
    assert inj.hits >= 1
    assert started_proxies, "vacuous: this scenario must have started a proxy"
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir), "workspace dir created by the failed create() leaked"
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
async def test_d10_creation_failure_spawn_error_leaves_no_live_proxy_listener(d10_backend, started_proxies, monkeypatch, tmp_path):
    """The specific reproduced defect: proxy.start() succeeded, then the
    docker-create subprocess could not even be spawned."""
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    inj = _DockerFailureInjector(monkeypatch, _docker_cmd("create"), "spawn_error")
    with pytest.raises(OSError):
        await d10_backend.create(request)
    assert inj.hits >= 1
    assert started_proxies, "vacuous: this scenario must have started a proxy"
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
@pytest.mark.parametrize("exc_type", [RuntimeError, asyncio.CancelledError])
async def test_d10_failure_after_container_really_exists_removes_it_by_label(
    d10_backend, started_proxies, monkeypatch, tmp_path, exc_type
):
    """`docker create` genuinely succeeded (a real container exists), then
    the caller-side await failed/was cancelled before any handle was
    recorded. With no handle, the only way to find it is the per-run
    label."""
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    inj = _DockerFailureInjector(monkeypatch, _docker_cmd("create"), "fail_after_success", exc_type)
    with pytest.raises(exc_type):
        await d10_backend.create(request)
    assert inj.hits >= 1
    assert started_proxies
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)  # includes: the really-created container is gone


@_needs_docker
@pytest.mark.asyncio
async def test_d10_pre_existing_workspace_is_not_deleted_by_a_failed_create(d10_backend, monkeypatch, tmp_path):
    """Safety guard on the fix itself: failed-create cleanup may only
    remove a workspace directory THIS call created, never a caller-owned
    one that was already there."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "caller_data.txt").write_text("keep me")
    request = _d10_request(tmp_path, ("true",), networked=False)
    inj = _DockerFailureInjector(monkeypatch, _docker_cmd("create"), "nonzero_exit")
    with pytest.raises(DockerBackendError):
        await d10_backend.create(request)
    assert inj.hits >= 1
    assert (ws / "caller_data.txt").read_text() == "keep me"


# ---- network-setup failure ------------------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d10_network_setup_failure_leaves_nothing(d10_backend, started_proxies, monkeypatch, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    # Every `docker network ...` call fails, so this fails whether or not
    # the shared network already exists.
    inj = _DockerFailureInjector(monkeypatch, _docker_cmd("network"), "nonzero_exit")
    with pytest.raises(DockerBackendError):
        await d10_backend.create(request)
    assert inj.hits >= 1
    assert started_proxies == [], "network setup failed first: no proxy should exist yet"
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


# ---- container start failure / execution failure --------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d10_container_start_failure_then_destroy_leaves_nothing(d10_backend, started_proxies, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("/nonexistent-binary-d10",))
    handle = await d10_backend.create(request)
    result = await d10_backend.run(handle, request)
    assert result.exit_code != 0  # the container could not run its command
    await d10_backend.destroy(handle)
    assert started_proxies
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
async def test_d10_execution_failure_then_destroy_leaves_nothing(d10_backend, started_proxies, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("sh", "-c", "exit 3"))
    handle = await d10_backend.create(request)
    result = await d10_backend.run(handle, request)
    assert result.exit_code == 3
    await d10_backend.destroy(handle)
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


# ---- timeout / cancellation -----------------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d10_timeout_kills_the_workload_then_destroy_leaves_nothing(d10_backend, started_proxies, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("sleep", "30"), timeout_sec=1)
    handle = await d10_backend.create(request)
    container_id = d10_backend._handles[handle.handle_id].container_id
    result = await d10_backend.run(handle, request)
    assert result.termination_reason == TerminationReason.TIMEOUT
    running = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", container_id], capture_output=True, text=True
    )
    assert running.stdout.strip() == "false", "timeout returned but the workload is still running"
    await d10_backend.destroy(handle)
    _assert_no_live_listener(started_proxies)
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
async def test_d10_cancellation_then_destroy_leaves_nothing(d10_backend, started_proxies, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("sleep", "30"), timeout_sec=30)
    handle = await d10_backend.create(request)
    run_task = asyncio.ensure_future(d10_backend.run(handle, request))
    await asyncio.sleep(1.0)
    await d10_backend.cancel(handle)
    result = await asyncio.wait_for(run_task, timeout=15)
    assert result.termination_reason == TerminationReason.CANCELLED
    await d10_backend.destroy(handle)
    _assert_no_live_listener(started_proxies)
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


# ---- external disappearance -----------------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d10_container_removed_externally_mid_run(d10_backend, started_proxies, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("sleep", "30"), timeout_sec=30)
    handle = await d10_backend.create(request)
    container_id = d10_backend._handles[handle.handle_id].container_id
    run_task = asyncio.ensure_future(d10_backend.run(handle, request))
    await asyncio.sleep(1.0)
    subprocess.run(["docker", "rm", "-f", container_id], check=True, capture_output=True)  # not via the backend
    await asyncio.wait_for(run_task, timeout=15)  # must not hang
    await d10_backend.destroy(handle)  # must not raise: already-gone is already-clean
    assert started_proxies
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
async def test_d10_container_removed_externally_before_run(d10_backend, started_proxies, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    handle = await d10_backend.create(request)
    container_id = d10_backend._handles[handle.handle_id].container_id
    subprocess.run(["docker", "rm", "-f", container_id], check=True, capture_output=True)
    result = await d10_backend.run(handle, request)
    assert result.termination_reason == TerminationReason.ERROR
    await d10_backend.destroy(handle)
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


# ---- daemon / API failure -------------------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d10_daemon_unreachable_during_destroy_keeps_the_handle_destroyable(
    d10_backend, started_proxies, monkeypatch, tmp_path
):
    """Simulated: EVERY docker CLI call fails to spawn while destroy() runs.
    destroy() cannot remove or even verify the container, so it must NOT
    report clean and must NOT drop the handle -- otherwise the container
    is orphaned with no way to retry. Once the failure clears, a second
    destroy() must finish the job."""
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    handle = await d10_backend.create(request)
    container_id = d10_backend._handles[handle.handle_id].container_id
    await d10_backend.run(handle, request)

    inj = _DockerFailureInjector(monkeypatch, _any_docker, "spawn_error")
    with pytest.raises(DockerBackendError):
        await d10_backend.destroy(handle)
    assert inj.hits >= 1
    assert handle.handle_id in d10_backend._handles, "handle dropped although the container was not confirmed gone"
    assert container_id in _d10_snapshot()["containers"], "test premise: the container must still exist here"
    _assert_no_live_listener(started_proxies)  # the host-side listener does not wait on the daemon

    inj.active = False  # the failure clears
    await d10_backend.destroy(handle)  # retry succeeds
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
async def test_d10_daemon_failure_during_run_start_keeps_the_handle_destroyable(
    d10_backend, started_proxies, monkeypatch, tmp_path
):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    handle = await d10_backend.create(request)
    inj = _DockerFailureInjector(monkeypatch, _docker_cmd("start"), "spawn_error")
    with pytest.raises(OSError):
        await d10_backend.run(handle, request)
    assert inj.hits >= 1
    assert handle.handle_id in d10_backend._handles
    inj.active = False
    await d10_backend.destroy(handle)
    _assert_no_live_listener(started_proxies)
    assert d10_backend._handles == {}
    assert not os.path.exists(request.policy.workspace_dir)
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
async def test_d10_artifact_copy_failure_leaks_no_host_tmpdir(d10_backend, started_proxies, monkeypatch, tmp_path):
    before = _d10_snapshot()
    request = _d10_request(tmp_path, ("true",))
    handle = await d10_backend.create(request)
    inj = _DockerFailureInjector(monkeypatch, _docker_cmd("cp"), "nonzero_exit")
    result = await d10_backend.run(handle, request)
    assert inj.hits >= 1
    assert result.artifacts.files == ()
    inj.active = False
    await d10_backend.destroy(handle)
    _assert_no_live_listener(started_proxies)
    _assert_nothing_leaked(before)  # includes artifact_tmpdirs


# ======================================================================
# Closeout audit (reconciliation §18) -- evidence the frozen checklist
# literally requires, which earlier passes either only asserted in prose
# or covered with a weaker test (e.g. test_artifacts_collected_with_real_
# sha256 never checked a hash; the D7 heartbeat test would pass
# vacuously if the grandchild never started; D2/D4/D6 had no runtime
# tests of the specified cases; A3/A6 had construction-level tests
# only). Each test below asserts EFFECTIVE state (docker inspect,
# in-container behavior, host filesystem), not the request that was built.
# ======================================================================


def _inspect_container(container_id: str) -> dict:
    out = subprocess.run(["docker", "inspect", container_id], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)[0]


def _closeout_image() -> str:
    return os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")


# ---- A3: image identity ---------------------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_a3_independent_backends_resolve_the_identical_immutable_digest(tmp_path):
    b1, b2 = DockerBackend(image_ref=_closeout_image()), DockerBackend(image_ref=_closeout_image())
    d1, d2 = await b1._resolve_image_digest(), await b2._resolve_image_digest()
    assert d1 == d2 and "@sha256:" in d1  # two fresh resolutions, not one cached value
    handles = []
    try:
        for i, b in enumerate((b1, b2)):
            request = SandboxRequest(command=("true",), policy=SandboxPolicy(workspace_dir=str(tmp_path / f"w{i}")))
            h = await b.create(request)
            handles.append((b, h))
            info = _inspect_container(b._handles[h.handle_id].container_id)
            assert info["Config"]["Image"] == d1  # the container is pinned to the digest, not a tag
    finally:
        for b, h in handles:
            await b.destroy(h)


@_needs_docker
@pytest.mark.asyncio
async def test_a3_image_like_env_cannot_change_what_runs(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    hostile = {k: "attacker/evil:latest" for k in ("OCBRAIN_SANDBOX_DOCKER_IMAGE", "DOCKER_IMAGE", "IMAGE", "image")}
    request = SandboxRequest(command=("true",), env=hostile, policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    try:
        expected = await backend._resolve_image_digest()
        info = _inspect_container(backend._handles[handle.handle_id].container_id)
        assert info["Config"]["Image"] == expected
        assert "attacker" not in info["Config"]["Image"]
    finally:
        await backend.destroy(handle)


# ---- A6: privilege surface, as the daemon actually holds it ----------


@_needs_docker
@pytest.mark.asyncio
@pytest.mark.parametrize("networked", [False, True])
async def test_a6_runtime_inspect_shows_no_privilege_or_host_sharing(tmp_path, networked):
    backend = DockerBackend(image_ref=_closeout_image())
    policy = SandboxPolicy(workspace_dir=str(tmp_path / "ws"), allowed_hosts=("example.com",) if networked else ())
    handle = await backend.create(SandboxRequest(command=("true",), policy=policy))
    try:
        info = _inspect_container(backend._handles[handle.handle_id].container_id)
        hc = info["HostConfig"]
        assert hc["Privileged"] is False
        assert not hc.get("CapAdd")
        assert hc.get("PidMode") in ("", None)
        assert hc.get("IpcMode") in ("", None, "private")
        assert hc.get("UTSMode") in ("", None)
        assert hc["NetworkMode"] != "host"
        assert not hc.get("Devices")
        assert hc["ReadonlyRootfs"] is True
        assert any("no-new-privileges" in o for o in (hc.get("SecurityOpt") or []))
        for m in info["Mounts"]:
            assert ".sock" not in m["Source"], f"runtime socket mounted: {m}"
            assert m["Source"] != "/"
    finally:
        await backend.destroy(handle)


# ---- C1: exit code 137 alone must never decide the classification ----


@_needs_docker
@pytest.mark.asyncio
async def test_c1_ordinary_sigkill_with_exit_137_is_not_resource_exceeded(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("sh", "-c", "sh -c 'kill -9 $$'; exit $?"), policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.exit_code == 137  # the same code a real OOM kill produces ...
        assert result.termination_reason != TerminationReason.RESOURCE_EXCEEDED  # ... and it is not one
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_c1_cancel_with_exit_137_is_cancelled_not_resource_exceeded(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("sleep", "30"), policy=SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30))
    handle = await backend.create(request)
    try:
        run_task = asyncio.ensure_future(backend.run(handle, request))
        await asyncio.sleep(1.0)
        await backend.cancel(handle)
        result = await asyncio.wait_for(run_task, timeout=15)
        assert result.exit_code == 137
        assert result.termination_reason == TerminationReason.CANCELLED
    finally:
        await backend.destroy(handle)


# ---- D2: read_only_paths, at runtime ---------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d2_read_only_path_rejects_write_delete_create_and_symlink_escape(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    (ro / "existing.txt").write_text("original")
    secret = tmp_path / "secret.txt"
    secret.write_text("HOSTSECRET-d2")
    os.symlink(str(secret), ro / "abs_link")  # absolute host path
    os.symlink("../secret.txt", ro / "rel_link")  # relative climb out of the mount
    backend = DockerBackend(image_ref=_closeout_image())
    script = (
        f"echo w > {ro}/new.txt 2>/dev/null; echo new=$?; "
        f"echo w > {ro}/existing.txt 2>/dev/null; echo mod=$?; "
        f"rm {ro}/existing.txt 2>/dev/null; echo rm=$?; "
        f"cat {ro}/abs_link 2>/dev/null; echo abs=$?; "
        f"cat {ro}/rel_link 2>/dev/null; echo rel=$?; "
        f"cat {ro}/existing.txt"
    )
    policy = SandboxPolicy(workspace_dir=str(tmp_path / "ws"), read_only_paths=(str(ro),))
    request = SandboxRequest(command=("sh", "-c", script), policy=policy)
    handle = await backend.create(request)
    try:
        out = (await backend.run(handle, request)).stdout
    finally:
        await backend.destroy(handle)
    for op in ("new", "mod", "rm", "abs", "rel"):
        assert f"{op}=0" not in out, f"{op} unexpectedly succeeded inside the read-only path:\n{out}"
    assert "HOSTSECRET-d2" not in out  # neither symlink reached the host secret
    assert out.rstrip().endswith("original")  # the path is readable, just not writable
    assert (ro / "existing.txt").read_text() == "original"  # host side untouched
    assert not (ro / "new.txt").exists()


# ---- D4: identity and label-based cleanup ----------------------------


def test_d4_create_args_label_carries_the_request_id():
    args = _build_create_args(**{**_COMMON_ARGS, "request_id": "req-d4-1234"})
    assert "ocbrain.request_id=req-d4-1234" in args


@_needs_docker
@pytest.mark.asyncio
async def test_d4_abandoned_labeled_container_is_found_and_removed_by_a_cleanup_pass(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("true",), policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    container_id = backend._handles[handle.handle_id].container_id
    del backend, handle  # abandoned: nothing in-process still refers to it

    def ids(label: str) -> set:
        r = subprocess.run(["docker", "ps", "-aq", "--no-trunc", "--filter", f"label={label}"],
                           capture_output=True, text=True, check=True)
        return set(r.stdout.split())

    try:
        assert container_id in ids(f"ocbrain.request_id={request.request_id}")  # by request identity
        assert container_id in ids("ocbrain.sandbox=true")  # by the generic backend label
    finally:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True)  # the cleanup pass
    assert container_id not in ids("ocbrain.sandbox=true")


# ---- D5: artifacts ----------------------------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d5_manifest_hash_and_size_match_an_independent_recomputation(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    script = "printf 'hello-d5' > out.bin && mkdir sub && printf 'deep' > sub/deep.txt"
    request = SandboxRequest(command=("sh", "-c", script), policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    try:
        files = {name: (sha, size) for name, sha, size in (await backend.run(handle, request)).artifacts.files}
    finally:
        await backend.destroy(handle)
    assert files["out.bin"] == (hashlib.sha256(b"hello-d5").hexdigest(), 8)
    assert files["sub/deep.txt"] == (hashlib.sha256(b"deep").hexdigest(), 4)  # normalized relative path


@_needs_docker
@pytest.mark.asyncio
async def test_d5_absolute_symlinks_are_rejected_while_legitimate_artifacts_survive(tmp_path):
    secret = tmp_path / "host_secret.txt"
    secret.write_text("HOSTSECRET-d5")
    secret_sha = hashlib.sha256(secret.read_bytes()).hexdigest()
    backend = DockerBackend(image_ref=_closeout_image())
    script = f"ln -s {secret} leak_abs; ln -s /etc leak_dir; echo ok > legit.txt"
    request = SandboxRequest(command=("sh", "-c", script), policy=SandboxPolicy(workspace_dir=str(tmp_path / "ws")))
    handle = await backend.create(request)
    try:
        files = (await backend.run(handle, request)).artifacts.files
    finally:
        await backend.destroy(handle)
    names = [f[0] for f in files]
    assert "legit.txt" in names  # the collector rejects the links, not the workspace
    assert not [n for n in names if "leak_" in n], names
    assert secret_sha not in [f[1] for f in files]  # the host file was never hashed into the manifest


@_needs_docker
@pytest.mark.asyncio
async def test_d5_relative_escaping_symlinks_never_reach_the_manifest(tmp_path):
    """Recorded behavior, not an endorsement: a RELATIVE symlink that climbs
    out of the workspace makes `docker cp` itself refuse (`invalid symlink`),
    so the manifest comes back empty -- nothing escapes, but the sandbox's
    legitimate artifacts are lost silently. The invariant asserted is the
    D5 one: no manifest entry resolves outside the artifact root."""
    backend = DockerBackend(image_ref=_closeout_image())
    script = "ln -s ../../../../../etc/hostname leak_rel; mkdir sub; ln -s ../../../../etc/hostname sub/leak_nested; echo ok > legit.txt"
    request = SandboxRequest(command=("sh", "-c", script), policy=SandboxPolicy(workspace_dir=str(tmp_path / "ws")))
    handle = await backend.create(request)
    try:
        files = (await backend.run(handle, request)).artifacts.files
    finally:
        await backend.destroy(handle)
    assert not [f[0] for f in files if "leak_" in f[0]], files


@_needs_docker
def test_d5_non_regular_files_neither_hang_collection_nor_enter_the_manifest(tmp_path):
    """Run in a subprocess with a hard timeout on purpose: hashing a FIFO
    would block the event loop thread itself (synchronous open()), so an
    in-process wait_for could never fire and a failure would hang the
    whole suite instead of failing this test."""
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    ws = tmp_path / "ws"
    script = f"""
import asyncio, sys
sys.path.insert(0, {str(repo_root)!r})
from core.sandbox.backends.docker_backend import DockerBackend
from core.sandbox.contracts import SandboxPolicy, SandboxRequest
async def main():
    be = DockerBackend(image_ref={_closeout_image()!r})
    req = SandboxRequest(command=("sh", "-c", "mkfifo pipe; echo ok > legit.txt"),
                         policy=SandboxPolicy(workspace_dir={str(ws)!r}))
    h = await be.create(req)
    try:
        r = await be.run(h, req)
        print("NAMES=" + ",".join(sorted(f[0] for f in r.artifacts.files)))
    finally:
        await be.destroy(h)
asyncio.run(main())
"""
    before = _d10_snapshot()["containers"]
    try:
        proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        pytest.fail("artifact collection hung on a non-regular file (FIFO) the sandbox created")
    finally:
        for cid in _d10_snapshot()["containers"] - before:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True)  # never leave a hung run's container
    assert proc.returncode == 0, proc.stderr
    names = proc.stdout.split("NAMES=")[1].strip().split(",")
    assert names == ["legit.txt"], names


# ---- D6: invalid and repeated lifecycle calls -------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d6_run_before_create_is_a_defined_error():
    backend = DockerBackend(image_ref=_closeout_image())
    ghost = SandboxHandle(handle_id="docker-never-created", request_id="r", backend_name="docker", state=SandboxState.PENDING)
    request = SandboxRequest(command=("true",), policy=SandboxPolicy(workspace_dir="/tmp/unused"))
    with pytest.raises(DockerBackendError):
        await backend.run(ghost, request)


@_needs_docker
@pytest.mark.asyncio
async def test_d6_double_run_is_a_defined_error_not_a_second_execution(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("sh", "-c", "echo x >> /workspace/count"),
                             policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    try:
        await backend.run(handle, request)
        with pytest.raises(DockerBackendError):
            await backend.run(handle, request)
        assert (tmp_path / "count").read_text().count("x") == 1, "the command was executed a second time"
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_d6_cancel_before_run_is_a_no_op_that_does_not_taint_the_later_run(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("echo", "hi"), policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    try:
        await backend.cancel(handle)  # nothing is running: must not raise, must not linger as a flag
        result = await backend.run(handle, request)
        assert result.termination_reason == TerminationReason.COMPLETED, "a run that finished normally was reported as cancelled"
        assert "hi" in result.stdout
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_d6_cancel_after_terminate_is_a_no_op(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("true",), policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    try:
        await backend.run(handle, request)
        await backend.cancel(handle)  # must not raise
        assert await backend.inspect(handle) == SandboxState.TERMINATED  # and must not change the state
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_d6_inspect_after_destroy_reports_a_defined_sandbox_state(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("true",), policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    await backend.destroy(handle)
    state = await backend.inspect(handle)
    assert isinstance(state, SandboxState)  # a contract enum member, never a raw docker string
    assert state == SandboxState.PENDING  # unknown-handle behavior, same shape as NamespaceBackend


# ---- D7 / D8, strengthened evidence -----------------------------------


@_needs_docker
@pytest.mark.asyncio
async def test_d7_cancel_reaches_a_grandchild_that_was_provably_alive_before(tmp_path):
    """The older heartbeat test compares two readings taken AFTER cancel, so
    it also passes if the grandchild never started (None == None). This one
    first proves the grandchild was alive and advancing, then that it stopped."""
    backend = DockerBackend(image_ref=_closeout_image())
    script = f"(sh -c '{_HEARTBEAT_LOOP}' &); sleep 30"
    request = SandboxRequest(command=("sh", "-c", script), policy=SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30))
    handle = await backend.create(request)
    container_id = backend._handles[handle.handle_id].container_id
    hb = tmp_path / "heartbeat"
    try:
        run_task = asyncio.ensure_future(backend.run(handle, request))
        for _ in range(300):  # wait for the grandchild itself, not for a guessed start latency
            if hb.exists() and hb.read_text().strip():
                break
            await asyncio.sleep(0.05)
        before_1 = hb.read_text().strip() if hb.exists() else ""
        await asyncio.sleep(0.6)
        before_2 = hb.read_text().strip() if hb.exists() else ""
        assert before_1 and before_2 and before_1 != before_2, "vacuous: the grandchild was not alive and advancing before cancel()"
        await backend.cancel(handle)
        await asyncio.wait_for(run_task, timeout=15)
        after_1 = hb.read_text().strip()
        await asyncio.sleep(1.0)
        assert hb.read_text().strip() == after_1, "a descendant kept writing after cancel() returned"
        running = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", container_id],
                                 capture_output=True, text=True)
        assert running.stdout.strip() == "false"
    finally:
        await backend.destroy(handle)


@_needs_docker
@pytest.mark.asyncio
async def test_d8_inspect_never_touches_the_container_itself(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("true",), policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    cid = backend._handles[handle.handle_id].container_id
    try:
        def docker_view() -> tuple:
            st = _inspect_container(cid)["State"]
            return (st["Status"], st["StartedAt"], st["FinishedAt"], _inspect_container(cid)["RestartCount"])

        created = docker_view()
        assert created[0] == "created"
        for _ in range(5):
            await backend.inspect(handle)
        assert docker_view() == created  # a created container is still created, never started
        await backend.run(handle, request)
        finished = docker_view()
        assert finished[0] == "exited"
        for _ in range(5):
            await backend.inspect(handle)
        assert docker_view() == finished  # an exited container is still exited, never restarted
    finally:
        await backend.destroy(handle)


# ---- A4 / A5: effective state inside the container ---------------------


@_needs_docker
@pytest.mark.asyncio
async def test_a4_host_only_env_var_is_absent_and_request_env_is_present_in_the_container(tmp_path, monkeypatch):
    monkeypatch.setenv("OCBRAIN_HOST_ONLY_A4", "leak-me")
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(
        command=("printenv",),
        env={"OCBRAIN_REQ_A4": "visible"},
        policy=SandboxPolicy(workspace_dir=str(tmp_path)),
    )
    handle = await backend.create(request)
    try:
        out = (await backend.run(handle, request)).stdout
    finally:
        await backend.destroy(handle)
    assert "OCBRAIN_HOST_ONLY_A4" not in out and "leak-me" not in out  # no host-process env var reached the container
    assert "OCBRAIN_REQ_A4=visible" in out  # what the request asked for did


@_needs_docker
@pytest.mark.asyncio
async def test_a5_a_restrictive_allowed_imports_value_still_runs_unimpeded(tmp_path):
    """Documents A5's chosen option (a): DockerBackend, like NamespaceBackend,
    does NOT enforce `allowed_imports`. A documentation test, not a security
    property: it would start failing only if someone added Docker-only import
    filtering, which is exactly the second policy surface A5/B3 forbid."""
    backend = DockerBackend(image_ref=_closeout_image())
    policy = SandboxPolicy(workspace_dir=str(tmp_path), allowed_imports=("json",))
    request = SandboxRequest(command=("python3", "-c", "import socket, os, sys; print('imports-ok')"), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
    finally:
        await backend.destroy(handle)
    assert "imports-ok" in result.stdout


# ======================================================================
# D11 (reconciliation §19): the record and the lock.
#
# Checklist D11's invariant: "no interleaving produces two internal
# records for one handle, OR A CONTAINER WITH NONE"; its forbidden
# shortcut: "a lock so coarse it serializes unrelated sandboxes, or no
# lock at all". The earlier D11 tests fire the named pairs and pass, but
# they never widen the window inside destroy(), so they could not see
# that destroy() removed the handle's record BEFORE awaiting the
# container's removal. These tests widen that window deterministically
# (the real `docker rm`, just delayed) and assert the invariant directly.
# ======================================================================


def _slow_rm_of(container_name, delay):
    return lambda argv: _docker_cmd("rm")(argv) and container_name in argv


async def _created_and_run(backend, tmp_path, name="ws"):
    request = SandboxRequest(command=("true",), policy=SandboxPolicy(workspace_dir=str(tmp_path / name)))
    handle = await backend.create(request)
    await backend.run(handle, request)
    return handle, backend._handles[handle.handle_id]


@_needs_docker
@pytest.mark.asyncio
async def test_d11_a_container_always_has_a_record_while_destroy_is_in_flight(tmp_path, monkeypatch):
    backend = DockerBackend(image_ref=_closeout_image())
    handle, state = await _created_and_run(backend, tmp_path)
    inj = _DockerFailureInjector(monkeypatch, _slow_rm_of(state.container_name, 0.8), "slow", delay=0.8)
    task = asyncio.ensure_future(backend.destroy(handle))
    await asyncio.sleep(0.3)  # the removal is now in flight
    assert inj.hits >= 1
    assert state.container_id in _d10_snapshot()["containers"]  # the container still exists ...
    assert handle.handle_id in backend._handles, "a container with no internal record"  # ... so its record must too
    assert await backend.inspect(handle) == SandboxState.TERMINATED  # and inspect() must still see the real state
    await task
    assert handle.handle_id not in backend._handles
    assert state.container_id not in _d10_snapshot()["containers"]


@_needs_docker
@pytest.mark.asyncio
async def test_d11_a_second_destroy_does_not_return_until_the_container_is_gone(tmp_path, monkeypatch):
    backend = DockerBackend(image_ref=_closeout_image())
    handle, state = await _created_and_run(backend, tmp_path)
    _DockerFailureInjector(monkeypatch, _slow_rm_of(state.container_name, 0.8), "slow", delay=0.8)
    first = asyncio.ensure_future(backend.destroy(handle))
    await asyncio.sleep(0.2)
    await backend.destroy(handle)  # the second caller
    assert state.container_id not in _d10_snapshot()["containers"], "destroy() returned while the removal was still in flight"
    await first


@_needs_docker
@pytest.mark.asyncio
async def test_d11_concurrent_destroys_under_failure_report_failure_to_every_caller(tmp_path, monkeypatch):
    before = _d10_snapshot()
    backend = DockerBackend(image_ref=_closeout_image())
    handle, state = await _created_and_run(backend, tmp_path)
    inj = _DockerFailureInjector(monkeypatch, _any_docker, "spawn_error", delay=0.3)
    results = await asyncio.gather(backend.destroy(handle), backend.destroy(handle), return_exceptions=True)
    assert inj.hits >= 1
    assert all(isinstance(r, DockerBackendError) for r in results), f"a caller was told success while removal had failed: {results}"
    assert handle.handle_id in backend._handles  # retained, so a retry is possible
    inj.active = False
    await backend.destroy(handle)
    assert backend._handles == {}
    _assert_nothing_leaked(before)


@_needs_docker
@pytest.mark.asyncio
async def test_d11_concurrent_destroys_on_one_handle_are_serialized_not_repeated(tmp_path, monkeypatch):
    backend = DockerBackend(image_ref=_closeout_image())
    handle, state = await _created_and_run(backend, tmp_path)
    inj = _DockerFailureInjector(monkeypatch, _slow_rm_of(state.container_name, 0.6), "slow", delay=0.6)
    await asyncio.gather(backend.destroy(handle), backend.destroy(handle))
    assert inj.hits == 1, "the second destroy() repeated the removal instead of observing the first one's completion"
    assert backend._handles == {}


@_needs_docker
@pytest.mark.asyncio
async def test_d11_destroying_one_sandbox_does_not_wait_for_another(tmp_path, monkeypatch):
    """The other half of the forbidden shortcut: a lock so coarse that it
    serializes unrelated sandboxes."""
    backend = DockerBackend(image_ref=_closeout_image())
    handle_a, state_a = await _created_and_run(backend, tmp_path, "a")
    handle_b, _ = await _created_and_run(backend, tmp_path, "b")
    _DockerFailureInjector(monkeypatch, _slow_rm_of(state_a.container_name, 1.5), "slow", delay=1.5)
    slow = asyncio.ensure_future(backend.destroy(handle_a))
    await asyncio.sleep(0.2)
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    await backend.destroy(handle_b)
    assert loop.time() - t0 < 1.0, "destroying B waited on A's removal"
    await slow


@_needs_docker
@pytest.mark.asyncio
async def test_d11_two_concurrent_runs_on_one_handle_execute_exactly_once(tmp_path):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("sh", "-c", "echo x >> /workspace/count"),
                             policy=SandboxPolicy(workspace_dir=str(tmp_path)))
    handle = await backend.create(request)
    try:
        results = await asyncio.gather(backend.run(handle, request), backend.run(handle, request), return_exceptions=True)
        assert len([r for r in results if isinstance(r, DockerBackendError)]) == 1, results
        assert (tmp_path / "count").read_text().count("x") == 1
    finally:
        await backend.destroy(handle)


# ======================================================================
# D7 / D11 (reconciliation §19.2): a cancel() that lands while `docker
# start` is still in flight.
#
# Intended state machine. The public SandboxState is fixed by D12
# (PENDING, PROVISIONING, RUNNING, TERMINATED), so "starting" and
# "cancelling" can only be PRIVATE phases of RUNNING:
#   PROVISIONING --run()--> RUNNING [start in flight -> container running]
#                           --exit or kill--> TERMINATED
# cancel() on a RUNNING handle must (a) not block on the start, (b) record
# intent, and (c) guarantee the workload cannot run to completion: the
# container is killed as soon as it is running and run() ends CANCELLED.
# cancel() is NOT serialized behind start (that would reintroduce the
# coarse serialization D11 forbids); run() owns enforcement.
# ======================================================================


def _container_status(container_id: str) -> str:
    return _inspect_container(container_id)["State"]["Status"]


@_needs_docker
@pytest.mark.asyncio
async def test_d7_cancel_during_an_in_flight_start_cannot_be_escaped_by_the_workload(tmp_path, monkeypatch):
    backend = DockerBackend(image_ref=_closeout_image())
    request = SandboxRequest(command=("sleep", "30"), policy=SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=30))
    handle = await backend.create(request)
    cid = backend._handles[handle.handle_id].container_id
    start = _DockerFailureInjector(monkeypatch, _docker_cmd("start"), "slow", delay=1.5)  # the real start, 1.5s late
    kill = _DockerFailureInjector(monkeypatch, _docker_cmd("kill"), "slow")  # pass-through, counts kill attempts
    loop = asyncio.get_running_loop()
    try:
        run_task = asyncio.ensure_future(backend.run(handle, request))
        for _ in range(40):  # fact 1: `docker start` is blocked before completion ...
            if start.hits:
                break
            await asyncio.sleep(0.05)
        assert start.hits >= 1 and not run_task.done()
        assert _container_status(cid) == "created"  # ... and the container has not started

        t0 = loop.time()
        await backend.cancel(handle)  # fact 2: cancel() is invoked during the blocked interval
        assert loop.time() - t0 < 1.0, "cancel() blocked on the in-flight start"  # not serialized behind it
        assert kill.hits >= 1 and not run_task.done()  # fact 3: the cancel path ran while start was still pending,
        assert _container_status(cid) == "created"  # against a container that had not started

        await asyncio.sleep(1.5 + 1.0)  # let the start complete, with margin
        running = _inspect_container(cid)["State"]["Running"]
        # facts 4 and 5: on the unfixed code the start completes afterwards and the workload is running
        assert running is False, "the start completed after cancel() and the workload is still running"

        result = await asyncio.wait_for(run_task, timeout=10)  # fact 6: what the contract promises
        assert result.termination_reason == TerminationReason.CANCELLED
        assert result.exit_code == 137  # it was killed, not allowed to finish
        assert await backend.inspect(handle) == SandboxState.TERMINATED
    finally:
        await backend.destroy(handle)
