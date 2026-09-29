# ADR-KERNEL-07 — Creative Content-Anchor Gate (first narrow slice toward Intent Sufficiency)

**Status:** PROPOSED — **not merge-ready: blocked on D-5** (§10). The code on the work
branch is a reviewable *proposal*, disabled by default
(`[runtime] creative_anchor_gate_enabled = false`). Its detector, policy rule, events
and tests are reusable under every D-5 outcome; its *placement* is not (§10). Decisions
D-1..D-5 (§6) are open and must be resolved by Moncif before this ADR can be ACCEPTED.
**Date:** Sept 28, 2026 (revised after architecture review, same day)
**Governing study:** `docs/studies/OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md`
(study only; unmodified copy). **Series:** next after ADR-KERNEL-06.

Evidence tags: `[FACT]` verified in live source this session (`main` @ `2520cb4`),
`[INFER]` reasoning from verified facts, `[PENDING]` open.

> **Naming and claim discipline.** This ADR does **not** implement Intent
> Sufficiency. It implements a *narrow experimental detector* for one class of
> under-specification and the plumbing to short-circuit on it. The earlier draft
> was titled "Intent Sufficiency Gate"; that over-claimed and risked freezing a weak
> heuristic as the canonical definition of sufficiency. The detector, flag, event
> and governor key are therefore named for what they measure.

## 1. Problem (unchanged, `[FACT]`)

Nothing between raw request text and a committed `ExecutionPlan` asks whether the
request is sufficiently specified. `interpret_request()` (`core/cognitive/intent.py`)
computes `Intent.confidence` and `complexity_estimate` and never branches on either.
`ClarificationPolicy` measures capability-match confidence and is exempted for
general-purpose-only plans (ADR-K4.2-H-13). `Orchestrator.handle()` returns a generic
apology, not a question, when compilation escalates. This is an unmet commitment
under the Constitution's Invariant 1 / Law 6 (study §A).

## 2. What slice 1 does

1. **Detector** (`core/cognitive/content_anchor.py`, `creative_content_anchor` v0):
   deterministic, no model call, reads **request text only**. In scope only for a
   generative verb + artifact noun (story/poem/essay/…). Counts content-bearing
   tokens after removing form specification (verb, noun, numbers, length words,
   filler). Zero → score 0.0; delegation phrases ("surprise me") → 1.0. **Out of scope →
   the detector ABSTAINS** (`score = None`).
2. **Policy application.** For in-scope requests only, the score is put on a
   `GovernanceAction` under its own key `content_anchor_score` and evaluated by
   `OrchestrationGovernor`, which applies a threshold (default 0.5) → `APPROVE` /
   `ESCALATE`. An abstaining detector has nothing to decide, so **no governance action
   is created**; an event is still emitted so replay shows it ran and declined.

   **What `score` means (and does not).** A coarse, detector-specific *presence
   indicator* for content-bearing tokens: `min(1, content_tokens / 2)`. It is **not** a
   probability that the request is sufficient, not a measure of how well-specified it
   is, and not comparable across detectors or versions (events carry detector name +
   version for that reason). `1.0` means only "≥ 2 content tokens, or the user
   delegated". A future sufficiency model must not consume it as if it were one.

   **What abstention means (and does not).** `in_scope = False` / `status = abstained`
   means *"this slice declines to make a judgment"* — **not** "known to be sufficient".
   Orchestration proceeds, but the record says `abstained`, distinct from `anchored`.
   In-scope + no anchor → clarify; in-scope + anchor/delegated → continue;
   out of scope → this policy abstains.
3. **Surface.** On `ESCALATE`, `Orchestrator.handle()` returns a specific question,
   emits `orchestrator.clarification_requested`, and does not call `plan()`,
   `compile()`, or `WorkflowRuntime.execute()`. A denial by a *different* governor is
   reported as a generic failure, never dressed up as a question.
4. **Observability.** One event per evaluation, `cognitive.content_anchor_evaluated`
   (goal_id, detector name + version, score, in_scope, delegated, verdict, status,
   governor). No raw request text in the payload.

**What slice 1 validates:** detect → ask → stop — pre-plan interception of form-only
creative requests and surfacing of a question. **What it does not:** material
sufficiency; conversational task continuation (preserve the task, merge the answer,
re-evaluate, continue); use of Intent/Goal state; Verification integration.
`IntentLifecycle.CLARIFICATION_PENDING`/`CLARIFIED` remain **unreached** (`[FACT]`, study
§H) — their existence as enum values does not mean a clarification lifecycle is live.

## 3. Placement and ownership (review point 1)

**Where:** after `interpret_request()` returns, before `plan()`, inside
`Orchestrator.handle()`'s K4.2 branch. **Owner:** `Orchestrator` (the sole authorized
caller of the cognitive entrypoints, DRIFT-11 `[FACT]`).

The study recommended "immediately after `form_goals()`, inside *or as a sibling
call within* `interpret_request()`". The earlier draft claimed to honor that "as the
sibling-call form"; **that was inaccurate** — the gate is outside `interpret_request()`.
Corrected facts:

- `[FACT]` DRIFT-10 is an AST check for `evaluate_action` *calls inside* `intent.py`
  and `planner.py`; DRIFT-11 restricts *which files may import* the three entrypoints.
  **DRIFT-11 does not freeze signatures** (the earlier draft said it did).
- `[FACT]` `interpret_request()` returns `List[Goal]`; it has no channel to return a
  "clarification required" outcome. Signalling from inside it means an additive
  `Goal` field or a return-contract change.
- `[FACT]` This slice's detector consumes **request text only**; `goal_id` is a
  correlation id. So the study's rationale for the in-function location — Intent and
  Goal signals co-present — is **not exercised by slice 1**. What *is* preserved is the
  study's cost property: it runs after the already-paid interpretation call and before
  capability discovery, planning, compilation, and execution.

**Proposed resolution (PROPOSED, provisional pending D-5 — §10 shows this placement
contradicts a K4.2 decision):** keep the Orchestrator-owned placement for slice 1,
because the detector needs nothing from Intent/Goal state and the alternative
touches a contract for no benefit. **Reopen** the in-function placement when a
detector needs hypotheses, dimensions, or discarded-candidate information (the
study's actual reason for that location).

## 4. Reconciliation with the architecture review

| # | Review point | Disposition |
|---|---|---|
| 1 | Gate placement differs from study | **Accepted, corrected** — §3 |
| 2 | `WorkflowRuntime.resume()` treated as established | **Accepted; and stronger than stated** — §5. Note: the earlier draft listed it as one candidate carrier in D-3, not as an assumption; it is now removed as a candidate for this placement |
| 3 | Round trip not implemented; don't claim `clarification_attempt` reuse | **Accepted** — §2 and code docstring say slice 1 validates detection + short-circuit only |
| 4 | Lexical signal weaker than the study's materiality definition | **Accepted** — renamed; blind spots pinned as executable tests (`TestKnownLimits`, incl. the reviewer's "1000-word science-fiction story" and "story about a dragon") |
| 5 | Repeats the crude-heuristic warning | **Accepted** — stated as experimental, one narrow class, not a general model; acceptance criteria measure only that (§7) |
| 6 | ESCALATE→REJECT bound can't occur statelessly | **Accepted, option B** — bound, `attempt`, `max_escalations` and the stalled status **removed** from code, governor, tests. Loop-freedom in slice 1 comes from statelessness, not a bound |
| 7 | "Governance decision" wording; Intent owns semantics | **Accepted** — detector (cognitive layer) owns meaning of the score; governor applies the threshold only. **Additionally found, not raised in review:** see D-5 |
| 8 | Verification is future-only | **Accepted** — principle recorded in §8 |
| 9 | `resolution_origin` on `Goal` is premature | **No action needed:** this ADR does not propose it (the *study* does, §T). Slice 1 fills no defaults, so it has no use for it; deferred until a defaulting mechanism exists |
| 10 | Ordering is right | Agreed |

## 5. `WorkflowRuntime.resume()` (review point 2)

`[FACT]` `resume(definition, instance_id, …)` requires a `WorkflowDefinition` and an
`instance_id`, reloads checkpointed `node_states`, and is documented as durability of
*state* after a crash (DEBT-003 / ADR-KERNEL-03), re-running interrupted nodes.
`[FACT]` At this gate no `WorkflowDefinition`, instance, or checkpoint exists —
`plan()` has not run and `execute()` creates the instance later.
`[INFER]` Therefore the study's "strong candidate for reuse" (§I/§T) was never
established and **does not apply to a pre-plan gate**. It could only apply if
clarification moved *after* planning (then a real pause/resume of a real workflow
would be meaningful) — a different design with different costs (planning already
spent). Status: `[PENDING]`, not a candidate for slice 1.

## 6. Decisions for Moncif (not made by this ADR)

- **D-1 — meaning of "verify" in Invariant 1:** ask the user, or route through
  Verification? Slice 1 assumes ask-the-user (Verification is wired into no live path).
- **D-2 — is asking the right default even for the story example?** Many users prefer
  an immediate story; over-escalation is a documented failure mode. Product decision.
- **D-3 — cross-turn state carrier.** A real round trip needs the answer merged with
  the original request and an attempt counter, event-sourced (Law 2), plus
  `IntentLifecycle.CLARIFICATION_PENDING`/`CLARIFIED`. `handle()` is stateless
  `str → str`. Not built. Candidates exclude `resume()` for this placement (§5).
- **D-4 — Test D (already known from context).** Needs the hint channel; not in slice 1.
  Recorded as a strict `xfail`.
- **D-5 — placement vs. the K4.2 "no dedicated clarification gate" decision. OPEN,
  merge-blocking.** Analysed from repository evidence in §10, with a recommendation
  (option C) that is **not** a decision. Corrects the earlier framing: the conflict is
  with a K4.2 architectural decision, not merely DRIFT-10's wording.

## 7. Verification: what slice 1 proves and does not

Proves (real `OrchestrationGovernor`/`GovernanceKernel`): form-only requests escalate
with no `plan()`/`compile()`/execute; requests with any content anchor, delegation,
or out of scope pass; key isolation from `ClarificationPolicy` and the H-13 exemption;
denial by another governor is not reported as a question; event carries no raw text;
flag off ⇒ inert; evaluation is stateless and repeatable.
Does **not** prove: material sufficiency; behavior against a live model; precision /
recall on a real corpus (constructed cases only); the study's 466-vs-1000-words
experiment (`[PENDING]`); cross-turn convergence; Test D. Acceptance for this slice
is limited to exactly the "proves" list.

**Full-suite qualification (do not let this drift into "suite passed").** The branch and
`main` @ `2520cb4` have **identical pre-existing failure sets** (23 test IDs: 16 failed +
7 errors, **untriaged**, causes unknown); the new and targeted tests pass. That is
evidence of *no newly introduced failures within that set*, nothing more.

## 8. Boundaries

- **Verification:** *Intent may consume Verification results when they exist; Intent
  does not verify.* No Verification dependency exists in this slice.
- **Provenance:** no defaults are filled, so no provenance field is added.
- **C-MoE:** unchanged; this only prevents downstream speculation about a
  form-only request.

## 9. Rollback

Set `creative_anchor_gate_enabled = false` (default). Full removal: delete
`core/cognitive/content_anchor.py`, the governor rule, the orchestrator block, the
config key and `main.py` wiring, and the test file. No schema, persisted state, or
registered event type to migrate.

## 10. D-5 — evidence and options (answers the second review's demand)

### 10.1 The actual authority is not DRIFT-10
`[FACT]` The phrase "compilation boundary only" appears in exactly two places:
DRIFT-10's description string (`scripts/check_drift.py:598`) and the D10 completion
report. DRIFT-10 is a *derived mechanical rule* (an AST check for `evaluate_action` calls
inside `intent.py`/`planner.py`), and **it does not flag this slice** (the call lives in a
new module). It is not the source authority.

`[FACT]` The source is the K4.2 authoritative document, "Clarification policy":
*"No dedicated clarification gate — **reaffirmed, not re-derived**"*; clarification is a
`ClarificationPolicy` **evaluated by the `OrchestrationGovernor` rule at the existing Plan
Compilation gate (K4 §15)**, *"not a new component or a new gate."* Its stated rationale:
(a) low confidence propagates `Goal.confidence → ExecutionPlan.confidence`; (b)
`SupervisorWorker`'s escalation surfaces *a concrete plan with its stated interpretation,
not an abstract disambiguation question*; (c) no new component.

This slice's pre-plan block **is** a dedicated clarification gate, and it asks an abstract
question. It contradicts that decision on (b) and (c). Two errors of mine and the study's
are corrected here: the study's §F argued only non-collision with `ClarificationPolicy`
and never confronted this decision; my first ADR draft cited "not a new component" to
reject a new gate while implementing one.

`[FACT]` Status of the decision: authoritative per the K4.2 document; **no**
`ARCHITECTURE_DECISIONS.md` exists and `ADR_INDEX.md` has no entry for it, so it is not
recorded as FINAL in a decision ledger. It must still be superseded explicitly, not
bypassed (PROJECT_INSTRUCTIONS §18.4.5: preserve the original, record the reason).

### 10.2 Cost facts (the pre-plan placement's whole justification)
`[FACT]` `handle()`: `interpret_request → plan → compile → execute`. `plan()` calls the
model **unconditionally once** (`_decompose → generate_with_fallback`; degrades only on
exception) plus capability discovery. `compile()` makes no model call: it runs governance
and returns. Generation happens at execution. So the pre-plan gate saves one
decomposition call + discovery + compile; a compile-gate placement saves only execution
(the large cost) and still pays **one decomposition call** per intercepted request.

### 10.3 Does the decision's premise cover this failure class?
`[FACT]` No, for content under-specification: the study established hypothesis confidence
is unrelated to content specificity, and H-13 exempts general-purpose-only plans at the
compile gate — so premise (a) does not hold for this class. That is a legitimate ground
to *reconsider* the decision, but reconsideration is a supersession, not a silent bypass.

### 10.4 Options (the review's A–D, plus the current state)
| Option | Verdict | Evidence |
|---|---|---|
| **Current** (pre-plan, dedicated, governed) | Contradicts the K4.2 decision unless superseded | §10.1 |
| **A** amend DRIFT-10 | Wrong target as the resolution | Derived rule; doesn't flag this slice; changing it leaves the K4.2 decision violated. Only a follow-on if the decision is superseded |
| **B** another *existing* pre-plan seam | None exists | `[FACT]` `handle()` order above; the only existing seam is Plan Compilation itself → collapses into C |
| **C** detect early (pure, no governance), carry result to `compile()`, evaluate at the existing compile gate | **Consistent with the K4.2 decision** | No new gate; one rule in the same governor at the same boundary. Costs: 1 decomposition call per intercepted request; needs (i) a carrier into `compile()` — an additive optional kwarg follows the existing `clarification_policy`/`clarification_attempt` pattern (its name/surface is "frozen by K4.2 §1"), or a field on `Goal`/`ExecutionPlan`; (ii) `handle()` turning an `ESCALATED` `CompilationResult` into a specific question instead of the generic apology (which also fixes the study's dead-end finding for `ClarificationPolicy`); (iii) an explicit choice between K4.2's intended "concrete plan + interpretation" surfacing and a question — `[FACT]` that surfacing is not wired on the K4.2 branch |
| **D** pure Intent-level, no governance | Least aligned | Still a dedicated clarification gate (same contradiction) and removes governance's audited ESCALATE |

### 10.5 Recommendation (`[INFER]`, **not a decision**)
Prefer **C**: it needs no supersession of a reaffirmed decision, keeps governance at the
compile boundary, and its cost is one small decomposition call on exactly the requests
that would otherwise trigger the large generation. Choose to keep the current placement
**only** if Moncif judges saving that call worth formally superseding K4.2's "no
dedicated clarification gate" — then an ADR must supersede it (original preserved,
reason recorded), and DRIFT-10's wording be amended as a consequence.

Reusable under C unchanged: detector, `content_anchor_score` key, governor rule, events,
abstention semantics, and all tests except the orchestrator-block tests. What changes:
the orchestrator block and a `compile()` carrier. **No rework is started on C until D-5
is decided.**
