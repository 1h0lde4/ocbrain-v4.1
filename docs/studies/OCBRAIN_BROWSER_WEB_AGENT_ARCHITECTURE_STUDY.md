# OCBrain — Browser / Web Agent Subsystem: Research + Architecture Study

**Status:** PROPOSAL. Not authoritative. Not scheduled. Not implementation-ready.

**Scope of this document:** Stages B–D only (Research, Architecture, Contract Specification) of the Browser/Web Agent Subsystem brief. No `BrowserWorker` implementation exists after this document. No new browser runtime exists after this document. No `CapabilityContract` is registered by this document. Every code block below is a design sketch for review, not a diff against `main`.

> **Architecture approval and implementation scheduling are separate decisions.** Nothing in this document should be read as a recommendation to schedule implementation. That determination belongs to Ocbriin and Moncif, made against `IMPLEMENTATION_ROADMAP.md` and `CURRENT_STATE.md` at whatever future point this proposal is reviewed — not inferred from the fact that a design exists.

**Author:** Claude (Browser/Web Agent Research Session), Sept 6–7, 2026. Grounded against `1h0lde4/ocbrain-v4.1` @ `79c84d5`.

**Governing sequencing, unaffected by this document:**

```
Kernel v1.0 / Verification work   → current priority (unchanged)
Browser/Web Agent                 → this document (Stage B–D research + architecture only)
Browser implementation            → future scheduled milestone (not started, not gated to start by this doc)
User Behavioral Learning Extension → separate, later study (out of scope here)
```

---

## 1. Scope Discipline

This is the load-bearing structural decision of the whole document, so it comes first rather than last.

| | **Tier 1 — Tracked scope** | **Tier 2 — Extended scope** |
|---|---|---|
| **Source of the scope claim** | `KNOWN_ISSUES.md` Future Workers table (authoritative per §18.2.1): `BrowserWorker — "Web browsing, content extraction" — Cognitive Phase`. `IMPLEMENTATION_ROADMAP.md` independently lists the same worker under future/deferred work. | This document's own synthesis of the original 122-section Browser/Web Agent brief. Not present in any authoritative roadmap file under any name. |
| **What it covers** | Fetch a URL, extract/clean content, route it through the existing trust/quarantine pipeline, return governed, evidenced output to a caller. | Clicking, typing, form submission, multi-tab/multi-window, authenticated sessions, downloads/uploads, visual/DOM grounding, JavaScript execution, external side effects (purchases, sends, deletes), human takeover. |
| **Runtime shape** | No browser process. HTTP retrieval only (`core/web/fetcher.py`, `aiohttp`). | A real browser runtime (Playwright/Chromium or equivalent) — does not exist anywhere in the repo today. |
| **Treatment in this document** | Specified in enough detail to be implementable once scheduled (§3–§4, §8–§13). | Specified as architecture only, explicitly to prevent an unscoped implementation from having to invent the boundary later (§14). Not implementable from this document alone — no runtime selection, no DOM/accessibility grounding decision, no benchmark run backs any specific claim here. |

**Rule for the rest of this document:** every section below is tagged **[Tier 1]**, **[Tier 2]**, or **[Both]**. A Tier 2 tag is not an argument for scheduling Tier 2 — it exists so that a future reader (including a future me) can tell at a glance which parts of this proposal describe something the roadmap has actually asked for versus something being kept ready in case it's asked for later.

---

## 2. Current Repository Integration **[Both]**

Confirmed via direct read, `79c84d5`:

- `core/web/{fetcher,parser,cleaner,search}.py` — HTTP-only retrieval. `fetcher.fetch_html(url, timeout_sec, max_retries)` does a plain `aiohttp` GET with a spoofed browser `User-Agent`, retry/backoff, no DOM, no JS.
- `core/web_learning/{trust,quarantine,pipeline}.py` — `TrustManager` (per-domain trust score, seeded `TRUSTED_DOMAINS` dict, adjusted by validation history) and `KnowledgeQuarantine` (pending/validated JSONL store). This is a working, if simple, provenance/trust pipeline.
- `modules/web_search/module.py` — wraps the above as a capability module.
- `interface/web/*.html` — OCBrain's own setup UI. Not part of this subsystem; noted only to prevent future conflation.

**Finding, not previously flagged, relevant to Tier 1 today (not just Tier 2 later):** `fetcher.fetch_html()` takes an arbitrary URL and fetches it with no destination validation of any kind — no private-IP/loopback/link-local/cloud-metadata check. This is a live gap in code that's in scope *today*, independent of anything this document proposes. See §5.

**Tier 1 integration shape:** `BrowserWorker._run()` calls `core/web/fetcher.fetch_html()` → `parser`/`cleaner` → routes extracted content through the *existing* `TrustManager`/`KnowledgeQuarantine` unchanged. No new provenance system for Tier 1. The only genuinely new Tier-1 piece is the worker boundary itself (§4) and the network policy gap (§5).

---

## 3. Browser Execution Kernel — Answered: No **[Both]**

The original brief asks, correctly, whether a dedicated Browser Execution Kernel is justified, and says explicitly not to build one if the repo already has an equivalent. It does.

`AbstractCognitiveWorker` (`core/workers/base.py`) already provides, for every worker including a future `BrowserWorker`, for free:

- **Structural governance enforcement** — `execute()` is non-overridable and wraps `_run()` inside `GovernanceKernel.evaluate_action()`. A worker cannot bypass governance by construction, not by convention.
- **Lifecycle state** — `WorkerState`: `IDLE / RUNNING / PAUSED / COMPLETED / FAILED / CANCELLED`.
- **Cancellation** — `ExecutionContext.cancellation_token`, the same `CancellationToken` every worker already receives.
- **Structured result reporting** — `WorkerResult.execution_detail: Optional[ExecutionOutcome]`, the (currently underused) hook for real `FailureType` classification instead of a bare boolean.
- **Budget/progress** — `ExecutionContext.execution_budget` (additive K4.4 field) plus the K4.4 `ExecutionWatchdog`/`ProgressMonitor` pair (§9).

**Recommendation:** no Browser Execution Kernel. Browser-specific concerns — state epochs, freshness validation, target re-grounding, DOM-mutation reconciliation — belong *inside* `BrowserWorker._run()` as an internal strategy object (Tier 2), not as a new sibling to `GovernanceKernel`/`ExecutionRuntime`. Building a second kernel here would be the exact "hidden second Planner" / duplicated-authority anti-pattern this project has already found and corrected twice (`DEBT-004`, `DEBT-016`).

---

## 4. BrowserWorker Boundary **[Tier 1 shape, Tier 2 content]**

```python
# PROPOSED — not implemented. core/workers/browser.py (sketch)

class BrowserWorker(AbstractCognitiveWorker):
    """Web browsing, content extraction (KNOWN_ISSUES.md Future Workers table).

    Tier 1: _run() delegates to core/web/{fetcher,parser,cleaner} and routes
    output through core/web_learning/{trust,quarantine} unchanged. No browser
    process. Tier 2 (not built): _run() delegates instead to a browser-runtime
    adapter behind the same interface -- the worker boundary does not move
    when the runtime behind it does (see Replaceability, S111-112 of the
    original brief).
    """

    worker_type = "browser"

    async def _run(self, context: ExecutionContext) -> WorkerResult:
        # Tier 1 body operates only on context.metadata["url"] / ["query"].
        # Tier 2 body would additionally read context.metadata["browser_context"]
        # (SS5) when present, and dispatch to a runtime adapter instead of
        # fetcher.fetch_html() directly.
        ...
```

Two decisions this makes explicitly, both consistent with existing code rather than inventing new machinery:

1. **No new context object competes with `ExecutionContext`.** Browser-specific parameters ride in `ExecutionContext.metadata["browser_context"]`, following the exact precedent `execution_budget` set as a K4.4 additive field — same pattern, not a new one.
2. **`execution_detail` gets populated for real.** Nowhere else in the codebase does a worker currently populate `WorkerResult.execution_detail` with a meaningful `FailureType` beyond the default — that's the same false-completion gap Verification work is fixing elsewhere (see §10). `BrowserWorker` should be built as a model citizen of the `ExecutionOutcome` contract from day one rather than inheriting the ambient `success`-boolean ambiguity. This costs nothing extra to design now and avoids a retrofit later.

---

## 5. Security / Network Egress Architecture **[Tier 1 gap; Tier 2 extends it]**

**Confirmed:** no domain allowlist, SSRF protection, or network-egress policy exists anywhere in `core/governance/`. `ConversationGuardrails`' denylist matches action *descriptions* (text), is empty by default, and has no concept of a network destination.

**This is not a future problem.** `core/web/fetcher.py` fetches whatever URL it's given today, with no restriction — a `BrowserWorker` built on top of it Tier-1-only would inherit that gap immediately, in scope, not as extended future work. Recommend this be closed as part of any Tier 1 implementation, independent of whether Tier 2 is ever scheduled.

**Proposed shape — reuses the existing `Governor` extension point, adds no new mechanism:**

```python
# PROPOSED — not implemented.
class NetworkEgressGovernor(Governor):
    """Evaluates action.metadata["target_url"] against a destination policy.

    Default-deny: RFC1918/loopback/link-local ranges, cloud metadata
    endpoints (169.254.169.254 and equivalents), and non-http(s) schemes are
    rejected regardless of allowlist contents -- an explicit allowlist entry
    cannot re-open these (fail closed per Browser Agent Invariant #22
    analogue: a degraded/misconfigured policy must not silently permit).
    """
    name = "NetworkEgressGovernor"

    def evaluate(self, action: GovernanceAction) -> GovernanceResult:
        ...  # APPROVE / REJECT / ESCALATE per GovernanceVerdict, same as
             # every other Governor -- no parallel security layer.
```

This is one more `Governor` registered with the existing `GovernanceKernel`, evaluated through the exact same `evaluate_action()` call every worker already goes through. No new enforcement path.

**Two real, dated incidents worth citing directly as design precedent** (Anthropic's own Claude in Chrome, which is architecturally the closest real system to what Tier 2 would eventually be):

- **ShadowPrompt** (disclosed Dec 27, 2025; patched extension v1.0.41): an overly-broad `*.claude.ai` origin allowlist, chained with a DOM-based XSS in a third-party CAPTCHA component hosted on a `claude.ai` subdomain, let any website silently inject prompts as the user, zero-click. The concrete lesson for §8 (Cross-Origin Trust): **match exact origins, not subdomain patterns, and treat every third-party-embedded component as its own trust boundary** — a trusted site does not make everything hosted under it trusted.
- **Cross-extension command injection** (reported May 2026; fixed in v1.0.70): the fix closed the gap in "standard" mode only — switching to "privileged" mode (which skips explicit user confirmation) could reopen it. Lesson: a security control scoped to one operating mode is not a security control unless it's verified to cover every mode the system can be in.

Anthropic's own published safety documentation for Claude in Chrome names indirect prompt injection as the primary risk category for browser-using AI tools and reports internal red-team numbers (23.6% attack success unprotected → 11.2% during autonomous use with current safeguards, 0% against a specific browser-attack subset; a separately reported, differently-scoped test on the Opus 4.6 model line cites sub-0.08%). These numbers aren't directly transferable to OCBrain — different model, different defenses, different methodology — but the shape of the mitigation stack (site blocklists, high-risk-category blocks, user confirmation for high-risk actions, classifiers) is directly relevant precedent for §14's side-effect classification and approval design.

---

## 6. Governance Integration **[Both]**

No new mechanism required beyond §5's proposed Governor. Existing shape already covers what the brief asks for:

- `GovernanceVerdict.ESCALATE` **already means** "requires HITL approval" — this is the brief's Human Approval concept (§69 of the original brief), not a new verdict type.
- `GovernanceAction.metadata: Dict[str, Any]` is the existing, extensible channel for browser-specific policy fields (`side_effect_class`, `target_url`, `origin`, `requires_fresh_observation`) — no schema change to `GovernanceAction` needed for Tier 1 or the early part of Tier 2.
- Side-effect classification (READ / REVERSIBLE_WRITE / IRREVERSIBLE_WRITE, brief §51) is a Tier 2 policy question, not a Tier 2 mechanism question — it's a matter of what values `AgentGovernor` (or the new `NetworkEgressGovernor`) checks in `action.metadata`, not a new enforcement path.

**Open question flagged for review, not decided here:** whether side-effect classification lives in a new `BrowserGovernor` or as an extension of `AgentGovernor`. Both are mechanically identical (a `Governor` subclass); this is a taxonomy/ownership question for whoever reviews this document, not an architecture question.

---

## 7. Execution Budget / Watchdog Integration **[Tier 2, with a Tier-1-relevant finding]**

`KNOWN_ISSUES.md` DEBT-016 tracks two independent `ExecutionWatchdog`/`ProgressMonitor` implementations:

- **Graph-aware pair** (`core/runtime/watchdog.py` + `progress.py`) — used by `core/workflow/runtime.py`, tied to `ExecutionGraph`.
- **Standalone pair** (`core/runtime/execution_watchdog.py` + `progress_monitor.py`, K4.4) — used today by `core/model_router.py`'s long-form generation path. Its own module docstring states it's deliberately generic — *"the same monitor works for a streaming LLM generation today, and — per the architecture-reconciliation brief's 'future workers and capabilities' requirement — for a Worker's step-by-step progress or a Capability's phase transitions later, without redesign."*

**Recommendation:** target the standalone K4.4 pair. It was explicitly built for this exact future-integration case; the graph-aware pair was not. This is a direct textual precedent, not a guess — but DEBT-016 is real and unresolved, so if/when the two implementations are reconciled, this integration point may need to move. Flagging as a pre-implementation checklist item, not resolving DEBT-016 here (out of scope — that's Kernel-layer debt, not Browser-subsystem work, per this document's own Scope Protection rule in §16).

**Recovery-invariant compliance**, cited directly from `execution_watchdog.py`'s own docstring: `OperationRecoveryBudget` is *"the sole operation-level autonomous-recovery budget... no component may create an independent recovery budget... no hidden retry universe."* Any Browser-local recovery (brief §62: Retry / Re-observe / Re-ground / Rollback / Compensate / Escalate / Abort) must either (a) stay intra-operation as a bounded watchdog extension, exactly like the existing stall-handling behavior, or (b) escalate through the *existing* `SupervisorWorker` → `OperationRecoveryBudget` path. It must never instantiate a third, independent retry mechanism. This directly operationalizes Browser Agent Invariant #24 ("retry must never blindly duplicate an uncertain external side effect") against real code rather than leaving it as a principle.

**Cancellation:** reuse `CancellationToken` unmodified. Cited precedent, `execution_watchdog.py`: *"Timeouts are cancellations triggered by timers — no separate mechanism... ExecutionWatchdog's only terminal action is calling the existing, unmodified CancellationToken.cancel(reason) — it never kills a process, throws across the stack, or maintains a second cancellation object."* Browser cancellation (brief §8) should follow this exactly: no second cancellation object, no browser-specific "stop" that isn't just this token.

**`FailureType` extension:** Browser will eventually need failure classes the current enum doesn't have (`NEEDS_HUMAN`, `UNSAFE`, `BLOCKED`, `STAGNANT`). `DEBT-015` already proposes extending the `FailureType`/`FailureClass` taxonomy (`transport.upstream` vs `.client`, `context.over_budget`, `authorization.failure`) as its own, already-flagged future architecture item, explicitly gated on its own ADR per the Architecture Freeze Principle. Recommend Browser's needed additions be coordinated into that same extension effort when it happens, rather than Browser growing an incompatible parallel taxonomy.

---

## 8. Verification / Evidence Integration **[Both — and the load-bearing dependency]**

Re-confirmed against `79c84d5`, not assumed from a prior session: `core/runtime/execution_outcome.py:81`'s `ExecutionOutcome.is_success` still treats `COMPLETED_WITH_PARTIAL_OUTPUT` as equal to `SUCCESS`; `core/workflow/runtime.py`'s completion check still reduces to the last node's own flag. Real work is underway — a frozen v3 spec, ~20 of ~90 contract types implemented and tested on an unmerged branch (`feature/verification-critic-evidence-phase-c`) — but nothing on `main` calls into `core/verification/` yet, and the interim safeguard is a confidence cap (`COMPLETED_WITH_WARNINGS`), not real verification.

**Consequence for this document:** the Browser brief's own central claim — *"a successful browser API call is not proof of task success"* (invariant #8) — cannot be made load-bearing today, because the general mechanism it depends on isn't wired into any live execution path yet. This isn't a Browser-subsystem defect; it's an accurate statement of a dependency.

**What Browser should still do now, at design time:** the C-MoE study already reserves the integration surface (`verification_status`, a `VERIFYING` lifecycle state) that Browser's own proposed lifecycle (§9) would need. Recommend `BrowserWorker` be designed to populate `execution_detail`/`ExecutionOutcome` richly regardless of whether anything downstream reads it yet — building to the interface that's coming rather than to the currently-broken shortcut, per this project's own Architecture Evolution Policy (favor convergence). **Explicitly not recommended:** Browser building its own independent verification mechanism to compensate — that would be exactly the duplicated-authority pattern already found twice in this codebase (`DEBT-004`, `DEBT-016`), and it would fork the definition of "did this actually succeed" across two subsystems instead of one.

---

## 9. Browser State, Action, and Lifecycle Contracts **[Tier 2]**

Sketched for completeness of the proposal; none of this is registered or wired to anything.

```python
# PROPOSED — Tier 2, not implemented.

class BrowserTaskState(str, Enum):
    """Nested beneath the existing WorkerState.RUNNING -- not a replacement
    for it. A BrowserWorker instance's outer WorkerState is still what
    GovernanceKernel/ExecutionWatchdog see; this is the internal detail."""
    SESSION_PROVISIONED = "session_provisioned"
    OBSERVING           = "observing"
    ACTING               = "acting"
    VERIFYING             = "verifying"   # matches the C-MoE study's reserved state name
    RECOVERING           = "recovering"
    AWAITING_HUMAN       = "awaiting_human"

@dataclass(frozen=True)
class BrowserObservation:
    observation_id: str
    state_epoch: int          # monotonic per session; an Action taken against
                               # epoch N must not execute silently against N+1
    url: str
    origin: str
    trust_classification: str  # from the EXISTING TrustManager, not a new field
    captured_at: float
    # Deliberately NOT a full DOM/accessibility/screenshot dump -- compact,
    # task-relevant observation per brief SS10.

@dataclass(frozen=True)
class BrowserAction:
    action_id: str
    execution_id: str
    action_type: str           # navigate | extract | click | type | ... (Tier 2 taxonomy)
    target_state_epoch: int    # the epoch this action was proposed against
    side_effect_class: str     # read | reversible_write | irreversible_write
    origin: str
    risk_level: str
```

**Freshness rule (brief §11–12):** an action whose `target_state_epoch` doesn't match the session's current epoch at execution time is rejected and forces re-observation — this is a plain equality check the worker performs before dispatch, not new kernel machinery.

**Session/lease model (brief §45):** no new identity system needed. `ExecutionContext` already carries `session_id`, `worker_id`, and `causal_chain`. A "BrowserSession" is a resource scoped by `(session_id, worker_id)` with a lease expiry, using fields that already exist rather than inventing a parallel identity scheme.

---

## 10. C-MoE Capability Integration **[Both]**

`core/capabilities/capability.py`'s own docstring states the operative policy directly: `CapabilityType.WEB_SEARCH` / `.BROWSER_AUTOMATION` are declared in the enum namespace but deliberately not registered, because registering "empty/fake Adapters for these now, with no real backend to test against, would be exactly the kind of unproven speculative structure K1.6's Resource Model audit explicitly rejected." The same reasoning applies to a `Browser Session` **Resource** type, which doesn't exist in `resource.py` at all yet, for the identical reason.

**This document follows that precedent rather than overriding it.** Below is what a future `CapabilityContract` for `browser_automation` would look like — specified, not registered:

```python
# PROPOSED SPECIFICATION ONLY. register_capability() is NOT called by this
# document. Actual registration is an implementation-phase action, gated on
# a real Adapter existing and passing real tests -- same bar LLM_COMPLETION
# cleared at K2.3, no lower.
CapabilityContract(
    capability_type="browser_automation",
    is_general_purpose=False,
    ...
)
```

**Second, independent gate:** full C-MoE capability *selection* logic doesn't exist yet either — `CapabilityExecutorWorker` is, by its own docstring, *"deliberately narrow — single-step execution only, no capability selection logic (still C-MoE future work)."* Browser's C-MoE integration is therefore gated behind two separate not-yet-built things, not one: its own Adapter, and C-MoE's own routing logic. Neither is proposed for construction here.

---

## 11. Provenance and Trust Boundaries **[Tier 1 reuses; Tier 2 extends]**

Tier 1 needs nothing new — extracted content already flows through `TrustManager.get_trust_score()` (per-domain, seeded, history-adjusted) and `KnowledgeQuarantine` (pending/validated). This is real, working prior art; extend it, don't replace it.

Tier 2 needs two extensions, both additive to the existing model rather than replacements:

1. **Field-level provenance** (brief §83): today's `TrustManager` scores a *domain*. Tier 2 extraction needs to trace an individual extracted value (a price, a confirmation number) back to a specific observation/element, not just "came from example.com." Proposed as an additional `provenance` field threaded through extraction results, not a new trust system.
2. **Cross-origin trust boundary changes** (brief §23): today's model has no concept of a same-page trust boundary changing mid-navigation. ShadowPrompt (§5) is the concrete argument for why "the page trusted a moment ago" and "the page now" need to be treated as potentially different trust domains, especially across a redirect or an embedded third-party component.

---

## 12. Future Interactive-Browser Capabilities **[Tier 2 — explicitly extended scope]**

This section exists so a Tier 2 implementer doesn't have to re-derive the boundary from zero, and so this document doesn't quietly smuggle Tier 2 into Tier 1 by omission. It is deliberately less detailed than §2–§11: none of it is scheduled, and over-specifying unscheduled work has its own cost (this project's own §18.6 already warns against adopting "experimental ideas without clear benefit" — the same logic applies to over-designing them).

- **Action taxonomy:** Navigate/Click/Type/Select/Scroll/Extract/Screenshot/Download/Upload/DragAndDrop/Dialog-handling, each as a `BrowserAction` subtype per §9's shape.
- **Authentication state machine:** `Unauthenticated → LoginRequired → Authenticating → Authenticated → SessionExpired`, with credentials never entering worker context directly — `vercel-labs/agent-browser`'s pattern is a clean, citable precedent here: credentials stored encrypted, referenced by name, "the LLM never sees passwords." A credential broker sitting between `BrowserWorker` and the runtime, not a new OCBrain-wide secrets system.
- **Human takeover:** Portia AI's `EndUser`/"clarification" abstraction is a clean precedent — when authentication or high-risk confirmation is needed, the worker escalates via the existing `GovernanceVerdict.ESCALATE` path (§6) carrying enough structured context (current objective, current state, reason, requested action, risk) that the human isn't handed an opaque yes/no.
- **Runtime selection:** not decided here. Playwright/Chromium is the dominant precedent across the research (browser-use, BrowserGym's WebArena/WorkArena family, `agent-browser`), but selection should happen at implementation time against then-current licensing/maintenance/container-compatibility facts, not be locked in by a research document.
- **Grounding strategy:** BrowserGym's own approach — DOM + accessibility tree + screenshot + element coordinates as complementary signals, not a DOM-vs-vision binary — matches the brief's own §38 instruction and is the strategy this document would recommend if asked to decide today, without deciding it.

---

## 13. Evaluation and Security Test Strategy **[Tier 2, informs any future Tier 1 acceptance criteria too]**

**Functional/benchmark landscape** (BrowserGym unifies most of these behind one observation/action interface — `pip install browsergym-{webarena,webarena-verified,visualwebarena,workarena,assistantbench}`):

| Benchmark | What it actually measures | Relevant caveat |
|---|---|---|
| WebArena (Zhou et al., ICLR 2024) | 812 tasks / 241 templates, 4 self-hosted realistic sites | Original scoring used substring/LLM-judge matching — see next row |
| WebArena-Verified (ServiceNow, 2025–26) | Same tasks, audited + deterministic, network-trace replay, 258-task "Hard" subset | Under grounded-interaction checks, contamination-prone baselines that "won" under old scoring dropped to 0% — benchmark *versions* are not comparable, exactly as the original brief warned |
| WorkArena / WorkArena++ (Drouin/Boisvert et al.) | 682 enterprise-workflow tasks on a real ServiceNow instance, validated via backend REST + frontend JS | Enterprise-workflow-shaped, not general open-web |
| VisualWebArena (Koh et al., 2024) | Multimodal/visual grounding tasks | Extends WebArena's execution-based eval to vision |
| AssistantBench (Yoran et al.) | Long-horizon, real-world information-seeking tasks | Explicitly targets recovery-from-partial-failure, not just completion |
| Online-Mind2Web (Xue et al., 2025) | Live-website evaluation | Found frontier agents up to ~59% less competent on live sites than static benchmarks suggested — the concrete number behind the original brief's "never claim real-world reliability from static benchmark success alone" |
| Odysseys (Jang et al., 2026, arXiv:2604.24964) | 200 long-horizon, multi-site tasks from real browsing histories, graded checkpoints | Explicitly critiques trajectory-level LLM-as-judge for long tasks — matches this project's own "cognitive verification is lower-trust than deterministic checks" principle |
| HORIZON (Wang et al., 2026) | Cross-domain, trajectory-grounded failure attribution by horizon length | Confirms terminal-metric-only evaluation systematically under-characterizes long-horizon failure |

A separate finding worth carrying into any future eval design directly: agents in this literature (Chung et al., 2025, cited via the Signal-Driven Observation paper) fail long-horizon tasks primarily by looping and losing track of the objective — **not** by exhausting context. That argues for the brief's own Stagnation Detection (§61) being weighted at least as heavily as budget/token accounting in any future evaluation harness.

**Security test strategy** — adopt adaptive, not fixed-string, red-teaming:

- **MUZZLE** (Syros et al., arXiv:2602.09222, Feb 2026): automated multi-agent pipeline (Explorer → attack-generator using PAIR → Dispatcher → Executor → Judge) that discovers indirect-prompt-injection surfaces from the target agent's *own* trajectory rather than a fixed attack list — found 37 previously-undocumented attacks across 4 apps, including 2 cross-application attacks. This is the concrete mechanism behind the original brief's "adaptive red-teaming... MUZZLE" reference, now confirmed real and cited properly.
- **DoomArena** (surfaced via the BrowserGym ecosystem): a framework specifically for injecting attacks into web pages inside BrowserGym environments — a plausible harness for running MUZZLE-style or fixed-string injection tests against whatever runtime Tier 2 eventually picks, without building a bespoke test harness from scratch.
- **ShadowPrompt / cross-extension incident** (§5): concrete, dated, real regression-test cases — exact-origin matching, and uniform policy enforcement across every operating mode, not just the default one.

---

## 14. Deliberately Out of Scope Here

- **Watchdog reconciliation (DEBT-016):** referenced (§7) as a dependency risk, not resolved. Resolving it is Kernel-layer work with its own justification requirement independent of Browser.
- **DEBT-011 (`ContentDomain` vs `LearningCandidate`):** unrelated to this subsystem; noted in the Stage A audit, not touched here.
- **User Behavioral Learning Extension:** explicitly a separate, later study per Ocbriin's direction — not folded into this document even though it also touches "what OCBrain learns from observing behavior," because that idea's governance model (propose-and-approve for user-habit learning) is a distinct problem from web-content trust.
- **Runtime selection, actual grounding-signal implementation, actual injection-defense implementation:** all Tier 2 and all deferred to whenever Tier 2 is scheduled, per this document's own scope discipline.

---

## 15. Open Questions for Review

Flagged, not resolved — consistent with this project's practice of recording authority gaps rather than filling them silently:

1. `BrowserGovernor` (new) vs. extending `AgentGovernor` for side-effect classification (§6) — mechanically identical, an ownership/taxonomy call.
2. Whether the `browser_automation` `CapabilityContract` shape sketched in §10 should be written into `capability.py` now (declared-only, matching `web_search`'s current treatment) or left purely in this document until implementation is scheduled. This document takes no position — either is consistent with K1.6's precedent.
3. Coordination point for `FailureType` extension (§7) — whether Browser's needed values (`NEEDS_HUMAN`, `UNSAFE`, `BLOCKED`, `STAGNANT`) ride on `DEBT-015`'s already-proposed taxonomy work or get proposed independently.

---

## 16. Closing Statement

Everything above is a proposal against `79c84d5`. It makes exactly zero changes to `main`, registers zero capabilities, and implements zero workers. Its purpose is to exist as a reviewable artifact — the same role `OCBRAIN_CMOE_COGNITIVE_RUNTIME_ARCHITECTURE_STUDY.md` and its companion Verification study already play for their subsystems — so that whenever Browser/Web Agent work is actually scheduled, it starts from an architecture that has already been checked against real code, not from a 122-section brief re-litigating what already exists.

**Architecture approval and implementation scheduling are separate decisions.** This document asks for the former. It does not ask for, and should not be read as implying, the latter.
