"""core/sandbox/contracts.py — Sandbox/Execution Fabric contracts (Phase 1).

Architecture references:
    docs/research/sandbox-execution-fabric/deep-research-report.md §4
        (schema definitions this module implements, under corrected naming)
    docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md
        §3 (naming decisions: Sandbox* prefix, not Execution* --
        core/runtime/ already owns Execution* for workflow-node
        orchestration, an unrelated concern)
    PI LAW 2 — Event Sourcing Over Hidden State
    PI LAW 3 — Isolation Over Convenience
    PI LAW 4 — Determinism Over Magic
    PI §14.1 — Sandboxing Rules (memory limits, timeouts, filesystem
        restrictions, import whitelists, network restrictions)

Design:
    - Frozen dataclasses throughout. State transitions go through
      dataclasses.replace() (see SandboxHandle.with_state), mirroring the
      Verification subsystem's Rubric lock-state pattern -- never
      in-place mutation.
    - Fail-closed __post_init__ validation: a malformed policy or request
      raises at construction time rather than surfacing as a confusing
      failure deep inside a backend.
    - Plain dict is used for a couple of fields (SandboxRequest.env,
      SandboxEvent.detail) despite frozen=True -- this mirrors
      core/events/event_stream.py's own StreamEvent.payload field exactly
      (verified by reading that file directly), not a shortcut taken here.
    - RuntimeCapabilities is a compositional frozenset, not a single
      exclusive enum: a backend can genuinely support more than one
      isolation primitive at once, and AdmissionGate (core/sandbox/
      admission.py) needs to check for specific primitives independently.
"""
from __future__ import annotations

import dataclasses
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SandboxCapability(Enum):
    """A single isolation primitive a backend may support."""

    USER_NAMESPACE = "user_namespace"
    MOUNT_NAMESPACE = "mount_namespace"
    PID_NAMESPACE = "pid_namespace"
    NET_NAMESPACE = "net_namespace"
    CGROUP_MEMORY = "cgroup_memory"
    CGROUP_PIDS = "cgroup_pids"
    NO_NEW_PRIVS = "no_new_privs"
    FILESYSTEM_JAIL = "filesystem_jail"
    NETWORK_DENY_DEFAULT = "network_deny_default"


@dataclass(frozen=True)
class RuntimeCapabilities:
    """What a given SandboxBackend actually supports, introspectable at
    runtime rather than assumed from its class name or documentation.
    """

    backend_name: str
    supported: frozenset[SandboxCapability] = field(default_factory=frozenset)

    def supports(self, capability: SandboxCapability) -> bool:
        return capability in self.supported

    def supports_all(self, *capabilities: SandboxCapability) -> bool:
        return all(c in self.supported for c in capabilities)


class TerminationReason(Enum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    RESOURCE_EXCEEDED = "resource_exceeded"
    CANCELLED = "cancelled"
    ERROR = "error"


class SandboxState(Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    TERMINATED = "terminated"


@dataclass(frozen=True)
class SandboxPolicy:
    """Resource, filesystem, and network policy for one sandbox run.

    Fail-closed: __post_init__ rejects zero/negative limits and an empty
    workspace path rather than letting a misconfigured policy reach a
    backend. Network access is deny-by-default (PI §14.1): allowed_hosts
    is empty unless explicitly populated, and Phase 1 backends are not
    required to honor a non-empty allowed_hosts yet (see AdmissionGate,
    which rejects such a policy against a backend that cannot enforce it
    rather than silently ignoring it).
    """

    workspace_dir: str
    timeout_sec: float = 30.0
    memory_limit_mb: int = 256
    max_pids: int = 64
    allowed_imports: tuple[str, ...] = field(default_factory=tuple)
    allowed_hosts: tuple[str, ...] = field(default_factory=tuple)
    read_only_paths: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.workspace_dir:
            raise ValueError("SandboxPolicy.workspace_dir must not be empty")
        if self.timeout_sec <= 0:
            raise ValueError("SandboxPolicy.timeout_sec must be > 0")
        if self.memory_limit_mb <= 0:
            raise ValueError("SandboxPolicy.memory_limit_mb must be > 0")
        if self.max_pids <= 0:
            raise ValueError("SandboxPolicy.max_pids must be > 0")


@dataclass(frozen=True)
class SandboxRequest:
    """One unit of work to run inside a sandbox.

    command is argv-list only, never a shell string -- fail-closed
    __post_init__ rejects a bare str even though str is technically
    iterable-of-characters and would otherwise silently produce garbage.
    This is a direct, deliberate echo of modules/system_ctrl/module.py's
    own "A7 audit" fix (shell=True / shell-string injection), recorded in
    the reconciliation so the same bug class isn't reintroduced here.
    """

    command: tuple[str, ...]
    policy: SandboxPolicy
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    env: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.command, str):
            raise ValueError(
                "SandboxRequest.command must be an argv sequence, not a "
                "shell string (see modules/system_ctrl 'A7 audit' history)"
            )
        if not self.command:
            raise ValueError("SandboxRequest.command must not be empty")
        if any(not isinstance(part, str) for part in self.command):
            raise ValueError("SandboxRequest.command entries must all be str")


@dataclass(frozen=True)
class SandboxHandle:
    """Opaque reference to a provisioned (possibly running) sandbox."""

    handle_id: str
    request_id: str
    backend_name: str
    state: SandboxState = SandboxState.PENDING

    def with_state(self, new_state: SandboxState) -> "SandboxHandle":
        """Single-step forward progression via dataclasses.replace --
        mirrors the Verification subsystem's Rubric lock-state pattern.
        Forward-only is enforced by callers (backends), not here; this
        method just performs the non-mutating transition itself.
        """
        return dataclasses.replace(self, state=new_state)


@dataclass(frozen=True)
class ArtifactManifest:
    """Files produced inside the sandbox, each with an integrity hash.

    Deliberately not the same type as core/cognitive/intent.py's
    CognitiveArtifact (a Protocol for a different, cognitive-layer
    concept) -- see reconciliation §2.
    """

    files: tuple[tuple[str, str, int], ...] = field(default_factory=tuple)
    # each entry: (relative_path, sha256_hex, size_bytes)

    def __len__(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class SandboxResult:
    """Structured outcome of one SandboxRequest."""

    handle_id: str
    exit_code: Optional[int]
    stdout: str
    stderr: str
    termination_reason: TerminationReason
    duration_sec: float
    artifacts: ArtifactManifest = field(default_factory=ArtifactManifest)

    @property
    def succeeded(self) -> bool:
        return (
            self.termination_reason is TerminationReason.COMPLETED
            and self.exit_code == 0
        )


class SandboxEventType(Enum):
    STARTED = "sandbox.started"
    PROVISIONED = "sandbox.provisioned"
    RESOURCE_EXCEEDED = "sandbox.resource_exceeded"
    FINISHED = "sandbox.finished"
    ERROR = "sandbox.error"


@dataclass(frozen=True)
class SandboxEvent:
    """Domain event for one sandbox lifecycle transition.

    Published through the EXISTING EventStream (core/events/
    event_stream.py) via core/sandbox/events.py -- this is deliberately
    NOT a second, parallel event bus (PI LAW 2; reconciliation §2 --
    EventStream is almost certainly what the source report's placeholder
    term "Event Backbone" was gesturing at).
    """

    event_type: SandboxEventType
    handle_id: str
    request_id: str
    timestamp: float = field(default_factory=time.time)
    detail: dict = field(default_factory=dict)
