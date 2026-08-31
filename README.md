<img width="1536" height="1024" alt="a5c8335f-e65d-4698-a789-4e1c05752f22" src="https://github.com/user-attachments/assets/2830440e-a250-45ee-95f6-095530b7ddd1" />

# OCBrain

**Overclocked Brain** — a local-first cognitive runtime that turns intent into governed, executable action.

This README reflects what is actually in the repository as of this reconciliation pass (Aug 2026). Where a claim can't be verified, it's marked as such rather than assumed. For day-to-day authoritative status, this project keeps three living documents ahead of the README — **`CURRENT_STATE.md`** (what's built), **`IMPLEMENTATION_ROADMAP.md`** (what's next), and **`KNOWN_ISSUES.md`** (what's broken or deferred) — this file is the entry point, not the deepest source of truth. See `PROJECT_INDEX.md` for the full document hierarchy and repository map.

---

## What OCBrain Is

OCBrain is a kernel for turning a request into a plan, executing that plan through explicit, governed steps, and remembering the outcome — rather than routing a prompt straight to a model. Every persistent-memory mutation and every autonomous action is expected to pass through a governance layer before it happens, and the system is built to emit events for what it does rather than keep state only in memory.

It is not a finished product. It's an actively-developed runtime with a genuinely substantial, working kernel underneath it, an actively-developed cognitive layer on top, and a long list of explicitly-tracked future work ahead of it — see [Milestone Status](#milestone-status) below.

## Current Development Status

| Area | Status |
|---|---|
| Kernel (K1 → K3.5.1) | Built. Not yet formally frozen — see [Kernel v1.0](#kernel-v10) below. |
| K4.2 — Cognitive Front-End | **Complete.** Packets 01–09, plus H1 (frozen Aug 17, 2026) and H2 (closed Aug 22, 2026) hardening passes. |
| Execution Reliability (watchdog/budget) | **Partial.** A same-day fix for a real production bug merged Aug 27, 2026. The larger proposed architecture behind it is research/design only — nothing beyond the bug fix is implemented. |
| C-MoE (Cognitive Runtime) | **Research phase.** Papers and reference repositories are being studied; no implementation, no transition plan, no milestone number assigned yet. |

Independently verified this pass: `pytest tests/ -q` → **1331 passed, 34 failed**, out of 1365 collected. All 34 failures were traced to one shared cause — this sandbox has no route to `huggingface.co` to download the sentence-transformer embedding model a shared test fixture needs — which matches the "34 pre-existing environment-only failures" figure the project's own documents have reported consistently since at least July 2026. No unexpected failures were found.

---

## Architecture Overview

Authority runs from principles down to code:

```
OCBRAIN_KERNEL_CONSTITUTION.md          9 laws, 9 invariants — highest authority
  └─ docs/architecture/KERNEL_ARCHITECTURE_v1.0.md   Frozen engineering spec
       └─ docs/architecture/PROJECT_INSTRUCTIONS.md  Operational engineering rules
            └─ ARCHITECTURE_CHANGELOG.md, ADRs        Historical decisions
                 └─ CURRENT_STATE.md → IMPLEMENTATION_ROADMAP.md → KNOWN_ISSUES.md
```

The kernel (runtime, workflow engine, capability registry, governance, memory, events) is meant to be stable and domain-agnostic. The Cognitive Front-End (K4.2) is built *on* the kernel, not *as* the kernel: intent interpretation → goal formation → constraint extraction → capability discovery → planning → plan compilation → validation, with reflection/evaluation/supervision workers wrapping the loop.

## Runtime / Execution Flow

**Correction (this pass):** an earlier version of this section described only the K4.2 path below, as though it were the whole flow. It isn't. `core/orchestrator.py`'s `Orchestrator.handle()` — the single method `main.py` and `interface/api.py` actually call for every request — is built on an older foundational pipeline (`core/parser.py`, `core/classifier.py`/`classifier_v3.py`, `core/decomposer.py`, `core/dispatcher.py`, `core/merger.py`, `core/module_registry.py`/`module_factory.py` dispatching into `modules/`) that none of this reconciliation's prior passes read or accounted for. It is **not** dead code — `Orchestrator.__init__` takes `modules` as a direct constructor argument from `main.py`. This project's own evidence-over-assumption principle means that pipeline needs its own dedicated audit before this README can describe it with the same confidence as the rest of this document. It is flagged here rather than silently left out. See [Known Limitations](#known-limitations).

What can be said with the same confidence as the rest of this file, because it's a direct code fact, not an inference: `config/settings.toml` sets `[runtime] use_k42_frontend = true`, and `main.py` reads that value and passes it straight into `Orchestrator`'s constructor — so the K4.2 path below is the default for a request, not a fallback. Inside `Orchestrator.handle()`, this happens conditionally — reached "if `self._use_k42_frontend` and a `WorkflowRuntime` was supplied at construction" — which does mean the older pipeline is still live in the same method for whatever cases fall outside that condition; this pass did not determine exactly which requests those are.

A request entering through `Orchestrator.handle()` with the K4.2 front-end enabled (`[runtime] use_k42_frontend` in `config/settings.toml`) follows:

```
interpret_request() → plan() → compile() → WorkflowRuntime.execute()
```

Every node execution is supervised by an `ExecutionWatchdog`/`ProgressMonitor` pair and every persistent memory mutation (`write`/`update`/`delete` on `UnifiedMemory`) calls `GovernanceKernel.evaluate_action()` first. When the condition above isn't met, `Orchestrator.handle()` falls back to its older built-in pipeline instead — not specifically a "`PlannerWorker` path," as a prior version of this file said; `PlannerWorker` (K2.2) is one worker that pipeline can dispatch to, not the whole mechanism. That fallback pipeline's own governance/observability posture has not been verified by this reconciliation.

## Implemented Components

| Component | Location | Status |
|---|---|---|
| GovernanceKernel + 5 governors | `core/governance/` | Live — evaluated on every action |
| WorkflowRuntime (DAG engine) | `core/workflow/` | Live |
| Capability Registry + Adapters | `core/capabilities/` | Live (Ollama, OpenAI-compatible, model-router adapters) |
| UnifiedMemory (L0–L4) | `core/memory/unified_memory.py` | Live — SQLite + FTS5 + BM25 + embeddings + graph index |
| GraphRAGPipeline | `core/memory/retrieval/graphrag/` | Live — canonical retrieval path |
| Graph index (indexer, entity extraction, eligibility) | `core/memory/graph/` | Live and wired into `UnifiedMemory`'s write/update/delete path — see [Known Limitations](#known-limitations) on why this is easy to miss |
| EventStream (durable) + EventBus (in-process) | `core/events/`, `core/event_bus.py` | Live — two mechanisms, not yet unified (`KNOWN_ISSUES.md` DEBT-004/005) |
| Cognitive Front-End (K4.2.1–K4.2.7) | `core/cognitive/` | Live |
| SupervisorWorker, ReflectionWorker, EvaluatorWorker | `core/workers/` | Live (built Packets 07/08, wired Aug 8, 2026) |
| ExecutionWatchdog / ProgressMonitor | `core/runtime/watchdog.py`+`progress.py` (graph-aware) **and** `execution_watchdog.py`+`progress_monitor.py` (standalone) | Live, but two independent, unreconciled implementations — see DEBT-016 |
| CLI / API interface | `interface/cli.py`, `interface/api.py` | Live (FastAPI) |

---

## Milestone Status

### K4.2 — Cognitive Front-End
**Status: Complete.** All 9 packets, plus hardening passes H1 (frozen Aug 17, 2026, independent 16-gate review) and H2 (closed Aug 22, 2026). Two items remain explicitly open, not silently dropped: DEBT-011 (an open-domain-vs-closed-enum contradiction between K4.2's `ContentDomain` and K4.1-L's `LearningCandidate`, deliberately left as a `[RECONCILE-PENDING]` marker) and DEBT-002 (a governance field, `delegating_worker_type`, that nothing currently populates).

### K4.3 — Architecture-to-Implementation Transition
**Status: Historical / already executed.** This is worth stating plainly because it does not mean what it's sometimes assumed to mean: **K4.3 is not C-MoE.** The document `docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md` is the planning artifact that broke the frozen K4.2 architecture into the nine packets above — its own validation checklist explicitly defers capability selection to "future C-MoE." A separate closeout report states its own scope as *"K4.2 finish-and-close — no K4.3, K4.4, or C-MoE work introduced,"* naming all three as distinct items, not synonyms. The transition document's own header still reads "Status: DRAFT — awaiting approval" (dated July 24, 2026) even though the work it planned shipped — that header is stale and should be updated to reflect that it was executed.

### C-MoE — Cognitive Runtime
**Status: Research phase.** Per the maintainer, this is currently a literature- and repository-study effort, not implementation — consistent with what's on disk: `docs/architecture/future_debt_study/OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md` is an architecture study, not a build. It has no assigned milestone number yet; it's referred to by name or loosely as "K4.3+/C-MoE" (i.e., sometime after K4.3). Zero implementation exists.

### Execution Reliability ("K4.4")
**Status: Partial.** Two sessions independently built overlapping `ExecutionBudget`/`ExecutionWatchdog`/`ProgressMonitor` implementations on branch `feature/execution-progress-inspection`; the collision surfaced a real contract-mismatch bug (an edit-style request crashed because the graph-aware watchdog called the model-router-facing `ExecutionBudget`'s old constructor signature), fixed and merged Aug 27, 2026 (commit `7ca7f35`). The label "K4.4" is used inconsistently across the project's own documents: `IMPLEMENTATION_ROADMAP.md` explicitly calls it *"informally labeled... not an official roadmap number,"* while `KNOWN_ISSUES.md` uses "K4.4" more casually in its own sync log and a debt title. Neither is wrong exactly, but they disagree — worth the project settling on one convention. The larger proposed architecture behind this (`Operation`/`ExecutionAttempt`/`ExecutionSnapshot`, giving retries a stable identity) is fully researched and written up in `docs/reports/WATCHDOG_EVOLUTION_RESEARCH_AND_ARCHITECTURE_REPORT.md` — **status: proposed only, nothing beyond the bug fix is implemented** (DEBT-015). The two watchdog implementations also remain functionally separate, not unified (DEBT-016).

### Kernel v1.0
**Status: Not frozen.** `docs/Bugs Hunt & fix reports/KERNEL_V1_0_PRE_FREEZE_DEBT_RECONCILIATION_AUDIT.md` identifies a minimum blocking-closure set of 2 items before freeze — a Kernel-Constitution-adjacent identity decision and a narrow authority conflict between a frozen ADR and existing code — both explicitly left open for the project owner to decide, per this project's own rule against silently resolving Constitution-adjacent questions.

---

## What Is Not Yet Implemented

- **C-MoE** — capability selection/routing among multiple candidate adapters. Research only.
- **CoderWorker, BrowserWorker** — declared as future cognitive workers, not built.
- Several declared `CapabilityType` values have no registered adapter: `embedding`, `web_search`, `browser_automation`, `file_access`, `memory_search`, `graph_traversal`, `image_generation`, `tool_invocation`, `external_api`.
- **Workflow checkpoint/resume** — `EventStream.create_checkpoint()` exists but `WorkflowRuntime` never calls it; a long-running workflow can't survive a process restart (DEBT-003).
- **Budget enforcement, operationally** — `BudgetGovernor` correctly rejects when step/token counters exceed threshold, but no code anywhere currently increments those counters, so the reject branch is unreachable in practice today (DEBT-007). This is a governance mechanism that is contractually correct but not operationally active — worth flagging given how central governance is to this project's own stated priorities.
- **Operation identity across retries** — a retried request is indistinguishable from a fresh one; researched and proposed (DEBT-015), not built.

## Legacy / Transitional Components

`modules/` is explicitly labeled "Legacy expert modules" in `PROJECT_INDEX.md` — 13 files across `web_search`, `mock`, `system_ctrl`, `empty_test`, `knowledge`, `coding`, and a `_template`. "Legacy" here means architecturally superseded by the capability-adapter system, **not** unmaintained or dead: `modules/system_ctrl` received a real security fix (input validation on an `os.startfile()`/subprocess call path) as recently as this project's A6/A7 remediation. Treat it as legacy-but-live, not safe to delete without checking call sites first.

## Technical Debt

Full register: `KNOWN_ISSUES.md`. Highlights:

- Two independent `ExecutionWatchdog`/`ProgressMonitor` pairs coexist and will drift again if either is touched in isolation without reconciling the other (DEBT-016).
- Three overlapping event mechanisms — `EventBus`, `EventStream`, `KnowledgeEvent` — record different facts about different concerns; no single unified audit trail yet (DEBT-004/005).
- `AgentGovernor`'s delegation-permission check is dormant: `SupervisorWorker` exists but nothing populates the metadata field the check depends on (DEBT-002).
- L2 semantic memory embeddings are volatile and recomputed on every restart (DEBT-006).
- Running the full test suite currently rewrites two tracked config files in place as a side effect of a fixture that isn't isolated to a temp path (DEBT-012) — cosmetic (line-ending changes only), not data-lossy, but will keep surprising people until fixed.

## Repository Structure

Verified against the actual tree, not the aspirational one previously in this file:

```
ocbrain/
├── main.py                      # Composition root — asyncio entrypoint, all singletons wired here
├── OCBRAIN_KERNEL_CONSTITUTION.md
├── CURRENT_STATE.md / IMPLEMENTATION_ROADMAP.md / KNOWN_ISSUES.md / PROJECT_INDEX.md
├── PRODUCT.md / README.md / CHANGELOG.md
│
├── core/
│   ├── (flat files directly in core/, NOT individually audited by this reconciliation — see Known Limitations)
│   │   ├── orchestrator.py          # Orchestrator.handle() — the real single entry point; built on the files below
│   │   ├── orchestrator_v3.py, classifier.py, classifier_v3.py, parser.py, decomposer.py, dispatcher.py, merger.py
│   │   ├── module_registry.py, module_factory.py    # loads/dispatches modules/ (see Legacy section)
│   │   ├── brain_api.py, brain_export.py, brain_version.py
│   │   ├── migrator.py, privacy.py, config.py, context.py
│   ├── runtime/            # Execution runtime, working memory, cancellation
│   ├── workflow/           # DAG engine (definition, instance, result)
│   ├── capabilities/       # Registry, adapter runtime, concrete adapters
│   ├── governance/         # GovernanceKernel + 5 governors
│   ├── cognitive/          # K4.2 front-end: intent, planner, learning, etc. (flat modules, not subdirectories)
│   ├── workers/            # Planner, Supervisor, Reflection, Evaluator, MemoryCurator
│   ├── memory/
│   │   ├── unified_memory.py
│   │   ├── graph/          # Graph index: engine, indexer, entity extraction, eligibility
│   │   ├── retrieval/      # Fusion façade, context builder, GraphRAG pipeline
│   │   ├── backends/, consolidation/
│   │   ├── cognitive_vault.py, mem_vault.py, hybrid_retrieval.py, dedup.py  # older memory stores — not yet audited;
│   │   │                                                                    #   unified_memory.py has an explicit
│   │   │                                                                    #   import_from_cognitive_vault() migration method
│   ├── events/             # EventStream (durable)
│   ├── event_bus.py        # EventBus (in-process, non-durable)
│   ├── knowledge/, learning/, meta/, observability/, pipeline/, prompt/, skills/
│   ├── web/, web_learning/ # Knowledge-acquisition path
│   ├── dashboard/, shadow/
│   ├── orchestrator.py, model_router.py, provider_mesh.py
│
├── interface/              # FastAPI (api.py) + CLI (cli.py) + tray/updater/voice
├── modules/                # Legacy expert modules (see above)
├── config/                 # settings.toml, models.toml, sources.toml
├── docs/
│   ├── architecture/       # Canonical specs, decisions/ (ADRs), future_debt_study/, archive/
│   ├── reports/, Bugs Hunt & fix reports/
├── tests/
```

Note: `core/cognitive/` and `core/memory/graph/` exist on disk but were missing from `PROJECT_INDEX.md`'s own directory tree prior to this pass — corrected there as part of this reconciliation.

## Installation / Setup

Verified from `pyproject.toml` (requires Python ≥3.11):

```bash
pip install -e .
```

Optional extras exist for `training` (LoRA fine-tuning: torch, trl, peft, bitsandbytes) and `voice` (whisper, pyttsx3, sounddevice) — install with `pip install -e ".[training]"` / `".[voice]"` if needed.

## Running OCBrain

Two real entry points are declared in `pyproject.toml`:

```bash
ocbrain          # → interface.cli:cli
ocbrain-start    # → main:main (the FastAPI server + scheduler)
```

Default configuration (`config/settings.toml`) points at a local Ollama instance (`http://localhost:11434`) — Ollama running locally is assumed, not bundled.

## Running Tests

```bash
pytest tests/ -q
```

1365 tests collected; 1331 pass in an offline sandbox. The remaining 34 require downloading a sentence-transformer embedding model from HuggingFace Hub and will fail without that network access — this is environment-dependent, not a code defect, and matches the count this project has tracked consistently since July 2026.

## Configuration

Three tracked TOML files in `config/`: `settings.toml` (runtime flags, e.g. `use_k42_frontend`), `models.toml`, `sources.toml`. Note: the full test suite currently has a side effect of rewriting `models.toml`/`sources.toml` in place (DEBT-012) — `git checkout -- config/models.toml config/sources.toml` afterward if you see a spurious diff. Two more config files exist and were not investigated this pass: `settings.yaml` and `user_prefs.yaml` — their relationship to the TOML files (superseded, complementary, or read by the un-audited orchestrator pipeline specifically) is unknown.

## Development Workflow

Governing rules live in `docs/architecture/PROJECT_INSTRUCTIONS.md` (a stub at the repository root points here). It is explicitly subordinate to the Kernel Constitution and `KERNEL_ARCHITECTURE_v1.0.md` — see `PROJECT_INDEX.md` for the full document authority order. Before starting new work, that project's own convention is: check `CURRENT_STATE.md` for what's built, `IMPLEMENTATION_ROADMAP.md` for what's next, and `KNOWN_ISSUES.md` for what's already known to be broken or deferred, before doing repository-wide exploration.

## Known Limitations

- **This reconciliation's biggest gap: an entire foundational request pipeline was found late and not fully audited.** Three prior passes of this documentation effort read `core/cognitive/`, `core/workflow/`, `core/governance/`, `core/capabilities/`, `core/workers/`, and `core/memory/unified_memory.py` in real depth, but used directory-only searches (`find core -maxdepth 2 -type d`) that never surfaced the ~16 files sitting directly in `core/` itself — `orchestrator.py` (the actual method every request goes through), `orchestrator_v3.py`, `classifier.py`, `classifier_v3.py`, `parser.py`, `decomposer.py`, `dispatcher.py`, `merger.py`, `module_registry.py`, `module_factory.py`, `brain_api.py`, `brain_export.py`, `brain_version.py`, `migrator.py`, `privacy.py`, `config.py`, `context.py` — nor the older memory stores (`cognitive_vault.py`, `mem_vault.py`, `hybrid_retrieval.py`, `dedup.py`) or `core/meta/`. These were confirmed live (imported directly by `main.py` and `interface/api.py`, not orphaned), and the K4.2 front-end is confirmed to be the default path (`use_k42_frontend = true`), but the fallback pipeline's own correctness, governance coverage, and relationship to `modules/` deserves the same file-by-file rigor the K-milestone system got, not the same-day patch this pass could give it. Treat everything in this README about `core/orchestrator.py` and its dependencies as provisional until that happens — everything else in this document was independently verified against source and a live test run.

- **Version identifiers disagree.** `version.txt` says `2.1.1`; `pyproject.toml` says `2.0.0`; the current branch/export is named `v4.1`. Worth the project picking one canonical version and propagating it.
- **Two parallel work-tracking conventions coexist.** Most status documentation uses the "K" milestone numbering (K1, K2.x, K3, K4.2.x...). Some real, live, well-integrated code — including the graph memory index — is instead attributed to an informal "Session N" numbering in code comments (Session 4 through at least Session 5.25) that isn't cross-referenced from `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, or `KNOWN_ISSUES.md`. This is almost certainly why graph memory reads as more "hidden" than it is — it's live and tested (`tests/test_graph.py`, `test_graph_indexer.py`, `test_graphrag.py`), just tracked in a different system than the one the milestone docs use.
- **`PROJECT_INDEX.md`'s own Report Chronology table admits a gap** since ~July 2026 (several K3/K4/K4.1/K4.2 reports aren't listed) — flagged in that file already, not fixed here as it's outside this pass's scope.
- **This reconciliation pass had no git history** (the reviewed copy had no `.git`), so claims that ultimately trace back to a commit hash (e.g. `7ca7f35`, `a6b012e`) were verified against the source tree and test suite where possible, but not against `git log` directly.
- The PROJECT_INSTRUCTIONS.md distributed outside this repository (e.g. pasted into a chat session) differs slightly from the in-repo copy at `docs/architecture/PROJECT_INSTRUCTIONS.md` — notably a precedence statement present in-repo but not in at least one external copy seen. Treat the in-repo copy as canonical.

## Next Development Steps

In the order the evidence actually supports:

1. Close the 2 Kernel v1.0 pre-freeze blockers (owner decision required on both).
2. Reconcile DEBT-011 (`ContentDomain` vs. `LearningCandidate`) before extending `ContentDomain` further.
3. Decide the "K4.4" naming question (informal vs. official) so `IMPLEMENTATION_ROADMAP.md` and `KNOWN_ISSUES.md` stop disagreeing with each other.
4. Continue C-MoE research; do not begin implementation or assign it a milestone number until a transition plan (a "K4.4→next" equivalent of the K4.3 document) exists and is approved.
5. Only after the above: the Documentation Infrastructure Phase described in `PROJECT_INSTRUCTIONS.md` §18.5 (this pass covers much of its intent for `README.md`, `PROJECT_INDEX.md`, `KNOWN_ISSUES.md`; `ARCHITECTURE_DECISIONS.md` and `MEMORY_ARCHITECTURE.md` as unified files still don't exist — `docs/architecture/decisions/` + `ADR_INDEX.md` currently cover the former function in a different shape).

## Architecture Principles

From `docs/architecture/PROJECT_INSTRUCTIONS.md`, in priority order when they conflict:

```
Governance → Replayability → Isolation → Observability →
Reliability → Determinism → Extensibility → Performance → UX
```

## Research / Future Directions

`docs/architecture/future_debt_study/` contains architecture studies — not implementations — covering C-MoE-style adaptive cognitive scaling and durable-execution patterns (Temporal/LangGraph/Restate-inspired). These exist to inform future ADRs before any code is written, per this project's own Architecture Freeze Principle.

---

*This file was rebuilt from repository evidence (source tree, test run, and the project's own status documents) rather than patched. Where a claim above conflicts with a newer commit, `CURRENT_STATE.md` wins — see `PROJECT_INDEX.md` for the full authority order.*
