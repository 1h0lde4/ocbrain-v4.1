# Sandbox network-redesign study (DEBT-039): evidence and reconciliation

- **Date:** October 3 2026
- **Status:** evidence phase complete; the user's decisions are recorded in section 7. **No design is chosen, nothing is implemented, and no repository code, test, capability or contract was changed.** The only file this study adds is this document.
- **Base:** `sandbox-fabric` at `1b829fc`. **Location decided by the user (October 3 2026, section 7):** branch `study/sandbox-network-redesign`, pushed; not to be merged into `main` yet.
- **Environment:** Ubuntu 24.04, kernel `6.18.44-fc-v64` (a Firecracker microVM), Docker Engine 29.1.3, cgroup v1, no `/etc/docker/daemon.json`, the `docker import`-built test image `ocbrain-test/base:local`. Everything below was observed on this one host.
- **Status vocabulary:** VERIFIED (observed in a run recorded here), CODE-READ (established by reading the source, no run), HYPOTHESIS, NOT TESTED.

## 1. Mandate

The user's instruction, verbatim: "the next workstream is the network-redesign study, beginning with evidence/reconciliation rather than implementation. The study should specifically resolve the DEBT-039 cross-sandbox egress finding, then establish what changes are actually required before touching C2 or A1."

Carried constraints: the invariant of reconciliation §17.4 (quoted in section 4); the frozen addendum and checklist; the Stage 5 decision (`sandbox-fabric` explicitly incomplete, reconciliation §19.4) is not reopened; A9/C3, D9 and Dependabot remain separate tracks and were not started.

## 2. Summary

1. **DEBT-039 is resolved as a finding.** It is reproducible (3 of 3 baseline runs), its mechanism is established from the code and consistent with every probe, and it is exploitable **without being handed the port** (a 2.3 s scan of the ephemeral range found the sibling's proxy) and on **both request paths** (`CONNECT` and plain HTTP). Two caveats left open in reconciliation §17.2 are closed.
2. **The cause is two facts together:** every networked sandbox's `AllowlistProxy` listens on the one shared network's gateway (`docker_backend.py`, `create()`), and the proxy discards the caller's address (`_net_proxy.py:82`, `client, _addr = server_sock.accept()`), so it cannot tell whose request it is serving. Its allowlist is per instance, so using the sibling's proxy means using the sibling's policy.
3. **A per-sandbox network alone does not meet "the proxy is the only path out".** A scratch experiment shows it removes the sibling-proxy path (the sibling's gateway is unreachable), but a container can still reach **any host service bound to `0.0.0.0`** through its own gateway. That is a distinct fact (F6), and it is true of the current topology too. The user has since ruled that F6 is in C2's scope (section 7), so a per-sandbox network by itself is insufficient.
4. **Per-sandbox networks have a capacity ceiling:** with Docker's default address pools, 29 additional internal networks were created before the daemon refused (F8).
5. **A1 needs no code change of its own.** It is blocked behind two other gates: the direct `NET_NAMESPACE` test (test-only) and the C2 network gate (needs the redesign). See section 5.
6. **Two behaviors listed as unexplained in reconciliation §17.5 are explained and are not defects in `AllowlistProxy`:** the plain-HTTP `403` is the host's upstream (F10), and the `test_net_proxy.py` flake is a test that assumes one `recv()` returns a whole response (F9).

## 3. Evidence

| ID | Finding | Status | Evidence |
|---|---|---|---|
| F1 | Sandbox B (allowlist `example.org`) obtains a tunnel to `example.com`, permitted only by sandbox A's allowlist, through A's proxy | VERIFIED | The verbatim §17.7 probe (Appendix A.1, extracted from the reconciliation document) ran 3 times: B's own proxy → `example.com` `403`; B's own proxy → `example.org` `200`; **A's proxy → `example.com` `200`**, each run |
| F2 | Mechanism: all proxies bind the shared gateway and the proxy cannot identify its caller | CODE-READ + VERIFIED | `docker_backend.py`, `create()`, the `if request.policy.allowed_hosts:` branch: `gateway_ip = await _ensure_sandbox_network()`, `AllowlistProxy(bind_ip=gateway_ip, …)`, `network_mode = "ocbrain-sandbox-net"`. `_net_proxy.py:82`: the peer address from `accept()` is bound to `_addr` and never used. `_is_allowed()` consults only `self._allowed`. Consistent with F1 and F3 |
| F3 | B finds A's proxy **without being told its port** | VERIFIED | Appendix A.2: B scanned the gateway's 28,232 ephemeral ports in 2.3 s; open ports were B's own proxy, A's proxy and a host service; `CONNECT example.com` through A's port returned `200`. A second run (A.3) again found A's proxy as the only candidate. Closes the §17.2 caveat "discovery by scanning was not demonstrated" |
| F4 | The plain-HTTP path has the same exposure | VERIFIED | Appendix A.3, deterministic local upstream (an HTTP server on the **host's loopback**): A allowed `127.0.0.1`, B did not. `GET http://127.0.0.1:<port>/` through B's own proxy → `403`; through A's proxy → `200 OK`. Closes the §17.2 caveat "only `CONNECT` was tried". Side effect: a proxy whose allowlist names a loopback address is a pivot into host-local services |
| F5 | Scope of the exposure | CODE-READ | Only a sandbox created with non-empty `allowed_hosts` joins the shared network (others get `--network none`). `check_admission()` currently rejects any request that sets `allowed_hosts` (`NETWORK_ALLOWLIST` is withdrawn), so the path is reachable by calling `create()` directly. A search of the repository found no importer of `core.sandbox` outside `tests/` and `core/sandbox/` (re-checked this session) |
| F6 | **A sandbox on the shared network reaches any host service bound to `0.0.0.0`** (or to the bridge address); loopback-only services are not reachable | VERIFIED | A.2: a listener on `0.0.0.0` accepted a connection from the sandbox via the gateway IP (the host side logged the container's address). A.3: a listener on `127.0.0.1` refused (`ConnectionRefusedError`). The gateway is a host address, so this is the topology's own behavior, independent of DEBT-039 |
| F7 | A **per-sandbox** internal network, with each proxy bound to its own gateway, removes the sibling-proxy path | VERIFIED (simulated) | A.4, plain listeners standing in for proxies, raw `docker network create --internal -o …enable_icc=false`. From a container on net B: own gateway:port **connected**; sibling's gateway:port **failed (`OSError`; the errno was not captured, and a missing route is the expected cause but was not verified)**; the `0.0.0.0` service via the sibling's gateway failed; the `0.0.0.0` service via its **own** gateway **connected** (F6 persists); the loopback service via its own gateway refused. Real `AllowlistProxy` instances were not used, so this proves the topology, not an implementation |
| F8 | Capacity of per-sandbox networks under Docker's default address pools | VERIFIED | 29 `--internal` networks were created, then `all predefined address pools have been fully subnetted`. The pre-existing `ocbrain-sandbox-net` and the default bridge are not counted. No `daemon.json` on this host. All created networks were removed afterwards |
| F9 | Sandbox containers run as **uid 0 with Docker's default capability set, including `NET_RAW`**; `_build_create_args` has no `--cap-drop` | VERIFIED | The same flags (`--read-only`, `--security-opt no-new-privileges`) gave `uid 0`, `CapEff 00000000a80425fb`: `NET_RAW` true, `NET_BIND_SERVICE` true, `NET_ADMIN` false, `SYS_ADMIN` false. Source: `docker_backend.py`, `_build_create_args`. Whether `NET_RAW` allows source-address or ARP spoofing on the bridge was **not tested** |
| F10 | The plain-HTTP `403` seen during the C2 work comes from the host's upstream, not from `AllowlistProxy` | VERIFIED | A direct plain-HTTP request from the host to `example.com` and to `example.org` (no proxy involved), with and without a `User-Agent`, returned `HTTP/1.1 403 Forbidden`. The proxy forwards what the upstream says |
| F11 | The `test_net_proxy.py` flake is a test-side assumption, and the proxy loses no data | VERIFIED (cause); NOT EXPLAINED (rate) | The two failing tests assert on a **single** `recv(4096)`: `assert resp.endswith(b"ok")` (line 70) and `assert tunneled.endswith(b"ok")` (line 83). A failing run captured `resp = b'HTTP/1.0 200 OK\r\nServer: …\r\nContent-Length: 2\r\n\r\n'`, i.e. headers only: the stdlib handler writes headers and body separately, the proxy relays each chunk as it arrives, and one `recv()` can return only the first. Reading to EOF was complete in **300 of 300** warm requests and **20 of 20** cold-process requests (no data lost). Measured rates: 6 of 300 warm requests returned a partial first `recv()`; 0 of 20 cold-process requests; the standalone file failed in 4 of 10 runs, and again in each of 3 later loops. **Why the pytest rate is higher than the warm-loop rate was not determined** |

## 4. Reconciliation against the frozen checklist

The invariant (reconciliation §17.4): "A sandbox must not be able to reach or use another sandbox's egress proxy, directly or indirectly, and its outbound policy must be enforced independently of sibling sandboxes."

**C2 (network bypass coverage; invariant: "with allowlisting active, the proxy is the *only* path out, not merely 'the proxy enforces its rules when used'").** Bullet by bullet:

| C2 bullet | Where it stands | Basis |
|---|---|---|
| Raw connection bypassing `HTTP_PROXY` fails | Not re-examined here; previously tested (reconciliation §14) | n/a |
| Docker bridge/gateway isn't a usable route | The earlier test covered the gateway as a route **beyond the host**. F6 shows the gateway also reaches **host-local services**. The user has ruled that C2 **does** cover it (section 7, decision 2): F6 is in scope | F6 |
| Another reachable container can't relay egress | Containers cannot reach each other (ICC off), but a sibling's **proxy** is a relay: this is DEBT-039 | F1 to F4 |
| `request.env` proxy values are overridden | Not re-examined here | n/a |

**A1 (`NETWORK_ALLOWLIST ∈ supported ⟹ NET_NAMESPACE ∈ supported`; test: admission-layer test plus an integration test that the request reaches the proxy path).** A1's own mechanism (the paired-claim invariant) is sound and tested. A1 is BLOCKED only because both capabilities it pairs are withdrawn. Re-claiming them needs:

- `NET_NAMESPACE`: a direct committed gate (reconciliation §17.8): the sandbox's netns differs from the host's, and concurrently created sandboxes have pairwise-distinct netns. This is a **test-only change**; the implementation is unchanged.
- `NETWORK_ALLOWLIST`: the C2 gate must pass, which is where the redesign is needed.

**B3 (no second policy surface; forbidden shortcut: "raw `iptables`/Docker-native network policy standing in for `_net_proxy.py`").** Any design must keep `AllowlistProxy` as the policy owner. Whether a host firewall rule may be a *supplement* that only limits which ports a sandbox can reach is not settled by the text (section 7, decision 3).

**B4 / file-touch.** This study changes none of the files in B4's list. Implementation of a redesign would legitimately touch `_net_proxy.py` and the topology (the user's own statement of the redesign's scope, reconciliation §17.4), which is outside the original DockerBackend workstream's boundary and needs its own authorization.

## 5. What is actually required, and what is not

**Required, derived from the evidence:**

1. **R1 (mandatory, section 7).** No sandbox may have a network path to another sandbox's proxy listener, or the proxy must refuse every caller but its own sandbox. F1 to F4 show the current topology does neither. F7 shows R1 is achievable at topology level with per-sandbox networks.
2. **R2 (mandatory; decided by the user, section 7).** F6 is in C2's scope: a networked sandbox must have no network path other than its proxy, so host-local services reachable through the gateway must be closed. R1 alone is not enough, because F6 survives a per-sandbox network (F7).
3. **R3.** If per-sandbox networks are used: a lifecycle that fits the existing invariants (D10: every acquired resource is cleaned or retained in a destroyable handle; D11: race-safe bookkeeping), and a capacity answer for F8 (an address-pool setting or an explicit small subnet per sandbox, or a stated concurrency limit). The shared network's lifecycle (reconciliation DEC-4, still undecided) is subsumed by this.
4. **R4.** If caller identity at the proxy is used instead: a source identity that an in-sandbox process cannot forge. F9 shows sandboxes run as uid 0 with `NET_RAW`, so a source-address check alone is weak until that is tested or the capability is dropped.
5. **R5.** The regression gates in section 6, none of which exists yet.

**Not required (by this evidence):**

- No change to `admission.py` or `contracts.py`. A1's mechanism already exists.
- No change to `NET_NAMESPACE`'s implementation, only its direct test.
- No fix inside `AllowlistProxy` for the plain-HTTP `403` (F10) or for the flake (F11): the first is the host's upstream, the second is the test.
- `NamespaceBackend` was **not examined**; this study concerns `DockerBackend`'s topology only.

**Option space (considerations, not decisions).** O1 by itself is insufficient, because F6 persists (R2). The user has asked that no option be chosen yet (section 7).

| Option | Sibling-proxy path (F1 to F4) | Other effects (evidence) | Open |
|---|---|---|---|
| O1: per-sandbox internal network, proxy bound to its own gateway | Removed at topology level (F7) | F6 persists (F7); capacity 29 with defaults (F8); needs a per-sandbox network lifecycle (R3) | A real proxy under real concurrency has not been tested |
| O2: keep the shared network, add a caller-identity check in the proxy | Removed only if the identity is unforgeable | No capacity problem; the proxy starts before its container has an address, so this needs addresses assigned up front; F6 persists; F9 makes source identity weak | Spoofing with `NET_RAW` untested |
| O3: reach the proxy over a channel that is not an IP network (for example a bind-mounted Unix socket and a relay inside the sandbox) | Removed by construction (no network listener to reach) | Could allow `--network none` and so remove F6; `AllowlistProxy` listens on TCP only today, so `_net_proxy.py` changes; needs a component inside the image | The base image's contents and the relay's own attack surface were not examined |
| O4: host firewall rules restricting what a sandbox can reach | Could remove it | Needs host privilege; B3 limits its role (section 4) | B3 reading; unreviewed |

## 6. Gates the redesign must pass (proposed; none added)

- **G1, the concurrent A/B regression.** Two concurrent networked sandboxes with deliberately different allowlists; B must not obtain A's egress by any of: a port it was handed, a port it found by scanning, `CONNECT`, plain HTTP. The shape is Appendix A.1 to A.3. This is the gate for DEBT-039 and C2.
- **G2, `NET_NAMESPACE`.** Reconciliation §17.8. Passing it re-earns `NET_NAMESPACE` only; it does not resurrect `NETWORK_ALLOWLIST` or C2.
- **G3, host-service scope (required; F6 is in C2's scope, section 7):** a networked sandbox cannot reach a `0.0.0.0`-bound host listener, with a loopback control.
- **G4, lifecycle and capacity** (if per-sandbox networks): no leaked network after each D10 failure point; behavior at and beyond the pool limit is defined and tested.
- **Separately,** and not a redesign gate: the two `test_net_proxy.py` tests should read the response to EOF or to `Content-Length`.

## 7. Decisions

**Decided by the user (October 3 2026), with the wording kept where it matters:**

1. **Where the study lives.** "Keep it on a new branch from `sandbox-fabric`, not `main`." The branch is `study/sandbox-network-redesign`, from `sandbox-fabric` at `1b829fc`. **Push: yes. Merge into `main`: no, not yet**: it "should remain an explicit study branch until the redesign decision and implementation work are separately authorized".
2. **F6 is in C2's scope.** The recorded decision: "C2 includes host-local services reachable through the sandbox gateway. F6 is therefore in redesign scope and must be closed before `NETWORK_ALLOWLIST` can be re-supported." The user drew these consequences: R1 and R2 are both mandatory; G3 is a required regression gate; **O1 by itself is insufficient**; F6 is "not another manifestation of DEBT-039" but a separate topology-level bypass that C2 still covers.
3. **No option is chosen.** O1 to O4 stay undecided "pending the next design study": "the study establishes what must be true; a subsequent design workstream chooses how to make it true."
4. **A1 stays blocked, not broken.** No change to `admission.py`, `contracts.py` or the `NET_NAMESPACE` implementation follows from this study. A1's remaining prerequisites are the direct `NET_NAMESPACE` test and a C2-compliant network design.

**Still open (the user's reply did not address them):**

- **B3.** May a host firewall rule be a supplement that only narrows which ports a sandbox can reach, with `AllowlistProxy` still owning the policy?
- **The flake.** Fix the two `test_net_proxy.py` tests (read the response to EOF or to `Content-Length`) in a separate small change?
- **Hardening.** F9 (no capability dropping) as its own item?
- **Registration.** F6 is separate from DEBT-039, so should it be registered as its own debt in `KNOWN_ISSUES.md`? Until it is, DEBT-039's text does not mention it.

## 8. Corrections to earlier records (the earlier text is not edited)

- Reconciliation §17.2 caveats: "discovering it by scanning … was not demonstrated" is closed by F3; "only `CONNECT` tunnelling was tried" is closed by F4. The "likely mechanism" paragraph is now CODE-READ and consistent with the probes (F2).
- Reconciliation §17.5, "the plain-HTTP path of `_net_proxy.py` has two separate unexplained behaviors": the `403` is F10 (host upstream) and the intermittent assertion is F11 (test-side). Neither was diagnosed as a proxy defect.
- Handoff version 3 listed "the cause of the `test_net_proxy.py` flake" as UNKNOWN: the cause of the failing assertion is now known (F11); the pytest-run rate is not.

## 9. Not examined

`NamespaceBackend`; `AF_VSOCK` or any other non-TCP route (the A9 track); IPv6 and UDP; the proxy's own DNS resolution of upstream names; whether `NET_RAW` allows spoofing on the bridge (F9); an implementation of any option with the real `AllowlistProxy`; behavior under real concurrency beyond two sandboxes.

## Appendix A. Scratch probes (verbatim; not part of the test suite)

Run with the Docker daemon up and `OCBRAIN_SANDBOX_DOCKER_IMAGE=ocbrain-test/base:local`. They create and remove their own sandboxes and networks; each run ended with 0 containers and 0 shared-network endpoints.

### A.1 The verbatim §17.7 probe, extracted from the reconciliation document by script and run unmodified (3 runs)

See reconciliation §17.7: the script is the first fenced `python` block there. It was extracted programmatically, with no edits.

### A.2 Study probe 1 (scratch, not in the repo): B scans the gateway for a sibling proxy; plain GET through each; a `0.0.0.0` host service

```python
"""Scratch study probe (NOT in the repo). Sandbox B (allowlist {example.org}) is NOT told A's port.
H2: can B discover A's proxy by scanning the gateway? H3: does plain HTTP behave like CONNECT through
a sibling's proxy? H4: can B reach an arbitrary host service listening on 0.0.0.0 via the gateway IP?"""
import asyncio, sys, shutil, socket, threading
sys.path.insert(0, "/home/claude/ocbrain-v4.1")
from core.sandbox.backends.docker_backend import DockerBackend, _ensure_sandbox_network
from core.sandbox.contracts import SandboxPolicy, SandboxRequest

B_SCRIPT = r'''
import asyncio, os, socket, time, urllib.parse
own = urllib.parse.urlparse(os.environ["HTTPS_PROXY"]); gw = own.hostname; own_port = own.port
host_port = int(os.environ["HOST_PORT"])

def talk(port, payload, rd=300):
    try:
        s = socket.create_connection((gw, port), timeout=6); s.sendall(payload); s.settimeout(10)
        d = s.recv(rd); s.close(); return d.split(b"\r\n")[0].decode(errors="replace")
    except Exception as e:
        return "ERR " + type(e).__name__

async def scan(lo, hi, conc=800):
    sem = asyncio.Semaphore(conc); open_ports = []
    async def one(p):
        async with sem:
            try:
                r, w = await asyncio.wait_for(asyncio.open_connection(gw, p), 0.6)
                w.close(); open_ports.append(p)
            except Exception:
                pass
    await asyncio.gather(*(one(p) for p in range(lo, hi + 1)))
    return sorted(open_ports)

t0 = time.time()
found = asyncio.run(scan(32768, 60999))
print("H2 scan of gateway %s ports 32768-60999: %.1fs; open ports: %s (own proxy = %d)" % (gw, time.time() - t0, found, own_port))
for p in found:
    tag = "OWN " if p == own_port else "OTHER"
    c = talk(p, b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
    h = talk(p, b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n")
    print("   %s port %d: CONNECT example.com -> %s | plain GET example.com -> %s" % (tag, p, c, h))
# plain HTTP, allowed host for B itself, via its own proxy (control)
print("   control OWN plain GET example.org -> %s" % talk(own_port, b"GET http://example.org/ HTTP/1.1\r\nHost: example.org\r\nConnection: close\r\n\r\n"))
try:
    s = socket.create_connection((gw, host_port), timeout=4); s.sendall(b"HELLO-FROM-SANDBOX"); s.close(); print("H4 arbitrary host service on 0.0.0.0:%d via gateway: CONNECTED" % host_port)
except Exception as e:
    print("H4 arbitrary host service on 0.0.0.0:%d via gateway: %s" % (host_port, type(e).__name__))
'''

async def main():
    got = []
    lst = socket.socket(); lst.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); lst.bind(("0.0.0.0", 0)); lst.listen(4); lst.settimeout(120)
    host_port = lst.getsockname()[1]
    def acc():
        try:
            c, a = lst.accept(); got.append((a, c.recv(64))); c.close()
        except Exception: pass
    threading.Thread(target=acc, daemon=True).start()
    be = DockerBackend(image_ref="ocbrain-test/base:local")
    for d in ("/tmp/st-A", "/tmp/st-B"): shutil.rmtree(d, ignore_errors=True)
    reqA = SandboxRequest(command=("sleep", "150"), policy=SandboxPolicy(workspace_dir="/tmp/st-A", allowed_hosts=("example.com",), timeout_sec=170))
    hA = await be.create(reqA); runA = asyncio.ensure_future(be.run(hA, reqA)); await asyncio.sleep(1.5)
    a_port = be._handles[hA.handle_id].proxy.port
    reqB = SandboxRequest(command=("python3", "-c", B_SCRIPT), env={"HOST_PORT": str(host_port)},
                          policy=SandboxPolicy(workspace_dir="/tmp/st-B", allowed_hosts=("example.org",), timeout_sec=150, max_pids=256))
    hB = await be.create(reqB); resB = await be.run(hB, reqB)
    print("[ground truth, not given to B: A's proxy port = %d; host service port = %d; gateway = %s]" % (a_port, host_port, await _ensure_sandbox_network()))
    print(resB.stdout.strip() or "(no stdout)")
    if resB.stderr.strip(): print("stderr:", resB.stderr.strip()[:400])
    print("host-side view of H4:", ("connection received from %s, payload %r" % (got[0][0], got[0][1])) if got else "NO connection received")
    await be.cancel(hA); await runA; await be.destroy(hA); await be.destroy(hB)
asyncio.run(main())
```

### A.3 Study probe 2 (scratch, not in the repo): deterministic host-loopback upstream; plain HTTP through the sibling's proxy; `0.0.0.0` versus loopback host services

```python
"""Scratch study probe 2 (NOT in the repo). Deterministic local upstream, no external dependency.
A allows {127.0.0.1} (its proxy can therefore dial HOST loopback); B allows {example.org}.
H3: plain HTTP via the sibling's proxy. H4b: scope of host-service reachability (0.0.0.0 vs 127.0.0.1)."""
import asyncio, sys, shutil, socket, threading, http.server
sys.path.insert(0, "/home/claude/ocbrain-v4.1")
from core.sandbox.backends.docker_backend import DockerBackend, _ensure_sandbox_network
from core.sandbox.contracts import SandboxPolicy, SandboxRequest

B_SCRIPT = r'''
import asyncio, os, socket, urllib.parse
own = urllib.parse.urlparse(os.environ["HTTPS_PROXY"]); gw = own.hostname; own_port = own.port
lo_port = int(os.environ["LOOP_PORT"]); any_port = int(os.environ["ANY_PORT"])
def talk(port, payload):
    try:
        s = socket.create_connection((gw, port), timeout=6); s.sendall(payload); s.settimeout(8)
        d = b""
        while True:
            c = s.recv(4096)
            if not c: break
            d += c
        s.close(); return d.decode(errors="replace").replace("\r\n", " | ")[:90]
    except Exception as e:
        return "ERR " + type(e).__name__
async def scan(lo, hi):
    sem = asyncio.Semaphore(800); out = []
    async def one(p):
        async with sem:
            try:
                r, w = await asyncio.wait_for(asyncio.open_connection(gw, p), 0.6); w.close(); out.append(p)
            except Exception: pass
    await asyncio.gather(*(one(p) for p in range(lo, hi + 1))); return sorted(out)
get = ("GET http://127.0.0.1:%d/ HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nConnection: close\r\n\r\n" % (lo_port, lo_port)).encode()
cands = [p for p in asyncio.run(scan(32768, 60999)) if p not in (own_port, any_port)]
print("B scanned the gateway; candidate ports other than its own proxy / the 0.0.0.0 service:", cands)
print("H3 plain GET http://127.0.0.1:<host-loopback-port>/ via B's OWN proxy ->", talk(own_port, get))
for p in cands:
    print("H3 same request via sibling candidate port %d ->" % p, talk(p, get))
for name, port in (("0.0.0.0-bound host service", any_port), ("127.0.0.1-bound host service (loopback)", lo_port)):
    try:
        s = socket.create_connection((gw, port), timeout=4); s.close(); r = "CONNECTED"
    except Exception as e:
        r = type(e).__name__
    print("H4b direct connect to %s via gateway %s:%d -> %s" % (name, gw, port, r))
'''

async def main():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header("Content-Length", "13"); self.end_headers(); self.wfile.write(b"HOST-LOOPBACK")
        def log_message(self, *a): pass
    lo = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=lo.serve_forever, daemon=True).start()
    anys = socket.socket(); anys.bind(("0.0.0.0", 0)); anys.listen(4)
    be = DockerBackend(image_ref="ocbrain-test/base:local")
    for d in ("/tmp/st2-A", "/tmp/st2-B"): shutil.rmtree(d, ignore_errors=True)
    reqA = SandboxRequest(command=("sleep", "100"), policy=SandboxPolicy(workspace_dir="/tmp/st2-A", allowed_hosts=("127.0.0.1",), timeout_sec=120))
    hA = await be.create(reqA); runA = asyncio.ensure_future(be.run(hA, reqA)); await asyncio.sleep(1.5)
    a_port = be._handles[hA.handle_id].proxy.port
    reqB = SandboxRequest(command=("python3", "-c", B_SCRIPT), env={"LOOP_PORT": str(lo.server_port), "ANY_PORT": str(anys.getsockname()[1])},
                          policy=SandboxPolicy(workspace_dir="/tmp/st2-B", allowed_hosts=("example.org",), timeout_sec=100, max_pids=256))
    hB = await be.create(reqB); resB = await be.run(hB, reqB)
    print("[ground truth: A's proxy port = %d (A allows 127.0.0.1 only); gateway = %s]" % (a_port, await _ensure_sandbox_network()))
    print(resB.stdout.strip() or "(no stdout)")
    if resB.stderr.strip(): print("stderr:", resB.stderr.strip()[:400])
    await be.cancel(hA); await runA; await be.destroy(hA); await be.destroy(hB)
asyncio.run(main())
```

### A.4 Per-sandbox-network experiment (scratch, not in the repo; touches no repository code)

```python
"""Scratch experiment (NOT in the repo, NO repo code touched): would a PER-SANDBOX internal network, with each
sandbox's proxy bound to ITS OWN gateway, satisfy the DEBT-039 invariant? Simulated with plain listeners."""
import subprocess, socket, threading, json, sys
IMG = "ocbrain-test/base:local"
def sh(*a): return subprocess.run(a, capture_output=True, text=True)
def mk(name):
    sh("docker", "network", "rm", name)
    r = sh("docker", "network", "create", "--internal", "-o", "com.docker.network.bridge.enable_icc=false", name)
    assert r.returncode == 0, r.stderr
    return sh("docker", "network", "inspect", name, "--format", "{{(index .IPAM.Config 0).Gateway}}").stdout.strip()
def listen(ip):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((ip, 0)); s.listen(8)
    threading.Thread(target=lambda: [s.accept()[0].close() for _ in range(64)], daemon=True).start()
    return s.getsockname()[1]
gwA, gwB = mk("xpn-a"), mk("xpn-b")
pA, pB, pX, pL = listen(gwA), listen(gwB), listen("0.0.0.0"), listen("127.0.0.1")
print("gateways: A=%s B=%s | simulated proxies: A=%s:%d B=%s:%d | extra host listeners: 0.0.0.0:%d 127.0.0.1:%d" % (gwA, gwB, gwA, pA, gwB, pB, pX, pL))
probe = r'''
import socket
def t(ip, port):
    try:
        s = socket.create_connection((ip, port), timeout=3); s.close(); return "CONNECTED"
    except Exception as e: return type(e).__name__
for label, ip, port in %s:
    print("  %%-58s %%s" %% (label, t(ip, port)))
''' % repr([
  ("own simulated proxy      (B-gw:pB)", gwB, pB),
  ("SIBLING's simulated proxy (A-gw:pA)  <- DEBT-039 path", gwA, pA),
  ("0.0.0.0 host service via own gateway", gwB, pX),
  ("0.0.0.0 host service via sibling's gateway", gwA, pX),
  ("127.0.0.1 host service via own gateway", gwB, pL),
])
r = sh("docker", "run", "--rm", "--network", "xpn-b", IMG, "python3", "-c", probe)
print("from a container on xpn-b (per-sandbox internal network):"); print(r.stdout.rstrip() or r.stderr[:300])
sh("docker", "network", "rm", "xpn-a"); sh("docker", "network", "rm", "xpn-b")
print("cleanup: leftover xpn nets =", sh("docker", "network", "ls", "--format", "{{.Name}}").stdout.count("xpn-"))
```

## Appendix B. Observed output (this host, October 3 2026)

```
A.1 baseline, 3 runs (ports vary per run: 35405, 35025, 36609):
1 B's OWN proxy -> example.com  (NOT in B's allowlist): HTTP/1.1 403 Forbidden
2 B's OWN proxy -> example.org  (in B's allowlist)    : HTTP/1.1 200 Connection Established
3 A's proxy     -> example.com  (in A's allowlist only): HTTP/1.1 200 Connection Established

A.2:
[ground truth, not given to B: A's proxy port = 41559; host service port = 46193; gateway = 172.18.0.1]
H2 scan of gateway 172.18.0.1 ports 32768-60999: 2.3s; open ports: [35963, 41559, 46193] (own proxy = 35963)
   OWN  port 35963: CONNECT example.com -> HTTP/1.1 403 Forbidden | plain GET example.com -> HTTP/1.1 403 Forbidden
   OTHER port 41559: CONNECT example.com -> HTTP/1.1 200 Connection Established | plain GET example.com -> HTTP/1.1 403 Forbidden
   OTHER port 46193: CONNECT example.com -> ERR TimeoutError | plain GET example.com -> ERR TimeoutError
H4 arbitrary host service on 0.0.0.0:46193 via gateway: CONNECTED
host-side view of H4: connection received from ('172.18.0.3', 40366), payload b''

A.3:
[ground truth: A's proxy port = 35791 (A allows 127.0.0.1 only); gateway = 172.18.0.1]
H3 plain GET http://127.0.0.1:<host-loopback-port>/ via B's OWN proxy -> HTTP/1.1 403 Forbidden
H3 same request via sibling candidate port 35791 -> HTTP/1.0 200 OK | Server: BaseHTTP/0.6 Python/3.12.3 | ...
H4b direct connect to 0.0.0.0-bound host service via gateway 172.18.0.1:44455 -> CONNECTED
H4b direct connect to 127.0.0.1-bound host service (loopback) via gateway 172.18.0.1:40791 -> ConnectionRefusedError

A.4 (from a container on xpn-b):
  own simulated proxy      (B-gw:pB)                         CONNECTED
  SIBLING's simulated proxy (A-gw:pA)  <- DEBT-039 path      OSError
  0.0.0.0 host service via own gateway                       CONNECTED
  0.0.0.0 host service via sibling's gateway                 OSError
  127.0.0.1 host service via own gateway                     ConnectionRefusedError

F8: 29 internal networks created; then: all predefined address pools have been fully subnetted
F9: uid: 0 | CapEff: 00000000a80425fb | NET_RAW True, NET_BIND_SERVICE True, NET_ADMIN False, SYS_ADMIN False
F10: direct from host, no proxy: example.com no-UA -> 403, with-UA -> 403; example.org no-UA -> 403, with-UA -> 403
F11: single-recv partial 6/300 (warm loop); cold processes 0/20; read-to-EOF complete 300/300 and 20/20; failing test captured resp = headers only
```
