# OCBrain Kernel — Architecture Documentation Audit, ADR Cleanup, Architecture Consolidation & K3 Preparation

**Date:** July 14, 2026
**Status:** Consolidation session output. No code modified. No architecture redesigned. Every finding below is either a direct file/line citation from a fresh clone of `main`, or explicitly marked as a recommendation requiring a separate decision.
**Session type:** Documentation and architecture-consistency audit, per the session prompt's own framing — not an implementation session.

---

## 0. Methodology and a Correction to the Session's Own Premise

Per this project's standing discipline (Kernel Constitution, Law of Evidence over Assumption; `PROJECT_INSTRUCTIONS.md` §18.4.1/§20.5; and the precedent set by every K2.x session report), this audit began with a fresh clone of `github.com/1h0lde4/ocbrain-v4.1` rather than accepting the session prompt's framing at face value. That check matters here specifically because the prompt's opening line — **"Kernel-v1.0 is now functionally complete through K2.3"** — is not accurate as stated, and the rest of this report is built on the corrected picture, not the prompt's premise.

**What is true:** K2.1, K2.2, and K2.3 have all been delivered, are on `main`, and represent substantial, well-verified engineering work (§3, §5). The Phase-0-reality-audit discipline that this correction itself relies on is now visibly embedded in the project's own culture — both `K2_2_CUTOVER_REPORT.md` and `K2_3_CAPABILITY_RUNTIME_REPORT.md` independently re-verified the repository from scratch before writing any code, and both independently rediscovered the same `kernel-v1.0` tag inaccuracy this report also found (§1.4). That is a real strength, not a formality, and it is the reason this session's own findings are as precise as they are.

**What is not true:**
1. K2.2's own explicitly-assigned scope (wiring `RetrievalContextBuilder`/`GraphRAGPipeline` into the live retrieval path) was not completed, is not mentioned in K2.2's or K2.3's delivery reports, and remains open today (§3.1, §5).
2. K2.4 (Governance Completion) has not started at all — three of the five canonical governors do not exist as classes anywhere in the repository, and `MemoryGovernor` is unchanged from its previously-documented disconnected state (§3.2, §5).
3. K2.3's own delivery report does not claim K3-readiness. Its final verdict is **"READY FOR K2.4"** (`K2_3_CAPABILITY_RUNTIME_REPORT.md:229`) — a narrower, more precise claim than "functionally complete through K2.3," and one that already anticipates K2.4 as the next step, not K3.

The session prompt's request to assess K3 readiness is answered in §8. The short version: the canonical architecture's own roadmap (`KERNEL_ARCHITECTURE_v1.0.md` §23) places K3 *after* K2.4, and K2.4 has not begun. This alone would be sufficient; two further independent reasons are given in §8.

**Authority order used throughout** (as specified by the session prompt): Kernel Constitution → `docs/architecture/` canonical architecture → accepted ADRs → `PROJECT_INSTRUCTIONS.md` → repository implementation → previous reports. This order governs which *document* wins when two documents disagree about what *should* be true. It does not and cannot override what the running code *actually does* — that is never a matter of authority, only of observation. Where a document's prescription and the code's behavior are both being described below, this report keeps those two questions separate rather than letting the authority order quietly answer an empirical question it wasn't built to answer.

---

## 1. Architecture Documentation Audit

### 1.1 `/docs/architecture/` — Complete Inventory

Exactly three files exist, and only three:

| File | Lines | Root duplicate exists? | Status |
|---|---|---|---|
| `KERNEL_ARCHITECTURE_v1.0.md` | 1,045 | No — root copy was deleted during the reorg; this is the sole copy | Canonical, self-declared "Frozen," dated July 10, 2026 |
| `ARCHITECTURE_CHANGELOG.md` | 172 | **Yes** — byte-identical to root copy (`diff` confirms) | Historical narrative + decision log |
| `PROJECT_INSTRUCTIONS.md` | 1,396 | **Yes** — byte-identical to root copy (`diff` confirms) | Operational engineering rules |

The reorg the session prompt describes ("the architecture is no longer scattered across reports") is real and mostly successful: `git log` shows `OCBRAIN_K1_KERNEL_AUDIT_AND_SPECIFICATION.md`, `OCBRAIN_K1.5_KERNEL_API_SERVICE_MODEL.md`, `OCBRAIN_K1.6_RESOURCE_MODEL.md`, `OCBRAIN_K1.7-K1.11_FINAL_ARCHITECTURE_FREEZE.md`, `OCBRAIN_KERNEL_Draft_0.9.md`, all three external repo studies, and the standalone `KERNEL_ARCHITECTURE_v1.0.md` root copy were all deleted from root and now live under `docs/archive/kernel/` and `docs/archive/research/` respectively. That part of the claim checks out.

What the prompt's framing misses: **two files now exist in two places at once with no sync mechanism**, and **a new round of root-level scattering has already begun** — `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md`, `K2_2_CUTOVER_REPORT.md`, `K2_3_CAPABILITY_RUNTIME_REPORT.md`, and `K2_IMPLEMENTATION_PLAN.md` all sit at root today, unarchived, alongside a fourth root copy of `ARCHITECTURE_HARDENING_SESSION_REPORT.md` that duplicates `docs/reports/ARCHITECTURE_HARDENING_SESSION_REPORT.md` byte-for-byte. The reorg pattern was applied once, correctly, to the K1-era documents — but nothing enforces that new session output lands in the right place going forward. Addressed in §6–7.

### 1.2 `KERNEL_ARCHITECTURE_v1.0.md` — Section-by-Section Assessment

This document is, on the whole, excellent: internally coherent, precisely scoped, and — for the large majority of its 24 sections — verified accurate against the current state of `main`. Specifically confirmed accurate by direct code inspection this session:

- §14.3's governor status table (Live/disconnected/not-built) — exact match to `core/governance/governance_kernel.py` and `core/governance/memory_governor.py` (§3.2 below).
- §16 (Dependency Rules), §17 (Ownership Model), §18 (Public Contracts), §19 (Extension Points) — read as a clean, coherent, self-consistent engineering specification with no internal contradictions found.
- §20.2's K2 file manifest — the file paths listed for K2.1–K2.3 (`core/runtime/execution_context.py`, `core/workflow/runtime.py`, `core/capabilities/registry.py`, etc.) all exist exactly as named.
- §21's eight ADRs (ADR-001 through ADR-008) each correspond to a real, verifiable design decision reflected in the current code (Protocol-based `CapabilityAdapter` and `Resource`, ephemeral Workers, EventBus-subscribes-EventStream, etc.).

Two genuine problems were found, both narrow and both fixable without a redesign:

**§3.1 misdescribes the Constitution.** It states "*The Kernel Constitution defines nine laws, nine invariants*" (correct) and then adds "*Two additional laws from `PROJECT_INSTRUCTIONS.md` complement the Constitution: 10 Contract Stability, 11 Failure Containment*" (incorrect on two counts — see §3 below for the full evidence chain). This is a real inaccuracy in the second-highest-authority document in the project, not a stylistic quibble, because a reader taking this document at face value comes away believing the Constitution is an 11-law document when the Constitution itself says otherwise.

**§13 and §23 are accurate as written but are now stale relative to what's shipped since.** §13.1 correctly labels the sophisticated retrieval stack "K2 target — wire into live path" and §23 correctly scopes that wiring to K2.2. Both statements were true and precise on July 10. Neither has been revisited since K2.2 and K2.3 shipped (July 11–12) without actually doing that wiring (§3.1, §5) — so the document is not *wrong*, but it no longer tells a reader whether this is still pending, in progress, or was silently dropped. This is a currency problem, not a correctness problem, and it is exactly the kind of gap a `CURRENT_STATE.md` (§6) would close without requiring `KERNEL_ARCHITECTURE_v1.0.md` itself to be touched.

### 1.3 `ARCHITECTURE_CHANGELOG.md` — Assessment

Well-constructed as a historical record — the Timeline table and the Migration History narrative are genuinely useful and match what the archived K1/K1.5/K1.6/K1.7–K1.11 documents actually contain. One factual error, addressed fully in §3: the Timeline row for the Constitution (`ARCHITECTURE_CHANGELOG.md:20`) states it was "*later updated to 11 laws*," which did not happen. The "Known Technical Debt (at freeze)" table is accurate as of its own freeze date and is the single clearest piece of evidence that the retrieval-stack wiring was already known, Critical, and assigned before K2.2 even started — which makes its absence from the K2.2 delivery report more notable, not less (§5).

### 1.4 Recurring Inaccuracy Not Owned by Any Document: the `kernel-v1.0` Tag

`git tag -l` on the freshly-cloned repository returns nothing. This is the fourth independent confirmation of the same fact — this report, `K2_2_CUTOVER_REPORT.md` §0, and `K2_3_CAPABILITY_RUNTIME_REPORT.md` §0 all found it fresh, and the userMemory record of this project notes it as a standing, previously-flagged issue. No document in the repository *claims* the tag exists (K2.2 and K2.3's own reports correctly report its absence) — the inaccuracy lives entirely in how *session prompts* (including this session's own title, "Kernel-v1.0 — Architecture Documentation Audit...") refer to a "Kernel-v1.0" milestone as if it were already tagged and closed. Recommendation: either create the tag once K2.4 genuinely closes out the Kernel Implementation Phase, or stop the practice of naming session prompts after an unachieved milestone. This is a process note, not an architecture finding, but it has now recurred across four consecutive sessions and is cheap to fix.

---

## 2. ADR Audit

### 2.1 Complete ADR Inventory

ADR-shaped content exists in **three different places**, using **two different naming conventions**, with **no dedicated ADR directory**:

| Location | Convention | Count | Status field? |
|---|---|---|---|
| `docs/architecture/KERNEL_ARCHITECTURE_v1.0.md` §21 | `ADR-NNN` (sequential, global) | 8 (ADR-001–008) | No individual status — implicitly FINAL by the document's own "Frozen" declaration |
| `ARCHITECTURE_CHANGELOG.md` "Major Architecture Decisions" | Narrative, numbered 1–10, no `ADR-` prefix | 10 | No |
| `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` (repo root) | `ADR-K{phase}-{seq}` (session-scoped) | 1 | Yes — `DRAFT` |

### 2.2 Cross-Reference: Do the Two Numbered Lists Actually Match?

| ARCHITECTURE_CHANGELOG item | Corresponding ADR-NNN? |
|---|---|
| 1. Worker Layer — Template Method Pattern | **None assigned** |
| 2. UnifiedMemory as Production Memory Owner | **None assigned** |
| 3. EventStream — Durable Event Log | ADR-006 |
| 4. Resource as Protocol, Not ABC | ADR-007 |
| 5. ExecutionContext Replaces WorkerContext | ADR-001 |
| 6. CapabilityAdapter as Protocol | ADR-002 |
| 7. Workers Are Ephemeral | ADR-003 |
| 8. WorkflowRuntime Owns Retries | ADR-004 |
| 9. No Automatic Rollback | ADR-005 |
| 10. Retrieval Stack Consolidation | **None assigned** |
| *(not in changelog narrative at all)* | ADR-008 (Per-Type Lifecycle Enums) — only appears in the Deprecated Concepts table |

Three genuinely major decisions (#1, #2, and #10 — the last of which is the single most consequential unresolved item in this whole report) have no formal ADR number anywhere. One formally-numbered ADR (ADR-008) has no corresponding narrative entry. This is not a contradiction in the sense of two documents disagreeing about a decision's *content* — no conflicting decisions were found — but it is a real inconsistency in how decisions get indexed, and it means neither document alone is a complete decision log.

### 2.3 `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` — Assessment

This is a genuinely strong piece of engineering writing and should be used as the house template for future ADRs. It documents the current dual-governance-checkpoint pattern (`Orchestrator.handle()` + `AbstractCognitiveWorker.execute()`), explains why it's currently safe (governors are stateless per call — verified directly against `core/governance/governance_kernel.py`'s `BUG-03` fix comment), names the specific new question K2.3 encountered (should a hypothetical third `AdapterRuntime`-level check exist), and explicitly declines to answer it, presenting two credible consolidation options for K3 without picking one. **Recommendation: Keep as-is.** It follows the project's five-status ADR lifecycle correctly, remains `DRAFT` pending human review, and should be read before K2.4 starts per its own closing line — the open governance-grain question it raises is directly relevant to K2.4's stated scope (per-capability governance).

### 2.4 Per-ADR Recommendations

| ADR | Recommendation | Justification |
|---|---|---|
| ADR-001 – ADR-007 (`KERNEL_ARCHITECTURE_v1.0.md`) | **Keep.** Each is verified against live code (§1.2) and none is contradicted by anything found this session. | Frozen, accurate, no evidence of drift. |
| ADR-008 (Per-Type Lifecycle Enums) | **Keep**, but add a one-line entry to `ARCHITECTURE_CHANGELOG.md`'s "Major Architecture Decisions" list so the two indexes are complete relative to each other. | Currently invisible outside the Deprecated Concepts table and §21 itself. |
| Changelog #1 (Worker Template Method) | **Retroactively number as ADR-009**, or explicitly document it as a pre-ADR-process "foundational" decision exempt from numbering. Either is fine; leaving it unresolved is not. | Structurally identical in importance to ADR-003 (Workers Are Ephemeral), which *is* numbered. |
| Changelog #2 (UnifiedMemory as Owner) | Same treatment as above — **ADR-010** or explicit foundational-decision exemption. | Same reasoning. |
| Changelog #10 (Retrieval Stack Consolidation) | **ADR-011**, and its text should be updated to reflect that the decision remains unimplemented, not merely historical. | This is the single decision this report found still has an open implementation gap (§3.1) — it should not read as closed history. |
| `ADR-K2.3-01` | **Keep `DRAFT`. Do not promote to `REVIEW` in this session** — that decision belongs to the person who owns the repo, not to a documentation audit. | Session prompt explicitly forbids silently updating ADR decisions. |

**Naming convention recommendation:** formally adopt the split that already exists in practice rather than treating it as an accident — `ADR-NNN` (sequential) for the frozen v1.0 baseline set (already closed, will not grow), and `ADR-K{phase}-{seq}` for everything decided after the freeze. State this explicitly in a new short index file (§7) rather than leaving a future reader to infer it.

---

## 3. Architecture Consistency Matrix

Cross-referencing Constitution × Canonical Architecture × ADRs × Implementation for every area where more than one of these four sources makes a claim.

### 3.1 The Constitution Law Count — The Report's Central Finding

| Source | Claim | Verified? |
|---|---|---|
| `OCBRAIN_KERNEL_CONSTITUTION.md` (the actual file, root) | 9 laws (lines 39–87), 9 invariants (Part IV), **Status: "Draft, not Final"**, dated July 8, 2026 | **Ground truth — directly read** |
| `OCBRAIN_KERNEL_CONSTITUTION_PRESSURE_TEST.md` | *Proposes* 2 additional laws (Contract Stability, Failure Containment) as a **recommendation**, explicitly not yet applied — its own §15 "Consolidated Diff — If Approved" frames every change as pending | Correctly hedged in its own text |
| `KERNEL_ARCHITECTURE_v1.0.md` §3.1 | "Nine laws" (correct) + "two additional laws from `PROJECT_INSTRUCTIONS.md`" (**incorrect attribution** — `PROJECT_INSTRUCTIONS.md`'s actual LAW 1–5 contain no laws named "Contract Stability" or "Failure Containment"; these originate solely from the Pressure Test's unapplied proposal) | Partially wrong |
| `ARCHITECTURE_CHANGELOG.md:20` | "9-law Constitution drafted (**later updated to 11 laws**)" | **Wrong — no such update was ever applied to the Constitution file** |
| `PRODUCT.md:20` | "bound by the Kernel Constitution — **11 laws** and 9 invariants" | **Wrong** |
| `CHANGELOG.md:9` | "Kernel Constitution v1.0 — **11 laws**, 9 invariants" | **Wrong** |
| `README.md:85,91` | "OCBrain is governed by **11 laws**... see the full Kernel Constitution for all **11 laws** and 9 invariants" | **Wrong** |

**The conflict:** by the authority order this session specifies, the Kernel Constitution is rank #1 — the highest authority in the project. The Constitution, read directly, unambiguously contains nine laws and is explicitly marked Draft. Five separate documents (six counting the duplicate `ARCHITECTURE_CHANGELOG.md` copy) treat an 11-law, presumably-Final Constitution as settled fact. This is not a disagreement between roughly-equal sources that needs adjudicating — it is the entire rest of the documentation set drifting away from a source of truth that never actually changed. The most likely mechanism, reconstructed from the dates: the K1 audit (July 8) asserted "*the Constitution in this repository is the 11-law version*" based on the Pressure Test diff being "applied," but the diff was never actually committed to `OCBRAIN_KERNEL_CONSTITUTION.md` — and every document written afterward inherited that assumption without re-checking the source file.

**Recommended resolution (two options, neither executed in this session):**
- **Option A — Ratify.** Apply the Pressure Test's Consolidated Diff (its own §15) to `OCBRAIN_KERNEL_CONSTITUTION.md` for real: add Law 10 (Contract Stability) and Law 11 (Failure Containment) in the Constitution's own voice (Purpose/Reasoning/Implications/Example, matching the other nine), expand Invariant 4 to six fields as the pressure test specifies, change Status from "Draft, not Final" to reflect a real amendment record, and correct `KERNEL_ARCHITECTURE_v1.0.md` §3.1's attribution (the two laws come from the Pressure Test's own reasoning, not from `PROJECT_INSTRUCTIONS.md`). This makes the five downstream documents correct as already written.
- **Option B — Correct the downstream claims.** Leave the Constitution at nine laws, Draft, and fix `ARCHITECTURE_CHANGELOG.md`, `PRODUCT.md`, `CHANGELOG.md`, and `README.md` to say nine.

This report recommends **Option A** on the merits — the Pressure Test's two proposed laws are well-reasoned, already-cited by name in `KERNEL_ARCHITECTURE_v1.0.md`'s own engineering-implication table (§3.1, rows 10–11), and every downstream document already assumes they exist — but the choice, and the act of amending a document whose own Part VIII requires "explicit approval, recorded with `FINAL` status," is deliberately left to a human decision rather than executed here.

### 3.2 Governance — Clean, No Drift Found

| Source | RecursionGovernor | BudgetGovernor | EvolutionGovernor | MemoryGovernor | OrchestrationGovernor / AgentGovernor / ConversationGuardrails |
|---|---|---|---|---|---|
| `PROJECT_INSTRUCTIONS.md` §6.1 | *(different name)* | *(different name)* | ✓ named | ✓ named | ✓ all three named |
| `KERNEL_ARCHITECTURE_v1.0.md` §14.3 | Live | Live | Live | Exists, disconnected | Not built (K2.4) |
| `core/governance/governance_kernel.py` (verified) | `class RecursionGovernor(Governor)`, self-registered at `__init__` line 293 | `class BudgetGovernor(Governor)`, registered line 294 | `class EvolutionGovernor(Governor)`, registered line 295 | — | — |
| `core/governance/memory_governor.py` (verified) | — | — | — | `class MemoryGovernor:` **(no base class)**, singleton at line 61, never passed to `register_governor()` | — |
| Anywhere in repo (verified) | — | — | — | — | **Zero classes found by this name anywhere** |

This is the one area audited this session with **zero inconsistency** between Constitution, architecture doc, and code. `KERNEL_ARCHITECTURE_v1.0.md` §14.3's table is accurate today, not just at freeze time. The PI §6.1-vs-code naming mismatch (`OrchestrationGovernor`/`AgentGovernor`/`ConversationGuardrails` vs. `RecursionGovernor`/`BudgetGovernor`/`EvolutionGovernor`) was already identified and reconciled by the K1 audit's own migration plan, and the architecture doc resolves it correctly by using the actual implemented names as canonical. No action needed beyond what's already tracked as K2.4 scope.

### 3.3 Retrieval Architecture — Confirmed, Unresolved Gap

| Source | Claim |
|---|---|
| `KERNEL_ARCHITECTURE_v1.0.md` §13.1 | `RetrievalContextBuilder` + `GraphRAGPipeline` = "Canonical Stack (**K2 target — wire into live path**)" |
| `KERNEL_ARCHITECTURE_v1.0.md` §13.2 | `RetrievalFusionEngine` = "Legacy Stack (**live today, to be superseded**)" |
| `KERNEL_ARCHITECTURE_v1.0.md` §23 (Canonical Roadmap) | "Wire `RetrievalContextBuilder` into live path" listed explicitly under **K2.2**'s scope |
| `ARCHITECTURE_CHANGELOG.md` "Known Technical Debt (at freeze)" | "Sophisticated stack (RCB/GraphRAG) disconnected from live path — **Critical** — K2.2" |
| `core/memory/assembly.py` (verified, current `main`) | `ContextAssemblyEngine.__init__` constructs `self._fusion = RetrievalFusionEngine(memory)` — the **legacy** stack, still the live path |
| `core/memory/retrieval/context/{__init__,builder}.py` (verified) | `RetrievalContextBuilder` / `GraphRAGPipeline` referenced **only within this module** — confirmed by repo-wide grep excluding tests; zero external consumers |
| `K2_2_CUTOVER_REPORT.md` (verified) | **Zero mentions** of "RetrievalContextBuilder," "GraphRAG," or "retrieval stack" anywhere in the document |
| `K2_3_CAPABILITY_RUNTIME_REPORT.md` (verified) | Same — no mention |

Every document that describes this decision agrees with every other document. The only disagreement is between all of them and the running code. This is a clean, unambiguous, single-cause finding: **the K2.2-scoped retrieval wiring was never done, and its status went unmentioned — not deferred with a reason, simply absent — in both delivery reports written since.** Full treatment in §5.

### 3.4 Capability & Resource Model — Consistent, Honestly Narrow

`KERNEL_ARCHITECTURE_v1.0.md` §10–11 specifies `CapabilityAdapter` as a Protocol and `Resource` as a Protocol with a four-category taxonomy. `K2_3_CAPABILITY_RUNTIME_REPORT.md` implements exactly this shape, and is explicit and correct about its own narrowness: one of ten named capability types (`LLM_COMPLETION`) has real registered adapters; two of seven named resource types (`HTTPClientResource`, `ModelResource`) are implemented. Verified directly: `core/capabilities/registry.py` contains no `execute`/`invoke` method (matches the doc's "pure metadata, no execution" description), and `core/capabilities/adapters/model_router_adapter.py` wraps the pre-existing `ModelRouter` bootstrap→shadow→native promotion system rather than replacing it — a textbook instance of this project's own documented compatibility-wrapper pattern, with the sunset condition stated in the adapter's own docstring. **No inconsistency found here.** The narrowness is disclosed, reasoned (citing K1.6's "prove every field" discipline against registering speculative adapters), and correctly reflected in `KERNEL_ARCHITECTURE_v1.0.md` §18.2's framing of these as "K2 Implementation Targets," not finished products.

### 3.5 Worker Model — Consistent With Roadmap Sequencing, One Stale Downstream Doc

Only `PlannerWorker` and `MemoryCuratorWorker` exist as classes, of the eight canonical types in `PROJECT_INSTRUCTIONS.md` §7.1. `KERNEL_ARCHITECTURE_v1.0.md` §23 correctly places the remaining six (`ReActWorker`, `ReflectionWorker`, `CoderWorker`, `EvaluatorWorker`, `BrowserWorker`, `SupervisorWorker`) in the **Cognitive Phase, explicitly post-Kernel** — so their absence is not architecture debt, it is correct sequencing. The one drift found: `PRODUCT.md`'s capability table still says "CognitiveWorker | Template built | 1 subclass: MemoryCuratorWorker," which predates `PlannerWorker`'s delivery in K2.1/K2.2. Minor, easy fix, listed in §6.

---

## 4. Documentation Dependency Map

```
                         OCBRAIN_KERNEL_CONSTITUTION.md  ← HIGHEST AUTHORITY
                         (root; 9 laws; Draft, not Final)
                                    │
                    ┌───────────────┼────────────────────┐
                    │               │                     │
    _RATIONALE.md   │   _PRESSURE_TEST.md                 │
    (reconciles PI   │   (proposes 2 more laws,            │
     LAW1-5 ↔ 5 of    │    NEVER APPLIED — see §3.1)        │
     the 9 laws)      │                                     │
                       ▼                                     │
        docs/architecture/KERNEL_ARCHITECTURE_v1.0.md ◄──────┘
        (canonical engineering spec; "Frozen"; supersedes
         K1 / K1.5 / K1.6 / K1.7-K1.11 for CURRENT decisions —
         those remain readable history, not current authority)
                    │
        ┌───────────┼─────────────────────┬───────────────────┐
        ▼                                 ▼                    ▼
ARCHITECTURE_CHANGELOG.md      ADR_K2_3_01_GOVERNANCE_    K2_IMPLEMENTATION_PLAN.md
(historical decision log;      OWNERSHIP.md               (K2.1–K2.4 scope; not
 DUPLICATED at root, byte-      (standalone, DRAFT,         marked up with actual
 identical — §1.1)              post-freeze ADR)            completion status)
        │
        ▼
K2_2_CUTOVER_REPORT.md, K2_3_CAPABILITY_RUNTIME_REPORT.md   (session delivery
        (root; NOT YET ARCHIVED — §1.1)                      records; each did
                                                               its own Phase-0 audit)
                    │
                    ▼  (downstream summaries — should never be authoritative,
                        but ARE where a new reader is likely to start)
        README.md · PRODUCT.md · CHANGELOG.md
        (all three: STALE on Constitution law count — §3.1;
         PRODUCT.md also stale on worker count — §3.5)

PROJECT_INSTRUCTIONS.md ── parallel operational-rules track, referenced by
   (root; DUPLICATED at       KERNEL_ARCHITECTURE_v1.0.md §3.1 with an
    docs/architecture/,       incorrect attribution (§3.1) — otherwise
    byte-identical)           not in conflict with anything else audited

docs/archive/{kernel,research}/*  ── correctly superseded, pre-freeze
docs/archive/{STATUS,REALITY_AUDIT,ARCHITECTURE_COMPLIANCE_REPORT,           
   ARCHITECTURE_ALIGNMENT_REPORT,MINIMUM_ARCHITECTURE_PATH,
   RECOVERY_REPORT,BUG_FIXES}.md  ── correctly superseded, pre-Constitution
   (all reference OCBRAIN_FUTURE_ARCHITECTURE.md / v4.3.4-era state;
    none conflict with current architecture; none need re-analysis)

docs/reports/{SESSION4,SESSION4B,SESSION4C,ARCHITECTURE_HARDENING}.md
   ── correctly archived session records, pre-Kernel-phase
```

**Reading this map:** there is exactly one real authority chain (Constitution → `KERNEL_ARCHITECTURE_v1.0.md` → `ARCHITECTURE_CHANGELOG.md`/ADRs), and it is sound except at the single point flagged in §3.1. The failure mode visible in this map is not "competing architectures" — it's **downstream summary documents (README/PRODUCT/CHANGELOG) drifting from a source that itself drifted once, upstream of them, and nobody re-checked the original.** Fixing the Constitution question (§3.1, one decision) fixes five of the six inconsistent claims found this session as a direct consequence.

---

## 5. Remaining Architecture Debt

Every item below is directly evidenced in §1–4; none is asserted without a citation.

### Critical — must be resolved before this session's own stated objective (one coherent, contradiction-free baseline) can be considered met, and before K2.4/K3 proceed

| Item | Evidence | Why Critical |
|---|---|---|
| Retrieval stack still unwired | §3.3 — direct code citation, zero external consumers of the canonical stack | Was already Critical at freeze (per the project's own severity rating), assigned to K2.2, and has now silently survived two subsequent delivery reports without acknowledgment. This is the textbook "build without wiring" failure this project's own research has named three times before (K1, K1.5, and now a fourth instance). |
| Constitution law-count contradiction | §3.1 — six documents, one ground-truth file | Directly blocks this session's Primary Objective of "no contradictory ADRs, no duplicated architectural decisions." The project's own highest-authority document is currently misdescribed by everything downstream of it. |
| K2.4 has not started | §3.2 — zero classes found for `OrchestrationGovernor`/`AgentGovernor`/`ConversationGuardrails`; `MemoryGovernor` unchanged | Not "debt" in the sense of something done wrong — but it is the direct reason K3 cannot be assessed as ready (§8), and the session prompt's framing skips over it entirely. |

### High — should be resolved before K3 begins

| Item | Evidence |
|---|---|
| ADR indexing inconsistency (two numbering conventions, three decisions unindexed) | §2.2 |
| No dedicated ADR/decisions directory | §2.1 — confirmed via repo-wide search |
| PI §18.4.2/§18.5 documentation-infrastructure files (`CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, `KNOWN_ISSUES.md`, `PROJECT_INDEX.md`, `MEMORY_ARCHITECTURE.md`) still do not exist anywhere in the repository | Confirmed via repo-wide search this session |
| New root-level scattering (`ADR_K2_3_01`, `K2_2_CUTOVER_REPORT.md`, `K2_3_CAPABILITY_RUNTIME_REPORT.md`, `K2_IMPLEMENTATION_PLAN.md`, duplicate `ARCHITECTURE_HARDENING_SESSION_REPORT.md`) | §1.1 |

### Medium — can be resolved during K3 or in parallel

| Item | Evidence |
|---|---|
| `PRODUCT.md`/`CHANGELOG.md` stale relative to K2.1–K2.3 (worker count, no mention of `CapabilityRegistry`/`AdapterRuntime`) | §3.5 |
| Duplicate `PROJECT_INSTRUCTIONS.md` and `ARCHITECTURE_CHANGELOG.md` (root + `docs/architecture/`), no sync mechanism | §1.1 |
| `K2_IMPLEMENTATION_PLAN.md` not marked up with per-milestone completion status | §1.2 |
| `KERNEL_ARCHITECTURE_v1.0.md` §23's roadmap block doesn't reflect that K2.1–K2.3 are done | §1.2 |
| ADR-K2.3-01's own open question (per-request vs. per-adapter-attempt governance grain) — already flagged by that ADR itself as a K3 input, not new debt | §2.3 |

### Low — historical or cosmetic

| Item | Evidence |
|---|---|
| Only 1 of 10 named capability types has real adapters | §3.4 — honestly scoped, not a gap in the sense of missing expected work |
| Only 2 of 7 named resource types implemented | §3.4 — same |
| Only 2 of 8 canonical worker types exist | §3.5 — correctly sequenced as post-Kernel, not debt |
| `kernel-v1.0` tag still doesn't exist, still referenced as if it does in session-prompt titles | §1.4 |

---

## 6. Documentation Cleanup Plan

**Keep, unchanged:**
`KERNEL_ARCHITECTURE_v1.0.md` (fix §3.1 only — see below), `ARCHITECTURE_CHANGELOG.md` (fix the Constitution timeline row and Retrieval-Stack-Consolidation entry only), the Constitution/Rationale/Pressure-Test trio (correctly ordered and internally honest about their own draft status), `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` (stays `DRAFT`), everything already in `docs/archive/` and `docs/reports/` (all correctly superseded, confirmed this session, no re-analysis needed).

**Fix (content correction, not restructuring — requires the Option A/B decision in §3.1 first):**
- `OCBRAIN_KERNEL_CONSTITUTION.md` — either amend to 11 laws for real (Option A) or leave at 9 and correct everything downstream (Option B).
- `KERNEL_ARCHITECTURE_v1.0.md` §3.1 — correct the "from `PROJECT_INSTRUCTIONS.md`" attribution regardless of which option is chosen; the two laws (if adopted) come from the Pressure Test.
- `ARCHITECTURE_CHANGELOG.md:20` — correct the Constitution timeline row to match whichever option is chosen.
- `PRODUCT.md:20`, `CHANGELOG.md:9`, `README.md:85,91` — same.
- `PRODUCT.md`'s capability table — update worker count (2, not 1) and add `CapabilityRegistry`/`AdapterRuntime` as a K2.3-delivered row.

**Merge:** none required — the document set is otherwise well-separated; no redundant content found beyond the exact-duplicate files below.

**De-duplicate (pick one canonical location, remove or stub the other):**
- `PROJECT_INSTRUCTIONS.md`: keep `docs/architecture/` copy as canonical (consistent with this session's own framing that canonical architecture lives there); root copy becomes a one-line pointer or is removed.
- `ARCHITECTURE_CHANGELOG.md`: same treatment.
- `ARCHITECTURE_HARDENING_SESSION_REPORT.md`: keep `docs/reports/` copy; remove root duplicate.

**Move (relocate, no content change):**
- `ADR_K2_3_01_GOVERNANCE_OWNERSHIP.md` → new `docs/architecture/decisions/` directory (§7).
- `K2_2_CUTOVER_REPORT.md`, `K2_3_CAPABILITY_RUNTIME_REPORT.md` → `docs/reports/`, matching the existing `SESSION4*`/`ARCHITECTURE_HARDENING` precedent.
- `K2_IMPLEMENTATION_PLAN.md` → `docs/architecture/`, as a planning companion to `KERNEL_ARCHITECTURE_v1.0.md` (or `docs/reports/` once K2.4 completes and it becomes purely historical — either is defensible; pick one and state it).

**Create (genuine gaps, not previously scheduled or newly invented — all are pre-existing PI §18.5 commitments):**
- `docs/architecture/decisions/` directory + a short `INDEX.md` inside it, formally documenting the `ADR-NNN` (frozen baseline) vs. `ADR-K{phase}-{seq}` (post-freeze) split from §2.4.
- `CURRENT_STATE.md` — would have made a meaningful fraction of this session's own investigative work (§1.2, §3.3) unnecessary if it already existed and were kept current.
- `KNOWN_ISSUES.md` — `ARCHITECTURE_CHANGELOG.md`'s "Known Technical Debt" table is a reasonable seed for this but isn't positioned or named as the living document PI §18.4.2 calls for.

**None of the above are executed in this session** — per the session's explicit constraints, this is a plan for a human or a dedicated follow-up session to act on, not a set of changes applied silently here.

---

## 7. Updated Canonical Documentation Structure

```
/OCBRAIN_KERNEL_CONSTITUTION.md                 (stays at root — highest authority, most visible)
/OCBRAIN_KERNEL_CONSTITUTION_RATIONALE.md
/OCBRAIN_KERNEL_CONSTITUTION_PRESSURE_TEST.md
/README.md  /PRODUCT.md  /CHANGELOG.md          (stay at root — public-facing entry points)

/docs/architecture/                              ← canonical engineering specification only
    KERNEL_ARCHITECTURE_v1.0.md                     (single copy — root duplicate removed)
    ARCHITECTURE_CHANGELOG.md                       (single copy — root duplicate removed)
    K2_IMPLEMENTATION_PLAN.md                       (moved from root)
    decisions/                                      ← NEW
        INDEX.md                                    (documents the two-convention split, §2.4)
        ADR-001..008 stay embedded in KERNEL_ARCHITECTURE_v1.0.md §21 (frozen baseline —
            do not extract; extraction would be a needless restructure of a frozen document)
        ADR-K2.3-01-governance-ownership.md         (moved from root, renamed for consistency)
        (future post-freeze ADRs land here directly, not at root)

/docs/reports/                                   ← session delivery records, chronological
    SESSION4_REPORT.md / SESSION4B_REPORT.md / SESSION4C_REPORT.md
    ARCHITECTURE_HARDENING_SESSION_REPORT.md        (single copy — root duplicate removed)
    K2_2_CUTOVER_REPORT.md                          (moved from root)
    K2_3_CAPABILITY_RUNTIME_REPORT.md               (moved from root)
    ARCHITECTURE_CONSOLIDATION_AND_K3_READINESS_REPORT.md   (this document)

/docs/archive/                                   ← unchanged, already correctly organized
    kernel/     (K1, K1.5, K1.6, K1.7-K1.11, Draft 0.9 — pre-freeze history)
    research/   (external repo studies, FUTURE_ARCHITECTURE — pre-Constitution research)
    *.md        (pre-Constitution v4.3.x-era audits — STATUS, REALITY_AUDIT, etc.)

/PROJECT_INSTRUCTIONS.md → docs/architecture/PROJECT_INSTRUCTIONS.md   (single copy — pick
    docs/architecture/ as canonical per this session's own framing; root becomes a stub
    pointing there, or is removed if nothing external links to the root path)

/CURRENT_STATE.md          ← NEW, root, per PI §18.5 — the single place "what's actually
                              done right now" is answered, so sessions like this one don't
                              have to reconstruct it from three reports and a code audit
/KNOWN_ISSUES.md           ← NEW, root, per PI §18.5 — supersedes/formalizes ARCHITECTURE_
                              CHANGELOG.md's "Known Technical Debt" table as the living version
```

**Ownership rule going forward, stated explicitly rather than left implicit** (this is the actual root cause behind §1.1's "new scattering"): `docs/architecture/` holds only the *current, canonical* specification and its direct decision history. `docs/reports/` holds *session-level* delivery records — the moment a session report is written, it belongs in `docs/reports/`, not at root, from the start. This report follows that rule itself (§ header — written directly into `docs/reports/`, not root).

---

## 8. K3 Readiness Assessment

### Verdict: **NOT READY**

Three independently-sufficient reasons, any one of which alone would justify this verdict:

**1. The canonical architecture's own roadmap places K3 after K2.4, and K2.4 has not started.** `KERNEL_ARCHITECTURE_v1.0.md` §23 states plainly: "K3 — Kernel Validation & Compliance Audit (**post-implementation**)," where "implementation" explicitly means K2.1 through K2.4 as a set. Verified directly this session: `OrchestrationGovernor`, `AgentGovernor`, and `ConversationGuardrails` do not exist as classes anywhere in the repository, and `MemoryGovernor` remains exactly as disconnected as `KERNEL_ARCHITECTURE_v1.0.md` §14.3 already documents it. This is not a documentation gap — it is unstarted implementation work that the architecture itself already scoped as a prerequisite.

**2. A Critical, K2.2-scoped deliverable was never completed and has gone unacknowledged across two subsequent sessions.** The live retrieval path (`ContextAssemblyEngine`) still constructs `RetrievalFusionEngine` — the stack `KERNEL_ARCHITECTURE_v1.0.md` §13.2 itself calls "legacy... to be superseded." `RetrievalContextBuilder`/`GraphRAGPipeline` have zero production consumers. This was rated Critical at architecture freeze, explicitly assigned to K2.2, and is mentioned in neither the K2.2 nor K2.3 delivery report. A compliance audit (K3's stated purpose) running today would either need to re-discover this gap from scratch — repeating this session's own work — or K3 would need to be scoped narrowly enough to skip it, which contradicts K3's own stated purpose of validating the *whole* kernel.

**3. This session's own Primary Objective — one coherent, internally consistent, evidence-backed architecture baseline — is not yet met.** Six documents (§3.1) currently assert facts about the project's own highest-authority document that the document itself does not support. A "clean foundation for K2.4 and K3," as this session was chartered to produce, cannot be said to exist while the Constitution's actual law count is in dispute across the repository.

### What Would Change This Verdict

None of the above requires new architecture, a redesign, or speculative work — every item has a scoped, already-understood fix:

- Resolve §3.1 (a documentation decision — Option A or B, §3.1 — plus five downstream edits).
- Wire `RetrievalContextBuilder`/`GraphRAGPipeline` into `ContextAssemblyEngine`, replacing the `RetrievalFusionEngine` construction, with the A/B comparison `KERNEL_ARCHITECTURE_v1.0.md` §13.2 already specifies before cutover.
- Complete K2.4 (`OrchestrationGovernor`, `AgentGovernor`, `ConversationGuardrails`, `MemoryGovernor` interface reconciliation) — already fully scoped in `KERNEL_ARCHITECTURE_v1.0.md` §20.2 and `K2_IMPLEMENTATION_PLAN.md`.

Once those three are done, this project would be in a genuinely strong position to begin K3 — the governance layer (§3.2) and capability/resource layer (§3.4) audited this session show no drift and no hidden gaps, which is real evidence that the underlying engineering discipline (Phase-0 audits, honest scoping, compatibility-wrapper documentation) is working. The gaps found here are specific and closable, not signs of a foundation that needs to be rethought.

---

## 9. Closing Synthesis

**What this session confirms works:** the Phase-0-reality-audit discipline this project has practiced since K1 is now self-sustaining — K2.2 and K2.3 each independently re-verified the repository from scratch rather than trusting their own session prompts, and both caught real inaccuracies (the `kernel-v1.0` tag, K2.1's "LIVE" claim) before those inaccuracies could compound. That discipline is exactly why this report could be written with this level of precision in one session rather than needing its own multi-session excavation.

**What this session found that wasn't previously visible in one place:** the retrieval-stack gap (§3.3) existed in three separate documents' worth of evidence — the architecture spec, the changelog's debt table, and two delivery reports' silence — but nothing had connected those three data points into a single "this is still open" statement until this session did. The Constitution law-count drift (§3.1) is similar: each individual document's claim looked like a reasonable inheritance from the one before it, and no single document is obviously wrong in isolation — the error only becomes visible by reading the Constitution file itself against everything that cites it, which is precisely the kind of check a documentation consolidation session exists to perform.

**One honest limitation of this report:** it verifies architecture and documentation consistency, per its mandate, and deliberately does not re-run the test suite or otherwise re-validate K2.1–K2.3's functional correctness (the session prompt's own constraints scope this to architecture readiness, not implementation work). The 47-file test suite present in `tests/` — including dedicated coverage for `test_execution_runtime.py`, `test_workflow_runtime.py`, `test_capabilities.py`, `test_context_builder.py`, and `test_graphrag.py` — was not executed this session. K2.2's and K2.3's own reports both report full regression-suite passes at time of delivery; this report neither confirms nor disputes that, since re-running it was outside this session's scope.

**If I were chief architect:** the single highest-leverage action available right now is not K2.4 — it's resolving §3.1. Everything else found this session either follows directly from it (five of six drifted documents) or is independent, already-scoped, already-understood implementation work (the retrieval wiring, K2.4 itself) that doesn't need another audit to clarify, only execution. A documentation-consolidation session's job is to leave behind a baseline precise enough that the next session doesn't have to re-derive it — that baseline now exists in this report, but it will only stay true if `CURRENT_STATE.md` (§6, §7) is actually created and kept current going forward, rather than this becoming the fifth document a sixth session has to reconcile against.

---

*Report complete. No code modified. No architecture redesigned. All recommendations in §3.1, §6, and §7 require explicit decision and action outside this session, per the session's own constraints.*
