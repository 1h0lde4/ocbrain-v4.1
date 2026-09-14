# OCBrain — Verification as Continuous Execution Quality-Control Layer
## Architecture Research & Proposal (Companion to the C-MoE Cognitive Runtime Study)

**Status:** Research and architecture proposal only. No code modified, no tests added, no K-number assigned, no freeze-blocker declared — classification recommendations below are for project-owner sign-off, per the governing task's explicit instruction.
**Audited against:** `github.com/1h0lde4/ocbrain-v4.1` @ `6f2eb9f0dff848610a34cd6747856126ed0f8abb` — same commit as the prior Kernel false-completion audit; nothing in this repo has changed between the two.
**Evidence tags, adopted from the CMoE study's own convention:** **[FACT]** direct source read this session, **[STUDY]** a conclusion from an existing OCBrain document, reconciled here, **[EXT]** external evidence gathered this session, **[INFER]** inference from the above, **[DECISION]** a design choice made here with its trade-off stated.

---

## A. Executive conclusion

**[DECISION]** Verification's correct conceptual role in mature OCBrain is not a new subsystem invented for C-MoE. It is the thing the existing C-MoE Cognitive Runtime Architecture Study already reserved space for at every layer it touched — a `verification_status` enum stub, a `verification confidence` field kept separate from four other confidence dimensions, a task-status enum explicitly capped below full completion until Verification exists, a "verification hook" primitive named and then explicitly deferred — and then declared, correctly, a **future milestone** out of K4.3 scope. This document is a first pass at that milestone, not a competing design.

**[FACT]** The failure this is meant to prevent is not hypothetical and not C-MoE-specific — it is live, today, in the Kernel, independent of whether C-MoE ever ships. The prior session's audit (same commit) traced it to one line: `core/workflow/runtime.py:280` — `success = last_result.success if last_result is not None else True`. That boolean propagates unchecked through `workflow.completed` (`:320`) into `EvaluatorWorker.goal_completed` (`evaluator.py:172`), and `ExecutionOutcome.is_success` (`execution_outcome.py:80-81`) explicitly treats `COMPLETED_WITH_PARTIAL_OUTPUT` as equal to `SUCCESS`. Today this is a one-hop chain, because **[STUDY]** exactly one `capability_type` is registered system-wide (the CMoE study's own finding, §85/93). C-MoE does not introduce this risk — it multiplies an already-present one across however many hops a WorkGraph has.

**[DECISION]** The correct architectural placement is therefore: a thin Evidence/Verification primitive that lives at the **Kernel/execution layer** (`WorkflowRuntime` / `CapabilityExecutorWorker`'s neighborhood), not inside C-MoE — matching the CMoE study's own stated principle that C-MoE *consumes* durability, memory, and evidence infrastructure through governed contracts rather than *owning* it (its own words: "Everything else... is modeled as infrastructure C-MoE consumes"). Built this way, it benefits today's single-capability system and tomorrow's C-MoE identically, and it fills stub fields that already exist rather than adding parallel ones.

---

## B. Current-state audit

**[FACT]** No standalone "Verification / Critic / Evidence" subsystem exists in this repository, and none is frozen. Checked directly: filename search, class/def search (`Verif`, `Critic`, `Evidence`, `VerificationState`, `EvidenceRecord`, `VerifiedState`), `ADR_INDEX.md`, `KNOWN_ISSUES.md`. The only real hits are `core/memory/retrieval/graphrag/evidence.py` (a narrow, unrelated `Evidence` dataclass for RAG-citation provenance — "why is this retrieved item here," not "did this task's output satisfy the request") and a memo verifying one specific packet's completion, not a subsystem. **[INFER]** The governing task's §21 premise — that a frozen Verification/Critic/Evidence architecture already exists and must not be casually replaced — does not match this repository. **[STUDY]** This is the same shape of error `KNOWN_ISSUES.md` has already self-corrected twice: the "K4.3 = C-MoE" premise "came from a governing prompt, not from this project's own roadmap." I'd treat §21's premise the same way rather than build a reconciliation against something that isn't there.

**[FACT]** What *does* exist is extensive, deliberate, forward-compatible design inside `docs/studies/OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md` (proposed, not implemented, per this project's own Architecture Freeze Principle):
- `verification_status` kept as an enum stub (`UNVERIFIED` default) specifically so Verification has somewhere to write later without a schema migration.
- Five confidence dimensions, deliberately never averaged into one score, one of them literally named "verification confidence... stub value until Verification exists."
- A five-state node-trust model (`REUSABLE`/`STALE` distinguished from `VALID`/`INVALID`) governing whether a result is reused, cheaply re-checked, or recomputed.
- A task-level status enum (`COMPLETED | COMPLETED_WITH_WARNINGS | PARTIALLY_SATISFIED | BLOCKED | FAILED | ABANDONED | CANCELLED | REQUIRES_USER`) where full `COMPLETED` is **structurally unreachable** without a real Verification result or explicit user confirmation — the study's own words: self-certified completion is "precisely the 'false success' failure mode." One correction worth carrying forward: the study attributes a quote — "completion reports cannot be trusted without verification" — to `KNOWN_ISSUES.md`. **[FACT]** Checked directly this session: that string does not appear in `KNOWN_ISSUES.md`. It's a fair paraphrase of the real A6/A7 incident (a report claiming "VERIFIED AND PRODUCTION-READY, 86/86 passing" that didn't match the actual repository), not a citation — worth fixing if that study is ever revised, not a reason to distrust the underlying conclusion.
- A `primary+verifier` composition primitive, explicitly scoped as "the verification hook, not full Verification" — and `critic → correction` loops explicitly excluded from K4.3, citing **[EXT, re-verified]** the AgentTether paper's finding that blind retry without a diagnosis step is a known, published failure mode, not an OCBrain-specific worry.
- `ArtifactProvenance.verified_by: Optional[str]  # verification event, once §77 exists` — a field already sitting there, unfilled.

**[FACT]** Directly relevant existing debt, all confirmed by direct read this session:
- **DEBT-003** — `EventStream.create_checkpoint()`/`get_checkpoint()`/`replay()` are real, implemented (`core/events/event_stream.py`), but `WorkflowRuntime` never calls them. Reclassified (correctly, Aug 29) as a Kernel v1.0 completion item in its own right, not merely a C-MoE prerequisite — its blocking prerequisite (identity linkage) is now resolved via `ADR-KERNEL-01`.
- **DEBT-015** — an `Operation`/`ExecutionAttempt`/`ExecutionSnapshot` schema, proposed only, not implemented. The closest existing proposal to an "Evidence model" — should be reconciled with, not duplicated (see §F).
- **DEBT-016** — the watchdog/progress-monitor duplication between the graph-aware and model-router-facing implementations.
- **DEBT-007** — `BudgetGovernor.evaluate()` is correctly implemented and would reject given real numbers, but nothing in the repository increments the counters it reads, so its reject branch is unreachable in production. **[INFER]** This is the same *shape* of bug as the completion-boolean issue in a different subsystem: a correct gate, never fed real data. Worth naming as a pattern, not a coincidence — any Verification gate proposed here needs an explicit answer to "what actually calls this," or it risks becoming a second instance of the same thing.
- **DEBT-008** — `EventStream` itself has no dedicated checkpoint/replay test coverage. The mechanism a Verification/Evidence layer would need to trust is, today, under-tested.

**[FACT]** A working precedent that "evidence outranks self-report" is achievable in this exact codebase, not a foreign idea: `core/model_router.py` already implements a real `bootstrap → shadow → native` promotion lifecycle for models, gated on `SHADOW_PROMOTE_MIN_QUERIES = 500` and `SHADOW_PROMOTE_THRESHOLD = 0.85` — externally-measured thresholds, not self-report. Verification, as proposed below, generalizes this pattern rather than inventing a new one.

---

## C. Failure propagation analysis

**[FACT]** Concrete, code-verified chain (same repro as the prior session's report): a capability call returns without erroring → `WorkerResult.success = True` (mechanical: the call didn't throw) → `WorkflowRuntime`'s last-node mirroring (`runtime.py:280`) → `workflow.completed` payload (`:320`) → `EvaluatorWorker.goal_completed` (`evaluator.py:172`). At no hop does anything compare the result against the `Constraint` set extracted from the original goal — `EvaluatorWorker` has zero references to `Constraint` anywhere in its source, confirmed by repo-wide grep.

**[INFER]** Under a single registered capability, this is a one-hop propagation — bad, but contained. The governing task's real concern is correct: once a second `capability_type` exists and C-MoE begins chaining calls, the exact same unchecked-boolean mechanism sits at every hop, with no structural reason an early wrong result gets caught before hop 150 rather than hop 1. **[EXT]** This maps directly onto the literature's outcome-reward-model (ORM) vs. process-reward-model (PRM) distinction: an ORM-shaped system — reward/verify only the final output — has a documented credit-assignment problem where a trajectory can fail despite many correct intermediate steps, or succeed despite flawed ones, because sparse terminal feedback cannot localize which step was wrong. OCBrain's current completion semantics are ORM-shaped by construction, not by choice — nothing was ever built to be PRM-shaped, so it isn't.

---

## D. Target architecture

```
   C-MoE (routing / reasoning / composition — future milestone, per CMoE study)
        │  consumes verified_state, unresolved_scope, contradictions
        ▼
   ┌─────────────────────────────────────────────┐
   │  Verified State  (§G)                        │
   └───────────────────▲───────────────────────────┘
                        │ produces
   ┌─────────────────────────────────────────────┐
   │  Verification  (§E lifecycle, §K escalation)  │  ← Kernel/execution-layer owned
   └───────────────────▲───────────────────────────┘
                        │ consumes
   ┌─────────────────────────────────────────────┐
   │  Evidence  (§F)  — persisted via EventStream  │
   └───────────────────▲───────────────────────────┘
                        │ emitted by
   Capabilities (CapabilityExecutorWorker, today: LLM_COMPLETION only)
```

**[DECISION]** Deliberately rejected: a design where every node execution triggers an LLM-based verifier. Two independent reasons converge on the same conclusion. Cost (§16 of the governing task — this would make OCBrain slower in direct proportion to its own ambition). And **[EXT]** AgentProcessBench's finding that current LLM-as-judge verifiers carry a measured, significant bias toward positive labels and struggle specifically to distinguish benign exploratory steps from real errors — meaning an all-LLM verification layer would systematically under-catch exactly the "plausible but wrong" failure class this whole investigation is about. Deterministic-first, cognitive-as-escalation (§K) is not just cheaper, it is more likely to actually catch the failure mode in question.

---

## E. Verification lifecycle

| Stage | What gets checked | Tier |
|---|---|---|
| Requirement | Does the extracted `Constraint` set look complete relative to the request text (heuristic — catches nothing on its own, flags for a stronger check) | Cheap |
| Planning | Does the plan's `PlanStep` sequence structurally cover the constraint set | Cheap |
| Compilation | Did any constraint present in the `Goal`/plan silently fail to survive into the compiled `WorkflowDefinition` — this is exactly the governing task's §10 example ("do not modify the workbook" captured, then dropped) | Cheap, deterministic diff |
| Execution (per node) | Does this node's `Evidence` match its own declared/expected shape | Cheap, deterministic-first |
| **Aggregation** | Does the union of node-level Evidence satisfy the goal-level Constraint set | **This is the hop that is currently entirely missing** — see §C |
| State/artifact mutation | Did a write occur where a Constraint said not to | Deterministic (diff against declared side effects) |
| Final result | Final acceptance — capped at `COMPLETED_WITH_WARNINGS` absent a real verdict, per the CMoE study's own existing decision | Gate |

---

## F. Evidence model

**[DECISION]** Shape modeled deliberately on the *existing* `core/memory/retrieval/graphrag/evidence.py` `Evidence` dataclass — same naming, same "answer why this is here without re-querying" intent, extended from retrieval to execution:

```
ExecutionEvidence:
    subject          # what capability/node produced this
    claim             # what the capability/model asserted (e.g. "story complete, 10,000 words")
    observed          # what was independently, deterministically measured (e.g. actual word count)
    method            # "deterministic" | "cognitive"
    confidence
    source_event_id   # EventStream anchor — reuses existing infrastructure, adds none
    timestamp
    inputs_touched    # recorded from what the capability actually read/wrote, NOT pre-declared
```

**[DECISION]** Persisted via `EventStream.create_checkpoint()`/`append()` — infrastructure that already exists and is already unused (DEBT-003), not a new store. This directly resolves DEBT-003's "never called" gap as a side effect of building Evidence correctly, rather than as a separate goal.

**[EXT]** Reuse policy modeled on Bazel/Buck2's content-addressed caching: Evidence for a given (capability, input-hash) pair is reusable until something in its recorded input set changes. **[INFER]** One necessary caveat, and it's a real one, not a formality: Buck2's own literature distinguishes *Applicative* build systems (dependencies known statically, before anything runs) from *Monadic* ones (dependencies discovered only at runtime). A build system is mostly Applicative. OCBrain capability execution is Monadic — nothing knows what a capability will actually read or touch until it runs. This makes `inputs_touched` something that must be recorded *from* execution, never assumed in advance, and it means naive "just copy Bazel's dependency graph" advice would be wrong for this system. Treat this as harder than the build-system case, not equivalent to it.

---

## G. Verified State model

**[DECISION]** `verified_scope` (Constraint items with satisfying Evidence) / `unresolved_scope` (Constraint items with no Evidence yet) / `contradictions` / `invalidated_set`. **[STUDY]** This is not a new C-MoE-facing concept — it is exactly what the CMoE study's own `RealityBrief` mechanism already reserves a slot for: `RealityBrief` entries are required to carry a trust tag distinguishing `ASSUMPTION`/`RAW_EVIDENCE` from `PROMOTED_KNOWLEDGE`/`VERIFIED_RESULT`. Verified State is the thing that populates the `VERIFIED_RESULT` tag. No new C-MoE-side contract is proposed here; this fills one that already exists.

---

## H. Dependency / invalidation model

**[EXT]** Modeled on Bazel's Skyframe / Buck2's DICE: bottom-up dirty-propagation — when a node's evidence is invalidated, dirtiness propagates only to what actually depended on it, and unrelated branches stay trusted. **[DECISION]** Anchored on infrastructure that already exists in this repository rather than inventing new identity: `WorkflowNodeState.attempt_id` and `root_operation_id` (both added by `ADR-KERNEL-01`, resolving the Kernel's own identity-linkage blocker) are the natural addressing scheme for "what specifically got invalidated" — A→B→C→D→E from the governing task's §9 maps onto a chain of `attempt_id`s under one `root_operation_id`, not a new invalidation-specific identity.

---

## I. C-MoE integration

Verification/Evidence sits below C-MoE, consumed through the contract the CMoE study already drafted: `verification_status`, the `verification confidence` field (currently a stub), and the `VERIFYING` state already present in that study's own outcome state machine (§31/§93 — "Verification requested," transitioning to `COMPLETED` or `REPLANNING`). **[DECISION]** Nothing here proposes a new C-MoE-side vocabulary; it proposes the implementation behind slots the existing design intentionally left open.

---

## J. Resource optimization

**[STUDY]** Reuses, rather than replaces, the CMoE study's own trust-vs-recompute decision (its `REUSABLE` vs. `STALE` distinction, and its heuristic that `STALE` nodes get cheaply revalidated rather than blindly reused or blindly recomputed whenever revalidation cost is materially lower than recomputation cost). Verified State (§G) is the concrete artifact that decision operates over — this section doesn't add a second policy, it makes the existing one implementable.

---

## K. Verification escalation

```
deterministic check (counts, lengths, schemas, checksums — most of the
   governing task's own §3 "quantitative scope" examples need nothing else)
        │ sufficient → continue
        ▼ ambiguous / high-risk
stronger deterministic check (diff against declared side effects, coverage count)
        │ still ambiguous / genuinely semantic
        ▼
cognitive check (C-MoE / LLM) — treated as LOWER default trust than a
   deterministic PASS, per AgentProcessBench's measured positive-label bias
        │ critical / irreversible
        ▼
strong gate (hard stop pending explicit confirmation)
```

**[DECISION]** The asymmetry in the middle tier is deliberate and evidence-backed, not a stylistic choice: a cognitive verifier's PASS should not be treated as equally trustworthy as a deterministic PASS, because the external literature shows LLM verifiers are measurably biased toward passing things.

---

## L. Recovery model

`detect → localize → contain → correct → re-verify → resume`, using infrastructure that already exists rather than new machinery: `attempt_id`/`root_operation_id` (ADR-KERNEL-01) for localization, `EventStream.create_checkpoint()`/`replay()` (real, unused — DEBT-003) for resume. **[EXT]** One concrete constraint from the durable-execution literature (Temporal, LangGraph, and the AWS saga-orchestration pattern for compensating transactions) that the governing task's §14 doesn't name but needs: a "local correction / retry" is only safe *without* a recorded idempotency key when the capability being retried is provably side-effect-free. **[INFER]** Today that's trivially true — the only registered capability is `LLM_COMPLETION`, which is stateless. It stops being true the moment a second, effectful `capability_type` (a file write, an API call) is registered, at which point retry-without-idempotency becomes a real hazard (duplicate writes, duplicate sends), not a theoretical one. Flagged as a forward requirement to design for now, not a currently-blocking gap.

---

## M. Multi-task / long-running execution

Task/execution/capability-invocation/evidence identity already has a real, just-resolved anchor: `root_operation_id` threaded `Goal → ExecutionPlan → WorkflowDefinition`, plus per-attempt `attempt_id` on `WorkflowNodeState` (`ADR-KERNEL-01`). **[DECISION]** Evidence and Verification records should key off this existing identity model directly rather than introduce a second one — cross-task contamination and shared-artifact concerns (governing task §17) are then a matter of correctly scoping `root_operation_id` boundaries, not a new subsystem.

---

## N. Architecture delta

| | Item |
|---|---|
| **Existing** | `verification_status`/confidence stubs, `REUSABLE`/`STALE` model, capped task-status enum, `RealityBrief` trust tags (all CMoE study, proposed); `EventStream.create_checkpoint`/`replay` (implemented, unused); `attempt_id`/`root_operation_id` (implemented, ADR-KERNEL-01); `model_router.py` promotion lifecycle (implemented, working precedent); `graphrag/evidence.py` (implemented, narrow scope) |
| **Required additions** | `ExecutionEvidence` record type at the execution layer (§F); an aggregation-stage check between per-node execution and `workflow.completed` (§E) — this is the one genuinely missing hop |
| **Optional improvements** | Deterministic-first escalation ladder as a formal policy object rather than ad hoc (§K); dependency-invalidation propagation reusing `attempt_id` (§H) |
| **Future C-MoE extensions (already scoped out by the CMoE study itself)** | Cognitive verifier composition beyond the single `primary+verifier` hook; multi-expert disagreement handling; `critic → correction` loops (explicitly deferred, citing AgentTether) |

---

## O. Repository impact (list only — nothing modified this session)

`core/workflow/runtime.py` (aggregation-stage hook point) · `core/runtime/execution_outcome.py` (the `is_success` conflation) · `core/workers/evaluator.py` (currently the only thing reading `goal_completed`, and not wired into the live path at all) · `core/events/event_stream.py` (already sufficient — reuse, don't rebuild) · `core/cognitive/planner.py` (`Constraint` dataclass would need the quantitative field the prior audit found missing) · a new `core/verification/` module, naming convention matching the existing `core/memory/retrieval/graphrag/evidence.py` precedent.

---

## P. Recommended implementation phases

Classified per the governing task's own A/B/C/D scheme. Classification, not a decision — routed to the project owner, not decided here, consistent with `KNOWN_ISSUES.md`'s own established pattern of routing exactly this kind of call rather than having a session self-assign it.

- **(A?) Flagged, not decided:** the `is_success` conflation and unused `COMPLETED_WITH_PARTIAL_OUTPUT` (prior session's report) is a live correctness bug independent of C-MoE's timeline. Whether it rises to a Kernel v1.0 freeze item is the project owner's call — Kernel v1.0's own two resolved blockers (per `ADR-KERNEL-01`) didn't include it, so it isn't automatically one by association.
- **(B) Small, compatible hardening:** wire `EventStream.create_checkpoint()` into `WorkflowRuntime` (resolves DEBT-003 regardless of C-MoE timing); stop `is_success` treating partial as full.
- **(C) C-MoE preparation:** `ExecutionEvidence` record type + the aggregation-stage check + dependency-invalidation propagation — sized specifically to fill the stub fields the CMoE study already reserved, not to exceed them.
- **(D) Future, post-freeze:** cognitive/semantic verifier composition beyond the single hook, multi-expert disagreement handling, full correction loops — all already explicitly out of scope in the existing CMoE study, and nothing in this document's findings changes that.

---

## Open items not resolved this session

`core/workers/supervisor.py` and `reflection.py` were not independently re-audited — `EvaluatorWorker`'s own docstring already established that none of Evaluator/Reflection/Supervisor has an autonomous trigger in the live path, which is enough to flag the same wiring gap applies here without re-deriving it file-by-file. Exact response-finalization location (where a `WorkflowRuntime` return value becomes literal user-facing text) remains open from the prior session's report and is the same open item here — it's where the aggregation-stage check in §E would actually need to sit.
