"""tests/core/sandbox/test_admission.py — Sandbox Fabric Phase 1, AdmissionGate.

Architecture Sources:
    core/sandbox/admission.py
    docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md
        §3 (AdmissionGate naming decision)

Coverage:
    - StubBackend's empty capability set is rejected outright (structural
      enforcement that the stub can never be mistaken for a real backend)
    - NamespaceBackend's full capability set is admitted for an ordinary
      deny-all-network request
    - NamespaceBackend now also admits a request naming allowed_hosts
      (DEBT-023 closure — it has NETWORK_ALLOWLIST)
    - A backend with NET_NAMESPACE but NOT the specific NETWORK_ALLOWLIST
      capability is still rejected for a policy naming allowed_hosts —
      the check is precise about which capability it needs, not "any
      network isolation at all"
"""
from core.sandbox.admission import check_admission
from core.sandbox.backends.namespace_backend import _CAPS as NAMESPACE_CAPS
from core.sandbox.backends.stub_backend import _CAPS as STUB_CAPS
from core.sandbox.contracts import RuntimeCapabilities, SandboxCapability, SandboxPolicy, SandboxRequest


def _request(**policy_overrides) -> SandboxRequest:
    policy = SandboxPolicy(workspace_dir="/tmp/ws", **policy_overrides)
    return SandboxRequest(command=("echo", "hi"), policy=policy)


def test_stub_backend_capabilities_are_rejected():
    decision = check_admission(_request(), STUB_CAPS)
    assert decision.allowed is False
    assert "filesystem jail" in decision.reason


def test_namespace_backend_admits_deny_all_network_request():
    decision = check_admission(_request(), NAMESPACE_CAPS)
    assert decision.allowed is True


def test_namespace_backend_admits_allowed_hosts_request():
    """DEBT-023: NamespaceBackend now genuinely enforces this via
    _net_proxy.py, so AdmissionGate should let it through."""
    decision = check_admission(_request(allowed_hosts=("pypi.org",)), NAMESPACE_CAPS)
    assert decision.allowed is True


def test_allowed_hosts_rejected_without_the_specific_capability():
    """A backend that isolates the network (NET_NAMESPACE) but does not
    specifically claim NETWORK_ALLOWLIST must still be rejected for a
    policy naming allowed_hosts — precise capability gating, not "any
    network isolation counts"."""
    partial_caps = RuntimeCapabilities(
        backend_name="hypothetical-deny-all-only",
        supported=frozenset(
            {
                SandboxCapability.FILESYSTEM_JAIL,
                SandboxCapability.CGROUP_MEMORY,
                SandboxCapability.CGROUP_PIDS,
                SandboxCapability.NET_NAMESPACE,
            }
        ),
    )
    decision = check_admission(_request(allowed_hosts=("pypi.org",)), partial_caps)
    assert decision.allowed is False
    assert "allowed_hosts" in decision.reason

