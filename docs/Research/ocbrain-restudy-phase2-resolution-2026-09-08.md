---
title: OCBrain — Restudy Phase 2, Evidence Resolution & Kernel-Freeze Classification
date: 2026-09-08
supersedes: "Resolves every [PENDING] item in ocbrain-repo-restudy-2026-09-08.md. That document's repository findings (§2) stand; this one replaces its uncertainty, per governing instruction."
audited_against: "github.com/1h0lde4/ocbrain-v4.1 @ 2c677b1 (2026-09-08 23:44:40 UTC, re-fetched and hard-reset this session — the earlier session's clone was 2 commits stale)"
---

# 0. What moved since the first pass

The repo advanced one commit while this restudy was running: `2c677b1`, syncing `CURRENT_STATE.md`/`KNOWN_ISSUES.md` for a "Verification/Critic/Evidence Phase 2" branch (`obligation.py`/`rubric.py`/`inspection.py`, unmerged, contract/design only). Re-fetching surfaced a full changelog spine that the first pass hadn't read closely: DEBT-019 (Context Engineering Security Audit, six phases, five confirmed regressions), DEBT-020 (a "false-completion Kernel audit" — real, unclassified), and the definitive documentary confirmation that **C-MoE has no implementation anywhere in this repository** — it is explicitly, repeatedly logged as "research and architecture proposal only... per this project's Architecture Freeze Principle." That single fact reframes Phase 1–4 below more than anything found in the 19 repos.

---

# Phase 1 — C-MoE Questions, Resolved

**There is no C-MoE implementation to trace.** `core/model_router.py` and `core/provider_mesh.py` are not C-MoE — they predate it and solve two narrower, different problems. Read in full this session:

- **`core/model_router.py`** (577 lines) — a per-module **maturity lifecycle** (`bootstrap → shadow → native`), not a per-request candidate router. For one `module_name`, it decides whether to call an external LLM, run external-and-own-model concurrently for comparison ("shadow"), or trust the module's own fine-tuned model ("native"). Promotion/rollback is driven by a slow EMA of semantic-similarity scores between external and own answers, not by comparing multiple competing candidates for a single request.
- **`core/provider_mesh.py`** (276 lines) — a **2-provider-type reliability failover mesh** (`OllamaProvider`, `GenericOpenAICompatibleProvider`), hardcoded, not dynamically discovered. `resolve_provider()` returns them in a fixed order; `generate_with_fallback()` filters by `is_available()` (cooldown/reachability/config-gating — a real eligibility filter), sorts by a crude 0–100 `health_score` (reliability proxy, not task-fit), and tries each in order until one succeeds. "Success" means the HTTP call didn't error and returned non-empty text — nothing about whether the text satisfies the request.

**What genuinely does exist, and is the closest live analog to C-MoE's shape:** `discover_capabilities()` (`core/cognitive/planner.py:743`), called from the Planner's `_decompose()`. This is real candidate generation + hard eligibility + scoring/ranking:
- Generation: queries `CapabilityRegistry` for all registered capabilities.
- Eligibility: `min_score` gate, with an explicit, documented exception — a general-purpose capability (`is_general_purpose=True`, currently only `LLM_COMPLETION`) is included regardless of score, ranked below any specific candidate that cleared the gate ("specificity dominance"). Capabilities with zero registered adapters are excluded outright.
- Scoring: returns `CapabilityDiscoveryResult(matches: List[CapabilityMatch])`, each carrying a `relevance_score` and `evidence`; deterministic tie-breaking on `capability_type` when scores are float-identical.
- **Selection is explicitly, deliberately not implemented here** — the function's own docstring: *"Never calls Adapter.execute(), never ranks down to a single winner (selection is explicitly deferred to a future Cognitive Runtime packet, per the Evolution Directive's discovery/selection split)."*

What actually happens downstream (`_decompose()`, same file, ~line 1177): `candidates = discovery_result.matches; step = PlanStep(..., capability_type=candidates[0].capability_type if candidates else "")`. **Rank-1-by-convention is the de facto selector** — not a dedicated Selector stage, no logic beyond "take the top of an already-sorted list," no post-selection validation. Critically, the *full* ranked candidate list survives (`results.append((step, candidates))`, not discarded) — the data a real Selector would need is already there, unused.

**A–I, answered directly:**

| # | Question | Answer |
|---|---|---|
| A | Candidate generation | Exists for **capabilities** (`discover_capabilities()`), not for **models/providers** per request (provider_mesh is a fixed 2-item list). |
| B | Hard eligibility | Exists for capabilities (`min_score` + adapter-existence + specificity-dominance exception). Exists narrowly for providers (`is_available()`). |
| C | Candidate scoring | Exists for capabilities (`relevance_score`). For providers, `health_score` is a reliability proxy, not a task-fit score. |
| D | Selection | **No dedicated stage.** Capabilities: implicit rank-1-of-ranked-list. Providers: sequential try-in-health-order until success. |
| E | Post-selection validation | **None, anywhere.** Nothing checks the chosen candidate against constraints that depend on the full selected set — confirmed independently by the False-Completion audit (§6 below): `Constraint` objects are never read by anything downstream of planning. |
| F | Confidence | **Not one field — at least four distinct, precisely different things exist; see Phase 3.** None of them is C-MoE-shaped "routing confidence." |
| G | Escalation | **No per-request confidence→escalate/reject gate exists.** The closest analog, `ModelRouter._maybe_rollback()`, is a slow, windowed (100-sample), aggregate drift detector operating on a per-module basis, sampled 5% of the time in native stage — not a per-request decision. |
| H | Verification feedback | **No.** Confirmed by direct trace (Phase 6/False-Completion audit): the only "success" signal that exists anywhere in the live path is "the call didn't error," propagated unchanged through three layers, never checked against what was actually asked for. |
| I | Observability | Mixed. Execution/streaming layer: genuinely good (`ExecutionOutcome` — `failure_type`, `watchdog_verdict`, `partial_output`, `retryable`; `span("provider_call", ...)` tracing). Routing-*decision*-reasoning observability (why this candidate, what was rejected and why): absent — there's no multi-candidate decision to have reasoning about yet outside `discover_capabilities()`'s `evidence` field, which exists but nothing consumes downstream. |

---

# Phase 2 — x-algorithm vs. OCBrain, Stage by Stage

All five remaining x-algorithm stage files (`hydrator.rs`, `scorer.rs`, `selector.rs`, `side_effect.rs`, `query_hydrator.rs`) read this session, completing the trace started in the first pass.

| Stage | x-algorithm (confirmed) | OCBrain (confirmed) | Equivalent? | Gap? | Recommendation |
|---|---|---|---|---|---|
| QueryHydrator | Enriches the query before the pipeline runs; `hydrate()` (async, fallible) + required `update()` (sync merge back) | Nothing named this; `discover_capabilities()` takes a pre-built `CapabilityDiscoveryRequest` | No | Not currently needed — no multi-source query enrichment problem exists yet | None now |
| Source | Pulls raw candidates | `CapabilityRegistry` query | Loose | — | — |
| Hydrator (+PostSelectionHydrator) | Enriches candidates; `run()` wrapper checks output length matches input length, warns on mismatch | Nothing enriches `CapabilityMatch` post-generation | No | Low — no evidence this is currently needed | Defer |
| Filter (+PostSelectionFilter) | Hard eligibility, twice (pre- and post-selection); auto-traced via wrapper | `min_score` + adapter-existence, **once**, pre-ranking only | Partial | **Yes — no post-selection pass, see Phase 4** | Conditional, see Phase 4 verdict |
| Scorer | Produces per-candidate score; length-invariant enforced | `relevance_score` via `_capability_match_score()` | Yes, at the capability layer | Provider layer uses `health_score` (reliability, not fit) — different concept, not a gap | None — correctly distinct concepts |
| Selector | Named stage; returns `SelectResult{selected, non_selected}` — **non-selected is retained, not discarded** | Implicit `candidates[0]` in `_decompose()`; full candidate list also retained on `PlanStep` but nothing reads the rest | Partial | **Yes — no dedicated Selector, no selection logic beyond "top of sorted list"** | ADOPT AFTER CURRENT MILESTONE, see Q1/Q2 |
| SideEffect | Named stage; receives both selected and non-selected candidates | `mark_success()`/`mark_failure()` update `health_score`; `health_monitor.record_provider_call()` | Partial | Provider-level only; nothing downstream of capability selection logs *why* a capability won/lost | Low priority — no consumer needs this yet |
| Auto-instrumentation | Every stage's `run()` wrapper handles tracing/metrics automatically, invisible to the implementor | Manual (`span(...)` calls written by hand in `provider_mesh.py`) | No | **Real, small, portable gap** | This is the one item from x-algorithm worth taking near-term — see Amendment 2, unchanged from the first pass |

**Read on the whole comparison:** x-algorithm is a *recommendation-ranking* system optimized for engagement at massive scale; most of its apparatus (dependent query hydration, two-pass filtering at candidate-set scale) doesn't have a problem to solve in OCBrain yet, because OCBrain's live capability registry has effectively one real candidate. The two things worth taking are narrow and structural, not the whole pipeline shape: **(1)** the auto-instrumenting wrapper pattern, and **(2)** the discipline of retaining non-selected candidates with their scores, which OCBrain's `PlanStep` already does by accident (the tuple isn't discarded) but doesn't yet exploit.

---

# Phase 3 — Confidence, Precisely Distinguished

Four distinct values exist in the live codebase. None is C-MoE's "routing confidence." **Do not merge these in future design work — they measure different things and are computed by different mechanisms:**

1. **`Intent.confidence`** (`core/cognitive/intent.py`) — how confident the system is in its *interpretation* of what the user meant. A ranked, confidence-scored `IntentHypothesis` selection. Computed heuristically (e.g. a `length_signal` term); the architecture doc itself gives "no explicit type or formula" (§12 is "illustrative, not frozen"). **Category: intent-interpretation confidence.**
2. **`CapabilityMatch.relevance_score`** (`core/cognitive/planner.py`) — how well one capability's declared purpose matches one subgoal's text. Deterministic, lexical/heuristic (`_capability_match_score()`). Not called "confidence" in code; functionally is a match score. **Category: capability-match confidence.**
3. **Plan-level confidence** (`_estimate_confidence()`, same file) — **the MIN across all plan steps of that step's top-candidate `relevance_score`.** "A plan is only as strong as its least-supported step." A derived, plan-wide aggregate of #2, not an independent signal. **Category: plan-confidence, capability-match-derived.**
4. **`ModelRouter`'s `similarity`** (`core/model_router.py`) — inter-model agreement, external-vs-own-model, computed only in "shadow" stage and sampled 5% of the time in "native" stage (95% of native-stage requests get no such signal at all). **Category: model-fidelity/drift confidence.** Feeds a slow EMA, not a per-request decision.

**What does not exist, confirmed by both direct grep (zero hits for "confidence" in `model_router.py`, `provider_mesh.py`, or anywhere in `core/capabilities/`) and the False-Completion audit's independent trace:**
- **Execution-risk confidence** — nothing estimates "how likely is this to fail/stall before running it." (The watchdog reacts to stalls after they start; it doesn't predict them.)
- **Verification/task-completion confidence** — nothing estimates "how likely is this output to actually satisfy the request." This is the exact gap the False-Completion audit names: the only completion signal anywhere in the live path is a single boolean meaning "the call didn't error," copied unchanged through three layers (`core/workflow/runtime.py:280`→`:320`→`core/workers/evaluator.py:172`).
- A separate, **unmerged, contract-only** Verification/Critic/Evidence system (`Obligation`/`Rubric`/`Criterion`/`InspectionPlan`, `feature/verification-critic-evidence-phase-c`, not on `main`) is in progress and is architecturally adjacent to "verification confidence," but it's a claims/evidence-rubric framework for a different purpose (validating claims against criteria with derivation-source tracking), not a drop-in fix for the completion-boolean problem, and it doesn't exist in the live path today regardless.

---

# Phase 4 — Post-Selection Pass: Verdict

Repo-wide grep for `diversity`, `mutual_exclu(sive)`, `parallelism_limit`, cross-candidate dedup: **zero hits, anywhere in `core/`.** No constraint type currently exists whose validity depends on the full selected set, because the live `CapabilityRegistry` has effectively one real candidate (`LLM_COMPLETION`) — the other nine `CapabilityType` values are declared, not registered, per `capability.py`'s own docstring. A post-selection pass has nothing to validate yet.

**Verdict: conditionally useful, not currently required.** The moment a second real capability type gets a registered adapter (the roadmap direction the Capability Runtime is explicitly built to support), multi-candidate interaction constraints become a live question — budget across selected capabilities, mutual exclusion, parallelism limits. Building the pass now would be speculative structure with no current consumer, which is exactly the kind of premature abstraction §20.5/LAW 4 warn against. **Recommendation: RESEARCH TRACK, triggered by "second real CapabilityType adapter lands," not by a calendar date.**

---

# Phase 5 — Archify Contracts, Read in Full

All three contract docs read directly, not the README.

- **`authoring-contract.md`** — schema/enum reference (componentType, variant, relationship IDs), layout-geometry rules (schema v1/v2, `col` bounds), a legend-rendering contract, and a language/locale-consistency contract. This is diagram-tool-specific; nothing here generalizes to OCBrain's cognitive architecture.
- **`delivery-contract.md`** — **this is the substantive find.** `deliver` "reads the specification once, writes those exact bytes to a private same-directory candidate snapshot, renders that snapshot, runs the complete artifact checker, and only replaces the target after all artifact checks pass." On any failure: "removes private state, preserves the previous trusted artifact, and never invokes an opener." The receipt carries SHA-256 + byte counts for both spec and artifact. **Three claims are explicitly, permanently kept separate: (1) deterministic artifact checks + byte identity, (2) automated browser evidence, (3) human/perceptual review — "passing one claim never implies either of the others."** `visual-check`'s own status model similarly refuses to let an environmental failure get silently relabeled as `skipped`.
- **`viewer-runtime.md`** — reader-UI feature spec (reading-depth zoom levels, guided-view chapters, export formats). Confirmed low value for OCBrain — this is genuinely just the diagram viewer's UX surface, not an architecture pattern.

**Why this matters beyond archify:** the three-claims-never-conflate principle, and the "any failure preserves the previous trusted state, never partially commits" atomic-swap discipline, are close to a direct diagnosis-and-cure pair for the False-Completion Kernel Audit finding (Phase 6). That audit's root cause is exactly a claim conflation — a cheap "the call didn't error" signal silently standing in for the much stronger, unasked claim "the output satisfies the request." Archify's own explicit rule against exactly this failure mode is worth citing as prior art when that fix gets written, not because archify needs to be adopted as a dependency, but because the invariant is portable and OCBrain already has a live case that needs it.

**Classification: RESEARCH TRACK** — "claims must never silently conflate" as a named, general OCBrain artifact/completion-signal invariant, informed by this evidence, feeding directly into whatever fixes DEBT-020.

---

# Phase 6 — `/modules/new`: Confirmed Exploit Chain

Full trace, this session, against live `main` (`interface/api.py`, `core/module_factory.py`, `core/module_registry.py`, `modules/_template/module.py`).

**The chain, precisely:**
1. `POST /modules/new` (`interface/api.py:406`) takes `NewModuleRequest{name, desc, model, keywords, sources}`. No authentication observed on this route. Global `CSRFHeaderMiddleware` requires a header, `x-ocbrain-local`, on all non-safe methods.
2. `core/module_factory.py`'s `create()`: **`name` IS validated** — `name.strip().lower().replace(" ", "_")` then `if not name.isidentifier(): raise ValueError(...)`. This closes injection via `name` specifically.
3. **`desc` is never validated.** The template substitution is plain `text.replace("{{NAME}}", name).replace("{{DESC}}", desc)`.
4. The template (`modules/_template/module.py`) places the placeholder as: `    desc = "{{DESC}}"` — inside a plain double-quoted string literal, itself inside an indented `class Module(BaseModule):` body.
5. A `desc` value containing a literal `"` breaks out of that string. Class bodies execute as ordinary statements at class-definition time — a correctly-indented payload after the breakout (e.g. `x"\n    import os\n    os.system(...)\n    y = "`) is valid Python that runs when the class is defined, i.e., **the moment the file is imported.**
6. `reload_module()` (`core/module_registry.py`), called synchronously in the same request handler immediately after `create()`, calls `importlib.import_module(mod_path)` — which **executes the file, in-process, with the server's own privileges.** No subprocess, no container, no sandbox of any kind.

**Verdict, using exactly the distinctions asked for:**
- Dangerous-looking code: yes.
- Reachable exploit: **yes** — one HTTP request, no auth, only a non-secret hardcoded CSRF header string required (the string `x-ocbrain-local` is public, committed in this repo — it stops a blind cross-origin browser CSRF page, and stops essentially nothing else: any other local process, malicious dependency, or compromised local tool that can read this repo or simply guess a conventional header name can set it trivially).
- Privilege boundary: **none.** In-process execution is a direct violation of LAW 3 ("No inline execution of generated Python... Always use subprocesses, containers, task runners, restricted environments") in its most literal form.
- Actual exploit chain: **confirmed, constructible, concrete** — not a theoretical pattern-match on `str.replace` + `import_module` co-occurring, but a traced, specific breakout point with a specific payload shape.

**Scope note, not a severity discount:** this lives in the legacy per-module bootstrap/shadow/native architecture (`module_factory.py`/`module_registry.py`/`model_router.py`'s world), which sits outside the K-numbered Kernel v1.0 boundary as tracked in `CURRENT_STATE.md`'s Kernel Implementation Status table. It is not automatically a Kernel-freeze blocker by this project's own scoping — but it's a confirmed, severe, trivially-reachable RCE regardless of which side of that boundary it falls on, and I'd recommend it get logged as its own `KNOWN_ISSUES.md` entry and treated on its own urgency, not folded into or deferred by Kernel-freeze sequencing. Classification below.

---

# Phase 7 — CTX-AUTH-001 and Siblings, Resolved

All five, read directly from `CURRENT_STATE.md`'s Context Engineering Security Audit section and the `DEBT-019` row (six-phase audit, Aug 31–Sep 4, 2026):

| ID | What it protects against | Live status |
|---|---|---|
| **CTX-AUTH-001** | Intent Hypothesis prompt interpolates retrieved context via bare `str.format()`, no delimiter/authority framing — the hypothesis parser accepts an injected line from anywhere in the completion | Confirmed, intentionally-red (2 tests, `test_intent_security.py`). **No live exploitation path today — nothing currently gets attacker content into memory.** Structural gap, not currently reachable. |
| **CTX-SCOPE-001** | `ContextMemory` has no scope parameter across `save()`/`last_n()`/the `turns` schema | Confirmed, intentionally-red. **Live and unconditional** — no adversarial trigger needed, this one just is what it is right now. |
| **CTX-CACHE-001** | `cached_generate()` hashes a lossily-compressed prompt, not the full one — distinct prompts can collide on one cache key | Confirmed, intentionally-red. **Live, unconditional, no adversarial input required.** |
| **CTX-DELETE-001** | `UnifiedMemory.delete()` returns `True` even when its own L1-removal step silently fails | Confirmed, intentionally-red — a correctness/integrity bug more than a security one. |
| **CTX-EXPORT-001** | `brain_export.py`'s `import_module()` (a *different* import_module than Phase 6's — this one validates only that `manifest.json` exists) — `overwrite=True` does a destructive `rmtree`+`copytree` swap | Confirmed. **Bounded** — same CSRF-header gate as Phase 6, and this audit's own framing treats that as sufficient mitigation given localhost-only bind. No regression test yet. |

**1, 2, 4, 5 — architectural or implementation-level:** all four are implementation-level (specific, local fixes — add scope, hash the real prompt, check the L1-removal return value, add signature/checksum validation), not architecture-level. **3 (CTX-CACHE-001)** is the same category.

**Real unresolved defect?** Yes, all five, per the audit's own confirmation — none is a false positive. **Does it affect current-milestone correctness?** The audit's own architecture decision (`context-compiler-architecture-decision.md`) already answered this: shared cognitive memory is the correct model, these are bugs to fix in place, not evidence the isolation model is wrong. **Kernel v1.0 freeze criteria?** These sit in the Context Engineering track, which the register (`context-compiler-remediation-register.md`) explicitly ties to Context Compiler adoption (Tier 1) and C-MoE parallel-worker integration (Tier 2) — **not** to the Kernel freeze boundary as currently scoped. Remediation has **not started** on any of the five.

---

# Phase 8 — MTPLX Stall Deadline, Narrowly

Traced `_resolve_stream_stall_deadline_s()` and both live call sites in `mtplx/server/openai.py`.

- **What counts as a stall:** zero progress for the whole deadline window while a request is in flight (`owner_stall_probe.observe(now_s)` — a progress probe, not a wall-clock timer on the whole request).
- **Default:** 300s, configurable, `0` disables. Deliberately generous — "the default clears even a multi-minute model load."
- **Hard timeout or progress deadline:** progress deadline. Genuine token output resets it; only true zero-progress freezing trips it. This explicitly distinguishes "slow but alive" from "stalled" — the exact distinction asked about.
- **What happens when it fires:** the individual request is cancelled and fails with a diagnosable error; **the daemon itself is never killed.** Structured logging (`_log_stream_stall_break`) records tokens already streamed before the stall, so partial progress is visible, not discarded.
- **Notable structural detail:** MTPLX watches **two separate phases independently** — generation stall (`owner_stall_probe`) and a distinct post-generation "commit wait" stall (`commit_wait_probe`), each with its own probe and its own cancellation path.

**Compared against OCBrain's own watchdog** (`ProgressMonitor` + `ExecutionWatchdog`, raced via `asyncio.wait(FIRST_COMPLETED)`, `report_progress()` vs. `report_activity()`, graceful per-request cancellation, `FailureType.STALLED` distinct from `HARD_DEADLINE`, `partial_output` preserved): **essentially the same design, arrived at independently.** Progress-probing over hard timeout, graceful per-request cancellation over process-kill, partial-output preservation — OCBrain already has all three.

**Classification: REDUNDANT**, not complementary and not a genuinely better pattern — with one narrow, unverified exception flagged for optional future follow-up, not chased further per this phase's explicit scope limit: whether OCBrain's own watchdog covers a distinct post-generation "commit" phase the way MTPLX's second probe does. I don't have direct evidence either way this session, and chasing it would exceed Phase 8's stated boundary ("do not perform a broad MTPLX study").

---

# Phase 9 — HyperFrames / diagram-design / OpenMAIC: Closed

None bears on any of the eight mandatory questions or the Phase 1–8 findings above. Re-applying this phase's own test — "could they realistically change an OCBrain architectural decision?" — the answer for all three remains no, unchanged from the first pass's Tier C/D placement. **Formally closed as low-value research; no further session time allocated.**

---

# Phase 10 — Every [PENDING] Item, Reconciled

From the first-pass report's §11 queue and inline `[PENDING]` markers:

| Item | Resolution |
|---|---|
| `core/model_router.py`/`provider_mesh.py` vs. x-algorithm's two-pass shape | **VERIFIED FALSE** (as originally framed) — there is no C-MoE pipeline to compare; see Phase 1. The comparison that *does* apply is capability-discovery vs. x-algorithm, done in Phase 2. |
| Confidence as typed field in C-MoE's actual contracts | **VERIFIED FALSE**, more precisely: no C-MoE contract exists to hold one; the layer that does exist (`discover_capabilities()`) has `relevance_score`, not "confidence." See Phase 3. |
| Full archify contract-doc read | **VERIFIED, DONE** — see Phase 5. |
| `/modules/new` exploitability | **VERIFIED TRUE** — confirmed exploit chain, see Phase 6. |
| CTX-AUTH-001 + 4 siblings | **VERIFIED TRUE, fully characterized** — see Phase 7. All five real, remediation not started, none currently a Kernel-freeze-scope item. |
| MTPLX stall-deadline vs. OCBrain watchdog | **VERIFIED — REDUNDANT**, one narrow sub-question left genuinely indeterminable within this phase's scope (commit-phase coverage) — see Phase 8. |
| "Auto-instrumenting wrapper pattern... not confirmed present or absent in OCBrain's own plugin/stage traits" | **VERIFIED FALSE (absent)** — `provider_mesh.py`'s `span(...)` calls are written by hand at each call site, not generated by a wrapper. Confirmed by direct read. |
| "No explicit post-selection eligibility pass... worth checking directly against core/model_router.py" | **VERIFIED FALSE, more precisely** — the relevant file is `planner.py`, not `model_router.py`; no post-selection pass exists, and per Phase 4, none is currently required either. |
| Ai-memory's consolidate crate vs. OCBrain's MemoryCuratorWorker | **PARTIALLY TRUE — refined, see Question 6 below.** A working mechanical consolidator (`core/memory/consolidation/consolidator.py`) already exists; it is not shaped like the governed, event-emitting Worker the roadmap names. |

---

# Phase 11 — Rankings, Recalculated

**Architectural value — did it actually change or strengthen an OCBrain conclusion, now that C-MoE's non-existence is confirmed?**

The first pass's ranking (Semantica > Maka > x-algorithm > OpenViking > ai-memory > Prime Agent > Needle > code-graph-rag) **holds**, with one adjustment: **x-algorithm moves up conceptually but down practically.** Its architectural value is now better understood as informing a *future* C-MoE build from a cleaner starting point (the discovery/selection split OCBrain's own planner already anticipates) rather than revealing a gap in something that exists today. Needle's confidence-as-typed-field pattern is now confirmed more directly actionable than it looked in the first pass, precisely because Phase 3 confirms *no* candidate-confidence field exists anywhere yet — there's no competing convention to reconcile against.

**Implementation value — which mechanisms can realistically be reused, now with OCBrain's actual code in hand?**

Re-ranked, ai-memory drops slightly and code-graph-rag/x-algorithm's narrow patterns rise: **x-algorithm's auto-instrumenting wrapper (small, self-contained, provider_mesh.py already has hand-written spans to replace) > ai-memory's consolidate crate (still valuable, but `consolidator.py` already proves the mechanical logic works — the gap is Worker-shaping, not algorithm) > Needle's confidence-field-plus-grounding-gate contract shape > Semantica (unchanged, richest but most expensive) > Apache Maka (unchanged, pattern portable, code isn't).**

**Research value — unchanged from the first pass**, except code-graph-rag's "System Self-Model" question now has one more concrete, in-repo motivating case: DEBT-020's false-completion chain was found by *exactly* the kind of cross-cutting trace (event/runtime-path archaeology across three files) a self-model would make cheaper to repeat.

---

# Phase 12 — Consolidated Finding Set

**Finding 1**
- Repository: internal (ground-truth reconciliation)
- Mechanism: C-MoE documentary trail
- Actual evidence: `CURRENT_STATE.md`/`KNOWN_ISSUES.md` changelog, multiple independent syncs, "research and architecture proposal only... per this project's Architecture Freeze Principle"
- OCBrain subsystem: Model Routing / Cognitive Runtime
- Current OCBrain state: No implementation exists
- Finding: The governing prompt's framing ("the actual current OCBrain C-MoE architecture") assumed an artifact that doesn't exist
- Impact: Reframes Phases 1–4 entirely
- Recommendation: Treat `discover_capabilities()` as the actual current state of C-MoE-adjacent infrastructure going forward
- Timing: N/A — documentary, not actionable
- Confidence: FACT, direct source read + multiple independent doc confirmations

**Finding 2**
- Repository: x-algorithm
- Mechanism: Auto-instrumenting stage wrapper (`Filter::run()` et al.)
- Actual evidence: `candidate-pipeline/filter.rs`, `hydrator.rs`, `scorer.rs`, `selector.rs` — all five confirmed to share the pattern
- OCBrain subsystem: `core/provider_mesh.py` (hand-written spans today)
- Current OCBrain state: Manual instrumentation
- Finding: Small, portable, self-contained technique
- Impact: Low migration cost, real observability improvement
- Recommendation: Adopt for any existing OCBrain plugin/stage trait
- Timing: Justified hardening, near-term
- Confidence: FACT

**Finding 3**
- Repository: internal (`interface/api.py`, `core/module_factory.py`, `core/module_registry.py`, `modules/_template/module.py`)
- Mechanism: Template string-literal breakout → in-process `importlib.import_module()`
- Actual evidence: Full chain traced, exact breakout point identified, payload shape verified as syntactically constructible
- OCBrain subsystem: legacy module-factory/module-registry HTTP surface (outside K-numbered Kernel boundary)
- Current OCBrain state: Live, unauthenticated except a hardcoded (non-secret) CSRF header, unpatched
- Finding: Confirmed RCE, direct LAW 3 violation
- Impact: Severe, regardless of Kernel-freeze scope
- Recommendation: Validate `desc` the same way `name` already is, at minimum; ideally never string-template into an imported `.py` file at all
- Timing: **Urgent, independent of Kernel-freeze sequencing**
- Confidence: FACT, full exploit chain constructed from source, not inferred

**Finding 4**
- Repository: internal (`core/runtime/execution_runtime.py:280`→`:320`→`core/workers/evaluator.py:172`, per the pre-existing False-Completion audit, independently spot-confirmed this session)
- Mechanism: Single success boolean, meaning "the call didn't error," treated as equivalent to "the output satisfies the request"
- Actual evidence: Direct citations to three call sites; `Constraint` dataclass has no quantitative field; `EvaluatorWorker` never reads `Constraint` (zero grep hits); `FailureType.COMPLETED_WITH_PARTIAL_OUTPUT` exists but is never assigned and is treated as success by `is_success`
- OCBrain subsystem: Workflow Runtime / Evaluator / completion-signal integrity
- Current OCBrain state: Confirmed live, unclassified (`DEBT-020`, "pending Moncif's decision")
- Finding: Real, confirmed, structurally distinct from anything in the 19-repo study, but resonant with Archify's "claims must never conflate" invariant
- Impact: A partial result can reach `SUCCESS` today
- Recommendation: Per the existing pre-implementation report's own minimal-fix sketch — give `Constraint` a checkable value, stop `is_success` from conflating partial with full, insert the check before response-finalization
- Timing: Candidate for pre-freeze correctness fix, pending the classification decision this project's own convention routes to Moncif
- Confidence: FACT — this session did not re-derive it, but did independently spot-confirm the cited call sites exist as described

**Finding 5**
- Repository: ai-memory + internal (`core/memory/consolidation/consolidator.py`)
- Mechanism: Memory curation/consolidation shape
- Actual evidence: `consolidator.py` (83 lines) implements real, running (hourly async loop) decay/dedup/distillation with a documented bug-fix (BUG-05, iterator-mutation) already in it
- OCBrain subsystem: Memory (§8), planned `MemoryCuratorWorker` (§7.1, v4.3.6)
- Current OCBrain state: Mechanical logic exists and runs; Worker-shaped governance/observability does not
- Finding: The gap isn't "no consolidation exists" — it's "existing consolidation isn't a governed, event-emitting Worker"
- Impact: v4.3.6 can likely wrap/reuse `consolidator.py`'s logic rather than build it from zero
- Recommendation: Feed ai-memory's `auto_improve_telemetry.rs`/`projection.rs` shape into v4.3.6's *Worker* design specifically; treat `consolidator.py`'s decay/dedup/distill logic as reusable
- Timing: Next milestone (v4.3.6)
- Confidence: FACT

---

# Mandatory Final Questions — Direct Answers

### Question 1 — Does current OCBrain already implement candidate-generation → eligibility → scoring → selection?

**Partially, and only at the capability layer, not the model/provider layer.** `discover_capabilities()` implements generation, eligibility, and scoring/ranking correctly and deliberately. **What's missing is Selection** — there is no dedicated Selector stage; a downstream caller takes index 0 of an already-sorted list by convention, with no logic, no post-selection validation, and no consumption of the `evidence`/ranking data beyond that. At the provider layer (`provider_mesh.py`), a much cruder, complete-but-different pipeline exists (reliability-ranked sequential fallback across a hardcoded 2-item list) that was never meant to be C-MoE and shouldn't be read as an attempt at it.

### Question 2 — Does OCBrain need a post-selection eligibility/constraint pass?

**Conditionally.** Not now — zero evidence any constraint type requiring one exists in the current codebase, because the live capability registry has effectively one real candidate. **Yes, later** — specifically, the moment a second `CapabilityType` gets a registered adapter, this becomes a live question, not a hypothetical one. Building it now would be speculative structure with no consumer.

### Question 3 — Does OCBrain need typed confidence in C-MoE?

Answered per-category, not collapsed:
- **Candidate-match confidence:** already exists (`CapabilityMatch.relevance_score`) — no gap.
- **Routing/selection confidence** (how much to trust having picked candidate N): **missing**, and would only matter once Selection (Question 1) is itself built — no point adding a confidence field to a decision that doesn't exist yet.
- **Execution-risk confidence:** missing, no current mechanism estimates failure likelihood before running.
- **Model confidence** (in the Needle sense — a calibrated per-call scalar): missing at the capability/routing layer; the closest live analog (`ModelRouter.similarity`) measures something different (external/own-model agreement) and is intermittent by design.
- **Verification/task-completion confidence:** missing, and this is the most urgent of the five given Finding 4 — not because C-MoE needs it, but because the live path needs *any* completion signal stronger than "didn't error," independent of C-MoE entirely.

### Question 4 — Does OCBrain need a dedicated provenance/conflict layer?

Comparing Semantica's `ProvenanceManager`/`ConflictDetector`/bitemporal model against OCBrain's actual current Memory+Event+Verification architecture (not the aspirational one): `EpisodicMemory.provenance` is a single free-text field (§8.2); no `ConflictDetector`-equivalent exists anywhere in `core/memory/`; the in-progress Verification/Critic/Evidence system (unmerged) is about validating claims against rubrics, not about detecting when two remembered facts contradict each other. **A new subsystem is justified** — existing components genuinely cannot represent "why was this believed, and did two sources disagree," not merely "haven't been asked to yet." **Classification: RESEARCH TRACK**, not urgent — nothing in this session's tracing found a live bug this gap is currently causing, unlike Findings 3 and 4.

### Question 5 — Does Maka reveal an actual weakness in OCBrain's EventStream/EventBus architecture?

Indirectly, yes, but not a new one — it sharpens an already-tracked item. `KNOWN_ISSUES.md` DEBT-004/DEBT-005 already document that OCBrain has *three* event mechanisms (`EventBus`, `EventStream`, `KnowledgeEvent`) with no single canonical source and no unified audit trail. Maka's "one Runtime Event Log, compaction changes projections not history" is a clean, one-sentence invariant OCBrain doesn't currently have written down anywhere for its own EventStream. This doesn't reveal a *new* weakness — DEBT-004/005 already say the same thing in more diffuse form — but it gives a crisper target statement to write down if/when that debt gets addressed. Not a freeze-relevant finding; DEBT-004/005 are both logged Low severity.

### Question 6 — Does ai-memory provide useful architecture for the planned MemoryCuratorWorker?

**Yes, but more narrowly than the first pass implied.** `core/memory/consolidation/consolidator.py` already exists and already runs (decay, dedup, distillation, with a real bug-fix already applied) — so ai-memory isn't filling an empty gap, it's a reference for the *shape* the existing logic should grow into: a governed `CognitiveWorker` (§7.2 — emits events, respects governance, supports interruption/evaluation) rather than a bare asyncio loop that only logs. Transferable: the `auto_improve`/`projection`/`sweep` separation of concerns. Incompatible: ai-memory has no equivalent of OCBrain's GovernanceKernel to wire through — that part is OCBrain-specific work no external reference provides.

### Question 7 — Does Prime Agent justify a lightweight session-local refinement mechanism?

It fills a *real*, currently-unaddressed gap, but building it carries real risk that must be scoped tightly. OCBrain's §13 Evolution Workflow is a heavy, correctly-gated pipeline for anything that matters; there's currently no lighter path for genuinely small, session-scoped adjustments, which either means such adjustments don't happen (plausible, given no evidence any exist today) or happen informally/undocumented (worse). Prime Agent's own design constraints — never rewrites the immutable base prompt, only supplemental state, snapshot-rollback-capable — are exactly the guardrails that would need to be non-negotiable in any OCBrain version, specifically **to prevent it becoming a second, uncontrolled self-modification channel** running alongside §13 rather than beneath it. **Classification: RESEARCH TRACK, not adoption** — the idea is sound, the guardrail design is the hard part, and this session found no evidence of urgency (no bug this gap is currently causing) to justify skipping straight to implementation.

### Question 8 — Does code-graph-rag justify a System Self-Model research track?

Only if a concrete purpose is named, and this session found one: **failure correlation.** DEBT-020's false-completion chain was found by manually tracing three files' worth of call sites by hand. code-graph-rag's `crash_correlation.py` is existence-proof that this specific kind of cross-cutting trace — "which code paths does this runtime failure actually touch" — is a solved-enough problem to make cheaper. Architecture understanding, change-impact analysis, and capability discovery are plausible but unevidenced this session; failure correlation has a concrete, freshly-discovered motivating case. **Classification: RESEARCH TRACK**, justified specifically by failure-correlation, not by "code graphs are generally useful."

---

# Required Final Classification

## MUST CHANGE BEFORE KERNEL FREEZE
*(Genuine blockers only — none currently qualify by this project's own Kernel-boundary scoping, since both formerly-identified blockers are closed and neither Finding 3 nor Finding 4 sits inside the K-numbered Kernel boundary as `CURRENT_STATE.md` currently draws it. Flagged here anyway because urgency and freeze-boundary are different axes:)*
- **Nothing meets this bar under the project's own current scoping.** Findings 3 (`/modules/new` RCE) and 4 (false-completion chain) are both severe and both currently unclassified/untracked as formal debt — but neither sits inside the Kernel v1.0 boundary as `CURRENT_STATE.md`'s own implementation-status table defines it. That's a scoping fact, not a severity judgment on either finding.

## SHOULD CHANGE BEFORE KERNEL FREEZE
- **Finding 4 (false-completion chain)** — even though it's formally outside the two historical Kernel blockers, it's a correctness defect in the live default execution path (`use_k42_frontend`, on since Aug 27) that the Kernel pipeline runs through. The pre-existing pre-implementation report's own minimal-fix sketch is small and scoped. Recommend Moncif weigh this as a freeze consideration even though its DEBT-020 status is currently unclassified — the mechanism is not in dispute, only its priority.
- Log `/modules/new` (Finding 3) as its own `KNOWN_ISSUES.md` entry regardless of freeze-boundary scoping — its current absence from the register is itself a gap this session found, independent of the 19-repo study.

## DEFER TO POST-FREEZE
- Selector-stage design for `discover_capabilities()` (Question 1) — genuinely valuable, correctly sequenced as post-freeze per the existing DEBT-019 remediation register (Tier 2 already gates C-MoE parallel-worker integration on Context Engineering remediation first).
- Provenance/conflict layer (Question 4).
- Auto-instrumenting wrapper pattern (Finding 2) — small enough to be near-term, but not freeze-relevant either way.
- MemoryCuratorWorker design, informed by Finding 5 — already sequenced at v4.3.6.
- CTX-AUTH-001 and siblings (Phase 7) — the audit's own architecture decision already places these in the Context Compiler/C-MoE remediation track, not Kernel freeze.

## RESEARCH VAULT
- Lightweight session-local evolution refinement, tightly guardrailed (Question 7).
- System Self-Model, scoped specifically to failure-correlation (Question 8).
- "Claims must never conflate" as a named, general artifact-generation invariant (Phase 5), feeding Finding 4's eventual fix.

## REJECT / CLOSED
- MTPLX beyond the stall-deadline mechanism (Phase 8) — redundant with OCBrain's existing watchdog, formally closed.
- HyperFrames, diagram-design, OpenMAIC as architecture sources (Phase 9) — formally closed, no further session time.
- x-algorithm's full pipeline shape as something to build wholesale — the auto-instrumenting wrapper is worth taking; the rest (dependent query hydration, two-pass filtering at scale) has no current OCBrain problem to solve.

---

# Final Verdict

The restudy does not reveal a Kernel v1.0 blocker by this project's own current scoping — both historical blockers are closed, and the two severe findings this phase surfaced (the `/modules/new` RCE and the false-completion success-boolean chain) both sit outside the K-numbered Kernel boundary as presently drawn, even though one of them runs through the Kernel's own default execution path daily. That's a real tension worth naming plainly rather than resolving unilaterally: **the scoping says "not a blocker," the evidence says "a correctness defect lives inside the path every request takes."** Whether that gap between scoping and reality should move Finding 4 into the freeze conversation is exactly the kind of call this project's own history routes to Moncif, not to a research pass.

Past that, the restudy is primarily **validation and hardening, not architectural revision.** C-MoE remains correctly unimplemented and correctly deferred — nothing here argues for building it early. What OCBrain has instead (`discover_capabilities()`) is a smaller, honest, deliberately-unfinished piece of the same shape, and the one piece missing from it (Selection) is exactly where the project's own documentation already said work would resume. The two genuinely new, source-confirmed findings this session produced — the RCE and the false-completion chain — came from re-reading OCBrain's own code and changelog, not from any of the 19 repositories; the external research's real contribution was supplying language and invariants (claim-conflation, one-ledger-many-projections, auto-instrumenting wrappers) that make OCBrain's own already-known gaps easier to name precisely, not new gaps in themselves.
