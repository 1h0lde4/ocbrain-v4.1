# Slice 3 — Trace Adapter: Discovery & Design Report

**Status:** Complete. Contracts (Slice 2) unchanged — no genuine incompatibility was found requiring it.
**Branch:** `eval-lab/research-and-architecture`
**Ground truth as of:** `main@13b86f8` (fetched fresh at the start of this Slice; `main` had moved since Slice 2 — see §0).

---

## 0. Ground-truth refresh before discovery

`main` advanced (`6bb5ecb..13b86f8`, 20 commits) since Slice 2. Two findings mattered enough to check before touching anything:

1. **A new study ("Kernel Completion Study") explicitly revisits the K4.3=C-MoE premise.** Its conclusion — C-MoE positioned post-Kernel-freeze, not as the milestone immediately following K4.2 — **independently confirms**, rather than contradicts, this Lab's existing milestone classification (`docs/reports/AGENT_EVALUATION_RELIABILITY_LAB_RESEARCH_AND_ARCHITECTURE_REPORT.md`'s "COGNITIVE PHASE / FUTURE DEPENDENCY" bucket). No correction needed to prior Lab work.
2. **ADR-KERNEL-01** introduced `root_operation_id` (Goal → ExecutionPlan → WorkflowDefinition, unchanged) and `attempt_id` (WorkflowNodeState, stable across retries) to resolve two specific Kernel-freeze blockers. **This does not resolve DEBT-015** — confirmed directly from `KNOWN_ISSUES.md`, whose DEBT-015 entry is byte-for-byte unchanged, and from the commit's own disclosure that the Orchestrator's replan loop does *not* propagate `root_operation_id` onto a recovery-triggered new Goal (i.e., a retry still gets a fresh identity — the exact gap DEBT-015 is about). Checked whether either field flows into `EventStream` payloads: it does not (`root_operation_id`/`attempt_id` do not appear anywhere in `core/orchestrator.py`, and `EventStream`/`EventBus` are explicitly listed "Untouched" in the ADR-KERNEL-01 commit's own disclosure). Nothing for this adapter to consume from that work; noted for the record, not implemented.

---

## 1. Mapping table

| Runtime event/source shape | Canonical Lab representation | Preserved fields | Raw/provenance retained | Unsupported/lost | Reason |
|---|---|---|---|---|---|
| `worker.started` (core/workers/base.py) | `TrajectoryEventType.WORKER` | occurred_at, sequence, worker_id (=source), execution_instance_id | `task_id` retained as raw payload | — | Direct fit |
| `worker.progress` | `OBSERVATION` | as above | `message` retained as raw | — | Progress update = observation |
| `worker.completed` | `WORKER` | as above + `duration_ms` (mapped directly) | `success`, `task_id` retained as raw | — | Controlled outcome, not a crash |
| `worker.failed` | `FAILURE` | as above | `error`, `error_type` retained as raw | — | Confirmed distinct from worker.completed(success=False): fires from an exception handler |
| `worker.cancelled` | `CANCELLATION` | as above | (empty payload) | — | |
| `worker.rejected` | `FAILURE` | as above | `reason`, `governor` retained as raw | — | Governance-layer rejection |
| `worker.escalated` | `RECOVERY` | as above | `reason`, `governor` retained as raw | — | Closest existing category; no dedicated governance-escalation type exists |
| `workflow.started` (core/workflow/runtime.py) | **UNKNOWN** (raw_type_name preserved) | occurred_at, sequence, source | `workflow_id` retained as raw | — | No existing TrajectoryEventType fits "whole-workflow execution began"; documented gap, not an oversight |
| `workflow.completed` | `COMPLETION` | as above | `workflow_id` retained as raw | — | Treated as independent completion evidence from `execution.completed`, not assumed redundant (discovery didn't fully establish the relationship) |
| `execution.completed` | `COMPLETION` | as above | — | — | Root-node-level terminal signal |
| `execution.failed` | `FAILURE` | as above | — | — | |
| `execution.progress` (core/runtime/progress.py, graph-aware) | `OBSERVATION` | as above + `node_id` (used for causal linkage) | `percent`/etc. retained as raw | — | |
| `execution.node.status` | `STATE_TRANSITION` | as above | `status` retained as raw | — | Literally a state transition |
| `execution.node.completed` | `WORKER` | as above + causal `parent_id` link where present | — | — | "node" and "worker" are related, not identical — approximated |
| `execution.node.failed` | `FAILURE` | as above | — | — | |
| `execution.recovery.started` | `RECOVERY` | as above | — | — | Clean match |
| Model-router-facing watchdog (`execution_watchdog.py`, `progress_monitor.py` — DEBT-016's other side) | **not representable** | — | — | **entire source** | Confirmed zero references to `EventStream`/`.append()` in either file — no event evidence exists to normalize. Not a schema-normalization problem; a confirmed evidence gap. |
| Any unrecognized `event_type` | `UNKNOWN` (raw_type_name preserved) | occurred_at, sequence, source | full payload retained | — | Controlled extensibility boundary, per Slice 2's own design for exactly this case |

Ambiguity documented rather than resolved: whether `workflow.completed` and `execution.completed` are ever truly redundant signals for the same underlying event was not established with confidence during discovery (both are emitted from `WorkflowRuntime.execute()`, at different points, via different internal paths). The adapter treats both as independent completion evidence rather than guessing they're interchangeable — collapsing them on an unverified assumption risks losing real information if they ever diverge.

---

## 2. Identity found in the runtime (kept distinct from each other and from all Lab identity)

Six genuinely different runtime-level identifiers were found, none of which the adapter conflates with any other or with Lab identity:

- `worker_id` — stable per worker instance (`f"{worker_type}:{uuid4hex8}"`), set once at construction.
- `task_id` — from `ExecutionContext`, the runtime's own task concept (not the Lab's `TaskInstanceId`).
- `workflow_id` — stable per `WorkflowDefinition` (template-level).
- `instance_id` — fresh `uuid4()` per `WorkflowRuntime.execute()` call (a new value even for a retry).
- `execution_id` — `metadata.get("execution_id") or instance_id`; lives on `ExecutionGraph`.
- `node_id` / `parent_id` — per-`ExecutionNode`, with real hierarchical structure (`parent_id`) the adapter turns into genuine `CausalReference` edges.

None of these become the Lab's `execution_instance_id` (caller-supplied, per ADR-LAB-01) or any other Lab identity. Where captured, they're preserved as raw payload provenance on the relevant `TrajectoryEvent`'s disposition record, not silently dropped and not silently promoted to Lab identity.

---

## 3. Adapter architecture

**Interface:** `normalize_trajectory(events: Iterable[StreamEvent], execution_instance_id, trajectory_id=None) -> NormalizationResult` (`eval_lab/adapters/trace_normalizer.py`). Pure function: same input, same output (see §5). Takes an already-retrieved iterable of `StreamEvent` — does not call `EventStream.replay()`/`.query()` itself, so `eval_lab/` never touches a database connection or event loop.

**Dependency boundary:** imports exactly two OCBrain-internal names beyond Slice 2's existing one: `core.events.event_stream.StreamEvent` (the pure dataclass — re-verified stdlib-only, zero coupling, the same safety bar `core.runtime.execution_outcome.FailureType` was held to in Slice 2). Never imports `EventStream`/`EventStore` (the stateful service classes in the same module). `test_dependency_boundary.py` extended to scan `eval_lab/adapters/` too and locks this exact allowlist in place.

**Identity model:** `TrajectoryEvent.trajectory_event_id` is derived deterministically from the source `StreamEvent.event_id` (`f"tev_{event.event_id}"`) — not randomly minted. This was caught as a real bug during testing (see §6) and fixed before commit, not left as an aspiration.

**Ordering rule:** sorted by `StreamEvent.sequence` (SQLite `AUTOINCREMENT`, assigned atomically at persist time under single-writer access — confirmed from the actual `CREATE TABLE`/`INSERT` code, not assumed). Timestamp is preserved (`occurred_at`) but never used for ordering, including when it conflicts with sequence.

**`ordering_relation_to_previous` heuristic** (documented as a heuristic, not a certainty): consecutive events from the *same* producer (`source`) are marked `ORDERED`; consecutive events from *different* producers are marked `CONCURRENT`, since persistence-order interleaving of independent producers doesn't imply true causal order between them.

**Replay/idempotency:** deduplicated by `event.event_id`. Identical repeat → `DUPLICATE_IGNORED`, no second `TrajectoryEvent`. Same `event_id` with a *different* payload/event_type → `CONFLICTING_DUPLICATE`, both occurrences recorded, first-seen stays canonical, outcome escalates to at least `PARTIAL` — never silently resolved either way.

---

## 4. Evidence integrity

**Information-loss policy:** every source event gets exactly one `EventDisposition` (`NORMALIZED` / `RETAINED_RAW` / `UNSUPPORTED` / `MALFORMED` / `REJECTED` / `DUPLICATE_IGNORED` / `CONFLICTING_DUPLICATE`) — never silently dropped. Payload fields the canonical `TrajectoryEvent` schema can't hold (e.g., `worker.failed`'s `error`/`error_type`, `worker.rejected`'s `reason`/`governor`) are retained verbatim in the disposition's `raw_payload`.

**These disposition/outcome/terminality types are adapter-owned** (`eval_lab/adapters/outcomes.py`), not new Slice 2 contracts — they describe *how normalization went*, a different concern from Slice 2's *what happened at runtime*. Slice 2 contracts are unchanged.

**Incomplete-trace semantics:** `StreamEvent.sequence` is confirmed global to the whole `EventStream` (a single `AUTOINCREMENT` counter shared by every producer and every concurrent execution — `EventStream.query()` itself documents a `payload_workflow_id` filter specifically because callers need to scope a shared global stream down to one execution). This means a gap in an execution-scoped subset's sequence numbers is the *normal* shape of a complete, correctly-filtered result (an unrelated concurrent execution's event legitimately sitting in the gap), not evidence of anything missing — treating it as such was caught and corrected during a review pass (§8 below) before this landed. Gap-based incompleteness detection is now opt-in only (`assume_contiguous_sequence=True`), for callers who can actually vouch the supplied slice is meant to be gap-free; the default assumes nothing.

**Terminality:** `COMPLETED_OBSERVED` / `FAILED_OBSERVED` / `CANCELLED_OBSERVED` only fire when a matching mapped event genuinely exists. Absence of any terminal-type event → `TERMINALITY_UNKNOWN`, explicitly *not* read as either success or failure — grounded directly in a real finding: `core/workers/base.py` wraps its `EventStream.append()` call in a bare try/except with only a log warning ("Event emission failure must NEVER stop worker execution"), so a worker can genuinely complete while its terminal event never reaches `EventStream` at all.

**No fabricated evidence, confirmed by test:** `test_no_fabricated_success_when_no_completion_evidence_exists`, `test_no_fabricated_causal_reference_without_real_parent_id`.

---

## 5. DEBT compatibility

**DEBT-016:** the two documented watchdog implementations were inspected directly rather than assumed symmetric. Finding: only the graph-aware side (`core/runtime/progress.py`) reaches `EventStream`; the model-router-facing side has zero references to it. This reframes what "handle both schemas" means in practice — there is one schema to normalize, and one confirmed absence to document (§1's mapping table, last data row), not two parallel schemas to reconcile. `ADR-LAB-02`'s original phrasing ("special-cases both DEBT-016 watchdog schemas") is corrected by this finding rather than contradicted; the underlying decision (accommodate DEBT-016 rather than assume unification) still holds and is exactly what's implemented.

**DEBT-015:** confirmed still fully open (§0). Not implemented, not resolved, not worked around with an unstable runtime identifier standing in for it. The Lab's `execution_instance_id` remains entirely Lab-minted, per ADR-LAB-01, unaffected by anything found this Slice.

---

## 6. Tests

`pytest eval_lab/tests -v` → **216 passed**. New: `test_trace_normalizer.py` (40 tests across runtime mapping, identity, ordering, replay, evidence integrity, failure handling, lifecycle, plus five review-driven additions — see §7), `fixtures_runtime_events.py` (realistic `StreamEvent` builders from confirmed payload shapes). `test_dependency_boundary.py` extended (5 tests, was 4) to also scan `eval_lab/adapters/`.

**One real bug found and fixed during initial testing, not weakened around:** `trajectory_event_id` was originally minted via random `uuid4()`, failing a determinism test (§7's Finding 2 requirement that equivalent evidence produce equivalent results). Fixed by deriving it deterministically from the source `event_id` instead — which also improves auditability. **A second real bug (unsafe sequence-gap inference) was found and fixed during external review, before commit** — see §7, Finding 1.

`git diff --check`: clean. Confirmed via `git diff --stat` that this Slice touches only files under `eval_lab/` plus this report — no causal connection to any pre-existing repository-wide test state (a `tomli_w`-related collection gap in the base `tests/` suite predates this branch entirely and is unrelated).

---

## 7. Review pass (before commit)

A review of the initial implementation raised five findings. Each was independently verified against actual code — not accepted or dismissed on the review's say-so alone — before any fix.

| # | Finding | Verified against | Disposition |
|---|---|---|---|
| 1 | Sequence gaps don't necessarily mean missing evidence | `core/events/event_stream.py`: `sequence` is a single store-wide `AUTOINCREMENT`; `query()`'s own docstring explains `payload_workflow_id` filtering exists because callers scope a shared global stream. **Confirmed genuine defect.** | Fixed: gap-based incompleteness detection changed from always-on to opt-in (`assume_contiguous_sequence`, default `False`). |
| 2 | Determinism should cover all generated fields, not just IDs | Re-checked every field-generation path in `trace_normalizer.py`/`outcomes.py` for `datetime.now()` or other wall-clock/random sources beyond the already-fixed `trajectory_event_id`. Found none. | Added `test_complete_serialized_output_identical_across_two_calls` (full `NormalizationResult.to_dict()` comparison, not spot fields) and `test_no_wall_clock_now_used_anywhere_in_normalization_result` to make the claim verified rather than assumed. |
| 3 | Raw evidence must stay durably linked to the trajectory, not only live in a transient result | The linkage already existed (`EventDisposition.canonical_trajectory_event_id` → `TrajectoryEvent.trajectory_event_id`, tested since the first version) but wasn't stated as a load-bearing fact about which object a caller must persist. | Documentation only: `NormalizationResult`'s docstring now states explicitly that it, not `Trajectory` alone, is the durable output unit. |
| 4 | `event_id` uniqueness scope needs verification, not assumption from the field's name | Re-read `StreamEvent`'s own field docstring ("Globally unique event identifier") and generation mechanism (`uuid.uuid4()`, client-side, not a per-store sequential counter). **Confirmed safe as originally implemented.** | Documentation made explicit (why `event_id` is trusted globally unique, not just unique-within-one-store) plus `test_event_id_generation_mechanism_is_uuid4_not_a_sequential_counter` grounding the claim directly in the real default factory. |
| 5 | Terminality needs an explicit authority hierarchy (child-operation vs. trajectory-level) | Checked the actual mapping table: `worker.completed`/`execution.node.completed` were already mapped to `WORKER`, not `COMPLETION`, specifically to prevent this — the rule was already correctly *implemented*, just not explicitly *named*. **Confirmed correct behavior, not yet formalized.** | Named explicitly in code (`_TERMINAL_TYPES_COMPLETION` etc. now documents the exclusion of `WORKER` directly) plus `test_many_completed_workers_do_not_imply_trajectory_completion` (20 completed workers, one completed node, no trajectory-level signal → still `TERMINALITY_UNKNOWN`). |

Only #1 required a behavior change. #2, #4, and #5 confirmed the original design was already correct and added the verification the review asked for. #3 was a documentation gap, not a code gap.

## 8. Scope verification

No Slice 4+ work. No runtime behavior changes (zero files under `core/` touched — confirmed by diff). No evaluator/oracle/simulator execution. No persistence, statistics engine, or benchmark runner. No C-MoE. No DEBT-015 implementation. No DEBT-016 resolution — only inspected and documented. Slice 2 contracts unmodified.
