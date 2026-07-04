# OCBrain Recovery Report

## Objective
This report details the missing architectural components that must be restored based on the discrepancies between the physical repository state and the authoritative documents (`OCBRAIN_FUTURE_ARCHITECTURE.md`, `STATUS.md`).

## Missing Core Modules to Restore

### 1. The Worker Framework (`core/workers/`)
**Impact:** Critical. Without workers, OCBrain cannot execute specialized tasks or self-improve.
* **`cognitive_worker.py`**: Base class implementing the `ToolLoopAgent` and `stopWhen` lifecycle.
* **`specialist_workers.py`**: Needs to contain canonical types: `ReActWorker`, `PlannerWorker`, `ReflectionWorker`, and the explicitly required `MemoryCuratorWorker` (for Active Memify).
* **`system_prompt_registry.py`**: The 7-system validated prompt registry.

### 2. The Governance Kernel (`core/governance/`)
**Impact:** High. Required to prevent runaway loops and enforce system boundaries.
* **`governance_kernel.py`**: Must implement hard limits (recursion depth, step limits, token budgets) and HITL (Human-In-The-Loop) escalations.
* **Missing Governors**: Needs `OrchestrationGovernor`, `AgentGovernor`, and `ConversationGuardrails` to complete the canonical 5 governors.

### 3. The Event & Workflow Subsystems (`core/events/`, `core/workflow/`)
**Impact:** High. Required for durable execution (v4.4.8) and long-horizon tasks.
* **`core/events/event_stream.py`**: Immutable WAL, pub/sub event router, and replay logic.
* **`core/workflow/workflow_engine.py`**: DAG-based execution, partial execution states, retry logic, and HITL wait points.

### 4. Pipeline & Observability
**Impact:** Medium. Important for safety and debugging.
* **`core/pipeline/pipeline_middleware.py`**: PII filtering, safety checks, and memory injection.
* **`core/observability/observability_framework.py`**: Counters, spans, and health checks to complement the existing tracer.

### 5. Skills & API
**Impact:** Medium.
* **`core/skills/skill_registry.py`**: SemVer handling and MCP auto-exposure.

## Recommended Restoration Strategy
Based on the execution mandate, we should restore these modules in dependency order:
1. **Governance & Events**: Establish the rules and the immutable log first.
2. **Workers**: Implement the worker classes since they depend on governance.
3. **Workflow**: Implement the engine that coordinates the workers.
4. **Pipeline & Observability**: Add the middleware and monitoring.
