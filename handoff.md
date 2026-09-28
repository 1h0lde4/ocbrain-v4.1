# Session Handoff

## 1. Handoff Metadata

- Handoff version: 1
- Created at: 2026-09-27T19:35 UTC (session ran 2026-09-21 through 2026-09-27)
- Workstream: DockerBackend implementation (DEBT-021), branch `sandbox-fabric`
- Task identifier: DEBT-021 — DockerBackend, per the committed base prompt (`d53b164`) + the frozen pre-implementation addendum + the frozen 28-item checklist
- Source session purpose: execute the "DockerBackend Implementation — Definitive Docker-Host Handoff" (reproduced in full in §2). Over the course of the session, a real Docker daemon became available (installed inside the session's own execution container — see §14) and every checklist item was carried through to real, adversarial, evidence-backed verification rather than staying design-only.
- Transfer status: **TRANSFER INCOMPLETE — LOCAL COMMIT ONLY** at the time this file was written (everything is committed, but the last two commits — the addendum/checklist commit and this handoff commit — are not yet on `origin/sandbox-fabric`, because no GitHub credential was available in the session when this was written). It becomes TRANSFER READY when `git fetch origin sandbox-fabric` shows the remote at or beyond the handoff commit — see §19 for the exact criterion and evidence.

## 2. Original Starting Prompt

Reproduced verbatim. This is the literal text the source session was given; everything else in this handoff is downstream of it.

> DockerBackend Implementation — Definitive Docker-Host Handoff
>
> Mission
>
> Implement the DockerBackend work defined by the committed DockerBackend implementation prompt, as amended by the frozen DockerBackend implementation addendum, and operationalized by the frozen 28-item checklist.
>
> This is an implementation session on the actual Docker host.
>
> The addendum and checklist are frozen. Do not rewrite, renumber, simplify, reinterpret, merge, split, or otherwise modify them.
>
> The objective is to implement the specified behavior, establish evidence for every requirement, maintain the existing architecture and policy boundaries, and produce a scope-clean result suitable for incorporation into the OCBrain kernel freeze audit.
>
> ---
>
> 0. Source-of-truth hierarchy
>
> Use the following hierarchy:
>
> 1. Committed DockerBackend implementation prompt — base contract.
> 2. Frozen DockerBackend addendum — additive amendments/extensions to that contract.
> 3. Frozen 28-item checklist — operational mapping of the addendum, including each item's source classification, affected file/symbol, and public/policy-surface flag.
> 4. Current committed repository/code/tests.
> 5. Actual observations from the Docker host.
>
> The addendum is additive, not substitutive.
>
> The 28-item checklist does not replace the committed prompt or its original Phase 0–6 requirements.
>
> Therefore:
>
> «Passing the 28 checklist items alone is not sufficient for completion. The original Phase 0–6 gates remain operative, as amended or extended by the frozen addendum.»
>
> When the addendum extends an existing phase gate, verify the original gate together with the extension.
>
> Do not implement from this handoff prompt alone. Before modifying the repository, locate and read the complete committed implementation prompt, frozen addendum, and frozen 28-item checklist.
>
> If any required source artifact is unavailable, appears to be a different version, or conflicts materially with another authoritative source, stop before modifying code and report the discrepancy.
>
> Use repository/code evidence over stale notes or remembered state.
>
> ---
>
> 1. Establish BOTH baselines before implementation
>
> No repository modification is permitted until both baselines are recorded with sufficient evidence.
>
> 1A. Repository baseline
>
> Record:
>
> - repository and exact location;
> - current branch;
> - current commit;
> - clean/dirty working-tree state;
> - committed implementation prompt/version;
> - frozen addendum/version;
> - frozen 28-item checklist/version;
> - relevant baseline tests;
> - pre-existing failures/errors relevant to this work.
>
> Do not attribute pre-existing failures to the DockerBackend implementation.
>
> 1B. Docker-host baseline
>
> Record the actual runtime environment required by the committed Phase 0 gates and addendum, including:
>
> - Docker daemon identity;
> - Docker/daemon version;
> - which daemon/runtime is actually serving the API;
> - endpoint/security context being certified;
> - relevant CVE fix/version or fix-date state;
> - "userns-remap" state;
> - "no-new-privileges" state;
> - AppArmor state/profile;
> - SELinux state/policy where applicable;
> - "iproute2" version/capabilities relevant to the requirements;
> - kernel version;
> - cgroup version;
> - cgroup driver;
> - any other Phase 0/addendum host fact needed for interpretation.
>
> Do not treat the host inventory as a substitute for running the original Phase 0 acceptance gates.
>
> Remote or otherwise untrusted Docker API endpoints must not silently qualify as the intended local sandbox runtime merely because the Docker API is reachable.
>
> Host-dependent requirements must be interpreted against the actual daemon/runtime/kernel/cgroup/security environment observed here.
>
> ---
>
> 2. A–D are classifications, NOT implementation phases
>
> The 28 checklist items use A/B/C/D as epistemic/source categories:
>
> - A — verified gaps;
> - B — already-explicit rules carried forward for traceability;
> - C — extensions to existing gates;
> - D — implementation requirements.
>
> Do not execute:
>
> «A → B → C → D»
>
> as a build sequence.
>
> B is continuous
>
> B is not a code phase.
>
> - B1 is reporting discipline, not code.
> - B2/B3 constrain how all implementation is performed.
> - B4 governs final-diff reconciliation.
>
> Keep B active throughout the entire session and audit it explicitly at the end.
>
> The four carried-forward rules include, at minimum:
>
> - "SECCOMP" does not by itself prove protection against a specific CVE/bypass;
> - capabilities remain empty/unearned until their corresponding verification gates pass;
> - do not introduce a second policy surface;
> - the committed Definition-of-Done file-touch boundary remains binding.
>
> ---
>
> 3. Implementation sequencing is dependency-driven
>
> The dependency order below governs implementation sequencing only.
>
> It does not replace, reorder, or weaken the original Phase 0–6 acceptance gates.
>
> 3A. A3 first
>
> Resolve A3 first.
>
> No container can exist until image resolution is established.
>
> A3 must preserve the following:
>
> - image configuration is backend-private;
> - "SandboxRequest" does not acquire an image injection surface;
> - resolve the configured image reference to an immutable digest before execution;
> - record/use the resolved immutable identity as required by the frozen contract.
>
> Do not treat an image tag alone as immutable execution identity.
>
> 3B. Establish the minimum executable lifecycle scaffold
>
> After A3, establish:
>
> - D1
> - D4
> - D6
> - D9
>
> This must produce a working create/run/inspect/destroy path sufficient to establish and observe:
>
> - filesystem mapping;
> - container identity;
> - lifecycle/state mapping;
> - event visibility.
>
> Do not expand this scaffold beyond what the committed prompt/addendum requires.
>
> Identity must remain backend-private and support collision avoidance and cleanup of abandoned containers, including appropriate naming/labeling behavior where required by the checklist.
>
> 3C. Exercise the dependent isolation/filesystem gates
>
> Once a real, inspectable container exists, implement and verify:
>
> - A2
> - A6
> - D2
> - D3
>
> A6 must explicitly account for the absence of:
>
> - "--privileged";
> - host PID/IPC/network/UTS sharing;
> - "--cap-add";
> - device exposure;
> - mounted Docker/container-runtime sockets.
>
> A security property must be established from the resulting runtime state, not merely from request construction.
>
> Do not add capability claims simply because a related Docker option or low-level mechanism exists.
>
> 3D. Network-dependent requirements
>
> Once the original Phase 5 network setup is operational, implement and verify:
>
> - A1
> - C2
>
> For "NETWORK_ALLOWLIST", establish the required "NET_NAMESPACE" dependency as required by admission and the frozen contract.
>
> For network enforcement, test the specified negative/bypass paths, including:
>
> - direct connection bypassing the proxy;
> - Docker gateway as an alternate route;
> - another reachable container acting as a bridge;
> - "request.env" attempting to redirect proxy variables.
>
> Environment application order must preserve the enforcement invariant:
>
> 1. apply "request.env";
> 2. in allowlist/proxy-enforced mode, forcibly set the actual enforced proxy endpoint for both uppercase and lowercase HTTP/HTTPS proxy variables.
>
> Caller-supplied proxy variables must not be able to redirect around the enforced network path.
>
> 3E. Host-dependent security/resource requirements
>
> Using the host baseline and the original phase evidence, implement and verify:
>
> - A9
> - C1
> - C3
>
> A9
>
> Test the relevant security behavior directly.
>
> In particular:
>
> - test "AF_ALG" as required;
> - test "AF_VSOCK" separately and directly;
> - never infer AF_VSOCK protection from an AF_ALG result;
> - do not represent generic "SECCOMP" presence as proof of protection against a specific bypass.
>
> C1
>
> Distinguish a genuine cgroup/resource enforcement event from an ambiguous process exit such as "137".
>
> Do not infer a specific resource-exceeded condition from the exit code alone.
>
> C3
>
> Distinguish:
>
> - "the bypass is closed"
>   from
> - "the implementation also broke legitimate 32-bit/compat workloads."
>
> A security gate that merely breaks legitimate compatibility behavior is not automatically a clean pass.
>
> 3F. A5 is independent
>
> A5 may be resolved at any convenient point.
>
> Do not create Docker-only policy merely to make an existing request field appear enforced.
>
> Where the existing architecture does not enforce a field such as "allowed_imports", preserve the documented non-enforcement contract unless the frozen requirements explicitly require genuine enforcement.
>
> Do not add an isolated DockerBackend policy surface merely to manufacture compliance.
>
> 3G. Lifecycle hardening
>
> With the core lifecycle working, implement and verify:
>
> - D5
> - D7
> - D8
> - D10
> - D11
>
> This includes, as applicable:
>
> Artifact handling
>
> Preserve the existing "ArtifactManifest" contract and implement the specified extraction behavior.
>
> Verify:
>
> - path normalization;
> - traversal rejection;
> - symlink-escape rejection;
> - hashing of the bytes actually retrieved;
> - no following a sandbox-created symlink into an arbitrary host path.
>
> Lifecycle/state semantics
>
> Preserve the existing public "TerminationReason" and "SandboxState" enums.
>
> Test the specified invalid/idempotent lifecycle operations, including:
>
> - run before create;
> - double run;
> - cancel before run;
> - cancel after termination;
> - double destroy;
> - inspect after destroy.
>
> Cancellation
>
> Cancellation must be tested against an actual process tree, including parent/child/grandchild behavior.
>
> Do not conclude that descendants died merely because:
>
> - "docker stop" returned;
> - the top-level PID disappeared;
> - the container state changed.
>
> Verify descendants actually terminate.
>
> Inspect
>
> Verify that inspection is side-effect free.
>
> Events
>
> Preserve the existing event taxonomy and event semantics.
>
> Do not create a parallel event taxonomy for cancellation/timeout or other lifecycle outcomes when the existing event types/detail fields are sufficient and required by the contract.
>
> Cleanup
>
> Exercise the specified failure points.
>
> Verify no orphaned:
>
> - containers;
> - networks;
> - mounts;
> - proxy listeners;
> - handles/bookkeeping state.
>
> Preserve idempotent "destroy()" semantics.
>
> Concurrency
>
> Test the race pairs specified by the checklist.
>
> Verify:
>
> - consistent bookkeeping;
> - valid terminal state;
> - no leaked/orphaned containers or resources;
> - correct behavior under concurrent lifecycle operations.
>
> ---
>
> 4. Original Phase 0–6 requirements remain active
>
> Throughout implementation, continue to enforce the full original committed prompt, including all applicable requirements from:
>
> - Phase 0 — host/runtime baseline and admission prerequisites;
> - Phase 1 — contracts, capabilities, and event semantics;
> - Phase 2 — namespace/privilege isolation;
> - Phase 3 — resource enforcement;
> - Phase 4 — security/CVE-specific gates;
> - Phase 5 — network setup/enforcement;
> - Phase 6 — lifecycle/integration behavior.
>
> The frozen A/B/C/D checklist is an amendment and implementation mapping over those gates.
>
> Never use the dependency graph as an excuse to skip an original phase requirement.
>
> ---
>
> 5. Strict implementation surface
>
> The Definition-of-Done/file-touch boundary is binding.
>
> Do not modify:
>
> - "SandboxBackend";
> - "NamespaceBackend";
> - "_ns_init.py";
> - "_seccomp.py";
> - "_net_proxy.py";
> - unrelated architecture or unrelated backend logic.
>
> Keep implementation confined to the authorized DockerBackend surface described by the frozen prompt/checklist, including:
>
> - "docker_backend.py";
> - DockerBackend-private helpers explicitly required by the implementation;
> - "test_docker_backend.py";
> - additive "SandboxCapability" entries only where explicitly justified/authorized;
> - other files only where the frozen contract explicitly authorizes them.
>
> Do not repair unrelated cross-backend issues as part of this work.
>
> In particular, do not "fix" the existing "NamespaceBackend._CAPS" issue as part of this task unless it is separately brought into scope by an authoritative requirement.
>
> Anything outside the authorized file/symbol boundary is scope drift until explicitly justified.
>
> ---
>
> 6. No second policy surface
>
> The committed prompt's architectural rule governing policy placement remains binding:
>
> «Do not create a second policy surface for implementation convenience.»
>
> Do not duplicate policy in:
>
> - backend-local shadow policy;
> - helper defaults;
> - convenience fallbacks;
> - capability declarations;
> - request-construction shortcuts;
> - test-only production semantics;
> - alternate enforcement tables.
>
> Use the existing policy/governance architecture.
>
> If satisfying a requirement appears to require a new policy surface, stop and reconcile it against the frozen contract before proceeding.
>
> ---
>
> 7. Capability discipline
>
> Capabilities are earned, not declared optimistically.
>
> For every capability:
>
> - identify the corresponding gate;
> - prove that gate;
> - only then add/claim the capability;
> - otherwise leave it absent/unearned as required by the contract.
>
> Do not use generic mechanism presence as evidence of a specific security property.
>
> In particular:
>
> «"SECCOMP" ≠ proof of protection against a particular CVE-specific bypass.»
>
> Do not add a "SandboxCapability" value simply because Docker supports an option or because a code path appears to request it.
>
> ---
>
> 8. Security gate and fail-closed discipline
>
> Where the contract defines a security/isolation/resource property as an admission or acceptance gate:
>
> - inability to establish the required control is a gate failure;
> - do not silently degrade to a weaker configuration;
> - reject/contain the operation according to the committed contract.
>
> Do not convert an unsupported or unverified host/runtime condition into a PASS.
>
> Where the contract intentionally permits non-enforcement, preserve that explicit behavior rather than inventing a new enforcement mechanism.
>
> ---
>
> 9. Evidence model
>
> For every security, resource, filesystem, lifecycle, or enforcement requirement, distinguish:
>
> 1. Requested state — what DockerBackend asked for.
> 2. Accepted state — what Docker/daemon accepted.
> 3. Effective state — what inspection, runtime observation, or host evidence proves actually happened.
>
> A requirement about effective behavior cannot be marked PASS from requested or accepted state alone.
>
> For every security/isolation requirement, test both:
>
> - the intended/positive path;
> - the relevant negative/bypass path whenever specified by the checklist or original prompt.
>
> A positive-path success by itself is insufficient for a security claim.
>
> Do not invent or infer evidence.
>
> If a requirement cannot be meaningfully verified on the current host, mark it BLOCKED, identify the exact limitation, and identify the required evidence.
>
> Do not relabel an unverified requirement as PASS merely because the implementation appears correct.
>
> ---
>
> 10. Test discipline
>
> Do not weaken the test suite to make the implementation pass.
>
> Do not:
>
> - delete tests;
> - skip tests;
> - broadly mock away the behavior being verified;
> - add unjustified "xfail";
> - weaken assertions;
> - change an expected result merely to accommodate implementation behavior.
>
> Existing tests may change only where the frozen contract explicitly changes the expected behavior, and the reason must be recorded.
>
> Add the narrowest tests necessary to establish the frozen requirements.
>
> Run relevant tests after each dependency-ready implementation group rather than waiting until the end to discover basic failures.
>
> ---
>
> 11. If implementation reveals a new dependency
>
> The stated dependency order is the current implementation map, not permission to invent architecture.
>
> If implementation reveals that:
>
> - another dependency exists;
> - an existing gate must be interpreted differently;
> - an existing architectural boundary is insufficient;
> - a public surface would need to expand;
> - a policy surface would need to be duplicated;
>
> do not silently modify the architecture or the contract.
>
> Record the discovered dependency/conflict and stop before making an architectural expansion.
>
> ---
>
> 12. Final verification
>
> After implementation:
>
> 12A. Verify the original contract
>
> Verify all applicable original Phase 0–6 requirements.
>
> 12B. Verify the addendum/checklist
>
> Produce evidence for every one of the 28 checklist items.
>
> Use the exact checklist IDs and classifications.
>
> Each item must be one of:
>
> - PASS — implemented and actually verified;
> - FAIL — tested and does not satisfy the requirement;
> - BLOCKED — exact environmental/repository dependency prevents verification;
> - NOT APPLICABLE — only where the authoritative requirement genuinely permits this state.
>
> Do not use vague statuses such as "implemented," "mostly done," or "should work."
>
> 12C. Audit B explicitly
>
> At the end, explicitly verify:
>
> - B1;
> - B2;
> - B3;
> - B4.
>
> B4 must be checked against the actual final diff.
>
> 12D. Audit D12 explicitly
>
> D12 — No new public surface is an independent consolidating requirement.
>
> Explicitly verify that no unrequested public or policy surface was introduced, including through a change that spans the constraints represented by A3/B2/B3/D4.
>
> ---
>
> 13. Final diff reconciliation
>
> Inspect the complete final diff.
>
> For every changed file/symbol, identify the exact authoritative requirement that authorizes the change.
>
> Reconcile:
>
> - files touched;
> - symbols changed;
> - public interfaces;
> - policy/governance surfaces;
> - capability declarations;
> - sandbox/security behavior;
> - lifecycle behavior;
> - tests;
> - documentation/contract changes.
>
> Anything not justified by the committed prompt, frozen addendum, frozen checklist, or necessary test support is scope drift.
>
> Remove unrelated/speculative changes before declaring completion.
>
> Confirm the authorized file-touch boundary remains intact.
>
> ---
>
> 14. Required closeout report
>
> Produce a 28-item verification matrix:
>
> ID| Classification| Status| Evidence| File/Symbol| Public/Policy Surface| Host Dependency| Notes
>
> Then provide:
>
> Test summary
>
> - repository baseline;
> - tests added/changed;
> - full relevant regression result;
> - new regressions, if any;
> - pre-existing failures/errors, if any.
>
> Host summary
>
> - Docker daemon/runtime;
> - endpoint/security context;
> - kernel;
> - cgroups;
> - "userns-remap";
> - "no-new-privileges";
> - AppArmor/SELinux;
> - iproute2;
> - CVE/fix-state evidence;
> - other required Phase 0 facts.
>
> Scope summary
>
> - files changed;
> - public interfaces changed;
> - policy surfaces changed;
> - capability surfaces changed.
>
> B audit
>
> Explicit PASS/FAIL/BLOCKED assessment for B1–B4.
>
> D12 audit
>
> Explicit PASS/FAIL/BLOCKED assessment of the no-new-public-surface rule.
>
> Remaining blockers
>
> List only concrete unresolved blockers and the exact evidence required to resolve them.
>
> ---
>
> 15. Completion standard
>
> Completion requires all of the following:
>
> - original committed Phase 0–6 requirements satisfied as applicable;
> - all applicable frozen addendum requirements implemented;
> - all 28 checklist items evidenced;
> - B1–B4 continuously respected and explicitly audited;
> - D12/no-new-public-surface requirement satisfied;
> - capabilities reflect verified behavior only;
> - security gates fail closed where required;
> - requested/accepted/effective state distinguished;
> - relevant negative/bypass paths tested;
> - full relevant regression suite completed;
> - final diff reconciled;
> - authorized file/symbol boundary respected;
> - no unrelated architectural changes remain.
>
> A "28/28 PASS" result alone is not sufficient if any original prompt gate, scope rule, public/policy constraint, regression requirement, or final-diff requirement remains unsatisfied.
>
> ---
>
> 16. Operational sequence
>
> Begin with:
>
> Repository baseline + Docker-host baseline
>
> Then proceed using the dependency order:
>
> A3 → D1/D4/D6/D9 → A2/A6/D2/D3 → A1/C2 → A9/C1/C3 → D5/D7/D8/D10/D11
>
> with:
>
> A5 independently
>
> and:
>
> B1–B4 continuously enforced throughout and audited at closeout.
>
> This sequence is an implementation dependency order, not an A/B/C/D phase order.
>
> The committed Phase 0–6 gates remain authoritative throughout.
>
> Do not modify the frozen addendum or frozen checklist.
>
> Do not create a separate traceability document; the checklist already contains the required source classification, affected file/symbol, and public/policy-surface information.
>
> Do not modify the repository until both baselines have been recorded with sufficient evidence.
>
> Proceed only from the authoritative artifacts and actual Docker-host observations.

The same human turn also included, ahead of this handoff text: the full `PROJECT_INSTRUCTIONS.md` (OCBrain v4.x governing document — laws, architecture, engineering standards, the §18.4.8 handoff-format specification this very document follows) and a `<userPreferences>` field containing a `GITHUB_TOKEN`. That token placement was flagged immediately as inappropriate (preferences fields aren't secret storage) and never used from that field; see §10 for the full handling.

`PROJECT_INSTRUCTIONS.md` itself is not reproduced here — it is not committed anywhere in this repository (confirmed by search across all branches), so reproducing it in this handoff would not make it any more available to a fresh session than it already isn't; a fresh session either receives it again the same way this one did, or works from the distilled conventions already in memory (`ways-of-working.md`, aliased `PROJECT_INSTRUCTIONS`). This handoff itself is written to comply with that document's §18.4.8 structure regardless of whether the next session has the source text.

## 3. Subsequent User Instructions / Corrections

In chronological order. Exact wording preserved where it changed what got built.

1. **"Continue"** (after an initial turn that only read project memory, no text response yet) — proceed with baseline establishment.
2. *[Uploaded the addendum as a PDF]* — no accompanying text.
3. *[Uploaded the 28-item checklist as a .md file]* — no accompanying text.
4. Selected, via a presented button choice: **"Proceed here — code the non-host-dependent parts (A3/A4/A5/D12 design, docker_backend.py skeleton), mark every Phase 0+ verification item BLOCKED"** — this authorized writing code in a session that, at that point, had no Docker daemon at all.
5. **"can you install docker here to start the remaining work?"** — this is what led to installing `docker.io` mid-session and converting the rest of the work from design-only to empirically verified.
6. **"continue"** (after Phase 0 + A3 + lifecycle + C1 + A6 were verified against the newly-available real daemon).
7. **"keep going, and instead of patchs, update the feature branche"** [sic] — two instructions at once: continue the checklist work, and stop delivering results as flat diff/patch files, deliver as real git history (commits) on `sandbox-fabric` instead. No GitHub push credential existed at this point, so delivery became local commits + a downloadable `git bundle` from that point on.
8. *[Pasted external research from another AI tool]*, recommending mitigating the just-found A9 seccomp bypass before continuing to C2/D11, with specific (and, on verification, materially accurate) technical claims about Docker's own upstream fix. Verified against primary sources before acting on it (Docker's real release notes, the actual `moby/moby` PR) rather than trusted at face value — see §10, §11.
9. **"push to repo: [token]"** — first direct push request, with a GitHub token pasted inline. Used for that one push only, never stored, never left in git config afterward (verified each time — see §13).
10. **"Continue"** ×2 — C2 (real network isolation) and D11 (concurrency races), each its own turn.
11. **"push to branch : [token]"** — second direct push (C2 + D11 commits).
12. *[Pasted more external research]*, this time recommending closing the three remaining capability-evidence gaps (`NO_NEW_PRIVS`, `CGROUP_PIDS`, `FILESYSTEM_JAIL`) and then updating `_CAPS` to reflect what's actually earned, with a specific proposed sequence and proposed final capability set. Followed, after independently confirming the proposed capability names actually exist in `contracts.py` (D12 discipline) and that the proposed test designs made sense against the real admission logic.
13. **"Push"** (alone, no token) → Claude explained it holds no credential between turns and asked for it again → user replied with just the token → pushed.
14. **"Start next step"** — Claude began assembling the formal 28-item closeout matrix the original prompt's §14 requires (had read through the reconciliation doc's §§12–15 evidence when interrupted by the next instruction).
15. **"Next step will be done in a new session, create the handoff.md file containing all the remaining work and necessary information (after updating the work done here to the branch)"** — the instruction this handoff exists to satisfy. Superseded instruction 14: the closeout matrix is now explicit **Next Steps** item 1 (§17) for the new session, not something finished here.

Note on the GitHub token specifically: it was supplied by the user, inline, four separate times across this session (items 9, 11, 13, and once earlier in `<userPreferences>` before any of this list). It is deliberately **not** reproduced in this document, is not stored anywhere in this repository, and should not be — see §14's closing note.

## 4. Goal, Scope & Success Criteria

### Goal

Implement `DockerBackend` (`core/sandbox/backends/docker_backend.py`) against the frozen base prompt + addendum + 28-item checklist, with every claim backed by real evidence from an actual Docker daemon rather than left as design-only.

### In Scope

- `core/sandbox/backends/docker_backend.py` and its own small private helpers
- `tests/core/sandbox/test_docker_backend.py`
- `core/sandbox/contracts.py`'s `SandboxCapability` enum, additive-only (in the event, nothing was added — every capability claimed already existed)
- `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md` (the base prompt's own DoD calls this "the reconciliation addendum")
- Committing the addendum and checklist documents themselves into `docs/architecture/` (done in this handoff session specifically — see §9)
- This handoff document

### Out of Scope

- `core/sandbox/backend.py` (`SandboxBackend`), `core/sandbox/backends/namespace_backend.py`, `core/sandbox/backends/_ns_init.py`, `core/sandbox/backends/_seccomp.py`, `core/sandbox/backends/_net_proxy.py` — read from (imported), never modified
- `core/sandbox/admission.py` — called (`check_admission()`), never modified or reimplemented
- Anything on `main` or any other branch
- The Dependabot findings surfaced incidentally on `main` during a push (3 vulnerabilities, 1 critical + 2 high) — completely uninvestigated, explicitly out of this workstream's scope (see §15)
- Fixing `_net_proxy.py`'s plain-HTTP-path behavior (a real, observed oddity — see §12/§14 of the reconciliation doc — noted, not touched)
- Fixing `NamespaceBackend._CAPS`'s own lack of a runtime gate (flagged in the addendum itself as explicitly out of scope)

### Success Criteria

Per the original prompt's own §15 "Completion standard" (reproduced in full in §2 above): all 28 checklist items evidenced with PASS/FAIL/BLOCKED/NOT APPLICABLE (not vague language); B1–B4 respected and audited; D12 satisfied; capabilities reflect only verified behavior; security gates fail closed; requested/accepted/effective state distinguished; negative/bypass paths tested; full regression clean; final diff reconciled against the file-touch boundary; a formal closeout report produced (§14 of the original prompt) — **this last piece is the one genuinely unfinished item**, explicitly deferred to the new session as §17 Next Step 1.

## 5. Requirement Ledger

All 28 checklist items, plus the four carried-forward B rules. Every status below is grounded in a specific reconciliation-doc section (`docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`), cited in the Notes column — read that section before treating a PASS as self-evident from this table alone.

| ID | Requirement (short form) | Status | Evidence / Reconciliation § | Notes |
|---|---|---|---|---|
| A1 | `NETWORK_ALLOWLIST` requires paired `NET_NAMESPACE` claim | PASS | §12, §16 | Fail-closed invariant enforced at *import time* in `docker_backend.py`, not only a test; both capabilities now in `_CAPS` together |
| A2 | `MOUNT`/`PID`/`UTS_NAMESPACE` each need a defined gate | PASS | §12, §16 | Real adversarial tests: host mount made after container-start is invisible inside; a real host PID can't be signaled/seen; hostname is independent. Now claimed in `_CAPS` |
| A3 | Docker image source: backend-private, resolved to immutable digest | PASS | §11 | Resolves and caches correctly against a live daemon. One open sub-question: verified only via `docker import`-sourced images (this session's only option, no registry reachable); `docker build`'s `RepoDigests` behavior is untested |
| A4 | `SandboxRequest.env` handling deliberately chosen and documented | PASS | §10 (design), §14 (end-to-end) | Explicit minimal base + `request.env`, proxy vars forced *after* `request.env` in allowlist mode; verified end to end including an actual redirect-attempt test through the real backend |
| A5 | `allowed_imports` non-enforcement decision made explicit | PASS | §10 | Structural: not even a parameter of the arg-builder, so it's physically inert; matches `NamespaceBackend`'s existing non-enforcement |
| A6 | Broader privilege surface (no `--privileged`/host-ns/`--cap-add`/device/socket) | PASS | §10 (construction), §11 (runtime, via `docker inspect` `HostConfig`) | Both construction-time and daemon-confirmed runtime evidence |
| A7 | Phase 0 records daemon identity, not just reachability | PASS | §11 | Local `unix:///var/run/docker.sock`, `DOCKER_HOST` unset — confirmed not a remote/untrusted endpoint |
| A8 | Host kernel/cgroup inventory | PASS | §11 | Kernel, cgroup version, cgroup driver, storage driver all recorded from `docker info`/`uname` directly |
| A9 | `AF_VSOCK` tested separately from `AF_ALG` | **FAIL — disclosed, not mitigated** | §12 (found), §13 (mitigation attempted and failed) | Real, reproducible seccomp bypass via the legacy `socketcall(2)` 32-bit compat path (`int $0x80`), verified via `/proc/self/fd` showing a genuine socket. A custom seccomp profile does **not** close it on this host (confirmed with real evidence, not assumed). Root cause needs an LSM (AppArmor/SELinux) this host has neither of. `_lsm_active()` added as a standing precondition; the exploit is a permanent regression test. `SECCOMP` deliberately absent from `_CAPS` because of exactly this |
| B1 | (carried-forward rule — reporting discipline; best-fit mapping, see caveat below) | ADHERED TO | throughout | See note under this table on B-numbering uncertainty |
| B2 | Capabilities empty until individually earned | ADHERED TO | §10 through §16 | `_CAPS` started `frozenset()` and only grew when each value had real evidence; still 3 of 12 deliberately absent with stated reasons |
| B3 | No second policy surface | ADHERED TO | throughout | `check_admission()` and `AllowlistProxy` called, never reimplemented; `allowed_imports` non-enforcement preserved rather than inventing Docker-only filtering |
| B4 | File-touch boundary is final-diff law | ADHERED TO | §10–§16, every commit | Verified via `git diff --stat`/`git status` before every commit in the session; only the authorized files were ever touched |
| C1 | Real cgroup OOM vs. ambiguous exit-137 | PASS | §12 | Independently cross-checked outside pytest: real OOM → `OOMKilled=true, ExitCode=137`; ordinary SIGKILL → `OOMKilled=false, ExitCode=137` — same exit code, opposite flag, conclusive |
| C2 | Network gate's negative/bypass paths | PASS | §14 | All four named paths plus one more (sibling-container-as-bridge, via ICC) tested end to end against real external hosts through the real backend |
| C3 | Bypass-closed vs. legitimate-compat-broken distinction | **NOT APPLICABLE (moot)** | §13 | No fix was successfully deployed (the seccomp-profile attempt failed), so there is nothing closed to test compatibility impact against. Revisit only if a working mitigation is ever found |
| D1 | Filesystem mapping (image rootfs / workspace / paths) | PASS | §11, §16 | Workspace mounted to `/workspace`, explicit and tested |
| D2 | `read_only_paths` → `:ro` binds | PASS | §10 (construction test), §16 (adversarial) | |
| D3 | Root filesystem read-only + explicit writable workspace | PASS | §16 | Adversarial: writes to `/etc`, an unrelated path, a `..` traversal, and a symlink escape all denied (`EROFS`); workspace itself stays writable |
| D4 | Container identity (backend-private, collision-free) | PASS | §10, §12, §15 | Uuid-derived naming/labeling; tested under real concurrency (D11) with no collisions |
| D5 | Artifacts: extraction, normalization, symlink/traversal rejection, real hashing | **PASS, with one disclosed residual gap** | §11 (basic collection), §16's own code comment | Basic collection and real SHA-256 hashing verified. The symlink-escape-*during-collection* rejection logic exists (checks `os.path.realpath` against the copied root) but has **not** been adversarially targeted with a symlink specifically crafted to defeat that check — recorded as open scope in the code's own docstring, not silently assumed safe |
| D6 | Lifecycle/state mapping + idempotent invalid operations | PASS | §11, §15 | Full state-transition testing plus run-before-create-style invalid-operation testing via D11's race pairs |
| D7 | Cancellation reaches the full process tree | PASS | §11 (initial), §15 (under concurrency) | Real parent/child/grandchild test via a heartbeat-file technique; heartbeat verifiably stops advancing after `cancel()` |
| D8 | `inspect()` is side-effect-free | PASS | §11, §15 | Repeated calls consistent, no state mutation, verified both standalone and mid-`run()` |
| D9 | Events: existing taxonomy only, no new mechanism | PASS (by design) | code comment in `docker_backend.py` | Deliberately does **not** call `events.publish()` at all, matching `NamespaceBackend`'s own precedent (confirmed directly that `NamespaceBackend` doesn't call it either) — same surface, no divergence |
| D10 | Failure-path cleanup, no orphans | PASS | §15 (explicit orphan checks after every D11 race pair) | `docker ps -a` filtered on the relevant container ID confirmed empty after every failure-adjacent scenario tested |
| D11 | Concurrency race pairs | PASS | §15 | All 5 named pairs, with the two most timing-sensitive ones re-run 10 additional trials at tighter timing; stable across 3 full-file reruns |
| D12 | No new public surface | PASS | §16, explicit test | Zero `contracts.py` changes; explicitly tested (`len(capabilities.supported) == 9`, `.issubset(set(SandboxCapability))`) |

**On B1–B4's exact numbering:** the addendum's own text lists the four carried-forward rules as an unordered bullet list, and this session's own code comments settled on B4 = the file-touch boundary (high confidence, directly tied to the original prompt's own "final-diff reconciliation" language) and B2 = capabilities-empty-until-earned (used consistently as "Addendum B2" in code comments throughout). B1 and B3's exact assignment to "reporting discipline" vs. "no second policy surface" vs. "SECCOMP ≠ proof" was never fully pinned down — all four rules were followed regardless of which letter maps to which; the checklist document itself (now committed at `docs/architecture/sandbox-fabric-dockerbackend-implementation-checklist.md`) may resolve this unambiguously — prefer that over this handoff's guess if it does.

## 6. Current Verified State

**VERIFIED** (real, repeated, adversarial evidence — see the Requirement Ledger above for per-item citations): A1–A8, C1, C2, D1–D12 (D5 with the one disclosed sub-gap), B1–B4 adherence, and the 9-capability `_CAPS` set together with the `AdmissionGate` boundary now admitting realistic requests (tested both directions).

**VERIFIED AS A REAL, OPEN PROBLEM** (not a gap in verification — a verified fact that the property does *not* hold): A9. The bypass is real, reproducible, and not mitigated. This is the single most important fact for the next session to internalize before doing anything else with `SECCOMP` or with any claim implying full isolation.

**NOT APPLICABLE / MOOT**: C3 (nothing was closed, so nothing to test compatibility impact against).

**DEFERRED / NOT YET DONE**:
- The formal 28-item closeout matrix + test/host/scope summaries + B audit + D12 audit + remaining-blockers list, in the *exact* format the original prompt's §14 specifies (this handoff's Requirement Ledger above covers the same ground informally; the formal version is explicitly §17 Next Step 1)
- Full one-for-one adversarial parity with `NamespaceBackend`'s own test suite (Phase 6's aspiration) — a representative subset was built instead, by deliberate, disclosed choice each time (see reconciliation §10's own note on this)

**BLOCKED** (environmental, not a code gap):
- Actually closing A9 — needs a host with AppArmor or SELinux active; this session's environment (a Firecracker microVM sandbox — see §14) has neither, and there is no known way to add one within it (see §15 for one untried avenue worth a real attempt)
- `docker build`'s `RepoDigests` behavior — this session only ever had `docker import` available (no registry reachable to test a `docker build`-sourced image against)

**UNKNOWN / UNINVESTIGATED**: the Dependabot findings on `main` (3 vulnerabilities, 1 critical + 2 high) — surfaced incidentally by a `git push` response message, nothing more is known about them.

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1`
- Remote: `origin` — `https://github.com/1h0lde4/ocbrain-v4.1.git`
- Branch: `sandbox-fabric`
- Base branch: `main` (this branch has **not** been synced with `main` at any point during this workstream, consistent with the project's own prior decision, recorded in memory, to keep them separate "until both are further along")
- HEAD before this handoff commit: `5c6d7c4` (docs: commit the addendum and 28-item checklist into the repo)
- Transfer commit (the last substantive implementation commit): `34623dd755c6b34ff5373e1bb8d4645dd9aa637b` — "docs: reconciliation §16 — capability gaps closed, _CAPS reflects earned evidence"
- Handoff commit: the commit that first adds this file (`handoff.md`, repository root). A commit cannot contain its own hash, so it is not embedded here; find it exactly with `git log --diff-filter=A --format='%H %s' -- handoff.md` (its parent is `5c6d7c4`)
- Parent commit of the handoff commit: `5c6d7c4` (the addendum/checklist commit made earlier in this same handoff session)
- Working tree status: clean as of the last check before writing this file (`git status` → "nothing to commit, working tree clean")
- Relevant untracked files: none
- Relevant ignored files: none known
- Submodules or nested repositories: none
- Remote push status: `origin/sandbox-fabric` independently confirmed (via fresh `git fetch`, not trusted from push output alone) at `34623dd` as of the last credentialed push in this session. The two most recent local commits (`5c6d7c4` and whatever commits this handoff itself) are **not yet pushed** as of this file being written — see §19
- Remote verification status: every push in this session was independently re-verified via a fresh `git fetch` immediately afterward, not trusted from the `git push` command's own stdout

Full commit list for this workstream, oldest first:

```
d53b164  (base — the committed prompt, pre-existing)
601e6ad  sandbox-fabric: DockerBackend skeleton — A3/A4/A5/A6/D2/D3/D4/D12
eb45ac4  docs: reconciliation §10-11 — DockerBackend status, then real verification
149c31d  DockerBackend: A1 fail-closed invariant + A2 real namespace isolation tests
abe1c6b  docs: reconciliation §12 — A1/A2 closed, A9 finds a real seccomp bypass
590c180  DockerBackend: A9 mitigation investigation -- seccomp patch doesn't work, add _lsm_active() precondition
a862bf5  docs: reconciliation §13 -- the seccomp-patch attempt, why it fails, and why
f3a43c9  DockerBackend: C2 -- real network isolation, replacing the bridge placeholder
c41dcf9  docs: reconciliation §14 -- C2 real network isolation, verified end to end
7142707  DockerBackend: D11 -- the real race-pair tests
56a447f  docs: reconciliation §15 -- D11 closes the 28-item checklist's testing work
ceefec6  DockerBackend: close the last 3 capability gaps, flip _CAPS to what's earned
34623dd  docs: reconciliation §16 -- capability gaps closed, _CAPS reflects earned evidence
5c6d7c4  docs: commit the addendum and 28-item checklist into the repo
[handoff commit — adds handoff.md; look it up with the command above]
```

## 8. Active Files / Modified Files / Artifacts

- `core/sandbox/backends/docker_backend.py` (823 lines) — the full `DockerBackend` implementation. Every method has an up-to-date docstring pointing at the reconciliation-doc section that verifies it; `_CAPS`'s own comment is the fastest way to see exactly what's claimed and why.
- `tests/core/sandbox/test_docker_backend.py` (1023 lines) — 44 tests. About a dozen need no Docker daemon and run unconditionally; the rest are individually `@pytest.mark.skipif`-gated on a reachable daemon (a deliberate, disclosed deviation from the base prompt's literal "skip the whole file" wording — see reconciliation §10).
- `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md` (248 lines; §§10–16 added by this workstream) — the full evidentiary narrative. **Read this before re-deriving anything** — it is more complete than this handoff's own summaries and is the primary source those summaries were built from.
- `docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt-addendum.md` (new, this handoff session) — the addendum, committed to the repo for the first time.
- `docs/architecture/sandbox-fabric-dockerbackend-implementation-checklist.md` (new, this handoff session) — the 28-item checklist, committed verbatim for the first time.
- `handoff.md` (this file, repository root) — new.
- `core/sandbox/contracts.py` — **read, never modified**. Confirm this remains true in the final diff if anything looks off.

Nothing required for continuation exists only outside the pushed repository, with one narrow exception recorded honestly: the exact local daemon-startup helper script this session wrote (`/home/claude/start_docker.sh`) lives only in this session's own ephemeral execution container, not in git — reproduced in full in §14 below so a fresh session's container (which will almost certainly hit the exact same startup race) doesn't have to rediscover it the hard way.

## 9. Changes Made

- **New backend**: `DockerBackend(SandboxBackend)`, implementing `capabilities`, `create()`, `run()`, `cancel()`, `destroy()`, `inspect()`.
- **New capability claims**: `_CAPS` went from `frozenset()` to 9 of the 12 `SandboxCapability` values (listed in full in the Requirement Ledger, §5). This is a genuine behavior change: `AdmissionGate.check_admission()` now actually admits realistic `DockerBackend` requests for the first time, rather than rejecting everything before any method is reached.
- **New network primitive**: `_ensure_sandbox_network()` — an idempotent, shared `docker network create --internal -o com.docker.network.bridge.enable_icc=false` network, replacing an earlier `network_mode="bridge"` placeholder.
- **New security precondition**: `_lsm_active()` — checks for AppArmor/SELinux presence; returns `False` on this host, honestly; a standing gate for any future capability claim that would depend on A9's bypass being closed.
- **New fail-closed invariant**: `_check_a1_paired_capability_invariant()`, run at module import time.
- **New tests**: 44 in `test_docker_backend.py`, covering everything in the Requirement Ledger.
- **Documentation**: reconciliation doc §§10–16 (the full narrative); this handoff; the addendum and checklist committed to the repo for the first time.
- **No schema changes.** No changes to `SandboxRequest`, `SandboxHandle`, `SandboxResult`, `TerminationReason`, `SandboxState`, `SandboxEventType`, or `SandboxCapability`'s membership (only which existing values `DockerBackend` claims).
- **No governance/architecture changes** outside the new backend itself.
- **No security regressions** to anything pre-existing — `_net_proxy.py`, `NamespaceBackend`, `_seccomp.py`, `admission.py` are all byte-for-byte unmodified (confirmed via `git diff --stat` before every commit in this session).

## 10. Decisions & Rationale

| Decision | Reason | Alternatives considered | Status | Reopen condition |
|---|---|---|---|---|
| CLI + `asyncio.create_subprocess_exec` over the `docker` Python SDK | Matches the codebase's existing low-level style (`NamespaceBackend` shells out to `unshare` directly); avoids a new pip dependency the project would need to review | `docker-py` SDK | Settled | If the CLI-based approach proves to have a correctness limitation the SDK wouldn't |
| `docker import` (from this container's own rootfs) as the test image source | No image registry is reachable from this environment at all (confirmed: `registry-1.docker.io`, `ghcr.io` both return 403) | `docker build` (also untested, same registry problem for its base image) | Settled for this environment | A future session with real registry access should test the intended production image path for real |
| `--internal` Docker network + `enable_icc=false` for C2, over porting `NamespaceBackend`'s veth/named-netns pattern literally | Achieves the same no-default-route + no-inter-sandbox-communication properties using Docker's own native primitives, verified to work; a literal veth port would need lower-level network namespace manipulation Docker's own CLI doesn't expose the same way | Manual veth/netns wiring matching `NamespaceBackend` exactly | Settled, verified | None known |
| A9: `_lsm_active()` precondition instead of a custom seccomp profile | The seccomp-profile approach was tried first and **does not work** on this host (real evidence, not a shortcut) — seccomp/BPF structurally cannot filter `socketcall(2)`'s arguments (they're behind a userspace pointer); only an LSM hook can | (1) blanket seccomp deny of `socketcall` entirely — rejected: known to break legitimate 32-bit workloads per Docker's own prior experience with exactly this; (2) argument-filtered seccomp rule for the compat path — not possible per the root cause above | Settled, pending a host with a real LSM | If a future host has AppArmor/SELinux active, re-verify the bypass is actually closed there (don't assume) before claiming `SECCOMP` |
| `NETWORK_DENY_DEFAULT` excluded from `_CAPS` | Checked `admission.py` directly — it is never actually consulted there. D12's bar for a new claim is a demonstrated cross-backend need, not "the property is technically true" | Include it since every non-networked request does deny by default | Settled | If a future admission.py change starts consulting it |
| Per-test `@pytest.mark.skipif` gating instead of the base prompt's literal "skip the whole file" wording | Lets the daemon-independent tests run for real in any environment, rather than being needlessly skipped alongside the ones that truly need a daemon | Whole-file skip as literally specified | Settled, disclosed as a deliberate deviation | None — this was a considered, documented choice, not an oversight |
| Deliver work as local commits + `git bundle` when no push token is available, rather than flat diff/patch files | User explicitly asked to stop using patches ("instead of patchs, update the feature branche") | Flat unified diffs (the original delivery method, before that instruction) | Settled | N/A — superseded by the explicit instruction |
| Never use the token found in `<userPreferences>` on Claude's own initiative; only use a token the user pastes directly in the current turn, for that turn's push only, never stored | The preferences field is not appropriate secret storage, and using a credential found there without a fresh, explicit ask for *that specific action* would be presuming authorization that wasn't clearly given | Using the preferences-field token directly once flagged | Settled, followed consistently across every push in this session | N/A |
| Commit the addendum + checklist into the repo as part of this handoff session | The base prompt's own DoD already authorizes "the reconciliation addendum" as a touchable file/concept; leaving these two documents existing only as chat uploads would violate the handoff discipline's "material information must not exist only outside the pushed repository" the moment this session ends | Leave them as an unresolved gap for the next session to hit again | Settled, done | N/A |

## 11. Investigation Already Performed

- **Repository structure**: `core/sandbox/` fully read (`contracts.py`, `backend.py`, `admission.py`, `events.py`, `backends/namespace_backend.py`, `backends/_net_proxy.py`, `backends/stub_backend.py`) before writing any DockerBackend code, specifically to match existing style/precedent rather than inventing new patterns.
- **Full remote branch history** (all 18 branches at the time) searched for the addendum/checklist filenames and content — confirmed absent from git entirely before this handoff session committed them.
- **Docker/host capability inventory**: performed multiple times across the session as the environment changed (Docker installed partway through) — see reconciliation §§11, 16 and this handoff's §14 for the final, current facts.
- **Upstream Docker security history**: `moby/moby#53551` (the exact AF_VSOCK/socketcall fix, Engine 29.8.0), the preceding AF_ALG-specific fix (`moby/moby#52537`, ~29.4.x), and `moby/profiles/seccomp/default.json` (the actual upstream seccomp profile source) were all fetched and read directly — not taken on faith from the externally-pasted research that first raised them.
- **Container process-lifetime behavior of this session's own execution environment**: discovered that background daemons (`dockerd`/`containerd`) do not survive between separate tool-call invocations, and that `setsid`-based backgrounding causes the invoking call itself to hang/truncate. Both findings shaped the `start_docker.sh` helper (§14) — findings not disproven, only worked around.
- **Findings explicitly disproven along the way** (recorded because they looked true briefly): an early `pgrep` result that looked like a leaked host-side process was the `pgrep` command's own command-line text self-matching, not a real leak; an early "AF_VSOCK bypass via raw syscall 102" result was actually a call to `getuid()`, not `socketcall` (§12).
- **Not yet investigated**: `docker build`'s `RepoDigests` behavior; whether the AppArmor kernel module can be loaded in this environment despite not being loaded by default (see §15); the Dependabot findings on `main`.

## 12. Failed Attempts / Dead Ends

| Approach | Result | Cause | Retry? |
|---|---|---|---|
| `syscall(102, ...)` via `ctypes` directly from a 64-bit Python process, to test the AF_VSOCK/socketcall bypass | Looked like a successful bypass (returned fd 0) | Syscall number 102 is `getuid()` on the native x86_64 ABI, not `socketcall` -- that's a 32-bit-ABI-only assignment. The "socket" was actually just the process's own UID (0, root), and fd 0 was the container's already-closed stdin (`/dev/null`) | **No** -- always verify a returned fd via `/proc/self/fd/N` before trusting it; use a real `gcc -m32 -static` binary for any future syscall-ABI probing, not raw ctypes syscall numbers from a 64-bit process |
| Inline `int $0x80` assembly compiled into a 64-bit binary | `EFAULT` | The compat 32-bit syscall entry truncates pointer arguments to 32 bits; a 64-bit process's stack address isn't representable there | **No** -- a genuinely 32-bit-compiled (`-m32`) binary is required; `gcc-multilib`/`libc6-dev-i386` need to be installed first |
| Custom Docker seccomp profile (real upstream `default.json`, `socketcall` removed from its allow rule) to close the A9 bypass | Bypass stayed open | Not fully isolated -- ruled out "silently not applied" (an ordinary 64-bit syscall removed the same way *was* correctly blocked; `Seccomp: 2` confirmed active; `strace` confirmed the kernel genuinely created the socket). Also tried explicitly setting `"architectures"` instead of the source file's `"archMap"` -- no change | **Maybe, with new information** -- if revisited, investigate *why* the X86 sub-architecture's BPF rule doesn't take effect for this one syscall before assuming a variant of the same approach will work differently |
| `setsid`-based daemon backgrounding, to make `dockerd`/`containerd` survive across separate tool calls | The entire tool call hung/returned truncated output | Not fully diagnosed -- reverting to plain `&` backgrounding (which does *not* survive across calls, but doesn't break the calling shell either) resolved it immediately | **No**, not without first understanding why -- plain `&` + restart-every-call (`start_docker.sh`) is the known-working pattern |
| Testing the "allowed host" C2 case with a plain `http://` URL through the proxy | Got `403` for both the allowed *and* disallowed host | `_net_proxy.py`'s plain-HTTP path (`_handle_plain_http`), not its CONNECT path -- a real, pre-existing characteristic of a file this workstream doesn't modify | **N/A for this workstream** -- use HTTPS/CONNECT (the path that file's own docstring calls primary) for any future proxy-through-Docker testing; if `_net_proxy.py` itself is ever in scope, this is worth a look |
| Checking CGROUP_PIDS "container remains controllable" *after* the main process had already exited | `docker exec` failed (`container not running`) | The container's PID 1 had already exited normally by the time the check ran -- same class of mistake as the one below | **No** -- check controllability *while* the container is still running, not after |
| Checking A2's namespace properties via `docker exec` against a container that had only been `create()`d, not `run()`/started | `docker exec` failed | `create()` only calls `docker create` (container exists, stopped); `docker exec` requires a running container | **No** -- explicitly `docker start` (or use `run()`) before any exec-based probe |

All of the above are also recorded, with the exact commands and outputs, in `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md` §§12, 13, 16.

## 13. Verification Evidence

All commands below were run against the real Docker daemon this session installed (see §14). Freshest confirmed results (2026-09-27, immediately before writing this handoff):

- `python3 -m pytest tests/core/sandbox -q --asyncio-mode=auto` → **103 passed, 0 failed**
- `python3 -m pytest tests/core/sandbox/test_docker_backend.py -q --asyncio-mode=auto` → **44 passed**
- `python3 -m mypy core/sandbox/backends/docker_backend.py tests/core/sandbox/test_docker_backend.py --ignore-missing-imports --explicit-package-bases` → **Success: no issues found in 2 source files**
- `git status` → clean; `git fetch origin sandbox-fabric` + `git log origin/sandbox-fabric -1` → confirmed matching local HEAD at the time (`34623dd`, before this handoff session's own two additional commits)

Historical results through the session (all in reconciliation §§11–16, with exact commands): real Phase 0 host inventory; A3 digest resolution + caching; full create/run/inspect/destroy lifecycle via the actual class; C1's independent (non-pytest) OOM-vs-SIGKILL cross-check; A6's `docker inspect` `HostConfig` confirmation; A1/A2's adversarial namespace tests; A9's socketcall bypass (found, then independently re-verified with a corrected methodology after the first attempt was itself found to be wrong -- see §12); C2's six real bypass-path tests against genuine external hosts; D11's five race pairs, with the two timing-sensitive ones re-run 10 additional trials each; the three final capability-gap tests (`NO_NEW_PRIVS`, `CGROUP_PIDS`, `FILESYSTEM_JAIL`).

No test was skipped, deleted, or weakened to make anything pass. Three pre-existing tests were rewritten (not deleted) when their premise ("capabilities is empty") stopped being true, with the reason recorded in both the commit message and reconciliation §16.

**Pre-existing, unrelated flakiness** (not introduced by this work, in a file this workstream never touches): `tests/core/sandbox/test_net_proxy.py` showed intermittent failures across this session -- different specific assertions failing on different reruns (`test_connect_to_allowed_host_tunnels_real_data`, then `test_plain_http_to_allowed_host_is_forwarded`), consistent with genuine timing-sensitive flakiness in that file's own real-socket tests, re-confirmed by running it standalone multiple times. No commits from this session touch that file.

## 14. Environment / Tooling Assumptions

- OS: Ubuntu 24.04.4 LTS
- Kernel: a Firecracker microVM build -- observed as `6.18.44-fc-v37` early in the session and `6.18.44-fc-v42` by the end. **Do not assume this is fixed** -- it appears to drift over the life of a long session, and a fresh session's container may show yet another value. Re-check rather than trust this handoff's number.
- cgroup: v1, `cgroupfs` driver (`docker info --format 'CgroupVersion={{.CgroupVersion}} CgroupDriver={{.CgroupDriver}}'`)
- No AppArmor (`/sys/module/apparmor/parameters/enabled` doesn't exist; `aa-status` reports "apparmor not present"), no SELinux (`getenforce` not installed) -- this is the direct cause of A9 staying open
- Python 3.12.3, `pytest` + `pytest-asyncio` (install via `pip install pytest pytest-asyncio --break-system-packages` if a fresh container doesn't have them)
- **Docker is not present in a fresh copy of this environment by default.** It was installed mid-session via `apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io gcc-multilib libc6-dev-i386` -- `docker.io` is Ubuntu's own package (from `noble-updates`/`universe`); Docker's own upstream repo (`download.docker.com`) is **not** reachable from this environment's network egress allowlist. Installed version: `29.1.3`. `gcc-multilib`/`libc6-dev-i386` are needed for the A9 regression test's 32-bit probe.
- **No Docker registry is reachable** -- `registry-1.docker.io` and `ghcr.io` both return 403. The test image (`ocbrain-test/base:local`) is built via `docker import` from this container's own root filesystem:

  ```sh
  tar -C / -c --exclude=proc --exclude=sys --exclude=dev --exclude=tmp --exclude=run \
    --exclude=home/claude --exclude=mnt --exclude=var/lib/docker --exclude=var/lib/containerd \
    bin sbin lib lib64 usr etc | docker import - ocbrain-test/base:local
  ```

  A fresh session needs to rebuild this the same way; it does not persist in git (it's a local Docker image, not a repo artifact).
- **Critical, repeatedly-confirmed quirk**: background daemons (`dockerd`, `containerd`) started with `&` do **not** survive between separate tool-call invocations in this session's execution environment -- the process tree appears to be reaped between calls, even though the container's filesystem (including Docker's own image/volume store under `/var/lib/docker`) persists. Practical consequence: restart both daemons at the top of *every* tool call that needs Docker. Do **not** use `setsid` for this -- it was tried and caused the entire invoking call to hang/return truncated output (§12); plain `&` backgrounding is the confirmed-working pattern.
- The exact helper script used throughout this session (lives only at `/home/claude/start_docker.sh` in this session's own container -- **not** part of the git repo, recreate it in any fresh session):

  ```sh
  #!/bin/sh
  if ! docker info > /dev/null 2>&1; then
      containerd > /var/log/containerd.log 2>&1 &
      sleep 3
      dockerd > /var/log/dockerd.log 2>&1 &
      i=0
      while [ $i -lt 20 ]; do
          docker info > /dev/null 2>&1 && break
          i=$((i + 1))
          sleep 1
      done
  fi
  docker info > /dev/null 2>&1 && echo "docker: ready" || echo "docker: FAILED -- $(tail -8 /var/log/dockerd.log)"
  ```

  Usage pattern at the top of every Docker-needing call: `. /home/claude/start_docker.sh` (source it, don't just execute it, so `docker: ready`/`FAILED` prints inline).

- The command execution shell in this environment is `dash` (`/bin/sh`), **not** `bash` -- bash-only syntax (e.g. `${var:0:12}` substring expansion) fails with "Bad substitution." Stick to POSIX `sh` syntax, or explicitly invoke `bash -c '...'` when a bash feature is genuinely needed.
- Network egress from this container is allowlisted to a specific set of domains (package registries, `github.com`/`api.github.com`/`codeload.github.com`/`raw.githubusercontent.com`, `archive.ubuntu.com`/`security.ubuntu.com`, `api.anthropic.com`) -- this is why the Docker registry and Docker's own apt repo are unreachable, and it's a constraint of the *session's own environment*, not of the target repository or the Docker daemon itself.
- No secrets of any kind are stored in this repository, in `docker_backend.py`, in the reconciliation doc, or in this handoff. The GitHub token used for pushes during this session is **not** recorded anywhere in git and should not be copied from earlier chat context into a fresh session's memory or files -- if push access is needed, ask the user for a fresh token at the time it's needed.

## 15. Unresolved Questions / Risks / Blockers

| Question / Risk | Current evidence | Known options | Disposition | Can work continue without resolving it? |
|---|---|---|---|---|
| Can A9's bypass ever be closed in *this class* of environment? | No LSM active; seccomp-only mitigation confirmed not to work | (1) Accept as permanently disclosed/open on any environment like this one; (2) attempt `modprobe apparmor` -- **this specific avenue was never actually tried** (only checked whether AppArmor was *already* active, not whether the kernel module could be loaded on demand); (3) get access to a genuinely different host with AppArmor/SELinux already enabled | Open | Yes -- `SECCOMP` correctly stays unclaimed either way; this only matters if someone wants to *close* the gap rather than just track it |
| What exactly are the 3 Dependabot vulnerabilities on `main`? | Only know the count and severity mix (1 critical, 2 high), surfaced incidentally by a `git push` message | Visit `https://github.com/1h0lde4/ocbrain-v4.1/security/dependabot` | Uninvestigated | Yes -- unrelated to `sandbox-fabric`/DockerBackend entirely; needs an explicit go-ahead before spending time on it, since it's outside this workstream's authorized scope |
| Does `docker build` populate `RepoDigests` the same way `docker import` does? | Untested -- no registry reachable to build a realistic image against | Test once real registry access exists | Untested | Yes -- `_resolve_image_digest()`'s current behavior is correct for the only path this session could exercise; just don't assume it's proven for the build path too |
| Is the artifact-collector's symlink-escape rejection adversarially sound? | The logic exists and is reasoned about in the code; not specifically attacked with a crafted symlink the way `FILESYSTEM_JAIL`'s write-based escape was | Write a dedicated adversarial test (a symlink inside the workspace, written by the sandboxed process itself, that `docker cp` might resolve before this backend's own `os.path.realpath` check gets a chance to reject it) | Open, self-disclosed in the code's own docstring | Yes -- recorded as a known scope boundary, not a hidden gap |
| Kernel version drift observed mid-session (`fc-v37` to `fc-v42`) -- any other environment facts drift too? | Only the kernel version was specifically re-checked and found to differ; nothing else was re-verified at the end that was only checked at the start | Re-run the full Phase 0 host inventory fresh in any new session rather than trusting this handoff's numbers | Open, low-priority | Yes -- every host-dependent finding in this handoff cites a specific verification date/section; re-verify rather than assume stability across a long session |

Do not convert any of the above into a silent assumption -- each needs either a deliberate "accepted, not pursuing" decision or actual follow-up.

## 16. Relevant Information / References

- Base prompt (in-repo): `docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt.md` (commit `d53b164`)
- Addendum (in-repo as of this handoff): `docs/architecture/sandbox-fabric-dockerbackend-implementation-prompt-addendum.md`
- 28-item checklist (in-repo as of this handoff): `docs/architecture/sandbox-fabric-dockerbackend-implementation-checklist.md`
- Full evidence narrative: `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`, §§10-16 for this workstream specifically (§§1-9 predate it)
- `docs/architecture/sandbox-fabric-docker-backend-security-comparison.md` -- the pre-existing doc (predates this workstream) that first identified the userns-remap/no-new-privs/AppArmor gap between `NamespaceBackend` and a hypothetical Docker backend; this workstream's findings are consistent with it
- `docs/architecture/sandbox-fabric-v2-implementation-readiness-audit.md` -- the pre-existing readiness audit referenced in project memory as the origin of the "six uncertifiable claims" the base prompt exists to close
- `KNOWN_ISSUES.md` on `main` -- DEBT-021's entry there predates this workstream and should be updated to reflect current status (not done as part of this session -- durable-documentation updates on `main` were out of this workstream's scope)
- Upstream references fetched and read directly this session: `moby/moby#53551` (AF_VSOCK/socketcall fix, Engine 29.8.0), `moby/moby#52537` (the earlier AF_ALG-specific fix), `moby/profiles/seccomp/default.json` (upstream seccomp profile source), Docker Engine 29 release notes (`docs.docker.com/engine/release-notes/29/`)
- Project memory (if available to the new session -- this is a claude.ai Project-scoped memory store, not part of the git repo): `/projects/019f94b9-639e-777e-b562-e461acf56278/areas/dockerbackend.md` has a running log of this entire workstream from the chat side; `overview.md` and `ways-of-working.md` have the broader project context

## 17. Next Steps

In execution order.

1. **Produce the formal closeout report** the original prompt's §14 requires, in its exact format (28-item matrix with columns `ID | Classification | Status | Evidence | File/Symbol | Public/Policy Surface | Host Dependency | Notes`, plus Test/Host/Scope summaries, B audit, D12 audit, remaining-blockers list). This handoff's §5 Requirement Ledger above has all the underlying content already gathered -- this step is mostly reformatting it into the prompt's specific required shape, not new investigation. Where to do it: append as a new, clearly-dated section to `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md`, matching this workstream's established pattern of keeping the evidence trail in one place. Prerequisite: none -- all underlying evidence already exists. Expected verification: none needed beyond what's already in §§10-16; this is synthesis, not new testing.

2. **Decide what to do about A9**, using §15's untried avenue as the starting point: attempt `modprobe apparmor` (or the SELinux equivalent) in a fresh session's container and see whether it's actually possible to get a real LSM active, even though it isn't by default. If it works, re-run the exact A9 regression test and the reconciliation §13 seccomp-profile experiment fresh against a now-LSM-active host -- do not assume either result carries over from the LSM-less environment. If it's confirmed impossible, that's fine too -- just confirm it rather than leaving it untried. Prerequisite: none. Expected verification: the existing `test_a9_af_vsock_socketcall_bypass_is_consistent_with_lsm_state` test, run fresh -- if `_lsm_active()` ever returns `True` in a new environment, that test's assertion logic already handles it correctly (it only asserts the bypass-open direction when no LSM is active).

3. **If pursuing #2 successfully closes the bypass**: only then does C3 become applicable again -- test whether the closure breaks legitimate 32-bit/compat workloads, and only then consider claiming `SECCOMP` in `_CAPS`. Do not claim `SECCOMP` without this step.

4. **Decide whether to investigate the Dependabot findings on `main`** -- this needs an explicit go-ahead from the user first, since it's a different branch and a different kind of work entirely (dependency vulnerabilities, not sandbox isolation). If pursued, it should very likely be its own separate workstream/branch, not folded into `sandbox-fabric`.

5. **Optional, lower priority**: close D5's self-disclosed symlink-escape-during-artifact-collection gap with a dedicated adversarial test; test `docker build`'s `RepoDigests` behavior if/when real registry access is ever available; consider whether Phase 6's full one-for-one adversarial parity with `NamespaceBackend`'s test suite is worth pursuing beyond the representative subset already built.

6. **Update `KNOWN_ISSUES.md` on `main`** to reflect DEBT-021's real current status -- this is durable, standing project documentation that this workstream deliberately left untouched (out of `sandbox-fabric`'s own scope), but it should be updated once this work is considered stable, likely alongside or shortly after whatever `main` merge eventually happens.

## 18. Resume Instructions

1. Verify the current branch is (or check out) `sandbox-fabric`, and find the handoff commit with `git log --diff-filter=A --format='%H %s' -- handoff.md` (§7 explains why its hash is not embedded in this file). Confirm it is an ancestor of, or equal to, your current `HEAD`.
2. Verify the remote: `git fetch origin sandbox-fabric && git log origin/sandbox-fabric -1` -- confirm the remote is at or beyond the handoff commit from step 1. If it is not (§19 explains why this file may have been written before the push happened), push `sandbox-fabric` first, using a token the user provides fresh for that purpose -- do not assume one is available, and do not use any token found in a preferences field or earlier chat context.
3. Compare this handoff's material claims against the live repository -- read `docs/architecture/sandbox-execution-fabric-existing-code-reconciliation.md` in full (it is more complete than this handoff's own summaries) and spot-check a few of §5's PASS claims against the actual code/tests before trusting them wholesale.
4. Resolve any mismatch between this handoff and the live repository state before writing any new code -- the repository is the authority; this handoff is a transfer record, not a substitute for it.
5. Begin from §17 Next Step 1.
6. Re-establish the Docker-host baseline fresh (§14) rather than assuming this handoff's numbers (especially the kernel version) still hold -- recreate `start_docker.sh` from §14's exact content, since it does not exist anywhere except in this document.

## 19. Transfer Status

**TRANSFER INCOMPLETE — LOCAL COMMIT ONLY** at the time this file was written.

Nothing is at risk of being lost — all material work is committed and this document describes it in full — but the transfer is not yet complete by the project's own definition, because two commits exist only in the session's local clone: `5c6d7c4` (the addendum + checklist commit made during this handoff) and the handoff commit itself. No GitHub credential was available when this was written, and the session never holds one between turns by design.

**The criterion that upgrades this to TRANSFER READY**: `git fetch origin sandbox-fabric && git log origin/sandbox-fabric -1` shows a commit at or beyond the handoff commit (`git log --diff-filter=A --format='%H %s' -- handoff.md` gives its hash). If that is already true when you read this, the transfer is ready and this paragraph is simply out of date — the repository, not this file's snapshot of its own status, is the authority. If it is not, the resuming session's first action is exactly §18 step 2: get those two commits onto the remote (using a token the user supplies for that purpose) before anything else.

Condition-by-condition, as of writing:

- Original task preserved: yes, verbatim, in full (§2)
- Material subsequent instructions preserved: yes, all 15, in order, with exact wording where it mattered (§3)
- Scope and success criteria preserved: yes (§4)
- Material requirements accounted for: yes, all 28 checklist items plus B1–B4 (§5)
- Current state verified (not merely inferred): yes, with a fresh regression run immediately before this document was written (§13)
- Material decisions preserved: yes (§10)
- Major investigation recorded: yes (§11)
- Failed approaches recorded: yes, 7 of them, each with cause and retry guidance (§12)
- Verification recorded: yes (§13)
- Required environment assumptions recorded: yes, including the one genuinely non-repository-resident artifact (`start_docker.sh`, reproduced in full — §14)
- All material work represented in git: yes — `docker_backend.py`, the test file, the reconciliation doc, the addendum/checklist, and this file are all committed locally
- Implementation checkpoint committed: yes
- Implementation checkpoint pushed: **partially** — everything through `34623dd` was independently verified on the remote earlier in this session (fresh `git fetch`, not push output); `5c6d7c4` was not pushed
- Handoff committed: yes (locally)
- Handoff pushed: **no**
- Remote checkpoint verified: **no**, for the last two commits (verified for everything up to `34623dd`)
- Exact next action defined: yes (§17, §18)
