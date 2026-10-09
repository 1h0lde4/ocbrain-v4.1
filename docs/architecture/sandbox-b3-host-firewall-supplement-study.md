# B3 study: can a host firewall be a supplementary reachability restriction? (DEBT-039, F6, option O4)

- **Date:** October 3 2026
- **Status:** evidence phase complete. **No design is selected, nothing is implemented, and no repository code, test, capability or contract was changed.** This document is the only file the branch adds.
- **Base:** `study/sandbox-network-redesign` at `ee525d9` (itself on `sandbox-fabric` at `1b829fc`). Branch: `study/b3-host-firewall-supplement`.
- **Environment (everything below was observed on this one host):** Ubuntu 24.04, kernel `6.18.44-fc-v64` (a Firecracker microVM, booted with `ipv6.disable=1`), Docker Engine 29.1.3 ("Firewall Backend: iptables"), iptables v1.8.10 **(nf_tables variant)**, nftables 1.0.9, the controller running as uid 0, `INPUT` policy ACCEPT, no other firewall manager observed.
- **Status vocabulary:** VERIFIED (observed in a run recorded in the appendices), CODE-READ, NOT TESTED. Finding numbers continue those of the network-redesign study (F1 to F11).
- **Related open items:** PR #48 (DEBT-040, the F6 row), PR #49 (DEBT-041, the F9 row) and PR #50 (the `test_net_proxy.py` fix) were opened in the same session; none is merged.

## 1. Mandate

The user's instruction, verbatim: "Can a host firewall mechanism be used only as a supplementary reachability restriction, while `AllowlistProxy` remains the sole owner of outbound policy?" The study was to determine, from the actual Docker/network topology and repository constraints: "whether such a firewall rule can be installed safely; what privileges it requires; whether it can distinguish sandbox traffic reliably; whether it creates a second policy surface, violating B3; whether it can close F6 without replacing `AllowlistProxy`; whether it changes the viability of O4 and/or hybrid designs; persistence/lifecycle behavior under D10/D11; interaction with concurrent sandboxes; IPv4/IPv6 implications that matter to this decision; exact regression tests required." And: "No implementation yet."

Carried decisions (study §7): F6 is in C2's scope; R1 and R2 are mandatory; G3 is a required gate; O1 alone is insufficient; no option is chosen; A1 stays blocked, not broken.

## 2. Summary

1. **Yes, technically and conditionally.** A host firewall rule can close F6 without replacing `AllowlistProxy`, if it (a) is keyed on the sandbox's own **bridge interface** rather than on source addresses, (b) contains no destination policy (only "this interface may reach the host at TCP port P"), and (c) is verified by behavior at run time. On two per-sandbox networks with real `AllowlistProxy` instances, bridge-keyed `INPUT` rules closed TCP and UDP access to a `0.0.0.0` host listener, left each proxy's allow/deny decisions untouched (`200` for the allowed host, `403` for the other) and contained no hostname (F14, F15).
2. **It cannot close DEBT-039 by itself on the shared network.** Rules keyed on each sandbox's source address stop honest sibling traffic, but forged-source packets from a sandbox with `NET_RAW` (Docker's default) matched another sandbox's `ACCEPT` rule (counter 5 → 15); with `--cap-drop NET_RAW` the raw socket could not even be created (F16). So **O4 on the shared network depends on DEBT-041 (F9) and is equivalent to O2**; O4 as a supplement to per-sandbox networks does not.
3. **The traffic that matters never reaches Docker's documented hook.** Container-to-gateway packets traverse `INPUT`, not `FORWARD`/`DOCKER-USER`: a `DOCKER-USER` drop rule matched 0 packets and the connection succeeded (F12). `INPUT` is not managed by Docker.
4. **Whether this satisfies B3 is an interpretation the user must rule on.** The supplement does not "stand in for" the proxy (the proxy is still what produces every allow and deny), and the responsibility it carries (which host-local endpoints a sandbox can reach) is not owned by the proxy today, which is the gap F6 exposes. But the base prompt says a Docker-idiomatic mechanism that needs a second policy surface is a design question to raise, not decide silently, and B3's "duplicates a responsibility" test is a judgment. Section 3 states seven conditions (S1 to S7) under which the study considers a supplement consistent with B3.
5. **A firewall adds an authority boundary and global host state.** Installing a rule needs `CAP_NET_ADMIN` in the host network namespace (F13); the Docker socket alone suffices through a helper container, so it is not new capability on a Docker host but it is a new actor and a governance decision (LAW 1, `PROJECT_INSTRUCTIONS` §6.1). Rules outlive the controller, the daemon and the network (F18); stale rules can be inherited by a recycled bridge name (F19); and no firewall code exists anywhere in the repository (F25).
6. **A static design removes most of that lifecycle cost.** One wildcard rule pair installed once (`-i ocbsbx+`: accept the proxy port, drop the rest), each sandbox on its own network with a bridge named `ocbsbx<id>`, and every proxy bound to a fixed port on its own gateway worked, with no per-sandbox rules to create or reap (F20). Its hazards are real and tested: a bridge whose name misses the prefix is **not covered and fails open** (F21), and the rules must be verified present, which a behavioral canary can do without firewall privilege (2.3 s here, F22). **Correction found afterwards (F28): the static rule as first tested had no destination match, and a sandbox with `NET_RAW` could use it to reach a sibling's gateway and the host's primary address on the proxy port. The corrected rule adds `-m addrtype --dst-type LOCAL --limit-iface-in`, which closed both while the sandbox's own proxy stayed reachable.**
7. **A non-firewall route to closing F6 appeared in the evidence.** Docker's `inhibit_ipv4` and `gateway_mode_ipv4=isolated` options leave the host bridge with no IPv4 address, so there is nothing for a sandbox to reach (F23). That removes the host-side address the proxy binds to today, so the proxy would have to run elsewhere (for example in a sidecar container). This is **unevaluated**; it is listed because it would avoid the B3 question altogether.
8. **`NamespaceBackend` on `main` shows F6 too** (F24): a sandbox run with `allowed_hosts` connected to a `0.0.0.0` listener through its gateway. DEBT-040 (PR #48) was updated to say so. This study does not examine that backend further.
9. **IPv6 could not be tested here** (the host boots with `ipv6.disable=1`). The decision does not hinge on it, but a design must assert it (F26, section 5, question 9).

## 3. Reconciliation against B3

**The frozen text.**
- B3 checklist item: "`DockerBackend` calls these; it defines no parallel admission function, proxy, or request/result shape". Invariant: "nothing in `docker_backend.py` duplicates a responsibility already owned by `admission.py`/`_net_proxy.py`/`contracts.py`". Forbidden shortcut: "raw `iptables`/Docker-native network policy standing in for `_net_proxy.py`".
- Base prompt (hierarchy position 1), the overriding rule: `allowed_hosts` enforcement is "`_net_proxy.py` called from a Docker network context, not a new proxy, not Docker's own network-policy primitives standing in for it. If implementing something Docker-idiomatic would require a second policy surface, stop and treat that as a design question to raise, not a decision to make silently inside this session." This study is that raising.
- Addendum, C2: the existing test "does not prove … that the Docker gateway can't serve as an alternate route"; it names "container network config" as part of the enforcement path.
- Repository precedent: `NamespaceBackend` builds its own host-side topology with root-only `ip netns`/`ip link` calls (6 call sites) and binds the proxy to a host-side veth address. **No file in `core/` uses `iptables`, `ip6tables` or `nft`** (F25). Privileged mutation of host networking has precedent; firewall rules do not.

**The test the study applied.** B3 prohibits a *second policy surface*. The study separates two things: **destination policy** (which hosts a sandbox may reach), owned by `AllowlistProxy`; and **local reachability** (which endpoints of the host itself a sandbox may reach), owned by nothing today. A rule is a supplement only if it carries the second and never the first.

| Question | Result | Evidence |
|---|---|---|
| Does a rule encode any destination? | No. Its text is an interface name, a gateway address and a proxy port | F15 |
| Can it permit anything the proxy denies? | No. The only thing it permits is TCP to the proxy's own port; B's own proxy still answered `403` for a host outside B's allowlist | F14 |
| Can it deny anything the proxy would allow? | Only non-proxy local endpoints, which the proxy does not offer | F14 |
| Does changing the allowlist require a rule change? | No | F15 |
| Single source of truth for the port? | In per-sandbox rules the port comes from `proxy.port` (a drift fails closed, F15); in the static design it is one constant used by `proxy.start(port)` and the rule text (guarded by the canary, F22) | F15, F22 |
| Can the rules alone produce an allow/deny for a destination? | No: with the proxy absent a sandbox has nothing to talk to | by construction; F14 |

**Conditions the study considers sufficient for a supplement (S1 to S7).**
- **S1.** The rule carries no destination, hostname or protocol-level policy. The proxy remains the only component that decides destinations.
- **S2.** The rule is keyed on the sandbox's own ingress bridge interface, never on a source address that a sandbox could forge (F16).
- **S3.** Its only permit is TCP to the proxy's bound address and port, and the destination must be an address of the sandbox's own ingress interface (a per-sandbox `-d`, or in a static rule `-m addrtype --dst-type LOCAL --limit-iface-in`: F28); everything else from that interface is dropped (all protocols, by a catch-all).
- **S4.** The proxy port in the rule comes from the same constant or object as the proxy's bind, and a mismatch fails closed (F15).
- **S5.** Installation and removal are fail-closed in order (drop first, accept above it; accept removed first, drop last) and tied to the sandbox handle (D10/D11, section 5, question 7).
- **S6.** Enforcement is verified by behavior, not by the existence of a rule (`PROJECT_INSTRUCTIONS` §14.1, §14.4): a canary must fail closed (F22).
- **S7.** The firewall code is a separate, narrow module with its own review and its own entry in the file-touch boundary. `docker_backend.py` calls it; it does not grow rule logic of its own.

**Reading offered for ratification:** B3 forbids a firewall that *stands in for* the proxy or *duplicates the destination decision*; a supplement meeting S1 to S7 does neither. This is an interpretation of a frozen text, so it is put to the user (section 8, D1) and not applied.

## 4. Evidence

| ID | Finding | Status | Evidence |
|---|---|---|---|
| F12 | Container-to-gateway traffic (F6) traverses **`INPUT`**, not `FORWARD`/`DOCKER-USER`. A `DOCKER-USER` drop rule left the connection working with 0 packets matched; an `INPUT` drop rule blocked it and matched 3 packets | VERIFIED | Appendix B.1 (E1) |
| F13 | Installing a rule needs `CAP_NET_ADMIN` in the host network namespace: as `nobody`, and as root with `net_admin` removed from the bounding set, `iptables -I` failed with "Could not fetch rule set generation id: Permission denied" (rc 4); `iptables -S INPUT` (listing) failed the same way in both cases, so even reading the rules needs it, which a controller without the capability cannot do to verify them. A helper container started through the Docker socket (`--network host --cap-add NET_ADMIN`) installed a rule that was then present on the host | VERIFIED | B.1 (E2) |
| F14 | On **per-sandbox networks** with a real `AllowlistProxy` on each gateway and bridge-keyed `INPUT` rules (drop first, accept above it): a `0.0.0.0` host TCP listener went from `CONNECTED` to `TimeoutError`, a UDP datagram from delivered to not delivered, while the sandbox's own proxy kept working (`200`, with the upstream on the host's loopback, so the proxy's host-originated traffic is unaffected) and B's proxy still answered `403` for a host outside B's allowlist | VERIFIED | B.2 (E3) |
| F15 | The installed rules contained no hostname; a rule whose port differed from the proxy's made the sandbox's own proxy unreachable (`TimeoutError`): a drift fails **closed** | VERIFIED | B.2 (E3) |
| F16 | On the **shared network**, source-IP-keyed rules stopped B reaching A's proxy and the host listener for honest traffic, but five forged-source SYNs sent from B (default capabilities) raised A's `ACCEPT` rule counter from 5 to 15. The increase of 10 is the 5 forged SYNs plus, probably, 5 `RST`s from A's own stack answering the unsolicited SYN-ACKs; the two were not separated. With `--cap-drop NET_RAW` the raw socket failed with `PermissionError`. A completed connection under a forged address was **not** attempted | VERIFIED (acceptance of forged packets); NOT TESTED (a full forged session) | B.2 (E4) |
| F17 | 24 parallel workers inserting two rules each, then removing them: 48 of 48 rules present and 0 left afterwards, with **and without** `-w`. This is the nf_tables variant of iptables; the legacy variant was not tested | VERIFIED (nft variant) | B.3 (E5a) |
| F18 | Rules are kernel state: a controller killed with `SIGKILL` after installing a rule left it in place, and rules survived killing and restarting `dockerd` and `containerd` (2 rules before, during and after; Docker's chains and the network unchanged). A reboot or a firewall-manager reload was **not tested** | VERIFIED (crash, daemon restart); NOT TESTED (reboot, other managers) | B.3 (E5b, E5d) |
| F19 | Rules are keyed on the interface **name**. After `docker network rm`, the rules stayed; a new network recreated with the same bridge name and subnet inherited them (an unrelated listener on the old `ACCEPT`ed port was `CONNECTED`, another port `TimeoutError`). A network with a different bridge name was unaffected | VERIFIED | B.3 (E5c) |
| F20 | **Static design:** one wildcard pair `-i ocbsbx+ -p tcp --dport 3128 -j ACCEPT` / `-i ocbsbx+ -j DROP`, installed once; two sandboxes on separate networks named `ocbsbx1` and `ocbsbx2`, each proxy bound to `<its gateway>:3128`: A's allowed request `200`, B's disallowed `403`, B to A's gateway:3128 `OSError` (no route), the `0.0.0.0` host TCP listener `TimeoutError`, UDP not delivered. The bridge interface exists right after `docker network create`, before any container | VERIFIED | B.4 (E7) |
| F21 | **Naming drift fails open:** a sandbox on a bridge named `ocbnope1` (no prefix match) connected to the `0.0.0.0` host listener. A fixed-port collision fails closed in both directions: a wildcard listener already on the port makes `proxy.start(port)` raise `OSError`, and a wildcard bind while a proxy holds the port raises `OSError` | VERIFIED | B.4 (E7b) and the collision mini-test |
| F22 | A **behavioral canary** (a throwaway container on a sandbox bridge trying a non-proxy host port) reported the static rules enforced in 2.3 s including container start; it needs Docker access only, not firewall privilege | VERIFIED (feasibility); the failure path (rules absent) was shown by F21's open case, not by a canary run | B.4 (E7c) |
| F23 | Docker-native alternative: with `-o com.docker.network.bridge.inhibit_ipv4=true`, and separately with `gateway_mode_ipv4=isolated`, the host bridge had **no IPv4 address** and Docker recorded no gateway; the control network had `10.231.9.1` and the host listener was reachable. A sandbox then has no host address to reach, but the proxy has no host-side address to bind to. Whether a sibling or sidecar container is reachable on such a network (ICC) was **not tested** | VERIFIED (addressing); NOT TESTED (sidecar reachability) | B.5 (E6b) |
| F24 | `NamespaceBackend` on `main` shows F6: a sandbox run with `allowed_hosts` reached a `0.0.0.0` listener through its gateway `10.200.0.1` (the host saw the connection from `10.200.0.2`); a `127.0.0.1` listener refused. Observed once, by a scratch probe against the unmodified backend; it is otherwise not audited | VERIFIED (once, one host) | B.5 (E8) |
| F25 | No file in `core/` uses `iptables`, `ip6tables` or `nft`; `NamespaceBackend` performs root-only host-network changes through `ip` (6 call sites) | CODE-READ | `grep` over `core/`; `namespace_backend.py` |
| F26 | **IPv6 is unavailable on this host**: the kernel command line has `ipv6.disable=1`, `/proc/sys/net/ipv6` does not exist, and a container has no `/proc/net/if_inet6`. IPv6 behavior could not be tested | VERIFIED (absence); NOT TESTED (behavior) | B.5 (E6a) |
| F27 | During the study the author's own experiment script left five stray `INPUT` rules behind (it deleted a rule by position number instead of by specification). The baseline-versus-after snapshot comparison reported `False`, the rules were found and removed, and the corrected script ended `True` on every later run. This is a small live demonstration of the orphan hazard in F18 and of why rules must be tracked by specification, never by position | VERIFIED | session record; B.2 |
| F28 | **The static rule of F20 had a hole.** With `-i ocbsbx+ -p tcp --dport 3128 -j ACCEPT` and no destination match, a sandbox with default capabilities (incl. `NET_RAW`) that crafted a raw Ethernet frame (`AF_PACKET`, addressed to its gateway's MAC) to the **sibling's gateway:3128** and to the **host's primary address:3128** received a SYN-ACK from each, i.e. it reached a sibling's proxy listener: the DEBT-039 reach through the very rule meant to prevent it. An IP-level raw send does not work (the sandbox has no route beyond its own subnet: `ENETUNREACH`), which is why E7's honest-traffic test missed it. Adding `-m addrtype --dst-type LOCAL --limit-iface-in` (destination must be an address of the ingress interface) left the own-gateway handshake working and produced no reply from either target. With `--cap-drop NET_RAW` the `AF_PACKET` socket failed with `PermissionError` and an ordinary connect failed. Transport-level reach only: a full forged session was not attempted. The per-sandbox rules of F14 carry `-d <own gateway>` and are not affected | VERIFIED | B.6 (E9) |

## 5. The questions, answered

**1. Can such a rule be installed safely?** Mechanically yes, with properties demonstrated: fail-closed ordering (drop first, accept above it), exact restoration of the firewall to its baseline after every run of the corrected scripts (snapshot comparison `True`; the one failed comparison was the author's own bug, F27), and a fail-closed response to a port drift (F15). What is not safe by default: the state is global and outlives the controller, the daemon and the network (F18, F19); a rule written without an `-i` match would affect unrelated host traffic, so **a rule without an interface match must be impossible to construct**; interplay with `ufw`/`firewalld`/an nft ruleset reload, and reboot persistence, were not tested.

**2. What privileges does it require?** `CAP_NET_ADMIN` in the host network namespace, to install or even list rules (F13). Today's `DockerBackend` needs only Docker access. Three ways to hold it: the controller runs with `CAP_NET_ADMIN`; a helper container started through the Docker socket (F13 shows it works; the sandbox containers themselves are forbidden `--cap-add` and host namespaces by checklist A6); or **one-time host provisioning** of a static rule set (F20), after which the controller needs no firewall privilege and checks enforcement by canary (F22). Each is a governance question (section 8, D2).

**3. Can it distinguish sandbox traffic reliably?** By **ingress interface**, yes, on per-sandbox networks (F14, F20): the interface is assigned by the kernel and a container cannot forge it. By **source address** on a shared network, no, while `NET_RAW` is present (F16). By a **wildcard on the bridge name**, yes, but only for bridges that carry the prefix (F21) and only with a destination match, without which a `NET_RAW` sandbox reaches siblings and the host (F28).

**4. Does it create a second policy surface?** Not under S1 to S7 (section 3); this is an interpretation for the user to ratify.

**5. Can it close F6 without replacing `AllowlistProxy`?** Yes on per-sandbox networks, for TCP and UDP (F14, F20). ICMP and other protocols were not exercised (the image has no `ping`), but a catch-all drop covers them by construction. On the shared network it closes F6 for honest traffic only (F16).

**6. Does it change the viability of O4 and of hybrids?** See section 6.

**7. Persistence and lifecycle under D10/D11.** Where it would sit, from `create()` as read (`docker_backend.py`): the network branch is entered when `allowed_hosts` is set; resources acquired are the proxy, the container and the workspace, unwound by `_abort_create(container_name, proxy, created_workspace)`; the handle record is `_DockerRunState`.
- *Per-sandbox rules* add a network and two rules to the acquired set, to the unwind, to `_DockerRunState`, and to `destroy()`. Set-up order that fails closed: network, drop rule, accept rule, proxy, container. Tear-down order: container, proxy, accept rule, drop rule, network. Rules and networks outlive a crashed controller (F18), so a start-up **reaper** keyed on a unique name prefix is required, and bridge names must carry the handle id so a recycled name cannot inherit stale rules (F19). Rule removal must be confirmed before the handle is forgotten, as `destroy()` already does for the container, and that confirmation needs the same privilege.
- *The static design* has **no per-sandbox rules**, so none of that rule bookkeeping exists; only networks and containers need reaping, which D10 already requires for the shared network. Its costs are the naming guard (F21), the fixed-port collision behavior (fails closed, F21) and the canary (F22).
- *D11:* per-handle rules are covered by the existing per-handle lock; parallel inserts and removals did not interfere (F17, nft variant).

**8. Interaction with concurrent sandboxes.** With separate networks and unique bridge names there is no coupling between sandboxes (F14, F20). The shared-network source-address design couples them through a growing rule set and is spoofable (F16). Capacity is a separate limit that applies to every per-sandbox-network design: 29 additional internal networks under default address pools (study F8).

**9. IPv4/IPv6.** Not testable here (F26). Reasoning only: Docker's networks are IPv4-only unless IPv6 is enabled on the network, and this host has no IPv6 at all. On a host with IPv6 enabled, a service bound to `::` could be reachable over a bridge's IPv6 address, which an IPv4 rule does not cover. The design must therefore **assert that the sandbox network has IPv6 disabled** (or carry an equivalent `ip6tables` rule), and the test for it must run only on an IPv6-capable host and say why it is skipped elsewhere.

**10. Regression tests required.** Section 7.

## 6. Option space after B3

| Option | Closes DEBT-039 (R1) | Closes F6 (R2) | New privilege / state | Status |
|---|---|---|---|---|
| O1 alone (per-sandbox network) | Yes (study F7) | **No** | none | Insufficient (user's ruling) |
| **H1: O1 + per-sandbox bridge-keyed `INPUT` rules** | Yes | Yes (F14) | `CAP_NET_ADMIN` at run time; per-handle rules; reaper | Viable; heavier lifecycle |
| **H1-static: O1 + one wildcard rule pair with a destination match, fixed proxy port, naming guard, canary** | Yes | Yes (F20) | privilege only at provisioning; naming guard; collision fails closed | Viable; **lightest firewall-based candidate** |
| O4 alone (shared network, source-address rules) | Honest traffic only | Honest traffic only | `CAP_NET_ADMIN`; growing rule set | **Not viable** while `NET_RAW` is present (F16); with it dropped, equivalent to O2 |
| O2 (shared network, caller identity in the proxy) | If identity unforgeable | No | none | Still depends on DEBT-041; F6 still open |
| H2: O1 + Docker `inhibit_ipv4`/`isolated` bridge + proxy in a sidecar | Yes | Yes by construction (F23) | a second container per sandbox, with its own egress network; no firewall | **Unevaluated**; would avoid the B3 question |
| O3 (no IP network; relay over a mounted socket) | By construction | By construction | a relay component in the image; `_net_proxy.py` is TCP-only | Unevaluated (study §5) |

The study does not choose among these; the choice belongs to the master specification, after the user rules on D1.

## 7. Regression tests required (proposed; none exists, none was added)

Every test below ends by comparing the host firewall (`iptables-save` without counters) and the Docker network/container lists to their start-of-test baseline.

- **T1 (G3, F6).** A `0.0.0.0` TCP listener and a `0.0.0.0` UDP listener on the host, a `127.0.0.1` listener as control: a networked sandbox cannot connect to the TCP listener through its gateway, no datagram is delivered, the control is refused or unreachable, and the sandbox's own proxy still answers. Must pass with `DOCKER-USER` empty (F12).
- **T2 (G1, DEBT-039).** Two concurrent networked sandboxes with different allowlists: B cannot reach A's proxy by a handed port, by scanning A's gateway range and B's own, by `CONNECT`, or by plain HTTP; A's allowed host returns `200` and B's disallowed host returns `403` through their own proxies.
- **T3 (policy ownership, S1).** The installed rule text contains no hostname and is identical in shape for two different allowlists; swapping the allowlist changes only the proxy's answers.
- **T4 (fail closed without privilege).** With firewall privilege unavailable, `create()` raises, and no network, container, proxy, rule or workspace remains (D10).
- **T5 (D10 failure points).** A failure injected at each step (network create, drop rule, accept rule, proxy start, `docker create`, `docker start`) leaves the baseline restored. Each injecting test asserts that the injection fired.
- **T6 (D11).** At least 8 concurrent create/destroy cycles, a double `destroy()`, and a `destroy()` racing `create()`: the rule count and network list return to baseline and no rule outlives its network.
- **T7 (crash recovery).** A controller killed after rule installation: the start-up reaper removes exactly the rules and networks carrying the prefix and nothing else.
- **T8 (stale name, F19).** A recreated network with a previously used name does not inherit an old `ACCEPT`.
- **T9 (naming guard, F21).** A sandbox network whose bridge name does not match the required prefix is rejected before any container starts.
- **T10 (canary, F22).** The canary reports "not enforced" and `create()` refuses when the static rules are absent, and "enforced" when they are present; it is bounded in time.
- **T11 (collision).** A pre-bound wildcard listener on the fixed proxy port makes `create()` fail closed and clean up.
- **T12 (IPv6, F26).** On an IPv6-capable host a `::`-bound listener is unreachable from a sandbox; on a host with IPv6 disabled the test is skipped and says why. A separate assertion checks that the sandbox network has IPv6 disabled.
- **T13 (forged source).** Only if a source-address design (O4 on a shared network, or O2) is ever chosen: forged-source packets from a sandbox are not accepted. It is expected to require `--cap-drop NET_RAW`.
- **T14 (`NamespaceBackend`).** Only if the user extends scope to F24: the same T1 against that backend.
- **T15 (F28).** A sandbox with default capabilities that sends a crafted frame (`AF_PACKET`) addressed to its gateway's MAC, with destination `<sibling gateway>:<proxy port>` and `<host primary address>:<proxy port>`, receives no reply, while the same probe to its own gateway receives a SYN-ACK. It must run with `NET_RAW` present so that it does not depend on DEBT-041.
- **A1 (unchanged).** The direct `NET_NAMESPACE` gate of study §6 (G2) is independent of all of the above.

## 8. Decisions needed from the user

1. **D1. Ratify the B3 reading?** May a host firewall rule be a supplement under S1 to S7, with `AllowlistProxy` the only owner of destination policy? If not, H1 and H1-static leave the option space and H2/O3 remain.
2. **D2. If yes, who holds the privilege?** (a) one-time host provisioning of a static rule set plus the canary; (b) the controller with `CAP_NET_ADMIN`; (c) a helper container. Each needs a governance decision; (a) gives the controller the least authority at run time but moves a requirement into host setup.
3. **D3. Evaluate H2 before choosing?** The non-firewall hybrid (isolated bridge plus a sidecar proxy) was only addressed, not tested for sidecar reachability or egress. Evaluating it costs a further study; skipping it is a legitimate choice.
4. **D4. `NamespaceBackend` (F24).** Is its F6 exposure in scope for the redesign, or a separate track? It is on `main` and advertises `NETWORK_ALLOWLIST`.
5. **D5. Capacity and IPv6 as design inputs.** The 29-network ceiling (study F8) and the IPv6 assertion (F26) belong to the master specification; do you want them stated there as requirements?

## 9. Corrections to earlier records (the earlier text is not edited)

- **DEBT-040** (PR #48) now says F6 also shows on `NamespaceBackend` on `main` (F24); the row's exposure paragraph was changed accordingly.
- Network-redesign study §9 lists "`NamespaceBackend`" as not examined: one scratch probe now exists (F24); it remains unaudited.
- Network-redesign study §5, option O4: "Needs host privilege; B3 limits its role" is refined here: bridge-keyed O4 is viable as a supplement to per-sandbox networks; source-address O4 is not.
- Study F9 (no capability dropping) is a prerequisite for O2 and for any source-address design, not for H1 or H1-static.
- **Correction to F20 and to summary item 6 (the author's):** the static design was reported as working on the basis of honest-traffic tests only. F28 shows its first form was bypassable by a `NET_RAW` sandbox. The text above was amended in place and marked; the original wording is in the first commit of this file (`d143dd5`).
- **Study F9 and DEBT-041:** with the corrected rule, DEBT-041 is **not** a prerequisite of H1-static either (F28, V2). It remains a recommended defense in depth.

## 10. Not examined

The legacy (non-nf_tables) iptables variant; `ufw`, `firewalld` and nft-ruleset reloads; reboot persistence; IPv6 behavior; ICMP; a forged *session* (not just packets); the sidecar's reachability and egress in H2; `AF_VSOCK`; a real concurrent load beyond 24 workers; the CI environment; behavior on a host whose `INPUT` policy is not ACCEPT.

## Appendix A. Scratch scripts (verbatim, as run; not part of the test suite)

Run with the Docker daemon up, the image `ocbrain-test/base:local`, and uid 0. Each script snapshots the firewall first and, except E8, ends by comparing it to the baseline. `e03_close_f6.py` is the corrected version; the first run had a rule-deletion bug (F27). `e07_static.py` contains one inert leftover line (an `exec` guarded by `if False`) that was not removed so that the listing stays verbatim.

### A.E1/E2: Chain traversal (F12) and privileges (F13)

```python
import sys; sys.path.insert(0, "/tmp/b3"); from common import *
print("== E0 environment")
for cmd in (("iptables", "-V"), ("ip6tables", "-V"), ("nft", "--version"), ("ip", "-V")):
    r = sh(*cmd); print("  ", " ".join(cmd), "->", (r.stdout or r.stderr).strip()[:80] or "NOT AVAILABLE")
print("   docker firewall info:", [l.strip() for l in sh("docker", "info").stdout.splitlines() if "irewall" in l or "iptables" in l.lower() or "IPv6" in l][:4])
print("   INPUT policy:", [l for l in ipt("-S", "INPUT").stdout.splitlines()][:3], "| DOCKER-USER present:", ipt("-S", "DOCKER-USER").returncode == 0)
def rd(p):
    try: return open(p).read().strip()
    except Exception as e: return "ABSENT(" + type(e).__name__ + ")"
print("   /proc/sys/net/ipv6/conf/all/disable_ipv6 =", rd("/proc/sys/net/ipv6/conf/all/disable_ipv6"), "| /proc/net/if_inet6 =", rd("/proc/net/if_inet6")[:40] or "(empty)", "| ip_forward =", rd("/proc/sys/net/ipv4/ip_forward"))
print("   kernel IPv6 config:", sh("sh", "-c", "zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_IPV6=|^CONFIG_IP6_NF_IPTABLES=' ; ls /proc/net/ip6_tables_names 2>&1 | head -1").stdout.strip() or "config not readable")
base = snapshot()
gw = mknet("b3-a", "ocbb3a", "10.231.1.0/24"); cip = mkc("b3c1", "b3-a")
print("   bridge ocbb3a exists right after network create (before any container)? see E3; here gw=%s container=%s" % (gw, cip))
ls, P, hits = listener(); us, UP, uhits = listener(kind=socket.SOCK_DGRAM)
print("   host listeners on 0.0.0.0: tcp %d, udp %d" % (P, UP))
def udp_send(): cexec("b3c1", f"import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'x',({gw!r},{UP}))"); time.sleep(0.5)
print("== E1 which netfilter chain does container->gateway (F6) traffic traverse?")
print("   baseline: tcp ->", tcp_probe("b3c1", gw, P), "|", end=" ")
n0 = len(uhits); udp_send(); print("udp delivered:", len(uhits) > n0)
def counters(chain): 
    return [l.split()[:2] for l in ipt("-L", chain, "-v", "-n", "-x").stdout.splitlines() if "ocbb3a" in l]
ipt("-I", "DOCKER-USER", "-i", "ocbb3a", "-p", "tcp", "--dport", str(P), "-j", "DROP")
print("   DOCKER-USER drop rule installed: tcp ->", tcp_probe("b3c1", gw, P), "| counters [pkts bytes]:", counters("DOCKER-USER"))
ipt("-D", "DOCKER-USER", "-i", "ocbb3a", "-p", "tcp", "--dport", str(P), "-j", "DROP")
ipt("-I", "INPUT", "-i", "ocbb3a", "-p", "tcp", "--dport", str(P), "-j", "DROP")
print("   INPUT drop rule installed:       tcp ->", tcp_probe("b3c1", gw, P), "| counters [pkts bytes]:", counters("INPUT"))
ipt("-D", "INPUT", "-i", "ocbb3a", "-p", "tcp", "--dport", str(P), "-j", "DROP")
print("   rules removed: tcp ->", tcp_probe("b3c1", gw, P))
print("== E2 privilege needed to install such a rule")
rule = ["INPUT", "-i", "ocbb3a", "-p", "tcp", "--dport", "9", "-j", "DROP"]
r = sh("setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "iptables", "-w", "-I", *rule); print("   unprivileged user (nobody): rc=%d %s" % (r.returncode, (r.stderr or r.stdout).strip()[:90]))
r = sh("setpriv", "--bounding-set=-net_admin", "--inh-caps=-net_admin", "iptables", "-w", "-I", *rule); print("   root without CAP_NET_ADMIN:  rc=%d %s" % (r.returncode, (r.stderr or r.stdout).strip()[:90]))
r = sh("docker", "run", "--rm", "--network", "host", "--cap-add", "NET_ADMIN", IMG, "iptables", "-w", "-I", *rule)
chk = ipt("-C", *rule).returncode == 0; print("   via the docker socket only (helper container, --network host --cap-add NET_ADMIN): rc=%d, rule now present on the HOST: %s" % (r.returncode, chk))
if chk: ipt("-D", *rule)
cleanup(["b3-a"], ["b3c1"])
after = snapshot()
print("== host firewall back to baseline after cleanup:", base == after)
if base != after:
    import difflib; print("\n".join(list(difflib.unified_diff(base.splitlines(), after.splitlines(), lineterm=""))[:12]))
```

### A.E3/E4: Per-sandbox rules with real proxies (F14, F15) and the shared-network source-address test (F16)

```python
import sys, http.server; sys.path.insert(0, "/tmp/b3"); sys.path.insert(0, "/home/claude/ocbrain-v4.1")
from common import *
from core.sandbox.backends._net_proxy import AllowlistProxy

def http_get(c, gw, port, url):
    code = (f"import socket\ns=socket.create_connection(({gw!r},{port}),timeout=4)\n"
            f"s.sendall(b'GET {url} HTTP/1.1\\r\\nHost: x\\r\\nConnection: close\\r\\n\\r\\n')\n"
            "d=b''\nwhile True:\n c=s.recv(4096)\n if not c: break\n d+=c\nprint(d.split(b'\\r\\n')[0].decode(), '|', d.split(b'\\r\\n\\r\\n')[-1][:20])")
    out = cexec(c, code); return out.splitlines()[-1] if out else "(no output)"

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Length", "13"); self.end_headers(); self.wfile.write(b"HOST-LOOPBACK")
    def log_message(self, *a): pass
up = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=up.serve_forever, daemon=True).start(); U = up.server_port
base = snapshot(); assert "ocbb3" not in base, "stale rules present before the run"; proxies = []; rules = []
def spec_of(r): return tuple(x for i, x in enumerate(r) if not (i == 1 and x.isdigit()))
def add(*r):
    assert ipt("-I", *r).returncode == 0; rules.append(spec_of(r))
def drop_rules():
    for r in reversed(rules): ipt("-D", *r)
    rules.clear()
try:
    print("== E3 per-sandbox network + REAL AllowlistProxy on each gateway + INPUT rules keyed on the bridge interface")
    gwA = mknet("b3-a", "ocbb3a", "10.231.1.0/24"); gwB = mknet("b3-b", "ocbb3b", "10.231.2.0/24")
    print("   bridge interface exists right after 'network create', before any container:", sh("ip", "link", "show", "ocbb3a").returncode == 0)
    cA, cB = mkc("b3cA", "b3-a"), mkc("b3cB", "b3-b")
    pA = AllowlistProxy(gwA, allowed_hosts=["127.0.0.1"]); pA.start(); pB = AllowlistProxy(gwB, allowed_hosts=["example.org"]); pB.start(); proxies += [pA, pB]
    ls, P, hits = listener(); us, UP, uhits = listener(kind=socket.SOCK_DGRAM)
    udp = lambda c, gw: (cexec(c, f"import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'x',({gw!r},{UP}))"), time.sleep(0.6))
    def f6(label):
        n = len(uhits); udp("b3cA", gwA)
        print("   %-34s A->0.0.0.0 host tcp: %-15s | udp delivered: %-5s | A->own proxy GET(allowed 127.0.0.1): %s" % (label, tcp_probe("b3cA", gwA, P), len(uhits) > n, http_get("b3cA", gwA, pA.port, f"http://127.0.0.1:{U}/")))
    f6("BEFORE rules:")
    print("   BEFORE rules: B->A's proxy (sibling) tcp:", tcp_probe("b3cB", gwA, pA.port), "(separate networks: no route)")
    # fail-closed ordering: DROP first, then ACCEPT above it
    for br, gw, px in (("ocbb3a", gwA, pA), ("ocbb3b", gwB, pB)):
        add("INPUT", "-i", br, "-j", "DROP")
        add("INPUT", "1", "-i", br, "-d", gw, "-p", "tcp", "--dport", str(px.port), "-j", "ACCEPT")
    f6("AFTER rules:")
    print("   AFTER rules: B own proxy GET 127.0.0.1 (NOT in B's allowlist) ->", http_get("b3cB", gwB, pB.port, f"http://127.0.0.1:{U}/"), " <- policy still decided by the proxy")
    ping = cexec("b3cA", f"import subprocess; r=subprocess.run(['ping','-c1','-W1',{gwA!r}],capture_output=True,text=True); print('ping rc', r.returncode)") if sh("sh","-c","command -v ping").returncode==0 else "ping binary absent"
    print("   AFTER rules: ICMP A->gateway:", ping)
    print("   installed rules (no hostnames, only interface + gateway + proxy port):"); [print("     iptables -I", " ".join(r)) for r in rules]
    print("   any hostname in the rules?", any(h in " ".join(" ".join(r) for r in rules) for h in ("127.0.0.1:", "example.org", "example.com")))
    # drift: rule port != proxy port -> fail closed
    assert ipt("-D", *rules[1]).returncode == 0; rules[1] = spec_of(("INPUT", "1", "-i", "ocbb3a", "-d", gwA, "-p", "tcp", "--dport", str(pA.port + 1), "-j", "ACCEPT")); assert ipt("-I", "INPUT", "1", "-i", "ocbb3a", "-d", gwA, "-p", "tcp", "--dport", str(pA.port + 1), "-j", "ACCEPT").returncode == 0
    print("   DRIFT (rule port != proxy port): A->own proxy:", tcp_probe("b3cA", gwA, pA.port), "<- fails closed, not open")
    print("== E4 SHARED network + source-IP rules (what O4 alone would be) and forged-source test")
    drop_rules(); [p.stop() for p in proxies]; proxies.clear(); cleanup(["b3-a", "b3-b"], ["b3cA", "b3cB"])
    gwS = mknet("b3-s", "ocbb3s", "10.231.3.0/24"); ipA, ipB = mkc("b3sA", "b3-s"), mkc("b3sB", "b3-s")
    sA = AllowlistProxy(gwS, allowed_hosts=["127.0.0.1"]); sA.start(); sB = AllowlistProxy(gwS, allowed_hosts=["example.org"]); sB.start(); proxies += [sA, sB]
    print("   BEFORE rules: B->A's proxy GET 127.0.0.1:", http_get("b3sB", gwS, sA.port, f"http://127.0.0.1:{U}/"), " (this is DEBT-039)")
    add("INPUT", "-i", "ocbb3s", "-j", "DROP")
    add("INPUT", "1", "-i", "ocbb3s", "-s", ipB, "-d", gwS, "-p", "tcp", "--dport", str(sB.port), "-j", "ACCEPT")
    add("INPUT", "1", "-i", "ocbb3s", "-s", ipA, "-d", gwS, "-p", "tcp", "--dport", str(sA.port), "-j", "ACCEPT")
    print("   AFTER source-IP rules: A->own:", http_get("b3sA", gwS, sA.port, f"http://127.0.0.1:{U}/"), "| B->A's proxy:", tcp_probe("b3sB", gwS, sA.port), "| B->0.0.0.0 host tcp:", tcp_probe("b3sB", gwS, P))
    spoof = r'''
import socket, struct, random
def cs(b):
    if len(b) % 2: b += b"\0"
    s = sum(struct.unpack("!%dH" % (len(b)//2), b)); s = (s >> 16) + (s & 0xffff); s += s >> 16; return ~s & 0xffff
def syn(src, dst, dport):
    sport, seq = random.randint(20000, 60000), random.getrandbits(32)
    t0 = struct.pack("!HHLLBBHHH", sport, dport, seq, 0, 5 << 4, 2, 65535, 0, 0)
    ph = socket.inet_aton(src) + socket.inet_aton(dst) + struct.pack("!BBH", 0, 6, len(t0))
    t = struct.pack("!HHLLBBHHH", sport, dport, seq, 0, 5 << 4, 2, 65535, cs(ph + t0), 0)
    i0 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(t), random.getrandbits(16), 0, 64, 6, 0, socket.inet_aton(src), socket.inet_aton(dst))
    i = i0[:10] + struct.pack("!H", cs(i0)) + i0[12:]
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW); s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1); s.sendto(i + t, (dst, 0))
try:
    for _ in range(5): syn("@SRC@", "@DST@", @PORT@)
    print("sent 5 SYNs claiming source @SRC@")
except Exception as e:
    print("raw socket failed:", type(e).__name__, e)
'''
    fill = lambda t, a, b, c: t.replace("@SRC@", a).replace("@DST@", b).replace("@PORT@", str(c))
    def ruleA_pkts():
        for l in ipt("-L", "INPUT", "-v", "-n", "-x").stdout.splitlines():
            if ipA in l and "ACCEPT" in l: return int(l.split()[0])
    sh("docker", "exec", "b3sB", "true")
    before = ruleA_pkts(); out = cexec("b3sB", fill(spoof, ipA, gwS, sA.port)); time.sleep(0.5); after = ruleA_pkts()
    print("   FORGED SOURCE from B (default caps, incl. NET_RAW): %s | A's ACCEPT rule packet counter %d -> %d (accepted forged packets: %s)" % (out, before, after, after > before))
    sh("docker", "rm", "-f", "b3sC"); r = sh("docker", "run", "-d", "--name", "b3sC", "--network", "b3-s", "--cap-drop", "NET_RAW", "--read-only", "--security-opt", "no-new-privileges", IMG, "sleep", "600")
    out2 = cexec("b3sC", fill(spoof, ipA, gwS, sA.port)); print("   same forged-source attempt with --cap-drop NET_RAW:", out2[:110])
finally:
    drop_rules(); [p.stop() for p in proxies]; cleanup(["b3-a", "b3-b", "b3-s"], ["b3cA", "b3cB", "b3sA", "b3sB", "b3sC"]); up.shutdown()
    print("== host firewall back to baseline after cleanup:", snapshot() == base)
```

### A.E5: Concurrency, crash and stale-rule behavior (F17, F18, F19)

```python
import sys, concurrent.futures as cf, signal; sys.path.insert(0, "/tmp/b3"); from common import *
base = snapshot(); assert "ocb" not in base
def ipt_nolock(*a): return sh("iptables", *a)
print("== E5a concurrent install/remove of rules for 24 sandboxes (2 rules each)")
for label, fn in (("with  -w (xtables lock wait)", ipt), ("WITHOUT -w", ipt_nolock)):
    def inst(i):
        a = fn("-I", "INPUT", "-i", f"ocbq{i}", "-j", "DROP"); b = fn("-I", "INPUT", "1", "-i", f"ocbq{i}", "-d", "10.9.9.1", "-p", "tcp", "--dport", str(30000 + i), "-j", "ACCEPT")
        return (a.returncode, b.returncode, (a.stderr + b.stderr).strip()[:70])
    with cf.ThreadPoolExecutor(24) as ex: res = list(ex.map(inst, range(24)))
    present = sum(1 for l in sh("iptables", "-w", "-S", "INPUT").stdout.splitlines() if "ocbq" in l)
    fails = [r for r in res if r[0] or r[1]]
    print("   %-30s install: %d/24 workers saw an error | rules present: %d (expected 48)%s" % (label, len(fails), present, (" | e.g. " + fails[0][2]) if fails else ""))
    def rem(i):
        for spec in (("-i", f"ocbq{i}", "-d", "10.9.9.1", "-p", "tcp", "--dport", str(30000 + i), "-j", "ACCEPT"), ("-i", f"ocbq{i}", "-j", "DROP")):
            fn("-D", "INPUT", *spec)
    with cf.ThreadPoolExecutor(24) as ex: list(ex.map(rem, range(24)))
    left = sum(1 for l in sh("iptables", "-w", "-S", "INPUT").stdout.splitlines() if "ocbq" in l)
    print("   %-30s after parallel removal: %d rules left" % ("", left))
    # clean any residue
    while any("ocbq" in l for l in sh("iptables", "-w", "-S", "INPUT").stdout.splitlines()):
        l = [x for x in sh("iptables", "-w", "-S", "INPUT").stdout.splitlines() if "ocbq" in x][0]; sh("sh", "-c", "iptables -w " + l.replace("-A", "-D", 1))
print("== E5b a controller that dies after installing a rule")
code = "import subprocess,os,signal; subprocess.run(['iptables','-w','-I','INPUT','-i','ocbdead','-j','DROP'],check=True); os.kill(os.getpid(), signal.SIGKILL)"
r = sh("python3", "-c", code); print("   controller SIGKILLed (rc=%d); rule still in the kernel: %s" % (r.returncode, any("ocbdead" in l for l in sh("iptables", "-w", "-S", "INPUT").stdout.splitlines())))
sh("iptables", "-w", "-D", "INPUT", "-i", "ocbdead", "-j", "DROP")
print("== E5c stale rules + a recycled bridge name")
gw = mknet("b3-r", "ocbb3r", "10.231.5.0/24")
ipt("-I", "INPUT", "-i", "ocbb3r", "-j", "DROP"); ipt("-I", "INPUT", "1", "-i", "ocbb3r", "-d", gw, "-p", "tcp", "--dport", "40111", "-j", "ACCEPT")
sh("docker", "network", "rm", "b3-r")
print("   network removed; its rules are still installed:", sum(1 for l in sh("iptables", "-w", "-S", "INPUT").stdout.splitlines() if "ocbb3r" in l), "rules (nothing removed them)")
gw2 = mknet("b3-r2", "ocbb3r", "10.231.5.0/24"); mkc("b3rc", "b3-r2")
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((gw2, 40111)); s.listen(4)
s2 = socket.socket(); s2.bind((gw2, 40112)); s2.listen(4)
print("   NEW network reusing the SAME bridge name+subnet: new unrelated listener on the old ACCEPTed port 40111 ->", tcp_probe("b3rc", gw2, 40111), "| on another port 40112 ->", tcp_probe("b3rc", gw2, 40112))
s.close(); s2.close(); cleanup(["b3-r2"], ["b3rc"])
for spec in (("-i", "ocbb3r", "-d", "10.231.5.1", "-p", "tcp", "--dport", "40111", "-j", "ACCEPT"), ("-i", "ocbb3r", "-j", "DROP")): ipt("-D", "INPUT", *spec)
print("   a NEW network with a DIFFERENT bridge name is unaffected by stale rules for the old name (rules are keyed on the interface name)")
print("== host firewall back to baseline:", snapshot() == base)
```

### A.E6: IPv6 availability and Docker-native options (F23, F26)

```python
import sys; sys.path.insert(0, "/tmp/b3"); from common import *
print("== E6a IPv6 on this host")
print("   /proc/cmdline mentions ipv6:", [w for w in open("/proc/cmdline").read().split() if "ipv6" in w] or "no ipv6.* parameter")
print("   /proc/sys/net/ipv6 exists:", os.path.exists("/proc/sys/net/ipv6"), "| ip -6 addr:", (sh("ip", "-6", "addr").stdout.strip()[:60] or "(none)"), "| docker 'IPv6' in info:", [l.strip() for l in sh("docker", "info").stdout.splitlines() if "IPv6" in l])
print("   in a container: /proc/net/if_inet6 =", (cexec("x", "print(open('/proc/net/if_inet6').read()[:60] or 'EMPTY')") if False else "(see below)"))
sh("docker", "rm", "-f", "b3six"); sh("docker", "run", "-d", "--name", "b3six", "--network", "bridge", "--read-only", IMG, "sleep", "60")
print("   in a default-bridge container: if_inet6 =", repr(cexec("b3six", "import os; print(open('/proc/net/if_inet6').read()[:60] if os.path.exists('/proc/net/if_inet6') else 'ABSENT')")))
sh("docker", "rm", "-f", "b3six")
print("== E6b Docker-native options (side evidence: can F6 be closed WITHOUT a host firewall?)")
ls, P, hits = listener()
for name, opts in (("inhibit_ipv4", ["-o", "com.docker.network.bridge.inhibit_ipv4=true"]), ("gateway_mode_ipv4=isolated", ["-o", "com.docker.network.bridge.gateway_mode_ipv4=isolated"]), ("host_binding/none (control: default internal)", [])):
    sh("docker", "rm", "-f", "b3n"); sh("docker", "network", "rm", "b3-n")
    r = sh("docker", "network", "create", "--internal", "--subnet", "10.231.9.0/24", "-o", "com.docker.network.bridge.name=ocbb3n", *opts, "b3-n")
    if r.returncode: print("   %-46s create FAILED: %s" % (name, r.stderr.strip()[:100])); continue
    br = sh("ip", "-4", "addr", "show", "dev", "ocbb3n").stdout; has_ip = "inet " in br
    sh("docker", "run", "-d", "--name", "b3n", "--network", "b3-n", "--read-only", IMG, "sleep", "60")
    route = cexec("b3n", "import subprocess; print(subprocess.run(['ip','route'],capture_output=True,text=True).stdout.strip().replace(chr(10),' ; '))")
    gw = sh("docker", "network", "inspect", "b3-n", "--format", "{{(index .IPAM.Config 0).Gateway}}").stdout.strip()
    print("   %-46s host bridge has an IPv4 address: %-5s | recorded gateway: %-10s | container route: %s | reach 0.0.0.0 host svc via gateway: %s" % (name, has_ip, gw or "(none)", route[:50] or "(none)", tcp_probe("b3n", gw, P, 2) if gw else "n/a"))
    sh("docker", "rm", "-f", "b3n"); sh("docker", "network", "rm", "b3-n")
```

### A.E7: The static design and its hazards (F20, F21, F22)

```python
import sys, http.server; sys.path.insert(0, "/tmp/b3"); sys.path.insert(0, "/home/claude/ocbrain-v4.1")
from common import *
from core.sandbox.backends._net_proxy import AllowlistProxy
exec(open("/tmp/b3/e03_close_f6.py").read().split("class H(")[0].split("def http_get")[1].join(["def http_get", ""]) if False else "")
def http_get(c, gw, port, url):
    code = (f"import socket\ns=socket.create_connection(({gw!r},{port}),timeout=4)\n"
            f"s.sendall(b'GET {url} HTTP/1.1\\r\\nHost: x\\r\\nConnection: close\\r\\n\\r\\n')\n"
            "d=b''\nwhile True:\n c=s.recv(4096)\n if not c: break\n d+=c\nprint(d.split(b'\\r\\n')[0].decode(), '|', d.split(b'\\r\\n\\r\\n')[-1][:20])")
    out = cexec(c, code); return out.splitlines()[-1] if out else "(no output)"
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Length", "13"); self.end_headers(); self.wfile.write(b"HOST-LOOPBACK")
    def log_message(self, *a): pass
up = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=up.serve_forever, daemon=True).start(); U = up.server_port
base = snapshot(); assert "ocb" not in base
PORT = 3128; proxies = []; installed = False
try:
    print("== E7 STATIC rules installed once (no per-sandbox rules): every sandbox bridge is named ocbsbx*, every proxy binds <its own gateway>:%d" % PORT)
    sh("iptables", "-w", "-I", "INPUT", "-i", "ocbsbx+", "-j", "DROP"); sh("iptables", "-w", "-I", "INPUT", "1", "-i", "ocbsbx+", "-p", "tcp", "--dport", str(PORT), "-j", "ACCEPT"); installed = True
    print("   static rule set:", [l for l in sh("iptables", "-w", "-S", "INPUT").stdout.splitlines() if "ocbsbx" in l])
    gwA = mknet("b3-x1", "ocbsbx1", "10.231.11.0/24"); gwB = mknet("b3-x2", "ocbsbx2", "10.231.12.0/24"); mkc("b3x1", "b3-x1"); mkc("b3x2", "b3-x2")
    pA = AllowlistProxy(gwA, allowed_hosts=["127.0.0.1"]); pA.start(PORT); pB = AllowlistProxy(gwB, allowed_hosts=["example.org"]); pB.start(PORT); proxies += [pA, pB]
    ls, P, hits = listener(); us, UP, uhits = listener(kind=socket.SOCK_DGRAM)
    print("   A -> own proxy, GET 127.0.0.1 (A allows it):          ", http_get("b3x1", gwA, PORT, f"http://127.0.0.1:{U}/"))
    print("   B -> own proxy, GET 127.0.0.1 (B does not allow it):  ", http_get("b3x2", gwB, PORT, f"http://127.0.0.1:{U}/"))
    print("   B -> A's gateway:%d (sibling proxy, same port number): " % PORT, tcp_probe("b3x2", gwA, PORT), "<- DEBT-039 path closed by topology")
    n = len(uhits); cexec("b3x1", f"import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x',({gwA!r},{UP}))"); time.sleep(0.6)
    print("   A -> 0.0.0.0 host tcp: %s | udp delivered: %s   <- F6 closed" % (tcp_probe("b3x1", gwA, P), len(uhits) > n))
    print("== E7b hazards of the static design")
    c = socket.socket(); c.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        c.bind(("0.0.0.0", PORT)); c.listen(2); print("   a host service already on 0.0.0.0:%d -> a NEW proxy bind on a gateway:" % PORT, end=" ")
        gwC = mknet("b3-x3", "ocbsbx3", "10.231.13.0/24"); pC = AllowlistProxy(gwC, allowed_hosts=["x.test"])
        try: pC.start(PORT); print("bound (collision NOT detected)"); pC.stop()
        except OSError as e: print("fails closed: %s" % type(e).__name__)
        c.close(); sh("docker", "network", "rm", "b3-x3")
    except OSError as e: print("   (could not stage the collision:", e, ")")
    print("   a bridge whose name does NOT match the prefix (naming drift):", end=" ")
    gwN = mknet("b3-n1", "ocbnope1", "10.231.14.0/24"); mkc("b3xn", "b3-n1"); print("0.0.0.0 host tcp from that sandbox ->", tcp_probe("b3xn", gwN, P), "<- F6 OPEN: the rule never covered it")
    print("== E7c behavioral canary (verifies enforcement end to end, needs no firewall privilege in the controller)")
    t0 = time.time(); sh("docker", "rm", "-f", "b3canary"); mkc("b3canary", "b3-x1")
    res = tcp_probe("b3canary", gwA, P, 2); print("   canary container on a sandbox bridge -> a non-proxy host port: %s (%.1fs incl. container start) => %s" % (res, time.time() - t0, "ENFORCED" if res != "CONNECTED" else "NOT ENFORCED: refuse to create sandboxes"))
    t0 = time.time(); res2 = tcp_probe("b3canary", gwN, P, 2) if False else None
finally:
    [p.stop() for p in proxies]; cleanup(["b3-x1", "b3-x2", "b3-x3", "b3-n1"], ["b3x1", "b3x2", "b3xn", "b3canary"]); up.shutdown()
    if installed:
        for spec in (("-i", "ocbsbx+", "-p", "tcp", "--dport", str(PORT), "-j", "ACCEPT"), ("-i", "ocbsbx+", "-j", "DROP")): ipt("-D", "INPUT", *spec)
    print("== host firewall back to baseline after cleanup:", snapshot() == base)
```

### A.common: Shared helpers

```python
import subprocess, socket, threading, time, json, sys, os
IMG = "ocbrain-test/base:local"
def sh(*a, check=False, timeout=60):
    r = subprocess.run(a, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode: raise RuntimeError(f"{a}: {r.stderr}")
    return r
def ipt(*a): return sh("iptables", "-w", *a)
def snapshot():
    out = sh("iptables-save").stdout
    return "\n".join(l for l in out.splitlines() if not l.startswith(("#", ":")) )
def mknet(name, bridge, subnet):
    sh("docker", "network", "rm", name)
    r = sh("docker", "network", "create", "--internal", "--subnet", subnet,
           "-o", "com.docker.network.bridge.enable_icc=false", "-o", f"com.docker.network.bridge.name={bridge}", name)
    assert r.returncode == 0, r.stderr
    return sh("docker", "network", "inspect", name, "--format", "{{(index .IPAM.Config 0).Gateway}}").stdout.strip()
def mkc(name, net):
    sh("docker", "rm", "-f", name)
    r = sh("docker", "run", "-d", "--name", name, "--network", net, "--read-only", "--security-opt", "no-new-privileges", IMG, "sleep", "600")
    assert r.returncode == 0, r.stderr
    return sh("docker", "inspect", name, "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}").stdout.strip()
def cexec(c, code, timeout=30):
    r = sh("docker", "exec", c, "python3", "-c", code, timeout=timeout); return (r.stdout + r.stderr).strip()
def tcp_probe(c, ip, port, t=3):
    return cexec(c, f"import socket\ntry:\n s=socket.create_connection(({ip!r},{port}),timeout={t}); s.close(); print('CONNECTED')\nexcept Exception as e: print(type(e).__name__)")
def listener(ip="0.0.0.0", kind=socket.SOCK_STREAM):
    s = socket.socket(socket.AF_INET, kind); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((ip, 0)); hits = []
    if kind == socket.SOCK_STREAM:
        s.listen(32)
        def acc():
            while True:
                try: c, a = s.accept(); hits.append(a); c.close()
                except Exception: return
    else:
        def acc():
            while True:
                try: d, a = s.recvfrom(64); hits.append(a)
                except Exception: return
    threading.Thread(target=acc, daemon=True).start(); return s, s.getsockname()[1], hits
def cleanup(nets=(), cons=()):
    for c in cons: sh("docker", "rm", "-f", c)
    for n in nets: sh("docker", "network", "rm", n)
```

### A.E8: NamespaceBackend probe (F24)

```python
"""Scratch probe (NOT in the repo, NO repo code modified): does the F6 mechanism also apply to NamespaceBackend (on main, claims NETWORK_ALLOWLIST)?
A sandbox with allowed_hosts runs a script that (1) finds its gateway from HTTPS_PROXY, (2) tries to reach a host listener bound to 0.0.0.0 and one bound to 127.0.0.1 via that gateway."""
import asyncio, os, socket, sys, tempfile, threading
sys.path.insert(0, "/home/claude/ocbrain-v4.1")
from core.sandbox.backends.namespace_backend import NamespaceBackend
from core.sandbox.contracts import SandboxPolicy, SandboxRequest

CODE = r'''
import os, socket, urllib.parse
u = urllib.parse.urlparse(os.environ["HTTPS_PROXY"]); gw = u.hostname
def t(label, port):
    try:
        s = socket.create_connection((gw, port), timeout=4); s.close(); print("%s -> CONNECTED" % label)
    except Exception as e:
        print("%s -> %s" % (label, type(e).__name__))
t("own proxy %s:%d" % (gw, u.port), u.port)
t("0.0.0.0-bound host service via gateway %s" % gw, int(os.environ["ANY_PORT"]))
t("127.0.0.1-bound host service via gateway %s" % gw, int(os.environ["LO_PORT"]))
'''
async def main():
    a = socket.socket(); a.bind(("0.0.0.0", 0)); a.listen(4)
    l = socket.socket(); l.bind(("127.0.0.1", 0)); l.listen(4)
    got = []
    a.settimeout(30)
    def acc():
        try:
            while True:
                c, ad = a.accept(); got.append(ad); c.close()
        except Exception: pass
    threading.Thread(target=acc, daemon=True).start()
    be = NamespaceBackend()
    ws = tempfile.mkdtemp()
    req = SandboxRequest(command=("python3", "-c", CODE), env={"ANY_PORT": str(a.getsockname()[1]), "LO_PORT": str(l.getsockname()[1])},
                         policy=SandboxPolicy(workspace_dir=ws, timeout_sec=30, allowed_hosts=("example.org",)))
    h = await be.create(req)
    try:
        r = await be.run(h, req)
        print("exit:", r.exit_code); print(r.stdout.strip() or "(no stdout)")
        if r.stderr.strip(): print("stderr:", r.stderr.strip()[:300])
        print("host-side: 0.0.0.0 listener saw connections from:", got)
        print("NamespaceBackend capabilities include NETWORK_ALLOWLIST:", any(c.name == "NETWORK_ALLOWLIST" for c in be.capabilities.supported))
    finally:
        await be.destroy(h)
asyncio.run(main())
```

### A.E9: Static rule destination test (F28)

```python
"""Scratch E9 (NOT in the repo): does the STATIC rule (no destination match) let a sandbox with NET_RAW reach a SIBLING's gateway:port?
Variants: V1 = static rule as tested in E7; V2 = V1 + `-m addrtype --dst-type LOCAL --limit-iface-in` (destination must be an address of the INGRESS interface).
Packets are crafted as raw Ethernet frames (AF_PACKET, needs CAP_NET_RAW) because an IP-level raw send needs a route and the sandbox has none beyond its own subnet. Evidence of reach = the sandbox RECEIVES a SYN-ACK from <target>:3128 (transport-level reachability; a full session is not attempted)."""
import sys; sys.path.insert(0, "/tmp/b3"); from common import *
PORT = 3128
SYN_PROBE = r'''
import socket, struct, random, time, sys, os
src, dst, dport, gw_own = "@SRC@", "@DST@", @PORT@, "@GW@"
def cs(b):
    if len(b) % 2: b += b"\0"
    s = sum(struct.unpack("!%dH" % (len(b)//2), b)); s = (s >> 16) + (s & 0xffff); s += s >> 16; return ~s & 0xffff
try:
    pk = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800)); pk.bind(("eth0", 0)); pk.settimeout(0.4)
except Exception as e:
    print("NO-AF_PACKET", type(e).__name__); sys.exit()
try: socket.create_connection((gw_own, 9), timeout=1)
except Exception: pass
mac_me = bytes.fromhex(open("/sys/class/net/eth0/address").read().strip().replace(":", ""))
gm = [l.split() for l in open("/proc/net/arp").read().splitlines()[1:] if l.split()[0] == gw_own]
if not gm: print("no ARP entry for own gateway"); sys.exit()
mac_gw = bytes.fromhex(gm[0][3].replace(":", ""))
sport = random.randint(20000, 60000); seq = random.getrandbits(32)
t0 = struct.pack("!HHLLBBHHH", sport, dport, seq, 0, 5 << 4, 2, 65535, 0, 0)
ph = socket.inet_aton(src) + socket.inet_aton(dst) + struct.pack("!BBH", 0, 6, len(t0))
t = struct.pack("!HHLLBBHHH", sport, dport, seq, 0, 5 << 4, 2, 65535, cs(ph + t0), 0)
i0 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(t), random.getrandbits(16), 0, 64, 6, 0, socket.inet_aton(src), socket.inet_aton(dst))
i = i0[:10] + struct.pack("!H", cs(i0)) + i0[12:]
pk.send(mac_gw + mac_me + b"\x08\x00" + i + t)
end = time.time() + 2.5; got = "no reply"
while time.time() < end:
    try: f = pk.recv(2048)
    except socket.timeout: continue
    if f[12:14] != b"\x08\x00" or f[23] != 6: continue
    ihl = (f[14] & 15) * 4; s_ip = socket.inet_ntoa(f[26:30]); o = 14 + ihl
    sp, dp, _, ack, off, flags = struct.unpack("!HHLLBB", f[o:o+14])
    if s_ip == dst and sp == dport and dp == sport and (flags & 0x12) == 0x12: got = "SYN-ACK received from %s:%d" % (s_ip, sp); break
print(got)
'''
GWOWN = {}
def reach(c, src, dst): return cexec(c, SYN_PROBE.replace("@SRC@", src).replace("@DST@", dst).replace("@PORT@", str(PORT)).replace("@GW@", GWOWN["B"]), timeout=20)
base = snapshot(); assert "ocb" not in base
hostip = sh("sh", "-c", "ip -4 route get 1.1.1.1 | sed -n 's/.* src \\([0-9.]*\\).*/\\1/p'").stdout.strip()
socks = []
def srv(ip):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((ip, PORT)); s.listen(8); socks.append(s)
try:
    gwA = mknet("b3-x1", "ocbsbx1", "10.231.11.0/24"); gwB = mknet("b3-x2", "ocbsbx2", "10.231.12.0/24"); ipA = mkc("b3x1", "b3-x1"); ipB = mkc("b3x2", "b3-x2")
    GWOWN["B"] = gwB; srv(gwA); srv(gwB); srv(hostip)
    print("setup: A=%s (gw %s) B=%s (gw %s) | host primary address %s | listeners bound to each of the three addresses on :%d" % (ipA, gwA, ipB, gwB, hostip, PORT))
    for label, extra in (("V0 no rules (control)", None), ("V1 static rule, no destination match", []), ("V2 static rule + addrtype LOCAL --limit-iface-in", ["-m", "addrtype", "--dst-type", "LOCAL", "--limit-iface-in"])):
        rules = []
        if extra is not None:
            acc = ["INPUT", "1", "-i", "ocbsbx+", "-p", "tcp", "--dport", str(PORT), *extra, "-j", "ACCEPT"]; drp = ["INPUT", "-i", "ocbsbx+", "-j", "DROP"]
            r1 = ipt("-I", *drp); r2 = ipt("-I", *acc)
            if r1.returncode or r2.returncode: print("  %s: rule install FAILED: %s" % (label, (r1.stderr + r2.stderr).strip()[:120])); ipt("-D", "INPUT", "-i", "ocbsbx+", "-j", "DROP"); continue
        print("  %s" % label)
        print("     B (default caps) -> OWN gateway   %s:%d : %s" % (gwB, PORT, reach("b3x2", ipB, gwB)))
        print("     B (default caps) -> SIBLING gw    %s:%d : %s" % (gwA, PORT, reach("b3x2", ipB, gwA)))
        print("     B (default caps) -> HOST address  %s:%d : %s" % (hostip, PORT, reach("b3x2", ipB, hostip)))
        if extra is not None:
            ipt("-D", "INPUT", "-i", "ocbsbx+", "-p", "tcp", "--dport", str(PORT), *extra, "-j", "ACCEPT"); ipt("-D", "INPUT", "-i", "ocbsbx+", "-j", "DROP")
    sh("docker", "rm", "-f", "b3x3"); sh("docker", "run", "-d", "--name", "b3x3", "--network", "b3-x2", "--cap-drop", "NET_RAW", "--read-only", "--security-opt", "no-new-privileges", IMG, "sleep", "300")
    ipt("-I", "INPUT", "-i", "ocbsbx+", "-j", "DROP"); ipt("-I", "INPUT", "1", "-i", "ocbsbx+", "-p", "tcp", "--dport", str(PORT), "-j", "ACCEPT")
    print("  V1 static rule, no destination match, sandbox with --cap-drop NET_RAW:")
    print("     raw probe -> SIBLING gw:", cexec("b3x3", SYN_PROBE.replace("@SRC@", ipB).replace("@DST@", gwA).replace("@PORT@", str(PORT)).replace("@GW@", gwB)))
    print("     ordinary connect -> SIBLING gw:", tcp_probe("b3x3", gwA, PORT))
    ipt("-D", "INPUT", "-i", "ocbsbx+", "-p", "tcp", "--dport", str(PORT), "-j", "ACCEPT"); ipt("-D", "INPUT", "-i", "ocbsbx+", "-j", "DROP")
finally:
    for s in socks: s.close()
    cleanup(["b3-x1", "b3-x2"], ["b3x1", "b3x2", "b3x3"])
    print("== host firewall back to baseline after cleanup:", snapshot() == base)
```

## Appendix B. Observed output (this host, October 3 2026)

### B.1 E0 to E2
```
iptables v1.8.10 (nf_tables) | ip6tables v1.8.10 (nf_tables) | nftables v1.0.9 | iproute2-6.1.0
docker firewall info: ['Firewall Backend: iptables'] | INPUT policy ACCEPT | DOCKER-USER present: True
/proc/sys/net/ipv6/conf/all/disable_ipv6 = ABSENT | /proc/net/if_inet6 = ABSENT | ip_forward = 1 | CONFIG_IPV6=y
E1 baseline: tcp -> CONNECTED | udp delivered: True
E1 DOCKER-USER drop rule installed: tcp -> CONNECTED | counters [pkts bytes]: [['0', '0']]
E1 INPUT drop rule installed:       tcp -> TimeoutError | counters [pkts bytes]: [['3', '180']]
E1 rules removed: tcp -> CONNECTED
E2 unprivileged user (nobody): rc=4 iptables v1.8.10 (nf_tables): Could not fetch rule set generation id: Permission denied
E2 root without CAP_NET_ADMIN:  rc=4 (same message)
E2 via the docker socket only (helper container, --network host --cap-add NET_ADMIN): rc=0, rule now present on the HOST: True
host firewall back to baseline after cleanup: True
```

### B.2 E3 and E4 (corrected run)
```
bridge interface exists right after 'network create', before any container: True
BEFORE rules: A->0.0.0.0 host tcp: CONNECTED | udp delivered: True | A->own proxy GET(allowed 127.0.0.1): HTTP/1.0 200 OK | b'HOST-LOOPBACK'
BEFORE rules: B->A's proxy (sibling) tcp: OSError (separate networks: no route)
AFTER rules:  A->0.0.0.0 host tcp: TimeoutError | udp delivered: False | A->own proxy GET(allowed 127.0.0.1): HTTP/1.0 200 OK | b'HOST-LOOPBACK'
AFTER rules:  B own proxy GET 127.0.0.1 (NOT in B's allowlist) -> HTTP/1.1 403 Forbidden
AFTER rules:  ICMP A->gateway: ping binary absent
rules: iptables -I INPUT -i ocbb3a -j DROP | -I INPUT -i ocbb3a -d 10.231.1.1 -p tcp --dport 34919 -j ACCEPT (and the same for ocbb3b/10.231.2.1:38455)
any hostname in the rules? False
DRIFT (rule port != proxy port): A->own proxy: TimeoutError  <- fails closed
E4 BEFORE rules: B->A's proxy GET 127.0.0.1: HTTP/1.0 200 OK  (this is DEBT-039)
E4 AFTER source-IP rules: A->own: HTTP/1.0 200 OK | B->A's proxy: TimeoutError | B->0.0.0.0 host tcp: TimeoutError
E4 FORGED SOURCE from B (default caps, incl. NET_RAW): sent 5 SYNs claiming source 10.231.3.2 | A's ACCEPT rule packet counter 5 -> 15
E4 same attempt with --cap-drop NET_RAW: raw socket failed: PermissionError [Errno 1] Operation not permitted
host firewall back to baseline after cleanup: True
(first run, flawed drift step: baseline comparison printed False; 5 stray rules found and removed -- F27)
```

### B.3 E5
```
E5a with  -w: install 0/24 workers saw an error | rules present: 48 (expected 48) | after parallel removal: 0 rules left
E5a WITHOUT -w: install 0/24 workers saw an error | rules present: 48 (expected 48) | after parallel removal: 0 rules left
E5b controller SIGKILLed (rc=-9); rule still in the kernel: True
E5c network removed; its rules are still installed: 2 rules
E5c NEW network, SAME bridge name+subnet: unrelated listener on the old ACCEPTed port 40111 -> CONNECTED | port 40112 -> TimeoutError
E5d before restart: rules=2 docker-chains=6 bridge=up | daemon down: rules=2 | after restart: rules=2 docker-chains=6 network-present=1 bridge=up
host firewall back to baseline: True
```

### B.4 E7
```
static rule set: ['-A INPUT -i ocbsbx+ -p tcp -m tcp --dport 3128 -j ACCEPT', '-A INPUT -i ocbsbx+ -j DROP']
A -> own proxy, GET 127.0.0.1 (A allows it):          HTTP/1.0 200 OK | b'HOST-LOOPBACK'
B -> own proxy, GET 127.0.0.1 (B does not allow it):  HTTP/1.1 403 Forbidden
B -> A's gateway:3128 (sibling proxy, same port number): OSError
A -> 0.0.0.0 host tcp: TimeoutError | udp delivered: False
naming drift (bridge ocbnope1): 0.0.0.0 host tcp from that sandbox -> CONNECTED  <- F6 OPEN
canary container on a sandbox bridge -> a non-proxy host port: TimeoutError (2.3s incl. container start) => ENFORCED
collision mini-test: direction 1 (wildcard first, proxy second): proxy.start() raised OSError | direction 2 (proxy first, wildcard second): wildcard bind raised OSError
host firewall back to baseline after cleanup: True
```

### B.5 E6 and E8
```
/proc/cmdline mentions ipv6: ['ipv6.disable=1'] | /proc/sys/net/ipv6 exists: False | ip -6 addr: (none) | default-bridge container if_inet6: 'ABSENT'
inhibit_ipv4:                 host bridge has an IPv4 address: False | recorded gateway: invalid IP
gateway_mode_ipv4=isolated:   host bridge has an IPv4 address: False | recorded gateway: invalid IP
control (default internal):   host bridge has an IPv4 address: True  | recorded gateway: 10.231.9.1 | reach 0.0.0.0 host svc via gateway: CONNECTED
E8 NamespaceBackend (allowed_hosts): own proxy 10.200.0.1:37805 -> CONNECTED | 0.0.0.0-bound host service via gateway 10.200.0.1 -> CONNECTED | 127.0.0.1-bound host service via gateway -> ConnectionRefusedError
E8 host-side: 0.0.0.0 listener saw connections from [('10.200.0.2', 36338)] | NamespaceBackend capabilities include NETWORK_ALLOWLIST: True
```

### B.6 E9 (F28)

```
setup: A=10.231.11.2 (gw 10.231.11.1) B=10.231.12.2 (gw 10.231.12.1) | host primary address 192.0.2.2 | listeners bound to each of the three addresses on :3128
V0 no rules (control):  B -> OWN gw: SYN-ACK | B -> SIBLING gw 10.231.11.1:3128: SYN-ACK | B -> HOST address 192.0.2.2:3128: SYN-ACK
V1 static rule, no destination match:  B -> OWN gw: SYN-ACK | B -> SIBLING gw: SYN-ACK received from 10.231.11.1:3128 | B -> HOST address: SYN-ACK received from 192.0.2.2:3128
V2 static rule + addrtype LOCAL --limit-iface-in:  B -> OWN gw: SYN-ACK | B -> SIBLING gw: no reply | B -> HOST address: no reply
V1 with --cap-drop NET_RAW: raw probe -> NO-AF_PACKET PermissionError | ordinary connect -> SIBLING gw: OSError
(first attempt used IP-level raw sockets: sibling and host targets failed with OSError [Errno 101] Network is unreachable, own gateway succeeded; the probe was rewritten to craft Ethernet frames)
host firewall back to baseline after cleanup: True
```
