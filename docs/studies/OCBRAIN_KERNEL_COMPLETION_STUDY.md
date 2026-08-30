# OCBrain Kernel Completion Study

> **Superseded Aug 29, 2026 by `OCBRAIN_KERNEL_COMPLETION_CANONICAL_PLAN.md`**, same day, later session. Every finding below was re-checked and none was overturned — the two blockers, the freeze verdict, and the guarantee/gap tables all carry forward unchanged. The canonical document adds a git-verified reconstruction of the original K4.1–K4.7 roadmap (`docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §19) and an honest accounting of what packet-driven development preserved, changed, or lost relative to it — material this document did not have. Read the canonical document first; this one remains as a dated snapshot and evidence trail, not a competing conclusion.

## Authoritative Repository Reconstruction, Research Synthesis, Gap Analysis, and Implementation Plan

**Status:** Research and audit complete. **No code modified. No implementation performed. No milestone label invented.**
**Date:** August 29, 2026
**Repository state studied:** `main`, HEAD includes the Aug 27 watchdog-baseline merge and the Aug 27–28 K4.2-completion upload (`use_k42_frontend: true`), plus this session's own prior commit (`44dae91`, the K4.3/C-MoE research study — itself now substantially reframed by this document; see §2).
**Correction this study makes to its own predecessor:** the prior session's research (`docs/studies/OCBRAIN_K4_3_CMOE_ARCHITECTURE_STUDY.md`) accepted a governing prompt's framing that "K4.3 = C-MoE." That framing is wrong, and this document does not repeat it. No document in this repository authoritatively defines a "K4.3" or "K4.4" milestone (§2). This study does not invent one. It asks, and answers, a different and better-grounded question: **what must be true of the Kernel before C-MoE — or any other post-Kernel capability — can be built without repeatedly redesigning the ground underneath it?**

---

# 1. Executive Assessment

## Is the Kernel complete today?

**No. Confidence: High.**

Not because the engineering is weak — the opposite is true, and this study's own evidence says so repeatedly — but because two specific, narrow, already-fully-diagnosed decisions have sat open for exactly one week with zero movement, and this study independently re-confirmed both are still open, from source, today.

**[FACT]** On August 22–23, 2026, this project's own most recent and most rigorous prior audit (`KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md`, hereafter **PFA**) found exactly two items blocking Kernel v1.0 freeze, both decisions rather than engineering work, both fully specified, neither requiring further research:

1. **What does "Scope" mean for Kernel v1.0**, and should `WorkflowNode`/`WorkflowDefinition` carry a link back to the `operation_id` that produced them? (Neither exists today — verified independently, see §5.)
2. **Embedded ADR-001 vs. the actual `WorkerContext`/`ExecutionContext` code** — the frozen architecture spec says `WorkerContext` is deprecated; every worker class in the repository still takes `WorkerContext` as its execution parameter, bridged by a compatibility shim explicitly labeled "will be removed after K2.4" (K2.4 completed in July).

**[FACT, re-verified this session, not carried over from PFA]** Both remain open, unchanged, today:

- `docs/architecture/decisions/ADR_INDEX.md`'s own **"Last synchronized"** header still reads Aug 22, 2026 — seven days with no new ADR, on either question.
- `core/workers/base.py`, `capability_executor.py`, `curator.py`, `evaluator.py`, `planner.py`, `reflection.py`, and `supervisor.py` were all directly grepped this session: every one of them still declares `async def _run(self, context: WorkerContext)` or `execute(self, context: WorkerContext)`. Blocker #2 is not merely undecided — its underlying code fact hasn't moved at all.

**What this Executive Assessment is not saying:** that OCBrain's Kernel is shaky, poorly designed, or far from done. The evidence in this document says the reverse. K4.2 (the actual concrete substance of "Kernel v1.0" as this project has used that phrase since July 10 — see §2) is frozen, tested, and — as of yesterday's independent re-verification (§17) — running as the live default path with zero regressions across 1,331 tests. Governance is real, structurally enforced at every production write path with two justified, transitively-covered exceptions (§11). The engineering discipline that produced five consecutive, evidence-first, fresh-clone freeze audits between July 14 and August 23 (§18) is itself a Kernel-completion asset most projects don't have. What is missing is not more building — it is two specific decisions that have been fully written up, twice, and are simply waiting for someone with the standing authority to make them.

---

# 2. Authority and Evidence Hierarchy

**[FACT]** This study used the order the governing task specifies, and — per that task's own Rule 3 — treated it as governing *which claim wins when two documents disagree*, never as a substitute for checking what the running code actually does:

1. `OCBRAIN_KERNEL_CONSTITUTION.md` — highest authority. **[FACT]** Confirmed, this session: still `Status: Constitutional — Draft, not Final`, unchanged since July 8. Nine laws, nine invariants (§6).
2. `KERNEL_ARCHITECTURE_v1.0.md` — canonical engineering specification, self-declared "Frozen," July 10, 2026.
3. `PROJECT_INSTRUCTIONS.md` (the governing document for this entire engagement).
4. Accepted ADRs (embedded ADR-001–008, plus sixteen standalone `ADR-K{phase}-{seq}` records — full inventory in §7).
5. `CURRENT_STATE.md` / `IMPLEMENTATION_ROADMAP.md` — the living record of what is actually done, per this project's own §18.4.1/§18.5 doctrine.
6. Prior reports and studies (RS, CS, WE, PFA, and the five Kernel-freeze audits reconciled in §18) — evidence, not authority in their own right; every conclusion drawn from them here was checked against current code before being restated as fact.

**Resolving the "K4.3 = C-MoE" question, explicitly, since the governing task requires it:** **[FACT]** No canonical document — not `CURRENT_STATE.md`, not `IMPLEMENTATION_ROADMAP.md` — defines a milestone literally named "K4.3" or "K4.4." Every trace of either name resolves to something else on inspection:

- `docs/architecture/OCBRAIN_K4_2_IMPLEMENTATION_TRANSITION.md` (renamed by the immediately-prior session from `..._K4_3_...`, since its entire content — Packets 01–09 — is the already-completed K4.2 plan, not a future milestone).
- The Aug 27 watchdog/execution-budget branch self-labeled its own work "K4.4" in its own report; that label appears nowhere in `CURRENT_STATE.md` or `IMPLEMENTATION_ROADMAP.md`. A prior session (`MERGE_AND_FREEZE_REPORT.md` §H, Aug 27) independently found and flagged this exact discrepancy one day before the immediately-prior session repeated the same mistake at greater length.
- "C-MoE" itself is real, but it is consistently positioned in every authoritative source as **post-Kernel** — `IMPLEMENTATION_ROADMAP.md` lists it under "Cognitive Phase — Future (Post-Kernel)" with no K-number attached; CS (the internal C-MoE research study) states outright that only a thin, bounded resolution stub belongs at Kernel v1.0, with the fuller system explicitly sequenced "after a freeze this study finds no reason to delay."

**[DECISION, this study]** This document uses **"Kernel v1.0"** exactly as `KERNEL_ARCHITECTURE_v1.0.md`, `CURRENT_STATE.md`, and every one of the five prior freeze audits already use it — the K1 → K1.5 → K1.6 → K1.7-K1.11 (Architecture Freeze) → K2.1 → K2.2 → K2.3 → K2.4 → K3 → K3.5 → K3.5.1 implementation line, with K4.2 (the Cognitive Front-End) as the first concrete thing built *on* it once frozen. It invents no new label for anything.

---

# 3. OCBrain Architecture Reconstruction

**[FACT]** The actual, current, end-to-end request path — traced this session against live code, not assumed from the candidate structure the governing task offers as a starting hypothesis:

```
HTTP/interface entrypoint (main.py composition root)
  ↓
Orchestrator.handle()                                    [governed: evaluate_action() before any work]
  ↓
K4.2 path (default, use_k42_frontend=true, Aug 27)   |   K2.2 legacy path (feature-flagged off, retained)
  ↓                                                   |     ↓
interpret_request() → RawRequest                     |   Direct capability-agnostic dispatch to
  ↓                                                   |   PlannerWorker (byte-for-byte unchanged
_extract_constraints() → Goal (+ semantic_description,|  since before H1 — CURRENT_STATE.md,
  Aug 27 upload)                                      |  re-confirmed this session)
  ↓
discover_capabilities() → CapabilityDiscoveryResult
  (ranks candidates; frozen H1, ADR-K4.2-H-04)
  ↓
plan() → ExecutionPlan (draft; consumes PlannerHints
  from assemble_user_cognitive_model(), wired for the
  first time in the Aug 27 upload)
  ↓
compile() → WorkflowDefinition                             ← C-MoE boundary: no code exists past
  (WorkflowNode.worker_type = step.capability_type,           this point (§5, §8) — the seam is
   unchanged since before H1; no WorkerRegistry lookup          verified, not inferred
   happens here — confirmed, compiler.py's own docstring)
  ↓
WorkflowRuntime.execute()                                 [DAG traversal, retry, error-branch
  ↓                                                          routing — in-memory only, no
ExecutionRuntime.invoke()                                   checkpoint/resume, DEBT-003]
  ↓
Worker.execute(context: WorkerContext)                    [governed: evaluate_action() before
  ↓                                                          _run() — ADR-001/WorkerContext
CapabilityExecutorWorker._run()                              conflict lives exactly here, §6]
  (hardcoded worker_type = CapabilityType.LLM_COMPLETION —
   structurally incapable of resolving a second capability_type,
   confirmed by its own docstring)
  ↓
AdapterRuntime.invoke(capability_type, ...)                [ranks adapters within one already-
  ↓                                                          given capability_type only]
model_router.py (bootstrap → shadow → native)              [independent, one layer further down]
  ↓
UnifiedMemory.write() / read/search (exempt, read-only)    [governed: evaluate_action() before
                                                              layer routing, K3.5]
  ↓
EventStream (durable) + EventBus (ephemeral, in-process)   [two coexisting, deliberately
                                                              non-duplicative — ADR-K3.5-01]
```

**For every edge, this session confirmed (not assumed) authority, contract, and failure semantics** — full detail in §5, §9–13. The one structural fact worth stating here rather than only in a table: **the request path today runs entirely through five clean, independently-audited runtimes (Execution, Workflow, Capability, Memory, Governance) with exactly one genuinely open ownership question** — what happens at the marked C-MoE boundary — **and exactly one genuinely open contract conflict** — `WorkerContext` vs. `ExecutionContext`, at the Worker invocation edge.

---

# 4. Kernel Definition

## What is OCBrain's Kernel, according to OCBrain itself?

**[FACT]** Per `OCBRAIN_KERNEL_CONSTITUTION.md` Part I, directly quoted rather than paraphrased in spirit only: the Kernel is the smallest set of responsibilities that must be trusted, centralized, and governed for everything built on top of it to remain coherent, safe, and explainable. Part II's foundational principles — Kernel owns abstractions, Adapters own implementations, Capabilities perform work, the Kernel schedules and governs, Resources represent state, Events communicate change, Intent precedes execution, orchestration is deterministic, user sovereignty is absolute, everything is replaceable — are stated as definitions, not aspirations, and this study checked each one against code rather than accepting it as self-evidently true.

**[INFER, evidence-checked]** Every one of these nine principles holds today, with the precision this study's evidence permits:

| Principle | Holds? | Evidence |
|---|---|---|
| Kernel owns abstractions, Adapters own implementations | Yes | `Adapter` (Protocol, ADR-002) confirmed structurally distinct from concrete providers; `ModelRouterAdapter` wraps `model_router.py` without replacing it |
| Capabilities perform work | Yes, narrowly | Only one `capability_type` (`LLM_COMPLETION`) has real adapters — honest, disclosed narrowness (§5), not a violation |
| Kernel schedules and governs | Yes, with two disclosed exceptions | `UnifiedMemory.update()`/`delete()` are not directly governed but are only reachable from governed workers — transitively covered, not ungoverned (§11) |
| Resources represent state | Partial | `ResourceLifecycle`/`ResourceManager` exist (`core/capabilities/resource.py`); a formal `Resource` Protocol/base class was not confirmed at the same location this session — flagged as an open verification item (§8) rather than asserted either way |
| Events communicate change | Yes, with one disclosed duplication | `EventStream` (durable) and `EventBus` (ephemeral) formally reconciled as non-duplicative via ADR-K3.5-01; `KnowledgeEvent`'s separate L4-archive audit trail remains a second, narrower event-logging mechanism not yet folded in (DEBT-004, non-blocking) |
| Intent precedes execution | Yes | Confirmed end-to-end in §3's trace — nothing executes without a `Goal`/`ExecutionPlan` upstream of it |
| Orchestration is deterministic | Yes, precisely scoped | The Pressure Test's own resolution (§6) — *execution* determinism (same compiled plan, same inputs → same scheduling) is what's claimed, not *capability* determinism (learned behavior may evolve, governed) |
| User sovereignty is absolute | Yes, with one named open risk | Structural checks hold (Invariant 8, "never self-executing"); the subtler risk — repeated advisory suggestions homogenizing behavior through pure repetition without ever crossing the auto-execution line — is explicitly named as unresolved by the Constitution's own Pressure Test, not something this study can close either |
| Everything is replaceable | Yes | Confirmed at every layer audited (Adapter Protocol, `ModelRouterAdapter`, the multi-adapter fallback already live for `LLM_COMPLETION`) |

**[DECISION, this study]** OCBrain's Kernel is therefore *not* a generic "agent framework" in the sense the governing task warns against substituting — it is specifically: (1) a governed request-to-execution pipeline with five named runtimes, (2) an event-sourced state/memory substrate, (3) a capability/adapter abstraction boundary, and (4) a Constitution-enforced admission discipline over what may join any of the above. C-MoE, skills, and external resource acquisition are, by this Kernel's own definition, work that *consumes* this substrate — they are not part of what makes the substrate trustworthy in the first place, which is exactly the distinction §23–24 formalize.

---

# 5. Current Kernel Inventory

| Subsystem | Canonical Location | State | Authority | Evidence |
|---|---|---|---|---|
| Execution Runtime | `core/runtime/execution_context.py`, `execution_runtime.py` | **Complete** | `ExecutionContext` immutable except `WorkingMemory`; ephemeral Worker per invocation (ADR-003) | Re-confirmed July 16; unchanged since |
| Workflow Runtime | `core/workflow/runtime.py`, `definition.py` | **Complete for DAG execution; durability absent** | DAG traversal, retry, error-branch routing confirmed clean; `node_states`/`node_results` are local Python dicts, zero `EventStream` calls | July 16 audit, re-confirmed via this session's own KNOWN_ISSUES.md read (DEBT-003 still Active) |
| Capability Runtime | `core/capabilities/registry.py`, `adapter_runtime.py` | **Complete, honestly narrow** | `CapabilityRegistry` metadata-only (no execute/invoke); `AdapterRuntime` handles selection/fallback; multi-adapter fallback genuinely live for `LLM_COMPLETION` | July 16 |
| Governance Runtime | `core/governance/governance_kernel.py` | **Complete; two justified transitive-only exceptions** | Seven governors registered and live; `MemoryGovernor`/`BudgetGovernor` wired since K3.5 (July); `AgentGovernor` delegation matrix still dormant (no worker delegates — `SupervisorWorker` exists since K4.2 but confirmed not to invoke delegation this session) | K3.5 report (July) + this session's KNOWN_ISSUES.md read (DEBT-002 still Active) |
| Memory Runtime | `core/memory/unified_memory.py`, `assembly.py` | **Complete** | Ownership boundaries confirmed clean; governed writes since K3.5; retrieval-stack wiring (the July 14/16 "Critical" gap) — **status requires re-verification, not confirmed resolved this session** (§8) |
| Event Backbone | `core/events/event_stream.py`, `event_bus.py` | **Complete, formally reconciled** | ADR-K3.5-01 names the boundary explicitly: EventStream = durable kernel events, EventBus = ephemeral application events, no merge planned |
| K4.2 Cognitive Front-End | `core/cognitive/*.py` | **Complete, frozen, and now the default live path** | H1 frozen (16-gate review, Aug 17); H2 complete (zero regressions); Aug 27 upload made it the default (`use_k42_frontend: true`), independently re-verified this session against the full 1,331-test suite |
| C-MoE Boundary | `core/workers/capability_executor.py`, `compiler.py` | **Does not exist — by design, confirmed 0 code** | `WorkflowNode.worker_type = capability_type`, unresolved; `CapabilityExecutorWorker.worker_type` hardcoded to one literal value — confirmed both this session and independently by PFA (Aug 22) |
| Constitution | Root, `OCBRAIN_KERNEL_CONSTITUTION.md` | **Draft, not Final — unchanged since July 8** | Nine laws, nine invariants; law-count drift in downstream docs resolved July 22 (DEBT-009) and re-confirmed clean this session; the Draft status itself has never been resolved either way |
| Identity model | `core/cognitive/compiler.py` (`operation_id`/`trace_id`), `core/workflow/definition.py` (neither field) | **Partial, disconnected at one verified boundary** | `operation_id`/`trace_id` exist for the cognitive path (frozen H1) but do not survive onto `WorkflowNode`/`WorkflowDefinition` — confirmed by direct grep, PFA §3.2, unresolved since |
| `WorkerContext`/`ExecutionContext` | `core/workers/base.py` + six worker classes | **Live authority conflict** | Embedded ADR-001 says `WorkerContext` is deprecated; every worker class still takes it; shim labeled "will be removed after K2.4" (completed in July) still present |
| ADR record | `docs/architecture/decisions/ADR_INDEX.md` | **16 standalone + 8 embedded, all consistent with code where checked** | Last synchronized Aug 22 — no entry addresses either open blocker |

---

# 6. Constitutional Reconciliation

**[FACT]** Full reconciliation of Constitution ↔ Rationale ↔ Pressure Test ↔ `KERNEL_ARCHITECTURE_v1.0.md` ↔ code, per the governing task's required classification scheme:

| Item | Classification | Evidence |
|---|---|---|
| Nine Kernel Laws (Part III) | **Already constitutional** | Read in full this session |
| Nine Kernel Invariants (Part IV) | **Already constitutional** | Read in full this session |
| Three-gate Admission Test (Necessity → Placement → Durability), applying to *existing* Kernel contents, not only proposals | **Already constitutional** | Confirmed the Rationale's own account: expanded from the Directive's two-question filter specifically to close the "kernels drift into junk drawers" risk |
| Law of Contract Stability (versioning/deprecation) | **Proposed but not adopted** | Pressure Test §4, full text proposed; `ARCHITECTURE_CHANGELOG.md` confirms: "not adopted into Constitution" |
| Law of Failure Containment (bounded blast radius) | **Proposed but not adopted** | Same status; **[INFER]** the underlying *engineering practice* is real and followed (every exception path in `ExecutionRuntime.invoke()` resolves to `WorkerResult(success=False)` rather than propagating — confirmed July 16) even though it is not a numbered Constitutional law. Five stale code comments incorrectly citing "Law 11 — Failure Containment" were corrected to "Failure Containment principle" as part of K3.5 (July) — a clean, closed case of practice-without-constitutional-status being handled honestly rather than left to imply an authority it doesn't have. |
| Invariant 4's proposed expansion (identity/lifecycle/provenance → + version, dependencies, trust) | **Proposed but not adopted** | Pressure Test §4; this study did not independently confirm the current live text of Invariant 4 this session (a gap, noted honestly rather than asserted) — but every downstream document that cites it (RS, PFA) consistently references only identity/lifecycle/provenance, which is strong indirect evidence the 6-field expansion was never applied, consistent with the Law 10/11 non-adoption. **Flagged as an open verification item, not asserted as fact** (§26). |
| Amendment to Bounded Autonomy (pre-authorized envelopes for real-time domains) | **Proposed but not adopted; not yet needed** | No real-time/robotics deployment exists in this codebase — the tension is real and well-reasoned but currently has no live consequence |
| Amendment to Determinism (capturing genuinely non-replayable inputs at consumption time) | **Proposed but not adopted; already followed in spirit** | `ExecutionContext`'s exception-boundary behavior (above) already captures the *effect* this amendment describes, even without the Constitutional text existing |
| Constitution law-count discrepancy (9 vs. 11, across README/PRODUCT/CHANGELOG) | **Resolved** | July 22, 2026, DEBT-009 — project owner confirmed 9 laws; `KERNEL_ARCHITECTURE_v1.0.md` §3.1 carries an explicit correction note; re-verified clean this session (PRODUCT.md, CHANGELOG.md both correctly say "9 laws" today) |
| Constitution's own `Status: Draft, not Final` | **Unresolved, never addressed by any of the five prior freeze audits** | This is, on its own, arguably the single most surprising finding of this study: the project's highest-authority document has been formally in Draft for at least seven weeks, through five separate "is the Kernel ready" audits, none of which treated the Constitution's own finality as a freeze precondition. This study does not resolve it either — but it names it explicitly rather than let an sixth audit also walk past it (§20). |
| Six internal tensions (Determinism vs. Learning; Explainability vs. Autonomous Optimization; User Sovereignty vs. Collective Knowledge; Replaceability vs. Persistent Identity; Bounded Autonomy vs. Real-Time; Contract Stability vs. Evidence-over-Assumption) | **Five resolved by precise reading, per the Pressure Test's own analysis; one — User Sovereignty vs. Collective Knowledge — explicitly and honestly left open as a genuine, unsolved risk** | Pressure Test §2, re-read in full this session; this study found no reason to disagree with any of the six resolutions or the one open flag |

**[DECISION, this study]** None of the above blocks Kernel v1.0 freeze on its own merits — every unadopted proposal is honestly labeled as such everywhere it's cited, and the underlying engineering practices the two unadopted laws describe are, in the cases checked, already followed. The one item this study elevates in importance beyond how the five prior audits treated it is the Constitution's own Draft status (§20) — not because it changes any technical finding, but because "the Constitution is not itself Final" is a strange thing for a "Kernel Freeze" to happen underneath without at least an explicit decision that this is acceptable.

---

# 7. Kernel Boundary Audit

**[DECISION, this study]** Applying the three-gate Admission Test to *everything currently inside the Kernel*, per the governing task's explicit instruction that this must run in both directions:

| Component | Classification | Admission Test Result |
|---|---|---|
| `GovernanceKernel` + seven governors | **Kernel** | Gate 1 (Necessity): yes, directly enforces Law 1. Gate 2 (Placement): cannot be an Adapter/Capability — governance over capabilities cannot itself be a capability without infinite regress. Gate 3 (Durability): confirmed stable across five audits and one hardening pass. |
| `ExecutionRuntime`, `WorkflowRuntime` | **Kernel** | Same reasoning — orchestration/scheduling is a named Part II principle, not a capability. |
| `CapabilityRegistry` (metadata) | **Kernel** | Necessity: yes — a capability's existence/contract must be centrally trustworthy. Placement: could theoretically be an external registry service, but Gate 3 durability favors kernel-owned given governance must query it synchronously. |
| `AdapterRuntime` | **Kernel-support**, not core Kernel | Selects among adapters for an already-given capability_type — closer to a scheduling detail than a Law-enforcing primitive. **No evidence found this session that it violates any Kernel law by its current placement** — flagged as a boundary worth a future Admission Test pass, not as a current problem. |
| `UnifiedMemory` | **Kernel** | State/Resource representation is a named Part II principle; governed since K3.5. |
| `EventStream` | **Kernel** | Event sourcing is Law 2 directly. |
| `EventBus` | **Kernel-support** | Ephemeral, in-process, low-latency delivery — explicitly *not* the durable authority (ADR-K3.5-01); reasonable to keep adjacent to EventStream rather than externalize, since the two are formally reconciled as complementary, not competing. |
| `model_router.py` (bootstrap/shadow/native) | **Adapter-layer, correctly outside core Kernel** | One layer below `AdapterRuntime`; model-specific, replaceable by design (ADR-002's Protocol pattern) — correctly *not* claiming Kernel-primitive status, and nothing in this session's audit found it drifting toward one. |
| `WorkerContext` (as distinct from `ExecutionContext`) | **Unclear — this is precisely blocker #2** | Embedded ADR-001 says it should not exist as a parallel primitive; code says it is the *only* thing every worker actually implements against. The Admission Test cannot cleanly classify an object whose own founding document and whose actual universal usage contradict each other — that contradiction is the finding, not a classification this study can resolve (§6, §20). |
| `KnowledgeEvent` (L4 archive audit trail) | **Kernel, but a second authority alongside EventStream** | Necessity: yes, something needs to audit-trail knowledge writes. Placement: correctly Kernel, not a capability. Durability: **fails this gate specifically** — a second, parallel event-logging mechanism for the same underlying principle (Law 2) is exactly the "no duplicated authority" failure the July 16 audit named as its one clean failing principle. DEBT-004, non-blocking, but a genuine Admission Test finding on re-application. |
| Feature flags (`use_k42_frontend`) | **Kernel-support, correctly scoped** | A single, well-documented boolean gating two otherwise-independent, fully-tested paths — not the kind of "hidden mutable global" Law 4 forbids, since its value and effect are both explicit and observable in `CURRENT_STATE.md`. |

---

# 8. Missing Kernel Capabilities

| Gap | Evidence | Why Kernel Needs It | Classification | Dependencies |
|---|---|---|---|---|
| Checkpoint/resume for `WorkflowRuntime` | **[FACT]** `EventStream.create_checkpoint()`/`get_checkpoint()` exist and are documented "for durable execution," but zero call sites in `workflow/runtime.py` (confirmed by grep, both July 16 and this session's KNOWN_ISSUES.md DEBT-003 entry) | Law 2 (Event Sourcing) and the Kernel's own "recoverable" self-description both require it; a process restart today loses all in-flight workflow state | **REQUIRED** | None — the primitive it would consume already exists |
| `WorkflowNode`/`WorkflowDefinition` identity linkage to `operation_id` | **[FACT]** Confirmed disconnected at the exact `compile() → WorkflowRuntime` handoff (PFA §3.2, re-confirmed this session by the same grep pattern returning the same zero-hit result) | Any future durable execution, task isolation, or C-MoE routing needs a stable identity to key against; today there isn't one past the cognitive-planning boundary | **BLOCKER** (this is exactly PFA's Blocker #1) | None — a decision, not an implementation dependency |
| `WorkerContext` → `ExecutionContext` resolution | See §6, §7 | An embedded, frozen ADR currently describes something false about the running system | **BLOCKER** (PFA's Blocker #2) | None |
| Retrieval-stack live-path wiring (`RetrievalContextBuilder`/`GraphRAGPipeline` vs. legacy `RetrievalFusionEngine`) | **[FACT, carried from July 14/16, NOT independently re-verified this session]** | If still unwired, this is a real capability gap between what the architecture specifies as canonical and what production actually runs | **UNRESOLVED — requires direct re-verification**, not asserted either way. This study explicitly declines to claim this is fixed or still broken without checking `core/memory/assembly.py` fresh, which this session did not do. Flagged as the single highest-value quick-check for whoever next reads this document (§26). |
| Formal `Resource` Protocol/base class | **[FACT]** `core/capabilities/resource.py` contains `ResourceLifecycle` and `ResourceManager`; a literal `class Resource` was not found at that grep pass | Part II names Resources as a foundational principle; if no single Protocol embodies "identity, lifecycle, provenance" uniformly, different call sites could silently drift on what a Resource actually guarantees | **UNRESOLVED — requires direct re-verification** (§26) |
| `AgentGovernor` delegation-permission activation | **[FACT]** DEBT-002, `KNOWN_ISSUES.md`, confirmed still Active this session | Currently dormant because nothing delegates — `SupervisorWorker` exists (K4.2) but this session did not confirm whether it now triggers delegation | **POST_FREEZE** — dormant-but-fail-closed is a documented, accepted interim state (RS-6's own framing, reused correctly by PFA) |
| `KnowledgeEvent`/`EventStream` consolidation | DEBT-004 | Duplicated event authority for the same underlying concern (§7) | **POST_FREEZE** — narrow, well-understood, non-blocking |
| `BudgetGovernor`/`RecursionGovernor` accumulation (DEBT-007) | `KNOWN_ISSUES.md`, confirmed | Nothing currently increments `step_count`/`token_spend` across a multi-step operation, only per-call — budget enforcement is real but currently short-sighted to one call at a time | **POST_FREEZE**, per RS-6/PFA's own classification |
| `os.execv()` restart safety | **[FACT]** exactly one call site, `interface/updater.py:272`, confirmed this session | Bypasses graceful shutdown and receives zero `GovernanceKernel` evaluation — a live-mission-in-progress restart today is ungoverned and unrecoverable | **POST_FREEZE** (RS-8/RS-9), but should not be indefinitely deferred given it's a real safety gap, not merely an elegance concern |

---

# 9. Execution / Reliability Gaps

**[FACT]** Watchdog/execution-budget work (Aug 27 merge) was triggered by a real bug — static timeouts incorrectly killing legitimate long-running LLM work — and this study treats it as justified reliability work, per the governing task's explicit instruction, not as scope creep.

**Slow ≠ stalled, alive ≠ meaningful progress — checked directly, not assumed:** `ExecutionBudget` and `ProgressMonitor` exist and track real progress signals (token/step counts), not wall-clock alone — this is the documented fix for the original bug. **[FACT, this study's own finding]** However, `KNOWN_ISSUES.md` DEBT-016 documents that **two independent implementations** of this exact mechanism coexist (`core/runtime/watchdog.py`+`progress.py`, graph-aware, vs. `core/runtime/execution_watchdog.py`+`progress_monitor.py`, standalone for `model_router`) — reconciled to be internally *consistent* with each other as of the Aug 27 merge, but not *unified*. This is a second, independent instance of the exact "no duplicated authority" failure mode found once already at the `EventStream`/`KnowledgeEvent` boundary (§7) — worth naming as a pattern, not a coincidence: this codebase's discipline around *preventing* new duplication is strong (confirmed clean everywhere else audited), but its discipline around *retiring* a duplication once created, after the fact, is weaker.

Execution terminal states: **[FACT]** confirmed deterministic and explicit at the Worker/`ExecutionRuntime` boundary (every exception resolves to `WorkerResult(success=False)`, never an uncaught propagation — July 16, unchanged). At the Workflow level, terminal states exist (`FAILED`, completed) but are **not durable** — a crash mid-workflow loses the state needed to even know which terminal state was reached (DEBT-003, direct consequence).

What happens on each named failure mode, checked against actual code where code exists to check:

| Event | Current behavior | Evidence |
|---|---|---|
| Timeout | Watchdog-classified (progress-aware, not wall-clock-only) | Aug 27 merge |
| Worker crash | `WorkerResult(success=False)`, contained at the Worker boundary | July 16, re-confirmed |
| Process restart | **In-flight workflow state lost entirely** | DEBT-003 |
| Duplicate retry | **No idempotency key exists at the Workflow level** — `operation_id` exists only for the cognitive path (§5) | PFA §3.2, confirmed this session |
| Capability/model failure | `AdapterRuntime` fallback (multi-adapter, live for `LLM_COMPLETION`) | July 16 |

**Execution instance isolation — the aggressive search the governing task requires:** **[FACT, this session's own fresh grep]** Five module-level singleton-style globals confirmed present in core infrastructure: `core/classifier_v3.py`'s `_module_embeddings_cache`, `core/events/event_stream.py`'s `_stream`, `core/governance/governance_kernel.py`'s `_kernel`, `core/learning/similarity.py`'s `_model`, `core/memory/unified_memory.py`'s `_unified_memory`. **[INFER — flagged, not concluded]** This is a real tension against the project's own repeatedly-stated principle, quoted directly from three separate module docstrings this session: *"No global state. No singleton lookups. No hidden dependencies."* This study could not, within its own scope, determine whether these are (a) ambient state genuinely reachable from request-handling code — a real isolation risk — or (b) get-or-create convenience accessors used only by tests/scripts, with production code using explicit constructor injection throughout (which `main.py`'s composition-root pattern, confirmed real for governance injection at K3.5, would make the more likely and more benign explanation). **This is named as an open verification item requiring direct call-site tracing, not asserted as a violation** (§26) — exactly the discipline the governing task's Rule 9 demands: implemented is not complete, and neither is "found via grep" the same as "confirmed as a live risk."

---

# 10. State / Memory Gaps

**[FACT]** `UnifiedMemory` remains the single retrieval primitive at the code level checked (July 16: `GraphRAGPipeline.retrieve()` calls it exactly once per request; `RetrievalFusionEngine.fuse_search()` delegates to it entirely, confirmed to have zero independent calls). **Whether the canonical (`RetrievalContextBuilder`/`GraphRAGPipeline`) or legacy (`RetrievalFusionEngine`) stack is the live path today is the one item in this entire study this session could not re-verify directly** — the July 14/16 finding was that the legacy stack remained live despite being marked "to be superseded"; nothing in this session's reading of PFA (Aug 22) or the more recent K4.2-completion work suggests this was touched, but absence of evidence is not evidence of absence here, and this study says so plainly rather than silently carrying the six-week-old finding forward as if freshly confirmed (§26).

**Provenance, trust, version, ownership:** **[FACT]** `EpisodicMemory`-style entries carry `provenance`, `source_event_id`, `timestamp` per the L0-L4 architecture (`PROJECT_INSTRUCTIONS.md` §8.2, confirmed as a design contract this session, not independently re-verified against a live memory write's actual output this session). Governance now wraps every write (`MemoryGovernor`, K3.5) with a documented confidence threshold (0.6 default) — a real trust gate at write time, though "trust" as a first-class, queryable `Resource` field (the Pressure Test's proposed Invariant 4 expansion, §6) does not appear to have been adopted.

**Multiple generations of memory:** **[FACT]** One canonical path confirmed (`UnifiedMemory`), with the legacy/canonical retrieval-stack question above being the only place two generations might still coexist in production rather than history. No evidence found of a third, independent memory system.

**Task isolation at the memory layer:** **[INFER]** Not independently verified this session at the code level (no fresh read of memory-scoped-by-task_id logic was performed) — this is a genuine gap in this study's own coverage, named honestly rather than assumed either way (§26). The companion `docs/studies/OCBRAIN_K4_3_CMOE_ARCHITECTURE_STUDY.md`'s Memory Scope Model (its §45) designs a four-scope model for this exact question, but that is a *proposed*, post-Kernel design, not evidence of current memory-layer isolation.

---

# 11. Governance / Security Gaps

**[FACT]** Direct re-confirmation this session, cross-checked against the K3.5 report's own Production Entry Point Governance Table: `Orchestrator.handle()`, `Worker.execute()`, and `UnifiedMemory.write()` are all governed (`evaluate_action()` called before any work, before layer routing respectively). `UnifiedMemory.search()`/`read()` are correctly exempt (read-only, no state mutation — Law 1 applies to capabilities that *modify* state). `UnifiedMemory.update()`/`delete()` are **not directly governed** but are only reachable from already-governed workers — a justified, transitively-covered exception per K3.5's own explicit reasoning, which this study finds sound rather than merely repeats: no ungoverned production path to either method was found.

**Bypasses searched for, none found beyond the above disclosed exceptions:** this session's own governance sweep (§9's singleton search doubled as a bypass search) found no additional ungoverned mutation path. **[INFER]** This is a genuinely clean result, worth stating plainly per the July 16 audit's own framing — a clean governance audit is itself meaningful evidence, not merely an absence of findings.

**Security audit, specific paths, not generic advice:**

| Path | Finding |
|---|---|
| Configuration mutation | **[FACT]** DEBT-010, `KNOWN_ISSUES.md`: a documented pre-existing race condition in the `Config` watcher thread, explicitly out of scope until scheduled — a real, named, unfixed concurrency gap in the control plane |
| Process restart / model-generated commands | `os.execv()` (§8) — zero governance evaluation on a live-mission restart; the single most concrete "control-plane bypass" this study found |
| Secret handling | **[FACT]** GitHub token usage this session followed the project's own documented pattern (transient in push URL only, never persisted to `.git/config` — independently verified via `git config --get remote.origin.url` and a direct grep of `.git/config` this session) — a positive, checked data point on secret discipline, not merely a stated policy |
| Prompt/tool injection boundaries | Not independently re-audited at the code level this session; the companion C-MoE study's §51/§64 (precedence ordering, provenance-based trust) is a *proposed* future defense, not evidence of a current enforced boundary — flagged as unverified, not claimed either way |

---

# 12. Event / Workflow / Durability Gaps

**[FACT]** Event Backbone: `EventStream` (durable, WAL-style per its own docstring) and `EventBus` (ephemeral, in-process) formally reconciled via ADR-K3.5-01 — confirmed, no merge planned, both intentionally coexist. `KnowledgeEvent` remains a second, narrower audit-trail mechanism for memory writes specifically (DEBT-004) — the one confirmed instance of "silence is not a valid state transition" being upheld through two different channels rather than one canonical channel, a duplication-of-authority finding, not a silence finding.

**Workflow durability: confirmed absent, not merely "structurally present."** This is worth stating in the governing task's own terms directly: `WorkflowRuntime` **exists**, is **specified**, is **implemented** for DAG traversal — but is not **durable**, not **recoverable** across a process restart, and this gap is not newly discovered; it has been documented, unchanged, since July 16, independently reconfirmed via three separate reads this session (July 16 report, PFA, and this session's own `KNOWN_ISSUES.md` DEBT-003 entry).

**Replay:** `EventStream.get_checkpoint()` exists as a primitive but, per the above, has no consumer. Deterministic reconstruction of "what was asked, what state existed, what was decided" is confirmed possible for anything that *did* get event-logged (Law 2's own guarantee, holding for everything that flows through `EventStream`) — but a checkpoint/resume *cycle* specifically is unimplemented, which is a narrower and more concrete claim than "replay doesn't work."

---

# 13. Validation / Explainability / Determinism Gaps

**[FACT]** Mechanistic vs. interpretive explainability — the Pressure Test's own resolution (§6) is the correct bar, and this study applies it rather than the stronger, unachievable one: does the Kernel produce a faithful trace of the actual decision process? **Yes, for everything event-logged** — `EventStream` entries carry causal fields; the K4.2 cognitive path's `caused_by`/`derived_from` distinction (ADR-K4.2-H-09) gives exactly the "why did this plan version exist" trace the governing task asks for. **Not yet, for the C-MoE boundary** — because nothing exists there to explain (§5).

**Determinism, precisely scoped per the Pressure Test's own split:** *execution* determinism (same compiled plan + same inputs → same scheduling decisions) — confirmed via `ExecutionRuntime`'s deterministic exception-boundary behavior and `WorkflowRuntime`'s confirmed-clean DAG traversal. *Capability* determinism (governed evolution, versioned, event-logged) — the underlying mechanism (`ContentDomain`/`LearningCandidate`, confirmed non-executable evidence, not executable code — checked directly this session's reading of PFA §9) supports this, though DEBT-011 (K4.1-L reconciliation) remains an open, tracked, non-blocking item.

**Non-replayable inputs:** wall-clock time, randomness, model outputs — **[INFER]** the Pressure Test's proposed amendment (capture at consumption time, replay reproduces the *decision*, not the *input*) is not yet Constitutional text, but this study found no evidence of a code path that violates its spirit — every exception/failure path already resolves to a captured `WorkerResult`, which is itself the "captured decision given that input" the amendment describes.

---

# 14. Task Mutation Analysis

**[FACT]** The Kernel today has **no primitive for this at all** — confirmed by the same identity-disconnection finding driving Blocker #1 (§5, §8): if `WorkflowNode`/`WorkflowDefinition` don't carry a stable identity linking back to the plan/goal that produced them, there is no anchor for "what changed" to be computed against in the first place. `core/cognitive/planner.py::plan()` takes exactly `(request, registry)` as input — no prior WorkGraph, no prior goal version, nothing to diff against (independently confirmed this session, and again by the companion C-MoE study's own §0 finding, reached the same way).

**[DECISION, this study]** Task mutation is **Kernel-required in its identity foundation, post-Kernel in its mechanism.** The Kernel does not need to implement goal-diffing, impact analysis, or selective recomputation — those are exactly the kind of cognitive-orchestration work that belongs to C-MoE (per the governing task's own §46/§47 framing, which this study agrees with on the merits, not merely because instructed to). But the Kernel **does** need to provide the one thing every mutation-handling design (this study's own companion research included) depends on: **a stable identity that survives from Goal through Plan through WorkflowNode**, so that "what changed relative to what" is even askable. This is not new scope invented for this study — it is precisely PFA's Blocker #1, reframed through the task-mutation lens rather than the durability lens, and it is the same fix either way.

**What OCBrain currently knows, checked directly against the four-way disconnection finding:**

| Question | Current answer |
|---|---|
| What changed? | Unanswerable — no version exists on `Goal` today (confirmed; the companion C-MoE study's §11 independently found the same absence) |
| What remains valid? | Unanswerable — no dependency graph exists between plan steps and their outputs at the Kernel level |
| What can be preserved / must be redone / should be cancelled? | Unanswerable for the same reason |
| Which active executions can safely continue? | Partially answerable at the *process* level (a running `WorkflowRuntime.execute()` call can be observed), unanswerable at the *identity* level (nothing says which `operation_id` it belongs to) |

**Do not design C-MoE to solve this** (the governing task's explicit instruction, and this study agrees): the fix is the identity primitive, at the Kernel layer, not a cognitive-reasoning layer built on top of a still-missing foundation.

---

# 15. Contract Stability Analysis

**[FACT]** Versioning exists and is taken seriously *within* the K4.2 cognitive path — `CapabilityMatch`/`CapabilityDiscoveryResult` frozen at H1 (ADR-K4.2-H-04), `OperationRecoveryBudget` unified (ADR-K4.2-H-05), `ExecutionPlan.lifecycle_state` and `caused_by` both real, versioned-in-spirit fields. **[FACT]** This same discipline does not yet exist as a *general Kernel mechanism* — there is no Constitutional Law of Contract Stability (§6), no formal deprecation-window process for a breaking capability-contract change outside the specific H1/H2 conventions this project has been applying ad hoc but consistently.

**The one live case where this matters concretely today:** embedded ADR-001 vs. `WorkerContext` (§6, §7) is, precisely, a contract-stability failure — a contract (which object workers take) was declared changed, and the declaration was never actually enforced or walked back, six-plus weeks later. **[INFER]** This is direct, concrete evidence for adopting the Pressure Test's proposed Law of Contract Stability, independent of this study's own recommendation on the merits — the exact failure mode that law exists to prevent has already happened once, quietly, in this repository.

---

# 16. Legacy / Architectural Debt

| Problem | Canonical Path | Legacy Path | Consumers | Removal Plan |
|---|---|---|---|---|
| `WorkerContext`/`ExecutionContext` | `ExecutionContext` (per ADR-001) | `WorkerContext` (actually universal) | All seven worker classes | **Cannot be removed until Blocker #2 (§6) is decided** — removal *is* one of the two viable resolutions, not a separable cleanup task |
| `EventStream`/`KnowledgeEvent` | `EventStream` | `KnowledgeEvent` (L4 archive audit trail) | Memory write path | DEBT-004, non-blocking; fold `KnowledgeEvent` emission into `EventStream` once scheduled |
| Duplicate Watchdog/ProgressMonitor implementations | Neither is canonical — both exist in parallel | `core/runtime/watchdog.py`+`progress.py` (graph-aware) vs. `execution_watchdog.py`+`progress_monitor.py` (standalone) | `WorkflowRuntime` vs. `model_router.py` respectively | DEBT-016; unify to one, post-freeze |
| K2.2 legacy `PlannerWorker` path vs. K4.2 | K4.2 (now default, `use_k42_frontend: true`) | K2.2 `PlannerWorker`, byte-for-byte unchanged | Feature-flag fallback only | **Keep intentionally** — documented, deliberate, reversible dual-path architecture, not accidental legacy (re-confirmed this session, `CURRENT_STATE.md`) |
| `OCBRAIN_FUTURE_ARCHITECTURE.md` duplicated (root + `docs/archive/research/`) | Either — genuinely byte-identical | — | Documentation only | Convert root copy to redirect stub, matching the existing `PROJECT_INSTRUCTIONS.md` pattern |
| Two misnamed `..._K4_3_IMPLEMENTATION_TRANSITION.md` files | N/A — historical planning doc, not a live contract | — | None (documentation only) | **Already resolved this session's predecessor** — renamed to `..._K4_2_...`, with an explanatory note |

**No transitional adapters, obsolete worker routes, or deprecated state models beyond the above were found** — consistent with PFA's own Aug 22 sweep, which this study's more limited fresh grep (§9) did not contradict.

---

# 17. Test Reality

**[FACT, independently re-run this session, not cited from any prior report]**

```
Full suite, fresh clone: 1,331 passed / 34 failed
```

Every one of the 34 failures traced individually (`--tb=line` on all 34, not merely the aggregate count) to the same root cause: this sandbox cannot reach `huggingface.co` to download `all-MiniLM-L6-v2`, used by `core/classifier_v3.py`'s semantic classification path. **Zero regressions** from either the Aug 27 watchdog-baseline merge or the Aug 27–28 K4.2-completion upload — a materially different and more rigorous check than the K4.2-completion report's own claim, which verified only a 509-test subset, not the full suite.

| Kernel Property | Unit | Integration | E2E | Failure | Recovery | Security | Replay | Missing |
|---|---|---|---|---|---|---|---|---|
| Execution Runtime | Yes | Yes | Yes | Yes (exception→`WorkerResult`) | N/A (ephemeral) | Not independently audited this session | N/A | — |
| Workflow Runtime | Yes | Yes | Yes | Partial | **No — nothing to recover, DEBT-003** | Not audited | **No — no checkpoint consumer** | Checkpoint/resume test coverage |
| Capability Runtime | Yes | Yes | Yes (D3's 9-test acceptance suite, per PFA) | Yes (fallback) | Yes (fallback) | Not audited | N/A | — |
| Governance | Yes | Yes (K3.5's own validation table, "by construction" reasoning, not all live-executed) | Not independently confirmed this session | Yes | N/A | Partial (see §11) | N/A | Live-executed governance-rejection test for `MemoryGovernor` beyond "by construction" |
| K4.2 Cognitive Front-End | Yes (51 new K4.2-completion tests, re-run and confirmed this session) | Yes | Yes | Yes | Yes (`caused_by`/impasse loop) | Not audited | Partial (`caused_by` chain, no dedicated replay test found) | — |
| Event Backbone | **No dedicated coverage — DEBT-008** | — | — | — | — | — | — | Direct `EventStream` test suite |

**Distinguishing environment failures from software failures, as the governing task requires:** all 34 current failures are environment-only (network egress), confirmed by direct per-failure traceback inspection this session, not inferred from a stable failure count alone.

---

# 18. Research Synthesis

## Prior OCBrain research, reconciled rather than restated

**[STUDY]** Five prior freeze/completion audits exist and were read in full this session: `ARCHITECTURE_CONSOLIDATION_AND_K3_READINESS_REPORT.md` (Jul 14), `KERNEL_V1_0_FINAL_ARCHITECTURE_AUDIT_REVISION.md` (Jul 14, same-day revision), `FINAL_K3_READINESS_AUDIT.md` (Jul 16), `K3.5 — Kernel Hardening Report (Final).md` (Jul), and `KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md` (Aug 22–23, hereafter PFA). Each did its own fresh-clone, evidence-first verification; none was trusted at face value by this study without a cross-check where a cross-check was feasible (§1, §17). Their combined trajectory is itself informative: Jul 14 found K2.2/K2.4 incomplete and a Constitution law-count crisis; Jul 16 found K2.1–K2.4 all genuinely complete with two narrow new gaps (checkpoint/resume, duplicated event authority); K3.5 (Jul) closed the governance gaps and issued an "UNCONDITIONAL KERNEL v1.0 CERTIFICATION" claim this study does **not** accept uncritically (§1) — DEBT-002 (AgentGovernor dormancy), confirmed still open today, was outside K3.5's stated scope and was never claimed resolved by K3.5 itself, so this is not a case of K3.5's own claim being false, but it is a case of "unconditional" doing more work than the two conditions K3.5 actually closed can support. PFA (Aug 22–23) is this project's most rigorous prior instance of exactly this study's own question, and its two-item blocking set (§1) is the anchor this entire document reconciles against, re-verified rather than re-derived.

**[STUDY]** RS (Reliability/Durable Execution) and CS (C-MoE Adaptive Cognitive Scaling) are both genuinely excellent, unpublished internal research — sixteen combined "Critical Pre-Freeze" items, **zero of which this study or PFA found to be a live blocker** (they are contracts to ratify before the *next* phase, not before this freeze). WE (Watchdog Evolution Research) independently and rigorously verified three external durability papers (Temporal, LangGraph, Restate as production precedent; AgentRewind arXiv:2608.14380 and AgentTether arXiv:2607.06273 independently re-confirmed genuine by this study's own predecessor session's live web search) — directly relevant to closing DEBT-003.

## Fresh external research, this session

| System | Mechanism | Kernel-relevant finding |
|---|---|---|
| **tinyhumansai/openhuman** (agent orchestrator, "checkpointed graphs," Rust) | `SqlRunLedgerCheckpointer`: a durable row is the source of truth controllers/resume read; explicit adapter-with-sunset-condition pattern kept "until existing checkpoint rows are migrated... and schema ownership is settled" | Independent, real-world validation that OCBrain's own `WorkerContext`/`ExecutionContext` shim pattern (§6) and its proposed checkpoint/resume fix (DEBT-003) are both industry-standard, not improvised — and that a compatibility shim with an explicit, unmet sunset condition is a recognized, named risk elsewhere too |
| **tinyhumansai/openhuman**, GitHub issue #4249 | Explicit internal argument for adopting "LangGraph-style state machine" specifically because "debugging agent behavior is hard without explicit state transitions to trace" | Directly corroborates RS/CS's own Work Unit dual-axis state machine proposal (§5, PFA §5) — an independent team reaching the same conclusion for the same reason |
| **affaan-m/ECC** (Claude Code agent-harness augmentation) | Explicit, textbook Bounded-Autonomy guardrail: "Autonomous operation must be explicitly requested and scoped... Do not create schedules, dispatch remote agents, write persistent memory... unless the user has approved that capability" | Direct, deployed validation of OCBrain's own Law of Bounded Autonomy — this is what the law looks like enforced in a comparable, shipping system |
| **affaan-m/ECC** | Opt-in, capability-contracted memory writes (`ECC_MEMORY_ALLOW_USER_SCOPE=1`, a documented "capability contract") | Validates OCBrain's own K3.5 `MemoryGovernor` wiring as the right shape of fix, not merely *a* fix |
| **Google ADK** (Agent Development Kit) | "Orchestrates non-deterministic LLM agents using deterministic structural routers" | Directly validates this study's — and the companion C-MoE study's — insistence that an LLM's output must be a scored *signal*, never the routing *decision* itself (§13) |
| **"In-Context Prompting Obsoletes Agent Orchestration for Procedural Tasks"** (arXiv:2604.27891) | Controlled study: for narrow procedural tasks, putting the whole procedure in-context and letting the model self-orchestrate outscored an external orchestrator (LangGraph) using the *same* model | **A genuine calibrating caution, not merely supporting evidence**: this is real evidence that heavy Kernel-mediated orchestration is not free, and its value is task-dependent. This directly supports the governing task's own framing — "the smallest complete and trustworthy Kernel," not the most elaborate one — rather than being a reason to add more orchestration machinery. |
| **RouterEval** (Huang et al., EMNLP Findings 2025) | A capable router over a large candidate pool can exceed the best single candidate — a "model-level scaling up" effect | Supports investing in routing-mechanism quality (relevant once C-MoE exists) over merely accumulating more capabilities |

---

# 19. Research-to-Kernel Gap Matrix

| Primitive | Research Evidence | OCBrain Current State | Gap | Kernel Required? |
|---|---|---|---|---|
| Execution isolation | affaan-m/ECC (scoped subagents), openhuman (worktree/RPC isolation) | Partial — clean at the Worker/Governance boundary; singleton pattern needs call-site verification (§9) | Open verification item | **Kernel-required, pending verification** |
| Durable execution / checkpoint-resume | openhuman (`SqlRunLedgerCheckpointer`), Temporal/LangGraph/Restate (via WE) | `EventStream.create_checkpoint()` exists, unconsumed | Confirmed, unresolved | **Kernel-required (Blocker-adjacent, §8)** |
| Cancellation | openhuman ("async sub-agents... steered while running and awaited cleanly") | Confirmed at `CancellationToken`/`ExecutionContext` level (K2.1) | None found | Already satisfied |
| Stable cross-boundary identity | Medulla's worker/session distinction; RS's Scope proposal | `operation_id` exists for cognitive path only, confirmed disconnected past `compile()` | **The central finding of this study** | **Kernel-required (Blocker #1, §5)** |
| Capability contracts + lifecycle | Composio, Datalayer/Open Agent Skills (prior OCBrain research, reconciled not re-derived), ECC's capability-contract pattern | `CapabilityMatch`/`CapabilityDiscoveryResult` frozen H1; `model_router.py`'s bootstrap/shadow/native lifecycle real | None found beyond the (correctly deferred) breadth question — only 1 of 10 named types has real adapters | Already satisfied for what exists |
| Deterministic routing over non-deterministic components | Google ADK | C-MoE doesn't exist yet to test this against; the *principle* is already correctly applied elsewhere (Worker exception boundary) | N/A — principle present, no C-MoE to apply it to yet | Post-Kernel, principle already Kernel-compatible |
| Contract versioning/deprecation discipline | openhuman's adapter-sunset pattern; Pressure Test's proposed Law | Ad hoc, followed within K4.2 (H1/H2 conventions); no general Kernel mechanism; one live failure case (ADR-001, §15) | Confirmed gap, with a live consequence | **Required, at minimum as a ratified process, not necessarily new code** |
| Failure containment / bounded blast radius | ECC's explicit autonomy guardrails; Pressure Test's proposed Law | Practiced (exception→`WorkerResult`) but not Constitutional | Practice exists, principle unratified | Not blocking — practice already present |
| Task/goal mutation handling | Companion C-MoE study's own findings; τ²-bench's dual-control formalization (prior research) | No identity foundation exists to build it on (§14) | Confirmed — but the *fix* is identity, not a mutation engine | **Kernel-required only at the identity layer** |

---

# 20. Kernel Completion Contract

**[DECISION, this study]** Derived from all fourteen sources listed in §2/§18, retaining only domains this study found actual evidence justifies — several of the governing task's candidate domains (Verification, full Contract Stability tooling, distributed considerations) are explicitly **not** included below, because nothing in this repository's evidence shows the Kernel is currently incoherent without them; they are named in §23 as post-Kernel instead.

**A Kernel freeze may occur once all of the following hold:**

### Cognition
- ✅ Intent → Goal → Constraints → Capability Discovery → Planning → Compilation → Validation: end-to-end, governed, tested (§3).

### Execution
- ✅ Identity, lifecycle, isolation (pending §9's verification item), cancellation, budgets, watchdog: present.
- ⬜ **Checkpoint/resume**: absent (§8, §12).
- ⬜ **A single, unified progress/watchdog implementation**, not two reconciled-but-separate ones (§9, DEBT-016).

### State
- ✅ Resources have lifecycle management (`ResourceLifecycle`/`ResourceManager`); ⬜ **a formal `Resource` Protocol should be confirmed to exist and be uniformly used** — not confirmed present at the expected location this session (§8).
- ✅ Memory ownership, governance (K3.5), and provenance fields exist.

### Durability
- ⬜ **Checkpoint/resume, consuming the already-existing `EventStream` primitive** — the single largest concrete gap this study found with no open decision blocking it, only implementation.
- ✅ Event sourcing itself, replay of anything logged.

### Governance
- ✅ Real enforcement at every production write path checked, with two disclosed, transitively-covered exceptions.
- ⬜ `AgentGovernor` delegation activation — **explicitly not required for freeze** (dormant-but-fail-closed is an accepted interim state, RS-6).

### Determinism / Explainability
- ✅ Both, at the precision level the Pressure Test's own resolution specifies (execution determinism, mechanistic explainability) — confirmed, not merely asserted.

### Contract Stability
- ⬜ **The ADR-001 vs. `WorkerContext` conflict must be resolved, one way or the other** (§6, §15) — this is not "adopt a new Law," it is "stop having one live contradiction between a frozen document and the code everyone actually runs."

### Identity
- ⬜ **The Scope/identity decision (PFA Blocker #1)** — the single highest-leverage unresolved item in this entire study, because task mutation (§14), durable execution (§12), and C-MoE (§24) all depend on it existing before their own designs can be implemented rather than merely proposed.

### Extension Boundary
- ✅ Adapter/Capability Protocol pattern, confirmed stable and replaceable at every layer checked; the one place it is genuinely absent (the C-MoE boundary) is absent *correctly*, by design (§5).

**Explicitly excluded from this contract, with reasons:** a ratified Law of Contract Stability or Failure Containment (§6 — the *practices* are present; the *Constitutional status* is a separate, non-blocking decision this study does not force into the freeze gate); full Verification subsystem (does not exist, nothing currently depends on it existing); distributed/multi-node concerns (no evidence anything in this codebase needs them yet); a resolution to the Constitution's own Draft status (§6 — named as worth an explicit decision, but this study found no evidence that "Draft" as a status has caused any actual incoherence in five audits' worth of evidence, so it does not belong in the same gate as items with a demonstrated live consequence).

---

# 21. Dependency-Aware Implementation Roadmap

```
                    [Decision: Scope/Identity]  [Decision: ADR-001/WorkerContext]
                              │                            │
                              ▼                            ▼
                    Step 1: WorkflowNode/          Step 2: Retire or ratify
                    WorkflowDefinition gain              WorkerContext
                    an identity field                     │
                              │                            │
                              ▼                            │
                    Step 3: Checkpoint/resume  ◄───────────┘
                    (consumes EventStream.
                     create_checkpoint/get_checkpoint,
                     keyed to the new identity field)
                              │
                    ┌─────────┼──────────────┐
                    ▼         ▼              ▼
              Step 4:    Step 5:        Step 6:
              Unify      Retrieval-      Formal
              Watchdog/  stack live-     Resource
              Progress   path re-        Protocol
              (DEBT-016) verification    confirmation
                    │         │              │
                    └─────────┴──────────────┘
                              │
                              ▼
                    Step 7: Ratify RS's 9 + CS's 7
                    Critical Pre-Freeze items via
                    two combined ADRs (per PFA's
                    own recommendation)
                              │
                              ▼
                    Step 8: KERNEL v1.0 FREEZE
                              │
                              ▼
                    Post-Kernel: C-MoE, Skills,
                    Resources (§23-24)
```

| Step | Objective | Depends on | Files/modules | Contracts | Tests | Exit criteria |
|---|---|---|---|---|---|---|
| 1 | Decide and implement Scope/identity linkage | Moncif's decision only | `core/workflow/definition.py` (new field), `core/cognitive/compiler.py` (thread it through) | New — a single additive field | A test asserting `WorkflowNode.operation_id` (or equivalent) matches the `operation_id` that produced its parent plan | Field exists, populated, non-null for every compiled node |
| 2 | Decide ADR-001's resolution; if option (b), migrate | Moncif's decision only | `core/workers/base.py` + six worker classes, if migrating | ADR-001's text, updated either way | Existing worker test suite must still pass unchanged | ADR_INDEX.md reflects a decision, dated after this study |
| 3 | Implement checkpoint/resume | Step 1 (needs an identity to key against) | `core/workflow/runtime.py` | New — a `WorkflowCheckpoint` contract, minimal | Kill-mid-workflow, restart, confirm resume without duplicate side effects | A process-restart test passes |
| 4 | Unify Watchdog/ProgressMonitor | None (independent of 1–3) | `core/runtime/watchdog.py`+`progress.py` vs. `execution_watchdog.py`+`progress_monitor.py` | None broken — additive consolidation | Existing tests for both, post-merge | One canonical implementation, both call sites migrated |
| 5 | Re-verify retrieval-stack live path | None | `core/memory/assembly.py` | None — verification only, or a real fix if still legacy | N/A until findings known | A direct, dated answer exists — this study explicitly could not provide one |
| 6 | Confirm/complete formal `Resource` Protocol | None | `core/capabilities/resource.py` | Possibly a new Protocol, additive | Existing resource tests | Answered with the same rigor as every other item in §8 |
| 7 | Ratify RS/CS's 16 items via two ADRs | None (can run in parallel with 1–6) | `docs/architecture/decisions/` | 16 contracts, all already specified | None — documentation only | Two new ADRs exist, dated |
| 8 | **Freeze** | 1, 2, 3 minimum; 4–7 strongly recommended not to defer past freeze given their age | `KERNEL_ARCHITECTURE_v1.0.md` | Freeze declaration itself | Full suite green (already true, §17) | §22's gate, fully checked |

---

# 22. Kernel Freeze Gate

**Objective pass/fail, per the governing task's explicit requirement for one:**

| Criterion | Pass condition | Current status |
|---|---|---|
| Architectural coherence | No unresolved contradiction between a frozen document and running code | **FAIL** — ADR-001/`WorkerContext` (§6) |
| Identity | Every execution-relevant object traceable to a stable identity | **FAIL** — `WorkflowNode`/`operation_id` disconnection (§5) |
| Durability | A killed-and-restarted workflow resumes without duplicate side effects | **FAIL** — DEBT-003 |
| Governance | Every production mutation path evaluated or transitively covered | **PASS** (§11) |
| Determinism | Execution determinism holds; non-replayable inputs captured at consumption | **PASS** (§13) |
| Explainability | Mechanistic trace exists for every event-logged decision | **PASS**, scoped correctly (§13) |
| No duplicated authority | Exactly one canonical implementation per responsibility | **FAIL, twice** — `EventStream`/`KnowledgeEvent` (§7) and Watchdog/ProgressMonitor (§9) |
| Testing | Full suite green, zero non-environment failures | **PASS** — independently re-verified this session (§17) |
| Cleanup | No unresolved compatibility shim with an expired sunset condition | **FAIL** — `WorkerContext` shim's own "will be removed after K2.4" condition expired in July |

**Verdict: NOT_FREEZE_READY.** Four failing criteria, all narrow, all fully diagnosed, three requiring a decision rather than research (identity, ADR-001, and — arguably — how urgently to treat the duplicated-authority pattern once named as a pattern rather than two coincidences) and one requiring bounded implementation with no open design question (checkpoint/resume). This is a materially smaller gap than "the Kernel is not ready" might suggest on first reading — it is the same two-decision closure set PFA found a week ago, confirmed unchanged, plus this study's own sharper naming of the duplicated-authority pattern as exactly that: a pattern, appearing twice, not two unrelated facts.

---

# 23. Post-Kernel Architecture

```
                    OCBrain Kernel (frozen, once §22 passes)
                              │
                      stable contracts:
                      identity, capability/adapter
                      protocol, governance,
                      event sourcing, memory
                              │
                 stable extension boundary:
                 CapabilityRegistry, AdapterRuntime,
                 WorkflowNode (now identity-bearing)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
      C-MoE                Skills             Resources
      (§24)          resource→skill      external tool/API
      routing,        acquisition,        acquisition,
      composition,     versioning,        provenance,
      WorkGraph        composition        governance
```

**Explicitly deferred, with reasons, per §57 of the governing task:**

| Feature | Why post-Kernel | Kernel dependency | Required extension point |
|---|---|---|---|
| C-MoE (full adaptive-scaling system) | CS's own explicit sequencing; zero code exists; the dispatch bridge it needs is a hardcoded single-value bypass today | Identity (§21 Step 1), unified watchdog signal (§21 Step 4) | `WorkflowNode.worker_type` generalized past its current hardcoded state |
| External resource acquisition / resource→skill | Not evaluated for necessity by any current Kernel gap | `CapabilityRegistry`'s existing metadata contract | A registration path for dynamically-discovered capabilities |
| Advanced skill evolution | Same | Governed learning pipeline (`ContentDomain`/`LearningCandidate`, already exists) | None new — the existing evidence-not-executable-logic contract already generalizes |
| Multi-node OCBrain | No evidence this codebase has any current need | Identity model, once resolved, would need to become distributed-aware — explicitly out of scope now | N/A |
| Advanced Studio features | SSE/snapshot plumbing already exists (Aug 27 merge) and is explicitly Studio-facing | The `routing.decision`-style event shape C-MoE would eventually emit | Already-existing event stream, additive only |
| Speculative autonomy mechanisms | No evidence requested or needed | Bounded Autonomy envelope pattern (Pressure Test §4, unadopted but reasoned) | Would require the Constitutional amendment first |

---

# 24. C-MoE Dependency Contract

**Not an implementation. A specification of what the Kernel must provide before C-MoE can be built without restructuring the Kernel underneath it — exactly the governing task's own framing, and this study does not exceed it.**

| C-MoE need | Kernel primitive it depends on | Current status |
|---|---|---|
| Route among more than one expert for a given step | A generalized `WorkflowNode` → worker dispatch path | **Missing — hardcoded to exactly one `capability_type`, confirmed this session and independently by PFA** |
| Know what has already happened to a task | Stable identity surviving from Goal through Plan through WorkflowNode | **Missing — PFA Blocker #1** |
| Resume a long-running routing/execution loop after a crash | Checkpoint/resume | **Missing — DEBT-003** |
| Trust a single progress/health signal, not two disagreeing ones | Unified Watchdog/ProgressMonitor | **Missing — DEBT-016** |
| Consume expert health/maturity without inventing a new lifecycle | `model_router.py`'s bootstrap→shadow→native pattern, generalized | **Present, at the model layer only — a real, reusable pattern, not yet generalized to arbitrary experts** |
| Emit structured, governed routing decisions | Existing `EventStream` + governance evaluation pattern | **Present, additive only — no new Kernel mechanism required, only a new event shape and a new Governor rule** |
| Never bypass Governance for a routing decision | `GovernanceKernel.evaluate_action()`, extended with C-MoE-specific rules | **Present as a pattern; would need new rules, not a new Governor** |

**This is not new scope discovery — it is a direct restatement of §8/§20's Kernel gaps, viewed through the one lens the governing task specifically asks for.** Nothing in this table requires research beyond what §5–20 already established.

---

# 25. Immediate Next Step

**Exactly one. Not implemented here, per the governing task's explicit instruction.**

> **Bring PFA's Blocker #1 (Scope/identity) and Blocker #2 (ADR-001/`WorkerContext`) to Moncif as two explicit, already-fully-specified decisions, unchanged in substance from how PFA framed them a week ago, with this study's confirmation that neither has moved and that both remain the sole reason Kernel v1.0 is not frozen.**

Everything else in this document — the sixteen RS/CS ratification items, the retrieval-stack re-verification, the `Resource` Protocol confirmation, the duplicated-authority pattern's naming — is real, tracked, and correctly sequenced to follow those two decisions, not to precede or substitute for them.

---

## A Closing Note on This Study's Own Limits

Per the governing task's Rule 14 (do not hide uncertainty), three items in this document are explicitly **not** independently re-verified this session and are named as such rather than silently carried forward as if they were: the retrieval-stack live-path status (§8, §10), the formal `Resource` Protocol's exact current shape (§8, §20), and whether the five confirmed module-level singletons (§9) are reachable ambient state or benign test/script accessors. A sixth session picking this document up should treat those three specifically as the highest-value next reads — not because they are expected to change this study's verdict, but because this study's own discipline (the same discipline PFA, K3.5, and the July audits all practiced) requires saying plainly what wasn't checked, not only what was.
