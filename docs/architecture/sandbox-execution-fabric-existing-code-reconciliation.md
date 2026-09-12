# Sandbox / Execution Fabric — Existing-Code Reconciliation

**Status:** Reconciliation complete. Ready to inform a revised kickoff prompt (report §15) for Phase 1 implementation.
**Date:** September 11, 2026
**Scope:** Read/reconcile pass triggered by `docs/research/sandbox-execution-fabric/deep-research-report.md` (external deep-research report on sandbox/execution-fabric design; fact-checked and corrected for 5 errors prior to this pass — see §1). Corresponds to the report's own §3 ("l'état de l'hôte/du dépôt") existing-code check, performed here against the live repository rather than deferred into Phase 1 implementation.
**Method:** Fresh read of `main` (this branch's base). Documentation-first per `PROJECT_INSTRUCTIONS.md` §18.4.1: `CURRENT_STATE.md`, `KNOWN_ISSUES.md`, `IMPLEMENTATION_ROADMAP.md` checked for sandbox/execution/watchdog/validationgate mentions before touching source. Targeted full reads (not class-name grep alone) of `core/runtime/`, `core/capabilities/`, `core/cognitive/learning.py`, `core/skills/skill_interface.py`, `modules/system_ctrl/module.py`, `modules/coding/module.py`, `core/events/event_stream.py`, `core/workers/`. No runtime code touched — this is a design/reconciliation pass only, per the Architecture Freeze Principle.

---

## 1. Corrections applied to the source report

Five factual errors, checked against primary sources and corrected in place in `docs/research/sandbox-execution-fabric/deep-research-report.md` (this same commit):

1. **nsjail license:** MIT → Apache-2.0 (narrative mention and comparison-table row both fixed).
2. **nsjail "dernier commit 2021" / reduced-maintenance claim:** unsupported — the repo shows discussion activity into 2025–2026 — removed and replaced.
3. **Firecracker device count:** "5 devices" is contested even within Firecracker's own materials (main site says 5, the repo's own FAQ says 6, having added `virtio-balloon`). Both mentions updated to reflect the discrepancy rather than assert a single stale number.
4. **OpenHands/Sysbox row:** corrected a license conflation — OpenHands itself is open-source; the proprietary tier is Sysbox Enterprise Edition, which is itself reportedly being discontinued as a standalone product in favor of the open Community Edition.
5. **Daytona:** removed an unexplained, unsupported "(mobile)" tag; added the independently-verified June 2026 closed-source transition, since the report's "Proprietary" table classification is correct but recent, and worth dating.

## 2. What already exists — inventory against the report's proposed contracts

Legend: **Extend** = build on top of this · **Reuse philosophy** = same approach, new implementation · **Publish through** = route new events here · **Collision risk** = no functional overlap but name is contested · **Greenfield** = nothing exists.

| Report proposes | Closest existing thing | Where | Verdict |
|---|---|---|---|
| `SandboxPolicy` / `RuntimeCapabilities` (timeout, memory, import restrictions) | `SkillExecutionConfig` — `mode` (default `"inline"`), `timeout_sec`, `memory_limit_mb`, `allowed_imports` | `core/skills/skill_interface.py:24` | **Extend.** Declared on skill metadata; confirmed by repo-wide grep to be read nowhere else — a real but currently inert rudiment, not a false lead. |
| Deny-by-default execution / admission | Action allowlist (`ACTION_HANDLERS`) + path jail (`SAFE_ROOT` / `_safe_path()`) | `modules/system_ctrl/module.py` | **Reuse philosophy, not code.** Same-process jail, not container/VM isolation — the report's own threat model already goes further. Has one documented, fixed vulnerability class (shell-injection, "A7 audit fix") worth reading before designing the new admission chain — same failure mode is easy to reintroduce. |
| `ExecutionEvent` | `EventStream` — the event-sourced backbone | `core/events/event_stream.py` | **Publish through.** Almost certainly what the report's own placeholder term "Event Backbone" (§3) was gesturing at without knowing the real name. No case found for a second, parallel event system. |
| `ExecutionRequest` / `ExecutionHandle` / `ExecutionResult` | `ExecutionContext`, `ExecutionRuntime`, `ExecutionOutcome`, `ExecutionBudget`, `ExecutionPolicy`, `ExecutionWatchdog` / `GraphExecutionWatchdog`, `ExecutionGraph`, `ExecutionNode`, `ExecutionRegistry` | `core/runtime/*.py` | **Collision risk — no functional overlap.** This family invokes in-process `Worker` objects for workflow orchestration (`ExecutionRuntime`'s own docstring: "constructs and invokes one Worker for one unit of work"). Nothing to do with sandboxed code execution. Namespace decision in §3. |
| GitHub-sourced "capabilities" (SBOM/Sigstore admission chain) | `CapabilityRegistry`, `CapabilityRequest`, `CapabilityResult`, `CapabilityContract`, `CapabilityType`, plus planner-side `CapabilityDiscoveryRequest` / `CapabilityMatch` | `core/capabilities/`, `core/cognitive/planner.py` | **Collision risk — no functional overlap.** Existing usage is entirely about routing a request to a registered orchestration capability. Different concern, same word. Naming decision in §3. |
| Admission gate before execution | `validation_gate()` | `core/cognitive/learning.py:377` | **Collision risk — name is taken.** Gates learning/cognitive decisions through `GovernanceKernel.evaluate_action()`. Notably a single async function, not a class. |
| `ArtifactManifest` | `CognitiveArtifact` (Protocol) | `core/cognitive/intent.py:54` | **No real overlap** — different layer entirely, name proximity only. |
| Container/VM isolation backend (Docker/gVisor/Kata/Firecracker) | — | — | **Confirmed greenfield.** Zero hits for docker/firecracker/gvisor/kata/microvm anywhere in application code (`*.py`, excluding tests). |
| `CoderWorker` as a consumer | Not yet built | `KNOWN_ISSUES.md` still lists it under Future Cognitive Workers; absent from `core/workers/` | **No integration target exists yet.** Building the fabric ahead of its primary consumer is defensible (infrastructure before consumer), but it means Phase 1 can't be integration-tested against a real caller. |

## 3. Naming decisions

Recorded here so they aren't re-litigated per file during implementation:

- **New contracts live under a `Sandbox*` prefix, in a new `core/sandbox/` package — not `Execution*`.** `core/runtime/` already owns `Execution*` for workflow-node orchestration. Recommend `SandboxRequest` / `SandboxHandle` / `SandboxResult` / `SandboxEvent` in place of the report's `Execution*`-prefixed names. `SandboxPolicy` (the report's own name) survives unchanged — it doesn't collide, and it's the name that should eventually point at `SkillExecutionConfig`'s replacement/superset.
- **"Capability" is avoided for the GitHub-admission concept.** Recommend "extension" or "external package" (e.g. `ExtensionManifest` rather than an implicit `CapabilityManifest`) to keep distance from `core/capabilities/`'s existing, unrelated meaning.
- **"ValidationGate" is avoided.** Recommend `AdmissionGate` (or `SandboxAdmissionGate`) for whatever gates a `SandboxRequest` before execution.
- **"Sandbox" itself is kept, deliberately.** It's the report's central term, it's directionally correct (this genuinely is a stronger, different kind of sandbox than `system_ctrl`'s path jail), and avoiding it would fight the report's own vocabulary for no real benefit. The distinction from the existing lighter-weight sandbox should be one documented sentence in the new code's module docstring, not a renaming exercise.

## 4. Non-blocking observations

- The repository's actual current state is considerably busier than the report's own framing assumed: a Kernel v1.0 freeze audit is open (`NOT_FREEZE_READY`, pending a classification decision on DEBT-020), and a Context Engineering Security Audit has five unresolved regressions (DEBT-019). Neither blocks sandbox-fabric work; both are worth knowing about before assuming `main` is quiet.
- `core/runtime/watchdog_decision.py`'s recent unification (`ADR_KERNEL_02_WATCHDOG_UNIFICATION`, Sept 5 2026 — two independent Watchdog implementations collapsed into one shared, pure `decide()` function behind a `ProgressSignal` Protocol) is a useful precedent if the sandbox fabric ends up needing its own resource-limit watchdog: the same split (pure decision function + typed signal Protocol) rather than a third bespoke implementation.
- No tracking-doc sync (`CURRENT_STATE.md` / `KNOWN_ISSUES.md` / `IMPLEMENTATION_ROADMAP.md`) was performed as part of this reconciliation — those live on `main` and are out of scope for a `sandbox-fabric`-branch commit under this project's branch-per-layer discipline. Recommend a dedicated sync pass once Phase 1 actually lands.

## 5. Recommendation

Ready to fire an updated version of the report's §15 kickoff prompt, incorporating: the five corrections (§1), the namespace decision (`core/sandbox/`, `Sandbox*` prefix, §3), the two reuse targets (`SkillExecutionConfig`, `EventStream`, §2), and the two renamed concepts ("extension" instead of "capability"; `AdmissionGate` instead of `ValidationGate`). No blocker found that would delay Phase 1 (Docker/OCI backend, per the report's own plan).
