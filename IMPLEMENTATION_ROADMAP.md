# OCBrain — Implementation Roadmap

**Last synchronized:** Aug 29, 2026 (ADR-KERNEL-01 — both Kernel v1.0 freeze blockers from the Canonical Kernel Completion Plan resolved same day: `root_operation_id`/`attempt_id` identity threading, and completion of the `WorkerContext`→`ExecutionContext` migration ADR-001 had declared but never finished. See `CURRENT_STATE.md` and `docs/architecture/decisions/ADR_KERNEL_01_ROOT_OPERATION_IDENTITY_AND_EXECUTION_CONTEXT_MIGRATION.md` for full detail. 1,343 passed / 34 failed, zero regressions; prior sync Aug 27, 2026 (added the Execution Reliability Track section — watchdog/execution-budget baseline merged from `feature/execution-progress-inspection`, orthogonal to and not gating/gated-by the Cognitive Front-End Phase below; see `KNOWN_ISSUES.md` DEBT-015/DEBT-016; prior sync Aug 22, 2026 K4.2-H2-D10 integrated, H2 formally closed after the independent audit's single blocker was resolved; prior sync Aug 22, 2026 K4.2-H2 complete — D3/D7/D11/D12 all merged, plus the out-of-band ADR-K4.2-H-13 fix; prior sync Aug 18, 2026 K4.2-H2 D10 pre-H2 drift baseline capability built and captured; D3/D7/D11/D12 set up for four-way parallel zero-contact Claude implementation — see `docs/architecture/h2_packets/README.md`; prior sync Aug 17, 2026 K4.2-H1 FROZEN — independent freeze review passed all 16 gates, Moncif signed off; H2 entry gate satisfied, H2 not yet started — see `docs/Bugs Hunt & fix reports/K4_2_H1_FINAL_FREEZE_REVIEW.md`; prior sync Aug 16, 2026 added K4.2-H1 — Contract Evolution Foundation; prior sync July 30, 2026 added Packet 09 — all 9 packets now complete, see note below; prior sync same day added Packet 08; prior sync same day added missing K4.2.6/K4.2.7 rows and Packet 07; prior sync July 29, 2026 corrected K4.2.4/K4.2.5 and added Plan Compilation; prior sync July 24, 2026 added the Cognitive Front-End Phase for K4.2.1–K4.2.3; prior sync July 22, 2026 K3 status correction; prior full sync July 18, 2026)
**Authority:** This is the living roadmap. The roadmap in `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §23 is frozen and reflects the plan as it existed at architecture freeze; this document reflects actual completion.

---

## Architecture Phase — ✅ Complete

| Milestone | Status | Deliverable |
|---|---|---|
| K1 — Kernel Runtime Audit | ✅ Complete | `OCBRAIN_K1_KERNEL_AUDIT_AND_SPECIFICATION.md` |
| K1.5 — Kernel API & Service Model | ✅ Complete | `OCBRAIN_K1.5_KERNEL_API_SERVICE_MODEL.md` |
| K1.6 — Resource Model | ✅ Complete | `OCBRAIN_K1.6_RESOURCE_MODEL.md` |
| K1.7–K1.11 — Architecture Freeze | ✅ Complete | `OCBRAIN_K1.7-K1.11_FINAL_ARCHITECTURE_FREEZE.md` |
| K4 — Contract Freeze | ✅ Complete | Implicit in K1.7–K1.11 |

---

## Implementation Phase — ✅ Complete

| Milestone | Status | Key Deliverables |
|---|---|---|
| K2.1 — Execution Runtime | ✅ Complete | `ExecutionRuntime`, `ExecutionContext`, `CancellationToken`, `WorkingMemory`, `WorkerRegistry`, `PlannerWorker` |
| K2.2 — Workflow Runtime | ✅ Complete | `WorkflowRuntime`, `WorkflowDefinition`, DAG execution, retrieval cutover |
| K2.3 — Capability Runtime | ✅ Complete | `CapabilityRegistry`, `AdapterRuntime`, `Adapter` Protocol, 3 concrete adapters |
| K2.4 — Governance Completion | ✅ Complete | `OrchestrationGovernor`, `AgentGovernor`, `ConversationGuardrails`, `MemoryGovernor` reconciled |

Completion reports:
- `K2_2_CUTOVER_REPORT.md` — WorkflowRuntime wiring
- `docs/reports/K2_2_RETRIEVAL_CUTOVER_REPORT.md` — Retrieval Runtime cutover
- `docs/reports/K2_4_GOVERNANCE_IMPLEMENTATION_REPORT.md` — Governance completion

---

## Kernel Hardening Phase — ✅ Complete

Consistency hardening on the already-complete Implementation Phase, addressing gaps DEBT-001 and (once-implicit) update/delete governance identified in `KNOWN_ISSUES.md`. Not a new architectural phase — no new subsystems, no public API changes.

| Milestone | Status | Key Deliverables |
|---|---|---|
| K3.5 — Governance Wiring (`write()`) | ✅ Complete | `UnifiedMemory.write()` calls `GovernanceKernel.evaluate_action()` before any mutation. `ADR-K3.5-01` (EventStream vs EventBus boundary). Resolves DEBT-001 for the write path. |
| K3.5.1 — Governance Consistency (`update()`, `delete()`) | ✅ Complete | `UnifiedMemory.update()` and `delete()` now call `evaluate_action()` before any mutation, using the identical pattern K3.5 established for `write()` (`memory_update` / `memory_delete` action types, matching reject/escalate event emission). Closes the last unguarded persistent-mutation entry points in `UnifiedMemory`. |

**Invariant established:** no persistent state mutation inside `UnifiedMemory` (`write`, `update`, `delete`) bypasses `GovernanceKernel`. `search()` and `read()` remain intentionally exempt (read-only, no state mutation).

**Scope note:** this closes the *structural* governance-bypass gap — every mutation now enters the same evaluation chain. It does not add new content-validation logic: `MemoryGovernor`'s confidence/growth-limit checks remain scoped to `memory_write` by its own existing design (see `CURRENT_STATE.md` Governance section). Extending `MemoryGovernor` to validate update/delete content specifically was not in scope for this hardening pass and was not attempted.

---

## Validation Phase — ✅ Complete

| Milestone | Status | Purpose |
|---|---|---|
| K3 — Kernel Compliance Audit | ✅ Complete | Verify implementation against Constitution and Architecture spec |

**Resolution (July 22, 2026):** This section previously marked K3 as `⬜ Next` and declined to adopt `docs/reports/K3.5 — Kernel Hardening Report (Final).md`'s certification framing, pending resolution of the tension recorded below. Confirmed by the project owner: K3 was performed — K3.5 and K3.5.1 are its remediation, not a parallel or preceding effort. Git history corroborates: `bebce09 ocbrain k3 audit` precedes `46f550c k3.5 hardening session` and `236e687 K3.5.1: Kernel governance consistency (update/delete) + write() event-emission fix`. This document's status line simply hadn't been updated. The Constitution law-count prerequisite below is resolved separately, same date — see `KNOWN_ISSUES.md` DEBT-009.

**Prerequisites for K3 (historical — all now satisfied):**
- ✅ Documentation synchronized with implementation
- ✅ All K2 sub-phases verified complete
- ✅ Constitution law count consistent across all documents — the `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §3.1 and `core/capabilities/resource.py` gaps flagged here are now corrected (`DEBT-009`, resolved); Constitution confirmed 9 laws / 9 invariants, project-wide.
- ✅ Navigation documents created for auditor entry
- ✅ Kernel Hardening Phase complete (write/update/delete governance consistency)

**Historical record, kept verbatim rather than deleted** — consistent with this project's own discipline of recording tensions rather than silently harmonizing them:

> **Note on certification claims (as originally written, July 18, 2026):** `docs/reports/K3.5 — Kernel Hardening Report (Final).md` states "UNCONDITIONAL KERNEL v1.0 CERTIFICATION" and frames the Kernel as ready for K4. This document does not adopt that framing. K3 (Kernel Compliance Audit) — the mechanism this project's own roadmap defines for determining Kernel-complete status — has not been performed, per this document's own tracking above. The certification claim rests partly on BudgetGovernor being fully operational; direct verification (July 18, 2026 Reality Synchronization pass) found the evaluation mechanism correct but currently unreachable in production, since nothing accumulates real step/token usage (`KNOWN_ISSUES.md` DEBT-007 — still open, unaffected by K3's resolution). This tension between the K3.5 report and this document is recorded here for explicit resolution, not silently harmonized in either direction.
>
> **Note (as originally written, July 18, 2026):** K3 (Kernel Compliance Audit) has not yet been performed and remains the outstanding gate before Cognitive Phase work begins. Kernel Hardening Phase completion strengthens the case for K3, but does not substitute for it — several unrelated debt items remain open (see `KNOWN_ISSUES.md`: DEBT-002 AgentGovernor delegation dormancy, DEBT-003 checkpoint/resume, DEBT-004/DEBT-005 event-mechanism fragmentation, DEBT-006 L2 volatility, DEBT-007 BudgetGovernor accumulation gap, DEBT-008 EventStream test coverage, DEBT-009 Constitution amendment propagation). This document does not declare Kernel closure; K3 is the mechanism for that determination.

**Current status (July 22, 2026):** DEBT-001 and DEBT-009 are resolved. DEBT-002 through DEBT-008 remain open, tracked debt — independent of K3, not gating it. K3's completion means the compliance-audit milestone occurred and its findings were remediated; it does not mean the codebase has zero remaining gaps.

---

## Cognitive Front-End Phase — ✅ Complete

**Added July 24, 2026.** This phase did not previously appear in this document — K4.2.1 and K4.2.2 had already been implemented, and K4.2.3 was implemented in a prior session but uploaded rather than committed through the packet process, so none of the three were ever reflected here. Corrected via direct code + test audit (see `CURRENT_STATE.md`'s new Cognitive Front-End section and `docs/architecture/k4_2_3_completion_report.md`). **Updated July 29, 2026** — K4.2.4/K4.2.5 and Plan Compilation (Packet 06) corrected/added. **Updated July 30, 2026** — K4.2.6 and K4.2.7 (Packets 04, 05 — completed by a separate parallel session, merged in via `git merge`/fast-forward, never previously added to this document even though `IMPLEMENTATION_TRACKER.md` had them) are added, and Reflection + Evaluation (Packet 07) completes this phase's sequential/dependency chain up through Packet 07. Re-verified via direct code + full test-suite audit (1048/1048 passing) before correcting.

| Milestone | Status | Key Deliverables |
|---|---|---|
| K4.2.1 — Intent Interpreter | ✅ Complete | `Intent`, `IntentHypothesis` dataclasses; input normalization; multi-hypothesis inference |
| K4.2.2 — Goal Formation | ✅ Complete | `Goal` dataclass; compound-request splitting; `interpret_request()` entrypoint |
| K4.2.3 — Constraint Extraction + Planner Contracts | ✅ Complete | `Constraint`/`PlannerRequest`/`PlannerHint`/`PlannerResult`; `_extract_constraints()`; `cognitive.constraints_extracted`; `rejected_precheck` on contradictory hard constraints |
| K4.2.4 — Capability Discovery | ✅ Complete | `CapabilityDiscoveryRequest`, `discover_capabilities()`; description-overlap ranking over existing `list_capabilities`/`get_contract`/`get_adapters` — no `CapabilityRegistry.resolve()` API exists or was added, see `k4_2_4_completion_report.md` |
| K4.2.5 — Planner Completion | ✅ Complete | `ClarificationPolicy`, `ExecutionPlanLifecycle`, `PlanStep`, `ExecutionPlan`; decomposition/sequencing/fallback-path/confidence/impasse pipeline; `plan()` entrypoint |
| Plan Compilation (Packet 06 — K4 §6/§15, K4.2 §1) | ✅ Complete | `CompilationResult`, `compile()` entrypoint; `plan_compile` governance gate reusing `AbstractCognitiveWorker.execute()`'s pattern; `ExecutionPlan` → `WorkflowDefinition` mapping |
| K4.2.6 — Shared ValidationGate + Learning Wiring | ✅ Complete | `LearningTier`, `ContentDomain`, `CognitiveDecision`, `LearningRecord`, `validation_gate()` (`core/cognitive/learning.py`) |
| K4.2.7 — User Cognitive Model | ✅ Complete | `UserCognitiveModelProjection`, `assemble_user_cognitive_model()` (`core/cognitive/user_model.py`) |
| Reflection + Evaluation Workers (Packet 07 — K4 §7/§8) | ✅ Complete | `EvaluatorWorker`/`EvaluationRecord` (`core/workers/evaluator.py`); `ReflectionWorker` (`core/workers/reflection.py`); reflections stored as `KnowledgeEntry`, not a new type (K4 §7) |
| Supervisor Worker (Packet 08 — K4 §9) | ✅ Complete | `SupervisorWorker`/`SupervisorOutcome` (`core/workers/supervisor.py`); reacts to `CompilationResult` REJECT/ESCALATE (never retries, invariant 9) and retries failed invocations via `ExecutionRuntime.invoke()`; no governance authority of its own |
| Integration: Full Cognitive Pipeline (Packet 09) | ✅ Complete | `tests/test_integration_full_pipeline.py` — end-to-end `raw_text → interpret() → plan() → compile()`, real objects; full event trail verified complete and replayable; all 9 K4 §16 invariants verified; one genuine pre-existing bug found and fixed in `plan()` (see `packet_09_integration_completion_report.md`) |
| K4.2-H1 — Contract Evolution Foundation (D1/D2/D4/D5/D6/D8/D9) | ✅ **FROZEN** (Aug 17, 2026) | K42-001/K42-002 fixed; `CapabilityMatch`/`CapabilityDiscoveryResult`; `OperationRecoveryBudget` (`core/cognitive/recovery.py`, new); `trace_id`/`operation_id`/`stage_tag`; `caused_by` provenance. See `docs/architecture/decisions/ADR_K4_2_H_0{1,2,4,5,6,8,9}_*.md` and `docs/Bugs Hunt & fix reports/K4_2_H1_COMPLETION_REPORT.md`. Independently re-audited against all 16 freeze gates (zero regressions, zero blockers) in `docs/Bugs Hunt & fix reports/K4_2_H1_FINAL_FREEZE_REVIEW.md`; Moncif signed off Aug 17, 2026. Frozen contracts (not to be silently modified by H2): see that review's §15. |
| K4.2-H2 — Discrimination, Diagnostics, Tracking & Drift Enforcement (D3/D7/D10/D11/D12) | ✅ Complete (Aug 22, 2026) | Five packets (four zero-contact parallel — D3/D7/D11/D12 — plus D10, sequenced after since it needed their final shape). D3: capability-discrimination acceptance suite + one trivial, deterministic tie-break fix (`ADR_K4_2_H_03`). D7: verification-only closeout confirming H1's terminal-impasse diagnostic already worked — zero code change (`ADR_K4_2_H_07`). D11: `RawRequest.detected_language`, dependency-free heuristic (`ADR_K4_2_H_11`; see `KNOWN_ISSUES.md` DEBT-013 for the propagation gap the closing audit found). D12: D10 drift-tooling record + the `IMPLEMENTATION_TRACKER.md` existence correction (`ADR_K4_2_H_10`, `ADR_K4_2_H_12`). D10: the full DRIFT-10..15 enforcement layer + CI wiring (`ADR_K4_2_H_10`, extended; see `KNOWN_ISSUES.md` DEBT-014 for the Governance-boundary scope note the closing audit found). Plus `ADR_K4_2_H_13` (not one of the five packets — a live-debugging fix for a pre-existing `ClarificationPolicy` bug that predates H2). Closed via an independent audit (`docs/Bugs Hunt & fix reports/K4_2_H2_FINAL_INDEPENDENT_AUDIT.md`) that re-derived every claim from the repository fresh, ran real end-to-end pipeline scenarios, and adversarially validated D10 before finding its one blocker (D10 implemented but not yet merged) — resolved by this row's own completion. Full combined suite on the merged state: 34 failed / 1230 passed, the 34 confirmed byte-for-byte identical to the pre-H2 baseline. |

Completion reports: `docs/architecture/k4_2_1_completion_report.md` through `k4_2_7_completion_report.md`, `packet_06_plan_compilation_completion_report.md` through `packet_09_integration_completion_report.md`, `docs/Bugs Hunt & fix reports/K4_2_H1_COMPLETION_REPORT.md`.

K4.2.1–K4.2.7, Plan Compilation, Reflection/Evaluation, and Supervision have zero live-path interaction with Kernel execution — `compile()` *produces* a `WorkflowDefinition` under governance, `EvaluatorWorker`/`ReflectionWorker` *read* whatever execution events already exist, and `SupervisorWorker` *reacts* to a `CompilationResult`/failed `WorkerResult` it is given, but nothing in the Cognitive Front-End invokes `WorkflowRuntime` or triggers any of these workers automatically after an execution — now proven, not merely claimed, to work correctly together end-to-end (Packet 09) — and none required K3 resolution to proceed, consistent with K3 having been separately confirmed complete above.

**This phase is complete.** All 9 packets (01–09) are done. See `docs/architecture/IMPLEMENTATION_TRACKER.md` for per-packet status, owners, and cross-packet dependencies — that document, not this section, is the authoritative packet-level tracker. Live wiring (`main.py` composition root, `WorkflowRuntime.execute()` automatic invocation, C-MoE capability selection) remains deliberately out of scope for this entire campaign, per `OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`'s own "Future Architectural Placeholders" scope statement — a future milestone, not tracked by Packets 01–09.

---

## Execution Reliability Track — Baseline Merged (Aug 27, 2026)

**Added Aug 27, 2026.** This is a separate track from the Cognitive Front-End Phase above and the Cognitive Phase below — it lives in `core/runtime/`, motivated by a real production bug (a flat 60s timeout killing long-form generation), not by any K4.2.x packet. It does not depend on Cognitive Front-End completion and Cognitive Front-End completion did not depend on it; the two are orthogonal.

Two sessions independently built overlapping `ExecutionBudget`/`ExecutionWatchdog`/`ProgressMonitor` implementations on `feature/execution-progress-inspection` (one informally labeled "K4.4" in its own report — not an official roadmap number, no such milestone appears elsewhere in this document). This session verified the branch fresh, fixed a genuine contract-mismatch bug between the two implementations (commit `7ca7f35`), re-ran the full test suite before and after (50/50 feature tests, 196/196 regression), and merged into `main` as a baseline.

**Merged and frozen:** configurable execution budget replacing the old flat timeout; watchdog/progress monitoring (in two still-unreconciled implementations — see `KNOWN_ISSUES.md` DEBT-016); SSE for long-running responses; the `use_k42_frontend` routing flag.

**Researched and proposed, not implemented:** stable operation identity across retries, `ExecutionAttempt`, `ExecutionSnapshot`, extended failure classification, a `RecoveryDecision` policy layer, checkpoint persistence, idempotency semantics. Full research (Temporal, LangGraph, Restate, and recent academic work, honestly sourced) and the proposed architecture are in `docs/reports/WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md`. Per this project's Architecture Freeze Principle, this should become its own ADR before implementation begins — tracked as `KNOWN_ISSUES.md` DEBT-015, explicitly deferred pending that review, not scheduled against any other phase's completion.

**Update, same day (Aug 27→28, 2026):** a separate, unreviewed direct-to-`main` upload (outside the normal branch/PR workflow — see `KNOWN_ISSUES.md`'s Aug 28 sync note for full provenance) flipped `use_k42_frontend` to `true`. **The K4.2 Cognitive Front-End is now the default execution path**, not merely feature-flagged for testing; the K2.2 `PlannerWorker` path is retained as LEGACY/COMPATIBILITY only. That same upload added `Goal.semantic_description` (richer capability-discovery signal), closed DEBT-013 (language-detection propagation), and — for the first time — wired `assemble_user_cognitive_model()`'s output into `PlannerHint`s reaching the orchestrator. Independently re-verified this session: 51 new tests pass, and the full suite (1,331 passed / 34 failed, all 34 the pre-existing `huggingface.co`-unreachable environment class) shows zero regressions from the flip.

---

## Canonical Kernel Completion Plan — Complete, Not Implemented (Aug 29, 2026)

**Supersedes the "Kernel Completion Study" entry below** (same day, morning session) — `docs/studies/OCBRAIN_KERNEL_COMPLETION_CANONICAL_PLAN.md` is now the canonical document for this question; the morning study remains as a dated evidence trail, all its findings re-confirmed rather than overturned.

**What's new:** a git-verified reconstruction of the original seven-milestone K4.1–K4.7 roadmap (`docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §19 — K4.1 Intent+Goal, K4.2 Planner/decomposition-only, **K4.3 Plan Compiler + Governance Gate**, **K4.4 Reflection/Evaluation read-only**, K4.5 Memory Integration, K4.6 Supervisor, K4.7 full-pipeline integration), traced against actual commit history packet-by-packet. Finding: no commit ever used any of these seven labels — packetization renamed everything to "K4.2.x" / "Packet 0N" — but five of seven milestones' *architectural substance* survived intact regardless (confirmed by direct code read: `planner.py` still never touches `compiler.py`; `compiler.py` still gates on `action_type="plan_compile"` exactly as the original `ADR-K4-04` intended, even though that ADR itself was never written). The one pair that didn't survive as originally sequenced — K4.4 shipping read-only before K4.5 added governed writes — turned out not to matter: `UnifiedMemory.write()` was already governed (K3.5) by the time Packet 07 built both concerns together, so the safety property the sequencing was meant to guarantee held anyway, just via different timing than planned.

**Freeze verdict unchanged: NOT_FREEZE_READY**, same two blockers as this morning and as the Aug 22–23 audit before it (Scope/identity linkage, ADR-001 vs. `WorkerContext`), independently re-confirmed unchanged a third time. See the canonical document's §38 for the single recommended next step.

---

## Kernel Completion Study — Complete, Not Implemented (Aug 29, 2026, morning)

**Correction to the previous day's entry, below this one and left intact rather than deleted, per this project's own "surface discrepancies explicitly" discipline:** the "K4.3 Research Phase" entry recorded on Aug 28 accepted a governing prompt's premise that "K4.3 = C-MoE" — a milestone name that does not exist in this document, `CURRENT_STATE.md`, or any other authoritative source. `docs/studies/OCBRAIN_KERNEL_COMPLETION_STUDY.md` reconstructs the actual Kernel v1.0 state instead of continuing to build on that premise, reconciling five prior fresh-clone freeze audits (Jul 14 – Aug 23) that this project had already produced but never consolidated into one answer.

**Headline finding: Kernel v1.0 is NOT_FREEZE_READY, blocked on exactly the same two decisions its most recent prior audit (Aug 22–23) identified a week ago — independently re-verified this session, unchanged:**
1. What "Scope" means for Kernel v1.0, and whether `WorkflowNode`/`WorkflowDefinition` should carry a link back to `operation_id` (they currently do not — confirmed by direct grep, twice, one week apart).
2. Embedded ADR-001 ("`WorkerContext` is deprecated") vs. the actual code (all seven worker classes still take `WorkerContext` — confirmed by direct grep this session).

Both are decisions requiring Moncif's call, not further research or implementation — see the study's §25 for the single recommended next step. C-MoE, correctly, is repositioned as **post-Kernel-freeze** work throughout — the two studies renamed below (they no longer claim to be "K4.3") remain valid research on what C-MoE should look like once Kernel v1.0 is actually frozen, not on when it happens relative to K4.2.

---

## C-MoE Cognitive Runtime Research — Complete, Not Implemented (Aug 28, 2026; corrected Aug 29)

`docs/studies/OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md` (100-section architecture proposal, renamed from `..._K4_3_...` — see its own correction note) and its companion `docs/studies/OCBRAIN_CMOE_REALITY_GROUNDING_SUBSTUDY.md` reconcile this project's prior unpublished internal research (`docs/architecture/future_debt_study/OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md` and `OCBRAIN_RELIABILITY_DURABLE_EXECUTION_ARCHITECTURE_STUDY.md`) against the current codebase and fresh external research, and define what C-MoE should be — **once Kernel v1.0 is frozen, per the Kernel Completion Study above, not as the immediate next milestone.** Research and architecture proposal only — no implementation.

Headline findings, unchanged in substance, now correctly sequenced: (1) the `WorkflowNode` → worker dispatch path only works because exactly one `capability_type` is registered anywhere in the system — the Kernel Completion Study independently reached the same finding and treats it as a Kernel-completion item (§8/§21 there), not a C-MoE-specific one; (2) a primitive plan-reality-feedback loop already exists (`ExecutionPlan.caused_by` + `cognitive.planner_impasse`) and should be generalized, not reinvented; (3) Project/Discussion and a four-scope memory model are modeled as Application-layer concepts over the Kernel's Scope primitive, never new Kernel primitives; (4) a companion sub-study concluded C-MoE should ground Planner in a thin, conditional, facts-only reality check before planning, plus a feasibility pass reusing C-MoE's own eligibility logic — explicitly rejecting both an iterative dialogue and a new standing "Reality Layer" component.

---

## Cognitive Phase — Future (Post-Kernel)

These items are beyond Kernel scope. They build ON the kernel, not AS the kernel. (K4.2.1–K4.2.5 and Plan Compilation are no longer listed here — see the Cognitive Front-End Phase above. `Planner.plan()`/decomposition (K4.2.5) and Plan Compilation (Packet 06) are complete; capability *selection* specifically — resolving a `capability_type` to a concrete registered adapter, as opposed to the discovery/ranking K4.2.4 already does — remains future work below, reserved for the Cognitive Runtime, itself gated on Kernel v1.0 freeze per the Kernel Completion Study above.)

- Self-Identity Model
- Reflection Engine
- Cognitive Runtime (C-MoE) — architecture proposed, not implemented, gated on Kernel v1.0 freeze; see `docs/studies/OCBRAIN_KERNEL_COMPLETION_STUDY.md` for freeze status and `docs/studies/OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md` for the full design (routing, WorkGraph, outcome contract)
- Skills Runtime
- External Knowledge Pipeline
- Multi-Agent Runtime (SupervisorWorker)
- Advanced GraphRAG/KAG
- Provenance Completion
- Web UI
- Developer Platform
- Additional Cognitive Workers (ReflectionWorker, EvaluatorWorker, CoderWorker, BrowserWorker)
- Additional Capability Types (Embedding, Web Search, Browser Automation, etc.)

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the distinction between active debt and future roadmap.

**Note (Aug 22, 2026, K4.2-H2 integration):** no `K4.2-H3` (or equivalent) packet brief, readiness plan, or ownership manifest exists anywhere in this repository as of this sync — recorded explicitly rather than left silently implied, matching this document's own standing discipline of stating what's confirmed rather than what's assumed. The items above remain the long-term future list; nothing currently scopes which of them (if any) H3 would tackle first.

---

*This document is the living roadmap. Update it when phases complete or new phases are defined.*
