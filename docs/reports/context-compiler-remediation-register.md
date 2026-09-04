# Context Compiler Remediation Register

Companion to `docs/reports/context-compiler-architecture-decision.md`
(Section 8). Actionable/trackable version of that document's
prioritization — this file is the one to update as items move; the
reconciliation document's own text should not need editing as work
progresses.

**Baseline commit:** `fc5e354`. Last updated alongside the
reconciliation document itself.

---

## Tier 1 — Must fix before Context Compiler adoption

| ID | Item | Why this tier | Action | Test |
|---|---|---|---|---|
| REM-001 | CTX-CACHE-001: `cached_generate()`'s compression-before-hash collision | Live, unconditional, no adversarial precondition — the only Tier 1 item that's a live bug today rather than an architectural gap | Hash the full prompt, or hash-then-compress instead of compress-then-hash | `tests/test_prompt_cache_security.py::TestCtxCache001Collision` (currently red) |
| REM-002 | CTX-AUTH-001: no delimiter/authority framing at Intent Hypothesis prompt construction | Root cause (Gap 1) is definitionally in scope for Context Compiler; shipping new infra around a known hole compounds it | Structural delimiting + explicit untrusted-data framing at serialization, as part of the `LLMContext` materialization design | `tests/core/cognitive/test_intent_security.py` (2 tests, currently red) |
| REM-003 | Gap 1: structured `Context` discarded before any consumer | The single most consequential architecture gap; everything else in Section 5 is downstream of this one point | Design (Exit Criterion 2) before implementation | — |
| REM-004 | Gap 2: no authority taxonomy | Required for REM-002/003 to be meaningful, not a separable nice-to-have | Draft schema (Exit Criterion 3) | — |

## Tier 2 — Must fix before Kernel/C-MoE integration

| ID | Item | Why this tier | Action |
|---|---|---|---|
| REM-005 | Re-evaluate global-pool scoping (Section 9) once genuine multi-worker parallelism exists | Not urgent under current single-path execution; becomes consequential specifically when C-MoE introduces parallel specialists with potentially different trust levels | Re-run the isolation-model question in Section 3 against the C-MoE design once it exists — do not pre-emptively redesign now |

## Tier 3 — Hardening (real, tracked, not blocking)

| ID | Item | Owning subsystem | Action | Test |
|---|---|---|---|---|
| REM-006 | CTX-SCOPE-001: `ContextMemory` has no scope parameter anywhere | `core/context.py` | Thread a scope parameter through `save()`/`last_n()`/`format_for_prompt()` and the `turns` schema | `tests/test_context_scope_security.py` (currently red) |
| REM-007 | CTX-DELETE-001: `delete()` returns `True` even when L1 storage deletion silently fails | `core/memory/unified_memory.py` | Either add `return False` in the step-7 except block, or correct the docstring and require callers to independently verify | `tests/test_unified_memory.py::TestUnifiedMemoryDelete` (currently red) |
| REM-008 | CTX-EXPORT-001: `import_module()` has no content/signature validation, `overwrite=True` fully replaces a module's knowledge base | `core/brain_export.py` | Add checksum/signature verification on the bundle; restrict `bundle_path` to an expected directory; consider requiring explicit confirmation beyond a boolean flag for `overwrite=True` | None yet — recommended as a follow-up addition to this register |
| REM-009 | `core/runtime/efficiency.py`'s `PromptCache`/`cost_aware_call` — dead code, zero live callers | `core/runtime/` | Remove, or wire in and reconcile with `core/prompt/cache.py` rather than leaving two parallel implementations (same pattern as the already-tracked DEBT-016) | — |
| REM-010 | Stale `core/orchestrator.py` comment claiming `OrchestrationGovernor`/`AgentGovernor`/`ConversationGuardrails` don't exist | `core/orchestrator.py` | Update the comment; mechanical, not a judgment call | — |
| REM-011 | `KNOWN_ISSUES.md`'s DEBT-013 self-contradiction (active-table row vs. separately-placed resolved note) and `DEBT-017`'s misplacement outside the main table | `KNOWN_ISSUES.md` | Mechanical doc-sync fix, flagged early in this research track, never yet applied | — |

## Tier 4 — Deferred research (not yet evidence-backed enough to prioritize further)

| ID | Item | Why deferred |
|---|---|---|
| REM-012 | Dedicated audit pass: `mem_vault.py`, `cognitive_vault.py`, `web_learning/pipeline.py`, `consolidation/consolidator.py`, `shadow/collector.py` | Confirmed live, never in scope for any of the six phases — see reconciliation Section 7. Needs its own structured pass before any priority classification would be evidence-backed. |
| REM-013 | Whether `ContextMemory` should be absorbed into Context Compiler's scope or hardened in place as a separate subsystem | Open question per reconciliation Section 9; REM-006 doesn't require this to be resolved first, but Context Compiler's final architecture does |
| REM-014 | Compression (LLMLingua-style) cost/benefit for this pipeline specifically | External research flagged real tension (compressor requires another model call) with local-first/deterministic principles; no OCBrain-specific benchmark exists yet |
| REM-015 | Second export/import router: `interface/api.py` and `core/brain_api.py` appear to duplicate `/export`/`/import` | Noted, not chased, during the secondary-copies-export audit; worth confirming whether this is intentional (e.g. versioning) or accidental duplication before treating it as either safe or a problem |

---

## How to use this register

- Move an item's row (or add a `Status` note) as work happens; don't
  edit the reconciliation document's prose to reflect progress.
- New findings from future audit passes (Tier 4 items, once resolved)
  get a new `REM-0xx` ID and slot into the appropriate tier using the
  same classification logic as reconciliation Section 8.
- Every Tier 1-3 item with an existing red test should turn that test
  green as its own completion criterion — do not close an item without
  the corresponding test passing.
