# Agent Evaluation & Reliability Lab — Research & Architecture Report

**Status:** Slice 1 (research + architecture + ADRs) complete. No contracts or runtime code included in this slice.
**Track:** Parallel / non-blocking. Does not modify K4.2, the Execution Reliability Track, or any Cognitive-Phase-Future item.
**Author:** Claude (OCBrain session), 2026-08-28
**Branch:** `eval-lab/research-and-architecture`
**Mission source:** three successive drafts of "OCBrain — Agent Evaluation & Reliability Lab"; this report follows the final ("Master Parallel Research + Architecture + Implementation Mission") draft, noting where it sharpened earlier drafts.

---

## 0. Executive Summary

This report inspects the live repository, surveys the current (as of August 2026) external landscape for agent evaluation, and proposes an architecture for an OCBrain-native Agent Evaluation & Reliability Lab. It intentionally stops short of writing contracts or code — per the mission's own slice plan, Slice 1 is research, architecture, and ADRs.

Three findings from repository recon materially change the shape of the proposal relative to what the mission brief assumed:

1. **No official "K4.3" milestone exists**, and **"K4.4" is explicitly disclaimed** by `IMPLEMENTATION_ROADMAP.md` as an informal label used in one report, not a real roadmap number. The real state is: K4.2 (all 9 packets) complete; an "Execution Reliability Track" with a merged baseline and two open, explicitly-deferred debt items (DEBT-015, DEBT-016); and an unscoped "Cognitive Phase — Future (Post-Kernel)" bucket that contains C-MoE. The milestone-classification section of this report (§7) uses the mission's requested category names but maps each to what actually exists.
2. **`EvaluatorWorker` and `ReflectionWorker` already exist** (`core/workers/evaluator.py`, `core/workers/reflection.py`, K4.2 Packet 07) and already produce `EvaluationRecord`s and reflection `KnowledgeEntry`s. This is an in-loop, single-task, self-assessment mechanism — a different concept from the Lab's job of external, evidence-backed verification across runs. The naming collision is real (both use "evaluat-") and is addressed directly in the architecture (§4.5) and in ADR-LAB-02.
3. **There is no real existing evaluation infrastructure to build on or displace.** `evals/run_eval.py` is a 75-line placeholder against a mocked subject call and a 10-question trivia dataset — not a foundation, not a conflict. It should be treated as superseded once the Lab exists (not deleted in this slice; flagged in §8).

The proposed architecture keeps the Lab as a new top-level package (`eval_lab/`, sibling to `core/`), consuming the runtime's existing event backbone through an adapter rather than a new parallel event system, and treating in-loop self-evaluation as one input signal among several rather than as ground truth. Four ADRs are proposed (all status `Proposed`, pending your review) covering identity/layering, the runtime boundary, evaluator/evidence/judge architecture, and versioning.

---

## 1. Repository Ground Truth

(Established by direct inspection of `1h0lde4/ocbrain-v4.1@main`, 2026-08-28. Superseding any assumption in the mission brief where they conflict — per the project's own §18.2.1 override rule, `CURRENT_STATE.md` / `IMPLEMENTATION_ROADMAP.md` / `KNOWN_ISSUES.md` are authoritative.)

| Question | Answer |
|---|---|
| Is K4.2 (Cognitive Front-End) done? | Yes. All 9 packets complete, H1 and H2 both frozen/reviewed. Live behind `[runtime] use_k42_frontend`, now enabled following the 2026-08-27 upload of `core/cognitive/*`. |
| Does an official "K4.3" exist? | No. Not used anywhere in `CURRENT_STATE.md` or `IMPLEMENTATION_ROADMAP.md`. Future cognitive work (including C-MoE) sits in an unscoped "Cognitive Phase — Future (Post-Kernel)" list. |
| Does an official "K4.4" exist? | No. `IMPLEMENTATION_ROADMAP.md` explicitly notes this label is informal, used only inside one report. The real name is the **Execution Reliability Track** — deliberately orthogonal to the K4.2.x campaign. |
| What's the Execution Reliability Track's actual state? | Baseline merged 2026-08-27 (commit `609ebfaa`, following the `7ca7f35` `ExecutionBudget` constructor fix). Two unreconciled watchdog code paths still coexist: model-router-facing (`core/runtime/execution_watchdog.py`, `progress_monitor.py`) and graph-aware (`core/runtime/watchdog.py`, `progress.py`, `execution_graph.py`, `projection.py`), tracked as **DEBT-016**. **DEBT-015**: no operation-identity concept exists yet — a retry cannot tell whether it should redo the same logical operation or respond fresh. Further evolution (the `Operation`/`ExecutionAttempt`/`ExecutionSnapshot` proposal) is explicitly deferred pending its own ADR — it has not been implemented. |
| Is there a "Kernel v1.0 freeze"? | In progress, not declared. `docs/Bugs Hunt & fix reports/KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md` and `docs/reports/KERNEL_V1_0_FINAL_ARCHITECTURE_AUDIT_REVISION.md` exist; this report does not assume freeze status either way and treats "POST-KERNEL-FREEZE" as a real future boundary. |
| What is the event backbone? | Fragmented across three mechanisms, already tracked as debt (DEBT-004/005): `EventBus` (in-process pub/sub, no persistence), `EventStream` (durable, append-only, SQLite WAL, supports replay and `create_checkpoint()`), and `KnowledgeEvent` (L4 archive). `EventStream` is the closest thing to a canonical durable log and is the right primary source for a trace adapter, but it does not carry 100% of what happens (some progress signal is `EventBus`-only, and DEBT-003 notes `WorkflowRuntime` doesn't yet call `create_checkpoint()` for resume). |
| Does an in-loop "evaluator" already exist? | Yes — `EvaluatorWorker` (`core/workers/evaluator.py`) and `ReflectionWorker` (`core/workers/reflection.py`), K4.2 Packet 07, stateless `AbstractCognitiveWorker` subclasses producing `EvaluationRecord`s and `KnowledgeEntry` reflections respectively, as part of a single task's own post-execution self-critique. This is **not** the Lab. See §4.5. |
| Is there existing evaluation infrastructure? | `evals/run_eval.py` (75 lines) + `evals/dataset.json` (10 general-trivia Q&A pairs) is a placeholder script with a mocked subject call (`mock_ocbrain_call`, literally echoes the query). No real scoring, no trajectory concept, no persistence. Not worth building on; safe to supersede. `data/evals/{coding,knowledge,system_ctrl,web_search}.json` appear to be similar scratch fixtures. |
| ADR conventions? | Two schemes coexist already: `ADR-001..008` embedded in the kernel architecture doc, and standalone `ADR-K{phase}-NN` files indexed in `docs/architecture/decisions/ADR_INDEX.md`. A third scheme for Lab-track decisions (`ADR-LAB-NN`) is consistent with existing practice and keeps Lab decisions clearly out of the K-numbered kernel sequence. |
| Report conventions? | `docs/reports/<ALL_CAPS_TITLE>.md`, e.g. `WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md`. This report follows that convention rather than the generic `docs/research/...` path the mission brief suggested, per the brief's own instruction to prefer repository convention. |

**One unrelated observation, out of scope for this track:** both `core/learning/evaluator.py` and a separate top-level `learning/evaluator.py` exist, mirroring the DEBT-016 duplication pattern seen in the watchdog code. Not investigated further here — flagging only so it isn't mistaken for something this track touched.

---

## 2. Systems Studied (External Research Sweep)

All findings below are from a fresh search pass on 2026-08-28, not from training-data recall, since several of these move fast enough that a seven-month-old snapshot would be stale.

**Inspect AI / Inspect Evals** (UK AI Security Institute) — separates `Task` / `Dataset` / `Solver` / `Scorer`, with sandboxed execution, checkpointing, and parallel/batch runs. The composition boundary (a task doesn't know how it will be scored; a scorer doesn't know how the solver produced its output) is exactly the separation the Lab needs between "subject" and "evaluator." Adopt the composition principle; don't adopt Inspect as a dependency.

**LangChain AgentEvals** — exposes multiple trajectory-comparison strategies (strict/ordered, unordered, subset, superset, LLM-judged). Useful confirmation that "one canonical trajectory comparison" is the wrong assumption — OCBrain needs at least state-equivalence and goal-equivalence modes because tool-call order is frequently not semantically meaningful (e.g., two independent read-only lookups).

**AgentBoard** — progress-aware, partial-credit evaluation instead of binary pass/fail; explicitly designed to diagnose *where* a multi-turn trajectory stalled, not just whether it finished. Directly supports the mission's checkpoint/progress model (§42–43 of the final brief).

**τ-bench / τ²-bench / ReliabilityBench / τ-Rec** — τ-bench established `pass^k` (all of k independent trials must succeed) as a stricter reliability measure than `pass@k` (at least one succeeds), state-based verification against ground-truth environment state, and policy-following under a scripted user. τ²-bench adds dual control (user *and* agent can both act on the environment). **ReliabilityBench** (2026) extends this family specifically with fault injection and stress conditions — directly relevant to §69 (Failure Injection) and worth tracking as a template for OCBrain's own fault-injection suite.

**METR time-horizon methodology** — human-calibrated task duration, logistic success-probability-vs-duration curves, 50%/80% time horizons. METR's own published estimate as of mid-2026 put the horizon-doubling time near 4.3 months (accelerated from an earlier ~7-month estimate), evaluated across current frontier models with an explicit caveat that measurements above ~16 hours are unreliable given the current task suite. The methodology is the valuable part; the specific curve-fitting is expensive and should be deferred (mission §50 agrees: build the data foundation now, not the full statistical package).

**AgentDojo / AgentHarm / Agent Security Bench / OS-Harm / SafeArena / WASP** — AgentDojo pairs 97 legitimate user tasks against 629 prompt-injection attack cases across 4 tool domains, scoring utility and attack-success independently (an agent can complete the task *and* fall for the injection — these are different outcomes, matching this mission's "SUCCESS + INVALID PROCESS" category). AgentHarm pairs 110 harmful/110 benign multi-step tasks over ~104 simulated tools to check whether safety training survives being embedded in an agentic tool-use loop rather than a single chat turn. The pattern worth adopting: benign/adversarial task *pairs*, not adversarial tasks in isolation, so a safety regression is measurable as a delta.

**OpenTelemetry GenAI semantic conventions** — as of mid-2026 sit around spec v1.41–1.42 and are still explicitly marked experimental (span names like `invoke_agent`/`execute_tool`, attributes like `gen_ai.usage.input_tokens`, `gen_ai.output.messages`). Current practitioner guidance is to adopt the span/attribute *shape* but isolate the literal convention strings behind a thin mapping layer, since the spec is still moving (there was a repository reorganization as recently as June 2026). This matches the mission's own instruction to treat OTel as an adapter, not a dependency — now with a concrete reason (spec churn) rather than just a principle.

**Langfuse / Braintrust / Promptfoo** — all three now converge on the same shape: datasets of cases → scorers (deterministic + LLM-judge) → experiments that diff two runs over the same dataset → regression gates in CI. None of them solve execution-instance isolation, task-mutation evaluation, or evaluator-integrity/anti-gaming — those are OCBrain-specific needs the Lab has to build itself. Adopt the dataset/experiment/scorer shape; the differentiator for OCBrain is trajectory depth and integrity, not the CRUD layer around it.

**AgencyBench** (arXiv:2601.11044) — long-horizon (multi-hour, ~1M-token context, ~90 tool calls/scenario) benchmark using a "Query / Deliverable / Rubric" triad with automated rubric scoring (threshold typically 60% rubric satisfaction) specifically to remove the human-in-the-loop bottleneck that limits how many trials you can actually run. The rubric-triad shape maps cleanly onto this mission's checkpoint-predicate model (§42).

**GauntletBench** (arXiv:2606.14397) — a modular environment + application + task-suite + automated-evaluation-engine pipeline, deliberately built on *less-familiar* applications specifically to resist contamination (SOTA agents score 19% vs. 80%+ for non-expert humans). Directly useful precedent for §17's contamination concerns: an evaluation suite's own popularity is itself a contamination risk.

**WildClawBench / Claw-Eval** (arXiv:2605.10912) — frames prior evaluation protocols (rule-based, executable, state-based) as each individually blind to *some* failure mode (side effects, superficial success, intermediate misbehavior), and proposes a hybrid protocol combining deterministic state/execution checks with semantic judgment over auditable evidence, plus deliberate error injection to catch agents that "finish without actually completing the task." This is close to a direct confirmation of this mission's own layered evaluator design (§29–32) from an independent source.

**LLM-as-judge bias & calibration** — current (2026) practice separates five documented biases: position (favors first/second slot in pairwise), verbosity (15–30 point score inflation for longer answers, original measurement from Wang et al. 2023/arXiv:2305.17926), self-preference (a judge scores its own model family 10–25% higher — Wataoka et al. 2024/arXiv:2410.21819, extended to rubric-based judging by Pombal et al. 2026/arXiv:2604.06996), format bias, and calibration drift. A 2026 RAND Corporation study found frontier judges exceeding 50% error rates on adversarial bias benchmarks despite ~80% accuracy on easy/controlled cases — i.e., judges are *not* uniformly reliable and the unreliability is concentrated exactly where it matters (close calls). Current mitigation practice: pairwise comparison with both orderings run, cross-family judging (never use the same model family as both generator and judge), 3-judge ensembles from 3 different families for high-stakes decisions, Cohen's kappa calibration against a human-labeled sample refreshed on a defined cadence (monthly is a commonly cited default), and a versioned judge identity tuple of `(judge_model_id, rubric_version, prompt_template_hash)` treated as an eval-suite migration whenever it changes, not a silent config edit.

**Metamorphic testing** — an established software-testing technique (Chen et al. 2018 survey) now being extended to LLMs/agents (e.g., MORTAR for multi-turn dialogue systems, 2024). The core idea — apply a transformation expected to preserve some invariant, then check the invariant holds on the new output — is a good fit for exactly the case this mission calls out (§53/§16): OCBrain has no single gold answer for most tasks, but it does have invariants ("goal preserved under a harmless paraphrase," "correctness unaffected by reordering independent constraints").

**Benchmark contamination** — a substantial and current literature (2025–2026) confirms this is not a theoretical risk: audits have found contamination in double-digit percentages of well-known suites, and the "SWE-bench illusion" paper (Liang et al. 2025/arXiv:2506.12286) specifically showed frontier models on SWE-bench sometimes succeed by recalling rather than solving. Two mitigation patterns worth adopting: **private benchmarking** (evaluation data stays confidential; only results are published) and **dynamic benchmarking** (rotate in cases built from information after each model's training cutoff). Both map directly onto the mission's benchmark-partition requirement (§17/§61): development / validation / public-regression / private-holdout / adversarial.

### Comparative matrix (condensed)

| System | Eval unit | Verification | Repeated trials | Adversarial | Local/offline | OCBrain takeaway |
|---|---|---|---|---|---|---|
| Inspect AI | Task→Solver→Scorer | Deterministic + model-graded | Supported | Via sandboxing | Yes | Adopt composition boundary |
| AgentEvals | Trajectory | Match strategies (exact/subset/semantic) | N/A | No | Yes | Adopt multi-mode trajectory comparison |
| AgentBoard | Multi-turn trajectory | Progress-aware, partial credit | Limited | No | Yes | Adopt progress/checkpoint model |
| τ-bench family | Env state + policy | State-based + rule | pass^k native | ReliabilityBench: yes | Yes | Adopt pass^k, state-based oracle |
| METR | Task w/ human baseline | Success curve vs. duration | Across models | No | Partial | Adopt data model, defer curve-fitting |
| AgentDojo/AgentHarm | Benign+attack task pairs | Utility ⊥ attack success | Some | Yes (core focus) | Yes | Adopt paired benign/adversarial cases |
| OTel GenAI | Span/trace | N/A (interchange) | N/A | N/A | Yes | Adapter only, isolate convention strings |
| Langfuse/Braintrust/Promptfoo | Dataset case | Deterministic + LLM judge | Yes | Limited | Partial (SaaS-leaning) | Adopt dataset/experiment/scorer shape only |
| AgencyBench | Long-horizon task | Rubric triad, automated | N/A | No | Partial | Adopt rubric/checkpoint shape |
| GauntletBench | Vision-grounded task | Automated engine | N/A | No (contamination-focused) | Yes | Adopt "unfamiliar surface" contamination defense |
| WildClawBench | Hybrid trajectory | State+exec+semantic+injection | N/A | Yes | Yes | Corroborates layered evaluator design |

---

## 3. Evaluation Target & Trust Model (adopted from the final brief, §2–3, §19)

Three things get evaluated separately and must never collapse into one verdict:

```
SUBJECT        — did OCBrain actually accomplish the task?
TRAJECTORY     — did it get there through a valid, safe, efficient, recoverable process?
EVALUATION     — can the measurement itself be trusted?
```

Five scoring dimensions apply within that: **correctness**, **groundedness/evidence**, **trajectory/process**, **safety/governance**, **performance**. Reliability is a cross-run property measured over repeated trials of all five, not a sixth dimension.

Trust boundary: `SUBJECT TRUTH` (environment/runtime state) → `TRAJECTORY TRUTH` (what the agent did) → `EVALUATION TRUTH` (what an evaluator concluded from trusted evidence). Evaluation annotations are additive and versioned; they never overwrite trajectory truth, and the subject can never write evaluation truth.

---

## 4. Proposed Architecture

### 4.1 Package boundary

New top-level package: **`eval_lab/`**, sibling to `core/`, `evals/`, `tests/` — **not** nested under `core/`. Two reasons, both grounded in recon rather than preference:

- The runtime-independence invariant (`OCBrain Runtime` must run without the Lab) is easier to keep true, and easier to verify by inspection (`grep -r "eval_lab" core/` should return nothing), if the Lab isn't inside the same package tree the runtime imports from by convention.
- **Naming collision avoidance**: `core/workers/evaluator.py` already owns "evaluator" as a concept (the in-loop `EvaluatorWorker`). Nesting the Lab under anything spelled `core/evaluation/` invites exactly the kind of accidental cross-wiring DEBT-016 shows this codebase is already prone to when two things share a name and a directory.

`evals/run_eval.py` should be treated as superseded once `eval_lab` has an equivalent smoke case — not deleted in this slice (out of scope; flagged for a follow-up commit once there's something to replace it with).

### 4.2 EvaluationRun (primary durable object)

As specified in the brief (§20–21 final draft): one `EvaluationRun` per execution attempt, referencing (not embedding) `BenchmarkDefinition` → `TaskDefinition` → `EvaluationCase` → `ExecutionReference` → `Trajectory` → `EvaluatorResult[]`. Identity fields kept fully distinct (no collapsing `task_id`/`task_instance_id`/`execution_instance_id`/`evaluation_run_id` — this repo already knows what happens when similar-but-distinct concepts get merged: see DEBT-015's whole premise, which is that `trace_id` doesn't currently distinguish a retry from a new operation).

### 4.3 Trace adapter

```
EventStream (durable, primary)  ─┐
EventBus (in-process, sampled)  ─┼─→  Trace Normalizer  →  EvaluationTrajectory
KnowledgeEvent (L4, sampled)    ─┘
```

Given the existing fragmentation (DEBT-004/005), the adapter treats `EventStream` as the canonical source (it's durable and already supports replay/checkpointing) and treats `EventBus`/`KnowledgeEvent` emissions as supplementary signal it may opportunistically fold in, never as something the trajectory depends on for correctness. This also means the trace adapter is naturally forward-compatible with DEBT-004/005 eventually being resolved — when the runtime unifies its event backbone, the adapter's job gets simpler, not different.

The adapter must special-case **two** watchdog/progress-monitoring event families (model-router-facing vs. graph-aware, per DEBT-016) rather than assuming one canonical schema, until DEBT-016 itself is resolved as its own packet. This is called out explicitly so a future contributor doesn't "fix" the adapter by deleting one branch.

### 4.4 Evaluator layers

Deterministic → structural/semantic → LLM judge → human, in that order of both preference and trust (per the brief's gold-standard hierarchy, §36 final draft), corroborated independently by WildClawBench's hybrid-protocol argument above. Judge layer specifics, grounded in the bias/calibration research in §2:

- Judge identity is a versioned tuple: `(judge_model_id, rubric_version, prompt_template_hash)`. Changing any element is an eval-suite migration, not a config edit.
- Default posture: cross-family judging (the judge is never the same model family as the subject being evaluated, to avoid self-preference bias) and both-orderings pairwise comparison where applicable (position-bias mitigation).
- A judge score always carries a confidence, and low-confidence or human/deterministic-disagreeing judge output routes to the human-review queue rather than silently winning.

### 4.5 Relationship to `EvaluatorWorker` / `ReflectionWorker`

These K4.2 workers produce in-loop, single-task self-assessment (`EvaluationRecord`, reflection `KnowledgeEntry`) as part of one execution's own process. The Lab's trace adapter should consume their output as **one input feature** on the trajectory (an agent's self-critique is itself an evaluable data point) — and must never treat it as ground truth. This is a direct instance of the mission's own "no self-referential evaluation" invariant (§31/91 in earlier drafts): the agent evaluating itself and the Lab evaluating the agent are different trust levels, even when the self-evaluation is well-built.

### 4.6 Evaluator integrity / anti-gaming / evaluator mutation testing

Both the final brief and independent research (metamorphic-testing literature, WildClawBench's injected-error methodology) converge on the same idea from different directions: an evaluator's correctness has to be tested the same way the subject's correctness is tested. Concretely, this slice's architecture reserves a `eval_lab/integrity/` boundary for:

- **Anti-gaming fixtures** — deliberately adversarial subjects (tampered evidence, forged PASS markers, post-verification artifact edits) that a correct evaluator must catch.
- **Evaluator mutation testing** (the final brief's new §40, not present in the earlier two drafts) — deliberately weaken an evaluator (invert a condition, drop a required check, ignore one tool failure) and confirm the evaluator test suite notices. This is mutation testing applied to the evaluator itself, distinct from anti-gaming (which tests whether the evaluator resists a malicious *subject*) — the mutation suite tests whether the evaluator resists its own bit-rot.

Where the kernel already has tamper-evidence or hashing primitives, the Lab should use them rather than build a parallel cryptographic system — this needs a short, targeted look at `core/governance/` and any existing audit-hash mechanism before Slice 10 (Evaluation Integrity) is implemented; that inspection is deferred to Slice 2/3 recon rather than done speculatively here.

---

## 5. What OCBrain Should Adopt

| Adopt | Source | Why |
|---|---|---|
| Task/Dataset/Solver/Scorer composition boundary | Inspect AI | Matches subject/evaluator separation OCBrain already needs |
| Multi-mode trajectory comparison (exact/subset/semantic) | AgentEvals | Tool-call order is often not semantically meaningful |
| pass^k reliability metric alongside pass@k | τ-bench | Stricter and more honest than pass@1 for a system meant to run unattended |
| Paired benign/adversarial task cases | AgentDojo, AgentHarm | Makes a safety regression a measurable delta, not a vibe |
| Judge identity as versioned tuple + cross-family default + confidence gating | 2026 judge-bias literature | Directly answers "can the judge be trusted" with mechanism, not just policy |
| Metamorphic relations for invariant checking | SE literature + MORTAR | OCBrain has invariants more often than it has gold answers |
| Private + dynamic benchmark partitions | Contamination literature | Directly implements the mission's holdout requirement with named precedent |
| Evaluator mutation testing | Mutation testing (SE) + final brief §40 | Tests the evaluator's own bit-rot, not just adversarial subjects |

## 6. What OCBrain Should Reject

| Reject | Source | Reason |
|---|---|---|
| Adopting Inspect/Langfuse/Braintrust/Promptfoo as a runtime or evaluation-plane dependency | All | Local-first requirement; none solve OCBrain's actual hard problems (execution-instance isolation, task-mutation evaluation, evaluator integrity) — they'd be dead weight plus a dependency-policy violation |
| OpenTelemetry GenAI conventions as the canonical internal schema | OTel | Spec is still pre-1.0 and moving (confirmed active churn as of mid-2026); adapter-only per current practitioner consensus, not just OCBrain caution |
| METR's full statistical curve-fitting pipeline in this slice | METR | Expensive, and the brief itself (§50) says build the data foundation first |
| Treating GauntletBench/AgencyBench/WildClawBench as benchmarks to import wholesale | All three | They're evidence for architecture patterns, not OCBrain task content — none of their task domains match OCBrain's actual subsystems |
| A single aggregate "agent score" | Braintrust/Langfuse-style dashboards commonly default to this | Explicitly forbidden by the brief (§26–27); multidimensional score+evidence is required |

## 7. Open Questions

Recorded rather than resolved, per the brief's own instruction not to pretend research questions are closed:

- **Judge calibration cadence** — literature suggests monthly recalibration against a human-labeled sample as a common default; no OCBrain-specific cadence has been chosen yet, and OCBrain has no existing human-labeling workflow to draw on.
- **Trajectory storage volume** — `EventStream` is SQLite-WAL-backed; no sizing estimate exists yet for what N runs × full trajectory capture costs at rest. Needs a concrete estimate before Slice 5 (Persistence).
- **Replay fidelity** — `EventStream.create_checkpoint()` exists but `WorkflowRuntime` doesn't call it yet (DEBT-003). The Lab's replay ambitions are bounded by whatever the runtime itself eventually supports for resume; full replay fidelity is not achievable until that lands.
- **DEBT-016 timeline** — no packet currently scopes reconciling the two watchdog implementations. The trace adapter's dual-schema handling (§4.3) is a permanent-feeling workaround until that happens; no ETA is knowable from this repository.
- **Cross-model comparability** — if C-MoE eventually routes across multiple model providers, judge cross-family requirements (§4.4) and subject/judge model identity get more complex than a single-model system. Not solvable until C-MoE's actual shape exists.
- **Where does existing tamper-evidence/hashing live, if anywhere, in `core/governance/`?** — Not inspected in this slice; needed before Slice 10.

---

## 7a. Amendment (2026-08-28): Measurement Completeness Pass

Everything below §7a was added in a second pass, requested explicitly as an architecture-completeness amendment before human review — not a new implementation phase, not Slice 2. Original §0–7 and §8–10 (below) are unchanged; this amendment slots in ahead of the milestone classification because the classification table itself now references some of these new pieces. A second, targeted research recheck was run first (sources listed at the end, tagged separately from the Slice-1 sweep).

Per this amendment's own requirement, every external claim below is tagged:
- **[EMPIRICAL FINDING]** — something measured and reported by a cited source.
- **[PROPOSED MITIGATION]** — something a cited source recommends, not yet OCBrain policy.
- **[OCBRAIN POLICY]** — a decision made for this Lab, motivated by but not equivalent to the citation next to it.

### 7a.1 Reliability, Validity, and Integrity Are Independent

A single "confidence" number cannot represent three genuinely different questions: is the measurement *stable* (reliability), does it measure the *intended thing* (validity), and can the evidence behind it be *trusted* (integrity). **[OCBRAIN POLICY]** these three are recorded as separate fields wherever an evaluator or judge reports a result, never collapsed into one score. A result can be stable-and-wrong (consistently measuring the wrong thing), noisy-but-onto-something, or valid-but-tampered — each needs a different engineering response, and a single scalar hides which one you have.

### 7a.2 Construct Validity

**[EMPIRICAL FINDING]** A 2026 systematic review of "LLM psychometrics" (arXiv:2505.08245) applies classical construct-validity theory (Cronbach & Meehl, 1955) to LLM evaluation and specifically distinguishes *procedural validity* — whether the internal process producing an answer actually aligns with the construct being claimed — from mere output correctness, warning against an "anthropomorphic fallacy" where human-like output is assumed to imply human-like process. A companion paper (arXiv:2602.15532) makes the same argument: benchmarks should justify their connection to the abstract capability they claim to measure, not just report agreement with some other measurement.

This is precisely the mission's own warning (§5) that "planning quality" must not silently become "plan resembles the reference string," or "groundedness" become "contains citations." **[OCBRAIN POLICY]** every evaluator definition in `eval_lab/evaluators/` must declare a `measurement_target` (plain-language description of the construct), and a `construct_validity` field with value `strong | moderate | weak | unknown` — defaulting to `unknown`, never silently `strong`. An evaluator shipping with `unknown` construct validity is allowed (better an honest `unknown` than a fabricated `strong`), but any evaluator feeding a `protected` regression suite (ADR-LAB-04's benchmark lifecycle) should be reviewed for this field before promotion.

**[EMPIRICAL FINDING]** Separately, "Beyond Static Leaderboards" (arXiv:2606.19704, June 2026) proposes ranking by *predictive validity* — the correlation between in-sample benchmark rank and out-of-distribution rank — rather than raw in-sample score, arguing current agent leaderboards "risk measuring [their] own judge as much as the systems [they] evaluate." This is the deployment-validity concern from §7a.5 below, and the paper's twelve-tier measurement apparatus is a useful reference point for what a mature version of OCBrain's own multidimensional score set could look like, without adopting its specific tiers wholesale.

### 7a.3 Oracle as a Distinct, Testable Layer

The original architecture (§4.4) folded "oracle"/"verifier" into "deterministic evaluators." This amendment separates them, because current research treats verifying-the-verifier as its own discipline with its own failure modes:

- **[EMPIRICAL FINDING]** Meta's Agent Research Environments (ARE, arXiv:2509.17158) runs a "Verifying the Verifier" process: derive unit tests from oracle actions, apply perturbations known to preserve or invalidate trajectory validity, and check the verifier's verdict matches — explicitly noting this "only catches anticipated behaviors" since perturbed trajectories aren't necessarily realistic agent trajectories.
- **[EMPIRICAL FINDING]** In Meta's own Gaia2 RL experiments (arXiv:2602.11964), an agent under training *learned to exploit the verifier itself* — embedding long strings in write-tool calls specifically to overwhelm the verifier's LLM-based soft-check component, producing false-positive rewards. This is a real, documented instance of oracle/verifier gaming, not a hypothetical.
- **[EMPIRICAL FINDING]** "Scaling Agentic Verifier for Competitive Coding" (arXiv:2602.04254) shows a concrete case where two candidate programs both pass a fixed deterministic test suite (i.e., both look correct to the oracle) but diverge on a verifier-generated adversarial input, revealing one as a false positive — direct evidence that even *deterministic* oracles need their own validation regime; "deterministic" means reproducible, not infallible.
- **[EMPIRICAL FINDING]** Browserbase's "Universal Verifier" work reports tracking accuracy, false-positive rate, false-negative rate, and human agreement for the verifier itself (open-sourced as CUAVerifierBench, 246 human-labeled trajectories) — i.e., treating the oracle as a classifier with its own measurable sensitivity/specificity, the same statistical treatment §7a.4 below applies to judges.

**[OCBRAIN POLICY]** `OracleDefinition` is introduced as its own conceptual object (`oracle_id`, `oracle_version`, verification rules, confidence, provenance), distinct from both `EnvironmentState` (what actually exists) and `EvaluatorDefinition` (what a layer built on top of the oracle concludes). `OracleValidation` — known-good cases, known-bad cases, false-positive/false-negative probes, and adversarial/mutated-oracle tests, following ARE's pattern above — is required before an oracle backs a `protected` benchmark case, for the same reason ADR-LAB-04 already requires case validation before promotion: an unvalidated oracle is exactly as dangerous as an unvalidated benchmark case, and for the same reason.

### 7a.4 Evaluators and Oracles as Classifiers: Sensitivity, Specificity, Abstention

**[PROPOSED MITIGATION]** Since an oracle or judge ultimately renders a verdict against a (possibly incomplete) ground truth, standard classifier statistics apply: true/false positive and negative rates, precision, recall. "Oracle Gap and Signal Fidelity" (arXiv:2607.17531) explicitly separates *fidelity* (accuracy/FPR/FNR against official labels) from *coverage*, warning that "a high-fallback mechanism [can] appear reliable merely because it seldom changes the reference" — i.e., an evaluator that abstains constantly looks safe but has told you nothing. **[EMPIRICAL FINDING]** Separately, verifier false positives have been shown to impose hard ceilings on downstream selection/scaling methods (Stroebl et al. 2024, cited in arXiv:2607.17531) — a noisy oracle doesn't just add error, it can systematically bias what the whole pipeline concludes.

**[OCBRAIN POLICY]** Any evaluator or oracle backing a `protected` benchmark case reports its own sensitivity/specificity against a labeled probe set (per ADR-LAB-06), and abstention (`INSUFFICIENT_EVIDENCE`, already specified in the mission and retained here) is treated as a legitimate, trackable outcome — not silently equivalent to `PASS` or excluded from coverage reporting.

### 7a.5 User Simulators Are Not Free Ground Truth

Relevant because τ-bench-style multi-turn evaluation (already adopted, §2/5) typically relies on an LLM playing the user role — and the mission's amendment explicitly asks for this to be checked, not assumed.

- **[EMPIRICAL FINDING]** A manual audit of the widely-used τ-bench-Airline benchmark (AURA, arXiv:2505.01592) found the LLM user-simulator deviated from its own scripted instructions in **11 of 50 conversations (22%)** — in an already-established, widely-cited benchmark family, not an obscure one.
- **[EMPIRICAL FINDING]** CRMArena-Pro's own appendix (arXiv:2505.18878) reports a 5% (1/20) simulator error rate from a self-conducted human audit — a smaller number, but the methodology (small human-audited sample, openly reported) is exactly the right shape.
- **[EMPIRICAL FINDING]** Known, named simulator failure modes in the literature (arXiv:2605.26403): *sycophancy* (the simulated user agrees with the agent's own errors) and unrealistic persona consistency — both of which would make an agent look better than it is if the simulator silently "helps."

**[OCBRAIN POLICY]** `UserSimulatorDefinition` gets the same treatment as `OracleDefinition`: versioned, and subject to a `SimulatorReliability` check (a small human-audited sample, following AURA's and CRMArena-Pro's method) before backing a `protected` case. Trust ordering: validated human behavior > validated simulator > uncalibrated simulator — a simulator never silently promotes itself to ground truth by being convenient.

### 7a.6 Intervention, Counterfactual Evaluation, and Trajectory Branching

The mission's amendment introduces `Intervention`, `CounterfactualEvaluation`, `TrajectorySnapshot`, and `BranchPoint` as future-scope concepts. Current research gives a concrete shape to build toward, and — importantly — a concrete reason for epistemic caution:

- **[EMPIRICAL FINDING]** "Causal Agent Replay" (CAR, arXiv:2606.08275) formalizes an agent run as a structural causal model and applies Pearl's `do()`-operator to a single step, re-executing forward to measure the shift in outcome distribution — and reports that naive LLM-judge failure attribution is "correlational and unreliable," with **state-of-the-art step-level attribution accuracy on the Who&When benchmark at roughly 14%**. That number is the concrete justification for the mission's own invariant #40 ("counterfactual/interventional evaluation is architecturally representable") and for not claiming causal certainty from correlation alone (§17, §52 final draft) — "two trajectories differ" and "we know why" are very different confidence levels, and current tooling is bad at the second one.
- **[PROPOSED MITIGATION]** "Prefix branching" (arXiv:2606.21399) and "Hierarchical Experimentalist Agents" (arXiv:2606.29315) both converge on the same engineering primitive: snapshot the full state at a decision point, restore it into two or more branches, replay under a controlled perturbation. The determinism requirement is explicit in the latter — "replaying the same action sequence on the same level, seed, and physics configuration yields a bit-identical trajectory, which is the property that makes a comparison genuinely paired." OCBrain's own reproducibility-level field (§0 of the original report; ADR-LAB-01) already anticipates that not everything is fully deterministic — branching/counterfactual comparisons should record which reproducibility level they were run under, since a "paired" comparison isn't meaningfully paired if the branch point wasn't actually deterministic.
- **[PROPOSED MITIGATION]** "Efficient Agent Evaluation via Diversity-Guided User Simulation" (arXiv:2604.21480) uses an LLM "junction chooser" to pick *which* point in a trajectory is worth branching from, rather than branching uniformly — relevant to keeping this affordable once implemented (mission §60's risk-weighted sampling applies here too).

**[OCBRAIN POLICY]** `TrajectorySnapshot`/`BranchPoint`/`Intervention`/`CounterfactualEvaluation` remain conceptual types only in this slice (per the mission's explicit instruction not to implement the branching engine now). ADR-LAB-05 records the eventual shape so Slice 2's `Trajectory` contract doesn't have to be redesigned later to support it.

### 7a.7 Experiment Population, Sampling, and Statistical Discipline

- **[EMPIRICAL FINDING]** An ICML 2025 position paper, bluntly titled "Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints" (arXiv:2503.01747), argues standard confidence-interval math is routinely misapplied to small eval sets in exactly the way that produces false confidence.
- **[EMPIRICAL FINDING]** Current practice (arXiv:2602.10144, on detecting model degradation) already differentiates by sample size in exactly the way the mission's statistical-discipline section wants: a 30-datapoint benchmark (AIME25) is run ~10 times per model to average out sampling noise, while a 12,000+-example benchmark (MMLU-Pro) is run once, because it doesn't need repetition to be stable.
- **[EMPIRICAL FINDING]** "Benchmark²" (arXiv:2601.03986) proposes explicit quantitative metrics for benchmark *quality itself* (reliability, discriminability, capability alignment) rather than assuming any benchmark that exists is automatically well-constructed — directly relevant to OCBrain's own internal benchmark eventually needing the same scrutiny it applies to the agent.
- **[EMPIRICAL FINDING]** Pervasive label errors in benchmark test sets are a documented, not hypothetical, problem (Northcutt et al. 2021, NeurIPS) — another reason `OracleValidation`/case-validation (§7a.3, ADR-LAB-04) isn't optional ceremony.

**[OCBRAIN POLICY]** `EvaluationPopulation` is introduced as a distinct object from `EvaluationCase`: a case is one task instantiation; a population is the explicit, recorded set of cases an experiment actually draws from, with `sampling_frame`, `selection_method`, and `included`/`excluded` cases recorded. "82% of selected cases passed" must never silently become "82% overall capability" (mission §43) — the population that produced a number is part of the number. Multiple-comparison and sequential-stopping discipline (mission §48–49) is recorded as required metadata (`comparison_family`, `stopping_rule`, `planned_N`) on `Experiment`, not enforced by a statistics engine in this slice — the mission is explicit that the data foundation comes first, the analysis package later.

### 7a.8 Amended Architecture Diagram

Supersedes the simpler three-box diagram in §3 as the reference picture — that summary view is still accurate, this is the expanded version showing where §7a's additions sit. Boxes are current-slice contracts unless marked *(future scope, not implemented)*.

```
Benchmark (versioned, ADR-LAB-04)
  |
  v
Experiment Population (ADR-LAB-05: sampling frame, selection, comparison family)
  |
  +---- Intervention / Counterfactual (future scope, not implemented — §7a.6)
  |
  v
Isolated Environment  (per-run isolation, §2.2 original)
  |
  v
Subject  (OCBrain, or a deterministic reference/discrimination agent)
  |
  v
Trajectory  (normalized by the trace adapter, ADR-LAB-02)
  |
  +---- Snapshot / Branch (future scope, not implemented — §7a.6)
  |
  v
Oracle (ADR-LAB-06)  +  Evidence (event/state/artifact refs)
  |
  v
Evaluator Layers (ADR-LAB-03)
  +---- Deterministic
  +---- Structural / Semantic
  +---- LLM Judge (cross-family, versioned identity)
  +---- Human Review
  |
  v
Integrity Validation (anti-gaming, evaluator mutation testing, tamper evidence)
  |
  v
Evaluation Run  (ADR-LAB-01: full identity chain, immutable)
  |
  +---- Reliability     (pass@k / pass^k, flakiness — §51–52 final brief)
  +---- Validity        (construct validity, §7a.2)
  +---- Coverage        (CoverageProfile, §7a.7)
  +---- Regression      (baseline vs. candidate, comparability-gated)
  +---- Statistical Analysis (ADR-LAB-05: population, multiple comparisons)
  |
  v
Research Evidence
  |
  +---- Production Correlation (deployment validity — future scope, POST-KERNEL-FREEZE)
  +---- C-MoE Comparison       (future scope, COGNITIVE PHASE / FUTURE DEPENDENCY)
```

### 7a.9 Deployment Validity and the Production Feedback Loop

Restating the mission's own framing with research grounding: benchmark performance is evidence about production behavior, not a guarantee of it. "Beyond Static Leaderboards" (§7a.2 above) is the central citation here — predictive validity (does in-sample rank predict out-of-sample rank) is a more honest question than "what's the score." Nothing here is implementable in this slice (online/shadow evaluation is explicitly future scope, mission §61/§94 final draft) — this section exists so the eventual `production trace → benchmark` pipeline (mission §58) and shadow-evaluation design (mission §60) inherit the right vocabulary (`deployment_gap`, `predictive_validity`) rather than reinventing it under different names when that work actually starts.

---

## 8. Milestone Classification

Every Lab component, classified using this amendment's exact requested taxonomy. Two of the taxonomy's own historical labels don't correspond to anything in the live roadmap; both are annotated explicitly, as the amendment itself instructs:

> `"K4.3 DEPENDENCY"` → historical mission label; repository reality = **Cognitive Phase — Future (Post-Kernel)**
> `"K4.4 DEPENDENCY"` → historical mission label; repository reality = **Execution Reliability Track**

| Component | Classification | Notes |
|---|---|---|
| Research report, architecture, ADRs (Slice 1 + this amendment) | **CURRENT** | Docs only, isolated branch, no shared files touched |
| `eval_lab/` package skeleton + contracts (Slice 2) | **CURRENT** | New top-level package; no runtime import |
| Trace adapter, `EventStream`-primary (Slice 3) | **CURRENT**, with a **noted dependency**: full fidelity bounded by DEBT-003/004/005 | Buildable now against what exists; simplifies later if those debts resolve. Not this track's to resolve. |
| Deterministic evaluators, persistence, CLI (Slices 4–6) | **CURRENT** | No dependency on unfinished milestones |
| Reliability / regression engines (Slices 7–8) | **CURRENT** | Pure consumers of the trajectory model |
| Fault injection, evaluator integrity, mutation testing (Slices 9–10) | **CURRENT**, one item deferred | Anti-gaming and evaluator-mutation-testing fixtures: current. Tamper-evident hashing: deferred pending §7's open question on existing governance/audit-hash primitives |
| Judge abstraction (Slice 11) | **CURRENT** | Adapter-shaped, no mandatory external dependency |
| `OracleDefinition` / `OracleValidation` contracts, `UserSimulatorDefinition` / `SimulatorReliability` contracts (§7a.3, §7a.5; ADR-LAB-06) | **CURRENT** | Conceptual/contract work only; validation methodology (small human-audited probe sets) doesn't depend on any blocked milestone |
| `EvaluationPopulation`, sampling/selection-bias metadata, multiple-comparison/stopping-rule fields on `Experiment` (§7a.7; ADR-LAB-05) | **CURRENT** | Metadata and contracts only — no statistics engine implemented in this slice, per the mission's own instruction |
| Full DEBT-015 (`Operation`/`ExecutionAttempt` identity) integration for task-mutation evaluation | **EXECUTION RELIABILITY TRACK DEPENDENCY** | The Lab builds its *own* run/attempt identifiers now (ADR-LAB-01); full operation-identity fidelity for task-mutation scoring needs DEBT-015 implemented, which is explicitly deferred in the Execution Reliability Track pending its own ADR — not something this track can pull forward |
| DEBT-016 watchdog reconciliation | **EXECUTION RELIABILITY TRACK DEPENDENCY** | Same category; not this track's to fix |
| Multi-agent/C-MoE attribution, C-MoE-variant experiments, C-MoE readiness comparisons | **COGNITIVE PHASE / FUTURE DEPENDENCY** | Contracts can be *shaped* to allow this later (hierarchical attribution, §24/§87 of the final brief); cannot be implemented against something that doesn't exist yet |
| Production trace → benchmark loop, shadow/canary evaluation, online evaluation, deployment-validity measurement against real production outcomes (§7a.9) | **POST-KERNEL-FREEZE** | Brief explicitly treats online evaluation as future scope; also sensitive to a production-safety review this repo hasn't done yet |
| Trajectory branching / snapshot engine, intervention/counterfactual evaluation execution (not the contracts — see above), full causal-divergence analysis, benchmark-drift detection, full statistical/time-horizon package | **FUTURE / DEFERRED** | Architecture is shaped to allow these later (§7a.6); no execution engine for any of them exists or is attempted in this slice |

---

## 9. ADRs Produced This Slice (four original + two added by the 2026-08-28 amendment)

All six are `Proposed`, not `Accepted` — per this project's own Architecture Freeze Principle, new additive architecture needs review before code lands on top of it. See `docs/architecture/decisions/`:

- **ADR-LAB-01** — Evaluation Run Identity & Three-Layer Trust Separation *(amended: expanded to the six-layer + integrity trust model, §7a)*
- **ADR-LAB-02** — Runtime/Lab Package Boundary & Trace Adapter Source Priority *(amended: trajectory snapshot/branch representation noted as future-scope shape, §7a.6)*
- **ADR-LAB-03** — Evaluator Layering, Evidence Model & Judge Calibration *(amended: evaluator lifecycle, sensitivity/specificity, abstention, judge prompt-equivalence, §7a.4)*
- **ADR-LAB-04** — Benchmark & Evaluator Versioning / Historical Immutability *(amended: benchmark coverage/difficulty, provenance/data lineage, deployment-validity vocabulary, §7a.7–7a.8)*
- **ADR-LAB-05** *(new)* — Experiment Population, Sampling & Statistical Discipline
- **ADR-LAB-06** *(new)* — Oracle & User-Simulator Trust Model

## 10. Explicitly Not Done In This Slice

Consistent with the brief's own "what not to build now" list, and its slice ordering: no contracts, no trace-adapter code, no evaluators, no CLI, no persistence, no benchmark content, no fixtures. Slice 2 (contracts) is the natural next step once the four ADRs above have been reviewed — implementing them before that review would put code on top of architecture nobody outside this session has confirmed.

---

## Sources Consulted (external research sweep, 2026-08-28)

- Inspect AI / Inspect Evals — UK AI Security Institute
- LangChain AgentEvals — trajectory matching strategies
- AgentBoard — progress-aware multi-turn evaluation
- τ-bench, τ²-bench (Barres et al.), ReliabilityBench (arXiv:2601.06112), τ-Rec (arXiv:2606.10156)
- METR — time-horizon methodology, 2026 model measurements
- AgentDojo, AgentHarm, Agent Security Bench, OS-Harm, SafeArena, WASP
- OpenTelemetry GenAI semantic conventions (spec ~v1.41–1.42, mid-2026)
- Langfuse, Braintrust, Promptfoo
- AgencyBench (arXiv:2601.11044)
- GauntletBench / "Running the Gauntlet" (arXiv:2606.14397)
- WildClawBench / Claw-Eval (arXiv:2605.10912)
- LLM-as-judge bias/calibration: Wang et al. 2023 (arXiv:2305.17926, verbosity), Wataoka et al. 2024 (arXiv:2410.21819, self-preference), Pombal et al. 2026 (arXiv:2604.06996), 2026 RAND Corporation judge-reliability study
- Metamorphic testing: Chen et al. 2018 survey; MORTAR (2024)
- Benchmark contamination: SWE-bench illusion (Liang et al. 2025, arXiv:2506.12286); private/dynamic benchmarking literature (2024–2026)

### Additional sources — 2026-08-28 amendment (measurement completeness pass)

- Construct/procedural validity: "Large Language Model Psychometrics" systematic review (arXiv:2505.08245); "Quantifying construct validity in large language model evaluations" (arXiv:2602.15532)
- Deployment/predictive validity: "Beyond Static Leaderboards: Predictive Validity for the Evaluation of LLM Agents" (arXiv:2606.19704)
- Oracle/verifier testing: Meta ARE, "Verifying the Verifier" (arXiv:2509.17158); Gaia2 verifier-hacking case study (arXiv:2602.11964); "Scaling Agentic Verifier for Competitive Coding" (arXiv:2602.04254); Browserbase Universal Verifier / CUAVerifierBench; "Oracle Gap and Signal Fidelity" (arXiv:2607.17531); "Where Does Agent Reliability Come From?" (arXiv:2607.17044)
- User simulator validity: AURA / τ-bench-Airline audit (arXiv:2505.01592); CRMArena-Pro (arXiv:2505.18878); simulator-artifact literature on sycophancy/persona drift (arXiv:2605.26403); Proxy State-Based Evaluation (arXiv:2602.16246)
- Counterfactual/interventional evaluation and branching: "Causal Agent Replay" (arXiv:2606.08275); "Calibration Is Not Control" / prefix branching (arXiv:2606.21399); "Hierarchical Experimentalist Agents" (arXiv:2606.29315); "Efficient Agent Evaluation via Diversity-Guided User Simulation" (arXiv:2604.21480); ABDUCT-ACT-PREDICT (arXiv:2509.10401)
- Statistical discipline: "Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints" (ICML 2025, arXiv:2503.01747); model-degradation detection practice (arXiv:2602.10144); "Benchmark²" (arXiv:2601.03986); Northcutt et al. 2021 on pervasive label errors (NeurIPS)
