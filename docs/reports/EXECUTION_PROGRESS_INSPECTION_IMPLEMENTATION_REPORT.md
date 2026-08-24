# OCBrain Execution Progress and Inspection
## Implementation Report

**Branch:** `feature/execution-progress-inspection`  
**Base:** `origin/main`  
**Date:** 2026-08-24

## A. Root Cause

The original long-generation failure was caused by two fixed 60-second provider ceilings: `safe_llm_call()` and the shared HTTP client's read timeout. Ollama's `mistral` generation of a 1000-word story exceeded that limit. The frontend fallback, `d.answer || 'No response.'`, hid the useful diagnostic when the answer became empty.

This implementation changes the provider/network ceiling to `OCBRAIN_LLM_TIMEOUT_SECONDS`, defaulting to 600 seconds. The execution watchdog remains the authoritative per-execution deadline and can cancel work through the existing `CancellationToken`.

## B. Architecture Reconciliation

The subsystem extends, rather than replaces, existing contracts:

- `ExecutionContext` remains the context passed to workers.
- `CancellationToken` remains the only cancellation mechanism.
- `ExecutionBudget` governs one execution's startup/progress/hard limits.
- Existing recovery budgets remain separate and authoritative.
- `ModelRouter`, `ProviderMesh`, and provider adapters are unchanged in layering.
- `EventStream` is the canonical persisted event backbone and real-time source.
- The in-memory registry is only an indexed snapshot/SSE delivery adapter; it is not a second event bus or persistence layer.

No Reliability, C-MoE, Kernel Constitution, or accepted K4.2 architecture files were modified.

## C. ExecutionGraph Design

`core/runtime/execution_graph.py` introduces:

- `ExecutionStatus`: pending, running, completed, failed, cancelled, stalled, recovering, waiting, blocked.
- `ExecutionNode`: parent/child identity, lifecycle timestamps, qualitative and quantitative progress, current action, failure and recovery fields.
- `ExecutionGraph`: arbitrary-depth parent-child graph with authoritative state transitions and snapshots.
- `ExecutionRegistry`: process-local lookup of active/recent graphs and bounded event queues for SSE.

The graph is created before workflow execution. Workflow definition nodes become runtime nodes, but their status is updated only by actual execution transitions. Dynamic children can be added during execution.

## D. Progress Model

`ProgressMonitor` provides generic operations:

- `report_progress()`
- `record_status()`
- `record_completion()`
- `record_failure()`
- `record_recovery()`

Progress is evidence-based. Quantitative values are optional; `progress_units` supports counters such as `{ "tokens": 1247 }` or `{ "completed": 3, "total": 5 }`. The streaming API reports aggregated chunk counts rather than writing one event per token.

Events are persisted and broadcast through `EventStream` using `execution.*` event names. No hidden model reasoning or raw prompts are included in progress payloads.

## E. Watchdog Integration

`ExecutionWatchdog` observes the graph and `ExecutionBudget`:

- startup and hard deadlines are represented by the budget;
- progress is measured using `last_progress_at`;
- healthy active nodes remain running while progress continues;
- nodes with no meaningful progress for `progress_deadline_seconds` become `stalled`;
- hard deadline expiry calls `CancellationToken.cancel()`;
- bounded budget extension is enforced by `max_extension_seconds`.

The watchdog does not create a second timeout or cancellation path. It is stopped on normal completion, workflow failure, validation failure, and unexpected runtime failure.

## F. UI Design

The existing chat UI now includes:

1. A compact `Thinking...` control for active executions.
2. An expandable execution panel showing the live task tree.
3. Status glyphs for pending, running, completed, failed, stalled, recovering, waiting, blocked, and cancelled.
4. Selection of the exact clicked node, including nested children.
5. Selected-node details: status, current action, progress evidence, elapsed time, last progress, failure, and recovery.
6. Live refresh from `GET /executions/{execution_id}/events` plus snapshots from `GET /executions/{execution_id}`.

The final answer remains separate from the inspection panel. The UI never infers completion from elapsed time.

## G. Security Boundary

`core/runtime/projection.py` explicitly allowlists user-visible fields. Internal execution details, private metadata, prompts, hidden reasoning, credentials, and stack traces are excluded. Failure messages are truncated and sensitive-looking values containing API keys, passwords, authorization headers, or token assignments are replaced with a generic diagnostic.

## H. Tests

Added `tests/test_execution_inspection.py` covering:

- nested graph creation and parent-child selection;
- authoritative status transitions;
- evidence-based progress and timestamps;
- user-safe projection excluding `execution_detail`;
- bounded budget extension;
- watchdog hard-deadline cancellation.

Validation performed:

- `tests/test_execution_inspection.py`, `tests/test_execution_runtime.py`: **40 passed**
- `tests/test_workflow_runtime.py`, `tests/test_execution_runtime.py`, `tests/test_orchestrator_recovery.py`: **64 passed**
- `tests/test_runtime_limits.py`, inspection, workflow tests: **26 passed**

## I. Original Reproduction

- Short requests can continue through the existing provider path.
- The former fixed 60-second provider ceiling is replaced by a configurable 600-second default, allowing healthy long-form generation to continue while graph progress is observed.
- A diagnostic follow-up can query the execution snapshot by `execution_id`; the API now preserves that identifier in the response metadata.

A full live 1000-word Ollama run was not used as an automated test because it depends on the local model process and can take several minutes. The timeout boundary and exception behavior remain covered by existing runtime tests and the earlier direct reproduction.

## J. Freeze Integrity

Verified by scope and test execution:

- Reliability architecture: unchanged.
- C-MoE architecture: unchanged.
- Kernel Constitution: unchanged.
- Accepted K4.2 ADRs: no edits.
- Operation recovery budget: not merged with execution budget.
- Cancellation: existing `CancellationToken` remains canonical.
- Event architecture: existing `EventStream` extended, not duplicated.

## K. Future Extension Points

The generic node contract can represent workers, capabilities, tools, and durable work units without a second progress system. Future work can add:

- checkpoint persistence using existing EventStream checkpoints;
- resume/replay by rebuilding graph state from events;
- worker-emitted child nodes;
- capability/provider metadata through internal detail fields and safe projection rules;
- OCBrain Studio views consuming the same snapshots and ordered events;
- multi-node execution using the existing parent-child relationship.

## Files Added or Changed

- `core/runtime/execution_graph.py`
- `core/runtime/execution_budget.py`
- `core/runtime/progress.py`
- `core/runtime/watchdog.py`
- `core/runtime/projection.py`
- `core/runtime/limits.py`
- `core/runtime/network.py`
- `core/workflow/runtime.py`
- `core/orchestrator.py`
- `interface/api.py`
- `interface/web/index.html`
- `tests/test_execution_inspection.py`
