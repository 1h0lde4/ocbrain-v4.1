# Sandbox Fabric Architecture v2 — Implementation-Readiness Audit

**Status:** Audit complete. Answers all five questions this was scoped to answer; implements nothing.
**Date:** September 16, 2026
**Method:** Fresh pull of `main` and `sandbox-fabric`, both re-verified rather than assumed current given how much concurrent activity has landed on this repository throughout this branch's history. Every claim about existing code cites an exact file/line/commit; every claim about Docker is marked as documented-not-verified, matching `sandbox-fabric-docker-backend-security-comparison.md`'s own convention. Section 0 is the post-DEBT-020 Kernel reconciliation this audit was explicitly sequenced behind.

---

## 0. Post-DEBT-020 Kernel Reconciliation

**DEBT-020 is resolved, decisively, not tentatively.** `d1180d4` (Sept 14, 2026, "Record DEBT-020 parallel-branch decision: main canonical, branch superseded") records Moncif's explicit ruling: main's already-merged implementation (`constraint_violations` / `Orchestrator.handle()`) stays canonical; a competing branch (`fix/debt-020-completion-semantics-sep2026`) that redesigned completion semantics differently is superseded, not reconciled or merged; `CompletionStatus`/`has_checkable_value()` from that branch are explicitly rejected — adopting either would need "a concrete architectural need and a fresh implementation against current main," not portage of stale, unaware-of-the-fix work. This is a real decision, not a default — worth stating plainly since it's the kind of thing a future session could otherwise re-litigate.

**The Kernel v1.0 freeze is not yet open, and the reason has moved.** It no longer hinges on DEBT-020. As of the latest pull (`main` HEAD `c67187a`), two sources give a near-identical but not word-for-word-identical account of what remains:
- `d1180d4` itself: "the remaining freeze-relevant open question narrows to **CTX-AUTH-001b** specifically — not DEBT-020, not DEBT-024/DEBT-025 (SupervisorWorker/API-auth stay separately tracked, non-blocking)."
- `docs/architecture/WORKSPACE_ARCHITECTURE.md` §B.3 ("REPO FACT," dated after `d1180d4`): "Near freeze. Remaining blockers: **CTX-AUTH-001b**: Open (001a closed per `aae1310`); **DEBT-024**: Retry semantics; **DEBT-025**: API authentication."

Both agree CTX-AUTH-001b is the live blocker (confirmed independently: `aae1310`, "Merge PR #17: reclassify CTX-AUTH-001 as partially closed," landed after `d1180d4` and is consistent with it). They disagree, in emphasis rather than fact, on whether DEBT-024/025 are "non-blocking" or "remaining blockers" — that's noted here rather than silently resolved one way, since it isn't this audit's decision to make and the discrepancy is small enough that restating it precisely is more honest than picking a side.

**Two real security fixes landed in the same window, unrelated to sandbox-fabric but relevant context for anyone doing freeze work:** `977ebcc` (RCE-001 — `POST /modules/new` permitted arbitrary in-process code execution) and `e41a820` (CTX-EXPORT-001 — a path-traversal-to-arbitrary-deletion primitive in `import_module()`), both authored by a separate "Claude (Freeze-Reconciliation)" session. RCE-001 in particular is worth naming here specifically because it's a concrete, real-world illustration of exactly the class of problem sandbox-fabric exists to prevent — in a different subsystem, already fixed, not something this audit needs to act on.

**A large, independent architecture initiative landed on `main` today (Sept 16), directly overlapping this audit's subject matter, and needs to be accounted for before answering the five questions below — not treated as background noise.** Four commits (`69375c9`, `b97188c`, `c67187a`), authored directly by Moncif via GitHub's upload UI, add:
- `core/workspace/domain.py` (554 lines): a domain model for `Project`, `Session`, `Discussion`, `Task`, `File`, `Artifact`, `ArtifactLineage`, `ComputationalLevel`, `ResourceBudget`, `ResourcePolicy`. **Zero consumers anywhere in the codebase** (checked directly: no file imports from `core.workspace`) — pure schema, exactly the stage `core/sandbox/contracts.py` was at before `backend.py` and `namespace_backend.py` gave it callers.
- `docs/architecture/WORKSPACE_ARCHITECTURE.md` (1093 lines), `ocbrain_architecture_corrections.md` (651 lines), `ocbrain_ux_architecture_report.md` (2114 lines): a broader UX/architecture proposal.

These documents were fact-checked against the real repository carefully in most places — `WORKSPACE_ARCHITECTURE.md` §G.3 correctly describes `SandboxPolicy`/`SandboxRequest`'s actual fields, down to citing `core/sandbox/contracts.py` line numbers accurately. But not everywhere: `ocbrain_ux_architecture_report.md` §G.2, marked with the document's own lower-confidence tag "(PCF)" rather than its "(REPO FACT)" tag, states `SandboxResult.artifacts` is `Dict[str, bytes]`. It is not — the actual, shipped type is `ArtifactManifest`, a tuple of `(relative_path, sha256_hex, size_bytes)` triples (`core/sandbox/contracts.py:169-181`); no file *content* is embedded in the result at all, deliberately. **This correction is recorded here, not silently fixed in that document** — it isn't this audit's document to edit, and the source document's own confidence-tagging already flagged it as less certain than its other claims.

The conceptual relationship worth carrying forward — not resolving now, since nothing wires into either side yet — is between the new domain model's `Artifact`/`ArtifactLineage` (a versioned, user-facing, first-class entity with real content, explicitly framed as "outputs" distinct from `File` "inputs") and `core/sandbox/contracts.py`'s `ArtifactManifest` (a narrow, per-execution integrity record: hashes, not content, scoped to one sandbox run). These are not the same thing and neither needs to change today, but a plausible future shape is visible already: a sandboxed execution's `ArtifactManifest` becoming an input to constructing a workspace-level `Artifact`, with `ArtifactLineage.source_execution_id` pointing at the `SandboxHandle` that produced it. §5 below treats this as a boundary condition on what an implementation session may touch, not something to build now.

---

## 1. What Sandbox functionality already exists in OCBrain after DEBT-020?

**All of it lives in `core/sandbox/`, and nothing outside that package implements competing or overlapping sandbox functionality.** Verified directly against current `main` (which has Phase 1 + DEBT-022 merged — `2bb0498` — but not yet DEBT-023 or the CVE-2026-31431/socketcall/Docker-comparison work, which remain on `sandbox-fabric` only) and current `sandbox-fabric`:

| File | Lines | Contents |
|---|---|---|
| `core/sandbox/contracts.py` | 231 | `SandboxPolicy`, `SandboxRequest`, `SandboxHandle`, `RuntimeCapabilities`, `SandboxCapability`, `ArtifactManifest`, `SandboxResult`, `SandboxEvent`/`SandboxEventType`, `TerminationReason`, `SandboxState` |
| `core/sandbox/backend.py` | 67 | `SandboxBackend` ABC — `capabilities`, `create`, `run`, `cancel`, `destroy`, `inspect` |
| `core/sandbox/admission.py` | 54 | `AdmissionGate.check_admission()` — deny-by-default, capability-gated |
| `core/sandbox/events.py` | 34 | Thin `SandboxEvent → EventStream` adapter |
| `core/sandbox/backends/stub_backend.py` | 88 | Zero-capability interface-test stub |
| `core/sandbox/backends/namespace_backend.py` | 499 | The real backend: namespaces, cgroups v1, seccomp, chroot, veth+proxy allowlisting |
| `core/sandbox/backends/_ns_init.py` | 102 | In-namespace init: bind-mount, chroot, no_new_privs, seccomp, exec |
| `core/sandbox/backends/_seccomp.py` | 251 | Denylist + argument-conditioned socket-family filtering, ctypes → libseccomp |
| `core/sandbox/backends/_net_proxy.py` | 195 | Allowlist-enforcing HTTP(S) forward proxy |
| **Total** | **1,528** | |

`NamespaceBackend`'s declared capabilities (`RuntimeCapabilities.supported`, read directly, not paraphrased): `cgroup_memory`, `cgroup_pids`, `filesystem_jail`, `mount_namespace`, `net_namespace`, `network_allowlist`, `network_deny_default`, `no_new_privs`, `pid_namespace`, `seccomp`, `user_namespace`, `uts_namespace` — twelve. `StubBackend` declares zero, by design, so `AdmissionGate` structurally cannot mistake it for something it isn't.

**Test coverage: 59 tests across seven files, all under `tests/core/sandbox/`**, collected fresh: `test_contracts.py`, `test_admission.py`, `test_stub_backend.py`, `test_events.py`, `test_namespace_backend.py`, `test_seccomp.py`, `test_net_proxy.py`, `test_allowed_hosts.py`. No other test directory in the repository references `core.sandbox`.

**What DEBT-020's resolution itself contributed to sandbox functionality: nothing directly.** It's a workflow-orchestration/completion-semantics fix (`Orchestrator.handle()`), architecturally unrelated to isolation/execution. It matters to this audit only as fresh evidence that main moves fast and needs re-verifying before any dependent work starts — which is exactly why §0 exists and why the workspace-architecture discovery above happened *during* this audit rather than being missed.

**What else exists that touches "sandbox" as a word, not as this subsystem:** `modules/system_ctrl/module.py`'s `SAFE_ROOT` path-jail (pre-existing, reconciled against in `sandbox-execution-fabric-existing-code-reconciliation.md` §2 — same-process jail, not this subsystem, not re-litigated here) and the new `core/workspace/domain.py`'s references to sandbox concepts in prose/docstrings only, no code.

---

## 2. Which parts of the Sandbox study are implemented, partially implemented, or purely planned?

Against `docs/research/sandbox-execution-fabric/deep-research-report.md`'s own section numbering (corrected, per its own commit history):

| Report section | Status | Evidence |
|---|---|---|
| §1–2 (literature review, comparison table) | Informational — not code | Informed design decisions (reconciliation §2's inventory table), not something to "implement" |
| §3 (host/repo inventory) | **Implemented** | `sandbox-execution-fabric-existing-code-reconciliation.md` §2 |
| §4 (contracts/schemas) | **Implemented**, renamed | `contracts.py` — `Sandbox*` prefix per reconciliation §3, not the report's own `Execution*` names |
| §5 (threat model & trust zones, isolation levels 0–4) | **Partially implemented** | The isolation *mechanisms* exist (namespaces/cgroups/seccomp/chroot); the report's own formal "levels 0–4" trust-zone framework was never built as an explicit contract — `NamespaceBackend` is one backend at one fixed isolation posture, not a selectable level |
| §6 (risk classification & policy composition, global ∧ task ∧ capability) | **Not implemented** | `AdmissionGate.check_admission()` is a flat pass/fail check, not a composition algebra across policy layers |
| §7 (GitHub capability admission chain — SBOM, Sigstore, `CapabilityManifest`) | **Purely planned** | No code anywhere; renamed "extension" not "capability" in the naming decisions (reconciliation §3) but not built under either name |
| §8 (secrets broker & identity isolation) | **Not implemented** | No secrets-broker code exists |
| §9 (global resource management — quotas/concurrency/backpressure across *multiple* sandboxes) | **Partially implemented** | Per-sandbox limits exist (cgroup memory/pids per handle); nothing caps concurrent sandbox count or does cross-sandbox backpressure |
| §10 (traceability, idempotency, TOCTOU) | **Partially implemented** | Traceability: yes, via `SandboxEvent`/`EventStream`. Idempotency: `request_id` is unique per request but there's no dedup-on-retry logic. TOCTOU: addressed incidentally where testing surfaced it (the cgroup-membership-before-exec ordering, the cgroup-vs-PID-namespace ambiguity) rather than as a named, systematic pass |
| §11 (snapshot/warm-pool, shared cache, inter-sandbox isolation, PTY, observability/audit/telemetry split, kill-plane) | **Purely planned** | Explicitly deferred in the report itself as "advanced options"; nothing here contradicts that |
| §12 (security invariants & adversarial tests) | **Implemented, extensively** | This *is* what `test_namespace_backend.py`/`test_seccomp.py`/`test_net_proxy.py`/`test_allowed_hosts.py` are |
| §13 (planning & Phase 1) | **Implemented** | Phase 1 shipped; the plan itself was revised in place once (naming decisions folded into §15's prompt) |
| §14 (acceptance criteria / DoD) | **Implemented for Phase 1's scope** | Every named success criterion (echo Hello, illegal path, network-deny, resource limits, cancellation) has a corresponding adversarial test; §14's criteria for *later* phases (Docker, seccomp allowlist maturity) are correspondingly not yet met |
| §15 (kickoff prompt for a parallel session) | **Superseded** | Revised in place, then never fired as a literal "parallel session" — Phase 1 through the CVE fixes were all built directly in the session that revised it, per explicit direction ("Start phase 1 here") |

**Net picture:** the parts of the report that describe *what Phase 1 needed to do* are done and adversarially verified. The parts describing a fuller, later-phase system (§6 policy composition, §7 GitHub admission, §8 secrets, §9 global quotas, §11 advanced options) remain exactly what the report itself scoped them as — later work, not gaps in what's shipped so far.

---

## 3. What exact contracts/boundaries must the eventual DockerBackend obey?

Not a design proposal — an enumeration of what already exists and binds any new backend, whether or not Docker changes the implementation underneath:

1. **The interface itself.** `class DockerBackend(SandboxBackend)` implementing exactly `capabilities` (property), `async create(request) -> SandboxHandle`, `async run(handle, request) -> SandboxResult`, `async cancel(handle) -> None`, `async destroy(handle) -> None`, `async inspect(handle) -> SandboxState` (`core/sandbox/backend.py`). No additional public methods; no signature deviation.
2. **Honest capability declaration.** `RuntimeCapabilities(backend_name="docker", supported=frozenset({...}))` must declare only what has actually been verified, not what Docker is assumed to provide. Per §2 of `sandbox-fabric-docker-backend-security-comparison.md`: user-namespace remapping and `no_new_privs` are off by default on Docker and must be explicitly configured and confirmed *before* being included in the declared set — a `DockerBackend` that declares `NO_NEW_PRIVS` because "Docker uses namespaces" without checking would violate this contract, not merely be imprecise.
3. **`AdmissionGate` is not to be special-cased.** `check_admission()` (`core/sandbox/admission.py`) must reject a `DockerBackend` the same way it already rejects `StubBackend` and would reject an under-capable backend — via the same `RuntimeCapabilities` check, not a Docker-specific carve-out.
4. **Naming stays inside the `Sandbox*`/`AdmissionGate`/"extension" decisions already recorded** (reconciliation §3) — a `DockerBackend` must not reintroduce `Execution*`-prefixed types, a `ValidationGate`, or "capability" for GitHub-sourced code, even by convenience or convention from Docker's own vocabulary (e.g. Docker's CLI calls things "capabilities" in the Linux-capabilities sense — that's a different, real meaning already, and a third, GitHub-sourced meaning must not collide with either).
5. **`SandboxRequest.command` stays argv-only.** The existing fail-closed `__post_init__` check (rejecting a bare `str`) applies identically; a `DockerBackend` translating this into `docker run <image> <command...>` must not reintroduce a shell-string path anywhere in that translation.
6. **Events publish through the existing `EventStream`,** via `core/sandbox/events.py`'s adapter, unchanged — not a second bus, not a Docker-specific event path.
7. **`allowed_hosts`, if supported, should reuse `_net_proxy.py` rather than duplicate it** — the proxy is backend-agnostic by construction; a `DockerBackend` pointing a container's `HTTP_PROXY`/`HTTPS_PROXY` at the same proxy process (on an isolated Docker network with no other route out) is the intended reuse path (comparison doc §2, §4 item 8), not a new proxy implementation.
8. **Artifact collection returns `ArtifactManifest`** (path/hash/size triples), not raw content — matching the correction recorded in §0 above and the existing contract's actual shape, regardless of what any other document currently says it is.

---

## 4. Which security claims require validation on a real Docker host and therefore cannot yet be certified?

Pulled forward, precisely, from `sandbox-fabric-docker-backend-security-comparison.md` §4 — restated here as *uncertifiable claims*, not a to-do list, since that's the distinction this question asked for:

1. **"`DockerBackend` provides equivalent isolation to `NamespaceBackend`."** Uncertifiable in full. Two dimensions are known to require explicit configuration Docker does not enable by default (`--userns-remap`, `--security-opt=no-new-privileges`) — this is not "needs testing," it's already known to be false unless configured, per Docker's own documentation. Certifiable only after that configuration is applied and independently confirmed the way `NamespaceBackend`'s mapped-root was (attempt something requiring real root; confirm failure).
2. **"cgroup limits behave the same way."** Uncertifiable — same primitive, different API surface, never tested end-to-end against real `docker run` flags. The exact adversarial tests already written (oversized allocation → `RESOURCE_EXCEEDED`, fork bomb → blocked) are the re-run needed; nothing here substitutes for actually running them.
3. **"The filesystem jail resists the same escapes."** Uncertifiable — OverlayFS + an image-derived rootfs is a different mechanism from chroot + host-bind-mounts. The symlink/traversal tests that pass here establish the *category* of test needed, not evidence about the differently-constructed filesystem.
4. **"`AF_ALG`/`AF_VSOCK` are blocked."** Likely true *if* a sufficiently recent Docker version is deployed (the fix is dated April 2026) — but uncertifiable without checking the specific version in use; an older pinned Docker predates the CVE fix entirely.
5. **"The `socketcall`/32-bit-compat bypass is closed."** The most important uncertifiable claim in this whole audit. Docker's own *current* mitigation is AppArmor/SELinux LSM hooks, not seccomp — and this repository's own equivalent fix (the `socketcall` denylist entry plus reliance on libseccomp's unrecognized-architecture kill) is Docker's *superseded* mitigation, empirically confirmed only for the namespace backend's own seccomp-only posture. Whether a Docker container without the same LSM configuration is actually protected is genuinely unknown and must not be assumed protected by analogy to either this repo's finding or Docker's fix.
6. **"`allowed_hosts` reuse via `_net_proxy.py` works unchanged against a container."** Uncertifiable until actually tried — the proxy's own logic doesn't care what's on the other end of the veth-equivalent link, but "doesn't care in principle" and "verified working" are different claims, and this audit only has grounds for the former.

None of the six above can be marked verified by this document. That is the point of the question.

---

## 5. What, exactly, should the eventual implementation session be allowed to modify?

Stated as boundaries, matching this project's diff-oriented development discipline (§18.4.8) and the Architecture Freeze Principle, informed by everything §0–4 surfaced:

**May create:**
- `core/sandbox/backends/docker_backend.py` and any small private helper modules alongside it, following the `_seccomp.py`/`_net_proxy.py` pattern (leading underscore, single responsibility).
- `tests/core/sandbox/test_docker_backend.py` and equivalents, following the existing skip-cleanly-without-the-dependency pattern already established (`_namespaces_available()`, the `gcc`-availability check in `test_seccomp.py`) — a `_docker_available()` equivalent, not a hard requirement that breaks the suite on a host without Docker.
- A short, focused addendum to `sandbox-execution-fabric-existing-code-reconciliation.md`, matching §§7–9's own pattern, once `DockerBackend` lands — not a rewrite of the existing sections.

**May modify, narrowly:**
- `core/sandbox/contracts.py`'s `SandboxCapability` enum, to add whatever new capability values `DockerBackend` needs to declare honestly (mirroring how `SECCOMP`, `UTS_NAMESPACE`, and `NETWORK_ALLOWLIST` were each added when, and only when, a real capability existed to declare) — additive only; existing values must not be renamed or removed.
- `core/sandbox/admission.py`, only if a genuinely new capability-gating rule is needed (mirroring the `allowed_hosts`-gated check) — not a rewrite of existing checks.

**Must NOT modify without a fresh, explicit reconciliation of its own, per the Architecture Freeze Principle:**
- `core/sandbox/backend.py`'s `SandboxBackend` ABC signatures — every existing backend and test depends on the current five-method shape.
- `namespace_backend.py`, `_seccomp.py`, `_net_proxy.py`, `_ns_init.py` — these are a different, already-verified backend; `DockerBackend` reusing `_net_proxy.py` (§3 item 7) means *calling* it, not editing it to fit Docker's needs in ways that could change `NamespaceBackend`'s own behavior.
- Anything under `core/runtime/`, `core/capabilities/`, `core/cognitive/`, `core/events/` — the naming-collision boundaries recorded in the reconciliation still apply; a Docker backend is exactly as unrelated to Verification/C-MoE/Kernel work as the namespace backend was.
- `core/workspace/domain.py` or its architecture docs — real, live work by Moncif directly, zero current relationship to sandbox execution beyond the narrow `ArtifactManifest`/`Artifact` conceptual note in §0, which is explicitly not something to act on now.

**Must NOT be assumed already resolved when the session starts:**
- The Kernel v1.0 freeze status (§0) — check `CURRENT_STATE.md` fresh; CTX-AUTH-001b's status will very plausibly have moved again by the time this work happens, exactly as it already has twice during this audit's own writing.
- Any of the six uncertifiable claims in §4 — each must be independently tested against whatever real Docker host the implementation session actually has, not marked done because this document described the mechanism.

**Out of scope entirely, restated from the comparison document rather than re-litigated:** AppArmor/SELinux LSM-hook work for the `socketcall` gap. That is real, disclosed, carried-forward risk — closing it (if it's ever closed) is its own focused pass, exactly like DEBT-022 and DEBT-023 each were, not something a `DockerBackend` implementation session should attempt as a side effect of getting Docker working.
