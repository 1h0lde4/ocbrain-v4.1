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
