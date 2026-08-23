# OCBrain — Kernel v1.0 Pre-Freeze Debt Reconciliation & Contract Integration Audit

**Status:** Reconciliation / verification / classification audit — not implementation, not redesign, not a third research study.
**Date:** August 22, 2026
**Repository state audited:** `1h0lde4/ocbrain-v4.1`, HEAD `5a08178` (own C-MoE study commit; working tree clean, `origin/main` matches local exactly at audit start — fetched and confirmed, not assumed).
**Governing directive:** `OCBrain — Kernel v1.0 Pre-Freeze Debt Reconciliation & Contract Integration Audit`.
**Documents integrated (all read this session, several re-read against post-H2-integration state rather than trusted from memory):** `OCBRAIN_KERNEL_CONSTITUTION.md`; `docs/architecture/PROJECT_INSTRUCTIONS.md`; `docs/architecture/OCBrain Architecture Evolution Directive.md` (**AED**); `docs/architecture/future_debt_study/OCBRAIN_RELIABILITY_DURABLE_EXECUTION_ARCHITECTURE_STUDY.md` (**RS**); `docs/architecture/future_debt_study/OCBRAIN_CMOE_ADAPTIVE_COGNITIVE_SCALING_ARCHITECTURE_STUDY.md` (**CMS**, this audit's own author, previous session — re-checked against code rather than trusted verbatim); `docs/architecture/IMPLEMENTATION_TRACKER.md`; `CURRENT_STATE.md`; `KNOWN_ISSUES.md`; `docs/architecture/decisions/ADR_INDEX.md` and all fifteen standalone ADRs; `docs/architecture/h2_packet_ownership.json`; `PROJECT_INDEX.md`; `IMPLEMENTATION_ROADMAP.md`; `docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`; plus direct reads of `core/workers/capability_executor.py`, `core/capabilities/adapter_runtime.py`, `core/model_router.py`, `core/governance/governance_kernel.py`, `core/workflow/definition.py`, `core/cognitive/compiler.py`, `core/workers/base.py`, `core/runtime/execution_context.py`, and a repository-wide sweep for legacy/deprecation markers.
**Evidence discipline:** `[FACT]` / `[INFER]` / `[REC]`, per this project's own convention.

---

## Executive Conclusion

**Verdict: NOT_FREEZE_READY.** The minimum blocking closure set is small — two explicit decisions, each already fully specified with its tradeoffs laid out by prior work, neither requiring further research or implementation. Everything else this audit found — including all sixteen Critical Pre-Freeze items RS and CMS together identify — is real, correctly scoped, and does not need to block the freeze itself; it needs to be ratified (a paperwork step, not a research step) before the *next* phase (any C-MoE/Runtime implementation packet) begins.

K4.2 itself — the actual Cognitive Front-End, which is what "Kernel v1.0" concretely means today per `KERNEL_ARCHITECTURE_v1.0.md`'s frozen spec and `OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md`'s pipeline boundary — is in excellent shape: H1 frozen with ceremony (16-gate review, Moncif sign-off, Aug 17); H2 complete with zero regressions (1214 passed / 34 pre-existing-and-identical failed, Aug 22); two independent studies (RS, CMS) each concluded "no stop" against it. **The two blockers below are not about K4.2's own readiness — they are about a Kernel-Constitution-level ambiguity and a live authority conflict, both narrow, both this project's own "no silent resolution" discipline says must not be resolved by an AI session.**

**Minimum blocking closure set (2 items — see full detail in Sections 3 and 11):**
1. **Scope/Session/identity-family decision** — RS's own Critical Pre-Freeze item #4, which RS explicitly says "needs Moncif's decision, not just this study's proposed reading." Unresolved by either study, by design. This audit does not resolve it either — resolving it is exactly the kind of silent architectural choice this project's standing discipline forbids an AI session from making.
2. **ADR-001 vs. current `WorkerContext`/`ExecutionContext` reality** — a genuine, previously undiscovered contradiction between a frozen, embedded ADR and the code as it has existed since before H1(Section 11). Small, bounded, two viable resolutions, needs an explicit choice.

Neither blocker requires new research, a new study, or implementation work to *identify* — both are fully specified below. Closing them is a decision, not a project.

---

## 1. Unified Debt Reconciliation

**[FACT]** `KNOWN_ISSUES.md` was last synchronized Aug 22, 2026 (same day as the H2 integration) and correctly reflects DEBT-002 through DEBT-012 as they stand post-integration — re-read in full this session, not assumed from an earlier snapshot. **None of RS's or CMS's findings have been folded into it yet** — confirmed by direct grep (no `DEBT-01[3-9]`, no mention of `RecursionGovernor` accumulation, `sqlite3.connect`, `os.execv`, or `WorkerContext` anywhere in the file). This is not a defect in `KNOWN_ISSUES.md` — RS and CMS both followed this project's own established pattern of *recommending* additions rather than self-editing a protected tracking file (see DEBT-012's own entry, added the same way by D12/ADR-K4.2-H-12 for a different finding). It does mean this audit's Section 1 is the first place these findings are reconciled into the single register the directive requires.

### 1.1 Existing register (DEBT-002 → DEBT-012) — reconciled, not restated

All eleven remain accurately classified as `KNOWN_ISSUES.md` already has them; none are duplicated, superseded, or resolved by RS/CMS's work. Table format: only what changed or what a study touches.

| ID | Title | Current status | RS/CMS touch? | Classification |
|---|---|---|---|---|
| DEBT-002 | AgentGovernor delegation dormancy | Active, Medium | No | POST_FREEZE |
| DEBT-003 | Checkpoint/resume not implemented | Active, Medium | **RS's #1 Critical Pre-Freeze item; CMS's entire durability posture inherits this directly (CMS §B.1, §T, §S)** | BLOCKING_PRE_FREEZE **for the contract shape only** (RS's own position — see §2 below); implementation is REQUIRED_POST_FREEZE |
| DEBT-004 | KnowledgeEvent/EventStream duality | Active, Low | No | POST_FREEZE |
| DEBT-005 | EventBus/EventStream relationship | Active, Low | No | POST_FREEZE |
| DEBT-006 | L2 semantic memory loses embeddings on restart | Active, Medium | RS cites as precedent for volatile-state pattern | POST_FREEZE |
| DEBT-007 | BudgetGovernor accumulation gap | Active, Medium | RS names as `OperationRecoveryBudget`/Think-Harder precedent (CMS §F.1, §L) | REQUIRED_POST_FREEZE |
| DEBT-008 | EventStream has no dedicated test coverage | Active, Low | No | POST_FREEZE |
| DEBT-010 | Config watcher race | Active, Low–Medium | No | POST_FREEZE |
| DEBT-011 | ContentDomain vs. LearningCandidate (K4.1-L) | Active, Medium | **CMS §O depends on this being resolved before C-MoE's own Routing Memory can safely extend the Learning Candidate model** | REQUIRED_POST_FREEZE, **gates K4.2.6+ already per `IMPLEMENTATION_ROADMAP.md`; this audit adds that it also gates CMS §O** |
| DEBT-012 | Test suite rewrites `config/*.toml` in place | Active, Low | No | POST_FREEZE |

**Resolved entries** (ClarificationPolicy/H-13, `IMPLEMENTATION_TRACKER.md` existence, A6/A7, K2.2-path persistence, DEBT-001, DEBT-009, and the July 16 readiness-audit backlog): re-read in full, all still correctly marked Resolved, no reopening evidence found. **RESOLVED_VERIFIED.**

### 1.2 Newly reconciled — RS/CMS findings not yet in the register, proposed as new entries

**[REC]** Proposed IDs continue from DEBT-012. Content is RS's/CMS's own (cited, not re-derived); the *reconciliation* — confirming each is still real against current code, assigning an ID, and classifying it in this project's actual taxonomy — is this audit's contribution.

| Proposed ID | Title | Evidence | Owner | Classification |
|---|---|---|---|---|
| DEBT-013 | `RecursionGovernor` accumulation never incremented — confirmed 100%, not merely likely | **[FACT]** Every single site that constructs a `GovernanceAction` or `ExecutionContext.governance_state` sets `recursion_depth` to literal `0` — `core/runtime/execution_runtime.py:166`, `core/workflow/runtime.py:366`, `core/orchestrator.py:215` (whose own comment reads "`handle()` has no actual recursion depth [tracking]"). `RecursionGovernor.evaluate()` (`core/governance/governance_kernel.py:136`) is correct and would reject at depth > 10 given a real number; no code path anywhere produces one. Re-verified by fresh repo-wide grep this session, not carried over from RS unchecked. | Governance | Active debt today; **elevated to REQUIRED_POST_FREEZE, not merely POST_FREEZE**, because CMS §F.1 identifies C-MoE's own recursive escalation path as the first mechanism that would actually need this wired — it stops being safe-to-leave-dormant the moment any C-MoE implementation packet starts. |
| DEBT-014 | Global `sqlite3.connect` monkeypatch | RS finding (not independently re-verified this session — L2 boundary, see Methodology) | Persistence | POST_FREEZE |
| DEBT-015 | `updater.py`'s `restart()` uses `os.execv()` — self-update is architecturally indistinguishable from a crash, zero governance evaluation | RS §S.2, this project's own sharpest Reliability finding | Runtime/Governance | **REQUIRED_POST_FREEZE** — not blocking the freeze itself (no update mechanism is invoked automatically today), but blocking before this project's own Autonomous Evolution Rules (`PROJECT_INSTRUCTIONS.md` §13, "no autonomous evolution may... bypass approval") can be said to actually hold for the update path specifically. |
| DEBT-016 | `WorkerContext`/`ExecutionContext` compatibility shim outlived its own stated removal target | **[FACT] New finding, this audit.** `core/runtime/execution_context.py`'s `query` and `recursion_depth` properties, and `to_worker_context()`, are each explicitly commented `"Compatibility shim — will be removed after K2.4."` K2.4 (Governance) completed long before K4.2. Confirmed by direct grep: every worker subclass in the repository (`PlannerWorker`, `CapabilityExecutorWorker`, `EvaluatorWorker`, `ReflectionWorker`, `SupervisorWorker`, `MemoryCuratorWorker`) still implements `_run(self, context: WorkerContext)`, not `ExecutionContext`, directly contradicting embedded ADR-001's premise ("Zero live consumers break — `MemoryCuratorWorker` is never instantiated in production") — that premise was true when ADR-001 was written; it has not been true since workers with real production paths were built. See Section 11 for the authority-conflict analysis; this entry is the debt-register side of that finding. | Runtime | POST_FREEZE (functionally safe — see Section 11 for why), **but the ADR-001 reconciliation decision itself (Section 11, blocker #2) is a freeze blocker.** |

**[FACT]** RS's other named gaps — no idempotency-key discipline, no Mission/Scope abstraction, no dynamic priority/deadline mechanism, no formal Work Unit state machine, Assurance Assessment doesn't exist, two unreconciled identifier families — are **not** listed as numbered `DEBT-XXX` items here, deliberately: none is a gap in code that exists and should work differently. Each is future-subsystem contract work (C-MoE, durable execution) that hasn't started, which is what `KNOWN_ISSUES.md`'s own "Future Roadmap (Not Debt)" category is for, not "Active Technical Debt." They are fully reconciled in Section 2 (the Critical Pre-Freeze matrix) and Section 3 (Scope/Identity closure) instead, where the directive's own structure already accounts for them without double-listing.

### 1.3 Documentation-only findings (not debt, not blocking, noted per Section 16's "tiny documentation-only correction" allowance — not corrected here, recommended instead)

- **[FACT]** `OCBRAIN_FUTURE_ARCHITECTURE.md` exists identically (byte-for-byte, confirmed by `md5sum`) at repository root and under `docs/archive/research/`. Same pattern as the already-resolved `PROJECT_INSTRUCTIONS.md`/`ARCHITECTURE_CHANGELOG.md` root duplication (per `KNOWN_ISSUES.md`'s own July 22 resolution note), except this one was never converted to a redirect stub. Zero risk (identical content); recommend the same stub treatment for consistency. **DUPLICATE_SUPERSEDED, documentation-only.**
- **[FACT]** Both RS's own Orientation Note and CMS's Orientation Note describe H2/D3 and H2/D12 as merged-then-reverted. **This is now stale** — the Aug 22 integration (`git log e528c1e..origin/main`, read in full this session) shows both were fixed and successfully reapplied (`2e97cb1 Reapply "H2/d3 capability discrimination"`, `3abb0f6 Reapply "H2/d12 tracking hardening"`), and D3/D7/D11/D12 are all now `✅ Complete` per `CURRENT_STATE.md`. This affects zero substantive finding in either study — both cited the revert purely as situational awareness, never as an input to any architectural conclusion — but the text itself is now inaccurate as a factual claim about repository history. **Documentation-only; recommend a one-line addendum to each study's Orientation Note, not a rewrite.**
- **[FACT]** `PROJECT_INDEX.md`'s directory-structure tree (re-read in full this session, current as of the Aug 22 sync) does not mention `docs/architecture/future_debt_study/` anywhere, despite it now containing two substantial, committed, freeze-relevant architecture documents. **Documentation-only gap; recommend adding one line to the tree.**

---

## 2. Critical Pre-Freeze Reconciliation Matrix

RS's 9 items (its own §P, quoted exactly, not paraphrased) and CMS's 7 (its own §Y — 6 explicitly enumerated as Y.1–Y.6, plus the overall "thin resolution function" shape recommendation CMS's own Executive Summary/Final Classification counts as a 7th, item #1, alongside Y.1–Y.6 as items #2–7; that internal cross-reference is now made explicit here rather than left as a minor self-inconsistency between CMS's two sections). **For every item: Implemented = built in code. Contract complete = the shape is written down somewhere findable. Verified = re-checked against current code this session, not just cited from the source study.**

### RS's 9 (source: RS §P)

| # | Requirement | Repo evidence | Implemented? | Contract complete? | Verified this session? | Blocking? | Exact closure needed |
|---|---|---|---|---|---|---|---|
| RS-1 | Work Unit/Work Graph durable state-transition event schema, extending `EventStream` | `EventStream.create_checkpoint()` exists (`core/events/event_stream.py`), never called by `WorkflowRuntime` (DEBT-003) | No | **Yes** — RS §C.2 specifies the shape | Yes — DEBT-003 re-confirmed active | No (contract, not implementation, needed pre-freeze) | ADR ratifying RS §C.2's shape |
| RS-2 | Reconcile `trace_id`/`operation_id`/`stage_tag` vs. `workflow_id`/`instance_id`/`session_id` | Both families exist in code (H1 introduced the first three; the second three predate H1) — not reconciled | No | Partial — RS names the conflict, explicitly declines to resolve it, flags it needs an L2 read RS itself didn't do | Not re-verified this session (RS's own stated L2 boundary; this audit did not perform that L2 read either — see Section 16 constraint against re-opening research) | **Yes, narrowly** — feeds directly into blocker #1 (Section 3) | The L2 read RS deferred, then an ADR |
| RS-3 | Idempotency-key contract for Adapters | No side-effecting (`consequential`) Adapter is registered today (only `LLM_COMPLETION`) | No | Yes — RS §I specifies `idempotency_key = f(work_unit_id, attempt_id)` | Yes — confirmed no consequential Adapter exists yet, so this is not yet load-bearing | No — not blocking until a consequential Adapter is proposed | ADR ratifying RS §I's shape before that Adapter is admitted |
| RS-4 | Scope-vs-Session-vs-Non-Goal resolution | Kernel Constitution Non-Goal ("no concept of 'conversation'") + existing `session_id` field on `ExecutionContext` (confirmed, `core/runtime/execution_context.py`) | N/A — decision, not code | No — explicitly, by RS's own words | Confirmed still open this session (RS's text unchanged; no ADR exists) | **YES — blocker #1** | Moncif's decision between RS's proposed readings or a fresh one |
| RS-5 | One `PRAGMA synchronous` decision across SQLite primitives | Not independently re-verified this session (L2) | No | Yes — RS §F.3 names the decision needed | No | No | ADR |
| RS-6 | `RecursionGovernor`/`BudgetGovernor` accumulation: wire or document-as-acceptable | **[FACT] Re-verified this session, precisely**: zero live increments anywhere for `recursion_depth`; `BudgetGovernor`'s gap already tracked as DEBT-007 | No (both) | Yes — the decision itself ("wire or document why not") is the contract | Yes, fresh this session (Section 1.2, DEBT-013) | No (this audit's own position: REQUIRED_POST_FREEZE, elevated by CMS's finding that C-MoE's escalation path will need it) | Either wire it or write the "acceptable dormant" ADR RS itself offers as a valid closure |
| RS-7 | Does every `evaluate_action()` call site durably log its verdict? | Not independently re-verified this session (L2) | Unknown | No — open question, not yet a contract | No | No | The audit RS itself scopes as separate work |
| RS-8 | Active-mission protection before `os.execv()` | **[FACT]** `interface/updater.py`'s `restart()` calls `os.execv()` directly (RS's own citation; not re-read this session, but the absence of any warn/block check is consistent with DEBT-015/Section 1.2 having found no governance routing on this path either) | No | Yes — RS §S.3.8 specifies the check | Partially (via DEBT-015's governance-routing finding, which is adjacent) | No — no automatic update mechanism is currently invoked, so nothing exercises this gap today | ADR + implementation, REQUIRED_POST_FREEZE |
| RS-9 | Route `updater.py` through `GovernanceKernel.evaluate_action()` | Same as RS-8 | No | Yes — RS §S.3.9 specifies the new `GovernanceAction` type | Same as RS-8 | No, same reasoning | ADR + implementation, REQUIRED_POST_FREEZE |

### CMS's 7 (source: CMS §Y, items 2–7, plus the Executive-Summary-level item 1)

| # | Requirement | Repo evidence | Implemented? | Contract complete? | Verified this session? | Blocking? | Exact closure needed |
|---|---|---|---|---|---|---|---|
| CMS-1 | C-MoE as a thin, bounded resolution function at v1.0 (not the full adaptive-scaling system) | `IMPLEMENTATION_TRACKER.md` Packet 06 + `compiler.py` confirm the exact seam (`WorkflowNode.worker_type = capability_type`, unresolved) | No (0 C-MoE code exists, confirmed by fresh grep this session — see Section 4) | Yes — CMS's entire document | Yes, re-verified via direct code read this session (`compiler.py`, `capability_executor.py`) | No — this is a scope recommendation, not a gate | ADR adopting CMS's recommended shape (Model B / Model E) |
| CMS-2 | Reserve `cognitive.routing_decided` event-type family in RS §C.2's schema | Additive to RS-1 | No | Yes | N/A (paired with RS-1) | No, paired with RS-1's own non-blocking status | Fold into the same RS-1 ADR |
| CMS-3 | Work Unit state machine: cognitive/routing axis + recovery axis as orthogonal dimensions | **[FACT] Confirmed no canonical state machine exists in code at all** — `WorkflowNode`'s only state-adjacent concept confirmed this session is the plain `worker_type: str` field; no state-machine enum found in `core/workflow/definition.py` | No | Yes, this session's own Section 5 below restates it precisely | Yes | No — cheap-to-specify contract, not yet needed since nothing implements either axis | Single ADR (see Section 5) |
| CMS-4 | Three-layer resolution stack (C-MoE → AdapterRuntime → model_router) frozen as an *ownership* boundary | **[FACT] Re-verified this session directly**: `AdapterRuntime.invoke(capability_type, ...)` (`core/capabilities/adapter_runtime.py:50`) only ever selects among adapters for one already-given `capability_type`; `model_router.py`'s bootstrap/shadow/native lifecycle (`_maybe_promote`/`_maybe_rollback`) confirmed real and independent of both | Two of three layers implemented (AdapterRuntime, model_router); C-MoE layer is the missing one, by design | Yes | Yes, fresh code read this session | No | ADR naming the three layers explicitly, so a future session doesn't accidentally collapse them |
| CMS-5 | Verification's expert-selection budget structurally separate from Work Unit's own | Verification Runtime does not exist as code (confirmed this session — no `class Verif*`/`VerificationRuntime` found anywhere) | No (nothing to separate yet) | Yes — the contract is specified for when it's built | Yes (via the "doesn't exist yet" confirmation) | No — moot until Verification is built | ADR, timed to land no later than Verification's own first implementation packet |
| CMS-6 | C-MoE decisions not exempted from RS §S.3.2's schema-versioning discipline | Same status as RS-1/CMS-2 — nothing built | No | Yes | N/A | No | Fold into the RS-1/CMS-2 ADR |
| CMS-7 | Record the "Virtual Worker" vs. frozen `ADR-003` "Worker" naming collision | **[FACT] Re-verified this session directly**: `ADR-003` ("Workers are ephemeral... no state persists") is embedded and frozen in `KERNEL_ARCHITECTURE_v1.0.md` §21; confirmed still accurate against every current worker class (`core/workers/*.py`) | N/A — a naming reservation, not code | Yes | Yes | No | A single sentence in whatever future document first proposes a persistent worker-like entity — genuinely the smallest item on either list |

**Reconciliation summary:** 16 items total. **Zero are implemented** (correctly — none of RS-1/2/3/8/9 or CMS-1 through 7 were ever meant to be implementation-before-freeze, per both studies' own explicit "contracts, not features" framing, which this audit's own directive independently repeats almost verbatim). **All 16 have complete contract shapes**, except RS-2 (partial — the conflict is named, the resolution isn't) and RS-7 (genuinely still an open question, not yet a contract). **Exactly one (RS-4) is a live blocker**, and RS-2 is a narrower, dependent piece of the same blocker (Section 3). Everything else is REQUIRED_POST_FREEZE at most — ratify via ADR, in most cases foldable into a single combined ADR per study (an RS-durability ADR covering RS-1/2/3/5/6/7/8/9 plus CMS-2/3/4/5/6, and one narrow CMS-1/7 ADR adopting C-MoE's recommended shape and recording the naming reservation) rather than sixteen separate documents.

---

## 3. Scope / Identity / Session Closure

**This section performs the one piece of fresh verification this audit judged worth doing beyond citing RS and CMS — RS's own §E.3 explicitly named an L2 read of `planner.py`/`compiler.py` it had not performed, and CMS's §N is directly blocked on the answer. That read is narrow, bounded, and answers a factual question (do the two identifier families actually connect anywhere) rather than opening new research — consistent with Section 16's constraint.**

### 3.1 What the current authoritative documents actually define

- `OCBRAIN_KERNEL_CONSTITUTION.md` Part VI (Non-Goals): **[FACT]** "the kernel has no concept of 'conversation' as a primitive, only Intent and Resources" — quoted exactly, per RS §E.1.
- RS §E.1 (a recommendation, explicitly not a resolution): a future **Scope** — deliberately not named "Session" — could be a kernel-owned Resource (identity/lifecycle/provenance per Invariant 4) whose job is execution isolation and concurrency/governance boundary-drawing, distinct from "conversation." RS is explicit this is offered, not decided.
- RS §E.2: today's actual identity inventory — `workflow_id`/`instance_id` (Work Graph, exists, correct pattern); `node.id`/bare attempt counter (Work Unit, partial); `operation_id`/`trace_id` (cognitive path, exists, frozen H1); `interaction_id` aliased as `session_id` (exists, narrowly scoped to one request); **Mission and Scope both do not exist at all.**
- CMS §N inherits RS §E.1 directly as a hard dependency for C-MoE's own concurrent-mission resource arbitration, and adds nothing new to the identity question itself — by design (CMS explicitly declined to propose a second reading).

### 3.2 Where definitions conflict, overlap, or remain incomplete — including this audit's own new evidence

**[FACT] New finding, this session, resolving RS §E.3's stated uncertainty with direct evidence rather than inference:** `operation_id`/`trace_id` are generated in `core/cognitive/compiler.py`'s `compile()` and threaded extensively through `core/cognitive/planner.py`'s internal calls (confirmed by direct grep — dozens of hits, `ADR-K4.2-H-08`'s frozen contract). **But `core/workflow/definition.py`'s `WorkflowNode` and `WorkflowDefinition` classes carry neither field** (confirmed — zero hits for either identifier as a field on either class). The two ID families are not merely "unreconciled" in some abstract sense; they are **verifiably disconnected at the exact `compile() → WorkflowRuntime` handoff boundary** — `operation_id`/`trace_id` exist only inside event-emission metadata dicts during planning/compilation and do not survive onto the object `WorkflowRuntime.execute()` actually receives. This sharpens RS-2 from "partial contract, unverified" to "fully diagnosed conflict, verified, resolution still pending" (Section 2's matrix updated accordingly — RS-2 was originally the study's own L2 gap; it is no longer a gap, only a still-open decision).

**Overlap, not conflict, confirmed:** `session_id` (`ExecutionContext`, exists) and RS's proposed future "Scope" are not the same thing today — `session_id` per its own docstring "correlates related requests" (narrow, request-level), while Scope is proposed as a broader, multi-Mission arbitration boundary. No code currently conflates them. The risk RS flags is prospective (Scope "quietly growing into conversation through the back door of concurrency work"), not a present contradiction.

### 3.3 What the canonical identity boundary must be for Kernel v1.0

**Not decided by this audit — by design.** RS's own text is explicit that this "needs Moncif's decision, not just this study's proposed reading," and this project's standing discipline ("no silent resolution... stop and wait for a design decision") applies with full force to an AI-authored audit exactly as it would to an AI-authored study. What this audit adds is precision on the decision's actual shape, now that 3.2's verification is done: the decision is not merely "what does Scope mean" in the abstract — it is concretely **"should `WorkflowNode`/`WorkflowDefinition` gain an identity field connecting them back to the `operation_id` that produced them, and if so, is that field itself 'Scope,' a narrower workflow-level identity, or something else?"** That is a smaller, more answerable question than RS's original framing, without this audit having answered it.

### 3.4 / 3.5 What C-MoE and durable execution/recovery each require from that boundary

Both fully specified already, cited rather than repeated: CMS §N (C-MoE needs Scope to be the unit shared expert/model pools are arbitrated across, once it exists) and RS §S (durable execution needs whichever identity is canonical to be the thing a checkpoint/resume cycle keys against). Neither requirement changes based on which specific resolution Moncif picks — both studies were written to be resolution-agnostic on this exact point, confirmed by re-reading both this session.

### 3.6 Can this be closed without redesigning the Constitution?

**[REC] Yes.** RS's own reading — Scope-as-kernel-Resource, not Scope-as-conversation — requires no Constitutional amendment; it is an application of the existing Non-Goal, not a revision of it. This audit finds no evidence requiring DEBT-009-style Constitutional reconsideration (that precedent, re-read in full in Section 1, was about a law-count discrepancy — a different kind of question entirely).

### 3.7 Is an ADR or explicit amendment required before freeze?

**[REC] An ADR is required — this is blocker #1 of this audit's minimum blocking closure set.** Not a Constitutional amendment (3.6). The ADR needs exactly one decision recorded: what Scope/identity boundary governs concurrent Missions and Work Graphs, and (per 3.2's sharpened question) whether `WorkflowNode`/`WorkflowDefinition` should carry an explicit link back to `operation_id`. Both RS and this audit decline to make that call; both leave it fully specified for whoever does.

---

## 4. K4.2 → Runtime Boundary Audit

**Verdict: clean pass, zero violations found, verified directly against code this session (not re-cited from CMS unchecked).**

Pipeline traced end to end: `interpret_request()` → `_extract_constraints()` → `discover_capabilities()` → `plan()` → `compile()` → `WorkflowNode` → *(C-MoE boundary — no code exists here)* → `CapabilityExecutorWorker` → `AdapterRuntime` → `model_router`.

| Distinction | Where it lives | Evidence |
|---|---|---|
| Capability **discovery** | `planner.py`'s `discover_capabilities()` | Ranks candidates by relevance; K4.2-H2-D3 (`ADR-K4.2-H-03`) added a tie-break key confirmed this session to affect *only* exact-score ties within ranking — re-read the actual diff, does not touch selection |
| Capability **selection** | **Does not exist in code anywhere** | `compiler.py`'s own docstring, quoted exactly: "Resolving `capability_type` to a concrete registered `WorkerRegistry` [entry]... reserved exclusively for the future [Cognitive Runtime/C-MoE]" |
| Adapter selection | `AdapterRuntime._rank_adapters()` | Operates only within one already-given `capability_type` (`invoke(self, capability_type: str, ...)` signature, confirmed) |
| Model selection | `model_router.py`'s `_maybe_promote`/`_maybe_rollback` | One layer below Adapter selection, confirmed independent |

**`WorkflowNode.worker_type: str = ""`** (confirmed field, `core/workflow/definition.py`) is set by `compiler.py`'s `_compile_step()` to `step.capability_type`, **unchanged** — confirmed at the exact line (`worker_type=step.capability_type`), with the function's own docstring stating plainly that no lookup against `WorkerRegistry` happens at compile time and that "at that point `worker_type` may need to become the resolved adapter identity" is future work, not current behavior.

`CapabilityExecutorWorker.worker_type = CapabilityType.LLM_COMPLETION` (confirmed, a **hardcoded class attribute**, not a dynamic dispatch table) — sharper than CMS's own framing: this bridge does not merely "not yet select," it is **structurally incapable of selecting**, since it can only ever resolve to the one literal value it's hardcoded to. Its own docstring confirms this is deliberate: "If a second capability_type is ever registered, this worker does not automatically cover it... Extending to more capabilities... is future work." **This is the single concrete point where C-MoE's first implementation packet will need to intervene** — not "add a selection layer somewhere in the pipeline" in the abstract, but specifically "replace this hardcoded `worker_type` with real dispatch."

**No violation of the ownership hierarchy found anywhere in this trace.** `C-MoE → CapabilityExecutorWorker → AdapterRuntime → model_router` is confirmed as CMS described it, with the caveat that the first arrow doesn't exist yet (correctly — nothing should be there before C-MoE is built).

---

## 5. Work Unit State Machine

**[FACT] No canonical state-machine definition exists in the repository today.** `WorkflowNode` (confirmed, `core/workflow/definition.py`) carries no state-enum field of its own; whatever ad hoc state tracking exists lives in `WorkflowRuntime`'s local dict (the same DEBT-003 volatility RS documents). CMS §D.3 is the only place either dimension is written down, and it is a **recommendation**, not a ratified contract:

- **Cognitive/routing axis** (CMS, would be C-MoE-owned): `READY → ROUTING → RUNNING → VERIFYING → {COMPLETED | NeedReplan | ...}`.
- **Durability/recovery axis** (RS Diagram 4, would be `WorkflowRuntime`/future-durability-layer-owned): `READY → RUNNING → {COMPLETED | FAILED | RETRYING}`, plus proposed `RECOVERY_REQUIRED → {RESUMING | RECONCILING}`, `FAILED → ABANDONED`.

**This audit confirms CMS's own finding stands: these were independently sketched by two different source documents (RS itself, and separately AED's cooperative-execution sketch, which CMS cites) with no existing text stating they are two axes of one object rather than one merged enum.** Re-checked against RS's Diagram 4 and AED's text directly this session (not re-derived, but re-confirmed neither source claims orthogonality). **Merging them into one flat enum "for convenience" is exactly what the directive's Section 5 forbids, and this audit agrees with that instruction on the merits**: a Work Unit mid-`ROUTING` when a crash occurs is a materially different resume case from one mid-final-`RUNNING`, and only the cognitive axis's existence tells a recovering process which case it's in.

**Classification: REQUIRED_POST_FREEZE, not blocking.** Nothing implements either axis today, so there is no live inconsistency to close before freeze — only a specification that should be written as a single ADR (already anticipated by RS's own Q.8) before either axis is implemented, so the two are designed together rather than reconciled after the fact.

---

## 6. C-MoE Freeze Boundary

**Verified against CMS's own Final Classification table (re-read in full this session) and this audit's own Section 2 matrix: every item the directive's Section 6 lists as required-to-stay-open is, in fact, still open, with no drift toward accidental over-specification.**

| Required to stay open | CMS's own classification | Confirmed still open? |
|---|---|---|
| Soft-signal routing algorithm | Explicitly not frozen, CMS §D.2 | Yes |
| Complexity scoring | ADVANCED C-MOE (estimator); the *signal* — candidate count post-filter — is the only frozen part, and it's a byproduct of existing discovery, not a new scoring system | Yes |
| Assurance aggregation formula | FUTURE RESEARCH, matches RS's own prior classification exactly (Deferred Research item 4) | Yes |
| Routing-learning algorithm | IMPORTANT POST-FREEZE (the *gate*, i.e. Verification+Governance required), algorithm itself untouched | Yes |
| Expert independence scoring | IMPORTANT POST-FREEZE (the *property*), scoring method unspecified | Yes |
| Advanced parallel/redundancy strategies | IMPORTANT POST-FREEZE at most | Yes |
| Sophisticated Think Harder policies | The *gate* (marginal-value check) is specified; the estimator is ADVANCED C-MOE | Yes |
| Cognitive Organization machinery | **NOT REQUIRED**, CMS §H | Yes — actively rejected, not merely deferred |
| Virtual Worker runtime entities | **NOT REQUIRED** as a heavyweight entity, CMS §G | Yes — actively rejected; metadata alternative is ADVANCED C-MOE |
| Distributed C-MoE | FUTURE RESEARCH, explicitly deferred per RS §O and CMS's own directive boundary alike | Yes |
| K5 Self-Model integration | FUTURE RESEARCH, gated on K5 unfreezing — CMS's own Orientation Note flags this as the one place it deliberately under-delivered relative to what its directive asked | Yes, and correctly so |

**No item has accidentally become an undocumented implementation expectation.** This audit finds CMS's own self-classification accurate on every count checked.

---

## 7. Reliability Integration

**[FACT] `EventStream` (`core/events/event_stream.py`) is confirmed as the only durability primitive either study proposes building on — neither RS nor CMS introduces a second one, re-checked directly against both documents' full text this session, not sampled.** RS's `create_checkpoint()`/`get_checkpoint()` (exists, unused by `WorkflowRuntime`) is the mechanism RS-1 extends; CMS-2's `cognitive.routing_decided` event-type family is explicitly additive to that same schema, not a parallel store — CMS's own words, re-confirmed: "no second durability mechanism."

**Does the architecture already provide an event contract for `cognitive.routing_decided`?** **No — confirmed by fresh grep this session: no such event type, or anything resembling it, exists anywhere in the codebase.** This is expected (C-MoE doesn't exist) and is exactly RS-1/CMS-2's combined pre-freeze item — the contract (candidate set, selected expert(s), eliminated candidates, decision evidence, escalation state, remaining budget, assurance state, resource assumptions, provenance — CMS §T/§X's own list, all still correctly unimplemented) needs to be specified in the same ADR as RS-1, not built yet.

**Recursive execution / `RecursionGovernor` / recovery budgets / concurrency limits:** all re-confirmed in Section 1.2 (DEBT-013) and Section 2 (RS-6) — `RecursionGovernor` is correct-but-dormant, `OperationRecoveryBudget` (`core/cognitive/recovery.py`, H1, frozen) is real and is CMS's own confirmed generalization seed for Think Harder, `AdaptiveSemaphore` (RS §A.4, not independently re-verified this session — L2) is the concurrency-limit precedent both studies rely on.

---

## 8. Verification Boundary

**[FACT] Neither a Verification Runtime nor a Reflection Runtime exists as code anywhere in this repository, confirmed by a fresh, repository-wide class-name search this session (`class Verif*`, `class.*VerificationRuntime`, `class.*ReflectionRuntime` — zero hits, distinct from `EvaluatorWorker`/`ReflectionWorker`, which are K4.2's existing, different-purpose workers, and from `tests/phase2_verification.py`, a test-process artifact unrelated to a Verification subsystem).**

Given nothing is built, "verify Execution ≠ Verification remains independently governed" reduces to an architecture-level check, not a code-level one: **AED states this independence directly and unconditionally** ("Execution never completes a Work Unit. Verification completes a Work Unit... Verification remains independent from execution"), and CMS §Q adds the one refinement this audit re-confirms is sound — a future Verification-internal expert-selection budget must be structurally separate from the Work Unit's own (CMS-5 in Section 2, correctly classified moot-until-built, correctly still specified now). **No contradiction found between AED and CMS on this point; nothing to reconcile.**

---

## 9. Governance / Safety Audit

Each required precedence check, verified against both studies and against code where code exists to check:

| Rule | Status |
|---|---|
| Resource scarcity changes strategy, not correctness requirements | **[FACT] Already `PROJECT_INSTRUCTIONS.md` §4** ("if performance conflicts with governance or replayability, governance wins") — CMS §E inherits this rather than inventing a parallel rule, re-confirmed by direct comparison of CMS's text against §4's exact wording this session. Holds. |
| Urgency cannot reduce mandatory correctness | Same §4 precedence; CMS §E/§N apply it identically to deadlines. Holds. |
| Priority cannot bypass Governance | CMS §N: priority affects allocation only, never acceptance/verification/Governance. No code exists yet to violate this (no priority mechanism is implemented — confirmed, `KNOWN_ISSUES.md`'s own Deliberately Deferred table has no scheduler entry). Holds, vacuously and by design. |
| Think Harder cannot bypass verification | CMS §L's explicit MUST-NOT list, enforced structurally via the same escalation gate as any other path (CMS §F) — not a separate, exemptable mechanism. Holds. |
| Additional experts require bounded justification | CMS §F's marginal-value gate + `OperationRecoveryBudget` generalization (real, frozen, confirmed this session at `core/cognitive/recovery.py`). Holds. |
| Redundancy cannot bypass idempotency | CMS §J explicitly reuses RS §I's idempotency-key model rather than proposing a redundancy-specific exemption. No consequential Adapter exists yet to test this against (Section 2, RS-3). Holds, currently vacuous. |
| Learning cannot directly become executable logic | **[FACT]** AED states this directly and unconditionally ("Learning occurs ONLY when BOTH... Verification Approved, Governance Approved"); matches this project's own standing principle independently. `core/cognitive/learning.py`'s `ContentDomain`/`LearningCandidate` machinery (existing code, confirmed) stores candidates as governed evidence, not executable code — consistent, re-confirmed by the class's own field shape (no execution hook found). Holds. |

**Zero violations found, in either architecture or code, across all seven checks.** This is the one section of this audit with a fully clean result on every sub-item — worth stating plainly rather than burying in a table, since a genuinely clean governance audit is itself a meaningful data point for the freeze verdict.

---

## 10. Legacy and Transition Debt

Repository-wide sweep this session (legacy/deprecated/shim/TODO/FIXME markers across `core/`, plus targeted checks) — findings classified per the directive's own five categories.

| Finding | Evidence | Classification |
|---|---|---|
| **`WorkerContext`/`ExecutionContext` compatibility shim** (headline finding, this audit — see also DEBT-016, Section 1.2) | `core/runtime/execution_context.py`'s `to_worker_context()`, `query` property, and `recursion_depth` property are each explicitly commented "Compatibility shim — will be removed after K2.4." K2.4 (Governance) completed long before K4.2. Every current worker (`PlannerWorker`, `CapabilityExecutorWorker`, `EvaluatorWorker`, `ReflectionWorker`, `SupervisorWorker`, `MemoryCuratorWorker`) still implements against `WorkerContext`, confirmed by direct grep. The mechanism itself is safe — `ExecutionRuntime.invoke()` constructs `ExecutionContext` fresh, then calls `.to_worker_context()` fresh on every call (confirmed, `execution_runtime.py:160,191`); there is no independent mutation path, so no Single-Source-of-Truth *data* risk exists despite the *code* duplication. | **Keep intentionally, for now** (removing it means migrating six worker classes' signatures — real implementation work, out of this audit's scope per Section 16) — **but see Section 11 for why ADR-001 itself needs a decision regardless of whether the shim is removed.** |
| Legacy K2.2 `PlannerWorker` path vs. K4.2 path | `CURRENT_STATE.md`, re-read this session: "Legacy K2.2 `PlannerWorker` path is byte-for-byte unchanged and remains the default," feature-flagged (`[runtime] use_k42_frontend`, default `false`) | **Keep intentionally** — explicitly documented, deliberate, reversible dual-path architecture, not accidental legacy. Not debt. |
| `OCBRAIN_FUTURE_ARCHITECTURE.md` duplicated at root and `docs/archive/research/` | Confirmed byte-identical via `md5sum` this session | **Documentation-only legacy** — recommend converting the root copy to the same redirect-stub pattern already used for `PROJECT_INSTRUCTIONS.md`/`ARCHITECTURE_CHANGELOG.md` |
| Root-level `PROJECT_INSTRUCTIONS.md` (129 B) / `ARCHITECTURE_CHANGELOG.md` (133 B) stubs | Already resolved per `KNOWN_ISSUES.md`'s own July 22 entry ("resolved via a redirect stub") | **Already unreachable as a problem** — re-confirmed working as designed, not reopened |
| `docs/archive/research/OCBRAIN_EXTERNAL_REPO_STUDY.md`/`V2`/`V3` filed under `/archive` despite `PROJECT_INSTRUCTIONS.md` §1.1 describing them as "permanent architectural references" | Location vs. status tension, first flagged by CMS's own Methodology section, re-confirmed here | **Documentation-only** — either the location or the "permanent reference" framing is stale; not a code risk either way. Recommend a one-line note in `PROJECT_INDEX.md` clarifying which governs. |
| Stale D3/D12-"reverted" language in both RS's and CMS's own Orientation Notes | Section 1.3, re-confirmed | **Documentation-only**, zero substantive impact on either study, recommend a one-line addendum to each |
| `core/web/search.py`'s `# TODO: Implement actual DuckDuckGo search` | Confirmed present, but consistent with — not contradicting — `KNOWN_ISSUES.md`'s own "Future Capability Types" table (`web_search`: "Declared, no adapter") | **Already tracked correctly elsewhere; not new debt.** Sweep confirms consistency, not a gap. |

**No transitional adapters, obsolete worker routes, or deprecated state models beyond the above were found.** The repository-wide `deprecated`/`legacy` sweep's remaining hits (`core/cognitive/learning.py`, `core/workers/curator.py`, `core/memory/*`) are confirmed to be a **domain concept** — `KnowledgeEntry.truth_status = "deprecated"`, marking superseded facts for provenance, per its own docstring ("Superseded; retained for provenance only") — not code debt. Verified this session to avoid a false-positive sweep result; these are working as intended.

---

## 11. ADR / Authority Audit

**One genuine conflict found — this audit's second freeze blocker.** Everything else checked out.

### 11.1 The conflict: embedded ADR-001 vs. current code

| | Content |
|---|---|
| **Concept** | Which object is the canonical, worker-facing execution parameter — `ExecutionContext` or `WorkerContext`? |
| **Authority A** | `KERNEL_ARCHITECTURE_v1.0.md` §21, embedded **ADR-001**, frozen with the architecture spec: *"`ExecutionContext` is the canonical execution parameter object. `WorkerContext` is deprecated... Zero live consumers break — `MemoryCuratorWorker` is never instantiated in production."* |
| **Authority B (= actual code)** | `AbstractCognitiveWorker.execute(self, context: WorkerContext)` / `_run(self, context: WorkerContext)` (`core/workers/base.py`) is the live template method every worker subclass implements against. Confirmed this session: `PlannerWorker`, `CapabilityExecutorWorker`, `EvaluatorWorker`, `ReflectionWorker`, `SupervisorWorker`, `MemoryCuratorWorker` all take `WorkerContext`, not `ExecutionContext`, directly — and several of these (`PlannerWorker` via the legacy K2.2 path; `CapabilityExecutorWorker` via K4.2, live behind a flag) have very much been "live consumers" for a long time. ADR-001's specific factual premise was true when written; it has not been true since workers with real production paths existed. |
| **Actual implementation** | A working, self-aware, explicitly-labeled "compatibility shim" (`ExecutionContext.to_worker_context()`) bridges the two on every single worker invocation — confirmed one-way, freshly derived each call, no data-integrity risk (Section 10). |
| **Required resolution** | Two viable paths, genuinely tied on evidence, both requiring a decision this audit does not make: **(a)** Update ADR-001's embedded text to reflect the current, working two-layer reality (`ExecutionContext` = Runtime-boundary canonical object; `WorkerContext` = Worker-boundary derived view, intentionally, permanently) — cheapest, zero code risk, but means embedded ADR-001 was simply wrong about "deprecated" and should say so plainly rather than leave a frozen, inaccurate premise sitting in the spec. **(b)** Actually complete the migration ADR-001 called for — six worker classes' method signatures change from `WorkerContext` to `ExecutionContext`, the shim retires — real implementation work, correctly out of scope for this audit (Section 16), but the *decision to schedule it* is not. |

**This audit does not choose between (a) and (b).** Per this project's own instruction ("for every conflict provide... required resolution. Do not silently choose one"), both are laid out with their tradeoffs; Moncif's call is the second item in the minimum blocking closure set.

### 11.2 Everything else checked — no further conflicts found

- `KERNEL_ARCHITECTURE_v1.0.md` §23's roadmap vs. `IMPLEMENTATION_ROADMAP.md`: **not a conflict** — `IMPLEMENTATION_ROADMAP.md` states its own relationship to the frozen §23 explicitly ("the roadmap in `KERNEL_ARCHITECTURE_v1.0.md` §23 is frozen and reflects the plan as it existed at architecture freeze; this document reflects actual completion") — a documented, intentional distinction between a frozen historical plan and a living completion record, re-confirmed by direct reading this session. No resolution needed; already self-resolved.
- `IMPLEMENTATION_TRACKER.md`'s prior "does not exist" false claims (two independent prior sessions): **already resolved**, per `KNOWN_ISSUES.md`'s own Aug 22 entry and `ADR-K4.2-H-12` — re-verified as correctly closed, not reopened by this audit.
- DEBT-009 (Constitution law-count / Resource Model discrepancy, July 22): **already resolved and re-confirmed** in Section 1.1 — no new evidence surfaced this session suggesting it needs reopening.
- No case was found this session of an implementation document silently overriding a Constitutional rule, or a future document (K5, `FUTURE_RESEARCH_VAULT.md`) being treated as a v1.0 specification anywhere in `CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`, or either prior study.
- `PROJECT_INDEX.md`'s document-hierarchy table (re-read in full this session): accurately reflects priority order 1–10; does not list RS/CMS at all (Section 1.3) — a completeness gap, not a contradiction of anything the table does state.

---

## 12. Implementation Readiness Matrix

| Area | Contract Frozen? | Implementation Complete? | Tests/Evidence | Remaining Debt | Freeze Impact |
|---|---|---|---|---|---|
| K4.2 Front-End | **Yes** — H1 (16-gate review + sign-off, Aug 17), H2 (Aug 22) | **Yes** | 1214 passed / 34 pre-existing-identical failed, zero regressions across H2 | DEBT-002, DEBT-011 (tracked, non-blocking) | **None — ready** |
| Workflow Graph | Partial — DAG execution stable; no formal state machine | Yes for current DAG scope; No for durability | Existing workflow tests pass | DEBT-003; Section 5's dual-axis state machine | REQUIRED_POST_FREEZE |
| Capability Boundary | **Yes** — `CapabilityMatch`/`CapabilityDiscoveryResult` frozen H1 | **Yes** | D3's 9-test acceptance suite + existing suite | None significant | **None — ready, cleanest area audited** |
| C-MoE Boundary | No — CMS's shape not yet ADR-ratified | No, by design (confirmed 0 code) | N/A | CMS's 7 items (Section 2) | REQUIRED_POST_FREEZE — before any C-MoE implementation packet, not before this freeze |
| Execution Runtime | Yes, with one live conflict | Yes | Existing suite | **ADR-001 vs. `WorkerContext` (blocker #2)** | **BLOCKING** |
| Verification | No — subsystem doesn't exist; independence specified at architecture level only | No | N/A | CMS-5 (budget separation contract) | REQUIRED_POST_FREEZE, not blocking (nothing built) |
| Reflection | Partial — `ReflectionWorker` (K4.2) exists and is tested; future Reflection Runtime doesn't | `ReflectionWorker` yes; Reflection Runtime no | `ReflectionWorker` tested | None blocking | None |
| Governance | Yes — 7 governors, `GovernanceKernel` | Yes, all active (2 dormant-but-fail-closed: Recursion, Budget) | Existing suite + this audit's clean 7-check sweep (Section 9) | DEBT-002/007/013 | REQUIRED_POST_FREEZE to wire; dormant-but-safe accepted as a valid interim state per RS-6 |
| Durability | No — RS-1 not yet ADR'd | No (DEBT-003) | DEBT-008 (no dedicated `EventStream` coverage) | DEBT-003, DEBT-008, RS-1/CMS-2 | REQUIRED_POST_FREEZE — long-tracked, not newly blocking |
| Recovery | Specified in RS's disposition tree; not ADR'd | No | N/A | RS-8/RS-9 | REQUIRED_POST_FREEZE |
| Identity | Partial — `operation_id`/`trace_id` frozen H1 for the cognitive path; two families confirmed disconnected at the `compile()`→`WorkflowRuntime` boundary (Section 3) | Partial | Existing H1 tests for the frozen half | RS-2, RS-4 | **BLOCKING (blocker #1)** |
| Concurrency | No — depends on Identity/Scope resolution | No (no scheduler exists, confirmed) | N/A | Transitively blocked by Identity | Blocked via blocker #1; not an independent blocker |
| Learning | Partial — AED's Verification+Governance gate frozen conceptually; `ContentDomain` reconciliation open | Yes for what exists | Existing suite | DEBT-011 (already gates K4.2.6+ independent of this audit) | REQUIRED_POST_FREEZE |
| Legacy Transition | N/A | `WorkerContext` shim confirmed safe-but-unretired | This audit's Section 10 sweep | DEBT-016 | Tied to blocker #2's decision |

---

## 13. Minimum Blocking Closure Set

**Exactly two items. Both are decisions, fully specified, requiring no further research or implementation to close — only Moncif's call.** Deliberately not inflated with the sixteen REQUIRED_POST_FREEZE items above, each of which is real, tracked, and correctly sequenced *after* freeze rather than before it, per the directive's own instruction against inflating this list.

1. **Scope/Session/identity-family decision** (Sections 2 [RS-4/RS-2], 3, 12 [Identity row]). Close by: an ADR recording (a) what Scope means for Kernel v1.0 — RS's own proposed reading (kernel-owned Resource, execution-isolation boundary, explicitly not "conversation") or an alternative, and (b) whether `WorkflowNode`/`WorkflowDefinition` should carry a link back to `operation_id`, now that this audit has confirmed with direct evidence that they currently do not.
2. **ADR-001 vs. current `WorkerContext` reality** (Section 11.1). Close by: an ADR choosing between updating ADR-001's text to match the working two-layer reality, or scheduling the six-worker migration ADR-001 originally called for.

**Everything else in this document — all sixteen RS/CMS Critical Pre-Freeze items (Section 2), the Legacy/Transition findings (Section 10), the documentation-only notes (Section 1.3) — is real, correctly classified, and does not block Kernel v1.0 freeze itself.**

---

## Post-Freeze Roadmap

### REQUIRED_POST_FREEZE (needed before the *next* implementation phase begins, not before freeze)

- Ratify RS's 9 + CMS's 7 items via ADR (Section 2) — recommend two combined ADRs (one RS-durability-scoped, one CMS-shape-scoped) rather than sixteen separate documents.
- Wire `RecursionGovernor`/`BudgetGovernor` accumulation, or formally accept RS-6's "document why dormant is fine" alternative (DEBT-007, DEBT-013).
- `os.execv()` active-mission protection + Governance routing (DEBT-015, RS-8/RS-9).
- Work Unit dual-axis state machine ADR (Section 5).
- `WorkerContext` migration, if blocker #2 resolves toward option (b) (Section 11.1).
- KNOWN_ISSUES.md additions: DEBT-013 through DEBT-016 (this audit recommends; does not self-edit the file, per established practice — Section 1.2).
- PROJECT_INDEX.md: add `future_debt_study/` to the directory tree; `OCBRAIN_FUTURE_ARCHITECTURE.md` root-copy redirect stub (Section 1.3, Section 10).
- One-line addenda to RS's and CMS's own Orientation Notes correcting the now-stale D3/D12 revert language (Section 1.3).
- DEBT-011's K4.1-L reconciliation pass — already scheduled independent of this audit, re-confirmed still open.

### ADVANCED_CMOE

- Work Graph subtree metadata as the Virtual-Worker substitute (CMS §G).
- Soft-signal scoring algorithm; marginal-cognitive-value estimator (CMS §D.2, §L).

### FUTURE_RESEARCH

- Full multidimensional Assurance aggregation (RS Deferred Research 4 / CMS §K, unchanged by either later document).
- Distributed/multi-node C-MoE (RS §O / CMS §M, §Z).
- K5 Self-Model integration (CMS §P) — gated on K5 unfreezing, not a Kernel-v1.0-era question.
- Cognitive Organization as a distinct concept (CMS §H) — gated on real multi-specialist-mission evidence, not scheduled.

---

## Final Verdict

# NOT_FREEZE_READY

**Minimum blocking closure set: 2 items (Section 13), both decisions, both fully specified, neither requiring new research or implementation.** K4.2 itself — frozen (H1) and complete (H2), tested, zero regressions, two independent studies concluding "no stop" — is in excellent shape and is not what is holding this verdict back. What is: one Kernel-Constitution-adjacent identity decision (RS's own #4, deliberately left to Moncif by RS, CMS, and this audit alike) and one newly-found, narrow authority conflict between a frozen embedded ADR and the code that has existed since before H1. Close both, and this audit's own assessment is that Kernel v1.0 is ready — the sixteen Critical Pre-Freeze items from RS and CMS are real but are gates on the *next* phase of work, not on the freeze itself, and this document's own Section 16 constraint against inflating the blocking list is taken seriously rather than nominally: this verdict reflects the smallest genuine blocking set this audit could find, not the largest plausible one.

---

*End of audit. Per the governing directive: reconcile, verify, close, classify — not research further. No production code was modified in this session; the audit's own single directly-relevant discovery (the disconnected `operation_id`/`trace_id` vs. `WorkflowNode` identifier families, Section 3.2) was a verification read, not a change.*

---

## Addendum (August 23, 2026) — D10 (drift-enforcement) verification

Flagged post-hoc: a fifth H2-track packet, `K4.2-H2-D10` ("full architecture drift enforcement," `DRIFT-10..15`, branch `h2/d10-drift-enforcement`), was in progress on its own branch throughout this audit and the preceding CMS session, authored by a separate parallel session, and was **not merged into `main`** at the time either document was written — nor is it merged as of this addendum. This is distinct from the pre-H2 `DRIFT-01..09` baseline (`scripts/check_drift.py`, landed Aug 18, `f070a7c`), which *was* on `main` throughout and which this audit did not separately exercise or cite.

**Checked directly rather than assumed:** D10's own six new checks (governance-boundary scope, frozen entrypoints, recovery authority, architecture-marker disappearance, multi-site canonical construction, forbidden diagnostic transport) address structural invariants unrelated to either of this audit's two blockers. Running D10's full `DRIFT-01..15` checker against current `main` (HEAD `2d77b94`, correctly, from its proper location after an initial attempt from a copied-out path gave a false-positive `DRIFT-13` violation via broken `__file__`-relative path resolution — caught and corrected before relying on it) returns **15/15 PASS, zero violations**, matching D10's own reported result against the same fully-integrated base. **No change to this audit's verdict, blocking set, or any finding.**

One forward-looking note, not a blocker: once D10 merges, the test count this audit cites (1214 passed / 34 failed) becomes 1230/34 (D10 adds 16 passing tests, same 34 pre-existing failures) — a heads-up for whoever next reads this document against a newer `main`, not a correction to what was accurate at audit time.
