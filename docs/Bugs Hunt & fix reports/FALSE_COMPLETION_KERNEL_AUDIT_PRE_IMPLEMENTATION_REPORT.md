# False-Completion / Partial-Execution Kernel Audit — Pre-Implementation Report

**Status:** Investigation only. No code changed, no tests added, nothing merged.
**Audited against:** `github.com/1h0lde4/ocbrain-v4.1` @ commit `6f2eb9f0dff848610a34cd6747856126ed0f8ab` (2026-09-01)
**Method:** Direct source reading only. No claim below rests on the architecture docs' own description of a component — every claim was checked against the actual file. Where I did not verify something directly, it's marked **OPEN** rather than asserted.

---

## 1. Reproduction status

Not reproduced live — this sandbox has no model backend to re-run the literal "write a 10,000-word story" prompt end-to-end, same limitation this repo's own Aug 27 Execution Reliability merge noted about itself in `CURRENT_STATE.md`. This report is source-code archaeology of the path the request would take, not a live repro.

## 2. Live execution path (confirmed)

`interpret_request()` → `Planner.plan()` [`_extract_constraints()`, `discover_capabilities()`] → `compiler.compile()` → `WorkflowRuntime.execute()` → `CapabilityExecutorWorker` dispatch → `workflow.completed` event.

This is the real, live default path, not a legacy fallback: `CURRENT_STATE.md`'s Aug 27 sync confirms `[runtime] use_k42_frontend` was flipped to `Enabled` that day, making this Cognitive Front-End pipeline (not the legacy K2.2 `PlannerWorker`) the default. `EvaluatorWorker` and `ReflectionWorker` sit *after* this path, invoked separately — see §4 finding 5.

## 3. Root cause — the full chain, with citations

1. **`Constraint` has no quantitative field.** `core/cognitive/planner.py` — the dataclass carries only `kind` (hard/soft), `relation`, `source`, `rationale` (free text), `validated_by`. There is nowhere to put "≥10,000 words" as a checkable value, even in principle.
2. **Constraint extraction doesn't try to catch quantities.** `_extract_explicit_constraints()` (planner.py:265) is a regex heuristic over modal language ("must", "must not") for hard/soft/policy-style constraints. Checked directly: `_EXPLICIT_CONSTRAINT_PATTERNS` contains no word-count, length, or quantity pattern.
3. **`EvaluatorWorker` never reads `Constraint` at all.** `grep -n "Constraint" core/workers/evaluator.py` returns zero hits — despite the architecture doc's own claim (cited in the module's docstring) that "EvaluatorWorker can fail a plan against it [a Constraint]." The worker's own docstring is more honest than that claim: *"no deterministic execution-only signal ... measures output quality directly — no such measurement exists anywhere in this repository today."*
4. **Completion authority is a single boolean, copied three times, checked against nothing.**
   - `core/workflow/runtime.py:280` — `success = last_result.success if last_result is not None else True`
   - `core/workflow/runtime.py:320` — emitted verbatim as `workflow.completed`'s `success` payload field
   - `core/workers/evaluator.py:172` — `goal_completed = bool(workflow_completed_events[0].payload.get("success", False))`

   Same boolean, same meaning, at every layer: *the call didn't error*. Never: *the output covers what was asked*.
5. **`EvaluatorWorker` isn't even in the live path today.** Its own docstring: *"There is no autonomous trigger anywhere in this repository for any worker... this packet does not add one for Evaluator either."* So even a correct check here wouldn't stop a false "done" from reaching the user — it runs after, for calibration, not as a gate. Any fix has to live at or before the `workflow.completed`/response-finalization point, not in Evaluator.
6. **The one data shape built for exactly this distinction is unused.** `core/runtime/execution_outcome.py:26` defines `FailureType.COMPLETED_WITH_PARTIAL_OUTPUT`. Repo-wide grep: it is referenced in exactly two places — its own definition, and:
   ```python
   # execution_outcome.py:80-81
   @property
   def is_success(self) -> bool:
       return self.failure_type in (FailureType.SUCCESS, FailureType.COMPLETED_WITH_PARTIAL_OUTPUT)
   ```
   Nothing assigns this value, and the one consumer that exists treats it as equivalent to full success anyway.
7. **`ValidationGate` is a real component — but it's the wrong one.** `validation_gate()` (`core/cognitive/learning.py:377`) is genuinely implemented, but it gates *promotion of new content into long-term memory* (Learning/Adaptation/Evolution tiers), entirely unrelated to whether a task's output satisfies what was requested. The bug report's assumed pipeline (`...→ ValidationGate → completion/finalization`) is a naming collision, not the same mechanism.
8. **Minor, adjacent finding:** `runtime.py:280`'s `else True` default means a workflow that executes zero nodes reports `success=True`. Small, but same family of bug — worth its own line in `KNOWN_ISSUES.md` regardless of what happens with the main finding.

## 4. Answers to the 15 audit questions

| # | Question | Answer |
|---|---|---|
| 1 | How is required work represented? | `Goal.structured_form` (free text) + `List[Constraint]` (qualitative only). |
| 2 | Is scope represented structurally? | No. No field anywhere encodes a quantitative/enumerable target. |
| 3 | Are work units represented? | No general abstraction. `PlanStep` exists for decomposition but isn't tied to a measurable share of a target. |
| 4 | Is partial progress represented? | Partially — `ExecutionOutcome.partial_output` and `FailureType.COMPLETED_WITH_PARTIAL_OUTPUT` exist as shapes; the latter is never assigned. `partial_output`'s callers weren't traced this session — **OPEN**. |
| 5 | Is cumulative progress persisted? | No mechanism found for accumulating progress toward one target across attempts. |
| 6 | Is remaining work represented? | No. |
| 7 | Can execution terminate while required work remains? | **Yes** — confirmed, §3.4. |
| 8 | What exact component is authoritative for completion? | `WorkflowRuntime._execute_from`'s `success` variable (runtime.py:280), propagated unchanged through two more layers. |
| 9 | Can model output implicitly cause completion? | **Yes** — a non-erroring call is sufficient at every layer traced. |
| 10 | Does ValidationGate verify exhaustive completion? | **No** — wrong component; it's memory-promotion, not task-scope (§3.7). |
| 11 | Can a partial result reach SUCCESS? | **Yes**, both structurally (`is_success` conflation) and in practice (nothing checks output against Constraints). |
| 12 | Can the system distinguish "useful partial" from "completed"? | Not currently in the live path — the data shape exists, nothing populates or enforces it. |
| 13 | Can the task resume from existing state? | Not evaluated — outside the layers traced this session. **OPEN.** |
| 14 | Can the planner expand/decompose remaining work? | Decomposition exists at planning time (K4.2.5); no feedback loop from "output fell short" back into the Planner was found. |
| 15 | Can a tool/model failure result in silent partial completion? | **Yes** — this is the exact mechanism in the reported repro. |

## 5. K4.2 / K4.3 / K4.4 reconciliation

This does not map cleanly onto any of the three:
- **Not a K4.2 defect** — K4.2 delivered the Intent→Goal→Plan→Compile pipeline and a *qualitative* Constraint model exactly as specified (K4.2 §12). It never promised quantitative scope-checking, so this isn't K4.2 failing its own spec.
- **Not the Execution Reliability/watchdog work** (Aug 27 merge) — that work protects against *stalls and deadlines* (the model hangs or runs too long). The reported bug is the opposite: the model finishes cleanly, well inside any budget, and is simply wrong about what it produced. I found no K-number attached to the watchdog/budget work in the sections read — if one exists elsewhere, that should correct this note.
- **No "K4.3 = C-MoE" exists** — `CURRENT_STATE.md`'s own Aug 28–29 syncs already corrected this exact misconception; C-MoE is explicitly post-freeze future work.

**Recommendation:** this is new, currently-unscoped territory — it should get its own `KNOWN_ISSUES.md` DEBT entry and, if it's to be addressed before freeze, its own K-number, rather than being folded into an existing one. Given Kernel v1.0 is currently `NOT_FREEZE_READY` on two unrelated blockers (Scope/identity linkage, ADR-001 vs `WorkerContext`), whether this becomes a **third** blocker or is explicitly deferred post-freeze is the kind of call this project's own history (`CURRENT_STATE.md`) repeatedly routes to Moncif rather than deciding unilaterally — I'd flag it there rather than assume either answer.

## 6. Minimal fix vs. deferred scope

**Minimal, Kernel-correctness-scoped (candidate for now, pending sign-off):**
- Give `Constraint` (or a new sibling type) an actual checkable value — not word-count-specific, a general `measure`/`target`/`comparator` shape that word-count, cell-count, item-count, and file-coverage can all instantiate, per the bug report's own "IMPORTANT DISTINCTION."
- Stop `is_success` from treating `COMPLETED_WITH_PARTIAL_OUTPUT` as `SUCCESS`. Likely needs two separate properties (e.g., "produced usable output" vs. "fully satisfied") rather than one conflated flag, since Supervisor retry logic may legitimately want the former.
- Insert the actual scope check *before* `workflow.completed`'s `success` field is set (runtime.py:280) or before whatever assembles the user-facing response — **not** in `EvaluatorWorker`, since it isn't in the live path (§3.5). This is the one point I'd want confirmed with more tracing before writing code: I have not yet located exactly where `WorkflowRuntime`'s return value becomes literal response text — **OPEN**, next thing to trace.

**Explicitly deferred (future milestone, not this fix):**
- General work-unit/coverage/resumability infrastructure — persistent progress tracking, resume-from-partial, planner re-decomposition on shortfall. This is genuinely the size of its own milestone, not a Kernel-correctness patch, and building it now would violate the Architecture Freeze Principle's "avoid large-scale rewrites" guidance for a project already mid-freeze-review.

## 7. Required tests (sketched, not written)

Grounded in real files, not hypothetical ones:
- Unit test on `_build_evaluation_record()` (evaluator.py): a `workflow.completed` event with `success=True` but a supplied output shorter than a supplied Constraint target → assert `goal_completed` should be `False` post-fix (currently would be `True` — this is the regression test for the bug itself).
- Unit test on `ExecutionOutcome.is_success`: `COMPLETED_WITH_PARTIAL_OUTPUT` → assert `False` post-fix (currently `True` — direct test of finding #6).
- Integration test alongside `tests/test_integration_full_pipeline.py`'s existing pattern: real objects, a Goal with an extractable length constraint, a capability response shorter than that constraint, assert the workflow does not report `success=True`.
- Regression: the existing 50/50 and 196/196 suites from the Aug 27 merge, to confirm no interference with stall/deadline handling.

## 8. Explicitly not done in this pass

No code was written. No `KNOWN_ISSUES.md` entry was added (recommend one, didn't add it unilaterally — that file is project-authoritative and this needs the K-number question resolved first per §5). Three items are flagged **OPEN** above (§4.4, §4.13, §6's response-finalization location) and should be closed before implementation starts, per this project's own "prove the state first" standard applied throughout `CURRENT_STATE.md`.
