# OCBrain C-MoE — Lower-Level Routing Boundary Reconciliation

**Date:** September 10, 2026
**Repository:** `1h0lde4/ocbrain-v4.1`, branch `main`, HEAD `379d778`
**Method:** Direct code inspection of every component named below (full-file reads, not docstring summaries), cross-referenced against the main C-MoE study (`OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md` §17–29, §33–34, §39, §44–45, §67, §69, §84–91), the Context Compiler remediation register, and three external precedents (NVIDIA Personal-AI-Router, RouterEval, RGD/CASCAL) verified directly against their own source rather than trusted from a secondhand description.

**Evidence-provenance convention for this document:** every claim is tagged `FACT` (read directly from current source this session), `ABSENCE` (a specific thing was searched for and confirmed not present — distinct from "not yet checked"), or `UNRESOLVED` (a real, named gap in the evidence, not filled with a plausible guess). This mirrors the project's existing `[VERIFIED-FRESH]`/`[NOT COMPLETED THIS PASS]` convention used in the Kernel closure audits.

**Scope boundary, stated explicitly:** this document reconciles the routing/model-selection layer only. It does not address the CTX-DELETE-001/CTX-AUTH-001 freeze-blocking classification dispute between the two Kernel v1.0 audits (`OCBRAIN_KERNEL_V1_FREEZE_AUDIT_SEPT_2026.md` vs. `docs/Bugs Hunt & fix reports/KERNEL_V1_0_CLOSURE_AUDIT_SEP2026.md`) — that is a separate, unresolved architecture/priority decision, tracked here only as a pointer, not analyzed further.

---

## 1. Executive Summary

C-MoE (expert selection) does not exist in this repository in any form — `FACT`, confirmed by this session's reading of every component below, none of which references an expert-selection concept. What does exist is a working, three-tier routing stack (module selection → capability implementation selection → model/provider selection) that C-MoE would sit *above*, not inside.

The central finding: **`ModelRouter`'s bootstrap→shadow→native lifecycle is not a form of expert-selection maturity.** It is a layer-D (model/provider selection) mechanism — a per-`module_name`, globally-scoped, empirical-equivalence-to-a-reference-model promotion ladder — answering "which underlying model serves an already-chosen module" rather than "which specialist should handle this work." The two share a mechanism *shape* (probationary parallel-run, compare, promote-by-threshold, regression rollback) but operate on different identity axes, at different layers, with different persistence scopes. Classified as **DIFFERENT CONCEPTS**, with a secondary **EVIDENCE PROVIDER / CONSUMER** relationship plausible if C-MoE is later built on top of named modules. The final `REUSE`/`ADAPT`/`KEEP SEPARATE`/`REJECT` disposition is reserved for Moncif — this document supplies evidence, not the verdict.

Three genuine, evidenced problems were found that are independent of that central question and do not wait on its resolution:

1. `ModelRouter`'s own promotion state has three live writers, not one.
2. Module/expert selection is currently duplicated across two live, never-cross-validated mechanisms.
3. The Kernel's own identity chain (`root_operation_id`/`attempt_id`) does not reach the capability/routing layer at all.

---

## 2. Component inventory (current repository, `FACT` throughout unless marked otherwise)

### 2.1 `ModelRouter` (`core/model_router.py`, 577 lines) — layer D

- **Identity/key:** `module_name` (string) — a named cognitive module (e.g. `knowledge`, `web_search`, `coding`), confirmed by cross-reference against `modules/*/module.py`'s `self.name` usage. Not a model instance, not a backend, not a capability_type.
- **Lifecycle stages:** `"bootstrap"` / `"shadow"` / `"native"` — raw string literals, no enum.
- **Transitions:** bootstrap→shadow at `query_count >= 500` (quality-blind). shadow→native at the *same* monotonic `query_count >= 500` (never reset per stage) **and** `maturity_score >= 0.85`. native→shadow (the only rollback path) when a 100-sample rolling average of 5%-sampled spot-check scores drops below `0.70`. No shadow→bootstrap path exists.
- **Metric:** `similarity` between the own-model answer and the external-model answer for the same query (embedding cosine, lexical Jaccard-cosine fallback) — agreement-with-a-reference, not verified correctness. Never imports `core/verification/` — `ABSENCE`, confirmed by import-list inspection.
- **Persistence:** dual-path — `config.set_module_state()` (TOML, `config/models.toml`) and, separately, `state_store.update_maturity()` / `record_training_pair()` (`core/runtime/state.py`'s `StateStore`).
- **Scope:** global. `ABSENCE` of `user_id`/`project_id`/`discussion_id`/`task_id` anywhere in the state keys — one `stage`/`maturity_score` per `module_name`, shared across every caller.
- **`_CRITICAL_STATE_KEYS`** (`core/config.py`): `{stage, bootstrap_model, base_model, active_weights}` persist synchronously; `query_count`/`maturity_score`/`train_pairs`/`last_trained` are deferred/batched (the "A6 audit fix," already resolved per its own historical trail).

**Finding — multiple writers, not one (state-ownership concern, distinct from routing authority):**

| Writer | Trigger | Fields written | Live? |
|---|---|---|---|
| `ModelRouter.route()`/`stream_route()` | Every live query | `stage`, `maturity_score`, `query_count` | `FACT`, primary path |
| `learning/scheduler.py._training_cycle()` | Periodic, after offline fine-tune + eval pass | Calls `model_router._update_maturity(name, 0.7)` then `_maybe_promote(name)` — both private methods, called directly from outside the class | `FACT` — confirmed by direct read |
| `core/brain_export.py:194` | Explicit human-initiated `.ocbrain` bundle import | `stage` (from the bundle's manifest) | `FACT` — legitimate (imported trained weights must carry their stage with them), but still a second writer |
| `learning/finetuner.py` | After each fine-tune run | `train_pairs`, `last_trained` only — **not** `stage`/`maturity_score`/`own_model_tag` | `FACT` |

**Classification: `DUPLICATION RISK`** on the `stage`/`maturity_score` decision specifically (scheduler.py's offline-eval path and the live similarity path feed the same mechanism via two different evidence sources, with no documented reconciling contract) — not `CONFLICT` (they are sequenced, not simultaneous).

**`UNRESOLVED`:** which code path writes `own_model_tag`. Neither `finetuner.py` nor `scheduler.py`'s visible calls set it; likely inside `module.load_weights()`, not read this session.

**`UNRESOLVED`:** the long-form/streaming generation path. `_call_external`/`_call_own_model` do call `provider_mesh.generate_with_fallback()` (confirmed by direct read). A separate `httpx.AsyncClient(timeout=120.0)` call exists elsewhere in the file (~line 280), bypassing `generate_with_fallback`'s health/cooldown tracking entirely — its full retry behavior was not read this session.

### 2.2 `AdapterRuntime` (`core/capabilities/adapter_runtime.py`, ~194 lines) — layer C

Given a `capability_type`, ranks registered `Adapter`s by `health_score`/`is_available()` (cooldown-based), tries in ranked order, forced-choice-to-soonest-recovering if all are in cooldown. Identity: Adapter-instance (`adapter_name`), not `module_name`. `ABSENCE` of any reference to ModelRouter's stage/bootstrap/shadow/native concepts anywhere in the file — `ModelRouterAdapter` is one opaque `Adapter` among several, ranked purely on `health_score`. It cannot override ModelRouter's internal decision and cannot be overridden by it — non-overlapping identity axes. Docstring states it is "a deliberate, direct generalization of `provider_mesh.py`'s `generate_with_fallback()`" — confirmed structurally identical (see 2.4).

### 2.3 `CapabilityRegistry` (`core/capabilities/registry.py`, 100 lines) — metadata only

`FACT`, confirmed by direct read, not inference: no `execute()`/`invoke()` method exists anywhere in the file. `register_adapter()` is a list append; `get_adapters()` returns a copy, no ranking. All selection logic lives in `AdapterRuntime`. Docstring explicitly cites the same Registry/Runtime split already established for `WorkerRegistry`/`ExecutionRuntime` (`OCBRAIN_K1_5_KERNEL_API_SERVICE_MODEL.md` §2.1). No selection authority has leaked in.

### 2.4 `provider_mesh.py` (276 lines) — provider layer

`Provider` base class (`health_score`, `cooldown_until`, `is_available()`, `mark_success()`/`mark_failure()`, exponential backoff 60s→120s→240s capped at 1hr) — structurally identical to `AdapterRuntime`'s `Adapter` protocol, confirmed by direct comparison, not assumed from the docstring lineage claim. `OllamaProvider` and `GenericOpenAICompatibleProvider` are the only two concrete providers — `ABSENCE` of any multi-machine/physical-node discovery concept. `resolve_provider(module_name)` reads `bootstrap_model` from `get_module_state()`. `generate_with_fallback()`: eligibility filter → health-ranked order → sequential try → mark success/fail. This is the *same shape* PAIR implements (§4), independently, already live in this codebase, one layer below `AdapterRuntime`.

### 2.5 Module/expert selection — duplicated across two live entry paths

**`FACT`:** two different, live mechanisms decide `module_name`, depending on which entry point receives a request:

- **`classifier_v3.classify()`** — the production path, imported by `core/orchestrator.py`, `core/orchestrator_v3.py`, and `core/workers/planner.py`. Primarily **semantic** (embedding cosine similarity against each module, threshold >0.3, or top match if >0.1), with a pure-keyword `_keyword_fallback()` used only when embeddings are unavailable. Returns a *scored list*, not a single module — can select more than one.
- **`classifier` (v1) `.label()` + `decomposer.build()`** — used only by `interface/api.py`'s SSE streaming endpoint, for single-task queries (`len(tasks) == 1`), which then calls `model_router.stream_route()` **directly**, bypassing `AdapterRuntime`/`CapabilityRegistry` entirely, because it needs true token-level streaming.

These are structurally gated apart (task-count branch), so they do not race on the same request — but the underlying classification *logic* genuinely differs and has never been cross-validated. Classified as **potential duplication**, not confirmed conflict.

**`FACT`, correcting an earlier working hypothesis in this reconciliation:** `core/workers/planner.py`'s own direct call to `model_router.route()` is **not** a live second authority. Its docstring states plainly: "K2.3 — Legacy Dispatch Migration... Fallback path: `self._model_router.route()` directly, kept only for backward compatibility with existing test code... not reachable in production," since `main.py`'s composition root always supplies `adapter_runtime`. The preferred, and only production, path is Planner → `CapabilityRequest` → `AdapterRuntime.invoke(LLM_COMPLETION)` → ranked adapters → (if `ModelRouterAdapter`) → `ModelRouter.route()`.

### 2.6 Identity/provenance — a confirmed gap, not a target-vs-current distinction

`FACT`: `root_operation_id`/`attempt_id` (ADR-KERNEL-01) are confirmed present at `Goal`/`ExecutionPlan`/`WorkflowDefinition`/`WorkflowNodeState`. `ABSENCE`: neither appears anywhere in `core/capabilities/*.py`, `core/capabilities/adapters/*.py`, `core/model_router.py`, `core/provider_mesh.py`, or `core/workers/planner.py` (repo-wide grep, zero hits). `CapabilityRequest` carries only `trace_id` — a fresh UUID, unrelated to the operation/attempt chain. **The Kernel's identity chain is actively dropped at the `CapabilityRequest` boundary today** — this is not unbuilt future work, it is a live, confirmed break in provenance for every request that reaches the routing layer.

---

## 3. External precedent, correctly scoped (not architecture requirements — `PRECEDENT`/`EVIDENCE` only, per the external-source transfer rule)

- **NVIDIA Personal-AI-Router (PAIR)** — verified directly against `github.com/NVIDIA/Personal-AI-Router`. A home-LAN inference distributor (Electron + Go), not a datacenter or multi-node fabric. Its algorithm: filter to nodes whose discovery inventory advertises the requested model → manual-node override → job-scheduler priority (pending workload + smoothed GPU pressure) → deterministic default order. **`ABSENCE` of any maturity/trust concept** — every advertising node is treated as equally trustworthy; this is pure real-time load balancing among already-vetted candidates. Relevant as precedent for a backend/node-dispatch layer, which OCBrain does not currently have (§4 below) — not relevant to expert selection or to ModelRouter's maturity concept, which solves a different problem (trust built up over time) that PAIR's design doesn't need.
- **RouterEval** (EMNLP, arXiv 2503.10657) — a benchmark for model-level routing from a candidate pool (8,500+ models, pool sizes 3–1,000, baselines from kNN through RoBERTa classifiers). Relevant to request/content-conditional model routing — i.e., C-MoE's own future territory (§17–27) — not to the routing stack that exists today.
- **Routing with Generated Data / CASCAL** (ACL 2026, Niu et al.) — trains routers without ground-truth labels via LLM-generated data; CASCAL identifies model-specific skill niches via consensus-voting correctness estimation and hierarchical clustering. Directly relevant to §21's Routing Signals design, since OCBrain has no labeled ground truth for "which module/expert is right for this request" any more than CASCAL's setting does — concrete, usable supporting evidence, not just background reading.

---

## 4. §21 Routing Signals — current-state disposition

C-MoE does not exist, so "does C-MoE see/own it" is `N/A` throughout. This table records what layer computes each signal *today*, and whether a future C-MoE should own or merely consume it.

| Signal | Current owner | Type today | C-MoE should own? |
|---|---|---|---|
| Task fit / specialization | `classifier_v3` (semantic similarity) | Runtime-supplied, soft | Yes — this *is* expert selection |
| Confidence | `classifier_v3`'s score | Runtime-supplied, soft | Yes |
| Historical performance | `ModelRouter.maturity_score` | Model/provider-supplied, soft | No — consume read-only |
| Verification history | Does not exist (Phase C unwired) | N/A | Consume once wired — never own |
| Resource/provider availability | `AdapterRuntime`/`provider_mesh` `is_available()` | Capability/backend-supplied, **hard** | No — respect, never override |
| Model maturity (stage) | `ModelRouter.stage` | Model/provider-owned | No |
| Implementation reliability | `AdapterRuntime.health_score` | Capability-owned | No |
| Backend health | `provider_mesh.health_score` | Backend-owned | No |
| Trust/authorization | `GovernanceKernel` (not traced this pass) | Governance-supplied, **hard** | Never |
| **Latency (measured)** | **`ABSENCE`** — only budget ceilings exist (60s `generate_with_fallback`, 120s long-form), no measured/ranked latency signal found anywhere read this session | — | — |
| **Cost (measured)** | **`ABSENCE`** — not tracked anywhere in the components read | — | — |
| **Node load** | **`ABSENCE`** — no physical-node concept exists to have load in the first place (§5) | — | — |
| Execution history | `state_store.query_count`/`record_training_pair()` | Model/provider-owned | No |

The latency/cost/node-load rows are marked `ABSENCE`, not `UNRESOLVED`: these were specifically searched for across every component in §2 and confirmed not present, as distinct from simply not yet having been checked.

---

## 5. Authority matrix

Refinement applied before finalizing this table: **candidate eligibility (layer A) and model-stage gating (part of layer D) are kept structurally separate, deliberately.** `AdapterRuntime.is_available()` answers "is this adapter instance currently usable at all" — a binary, cooldown-based gate over *interchangeable implementations* of the same capability. `ModelRouter.stage` answers a different question: "for a module that has already been selected, which model *variant* (external vs. own-trained) is the current promotion state allowed to use." Folding the second into "eligibility" would silently reintroduce the exact layer conflation this reconciliation exists to eliminate — stage is a **layer-D selection input**, not a layer-A/C-style eligibility filter, even though both are gates. They are listed separately below for that reason.

| Decision | Owner | Candidate set | Persistence | Fallback/retry |
|---|---|---|---|---|
| A. Candidate eligibility (adapter instances only) | `AdapterRuntime._is_available()` | Registered `Adapter`s for a `capability_type` | In-memory on the Adapter object — `UNRESOLVED`, `Adapter`'s own class not read | Ranked retry within `AdapterRuntime.invoke()` |
| B. Expert/module selection | Split — `classifier_v3` (main path) / `classifier`v1+`decomposer` (SSE path) | Registered modules | `ABSENCE` of any persistence found | None |
| C. Capability implementation selection | `AdapterRuntime._rank_adapters()` | `CapabilityRegistry.get_adapters()` (discovery-only) | Same as A | Same as A |
| D. Model/provider selection, *including* stage-gating | `ModelRouter.route()` (primary; not sole state-writer — §2.1) | bootstrap/shadow/native for a given `module_name` | `config` (TOML) + `StateStore`, global scope | native→shadow rollback only; no retry of the current call |
| E. Backend/node dispatch | **Does not exist as a distinct layer** — closest analog is `provider_mesh`'s provider-*type* choice (Ollama vs. OpenAI-compatible), which is single-machine, not multi-node | — | — | — |
| F. Fallback | Layered by design, no single owner: `AdapterRuntime` (adapter-level) and `provider_mesh.generate_with_fallback` (provider-level) | — | — | Exponential backoff (provider layer); ranked retry + cooldown (adapter layer) |

Fallback is recorded here as genuinely distributed across layers, by design (confirmed via the explicit docstring lineage in §2.2/§2.4), not consolidated into one invented owner — doing so would misrepresent evidence that supports deliberate layering, not a gap.

---

## 6. Duplication / risk register

- **Confirmed duplication:** `ModelRouter`'s `stage`/`maturity_score` state (§2.1) — three writers, two independent evidence sources feeding one promotion mechanism, no documented reconciling contract.
- **Potential duplication:** two live, never-cross-validated module-selection mechanisms (§2.5) — structurally non-racing, but capable of disagreeing on the same kind of query depending on entry point.
- **Harmless layering, confirmed by design:** `provider_mesh` → `AdapterRuntime` (explicit docstring lineage, structurally identical `Provider`/`Adapter` protocols); `CapabilityRegistry`/`AdapterRuntime` mirrors the established `WorkerRegistry`/`ExecutionRuntime` split; Planner's legacy direct-`ModelRouter` call, confirmed dead in production.
- **Unresolved:** the long-form generation path's real fallback behavior (§2.1); `own_model_tag`'s writer (§2.1); whether the SSE fast-path's bypass of `AdapterRuntime` also bypasses governance/verification hooks that live at that layer (not evaluated this session).

---

## 7. `ModelRouter` maturity disposition — evidence, verdict reserved

**Evidence:** `module_name` is fixed *before* `ModelRouter.route()` is ever invoked, by whichever classifier fired (§2.5). ModelRouter's own decision is layer D — which underlying model serves an already-chosen module — global-scoped, and already has three write paths into the same state (§2.1).

**Interpretation:** the mechanism *shape* (probationary parallel-run, compare, promote-by-threshold, regression rollback) is shared with what an expert-level maturity concept would plausibly need, but it is applied to a different decision, on a different identity axis, at a different layer, with a different (and currently problematic) persistence scope.

**Classification: `DIFFERENT CONCEPTS`**, secondary relationship **`EVIDENCE PROVIDER / CONSUMER`** (plausible, not confirmed) — if a future Expert is built on top of a given `module_name`, that module's current stage is a legitimate read-only input to the Expert's own trustworthiness, but copying the mechanism upward into `ExpertDescriptor.maturity_stage` as the same field would import all three of §2.1's unresolved problems (multiple writers, global scope, non-content-aware signal) into C-MoE's own architecture.

**Evidence leans toward Option B** (§8 of the original reconciliation brief: C-MoE consumes lower-layer maturity as a read-only routing input) **over Option A or C.** This is not the final disposition — `REUSE` / `ADAPT` / `KEEP SEPARATE` / `REJECT` is reserved for Moncif.

---

## 8. Impact on the main C-MoE study

| Finding | Classification | Sections affected |
|---|---|---|
| ModelRouter = layer D, not expert-selection maturity | `CLARIFICATION` | §17, §24, §25, §84 (currently describe reuse without this layer distinction) |
| Scope/`root_operation_id` gap at `CapabilityRequest` | `IMPLEMENTATION PREREQUISITE`, sharpened | §39, §44 (both assume identity reaches further than it does) |
| Context Compiler no longer "undefined territory" | `CLARIFICATION` | §67 (needs the same pointer-style correction §69/§32/§77 already received) |
| Latency/cost/node-load signal absence | `IMPLEMENTATION PREREQUISITE` | §21, §29 (routing-cost analysis currently has no real signals to analyze) |
| Two-classifier module-selection duplication | `DEFERRED` | Not yet named in any study section — new finding |
| `own_model_tag` writer, long-form fallback mechanics | `UNRESOLVED` | — |
| Backend/node dispatch as a non-existent layer | `CLARIFICATION` | §5's own layer list (external brief) — E should read "not yet a layer," not "TBD" |

**Not addressed by this document, explicitly:** the CTX-DELETE-001/CTX-AUTH-001 freeze-blocking classification dispute (see Scope boundary, above). That is the next open item, and it is an architecture/priority decision, not a routing question.
