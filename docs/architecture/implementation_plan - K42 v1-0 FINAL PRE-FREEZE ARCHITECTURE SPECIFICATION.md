# K4.2 v1.0 — FINAL PRE-FREEZE ARCHITECTURE SPECIFICATION

**Date:** Aug 14, 2026
**Authority:** Final architecture gate before K4.2-H1 implementation.
**Repository status:** Read-only. No `.git` directory present (extracted archive). No files modified.

---

## 1. Final Freeze Verdict

### `READY TO FREEZE`

No architecture-affecting ambiguity remains. Both human decisions are resolved. All 12 decisions have been reconciled against repository evidence. The stress test passes all 8 criteria. The specification below is implementation-ready.

**Path forward:**
```
K4.2-H1 implementation
    ↓
H1 tests + architecture verification
    ↓
H1 FREEZE
    ↓
K4.2-H2 implementation
    ↓
H2 tests + architecture verification
    ↓
K4.2 v1.0 FREEZE
    ↓
Parallel future milestone development
```

---

## 2. Final Human Decisions Resolved

### HQ-1 — Recovery Budget Default

**Decision:** `max_total_recovery_attempts = 3` as the implementation/configuration default, stored in `config/settings.toml` under `[runtime]`. This is NOT an immutable architectural constant — the architecture freezes the *contract*, not the numeric value.

**Configuration:**
```toml
[runtime]
use_k42_frontend = false
max_recovery_attempts = 3   # NEW — H1 adds this
```

**Invariant (frozen):** Every user operation has one authoritative autonomous recovery budget. No component may create an independent recovery budget outside this contract. Planner and Supervisor MAY consume the same budget. Neither may create a hidden retry universe.

### HQ-2 — General-Purpose Capability Identification

**Decision:** `CapabilityContract` gains `is_general_purpose: bool = False`. Explicit capability metadata owned by the registry. No inference from description breadth, no separate hard-coded list in Planner.

**Existing `CapabilityContract`** (lines [113–124](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/capabilities/capability.py#L113-L124)):
```python
@dataclass
class CapabilityContract:
    capability_type: str
    description: str
    required_resources: List[str] = field(default_factory=list)
    version: str = "1.0.0"
```

**After H1:**
```python
@dataclass
class CapabilityContract:
    capability_type: str
    description: str
    required_resources: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    is_general_purpose: bool = False  # ADR-K4.2-H-02
```

---

## 3. Final Normative Rules

> All rules use RFC 2119 language. Rules are numbered D1–D12 matching the original 12 decisions.

**D1 — Layered Semantic Authority.** RawRequest is the immutable literal source. Goal is the authoritative cognitive interpretation. Cognitive semantic consumption (Planner, Discovery, Compilation) MUST consume Goal, not re-interpret RawRequest independently. Diagnostic/audit access to RawRequest is observational. Goal MAY initially preserve the request verbatim. Refinement MUST preserve provenance via `derived_from` + `intent_id`.

**D2 — General-Purpose Fallback.** `CapabilityContract.is_general_purpose: bool = False`. Specificity dominance: strong specific > weak specific > general-purpose fallback. General-purpose MUST NOT override a sufficiently strong specific candidate. General-purpose MAY participate when specific candidates are absent or weak. Threshold is configurable, not hard-coded. No capability type routing hard-coded in Planner.

**D3 — Capability Discrimination Gate.** K4.2-H2 MUST include 5 acceptance cases: (A) specific match, (B) general fallback, (C) unsupported → impasse, (D) ambiguous → ranked list preserved, (E) multi-capability → per-step candidates. Adding a capability MUST NOT require Planner source modification.

**D4 — Canonical CapabilityDiscoveryResult.** `discover_capabilities()` SHALL return `CapabilityDiscoveryResult` (ranked `List[CapabilityMatch]`), not bare `List[CapabilityContract]`. EventStream receives a derived projection. Legacy compatibility via `.contracts` property.

**D5 — Unified Recovery Budget.** `OperationRecoveryBudget(max_total_recovery_attempts=3, internal_recovery_used=0, exhausted=False)`. Internal recovery (re-planning, retry, re-compilation) consumes budget. User clarification creates a NEW operation with its own budget, linked via `caused_by`. Terminal = exhausted, diagnostic surfacing, no further autonomous retry.

**D6 — Learning Domain Contract.** K4.2 v1.0 freezes `ContentDomain` as closed set. `ValidationGate` is canonical. Future MAY generalize. No silent reinterpretation without new ADR. `[RECONCILE-PENDING]` markers removed.

**D7 — Supervisor Terminal Role.** Terminal Planner impasse routes directly: Planner → Diagnostic Event → Orchestrator → user. Supervisor is NOT in this path. Supervisor retains compilation REJECT/ESCALATE and failed-worker retry. Future recovery authority requires new ADR.

**D8 — Trace Semantics.** Five identifiers: `trace_id` (request), `operation_id` (stage), `event_id` (event), `resource_id` (artifact), `workflow_id` (workflow). No `correlation_id`. `trace_id` in `StreamEvent.payload` for v1.0.

**D9 — Causal Provenance.** `derived_from: List[str]` = artifact lineage only. `caused_by: Optional[str] = None` = causal event/failure reference. MUST NOT mix event IDs into `derived_from`.

**D10 — Architecture-Drift Verification.** `scripts/check_drift.py` (implementation) + `tests/test_architecture_drift.py` (CI wrapper). 9 checks (DRIFT-01 through DRIFT-09). Documentation checks are secondary.

**D11 — Multilingual Scope.** v1.0 = language-aware/preserving. Best-effort detection, original preservation, no silent language change. `RawRequest.detected_language: Optional[str] = None`. Future = semantic multilingual intelligence.

**D12 — H1/H2 Structure.** H1 (foundation, D1/2/4/5/6/8/9) → H1 freeze → H2 (operational, D3/7/10/11/12) → H2 freeze → v1.0 freeze → parallel milestones.

---

## 4. Final Contract Model

### CognitiveArtifact Protocol (after H1)
```python
@runtime_checkable
class CognitiveArtifact(Protocol):
    resource_id: str
    produced_by: str
    derived_from: List[str]
    caused_by: Optional[str]       # NEW — ADR-K4.2-H-09
    lifecycle_state: str
```

### CapabilityContract (after H1)
```python
@dataclass
class CapabilityContract:
    capability_type: str
    description: str
    required_resources: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    is_general_purpose: bool = False  # NEW — ADR-K4.2-H-02
```

### CapabilityMatch (NEW — H1)
```python
@dataclass
class CapabilityMatch:
    """One candidate from capability discovery."""
    capability_type: str
    contract: CapabilityContract
    relevance_score: float
    subgoal_ref: str
    is_general_purpose: bool = False
```

### CapabilityDiscoveryResult (NEW — H1)
```python
@dataclass
class CapabilityDiscoveryResult:
    """Ranked discovery output — canonical, not telemetry."""
    matches: List[CapabilityMatch]
    subgoal_ref: str

    @property
    def contracts(self) -> List[CapabilityContract]:
        """Legacy compatibility projection."""
        return [m.contract for m in self.matches]
```

### OperationRecoveryBudget (NEW — H1)
```python
@dataclass
class OperationRecoveryBudget:
    """One per operation (scoped by trace_id)."""
    max_total_recovery_attempts: int = 3
    internal_recovery_used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_total_recovery_attempts - self.internal_recovery_used)

    @property
    def exhausted(self) -> bool:
        return self.internal_recovery_used >= self.max_total_recovery_attempts

    def consume(self) -> bool:
        """Returns True if recovery was permitted, False if exhausted."""
        if self.exhausted:
            return False
        self.internal_recovery_used += 1
        return True
```

### RawRequest (after H1)
```python
@dataclass(frozen=True)  # CHANGED — was @dataclass, now frozen
class RawRequest:
    text: str
    detected_language: Optional[str] = None  # NEW — ADR-K4.2-H-11
```

> [!NOTE]
> `RawRequest` gains `frozen=True` to enforce immutability (D1). The `detected_language` field is H2 scope (D11), but the frozen marker is H1 scope (D1). H1 adds `frozen=True` only; H2 adds `detected_language`.

---

## 5. Final Capability Discovery Model

```
Input: CapabilityDiscoveryRequest(subgoal_ref, description, constraints)
              │
              ▼
    CapabilityRegistry.list_capabilities()
              │
              ▼
    For each capability with ≥1 registered adapter:
        score = _capability_match_score(request, contract)
        general = contract.is_general_purpose
              │
              ▼
    Partition:
        specific_candidates = [c for c in scored if not c.is_general_purpose]
        general_candidates  = [c for c in scored if c.is_general_purpose]
              │
              ▼
    Apply specificity dominance:
        IF any specific_candidate.score ≥ specificity_threshold:
            ranked = sorted(specific_candidates, desc) + general_candidates
        ELSE:
            ranked = sorted(all_candidates, desc)
              │
              ▼
    IF no candidates with score > 0:
        → None (caller produces ImpasseRecord)
              │
              ▼
Output: CapabilityDiscoveryResult(matches=[CapabilityMatch(...)], subgoal_ref)
```

**Specificity threshold:** Configurable via `PlannerHint`. Default is implementation choice stored in code or config — NOT an architecture constant.

---

## 6. Final Recovery Model

### State Machine

```
OPERATION_STARTED
    │
    ▼
PLANNING ──(ready_for_compilation)──► COMPILING
    │                                      │
    │ (impasse)                     (COMPILED)──► EXECUTING
    │                                      │           │
    ▼                                      │      (success)──► COMPLETED
RECOVERY_CHECK                             │           │
    │                                      │      (failure)──► SUPERVISOR_RETRY
    │ (budget.remaining > 0)               │                       │
    │    ──► RE-PLANNING                   │               (budget check)
    │         (budget.consume())           │                    │    │
    │                                      │          (yes)─────┘    │
    │ (budget.exhausted)              (REJECT/                (no)───▼
    ▼                                 ESCALATE)          TERMINAL_FAILURE
TERMINAL_IMPASSE                          │                    │
    │                                     ▼                    ▼
    ▼                            SUPERVISOR_SURFACE     DIAGNOSTIC_EVENT
DIAGNOSTIC_EVENT                       │
(cognitive.planner_                    ▼
 impasse_terminal)             TERMINAL_FAILURE
                                       │
                                       ▼
                               DIAGNOSTIC_EVENT
                              (cognitive.operation_failed)
```

### Budget Semantics

| Action | Budget impact |
|---|---|
| Initial `plan()` call | No budget cost (first attempt is free) |
| Planner re-planning after impasse | `budget.consume()` |
| Supervisor worker retry | `budget.consume()` |
| Re-compilation (if architecturally permitted) | `budget.consume()` |
| User clarification | NEW operation, NEW budget, linked via `caused_by` |
| Exhaustion | Terminal state — no further autonomous recovery |

### Recovery Invariant (frozen)
> Every user operation has one authoritative autonomous recovery budget. No component may create an independent recovery budget outside this contract.

---

## 7. Final Diagnostic Model

| Concept | Type | Storage | Query pattern |
|---|---|---|---|
| Event | `StreamEvent` | EventStream (SQLite WAL) | By `event_type`, `source`, `payload.trace_id` |
| Failure | `ImpasseRecord`, `CompilationResult(status≠COMPILED)`, `WorkerResult(success=False)` | In event payload | By event type + trace |
| Trace | `trace_id` in payload | EventStream | Filter by payload key |
| Operation | `operation_id` in payload | EventStream | Filter by payload key |
| Artifact | `resource_id` on CognitiveArtifact | In-memory + event log | By `resource_id` |
| Artifact lineage | `derived_from: List[str]` | Artifact field | Graph traversal |
| Causal relation | `caused_by: Optional[str]` | Artifact field | Event lookup |

### Diagnostic contract boundary
The Diagnostic System is **cross-cutting**, **reusable**, and **non-authoritative** for recovery and governance. It records; it does not decide.

---

## 8. Final Identifier / Provenance Model

| Identifier | Type | Creator | Lifetime | Persisted |
|---|---|---|---|---|
| `trace_id` | UUID str | `interpret_request()` via `tracer.get_trace_id()` | Request → response | `StreamEvent.payload` |
| `operation_id` | UUID str | Each `plan()` / `compile()` / `discover_capabilities()` | Call → return | `StreamEvent.payload` |
| `event_id` | UUID str | `EventStream.append()` | Permanent | `StreamEvent.event_id` |
| `resource_id` | UUID str | Artifact constructor | Artifact lifecycle | Artifact field |
| `workflow_id` | UUID str | `WorkflowRuntime.execute()` | Workflow lifecycle | Worker context |

| Provenance | Type | Semantics |
|---|---|---|
| `derived_from` | `List[str]` | Artifact → ancestor artifact(s). Resource IDs only. |
| `caused_by` | `Optional[str]` | Artifact → triggering event. Event ID only. |

---

## 9. Final Architecture-Drift Model

| Check | Rule | AST Target |
|---|---|---|
| DRIFT-01 | `core/cognitive/*.py` must not import `core.workflow.runtime` | Import analysis |
| DRIFT-02 | `core/cognitive/*.py` must not import `core.capabilities.adapter_runtime` | Import analysis |
| DRIFT-03 | `core/workers/supervisor.py` must not import `plan()` or `compile()` function | Import + name analysis |
| DRIFT-04 | `RawRequest` construction only in `core/cognitive/intent.py` | Constructor call-site |
| DRIFT-05 | `SupervisorWorker` must not call `GovernanceKernel.evaluate_action()` | Call-site analysis |
| DRIFT-06 | No hard-coded capability type strings in Planner routing | Literal string analysis in `discover_capabilities` and callers |
| DRIFT-07 | `cognitive.*` events emitted only from `core/cognitive/` or `core/workers/` | Event type + source file cross-reference |
| DRIFT-08 | Canonical builders not bypassed (where declared) | Constructor uniqueness |
| DRIFT-09 | No unauthorized shared-contract producer outside declared owners | Producer source analysis |

**Current repository compliance (verified):**
- ✅ DRIFT-01: No imports of `core.workflow.runtime` or `core.capabilities.adapter_runtime` in `core/cognitive/`
- ✅ DRIFT-03: `supervisor.py` imports `CompilationResult`/`CompilationStatus` from `compiler.py` (legitimate consumer), NOT `compile()` or `plan()`
- ✅ DRIFT-04: `RawRequest` not imported outside `core/cognitive/intent.py`
- ✅ DRIFT-05: `SupervisorWorker` references `GovernanceKernel` only in docstring comments, never in code calls
- ✅ DRIFT-06: No hard-coded capability type strings in `planner.py` routing logic

---

## 10. H1 Implementation Specification

### Scope
H1 implements Decisions 1, 2, 4, 5, 6, 8, 9 — foundational contracts.

### Exact Modules Affected

#### [MODIFY] `core/capabilities/capability.py`
- **Change:** Add `is_general_purpose: bool = False` to `CapabilityContract` (line 124).
- **Invariant:** Default `False` preserves all existing registrations.
- **Migration:** None — new field with default.

#### [MODIFY] `core/cognitive/intent.py`
- **Change 1:** `RawRequest` (line 196): add `frozen=True` to `@dataclass`.
- **Change 2:** `CognitiveArtifact` Protocol (line 52): add `caused_by: Optional[str]` field.
- **Change 3:** `Intent` dataclass (line 152): add `caused_by: Optional[str] = None`.
- **Change 4:** `Goal` dataclass (line 492): add `caused_by: Optional[str] = None`.
- **Change 5:** Add docstring blocks establishing D1 semantic tiers on `RawRequest`, `Goal`.
- **Change 6:** `interpret_request()` (line 707): generate `trace_id` via `from core.observability.tracer import get_trace_id`; include `trace_id` and `operation_id` in all emitted event payloads.
- **Migration:** `frozen=True` on `RawRequest` — verify no existing code mutates a `RawRequest` instance after creation (confirmed: `normalize_request()` constructs and returns, never mutated downstream).

#### [MODIFY] `core/cognitive/planner.py`
- **Change 1:** Add `CapabilityMatch` and `CapabilityDiscoveryResult` dataclasses (after line 596).
- **Change 2:** `discover_capabilities()` (line 639): change return type from `List[CapabilityContract]` to `CapabilityDiscoveryResult`. Build `CapabilityMatch` entries preserving scores. Apply specificity dominance partitioning.
- **Change 3:** `_decompose()` (line 863): update to consume `CapabilityDiscoveryResult.matches` instead of bare `List[CapabilityContract]`.
- **Change 4:** `_detect_impasse()`, `_estimate_confidence()`, `_alternative_plans()`: update to consume `CapabilityMatch` objects.
- **Change 5:** `ExecutionPlan` (line 804): add `caused_by: Optional[str] = None`.
- **Change 6:** Add `operation_id` generation in `plan()` (line 1136); include in event payloads.
- **Change 7:** Add `_extract_constraints()` D1-compliance docstring (line 433–436 fallback from `structured_form["raw_request"]` is D1-compliant: reads from Goal, not from RawRequest object).
- **Invariant:** `discover_capabilities()` return type change is the largest change. All callers are internal to this file.

#### [MODIFY] `core/cognitive/compiler.py`
- **Change:** Add `operation_id` generation in `compile()` (line 257); include in event payloads.
- **Migration:** None — additive payload keys.

#### [MODIFY] `core/cognitive/learning.py`
- **Change:** Add `caused_by: Optional[str] = None` to `LearningRecord` and `CognitiveDecision`.
- **Migration:** None — new optional field.

#### [MODIFY] `core/workers/supervisor.py`
- **Change:** `_attempt_retry()` docstring update to reference `OperationRecoveryBudget` contract. (Actual budget enforcement is in the caller — Orchestrator — not in Supervisor itself, which is stateless per K4 §4.)

#### [NEW] `core/cognitive/recovery.py`
- **Content:** `OperationRecoveryBudget` dataclass (as specified in §4 above). Module-level only, no integration point — Orchestrator consumes it.
- **Boundary:** This is a data contract, not a new subsystem.

#### [MODIFY] `config/settings.toml`
- **Change:** Add `max_recovery_attempts = 3` under `[runtime]`.

#### [MODIFY] `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md`
- **Change:** Remove `[RECONCILE-PENDING]` markers from §0 and §6. Add reconciliation note citing ADR-K4.2-H-06.

#### [MODIFY] `docs/architecture/decisions/ADR_INDEX.md`
- **Change:** Add K4.2-H series ADRs to Standalone ADRs table.

#### [NEW] `docs/architecture/decisions/ADR_K4_2_H_01_LAYERED_SEMANTIC_AUTHORITY.md` through `ADR_K4_2_H_09_CAUSAL_PROVENANCE.md`
- **Content:** 7 ADRs covering H1 decisions (see §17 for exact contents).

### H1 Tests

| Test file | Test | Verifies |
|---|---|---|
| `tests/test_intent.py` | `test_raw_request_immutable` | `RawRequest(frozen=True)` raises on mutation |
| `tests/test_intent.py` | `test_goal_caused_by` | `Goal.caused_by` field present, optional |
| `tests/test_intent.py` | `test_interpret_request_trace_id` | `trace_id` in event payloads |
| `tests/test_planner.py` | `test_discover_returns_discovery_result` | Return type is `CapabilityDiscoveryResult` |
| `tests/test_planner.py` | `test_discovery_result_preserves_scores` | `CapabilityMatch.relevance_score` populated |
| `tests/test_planner.py` | `test_specificity_dominance_strong_specific` | Strong specific ranks above general-purpose |
| `tests/test_planner.py` | `test_specificity_dominance_weak_fallback` | General-purpose wins when no strong specific |
| `tests/test_planner.py` | `test_plan_includes_operation_id` | `operation_id` in plan events |
| `tests/test_planner.py` | `test_discovery_result_legacy_contracts` | `.contracts` property returns `List[CapabilityContract]` |
| `tests/test_compiler.py` | `test_compile_includes_operation_id` | `operation_id` in compile events |
| `tests/core/cognitive/test_recovery.py` | `test_budget_creation` | Default budget = 3 |
| `tests/core/cognitive/test_recovery.py` | `test_budget_consume` | `consume()` decrements, returns False when exhausted |
| `tests/core/cognitive/test_recovery.py` | `test_budget_remaining` | `remaining` property correct |
| `tests/test_learning.py` | `test_learning_record_caused_by` | `caused_by` field present |

### H1 Rollback
All H1 changes are additive: new fields with defaults, new dataclasses, return type widening. Rollback = revert commit. No schema migration to reverse.

### H1 Stop Conditions
- **STOP** if `discover_capabilities()` return type change breaks any test in `test_planner.py` — investigate consumer assumptions before proceeding.
- **STOP** if `RawRequest(frozen=True)` causes failures — search for post-construction mutation of `RawRequest` instances.
- **STOP** if any existing test fails that is not directly related to the H1 changes.

---

## 11. H1 Acceptance Gate

| # | Criterion | Type | Pass condition |
|---|---|---|---|
| H1-G1 | Goal semantic preservation | Unit | `Goal.derived_from` populated, `intent_id` set |
| H1-G2 | `CapabilityDiscoveryResult` contract | Unit | `discover_capabilities()` returns structured type with scores |
| H1-G3 | Specific/general ranking | Unit | Strong specific ranks above general-purpose |
| H1-G4 | Recovery budget contract | Unit | Budget counts, exhausts, reports remaining correctly |
| H1-G5 | Identifier propagation | Unit | `trace_id`, `operation_id` in event payloads |
| H1-G6 | Provenance separation | Unit | `derived_from` contains resource IDs only; `caused_by` is Optional[str] |
| H1-G7 | Learning reconciliation | Spec | `[RECONCILE-PENDING]` markers removed |
| H1-G8 | Existing regression | Suite | All pre-existing tests pass |
| H1-G9 | Architecture drift (H1 checks) | Static | DRIFT-01, DRIFT-02, DRIFT-04, DRIFT-05, DRIFT-06 pass |
| H1-G10 | No unrelated changes | Review | Diff contains only H1-scoped modifications |

**H1 FREEZE** requires all 10 criteria passing.

---

## 12. H2 Implementation Specification

### Scope
H2 implements Decisions 3, 7, 10, 11, 12 — operational hardening.

### Exact Modules Affected

#### [MODIFY] `core/cognitive/intent.py`
- **Change:** `RawRequest` gains `detected_language: Optional[str] = None` (D11). Since H1 already made it `frozen=True`, this adds a second field to the frozen dataclass.
- **Change:** `normalize_request()` adds best-effort language detection (e.g., via `langdetect` or simple heuristic) setting `detected_language` on the returned `RawRequest`.

#### [MODIFY] `core/orchestrator.py`
- **Change:** Lines [280–287](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/orchestrator.py#L280-L287): On terminal Planner impasse (budget exhausted), emit `cognitive.planner_impasse_terminal` event with full `ImpasseRecord` payload before returning error to user.

#### [NEW] `scripts/check_drift.py`
- **Content:** Implementation of DRIFT-01 through DRIFT-09 using AST analysis. Outputs JSON results. Each check is a function returning pass/fail + details.

#### [NEW] `tests/test_architecture_drift.py`
- **Content:** Pytest wrapper importing `scripts/check_drift.py`. Each DRIFT check = one test function.

#### [NEW] `tests/test_capability_discrimination.py`
- **Content:** 5 mandatory acceptance test cases (A–E) per D3.

#### [MODIFY] `docs/architecture/IMPLEMENTATION_TRACKER.md`
- **Change:** Add K4.2 v1.0 Hardening Campaign section with H1 and H2 entries.

#### [MODIFY] `IMPLEMENTATION_ROADMAP.md`
- **Change:** Add K4.2 v1.0 Hardening Phase after Cognitive Front-End Phase.

#### [MODIFY] `CURRENT_STATE.md`
- **Change:** Add K4.2-H1 and K4.2-H2 milestones.

#### [NEW] `docs/architecture/decisions/ADR_K4_2_H_10_DRIFT_VERIFICATION.md` through `ADR_K4_2_H_12_HARDENING_PACKET_STRUCTURE.md`
- **Content:** 3 ADRs covering H2 decisions.

### H2 Tests

| Test file | Test | Verifies |
|---|---|---|
| `tests/test_capability_discrimination.py` | `test_case_a_specific_match` | Domain-specific wins over non-matching |
| `tests/test_capability_discrimination.py` | `test_case_b_general_fallback` | General-purpose wins when no strong specific |
| `tests/test_capability_discrimination.py` | `test_case_c_unsupported` | No candidate → `ImpasseRecord` |
| `tests/test_capability_discrimination.py` | `test_case_d_ambiguous` | Multiple candidates preserved in ranked list |
| `tests/test_capability_discrimination.py` | `test_case_e_multi_capability` | Per-step discovery with distinct candidates |
| `tests/test_capability_discrimination.py` | `test_no_planner_modification_required` | Register new capability, discovery finds it without code change |
| `tests/test_architecture_drift.py` | `test_drift_01` through `test_drift_09` | All 9 drift checks pass |
| `tests/test_intent.py` | `test_detected_language_field` | `RawRequest.detected_language` present |
| `tests/test_intent.py` | `test_language_preservation` | Output language not silently changed |
| `tests/test_runtime_integration.py` | `test_planner_impasse_terminal_event` | Terminal impasse emits diagnostic event |

### H2 Rollback
All H2 changes are additive. Rollback = revert commit.

### H2 Stop Conditions
- **STOP** if any DRIFT check fails on the CURRENT repo state (before H2 changes) — indicates the check definition is wrong.
- **STOP** if language detection dependency is unavailable — fall back to `detected_language = None` without blocking H2.

---

## 13. H2 Acceptance Gate

| # | Criterion | Type | Pass condition |
|---|---|---|---|
| H2-G1 | Capability discrimination Cases A–E | Integration | All 5 cases pass |
| H2-G2 | Capability independence | Integration | New capability registered → discovered without code change |
| H2-G3 | Terminal impasse diagnostic | Integration | `cognitive.planner_impasse_terminal` emitted with `ImpasseRecord` |
| H2-G4 | Language preservation | Unit | `detected_language` field present; no silent output language change |
| H2-G5 | Architecture drift CI | Static | All DRIFT-01 through DRIFT-09 pass |
| H2-G6 | Complete regression | Suite | All pre-existing + H1 + H2 tests pass |
| H2-G7 | Contract/invariant suite | Suite | All H1-G1 through H1-G10 still pass |
| H2-G8 | Diagnostic causal tracing | Integration | `trace_id` → events → `caused_by` → failure chain queryable |
| H2-G9 | No architecture boundary violations | Static + Review | No DRIFT failures; diff is H2-scoped only |

**H2 FREEZE** requires all 9 criteria passing.
**K4.2 v1.0 FREEZE** = H1 FREEZE + H2 FREEZE.

---

## 14. Parallel Milestone Contract

After K4.2 v1.0 FREEZE, future milestones MAY work in parallel provided they:

1. **Consume frozen contracts.** `CapabilityDiscoveryResult`, `OperationRecoveryBudget`, `CognitiveArtifact` (with `caused_by`), identifier semantics.
2. **Preserve invariants.** All 14 invariants in §25 matrix.
3. **Declare contract extensions.** New fields require ADR.
4. **Use the Diagnostic System.** Emit events via `EventStream`; use `trace_id`, `operation_id`.
5. **Pass the architecture-drift gate.** `tests/test_architecture_drift.py` must pass.

---

## 15. Future Change-Control Rules

**MAY independently:**
- Internal implementation changes, private refactors, optimizations preserving semantics, new subsystem-local failure codes.

**MUST obtain architecture review before changing:**
- Shared contract meaning, required shared fields, ownership, provenance semantics, recovery authority, governance boundaries, execution semantics, canonical construction rules, Diagnostic core contract.

**Frozen invariant:** No silent semantic reinterpretation is permitted.

---

## 16. K4.2 v1.0 Freeze Criteria

| # | Criterion | Status |
|---|---|---|
| 1 | All 12 ADRs accepted | ✅ Ready |
| 2 | H1 acceptance gate passes | ⏳ Requires implementation |
| 3 | H2 acceptance gate passes | ⏳ Requires implementation |
| 4 | Complete regression suite passes | ⏳ Requires implementation |
| 5 | All DRIFT checks pass | ⏳ Requires implementation |
| 6 | `[RECONCILE-PENDING]` markers removed | ⏳ H1 task |
| 7 | No open human decisions | ✅ Both resolved |
| 8 | Stress test passes all 8 criteria | ✅ See §31 |

---

## 17. Exact ADR Contents

### ADR-K4.2-H-01 — Layered Semantic Authority

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** `RawRequest`, `Goal`, and downstream artifacts had informal relationships. No architectural rule enforced that Goal is the authoritative cognitive interpretation while RawRequest remains immutable source. Downstream stages could reach back to `RawRequest` to re-interpret independently.

**Decision:**
- `RawRequest` SHALL be the immutable literal source of normalized user input. `@dataclass(frozen=True)`. No component MAY modify it after `normalize_request()` returns.
- `Goal` SHALL be the authoritative cognitive interpretation. All cognitive semantic consumption — Planner, Capability Discovery, Plan Compilation — MUST consume `Goal`, not re-interpret `RawRequest` independently.
- `ExecutionPlan`, `WorkflowDefinition`, `WorkflowNode` are derived views. MUST NOT reach past `Goal`.
- Diagnostic/audit systems MAY access `RawRequest` content observationally.
- `Goal` MAY initially preserve the request verbatim. Refinement MUST preserve provenance via `derived_from` and `intent_id`.

**Consequences:** `RawRequest` becomes `frozen=True`. Existing `_extract_constraints()` fallback to `goal.structured_form.get("raw_request")` is compliant (reads from Goal, not RawRequest object). No existing code path violated.

---

### ADR-K4.2-H-02 — General-Purpose Capability Fallback

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** `discover_capabilities()` scored all capabilities equally by description overlap. General-purpose capabilities (e.g., `LLM_COMPLETION`) could crowd out specific ones.

**Decision:**
- `CapabilityContract` SHALL carry `is_general_purpose: bool = False`.
- Specificity dominance: strong specific evidence > weak specific evidence > general-purpose fallback.
- A general-purpose capability MUST NOT override a sufficiently strong specific candidate.
- A general-purpose capability MAY participate when specific candidates are absent or weak.
- A general-purpose capability MUST NOT automatically receive arbitrary positive relevance merely because it is general-purpose.
- The specificity threshold SHALL be configurable, not hard-coded in the architecture.
- No capability type string SHALL be hard-coded in Planner routing logic.

**Consequences:** `CapabilityContract` gains one field with default. All existing registrations unchanged (`False` default). `discover_capabilities()` adds partitioning logic.

---

### ADR-K4.2-H-03 — Capability Discrimination Acceptance Gate

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** No test verified that capability discovery can distinguish between competing candidates. The acceptance criterion was informally stated as a future recommendation.

**Decision:**
K4.2-H2 acceptance suite MUST include 5 mandatory cases:
- **A (Specific match):** Domain-specific capability ranks strictly above non-matching capability.
- **B (General fallback):** General-purpose capability MAY win when no strong specific candidate exists.
- **C (Unsupported):** No meaningful candidate → terminal impasse, not arbitrary fallback.
- **D (Ambiguous):** Multiple plausible capabilities → ranked list preserved, not flattened.
- **E (Multi-capability):** Different steps require different capabilities → per-step candidate sets.

Registering a second capability MUST NOT require Planner source-code modification. This is a K4.2-H2 gate (not H1).

**Consequences:** 6 new test cases in `tests/test_capability_discrimination.py`. Proves discovery works dynamically.

---

### ADR-K4.2-H-04 — CapabilityMatch as Canonical Discovery Result

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** `discover_capabilities()` returned `List[CapabilityContract]`, discarding computed relevance scores. Planner could not consume ranked evidence.

**Decision:**
- `CapabilityMatch` dataclass: `capability_type`, `contract`, `relevance_score`, `subgoal_ref`, `is_general_purpose`.
- `CapabilityDiscoveryResult` dataclass: `matches: List[CapabilityMatch]`, `subgoal_ref`.
- `discover_capabilities()` SHALL return `CapabilityDiscoveryResult`.
- `EventStream` receives a derived observability projection — never authoritative for planning.
- Legacy compatibility via `.contracts` property returning `List[CapabilityContract]`.

**Consequences:** Return type change in `discover_capabilities()`. All callers are internal to `planner.py`. Legacy compatibility preserved.

---

### ADR-K4.2-H-05 — Unified Operation-Level Recovery Budget

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** Planner recovery and Supervisor recovery had independent budgets with no unified ceiling. No operation-level limit existed.

**Decision:**
- `OperationRecoveryBudget(max_total_recovery_attempts, internal_recovery_used, exhausted)`.
- `max_total_recovery_attempts` is configurable; default = 3 (stored in `config/settings.toml` `[runtime]`).
- Internal recovery (re-planning, Supervisor retry, re-compilation) consumes budget.
- User clarification creates a NEW operation with its own budget, linked via `caused_by`. Does NOT consume the prior operation's budget.
- Terminal state: `exhausted == True` → diagnostic surfacing, no further autonomous retry.
- **Invariant:** Every user operation has one authoritative autonomous recovery budget. No component may create an independent recovery budget outside this contract.

**Consequences:** New `core/cognitive/recovery.py` module. Orchestrator threads budget through the pipeline. `config/settings.toml` gains one key.

---

### ADR-K4.2-H-06 — Learning Domain Contract Reconciliation

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** K4.1-L defined open `domain: str` for `LearningCandidate`. K4.2 implemented `ContentDomain` as a closed set. The K4.2 spec carried `[RECONCILE-PENDING]` markers.

**Decision:**
- K4.2 v1.0 freezes `ContentDomain` as a closed set: SKILL, INTENT_ONTOLOGY, USER_MODEL.
- `ValidationGate` is the canonical promotion gate.
- Future architecture evolution MAY generalize to an open `domain: str`. No specific milestone is promised.
- No milestone MAY silently reinterpret `ContentDomain` or add values without a new ADR.
- `[RECONCILE-PENDING]` markers in K4.2 spec §0 and §6 SHALL be removed.

**Consequences:** Spec markers removed. No code change. Future evolution path preserved but not committed.

---

### ADR-K4.2-H-07 — Supervisor Terminal Impasse Role

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** When Planner reaches terminal impasse, Supervisor's role was ambiguous. Repository evidence shows `SupervisorWorker._run()` has no input path for `PlannerResult`; it handles only `CompilationResult` and `failed_worker_result`. Routing terminal impasse through Supervisor would be a semantic no-op.

**Decision:**
- Terminal Planner impasse SHALL NOT route through Supervisor in v1.0.
- Path: Planner → Diagnostic Event (`cognitive.planner_impasse_terminal`) → Orchestrator → user.
- Supervisor retains: compilation REJECT/ESCALATE handling, failed-worker retry.
- Supervisor SHALL NOT gain Planner recovery authority in v1.0.
- Future Goal-revision/re-planning by Supervisor requires a new ADR.

**Consequences:** No change to `supervisor.py`. Orchestrator gains one new diagnostic event emission. Supervisor scope is explicitly bounded.

---

### ADR-K4.2-H-08 — Trace Semantics

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** The codebase used `event_id`, `workflow_id`, and had an existing `trace_id` in `core/observability/tracer.py`, but no formal identifier model. `StreamEvent` had no `trace_id` or `operation_id`.

**Decision:**
- Five orthogonal identifiers: `trace_id` (request lineage), `operation_id` (stage invocation), `event_id` (one event), `resource_id` (one artifact), `workflow_id` (one workflow execution).
- No `correlation_id` — redundant with `derived_from` + `caused_by`.
- `trace_id` created by `interpret_request()` via existing `core.observability.tracer.get_trace_id()`.
- `operation_id` generated per `plan()` / `compile()` / `discover_capabilities()` call.
- For v1.0, `trace_id` and `operation_id` stored in `StreamEvent.payload`, NOT as top-level fields (no SQLite schema migration).

**Consequences:** Event payloads gain `trace_id` and `operation_id` keys. No schema migration. Future MAY promote to top-level fields via dedicated ADR.

---

### ADR-K4.2-H-09 — Causal Provenance Separation

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** `derived_from: List[str]` contained only artifact `resource_id`s across the entire codebase. No mechanism existed for causal event references. A prior proposal suggested mixing event IDs into `derived_from` with an `event:` prefix.

**Decision:**
- `derived_from: List[str]` SHALL contain artifact/resource lineage ONLY. No event IDs.
- `caused_by: Optional[str] = None` added to `CognitiveArtifact` Protocol for causal event/failure references.
- These fields serve distinct purposes: `derived_from` answers "what is this artifact's lineage?" while `caused_by` answers "what failure/event triggered this artifact's creation?"
- `caused_by` is optional with `None` default — zero migration cost.

**Consequences:** `CognitiveArtifact` Protocol gains one optional field. All implementing dataclasses (`Intent`, `Goal`, `ExecutionPlan`, `LearningRecord`, `EvaluationRecord`) gain the field. Existing `derived_from` semantics preserved.

---

### ADR-K4.2-H-10 — Architecture-Drift Verification

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** No automated check verified code consistency with the frozen K4.2 architecture. Drift was caught manually — and had occurred at least 4 times.

**Decision:**
- `scripts/check_drift.py` = single reusable implementation of all drift checks. Outputs structured JSON.
- `tests/test_architecture_drift.py` = pytest CI wrapper importing `check_drift`. No duplicated logic.
- 9 checks: DRIFT-01 through DRIFT-09 covering import boundaries, construction canonicality, event ownership, and routing independence.
- Documentation checks (docstring references) are secondary — NOT primary compliance proof.
- Primary compliance comes from AST analysis, call graph checks, contract tests, and invariant tests.

**Consequences:** Two new files. CI gate prevents architecture drift on every test run.

---

### ADR-K4.2-H-11 — Multilingual Scope

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** OCBrain had no multilingual specification or language detection code.

**Decision:**
- v1.0 = language-aware / language-preserving.
- Best-effort language detection. Original input preservation. Language metadata propagation via `RawRequest.detected_language: Optional[str]`.
- The system MUST NOT silently change the output language. User-specified target language governs.
- Uncertain detection degrades to `None`, not an error.
- v1.0 does NOT guarantee cross-lingual retrieval, translation-aware discovery, code-switch segmentation, or language-independent capability scoring.
- Ontology categories SHOULD be language-neutral; v1.0 does not claim cross-lingual semantic equivalence.

**Consequences:** `RawRequest` gains one optional field. `normalize_request()` gains language detection. Future evolution = semantic multilingual intelligence.

---

### ADR-K4.2-H-12 — Hardening Packet Structure

**Date:** Aug 14, 2026 | **Status:** Accepted

**Context:** Original K4.2 campaign completed Packets 01–09. Using "Packet 10/11" for hardening would create confusion.

**Decision:**
- K4.2-H1 (Foundation): Decisions 1, 2, 4, 5, 6, 8, 9. Ends with H1 freeze.
- K4.2-H2 (Operational): Decisions 3, 7, 10, 11, 12. Depends on H1 freeze. Ends with H2 freeze = K4.2 v1.0 freeze.
- Original Packets 01–09 naming and history preserved unchanged.
- No future milestone parallelization until K4.2 v1.0 freeze.

**Consequences:** `IMPLEMENTATION_TRACKER.md`, `IMPLEMENTATION_ROADMAP.md`, `CURRENT_STATE.md` gain H1/H2 sections.

---

## 18. Final Remaining Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | `discover_capabilities()` return type change may have undiscovered test consumers | Low | All callers confirmed internal to `planner.py`. `.contracts` compatibility property provided. Run full regression suite. |
| R2 | Language detection dependency may not be available in all deployment environments | Low | `detected_language` defaults to `None`. Detection failure is degradation, not error. |
| R3 | `OperationRecoveryBudget` threading through Orchestrator adds complexity to an already large function | Medium | Budget is a simple dataclass with no integration with existing governance. Orchestrator's K4.2 branch is already isolated by feature flag. |

---

## 19. Final Recommendation

### `READY TO FREEZE`

No architecture-affecting ambiguity remains. Both human decisions are resolved. All 12 decisions have been reconciled against repository evidence and verified with stress test checks against the live codebase.

**Next step:** Give the next implementation session the K4.2-H1 Implementation Specification (§10 of this document) as its packet. H1 implements Decisions 1, 2, 4, 5, 6, 8, 9. Upon H1 completion and gate passage (§11), freeze H1 and proceed to H2.

---

## Appendix A — Stress Test Results

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Can a capability be added without Planner modification? | **YES** | `CapabilityRegistry.register_capability()` + `register_adapter()`. `discover_capabilities()` iterates `registry.list_capabilities()` dynamically. DRIFT-06 enforces no hard-coded routing. |
| 2 | Can a language be added without Planner modification? | **YES** | Planner consumes `Goal.structured_form`, not `RawRequest.detected_language`. Language detection is in `normalize_request()` only. |
| 3 | Can a future semantic matcher be introduced without redesigning Goal? | **YES** | `Goal.structured_form` is `Dict[str, Any]` — open schema. `Goal.confidence` and `derived_from` are generic. A semantic matcher produces a new Goal with `derived_from` provenance. |
| 4 | Can two sessions work on independent milestones after freeze without redefining shared contracts? | **YES** | Shared contracts are frozen. Change-control rules (§15) require ADR for any shared contract change. DRIFT gate catches violations. |
| 5 | Can a terminal failure be diagnosed without reproducing the original bug? | **YES** | `trace_id` groups all events. `ImpasseRecord` carries full context. `caused_by` links to triggering event. `OperationRecoveryBudget` reports remaining attempts. |
| 6 | Can recovery terminate deterministically? | **YES** | `OperationRecoveryBudget.exhausted` is a boolean check. `max_total_recovery_attempts` is finite. No hidden parallel budgets (frozen invariant). |
| 7 | Can the system distinguish root failure from downstream consequences? | **YES** | `derived_from` = artifact lineage. `caused_by` = root causal event. `operation_id` distinguishes stage. `trace_id` groups. |
| 8 | Can architecture drift be detected automatically? | **YES** | `scripts/check_drift.py` with 9 AST-based checks. `tests/test_architecture_drift.py` CI gate. |

---

## Appendix B — Architectural Invariant Testability Matrix

| # | Invariant | Unit | Integration | Static | Runtime Diagnostic |
|---|---|---|---|---|---|
| 1 | RawRequest/Goal authority | `RawRequest(frozen=True)` test | interpret→plan pipeline | DRIFT-04 | `cognitive.goal_formed` |
| 2 | Goal semantic preservation | Goal roundtrip test | K4.2 pipeline end-to-end | — | `derived_from` chain |
| 3 | Canonical CapabilityDiscoveryResult | Return type assertion | Pipeline consumes scores | — | `cognitive.capabilities_discovered` |
| 4 | Specific > general ranking | Ranking with 2+ capabilities | Cases A/B | DRIFT-06 | Score in event payload |
| 5 | Second-capability discrimination | Cases A–E | Full pipeline, 2+ capabilities | — | Event payloads |
| 6 | Operation recovery budget | Budget consume/exhaust | Recovery + budget threading | — | Budget remaining in diagnostics |
| 7 | Supervisor authority boundaries | Supervisor ignores PlannerResult | Compilation reject → Supervisor | DRIFT-03, DRIFT-05 | `cognitive.supervision_escalated` |
| 8 | derived_from vs caused_by | `derived_from` = resource IDs only | Failure → recovery → caused_by | — | Provenance query |
| 9 | Diagnostic failure recording | Impasse terminal event test | Full failure path | — | Event completeness |
| 10 | Dynamic capability registration | Register → discovered | No Planner change needed | DRIFT-06 | Discovery event |
| 11 | Governance boundary | Compile without governance fails | Governance reject → Supervisor | DRIFT-05 | `cognitive.plan_rejected` |
| 12 | Canonical construction | RawRequest only from normalize | — | DRIFT-04, DRIFT-08 | — |
| 13 | Language preservation | `detected_language` field test | Input → output language | — | Metadata in payload |
| 14 | Architecture drift | All DRIFT checks pass | — | DRIFT-01 through DRIFT-09 | — |

---

**Repository status:** Read-only. No `.git` directory present (extracted archive). No files modified.
