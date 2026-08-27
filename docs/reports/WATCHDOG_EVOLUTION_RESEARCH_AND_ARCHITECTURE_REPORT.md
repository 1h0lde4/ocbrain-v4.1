# OCBrain — Watchdog Evolution: Research & Architecture Report

**Branch investigated:** `feature/execution-progress-inspection`
**Base:** `main` @ `5197d88` (K4.2-H2, frozen)
**Date:** 2026-08-26
**Companion commit:** `7ca7f35` — "fix(K4.4): reconcile workflow-runtime watchdog path with real ExecutionBudget contract" (already pushed; see §A and §I)

This report follows the mission brief's own instruction: reconnaissance and reconciliation first, implementation proposal last. §A–C are forensic (what's actually there, what broke, why). §D is external research. §E–H are the proposal. §I–J close out freeze integrity and debt. Nothing in §E onward has been implemented — only the verified-defect fix in `7ca7f35` has, and that is called out explicitly as a licensed exception under the Architecture Freeze Principle, not a preview of the proposal.

---

## A. Current post-watchdog state

`main` has no knowledge of any of this work — `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md`, and `IMPLEMENTATION_TRACKER.md` don't mention a watchdog at all, and the most recent completed milestone there is still K4.2-H2 (Aug 22). A branch literally named `watchdog-branch` exists but is bit-for-bit identical to `main` (0 commits either direction) — it appears to be an unused placeholder, not where the work happened.

The real work is on `feature/execution-progress-inspection`, 18 commits ahead of `main`. It contains **two independent, unreconciled implementations** of the same conceptual components, from two different sessions:

| | "Execution Progress Inspection" (2026-08-24 report) | "K4.4" (undated report, self-described as a local-sandbox patch never pushed by its own author) |
|---|---|---|
| Files | `core/runtime/watchdog.py`, `progress.py`, `execution_graph.py`, `projection.py` | `core/runtime/execution_budget.py`, `execution_watchdog.py`, `progress_monitor.py`, `execution_outcome.py` |
| Consumed by | `core/workflow/runtime.py`, `interface/api.py` (the UI "Thinking…" panel, `/executions/{id}` endpoints) | `core/model_router.py` (`_call_monitored_streaming`, the actual LLM-generation path) |
| Scope | Full graph-aware execution tree, SSE-backed UI inspection, node-level status | Budget/monitor/watchdog only — deliberately did not implement the graph, projection, or event vocabulary (its own report is explicit about this cut) |
| Tests (as pushed) | `test_execution_inspection.py` | `test_execution_budget.py`, `test_progress_monitor.py`, `test_execution_watchdog.py`, `test_model_router_monitored_streaming.py` |

Both define `ExecutionBudget` and `ExecutionWatchdog`. Since `core/runtime/execution_budget.py` is a shared filename, the K4.4 version is the one that physically exists on disk today — its constructor, field names, and methods are what's real. The commit history (many "Add files via upload" commits on 2026-08-26, the day of this session, including a delete+rename pair) is consistent with these having been assembled by hand from at least two separate outputs, without either author checking the other's contract.

**What the watchdog demonstrably fixed (original bug, confirmed by both reports independently and by this session):** a flat `asyncio.wait_for(..., timeout=60.0)` in `safe_llm_call()` used to kill any generation over ~60s, and the frontend's `d.answer || 'No response.'` fallback hid the real cause. K4.4 replaced the flat ceiling with `ExecutionBudget`/`ExecutionPolicy.for_generation()` (configurable, throughput-adaptive) and wired it into `ModelRouter.route()` via `_call_monitored_streaming()`. This is why plain chat and the 1000-word story generation both work.

**Verified test state as of this report** (this session ran the suite directly, not by trusting either report's numbers):
- Before this session's fix: 49/50 passed across the five feature test files — one failure, `test_execution_inspection.py::test_watchdog_cancels_at_hard_deadline_and_never_exceeds_extension_cap`, `TypeError: ExecutionBudget.__init__() got an unexpected keyword argument 'hard_deadline_seconds'`.
- After the fix in `7ca7f35`: 50/50 on those five files, 196/196 on the broader regression set (`test_model_router`, `test_runtime_limits`, `test_context`, `test_context_builder`, `test_orchestrator_recovery`, `test_supervisor_worker`, `test_planner_worker`, `test_reflection_worker`, `test_evaluator_worker`, `test_workflow_runtime`, `test_execution_runtime`).

---

## B. New observed failure — traced

Reproduced twice: once by this session via static analysis + a direct object-level repro (no Ollama needed), once live by Moncif in a Codespace against the real app. Both match the mission brief's original report exactly: edit request → "keeps thinking, then error" → retry produces an unrelated new story rather than the requested edit.

**Exact mechanism.** `core/orchestrator.py` routes through `core/workflow/runtime.py` when `self._use_k42_frontend and self._workflow_runtime is not None` (line 275) — a flag enabled today via the "Enable use of K42 frontend in settings" commit. `workflow/runtime.py` then does, verbatim (pre-fix):

```python
budget = ExecutionBudget(
    progress_deadline_seconds=45.0,
    hard_deadline_seconds=600.0 if word_count >= 500 else 300.0,
)
```

The real `ExecutionBudget` (K4.4) has no such fields — it requires `startup_deadline_s`, `progress_deadline_s`, `hard_ceiling_s`, `absolute_ceiling_s`, `max_extension_s`. This session reproduced the literal exception:

```
TypeError: ExecutionBudget.__init__() got an unexpected keyword argument 'progress_deadline_seconds'
```

This is caught by a broad `except Exception as e` in `orchestrator.py` (line 593) that logs it and returns `"Sorry, I encountered an internal error: {type(e).__name__}"` as a normal string — which is what renders as "shows error" in the UI. (Had that construction somehow succeeded, the code goes on to call `budget.start()` and `watchdog.start()` → `self.budget.start()` again, both also nonexistent on the real class — the incompatibility is not a single typo, it's a full contract mismatch between `workflow/runtime.py`/`watchdog.py` and the K4.4 `ExecutionBudget` they were never updated to match.) Plain chat and the original story generation don't go through this path — they call `model_router.py` directly, which uses its own correct, self-consistent K4.4 objects.

**On the literal "HTTP 502" in the original mission brief specifically:** the orchestrator-level catch above returns a clean string response, not a raw 502 — so if a real deployment saw a literal 502, that most likely means either (a) a different deployment/proxy in front of that instance translated a dropped or idle connection into 502 independently of this exception, plausible during the planning/compilation phase before any SSE bytes are flowing, or (b) the exception surfaced somewhere upstream of this catch in that specific request path. This session cannot confirm which from static code alone — there is no access to that deployment's proxy or logs from this sandbox. Recorded as an open item in §J rather than asserted as resolved.

**Why the retry produces a new story, not the edit:** confirmed absent, not inferred. `interface/api.py`'s `/query` endpoint has zero references to `trace_id`, `operation_id`, or `request_id` — no client-supplied identity is accepted at all. `core/observability/tracer.py`'s `get_trace_id()` is a `ContextVar` that generates a fresh UUID whenever none exists in the current context, and `orchestrator.py` only ever calls `get_trace_id()`, never `set_trace_id()` with anything client-supplied. `OperationRecoveryBudget` (`core/cognitive/recovery.py`) is documented as "scoped by trace_id," but since trace_id is fresh per top-level request, a "retry" is — to every part of this system — a brand-new operation with no relationship to the one that failed. There is no mechanism, anywhere in the codebase, for a retry to say "this is the same logical edit as before."

---

## C. Root-cause analysis

- **Transport failure:** not confirmed as the primary cause here — the crash is caught gracefully server-side and returns a normal string. A genuine, still-open transport-layer risk exists independently (SSE connections sitting idle during the planning/compilation phase before generation begins could plausibly hit an intermediary's idle-timeout in some deployments), but this session has no evidence tying it to the specific incident. See §J.
- **Execution failure:** yes, confirmed and now fixed — a straightforward contract mismatch between two independently-developed modules sharing a filename, `TypeError` at construction.
- **Recovery failure:** yes, and by design absence rather than a bug — there is no attempt/recovery abstraction above "the request either returns an answer or an error string." A "retry" today is indistinguishable, to the system, from any other new message.
- **Semantic integrity failure:** yes, confirmed absent — no operation identity is threaded from client through orchestrator through retry. This is the deeper issue and the actual subject of §E onward.

---

## D. Research synthesis

Three of the four named papers were verified directly (real abstracts, real arXiv IDs, matching the brief's description closely). One could not be located after four independent search attempts across different phrasings and a direct listing-page check — flagged honestly below rather than filled in with invented content, with a verified adjacent paper substituted where it covers the same ground.

| Source | Relevant mechanism | OCBrain adaptation | Why | Reject / avoid |
|---|---|---|---|---|
| **Temporal** | Activities retry individually and are expected to be idempotent (at-least-once); Workflows do *not* retry by default — retrying a whole workflow re-runs everything deterministically, which Temporal's own docs and an open feature request (`temporalio/temporal#8901`, "skip re-executing completed activities on workflow retry") explicitly flag as unsolved and costly. Workflow ID acts as a dedup/idempotency key; Run ID + Activity ID composes an idempotency key for external calls. | Confirms the Operation/Attempt split: only the *failed node* should re-run, never the whole logical operation. `operation_id` (§E) plays Temporal's Workflow-ID role — a stable dedup key across attempts. | Directly validates the mission's central invariant with a production system that hit the identical problem at scale. | Don't adopt Temporal's determinism-and-replay-of-code model — OCBrain's nodes are LLM calls, not deterministic functions; full workflow replay doesn't apply. |
| **LangGraph** | `thread_id` is the stable cross-resume identity; a `Checkpointer` snapshots state after every "super-step" (channel values, pending nodes, run config, parent-checkpoint pointer), so a crash/interrupt resumes from the last checkpoint rather than from scratch — "no double-charging the model for completed nodes." Side-effecting steps are marked so replay doesn't repeat them. | `thread_id` is essentially what `operation_id` should be for OCBrain. The checkpoint shape (state snapshot + pending-node pointer + parent link) is close to what `ExecutionSnapshot` (§E) needs. | Closest existing OSS analog to "resume the same logical unit from its last good state" — and it's a widely-used, current pattern (LangGraph Platform automates it in hosted deployments). | Don't adopt LangGraph's full graph-execution runtime — OCBrain already has `ExecutionGraph`/`Planner`/`Supervisor`; only the identity + snapshot *pattern* is wanted, not a second execution engine. |
| **Restate** | Idempotency key on request headers → automatic dedup, replayed result on duplicate. Every invocation is tracked through completion; **the processor explicitly "tracks invocation execution attempts (retries) and rejects events sent from an invocation if a newer attempt has started."** Journal records each step + result; replay skips completed steps. | The "reject events from a superseded attempt" rule is exactly the Operation/Attempt invariant, stated as a production guarantee rather than a design goal. Worth lifting almost verbatim: once Attempt N+1 exists, Attempt N's late-arriving effects should be ignored. | Cleanest, most current (2026) articulation of durable-invocation semantics for exactly this failure class, including an LLM-agent-specific writeup (Vadim, July 2026) describing the same orchestrator → durability-layer → LLM pattern OCBrain would need. | Don't adopt Restate's own runtime/journal-log infrastructure — OCBrain already has `EventStream`/WAL; the *policy* (idempotency key, stale-attempt rejection) is the transferable part, not the storage engine. |
| **AgentRewind** (arXiv:2608.14380, verified — Zhuang, Chen, Duan, Zheng, Li, Zhang) | Records **aligned checkpoints of both agent context and environment state** so a long-horizon agent can rewind to an earlier point and resume "with information from previous attempts" rather than restarting blind. Companion benchmark: MettleBench. | Directly supports `ExecutionSnapshot` needing to capture *both* conversational/context state and the target artifact's state (the story), aligned to the same point — not just one or the other. | Published this month, purpose-built for exactly this failure class (long-horizon agent errors that are hard to reverse after the fact). | Don't adopt wholesale — it's framed for general long-horizon agent tasks with its own benchmark harness; OCBrain needs the *alignment* idea, not the paper's evaluation apparatus. |
| **AgentTether** (arXiv:2607.06273, verified — Zhao, Zhang, Gu, Sun, Pei, Bansal, Rajmohan, Ma) | Abstracts a run into **Transition Units** linked by a dependency-aware **Critical Transition Graph**, localizing the failure-critical subtrajectory instead of treating a run as pass/fail. Explicitly contrasts this with "blind retry adds no diagnosis." | Supports localizing recovery to the failed node (§E `RecoveryDecision`) rather than re-running the whole operation — matches the mission's own "retry validation, not regenerate the story" example precisely. | Directly on-point, recent (Jul 2026), and explicitly critiques the exact anti-pattern (blind retry) this report is trying to move OCBrain away from. | The full graph-diagnosis model (offline normal-behavior model + run-local detector) is heavier than OCBrain needs today — adopt the localization *principle*, defer the statistical diagnosis machinery. |
| **Graph-based execution/planning research** | The specific title named in the brief ("Planning as Graphs") could not be located verbatim; the general area is real and active — e.g. "From Agent Loops to Structured Graphs: A Scheduler-Theoretic Framework for LLM Agent Execution" and "GAP: Graph-Based Agent Planning" both model task dependencies as graphs with success/failure-conditioned transitions. | Confirms `ExecutionGraph` (already implemented in the Aug-24 work) as the right shape for outcome-conditioned local recovery, once reconciled with the K4.4 budget/watchdog. | Converging, current research independently arrives at the same graph-with-recovery-edges shape OCBrain already half-built. | Don't rebuild `ExecutionGraph` around any one paper's formalism — reconcile the two implementations already in the repo first (see §J) before adding a third model. |
| **"Beyond Single-Use Tokens" / CapLease** (arXiv:2608.01710, verified — Xu, Fan, Wang, Li, Liu) | Names the exact failure mode as **"semantic replay"**: an agent that replans/retries gets a *fresh* token for what is semantically the *same* authorized action, so identifier-local single-use tokens don't prevent duplication. Fix: durable, monotonic state over the action/confirmation/budget, with Issue→Prepare→Commit transitions (CapLease). | This is the clearest available statement of the mission's own principle ("identity must attach to the semantic operation, not the attempt"), from a different domain (authorization) but the identical structural bug. The Issue/Prepare/Commit states are a clean, reusable shape for `ExecutionAttempt.status`. | Best available grounding for *why* `operation_id` must be independent of any per-request identifier — published this month, purpose-built around this exact class of bug. | Don't import CapLease's authorization/payment-security machinery — OCBrain doesn't need cryptographic capability leases; only the identity/state-machine pattern transfers. |
| **"AgentR"** (arXiv:2608.15264, as named in the brief) | **Not verified.** Searched by ID, by name plus description, and checked the surrounding arXiv listing page directly — no matching paper found under this ID or title. Not asserting it doesn't exist, only that it could not be located, and no content is invented for it here. | — | — | Substituting **"Agent Operating Systems (AOS): Integrating Agentic Control Planes into, and Beyond, Traditional Operating Systems"** (verified, real) as the closest confirmed source for this row's actual topic: it defines agent lifecycle states (created/initialized/active/awaiting/executing/suspended/terminated), durable agent identifiers, and "deterministic termination semantics" including handling of outstanding/non-cancelable tool calls — directly relevant to what an `ExecutionAttempt` lifecycle needs. |

---

## E. Recommended OCBrain architecture

Reconciled against what's actually in the repo today, not the mission brief's assumed starting point:

| Concept | Status | Recommendation |
|---|---|---|
| `ExecutionBudget` | **Exists, correct, tested** (K4.4) | Keep as-is. Do not touch — it's the one component both implementations agree should exist, and it's the one currently correct. |
| `ProgressMonitor` | **Exists twice**, incompatibly (`progress.py` graph-aware vs. `progress_monitor.py` standalone) | Do not add a third. Consolidation is real work (see §J) but is a separate, larger decision than this pass — the fix already shipped only made the two existing ones internally consistent again, it didn't merge them. |
| `ExecutionWatchdog` | **Exists twice**, now mutually consistent with `ExecutionBudget` after `7ca7f35` | Same as above — kept generic per the mission's own instruction (§30: "the watchdog remains a generic runtime primitive... budget, progress, liveness, deadline, cancellation" only). Do not fold Operation/Attempt logic into it. |
| `ExecutionOutcome` / `FailureType` | **Exists** (`core/runtime/execution_outcome.py`): `success`, `completed_with_partial_output`, `stalled`, `hard_deadline`, `cancelled`, `provider_failure`, `empty_response`, `validation_error`, `other_failure`. Already has a `retryable` field. | Extend, don't replace. Add categories the mission specifically wants that aren't covered yet: `transport.upstream` vs `transport.client` (distinguishing a dropped upstream connection from a malformed client request), `context.over_budget`, `authorization.failure`. Keep the existing values — `model_router.py` already depends on them. |
| `OperationRecoveryBudget` | **Exists** (`core/cognitive/recovery.py`, ADR-K4.2-H-05), "scoped by trace_id" | Keep as the sole authoritative recovery-attempt budget — non-negotiable per the mission brief and per the K4.4 report's own explicit disclaimer. The fix is upstream of it: give it a trace_id/operation_id that's actually *stable across retries* (currently isn't — see §B), not a change to the budget itself. |
| `Operation` | **Does not exist** | New, additive. A durable record: `operation_id` (stable across attempts — this is the part `trace_id` currently fails to provide), `operation_type` (e.g. `EDIT`, `GENERATE`), `target` (e.g. the story artifact's identifier), `requested_changes`, `created_at`. Minimum viable version: generate this once per *user intent* (not per HTTP request) and have the client echo it back on retry; the server treats a matching `operation_id` as "same logical operation, new attempt" rather than starting fresh. |
| `ExecutionAttempt` | **Does not exist** | New, additive. `attempt_id` (changes every attempt) + `operation_id` (stable) + `node_id` + timestamps + `ExecutionOutcome`. The invariant from Temporal/Restate/CapLease above: **operation_id stable, attempt_id changes, a new attempt supersedes the previous one's authority to act.** |
| `ExecutionSnapshot` | **Does not exist** | New, additive, and the highest-leverage piece for the actual reported bug. For an `EDIT` operation specifically: `operation_type`, `target` (which artifact), `requested_changes` (the parsed constraints — "revenge," "family murdered," "snake-tattoo organization," "survived by chance"), and enough conversational context to reconstruct the request without re-deriving it from whatever the conversation looks like *after* a partial failure. This is what would have kept the retry from turning into a new story. |
| `FailureClass` | **Partially exists** as `FailureType` | Not a new concept — see the `ExecutionOutcome` row above. Extend the enum; don't create a parallel taxonomy. |
| `RecoveryDecision` | **Does not exist** | New, additive, and deliberately thin: given an `ExecutionOutcome` + `Operation`, decide (a) is this retryable at all (checks `OperationRecoveryBudget.remaining`), (b) retry the same node or fall back to a coarser one (AgentTether's localization principle — retry the failed step, not the whole operation), (c) construct Attempt N+1 from the `ExecutionSnapshot`, not from re-reading the live conversation. |

```text
User Operation
      |
Operation (operation_id, type, target, requested_changes)   <- NEW
      |
ExecutionGraph / ExecutionNode                                <- EXISTS (Aug-24)
      |
ExecutionAttempt (attempt_id, operation_id, node_id)         <- NEW
      |
ExecutionBudget + ProgressMonitor + ExecutionWatchdog          <- EXISTS (K4.4, now consistent)
      |
ExecutionOutcome / FailureType                                <- EXISTS, extend taxonomy
      |
RecoveryDecision (checks OperationRecoveryBudget)             <- NEW, thin
      |
ExecutionSnapshot -> Attempt N+1 (same operation_id)          <- NEW
```

---

## F. Adopt / reject matrix

| Concept | Adopt now | Adopt later | Extension point | Reject |
|---|---|---|---|---|
| Stable `operation_id` distinct from per-request `trace_id` | ✅ (must — see §G) | | | |
| `ExecutionAttempt` record | | ✅ | | |
| `ExecutionSnapshot` (EDIT-shaped operations first) | | ✅ | | |
| Extend `FailureType` taxonomy (`transport.upstream/client`, `context.over_budget`) | | ✅ | | |
| `RecoveryDecision` policy layer | | | ✅ (design now, build after Attempt/Snapshot exist) | |
| Consolidate the two `ProgressMonitor`/`ExecutionWatchdog` implementations | | | ✅ (real work, needs its own packet) | |
| Full checkpoint-per-node persistence via `EventStream` replay (LangGraph-style) | | | ✅ | |
| Idempotency keys for external side effects | | | ✅ (no side-effecting capabilities exist yet to protect) | |
| Temporal-style deterministic workflow replay | | | | ✅ reject — wrong execution model for LLM nodes |
| Restate/Temporal's own runtime or journal infrastructure | | | | ✅ reject — `EventStream`/WAL already fills this role |
| AgentTether's statistical offline normal-behavior model | | | ✅ (principle now, model later) | |
| CapLease's cryptographic authorization machinery | | | | ✅ reject — no payment/authorization surface exists to protect |
| A third graph-execution engine inspired by any single paper | | | | ✅ reject — reconcile the two already in the repo first |

---

## G. Implementation proposal

**Must implement now** (small, additive, unblocks correctness):
1. *(Already shipped, `7ca7f35`)* — reconcile `workflow/runtime.py`/`watchdog.py` with the real `ExecutionBudget` contract.
2. Introduce a stable `operation_id`, generated once per user-intent turn and threaded client → `/query` → `orchestrator.py` → `get_trace_id()`/`set_trace_id()`. This alone doesn't fix semantic-integrity, but without it nothing downstream can even be built — it's the prerequisite for everything in §E marked "new."

**Should implement now:**
3. `ExecutionAttempt` as a first-class dataclass (additive, no changes to existing callers).
4. `ExecutionSnapshot` for `EDIT`-type operations specifically — the exact case that broke. Capture target + requested_changes at the point the operation is first understood, before any generation starts.
5. Extend `FailureType` with the transport/context/authorization categories from §E.
6. Wire `model_router.py`'s `execution_detail` (already reaches `RouteResult` per the K4.4 report, disclosed as untraced further) up to the orchestrator so a `RecoveryDecision` has something real to inspect.

**Future work:**
7. `RecoveryDecision` as a formal policy object.
8. Consolidate the duplicate `ProgressMonitor`/`ExecutionWatchdog` pair — needs its own packet and its own decision about which UI/event contract wins.
9. Node-boundary checkpoint persistence via `EventStream` (LangGraph-style), so a retry can resume from "plan built" rather than re-planning.
10. Idempotency keys — deferred until a capability with an actual external side effect exists to protect.

This split matches the mission's own instruction not to overbuild v1.1, and keeps every "now" item additive and reversible per the Architecture Freeze Principle.

---

## H. Test plan

- **Same operation across retry:** construct an `Operation`, fail Attempt 1 (inject a `provider_failure`), verify Attempt 2 carries the same `operation_id` and `ExecutionSnapshot.requested_changes`.
- **Same target:** for an `EDIT`, assert the retried attempt's target artifact identifier is unchanged even when conversation state has moved on.
- **Same requested transformation:** assert `requested_changes` string/struct is byte-identical across attempts unless a human explicitly changes the request.
- **Checkpoint/snapshot preservation:** simulate a crash mid-attempt after the snapshot is taken but before generation completes; assert Attempt 2 reconstructs from the snapshot, not from re-parsing live conversation.
- **Failure classification:** table-test every `FailureType` value (including the three new ones) against `RecoveryDecision` to confirm retryable vs. not-retryable is correct per type.
- **Idempotency (forward-looking):** once any side-effecting capability exists, assert a duplicate Attempt with the same `operation_id` does not repeat the external effect — no such capability exists yet, so this is a placeholder test to write alongside that capability, not before.
- **Regression:** the existing 246 (50 + 196) tests this session verified must stay green; `test_execution_inspection.py`'s two still-passing tests should get the same scrutiny this report gave the one that was failing, since they weren't independently re-derived here beyond confirming they pass.

---

## I. Freeze integrity

Confirmed for the fix already shipped (`7ca7f35`):
- **Reliability, C-MoE, Kernel Constitution:** untouched — not referenced by any changed file.
- **Accepted K4.2 ADRs:** untouched.
- **`OperationRecoveryBudget` (`core/cognitive/recovery.py`):** zero lines touched, confirmed by diff, not imported by the changed files.
- **`CancellationToken`:** zero lines touched.
- **Scope:** exactly three files changed (`core/workflow/runtime.py`, `core/runtime/watchdog.py`, one test); the incidental `config/models.toml` line-ending churn (a pre-existing quirk the K4.4 report already disclosed) was caught and reverted before pushing, per this project's own scope-discipline rule.

For the §E–H proposal (not yet implemented): every item is additive (new fields with defaults, new dataclasses, extended enums) and none requires modifying `OperationRecoveryBudget`, `CancellationToken`, or any accepted ADR. If adopted, this should become its own ADR before implementation begins, per this project's own process — not something this report presumes to number or pre-approve.

---

## J. Remaining debt

- **The duplication itself is still live debt.** This session's fix made the two implementations *consistent*, not *unified*. `core/runtime/watchdog.py`+`progress.py` and `execution_watchdog.py`+`progress_monitor.py` still both exist, serve different callers, and will drift again the next time either is touched in isolation. Worth its own packet.
- **The literal "HTTP 502" / SSE-during-planning transport risk is unconfirmed, not resolved.** This sandbox has no path to the deployment that produced that exact status code. Worth checking directly: does the proxy in front of the real deployment have an idle-connection timeout shorter than the planning/compilation phase takes?
- **`test_execution_inspection.py`'s other two tests** (not the one that was failing) were confirmed passing but not independently re-derived against the real contract the way the failing one was — worth the same scrutiny if this area is touched again.
- **`config/models.toml` line-ending rewrite** is pre-existing (K4.4 report already disclosed it, caused by `core/config.py`'s `Config` singleton on import) and still present — not caused by or fixed by this work.
- **`KNOWN_ISSUES.md` DEBT-013/DEBT-014** (from the K4.2-H2 close, re: `detected_language` propagation and the drift checker's narrower-than-stated coverage) were not re-examined here — out of scope for this packet, flagged only so they aren't lost.
