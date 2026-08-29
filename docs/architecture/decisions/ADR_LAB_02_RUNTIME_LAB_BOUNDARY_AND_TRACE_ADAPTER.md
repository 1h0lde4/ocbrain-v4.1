# ADR-LAB-02: Runtime/Lab Package Boundary & Trace Adapter Source Priority

**Status:** PROPOSED — pending human review before Slice 2 (contracts) begins
**Date:** August 28, 2026
**Author:** Agent Evaluation & Reliability Lab research session (parallel track, branch `eval-lab/research-and-architecture`)
**Scope:** New `eval_lab/` package (not yet created); read-only consumption of `core/events/`, `core/runtime/`, `core/workers/`.

---

## 1. Context

The mission requires the Lab to consume runtime events without the runtime ever importing the Lab, and without duplicating runtime truth. Two repository-specific facts make the naive version of this harder than the mission assumed:

1. **The event backbone is already fragmented** (`KNOWN_ISSUES.md` DEBT-004/005): `EventBus` (in-process pub/sub, no persistence), `EventStream` (durable, replayable, SQLite WAL, supports `create_checkpoint()`), and `KnowledgeEvent` (L4 archive) are three separate mechanisms, not one canonical stream.
2. **"Evaluator" is already a taken name.** `core/workers/evaluator.py` (`EvaluatorWorker`, K4.2 Packet 07) is an in-loop, single-task, self-assessment cognitive worker producing `EvaluationRecord`s — a different concept from this Lab, which evaluates trajectories externally and across runs. Nesting the Lab under `core/evaluation/` would put two different "evaluat-" concepts in the same namespace in a codebase that already has one unreconciled duplication problem in this exact shape (DEBT-016, two watchdog implementations).

## 2. Decision

- The Lab lives at **top-level `eval_lab/`**, sibling to `core/`, `evals/`, `tests/` — not nested inside `core/`. This makes the "runtime does not depend on the Lab" invariant checkable by a simple grep (`core/` should never reference `eval_lab/`) rather than requiring package-level dependency analysis.
- `evals/run_eval.py` (a 75-line placeholder against a mocked subject call) is left in place for this slice, explicitly noted as superseded rather than removed — removing it is a separate, later commit once `eval_lab` has an equivalent smoke case to replace it with.
- The trace adapter (`eval_lab/adapters/trace_normalizer.py`, to be built in Slice 3) treats `EventStream` as the **primary and canonical** source, since it is durable and already supports replay. `EventBus` and `KnowledgeEvent` emissions are consumed as **supplementary** signal — the trajectory's correctness must never depend on an `EventBus`-only event that has no durable counterpart.
- The adapter explicitly special-cases **two** watchdog/progress event families (model-router-facing: `execution_watchdog.py`/`progress_monitor.py`; graph-aware: `watchdog.py`/`progress.py`/`execution_graph.py`/`projection.py`) per DEBT-016, rather than assuming a single canonical watchdog schema. This is a deliberate, documented workaround — not a design the Lab prefers — and should be revisited the moment DEBT-016 is resolved as its own packet.
- `EvaluatorWorker`/`ReflectionWorker` output (`EvaluationRecord`, reflection `KnowledgeEntry`) is consumed by the trace adapter as **one input feature** on the trajectory, never as an evaluation result. The Lab's own evaluators are what produce `EvaluationResult` records; an in-loop self-assessment is evidence *about* the trajectory, not a substitute for external evaluation.

## 3. Consequences

- Any future refactor that unifies the event backbone (resolving DEBT-004/005) simplifies the adapter; it does not require a redesign, because the adapter was never written to assume a single source.
- If DEBT-016 is resolved before the trace adapter ships, the dual-schema handling becomes dead code that should be removed at that time — flagged here so it isn't mistaken for permanent architecture.
- A `core/` → `eval_lab/` import would be a review-blocking defect under this ADR, not a style preference.

## 4. Amendment (2026-08-28): Trajectory Snapshot/Branch Shape (Future Scope, Not Implemented)

This amendment does not change the trace-adapter decision above. It records one shape constraint for Slice 2's `Trajectory` contract, so it doesn't need breaking changes later: current research on counterfactual agent evaluation (see the accompanying report, §7a.6 — "Causal Agent Replay," "prefix branching," "Hierarchical Experimentalist Agents") converges on the same primitive — an immutable snapshot of full state at a decision point, restorable into independent branches, with determinism as a precondition for the branches being genuinely comparable. The Lab does not build a branching engine in this slice or the next (per the mission's explicit instruction). The only thing this amendment asks Slice 2 to do is avoid a `Trajectory` shape that would make adding `TrajectorySnapshot`/`BranchPoint` later a breaking change — e.g., trajectory events should be identifiable by a stable reference that a future snapshot could point to, rather than only by array position. Concretely, this affects **field design, not scope**: no snapshot/branch code exists until some future slice actually asks for it.

## 5. Alternatives considered (amendment)

- **Design the `Trajectory` contract with no forward compatibility for branching, revisit if/when branching is actually built**: rejected as the default, specifically because the research above shows determinism-at-the-branch-point is a precondition that's much cheaper to design for now (stable event references) than to retrofit later (once historical trajectories already exist without them).

## 6. Alternatives considered (original)

- **`core/evaluation/`**: rejected for the naming-collision reason above, independent of any technical merit — this codebase has direct, recent evidence (DEBT-016) of what unreconciled same-name-different-concept code paths cost.
- **Build a fourth unified event stream inside the Lab and backfill the runtime to emit into it**: rejected. This is exactly the "runtime → evaluation engine → runtime" circular dependency direction the mission explicitly forbids (§93 final draft), and it would make solving DEBT-004/005 the Lab's problem to solve on the runtime's behalf, which is out of this track's charter.
- **Wait for DEBT-004/005/016 to resolve before building the adapter at all**: rejected. Those debts have no scoped packet or ETA; blocking the entire Lab on them would violate the mission's own roadmap-isolation requirement in the other direction (the Lab waiting on the kernel is still coupling, just inverted).
