# OCBrain — Known Issues & Technical Debt Register

**Last synchronized:** July 2026 (post-K3.5.1 Kernel Hardening)
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

**Resolved (K3.5 / K3.5.1):** ~~DEBT-001 — MemoryGovernor dormancy~~. `UnifiedMemory.write()` (K3.5) and `update()`/`delete()` (K3.5.1) now all call `GovernanceKernel.evaluate_action()` before any state mutation. No persistent mutation entry point in `UnifiedMemory` bypasses governance. Note: this resolves the *structural* bypass only — `MemoryGovernor`'s own content-validation logic (confidence/growth-limit checks) remains scoped to `memory_write` by its own design; it does not independently validate update/delete content, and extending it to do so was not in scope for this hardening pass.

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
