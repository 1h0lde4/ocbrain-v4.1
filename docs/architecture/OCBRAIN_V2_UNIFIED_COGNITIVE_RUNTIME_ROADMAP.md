# OCBrain v2 — Unified Cognitive Runtime and Roadmap Proposal

**Document status:** PROPOSED — architecture and roadmap research only; not ratified  
**Target generation:** OCBrain v2 (provisional architectural-generation label)  
**Current baseline:** `main` at `16d663ac8449965f774033da46d5063506a772a7` (29 October 2026)  
**Prepared on:** 30 October 2026  
**Scope:** Future cognitive architecture, migration principles, research gates and high-level roadmap  
**Implementation authorization:** NONE  
**Relationship to current roadmap:** Companion proposal; does not replace or amend `IMPLEMENTATION_ROADMAP.md` unless and until explicitly approved and reconciled

---

## 1. Executive decision proposed

OCBrain should investigate a future architecture in which the existing Planner becomes the foundation of an internal **Planning Engine within a unified C-MoE Cognitive Runtime**.

C-MoE would evolve beyond an expert router. It would become the coordinated cognitive runtime that constructs, evaluates and adapts strategies for achieving an authorized Goal. Its internal cognitive capabilities would include:

1. Planning and decomposition, evolved from the existing K4.2 Planner.
2. Skill Intelligence: skill discovery, applicability assessment, transfer, adaptation and composition.
3. Expert Intelligence: expert discovery, eligibility, specialization assessment, selection and collaboration.
4. Adaptive Strategy and Orchestration: strategy refinement, cognitive continuation, recovery decisions and replanning.
5. A shared Cognitive Workspace containing the task-scoped context needed by those capabilities.

These are **internal capabilities of one C-MoE runtime**, not five autonomous subsystems with competing authority. The Planner remains a distinct, testable internal module; it is not deleted, rewritten from zero or made into a second top-level cognitive authority.

This proposal does **not** move the Kernel into C-MoE. OCBrain's Kernel remains the governed execution, persistence, event, resource and authorization foundation. C-MoE proposes and coordinates cognitive strategies; the Kernel authorizes and executes the resulting work through its existing contracts.

The recommended direction is to preserve the current v1.x implementation and completed milestones, settle the v2 architecture before C-MoE implementation begins, and integrate the existing Planner when that implementation phase arrives.

## 2. Why this direction emerged

This proposal records the reasoning behind the architectural direction so that a future implementation team does not have to reconstruct the discussion or rediscover its assumptions.

### 2.1 The initial skill question

The starting question was how C-MoE should use skills. A simple expert router asks which expert should perform a task. A more capable system must also reason about which method should be used, whether that method is applicable, whether it can be transferred from another domain, whether it needs adaptation, and whether several methods can be composed.

That led to the distinction between:

- **Knowledge:** what OCBrain knows or has evidence for.
- **Skill:** a reusable procedure for accomplishing a class of objectives under stated conditions.
- **Expert:** an executor or specialist capable of carrying out work.
- **Capability:** a contracted operation that the system can make available and govern.
- **Tool:** a concrete mechanism used by an implementation.
- **Plan:** a proposed strategy and decomposition for achieving a Goal.
- **Execution workflow:** the Kernel-owned representation that the execution infrastructure actually runs.

A skill is not automatically an expert, a tool, a capability or a workflow. The same skill may be implemented through different experts or capabilities; one expert may use many skills.

### 2.2 Why a separate Skill Intelligence subsystem was rejected as the default

A separate autonomous Skill Intelligence agent beside C-MoE would create another cognitive authority. It could independently interpret tasks, recommend strategies, request execution or evolve methods, duplicating responsibilities that should be coordinated by the Cognitive Runtime.

The chosen direction is different: **skill reasoning is a first-class internal responsibility of C-MoE**, while skill storage, versioning, safe execution, validation and governed promotion remain supporting infrastructure with their own narrow contracts.

This keeps one coordinated cognitive authority without turning C-MoE into one giant implementation unit.

### 2.3 Why Planner and C-MoE are increasingly interdependent

The original separation assumed a relatively clean handoff:

- Planner decides what should be done and emits an ExecutionPlan.
- C-MoE determines which experts should execute its steps and adapts when execution reality differs from the plan.

That boundary becomes increasingly expensive as skill adaptability grows.

A useful transferable skill may change the decomposition itself. A newly discovered skill may remove several proposed work units. A skill composition may introduce new dependencies. Expert availability, resource budgets or execution constraints may make an initially attractive method infeasible. Actual outcomes may make the current decomposition obsolete.

Consequently, planning, skill reasoning and expert selection would repeatedly exchange plan versions, skill candidates, constraints, context, feasibility findings and execution observations. The cost is not only network or function-call latency. Even in one process, repeated subsystem handoffs create:

- duplicated or repeatedly serialized context;
- synchronization of Goal, plan, skill and task versions;
- stale assumptions and contradictory intermediate decisions;
- duplicated model reasoning and avoidable decision cycles;
- extra failure and recovery paths;
- unclear ownership when Planner and C-MoE disagree;
- more complicated provenance and debugging.

This is a compelling architectural reason to investigate a shared cognitive workspace and one coordinated runtime. It is a **strong hypothesis**, not yet an empirical proof that every unified design will outperform every separated design. The research phase must measure the claimed benefits.

### 2.4 Why this is a major-generation proposal

The approved OCBrain Architecture Evolution Directive v1.0 explicitly keeps Planning in the Cognitive Front-End and capability/expert selection in the future Cognitive Runtime. Making Planner an internal C-MoE capability changes that approved ownership boundary.

That is not a routine additive feature. It deserves a separately reviewed major architectural evolution, provisionally called **OCBrain v2**, rather than a silent change to v1.x.

The current K4.2 milestone remains complete and historically accurate. The proposal changes a future architectural arrangement; it does not rewrite what K4.2 delivered.

### 2.5 Why the decision is being prepared before C-MoE exists

C-MoE has not been implemented. The existing Planner is substantially implemented and its K4.2 work is complete. This is therefore the lowest-risk time to settle the future relationship.

The objective is to avoid building a new C-MoE around a permanent Planner/C-MoE boundary, only to pay the cost of consolidating those components later. The existing Planner should be reused as the starting point of the v2 Planning Engine.

## 3. Relationship to OCBrain v1.x, K4.2 and approved architecture

### 3.1 Preserve the current implementation

During v1.x:

- K4.2 remains complete.
- Intent interpretation and Goal formation remain in the existing Cognitive Front-End.
- The existing Planner, its contracts, tests, events and current request path remain in place.
- Existing Plan Compilation and its GovernanceKernel gate remain in place.
- No Planner rewrite, C-MoE integration refactor or speculative compatibility layer is authorized by this document.
- Existing Kernel and application behavior must not be changed merely to make the future architecture look cleaner.

The existing Planner is the implementation asset from which the future Planning Engine will evolve.

### 3.2 Preserve the historical meaning of K4 milestones

The canonical Kernel Completion Plan reconstructed the original K4 milestones:

| Historical milestone | Original responsibility | Treatment in this proposal |
|---|---|---|
| K4.1 | Intent and Goal primitives | Remains complete and unchanged |
| K4.2 | ExecutionPlan and Planner, decomposition | Remains complete and unchanged |
| K4.3 | Plan Compiler and Governance Gate | Remains the historical and implemented meaning of K4.3; it was never C-MoE |
| K4.4 | Reflection and Evaluation | Remains historical completed work; future evolution may extend it |
| K4.5 | Memory Integration | Remains historical completed work; memory ownership does not move into C-MoE |
| K4.6 | SupervisorWorker | Remains historical worker-supervision responsibility |
| K4.7 | Full-pipeline integration | Remains historical integration milestone |

No new K4.3, K4.8 or other K4 milestone is created for C-MoE.

### 3.3 Preserve the Kernel as the stable substrate

Kernel v1.0 remains the foundation beneath the future Cognitive Runtime. The v2 proposal must not make Kernel changes a routine prerequisite for adding or evolving expertise.

The following responsibilities remain outside C-MoE:

- GovernanceKernel: authorization and policy enforcement.
- UnifiedMemory: canonical persistent memory and governed mutations.
- EventStream: durable event history and replay.
- WorkflowRuntime: actual WorkflowInstance lifecycle, workflow/node sequencing, retries, checkpoints, resume and execution transactions.
- ExecutionRuntime: worker invocation and execution boundaries.
- CapabilityRegistry and AdapterRuntime: capability contracts, registrations and implementation dispatch.
- Kernel resource and identity contracts: stable operation, attempt, task and execution identity.

C-MoE is a Kernel-managed cognitive runtime, not a second Kernel.

### 3.4 Formal effect on the approved Architecture Evolution Directive

The approved Directive v1.0 says that the Cognitive Front-End includes Planning and that all responsibilities after Planning belong to the future Cognitive Runtime. It also prohibits silently changing completed milestones or moving responsibilities.

This proposal conflicts with that future ownership arrangement by design. **The conflict must not be resolved by silently editing the approved directive.**

Before any v2 implementation begins, the owner must explicitly approve a new versioned architecture decision or directive that:

1. preserves completed v1.x/K4.2 work and its historical status;
2. supersedes only the future ownership boundary that keeps Planner outside C-MoE;
3. establishes the Planning Engine as an internal C-MoE capability;
4. retains the Kernel, governance, execution, memory and verification boundaries stated here;
5. records the transition and compatibility policy.

Until that ratification exists, the current approved v1.0 architecture remains authoritative for v1.x.

### 3.5 Version naming caveat

“OCBrain v2” in this document is a **provisional architectural-generation label**, not a package-version change, repository rename, Kernel v2 declaration or release promise. The repository and existing materials use v4.1 naming in places. The final mapping between architectural generation, product release version, package version and Kernel version must be decided explicitly before release planning.

## 4. Proposed v2 target architecture

### 4.1 Cognitive Front-End

The existing front door remains responsible for receiving unstructured input and producing a structured, user-grounded objective.

Intent interpretation and Goal formation remain outside C-MoE in this proposal. The v2 architecture should not conflate understanding what the user asked for with deciding how to accomplish it.

The precise placement of constraint extraction and static capability discovery requires a deliberate design review. Some of those functions currently live inside Planner. They must be classified by responsibility rather than moved mechanically with a file or class name:

- user- and policy-derived constraints must retain their provenance and binding semantics;
- static discovery may supply candidate information;
- dynamic skill/expert eligibility and runtime selection belong inside C-MoE;
- no discovery result grants permission or proves that an expert can safely execute.

No K4.2 code is moved now. This is a v2 design decision to settle before implementation.

### 4.2 C-MoE: one runtime with specialized internal capabilities

**Planning Engine — evolved from the existing Planner**

Owns strategic decomposition and strategy construction within C-MoE: sub-goals, work-unit decomposition, sequencing, dependencies, alternatives, feasibility assumptions, confidence, impasse analysis and plan revision.

The existing Planner's useful algorithms and contracts are the starting point. Its future evolution allows planning to reason over skills and expertise before the strategy is finalized, instead of treating those as information that only arrives after planning.

**Skill Intelligence**

Reasons about procedural knowledge:

- discovers potentially applicable skills;
- checks preconditions, postconditions, invariants and environmental assumptions;
- distinguishes direct applicability from uncertain or exploratory transfer;
- evaluates transfer across context, affordances, parameters, composition and underlying principles;
- adapts a method while preserving its declared invariants;
- composes multiple skills into a larger procedure;
- identifies when a skill is missing, unsuitable or unsafe.

This is an internal C-MoE capability, not an independent autonomous subsystem.

**Expert Intelligence**

Reasons about who or what can execute a work unit:

- generates candidate experts from registered, versioned contracts;
- checks hard eligibility first (permissions, contracts, availability, required capabilities and resource limits);
- ranks eligible candidates using task fit, specialization, reliability, cost, latency and evidence;
- handles fallback, abstention, disagreement and composition;
- records why a candidate was selected or rejected.

Expert identity and lifecycle must remain separate from skill identity, skill version, model/provider identity and routing-policy version. ModelRouter's model/provider maturity lifecycle must not be reused as though it were an expert lifecycle.

**Adaptive Strategy and Orchestration**

Coordinates the internal reasoning capabilities under one C-MoE decision authority. It determines when the current strategy should continue, be refined, be recomposed, be suspended or be returned for user input. It integrates actual execution observations without taking over Kernel execution mechanics.

Internal modules can provide typed findings and recommendations. A single C-MoE orchestration authority coordinates the task-level cognitive decision; modules must not independently race to mutate the authoritative strategy.

**Shared Cognitive Workspace**

Provides shared, task-scoped working context for the internal modules. It should include references to the active Goal and constraints, plan hypotheses and versions, skill candidates and versions, expert/capability availability, assumptions, feasibility evidence, execution observations and decision provenance.

This is a working cognitive representation, not a second UnifiedMemory, a second event store or a second authoritative execution-state database. Durable knowledge remains in UnifiedMemory; durable history remains in EventStream; actual workflow and node state remains in WorkflowRuntime.

### 4.3 Supporting infrastructure remains separately owned

| Supporting infrastructure | Responsibility | Relationship to C-MoE |
|---|---|---|
| Skill catalog / registry | Versioned discovery, contracts, provenance and applicability metadata | Supplies reusable procedural knowledge |
| Skill Runtime | Controlled execution of a selected skill implementation | Executes; does not decide strategy |
| Capability Registry / AdapterRuntime | Capability contracts and replaceable implementations | Supplies authorized operations and adapters |
| WorkflowRuntime / ExecutionRuntime | Actual workflow execution and worker lifecycle | Executes C-MoE-approved compiled work |
| GovernanceKernel | Authorization and policy decisions | Approves or rejects governed actions |
| UnifiedMemory | Persistent knowledge and approved memory | Supplies scoped evidence and receives governed promotions |
| Verification | Independent outcome-versus-requirement assessment | Supplies evidence; C-MoE cannot self-certify correctness |
| Reflection | Historical critique and trajectory analysis | Supplies future improvement recommendations |
| Learning and Evolution | Candidate validation, governance and promotion | Controls whether learning changes future behavior |
| Context Compiler | Structured, provenance-aware context construction | Supplies a shared context view through defined contracts |
| External Knowledge Pipeline | Acquisition of reviewable external knowledge | May supply candidates for knowledge or skill induction |
| Studio / observability | Explanation and presentation of runtime state | Consumes events and projections; does not own decisions |

The supporting infrastructure should be independently replaceable. Its existence does not create another cognitive decision authority.

## 5. The skill model C-MoE must support

### 5.1 Skill definition and skill implementation are different

A skill definition describes the reusable method: its objective/problem signature, preconditions, procedure, required affordances, expected effects, invariants, termination conditions, verification criteria, limitations and evidence of applicability.

A skill implementation is a concrete realization of that method: for example, code, a sequence of tool operations, a browser procedure, a data-analysis implementation or a human-assisted procedure.

This separation is necessary for provider and environment independence. One semantic skill may have multiple implementations. C-MoE selects a method; the Skill Runtime and capability infrastructure determine how an authorized implementation is executed.

### 5.2 Transfer must be evidence-based

Transfer is not copying instructions from one domain into another. The future system should evaluate at least:

- objective and problem-structure compatibility;
- precondition compatibility;
- required affordances and available actions;
- environmental and contextual shift;
- preservation of effects and invariants;
- evidence coverage and known failure modes;
- risk, reversibility and verification strength.

Transfer outcomes should distinguish direct applicability, adaptation required, exploratory use and ineligibility. A single opaque similarity score must not be treated as proof that a skill transfers safely.

The future evaluation program should test parameter transfer, context transfer, affordance transfer, composition transfer, principle transfer and adaptation to genuinely novel situations separately.

### 5.3 Missing skill is not the same as missing capability

C-MoE must distinguish at least these situations:

- **No applicable skill:** the method is unknown or no stored procedure fits. The system may investigate, reason from available evidence or request information.
- **Missing capability:** a required operation or affordance is unavailable. This is a capability gap, not merely a missing procedure.
- **Missing information:** the method and actions may exist, but necessary facts are unknown.
- **Permission denied:** the operation exists but policy or user authorization does not permit it.
- **Infeasible or unsafe transfer:** a skill exists but its assumptions or invariants cannot be preserved.

These distinctions lead to different responses. A missing method must not cause the system to invent a capability. A missing capability must not be hidden by repeatedly rewriting the plan.

### 5.4 Skill composition

C-MoE should be able to compose compatible skills into a larger procedure. Composition must preserve typed input/output contracts, preconditions, effects, provenance, dependency order, termination conditions and verification obligations.

Composition must be bounded. Unrestricted recursive composition and uncontrolled agent loops are not acceptable. The implementation must define recursion limits, budget limits, cycle detection, termination conditions and failure/abstention behavior before enabling autonomous composition.

### 5.5 Skill acquisition and evolution are governed lifecycle operations

Skill consumption is required from the first meaningful C-MoE capability: a runtime that can only select experts but cannot discover or use procedural knowledge would omit the reason for this architectural evolution.

Autonomous skill creation and evolution may arrive later. Their contracts should nevertheless be defined before implementation so that skill consumption does not create an incompatible foundation.

The lifecycle must distinguish:

1. experience and observed outcomes;
2. an induced SkillCandidate with provenance and evidence;
3. contract, safety and invariants validation;
4. sandbox testing and side-effect analysis;
5. held-out evaluation and transfer testing;
6. GovernanceKernel authorization;
7. publication as a versioned skill;
8. monitoring, supersession, revocation and retirement.

K4.1-L's invariant remains in force: promoted LearningCandidates are retrievable evidence, never executable rules. An executable SkillCandidate requires a separate artifact type and lifecycle. The shared Learning ValidationGate can be evaluated as a promotion-policy dependency, but it is not itself a Skill Runtime or a skill-creation pipeline.

### 5.6 Existing Skill infrastructure is a starting point, not a completed runtime

The repository contains a small BaseSkill abstraction and SkillMetadata/SkillInput/SkillOutput contracts. This is useful prior work, but it is not yet proof of a hardened Skill Runtime.

In particular, SkillExecutionConfig declares mode, timeout, memory limit and allowed imports, but those declarations must not be mistaken for enforced operating-system isolation. BaseSkill currently executes its implementation in-process under an async timeout. Its general exception retry behavior can repeat side effects, and its optional cache is keyed by serialized keyword arguments rather than a complete execution scope, identity, authorization and environment contract.

Before C-MoE can safely invoke skills, the Skill Runtime must establish enforced isolation, permission scoping, resource limits, cancellation, auditable execution, side-effect classification, idempotency-aware retry semantics and cache-scope correctness. The existing Execution Fabric may provide reusable sandbox infrastructure, but that reuse must be verified against actual contracts and threat models rather than assumed.

## 6. One integrated cognitive cycle

The target runtime should coordinate a single bounded cognitive process rather than implement a rich, recursive Planner-to-C-MoE dialogue.

1. The Front-End supplies a structured Goal and its provenance.
2. C-MoE assembles a conditional, read-only view of relevant reality: prior work, verified results, memory references and coarse capability/expert availability.
3. The Planning Engine constructs an initial strategy while consulting Skill Intelligence and Expert Intelligence as needed.
4. Skill Intelligence tests applicability and possible transfer; Expert Intelligence tests whether suitable executors and capabilities exist.
5. The integrated runtime revises the strategy before execution when the combined evidence shows that a better or feasible method is available.
6. C-MoE emits a structured proposed strategy. Plan Compilation validates and compiles it through the existing Kernel-facing seam; GovernanceKernel authorizes the compile action.
7. WorkflowRuntime executes the resulting WorkflowDefinition and remains the source of truth for actual workflow/node lifecycle, retries, checkpoints and resume.
8. C-MoE consumes structured execution observations and, where available, independent Verification results.
9. It decides whether the current strategy can continue, needs a bounded adaptation, requires a revised plan, must abstain, or needs user input. Revised strategies pass through compilation and governance again before execution.
10. Reflection and governed Learning may use the resulting evidence to improve future behavior; no unverified outcome silently changes executable skills or routing policy.

The Reality-Grounding sub-study's useful conclusion remains: facts and evidence may be assembled before planning, but a separate Reality authority or an iterative Planner↔C-MoE dialogue should not be introduced. In v2, planning and skill/expert reasoning share one coordinated runtime, so they can refine a strategy within one task-scoped workspace. This does not authorize an unbounded internal loop: bounded reasoning rounds, clear stopping conditions, decision budgets and abstention rules are mandatory.

## 7. Strict authority boundaries

### 7.1 Cognitive decisions versus execution mechanics

C-MoE decides the cognitive strategy: which procedure and expert should be proposed, what the next task-level cognitive action should be, and whether the strategy needs revision.

The Kernel decides and enforces the mechanics: whether an action is authorized, how a compiled workflow is scheduled and executed, what the true workflow/node state is, how retries and checkpoints work, and how events and durable resources are recorded.

The proposed WorkGraph in the existing C-MoE study requires explicit reconciliation. If retained, it must represent C-MoE's **cognitive strategy and work decomposition**, not become a competing authoritative execution graph. Actual workflow/node execution state remains in WorkflowRuntime. C-MoE may propose graph changes; the approved work must pass through Plan Compilation and Kernel execution. A projection of execution status must derive from canonical Kernel events/results rather than independently mutate the same state.

### 7.2 Governance

C-MoE cannot grant permissions, approve its own actions, bypass policy or directly authorize persistent mutation. It proposes; GovernanceKernel authorizes.

### 7.3 Verification

Execution success is not proof that the user's intent was satisfied. C-MoE must consume independently produced Verification results. Full goal-level completion claims must follow the accepted verification contract, with explicit treatment for unverified, partially satisfied, blocked, cancelled and failed outcomes.

### 7.4 Reflection and Learning

C-MoE can emit decision provenance, task outcomes and improvement candidates. Reflection owns retrospective critique; Learning owns candidate validation and promotion; GovernanceKernel owns authorization. C-MoE cannot silently rewrite its own policies or publish executable skills.

### 7.5 Supervisor and retry ownership

Kernel WorkflowRuntime owns mechanical node retry and checkpoint/resume behavior. SupervisorWorker retains its defined worker-level supervision/recovery classification. C-MoE owns task-level cognitive strategy decisions. These boundaries must prevent multiple actors from racing to recover the same failure at different layers without a single, explicit precedence rule.

### 7.6 Capability isolation

Capabilities remain independently versioned, installable, replaceable and governed. They do not directly invoke, import or depend on each other. C-MoE coordinates capability use through the Kernel contracts; skill composition must not become a back door for capability-to-capability invocation.

## 8. Proposed OCBrain v2 roadmap

The following is a dependency-oriented roadmap proposal, not an implementation authorization or a claim that the prerequisite work is complete.

### Phase 0 — v1.x stability and Kernel readiness

**Purpose:** Preserve the working v1.x platform and establish a valid foundation before the next-generation runtime begins.

**Work to do when this phase is reached:**

- Complete the current Kernel v1.0 freeze process against a fresh main commit, not an old audit baseline.
- Reconcile the freeze-remediation register, open debts, approved ADRs, required decisions and live code.
- Reconfirm operation/attempt identity, workflow durability, retry/idempotency behavior, concurrency, execution-state ownership and event provenance.
- Reconcile all currently open PRs and branches that affect those areas.
- Verify that the actual capability dispatch path supports the intended number and variety of capability types.
- Reassess Context Compiler prerequisites, task/project scoping and provenance before multi-worker C-MoE integration.
- Retain the current K4.2 Planner and existing interfaces unchanged.

**Exit gate:** Kernel v1.0 has an explicit accepted freeze verdict and reproducible baseline; all C-MoE-blocking Kernel dependencies are either resolved or explicitly classified and accepted by the owner. No C-MoE implementation begins while this gate remains open.

### Phase 1 — v2 architecture research and ratification

**Purpose:** Prove that the unified runtime is justified and define its authoritative architecture before implementation.

**Work to do:**

- Reconcile the full existing C-MoE architecture study, Routing Architecture Study, Reality-Grounding sub-study, Verification study, K4.2 authoritative architecture, K4.1-L, K5 future evolution study, Kernel Constitution and approved Architecture Evolution Directive.
- Separate facts about current source from proposals and historical claims; update statuses using fresh evidence.
- Compare two designs using the same workload and execution conditions:
  - A: existing Planner plus a richer but separate C-MoE;
  - B: Planner integrated as an internal Planning Engine within C-MoE.
- Include skill-heavy tasks that require transfer, adaptation, composition, replanning and recovery; simple routing-only tasks are insufficient to settle this question.
- Measure task success, plan feasibility, handoff count, context duplication, version conflicts, number of cognitive cycles, stale-plan incidents, unnecessary replanning, latency, token/resource cost, recovery quality and traceability.
- Study model behavior through observable prompts, tool use, outcomes and artifacts where useful. Do not claim to know proprietary model internals or make OCBrain dependent on any external model provider.
- Define the v2 authority matrix, module contracts, cognitive workspace, skill model, outcome model, migration boundary and acceptance gates.
- Produce an ADR or versioned directive that explicitly supersedes the relevant v1.0 future ownership arrangement without modifying completed K4.2 history.

**Exit gate:** Owner-approved architecture, evidence-backed decision record, migration plan, no unresolved authority conflict, and measurable acceptance criteria. Until then v2 remains a proposal.

### Phase 2 — shared cognitive and skill foundations

**Purpose:** Establish the contracts and safety infrastructure that a unified runtime needs.

**Work to do:**

- Define skill identity, version, semantic definition, implementation binding, provenance, applicability, preconditions, invariants, effects, termination and verification contracts.
- Define expert identity and expert contracts separately from skill identity and model/provider identity.
- Define the shared task-scoped Cognitive Workspace and its relationship to Context Compiler, UnifiedMemory and EventStream.
- Reconcile stable task/operation/attempt identity and scope propagation through capability, skill and expert execution.
- Establish the safe Skill Runtime boundary using measured and enforced controls, not metadata declarations alone.
- Define side-effect classes, idempotency requirements, cancellation, timeout, budget, retry and cache semantics.
- Reconcile Skill Registry and capability discovery without creating duplicate registries or two independent routing authorities.
- Define version and compatibility policy for skills, implementations, expert descriptors, plans and routing policy.

**Exit gate:** Contracts are reviewed and versioned; safe execution and isolation are independently tested; identity, scope, provenance and authorization flow end-to-end; no skill can bypass Kernel governance or call another capability directly.

### Phase 3 — integrate the existing Planner as C-MoE's Planning Engine

**Purpose:** Reuse completed K4.2 planning work inside the unified runtime without recreating it.

**Work to do:**

- Inventory the existing Planner's responsibilities, algorithms, public interfaces, events, contracts, tests and known limitations.
- Classify each responsibility: retain in the Planning Engine, retain in the Front-End, move to supporting infrastructure, or defer.
- Resolve the precise placement of constraint extraction and static capability discovery; do not move them merely because they currently reside in planner.py.
- Preserve the existing Goal, Constraint, PlannerRequest/PlannerResult, ExecutionPlan, PlanStep, confidence, alternatives, impasse and provenance semantics wherever evidence supports them.
- Introduce a compatibility boundary so existing v1.x calls can continue to use the established interpret/plan/compile surface while v2 internals are developed.
- Make the Planning Engine consume structured skill and expert evidence without giving it authority to execute capabilities.
- Preserve the Plan Compiler and its GovernanceKernel gate as the route from cognitive strategy to Kernel WorkflowDefinition.
- Test that v2 strategy construction does not regress K4.2 outputs, invariants or existing callers.

**Exit gate:** The Planning Engine is demonstrably derived from the existing Planner; compatibility tests pass; there is one authoritative cognitive plan representation; no second compiler, workflow engine or execution-state store is introduced.

### Phase 4 — skill-aware planning and expert intelligence

**Purpose:** Make skills and expertise first-class inputs to strategy construction.

**Work to do:**

- Build skill discovery, applicability checks and hard eligibility.
- Implement expert candidate discovery, eligibility and risk-aware selection.
- Let the Planning Engine consider useful skills and expertise during decomposition, rather than discovering them only after a plan is fixed.
- Evaluate direct skill use versus parameter/context/affordance/principle transfer.
- Distinguish direct applicability, adaptation required, exploratory use and ineligibility.
- Support bounded skill composition with contract compatibility, dependency ordering and preserved invariants.
- Distinguish missing skill, missing capability, missing information, denied permission and unsafe transfer.
- Establish deterministic routing mechanics separately from versioned routing policy and tunable weights.
- Keep model/provider routing as a separate lower-level concern.

**Exit gate:** Real, distinct skills and experts can be discovered and selected; positive and negative transfer cases are tested; unsafe or unsupported candidates are rejected or escalated; selection is explainable and reproducible.

### Phase 5 — unified adaptive strategy runtime

**Purpose:** Coordinate planning, skills and experts through one coherent cognitive process.

**Work to do:**

- Establish one C-MoE orchestration authority and a bounded reasoning cycle.
- Build conditional, read-only reality/context grounding and feasibility evaluation.
- Coordinate plan construction, skill adaptation, composition and expert selection over the shared workspace.
- Define the cognitive WorkGraph's exact scope and make it a strategy representation/projection, not a duplicate of Kernel execution state.
- Translate approved strategy revisions through Plan Compilation and GovernanceKernel before Kernel execution.
- Consume structured execution outcomes, preserve Goal and plan ancestry, and reject stale results against current versions.
- Distinguish continue, adapt, compose, abstain, request information, request user input, replan and terminate outcomes.
- Define maximum reasoning rounds, recursion depth, resource budgets, termination conditions and failure containment.
- Ensure task-level C-MoE strategy recovery does not duplicate WorkflowRuntime retry or SupervisorWorker authority.

**Exit gate:** The runtime can handle a complete authorized task, adapt a method based on real observations, safely recompile changed strategy and preserve one canonical execution history. Boundedness and termination are demonstrated under adversarial tests.

### Phase 6 — independent verification and evidence integration

**Purpose:** Ensure the unified runtime optimizes for actual goal satisfaction, not merely successful execution.

**Work to do:**

- Reconcile and adopt the project's Verification/Critic/Evidence architecture through its own approval process.
- Define requirement decomposition and measurable acceptance contracts for supported artifact/task classes.
- Keep execution receipts, observations, evidence, verification results and final verdicts distinct.
- Verify results independently from the C-MoE decision that selected the skill or expert.
- Define how partial success, contradictory evidence, missing evidence and unverifiable results affect task status.
- Ensure C-MoE consumes verification results for strategy continuation and future routing evidence.
- Prevent self-certification of full task completion.

**Exit gate:** A C-MoE-selected expert cannot make its own output verified merely by returning success; verification provenance and failure modes are explicit and tested.

### Phase 7 — reflection, governed learning and skill evolution

**Purpose:** Improve future strategies without allowing uncontrolled self-modification.

**Work to do:**

- Integrate Reflection as a retrospective consumer of trajectories, decisions, outcomes and verification evidence.
- Define separate LearningCandidate and executable SkillCandidate types and lifecycles.
- Evaluate whether the existing shared ValidationGate can serve the skill promotion path without weakening domain-specific validation.
- Validate skill candidates on held-out tasks and transfer benchmarks.
- Require sandbox testing, invariants, permissions, provenance and versioning before publication.
- Require GovernanceKernel authorization for Evolution-tier actions; retain human approval where policy requires it.
- Support version rollback, revocation, deprecation and supersession.
- Ensure learned candidates remain evidence until the appropriate governed promotion process authorizes a specific change.

**Exit gate:** No experience or model-generated proposal becomes an executable skill or changed routing policy without evidence, validation, authorization and an auditable version transition.

### Phase 8 — broader cognitive integration and scale

**Purpose:** Extend the mature runtime without changing its authority model.

Potential integrations, sequenced only when their prerequisites exist:

- Self-Identity / Self Model and evidence-based system capability awareness.
- Context Compiler and richer provenance-aware context assembly.
- External Knowledge Pipeline and knowledge-to-skill induction.
- Advanced GraphRAG/KAG for structured retrieval and relationships.
- Multi-Agent Runtime and expert collaboration, bounded by the same capability and governance contracts.
- Project/Discussion scope and controlled cross-task reuse.
- OCBrain Studio, explainability, observability, evaluation and reliability tooling.
- Proactive optimization only after sufficient verified cross-task history exists.

**Exit gate:** Each addition has a single owner, a clear dependency and a demonstrated benefit; no integration creates duplicate authority, hidden persistence or uncontrolled autonomous behavior.

## 9. Evaluation program and evidence required

The architecture must be evaluated against a separated Planner + C-MoE baseline before the unified design is declared superior.

### 9.1 Workload classes

The benchmark set must include:

- simple tasks with no meaningful skill transfer;
- complex hierarchical decomposition;
- tasks where a relevant skill already exists;
- cross-domain transfer with changed context or affordances;
- tasks requiring adaptation or composition of multiple skills;
- tasks where no suitable skill exists;
- tasks where a capability or permission is missing;
- changing user requirements and plan mutation;
- failed or partial execution requiring recovery;
- ambiguous or contradictory evidence;
- high-risk or irreversible actions requiring stronger governance.

### 9.2 Measurements

At minimum, capture:

- task and goal success as determined by independent verification;
- plan feasibility before execution;
- expert/skill selection quality and calibration;
- transfer success and negative-transfer rate;
- skill composition success and invariant violations;
- cognitive handoffs and duplicated context volume;
- reasoning cycles, latency and token/resource consumption;
- stale-plan, stale-result and version-conflict incidents;
- replanning frequency and unnecessary recomputation;
- execution retries and duplicated side effects;
- abstention quality, escalation quality and user-interaction rate;
- provenance completeness and reproducibility.

### 9.3 Acceptance principle

A unified runtime should be preferred only if it improves overall outcomes or materially reduces coordination risk without introducing unacceptable complexity, weaker isolation or poorer explainability. Lower handoff count alone is not sufficient evidence.

External model studies may inform benchmark design and behavioral targets, but OCBrain must remain provider-independent and local-first. No proprietary internal architecture should be inferred from observable outputs.

## 10. Migration and compatibility principles

The transition should be evolutionary, not a rewrite.

1. **Keep v1.x operational.** Do not alter K4.2 implementation as a prerequisite for researching v2.
2. **Reuse the Planner.** Treat current planner logic, contracts, tests and event history as prior assets.
3. **Use a compatibility facade.** Existing interfaces should remain usable while their implementation is redirected to the internal Planning Engine when v2 is ready.
4. **Preserve artifacts and provenance.** Existing Goal, ExecutionPlan, WorkflowDefinition and event records must remain interpretable. Any new fields require defaults or explicit schema/version migration.
5. **Preserve the Kernel seam.** All executable workflows continue through Plan Compilation, GovernanceKernel and WorkflowRuntime.
6. **Avoid dual writers.** During migration, one component owns each authoritative plan, strategy and execution state at a time. A temporary compatibility layer must have an explicit sunset condition.
7. **Migrate incrementally.** Introduce the integrated runtime behind a controlled boundary, validate parity and behavior, and remove old routing/ownership paths only after their consumers have been accounted for.
8. **Do not conflate release labels.** Kernel v1.0 and the provisional OCBrain v2 cognitive generation are separate version axes.

No specific code migration is authorized by this roadmap.

## 11. Risks and safeguards

| Risk | Required safeguard |
|---|---|
| C-MoE becomes a cognitive monolith | Independently testable internal modules, explicit contracts and one orchestration authority |
| C-MoE becomes a second Kernel | Keep governance, durable state, workflow execution and resource lifecycle in Kernel services |
| Planner rewrite discards working behavior | Preserve K4.2 implementation and compatibility contracts; migrate with parity tests |
| Skill transfer causes negative transfer | Evidence-based applicability, preconditions, invariants, held-out transfer tests and abstention |
| Skill runtime executes untrusted code unsafely | Enforced sandbox, permissions, limits, audit and idempotency-aware effects |
| Infinite reasoning or skill recursion | Explicit bounds, budgets, termination and cycle detection |
| C-MoE WorkGraph duplicates WorkflowRuntime | Cognitive strategy graph only; execution state remains Kernel-authoritative |
| Planner and C-MoE are replaced by two hidden model loops | Shared workspace, bounded coordinated decisions and traceable reasoning rounds |
| Learning silently changes behavior | Candidate/validation/governance/promotion lifecycle and immutable version history |
| Verification becomes self-referential | Independent verifier, separate evidence and verdict contracts |
| ModelRouter is confused with expert routing | Keep provider/model, expert, skill and routing-policy identities separate |
| Memory/context contamination across tasks | Explicit task/project scope, provenance, authority and concurrency tests |

## 12. Explicitly deferred or prohibited

Unless a later approved decision changes these constraints, v2 must not:

- replace or weaken the Kernel's governance or execution contracts;
- make C-MoE directly execute arbitrary code or bypass Skill Runtime and capability boundaries;
- permit capabilities to invoke or depend on one another directly;
- create a second authoritative workflow engine, persistent memory or event store;
- treat a retrieved skill or LearningCandidate as trusted executable instructions;
- claim that skill similarity proves transferability;
- allow unbounded recursive agents, unlimited replanning or self-modification;
- allow C-MoE to verify or authorize its own outputs;
- require a cloud provider, external paid LLM or specific model family;
- assume distributed multi-node execution before the single-node contracts and workload evidence justify it;
- rename the repository or change package/product version labels as a side effect of accepting this architecture proposal.

## 13. Decisions that remain open before implementation

The architecture approval phase must resolve, at minimum:

1. The precise boundary between the Cognitive Front-End and C-MoE for constraint extraction and static capability discovery.
2. The canonical cognitive strategy representation and its relationship to ExecutionPlan.
3. The exact meaning, ownership and persistence of a C-MoE WorkGraph projection.
4. The contracts separating SkillDefinition, SkillImplementation, ExpertDescriptor and CapabilityContract.
5. The Skill Runtime security profile, sandbox backend requirements and side-effect semantics.
6. The transfer evidence model and acceptance thresholds by transfer class.
7. The expert performance history and routing-policy lifecycle, distinct from ModelRouter's model maturity state.
8. The relationship between Verification, Reflection, SupervisorWorker and C-MoE recovery decisions.
9. The shared Cognitive Workspace's relationship to Context Compiler, UnifiedMemory, EventStream and task/project scope.
10. The compatibility and deprecation policy for current public interfaces and old orchestration paths.
11. The exact release naming: architectural generation v2 versus the repository's current v4.1 naming.
12. Which capabilities are required for the first useful C-MoE release versus advanced post-MVP phases.

An unresolved authority conflict is a stop condition, not permission to guess.

## 14. Source documents and traceability

This proposal is based on the repository snapshot at the stated baseline. The following documents are the primary evidence and must be re-read against fresh main before final ratification.

| Source | What it contributes |
|---|---|
| [OCBrain Architecture Evolution Directive v1.0](OCBrain%20Architecture%20Evolution%20Directive.md) | Approved current boundary; explicit conflict requiring formal supersession |
| [Kernel Constitution](../../OCBRAIN_KERNEL_CONSTITUTION.md) | Laws of bounded autonomy, explicit state, separation, determinism, evidence and single source of truth |
| [Kernel Architecture v1.0](KERNEL_ARCHITECTURE_v1.0.md) | Kernel service ownership, WorkflowRuntime and ExecutionRuntime contracts |
| [K4.2 Cognitive Front-End Authoritative Architecture](OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md) | Completed Planner/front-end responsibilities, contracts and public seams |
| [Canonical Kernel Completion Plan](../studies/OCBRAIN_KERNEL_COMPLETION_CANONICAL_PLAN.md) | Historical K4.1–K4.7 reconstruction and correction that K4.3 is Plan Compiler/Governance |
| [C-MoE Cognitive Runtime Architecture Study](../studies/OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md) | Existing expert, routing, outcomes, WorkGraph, memory and C-MoE design proposals to reconcile |
| [C-MoE Routing Architecture Study](../studies/OCBRAIN_CMOE_ROUTING_ARCHITECTURE_STUDY.md) | Separation between module, capability implementation, model/provider and expert routing |
| [C-MoE Reality-Grounding Sub-study](../studies/OCBRAIN_CMOE_REALITY_GROUNDING_SUBSTUDY.md) | Conditional, read-only grounding and rejection of an iterative Planner↔C-MoE dialogue |
| [C-MoE Verification Architecture Study](../studies/OCBRAIN_CMOE_VERIFICATION_ARCHITECTURE_STUDY.md) | Independent verification, evidence and false-completion boundaries |
| [K4.1-L Cognitive Learning Architecture](OCBRAIN_K4_1_L_FINAL_LEARNING_ARCHITECTURE.md) | LearningCandidate invariant and governed promotion |
| [K5 Future Cognitive Evolution Architecture](OCBRAIN_K5_FUTURE_COGNITIVE_EVOLUTION_ARCHITECTURE.md) | Self Model, strategy selection, belief revision and deferred cognitive evolution |
| [Context Compiler Remediation Register](../reports/context-compiler-remediation-register.md) | Context preservation, authority, scoping and multi-worker integration prerequisites |
| [Implementation Roadmap](../../IMPLEMENTATION_ROADMAP.md) | Current milestone history and post-Kernel phase placement |
| [Current State](../../CURRENT_STATE.md) and [Known Issues](../../KNOWN_ISSUES.md) | Implementation facts, live debt, freeze remediation and evidence status |

### 14.1 Baseline caveats

The roadmap is based on main at 16d663ac8449965f774033da46d5063506a772a7. Several current tracking documents have different synchronization dates, and some sections preserve older historical snapshots. The October 28 Known Issues update, October freeze-remediation register, open PRs and current source must be reconciled before a later implementation branch is planned.

This document does not claim the Kernel is currently FREEZE READY. It explicitly requires a fresh freeze verdict.

## 15. Branching and integration policy for this proposal

This proposal is intentionally maintained on a separate branch and submitted as a PR rather than changing main while many unrelated PRs are open and being merged.

The intended integration order is:

1. Continue reconciling and merging the active v1.x and Kernel PRs independently.
2. Keep this roadmap proposal isolated; do not make it a dependency of those PRs.
3. Before this PR is merged, fetch the then-current main and re-check every source claim, file path, freeze status, open debt and relevant ADR.
4. Update the proposal for any relevant changes that landed after its base commit.
5. Check for conflicts with newly accepted architectural decisions. If a real conflict appears, document and resolve it explicitly rather than forcing the merge.
6. Merge this proposal only after the other active PRs that materially affect its baseline have been reconciled.
7. Even after this document is merged, it remains PROPOSED until a separate owner decision/ADR formally ratifies it.

The branch-last strategy is an integration-control measure. It is not an attempt to avoid review, required checks or source reconciliation.

## 16. Approval and implementation gates

This proposal may be accepted as a research and roadmap direction without authorizing implementation.

Before implementation is authorized, all of the following must be true:

- The Kernel v1.0 freeze gate has a fresh accepted verdict.
- The v2 architecture comparison has measured evidence and a recorded decision.
- The Planner integration boundary and compatibility policy are approved.
- The C-MoE authority matrix has no unresolved overlap with Kernel, Supervisor, Verification, Reflection, Memory or Learning.
- Skill contracts, safe runtime requirements and transfer evaluation criteria are approved.
- The cognitive WorkGraph and Kernel execution-state relationship is explicit.
- The v2 roadmap and required ADR/directive changes are approved.
- Each implementation batch has an owner, allowed files, out-of-scope items, tests, acceptance criteria and rollback conditions.

**Final recommendation:** Preserve the v1.x Planner exactly where it is operationally today. Make it the named implementation foundation for the v2 C-MoE Planning Engine in the approved future architecture. Build the unified runtime only after research proves the benefit and the Kernel foundation is formally ready.

This is a proposal for a stronger next-generation OCBrain cognitive architecture—not an implementation request, not a K4 milestone change and not a declaration that OCBrain v2 has already been approved.
