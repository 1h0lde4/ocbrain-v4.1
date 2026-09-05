# OCBrain — External Research Brainstorm (September 2026)

**Purpose:** Per the governing task ("check all available research papers and github repos to find and brainstorm ideas that can strengthen OCBrain"), and per `PROJECT_INSTRUCTIONS.md` §18.4.6 (Audit Reuse — review existing research before launching a new one). This document does two things: (1) states plainly what was already found, so nothing below duplicates it, and (2) adds a small number of new, externally-sourced ideas that are not yet in the repository's own research corpus, each evidence-tagged per this project's own convention (`[FACT]` / `[EXT]` / `[INFER]` / `[DECISION]`).

**Scope discipline (per Architecture Freeze Principle, §20.5):** Kernel v1.0 is `NOT_FREEZE_READY` per `CURRENT_STATE.md`. Nothing below is implemented. This is research and proposal only — the correct next step for each item is an entry in `docs/architecture/FUTURE_RESEARCH_VAULT.md` or a new `KNOWN_ISSUES.md` row, not code.

---

## 0. What was checked first (Audit Reuse)

Before searching externally, the following were read to establish what this repository already knows:

- `docs/archive/research/OCBRAIN_EXTERNAL_REPO_STUDY.md` (V1, 20 repos — CrewAI, Unsloth, skill-catalog projects)
- `docs/archive/research/OCBRAIN_EXTERNAL_REPO_STUDY_V2.md` (70 repos — reasoning/planning/agentic-architecture clusters, including enterprise multi-agent SDKs and knowledge-augmented planning)
- `docs/archive/research/OCBRAIN_EXTERNAL_REPO_STUDY_V3.md` (27 personal cognitive-AI projects and reasoning-discovery lists)
- `docs/archive/research/OCBRAIN_FUTURE_ARCHITECTURE.md`
- `docs/architecture/FUTURE_RESEARCH_VAULT.md` (FR-0001–FR-0015, plus the Priority A/B/C repository study backlog)
- `docs/reports/WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md` (Temporal / LangGraph / Restate / AgentRewind / AgentTether / CapLease — sourcing DEBT-015)
- `docs/architecture/future_debt_study/OCBRAIN_RELIABILITY_DURABLE_EXECUTION_ARCHITECTURE_STUDY.md` (deliberate decision to extend `EventStream` rather than adopt Temporal wholesale)
- `docs/studies/OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md`, `OCBRAIN_CMOE_VERIFICATION_ARCHITECTURE_STUDY.md`, and `docs/architecture/future_debt_study/OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md` (C-MoE research phase — cites AgentTether, Bazel Skyframe/Buck2 DICE for invalidation)
- `KNOWN_ISSUES.md` in full (DEBT-002 through DEBT-018)

**Conclusion of that review:** this project's own research corpus on reasoning architectures, multi-agent orchestration, durable execution, and invalidation models is already unusually deep — deeper than a fresh external pass would typically produce. Re-running that ground would waste effort against §18.4.6. The value-add below is therefore narrow and targeted: one verified code-level gap this research corpus doesn't mention at all, plus four external items confirmed (by keyword search across every `.md` in the repository) to be genuinely absent from the existing research.

---

## A. A verified gap the existing research corpus does not cover: there is no code-execution sandbox anywhere in this repository

**[FACT]** `PROJECT_INSTRUCTIONS.md` §3 mandates a four-process runtime including a **Task Runner** ("sandboxed code execution, isolated subprocess runtime, JS/Python execution, restricted execution environment"), and §7.4 requires `CoderWorker` to "operate in sandboxed environments." Law 3 (§2) forbids inline execution of generated Python/JavaScript/shell and requires subprocesses, containers, or restricted environments.

**[FACT]** Verified directly against the checked-out repository (`main`, commit `6a6c805`):
- `core/workers/` contains exactly seven files: `base.py`, `capability_executor.py`, `curator.py`, `evaluator.py`, `planner.py`, `reflection.py`, `supervisor.py`. No `coder.py` and no `CoderWorker` class exists anywhere (`grep -rn "CoderWorker" --include="*.py" .` returns only a reference inside `tests/test_k2_4_governance.py`, i.e. a test fixture name, not an implementation).
- There is no `task_runner`, `TaskRunner`, or sandbox module anywhere in the repository (`find . -iname "*task_runner*" -o -iname "*sandbox*"` returns nothing).
- `modules/coding/module.py` (81 lines, read in full) is the only "coding" capability that exists today. It generates code as text via an LLM call (`generate_with_fallback`) and validates the result with `ast.parse()` — a **syntax check only**. There is no `subprocess`, `docker`, `exec()`, `eval()`, or any execution of the generated code anywhere in that file, or anywhere else in `modules/` or `core/`.

**[INFER]** OCBrain can currently *write* code but cannot *run* it. This is not one of the tracked DEBT items in `KNOWN_ISSUES.md` — it isn't debt against something built, it's a mandatory architectural component (§3's fourth process) with zero implementation, which is a different kind of gap than the ones already tracked there. None of the three research corpora (V1/V2/V3) or the Future Research Vault mention sandboxed execution technology at all — this appears to be a genuine blind spot, not a deliberately deferred item (nothing in `FUTURE_RESEARCH_VAULT.md`'s FR-0001–FR-0015 or its "Deliberately Deferred Architecture" table in `KNOWN_ISSUES.md` names it).

This is the one item below that isn't "brainstorm" in the speculative sense — it's a concrete missing piece with a clear owner (whoever eventually builds `CoderWorker` / the Task Runner process) and it's worth having options on file before that work starts, per §18.4.1's "documentation-first" principle.

---

## B. New external findings (not present in this repository's research corpus)

Each item below was checked by keyword grep against every `.md` file in the repository before inclusion; none produced a hit, confirming genuine novelty relative to this project's own research memory.

### B1 — Sandbox technology options for the Task Runner (directly answers Section A)

**Problem:** §3/§7.4/Law 3 require sandboxed execution; nothing exists yet.

**What repositories/projects inform this:** `google/gvisor` (user-space kernel intercepting syscalls, Apache-2.0), `firecracker-microvm/firecracker` (AWS's microVM VMM, ~125ms cold boot, dedicated kernel per sandbox), `e2b-dev/E2B` (Firecracker-based, open-source control plane, purpose-built SDK for agent code execution), and lighter-weight Linux-native options not cloud-oriented at all: `google/nsjail` and `containers/bubblewrap` (both self-hostable with no VM layer, suited to a fully local, no-cloud-dependency deployment).

**Why this matters for OCBrain specifically:** Law 5 (Local-First) rules out the managed-cloud options most current comparisons default to (E2B's managed runtime, Modal, Daytona — all send code to someone else's infrastructure). That narrows the realistic candidate set to **gVisor** (container-speed startup, weaker isolation, easy to self-host via `runsc`) or **Firecracker** (microVM-grade isolation, self-hostable, but requires bare-metal KVM access — a real constraint if OCBrain ever needs to run inside a VM itself) for anything at container-scale, and **nsjail/bubblewrap** for a lighter, no-VM local option if the isolation bar is "restrict syscalls and filesystem" rather than "assume the code is actively hostile."

**Trade-offs:** gVisor trades some isolation strength for much simpler local self-hosting (no nested virtualization requirement). Firecracker gives materially stronger isolation (separate kernel per execution) at the cost of deployment complexity on non-bare-metal hosts. nsjail/bubblewrap avoid the VM question entirely but share the host kernel, which is a meaningfully weaker boundary for LLM-generated code from an untrusted or adversarially-prompted source (see B4 — this is exactly the class of risk ASI-series threats target).

**What it enables:** an actual, safe implementation path for `CoderWorker` and the Task Runner process — currently the single largest gap between the mandatory architecture in this document and what exists in code.

**Recommendation:** file as a new Future Research Vault entry (or a new `KNOWN_ISSUES.md` "Deliberately Deferred Architecture" row) rather than choosing now — this is a Kernel-completion-adjacent decision, not a C-MoE one, and per the Architecture Freeze Principle it needs its own ADR before implementation.

### B2 — `vllm-project/semantic-router` as a concrete reference for C-MoE's still-empty "Expert Model"

**Problem:** `OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md` §17 states plainly that exactly one `capability_type` (`llm_completion`) is registered anywhere in the system today — there is nothing yet to route *between*. §19–22 of that same study lay out routing policy, candidate generation, routing signals, and a confidence model as open design questions.

**What repository informs this:** `vllm-project/semantic-router` (Apache-2.0, active — v0.3 "Themis" shipped June 2026, ongoing weekly community meetings). It is a self-hostable, Envoy-gateway-based router that classifies incoming requests semantically (via small BERT-family classifiers, not a full LLM call) and directs each one to a specialized backend model or path. Beyond routing, it ships as reusable, independently useful classifier heads: PII/prompt-guard detection, semantic response caching, and a real-time hallucination/factcheck classifier.

**Why it's relevant rather than just interesting:** it is one of the only actively-maintained, self-hostable (no managed-cloud dependency, satisfying Law 5) reference implementations of exactly the problem C-MoE's own study identifies as unsolved — routing *before* generation based on semantic classification rather than a second LLM call. Its PII-guard and hallucination-classifier components are also directly reusable as inputs to `MemoryGovernor`/`ConversationGuardrails` regardless of whether C-MoE routing itself is ever adopted.

**Trade-offs:** it's designed for routing between multiple *model backends* behind an inference gateway, not between OCBrain's broader notion of "capability" (worker/adapter/tool/skill per §17 of the C-MoE study) — architectural translation work would be needed, not a drop-in adoption. It also assumes an Envoy-fronted serving layer, which is an infrastructure dependency OCBrain doesn't currently have.

**What it enables:** a concrete, running reference to compare C-MoE's eventual routing-signal design against, rather than designing routing signals from first principles alone.

### B3 — UK AISI's `inspect_ai` as a foundation for the unbuilt Verification/Critic/Evidence system

**Problem:** DEBT-018 tracks that ~5 of ~90 named Verification/Critic/Evidence contract types exist, on an unmerged branch, with **nothing wired into any live code path**. `OCBRAIN_CMOE_VERIFICATION_ARCHITECTURE_STUDY.md` independently concluded no such subsystem exists yet and designed one from scratch (task-status enum, `primary+verifier` composition, Bazel/Buck2-style dependency invalidation).

**What repository informs this:** `UKGovernmentBEIS/inspect_ai` — MIT-licensed, open-source, developed by the UK AI Security Institute, and (per its own release notes and independent write-ups) adopted internally by Anthropic and DeepMind for frontier-model evaluation. Its core abstraction — `dataset → Task → Solver → Scorer`, with built-in sandboxed execution (process-jail or Docker) and model-graded or custom scoring — maps unusually cleanly onto the same problem shape the frozen Verification study already designed independently: something produces a claim, something else checks it against defined criteria, and the result is a structured, replayable record rather than a self-report.

**Why it's relevant:** it is a working, tested, typed, reproducible implementation of a closely related problem — pluggable "solver" and "scorer" objects that any subsystem can compose, with logs that transform into structured dataframes for analysis (directly analogous to this project's `evals_df`-shaped-and-replay ambitions in §12/§16 of `PROJECT_INSTRUCTIONS.md`). It would not replace the bespoke `Claim`/`Obligation`/`Rubric` contract model already designed, but its `Solver`/`Scorer` composition pattern is a candidate mechanism for the "primary+verifier" hook the frozen study already scoped, rather than building that composition machinery from nothing.

**Trade-offs:** `inspect_ai` is designed around evaluation runs (dataset in, score out), not continuous production-traffic verification gating every live task the way `PROJECT_INSTRUCTIONS.md` §16.2 and the Verification study both intend. Adopting its patterns means translating "evaluation harness" into "always-on quality gate," which is a real design gap, not a drop-in.

**What it enables:** a tested reference for the `Solver`/`Scorer` composition boundary specifically — the part of the ~75-remaining-type Verification system (`VerificationMethod`, `Critique`/`VerificationFinding`, the `*Coverage` types) that is closest to what `inspect_ai` already solved.

### B4 — OWASP Top 10 for Agentic Applications 2026 (ASI01–ASI10) as a Governance Kernel checklist

**Problem:** `PROJECT_INSTRUCTIONS.md` §6.1 names five required governors (`OrchestrationGovernor`, `MemoryGovernor`, `AgentGovernor`, `EvolutionGovernor`, `ConversationGuardrails`) and §19 lists explicit anti-patterns, but neither was checked against a published, adversarially-derived threat taxonomy — they were derived from first principles.

**What informs this:** the OWASP GenAI Security Project's **Top 10 for Agentic Applications 2026**, released December 2025 after peer review by 100+ practitioners — the first taxonomy of its kind specifically for autonomous agents (as opposed to OWASP's earlier, LLM-prompt-focused Top 10). It enumerates ten risk categories (ASI01 "Agent Goal Hijacking" via poisoned tool/RAG/document input through ASI10, spanning excessive privilege, tool/integration misuse, supply-chain compromise in agent-framework dependencies, and memory/state-persistence weaknesses).

**Why it's relevant:** it's an external, adversarially-reviewed checklist to run each existing governor against, rather than trusting that five governors named from first principles happen to cover the real attack surface. ASI01 in particular (goal hijacking via untrusted document/tool content) maps directly onto §11's Knowledge Acquisition pipeline (`crawl → extract → normalize → score → quarantine → validate → consolidate → memory`) — that pipeline's existing quarantine/validate stages are a reasonable structural defense, but nothing in the repository's documentation currently states that they were designed with this specific threat in mind, versus general data-quality concerns.

**Trade-offs:** it's a checklist, not an architecture — applying it produces a gap analysis, not a design. Several of its ten categories (e.g., supply-chain vulnerabilities in agent-framework dependencies) are about the surrounding ecosystem rather than OCBrain's own code, so not every item will produce an actionable OCBrain-specific finding.

**What it enables:** a concrete audit exercise — "map each of the five existing Governors and the Knowledge Acquisition pipeline against ASI01–ASI10, log any uncovered risk as a new `KNOWN_ISSUES.md` row" — that's scoped, bounded, and fits this project's existing audit methodology exactly (recon → targeted read → findings → report).

---

## C. What was deliberately *not* re-proposed

To respect §18.4.6, the following obvious candidates were checked and excluded because this repository has already done substantively equivalent or better work on them:

- **Temporal / Restate / DBOS-style durable workflow engines** — already researched in depth in `WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md` and `OCBRAIN_RELIABILITY_DURABLE_EXECUTION_ARCHITECTURE_STUDY.md`, which explicitly and reasonably decided to extend the existing `EventStream` WAL first rather than adopt external durable-execution infrastructure.
- **MemGPT/Letta-style tiered memory** — Letta is already named in `OCBRAIN_EXTERNAL_RESOURCE_TO_CAPABILITY_RESEARCH_STUDY.md`; OCBrain's own L0–L4 layering is already more granular than Letta's two-tier model.
- **CrewAI / enterprise multi-agent SDKs** — covered in V1 (§"HIGHEST PRIORITY") and V2 Cluster D.
- **Bazel Skyframe/Buck2 DICE-style dependency invalidation** — already the explicit anchor for the Verification study's dependency/invalidation model (§H).
- **Generic event-sourcing/CQRS literature** for reconciling the `EventBus`/`EventStream`/`KnowledgeEvent` triality (DEBT-004/005) — a fresh pass over current material added nothing beyond textbook restatement of principles this project's own architecture already implements; no new pattern was found worth flagging.

---

## D. Suggested filing

Per the Architecture Freeze Principle, none of B1–B4 should become code directly. Suggested disposition:

| Item | Suggested location |
|---|---|
| A — Task Runner / sandbox gap | New `KNOWN_ISSUES.md` "Deliberately Deferred Architecture" row, or new `FUTURE_RESEARCH_VAULT.md` FR-entry — it's a missing mandatory component, not debt against existing code |
| B1 — Sandbox tech options | Attach to the same entry as A |
| B2 — vLLM Semantic Router | Append to `OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md`'s §17–22 as an `[EXT]` reference, or its own Repository Study Backlog entry |
| B3 — inspect_ai | Append to `OCBRAIN_CMOE_VERIFICATION_ARCHITECTURE_STUDY.md` as an `[EXT]` reference against its Solver/Scorer-shaped open items |
| B4 — OWASP Agentic Top 10 | Standalone audit task: map against the five Governors + Knowledge Acquisition pipeline |

I haven't made any of these edits to the canonical docs myself — say the word and I'll fold them in.
