# DEBT-020 — Live-Path Re-Verification, Root-Cause Characterization, and Proposed Completion-Gate Design

**Status:** Trace complete (mission §0–1). Design proposed, not implemented (mission §2–4). No code changed, no tests added, nothing merged.
**Audited against:** `1h0lde4/ocbrain-v4.1` @ `f7058d3bf428b62ddfff18d58636736dc18b5f5d` (2026-09-09), fetched fresh this session — nothing below is assumed from a prior report's word alone where the underlying code was available to check directly. Where something was carried forward rather than independently re-verified this session, it is marked as such rather than presented as fresh.
**Relationship to prior work:** Extends `FALSE_COMPLETION_KERNEL_AUDIT_PRE_IMPLEMENTATION_REPORT.md` (Sep 2, 2026) and the Sep 6, 2026 Kernel freeze audit's §5. Every load-bearing claim in both was independently re-checked against today's HEAD before being reused here (per §18.4.6). None was overturned; several are sharpened with detail neither prior pass captured.

---

## Part 1 — Live path, re-verified

### 1.1 The chain, at current line numbers, confirmed first-hand

```
core/workflow/runtime.py:530   success = last_result.success if last_result is not None else True
core/workflow/runtime.py:570   "workflow.completed" event payload includes "success": success
core/workers/evaluator.py:172  goal_completed = bool(workflow_completed_events[0].payload.get("success", False))
```

Unchanged since commit `283b4aa` (Sep 7, DEBT-003). `git log 6f2eb9f0..HEAD -- core/workflow/runtime.py core/workers/evaluator.py core/cognitive/planner.py core/runtime/execution_outcome.py` returns empty — zero commits have touched any of these four files since the Sep 2 audit's pinned commit.

### 1.2 Two errors in the tracking docs, found this session

1. `KNOWN_ISSUES.md` / `CURRENT_STATE.md` / `IMPLEMENTATION_ROADMAP.md` all cite `core/runtime/execution_runtime.py:280→:320`. That file exists and is real, but is not the site of this bug — confirmed by direct grep. The actual chain is `core/workflow/runtime.py:530` (moved from `:280` during the Sep 5 DEBT-016 refactor; the freeze audit's own citation, not the three tracking docs', is the accurate one).
2. `WorkflowResult`'s own docstring (`runtime.py:147`) reads *"success: True if all executed nodes succeeded."* The actual implementation at `:530` checks only `last_result.success` — the last node `_execute_from` returned, not an aggregate over `node_results`. The class's own documentation overstates what the field actually verifies, in the same direction as the bug itself.

Both are folded into the doc-sync step once implementation lands, not treated as separate debt.

### 1.3 Answers to the mission's §1 checklist, condensed

| Item | Finding |
|---|---|
| Entry → plan → compile → execute | `Orchestrator.handle()` → `interpret_request()` → `Planner.plan()` → `compile_plan()` → `WorkflowRuntime.execute()`. Two callers of `execute()` exist in `orchestrator.py` (`:454` live K4.2 default, `:601` explicitly-commented test-only K2.2 legacy) — both converge on the same `execute()`/`_execute_from()`, so a fix there covers both without touching `orchestrator.py`. |
| Worker result creation | `WorkerResult` (`core/workers/base.py:112`) — plain `success: bool = True`, independent of the richer optional `execution_detail: Optional[ExecutionOutcome]`. **New finding:** grep confirms nothing anywhere derives one from the other; they can disagree and nothing reconciles them. The cruder, unlinked one is what reaches the bug chain. |
| Partial/intermediate output | `ExecutionOutcome.partial_output` (`execution_outcome.py:63`), populated in production at `core/model_router.py:436`. **New finding, closes a prior OPEN item:** consumed nowhere in the decision path — only a dev script (`validate_live.py`) and one test read it. |
| Node aggregation | `success = last_result.success if last_result is not None else True` (`:530`) — "did the last thing that ran not error," not "did the whole task get done." |
| Error/recovery branches | `error_branch` redirection (`:639`, `:694`). **New finding:** not a special case — the redirected-to node's own result becomes `last_result` through the identical path. A gate that correctly evaluates final output against constraints handles this automatically; no bespoke logic needed. |
| Retry | Not fully traced this pass. `SupervisorWorker._attempt_retry()` and `root_operation_id`/`attempt_id` (ADR-KERNEL-01) exist. Whether a retried attempt's result can reach this chain in a way that bypasses the eventual gate is **OPEN** — first item for the implementation pass. |
| Checkpoint/resume | `ADR-KERNEL-03`: a node `RUNNING` at checkpoint time is reset to `PENDING` and fully re-executed, never assumed complete. Doesn't touch this specific bug (operates one level up), but is the right existing precedent for how the new gate should treat `UNKNOWN`. |
| Streaming | Out of this chain — `interface/api.py`'s streaming endpoint bypasses the K4.2 pipeline entirely (DEBT-017, pre-existing, not re-verified this session). |
| Missing-result default | `else True` branch at `:530` fires only if `last_result is None`. **OPEN:** whether that's reachable in practice (vs. `_execute_from` always returning a real `WorkerResult`, including the `success=False` cancellation case already handled at `:618/:622`) was not conclusively resolved this session. |

### 1.4 What the mechanism actually is

Not "the system wrongly believes it succeeded." The `success` field at every site above honestly measures whether execution reached a terminal state without erroring — the code's own comment (`:513–519`) says exactly that, unprompted, including the explicit case of error-branch recovery. The gap is that nothing exists to answer the other question — did the output satisfy what was asked — so the one signal that does exist gets treated, three layers downstream, as if it answered both.

`Constraint` (`planner.py:85`, fields verified by direct read this session) has no field capable of holding a checkable value: `kind` (hard/soft), `relation`, `source`, `rationale`, `validated_by` — all qualitative. `_EXPLICIT_CONSTRAINT_PATTERNS` (`planner.py:250`) is modal-language regex only (`must` / `should` / `without` / `only` / `exclusively`) — no quantity detection. Zero commits to either since Sep 2.

---

## Part 2 — Proposed design for mission §2–4 (semantic distinction + gate)

**Proposal only — not implemented.** Flagging before writing code because every later section (aggregation, retry, checkpoint, streaming, and eventually Verification per §36) inherits whatever gets decided here.

### 2.1 Two-axis model, mapped onto real names

Per this project's Architecture Evolution Policy (§18.6 — favor convergence over novelty) and §1.1 (extract patterns, don't build competing ones):

- **Execution status** — no new type needed. `WorkflowResult.success` / `WorkerResult.success` keep their current, honest meaning. `FailureType` (`execution_outcome.py:19`) already has close to the right shape for *why* an execution ended — extend it, don't replace it.
- **Completion status** — genuinely new; nothing today plays this role under any name. Proposed: a `CompletionStatus` enum (`SATISFIED` / `INCOMPLETE` / `VIOLATED` / `UNKNOWN`), added to `core/runtime/execution_outcome.py` next to `FailureType` rather than a new module — same file, same import surface, same K4.4 provenance.

### 2.2 Where the gate lives

Inside `WorkflowRuntime._execute_from`, replacing the bare assignment at `:530` — not in `EvaluatorWorker`, not in `orchestrator.py` (§1.3: both callers already converge here). Sketch:

```python
completion = self._evaluate_completion(last_result=last_result, execution_plan=execution_plan)
success = last_result.success if last_result is not None else True   # unchanged meaning
result = WorkflowResult(
    success=success,                      # execution status — unchanged
    completion_status=completion.status,      # new
    completion_reason=completion.reason,      # new, typed
    ...
)
```

`evaluator.py:172`'s `goal_completed` gets redefined off `completion_status == SATISFIED`, not off `success` — closing the actual chain rather than adding a check beside it.

### 2.3 Fail-closed evaluation shape

```
any hard Constraint has a checkable value AND it is not met   -> VIOLATED
no hard Constraint has a checkable value                       -> UNKNOWN   (not SATISFIED)
execution status is failure / cancelled / timed-out             -> INCOMPLETE
every checkable hard Constraint is met                          -> SATISFIED
```

The `UNKNOWN` branch is the consequential one: since no `Constraint` today carries a checkable value, **most tasks land in `UNKNOWN`, not `SATISFIED`**, until `Constraint` gets a value shape (§2.4) and something upstream populates one. Correct per mission §6 ("when completion cannot be proven, safe behavior is non-success") but a real, visible behavior change — `goal_completed` will read `False` far more often than today, for the right reason, worth confirming before it ships.

### 2.4 The one piece of net-new capability this requires

```python
@dataclass
class Constraint:
    kind: str = ConstraintKind.HARD
    relation: str = ConstraintRelation.SATISFIES
    source: str = ConstraintSource.EXPLICIT
    rationale: str = ""
    validated_by: Optional[str] = None
    measure: Optional[str] = None        # new — e.g. "word_count", "item_count"
    target: Optional[float] = None       # new — e.g. 10000
    comparator: Optional[str] = None     # new — "gte" | "lte" | "eq"
```

All three new fields default to `None`; existing construction sites are unaffected — same additive pattern as `execution_detail` on `WorkerResult`. This gives the *shape* a checkable value and lets the gate evaluate any constraint that has one. It does **not** teach `_extract_explicit_constraints()` to detect quantities from prose — that stays out of scope, per both prior reports and mission §38 (Planner/NLU extraction, not Kernel completion semantics).

---

## Explicitly not yet done

Retry-result interaction with this chain, whether `last_result` can genuinely be `None` at `:530`, `execution_detail.is_success`'s own SUCCESS/`COMPLETED_WITH_PARTIAL_OUTPUT` conflation (real, named in the original minimal-fix recommendation, not yet folded into this design), and everything from mission §15 onward — aggregation across multiple nodes with mixed constraint outcomes, checkpoint/resume interaction with `completion_status`, the full adversarial test matrix. This document covers mission §0–4 only.
