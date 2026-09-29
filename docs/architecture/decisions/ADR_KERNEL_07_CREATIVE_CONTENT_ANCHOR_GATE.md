# ADR-KERNEL-07 — Creative Content-Anchor Gate (first narrow slice toward Intent Sufficiency)

**Status:** PROPOSED — **not implementation-ready for merge.** The code on the work
branch is a reviewable *proposal*, disabled by default
(`[runtime] creative_anchor_gate_enabled = false`). Decisions D-1..D-5 (§6) are open
and must be resolved by Moncif before this ADR can be ACCEPTED.
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
   filler). Zero → score 0.0; delegation phrases ("surprise me") → 1.0; out of scope
   → 1.0 (fail-open).
2. **Policy application.** The detector's score is put on a `GovernanceAction` under
   its own key `content_anchor_score` and evaluated by `OrchestrationGovernor`,
   which applies a threshold (default 0.5) → `APPROVE` / `ESCALATE`.
3. **Surface.** On `ESCALATE`, `Orchestrator.handle()` returns a specific question,
   emits `orchestrator.clarification_requested`, and does not call `plan()`,
   `compile()`, or `WorkflowRuntime.execute()`. A denial by a *different* governor is
   reported as a generic failure, never dressed up as a question.
4. **Observability.** One event per evaluation, `cognitive.content_anchor_evaluated`
   (goal_id, detector name + version, score, in_scope, delegated, verdict, status,
   governor). No raw request text in the payload.

**What slice 1 validates:** detection of form-only creative requests and
short-circuiting before planning. **What it does not:** material sufficiency, a
multi-turn clarification lifecycle, use of Intent/Goal state, or any Verification
integration.

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

**Proposed resolution (PROPOSED):** keep the Orchestrator-owned placement for slice 1,
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
- **D-5 — governance boundary (new).** `[FACT]` DRIFT-10 describes governance as
  sitting "at the compilation boundary only". This slice adds a governed evaluation
  **before** compilation. It passes the mechanical check (the call is in a new
  module) but is in tension with that stated rationale. Options: (i) amend the
  boundary statement to admit a pre-plan, non-capability escalation; (ii) drop the
  governance round-trip for slice 1 and make the threshold decision inside the
  cognitive layer, leaving governance at compile. Not decided here.

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
