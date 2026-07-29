# OCBrain Kernel v1.0 — Current State

**Last synchronized:** July 29, 2026 (corrected Cognitive Front-End status section below — it had not been updated since July 24, 2026 despite K4.2.4/K4.2.5 (Packets 02/03) completing July 25–27, and Plan Compilation (Packet 06) completing this session; prior sync July 24, 2026 added the section for K4.2.1–K4.2.3; prior sync July 22, 2026 K3 status correction; prior full sync July 18, 2026)
**Authority:** This document is the authoritative answer to "what is actually built right now."

---

## Kernel Implementation Status

| Phase | Status | Completion |
|---|---|---|
| K1 — Architecture Specification | ✅ Complete | July 2026 |
| K2.1 — Execution Runtime | ✅ Complete | July 2026 |
| K2.2 — Workflow Runtime | ✅ Complete | July 2026 |
| K2.3 — Capability Runtime | ✅ Complete | July 2026 |
| K2.4 — Governance Completion | ✅ Complete | July 2026 |
| K3.5 — Governance Wiring (`write()`) | ✅ Complete | July 2026 |
| K3.5.1 — Governance Consistency (`update()`, `delete()`) | ✅ Complete | July 2026 |
| K3 — Compliance Audit | ✅ Complete | July 2026 |

**K3 resolution note (July 22, 2026):** This table previously marked K3 as outstanding, and `IMPLEMENTATION_ROADMAP.md` explicitly declined to adopt `docs/reports/K3.5 — Kernel Hardening Report (Final).md`'s "UNCONDITIONAL KERNEL v1.0 CERTIFICATION" framing pending resolution. Confirmed by the project owner: K3 was in fact performed — the existence of K3.5/K3.5.1 is itself the result of doing it (K3 surfaced the governance-bypass gaps; K3.5/K3.5.1 remediated them). Git history corroborates the sequence: `bebce09 ocbrain k3 audit` precedes `46f550c k3.5 hardening session` and `236e687 K3.5.1: Kernel governance consistency...`. This document's status line simply hadn't been updated after K3 happened. Unrelated tracked debt (`KNOWN_ISSUES.md` DEBT-002 through DEBT-008) remains open regardless — K3's completion means the compliance-audit milestone occurred, not that zero debt remains.

---

## Cognitive Front-End Implementation Status

**Added July 24, 2026** — this section did not previously exist; K4.2.1–K4.2.3 had been implemented (the first two properly, K4.2.3 via an unreviewed upload — see `docs/architecture/k4_2_3_completion_report.md` §0) but never rolled into this document, the same kind of doc/reality lag this file's own K3 note above already describes once. Corrected via direct code audit, not by trusting any prior report's claim. **Updated July 29, 2026** — K4.2.4, K4.2.5, and Plan Compilation (Packets 02, 03, 06) had the same lag: all three were complete (git commits `be07a97`, `1e903c1`, and this session respectively) but this table still showed K4.2.4 as "Not started" and omitted K4.2.5 entirely. Re-verified via direct code audit and a full test run (922/922 passing) before correcting, not by trusting `IMPLEMENTATION_TRACKER.md`'s prose alone.

| Milestone | Status | Completion | Key Deliverables |
|---|---|---|---|
| K4.2.1 — Intent Interpreter | ✅ Complete | July 2026 | `Intent`, `IntentHypothesis`, `CognitiveArtifact` protocol, multi-hypothesis inference, input normalization (`core/cognitive/intent.py`) |
| K4.2.2 — Goal Formation | ✅ Complete | July 2026 | `Goal`, `GoalLifecycle`, `form_goals()`, compound-request splitting, `interpret_request()` public entrypoint |
| K4.2.3 — Constraint Extraction + Planner Contracts | ✅ Complete | July 24, 2026 | `Constraint`, `PlannerRequest`, `PlannerHint`, `PlannerResult`, `_extract_constraints()`, `cognitive.constraints_extracted` event, `rejected_precheck` contradiction detection (`core/cognitive/planner.py`) |
| K4.2.4 — Capability Discovery | ✅ Complete | July 26, 2026 | `CapabilityDiscoveryRequest`, `discover_capabilities()`, description-overlap ranking (`core/cognitive/planner.py`) |
| K4.2.5 — Planner Completion | ✅ Complete | July 27, 2026 | `ClarificationPolicy`, `ExecutionPlanLifecycle`, `PlanStep`, `ExecutionPlan`, decomposition/sequencing/impasse pipeline, `plan()` public entrypoint (`core/cognitive/planner.py`) |
| Plan Compilation (Packet 06 — K4 §6/§15, K4.2 §1) | ✅ Complete | July 29, 2026 | `CompilationStatus`, `CompilationResult`, `compile()` public entrypoint, `plan_compile` governance gate, ExecutionPlan→WorkflowDefinition mapping (`core/cognitive/compiler.py`) |

Boundary holds as specified (K4.2 §1): the full three-entrypoint public surface — `interpret()`, `plan()`, `compile()` — now exists. `compile()` is the single seam to Kernel execution (K4.2 §1/§6): it produces a `WorkflowDefinition` under governance, but nothing in the Cognitive Front-End executes one — `WorkflowRuntime` invocation of a compiled plan remains untouched, as does capability *selection* (resolving a `capability_type` to a specific registered adapter), both reserved for future work (`SupervisorWorker`/Packet 08, the Cognitive Runtime/C-MoE). See `docs/architecture/k4_2_1_completion_report.md` through `k4_2_5_completion_report.md` and `packet_06_plan_compilation_completion_report.md` for full detail per milestone.

---

## Runtime Services

| Service | File | Status | Description |
|---|---|---|---|
| **ExecutionRuntime** | `core/runtime/execution_runtime.py` | Live | Worker invocation, ExecutionContext lifecycle, failure containment. One worker per call, never raises. |
| **WorkflowRuntime** | `core/workflow/runtime.py` | Live | DAG-based multi-worker orchestration. Retry with exponential backoff. Lifecycle event emission. |
| **AdapterRuntime** | `core/capabilities/adapter_runtime.py` | Live | Capability execution with adapter selection, health-based ranking, and automatic fallback. |
| **CapabilityRegistry** | `core/capabilities/registry.py` | Live | Metadata-only index of capabilities and adapters. Does not execute — AdapterRuntime executes. |
| **GovernanceKernel** | `core/governance/governance_kernel.py` | Live | Constitutional governance enforcement. Template method pattern makes bypass structurally impossible. |
| **UnifiedMemory** | `core/memory/unified_memory.py` | Live | L0–L4 tier memory model. SQLite + FTS5 + BM25 + embeddings + graph index. |
| **EventStream** | `core/events/event_stream.py` | Live | Immutable, append-only event log. SQLite WAL. Pub/sub, replay, checkpoints. |

---

## Governance

7 governors registered in `GovernanceKernel.__init__()`:

| Governor | File | Status | Purpose |
|---|---|---|---|
| **RecursionGovernor** | `core/governance/governance_kernel.py` | Active | Prevents runaway recursive loops (depth > 10 → REJECT) |
| **BudgetGovernor** | `core/governance/governance_kernel.py` | Active (evaluation mechanism correct; no accumulation source yet) | Correctly rejects when `step_count`/`token_spend` exceed threshold. Metadata propagation is wired end-to-end (`ExecutionContext` → `AbstractCognitiveWorker.execute()` → `Orchestrator.handle()`), but nothing in the repository currently increments these values beyond their `0`/`0.0` initialization — the REJECT branch is logically correct but currently unreachable in any production path. See KNOWN_ISSUES.md DEBT-007. |
| **EvolutionGovernor** | `core/governance/governance_kernel.py` | Active | Controls self-modifying actions. HITL escalation when `requires_approval` is set. |
| **OrchestrationGovernor** | `core/governance/orchestration_governor.py` | Active (permissive default) | Authorizes which worker types may execute |
| **AgentGovernor** | `core/governance/agent_governor.py` | Active (no live trigger) | Per-call resource ceiling and delegation permission matrix |
| **ConversationGuardrails** | `core/governance/conversation_guardrails.py` | Active (permissive default) | Session-level content policy via denylist |
| **MemoryGovernor** | `core/governance/memory_governor.py` | Active (live trigger: `memory_write` only) | Validates memory ingestion quality and growth limits |

All persistent memory mutations (write, update, delete) are governed before any state change occurs. `UnifiedMemory.write()` (K3.5), `update()`, and `delete()` (K3.5.1) each call `GovernanceKernel.evaluate_action()` first — before storage mutation, cache invalidation, archive writes, graph sync, or hook execution — using `memory_write` / `memory_update` / `memory_delete` action types respectively. REJECT/ESCALATE short-circuits the operation and emits a durable `EventStream`/`KnowledgeEvent` record (`memory_{write,update,delete}_{rejected,escalated}`); every other governor still runs against all three action types in the same evaluation chain. No persistent state mutation inside `UnifiedMemory` bypasses `GovernanceKernel`.

> **Note:** `MemoryGovernor`'s content-validation logic (confidence and growth-limit rejection) is scoped to `action_type == "memory_write"` by its own explicit design — it approves `memory_update`/`memory_delete` unconditionally rather than applying update/delete-specific content checks, since none currently exist. OrchestrationGovernor, AgentGovernor, and ConversationGuardrails remain permissive by default (empty deny-lists) — real, live checks that simply have nothing configured to reject yet, not dormant call sites. AgentGovernor's delegation permission matrix specifically still awaits `SupervisorWorker`, which does not yet exist. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for details.

---

## Cognitive Workers

| Worker | File | Status |
|---|---|---|
| **AbstractCognitiveWorker** | `core/workers/base.py` | Template base — governance → events → `_run()` |
| **PlannerWorker** | `core/workers/planner.py` | Implemented, production-wired (K2.2) |
| **MemoryCuratorWorker** | `core/workers/memory_curator.py` | Implemented, composition-root-wired (K2.1) |

---

## Capability Adapters

3 adapters registered for `CapabilityType.LLM_COMPLETION`:

| Adapter | File | Description |
|---|---|---|
| **ModelRouterAdapter** | `core/capabilities/adapters/model_router_adapter.py` | Wraps pre-existing ModelRouter (compatibility bridge) |
| **OllamaAdapter** | `core/capabilities/adapters/ollama_adapter.py` | Direct Ollama API adapter |
| **OpenAICompatAdapter** | `core/capabilities/adapters/openai_compat_adapter.py` | OpenAI-compatible API adapter |

---

## Retrieval Stack

| Component | File | Status |
|---|---|---|
| **ContextAssemblyEngine** | `core/memory/assembly.py` | Live — production retrieval entry point |
| **GraphRAGPipeline** | `core/memory/retrieval/graphrag/pipeline.py` | Live — canonical retrieval runtime |
| **RetrievalContextBuilder** | `core/memory/retrieval/context/builder.py` | Live — structured context assembly |
| **RetrievalFusionEngine** | `core/memory/retrieval/fusion.py` | Compatibility façade — delegates to GraphRAGPipeline |

---

## Other Kernel Domains

Explicitly checked in the July 18, 2026 Reality Synchronization pass; not previously listed in this document.

| Domain | Status | Notes |
|---|---|---|
| **Scheduler (kernel-level)** | Missing — deliberate | No `SchedulerService` exists. Explicitly, repeatedly deferred by K1/K1.5/K1.6 ("not needed yet" — `asyncio.gather()` fan-out is sufficient at single-process scale; a dedicated scheduler is scoped to distributed/queue-mode execution, not yet built). Not a gap relative to current scope. |
| **Scheduler (learning pipeline)** | Live, unrelated | `learning/scheduler.py`'s `Scheduler` class (crawl/clean/train/distill/gap-detect loops) is constructed at `main.py`'s composition root. A distinct subsystem from kernel-level task scheduling — do not conflate the two. |
| **Resource Model** | Partially implemented | No formal `Resource` Protocol/ABC class exists anywhere — by design, per `OCBRAIN_K1.6_RESOURCE_MODEL.md`'s explicit decision to use structural typing rather than inheritance, to avoid touching `KnowledgeEntry`'s declaration. Two concrete Resource types exist (`HTTPClientResource`, `ModelResource` in `core/capabilities/resource.py`, K2.3) implementing a six-field shape. `KnowledgeEntry` — the one object K1.6's own migration plan said needed minor field alignment — has not been aligned (retains `trust_score`, not `trust`; no `version`/`dependencies` fields). See KNOWN_ISSUES.md DEBT-009 for the six-field shape's unratified-Constitution-amendment provenance. |
| **Explainability** | No dedicated layer; diffuse partial compliance | No `Explain*` class or module exists anywhere in the repository. `GovernanceResult.reason` is populated on every REJECT/ESCALATE (governance-decision-level explainability, real and functional). The Constitution's broader Law 6 example — "before a workflow runs, the kernel can state plainly what it understood the goal to be, and what it's still uncertain about" — has no general-purpose implementation in `ExecutionRuntime` or `WorkflowRuntime`; no pre-execution confidence/justification surface exists. |

---

| Document | Location | Purpose |
|---|---|---|
| Kernel Constitution | `OCBRAIN_KERNEL_CONSTITUTION.md` | 9 laws, 9 invariants — highest authority |
| Kernel Architecture v1.0 | `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` | Frozen engineering specification |
| Architecture Changelog | `docs/architecture/ARCHITECTURE_CHANGELOG.md` | Historical context for decisions |
| Project Instructions | `docs/architecture/PROJECT_INSTRUCTIONS.md` | Operational engineering rules |
| This document | `CURRENT_STATE.md` | What is actually built right now |
| Implementation Roadmap | `IMPLEMENTATION_ROADMAP.md` | What comes next |
| Known Issues | `KNOWN_ISSUES.md` | Active debt and deferred items |
| Project Index | `PROJECT_INDEX.md` | Repository map |

---

*This document is the single source of truth for "what exists." If this document and another document disagree about implementation status, this document is authoritative. Update this document whenever implementation status changes.*
