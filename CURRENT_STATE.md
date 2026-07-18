# OCBrain Kernel v1.0 — Current State

**Last synchronized:** July 18, 2026 (Repository Reality Synchronization pass)
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
| K3 — Compliance Audit | ⬜ Next | — |

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
