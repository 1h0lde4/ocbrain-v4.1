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
