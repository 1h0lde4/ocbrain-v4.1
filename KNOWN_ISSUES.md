# OCBrain — Known Issues & Technical Debt Register

**Last synchronized:** Aug 16, 2026 (K4.2-H1 packet: added DEBT-011 tracking the ContentDomain/K4.1-L deferral explicitly per D6/ADR-K4.2-H-06; prior sync Aug 12, 2026 added DEBT-010, moved EvaluatorWorker/ReflectionWorker/SupervisorWorker out of Future Cognitive Workers since Packets 07/08 built them in July, resolved A6/A7 for real, resolved the K4.2 interaction-persistence gap; prior sync July 24, 2026 clarified Cognitive Front-End vs. future-worker scope; prior sync July 22, 2026 DEBT-009 resolution; prior full sync July 18, 2026)
**Authority:** This is the canonical register of known technical debt, deferred items, and future work.

---

## Active Technical Debt

Items that represent genuine gaps in the current implementation. These should be addressed before or during K3.

| ID | Area | Issue | Severity | Impact |
|---|---|---|---|---|
| DEBT-002 | Governance | **AgentGovernor delegation dormancy** — `AgentGovernor` delegation permission matrix checks `metadata["delegating_worker_type"]`, but no worker currently populates this field. **Correction (Aug 12, 2026):** `SupervisorWorker` now exists (Packet 08, July 30, 2026) and is composition-root-wired (Runtime Integration, Aug 8, 2026) — but it does not populate `delegating_worker_type` either (confirmed by direct grep of `core/workers/supervisor.py`: no reference to that key anywhere). The dormancy conclusion is unchanged; only the previous "SupervisorWorker does not yet exist" reason is now wrong and is corrected here. The per-call cost ceiling check IS active. | Medium | Delegation permissions remain unenforced — now because no worker populates the field, not because SupervisorWorker is missing. |
| DEBT-003 | Workflow | **Checkpoint/resume not implemented** — `WorkflowRuntime` tracks node state in local dicts (never persisted). `EventStream.create_checkpoint()` exists but is never called by WorkflowRuntime. Long-running workflows cannot survive process restart. | Medium | No workflow durability across restarts. |
| DEBT-004 | Events | **KnowledgeEvent/EventStream duality** — Two separate event mechanisms exist: `KnowledgeEvent` (writes to L4 Archive via `ArchiveBackend.append_event()`) and `EventStream` (SQLite WAL, system-wide operational events). They record different facts about different concerns, but a consumer wanting a complete timeline must query both. Architecture research (FA §5.4) acknowledges this for future consolidation. | Low | No single unified audit trail. |
| DEBT-005 | Events | **EventBus/EventStream relationship** — `EventBus` (`core/event_bus.py`) provides in-process pub/sub with no persistence. `EventStream` provides durable, append-only events. Both exist; `ARCHITECTURE_CHANGELOG.md` documents their relationship ("EventBus subscribes to EventStream"). Three event mechanisms total (EventBus + EventStream + KnowledgeEvent). | Low | Event infrastructure fragmentation. |
| DEBT-006 | Memory | **L2 semantic memory loses embeddings on restart** — `InMemoryVectorBackend` is volatile. Embeddings are recomputed on startup from persisted entries. | Medium | Startup cost scales with entry count. |
| DEBT-007 | Governance | **BudgetGovernor accumulation gap** — `BudgetGovernor.evaluate()` correctly rejects when `action.metadata["step_count"]`/`["token_spend"]` exceed their thresholds, and K3.5 wired real propagation of a `budget` sub-dict from `ExecutionContext.metadata` through `AbstractCognitiveWorker.execute()` up to `Orchestrator.handle()`'s own `GovernanceAction`. But no code anywhere in the repository (confirmed by repo-wide search) increments `step_count`/`token_spend`/`budget["steps"]`/`budget["tokens"]` — every call site either initializes them to `0`/`0.0` (`execution_runtime.py`, `orchestrator.py`) or reads a metadata key nothing ever writes a nonzero value to. `WorkflowRuntime` does not reference budget fields at all. The evaluation mechanism is genuinely correct and would reject given real numbers (verified directly); the gap is that nothing currently produces real numbers, so the REJECT branch is unreachable in any current production path. | Medium | Step/token budgets are not actually enforced in practice, despite the governor being registered, evaluated on every action, and logically correct. |
| DEBT-008 | Tests | **EventStream has no dedicated test coverage** — no test file targets `EventStream`'s own behavior (`append()`, `replay()`, `create_checkpoint()`/`get_checkpoint()`, WAL persistence). It appears only as an incidental constructor dependency inside other subsystems' tests (`test_execution_runtime.py`, `test_workflow_runtime.py`, `test_planner_worker.py`, `test_capabilities.py`, `test_k2_2_runtime_migration.py`) via `get_event_stream()`, none of which exercise checkpoint/replay directly. A regression in checkpoint or replay logic specifically would not be caught by the existing suite. | Low | Silent regression risk in durability-critical event infrastructure. |
| DEBT-010 | Config | **`Config`'s watcher thread races against `CONFIG_DIR` patching** — `Config._start_watcher()`'s background thread calls `_load_all()`, which does a fresh module-level `CONFIG_DIR` lookup on every read. On a freshly-constructed `Config()`, the watcher's first loop iteration always fires (empty `mtimes` dict) and reads all 5 tracked files individually, each call releasing the GIL. If a test does `with patch("core.config.CONFIG_DIR", tmp_path): Config()` and that burst hasn't finished by the time the `with` block exits, the tail end of the burst reads with the *reverted* `CONFIG_DIR` — or, if the burst runs entirely inside the patch window but a *different* `Config()` instance's watcher thread (e.g. the module-level singleton, already running) happens to fire mid-window, it reads with the *patched* value instead, corrupting that instance's `_settings`/`_models`. Discovered incidentally (not by design) while verifying DEBT-010's neighbor A6 fix: `tests/test_audit_fixes.py::TestA6ConfigWrites` run immediately before `tests/test_config.py` reproduces this at roughly 50% (4/8 and 6/8 across 8 trials each, within noise) on **both** the pre-fix and post-fix code — confirmed pre-existing, not introduced by the A6 fix. Out of scope for A6 (not tested, not requested); the A6 fix was deliberately designed to add no new writes from the watcher thread so it doesn't make this worse. | Low–Medium | Timing-dependent, low-probability test flakiness (`test_config.py` failing when run after `TestA6ConfigWrites` in the same process) and a narrow theoretical production hazard if `CONFIG_DIR` were ever reassigned at runtime outside of tests (it currently never is). No data loss risk in production. |
| DEBT-011 | Learning | **`ContentDomain` (K4.2) vs. `LearningCandidate` (K4.1-L) — open-domain contradiction, explicitly deferred, not resolved** — `core/cognitive/learning.py`'s `ContentDomain` is a closed three-value enum (`SKILL`/`INTENT_ONTOLOGY`/`USER_MODEL`). `OCBRAIN_K4_1_L_FINAL_LEARNING_ARCHITECTURE.md`'s `LearningCandidate` model is explicitly open-domain. Per this repository's own document-precedence hierarchy, K4.1-L outranks K4.2, so an open model should prevail — but no reconciliation pass against K4.1-L has actually been performed (`OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` §0/§6 flag this themselves via a `[RECONCILE-PENDING]` marker, deliberately left in place rather than removed — K4.2-H1, ADR-K4.2-H-06, Aug 16, 2026). H1 implemented `is_general_purpose` on `CapabilityContract` (D2, unrelated) and added `caused_by` (D9) to `LearningRecord`/`CognitiveDecision` without touching `ContentDomain` at all — H1 deliberately did not attempt this reconciliation; it is recorded here specifically so the marker's continued presence in the architecture doc is legible as "still open," not overlooked. | Medium | `ContentDomain` cannot be safely extended or genericized until a dedicated reconciliation pass against K4.1-L (and the Service Architecture / Recursive Composition documents §0 also names) resolves which model governs; K4.2.6+ (Shared ValidationGate and Learning Wiring) is blocked on this per `IMPLEMENTATION_ROADMAP.md`. |
**Resolved (July 22, 2026):** ~~DEBT-009 — Constitution amendment propagated into a canonical spec and into code, without ratification~~. Confirmed by the project owner: the Constitution is 9 laws / 9 invariants, ratified; the Pressure Test's proposed 11-law/6-field diff was never adopted, and the two downstream artifacts assuming otherwise were simply stale, not evidence of a live ratification question. Corrected: `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §3.1's "two additional laws" table removed (it had also misattributed the two unratified laws to `PROJECT_INSTRUCTIONS.md`, which contains no such laws at all); `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md`'s precedence line corrected from "(11-law)" to "(9-law)"; `core/capabilities/resource.py`'s `HTTPClientResource` docstring corrected to stop citing a ratified six-field Invariant 4. Runtime behavior unaffected, as originally noted — only the citations were wrong, not the code's actual fields.

**Resolved (K3.5 / K3.5.1):** ~~DEBT-001 — MemoryGovernor dormancy~~. `UnifiedMemory.write()` (K3.5) and `update()`/`delete()` (K3.5.1) now all call `GovernanceKernel.evaluate_action()` before any state mutation. No persistent mutation entry point in `UnifiedMemory` bypasses governance. Note: this resolves the *structural* bypass only — `MemoryGovernor`'s own content-validation logic (confidence/growth-limit checks) remains scoped to `memory_write` by its own design; it does not independently validate update/delete content, and extending it to do so was not in scope for this hardening pass.

**Resolved (since the July 16, 2026 `FINAL_K3_READINESS_AUDIT.md`), for the record:** that audit's two "Mandatory before K3" items and several "Recommended" items are now resolved, confirmed by direct re-check this session (Reality Synchronization pass) — not by trusting any intervening report's own claim: `PRODUCT.md`'s capability table now correctly reads 7 governors / 2 worker subclasses; `README.md`/`CHANGELOG.md` no longer assert "11 laws"; `ARCHITECTURE_CHANGELOG.md`'s debt table now correctly marks the K2.1/K2.2/K2.4 findings "Resolved"/"Partially resolved" and its root/`docs/architecture/` duplication was resolved via a redirect stub (not by making the copies identical); its own Timeline no longer claims the Constitution was "later updated to 11 laws"; `K2_2_CUTOVER_REPORT.md` and `docs/reports/K2_2_RETRIEVAL_CUTOVER_REPORT.md` now cross-reference each other as companion reports; `CURRENT_STATE.md`/`KNOWN_ISSUES.md`/`IMPLEMENTATION_ROADMAP.md`/`PROJECT_INDEX.md` now exist. One item from that audit's evidence chain remained open longer than the rest and is carried forward precisely, not silently dropped: the Constitution law-count/Resource-Model question itself (DEBT-009, resolved July 22, 2026 — see above) — the *downstream prose claims* were fixed in this pass, but the canonical spec's own table (§3.1) and the Resource Model code needed a separate, later resolution.

**Resolved (Aug 12, 2026):** ~~K4.2-path interactions were never persisted~~. Found during the post-Runtime-Integration bug hunt: `Orchestrator.handle()`'s K4.2 branch (added Aug 8, 2026) computed an answer and returned it, but never called `self.memory.write(content_type="interaction", ...)` or `self.context.save(...)`. The K2.2 path gets both "for free" because `PlannerWorker` does them internally (`core/workers/planner.py` Steps 7–8, using the exact same `memory`/`context_memory` singletons `Orchestrator` itself holds — confirmed by reading `main.py`'s composition root, not assumed). `CapabilityExecutorWorker` is deliberately narrow — a single compiled-step executor, per its own module docstring, not a whole-query handler — and correctly has no memory/context wiring of its own; nothing else filled the gap. Fixed by adding both calls directly to `Orchestrator.handle()`'s K4.2 branch, mirroring `PlannerWorker`'s pattern exactly (including non-blocking failure handling on the memory write). New regression test: `tests/test_runtime_integration.py::TestMemoryWrites::test_interaction_persisted_to_memory_and_context`.

**Resolved (Aug 12, 2026):** ~~A6 — Config Writes~~ and ~~A7 — System Controller~~. Both were previously reported "VERIFIED AND PRODUCTION-READY, 86/86 passing" by `docs/Bugs Hunt & fix reports/walkthrough.md` and `final_runtime_integration_audit.md`. That report did not match the actual repository: `git diff` against the pre-upload baseline showed zero changes to `core/config.py`, and `modules/system_ctrl/module.py` still had the original `subprocess.Popen(cmd, shell=(SYSTEM == "Windows"))` vulnerability with no `_validate_open_target` function at all — confirmed by direct code reading and by running `tests/test_audit_fixes.py`, which failed with `ImportError`/`AttributeError` on both, not the described assertion failures. The intended production fixes appear to have been left out of whatever upload produced those two files' test coverage and documentation. Implemented for real this session: `core/config.py` gained `_CRITICAL_STATE_KEYS`, a `_models_dirty` flag, and a `flush()` method (critical keys like `stage`/`bootstrap_model` still persist immediately; everything else defers, closing the per-query synchronous-write bottleneck the original A6 finding identified); `modules/system_ctrl/module.py` gained `_validate_open_target()` (character-allowlist + flag-injection rejection) and `_open_app()` now uses `os.startfile()` on Windows instead of a shell. All 10 `test_audit_fixes.py::TestA6ConfigWrites`/`TestA7SystemController` tests pass; no regressions in `tests/test_config.py` or `tests/test_system_ctrl.py`.

---

## Deliberately Deferred Architecture

Items explicitly scoped out with architectural justification. These are NOT debt — they are intentional phase boundaries.

| Item | Rationale | Phase |
|---|---|---|
| Workflow checkpoint/resume persistence | Out of scope for K2.2 per session rules. EventStream checkpoint infrastructure exists; consumption deferred. | Post-K3 |
| AgentGovernor delegation wiring | No worker populates `metadata["delegating_worker_type"]`. `SupervisorWorker` exists as of Packet 08 (July 30, 2026) but does not populate it either — see DEBT-002. | Post-SupervisorWorker |
| KnowledgeEvent/EventStream merge | FA §5.4 identifies this; requires Memory Runtime redesign. | Post-K3 |
| ConversationGuardrails content policy | Default denylist is empty by design (permissive default, K2.4 risk mitigation). Content policy configuration is operational, not architectural. | Deployment |
| OrchestrationGovernor deny list | Default is permissive by design. Deny list configuration is operational. | Deployment |

---

## Future Roadmap (Not Debt)

Items that are correctly absent because they belong to future phases.

**Clarification (added July 24, 2026):** everything below remains accurate —
`SupervisorWorker`, `ReflectionWorker`, and the future capability adapters
genuinely do not exist yet. What changed is narrower: the Cognitive
Front-End *data-contract plumbing* that feeds `Planner` — Intent
Interpretation (K4.2.1), Goal Formation (K4.2.2), and Constraint Extraction
(K4.2.3) — is now implemented (see `CURRENT_STATE.md`'s Cognitive Front-End
section). None of it required any item below; Capability Discovery (K4.2.4,
the next milestone) is the first piece of Cognitive Phase work that
overlaps this table, specifically the future capability adapters.

**Update (Aug 12, 2026):** the clarification above is now itself stale on
one point — `ReflectionWorker`, `EvaluatorWorker`, and `SupervisorWorker`
were built by Packets 07/08 (July 30, 2026) and composition-root-wired by
Runtime Integration (Aug 8, 2026; see `CURRENT_STATE.md`'s Cognitive
Workers table). Moved out of the table below accordingly. `CoderWorker` and
`BrowserWorker` remain genuinely unbuilt.

### Future Cognitive Workers

| Worker | Purpose | Phase |
|---|---|---|
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
