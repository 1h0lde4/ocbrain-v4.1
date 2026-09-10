---
title: OCBrain — Comparative Restudy of 19 Repositories
date: 2026-09-08
status: PARTIAL — first pass complete, deep-dive queue below
evidence_tags: "[FACT] = verified this session via clone/source read.  [CLAIM] = repo's own stated claim, not independently verified.  [INFER] = reasonable inference from FACT evidence.  [PENDING] = flagged, not yet verified — needs follow-up."
---

# 0. Ground-Truth Reconciliation (done before touching the 19 repos)

Per this project's own precedence rules, prior claims — including a pasted governing document — are hypotheses until checked against current source. Two discrepancies surfaced immediately:

**PROJECT_INSTRUCTIONS.md mismatch.** The repo root `PROJECT_INSTRUCTIONS.md` is a 129-byte stub pointing to `docs/architecture/PROJECT_INSTRUCTIONS.md` (1,422 lines). [FACT] That real file's §20 block runs `20.1`–`20.11` (lines 1142–1372+), including **`## 20.6 Evidence-First Reconciliation`** — a section with no counterpart in the document pasted into this conversation, which jumps from a `20.5 Architectural Discipline` to an unlabeled "Architecture Freeze Principle" block. §20.6 states, in substance, that prior ADRs, session summaries, and *a governing prompt's own stated premises* are hypotheses, not authority — current code and traced execution are. [FACT]

**§1.1 doesn't exist.** The pasted document's §1.1 "Architectural Research Authority" claims the repository already contains "two comprehensive research documents synthesizing dozens of leading projects" treated as "permanent architectural references." A repo-wide grep for that section title and for phrases like "synthesizing dozens" / "leading projects" returned zero hits anywhere in the repository. [FACT] The closest actual artifacts are OCBrain's own internal self-studies under `docs/studies/` (CMoE cognitive-runtime and kernel-completion studies) and a root-level `OCBRAIN_FUTURE_ARCHITECTURE.md` (~100KB, dated 2026-06-15, framed around ~200 external repos, memory/runtime-focused). I checked that file for name overlap with the 19 targets here — zero matches. So this restudy is genuinely new ground, not a rehash, but the framing that a "first pass" already produced two canonical survey documents doesn't correspond to anything currently in the repo.

**Practical consequence:** everything below treats `docs/architecture/PROJECT_INSTRUCTIONS.md` (the live file) as authoritative over the pasted copy, consistent with that file's own §20.6.

**Debt-register refresh** (memory context predates several of these):

| Item | Status per live `KNOWN_ISSUES.md` | Note |
|---|---|---|
| DEBT-011 | Still open/active | Consistent with local-but-unpushed reconciliation |
| DEBT-016 (duplicate watchdogs) | **Resolved** (new) | `ADR_KERNEL_02_WATCHDOG_UNIFICATION` — unified via `GraphExecutionWatchdog` + shared `watchdog_decision.py` |
| DEBT-003 | **Resolved** (new, not previously tracked in memory) | Checkpoint/resume, `ADR_KERNEL_03_CHECKPOINT_RESUME.md` |
| DEBT-001 (MemoryGovernor) | **Partially resolved** | `write()`/`update()`/`delete()` now all route through `GovernanceKernel.evaluate_action()` — the structural bypass is closed. MemoryGovernor's own *content*-validation logic (confidence/growth-limit checks) is still scoped to `write` only by design; update/delete aren't content-validated. The narrower gap survives inside the fixed one. |
| DEBT-015 | Partially addressed | The checkpoint-identity sub-item is now covered by DEBT-003; the rest is still open, still needs an ADR under the Architecture Freeze Principle |
| DEBT-017 | Unchanged, open, low severity | |
| `/modules/new` RCE | Route and `import_module` usage both still present as cloned | **Not tracked** in `KNOWN_ISSUES.md` under any heading I searched. I did not re-run a full exploit-chain re-verification this session — flagging the tracking gap, not re-asserting exploitability from a stale read. |
| CTX-AUTH-001 (+4 siblings) | New to me | Five intentionally-red security-regression tests exist as tripwires for an unresolved context-authorization gap — worth a dedicated look next session. |

---

# 1. Executive Conclusion

**Critical / Tier A** (could change a subsystem boundary or contract):
1. **x-algorithm's candidate pipeline is close to a reference implementation of the exact architecture the brief speculates about for C-MoE** — `QueryHydrator → Source → Hydrator → Filter → PostSelectionFilter → Scorer → Selector → SideEffect`, with a *second* eligibility pass after selection (catches candidates that become ineligible only once combined with others) and automatic per-stage tracing/metrics via a trait default method, so every stage gets uniform observability without each implementor remembering to add it. This is a stronger shape than "router → model."
2. **Semantica's decision-provenance model (`Record → Link → Query → Govern → Audit Export`, W3C PROV-O-based, bitemporal facts, explicit `ConflictDetector`/`SourceTracker`) is more rigorous than anything currently described in OCBrain's memory-scoring formula.** OCBrain's L0–L4 layers say *what* to store; Semantica's model says how to prove *why a decision was made* and *resolve contradictions* — a layer OCBrain doesn't appear to have.
3. **`ai-memory`'s consolidate crate (`curator.rs`, `auto_improve.rs`, `sweep.rs`, `projection.rs`) is a working reference implementation for almost exactly the `MemoryCuratorWorker` OCBrain has already named in §7.1 and scheduled for v4.3.6 but (per the roadmap) hasn't built yet.** This is unusually directly actionable.
4. **Maka's single-Runtime-Event-Log-as-canonical-source-with-multiple-projections model gives a crisp answer to OCBrain's own open question about EventStream/EventBus separation**: one ledger, compaction changes *provider input projections*, never history. Maka's explicit rejection of a second "swarm" execution path ("there is no `SwarmRun`, second event ledger, or background owner") is a concrete, lived anti-pattern warning that maps directly onto LAW 2 and LAW 4.

**Major opportunities / Tier B:**
5. Needle's confidence field is a first-class API return value (`"confidence": 0.94`) on every call, paired with a structural grounding check that *blocks execution* of ungrounded arguments by default (`strict=True`) rather than relying on prompted carefulness — a concrete escalation-gating mechanism, not just a concept.
6. OpenViking's `benchmark/tau2` README explicitly scopes which ablations count as "current evidence" vs. diagnostic-only, specifically to stop a reproduction agent from citing an unvalidated variant as validated — a rigor pattern worth adopting for OCBrain's own eventual eval reports.
7. code-graph-rag is a substantive, 12-language, benchmarked answer to the brief's "System Self-Model" question — evidence that a graph-based self-model of a codebase is a solved-enough problem to reuse patterns from, not a research fantasy.

**Validation findings:** OCBrain's LAW 3 (never inline-execute generated code) is *stricter* than Prime Agent's own stated posture — Prime Agent's README explicitly warns its worker/kernel isolation is "not a security sandbox." That's independent confirmation OCBrain's isolation stance is the more defensible one, not overcautious.

**Distractions / Tier E, confirmed by inspection not assumption:** `public-apis` (a link list), `OpenLogi` (a Logitech HID driver), `vorssaint-utils` (a macOS menu-bar app), `awesome-gpt-image-2` (a prompt-gallery SaaS product) carry no architectural signal for OCBrain. Flagging this is itself a finding — nothing here should get force-fit.

**Depth caveat:** the 6 flagged repos plus `ai-memory` and `code-graph-rag` got real source-level dives (file paths and mechanisms cited below). `archify`, `MTPLX`, `modular`, `OpenMAIC` got a lighter, targeted look. `diagram-design`, `hyperframes`, and the five Tier-E repos got structural recon only — sufficient to classify them, not to extract deep mechanism detail. That queue is in §11.

---

# 2. Repository-by-Repository Findings

## 2.1 Semantica (`semantica-agi/semantica`) — Tier A, deep dive done

**What it is:** graph-native context/knowledge substrate for agent systems. Python, ~47MB, commit activity same-day. [FACT]

**Architecture (verified):** `ingest → parse → normalize → split → extract → conflict-detect → dedupe → KG construction → {ontology, reasoning, provenance, context} → {vector, graph} storage → export/visualize/services`. [FACT] Core modules include `semantica/context` (`ContextGraph`, `AgentContext`, `DecisionRecorder`, `CausalChainAnalyzer`, `PolicyEngine`), `semantica/provenance` (`ProvenanceManager`, built on **W3C PROV-O**, not a bespoke schema), `semantica/conflicts` (`ConflictDetector`, `ConflictResolver`, `SourceTracker`), `semantica/reasoning` (`ReteEngine`, `DatalogReasoner`, `SPARQLReasoner`), and bitemporal facts (`BiTemporalFact` + `TemporalGraphQuery` — real point-in-time querying, not just timestamps). [FACT] Framework integrations exist for agno, crewai, google_adk, langchain, openclaw. [FACT]

**Notable mechanism:** the "Decision Intelligence Lifecycle" — `Record → Link → Query → Govern → Audit Export` — treats *why a decision was made* as a first-class, provenance-linked, exportable-for-audit object.

**Evidence it works:** `ARCHITECTURE.md` and module layout are internally consistent with the claims; I did not run its test suite or benchmarks this session. [PENDING]

**Limitation:** using W3C PROV-O and Datalog/SPARQL reasoners is a real dependency/complexity commitment — this is not a lightweight add-on.

**OCBrain mapping:** L0–L4 memory layers (§8.1) define storage tiers but nothing plays the role of `ProvenanceManager` + `ConflictDetector` + bitemporal queries together. `EpisodicMemory.provenance: str` (§8.2) is a single string field — Semantica's provenance is a queryable, standards-based subgraph.

**Classification:** RESEARCH TRACK now, ADOPT AFTER CURRENT MILESTONE for the underlying principle (structured provenance + conflict detection as a first-class layer, not full PROV-O adoption).

## 2.2 OpenViking (`volcengine/OpenViking`) — Tier A, deep dive done

**What it is:** "context database for AI agents." Polyglot: Rust (`crates/ov_cli`, `crates/ragfs`), C++-adjacent native storage (`src/`, with `third_party/{croaring,leveldb,rapidjson,spdlog}`), Python core (`openviking/{ingest,parse,retrieve,session,storage,privacy,...}`), TypeScript web studio. ~172MB, AGPLv3, active same-day. [FACT]

**Evidence it works — this is the strongest benchmark evidence in the set.** `benchmark/` contains real harnesses against LoCoMo, LongMemEval, and TAU-2, not just claims. [FACT] The LoCoMo harness runs three memory paths (`native`/`e2e`/`preingest`) through an external "Hermes Agent" for A/B comparison. [FACT] The TAU-2 README documents "OpenViking Memory V2" trained on TAU-2 conversations, comparing a `no_memory` baseline against a `template_indexed_trajectory_top4_prewrite_top2` treatment — and explicitly states that "category rerank, experience-memory routes, fixed-count-only ablations... are intentionally left out of this README and config set so reproduction agents do not mistake diagnostic routes for current evidence." [FACT] The `memory_organization` benchmark grades autonomous file-reorganization decisions where "the expected organization exists only in the grader" — blind grading, no leakage. [FACT]

**Notable mechanism:** trajectory memory is injected at *specific execution points* — "top4 at the first user turn and top2 before write-like tool calls" — not just prepended once at session start. [FACT]

**Limitation:** AGPLv3 — a real consideration if OCBrain ever wanted to depend on it directly rather than borrow the pattern. Also the sheer surface area (memory plugins for a dozen-plus agent harnesses: Claude Code, Codex, Cursor, opencode, openclaw, langchain...) suggests OpenViking is positioning as universal third-party memory infrastructure, which is a different product shape than an embedded subsystem.

**OCBrain mapping:** directly relevant to §8 (Memory System) and §8.3 (hybrid retrieval — OpenViking's retrieval stack plus rerank step is a concrete instance of the BM25+embedding+RRF requirement already in PROJECT_INSTRUCTIONS.md). The evidence-scoping discipline in the TAU-2 README is relevant to §16 (Testing) and the future Evaluation Lab.

**Classification:** VALIDATION (hybrid retrieval + benchmark rigor already match OCBrain's stated intent) plus RESEARCH TRACK (trajectory-memory injection at write-time specifically).

## 2.3 Apache Maka (`apache/maka`) — Tier A, deep dive done

**What it is:** an ASF-incubating "agent workspace that keeps a complete record of everything it did." TypeScript, Electron desktop app + CLI/TUI. [FACT]

**Architecture (verified, from `ARCHITECTURE.md`):** "Maka has one execution authority: Runtime Host." [FACT] `Runtime Event Log` is "the canonical source for model messages, tool calls, tool results, and termination facts. Context pruning and compaction change provider input projections, not history." [FACT] Layering: `SessionManager`/`AgentRun` own execution lifecycle; `Agent Graph` schedules dependent work as ordinary child Sessions through the *same* Runtime; `Storage` owns interactive runtime state only, with "no Eval-specific root, TaskRun ledger, or experiment result authority." [FACT] `packages/core|storage|runtime|runtime-host|eval|cli` is the code-boundary table given directly in the doc. [FACT]

**Notable anti-pattern lesson:** "Agent Swarm" — multi-agent fan-out — was deliberately implemented with *zero* new execution machinery: "There is one scheduler, one ledger, and one control plane, and they are the graph's... there is no `SwarmRun`, second event ledger, or background owner." A synchronous `agent_swarm` tool existed and was *removed* (#2384) in favor of routing everything back through the single Agent Graph. [FACT]

**Eval-integrity mechanism:** `Cell = task × repetition × subject`; "repetition" (a new statistical sample) is explicitly distinguished from "infra retry" (a replacement attempt for the same cell after infra failure), and "the earliest valid attempt is authoritative; operators cannot choose a preferred outcome" — this prevents both infra flakiness from polluting variance and cherry-picking of results. [FACT]

**Self-referential rigor:** the architecture doc itself states "Current GitHub issues and source take precedence over older drafts" for its own historical design docs under `docs/archive`. [FACT] — an independent instance of the same "evidence over documents" discipline as OCBrain's own §20.6.

**Limitation:** this is a desktop-app-first product; adopting the *pattern* (one ledger, projections, no parallel execution authority) is straightforward, adopting the *code* is not (Electron/TS stack, different runtime model from OCBrain's Python-first worker pool).

**OCBrain mapping:** LAW 2 (event sourcing over hidden state), the open EventStream/EventBus separation question, §6.2 workflow-engine rules (DAG-based, no recursive spaghetti loops), and the future Evaluation Lab's cherry-picking-resistance requirements.

**Classification:** ADOPT AFTER CURRENT MILESTONE for the "one ledger, N projections" invariant as an explicit architectural statement; VALIDATION for the anti-swarm-machinery stance (matches LAW 4 already).

## 2.4 Prime Agent (`PrimeIntellect-ai/prime-agent`) — Tier A, deep dive done

**What it is:** an open-source coding/research agent built on two named abstractions: the **Recursive Language Model (RLM)** — "context as variables... tools like recursive subagents as function calls... inside a persistent REPL" — and the **Continual Harness** (arXiv 2605.09998) — durable, refinable session state, separate from the immutable base prompt. [FACT/CLAIM — arXiv reference is the repo's own citation, not independently read this session]

**Architecture (verified):** hybrid split — TS/JS `packages/agent` (`agent-loop.ts`, `agent.ts`, `proxy.ts`) for orchestration, and a separate Python `prime-agent-runtime/src/rlm/` (`harness.py`, `repl.py`, `bash.py`, `mcp.py`, `skill.py`) as the actual execution kernel. [FACT]

**Notable mechanism:** `/refine` "reviews the current trajectory and can apply small, evidence-backed updates to supplemental harness state. It never rewrites the immutable base system prompt, and recorded snapshots support rollback." [FACT, quoted from README] This is a session-scoped, lightweight version of exactly the shape OCBrain's §13 Autonomous Evolution pipeline already requires at a heavier, gated cadence (simulate→evaluate→benchmark→safety-validate→human-approve→deploy→monitor→rollback).

**Important self-disclosed limitation, directly relevant to OCBrain's isolation stance:** the README states outright — "Prime Agent executes model-generated Python and project commands with your user permissions. Its worker and kernel processes improve lifecycle isolation and recovery; they are **not** a security sandbox... Run untrusted code or instructions in an external sandbox." [FACT, direct quote] This is independent, self-disclosed confirmation that lifecycle isolation ≠ security sandboxing — exactly the distinction LAW 3 draws by mandating subprocess/container/task-runner isolation rather than "better process management."

**OCBrain mapping:** §7.4 CoderWorker rules, §3 Task Runner process, §13 Evolution Rules, LAW 3.

**Classification:** VALIDATION (OCBrain's isolation posture is stricter and that's correct, per Prime Agent's own admission) plus RESEARCH TRACK (a lightweight, session-local "small evidence-backed harness refinement" tier as a fast path underneath the full Evolution Workflow, for genuinely small increments that don't warrant the full pipeline).

## 2.5 Needle (`cactus-compute/needle`) — Tier A, deep dive done

**What it is:** a 45M-parameter open specialist model for tool calling, device use, and structured extraction. Small footprint (~14MB repo). [FACT]

**API contract (verified from `doc/apis.md`, not just the README):** every `agent.complete()` response is one JSON object carrying `"confidence": 0.94` alongside `prefill_tps`/`decode_tps`/`peak_ram_mb` — confidence is a first-class return value, not an add-on. [FACT, direct quote from documented schema]

**Grounding-as-execution-gate:** "A date argument whose year matches none of the years written in the conversation so far... is reported in `validation.ungrounded`... `run()` does not execute such a call... Pass `strict=False` to execute anyway." [FACT, direct quote] Hallucination-checking is structurally enforced (blocks execution by default) rather than left to prompted carefulness.

**No-free-text contract:** "A request no declared tool can serve is refused with the empty call `[]`. That is the whole contract for off-topic input; there is no free-text fallback." [FACT] Reasoning traces are unconstrained natural language (for legibility) but the call itself is grammar-constrained (for correctness) — a clean separation between "explain" and "act."

**Isolation model:** "Each tuned agent runs in its own worker process... owns an independent engine, KV cache, and conversation." [FACT]

**OCBrain mapping:** this is squarely Research Lens E territory (C-MoE candidate confidence/escalation) and directly informs the "is a small model good enough" decision the brief flags as a major open research area.

**Classification:** ADOPT AFTER CURRENT MILESTONE — the concrete pattern (confidence as a typed field on every routing decision; grounding checks that block execution rather than just warn) is directly portable to C-MoE's eligibility/scoring stage regardless of which model Needle itself is or isn't used for.

## 2.6 x-algorithm (`xai-org/x-algorithm`) — Tier A, deep dive done

**What it is:** X's production "For You" candidate ranking system, open-sourced. Rust. [FACT] Includes trust-and-safety classifiers (`botmaker/`, `abuse-enforcement-service/`, content classifiers) alongside the ranking pipeline — noted for completeness, not a focus of this restudy.

**Architecture (verified from `candidate_pipeline.rs`, `filter.rs`):** an explicit `PipelineStage` enum — `QueryHydrator → DependentQueryHydrator → Source → Hydrator → PostSelectionHydrator → Filter → PostSelectionFilter → Scorer → Selector → SideEffect`. [FACT, read directly from source] Two things stand out beyond the brief's own sketch of "candidate generation → eligibility → scoring → selection":
- **A second, post-selection filter/hydrator pass** — catching candidates that only become ineligible once combined with what else got selected (a diversity or budget constraint, for instance), which a single pre-scoring eligibility pass can't catch.
- **Automatic per-stage observability.** The `Filter` trait's default `run()` method wraps the abstract `filter()` method every implementor writes, and *itself* handles span tracing, `kept_count`/`removed_count`/`filter_rate` metrics recording, and stats emission — via `#[tracing::instrument]` and a stats macro. [FACT, read directly from source] An implementor only writes the filtering logic; instrumentation is structurally guaranteed, not something each stage author has to remember.
- `SideEffect` is a named pipeline stage, not a bolted-on step after the pipeline ends.

**OCBrain mapping:** directly answers the brief's Section F question. C-MoE's candidate-generation → eligibility → ranking → selection → execution → verification → routing-feedback shape is *validated* as the right general direction by this evidence, and the "wrapper auto-instruments the abstract method" pattern is a concretely adoptable implementation technique for §12 Observability Rules (every stage observable "for free" rather than by convention).

**Classification:** ADOPT AFTER CURRENT MILESTONE for the pipeline-stage shape (including the post-selection filter pass, which is easy to miss), ADOPT NOW-adjacent for the auto-instrumenting wrapper pattern specifically, since it's a small, self-contained, high-leverage technique applicable anywhere OCBrain already has a plugin/stage trait.

## 2.7 ai-memory (`akitaonrails/ai-memory`) — Tier A/B, deep dive done

**What it is:** cross-harness persistent memory for AI coding agents (Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Grok, Devin, Kimi, Kiro, and more) sharing one memory server. Rust, multi-crate (`ai-memory-core`, `-consolidate`, `-store`, `-hooks`, `-mcp`, `-llm`, `-web`, `-wiki`, `-workstream`). [FACT]

**Pipeline (verified):** `capture → consolidate → recall → handoff`. [FACT, direct quote] "Handoffs are a protocol here, not a convention — typed, owned, claimed exactly once." [FACT, direct quote] — implying an explicit single-claim/ownership mechanism to prevent double pickup by two agents.

**Source-of-truth model, directly validating OCBrain's own documentation philosophy:** "Your memory is plain markdown. The source of truth is a git-backed wiki of ordinary `.md` files... The database is a derived index that can always be rebuilt from the files." [FACT, direct quote] This is the same "documents are ground truth, index is a rebuildable cache" stance PROJECT_INSTRUCTIONS.md §18.4 already prescribes for OCBrain (`CURRENT_STATE.md` etc. as project memory) — independent convergence, not a new idea to import.

**Directly actionable for a named-but-unbuilt OCBrain component:** the `ai-memory-consolidate` crate contains `curator.rs`, `auto_improve.rs`, `auto_improve_schedule.rs`, `auto_improve_telemetry.rs`, `sweep.rs`, `lint.rs`, `projection.rs`. [FACT] OCBrain's §7.1 already names a `MemoryCuratorWorker` as a canonical worker type, and §18.5 schedules "v4.3.6 Memory Curator Worker" as an upcoming milestone. This crate is close to a working reference implementation of that exact, already-planned component — curation, auto-improvement scheduling, telemetry, and sweep/lint passes over consolidated memory.

**Default-local, zero-cost path:** "the default path uses zero LLM calls: capture, search, and handoffs all work with no API key at all." [FACT]

**OCBrain mapping:** §7.1 (MemoryCuratorWorker), §18.5 (Documentation Infrastructure / v4.3.6 milestone), §18.4 (documentation-as-source-of-truth — validation), session-continuity workflow (§18.4.7) — this is close to a productized version of the HANDOFF.md/zip-archive workflow already in use between this project and Claude sessions.

**Classification:** ADOPT AFTER CURRENT MILESTONE, specifically as direct input to the v4.3.6 Memory Curator Worker design once that milestone opens — this is the single most directly-actionable finding in the whole restudy given it targets a component OCBrain has already named and scheduled.

## 2.8 code-graph-rag (`vitali87/code-graph-rag`) — Tier B, deep dive done

**What it is:** AST-graph-backed code RAG. Python, 12 language grammars (cpp, csharp, dart, go, java, js, lua, php, python, rust, scala, sql), Cypher query layer (graph DB), PyPI-published, enterprise support offering, CI with Codecov/SonarCloud. [FACT]

**Notable modules:** `dead_code.py`, `crash_correlation.py`, `context_pruning.py`, `ast_cache.py`, a dedicated `benchmarks/` directory (11 scripts). [FACT] `crash_correlation.py` in particular — correlating runtime failures back to graph nodes — is directly relevant to a future failure-analysis capability, not just static code search.

**OCBrain mapping:** this is the most substantive evidence in the set for the brief's Research Lens G question ("could OCBrain maintain a graph-based internal model of itself?"). code-graph-rag is existence proof that a multi-language, benchmarked, incrementally-indexed code graph is buildable and maintainable at a serious engineering bar — it is not itself OCBrain's self-model, but it's strong evidence the idea is tractable.

**Classification:** RESEARCH TRACK — "System Self-Model / Repository Intelligence" deserves to become a named future research item (see §7), with code-graph-rag as the primary existence-proof citation.

## 2.9 Archify (`tt-a1i/archify`) — Tier C, light touch

**What it is:** a Claude Code / Codex / Cursor "Agent Skill" that turns a repo or system description into an interactive system map — typed JSON intermediate representation compiled deterministically to portable HTML/SVG, with "before/delta/after" diffing for architecture changes across commits. [CLAIM, from README — not independently verified this session beyond confirming the file layout] Structural evidence: dedicated `authoring-contract.md`, `delivery-contract.md`, and `viewer-runtime.md` reference docs exist, consistent with a formalized typed-IR-in/rendered-artifact-out contract. [FACT — files exist; contents not read this session]

**OCBrain mapping:** Research Lens H (deterministic generation/validation) and, secondarily, Lens G (a repo-to-system-map tool is adjacent to a self-model, though narrower — it visualizes, it doesn't reason over the graph).

**Classification:** FUTURE — worth a full read of the three contract docs before any adoption decision; too early to rank higher than that on this pass. [PENDING]

## 2.10 diagram-design (`cathrynlavery/diagram-design`) — Tier C/D, recon only

**What it is:** a Claude Code / Codex / Factory Droid Agent Skill for generating editorial diagrams (SVG/HTML) from semantic patterns, with schema validation. [CLAIM, from recon-level README read]

**OCBrain mapping:** Lens H only, and narrowly — this is about diagram aesthetics/generation, not architecture.

**Classification:** FUTURE, low priority. [PENDING — recon depth only]

## 2.11 hyperframes (`heygen-com/hyperframes`) — Tier C/D, recon only

**What it is:** "Write HTML. Render video. Built for agents." — deterministic HTML→video rendering, explicit multi-harness plugin support (`.claude-plugin`, `.codex`, `.cursor-plugin`, `.agents`), a "catalog" of composable design blocks. [FACT — structure confirmed; mechanism claims not independently verified]

**OCBrain mapping:** Lens H (deterministic artifact generation) and, weakly, Lens I (a components/blocks catalog is a lightweight instance of capability modularity).

**Classification:** FUTURE. [PENDING — recon depth only]

## 2.12 OpenMAIC (`THU-MAIC/OpenMAIC`) — Tier C, light touch

**What it is:** "one-click generation of immersive multi-agent interactive classrooms" — a Next.js app for AI-generated educational simulations, backed by a JCST'26 paper. [FACT/CLAIM]

**Notable pattern (verified in source, not README):** consistent frontend discipline around lifecycle-driven state — UI status fields ("the fold's `status` only moves when a runner lifecycle event arrives") and explicit ownership comments ("Course identity alone owns its lifecycle") appear repeatedly across `components/workbench/` and `components/edit/`. [FACT, read directly in `.tsx`/`.ts` source] This is event-driven UI-state discipline at the frontend layer — a minor, real confirmation that "UI projections driven by backend lifecycle events, never mutated directly" is a pattern worth holding OCBrain's own future UI work to, but it's frontend engineering hygiene, not core cognitive architecture.

**Classification:** LOW priority validation only; not a source of new architecture for OCBrain's core layers.

## 2.13 MTPLX (`youssofal/MTPLX`) — Tier C, light touch

**What it is:** local LLM inference acceleration on Apple Silicon via multi-token prediction / speculative decoding — "twice as fast." Not an agent-architecture project. [FACT]

**Notable detail:** its own install docs state a defensive-engineering principle worth quoting: if a fan-control dependency is missing, MTPLX "prints install instructions and continues without fan control... **It must not silently enable spin-loop or clock-anchor modes**." [FACT, direct quote] — an explicit "no silent behavior-mode changes" stance, which is a small but real instance of the same discipline behind LAW 4's "avoid hidden side effects." The CLI also exposes a `--stream-stall-deadline-s` flag per its latest commit message, which is directly adjacent to OCBrain's own watchdog/stall-detection concerns, though I did not trace its implementation this session. [PENDING — flagged from commit-log/CLI-surface evidence only, not source-verified]

**OCBrain mapping:** narrow — local-inference tooling, not cognitive architecture. The stall-deadline flag is worth a follow-up look given its direct resonance with the watchdog work.

**Classification:** LOW priority, except the stall-deadline mechanism specifically → RESEARCH TRACK (small, targeted).

## 2.14 modular/modular — Tier D, light touch

**What it is:** Modular's monorepo — Mojo language + MAX inference/compute platform. Large (~353MB shallow clone). [FACT] The `max/` kernel library targets both NVIDIA and AMD GPUs with production-grade compute kernels. [FACT, from README]

**OCBrain mapping:** §10 Distributed Compute Instructions names LocalAI/exo/DeepSeek-V3.1/airllm as the preferred stack, not Modular — this restudy doesn't provide grounds to change that. Modular is real, serious infrastructure, but adopting it would be a platform-level bet (Mojo language, Bazel build), not an architectural pattern to borrow piecemeal.

**Classification:** FUTURE / VALIDATION ONLY — confirms the compute layer is correctly scoped as "swappable accelerator," not something to go deep on now.

## 2.15–2.19 Confirmed low/no relevance (structural recon only, no forced fit)

- **OpenLogi** (`AprilNEA/OpenLogi`) — a Rust, local-first alternative to Logitech Options+ for HID++ device control (mice/keyboards/webcams). [FACT] No agent/cognitive-architecture content. Only very indirect value: another mature example of "local-first done well," nothing OCBrain doesn't already know.
- **vorssaint-utils** — a Swift macOS menu-bar utility app (fan control, now-playing, screen-recording presets). [FACT] No relevance.
- **awesome-gpt-image-2** (`freestylefly`) — a commercial prompt-gallery/SaaS product for image-generation prompts (payment integration, community features). [FACT] No relevance to agent architecture.
- **public-apis** — literally a curated README list of public APIs plus a CI validation script. [FACT] Zero architectural content. Including this in the target set doesn't map to anything — noted plainly rather than force-fit.
- **VoiceStudio** (`debpalash`) — a local-first voice cloning/TTS/dictation desktop studio with an MCP server and a plugin system. [FACT] The MCP-server-plus-plugin-directory shape is a minor, generic confirmation that "expose capabilities as MCP + plugins" is a common shape (Lens I/J), but the product itself (voice/TTS) has no bearing on OCBrain's cognitive core.

**Classification for all five: REJECT as architecture sources.** This isn't a failure of the research — confirming irrelevance by inspection (not assumption) is exactly what was asked for, and it's useful to know none of these are secretly relevant.

---

# 3. Cross-Repository Synthesis

Repeated motifs, independent of which repo I found them in:

- **One ledger, many projections.** Maka states it explicitly; OpenViking's benchmark harnesses and ai-memory's "database is a derived index, files are truth" converge on the same shape from different angles. OCBrain's own `CURRENT_STATE.md`-as-truth convention is a documentation-layer instance of the identical principle.
- **Confidence as a typed, returned value, not a vibe.** Needle returns it on every call; x-algorithm's scorer stage exists specifically to produce ranked, comparable values before selection.
- **Structural gates over prompted carefulness.** Needle blocks execution of ungrounded arguments by default; x-algorithm's post-selection filter catches what a single eligibility pass can't; Maka's "earliest valid attempt is authoritative" removes a human's ability to cherry-pick a result.
- **Self-referential evidence discipline.** Maka's own architecture doc defers to current issues/source over its own older drafts; OpenViking's TAU-2 README explicitly scopes what counts as validated evidence vs. diagnostic-only; OCBrain's own (newly-discovered-this-session) §20.6 does the same thing for governing prompts. Three independent systems converged on "don't trust your own prior documentation without checking."
- **Isolation ≠ sandboxing, and good projects say so out loud.** Prime Agent's README is explicit about this gap in its own design. That's a useful signal: the honest projects flag it rather than imply safety they don't have.

---

# 4. OCBrain Gap Report

**Critical:**
- Structured, queryable decision provenance + conflict detection (Semantica) — `EpisodicMemory.provenance: str` is a single field, not a subgraph.
- `/modules/new` RCE exists in code and isn't in `KNOWN_ISSUES.md` under any heading searched — a tracking gap on a previously-flagged critical item, independent of anything in the 19 repos.

**High:**
- No named component currently plays the "curator" role ai-memory's consolidate crate demonstrates a working shape for — directly relevant given `MemoryCuratorWorker` is already planned (v4.3.6).
- No explicit "post-selection" eligibility pass in however C-MoE's routing is currently structured (worth checking directly against `core/model_router.py` — not verified this session against x-algorithm's two-pass shape). [PENDING]
- Confidence is not currently confirmed as a typed, per-candidate field anywhere in C-MoE's contracts. [PENDING — needs a direct check against current router code]

**Medium:**
- No explicit invariant statement anywhere I've seen equivalent to Maka's "compaction changes projections, not history" for OCBrain's own EventStream.
- No evidence-scoping discipline (à la OpenViking's TAU-2 README) yet exists in whatever OCBrain's evaluation artifacts currently are.

**Low:**
- Auto-instrumenting wrapper pattern (x-algorithm) not confirmed present or absent in OCBrain's own plugin/stage traits. [PENDING]

---

# 5. OCBrain Architecture Validation

Things this restudy independently supports, not just "not disproven":

- **LAW 3 (Isolation Over Convenience) is correctly stricter than the median project in this set.** Prime Agent self-discloses it isn't sandboxed; OCBrain's mandate for subprocess/container/task-runner isolation is the more defensible position, confirmed by a comparable project's own admission of the gap.
- **§18.4's documentation-as-source-of-truth model** is independently converged-upon by ai-memory ("files are truth, DB is a derived index") and Maka ("source takes precedence over drafts").
- **LAW 4's rejection of hidden orchestration** is validated by Maka's explicit removal of a parallel swarm execution path in favor of one graph, one ledger, one control plane.
- **§8.3's hybrid retrieval requirement (BM25 + embeddings + RRF, embedding-only prohibited)** is validated as the right call — OpenViking's own retrieval stack is not embedding-only either.

---

# 6. Proposed Architectural Amendments

Only where evidence is genuinely strong enough to propose something concrete:

**Amendment candidate 1 — Provenance/conflict layer.**
- *Current:* `EpisodicMemory.provenance: str` (§8.2); no described conflict-detection mechanism.
- *Evidence:* Semantica §2.1 above.
- *Proposed change:* a dedicated provenance/conflict subsystem sitting alongside L1–L2 memory — not full PROV-O adoption, but the *shape* (structured provenance object, explicit conflict detector, source tracker) rather than a free-text field.
- *Affected:* memory layer (§8), any subsystem that currently trusts a single `provenance: str`.
- *Migration complexity:* moderate — additive, doesn't require rewriting existing episodic records, but does require a new contract.
- *Timing:* next architectural milestone, not current-milestone correctness.

**Amendment candidate 2 — Auto-instrumenting stage wrapper.**
- *Current:* observability is a per-module requirement (§12.1), enforced by convention.
- *Evidence:* x-algorithm §2.6 above.
- *Proposed change:* wherever OCBrain has a plugin/stage trait (workflow nodes, skill execution, filters), give the trait a default `run()` that wraps the abstract method and handles tracing/metrics automatically, the way x-algorithm's `Filter::run()` does.
- *Affected:* §6.3 (Node Execution Rules), §12 (Observability).
- *Migration complexity:* low — this is additive to existing trait/interface definitions.
- *Timing:* justified hardening, adoptable now-adjacent since it's small and self-contained.

Everything else above is RESEARCH TRACK or ADOPT-AFTER-MILESTONE, not amendment-ready yet — see §7 and §8.

---

# 7. Research Tracks to Add (candidates for the Future Research Vault)

1. **Provenance & Conflict Layer** — motivated by Semantica; question: does OCBrain need a queryable provenance/conflict subsystem beneath L1–L2 memory, and at what complexity budget (full PROV-O vs. a lighter bespoke shape)? Priority: High.
2. **Trajectory-Aware, Injection-Point-Specific Memory Retrieval** — motivated by OpenViking's TAU-2 treatment (top-k at first turn, different top-k before write-like tool calls); question: should OCBrain's retrieval scoring (§8.4) vary by *where in execution* the retrieval happens, not just recency/importance/relevance? Priority: Medium-High.
3. **System Self-Model / Repository Intelligence** — motivated by code-graph-rag + archify; question: is a graph-based internal model of OCBrain's own codebase (source + Git history + runtime events + tests + evaluations) tractable at OCBrain's scale, and what would it be *for* beyond code search? Priority: Medium, explicitly flagged by the brief itself as a candidate track.
4. **Lightweight Session-Local Harness Refinement** — motivated by Prime Agent's `/refine`; question: should there be a fast, session-scoped evidence-backed-update tier underneath the full §13 Evolution Workflow, for increments too small to warrant the whole pipeline, without weakening the pipeline's guarantees for anything that matters? Priority: Medium.
5. **Stall/Deadline Handling in Third-Party Local-Inference CLIs** — motivated by MTPLX's `--stream-stall-deadline-s` flag; narrow question: does its implementation offer anything OCBrain's own watchdog/stall-detection work (whitespace-keepalive, `asyncio.wait(FIRST_COMPLETED)`) doesn't already have? Priority: Low, cheap to resolve.

---

# 8. Roadmap Impact

- **Do now:** none of the above — this was explicitly a research pass, no code changes authorized or made.
- **Justified hardening (small, cheap, near-term):** log `/modules/new` as a tracked `KNOWN_ISSUES.md` entry (independent of the 19 repos, surfaced by the ground-truth refresh); the auto-instrumenting wrapper pattern, if a suitable trait already exists to retrofit.
- **After current milestone:** provenance/conflict layer research; C-MoE candidate-pipeline shape comparison against x-algorithm's two-pass model (needs a direct read of `core/model_router.py` first — not done this session).
- **Next milestone:** feed the ai-memory consolidate-crate findings directly into v4.3.6 Memory Curator Worker design, once that milestone opens.
- **Later / research track:** items 2–5 in §7.
- **Reject:** the five Tier-E repos as architecture sources; Modular as a near-term compute-layer swap.
- **Roadmap-drift flag:** nothing here should trigger scope creep on v4.3.5/v4.3.6/v4.3.7 or the current audit-remediation work — every ADOPT-AFTER-MILESTONE item above is explicitly gated behind milestone completion, consistent with §18.2.1 and the Architecture Freeze Principle.

---

# 9. Final Ranking

**By architectural value to OCBrain:** Semantica > Apache Maka > x-algorithm > OpenViking > ai-memory > Prime Agent > Needle > code-graph-rag > archify > OpenMAIC ≈ hyperframes ≈ diagram-design > MTPLX > modular > VoiceStudio > OpenLogi ≈ vorssaint-utils ≈ awesome-gpt-image-2 ≈ public-apis.

**By near-term implementation value (how directly usable is a concrete piece, not just a pattern):** ai-memory (consolidate crate maps to a named, scheduled component) > x-algorithm (the wrapper-instrumentation trick is a drop-in technique) > Needle (confidence-field + grounding-gate contract shape) > Semantica (valuable but the heaviest lift) > Apache Maka (pattern is portable, code isn't) > everything else, roughly as ranked above.

These two orderings genuinely diverge at the top — Semantica is architecturally the richest find but the most expensive to act on; ai-memory is architecturally narrower but lands almost directly on a component OCBrain has already named.

---

# 10. What We Were Missing

Concrete, not abstract:

- **A provenance/conflict layer under memory.** OCBrain's memory model says what to keep and how to score it; it doesn't currently have a first-class way to answer "why was this believed, and did two sources disagree" the way Semantica's `ProvenanceManager` + `ConflictDetector` do.
- **A working reference shape for the Memory Curator Worker OCBrain already planned but hasn't built.** This isn't a new idea — it's evidence for a component already on the roadmap, which is more valuable than a new idea would have been.
- **Confidence as a returned, typed value on routing/candidate decisions**, and grounding checks that block execution by default rather than warn — both concrete, small, and currently unconfirmed as present in C-MoE's actual contracts (flagged PENDING, needs a direct check).
- **A second, post-selection eligibility pass.** The brief's own sketch of C-MoE's evolution (candidate generation → eligibility → scoring → selection → execution) is missing exactly the step x-algorithm added in production: checking eligibility again *after* selection, because some constraints only bind once you know what else got picked.
- **An explicit, written-down invariant for what compaction/pruning is allowed to touch.** Maka says it in one sentence ("projections, not history"); I did not find an equivalently explicit sentence for OCBrain's EventStream this session, and it's cheap to write one.
- **A confirmed, tracked status for a previously-flagged critical vulnerability.** This isn't from the 19 repos — it's from re-grounding before starting, and it's the kind of gap the research task's own premise (trust current state, not carried-over claims) exists to catch.

---

# 11. Session Status — What's Done vs. Queued

**Done this session, source-level:** Semantica, OpenViking, Apache Maka, Prime Agent, Needle, x-algorithm, ai-memory, code-graph-rag — all with file-path-level evidence, cited above.

**Done, light/targeted touch only:** archify, MTPLX, modular, OpenMAIC — enough to classify and extract one or two concrete details each, not enough for a full per-repo write-up at the same depth as the eight above.

**Done, recon-only (sufficient to classify, not to extract deep mechanism):** diagram-design, hyperframes.

**Confirmed low/no relevance by inspection:** OpenLogi, vorssaint-utils, awesome-gpt-image-2, public-apis, VoiceStudio.

**Queued for next pass, in priority order:**
1. Direct comparison of `core/model_router.py` / `core/provider_mesh.py` against x-algorithm's two-pass eligibility shape — needed before Amendment 2 or the "confidence as typed field" gap can be stated with confidence rather than flagged PENDING.
2. Full read of archify's three contract docs (`authoring-contract.md`, `delivery-contract.md`, `viewer-runtime.md`).
3. `/modules/new` — log as a `KNOWN_ISSUES.md` entry; decide whether a fresh exploit-chain re-verification is warranted before or separately from that.
4. CTX-AUTH-001 and its four sibling red tests — what gap they're tripwiring for.
5. Deeper hyperframes/diagram-design/OpenMAIC passes if any of the research tracks in §7 get greenlit.

Say the word and I'll keep going on any of these.
