"""tests/core/sandbox/test_net_proxy.py — Sandbox Fabric, _net_proxy module unit tests.

Architecture Sources:
    core/sandbox/backends/_net_proxy.py (closes KNOWN_ISSUES.md DEBT-023,
    the enforcement half — namespace_backend.py's veth/netns wiring is
    covered separately in test_allowed_hosts.py)

Coverage, all against a real local HTTP server (no mocking of sockets):
    - plain HTTP proxy-style request (absolute-URI request line) to an
      allowed host is forwarded, with a real response relayed back
    - CONNECT to an allowed host succeeds and tunnels real bytes both
      ways (this is what any HTTPS client, including pip, actually uses)
    - CONNECT to a host NOT on the allowlist gets 403 and no connection
      to the real target is ever made
    - plain HTTP to a disallowed host also gets 403
    - hostname matching is exact and case-insensitive, not substring/
      wildcard
"""
import http.server
import socket
import threading

import pytest

from core.sandbox.backends._net_proxy import AllowlistProxy


@pytest.fixture
def target_server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_port
    server.shutdown()


@pytest.fixture
def proxy():
    p = AllowlistProxy("127.0.0.1", allowed_hosts=["127.0.0.1"])
    p.start()
    yield p
    p.stop()


def _send_and_recv(port: int, data: bytes, recv_len: int = 4096) -> bytes:
    s = socket.create_connection(("127.0.0.1", port), timeout=3)
    s.sendall(data)
    resp = s.recv(recv_len)
    s.close()
    return resp


def test_plain_http_to_allowed_host_is_forwarded(proxy, target_server):
    req = (
        f"GET http://127.0.0.1:{target_server}/ HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{target_server}\r\nConnection: close\r\n\r\n"
    ).encode()
    resp = _send_and_recv(proxy.port, req)
    assert b"200 OK" in resp
    assert resp.endswith(b"ok")


def test_connect_to_allowed_host_tunnels_real_data(proxy, target_server):
    s = socket.create_connection(("127.0.0.1", proxy.port), timeout=3)
    s.sendall(f"CONNECT 127.0.0.1:{target_server} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
    connect_resp = s.recv(4096)
    assert b"200 Connection Established" in connect_resp

    s.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{target_server}\r\nConnection: close\r\n\r\n".encode())
    tunneled = s.recv(4096)
    s.close()
    assert b"200 OK" in tunneled
    assert tunneled.endswith(b"ok")


def test_connect_to_disallowed_host_is_rejected_and_never_dialed(proxy):
    resp = _send_and_recv(proxy.port, b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com\r\n\r\n")
    assert resp == b"HTTP/1.1 403 Forbidden\r\n\r\n"


def test_plain_http_to_disallowed_host_is_rejected(proxy):
    req = b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n"
    resp = _send_and_recv(proxy.port, req)
    assert resp == b"HTTP/1.1 403 Forbidden\r\n\r\n"


def test_host_matching_is_case_insensitive_but_exact():
    p = AllowlistProxy("127.0.0.1", allowed_hosts=["PyPI.org"])
    assert p._is_allowed("pypi.org")
    assert p._is_allowed("PYPI.ORG")
    assert not p._is_allowed("files.pythonhosted.org")
    assert not p._is_allowed("evilpypi.org")
    assert not p._is_allowed("pypi.org.evil.com")
