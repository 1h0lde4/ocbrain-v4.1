# ADR-KERNEL-07 — Intent Sufficiency Gate (Slice 1)

**Status:** PROPOSED — design and slice-1 implementation are on a work branch for
review. Nothing here is ACCEPTED until Moncif accepts it. The gate ships
**disabled by default** (`[runtime] intent_sufficiency_enabled = false`), so
merging the branch changes no observable behavior.
**Date:** Sept 28, 2026
**Governing study:** `docs/studies/OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md`
(study only; this ADR is the decision record its §T/§U say must precede any code).
**Series note:** next number after ADR-KERNEL-06 in the `ADR-KERNEL-NN` series.

Evidence tags follow project convention: `[FACT]` verified in live source this
session (clone of `main` @ `2520cb4`), `[INFER]` reasoning from verified facts,
`[PENDING]` open.

---

## 1. Problem

`[FACT]` Nothing between raw request text and a committed `ExecutionPlan` asks
whether the request is *sufficiently specified*. `interpret_request()`
(`core/cognitive/intent.py:1239`) computes `Intent.confidence` and
`IntentDimensions.complexity_estimate` (`_estimate_complexity`, `:835`) and never
branches on either.

`[FACT]` The only clarification mechanism, `ClarificationPolicy`, measures
capability-match confidence and is exempted for general-purpose-only plans
(`OrchestrationGovernor._evaluate_clarification_policy`,
`core/governance/orchestration_governor.py`, ADR-K4.2-H-13). With only
`LLM_COMPLETION` registered, that exemption applies to essentially every request.

`[FACT]` Even when `ClarificationPolicy` does escalate, `Orchestrator.handle()`
returns a generic apology ("I wasn't able to prepare your request…",
`core/orchestrator.py`, `CompilationStatus != COMPILED` branch), not a question.

`[FACT]` This contradicts the Kernel Constitution's own Invariant 1 and Law 6
(as quoted in the study, §A). It is an unmet commitment, not an external critique.

## 2. Decision (slice 1)

Add a **sibling policy** to `ClarificationPolicy`, evaluated by the **same**
`OrchestrationGovernor`, at a point **after** `interpret_request()` and **before**
`plan()`:

1. **New module `core/cognitive/sufficiency.py`.** Contains the pure assessment
   function, `SufficiencyPolicy`, and an async evaluator that builds a
   `GovernanceAction` and calls `GovernanceKernel.evaluate_action()` — the exact
   pattern `compiler.py` and `learning.py` already use.
2. **Governor rule.** `OrchestrationGovernor` gains a fourth question, keyed on
   `metadata["sufficiency_score"]` (a **distinct key** from `"confidence"`, so the
   existing `ClarificationPolicy` rule cannot fire on it). Same verdicts and same
   bounded-retry semantics as `ClarificationPolicy`: `ESCALATE` below threshold
   while `attempt < max_escalations`, `REJECT` (stalled) at the bound.
3. **Signal is deterministic and adds no model call.** It answers one narrow
   question — *does the request contain any content-bearing token beyond its form
   specification?* — and only for open-ended creative composition
   (artifact noun ∈ {story, poem, essay, song, …} **and** a generative verb).
   Everything else is `in_scope=False` → sufficient (fail-open).
4. **Surface.** On `ESCALATE`/`REJECT`, `Orchestrator.handle()` returns a specific
   question naming what is missing, emits `orchestrator.clarification_requested`,
   and does **not** call `plan()`, `compile()`, or `WorkflowRuntime.execute()`.
5. **Observability.** One event per evaluation:
   `cognitive.intent_sufficiency_evaluated` (trace_id, goal_id, score, in_scope,
   delegated, verdict, governor, attempt). No raw request text in the payload.

## 3. Constraints honored

| Constraint | How |
|---|---|
| DRIFT-05/10: no governance call inside `intent.py`/`planner.py` | Governance is invoked from the new module, not from those two files |
| DRIFT-11: frozen signatures of `interpret_request()`/`plan()`/`compile()` | Untouched; `interpret_request()` is **not modified** |
| ADR-K4.2-H-13 exemption | Untouched; sufficiency uses a separate key and rule, so the exemption cannot swallow it |
| ADR-K4.2-H-08 (`operation_id` only for `plan()`/`compile()`) | Event carries `trace_id`/`goal_id` only |
| Law 2 / no hidden mutable state | Slice 1 is stateless per request; no pending-clarification store is introduced (see D-3) |
| Determinism / replay | Assessment is a pure function of the request text |

## 4. Alternatives considered

- **Broaden `ClarificationPolicy`.** Rejected: recreates the confidence-naming
  collision the study diagnoses, one level down.
- **New governor / new gate.** Rejected: violates the "not a new component" rule
  K4.2 §2 already states for clarification.
- **LLM-judged sufficiency.** Deferred: adds a non-deterministic call before the
  gate whose purpose is to avoid unnecessary calls; revisit only if the lexical
  signal proves too coarse (see §7).
- **Gate inside `interpret_request()`.** Rejected for slice 1: it would put a
  governance call in a DRIFT-05/10-policed file and touch a frozen entrypoint.
  `[PENDING]` The study's §F placement ("inside or as a sibling call") is honored
  as the sibling-call form.

## 5. Decisions needed from Moncif (not made by this ADR)

- **D-1 — meaning of "verify" in Invariant 1.** Does "where genuinely ambiguous,
  verify" mean *clarify with the user*, or *route through Verification*? Slice 1
  assumes clarify-with-user because Verification is wired into no live path
  (study §M). `[PENDING]` A Constitution clarifying note is recommended.
- **D-2 — is asking the right default for the story example?** Many users prefer
  an immediate story. The gate is flag-off and fail-open outside its narrow scope
  for this reason; whether to enable it, and for which artifact classes, is a
  product decision, not an engineering one. Over-escalation is itself a documented
  failure mode (study §I, Headroom).
- **D-3 — cross-turn state carrier.** A real clarification round trip needs the
  answer merged with the original request, `clarification_attempt` incremented,
  and `IntentLifecycle.CLARIFICATION_PENDING`/`CLARIFIED` activated. `handle()` is
  `str -> str` and stateless; any carrier (orchestrator-held map, `WorkflowRuntime`
  checkpoint reuse per study §I, or context memory) is an architectural choice that
  must be event-sourced to satisfy Law 2. **Slice 1 does not build it.** The
  question it returns instructs the user to resend the request with details, which
  is stateless and loop-free (each request is assessed fresh).
- **D-4 — Test D (already-known-from-context).** Unimplementable in slice 1: it
  needs the hint channel wired into the sufficiency check (study §U). Recorded as a
  known acceptance gap, not silently skipped.

## 6. Verification plan (what slice 1 proves, and what it does not)

Proves (unit + real-governor tests, this branch): Test A (under-specified →
`ESCALATE`, no plan/compile/execute), Test B (well-specified → approve), Test C
(delegation → approve), Test G (bounded: stalled at `max_escalations`), key
isolation from `ClarificationPolicy`, fail-open for out-of-scope requests,
orchestrator short-circuit with flag on, and byte-identical behavior with flag off.

Does **not** prove: behavior against a live model backend; the literal 466-vs-1000
words experiment (study §B `[PENDING]`); precision/recall on a real request corpus
(the lexical signal has only been tested on constructed cases); cross-turn
convergence (D-3); Test D (D-4).

## 7. Risks

- **Lexical signal is coarse.** It can under-trigger (any content token passes) and
  over-trigger on terse-but-complete requests outside its lexicon. Mitigated by
  narrow scope, fail-open default, and the flag; replaceable behind the same
  governance shape without a new ADR (study Gate 3).
- **Known-narrow scope.** Only creative-composition requests are assessed today.
- **Interaction with DEBT-038 / ADR-CAP-03.** Registering specific capabilities
  changes `general_purpose_only` behavior; the sufficiency rule is independent of
  it by construction and has a regression test asserting that.

## 8. Rollback

Set `[runtime] intent_sufficiency_enabled = false` (already the default). Full
removal: delete `core/cognitive/sufficiency.py`, the governor rule, the
orchestrator block, the config key, and the tests — no schema, event-type
registration, or persisted state exists to migrate.
