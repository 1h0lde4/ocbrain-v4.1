# OCBrain — Merge & Freeze Report: K4.4 Watchdog Baseline

**Date:** 2026-08-27
**Merge commit:** `609ebfa` (docs follow-up: `d1bf5a8`)
**Branch merged:** `feature/execution-progress-inspection` → `main`

---

## A. Branch state

| | |
|---|---|
| Branch | `feature/execution-progress-inspection` |
| Commits merged | 20 (18 pre-existing + `7ca7f35` contract fix + `fc609de` research report, both added this session) |
| Merge base | `5197d88` (K4.2-H2 close) |
| `main` at merge time | `eabe46c` — had moved 1 commit past the merge base (an unrelated, zero-overlap docs-only commit; included via this merge, no conflict) |
| Final commit on `main` | `d1bf5a8` |
| Working tree | Clean (verified post-merge and post-doc-update; recurring `config/*.toml` line-ending noise from running the test suite — pre-existing, DEBT-012 — reverted each time, never committed) |

## B. Changes merged

- **Watchdog / ExecutionBudget:** `core/runtime/execution_budget.py` (new), `core/runtime/watchdog.py` (new), `core/runtime/execution_watchdog.py` (new) — two independent implementations, see §F/§G.
- **Progress monitoring:** `core/runtime/progress.py` (new), `core/runtime/progress_monitor.py` (new) — same duplication.
- **Execution graph / inspection:** `core/runtime/execution_graph.py`, `execution_outcome.py`, `projection.py` (all new).
- **API / UI:** `interface/api.py`, `interface/web/index.html` (SSE for long-running responses; empty-response handling).
- **Runtime plumbing:** `core/runtime/network.py` (httpx read-timeout, hardcoded 60s → `OCBRAIN_LLM_TIMEOUT_SECONDS`, default 600), `core/runtime/execution_context.py` (additive `execution_budget` field), `core/runtime/limits.py`, `core/provider_mesh.py` (comment only), `core/model_router.py`, `core/orchestrator.py`, `core/workflow/runtime.py`, `core/workers/base.py` (rename churn, resolved cleanly).
- **Config:** `config/settings.toml` (`use_k42_frontend` enabled).
- **Tests:** `test_execution_budget.py`, `test_progress_monitor.py`, `test_execution_watchdog.py`, `test_execution_inspection.py`, `test_model_router_monitored_streaming.py` (all new), `validate_live.py`.
- **Docs:** `docs/reports/EXECUTION_PROGRESS_INSPECTION_IMPLEMENTATION_REPORT.md`, `K4_4_IMPLEMENTATION_REPORT.md` (both pre-existing on the branch), `WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md` (written this session, committed to the branch before merging).
- **Contract fix:** `7ca7f35` (this session) — see §E.

No unrelated or accidental changes found across all 20 commits — every file touched traces to this work. The one recurring anomaly (`config/models.toml`/`sources.toml`/`settings.toml` line-ending churn from running tests) is pre-existing, already tracked as `KNOWN_ISSUES.md` DEBT-012, and was reverted from the working tree each time it appeared rather than committed.

## C. Validation

| | Before this session | After fix (`7ca7f35`) | After merge to `main` | Full suite, deps installed |
|---|---|---|---|---|
| Feature tests (5 files) | 49/50 (1 failing — contract mismatch) | 50/50 | 50/50 | 50/50 |
| Regression set (11 files) | not run | 196/196 | 196/196 | 196/196 |
| Full `tests/` | not run | not run | not run | **1296 passed**, 6 failed + 4 errors — all confirmed (by installing `fastapi`/`httpx`/`aiofiles` and re-running, then inspecting the remaining tracebacks directly) to be `chromadb` not being installed in this sandbox. Zero relationship to this merge. |

Every number above was re-run fresh this session, not carried forward from either implementation report's own claim.

## D. Original watchdog objective

Confirmed via code path + test verification (this sandbox has no live model backend to re-run the literal prompts): the flat 60-second timeout that killed long-form generation (`write a 1000 word short story` → no response) is gone. Two things changed it: `ExecutionBudget` (configurable, replacing a hardcoded `asyncio.wait_for(..., timeout=60.0)`), and `core/runtime/network.py`'s httpx client read-timeout (hardcoded `60.0` → `OCBRAIN_LLM_TIMEOUT_SECONDS`, default `600`). Both were necessary; the K4.4 report's own account only mentioned the first.

## E. New issues discovered — status

- **Contract mismatch (this session's `7ca7f35`):** the two independently-built implementations both defined `ExecutionBudget` under the same filename; the K4.4 version is what's actually on disk, but `core/workflow/runtime.py` and `core/runtime/watchdog.py` still called the older, pre-K4.4 API. Reproduced the exact `TypeError`, fixed, verified via test and via live reproduction in a Codespace (Moncif independently hit the same symptom — "keeps thinking, then error" on edit requests — before this fix landed). **Status: fixed and merged.**
- **Retry semantic-integrity gap:** confirmed absent, not inferred — no `operation_id`/`trace_id` is threaded from client through retry anywhere in the codebase. **Status: deferred, `KNOWN_ISSUES.md` DEBT-015.** Full research and proposed architecture in `docs/reports/WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md`.
- **Watchdog/progress duplication:** two implementations coexist, now internally consistent with each other's dependencies but still architecturally separate. **Status: deferred, `KNOWN_ISSUES.md` DEBT-016.**
- **Literal "HTTP 502" (original mission brief) vs. the graceful string-error this session traced:** `orchestrator.py` catches the contract-mismatch exception and returns a clean error string, not a raw 502. If a real deployment saw a literal 502, that's more likely an upstream proxy translating a dropped/idle connection (plausible during the planning phase before SSE bytes flow) than this exact code path. **Status: unconfirmed, recorded as open in the research report, not asserted as resolved.**

## F. Research retained

Summarized from `docs/reports/WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md` (full detail there — **RESEARCHED and PROPOSED, none of it IMPLEMENTED**):

- **Temporal:** Activity-level retry vs. workflow-level retry are different things; retrying a whole unit re-runs everything. Workflow ID as a stable dedup key.
- **LangGraph:** `thread_id` as stable cross-resume identity; checkpointer snapshots state per super-step so a crash resumes rather than restarts.
- **Restate:** Idempotency keys deduplicate; the processor explicitly "rejects events sent from an invocation if a newer attempt has started" — the clearest existing statement of the Operation/Attempt invariant.
- **AgentRewind** (arXiv:2608.14380, verified): aligned checkpoints of agent context *and* environment state together.
- **AgentTether** (arXiv:2607.06273, verified): localizes the failure-critical subtrajectory instead of retrying the whole run.
- **"Beyond Single-Use Tokens" / CapLease** (arXiv:2608.01710, verified): names the exact failure mode as "semantic replay" — identity must attach to the semantic operation, not the attempt.
- One named source ("AgentR," arXiv:2608.15264) could not be located after four independent search attempts; flagged as unverifiable in the report rather than filled in with invented content.

**Proposed (not implemented):** `Operation`, `ExecutionAttempt`, `ExecutionSnapshot`, `RecoveryDecision`, extending the existing `FailureType` taxonomy. All additive; none require modifying `OperationRecoveryBudget` or `CancellationToken`.

## G. Deferred work

Recorded in `KNOWN_ISSUES.md` as DEBT-015 (research/proposal — operation identity, `ExecutionAttempt`, `ExecutionSnapshot`, extended failure classification, `RecoveryDecision`, checkpoint persistence, idempotency, stale-attempt rejection, worker/capability integration, richer inspection UI, durable execution history — 12 sub-items, all **status: proposed only**) and DEBT-016 (the watchdog/progress duplication — **status: deferred, needs its own packet**).

## H. Roadmap handoff — and a discrepancy I'm flagging rather than resolving unilaterally

The merge brief's own framing was: *"K4.2 incomplete → finish K4.2 → clean legacy/temporary compatibility paths → K4.3 → K4.4 continuation… K4.3 must not be skipped… resume K4.4 only after K4.2 is complete."*

Reading `CURRENT_STATE.md` and `IMPLEMENTATION_ROADMAP.md` fresh (not assuming either the merge brief or my own memory of prior sessions), both say plainly and repeatedly, with dates and cross-references: **all 9 K4.2 packets, plus K4.2-H1 (frozen) and K4.2-H2, are complete.** Neither document defines a "K4.3" milestone anywhere. The only file matching that name is `docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md` — which, on inspection, is the *planning document* (dated July 24, 2026, "DRAFT — awaiting approval") that broke K4.2 into Packets 01–09. Those packets are the ones now marked complete. It is not a phase that follows K4.2; it's the plan that produced K4.2's own implementation, already executed. I could not find "K4.4" anywhere in either authoritative document either — it appears only as the label the (now-merged) feature branch's own report gave itself.

I don't think it's my call to silently pick a version of this story and write it permanently into the project's authoritative docs — either "silently comply with K4.2-incomplete/K4.3-pending" (which would make `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md` less accurate than they were before I touched them) or "silently overwrite it with what I think is right" (which discards context you might have that isn't written down anywhere yet). So: the doc updates in this merge describe the watchdog/execution-reliability work as its own track, orthogonal to K4.2.x — accurate either way — without asserting a K4.2/K4.3 sequencing claim in either direction. Flagging it here plainly so you can correct me if there's context I'm missing, or confirm if this was simply based on a title-reading slip in whatever produced the merge brief.

What I can state cleanly regardless of how that resolves: **the watchdog/execution-budget baseline is merged and frozen. `Operation`/`ExecutionAttempt`/`ExecutionSnapshot` and everything else in DEBT-015 are proposed, not started, and per the Architecture Freeze Principle should get their own ADR before implementation begins.**

## I. Freeze integrity

Verified by diff (`git diff 5197d88 609ebfa`), not assumption:
- `OCBRAIN_KERNEL_CONSTITUTION.md`, `docs/architecture/decisions/` (ADRs), `core/cognitive/recovery.py` (`OperationRecoveryBudget`), `core/runtime/cancellation.py` (`CancellationToken`): **zero lines touched.**
- K4.2-H1's explicitly frozen contracts (`RawRequest`, `CapabilityMatch`/`CapabilityDiscoveryResult`, `trace_id`/`operation_id`/`stage_tag`, the three cognitive entrypoints) — checked `core/cognitive/intent.py`, `planner.py`, `compiler.py`, `learning.py`, `user_model.py`, `core/observability/tracer.py`, and all three K4.2 workers: **zero lines touched.**
- No standalone "Reliability freeze" document exists in this repository to check against (searched; none found) — noting this rather than asserting compliance with something that isn't a real, named artifact here. "C-MoE" exists only as a future-architecture study doc (`docs/architecture/future_debt_study/OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md`) — not yet implemented, so nothing exists yet to have been put at risk.

## J. Repository state

```
d1bf5a8  docs: record K4.4 watchdog merge, defer further execution-reliability evolution
609ebfa  Merge feature/execution-progress-inspection into main: K4.4 watchdog baseline
fc609de  docs(K4.4): watchdog evolution research + architecture report
eabe46c  docs: add external resource->skill->capability research study
7ca7f35  fix(K4.4): reconcile workflow-runtime watchdog path with real ExecutionBudget contract
```
`main` @ `d1bf5a8`, pushed. Working tree clean. `feature/execution-progress-inspection` left in place, not deleted, in case you want it as a reference — it's now fully contained in `main` (fast-forward-equivalent content, merged via `--no-ff`).
