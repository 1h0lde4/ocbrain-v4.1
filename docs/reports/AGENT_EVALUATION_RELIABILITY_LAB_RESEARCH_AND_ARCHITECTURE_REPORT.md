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

## 8. Milestone Classification

Every Lab component, classified using the mission's requested category names — annotated with what each category actually maps to in this repository, since two of the assumed labels (K4.3, K4.4) don't exist as stated.

| Component | Classification | Notes |
|---|---|---|
| Research report, architecture, ADRs (this slice) | **CURRENT** | Docs only, new branch, no shared files touched |
| `eval_lab/` package skeleton + contracts (Slice 2) | **CURRENT** | New top-level package; no runtime import |
| Trace adapter, `EventStream`-primary (Slice 3) | **CURRENT**, with a **noted dependency**: full fidelity bounded by DEBT-003/004/005 | Buildable now against what exists; will simplify later if those debts resolve |
| Deterministic evaluators, persistence, CLI (Slices 4–6) | **CURRENT** | No dependency on unfinished milestones |
| Reliability / regression engines (Slices 7–8) | **CURRENT** | Pure consumers of the trajectory model |
| Fault injection, evaluator integrity, mutation testing (Slices 9–10) | **CURRENT**, one item deferred | Anti-gaming and mutation-testing fixtures: current. Tamper-evident hashing: **deferred pending §7's open question** on existing governance/audit-hash primitives |
| Judge abstraction (Slice 11) | **CURRENT** | Adapter-shaped, no mandatory external dependency |
| Full DEBT-015 (`Operation`/`ExecutionAttempt` identity) integration for task-mutation evaluation | **Execution Reliability Track dependency** (the brief's "K4.4/WATCHDOG DEPENDENCY") | The Lab can build its *own* run/attempt identifiers now, but full operation-identity fidelity for task-mutation scoring needs DEBT-015 implemented, which is explicitly deferred pending its own ADR — not something this track can pull forward |
| DEBT-016 watchdog reconciliation | **Execution Reliability Track dependency** | Same category; not this track's to fix |
| Multi-agent/C-MoE attribution, C-MoE-variant experiments | **C-MoE DEPENDENCY** (the brief's "K4.3 DEPENDENCY", remapped — no K4.3 exists; the real bucket is "Cognitive Phase — Future (Post-Kernel)") | Contracts can be *shaped* to allow this later (hierarchical attribution, §24 of the final brief); cannot be implemented against something that doesn't exist yet |
| Production trace → benchmark loop, shadow/canary evaluation, online evaluation | **POST-KERNEL-FREEZE** | Brief explicitly treats online evaluation as future scope (§84 final draft); also sensitive to production-safety review this repo hasn't done yet |
| Full causal-divergence analysis, counterfactual/interventional evaluation, benchmark-drift detection, full statistical/time-horizon package | **FUTURE / DEFERRED** | Architecture should not block these (contracts are shaped to allow later addition); no attempt to implement now |

---

## 9. ADRs Produced This Slice

All four are `Proposed`, not `Accepted` — per this project's own Architecture Freeze Principle, new additive architecture needs review before code lands on top of it. See `docs/architecture/decisions/`:

- **ADR-LAB-01** — Evaluation Run Identity & Three-Layer Trust Separation
- **ADR-LAB-02** — Runtime/Lab Package Boundary & Trace Adapter Source Priority
- **ADR-LAB-03** — Evaluator Layering, Evidence Model & Judge Calibration
- **ADR-LAB-04** — Benchmark & Evaluator Versioning / Historical Immutability

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
