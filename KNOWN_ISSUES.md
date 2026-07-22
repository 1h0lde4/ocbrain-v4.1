# OCBrain — Known Issues & Technical Debt Register

**Last synchronized:** July 22, 2026 (DEBT-009 resolution; prior full sync July 18, 2026)
**Authority:** This is the canonical register of known technical debt, deferred items, and future work.

---

## Active Technical Debt

Items that represent genuine gaps in the current implementation. These should be addressed before or during K3.

| ID | Area | Issue | Severity | Impact |
|---|---|---|---|---|
| DEBT-002 | Governance | **AgentGovernor delegation dormancy** — `AgentGovernor` delegation permission matrix checks `metadata["delegating_worker_type"]`, but no worker currently populates this field. `SupervisorWorker` does not yet exist. The per-call cost ceiling check IS active. | Medium | Delegation permissions are unenforced until SupervisorWorker exists. |
| DEBT-003 | Workflow | **Checkpoint/resume not implemented** — `WorkflowRuntime` tracks node state in local dicts (never persisted). `EventStream.create_checkpoint()` exists but is never called by WorkflowRuntime. Long-running workflows cannot survive process restart. | Medium | No workflow durability across restarts. |
| DEBT-004 | Events | **KnowledgeEvent/EventStream duality** — Two separate event mechanisms exist: `KnowledgeEvent` (writes to L4 Archive via `ArchiveBackend.append_event()`) and `EventStream` (SQLite WAL, system-wide operational events). They record different facts about different concerns, but a consumer wanting a complete timeline must query both. Architecture research (FA §5.4) acknowledges this for future consolidation. | Low | No single unified audit trail. |
| DEBT-005 | Events | **EventBus/EventStream relationship** — `EventBus` (`core/event_bus.py`) provides in-process pub/sub with no persistence. `EventStream` provides durable, append-only events. Both exist; `ARCHITECTURE_CHANGELOG.md` documents their relationship ("EventBus subscribes to EventStream"). Three event mechanisms total (EventBus + EventStream + KnowledgeEvent). | Low | Event infrastructure fragmentation. |
| DEBT-006 | Memory | **L2 semantic memory loses embeddings on restart** — `InMemoryVectorBackend` is volatile. Embeddings are recomputed on startup from persisted entries. | Medium | Startup cost scales with entry count. |
| DEBT-007 | Governance | **BudgetGovernor accumulation gap** — `BudgetGovernor.evaluate()` correctly rejects when `action.metadata["step_count"]`/`["token_spend"]` exceed their thresholds, and K3.5 wired real propagation of a `budget` sub-dict from `ExecutionContext.metadata` through `AbstractCognitiveWorker.execute()` up to `Orchestrator.handle()`'s own `GovernanceAction`. But no code anywhere in the repository (confirmed by repo-wide search) increments `step_count`/`token_spend`/`budget["steps"]`/`budget["tokens"]` — every call site either initializes them to `0`/`0.0` (`execution_runtime.py`, `orchestrator.py`) or reads a metadata key nothing ever writes a nonzero value to. `WorkflowRuntime` does not reference budget fields at all. The evaluation mechanism is genuinely correct and would reject given real numbers (verified directly); the gap is that nothing currently produces real numbers, so the REJECT branch is unreachable in any current production path. | Medium | Step/token budgets are not actually enforced in practice, despite the governor being registered, evaluated on every action, and logically correct. |
| DEBT-008 | Tests | **EventStream has no dedicated test coverage** — no test file targets `EventStream`'s own behavior (`append()`, `replay()`, `create_checkpoint()`/`get_checkpoint()`, WAL persistence). It appears only as an incidental constructor dependency inside other subsystems' tests (`test_execution_runtime.py`, `test_workflow_runtime.py`, `test_planner_worker.py`, `test_capabilities.py`, `test_k2_2_runtime_migration.py`) via `get_event_stream()`, none of which exercise checkpoint/replay directly. A regression in checkpoint or replay logic specifically would not be caught by the existing suite. | Low | Silent regression risk in durability-critical event infrastructure. |
**Resolved (July 22, 2026):** ~~DEBT-009 — Constitution amendment propagated into a canonical spec and into code, without ratification~~. Confirmed by the project owner: the Constitution is 9 laws / 9 invariants, ratified; the Pressure Test's proposed 11-law/6-field diff was never adopted, and the two downstream artifacts assuming otherwise were simply stale, not evidence of a live ratification question. Corrected: `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §3.1's "two additional laws" table removed (it had also misattributed the two unratified laws to `PROJECT_INSTRUCTIONS.md`, which contains no such laws at all); `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md`'s precedence line corrected from "(11-law)" to "(9-law)"; `core/capabilities/resource.py`'s `HTTPClientResource` docstring corrected to stop citing a ratified six-field Invariant 4. Runtime behavior unaffected, as originally noted — only the citations were wrong, not the code's actual fields.

**Resolved (K3.5 / K3.5.1):** ~~DEBT-001 — MemoryGovernor dormancy~~. `UnifiedMemory.write()` (K3.5) and `update()`/`delete()` (K3.5.1) now all call `GovernanceKernel.evaluate_action()` before any state mutation. No persistent mutation entry point in `UnifiedMemory` bypasses governance. Note: this resolves the *structural* bypass only — `MemoryGovernor`'s own content-validation logic (confidence/growth-limit checks) remains scoped to `memory_write` by its own design; it does not independently validate update/delete content, and extending it to do so was not in scope for this hardening pass.

**Resolved (since the July 16, 2026 `FINAL_K3_READINESS_AUDIT.md`), for the record:** that audit's two "Mandatory before K3" items and several "Recommended" items are now resolved, confirmed by direct re-check this session (Reality Synchronization pass) — not by trusting any intervening report's own claim: `PRODUCT.md`'s capability table now correctly reads 7 governors / 2 worker subclasses; `README.md`/`CHANGELOG.md` no longer assert "11 laws"; `ARCHITECTURE_CHANGELOG.md`'s debt table now correctly marks the K2.1/K2.2/K2.4 findings "Resolved"/"Partially resolved" and its root/`docs/architecture/` duplication was resolved via a redirect stub (not by making the copies identical); its own Timeline no longer claims the Constitution was "later updated to 11 laws"; `K2_2_CUTOVER_REPORT.md` and `docs/reports/K2_2_RETRIEVAL_CUTOVER_REPORT.md` now cross-reference each other as companion reports; `CURRENT_STATE.md`/`KNOWN_ISSUES.md`/`IMPLEMENTATION_ROADMAP.md`/`PROJECT_INDEX.md` now exist. One item from that audit's evidence chain remained open longer than the rest and is carried forward precisely, not silently dropped: the Constitution law-count/Resource-Model question itself (DEBT-009, resolved July 22, 2026 — see above) — the *downstream prose claims* were fixed in this pass, but the canonical spec's own table (§3.1) and the Resource Model code needed a separate, later resolution.

---

## Deliberately Deferred Architecture

Items explicitly scoped out with architectural justification. These are NOT debt — they are intentional phase boundaries.

| Item | Rationale | Phase |
|---|---|---|
| Workflow checkpoint/resume persistence | Out of scope for K2.2 per session rules. EventStream checkpoint infrastructure exists; consumption deferred. | Post-K3 |
| AgentGovernor delegation wiring | Requires SupervisorWorker, which is Cognitive Phase work. | Cognitive Phase |
| KnowledgeEvent/EventStream merge | FA §5.4 identifies this; requires Memory Runtime redesign. | Post-K3 |
| ConversationGuardrails content policy | Default denylist is empty by design (permissive default, K2.4 risk mitigation). Content policy configuration is operational, not architectural. | Deployment |
| OrchestrationGovernor deny list | Default is permissive by design. Deny list configuration is operational. | Deployment |

---

## Future Roadmap (Not Debt)

Items that are correctly absent because they belong to future phases.

### Future Cognitive Workers

| Worker | Purpose | Phase |
|---|---|---|
| ReflectionWorker | Evaluate and critique the system's own outputs | Cognitive Phase |
| EvaluatorWorker | Score/grade outputs against criteria | Cognitive Phase |
| SupervisorWorker | Coordinate multiple sub-workers via ExecutionRuntime | Cognitive Phase |
| CoderWorker | Code generation, modification, analysis (sandboxed) | Cognitive Phase |
| BrowserWorker | Web browsing, content extraction | Cognitive Phase |

### Future Capability Types

| Capability | Status | Phase |
|---|---|---|
| `embedding` | Declared in `CapabilityType`, no adapter registered | Cognitive Phase |
| `web_search` | Declared, no adapter | Cognitive Phase |
| `browser_automation` | Declared, no adapter | Cognitive Phase |
| `file_access` | Declared, no adapter | Cognitive Phase |
| `memory_search` | Declared, no adapter | Cognitive Phase |
| `graph_traversal` | Declared, no adapter | Cognitive Phase |
| `image_generation` | Declared, no adapter | Cognitive Phase |
| `tool_invocation` | Declared, no adapter | Cognitive Phase |
| `external_api` | Declared, no adapter | Cognitive Phase |

### Future Architecture

- MCP-native tool integration
- Self-improvement under governance
- Advanced reranking (HyDE, cross-encoder)
- Durable workflow persistence
- Multi-agent coordination

---

*This document distinguishes between debt (gaps), deferred items (intentional), and future work (not yet started). Update it as items are resolved or new issues are discovered.*
