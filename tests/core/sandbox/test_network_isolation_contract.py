"""tests/core/sandbox/test_network_isolation_contract.py -- batch B01 of the
`sandbox-network-isolation` workstream: the mechanism-independent definition of
"isolated" for a networked sandbox, written as executable tests BEFORE any
mechanism exists.

Architecture Sources:
    docs/architecture/sandbox-network-isolation-master-specification.md
        §5 (INV-1 is the thing under test), §14 (TC-01 to TC-04), §15 (file
        boundary), §16 B01 (scope, requirements, acceptance)
    docs/architecture/sandbox-network-redesign-study.md (F1 to F6; the scratch
        probes in its Appendix A are the model for the probes below)
    docs/architecture/sandbox-b3-host-firewall-supplement-study.md (F28; the
        crafted-frame probe in its Appendix A.E9 is the model for TC-04)

What these tests define (INV-1): a networked sandbox can reach, from its
network, only its own proxy endpoint. They probe BEHAVIOR from inside a
sandbox, from a test-owned attacker container and from the host. Nothing here
presupposes a firewall, a per-sandbox network or any other mechanism (ruling
D3), and nothing in this file changes production code.

Expected state (RED): on a Docker host WITHOUT the isolation mechanism, every
contract case below fails, and fails for the documented reason:

    TC-01, TC-02  a host service bound to 0.0.0.0 is reachable through the
                  gateway (TCP and UDP)                      -> DEBT-040 (F6)
    TC-03         a sandbox reaches a sibling's proxy by a handed port, by
                  scanning, by CONNECT and by plain HTTP     -> DEBT-039 (F1-F4)
    TC-04         a crafted frame from a NET_RAW attacker reaches the sibling's
                  proxy endpoint (DEBT-039) and a host service (DEBT-040)

How "red for the right reason" is enforced (spec §16 B01 risk: a case that
fails for the wrong reason would be hidden by a loose marker):

  * Each case is marked `xfail(strict=True, raises=<DebtNNNViolation>)`. The
    violation classes below are raised ONLY by the contract assertion, after
    every setup step has been checked and every control has behaved. Any other
    failure (a harness error, a broken probe, a failed control, an ordinary
    AssertionError) is NOT an instance of those classes, so the marker does
    not absorb it and the case FAILS loudly.
  * `strict=True`: when a mechanism makes a case pass, it XPASSes and fails the
    suite, which forces the batch that earns the gate to remove the marker in
    the same change (never the known-failures manifest, PI §16.4).
  * The meta-tests at the end find the cases by name and check every variant:
    one strict xfail, typed by a specific violation class, naming its debt.
    A case added without such a marker fails the meta-test (no Docker needed).
  * Every case asserts that its injection or setup fired (listeners accept
    from the host, probes ran, positive controls answered) and that the host
    returns to its start-of-test baseline (Docker containers, networks, and
    the firewall without counters).

TC-04 note: the attacker is a test-owned container joined to sandbox B's own
network with NET_RAW added by the test (spec §14, OD-8). Its positive control
is network-scoped, as INV-1 is ("from its network"): the same crafted frame to
B's own proxy endpoint must get a SYN-ACK. A mechanism keyed on a sandbox's
source address, rather than on the network, would fail that control loudly
(a harness-level failure, not a contract violation); the specification's
rule S2 keys on the ingress bridge interface, which satisfies it.

Host gating (spec §14):
    D  a reachable Docker daemon and the test image present locally; otherwise
       the Docker cases SKIP with the reason. The image must contain python3
       (the convention in this repository is OCBRAIN_SANDBOX_DOCKER_IMAGE=
       ocbrain-test/base:local).
    P  provisioned isolation. No provisioning artifact exists yet (batch B10
       creates it), so for now the operator declares it with
       OCBRAIN_SANDBOX_NETWORK_PROVISIONED=1. A declared-provisioned host runs
       the cases WITHOUT the expected-failure marker, i.e. they must pass. The
       declaration can only make the suite stricter, never more lenient. B10
       replaces this declaration with the provisioning script's verify mode.

Backend parametrization: the cases run per backend in `_BACKEND_FACTORIES`.
Only "docker" is registered. NamespaceBackend equivalents are TC-17 (batch B04,
after B01) and no claim about NamespaceBackend is made here.

Hermeticity (spec §14, rule of October 8 2026): every upstream is a host-local
loopback server this file starts; the names used in allowlists never resolve
and are never dialed.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Iterator

import pytest

from core.sandbox.backends.docker_backend import DockerBackend
from core.sandbox.contracts import SandboxPolicy, SandboxRequest

# Reused, never re-implemented as a single recv() (study F11): the read-to-EOF
# helper that fixed the test_net_proxy.py flake, and the loopback upstream that
# records every request target it receives.
from .test_docker_backend import _RecordingUpstream
from .test_net_proxy import _recv_to_eof

_IMAGE = os.environ.get("OCBRAIN_SANDBOX_DOCKER_IMAGE", "alpine:3")


# ======================================================================
# Host gating (D, P)
# ======================================================================


def _docker_ready() -> tuple[bool, str]:
    """D: a reachable daemon AND the test image present locally."""
    try:
        if subprocess.run(["docker", "version"], capture_output=True, timeout=10).returncode != 0:
            return False, "requires a reachable Docker daemon"
        if subprocess.run(["docker", "image", "inspect", _IMAGE], capture_output=True, timeout=10).returncode != 0:
            return False, f"requires the test image {_IMAGE!r} locally (OCBRAIN_SANDBOX_DOCKER_IMAGE; it must contain python3)"
    except (OSError, subprocess.TimeoutExpired):
        return False, "requires a reachable Docker daemon"
    return True, ""


_DOCKER_OK, _DOCKER_WHY = _docker_ready()
needs_docker = pytest.mark.skipif(not _DOCKER_OK, reason=_DOCKER_WHY)


def _provisioned() -> bool:
    """P: the operator declares that the isolation mechanism is provisioned on
    this host (see the module docstring; replaced by B10's verify mode)."""
    return os.environ.get("OCBRAIN_SANDBOX_NETWORK_PROVISIONED") == "1"


# ======================================================================
# Violations, markers, registry
# ======================================================================


class ContractViolation(AssertionError):
    """Raised ONLY by a contract assertion, after setup and controls held."""


class Debt039Violation(ContractViolation):
    """DEBT-039: one sandbox can use, or reach, another sandbox's proxy."""


class Debt040Violation(ContractViolation):
    """DEBT-040 (F6): a sandbox reaches a host-local service."""


class HarnessError(RuntimeError):
    """The test itself is broken (a probe did not run, a control failed, two
    observers disagree). Never matched by any expected-failure marker."""


def _red_mark(violation: type[ContractViolation], debt: str, finding: str, tc: str) -> pytest.MarkDecorator:
    """The one expected-red marker: strict, typed by the violation class, and
    conditional on the host NOT being declared provisioned. A case whose
    variants fail for different debts passes it per variant through
    pytest.param(..., marks=...)."""
    return pytest.mark.xfail(
        condition=not _provisioned(),
        raises=violation,
        strict=True,
        reason=(
            f"{tc}: {debt} ({finding}) is open, so this case is expected red until the "
            f"isolation mechanism is provisioned (spec §16 B01). A pass means the gate "
            f"is earned: remove this marker in the same change."
        ),
    )


# ======================================================================
# Backend parametrization
# ======================================================================

_BACKEND_FACTORIES: dict[str, Callable[[], DockerBackend]] = {
    "docker": lambda: DockerBackend(image_ref=_IMAGE),
}


@pytest.fixture(params=sorted(_BACKEND_FACTORIES))
def backend(request):
    return _BACKEND_FACTORIES[request.param]()


# ======================================================================
# Baseline: Docker containers, networks and the firewall (without counters)
# ======================================================================


def _docker(*argv: str, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argv], capture_output=True, text=True, timeout=timeout)


def _firewall_snapshot() -> str | None:
    """`iptables-save` without counters or chain-policy counter lines, or None
    when it cannot be read (then the firewall comparison is not made and the
    Docker comparison still is)."""
    try:
        r = subprocess.run(["iptables-save"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return "\n".join(line for line in r.stdout.splitlines() if not line.startswith(("#", ":")))


def _host_snapshot() -> dict:
    containers = set(_docker("ps", "-aq", "--no-trunc").stdout.split())
    networks = set(_docker("network", "ls", "--no-trunc", "--format", "{{.ID}} {{.Name}}").stdout.splitlines())
    return {"containers": containers, "networks": networks, "firewall": _firewall_snapshot()}


@pytest.fixture(scope="module")
def _infrastructure_warm():
    """Whatever persistent infrastructure the mechanism keeps (today: the one
    shared network) is created once, before any baseline is taken, so the first
    case does not look like it leaked. Uses only the public backend API."""
    if not _DOCKER_OK:
        yield
        return

    async def warm() -> None:
        backend = _BACKEND_FACTORIES["docker"]()
        request = SandboxRequest(
            command=("true",),
            policy=SandboxPolicy(
                workspace_dir=os.path.join(os.environ.get("TMPDIR", "/tmp"), f"b01-warm-{uuid.uuid4().hex[:8]}"),
                allowed_hosts=("warm.invalid",),
                timeout_sec=20,
            ),
        )
        handle = await backend.create(request)
        await backend.destroy(handle)

    asyncio.run(warm())
    yield


@pytest.fixture
def host_baseline(_infrastructure_warm):
    """Every host case ends by comparing the host with its start-of-test
    baseline (spec §14). A leak is reported as a teardown ERROR: it is a
    harness or product fault, never absorbed by an expected-failure marker."""
    before = _host_snapshot()
    yield before
    after = _host_snapshot()
    assert after["containers"] - before["containers"] == set(), (
        f"leaked containers: {after['containers'] - before['containers']}"
    )
    assert after["networks"] - before["networks"] == set(), f"leaked networks: {after['networks'] - before['networks']}"
    assert before["networks"] - after["networks"] == set(), f"vanished networks: {before['networks'] - after['networks']}"
    if before["firewall"] is not None and after["firewall"] is not None:
        assert after["firewall"] == before["firewall"], "the host firewall changed during the case"


# ======================================================================
# Describing a created sandbox from the outside (Docker introspection)
# ======================================================================


@dataclass(frozen=True)
class _SandboxView:
    request_id: str
    container_id: str
    network: str  # the network the sandbox is attached to
    gateway: str  # that network's gateway address (a host address)
    proxy_host: str  # the endpoint the sandbox's own proxy listens on
    proxy_port: int


def _inspect_json(container_id: str) -> dict:
    r = _docker("inspect", container_id)
    if r.returncode != 0:
        raise HarnessError(f"docker inspect {container_id} failed: {r.stderr.strip()}")
    return json.loads(r.stdout)[0]


def _describe(request: SandboxRequest) -> _SandboxView:
    ids = _docker("ps", "-aq", "--no-trunc", "--filter", f"label=ocbrain.request_id={request.request_id}").stdout.split()
    if len(ids) != 1:
        raise HarnessError(f"expected exactly one container for request {request.request_id}, found {ids}")
    info = _inspect_json(ids[0])
    network = info["HostConfig"]["NetworkMode"]
    env = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    proxy = env.get("HTTPS_PROXY")
    if not proxy or not proxy.startswith("http://"):
        raise HarnessError(f"the sandbox was not given an HTTPS_PROXY endpoint (env: {sorted(env)})")
    proxy_host, _, proxy_port = proxy[len("http://") :].rpartition(":")
    g = _docker("network", "inspect", network, "--format", "{{(index .IPAM.Config 0).Gateway}}")
    gateway = g.stdout.strip()
    if g.returncode != 0 or not gateway:
        raise HarnessError(f"cannot read the gateway of network {network!r}: {g.stderr.strip()}")
    return _SandboxView(request.request_id, ids[0], network, gateway, proxy_host, int(proxy_port))


def _request(tmp_path, label: str, *, command, allowed_hosts, env=None, timeout_sec: float = 30, max_pids: int = 64):
    return SandboxRequest(
        command=tuple(command),
        policy=SandboxPolicy(
            workspace_dir=str(tmp_path / label),
            allowed_hosts=tuple(allowed_hosts),
            timeout_sec=timeout_sec,
            max_pids=max_pids,
        ),
        env=dict(env or {}),
    )


@contextlib.asynccontextmanager
async def _created(backend: DockerBackend, request: SandboxRequest):
    """create() directly (admission is withdrawn, spec §16 B01); destroy() always."""
    handle = await backend.create(request)
    try:
        yield handle, _describe(request)
    finally:
        await backend.destroy(handle)


async def _run_probe(backend: DockerBackend, handle, request: SandboxRequest) -> dict[str, str]:
    result = await backend.run(handle, request)
    if result.exit_code != 0:
        raise HarnessError(
            f"the probe did not run to completion (exit {result.exit_code}, {result.termination_reason}); "
            f"the image needs python3.\nstdout: {result.stdout[-400:]}\nstderr: {result.stderr[-400:]}"
        )
    return _kv(result.stdout)


def _kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.isidentifier():
            out[key] = value
    return out


def _need(observed: dict[str, str], *keys: str) -> None:
    missing = [k for k in keys if k not in observed]
    if missing:
        raise HarnessError(f"the probe did not report {missing}; it reported {sorted(observed)}")


async def _off_loop(fn: Callable, *args, **kwargs):
    """Run a blocking host-side step (socket, docker CLI, poll) off the event
    loop, so a concurrent sandbox's run() task is never stalled by the test."""
    return await asyncio.to_thread(fn, *args, **kwargs)


def _http_status_code(raw: bytes | str) -> str:
    """The status code of an HTTP response (bytes or text), or '-' when the
    first line is not an HTTP status line."""
    text = raw.decode("latin-1") if isinstance(raw, bytes) else raw
    parts = text.split("\r\n", 1)[0].split()
    return parts[1] if len(parts) > 1 and parts[0].startswith("HTTP/") else "-"


# ======================================================================
# Probes that run INSIDE the sandbox (python3, stdlib only)
# ======================================================================

_PROBE_PRELUDE = r'''
import os, socket, urllib.parse


def recv_all(s, limit=1 << 16):
    # Read to EOF: one recv() is not a whole response (study F11).
    chunks, total = [], 0
    while total < limit:
        c = s.recv(4096)
        if not c:
            break
        chunks.append(c)
        total += len(c)
    return b"".join(chunks)


def recv_until(s, marker=b"\r\n\r\n", limit=1 << 16):
    buf = b""
    while marker not in buf and len(buf) < limit:
        c = s.recv(4096)
        if not c:
            break
        buf += c
    return buf


def status(text):
    return text.split("\r\n", 1)[0] if text else "EMPTY"


def code(line):
    parts = line.split()
    return parts[1] if len(parts) > 1 and parts[0].startswith("HTTP/") else "-"


def connect_via(host, port, target, timeout=6):
    """CONNECT target through the proxy at host:port -> (status line, socket or None)."""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(timeout)
        s.sendall(("CONNECT %s HTTP/1.1\r\nHost: %s\r\n\r\n" % (target, target)).encode())
        return status(recv_until(s).decode("latin-1")), s
    except Exception as e:
        return "ERR " + type(e).__name__, None


def plain_via(host, port, target, path, timeout=6):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(timeout)
        s.sendall(("GET http://%s%s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % (target, path, target)).encode())
        text = recv_all(s).decode("latin-1")
        s.close()
        return text
    except Exception as e:
        return "ERR " + type(e).__name__


def reach_tcp(host, port, payload=b"", timeout=3):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        if payload:
            s.sendall(payload)
        s.close()
        return "CONNECTED"
    except Exception as e:
        return type(e).__name__


_proxy = urllib.parse.urlparse(os.environ["HTTPS_PROXY"])
GW = _proxy.hostname
OWN_PORT = _proxy.port
TOKEN = os.environ["TOKEN"]
'''

# Positive control used by TC-01 and TC-02: the sandbox's OWN proxy still answers
# (it rejects a non-allowlisted name with 403 without dialing anything).
_OWN_PROXY_CONTROL = r'''
_line, _s = connect_via(GW, OWN_PORT, "disallowed.invalid:443")
if _s:
    _s.close()
print("OWN_PROXY=" + _line)
'''

_TC01_PROBE = (
    _PROBE_PRELUDE
    + _OWN_PROXY_CONTROL
    + r'''
print("LOOPBACK_BOUND=" + reach_tcp(GW, int(os.environ["LOOP_PORT"]), TOKEN.encode()))
print("WILDCARD_BOUND=" + reach_tcp(GW, int(os.environ["ANY_PORT"]), TOKEN.encode()))
'''
)

_TC02_PROBE = (
    _PROBE_PRELUDE
    + _OWN_PROXY_CONTROL
    + r'''
import time
sent = {}
for name, port in (("LOOPBACK_BOUND", int(os.environ["LOOP_PORT"])), ("WILDCARD_BOUND", int(os.environ["ANY_PORT"]))):
    u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent[name] = 0
    for i in range(3):
        sent[name] += 1 if u.sendto(TOKEN.encode(), (GW, port)) == len(TOKEN) else 0
        time.sleep(0.1)
    u.close()
    print("SENT_" + name + "=%d" % sent[name])
'''
)

_TC03_PROBE = (
    _PROBE_PRELUDE
    + r'''
vector = os.environ["VECTOR"]
a_gw, a_port = os.environ["A_GW"], int(os.environ["A_PORT"])
up = int(os.environ["UP_PORT"])
target = "127.0.0.1:%d" % up
path = "/" + TOKEN

# Control: B's own proxy rejects A's allowed host (the two allowlists differ).
_line, _s = connect_via(GW, OWN_PORT, target)
if _s:
    _s.close()
print("OWN_CONTROL=" + _line)

if vector == "handed_port":
    print("A_TCP=" + reach_tcp(a_gw, a_port))
elif vector == "connect_method":
    line, s = connect_via(a_gw, a_port, target)
    print("A_CONNECT=" + line)
    if s is not None:
        if code(line) == "200":
            s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % (path, target)).encode())
            print("A_TUNNEL=" + status(recv_all(s).decode("latin-1")))
        s.close()
elif vector == "plain_http":
    print("A_PLAIN=" + status(plain_via(a_gw, a_port, target, path)))
elif vector == "scan":
    import asyncio

    async def scan(host, ports, conc=800):
        sem = asyncio.Semaphore(conc)
        found = []

        async def one(p):
            async with sem:
                try:
                    _r, w = await asyncio.wait_for(asyncio.open_connection(host, p), 0.6)
                    w.close()
                    found.append(p)
                except Exception:
                    pass

        await asyncio.gather(*(one(p) for p in ports))
        return sorted(found)

    ports = [3128] + list(range(int(os.environ["SCAN_LO"]), int(os.environ["SCAN_HI"]) + 1))
    open_eps = []
    for host in sorted({GW, a_gw}):
        open_eps += ["%s:%d" % (host, p) for p in asyncio.run(scan(host, ports))]
    print("SCAN_OPEN=" + ",".join(open_eps))
else:
    print("UNKNOWN_VECTOR=" + vector)
'''
)

# TC-04: runs inside a test-owned attacker container that has NET_RAW added
# explicitly by the test (spec §14: the case must stay valid after DEBT-041 drops
# NET_RAW from normal sandboxes). Crafts one TCP SYN as a raw Ethernet frame
# (AF_PACKET) and reports whether a SYN-ACK came back from the target. Model: the
# study's E9 probe (F28).
_TC04_FRAME_PROBE = r'''
import socket, struct, random, time, sys
src, dst, dport, gw_own = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]


def cs(b):
    if len(b) % 2:
        b += b"\0"
    s = sum(struct.unpack("!%dH" % (len(b) // 2), b))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return ~s & 0xFFFF


try:
    pk = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))
    pk.bind(("eth0", 0))
    pk.settimeout(0.4)
except Exception as e:
    print("RESULT=NO_AF_PACKET " + type(e).__name__)
    sys.exit(0)
try:
    socket.create_connection((gw_own, 9), timeout=1)  # populates the ARP entry for the gateway
except Exception:
    pass
mac_me = bytes.fromhex(open("/sys/class/net/eth0/address").read().strip().replace(":", ""))
rows = [l.split() for l in open("/proc/net/arp").read().splitlines()[1:] if l.split()[0] == gw_own]
if not rows:
    print("RESULT=NO_ARP_FOR_GATEWAY")
    sys.exit(0)
mac_gw = bytes.fromhex(rows[0][3].replace(":", ""))
sport, seq = random.randint(20000, 60000), random.getrandbits(32)
t0 = struct.pack("!HHLLBBHHH", sport, dport, seq, 0, 5 << 4, 2, 65535, 0, 0)
ph = socket.inet_aton(src) + socket.inet_aton(dst) + struct.pack("!BBH", 0, 6, len(t0))
t = struct.pack("!HHLLBBHHH", sport, dport, seq, 0, 5 << 4, 2, 65535, cs(ph + t0), 0)
i0 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(t), random.getrandbits(16), 0, 64, 6, 0, socket.inet_aton(src), socket.inet_aton(dst))
ip = i0[:10] + struct.pack("!H", cs(i0)) + i0[12:]
pk.send(mac_gw + mac_me + b"\x08\x00" + ip + t)
end, got = time.time() + 2.5, "NO_REPLY"
while time.time() < end:
    try:
        f = pk.recv(2048)
    except socket.timeout:
        continue
    if f[12:14] != b"\x08\x00" or f[23] != 6:
        continue
    o = 14 + (f[14] & 15) * 4
    sp, dp, _a, ack, off, flags = struct.unpack("!HHLLBB", f[o : o + 14])
    if socket.inet_ntoa(f[26:30]) == dst and sp == dport and dp == sport and (flags & 0x12) == 0x12:
        got = "SYN_ACK"
        break
print("RESULT=" + got)
'''


# ======================================================================
# Host-side observers (every one reads to EOF, never a single recv())
# ======================================================================


class _TcpRecorder:
    """A TCP listener that records (peer, payload) for every connection."""

    def __init__(self, bind_ip: str) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((bind_ip, 0))
        self._sock.listen(32)
        self._sock.settimeout(0.2)
        self.port: int = self._sock.getsockname()[1]
        self.bind_ip = bind_ip
        self._seen: list[tuple[tuple[str, int], bytes]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, peer = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(2)
                try:
                    data = _recv_to_eof(conn)
                except OSError:
                    data = b""
            with self._lock:
                self._seen.append((peer, data))

    def payloads(self) -> list[bytes]:
        with self._lock:
            return [d for _, d in self._seen]

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()

    def wait_for(self, payload: bytes, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if payload in self.payloads():
                return True
            time.sleep(0.05)
        return False

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        self._sock.close()


class _UdpRecorder:
    def __init__(self, bind_ip: str) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((bind_ip, 0))
        self._sock.settimeout(0.2)
        self.port: int = self._sock.getsockname()[1]
        self._seen: list[bytes] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _peer = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                self._seen.append(data)

    def payloads(self) -> list[bytes]:
        with self._lock:
            return list(self._seen)

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()

    def wait_for(self, payload: bytes, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if payload in self.payloads():
                return True
            time.sleep(0.05)
        return False

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)
        self._sock.close()


def _host_send_tcp(endpoint: tuple[str, int], payload: bytes) -> None:
    with socket.create_connection(endpoint, timeout=3) as c:
        c.sendall(payload)


def _host_tcp_connects(endpoint: tuple[str, int]) -> bool:
    try:
        socket.create_connection(endpoint, timeout=3).close()
    except OSError:
        return False
    return True


def _host_send_udp(endpoints: list[tuple[str, int]], payload: bytes) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
        for endpoint in endpoints:
            u.sendto(payload, endpoint)


@contextlib.contextmanager
def _closing_all() -> Iterator[list]:
    items: list = []
    try:
        yield items
    finally:
        for item in items:
            item.close()


def _token(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _host_primary_ipv4() -> str | None:
    """The host's primary non-loopback IPv4 address (the one used to reach the
    outside), without sending a packet; None when the host has no such route."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET-1; connect() on UDP only selects a route
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return None if ip.startswith("127.") or ip == "0.0.0.0" else ip


# ======================================================================
# TC-01 / TC-02: host services bound to 0.0.0.0 (DEBT-040, F6)
# ======================================================================


@needs_docker
@_red_mark(Debt040Violation, "DEBT-040", "F6, a 0.0.0.0 host listener is reachable through the gateway", "TC-01")
@pytest.mark.asyncio
async def test_tc01_wildcard_tcp_listener_is_unreachable_through_the_gateway(backend, tmp_path, host_baseline):
    token = _token("tc01")
    with _closing_all() as opened:
        wildcard = _TcpRecorder("0.0.0.0")
        loopback = _TcpRecorder("127.0.0.1")
        opened += [wildcard, loopback]
        request = _request(
            tmp_path, "tc01", command=("python3", "-c", _TC01_PROBE), allowed_hosts=("allowed.invalid",),
            env={"TOKEN": token, "ANY_PORT": str(wildcard.port), "LOOP_PORT": str(loopback.port)},
        )
        async with _created(backend, request) as (handle, sandbox):
            # Setup fired: from the HOST, the wildcard listener answers on the
            # gateway address, and the loopback-bound one does not (it is the
            # negative control: it must stay unreachable through the gateway).
            host_probe = b"tc01-host-setup"
            await _off_loop(_host_send_tcp, (sandbox.gateway, wildcard.port), host_probe)
            if not await _off_loop(wildcard.wait_for, host_probe, 3):
                raise HarnessError("setup: the 0.0.0.0 listener did not accept from the host")
            if await _off_loop(_host_tcp_connects, (sandbox.gateway, loopback.port)):
                raise HarnessError("setup: a 127.0.0.1-bound listener answered on the gateway address")
            wildcard.clear()
            loopback.clear()

            observed = await _run_probe(backend, handle, request)
            _need(observed, "OWN_PROXY", "LOOPBACK_BOUND", "WILDCARD_BOUND")

            assert observed["OWN_PROXY"].startswith("HTTP/1.1 403"), (
                f"control: the sandbox's own proxy did not answer ({observed['OWN_PROXY']!r}); the probe is not "
                f"measuring a working network path"
            )
            assert observed["LOOPBACK_BOUND"] != "CONNECTED" and not loopback.payloads(), (
                "control: a 127.0.0.1-bound service was reached through the gateway; the probe is invalid"
            )

            reached_by_sandbox = observed["WILDCARD_BOUND"] == "CONNECTED"
            reached_on_host = await _off_loop(wildcard.wait_for, token.encode(), 2.0)
            if reached_by_sandbox != reached_on_host:
                raise HarnessError(
                    f"observers disagree: the sandbox says {observed['WILDCARD_BOUND']!r}, the host listener "
                    f"{'saw' if reached_on_host else 'did not see'} the token"
                )
            if reached_on_host:
                raise Debt040Violation(
                    f"DEBT-040/F6: sandbox {sandbox.request_id} delivered its token to a TCP service bound to "
                    f"0.0.0.0 on the host, through its gateway {sandbox.gateway} (network {sandbox.network})"
                )


@needs_docker
@_red_mark(Debt040Violation, "DEBT-040", "F6, a 0.0.0.0 UDP host listener receives datagrams from a sandbox", "TC-02")
@pytest.mark.asyncio
async def test_tc02_wildcard_udp_listener_receives_no_datagram_from_the_sandbox(backend, tmp_path, host_baseline):
    token = _token("tc02")
    with _closing_all() as opened:
        wildcard = _UdpRecorder("0.0.0.0")
        loopback = _UdpRecorder("127.0.0.1")
        opened += [wildcard, loopback]
        request = _request(
            tmp_path, "tc02", command=("python3", "-c", _TC02_PROBE), allowed_hosts=("allowed.invalid",),
            env={"TOKEN": token, "ANY_PORT": str(wildcard.port), "LOOP_PORT": str(loopback.port)},
        )
        async with _created(backend, request) as (handle, sandbox):
            # Setup fired, from the host: the wildcard socket receives on the
            # gateway address; the loopback-bound one does not.
            host_probe = b"tc02-host-setup"
            await _off_loop(_host_send_udp, [(sandbox.gateway, wildcard.port), (sandbox.gateway, loopback.port)], host_probe)
            if not await _off_loop(wildcard.wait_for, host_probe, 3):
                raise HarnessError("setup: the 0.0.0.0 UDP socket did not receive from the host")
            await asyncio.sleep(0.3)
            if host_probe in loopback.payloads():
                raise HarnessError("setup: a 127.0.0.1-bound UDP socket received a datagram via the gateway")
            wildcard.clear()
            loopback.clear()

            observed = await _run_probe(backend, handle, request)
            _need(observed, "OWN_PROXY", "SENT_LOOPBACK_BOUND", "SENT_WILDCARD_BOUND")

            assert observed["OWN_PROXY"].startswith("HTTP/1.1 403"), (
                f"control: the sandbox's own proxy did not answer ({observed['OWN_PROXY']!r})"
            )
            # The send path was exercised: every datagram was handed to the kernel.
            assert observed["SENT_WILDCARD_BOUND"] == "3" and observed["SENT_LOOPBACK_BOUND"] == "3", (
                f"the probe did not send its datagrams: {observed}"
            )
            await asyncio.sleep(0.5)
            assert token.encode() not in loopback.payloads(), (
                "control: a 127.0.0.1-bound UDP socket received a datagram via the gateway; the probe is invalid"
            )
            if await _off_loop(wildcard.wait_for, token.encode(), 2.0):
                raise Debt040Violation(
                    f"DEBT-040/F6: sandbox {sandbox.request_id} delivered UDP datagrams to a socket bound to "
                    f"0.0.0.0 on the host, through its gateway {sandbox.gateway} (network {sandbox.network})"
                )


# ======================================================================
# TC-03: a sandbox must not reach a sibling's proxy (DEBT-039, F1 to F4)
# ======================================================================


def _ephemeral_range() -> tuple[int, int]:
    try:
        with open("/proc/sys/net/ipv4/ip_local_port_range") as f:
            lo, hi = f.read().split()
        return int(lo), int(hi)
    except (OSError, ValueError):
        return 32768, 60999


async def _wait_running(container_id: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = await _off_loop(_docker, "inspect", "--format", "{{.State.Running}}", container_id)
        if state.stdout.strip() == "true":
            return
        await asyncio.sleep(0.1)
    raise HarnessError(f"sandbox container {container_id} did not reach the running state within {timeout}s")


async def _agree_with_upstream(upstream: _RecordingUpstream, token: str, b_says_reached: bool, observed: dict) -> None:
    """Two observers, one fact: B's claim that it got through to A's host must
    match what the host-local upstream recorded. A disagreement means the
    probe or the harness is wrong, never a contract result."""
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if any(token in request for request in upstream.requests):
            break
        await asyncio.sleep(0.05)
    upstream_saw = any(token in request for request in upstream.requests)
    if upstream_saw != b_says_reached:
        raise HarnessError(
            f"observers disagree: B reported {observed}, the upstream "
            f"{'saw' if upstream_saw else 'did not see'} B's token (recorded: {upstream.requests})"
        )


def _via_a(endpoint: tuple[str, int], payload: bytes) -> bytes:
    """A host-side request through a proxy endpoint, read to EOF."""
    with socket.create_connection(endpoint, timeout=5) as s:
        s.settimeout(5)
        s.sendall(payload)
        return _recv_to_eof(s)


@needs_docker
@pytest.mark.parametrize("vector", ["handed_port", "scan", "connect_method", "plain_http"])
@_red_mark(Debt039Violation, "DEBT-039", "F1 to F4, a sandbox uses a sibling's proxy", "TC-03")
@pytest.mark.asyncio
async def test_tc03_sandbox_cannot_reach_a_siblings_proxy(vector, backend, tmp_path, host_baseline):
    upstream = _RecordingUpstream()
    upstream.start()
    token = _token("tc03")
    scan_lo, scan_hi = _ephemeral_range()
    try:
        # A: concurrent, long-running, allows ONLY the host-local upstream.
        request_a = _request(
            tmp_path, "tc03-a", command=("sleep", "120"), allowed_hosts=("127.0.0.1",), timeout_sec=150
        )
        async with _created(backend, request_a) as (handle_a, a):
            run_a = asyncio.ensure_future(backend.run(handle_a, request_a))
            try:
                await _wait_running(a.container_id)
                a_endpoint = (a.proxy_host, a.proxy_port)
                target = f"127.0.0.1:{upstream.port}"

                # Controls from the host: A's own proxy allows A's host (200) and
                # the upstream really records the request. Then forget them.
                ok = await _off_loop(
                    _via_a, a_endpoint,
                    f"GET http://{target}/ctl-{token} HTTP/1.1\r\nHost: {target}\r\nConnection: close\r\n\r\n".encode(),
                )
                assert _http_status_code(ok) == "200", f"control: A's proxy did not allow A's host: {ok[:80]!r}"
                assert upstream.requests == [f"http://{target}/ctl-{token}"], f"control: the upstream saw {upstream.requests}"
                upstream.requests.clear()
                if vector == "scan":
                    assert scan_lo <= a.proxy_port <= scan_hi or a.proxy_port == 3128, (
                        f"setup: A's proxy port {a.proxy_port} is outside the scanned space {scan_lo}-{scan_hi}, 3128"
                    )

                # B: allows only a name that never resolves; it runs the probe.
                request_b = _request(
                    tmp_path, "tc03-b", command=("python3", "-c", _TC03_PROBE), allowed_hosts=("b-only.invalid",),
                    env={
                        "TOKEN": token, "VECTOR": vector, "A_GW": a.proxy_host, "A_PORT": str(a.proxy_port),
                        "UP_PORT": str(upstream.port), "SCAN_LO": str(scan_lo), "SCAN_HI": str(scan_hi),
                    },
                    timeout_sec=150 if vector == "scan" else 40,
                    max_pids=256,
                )
                async with _created(backend, request_b) as (handle_b, b):
                    observed = await _run_probe(backend, handle_b, request_b)
                    _need(observed, "OWN_CONTROL")
                    assert observed["OWN_CONTROL"].startswith("HTTP/1.1 403"), (
                        f"control: B's own proxy did not reject A's allowed host ({observed['OWN_CONTROL']!r}); "
                        f"the two allowlists do not differ as the case requires"
                    )
                    a_ep = f"{a.proxy_host}:{a.proxy_port}"

                    if vector == "handed_port":
                        _need(observed, "A_TCP")
                        reached = observed["A_TCP"] == "CONNECTED"
                        how = f"connected to A's proxy endpoint {a_ep} when handed its port"
                    elif vector == "scan":
                        _need(observed, "SCAN_OPEN")
                        found = [e for e in observed["SCAN_OPEN"].split(",") if e]
                        own_ep = f"{b.proxy_host}:{b.proxy_port}"
                        if own_ep not in found:
                            raise HarnessError(
                                f"control: the scan did not find B's own proxy endpoint {own_ep}; it is not measuring "
                                f"reachability (found {found})"
                            )
                        reached = a_ep in found
                        how = f"discovered A's proxy endpoint {a_ep} by scanning (open endpoints: {found})"
                    elif vector == "connect_method":
                        _need(observed, "A_CONNECT")
                        reached = _http_status_code(observed["A_CONNECT"]) == "200"
                        how = f"obtained a CONNECT tunnel to A's host through A's proxy ({observed['A_CONNECT']!r})"
                        # B only sends a request through the tunnel when the tunnel opened, so
                        # the upstream must have seen B's token exactly when B reports a tunnel.
                        await _agree_with_upstream(upstream, token, reached, observed)
                    else:
                        _need(observed, "A_PLAIN")
                        reached = _http_status_code(observed["A_PLAIN"]) == "200"
                        how = f"fetched A's host with plain HTTP through A's proxy ({observed['A_PLAIN']!r})"
                        await _agree_with_upstream(upstream, token, reached, observed)

                    if reached:
                        raise Debt039Violation(
                            f"DEBT-039: sandbox B {b.request_id} {how}; B's own allowlist does not contain A's host "
                            f"(vector {vector}; network {b.network}, gateway {b.gateway})"
                        )
            finally:
                await backend.cancel(handle_a)
                await run_a
    finally:
        upstream.close()


# ======================================================================
# TC-04: a NET_RAW attacker on the sandbox's own network (DEBT-039, DEBT-040)
# ======================================================================


def _exec_frame_probe(container: str, src: str, dst: str, dport: int, own_gateway: str) -> str:
    r = _docker("exec", container, "python3", "-c", _TC04_FRAME_PROBE, src, dst, str(dport), own_gateway, timeout=30)
    lines = _kv(r.stdout)
    if "RESULT" not in lines:
        raise HarnessError(f"the frame probe did not report a result: stdout={r.stdout[-300:]!r} stderr={r.stderr[-300:]!r}")
    return lines["RESULT"]


@needs_docker
@pytest.mark.parametrize(
    "target_kind, violation, debt",
    [
        # Each variant carries its own strict marker, typed by the debt it demonstrates.
        pytest.param(
            "sibling_proxy", Debt039Violation, "DEBT-039", id="sibling_proxy",
            marks=_red_mark(Debt039Violation, "DEBT-039", "F28, a crafted frame reaches a sibling's proxy endpoint", "TC-04"),
        ),
        pytest.param(
            "host_primary", Debt040Violation, "DEBT-040", id="host_primary",
            marks=_red_mark(Debt040Violation, "DEBT-040", "F28, a crafted frame reaches a host service on the primary address", "TC-04"),
        ),
    ],
)
@pytest.mark.asyncio
async def test_tc04_net_raw_attacker_gets_no_reply_from_sibling_or_host(
    target_kind, violation, debt, backend, tmp_path, host_baseline
):
    host_ip = _host_primary_ipv4()
    if host_ip is None:
        pytest.skip("the host has no primary non-loopback IPv4 address to target")
    attacker = f"b01-tc04-{uuid.uuid4().hex[:10]}"
    with _closing_all() as opened:
        host_listener = _TcpRecorder(host_ip)
        opened.append(host_listener)
        request_a = _request(tmp_path, "tc04-a", command=("true",), allowed_hosts=("a-only.invalid",))
        request_b = _request(tmp_path, "tc04-b", command=("true",), allowed_hosts=("b-only.invalid",))
        async with _created(backend, request_a) as (_ha, a), _created(backend, request_b) as (_hb, b):
            try:
                # Setup fired: the host listener answers on the primary address.
                setup = b"tc04-host-setup"
                await _off_loop(_host_send_tcp, (host_ip, host_listener.port), setup)
                if not await _off_loop(host_listener.wait_for, setup, 3):
                    raise HarnessError("setup: the host-primary listener did not accept from the host")
                host_listener.clear()

                # The attacker is test-owned, joined to B's own network, with NET_RAW
                # added EXPLICITLY (the backend itself forbids --cap-add, A6).
                run = await _off_loop(
                    _docker,
                    "run", "-d", "--name", attacker, "--network", b.network, "--cap-add", "NET_RAW",
                    "--read-only", "--security-opt", "no-new-privileges", _IMAGE, "sleep", "120",
                )
                if run.returncode != 0:
                    raise HarnessError(f"could not start the attacker container: {run.stderr.strip()}")
                info = await _off_loop(_inspect_json, attacker)
                attacker_ip = next(iter(info["NetworkSettings"]["Networks"].values()))["IPAddress"]
                if not attacker_ip:
                    raise HarnessError("the attacker container has no address on the sandbox's network")

                # Positive control: the SAME probe to B's own gateway and own proxy port
                # gets a SYN-ACK. Without it a "no reply" below would mean nothing.
                control = await _off_loop(_exec_frame_probe, attacker, attacker_ip, b.proxy_host, b.proxy_port, b.gateway)
                assert control == "SYN_ACK", (
                    f"control: the crafted frame to B's own proxy endpoint {b.proxy_host}:{b.proxy_port} got {control!r}; "
                    f"the probe is not measuring reachability"
                )

                if target_kind == "sibling_proxy":
                    dst, dport = a.proxy_host, a.proxy_port
                    what = f"A's proxy endpoint {dst}:{dport} (A's gateway {a.gateway})"
                else:
                    dst, dport = host_ip, host_listener.port
                    what = f"a TCP service on the host's primary address {dst}:{dport}"
                result = await _off_loop(_exec_frame_probe, attacker, attacker_ip, dst, dport, b.gateway)
                if result not in ("SYN_ACK", "NO_REPLY"):
                    raise HarnessError(f"the frame probe to the target reported {result!r}")
                if result == "SYN_ACK":
                    raise violation(
                        f"{debt}: a NET_RAW container on sandbox B's network ({b.network}) crafted a frame and got a "
                        f"SYN-ACK from {what}"
                    )
            finally:
                await _off_loop(_docker, "rm", "-f", attacker)


# ======================================================================
# Meta-tests: the markers themselves (need no Docker)
# ======================================================================


def _contract_functions() -> list[Callable]:
    """Every contract case in this module, found by name (not registered), so a
    case added without a marker cannot hide from the meta-tests."""
    return [fn for name, fn in sorted(globals().items()) if name.startswith("test_tc") and callable(fn)]


def _variant_marks(fn) -> list[list]:
    """The marks that apply to each variant of a case: for a plain case, one
    entry; for a parametrized case, the function's marks plus each parameter
    set's own marks (pytest.param(..., marks=...))."""
    marks = list(getattr(fn, "pytestmark", []))
    parametrize = [m for m in marks if m.name == "parametrize"]
    shared = [m for m in marks if m.name != "parametrize"]
    variants: list[list] = [shared]
    for m in parametrize:
        argvalues = m.args[1]
        variants = [shared + list(ps.marks) for ps in argvalues] if hasattr(argvalues[0], "marks") else variants
    return variants


def test_every_contract_case_is_strictly_typed_and_names_its_debt():
    """A loose marker would hide a case that fails for the wrong reason (spec
    §16 B01, risk). Every variant of every contract case must carry exactly one
    xfail that is strict, names a ContractViolation subclass in `raises`, and
    cites a debt."""
    functions = _contract_functions()
    assert functions, "no contract case found"
    for fn in functions:
        for marks in _variant_marks(fn):
            xfails = [m for m in marks if m.name == "xfail"]
            assert len(xfails) == 1, f"{fn.__name__}: expected one xfail marker per variant, found {len(xfails)}"
            kwargs = xfails[0].kwargs
            assert kwargs.get("strict") is True, f"{fn.__name__}: the marker is not strict"
            raises = kwargs.get("raises")
            assert isinstance(raises, type) and issubclass(raises, ContractViolation) and raises is not ContractViolation, (
                f"{fn.__name__}: `raises` must be a specific violation class (DEBT-039 or DEBT-040), got {raises!r}"
            )
            reason = kwargs.get("reason", "")
            debt = "DEBT-039" if raises is Debt039Violation else "DEBT-040"
            assert debt in reason, f"{fn.__name__}: the reason does not name {debt}"


def test_the_catalogue_covers_tc01_to_tc04():
    names = {fn.__name__ for fn in _contract_functions()}
    for prefix in ("test_tc01_", "test_tc02_", "test_tc03_", "test_tc04_"):
        assert any(n.startswith(prefix) for n in names), f"no contract case for {prefix[5:9].upper()}"


def test_violations_are_not_confusable_with_harness_failures():
    assert issubclass(Debt039Violation, AssertionError) and issubclass(Debt040Violation, AssertionError)
    assert not issubclass(HarnessError, ContractViolation)
    assert not issubclass(AssertionError, ContractViolation), "a plain assert must never match a marker"
    assert not issubclass(Debt039Violation, Debt040Violation) and not issubclass(Debt040Violation, Debt039Violation)


def test_kv_parser_ignores_noise_and_keeps_the_last_value():
    assert _kv("noise\nA=1\nB=x=y\nnot a key=2\nA=3\n") == {"A": "3", "B": "x=y"}


def test_provisioned_declaration_is_off_unless_explicitly_one(monkeypatch):
    for value in (None, "", "0", "true", "yes"):
        if value is None:
            monkeypatch.delenv("OCBRAIN_SANDBOX_NETWORK_PROVISIONED", raising=False)
        else:
            monkeypatch.setenv("OCBRAIN_SANDBOX_NETWORK_PROVISIONED", value)
        assert _provisioned() is False
    monkeypatch.setenv("OCBRAIN_SANDBOX_NETWORK_PROVISIONED", "1")
    assert _provisioned() is True
