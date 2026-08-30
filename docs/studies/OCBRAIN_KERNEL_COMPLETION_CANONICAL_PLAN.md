# OCBrain — Canonical Kernel Completion Reconciliation & Implementation Plan

**Status:** Research, audit, and reconciliation complete. **No code modified. No milestone implemented. No milestone invented.**
**Date:** August 29, 2026
**Relationship to prior work:** This document is the canonical one this project now has for the Kernel-completion question. It **supersedes** `docs/studies/OCBRAIN_KERNEL_COMPLETION_STUDY.md` (yesterday's predecessor) rather than duplicating it — every finding there was re-checked, none was overturned, and this document reuses that evidence explicitly rather than re-deriving it, per this task's own Rule 10 ("preserve closed decisions; do not reopen without new evidence"). What this document adds, and what the predecessor did not have, is a **git-verified reconstruction of the original K4.1–K4.7 roadmap** and an honest accounting of what packet-driven development preserved, changed, or lost relative to it — the genuinely new contribution here.

---

# 1. Executive Verdict

**Is the Kernel complete today? No. Confidence: High.** Unchanged from yesterday's finding, and this document did not find new evidence to revise it: two narrow, fully-diagnosed decisions block freeze (§15, §31, §35), both open for exactly one week with zero movement, re-confirmed unchanged a second time this session.

**What this document adds to that verdict:** the historical reconstruction below (§3–5) found something the predecessor study didn't look for and therefore didn't find — a **real, git-documented original architecture** (`docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §19, a seven-milestone roadmap, K4.1 through K4.7) whose **milestone labels were never used in a single commit**, yet whose **safety-relevant boundaries were, on inspection, substantially preserved** — the governance gate the original K4.3 wanted at plan compilation exists in code today, cited back to its origin section, even though no commit was ever named "K4.3." This is a better and more specific finding than either "nothing was lost" or "everything was lost": **the labels were lost; most of the engineering intent behind them was not.** Where it genuinely was not preserved, this document says so plainly (§5).

---

# 2. Authority and Evidence Hierarchy

Unchanged from the predecessor study, restated for this document's own standing: Constitution (highest) → `KERNEL_ARCHITECTURE_v1.0.md` → `PROJECT_INSTRUCTIONS.md` → accepted ADRs → `CURRENT_STATE.md`/`IMPLEMENTATION_ROADMAP.md` → prior reports/studies (evidence, not authority in their own right). **One addition specific to this document's task:** where the *original* architectural intent is being reconstructed (§3–5), `OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` and git history are the primary sources, and they are treated as authoritative for **what was intended**, while `IMPLEMENTATION_ROADMAP.md`/current code remain authoritative for **what actually exists** — the whole point of §3–5 is that these two authorities disagree on labels while agreeing, more often than not, on substance.

**On "K4.3 = C-MoE," restated precisely because this task's own Rule 2 requires it:** that premise remains wrong, exactly as the predecessor study found. It is not, however, meaningless to ask "what did K4.3 originally mean" — it meant something real and specific (§3), it was simply never C-MoE, and it was never implemented under that name.

---

# 3. Original K4.1–K4.7 Reconstruction

**[FACT, git-verified this session]** `docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §19 ("Implementation Roadmap") contains a complete, explicit, seven-milestone plan, each with a stated testable exit criterion:

| Milestone | Original scope | Testable exit criterion (as written) |
|---|---|---|
| **K4.1** | Intent + Goal primitives | Given a query, produces a well-formed Goal. No Kernel interaction yet. |
| **K4.2** | ExecutionPlan + Planner, **decomposition only, no compilation yet** | Given a Goal, produces a well-formed ExecutionPlan with confidence + justification. Still no Kernel interaction. |
| **K4.3** | **Plan Compiler + Governance Gate** | A compiled `WorkflowDefinition` round-trips through the existing, unmodified `WorkflowRuntime.execute()`. First milestone with real Kernel interaction, deliberately scoped narrow. |
| **K4.4** | ReflectionWorker + EvaluatorWorker, **read-only, no memory writes yet** | Given a completed/failed workflow's event trail, produce a well-formed record. Writes deliberately deferred to K4.5 "so this milestone can't regress memory behavior." |
| **K4.5** | Memory Integration | Wire Reflection/Evaluation's promotion decisions to `UnifiedMemory.write()`. |
| **K4.6** | SupervisorWorker | Retry-via-reinvocation, escalation, ships last because "it has nothing to supervise until K4.1–4.5 exist." |
| **K4.7** | Full pipeline integration test | End-to-end Intent→Response against the real Kernel; exit criterion is the existing full test suite still passing unchanged, plus new coverage added alongside it. |

The same document also names six planned ADRs that were meant to accompany this roadmap — **[FACT, verified this session]** none of the six (`ADR-K4-01` through `ADR-K4-06`) exist in `docs/architecture/decisions/ADR_INDEX.md` or anywhere else in the repository. The most consequential of the six, `ADR-K4-04 — Governance Gate Placement (Plan Compilation)`, records *why* the gate belongs at compilation rather than at planning or execution — a real, important architectural decision whose reasoning exists only inside this one architecture document today, not in the ADR system that was supposed to formalize it.

---

# 4. K4 Recovery Matrix

**[FACT, reconstructed from git history this session — every "Current Code" and "Packet" cell below is a direct commit reference, not an inference]**

| Original Milestone | Original Responsibility | Packet(s)/Commits | Current Code | Boundary Preserved? | Evidence |
|---|---|---|---|---|---|
| **K4.1** | Intent + Goal primitives | Pre-packet direct commits: `ec097a7`, `310e4c9`, `05fa8d0`, `096b728`, `bf81429` (all literally titled "K4.2.1: ...") | `core/cognitive/intent.py` | **Label lost, substance preserved** — the work is real, tested (36 tests), and functionally matches K4.1's scope exactly; it was simply never called "K4.1" | Git log, direct read |
| **K4.2** | ExecutionPlan + Planner, decomposition only | Packet 01–03 (`685b83f`, `be07a97`, `1e903c1` — K4.2.3/4/5) | `core/cognitive/planner.py` | **Preserved, both label and substance** — `planner.py` line 1004 explicitly states its output is "not yet compiled into a runnable WorkflowDefinition"; `compiler.py` is a separate module Planner never imports | Direct grep this session: zero references to `compiler`/`WorkflowDefinition`/`compile(` in `planner.py` outside of the one explanatory comment citing `compiler.py` by name as a *different* module |
| **K4.3** | **Plan Compiler + Governance Gate** | Packet 06 (`d48156b`, `9fced8b`) — never labeled "K4.3" in any commit | `core/cognitive/compiler.py` | **Label lost entirely; substance preserved precisely** — `GovernanceAction(action_type="plan_compile")` exists, gates compilation exactly as designed; `cognitive.plan_compiled`/`cognitive.plan_rejected` events exist and fire; code comments explicitly cite "K4 §12" and "K4 §15" as their origin | Direct grep this session: `compiler.py` lines 9–10, 27, 280, 308, 343, 363, 399 |
| **K4.4** | ReflectionWorker + EvaluatorWorker, read-only | Packet 07 (`11df3e1`) | `core/workers/reflection.py`, `evaluator.py` | **Label lost; sequencing merged with K4.5, not simply "preserved" or "lost"** — see §5 | Direct grep this session |
| **K4.5** | Memory Integration (deliberately *after* K4.4) | **Same packet as K4.4** (`11df3e1`), not a separate one | Same files | **Temporal separation not preserved as designed — see §5 for why this did not turn out to matter** | Direct grep this session: both workers call `self._memory.write()` directly within the same packet that also builds the read-only reflection/evaluation logic |
| **K4.6** | SupervisorWorker | Packet 08 (`d4b710d`, `b1d2e0c`) — never labeled "K4.6" in any commit | `core/workers/supervisor.py` | **Label lost, substance preserved** — built after Reflection/Evaluation/Memory existed, matching the original sequencing rationale ("nothing to supervise until K4.1–4.5 exist") even without the label | Git log ordering: Packet 08 postdates Packet 07 |
| **K4.7** | Full pipeline integration test | Packet 09 (`242931c`) — "Integration: Full Cognitive Pipeline" | Full test suite | **Label lost, substance preserved** — commit message matches the original exit criterion's intent almost verbatim | Git log |
| *(not in original plan)* | User Cognitive Model | Packet 05 (`5f30b9c`, K4.2.7) | `core/cognitive/user_model.py` | **New scope, added during packetization, not present in the original 7-milestone plan at all** | Comparing §3's table against the packet list directly |

**Net finding:** of seven original milestones, **zero retained their original label** in any commit, but **five of seven (K4.1, K4.2, K4.3, K4.6, K4.7) preserved their architectural substance essentially intact** — a materially better outcome than "packet-driven development erased the original architecture." The two that did not cleanly preserve their original design (K4.4/K4.5's deliberate temporal separation) are examined in §5, and — as that section shows — the underlying *safety concern* those two were designed to protect turns out to have been satisfied anyway, by a different mechanism than the one originally planned.

---

# 5. Architectural Boundaries Lost or Blurred During Development

## Planner → Compiler: **Preserved cleanly, both label and substance are the wrong frame here — the substance is what mattered and it's intact**

The original reason for this boundary (per K4.2/K4.3's exit criteria): let the Planner's output be independently testable *before* anything touches the Kernel, and gate the first real Kernel interaction narrowly, at one well-defined point, "to keep the blast radius small if something about the seam doesn't hold up." **[FACT]** This purpose is still served today — `Planner.plan()` genuinely has zero Kernel-facing side effects, and `compiler.py` is the sole, well-defined point where a plan becomes Kernel-executable work, gated by governance. Nothing about this boundary needs restoring because nothing about it was actually lost — only its milestone number was.

## Compiler → Governance: **The gate exists; the ADR that was supposed to explain it does not**

**[FACT]** The gate itself (`action_type="plan_compile"`) is real, functioning, and correctly positioned per `ADR-K4-04`'s stated reasoning (mirroring the K3.5 "evaluate before mutation" precedent). What's missing is not the gate — it's the **decision record**. A future engineer reading `ADR_INDEX.md` today would have no way to discover that this gate's placement was a deliberate, reasoned choice (rather than an arbitrary one) unless they happen to read `OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §15 directly. **Does this loss still matter today?** Marginally, and specifically for future contract-stability discipline (§22): the next person who wants to move or duplicate this gate has no ratified ADR to check against, only a design document's prose. **Should it be restored?** Yes, cheaply — writing `ADR-K4-04` now, describing what was actually built rather than what was planned, costs nothing and closes a real documentation gap. **This is the one item in this section classified CLEANUP, not REQUIRED** (§51's taxonomy) — the engineering is sound; only its formal record is thin.

## Reflection/Evaluation → Memory: **Sequencing changed; the underlying safety concern was satisfied anyway**

This is the one boundary this study found genuinely restructured, and it deserves the most careful treatment because "restructured" is not automatically "regressed."

1. **What was the boundary?** K4.4 was explicitly designed to ship *before* K4.5, with zero memory writes, specifically "so this milestone can't regress memory behavior even if something in the record schema is wrong."
2. **Why did the original architecture separate it?** Risk containment through sequencing — validate the read-only logic first, add write capability only once that's proven, and only once the write path itself (`UnifiedMemory.write()`) is trustworthy.
3. **Did packet implementation preserve that purpose?** Not through the same mechanism. **[FACT]** Packet 07 built both the read-only reflection/evaluation logic *and* the `UnifiedMemory.write()` calls together, in one packet, not two sequential ones.
4. **Does the loss still matter today?** **[INFER, this study's own finding]** No, and here is the specific reason why, not merely an assertion that it's fine: `UnifiedMemory.write()` had *already* been made governance-checked by K3.5 (`GovernanceKernel.evaluate_action()` before any mutation) — and K3.5, per `IMPLEMENTATION_ROADMAP.md`'s own phase ordering, is part of the **Kernel Hardening Phase**, which precedes the **Cognitive Front-End Phase** (where Packet 07 lives) in the actual chronological build order. The original plan's *purpose* — don't let Reflection/Evaluation write to memory before the write path is trustworthy — was satisfied by a **different sequencing than the one originally designed**: instead of "K4.4 first with no writes, K4.5 second adding governed writes," what actually happened was "make `UnifiedMemory.write()` trustworthy first (K3.5, for unrelated reasons), then build K4.4 and K4.5's concerns together, safely, because the prerequisite was already met." The safety property held; the sequencing that was supposed to guarantee it was different from the plan.
5. **Should this be restored?** No — restoring the original two-packet sequencing now would mean *removing* working, governed memory-write capability from Reflection/Evaluation and re-adding it later, for no safety benefit, since the actual current risk (governed vs. ungoverned writes) is already closed. **This study classifies this item CLOSED, not OPEN** (§45).

## Learning → Memory: **Not restructured — governed from the same starting point as Reflection/Evaluation**

**[FACT]** `core/cognitive/learning.py` (governing `LearningCandidate` promotion, including the `plan_compile` action-type list seen at line 237 during this session's grep) was built alongside, not before, the governed `UnifiedMemory.write()` path — the same reasoning as the Reflection/Evaluation finding above applies here without needing separate treatment: Learning never had a window where it could write to memory *before* the write path was governed, because that window (pre-K3.5) predates Learning's own packet entirely.

---

# 6. Current Architecture

**[STUDY, reused from the predecessor study's §3, re-confirmed not re-traced]** The actual, current, end-to-end request path — Orchestrator.handle() (governed) → K4.2 cognitive path (default since Aug 27) or K2.2 legacy path (flagged off) → interpret_request() → constraint extraction → capability discovery → plan() → compile() (governed, `plan_compile` gate) → WorkflowRuntime.execute() → ExecutionRuntime.invoke() → Worker.execute(context: WorkerContext) → CapabilityExecutorWorker (hardcoded to one capability_type) → AdapterRuntime → model_router.py → UnifiedMemory (governed since K3.5) → EventStream + EventBus. Full edge-by-edge detail, including contract/authority/failure-semantics for each edge, is in the predecessor study's §3 and is not repeated verbatim here — nothing in this session's historical research (§3–5 above) found a reason to revise it.

**One addition this session's historical work makes to that picture:** the `compile()` step's governance gate (§5) is now understood not just as "a governance check exists here" but as **the deliberate, designed location of the Kernel's first real interaction point with cognitive output** — a distinction worth carrying forward into §9's Guarantee Matrix.

---

# 7. Kernel Definition

**[STUDY, unchanged from the predecessor study's §4]** OCBrain's Kernel is the smallest set of responsibilities that must be trusted, centralized, and governed for everything above it to remain coherent, safe, and explainable (Constitution Part I) — concretely, a governed request-to-execution pipeline (five named runtimes), an event-sourced state/memory substrate, a capability/adapter abstraction boundary, and a Constitution-enforced admission discipline. **This session's historical reconstruction adds one precision to this definition:** the Kernel's boundary was, from the start, deliberately drawn to *end* at the governance gate around plan compilation (K4.3's entire reason for existing, per ADR-K4-04) — everything downstream of that gate (execution, memory, events) is Kernel; everything upstream of it (intent interpretation, goal formation, planning) was explicitly designed to have "no Kernel interaction yet," per K4.1/K4.2's own stated exit criteria. This is a cleaner, more precisely-sourced statement of the Planner/C-MoE boundary question than either prior study (this session's predecessor, or the earlier C-MoE studies) was able to make, because it comes from the original architecture's own stated design intent, not from this study's inference.

---

# 8. Kernel Boundary Audit

**[STUDY, unchanged from the predecessor study's §7 — reused, not re-derived]** Full three-gate Admission Test results for every current Kernel component (GovernanceKernel, ExecutionRuntime, WorkflowRuntime, CapabilityRegistry, AdapterRuntime, UnifiedMemory, EventStream, EventBus, `model_router.py`, `WorkerContext`, `KnowledgeEvent`, feature flags) are unchanged and not repeated here — see the predecessor study §7 for the full table. **This session found no new component requiring reclassification.**

---

# 9. Kernel Guarantee Matrix

**[DECISION, new format for this document]** Per the governing task's explicit chain requirement (`guarantee → contract → implementation → enforcement → runtime evidence → tests`), with `UNPROVEN` where any link is missing:

| Guarantee | Contract | Implementation | Enforcement Point | Runtime Evidence | Test Evidence | Status |
|---|---|---|---|---|---|---|
| Every state mutation is governed | Mutation requires a `GovernanceKernel.evaluate_action()` decision | `GovernanceKernel.evaluate_action()` | Orchestrator entry, Worker boundary, `UnifiedMemory.write/update/delete` | Confirmed clean sweep, this session and predecessor (§11 below) | K3.5 validation table ("by construction," not fully live-executed — a real, disclosed gap, not hidden) | **PROVEN**, with one disclosed evidentiary caveat |
| Plan compilation cannot bypass governance | `action_type="plan_compile"` gate before any `WorkflowDefinition` is produced | `core/cognitive/compiler.py` | The gate itself | `cognitive.plan_compiled`/`cognitive.plan_rejected` events fire | Not independently re-run this session | **PROVEN** at the code level; **IMPLEMENTED/UNVERIFIED** at the live-test level |
| Execution identity survives from Goal to WorkflowNode | None exists | — | — | `WorkflowNode`/`WorkflowDefinition` carry no `operation_id` field | Direct grep, twice, one week apart | **MISSING** (PFA Blocker #1, unchanged) |
| WorkerContext is deprecated (ADR-001) | ADR-001's own text | — | — | All seven worker classes still take `WorkerContext` | Direct grep, twice | **CONTRADICTORY** (PFA Blocker #2, unchanged) |
| A killed workflow can resume without duplicate side effects | None exists | `EventStream.create_checkpoint()` exists, unconsumed | — | Zero call sites in `WorkflowRuntime` | DEBT-003, confirmed three separate sessions | **MISSING** |
| Reflection/Evaluation cannot write ungoverned memory | Implicit — satisfied via K3.5 preceding Packet 07 chronologically, not via K4.4/K4.5's originally-planned sequencing (§5) | `UnifiedMemory.write()`'s governance check | `MemoryGovernor` | Confirmed, both workers call the governed path | Not independently re-run this session | **PROVEN**, via a different mechanism than originally designed |
| Exactly one canonical progress/recovery signal exists | Implicit — "no duplicated authority" | — | — | Two implementations (`watchdog.py`+`progress.py` vs. `execution_watchdog.py`+`progress_monitor.py`), reconciled but not unified | DEBT-016, confirmed | **CONTRADICTORY** |

---

# 10. Negative Requirements

**[DECISION]** What the Kernel must never allow, checked against actual code where checkable this session, per the governing task's named list:

| Prohibition | Status | Evidence |
|---|---|---|
| LLM output → direct execution | **Holds** | Every decision path checked this session (routing, compilation) treats a model output as a scored input, never the executed action itself; the `plan_compile` gate specifically sits between plan and execution for exactly this reason |
| Capability → Governance bypass | **Holds, with two disclosed transitive-only exceptions** | `UnifiedMemory.update()`/`delete()` are not directly governed but are only reachable from already-governed workers (§8, predecessor §11) |
| Worker → ambient execution state | **Unverified — the singleton question** | Five module-level singletons confirmed present (predecessor §9); whether any is reachable from a Worker's production call path was not traced this session either |
| Task A → silent mutation of Task B | **Holds by construction, but only weakly tested** | No cross-task identity exists yet to even test this against rigorously (§9's identity-missing finding cuts both ways: nothing has ever been observed leaking, but nothing has been built that would make leaking *possible* to test for either) |
| Reflection → unauthorized durable memory write | **Holds** | §5, §9 — governed via `UnifiedMemory.write()` |
| Untrusted resource → implicit trust | **Not independently audited this session** | No fresh check of external-input trust boundaries was performed |
| Legacy path → bypass canonical path | **Holds** | K2.2 legacy path is feature-flagged off, not silently coexisting (`use_k42_frontend`, confirmed) |
| Frozen contract → silent breaking change | **Fails once, confirmed** | ADR-001/`WorkerContext` (§9) is exactly this failure, already happened, still uncorrected |
| Retry → infinite loop | **Holds, narrowly** | `OperationRecoveryBudget` exists and bounds retries, though scoped to `trace_id` rather than a stable cross-retry identity (WE's own finding, reused) |
| Execution → identity loss | **Fails, confirmed** | §9's identity-missing finding, PFA Blocker #1 |
| External side effect → unsafe replay | **Not independently audited this session** | No idempotency mechanism exists at the Workflow level (predecessor §9's finding, reused) — this is the same gap as checkpoint/resume, not a separate one |

---

# 11. Authority Chain

**[DECISION]** Who is allowed to decide what, traced through the actual current pipeline:

```
User            → sole authority over goal content, task mutation intent, approval decisions
  ↓
Intent/Goal     → Planner-owned; cannot execute anything itself (confirmed, §6)
  ↓
Planner         → strategy only; explicitly cannot compile (§5's preserved boundary) or execute
  ↓
Governance      → sole authority to authorize the plan_compile gate and every downstream mutation
  ↓
Executor        → mechanical authority only — "can this run safely," never "should this run" (predecessor §6's timing test)
  ↓
Validator       → not a distinct current component; validation is folded into Governance's evaluate_action() calls and the compile-time gate — no separate "Validator" authority exists today, which is worth naming explicitly rather than silently assuming one does
  ↓
Memory/Learning → write authority only through Governance (§9); cannot self-promote a candidate to durable Knowledge without it
```

**[INFER]** No evidence was found this session of any lower-level component acquiring higher-level authority it shouldn't have — the one live exception to clean authority separation is not a component overreaching, but a component (`WorkerContext`) whose own *documented* authority (deprecated, should not exist) contradicts its *actual* authority (universally used) — a contract-stability failure (§5, §22), not an authority-escalation one.

---

# 12. Object Lifecycle Audit

| Object | Created | Mutated? | Versioned? | Persisted? | Superseded? | Deleted? | Replayed? | Gap |
|---|---|---|---|---|---|---|---|---|
| `Goal` | Intent interpretation | No (immutable per K4.2-H1 discipline) | **No** — no version field exists (confirmed by this session's own C-MoE research and re-confirmed here) | Via `ExecutionPlan.goal_id` reference | N/A — no versioning | No explicit deletion path traced | Via event log if event-logged | **No version field — this is the identity/mutation-handling gap underlying PFA Blocker #1, restated at the object level** |
| `ExecutionPlan` | `plan()` | No | **Yes, in spirit** — `caused_by` links a plan to the impasse that produced its successor; no integer version field, but a real lineage chain | Via `resource_id` | Via `lifecycle_state` (`superseded` is a defined enum value, per predecessor study §5) | Not traced | Via `caused_by` chain | `lifecycle_state`'s `compiled/executing/completed/failed/superseded` transitions are defined but nothing currently drives them (predecessor study's central §16 finding, reused) |
| `WorkflowDefinition` | `compile()` | Not traced this session | No | Not traced this session | Not traced | Not traced | Not independently confirmed this session | **No identity linkage to the plan/goal that produced it** — same root cause as `WorkflowNode`'s gap below |
| `WorkflowNode` | `compile()` | During execution (`node_states`, in-memory only) | No | **No — in-memory Python dict only**, confirmed (DEBT-003) | Not applicable | Not applicable | **No — this is exactly the durability gap** | Confirmed, unresolved |
| `ExecutionContext` | Per invocation | Working memory only, rest immutable (ADR-003) | No | Ephemeral by design | N/A | Garbage-collected at invocation end | N/A — deliberately ephemeral | None found — this object's lifecycle is correctly minimal by design |
| `WorkerContext` | Per worker invocation | Not traced | No | Ephemeral | N/A | Garbage-collected | N/A | **Its entire lifecycle is itself the open question** — should it exist at all (§9's `WorkerContext`/ADR-001 conflict) |
| `WorkerResult` | Per worker execution | No — immutable result object | No | Via `WorkerResult.artifacts` if referenced downstream | Not applicable | Not traced | Via event log if logged | Not independently re-verified this session beyond the `success=False` exception-boundary pattern already confirmed (predecessor §9) |
| `Resource` (`ResourceLifecycle`/`ResourceManager`) | Registration | Via `ResourceLifecycle` | Not confirmed | Confirmed present | Not confirmed | Not confirmed | Not confirmed | **The predecessor study's own open item, unchanged**: whether a formal `Resource` Protocol exists uniformly was not independently re-verified this session either |
| `KnowledgeEntry` | `UnifiedMemory.write()` | Via `update()` | Not confirmed this session | Yes, by definition | Via supersession semantics (not independently re-verified) | Via `delete()` | Via `EventStream` if event-logged | Provenance/trust fields' exact current shape not independently re-verified this session (same caveat as predecessor §10) |
| `Event` (`EventStream`) | Any governed mutation | Never — immutable by Law 2 | Implicit via ordering | Yes, durable (WAL-style) | N/A | Not traced | Yes — this is its entire purpose | None found |
| `LearningCandidate` | Learning pipeline | Via validation | Not confirmed this session | Via promotion to `KnowledgeEntry` | Via the validation gate itself | Not traced | Via `EventStream` if logged | DEBT-011 (K4.1-L/K4.2 `ContentDomain` reconciliation), confirmed still open, unrelated to this specific lifecycle question |

**[INFER]** The pattern across this table is consistent with every other finding in this document: objects **upstream** of the plan-compilation gate (`Goal`, `ExecutionPlan`) have real, if incomplete, lineage tracking; objects **at and downstream** of it (`WorkflowDefinition`, `WorkflowNode`) have none. This is the same boundary (§5, §7) showing up a third time, at the object-lifecycle level rather than the architecture-diagram or guarantee-matrix level — further evidence that PFA Blocker #1 is not an isolated gap but the single point where a real, working lineage discipline (upstream) meets a real, working execution mechanism (downstream) with nothing currently connecting them.

---

# 13. Current Kernel Inventory

**[STUDY, unchanged from the predecessor study's §5 — reused, not re-derived]** Full subsystem-by-subsystem table (Execution/Workflow/Capability/Governance/Memory Runtimes, Event Backbone, K4.2 Cognitive Front-End, C-MoE Boundary, Constitution, Identity model, `WorkerContext`/`ExecutionContext`, ADR record) is unchanged and not repeated here — see predecessor §5. This session's historical work (§3–5 above) does not change any cell in that table; it explains *why* several of them are shaped the way they are.

---

# 14. Constitutional Reconciliation

**[STUDY, unchanged from the predecessor study's §6]** Nine laws, nine invariants, both already-constitutional; the Pressure Test's proposed Contract Stability and Failure Containment laws remain proposed-but-not-adopted (confirmed, `ARCHITECTURE_CHANGELOG.md`); the Constitution's own `Status: Draft, not Final` remains unresolved, unchanged since July 8, and still not treated as a freeze precondition by any of now six audits including this one. **This session's addition:** §5's ADR-K4-04 finding is a second, concrete instance of "engineering practice exists, formal record does not" — the same shape as the already-known Contract-Stability-law situation, reinforcing rather than contradicting the predecessor's classification scheme.

---

# 15. Kernel Completion Requirements

**[STUDY, unchanged from the predecessor study's §20 "Kernel Completion Contract" — reused verbatim in substance]** A Kernel freeze may occur once: checkpoint/resume exists (⬜); the Watchdog/ProgressMonitor duplication is unified (⬜); the Scope/identity decision is made and `WorkflowNode`/`WorkflowDefinition` carry it (⬜, **the same gap §12 just found a third time**); the ADR-001/`WorkerContext` conflict is resolved (⬜); everything else already holds (✅ — governance enforcement, determinism/explainability at the correct precision, testing). **This session's historical work adds no new item to this list** — it explains the origin of the identity gap (§3–5, §12) more precisely than the predecessor could, without changing what needs to happen to close it.

---

# 16. Missing Kernel Work

| Gap | Evidence | Classification | Dependencies | Required Action |
|---|---|---|---|---|
| `WorkflowNode`/`WorkflowDefinition` identity linkage | §9, §12, PFA Blocker #1 | **BLOCKER** | None — decision only | Moncif's decision, then one additive field |
| ADR-001 vs. `WorkerContext` | §9, PFA Blocker #2 | **BLOCKER** | None | Moncif's decision, then either an ADR-text update or a 7-class migration |
| Checkpoint/resume | §9, DEBT-003 | **REQUIRED** | Identity decision above (needs something to key checkpoints against) | Implementation, no open design question |
| Watchdog/ProgressMonitor unification | §9, DEBT-016 | **RELIABILITY** | None | Implementation, no open design question |
| `ADR-K4-01` through `ADR-K4-06`, never written | §3, §5 | **CLEANUP** | None | Write them describing what was actually built, not what was planned |
| Retrieval-stack live-path status | Predecessor §8/§10 | **UNRESOLVED** | None | A direct, dated re-check — this document still cannot provide one |
| Formal `Resource` Protocol confirmation | Predecessor §8, §12 | **UNRESOLVED** | None | A direct re-check |
| Module-level singleton call-site tracing | Predecessor §9, §10 | **UNRESOLVED** | None | Trace whether any is reachable from a production request path |
| `AgentGovernor` delegation dormancy | DEBT-002 | **DEFERRED** | `SupervisorWorker` delegation triggers (does not currently invoke it) | Post-freeze, dormant-but-fail-closed is accepted |
| `EventStream`/`KnowledgeEvent` duplication | DEBT-004 | **DEFERRED** | None | Post-freeze consolidation |
| `os.execv()` ungoverned restart | Predecessor §8, §11 | **SECURITY** | None | Should not be indefinitely deferred, though not classified BLOCKER since it requires an active live-mission-in-progress restart to matter |

---

# 17. Execution / Reliability

**[STUDY, unchanged from the predecessor study's §9]** Slow ≠ stalled and alive ≠ meaningful progress both hold, checked directly against `ExecutionBudget`/`ProgressMonitor` code. Two independent watchdog implementations exist, reconciled but not unified (DEBT-016) — the second confirmed instance of the "prevent new duplication well, retire existing duplication less well" pattern (§9's Guarantee Matrix makes this explicit for the first time as a named pattern rather than two separate facts). Terminal states deterministic at the Worker boundary; not durable at the Workflow boundary (DEBT-003).

---

# 18. Workflow / Durability

**[STUDY, unchanged from the predecessor study's §12]** `EventStream.create_checkpoint()`/`get_checkpoint()` exist as unconsumed primitives. Confirmed absent, not merely "structurally present" — this document's own §9 Guarantee Matrix restates this with full evidence-chain precision (guarantee → contract → implementation → enforcement → evidence → tests) rather than prose alone. **Idempotency at the Workflow level does not exist** — `operation_id` exists only for the cognitive path (§9, §12), meaning a duplicate-retry or replay-after-crash scenario has no dedup key to check against below the compilation boundary. This is the same underlying gap as checkpoint/resume, not a second, independent one — both trace to the identity gap (§9, §12, §16).

---

# 19. State / Memory / Learning

**[STUDY, largely unchanged from the predecessor study's §10, with §5's reconciliation folded in]** One canonical memory path (`UnifiedMemory`) confirmed; the retrieval-stack legacy-vs-canonical question remains genuinely unresolved this session (honest carry-forward, not a fresh finding either way). **This document's specific addition**, per its own §26 mandate to reconstruct original K4.4/K4.5 semantics: the enforced chain today is **Reflection/Evaluation → `UnifiedMemory.write()` (governed) → durable Knowledge**, with **no separate validation stage between "evaluation record" and "durable memory write" beyond `UnifiedMemory.write()`'s own governance check** — the original plan's implicit assumption that K4.5 would be a distinct integration step with its own validation logic did not materialize as a separate step, because (per §5) the write path was already trustworthy by the time this work was built, collapsing what would have been two steps into one without losing the safety property either was meant to provide.

---

# 20. Governance / Security

**[STUDY, unchanged from the predecessor study's §11]** Every production mutation path checked is governed, with two disclosed, transitively-covered exceptions (`UnifiedMemory.update()`/`delete()`). `os.execv()` remains the single most concrete control-plane bypass found (zero governance evaluation on a live-mission restart). DEBT-010's configuration-watcher race remains open, unfixed, tracked. Prompt/tool injection boundaries remain not independently re-audited at the code level in either this session or the predecessor.

---

# 21. Concurrency / Data Integrity

**[DECISION, new analysis for this document — the predecessor study did not have a dedicated section for this]** Per the governing task's explicit partial-failure scenarios, evaluated against what this session's evidence actually supports rather than invented from nothing:

| Partial-failure scenario | Can it currently happen? | Consequence | Evidence basis |
|---|---|---|---|
| Workflow state written, event not written | **Cannot be ruled out — untested this session** | Possible phantom-progress state | No independent trace performed; `WorkflowRuntime`'s in-memory-dict state (DEBT-003) is not itself event-sourced per node transition, only at higher-level milestones, per the predecessor's own §12 finding |
| Event written, memory mutation fails | **Structurally unlikely** for the governed path specifically | — | `UnifiedMemory.write()` evaluates governance *before* mutating; an event for a mutation that didn't happen would require the write call itself to emit before attempting, which was not confirmed either way this session |
| Checkpoint exists, referenced artifact missing | **Cannot occur — no checkpoints exist yet** | N/A until DEBT-003 is closed | Direct consequence of the confirmed absence |
| Migration starts, process crashes midway | **Not evaluated this session** | Unknown | No schema-migration code path was audited this session or the predecessor |

**[DECISION, honest scope limit]** A full concurrency/race audit (the governing task's own §23) requires tracing actual concurrent-access code paths (shared config watcher threads, memory writes racing with reads, retry logic racing with cancellation) that neither this session nor its predecessor performed at the necessary depth. **This is named explicitly as the single largest gap in this document's own coverage** (§39's honesty requirement) rather than papered over with confident-sounding generalities. The one concurrency finding this study *can* state with confidence, because it was independently confirmed via direct code read: DEBT-010's config-watcher race is real, named, and unfixed.

---

# 22. Contract Stability / Migration

**[STUDY, unchanged from predecessor §15, extended by §5's finding]** Versioning is real and followed within K4.2's H1/H2 conventions; no general Kernel mechanism exists. The one live failure case remains ADR-001/`WorkerContext`. **This session's addition:** `ADR-K4-04`'s non-existence (§5) is a second, milder instance of the same underlying problem — a contract decision (the `plan_compile` gate's placement) was made and implemented correctly, but its formal record was never written, which is a smaller failure than ADR-001's (code and document don't *contradict* each other here, the document simply doesn't exist) but is evidence of the same systemic weakness: **this project is more disciplined about implementing contract decisions than about formally recording them once implemented.**

---

# 23. Legacy / Duplicate Architecture

**[STUDY, unchanged from predecessor §16, table reused]** `WorkerContext`/`ExecutionContext`, `EventStream`/`KnowledgeEvent`, duplicate Watchdog/ProgressMonitor implementations, K2.2 legacy path (intentionally retained), the two renamed misnamed documents (already resolved by prior sessions). **No new duplicate found this session.**

---

# 24. Decision Register

**[DECISION, the governing task's explicitly mandatory table]**

| Decision | Current Question | Options | Recommended Choice | Owner Decision Required? | Blocking? |
|---|---|---|---|---|---|
| Scope/identity | What does "Scope" mean for Kernel v1.0? Should `WorkflowNode`/`WorkflowDefinition` carry `operation_id`? | (a) Yes, add it now; (b) defer, freeze without it | (a) — every downstream capability this study examined (durability, task mutation, C-MoE) depends on it | **Yes — Moncif** | **Yes (PFA Blocker #1)** |
| `WorkerContext`/`ExecutionContext` | Retire `WorkerContext`, or update ADR-001 to reflect that it's the real contract? | (a) Migrate 7 worker classes to `ExecutionContext`; (b) rewrite ADR-001's text | Either is acceptable; (b) is cheaper, (a) is more architecturally honest to the original intent | **Yes — Moncif** | **Yes (PFA Blocker #2)** |
| Checkpoint/resume implementation approach | Build fresh, or adopt the DEBT-015 proposed schema (`Operation`/`ExecutionAttempt`/`ExecutionSnapshot`)? | (a) Adopt DEBT-015's schema; (b) design new | (a) — already researched, externally validated (openhuman's `SqlRunLedgerCheckpointer`, Temporal/LangGraph/Restate precedent) | No — this is an implementation choice, not an architectural one, once the identity decision above is made | Not itself blocking, but cannot be usefully built until the identity decision is made |
| Watchdog/ProgressMonitor unification target | Keep the graph-aware implementation, the standalone one, or write a third that supersedes both? | (a)/(b)/(c) | Not evaluated in enough depth this session to recommend a specific target — flagged as an open question (§30) | Engineering judgment, not necessarily Moncif's | No — non-blocking, but should not be deferred indefinitely |
| `ADR-K4-01`–`06`, write now or skip | Formalize the original K4 roadmap's decision records retroactively? | (a) Write them, describing what was built; (b) don't bother, the code comments already cite the source document | (a) — cheap, closes a real gap (§16, §22) | No | No |
| Constitution's `Draft, not Final` status | Resolve to Final, or explicitly decide Draft is acceptable through freeze? | (a) Finalize now; (b) explicit acceptance of Draft-through-freeze; (c) continue not deciding | Not this study's call — named, not resolved, for the sixth consecutive audit | **Yes — Moncif**, if it is to be resolved at all | **Not currently blocking**, per this and every prior audit's own classification, but is the one item this study recommends stop being silently carried forward without an explicit decision either way |

---

# 25. Closed / Open / Deferred Register

**CLOSED — do not reopen without new evidence:**
- Constitution law count (9 laws, 9 invariants; DEBT-009, July 22)
- K3 (Kernel Compliance Audit) — performed; K3.5/K3.5.1 are its remediation, not a parallel effort (confirmed via git history this session and predecessor)
- Planner/Compiler boundary (§5 — confirmed intact, not merely assumed)
- Reflection-Evaluation/Memory sequencing (§5 — restructured but safety-equivalent; do not "restore" the original two-packet sequencing, it would remove working capability for no benefit)

**OPEN — requires decision or implementation:**
- Scope/identity linkage (§24, BLOCKER)
- `WorkerContext`/`ExecutionContext` (§24, BLOCKER)
- Checkpoint/resume (§16, REQUIRED)
- Watchdog/ProgressMonitor unification (§16, RELIABILITY)
- `ADR-K4-01`–`06` retroactive documentation (§16, CLEANUP)
- Retrieval-stack live-path status (§16, UNRESOLVED — needs a check, not a decision)
- Formal `Resource` Protocol confirmation (§16, UNRESOLVED)
- Singleton call-site tracing (§16, UNRESOLVED)
- Full concurrency/race audit (§21, explicitly named as this document's own largest coverage gap)
- Constitution `Draft, not Final` status (§24 — open on whether to decide, not open as a live problem)

**DEFERRED — intentionally post-Kernel:**
- `AgentGovernor` delegation activation (dormant-but-fail-closed accepted, DEBT-002)
- `EventStream`/`KnowledgeEvent` consolidation (DEBT-004)
- `BudgetGovernor` cross-step accumulation (DEBT-007)
- C-MoE, in its entirety (§37)
- External resource/skill acquisition, in its entirety (§36)

---

# 26. Test Reality

**[STUDY, unchanged from predecessor §17]** Full suite independently re-run twice now (predecessor session and confirmed stable): 1,331 passed / 34 failed, all 34 the pre-existing `huggingface.co`-unreachable environment class, confirmed by per-failure traceback inspection. No dedicated `EventStream` test suite (DEBT-008). Governance validation exists "by construction" for several K3.5 checks, not fully live-executed — a disclosed evidentiary gap, not a hidden one.

---

# 27. Reproducibility / Operational Readiness

**[DECISION, new for this document]** A fresh-clone reproduction was, in fact, performed twice across this engagement's sessions (once for the C-MoE research, once for this Kernel study), each time successfully: clone → dependencies already present in this sandbox's Python environment (no install failures once disk-space constraints were worked around) → full test suite runs cleanly → 1,331/1,365 passing, environment-only failures excluded. **[FACT]** No database, external service, or non-Python runtime dependency was required to reach this state — the one external dependency the test suite touches (`huggingface.co`, for sentence-transformer embeddings) is exactly the one source of the 34 known failures, cleanly isolated and understood, not a hidden or surprising dependency. **This is a genuinely positive reproducibility finding**, worth stating plainly rather than only in the negative (no evidence of fragility was found, across two independent fresh-clone attempts).

---

# 28. Research Synthesis

**[STUDY, unchanged from predecessor §18 — five prior freeze audits (Jul 14 – Aug 23) plus RS/CS/WE/AED, and fresh external research (tinyhumansai/openhuman, affaan-m/ECC, Google ADK, RouterEval, the arXiv:2604.27891 calibrating caution) all carry forward unchanged.]** **This session's own addition to the research base is entirely historical/internal** (§3–5) rather than external — no new external research was performed this session, since the governing task's own research list (§48–49) substantially overlaps what the predecessor already covered, and this session's marginal value was clearly in the git/document archaeology instead.

---

# 29. Research-to-Kernel Gap Matrix

**[STUDY, unchanged from predecessor §19]** Execution isolation, durable execution/checkpoint-resume, cancellation, stable cross-boundary identity, capability contracts/lifecycle, deterministic routing, contract versioning/deprecation discipline, failure containment, task/goal mutation handling — all findings unchanged. **This document's historical work reinforces, rather than adds a new row to, the identity-related rows specifically** — §12's object-lifecycle finding is a third independent confirmation (after the predecessor's §5/§8 and this document's §9 Guarantee Matrix) that the identity gap is the single most load-bearing missing primitive in this entire research base.

---

# 30. Task Mutation Analysis

**[STUDY, unchanged from predecessor §14, reinforced by this session's §12]** Kernel-required in its identity foundation only; post-Kernel in its mechanism. `planner.py::plan()` still takes only `(request, registry)` — no prior WorkGraph, no goal version, nothing to diff against. **§12's object-lifecycle audit adds direct confirmation**: `Goal` has no version field, `ExecutionPlan` has lineage-in-spirit (`caused_by`) but no integer version, and nothing downstream of compilation has any lineage at all. Do not design C-MoE to solve this (this document agrees with the governing task's own instruction on the merits, independently re-derived, not merely repeated) — the fix is the identity primitive, which is Kernel work, not cognitive-reasoning work.

---

# 31. Kernel Completion Contract

**[STUDY, unchanged from predecessor §20 — restated here as this document's canonical version]**

**A Kernel freeze may occur once:**
- ✅ Cognition pipeline (Intent → Governance) — complete, governed, tested
- ⬜ **Checkpoint/resume** — absent
- ⬜ **Unified Watchdog/ProgressMonitor** — two implementations remain
- ✅ Resource lifecycle management exists; ⬜ formal `Resource` Protocol unconfirmed
- ⬜ **Checkpoint/resume, again, under Durability** — same gap, listed once at the guarantee level (§9) and once at the domain level here for completeness with the governing task's own structure
- ✅ Governance enforcement, with two disclosed transitive exceptions
- ✅ Determinism/Explainability at the correct, Pressure-Test-specified precision
- ⬜ **ADR-001/`WorkerContext` resolution**
- ⬜ **Scope/identity decision and implementation**
- ✅ Extension boundary (Adapter/Capability Protocol), correctly absent only where it should be (the C-MoE seam)

**Explicitly excluded, with reasons, unchanged from predecessor §20:** ratified Contract Stability/Failure Containment laws (practice exists, Constitutional status is separable and non-blocking); full Verification subsystem (nothing depends on it existing); distributed concerns (no evidence of need); the Constitution's own Draft status (named, §24, not made a gate condition since five prior audits plus this one found no live incoherence traceable to it).

---

# 32. Canonical Sequential Implementation Plan

**[DECISION — the one plan this document asks for, per its own instruction not to preserve obsolete packet names or invent new K-numbers]**

```
Phase 0 — Reconciliation / Decisions
  Step 0.1: Scope/identity decision (Moncif)
  Step 0.2: WorkerContext/ExecutionContext decision (Moncif)
  Step 0.3: Write ADR-K4-04 through ADR-K4-06 retroactively, describing
            what was built (cheap, parallelizable with everything else)

Phase 1 — Foundational Kernel Corrections
  Step 1.1: Implement the identity decision (0.1) — add operation_id
            linkage to WorkflowNode/WorkflowDefinition
  Step 1.2: Implement the WorkerContext decision (0.2) — either update
            ADR-001's text, or migrate 7 worker classes to ExecutionContext

Phase 2 — Durability / Reliability
  Step 2.1: Checkpoint/resume, adopting DEBT-015's proposed
            Operation/ExecutionAttempt/ExecutionSnapshot schema, keyed to
            the identity field from Step 1.1
  Step 2.2: Unify Watchdog/ProgressMonitor to one canonical implementation

Phase 3 — State / Memory / Contract Cleanup
  Step 3.1: Re-verify retrieval-stack live-path status; fix if still legacy
  Step 3.2: Confirm/complete formal Resource Protocol
  Step 3.3: Trace singleton call sites; confirm benign or fix

Phase 4 — Legacy Removal
  Step 4.1: If Step 0.2 chose migration, remove the WorkerContext shim
            entirely once all 7 classes are migrated and tested
  Step 4.2: EventStream/KnowledgeEvent consolidation (DEBT-004) — may be
            deferred past freeze per its own DEFERRED classification (§25),
            but is safe to do here if convenient

Phase 5 — Full Kernel Audit
  Step 5.1: A concurrency/race audit at the depth §21 explicitly named as
            not yet performed
  Step 5.2: Re-run the full Hail-Mary campaign (§34) against the
            post-Phase-1-4 codebase

Phase 6 — Freeze Validation
  Step 6.1: Check every row of the Freeze Gate (§35) against fresh evidence
  Step 6.2: Produce the Freeze Artifacts (§33)

Phase 7 — Kernel v1.0 FREEZE

Phase 8 — Post-Kernel (§36-37)
```

Hard dependencies: 0.1 → 1.1 → 2.1 (each strictly gates the next). 0.2 → 1.2 → 4.1 (same). Soft/parallel-safe: 0.3, 3.1, 3.2, 3.3 have no dependency on anything else and can run alongside Phase 0-2 at any time. 2.2 has no dependency on Phase 1 and can also run in parallel. Phase 5 depends on Phases 1-4 being substantially complete, since a concurrency/hail-mary audit of code that's about to change again has limited value.

---

# 33. Freeze Artifacts

**[DECISION]** What physically constitutes "Kernel v1.0, frozen," per the governing task's own list, mapped to what already exists vs. what this plan produces:

```
frozen architecture specification   — EXISTS (KERNEL_ARCHITECTURE_v1.0.md, July 10)
accepted ADR set                    — EXISTS + Phase 0.3/Phase 1's new ADRs
frozen public contracts             — Phase 1 resolves the one live contradiction
Constitution status                 — EXISTS as Draft; freeze does not require
                                       resolving this per §31, but should record
                                       the explicit decision not to (§24)
implementation baseline             — this document's own §13 inventory, dated
test baseline                       — 1,331/1,365, dated, environment failures named
known limitations                   — §16, this document
debt register                       — KNOWN_ISSUES.md, already maintained
migration/version policy            — Phase 0.3's retroactive ADRs establish this
                                       for the plan-compilation gate specifically;
                                       no general policy exists yet (§22) and this
                                       plan does not manufacture one merely for
                                       freeze's sake
reproducibility record              — §27, already demonstrated twice
security review                     — Partial (§20); os.execv() gap named, not
                                       closed by this plan (classified SECURITY,
                                       §16, recommended not to defer indefinitely
                                       but not gating freeze either)
reliability review                  — Phase 5
failure-campaign results            — Phase 5.2, per §34
release/tag/commit                  — Phase 7's own action
```

---

# 34. Hail-Mary Campaign Plan

**[DECISION — a plan, not an execution, per this task's explicit instruction]** Scoped to run in Phase 5, after Phases 1-4 close the known gaps, so the campaign is attacking the corrected architecture, not the currently-known-incomplete one:

```
Cognition:  malformed plan input, impossible capability requirement,
            contradictory constraints — target: compile()'s governance
            gate correctly rejects, not silently degrades
Execution:  worker crash mid-checkpoint (Phase 2.1's new mechanism),
            watchdog false-positive after unification (Phase 2.2)
Durability: process restart mid-workflow — target: resume without
            duplicate side effects, the exact DEBT-003 exit criterion
State:      concurrent task identity collision — target: Phase 1.1's new
            identity field actually prevents cross-task confusion, not
            merely records identity without using it defensively
Governance: attempt a plan_compile bypass directly — target: confirm the
            gate found in §5 cannot be circumvented by a crafted
            WorkflowDefinition constructed outside compile()
External:   os.execv() during an active mission — target: confirm whether
            this remains ungoverned post-Phase-4, and if so, whether that's
            acceptable for freeze (this plan does not presume the answer)
```

Every finding becomes: reproduction → root cause → fix → regression test → full regression, per the governing task's own required chain. **This plan does not execute the campaign** — Phase 5.2 in §32 is where that happens, after this document's own recommendations are implemented.

---

# 35. Freeze Gate

**[DECISION, unchanged verdict from predecessor §22, restated with this document's fuller evidence chain]**

| Criterion | Status |
|---|---|
| Architecture coherent (original K4 intent reconciled) | **PASS, newly confirmed this session** — §3–5's reconciliation found substance preserved even where labels were not |
| Identity | **FAIL** — §9, §12, §24 |
| Contract stability (no frozen-doc-vs-code contradiction) | **FAIL** — ADR-001/`WorkerContext` |
| Durability | **FAIL** — checkpoint/resume absent |
| No duplicated authority | **FAIL, twice** — Watchdog/ProgressMonitor, EventStream/KnowledgeEvent |
| Governance | **PASS** |
| Determinism/Explainability | **PASS** |
| Testing | **PASS** |
| Concurrency | **UNRESOLVED — not yet audited to the depth this gate requires** (§21) |
| Cleanup | **FAIL** — expired `WorkerContext` shim sunset condition, unwritten ADRs |
| Reproducibility | **PASS** |

**Verdict: NOT_FREEZE_READY.** Unchanged from yesterday's verdict in substance; this document adds one new column of confidence (§3-5's historical reconciliation) and one new named gap in the gate itself (concurrency, honestly marked UNRESOLVED rather than assumed PASS).

---

# 36. Post-Kernel Roadmap

**[STUDY, unchanged from predecessor §23]** C-MoE, external resource acquisition, advanced skill evolution, multi-node OCBrain, advanced Studio features, speculative autonomy — all post-Kernel, all with the extension points named in predecessor §23's table, unchanged.

---

# 37. C-MoE Dependency Contract

**[STUDY, unchanged from predecessor §24, reinforced by this session's own historical finding]** Every C-MoE need traces to a Kernel gap already named in this document under a different lens: generalized dispatch (§16's blocking dispatch-bridge finding, carried from predecessor), stable identity (§9, §12, §24 — now confirmed independently three separate ways this session alone), checkpoint/resume (§18), a single trusted progress signal (§17). **This document adds no new C-MoE-specific requirement** — it only strengthens the evidence behind requirements the predecessor already named, which is the correct outcome for a document whose job was to reconcile history, not expand scope.

---

# 38. Immediate Next Step

**Exactly one, unchanged in substance from yesterday, now backed by two independent studies and a git-verified historical reconstruction rather than one:**

> **Bring the Scope/identity decision and the ADR-001/`WorkerContext` decision to Moncif as the two explicit, fully-specified blockers they are — both open for one week with zero movement, both re-confirmed unchanged twice now. Everything else in this document (the retroactive ADRs, the retrieval-stack check, the concurrency audit, the Watchdog unification) is real, correctly sequenced to follow those two decisions, and does not need to precede them.**

---

## A Note on What Changed Between This Document and Its Predecessor

Not the verdict (unchanged: NOT_FREEZE_READY, same two blockers). Not the Freeze Gate's shape (same criteria, same two new confirmed failures beyond the two blockers — duplicated authority, cleanup). What changed is **confidence and precision**: yesterday's study knew *that* the Kernel was incomplete; this one additionally knows *why*, historically — that the original architecture was more thorough than its packet-driven implementation history suggests at a glance, that most of its safety-relevant boundaries survived contact with real engineering pressure even when their names didn't, and that the one boundary that didn't survive as designed (K4.4/K4.5's sequencing) turned out not to matter because the underlying concern was satisfied by an accident of chronological ordering rather than by design. That is a meaningfully better position to freeze from than "we don't know what we might have lost" — even though it changes none of the two decisions still sitting, unmoved, in front of Moncif.
