# OCBrain — K2 Implementation Plan

**Status:** Approved for execution.
**Prerequisite:** Kernel Architecture v1.0 frozen. Repository finalized.
**Scope:** Kernel runtime implementation only. No cognitive-phase features.

---

## K2.1 — Execution Runtime

### Objectives

Build the canonical `ExecutionRuntime` — the service that constructs and invokes one Worker for one unit of work. This is the foundational piece that unblocks all subsequent K2 milestones.

### Dependencies

- KERNEL_ARCHITECTURE_v1.0.md §7 (Execution Model)
- KERNEL_ARCHITECTURE_v1.0.md §9 (Worker Model)
- Existing: `AbstractCognitiveWorker`, `GovernanceKernel`, `EventStream`

### Deliverables

| Deliverable | File | Type |
|---|---|---|
| ExecutionContext | `core/runtime/execution_context.py` | NEW |
| CancellationToken | `core/runtime/cancellation.py` | NEW |
| WorkingMemory | `core/runtime/working_memory.py` | NEW |
| ExecutionRuntime | `core/runtime/execution_runtime.py` | NEW |
| WorkerRegistry | `core/runtime/worker_registry.py` | NEW |
| PlannerWorker (minimal) | `core/workers/planner.py` | NEW |
| Worker base class update | `core/workers/base.py` | MODIFY |
| Orchestrator delegation | `core/orchestrator.py` | MODIFY |
| Composition root wiring | `main.py` | MODIFY |

### Tests

- Unit: `ExecutionRuntime.invoke()` returns `WorkerResult` for success and failure
- Unit: `WorkerRegistry.get()` resolves registered types, returns error for unknown
- Unit: `CancellationToken` propagation through `_run()`
- Unit: `WorkingMemory` allocation and cleanup
- Integration: `ExecutionRuntime.invoke()` → `Worker.execute()` → `GovernanceKernel.evaluate_action()` → `EventStream.append()`
- Regression: `asyncio.gather(..., return_exceptions=True)` containment behavior preserved
- Regression: Existing orchestrator tests pass after delegation

### Expected Repository Changes

- 6 new files in `core/runtime/` and `core/workers/`
- 3 modified files (`base.py`, `orchestrator.py`, `main.py`)
- `WorkerContext` deprecated (superseded by `ExecutionContext`)
- `MemoryCuratorWorker` wired into composition root for the first time

### Success Criteria

1. `ExecutionRuntime.invoke("memory_curator", context)` successfully executes `MemoryCuratorWorker._run()`
2. Governance evaluation fires before `_run()` (template method pattern preserved)
3. Events emitted for worker lifecycle transitions
4. Failures contained as `WorkerResult(success=False)` — never exceptions
5. CancellationToken honored in `_run()`
6. Working Memory allocated at invocation, cleaned up after
7. All existing tests pass without modification

### Implementation Order

```
1. CancellationToken (standalone, no dependencies)
2. WorkingMemory (standalone, no dependencies)
3. ExecutionContext (depends on CancellationToken, WorkingMemory)
4. WorkerRegistry (standalone)
5. ExecutionRuntime (depends on WorkerRegistry, ExecutionContext)
6. Modify AbstractCognitiveWorker.execute() to accept ExecutionContext
7. Modify MemoryCuratorWorker._run() to accept ExecutionContext
8. Register MemoryCuratorWorker in WorkerRegistry at composition root
9. PlannerWorker (minimal — wraps current classify→dispatch as a worker)
10. Modify Orchestrator to delegate through ExecutionRuntime
```

### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Wiring workers into hot path regresses containment behavior | Critical | Explicit regression test before merging |
| `WorkerContext` → `ExecutionContext` migration breaks `MemoryCuratorWorker` | Low | Only one consumer, never instantiated in production |
| Orchestrator delegation changes response format | Medium | A/B comparison of outputs before and after |

---

## K2.2 — Workflow Runtime

### Objectives

Implement the canonical `WorkflowRuntime` — the service that coordinates a DAG of `ExecutionRuntime` invocations with retry logic, checkpoints, and HITL gates.

### Dependencies

- **K2.1 must be complete** (WorkflowRuntime calls ExecutionRuntime)
- KERNEL_ARCHITECTURE_v1.0.md §8 (Workflow Model)
- Existing: `EventStream` (checkpoints), `core/decomposer.py` (reference pattern)

### Deliverables

| Deliverable | File | Type |
|---|---|---|
| WorkflowDefinition, WorkflowNode, WorkflowEdge, RetryPolicy | `core/workflow/definition.py` | NEW |
| WorkflowInstance, WorkflowState | `core/workflow/instance.py` | NEW |
| WorkflowRuntime | `core/workflow/runtime.py` | NEW |
| WorkflowResult | `core/workflow/result.py` | NEW |
| Wire RetrievalContextBuilder into live path | `core/memory/assembly.py` | MODIFY |

### Tests

- Unit: DAG topological ordering with simple linear and branching workflows
- Unit: RetryPolicy backoff behavior (exponential, max retries, retryable errors)
- Unit: Checkpoint creation and resume from checkpoint
- Unit: Cancellation propagation through workflow nodes
- Unit: Error branch routing on node failure
- Integration: Multi-node workflow executing through ExecutionRuntime
- Integration: A/B comparison of retrieval quality (RCB vs. legacy RFE)
- Regression: Existing retrieval tests pass after RCB wiring

### Expected Repository Changes

- 4 new files in `core/workflow/`
- 1 modified file (`core/memory/assembly.py`)
- `RetrievalContextBuilder` + `GraphRAGPipeline` wired into live retrieval path

### Success Criteria

1. A 3-node linear workflow executes successfully
2. A workflow with a failing node retries per RetryPolicy and recovers
3. A workflow with a failing node and error_branch routes correctly
4. Checkpoint/resume works across workflow suspension and resumption
5. Per-node events emitted to EventStream
6. RetrievalContextBuilder produces structured `Context` objects in the live path
7. Retrieval quality is equal to or better than legacy path (A/B comparison)

### Implementation Order

```
1. WorkflowDefinition, WorkflowNode, WorkflowEdge, RetryPolicy (data classes)
2. WorkflowInstance, WorkflowState (state management)
3. WorkflowResult (result aggregation)
4. WorkflowRuntime.execute() (core DAG execution loop)
5. WorkflowRuntime.resume() (checkpoint-based resumption)
6. WorkflowRuntime.cancel() (cancellation propagation)
7. Wire RetrievalContextBuilder into ContextAssemblyEngine
8. A/B comparison testing before cutover
```

### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Retrieval quality regression during RCB cutover | High | A/B comparison with fixed query set before switching |
| DAG cycle detection missing | Medium | Validate DAG structure at definition time, not runtime |
| Checkpoint data format not forward-compatible | Low | Version checkpoint payloads from day one |

---

## K2.3 — Capability Registry

### Objectives

Implement the canonical `CapabilityRegistry` and `CapabilityResolver` — the services that generalize the existing provider health-tracking pattern to all capabilities.

### Dependencies

- **Can proceed in parallel with K2.2 once K2.1 lands**
- KERNEL_ARCHITECTURE_v1.0.md §10 (Capability Model)
- Existing: `provider_mesh.py` (reference pattern, live)

### Deliverables

| Deliverable | File | Type |
|---|---|---|
| CapabilityAdapter Protocol | `core/capabilities/adapter.py` | NEW |
| CapabilityRegistry | `core/capabilities/registry.py` | NEW |
| CapabilityResolver | `core/capabilities/resolver.py` | NEW |
| Provider wrapper adapters | `core/provider_mesh.py` | MODIFY |

### Tests

- Unit: CapabilityRegistry register/resolve/list
- Unit: CapabilityResolver selection by health score
- Unit: CapabilityResolver behavior when all candidates unhealthy
- Unit: Provider satisfies CapabilityAdapter Protocol (structural typing check)
- Integration: Worker resolves capability through registry, invokes through adapter
- Regression: Existing provider_mesh tests pass after wrapping

### Expected Repository Changes

- 3 new files in `core/capabilities/`
- 1 modified file (`core/provider_mesh.py`)
- Existing Provider classes wrapped as CapabilityAdapters

### Success Criteria

1. `CapabilityRegistry.resolve("inference")` returns wrapped Provider adapters
2. `CapabilityResolver.select()` picks the healthiest available adapter
3. Existing `Provider` classes satisfy `CapabilityAdapter` Protocol without inheritance changes
4. `mark_success()` / `mark_failure()` affect future resolution scoring
5. All existing provider_mesh tests pass

### Implementation Order

```
1. CapabilityAdapter Protocol definition
2. CapabilityRegistry (register, resolve, list)
3. CapabilityResolver (select with health scoring)
4. Wrap OllamaProvider as CapabilityAdapter
5. Wrap GenericOpenAICompatibleProvider as CapabilityAdapter
6. Register adapters at composition root
7. Integration test: Worker → Registry → Resolver → Adapter
```

### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Protocol structural typing misses a field at runtime | Low | mypy static check + runtime Protocol conformance test |
| Provider.generate() → Adapter.invoke() naming mismatch | Low | Thin wrapper method, not rename |
| Registry populated but never used (same disconnection pattern) | Medium | Wire into at least one Worker before session ends |

---

## K2.4 — Governance Completion

### Objectives

Complete the governance subsystem by reconciling `MemoryGovernor`'s interface, implementing the remaining governors, and ensuring per-capability governance evaluation.

### Dependencies

- **K2.1 should be complete** (governance evaluation happens inside Workers)
- KERNEL_ARCHITECTURE_v1.0.md §14 (Governance)
- Existing: `GovernanceKernel`, `Governor` base class, 3 live governors

### Deliverables

| Deliverable | File | Type |
|---|---|---|
| MemoryGovernor interface reconciliation | `core/governance/memory_governor.py` | MODIFY |
| OrchestrationGovernor | `core/governance/orchestration_governor.py` | NEW |
| AgentGovernor | `core/governance/agent_governor.py` | NEW |
| ConversationGuardrails | `core/governance/conversation_guardrails.py` | NEW |

### Tests

- Unit: `MemoryGovernor.evaluate()` conforms to `Governor` base class interface
- Unit: `OrchestrationGovernor` evaluates workflow-level actions
- Unit: `AgentGovernor` enforces agent-level permissions
- Unit: `ConversationGuardrails` applies conversation safety rules
- Integration: All governors registered in `GovernanceKernel`, chain evaluation works
- Integration: Full governance chain evaluates worker + capability + memory actions
- Regression: Existing governor tests pass after MemoryGovernor interface change

### Expected Repository Changes

- 3 new files in `core/governance/`
- 1 modified file (`core/governance/memory_governor.py`)

### Success Criteria

1. `MemoryGovernor` satisfies the `Governor` base class interface
2. `MemoryGovernor` registered in `GovernanceKernel` at composition root
3. All new governors implement `evaluate(action: GovernanceAction) -> GovernanceResult`
4. GovernanceKernel chain evaluation processes all governors in order
5. REJECT from any governor terminates the chain

### Implementation Order

```
1. Reconcile MemoryGovernor.validate_ingestion() → Governor.evaluate()
2. Register MemoryGovernor in GovernanceKernel at main.py
3. OrchestrationGovernor (workflow-level governance)
4. AgentGovernor (agent-level permissions)
5. ConversationGuardrails (safety rules)
6. Full integration test with all governors
```

### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| MemoryGovernor interface change breaks undiscovered consumers | Low | Zero consumers found (grep verified) |
| New governors too restrictive, blocking normal operation | Medium | Permissive defaults, logging-only mode initially |
| Governor evaluation order matters | Low | Document order in composition root |

---

## Cross-Milestone Summary

| Milestone | New Files | Modified Files | Complexity | Parallelizable |
|---|---|---|---|---|
| K2.1 — Execution Runtime | 6 | 3 | High | No (must go first) |
| K2.2 — Workflow Runtime | 4 | 1 | Medium | After K2.1 |
| K2.3 — Capability Registry | 3 | 1 | Low | After K2.1, parallel with K2.2 |
| K2.4 — Governance Completion | 3 | 1 | Medium | After K2.1 |
| **Total** | **16** | **6** | | |

### Recommended Execution Sequence

```
Week 1-2: K2.1 — Execution Runtime (unblocks everything)
Week 3-4: K2.2 + K2.3 in parallel
Week 5:   K2.4 — Governance Completion
Week 6:   Integration testing, final validation
```

### K2 Exit Criteria

K2 is complete when:

1. All 16 new files implemented and tested
2. All 6 modified files updated and regression-tested
3. At least one Worker (MemoryCuratorWorker) executes through ExecutionRuntime in production
4. At least one Workflow executes through WorkflowRuntime
5. RetrievalContextBuilder is the live retrieval path
6. All governors registered and evaluating
7. All public contracts match KERNEL_ARCHITECTURE_v1.0.md §18
8. Constitution compliance verified (K3 preparation)

---

*K2 Implementation Plan complete. No implementation performed. Planning only.*
