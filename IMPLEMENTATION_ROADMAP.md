# OCBrain — Implementation Roadmap

**Last synchronized:** July 30, 2026 (added missing K4.2.6/K4.2.7 rows and Packet 07 — see note below; prior sync July 29, 2026 corrected K4.2.4/K4.2.5 and added Plan Compilation; prior sync July 24, 2026 added the Cognitive Front-End Phase for K4.2.1–K4.2.3; prior sync July 22, 2026 K3 status correction; prior full sync July 18, 2026)
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

## Cognitive Front-End Phase — In Progress

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

Completion reports: `docs/architecture/k4_2_1_completion_report.md` through `k4_2_7_completion_report.md`, `packet_06_plan_compilation_completion_report.md`, `packet_07_reflection_evaluation_completion_report.md`.

K4.2.1–K4.2.7, Plan Compilation, and Reflection/Evaluation have zero live-path interaction with Kernel execution — `compile()` *produces* a `WorkflowDefinition` under governance and `EvaluatorWorker`/`ReflectionWorker` *read* whatever execution events already exist for a `workflow_id`, but nothing in the Cognitive Front-End invokes `WorkflowRuntime` or triggers Evaluator/Reflection automatically after an execution — and none required K3 resolution to proceed, consistent with K3 having been separately confirmed complete above.

**Remaining in this phase:** Packet 08 (Supervisor Worker, unblocked, depends on Packet 07), Packet 09 (Integration: Full Cognitive Pipeline, depends on all prior packets). See `docs/architecture/IMPLEMENTATION_TRACKER.md` for per-packet status, owners, and cross-packet dependencies — that document, not this section, is the authoritative packet-level tracker.

---

## Cognitive Phase — Future (Post-Kernel)

These items are beyond Kernel scope. They build ON the kernel, not AS the kernel. (K4.2.1–K4.2.5 and Plan Compilation are no longer listed here — see the Cognitive Front-End Phase above. `Planner.plan()`/decomposition (K4.2.5) and Plan Compilation (Packet 06) are complete; capability *selection* specifically — resolving a `capability_type` to a concrete registered adapter, as opposed to the discovery/ranking K4.2.4 already does — remains future work below, reserved for the Cognitive Runtime.)

- Self-Identity Model
- Reflection Engine
- Cognitive Runtime (C-MoE) — capability *selection*: resolving a `PlanStep.capability_type` (and the `WorkflowNode.worker_type` Plan Compilation carries forward unchanged) to a concrete registered `WorkerRegistry`/adapter entry
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

---

*This document is the living roadmap. Update it when phases complete or new phases are defined.*
