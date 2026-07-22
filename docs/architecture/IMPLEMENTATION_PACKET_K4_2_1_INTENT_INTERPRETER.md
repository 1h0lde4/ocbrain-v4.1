# Implementation Packet: K4.2.1 Intent Interpreter

===========================================================
## 1. Mandatory Architecture Review
===========================================================
- **`PROJECT_INSTRUCTIONS.md`**: Supreme execution contract. Dictates Governance Before Capability, Event Sourcing, Isolation, Determinism, Local-First.
- **`OCBRAIN_KERNEL_CONSTITUTION.md`**: 11-law baseline for system integrity and governance.
- **`KERNEL_ARCHITECTURE_v1.0.md` & `ARCHITECTURE_CHANGELOG.md`**: Kernel history and context.
- **`OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` (K4)**: Defines core boundary: Cognitive Runtime reasons, Kernel executes.
- **`OCBRAIN_K4_1_FINAL_CONSOLIDATED_ARCHITECTURE.md` (K4.1)**: Cognitive Services and recursive Delegation; Policy vs. Mechanism split.
- **`OCBRAIN_K4_1_L_FINAL_LEARNING_ARCHITECTURE.md` (K4.1-L)**: Validation and promotion pipeline for learning.
- **`OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` (K4.2)**: Authoritative blueprint for K4.2.1 Intent Interpreter.

**Architecture Hierarchy & Dependencies**
K4.2 relies entirely on K4, K4.1, and K4.1-L boundaries, which are subordinate to `PROJECT_INSTRUCTIONS.md` and `OCBRAIN_KERNEL_CONSTITUTION.md`.

**Implementation Boundaries**
The Cognitive Runtime produces Cognitive Artifacts (`Intent`, `Goal`, `ExecutionPlan`). It never executes workflows, calls adapters directly, or writes directly to `UnifiedMemory`.

**Governance Boundaries**
`GovernanceKernel` is the sole authority for policy evaluation. The Cognitive Runtime does not evaluate its own policy.

**Learning Boundaries**
Learning produces `LearningCandidate`s (evidence), never self-executing rules.

**Replay & Determinism Rules**
Execution determinism is absolute. Normalization and inference must execute deterministically. All transitions must be deterministically reproducible via immutable event logs. Replays resolve memory lookups against active versions.

===========================================================
## 2. Future Compatibility Review
===========================================================
Review of `FUTURE_RESEARCH_VAULT.md` and `OCBRAIN_K5_FUTURE_COGNITIVE_EVOLUTION_ARCHITECTURE.md` complete. These are architectural constraints only.
Implementation must never conflict with them.

- Does implementation block future evolution? No.
- Does it duplicate future capabilities? No.
- Does it consume future responsibilities? No.
- Does it close extension points? No.
- Does it hard-code future assumptions? No.
- Does it introduce future architectural debt? No.

===========================================================
## 3. Repository Audit
===========================================================
Search for existing infrastructure before implementation:
- contracts: [Found | Location | Reuse/Extend/Replace/New | Reason]
- interfaces: [Found | Location | Reuse/Extend/Replace/New | Reason]
- abstractions: [Found | Location | Reuse/Extend/Replace/New | Reason]
- utilities: [Found | Location | Reuse/Extend/Replace/New | Reason]
- provider routing: [Found | Location | Reuse/Extend/Replace/New | Reason]
- retrieval: [Found | Location | Reuse/Extend/Replace/New | Reason]
- ontology lookup: [Found | Location | Reuse/Extend/Replace/New | Reason]
- embeddings: [Found | Location | Reuse/Extend/Replace/New | Reason]
- context assembly: [Found | Location | Reuse/Extend/Replace/New | Reason]
- governance: [Found | Location | Reuse/Extend/Replace/New | Reason]
- workflow runtime: [Found | Location | Reuse/Extend/Replace/New | Reason]
- UnifiedMemory: [Found | Location | Reuse/Extend/Replace/New | Reason]
- EventBus: [Found | Location | Reuse/Extend/Replace/New | Reason]
- registries: [Found | Location | Reuse/Extend/Replace/New | Reason]
- existing tests: [Found | Location | Reuse/Extend/Replace/New | Reason]

===========================================================
## 4. Architecture Drift Check
===========================================================
Compare architecture against repository. Report:
- missing implementations
- duplicate implementations
- obsolete implementations
- architecture violations

STOP if conflicts exist.

===========================================================
## 5. Evidence Rule
===========================================================
Every implementation decision must cite the architecture section that authorizes it.
"Best practice", "Clean architecture", "Future flexibility" are NOT valid evidence.

===========================================================
## 6. Implementation Scope
===========================================================
**Objective**: Implement K4.2.1 Intent Interpreter logic (Normalization and Inference) to convert `RawRequest` into `IntentHypothesis` objects.
**Architecture sections**: K4.2 §2, K4.2 §12, K4.2 §15, K4.1 §IV.
**Components**: Intent Interpreter normalization & hypothesis generation logic.
**Files**: `core/cognitive/__init__.py`, `core/cognitive/intent.py`, `tests/core/cognitive/test_intent.py`.
**Dependencies**: Existing retrieval and provider routing.
**Contracts**: `CognitiveArtifact`, `Intent`, `IntentHypothesis`.
**Events**: `cognitive.intent_hypotheses_generated`, `cognitive.intent_interpreted`.
**State changes**: Creates `Intent` artifact (in-memory).
**Governance review**: Only inferences are produced; no capabilities executed.
**Learning review**: Output does not bypass `ValidationGate`.

===========================================================
## 7. Implementation Order
===========================================================
1. Perform Repository Audit & Architecture Drift Check. (Commit)
2. Implement `CognitiveArtifact`, `Intent`, `IntentHypothesis` contracts exactly as specified in K4.2 §12. (Commit)
3. Implement deterministic input normalization utilizing existing utilities. (Commit)
4. Implement inference mapping reusing existing context assembly and provider routing. (Commit)
5. Integrate existing event emission for `cognitive.intent_hypotheses_generated` and `cognitive.intent_interpreted`. (Commit)
6. Write test suites. (Commit)

===========================================================
## 8. Test Plan
===========================================================
- **Unit**: Correct hypothesis mapping using fixed queries.
- **Negative**: Malformed inputs rejected before inference.
- **Replay**: Verify events contain metadata necessary to reconstruct state.
- **Determinism**: Identical inputs must yield identical hypothesis ordering and confidence scores.
- **Governance**: Ensure no execution bounds are crossed.
- **Regression**: Ensure no existing behavior is broken.
- **Future Compatibility**: Ensure no K5-reserved names/events are claimed.

===========================================================
## 9. Acceptance Criteria
===========================================================
- Architecture compliance verified.
- Governance compliance verified.
- Learning compliance verified.
- Replay compliance verified.
- Determinism compliance verified.
- No duplicated infrastructure.
- No invented abstractions.
- No invented contracts.
- No invented events.
- No invented registries.
- No hidden state.
- No runtime mutation.
- No architecture drift.

===========================================================
## 10. Architecture Clarification Rules
===========================================================
If implementation requires inventing anything because architecture is incomplete, implementation MUST STOP.
Generate an Architecture Clarification Report. Never guess. Never invent.

===========================================================
## 11. Architectural Self Audit
===========================================================
- Which architecture sections were implemented?
- Which contracts were implemented?
- Which files changed?
- Which files were created?
- Which assumptions were made?
- Which assumptions require clarification?
- Were architectural decisions invented?
- Were abstractions duplicated?
- Were future extension points closed?
- Were future documents reviewed?
- Does implementation conflict with Future Research Vault?
- Does implementation conflict with K5?
- Does implementation introduce technical debt?
- Does implementation remain compatible with future evolution?

===========================================================
## 12. Claude Implementation Handoff
===========================================================
**Authorized files**: `core/cognitive/__init__.py`, `core/cognitive/intent.py`, `tests/core/cognitive/test_intent.py`.
**Forbidden files**: Existing execution logic, `UnifiedMemory`, `GovernanceKernel`.
**Out-of-scope items**: Goal Formation, Planning, Kernel modifications, K5 features.
**Verification commands**: `pytest tests/core/cognitive/test_intent.py`, type checking tools.
**Required commits**: Atomic commits after every step in Section 7.
**Completion checklist**: Self Audit passing, tests passing, no architectural drift or invention.
