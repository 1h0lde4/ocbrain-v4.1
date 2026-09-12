"""tests/core/sandbox/test_contracts.py — Sandbox Fabric Phase 1, contracts.

Architecture Sources:
    core/sandbox/contracts.py
    docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md

Coverage:
    - SandboxPolicy fail-closed __post_init__ validation (empty workspace,
      non-positive timeout/memory/pids)
    - SandboxRequest fail-closed __post_init__ validation, specifically
      rejecting a shell-string command (the "A7 audit" bug class)
    - SandboxHandle.with_state() returns a new instance (frozen, no
      in-place mutation) with the original left untouched
    - RuntimeCapabilities.supports() / supports_all()
    - SandboxResult.succeeded is exit_code == 0 AND COMPLETED, not either
      alone
"""
import pytest

from core.sandbox.contracts import (
    ArtifactManifest,
    RuntimeCapabilities,
    SandboxCapability,
    SandboxHandle,
    SandboxPolicy,
    SandboxRequest,
    SandboxResult,
    SandboxState,
    TerminationReason,
)


def _policy(**overrides) -> SandboxPolicy:
    defaults = dict(workspace_dir="/tmp/ws")
    defaults.update(overrides)
    return SandboxPolicy(**defaults)


def test_policy_rejects_empty_workspace():
    with pytest.raises(ValueError, match="workspace_dir"):
        SandboxPolicy(workspace_dir="")


@pytest.mark.parametrize(
    "field_name,value",
    [("timeout_sec", 0), ("timeout_sec", -1), ("memory_limit_mb", 0), ("max_pids", 0)],
)
def test_policy_rejects_non_positive_limits(field_name, value):
    with pytest.raises(ValueError):
        _policy(**{field_name: value})


def test_policy_accepts_sane_defaults():
    p = _policy()
    assert p.timeout_sec == 30.0
    assert p.memory_limit_mb == 256


def test_request_rejects_shell_string_command():
    """The A7-audit bug class: a bare string is iterable-of-characters,
    not argv. Must fail loudly, not silently produce garbage argv."""
    with pytest.raises(ValueError, match="argv sequence"):
        SandboxRequest(command="echo hello", policy=_policy())


def test_request_rejects_empty_command():
    with pytest.raises(ValueError, match="must not be empty"):
        SandboxRequest(command=(), policy=_policy())


def test_request_rejects_non_str_command_entries():
    with pytest.raises(ValueError, match="must all be str"):
        SandboxRequest(command=("echo", 5), policy=_policy())


def test_request_accepts_argv_tuple():
    req = SandboxRequest(command=("echo", "hello"), policy=_policy())
    assert req.command == ("echo", "hello")
    assert req.request_id  # auto-generated


def test_handle_with_state_is_non_mutating():
    h1 = SandboxHandle(handle_id="a", request_id="r", backend_name="stub")
    assert h1.state is SandboxState.PENDING
    h2 = h1.with_state(SandboxState.RUNNING)
    assert h2.state is SandboxState.RUNNING
    assert h1.state is SandboxState.PENDING  # original untouched
    assert h1 is not h2


def test_runtime_capabilities_supports():
    caps = RuntimeCapabilities(
        backend_name="x",
        supported=frozenset({SandboxCapability.CGROUP_MEMORY, SandboxCapability.FILESYSTEM_JAIL}),
    )
    assert caps.supports(SandboxCapability.CGROUP_MEMORY)
    assert not caps.supports(SandboxCapability.NET_NAMESPACE)
    assert caps.supports_all(SandboxCapability.CGROUP_MEMORY, SandboxCapability.FILESYSTEM_JAIL)
    assert not caps.supports_all(SandboxCapability.CGROUP_MEMORY, SandboxCapability.NET_NAMESPACE)


def test_empty_runtime_capabilities_supports_nothing():
    caps = RuntimeCapabilities(backend_name="stub")
    assert not caps.supports(SandboxCapability.FILESYSTEM_JAIL)


@pytest.mark.parametrize(
    "exit_code,reason,expected",
    [
        (0, TerminationReason.COMPLETED, True),
        (1, TerminationReason.COMPLETED, False),
        (0, TerminationReason.TIMEOUT, False),
        (None, TerminationReason.RESOURCE_EXCEEDED, False),
    ],
)
def test_result_succeeded(exit_code, reason, expected):
    result = SandboxResult(
        handle_id="h",
        exit_code=exit_code,
        stdout="",
        stderr="",
        termination_reason=reason,
        duration_sec=0.1,
    )
    assert result.succeeded is expected


def test_artifact_manifest_len():
    manifest = ArtifactManifest(files=(("a.txt", "deadbeef", 4),))
    assert len(manifest) == 1
    assert len(ArtifactManifest()) == 0
