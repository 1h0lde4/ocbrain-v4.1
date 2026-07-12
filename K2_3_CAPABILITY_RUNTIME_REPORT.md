# OCBrain K2.3 — Capability Runtime, Adapter Layer & Resource Binding
## Report

**Date:** July 12, 2026
**Status:** Implementation complete. Base commit: `9a390ec` (current `main` tip — includes all of K2.2, verified live; see §0).
**Method:** Phase 0 reality audit (fresh clone, not the session prompt's claims) before any code, real regression suite before/after, new capability layer smoke-tested standalone before integration, mechanical (non-mocked) end-to-end verification via `scripts/integration_check.py`.

---

## 0. Phase 0 Reality Audit

The K2.3 prompt claims `Tag: kernel-v1.0` and that K2.1/K2.2 are complete with a specific live execution path. Checked directly rather than assumed, per the same discipline established in the K2.2 Cutover Report:

- **No `kernel-v1.0` tag exists** — same finding as K2.2, `git tag -l` returns nothing. Noted, not dwelt on further; this is now an established, consistent inaccuracy in how these session prompts describe the repository, not a new issue.
- **K2.1 and K2.2 genuinely are complete this time.** A fresh clone confirmed `core/orchestrator.py` carries the K2.2 cutover, `core/workflow/definition.py` has `build_planner_workflow()`, and all three K2.2 test files are present — commit `9a390ec`, which matches the K2.2 delivery exactly (`git diff --stat` against the prior commit showed the identical 1,343-line addition this session delivered last time). Good confirmation that the delivery-and-apply loop from K2.2 worked end-to-end.
- **Nothing capability/adapter/resource-shaped existed yet** — unlike K2.2 (where `WorkflowRuntime`/`PlannerWorker` were already built and merely unwired), a repository-wide search for capability/adapter/resource-manager code found nothing. This session's work is genuinely new, not a wiring-only fix.
- **`core/skills/skill_interface.py` (2 files, zero importers) and `core/provider_mesh.py` (271 lines, live but LLM-only) were re-confirmed exactly as `OCBRAIN_K1_5_KERNEL_API_SERVICE_MODEL.md` described them** — the latter document explicitly anticipated this session's shape: *"CapabilityRegistry... unifies skill_interface.py (currently orphaned) and provider_mesh.py (currently live but scoped to inference only) under one resolution contract."* `skill_interface.py`'s `BaseSkill` is a separate, distinct concept from what this session builds (see §7 for why it was deliberately left untouched).
- **`core/model_router.py`'s `ModelRouter` is substantially more than "module dispatch."** It owns a real, production bootstrap → shadow → native maturity lifecycle per module — training-pair recording, EMA maturity scoring, promotion, and regression rollback (`SHADOW_PROMOTE_THRESHOLD`, `REGRESSION_THRESHOLD`, etc.). None of this is mentioned anywhere in the K2.3 prompt. This is the single most consequential Phase 0 finding this session, and it directly shaped the design (§1, §5).

---

## 1. Capability Runtime Report

New package: `core/capabilities/` (9 files: `capability.py`, `resource.py`, `registry.py`, `adapter_runtime.py`, `adapters/{__init__,model_router_adapter,ollama_adapter,openai_compat_adapter}.py`, plus `__init__.py`).

**Design decision, stated plainly:** `ModelRouter`'s maturity/promotion/rollback system (§0) is real, tested, production behavior that the K2.3 prompt never asked to be touched, changed, or removed — and the prompt's own "Frozen Architecture" section instructs producing an ADR rather than silently redesigning anything discovered mid-session to be more complex than assumed. Rather than replace `ModelRouter` with a generic LLM adapter (which would delete working promotion/rollback logic), the Capability Runtime is built so `ModelRouter` becomes **one Adapter's internal implementation**, wrapped and documented, not bypassed. Two additional "pure" adapters (`OllamaAdapter`, `OpenAICompatAdapter`) also exist, proving the abstraction works end-to-end against a real, unwrapped provider — not only as a proxy for legacy code. Full rationale in `core/capabilities/adapters/model_router_adapter.py`'s own docstring.

**Scope decision:** only `CapabilityType.LLM_COMPLETION` has a registered `CapabilityContract` + real Adapters. The other 9 capability types the K2.3 prompt names as examples (Embedding, Web Search, Browser Automation, File Access, Memory Search, Graph Traversal, Image Generation, Tool Invocation, External API) are declared as type constants — so the namespace matches the target shape — but **not registered**, because nothing in this session's actual scope has a real, testable backend for them yet. Registering empty/fake adapters would repeat exactly the mistake `OCBRAIN_K1_6_RESOURCE_MODEL.md`'s Resource field audit corrected (rejecting fields with "zero evidence anywhere in the codebase that this is used").

---

## 2. Capability Registry Report

`core/capabilities/registry.py`. Pure metadata, no execution — confirmed by the file itself containing no `execute`/`invoke` method anywhere. Responsibilities implemented: `register_capability()`, `register_adapter()` (rejects registration against an unknown capability type — a configuration error caught at startup, not silently ignored), `get_contract()`, `get_adapters()` (returns a defensive copy — mutating the caller's list cannot corrupt registry state, verified by test), `list_capabilities()`, `validate()` (flags capabilities with zero adapters), `stats()`.

Deliberately mirrors the Registry/Runtime split `OCBRAIN_K1_5_KERNEL_API_SERVICE_MODEL.md` §2.1 already established for `WorkerRegistry`/`ExecutionRuntime` ("Registry answers 'what exists,' Resolver answers 'which one, right now'") — the same split, one layer over.

---

## 3. Adapter Runtime Report

`core/capabilities/adapter_runtime.py`. Owns: adapter selection, provider selection, adapter lifecycle (health/cooldown), execution delegation, failure isolation, fallback, diagnostics — matching the K2.3 prompt's Adapter Runtime responsibilities list item for item.

**Deliberately a direct generalization of `core/provider_mesh.py`'s `generate_with_fallback()`** — health-score ranking, cooldown-based availability, forced-choice-when-all-in-cooldown, exponential-backoff failure marking — rather than a new selection algorithm invented from scratch. This is an explicit application of the Kernel Constitution's Law of Evidence over Assumption: `provider_mesh`'s pattern is already production-proven for exactly this problem shape (which of several backends should serve this request, with graceful degradation), and re-deriving a different algorithm here would have no justification.

**Never raises** — every failure path (unknown capability, no adapters, all adapters exhausted, an adapter that raises rather than returning `success=False`) returns a `CapabilityResult(success=False, ...)`, matching `ExecutionRuntime.invoke()`/`WorkflowRuntime.execute()`'s established never-raise contract (Law of Failure Containment). Verified by test (`test_falls_back_past_a_raising_adapter`).

**Events:** `adapter.invoked` / `adapter.failed`, emitted per attempt, verified against the real `EventStream` singleton using the `since=` timestamp filter (§8 of the K2.2 Cutover Report already documented why count/slice comparisons are unsafe against `EventStream.query()`'s `ORDER BY sequence DESC LIMIT 100` behavior — that lesson was applied directly here, no repeat mistake).

---

## 4. Resource Binding Report

`core/capabilities/resource.py`, extending the K1.6-frozen Resource Model. Per K1.6 §2's "prove every field" discipline, only two Resource types are implemented, both with direct evidence in the existing codebase:

- **`HTTPClientResource`** — wraps `core.runtime.network.client`, a real, already-shared, already-lifecycle-managed (`close_client()`) global `httpx.AsyncClient`.
- **`ModelResource`** — represents one `(host, model_tag)` binding; real because `provider_mesh.OllamaProvider` already carries exactly these two fields per instance. `ResourceManager.bind_model_resource()` returns the *same* Resource identity for repeated binds of the same pair (deterministic `resource_id`), verified by test, consistent with K1.6 §6's "cross-resource references are always by ID" rule.

GPU, Filesystem, Browser Session, Database, MCP Server (also named in the K2.3 prompt) are **not implemented** — no Adapter in this session's actual scope needs them. Declaring unused Resource types would be exactly the speculative-structure mistake K1.6 already rejected once for the base Resource Protocol's own fields.

`ResourceManager` is constructed once in `main.py` and passed explicitly into `AdapterRuntime`, which hands it to each Adapter's `execute()` call — no global state, no singleton lookup from inside an Adapter, per the K2.3 prompt's explicit Resource Binding requirement.

---

## 5. Legacy Dispatch Migration Report

**Before:** `PlannerWorker._dispatch_module()` called `self._model_router.route(mod_name, query, self._context_memory)` directly — a concrete dependency on `ModelRouter`.

**After:** `_dispatch_module()` calls `self._adapter_runtime.invoke(CapabilityType.LLM_COMPLETION, request=...)` when `adapter_runtime` is configured (production, always — see §6). PlannerWorker now imports `CapabilityType`, not `ModelRouter` — it knows *that* an LLM-completion capability exists, not *which* concrete router/provider fulfills it, matching the K2.3 prompt's "Workers must never know concrete providers. Workers only know Capabilities" requirement literally.

**Documented compatibility wrapper (per the prompt's explicit allowance — "Modules may temporarily remain as compatibility wrappers. However: Every compatibility wrapper must be documented"):** `ModelRouterAdapter` wraps the unmodified `ModelRouter` singleton and is registered first (default choice) for `LLM_COMPLETION`. Its docstring is the required documentation: what it wraps, why (§0's maturity-system finding), and a stated (not scheduled) sunset condition — removable once `ModelRouter`'s promotion logic is itself reviewed and either kept as deliberate `AdapterRuntime`-level policy or migrated, a K3+ decision.

**Backward-compatible fallback, not a second production path:** `_dispatch_module()` still falls back to `self._model_router.route()` directly if `adapter_runtime` is `None` — but `main.py`'s composition root always supplies `adapter_runtime` now (§6), so this fallback is test-only in production, exactly the same standard K2.2 established for `Orchestrator.handle()`'s `workflow_runtime=None` branch. All 11 pre-existing `tests/test_planner_worker.py` tests (K2.2, construct with `model_router=` only) pass unmodified — this is the proof the fallback genuinely still works, not just an assertion.

**Bug fixed in the same change:** the prior "neither `model_router` nor anything else configured" branch returned a bare `WorkerResult` object directly into what `asyncio.gather()` collects — `_run()`'s result-processing loop only checks `isinstance(res, Exception)`, so a `WorkerResult` would have silently leaked into `merger.merge()` uncaught (`merger.merge()` expects `RouteResult`-shaped objects with `.answer`). This session's replacement raises `RuntimeError` instead, which the existing containment already formats correctly (`"[Error in {mod_name}: {res}]"`) — a strict correctness improvement, verified by a dedicated regression test (`test_no_adapter_runtime_and_no_model_router_is_contained_not_raised`), not just a refactor.

---

## 6. Composition Root Review

| Component | Instantiated? | DI'd? | Reachable from `main.py`? | Exercised in production? |
|---|---|---|---|---|
| `ResourceManager` | **Yes — new** | Yes | Yes | Yes |
| `CapabilityRegistry` | **Yes — new** | Yes | Yes | Yes |
| `ModelRouterAdapter` (wraps `model_router`) | **Yes — new** | Yes | Yes | Yes — default adapter |
| `OllamaAdapter` | **Yes — new** | Yes | Yes | Fallback only (verified reachable, not the default path — see §8) |
| `OpenAICompatAdapter` | **Yes — new** | Yes | Yes | Fallback only, and self-reports unavailable unless `global.openai_compat_url` is configured (unchanged `provider_mesh` behavior, reused not reimplemented) |
| `AdapterRuntime` | **Yes — new** | Yes | Yes | Yes |
| `PlannerWorker` | Yes (K2.2) | **Changed** — `constructor_kwargs` now passes `adapter_runtime` instead of `model_router` | Yes | Yes |
| Everything else (Kernel, EventStream, GovernanceKernel, WorkerRegistry, ExecutionRuntime, WorkflowRuntime, Orchestrator) | Yes (K2.1/K2.2) | Yes | Yes | Yes — unchanged this session |

`main.py`'s module docstring and final startup log line were updated to reflect K2.3 (`"K2.3: CapabilityRuntime LIVE"`), matching the K2.2 precedent of keeping these accurate rather than aspirational (§0 of the K2.2 report flagged the previous log line as inaccurate at the time it was written — this session's own log line is the one now claiming production status, and §8 below is the mechanical proof backing that claim, not just the log statement itself).

---

## 7. Runtime Reachability Audit

Two-part verification, matching the K2.2 standard:

1. **Static** — traced above (§6), confirmed by direct file read of `main.py`.
2. **Mechanical** — `scripts/integration_check.py` §8 (new this session) builds the real object graph (`CapabilityRegistry` → `AdapterRuntime` → `ModelRouterAdapter` wrapping a real `ModelRouter`, registered alongside `OllamaAdapter`/`OpenAICompatAdapter` in the exact order `main.py` uses) and asserts:
   - `k23_registry.validate() == []` — no unfulfilled capability, confirmed against the real registry shape, not a test double.
   - The full chain (`Orchestrator.handle()` → `WorkflowRuntime` → `ExecutionRuntime` → `PlannerWorker` → `AdapterRuntime` → `ModelRouterAdapter` → `ModelRouter`) returns the correct answer end-to-end, with only the network-level seam (`ModelRouter.route()`, which would otherwise hit a real Ollama server) patched.
   - `adapter.invoked` actually appears in the real `EventStream`.
   - The invoked event's `adapter` field is `"ModelRouterAdapter"` — **mechanical proof `ModelRouterAdapter` is genuinely the default chosen adapter in the real registration order**, not merely "registered somewhere."

   Run output: all 20 checks (15 pre-existing from K2.1/K2.2 + 5 new) `PASS`. No bugs found in this section this session (contrast with K2.2, where the equivalent section caught a real `EventStream.query()` misuse — the lesson from that was applied proactively here, using `since=` from the start rather than count/slice).

`OllamaAdapter`/`OpenAICompatAdapter`'s reachability as *fallback* adapters (not the default path) is verified by `tests/test_capabilities.py::TestAdapterRuntimeSelection::test_falls_back_to_second_adapter_on_failure` and the health-ranking tests — they are registered, resolvable, and would be attempted if `ModelRouterAdapter` failed, but are not exercised by default in `integration_check.py` since `ModelRouterAdapter` succeeds first (by design — see §5).

---

## 8. Governance ADR

Produced as a separate document: **`ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md`**. Per the K2.3 prompt's explicit instruction, this is discussion-only — it changes no code and no governance behavior. Summary: the existing dual-evaluation pattern (Orchestrator level + Worker-template-method level) is safe today because `RecursionGovernor`/`BudgetGovernor` are stateless per call, but that safety is a convention, not an enforced invariant, and doesn't automatically extend to future governors. K2.3 explicitly decided **not** to add a third governance touchpoint inside the new `AdapterRuntime`, for two reasons documented in the ADR itself: the prompt's own instruction not to change this behavior this session, and a genuine open question (should governance apply once per capability request or once per adapter-fallback-attempt?) that shouldn't be decided without evidence from real adapter-fallback traffic. Two consolidation directions for K3 are presented as alternatives, not a single recommendation — the ADR is explicit about not choosing between them.

---

## 9. Legacy Audit

| Component | Still used? | Bypassed? | Obsolete? | Removable after K2.4? |
|---|---|---|---|---|
| `ModelRouter` (bootstrap/shadow/native maturity logic) | Yes — fully, unmodified, wrapped by `ModelRouterAdapter` | No — it's the default adapter | No | No — this is real, live, production behavior; not a migration target this session or a known-obsolete item |
| `PlannerWorker._model_router` direct-call fallback | Test-construction only (§5) | Yes, in production | Not yet — still test-reachable | Yes, once `tests/test_planner_worker.py`'s `model_router=`-only tests are migrated to construct a real `adapter_runtime` instead, same standard as K2.2's Orchestrator-level legacy branch |
| `skill_interface.py` / `BaseSkill` | Unrelated to this migration (§0) | No | No | No — separate, still-orphaned concept, out of scope this session (see §11) |
| K2.2's own legacy `Orchestrator._run_module()`/classify-dispatch-merge branch | Unchanged this session | Unchanged | Unchanged | Tracked in the K2.2 Cutover Report, not re-audited here — no new information this session |

No legacy component was removed this session — none is provably unused (tests still reach the `model_router`-only fallback), consistent with the prompt's own instruction: *"Do not remove anything without proving it is unreachable."*

---

## 10. Technical Debt Report (new items surfaced this session)

| Item | Severity | Notes |
|---|---|---|
| Test-suite pollution of tracked files (`config/*.toml`, `modules/*/knowledge.db/*`) | Low–Medium | **Same reproducible issue flagged in the K2.2 Cutover Report §8, confirmed reproducible a second time this session.** Not fixed here — unrelated to K2.3's scope, and fixing it now would be exactly the "unrelated refactor" PI §18.4.8 warns against. Worth a dedicated small session. |
| `ModelRouter`'s maturity/promotion system has no Capability/Adapter-level visibility | Low | `ModelRouterAdapter` surfaces `source`/`similarity`/`route_latency_ms` in `CapabilityResult.metadata`, but `AdapterRuntime`'s own health/cooldown tracking (from `BaseAdapter`) is entirely separate from `ModelRouter`'s own internal maturity scoring — two independent notions of "is this adapter/module healthy" exist side by side. Not a bug (each is scoped correctly to what it tracks), but worth a design note for whoever eventually reviews consolidating them. |
| `CapabilityRequest.payload` is an untyped dict | Low | Deliberate, stated in `capability.py`'s own docstring — a typed-per-capability request hierarchy designed against a sample size of one real capability (`LLM_COMPLETION`) would be premature structure. Revisit once a second capability type is actually registered. |
| Governance ADR leaves a real open question undecided (§8) | N/A — by design | Not debt; an explicitly deferred decision, per the prompt's own instruction. Flagged here only so it isn't lost track of before K3. |

---

## 11. What Was Deliberately Not Touched

- **`core/skills/skill_interface.py` / `BaseSkill`** — a separate, pre-existing, still-orphaned concept (zero importers, confirmed again this session). `OCBRAIN_K1_5_KERNEL_API_SERVICE_MODEL.md` §1.1 already names `Skill` as "the current, forward-looking name for a typed, contract-bearing Capability" — suggesting eventual reconciliation with what this session builds — but K2.3's prompt scopes Capability/Adapter/Resource specifically around *provider access* (LLM, embedding, browser, etc.), a lower-level concern than a versioned, user-authored `.skill.md`-style executable bundle. Forcing a merge now, unasked, would be exactly the kind of silent redesign the "Frozen Architecture" section forbids. Recommend a dedicated ADR (not this session's, a future one) specifically on Skill/Capability reconciliation.
- **`ModelRouter`'s internals** — confirmed unmodified, byte-for-byte, by `git diff`. Only wrapped.
- **Any second governance evaluation point** — see §8.

---

## 12. Regression Report

- **Baseline (current `main` tip, `9a390ec`, before any K2.3 change):** 581 passed, 0 failed (same exclusions as K2.2: `test_stress.py`, `chaos_monkey.py` non-standard; `test_cognitive_memory.py` — pre-existing, unrelated `fusion_engine` import error, confirmed still present and still unrelated).
- **After all K2.3 changes + new tests:** **620 passed, 0 failed** (581 + 39 new: 33 in `tests/test_capabilities.py`, 6 in `tests/test_planner_capability_migration.py`).
- **Regressions introduced:** none.
- **Bugs found and fixed:** 1 — the `WorkerResult`-leak in `_dispatch_module`'s no-backend-configured branch (§5), a latent issue in K2.2-era code, not something this session's new capability layer introduced. The new `core/capabilities/` package itself had zero bugs found by its own 33-test suite (contrast with K2.2's `WorkflowRuntime`, which had two) — attributed to deliberately mirroring `provider_mesh.py`'s already-proven selection/fallback algorithm rather than designing a new one from scratch (§3).
- **Mechanical verification:** `scripts/integration_check.py`, 20/20 checks pass (§7).

---

## 13. Updated Roadmap

```
K2.1  ExecutionRuntime, ExecutionContext, WorkerRegistry ................ COMPLETE

K2.2  WorkflowRuntime, PlannerWorker wiring, production cutover ......... COMPLETE
      (verified live on main tip 9a390ec this session, §0)

K2.3  Capability Runtime, Capability Registry, Adapter Runtime,
      Resource Binding, Legacy Dispatch Migration ....................... COMPLETE
      - CapabilityRegistry, ResourceManager, AdapterRuntime: new, tested
      - ModelRouterAdapter: documented compatibility wrapper around the
        unmodified ModelRouter maturity/promotion system
      - OllamaAdapter, OpenAICompatAdapter: "pure" capability path,
        registered as fallback, reachability verified by test
      - PlannerWorker._dispatch_module(): migrated to capability-based
        dispatch, with a K2.2-style backward-compatible fallback and one
        latent bug fixed in the same change
      - Governance ADR produced (ADR_K2_3_01), no behavior changed
      - Only LLM_COMPLETION registered; 9 other capability types declared
        but not implemented -- explicit scope decision, not an oversight

K2.4  Governance completion (next)
      - Remaining governors, policy engine, per-capability governance,
        execution policies
      - Should read ADR_K2_3_01 before deciding whether/how
        AdapterRuntime gets its own governance touchpoint (§8's open
        question)

K3    Kernel validation, architecture compliance, performance/stress
      testing, compatibility-layer removal, governance consolidation
      (per ADR_K2_3_01) .................................................. UNCHANGED,
      now informed by ADR_K2_3_01's two consolidation options

K4    Runtime optimization, profiling, scheduling, caching,
      concurrency tuning ................................................ UNCHANGED
```

---

## 14. Complete Modified File List

**Modified:**
- `core/workers/planner.py` — `adapter_runtime` constructor param, `_dispatch_module()` migrated to capability-based dispatch with documented fallback, latent `WorkerResult`-leak bug fixed.
- `main.py` — `CapabilityRegistry`/`ResourceManager`/`AdapterRuntime` construction, 3 adapters registered, `PlannerWorker`'s `constructor_kwargs` switched from `model_router` to `adapter_runtime`; docstring and startup log updated.
- `scripts/integration_check.py` — extended with a real, non-mocked K2.3 wiring section (5 new checks).

**Created:**
- `core/capabilities/__init__.py`
- `core/capabilities/capability.py`
- `core/capabilities/resource.py`
- `core/capabilities/registry.py`
- `core/capabilities/adapter_runtime.py`
- `core/capabilities/adapters/__init__.py`
- `core/capabilities/adapters/model_router_adapter.py`
- `core/capabilities/adapters/ollama_adapter.py`
- `core/capabilities/adapters/openai_compat_adapter.py`
- `tests/test_capabilities.py` — 33 tests.
- `tests/test_planner_capability_migration.py` — 6 tests.
- `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` — the requested ADR.
- `K2_3_CAPABILITY_RUNTIME_REPORT.md` — this document.

**Explicitly reverted (test-run side effects, not real changes — see §10):** `config/models.toml`, `config/settings.toml`, `config/sources.toml`, `modules/empty_test/knowledge.db/chroma.sqlite3`, `modules/mock/knowledge.db/*`, `modules/system_ctrl/knowledge.db/chroma.sqlite3`.

---

## 15. Readiness Assessment

**READY FOR K2.4 — Governance Completion & Policy Engine.**

All stated success criteria met: Capability Runtime operational, `CapabilityRegistry` owns resolution (metadata only, verified no execute method), `AdapterRuntime` owns provider selection (verified via the health-ranking/fallback test suite and the mechanical default-adapter proof in §7), Workers depend only on Capabilities (`PlannerWorker` no longer imports `ModelRouter`), providers hidden behind Adapters, Resources bound through the Resource Model (2 real types, evidence-grounded, no speculative ones), legacy module dispatch (the direct `model_router.route()` call) removed from the canonical path with a documented, test-verified compatibility bridge for backward compatibility only, composition root updated and reviewed, runtime reachability verified both statically and mechanically, Governance ADR produced without changing governance behavior, no production-disconnected implementation remains (everything in `core/capabilities/` is constructed and reachable from `main.py`, confirmed in §6/§7).

One thing carried forward deliberately rather than resolved: `ADR_K2_3_01`'s open question (per-request vs. per-adapter-attempt governance grain, if/when `AdapterRuntime` gets its own check) should be read before K2.4 starts, since K2.4's own scope ("per-capability governance") is exactly the question that ADR raises.
