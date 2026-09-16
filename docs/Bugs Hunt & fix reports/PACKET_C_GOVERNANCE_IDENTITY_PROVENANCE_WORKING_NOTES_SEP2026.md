# Packet C — Governance / Identity / Provenance — Working Notes

**Status:** IN PROGRESS. This is not a final packet report — it records the first concrete finding (the explicitly-flagged `CapabilityRequest` boundary) before the broader trace continues.

**Baseline:** `main` at `977ebcc` (post RCE-001 hotfix + CVE-2026-31431 mitigation + DEBT-020 parallel-branch supersession + CTX-SCOPE-001 caller wiring).

---

## Finding C-1: `CapabilityRequest.trace_id` does not carry real execution identity, and `CapabilityResult` carries none at all

**Traced fresh, not inherited from the original freeze mission's flagged hypothesis.**

`core/capabilities/capability.py`'s `CapabilityRequest.trace_id` is `field(default_factory=lambda: str(uuid.uuid4()))` — a fresh, random UUID generated at construction time, unrelated to the calling execution's actual identity chain (`root_operation_id` / `execution_id` / `attempt_id`, established by `ADR-KERNEL-01`).

All three production construction sites confirmed, none override it:
- `core/capabilities/adapter_runtime.py:62` (the generic `invoke()` convenience wrapper)
- `core/workers/capability_executor.py:116`
- `core/workers/planner.py:298` (`_dispatch_module()`)

`CapabilityResult` (`core/capabilities/capability.py:98`) has **no `trace_id` field, and no identity field of any kind** — `success` / `output` / `error` / `adapter_used` / `duration_ms` / `metadata` only. The one place `trace_id` is actually used is three internal event-metadata dict constructions inside `adapter_runtime.py` itself (lines 100, 113, 123) — it never becomes a first-class, caller-visible field on the result.

**The one place real identity does flow through is informal and narrow, not a designed propagation path.** `planner.py`'s `_dispatch_module()` reads `context.metadata.get("execution_id", "")` and smuggles it into `payload["scope"]` — a free-form dict key, not a typed field — specifically for CTX-SCOPE-001's context-scoping purpose (confirmed by the adjacent code comment referencing CTX-SCOPE-001 directly). `model_router_adapter.py:77` is the only adapter that reads it (`request.payload.get("scope", "")`). The other two construction sites never populate this key, and the other two adapters (`ollama_adapter.py`, `openai_compat_adapter.py`) never read it.

**Consequence:** for any capability invocation crossing this boundary, there is currently no first-class mechanism to answer, after the fact, "which Goal / ExecutionPlan / WorkflowNodeState / attempt did this actually belong to." The field named for that purpose (`trace_id`) doesn't carry it; the field that would need to carry it on the way back (`CapabilityResult`) doesn't exist. This is a genuine, evidenced gap in evidence lineage (mission §9: "what happened, under which operation/attempt, using which evidence") for this specific boundary — not resolved, not yet classified against Kernel v1.0 freeze status, purely documented as found.

**Not yet done:** whether this is reachable/consequential depends on what actually consumes `CapabilityResult` downstream and whether anything there needs (or currently fakes) this correlation — not traced yet. Also not yet done: the rest of Packet C's mandate (authorization decisions generally, confused-deputy analysis, where trust context can be forged/widened/bypassed beyond this one boundary).

**Classification:** UNPROVEN as a security control (there is no control here to classify as bypassed — the gap is that no first-class provenance-carrying mechanism exists at this boundary, not that an existing one can be routed around).

---

## Finding C-2: Governance is live-enforced and structurally un-bypassable at two points, but neither point evaluates the specific capability actually invoked

**Traced fresh.** `GovernanceKernel.evaluate_action()` has exactly two production call sites outside `UnifiedMemory`'s own writes/deletes (already covered by the CTX-DELETE-001 pass): `core/cognitive/compiler.py:369` (`action_type="plan_compile"`) and `core/workers/base.py:246` (`action_type="worker_execute"`, inside `AbstractCognitiveWorker.execute()`, which every canonical worker type extends and cannot override — confirmed by `execute()`'s own docstring: "This method is NOT overridable").

**This is genuinely, structurally enforced, not just documented:** `scripts/check_drift.py` contains active, automated checks (DRIFT-05 and an equivalent Planner rule) that fail if any worker calls `GovernanceKernel.evaluate_action()` directly instead of going through the base class — a real architectural-drift guard against exactly the kind of scattered, divergent governance calls that would create bypass risk.

**The gap:** neither governance evaluation is ever given the specific capability_type or payload that will actually execute. `plan_compile`'s `GovernanceAction.metadata` carries `goal_id`, `confidence`, `step_count` — a *count* of steps, not what each step will call. `worker_execute`'s metadata carries `workflow_id`, `step_count`, `token_spend` — nothing about the capability dispatch that happens later, inside the worker's own `_run()`. `planner.py:307`'s direct call to `self._adapter_runtime.invoke(capability_type=..., payload=...)` — the actual consequential action — is never itself the subject of an `evaluate_action()` call anywhere in the traced chain.

**This is not "capability execution bypasses governance"** — every capability dispatch traced happens inside a worker whose `execute()` already ran the coarse check, and that check cannot be skipped. **It is that the recorded governance decision ("this worker may run," "this plan may compile") is at a materially coarser granularity than the action actually executed ("invoke capability X with payload Y")** — exactly Packet C's attention area #7. Whether this matters in practice depends on whether the set of capabilities a compiled, approved plan can cause a worker to invoke is otherwise bounded (e.g., by `CapabilityRegistry`'s own registration surface) — not yet traced.

**Classification:** PARTIAL. Live-enforced at the plan and worker granularity (structurally, via `check_drift.py`); not enforced at the capability/payload granularity anywhere in the traced chain. Named gap, not a claim of full bypass.

**Present-day severity context, traced not assumed:** `CapabilityType` (`core/capabilities/capability.py:46`) is deliberately plain string constants, not a closed `Enum` — "new capability types are added by any future session registering a new `CapabilityContract`... exactly the kind of closed-set friction the Constitution's Law of Replaceability warns against." Its own docstring states plainly: **only `LLM_COMPLETION` has a registered `CapabilityContract` and real adapters today** — the other declared types (Web Search, Browser, etc.) are named in the type namespace but not functional. This meaningfully narrows C-2's present-day consequence: with effectively one live, registered capability, "governance didn't evaluate which capability" has little to bite on yet. It does **not** narrow the finding itself, and the architecture is explicitly designed to grow this surface without revisiting this file — meaning C-2 becomes materially more consequential exactly as more capabilities are registered, with nothing currently gating that growth against the granularity gap. Same shape as the CTX-AUTH-001b disposition: not urgent today, on a trajectory where a specific, nameable future change (a second `CapabilityContract` being registered) is the condition that would revisit it.

---

## Finding C-3: Retry attempts re-run governance per attempt — no stale-authorization reuse (attention area #8)

**Traced fresh, and this one is a negative result worth recording as explicitly as a defect would be.**

`core/workflow/runtime.py:832`'s `_execute_node_with_retry()` loops `for attempt in range(1 + policy.max_retries)`, and **every iteration** constructs a fresh `ExecutionContext` and calls `self._execution_runtime.invoke(worker_type=..., context=ctx)` — which routes to the worker's non-overridable, governed `execute()`. There is no path where a retry reuses the first attempt's authorization decision, and no lower-level re-entry that skips `execute()`. Each attempt also gets a fresh `state.attempt_id = str(uuid.uuid4())` alongside the incrementing `state.attempts` counter — the distinction `WorkflowNodeState`'s own docstring (line 54) explains deliberately: `attempt_id` survives process restarts where a bare counter would collide.

**Classification: LIVE-ENFORCED.** Retry does not bypass the authorization boundary.

### C-3a: `recursion_depth` is hardcoded to 0 — investigated, and it is *not* a retry-path widening

The retry loop passes `governance_state={"recursion_depth": 0}` as a literal on every attempt. This does feed a live control: `ExecutionContext.recursion_depth` is a direct alias for `governance_state["recursion_depth"]` (`core/runtime/execution_context.py:110-118`), `base.py:246` passes it into `GovernanceAction.recursion_depth`, and `governance_kernel.py:136` compares it against `max_depth` and rejects above it.

**But this is not a defect introduced by the retry path, and reporting it as one would be wrong.** Every production construction site hardcodes the same literal — `core/runtime/execution_runtime.py:166` and `core/orchestrator.py:216` both do the same — and `orchestrator.py:194` documents the reason explicitly in-line: `handle()` has no actual recursion. **No real depth value is computed anywhere and then discarded**; there is no live recursion in the current architecture for this governor to measure.

The accurate finding is therefore about the *governor*, not the retry path: the recursion-depth limit is **dormant by construction** — consistently, deliberately, and documented — rather than silently bypassed on one path while enforced on others. It becomes a live control only if/when genuine recursive execution is introduced, at which point every one of these three construction sites needs a real depth value rather than a literal.

**Classification: DOCUMENT-ONLY** (the control exists and is wired, but has nothing live to measure today) — explicitly *not* BYPASSABLE, which is what a narrower look at the retry path alone would have wrongly concluded.

---

## Finding C-4: SupervisorWorker's retry path — Session 1's finding re-verified and materially corrected (attention area #9)

**Session 1 of the freeze audit recorded this as a live, untracked gap ("`_attempt_retry()` has no production call site... dual uncoordinated recovery authorities"). Re-checked against current `main` per the evidence-first rule that a prior finding is a hypothesis, not ground truth. The reachability fact holds; the characterization does not.**

Reachability confirmed unchanged on `977ebcc`: `failed_worker_result` is constructed in exactly 13 places, **all 13 in test files** (`test_supervisor_worker.py` ×11, `test_integration_full_pipeline.py` ×1, plus the read site itself). Zero production constructions.

**What Session 1 missed:** this is documented, deliberate, and contractually specified — not an accidental dead path.

- `core/orchestrator.py:428` names the situation explicitly in-line: `_attempt_retry()` is "reached only via a separate `failed_worker_result` parameter **this call site does not set**," and explains why `recovery_budget` is threaded through unconditionally anyway ("simpler and safer than only threading it on some invocations, and costs nothing since it is inert on this path").
- `supervisor.py:166`'s `_run()` docstring specifies both input paths as independent, with a defined result when neither is supplied (`WorkerResult(success=True, outcome="no_action")`) — not undefined behavior.
- The constructor docstring states that if `execution_runtime` is `None`, "the retry path (2) is unavailable and `_run()` reports that plainly rather than silently doing nothing."
- `test_integration_full_pipeline.py:450` passes `failed_worker_result` and asserts it **must be ignored** on that path — the unreachability is itself under test, deliberately.

**Accurate characterization:** a built, tested, documented capability whose activation contract is specified but whose production wiring is intentionally deferred — the same "declared but not registered" pattern C-2 found in `CapabilityType`. Not a governance bypass (any retry it performs goes through `ExecutionRuntime.invoke()` → governed `execute()`, same as C-3), and not silent dead code.

**Classification: TEST-ONLY**, with the important qualifier that this is by design and documented as such, not an oversight. The residual issue is narrower than Session 1 stated: not "an untracked gap," but that **`KNOWN_ISSUES.md` carries no entry noting this deliberate deferral** — so a future session reading only the tracking docs would rediscover it as a surprise, exactly as Session 1 did. Disposition: worth a one-line `KNOWN_ISSUES.md` note recording it as intentional-and-deferred, not a code change. Session 1's "dual uncoordinated recovery authorities" framing should be treated as **superseded by this finding**, not carried into the freeze manifest as-written.
