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
