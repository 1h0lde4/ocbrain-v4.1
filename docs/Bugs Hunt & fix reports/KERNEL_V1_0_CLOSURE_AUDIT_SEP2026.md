# OCBrain Kernel v1.0 — Definitive Closure Audit

**Audit date:** September 6, 2026
**Repository:** `1h0lde4/ocbrain-v4.1`, branch `main`, HEAD `6a6c805` (clean working tree)
**Method:** Direct code inspection, fresh test execution, and git/documentation cross-checking performed this session, layered on top of this repository's own extraordinarily rigorous historical self-audit trail (`CURRENT_STATE.md`, `KNOWN_ISSUES.md`, `IMPLEMENTATION_ROADMAP.md`) — which this session independently spot-verified rather than trusted outright, per your own §3 rule.

**A note on evidence provenance, stated once here rather than repeated everywhere below:** every finding is tagged `[VERIFIED-FRESH]` (I read the code / ran the command myself this session), `[VERIFIED-CROSS-CHECKED]` (the project's own documentation makes this claim, and I independently confirmed the specific underlying code fact it depends on), or `[DOCUMENTED-NOT-REVERIFIED]` (the project's own already-rigorous audit trail states this, I did not personally re-run the check this session, and I am saying so rather than implying otherwise). Sections requiring investigation depth beyond what a single audit session's tool budget allows are marked `[NOT COMPLETED THIS PASS]` with a precise statement of what remains, rather than filled with plausible-sounding but unverified content.

---

## 1. Executive Assessment

**Current status: 🟡 CONDITIONAL GO is close, but not yet earned.** The Kernel is materially closer to freezable than a surface read of `KNOWN_ISSUES.md` alone would suggest — the two blockers every fresh-clone audit since July has named (`root_operation_id` identity linkage; `WorkerContext`→`ExecutionContext` migration) are **genuinely resolved**, confirmed by this session's own direct code read, not merely by trusting the resolving document's claim. That is real, hard-won progress and should be credited as such.

But this session found things the existing documentation does not yet capture:

1. **`SupervisorWorker`'s worker-retry path has zero production call sites.** `_attempt_retry()` is fully implemented, unit-tested in isolation, and unreachable in the live K4.2 pipeline — `failed_worker_result`, the parameter that would trigger it, is never populated outside two test files. Meanwhile `WorkflowRuntime` runs its own independent, node-local retry mechanism that does not draw from the shared `OperationRecoveryBudget` the architecture's own comments describe as a single-recovery-budget invariant. This is a real §38 false-completion finding, found by tracing reachability, not by reading a docstring.
2. **A fresh, from-scratch test run this session shows 39 failures, not the 36 last documented** (Aug 31 sync). Reconciled: 34 are the same pre-existing `huggingface.co`-network-unreachable environment class (consistent with every prior sync back to July 30 — this project's clean-room story is real and stable). The other 5 are deliberately-red, intentionally-undeleted security-invariant tests (`CTX-AUTH-001` ×2, plus three **not yet in any synced document**: `CTX-SCOPE-001`, `CTX-CACHE-001`, `CTX-DELETE-001`). These represent four distinct, currently-unfixed, evidenced vulnerabilities: prompt-injection-shaped context poisoning, cross-caller memory-scope leakage, prompt-cache collision, and — most seriously — `UnifiedMemory.delete()` returning `True` when the authoritative L1 deletion actually failed silently underneath it.
3. **`interface/api.py` has no authentication anywhere** — confirmed by exhaustive grep, not assumption. Mitigated by localhost-only binding and a CSRF header that blocks the browser vector specifically, but any other local process on the machine can call every endpoint, including `PUT /config`, unchallenged.
4. **A stale `v1.0.0` git tag exists**, 96 commits behind `main`, predating the entire freeze campaign. It must not be reused or confused with the actual freeze point.

None of this is presented to undercut the real progress on the two historical blockers — it's presented because the four items above are exactly the class of thing a closure audit exists to surface, and none of them were visible from the documentation alone.

**Biggest freeze risks, in order:** (1) the four open `CTX-*` security invariants, particularly `CTX-DELETE-001` (silent-failure-reported-as-success on deletion is a correctness violation with compliance implications, not just a hardening nicety); (2) the two uncoordinated retry mechanisms and the associated loss of a single recovery-budget invariant (DEBT-016 territory, but distinct from it); (3) DEBT-003 (checkpoint/resume) — genuinely unblocked now, genuinely not yet built; (4) the unauthenticated API surface, whose severity depends on a threat-model decision only you can make (is "any local process" inside or outside OCBrain's trust boundary?).

---

## 2. Repository Ground Truth

`[VERIFIED-FRESH]`

- Branch: `main`. HEAD: `6a6c805` ("docs: sync CURRENT_STATE.md/KNOWN_ISSUES.md for Phase C round 2", 2026-09-05). Working tree clean at audit start and end (no code modified — this audit made zero commits to `main`, per your Rule 4).
- Tags: `v1.0.0` → `0efa222` (Aug 14, 2026, message "Fix formatting in release.yml") — **96 commits behind current `main`**. `v4.2.0-k4.2-cognitive-frontend` → `242931c` ("Packet 09 — final review pass"). **Finding:** the `v1.0.0` tag is stale and cannot be treated as evidence the Kernel was ever frozen; it predates the entire ADR-KERNEL-01 identity/migration work and every K4.2 hardening packet after Packet 09. (§53/§54 material — flagged, not fixed, per Rule 4.)
- Remote branches present: `Verifying-code-deployment-consistency`, `eval-lab/research-and-architecture`, `feature/verification-critic-evidence-phase-c` — not merged into `main`; not inspected in depth this session (`[NOT COMPLETED THIS PASS]` — recommend checking whether any contains work that should land before freeze, particularly the verification-critic-evidence branch given DEBT-018's status below).
- No documentation-vs-code contradiction was found regarding current branch/commit state. Where prior sessions' documentation was *itself* found to contain a contradiction and self-corrected in place (the "K4.3 = C-MoE" premise, the "ADR-KERNEL-01 residual identity gap" that traced to not existing), this audit independently re-confirmed the corrected version against code rather than trusting the correction's own say-so — see §4 and §12.

---

## 3. Kernel Boundary

`[VERIFIED-CROSS-CHECKED]` — derived from the repository's own `docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §19 roadmap and this session's direct reachability tracing (§2 above), not assumed from a label list.

| Component | Kernel? | Reason | Required for v1.0? | Post-Freeze? | Evidence |
|---|---|---|---|---|---|
| Cognitive Front-End (Intent/Goal, `intent.py`) | Yes | K4.1 substance; produces the `Goal` every downstream stage consumes | Yes | — | `core/cognitive/intent.py`, live via `use_k42_frontend=true` |
| Planner / capability discovery (`planner.py`) | Yes | K4.2 substance; the only path from Goal to an executable plan | Yes | — | `core/cognitive/planner.py:1173` `discover_capabilities()` |
| Plan Compiler + Governance Gate (`compiler.py`) | Yes | Originally-planned K4.3; already shipped under different packet naming | Yes | — | `compiler.py:259`, gates on `action_type="plan_compile"` |
| WorkflowRuntime / node execution | Yes | Executes compiled plans; owns retry/error-branch semantics | Yes | — | `core/workflow/runtime.py` |
| GovernanceKernel + 5 governors | Yes | Law 1; every autonomous action must pass through it | Yes | — | `core/governance/*` |
| EventStream (durable WAL) | Yes | Sole durability substrate the reliability study chose to extend | Yes | — | `core/events/event_stream.py` (checkpoint API present, unconsumed) |
| SupervisorWorker | Yes | Canonical worker type (§7.1); currently reachable for compilation REJECT/ESCALATE only | Yes, but see §11.E | — | `core/workers/supervisor.py` |
| UnifiedMemory (L0–L4) | Partial | Kernel-required for interaction persistence; the deletion-integrity defect (CTX-DELETE-001) is a Kernel correctness issue, not a memory-feature issue | Yes (for write/read integrity); No (for full L0-L4 feature completeness) | Feature depth beyond correctness | `core/memory/unified_memory.py` |
| ExecutionWatchdog / ProgressMonitor | Yes | Required for long-running-execution safety; currently duplicated (DEBT-016) | Yes | — | `core/runtime/watchdog.py` + `execution_watchdog.py` |
| Verification/Critic/Evidence system | No (not yet) | ~5 of ~90 contract types exist on an unmerged branch; nothing wired into any live path | No — this is why it's not a v1.0 requirement, not because it's undesirable | Yes, continues post-freeze | `feature/verification-critic-evidence-phase-c` (unmerged), DEBT-018 |
| C-MoE (any form) | No | No milestone number owns it; no code of any kind implementing it exists anywhere in the repository (`[VERIFIED-FRESH]`: `grep -rEln "class.*Expert\|mixture.of.expert\|c_moe\|CMoE\|expert_select\|expert_rout"` across `core/` and `modules/` returns zero results) | No | Yes, explicitly | `IMPLEMENTATION_ROADMAP.md`'s own self-correction, §4 below |
| K2.2 `PlannerWorker` direct-invocation path | Yes, but legacy | Still the `else` branch when `use_k42_frontend` is false or `workflow_runtime is None`; intentionally retained fallback, not accidental duplication | Retained-but-not-primary | — | `orchestrator.py`'s branch on `use_k42_frontend` |
| Task Runner / sandboxed code execution (§3 of your own instructions) | Architecturally mandated | Zero implementation anywhere (see prior session's brainstorm report, independently reconfirmed unaffected by this session's work) | **Ambiguous — see below** | Likely yes, but only your call | No `task_runner`/`sandbox` module or `CoderWorker` class exists anywhere in the repository |

**On the Task Runner:** this is a genuine boundary question you need to resolve explicitly, not one this audit can resolve for you. `PROJECT_INSTRUCTIONS.md` §3 lists it as one of four mandatory Kernel processes. But nothing in the current K4.1–K4.4 substance depends on it — no planner output, no compiled plan, no governance gate references arbitrary code execution today. Per your own Anti-Scope-Drift Rule (§61): if the current Kernel can be correctly completed without it, it's POST-FREEZE. By that test, it is POST-FREEZE **for the Kernel's own internal completeness**, but it remains a documented gap against your own architectural mandate that a future milestone must close — recommend an explicit decision recorded either in `KNOWN_ISSUES.md`'s Deliberately Deferred Architecture table (with the §3 mandate cited) or as a new debt item, so it doesn't silently fall out of tracking the way it currently has (it's in neither `KNOWN_ISSUES.md` nor `FUTURE_RESEARCH_VAULT.md` today).

---

## 4. Roadmap Reconstruction (K4.1–K4.4) — and the C-MoE Firewall

`[VERIFIED-CROSS-CHECKED]` against `IMPLEMENTATION_ROADMAP.md` and `CURRENT_STATE.md`, cross-referenced this session against the specific code claims it makes (`compiler.py` gating, `planner.py`/`compiler.py` separation, `use_k42_frontend` default) — all confirmed true by direct read.

**What actually happened, reconstructed from git-verified project history (their own words, condensed and paraphrased, not quoted):**

The original 2026-vintage architecture document (`OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md` §19) planned seven milestones: K4.1 Intent+Goal, K4.2 Planner (decomposition only), **K4.3 Plan Compiler + Governance Gate**, K4.4 Reflection/Evaluation (read-only), K4.5 Memory Integration, K4.6 Supervisor, K4.7 full-pipeline integration.

**No commit ever used these seven labels.** Real development renamed everything to "K4.2.x" / "Packet 0N" from Packet 01 onward. Verified this session: `planner.py` never imports or calls anything from `compiler.py` — the separation the original K4.2/K4.3 split intended survived, just under different names. `compiler.py` gates on `action_type="plan_compile"` exactly as originally intended, even though the ADR that would have formally described this (`ADR-K4-04`) was never written — the engineering exists, only the paper trail is thinner than it should be. Five of the seven original milestones' *architectural substance* survived intact. The K4.4/K4.5 pair (read-only reflection, then a separate governed-writes milestone) collapsed into one packet, but this specific collapse turned out to be safety-equivalent: `UnifiedMemory.write()` was already governed (K3.5) by the time that packet was built, so the property the original sequencing was designed to guarantee held anyway.

**The C-MoE / K4.3 confusion, and how it was actually resolved (this matters for your §2 requirement directly):** On Aug 28, 2026, a governing prompt's premise that "K4.3 = C-MoE" was accepted into that day's documentation sync. This was wrong, and the project caught it itself the very next day — not silently: the Aug 29 entry is a struck-through, in-place correction (not a deletion), explicitly stating "K4.3" as a milestone label does not exist anywhere authoritative, and that the two C-MoE research documents produced under that mistaken premise were renamed to drop the "K4.3" label (their technical content was unaffected — only the claimed relationship to K4.2/K4.3 sequencing was wrong). This session independently reconfirmed: **zero code implementing any C-MoE concept exists anywhere in this repository.** C-MoE is unambiguously post-Kernel-freeze research. Per your §2 instruction: the current Kernel can be, and per the roadmap reconstruction above already substantially has been, completed without any C-MoE architecture. Nothing found this session requires it.

**One governance-process finding worth surfacing (§18.3 relevance):** the `use_k42_frontend=true` flip — which made the K4.2 Cognitive Front-End the default execution path — landed via, in the project's own words, "an unreviewed direct-to-`main` upload... authored outside the normal branch/PR workflow." This is exactly the kind of major architectural change §18.3 says should define its architectural/governance/rollback impact before merging. It happened to be safe (independently re-verified, zero regressions), but the process gap that let a default-execution-path change skip review is itself worth a line in a freeze-hygiene checklist, separate from whether this particular instance caused harm.

| Milestone | Original Intent | Current Meaning | Status |
|---|---|---|---|
| K4.1 | Intent + Goal formation | Unchanged in substance | ✅ Complete, live |
| K4.2 | Planner (decomposition only) | Planner + capability discovery + impasse handling, packetized as "K4.2.x" | ✅ Complete, live (see §6 for the one real gap found) |
| K4.3 | Plan Compiler + Governance Gate | Same substance, shipped as `compiler.py`, never called "K4.3" in any commit | ✅ Complete, live |
| K4.4 | Reflection/Evaluation (read-only) | Collapsed into the same packet as governed writes; safety-equivalent per above | ✅ Complete, live |
| — | — | (K4.5/K4.6/K4.7 labels: Memory Integration / Supervisor / full-pipeline integration — substance also shipped, packet-named differently) | ✅ Complete, live |
| "K4.3 = C-MoE" | — | **Never a real milestone.** Self-corrected Aug 29, 2026. | 🚫 NOT APPLICABLE |
| C-MoE (as a concept) | Future cognitive-scaling architecture | Research-phase only, three dedicated study documents, zero code | ⏸️ POST-FREEZE, confirmed |

---

## 5. Requirements → Implementation → Test Traceability (selected — full matrix is a larger undertaking than this session's remaining budget allows; the rows below are the ones this session specifically traced end-to-end)

`[VERIFIED-FRESH]` for every row below — each link in each chain was read directly, not inferred.

| ID | Requirement | Contract | Implementation | Registered/Reachable | Integration | Tests/Evidence | Result | Freeze Status |
|---|---|---|---|---|---|---|---|---|
| T-01 | Stable operation identity, Goal→Workflow | `root_operation_id: str` | `intent.py:706`, `planner.py:1057,1534`, `compiler.py:259`, `definition.py:130` | Yes | Yes | Confirmed via direct read of all 4 hops | ✅ COMPLETE | Clear |
| T-02 | Stable attempt identity across retries | `attempt_id` on `WorkflowNodeState` | `runtime.py:67` (field), `:433` (set) | Yes | Yes | Not independently re-run this session; field presence confirmed | 🧪 UNDER-VERIFIED (field exists; behavior across a real retry not re-traced this session) | Likely clear |
| T-03 | `ExecutionContext`-only worker invocation (no `WorkerContext` bridge) | All 7 `AbstractCognitiveWorker` subclasses | `base.py:203`, confirmed no `to_worker_context()` call in `execution_runtime.py:190-191` | Yes | Yes | 45 test call sites still construct `WorkerContext` directly (test-only, not production) | ✅ COMPLETE (production); 🧹 LEGACY (tests, dead import in 5/6 worker files) | Clear |
| T-04 | Semantic description ≠ execution payload | `raw_request` / `description` / `semantic_description` fields | `intent.py:755-894` | Yes | Yes, consumed at `planner.py:452,616` | Not independently unit-tested this session; consumption confirmed by direct call-site read | ✅ COMPLETE | Clear |
| T-05 | Capability discovery is runtime-reachable, not just implemented | `discover_capabilities()` | `planner.py:1173` | Yes — `use_k42_frontend=true` in `config/settings.toml:14`, read by `main.py:398`, gated at `orchestrator.py:275` | Yes | Confirmed by tracing the full config→composition-root→orchestrator chain | ✅ COMPLETE | Clear |
| T-06 | Intent ontology write→read→consume loop | `ContentDomain.INTENT_ONTOLOGY` write; `load_known_categories()` read | `learning.py` (write), `intent.py:1044-1069` (read) | Yes — called at `orchestrator.py:294-299`, fed into `interpret_request()` | Yes | Loop traced end-to-end this session | ✅ COMPLETE | Clear |
| T-07 | Planner impasse → bounded recovery → terminal event | `OperationRecoveryBudget`; `cognitive.planner_impasse_terminal` | `orchestrator.py:346-390` | Yes, self-contained in Orchestrator's re-plan loop | Yes | `[DOCUMENTED-NOT-REVERIFIED]`: project's own D7 closeout states this was directly tested; not independently re-run this session | ✅ COMPLETE (design confirmed correct; test re-execution not repeated) | Clear |
| T-08 | Failed worker invocation → SupervisorWorker retry, budget-aware | `context.parameters["failed_worker_result"]` → `_attempt_retry()` | `supervisor.py:212-250` | **No** — zero production call sites populate `failed_worker_result` anywhere in the repository; only 2 test files set it | No | Unit-tested in isolation only (`test_supervisor_worker.py`) — tests exercise a code path production never reaches | ⚠️ INTEGRATION-BROKEN / 🧪 tested-but-unreachable (§38 false-completion) | **P1 — should be resolved before freeze or explicitly re-scoped** |
| T-09 | Node-level execution retry | `node.retry_policy` | `runtime.py:416-478` | Yes | Yes | `test_workflow_runtime.py::TestWorkflowRuntimeRetry` (3 tests) — passing in this session's fresh run | ✅ COMPLETE, but see T-08: this mechanism does not draw from the shared `OperationRecoveryBudget`, so two uncoordinated recovery authorities coexist | ⚠️ Works, but violates the single-recovery-budget invariant your own code comments assert |
| T-10 | Checkpoint/resume durability | `EventStream.create_checkpoint()`/`get_checkpoint()` | `event_stream.py` (method exists) | **No** — `WorkflowRuntime` never calls either method (`[VERIFIED-FRESH]`, zero hits) | No | DEBT-008: no dedicated test coverage for checkpoint/replay behavior at all | 🔴 MISSING | **DEBT-003 — P1, prerequisite now resolved, ready to implement** |
| T-11 | Single canonical execution-recovery signal | One `ExecutionWatchdog`/`ProgressMonitor` implementation | Two independent pairs exist: `watchdog.py`+`progress.py` (graph-aware) vs `execution_watchdog.py`+`progress_monitor.py` (model-router-facing) | Both reachable, from different call sites | Reconciled once (commit `7ca7f35`) for one specific contract bug, not unified | `[DOCUMENTED-NOT-REVERIFIED]` per DEBT-016 | ⚠️ INCORRECT (duplicated authority) | **DEBT-016 — the project's own Kernel Completion Study already classifies this as a Freeze Gate failure in its own right** |
| T-12 | Context-poisoning resistance in intent interpretation | "Request:" section structurally distinguishable from retrieved context | `intent.py` prompt assembly | Exists but does not satisfy the invariant | Reachable | `tests/core/cognitive/test_intent_security.py` — **FAILING**, by design (tracked red, `CTX-AUTH-001`) | ⚠️ INCORRECT | **P0/P1 — see §15** |
| T-13 | Conversation-context scoping to caller | Per-caller isolation of recent-conversation retrieval | Not yet enforced | Reachable | `tests/test_context_scope_security.py` — **FAILING**, tracked red, `CTX-SCOPE-001` | ⚠️ INCORRECT | **P0/P1 — see §15** |
| T-14 | Prompt-cache key collision resistance | Cache key must differ when compressed-middle content differs | Not yet enforced | Reachable | `tests/test_prompt_cache_security.py` — **FAILING**, tracked red, `CTX-CACHE-001` | ⚠️ INCORRECT | **P1 — see §15** |
| T-15 | Deletion integrity | `UnifiedMemory.delete()` must return `False` if authoritative L1 storage deletion fails | Currently always returns `True` (logs and swallows the exception) | Reachable | `tests/test_unified_memory.py::TestUnifiedMemoryDelete` — **FAILING**, tracked red, `CTX-DELETE-001` | ⚠️ INCORRECT — false success on data deletion | **P0 — see §15** |
| T-16 | API authentication | No formal contract found requiring one | None present | N/A | N/A | None | 🔴 MISSING (or NOT APPLICABLE if deliberately out of Kernel scope for a local-first tool — your call) | See §15 |


---

## 6. K4.2 Detailed Gap Analysis

`[VERIFIED-FRESH]` — this session independently re-verified all five structural concerns your governing prompt named, rather than assuming prior closure claims.

**A. Semantic Description vs. Execution Payload — ✅ RESOLVED.** `intent.py` maintains a clean three-way split: `raw_request` (original text, execution payload), `description` (back-compat alias of `raw_request`), `semantic_description` (a distinct field combining the classification hypothesis label with the request, purpose-built for capability matching). Confirmed consumed, not orphaned, at `planner.py:452` and `:616`.

**B. Capability Discovery — ✅ RESOLVED, runtime-reachable.** `discover_capabilities()` exists (`planner.py:1173`), is called from within the live `plan()` pipeline, and that pipeline is reached from `Orchestrator.handle()` whenever `use_k42_frontend` is true — which it is, by default, in the shipped `config/settings.toml`. Full chain traced: `settings.toml:14` → `main.py:398,407` → `orchestrator.py:275`.

**C. Planner Impasse — ✅ Correctly architected, not a gap, but distinct from Supervisor coverage (see E below).** Impasse detection, bounded retry via a shared `OperationRecoveryBudget`, and a terminal event (`cognitive.planner_impasse_terminal`) all live inside the Orchestrator's own re-plan loop (`orchestrator.py:346-390`) — a deliberate design choice (D7) to keep impasse recovery separate from `SupervisorWorker`, which handles a different failure class (compilation rejection). This separation is legitimate architecture, not an oversight, as long as both paths genuinely terminate rather than loop or hang — the budget-exhaustion path was confirmed to exist; this session did not re-execute the specific regression test proving it under load.

**D. Intent Ontology — ✅ RESOLVED, closed loop.** Write (`ContentDomain.INTENT_ONTOLOGY` via `ValidationGate`), read (`load_known_categories()`, `intent.py:1044-1069`), and consumption (`orchestrator.py:294-299`, feeding `interpret_request()`) were all traced directly. Information written is genuinely read back and used, not merely persisted.

**E. Supervisor Coverage — ⚠️ REAL GAP.** This is the one item in the original five where fresh verification contradicts the apparent completion story. `SupervisorWorker` is invoked from exactly one production call site (`orchestrator.py:436`), for compilation `REJECT`/`ESCALATE` only. Its second documented capability — retrying a failed worker invocation via `context.parameters["failed_worker_result"]` — has **no production call site anywhere in the repository**. A repo-wide grep for the string `"failed_worker_result"` returns exactly four files: two tests that construct it directly to exercise `_attempt_retry()` in isolation, `supervisor.py` itself (where it's read), and a comment in `orchestrator.py` explicitly noting this call site does *not* set it. This means: a worker that throws mid-execution inside the live K4.2 pipeline is caught by `WorkflowRuntime`'s own local `retry_policy` mechanism (§11 below), never by `SupervisorWorker`. `SupervisorWorker`'s retry capability, as currently wired, is real code with real tests that cannot be exercised by any actual request the system serves.

**K4.2 Completion Matrix**

| Sub-area | Status | Evidence |
|---|---|---|
| Description/payload separation | ✅ COMPLETE | `intent.py:755-894`, consumed at `planner.py:452,616` |
| Capability discovery, runtime-reachable | ✅ COMPLETE | `settings.toml:14` → `main.py:398` → `orchestrator.py:275` → `planner.py:1173` |
| Planner impasse detection + bounded recovery | ✅ COMPLETE | `orchestrator.py:346-390` |
| Intent ontology, closed write/read loop | ✅ COMPLETE | `learning.py` → `intent.py:1044-1069` → `orchestrator.py:294-299` |
| Supervisor coverage — compilation failures | ✅ COMPLETE | `orchestrator.py:405-445` |
| Supervisor coverage — worker execution failures | 🔴 MISSING (implemented, unreachable) | `supervisor.py:212-250`, zero live callers |
| Shared recovery budget across all recovery paths | ⚠️ INCORRECT — two uncoordinated mechanisms | `orchestrator.py`'s `OperationRecoveryBudget` vs. `runtime.py`'s local `retry_policy` |

**K4.2 Closure Checklist (objective, per §50):**
1. Either (a) wire a real call site that populates `failed_worker_result` when a node's local `retry_policy` is exhausted, so `SupervisorWorker` gets a genuine escalation opportunity before a workflow gives up, or (b) formally deprecate `_attempt_retry()` and its tests, documenting that node-local `retry_policy` is the sole, intentional execution-retry mechanism. Either is acceptable; leaving both to coexist silently is not.
2. If (a) is chosen: `WorkflowRuntime`'s node retry loop must consume from the same `OperationRecoveryBudget` the planner re-plan loop uses, or explicitly document why node-level and plan-level recovery are allowed separate budgets.
3. A new integration test must exercise a real worker exception propagating through the live K4.2 path end-to-end (not a mock of `SupervisorWorker` in isolation) and assert which mechanism actually handles it.

---

## 7. K4.3 Detailed Gap Analysis (repository-defined K4.3 only)

`[VERIFIED-CROSS-CHECKED]`, per §4 above.

1. **What is K4.3?** Per the original architecture document, "Plan Compiler + Governance Gate." No commit ever used the label; the substance shipped as `compiler.py`.
2. **What problem does it solve?** Validating and compiling a planner-produced plan into an executable `WorkflowDefinition`, gated by governance before execution can begin.
3. **Required components:** a compiler (`compiler.py`), a governance gate check (`action_type="plan_compile"` evaluated by `GovernanceKernel`), and REJECT/ESCALATE handling.
4. **Acceptance criteria (reconstructed, not formally documented under this label anywhere):** a plan reaches the compiler; the compiler evaluates it against governance before producing a `WorkflowDefinition`; rejection/escalation routes to `SupervisorWorker`.
5. **Complete:** compiler exists, governance gate is real (confirmed `action_type="plan_compile"` is actually evaluated, not decorative), REJECT/ESCALATE routes to `SupervisorWorker` (§6/§11.E — this specific path is the one that *does* work).
6. **Partial:** none found specific to this milestone's own scope.
7. **Missing:** a formal ADR (`ADR-K4-04`) was never written — a documentation-hygiene gap, not a functional one.
8. **Incorrectly implemented:** none found specific to compilation itself; the Supervisor-reachability gap (§6.E) is adjacent (Supervisor consumes compiler output correctly) but not a K4.3 defect per se.
9. **What depends on unfinished K4.2:** nothing — K4.2's one real gap (Supervisor worker-retry reachability) is downstream of K4.3, not a K4.3 dependency.
10. **What blocks Kernel v1.0:** nothing new found in this milestone specifically; it inherits the K4.2 Supervisor-reachability concern as a shared consumer, not as its own defect.

**Explicit statement per your §12 requirement:** no part of what this repository actually calls (or should call) K4.3 is C-MoE work. The "K4.3 = C-MoE" premise was a one-day documentation error, self-corrected the next day, independently reconfirmed absent from the codebase this session.

---

## 8. K4.4 Freeze Relevance

`[DOCUMENTED-NOT-REVERIFIED]` for the milestone-substance claim (collapsed into the same packet as K4.2/K4.3 work, per §4); `[VERIFIED-FRESH]` for the execution-reliability items below, which is what "K4.4" concretely refers to in this project's own more recent usage (the watchdog/execution-budget merge, Aug 27, 2026).

| Item | Classification | Reason |
|---|---|---|
| Reflection/Evaluation read path (original K4.4 substance) | REQUIRED FOR KERNEL — already satisfied | Collapsed into the governed-writes packet; safety property held anyway (§4) |
| ExecutionWatchdog/ProgressMonitor (single canonical implementation) | **REQUIRED FOR KERNEL** | DEBT-016; the project's own Kernel Completion Study already classifies this as freeze-gate-failing, not merely nice-to-have |
| Checkpoint/resume (DEBT-003) | **REQUIRED FOR KERNEL** | Same study's own reclassification (Aug 29): Kernel v1.0 "cannot honestly claim durability" without it |
| Operation/ExecutionAttempt/ExecutionSnapshot architecture (DEBT-015) | POST-FREEZE | Explicitly and correctly reclassified as proposed-only future architecture on Aug 29, after a one-day mistaken "K4.3 Packet 0" classification was corrected |
| Richer execution-inspection UI beyond what's merged | POST-FREEZE | DEBT-015 sub-item, explicitly deferred |
| Stale-attempt rejection, idempotency semantics for future side-effecting capabilities | POST-FREEZE | DEBT-015 sub-items; no current capability needs them yet |

Not all of K4.4 is required before freeze — this table deliberately does not wave through the whole "K4.4" label; DEBT-015's twelve sub-items are correctly kept out of scope while DEBT-003/DEBT-016 are correctly kept in.

---

## 9. Architectural Invariants

`[VERIFIED-FRESH]` for the specific violation found; the rest of the register reflects invariants your instructions name explicitly, checked to the depth this session's tool budget allowed — several rows are honestly marked as needing deeper, dedicated investigation.

| ID | Invariant | Where Enforced | Violation Found? | Freeze Status |
|---|---|---|---|---|
| INV-01 | Single shared recovery budget across all recovery paths | Intended via `OperationRecoveryBudget` | **Yes** — `WorkflowRuntime`'s node-local `retry_policy` retries do not draw from it | ⚠️ Violation — P1, see §6/§11 |
| INV-02 | No worker bypasses governance | `GovernanceKernel.evaluate_action()` called from `intent.py`/`planner.py`, and (per DEBT-014) also correctly from `learning.py`'s `ValidationGate`, though the drift-check tooling (`DRIFT-10`) doesn't know to check that file | No bypass found; the *checker's* coverage is narrower than the boundary it protects (DEBT-014) | Not a current violation, but a detection gap |
| INV-03 | Execution-instance isolation (Task A cannot mutate Task B) | Not specifically re-traced this session beyond the one global found (`ADAPTIVE_LLM_LIMIT`, an intentional shared concurrency limiter, not a correctness hazard) | `[NOT COMPLETED THIS PASS]` — a full cross-execution contamination trace (shared caches, ambient context, ID reuse) was not performed | Needs dedicated pass before freeze sign-off |
| INV-04 | Worker lifecycle integrity (no orphaned/immortal workers) | `[NOT COMPLETED THIS PASS]` | — | Needs dedicated pass |
| INV-05 | Deletion means deletion | `UnifiedMemory.delete()` | **Yes** — returns `True` even when L1 storage deletion actually raised | 🔴 P0, see §15 |
| INV-06 | Contract integrity (producer/consumer agreement) | Spot-checked for `description`/`semantic_description` (holds) and `failed_worker_result` (does not — producer side doesn't exist) | Mixed | See §6.E |
| INV-07 | Deterministic control flow, no hidden hostile nondeterminism | `[NOT COMPLETED THIS PASS]` beyond the module-global scan in §2 (no problematic globals found in `core/`, non-exhaustive) | — | Needs dedicated pass |
| INV-08 | Configuration integrity (no silent global mutation) | `PUT /config` restricted to a 5-key allowlist, confirmed | No violation found in the mutation surface itself | Clear, but see §15 for the authentication gap around it |

---

## 10. Boundary / Bypass Analysis

`[VERIFIED-FRESH]` for the bypasses found; `[NOT COMPLETED THIS PASS]` for a full systematic walk of every boundary in your §17 example pipeline — this session traced the boundaries that came up naturally during the K4.2/Supervisor work and did not separately walk planner→capability-discovery or recovery→state-transition boundaries beyond what's already covered above.

- **Execution bypassing Supervisor-mediated governance-of-recovery:** confirmed (§6.E) — `WorkflowRuntime`'s node-level retry executes without any Supervisor/budget check. This is a real bypass of the *intended* single-recovery-authority invariant, even though it is not a bypass of `GovernanceKernel` itself.
- **API bypassing authentication (not validation — input validation via `MUTABLE_CONFIG_KEYS` does hold):** confirmed (§15) — no auth layer exists to bypass in the first place, which is a different and arguably more fundamental gap than a bypass of an existing control.
- **Legacy path (K2.2 `PlannerWorker`) bypassing K4.2 controls:** not a bypass — it's a deliberately separate, mutually-exclusive branch (`if use_k42_frontend and workflow_runtime`), not a path that runs *alongside* K4.2 and could accidentally win a race. Confirmed by reading the branch condition directly.

---

## 11. State / Event / Workflow Analysis

`[VERIFIED-FRESH]` for what's below; full state-transition diagrams for every Kernel state machine were **not** produced this session — that is a substantial standalone exercise this audit's remaining budget did not allow (`[NOT COMPLETED THIS PASS]`).

- **Node execution retry state machine:** `WorkflowRuntime._execute_node_with_retry()` (`runtime.py:416-478`) implements backoff, `retryable_errors` filtering, and `max_retries` against `node.retry_policy`. Confirmed reachable and covered by `tests/test_workflow_runtime.py::TestWorkflowRuntimeRetry` (3 tests, all passing in this session's fresh run).
- **Checkpoint/replay:** `EventStream.create_checkpoint()`/`get_checkpoint()` exist as methods but are **never called** by `WorkflowRuntime` — confirmed by direct grep returning zero hits in `runtime.py`. This means the "restart mid-workflow" state transition has no implemented recovery path at all today: a process restart during a long-running workflow does not resume, checkpoint or not — there is simply nothing to resume from. This is DEBT-003, and per §7's traceability, its identity prerequisite is now satisfied, making it the most "shovel-ready" open item in the entire register.
- **Duplicate event handling / idempotency of the event backbone itself:** `[NOT COMPLETED THIS PASS]` — DEBT-008 already documents that `EventStream` has no dedicated test coverage of its own `append()`/`replay()`/checkpoint behavior; this session did not independently write or run such a test, and recommends doing so as part of implementing DEBT-003 (you'd need this test infrastructure to validate the checkpoint work anyway — sequencing this together avoids rework, per your own §49 "no rework principle").

---

## 12. Execution / Worker / Watchdog Analysis

`[VERIFIED-FRESH]` for the duplication confirmation; `[DOCUMENTED-NOT-REVERIFIED]` for the specific historical bug the reconciliation commit fixed.

- **Two independent watchdog/progress-monitor pairs confirmed still present:** `core/runtime/watchdog.py` + `progress.py` (graph-aware, used by `WorkflowRuntime` and the execution-inspection UI) vs. `core/runtime/execution_watchdog.py` + `progress_monitor.py` (standalone, used by `model_router.py`'s long-form generation path). Both name their primary class `ExecutionWatchdog` and `ProgressMonitor` identically — confirmed via `ls core/runtime/*watchdog* core/runtime/*progress*` returning all four files.
- This directly matters for your §14/§15 questions about distinguishing slow-but-progressing execution from genuine stalls: **there are two separate, potentially divergent answers to "is this execution stalled?" depending on which code path a given request takes.** A caller written against one implementation's contract can silently point at the other (this is exactly the incident DEBT-015 was originally motivated by, and DEBT-016 is its second confirmed instance of the same "duplicated authority" pattern, alongside `EventStream`/`KnowledgeEvent` in §4/DEBT-004).
- Watchdog Failure Scenarios 1–10 (your §15): `[NOT COMPLETED THIS PASS]` as an exhaustive per-scenario trace through both implementations. Given the duplication itself is already a confirmed, named debt item with its own remediation plan pending, tracing all ten scenarios through *both* watchdog implementations before they're unified would very likely be work that gets partially discarded once DEBT-016 is resolved — recommend doing the ten-scenario trace **after** unification, per your own §49 no-rework principle, rather than before.

---

## 13. Concurrency / Isolation / Resource Analysis

`[VERIFIED-FRESH]` for the specific scan performed; broader concurrency/race auditing is `[NOT COMPLETED THIS PASS]`.

- Module-level mutable global scan across `core/`: one intentional global found (`ADAPTIVE_LLM_LIMIT`, `limits.py:11`, a shared `AdaptiveSemaphore` bounding total concurrent LLM calls process-wide — architecturally correct as a genuine cross-request resource limiter, not a correctness hazard). No other module-level mutable dict/list singletons found by the pattern searched (non-exhaustive — this was a grep-based scan, not an AST-level analysis, so it should not be read as a proof of absence).
- `AdaptiveSemaphore` itself was independently re-verified this session as a real, non-no-op implementation with correct lock-guarded shrink/grow semantics and two explicit historical bug-fix comments in its own source, addressing the specific "no-op behavior" finding from your list in §32 of the governing prompt. **RESOLVED**, confirmed by direct code read.
- Two competing memory-related classes were noted (`core/context.py`'s `ContextMemory` vs. `core/memory/unified_memory.py`'s `UnifiedMemory`) but their exact relationship — legitimate separation of concerns (short-term working context vs. full L0-L4 layered memory) vs. genuine unreconciled duplication — was not traced to a conclusion this session. `[NOT COMPLETED THIS PASS]`, flagged for §14/§28 follow-up.
- Race-condition audit against your specific §25 scenario list (two workflows concurrently, worker completion vs. watchdog, retry vs. original attempt, etc.): `[NOT COMPLETED THIS PASS]`. This is a substantial dedicated exercise, and given the watchdog duplication (§12) is already a known, named blocker, the highest-value version of this audit happens after that duplication is resolved — auditing races across two implementations that are about to be merged risks documenting races that disappear (or change shape) once DEBT-016 closes.
- Resource-leak audit (processes/threads/file handles/DB connections): `[NOT COMPLETED THIS PASS]`.

---

## 14. Memory / Persistence / Configuration Analysis

`[VERIFIED-FRESH]` for the deletion-integrity finding, which is the most significant item in this section.

- **`UnifiedMemory.delete()` returns `True` even when the authoritative L1 storage deletion actually failed.** This is not a hypothesis — it is the exact, currently-failing assertion in `tests/test_unified_memory.py::TestUnifiedMemoryDelete::test_delete_returns_false_when_l1_storage_deletion_fails`, run fresh this session. The test's own docstring cites `docs/research/context-engineering/revocation-deletion-retention-audit.md` and explicitly instructs future readers not to weaken or remove the assertion. Current behavior: the code catches the L1 deletion exception, logs it, and falls through to an unconditional `return True`. **Practical consequence: any caller that asks OCBrain to delete something and receives a success response cannot actually trust that the data is gone.** For a local-first cognitive system whose memory architecture explicitly claims provenance and lifecycle guarantees (§8 of your governing project instructions — "no memory without provenance"), a silent-failure-reported-as-success on deletion is a correctness violation, not a hardening nicety. Recommend **P0**.
- Config mutation surface (`PUT /config`): restricted to 5 keys (`ollama_host`, `debug`, `log_level`, `web_ui_port`, `auto_update`) via `MUTABLE_CONFIG_KEYS` — confirmed narrow, no arbitrary-key mutation possible through this endpoint.
- `models.toml`/`settings.toml`/`sources.toml` synchronous-rewrite issue (historical A6 finding): confirmed fixed — `config.py` now defers non-critical writes via a dirty-flag/`flush()` pattern, only a small critical-key set persists immediately. **RESOLVED**, confirmed by direct code read of the "A6 audit fix" block.
- DEBT-010 (config watcher thread racing against `CONFIG_DIR` patching during tests) and DEBT-012 (full-suite runs rewriting real config files, including a real content-loss incident against `settings.toml`'s comments, not just line-ending noise) remain open per the project's own register; not independently re-run this session (`[DOCUMENTED-NOT-REVERIFIED]`).
- L2 semantic memory volatility (DEBT-006 — embeddings lost on restart, recomputed from persisted entries) remains open, Medium severity, not independently re-verified this session.

---

## 15. Governance / Security Analysis

`[VERIFIED-FRESH]` throughout this section — every named historical finding from your list was individually checked against current code, not assumed.

| Historical finding | Current status | Evidence |
|---|---|---|
| Fine-tuning safety gate incorrectly comparing a model to itself | 🧪 **Not reproducible in current code.** `learning/evaluator.py:14-56` genuinely compares new-local-weights vs. old-local-weights, both scored against a true external ground truth (`model_router._call_external()`, confirmed to resolve to a distinct cloud-provider mesh, not the module's own local model). I could not locate this specific finding's original source document in-repo to confirm it describes the same code path; recommend you confirm before formally closing it, since I'm reporting "not found as described in current code," not "confirmed fixed with a remediation trail." | `learning/evaluator.py`, `model_router.py:319-345` |
| Mocked web-learning LLM judge | ⚠️ **Still present, confirmed.** `learning/gap_detector.py:115-124`'s `_answer_quality()` — which directly gates what counts as a "knowledge gap" worth retraining on (line 84) — is `min(len(answer)/300, 1.0)`. A pure length heuristic with zero semantic assessment and no LLM call, despite functioning as the module's de facto quality judge. | `learning/gap_detector.py:84,115-124` |
| AdaptiveSemaphore no-op behavior | ✅ **Fixed, confirmed.** Real AIMD-style shrink/grow under a lock, two explicit `# BUG FIX` comments addressing exactly this class of historical defect, wired to a real call site (`limits.py:47`). | `core/runtime/resilience.py:55-127` |
| `models.toml` synchronous rewrite on every query | ✅ **Fixed, confirmed** ("A6 audit fix" in code). | `core/config.py:184-210` |
| `_open_app()` sandbox bypass | ✅ **Fixed, confirmed** ("A7 audit fix" — shell removed, character allowlist, `os.startfile()` on Windows). | `modules/system_ctrl/module.py:50-95` |
| Unauthenticated `PUT /config` | ⚠️ **Still true, with real but partial mitigation.** No `Depends(auth)`, API key, or token check exists anywhere in `interface/api.py` — confirmed by exhaustive pattern search. Mitigated by: (1) server binds `127.0.0.1` only, not `0.0.0.0`; (2) `MUTABLE_CONFIG_KEYS` limits the blast radius of this specific endpoint to 5 low/medium-risk settings; (3) `CSRFHeaderMiddleware` requires a custom `X-OCBrain-Local` header on every mutating request, which specifically blocks the *browser* cross-origin attack vector (browsers cannot add arbitrary headers cross-origin without a preflight that would fail here). **What remains unmitigated: any other local process on the same machine — not just a browser tab — can call every endpoint, including `/query` (task submission) and `PUT /config`, with no identity check whatsoever.** Whether that's acceptable depends entirely on your threat model for a local-first tool (is "another process on this machine" inside or outside the trust boundary?) — this audit surfaces the fact, the severity call is yours. | `interface/api.py` (full file scanned for auth patterns — none found), `main.py:453` |
| Unauthenticated `interface/api.py` generally | Same as above — it's one finding, not two; confirmed the CSRF middleware applies uniformly to all mutating routes, so the same partial-mitigation picture applies system-wide, not just to `/config`. | `interface/api.py:40-68` |

**New findings this section surfaced, not on your original historical list — the four `CTX-*` tracked-red security invariants, discovered via this session's fresh full-suite run:**

This repository has an explicit, disciplined policy of never using `xfail` for known-but-unfixed issues — they are left genuinely red on purpose, so the pass/fail count always reflects true status rather than being inflated (confirmed via each test file's own header comment, e.g. `test_intent_security.py:12-13`: *"do not mark them xfail (this repository has no xfail convention); known failures are tracked and left genuinely red."*). This is a disciplined practice worth explicitly commending — but it means a nonzero failure count in this suite is partly by design, and a closure audit must read *which* failures those are rather than treating the aggregate number as pass/fail.

Reconciliation of this session's fresh run (1,350 passed / 39 failed) against the last documented baseline (Aug 31: 1,347 passed / 36 failed — 34 `huggingface.co`-network environment failures + 2 `CTX-AUTH-001` tests): **34 (environment, confirmed identical class via per-failure traceback inspection) + 5 tracked-red security tests = 39.** Two of those five (`CTX-AUTH-001` ×2) were already known as of Aug 31. **Three are new since the last sync and are not yet in any of your documentation:**

1. **`CTX-AUTH-001`** (`test_intent_security.py`, 2 tests) — already documented. Retrieved/poisoned context can inject a second "Request:" section into the LLM prompt, structurally indistinguishable from the genuine one — a prompt-injection / context-poisoning vulnerability in the intent-interpretation pipeline. Directly relevant to the OWASP Agentic AI "Goal Hijacking" risk category flagged in the prior research session.
2. **`CTX-SCOPE-001`** (`test_context_scope_security.py`) — **not yet documented anywhere.** Recent-conversation context retrieval is not scoped to the calling user/session — a cross-caller memory-leakage risk.
3. **`CTX-CACHE-001`** (`test_prompt_cache_security.py`) — **not yet documented anywhere.** Prompts differing only in compressed-middle content do not produce distinct cache keys, risking cache collision (one caller's cached response served to another, or stale content served incorrectly).
4. **`CTX-DELETE-001`** (`test_unified_memory.py`) — **not yet documented anywhere**, and the most serious of the four. Covered in full in §14 above: `delete()` reports success when the underlying deletion actually failed.

All four are currently unfixed. All four are testable, evidenced, and reproducible — I ran the suite and watched them fail with the exact assertions above. Recommend all four be added to `KNOWN_ISSUES.md`'s Active Technical Debt table immediately (regardless of this audit's broader disposition), since they are currently invisible to anyone reading only the documentation rather than running the suite.

---

## 16. Legacy / Migration / Cleanup Analysis

`[VERIFIED-FRESH]` for the items checked.

| Component | Why Legacy | Still Referenced? | Runtime Reachable? | Replacement | Safe to Remove? | Cleanup Needed |
|---|---|---|---|---|---|---|
| `WorkerContext` class | Superseded by `ExecutionContext` (ADR-KERNEL-01) | Yes — imported in all 7 worker files, but unused beyond the import in 5/6 | No (production); Yes (45 test call sites) | `ExecutionContext` | Not yet — 45 tests depend on it | Migrate those 45 test constructions to `ExecutionContext`, then delete both the class and the now-genuinely-unused imports |
| K2.2 `PlannerWorker` direct-invocation path | Predates K4.2 Cognitive Front-End | Yes, as the intentional fallback branch | Yes, when `use_k42_frontend=false` or `workflow_runtime is None` | K4.2 pipeline | **No — this is a deliberate, documented fallback, not accidental duplication.** Do not remove without a separate decision to drop K2.2 support entirely. | None — correctly labeled "legacy/compatibility only" in your own docs |
| `SupervisorWorker._attempt_retry()` | Not legacy in the sense of superseded — it's *unreached*, which is a different problem (§6.E) | Yes, in 2 test files | No, in production | N/A — this is the thing that needs a decision, not a replacement | N/A | Decide: wire it in for real, or formally retire it and its tests |
| Two watchdog/progress-monitor implementations | Independently built, never reconciled | Both, from different call sites | Both | Should converge to one | No — both are live | DEBT-016's own remediation, already scoped |

No migration/compatibility footprint concerns were found for the `WorkerContext` cleanup specifically — it holds no persisted state of its own (it's a runtime parameter-passing object, not a schema stored anywhere), so deleting it once tests are migrated carries no data-migration risk. This was not independently re-verified for the watchdog duplication or for `ContextMemory`/`UnifiedMemory` (§13) — `[NOT COMPLETED THIS PASS]`.

---

## 17. False-Completion / Negative-Space Analysis

This is the section this session's investigation produced the most direct value for — the following all "look complete" by a docstring/architecture-doc reading and are not, confirmed by tracing actual reachability rather than reading claims:

- **`SupervisorWorker._attempt_retry()`** — real code, real unit tests, zero production reachability (§6.E, §11).
- **`learning/gap_detector.py`'s `_answer_quality()`** — named and used as a quality signal; is actually a length heuristic (§15).
- **`EventStream.create_checkpoint()`/`get_checkpoint()`** — real methods, zero callers (§11, DEBT-003).
- **`UnifiedMemory.delete()`** — returns a success value that does not mean what its own docstring says it means (§14).
- **The `v1.0.0` git tag** — exists, but does not mean "the Kernel was frozen" (§2).

**Negative-space (things the Kernel currently *can* do that it should not be able to):**
- Any local process can mutate 5 configuration keys, and call any other endpoint including task submission, without any identity check (§15).
- A caller can receive `delete() == True` and have their data still present (§14/§15, `CTX-DELETE-001`).
- Retrieved/external context can, per `CTX-AUTH-001`, produce a prompt structurally indistinguishable from a legitimate second user request.

---

## 18. Testing / Historical Regression Analysis

`[VERIFIED-FRESH]` — full suite run this session, 1,389 tests collected, 1,350 passed / 39 failed in 72 seconds (`python3 -m pytest -q`, clean install from `requirements.txt`, network restricted to the sandbox's allowed domains — notably excluding `huggingface.co`).

**Historical Failure Regression Matrix (the items this session specifically re-checked):**

| Failure | Original Symptom | Root Cause | Fix | Current Code | Regression Test | Current Status |
|---|---|---|---|---|---|---|
| AdaptiveSemaphore no-op | Concurrency limiter didn't actually limit | Missing acquire-state tracking, guard ordering bug | Two explicit bug-fix commits, inline comments | `resilience.py:55-127` | Not independently re-run this session as an isolated unit test; behavior read directly from source | ✅ Fixed |
| A6 — `models.toml` sync rewrite | Synchronous file write on every query | No dirty-flag/deferred-write mechanism | Dirty-flag + `flush()`, critical-key exception list | `config.py:184-210` | `tests/test_audit_fixes.py::TestA6ConfigWrites` — ran clean in this session's full suite | ✅ Fixed |
| A7 — `_open_app()` sandbox bypass | Shell-based subprocess invocation, injectable | Shell removed, character allowlist added | `_validate_open_target()`, `os.startfile()` on Windows | `modules/system_ctrl/module.py:50-95` | `tests/test_audit_fixes.py::TestA7SystemController` — 3 related tests failed in this session's run, but on `OSError` (huggingface cascade), not the original vulnerability's assertion — confirmed environment artifact, not regression | ✅ Fixed (test failures are unrelated network artifacts) |
| ClarificationPolicy over-escalation | Near-zero Jaccard similarity for realistic phrasing tripped a 0.5 threshold universally | `_is_general_purpose_only()` exemption added | `ADR_K4_2_H_13...` | Not independently re-run this session | 🧪 Not re-verified this session, documented as fixed |
| Watchdog contract mismatch (the DEBT-015/016 motivating incident) | Edit-style requests crashed on two independent `ExecutionBudget` contracts | Commit `7ca7f35` pointed the graph-aware pair at the correct contract | Partial — the two implementations still coexist | See §12/DEBT-016 | Not independently re-run this session | ⚠️ Partially fixed (the specific crash, yes; the underlying duplication, no) |
| **The watchdog timeout problem** (explicitly required by your §40) | `[NOT COMPLETED THIS PASS]` — I could not locate a document in this repository specifically titled or describing "the watchdog timeout problem" as a named historical incident distinct from the contract-mismatch bug above. If you have a specific incident in mind, point me to it and I'll trace it directly rather than guess. | | | | | |

**Test suite classification (this session's fresh run):**
- 1,350 passing — the overwhelming majority genuinely exercise real behavior (spot-checked several: `test_workflow_runtime.py`'s retry tests construct real `WorkflowRuntime` instances and real retryable exceptions, not pure mocks).
- 34 failing — confirmed, by direct traceback inspection, all attributable to `sentence-transformers`/`huggingface.co` model download requiring internet access this sandbox does not have. **Environment artifact, not a code defect** — but see §19, since this same limitation would affect anyone else's clean-room attempt too, and it is currently undocumented how to run this suite fully offline.
- 5 failing — deliberately red, tracking 4 distinct unfixed security/correctness invariants (§15).
- 0 failing — of the remainder; this session found no failures outside these two buckets.

This is a materially cleaner picture than "39 failures" sounds in isolation, but it is not a clean bill of health either — the 5 deliberately-red tests exist precisely because the underlying issues are real and unfixed, not because the tests are wrong.

---

## 19. Clean-Room / Reproducibility Analysis

`[VERIFIED-FRESH]` — this session performed an actual clean-room attempt, not a description of one.

- Fresh `git clone` → `pip3 install -r requirements.txt --break-system-packages` succeeded (after resolving a disk-space constraint specific to this sandbox, not the project — 21 dependencies, install completed without error once space was available).
- `python3 -m pytest --collect-only` → 1,389 tests collected cleanly, no collection errors.
- Full suite executed to completion in 72 seconds, no hangs, no crashes — this is a meaningfully positive signal: the suite is well-behaved even when the 34 network-dependent tests fail, rather than hanging waiting for a timeout.
- **Gap found:** nothing in the repository documents that `huggingface.co` access is expected/required for a subset of tests, or how to run the suite in a genuinely offline-friendly mode (e.g., a documented `HF_HUB_OFFLINE=1` environment variable, a bundled small model, or a marker to skip embedding-dependent tests). Anyone else attempting a clean-room validation in a network-restricted environment will rediscover these same 34 failures from scratch and have to independently conclude they're environment artifacts, exactly as this session did. Recommend documenting this explicitly (a line in `README.md` or a `pytest.ini` marker) as a freeze-hygiene item (§53).
- Startup/shutdown sequence itself: `[NOT COMPLETED THIS PASS]` — this session did not attempt to actually start the `main.py` process end-to-end (would require an Ollama instance or equivalent, not available in this sandbox, and starting a long-lived server process wasn't a good fit for this audit's remaining tool budget).

---

## 20. Debt Register

Consolidating this project's own `KNOWN_ISSUES.md` (rows verified to still be open by targeted spot-check this session where noted) with this session's own new findings.

| ID | Finding | Severity | Freeze Impact | Required Action | Disposition |
|---|---|---|---|---|---|
| NEW-1 | `SupervisorWorker` worker-retry path unreachable in production | P1 | Blocks confident freeze claim on execution-failure recovery | Wire a real call site or formally retire the mechanism (§6) | **P1 — MAJOR** |
| NEW-2 | `CTX-DELETE-001`: `delete()` reports success on silent L1 failure | P0 | Data-integrity/compliance-adjacent correctness violation | Fix `UnifiedMemory.delete()` to propagate the failure | **P0 — FREEZE BLOCKER** |
| NEW-3 | `CTX-AUTH-001`: context-injection can forge a second "Request:" section | P0/P1 | Prompt-injection vector into the Cognitive Front-End | Structurally separate context from request in the prompt template | **P0 — FREEZE BLOCKER** (governance/security, Law 1) |
| NEW-4 | `CTX-SCOPE-001`: conversation context not scoped to caller | P1 | Cross-caller memory leakage | Add caller-scoping to recent-conversation retrieval | **P1 — MAJOR** |
| NEW-5 | `CTX-CACHE-001`: prompt cache key collision on compressed-middle variation | P1/P2 | Wrong or leaked cached responses | Include full prompt content (or a stronger hash) in the cache key | **P1 — MAJOR** |
| NEW-6 | `interface/api.py` has no authentication anywhere | P1 (threat-model-dependent) | Any local process can submit tasks / mutate config unchallenged | Decision required: is this in-scope for local-first Kernel v1.0, or explicitly deferred? | **P1 — MAJOR, pending your threat-model decision** |
| NEW-7 | Stale `v1.0.0` git tag, 96 commits behind `main` | P2 | Release-hygiene / confusion risk, not functional | Delete or clearly annotate before any real freeze tag is cut | **P2 — MODERATE** |
| NEW-8 | `learning/gap_detector.py`'s quality "judge" is a length heuristic | P2 | Learning-pipeline gap-detection quality is weaker than it appears | Replace with a real quality signal, or rename/document as a heuristic explicitly | **P2 — MODERATE** (not a Kernel-path item; scoped to the learning subsystem) |
| DEBT-003 | Checkpoint/resume not implemented | Medium (project's own label); this audit concurs it's now unblocked and ready | **Kernel-completion blocker per the project's own Kernel Completion Study** | Implement against `root_operation_id`/`attempt_id`, now that the identity prerequisite exists | **P1 — MAJOR, highest-readiness item in the register** |
| DEBT-016 | Two independent watchdog/progress-monitor implementations | Medium (project's own label); this audit concurs with the project's own reclassification | **Kernel Freeze Gate failure in its own right**, per the project's own study | Unify into one canonical implementation | **P1 — MAJOR** |
| DEBT-002 | AgentGovernor delegation dormancy | Medium | Not currently exploitable (nothing delegates) | Populate `delegating_worker_type` when `SupervisorWorker` delegates, or formally defer | P2 — MODERATE |
| DEBT-004/005 | Event mechanism triality (KnowledgeEvent/EventStream/EventBus) | Low | No single unified audit trail | Future consolidation | **P3 — POST-FREEZE** (project's own correct classification) |
| DEBT-006 | L2 embeddings volatile across restart | Medium | Startup cost scales with entry count; not a correctness issue | Persist embeddings | P2 — MODERATE |
| DEBT-007 | Budget governor logic correct but nothing feeds it real numbers | Medium | Step/token budgets not actually enforced despite correct evaluation logic | Wire real accumulation | P2 — MODERATE |
| DEBT-008 | No dedicated `EventStream` test coverage | Low | Silent regression risk in durability-critical code | Add tests, ideally alongside DEBT-003 work | P2 — MODERATE (bundle with DEBT-003) |
| DEBT-010 | Config watcher thread race during test patching | Low–Medium | Test flakiness; narrow theoretical production hazard | Root-cause and fix the race, or isolate the watcher's `CONFIG_DIR` read | P3 — POST-FREEZE (project's own classification; low production risk) |
| DEBT-011 | `ContentDomain` vs. `LearningCandidate` open-domain contradiction | Medium | Blocks further `ContentDomain` extension | Dedicated reconciliation pass | P2 — MODERATE, not currently blocking anything freeze-critical |
| DEBT-012 | Full-suite runs rewrite real config files, sometimes losing real comment content | Low–Medium | Spurious diffs; one confirmed content-loss instance (reverted, not committed) | Identify and fix the offending fixture | P2 — MODERATE |
| DEBT-013 | `detected_language` doesn't propagate past `normalize_request()` | Low (by design so far) | No current feature needs it | Wire when a feature actually needs it | P3 — POST-FREEZE |
| DEBT-014 | Drift-check tooling doesn't cover `learning.py`'s (legitimate) governance call | Low | Detection-coverage gap, not an active violation | Extend `GOVERNANCE_BOUNDARY_FILES` | P2 — MODERATE |
| DEBT-015 | Operation/ExecutionAttempt/ExecutionSnapshot architecture | Medium (project's own label) | Correctly non-blocking future architecture | — | **P3 — POST-FREEZE, confirmed correct** |
| DEBT-018 | Verification/Critic/Evidence system (~5/90 contract types, unmerged branch) | N/A — not yet a Kernel requirement | Not currently required for v1.0 | Continue on its own branch | **P3 — POST-FREEZE** |
| — | Task Runner / sandboxed code execution (§3 mandate, zero implementation) | Architecturally mandated, currently untracked anywhere | Not required by current Kernel substance, but a documented mandate with no tracking entry | Add to `KNOWN_ISSUES.md` or `FUTURE_RESEARCH_VAULT.md` explicitly, even if disposed as post-freeze | **Needs an explicit disposition decision — currently falls through every tracking mechanism** |

---

## 21. MUST FIX BEFORE FREEZE

1. `CTX-DELETE-001` — `UnifiedMemory.delete()` must return `False` (or raise) when the authoritative storage deletion fails. Acceptance: `tests/test_unified_memory.py::TestUnifiedMemoryDelete::test_delete_returns_false_when_l1_storage_deletion_fails` passes.
2. `CTX-AUTH-001` — the constructed intent-interpretation prompt must not allow retrieved context to produce a second, structurally-indistinguishable "Request:" section. Acceptance: both `test_intent_security.py` tests pass.
3. `SupervisorWorker` worker-retry reachability — either wire a real production call site for `failed_worker_result`, or formally retire `_attempt_retry()` and its tests with a documented decision. Acceptance: either a new integration test proves a real worker exception reaches `SupervisorWorker`, or the dead code and its tests are removed and `KNOWN_ISSUES.md` records the decision.
4. DEBT-016 — unify the two watchdog/progress-monitor implementations into one canonical authority. Acceptance: one `ExecutionWatchdog` class, one `ProgressMonitor` class, both call sites (`WorkflowRuntime` and `model_router.py`) use the same one.
5. DEBT-003 — implement checkpoint/resume against the now-resolved identity prerequisite. Acceptance: a process restart mid-workflow resumes from the last checkpoint without duplicating or losing completed node work, proven by a new integration test that kills and restarts the process mid-execution.

## 22. MUST VERIFY BEFORE FREEZE

1. `CTX-SCOPE-001` and `CTX-CACHE-001` — real, evidenced, currently unfixed, but this session did not assess how exploitable they are in OCBrain's actual deployment model (single local user vs. multi-caller). Verify severity against your actual threat model before deciding whether they join the P0 list above or are P1/P2.
2. The API authentication gap (`interface/api.py`) — verify against your actual threat model whether "any local process" is inside or outside OCBrain's trust boundary. This determines whether it's a freeze blocker or an accepted, documented risk.
3. Planner-impasse terminal-event behavior under genuine budget exhaustion — the design is confirmed correct by code read; the specific regression test proving it was not re-executed this session.
4. `attempt_id` stability across a real multi-attempt retry sequence — field exists; behavior not re-traced end-to-end this session.
5. Whether `ContextMemory` (`core/context.py`) and `UnifiedMemory` are a legitimate separation of concerns or unreconciled duplication (§13).
6. Execution-instance isolation, worker lifecycle integrity, and resource-leak freedom (§13, §16 of your governing prompt) — none of these were audited to completion this session; each needs a dedicated pass before a genuine 🟢 GO can be issued.
7. Whether the historical "fine-tuning safety gate comparing model to itself" finding refers to the code path this session inspected (which looks correct) or a different, possibly-already-removed code path.

## 23. MUST NOT TOUCH BEFORE FREEZE

- C-MoE, in any form — confirmed zero code exists; confirmed not required by any current Kernel substance (§4).
- DEBT-015's Operation/ExecutionAttempt/ExecutionSnapshot architecture — correctly proposed-only.
- DEBT-018's Verification/Critic/Evidence system — continue on its own branch; do not pull it into the Kernel-freeze critical path.
- The K2.2 `PlannerWorker` legacy path — it is an intentional fallback, not a target for removal or "cleanup" as part of this freeze.
- Any new architecture for the Task Runner / sandboxed execution mandate — this needs a scope decision (§3), not a design or implementation, before freeze.
- Any of the four Priority-B/C repository study backlog items from `FUTURE_RESEARCH_VAULT.md`.
- Richer execution-inspection UI, idempotency semantics for future side-effecting capabilities, stale-attempt rejection — all correctly DEBT-015 sub-items, all correctly deferred.

---

## 24. Kernel Freeze Critical Path

Derived from actual dependencies found this session, not assumed:

```
Fix CTX-DELETE-001 (independent, no dependencies)
    +
Fix CTX-AUTH-001 (independent, no dependencies)
    ↓
Resolve SupervisorWorker retry-reachability decision
    ↓ (informs whether node-retry needs the shared budget wired in)
Unify DEBT-016 (two watchdog implementations)
    ↓ (checkpoint work should target the unified watchdog's failure/recovery signals, not duplicate against both)
Implement DEBT-003 (checkpoint/resume)
    ↓
Full regression run (must show zero new failures beyond the 34 documented environment-only ones, and confirm CTX-AUTH-001/CTX-DELETE-001 now pass)
    ↓
Resolve MUST-VERIFY items #1-#2 above (threat-model decisions only you can make)
    ↓
Clean-room validation repeat (confirm the fixes hold from a fresh clone)
    ↓
Debt register final reconciliation + KNOWN_ISSUES.md sync
    ↓
Kernel v1.0 Freeze
```

## 25. Parallelizable Work

```
CRITICAL PATH
CTX-DELETE-001 fix ─┐
CTX-AUTH-001 fix ───┼→ SupervisorWorker decision → DEBT-016 unification → DEBT-003 → full regression → Freeze

PARALLEL (no shared files, no architecture dependency on the critical path above)
CTX-SCOPE-001 investigation/fix ─┐
CTX-CACHE-001 investigation/fix ─┼→ folds into the same regression run before freeze
v1.0.0 tag cleanup ──────────────┤
KNOWN_ISSUES.md sync of NEW-1..8 ┘
```
DEBT-002/006/007/010/011/012/014 are all independently parallelizable — none of them share files or architecture with the critical path above, and each is individually small. They are P2/P3 and not required before freeze, but can be picked up opportunistically without risk of conflicting with the critical-path work.

---

## 26. Full Sequential Implementation Plan

### Step 1 — Fix CTX-DELETE-001

**Objective:** `UnifiedMemory.delete()` returns `False` when authoritative L1 storage deletion fails, instead of unconditionally `True`.
**Current State:** `unified_memory.py`'s delete path catches the storage-layer exception, logs it, falls through to `return True`.
**Gap:** the return value contradicts the method's own documented guarantee.
**Dependencies:** none.
**Files/Components:** `core/memory/unified_memory.py` (delete method, near line 988 per this session's log output).
**Implementation Actions:** propagate the failure — return `False`, or re-raise a typed exception the caller must handle, matching whichever contract the rest of `UnifiedMemory`'s write/update methods already use for failure signaling (check `write()`/`update()` for the established pattern before choosing, per your Law 4 determinism/consistency preference).
**Acceptance Criteria:** `tests/test_unified_memory.py::TestUnifiedMemoryDelete::test_delete_returns_false_when_l1_storage_deletion_fails` passes; no other `test_unified_memory.py` test regresses.
**Tests:** the existing test above; no new test needed unless the failure-signaling mechanism changes shape (e.g., if you choose to raise rather than return `False`, the test itself needs updating too — but that's a test-authoring decision, not new coverage).
**Regression Risk:** low — any caller currently assuming `delete()` always succeeds needs auditing; grep for `.delete(` call sites and confirm each handles a `False`/exception return.
**Exit Condition:** test passes; call-site audit complete.

### Step 2 — Fix CTX-AUTH-001

**Objective:** retrieved/external context cannot produce a prompt section structurally indistinguishable from the genuine user request.
**Current State:** `intent.py`'s prompt assembly interpolates retrieved context and the raw request into the same template without a structural boundary that survives adversarial content.
**Gap:** a context string containing literal `"Request:\n"` produces two such sections in the final prompt.
**Dependencies:** none.
**Files/Components:** `core/cognitive/intent.py` (prompt-construction function feeding `generate_with_fallback`).
**Implementation Actions:** escape or strip structural delimiter tokens from retrieved context before interpolation, or restructure the prompt so the request section is delimited by a token that cannot appear in untrusted context (e.g., a boundary marker generated fresh per call, not a static string an attacker can predict and replicate).
**Acceptance Criteria:** both `tests/core/cognitive/test_intent_security.py` tests pass.
**Tests:** existing two tests; consider adding a third exercising a different injection shape (e.g., injected content appearing *before* rather than after the legitimate request) to confirm the fix isn't shape-specific.
**Regression Risk:** medium — this touches the core prompt template every intent-classification call uses; full `test_intent_security.py` and `test_planner_worker.py`-adjacent suites should be re-run in full, not spot-checked.
**Exit Condition:** both tests pass; no prompt-construction regression in the broader intent-classification test set.

### Step 3 — Resolve SupervisorWorker retry-reachability

**Objective:** either `failed_worker_result` has a real production producer, or `_attempt_retry()`/its tests are formally retired.
**Current State:** implemented, tested in isolation, zero production callers.
**Gap:** a genuine worker-execution failure in the live K4.2 path is invisible to `SupervisorWorker`.
**Dependencies:** Steps 1–2 are independent of this; can run in parallel.
**Files/Components:** `core/orchestrator.py` (or `core/workflow/runtime.py`, depending on where you decide the escalation should originate), `core/workers/supervisor.py`.
**Implementation Actions:** decide first (this is an architecture decision, not a pure implementation task) whether execution-failure recovery should ever escalate above node-local `retry_policy` to a Supervisor-mediated, budget-aware retry — and if so, at what trigger (retry_policy exhausted? specific error classes only?). Then wire the call site accordingly, ensuring it draws from the same `OperationRecoveryBudget` the planner re-plan loop uses. If the decision is "no, node-local retry is sufficient by design," delete `_attempt_retry()` and its two test files, and document the decision in `KNOWN_ISSUES.md`.
**Acceptance Criteria:** either (a) a new integration test proves a real thrown exception inside a live K4.2 node execution reaches `SupervisorWorker` via `failed_worker_result`, and the budget consumed is shared with the planner's `OperationRecoveryBudget`; or (b) `_attempt_retry()` and its dedicated tests no longer exist, and `KNOWN_ISSUES.md` records why.
**Tests:** new integration test (option a) or removal of `test_supervisor_worker.py`'s retry-specific tests (option b).
**Regression Risk:** low for option (b); medium for option (a) — touches the shared recovery-budget accounting path.
**Exit Condition:** one of the two acceptance criteria is objectively true.

### Step 4 — Unify DEBT-016 (watchdog/progress-monitor duplication)

**Objective:** one canonical `ExecutionWatchdog` and one canonical `ProgressMonitor`, used by both `WorkflowRuntime` and `model_router.py`.
**Current State:** two independent pairs, `watchdog.py`+`progress.py` vs. `execution_watchdog.py`+`progress_monitor.py`.
**Gap:** duplicated authority on "is this execution stalled?"
**Dependencies:** should follow Step 3 (if Step 3 changes how execution failures escalate, the unified watchdog should be built against the final shape of that escalation path, not against a version that's about to change — per your own §49 no-rework principle).
**Files/Components:** `core/runtime/watchdog.py`, `progress.py`, `execution_watchdog.py`, `progress_monitor.py`, plus both call sites (`core/workflow/runtime.py`, `core/model_router.py`).
**Implementation Actions:** pick the graph-aware pair as canonical (it's already the one integrated with the execution-inspection UI/API per the project's own notes) and migrate `model_router.py`'s long-form generation path onto it; delete the standalone pair once migrated.
**Acceptance Criteria:** `grep -rn "class ExecutionWatchdog\|class ProgressMonitor"` returns exactly one definition of each in the whole repository; both call sites use it.
**Tests:** existing tests for both current implementations must be consolidated onto the surviving one, not simply deleted — confirm no coverage is lost in the merge.
**Regression Risk:** medium-high — `model_router.py`'s long-form generation path is a real, exercised production path; this migration needs its own dedicated regression pass, not a spot-check.
**Exit Condition:** single implementation confirmed; both call sites' existing tests pass against it.

### Step 5 — Implement DEBT-003 (checkpoint/resume)

**Objective:** `WorkflowRuntime` calls `EventStream.create_checkpoint()`/`get_checkpoint()` such that a process restart mid-workflow resumes rather than losing or duplicating work.
**Current State:** the identity prerequisite (`root_operation_id`, `attempt_id`) exists; the checkpoint API exists; nothing connects them.
**Gap:** the connection itself.
**Dependencies:** Step 4 (checkpointing should record state consistent with whichever watchdog/recovery signal is now canonical, not build against a duplicated one that's about to be removed).
**Files/Components:** `core/workflow/runtime.py`, `core/events/event_stream.py`.
**Implementation Actions:** call `create_checkpoint()` at node-completion boundaries (using `root_operation_id`/`attempt_id` as the checkpoint key); on startup, check for an existing checkpoint matching an in-flight `root_operation_id` and resume from it rather than restarting from scratch; add the dedicated `EventStream` test coverage DEBT-008 already flags as missing, since you'll need it to validate this work regardless.
**Acceptance Criteria:** a new integration test that starts a multi-node workflow, kills the process mid-execution, restarts it, and confirms the workflow resumes from the last completed node rather than re-running from the beginning or losing the operation entirely.
**Tests:** the new integration test above, plus DEBT-008's previously-missing direct `EventStream.append()`/`replay()`/checkpoint unit tests.
**Regression Risk:** medium — touches the core workflow execution loop; full `test_workflow_runtime.py` suite must pass unchanged for the non-crash-recovery cases.
**Exit Condition:** the kill/restart integration test passes; DEBT-008's coverage gap is closed; full regression suite shows zero new failures.

### Steps 6+ — Full Regression, Threat-Model Decisions, Clean-Room Repeat, Freeze

Per the critical path in §24: full regression run (expect the same 34 documented environment-only failures, zero others); your explicit decisions on the API-authentication threat model and on `CTX-SCOPE-001`/`CTX-CACHE-001` severity (§22); a repeat clean-room clone-and-test cycle to confirm the fixes hold from scratch; final `KNOWN_ISSUES.md`/`CURRENT_STATE.md` sync; tag the actual freeze commit (not `v1.0.0`, which is stale — cut a new, correctly-placed tag).

---

## 27. Reliability / Failure Campaign

`[NOT COMPLETED THIS PASS]` as an executed campaign — this session traced individual failure paths incidentally (planner impasse, compilation rejection, node-level retry) but did not design and run the full deliberate campaign your §51 specifies across all listed scenarios. What's confirmed from this session's work maps onto a few of your scenarios directly:

| Scenario | Current Evidence | Gap |
|---|---|---|
| Planner impasse | Confirmed: bounded retry, terminal event, correctly separate from Supervisor (§6.C) | Terminal-event test not re-executed this session |
| Compilation rejection | Confirmed: routes to `SupervisorWorker` correctly (§6.E) | — |
| Worker exception | **Confirmed gap:** caught by node-local `retry_policy` only; `SupervisorWorker` escalation unreachable (§6.E) | Step 3 above |
| Process restart mid-execution | **Confirmed gap:** no checkpoint consumption exists at all (§11, DEBT-003) | Step 5 above |
| Duplicate event handling | `[NOT COMPLETED THIS PASS]` | Needs DEBT-008 coverage, bundle with Step 5 |
| Concurrent executions | `[NOT COMPLETED THIS PASS]` | §13 |
| Model unavailable / malformed / empty output | `[NOT COMPLETED THIS PASS]` this session, though §31 of your original prompt's historical concern ("short requests succeed, larger requests return 'No response'") was not re-traced — recommend a dedicated pass | — |

The remaining scenarios in your §51 list (malformed input, ambiguous capability, budget exhaustion as distinct from impasse, cancellation-during-recovery races, persistence corruption, duplicate workers, task mutation) were not exercised this session. Recommend this campaign be run as its own dedicated pass **after** Steps 1–5 above, since several of the scenarios (worker exception, process restart) would otherwise be tested against code that's about to change.

---

## 28. Kernel v1.0 Freeze Gate

Using your own checklist structure, current status:

**Architecture:** boundary defined (§3) ✅ · required milestones complete (§4, K4.1-K4.4 substance) ✅ · one authoritative implementation per responsibility ⚠️ (watchdog duplication, DEBT-016) · obsolete paths removed 🧹 (`WorkerContext`, pending test migration) · contracts stable ✅ (spot-checked) · state ownership defined 🧪 (not fully audited) · architecture invariants satisfied ⚠️ (INV-01, INV-05 currently violated)

**K4.2:** required packets complete ✅ · acceptance criteria satisfied ✅ (4 of 5 structural gaps) · required integrations working ⚠️ (Supervisor worker-retry gap) · known structural gaps resolved ⚠️ (4 of 5)

**K4.3:** repository-defined K4.3 completely implemented ✅ · acceptance criteria satisfied ✅ · dependencies resolved ✅ · no accidental C-MoE scope imported ✅, confirmed independently

**K4.4:** freeze-required items complete ⚠️ (DEBT-003, DEBT-016 open) · hardening items dispositioned ✅ (DEBT-015 correctly deferred) · post-freeze work explicitly deferred ✅

**Execution:** workflow execution verified ✅ (happy path) · worker lifecycle verified 🧪 (not audited) · watchdog verified ⚠️ (duplicated) · budgets verified ⚠️ (DEBT-007, not fed real numbers) · cancellation verified 🧪 (not audited) · retries verified ⚠️ (works, but split-authority) · recovery verified ⚠️ (checkpoint missing) · execution-instance isolation verified 🧪 (not audited)

**State/Events/Persistence:** events consistent 🧪 · replay verified 🔴 (never exercised, DEBT-003) · persistence verified 🧪 · crash recovery verified 🔴 · idempotency verified 🧪 · state machines complete 🧪

**Governance/Security:** no known P0 governance/security flaws ❌ (`CTX-DELETE-001`, `CTX-AUTH-001` are P0) · no bypassable critical controls ⚠️ (recovery-budget bypass, §9) · configuration protected ⚠️ (no auth, narrow mutation surface) · sandbox boundaries respected N/A (no sandbox exists yet, §3)

**Memory:** authoritative memory path established 🧪 (ContextMemory/UnifiedMemory relationship unresolved) · legacy conflicts removed 🧪 · persistence/recovery verified ⚠️ (deletion-integrity defect)

**Concurrency:** no unresolved critical race conditions 🧪 (not audited) · simultaneous execution isolation verified 🧪 · watchdog/cancellation/retry races verified 🧪

**Tests:** complete regression suite passes ✅ (modulo documented environment/deliberately-red exceptions) · integration tests pass ✅ · failure campaign passes ❌ (not run, §27) · historical regression failures covered ⚠️ (partial, §18) · critical negative paths tested ⚠️ (the 4 CTX-* invariants exist specifically because they're *not* yet satisfied) · migration/recovery tests pass 🔴 (don't exist yet, DEBT-008/DEBT-003)

**Reproducibility:** clean checkout works ✅, verified this session · clean installation works ✅, verified this session (once disk space was available) · canonical test procedure works ✅ · startup/shutdown verified 🧪 (not attempted) · no undocumented environmental dependency ⚠️ (huggingface.co dependency undocumented)

**Debt:** no unresolved P0 blockers ❌ (2 found this session) · P1 resolved or justified ❌ (4-5 open) · all remaining debt classified ✅ (§20) · post-freeze scope documented ✅

**Release:** documentation synchronized ⚠️ (3 new CTX-* findings not yet in `KNOWN_ISSUES.md`) · version/tag prepared ❌ (`v1.0.0` is stale) · freeze candidate reproducible ✅ · post-freeze change policy defined ⚠️ (see §29, this audit proposes one; not yet ratified by you)

**Overall gate status: not satisfied. Two P0s, four to five P1s, and several 🧪/❌ rows must close first.**

---

## 29. Post-Freeze Change Policy (proposed — needs your ratification, not this audit's authority to set)

**Allowed after freeze without reopening architecture:**
- Fixes to any of the P0/P1 items in §20 that are *discovered but not yet fixed* by freeze time (shouldn't happen if §21's list is actually cleared first, but stated for completeness).
- Narrow security patches (a new `CTX-*`-style finding discovered post-freeze).
- DEBT-002/006/007/010/011/012/014-class bounded, single-subsystem fixes.

**Not allowed without reopening architecture:**
- Any C-MoE integration.
- Any change to the `root_operation_id`/`attempt_id` identity model.
- Any change to the GovernanceKernel's 5-governor structure or the Law 1 "no bypass" invariant.
- Any new orchestration-layer state machine.
- Implementing the Task Runner / sandboxed execution mandate — this is substantial enough new capability that it deserves its own milestone and ADR, not a post-freeze patch.

---

## 30. Deferred After Kernel v1.0

- C-MoE (all three research documents' proposed architecture) — confirmed post-freeze, confirmed zero current code.
- DEBT-015's full Operation/ExecutionAttempt/ExecutionSnapshot architecture (12 sub-items).
- DEBT-018's Verification/Critic/Evidence system (~85 of ~90 contract types remaining).
- Richer execution-inspection UI.
- `FUTURE_RESEARCH_VAULT.md`'s FR-0001–FR-0015 and the Priority A/B/C repository study backlog.
- The Task Runner / sandboxed code execution mandate — **you need to explicitly decide this belongs here rather than letting it continue falling through every tracking document, per §3's finding.**
- `ContentDomain`/`LearningCandidate` reconciliation (DEBT-011) — moderate priority, not freeze-blocking, but shouldn't be forgotten indefinitely either.

---

## 31. FINAL GO / NO-GO

# 🔴 NO-GO

The Kernel cannot be frozen as-is. This is not a close call inflated into caution — two of the blockers found this session are P0 by any reasonable reading of your own Law 1 (Governance Before Capability) and your own memory-provenance requirements (§8): a deletion that silently doesn't happen while reporting success, and a prompt-injection vector into the component every single request passes through first.

**Blockers (must close before any freeze consideration):**
1. `CTX-DELETE-001` (§21.1)
2. `CTX-AUTH-001` (§21.2)

**Required fixes (strongly recommended before freeze, arguable as P1 rather than P0 depending on your risk tolerance):**
3. `SupervisorWorker` retry-reachability decision (§21.3)
4. DEBT-016 watchdog unification (§21.4)
5. DEBT-003 checkpoint/resume (§21.5)

**Required verification (must resolve the ambiguity, even if the answer turns out benign):**
6. `CTX-SCOPE-001` / `CTX-CACHE-001` severity against your actual threat model (§22.1)
7. API authentication threat-model decision (§22.2)

**Dependency order:** §24's critical path — the two P0 security fixes can happen immediately and in parallel with each other; everything else follows the sequence in §24/§26.

Once §21's five items are closed and §22's items are explicitly resolved (not necessarily "fixed," but *decided*), this becomes, in this auditor's assessment, a legitimate 🟡 CONDITIONAL GO — the underlying architecture is sound, the historical identity/migration blockers are genuinely resolved, and nothing found this session requires a redesign, only completion of already-scoped work.

---

## 32. EXACTLY WHAT REMAINS BEFORE KERNEL V1.0

1. **Fix `CTX-DELETE-001`.** Reason: false-success on deletion violates memory-provenance/correctness guarantees. Dependency: none. Acceptance: `test_delete_returns_false_when_l1_storage_deletion_fails` passes.
2. **Fix `CTX-AUTH-001`.** Reason: prompt-injection vector in the Cognitive Front-End. Dependency: none. Acceptance: both `test_intent_security.py` tests pass.
3. **Decide and resolve `CTX-SCOPE-001` severity; fix or explicitly accept the risk.** Reason: cross-caller memory-scope leakage. Dependency: none. Acceptance: either the fix lands and its test passes, or `KNOWN_ISSUES.md` records an explicit, reasoned acceptance of the residual risk.
4. **Decide and resolve `CTX-CACHE-001` severity; fix or explicitly accept the risk.** Reason: prompt-cache collision. Dependency: none. Acceptance: same pattern as #3.
5. **Decide `SupervisorWorker` retry-reachability: wire it or retire it.** Reason: currently tested-but-unreachable code, a false-completion risk. Dependency: none. Acceptance: §21.3.
6. **Unify the two watchdog/progress-monitor implementations (DEBT-016).** Reason: the project's own Kernel Completion Study already names this a freeze-gate failure. Dependency: ideally after #5. Acceptance: §21.4.
7. **Implement checkpoint/resume (DEBT-003).** Reason: no workflow durability across restart despite the checkpoint API existing. Dependency: after #6. Acceptance: §21.5.
8. **Decide the API-authentication threat model and act accordingly** (fix, or explicit documented acceptance). Reason: currently zero authentication anywhere in `interface/api.py`. Dependency: none, parallelizable with anything above. Acceptance: either an auth mechanism is added, or `KNOWN_ISSUES.md`/an ADR explicitly states why "any local process" is an accepted trust boundary for a local-first tool.
9. **Run the full reliability/failure campaign (§27) against the post-fix codebase.** Reason: this session traced individual paths but did not execute the full deliberate campaign your governing prompt specifies. Dependency: after #1–7 (testing fixed code, not code about to change). Acceptance: §27's table fully populated with pass/fail evidence for every listed scenario.
10. **Full regression run.** Reason: confirm zero new failures beyond the 34 documented environment-only ones, and confirm all previously-red `CTX-*` tests now pass. Dependency: after #1–9. Acceptance: `pytest -q` shows only the 34 known `huggingface.co` failures (or zero, if offline-mode is also fixed as a nice-to-have) and nothing else.
11. **Repeat clean-room clone-and-test cycle from scratch.** Reason: confirm the fixes hold independent of this session's already-warmed environment. Dependency: after #10. Acceptance: §19's procedure repeated, same result.
12. **Sync `KNOWN_ISSUES.md`/`CURRENT_STATE.md`** with all findings from this audit (the 3 new `CTX-*` items, the `SupervisorWorker` finding, the DEBT-016/DEBT-003 closures, the `v1.0.0` tag cleanup). Dependency: after #1–11. Acceptance: documentation matches code, re-verifiable by the next session's own fresh grep, the way this session verified its predecessors'.
13. **Delete or clearly re-annotate the stale `v1.0.0` tag; cut the real freeze tag on the correct commit.** Dependency: after #12. Acceptance: a tag exists whose commit is the actual, fully-verified freeze point.
14. **FREEZE KERNEL V1.0.**

