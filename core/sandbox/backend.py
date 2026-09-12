"""core/sandbox/backend.py — SandboxBackend abstract interface (Phase 1).

Architecture references:
    docs/research/sandbox-execution-fabric/deep-research-report.md §13
        point 3 ("classe Runtime avec methods create/exec/poll/stop/
        destroy/inspect")
    docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md
        §3 -- named SandboxBackend, not bare "Runtime": core/runtime/
        already has ExecutionRuntime and (separately) WorkflowRuntime.

Every backend must:
    - report its RuntimeCapabilities so AdmissionGate (core/sandbox/
      admission.py) can reject requests the backend cannot actually
      enforce, rather than silently degrading isolation (PI LAW 3).
    - create() a sandbox from a SandboxRequest.
    - run() the request's command inside it to completion, returning a
      SandboxResult (Phase 1 collapses the report's separate exec/poll
      into one awaited call; streaming/poll-based execution is a
      candidate Phase 2 addition once a real consumer exists).
    - cancel() a running sandbox such that no descendant process survives
      (see namespace_backend.py's process-group kill for how this is
      verified empirically, not just asserted).
    - destroy() unconditionally, even after a failed run, so nothing
      leaks (cgroups, temp workspaces).
    - inspect() the current state without side effects.
"""
from abc import ABC, abstractmethod

from core.sandbox.contracts import (
    RuntimeCapabilities,
    SandboxHandle,
    SandboxRequest,
    SandboxResult,
    SandboxState,
)


class SandboxBackend(ABC):
    """Abstract backend for provisioning and running one sandboxed command."""

    @property
    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        """What this backend actually enforces. Must not overclaim --
        AdmissionGate trusts this to decide whether a request is safe to
        run here at all."""

    @abstractmethod
    async def create(self, request: SandboxRequest) -> SandboxHandle:
        """Provision (but do not yet run) a sandbox for this request."""

    @abstractmethod
    async def run(self, handle: SandboxHandle, request: SandboxRequest) -> SandboxResult:
        """Run the request's command to completion (or timeout/cancel)."""

    @abstractmethod
    async def cancel(self, handle: SandboxHandle) -> None:
        """Kill a running sandbox and every descendant process. Idempotent."""

    @abstractmethod
    async def destroy(self, handle: SandboxHandle) -> None:
        """Release all resources (cgroups, temp dirs) for this handle.
        Must be safe to call even if create()/run() partially failed."""

    @abstractmethod
    async def inspect(self, handle: SandboxHandle) -> SandboxState:
        """Return the current state without side effects."""
