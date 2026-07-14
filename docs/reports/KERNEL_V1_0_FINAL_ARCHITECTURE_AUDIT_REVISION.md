# OCBrain Kernel v1.0 — Final Architecture Audit Revision

**Date:** July 14, 2026
**Status:** Revision of `K2_DOCUMENTATION_SYNCHRONIZATION_AND_K2_4_READINESS_REPORT.md`. Not a new audit — the repository is unchanged (`git fetch` confirms `origin/main` is still at `5370ed0`, this session's own prior commit). No code modified. No architecture redesigned. Constitution not amended. Historical ADRs not renumbered.
**Relationship to prior work:** every validated finding from the previous report is preserved below. Nothing is removed; nothing is reversed. What changes is authority framing (§2 below), the degree of emphasis given to naming versus behavior, and the addition of two new sections (§9, §10) synthesizing what the prior three sessions' evidence adds up to architecturally, not just item-by-item.

---

## 1. Executive Summary

This revision does four things the prior report did not: (1) reframes findings that leaned on `K2_IMPLEMENTATION_PLAN.md` so that a planning artifact is never treated as if it were a specification — the underlying findings survive because, checked again, every one of them is independently grounded in `KERNEL_ARCHITECTURE_v1.0.md` itself, not only in the plan; (2) explicitly investigates and rules out a specific alternative explanation for the retrieval-stack finding (does `RetrievalFusionEngine` secretly delegate to the canonical stack? — no, verified directly, §12); (3) decouples the Constitution's law-numbering question from K2.4's actual governance engineering, which changes the recommended action order; (4) adds two sections describing what the accumulated evidence across three sessions now shows about the kernel's emerging shape, and ranks remaining work by architectural risk rather than by effort or age.

**No factual finding changes.** K2.1 complete. K2.2 half-complete. K2.3 complete with minor naming drift. K2.4 not started. The Constitution is nine laws, Draft, while several downstream documents assert eleven. K3 is not ready. What changes is how confidently each of these can be stated, how they're grounded, and what follows from them.

---

## 2. Validation of the Previous Audit — Reframed for Authority

The previous report is validated in substance. This section corrects one thing about *how* it argued its case, per the authority order specified for this session:

1. `OCBRAIN_KERNEL_CONSTITUTION.md`
2. `KERNEL_ARCHITECTURE_v1.0.md`
3. `PROJECT_INSTRUCTIONS.md`
4. Accepted ADRs
5. Implementation Plans
6. Reports

`K2_IMPLEMENTATION_PLAN.md` is an Implementation Plan — rank 5. It describes an intended approach: which files were expected to be created, which existing files were expected to change, and what the author believed "done" would look like at the time it was written. It is not a specification, and deviation from it is not, by itself, evidence of incompleteness. The previous report's language ("graded directly against its own file manifest," "9 of 16 files exist") reads, in places, as if matching the plan's exact file list were the bar. It should not be. Restated properly: **the question that matters is whether the architectural behavior specified in `KERNEL_ARCHITECTURE_v1.0.md` (rank 2) is present, not whether the code lives at the file paths a planning document guessed it would.**

Checked against that corrected standard, every substantive finding survives, because each one turns out to be independently grounded above rank 5, not only within it:

- **The retrieval-stack finding does not depend on the plan at all.** `KERNEL_ARCHITECTURE_v1.0.md` §13 — the canonical architecture itself — designates `RetrievalContextBuilder`/`GraphRAGPipeline` "Canonical Stack" and `RetrievalFusionEngine` "Legacy Stack, to be superseded." That designation is what makes the current code's continued use of the legacy path a real finding. `K2_IMPLEMENTATION_PLAN.md`'s explicit deliverable table (naming `core/memory/assembly.py`) is retained below only as corroborating evidence that this was understood as concrete, scheduled work — not as the source of the finding's authority.
- **The governance finding does not depend on the plan either.** `KERNEL_ARCHITECTURE_v1.0.md` §14.3's own table already documents which governors are live, disconnected, or unbuilt — independently confirmed against the actual classes in `core/governance/`.
- **The capability-layer naming observation (`Adapter` vs. the plan's `CapabilityAdapter`, `AdapterRuntime` vs. `CapabilityResolver`) is exactly the kind of thing that *should* be read as low-weight**, per this section's own logic — it is a planning-artifact-versus-implementation naming difference, not a specification-versus-implementation one, since `KERNEL_ARCHITECTURE_v1.0.md` §10 describes the Protocol-based Adapter pattern in terms general enough that either name satisfies it. Condensed accordingly — see §8.

Where this section previously used "success criteria" and "exit criteria" language borrowed directly from the Implementation Plan, that grading is retained in §12 as a useful, practical cross-check (it was, after all, the project's own stated definition of what K2 needed to deliver) — but explicitly relabeled as corroborating, not authoritative, evidence.

---

## 3. Documentation Synchronization Findings

Unchanged from the previous report, with the naming-drift item condensed per §2 and one addition:

1. `K2_IMPLEMENTATION_PLAN.md` has never been updated with completion status against its own milestones — still reads as a pure forward-looking plan despite three of four phases being delivered.
2. `provider_mesh.py` was deliberately left unmodified for K2.3, extended via external adapters instead — a positive deviation, now elevated to a formal recommendation (§5.4).
3. **New, incidental to this session's rule-5 verification (§12):** `core/memory/retrieval/fusion.py`'s docstring cites "ADR-006" for the decision that "all retrieval logic lives exclusively in `UnifiedMemory`" — a different decision than the ADR-006 catalogued in `KERNEL_ARCHITECTURE_v1.0.md` §21 (EventBus subscribes to EventStream). This is a real numbering collision between the pre-Kernel "Session 3B"-era ADR sequence referenced in code comments and the Kernel-phase ADR-NNN sequence audited in §5. Low practical consequence — the two contexts are unlikely to be confused in practice — but it is a second, concrete instance of the exact problem §5 already describes in the abstract, found while verifying an unrelated question, and worth folding into the same cleanup rather than treated as new work.
4. Naming drift (`Adapter`/`AdapterRuntime` vs. the plan's `CapabilityAdapter`/`CapabilityResolver`; `WorkflowNodeState` vs. the plan's separate `WorkflowInstance`/`WorkflowState`) — noted once, here, rather than repeated across §8 and elsewhere as in the previous report. Functionally equivalent in both cases; not tracked further as a distinct action item.

---

## 4. Constitution Review — Decoupling Governance Behavior from Law Numbering

The previous report's finding stands unchanged: `OCBRAIN_KERNEL_CONSTITUTION.md` is nine laws, `Status: Draft, not Final`; `ARCHITECTURE_CHANGELOG.md`, `PRODUCT.md`, `CHANGELOG.md`, `README.md`, and `KERNEL_ARCHITECTURE_v1.0.md` §3.1 all assert or imply eleven. This section revises how much that fact should weigh on what happens next, because the previous report's recommended action order implicitly coupled "resolve the numbering" to "before governance work proceeds" — a coupling worth examining directly rather than carrying forward by inertia.

**Two separate questions were being treated as one.** The first: *what does the Constitution currently say, and is every document consistent with it?* — a Single Source of Truth question, purely textual. The second: *what should K2.4's governors actually enforce?* — an engineering-design question. These do not need the same answer at the same time.

**Governance should enforce architectural behaviors, not law numbers.** Failure containment (bounded blast radius; no unhandled exception propagates past the `ExecutionRuntime` boundary), contract stability (existing dependents aren't silently broken), and deterministic execution are sound engineering practices independent of whether they carry a Constitutional citation. This is not merely asserted — it is already partially true in the current codebase: `KERNEL_ARCHITECTURE_v1.0.md`'s own ADR-004 (WorkflowRuntime Owns Retries) and ADR-005 (No Automatic Rollback in K2) already encode failure-handling behavior at the implementation level, and ADR-007 (Resource as Protocol) already encodes contract-stability-supporting design — specifically so existing types don't need to change their declarations to satisfy a new interface. All three of these are live, ratified (Constitution Law 4, Determinism; Law 3, Separation of Concerns), and doing real work today, entirely independent of whether "Contract Stability" and "Failure Containment" ever become numbered Laws 10 and 11.

**Consequence for sequencing:** resolving the Constitution's textual status remains worth doing — it is cheap, and it is the direct fix for a repository-wide inconsistency spanning five-plus documents — but it is **not a prerequisite for K2.4's engineering work**, and this revision removes that implied dependency from the action plan (§13). K2.4 can and should build `OrchestrationGovernor`, `AgentGovernor`, `ConversationGuardrails`, and reconcile `MemoryGovernor` against sound engineering principles that are already well-specified, whether or not the Constitution amendment has happened yet. The two resolution paths presented previously (ratify via the Pressure Test's proposed diff, or correct the five-plus downstream documents back to nine) remain unchanged and unexecuted here, per instruction.

---

## 5. ADR Review

### 5.1 Numbering, locations, lifecycle — unchanged from the previous report

`ADR-NNN` (sequential, embedded in `KERNEL_ARCHITECTURE_v1.0.md` §21, ADR-001–008) and `ADR-K{phase}-{seq}` (session-scoped, `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md`) coexist without either being documented as the deliberate convention. No dedicated ADR directory exists. Three major decisions (Worker Template Method, UnifiedMemory as Owner, Retrieval Stack Consolidation) have no ADR number in either sequence.

### 5.2 New: a third, colliding numbering context

§3, item 3: `core/memory/retrieval/fusion.py`'s docstring references an "ADR-006" from what its own comments call "Session 3B" — a pre-Kernel-phase numbering context distinct from both sequences in §5.1. This doesn't change the recommendation, it reinforces it: the two-tier convention proposed below should also account for retiring or namespacing older in-code ADR references from before the Kernel phase existed, not only the two currently-active sequences.

### 5.3 Recommended long-term organization — unchanged

Adopt the two-tier convention explicitly: `ADR-NNN` closed at the K1.7–K1.11 freeze batch (ADR-001–008, no new members); `ADR-K{phase}-{seq}` for everything since. Create `docs/architecture/decisions/`, move `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` there unchanged. Give the three unnumbered changelog decisions phase-appropriate identifiers (`ADR-K1-01`, `ADR-K1-02`, `ADR-K1.5-01`) rather than folding them into the closed `ADR-NNN` sequence — no renumbering of ADR-001–008. A short `INDEX.md` lists every ADR, its status, and one line of scope, and should note the retired pre-Kernel numbering context from §5.2 as historical, non-authoritative background.

### 5.4 New recommendation: an ADR for extension over modification

`provider_mesh.py` was left unmodified for K2.3; new adapters wrap its existing `Provider` classes from outside instead. This is not an isolated instance — the same pattern was independently applied a second time in the same milestone: `ModelRouter`'s existing bootstrap-to-shadow-to-native promotion logic was likewise left untouched and wrapped by `ModelRouterAdapter`, rather than replaced. Two independent applications of the same principle within one milestone is meaningful corroboration by this project's own stated standard (Constitution, Law of Evidence over Assumption: a pattern converged on independently is preferred over one adopted for being new).

**Recommendation:** a new ADR, using the §5.3 convention (e.g., `ADR-K2.3-02`), formally documenting the principle: *stable, live, already-tested production infrastructure should be extended through adapters and wrappers whenever practical, rather than modified directly.* This improves long-term maintainability in a specific, checkable way — it keeps the blast radius of new work bounded to the new adapter file, leaves the existing subsystem's own test coverage and behavior untouched and trustworthy, and gives a natural, low-risk rollback path (delete the wrapper) that direct modification doesn't offer. This ADR is a recommendation for a human or a dedicated session to create — not created in this session, consistent with the instruction against silently updating ADR decisions.

---

## 6. Repository Cleanup Plan

Unchanged from the previous report (see that report §6 for full detail): de-duplicate `PROJECT_INSTRUCTIONS.md`, `ARCHITECTURE_CHANGELOG.md`, and `ARCHITECTURE_HARDENING_SESSION_REPORT.md` (each exists twice, byte-identical, with no sync mechanism); move `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` into the new `docs/architecture/decisions/`; move `K2_2_CUTOVER_REPORT.md` and `K2_3_CAPABILITY_RUNTIME_REPORT.md` into `docs/reports/`; move `K2_IMPLEMENTATION_PLAN.md` into `docs/architecture/` as a planning companion to the canonical spec. No restructuring executed in this session.

---

## 7. Documentation Infrastructure Recommendations

Unchanged from the previous report's reconciled recommendation set — restated briefly:

- **`CURRENT_STATE.md`** — single-page current-truth snapshot; would have made a meaningful fraction of all three sessions' investigative work unnecessary had it existed and been kept current.
- **`IMPLEMENTATION_STATUS.md`** — not recommended as a separate file; fold into `CURRENT_STATE.md` as a milestone-status section rather than creating a second, overlapping source of truth.
- **`KNOWN_ISSUES.md`** — living, prunable debt list, distinct from `ARCHITECTURE_CHANGELOG.md`'s append-only historical narrative.
- **`IMPLEMENTATION_ROADMAP.md`** — living counterpart to `KERNEL_ARCHITECTURE_v1.0.md` §23's frozen roadmap block, matching `PROJECT_INSTRUCTIONS.md` §18.2.1's own stated design intent.
- **`PROJECT_INDEX.md`** — a "start here" map, promoting the previous report's own Documentation Dependency Map into a permanently maintained file.
- **Not recommended:** `ARCHITECTURE_DECISIONS.md` (role already filled by §5.3's `docs/architecture/decisions/INDEX.md`) and `MEMORY_ARCHITECTURE.md` (role already filled by `KERNEL_ARCHITECTURE_v1.0.md`'s own memory-layer sections).

---

## 8. K2 Status Review

Reframed per §2 — behavior against `KERNEL_ARCHITECTURE_v1.0.md`, not file-path matching against the plan. Where a planned file name differs from the actual one, that is noted once and set aside; what's graded is whether the intended architectural behavior is present.

### K2.1 — Execution Runtime: **Complete**

`ExecutionContext`, `CancellationToken`, `WorkingMemory`, `ExecutionRuntime`, `WorkerRegistry`, and a minimal `PlannerWorker` are all present and, per direct inspection of `main.py`, genuinely wired into the live composition root — `worker_registry.register(MemoryCuratorWorker)`, `execution_runtime = ExecutionRuntime(...)`. No remaining work.

### K2.2 — Workflow Runtime: **Half complete**

`WorkflowRuntime` and its DAG-execution machinery are complete and confirmed live in production (`main.py`: `workflow_runtime = WorkflowRuntime(...)`). The second half of this milestone's scope — replacing the live retrieval path's legacy stack with the canonical one — was not done. This conclusion rests on `KERNEL_ARCHITECTURE_v1.0.md` §13's own canonical-vs-legacy designation (§2), corroborated, not established, by the Implementation Plan's matching deliverable entry.

### K2.3 — Capability Registry: **Complete**

The full capability/adapter/resolver behavior specified in `KERNEL_ARCHITECTURE_v1.0.md` §10 is present for one capability type (`LLM_COMPLETION`), under names (`Adapter`, `AdapterRuntime`) that differ cosmetically from the plan's (`CapabilityAdapter`, `CapabilityResolver`) without any behavioral difference (§2, §3). `provider_mesh.py` was extended rather than modified, by design (§5.4) — a positive, lower-risk deviation from the plan, not a gap.

### K2.4 — Governance Completion: **Not started**

None of `orchestration_governor.py`, `agent_governor.py`, `conversation_guardrails.py` exist, even as empty files. `MemoryGovernor` remains an unregistered, base-class-incompatible singleton. Fully specified already in `KERNEL_ARCHITECTURE_v1.0.md` §14.3 and (as corroborating planning detail) `K2_IMPLEMENTATION_PLAN.md`.

---

## 9. The Architecture Emerging from Kernel v1.0: Five Independent Runtimes

This is a synthesis, not a new investigation — the underlying facts were already established across this and the two prior sessions; what's new is naming the pattern they add up to.

Across K2.1 through K2.3 (and K2.4's already-specified scope), the kernel has converged on five independently-addressable runtime subsystems, each occupying its own directory, each with its own internal state model, connected to the others only through narrow contracts rather than direct internal coupling:

| Runtime | Location | Owns | Does not do |
|---|---|---|---|
| **Execution Runtime** | `core/runtime/` | Invoking exactly one Worker per call, propagating `ExecutionContext`, honoring cancellation | Decide *whether* an action is permitted (that's Governance's job) or *what order* a multi-step task runs in (that's Workflow's job) |
| **Workflow Runtime** | `core/workflow/` | Coordinating DAGs of Execution Runtime invocations, retries, node state | Execute anything itself — it delegates every node to Execution Runtime |
| **Memory Runtime** | `core/memory/` | `UnifiedMemory`, `ContextAssemblyEngine`, the retrieval subsystem — all persistent and working memory | Decide governance policy over what gets stored or retrieved (that's `MemoryGovernor`'s job, currently disconnected — see below) |
| **Capability Runtime** | `core/capabilities/` | Resolving and invoking external capabilities/providers via `CapabilityRegistry` + `AdapterRuntime` | Know anything about workflows, workers, or memory — a capability request is opaque to what asked for it |
| **Governance Runtime** | `core/governance/` | Evaluating and gating actions before they proceed, via `GovernanceKernel` + Governors | Perform the work it gates — it evaluates, it never executes |

**Why this separation is significant, not merely tidy:** each runtime independently satisfies Constitution Law 7 (Replaceability) — Memory Runtime's retrieval engine could be swapped without Workflow Runtime knowing; Capability Runtime's adapters can be added or removed without touching Execution Runtime. Each independently satisfies Law 3 (Separation of Concerns) — no runtime performs another's job, confirmed by the "does not do" column above holding true in every subsystem checked across three audit sessions, not asserted from the architecture document alone. This is also the concrete, present-tense realization of work specified two phases earlier and on paper only: `OCBRAIN_K1_5_KERNEL_API_SERVICE_MODEL.md`'s "Kernel Service Model" table named almost exactly this set of services (`ExecutionRuntime`, `WorkflowRuntime`, `CapabilityRegistry`, `CapabilityResolver`, `WorkerRegistry`, `ContextService`, `GovernanceService`, `EventService`, `MemoryService`) as the target shape before a single line of K2 code existed. That the K2.1–K2.3 implementation now materially matches it is evidence the K1.5 design work was sound, not merely evidence that a plan was followed.

This pattern is what makes OCBrain's longer-term direction — a model-swarm architecture where cognitive functions are handled by independently swappable, specialized components — structurally possible rather than aspirational. A kernel where memory, execution, workflow, capability, and governance are genuinely separable is the precondition for eventually swapping in specialized workers, routing models by capability, or replacing a retrieval strategy, without a kernel-wide rewrite each time. This is worth recognizing as an architectural milestone in its own right, reached through K2.1–K2.3, not merely a byproduct of implementing a checklist.

**One honest qualifier:** the separation is currently cleanest for Execution, Workflow, Capability, and Governance Runtimes — each has exactly one live implementation of its core responsibility. Memory Runtime is the one exception: it currently contains *two* competing implementations of its retrieval responsibility (the legacy façade and the canonical stack), which is precisely the unresolved item this and the prior two audits keep returning to. The five-runtime pattern is real and load-bearing; it is not yet uniformly finished.

---

## 10. Architectural Risk Analysis

Ranked by architectural impact — blast radius, coupling, and reversibility — not by implementation effort or how long an item has been open.

| Risk | Item | Why |
|---|---|---|
| **Very High** | *(none currently open)* | Nothing in this audit represents an unbounded, cross-cutting risk. The two closest candidates (governance completion, retrieval cutover) are both already bounded by existing safeguards — Law 1's own discipline for the former, the plan's own A/B methodology for the latter — which is exactly what keeps them from qualifying here. |
| **High** | K2.4 Governance Completion | Governance is the one runtime (§9) that every other runtime's actions pass through by design (Constitution Law 1, Bounded Autonomy). New governor logic — not just wiring, genuine new rules — has a wide blast radius if the rules are wrong, and getting evaluation order or chain semantics wrong could silently under- or over-restrict every other subsystem at once. |
| **Medium** | Retrieval-stack cutover | Bounded architecturally — the swap happens entirely inside `ContextAssemblyEngine`'s own internals, behind an interface that doesn't change, with a well-specified rollback (revert to the legacy façade). Real risk is operational (retrieval quality regression), not structural, and is already the subject of a specified A/B methodology before cutover. |
| **Low** | Constitution law-count resolution | Per §4, this no longer carries architectural weight on its own — it is a textual consistency question, not a runtime-behavior one. Still worth fixing (Law of Single Source of Truth), but its risk is to document trustworthiness, not to the kernel's behavior. |
| **Low** | K2.3 naming reconciliation (`Adapter`/`AdapterRuntime` vs. plan names) | Cosmetic, zero behavioral difference (§2, §3) — carried at Low rather than Very Low only because left unaddressed indefinitely, it risks becoming a third inconsistent name for the same concept (§5.2 shows this has already happened once, with ADR numbering). |
| **Very Low** | Documentation infrastructure gaps, repository de-duplication, ADR directory creation | Zero runtime behavior impact. Real cost is process efficiency (repeated re-derivation of state across sessions, as this and the prior audit both had to do), not architectural soundness. |

---

## 11. K2.4 Readiness Assessment

**The repository is engineering-ready to begin K2.4**, unchanged from the previous conclusion, now on a firmer footing per §4: K2.4's four deliverables have no code-level dependency on the retrieval-stack item, and — per §4's decoupling — no longer need to wait on the Constitution's textual resolution either. Ranked by actual engineering importance, separating documentation cleanup from implementation blockers:

1. **Zero hard implementation blockers.** K2.1 (K2.4's only stated prerequisite) is complete; K2.4's file manifest, success criteria, and implementation order are already fully specified.
2. **No dependency on retrieval completion** (§9's Memory-Runtime/Governance-Runtime boundary makes this structurally clear, not just asserted) — the two can proceed in either order or in parallel.
3. **A specific reason to prefer Governance before Retrieval, if choosing an order rather than parallelizing — see §13.** Not a blocker in either direction; a recommendation about sequencing quality, addressed directly there per this session's own instruction to reevaluate it.
4. **No documentation cleanup item blocks K2.4.** The duplicate files, scattered reports, and missing `CURRENT_STATE.md` should still be fixed on their own merits, not as a precondition.

---

## 12. K3 Readiness Assessment

### Verdict: **NOT READY** — unchanged, now with the rule-5 verification made explicit

**The retrieval-stack finding was checked against a specific alternative hypothesis before being restated here: does `RetrievalFusionEngine` internally delegate to `RetrievalContextBuilder` or `GraphRAGPipeline`, making the "legacy vs. canonical" distinction moot?** Investigated directly this session by reading `core/memory/retrieval/fusion.py` in full, not inferred from an earlier, broader grep. **It does not.** `RetrievalFusionEngine` is a thin, already-refactored compatibility façade (per its own docstring, dating to "Session 3B," well before the Kernel phase) with exactly one method, `fuse_search()`, which delegates entirely to `UnifiedMemory.search()` (BM25 + vector + RRF). Its only imports are `UnifiedMemory` and `SearchResult`. There is no reference to `RetrievalContextBuilder` or `GraphRAGPipeline` anywhere in the file — no import, no instantiation, no call. This possibility is now investigated and explicitly ruled out, not left implicit.

**Grading against `K2_IMPLEMENTATION_PLAN.md`'s eight stated exit criteria**, retained as a useful cross-check per §2 — informative because it was the project's own definition of done, not authoritative because it is rank 5:

| # | Exit criterion | Status |
|---|---|---|
| 1 | All 16 new files implemented and tested | Not met as literally stated — most of the shortfall is naming/organization (§2, §8), not missing behavior; K2.4's three files are a genuine, complete gap |
| 2 | All 6 modified files updated and regression-tested | Not met — 3 of 6 as planned; 1 deliberately done differently for good reason (§5.4); 2 not done (`assembly.py`, `memory_governor.py`) |
| 3 | A Worker executes through `ExecutionRuntime` in production | **Met** |
| 4 | A Workflow executes through `WorkflowRuntime` | **Met** |
| 5 | `RetrievalContextBuilder` is the live retrieval path | **Not met** — confirmed directly, and now with the alternative hypothesis above ruled out |
| 6 | All governors registered and evaluating | **Not met** — 3 of 6 named governors registered |
| 7 | All public contracts match `KERNEL_ARCHITECTURE_v1.0.md` §18 | Not independently verified this session — this is literally K3's own stated purpose |
| 8 | Constitution compliance verified | Reframed by §4: this criterion, as written, conflates the two questions §4 separates. Compliance with the *behaviors* the Constitution requires (Laws 1–9, fully ratified) can be verified independently of the Laws 10–11 numbering question. Recommend K3 grade this criterion against the nine ratified laws only, treating the numbering question as a separate, parallel item rather than a blocker to this specific criterion. |

**Net: 2 of 8 clearly met, 4 of 8 clearly not met, 1 reframed rather than failed outright (§4's correction), 1 not evaluated this session.** This still yields NOT READY — the retrieval and governance gaps (criteria 5 and 6) are unaffected by anything reframed in this revision, and both are real, structural, independently-grounded findings (§2). What changes from the previous report is that criterion 8 no longer needs to be read as a hard blocker in its own right; it is folded into the Constitution's already-acknowledged, already-tracked, non-blocking resolution path.

---

## 13. Prioritized Action Plan — Reevaluated

The previous report's order was Constitution → Retrieval → K2.4. This session was asked to reevaluate specifically whether Governance should precede Retrieval, given no dependency runs either direction. It should, and the case is more than a preference:

**Governance before Retrieval, with the Constitution question running in parallel rather than gating either.**

The justification is textual, not just architectural intuition: `PROJECT_INSTRUCTIONS.md` LAW 1 — the first, foundational law of the entire project — states plainly that "*no feature increases capability without increasing governance visibility*," and that governance should be attached *before* a capability is extended, not fitted afterward. Wiring the canonical retrieval stack into the live path is a genuine capability change at the point of activation — every retrieval-touching request would, from that moment, receive materially richer information (graph-aware, contradiction-detecting, provenance-carrying `Context` objects instead of flat `SearchResult` lists), regardless of how long the underlying code has already existed unwired. Doing this while `MemoryGovernor` — the governor whose subsystem retrieval most directly belongs to — remains an unregistered, interface-incompatible singleton means the capability change would land in a less-governed environment than LAW 1 calls for. Completing K2.4 first means the retrieval cutover, when it happens, lands into an already-governed environment instead of needing governance retrofitted around it afterward — avoiding, in a smaller and more literal sense, the exact "build without wiring, worry about oversight later" pattern this project's own research has repeatedly named as its recurring failure mode.

This is not an absolute serialization requirement — genuinely, no code-level dependency runs from Governance to Retrieval (§9, §11), and with two active contributors, the two tracks could reasonably proceed in parallel. Where a single sequence must be chosen, Governance first is the more defensible default; where parallel work is possible, that is equally sound and this recommendation does not argue against it.

**Revised order:**

1. **Begin K2.4 (Governance Completion)** — no blocker, fully specified, and per the LAW 1 reasoning above, the more architecturally sound default when a single order must be chosen.
2. **Resolve the Constitution's textual status** (§4) — proceeds in parallel with (1), not before it; cheap, and the direct fix for the widest-reaching documentation inconsistency found across all three sessions.
3. **Complete K2.2's retrieval-stack wiring** — proceeds after (1) if serialized, or in parallel with both if resourcing allows; fully specified already, including its own A/B-comparison rollback plan.
4. **Create `CURRENT_STATE.md` and `KNOWN_ISSUES.md`** (§7) — the direct fix for why three consecutive sessions each had to reconstruct K2 status from multiple documents and a fresh code audit.
5. **Execute the repository cleanup plan** (§6) and **create the ADR directory with the extension-over-modification recommendation** (§5.4) — no dependency on anything above, can proceed at any point.
6. **Create `IMPLEMENTATION_ROADMAP.md` and `PROJECT_INDEX.md`** (§7) — lowest urgency, completes the documentation-infrastructure set.
7. **Re-run K3 readiness once (1) and (3) are complete** — at that point, per §12's own criteria, genuinely close to a positive assessment rather than requiring a fourth audit to re-discover the same two structural gaps again.

---

*Revision complete. Every validated finding from the prior report preserved. No code modified. No architecture redesigned. Constitution not amended. Historical ADRs (ADR-001–008) not renumbered. This document and the prior report together form the complete audit trail; this document is the current definitive reference per its own header.*
