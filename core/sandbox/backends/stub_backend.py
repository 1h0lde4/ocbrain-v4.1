"""core/sandbox/backends/stub_backend.py — minimal in-process stub backend.

The source report (§13, point 3) explicitly anticipates needing "un stub
minimal ... pour tests d'interface". This is that stub.

It runs commands via subprocess in the CURRENT namespace with NO isolation
whatsoever, and must never be selected for untrusted code (PI LAW 3). This
is enforced structurally, not just by convention: its `capabilities`
claims ZERO SandboxCapability values, so AdmissionGate.check_admission()
rejects every real request against it (see tests) -- the only thing this
backend is actually admissible for is testing the contract/interface layer
and backend-selection logic itself.
"""
import asyncio
import time

from core.sandbox.backend import SandboxBackend
from core.sandbox.contracts import (
    RuntimeCapabilities,
    SandboxHandle,
    SandboxRequest,
    SandboxResult,
    SandboxState,
    TerminationReason,
)

_CAPS = RuntimeCapabilities(backend_name="stub", supported=frozenset())


class StubBackend(SandboxBackend):
    def __init__(self) -> None:
        self._states: dict[str, SandboxState] = {}

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return _CAPS

    async def create(self, request: SandboxRequest) -> SandboxHandle:
        handle = SandboxHandle(
            handle_id=f"stub-{request.request_id}",
            request_id=request.request_id,
            backend_name="stub",
            state=SandboxState.PROVISIONING,
        )
        self._states[handle.handle_id] = handle.state
        return handle

    async def run(self, handle: SandboxHandle, request: SandboxRequest) -> SandboxResult:
        self._states[handle.handle_id] = SandboxState.RUNNING
        started = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *request.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=request.policy.timeout_sec
                )
                reason = TerminationReason.COMPLETED
                exit_code = proc.returncode
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout, stderr = b"", b"sandbox timed out"
                reason = TerminationReason.TIMEOUT
                exit_code = None
        finally:
            self._states[handle.handle_id] = SandboxState.TERMINATED

        return SandboxResult(
            handle_id=handle.handle_id,
            exit_code=exit_code,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            termination_reason=reason,
            duration_sec=time.monotonic() - started,
        )

    async def cancel(self, handle: SandboxHandle) -> None:
        self._states[handle.handle_id] = SandboxState.TERMINATED

    async def destroy(self, handle: SandboxHandle) -> None:
        self._states.pop(handle.handle_id, None)

    async def inspect(self, handle: SandboxHandle) -> SandboxState:
        return self._states.get(handle.handle_id, SandboxState.PENDING)
