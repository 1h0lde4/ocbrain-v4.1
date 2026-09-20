# Context Compiler Remediation Register

Companion to `docs/reports/context-compiler-architecture-decision.md`
(Section 8). Actionable/trackable version of that document's
prioritization — this file is the one to update as items move; the
reconciliation document's own text should not need editing as work
progresses.

**Baseline commit:** `fc5e354`. Last updated alongside the
reconciliation document itself.

**Update (branch-consolidation pass, Sept 2026):** `fix/context-security-findings-sep2026`
was reconciled against this register — file-level diff and empirical
before/after test verification, not the branch's own audit report taken
at face value. See the Tier 1/Tier 3 notes and the new Resolved section
below for what actually changed and what didn't.

---

## Tier 1 — Must fix before Context Compiler adoption

| ID | Item | Why this tier | Action | Test |
|---|---|---|---|---|
| REM-002 | CTX-AUTH-001: no delimiter/authority framing at Intent Hypothesis prompt construction | Root cause (Gap 1) is definitionally in scope for Context Compiler; shipping new infra around a known hole compounds it | Structural delimiting + explicit untrusted-data framing at serialization, as part of the `LLMContext` materialization design | `tests/core/cognitive/test_intent_security.py` (2 tests) — **1 of 2 now green, see note below** |
| REM-003 | Gap 1: structured `Context` discarded before any consumer | The single most consequential architecture gap; everything else in Section 5 is downstream of this one point | Design (Exit Criterion 2) before implementation | — |
| REM-004 | Gap 2: no authority taxonomy | Required for REM-002/003 to be meaningful, not a separable nice-to-have | Draft schema (Exit Criterion 3) -- **drafted as ADR-KERNEL-06 (DRAFT, unapproved) and implemented at the Intent boundary on branch `fix/ctx-auth-001b-rem004-authority-boundary-sep2026`; not on `main`** | `tests/core/cognitive/test_authority.py`, `test_intent_acceptance.py`, `test_intent_authority_boundary.py` (498 tests, branch only) |

**REM-004 / REM-002 status note (Sept 20, 2026, branch `fix/ctx-auth-001b-rem004-authority-boundary-sep2026` @ base `main` `4669e21` -- NOT on `main`; supersedes the Sept 15 note below on REM-004's status, not on its history):** REM-004 was designed and implemented at the Intent -> Goal boundary. Design: `docs/architecture/decisions/ADR_KERNEL_06_INSTRUCTION_AUTHORITY_TAXONOMY.md` (**DRAFT -- not reviewed, not approved**; implementation existing does not move it past DRAFT). **REM-004 is the architecture/design contract; CTX-AUTH-001b is the security acceptance condition -- one piece of work, not two bugs.** Status: **implemented on the branch, verified there, NOT closed on `main`, register status not moved to Resolved.** Both `TestCtxAuth001StructuralContainment` (001a) and `TestCtxAuth001ParserAcceptance` (001b) pass on the branch **with their assertions unchanged** (the test module is AST-identical to `HEAD` apart from its docstring, which had become stale and was corrected). Evidence, measured: full suite 6 failed / 1501 passed on unmodified `main` -> 5 failed / 2000 passed on the branch, zero new failures, the 5 remaining being the same chromadb `KeyError: '_type'` environment failures; drift 15/15 PASS; 498 new tests; 35 mutants (14 inherited + 21 authored in review) all caught. **Explicit corrections to earlier statements in this file and in `KNOWN_ISSUES.md`/`CURRENT_STATE.md`** (recorded, not silently rewritten): (1) the 001b test drives `generate_hypotheses()`, **not** `_parse_hypotheses()` in isolation -- verified by reading the test; the difference is what makes parser/acceptance separation possible; (2) "no content-agnostic signal exists" was too strong: a closed-world *label contract* (form, not meaning) is content-agnostic, but it cannot detect a *well-formed* hijack; (3) "REM-004 not started" (Sept 15) is superseded by this branch; (4) the Sept 15 decision **not to bolt an authority field onto `IntentHypothesis` stands** -- `IntentHypothesis` is unchanged and a separate frozen `AcceptedHypothesis` carries authority. **What is and is not claimed:** the tested authority-escalation paths are closed (model output, retrieved content, score, paraphrase, retry/fallback, cache, serialization/replay, concurrency, and a demonstrated `MODEL_PROPOSAL -> ConstraintSource.EXPLICIT` path in the planner); **not** "all prompt injection is impossible". The 001b test has an empty mocked context, so it is closed by the label-admission contract, not by provenance; a well-formed hijack (e.g. lowercase `create_account | 1.00`) is contained as a tainted `MODEL_PROPOSAL`, not detected. Real hostile exploitation remains **not demonstrated** (unchanged from CTX-AUTH-001's threat model). The label contract has **not** been measured against a real local model (none in the verification sandbox). Pending owner decisions (none self-approved): approve the ADR; accept the label contract as 001b's closure mechanism; freeze-blocker classification (Moncif's call); the two REQUIRES-ADR contract rows; fate of the unmerged `ADR_KERNEL_05_CTX_AUTH_001B_DEFERRAL_PROPOSAL.md` -- see the ADR's "Decisions requested". REM-003 (structured `Context` discarded before any consumer) is **untouched** and still gates per-source provenance.

**REM-002 status note (Sept 15, 2026 freeze-classification pass, supersedes the branch-consolidation note below on verification method, not on conclusion):** Both `TestCtxAuth001StructuralContainment` and `TestCtxAuth001ParserAcceptance` were executed directly against current `main` rather than taken on the prior note's word. Result: **001a (structural) CLOSED** — `_neutralize_structural_tokens()` confirmed passing by execution. **001b (parser/authority acceptance) OPEN** — confirmed failing by execution; `_parse_hypotheses()` accepted an injection-shaped line as an ordinary, undifferentiated `IntentHypothesis`, reproducing the exact acceptance-indistinguishability this item's Action column's "authority framing" half was meant to prevent. Whole-repo grep (`main` and every branch, including `security/freeze-reconciliation-sep2026`, checked and ruled out as stale — 35 commits behind, no new content) confirms no `AuthorityLevel` type or equivalent exists anywhere; REM-004's status of `—` is therefore not just undocumented but structurally certain to be undocumented, since nothing has been built for it to document. **Explicit decision this pass: not closing 001b with a stopgap authority field bolted onto `IntentHypothesis`** — REM-002's own dependency on REM-004 ("required... to be meaningful, not a separable nice-to-have") is a statement about what a real fix requires, and a field added only to satisfy the test's assertion would not supply it. **Not marking REM-002 resolved.** Sequence going forward: whether REM-004 itself should be treated as Kernel v1.0-blocking (as distinct from Context-Compiler-blocking, which this tier already establishes) is Moncif's call, not resolved by this note.

*(Prior branch-consolidation note, kept for history, not superseded on its facts:)* `fix/context-security-findings-sep2026`
landed a partial mitigation — `core/cognitive/intent.py`'s prompt assembly now
structurally neutralizes tokens that could forge a second `Request:` section
(`TestCtxAuth001StructuralContainment`, verified passing). This is only the
structural-delimiting half of this item's own Action column; the
authority-framing half is not addressed, and this row's own dependency on
REM-004 ("required... to be meaningful, not a separable nice-to-have") is
therefore still unmet. A second, distinct component of the same original
CTX-AUTH-001 finding (per `CURRENT_STATE.md`'s own definition, which already
named both halves) — the hypothesis *parser* accepting an injection-shaped
completion line regardless of prompt containment — remains fully unaddressed
and is still red (`TestCtxAuth001ParserAcceptance`). Whether this partial mitigation is sufficient to de-prioritize
the remaining work pending Context Compiler, or whether the authority-taxonomy
and parser-side work should move up, is Moncif's call — this note documents
what changed, not what it means for the tier.

## Tier 2 — Must fix before Kernel/C-MoE integration

| ID | Item | Why this tier | Action |
|---|---|---|---|
| REM-005 | Re-evaluate global-pool scoping (Section 9) once genuine multi-worker parallelism exists | Not urgent under current single-path execution; becomes consequential specifically when C-MoE introduces parallel specialists with potentially different trust levels | Re-run the isolation-model question in Section 3 against the C-MoE design once it exists — do not pre-emptively redesign now |

## Tier 3 — Hardening (real, tracked, not blocking)

| ID | Item | Owning subsystem | Action | Test |
|---|---|---|---|---|
| REM-008 | CTX-EXPORT-001: `import_module()` has no content/signature validation, `overwrite=True` fully replaces a module's knowledge base | `core/brain_export.py` | Add checksum/signature verification on the bundle; restrict `bundle_path` to an expected directory; consider requiring explicit confirmation beyond a boolean flag for `overwrite=True` | None yet — recommended as a follow-up addition to this register |
| REM-009 | `core/runtime/efficiency.py`'s `PromptCache`/`cost_aware_call` — dead code, zero live callers | `core/runtime/` | Remove, or wire in and reconcile with `core/prompt/cache.py` rather than leaving two parallel implementations (same pattern as the already-tracked DEBT-016) | — |
| REM-010 | Stale `core/orchestrator.py` comment claiming `OrchestrationGovernor`/`AgentGovernor`/`ConversationGuardrails` don't exist | `core/orchestrator.py` | Update the comment; mechanical, not a judgment call | — |
| REM-011 | `KNOWN_ISSUES.md`'s DEBT-013 self-contradiction (active-table row vs. separately-placed resolved note) and `DEBT-017`'s misplacement outside the main table | `KNOWN_ISSUES.md` | Mechanical doc-sync fix, flagged early in this research track, never yet applied | — |

## Resolved

| ID | Item | Resolution |
|---|---|---|
| REM-001 | CTX-CACHE-001 | `cached_generate()` now hashes the full prompt instead of the lossily-compressed one. `TestCtxCache001Collision` passes. Landed via selective port from `fix/context-security-findings-sep2026` (branch-consolidation pass, Sept 2026). |
| REM-007 | CTX-DELETE-001 | `UnifiedMemory.delete()` now propagates the real L1 deletion outcome instead of an unconditional `True`. `TestUnifiedMemoryDelete::test_delete_returns_false_when_l1_storage_deletion_fails` passes. Landed via the same selective port. |
| REM-006 | CTX-SCOPE-001 | Mechanism (branch-consolidation pass) plus all identified live caller sites (this pass, `fix/ctx-scope-001-caller-wiring`): `core/workers/planner.py:218`, `core/model_router.py:314` (both `_dispatch_module()` branches — the closing audit's "`planner.py:305`" citation pointed at the caller, not the true sink), `interface/api.py:381` and its direct `stream_route()` call (found during this pass's own verification, not in the audit's list). Proven against a real `ContextMemory`: `tests/test_planner_worker.py::TestCtxScope001PlannerCallerWiring`, `tests/test_model_router.py`, `tests/test_api_context_scope.py`. One residual, unchanged, non-blocking fragility not touched by this pass: `core/workers/capability_executor.py:121` reaches the same `ModelRouter` chain with `context=""`, short-circuiting before `format_for_prompt()` fires — safe today by accident (audit row #6), not by design. |

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
