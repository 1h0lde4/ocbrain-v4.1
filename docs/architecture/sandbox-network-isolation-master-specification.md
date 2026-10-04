# Sandbox network isolation: master architectural specification

`DEBT-039 + F6 → C2 → NETWORK_ALLOWLIST → A1`

- **Date:** October 3 2026
- **Status:** **ACCEPTED as the baseline specification of the workstream `sandbox-network-isolation`** (user ruling OD-1, October 4 2026, after one editorial correction: the claim that port 3128 is "less common" was removed). **Decision gates DG-1 (mechanism) and DG-2 (`NamespaceBackend`) are preserved and not pre-decided.** This is a specification, not an implementation: nothing here is IMPLEMENTED or VERIFIED by it. **No repository code, test, capability or contract was changed**; the branch adds this file only.
- **Rulings of October 4 2026 (OD-1 to OD-9):** recorded in section 19 and applied where they change the text below (port, canary image, provisioning path, capacity, evidence protocol, file boundary, DEBT-041 schedule, firewall-manager scope, TC-04 fixture).
- **Base:** `study/b3-host-firewall-supplement` at `34f4b38`, which sits on `study/sandbox-network-redesign` (`ee525d9`) and `sandbox-fabric` (`1b829fc`). Branch: `spec/sandbox-network-isolation-master`.
- **Authority order for this document:** the user's rulings (section 2; they interpret and do not amend the frozen base prompt, addendum and checklist, which are not modified), then those frozen documents, then the two studies (`docs/architecture/sandbox-network-redesign-study.md`, `docs/architecture/sandbox-b3-host-firewall-supplement-study.md`; findings F1 to F28), over this specification.
- **Status vocabulary used in tables:** VERIFIED (observed in a study run), SPECIFIED (a requirement of this design, not yet built), UNVERIFIED (could not be tested), OPEN (needs a ruling).
- **Scope of the word "complete":** this specification closes the path to C2 and A1 only. `sandbox-fabric` stays explicitly incomplete (reconciliation §19.4) while A9, C3 and D9 are open, whatever happens here.

## 1. Purpose, scope, non-goals

**Purpose.** Define, before any implementation, the network topology, enforcement, privilege, lifecycle, capacity, IPv6, capability and evidence rules under which a networked sandbox can truthfully claim `NETWORK_ALLOWLIST`, and decompose the work into controlled, independently auditable batches.

**In scope.**
1. Closing DEBT-039 (a sandbox using a sibling's proxy) and DEBT-040 / F6 (a sandbox reaching host-local services through its gateway) for `DockerBackend`.
2. The conditions under which `NETWORK_ALLOWLIST`, and its pair `NET_NAMESPACE`, may be claimed again (A1), and the order in which C2 and A1 close.
3. The F6 exposure of `NamespaceBackend` on `main`: an audit now, a remediation or withdrawal decision later (ruling D4).
4. A bounded comparative study of the non-firewall hybrid H2 before the final mechanism is chosen (ruling D3).

**Non-goals.**
- Implementing anything, or choosing between the firewall path and H2 (that is decision gate DG-1).
- A9, C3 (the LSM host), D9 (event producer), Dependabot, the §17.5 follow-ups, and DEBT-041 as a prerequisite (it is recommended hardening, not a dependency, section 4.3).
- Any change to `contracts.py`, `admission.py` or `_net_proxy.py`. This design needs none (the proxy already accepts a port in `start(port)`).
- Changing the Stage 5 decision or the frozen documents.

## 2. Rulings that bind this design

From the user's rulings of October 3 2026 and the earlier study decisions:

| ID | Ruling | Binding consequence |
|---|---|---|
| S-§7.2 | F6 is in C2's scope; R1 and R2 mandatory; G3 required; O1 alone insufficient | Both the sibling path and the host-local path must close before `NETWORK_ALLOWLIST` is re-supported |
| S-§7.3 | No option chosen until a later design workstream | This document is that workstream; selection is still gated (DG-1) |
| S-§7.4 | A1 blocked, not broken; no change to `admission.py`, `contracts.py` or the `NET_NAMESPACE` implementation | A1 closes by evidence and by restoring claims, not by new mechanism in the admission layer |
| **D1** | Ratify the B3 reading **conditionally** | A host-firewall supplement is a valid B3 mechanism only when S1 to S7 are satisfied. "Merely having an INPUT rule" does not satisfy B3: topology, bridge identity, privilege, lifecycle, IPv6 and regression conditions must all be enforced |
| **D2** | One-time host provisioning | The long-lived controller does not hold `CAP_NET_ADMIN`. Rules are provisioned once; the system enforces the expected topology and runs a behavioral canary. A Docker-socket helper is the same trust level |
| **D3** | Evaluate H2 before final selection | The first batches must not hard-wire a firewall assumption; H2 gets a bounded comparative study against the ratified B3 baseline |
| **D4** | `NamespaceBackend` is in scope | The spec distinguishes "backend supports `NETWORK_ALLOWLIST`" from "backend has been proven to enforce the isolation contract" |
| **D5** | The 29-network ceiling and IPv6 become explicit, testable requirements | 29 is a stated supported-capacity constraint with a test; IPv6 is detected and enforced, with no silent fail-open path |

**What the privilege ruling does and does not buy (stated so that nobody over-reads it).** The controller already needs the Docker socket, which is root-equivalent on the host. Withholding `CAP_NET_ADMIN` is a least-authority and governance control: it keeps the controller's own code from editing firewall state, and it makes a controller bug unable to widen a rule by accident. It is **not** a defense against a compromised controller, which can already do anything through Docker. The threat this design defends against is a hostile payload inside a sandbox (section 3).

## 3. Threat model

| | In the model | Out of the model |
|---|---|---|
| Attacker | Code running in a sandbox container: uid 0 inside it, Docker's default capability set (including `NET_RAW`, finding F9) unless a batch drops it, `no-new-privileges`, read-only root, no `NET_ADMIN`, no `SYS_ADMIN` | A compromised controller; a root user on the host; a malicious Docker image supplier; the Docker daemon itself |
| Goals | Reach a sibling's proxy (DEBT-039); reach any host-local service (F6); obtain egress under another sandbox's allowlist; make enforcement silently absent | Kernel exploits; `AF_VSOCK`/`socketcall` (A9 track); UDP/ICMP tunneling through the proxy |
| Capabilities assumed | Raw sockets and `AF_PACKET` frames to its gateway's MAC (VERIFIED as usable under default caps, F28); source-address forgery (VERIFIED accepted by a source-keyed rule, F16); port scanning (VERIFIED, F3); concurrent sandboxes | Escaping the workspace jail (the `FILESYSTEM_JAIL` track); reaching the Docker socket (forbidden by A6) |

## 4. Selected baseline topology (proposed as the B3-ratified baseline "T-FW")

"Selected" means: this is the design the specification works out in full as the baseline, so that H2 has a concrete thing to be compared with. Final selection is DG-1.

### 4.1 Topology

1. **One internal Docker network per networked sandbox.** Options: `--internal`, ICC off (`enable_icc=false`), and an explicit bridge name `ocbsbx` + 8 hex characters of the handle id (14 characters, within the 15-character interface-name limit; VERIFIED that Docker honors `com.docker.network.bridge.name` and creates the interface at network creation, before any container, F20). Labeled `ocbrain.sandbox=1` and with the handle id. Docker's default address pools allocate the subnet. The shared network `ocbrain-sandbox-net` is **retired** for new sandboxes (this resolves DEC-4: no new sandbox uses it; the controller does not delete a pre-existing instance without a ruling).
2. **The proxy binds that network's own gateway address on one fixed port** (`AllowlistProxy(bind_ip=<own gateway>, …).start(PORT)`). `PORT` is a single constant shared by the backend, the provisioning artifact and the canary. `PORT` is **3128** (ruled, OD-4; it is the value that was tested). A collision with a host service on that port fails closed in both directions (VERIFIED, F21) and is a deployment concern to document, not a reason to change the value.
3. **Host `INPUT` rules provisioned once, static, with no per-sandbox rule:**

```
iptables -w -I INPUT -i ocbsbx+ -j DROP
iptables -w -I INPUT 1 -i ocbsbx+ -p tcp --dport <PORT> -m addrtype --dst-type LOCAL --limit-iface-in -j ACCEPT
```

   The destination match is mandatory: without it a sandbox with `NET_RAW` reached a sibling's gateway and the host's primary address on the proxy port (VERIFIED, F28); with it both failed while the sandbox's own gateway worked (VERIFIED, F28). A chain-structured form (a dedicated chain entered by a single jump) is allowed if batch B10 re-verifies it; the tested form is the one above.
4. **The sandbox container joins only that network**, with `HTTP_PROXY`/`HTTPS_PROXY` pointing at `http://<gateway>:<PORT>` as today. Networks created without `allowed_hosts` are not created at all: those sandboxes keep `--network none`.
5. **Behavioral canary** before the workload starts, on the sandbox's own network (section 7).
6. **IPv6 guard** and **capacity guard** (sections 8 and 9).

### 4.2 What each part closes

| Threat | Closed by | Evidence |
|---|---|---|
| DEBT-039: a sibling's proxy | Separate networks (no route, F7) plus the destination-matched rule (F28) | F7, F14, F28 |
| F6: host-local TCP and UDP services | Catch-all `DROP` on the sandbox interface; the only `ACCEPT` is the proxy port at the ingress interface's own address | F14, F20, F28 |
| Source forgery (F16) | The rule is keyed on the ingress interface, never on a source address | F14 |
| Policy duplication (B3) | Rules carry no destination; all allow/deny decisions stay in `AllowlistProxy` | F14, F15 |
| Enforcement silently absent | Behavioral canary, which needs no firewall privilege to run (listing rules needs `CAP_NET_ADMIN`, F13) | F22 |
| Naming drift | Topology validation before use, plus the canary | F21 |

### 4.3 What is deliberately not required

- **DEBT-041 (dropping `NET_RAW`)** is not on the critical path and is **scheduled after B13 and B21** (ruling OD-8). It is not a prerequisite of T-FW: with the destination match, the `NET_RAW` attack of F28 fails. It stays recommended defense in depth and is a prerequisite of any source-address design (O2, and O4 on a shared network, F16). If a later change removes or weakens the destination match, DEBT-041 becomes a prerequisite again; TC-04 runs with `NET_RAW` present, granted explicitly by its fixture so that it survives DEBT-041, precisely so that it would catch that.
- **No firewall code in the controller**, and no `CAP_NET_ADMIN` there (ruling D2, test TC-21).

## 5. Invariants

| ID | Invariant | Enforced by | Tests |
|---|---|---|---|
| INV-1 | A networked sandbox can reach, from its network, only its own proxy endpoint: own gateway address, the fixed port, TCP | Topology and static rules | TC-01 to TC-04 |
| INV-2 | Destination policy is decided only in `AllowlistProxy`; the firewall carries no destination, host or allowlist input | Rule constant; B3 conditions S1 to S4 | TC-05 |
| INV-3 | Fail closed: if enforcement cannot be established or verified, no networked sandbox is created and nothing is left behind | Canary, topology validation, `_abort_create` | TC-06 to TC-09 |
| INV-4 | The controller holds no firewall privilege at run time | Provisioning is a separate act | TC-21, TC-20 |
| INV-5 | A capability is claimed only while its evidence exists, per backend: advertised is not proven | Batches B13, B21, B30; claim/evidence coupling | TC-18, TC-19 |
| INV-6 | Every acquired resource (network, proxy, container, workspace) is cleaned immediately or retained in a destroyable handle (D10); handle bookkeeping is race-safe (D11) | Lifecycle ordering, per-handle lock, reaper | TC-09 to TC-11 |
| INV-7 | At most 29 sandbox networks exist concurrently; the 30th request is refused with a defined error and no residue | Capacity guard | TC-13 |
| INV-8 | No silent IPv6 path: either IPv6 isolation equivalence is proven, or deployment is refused when IPv6 is enabled | IPv6 guard | TC-14, TC-15 |
| INV-9 | Enforcement and refusals are observable (structured logs now; `EventStream` when D9 is resolved; no second event mechanism, addendum) | Logging at each decision | review |

## 6. B3 conditions S1 to S7 as enforceable requirements (ruling D1)

D1 says a firewall supplement is a valid B3 mechanism **only when S1 to S7 are satisfied**, and that having an `INPUT` rule is not enough. Each condition is therefore a requirement with an enforcement point and a test; a batch cannot be accepted while any is unmet.

| S | Requirement | Enforcement | Test |
|---|---|---|---|
| S1 | Rules carry no destination, hostname or protocol-level policy; the proxy alone decides destinations | The rule text is a fixed constant with no allowlist input; the provisioning tool takes no host argument | TC-05 |
| S2 | Keyed on the ingress bridge interface, never on a source address | `-i ocbsbx+` | TC-05, TC-04 |
| S3 | Only permit: TCP to the proxy's bound address and port, destination an address of the ingress interface; all else dropped | The two rules of section 4.1 | TC-01 to TC-04, TC-05 |
| S4 | The proxy port in the rule comes from the same constant as the proxy's bind; a mismatch fails closed | One `PORT` constant; provisioning and backend import or parse the same value | TC-05 (equality), TC-07 (a drift makes the canary's positive control fail) |
| S5 | Installation and removal are fail-closed in order and tied to the handle (D10/D11) | With static rules there is no per-sandbox rule; the per-handle resources are the network, proxy and container, set up and torn down in the orders of section 10 | TC-09, TC-10 |
| S6 | Enforcement is verified by behavior, not by the existence of a rule | The canary, which fails closed | TC-06, TC-07 |
| S7 | The firewall knowledge lives in a separate, narrow place with its own review and file boundary; `docker_backend.py` calls it and grows no rule logic | The provisioning artifact is outside the controller; the controller module `_sandbox_network.py` holds only the topology, canary, capacity and IPv6 logic | review; file-touch check in each batch |

## 7. Privilege and provisioning (ruling D2)

1. **Provisioning is a distinct act performed by a privileged operator or deployment step**, outside the controller process: it installs the two rules of section 4.1 (idempotently), can verify them, and can remove them. The tested privilege is `CAP_NET_ADMIN` in the host network namespace (F13).
2. **The controller verifies enforcement by behavior only**, because even listing the rules needs `CAP_NET_ADMIN` (F13). The canary is therefore the controller's only enforcement check and cannot be skipped by configuration.
3. **Canary.** On the sandbox's own network, after the proxy is started and before the workload container is created, a throwaway container: (a) positive control: connects to `<own gateway>:<PORT>` and must succeed; (b) negative probe: connects to a controller-owned ephemeral listener bound to `0.0.0.0` on the host and must fail within a bounded time. Anything other than "positive succeeded and negative failed" refuses the create. A canary whose positive control fails never reports "enforced" (so a dead network is not mistaken for a working rule). Measured cost: 2.3 s including a container start (F22). Per-create execution is required in v1 (priority order: governance and isolation before performance); caching is a later, evidence-backed change.
4. **Canary image.** The canary needs a TCP-connect capability inside the container. The sandbox image is caller-supplied and may lack one. The canary image is therefore (ruled, OD-3) a **dedicated, minimal, immutable-digest-pinned image provisioned in advance, with a deterministic TCP-connect primitive, and never pulled during `create()`**. Positive and negative controls run on **every** create in v1. The exact digest is fixed in batch B12, after it has been verified against the repository and the host.
5. **Residual risk, stated plainly:** rules can be flushed or reordered after the canary by another host tool (a firewall-manager reload was not tested, F18). The canary detects this at the next create; it cannot close the window in between. Mitigation: re-run the canary on a timer and after a daemon-restart signal; treat a failure as "refuse new networked sandboxes".
6. **Provisioning artifact.** A script or document with install, verify and remove modes, an exact expected-rules constant, and an evidence record of the kernel, Docker and iptables variant it was verified on (nf_tables variant tested; legacy untested). Path (ruled, OD-4): `scripts/sandbox/provision_network_isolation.sh`, with `install`, `verify` and `remove` modes; `PORT` and the interface prefix have a single source of truth shared with the backend. Firewall-manager coexistence (ufw, firewalld, manager reloads, reboot persistence) is **out of scope for v1** (OD-9): it is documented as unverified or unsupported, the behavioral canary is the fail-closed detector when the expected enforcement disappears, and B10 verifies only the exact firewall backend and variant it was tested on. A manager-integration design is a separate workstream.

## 8. Capacity requirement (ruling D5)

- **Requirement.** `MAX_CONCURRENT_SANDBOX_NETWORKS = 29`: a named constant, enforced by a counting limiter that reserves a slot before the network is created and releases it only after removal is confirmed. A request beyond the limit raises a defined error (`DockerBackendError` family) and leaves no network, container, proxy or workspace behind.
- **What 29 is and is not (so the test is honest).** It was measured on one host as the number of additional internal networks Docker accepted under its default address pools with two networks already present (study F8: `all predefined address pools have been fully subnetted` at the 30th). It is a property of the pool configuration and of the networks already present, not a Docker constant. The specification therefore requires: (a) the constant is the supported maximum, as ruled; (b) a start-up or provisioning **capacity probe** confirms the daemon can actually create that many on this host, and a host that cannot is refused for networked sandboxes; (c) the effective limit is the lower of the constant and what the probe found. Ruled (OD-5): the effective limit is `min(29, probe result)`; raising the ceiling (an explicit dedicated address pool) is out of scope and needs a new ruling.
- **Applies to** every per-sandbox-network design (the T-FW baseline and H2). `NamespaceBackend` allocates /30s from `10.200.0.0/16` and has its own limit, which is not covered by this constant.

## 9. IPv6 requirement (ruling D5)

- **Detection.** IPv6 is treated as **off** only if `/proc/sys/net/ipv6` is absent or `disable_ipv6` is 1 for `all` and `default`; anything else is **on** or **unknown**. Detection reads injectable sources so it can be unit tested.
- **Behavior in v1.** If IPv6 is on or unknown, **creating a networked sandbox is refused** with a defined error that names the reason. This is the fail-closed choice: IPv6 behavior could not be tested on this host (it boots with `ipv6.disable=1`, F26), so the specification does not claim equivalence.
- **The other branch of the ruling** ("prove equivalent IPv6 isolation") is a later batch (B14) that needs an IPv6-capable host: an `ip6tables` equivalent of the section 4.1 rules plus a test that a `::`-bound host listener is unreachable. Until it exists and passes, the refuse branch is the only supported behavior and IPv6 isolation is UNVERIFIED.
- **Network option.** Sandbox networks are created with IPv6 disabled and the topology validation asserts it.

## 10. Lifecycle and failure model (D10, D11)

Order of acquisition in `create()` for a networked sandbox, and the reverse for unwinding and `destroy()`:

1. Capacity slot reserved. 2. IPv6 guard evaluated. 3. Network created and its topology validated (internal, ICC off, IPv6 off, expected bridge name and labels). 4. Proxy started on `<gateway>:<PORT>`. 5. Canary run. 6. Workload container created. 7. Workload started (existing `run()` path). Teardown: container, proxy, network (removal confirmed), slot released.

| Failure point | Required result |
|---|---|
| Capacity or IPv6 refusal | Raised before any resource exists |
| Network create or topology validation fails | Remove the network if it exists; release the slot |
| Proxy bind fails (collision, F21) | Remove the network; release the slot |
| Canary fails or times out | Stop the proxy; remove the network and canary container; release the slot |
| `docker create` or `docker start` fails | Existing `_abort_create` unwind extended with proxy stop, network removal and slot release |
| Removal of the network cannot be confirmed | The handle is retained (as `destroy()` already does for containers); the slot stays held |
| Controller crash | Networks and containers carrying the label outlive it (rules are not per-sandbox, so no rule leaks, unlike per-sandbox rules, F18). A **reaper** at start-up removes labeled networks and containers that no live handle owns, and nothing else |

D11: the existing per-handle lock covers `destroy()`; the capacity limiter is a single lock-protected counter; concurrent create/destroy must neither exceed the limit nor leak (TC-10, TC-13). The static rules make D11 simpler than per-sandbox rules: there is no rule state to race.

## 11. The gate chain

```
DEBT-039 (sibling proxy) ─┐
                          ├─► C2 ─┐
DEBT-040 / F6 (host-local)─┘       │
                                   ├─► NETWORK_ALLOWLIST re-claimed ─► A1 PASS
NET_NAMESPACE (direct gate, G2) ───┘
```

| Step | Closes when | Gates (all must pass) | Notes |
|---|---|---|---|
| DEBT-039 closed | G1 passes on a provisioned host, on the final code | G1 = TC-03 and TC-04 | Registers the closure in `KNOWN_ISSUES.md` by a separate PR |
| DEBT-040 closed | G3 passes | G3 = TC-01 and TC-02 | DEBT-040 stays open for `NamespaceBackend` until G7 passes there (ruling D4) |
| C2 PASS (Docker) | DEBT-039 and DEBT-040 closed for `DockerBackend`, plus G4, G5, G6 | G4 = TC-06 to TC-13 and TC-21; G5 = TC-05 and TC-20; G6 = TC-14 and TC-15 (TC-15 skipped with a stated reason on a host without IPv6, and then IPv6 stays refused) | The other C2 bullets (raw connection, `request.env` override) keep their existing tests |
| `NET_NAMESPACE` re-earned | G2 passes: the netns differs from the host's; concurrent sandboxes have pairwise-distinct netns | G2 = TC-16 | Independent of everything above; it must not resurrect `NETWORK_ALLOWLIST` or C2 |
| `NETWORK_ALLOWLIST` re-claimed | C2 PASS and `NET_NAMESPACE` re-earned, in the same change that records the evidence | n/a | `_CAPS` then goes from 7 to 9 of 12 |
| A1 PASS | Both claims present; the admission-layer and integration tests pass | G8 = TC-18 | `admission.py` and `contracts.py` unchanged (ruling S-§7.4) |

A capability is added to `_CAPS` only in the batch that records its evidence. `NETWORK_DENY_DEFAULT`, `SECCOMP`, `USER_NAMESPACE` are untouched.

## 12. `NamespaceBackend` (ruling D4)

- **Current evidence.** A sandbox run with `allowed_hosts` reached a `0.0.0.0` host listener through its gateway `10.200.0.1`; a loopback listener refused (F24; observed once, one host, the backend otherwise unaudited). It advertises `NETWORK_ALLOWLIST` on `main`.
- **The distinction the ruling requires.** Two different statements are kept apart everywhere: **advertised** (the backend lists the capability) and **contract-verified** (the shared conformance suite, `tests/core/sandbox/test_network_isolation_contract.py`, passes for that backend on a provisioned host). The contract-verified status is recorded per backend in the reconciliation document and evidenced by the suite; it is not a new public enum value (the addendum allows new `SandboxCapability` values only with a demonstrated cross-backend need, and none is needed to express this).
- **Process.** B04 runs the shared conformance cases against `NamespaceBackend` with strict expected-failure markers that name DEBT-040, so CI stays green while the gap is open and the marker fails the build the moment the gap closes without the marker being removed. Whether the remediation is the same pattern (a prefix-keyed rule on the host veth, by analogy; NOT TESTED) or a withdrawal of the claim from `NamespaceBackend` is **decision gate DG-2**, after B04. Withdrawing the claim changes behavior on `main` (admission would reject `allowed_hosts` requests) and reopens the DEBT-023 closure, so it is a user decision, not an engineering default.
- **Non-blocking.** The ruling says the F6 exposure "need not automatically block unrelated redesign work": batches for `DockerBackend` do not wait for DG-2.

## 13. H2 comparative study (ruling D3)

H2: per-sandbox network with Docker's `inhibit_ipv4` or `gateway_mode_ipv4=isolated` (no IPv4 address on the host bridge, VERIFIED, F23) and the proxy in a sidecar container. B05 compares H2 with T-FW on the user's four named criteria, with experiments that were not run in the B3 study:

| Criterion | T-FW baseline (known) | H2 question to answer by test |
|---|---|---|
| Privilege | One-time host provisioning, `CAP_NET_ADMIN` at that moment | Does H2 need any host-level privilege beyond the Docker socket? |
| Lifecycle | One network, proxy and container per sandbox; no rule state | A sidecar adds a second container and its own egress network: its create/destroy ordering under D10/D11, and orphan behavior |
| IPv4/IPv6 | IPv6 refused when enabled (section 9) | Does an address-less bridge also remove IPv6 exposure? Needs an IPv6-capable host, otherwise UNVERIFIED |
| Sidecar complexity | None | Can a sandbox reach the sidecar and nothing else with ICC off and no bridge address? Does `AllowlistProxy` (TCP, bound to an address) run unchanged in a sidecar? What does the sidecar's own egress network allow, and is it a second F6? |

Output: a study document and a comparison table, input to DG-1. **Reopen condition for this specification:** if DG-1 selects H2, sections 4, 7 and 10 are replaced by an H2 section; sections 5, 8, 9, 11, 12 and the test catalogue (except TC-05, TC-20, TC-21) carry over.

## 14. Test catalogue

Host requirements: **D** = reachable Docker daemon and the test image; **P** = provisioned rules; **R** = root and firewall privilege (to install and remove rules or to drop capabilities); **V6** = IPv6-capable host. Every host test ends by comparing the firewall (`iptables-save` without counters) and the Docker network and container lists with their start-of-test baseline. Every injecting test asserts that its injection fired.

| ID | Test | Needs | Gate |
|---|---|---|---|
| TC-01 | A `0.0.0.0` TCP listener is unreachable from a networked sandbox through its gateway; a `127.0.0.1` listener is a negative control; the sandbox's own proxy still answers; passes with `DOCKER-USER` empty (F12) | D P | G3 |
| TC-02 | A `0.0.0.0` UDP listener receives no datagram from the sandbox | D P | G3 |
| TC-03 | Two concurrent sandboxes with different allowlists: B cannot reach A's proxy by a handed port, by scanning the gateway ranges, by `CONNECT`, or by plain HTTP; A's allowed host `200`, B's disallowed host `403` | D P | G1 |
| TC-04 | The attacker is a test-owned container joined to the sandbox's own network with `NET_RAW` **explicitly added by the test fixture** (the backend itself forbids `--cap-add`, A6), so the case stays valid after DEBT-041 drops `NET_RAW` from normal sandboxes: a crafted frame (`AF_PACKET`) to the sibling's gateway and to the host's primary address on the proxy port gets no reply; the same probe to the own gateway gets a SYN-ACK (F28) | D P | G1 |
| TC-05 | Rule ownership: the provisioning artifact's rule text equals the expected constant; it contains no hostname and takes no allowlist input; its port equals the backend's `PORT`; its interface prefix equals the backend's naming prefix | none | G5 |
| TC-06 | Fail closed: with the rules absent, or a canary forced to fail, `create()` raises and no network, container, proxy or workspace remains | D (R for the real-absent case) | G4 |
| TC-07 | Canary controls: a failing positive control never reports "enforced"; a negative probe that connects reports "not enforced"; the canary is bounded in time; a `PORT` drift makes the positive control fail | D P | G4 |
| TC-08 | Topology validation: a network with a non-matching bridge name, not internal, ICC on, or IPv6 on is rejected before any container starts (F21) | D | G4 |
| TC-09 | D10: an injected failure at each step of section 10 leaves the baseline restored | D P | G4 |
| TC-10 | D11: at least 8 concurrent create/destroy cycles, a double `destroy()`, and a `destroy()` racing `create()`: networks, containers and the capacity counter return to baseline | D P | G4 |
| TC-11 | Crash recovery: after a simulated controller kill, the start-up reaper removes exactly the labeled networks and containers and nothing else | D P | G4 |
| TC-12 | Port collision: a pre-bound wildcard listener on `PORT` makes `create()` fail closed and clean up (F21) | D P | G4 |
| TC-13 | Capacity: 29 concurrent networked sandboxes are accepted, the 30th is refused with the defined error and no residue, and slots are released after destroy and after each failure path | D P | G4 |
| TC-14 | IPv6 guard unit test: detection matrix over injected sources (absent / 1 / 0 / unreadable) gives supported or refuse as in section 9 | none | G6 |
| TC-15 | IPv6 on a real host: a `::`-bound host listener is unreachable from a sandbox, or deployment is refused; skipped with the stated reason on a host without IPv6 | V6 D P | G6 |
| TC-16 | `NET_NAMESPACE`: the sandbox's netns differs from the host's; concurrently created sandboxes have pairwise-distinct netns | D | G2 |
| TC-17 | `NamespaceBackend` runs TC-01 to TC-03 equivalents; strict expected failure until DG-2 is executed | namespace env | G7 |
| TC-18 | A1: with both claims, `check_admission()` admits an `allowed_hosts` request and the integration path reaches the proxy (`200` allowed, `403` disallowed); the paired-claim invariant test is retained | D P | G8 |
| TC-19 | Claim/evidence coupling (proposed): `NETWORK_ALLOWLIST` in a backend's `_CAPS` implies the conformance cases for that backend carry no expected-failure marker | none | G8 |
| TC-20 | Provisioning: installing twice yields exactly one rule pair; removal restores the baseline snapshot; verify mode exits non-zero when the rules are absent | R | G5 |
| TC-21 | The controller runs with `net_admin` removed from its bounding set and still completes create, run and destroy on a provisioned host (proves ruling D2) | D P R | G4 |

**Evidence procedure.** The repository's `tests` job runs `pytest tests/`; since PR #55 (FZ-07, on `main` at `e438387`) it records pytest's real exit code and its gate tolerates only failures listed in the known-failures manifest, and only with exit code 1, failing on collection or setup errors, INTERNALERROR and zero-passed runs; Docker-gated tests skip when no daemon is reachable, and none of the P or R tests can pass on an unprovisioned runner. The gates are therefore **host-evidenced**: each batch that earns a gate records, in the reconciliation document (the canonical evidence record, ruling OD-6): the final commit SHA, the branch and base, the host fingerprint (kernel, Docker, iptables variant), the provisioning state, the exact command, the result, a timestamp, the cleanup and baseline check, and any artifact or hash needed to reproduce the observation. A failing gate must never be hidden by adding it to the known-failure manifest; expected failures use strict markers that name the debt (`PROJECT_INSTRUCTIONS` §16.4).

## 15. File-touch boundary for the workstream `sandbox-network-isolation` (ratified, OD-7; anything outside it needs a fresh ruling)

| Allowed | Not allowed (without a new ruling) |
|---|---|
| `core/sandbox/backends/docker_backend.py`; a new `core/sandbox/backends/_sandbox_network.py`; new and existing tests under `tests/core/sandbox/`; `scripts/sandbox/` (provisioning); `docs/architecture/` documents; `KNOWN_ISSUES.md` only through its own PR from `main` | `contracts.py`, `admission.py`, `_net_proxy.py`, the frozen addendum and checklist; `namespace_backend.py` outside B30; any change that adds a `SandboxCapability` value |

Every batch also runs `python3 scripts/check_drift.py` and keeps it green.

## 16. Batches

**Structure.** Phases run in order; a batch is eligible when its dependencies are done. Every batch has its own branch, its own PR and its own evidence, and a PR is merged only on an explicit instruction. Each batch records the twelve required items. "Baseline" is the commit or state the batch starts from.

| Batch | Depends on | Unblocks |
|---|---|---|
| B00 | the user's merge decisions | B01, B02, B03, B05 |
| B01 | B00 | B04, DG-1 |
| B02 | B00 | B21 |
| B03 | B00 | B10, B11 (after DG-1) |
| B04 | B01 | DG-2 |
| B05 | B00 | DG-1 |
| DG-1 | B01, B05 (user decision) | B10 |
| DG-2 | B04 (user decision) | B30 |
| B10 | DG-1(a), B03 | B11 |
| B11 | B10, B03 | B12 |
| B12 | B11 | B13 |
| B13 | B12 | B21 |
| B14 (optional) | B13 and an IPv6-capable host | none |
| B21 | B02, B13 | B22 |
| B22 | B21 | none |
| B30 | B04, DG-2 | none |
| DEBT-041 hardening (a separate item, not a batch of this chain) | B13 and B21 (ruling OD-8) | none |

**Ruled execution order (October 4 2026):** B00; then B01, B02, B03 and B05; then B04; then DG-1. Only if DG-1 selects T-FW: B10, B11, B12, B13, B21, B22. B14 stays optional and needs a real IPv6-capable host. B30 is gated separately by DG-2. No effort goes into the firewall path before H2 has been evaluated.


### Phase P0: preconditions (the user's actions, no code)

#### B00. Repository baseline reconciliation

| Item | Content |
|---|---|
| Baseline | `main` at its current tip (it moved to `80a1bb8` during the studies); `sandbox-fabric` `1b829fc`; open PRs #48 (DEBT-040), #49 (DEBT-041), #50 (the `test_net_proxy.py` fix, base `sandbox-fabric`) |
| Purpose | Settle the branch lineage the implementation will build on |
| Dependencies | The user's merge decisions |
| Scope | Merge or not PRs #48, #49, #50; decide whether `main` is merged into `sandbox-fabric` (36 ahead, 27 behind at last count); choose the base branch for P1 to P3 (expected: a new branch from `sandbox-fabric` after PR #50) |
| Out of scope | Any code change |
| Files | none |
| Requirements | Each merge is an explicit instruction; the second `KNOWN_ISSUES.md` PR needs a branch update for the shared insertion point; **`main` is not merged wholesale into `sandbox-fabric` to simplify the graph without first checking the resulting tree against the intended baseline** (the user's caution of October 4 2026) |
| Tests | CI on each PR (checks were green at opening) |
| Acceptance | The base branch for B01 is named and verified (`git ls-remote`) |
| Invariants | No force-push, no history rewrite |
| Risks | Divergence of `sandbox-fabric` from `main` grows; the proxy and its tests exist only on `sandbox-fabric` |
| Evidence | Remote refs, PR states |
| Resulting state | A named, current base branch |
| Eligible next | B01, B02, B03, B05 (B04 after B01) |

### Phase P1: mechanism-neutral foundation (D3: nothing here may presuppose the firewall)

#### B01. Contract conformance suite (red)

| Item | Content |
|---|---|
| Baseline | The B00 base branch; `DockerBackend` with `NETWORK_ALLOWLIST` withdrawn |
| Purpose | Write the mechanism-independent definition of "isolated" as executable tests before any mechanism exists |
| Dependencies | B00 |
| Scope | `tests/core/sandbox/test_network_isolation_contract.py`: TC-01, TC-02, TC-03, TC-04 as backend-parametrized cases; host-gating helpers (D, P); strict expected-failure markers naming DEBT-039 and DEBT-040; the F11-style read-to-EOF helper reused, never single `recv()` |
| Out of scope | Any source change; a firewall assumption in the test bodies (they probe behavior from inside a sandbox and from the host) |
| Files | one new test file; possibly a shared helper under `tests/core/sandbox/` |
| Requirements | The cases create networked sandboxes by calling `create()` directly (admission withdrawn); every case asserts its injection or setup fired; cleanup restores the baseline |
| Tests | TC-01 to TC-04 |
| Acceptance | On a Docker host without provisioning the cases fail for the documented reason (the marker's `raises` and message match) and not for a harness error; on a host without Docker they skip with the reason; the suite is collected by `pytest` |
| Invariants | INV-1 as the thing under test |
| Risks | A case that fails for the wrong reason would be hidden by a loose marker; mitigated by `raises=` and a reason match |
| Evidence | Run output on this kind of host, recorded in the reconciliation document with the OD-6 fields |
| Resulting state | Red, executable gates for G1 and G3; no behavior change |
| Eligible next | B04, DG-1 (together with B05) |

#### B02. `NET_NAMESPACE` gate (G2)

| Item | Content |
|---|---|
| Baseline | The B00 base branch; `_CAPS` at 7 of 12 |
| Purpose | Re-earn `NET_NAMESPACE` alone (ruling of the earlier session: it must not resurrect `NETWORK_ALLOWLIST` or C2) |
| Dependencies | B00 |
| Scope | TC-16; `NET_NAMESPACE` re-added to `DockerBackend._CAPS` in the same PR; reconciliation §18 updated |
| Out of scope | `NETWORK_ALLOWLIST`; any topology change; `admission.py` |
| Files | `docker_backend.py` (`_CAPS` only), `test_docker_backend.py` or the new suite, the reconciliation document |
| Requirements | The test compares the sandbox's network namespace identity with the host's and between two concurrent sandboxes |
| Tests | TC-16 |
| Acceptance | TC-16 passes; `_CAPS` is 8 of 12; A1's paired-claim test still passes (it only constrains `NETWORK_ALLOWLIST ⇒ NET_NAMESPACE`); no other claim changes |
| Invariants | INV-5 (claim added only with its evidence in the same change) |
| Risks | Someone reads `NET_NAMESPACE` as isolation evidence (the earlier withdrawal exists to prevent that); the PR text and docstring must say it is not |
| Evidence | Test run; `_CAPS` diff |
| Resulting state | `NET_NAMESPACE` claimed with a direct test; `NETWORK_ALLOWLIST` still withdrawn |
| Eligible next | B21 (needs it), any |

#### B03. Capacity and IPv6 guard primitives

| Item | Content |
|---|---|
| Baseline | The B00 base branch |
| Purpose | Build the two guards that apply to every per-sandbox-network design, with no dependence on the firewall |
| Dependencies | B00 |
| Scope | New `core/sandbox/backends/_sandbox_network.py` holding: the counting limiter and `MAX_CONCURRENT_SANDBOX_NETWORKS = 29`; the capacity probe interface; the IPv6 detection and decision function with injectable sources. Not wired into `create()` |
| Out of scope | Network creation, rules, canary, wiring |
| Files | the new module; new unit tests |
| Requirements | Section 8 (limit, effective limit `min(29, probe result)` per OD-5, reservation before create, release after confirmed removal, defined error) and section 9 (detection matrix, refuse by default) |
| Tests | TC-14; limiter unit tests (limit, release, concurrent reservation without exceeding) |
| Acceptance | Unit tests pass; mypy clean; no import cycle; `check_drift.py` green |
| Invariants | INV-7, INV-8 |
| Risks | If DG-1 chooses a design without per-sandbox networks, this is re-scoped (reopen condition) |
| Evidence | Test run, mypy |
| Resulting state | Two inert, tested guards |
| Eligible next | B11, B12 (after DG-1) |

#### B04. `NamespaceBackend` F6 audit

| Item | Content |
|---|---|
| Baseline | B01 merged on the base branch; `main`'s `namespace_backend.py` |
| Purpose | Establish, by the shared suite, what `NamespaceBackend` does under the contract (ruling D4) |
| Dependencies | B01 |
| Scope | TC-17: parametrize B01's cases over `NamespaceBackend` with strict expected-failure markers naming DEBT-040; a findings section in the reconciliation document; the F24 probe turned into a committed case |
| Out of scope | Any change to `namespace_backend.py`; deciding remediation or withdrawal |
| Files | the suite from B01; the reconciliation document |
| Requirements | Cases skip with a reason when namespaces or `ip netns` are unavailable (as `test_allowed_hosts.py` does) |
| Tests | TC-17 |
| Acceptance | The F6 case fails for the documented reason and is marked strict; the sibling case is evaluated and its result recorded (not yet known, since `NamespaceBackend` allocates a distinct /30 per sandbox, which may already prevent it) |
| Invariants | INV-5 |
| Risks | The existing `test_allowed_hosts.py` has an environment gate; where it skips in CI the evidence is local |
| Evidence | Run output |
| Resulting state | A recorded, tested picture of `NamespaceBackend`'s status; input to DG-2 |
| Eligible next | DG-2 |

#### B05. H2 bounded comparative study

| Item | Content |
|---|---|
| Baseline | The B00 base branch (study documents only) |
| Purpose | Give DG-1 the evidence it lacks (ruling D3) |
| Dependencies | B00 |
| Scope | Section 13's criteria and experiments; a study document and a comparison table against T-FW; a time box agreed with the user |
| Out of scope | Implementation; choosing |
| Files | one study document |
| Requirements | Every experiment states its environment; IPv6 claims are UNVERIFIED unless an IPv6 host is available; the sidecar's own egress is evaluated as a possible second F6 |
| Tests | n/a (experiments, appendices) |
| Acceptance | Each of the four criteria has an answer marked VERIFIED, UNVERIFIED or OPEN, with evidence |
| Invariants | No design is chosen in the document |
| Risks | Open-ended scope; hence the time box |
| Evidence | Appendices with scripts and outputs, as in the earlier studies |
| Resulting state | An evaluated alternative |
| Eligible next | DG-1 |

#### DG-1. Mechanism selection (user decision)

Inputs: the B3 study, this specification, B05, B01. Outcomes: (a) T-FW proceeds to P2; (b) H2 is selected and a supplement specification replaces sections 4, 7, 10 before P2; (c) a hybrid is specified. Criteria to apply: privilege and provisioning burden; lifecycle risk under D10/D11; IPv4/IPv6 behavior; complexity; evidence strength. Nothing in P2 starts before this decision.

#### DG-2. `NamespaceBackend` disposition (user decision)

Inputs: B04. Outcomes: (a) remediate to the isolation contract (B30); (b) withdraw `NETWORK_ALLOWLIST` from `NamespaceBackend` and reopen DEBT-023, as a deliberate behavior change on `main`; (c) leave advertised-but-unproven with DEBT-040 open and the strict markers in place, as an explicit, time-limited exception. DG-2 does not gate `DockerBackend` work.

### Phase P2: T-FW implementation (only after DG-1(a))

#### B10. Provisioning artifact and verification tool

| Item | Content |
|---|---|
| Baseline | DG-1(a); B03 merged |
| Purpose | Make the host rules a reviewed, idempotent, removable, verifiable artifact outside the controller |
| Dependencies | DG-1, B03 |
| Scope | Install, verify and remove modes for the two rules of section 4.1 (or a re-verified chain form); the `PORT` constant and the interface prefix as the single shared source; the evidence record format; documentation of the privilege, of the nf_tables variant tested, and of the untested items (legacy iptables, firewall managers, reboot persistence) |
| Out of scope | Controller code; the canary; firewall-manager coexistence (OD-9) |
| Files | `scripts/sandbox/provision_network_isolation.sh` (ruled path), tests for TC-05 and TC-20, the reconciliation document |
| Requirements | The rule text has no destination, host or allowlist input (S1); the destination match is present (F28); installation is idempotent; removal restores the baseline; verify mode returns non-zero when the rules are absent; the exact firewall backend and variant it was tested on are verified and recorded; `PORT` is 3128 and shared with the backend |
| Tests | TC-05, TC-20; a re-run of E9 as TC-04's precondition |
| Acceptance | Both tests pass on a host with root; exact rule text recorded; the evidence record lists kernel, Docker and iptables variant |
| Invariants | INV-2, INV-4, S1 to S4 |
| Risks | Rule ordering drift against other host tools; a firewall manager reload flushing the rules (not tested): documented and covered by the canary, not claimed solved |
| Evidence | Run output and snapshot comparisons |
| Resulting state | A provisioned host can be reproduced from the repository |
| Eligible next | B11 |

#### B11. Per-sandbox network lifecycle in `DockerBackend`

| Item | Content |
|---|---|
| Baseline | B10 merged; B03 merged |
| Purpose | Replace the shared network with per-sandbox networks and bring them under D10 and D11 |
| Dependencies | B10, B03 |
| Scope | Network creation with the options of section 4.1, labels and naming; topology validation; unwind and `destroy()` extended; the start-up reaper; the capacity limiter wired in; the IPv6 guard wired in; the shared network no longer used (DEC-4) |
| Out of scope | The proxy port and canary (B12); capability claims |
| Files | `docker_backend.py`, `_sandbox_network.py`, `test_docker_backend.py` |
| Requirements | Section 10's order and failure table; removal confirmed before a handle is forgotten; slot released only then |
| Tests | TC-08, TC-09 (the network steps), TC-10, TC-11, TC-13, TC-14 integration |
| Acceptance | The new tests pass; the existing 88 `DockerBackend` tests and the full `tests/core/sandbox` suite still pass; orphan checks clean (0 containers, 0 sandbox networks, 0 temp directories) |
| Invariants | INV-6, INV-7, INV-8 |
| Risks | The change touches the create/destroy paths that D10/D11 were hardened on: every existing injecting test must still assert its injection fired; the capacity limiter introduces a new lock whose interaction with the per-handle lock must be shown deadlock-free |
| Evidence | Test run, mutation checks of the new unwind steps |
| Resulting state | Per-sandbox networks with correct lifecycle, still without proxy-port or canary enforcement |
| Eligible next | B12 |

#### B12. Fixed-port proxy, canary and fail-closed `create()`

| Item | Content |
|---|---|
| Baseline | B11 merged |
| Purpose | Make enforcement verified at every create and make absent enforcement a refusal |
| Dependencies | B11 |
| Scope | `AllowlistProxy.start(PORT)` on the sandbox's own gateway; the canary of section 7 (a pre-provisioned, immutable-digest-pinned image that is never pulled during `create()`, positive and negative controls on every create, a time bound; the digest is fixed here after verification against the repository and host); refusal paths; structured logging of each decision; canary re-run policy |
| Out of scope | `_net_proxy.py` (unchanged); rule installation |
| Files | `docker_backend.py`, `_sandbox_network.py`, tests |
| Requirements | Sections 4.1, 7 and 10; the canary cannot be disabled by configuration |
| Tests | TC-06, TC-07, TC-09 (the remaining steps), TC-12, TC-21 |
| Acceptance | On a provisioned host `create()` succeeds and the canary reports enforced; with rules removed `create()` refuses and leaves nothing; with the controller's `net_admin` removed the full cycle still works |
| Invariants | INV-3, INV-4, S4, S6 |
| Risks | The canary digest must be verified before it is fixed; a canary that is too permissive; extra per-create latency (2.3 s measured); a collision with a host service on `PORT` fails closed and is a deployment concern to document |
| Evidence | Test run on a provisioned host; mutation check that a no-op canary is caught |
| Resulting state | Enforcement is verified per sandbox; the contract cases of B01 can now pass |
| Eligible next | B13 |

#### B13. Gate evidence and C2 closure

| Item | Content |
|---|---|
| Baseline | B12 merged |
| Purpose | Flip the red gates and record C2 with evidence |
| Dependencies | B12 |
| Scope | Remove the strict expected-failure markers from the `DockerBackend` cases of B01; run G1, G3, G4, G5, G6 on a provisioned host; record the host fingerprint and results in the reconciliation document; mark C2 PASS for `DockerBackend`; update the matrix; separately, a `KNOWN_ISSUES.md` PR from `main` closing DEBT-039 and, for `DockerBackend`, DEBT-040 |
| Out of scope | `_CAPS`; `NamespaceBackend` |
| Files | the B01 suite, the reconciliation document; `KNOWN_ISSUES.md` by its own PR |
| Requirements | A gate is recorded as passed only if the run was on the final code of the merged state |
| Tests | TC-01 to TC-13, TC-20, TC-21, TC-14 (TC-15 skipped with its reason on a host without IPv6) |
| Acceptance | All named tests pass; the reconciliation §18 matrix shows C2 PASS for `DockerBackend` with the evidence block; DEBT-040 stays open for `NamespaceBackend` unless G7 has passed |
| Invariants | INV-1 to INV-3, INV-5 |
| Risks | Declaring C2 on evidence from a stale build; hence the "final code" requirement |
| Evidence | The evidence block |
| Resulting state | C2 PASS (Docker); `NETWORK_ALLOWLIST` not yet re-claimed |
| Eligible next | B21 |

#### B14. IPv6 equivalence proof (optional; needs an IPv6-capable host)

| Item | Content |
|---|---|
| Baseline | B13 |
| Purpose | Replace the "refuse" branch of section 9 with a proven "equivalent isolation" branch |
| Dependencies | B13; an IPv6-capable host |
| Scope | An `ip6tables` equivalent of the section 4.1 rules; TC-15 on that host; provisioning artifact extended |
| Out of scope | Anything on a host without IPv6 |
| Files | provisioning artifact, `_sandbox_network.py`, tests |
| Requirements | A `::`-bound host listener is unreachable; the guard moves from refuse to supported only on hosts where the equivalent rules are verified by a canary |
| Tests | TC-15 |
| Acceptance | TC-15 passes on an IPv6-capable host and its evidence is recorded; elsewhere the refuse behavior is unchanged |
| Invariants | INV-8 |
| Risks | Not testable on the development host; stays UNVERIFIED until a host exists |
| Evidence | Host fingerprint and output |
| Resulting state | IPv6 isolation either proven for stated hosts or still refused |
| Eligible next | none required |

### Phase P3: capability earning

#### B21. Re-claim `NETWORK_ALLOWLIST` (A1)

| Item | Content |
|---|---|
| Baseline | B02 and B13 merged |
| Purpose | Restore the claim, and with it close A1 |
| Dependencies | B02, B13 |
| Scope | `NETWORK_ALLOWLIST` added to `DockerBackend._CAPS` (9 of 12) in the same change as the A1 evidence; TC-18 and TC-19; the matrix updated: C2 PASS, A1 PASS |
| Out of scope | `admission.py`, `contracts.py`; `NamespaceBackend`; any other capability |
| Files | `docker_backend.py` (`_CAPS`), tests, the reconciliation document |
| Requirements | Both claims present; the admission-layer test passes; the integration test shows an admitted request reaching the proxy with `200` for an allowed host and `403` for a disallowed one |
| Tests | TC-18, TC-19 |
| Acceptance | Tests pass on a provisioned host; `_CAPS` is 9 of 12; the paired-claim invariant holds; the full suite passes |
| Invariants | INV-5 |
| Risks | Claiming without the provisioned host: the docstring and the capability's documentation must state that the claim holds only on a provisioned host and that the canary refuses otherwise (the claim is about the backend under its documented deployment, and `check_admission()` cannot know the host state, so the canary is what keeps the claim honest at create time) |
| Evidence | Test run; matrix diff |
| Resulting state | A1 PASS, C2 PASS, `NETWORK_ALLOWLIST` claimed |
| Eligible next | B22 |

#### B22. Completion-status reconciliation

| Item | Content |
|---|---|
| Baseline | B21 merged |
| Purpose | Record what changed and what did not |
| Dependencies | B21 |
| Scope | A reconciliation subsection stating the new matrix; `sandbox-fabric` remains explicitly incomplete because A9, C3 and D9 are open; the `KNOWN_ISSUES.md` updates for DEBT-021 by its own PR; a refreshed `handoff.md` |
| Out of scope | Reopening the Stage 5 decision for any other item |
| Files | the reconciliation document, `handoff.md`, `KNOWN_ISSUES.md` (own PR) |
| Requirements | Facts only; no item is called complete without its evidence |
| Tests | n/a |
| Acceptance | The tally sums to 28 and matches the matrix; the incomplete items are named with their blockers |
| Invariants | No silent change of a decision |
| Risks | Overstating completion |
| Evidence | The matrix, the refs |
| Resulting state | An accurate record |
| Eligible next | none in this chain |

### Phase P4: `NamespaceBackend` (after DG-2)

#### B30. `NamespaceBackend` remediation or claim withdrawal

| Item | Content |
|---|---|
| Baseline | B04 merged; DG-2 decided |
| Purpose | Bring `NamespaceBackend` under the isolation contract or stop advertising what is not proven |
| Dependencies | B04, DG-2; for remediation a provisioned host and a prefix-keyed rule design for the host veth (by analogy; NOT TESTED) |
| Scope | Per DG-2: (a) rename the host veth to a dedicated prefix, extend provisioning, add the canary and the fail-closed gate, flip the strict markers; or (b) remove `NETWORK_ALLOWLIST` from its `_CAPS`, reopen DEBT-023 in `KNOWN_ISSUES.md`, adjust its tests; or (c) record the exception |
| Out of scope | `DockerBackend` |
| Files | `core/sandbox/backends/namespace_backend.py`, `test_allowed_hosts.py` and the shared suite; `KNOWN_ISSUES.md` (own PR) |
| Requirements | The same S1 to S7 apply to any firewall use here; no behavior change on `main` without the DG-2 ruling |
| Tests | TC-17 passing (remediation) or the claim/evidence coupling (withdrawal) |
| Acceptance | The advertised and contract-verified statuses agree for `NamespaceBackend`, or the divergence is recorded as an accepted exception |
| Invariants | INV-5 |
| Risks | A behavior change on `main`; the existing DEBT-023 tests and users of the claim |
| Evidence | Test run; the decision record |
| Resulting state | DEBT-040 closed for both backends, or its remaining scope recorded |
| Eligible next | none in this chain |

## 17. Requirements traceability

| Requirement | Mechanism | Test | Gate | Batch |
|---|---|---|---|---|
| No sibling-proxy reach (DEBT-039) | Per-sandbox networks plus the destination-matched rule | TC-03, TC-04 | G1 | B11, B12, B13 |
| No host-local reach (F6) | Catch-all drop on the sandbox interface | TC-01, TC-02 | G3 | B10, B13 |
| Policy ownership (B3) | Constant rule text with no destination | TC-05 | G5 | B10 |
| Fail closed | Canary and topology validation | TC-06 to TC-08 | G4 | B11, B12 |
| Least privilege (D2) | Provisioning outside the controller | TC-20, TC-21 | G4, G5 | B10, B12 |
| Lifecycle (D10/D11) | Ordered acquisition, reaper, per-handle lock, limiter | TC-09 to TC-13 | G4 | B11 |
| Capacity 29 (D5) | Counting limiter, capacity probe | TC-13 | G4 | B03, B11 |
| IPv6 (D5) | Detect, refuse; proof later | TC-14, TC-15 | G6 | B03, B14 |
| `NET_NAMESPACE` | Direct netns test | TC-16 | G2 | B02 |
| C2 PASS | G1, G3, G4, G5, G6 | as above | | B13 |
| `NETWORK_ALLOWLIST` and A1 | Restore claims with evidence | TC-18, TC-19 | G8 | B21 |
| `NamespaceBackend` contract (D4) | Shared suite, then DG-2 | TC-17 | G7 | B04, B30 |
| H2 evaluated (D3) | Comparative study | experiments | DG-1 | B05 |

## 18. Risk register

| ID | Risk | Likelihood / effect | Mitigation | Residual |
|---|---|---|---|---|
| R1 | A host tool flushes or reorders `INPUT` after provisioning | Unknown / high | Canary per create, timer, refusal on failure; rules inserted at position 1; documented | A window between canary runs |
| R2 | Reboot or firewall-manager reload drops the rules | Not tested / high | Provisioning documents persistence for the host's manager; the canary refuses when absent | Unverified on managers other than none |
| R3 | The canary image lacks a connect tool, or the canary is too permissive | Medium / high | Pinned provisioned image; TC-07 controls; mutation check | OD-3 |
| R4 | iptables legacy variant behaves differently | Not tested / medium | Provisioning verified per variant; recorded | Legacy untested |
| R5 | IPv6 reachability on IPv6-enabled hosts | Not testable here / high | Refuse by default (section 9) | UNVERIFIED until B14 |
| R6 | The 29-network constant disagrees with the real pool capacity | Known (host-dependent) / medium | Capacity probe; lower of the two | Documented |
| R7 | D10/D11 regressions from touching create/destroy | Medium / high | Existing injection and race tests retained; mutation checks; separate batch (B11) | Reviewed per batch |
| R8 | A claim added without evidence | Low / high | Same-change rule; TC-19 | None if enforced |
| R9 | Gates cannot run in CI | Certain / medium | Host-evidenced gates with fingerprints; strict markers, not the manifest | Reviewer discipline |
| R10 | `NamespaceBackend` behavior change on `main` | Medium / medium | DG-2 ruling before B30 | None until decided |
| R11 | A fixed-port collision with a host service | Low / medium | Fails closed (F21); documented | Deployment concern |
| R12 | The static rule has other bypasses not yet tested (fragments, other protocols, ARP) | Unknown / high | Catch-all drop covers protocols; an adversarial pass is part of B13; F28 shows a first design can look right and be wrong | Open until B13 |

## 19. Decisions: rulings of October 4 2026, and what is still open

| ID | Ruling | Applied in |
|---|---|---|
| OD-1 | **YES, with one editorial correction before ACCEPTED.** T-FW is ratified as the proposed baseline; DG-1 stays the final mechanism-selection gate. The claim that port 3128 is "less common" is removed; 3128 stays because it is already tested | Status line; section 4.1 |
| OD-2 | **YES, the sequencing is correct.** B05 completes before DG-1; B04 completes before DG-2. This specification pre-decides neither gate | Section 16, dependency table |
| OD-3 | **YES.** A dedicated, minimal, immutable-digest-pinned, pre-provisioned canary image with a deterministic TCP-connect primitive; not pulled during `create()`; positive and negative controls on every create in v1; the digest is fixed in B12 after repository and host verification | Section 7.4; B12 |
| OD-4 | **PORT = 3128.** Provisioning artifact `scripts/sandbox/provision_network_isolation.sh` with install, verify and remove modes. The shared constant is the single source of truth | Sections 4.1, 7.6; B10 |
| OD-5 | **YES.** `MAX_CONCURRENT_SANDBOX_NETWORKS = 29` is the supported constant, validated by the capacity probe; the effective limit is `min(29, probe result)`; raising it is out of scope and needs a new ruling | Section 8; B03 |
| OD-6 | **YES.** The reconciliation document is the canonical evidence record. Each gated run records: final commit SHA, branch and base, host fingerprint, kernel, Docker and iptables variant, provisioning state, exact command, result, timestamp, cleanup and baseline check, and any artifact or hash needed to reproduce. Strict expected-failure markers remain the mechanism for red states; the known-failures manifest is never used to hide a gate | Section 14; B01 |
| OD-7 | **RATIFIED.** `contracts.py`, `admission.py`, `_net_proxy.py` and the frozen documents stay untouched. Allowed: the listed backend and network module, sandbox tests, the provisioning artifact, architecture documents, and `KNOWN_ISSUES.md` only through its own PR. Workstream name: `sandbox-network-isolation`. Anything outside needs a fresh ruling | Section 15 |
| OD-8 | **Not on the critical path.** DEBT-041 is defense in depth, scheduled after B13 and B21. The proof deliberately tests with `NET_RAW` present so that F28 stays a meaningful regression; the test fixture grants `NET_RAW` explicitly | Section 4.3; TC-04; dependency table |
| OD-9 | **Out of scope for B10.** ufw, firewalld, manager reloads and reboot persistence are documented as unverified or unsupported for v1; B10 verifies the exact firewall backend and variant it tested; the canary is the fail-closed detector; a manager-integration design is a separate workstream | Section 7.6; B10 |

**One technical point recorded with the rulings.** The F28 correction confirms the central principle: the firewall rule constrains the transport path and does not duplicate proxy policy. The mandatory `--dst-type LOCAL --limit-iface-in` match is part of the security invariant, not an implementation detail, and TC-04 must keep actively attempting the forged Ethernet path with `NET_RAW` granted by its fixture.

**Still open (user decisions, not pre-decided here):**
- **B00's merge decisions** for PRs #48, #49 and #50, and the choice of the implementation base branch (section 16, B00). Each merge needs its own explicit instruction.
- **DG-1** (after B01 and B05) and **DG-2** (after B04).

## 20. What this specification does not claim

- That any design here has been built, or that T-FW is the final choice (DG-1).
- That IPv6 isolation works (UNVERIFIED).
- That the legacy iptables variant, a firewall-manager reload or a reboot preserves the rules (not tested).
- That a forged *session* (as opposed to the first packets, F16 and F28) is possible or impossible.
- That `NamespaceBackend`'s sibling reach exists (not yet evaluated); only its F6 reach was observed, once.
- That `sandbox-fabric` is complete: A9, C3 and D9 remain open whatever happens here.
