# Context Isolation Caller Audit — Sept 7, 2026

**Scope:** every path from `core.context.ContextMemory` to a real caller, traced to actual production reachability — not to what any prior document claimed. Requested as a precondition before CTX-SCOPE-001 can be declared closed. See `KERNEL_V1_0_CLOSURE_AUDIT_SEP2026.md` and `docs/research/context-engineering/context-authority-threat-model.md` for prior context.

**Headline finding:** the threat-model document's own account of which read path is production-live is wrong. It named the Legacy Compatibility Bridge (`orchestrator.py:726`/`core/orchestrator._run_module()`) as the exposure and separately noted the K4.2 write call as "does not itself read back." Tracing actual call chains instead of the documented ones shows the opposite: **the Legacy Bridge path is confirmed dormant** (matches this repo's own established standard for that branch — `main.py` always supplies a `workflow_runtime`), while **`PlannerWorker` — one of the seven canonical K4.2 workers, not a legacy component — has both a live unscoped read and a live unscoped write**, neither of which the threat model mentions at all. This is exactly the kind of documentation/code divergence this project's own audit discipline exists to catch, and it changes where remediation effort should go.

---

## Method

Starting from `core/context.py:221` (`context_memory = ContextMemory()` — confirmed the *only* constructor call anywhere in the repository; every caller shares one process-wide singleton and one SQLite file), every `.save(`, `.last_n(`, `.format_for_prompt(`, and `.boost_module(` call site was located by grep, then traced upward through its actual call chain — not its containing file's name or comments — to determine whether that chain is reachable from `main.py`'s real composition root under the shipped default config (`use_k42_frontend = true`).

Three chains required tracing through more than one hop before their liveness could be determined:

- `ModelRouter.route()` (`core/model_router.py:124`) has exactly 4 call sites repo-wide: `Orchestrator._run_module()` (Legacy Bridge — confirmed dormant per that block's own comment), `ModelRouterAdapter.execute()` (`core/capabilities/adapters/model_router_adapter.py:85`), and two in `core/workers/planner.py`.
- `ModelRouterAdapter` is registered **first** in `main.py`'s adapter list for `CapabilityType.LLM_COMPLETION`, making it `AdapterRuntime`'s default choice in production (confirmed by that file's own extensive documentation, not inferred).
- Two different K4.2 workers dispatch through it with two different `context` payloads: `CapabilityExecutorWorker._run()` hardcodes `"context": ""` (empty string — falsy, so `ModelRouter._build_prompt()`'s `if context else ""` guard means `format_for_prompt()` is never actually called on this path, despite the call chain itself being live). `PlannerWorker._dispatch_module()` passes `"context": self._context_memory` — the real, shared singleton. That guard does not save this second path.

## The matrix

| # | Access point | Direction | Real call chain | Scope passed | Live in shipped default config | Classification |
|---|---|---|---|---|---|---|
| 1 | `core/orchestrator.py:510` | write | `Orchestrator.handle()`, K4.2 branch | `scope=execution_id` (fixed this week) | **Yes** | ✅ Scoped correctly |
| 2 | `core/orchestrator.py:726` | write | Legacy Compatibility Bridge | `scope=execution_id` (fixed this week) | No — confirmed dormant, `main.py` always supplies `workflow_runtime` | Scoped correctly, but moot while dormant |
| 3 | `core/workers/planner.py:218` | **write** | `PlannerWorker._run()`, step 8 — saving its own answer, every time it runs | **none** | **Yes** — `PlannerWorker` is a canonical K4.2 worker, invoked via the standard execution graph | 🔴 **Unsafe** — live, unscoped, not mentioned in the threat model at all |
| 4 | `core/workers/planner.py:305` (`_dispatch_module`, "preferred path") | **read** | `PlannerWorker._dispatch_module()` → `AdapterRuntime.invoke()` → (default adapter) `ModelRouterAdapter.execute()` → `ModelRouter.route()` → `_build_prompt()` → `format_for_prompt(5)` | **none** | **Yes** — this is the "preferred path," per that method's own docstring, taken whenever `adapter_runtime is not None`, which `main.py`'s composition root always supplies | 🔴 **Unsafe — this is the real, live exposure.** The threat model's "confined to the Legacy Compatibility Bridge" claim describes a dormant path; this is the one that actually runs. |
| 5 | `interface/api.py:381` (`_save_context_background`) | **write** | Streaming SSE endpoint, fire-and-forget after each streamed response | **none** | **Yes** — directly in the HTTP streaming response path | 🔴 **Unsafe**, not mentioned in the threat model |
| 6 | `core/workers/capability_executor.py:121` | read (attempted) | `CapabilityExecutorWorker._run()` → same adapter chain as #4 | `context=""` (empty string) | Chain is live, but `format_for_prompt()` is never actually invoked — `""` is falsy | Safe today, **by accident, not by design** — fragile: if this literal ever changes from `""` to `None`... actually `None` is also falsy, so specifically fragile only if it's ever changed to a real (even empty-seeming but truthy) object without adding scope |
| 7 | `core/model_router.py:314` via `Orchestrator._run_module()` | read | Legacy Compatibility Bridge | none | No — dormant, same as #2 | Intentionally-global-but-moot while dormant |
| 8 | `modules/base.py:215` + 4 subclasses (`knowledge`, `coding`, `web_search`, `_template`) | read | `run()`/`run_own()`, reachable only from `core/orchestrator_v3.py` (self-documented "compatibility facade... for lightweight tests and integrations," imported only by `examples/demo_phase2.py` and two test files) and `learning/evaluator.py:38` (`context=None` explicitly — the `if context else ""` guard prevents the call entirely) | none | **No — confirmed unreachable from any live production path.** No adapter in `core/capabilities/adapters/` (`model_router_adapter.py`, `ollama_adapter.py`, `openai_compat_adapter.py`) references the `modules/` package. | Effectively dead code. **This corrects a claim made in this session's own previous turn** ("modules/base.py's K2.2 module-dispatch path is live, not dormant") — that claim was asserted without tracing this far; it does not hold up. |
| 9 | `core/classifier.py:45` (`boost_module`) | read | `classify()`, called only from the Legacy Compatibility Bridge | none | No — dormant, same as #2/#7 | Intentionally-global-but-moot while dormant |
| 10 | `core/context.py:221` | constructor | Module-level singleton; every access point above shares this one instance and one SQLite file | N/A | Always | Architectural fact underlying every row above — there is no per-caller or per-session `ContextMemory` anywhere in this codebase |

## What this means for CTX-SCOPE-001's disposition

**Not closed.** The mechanism (real `scope` column, parameter threading, cache-key fix) is correct and tested. But it is wired into exactly the two call sites (#1, #2) that this audit now shows are the *least* urgent — #2 is dormant, and #1 was already the one part of the original threat model's own analysis that turned out to be accurate. The three genuinely live, unscoped access points (#3, #4, #5) are unwired, and none of them were named in the original threat-model document at all.

Per instruction, none of #3/#4/#5 were wired in this pass — no arbitrary scope was assigned to get anything green. All three have the same natural remediation available as #1 did: `PlannerWorker._run()` and `_dispatch_module()` both receive `context: ExecutionContext` as a parameter (confirmed — `context.metadata`, `context.query` are already referenced elsewhere in the same method), which carries `root_operation_id`/`attempt_id`, the same identity primitives ADR-KERNEL-01 threaded through the rest of the Kernel. `interface/api.py`'s streaming endpoint already has `execution_id` in scope at its call site (confirmed — the same identifier `interface/api.py`'s other two `.handle()` calls already pass). Wiring #3/#4/#5 to these would be the same pattern as #1, not a new design — but that's a decision for you to make explicitly, not something this audit should do unilaterally.

**Separately, real architectural debt, independent of CTX-SCOPE-001:** row #8 suggests the entire `modules/*.py` class hierarchy (`run()`, `run_own()`, `_build_prompt()`) may be dead code relative to the current K4.2-default configuration — superseded by the Capability/Adapter system but never removed or flagged as such anywhere in `KNOWN_ISSUES.md`. This wasn't this audit's primary target and deserves its own verification pass (in particular: confirm nothing outside `core/`/`modules/` — e.g. a CLI command or scheduled job — still constructs these classes directly) before any cleanup decision, but it's worth recording now rather than losing it.

## Recommended KNOWN_ISSUES.md disposition

- **CTX-DELETE-001 — closed.**
- **CTX-CACHE-001 — closed.**
- **CTX-AUTH-001a — closed.**
- **CTX-AUTH-001b — open, requires provenance/trust design** (Context Compiler work).
- **CTX-SCOPE-001 — open.** Mechanism implemented and tested; two of five real access points wired (one of which is dormant); three live, unscoped access points identified by this audit (`planner.py:218`, `planner.py:305`, `interface/api.py:381`) remain unwired pending an explicit decision, not a technical blocker. The threat-model document's own liveness claims should be corrected before anyone else relies on them.
- **New, tracked separately:** possible dead code in `modules/*.py`'s dispatch methods — needs its own confirmation pass before any removal decision.
