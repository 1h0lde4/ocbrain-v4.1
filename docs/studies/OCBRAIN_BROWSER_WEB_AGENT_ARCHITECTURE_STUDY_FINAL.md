# OCBrain — Browser / Web Agent Subsystem: Final Reconciled Architecture Study

```
Status:              PROPOSAL — NOT AUTHORITATIVE
Repository basis:    1h0lde4/ocbrain-v4.1 @ 79c84d5
                      (re-checked against 25ad85b before push prep -- see Part 0.5)
Implementation:      NOT STARTED
Scheduling:          NOT SCHEDULED
Current priority:    Kernel v1.0 / Verification
Browser:              FUTURE MILESTONE
User Behavioral Learning Extension:
                        SEPARATE LATER STUDY
Supersedes:           v1 (research/contract detail, still referenced) and v2 (hardening pass, corrections carried forward and in one case reversed — see Correction Ledger #9-11 and Part 0.5)
```

> **Architecture approved ≠ implementation prerequisites satisfied ≠ implementation scheduled.** These are three separate determinations. This document makes the first one. The Dependency Gate (Part D) shows the second is mostly unmet today. Nobody has made the third, and nothing here should read as though they have.

---

# Part 0 — Correction Ledger

Two of these reverse something v1/v2 stated with more confidence than the evidence supported. Recorded in place, not silently fixed — matching this repository's own convention (`CURRENT_STATE.md`'s ADR-KERNEL-01 entry: "corrected there in place, struck through, not deleted").

| # | Item | v1/v2 said | Re-verified finding | Evidence class |
|---|---|---|---|---|
| 1 | Cancellation | (v2, correctly) three mechanisms coexist | Reaffirmed, unchanged | `VERIFIED_IN_CODE` |
| 2 | `ESCALATE`/HITL | (v2, correctly) fails closed, no resume path | Reaffirmed, unchanged | `VERIFIED_IN_CODE` |
| 3 | No second planner | (v2, correctly) grounded in `planner.py`/`compiler.py` docstrings | Reaffirmed, unchanged | `VERIFIED_IN_CODE` |
| 4 | Browser Execution Kernel wording | v1 said the repo "already has a suitable equivalent abstraction" | Reworded per this session's own instruction: `AbstractCognitiveWorker` is not itself a Browser Execution Kernel — it supplies the execution-layer mechanisms a dedicated one would otherwise duplicate. The conclusion (no separate kernel) is unchanged; the framing was imprecise. | `VERIFIED_IN_CODE` for the mechanisms; the "kernel" framing itself was `INFERRED`, now corrected |
| 5 | Odysseys, "44.5%" | Not previously cited at this precision | Verified directly against the paper (arXiv:2604.24964) and independently corroborated (a literature-review summary, and the lead author's own announcement thread): the strongest tested model, Opus 4.6, scored 44.5% task-perfect on Odysseys' original evaluation harness; GPT-5.4 scored 33.5%. Separately, the public Odysseys leaderboard's current top entry (browser-use, 87.4%) is a **later, third-party submission using a different harness**, not a contradiction of the paper's own number — different measurement, not different reality. | `VERIFIED_IN_AUTHORITATIVE_DOC` (arXiv abstract + author statement) |
| 6 | "Chrome's published agentic-browser security architecture... a separate user-alignment critic" | This session's own prompt attributed this to "Chrome's" architecture generally | **Correction:** the user-alignment-critic architecture (a separate model, isolated from untrusted content, seeing only action metadata, vetoing misaligned actions; plus extended origin-isolation scoping) is **Google's own native Chrome agentic-browsing feature, powered by Gemini** (security.googleblog.com, Dec 2025) — a different system from **Anthropic's Claude for Chrome**, which is a third-party extension with its own separate architecture (site blocklists, high-risk-site blocks, user confirmations, safety classifiers; the ShadowPrompt and cross-extension incidents cited in v1 §5 belong to *this* system, not Google's). Both are real and both are useful precedent, but conflating them would misattribute specific mechanisms to the wrong product. Kept separate below (§19). | `VERIFIED_IN_AUTHORITATIVE_DOC` for both, now correctly attributed |
| 7 | "Chrome's... extension guidance... minimum permissions" | Presented alongside the above two | Correction: this is a **third, separate thing** — general Chrome Web Store extension-platform policy (applies to all extensions, not specific to any agent), long-standing and stable. Not re-verified via fresh search this session (treated as standing platform-policy knowledge, not a session finding) — flagged as such rather than presented with the same evidentiary weight as #6. | `INFERRED` (stable general knowledge, not freshly verified this session) |
| 8 | "No Resource types are implemented yet" (v1 §10, v2 §10) | Stated resource.py "mostly documents what's not implemented" | **Correction:** `core/capabilities/resource.py` does contain one real, implemented Resource: `HTTPClientResource` (`@dataclass`, identity/lifecycle/version/dependencies/trust/provenance fields per K1.6 §3's Resource Protocol), wrapping a shared `core.runtime.network.client` (`httpx.AsyncClient`) singleton. v1/v2's claim that resource types are purely declared-not-implemented was too broad — one exists, for network access specifically, which is directly relevant to Tier 1. | `VERIFIED_IN_CODE` |
| 9 | *(new finding, not a correction of a prior claim)* | — | `core/web/fetcher.py` — the module Tier 1 `BrowserWorker` would call — does **not** use `HTTPClientResource` or the shared `core.runtime.network.client`; it opens its own independent `aiohttp` session. `modules/web_search/module.py` (which wraps the Tier 1 web capability) does reference `runtime.network`. This is a genuine, previously-unflagged inconsistency at the network-client boundary — potentially a third instance of the "duplicated authority" pattern this project has already found twice (`DEBT-004` at the EventStream boundary, `DEBT-016` at the watchdog boundary), though I have not traced far enough to confirm `fetcher.py`'s separate session is accidental rather than a deliberate choice (it does things — custom retry/backoff, a spoofed User-Agent — the shared client's config doesn't obviously support). Classified `D` (common Kernel/shared-infrastructure question) below — flagged as a candidate `KNOWN_ISSUES.md` entry, not fixed here, not Browser's to resolve. | `VERIFIED_IN_CODE` for the split; `UNKNOWN` for whether it's a defect or a deliberate divergence |
| 10 | "The K4.4 standalone watchdog pair is the current best candidate" (v1 §7, v2 §7) | Stated with moderate confidence | **Softened per this session's explicit instruction, and per new evidence:** `KNOWN_ISSUES.md`'s DEBT-016 entry, in the portion read this session, is more serious than previously characterized — `docs/studies/OCBRAIN_KERNEL_COMPLETION_STUDY.md` names it a Kernel v1.0 **freeze-gate failure in its own right** ("the second confirmed instance of the same 'duplicated authority' pattern also found at the EventStream/KnowledgeEvent boundary"), not merely debt Browser happens to depend on. The K4.4 pair remains the better-documented precedent for future-worker integration (its own docstring says so directly), but which pair survives Kernel-level reconciliation is now explicitly Kernel's decision, on Kernel's timeline, not an assumption this document should lean on. | `VERIFIED_IN_AUTHORITATIVE_DOC` |
| 11 | MUZZLE, "37 attacks across 4 web applications" | Cited in v1/v2 | Reaffirmed via independent re-search this session — same paper (arXiv:2602.09222), same figure. Consistent both times. | `VERIFIED_IN_AUTHORITATIVE_DOC` |

---

# Part 0.5 — Addendum: Caught While Preparing to Push (Sept 8, before anything reached the remote)

Before pushing this branch, I re-fetched `origin/main` as routine practice and found it had moved 7 commits past this document's basis (`79c84d5` → `25ad85b`), including two ADRs that directly bear on claims above. Caught before any push, not after — recorded here rather than silently rewritten, per this project's own correction convention.

**ADR-KERNEL-02 (Sept 5, 2026) resolves DEBT-016.** Both watchdog implementations were kept, not merged — the two `ProgressMonitor`s genuinely serve different consumers — but a shared `watchdog_decision.py` now backs both, and the graph-aware watchdog (renamed `GraphExecutionWatchdog`, the one `WorkflowRuntime` actually uses) can now genuinely grant bounded extensions and cancel on a real stall, which it structurally could not do before. **This reverses Correction #10's lean.** A future `BrowserWorker` runs as a `WorkflowNode` inside `WorkflowRuntime` (§A.2's own conclusion) — meaning `GraphExecutionWatchdog`, not the K4.4 standalone pair pointed to in v1/v2, is now the watchdog a future Browser implementation would actually integrate with. The ADR also caught and fixed a real pre-existing bug: `WorkflowRuntime`'s default budget construction made `grant_extension()` structurally incapable of ever granting anything on the default execution path — the exact path Browser would run on — regardless of anything Browser itself would have done differently.

**ADR-KERNEL-03 (Sept 5, 2026) resolves DEBT-003** — workflow checkpoint/resume across a process restart, built on `EventStream`'s previously-unused checkpoint primitive. **This does not resolve the HITL gap** (Correction #2, Scenario F) — it's a different kind of resume (crash recovery via a known `instance_id`, invoked explicitly, not automatic) with no connection to `GovernanceVerdict.ESCALATE` anywhere in the ADR. Worth recording because it's now a real, tested, working primitive a future HITL mechanism could be built on top of, which wasn't true before.

**Sequencing note, flagged not resolved:** both ADRs state Verification/Critic/Evidence integration remains "post-freeze/post-C-MoE," with the Kernel freeze audit now "the next planned step." Prior context this study was working from had Verification ordered *before* C-MoE. Whether that's a genuine sequencing change or an imprecision in what this study had on record isn't resolved here — flagged rather than silently picked one way.

**Net effect on this document:** the Dependency Gate's Watchdog row (Part D) is updated below. Everything else in this study — the semantic/physical action split, the authority model, the invariant catalog, the Tier 1/Tier 2 boundary, the freeze recommendation itself — is unaffected. The freeze recommendation stands.

---

# Part 1 — Authority Hierarchy

Established directly from the documents' own stated precedence, not assumed:

```
OCBRAIN_KERNEL_CONSTITUTION.md
    Status: "Constitutional — Draft, not Final."
    "The highest-level architectural document in the project.
     It governs the FRAMING of PROJECT_INSTRUCTIONS.md and every
     architecture and research document beneath it. It supersedes
     none of them in substance."
        ↓ governs framing/principles, not engineering detail
docs/architecture/KERNEL_ARCHITECTURE_v1.0.md
    Status: "Frozen — Canonical engineering specification."
    "Second-highest document in the project hierarchy. The Kernel
     Constitution governs principles; this document governs engineering."
        ↓
docs/architecture/PROJECT_INSTRUCTIONS.md (v4.1, live)
    "Subordinate to the Kernel Constitution and KERNEL_ARCHITECTURE_v1.0.md.
     ...provides operational engineering rules."
```

**A second, orthogonal axis** — these are authoritative for *current factual state*, not for *what should be true*, and don't compete with the documents above:

```
CURRENT_STATE.md      "the authoritative answer to what is actually built right now"
IMPLEMENTATION_ROADMAP.md
KNOWN_ISSUES.md        "the canonical register of known technical debt, deferred items, and future work"
docs/architecture/decisions/ADR_INDEX.md + individual ADRs
                       authoritative for the specific decision each one records
```

**Where architecture studies (including this one) sit:** nowhere in either hierarchy above — no document I found ranks `docs/studies/*.md` or `docs/architecture/*_STUDY.md` at all. That's not an oversight I'm filling in; it's consistent with how this exact repository has repeatedly treated its own prior studies (e.g., the K4.3/C-MoE research phase: "research and architecture proposal only, not implemented, per this project's Architecture Freeze Principle"). Studies are inputs a future ADR or roadmap update may or may not adopt — they carry no authority on their own, including this one.

**Conflicting claims found this session:** none between this proposal and the two normative documents or the three factual-state documents. One internal tension worth naming: the Constitution — the *highest* document — is itself explicitly "Draft, not Final." This document doesn't attempt to resolve that; it's noted because a future reader shouldn't assume "highest in the hierarchy" means "settled."

**Resolution:** this study is written as subordinate to all five documents above, consults `CURRENT_STATE.md`/`KNOWN_ISSUES.md`/`IMPLEMENTATION_ROADMAP.md` for factual claims, and defers any principle-level question to the Constitution/Architecture pair rather than asserting its own.

---

# Part 2 — Evidence Classification (Key Claims)

| Claim | Class |
|---|---|
| `BrowserWorker` does not exist | `VERIFIED_IN_CODE` (zero grep hits, whole repo) |
| Tier 1 scope = "web browsing, content extraction" | `VERIFIED_IN_AUTHORITATIVE_DOC` (`KNOWN_ISSUES.md` + `IMPLEMENTATION_ROADMAP.md` agree) |
| `browser_automation` capability declared, not registered | `VERIFIED_IN_CODE` (enum member exists; `CapabilityRegistry` has no contract for it) |
| Cancellation has three coexisting mechanisms | `VERIFIED_IN_CODE` |
| `ESCALATE` has no resume path | `VERIFIED_IN_CODE` |
| No network-egress/SSRF policy exists | `VERIFIED_IN_CODE` (`core/governance/` grep, no match) |
| `core/web/fetcher.py` bypasses the shared network client | `VERIFIED_IN_CODE` |
| Verification not wired into any live path | `VERIFIED_IN_CODE` (only 2 references to `COMPLETED_WITH_PARTIAL_OUTPUT`, both in the enum's own definition/property) |
| DEBT-016 is a Kernel v1.0 freeze-gate concern, not just Browser-adjacent debt | `VERIFIED_IN_AUTHORITATIVE_DOC` |
| `BrowserSemanticAction`/`BrowserPhysicalAction` split | `PROPOSED` (this study, informed by real external precedent — BAP, ABP, CELLMATE — none of which are OCBrain code) |
| `NetworkEgressGovernor` | `PROPOSED` — explicitly not created, not registered |
| Odysseys 44.5% (Opus 4.6) | `VERIFIED_IN_AUTHORITATIVE_DOC` (external) |
| Which watchdog pair Browser should target | Was stated as near-`VERIFIED`; now `INFERRED`, pending Kernel-level DEBT-016 resolution (Correction #10) |

---

# Part 3 — Scope-Impact Classification (New Findings)

| Finding | Class | Rule applied |
|---|---|---|
| `fetcher.py`/shared-network-client split (Correction #9) | `D` — common Kernel/shared-infrastructure question | Not fixed by Browser work; flagged as a `KNOWN_ISSUES.md` candidate |
| DEBT-016 severity (Correction #10) | `D` | Browser consumes whichever watchdog Kernel reconciliation lands on; doesn't resolve the reconciliation |
| `HTTPClientResource` exists (Correction #8) | `A` — required for Browser architecture correctness | Changes what §46/§48 (session/resource governance) can honestly claim already exists |
| Google/Anthropic Chrome conflation (Correction #6) | `A` | Wrong attribution would misrepresent which mitigations belong to which system in the Threat Model (Part C, prior document) |
| `BrowserGovernor` vs `AgentGovernor` | `F` — future research/decision, explicitly left open | Per this session's own Open-Question Discipline |
| Runtime selection (Playwright vs. alternatives) | `C` — Tier 2 only | Doesn't affect Tier 1 or the architecture's correctness |
| DEBT-011 (`ContentDomain`/`LearningCandidate`), noted in Stage A | `E` — unrelated existing debt | Not Browser's to fix, not re-touched here |

---

# Part 4 — Tier Discipline and Gates

Unchanged in substance from v1/v2; restated precisely per this session's wording requirement.

**Tier 1** = `BrowserWorker`, HTTP-backed via `core/web/` + `core/web_learning/`. This is the *future worker boundary*, initially HTTP-only — **not** evidence that a browser runtime exists, and not permitted to silently acquire any Tier 2 requirement (DOM automation, screenshots, visual grounding, Playwright, authenticated profiles, multi-tab, page JavaScript, interactive forms) absent an explicit future roadmap decision.

**Tier 1 Implementation Gate** (HTTP browsing, extraction, trust/quarantine, governed execution, evidenced result):

| Prerequisite | State |
|---|---|
| Network egress enforcement | Missing — Correction #9 makes this slightly worse than previously stated, since even the shared client's own governance (via `HTTPClientResource`) isn't what Tier 1's code path would use |
| Governed worker execution | Present (`AbstractCognitiveWorker`) |
| Trust/quarantine | Present (`TrustManager`/`KnowledgeQuarantine`) |
| Evidenced result | Present as a hook (`WorkerResult.execution_detail`), unpopulated by convention today |

**Tier 2 Implementation Gate** (runtime, interactive actions, session mgmt, grounding, auth, side effects, HITL, advanced recovery, visual execution) — every row is currently missing; see Part D for the full table. A Tier 2 prerequisite does not block Tier 1 unless a concrete dependency is shown, and none is — the two gates are genuinely independent.

---

# Part 5 — Browser Execution Kernel (Reworded)

Per Correction #4: the accurate claim is not that `AbstractCognitiveWorker` *is* a Browser Execution Kernel, but that the execution-layer mechanisms a dedicated kernel would otherwise have to duplicate — structural governance enforcement, lifecycle state, cancellation plumbing, budget/progress integration, structured result reporting — already exist at the Worker/Kernel layer. Browser-specific concerns (state-epoch tracking, freshness validation, target re-grounding, DOM-mutation reconciliation) belong inside the future `BrowserWorker` and its bounded collaborators, not in a new sibling to `GovernanceKernel`/`ExecutionRuntime`. **No separate Browser Execution Kernel.**

---

# Part 6 — BrowserWorker Boundary

```
Tier 1: ExecutionContext → URL/query → network policy (missing today, D-class)
        → core/web/{fetcher,parser,cleaner} → TrustManager/KnowledgeQuarantine
        → WorkerResult/ExecutionOutcome

Tier 2: same worker boundary → runtime adapter (unselected) → BrowserSemanticAction
        compiled to BrowserPhysicalAction → observation loop → same result path
```

No second context object; browser parameters live in `ExecutionContext.metadata` only, following the `execution_budget` precedent (unchanged from v2).

---

# Part 7 — Contract Ownership Matrix

| Contract | Canonical owner | Producer | Consumer | Allowed extender | Lifecycle | Versioning |
|---|---|---|---|---|---|---|
| `BrowserExecutionContract`/context | This study (proposed) | `Supervisor`/Planner path via `ExecutionContext.metadata` | `BrowserWorker` | None else — single producer | Per-execution | Tied to `ExecutionContext`'s own versioning, not separate |
| `BrowserTask` | Compiler's `PlanStep`/`ExecutionPlan` (existing) | `core/cognitive/compiler.py` | `BrowserWorker` | Not Browser — Browser consumes, never redefines | Per-`WorkflowNode` | Existing `WorkflowDefinition` versioning |
| `BrowserObservation` | This study (proposed) | Runtime adapter (Tier 2, unselected) | `BrowserWorker` internal logic | `BrowserWorker` may extend fields; may not change `observation_id`/`state_epoch` semantics | Per-observation | Schema version needed if persisted past one execution |
| `BrowserSemanticAction` | This study (proposed) | `BrowserWorker`, compiled from `BrowserTask` | Runtime adapter (via `BrowserPhysicalAction`) | Nobody downstream — physical layer reads, never edits | Per-action | Must be schema-versioned if it ever crosses a persistence boundary (evidence, replay) |
| `BrowserPhysicalAction` | This study (proposed) | Runtime adapter | Runtime only | Runtime-specific, not shared | Ephemeral, per-dispatch | Runtime-internal, no cross-boundary version needed |
| `BrowserActionResult` | This study (proposed) | Runtime adapter | `BrowserWorker` → `WorkerResult.execution_detail` | `BrowserWorker` | Per-action | Rides on `ExecutionOutcome`'s existing versioning |
| `BrowserEvidence` | This study (proposed) | `BrowserWorker` | Future Verification | Verification only, once it exists | Per-execution, retained | Must match whatever schema Verification's Phase C branch settles on — **not decided here**, explicit dependency |
| `BrowserArtifact` | This study (proposed) | Runtime adapter (downloads, screenshots) | `BrowserWorker`, evidence pipeline | Artifact-trust classifier (not yet designed) | Ephemeral/operation/audit-retained per classification | Not needed until Tier 2 |
| `BrowserSideEffect` | This study (proposed) | `BrowserWorker` at dispatch time | Evidence, future Verification | Nobody | Per-action, retained with evidence | Same dependency as `BrowserEvidence` |
| `BrowserTrajectory` | This study (proposed) | Assembled from the above | Learning Gate (existing) | Learning Gate only | Post-execution | Must satisfy Learning Gate's existing promotion criteria — not a new gate |
| `BrowserCapability` | `CapabilityContract` (existing type, unregistered) | Would be C-MoE registration, if/when scheduled | C-MoE capability selection (doesn't exist yet) | Nobody — single canonical registry | N/A until registered | K2.3's existing precedent |
| `BrowserHealth` | This study (proposed) | `BrowserWorker`/runtime | C-MoE capability discovery | Nobody | Live/polled | N/A |
| `HumanInterventionRequest` | **No canonical owner exists yet** | N/A | N/A | N/A | N/A | Blocked entirely on a common HITL mechanism landing first (Part D) |

No object above is simultaneously a Planner contract, a Governance contract, a runtime contract, *and* a Verification contract — the closest thing to a shared object is `ExecutionContext` itself, which already has exactly one owner (the Kernel) and is extended, never re-purposed, by everything downstream of it.

---

# Part 8 — Authority Conservation, Revocation, and Freshness (Consolidated)

Carried forward from v2 with two additions this session's prompt correctly identified as missing.

**Authority Conservation** (unchanged): *a Browser execution, delegated worker, recovery path, runtime adapter, session, or human-approved continuation must never possess more authority than was explicitly granted by its parent execution and active policy context.*

**Authority Revocation** (new — v2 stated conservation but not revocation): *previously granted authority must become unusable when its grounding condition changes* — cancellation, `task_generation` change, authorization expiry, policy version change, session-identity change, human-approval expiry, or credential/session invalidation. No revoked or superseded authority may be reused. This is the dynamic complement to conservation: conservation bounds how much authority a thing can have at grant time; revocation bounds how long that grant stays good for.

**`policy_version` in authorization freshness** (new nuance): an action authorized under policy N must not execute under a materially different policy N+1 unless the architecture explicitly says the prior authorization survives the change. Concretely, `policy_version` joins `task_generation` and `state_epoch` as a third value revalidated immediately pre-dispatch (§A.6 of v2, now three-way rather than two-way).

**`authorization_scope`, precisely**: an inherited binding to authority the parent execution and active Governance context already granted — never authority Browser generates itself, never a text label, never an approximate match to a similar-looking prior authorization. Browser may validate it, attenuate it (narrow what it uses), and consume it. It may never mint, broaden, or reinterpret it into something more permissive.

**Recovery cannot be privilege escalation** (unchanged from v2): recovery may change strategy; it may never increase authority. A replan-triggered new action must not inherit the old `authorization_scope` unless `task_generation`, `policy_version`, and `state_epoch` are all still the ones the original grant was issued against.

**TOCTOU / freshness** (unchanged from v2, now explicitly three-dimensional): `task_generation`, `state_epoch`, `policy_version`, target identity, and effective network destination are all revalidated immediately before physical dispatch — not once at observation time.

---

# Part 9 — Observation, Evidence, and Negative Evidence

**Observation reconciliation** (sharpened): modality agreement (DOM + accessibility tree, say) can raise confidence; it is explicitly **not** authorization, not authority, and not proof of correctness. Disagreement forces re-observation and, for high-impact actions, escalation — never a pick-the-convenient-channel default (unchanged conclusion from v2 §A.8, now stated with the negative case made explicit per this session's instruction).

**Evidence freshness**: every evidence record ties to `execution_id`, `task_generation`, `state_epoch`, `policy_version`, and an observation timestamp — evidence gathered against a since-superseded task or state does not remain authoritative merely because the record itself wasn't deleted.

**Negative evidence** (new — not addressed in v1/v2): evidence must be able to establish that something *did not* happen, not only that something did — "the purchase was not completed," "the message was not sent." This matters specifically for `FAILED`/`CANCELLED`/`BLOCKED`/`OUTCOME_UNKNOWN` terminal states, where the absence of a positive confirmation is itself the fact that needs to be evidenced, not merely assumed from the absence of a success signal.

---

# Part 10 — Network Security (Updated)

Unchanged conclusion from v2 (`NetworkEgressGovernor` is a proposed Kernel-level capability, not Browser-owned, not created or registered here) — sharpened by Correction #9: the gap is worse than "no policy exists," because even the one piece of network-access infrastructure that *does* exist (`HTTPClientResource` / the shared `core.runtime.network.client`) isn't what Tier 1's actual code path (`core/web/fetcher.py`) would use. Whoever eventually builds the network-egress policy has two things to reconcile, not one: writing the policy, and deciding whether Tier 1 should be rerouted through the shared client so the policy has one enforcement point instead of two.

Distinguishing textual hostname from effective network destination, validating every redirect hop independently, and treating DNS rebinding as an in-scope attack class are unchanged from v2's threat table.

---

# Part 11 — HITL, Cancellation, Recovery, Idempotency (Consolidated)

- **HITL**: `GovernanceVerdict.ESCALATE` ≠ a pause/resume mechanism (Correction #2, reaffirmed). Future Browser HITL uses a common OCBrain mechanism once one exists; this document does not design one. Approval, when it exists, binds to execution + task + action + target + data scope + policy context + risk scope + time, and cannot transfer to a materially different action (unchanged from v2).
- **Cancellation**: three mechanisms coexist today (Correction #1); Browser uses the canonical `asyncio`/`ExecutionContext.cancellation_token` pair and introduces no Browser-specific cancellation token, stop flag, or subsystem.
- **Recovery**: `OperationRecoveryBudget` is the sole operation-level budget; Browser reuses it, never creates a second one (unchanged).
- **Idempotency** (new explicit classification, not in v1/v2): future Browser actions should be classified `safe_to_retry` / `idempotent` / `conditionally_idempotent` / `non_idempotent` / `unknown` at design time, not discovered by accident at retry time. For `unknown` or `non_idempotent` actions after a timeout or crash, the only correct move is external-state reconciliation before any retry decision — never a blind retry, and never treating timeout as proof of failure (`OUTCOME_UNKNOWN` remains a distinct terminal state from `FAILED`, unchanged from v2).

---

# Part 12 — Data Flow, Credentials, Runtime Privilege (Consolidated, unchanged from v2 §C.1–C.3)

Trust dimensions (source/content/identity/instruction-authority/evidence-confidence) stay separate, never collapsed into one score. Credentials (password/passkey/OTP/OAuth/session-cookie) are classified by LLM-visibility and mediator, matching `vercel-labs/agent-browser`'s "the LLM never sees passwords" precedent. Purpose-bound data use ("book delivery" ≠ "marketing signup") is a Tier 2 design note resting on `BrowserSemanticAction.authorization_scope`, not new infrastructure. None of this changed this session; restated for a standalone reader.

---

# Part 13 — Provenance, Learning, Memory Scope, Telemetry (Consolidated + one addition)

Tier 1 reuses `TrustManager`/`KnowledgeQuarantine` unchanged. Tier 2 needs field-level provenance and cross-origin trust-boundary tracking (unchanged from v2). The Learning Gate (successful AND verified AND policy-compliant) remains the sole promotion authority; no browser-trajectory learning path exists yet at all, so this is currently N/A by absence, not by defense. Memory scope (session/execution/task/account/domain/site/global) stays as specified in v1 — site-specific behavior never auto-promotes to global.

**Telemetry privacy** (new — not covered in v1/v2): future observability is itself a potential leak path. URLs, queries, page titles, filenames, account identifiers, and failure details can all be sensitive. What's logged, what's redacted, what's retained, and who can access it need explicit answers before Tier 2 telemetry is built — not assumed harmless because it's "just metadata."

---

# Part 14 — Session Isolation, Capability Negotiation (Consolidated + one clarification)

Session identity rides on existing `ExecutionContext.session_id`/`worker_id` — no parallel identity system (unchanged). Resource governance ties to existing execution-budget mechanisms, not a Browser-only budget subsystem (unchanged, and per Correction #8, `HTTPClientResource` is a concrete existing pattern for what a `BrowserSessionResource` would eventually look like, if one is ever justified — not decided here).

**Capability negotiation ≠ authorization** (new explicit statement): a runtime supporting capability X does not mean the current execution is authorized to use X, and an authenticated-session capability existing does not mean this task may authenticate. These are independent checks — one is "what can the runtime do," the other is "what is this execution allowed to do" — and collapsing them would let capability availability silently substitute for a governance decision.

---

# Part 15 — Evaluation and Security (Consolidated, with corrected attribution)

**Evaluation:** WebArena/WebArena-Verified/VisualWebArena/WorkArena(++)/AssistantBench/Online-Mind2Web/Odysseys/HORIZON — unchanged citation set from v1/v2, now with Odysseys' 44.5% precisely sourced (Correction #5) rather than gestured at. Long-horizon reliability is not extrapolated from short-benchmark success; efficiency (Odysseys' own Trajectory Efficiency metric, reported extremely low even for frontier models) is weighted alongside success rate, not treated as secondary.

**Security, correctly attributed (Correction #6):**

| System | Owner | Mechanism |
|---|---|---|
| Native Chrome agentic browsing | Google, Gemini-powered | Separate "user alignment critic" model (sees only action metadata, not raw web content; vetoes misaligned actions), extended origin-isolation scoped to task-relevant origins, user confirmations, real-time threat detection, red-teaming |
| Claude for Chrome | Anthropic, third-party extension | Site blocklists, high-risk-site blocks, user confirmations for high-risk actions, safety classifiers; real disclosed incidents (ShadowPrompt — subdomain-allowlist + third-party XSS chain; a cross-extension command-injection issue where the fix initially covered only "standard" mode) |
| Chrome extension platform policy | Google, general | Least-privilege permissions, optional permissions, no "just in case" broad grants — standing platform guidance, not a specific agent's architecture |

MUZZLE (37 attacks, 4 apps, cross-application prompt injection included) remains the concrete precedent for adaptive rather than fixed-string red-teaming, reaffirmed by independent re-search this session (Correction #11).

---

# Part 16 — End-to-End Scenario Trace

| Scenario | Traced path through this architecture | Gap found? |
|---|---|---|
| **A — Normal Tier 1 read** | Task → `BrowserWorker` → (missing) network policy → `fetcher`/`parser`/`cleaner` → `TrustManager`/`KnowledgeQuarantine` → `ExecutionOutcome` → (not-yet-live) Verification | Yes — network policy gap, already tracked (Correction #9, Part 10) |
| **B — Malicious web content** | Content observed → cannot enter `BrowserSemanticAction` (no code path exists from page text to a semantic action, by the two-object split) → remains data | No new gap — this is what the split is *for* |
| **C — Task mutation** | `task_generation` N → semantic action issued → upstream replan → generation N+1 → old semantic action's `task_generation` no longer matches → rejected pre-dispatch | No gap, contingent on the freshness check (Part 8) actually being implemented at Tier 2 — an implementation-phase risk, not an architecture gap |
| **D — Page mutation** | `state_epoch` N → physical action → page changes → epoch N+1 → physical action rejected, re-observation forced | Same caveat as C |
| **E — Uncertain external write** | Write dispatched → timeout → `OUTCOME_UNKNOWN` (not `FAILED`, not `SUCCESS`) → external-state reconciliation required before any retry → idempotency classification (Part 11) determines whether retry is even considered | No gap |
| **F — HITL** | `ESCALATE` → **stops here today** — no common pause/persist/resume mechanism exists (Correction #2) → this scenario cannot complete with current repository infrastructure | **Real gap — not Browser's to fix, but Browser cannot deliver full HITL until it exists.** Recorded in the Dependency Gate, not hidden. |
| **G — Cancellation** | Cancellation triggered → canonical `asyncio`/`cancellation_token` path (not the legacy `_cancelled` flag) → Browser activity terminates → no Browser-specific cancellation authority remains active | No gap, contingent on Tier 2 implementation actually using the canonical path rather than the legacy one — flagged as an implementation-phase risk given `MemoryCuratorWorker` shows the legacy path is still live enough to be checked by at least one real worker |
| **H — Recovery** | Failure → bounded recovery within `OperationRecoveryBudget` → authority unchanged (Part 8) → replan routes through upstream Planner/Supervisor when required, not Browser itself | No gap |
| **I — Learning** | Observation → extraction → provenance-tagged → evidence → (not-yet-live) Verification → Learning Gate → durable-knowledge candidate | Contingent on Verification landing — an explicit, already-tracked dependency, not a new gap |
| **J — Session/worker crash** | Worker dies → session lease/orphan handling (proposed, scoped by existing `ExecutionContext.session_id`/`worker_id`, not a new identity system) → cleanup → no uncontrolled browser activity survives | No gap at the architecture level; orphan-detection mechanics are unspecified Tier 2 implementation detail, correctly left open per this document's Open-Question Discipline |

Only Scenario F surfaces a genuine, currently-unresolvable gap — and it's a gap in OCBrain's common infrastructure (no HITL mechanism exists anywhere yet), not a gap in the Browser architecture's handling of HITL once one exists.

---

# Part 17 — Negative-Space Audit

| Area | Status |
|---|---|
| Identity | Delegated to existing `ExecutionContext.session_id`/`worker_id`/`execution_id` |
| Authority (grant) | Represented — Authority Conservation (Part 8) |
| Authority (revocation) | Represented — Authority Revocation (Part 8, new this session) |
| Freshness | Represented — three-dimensional (`task_generation`/`state_epoch`/`policy_version`) |
| Policy version | Represented — Part 8 |
| Data provenance | Delegated to existing `TrustManager`/`KnowledgeQuarantine` (Tier 1); extended conceptually for Tier 2 (Part 13) |
| Data egress | Represented as a future common dependency (`NetworkEgressGovernor`, Part 10) — explicitly not Browser-owned |
| Side effects | Represented (side-effect classification, idempotency classes, Part 11) |
| Cancellation | Delegated to existing canonical mechanisms (Part 11) |
| HITL | **Future common dependency — does not exist anywhere yet.** Represented as a dependency, not designed here |
| Recovery | Delegated to existing `OperationRecoveryBudget` |
| Verification | Future common dependency — architecture designed to be ready for it (rich `execution_detail` population), not to substitute for it |
| Learning | Delegated to existing Learning Gate |
| Session ownership | Represented, scoped by existing identity fields |
| Resource ownership | Partially represented — `HTTPClientResource` exists as precedent (Correction #8); whether a `BrowserSessionResource` should exist is explicitly `unknown`/open |
| Runtime containment | Out of scope — Tier 2, runtime-selection-dependent, correctly deferred |

No silent gaps found: every row is either represented, explicitly delegated, or explicitly named as a future dependency — none are simply absent without a label.

---

# Part 18 — Migration Stability, Tier 1 → Tier 2

Stable across the transition: the `BrowserWorker(AbstractCognitiveWorker)` boundary itself, `ExecutionContext` as the sole context object, the `task_generation`/`state_epoch`/`policy_version` freshness model, Authority Conservation/Revocation, and the semantic/physical action split (semantic actions don't change shape when the runtime behind physical actions changes). Tier-1-only: no `BrowserObservation`/`BrowserSemanticAction` distinction is needed for a plain fetch (there's no "physical action" below "make an HTTP request"). Tier-2-only additions: the full action taxonomy, session/auth state machines, visual/DOM grounding. The worker boundary does not move when the runtime does — that was the point of keeping runtime selection out of this document entirely.

---

# Part 19 — Final Documentation Integrity Check

Self-audit against this session's explicit list — confirmed clean:

- Does not claim `BrowserWorker` exists — every code block marked `PROPOSED`.
- Does not claim a browser runtime exists — explicitly "unselected" throughout.
- Does not claim HITL pause/resume exists — Correction #2, Scenario F.
- Does not claim cancellation is unified — Correction #1.
- Does not claim C-MoE browser routing exists — capability selection logic itself doesn't exist (Part 7, `BrowserCapability` row).
- Does not claim Verification is live on `main` — stated as not wired into any live path throughout.
- Does not claim `NetworkEgressGovernor` exists — explicitly "not created, not registered" (Part 10).
- Does not claim Browser capability registration exists — declared-not-registered, unchanged.
- Does not claim Browser session resources exist — `HTTPClientResource` exists for network access generally; a Browser-specific resource is explicitly `unknown`/open (Part 17).
- Does not imply implementation is scheduled — restated at every major boundary of this document.

---

# Part D — Dependency Gate

| Prerequisite | Current state | Tier 1 requirement? | Tier 2 requirement? | Browser-owned? | Common dependency? |
|---|---|---|---|---|---|
| Kernel v1.0 stable | Two named blockers closed Aug 31; no fresh freeze verdict observed in what was read | No | No | No | Yes |
| Verification wired into a live path | No — unmerged branch | No (Tier 1 can populate `execution_detail` without a consumer) | Yes | No | Yes |
| Canonical failure taxonomy | Open (`DEBT-015`) | No | Yes | No | Yes |
| Watchdog/recovery reconciled | **Yes** — `ADR-KERNEL-02` (Sept 5, 2026; see Part 0.5). Target `GraphExecutionWatchdog`, not the K4.4 standalone pair v1/v2 pointed to | Soft — Tier 1 has minimal recovery needs | Yes | No | No longer a common-dependency blocker — resolved |
| Common HITL mechanism | Does not exist anywhere | No | Yes | No | Yes |
| Network egress enforcement | Does not exist; worse than stated per Correction #9 | **Yes** | Yes | No | Yes |
| Credential/identity architecture | Does not exist | No | Yes | Partially (broker role, Part 12) | Mostly |
| `browser_automation` registered | No, by deliberate policy | No | Yes | Yes (the registration act itself) | No |
| Browser runtime selected | No | No | Yes | Yes | No |

Tier 1's only **Yes** in the "requirement" columns that isn't already satisfied is network egress — everything else Tier 1 needs (governed execution, trust/quarantine, evidence hook) already exists.

---

# Part E — Final Invariant Catalog (Deduplicated)

```
B-01  Governance cannot be bypassed. [Structural: AbstractCognitiveWorker.execute()]
B-02  Web content is data, never authority.
B-03  Observation does not imply authorization.
B-04  A physical action must resolve to a valid semantic action, or fail closed.
B-05  task_generation, state_epoch, and policy_version are independent and all three
      are revalidated immediately pre-dispatch.
B-06  Authorization binds to execution_id + task_generation + state_epoch +
      policy_version + target + authorization_scope -- not to "looks similar."
B-07  Physical actions cannot invent, alter, or broaden semantic intent.
B-08  Unknown/unsupported action types fail closed.
B-09  Unknown external outcomes (OUTCOME_UNKNOWN) are never SUCCESS and never
      blindly retried.
B-10  Authority can only be conserved or attenuated through delegation, recovery,
      or human approval -- never increased.
B-11  Authority can be revoked; revoked or superseded authority cannot be reused.
B-12  Credentials never enter unrestricted model/LLM-visible context.
B-13  Data use is purpose-bound to the semantic_intent that authorized its collection.
B-14  Cross-origin data transfer is a governed decision.
B-15  Network destinations are validated by resolved address, not hostname text;
      every redirect hop is independently revalidated.
B-16  Browser sessions cannot cross execution-ownership boundaries.
B-17  Evidence preserves provenance across every transformation, and can establish
      that something did NOT happen, not only that it did.
B-18  Task success is decided by Verification, once it exists on a live path --
      never by Browser's own self-report.
B-19  Browser cannot construct a parallel Verification, recovery-budget, HITL,
      or Planner authority.
B-20  Multiple observation channels disagreeing forces re-observation, not a
      convenient pick.
B-21  Web-derived content is promotable to durable learning only through the
      existing Learning Gate (successful AND verified AND policy-compliant).
B-22  Browser contains grounding/target-resolution/execution-adaptation
      intelligence and nothing resembling a second interpret()/plan()/compile().
B-23  Runtime capability availability and execution authorization are separate
      checks -- neither substitutes for the other.
B-24  Idempotency class (safe_to_retry / idempotent / conditionally_idempotent /
      non_idempotent / unknown) is declared before retry is ever considered.
```

(24 invariants, down from the 25-30 drafted across the prior two passes — merged near-duplicates, folded the new revocation/policy-version/negative-evidence/capability-negotiation findings in rather than appending them as afterthoughts.)

---

# Part F — Open Questions Register

| Question | Why unresolved | Options | Recommended decision point | Phase affected |
|---|---|---|---|---|
| `BrowserGovernor` (new) vs. extending `AgentGovernor` | Mechanically identical; ownership/taxonomy call only | Either | Whenever `NetworkEgressGovernor`-adjacent work is actually scheduled at the Kernel level | Tier 1 (network policy) |
| `browser_automation` contract declaration timing | K1.6 precedent argues for waiting; nothing forces waiting | Declare now (matches `web_search`'s current treatment) vs. wait for a real adapter | Implementation scheduling review | Tier 2 |
| Failure-taxonomy coordination | `DEBT-015` already proposes an extension; Browser's needs (`NEEDS_HUMAN`/`UNSAFE`/`BLOCKED`/`STAGNANT`) aren't in it yet | Fold into `DEBT-015`'s ADR vs. propose separately | Whenever `DEBT-015` gets its own ADR, per Architecture Freeze Principle | Tier 2 |
| Runtime selection | Deliberately deferred — selecting now would lock in a decision against then-stale facts | Playwright/Chromium (dominant precedent) vs. alternatives evaluated at implementation time | Tier 2 implementation kickoff | Tier 2 |
| Grounding implementation (DOM/A11y/visual mix) | Same reasoning as runtime selection | BrowserGym's hybrid approach is the leading precedent, not locked in | Tier 2 implementation kickoff | Tier 2 |
| HITL mechanism design | Doesn't exist anywhere in OCBrain yet; not Browser's to design alone | Needs a Kernel-level ADR, not a Browser-subsystem decision | Whenever common HITL is prioritized | Both tiers (Tier 1 rarely needs it; Tier 2 needs it structurally) |
| `fetcher.py` vs. shared network client (Correction #9) | Newly surfaced this session; not yet triaged by the project owners | Reroute `fetcher.py` through the shared client vs. confirm the separation is deliberate | Next `KNOWN_ISSUES.md` sync | Tier 1 |
| Whether a `BrowserSessionResource` should exist | `HTTPClientResource` is a real precedent but doesn't settle whether Browser needs its own | Model it as a `Resource` vs. keep it inside `ExecutionContext` scoping only | Tier 2 implementation kickoff | Tier 2 |

---

# Freeze Decision

**READY FOR ARCHITECTURE APPROVAL.**

Basis: the architecture is internally consistent (Contradiction Audit, prior pass, reaffirmed — no new contradictions surfaced this session), contains no hidden authority, no hidden parallel runtime, and no privilege-escalation path across delegation/recovery/HITL (audited, Part 16's scenario trace finds exactly one real gap, and it's a named common-infrastructure dependency, not an architectural defect). Open questions are correctly left open rather than force-closed. Corrections found this session (Part 0) improve precision; none of them invalidate the design.

This finding is **only** about the architecture. It says nothing about whether implementation prerequisites are satisfied — the Dependency Gate (Part D) shows most are not — and nothing about whether implementation should be scheduled, which remains Ocbriin's and Moncif's decision, made against `IMPLEMENTATION_ROADMAP.md`, whenever they choose to make it.

---

# Final Status

```
Status:              PROPOSAL — NOT AUTHORITATIVE
Repository basis:    1h0lde4/ocbrain-v4.1 @ 79c84d5
Implementation:      NOT STARTED
Scheduling:          NOT SCHEDULED
Current priority:    Kernel v1.0 / Verification
Browser:              FUTURE MILESTONE
User Behavioral Learning Extension:
                        SEPARATE LATER STUDY
```

**Final principle, unchanged across all three passes:** Browser is an execution capability, not an independent cognitive authority. It observes, grounds, translates authorized semantic intent into physical interaction, executes within that authorization, and reports evidence. It does not redefine the objective, grant itself authority, turn webpage content into instructions, bypass Governance, invent a second Planner or Verification or recovery budget or HITL authority, reuse stale authorization, treat browser API success as verified success, or promote unverified experience into durable learning. Those decisions remain exactly where they already are in this codebase.
