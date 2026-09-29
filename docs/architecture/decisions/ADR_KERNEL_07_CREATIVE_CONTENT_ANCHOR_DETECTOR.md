# ADR-KERNEL-07 — Creative Content-Anchor Detector (first narrow slice toward Intent Sufficiency)

**Status:** PROPOSED. **D-5 RESOLVED — Option C, decided by Moncif on 2026-09-29** (§10).
D-1..D-4 remain open. Acceptance and merge readiness are Moncif's call; nothing here is
ACCEPTED. The implementation is on a work branch, disabled by default
(`[runtime] creative_content_anchor_enabled = false`); with the flag off, `handle()` and the
`compile()` call are unchanged.
**Date:** Sept 29, 2026 (supersedes the earlier "Gate" revisions of this ADR; the renaming
from *Gate* to *Detector* is deliberate — K4.2 records no dedicated clarification gate).
**Governing study:** `docs/studies/OCBRAIN_INTENT_SUFFICIENCY_STUDY_SEPT2026.md` (unmodified).
**Series:** next after ADR-KERNEL-06.

Evidence tags: `[FACT]` verified in live source (clone of `main` @ `2520cb4`, re-checked
against `2e5cfc0`); `[INFER]` reasoning from verified facts; `[PENDING]` open.

> **Claim discipline.** This does **not** implement Intent Sufficiency. It implements a
> *narrow experimental detector* for one class of under-specification and carries its
> observation to the existing Plan Compilation boundary.

## 1. Problem (`[FACT]`)

Nothing between raw request text and a committed `ExecutionPlan` asks whether the request is
sufficiently specified. `interpret_request()` computes `Intent.confidence` and
`complexity_estimate` and never branches on either. `ClarificationPolicy` measures
capability-match confidence and is exempted for general-purpose-only plans (ADR-K4.2-H-13).
`Orchestrator.handle()` returns a generic apology, not a question, when compilation
escalates. This is an unmet commitment under the Constitution's Invariant 1 / Law 6 (study §A).

## 2. Decision (Option C)

```
interpret_request()
   ↓
detect  ── pure, non-governing observation (this ADR's module; emits an event)
   ↓
plan()                      (one unconditional decomposition model call — §10.2)
   ↓
compile()  ── EXISTING Plan Compilation gate; the observation rides its EXISTING
   ↓          "plan_compile" governance action under its own metadata keys
OrchestrationGovernor  (EXISTING) applies a threshold alongside ClarificationPolicy
   ↓
ESCALATE → clarification response: detector-specific question + the interpreted plan/intent
```

1. **Detector** (`core/cognitive/content_anchor.py`, `creative_content_anchor` v0):
   deterministic, no model call, reads **request text only**. In scope only for a generative
   verb + artifact noun (story/poem/essay/…). Counts content-bearing tokens after removing
   form specification. Zero → score 0.0; delegation ("surprise me") → 1.0; out of scope →
   **abstains** (`score = None`). It imports no governance code and decides nothing
   (enforced by an architecture test).
2. **Carrier.** `compile()` gains one additive, keyword-only, default-`None` argument,
   `content_anchor`. Its metadata keys (`content_anchor_score`, `content_anchor_threshold`)
   are merged into the **existing** governance action; empty for `None` or an abstention, so
   the default path is byte-identical. `[FACT]` `compile`'s name is frozen by K4.2 §1; its
   parameter list already grew additively (`clarification_policy`, `clarification_attempt`).
3. **Policy application.** The existing `OrchestrationGovernor` gains one rule that applies a
   threshold to `content_anchor_score` (ESCALATE below 0.5; no attempt bound — slice 1 has no
   attempt state). It reads only its own key; `ClarificationPolicy` reads only `confidence`.
   The content-anchor rule is evaluated first; if it passes or is inert, `ClarificationPolicy`
   runs as before.
4. **Surface.** `handle()` turns an `ESCALATED` compilation into a clarification response
   when — and only when — the ESCALATE came from `OrchestrationGovernor` **and** the carried
   observation is missing an anchor (the same predicate the governor applied). Any other
   escalation keeps the pre-existing generic message. The response is **the interpreted
   intent, the draft plan steps (≤5, one line each, truncated), and a specific question**.
   `SupervisorWorker` is still invoked exactly as before.
5. **Observability.** `cognitive.content_anchor_observed` (detector name/version, score,
   in_scope, abstained, missing; no raw text) pre-plan; the existing `cognitive.plan_rejected`
   (now with an additive `content_anchor_score` when the detector contributed);
   `orchestrator.clarification_requested`.
6. **No new gate, no new governance boundary, no new governance evaluation.** A test asserts
   the recorded sequence of governance evaluations is identical with the flag on and off.

## 3. Placement and ownership

The observation runs in `Orchestrator.handle()` after `interpret_request()` returns —
the Orchestrator being the sole authorized caller of the cognitive entrypoints (DRIFT-11
`[FACT]`; DRIFT-11 restricts *importers*, it does **not** freeze signatures).
`interpret_request()` is untouched. The detector consumes request text only; `goal_id` is a
correlation id, so the study's rationale for an in-function placement (Intent and Goal
signals co-present) is **not exercised** by slice 1. **Reopen** when a detector needs
hypotheses, dimensions, or discarded-candidate information. Semantic ownership: the detector
(cognitive layer) owns what its score means; the governor only applies a threshold — the
mechanism role it already plays for `ClarificationPolicy`.

## 4. Constraints honored

| Constraint | How |
|---|---|
| K4.2: "No dedicated clarification gate — reaffirmed"; evaluated at Plan Compilation | Kept. No pre-plan decision exists; the only governance evaluation of the observation is the existing compile-time action |
| DRIFT-05/10: no `evaluate_action` call in `intent.py`/`planner.py` | None added anywhere new; `compiler.py` already owns this call |
| DRIFT-11: sole-caller rule | Orchestrator remains the only importer of the entrypoints |
| ADR-K4.2-H-13 (general_purpose_only exemption) | Applies only to `ClarificationPolicy`; the content-anchor rule is keyed separately and tested against it with real `compile()` |
| K4.2 §1: `compile` name frozen | Name unchanged; one additive optional keyword argument (the only contract touch) |
| ADR-K4.2-H-08 (`operation_id` from `plan()`/`compile()` only) | The detector generates none |
| Law 2 / determinism | Pure function of request text; observation is evented; no hidden state |
| No hidden state / no attempt carrier | Stateless per request (D-3) |

## 5. Semantics (explicit on purpose)

- **`score`** is a coarse presence indicator, `min(1, content_tokens / 2)`. It is **not** a
  probability of sufficiency, not comparable across detectors/versions (events carry name +
  version), and must not be consumed by a future sufficiency model as one.
- **Abstention** (`score None`, `abstained: true`) means *this slice declines to judge* — never
  "known sufficient". No governance keys are added for it.
- **Scope of slice 1: detect → ask → stop.** It does not preserve the task, merge the answer,
  or re-evaluate. `IntentLifecycle.CLARIFICATION_PENDING`/`CLARIFIED` remain **unreached**
  (`[FACT]`, study §H); no bounded-retry semantics exist. Resubmission is a fresh request.
- **Known blind spots (executable, `TestKnownLimits`):** "write a 1000-word science-fiction
  story", "write a story about a dragon", and "write a funny story" all pass.

## 6. Architecture-review dispositions

| Review point | Disposition |
|---|---|
| 1 Placement vs study | Accepted, corrected (§3). Superseded in substance by D-5 = C: the *decision* now sits at Plan Compilation |
| 2 `resume()` | Accepted; does not apply — needs a `WorkflowDefinition` + instance (§7) |
| 3, 6 Round trip / bound not implemented | Accepted; bound removed; scope stated (§5) |
| 4, 5 Weak lexical signal | Accepted; narrow, named, versioned, blind spots pinned |
| 7 Semantic ownership | Accepted (§3) |
| 8 Verification future-only | Accepted (§11) |
| 9 `resolution_origin` | Not proposed by this ADR (the *study* does); no defaults filled |
| 10 Ordering | Agreed |
| 2nd review: resolve D-5 from evidence | Done (§10); **decided: Option C** |
| 2nd review: score meaning; abstention; slice scope; full-suite wording | Done (§5, §9) |

## 7. `WorkflowRuntime.resume()` (`[FACT]`)

`resume(definition, instance_id, …)` requires a `WorkflowDefinition` and instance, reloads
checkpointed node states, and is documented as crash-recovery durability (DEBT-003). At the
detection point neither exists. `[INFER]` The study's "strong candidate for reuse" was never
established for a pre-plan carrier. Under C the decision now happens *after* planning, so a
future carrier could reconsider it — `[PENDING]`, not part of slice 1.

## 8. Open decisions (Moncif)

- **D-1** meaning of "verify" in Invariant 1 (ask the user vs route through Verification).
- **D-2** is asking the right default even for the story example? Product decision;
  over-escalation is a documented failure mode.
- **D-3** cross-turn state carrier (answer merge, attempt counter, lifecycle states),
  event-sourced. Not built.
- **D-4** Test D (already known from context). Strict `xfail`.
- ~~**D-5**~~ **Resolved: Option C** — see §10.

## 9. Verification: what is and is not proven

Proves, with real `compile()`, real `GovernanceKernel`, real `ExecutionPlan`: a form-only
creative request ESCALATES at Plan Compilation; the H-13 exemption does not swallow it (with a
no-anchor baseline proving the exemption is active); anchored/delegated/abstained requests
compile; `ClarificationPolicy` still operates alongside and is evaluated after the anchor rule;
another governor's rejection is not turned into a question; the feature adds **no**
governance evaluation (sequence identical on vs off); the detector module has no governance
import; flag-off is inert and the `compile()` call is unchanged; the response pairs the
interpreted plan with a specific question and bounds model-derived text.
Does **not** prove: material sufficiency; live-model behavior; precision/recall on a real
corpus; the study's 466-vs-1000-words experiment (`[PENDING]`); cross-turn convergence; Test D.

**Full-suite qualification.** Branch and `main` have **identical pre-existing failure sets**
(23 test IDs: 16 failed + 7 errors, **untriaged**). That is evidence of *no newly introduced
failures within that set*, not "the suite passed".

## 10. D-5 — evidence, decision, consequences

### 10.1 Evidence (unchanged findings)
`[FACT]` "compilation boundary only" appears only in DRIFT-10's description string
(`scripts/check_drift.py`) and the D10 report: a *derived* mechanical rule, not the authority.
The authority is the K4.2 authoritative document: *"No dedicated clarification gate —
reaffirmed, not re-derived"*; `ClarificationPolicy` is evaluated by the `OrchestrationGovernor`
at the existing Plan Compilation gate; rationale: (a) confidence propagates Goal→plan, (b)
escalation surfaces a *concrete plan with its stated interpretation*, (c) no new component.
The earlier pre-plan gate contradicted this; the study never confronted the decision.
`[FACT]` No `ARCHITECTURE_DECISIONS.md` exists and `ADR_INDEX.md` had no entry for it.
`[FACT]` `plan()` makes one unconditional model call (`_decompose → generate_with_fallback`,
degrading only on exception); `compile()` makes none; generation happens at execution.
`[FACT]` The decision's premise (a) does not cover content under-specification.

### 10.2 Options considered
Current pre-plan gate (contradicts K4.2) · **A** amend DRIFT-10 (wrong target) · **B** another
existing seam · **C** detect early, decide at the existing gate · **D** pure Intent-level, no
governance (still a dedicated gate).

**Correction found while implementing C.** The earlier text said no other pre-plan governance
seam exists and that B "collapses into C". That was imprecise. `[FACT]` `handle()` opens with a
request-authorization evaluation (`ORCHESTRATOR_ACTION_TYPE`, PI LAW 1, before any work;
ESCALATE there means "requires human approval"), present on the untouched baseline. It is an
authorization seam, not a clarification seam, and runs before `interpret_request()`. Using it
would put a clarification decision inside an authorization check — mixing responsibilities and
contradicting K4.2 as much as the pre-plan gate did. B's rejection stands, on corrected
grounds. The property that matters, and is now tested, is that **the feature adds no
governance evaluation of its own**.

### 10.3 Decision (Moncif, 2026-09-29) — recorded verbatim
> **Resolved: Option C.** The content-anchor detector executes before planning as a pure,
> non-governing observation. Its result is carried through planning to the existing Plan
> Compilation boundary, where the existing OrchestrationGovernor evaluates it alongside
> ClarificationPolicy. No new clarification gate or new governance boundary is introduced. An
> ESCALATE result may surface a detector-specific clarification question, paired with the
> concrete interpreted plan/intent required by K4.2.

K4.2 is **not** superseded; DRIFT-10's wording is left unchanged.

### 10.4 Consequences and risks
- **Cost:** an intercepted request still pays `plan()`'s one decomposition model call (plus
  capability discovery); only execution/generation is avoided.
- **Risk `[PENDING]`:** the draft plan steps shown to the user are model-generated from an
  under-specified request and may themselves speculate (e.g. invent a premise), which is the
  behavior the detector exists to avoid. Mitigated by showing at most five truncated, labeled
  "draft" steps; whether showing them helps or hurts is an empirical question for a live run.
  The pairing is easy to drop (`plan_steps=[]`) if it proves unhelpful.
- **Contract touch:** one additive keyword argument on `compile()`; the rest is additive
  metadata and an additive event key.

## 11. Boundaries and rollback

- **Verification:** *Intent may consume Verification results when they exist; Intent does not
  verify.* No Verification dependency exists here.
- **Provenance:** no defaults are filled, so no provenance field is added.
- **C-MoE:** unchanged; this only prevents downstream speculation about a form-only request.
- **Rollback:** set `creative_content_anchor_enabled = false` (default). Full removal: delete
  `core/cognitive/content_anchor.py`; remove the `content_anchor` argument and metadata merge
  in `compiler.py`; the governor rule; the orchestrator observation/carry/response blocks;
  the config key and `main.py` wiring; and the test file. No schema, persisted state, or
  registered event type to migrate.
