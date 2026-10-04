# ADR-KERNEL-07 — Creative Content-Anchor Detector (first narrow slice toward Intent Sufficiency)

**Status:** PROPOSED. **D-5 RESOLVED — Option C, decided by Moncif on 2026-09-29** (§10).
D-1..D-4 have dispositions recorded in §8 (D-1/D-2 PROPOSED, D-3/D-4 DEFERRED), none yet
accepted. Acceptance is Moncif's call; nothing here is ACCEPTED. The implementation is merged to `main` behind a default-off flag (a merge is not an acceptance of
this ADR, which stays PROPOSED); it is disabled by default
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
ESCALATE → clarification response: detector-specific question + the request text and draft plan steps (§10.4)
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
   escalation keeps the pre-existing generic message. The response is **the request text (echoed:
   `description` is the user's raw request, §10.4), the draft plan steps (≤5, one line each, truncated),
   and a specific question**.
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

## 8. D-1..D-4 — dispositions recorded (explicit acceptance by Moncif pending)

Status vocabulary follows PROJECT_INSTRUCTIONS §0.3. Each disposition was recommended by Claude
from the evidence below and **endorsed in the 2026-09-30 architecture review**; none has been
explicitly ACCEPTED by Moncif, so none is recorded as ACCEPTED. D-5 is decided (§10).

| # | Disposition | Status |
|---|---|---|
| D-1 | "verify" = **Intent Verification**; asking the user is one mechanism, not the only one; output Verification is separate. Recorded as a note *in this ADR* | PROPOSED |
| D-2 | Keep the flag **off**; enabling is a measured experiment | PROPOSED — equals the implemented default |
| D-3 | Cross-turn state / session identity → **its own future ADR** (number not reserved) | DEFERRED |
| D-4 | Test D stays a strict `xfail`; depends on D-3 | DEFERRED |
| — | Live draft-plan behavior (§10.4) | **OBSERVED for one model (llama3, n = 11); disposition pending** |

**No code on this branch depends on any of these dispositions.** D-2's "off" is the
pre-existing default; D-3 and D-4 are unimplemented by design; D-1 is a documentation note.
**Nothing in the Constitution documents was edited**; if the D-1 note should also live there,
that is a separate, Moncif-initiated change.

**D-1 — what "verify" means in Invariant 1.** *Disposition: clarifying note (PROPOSED).*
- `[FACT]` Constitution line 99: *"The kernel does not act on intent it has not first
  attempted to understand and, where genuinely ambiguous, verify."*
- `[FACT]` Pressure Test glossary: *"Intent is the raw, possibly ambiguous expression of what
  a user wants, prior to verification. Goal is the verified, disambiguated target state
  Intent compiles down to once verification succeeds"*, and "Goal Verification" is renamed
  **Intent Verification**: *"you verify the Intent in order to produce a Goal."*
- `[INFER]` So "verify" is **Intent Verification** (Intent → Goal) — neither "route through the
  output-Verification subsystem" nor, by definition, "ask the user". The study's dichotomy
  was a false one; the Constitution does not say *who or what* performs Intent Verification.
  Asking the user (this ADR) is one legitimate mechanism of it, not the only one.
- `[INFER]` Naming tension, recorded not fixed: `interpret_request()` returns `Goal`s *before*
  any verification, while the glossary defines a Goal as post-verification; under Option C the
  clarification happens after Goal formation and planning.
- Proposed note text: *"'verify' in Invariant 1 means Intent Verification; asking the user is
  one mechanism; output Verification is a separate concept."*

**D-2 — is asking the right default (e.g. for the story example)?** *Disposition: flag stays off;
enabling is a measured experiment (PROPOSED).*
- `[FACT]` Rationale §2: the qualifier *"where genuinely ambiguous"* is *"a deliberate hedge
  against a literal reading that would make the system stop and ask for clarification
  constantly. That hedge is untested. Worth watching in practice rather than trusting the
  wording is already right."*
- `[FACT]` The detector fires only on in-scope requests with zero content tokens; "surprise
  me" is an escape hatch; default is off. `[FACT]` No ask-rate data exists.
- Measurable at no extra cost: compare `orchestrator.clarification_requested` events with
  `cognitive.content_anchor_observed` events (`abstained: false`). Product call; not an
  engineering one.

**D-3 — cross-turn state carrier.** *Disposition: DEFERRED to its own ADR.*
- `[FACT]` No session/conversation identity on the K4.2 path: `_interaction_id(query)` hashes
  the query text alone; `interface/api.py` has no session/conversation concept (0 matches);
  `interpret_request()` takes no context parameter.
- `[FACT]` The orchestrator comment at L597–604 says the legacy K2.2 branch saves interaction
  and context itself and the K4.2 branch does so explicitly after execution. By control flow
  the clarification return precedes those writes, so the asked question and the user's reply
  are **not recorded as a linked exchange**.
- `[INFER]` `resume()` remains inapplicable under C: the ESCALATE happens at `compile()`,
  before `execute()` creates an instance.
- A real lifecycle needs a session-identity decision touching the API, events and
  `IntentLifecycle` — out of slice 1, which stays **detect → ask → stop**.

**D-4 — Test D (already known from context).** *Disposition: DEFERRED; strict `xfail` stays; depends on D-3.*
- `[FACT]` `interpret_request` parameters: `raw_text, memory, event_stream, known_categories,
  ontology_schemas` — no inbound context channel. The "PlannerHint" mentions are the
  *outbound* Intent→Planner channel. The detector reads request text only.
- `[INFER]` Without D-3's prior-turn carrier there is nothing to consult; inventing an inbound
  channel here would be an unrecorded architectural decision.

**Suggested order:** D-1 (note) → D-2 (keep off; decide whether to run the experiment) → D-3 →
D-4 (dependent on D-3). The live draft-plan check (§10.4) is independent of all four.

## 9. Verification: what is and is not proven

Proves, with real `compile()`, real `GovernanceKernel`, real `ExecutionPlan`: a form-only
creative request ESCALATES at Plan Compilation; the H-13 exemption does not swallow it (with a
no-anchor baseline proving the exemption is active); anchored/delegated/abstained requests
compile; `ClarificationPolicy` still operates alongside and is evaluated after the anchor rule;
another governor's rejection is not turned into a question; the feature adds **no**
governance evaluation (sequence identical on vs off); the detector module has no governance
import; flag-off is inert and the `compile()` call is unchanged; the response pairs the
request text and draft plan steps with a specific question and bounds model-derived text.
Acceptance of the slice's structural invariants does **not** depend on live draft-plan behavior,
which has been observed for one model only (§10.4).
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
- **Risk — draft plan steps: OBSERVED for one model; disposition pending.** The response shows
  model-generated plan steps for a request the detector says lacks content. The question, narrowly:
  *does exposing draft plan steps add useful context, or introduce speculative assumptions?*
  - **Evidence** (first real run: llama3 via Ollama in a Codespace, 11 requests, one run; full record in
    `docs/studies/OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RESULT_OCT2026.md`): all 11 plans were model-generated and
    multi-step — steps per plan 7, 6, 7, 7, 5, 11, 5, 7, 9, 7, 12 (median 7; 83 in total; **0 single-step**) —
    and 9 of 11 exceed the 5-step display cap. By the author's reading (one reader; check it), **no step
    names a concrete subject, genre, character, setting or premise**; most are generic authoring workflow
    (brainstorm / outline / draft / revise / proofread); a minority presuppose form or process the user did
    not choose (character profiles and backstories, plot twists, a thesis plus researched sources, chord
    progressions, "beta readers", "select a joke from a database or generate one using an algorithm").
    **Answer to the narrow question: neither, cleanly.** The steps add almost no context toward "what should
    it be about?", and what they introduce is *process/form* assumptions, not *premise* assumptions.
  - **My earlier hypothesis was wrong on both counts.** I expected a single-step, "redundant" plan and wrote
    that the decomposition input is "the interpretation (not the raw request)". Refuted for this model
    (0 of 11 single-step), and the input *is* the raw request: `structured_form["description"] =
    intent.raw_request` (`core/cognitive/intent.py:1090`).
  - **The "interpretation" line is an echo.** Because `description` is the raw request by design, "Here's how
    I read your request: …" shows the user's own words. The only real interpretation signal the Intent stage
    produces is the hypothesis category label (`semantic_description` = "<label>: <request>", label dropped
    when it is the `novel` placeholder). §2 item 4 and §9 are corrected accordingly. The rendered response
    also joins sentence-final steps with semicolons ("story.; 2.") and its example text ("a noir mystery, a
    cozy fantasy…") is story-specific for every artifact kind (a joke, an essay, a song).
  - **Instrument:** `scripts/live_check_draft_plan.py`. Its `speculative` label was **saturated, 11 of 11**:
    generic planning vocabulary (develop, including, clear, key, overall) counts as "content", so the label
    carries no information here and the printed steps are the evidence. The runbook's validity checker was
    also wrong at first (it treated an echoed interpretation as a sign of failure); corrected and tested.
  - **Limits:** 11 requests; one model; one run (sampling variance unknown); a fresh, empty memory store; one
    human reader; model identity recovered after the fact (`llama3:latest`, 8.0B, Q4_0, ID `365c0bd3c000`), sampling
    uncontrolled (the code sets no temperature or seed, so a re-run is expected to differ), and the repo commit
    not captured. It does **not** establish
    behavior with other models, with populated memory, or any effect on user outcomes. It does not accept
    this ADR.
  - **Containment options, none applied** — (A) `plan_steps=[]`; (B) drop both the plan and the echoed
    interpretation, leaving the question only; (C) cap the plan at three steps and fix its formatting.
    D-5 as decided says an ESCALATE *may* surface a question paired with the plan/intent, so (A) and (B)
    stay inside it. The author's reading of the evidence favors (B). The run refutes the hypothesis and shows what the
    system does; it does **not** by itself establish that the behavior is undesirable or that (B) is the only
    correct response — that is a product/architecture decision. Disposition is Moncif's.
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
