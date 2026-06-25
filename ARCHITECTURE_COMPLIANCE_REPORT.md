# Architecture Compliance Report

## Methodology

Every component proposed for implementation is evaluated against two authoritative documents:
- **FA** = `OCBRAIN_FUTURE_ARCHITECTURE.md`
- **PI** = `PROJECT_INSTRUCTIONS.md`
- **UM** = `Update Unified Memory Migration Design.md`

For each component: exact source evidence is quoted, status is verified against the physical repository, and an architectural compliance verdict is rendered.

**Mandatory Rule**: No component is implemented without explicit justification from the authoritative documents.

---

## 1. GovernanceKernel

### Source Evidence

**PI §6.1 (line 248):**
> "The GovernanceKernel is mandatory."
> "Every autonomous action must pass through governance evaluation."

**PI §6.1 Required Governors (lines 254-260):**
> ```
> OrchestrationGovernor
> MemoryGovernor
> AgentGovernor
> EvolutionGovernor
> ConversationGuardrails
> ```

**PI LAW 1 (line 64):**
> "No autonomous capability may bypass governance."
> "If a feature increases capability without increasing governance visibility, redesign it."

**FA §1.2 (line 58):**
> "GovernanceKernel enforces hard limits at every step"

**FA §4.1 Layer 0 (lines 883-888):**
> ```
> LAYER 0: GOVERNANCE & SECURITY
> ├─ GovernanceKernel (recursion, steps, tokens, workers)
> ├─ HumanApprovalNode (HITL at workflow DAG nodes)
> ├─ GuardrailsNode (PII, content safety, prompt injection)
> ├─ AgentShield-style validation (provider configs, MCP tools)
> └─ EvolutionGovernor (self-modification requires approval)
> ```

### Status
**Missing.** `core/governance/` contains only `memory_governor.py` (1 of 5 required governors). No `governance_kernel.py` exists.

### Implementation Necessity
**Required Now.** PI explicitly states "The GovernanceKernel is mandatory." LAW 1 is an immutable project law. Every other component depends on governance.

### Future Rewrite Risk
**None.** The GovernanceKernel is a permanent architectural fixture at Layer 0. No future phase supersedes or replaces it.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | GovernanceKernel must approve memory writes via MemoryGovernor |
| KnowledgeEntry | Governance validates trust_score, truth_status before writes |
| KnowledgeEvent | Governance actions emit KnowledgeEvents (audit trail) |
| Graph Layer | Governance controls graph mutations |
| Event Layer | Governance decisions are event-sourced (LAW 2) |
| Workflow Layer | GovernanceKernel evaluates every workflow node execution |
| Worker Layer | "No worker may bypass governors" (PI §6.1 line 272) |

### Architectural Compliance Verdict
**Fully Aligned.** Explicit mandate from both PI and FA. Foundational requirement.

---

## 2. EventStream

### Source Evidence

**PI LAW 2 (lines 82-97):**
> "All meaningful cognitive activity must emit immutable events."
> "Every major operation must be: observable, replayable, inspectable, recoverable."

**FA §1.2 (line 59):**
> "EventStream provides full audit trail"

**FA §4.1 Layer 1 (lines 890-894):**
> ```
> LAYER 1: EVENT BACKBONE
> ├─ EventStream (immutable WAL, pub/sub, replay, checkpoints)
> ├─ Durable Execution (workflow state survives restarts)
> ├─ Kafka/Redpanda integration point (Phase 5, distributed)
> └─ ClickHouse export (event analytics, Phase 4.5)
> ```

**FA Pattern 2 (lines 808-812):**
> "OCBrain's EventStream (already event-sourced) needs to become the basis for durable workflow execution, not just observability."

**FA §5.4 Roadmap Difference Analysis:**
> "Event Backbone — Not specified [in Source A] — v4.3.5.5 [in Source B] — Important — Rename → Durable Execution — Better captures value"

### Status
**Missing.** `core/events/` contains only `__init__.py`. An `event_bus.py` exists in `core/` but it is a simple in-memory pub/sub — not an immutable WAL, not persistent, not replayable.

### Implementation Necessity
**Required Now.** LAW 2 is an immutable project law. The FA treats EventStream as already existing (§1.2: "EventStream provides full audit trail"). It is architecturally assumed to be present.

### Future Rewrite Risk
**Low.** The EventStream WAL design is stable across all future phases. Future distributed phases (v4.5.5) add Redpanda as a transport, but the core API and WAL persistence remain the same. Implementing now against the defined interface avoids rewrite.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | Memory writes emit events to EventStream |
| KnowledgeEntry | No direct dependency |
| KnowledgeEvent | KnowledgeEvents are the events written to EventStream |
| Governance | Governance decisions are logged to EventStream |
| Graph Layer | Graph mutations are event-sourced |
| Workflow Layer | Workflow checkpoints stored in EventStream WAL (v4.4.8) |
| Worker Layer | Workers emit progress/completion events |

### Architectural Compliance Verdict
**Fully Aligned.** Mandated by LAW 2 and explicitly present in the Layer 1 architecture.

---

## 3. WorkflowEngine

### Source Evidence

**PI §6.2 (lines 276-294):**
> "The workflow engine is DAG-based."
> "Every workflow must support: serialization, replay, interruption, checkpointing, node caching, partial execution, retry policies, error branches, observability hooks."

**PI §6.3 (lines 298-312):**
> ```python
> class WorkflowNode:
>     node_type: str
>     execution_mode: str
>     retry_policy: RetryPolicy
>     guardrails: GuardrailsConfig
>     approval: HITLConfig
> ```

**FA §4.1 Layer 2 (lines 896-900):**
> ```
> LAYER 2: COGNITIVE ORCHESTRATION
> ├─ WorkflowEngine (DAG, durable execution, partial re-run, HITL nodes)
> ```

**FA §5.4 Roadmap Difference Analysis:**
> "Workflow Engine — Phase 1 done [Source A] — v4.4.7 [Source B] — Duplicate — Remove — Already completed"

### Status
**Missing.** `core/workflow/` contains only `__init__.py`. Despite FA §5.4 claiming "Phase 1 done" and "Already completed," the file is physically absent.

### Implementation Necessity
**Required Now** — but with an important nuance. FA §5.4 says "Already completed" and "Remove" (from the roadmap as a new task). This implies the WorkflowEngine *was* implemented at some point and has been lost. The current phase is v4.3.5 and the WorkflowEngine is a prerequisite for v4.4.8 (Durable Workflow Runtime).

**However**, FA §5.6 Dependency Validation states:
> "v4.4.8 Durable Execution — Prerequisites: WorkflowEngine (done), EventStream (done)"

This confirms WorkflowEngine was assumed complete. It must be restored.

### Future Rewrite Risk
**Medium.** Phase v4.4.8 adds durable execution (checkpoint/resume), saga/compensation, and versioning on top of the WorkflowEngine. If the initial implementation does not design for checkpoint serialization, it will require rework. **Mitigation:** implement serializable node state and checkpoint hooks from the start, even if not used until v4.4.8.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | Workflow nodes read/write memory |
| KnowledgeEntry | No direct dependency |
| KnowledgeEvent | Workflow transitions emit events |
| Governance | Every node execution passes through GovernanceKernel |
| Graph Layer | No direct dependency |
| Event Layer | Workflow state changes are event-sourced |
| Worker Layer | Workers are executed within workflow nodes |

### Architectural Compliance Verdict
**Fully Aligned.** Explicitly mandated by PI §6.2 and FA Layer 2. Was previously implemented; must be restored.

---

## 4. Worker Framework (CognitiveWorker base class)

### Source Evidence

**PI §7 (lines 340-344):**
> "Workers are specialized cognitive runtimes."
> "Workers are NOT free-form chatbots."

**PI §7.2 (lines 365-375):**
> "Every worker must: emit events, stream progress, expose state, support interruption, respect governance, support evaluation, support observability."

**FA §4.1 Layer 3 (lines 902-910):**
> ```
> LAYER 3: AGENT RUNTIME
> ├─ ReActWorker (tool loop, stopWhen, Agent Protocol)
> ├─ PlannerWorker (decompose, schedule, validate dependencies)
> ├─ ReflectionWorker (generate, critique, refine)
> ├─ CoderWorker (sandbox, repomix, git-native, Playwright MCP)
> ├─ EvaluatorWorker (pointwise, pairwise, DeepEval-inspired metrics)
> ├─ BrowserWorker (Playwright MCP, Firecrawl, trust pipeline)
> ├─ MemoryCuratorWorker (active memory improvement, memify-style)
> └─ [Role-specialized workers added per Phase 4+ skills]
> ```

**FA §1.1 Technical Debt (line 45):**
> "MemoryCuratorWorker class entirely absent (§7.1 canonical worker types)"

### Status
**Missing.** `core/workers/` contains only `__init__.py`. No base class, no specialist implementations.

### Implementation Necessity
**Required Now.** Workers are Layer 3 of the target architecture. Without them, no cognitive task execution is possible. The `Orchestrator` currently dispatches to modules (old pattern), not workers (target pattern).

### Future Rewrite Risk
**Low.** The worker abstraction (emit events, stream progress, respect governance) is stable across all future phases. New worker types are added, but the base class API remains constant.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | Workers read/write memory during execution |
| KnowledgeEntry | Workers produce KnowledgeEntries as outputs |
| KnowledgeEvent | Worker actions emit KnowledgeEvents |
| Governance | "No worker may bypass governors" (PI §6.1) |
| Graph Layer | Some workers (MemoryCurator) operate on graph |
| Event Layer | Workers emit events to EventStream |
| Workflow Layer | Workers execute within workflow nodes |

### Architectural Compliance Verdict
**Fully Aligned.** Explicitly mandated in PI §7.1 and FA Layer 3.

---

## 5. PlannerWorker

### Source Evidence

**PI §7.1 (line 351):**
> `PlannerWorker` — listed as canonical worker type.

**FA §4.1 Layer 3 (line 904):**
> "PlannerWorker (decompose, schedule, validate dependencies)"

### Status
**Missing.** No implementation exists.

### Implementation Necessity
**Required Later.** The PlannerWorker is a canonical type, but the current orchestrator handles basic routing. The PlannerWorker becomes critical at v4.3.9 (Instinct→Skill learning) and v4.4+ (complex multi-step workflows).

**For the current phase (v4.3.5):** A stub implementation satisfying the base class contract is sufficient. Full planning logic (decompose, schedule, validate) is needed at Phase 4.

### Future Rewrite Risk
**Low.** Implementing as a CognitiveWorker subclass with the defined interface ensures future enhancements are additive, not rewriting.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | Reads memory for context during planning |
| Worker Layer | Extends CognitiveWorker base |
| Governance | Passes plans through governance before execution |
| Workflow Layer | Creates workflow DAGs for execution |

### Architectural Compliance Verdict
**Fully Aligned.** Canonical worker type in both PI and FA.

---

## 6. EvaluatorWorker

### Source Evidence

**PI §7.1 (line 355):**
> `EvaluatorWorker` — listed as canonical worker type.

**FA §4.1 Layer 3 (line 907):**
> "EvaluatorWorker (pointwise, pairwise, DeepEval-inspired metrics)"

**FA §5.6 Dependency Validation:**
> "v4.3.9 Instinct→Skill — Prerequisites: v4.3.8 retrieval, EvaluatorWorker"

**FA v4.4.2.1 (line 1124):**
> "Requires EvaluatorWorker approval before L3 write"

### Status
**Missing.** No implementation exists. Note: `learning/evaluator.py` exists but is a training evaluation script, not the cognitive EvaluatorWorker.

### Implementation Necessity
**Required Later** (v4.3.9). FA §5.6 lists it as a prerequisite for Instinct→Skill learning. Not needed for the current v4.3.5 phase but required before v4.3.9.

**For the current phase:** A stub implementation is sufficient.

### Future Rewrite Risk
**Low.** DeepEval-inspired metrics are additive to the base evaluation interface.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| Worker Layer | Extends CognitiveWorker base |
| UnifiedMemory | Reads memory entries for evaluation scoring |
| Governance | Evaluations must respect governance policies |

### Architectural Compliance Verdict
**Fully Aligned.** Canonical worker type with explicit dependency role in the roadmap.

---

## 7. SupervisorWorker

### Source Evidence

**PI §7.1 (line 358):**
> `SupervisorWorker` — listed as canonical worker type.

**FA §4.1 Layer 3:** Not explicitly listed in the Layer 3 diagram. The diagram lists 7 workers + "[Role-specialized workers added per Phase 4+ skills]."

**FA Pattern 11 (line 861):**
> "Multi-Agent Role Specialization (★ 9/10 prevalence)"
> "OCBrain implication: Worker types (ReAct, Planner, Coder, Evaluator) are correct."

### Status
**Missing.** No implementation exists.

### Implementation Necessity
**Future Placeholder Only.** The SupervisorWorker is listed in PI §7.1 canonical types but is **not present** in FA §4.1 Layer 3 diagram. FA Pattern 11 explicitly names "ReAct, Planner, Coder, Evaluator" as correct — SupervisorWorker is not mentioned.

The SupervisorWorker pattern (hierarchical delegation) comes from CrewAI (FA §Domain A, line 223: "Hierarchical process pattern (SupervisorWorker orchestrates sub-workers)"). FA recommends "Adopt Concepts Only" for CrewAI.

### Future Rewrite Risk
**None.** As a CognitiveWorker subclass, adding it later has no rework cost.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| Worker Layer | Extends CognitiveWorker, orchestrates other workers |
| Workflow Layer | Creates sub-workflows for delegated tasks |

### Architectural Compliance Verdict
**Partially Aligned.** Listed in PI §7.1 but absent from FA Layer 3. Implementing a stub satisfies PI; full implementation should be deferred to Phase 4+ when multi-agent coordination is needed.

> [!WARNING]
> **FLAG:** SupervisorWorker is justified by PI §7.1 but has weaker support in FA. Proposed because PI lists it as canonical. A stub class is justified; full orchestration logic should wait for the FA-specified "[Role-specialized workers added per Phase 4+ skills]" milestone.

---

## 8. BrowserWorker

### Source Evidence

**PI §7.1 (line 356):**
> `BrowserWorker` — listed as canonical worker type.

**FA §4.1 Layer 3 (line 908):**
> "BrowserWorker (Playwright MCP, Firecrawl, trust pipeline)"

**FA v4.4.1 (lines 1104-1108):**
> ```
> v4.4.1 BrowserWorker (Playwright MCP)
>     - playwright-mcp as BrowserWorker backend
>     - Trust pipeline for browser-extracted content
>     - Sandboxed execution with governance limits
>     - Screenshot → LLM-described for non-text pages
> ```

**FA §6 Priority Matrix (line 1272):**
> "BrowserWorker (Playwright MCP) — playwright-mcp — Medium effort — HIGH impact" — listed under **Short-Term (Phase 4)**

### Status
**Missing.** No implementation exists. Note: `core/web_learning/pipeline.py` handles web crawling but is not a BrowserWorker.

### Implementation Necessity
**Required Later** (v4.4.1). Explicitly scheduled for Phase 4, not the current phase (v4.3.5). The FA Priority Matrix places it in "Short-Term (Phase 4)" — after Memory Foundation completion.

### Future Rewrite Risk
**None.** It is Phase 4 work. Implementing it now would be premature per FA §5.3: "v4.4 Executive Cortex (before basic knowledge acquisition works)" is flagged as premature, and BrowserWorker is Phase 4.4.1.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| Worker Layer | Extends CognitiveWorker |
| Governance | Sandboxed execution with governance limits |
| Event Layer | Emits browsing events |
| Knowledge Acquisition (v4.3.6.2) | Feeds into knowledge acquisition pipeline |

### Architectural Compliance Verdict
**Fully Aligned** — but **not for current phase**. BrowserWorker is Phase 4 work. A stub class definition in the worker framework is justified; full Playwright MCP integration is premature.

> [!IMPORTANT]
> **FLAG:** BrowserWorker is explicitly Phase 4.4.1. Only a stub class should be created now. Full implementation requires playwright-mcp and trust pipeline integration which are Phase 4 dependencies.

---

## 9. Skill Registry

### Source Evidence

**PI §9.1 (lines 483-493):**
> "Every skill must: be versioned, expose metadata, define schemas, support validation, support replayability, support MCP exposure, support isolated execution."

**PI §9.4 (lines 531-542):**
> "Everything should eventually be exposable as MCP: skills, workflows, tools, memory providers, orchestration services, cognitive workers."
> "MCP-native architecture is mandatory."

**FA Pattern 8 (lines 846-849):**
> "Declarative Skill/Tool Definitions (★ 10/10 prevalence)"
> "OCBrain implication: Already implemented (.skill.md files). Extend with: JSON Schema for input validation, example pairs for auto-testing, performance benchmarks, and cost estimates."

**FA Pattern 10 (line 859):**
> "Every OCBrain capability should eventually be MCP-exposed. Already started with SkillRegistry."

### Status
**Partially Exists.** `core/skills/skill_interface.py` exists (6,885 bytes) providing a skill interface. `skill_registry.py` does not exist. FA Pattern 8 states skills are "Already implemented (.skill.md files)" but the registry for discovering, versioning, and MCP-exposing them is not present.

### Implementation Necessity
**Required Now** — but as infrastructure, not as full MCP exposure. The skill interface exists; a registry to discover and version skills is needed for the Phase 3 completion milestone. Full MCP auto-exposure is Phase 4.7.

### Future Rewrite Risk
**Low.** The registry pattern (discover, load, version, expose) is stable. MCP exposure is additive.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | Skills stored as L3 procedural memory |
| KnowledgeEntry | Skills are KnowledgeEntries with layer="l2", procedure_name set |
| Governance | EvolutionGovernor approves skill mutations |
| Worker Layer | Workers execute skills; EvaluatorWorker approves skill promotion |

### Architectural Compliance Verdict
**Fully Aligned.** Mandated by PI §9 and FA Pattern 8. Partial implementation exists; registry completion is justified.

---

## 10. Memory Curator (MemoryCuratorWorker)

### Source Evidence

**PI §7.1 (line 357):**
> `MemoryCuratorWorker` — listed as canonical worker type.

**FA §1.1 Technical Debt (line 45):**
> "MemoryCuratorWorker class entirely absent (§7.1 canonical worker types)"

**FA §4.1 Layer 3 (line 909):**
> "MemoryCuratorWorker (active memory improvement, memify-style)"

**FA §4.1 Layer 4 (line 919):**
> "Memory Curator (memify-style: prune, strengthen, derive, align)"

**FA v4.3.6 (lines 1053-1057):**
> ```
> v4.3.6 Memory Curator Worker (§7.1 canonical worker)
>     - MemoryCuratorWorker as CognitiveWorker subclass (currently MISSING)
>     - Wraps MemoryConsolidator with Agent Protocol interface
>     - Active memify pipeline: prune stale, strengthen high-access, derive facts
>     - Contradiction resolution: when graph finds contradictions, curator resolves
> ```

**FA §6 Priority Matrix (line 1270):**
> "MemoryCuratorWorker class — §7.1 canonical — Low effort — HIGH — required by spec"
> Listed under **Immediate (Complete before Phase 4)**

**FA Pattern 4 (lines 820-824):**
> "MemoryConsolidator should not just evict+promote but actively: prune stale nodes, strengthen high-access connections, derive new facts from existing facts, detect and resolve contradictions."

**UM §5 (lines 167-191):**
> Memory Curator Lifecycle Hooks: `before_write()`, `after_write()`, `before_promote()`, `after_promote()`, `before_archive()`, `after_archive()`, `before_delete()`, `after_delete()`

### Status
**Partially Exists.** The HookRegistry in `unified_memory.py` (lines 92-118) defines all the extension points. The actual `MemoryCuratorWorker` class that registers with and implements these hooks does not exist.

### Implementation Necessity
**Required Now.** FA §6 Priority Matrix explicitly lists it as "Immediate (Complete before Phase 4)." FA §1.1 calls it out as existing technical debt. It is the current phase's (v4.3.6) primary deliverable.

### Future Rewrite Risk
**Low.** The HookRegistry is already designed. The curator wraps the existing MemoryConsolidator and adds LLM-based fact derivation (Phase 4+ enhancement). Basic prune/strengthen/detect is stable.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | Registers with HookRegistry; operates on all memory layers |
| KnowledgeEntry | Reads/modifies truth_status, confidence, importance |
| KnowledgeEvent | Emits events for every curation action |
| Governance | EvolutionGovernor approves knowledge changes above threshold |
| Graph Layer | Reads contradictions from graph for resolution |
| Event Layer | Curation actions are event-sourced |
| Worker Layer | Extends CognitiveWorker base class |

### Architectural Compliance Verdict
**Fully Aligned.** One of the most explicitly mandated components in the entire architecture. Called out as missing technical debt, listed as Immediate priority, scheduled for the current phase.

---

## 11. Graph Integration (Graph-Vector Mutual Indexing)

### Source Evidence

**FA §1.1 Weaknesses (line 28):**
> "No graph-vector fusion (graph and L2 operate independently)"

**FA §4.1 Layer 4 (line 918):**
> "Graph Layer (FalkorDB at scale, mutual-indexed with L2)"

**FA §4.2 Key Architectural Changes:**
> "Graph-vector fusion — Current: Separate layers — Target: Mutual-indexed, co-queried — Priority: HIGH"

**FA v4.3.5.1 (lines 1047-1051):**
> ```
> v4.3.5.1 GraphRAG Layer (Mutual Indexing)
>     - Every graph node stores L2 entry_id reference
>     - Every L2 entry stores graph node_id reference
>     - Unified query: graph traversal enriched by vector context
>     - KAG-inspired logical-form query path for multi-hop questions
> ```

**FA §6 Priority Matrix (line 1270):**
> "Mutual graph-L2 indexing — KAG, cognee — Medium effort — HIGH — unlocks multi-hop"
> Listed under **Immediate (Complete before Phase 4)**

**FA §9.1 (lines 1361-1362):**
> "Graph-vector fusion — Graph and vector are disjoint. Mutual indexing is the unlock for multi-hop reasoning."

**UM §4 (lines 141-164):**
> Updated layer architecture defines L3 as Graph Memory. KnowledgeEntry already includes `graph_node_id: Optional[str]` field for mutual indexing.

### Status
**Partially Exists.** `graph_engine.py` provides basic node/edge CRUD. `KnowledgeEntry` has `graph_node_id` field. `SQLiteGraphBackend` in backends exists. However, actual mutual indexing (graph node ↔ L2 entry bidirectional references) is not implemented.

### Implementation Necessity
**Required Now.** This is the current phase's (v4.3.5) primary deliverable. FA §6 lists it as Immediate and FA §9.1 calls it one of the 5 critical gaps.

### Future Rewrite Risk
**Medium.** FA §5.6 notes: "v4.3.5 GraphRAG — If delayed: Multi-hop retrieval fails." And: "v4.3.6 Curator — Prerequisites: v4.3.5 mutual indexing — If too early: Can't curate without graph." The graph schema must support FalkorDB migration at scale (Phase 5-6), so the abstraction layer (already in `backends/base.py` as `GraphBackend` ABC) must be preserved.

### Dependency Analysis
| Dependency | Relationship |
|---|---|
| UnifiedMemory | Graph is registered as L3 backend via `register_graph_backend()` |
| KnowledgeEntry | `graph_node_id` field provides the L2→L3 pointer |
| KnowledgeEvent | Graph mutations emit events |
| Governance | Graph writes pass through governance |
| Event Layer | Graph operations are event-sourced |
| Retrieval Engine (v4.3.8) | Multi-hop retrieval depends on mutual indexing |
| Memory Curator (v4.3.6) | Curator resolves contradictions found by graph |

### Architectural Compliance Verdict
**Fully Aligned.** Current phase's primary deliverable. Multiple explicit mandates across FA §1.1, §4.1, §4.2, §5.5, §6, and §9.1.

---

## Flagged Components — Not in Original 11 But Identified During Audit

### 12. knowledge_event.py (KnowledgeEvent)

**Not in the user's requested review list, but critical.**

**UM §2 (lines 44-96):**
> "Separate KnowledgeEntry From KnowledgeEvent"
> "KnowledgeEvent — Represents lifecycle changes affecting a KnowledgeEntry."
> "Do not use KnowledgeEvent as the sole memory representation."

**FA §5.4:**
> "Knowledge Event Model — Not specified [Source A] — v4.3.4.6 [Source B] — Needed — Merge into event backbone — Not standalone"

**Status:** **Missing — IMPORT BLOCKER.** `unified_memory.py` line 36 imports `from core.memory.knowledge_event import KnowledgeEvent` — the file does not exist. The entire UnifiedMemory system cannot be imported.

**Implementation Necessity:** **Required Immediately.** System is non-functional without it.

**Architectural Compliance Verdict:** **Fully Aligned.** Explicitly mandated by UM §2.

---

### 13. PipelineMiddleware

**Not in the user's requested review list.**

**PI does not explicitly name "PipelineMiddleware."** It describes pipeline behavior implicitly:
- PI §14.1: sandboxing rules
- PI §14.3: permission model
- FA Layer 6 describes the Knowledge Pipeline but not a "PipelineMiddleware" class.

**Status:** Missing. `core/pipeline/` contains only `__init__.py`.

**Implementation Necessity:** **Flag — weak architectural justification.** PI describes pipeline concepts but does not mandate a "PipelineMiddleware" component by name. The existing `core/web_learning/pipeline.py` and `core/privacy.py` partially cover PII filtering and safety.

> [!WARNING]
> **FLAG:** PipelineMiddleware was proposed in the previous implementation plan but lacks explicit naming in either PI or FA. The pipeline concept exists but as part of Knowledge Acquisition (v4.3.6.2), not as a standalone middleware layer. **Recommend deferring** to v4.3.6.2 when knowledge acquisition pipeline is built, rather than creating a standalone middleware now.

**Architectural Compliance Verdict:** **Not Aligned** as a standalone component. Functionality is covered by Knowledge Acquisition Pipeline (v4.3.6.2) and existing privacy/trust modules.

---

### 14. ObservabilityFramework

**Not in the user's requested review list.**

**FA §4.1 Layer 9 (lines 953-958):**
> ```
> LAYER 9: OBSERVABILITY & TELEMETRY
> ├─ Langfuse integration
> ├─ Prometheus metrics (exported from ObservabilityFramework)
> ├─ Grafana dashboards
> ├─ DuckDB analytics
> └─ ClickHouse
> ```

**FA v4.4.5 (lines 1138-1142):**
> "Cognitive Observability Layer — Langfuse integration — Prometheus metrics export from ObservabilityFramework"

**FA §6 Priority Matrix:** Langfuse listed as Immediate; Prometheus listed as Short-Term (Phase 4).

**Status:** Partially exists. `core/observability/tracer.py` exists. No `ObservabilityFramework` class.

**Implementation Necessity:** FA explicitly references "ObservabilityFramework" as the source for Prometheus metrics, scheduled at v4.4.5. Langfuse tracing is listed as Immediate. A minimal ObservabilityFramework wrapping the existing tracer is justified; full Prometheus/Grafana is Phase 4.

**Architectural Compliance Verdict:** **Partially Aligned** for current phase. A minimal framework wrapping the tracer is justified. Full Layer 9 is Phase 4.4.5.

---

## Summary Table

| # | Component | PI Evidence | FA Evidence | Status | Necessity | Rewrite Risk | Verdict |
|---|-----------|------------|-------------|--------|-----------|-------------|---------|
| 1 | GovernanceKernel | §6.1 "mandatory" | Layer 0 | Missing | **Required Now** | None | **Fully Aligned** |
| 2 | EventStream | LAW 2 | Layer 1 | Missing | **Required Now** | Low | **Fully Aligned** |
| 3 | WorkflowEngine | §6.2 | Layer 2 | Missing (was "done") | **Required Now** | Medium | **Fully Aligned** |
| 4 | Worker Framework | §7, §7.1, §7.2 | Layer 3 | Missing | **Required Now** | Low | **Fully Aligned** |
| 5 | PlannerWorker | §7.1 canonical | Layer 3 | Missing | Required Later | Low | **Fully Aligned** |
| 6 | EvaluatorWorker | §7.1 canonical | Layer 3, §5.6 | Missing | Required Later | Low | **Fully Aligned** |
| 7 | SupervisorWorker | §7.1 canonical | **Absent from Layer 3** | Missing | Future Placeholder | None | **Partially Aligned** |
| 8 | BrowserWorker | §7.1 canonical | Layer 3, v4.4.1 | Missing | Required Later (v4.4.1) | None | **Fully Aligned** (Phase 4) |
| 9 | Skill Registry | §9.1, §9.4 | Pattern 8, 10 | Partial | Required Now | Low | **Fully Aligned** |
| 10 | Memory Curator | §7.1 canonical | v4.3.6, §6 Immediate | Partial (hooks only) | **Required Now** | Low | **Fully Aligned** |
| 11 | Graph Integration | — | v4.3.5, §4.2, §9.1 | Partial | **Required Now** | Medium | **Fully Aligned** |
| 12 | knowledge_event.py | — | §5.4, UM §2 | **IMPORT BLOCKER** | **Immediate** | None | **Fully Aligned** |
| 13 | PipelineMiddleware | Implicit only | Not named | Missing | Defer to v4.3.6.2 | — | **Not Aligned** |
| 14 | ObservabilityFramework | §12 | Layer 9, v4.4.5 | Partial (tracer only) | Minimal Now | Low | **Partially Aligned** |
