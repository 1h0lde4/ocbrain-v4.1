# K4.2 v1.0 Hardening — 12 Architectural Decisions

**Date:** Aug 14, 2026
**Scope:** Resolve 12 open architectural decisions that harden the K4.2 Cognitive Front-End before specification freeze. Incorporates findings from external spec-driven-development repositories (spec-kit, spec-kitty, OpenSpec).

> [!IMPORTANT]
> These decisions produce **specification-level artifacts only** — ADRs, spec amendments, and code changes to align existing implementations. No new subsystems, no new Kernel components, no new public entrypoints.

---

## External Repository Insights (Applied Throughout)

Three repos were studied: [github/spec-kit](https://github.com/github/spec-kit), [Priivacy-ai/spec-kitty](https://github.com/Priivacy-ai/spec-kitty), and [Fission-AI/openspec](https://github.com/Fission-AI/openspec). Key ideas adopted:

| Repo | Pattern | Applied Where |
|---|---|---|
| **spec-kit** | Bidirectional traceability (code ↔ task ↔ plan ↔ spec ↔ constitution) | Decision 10: static graph checks |
| **spec-kit** | `/speckit.converge` — drift detection against spec | Decision 10: architecture-drift verification gate |
| **spec-kitty** | Pre-flight readiness gate (`/spec-kitty.analyze`) — completeness, DAG validation, acceptance criteria | Decision 3: second-capability acceptance criterion |
| **spec-kitty** | Charter ↔ Doctrine ↔ Mission layering (immutable laws vs tactical procedures vs feature requests) | Decision 1: layered semantic authority |
| **spec-kitty** | Finite State Machine for task lane transitions with validation | Decision 5: recovery budget FSM |
| **OpenSpec** | RFC 2119 normative language (`MUST`/`SHALL`/`SHOULD`/`MAY`) for behavioral contracts | All decisions: normative language in ADRs |
| **OpenSpec** | Delta specs (`ADDED`/`MODIFIED`/`REMOVED`) for incremental evolution | Decision 12: rename/reconciliation framing |
| **OpenSpec** | `openspec validate --strict` — markdown AST + heading hierarchy + scenario block verification | Decision 10: integration-gate tooling |
| **OpenSpec** | Separation of Intent ("Why") / Contract ("What") / Mechanism ("How") | Decision 1: RawRequest / Goal / derived views |

---

## Decision 1 — Layered Semantic Authority

**Problem:** `RawRequest`, `Goal`, and downstream artifacts (e.g. `ExecutionPlan`, `WorkflowDefinition`) have informal relationships. Nothing enforces that `Goal` is the *authoritative cognitive interpretation* while `RawRequest` remains the immutable source and everything downstream is a consumer.

**Current state:**
- [`core/cognitive/intent.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/intent.py) defines `RawRequest` as a field on `Intent` — it's treated as input, but there's no architectural rule saying it's immutable.
- `Goal` is a `CognitiveArtifact` with `derived_from` pointing at `Intent`, but nothing prevents downstream stages from reaching back into `RawRequest` to reinterpret it.
- `ExecutionPlan` and `WorkflowDefinition` don't formally declare themselves as *consumers* — they can (and do) reference upstream fields directly.

**Decision:**

Define three tiers of semantic authority, formalized as a new ADR:

| Tier | Artifact | Semantics | Mutability |
|---|---|---|---|
| **Source** | `RawRequest` | The immutable, verbatim user input. No component MAY modify it after normalization. | Frozen at creation |
| **Authoritative Interpretation** | `Goal` | The canonical cognitive interpretation. All downstream stages MUST consume `Goal`, not `RawRequest`. Any reinterpretation creates a new `Goal` with `derived_from` provenance. | Immutable once `verified`; successor replaces, never edits |
| **Derived View** | `ExecutionPlan`, `WorkflowDefinition`, `WorkflowNode` | Consumer artifacts. MUST NOT reach past `Goal` to re-interpret `RawRequest` directly. MAY carry `goal_id` reference. | Mutable within their own lifecycle |

**Inspiration:** OpenSpec's `proposal.md` → `spec.md` → `design.md` → `tasks.md` cascade, where each layer consumes the one above and never reaches past it. Also mirrors spec-kitty's Charter (immutable) → Doctrine (tactical) → Mission (feature) hierarchy.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_01_LAYERED_SEMANTIC_AUTHORITY.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_01_LAYERED_SEMANTIC_AUTHORITY.md)
Full ADR documenting the three tiers, with RFC 2119 normative language.

#### [MODIFY] [`core/cognitive/intent.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/intent.py)
- Add `@dataclass(frozen=True)` to `RawRequest` (or equivalent immutability enforcement if it's currently a dict/string).
- Add docstring block establishing `RawRequest` as Tier-Source, `Goal` as Tier-Authoritative.

#### [MODIFY] [`core/cognitive/planner.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/planner.py)
- Audit `_extract_constraints()` and `plan()` to ensure they consume `Goal` fields only, never reaching back into `PlannerRequest.goal.intent.raw_request` to re-parse.
- Add docstring enforcement stating Planner is a Tier-Derived consumer.

---

## Decision 2 — General-Purpose Capability as Fallback

**Problem:** `discover_capabilities()` currently uses description-overlap scoring. When no specific capability matches well, should `LLM_COMPLETION` (general-purpose) be universally relevant (always scored high) or treated as a fallback?

**Current state:** [`core/cognitive/planner.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/planner.py) scores all capabilities equally by description overlap. `LLM_COMPLETION` wins by default because its description is broad enough to match most things, crowding out more specific capabilities.

**Decision:** General-purpose capability (`LLM_COMPLETION`) SHALL be treated as a **fallback**, not a universally relevant match:

1. `discover_capabilities()` SHALL first score domain-specific capabilities.
2. `LLM_COMPLETION` SHALL be included in results **only if** no domain-specific candidate exceeds a minimum relevance threshold, **or** as a trailing fallback entry in every candidate list (scored below any domain-specific match).
3. The threshold is a `PlannerHint`-level parameter, not a hard-coded constant — consistent with K4.2 §5's advisory-only hint design.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_02_GENERAL_PURPOSE_FALLBACK.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_02_GENERAL_PURPOSE_FALLBACK.md)

#### [MODIFY] [`core/cognitive/planner.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/planner.py)
- Modify `discover_capabilities()` to partition candidates into domain-specific vs. general-purpose, applying fallback scoring.
- Add `is_general_purpose` field or tag to `CapabilityDiscoveryRequest` results.

---

## Decision 3 — Second-Capability Discrimination as Packet Acceptance Criterion

**Problem:** Packet 11 (future) needs an acceptance criterion that proves capability discovery can distinguish between two or more competing candidates, not just fall back to a single general-purpose capability.

**Current state:** Packet 09's integration tests verify the happy path but never test `discover_capabilities()` with >1 registered capability of different types.

**Decision:** Any future packet that touches capability discovery (equivalent of Packet 11) MUST include a mandatory acceptance test:

> **GIVEN** two or more capabilities registered in `CapabilityRegistry`, each with distinct `capability_type` and non-overlapping descriptions,
> **WHEN** `discover_capabilities()` is called with a description matching one specific capability,
> **THEN** the matching capability MUST rank strictly above the non-matching capability, **AND** `LLM_COMPLETION` (if registered) MUST rank below the domain-specific match (per Decision 2).

**Inspiration:** spec-kitty's pre-flight readiness gate (`/spec-kitty.analyze`) — which validates completeness and acceptance criteria existence before allowing implementation.

### Proposed Changes

#### [MODIFY] [`docs/architecture/IMPLEMENTATION_TRACKER.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/IMPLEMENTATION_TRACKER.md)
- Add this acceptance criterion to the Required Validation Checklist for future capability-discovery packets.

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_03_CAPABILITY_DISCRIMINATION.md)

---

## Decision 4 — CapabilityMatch: Discovery Result vs. Telemetry

**Problem:** Is `CapabilityMatch` (the output of `discover_capabilities()`) the canonical discovery result that downstream stages consume, or is it observability/telemetry data?

**Current state:** `discover_capabilities()` returns a `List[CapabilityMatch]` which the Planner consumes directly to build `PlanStep.capability_type`. The same data is emitted as a `cognitive.capabilities_discovered` event. It is unclear which is authoritative.

**Decision:** `CapabilityMatch` SHALL be the **canonical discovery result** — a first-class cognitive artifact, not telemetry:

1. `CapabilityMatch` is what Planner consumes to select capabilities for `PlanStep`s.
2. The `cognitive.capabilities_discovered` event carries a *copy* of the match list for observability — the event is a derived view (Decision 1: Tier-Derived), not the source of truth.
3. If future C-MoE runtime overrides discovery, it produces a new `CapabilityMatch` list with `derived_from` provenance, not a side-channel bypass.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_04_CAPABILITY_MATCH_CANONICAL.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_04_CAPABILITY_MATCH_CANONICAL.md)

#### [MODIFY] [`core/cognitive/planner.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/planner.py)
- Add docstring to `CapabilityMatch` establishing it as canonical.
- Add `derived_from` field (or equivalent provenance) to `CapabilityMatch` if missing.

---

## Decision 5 — Unified Operation-Level Recovery Budget

**Problem:** Planner recovery (impasse → subgoaling) and Supervisor recovery (retry failed workers) each have their own implicit budgets but no unified ceiling. A request could exhaust Planner's retry budget, then exhaust Supervisor's, without any operation-level limit.

**Current state:**
- Planner: `ClarificationPolicy` has a bounded retry ceiling (K4.2 §14), but the ceiling is per-escalation, not per-operation.
- Supervisor: `max_supervisor_retries` (default 1), caller-supplied, per-invocation.
- No shared budget connects the two.

**Decision:** Define one `operation_recovery_budget` that covers both Planner and Supervisor recovery within a single user request:

```
OperationRecoveryBudget:
    max_total_recovery_attempts: int  # default 3 — covers ALL recovery across Planner + Supervisor
    planner_attempts_used:       int  # incremented by ClarificationPolicy escalation cycles
    supervisor_attempts_used:    int  # incremented by SupervisorWorker retry cycles
    exhausted:                   bool # True when planner_attempts + supervisor_attempts >= max_total
```

When `exhausted` becomes True, no further recovery is attempted — the operation is surfaced to the user as a terminal failure with full diagnostic context.

**Inspiration:** spec-kitty's FSM-based lane transitions with validation — treating recovery as a bounded state machine, not open-ended retry loops.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_05_RECOVERY_BUDGET.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_05_RECOVERY_BUDGET.md)

#### [MODIFY] [`core/cognitive/planner.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/planner.py)
- `ClarificationPolicy` consults `OperationRecoveryBudget` before escalating.

#### [MODIFY] [`core/workers/supervisor.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/workers/supervisor.py)
- `_attempt_retry()` checks `OperationRecoveryBudget.exhausted` before retrying.

---

## Decision 6 — K4.1-L vs K4.2 Learning Domain Contract

**Problem:** K4.1-L defines a generalized `LearningCandidate` contract (any component, open `domain` string). K4.2 defines `LearningRecord` + `CognitiveDecision` + `ValidationGate` with three specific `ContentDomain`s (SKILL, INTENT_ONTOLOGY, USER_MODEL). These two specifications overlap but have subtle differences in vocabulary, lifecycle states, and governance paths.

**Current state:**
- [`core/cognitive/learning.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/learning.py) implements K4.2's contract with `LearningTier`, `ContentDomain`, `LearningLifecycle`.
- K4.1-L's `LearningCandidate` with open `domain` string is not implemented anywhere — it's architecture-only.
- The K4.2 spec itself marks this `[RECONCILE-PENDING]` in §0 and §6.

**Decision:** Resolve in favor of K4.2's implemented contract as the v1.0 baseline, with K4.1-L's generalization as the designated evolution path:

1. **v1.0 (freeze now):** `ContentDomain` remains a closed set (SKILL, INTENT_ONTOLOGY, USER_MODEL). `ValidationGate` is the canonical promotion gate.
2. **v1.1 (future):** `ContentDomain` opens to an arbitrary `domain: str` per K4.1-L's `LearningCandidate.domain`. The `ValidationGate` signature already supports this (it's parameterized by `content_domain`).
3. **Remove `[RECONCILE-PENDING]`** from K4.2 §0 and §6 — the reconciliation is this decision.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_06_LEARNING_DOMAIN_CONTRACT.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_06_LEARNING_DOMAIN_CONTRACT.md)

#### [MODIFY] [`docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md)
- Remove `[RECONCILE-PENDING]` markers from §0 and §6.
- Add a reconciliation note citing this ADR.

---

## Decision 7 — Supervisor's Terminal Impasse Role

**Problem:** When Planner reaches a terminal impasse that cannot be resolved by subgoaling or clarification, Supervisor's role is ambiguous: is it a recovery authority (can generate a revised Goal/plan) or a diagnostic surface (surfaces the failure to the user)?

**Current state:** [`core/workers/supervisor.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/workers/supervisor.py) explicitly documents this ambiguity (lines 63–71): "Sending a revised plan back to Planner... is therefore intentionally deferred to a future architecture revision."

**Decision:** Supervisor SHALL be **diagnostic surfacing only** for terminal Planner impasse — not recovery authority:

1. On terminal Planner impasse (all recovery budget exhausted per Decision 5), Supervisor MUST NOT generate a revised Goal or plan.
2. Supervisor MUST emit `cognitive.supervision_impasse_terminal` with full diagnostic context (impasse type, recovery attempts exhausted, constraint set, capability gap).
3. The diagnostic event is the user-facing surface — a future HITL queue/UI consumes it.
4. Recovery authority (generating a revised Goal from impasse diagnostics) is explicitly reserved for a future Planner↔Supervisor feedback loop, gated by a future ADR.

This resolves the ambiguity cleanly: Supervisor surfaces, never recovers. Recovery authority requires its own future design pass.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_07_SUPERVISOR_TERMINAL_ROLE.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_07_SUPERVISOR_TERMINAL_ROLE.md)

#### [MODIFY] [`core/workers/supervisor.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/workers/supervisor.py)
- Add `cognitive.supervision_impasse_terminal` event emission.
- Update module docstring to formally declare "diagnostic surfacing only."

---

## Decision 8 — Trace/Correlation/Operation ID Semantics

**Problem:** The codebase uses `event_id`, `correlation_id` (mentioned in K4.2 spec), `workflow_id`, `operation_id` (not yet formalized), and `derived_from` chains — but there is no single document that precisely defines each, their lifetimes, and how they relate.

**Current state:**
- [`core/events/event_stream.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/events/event_stream.py): `StreamEvent` has `event_id` (per-event UUID) and `source`. No `correlation_id` or `trace_id` field.
- K4.2 §10/§2: references "originating event's correlation ID" but never defines a field for it.
- `WorkflowRuntime`: uses `workflow_id` for DAG-level grouping.
- `ExecutionContext`: has `metadata` dict but no structured trace ID.

**Decision:** Define three orthogonal identifiers with precise semantics:

| Identifier | Scope | Lifetime | Meaning |
|---|---|---|---|
| `trace_id` | Entire user request | Birth: `interpret_request()` call. Death: final response returned to user. | Groups everything that happened because of one user request. Equivalent to a distributed-tracing span root. |
| `correlation_id` | Causal chain within a trace | Birth: any stage that produces a new artifact. Death: artifact lifecycle ends. | Links causally related events — e.g., "this `Goal` was formed because of this `Intent`." Carried via `derived_from` chains. |
| `operation_id` | Single stage invocation | Birth: one `plan()` call or one `compile()` call. Death: that call returns. | Disambiguates multiple invocations of the same stage within one trace (e.g., replanning after recovery). |

`workflow_id` remains as-is — it's the `WorkflowRuntime`'s own execution-scope identifier, subordinate to `trace_id`.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_08_TRACE_SEMANTICS.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_08_TRACE_SEMANTICS.md)

#### [MODIFY] [`core/events/event_stream.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/events/event_stream.py)
- Add optional `trace_id` and `operation_id` fields to `StreamEvent`.

#### [MODIFY] [`core/cognitive/intent.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/intent.py)
- `interpret_request()` generates the `trace_id` at birth and threads it through all emitted events.

---

## Decision 9 — Causal Parent as Event-or-Failure Capable

**Problem:** Should `derived_from` references be limited to successful artifacts, or should they also link to failure events?

**Current state:** `derived_from: List[str]` on all `CognitiveArtifact`s links to `resource_id`s of predecessor artifacts. Failures produce events but no `resource_id` — so `derived_from` can't reference "this Goal was formed because the previous Goal failed validation."

**Decision:** `derived_from` SHALL support referencing both artifact `resource_id`s and `event_id`s:

1. An entry in `derived_from` MAY be either a `resource_id` (artifact reference) or an `event_id` (event reference, prefixed with `event:` to disambiguate).
2. This enables causal chains like: `Goal_v2.derived_from = ["goal:Goal_v1_resource_id", "event:goal_validation_failed_event_id"]`.
3. No structural change to the `derived_from` field type (`List[str]`) — only a naming convention and documentation.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_09_CAUSAL_PARENT_EVENTS.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_09_CAUSAL_PARENT_EVENTS.md)

#### [MODIFY] [`core/cognitive/intent.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/intent.py)
- Update `CognitiveArtifact` protocol docstring to document the `event:` prefix convention.
- Update `Intent` and `Goal` docstrings to show failure-causal examples.

---

## Decision 10 — Architecture-Drift Verification at Integration Gate

**Problem:** There is no automated check that code changes remain consistent with the frozen K4.2 architecture specification. Drift is caught manually during code review, which is error-prone (the K4.2 spec itself documents multiple cases of doc/reality lag).

**Current state:** Per `CURRENT_STATE.md` line 3, doc/reality lag has happened at least 4 times across K4.2's lifetime. No automated verification exists.

**Decision:** Make architecture-drift verification a mandatory part of the integration gate:

1. **Static boundary checks:** A script that verifies:
   - Cognitive Front-End modules (`core/cognitive/*.py`) never import from `core/workflow/runtime.py` or `core/capabilities/adapter_runtime.py` directly (boundary violation).
   - `core/workers/supervisor.py` never imports `compile()` or `plan()` (invariant 9 structural enforcement).
   - `RawRequest` is never accessed outside `core/cognitive/intent.py` (Decision 1 enforcement).

2. **Spec traceability check:** Every `.py` file in `core/cognitive/` and `core/workers/` MUST contain a docstring referencing its governing architecture section (already the case — this codifies the existing convention).

3. **Run as CI gate:** Added to the test suite as `tests/test_architecture_drift.py`.

**Inspiration:** spec-kit's `/speckit.converge` drift detection, OpenSpec's `openspec validate --strict`, and spec-kitty's pre-flight readiness gate.

### Proposed Changes

#### [NEW] [`tests/test_architecture_drift.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/tests/test_architecture_drift.py)
Static import-graph checks and docstring-reference checks.

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_10_DRIFT_VERIFICATION.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_10_DRIFT_VERIFICATION.md)

---

## Decision 11 — Multilingual Support: Language-Aware v1.0

**Problem:** OCBrain has no multilingual specification. Calling it "multilingual support" without semantic multilingual matching (cross-lingual embeddings, translation-aware retrieval) would be dishonest.

**Current state:** No multilingual code, schema, or spec exists anywhere in the repository (confirmed by research agent).

**Decision:** Reframe honestly:

**v1.0: Language-Aware/Preserving**
1. Input Normalization (`interpret_request()`) SHALL detect the input language and carry it as `RawRequest.detected_language: Optional[str]`.
2. All downstream stages MUST preserve the user's language in any user-facing output (no silent translation to English).
3. Retrieval (BM25 + semantic) operates in whatever language the content was stored in — no cross-lingual matching.
4. The `Intent Ontology` categories are language-neutral (structural, not lexical) — they work across languages because they match on intent structure, not surface words.

**v2.0 (future, explicit non-goal for v1.0): Semantic Multilingual Matching**
- Cross-lingual embeddings for retrieval.
- Translation-aware capability discovery.
- Multilingual ontology entries.

### Proposed Changes

#### [NEW] [`docs/architecture/decisions/ADR_K4_2_H_11_MULTILINGUAL_SCOPE.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/decisions/ADR_K4_2_H_11_MULTILINGUAL_SCOPE.md)

#### [MODIFY] [`core/cognitive/intent.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/intent.py)
- Add `detected_language: Optional[str] = None` to `RawRequest` or the normalization output.

---

## Decision 12 — Rename Packet 10/11 Series

**Problem:** The original K4.2 implementation campaign completed Packets 01–09. Using "Packet 10" and "Packet 11" for hardening/reconciliation work creates confusion — it looks like the original campaign has more unfinished work, when in fact it was declared complete.

**Current state:** [`docs/architecture/IMPLEMENTATION_TRACKER.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/IMPLEMENTATION_TRACKER.md) says "All 9 packets complete" with zero in-progress and zero waiting.

**Decision:** Rename the new packet series:

| Old Name | New Name | Purpose |
|---|---|---|
| Packet 10 | **K4.2-H1** (Hardening Packet 1) | Decisions 1–6: semantic authority, capability fallback, discrimination criterion, CapabilityMatch canonical status, recovery budget, learning domain reconciliation |
| Packet 11 | **K4.2-H2** (Hardening Packet 2) | Decisions 7–12: Supervisor role, trace semantics, causal parents, drift verification, multilingual scope, this rename itself |

The `H` prefix distinguishes hardening/reconciliation work from the original implementation campaign. The original Packets 01–09 history is preserved unchanged.

**Inspiration:** OpenSpec's delta specs (`ADDED`/`MODIFIED`/`REMOVED`) — this is a `MODIFIED` to the naming scheme, not a rewrite of history.

### Proposed Changes

#### [MODIFY] [`docs/architecture/IMPLEMENTATION_TRACKER.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/docs/architecture/IMPLEMENTATION_TRACKER.md)
- Add a new section: "K4.2 v1.0 Hardening Campaign" with K4.2-H1 and K4.2-H2 entries.
- Preserve original Packets 01–09 section unchanged.

#### [MODIFY] [`IMPLEMENTATION_ROADMAP.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/IMPLEMENTATION_ROADMAP.md)
- Add "K4.2 v1.0 Hardening Phase" section after the Cognitive Front-End Phase.

#### [MODIFY] [`CURRENT_STATE.md`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/CURRENT_STATE.md)
- Add rows for K4.2-H1 and K4.2-H2 milestones.

---

## Verification Plan

### Automated Tests

```bash
# Existing regression suite
python -m pytest tests/ -x --tb=short

# New drift verification
python -m pytest tests/test_architecture_drift.py -v

# New capability discrimination test
python -m pytest tests/core/cognitive/test_planner.py -k "test_capability_discrimination" -v
```

### Manual Verification
- Review all 12 new ADRs for constitutional compliance (each decision checked against Constitution Laws and Invariants).
- Verify `[RECONCILE-PENDING]` markers are removed from K4.2 spec.
- Verify `IMPLEMENTATION_TRACKER.md` correctly reflects the new K4.2-H naming.

---

## Open Questions

> [!IMPORTANT]
> **Q1 (Decision 5):** What should the default `max_total_recovery_attempts` be? I've proposed 3 as a reasonable ceiling (covering ~1 Planner retry + ~2 Supervisor retries, or vice versa). Would you prefer a different default, or should this be configurable via `config/settings.toml`?

> [!IMPORTANT]
> **Q2 (Decision 8):** Should `trace_id` be added to `StreamEvent` as a top-level field (changing the SQLite schema) or carried inside `payload` (no schema change but less queryable)? Top-level field is cleaner but requires a schema migration.

> [!IMPORTANT]
> **Q3 (Decision 10):** Should the drift verification script be a standalone `scripts/check_drift.py` (runnable independently) or integrated directly into the pytest suite as `tests/test_architecture_drift.py` (runs with every `pytest`)? I've proposed pytest integration for enforcement, but a standalone script is more accessible for ad-hoc checks. Both?

> [!IMPORTANT]
> **Q4 (Decision 11):** Is language detection at Input Normalization sufficient for v1.0, or do you also want `Goal.structured_form` to carry the detected language? The former is simpler; the latter enables language-aware planning.

> [!IMPORTANT]
> **Q5 (Decision 12):** Should K4.2-H1 and K4.2-H2 be a single combined packet, or kept as two separate packets with K4.2-H1 covering foundation decisions (1–6) and K4.2-H2 covering operational decisions (7–12)?
