# ADR-K4.2-H-08: Trace and Operation Identifier Semantics

**Status:** ACCEPTED
**Date:** August 16, 2026
**Author:** K4.2-H1 packet (Contract Evolution Foundation)
**Scope:** `core/cognitive/intent.py`, `core/cognitive/planner.py`, `core/cognitive/compiler.py`.

---

## 1. Context

Diagnostic events across the cognitive pipeline carried no consistent way to correlate "everything that happened during one user request" (a trace) from "one top-level cognitive-stage invocation" (an operation) from "one sub-step within that invocation" (a stage). No `correlation_id` is introduced — `trace_id`/`operation_id`/`stage_tag` cover the same ground with clearer, non-overlapping ownership.

## 2. Decision

- **`trace_id`**: the existing observability mechanism (`core/observability/tracer.py`'s `get_trace_id()`, a `ContextVar` accessor). Stable across an entire request/trace by construction — no new propagation code needed; a re-plan loop calling `plan()` repeatedly within the same async context naturally gets the same `trace_id` on every call.
- **`operation_id`**: generated fresh, only, by the two top-level cognitive-stage entrypoints — `plan()` and `compile()`. `discover_capabilities()` and `_extract_constraints()` do **not** generate their own; they receive the parent's `operation_id` as a passthrough parameter and share it, distinguished by `stage_tag`.
- **`stage_tag`**: a plain string discriminator for sub-operations within one `operation_id` — `"constraint_extraction"`, `f"capability_discovery:{request.subgoal_ref}"` (using the request's own `subgoal_ref`, e.g. `goal_id:0`, `goal_id:1`, rather than a separately-invented step index). No new stage-ID system is introduced.
- `PlannerResult` gains `operation_id: Optional[str] = None`, surfaced from `plan()`'s own generation, so Orchestrator can reference the same identifier in its own diagnostic events (e.g. `cognitive.planner_impasse_terminal`) without pre-generating and injecting one itself.

## 3. Consequences

- Verified directly: `plan()`/`compile()` each generate a fresh `operation_id` on every call while sharing the same `trace_id` (`test_each_plan_call_generates_a_fresh_operation_id`, `test_each_compile_call_generates_a_fresh_operation_id`); repeated `capability_discovery` calls within one `_decompose()` pass share one `operation_id` with different `stage_tag`s (`test_event_includes_trace_and_stage_tag`).
- The re-plan-retains-trace-but-changes-operation_id acceptance criterion is proven at the Orchestrator level, where the re-plan loop actually lives (`tests/test_orchestrator_recovery.py`), not inside `plan()` itself, which has no loop of its own.
- `CompilationResult` does not carry `operation_id` forward — nothing downstream currently needs to reference `compile()`'s own operation_id after the call returns.

## 4. Alternatives considered

- **A `correlation_id` field, as an earlier draft of this decision used**: rejected in the final pass — `trace_id`/`operation_id`/`stage_tag` are more precise about what's actually being correlated at each level; explicitly "no correlation_id."
- **Generating `operation_id` inside `discover_capabilities()` itself**: rejected — it is nested within Planner's `_decompose()`, not a top-level entrypoint; giving it its own `operation_id` would fragment one logical `plan()` operation across multiple identifiers for no benefit.
