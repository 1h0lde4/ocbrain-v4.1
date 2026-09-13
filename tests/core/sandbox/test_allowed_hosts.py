"""tests/core/sandbox/test_allowed_hosts.py — Sandbox Fabric, DEBT-023
integration tests (NamespaceBackend + veth/netns + AllowlistProxy, end to
end).

Architecture Sources:
    core/sandbox/backends/namespace_backend.py (_setup_allowlisted_network,
    the conditional argv/env construction in _run_sync)
    core/sandbox/backends/_net_proxy.py (the enforcement itself, unit-
    tested separately in test_net_proxy.py)
    docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md
        §7 addendum (DEBT-023 closure)

Coverage:
    - a sandboxed process, with a real local server's host in
      allowed_hosts, reaches it through the proxy and gets a real
      response -- HTTP_PROXY/HTTPS_PROXY are respected automatically by
      Python's own urllib, exercising the actual env-var wiring, not a
      hand-rolled client
    - the SAME sandboxed process, with a DIFFERENT host in allowed_hosts
      (i.e. the real target is not on the list), is rejected
    - the deny-all path (empty allowed_hosts) is unaffected by any of
      this -- still no route out at all
    - destroy() leaves no netns, veth interface, or proxy process behind
"""
import http.server
import os
import socket
import subprocess
import threading

import pytest

from core.sandbox.backends.namespace_backend import NamespaceBackend
from core.sandbox.contracts import SandboxPolicy, SandboxRequest, TerminationReason


def _namespaces_available() -> bool:
    try:
        r = subprocess.run(
            ["unshare", "--user", "--map-root-user", "--net", "--fork", "--", "true"],
            capture_output=True,
            timeout=5,
        )
        ip_ok = subprocess.run(["ip", "netns", "list"], capture_output=True, timeout=5).returncode == 0
        return (
            r.returncode == 0
            and ip_ok
            and os.path.isdir("/sys/fs/cgroup/memory")
            and os.access("/sys/fs/cgroup/memory", os.W_OK)
        )
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _namespaces_available(), reason="requires unshare + iproute2 + a writable cgroup v1 memory controller"
)


@pytest.fixture
def backend():
    return NamespaceBackend()


@pytest.fixture
def workspace(tmp_path):
    d = tmp_path / "ws"
    d.mkdir()
    return str(d)


@pytest.fixture
def target_server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"hello from allowed host"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_port
    server.shutdown()


def _fetch_code(url: str) -> str:
    return (
        "import urllib.request, sys\n"
        f"try:\n"
        f"    with urllib.request.urlopen({url!r}, timeout=8) as resp:\n"
        "        sys.stdout.write(resp.read().decode())\n"
        "except Exception as e:\n"
        "    sys.stderr.write(f'FETCH_FAILED: {e}')\n"
        "    sys.exit(1)\n"
    )


@pytest.mark.asyncio
async def test_allowed_host_is_reachable_through_the_proxy(backend, workspace, target_server):
    policy = SandboxPolicy(
        workspace_dir=workspace, timeout_sec=15, allowed_hosts=("127.0.0.1",)
    )
    url = f"http://127.0.0.1:{target_server}/"
    request = SandboxRequest(command=("python3", "-c", _fetch_code(url)), policy=policy)
    handle = await backend.create(request)
    try:
        state = backend._handles[handle.handle_id]
        assert state.netns_name is not None, "allowlisted network setup did not run"
        assert state.proxy is not None and state.proxy.port

        result = await backend.run(handle, request)
        assert result.exit_code == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        assert result.stdout == "hello from allowed host"
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_host_not_on_the_allowlist_is_rejected(backend, workspace, target_server):
    """allowed_hosts names a DIFFERENT host than the one actually being
    fetched -- the real target must still be reachable at the network
    level (it's the same local server), but the proxy's allowlist check
    must reject it anyway."""
    policy = SandboxPolicy(
        workspace_dir=workspace, timeout_sec=15, allowed_hosts=("some-other-host.invalid",)
    )
    url = f"http://127.0.0.1:{target_server}/"
    request = SandboxRequest(command=("python3", "-c", _fetch_code(url)), policy=policy)
    handle = await backend.create(request)
    try:
        result = await backend.run(handle, request)
        assert result.exit_code != 0
        assert "403" in result.stderr or "FETCH_FAILED" in result.stderr
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_empty_allowed_hosts_still_has_no_route_at_all(backend, workspace):
    """Regression check: the deny-all path must be completely unaffected
    by DEBT-023's addition -- no veth, no netns, no proxy, same as
    before."""
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10)
    request = SandboxRequest(command=("echo", "hi"), policy=policy)
    handle = await backend.create(request)
    try:
        state = backend._handles[handle.handle_id]
        assert state.netns_name is None
        assert state.proxy is None
        result = await backend.run(handle, request)
        assert result.succeeded
    finally:
        await backend.destroy(handle)


@pytest.mark.asyncio
async def test_destroy_leaves_no_netns_veth_or_proxy_behind(backend, workspace, target_server):
    policy = SandboxPolicy(workspace_dir=workspace, timeout_sec=10, allowed_hosts=("127.0.0.1",))
    request = SandboxRequest(command=("echo", "hi"), policy=policy)
    handle = await backend.create(request)
    state = backend._handles[handle.handle_id]
    netns_name, veth_host, proxy = state.netns_name, state.veth_host, state.proxy

    await backend.run(handle, request)
    await backend.destroy(handle)

    ns_list = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True).stdout
    assert netns_name not in ns_list, f"{netns_name} still listed after destroy()"

    link_check = subprocess.run(["ip", "link", "show", veth_host], capture_output=True)
    assert link_check.returncode != 0, f"{veth_host} still exists after destroy()"

    assert proxy.port is not None  # sanity: it really had started
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", proxy.port), timeout=1)
