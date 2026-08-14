# K4.2 v1.0 — FINAL IMPLEMENTATION-ALIGNMENT CORRECTION PASS

**Date:** Aug 14, 2026
**Authority:** Final correction pass before K4.2-H1 implementation begins.
**Repository status:** Read-only. No `.git` directory present (extracted archive). No files modified.

---

## 1. Freeze Verdict

### `READY TO FREEZE`

Four implementation-alignment corrections applied. All contract-to-implementation mismatches resolved. The specification below is safe to use as the authoritative H1 implementation packet.

---

## 2. Corrections Applied

### H1-C1 — Recovery Budget Wired Through Orchestrator

**Problem:** `OperationRecoveryBudget` was defined in `core/cognitive/recovery.py` but `core/orchestrator.py` was not listed in the H1 module scope. The budget existed as a data contract without actually being the shared authority.

**Correction:** `core/orchestrator.py` is now explicitly in H1 scope. The specification defines:
- **Budget creation:** Orchestrator creates `OperationRecoveryBudget` at K4.2 branch entry (line 261), reading `max_recovery_attempts` from config.
- **Budget ownership:** Orchestrator owns the single authoritative instance for the operation.
- **Budget propagation:** Orchestrator passes the budget instance to `plan()` and to Supervisor via `context.parameters["recovery_budget"]`.
- **Budget consumption:** `plan()` calls `budget.consume()` before each re-planning attempt. Supervisor's `_attempt_retry()` calls `budget.consume()` before each worker retry.
- **Budget exhaustion:** When `budget.exhausted == True`, the caller emits a terminal diagnostic event and returns a user-facing failure.
- **Clarification:** Creates a new Orchestrator `handle()` call → new `trace_id` → new `OperationRecoveryBudget`.

**New integration test:** `test_shared_budget_across_planner_and_supervisor` proving same budget consumed by both.

---

### H1-C2 — Autonomous Re-Compilation Removed from v1.0

**Problem:** D5 listed "re-compilation" as an autonomous recovery action, but no v1.0 code path implements autonomous re-compilation. No specification defines who initiates it, what changes, or how governance is re-entered.

**Correction:** Autonomous re-compilation is **removed** from the v1.0 recovery contract. The only autonomous recovery actions in v1.0 are:
1. **Planner re-planning** (on impasse, if budget allows)
2. **Supervisor worker retry** (on worker failure, if budget allows)

Compilation rejection continues to use the existing Supervisor surface path (Orchestrator lines [294–304](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/orchestrator.py#L294-L304)) — Supervisor surfaces the rejection, it does not re-compile. A future re-compilation recovery mechanism MAY be introduced through a dedicated ADR.

All references to "re-compilation" as a budget-consuming recovery action have been removed from: D5, recovery state machine, recovery table, ADR-K4.2-H-05, H1 tests, H1 acceptance gate.

---

### H1-C3 — Capability Discovery Signal-Extensible + Match Evidence

**Problem:** The specification could be read as freezing Jaccard token-overlap as the architectural definition of capability semantics. `CapabilityMatch` lacked explanatory evidence.

**Correction:**
- **Signal extensibility frozen:** `_capability_match_score()` is the current v1.0 implementation of matching signals, NOT the architectural definition. The stable contract is: `CapabilityDiscoveryRequest → candidate generation → relevance signals → CapabilityMatch → CapabilityDiscoveryResult → Planner`. Internal signals may evolve without changing the external discovery contract.
- **Match evidence added:** `CapabilityMatch` gains `evidence: Dict[str, Any] = field(default_factory=dict)` for diagnostic/explanatory metadata. Evidence is NOT a second source of truth — `relevance_score` remains canonical.
- **Invariant frozen:** Future matching signals MAY be added or replaced without changing the semantic meaning of `CapabilityMatch`, `CapabilityDiscoveryResult`, `Goal`, or `PlannerRequest`.

---

### H1-C4 — operation_id Semantics Resolved

**Problem:** The identifier model listed `plan()`, `compile()`, and `discover_capabilities()` as operation-producing calls, but `discover_capabilities()` is called *inside* `_decompose()` which is called *inside* `plan()`. These are nested, not independent top-level operations.

**Correction — resolved semantic model:**
- `operation_id` scopes to **top-level cognitive stage invocations only**: `plan()` and `compile()`.
- `discover_capabilities()` calls within `plan()` share the parent `operation_id` and are distinguished by a `stage_tag` field in the event payload (e.g., `"stage_tag": "capability_discovery:step-0"`).
- This matches the repository reality: `discover_capabilities()` is called in a loop inside `_decompose()` (lines [916–938](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/planner.py#L916-L938)), not as an independent top-level operation.

**Parent/child structure:**
```
trace_id = T-abc
    │
    ├── operation_id = O-plan-001    (plan() call)
    │       ├── stage_tag = "capability_discovery:step-0"
    │       ├── stage_tag = "capability_discovery:step-1"
    │       └── stage_tag = "constraint_extraction"
    │
    └── operation_id = O-compile-001 (compile() call)
```

---

### Secondary Corrections Applied

**S1 — RawRequest Frozen Construction (§9 of directive):**
H2 spec updated to require language detection *before* `RawRequest` construction, since `frozen=True`:
```python
language = _detect_language(text)
return RawRequest(text=text, detected_language=language)
```

**S2 — Intent.raw_request vs RawRequest Distinction (§10):**
D1 clarified: `RawRequest` is the normalized input boundary object (`@dataclass(frozen=True)`). `Intent.raw_request` is an immutable `str` field capturing `RawRequest.text`. They are NOT the same type. The relationship is: `RawRequest.text → Intent.raw_request` (string copy).

**S3 — DRIFT-08 Ownership Model (§11):**
DRIFT-08 now requires a declared canonical owner for each shared contract. Only production construction outside the declared owner is flagged. Test doubles and compatibility adapters remain legal. Canonical owners documented in the drift check configuration.

**S4 — Diagnostic System Scoping (§12):**
H1 establishes the OCBrain-wide Diagnostic & Failure *contract*. H1/H2 do not require every OCBrain subsystem to migrate immediately. K4.2 is the first major consumer. Future milestones integrate their subsystem-specific failure codes.

**S5 — Intent.raw_request docstring:**
H1 adds a D1-compliance docstring to `Intent.raw_request: str` explicitly noting it is a captured string value, not a `RawRequest` reference.

---

## 3. Final Normative Rules (Corrected)

> Changes from the previous specification are marked with `[CORRECTED]`.

**D1 — Layered Semantic Authority.** `RawRequest` is immutable (`frozen=True`). Goal is the authoritative cognitive interpretation. `[CORRECTED]` `Intent.raw_request: str` captures `RawRequest.text` by value. It is not a nested `RawRequest` object. Downstream cognitive stages MUST consume Goal, not re-interpret `RawRequest` independently. Diagnostic/audit access is observational.

**D2 — General-Purpose Fallback.** `CapabilityContract.is_general_purpose: bool = False`. Specificity dominance. No hard-coded routing.

**D3 — Capability Discrimination Gate.** K4.2-H2: 5 acceptance cases (A–E). Adding a capability MUST NOT require Planner modification.

**D4 — Canonical CapabilityDiscoveryResult.** `discover_capabilities()` returns `CapabilityDiscoveryResult`. `[CORRECTED]` `CapabilityMatch` includes `evidence: Dict[str, Any]` for diagnostic metadata. `[CORRECTED]` The matching signal implementation (`_capability_match_score()`) is NOT the architectural definition — it is the current v1.0 signal. Future signals MAY be added without changing the discovery contract.

**D5 — Unified Recovery Budget.** `[CORRECTED]` v1.0 autonomous recovery = Planner re-planning + Supervisor worker retry ONLY. Autonomous re-compilation is NOT a v1.0 recovery action. `[CORRECTED]` Orchestrator creates, owns, and threads the single `OperationRecoveryBudget`. No hidden parallel budgets.

**D6 — Learning Domain Contract.** ContentDomain = closed set. `[RECONCILE-PENDING]` markers removed.

**D7 — Supervisor Terminal Role.** Terminal Planner impasse does NOT route through Supervisor.

**D8 — Trace Semantics.** `[CORRECTED]` `operation_id` scopes to top-level cognitive stage calls (`plan()`, `compile()`) only. `discover_capabilities()` shares the parent `operation_id` with a `stage_tag` discriminator. No `correlation_id`.

**D9 — Causal Provenance.** `derived_from: List[str]` = artifact lineage only. `caused_by: Optional[str]` = causal event reference.

**D10 — Architecture-Drift Verification.** `[CORRECTED]` DRIFT-08 requires declared canonical owners. Test doubles exempt.

**D11 — Multilingual Scope.** `[CORRECTED]` H2 language detection MUST occur before `RawRequest` construction (frozen dataclass).

**D12 — H1/H2 Structure.** H1 → H1 freeze → H2 → H2 freeze → v1.0 freeze.

---

## 4. Final Contract Model (Corrected)

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

### CapabilityMatch (NEW — H1) `[CORRECTED]`
```python
@dataclass
class CapabilityMatch:
    """One candidate from capability discovery.

    evidence is diagnostic/explanatory metadata — NOT a second source
    of truth. relevance_score remains the canonical ranking signal.
    """
    capability_type: str
    contract: CapabilityContract
    relevance_score: float
    subgoal_ref: str
    is_general_purpose: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)
```

**v1.0 evidence keys** (populated where signal exists):

| Key | Type | Source |
|---|---|---|
| `lexical_score` | `float` | `_capability_match_score()` Jaccard result |
| `specificity_tier` | `str` | `"strong_specific"`, `"weak_specific"`, or `"general_fallback"` |
| `general_fallback` | `bool` | `True` if this is a general-purpose capability acting as fallback |

Future signals (embeddings, domain, schema, language) add keys without changing the contract.

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

    @property
    def top_match(self) -> Optional[CapabilityMatch]:
        """Highest-ranked candidate, or None if empty."""
        return self.matches[0] if self.matches else None
```

### OperationRecoveryBudget (NEW — H1) `[CORRECTED]`
```python
@dataclass
class OperationRecoveryBudget:
    """One per operation (scoped by trace_id).

    v1.0 autonomous recovery actions:
        - Planner re-planning (on impasse)
        - Supervisor worker retry (on worker failure)

    NOT included in v1.0: autonomous re-compilation.
    """
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

### RawRequest (H1 changes `frozen=True`; H2 adds `detected_language`)

**After H1:**
```python
@dataclass(frozen=True)
class RawRequest:
    text: str
```

**After H2:** `[CORRECTED — construction pattern]`
```python
@dataclass(frozen=True)
class RawRequest:
    text: str
    detected_language: Optional[str] = None
```

**H2 construction pattern** (detection before construction):
```python
def normalize_request(raw_text: str) -> RawRequest:
    # ... existing normalization ...
    text = ...  # normalized text
    language = _detect_language(text)  # best-effort, may return None
    return RawRequest(text=text, detected_language=language)
```

---

## 5. Final Capability Discovery Contract (Corrected)

### Signal-Extensibility Invariant (Frozen)

> `_capability_match_score()` is the current v1.0 implementation of matching signals. It is NOT the architectural definition of capability semantics. Future matching signals MAY be added or replaced without changing the semantic meaning of `CapabilityMatch`, `CapabilityDiscoveryResult`, `Goal`, or `PlannerRequest`.

### Stable Contract Boundary

```
CapabilityDiscoveryRequest          ← STABLE INPUT CONTRACT
        ↓
    candidate generation            ← implementation detail (registry iteration)
        ↓
    relevance signals               ← EXTENSIBLE (v1.0: Jaccard; future: embeddings, etc.)
        ↓
    CapabilityMatch (with evidence) ← STABLE OUTPUT TYPE
        ↓
    specificity dominance           ← STABLE RANKING RULE
        ↓
    CapabilityDiscoveryResult       ← STABLE OUTPUT CONTRACT
        ↓
    Planner                         ← STABLE CONSUMER
```

**What is frozen:** Input/output types, ranking rule, evidence contract shape.
**What is extensible:** Internal signal computation, evidence keys, threshold values.

### v1.0 Discovery Flow (Corrected)

```python
async def discover_capabilities(...) -> CapabilityDiscoveryResult:
    scored = []
    for capability_type in registry.list_capabilities():
        contract = registry.get_contract(capability_type)
        if contract is None or not registry.get_adapters(capability_type):
            continue
        score = _capability_match_score(request, contract)
        if score >= min_score:
            tier = _classify_tier(score, contract.is_general_purpose, threshold)
            match = CapabilityMatch(
                capability_type=contract.capability_type,
                contract=contract,
                relevance_score=score,
                subgoal_ref=request.subgoal_ref,
                is_general_purpose=contract.is_general_purpose,
                evidence={
                    "lexical_score": round(score, 4),
                    "specificity_tier": tier,
                    "general_fallback": contract.is_general_purpose,
                },
            )
            scored.append(match)

    # Apply specificity dominance
    ranked = _apply_specificity_dominance(scored, threshold)

    # Emit event (derived projection — not authoritative)
    await event_stream.append("cognitive.capabilities_discovered", ...)

    return CapabilityDiscoveryResult(matches=ranked, subgoal_ref=request.subgoal_ref)
```

---

## 6. Final Recovery Contract (Corrected)

### v1.0 Autonomous Recovery Actions (Exhaustive)

| # | Action | Initiator | Budget impact | Existing code path |
|---|---|---|---|---|
| 1 | **Planner re-planning** | Orchestrator (on impasse, if budget allows) | `budget.consume()` | Currently: Orchestrator returns immediately on impasse (line 286). H1 adds re-plan loop. |
| 2 | **Supervisor worker retry** | Orchestrator → Supervisor (on worker failure, if budget allows) | `budget.consume()` | Currently: Supervisor `_attempt_retry()` (line 248) uses `max_supervisor_retries`. H1 threads budget. |

**NOT in v1.0:** Autonomous re-compilation. Compilation rejection → Supervisor surfaces → terminal.

### Budget Lifecycle (Corrected)

```
Orchestrator.handle(query)
    │
    ├── budget = OperationRecoveryBudget(
    │       max_total_recovery_attempts=config.max_recovery_attempts)
    │
    ├── interpret_request(query)  → goals
    │
    ├── PLAN_LOOP:
    │   │  planner_result = plan(request, registry, budget=budget)
    │   │
    │   │  IF impasse AND budget.consume():
    │   │      → retry PLAN_LOOP
    │   │  ELIF impasse AND budget.exhausted:
    │   │      → emit cognitive.planner_impasse_terminal
    │   │      → return terminal failure to user
    │   │  ELIF ready_for_compilation:
    │   │      → continue to compile
    │
    ├── compilation_result = compile(plan)
    │   │
    │   │  IF rejected/escalated:
    │   │      → Supervisor.surface()  (existing path, no retry)
    │   │      → return terminal failure to user
    │
    ├── wf_result = workflow_runtime.execute(workflow_definition)
    │   │
    │   │  IF worker failure AND budget.consume():
    │   │      → Supervisor._attempt_retry()
    │   │  ELIF worker failure AND budget.exhausted:
    │   │      → emit cognitive.operation_failed
    │   │      → return terminal failure to user
    │
    └── return answer
```

### Budget Propagation (Corrected — Precise)

| Component | How it receives budget | How it consumes |
|---|---|---|
| **Orchestrator** | Creates it. Reads `config/settings.toml [runtime] max_recovery_attempts`. | Calls `budget.consume()` before re-planning. |
| **Planner (`plan()`)** | Does NOT consume budget directly. Returns `PlannerResult` with `status='impasse'`. Orchestrator decides whether to re-invoke. | N/A — Orchestrator is the decision-maker. |
| **Supervisor** | Receives budget via `context.parameters["recovery_budget"]`. | Calls `budget.consume()` in `_attempt_retry()` before the retry call. Replaces the current `attempt >= max_retries` check. |

### Recovery Invariant (Frozen)

> Every user operation has one authoritative autonomous recovery budget. No component may create an independent recovery budget outside this contract. Planner and Supervisor consume the same budget instance. Neither may create a hidden retry universe.

---

## 7. Final Diagnostic Contract (Corrected)

### Scope Clarification

H1 establishes the OCBrain-wide Diagnostic & Failure **contract**. K4.2 is the first major consumer. H1/H2 do NOT require every OCBrain subsystem to migrate immediately. Future milestones integrate their subsystem-specific failure codes using the shared contract.

### Diagnostic Events (v1.0 — K4.2 scope)

| Event type | Emitted by | When | Payload keys |
|---|---|---|---|
| `cognitive.planner_impasse_terminal` | Orchestrator | Terminal Planner impasse (budget exhausted) | `trace_id`, `operation_id`, `goal_id`, `impasse_detail`, `recovery_budget_state` |
| `cognitive.operation_failed` | Orchestrator | Terminal worker failure (budget exhausted) | `trace_id`, `operation_id`, `workflow_id`, `failure_detail`, `recovery_budget_state` |
| `cognitive.capabilities_discovered` | `discover_capabilities()` | After discovery completes | `trace_id`, `operation_id`, `stage_tag`, `subgoal_ref`, `candidates` |
| `cognitive.constraints_extracted` | `_extract_constraints()` | After extraction | `trace_id`, `operation_id`, `goal_id`, `constraint_count` |
| `cognitive.plan_compiled` | `compile()` | After successful compilation | `trace_id`, `operation_id`, `plan_id` |
| `cognitive.plan_rejected` | `compile()` | Governance rejects plan | `trace_id`, `operation_id`, `plan_id`, `reason` |
| `cognitive.supervision_escalated` | Supervisor | Plan escalated | `trace_id`, `governance_reason` |

### Contract Boundary

The Diagnostic System is **cross-cutting**, **reusable**, and **non-authoritative** for recovery and governance. It records; it does not decide. It does NOT become: Orchestrator, Governance engine, or autonomous recovery engine.

---

## 8. Final Identifier and Provenance Contract (Corrected)

### Identifier Model `[CORRECTED]`

| Identifier | Scope | Creator | Semantics |
|---|---|---|---|
| `trace_id` | Entire user request | `interpret_request()` via `tracer.get_trace_id()` | Groups ALL events, artifacts, operations in one user interaction |
| `operation_id` | Top-level cognitive stage | `plan()` and `compile()` each generate one | Disambiguates repeated stage invocations within a trace |
| `stage_tag` | Sub-operation discriminator | Callers within an operation (e.g., `_decompose()`) | Distinguishes sub-calls (e.g., per-step discovery) within one operation. NOT an independent identifier. |
| `event_id` | Single event | `EventStream.append()` | Unique event reference |
| `resource_id` | Single artifact | Artifact constructor | Unique artifact reference |
| `workflow_id` | Workflow execution | `WorkflowRuntime.execute()` | Groups workflow events |

### `operation_id` Nesting Model `[CORRECTED]`

```
trace_id = T-abc
    │
    ├── operation_id = O-plan-001           ← plan() generates this
    │       ├── stage_tag: "constraint_extraction"
    │       ├── stage_tag: "capability_discovery:step-0"
    │       ├── stage_tag: "capability_discovery:step-1"
    │       ├── stage_tag: "decomposition"
    │       └── stage_tag: "impasse_detection"
    │
    ├── operation_id = O-plan-002           ← re-plan after recovery
    │       └── (same sub-tags)
    │
    └── operation_id = O-compile-001        ← compile() generates this
```

**Key property:** `discover_capabilities()` does NOT generate its own `operation_id`. It executes within the parent `plan()` operation and is distinguished by `stage_tag` in event payloads.

### Provenance Model

| Field | Type | Contains | Example |
|---|---|---|---|
| `derived_from` | `List[str]` | Artifact `resource_id`s ONLY | `["goal-uuid-123"]` |
| `caused_by` | `Optional[str]` | Event `event_id` ONLY (or `None`) | `"event-uuid-failure-456"` |

**Invariant:** `derived_from` MUST NOT contain event IDs. `caused_by` MUST NOT contain artifact IDs.

---

## 9. Final Drift Verification Contract (Corrected)

| Check | Rule | Mechanism |
|---|---|---|
| DRIFT-01 | `core/cognitive/*.py` must not import `core.workflow.runtime` | AST import analysis |
| DRIFT-02 | `core/cognitive/*.py` must not import `core.capabilities.adapter_runtime` | AST import analysis |
| DRIFT-03 | `supervisor.py` must not import `plan()` or `compile()` functions | AST import + name analysis. Note: importing `CompilationResult`/`CompilationStatus` is legitimate (consumer, not caller). |
| DRIFT-04 | `RawRequest` construction only in `core/cognitive/intent.py` | Constructor call-site analysis |
| DRIFT-05 | `SupervisorWorker` must not call `GovernanceKernel.evaluate_action()` directly | AST call-site. Note: docstring mentions are NOT violations. |
| DRIFT-06 | No hard-coded capability type strings in Planner routing | Literal string analysis in discovery/routing paths |
| DRIFT-07 | `cognitive.*` events emitted only from `core/cognitive/` or `core/workers/` | Event type + source file cross-reference. Exception: `cognitive.planner_impasse_terminal` emitted by Orchestrator (declared owner per D7). |
| DRIFT-08 | `[CORRECTED]` Canonical builders not bypassed by production code outside declared owner | Constructor call-site filtered by ownership declaration. Test doubles and compatibility adapters EXEMPT. |
| DRIFT-09 | No unauthorized shared-contract producer outside declared owners | Producer source analysis |

### DRIFT-08 Canonical Ownership Declarations

| Contract | Canonical Constructor/Builder | Declared Owner |
|---|---|---|
| `RawRequest` | `normalize_request()` | `core/cognitive/intent.py` |
| `Goal` | `form_goals()` | `core/cognitive/intent.py` |
| `ExecutionPlan` | `plan()` | `core/cognitive/planner.py` |
| `CapabilityDiscoveryResult` | `discover_capabilities()` | `core/cognitive/planner.py` |
| `CompilationResult` | `compile()` | `core/cognitive/compiler.py` |
| `OperationRecoveryBudget` | Orchestrator K4.2 branch | `core/orchestrator.py` |

DRIFT-08 flags production construction of these types outside their declared owner. Test files (`tests/*.py`) are exempt.

### DRIFT-07 Exception

`cognitive.planner_impasse_terminal` is emitted by `core/orchestrator.py`, not by `core/cognitive/` or `core/workers/`. This is architecturally declared per D7 (terminal impasse routes through Orchestrator, not Supervisor). The drift check MUST whitelist this specific event+source combination.

---

## 10. Corrected H1 Implementation Specification

### H1 Scope
H1 implements Decisions 1, 2, 4, 5, 6, 8, 9 — foundational contracts.

### Exact Modules Affected `[CORRECTED]`

---

#### [MODIFY] [`core/capabilities/capability.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/capabilities/capability.py)

**Line 124:** Add `is_general_purpose: bool = False` to `CapabilityContract`.
**Migration:** None — new field with default. All existing registrations unchanged.

---

#### [MODIFY] [`core/cognitive/intent.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/intent.py)

| Change | Location | Detail |
|---|---|---|
| `RawRequest` frozen | Line 196 | `@dataclass` → `@dataclass(frozen=True)` |
| `CognitiveArtifact` gains `caused_by` | Line 52–73 | Add `caused_by: Optional[str]` to Protocol |
| `Intent` gains `caused_by` | Line 152 | Add `caused_by: Optional[str] = None` |
| `Goal` gains `caused_by` | Line 492 | Add `caused_by: Optional[str] = None` |
| D1-compliance docstring on `Intent.raw_request` | Line 179 | Document: `str` value captured from `RawRequest.text`, not a `RawRequest` reference |
| `trace_id` in events | Line 707+ | `interpret_request()` calls `get_trace_id()` and includes in event payloads |

**Migration check:** Verify no code mutates `RawRequest` after construction. Repository evidence confirms: `normalize_request()` constructs and returns; no downstream mutation.

---

#### [MODIFY] [`core/cognitive/planner.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/planner.py)

| Change | Location | Detail |
|---|---|---|
| Add `CapabilityMatch` dataclass | After line 596 | Fields: `capability_type`, `contract`, `relevance_score`, `subgoal_ref`, `is_general_purpose`, `evidence` |
| Add `CapabilityDiscoveryResult` dataclass | After `CapabilityMatch` | Fields: `matches`, `subgoal_ref`. Properties: `contracts`, `top_match` |
| `discover_capabilities()` return type | Lines 639–716 | Returns `CapabilityDiscoveryResult` instead of `List[CapabilityContract]`. Builds `CapabilityMatch` entries with scores and evidence. Applies specificity dominance. |
| `_decompose()` update | Lines 863–946 | Consumes `CapabilityDiscoveryResult.matches` instead of bare list |
| `_detect_impasse()` update | Lines 1094–1133 | Consumes `CapabilityMatch` objects |
| `_estimate_confidence()` update | Lines 991–1016 | Consumes `CapabilityMatch` objects |
| `_alternative_plans()` update | Lines 1019–1064 | Consumes `CapabilityMatch` objects |
| `ExecutionPlan` gains `caused_by` | Line 804 | Add `caused_by: Optional[str] = None` |
| `operation_id` generation | Line 1136 (`plan()`) | Generate `operation_id = str(uuid.uuid4())`, include in all event payloads along with `trace_id` |
| `stage_tag` in discovery events | Line 703 | Add `"stage_tag": f"capability_discovery:{request.subgoal_ref}"` to event payload |

**All callers of `discover_capabilities()` are internal** to this file (`_decompose()`). No external consumers exist.

---

#### [MODIFY] [`core/cognitive/compiler.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/compiler.py)

**`compile()` (line 257):** Generate `operation_id`, include in event payloads with `trace_id`.
**Migration:** Additive payload keys only.

---

#### [MODIFY] [`core/cognitive/learning.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/learning.py)

Add `caused_by: Optional[str] = None` to `LearningRecord` and `CognitiveDecision`.
**Migration:** None — new optional field.

---

#### [NEW] `core/cognitive/recovery.py`

Contains `OperationRecoveryBudget` dataclass (as specified in §4). Module-level data contract only.

---

#### [MODIFY] [`core/orchestrator.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/orchestrator.py) `[CORRECTED — was missing]`

| Change | Location | Detail |
|---|---|---|
| Budget creation | Line 261 (K4.2 branch entry) | `budget = OperationRecoveryBudget(max_total_recovery_attempts=config.max_recovery_attempts)` |
| Planner re-plan loop | Lines 276–287 | Wrap `plan()` call in a loop: on impasse, if `budget.consume()`, retry; else emit terminal event and return |
| Budget to Supervisor | Lines 297–304 | Thread `budget` into Supervisor's `context.parameters["recovery_budget"]` |
| Terminal impasse event | After line 287 | Emit `cognitive.planner_impasse_terminal` with `ImpasseRecord` and `recovery_budget_state` |

**Implementation pattern:**
```python
# Inside the K4.2 branch (line 261+):
budget = OperationRecoveryBudget(
    max_total_recovery_attempts=self._config.get(
        "runtime", {}).get("max_recovery_attempts", 3))

planner_result = None
while True:
    planner_result = await plan_fn(
        planner_request, self._capability_registry,
        event_stream=self._event_stream)

    if planner_result.status == PlannerStatus.READY_FOR_COMPILATION:
        break

    if not budget.consume():
        # Terminal impasse — budget exhausted
        await self._emit_event("cognitive.planner_impasse_terminal", {
            "interaction_id": interaction_id,
            "impasse_detail": str(planner_result.impasse_detail),
            "recovery_budget_remaining": budget.remaining,
        })
        return ("Sorry, I could not form a plan for this "
                f"request: {planner_result.status}")

    # Re-plan with same request (budget consumed, loop continues)
```

---

#### [MODIFY] [`core/workers/supervisor.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/workers/supervisor.py)

| Change | Location | Detail |
|---|---|---|
| `_attempt_retry()` | Lines 248–290 | Read `budget = context.parameters.get("recovery_budget")`. If present, call `budget.consume()` before retry. If exhausted, return `RETRY_EXHAUSTED`. Falls back to existing `max_supervisor_retries` check if no budget provided (legacy compatibility). |

**Implementation pattern:**
```python
async def _attempt_retry(self, context, failed_result):
    budget = context.parameters.get("recovery_budget")
    if budget is not None:
        if not budget.consume():
            return WorkerResult(
                success=False,
                output={"outcome": SupervisorOutcome.RETRY_EXHAUSTED,
                        "budget_remaining": 0},
            )
    else:
        # Legacy path — existing max_supervisor_retries check
        max_retries = int(context.parameters.get("max_supervisor_retries", 1))
        attempt = int(context.parameters.get("supervisor_retry_attempt", 0))
        if attempt >= max_retries:
            return WorkerResult(...)
    # ... proceed with retry ...
```

---

#### [MODIFY] [`config/settings.toml`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/config/settings.toml)

Add under `[runtime]`:
```toml
max_recovery_attempts = 3
```

---

#### Documentation changes (H1)

| File | Change |
|---|---|
| `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` | Remove `[RECONCILE-PENDING]` markers from §0, §6 |
| `docs/architecture/decisions/ADR_INDEX.md` | Add K4.2-H-01 through K4.2-H-09 to Standalone ADRs table |
| 7 new ADR files | ADR-K4.2-H-01 through ADR-K4.2-H-09 (H1 decisions) |

---

### H1 Rollback
All changes are additive: new fields with defaults, new dataclasses, return type widening, config key addition. Rollback = revert commit. No schema migration.

### H1 Stop Conditions
- **STOP** if `RawRequest(frozen=True)` causes test failures — search for post-construction mutation.
- **STOP** if `discover_capabilities()` return type change breaks callers — verify `.contracts` compatibility.
- **STOP** if Orchestrator re-plan loop introduces unbounded behavior — budget MUST enforce termination.
- **STOP** if any existing test fails unrelated to H1 changes.

---

## 11. Corrected H1 Acceptance Gate

| # | Criterion | Type | Pass condition |
|---|---|---|---|
| H1-G1 | Goal semantic preservation | Unit | `Goal.derived_from` populated, `intent_id` set, `caused_by` field present |
| H1-G2 | `CapabilityDiscoveryResult` contract | Unit | `discover_capabilities()` returns structured type with scores and evidence |
| H1-G3 | Specific/general ranking | Unit | Strong specific ranks above general-purpose; evidence contains `specificity_tier` |
| H1-G4 | Recovery budget contract | Unit | Budget counts, exhausts, reports remaining correctly |
| H1-G5 | `[CORRECTED]` Shared budget integration | Integration | **Same** `OperationRecoveryBudget` instance consumed by Orchestrator (for re-plan) and Supervisor (for retry). Remaining decrements correctly across both. Terminal when exhausted. |
| H1-G6 | Identifier propagation | Unit+Integration | `trace_id` stable across request; `operation_id` per `plan()`/`compile()` call; `stage_tag` distinguishes sub-calls |
| H1-G7 | Provenance separation | Unit | `derived_from` = resource IDs only; `caused_by` = event ID or None |
| H1-G8 | Learning reconciliation | Spec review | `[RECONCILE-PENDING]` markers removed |
| H1-G9 | Existing regression | Suite | All pre-existing tests pass |
| H1-G10 | Architecture drift (H1 checks) | Static | DRIFT-01, DRIFT-02, DRIFT-04, DRIFT-05, DRIFT-06 pass |
| H1-G11 | Signal extensibility | Unit | Adding a new evidence key to `CapabilityMatch.evidence` does not change `CapabilityDiscoveryResult` contract or any consumer |

**H1 FREEZE** requires all 11 criteria passing.

### H1-G5 Integration Test (Required) `[NEW]`

```python
def test_shared_budget_across_planner_and_supervisor():
    """Prove ONE budget is shared, not independent copies."""
    budget = OperationRecoveryBudget(max_total_recovery_attempts=3)
    assert budget.remaining == 3

    # Simulate Planner re-plan (Orchestrator consumes)
    assert budget.consume() == True
    assert budget.remaining == 2

    # Simulate Supervisor worker retry
    assert budget.consume() == True
    assert budget.remaining == 1

    # One more
    assert budget.consume() == True
    assert budget.remaining == 0

    # Exhausted
    assert budget.consume() == False
    assert budget.exhausted == True
```

This test alone is necessary but not sufficient. The integration test MUST also verify that Orchestrator passes the same instance to both Planner (re-plan loop) and Supervisor (via context.parameters).

---

## 12. Corrected H2 Implementation Specification

### H2 Scope
H2 implements Decisions 3, 7, 10, 11, 12 — operational hardening.

### Exact Modules Affected

#### [MODIFY] [`core/cognitive/intent.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/cognitive/intent.py)

- `RawRequest` gains `detected_language: Optional[str] = None`. Since H1 made it `frozen=True`, detection MUST occur before construction.
- `normalize_request()` adds best-effort language detection. Pattern: `language = _detect_language(text); return RawRequest(text=text, detected_language=language)`.

#### [MODIFY] [`core/orchestrator.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(6)/ocbrain-v4.1-main/core/orchestrator.py)

- Terminal Planner impasse: emit `cognitive.planner_impasse_terminal` (if not already done in H1 — verify H1 completion).

#### [NEW] `scripts/check_drift.py`

- DRIFT-01 through DRIFT-09. AST analysis. Outputs JSON. Canonical ownership declarations embedded.

#### [NEW] `tests/test_architecture_drift.py`

- Pytest wrapper importing `check_drift`. One test per DRIFT check.

#### [NEW] `tests/test_capability_discrimination.py`

- Cases A–E per D3. Plus dynamic registration test.

#### Documentation

- 3 new ADR files: ADR-K4.2-H-10 through ADR-K4.2-H-12.
- `IMPLEMENTATION_TRACKER.md`, `IMPLEMENTATION_ROADMAP.md`, `CURRENT_STATE.md` updates.

### H2 Stop Conditions
- **STOP** if any DRIFT check fails on current repo (before H2 changes) — check definition is wrong.
- **STOP** if language detection dependency unavailable — fall back to `None`.

---

## 13. Corrected H2 Acceptance Gate

| # | Criterion | Type | Pass condition |
|---|---|---|---|
| H2-G1 | Cases A–E | Integration | All 5 discrimination cases pass |
| H2-G2 | Dynamic registration | Integration | New capability discovered without code change |
| H2-G3 | Terminal impasse diagnostic | Integration | `cognitive.planner_impasse_terminal` emitted with full payload |
| H2-G4 | Language preservation | Unit | `detected_language` field present; frozen construction pattern works; no silent output language change |
| H2-G5 | Architecture drift CI | Static | DRIFT-01 through DRIFT-09 pass |
| H2-G6 | Complete regression | Suite | All pre-existing + H1 + H2 tests pass |
| H2-G7 | H1 contracts preserved | Suite | All H1-G1 through H1-G11 still pass |
| H2-G8 | Diagnostic causal tracing | Integration | `trace_id` → events → `caused_by` → failure chain queryable |
| H2-G9 | No boundary violations | Static + Review | No DRIFT failures; diff is H2-scoped only |

**H2 FREEZE** requires all 9 criteria. **K4.2 v1.0 FREEZE** = H1 FREEZE + H2 FREEZE.

---

## 14. Final Parallel Milestone Contract

After K4.2 v1.0 FREEZE, future milestones:

1. **Consume frozen contracts.** `CapabilityDiscoveryResult`, `OperationRecoveryBudget`, `CognitiveArtifact` (with `caused_by`), identifier semantics.
2. **Preserve invariants.** All 14 in the testability matrix.
3. **Declare extensions via ADR.** New shared fields, contract changes, recovery authority changes.
4. **Use Diagnostic System.** Emit events via `EventStream`; use `trace_id`, `operation_id`.
5. **Pass drift gate.** `tests/test_architecture_drift.py` must pass.

**MAY independently:** Internal refactors, private optimizations, new subsystem-local failure codes.
**MUST obtain review for:** Shared contract meaning, ownership, provenance semantics, recovery authority, governance boundaries, execution semantics, canonical construction rules, Diagnostic core contract.

---

## 15. Final Risks (Corrected)

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Orchestrator re-plan loop complexity | Medium | Budget enforces termination. Loop is structurally bounded by `max_total_recovery_attempts`. Stop condition defined. |
| R2 | Supervisor budget/legacy dual-path | Low | Legacy `max_supervisor_retries` preserved as fallback. New budget path is additive. Supervisor remains stateless. |
| R3 | `discover_capabilities()` return type change | Low | All callers internal to `planner.py`. `.contracts` compatibility property provided. |
| R4 | Language detection dependency availability | Low | `detected_language` defaults to `None`. Detection failure is degradation, not error. |
| R5 | DRIFT-07 Orchestrator exception for `cognitive.planner_impasse_terminal` | Low | Explicitly whitelisted in drift check configuration. Architecturally justified by D7. |

---

## 16. Final Recommendation

### `READY TO FREEZE`

All four implementation-alignment corrections have been applied:
- **H1-C1:** Recovery budget wired through Orchestrator with precise lifecycle semantics.
- **H1-C2:** Autonomous re-compilation removed from v1.0 recovery contract.
- **H1-C3:** Capability discovery frozen as signal-extensible; `CapabilityMatch` gains evidence.
- **H1-C4:** `operation_id` scoped to top-level stage calls; sub-calls use `stage_tag`.

Five secondary corrections applied (RawRequest frozen construction, Intent.raw_request semantics, DRIFT-08 ownership, diagnostic scoping, Intent.raw_request docstring).

### Stress Test Results (Corrected)

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Can capabilities be added without Planner changes? | **YES** | Registry-based discovery. DRIFT-06 enforced. |
| 2 | Can new matching signals be added without changing CapabilityMatch contract? | **YES** | `evidence: Dict[str, Any]` is open. `relevance_score` is stable. Signal-extensibility invariant frozen. |
| 3 | Can language support evolve without Planner changes? | **YES** | Planner consumes Goal, not `RawRequest.detected_language`. |
| 4 | Can future milestones preserve single Goal authority? | **YES** | D1 frozen. DRIFT-04 enforced. |
| 5 | Can Planner and Supervisor share one recovery budget? | **YES** | Orchestrator creates single instance, threads to both. Integration test required. |
| 6 | Can a failure be traced from root cause to terminal? | **YES** | `trace_id` + `operation_id` + `caused_by` + `ImpasseRecord`. |
| 7 | Can `derived_from` and `caused_by` remain semantically distinct? | **YES** | Different types, different semantics, invariant frozen. |
| 8 | Can architecture drift be detected automatically? | **YES** | DRIFT-01 through DRIFT-09 with CI gate. |
| 9 | Can future sessions work independently after H2 freeze? | **YES** | Frozen contracts, change-control rules, drift gate. |

### Next Step

Give the next implementation session the **K4.2-H1 Implementation Specification** (§10 of this document) as its packet.

```
K4.2-H1 implementation
    ↓
H1 tests + 11-criterion acceptance gate
    ↓
H1 FREEZE
    ↓
K4.2-H2 implementation
    ↓
H2 tests + 9-criterion acceptance gate
    ↓
K4.2 v1.0 FREEZE
    ↓
PARALLEL FUTURE MILESTONES
```

---

**Repository status:** Read-only. No `.git` directory present (extracted archive). No files modified.
