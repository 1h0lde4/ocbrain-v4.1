"""core/sandbox/backends/_net_proxy.py — allowlist-enforcing forward proxy
(closes KNOWN_ISSUES.md DEBT-023).

Runs on the HOST side (real network access) of a veth pair whose sandbox
side has no route to anywhere else -- see namespace_backend.py's
_setup_allowlisted_network(). The sandbox can reach *only* this proxy;
this proxy is the only thing that can reach the outside world on the
sandbox's behalf, and only for hostnames in SandboxPolicy.allowed_hosts.

Stdlib only, deliberately -- this is a small, auditable relay, not a
general-purpose proxy server. It understands exactly two things:

    - HTTP CONNECT (the mechanism every HTTPS client, including pip, uses
      to tunnel through a proxy): parse the target "host:port", check the
      host against the allowlist, then either relay raw bytes
      bidirectionally (TLS itself is never touched -- this proxy cannot
      and does not decrypt anything) or return 403.
    - Plain HTTP with a proxy-style absolute-URI request line (rare in
      practice now that almost everything is HTTPS, but simple to
      support correctly): parse the Host header, check it, forward or
      403.

Hostname matching is exact (case-insensitive), not wildcard/suffix --
"pypi.org" does not implicitly permit "files.pythonhosted.org". Simpler
to reason about and verify correctly than pattern matching; broader
matching is a tracked future enhancement, not something to guess at now.
"""
import re
import socket
import threading
from typing import Iterable

_CONNECT_RE = re.compile(rb"^CONNECT\s+([^\s:]+):(\d+)\s+HTTP/1\.[01]\r\n", re.IGNORECASE)
_REQUEST_LINE_RE = re.compile(rb"^([A-Z]+)\s+http://([^/\s:]+)(?::(\d+))?(/\S*)?\s+HTTP/1\.[01]\r\n")
_HOST_HEADER_RE = re.compile(rb"\r\nHost:\s*([^\s:\r\n]+)(?::(\d+))?\r\n", re.IGNORECASE)

_RECV_CHUNK = 65536
_HEADER_TIMEOUT_SEC = 5.0


class AllowlistProxy:
    """A forward proxy that only permits CONNECT/HTTP to `allowed_hosts`.

    Not a context manager by accident of laziness -- start()/stop() are
    explicit because the caller (namespace_backend.py) needs the bound
    port back from start() before it can finish configuring the sandbox
    side of things.
    """

    def __init__(self, bind_ip: str, allowed_hosts: Iterable[str]):
        self._bind_ip = bind_ip
        self._allowed = {h.lower() for h in allowed_hosts}
        self._server_sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.port: int | None = None

    def start(self, port: int = 0) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._bind_ip, port))
        sock.listen(16)
        sock.settimeout(0.5)  # so the accept loop can notice _stop
        self._server_sock = sock
        self.port = sock.getsockname()[1]
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        return self.port

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        if self._server_sock is not None:
            self._server_sock.close()

    def _accept_loop(self) -> None:
        assert self._server_sock is not None, "_accept_loop must only run after start()"
        server_sock = self._server_sock
        while not self._stop.is_set():
            try:
                client, _addr = server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _handle_client(self, client: socket.socket) -> None:
        try:
            client.settimeout(_HEADER_TIMEOUT_SEC)
            header = self._read_headers(client)
            if header is None:
                return

            m = _CONNECT_RE.match(header)
            if m:
                host = m.group(1).decode("ascii", errors="replace")
                port = int(m.group(2))
                self._handle_connect(client, host, port)
                return

            m = _REQUEST_LINE_RE.match(header)
            if m:
                host = m.group(2).decode("ascii", errors="replace")
                port = int(m.group(3)) if m.group(3) else 80
                self._handle_plain_http(client, header, host, port)
                return

            hm = _HOST_HEADER_RE.search(header)
            if hm:
                host = hm.group(1).decode("ascii", errors="replace")
                port = int(hm.group(2)) if hm.group(2) else 80
                self._handle_plain_http(client, header, host, port)
                return

            client.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        except (OSError, socket.timeout):
            pass
        finally:
            client.close()

    def _read_headers(self, client: socket.socket) -> bytes | None:
        buf = b""
        while b"\r\n\r\n" not in buf:
            try:
                chunk = client.recv(4096)
            except (OSError, socket.timeout):
                return None
            if not chunk:
                return None
            buf += chunk
            if len(buf) > 65536:
                return None  # header too large; not a client we need to support
        return buf

    def _is_allowed(self, host: str) -> bool:
        return host.lower() in self._allowed

    def _handle_connect(self, client: socket.socket, host: str, port: int) -> None:
        if not self._is_allowed(host):
            client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            return
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            return
        client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        _relay(client, upstream)

    def _handle_plain_http(self, client: socket.socket, header: bytes, host: str, port: int) -> None:
        if not self._is_allowed(host):
            client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            return
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            return
        upstream.sendall(header)
        _relay(client, upstream)


def _relay(a: socket.socket, b: socket.socket) -> None:
    """Bidirectional byte relay until either side closes. Two threads,
    each shutting down its OWN read direction on EOF so the other
    direction can still drain in flight -- avoids truncating a response
    that was still being written when the client finished sending."""
    done = threading.Event()

    def pump(src: socket.socket, dst: socket.socket) -> None:
        try:
            while not done.is_set():
                chunk = src.recv(_RECV_CHUNK)
                if not chunk:
                    break
                dst.sendall(chunk)
        except OSError:
            pass
        finally:
            done.set()
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    t1 = threading.Thread(target=pump, args=(a, b), daemon=True)
    t2 = threading.Thread(target=pump, args=(b, a), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    a.close()
    b.close()
