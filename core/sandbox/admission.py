"""core/sandbox/admission.py — AdmissionGate (Phase 1).

Deny-by-default check that every SandboxRequest passes through before a
backend ever touches it.

Named AdmissionGate, not ValidationGate: core/cognitive/learning.py's
validation_gate() already gates a different concern entirely (learning /
cognitive decisions via GovernanceKernel.evaluate_action()), and reusing
that name would be confusing (reconciliation §3). No import from or
dependency on that module exists here, deliberately.
"""
from dataclasses import dataclass

from core.sandbox.contracts import RuntimeCapabilities, SandboxCapability, SandboxRequest


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    reason: str = ""


def check_admission(
    request: SandboxRequest, capabilities: RuntimeCapabilities
) -> AdmissionDecision:
    """Fail-closed: any unmet requirement is a rejection, never a warning
    or a silent downgrade (PI LAW 3 — Isolation Over Convenience).
    """
    if not capabilities.supports(SandboxCapability.FILESYSTEM_JAIL):
        return AdmissionDecision(False, "backend cannot provide a filesystem jail")

    if not capabilities.supports(SandboxCapability.CGROUP_MEMORY):
        return AdmissionDecision(False, "backend cannot enforce a memory limit")

    if not capabilities.supports(SandboxCapability.CGROUP_PIDS):
        return AdmissionDecision(False, "backend cannot enforce a process-count limit")

    if request.policy.allowed_hosts and not capabilities.supports(
        SandboxCapability.NET_NAMESPACE
    ):
        return AdmissionDecision(
            False, "policy names allowed_hosts but backend cannot isolate network at all"
        )

    if request.policy.allowed_hosts and not capabilities.supports(
        SandboxCapability.NETWORK_ALLOWLIST
    ):
        return AdmissionDecision(
            False,
            "policy names allowed_hosts, which this backend does not enforce "
            "(it only supports deny-all network policy)",
        )

    return AdmissionDecision(True)
