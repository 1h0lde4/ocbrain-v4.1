# Sandbox Fabric — DockerBackend Implementation Prompt

**Status:** Ready to fire, in a session with an actual Docker-enabled host. Not usable here — `docker`/`runc`/`podman` confirmed absent throughout this branch's history.
**Date:** September 17, 2026
**Derived from:** `sandbox-fabric-v2-implementation-readiness-audit.md` (commit `74b7db7`) §§3–5, and `sandbox-fabric-docker-backend-security-comparison.md` §4. Read both before starting — this prompt summarizes their conclusions for action; it does not restate their reasoning.
**Does not require:** Track A (CTX-AUTH-001b / Kernel freeze) to be resolved first. These are independent — nothing here touches Kernel/Verification/C-MoE territory, matching every prior pass on this branch.

---

> **Prerequisite reading, in order:** `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`, `docs/architecture/sandbox-fabric-docker-backend-security-comparison.md`, `docs/architecture/sandbox-fabric-v2-implementation-readiness-audit.md`. Do not re-derive what they already answered.
>
> **Context:** `core/sandbox/` (1,528 lines, `NamespaceBackend` + supporting modules, 59 tests) implements the `SandboxBackend` interface with namespaces/cgroups/seccomp/chroot. This session adds a second backend, `DockerBackend`, on the same interface, using an actual Docker daemon. The two backends coexist — nothing about landing this one changes what `NamespaceBackend` does or how it's tested.
>
> **The one architectural rule that overrides any convenience shortcut:** `DockerBackend` consumes the existing sandbox contracts and `core/sandbox/backends/_net_proxy.py`. It does not become a second policy or network architecture. Concretely: `SandboxPolicy`/`SandboxRequest`/`SandboxResult`/`AdmissionGate` are not reinvented or paralleled for Docker's own idioms, and `allowed_hosts` enforcement is `_net_proxy.py` called from a Docker network context, not a new proxy, not Docker's own network-policy primitives standing in for it. If implementing something Docker-idiomatic would require a second policy surface, stop and treat that as a design question to raise, not a decision to make silently inside this session.

---

## Phase 0 — Host inventory (do this before writing any `DockerBackend` code)

Mirrors how `NamespaceBackend` itself started: verify the primitives are actually present before designing around them, the same discipline throughout this branch's history.

1. `docker version`, `docker info` — confirm a real daemon is reachable, not just the CLI installed.
2. **Docker version, checked against the CVE-2026-31431 fix date (moby/profiles#20, merged April 30 2026).** An older pinned version predates the `AF_ALG`/`AF_VSOCK` seccomp fix entirely — record the exact version found.
3. `docker info | grep -i userns` (or equivalent) — is `--userns-remap` configured on this daemon? Comparison doc §2: off by default. Record actual state, don't assume.
4. Is `--security-opt=no-new-privileges` the daemon's default, or opt-in per-run? Comparison doc §2: opt-in by default. Record actual state.
5. `aa-status` / `getenforce` (or equivalent) — is AppArmor or SELinux active on this host at all? This determines whether Phase 4's gate can even be attempted.
6. Confirm `iproute2` (`ip netns`, `ip link`) is present on this host if Docker-network + `_net_proxy.py` integration (Phase 5) is to be attempted — same dependency `NamespaceBackend`'s `allowed_hosts` path already needs.

Record all six findings plainly, including negative ones, before proceeding. A negative finding (e.g. "AppArmor not active") is not a blocker for Phase 0 — it changes what Phase 4 can conclude.

## Phase 1 — Contracts (no new design, implementation only)

Per audit §3, verbatim:

1. `class DockerBackend(SandboxBackend)` in `core/sandbox/backends/docker_backend.py` — exactly `capabilities`, `create`, `run`, `cancel`, `destroy`, `inspect`. No additional public surface.
2. `RuntimeCapabilities(backend_name="docker", supported=frozenset({...}))` — populated **only** from what Phase 0–5 actually confirm, not from what Docker is assumed to provide. Start this set empty; add each `SandboxCapability` value only after its corresponding gate below passes.
3. `SandboxRequest.command` stays argv-only through the translation into `docker run <image> <command...>` (or the SDK equivalent) — no shell-string path introduced anywhere in that translation.
4. Events publish through the existing `EventStream` via `core/sandbox/events.py`, unchanged.
5. `ArtifactManifest` (path/hash/size triples) is the return shape for collected artifacts — not raw content, matching the correction already on record (audit §0) against an unrelated document's stale claim.
6. New `SandboxCapability` enum values, if genuinely needed, are additive only in `core/sandbox/contracts.py` — no renaming or removing existing values.

## Phase 2 — Isolation gate: user-namespace remapping + `no_new_privs`

Uncertifiable claim #1 (comparison §4, audit §4). Do not declare `USER_NAMESPACE` or `NO_NEW_PRIVS` in `capabilities` until:

- `--userns-remap` is explicitly configured for the daemon or run, and adversarially confirmed — attempt something that requires genuine host root from inside the container, confirm it fails, the same pattern `NamespaceBackend`'s mapped-root was verified with.
- `--security-opt=no-new-privileges` is explicitly set per-run (not assumed from daemon defaults), and confirmed via the container's own `/proc/self/status` `NoNewPrivs` field or equivalent.

If either cannot be configured on the available host, `DockerBackend.capabilities` must **not** claim it — `AdmissionGate` relies on this being honest, not aspirational.

## Phase 3 — cgroup and filesystem gates

Uncertifiable claims #2–3. Re-run, don't assume:

- The exact adversarial pattern already proven for `NamespaceBackend`: an allocation sized well past a configured `--memory` limit must be caught and reported analogously to `RESOURCE_EXCEEDED`; a fork-bomb-style payload must be stopped by `--pids-limit`.
- Symlink-escape and path-traversal attempts against the container's actual OverlayFS-backed filesystem — the specific tests from `test_namespace_backend.py` are the template, not something to import unmodified (the filesystem mechanism is different; the adversarial *intent* transfers, the mechanism doesn't).

Only after both pass does `capabilities` gain `CGROUP_MEMORY`, `CGROUP_PIDS`, `FILESYSTEM_JAIL`.

## Phase 4 — Seccomp gate: `AF_ALG`/`AF_VSOCK` and the `socketcall` question

Uncertifiable claims #4–5. **This is the phase most likely to end in an honest "not closed" rather than a pass, and that is an acceptable outcome — a silent pass is not.**

1. Confirm the Docker version found in Phase 0 post-dates the `AF_ALG`/`AF_VSOCK` fix. If it does, verify directly (attempt `socket(AF_ALG, ...)` from inside a container with the default seccomp profile) rather than trusting the version number alone.
2. **The `socketcall` question, specifically:** if Phase 0 found AppArmor or SELinux active and properly enforcing, verify the LSM rule (`deny network alg` / `alg_socket`) is actually applied to containers on this host — this is Docker's *real*, current mitigation, not the seccomp-only one this branch's own `NamespaceBackend` relies on.
3. If AppArmor/SELinux is **not** active on this host (Phase 0 found this on the build environment used throughout this branch — very possibly true here too): compile and run the same int-`0x80` probe used to verify `NamespaceBackend` (`tests/core/sandbox/test_seccomp.py`'s `_compile_socketcall_probe` pattern) against a real container, with the container's own seccomp profile active. Record the actual result. Do not extrapolate from `NamespaceBackend`'s own SIGSYS finding — that result was specific to a filter with no explicit multi-architecture declaration; Docker's default profile *does* declare `SCMP_ARCH_X86_64`/`X86`/`X32` explicitly, so the mechanism protecting `NamespaceBackend` does not obviously transfer.
4. If this gate cannot be closed on the available host, `capabilities` must **not** claim `SECCOMP` implies protection against this specific bypass — document the gap in the same style as reconciliation §9's own honest caveat, in a new addendum to that document, not silently.

## Phase 5 — Network gate: `allowed_hosts` via `_net_proxy.py` reuse

Uncertifiable claim #6. Per the architectural rule above: this is integration, not reimplementation.

1. Put the container on an isolated Docker network with no default route out (mirroring `NamespaceBackend`'s no-default-route veth setup).
2. Start (or reuse a running) `core.sandbox.backends._net_proxy.AllowlistProxy` instance reachable from that network.
3. Set `HTTP_PROXY`/`HTTPS_PROXY` (both cases) via `-e` at container start, pointing at that proxy.
4. Adapt `test_allowed_hosts.py`'s actual test pattern — a real fetch to an allowed host succeeds through the chain; the same fetch with a different `allowed_hosts` entry is rejected; the deny-all path (no `allowed_hosts`) is confirmed to have no route out at all, same as `NamespaceBackend`'s.

Only after this passes does `capabilities` gain `NETWORK_ALLOWLIST`; only after the deny-all check separately passes does it gain `NETWORK_DENY_DEFAULT`.

## Phase 6 — Test suite

`tests/core/sandbox/test_docker_backend.py`, following the established skip-cleanly pattern (`_namespaces_available()` in `test_namespace_backend.py`, the `gcc` check in `test_seccomp.py`): a `_docker_available()` guard that skips the whole file on a host without a reachable daemon, never a hard failure. Coverage should mirror `NamespaceBackend`'s own adversarial suite one-for-one where the mechanism allows (echo Hello, illegal path, resource limits, cancellation, artifact hashing) and explicitly diverge where Phase 3–5 found real mechanism differences.

## Definition of Done for this phase

Not "all six gates pass" — that may not be achievable on every host, and Phase 4 in particular may legitimately end open. Done means:

- Phase 0's inventory is recorded, including negative findings.
- `DockerBackend` implements the interface and passes Phase 6's suite on whatever host was actually used.
- `capabilities` reflects exactly and only what Phases 2–5 individually confirmed — no capability claimed on the strength of "Docker generally does this."
- Every gate that did **not** close is documented as an open, disclosed gap — a short addendum to the reconciliation doc, in the same voice as its existing §§7–9 (state what was found, what was verified, what wasn't, and why) — not left implicit, not silently downgraded to a passing claim.
- No file outside `core/sandbox/backends/docker_backend.py`, its own small helpers, `tests/core/sandbox/test_docker_backend.py`, `core/sandbox/contracts.py`'s enum (additive only), and the reconciliation addendum was touched, per audit §5's scope boundary.
