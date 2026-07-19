# OCBrain K4 — Cognitive Runtime Architecture

**Date:** July 18, 2026
**Status:** Architecture Only — zero code, zero patches, zero Kernel modifications. Ready for milestone-by-milestone implementation review, not for direct implementation.
**Precedence:** Subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md` and `PROJECT_INSTRUCTIONS.md`. Everything below is Architecture Specification (Constitution Part VIII), freely revisable without amending either.
**Method:** Every claim about current repository state was verified directly against source in a fresh clone (`HEAD cc2214a`) before this document was drafted, not assumed from prior sessions.

---

## 0. Kernel Status — Correction and Basis for This Document

The directive that requested this document opens by asserting the Kernel has "reached architectural stability" and "MUST now be treated as frozen." A follow-up message asked for a bounded, 14-claim verification with an explicit instruction: if a claim is false, stop and report before proceeding.

The verification was performed. All 14 individually-listed technical claims are confirmed true directly against source:

| # | Claim | Verified |
|---|---|---|
| 1 | Governance wired into worker execution | ✅ `core/workers/base.py:222` — Template Method pattern, `execute()` calls `evaluate_action()` before `_run()` |
| 2 | Governance wired into orchestrator execution | ✅ `core/orchestrator.py:200` |
| 3 | Governance wired into UnifiedMemory write/update/delete | ✅ `core/memory/unified_memory.py:441,748,869` |
| 4 | BudgetGovernor metadata propagates end-to-end | ✅ true as literally worded — with the caveat already on record: propagation is real, accumulation is not (nothing anywhere increments `step_count`/`token_spend` past `0`/`0.0`; re-confirmed by fresh repo-wide search) |
| 5 | UnifiedMemory is the single memory authority | ✅ no other module writes to storage backends directly |
| 6 | WorkflowRuntime is the sole workflow coordinator | ✅ one class, `core/workflow/runtime.py:81` |
| 7 | ExecutionRuntime is the sole worker execution runtime | ✅ one file, `core/runtime/execution_runtime.py` |
| 8 | Capability execution owned by AdapterRuntime | ✅ one implementation, `core/capabilities/adapter_runtime.py` |
| 9 | EventStream is the durable kernel event system | ✅ one class, SQLite WAL-backed |
| 10 | EventBus is the application signalling mechanism | ✅ pure in-memory handler dict, no persistence |
| 11 | Kernel ownership boundaries unchanged | ✅ composite of 1–10 |
| 12–14 | State documents reflect the repository | ✅ internally consistent with everything above |

**One discrepancy, reported rather than silently resolved either way:** the premise "this work continues after the completion of K3" does not hold. K3 (Kernel Compliance Audit) is listed as `⬜ Next` in both `CURRENT_STATE.md` and `IMPLEMENTATION_ROADMAP.md`, unchanged as of this session. K3.5 and K3.5.1 are genuinely complete; K3 itself — whose own defined scope is "verify implementation against Constitution and Architecture spec" — has not been performed, and covers ground this 14-item checklist does not: `KNOWN_ISSUES.md` DEBT-002 (AgentGovernor delegation dormancy), DEBT-003 (checkpoint/resume absent), DEBT-008 (EventStream has no dedicated tests), and DEBT-009 (a canonical spec and a committed code module both assume an unratified Constitution amendment) are all still open and untouched by the 14 verified claims.

**Basis this document proceeds on:** the 14 verified technical facts are a legitimate, sufficient basis for treating *these specific ownership boundaries* — governance wiring, single-authority ownership of Memory/Workflow/Execution/Capability/Events — as stable enough to design a new layer against. That is a narrower, honest claim than "the Kernel has passed formal compliance audit and is closed," and this document does not assert the latter anywhere below. Where this document says "the Kernel is stable for this purpose," it means the verified boundaries above — not a K3 sign-off that hasn't happened. This distinction matters and is preserved throughout.

Because K4 as scoped is architecture-only — zero Kernel modifications, zero implementation — nothing above blocks the work requested. It does mean K3 should still happen before any of this document's roadmap (§19) begins landing code, since several of its milestones touch exactly the still-open ground K3 would examine.

---

## 1. Cognitive Runtime Specification

**Purpose.** The Cognitive Runtime is the layer that decides what should happen. The Kernel is the layer that makes what's decided actually happen, safely, governed, and replayably. This is a direct restatement of the directive's own Core Principle, and it is the only sentence this entire document needs to stay consistent with.

**Ownership.** The Cognitive Runtime permanently owns: intent interpretation, goal formation, planning, plan compilation (the translation step, not execution), reflection, evaluation, and supervision of cognitive workers. It never owns: memory persistence, governance, workflow execution, capability execution, or event persistence. Those five remain exactly where they are today — `UnifiedMemory`, `GovernanceKernel`, `WorkflowRuntime`/`ExecutionRuntime`, `AdapterRuntime`, `EventStream`.

**Boundary, stated precisely.** The Cognitive Runtime produces a `WorkflowDefinition` (already the Kernel's own, existing execution contract — §6). It never constructs a `WorkflowNodeState`, never calls `WorkflowRuntime.execute()`'s internal `_execute_from()`, never touches a storage backend, never emits an `EventStream` event under its own authority (it requests emission through the same worker-lifecycle path every other worker already uses). Everything the Cognitive Runtime does to affect the world outside itself happens by handing the Kernel an artifact the Kernel already knows how to consume.

**Public interfaces.** Two, deliberately: `plan(goal: Goal) -> ExecutionPlan` (Planner) and `compile(plan: ExecutionPlan) -> WorkflowDefinition` (Plan Compiler). Everything else — Reflection, Evaluation, Supervision — consumes Kernel-emitted events and produces artifacts; none of them expose a synchronous "do this" entrypoint that anything outside the Cognitive Runtime calls directly, because nothing outside it should be able to trigger reflection or evaluation as a side effect of an unrelated action. They are triggered by the pipeline (§2), not called ad hoc.

**Internal modules.** §3 derives the minimal set; the answer is seven, not the thirteen candidates the directive lists as possibilities.

**Lifecycle.** One Cognitive Runtime "session" spans exactly one Intent-to-Response cycle. It has no life before the Intent arrives and no life after the Response is assembled — anything that needs to survive past that boundary is either written to `UnifiedMemory` (permanent) or discarded (Working Cognitive State, §10). This mirrors the Kernel's own Worker lifecycle discipline exactly (`WorkerState`: fresh instance per invocation, no hidden state outside of resources) rather than inventing a second lifecycle model.

---

## 2. Cognitive Execution Model

```
User Intent                                                    [User]
     │
     ▼
Intent Interpretation ──────────────────────────  [Cognitive Runtime: Intent Interpreter]
     │  produces: Intent (raw, timestamped)
     ▼
Goal Formation ──────────────────────────────────  [Cognitive Runtime: Intent Interpreter]
     │  produces: Goal (verified, references originating Intent)
     ▼
Planning ────────────────────────────────────────  [Cognitive Runtime: Planner]
     │  produces: ExecutionPlan (candidate steps, confidence, alternatives, justification)
     ▼
Plan Compilation ────────────────────────────────  [Cognitive Runtime: Plan Compiler]
     │  produces: WorkflowDefinition (Kernel's existing DAG contract)
     │  GOVERNANCE GATE: evaluate_action(action_type="plan_compile") — §15
     ▼
Kernel Execution ────────────────────────────────  [Kernel: WorkflowRuntime → ExecutionRuntime]
     │  unchanged. Every node invocation independently governed, exactly as today.
     ▼
Observation ──────────────────────────────────────  [Kernel emits; Cognitive Runtime observes]
     │  EventStream events (workflow.*, worker lifecycle) — no new monitoring layer (§3, Execution Monitor rejected)
     ▼
Evaluation ───────────────────────────────────────  [Cognitive Runtime: EvaluatorWorker]
     │  produces: EvaluationRecord (scored against the originating Goal/Plan)
     ▼
Reflection ───────────────────────────────────────  [Cognitive Runtime: ReflectionWorker]
     │  produces: ReflectionRecord (critique, retry/replan/accept decision)
     ▼
Memory Update ────────────────────────────────────  [Cognitive Runtime decides what; Kernel: UnifiedMemory owns the write]
     │  selective promotion via MemoryCuratorWorker's existing methods — §13
     ▼
Response ─────────────────────────────────────────  [Cognitive Runtime assembles; delivery is presentation-layer, outside K4's scope]
```

**Cross-cutting, not a pipeline stage:** Supervisor watches Planning → Compilation → Execution and intervenes on failure (retry, replan, escalate). It is drawn as cross-cutting deliberately — placing it as a linear stage would misrepresent it as something that runs once per cycle, when its actual job is to be watching throughout.

**Every transition's owner is stated above explicitly** per the directive's own requirement. Two transitions deserve a specific note:

- **Plan Compilation → Kernel Execution** is the single load-bearing seam in this entire model. It is the only point where a Cognitive Runtime artifact becomes a Kernel-executable one, and it is therefore the only point that needs a governance gate specific to this new layer (§15). Every other Kernel-facing action in this pipeline (each worker invocation during Kernel Execution) is already governed by the existing, unmodified per-worker path.
- **Response** is drawn as owned by the Cognitive Runtime for *synthesis* (turning the Evaluation/Reflection outcome into a coherent answer — literally what `merger.merge()` already does inside today's `PlannerWorker._run()`, so this is not a new concept, only a relocated one), but *delivery* (the actual transport of that answer back to the caller) is interface-layer plumbing that predates and sits outside both the Kernel and the Cognitive Runtime. This document does not design it.

---

## 3. Runtime Components — Minimal Architecture

The directive lists thirteen candidates and explicitly asks that not all be assumed necessary. Applying the same discipline `OCBRAIN_K1.6_RESOURCE_MODEL.md` applied to its own candidate list — every field proven or rejected, not just renamed — seven survive:

| Component | Verdict | Reason |
|---|---|---|
| **Intent Interpreter** | **Keep** | Genuine entry point; nothing downstream has a Goal to work from without it. |
| **Planner** | **Keep** | Explicitly the evolution target named in the directive's own §4 (Worker Evolution). |
| **Plan Compiler** | **Keep** | The one component that makes "planning never executes" structurally true rather than aspirational — it is the seam, not a redundant layer (§6). |
| Reasoner | **Reject** | Would duplicate what Planner (forward reasoning about what to do) and Reflection (backward reasoning about what happened) already do between them. A generic "Reasoner" sitting alongside both is an unbounded, undifferentiated component — exactly what `PROJECT_INSTRUCTIONS.md` §20.5 calls a "magical abstraction." |
| **Reflection Engine** | **Keep, folded into ReflectionWorker** | Not a separate class. `PROJECT_INSTRUCTIONS.md` §7.1 already names `ReflectionWorker` canonically; the directive's own §4 asks how it should *behave*, implying the worker itself is the mechanism, not a wrapper around it. |
| **Evaluator** | **Keep, folded into EvaluatorWorker** | Same reasoning — already canonical, already named. |
| **Supervisor** | **Keep, folded into SupervisorWorker** | Same reasoning — already canonical, already named, and already the explicit target of `PROJECT_INSTRUCTIONS.md` §7.1's eighth worker type. |
| Goal Manager | **Reject, folded into Working Cognitive State** | A standing manager for something that lives for one session and has no cross-session persistence requirement anywhere in this project's documented scope is unproven complexity. The Goal is a field inside Working Cognitive State (§10), produced once by Intent Interpreter, read by Planner. Inventing a manager class for a single mutable field mirrors exactly the over-fitted lifecycle machine K1.6 rejected for Resources. |
| **Working Context Manager** | **Keep, renamed — this IS Working Cognitive State** | Same concept, one name, not two (§10). |
| Plan Compiler | *(counted once above)* | — |
| Execution Monitor | **Reject** | `EventStream` already captures every workflow/worker lifecycle transition. A separate Execution Monitor would duplicate that capture path. Supervisor subscribes to existing events directly; it does not need its own monitoring subsystem to watch. |
| Confidence Engine | **Reject, folded into artifact fields** | Confidence is not a standing service — it is a field Planner populates on `ExecutionPlan` and a field EvaluatorWorker populates on `EvaluationRecord` (tracking predicted-vs-actual over time is EvaluatorWorker's own calibration responsibility, not a separate engine's). |
| Self Critique | **Reject — this is Reflection** | `PROJECT_INSTRUCTIONS.md` §7.3 already defines Reflection as "critique outputs, detect inconsistencies, validate reasoning" — Self Critique is that definition restated, not an additional component. |
| Decision Engine | **Reject** | Decision-making is already distributed correctly: Planner decides what to attempt, Supervisor decides how to recover, Governance decides what's permitted. A standing "Decision Engine" would either duplicate one of these three or become the kind of unscoped catch-all `PROJECT_INSTRUCTIONS.md` §20.5 forbids. |

**Final component set (7):** Intent Interpreter, Planner, Plan Compiler, ReflectionWorker, EvaluatorWorker, SupervisorWorker, Working Cognitive State.

---

## 4. Worker Evolution

**Should PlannerWorker become a real planner?** Yes, and the current implementation makes the gap concrete rather than abstract. `core/workers/planner.py::_run()` — read directly, not summarized — is the legacy `Orchestrator.handle()` classify→dispatch→merge pipeline moved into worker form verbatim (its own docstring: *"This is the legacy Orchestrator.handle() logic, moved here to make it governable"*). It parses a query, classifies it into module labels via `classifier_v3`, dispatches to modules in parallel, and merges results. There is no goal decomposition, no task sequencing, no constraint analysis, no capability-selection reasoning, no confidence estimation, no alternative-plan generation anywhere in it. §5 designs what replaces this.

**How should ReflectionWorker behave?** It does not exist yet as a class (confirmed absent, `core/workers/` contains exactly two worker subclasses: `PlannerWorker`, `MemoryCuratorWorker`). Its behavior is specified in §7.

**What responsibilities belong to EvaluatorWorker?** Also does not exist yet. Specified in §8.

**How does SupervisorWorker coordinate failures?** Also does not exist yet. Specified in §9.

**Should BrowserWorker and CoderWorker remain ordinary workers?** Yes, unambiguously. They *execute* — browse, write code — they do not *reason* about what should happen. Per the Core Principle, that places them on the Kernel-facing execution side of the boundary, invoked as ordinary `WorkflowNode`s by a compiled plan, exactly as any worker is invoked today. Nothing about K4 changes them.

**Should workers become stateless?** They already are, and this document changes nothing about that. `WorkerState` is per-invocation; the Constitution's own "no hidden state outside of resources" principle already governs this. Planner, ReflectionWorker, EvaluatorWorker, and SupervisorWorker must follow the identical discipline: any state that needs to persist across one worker's own invocation boundary lives explicitly in Working Cognitive State (inspectable, session-scoped) or `UnifiedMemory` (persistent), never in an instance attribute.

**Should workers produce cognitive artifacts?** Yes, and the Kernel already has the exact slot for this with zero schema change required: `WorkerResult.artifacts: Dict[str, Any]` (`core/workers/base.py:111`), documented in its own docstring as "Named outputs (files, data structures) produced." `ExecutionPlan`, `ReflectionRecord`, and `EvaluationRecord` are serialized into this field by the worker that produces them. This is confirmed, not proposed — the field already exists, already typed generically enough to carry structured artifacts, already flows through the same governed `execute()` path every worker uses.

**A boundary case worth naming precisely: `MemoryCuratorWorker`.** Its passive hooks (`_before_write_hook`, `_before_delete_hook`) are Kernel-adjacent structural gates and stay exactly as they are. Its active methods — `prune_stale()`, `strengthen_high_access()`, `resolve_contradictions()` — already exist, are already real (not stubs), and already involve judgment (which entries to prune, which connections to strengthen). These sit at the Kernel/Cognitive boundary rather than cleanly on one side. §15 addresses the specific, concrete gap found in them.

---

## 5. Planning Model

`Planner` replaces `PlannerWorker._run()`'s classify-and-dispatch body with a real decomposition pipeline, while keeping the same worker shell (governed `execute()`, event emission, `WorkerResult` output) unchanged:

```python
# Illustrative signature only — not implementation.
async def plan(self, goal: Goal, context: WorkingCognitiveState) -> ExecutionPlan:
    candidate_steps   = self._decompose(goal)              # goal → ordered tasks
    constraints        = self._extract_constraints(goal)     # what limits the plan
    capabilities        = self._select_capabilities(candidate_steps)  # via CapabilityRegistry.resolve() — unmodified
    ordering            = self._sequence(candidate_steps, constraints)
    fallbacks           = self._fallback_paths(ordering)      # per-step error_branch candidates
    confidence          = self._estimate_confidence(ordering, capabilities)
    alternatives        = self._alternative_plans(goal, top_n=2)  # generated, not necessarily compiled
    return ExecutionPlan(goal_id=goal.resource_id, steps=ordering,
                          confidence=confidence, alternatives=alternatives,
                          justification=self._justify(ordering, constraints))
```

**Capability selection reuses `CapabilityRegistry.resolve()`/`AdapterRuntime` exactly as they exist today** — Planner asks "what can do this," the existing registry answers, Planner does not maintain its own parallel notion of what capabilities exist (per §14, this is the one rule that keeps this section from redesigning Capability Runtime by accident).

**Are plans immutable artifacts?** Yes, once compiled. An `ExecutionPlan` is mutable while Planner is still assembling it (a local, in-progress object); the moment it is handed to Plan Compiler and passes the governance gate (§15), the resulting `WorkflowDefinition` is exactly as immutable as any other `WorkflowDefinition` already is today — nothing about `WorkflowRuntime` changes, so nothing new needs to be invented to make this true. The `ExecutionPlan` object itself, if promoted to memory (§13), is written once and superseded by a new entry on revision, matching `KnowledgeEntry.supersedes` — never edited in place.

---

## 6. Execution Plans

**Ownership.** `ExecutionPlan` is a Cognitive Runtime artifact, produced by Planner, consumed by Plan Compiler. It is never touched by `WorkflowRuntime`.

**Structure** (illustrative fields, not a frozen schema):

```python
@dataclass
class ExecutionPlan:
    resource_id:    str              # identity, per the Resource Protocol naming convention
                                      # already established in core/capabilities/resource.py
    goal_id:        str              # provenance — the Goal this plan satisfies
    steps:          List[PlanStep]   # ordered; each maps to one eventual WorkflowNode
    confidence:     float
    alternatives:   List[str]        # references to alternative ExecutionPlan.resource_id, not embedded copies
    justification:  str              # why this ordering, why these capabilities
    lifecycle_state: str             # draft → compiled → executing → completed | failed | superseded
```

This deliberately follows the naming convention `core/capabilities/resource.py`'s `HTTPClientResource`/`ModelResource` already established (`resource_id`, not `id` or `plan_id`) — reusing an existing convention rather than inventing a third naming scheme, consistent with `OCBRAIN_K1.6_RESOURCE_MODEL.md`'s own Resource Protocol (structural typing, no formal base class required — the same pattern applies here without needing a new `class ExecutionPlan(Resource):` declaration).

**Serialization.** Same discipline `OCBRAIN_K1.6_RESOURCE_MODEL.md` §7 already established for every Resource-shaped object: dataclass, `to_dict()`/`from_dict()` via existing introspection, no new serialization framework.

**Relationship with `WorkflowDefinition`.** One-directional: `ExecutionPlan` compiles *into* a `WorkflowDefinition`; a `WorkflowDefinition` never compiles back into an `ExecutionPlan`. This is deliberate — it is what makes "planning never executes, execution never plans" a structural property rather than a convention someone could accidentally violate. `PlanStep` maps onto `WorkflowNode` roughly 1:1 (`WorkflowNode` is confirmed minimal: `node_id`, `worker_type`, `config`, `retry_policy`, `error_branch` — one worker per node), so Plan Compiler's actual job is narrow: reduce Planner's richer reasoning (candidate alternatives, justification, confidence) down to the single concrete sequence `WorkflowRuntime` already knows how to run, discarding or archiving (not executing) everything that didn't get selected.

**Relationship with `WorkflowRuntime`.** None, directly. `WorkflowRuntime.execute()` receives a `WorkflowDefinition` and has no awareness an `ExecutionPlan` ever existed. This is the entire point of the compilation seam.

**Relationship with `EventStream`.** `plan.compiled` and `plan.rejected` events (§12) are emitted at the compilation seam, carrying the plan's `resource_id` and confidence — enough for a later Reflection/Evaluation pass to look the plan back up without `EventStream` itself needing to know anything about plan internals.

---

## 7. Reflection Architecture

**When does it run?** After execution completes (success or failure), and only there. Not before (there is nothing to reflect on yet — Planner's own confidence estimate serves the equivalent pre-execution role, and duplicating it as a form of "pre-reflection" would blur Planner's and ReflectionWorker's responsibilities). Not continuously (an always-on reflection loop is exactly the unbounded background process `OCBRAIN_EXTERNAL_REPO_STUDY_V3.md`'s Helix-AGI finding flagged as needing governance wrapped around it from day one — Reflection here is invoked once per cycle, at a defined point, not a standing loop).

**What data does it consume?** The `EvaluationRecord` (§8) for this cycle, the `ExecutionPlan` that was compiled, and the `EventStream` events the execution actually produced (via `EventStream.replay()` or a bounded query scoped to this workflow's `workflow_id` — not a new read path, the existing one).

**How does it modify future behaviour?** Indirectly, and only through two existing, governed mechanisms — it does not get a third: (1) it may propose a memory write (a candidate instinct, pattern, or correction) which goes through `UnifiedMemory.write()`'s already-governed path exactly like any other write; (2) on retry/replan, it hands a *new* `Goal` or a *revised* `ExecutionPlan` back to Planner — it does not reach into `WorkflowRuntime` or re-trigger the failed workflow itself.

**How are reflections stored?** As `KnowledgeEntry` instances (§13) — not a new object type. `KnowledgeEntry` already has every field a reflection needs: `content`, `confidence`, `derived_from` (pointing at the evaluation/plan it reflects on — this field already exists precisely for this kind of provenance chain), `truth_status` for whether the pattern has been validated yet.

**How are reflections distinguished from facts?** By `derived_from` being non-empty and by content framing, not by a separate schema. A reflection is a `KnowledgeEntry` whose `derived_from` traces to an `EvaluationRecord`/`ExecutionPlan`, not to an external source. This reuses the existing Truth Framework (`unknown → candidate → verified → conflicted → deprecated`, already the canonical state machine per `OCBRAIN_EXTERNAL_REPO_STUDY.md`'s own already-adopted recommendation to reuse this exact machine for skill/pattern trust rather than inventing a parallel one) rather than a new distinguishing mechanism.

---

## 8. Evaluation Architecture

**Cover:** quality scoring, goal completion, reasoning validation, hallucination detection, tool success, capability effectiveness, confidence calibration, evaluation artifacts — per the directive's own list.

`EvaluatorWorker` produces one `EvaluationRecord` per completed (or failed) execution:

```python
@dataclass
class EvaluationRecord:
    resource_id:       str
    plan_id:            str    # the ExecutionPlan evaluated
    goal_completed:     bool
    quality_score:      float  # pointwise, per the Google GenAI eval pattern already
                                # named in COMPLETE_UNIFIED_STUDY_V3.md's EvaluatorWorker design
    reasoning_valid:    bool
    tool_success_rate:  float  # fraction of invoked capabilities that succeeded
    predicted_confidence: float  # copied from the ExecutionPlan being evaluated
    actual_outcome:     bool   # did it actually succeed
```

**Confidence calibration** is EvaluatorWorker's own standing responsibility, not a separate Confidence Engine (§3): it accumulates `(predicted_confidence, actual_outcome)` pairs over time (queried from past `EvaluationRecord` entries in `UnifiedMemory`, not held in worker state — statelessness, §4) and can compute a calibration score (Brier-style) on demand. This is the calibration pattern already identified and recommended in `OCBRAIN_EXTERNAL_REPO_STUDY_V2.md` Cluster H (Metaculus forecasting-tools) — a distinct evaluation dimension from correctness, folded here into `EvaluatorWorker` rather than a separate component, consistent with §3's rejection of a standalone Confidence Engine.

**Evaluation never changes facts** (§16) — `EvaluatorWorker` writes new `EvaluationRecord` entries; it never edits the `KnowledgeEntry` or event it evaluated.

---

## 9. Supervision Architecture

**Responsibilities:** worker monitoring, plan monitoring, failure recovery, retry strategy, escalation, termination, loop prevention — per the directive's list, each addressed:

- **Worker/plan monitoring:** via `EventStream` subscription, not a redundant Execution Monitor (§3). Supervisor listens for worker-failure and `workflow.*` events already emitted today.
- **Failure recovery / retry strategy:** Supervisor's retry is not a new mechanism — it is a second call to `ExecutionRuntime.invoke()` (for a single failed node) or `WorkflowRuntime.execute()` (for a sub-workflow), exactly as any caller would make. Because every invocation is already independently governed (`Template Method pattern makes bypass structurally impossible`, per `base.py`'s own docstring), a Supervisor-initiated retry gets governance re-evaluated for free — no parallel authorization layer needs to be built.
- **Escalation:** already a first-class Kernel concept — `GovernanceVerdict.ESCALATE`, already used by `EvolutionGovernor` for `requires_approval` actions. Supervisor's job on escalation is to surface it (matching the existing HITL pattern), not to construct a second approval mechanism.
- **Termination:** Supervisor can decide *not* to retry (accept the failure, hand it to Reflection) — it cannot itself terminate a running `WorkflowRuntime` execution; that is `RecursionGovernor`/cancellation-token territory, unchanged.
- **Loop prevention:** Supervisor must not retry a plan Governance already rejected or escalated — see §16's new invariant on this exact failure mode.

**Interaction with GovernanceKernel, avoiding duplicated authority.** Supervisor decides *how* to respond to a failure; GovernanceKernel decides *whether* the resulting action is permitted. These are genuinely different questions and Supervisor must not answer the second one itself — every recovery action it initiates re-enters through the same `evaluate_action()` path everything else does. This is the direct, concrete answer to the directive's own instruction to "avoid duplicated authority": Supervisor has none of its own to duplicate, by design.

---

## 10. Working Cognitive State

**Does the Cognitive Runtime need its own transient reasoning state, distinct from the Kernel's `WorkingMemory`?** Yes — but it is a genuinely different thing from `WorkingMemory` (L0, per `PROJECT_INSTRUCTIONS.md` §8.1: in-process, sub-millisecond, LRU-evicted, general-purpose scratch space any Worker can read/write during *one execution*), not a competing implementation of the same concept.

**Ownership.** The Cognitive Runtime, for the duration of one Intent-to-Response session (§1).

**Lifecycle.** Created when Intent Interpretation begins; discarded when Response is assembled. It does not persist across sessions — anything worth keeping has already been written to `UnifiedMemory` by that point (§13).

**Cleanup.** Unconditional at session end, mirroring `WorkerContext.working_memory`'s own LRU-plus-hard-cleanup pattern (`OCBRAIN_K1.5_KERNEL_API_SERVICE_MODEL.md` §6) rather than inventing a second cleanup discipline.

**Persistence rules.** None by default. Working Cognitive State is never itself written to disk; only specific artifacts it holds (a `ReflectionRecord`, a promoted `ExecutionPlan`) get individually written through `UnifiedMemory`'s governed path when Reflection/Evaluation decide they're worth keeping.

**What it holds:** the current `Intent`, the current `Goal`, the in-progress or most recent `ExecutionPlan`, the most recent `EvaluationRecord`/`ReflectionRecord` for this session. This is the "Goal Manager" and "Working Context Manager" candidates from §3, unified into one thing rather than two, because they were never actually two things — a session-scoped bag of the cognitive artifacts in flight.

**Must never duplicate `UnifiedMemory`.** Enforced structurally, not by convention alone: Working Cognitive State has no `search()` method and no persistence path of its own. Anything that needs to be searchable or to survive past this session must go through `UnifiedMemory.write()` — there is no second store to accidentally duplicate into.

---

## 11. Explainability

This section closes a gap this project has already found and documented, not a hypothetical one. The July 18, 2026 Reality Synchronization pass confirmed directly: no `Explain*` class or module exists anywhere in the repository; `GovernanceResult.reason` gives governance-decision-level explainability only; Constitution Law 6's own example ("before a workflow runs, the kernel can state plainly what it understood the goal to be, and what it's still uncertain about") has no general-purpose implementation anywhere.

**This document's position: explainability is not a component to build (§3 already rejected a standalone Confidence Engine and Decision Engine for the same reason) — it is a property that falls out of the artifacts already specified above, if and only if each one carries its justification as a first-class field rather than reconstructing it after the fact from logs**, which is the literal wording of Constitution Law 6's own Implications clause. Concretely, per the directive's own list:

- **Reasoning chain** → `ExecutionPlan.justification` + the sequence of `PlanStep`s themselves.
- **Selected capabilities** → each `PlanStep`'s resolved capability, already visible in the compiled `WorkflowNode.worker_type`/`config`.
- **Rejected alternatives** → `ExecutionPlan.alternatives`, retained as references even though only one path was compiled and executed.
- **Confidence** → `ExecutionPlan.confidence` (predicted) and `EvaluationRecord.predicted_confidence` vs `actual_outcome` (calibrated, after the fact).
- **Evaluation** → `EvaluationRecord` itself.
- **Reflection** → `ReflectionRecord` itself.
- **Plan evolution** → `KnowledgeEntry.supersedes`, already an existing field, applied to promoted `ExecutionPlan` entries across retries/replans.

No new "Explainability Layer" is proposed. Building one would mean either duplicating data that already lives on these artifacts, or — worse — becoming a second, competing source of truth about *why* a decision was made, which is precisely what Constitution Law 9 (Single Source of Truth) exists to prevent.

---

## 12. Event Integration

`EventStream` is not modified. New event *names* only, following its existing dot-namespaced convention (`workflow.started`, `workflow.completed`, confirmed directly in `core/workflow/runtime.py`) with a `cognitive.` prefix — distinct from the `workflow.` prefix Kernel events already use, and distinct from `KnowledgeEvent`'s separate snake_case convention (`memory_write_rejected`), since these are general operational/reasoning events, not `KnowledgeEvent`'s narrower Memory/L4-Archive-scoped audit facts:

```
cognitive.intent_interpreted
cognitive.goal_formed
cognitive.plan_compiled
cognitive.plan_rejected        # governance REJECT/ESCALATE at the compilation gate, §15
cognitive.plan_executed
cognitive.reflection_completed
cognitive.evaluation_completed
cognitive.supervision_escalated
```

Each is emitted through the same worker-lifecycle event path every existing worker already uses (`emit_progress`/lifecycle events inside `execute()`) — no new emission mechanism, no new subscriber infrastructure. Supervisor (§9) and any future observability consumer subscribe to these exactly as they would to `workflow.*` events today.

---

## 13. Memory Integration

`UnifiedMemory` is not redesigned. This section defines *when* the Cognitive Runtime calls its existing, unmodified interface.

**When memories are searched.** Intent Interpretation (assembling context for Goal formation — reusing the existing `context_assembler`/`RetrievalFusionEngine` path `PlannerWorker._run()` already calls today) and Planning (capability/pattern lookup during decomposition).

**When memories are written.** Not automatically, and not by Planner directly. Writes happen at two points, both post-hoc: (1) Reflection proposing a candidate instinct/correction (§7); (2) Evaluation's outcome being written as provenance for future calibration. Both go through `UnifiedMemory.write()`'s already-governed path (`memory_write`, K3.5) — no second write path is introduced.

**When memories are ignored.** Every intermediate `ExecutionPlan` draft, every rejected alternative, every routine (non-instructive) successful execution. Writing every plan draft to memory would be exactly the "memory without scoring" anti-pattern this project's own external-repo research (`COMPLETE_UNIFIED_STUDY_V3.md` §8) already lists as a documented "don't build" — importance/recency/relevance scoring exists precisely to prevent this, and the discipline here is the same one already governing every other memory write: only write what's worth retrieving later.

**What reflections become memories.** `KnowledgeEntry` instances as specified in §7 — reused schema, not a new one.

**What evaluations become memories.** `KnowledgeEntry` instances with `derived_from` pointing at the plan/execution evaluated, `truth_status` tracking whether the evaluation's own conclusion has itself been validated over time (i.e., did a later, similar plan actually perform as this evaluation predicted).

**What plans become memories.** Only plans a later Reflection or Evaluation judges worth keeping — using `KnowledgeEntry`'s existing `procedure_name` field (confirmed present, `core/memory/knowledge_entry.py:80`, currently populated by nothing) with `layer="l3"`, which is precisely the field this project's own Constitution Rationale already anticipated for procedural-memory content, unused until now. This is the concrete, evidence-grounded instance of "reuse existing Kernel abstractions, do not invent parallel systems" this whole document is built around: a promoted `ExecutionPlan` does not need a new memory-layer concept invented for it — the field was already there.

**Respecting Memory Governance.** Every one of the above writes is a `UnifiedMemory.write()` call and therefore already passes through `GovernanceKernel.evaluate_action()` (K3.5) with zero additional wiring required from this document.

---

## 14. Capability Integration

`CapabilityRegistry`/`AdapterRuntime` are not redesigned. Planner's capability-selection step (§5) calls `CapabilityRegistry.resolve(capability) -> List[CapabilityAdapter]` exactly as it exists today, using whatever health/availability ranking `AdapterRuntime` already applies (confirmed real: `_rank_adapters`, `_health`, `_is_available`, retry through ranked candidates). The Cognitive Runtime's only new relationship to this system is as a *caller* of an interface that already exists — it introduces no second resolution path, no second adapter concept, and no change to the currently-registered `LLM_COMPLETION` capability or its three adapters.

Capability *execution* remains entirely inside `AdapterRuntime`, invoked only as a consequence of a compiled `WorkflowNode` running inside `WorkflowRuntime` — the Cognitive Runtime never calls an adapter directly.

---

## 15. Governance Integration

**Which cognitive actions require governance.** One, primarily: Plan Compilation. This is the moment reasoning becomes a commitment the Kernel will actually execute — the same principle K3.5/K3.5.1 already established for memory (evaluate *before* the consequential transition, not after). Plan Compiler constructs a `GovernanceAction(action_type="plan_compile", metadata={"goal_id": ..., "confidence": ..., "step_count": len(plan.steps)})` and calls `evaluate_action()` before producing the `WorkflowDefinition`. This reuses `AbstractCognitiveWorker.execute()`'s exact, already-proven pattern (REJECT/ESCALATE short-circuits, emits `cognitive.plan_rejected`, §12) — not a new governance mechanism.

**A second, concrete, already-latent gap this design surfaces rather than creates:** `EvolutionGovernor.SELF_MODIFYING_ACTIONS` (`core/governance/governance_kernel.py:243-246`) already contains `memory_curate`, `memory_derive`, `memory_prune`, `memory_merge` — action types the Kernel is already prepared to evaluate. Directly confirmed: `MemoryCuratorWorker.prune_stale()`, `strengthen_high_access()`, and `resolve_contradictions()` — real, existing methods, not stubs — construct no `GovernanceAction` at all today. This predates K4 and is not introduced by this document, but K4 is the layer that will actually exercise these methods with intent (via Reflection/Evaluation's memory-promotion decisions, §7/§13), so it is the right place to name the fix precisely: when the Cognitive Runtime triggers active curation, it should do so through calls that construct `GovernanceAction`s using these *already-existing* action-type strings, closing a gap the Kernel was already built to handle rather than inventing new governance surface area.

**Which runtime artifacts should be evaluated.** `ExecutionPlan` at compilation (above). `ReflectionRecord`/`EvaluationRecord` themselves are not separately gated — they are read-only reasoning outputs; their *consequences* (a memory write, a retry) are what pass through governance, not the reflection/evaluation act itself.

**How escalation affects planning.** An escalated plan compilation halts at the gate (§2) — Plan Compiler does not produce a `WorkflowDefinition`, Supervisor is notified via `cognitive.plan_rejected`, and the plan sits pending HITL approval exactly as any other `GovernanceVerdict.ESCALATE` outcome does today. Nothing new is built for this; it is the existing mechanism, applied at a new point.

**How rejected plans recover.** Supervisor may hand a *revised* `Goal` back to Planner (§9) — it must not resubmit the same rejected `ExecutionPlan` unchanged (§16's new invariant).

---

## 16. Runtime Invariants

The directive's seven examples are evaluated individually, not copied wholesale — the same discipline applied to every candidate list in this document:

| Invariant | Verdict | Reasoning |
|---|---|---|
| Every plan has a goal | **Keep** | Enforced structurally: `ExecutionPlan.goal_id` is non-optional; Plan Compiler refuses a plan with no goal reference. |
| Every goal has an owner | **Keep, sharpened** | Rewritten as: *every Goal carries provenance to the Intent that produced it* — matching Constitution Invariant 4's "every resource carries provenance" rather than the vaguer original wording. |
| Every reasoning step is explainable | **Keep** | This is the invariant that actually closes the Explainability gap (§11) if enforced — tied to concrete fields, not left abstract. |
| Planning never executes | **Keep** | The Core Principle itself; the entire compilation seam (§6) exists to make this structurally true. |
| Execution never plans | **Keep** | The mirror image; already true of `WorkflowRuntime`/`ExecutionRuntime` today (confirmed: they execute exactly what a `WorkflowDefinition` specifies, they never originate new steps). |
| Reflection never mutates execution history | **Keep** | Direct corollary of Constitution Law 2 (Explicit State) and `EventStream`'s append-only design. Reflection writes new records; it never edits the historical ones it reflects on. |
| Evaluation never changes facts | **Keep** | Same reasoning, applied to `EvaluationRecord` vs the `KnowledgeEntry`/event evaluated. |

**Two additions, both evidence-driven, neither in the directive's original list:**

- **The Cognitive Runtime never bypasses Governance.** A direct corollary of Constitution Law 1, stated explicitly here because this exact class of bug — a mutation path that quietly skips `evaluate_action()` — has now been found and fixed twice in this project's own history (`UnifiedMemory.write()` pre-K3.5, then `update()`/`delete()` pre-K3.5.1). Naming it as a standing invariant for the *next* layer, before it ships, is cheaper than finding it after.
- **A rejected or escalated plan is not silently retried as-is.** Closes a specific, concrete failure mode this architecture would otherwise permit: Supervisor retry-looping a plan Governance already refused, which is exactly the uncontrolled recursive pattern `PROJECT_INSTRUCTIONS.md` §6.2 and `RecursionGovernor` already exist to prevent. Worth stating explicitly rather than assuming Supervisor's design (§9) alone prevents it.

---

## 17. Repository Layout

```
core/
  cognitive/                         # NEW package — the Cognitive Runtime
    __init__.py
    intent.py                        # Intent, Goal dataclasses + Intent Interpreter
    planner.py                       # Planner (replaces classify/dispatch body of
                                      #   core/workers/planner.py's PlannerWorker._run())
    plan.py                          # ExecutionPlan, PlanStep dataclasses
    compiler.py                      # Plan Compiler: ExecutionPlan -> WorkflowDefinition
                                      #   + governance gate (§15)
    working_state.py                 # WorkingCognitiveState (§10)
  workers/
    reflection.py                    # NEW — ReflectionWorker (AbstractCognitiveWorker subclass)
    evaluator.py                     # NEW — EvaluatorWorker (AbstractCognitiveWorker subclass)
    supervisor.py                    # NEW — SupervisorWorker (AbstractCognitiveWorker subclass)
    planner.py                       # MODIFIED — _run() delegates to core/cognitive/planner.py
                                      #   rather than containing classify/dispatch/merge inline
    curator.py                       # MODIFIED — active-curation methods construct
                                      #   GovernanceActions using existing SELF_MODIFYING_ACTIONS
                                      #   types (§15); no new methods, no new class
```

**No new top-level directory** — `core/cognitive/` sits as a peer to `core/workflow/`, `core/governance/`, `core/capabilities/`, matching the existing domain-driven layout `PROJECT_INSTRUCTIONS.md` §17 already specifies, rather than introducing a parallel structure.

**No new documents required by this layout beyond the milestone reports §19 will produce** — `ExecutionPlan`/`ReflectionRecord`/`EvaluationRecord` are `KnowledgeEntry`-compatible artifacts (§6, §13), not a new memory-layer document needing its own architecture spec.

---

## 18. ADRs (Enumerated Only)

Per instruction, not written here:

1. **ADR-K4-01 — Cognitive/Kernel Boundary.** Ratifies the Core Principle as a binding architectural decision, not just directive prose.
2. **ADR-K4-02 — ExecutionPlan Compilation Seam.** The one-directional Plan → WorkflowDefinition relationship (§6); why no reverse path exists.
3. **ADR-K4-03 — Cognitive Runtime Component Minimalism.** Records the seven-of-thirteen decision (§3) and the reasoning behind each rejection, so a future session doesn't re-propose Reasoner/Execution Monitor/Confidence Engine/Decision Engine without re-litigating this evidence.
4. **ADR-K4-04 — Governance Gate Placement (Plan Compilation).** Why the gate sits at compilation, not at planning or at execution (mirrors the K3.5/K3.5.1 "evaluate before mutation" precedent explicitly).
5. **ADR-K4-05 — Cognitive Event Namespace.** The `cognitive.` prefix decision (§12) and its relationship to `workflow.`/`KnowledgeEvent`'s existing conventions.
6. **ADR-K4-06 — Procedural Memory Reuse for Execution Plans.** Formalizes using `KnowledgeEntry.procedure_name`/`layer="l3"` rather than a new plan-memory schema (§13).

---

## 19. Implementation Roadmap

Each milestone independently testable; each preserves repository stability; no giant jumps.

```
K4.1  Intent + Goal primitives
      - Intent, Goal dataclasses (core/cognitive/intent.py)
      - Intent Interpreter: query -> Intent -> Goal (reuses existing
        parser.parse()/context_assembler, no new retrieval path)
      - Testable in isolation: given a query, produces a well-formed Goal.
      - No Kernel interaction yet -- lowest-risk milestone, ships first.

K4.2  ExecutionPlan + Planner (decomposition only, no compilation yet)
      - ExecutionPlan, PlanStep dataclasses (core/cognitive/plan.py)
      - Planner.plan(goal) -> ExecutionPlan, using CapabilityRegistry.resolve()
        for capability selection (existing, unmodified)
      - Testable in isolation: given a Goal, produces a well-formed
        ExecutionPlan with confidence + justification populated.
      - Still no Kernel interaction -- ExecutionPlan is not yet compiled
        or executed by anything.

K4.3  Plan Compiler + Governance Gate
      - compiler.py: ExecutionPlan -> WorkflowDefinition
      - GovernanceAction(action_type="plan_compile") wired at the gate
      - cognitive.plan_compiled / cognitive.plan_rejected events (§12)
      - Testable: a compiled WorkflowDefinition round-trips through the
        EXISTING, UNMODIFIED WorkflowRuntime.execute() without any
        WorkflowRuntime change -- this is the milestone that proves the
        seam (§6) actually holds, not just on paper.
      - First milestone with real Kernel interaction; scoped narrowly
        (one compile call, one governance check) to keep the blast
        radius small if something about the seam doesn't hold up.

K4.4  ReflectionWorker + EvaluatorWorker (read-only, no memory writes yet)
      - Both as ordinary AbstractCognitiveWorker subclasses
      - Consume EventStream events + the compiled plan; produce
        ReflectionRecord / EvaluationRecord as WorkerResult.artifacts
      - Testable: given a completed (or failed) workflow's event trail,
        produce a well-formed record. No UnifiedMemory writes yet --
        deliberately deferred to K4.5 so this milestone can't regress
        memory behavior even if something in the record schema is wrong.

K4.5  Memory Integration
      - Wire Reflection/Evaluation's promotion decisions to
        UnifiedMemory.write() using procedure_name/layer="l3" (§13)
      - Fix the MemoryCuratorWorker governance gap named in §15
        (prune_stale/strengthen_high_access/resolve_contradictions now
        construct GovernanceActions using EvolutionGovernor's existing
        SELF_MODIFYING_ACTIONS types)
      - Testable: promoted plans/reflections are retrievable via
        UnifiedMemory.search() like any other L3 entry; governance
        REJECT/ESCALATE on a curation action is independently testable
        against the existing EvolutionGovernor, unchanged.

K4.6  SupervisorWorker
      - Retry-via-reinvocation (§9), escalation surfacing, the
        rejected-plan-not-retried-as-is invariant (§16) enforced
      - Testable: inject a worker failure, confirm Supervisor retries
        through the normal governed path (not a bypass) and confirms
        the new invariant against a REJECT/ESCALATE fixture.
      - Ships last among the reasoning components because it is the
        one component whose entire job is reacting to the others --
        it has nothing to supervise until K4.1-4.5 exist.

K4.7  Full pipeline integration test
      - End-to-end: Intent -> ... -> Response, exercising every owner
        transition in §2's diagram against the real Kernel (not mocks)
      - Regression suite: confirm zero behavior change to any existing
        Kernel test (WorkflowRuntime, ExecutionRuntime, GovernanceKernel,
        UnifiedMemory) -- this milestone's exit criterion is that the
        existing 702-test suite still passes unchanged, plus new
        Cognitive Runtime coverage added alongside it, not replacing it.
```

**Explicitly out of scope for this roadmap**, per the directive's own constraints: capability discovery, plugin marketplace, repository ingestion, automatic adapter generation, external/dynamic capability loading. None of K4.1–K4.7 touch any of these.

**Sequencing note, stated plainly:** this roadmap is safe to *design* against now (architecture only, per this document's own scope), but per §0, K4.1's actual implementation should not begin before K3 (Kernel Compliance Audit) either completes or is explicitly, deliberately deferred by the project owner — several of K3's own open items (DEBT-002, DEBT-003, DEBT-008) sit close enough to the Kernel-execution surface this roadmap depends on (governed worker invocation, `WorkflowRuntime` execution, `EventStream`) that discovering a real problem in one of them mid-way through K4 implementation would be more expensive to unwind than confirming them first.

---

*Architecture complete. No implementation performed, no Kernel files modified, no existing test suite touched. Ready for ADR drafting (§18) and milestone-by-milestone implementation review (§19) once K3 status is explicitly resolved.*
