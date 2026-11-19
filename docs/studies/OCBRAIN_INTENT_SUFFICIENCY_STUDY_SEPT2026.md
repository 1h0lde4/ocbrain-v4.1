# OCBrain — Intent Sufficiency Study: Why OCBrain Acts on Under-Specified Requests

**Status:** Study only — no implementation. Per the governing task's explicit constraint, this document establishes ground truth, characterizes the observed behavior, researches the landscape, and produces an evidence-backed recommendation. It does not modify `core/`.

**Scope note on this pass:** Session context is Claude Web — read-only, unauthenticated HTTPS clone of `https://github.com/1h0lde4/ocbrain-v4.1`, re-cloned fresh this session per the project's evidence-first convention (prior summaries, including this repo's own `CURRENT_STATE.md`/`KNOWN_ISSUES.md`, are treated as claims to re-verify, not ground truth, and were re-verified against live source where load-bearing for this study). No live model backend is available in this sandbox, so the literal "write a 1000 words story" prompt could not be re-run end-to-end; every claim below is either a direct code citation or explicitly marked as unverified. Evidence tags follow this project's own convention: `[FACT]` direct source verification, `[CLAIM]` stated in project docs but not independently re-derived here, `[INFER]` this study's own reasoning from verified facts, `[PENDING]` genuinely open.

**Natural location:** `docs/studies/`, matching `OCBRAIN_KERNEL_V1_FREEZE_AUDIT_SEPT_2026.md` and siblings. Delivered here as a file since this session cannot push to the repo (per `ways-of-working.md`'s environment constraint — production actions are deferred to Claude Code or the GitHub web UI).

---

## A. Executive finding

`[FACT]` OCBrain has exactly one mechanism today that can turn a request-in-progress into a clarifying question: `ClarificationPolicy`, evaluated by `OrchestrationGovernor._evaluate_clarification_policy()` at Plan Compilation (`core/cognitive/compiler.py:269`, `core/governance/orchestration_governor.py:158`). Its own docstring is explicit about what it measures: *"Policy data governing when a low-confidence **ExecutionPlan** should be escalated"* (`planner.py:1020-1022`) — a **capability-match** confidence, computed as Jaccard token overlap between a decomposed step's description and its top candidate capability's own self-description (`_capability_match_score`, `planner.py:802`; confirmed by `ADR-K4.2-H-13`'s own worked example: `"hi and hello"` and `"book a flight to Tokyo next week"` both score `0.0` against `LLM_COMPLETION`'s description).

`[FACT]` That is a different question from **intent sufficiency** — whether the request contains enough information to produce a result aligned with what the user wants. OCBrain does compute Intent- and Goal-level signals that are closer to that question (`Intent.confidence` — the top hypothesis's own score; `IntentDimensions.complexity_estimate` — a length/hypothesis-count heuristic, `_estimate_complexity`, `intent.py:579-589`). `interpret_request()` (`intent.py:966-1069`), the sole top-level entrypoint for every request, computes both, event-logs both (`cognitive.intent_interpreted`, `cognitive.goal_formed`), and **never once compares either to a threshold or branches on either**. They are recorded, then carried forward unconditionally. This is a direct reading of the function, not an inference.

`[FACT]` Because OCBrain currently registers exactly one capability (`LLM_COMPLETION`, `is_general_purpose=True` — `ADR-K4.2-H-02`), and because `ADR-K4.2-H-13` (Aug 20, 2026) — correctly, for the bug it was fixing — exempts any plan whose only candidate is the general-purpose fallback from `ClarificationPolicy` entirely, *"regardless of the raw confidence value"* (`orchestration_governor.py:179-206`), the one check that exists is switched off for essentially every request in the current deployment configuration. `ADR-K4.2-H-13` says this outright: *"Practical scope today: ... this exemption applies broadly — most plans currently are general-purpose-only by construction."*

`[INFER]` The story-generation example is therefore not a bug in the ordinary sense — it is two separately-correct decisions (constraint extraction exists; the general-purpose exemption is the right fix for its own reported bug) composing into a gap neither decision was evaluating: nothing between raw text and a committed `ExecutionPlan` ever asks *"is what the user actually wants sufficiently determined?"* — only *"am I unsure **which capability** to use?"*, a question with a fixed, degenerate answer while only one capability is registered.

`[FACT]` `ADR-K4.2-H-13` names this precisely, in its own "Alternatives considered" section, as future work: *"Decouple 'confidence' (ranking) from a separate 'clarification-worthiness' signal architecture-wide: the more general, more correct long-term shape of this problem ... noted here as a candidate for `FUTURE_RESEARCH_VAULT.md`."* `[FACT]` It was never actually added there — a `grep -n -i "clarif"` of `docs/architecture/FUTURE_RESEARCH_VAULT.md` returns zero hits. The OCBrain team identified this exact architectural question over the same file thirteen months before this study, correctly scoped it out of a live-debugging fix, and the pointer to track it as future work was itself dropped.

`[FACT]` This is not a case where OCBrain's own principles disagree with the study's premise. `OCBRAIN_KERNEL_CONSTITUTION.md` Law 6 (Explainability) states as its own illustrative example: *"Before a workflow runs, the kernel can state plainly what it understood the goal to be, and what it's still uncertain about."* Invariant 1 (Part IV) states: *"The kernel does not act on intent it has not first attempted to understand and, where genuinely ambiguous, verify."* `CURRENT_STATE.md`'s own "Other Kernel Domains → Explainability" row confirms the gap independently: *"No `Explain*` class or module exists anywhere... no pre-execution confidence/justification surface exists."* The study's premise is the Kernel Constitution's own unmet commitment, not an external critique.

`[FACT]` A third, independent finding, arguably the most load-bearing for what gets built later: **even in the one case that does still escalate today** (a request with a genuinely weak *specific* capability alternative, not the general-purpose-only case), the user does not receive a targeted question. `Orchestrator.handle()` treats a non-`COMPILED` `CompilationResult` — whether `REJECT` or `ESCALATE` — with the same generic message: *"I'm sorry, I wasn't able to prepare your request for execution. Please try rephrasing or simplifying your request"* (`orchestrator.py:449-451`). No specific ambiguity is surfaced, and `clarification_attempt` (`compiler.py:275`, `orchestration_governor.py:213`) — the parameter that exists specifically to thread a clarification round across messages — has no live caller (`CURRENT_STATE.md`: *"a future caller (SupervisorWorker, ...) that doesn't exist yet"*; confirmed here by `grep`: every non-test reference is inside `orchestration_governor.py` and `compiler.py`'s own internals, never assigned from a live conversation turn). So even a perfect ambiguity detector would today produce the same dead-end apology a hard failure produces.

---

## B. Reproduction / characterization

`[PENDING]` The literal prompt could not be re-run end-to-end in this sandbox (no live model backend — the same limitation this repository's own `CURRENT_STATE.md` discloses for its Execution-Reliability work: *"this sandbox has no live model backend to re-run the literal end-to-end prompts against"*). What follows is what was, and was not, established by direct code tracing.

**Established by direct tracing (deterministic, not probabilistic):**
- `[FACT]` `use_k42_frontend = true` (`config/settings.toml:14`) — the K4.2 cognitive pipeline this trace follows is the live default, not a side branch (`CURRENT_STATE.md` itself is internally inconsistent about this across sync entries dated Aug 8 vs. Aug 27–28; this session's own fresh read of `settings.toml` resolves it in favor of `true`, matching the later, Aug-28-and-onward entries and `KNOWN_ISSUES.md`'s framing of the flag flip as a completed, non-vestigial change).
- `[FACT]` For "write a 1000 words story," `interpret_request()` produces one or more `IntentHypothesis` objects via `generate_hypotheses()` (an LLM call — see Section G), takes the top one unconditionally, and proceeds to `form_goals()` with no gate.
- `[FACT]` `discover_capabilities()` finds `LLM_COMPLETION` as the only candidate for any decomposed step of this request; its Jaccard match score against the literal request text will be at or near `0.0`, structurally, for the same reason `ADR-K4.2-H-13`'s own worked examples score `0.0` — a request describing what the user wants shares essentially no tokens with a capability description of what the capability *is*.
- `[FACT]` `_is_general_purpose_only()` (`planner.py:1374`) will therefore return `True` for this plan (every step's top candidate is the sole, general-purpose fallback), setting `ExecutionPlan.general_purpose_only = True`.
- `[FACT]` `compile()` passes `general_purpose_only=True` into the `ClarificationPolicy` governance action's metadata; `OrchestrationGovernor._evaluate_clarification_policy()` returns `None` (approve) immediately upon seeing that flag, before the confidence-threshold comparison ever runs (`orchestration_governor.py:179-206`).
- `[FACT]` Compilation proceeds to `COMPILED`; `WorkflowRuntime.execute()` runs; `CapabilityExecutorWorker` invokes the registered `LLM_COMPLETION` adapter, which is where the actual generation call — and the only point where the literal output length is determined — occurs.

**Two live, mutually exclusive possibilities this pass could not distinguish between, and the "stale task premise" check this project's `ways-of-working.md` calls for:**

`[PENDING]` 1. If the observed 466-word experiment was run **before** Sept 6, 2026 (`ADR-KERNEL-04`, DEBT-020), the constraint-checking machinery described in Section C did not yet exist at all — a 466-word output for a 1000-word request would have been returned with no disclosure of any kind, exactly as described in the governing task document. This is consistent with everything traced above.

`[PENDING]` 2. If it was run **on or after** Sept 6, 2026 against current `main`, the architecturally-correct behavior is: the 466-word output is returned, but with an appended disclosure — *"(Note: this response may not fully satisfy your request -- ...)"* — and an `orchestrator.response_incomplete` event (`orchestrator.py`, `ADR-KERNEL-04` Part D). The governing task's "Observed behavior" section does not mention a disclosure either way. If one was present and simply not mentioned in the task's framing, Finding B (Section C) is already substantially resolved architecturally, and the open question narrows to *whether the disclosure fired correctly for this exact case* — which turns on whether the extracted constraint was `HARD` by default (Section C confirms it is) and whether `"write a 1000 words story"` parses through `_extract_word_count_constraints` (`planner.py:319`) as an "at least 1000" floor or an "exactly 1000" target — a parsing detail worth a targeted unit test rather than further architectural investigation.

**Recommendation:** before any implementation work begins, reproduce this exact prompt against current `main` with a real model backend and record whether a disclosure was appended. This is a five-minute check that resolves an ambiguity this study cannot.

---

## C. Constraint-adherence finding (separate, per the task's own instruction to keep A and B apart)

`[FACT]` This is **not open**. `DEBT-020` was classified as a Kernel v1.0 freeze blocker by the project owner and resolved Sept 6, 2026 (`ADR_KERNEL_04_FALSE_COMPLETION_FIX.md`), with an addendum Sept 13, 2026 comparing it against an independently-developed alternative design and confirming the shipped fix as canonical. The mechanism, precisely:

1. `Constraint` (`planner.py:85`) gained `measure`/`comparator`/`target`/`is_measurable()`/`is_satisfied_by()`. Only word-count extraction is implemented (`_extract_word_count_constraints`, `planner.py:319` — "at least/at most/exactly/more than/fewer than N words," plus a bare "N words" fallback read as a floor). Item-count and file-coverage constraints share the data model but have no extractor yet — explicitly deferred, not attempted.
2. `ExecutionPlan` and `WorkflowDefinition` gained a `constraints: List[Constraint]` field (they had none before this fix — a more complete gap than "no quantitative field," per the ADR's own tracing).
3. `WorkflowResult` gained `constraint_violations: List[str]`; `WorkflowRuntime._run()` calls `_check_constraints()` (`workflow/runtime.py:162`) after computing node-level success — if a measurable `HARD` constraint (not `SOFT`) is violated, `success` flips to `False` and the violation is recorded. A genuine node error is never re-examined for constraint satisfaction.
4. `Orchestrator.handle()`'s K4.2 branch (`orchestrator.py:461` onward) checks `wf_result.constraint_violations` before treating `answer` as final — on a violation the output is **kept** (partial work still has value) but an honest disclosure is appended, and `orchestrator.response_incomplete` is emitted.

`[FACT]` Coverage: 37 dedicated tests (`tests/test_debt_020_false_completion.py`) across every comparator, boundary values, qualifier-phrasing overlap-safety, and five end-to-end `WorkflowRuntime.execute()` scenarios; 2 more (`tests/test_integration_full_pipeline.py::TestConstraintsSurviveRealPipeline`) proving a word-count phrase survives the **real** `interpret_request → plan → compile` pipeline, not a hand-built fixture.

`[FACT]` Explicitly and honestly not covered, per the ADR's own "What was explicitly not done": item-count/file-coverage extraction (data model ready, no extractor); the K4.2 branch's pre-existing, separate silent-drop of a genuine `wf_result.success == False` with no constraint violations (found while tracing this fix, flagged rather than folded in — a different, still-open gap); the legacy K2.2 fallback path (`use_k42_frontend=false`), which has no `Constraint` machinery at all — moot today since that flag is `true` and, per `ADR-KERNEL-04`'s own words, "an increasingly vestigial configuration."

`[INFER]` **Relationship to Finding A:** today the two are orthogonal by construction, not by design intent — constraint-checking runs only *after* generation completes, as a safety net on the way out, while the gap in Section A is entirely *upstream*, at the decision to generate at all. If Section A's gap were closed (a real sufficiency check before generation), this machinery does not become redundant — it becomes what selective-prediction literature calls a second line of defense: sufficiency-checking reduces how often generation starts on a materially underspecified request; constraint-checking catches the residual cases where a request looked sufficient but the generation still under-delivered against an explicit, extractable number. Recommend treating them as two backstops in series, not proposing to fold one into the other.

---

## D. Exact execution trace

```
User: "write a 1000 words story"
  │
  ▼
Orchestrator.handle()                              orchestrator.py:173
  │  use_k42_frontend=true (config/settings.toml:14) → K4.2 branch
  ▼
interpret_request(raw_text)                         intent.py:966
  │
  ├─ normalize_request(raw_text) → RawRequest        intent.py:391, 1008
  │
  ├─ generate_hypotheses(raw_request, ...)           intent.py:592, 1011
  │    → _build_hypothesis_prompt (LLM call #1)      intent.py:514
  │    → _parse_hypotheses(completion)                intent.py:531
  │    → List[IntentHypothesis]  (event: cognitive.intent_hypotheses_generated)
  │
  ├─ selected = hypotheses[0] if hypotheses else None    intent.py:1025
  │    ── no threshold check, no branch on confidence ──
  │
  ├─ IntentDimensions.complexity_estimate =
  │      _estimate_complexity(text, len(hypotheses))  intent.py:579-589, 1029
  │    ── computed, event-logged, never compared to anything ──
  │
  ├─ Intent(confidence=selected.score or 0.0, ...)    intent.py:1032-1040
  │    (event: cognitive.intent_interpreted)
  │
  └─ form_goals(intent, ...) → List[Goal]             intent.py:876, 1054
       Goal.confidence = intent.confidence − schema_penalty   intent.py:932
       (event: cognitive.goal_formed)
       ── still no threshold check anywhere in interpret_request() ──
  │
  ▼
planner.plan(goal, registry, ...)                    planner.py:1540
  │
  ├─ _extract_constraints(goal, ...)                  planner.py:507
  │    → _extract_word_count_constraints() finds "1000 words"
  │      as a measurable, HARD Constraint               planner.py:319
  │
  ├─ discover_capabilities() → only LLM_COMPLETION      planner.py:842
  │    is_general_purpose=True (ADR-K4.2-H-02)
  │    Jaccard match score ≈ 0.0 (request shares no tokens
  │    with "Generate text from a prompt via a language model.")
  │
  ├─ _estimate_confidence() → plan.confidence ≈ 0.0     planner.py:1341
  ├─ _is_general_purpose_only() → True                  planner.py:1374
  │    (comment at planner.py:1564: the confidence/governance
  │     check happens "at the Plan Compilation gate, not earlier")
  │
  └─ ExecutionPlan(confidence≈0.0, general_purpose_only=True,
                    constraints=[Constraint(word_count, HARD, 1000)])
  │
  ▼
compiler.compile(plan, clarification_policy, clarification_attempt=0)   compiler.py:269
  │  governance action metadata:
  │    confidence≈0.0, confidence_threshold=0.5,
  │    general_purpose_only=True, clarification_attempt=0, max_escalations=2
  ▼
OrchestrationGovernor._evaluate_clarification_policy()   orchestration_governor.py:158
  │  general_purpose_only is True →
  │  return None (approve — "nothing to decide here")   orchestration_governor.py:179-206
  │  ── EXEMPT from ClarificationPolicy, regardless of confidence ──
  ▼
CompilationStatus.COMPILED → WorkflowDefinition(constraints=[...])
  ▼
WorkflowRuntime.execute()                             workflow/runtime.py:294
  │  CapabilityExecutorWorker → AdapterRuntime.invoke() → ModelRouter
  │    ── the actual generation call; the only real resource commitment ──
  │  _check_constraints() after node completion         workflow/runtime.py:162
  │    if word-count HARD constraint violated: success=False,
  │    constraint_violations=[...]
  ▼
Orchestrator.handle() K4.2 branch, answer = wf_result.output    orchestrator.py:461
  │  if constraint_violations: keep output, append disclosure,
  │  emit orchestrator.response_incomplete             orchestrator.py:463-470 (ADR-KERNEL-04 Part D)
  ▼
Response to user
```

`[INFER]` The single largest fact this trace establishes: **zero code paths between the raw text and the committed `ExecutionPlan` ever ask whether the request is sufficiently specified.** The only gate in the entire pipeline is capability-match confidence at Plan Compilation, and it is structurally exempted for exactly this request's configuration.

---

## E. Problem definition

Grounded in OCBrain's own vocabulary rather than invented terms, and in the SAGE-Agent paper's (Section H) formal distinction:

- **Intent** — `[FACT]` OCBrain's own type: a `Intent` object (`intent.py:168`), *"A ranked, confidence-scored interpretation of one request."* Already exists; not redefined here.
- **Intent sufficiency** — `[INFER]` whether the selected `Intent`/`Goal` determines a plan and output the user would recognize as what they asked for, as opposed to determining only the *category* of request (OCBrain already computes category reliably — `dimensions.category = selected.label` — the gap is entirely about *content within the category*, not about topic classification).
- **Material ambiguity / missing information** — using the governing task's own test, now grounded: *would a different plausible resolution of the unknown produce a different extractable `Constraint`, a different `capability_type` match, or a materially different `WorkflowDefinition`?* For "write a 1000 words story," genre/tone/audience/POV are all unresolved and each would visibly change the generated text — material by this test. Length is *not* ambiguous — it was stated and is already captured as a `Constraint` (Section C).
- **Safe/defaultable missing information** — an unknown where OCBrain's existing `_extract_inferred_constraints()` (`planner.py:422`) or a system default produces a result no worse, in expectation, than asking would have been worth the interruption. Formatting minutiae, not thematic content.
- **Clarification-required state** — `[INFER]` does not exist as a first-class state today. `IntentLifecycle` (`intent.py:91`) already reserves the vocabulary for one: *"draft → interpreted → [clarification_pending → clarified] → superseded"* (`intent.py:94`), with an explicit comment that these two states *"belong to ClarificationPolicy escalation (K4.2 §2/§9, later milestones)"* — i.e., the enum values are already declared and simply never reached by any code path today. This is a second, independent piece of evidence (alongside `clarification_attempt`) that the project's own architecture already anticipated this exact gap and left a named, unused extension point for it.
- **User-delegated choice** — "surprise me," "use your judgment" — `[FACT]` no existing mechanism distinguishes this from ordinary silence on a dimension; both currently look identical (nothing was said) to whatever future sufficiency check gets built. Section 9's distinction has to be designed in, not inferred from present code.
- **Consequential ambiguity** — ties to reversibility (Section Q): today, with only `LLM_COMPLETION` registered, every consequence is "generate some text nobody is forced to use" — low-consequence by construction. This changes the moment a capability with external effects is registered.

---

## F. Decision boundary — where "is this sufficiently specified?" should be asked

`[INFER]` Recommend: **immediately after `form_goals()`, inside (or as a sibling call within) `interpret_request()`, before `discover_capabilities()`/`plan()` is invoked.** Reasoning, evidence-based rather than asserted:

- It is the earliest point at which `Goal.confidence`, `Intent.dimensions.complexity_estimate`, and the full set of already-parsed hypotheses (including the ones `selected = hypotheses[0]` currently discards) all exist simultaneously.
- It is *before* `_extract_constraints()`, `discover_capabilities()`, and decomposition — all of which do real, if inexpensive, work that a genuinely under-specified request makes wasted effort.
- It reuses `interpret_request()`'s own event-emission convention (`cognitive.intent_interpreted`, `cognitive.goal_formed`) rather than introducing a new observability path — consistent with Law 2 (Explicit State).
- It does **not** collide with `ClarificationPolicy`, which the Planner's own comment (`planner.py:1564-1571`) places deliberately later, "at the Plan Compilation gate" — a sibling check at Goal-formation time is additive, not a redesign of an existing, working, frozen-adjacent mechanism.

---

## G. Resource boundary — what must wait

`[FACT]` The pipeline is not "zero cost until execution" — `generate_hypotheses()` already makes one LLM call (`_build_hypothesis_prompt` → completion → `_parse_hypotheses`) before any decision point exists at all. This is unavoidable: OCBrain cannot know a request's category without some interpretation step, and this study is not proposing to remove that call.

`[INFER]` The boundary that matters is the one *after* that first, unavoidable classification-style call and *before*:
- `discover_capabilities()`'s decomposition/candidate-scoring work (cheap — pure local Jaccard scoring against registry metadata, no further model call, but still real work multiplied per decomposed step),
- and, decisively, `CapabilityExecutorWorker → AdapterRuntime → ModelRouter`'s actual generation call — the only step with a real cost/latency/token footprint comparable to what the user is asking to be generated.

A sufficiency check placed per Section F sits exactly at this boundary: after the one interpretation call already being paid for, before every subsequent cost. This matches the governing task's own Section 25 distinction between "cheap intent analysis" and "significant commitment to an interpretation" using OCBrain's actual cost structure rather than an assumed one.

---

## H. Research landscape — academic (bounded, real pass — not exhaustive)

Ten searches were run against current literature (Sept 2026); the following were most directly applicable. This is a representative scan, not the full sweep the governing task's Section 30 envisions — depth was prioritized over breadth given how much ground-truth work the repository itself required.

| Work | Mechanism | Applicability to OCBrain | Limitation |
|---|---|---|---|
| **"Structured Uncertainty guided Clarification for LLM Agents" (SAGE-Agent)**, arXiv 2511.08798, Oct 2025 | Models tool-argument clarification as a POMDP with Expected Value of Information (EVPI); **explicitly separates "specification uncertainty (what the user wants) from model uncertainty (what the LLM predicts)"** | This is the formal academic statement of exactly Finding A's empirical result — OCBrain's `plan.confidence` is model/match uncertainty; nothing measures specification uncertainty. Their EVPI framing is a candidate formalization for Section F/J's sufficiency signal, and their reported result (7–39% coverage gain while *reducing* question count 1.5–2.7×) is direct evidence against "ask more = safer" | Benchmarked on tool-argument disambiguation (ClarifyBench), not open-ended generation with stylistic freedom; porting the POMDP machinery wholesale would be disproportionate to OCBrain's single-capability configuration today |
| **"Knowing but Not Showing: LLMs Recognize Ambiguity but Rarely Ask Clarifying Questions,"** arXiv 2605.25284, May 2026 | Finds models often *internally* detect ambiguity without acting on it by asking | Independent academic confirmation of the exact pattern this study found in code: `_estimate_complexity`'s `ambiguity_signal` (from `hypothesis_count`) is computed and event-logged, never acted on. Detection existing without action being taken on it is a documented failure mode, not unique to OCBrain | Studied via prompting off-the-shelf chat models, not agentic pipelines with a separate governance layer like OCBrain's — the fix shape differs (OCBrain needs a wired *decision*, not better prompting) |
| **"Learning to Ask: When LLM Agents Meet Unclear Instruction" (AwN / NoisyToolBench),** arXiv 2409.00557, EMNLP 2025 | Taxonomy of instruction problems: missing information, ambiguous references, inaccuracies, infeasibility | Validates Section E's definitions independently; the "missing information" category maps directly onto the story example | Tool-calling focus; OCBrain's failure mode (single general-purpose capability) sits outside its taxonomy's assumed multi-tool setting |
| **Horvitz, "Principles of Mixed-Initiative User Interfaces"** (classic; summarized via Allen et al.'s four-level mixed-initiative framework) | *"Considering uncertainty about a user's goals: ... If there is ambiguity about what the user wants and wrong automation might harm the user, the system should ask for more information or not carry out the command."* Clarification/subdialogue-initiation is one of four defined initiative levels; empirically accounts for 27% of mixed-initiative interactions in human collaborative planning (Allen et al. 1999) | Foundational HCI precedent predating LLM agents by two decades — the problem and its shape are not new to conversational AI; strengthens Constitution Law 8 ("prefer patterns proven elsewhere") for whatever gets designed | Pre-LLM; says nothing about automatic ambiguity *detection*, only about the interaction pattern once ambiguity is known |
| **Rao & Daumé III (2018), "Learning to ask good questions: ranking clarification questions using expected value of perfect information"** | EVPI-based ranking for question *selection*, not just detection | Directly informs Section F/the task's own Section 8 (which question to ask first) — a formalization OCBrain could adopt for choosing among several unresolved dimensions (genre vs. length vs. audience) rather than an ad hoc order | Question-ranking only; doesn't address the upstream "should I ask at all" decision |
| **Selective prediction / reject-option learning** (Chow 1957; Geifman & El-Yaniv 2017; "Selective Prediction in AI" survey, 2026) | Formalizes abstention as a risk–coverage trade-off; explicitly warns: *"Deferral Messaging Paradigms: The way in which abstentions are communicated to downstream decision-makers fundamentally alters composite system accuracy"* | Directly diagnoses Section A's third finding — OCBrain's generic "I wasn't able to prepare your request" message is exactly the bad deferral-messaging pattern this literature warns against, not a minor UX nit | Framed for classification tasks with a ground-truth error rate; OCBrain's "error" (misaligned generation) is harder to measure directly |

**Additional grounding note, not from a search but from this project's own materials:** `docs/architecture/OCBRAIN_EXTERNAL_REPO_STUDY.md` (and V2/V3) already survey ~90 external AI frameworks as permanent architectural references per `PROJECT_INSTRUCTIONS.md` §1.1/§20.5's own instruction to consult them before proposing new architecture. This study did not re-read those documents in full given the size of the ground-truth work already required; **a follow-up pass should specifically check whether any of the ~90 already-surveyed frameworks address clarification/sufficiency**, since Law 8's evidence-over-assumption standard is better served by reusing that existing survey than by this study's own smaller external pass.

---

## I. Research landscape — GitHub / open source (bounded, real pass)

`[FACT]` The dominant convergent pattern in the current open-source agent ecosystem is **LangGraph's `interrupt()` primitive** and its associated Human-in-the-Loop middleware: a tool call (or an explicit decision point) pauses the execution graph, state is persisted via a checkpointing layer, and a human response resumes execution from exactly that point. LangGraph's own docs distinguish `respond` (the human is *answering*, as for a placeholder `ask_user` tool) from `reject` (the human is *denying* an action) — a vocabulary distinction directly useful for OCBrain's own Section 27 concern (clarification is not authorization).

`[INFER]` This is architecturally significant for OCBrain specifically: **`WorkflowRuntime` already has exactly this shape of primitive**, built for a different reason. `resume(definition, instance_id)` (`workflow/runtime.py:330`, `ADR-KERNEL-03`, DEBT-003) checkpoints after every node boundary and can continue a previously-interrupted execution, reusing completed nodes' results. This is the same "persist state, pause, resume later" mechanism LangGraph's checkpointing layer provides for clarification pauses — OCBrain built it for crash recovery, not conversation pauses, but the shape is identical. Per Constitution Law 8 (prefer convergent, evidence-backed patterns) and the governing task's own Section 38 (minimal-change principle, reuse existing structures), **this is a strong candidate for reuse rather than a new persistence mechanism** — see Section O.

`[FACT]` **Headroom** (`github.com/turangenesis/headroom`), a measurement study of human-in-the-loop escalation, frames escalation as *"selective classification under asymmetric cost with a fatiguing reviewer"* and demonstrates empirically that escalating more often can produce a *worse* safety outcome (reviewer fatigue causes rubber-stamping) — a decision-theoretic counterweight to any naive "when in doubt, ask" implementation. Directly relevant to the governing task's own Section 7 ("minimum necessary clarification, not maximum information collection") and Section 22 (loop control) — over-triggering is not merely annoying, it is a documented failure mode with its own name.

`[FACT]` **Researchify** (`github.com/Princ3mish/Researchify`) is a concrete, working example of the resource-boundary principle in Section G: a multi-agent research pipeline that pauses for clarification *"during the initial research phase"*, specifically before the expensive multi-source aggregation work begins — the same "ask before the costly part, not after" placement this study recommends for OCBrain.

---

## J. Architectural placement

`[INFER]` Recommend a **sibling policy to `ClarificationPolicy`**, not a modification of it and not a new subsystem/governor. Concretely (naming illustrative, not prescriptive — this is a study, not a design doc):

- A new, narrowly-scoped policy object — structurally identical in shape to `ClarificationPolicy` (a `confidence_threshold` and a `max_escalations`, per `planner.py:1037-1039`'s own stated minimalism: *"nothing beyond that is added"*) — but evaluated on an **Intent/Goal-level sufficiency signal**, not `ExecutionPlan.confidence`.
- Evaluated by the **same** `OrchestrationGovernor`, reusing the **same** `GovernanceVerdict.ESCALATE` outcome, the **same** `clarification_attempt`/`max_escalations` bounded-retry discipline already built and tested for `ClarificationPolicy` (`orchestration_governor.py:213-245`) — not a second governor, not a second escalation vocabulary.
- This satisfies Constitution Part V's Admission Test cleanly: Gate 1 (strengthens Invariant 1 and Law 6 directly, not mere convenience), Gate 2 (fits inside the existing `GovernanceKernel`/Policy pattern — no new kernel-level component), Gate 3 (states the problem, not a specific model — the signal computation can evolve without touching the governance shape).
- Placement in the pipeline per Section F: evaluated once, right after `form_goals()`, before `discover_capabilities()`.

`[INFER]` Explicitly **not** recommended: broadening `ClarificationPolicy` itself to absorb this question. Its docstring, its `confidence_threshold` semantics, and `ADR-K4.2-H-13`'s exemption logic are all specifically reasoned about capability-match confidence; folding a second, different kind of uncertainty into the same field would recreate the exact naming collision this study's Finding A diagnoses, one level down.

---

## K. Context / provenance model

`[FACT]` The exact taxonomy the governing task's Section 10 asks about (`USER_EXPLICIT`, `MODEL_INFERENCE`, etc.) does not exist in OCBrain today. `[FACT]` But the *pattern* it wants already has a working, ADR-ratified, frozen precedent: `ADR-K4.2-H-01`, "Layered Semantic Authority" — `RawRequest` is immutable (`@dataclass(frozen=True)`), `Intent.raw_request` is documented as *"a captured string value ... never a live/nested `RawRequest` reference,"* and the ADR's whole point was fixing a bug where a downstream layer's own diagnostic label (`intent.selected.label`) had been leaking backward into a field whose purpose was preserving the user's actual words.

`[INFER]` Recommend extending this exact pattern rather than building a new taxonomy: when the sufficiency check (Section J) has to fill in a default or record an assumption, it should be captured the same way `ADR-K4.2-H-01` already insists real user content be captured — as an explicitly-labeled field, never silently merged into `Goal.structured_form` as if the user had said it. `Goal` already has the room for this (`structured_form: Dict[str, Any]`, `intent.py:679-740`); a `resolution_origin` (or similarly-named) side-channel matching the confidence-inheritance pattern already used for `Goal.confidence` (`intent.py:932`) is a small, precedented addition, not a new subsystem.

---

## L. Future-learning boundary

`[FACT]` This does not need to be designed from scratch either — `K4.2.7`, "User Cognitive Model" (`core/cognitive/user_model.py`, `assemble_user_cognitive_model()`), already exists and is wired: `PlannerHint`s sourced from it reach the Planner (`CURRENT_STATE.md`: *"`PlannerHint`s from `assemble_user_cognitive_model()` reaching the orchestrator for the first time"*, Aug 28, 2026). `[INFER]` This is the conceptual boundary the governing task's Section 12 wants preserved for future learning — it already exists, as a *hint*, not an assertion, consumed downstream without being merged into what counts as the user's stated intent. The correct extension, when a future learning subsystem exists, is to make it another hint source feeding this same channel — not a second mechanism, and not something this study is proposing to build now.

---

## M. Verification boundary

`[FACT]` This section can be shorter than the governing task anticipated, because the premise needs correcting: the Verification/Critic/Evidence subsystem described in the task's Sections 15–21 as something Intent must be careful not to duplicate **is not wired into any live path today.** It exists as contracts only, on an unmerged branch (`feature/verification-critic-evidence-phase-c`), confirmed by `CURRENT_STATE.md` itself: *"Confirmed still absent: any code anywhere that actually calls into `core/verification/`."* `core/workers/evaluator.py`'s own architecture explicitly treats its measurement output as *"contextual, never authoritative"* regardless (per the frozen v2 architecture doc §30) — it was never meant to be a live verification authority either.

`[INFER]` So there is no live duplication risk today. The boundary question is still worth answering *for the future*, since Verification is roadmapped for post-freeze/post-C-MoE work. The project has already, independently, drawn exactly this line once: `ADR-KERNEL-04`'s Sept 13 addendum explicitly **rejected** porting a `CompletionStatus`/`UNKNOWN`-by-default design into the Kernel layer's constraint-checking, reasoning: *"separating 'an answer was produced' from 'the answer is correct' is, on reflection, Verification's question more than the Kernel's ... Building that separation into the Kernel layer now blurs a boundary just drawn on purpose."* `[INFER]` Recommend Intent-sufficiency follow the identical discipline, stated in the same terms this project already used once: **"is this task well-specified enough to act on" is a Kernel/Intent question; "is the eventual output correct or adequately evidenced" remains Verification's, whenever it lands** — reusing precedent rather than re-deriving the boundary.

---

## N. Verification consumption model

`[INFER]` Given M, there is nothing live to consume today. When Verification does land, the natural integration point is the same provenance channel proposed in Section K — a verified fact would enter as another labeled input alongside hints and defaults, never silently promoted to "the user's stated intent." No new consumption mechanism is recommended now; building one against a system that does not yet run would be exactly the kind of speculative state machine the governing task's Section 39 explicitly rules out.

*(Note, kept separate from this study's own findings: this project's memory records a chat-only decision, `ADR-KERNEL-05`, on the related-but-distinct CTX-AUTH-001b question — whether a generated candidate's provenance carries enough authority to influence an accepted `IntentHypothesis`. That decision is not reflected anywhere in the cloned repository — no `ADR_KERNEL_05` file exists in `docs/architecture/decisions/`, and a repo-wide `grep` for `AuthorityLevel` returns nothing. Per this project's own evidence-first rule, a chat-recorded decision is not repo ground truth until it lands; this study treats it as `[PENDING]` and does not build on it, though Section V flags the sequencing risk of two related, unmerged efforts touching the same file.)*

---

## O. Clarification lifecycle

`[INFER]` Recommend composing three pieces that already exist, rather than building a new one:

```
User request
     ↓
interpret_request() → Goal (as today)
     ↓
[NEW] sufficiency check (Section J) — sibling policy, same governance path
     ↓ ESCALATE                              ↓ approve (as today)
[NEW] specific question surfaced;      plan() → compile() → execute()
WorkflowRuntime checkpoints
current state (reusing the
existing resume()/ADR-KERNEL-03
mechanism, Section I) instead of
inventing new persistence
     ↓
User answers
     ↓
clarification_attempt incremented          IntentLifecycle transitions
(already-threaded parameter,               draft → interpreted →
compiler.py:275, orchestration_            clarification_pending →
governor.py:213 — currently unwired,       clarified (already-declared
not currently absent)                      enum values, intent.py:104-105,
     ↓                                      currently unreached)
Same Goal re-enriched with the answer
(via the provenance channel, Section K —
distinguishable from the original as
USER_CLARIFICATION-equivalent, not
re-asserted as if stated the first time)
     ↓
Re-run sufficiency check → ESCALATE again (bounded by max_escalations,
reusing the existing stall-to-SupervisorWorker pattern,
orchestration_governor.py:218-234) or approve → plan() → compile() → execute()
```

`[FACT]` Every piece labeled "already exists" above is a direct code citation, not a design proposal: `resume()`, `clarification_attempt`, and the two `IntentLifecycle` enum values are all present in `main` today, unused for this purpose. `[INFER]` This is what the governing task's Section 38 minimal-change principle looks like concretely for this codebase: the lifecycle the task describes in the abstract (Section 20) is not a new invention here — it is three already-declared, currently-disconnected pieces of OCBrain's own architecture, wired together.

---

## P. Task-change / Verification interaction

`[INFER]` Moot today per Section M — nothing exists downstream to invalidate or recheck. When Verification lands, recommend it inherit `ADR-KERNEL-04`'s addendum discipline (Section M) rather than have Intent's clarification lifecycle directly manipulate Verification lifecycle state.

---

## Q. Consequence / reversibility considerations

`[FACT]` Today, with only `LLM_COMPLETION` registered, every consequence of proceeding under ambiguity is "generate some text the user is not forced to use" — Constitution Invariant 8 already covers the adjacent case (*"Recommendations sourced from outside a single instance are never self-executing"*), and `core/sandbox/`'s `AdmissionGate` (Sandbox/Execution Fabric Phase 1, Sept 2026) already establishes a working precedent for OCBrain scaling scrutiny to an action's external effect — network-deny-by-default, explicit allowlisting required. `[INFER]` Recommend the same shape for clarification strictness: text generation with no side effects warrants the moderate, EVPI-style bar this study's Section F/H propose; any future capability that writes, sends, deletes, or otherwise has an external effect should inherit a stricter bar by construction, the same way `AdmissionGate` already treats network access — not by re-deriving reversibility per capability, but by keying the sufficiency threshold to whatever mechanism eventually classifies a capability as side-effecting (none exists yet; `CapabilityContract` has no such field today — a real gap, but out of this study's scope to design).

---

## R. C-MoE boundary

`[FACT]` C-MoE is confirmed research/architecture-proposal only — `CURRENT_STATE.md`: *"Capability *selection* (choosing among multiple candidate adapters for a `capability_type`) remains explicit future work reserved for the Cognitive Runtime/C-MoE."* No implementation exists to sequence against today. `[INFER]` The governing task's own hypothesized ordering (`PROJECT_INSTRUCTIONS.md` §28: Intent → Sufficiency/clarification → Planner → C-MoE → Execution) is therefore not a design decision this study needs to defend against a competing implementation — it simply matches where the sufficiency check in Section J already sits (before `discover_capabilities()`, which is what C-MoE will eventually extend). Recommend this ordering be stated explicitly in whatever ADR eventually implements Section J's policy, so a future C-MoE implementer inherits an already-sufficiency-checked `Goal`/`ExecutionPlan` rather than re-litigating the ordering.

---

## S. Evaluation and tests

`[INFER]` Recommend following this repository's own established idiom for exactly this kind of fix — `tests/test_debt_020_false_completion.py`'s shape (boundary values, phrasing variety, overlap-safety, real-pipeline integration tests alongside hand-built fixtures) is a strong, precedented template for a future `tests/test_intent_sufficiency.py`. Mapping the governing task's own Test A–N onto OCBrain's actual pipeline:

| Task's test | OCBrain-concrete version |
|---|---|
| A — under-specified request | `"write a 1000 words story"` — expect the new sufficiency check to ESCALATE (not `ClarificationPolicy`, which correctly stays silent per `general_purpose_only`) before `discover_capabilities()` is ever called; assert no `WorkflowRuntime.execute()` invocation occurred |
| B — sufficiently specified | e.g. `"write a 1000-word noir detective short story, first person, ending on a twist"` — expect approval, no escalation |
| C — delegated choice | `"write a story, surprise me"` — expect approval; requires Section E's delegation-detection, not present today |
| D — already known | genre stated earlier in a multi-turn context — requires `ContextMemory`/`assemble_user_cognitive_model()` participation (Section L's hint channel), not present in `interpret_request()` today; likely fails until that wiring exists — a legitimate acceptance-test gap to flag, not to silently skip |
| G — repeated clarification doesn't loop forever | reuse `orchestration_governor.py:218-234`'s existing `max_escalations` test pattern (`tests/test_k2_4_governance.py` already has the shape for `ClarificationPolicy`; mirror it) |
| L — constraint preservation | already covered — `tests/test_debt_020_false_completion.py` and `TestConstraintsSurviveRealPipeline` (Section C) |
| M — no unnecessary Verification | trivially true today (Section M) — worth a regression test once Verification is wired, not before |

`[INFER]` Metrics: `ClarEval`'s and SAGE-Agent's coverage-vs-question-count framing (Section H) is directly portable — measure how often the new check escalates on Test-A-style prompts (recall) versus Test-B-style prompts (precision/false-positive rate), the same two-sided evaluation `ADR-K4.2-H-13` itself implicitly ran when it verified its fix both fixed the reported bug *and* did not silently weaken genuine escalation for a real specific-but-weak capability.

---

## T. Minimal implementation recommendation (not implemented here)

`[INFER]` Smallest coherent change, composed entirely of extending things that already exist:

1. **Signal:** a new, distinct field — not reusing `plan.confidence`'s name or its Jaccard-based computation — populated at Goal-formation time. Starting ingredient: the `ambiguity_signal`/`hypothesis_count` component `_estimate_complexity` already computes and currently discards into an unused dimension — but strengthened per Section U's over/under-triggering risk, likely combined with "did `_extract_constraints()` find zero constraints in a category where at least one is normally expected" as a second, more specific signal, rather than length alone.
2. **Policy + governance:** a sibling policy object to `ClarificationPolicy` (Section J), evaluated by the same `OrchestrationGovernor`, producing the same `ESCALATE` verdict, reusing `clarification_attempt`/`max_escalations` verbatim.
3. **Surface + lifecycle:** replace the generic apology at `orchestrator.py:449-451` with a real, specific question when this new policy (not the existing `CompilationRejected` path) is the reason; wire `clarification_attempt` to actually increment across a real conversation turn; use `WorkflowRuntime.resume()`'s existing checkpoint mechanism (Section I) to persist state across the pause rather than building new persistence; activate the two already-declared, currently-unreached `IntentLifecycle.CLARIFICATION_PENDING`/`CLARIFIED` states.
4. **Provenance:** a `resolution_origin`-style field on `Goal`, following `ADR-K4.2-H-01`'s existing layered-authority precedent (Section K), so a system default is visibly distinguishable from what the user actually said, including after a clarification answer is merged back in.

`[INFER]` Every one of the four pieces above extends an existing, already-ADR'd or already-declared OCBrain structure. None requires a new governor, a new persistence layer, a new event type, or a new top-level entrypoint — consistent with the governing task's Section 38 instruction to prefer reuse and with Constitution Gate 2 (adapter/capability/composition before new kernel content).

**This remains a design sketch, not a specification** — per the task's own constraint, no code is proposed here, and per the Architecture Freeze Principle, this needs its own ADR before a single line changes.

---

## U. Risks / failure modes

- `[INFER]` **Re-creating `ADR-K4.2-H-13`'s own bug one level up.** A naive length- or hypothesis-count-based sufficiency signal risks over-triggering on short-but-clear requests exactly the way the original `ClarificationPolicy` over-triggered on short-but-clear ones before `ADR-K4.2-H-13`. Mitigation: transplant that ADR's own fix discipline — escalate only when a materially different plausible resolution genuinely exists (Section E's test), not merely when text is short — rather than reusing `_estimate_complexity` unmodified.
- `[INFER]` **Under-triggering via the same crude heuristic in the other direction** if `_estimate_complexity` is reused naively — length alone says nothing about whether the *content* is determined. Mitigation: the two-signal approach sketched in Section T item 1.
- `[FACT]` **Interaction with the still-open, chat-only-decided CTX-AUTH-001b thread.** Both this study's recommendation and the CTX-AUTH-001b authority mechanism (Section N's note) touch `core/cognitive/intent.py`'s acceptance/field surface. Per this project's own explicit sequencing (recorded in project memory, not yet in the repo): CTX-AUTH-001b's ADR must land and its mechanism must be decided before `IntentHypothesis` itself is touched. Any future implementation of this study's recommendation should be sequenced to avoid colliding with that ADR, not to race it — a real coordination risk, out of scope for this study to resolve, but worth flagging loudly for whoever schedules the two.
- `[FACT]` **Architecture Freeze Principle applies.** `core/cognitive/intent.py`/`planner.py`/`compiler.py` all touch K4.2-H1's frozen, "SAFE-TO-DEPEND-ON" contracts (`RawRequest` immutability, the three-entrypoint signatures, `trace_id`/`operation_id` semantics). Section T's recommendations were designed to add fields and a sibling policy rather than modify any frozen contract, but this needs explicit confirmation in the eventual ADR, not assumed here.
- `[INFER]` **Section S's Test D (already-known-from-context) is currently unimplementable** without also wiring Section L's hint channel into `interpret_request()` itself, which it does not reach today (`PlannerHint`s reach the Planner, not Intent). A minimal-scope implementation that skips this would satisfy Tests A/B/G but visibly fail D — worth deciding explicitly rather than discovering during implementation.

---

## V. Open questions

1. `[PENDING]` Was the observed 466-word experiment run before or after Sept 6, 2026 (`ADR-KERNEL-04`)? Determines whether Finding B is fully historical or has a residual live gap (Section B).
2. `[PENDING]` Constitution Invariant 1's *"where genuinely ambiguous, verify"* — does "verify" mean *clarify with the user*, or *route through Verification*? The Constitution's own text is genuinely ambiguous on this point (Section M/A) and would benefit from its own clarifying note, ideally before either mechanism is built further.
3. `[PENDING]` Sequencing between this study's eventual implementation and CTX-AUTH-001b's ADR-KERNEL-05 (chat-decided, not yet in the repo) — both touch `intent.py`; order matters and is not this study's to decide (Section U).
4. `[PENDING]` This study's Finding A is characterized against today's single-capability (`LLM_COMPLETION`-only) configuration. `ADR-K4.2-H-13` itself notes the general-purpose exemption "will naturally and automatically narrow in scope as real, specific capabilities are registered." Once a second, specific capability exists, `ClarificationPolicy` will fire far more often on its own axis (capability ambiguity) — worth re-verifying Finding A's practical severity at that point rather than assuming it's static.
5. `[PENDING]` Whether `docs/architecture/OCBRAIN_EXTERNAL_REPO_STUDY.md`'s ~90 already-surveyed frameworks contain clarification/sufficiency-relevant patterns this study's smaller external pass missed (Section H's own noted gap).

---

## Final questions — direct answers, cross-referenced to fuller sections

1. **What precisely causes OCBrain to act on materially under-specified requests?** No code path checks intent sufficiency at all; the one confidence gate that exists measures a different thing (capability-match) and is structurally exempted for the current single-capability deployment. (A, D)
2. **Why does the current Intent path consider the story request sufficiently actionable?** It never considers the question — `interpret_request()` computes confidence/complexity signals and never branches on either. "Sufficiently actionable" is never evaluated; the request simply isn't stopped. (D)
3. **Where should "is this sufficiently specified?" live?** Immediately after `form_goals()`, before `discover_capabilities()`. (F)
4. **Smallest architecturally correct change?** A sibling policy to `ClarificationPolicy`, same governance path, reusing `clarification_attempt`, `resume()`, and the already-declared `IntentLifecycle` clarification states. (J, O, T)
5. **How should the system distinguish explicit intent, clarification answers, context, defaults, and inference?** Extend `ADR-K4.2-H-01`'s existing Layered Semantic Authority pattern rather than build a new taxonomy. (K)
6. **How should conflicting context resolve without letting future learning override current instructions?** Not yet a live question — `assemble_user_cognitive_model()`'s hints already arrive as advisory, not authoritative, and the same discipline extends cleanly. (L)
7. **How does clarification converge without unnecessary questions or loops?** Reuse the already-built, already-tested `max_escalations`/stall-to-`SupervisorWorker` bound (`orchestration_governor.py:218-234`). (O)
8. **Where should significant resource commitment be blocked?** After the one unavoidable hypothesis-generation call, before capability discovery and, decisively, before the generation call itself. (G)
9. **Exact boundary between Intent clarification and Verification?** No live boundary conflict exists — Verification isn't wired into any path yet. The project's own `ADR-KERNEL-04` addendum already drew this exact line once ("is it produced" is Kernel; "is it correct" is Verification) and that precedent should be reused. (M)
10. **Which existing Verification outputs can Intent safely consume?** None exist in a live path to consume. (M, N)
11. **How should a clarified task interact with existing Verification lifecycle?** Moot today; inherit the same addendum's discipline when Verification lands. (P)
12. **What must be preserved now for future learning without building it?** The existing hint-channel boundary (`assemble_user_cognitive_model()`) already does this — nothing new needed. (L)
13. **C-MoE's role before/after sufficiency?** After — C-MoE doesn't exist yet, and the recommended check sits before the capability-discovery step C-MoE will eventually extend. (R)
14. **How do clarification and authorization/governance stay distinct?** They already share one governance mechanism (`OrchestrationGovernor`) safely today, distinguished by verdict semantics, not by separate systems; the same governor hosting two sibling policies (Section J) preserves this. (J, Q)
15. **What does the 466-vs-1000 result reveal about constraint adherence?** Nothing currently open — `ADR-KERNEL-04` (Sept 6, 2026) already implemented, tested, and shipped word-count constraint checking with an honest-disclosure fallback; the only unresolved piece is whether the observed experiment predates that fix. (B, C)
16. **What acceptance tests would demonstrate improvement without redundant Verification or wasted resources?** Test A/B/G are implementable against existing infrastructure today; Test D requires the hint-channel wiring flagged as a real, undecided scope question. (S, U)
17. **Smallest implementation scope avoiding a general redesign?** The four-item sketch in Section T — entirely additive to existing, already-ADR'd structures, no new subsystem. (T)

---

*Sources cited throughout are file paths and line numbers from a fresh, unauthenticated clone of `https://github.com/1h0lde4/ocbrain-v4.1` taken this session, plus `docs/architecture/decisions/ADR_K4_2_H_01/H_02/H_13`, `ADR_KERNEL_04`, `OCBRAIN_KERNEL_CONSTITUTION.md`, `CURRENT_STATE.md`, and `KNOWN_ISSUES.md` from that same clone, plus the external sources named inline in Sections H–I.*
