"""tests/core/sandbox/test_stub_backend.py — Sandbox Fabric Phase 1, StubBackend.

Architecture Sources:
    core/sandbox/backends/stub_backend.py

Coverage:
    - Full lifecycle (create -> run -> inspect -> destroy) with no real
      isolation, used for interface-contract tests
    - Timeout path returns TerminationReason.TIMEOUT, not an exception
    - capabilities is genuinely empty (see test_admission.py for the
      corresponding rejection)
"""
import pytest

from core.sandbox.backends.stub_backend import StubBackend
from core.sandbox.contracts import SandboxPolicy, SandboxRequest, SandboxState, TerminationReason


@pytest.mark.asyncio
async def test_echo_hello_completes(tmp_path):
    backend = StubBackend()
    policy = SandboxPolicy(workspace_dir=str(tmp_path))
    request = SandboxRequest(command=("echo", "Hello"), policy=policy)

    handle = await backend.create(request)
    assert await backend.inspect(handle) == SandboxState.PROVISIONING

    result = await backend.run(handle, request)
    assert result.succeeded
    assert result.stdout.strip() == "Hello"
    assert await backend.inspect(handle) == SandboxState.TERMINATED

    await backend.destroy(handle)
    assert await backend.inspect(handle) == SandboxState.PENDING


@pytest.mark.asyncio
async def test_timeout_is_reported_not_raised(tmp_path):
    backend = StubBackend()
    policy = SandboxPolicy(workspace_dir=str(tmp_path), timeout_sec=0.2)
    request = SandboxRequest(command=("sleep", "5"), policy=policy)

    handle = await backend.create(request)
    result = await backend.run(handle, request)

    assert result.termination_reason == TerminationReason.TIMEOUT
    assert result.exit_code is None


@pytest.mark.asyncio
async def test_capabilities_are_empty():
    backend = StubBackend()
    assert backend.capabilities.supported == frozenset()
