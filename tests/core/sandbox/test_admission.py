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
    - A policy naming allowed_hosts is rejected even against a backend
      that supports NET_NAMESPACE, because no Phase 1 backend enforces an
      allowlist yet (fail-closed, not silently ignored)
"""
from core.sandbox.admission import check_admission
from core.sandbox.backends.namespace_backend import _CAPS as NAMESPACE_CAPS
from core.sandbox.backends.stub_backend import _CAPS as STUB_CAPS
from core.sandbox.contracts import SandboxPolicy, SandboxRequest


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


def test_allowed_hosts_rejected_even_with_net_namespace_support():
    decision = check_admission(_request(allowed_hosts=("pypi.org",)), NAMESPACE_CAPS)
    assert decision.allowed is False
    assert "allowed_hosts" in decision.reason
