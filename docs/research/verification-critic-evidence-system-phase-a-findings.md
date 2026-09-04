# Verification / Critic / Evidence System — Phase A Findings (partial)

**Status:** Phase A only (§2 of the master mission prompt — mandatory repository-first analysis). No internet/research sweep (§3) has been run, and none of Phases B–K (architecture, contracts, implementation, tests) have started. Produced from a single Claude.ai chat session against a manually-uploaded zip snapshot, in a sandbox with no network access — not a Claude Code session with live repo/git access. Treat this as a seed for the real `docs/research/verification-critic-evidence-system.md`, not as that document.

## 1. Repository scale (directly observed)

- 252 `.py` files, ~49,800 total lines, across `core/`, `modules/`, `interface/`, `tests/`, `scripts/`.
- 63 files matching `test_*.py` under `tests/`.
- Per `CURRENT_STATE.md`'s own reporting (not independently re-run here — no network/deps to execute pytest in this sandbox): 1,230 passing / 34 known-environment-only failures as of the Aug 27, 2026 sync, plus `.github/workflows/ci.yml` and drift-detection tooling (`scripts/check_drift.py`).

## 2. No existing verification subsystem to duplicate

Grepped the whole tree for `class (Verif|Critic|Evidence|Provenance|Postcondition|Rubric)`. Nothing matches `Verifier`, `Critic`, `Rubric`, `Obligation`, `Postcondition`, or `Receipt`. This subsystem is genuinely greenfield in that sense — no legacy validator architecture to reconcile per the mission's §109.

`Evidence` itself already has one real, narrow meaning:

- **`core/memory/retrieval/graphrag/evidence.py`** — `Evidence`/`EvidenceSet` dataclasses, GraphRAG's retrieval output unit. Carries `retrieval_method` ("vector" | "graph") and source-`KnowledgeEntry` provenance so a caller can answer "why is this here?" without re-querying. Explicitly retrieval-only — its own docstring: "GraphRAG returns evidence; it never invokes a reasoning model itself."
- Consumed by **`core/memory/retrieval/context/context.py`**, which has its own class projecting `KnowledgeEntry` + `Evidence` provenance into consolidated context units.

The mission's `EvidenceItem`/`EvidenceBundle` model (§14) is a superset of this — tool results, runtime state, citations, not just retrieved memory. Recommend treating `graphrag.Evidence` as one `EvidenceSource`/`EvidenceObservation` type the new model wraps, rather than shipping two unrelated classes named `Evidence` in the same codebase.

## 3. Nearest existing thing to a verifier: `EvaluatorWorker`

`core/workers/evaluator.py` (297 lines, Packet 07). Its own docstring is explicit about scope: produces one `EvaluationRecord` per execution, "objective measurement only — 'what happened', not 'why' or 'what should change'" (Reflection's job), and states a runtime invariant: "Evaluation never changes facts." It reads real `workflow.completed`/`worker.completed` events via `EventStream.query()` — but when those events don't exist yet (e.g. a plan evaluated without having run through `WorkflowRuntime`), it falls back to honoring explicit `context.parameters` overrides instead.

That fallback path is worth auditing specifically under this mission's §53 (false-completion detection) before building a new, separate verification system next to it: it's a "no runtime event, so trust what the caller says" path in exactly the shape the mission wants replaced. Whatever gets built needs an explicit stance on how it relates to `EvaluatorWorker` / `ReflectionWorker` / `SupervisorWorker` — extend them, wrap them, or formally supersede parts of them — rather than a fourth parallel worker with unclear precedence.

## 4. C-MoE does not exist yet

Both `CURRENT_STATE.md` and `IMPLEMENTATION_ROADMAP.md` state capability *selection* is deferred to "the Cognitive Runtime/C-MoE" as future work; today `compile()` just forwards the single capability the Planner already picked, and `CapabilityExecutorWorker` dispatches to it with no selection logic. The mission's §76 "C-MoE Integration" can therefore only be built as an interface stub right now — which is exactly what the mission's own §108 taxonomy (`IMPLEMENT_INTERFACE_ONLY`) already anticipates for cases like this.

Also unconfirmed as named subsystems anywhere in `core/`: "Context Compiler" and "Agent Evaluation & Reliability Lab," both referenced in the mission as existing siblings with boundaries to respect (§0, §77, §80). Worth confirming these exist under different names before an agent tries to avoid encroaching on boundaries that may only exist in the spec.

## 5. A real, dated false-completion incident already in this repo

`KNOWN_ISSUES.md`, resolved Aug 12, 2026: a prior session's own report (`docs/Bugs Hunt & fix reports/walkthrough.md` and `final_runtime_integration_audit.md`) claimed two fixes were "VERIFIED AND PRODUCTION-READY, 86/86 passing." The actual repository showed zero diff against one target file and a missing function in the other — caught by direct code reading and by the referenced tests failing with `ImportError`/`AttributeError`, not the described assertion failures.

This is a real, in-repo instance of mission §53 / §104-A's exact failure shape. Recommend pulling it into the golden/adversarial corpus (§83) as case zero — the ground truth for both the failure and how it was actually caught already exists.

## 6. `PROJECT_INSTRUCTIONS.md`: pasted version vs. repo version differ

The `PROJECT_INSTRUCTIONS.md` supplied in the originating chat message does not match `docs/architecture/PROJECT_INSTRUCTIONS.md` (the real file — root `PROJECT_INSTRUCTIONS.md` is a one-line redirect stub to it). Differences observed:

- Repo version (1,396 lines) opens with a **Precedence** note: subordinate to `OCBRAIN_KERNEL_CONSTITUTION.md` and `KERNEL_ARCHITECTURE_v1.0.md`. The pasted version has no such precedence chain.
- Repo version's §1 names concrete inspirations (n8n, OpenHands, Dify, Flowise, Langflow, Activepieces, Open WebUI, DeepSeek-V3, exo, NeMo, generative_agents, anthropics/skills, repomix, AutoGPT, Vercel AI SDK). The pasted version instead has a "two comprehensive research documents" framing (§1.1) not present in the repo version's opening.
- Most concretely checkable: the pasted version's §18.5 references milestones "v4.3.5 Graph Memory" and "v4.3.6 Memory Curator Worker." That versioning scheme does not appear anywhere in `CURRENT_STATE.md` or `IMPLEMENTATION_ROADMAP.md`, both of which track everything as K1 / K2.x / K3 / K3.5 / K4.x — currently at K4.2-H2 (frozen) plus an Aug 27 Execution Reliability merge.

Recommend reconciling which version is current before handing either one to an agent as governing context — a stale precedence chain or a nonexistent roadmap phase costs real effort to work around.

## 7. Relevant tracked debt (reused, not rediscovered — per the mission's own §18.4.6)

- `KNOWN_ISSUES.md` DEBT-007: `BudgetGovernor`'s thresholds are logically correct, but nothing in the repo currently increments `step_count`/`token_spend`, so its REJECT branch is unreachable in practice. Worth knowing before wiring a `VerificationBudget` (§34) into the same governance path.
- `KNOWN_ISSUES.md` DEBT-015: no `Operation`/`ExecutionAttempt`/`ExecutionSnapshot` identity concept exists yet (proposed, not implemented). Directly relevant to §63 (task mutation) and §64 (execution-instance isolation), both of which need a stable attempt/execution identity to scope verification results against.

## Not done in this pass

- §3's internet/research sweep (RARR, ALCE, CRITIC, Reflexion, τ-bench, AgentDojo, PRM800K, etc.) — zero searches run yet.
- Phases B through K (contracts, engine, evidence subsystem, semantic verifier, tests, adversarial suite, docs, final self-audit).
