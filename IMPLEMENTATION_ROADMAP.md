# OCBrain — Implementation Roadmap

**Last synchronized:** July 18, 2026 (Repository Reality Synchronization pass)
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

## Validation Phase — ⬜ Next

| Milestone | Status | Purpose |
|---|---|---|
| K3 — Kernel Compliance Audit | ⬜ Next | Verify implementation against Constitution and Architecture spec |

**Prerequisites for K3:**
- ✅ Documentation synchronized with implementation
- ✅ All K2 sub-phases verified complete
- ⚠️ Constitution law count consistent across all documents — **true for all living top-level documents** (`README.md`, `CHANGELOG.md`, `PRODUCT.md`, `ARCHITECTURE_CHANGELOG.md`, this document, `CURRENT_STATE.md` all correctly state nine laws; confirmed by direct re-check July 18, 2026), **not yet true for `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §3.1**, whose own law table numbers unratified laws as rows 10–11 without disambiguating them from the ratified nine, and not yet true for `core/capabilities/resource.py`'s Resource dataclasses, which implement a six-field shape assuming the same unratified amendment. See `KNOWN_ISSUES.md` DEBT-009.
- ✅ Navigation documents created for auditor entry
- ✅ Kernel Hardening Phase complete (write/update/delete governance consistency)

**Note on certification claims:** `docs/reports/K3.5 — Kernel Hardening Report (Final).md` states "UNCONDITIONAL KERNEL v1.0 CERTIFICATION" and frames the Kernel as ready for K4. This document does not adopt that framing. K3 (Kernel Compliance Audit) — the mechanism this project's own roadmap defines for determining Kernel-complete status — has not been performed, per this document's own tracking above. The certification claim rests partly on BudgetGovernor being fully operational; direct verification (July 18, 2026 Reality Synchronization pass) found the evaluation mechanism correct but currently unreachable in production, since nothing accumulates real step/token usage (`KNOWN_ISSUES.md` DEBT-007). This tension between the K3.5 report and this document is recorded here for explicit resolution, not silently harmonized in either direction.

**Note:** K3 (Kernel Compliance Audit) has not yet been performed and remains the outstanding gate before Cognitive Phase work begins. Kernel Hardening Phase completion strengthens the case for K3, but does not substitute for it — several unrelated debt items remain open (see `KNOWN_ISSUES.md`: DEBT-002 AgentGovernor delegation dormancy, DEBT-003 checkpoint/resume, DEBT-004/DEBT-005 event-mechanism fragmentation, DEBT-006 L2 volatility, DEBT-007 BudgetGovernor accumulation gap, DEBT-008 EventStream test coverage, DEBT-009 Constitution amendment propagation). This document does not declare Kernel closure; K3 is the mechanism for that determination.

---

## Cognitive Phase — Future (Post-Kernel)

These items are beyond Kernel scope. They build ON the kernel, not AS the kernel.

- Self-Identity Model
- Reflection Engine
- Planning Engine (full, beyond PlannerWorker)
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
