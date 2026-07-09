# OCBrain Kernel Phase — K1.5: Kernel API, Service Model & Contract Freeze Proposal

**Date:** July 8, 2026
**Status:** Final pre-implementation architecture specification. No code written — per instruction, this is contract design, not implementation.
**Precedence applied:** Kernel Constitution (11-law version) → `PROJECT_INSTRUCTIONS.md` → K1 Runtime Audit → implemented code → prior architecture documents, exactly as specified.
**Re-audit scope:** Composition root, `UnifiedMemory`, the full graph/retrieval subsystem (not previously read at file level in K1), `provider_mesh.py`, worker framework, skill interface all re-verified directly against source this session. K1's findings are treated as a starting point, not assumed correct without re-checking — one of them needed revision; see §13.

---

## 0. What Changed Since K1

K1 found the worker layer fully built and fully disconnected from production. Re-reading the repository with fresh eyes for this session found the **same pattern in a second, more advanced subsystem that K1 didn't inspect at the file level**: `core/memory/retrieval/graphrag/` (`GraphRAGPipeline`, `IntentAnalyzer`, `TraversalStrategy`, `RankingStrategy`) and `core/memory/retrieval/context/` (`RetrievalContextBuilder`, `Context`, `ContextBlock`, `ContradictionGroup`, `ProvenanceRecord`, MinHash dedup, token budgeting) are real, well-factored, and have their own substantial test coverage (`test_graphrag.py`, `test_context_builder.py`, `test_graph_indexer.py` — 64K of tests combined) — and have **zero consumers outside their own subsystem**, confirmed by grep with no false positives. The live retrieval path (`RetrievalFusionEngine.fuse_search()`, called from `ContextAssemblyEngine`, called from `Orchestrator.handle()`) delegates straight to `UnifiedMemory.search()` and returns a plain `List[SearchResult]` — no `Evidence`, no `Context` object, no contradiction detection, no provenance record. Two complete, non-overlapping retrieval stacks exist in this codebase today; only the simpler one is live.

This is not a new category of problem — it's the same "built, tested, disconnected" pattern K1 found in the worker layer, now confirmed in a second place. It does change one specific recommendation from K1's migration plan (§13) and materially shapes the Working Memory model below (§6).

---

## 1. Kernel Vocabulary Freeze

The requested list has ~48 candidate terms. A number of these are genuine synonyms or belong to a different layer than the Kernel. Both are noted explicitly rather than silently — collapsing without explanation would just move the ambiguity problem instead of solving it.

### 1.1 Canonical Definitions

| Term | Definition | Owner |
|---|---|---|
| Kernel | The smallest set of responsibilities that must be centralized/governed for OCBrain to remain coherent, safe, explainable (Constitution Part I) | — |
| Kernel Runtime | The live process instantiating the Kernel's services | Composition root |
| Execution Runtime | The service that invokes one Worker/Capability for one unit of work | New (§2) |
| Execution Boundary | The isolation line around one execution — what it can see, touch, and fail without affecting | Execution Runtime |
| Execution Context | The data object threading through one execution: `request_id`, `worker_id`, `session_id`, `causal_chain`, `working_memory`, `governance_state`, `cancellation_token` (per K1 §3.3) | Execution Runtime, passed by value |
| Execution Transaction | The atomicity unit for a multi-step execution — what gets rolled back together if a step fails mid-sequence | Workflow Runtime (only meaningful for multi-node workflows; a single Worker invocation has no sub-steps to roll back) |
| Kernel State | The kernel's own bookkeeping — registries, governor state, active execution table | Kernel Runtime |
| Runtime State | The state of one in-progress execution | Execution Context |
| Working Memory | L0 (PI §8.1) — in-process, sub-millisecond, LRU-evicted scratch space any Worker can read/write during execution | Context Service |
| Context | A transient, task-scoped view assembled from Memory/Knowledge for one execution — not a persistent store (Constitution glossary, unchanged) | Retrieval, held in Working Memory |
| Evidence | Observation(s) evaluated as relevant/reliable enough to justify a claim (Constitution glossary, unchanged) | Retrieval |
| Capability | An abstract, schedulable unit of work defined by its contract, independent of what satisfies it (Constitution glossary) | Capability Registry |
| Capability Contract | The formal input/output/side-effect specification one Capability publishes | Capability Registry |
| Capability Adapter | A concrete implementation satisfying a Capability's contract by wrapping one external system (Constitution glossary) | Capability Registry |
| Capability Registry | The static index of what Capabilities/Adapters exist | New (§2) |
| Capability Resolver | The runtime function that picks *which* Adapter satisfies a Capability request right now (health/cost/latency-scored) | New (§2) |
| Worker | A schedulable cognitive unit executing via `AbstractCognitiveWorker.execute()` | Worker Registry |
| Worker Context | `ExecutionContext` plus worker-specific fields — not a separate concept, a specialization | Execution Runtime |
| Worker Lifecycle | created → running → suspended → completed/failed (`WorkerState` enum, already defined in `core/workers/base.py`) | Execution Runtime |
| Memory | The kernel's persistent store of Observations, Evidence, and derived facts (Constitution glossary, unchanged) | Memory Service |
| Knowledge | The subset of Memory validated past a confidence threshold (Constitution glossary, unchanged) | Memory Service |
| Graph | An index over Memory, not a storage layer — direct quote from this repository's own hardening report, itself citing `OCBRAIN_FUTURE_ARCHITECTURE.md` | Memory Service |
| Retrieval | The Capability of querying Memory/Knowledge to produce Evidence | Memory Service, invoked as a Capability |
| Workflow | A reusable, versioned template composing Capabilities to satisfy a class of Goals (Constitution glossary, unchanged) | Workflow Runtime |
| Service | A Kernel-internal component with its own lifecycle that does coordination work — distinguished from a Capability, which does domain work | — |
| Adapter | The general Kernel term. `Provider` (the actual class name in `provider_mesh.py`) becomes a *sub-type* of Adapter scoped to inference specifically, not a competing general term | Capability Registry |
| Skill | The current, forward-looking name for a typed, contract-bearing Capability (`skill_interface.py`'s `BaseSkill`) | Capability Registry |
| Module | The legacy name for what `Skill` replaces — `Orchestrator.modules`, `classify()`'s output labels. Being phased out, not frozen | — |
| Tool | What a Skill is called when exposed externally via MCP — same underlying object, different vocabulary at a different boundary | — |
| Event | An immutable record of a specific state transition (Constitution glossary, unchanged) | Event Service |
| Observation | A raw, timestamped record of something perceived or that occurred (Constitution glossary, unchanged) | — |
| Decision | The outcome of one governance evaluation — maps directly to the real `GovernanceVerdict` enum already in code: REJECT / ESCALATE / proceed | Governance Service |
| Goal | The verified target state an Intent compiles to (Constitution glossary, unchanged) | — |
| Task | A single schedulable unit of work toward a Goal (Constitution glossary, unchanged) — absorbs "Instruction," which is not a separate concept | — |
| Action | What a Capability actually does when invoked — the concrete effect | Capability Adapter |
| Constraint | Something extracted from an Intent that limits how its Goal can be satisfied — distinct from Policy, which is kernel-level and intent-independent | Intent Verification |
| Policy | A specific, declared rule constraining what a capability or resource may do (Constitution glossary, unchanged) | Governance Service |
| Governor | An implementation of one Policy — a `Governor` subclass in the actual codebase | Governance Service |

### 1.2 Explicit Collapses (with reasoning)

- **Execution Scope → Execution Boundary.** Same concept under two names in the source list; kept the more precise term.
- **Capability Runtime → Execution Runtime.** A Capability invocation *is* an execution. A separate runtime for it would duplicate Execution Runtime's job under a different name.
- **Instruction → Task.** No daylight between them once Task is precisely defined.
- **Reasoning, Planning → not Kernel vocabulary.** These are Capability-layer or Worker-layer concepts (what `PlannerWorker` and `ReflectionWorker` specifically *do*), not things the Kernel itself needs to define. The Kernel schedules a `PlannerWorker`; it doesn't need its own notion of "planning" independent of that Worker's contract. Defining these at the Kernel level would be exactly the kind of scope creep the Constitution's Non-Goals (`not another AI agent framework`) exists to prevent.
- **Identity → not this session's scope.** "Self Identity" is explicitly named as a future Cognitive Phase item in the K1 prompt's own roadmap, explicitly out of scope for the Kernel phase. Freezing a definition for it now would be defining a concept before there's any implementation experience to ground it in — directly against the Law of Evidence over Assumption.
- **Hypothesis → not Kernel vocabulary.** This belongs to whatever specific Worker strategy needs it (a forecasting- or research-style worker, per the Metaculus calibration pattern already tracked in the research corpus) — it's domain vocabulary for one Capability, not a kernel primitive.

---

## 2. Kernel Service Model

Same discipline applied here as to vocabulary: the requested list has 23 candidates. Nine are genuine, distinct services (five already exist, four are new). The rest collapse into those nine or are explicitly rejected, with reasons — "do not invent services unnecessarily" is taken literally.

### 2.1 The Real Service Set

| Service | Status | Purpose | Thread safety | Failure behavior |
|---|---|---|---|---|
| `GovernanceService` (`GovernanceKernel`) | **Exists, live** | Evaluate actions against registered Governors before they proceed | Single-threaded asyncio, no shared mutable state across concurrent calls beyond governor stats | A governor error must not silently permit — evaluated separately per K1's remaining-governor work |
| `EventService` (`EventStream`) | **Exists, live** | Append-only event log, replayable | Append-safe by construction (WAL-backed) | Emission failure is non-fatal by design (`_emit_event`'s try/except, already verified in code) — logged, never blocks the request |
| `MemoryService` (`UnifiedMemory`) | **Exists, live** | Canonical read/write for all persistent memory | Single instance, verified (K1 §1.1); async-safe | Write failures are caught and logged non-blocking in `Orchestrator.handle()` today — acceptable for now, revisit once Workers own this path |
| `HealthMonitor` | **Exists, live** | Periodic system health checks | Background task, isolated from request path | Already correctly isolated (confirmed: `health_monitor.start()` runs as its own background task) |
| `ExecutionRuntime` | **New — Critical** | Construct and invoke one `AbstractCognitiveWorker`, propagating `ExecutionContext`, enforcing the Execution Boundary | Must support concurrent invocations (current `asyncio.gather` fan-out pattern) | Must integrate the containment pattern already correct at the module-fan-out level (`return_exceptions=True`) — don't regress this when the worker layer takes over |
| `WorkflowRuntime` | **New — Critical** | Coordinate a DAG of Execution Runtime invocations; own Execution Transactions | Sequential within one workflow instance; multiple workflow instances run concurrently | Failure Containment (Constitution Law 11) applies at the node level — one node's failure suspends that node, not the whole workflow, unless the workflow's own contract says otherwise |
| `CapabilityRegistry` | **New — Critical** | Static index: what Capabilities/Adapters exist | Read-heavy, safe for concurrent reads; writes (registration) happen at startup | A missing capability is a resolution-time error, not a registry-time one |
| `CapabilityResolver` | **New — Critical** | Runtime selection of *which* Adapter satisfies a request, when more than one could | Stateless function of current health/cost/latency data | Falls back through the Adapter list in ranked order; total unavailability surfaces as a Failure Containment event, not a silent hang |
| `WorkerRegistry` | **New — Critical** | Index of constructable Worker types | Read-heavy | Requesting an unregistered Worker type is a resolution-time error |
| `ContextService` | **Partial — extend** | Own Working Memory; assemble per-execution Context (see §6) | Scoped to one execution, no cross-execution sharing by default | If assembly fails, degrade to an empty Context rather than blocking the request — matches the existing non-blocking pattern already used for memory writes |

### 2.2 Explicitly Rejected or Folded — With Reasons

- **`Scheduler`** — not justified yet. `asyncio.gather()` is simple, already verified non-blocking (hardening report), and sufficient at single-process scale. A dedicated scheduler earns its place once distributed/queue-mode execution is real (already sequenced later in the existing roadmap). Building it now would be solving a problem the system doesn't have yet.
- **`StateManager`** — largely exists already as `core/runtime/state.py`; extend it, don't build a parallel service.
- **`MetricsCollector`** — folds into `EventService`. PI §12 already treats traces/metrics/logs/events as one integrated observability concern; a separate collector would just be a second place metrics could disagree with the event log, which is exactly what the Law of Single Source of Truth exists to prevent.
- **`RecoveryManager`** — folds into `ExecutionRuntime`/`WorkflowRuntime`. Recovery is a *responsibility* those two services already need under Law of Failure Containment, not a third service that would need to coordinate with both of them anyway.
- **`ServiceContainer` / dependency-injection container** — rejected, same reasoning as K1's `ServiceLocator` rejection. Current explicit constructor injection is verified "mostly correct" by direct code read. A container would trade explicit, inspectable wiring for implicit resolution — a direct LAW 4 regression, not an improvement.
- **`ExecutionManager`** — this is `ExecutionRuntime` under a second name from the request list; not counted twice.
- **`KernelRuntime`** — not a peer service; it's the process that hosts the services above. Listing it as one of them would be a category error.
- **`ExecutionBoundary`, `ExecutionContext`, `ExecutionTransaction`, `WorkingMemory` (as standalone services)** — these are vocabulary/data concepts (§1), not services with their own independent lifecycle. `WorkingMemory` specifically is a *resource* `ContextService` manages, not a service in its own right.

---

## 3. Stable Kernel APIs

Contracts only — no implementation. Four genuinely new surfaces (the rest are already stable, per K1 §3.5, and unchanged here).

**`ExecutionRuntime.invoke(worker_type: str, context: ExecutionContext) -> WorkerResult`**
Purpose: run one Worker. Failure contract: never raises past the caller — failures resolve to a `WorkerResult` with a failure state, consistent with the containment pattern already correct in the fan-out path today. Cancellation: honors `context.cancellation_token`. Determinism: given the same `worker_type` and a replayed `context` (including its captured non-replayable inputs, per Constitution Law 4's amendment), scheduling decisions are reproducible; the Worker's own output may not be, if it calls a model. Versioning: `worker_type` strings are versioned per Law of Contract Stability — adding a worker type is additive; removing one goes through a deprecation window.

**`WorkflowRuntime.execute(workflow: Workflow, context: ExecutionContext) -> WorkflowResult`**
Purpose: run a DAG of Capability/Worker invocations. Transaction semantics: the whole `Workflow` is one Execution Transaction by default; individual nodes may opt into independent containment via their own retry/error-branch configuration (already specified structurally in PI §6.3's `WorkflowNode`). Observability: emits one Event per node transition, not just start/end of the whole workflow — this is the fix for K1's "Explicit State granularity" finding (§1.2 of K1).

**`CapabilityRegistry.resolve(capability: str) -> List[CapabilityAdapter]`** and **`CapabilityResolver.select(candidates: List[CapabilityAdapter]) -> CapabilityAdapter`**
Purpose: two-step, deliberately split — Registry answers "what exists," Resolver answers "which one, right now." Splitting these lets the selection algorithm (health/cost/latency scoring, per the OmniRoute Auto-Combo pattern already flagged as the design reference in the earlier architecture research) evolve independently of what's merely registered. Failure contract: an empty candidate list from Registry is a configuration error (surfaced immediately); a Resolver that can't select from a non-empty list because everything's unhealthy is a Failure Containment event.

**`WorkerRegistry.get(worker_type: str) -> Type[AbstractCognitiveWorker]`**
Purpose: resolve a worker type to its constructable class. Deprecation strategy: same window-based approach as Capability contracts — a worker type isn't removed in the same release it's superseded.

All four are additive to the already-stable surface (`UnifiedMemory`, `GovernanceKernel.evaluate_action()`, `EventStream.append()`) identified in K1 — nothing already stable needs to change shape.

---

## 4. Execution Model

**Request lifecycle:** intent arrives → (future) Intent Verification → compiled into a Workflow or a single Worker invocation → `ExecutionRuntime`/`WorkflowRuntime` runs it, `GovernanceService` evaluated first, every transition evented → result returned.

**Worker lifecycle:** `WorkerState` (already defined: presumably created/running/completed/failed states in `core/workers/base.py`) governs one Worker instance across exactly one `ExecutionRuntime.invoke()` call. Workers are not long-lived; a new instance per invocation, consistent with the "no hidden state outside of resources" principle.

**Boundaries:** the Execution Boundary sits between `WorkflowRuntime` (trusted, kernel-side) and each Capability Adapter (potentially untrusted, always isolated per Law of Separation of Concerns and PI §14.1's sandboxing rules).

**Transactions:** one Workflow = one Execution Transaction by default (§1). A single Worker invocation has no internal sub-steps to roll back, so the concept doesn't apply below the Workflow level.

**Cancellation:** propagates via `context.cancellation_token` through every layer — `ExecutionRuntime`, `WorkflowRuntime`, and into whatever a Capability Adapter is doing, where the Adapter is responsible for honoring it (this is a contract obligation on Adapters, not something the kernel can force from outside an isolated boundary).

**Retries:** per-node retry policy, already structurally specified in PI §6.3 (`retry_policy: RetryPolicy` on `WorkflowNode`) — this session doesn't need to redesign it, just confirm `WorkflowRuntime` is where it's enforced.

**Parallel and nested execution:** parallel fan-out (today's `asyncio.gather` pattern) becomes `WorkflowRuntime` dispatching independent DAG branches concurrently — same mechanism, formalized. Nested execution (a Worker that itself triggers a sub-workflow) is a `WorkflowRuntime` invoking `ExecutionRuntime` invoking a Worker whose own logic calls back into `WorkflowRuntime` — this needs a recursion-depth check at that specific re-entry point, which is exactly what `RecursionGovernor` (already live) is for. No new mechanism needed, just confirming the existing governor covers this path once it's reachable.

**Event emission, state transitions, failure containment:** per §2's `WorkflowRuntime` entry — one Event per node transition, containment scoped to the node unless the workflow's own contract says otherwise.

**Timeouts, interruptibility:** fold into the same `cancellation_token` mechanism — a timeout is a cancellation triggered by a timer rather than a user action; no separate mechanism needed.

---

## 5. Capability Architecture

Replacing "module" with "Capability" concretely, not just terminologically:

- **Discovery:** `CapabilityRegistry` is populated at startup from two sources today: `provider_mesh.py`'s `Provider` subclasses (become inference Adapters) and, once written, `BaseSkill` implementations (`skill_interface.py` — currently zero implementations exist; this is a real, not just organizational, gap).
- **Lifecycle:** register at startup → resolved per-request by `CapabilityResolver` → invoked via `ExecutionRuntime` (a Capability invocation is an Execution, per §1's collapse) → health/availability feeds back into future resolution scoring, mirroring `provider_mesh.py`'s existing `_provider_health()`/`_provider_mark_success()`/`_provider_mark_failure()` functions, which already do exactly this for the inference-only case today and are the concrete pattern to generalize.
- **Permissions, dependencies:** carried on the `CapabilityContract` (§1), consistent with the Constitution's Resource model (identity, lifecycle, version, dependencies, trust, provenance — Invariant 4, six-field version).
- **Versioning, hot reload, evolution:** versioning follows Law of Contract Stability directly. Hot reload and autonomous capability evolution (SkillOpt-style, already tracked in the research corpus) are explicitly **not** in scope for K1.5 — they're Cognitive Phase concerns that consume a stable `CapabilityRegistry`, not something the registry itself needs to support yet.
- **How Skills, Providers, MCP tools, web APIs, native reasoning, future plugins all become Capabilities:** each gets exactly one Adapter implementing the same `CapabilityContract` shape. A Skill is a Capability whose Adapter is local code; a Provider is a Capability whose Adapter is a remote inference endpoint; an MCP tool is a Capability whose Adapter is an MCP client call. One contract, many Adapter kinds — this is precisely what "the kernel owns abstractions; adapters own implementations" (Constitution Part II) means made concrete.

---

## 6. Working Memory Model — Revised From K1

K1 concluded "Working Memory → Context" (Working Memory as the general container, Context as one specific thing placed into it). That direction still holds, but this session's discovery (§0) sharpens what "Context" actually means in practice, because there are now two candidate producers of it:

- The live path (`RetrievalFusionEngine.fuse_search()`) produces a flat `List[SearchResult]` — no structure, no provenance, no contradiction handling.
- The disconnected path (`RetrievalContextBuilder.build()`) produces a real `Context` object (`ContextBlock`s, `ContradictionGroup`s, `ProvenanceRecord`s, deduplicated, token-budgeted) — exactly what the Constitution's glossary means by "Context."

**Recommendation: Working Memory should hold the `RetrievalContextBuilder`-shaped `Context`, not `SearchResult` lists.** The disconnected subsystem is the one that actually matches the Constitution's own vocabulary and the K1 prompt's own frozen principle ("RetrievalContextBuilder produces Context"). This means wiring `RetrievalContextBuilder`/`GraphRAGPipeline` into the live path is not a nice-to-have alongside the Worker-layer fix — it's the same category of fix, on the memory side. Treat these as one combined K2 milestone, not two separate ones (revises K1's migration plan — see §13).

**Full model:**
- **Ownership:** `ContextService` owns Working Memory for the duration of one execution.
- **Scope:** per-execution by default. Nothing persists Working Memory across requests — that's what long-term Memory (`UnifiedMemory`) is for.
- **Visibility:** readable by any Worker within the same `ExecutionContext`; not visible across concurrent, unrelated executions.
- **Mutation:** append/overwrite freely during execution; no external mutation once the execution completes (matches Law of Explicit State — nothing meaningful changes without the change itself being part of that execution's own record).
- **Cleanup:** LRU eviction (per PI §8.1's existing L0 spec) plus hard cleanup at execution end.
- **Snapshot semantics:** the `Context` object placed into Working Memory is itself immutable once assembled (already true of the `Context`/`ContextBlock` dataclasses) — a new retrieval produces a new `Context`, it doesn't mutate the old one. This gives replay for free: the Event log records which `Context` snapshot a decision was made against.
- **vs. Long-term Memory / Knowledge:** unchanged from the Constitution glossary — Working Memory is transient and execution-scoped; Memory and Knowledge are the persistent stores it's assembled *from*.

---

## 7. Worker Architecture

**Base class question (does the request list's nine candidate Workers share one base or compose differently):** one base class, per the Constitution's own principle that a Capability is defined by its contract, independent of what satisfies it — `AbstractCognitiveWorker` already correctly provides the shared contract (governance evaluation, event emission, `WorkerState` lifecycle). Specialization (`PlannerWorker` vs. `CoderWorker` vs. `EvaluatorWorker`) happens through what each subclass's `execute()` does internally and what Capabilities it's permitted to call — composition of *behavior*, inheritance of *contract*. This matches PI §7.1's existing canonical list and needs no redesign, only population — six of the eight canonical types (plus the two new ones this request adds, `IdentityWorker`/`MemoryWorker`/`ReasoningWorker` — noting `Reasoning` was already excluded from kernel vocabulary in §1; a `ReasoningWorker` can still exist as a Worker *type*, it just doesn't need a kernel-level definition of what reasoning *means*) don't exist as classes yet.

**Isolation, permissions, memory access:** each Worker receives a scoped `ExecutionContext` carrying only the Working Memory, governance state, and Capability access it needs — least-privilege, per PI §14.3, enforced by what's threaded through the context object rather than by the Worker trusting itself to behave.

**Supervision, hierarchy:** `SupervisorWorker` (still unbuilt) is the one canonical type explicitly meant to construct/coordinate other Workers — this is where nested execution's recursion-depth governance (§4) actually gets exercised in practice.

**Retries, cancellation, failures:** inherited from `ExecutionRuntime`'s contract (§3) — not reimplemented per Worker type.

---

## 8. State Model

Collapsing the requested twelve-way state split into what's actually distinct, cross-referenced to owners already established above:

| State category | Distinct from the others? | Owner |
|---|---|---|
| Kernel State | Yes — registries, governor counters | Kernel Runtime |
| Execution / Runtime / Working State | These three are one thing (the live `ExecutionContext` of one in-progress execution) under three names in the request list | Execution Runtime |
| Memory / Knowledge State | Already the L0–L4 model, unchanged | Memory Service |
| Persistent State | Same as Memory State — not a separate category | Memory Service |
| Workflow State | Yes — which node of a DAG is active, per instance | Workflow Runtime |
| Capability State | Yes — health/availability per Adapter | Capability Resolver |
| Graph State | Not separate — Graph is an index over Memory State, not its own state category (§1) | Memory Service |
| User / Identity State | Out of scope this session (§1's Identity exclusion) | — |

**Recovery, replay, causal ordering, event sourcing:** all already correctly anchored to `EventStream` — nothing here needs a new mechanism, just confirming every state category above has its transitions represented as Events per Law of Explicit State. This is currently true at the orchestrator-lifecycle level and not yet true at finer grain (K1's own finding) — the gap is coverage depth, not a missing mechanism.

---

## 9. Dependency Graph

```
Kernel (Governance, Events, Registries)
  ↓
Execution Runtime / Workflow Runtime
  ↓
Workers
  ↓
Capabilities (Registry + Resolver + Adapters)
  ↓
Memory Service (owns Retrieval as a Capability it exposes)
  ↓
External Systems (via Adapters only)
```

**Forbidden, explicitly:**
- Capabilities may not depend on specific Workers (inverts the direction — a Capability must be callable by any Worker with permission, not coupled to one).
- Memory Service may not depend on Workflow Runtime (would create a cycle — Workflow Runtime already depends on Memory Service transitively through Capabilities).
- Adapters may not be imported directly by anything above the Capability layer — confirmed already true in production for `UnifiedMemory`'s own backends (K1's own audit verified `Orchestrator` never touches `._storage`/`._vector`/`._graph` directly); the same discipline needs to extend to the new Capability layer once it exists.

**No exceptions found that need justifying** — the current codebase's one real layering violation (Orchestrator doing worker-shaped work inline) is exactly what K2 fixes, not a case of the dependency graph itself needing an exception.

---

## 10. Interface Freeze Proposal

**Mature enough to freeze at K4:** `ExecutionContext`, `Worker` (the `AbstractCognitiveWorker` contract), `Evidence`, `Context`/`ContextBlock`, `Event`, `Governor`, `GovernanceResult`/`GovernanceVerdict` — all already stable, already tested, not expected to change shape based on anything found this session.

**Not yet mature — explicitly not frozen:** `CapabilityContract` (zero real implementations exist yet; freezing an interface with zero real users risks freezing the wrong shape), `WorkflowNode`'s full field set (structurally specified in PI §6.3 but not yet implemented against real workflows), `WorkerRegistry`/`CapabilityRegistry`/`CapabilityResolver` APIs (§3's contracts are a strong starting proposal, not proven by use yet). These should be built in K2, exercised, and frozen at K4 as originally planned — not frozen now, before anything has used them.

---

## 11. Architectural Risks

| Risk | Severity | Probability | Impact | Mitigation | Blocks K2? |
|---|---|---|---|---|---|
| Wiring Workers into the hot path regresses the one confirmed-correct containment behavior (`return_exceptions=True` fan-out) | Critical | Medium | A single Capability failure could crash a whole request instead of degrading gracefully | Explicit regression test asserting per-node containment survives the migration, before merging | No — mitigated by test discipline, not a blocker |
| Two full retrieval stacks (live simple path, disconnected sophisticated path) get merged incorrectly, silently changing retrieval quality | High | Medium | Answers could get worse before anyone notices, since both paths "work" | A/B comparison during K2.2 — run both, compare a fixed query set, before cutting over | No, but should gate the specific cutover step within K2 |
| `MemoryGovernor`'s interface redesign breaks something not yet discovered | Medium | Low | Zero current consumers found, so low actual risk, but not exhaustively verified | Full regression suite before/after, same discipline the hardening report already used | No |
| README/PRODUCT.md drift continues to mislead new contributors during K2 | Medium | High (already happening) | Onboarding confusion, not architectural risk | Cheap fix, doesn't block K2, should happen in parallel | No |
| Distributed/queue-mode execution eventually needs `Scheduler`, and retrofitting it after `ExecutionRuntime`/`WorkflowRuntime` are frozen at K4 is harder than designing for it now | Low | Low (years out per existing roadmap) | Possible K4+ interface revision | Explicitly deferred, not ignored — noted here so it isn't a surprise later | No |

Nothing found rises to "blocks K2" — every risk has a mitigation that fits inside K2's own test discipline, matching the standard already set by this repository's own hardening session.

---

## 12. Roadmap Validation

The existing K1→K4 + Parallel Cognitive Development shape, refined by K1's own K2 sub-phasing, still holds. One addition based on this session's discovery: **K2.2 (originally "WorkflowEngine wrapping decomposer.py") is revised** — see §13. No other reordering is justified; Self Identity, Reflection, Planning, Skills, External Knowledge, KAG, Multi-Agent Runtime, Web/Developer Platform, Production Hardening all still correctly sit downstream of a Kernel that doesn't exist as a coherent, wired system yet.

---

## 13. Migration Strategy — K1 to K2 (Revised)

K1's migration plan proposed K2.2 as "WorkflowEngine (minimal), wrapping `decomposer.py`'s existing Task/DAG output." That recommendation is revised:

**Was:** wrap the simple, narrow `decomposer.py` task-splitter as the first real WorkflowEngine consumer.
**Now:** `GraphRAGPipeline`'s own internal design (pluggable `IntentAnalyzer`, `TraversalStrategy`, `RankingStrategy`, already built and tested) is a better reference pattern for `WorkflowNode` design than `decomposer.py` — it's a real, working example of staged, pluggable execution already living in this codebase. K2.2 should now be scoped as: (a) wire `RetrievalContextBuilder`/`GraphRAGPipeline` into the live `ContextAssemblyEngine` path (closing §0/§6's finding), using that wiring exercise itself to validate the `WorkflowNode` shape against a real pluggable pipeline, then (b) generalize from there. This combines what were two separate K1 findings (Worker disconnection, and now retrieval-stack disconnection) into one coherent K2 milestone rather than two uncoordinated ones — both are instances of the same underlying problem.

Everything else in K1's migration plan (§4 of that document) stands unchanged.

---

## 14. Technical Debt Report — Delta From K1

No new debt category introduced. One item's severity is revised: **the retrieval-stack disconnection (§0) is now Critical, not previously catalogued** — it belongs alongside K1's Worker-layer finding in the Kernel debt tier, not filed separately under Retrieval debt, because it's architecturally the same failure mode (sophisticated subsystem, zero wiring), not a distinct kind of problem.

---

## 15. Final Readiness Assessment

**READY FOR K2 — KERNEL CORE IMPLEMENTATION.**

This session's re-audit found one thing K1 missed, and it strengthened rather than weakened the case for proceeding: the pattern K1 identified (build thoroughly, never wire in) is now confirmed twice, independently, in two different subsystems built by different sessions — which means it's a *process* pattern worth naming explicitly for K2, not a one-off oversight. **Recommend K2 begin with an explicit checklist step: "does this newly-built piece get wired into the live path before the session ends," treated as a first-class deliverable, not an assumed follow-up.** That single practice, applied going forward, would have caught both disconnections at the moment they were introduced rather than two audits later.

Everything else — vocabulary, service model, APIs, execution model, Working Memory, Capability architecture, Worker architecture, state model, dependency graph — is specified precisely enough that K2 can proceed as an implementation session, not another design session, matching this session's own success criteria.

---

*K1.5 complete. No implementation performed. Two Critical K2 milestones now identified and merged into one (§13): Worker-layer wiring and retrieval-stack wiring, both instances of the same disconnection pattern, both blocking real Kernel behavior, neither individually large enough to need its own dedicated session if scoped together deliberately.*
