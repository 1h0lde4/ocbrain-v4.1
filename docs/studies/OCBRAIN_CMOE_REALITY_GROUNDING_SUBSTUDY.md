# OCBrain C-MoE — Reality-Anchored Planning Sub-Study

> **Renamed Aug 29, 2026**, for the same reason and at the same time as its parent document, `OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md` — see that file's own correction note. "K4.3" was never an authoritative milestone name; this remains valid post-Kernel-freeze C-MoE research.


**Status:** Research complete. Feeds into `OCBRAIN_K4_3_CMOE_ARCHITECTURE_STUDY.md` (§4, §6 amended; incorporated into the MVP/target definitions there). Not implemented.
**Date:** August 28, 2026
**Relationship to the main study:** This is a focused sub-study, not a parallel architecture. Every contract and boundary defined here is expressed in the main study's own vocabulary (Evidence/Knowledge/Decision from its §55, the eligibility funnel from its §20, the Context Compiler boundary from its §67) rather than introducing a second vocabulary. Where this document reaches a conclusion that changes the main study, it says so explicitly rather than leaving two documents quietly disagreeing.

---

## 0. Question under study

> Should C-MoE engage in a bounded cognitive discussion with the Planner before planning begins, so the Planner plans against a current, evidence-grounded representation of reality rather than in a vacuum?

**[FACT, newly verified for this sub-study]** The vacuum is real, not hypothetical. `core/cognitive/planner.py::plan(request: PlannerRequest, registry: CapabilityRegistry, ...)` takes exactly two real inputs: the request (goal, constraints, hints) and the `CapabilityRegistry` (static, declared capability metadata — what capability *types* exist, not what is currently true about this task, project, or expert health). Nothing about prior WorkGraph outcomes, existing project artifacts, prior failed attempts at the same goal, or current expert health reaches Planner today. This is not a defect in K4.2 — none of that state existed for Planner to consult until this study's own Memory Scope Model and WorkGraph invented it — but it is a genuine, confirmed gap that something must address once that state *does* exist.

---

## 1. Verdict

**Adopt with modification.**

Neither the original hypothesis (a rich bidirectional C-MoE↔Planner dialogue, Option D) nor outright rejection survives scrutiny. The evidence supports a **thin, conditional, single-round, read-only, strictly-factual** grounding step before planning, plus a **feasibility pass reusing C-MoE's own eligibility machinery** against the completed draft plan — not a new standing "reality" authority, and not a negotiation.

---

## 2. Working through the five architectures

| Option | Verdict | Why |
|---|---|---|
| **A. Pure pre-planning consultation** | Half-right | Solves the vacuum problem but, alone, cannot catch infeasibility introduced *by* the plan's own structure (a step ordering that only becomes infeasible once steps are sequenced) |
| **B. Pure post-planning feasibility check** | Half-right | Catches structural infeasibility but leaves Planner drafting the *first* version blind to reusable prior work, silently duplicating it |
| **C. Both** | **Adopted** | The two failure modes above are independent and both real; one lightweight mechanism does not cover both |
| **D. Rich bounded dialogue** | **Rejected** | An iterative Planner↔C-MoE loop is functionally a recursive agent loop with two participants instead of one. `PROJECT_INSTRUCTIONS.md` §5 names "recursive uncontrolled agent loops" as a forbidden pattern outright; making the loop "bounded" (a fixed round cap) does not remove the harder problem this option introduces on its own — an explicit termination *and convergence* condition ("has the dialogue actually settled, or did we just run out of rounds mid-disagreement") that this study could not derive a principled answer for. A fixed-round dialogue that times out mid-disagreement is worse than a single-round exchange that is honest about not resolving everything, because the former masks non-convergence as apparent agreement. |
| **E. A separate standing Reality/State layer** | **Rejected, as a new component** — its *function* is adopted, folded elsewhere | Fails the main study's own Kernel Admission Test (its §44, Gate 1): reality acquisition is retrieval-and-filtering over Memory (§45 of the main study) and capability health (its §20); it is not a new, irreducible coordination responsibility. A fourth standing authority here duplicates Context Compiler (main study §67) before that milestone even exists, and duplicates C-MoE's own eligibility funnel. Two components solving the same problem is precisely the "duplicate authority" failure mode the main study spends its §33, §85 and §87 resolving elsewhere — repeating that mistake here to solve a different problem would be inconsistent. |

**The failure mode this stress-test surfaced that the original hypothesis did not anticipate:** treating "grounding" and "strategy" as points on the same conversational channel is what makes Option D dangerous. The moment C-MoE's grounding output contains a recommendation ("given this, you should do A→B→C") rather than a fact ("artifact Z already exists, expert E is degraded"), C-MoE has quietly become a second Planner — the exact failure the main study's §4 and this project's whole design already guard against. The fix is not a smarter dialogue protocol; it is a hard content restriction on what grounding is allowed to say: **facts and evidence only, never a plan sketch.** This restriction is what makes a single round sufficient — a dialogue is only "needed" if the first round is allowed to be strategically incomplete, and it need not be if its content is disciplined to facts.

---

## 3. What "reality" means, precisely, and what it excludes

**[DECISION]** Included, because each has a concrete grounding consumer:

```
existing project artifacts & verified facts     (Project Memory, main study §45)
prior attempts at this or a materially similar goal, and why they failed   (WorkGraph history, once §16/§37 exist)
current expert/capability health (coarse: available / degraded / unavailable)  (main study §20's eligibility filter, reused)
active project-level constraints                (Project Memory)
relevant global user preferences                (Global User Memory, §45, only if the goal-matching signal is strong — see §5 below)
remaining execution/cognitive budget            (existing ExecutionBudget + main study §43)
```

**[DECISION]** Explicitly excluded, because including them either has no grounding consumer or actively risks contamination:

```
full expert internals (ExpertDescriptor's operational fields, main study §17) — Planner needs "is X available," never X's cost model or contract schema; that belongs to Plan Compiler/C-MoE routing, not grounding
other projects' memory                           — main study §56 already forbids this unconditionally
other tasks' in-flight WorkGraph state            — main study §40 already forbids this unconditionally
raw retrieved external content                    — this is a routing-time/execution-time concern (main study §51 places it lowest-precedence); surfacing it at grounding time adds prompt-injection surface for no planning benefit
speculative/derived "insights" not yet promoted to Knowledge — grounding may only surface Evidence and promoted Knowledge (main study §55's object model), never an un-promoted inference, or grounding becomes a backdoor around the promotion pipeline (main study §47)
```

**[INFER]** The line is not "everything true about the world" vs. "nothing" — it is "everything **already governed and scoped** as Evidence or Knowledge for *this* task/project" vs. "anything that would require grounding to newly acquire authority it does not already have." Grounding is a **read** through existing scope boundaries, never a bypass of them.

---

## 4. Observation vs. interpretation

**[DECISION]** Every fact in a Reality Brief (§6) carries a trust tag drawn from the main study's own Evidence/Knowledge distinction (§55), not a new taxonomy:

```
VERIFIED_RESULT     — Verification-confirmed (rare, until §77 of the main study ships)
PROMOTED_KNOWLEDGE  — passed the promotion pipeline (main study §47)
RAW_EVIDENCE        — un-promoted, task-scoped observation (a tool result, a prior attempt's log)
ASSUMPTION          — Planner's own prior assumption, being re-surfaced for revalidation, not a new claim
STALE               — flagged as such per the main study's §52 freshness policy, shown anyway with the flag, not silently dropped
```

**[DECISION]** A Reality Brief must never present an `ASSUMPTION` or `RAW_EVIDENCE` item with the same visual/structural weight as `PROMOTED_KNOWLEDGE` or `VERIFIED_RESULT` — this is the direct, concrete answer to the sub-study's own concern ("a Planner should not unknowingly treat 'C-MoE inferred X' as equivalent to 'the runtime verified X'"). Enforced by making trust tag a required, non-optional field on every Reality Brief entry, not a convention.

---

## 5. Reality Snapshot and staleness

**[DECISION]** A `RealitySnapshot` is adopted, but as a thin wrapper, not a new heavyweight artifact type — it reuses the main study's existing versioning pattern (its §11 Goal ancestry, §36 `plan_version`) rather than inventing a fourth kind of version number:

```python
@dataclass
class RealitySnapshot:
    snapshot_id: str
    task_id: str                    # scope-bound, per main study §39-40 — never cross-task
    captured_at: datetime
    evidence_refs: List[str]        # Evidence/Knowledge object IDs, not embedded copies
    assumptions: List[str]
    validity_window: Optional[timedelta] = None
```

**[DECISION]** `ExecutionPlan` (main study §4) gains one optional field, `based_on_snapshot: Optional[str]`, mirroring `caused_by`'s existing pattern exactly (same file, same author, same convention — not a new one). **[DECISION]** Staleness detection reuses the main study's §36 mechanism verbatim: a plan whose `based_on_snapshot` no longer matches the current snapshot state when execution is about to begin is treated exactly like a late-stale-result — flagged, not silently trusted, and re-grounded only if the mismatch is material (a changed constraint, a newly-unavailable expert), not on every trivial drift. **[INFER]** This is the single cleanest piece of evidence that this sub-study's contract *belongs inside* the main study rather than beside it: it did not need a new versioning concept, only one new field reusing an existing pattern twice already established there.

---

## 6. The grounding call itself — rejecting "dialogue," adopting "request/response"

**[DECISION]** Not `get_reality()` (too thin — loses the relevance-filtering the sub-study rightly insists on) and not a dialogue (§2). One request, one response:

```
Planner (or the Orchestrator, on Planner's behalf) issues:
    RealityGroundingRequest { goal, project_id?, task_id, trigger_reason }
          ↓
"Reality Assembly" (a thin function — see §8 on ownership) returns:
    RealityBrief { snapshot_id, relevant_prior_work: [ArtifactRef],
                    known_blockers: [...], expert_availability_summary: [...],
                    applicable_constraints: [...], relevant_prior_failures: [...] }
          ↓
Planner plans against RealityBrief + its existing inputs (goal, constraints, CapabilityRegistry)
          ↓
Plan Compiler produces a draft ExecutionPlan
          ↓
C-MoE eligibility funnel (main study §20, reused, not duplicated) runs once against the
draft plan's declared capability_types, using expert_availability_summary already in hand
          ↓
FeasibilityResult { plan_id, feasible: bool, blocking_issues, degraded_warnings }
          ↓
feasible → execution begins ; not feasible → Planner revises (a new plan VERSION, main
                                                study §11 — not a new dialogue round)
```

**[INFER]** This resolves the sub-study's own termination-condition question (§6 of the source prompt) by making it not arise: there is nothing to terminate, because there is no loop. A revision after an infeasible `FeasibilityResult` is architecturally identical to any other replan (main study §8) — it does not need a separate mechanism, only a separate *trigger reason* on the same mechanism.

---

## 7. When grounding runs at all — conditional, not mandatory

**[DECISION]** Triggered by any of, evaluated cheaply before Planner is invoked:

```
task belongs to a Project (main study §44) with non-empty Project Memory
task's own phrasing references continuation ("continue," "the previous attempt," "like before")
capability discovery's candidate set includes any expert with resource_cost above a small
    fixed threshold, or with a permission scope broader than read-only
task is itself a replan (main study §8) — in which case grounding already happened
    implicitly via PlanRealityFeedback and this mechanism is correctly skipped, not duplicated
```

**[DECISION]** Otherwise skipped outright — not run in a "cheap mode," genuinely skipped — for the simple, no-project, no-side-effect, single-turn case (the sub-study's own §23 concern about unconditional overhead is real, and a partial/cheap grounding call still costs a memory query and a round-trip for a case, e.g. "what's 2+2," where the answer is provably always empty). **[INFER]** This trigger list is deliberately conservative (biased toward skipping) because a false negative here (skipping grounding when it would have helped) degrades gracefully — Planner behaves exactly as K4.2 does today, which is the current, already-shipping behavior — while a false positive (grounding when unneeded) has a real, paid latency/token cost on every trivial request. Asymmetric failure cost justifies a conservative trigger.

---

## 8. Ownership matrix

| Responsibility | Owner | Note |
|---|---|---|
| Reality acquisition (running the read-only queries) | **Reality Assembly** — a thin function, explicitly *not* a new standing component | A pre-Context-Compiler stub; superseded in place once main study §67's Context Compiler ships, without Planner's or C-MoE's call sites changing |
| Curating acquired facts into a RealityBrief | Reality Assembly | Filters by relevance to the specific goal, per §3's inclusion list — never a context dump |
| Reality interpretation for feasibility purposes | **C-MoE**, via its existing eligibility funnel (main study §20) | Reused, not duplicated — this is the one place this sub-study gives C-MoE new work, and it is work C-MoE already has to do at execution time regardless |
| Memory retrieval | **Memory** (main study §45), queried *by* Reality Assembly | Unchanged from the main study |
| Strategic planning | **Planner**, unchanged | Consumes RealityBrief as an additional input; does not delegate strategy to it |
| Plan validation (feasibility) | **C-MoE** | See above |
| Expert selection (which expert runs, at execution time) | **C-MoE** (main study §17-24), unchanged | Grounding's `expert_availability_summary` is coarse (available/degraded/unavailable per capability type) — never a routing decision itself |
| Execution | **ExecutionRuntime**, unchanged | — |
| Reality feedback (post-execution) | **C-MoE**, via Plan Reality Feedback (main study §8) | Unchanged — this sub-study only adds a *pre*-execution counterpart, it does not touch the existing post-execution one |
| Goal mutation | User-triggered (main study §10) | Unchanged |

**[INFER]** No row in this table names a component this sub-study invents. Every owner is either an existing K4.2 component, a component the main study already designed (C-MoE, Memory), or an explicitly-labeled stub for a not-yet-built future milestone (Context Compiler). This is the concrete demonstration that Option E (a new standing layer) was correctly rejected in §2 — the table has no row for it because no row needed one.

---

## 9. Failure and mutation interaction

**[DECISION]** This sub-study introduces no new failure-handling authority — every case below routes through a main-study mechanism already defined:

| Case | Handling |
|---|---|
| Grounding finds `INSUFFICIENT_INFORMATION` | Not a new state — resolves to the main study's `NeedInformation` outcome (§30) applied *before* routing exists yet, escalated to the user (§82) exactly as it would be mid-execution |
| Reality changes between grounding and execution start | §5's staleness check; re-ground only if material |
| User mutates the goal after a Reality Brief was issued | Ordinary task mutation (main study §10) — the Brief becomes part of the superseded plan version's provenance, not silently discarded |
| Grounding itself needs active information-gathering (a search) | Permitted, but strictly `read_only` permission scope (main study §64's `PermissionScope`, reused) — grounding may look, never act; this is enforced the same way any other read-only capability invocation is, not by a new rule |
| Feasibility check fails after planning | Triggers a new plan version (main study §11), not a dialogue round (§6) |

---

## 10. Isolation and memory interaction

**[DECISION]** No new isolation rule — `RealitySnapshot.task_id` (§5) inherits the main study's existing hard scoping (§39-40, §56) directly. A grounding call for Discussion C in Project A may read Project A's Project Memory (main study §44) and relevant promoted Reusable Evidence (§45), exactly as any other in-project read would; it may never read Project B's memory, another task's live WorkGraph, or another discussion's temporary assumptions, for exactly the reasons already established there. This sub-study adds no exception to those boundaries.

---

## 11. K4.3 scope classification

```
K4.3 mandatory:
    RealityBrief contract (§6) · RealitySnapshot + ExecutionPlan.based_on_snapshot (§5)
    Conditional trigger policy (§7) · Feasibility pass reusing C-MoE's eligibility funnel (§6, §8)
    Read-only permission enforcement for grounding calls (§9)

K4.3 supporting infrastructure (already in the main study's own K4.3 scope, reused here):
    Project Memory (main study §45) · C-MoE eligibility funnel (§20) · Plan versioning (§11)

Future / deferred:
    Full Context Compiler (main study §67) — Reality Assembly is its stub, not its replacement
    Any strategic content in grounding output — permanently out of scope, not merely deferred (§2)
    Proactive "here's a better approach" suggestions — Proactive Optimization/Fable territory (main study §74)

Unnecessary (rejected outright, not deferred):
    A standing Reality/State Layer component distinct from Memory + C-MoE + Context Compiler (§2, Option E)
    An iterative bounded Planner↔C-MoE dialogue (§2, Option D)
    Mandatory grounding for every request regardless of complexity (§7)
```

---

## 12. Open questions

- Whether `expert_availability_summary`'s granularity (available/degraded/unavailable per capability *type*) is coarse enough to avoid leaking operational `ExpertDescriptor` detail into Planner, or whether even that is too much — this study could not settle it without an implementation to observe, and flags it for the packet that builds Reality Assembly rather than guessing.
- Whether the conditional-trigger heuristics in §7 should themselves be tunable policy (main study §19's Policy/Mechanism split) from the start, or hard-coded initially and only split out once real trigger-accuracy data exists — this study leans toward the latter (avoid the K4.2 `description`-overload lesson of building flexibility before there is evidence it is needed) but does not treat this as settled.
- Whether a `FeasibilityResult` that is merely `degraded_warnings`-only (feasible, but with caveats) should be surfaced to the user before execution begins, or only logged — this is a UX question this architecture study is not positioned to answer and is left to product judgment.

---

## 13. Recommendation to the main K4.3/C-MoE study

Amend the main study as follows, rather than treating this as a competing document:

1. **§4 (Planner vs C-MoE vs Execution)** gains one clause: Planner's "before any step has executed" grounding is no longer limited to static `CapabilityRegistry` metadata — it now also consumes a `RealityBrief` (this document, §6), assembled by a thin Reality Assembly function that is explicitly *not* C-MoE and explicitly a stand-in for the not-yet-built Context Compiler (main study §67).
2. **§6 (Closed-Loop Runtime Model)** gains a pre-loop step: `Goal → [conditional] Reality Assembly → RealityBrief → Planner → Plan → [C-MoE feasibility pass, reusing §20] → C-MoE realization loop (unchanged)`.
3. **§4's `ExecutionPlan` field list** gains `based_on_snapshot: Optional[str]` (this document, §5), following the exact convention `caused_by` already established.
4. **§93 (Minimum Viable K4.3)** should include the conditional grounding call and the feasibility pass as MVP-scope, not Full-Target — both are cheap (reusing existing/planned mechanisms, per §8's ownership table above) and directly close a confirmed, evidenced gap (§0) rather than adding speculative scope.
5. **No other section of the main study requires amendment.** In particular, §17-30 (expert model, routing, outcome contract), §31-43 (runtime state machine, durability, identity), and §44-58 (memory scope model) are all consumed by this mechanism as-is, unchanged — this sub-study is an additional *consumer* of the main study's existing contracts, not a revision of them.
