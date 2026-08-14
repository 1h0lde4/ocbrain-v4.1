# K4.2 Dynamic Cognitive Pipeline — Contract, Evolution, Parallel-Milestone & OCBrain Diagnostic Architecture Specification

**Repository audited:** `github.com/1h0lde4/ocbrain-v4.1` @ `main` (HEAD `2778b26`, unchanged — verified clean before and after this audit)
**Audit type:** Read-only architectural study. No files modified, no branches created, no commits made.
**Author role:** Principal Architect / Systems Integration Lead / Reliability Architect, per session task specification
**Date:** August 14, 2026

**Evidence key used throughout this document:**

| Tag | Meaning |
|---|---|
| **[FACT]** | Directly observed in the repository during this session (file:line cited) |
| **[ARCH]** | Explicitly stated by an authoritative architecture document (section cited) |
| **[AUDIT]** | Established by a prior audit — either re-derived independently this session, or, where the original report artifact was not itself found in the repository, carried forward from project history and flagged as such |
| **[INFER]** | Derived logically by this document from FACT/ARCH/AUDIT evidence |
| **[REC]** | A new design proposal made by this document — not yet an architectural decision |

No recommendation in this document is presented as an already-made architecture decision. Where documentation, implementation, and tests disagreed, the disagreement is stated explicitly rather than silently resolved.

**Contents:** [1](#1-executive-decision) Executive Decision · [2](#2-verification-of-the-supplied-audits) Verification of Supplied Audits · [3](#3-verified-current-k42-architecture) Verified Current Architecture · [4](#4-current-weak-links-and-failure-paths) Weak Links & Failure Paths · [5](#5-architectural-principles) Architectural Principles · [6](#6-semantic-ownership-model) Semantic Ownership Model · [7](#7-canonical-cognitive-contracts) Canonical Contracts · [8](#8-contract-ownership-matrix) Ownership Matrix · [9](#9-capability-discovery-architecture) Capability Discovery · [10](#10-capabilitymatch-contract) CapabilityMatch · [11](#11-internationalization-architecture) i18n · [12](#12-impasse--recovery-architecture) Impasse & Recovery · [13](#13-supervisorworker-contract) SupervisorWorker · [14](#14-intent-ontology-lifecycle) Intent Ontology · [15](#15-canonical-construction-rules) Canonical Construction · [16](#16-contract-versioning--migration) Contract Versioning · [17](#17-ocbrain-diagnostic--failure-architecture) Diagnostic Architecture · [18](#18-failure-taxonomy-and-reason-code-model) Failure Taxonomy · [19](#19-failurerecord-contract) FailureRecord · [20](#20-failure-correlation--causality) Correlation & Causality · [21](#21-diagnostic-event-architecture) Diagnostic Events · [22](#22-k42-diagnostic-integration) K4.2 Integration · [23](#23-boundary-contract-matrix) Boundary Matrix · [24](#24-architecture-invariants) Invariants · [25](#25-test-architecture) Test Architecture · [26](#26-mocking-policy) Mocking Policy · [27](#27-observability) Observability · [28](#28-performance--scalability) Performance · [29](#29-security--reliability) Security · [30](#30-parallel-milestone-development-architecture) Parallel Milestones · [31](#31-milestone-ownership--dependency-matrix) Milestone Matrix · [32](#32-contract-change-control-protocol) Change Control · [33](#33-integration-gate) Integration Gate · [34](#34-k42-vs-post-kernel-boundary) K4.2 vs Post-Kernel · [35](#35-implementation-phases) Implementation Phases · [36](#36-parallel-safe-implementation-packets) Packets · [37](#37-future-claude-session-guardrails) Session Guardrails · [38](#38-final-acceptance-checklist) Acceptance Checklist · [39](#39-architecture-freeze-definition) Freeze Definition · [40](#40-final-verdict) Final Verdict · [41](#41-supplementary-recommendations-beyond-the-original-task-scope) Supplementary Recommendations

---

# 1. Executive Decision

**[REC]** This specification's central recommendation, in one sentence: *fix the two proven defects at their true root cause (a broken single-source invariant for task semantics, and a single-signal capability-matching function), and use that same repair pass to stand up the minimal OCBrain-wide Diagnostic & Failure substrate — because the repair itself is the clearest evidence yet of exactly the failure-observability gap that substrate exists to close.*

Five things are decided here, subject to Moncif's review (none of these are self-executing — this is a specification, not a patch):

1. **K42-001 and K42-002 are both confirmed, both real, and both independent** — re-verified from first principles against the live repository this session, with an exact token-level reproduction of K42-002 against all five required test queries (§4).
2. **The fix is not a rename and not a threshold change.** `structured_form["description"]` already occupies the "one authoritative semantic representation" role the architecture wants — it is simply populated from the wrong field. `_capability_match_score`'s `min_score=0.01` gate at the `_decompose()` call site is *already* the correct, deliberate design (distinguishing "no signal" from "weak signal") — the defect is that the *only* signal available is lexical overlap, which is structurally unable to produce a nonzero score for short, generic, or non-English queries against any real-world capability description. Both defects are fixed by *strengthening what already exists*, not by introducing new types or lowering gates (§6, §9).
3. **A minimal Diagnostic & Failure substrate belongs in K4.2 now**, not after, because K4.2's own repair work is already three confirmed instances of the class of problem this substrate exists to prevent: an event the architecture specifies but the code never emits (`cognitive.planner_impasse`, §4.6), a failure path with only a free-text string for a reason (`ImpasseRecord.reason`, `CompilationResult.precheck_errors`), and a recovery worker (`SupervisorWorker`) that is architecturally positioned for exactly this class of failure but has zero wiring to it today (§4.7–4.8).
4. **This repository already contains most of the raw material the Diagnostic System needs** — a request-scoped, async-safe correlation primitive (`core/observability/tracer.py`), a durable, replayable event backbone (`EventStream`), and a governance-decision log shape (`CognitiveDecision`) that already covers one entire branch of the proposed failure taxonomy. The correct design reuses all three. Building a fourth event mechanism would repeat a mistake the project has already tracked against itself twice (DEBT-004, DEBT-005 — §4.9).
5. **Parallel-milestone safety is achievable with the project's existing nine-step packet discipline, extended by four new required fields** (contracts consumed/extended/frozen, diagnostic integration requirements) — not a new process (§30–33).

---

# 2. Verification of the Supplied Audits

Three distinct prior-work artifacts are in play for this session, and they are not the same document. Conflating them would misattribute evidence, so they are kept separate here.

## 2.1 The K42-001 / K42-002 impasse investigation

**[AUDIT]** Per project history, a prior session performed a read-only audit that independently verified two defects (K42-001: `structured_form["description"]` set to a hypothesis label instead of the actual request text; K42-002: Jaccard token-overlap capability scoring returns 0.0 for realistic phrasings) and proved them independent of each other via compound-request reproduction. A repository-wide search this session for the literal strings `K42-001`, `K42-002`, `Jaccard` + `Independent Verification`, and a file named anything resembling `OCBrain_K4.2_Independent_Verification_Report.md` returned **no committed artifact** — the report itself was apparently never committed, only its conclusions carried forward. **This is stated plainly rather than silently assumed either way.**

Rather than treat this as a blocking gap, this session independently re-derived both defects from the live repository from first principles (§4.1–4.2), including a full token-level reproduction of K42-002 against the actual registered `LLM_COMPLETION` capability text and all five required test queries. **Both defects are now [FACT], not merely [AUDIT]** — the original finding is confirmed by fresh, independent evidence, not merely trusted.

## 2.2 `docs/architecture/k4_2_architecture_hardening_review.md`

**[FACT]** This file exists in the repository (dated July 24, 2026) and is the only document matching "K4.2 architectural review" found in the repository. It is **not** the K42-001/K42-002 investigation. It is a fourteen-concept architecture-hardening pass (Cognitive Session, Transaction Boundary, Artifact Versioning, Confidence Provenance, Planner Search Budget, Cancellation Semantics, Intent Stability, Discovery Caching, Reflection Boundary, Reasoning Evidence, Cognitive Snapshot, Evolution Simulation, Cognitive Invariants, K5 Forward Compatibility) that rejected twelve proposed concepts as already covered by existing mechanisms and accepted two minimal clarifications (Confidence Provenance and Intent Immutability After Interpretation), both already merged into the authoritative K4.2 document. **It does not mention impasse, Jaccard, `structured_form`, or either K42 defect at all** — confirmed by direct grep of the file. It is treated here as **[ARCH]**-grade prior work (its two accepted clarifications are load-bearing for §6 and §14 below) but is **not** the "existing K4.2 Dynamic Cognitive Pipeline review" this session's task brief describes as its primary input.

## 2.3 This session's own Phase 0 audit

**[FACT]** Everything else in this document not otherwise attributed is this session's own direct repository reading: `core/cognitive/intent.py`, `planner.py`, `compiler.py`, `learning.py`, `user_model.py`; `core/capabilities/capability.py`, `registry.py`; `core/workers/supervisor.py`, `capability_executor.py`, `base.py`; `core/orchestrator.py`; `core/governance/governance_kernel.py`; `core/events/event_stream.py`; `core/observability/tracer.py`; `core/meta/self_model.py`; `main.py`; `OCBRAIN_KERNEL_CONSTITUTION.md`; `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md`; `docs/architecture/OCBRAIN_K4_1_L_FINAL_LEARNING_ARCHITECTURE.md`; `docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`; `CURRENT_STATE.md`; `KNOWN_ISSUES.md`; `IMPLEMENTATION_ROADMAP.md`; `docs/architecture/IMPLEMENTATION_PACKET_TEMPLATE.md`. `git status --short` was clean at the start and end of the session; no file was modified.

---

# 3. Verified Current K4.2 Architecture

**[FACT]** All nine K4.2 packets, per `CURRENT_STATE.md` (last synchronized Aug 12, 2026) and confirmed by direct code reading this session, are complete and live behind a feature flag:

| # | Milestone | File(s) | Confirmed this session |
|---|---|---|---|
| 1 | K4.2.1 Intent Interpreter | `core/cognitive/intent.py` | `Intent`, `IntentHypothesis`, `CognitiveArtifact` Protocol, `interpret_request()` |
| 2 | K4.2.2 Goal Formation | `core/cognitive/intent.py` | `Goal`, `form_goals()`, compound-split via `_split_compound_goals()` |
| 3 | K4.2.3 Constraint Extraction + Planner Contracts | `core/cognitive/planner.py` | `Constraint`, `PlannerRequest`, `PlannerHint`, `PlannerResult`, `_extract_constraints()` |
| 4 | K4.2.4 Capability Discovery | `core/cognitive/planner.py` | `CapabilityDiscoveryRequest`, `discover_capabilities()`, `_capability_match_score()` (Jaccard) |
| 5 | K4.2.5 Planner Completion | `core/cognitive/planner.py` | `ClarificationPolicy`, `ExecutionPlan`, `_decompose()`, `_detect_impasse()`, `plan()` |
| 6 | Plan Compilation | `core/cognitive/compiler.py` | `CompilationResult`, `compile()`, ExecutionPlan→WorkflowDefinition |
| 7 | K4.2.6 Shared ValidationGate + Learning | `core/cognitive/learning.py` | `validation_gate()`, `LearningTier`, `ContentDomain`, `LearningRecord` |
| 8 | K4.2.7 User Cognitive Model | `core/cognitive/user_model.py` | `assemble_user_cognitive_model()` |
| 9 | Reflection + Evaluation + Supervisor | `core/workers/{evaluator,reflection,supervisor}.py` | `EvaluatorWorker`, `ReflectionWorker`, `SupervisorWorker` |

**[FACT]** Runtime wiring (`core/orchestrator.py:242-419`): a feature flag `use_k42_frontend` (default `False`, `config/settings.toml` key `[runtime] use_k42_frontend`) gates a branch inside `Orchestrator.handle()`. When `False`, execution is byte-for-byte the legacy K2.2 `PlannerWorker` path — the K4.2 branch is not entered at all. When `True`:

```text
query
  │
  ▼
interpret_request(query, memory, event_stream)   core/cognitive/intent.py
  │  → List[Goal]  (only goals[0] used — multi-goal execution is a
  │                 confirmed-intentional deferral, CURRENT_STATE.md)
  ▼
plan(PlannerRequest(goal), capability_registry)  core/cognitive/planner.py
  │  → PlannerResult{status, execution_plan | impasse_detail}
  │
  ├─ status == IMPASSE ─────────────► apology returned directly to user
  │                                    (no SupervisorWorker call, no event
  │                                     beyond generic orchestrator.query_failed)
  │
  ▼ status == READY_FOR_COMPILATION
compile(execution_plan, governance)              core/cognitive/compiler.py
  │  → CompilationResult{status, workflow_definition | governance_result | precheck_errors}
  │
  ├─ status != COMPILED ────────────► SupervisorWorker.invoke() (surfacing only,
  │                                    never retries — K4 §16 invariant 9)
  │                                    + orchestrator.query_failed event
  │
  ▼ status == COMPILED
WorkflowRuntime.execute(workflow_definition)
  │  → wf_result.output
  ▼
EvaluatorWorker.invoke() → EvaluationRecord
  ▼
ReflectionWorker.invoke()
  │
  ▼
memory.write(...) + context.save(...)  [Aug 12 bug-hunt fix — see §4.9]
  ▼
orchestrator.query_completed event → answer returned
```

**[FACT]** `CapabilityExecutorWorker` (`core/workers/capability_executor.py`) is the `WorkflowNode.worker_type → AdapterRuntime.invoke()` bridge that makes a compiled `WorkflowDefinition` executable — deliberately narrow, single-step dispatch only, no capability *selection* logic of its own.

**[FACT]** Only one `CapabilityType` has a registered `CapabilityContract` + live adapters: `LLM_COMPLETION`, registered in `main.py:262-279` with `description="Generate text from a prompt via a language model."` and three adapters (`ModelRouterAdapter`, `OllamaAdapter`, `OpenAICompatAdapter`). Nine further types (`EMBEDDING`, `WEB_SEARCH`, `BROWSER_AUTOMATION`, `FILE_ACCESS`, `MEMORY_SEARCH`, `GRAPH_TRAVERSAL`, `IMAGE_GENERATION`, `TOOL_INVOCATION`, `EXTERNAL_API`) are declared as string constants but not registered — `core/capabilities/capability.py:69-78`. This matters directly for §9 and §43: today's capability-discovery problem is a **degenerate single-candidate case**, not yet a many-capability ranking problem.

---

# 4. Current Weak Links and Failure Paths

## 4.1 K42-001 — Goal Formation discards the user's actual request

**[FACT]** `core/cognitive/intent.py:566-570`, inside `_validate_structured_form()`:

```python
structured_form: Dict[str, Any] = {
    "description": intent.selected.label if intent.selected else "unknown",
    "category": category,
    "raw_request": intent.raw_request,
}
```

`intent.selected` is an `IntentHypothesis`; `.label` is a short classification-style label produced by hypothesis generation (`_parse_hypotheses`, `_build_hypothesis_prompt`), not the request text. `intent.raw_request` — the actual text — sits one line below, unused for `description`. This is the sole call site for single (non-compound) requests: `form_goals()` (line 662) calls `_validate_structured_form()` and uses its output as-is unless the request was split into more than one part (line 668-670), in which case — and *only* in which case — `structured_form["description"]` is overwritten with `part_text`, the real sub-request text. **The fix already exists in the codebase, for exactly one of the two cases it needs to cover.**

**[FACT]** All five required test queries (`"Hello"`, `"What is 2 + 2?"`, `"List the available capabilities."`, `"What can you do?"`, `"Explain what OCBrain is."`) are single, non-compound requests — `_split_compound_goals()`'s separator pattern (`and then|then|after that|also|additionally`) does not match any of them, so `len(parts) == 1` for all five, and none of them ever reach the corrective branch.

## 4.2 K42-002 — Capability Discovery's Jaccard scoring, reproduced exactly

**[FACT]** `_capability_match_score()` (`planner.py:617-636`) is pure Jaccard similarity — `|tokens_a ∩ tokens_b| / |tokens_a ∪ tokens_b|` — over lowercase alphanumeric tokens (`_tokenize`, line 609-614) minus a fixed stopword set (line 603-606), comparing `CapabilityDiscoveryRequest.description` against `CapabilityContract.description`. No other signal exists. This is not an oversight — the function's own docstring states no scoring formula is architecture-mandated and this one was chosen for being simple, deterministic, and auditable, matching the same style already used for constraint extraction. **The formula is a reasonable implementation choice; the problem is that it is the *only* choice.**

**[FACT]** `_decompose()` (`planner.py:936-938`) calls `discover_capabilities(..., min_score=0.01)` — deliberately *not* `discover_capabilities`'s own permissive default of `0.0` — specifically so a capability with literally zero token overlap (no relevance signal at all) is excluded from candidates, while `discover_capabilities()`'s own default caller-facing behavior (rank, don't filter) is left untouched for other callers. This gate is the correct, deliberate design described in K4.2 §5/§14's "no matching capability" semantics, not a bug. **Lowering it would not fix K42-002 — it would defeat the exact distinction the comment at `planner.py:921-935` explains it exists to preserve** (see §9.4, §29).

**Independent reproduction, this session, against the real registered contract** (`main.py:264`: `description="Generate text from a prompt via a language model."`):

Contract tokens after stopword removal: `{generate, text, prompt, language, model}` (`a`, `from`, `via` are stopwords).

| Required test query | Query tokens (post-stopword) | ∩ with contract | Jaccard score | Passes `min_score=0.01`? |
|---|---|---|---|---|
| `"Hello"` | `{hello}` | `{}` | **0.0** | No → impasse |
| `"What is 2 + 2?"` | `{what, 2}` (`is` is a stopword) | `{}` | **0.0** | No → impasse |
| `"List the available capabilities."` | `{list, available, capabilities}` | `{}` | **0.0** | No → impasse |
| `"What can you do?"` | `{what, can, you, do}` | `{}` | **0.0** | No → impasse |
| `"Explain what OCBrain is."` | `{explain, what, ocbrain}` (`is` is a stopword) | `{}` | **0.0** | No → impasse |

Every one of the five required queries scores exactly `0.0` against the only real capability in the system, independent of K42-001 (this reproduction used the queries directly as `CapabilityDiscoveryRequest.description`, not via the broken Goal path). **K42-001 and K42-002 are independently, mechanically confirmed to both cause impasse on all five required queries, individually.**

## 4.3 A real class-name collision compounds the semantic-ownership problem

**[FACT]** `planner.py:544-563`: the K4.2 discovery-time parameter object was originally specified by architecture as `CapabilityRequest`, colliding with the pre-existing K2.3 execution-time type `core.capabilities.capability.CapabilityRequest` (`capability_type, payload, trace_id, metadata` — the input to one `Adapter.execute()` call). Already resolved by renaming the newer type to `CapabilityDiscoveryRequest` (documented July 25, 2026 architecture correction, `k4_2_4_completion_report.md`). This is *not* open — it is included here because it is direct, first-party evidence that the project has already had to relearn, once, exactly the lesson §15–16 of this document formalizes: two unrelated concepts sharing one name is a semantic-ownership failure independent of whether either concept's own logic is correct.

## 4.4 `CapabilityRegistry.resolve()` does not exist

**[FACT]** K4.1 Part III's prose describes capability selection happening "via the Kernel's existing `CapabilityRegistry.resolve()`, unmodified." **[FACT]** The actual class (`core/capabilities/registry.py`) has no `resolve()` method — its public surface is `register_capability`, `register_adapter`, `get_contract`, `get_adapters`, `list_capabilities`, `validate`, `stats`. A repository-wide search for `CognitiveServiceRegistry`/`ServiceRegistry` returns zero results. **[INFER]** K4.1 Part III describes a registry API and a second registry ("CognitiveService Registry") that were never implemented — this is an aspirational reference in an architecture document that predates the actual `CapabilityRegistry` implementation, already flagged once by the K4.2.4 completion report as "Not Applicable," not silently worked around.

## 4.5 The Intent Ontology has a write path with no wired production read path

**[FACT]** `interpret_request()` accepts `known_categories: Optional[List[str]] = None` (`intent.py:712`), threaded through to `_build_hypothesis_prompt()` (line 449) where it is described as representing "the Intent Ontology's current L3 entries" (line 432). **[FACT]** The one production call site — `core/orchestrator.py`'s K4.2 branch, line 271-272 — calls `interpret_request(query, memory=self.memory, event_stream=self._event_stream)` **without** `known_categories=`. It therefore always defaults to `None` → `[]`, and `_build_hypothesis_prompt` always renders `"(none yet)"` for the category list in production, regardless of how many categories the Intent Ontology has actually promoted via `validation_gate(content_domain=ContentDomain.INTENT_ONTOLOGY, ...)` (`learning.py`). **A fully-built write path (learning → validation_gate → promoted `LearningRecord`) feeds a read path that is never actually called.**

## 4.6 `cognitive.planner_impasse` is specified but never emitted

**[ARCH]** K4.2 §11's event-reconciliation table (line 307) states `cognitive.planner_impasse` is "**New** — emitted on `PlannerResult.status == "impasse"`." **[FACT]** `plan()` (`planner.py:1183-1185`):

```python
impasse = _detect_impasse(steps_with_candidates)
if impasse is not None:
    return PlannerResult(status=PlannerStatus.IMPASSE, impasse_detail=impasse)
```

No `event_stream.append(...)` call exists on this path, or anywhere else in `_detect_impasse()` or `plan()`. Every impasse is invisible to `EventStream` — the one place a durable, replayable, correlatable record of *why the system couldn't act* should exist, doesn't.

## 4.7 Planner impasse is architected as recoverable, implemented as terminal

**[ARCH]** K4.2 §14's Failure Handling table, verbatim: "Planner impasse (`status: "impasse"`) | Soar-derived impasse→subgoaling (K4.2-R §4.9) — routes through Capability Discovery and, if nothing resolves it, Skill Runtime delegation (K4.1 §9)."

**[FACT]** No `Skill` or `SkillRuntime` class exists anywhere in the repository — confirmed independently this session and already noted by `_detect_impasse()`'s and `_decompose()`'s own docstrings as a "documented gap, not silently treated as fully resolved." **[FACT]** `core/orchestrator.py:280-287`: on `PlannerStatus.IMPASSE`, the K4.2 branch emits one generic `orchestrator.query_failed` event and returns `"Sorry, I could not form a plan for this request: {status}"` directly to the user — no re-attempt through Capability Discovery, no `SupervisorWorker` invocation (contrast with `CompilationStatus != COMPILED`, which *does* invoke `SupervisorWorker`, lines 297-304). **[INFER] This is a direct, confirmed contradiction between an authoritative architecture document (§14) and the shipped implementation** — not a matter of interpretation. It is stated here rather than silently resolved in either direction, per this document's evidence-first mandate.

## 4.8 SupervisorWorker has zero wiring to Planner impasse

**[FACT]** `core/workers/supervisor.py:165-217`: `SupervisorWorker._run()` has exactly two input paths — `context.parameters["compilation_result"]` (a `CompilationResult`; classified by `_classify_compilation_outcome()` into `ESCALATED`/`REJECTED`/`None`) and `context.parameters["failed_worker_result"]` (bounded retry via `ExecutionRuntime.invoke()`, `max_supervisor_retries` default 1). **Neither path accepts an `ImpasseRecord` or `PlannerResult`.** Combined with §4.7, this means: today, a Planner impasse is invisible to the one worker whose entire purpose is reacting to cognitive-pipeline failures.

## 4.9 Diagnostic primitives are thin; failure fields are free text throughout

**[FACT]** `core/observability/tracer.py` (99 lines) provides exactly one thing usable here: an async-safe, `ContextVar`-based `trace_id` (`get_trace_id()`/`set_trace_id()`) plus a `span()` timing context manager. No failure taxonomy, no severity, no structured record, no causality chain exists anywhere in the repository.

**[FACT]** Every failure-shaped field encountered this session is an untyped string, not a code from any shared taxonomy: `ImpasseRecord.reason: str` (free text, `planner.py:186`), `CompilationResult.precheck_errors: List[str]` (`compiler.py:122`), and `core/orchestrator.py`'s own ad hoc `"error_type": "PlannerImpasse"` / `"CompilationRejected"` / `type(e).__name__` strings (lines 284, 308, 416) — three different call sites inventing three different informal naming conventions for the same concept.

**[FACT]** Three parallel event-shaped mechanisms already coexist, and the project has already tracked this against itself twice: **DEBT-004** ("`KnowledgeEvent`/`EventStream` duality... a consumer wanting a complete timeline must query both") and **DEBT-005** ("`EventBus`/`EventStream` relationship... Three event mechanisms total... Event infrastructure fragmentation"), both in `KNOWN_ISSUES.md`. `StreamEvent` (`core/events/event_stream.py`) uses a `payload: Dict[str, Any]` field and is the durable WAL; `KnowledgeEvent` (`core/memory/knowledge_event.py`) uses a `metadata=` field and writes to the L4 Archive; `EventBus` (`core/event_bus.py`) is in-process pub/sub with no persistence. **A fourth, diagnostic-specific transport would make this a tracked debt item into a tracked pattern** — §17.4/§21 build directly against `EventStream`, reusing the existing `payload` shape, specifically to avoid this.

**[FACT] Directly relevant precedent for the Diagnostic System's `GOVERNANCE_OUTCOME` class:** K4.2 §12 already defines `CognitiveDecision` — "the shared shape logged at ANY GovernanceKernel evaluation... `action_type: str, subject_ref: str, verdict: "proceed"|"reject"|"escalate", reason: str, evaluated_at: timestamp`." This already *is* a structured failure/outcome record for governance verdicts specifically. §19 below treats it as a producer to wrap, not a pattern to duplicate.

**[FACT] A directly cautionary precedent for the new Recovery Budget (§12):** `KNOWN_ISSUES.md` **DEBT-007** — `BudgetGovernor`'s evaluation logic is confirmed correct and its metadata plumbing confirmed wired end-to-end, but no code anywhere in the repository ever increments `step_count`/`token_spend`, so the REJECT branch is "logically correct but currently unreachable in any production path." **This is the exact failure mode a new Recovery Budget must not repeat** — a governance-shaped mechanism whose enforcement path is correct but structurally dead because nothing feeds it real numbers.

## 4.10 `LearningRecord`/`content_domain` contradicts `LearningCandidate`/`domain` in a higher-precedence document

**[ARCH]** `docs/architecture/OCBRAIN_K4_1_L_FINAL_LEARNING_ARCHITECTURE.md` (line 19): "the learning surface is generalized: any cognitive component may emit a `LearningCandidate`... through one explicit contract — **not six named, implicitly closed categories**." Its `domain` field is explicitly open-ended (line 145: "the Kernel's ontology is never a fixed enum").

**[ARCH]** `docs/architecture/OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md` §12 (line 362-366) instead specifies `LearningRecord` with `content_domain: str`.

**[FACT]** The actual implementation (`core/cognitive/learning.py`) builds exactly what K4.2 §12 specifies — `class LearningRecord`, and `class ContentDomain: SKILL = "skill"; INTENT_ONTOLOGY = "intent_ontology"; USER_MODEL = "user_model"; ALL = (SKILL, INTENT_ONTOLOGY, USER_MODEL)` — a **closed, three-value enum**, the exact "implicitly closed categories" pattern K4.1-L's own text names and rejects.

**[INFER]** Per the authoritative document precedence order (memory: K4.1-L ranks *above* K4.2 Cognitive Front-End), a strict reading would have the open-domain `LearningCandidate` model win — yet the shipped, tested implementation follows the lower-precedence document. This is a real contradiction between two authoritative documents, not a documentation typo, and is carried forward unresolved into §16.2 rather than silently picked one way or the other.

---

# 5. Architectural Principles

**[REC]** The fourteen principles from this task's own framing (§60) are adopted, each tied here to the specific Constitution Law or Invariant that already requires it — none of these are new obligations, only the first time they are named as a set:

| Principle | Constitution grounding |
|---|---|
| Semantic preservation — raw request never replaced by classification data | **Law 9** (Single Source of Truth); Invariant 1 |
| Single source of truth per semantic concept | **Law 9**; the entire premise of §6 below |
| Derived views are not independent authorities | Law 9 + Law 4 (Determinism) |
| Dynamic capability discovery — no Planner-specific routing code per capability | Law 7 (Replaceability) |
| Capability vs. adapter separation | Law 7; already the K2.3 Registry/Runtime split |
| Language as metadata/compatibility, not primary router | Law 4 (Determinism — routing must not vary by incidental phrasing) |
| Schema-aware direction, even if matching is initially limited | Law 6 (Explainability) — a contract that exists but isn't fully enforced is still more explainable than no contract |
| Reason-driven recovery, not threshold-lowering | Law 4 + Law 8 (Evidence over Assumption) |
| Single recovery authority/budget | **Law 1** (Bounded Autonomy) |
| Governance separation — Intent/Planner never acquire governance authority | **Law 1**; already enforced structurally in `SupervisorWorker._surface_compilation_outcome()` |
| Diagnostic substrate: structured, correlated, causal, observable | **Law 2** (Explicit State) + **Invariant 5** ("information that crosses a kernel boundary is represented as an event") |
| Contract validation fails early and visibly | Law 2 + Law 6 |
| Parallel safety — extend, never silently redefine | **Law 9** applied across sessions, not just within one |
| Canonical construction — one path per shared contract | Law 9; already the pattern `build_planner_request()`/`build_capability_discovery_request()` establish |

All fourteen are already implied by the nine ratified Laws — this document does not add new laws, only makes their K4.2-specific consequences explicit and testable (§24).

---

# 6. Semantic Ownership Model

## 6.1 The finding that reframes this whole section

**[INFER]** The instinct going into this task was that `description` is "overloaded" and needs splitting into three independent representations (authoritative / discovery / execution). Having now read the actual data flow, that is not quite what the evidence shows. What the evidence shows:

```text
Goal.structured_form["description"]      ← THE authoritative field, already
        │                                    single-sourced by design
        │  (build_capability_discovery_request, planner.py:593 — a bare,
        │   read-only pass-through: .get("description", ""))
        ▼
CapabilityDiscoveryRequest.description    ← already a pure derived view
        │
        │  (_decompose, planner.py:896-897 — feeds an LLM decomposition
        │   prompt, whose output becomes each PlanStep.description)
        ▼
PlanStep.description                      ← already a derived view,
                                             one step further downstream
```

**The "one authoritative representation → derived consumer views" shape §15/§16 of the task brief asks for is already how this code is built.** `build_capability_discovery_request()` does not have its own idea of what the task is — it reads `goal.structured_form["description"]` and nothing else. The defect (§4.1) is not that discovery independently decided to use a hypothesis label; it is that the *authoritative field itself* was populated from the wrong source, and nothing in the codebase — no test, no contract, no invariant — protects that population from regressing.

**[REC]** Therefore this document does **not** recommend introducing new types (no `TaskSemantics`, no three-way Goal split). It recommends:

1. Fix the population at its one true source (`_validate_structured_form`, `intent.py:566-570`): `"description": intent.raw_request` unconditionally (dropping the `intent.selected.label if ... else "unknown"` branch entirely — it has no correct use here; `raw_request` is always available on a constructed `Intent`).
2. Unify the now-redundant compound-request special case (`form_goals`, line 668-670) — once the source itself is fixed, the compound path's separate overwrite becomes exactly what per-part substitution already looks like: `structured_form["description"] = part_text` instead of `intent.raw_request`, applied uniformly, single code path, no special case.
3. **Add the missing guardrail**: a contract-level invariant test (K42-S01, §24) asserting `Goal.structured_form["description"]` is always a substring-traceable derivative of `Intent.raw_request` (or one of `_split_compound_goals()`'s own parts) and is never equal to any `IntentHypothesis.label` in `Intent.hypotheses` unless the two happen to be identical text. This is what was missing, not a new field.

This is the single most consequential judgment call in this document: **the semantic-ownership problem here is a missing invariant guard, not a missing architecture.** The corollary is that Architecture Freeze (§39, PROJECT_INSTRUCTIONS §20.5) is respected, not violated — this is "a verified defect" and "eliminates ambiguity," the two conditions PROJECT_INSTRUCTIONS §20.5 itself requires for a freeze-compatible change, and nothing about `Goal`'s shape needs to change.

## 6.2 Field-level authority table

| Field | Authority | Producer | Consumers | Derivation | Mutable after creation? |
|---|---|---|---|---|---|
| `Intent.raw_request` | **Authoritative source** | `interpret_request()` (from `RawRequest.text`) | Everything downstream | None — this *is* the source | No (Intent immutable after `interpreted`, per §6.3 below) |
| `Goal.structured_form["description"]` | Derived, single-sourced | `_validate_structured_form()` / `form_goals()` | `build_capability_discovery_request()`, `_decompose()` | `intent.raw_request` (whole) or one `_split_compound_goals()` part | No (new `Goal` per re-interpretation) |
| `CapabilityDiscoveryRequest.description` | Pure pass-through view | `build_capability_discovery_request()` | `discover_capabilities()`, `_capability_match_score()` | `goal.structured_form["description"]`, unmodified | N/A — ephemeral parameter object |
| `PlanStep.description` | Derived view, one hop further | `_decompose()` | Execution / `CapabilityExecutorWorker` | LLM decomposition of `goal.structured_form["description"]` | No (new `ExecutionPlan` per re-plan) |
| `Intent.dimensions.category` | Authoritative classification | Hypothesis inference | `_validate_structured_form()` (schema lookup key), `build_planner_request()` (hint generation) | Model output, constrained to `known_categories` ∪ `"novel"` | No |
| `IntentHypothesis.label` | Authoritative *only for ranking hypotheses* | Hypothesis inference | Intent selection logic, `Goal.alternatives` | Model output | No — **never** a valid source for `description` (this is the entire content of the K42-001 fix) |

## 6.3 Confirmed-compatible clarifications already merged

**[ARCH]** Two clarifications from `k4_2_architecture_hardening_review.md` are already load-bearing for this model and are treated here as settled, not re-litigated: (1) an `Intent` that has reached `interpreted` is immutable — reinterpretation creates a successor via `derived_from`, never an in-place mutation; (2) confidence adjustments are traceable through the existing `derived_from` + event-correlation mechanism, not a dedicated confidence-provenance structure. Both directly support §6.1's "fix the source, don't add new mechanism" conclusion.

---

# 7. Canonical Cognitive Contracts

**[REC]** Target-state contracts. Fields marked **(new)** are additive — every existing field, type, and call site is unchanged; this is extension, not redesign, consistent with §39's freeze rules.

```text
                              USER REQUEST
                                    │
                                    ▼
                       ┌───────────────────────┐
                       │  INPUT NORMALIZATION   │
                       │  RawRequest.text        │
                       │  RawRequest.language(new)│  ← §11
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │        INTENT          │
                       │ hypotheses, selected    │
                       │ dimensions.category     │
                       │ dimensions.detected_    │
                       │   language (new) — §11  │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │   AUTHORITATIVE GOAL    │
                       │ structured_form:        │
                       │   description ◄── ALWAYS│
                       │     intent.raw_request   │
                       │     or a compound part   │
                       │     (never a hypothesis  │
                       │     label — K42-S01)     │
                       │ confidence, constraints  │
                       └─────────┬─────────┬─────┘
                                 │         │
                     (read-only view)   (read-only view)
                                 ▼         ▼
                    ┌──────────────┐  ┌──────────────┐
                    │ DISCOVERY    │  │ EXECUTION    │
                    │ VIEW          │  │ VIEW (PlanStep│
                    │ (Capability-  │  │ .description) │
                    │  Discovery    │  └──────┬───────┘
                    │  Request)     │         │
                    └──────┬───────┘         │
                           ▼                  │
                  ┌──────────────────┐        │
                  │ CAPABILITY        │        │
                  │ DISCOVERY         │        │
                  │  signals (§9):    │        │
                  │   lexical (kept)  │        │
                  │   aliases (new)   │        │
                  │   domain_tags(new)│        │
                  │   general_purpose │        │
                  │     flag (new)    │        │
                  │   schema (future) │        │
                  └──────┬───────────┘        │
                         ▼                     │
                  ┌──────────────┐             │
                  │CapabilityMatch│  §10        │
                  │ evidence[]    │             │
                  └──────┬───────┘             │
                         └─────────┬───────────┘
                                   ▼
                             ┌───────────┐
                             │  PLANNER   │
                             └─────┬─────┘
                                   ▼
                          ┌────────────────┐
                          │ IMPASSE?         │
                          │ if yes: emit     │
                          │ cognitive.planner_│
                          │ impasse (fixes   │
                          │ §4.6) + FailureRecord│
                          │ (PLANNER.* code) │
                          └────────┬─────────┘
                                   ▼
                             ┌───────────┐
                             │  COMPILE   │──────► GOVERNANCE ──► KERNEL
                             └───────────┘
```

Data contracts, current + proposed additive fields (`(new)` marked; everything else already exists exactly as shown):

```python
# core/cognitive/intent.py — additive only
@dataclass
class RawRequest:
    text: str
    language: Optional[str] = None          # (new) §11 — best-effort, metadata only

@dataclass
class IntentDimensions:
    category: str
    modality: str
    complexity_estimate: float
    detected_language: Optional[str] = None  # (new) §11 — propagated from RawRequest

# core/capabilities/capability.py — additive only
@dataclass
class CapabilityContract:
    capability_type: str
    description: str
    required_resources: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    aliases: List[str] = field(default_factory=list)          # (new) §9
    domain_tags: List[str] = field(default_factory=list)      # (new) §9
    is_general_purpose: bool = False                          # (new) §9.4 — the actual fix vector for K42-002
    input_schema: Optional[Dict[str, Any]] = None              # (new) §9.5 — contract now, matching later
    output_schema: Optional[Dict[str, Any]] = None             # (new) §9.5
```

No existing field is renamed, removed, or repurposed anywhere in this table.

---

# 8. Contract Ownership Matrix

| Stage | Owns | Reads | Produces | May mutate | Must never change | Failure reporter | Recovery authority |
|---|---|---|---|---|---|---|---|
| Intent Interpreter | `Intent`, hypothesis generation | `RawRequest`, `known_categories` (§14) | `Intent` (draft→interpreted) | Nothing outside itself | `RawRequest.text` | *(new)* `FailureRecord` on `NormalizationRejected` — §22 | None (no retry authority) |
| Goal Formation | `Goal`, `structured_form` population | `Intent` | `Goal` (draft/verified) | Nothing outside itself | `Intent.raw_request` | *(new)* `FailureRecord` on schema-validation degrade | None |
| Constraint Extraction | `Constraint` list | `Goal` text | `List[Constraint]` | Nothing | `Goal.structured_form` | *(new)* on extraction/precheck rejection | None (`check_precheck_rejection` is terminal by design) |
| Capability Discovery | `CapabilityDiscoveryRequest`→candidates | `Goal` (via builder only), `CapabilityRegistry` | `List[CapabilityContract]`, `CapabilityMatch` (§10) | Nothing | Does not select adapters (K42-S05), does not rank down to one winner | *(new)* on empty-candidate result | None |
| Planner Completion | `ExecutionPlan`, `ImpasseRecord` | `PlannerRequest`, discovery output | `PlannerResult` | Nothing outside itself | Does not call Governance (K4.2 §2 — reserved for Compilation) | *(new)* on impasse (§4.6 fix) | None — impasse is Planner-local until reported (§12) |
| Plan Compilation | `WorkflowDefinition`, `CompilationResult` | `ExecutionPlan`, Governance | `WorkflowDefinition` or rejection | Nothing outside itself | — | *(new)* on `REJECTED`/`ESCALATED`/`REJECTED_PRECHECK` | None — surfaces to SupervisorWorker, never retries itself (K4 §16 invariant 9) |
| Governance (`GovernanceKernel`) | Verdicts, `CognitiveDecision` | Actions from any stage | `GovernanceResult` | Nothing | Verdict authority itself | Already-existing `CognitiveDecision` — wrapped by *(new)* `FailureRecord` (§19.3), not duplicated | Sole approval authority (Law 1) |
| WorkflowRuntime / `CapabilityExecutorWorker` | Execution dispatch | `WorkflowDefinition` | `WorkflowResult` | Nothing upstream | Capability *selection* stays out of scope (still C-MoE future work) | Existing `WorkerResult.error` — *(new)* `FailureRecord` on dispatch failure | None (delegates to Supervisor via failed-worker-result path) |
| `SupervisorWorker` | Recovery *reaction*, never a verdict of its own | `CompilationResult`, `failed_worker_result`, *(new)* impasse reports (§12–13) | `SupervisorOutcome` | Nothing it didn't create | Never re-invokes a rejected/escalated plan unchanged (K4 §16 invariant 9, structurally enforced — no `compile()`/`ExecutionRuntime` call in `_surface_compilation_outcome()`) | Consumes `FailureRecord`s, does not produce diagnostic infrastructure itself (K42-S28) | Bounded retry only, existing `max_supervisor_retries` mechanism, extended not replaced (§30) |
| `EvaluatorWorker` / `ReflectionWorker` | Post-execution analysis | `EvaluationRecord`, execution trail | Analysis artifacts, proposed memory writes | Nothing evaluated (never edits artifacts, K4 §8) | — | N/A — post-hoc, not failure-path | None |

---

# 9. Capability Discovery Architecture

## 9.1 What stays exactly as it is

**[REC]** The candidate-generation shape is sound and is kept unchanged: query `CapabilityRegistry.list_capabilities()`, skip contracts with zero registered adapters (the existing "declared but unfulfilled" filter, `registry.validate()`'s own concept), skip contracts with no contract object. This correctly separates **relevance** (does this look related) from **availability** (is anything registered to actually run it) already, and does not select a concrete adapter — K42-S05 already holds today and is preserved.

## 9.2 What changes: one signal becomes several

**[REC]** `_capability_match_score()` (single float) becomes `_capability_match_signals()` (structured evidence list), matching the shape the task brief's §24 pipeline calls for:

```text
Goal → Discovery View → Candidate Generation → Compatibility Gates → Match Signals →
    ├── lexical            (existing Jaccard — kept, weight reduced from "only signal" to "one of several")
    ├── aliases             (new — CapabilityContract.aliases, §7)
    ├── domain_tags         (new — coarse tag overlap against Intent.dimensions.category)
    ├── general_purpose flag (new — §9.4, the concrete K42-002 fix)
    ├── schema/interface    (future hook — contract field exists now, §9.5, matching deferred)
    └── semantic similarity  (future hook, explicitly out of scope now — embeddings are a K4.3+/C-MoE decision, not invented here)
    → Evidence aggregation → CapabilityMatch (§10) → Rank
```

**Relevance vs. compatibility vs. availability vs. runtime selection, made explicit** (task brief §24):

| Concept | Meaning here | Owned by |
|---|---|---|
| Relevance | "This capability appears related to the request" | Capability Discovery (this section) |
| Compatibility | "This capability's interface can satisfy what's being asked" | Capability Discovery, schema signal (currently a contract-only hook — §9.5) |
| Availability | "A usable adapter is currently registered" | Capability Discovery's existing zero-adapter filter (unchanged) |
| Runtime selection | "Which specific adapter/model actually executes" | **Out of scope for K4.2** — `CapabilityExecutorWorker`/AdapterRuntime/future C-MoE (K42-S05, §34) |

## 9.3 Why constraints still don't factor into scoring

**[FACT]** The K4.2.4 completion report already flagged, as a documented (not silent) implementation-judgment gap, that `applicable_constraints` round-trips through `CapabilityDiscoveryRequest` but does not influence `_capability_match_score`, reasoning that hard constraints are frequently *negative* ("must not use X") and naively mixing their text into a positive-overlap score risks boosting relevance to the very thing a constraint excludes. **[REC]** This reasoning is sound and is preserved unchanged — constraint-aware discovery remains a documented future hook (§45), not built now, for the same reason: no evidenced heuristic exists yet for turning a negative constraint into a scoring adjustment without risking the opposite of its intent.

## 9.4 The concrete fix for K42-002 — `is_general_purpose`, not a threshold change

**[REC]** This is the single highest-leverage, lowest-risk addition in this document, and it is scoped tightly on purpose. Add `CapabilityContract.is_general_purpose: bool = False` (§7). A capability marked `True` contributes a fixed, low-but-nonzero baseline relevance signal (e.g. `0.05`, tunable — see below) regardless of lexical overlap, reflecting a real, evidenced fact about this system's actual capability set: `LLM_COMPLETION` genuinely is a generalist fallback today (it is the *only* registered capability, §3), and "no keyword overlap" is not the same claim as "no capability can plausibly help." Concretely: `LLM_COMPLETION` registered with `is_general_purpose=True` would score `0.05` (say) against all five required queries instead of `0.0`, clearing the `min_score=0.01` gate **without changing that gate**, and without inventing a numeric score for the other nine unregistered, never-tested capability types — this signal only ever fires for contracts a human has explicitly marked, so it cannot silently make an irrelevant, narrow capability (e.g. a hypothetical future `IMAGE_GENERATION`) look like a match for `"Hello"`.

This directly satisfies the task brief's own constraint (§27, §29): it is not a "lower the threshold" fix (the `0.01` gate is untouched and still excludes zero-signal narrow capabilities), and it is reason-driven (the reason a capability matches becomes explicit evidence — `{"signal": "general_purpose", "detail": "capability declared as a generalist fallback"}` — not a magic number with no explanation, §10).

**[REC]** Exact baseline weight is intentionally left as a tunable constant, not hard-coded here as an architecture-mandated value — consistent with §27's own instruction not to invent numeric values solely to pass a test. What is architecture-mandated is the *existence* of this signal class and that it is evidenced, not silent.

## 9.5 Schema: contract now, matching later

**[REC]** `CapabilityContract.input_schema`/`output_schema` (§7, both `Optional[Dict[str, Any]] = None`) are added as **contract fields only** — no schema-matching logic is implemented in K4.2. This is deliberately the "contract exists now, full matching subset comes later" pattern the task brief's §25 explicitly permits, chosen because: (a) it gives future capability authors a place to declare an interface without inventing one later under time pressure, (b) it costs nothing today (`None` is a valid, ignorable default; zero call sites need to change), and (c) it is the natural home for the "schema/interface" match signal in §9.2's pipeline once real multi-capability schema diversity exists to test it against (today there is exactly one real capability — testing a schema matcher against a sample size of one would be exactly the kind of unevidenced heuristic §9.3 already declined to build for constraints).

---

# 10. CapabilityMatch Contract

**[REC]**

```python
@dataclass
class CapabilityMatchEvidence:
    signal: str            # "lexical" | "alias" | "domain_tag" | "general_purpose" | "schema" (future)
    score: float            # this signal's own contribution, [0,1]
    detail: str             # short, human-readable reason (e.g. matched token set, matched alias)

@dataclass
class CapabilityMatch:
    capability_type: str
    aggregate_score: float
    relevance_evidence: List[CapabilityMatchEvidence] = field(default_factory=list)
    compatibility_evidence: List[CapabilityMatchEvidence] = field(default_factory=list)  # schema-signal home, §9.5
    negative_evidence: List[CapabilityMatchEvidence] = field(default_factory=list)        # constraint conflicts, future hook §9.3
    language_compatible: Optional[bool] = None   # §11 — metadata, never a hard gate on its own
    reason_codes: List[str] = field(default_factory=list)  # CAPABILITY.* taxonomy, §18
```

**[REC]** `discover_capabilities()`'s current return type (`List[CapabilityContract]`, ranked) is **not broken and is kept as the function's return type** for existing callers (`_decompose()` and any future direct caller) — `CapabilityMatch` is an *additional*, richer artifact `discover_capabilities()` also assembles internally and attaches to the `cognitive.capabilities_discovered` event payload (§21), so Planner's own call sites need zero changes while diagnostics, future learning, and debugging gain the full evidence trail. This is the same "additive, not replacing" discipline applied everywhere else in this document.

Consumers: Planner (ranking, unchanged signature), Impasse (§12 — `ImpasseRecord.attempted_capabilities` becomes traceable to *why* each one didn't clear the bar, not just that it didn't), Recovery (§12), diagnostics (§17-22), future learning (a `CapabilityMatch` trail is exactly the kind of evidence a future semantic-matching signal would train or calibrate against — not built now, but not precluded either).

---

# 11. Internationalization Architecture

**[FACT]** Confirmed by direct search this session: no `language` field, no `_detect_language` function, and no language-handling logic of any kind exists anywhere in `core/cognitive/` or `core/capabilities/`. This is a genuine, total gap, not a partial one.

**[REC]** Design, scoped to metadata-and-compatibility per the task brief's own explicit instruction ("Language metadata should primarily serve compatibility, localization, diagnostics... rather than becoming the primary semantic router. Do not require translation to English. Do not introduce cloud language APIs."):

1. `RawRequest.language: Optional[str]` (§7) — populated by a cheap, local, deterministic heuristic (script-range detection for non-Latin scripts; a small local lexical-frequency detector for Latin-script languages — no network call, no cloud API, consistent with Law 5 Local-First). Best-effort; `None` is a fully valid, handled value everywhere downstream.
2. `IntentDimensions.detected_language: Optional[str]` (§7) — simple propagation from `RawRequest.language`, not re-derived.
3. `intent.raw_request` is **never altered, translated, or normalized based on language** — the existing `_tokenize()`/Jaccard signal continues operating on whatever script the request arrived in; a French or Arabic request against an English-described capability will still score low on the lexical signal specifically, which is expected and correct — this is exactly why §9.4's `is_general_purpose` signal is language-agnostic (a boolean flag, not text matching) and becomes the primary rescue path for non-English generic queries under today's implementation, not a language-specific carve-out.
4. `CapabilityMatch.language_compatible` (§10) is populated only if a capability contract someday declares supported languages (not built now — no capability needs it yet, one real capability exists) — and even then it is explicitly a **soft signal**, never a hard gate, per the task brief's "does not become the primary semantic router" instruction.
5. **Future extension point, explicitly not built now**: a semantic multilingual matcher (embeddings, cross-lingual similarity) would plug into the `schema`/`semantic similarity` slots already reserved in §9.2's signal pipeline — the signal-list shape is designed so this addition requires zero changes to `Goal`, `CapabilityDiscoveryRequest`, or any existing signal, satisfying K42-S20.

Mixed-language input, transliteration, typos, and technical terminology are handled the same way single-language input already is: as raw text the lexical signal may or may not score well against, rescued where applicable by the general-purpose signal — no special-case code path is introduced for any of these, per Law 4 (Determinism: routing must not vary by incidental phrasing).

---

# 12. Impasse & Recovery Architecture

## 12.1 What the architecture already specifies, precisely

**[ARCH]** K4.2 §14 (quoted in full at §4.7): impasse routes through **Capability Discovery retry**, then, if unresolved, **Skill Runtime delegation**. **[FACT]** Skill Runtime does not exist. **[REC]** This document does not invent a Skill Runtime to fill that gap (that would be exactly the "fabricate a stand-in system" anti-pattern `_decompose()`'s own docstring already declined to do for skill preconditions) — it implements the part of §14 that *is* buildable now (bounded Capability Discovery retry) and makes the part that isn't (Skill Runtime delegation) an explicit, tracked, K4.3+ boundary (§34), not a silent no-op.

## 12.2 Failure-reason-driven recovery, not threshold-lowering

**[REC]** `_detect_impasse()` gains a reason classification, distinguishing (task brief §29's own list, mapped to this codebase's actual state):

| Impasse reason | Meaning here | Recoverable? |
|---|---|---|
| `NO_CANDIDATE_REGISTERED` | `registry.list_capabilities()` returned nothing with adapters at all | Terminal — nothing to retry against |
| `ZERO_SIGNAL_ALL_CANDIDATES` | Candidates exist but every one scored below `min_score` on every signal (today's actual K42-002 failure mode) | **One bounded retry** — re-run discovery signals (not re-run the whole Planner) after confirming §6's description-source invariant held (rules out a K42-001-shaped regression as the cause before blaming discovery itself) |
| `CONTRACT_VIOLATION_UPSTREAM` | `Goal.structured_form["description"]` was empty/degenerate reaching discovery — i.e. exactly what K42-001 looked like | Not Planner-recoverable — reported as `CONTRACT.GOAL_DESCRIPTION_INVALID` (§18), Planner-local, escalated to diagnostics, not silently retried into a probably-identical failure |
| `AMBIGUOUS_GOAL` | Multiple candidates cleared the bar with close, low scores | Not Planner-recoverable — belongs to `ClarificationPolicy` (already-existing mechanism, K4.2 §2/§9), not a new one |

**[REC]** The bounded retry for `ZERO_SIGNAL_ALL_CANDIDATES` is capped at exactly one attempt, reuses the *same* discovery call with the newly-added multi-signal scoring (§9) rather than any threshold change, and is tracked by the Recovery Budget (§12.3) — never a second, independent retry loop.

## 12.3 One recovery budget, reusing an existing pattern

**[ARCH]** K4.2 §14 itself already directs this: bounded clarification-escalation loops should reuse "`RecursionGovernor`'s existing bounded-loop principle rather than inventing a second one." **[REC]** The Recovery Budget for Planner-level impasse retry follows the identical instruction — it is a thin, explicit counter threaded the same way `SupervisorWorker`'s own existing `max_supervisor_retries`/`supervisor_retry_attempt` pair is already threaded (caller-tracked, Supervisor/Planner holds no state of its own, per K4 §4) — **not** a new governance mechanism, **not** a second `BudgetGovernor`. Concretely: `PlannerRequest` gains one additive field, `recovery_attempt: int = 0` (default 0, caller-populated on retry), and `plan()` refuses a second `ZERO_SIGNAL_ALL_CANDIDATES` retry once `recovery_attempt >= 1`, returning terminal `IMPASSE` with reason `RECOVERY_BUDGET_EXHAUSTED`. **[REC] This design is deliberately shaped to avoid DEBT-007's exact failure mode (§4.9)** — the counter is incremented at the one call site that performs the retry, not scattered across multiple call sites that might each assume another increments it.

## 12.4 What §4.6/§4.7's fixes look like concretely

**[REC]**
1. `plan()`'s impasse branch emits `cognitive.planner_impasse` (already named, already specified, simply never called) with the new `FailureRecord` attached (§19) — closing §4.6.
2. Terminal impasse (`recovery_attempt >= 1` or a non-recoverable reason) is reported to `SupervisorWorker` for **visibility only** — a third input path alongside `compilation_result`/`failed_worker_result`, named `impasse_report`, that `SupervisorWorker` surfaces (mirrors `_surface_compilation_outcome`'s existing pattern exactly) but never retries from directly — Planner-level retry, if any, already happened once under §12.3's own budget before Supervisor ever sees it. This closes §4.8 without granting Supervisor new authority (K42-S11/S12 preserved).

---

# 13. SupervisorWorker Contract

**[REC]** Formalizing which Planner/Compilation failures belong where, using this codebase's own already-established vocabulary:

| Failure class | Where it's decided | Supervisor's role |
|---|---|---|
| `rejected_precheck` (Planner) | Planner-local, terminal — provably unsatisfiable before decomposition even starts | **Never reaches Supervisor** — unchanged, matches the existing pattern for compilation's own `REJECTED_PRECHECK` |
| `impasse`, recoverable reason, `recovery_attempt == 0` | Planner-local — one bounded retry inside `plan()` itself (§12.2-12.3) | Not invoked yet |
| `impasse`, terminal (budget exhausted or non-recoverable reason) | Reported | **Supervisor-handled — visibility/surfacing only** (new `impasse_report` path, §12.4), same shape as existing `_surface_compilation_outcome` |
| Ambiguous Goal / low confidence crossing escalation threshold | `ClarificationPolicy` (existing, K4.2 §2/§9) | Not Supervisor's concern — a different, already-specified escalation path |
| `CompilationStatus.REJECTED` / `ESCALATED` | Governance verdict | **Supervisor-handled** — unchanged, existing `_surface_compilation_outcome` |
| `failed_worker_result` (any worker) | Execution-time failure | **Supervisor-handled — bounded retry**, unchanged, existing `_attempt_retry` |

**[REC]** No change to `SupervisorWorker`'s governance posture: it still produces no `GovernanceVerdict` of its own (K42-S12 — confirmed already true, `SupervisorOutcome` is explicitly documented as distinct from `GovernanceVerdict` in the existing code), and `_surface_compilation_outcome`'s structural guarantee (no `compile()`/`ExecutionRuntime` call in that method at all — K4 §16 invariant 9) is extended verbatim to the new `impasse_report` path: no `plan()`/`discover_capabilities()` call appears in whatever surfaces an `impasse_report` either.

---

# 14. Intent Ontology Lifecycle

**[FACT]** Write path is real and tested: `validation_gate(content_domain=ContentDomain.INTENT_ONTOLOGY, ...)` (`learning.py`) → promotion → `LearningRecord`. Read path (`known_categories` parameter, `intent.py`) is real and wired end-to-end *inside* `intent.py` — but never populated at its one production call site (`orchestrator.py`, §4.5).

```text
learning (any cognitive component observes a pattern)
  ↓
validation_gate(content_domain=INTENT_ONTOLOGY, tier=...)   [EXISTS, TESTED]
  ↓
promoted LearningRecord                                      [EXISTS]
  ↓
??? — no query function reads promoted INTENT_ONTOLOGY entries back out  [MISSING]
  ↓
known_categories: List[str]                                  [PARAMETER EXISTS, NEVER POPULATED]
  ↓
intent interpretation prompt                                 [ALWAYS SEES "(none yet)" IN PRODUCTION]
```

**[REC]** Close the loop with the smallest possible addition: a `list_promoted_categories() -> List[str]` query function in `learning.py` (mirroring `user_model.py`'s already-existing `list_user_model_entries()` pattern for the *other* `ContentDomain` — precedent already exists in this exact file family), called once per `interpret_request()` invocation at the orchestrator's K4.2 call site, and — per the hardening review's own already-accepted §8 caching clarification (§4.9-adjacent finding, `k4_2_architecture_hardening_review.md` item 8: "cached with a short TTL, purely as a performance measure... Cache hits are still events") — cached with a short TTL rather than queried fresh on every single request. **This is a read-side wiring fix, not a new ontology-management subsystem** — no promotion, aliasing, merge, or lifecycle logic changes; `validation_gate()`'s existing safety checks are untouched.

---

# 15. Canonical Construction Rules

**[FACT]** `build_planner_request()` and `build_capability_discovery_request()` (both `planner.py`) are already canonical in practice — every production call site this session traced uses them; no inline `PlannerRequest(...)`/`CapabilityDiscoveryRequest(...)` construction was found outside these two builders and their own tests.

**[REC]** Make this **provably**, not just currently, true — reusing a testing pattern **this exact codebase already applies elsewhere**. `tests/test_reflection_worker.py`, `tests/test_supervisor_worker.py`, and `tests/test_evaluator_worker.py` already contain static identifier-based assertions of exactly this shape (`assert "validation_gate" not in identifiers`, confirmed this session by direct grep). **[REC]** Add the mirror-image assertion: a static test (AST-based, consistent with this project's own `graphify`/`graphifyy` tooling per the project's established repository-tooling conventions) asserting that the only two call sites in `core/` constructing `CapabilityDiscoveryRequest(` or `PlannerRequest(` directly are `build_capability_discovery_request()` and `build_planner_request()` themselves. This is the single-canonical-path invariant (K42-S13) made testable using the project's own established idiom, not a new testing philosophy introduced from outside.

---

# 16. Contract Versioning & Migration

## 16.1 General policy

**[REC]** No generic contract-versioning framework is built now (task brief §34 explicitly permits this). What is required — and does not exist today — is that every shared contract listed in §7/§8 has an explicit **evolution strategy**, which for K4.2's current, single-deployment, pre-parallel-milestone state means exactly one thing in practice: **new fields are additive with defaults, existing fields are never repurposed, and any change to an existing field's meaning is an Architecture-Review-Required change** (§32), not an Independently Safe one. Every field addition proposed in this document (§7, §10, §12.3) already follows this rule — none of them require a migration step because none of them change what an existing field means or removes anything a consumer currently depends on.

## 16.2 The one contract that needs an explicit decision, not a silent pick

**[INFER]** §4.10's `LearningRecord`/closed `ContentDomain` vs. `LearningCandidate`/open `domain` contradiction is the one real exception to "additive fixes everything" — it is a genuine disagreement between two authoritative documents about whether the domain space is closed or open, and the *shipped, tested* implementation already picked one side (closed, three values) while the higher-precedence document specifies the other. **[REC]** This document does not silently resolve it either direction. It records the two positions, their evidence, and recommends the decision be made explicitly before any K4.2.6+ Learning Architecture work proceeds further (already flagged as an open item independent of this session):

| | `LearningRecord.content_domain` (shipped) | `LearningCandidate.domain` (K4.1-L, higher precedence) |
|---|---|---|
| Shape | Closed 3-value enum (`SKILL`, `INTENT_ONTOLOGY`, `USER_MODEL`) | Open string, no enum |
| Tested? | Yes — `validation_gate()` is real, tiered, tested | Not implemented as such |
| Rationale given | None found in K4.2 §12 beyond the type declaration | Explicit: "not six named, implicitly closed categories" — designed for components not yet imagined |
| Migration cost if K4.1-L wins | `ContentDomain.ALL` becomes a set of currently-known values rather than the full enum; `validation_gate()`'s `if content_domain not in ContentDomain.ALL` check (`learning.py:493`) becomes a registration check instead of a membership check — a real but bounded, well-isolated change | — |

**[REC]** If not otherwise directed, this document's own recommendation leans toward K4.1-L's open model on precedence grounds alone (Law 9 — a lower-precedence document should not silently override a higher one) — but this is flagged as a recommendation requiring explicit sign-off, not a decision this specification makes unilaterally, precisely because it is Architecture-Review-Required by its own §32 classification below.

---

# 17. OCBrain Diagnostic & Failure Architecture

## 17.1 Scope discipline

**[REC]** Built now: the core contract (`FailureRecord`), the taxonomy, correlation/causality shape, transport (reusing `EventStream`), and integration at exactly the K4.2 boundaries where §4 found real gaps. **Not built now**: distributed observability, ML root-cause detection, dashboards, cross-fleet health analytics, automated healing — all explicitly out of scope per the task brief §14/§45, and none of them are needed to close any of §4's findings.

## 17.2 Why now, and why K4.2 specifically

**[INFER]** Every confirmed weak link in §4 that involves a *failure path* (§4.6 impasse event never emitted, §4.7 architecture/implementation contradiction on recoverability, §4.8 Supervisor has no impasse input, §4.9 three free-text error fields with three different informal naming conventions) is the same underlying problem wearing different clothes: **there is currently no shared vocabulary for "something didn't go as expected"** anywhere in the cognitive pipeline. Fixing K42-001/K42-002 without also fixing this would leave the *next* cognitive-pipeline defect exactly as invisible as these two were.

## 17.3 Responsibility boundary (task brief §5, adopted verbatim — this is exactly right and needs no modification)

```text
Subsystem → detects problem → Diagnostic System → records/classifies/correlates
                                                          ↓
                                                  Recovery Authority → decides whether/how recovery occurs
```

**[REC]** The Diagnostic System is a recorder, not a decision-maker (K42-S28). It never gains the authority `SupervisorWorker` or `GovernanceKernel` already hold. This is the same governance-separation principle (§5) applied to a new subsystem before that subsystem exists, rather than after — cheaper to state now than to retrofit later.

## 17.4 Reuse, don't add a fourth transport

**[FACT→REC]** Given §4.9's DEBT-004/DEBT-005 evidence (three event mechanisms already tracked as fragmentation debt), the Diagnostic System's transport decision is not close: **`FailureRecord`s are carried as `EventStream` events, under a new `diagnostic.*` namespace, using the exact same `EventStream.append(event_type, source=, payload=)` shape every other K4.2 event already uses** (confirmed correct usage, `planner.py:703-714`). No new persistence layer, no new pub/sub mechanism, no fifth event system. `FailureRecord.correlation_id` is sourced from the **already-existing** `core/observability/tracer.py` `get_trace_id()` ContextVar — this repository already has exactly the async-safe, request-scoped correlation primitive the task brief asks for; it has simply never been connected to a structured failure record.

## 17.5 Diagnostic dependency graph

```text
Subsystem / Stage (Intent, Goal, Planner, Discovery, Compiler, Governance...)
       │
       ▼
Failure Detection  (existing exception handling / existing status enums —
                     unchanged; this is where a FailureRecord gets constructed,
                     not a new detection mechanism)
       │
       ▼
FailureRecord  (§19)
       │
       ├────────────► EventStream  (existing transport, §17.4 — diagnostic.* events)
       │
       ├────────────► Causal Chain  (correlation_id + causal_parent, §20)
       │
       ├────────────► Health State  [future — not built now, §17.1]
       │
       └────────────► Recovery Authority (SupervisorWorker for compilation/impasse
                        surfacing; Planner's own bounded retry for impasse per §12.3;
                        GovernanceKernel for verdicts — never the Diagnostic System itself)
                         │
                         ▼
                    Recovery Action (existing mechanisms — §12, §13; nothing new
                                      invented here)
                         │
                         ▼
                    new FailureRecord (if the recovery attempt itself fails —
                                        causal_parent points at the original)
```

---

# 18. Failure Taxonomy and Reason-Code Model

## 18.1 Failure class (task brief §6, adopted, mapped against evidence found this session)

| Class | Meaning | Confirmed example from this session's audit |
|---|---|---|
| `SUCCESS` | Expected outcome | — |
| `WARNING` | Noteworthy, non-blocking | Memory-write failure caught and logged non-blocking (`orchestrator.py:386-388`) — today a bare `logger.warning`, becomes a `WARNING`-class `FailureRecord` |
| `DEGRADED` | Fallback succeeded | Provider cooldown/fallback via `Adapter.mark_failure()`'s existing exponential backoff (`capability.py:183-188`) — already a real, tested pattern; a `DEGRADED` record wraps it, does not replace it |
| `RECOVERABLE_FAILURE` | Bounded retry applies | §12.2's `ZERO_SIGNAL_ALL_CANDIDATES` impasse, before the recovery budget is exhausted |
| `IMPASSE` | Cognitive-specific: no plannable path found | §4.1/§4.2's exact failure mode — **not automatically an error** |
| `TERMINAL_FAILURE` | Recovery exhausted or reason is non-recoverable | §12.2's `RECOVERY_BUDGET_EXHAUSTED`, `AMBIGUOUS_GOAL` |
| `SYSTEM_ERROR` | Unexpected exception, not a modeled failure mode | `orchestrator.py:404-419`'s generic `except Exception` branch |
| `CONTRACT_VIOLATION` | A cross-stage data contract was broken | §12.2's `CONTRACT_VIOLATION_UPSTREAM` — the generalized, permanent form of what K42-001 looked like from Capability Discovery's point of view |
| `GOVERNANCE_OUTCOME` | A `GovernanceVerdict` was reject/escalate | Wraps existing `CognitiveDecision` (§19.3) — does not replace it |

Not every non-success is an error — `DEGRADED` and `IMPASSE` in particular are legitimate, expected, sometimes-correct outcomes and must never collapse into `SYSTEM_ERROR`'s bucket, exactly as the task brief's §6 examples specify.

## 18.2 Reason-code namespace

**[REC]** Hierarchical, dot-namespaced, matching the existing `cognitive.*`/`workflow.*` event-naming convention (K4.2 §11's own reconciliation table already establishes this style — reused, not reinvented):

```text
CONTRACT.*      — cross-stage data contract violations
COGNITIVE.*      — general cognitive-pipeline (parent namespace for the below)
INTENT.*
GOAL.*
PLANNER.*
CAPABILITY.*
DISCOVERY.*
RECOVERY.*
GOVERNANCE.*     — wraps CognitiveDecision, does not duplicate its fields
PROVIDER.*       — wraps Adapter.mark_failure()/health_score, does not duplicate it
```

K4.2's own evidenced reason codes, defined now (all others are future subsystems' own responsibility to define under this namespace, per §18.3):

| Code | Fires when | Class |
|---|---|---|
| `CONTRACT.GOAL_DESCRIPTION_NOT_RAW_TEXT` | §6.1's invariant test fails — `structured_form["description"]` traces to a hypothesis label instead of `raw_request`/a compound part | `CONTRACT_VIOLATION` — this is the **permanent regression guard for K42-001**, not just today's one-time fix |
| `CAPABILITY.ZERO_SIGNAL_ALL_CANDIDATES` | Every discovered candidate scored below `min_score` on every signal | `IMPASSE` → `RECOVERABLE_FAILURE` (one retry) |
| `CAPABILITY.NO_CANDIDATE_REGISTERED` | Registry has nothing with adapters at all | `IMPASSE` → `TERMINAL_FAILURE` |
| `PLANNER.IMPASSE_RECOVERY_EXHAUSTED` | §12.3's budget hit | `TERMINAL_FAILURE` |
| `PLANNER.PRECHECK_REJECTED` | Contradictory hard constraints | `TERMINAL_FAILURE` (unchanged from today's `rejected_precheck`, now classified) |
| `GOAL.SCHEMA_VALIDATION_DEGRADED` | `_validate_structured_form()`'s existing degrade-not-fail path | `WARNING` (confidence penalty already applied — this just makes it visible) |
| `GOVERNANCE.VERDICT_REJECT` / `GOVERNANCE.VERDICT_ESCALATE` | Wraps existing `CompilationResult.status` REJECTED/ESCALATED | `GOVERNANCE_OUTCOME` |

## 18.3 Ownership, uniqueness, evolution

**[REC]** One subsystem owns one top-level namespace segment. A new reason code under an existing segment (e.g. a future `PLANNER.NEW_CODE`) is an **Independently Safe** change (§32) — no architecture review required, since it extends the enum without altering `FailureRecord`'s shape or any consumer's parsing logic. A *new top-level segment* (a new subsystem joining the taxonomy) is **Compatibility-Sensitive** — announced, not silently added, so two parallel milestones don't independently invent the same segment name for different things. Severity mapping (§18.1's class table) is fixed per class, not per code, keeping the two concerns (what kind of thing happened vs. how bad it is) independently understandable — matching the task brief's own explicit instruction that severity be distinct from failure class (§40).

---

# 19. FailureRecord Contract

## 19.1 What kind of thing a `FailureRecord` is

**[FACT→INFER]** K4.2 §12's own closing line already draws the exact distinction needed here: "`CognitiveDecision` and `LearningRecord` are log/record shapes, written as part of an Event or a `KnowledgeEntry`, not independent Resources with their own registry." **[REC]** `FailureRecord` is the same kind of thing — a log/record shape carried inside an `EventStream` event payload, **not** a `CognitiveArtifact`/Resource with its own `resource_id`-addressable registry. It does not need a lifecycle state machine of its own; its lifecycle *is* the event stream's own append-only, replayable history.

## 19.2 Field table

| Field | Type | Required | Authority | Producer | Consumers | Mutable? | Persistence |
|---|---|---|---|---|---|---|---|
| `failure_id` | `str` (uuid4) | Yes | Diagnostic System | Whoever constructs the record | Correlation queries | No | `EventStream` payload |
| `correlation_id` | `str` | Yes | **Reused from `tracer.get_trace_id()`** — not re-derived | Same as above | Causal-chain reconstruction (§20) | No | `EventStream` payload |
| `operation_id` | `str` | Yes | Caller-supplied (e.g. `interaction_id`, already threaded through `orchestrator.py` end-to-end) | Orchestrator/caller | Cross-request tracing | No | `EventStream` payload |
| `timestamp` | `float` | Yes | `time.time()` | Auto | Timeline ordering | No | `EventStream` payload (mirrors `StreamEvent.timestamp`) |
| `subsystem` | `str` | Yes | Producer | Producer | Filtering, §18.3 namespace ownership | No | payload |
| `stage` | `str` | Yes | Producer (e.g. `"IntentInterpreter"`, `"CapabilityDiscovery"`) | Producer | Boundary-matrix cross-reference (§23) | No | payload |
| `failure_class` | `str` (§18.1 enum) | Yes | Taxonomy | Producer | Severity derivation, alerting (future) | No | payload |
| `reason_code` | `str` (§18.2 namespace) | Yes | Taxonomy | Producer | Machine-readable dispatch (this is what `ImpasseRecord.reason`/`precheck_errors`/ad hoc `error_type` strings never had, §4.9) | No | payload |
| `severity` | `str` | Yes | Derived from `failure_class`, fixed mapping (§18.3) | Auto | Future health rollup | No | payload |
| `recoverability` | `str` (`recoverable`\|`terminal`\|`not_applicable`) | Yes | Producer, per §18.1's class | Producer | Recovery Authority's own decision input (not the Diagnostic System's decision — §17.3) | No | payload |
| `attempt` / `recovery_budget` | `int`/`int` | No | §12.3's counter, when applicable | Planner/Supervisor | Bounded-loop verification | No | payload |
| `causal_parent` | `Optional[str]` (a `failure_id`) | No | Producer, when chaining | Producer | Causality reconstruction (§20) | No | payload |
| `evidence` | `Dict[str, Any]` | No | Producer | Producer | Debugging | No | payload — **bounded, no raw user secrets** (§29) |
| `governance_ref` | `Optional[str]` | No | Wraps an existing `CognitiveDecision`, when `failure_class == GOVERNANCE_OUTCOME` | GovernanceKernel | — | No | payload |

## 19.3 Explicit non-duplication rule

**[REC]** A `FailureRecord` produced from a `GovernanceKernel` evaluation **wraps** the existing `CognitiveDecision` (`governance_ref` points at it; `reason_code`/`recoverability` are derived from `CognitiveDecision.verdict`, not independently re-decided) — it never re-implements verdict logic. This is the concrete enforcement of §17.3's boundary and directly prevents the Diagnostic System from becoming "a second Governance engine," which the task brief explicitly forbids (§5).

```python
@dataclass
class FailureRecord:
    failure_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=get_trace_id)   # reuses core/observability/tracer.py
    operation_id: str = ""
    timestamp: float = field(default_factory=time.time)
    subsystem: str = ""
    stage: str = ""
    failure_class: str = ""      # FailureClass.* , §18.1
    reason_code: str = ""        # dot-namespaced, §18.2
    severity: str = ""           # derived, fixed per failure_class
    recoverability: str = "not_applicable"
    attempt: int = 0
    recovery_budget: Optional[int] = None
    causal_parent: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    governance_ref: Optional[str] = None
```

---

# 20. Failure Correlation & Causality

**[REC]** Two IDs, reused not invented: `correlation_id` (= `tracer.get_trace_id()`, already request-scoped and async-safe) ties every `FailureRecord` from one request together; `causal_parent` (a `failure_id`) chains a downstream consequence to its root cause explicitly, only when a producer actually knows the chain — never inferred after the fact. Worked example, directly reconstructing the exact chain shape the task brief's §8 asks for, grounded in this session's own findings:

```text
CAPABILITY.ZERO_SIGNAL_ALL_CANDIDATES   (failure_id: f1, causal_parent: None)
        │  — Capability Discovery, this is the root cause
        ▼
PLANNER.IMPASSE_RECOVERY_EXHAUSTED       (failure_id: f2, causal_parent: f1)
        │  — Planner, one bounded retry already spent (§12.3) and still zero signal
        ▼
orchestrator.query_failed                (references f2 in its payload)
        │  — same event that already exists today, now carrying a real reason_code
        ▼
(user-visible apology message, unchanged wording — this is a diagnostics
 improvement, not a UX change)
```

Answering the task brief's own test question directly: **"what happened first, what resulted from it, what recovery was attempted, and why did the system ultimately stop"** is now answerable by querying `EventStream` for `correlation_id == <this request's trace_id>`, ordering by `timestamp`, and walking `causal_parent` pointers — no new query mechanism, `EventStream.query(since=...)` already exists (note: per this project's own established discipline, `query()` returns newest-first with a default `limit=100`, so any diagnostic tooling built against this must use the `since=` filter, not count-based slicing, exactly as already required of every other `EventStream` consumer in this codebase).

---

# 21. Diagnostic Event Architecture

**[REC]** New `diagnostic.*` events, transported by the existing `EventStream.append()` — no new event mechanism (§17.4):

| Event | Producer | Payload (minimum) | Fixes / relates to |
|---|---|---|---|
| `cognitive.planner_impasse` | `plan()` | `FailureRecord` (impasse-class) | **§4.6 — closes the confirmed emit gap directly; this event name is already architecture-specified, not new** |
| `diagnostic.failure_recorded` | Any subsystem constructing a `FailureRecord` | Full `FailureRecord` | General case |
| `diagnostic.recovery_started` / `diagnostic.recovery_completed` | Planner (§12.3 retry), SupervisorWorker | `failure_id`, `attempt`, outcome | Makes §12's bounded retry itself observable, closing the "recovery state" half of §4.9's gap |
| `diagnostic.terminal_failure` | Whichever stage gives up | `FailureRecord` (terminal), full causal chain if traced | Answers "why did it stop" without reproducing the bug from scratch |
| `diagnostic.contract_violation` | Any boundary validation (§23) | `FailureRecord` (`CONTRACT_VIOLATION`) | Generalized K42-001 regression guard (§18.2) |

Each has one producer, one fixed payload shape (a `FailureRecord`, optionally with extra context keys), the same `correlation_id`/versioning discipline every other K4.2 event already follows, and no event here is invented without a concrete producer and consumer identified in this table — matching the task brief's own instruction not to add unnecessary events.

---

# 22. K4.2 Diagnostic Integration

**[REC]** Minimum viable integration, scoped exactly to where §4 found real gaps — nowhere else:

| Stage | Integration |
|---|---|
| Intent Interpreter | `NormalizationRejected` (currently silent by design, §4.9) gains a `FailureRecord` (`class=WARNING`, `reason_code=INTENT.NORMALIZATION_REJECTED`) — the one existing silent failure path in this file |
| Goal Formation | `GOAL.SCHEMA_VALIDATION_DEGRADED` on the existing degrade-not-fail path (§18.2) |
| Capability Discovery | `CAPABILITY.ZERO_SIGNAL_ALL_CANDIDATES` / `CAPABILITY.NO_CANDIDATE_REGISTERED` (§18.2), attached to the existing `cognitive.capabilities_discovered` event rather than a separate one when the result is non-empty-but-low-confidence |
| Planner | `cognitive.planner_impasse` now actually emitted (§4.6, §21); `PLANNER.PRECHECK_REJECTED`, `PLANNER.IMPASSE_RECOVERY_EXHAUSTED` |
| Recovery (§12) | `diagnostic.recovery_started`/`completed` around the one bounded retry |
| Orchestrator | The three existing ad hoc `error_type` strings (§4.9) are replaced by real `reason_code`s from a real `FailureRecord`, attached to the *same* `orchestrator.query_failed` event that already exists — no new orchestrator-level event |
| Compiler boundary | `governance_ref`-wrapped `FailureRecord` on `REJECTED`/`ESCALATED`/`REJECTED_PRECHECK` (§19.3) |

No integration point beyond this table is added in K4.2 — future subsystems (Memory, Workflow, Providers, etc.) adopt the same `FailureRecord`/taxonomy/`EventStream` pattern on their own schedule, under their own namespace segment (§18.3), which is the entire point of building the contract here first.

---

# 23. Boundary Contract Matrix

| Boundary | Input | Output | Authority | Validation | Confidence | Provenance | Language | Failure | Recovery | Diagnostics | Builder |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Input→Intent | `RawRequest` | `Intent` | Intent Interpreter | `NormalizationRejected` screen | `IntentHypothesis.score`→`Intent.confidence` | `derived_from=[]` (root) | `RawRequest.language` (new) | `INTENT.NORMALIZATION_REJECTED` (new) | None | `diagnostic.failure_recorded` (new) | `normalize_request()` |
| Intent→Goal | `Intent` | `Goal` | Goal Formation | `_validate_structured_form()` (existing) + **§6.1's new description-source invariant test** | Inherited, penalized on schema-degrade | `derived_from=[intent.resource_id]` | `IntentDimensions.detected_language` propagated | `GOAL.SCHEMA_VALIDATION_DEGRADED`, `CONTRACT.GOAL_DESCRIPTION_NOT_RAW_TEXT` (new) | None | as above | `form_goals()` |
| Goal→Discovery View | `Goal` | `CapabilityDiscoveryRequest` | Capability Discovery | Read-only pass-through, no independent validation | N/A (view, not scored itself) | Implicit via `Goal` | Carried, not re-derived | N/A at this hop | N/A | N/A | `build_capability_discovery_request()` |
| Discovery→CapabilityMatch | `CapabilityDiscoveryRequest`, `CapabilityRegistry` | `List[CapabilityContract]` + `CapabilityMatch` (new) | Capability Discovery | Zero-adapter filter (existing) | `aggregate_score` (§10, new) | N/A (ephemeral) | `language_compatible` (new, soft) | `CAPABILITY.*` (§18.2, new) | Planner's bounded retry (§12.3) | `cognitive.capabilities_discovered` (existing, enriched) | `discover_capabilities()` |
| Goal+Discovery→Planner | `PlannerRequest` | `PlannerResult` | Planner | `_detect_impasse()` + new reason classification (§12.2) | `_estimate_confidence()` (existing) | `derived_from=[goal.resource_id]` | Carried | `PLANNER.*` (new) | §12.3 bounded retry | `cognitive.planner_impasse` (now actually emitted) | `build_planner_request()` |
| Planner→Compiler | `ExecutionPlan` | `CompilationResult` | Plan Compiler | `_validate_plan_structure()` (existing) | Existing | Existing | N/A | Existing status enum, now `governance_ref`-wrapped (§19.3) | `SupervisorWorker` (existing, unchanged) | Existing events, enriched | `compile()` |
| Compiler→Governance | Compilation action | `GovernanceResult`/`CognitiveDecision` | GovernanceKernel | Existing (unchanged — governance logic itself is out of scope here) | N/A | Existing | N/A | `GOVERNANCE.*` wrapping `CognitiveDecision` | Sole approval authority (Law 1) | Existing | N/A |

---

# 24. Architecture Invariants

**[REC]** K42-S01 through K42-S28, as specified in the task brief, are adopted **without modification** — they are well-formed, each independently testable, and every one of them is directly supported by evidence gathered this session (§4) rather than asserted abstractly. Three are added, each motivated by a specific finding this session made that the original 28 don't quite cover:

| # | Invariant | Motivated by |
|---|---|---|
| **K42-S29** | An event name specified in an authoritative architecture document's Event Integration table is either emitted by the code claiming to implement that section, or the discrepancy is recorded in `KNOWN_ISSUES.md` — never silently absent | §4.6's confirmed `cognitive.planner_impasse` gap |
| **K42-S30** | A `FailureRecord`'s `reason_code` is never a free-text string reused as if it were a code (i.e., `ImpasseRecord.reason`-style prose does not migrate into `reason_code` verbatim) | §4.9's three ad hoc, mutually-inconsistent `error_type` strings |
| **K42-S31** | A capability-relevance signal that can rescue a zero-lexical-overlap match (e.g. `is_general_purpose`) must be an explicit, evidenced, human-declared property of the capability contract — never an implicit consequence of lowering a numeric threshold | §9.4/§29 — the direct architectural guard against "lower the threshold" being mistaken for a fix |

All 31 are individually testable, per §25.

---

# 25. Test Architecture

**[REC]** Aligned to this project's own established testing conventions — confirmed this session by direct reading of `tests/test_reflection_worker.py`, `tests/test_supervisor_worker.py`, `tests/test_evaluator_worker.py`, `tests/core/cognitive/test_learning.py` — not a new testing philosophy:

| Test class | What it proves | Existing precedent reused |
|---|---|---|
| Failure detection | A stage constructs a `FailureRecord` when its own existing failure condition fires | New — no precedent needed, straightforward assertion on the record's presence |
| Failure classification | Correct `failure_class`/`reason_code` for a given input | New |
| Correlation | One request's `FailureRecord`s share one `correlation_id` | Reuses `tracer.py`'s existing `get_trace_id()` — testable by asserting the same value threads through, same pattern already used to test `span()` |
| Causality | `causal_parent` correctly links §20's worked chain | New |
| Recovery | §12.3's budget counter increments exactly once per retry, refuses a second | Mirrors the existing `test_supervisor_worker.py` retry-bound tests directly |
| Terminal state | A `TERMINAL_FAILURE` record explains, via `reason_code`, why recovery stopped | New |
| Contract violations | §6.1's description-source invariant test fails loudly on a deliberately-reintroduced K42-001-shaped regression | **This is the actual regression test for K42-001** — not just "the bug is fixed" but "the bug class cannot silently return" |
| Severity vs. class | Two different `reason_code`s under the same `failure_class` can carry different `severity` | New |
| Degraded success | A `DEGRADED`-class record is never mistaken for `TERMINAL_FAILURE` in an assertion | New — directly guards §18.1's "not every non-success is an error" principle |
| Canonical construction | Static identifier assertion, §15 — **directly reuses this project's own existing `"validation_gate" not in identifiers`-style pattern**, applied to `CapabilityDiscoveryRequest(`/`PlannerRequest(` |
| Parallel milestone | A new `reason_code` under an owned namespace segment integrates without modifying `FailureRecord`'s dataclass shape | New |

**[FACT]** Baseline to preserve: `CURRENT_STATE.md` reports 1048/1048 tests passing as of the last full-suite run referenced in this repository; memory records environment-only failures traced to sandbox inability to reach `huggingface.co`, unrelated to any of this document's scope.

---

# 26. Mocking Policy

**[REC]** Task brief §41 adopted verbatim, with one concrete, evidence-grounded addition: this session confirmed `discover_capabilities()` returns real `CapabilityContract` objects from a real `CapabilityRegistry` (§4.4's confirmed API), never a synthesized stand-in — integration tests exercising the Planner↔Discovery boundary must continue registering a real `CapabilityContract` with a real (possibly deliberately generic-scoring) `description`, and must **never** hand-craft a contract whose `description` is copied verbatim from the test's own query text merely to guarantee a nonzero Jaccard score — doing so would hide exactly the class of failure §4.2 found. Mock only at genuine external boundaries: a fake `Adapter`/provider is fine (matches the existing `Adapter` Protocol's structural-typing design, `capability.py:127-146`); a fake capability *contract* engineered to match is not.

---

# 27. Observability

**[REC]** Integration with existing infrastructure only — no new observability platform:

| Existing mechanism | How the Diagnostic System uses it |
|---|---|
| `EventStream` | Transport for all `diagnostic.*` events (§21) — no new transport |
| `core/observability/tracer.py` | Source of `correlation_id` (§19.2) — no new correlation primitive |
| `CognitiveDecision` (K4.2 §12) | Wrapped, not duplicated, for `GOVERNANCE_OUTCOME` (§19.3) |
| `Adapter.health_score`/`cooldown_until` (`capability.py`) | Model for `PROVIDER.*` `DEGRADED` records — same exponential-backoff shape, not re-invented |

Every new event in §21 has one producer, one payload shape, and one identified consumer set — no event is added speculatively.

---

# 28. Performance / Scalability

**[FACT]** Today's real scale is one registered capability. **[REC]** Reasoned projection, not benchmarked (none of this document's changes have been implemented or measured — stating otherwise would violate this document's own evidence-first discipline):

| Capabilities | Discovery cost | Diagnostic cost |
|---|---|---|
| 1 (today) | Unchanged — one contract, now scored on 3-4 signals instead of 1, still O(1) | Zero new records unless a failure actually occurs |
| 10 | O(n) contract scan, unchanged shape; multi-signal scoring is still per-contract O(1) work, so still O(n) total | `FailureRecord` construction only on the failure path — no steady-state cost |
| 100–1000 | Same O(n) shape holds; `list_capabilities()`'s current linear scan becomes the first real bottleneck candidate — **not addressed now** (§43 in the original brief explicitly asks this be identified, not prematurely solved) — indexing/caching by `domain_tags` is a plausible future optimization once real multi-capability data exists to justify it |

**[REC]** Diagnostics are bounded by construction (§19's `evidence: Dict[str, Any]` is explicitly a small, structured dict, not a dump of full request/response payloads) and only fire on the failure path — they cannot become a steady-state bottleneck the way an always-on tracing system could, by design.

---

# 29. Security / Reliability

**[REC]** Ontology poisoning: `validation_gate()`'s existing tiered checks (unchanged) already gate `INTENT_ONTOLOGY` promotion — the new read-side wiring (§14) only ever reads *promoted* entries, never raw candidates, so it inherits the existing safety boundary rather than needing a new one. Malicious capability metadata / alias spoofing: `CapabilityContract` registration remains composition-root-only (existing, `registry.py`'s own stated design — "No global state. No singleton lookups") — `aliases`/`domain_tags`/`is_general_purpose` (§7) are new *fields* on an already-trusted registration path, not a new untrusted input surface. Retry abuse / infinite recovery: closed structurally by §12.3's single, explicitly-incremented budget counter, following the exact pattern §4.9 flagged DEBT-007 for *not* having enforced in practice — this document's design is deliberately different in the one respect that mattered (the counter is incremented at its one call site, not assumed incremented elsewhere). Diagnostic tampering: `FailureRecord`s are `EventStream` events — already immutable/append-only by that transport's own existing design (`StreamEvent` is a frozen dataclass). Sensitive-data leakage: `FailureRecord.evidence` is explicitly bounded and structured (§19.2) — raw user request text is **not** duplicated into `evidence` by default; a `FailureRecord` references the `Goal`/`Intent` it concerns by ID, the same provenance-by-reference pattern already used everywhere else in this architecture (`derived_from`), rather than re-embedding content that already exists once, addressably, elsewhere.

---

# 30. Parallel Milestone Development Architecture

**[FACT]** This project already has a working parallel-development discipline — this session confirmed it directly: K4.2.6/K4.2.7 (Packets 04/05) were "completed by a separate parallel session, merged in via `git merge`/fast-forward" (`IMPLEMENTATION_ROADMAP.md`), and the project's own nine-step packet process (Reality audit → compliance matrix → change plan → implementation → tests → interface stability audit → documentation sync → architecture compliance audit → merge-readiness audit → single commit) already produced a clean merge once. **[REC]** This document extends that process with four additional required fields, rather than replacing it:

```text
                 K4.2 CONTRACT BASELINE (this document)
                           │
         ┌─────────────────┼─────────────────┬───────────────────┐
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
   Goal Contract     Capability Contract  Failure Contract   Recovery Budget
   (§6-7, frozen      (§7/§9/§10,           (§19, frozen        (§12.3, frozen
   description-       additive fields        shape, open        shape)
   source rule)        only)                 reason-code
                                              namespace)
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
   e.g. i18n         e.g. multi-signal   e.g. any subsystem  e.g. Supervisor
   milestone (§11)    discovery (§9)      adopting §17-22     impasse wiring (§13)
         │                 │                 │                   │
         └─────────────────┼─────────────────┴───────────────────┘
                           ▼
                    Integration Gate (§33)
                           │
                           ▼
                    Architecture Freeze (§39)
```

---

# 31. Milestone Ownership & Dependency Matrix

| Contract | Owner (this K4.2 baseline session) | Extension rights (future milestones) | Breaking-change rule |
|---|---|---|---|
| `Goal.structured_form` shape | Goal Formation | May add new optional keys | May **never** change `description`'s source rule (§6.1) without Architecture Review |
| `CapabilityContract` | Capability Discovery | May add new optional fields (matches §7's own pattern) | May never repurpose `description`'s meaning |
| `CapabilityMatch`/evidence signals | Capability Discovery | May add new `signal` values | May never remove `general_purpose` without a replacement rescue mechanism for zero-lexical-overlap queries (this is the load-bearing fix for K42-002 — removing it silently reintroduces the defect) |
| `FailureRecord` | Diagnostic System (new, this document) | Any subsystem may add `reason_code`s under its own namespace segment (§18.3) | May never add a required field without a default — every future consumer must keep working unmodified |
| Recovery Budget shape | Planner/Supervisor (§12.3) | None — single authority, not extensible per K42-S10 | Any second, independent retry counter anywhere is itself a violation |

---

# 32. Contract Change-Control Protocol

**[REC]** Task brief §36 classification, applied concretely to this document's own proposals so future sessions have a worked example, not just a category list:

| Category | Examples from this document |
|---|---|
| **Independently safe** | `_capability_match_score` → `_capability_match_signals` internal refactor; adding a new `PROVIDER.*` reason code; performance tuning of `list_capabilities()`'s scan |
| **Compatibility-sensitive** | Adding `CapabilityContract.aliases`/`domain_tags`/`is_general_purpose` (§7 — new optional fields, existing callers unaffected, but every future capability registration should consider populating them) |
| **Architecture review required** | §16.2's `LearningRecord`/`LearningCandidate` domain-model reconciliation; any change to `description`'s single-source rule (§6.1); any change to which failure classes are `recoverable` by default (§18.1) |
| **Forbidden without explicit architecture decision** | A second recovery-budget counter anywhere; a capability-relevance signal that fires from threshold-lowering rather than declared evidence (K42-S31); any new event transport parallel to `EventStream` (§17.4) |

---

# 33. Integration Gate

**[REC]** Extends the project's existing nine-step packet process (unchanged steps 1-9) with:

**Step 10 — Diagnostic correctness.** Every new failure-shaped code path introduced by the packet emits a `FailureRecord` under an owned `reason_code`; no free-text-only error field is introduced (K42-S30).
**Step 11 — Cross-milestone correctness.** The packet's own tests plus a fixed regression check: does `Goal.structured_form["description"]` still trace to `raw_request` for all five originally-required test queries (a permanent, cheap, five-line regression suite directly from §4.2's own reproduction table)?
**Step 12 — Architecture correctness.** No contract listed in §31 changed outside its declared extension rights.

This is four additions to an already-working nine-step process, not a new process — consistent with §39's freeze principle (extend, don't rebuild).

---

# 34. K4.2 vs Post-Kernel Boundary

| Capability | K4.2 now | K4.2 future hook | Post-Kernel/K5 | Reason |
|---|---|---|---|---|
| Multi-signal capability discovery (lexical/alias/domain/general-purpose) | ✅ | — | — | §9 — directly fixes K42-002, evidenced by real data |
| Schema/interface compatibility *matching* | Contract field only | ✅ | — | §9.5 — one real capability exists; nothing to test a matcher against yet |
| Semantic/embedding capability matching | — | ✅ (signal slot reserved, §9.2) | Possibly, depending on where C-MoE lands | No evidence yet that lexical+alias+domain is insufficient at real scale |
| Bounded impasse retry via corrected discovery signals | ✅ | — | — | §12 — closes §4.7's confirmed architecture/implementation gap using only what exists |
| Skill Runtime delegation after impasse | — | Explicitly tracked, not built | ✅ K4.3+/K5 | §4.7 — no `SkillRuntime` exists; inventing one now would be exactly the "fabricate a stand-in system" anti-pattern this codebase's own docstrings already declined |
| Capability *selection* among multiple adapters (C-MoE) | — | — | ✅ | Already explicitly deferred (`CURRENT_STATE.md`, `k4_2_4_completion_report.md`) — unchanged by this document |
| Multi-goal execution (compound requests beyond `goals[0]`) | — | Tracked | K4.3 | Already a confirmed-intentional deferral; this document does not expand K4.2's scope to cover it |
| Advanced ontology evolution (merge/alias/lifecycle beyond promote) | — | — | ✅ | §14 only closes the read-wiring gap; promotion/lifecycle logic is untouched and out of scope |
| Diagnostic health rollup / dashboards | — | Reserved (§17.5's "Health State [future]" node) | ✅ | Explicitly excluded, task brief §14/§45 |
| Self Model (autonomous, learned) | — | — | ✅ K5 (frozen) | See §41.6 — a **different**, pre-K4 legacy module of the same name exists and should not be confused with this |

---

# 35. Implementation Phases

**[REC]** Reordered from the task brief's own suggested layering, against this session's actual dependency evidence (the Diagnostic core has no dependency on the Capability Discovery fix, and vice versa — they can run in parallel once each has its own contract frozen at the end of Phase 0):

| Phase | Content | Depends on |
|---|---|---|
| 0 | Architecture & Contract Freeze — this document, reviewed, §16.2's LearningRecord question explicitly decided | — |
| 1 | Goal/Semantic Contract Repair — §6.1's fix + §24's `CONTRACT.GOAL_DESCRIPTION_NOT_RAW_TEXT` regression guard | Phase 0 |
| 1′ (parallel with 1) | Diagnostic Core Foundation — `FailureRecord`, taxonomy, `EventStream` integration, no K4.2-specific wiring yet | Phase 0 |
| 2 | Dynamic Capability Discovery — §9/§10, depends on Diagnostic Core existing so `CAPABILITY.*` codes have somewhere to go | 1′ |
| 3 | Internationalization — §11, additive fields only | Phase 0 (can start anytime after Phase 0) |
| 4 | Impasse & Recovery — §12, depends on both the Goal fix (1) and corrected Discovery (2) being in place, since its retry re-runs Discovery | 1, 2 |
| 5 | Supervisor Integration — §13, depends on 4 | 4 |
| 6 | Intent Ontology read-wiring — §14 | Phase 0 (independent of 1-5) |
| 7 | Canonical construction static tests — §15 | 1, 2 (needs the builders' final call-site shape settled) |
| 8 | Full K4.2 Integration — cross-stage, cross-milestone, regression per §33 | All above |

---

# 36. Parallel-Safe Implementation Packets

**[REC]** Two fully worked packets, in this project's own existing template format (`docs/architecture/IMPLEMENTATION_PACKET_TEMPLATE.md`, confirmed this session), extended with this document's new required sections:

## Packet 10 — Diagnostic Core Foundation

```text
Packet ID:            10
Title:                Diagnostic Core Foundation
Milestone:             K4.2.8 (new)
Owner:                 (assign)
Dependencies:          None (Phase 0 only)
Blocks:                Packets 11, 12 (Capability Discovery, Impasse/Recovery)

Allowed files:          core/diagnostics/ (new), core/observability/tracer.py (read-only import)
Forbidden files:        core/cognitive/*, core/capabilities/*, core/workers/* (no wiring yet — that's Packets 11+)

Contracts consumed:     EventStream.append() (existing, unchanged), tracer.get_trace_id() (existing, unchanged)
Contracts extended:     None (nothing exists yet to extend)
Contracts frozen:       FailureRecord (§19), FailureClass enum (§18.1), reason-code namespace shape (§18.2 — not
                          its full contents, which grow per-subsystem)

Architecture invariants: K42-S27, K42-S28, K42-S30 (§24)
Diagnostic integration:  This IS the diagnostic integration — N/A
Implementation:          FailureRecord dataclass, FailureClass/reason-code constants, diagnostic.* event helpers
                          wrapping EventStream.append()
Local tests:             §25's failure-detection/classification/correlation/causality test classes, against
                          synthetic (non-K4.2) call sites
Boundary tests:          None yet — no consumer exists
Cross-milestone tests:   N/A (first packet in this line)
Acceptance criteria:     FailureRecord round-trips through EventStream; correlation_id matches tracer.get_trace_id()
                          in a threaded async context
Stop conditions:         If EventStream.append()'s existing payload shape cannot represent FailureRecord without
                          a change to EventStream itself — stop, report, do not modify EventStream
Expected final report:   Files touched, new event types registered, zero changes to any existing K4.2 file
```

## Packet 11 — Capability Discovery Multi-Signal Repair

```text
Packet ID:            11
Title:                Capability Discovery Multi-Signal Repair (closes K42-002)
Milestone:             K4.2.4-R (revision)
Owner:                 (assign)
Dependencies:          Packet 10 (Diagnostic Core)
Blocks:                Packet 12 (Impasse & Recovery)

Allowed files:          core/cognitive/planner.py, core/capabilities/capability.py (additive fields only)
Forbidden files:        core/cognitive/intent.py (that's Packet for §6.1 — do not fix K42-001 here even though
                          it's tempting; keep the two independent repairs in independent, separately-verifiable
                          commits, exactly as the original K42 investigation proved them independent)

Contracts consumed:     FailureRecord (Packet 10), CapabilityRegistry's existing API (§4.4 — register_capability,
                          get_contract, get_adapters, list_capabilities — unchanged)
Contracts extended:     CapabilityContract (+ aliases, domain_tags, is_general_purpose, input_schema, output_schema
                          — all Optional/defaulted, §7)
Contracts frozen:       discover_capabilities()'s existing return type List[CapabilityContract] (§10 — CapabilityMatch
                          is additional, not a replacement)

Architecture invariants: K42-S05, K42-S06, K42-S08, K42-S19, K42-S31 (§24)
Diagnostic integration:  CAPABILITY.ZERO_SIGNAL_ALL_CANDIDATES / CAPABILITY.NO_CANDIDATE_REGISTERED (§18.2, §22)
Implementation:          _capability_match_signals() replacing _capability_match_score() internally;
                          CapabilityMatch assembly; is_general_purpose=True set on the LLM_COMPLETION registration
                          in main.py (one-line composition-root change)
Local tests:             §4.2's five-query reproduction table, now asserting non-impasse; §26's mocking-policy
                          compliant integration tests
Boundary tests:          Planner's existing consumption of discover_capabilities()'s return value is unchanged
                          (signature-compatible)
Cross-milestone tests:   Full existing 1048-test baseline still passes
Acceptance criteria:     All five originally-required test queries no longer impasse; min_score=0.01 gate at the
                          _decompose() call site is unchanged (not lowered — this is checked explicitly, not just
                          assumed)
Stop conditions:         If achieving non-impasse requires lowering min_score below 0.01 rather than adding a
                          signal — stop, this violates K42-S31, report instead of proceeding
Expected final report:   Files touched, exact diff of main.py's LLM_COMPLETION registration, before/after Jaccard
                          vs. aggregate scores for all five required queries
```

---

# 37. Future Claude Session Guardrails

**[REC]** Task brief §52's nineteen-point checklist, adopted, with the project's own existing discipline (memory: "Phase 0 reality audit is non-negotiable... code is ground truth... discrepancies are reported, never silently resolved") cited as the reason each point is not new practice, only made explicit for this workstream specifically:

1. Read this document's contract baseline (§6-16, §19) before touching code.
2. Re-run this session's own Phase 0 pattern: fresh clone, `git status --short` clean before and after, read the actual file before trusting this document's line numbers (they will drift as the codebase changes).
3. Confirm your packet's `Allowed files` still matches reality — if a prior packet already touched a file this packet expected to own alone, stop and report (§53).
4-5. Identify consumed/extended contracts using §31's matrix as a starting index, not a final answer — verify against the live registry of what other in-flight packets have already claimed.
6. Stop if a breaking change to a **frozen** contract (§31, rightmost column) appears necessary — this is not a judgment call to make solo.
7-10. Implement only within packet scope (§36's two worked examples show the granularity expected); no unrelated refactors; never weaken a test to make it pass; never engineer a mock to force success (§26).
11. Every new failure-shaped code path gets a `FailureRecord` (§22) — this is now as mandatory as event emission already is under Law 2.
12-14. Run local, boundary, and invariant tests (§24-25) before reporting done.
15. Verify `git status --short` clean if this was a read-only session; verify only the intended files changed if not.
16-19. Report exact files/functions touched, contract impact, diagnostics added, and any discrepancy found — using this document's own evidence-tagging convention (`[FACT]`/`[ARCH]`/`[AUDIT]`/`[INFER]`/`[REC]`) so the next session can tell what was verified versus proposed.

---

# 38. Final Acceptance Checklist

- [ ] Git integrity — repository state matches the packet's own `Allowed files` declaration, nothing else touched
- [ ] Unit correctness — affected components' own tests pass
- [ ] Contract correctness — §31's invariants hold for every contract touched
- [ ] Boundary correctness — §23's matrix still describes reality at every adjacent stage
- [ ] Diagnostic correctness — every new failure path has a `FailureRecord` under an owned `reason_code`
- [ ] Recovery correctness — §12.3's single counter is the only counter; no second retry loop exists anywhere in the diff
- [ ] Regression correctness — full existing suite (1048 tests, per `CURRENT_STATE.md`) passes; §4.2's five-query table specifically re-verified non-impasse
- [ ] Cross-milestone correctness — no previously-completed packet's own acceptance criteria now fail
- [ ] Architecture correctness — no contract changed outside its declared extension rights (§32)
- [ ] Governance correctness — no `GovernanceKernel` bypass; `SupervisorWorker`/Diagnostic System still produce no verdict of their own (K42-S11/S12/S28)

---

# 39. Architecture Freeze Definition

**[REC]** Directly reusing PROJECT_INSTRUCTIONS §20.5's own Architecture Freeze Principle, applied to the specific contracts this document introduces or touches:

**May change without review:** internal implementation of `_capability_match_signals()`'s exact weighting; `FailureRecord.evidence`'s exact key names within a subsystem's own namespace; performance optimizations that preserve every field's meaning.

**Architecture review required:** anything in §32's third row; the exact value of `is_general_purpose`'s baseline score (§9.4 — left as a tunable constant on purpose, but *changing* it once set is a semantic change to how aggressively the rescue signal fires, not a pure performance tweak); `FailureRecord`'s field list itself (§19.2).

**Forbidden without an explicit architecture decision:** everything in §32's fourth row; silently picking a side in §16.2's `LearningRecord`/`LearningCandidate` question without recording the decision; any `SupervisorWorker` or Diagnostic System change that grants either one governance authority it does not have today.

---

# 40. Final Verdict

**What must be redesigned?** Nothing at the type/contract level. `Goal`, `Intent`, `CapabilityDiscoveryRequest`, `PlannerRequest`/`Result`, `ExecutionPlan`, `CompilationResult` all keep their current shape. What must be redesigned is the **population** of one field (`structured_form["description"]`, §6.1) and the **signal set** behind one function (`_capability_match_score` → multi-signal, §9).

**What can remain unchanged?** Candidate generation's relevance/availability split (§9.1); `SupervisorWorker`'s existing two input paths and its K4 §16 invariant-9 structural guarantee (§13); `build_planner_request()`/`build_capability_discovery_request()` as the canonical construction path (§15); the entire Governance/Compilation gate (§8); `CapabilityRegistry`'s existing API (§4.4).

**What must be migrated?** Nothing requires a data migration — every proposed field is additive with a default. The one open question (§16.2) is a *decision*, not a migration, until that decision is made.

**What should be implemented now?** §6.1's description-source fix + its permanent regression guard; §9.4's `is_general_purpose` signal; the Diagnostic Core (§17-22) at the scope §22 defines and nowhere wider; §12's bounded impasse retry; §14's Intent Ontology read-wiring.

**What should be a future hook?** Schema/interface matching (§9.5); semantic/embedding capability matching (§9.2, §11.5); constraint-aware scoring (§9.3); health rollup (§17.5).

**What should be deferred to Post-Kernel/K5?** Skill Runtime delegation after impasse (§34); capability *selection* among multiple adapters (already deferred, unchanged); advanced ontology lifecycle beyond promote/read (§14); anything resembling the K5 "Self Model" concept — see §41.6 for why this needs a careful, separate look, not a K4.2-scope decision.

**What belongs to the OCBrain-wide Diagnostic System?** `FailureRecord`, the failure-class taxonomy (§18.1), the reason-code namespace *shape* (§18.2 — not its full contents, which every subsystem grows on its own schedule), correlation/causality (§20), the `diagnostic.*` event family (§21).

**What belongs only to K4.2?** The specific reason codes under `INTENT.*`/`GOAL.*`/`PLANNER.*`/`CAPABILITY.*` this document defines (§18.2); the Recovery Budget's specific counter shape (§12.3 — a pattern other subsystems may copy, not a shared mechanism they call into).

**What can be parallelized safely?** Per §35's phase graph: Diagnostic Core (Phase 1′) and the Goal-description fix (Phase 1) are fully independent and can run in two parallel sessions today. Internationalization (Phase 3) and Intent Ontology read-wiring (Phase 6) are independent of everything except Phase 0.

**What cannot be parallelized without coordination?** Capability Discovery's multi-signal repair (Phase 2) needs Diagnostic Core's contract frozen first (its new `CAPABILITY.*` codes need somewhere real to go, even if the events aren't wired to a live consumer yet). Impasse & Recovery (Phase 4) genuinely depends on both the Goal fix and the Discovery fix landing first, because its one bounded retry re-runs corrected discovery against a correctly-populated Goal — testing it against either unfixed dependency would validate the wrong thing.

**What contracts become frozen?** `FailureRecord`'s field list; `description`'s single-source rule; the `min_score=0.01` gate's *purpose* (its exact numeric value is tunable, but "distinguishes zero-signal from weak-signal" is not); `SupervisorWorker`'s no-independent-governance-authority guarantee.

**What changes require architecture review?** §32's third-row list, concretely: the `LearningRecord`/`LearningCandidate` reconciliation (§16.2), `is_general_purpose`'s baseline weight once set, and any future proposal to let a failure class other than `RECOVERABLE_FAILURE` participate in bounded retry.

**How does the design prevent future milestones from silently breaking earlier milestones?** Every contract in §31 has an explicit extension-rights row; §33's Integration Gate adds a permanent five-query regression check (§4.2's own reproduction, made durable) that any future packet must pass; canonical-construction static tests (§15) make "only the builder constructs this type" provable, not just currently-true.

**How does the Diagnostic System prevent blind debugging?** Every failure gets a `reason_code` from a shared, dot-namespaced taxonomy instead of a free-text string invented at the call site (§4.9's exact, confirmed problem); `correlation_id` + `causal_parent` make "what happened first, what resulted from it" a query against existing `EventStream` infrastructure (§20) instead of a manual reconstruction from scattered logger calls.

**Why is this architecture durable?** Because, verified against this repository's own actual code rather than assumed: every load-bearing piece it depends on already exists, is already tested, and is already the pattern this codebase reaches for on its own (the `Adapter` health/cooldown pattern, the `tracer.py` correlation ID, the static-identifier test idiom, the additive-dataclass-field convention used throughout `intent.py`/`planner.py`/`compiler.py`). This document adds one new contract (`FailureRecord`) and one new signal-class concept (multi-signal capability matching) — everything else is extension of what was already there, verified working, before this session began.

---

# 41. Supplementary Recommendations (Beyond the Original Task Scope)

Everything above answers the task brief as specified. Everything below is this document's own set of additional suggestions, found as a byproduct of the Phase 0 investigation, offered because they are cheap, evidenced, and directly adjacent to this workstream — not because they were asked for. None of them are assumed accepted; each is a standalone proposal.

**41.1 — Stress-test the multi-signal redesign against a second real capability before declaring it done.** Every finding in §4.2 and every fix in §9 was validated against a **degenerate one-capability system**. `modules/web_search/` already exists in this repository (confirmed this session, directory present) and `CapabilityType.WEB_SEARCH` is already declared (`capability.py:71`, currently unregistered). Registering a second real `CapabilityContract` — even a minimal one — before Packet 11 (§36) is marked complete would turn the multi-signal scoring from "passes five known queries against one contract" into "correctly *discriminates* between two genuinely different capabilities," which is a meaningfully stronger proof and costs roughly one additional `CapabilityContract` registration plus a handful of new test queries.

**41.2 — Use `graphify`/`graphifyy` to generate, not hand-maintain, the Boundary Contract Matrix and dependency graphs.** This project already has AST-based codebase-graph tooling in its toolchain (per established project practice). §7's contract dependency graph and §23's boundary matrix are exactly the kind of artifact that drifts silently the moment someone edits a call site without updating the doc — which is precisely the "doc/reality lag" pattern `CURRENT_STATE.md` itself has already caught and corrected multiple times (its own changelog: K4.2.3, then K4.2.4/K4.2.5, then K4.2.6/K4.2.7 rows were each added late, "corrected via direct code audit, not by trusting any prior report's claim"). A `graphify`-generated cross-check — even just "which functions construct a `CapabilityDiscoveryRequest`" or "which functions call `event_stream.append`" — run as part of the Integration Gate (§33) would catch that class of drift mechanically rather than relying on the next session's own manual reality audit to catch it again.

**41.3 — `core/meta/self_model.py` is very likely legacy, pre-K4 code that happens to share a name with the frozen K5 "Self Model" concept — worth a deliberate housekeeping decision, not a silent assumption either way.** This session inspected the file directly: it is a 112-line static dict (`SELF_MODEL = {"identity": {"version": "3.01", "current_phase": 4}, ...}`) with two small update functions — no learning, no autonomous reasoning, no proactive initiation. The version string ("3.01") predates this repository's own v4.1 numbering, which strongly suggests this is a carried-forward OCBrain v3.x artifact, not an implementation of K5's Self Model. **This document does not claim it violates the K5 freeze** — it hasn't been read closely enough to claim that, and a static status dict is a plausible, freeze-compatible thing for a v3-era build to have had. It is flagged only because *the name alone* is exactly the kind of thing that could cause a future session — human or Claude — to either (a) mistakenly treat this file as evidence K5 work has already started, or (b) mistakenly extend it, thinking it's a harmless legacy stub, and accidentally build toward K5 territory without the explicit K5-boundary stop the Constitution requires. A short, dedicated audit (rename, archive, or explicitly document as "pre-K4 legacy, unrelated to K5 Self Model, retained for X reason") would close this ambiguity cheaply.

**41.4 — Diagnostic Core (Packet 10) is a natural, low-cost opportunity to close DEBT-008 at the same time.** `KNOWN_ISSUES.md` DEBT-008 notes `EventStream` has no dedicated test coverage of its own — every existing test exercises it only incidentally as a constructor dependency. Packet 10's own correlation/causality tests (§25) already need to exercise `EventStream.append()`/`query()` directly and in sequence to prove `correlation_id` threading works — extending that same test file to also directly cover `create_checkpoint()`/`get_checkpoint()`/replay (which Packet 10 doesn't otherwise need) would close DEBT-008 as a two-or-three-test-case addition riding on infrastructure Packet 10 is building anyway, rather than a separate future effort.

**41.5 — The three-way event-mechanism fragmentation (`EventStream`/`KnowledgeEvent`/`EventBus`, DEBT-004/DEBT-005) is out of scope for K4.2 but this document's own §17.4 decision is a small, concrete data point for whenever that consolidation is scheduled:** the Diagnostic System found `EventStream`'s existing `payload=`/`source=` shape sufficient for every K4.2 diagnostic need with zero extension required. That's mild evidence (not proof) that `EventStream` is the right long-term consolidation target between the three, for whoever eventually scopes that DEBT item.

**41.6 — `compile(..., clarification_attempt=...)`'s stub parameter (noted in `CURRENT_STATE.md` as "exists as a stateless parameter for a future caller that doesn't exist yet") is a small Law 4 (Determinism/Explicitness) friction point worth resolving one way or the other during Phase 4/5 (§35) rather than carrying indefinitely: either wire it to §12.3's Recovery Budget (it may be the same concept, arrived at from the compilation side rather than the planning side — worth checking before building a second one) or remove it until a real caller exists. This document does not resolve it here — it wasn't in scope, and resolving it requires reading `compile()`'s full call graph, which this session did not do — but flags it because the pattern ("a parameter that exists for a caller that doesn't exist yet") is exactly adjacent enough to §12.3's own new counter that a future session should check for accidental duplication before adding a second recovery-tracking field.

**41.7 — Once this workstream lands, the Documentation Infrastructure Phase (PROJECT_INSTRUCTIONS §18.5) trigger condition is close to met.** That phase is scheduled "after completion of... the current audit remediation work" — this document *is* that audit remediation's specification. `PROJECT_INDEX.md` already exists (confirmed this session); a `docs/architecture/decisions/` directory already exists but this session did not open it to confirm whether it already serves the `ARCHITECTURE_DECISIONS.md` role PROJECT_INSTRUCTIONS §18.4.2 describes, or whether that file still needs to be created separately — worth a five-minute check before the Documentation Infrastructure Phase formally opens, so it doesn't duplicate a directory that already does the job.

---

*End of specification.*

**Read-only compliance, restated:** `git status --short` was empty at session start and remains empty now — confirmed immediately before this document was written. No file in `/home/claude/audit/repo` was modified, no branch was created or switched, no commit was made, no patch was generated or applied. This entire document was produced from direct reading of the repository as it exists on `origin/main` at commit `2778b26`.
