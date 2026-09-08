# OCBrain — Browser / Web Agent Subsystem: Final Architecture Study (v2)

```
Status:              PROPOSAL — NOT AUTHORITATIVE
Repository basis:    1h0lde4/ocbrain-v4.1 @ 79c84d5
Implementation:      NOT STARTED
Scheduling:          NOT SCHEDULED
Current priority:    Kernel v1.0 / Verification
Browser:             FUTURE MILESTONE
Supersedes:          OCBRAIN_BROWSER_WEB_AGENT_ARCHITECTURE_STUDY.md (v1, same commit)
```

> **Architecture approval and implementation scheduling are separate decisions.** This document performs a hardening pass — it corrects two overclaims from v1, closes several security/authority gaps v1 left implicit, and produces the four artifacts requested for final review. It still implements nothing, registers nothing, and modifies no code on `main`. Its acceptance as an architecture does not schedule its implementation.

```
Kernel v1.0 / Verification   → current priority, unchanged
future Browser/Web Agent     → this document
future Tier-1 implementation → not started, not scheduled
future Tier-2 implementation → not started, not scheduled
```

The User Behavioral Learning Extension remains a separate future study, untouched here.

---

## 0. What This Pass Changed

v1 was directionally sound but under-specified three things a final pass has to get right: it didn't fully separate semantic intent from physical action, it didn't state an authority-conservation invariant strongly enough to catch privilege escalation across delegation/recovery/HITL, and it stated two things about current OCBrain behavior with less precision than a re-read of the actual code supports. Corrected below, with the exact lines.

| # | v1 said | Re-read of `79c84d5` shows | Correction |
|---|---|---|---|
| 1 | (implied) cancellation is uniformly `ExecutionContext.cancellation_token` | `AbstractCognitiveWorker.__init__` also sets `self._cancelled: bool = False` (`core/workers/base.py:196`), with a setter (`:368`) and `is_cancelled` property (`:373-379`). `core/workers/curator.py` (a live, implemented worker) checks `self.is_cancelled` — the worker-local flag — at three call sites, not `context.cancellation_token`. Meanwhile `execute()`'s own cancellation handling is a third path: it catches `asyncio.CancelledError` around the `_run()` call. | Three cancellation-adjacent mechanisms coexist today, not one: (a) `asyncio.Task` cancellation, caught by `execute()`; (b) `ExecutionContext.cancellation_token`, checked by `WorkflowRuntime`/`ModelRouter`/the K4.4 watchdog; (c) `AbstractCognitiveWorker._cancelled`, checked by `MemoryCuratorWorker`. I have not traced every call site of a worker-level `.cancel()`, so I can't say whether (c) is reachable in current live paths — only that it exists and is checked. A future `BrowserWorker` must use (a)/(b), the same path `execute()` and the watchdog already share, and must not extend (c). Resolving the (c) duplication itself is Kernel-layer debt, out of Browser's scope — flagged, not fixed here. |
| 2 | `GovernanceVerdict.ESCALATE` "already means... requires HITL approval" (true) — framed as if that closes the human-approval question | `execute()`'s actual `ESCALATE` branch (`core/workers/base.py`, the block right after `REJECT`) emits `worker.escalated` and immediately **returns a failed `WorkerResult`** with `metadata={"requires_hitl": True}`. It does not pause, does not persist a resumable request, and provides no resume/reject/expire path. Confirmed independently: zero matches anywhere in the repo for `PendingApproval`, `ApprovalRequest`, `resume_from_approval`, `approval_id`, or `approval_state`. | `ESCALATE` today is a specific *kind of failure with a flag*, not a pause/resume mechanism. A future Browser HITL flow (brief §69–70) has nothing to attach to yet beyond "fail and tell the caller a human is needed." Treated in §A.9/§Gate below as a genuine prerequisite, not an integration detail. |
| 3 | (implicit) whether a second planning layer inside Browser would duplicate existing architecture | `core/cognitive/planner.py`'s own docstring states the boundary explicitly: *"Produces Cognitive Artifacts and ephemeral parameter objects only. Never invokes capabilities, never selects experts, never performs execution... Capability selection belongs exclusively to the future Cognitive Runtime (C-MoE)."* `core/cognitive/compiler.py` is *"the single seam between reasoning (Cognitive Front-End) and execution (Kernel)."* The Cognitive Front-End's full public surface is fixed at exactly three calls: `interpret()`, `plan()`, `compile()`. | This isn't a principle I need to argue for — it's already the codebase's own stated law. See §A.2. |

---

# Part A — Revised Architecture Study

## A.1 Tier Discipline (unchanged from v1, restated for a standalone reader)

**Tier 1 (tracked):** `BrowserWorker` = "web browsing, content extraction" (`KNOWN_ISSUES.md` Future Workers table; corroborated by `IMPLEMENTATION_ROADMAP.md`). HTTP-only, via `core/web/fetcher.py`. No browser process.

**Tier 2 (extended, not tracked anywhere):** interactive automation — click/type/forms/multi-tab/auth/downloads/JS/visual grounding/external side effects/human takeover. Specified here as architecture only.

Nothing below promotes Tier 2 into Tier 1. Where a finding applies to Tier 1 today (not just Tier 2 later), it's marked **[Tier 1 — current gap]**.

## A.2 No Second Planner

Answered directly by the codebase, not by principle alone. `PlanStep`/`ExecutionPlan` (`core/cognitive/planner.py`) already are the semantic-to-physical bridge object; `compiler.compile()` already maps them onto `WorkflowDefinition` nodes/edges behind a governance gate (`action_type="plan_compile"`) before any execution exists. A `BrowserWorker` is invoked as one `WorkflowNode` (`worker_type="browser"`) inside an *already-compiled* `WorkflowDefinition` — it receives one `PlanStep`'s worth of resolved config and executes it.

**What Browser may contain** (per the brief's own framing, now grounded): grounding intelligence, target resolution, execution adaptation — i.e., *how* to carry out the one step it was given, including local retries and re-grounding. **What it may not contain:** a second call into anything resembling `interpret()`/`plan()`/`compile()`, and no independent "what should happen next at the task level" reasoning. If a browser task needs replanning, that request goes back up through `SupervisorWorker` to the real Planner — Browser does not decide to replan itself (see §A.9, Invariant B-25).

## A.3 Broker vs. Worker

The brief's decomposition (`Semantic Browser Contract → Security/Policy Boundary → Browser Broker → Browser Adapter → Browser Runtime`) is a reasonable research question but not one this codebase's current maturity can answer with evidence — there is no browser runtime, no adapter, and (per A.1's correction) not even a finished HITL or cancellation-authority story to hang a Broker off of. Rather than invent a `BrowserBroker` class now:

- **Recommendation:** treat "Broker" as a *role*, not a class, for this document's purposes — the set of responsibilities (session ownership, credential mediation, security-policy enforcement, control-transport management) that must sit between `BrowserWorker._run()` and whatever runtime Tier 2 eventually picks. Whether that role becomes its own module or stays inside `BrowserWorker` as an internal collaborator is an implementation-time decision, not an architecture-time one — deciding it now would be exactly the "unproven speculative structure" K1.6 already rejected once (§10 of v1).
- **What is decided:** the role's responsibilities may **not** be split across `BrowserWorker` and something else in a way that lets either side independently authorize an action. Whoever ends up holding "Broker" responsibilities still calls into the *same* `GovernanceKernel.evaluate_action()` — see Authority Matrix, Part B.

## A.4 Semantic Action Contract

Real, shipping systems in this space already draw this exact line. **Browser Agent Protocol (BAP)** and **agent-browser-protocol (ABP)** both sit as a thin, deterministic execution layer between "the LLM decides what to do" and "Playwright does it," using semantic selectors (ARIA role + accessible name, visible text) instead of CSS/XPath, and both report the resulting action space as small, typed, and fast (BAP: ~10–25ms/action, in-process, versus 800–1500ms for LLM-per-click approaches). CELLMATE (UC San Diego, arXiv:2512.12594) makes the security case for the same split directly: it maps browser actions to an "agent sitemap" of semantic meanings *specifically* so that policy can be written against semantic intent rather than low-level UI primitives, and states plainly that "enforcing meaningful policies on low-level UI primitives is brittle and error-prone."

**Proposed shape** (extends the `BrowserAction` sketched in v1 §9, does not replace it — semantic and physical are different objects, not different fields on one object):

```python
# PROPOSED — Tier 2, not implemented, not registered.

@dataclass(frozen=True)
class BrowserSemanticAction:
    """What OCBrain asked for, before any physical interaction is chosen.
    Compiled 1:many into BrowserPhysicalAction (below) by whatever holds
    the Broker role (SS A.3) -- OCBrain-side code never emits physical
    actions directly."""
    execution_id: str
    task_generation: int        # SS A.6 -- distinct from state_epoch
    semantic_intent: str        # e.g. "submit_search", "confirm_purchase"
    target: str                 # role+name style, e.g. role("button","Submit")
    parameters: Dict[str, Any]
    preconditions: List[str]
    expected_effect: str
    side_effect_class: str
    authorization_scope: str    # binds to a GovernanceResult, SS A.6/Part B
    observation_requirements: List[str]
    verification_requirements: List[str]
    policy_version: str

@dataclass(frozen=True)
class BrowserPhysicalAction:
    """The compiled, runtime-specific interaction. Never constructed
    directly from a Planner/Supervisor -- only ever produced by compiling
    a BrowserSemanticAction against a current BrowserObservation."""
    semantic_action_id: str     # FK to the BrowserSemanticAction it compiled from
    state_epoch: int            # SS A.6
    primitive: str              # click | type | navigate | ...
    coordinates_or_ref: Any
```

Unknown `semantic_intent` values, or a `BrowserPhysicalAction` whose `semantic_action_id` doesn't resolve, fail closed — no adapter is permitted to invent a physical action from an LLM string that didn't pass through this compilation step (brief §7, this document's own §110 P0 list item 7).

## A.5 Preconditions, Settlement, Postconditions

`click() returned` is not `action succeeded` — v1 already said this; the gap was not saying what to do instead. ABP's concrete answer is directly reusable as a design pattern: each step injects input, waits for an engine-defined **settled** boundary (not a fixed sleep), captures output, then proceeds. Adopting that shape:

```
precondition check  →  dispatch  →  wait-for-settled  →  observe  →  postcondition check  →  BrowserActionResult
```

"Settled" is runtime-specific (network idle, DOM-mutation quiescence, a specific selector's appearance) and is exactly the kind of decision this document declines to lock in (§A.3) — but the *shape* (settlement is a condition to wait for, not a duration to sleep for) is decided.

## A.6 Two Kinds of Staleness, Not One

v1 modeled `state_epoch` (web-page staleness). This pass adds **`task_generation`** (OCBrain-side staleness — the task itself changed, was replanned, or was cancelled-and-reissued) as a distinct counter, because the two fail independently: a page can be perfectly fresh while the *task* that authorized acting on it no longer exists (replan happened upstream), and vice versa. `BrowserSemanticAction.task_generation` and `BrowserPhysicalAction.state_epoch` are separate fields for exactly this reason — an action must be rejected if *either* has moved, not just one.

This also directly answers §10's TOCTOU question: the properties that must be revalidated immediately before physical execution are `task_generation`, `state_epoch`, `target` identity, `origin`, and `authorization_scope` — all five, not just the page-state ones. CELLMATE's TOCTOU/"branch steering" framing is the concrete literature reference for why this can't be checked once at observation time and assumed to hold through dispatch.

## A.7 Self-Healing Cannot Become Semantic Drift

Re-grounding a stale target (brief §35) repairs `BrowserPhysicalAction.coordinates_or_ref`. It must never regenerate `BrowserSemanticAction.semantic_intent`, `expected_effect`, or `authorization_scope` — those are upstream of the physical layer entirely and re-grounding has no legitimate reason to touch them. This is the direct answer to invariant B-07 below, and it's mechanically enforced by the two-object split in §A.4: a re-grounding routine that only ever has write access to `BrowserPhysicalAction` cannot drift the semantic action even by accident, because it doesn't hold a reference to a mutable one.

## A.8 Observation Model — Modality Conflict Is Not Corroboration

v1's provenance model (§11) covered *source* trust. It didn't cover what happens when two observation channels of the *same* page disagree — DOM says visible, accessibility tree says hidden, screenshot shows nothing. Per this document's own instruction: these are not independent evidence that happens to agree or disagree; they're multiple views of one (possibly compromised) page, and disagreement is itself a signal. Proposed handling, Tier 2: a high-impact action requires observation agreement across at minimum two independent channels (e.g., DOM + accessibility); disagreement forces re-observation before the action proceeds rather than picking whichever channel is more convenient.

## A.9 Tier 1 Boundary, Restated Precisely

```
URL → NetworkEgressGovernor (Part C) → core/web/fetcher.py → parser/cleaner
    → TrustManager / KnowledgeQuarantine (existing, unchanged)
    → WorkerResult.execution_detail populated as real ExecutionOutcome
    → (future) Verification, once wired to any live path
```

No browser process, no JS execution, no interactive session — but per **[Tier 1 — current gap]** in v1 §5, Tier 1 does not get a pass on the network-egress gap merely because it's the smaller tier: `core/web/fetcher.py` fetches whatever URL it's handed today, full stop.

---

# Part B — Authority & Dependency Matrix

| Decision | Current authority (as of `79c84d5`) | Future authority | May Browser decide? |
|---|---|---|---|
| Objective | User request / Planner (`core/cognitive/planner.py`) | Same | No |
| Task decomposition | Planner + Compiler (`interpret→plan→compile`, the fixed three-call surface) | Same | No |
| Capability selection | Not implemented — `CapabilityExecutorWorker` is explicitly single-step-only, "no capability selection logic (still C-MoE future work)" | C-MoE | No |
| Action authorization | `GovernanceKernel.evaluate_action()`, structurally non-bypassable via `AbstractCognitiveWorker.execute()` | Same, extended with a `NetworkEgressGovernor` (Part C) | No |
| Network destination policy | **Does not exist** (confirmed: no allowlist/SSRF/egress code anywhere in `core/governance/`) | Common `Governor`, Kernel-registered — see Part C.5 | No — proposed as Kernel-level specifically so Browser can't own it |
| HITL pause/resume | **Does not exist** — `ESCALATE` fails the call with a flag, no persistence (§0, correction 2) | Common mechanism, not yet designed anywhere in the repo | No |
| Cancellation | Split three ways today (§0, correction 1) | Canonical = `ExecutionContext.cancellation_token` / `asyncio` cancellation | No — Browser consumes, doesn't add a signal |
| Recovery budget | `OperationRecoveryBudget` (`core/cognitive/recovery.py`), "one recovery budget per operation... no hidden retry universe" (ADR-K4.2-H-05) | Same | No |
| Task success / verification | Not wired into any live path (`COMPLETED_WITH_PARTIAL_OUTPUT` bug, unmerged Phase C branch) | Verification (once landed) | No |
| Durable-learning promotion | `core/web_learning/{trust,quarantine}.py` (Tier 1 scope only — no browser-trajectory learning path exists) | Learning/Verification jointly, per this project's own Learning Gate principle | No |
| Semantic target freshness / physical re-grounding | N/A — doesn't exist yet | `BrowserWorker` internal (§A.7) | **Yes, within the state_epoch/task_generation boundary** |
| Physical action execution | N/A | `BrowserWorker` / runtime adapter | **Yes, within an already-authorized `BrowserSemanticAction`** |
| Session lifecycle (Tier 2) | N/A | `BrowserWorker`, scoped by existing `ExecutionContext.session_id`/`worker_id` | **Within scope**, not a new identity system |
| Security veto | `GovernanceKernel` (all five registered Governors, including `EvolutionGovernor` — implemented inside `governance_kernel.py` itself, not a separate file) | Same | No |

The two "Yes" rows are the entire positive case for Browser having any local intelligence at all — everything else in this table is a "No" by design, which is the concrete form of Invariant B-25 (no second planner) and the Authority Conservation invariant (B-11) below.

---

# Part C — Threat, Information-Flow, and Security Model

## C.1 Trust Dimensions, Kept Separate

Per this document's own instruction not to collapse these: **source trust** (TrustManager's domain score) ≠ **content trust** (is *this* instruction on the page legitimate) ≠ **identity trust** (is the authenticated session who it claims) ≠ **instruction authority** (does this content get to change what OCBrain does — answer: never) ≠ **evidence confidence** (how sure is the verifier). A `.gov` domain with a high TrustManager score can still host a comment section with an injection payload; that payload has zero instruction authority regardless of the domain score. This isn't a hypothetical — it's the exact shape of the ShadowPrompt incident (v1 §5): a trusted domain (`claude.ai`), a legitimately embedded third-party component, and a resulting authority collapse because subdomain trust was conflated with component trust.

## C.2 Credential / Identity Architecture (Tier 2)

Not "username + password fields." Passkeys/WebAuthn, OTP/MFA, OAuth, and FedCM flows are explicitly *browser-mediated* by W3C design — the browser, not a script, owns the ceremony. Proposed classification, matching `vercel-labs/agent-browser`'s concrete precedent ("the LLM never sees passwords," credentials stored encrypted and referenced by name):

| Credential class | LLM-visible? | Mediated by |
|---|---|---|
| Password | No | Credential broker (role, §A.3), referenced by name |
| Passkey/WebAuthn | No — browser/OS ceremony | Browser/OS, not OCBrain |
| OTP/MFA code | No, unless the human types it themselves | Human, via HITL takeover |
| OAuth/FedCM | No — redirect flow, browser-mediated | Browser |
| Session cookie | No | Credential broker; excluded from observations/logs/evidence by default |

Authentication is a **security-context transition**, not a UI event: crossing `Unauthenticated → Authenticated` should be treated as a governance-relevant state change that can raise the side-effect-classification floor and the evidence bar for subsequent actions in the same session, not merely a fact the worker happens to observe.

## C.3 Information Flow Is Purpose-Bound

`Use address to book delivery` does not imply `use address for marketing signup`. This can't be enforced by trust scoring — it requires tracking *why* a piece of data entered the session (which `BrowserSemanticAction.semantic_intent` it arrived under) and refusing to let it flow into an action whose `semantic_intent` wasn't the one that authorized collecting it. This is a Tier 2 design note, not a mechanism to build now — flagged because it's a real gap the two-object split in §A.4 happens to make tractable later (the semantic action already carries `authorization_scope`; purpose-binding is a check against that field, not new infrastructure).

## C.4 Threat → Control → Enforcement → Test

| Threat | Attack path | Control | Enforcement point | Evidence | Test precedent |
|---|---|---|---|---|---|
| SSRF / internal-network access | Fetch a URL resolving to loopback/RFC1918/cloud-metadata | `NetworkEgressGovernor`, default-deny, validates the *resolved* destination, not the hostname string | Governance evaluation, pre-dispatch | Denied-connection event | — |
| DNS rebinding | TTL=0 record changes IP between check and connect | Re-validate destination at actual connect time, not just at URL-parse time | Network layer, inside the fetch/adapter call itself | Connection log w/ resolved IP | — |
| Redirect abuse | 3xx chain ends at an internal target | Re-validate *every* redirect hop against the same policy, not just the origin URL | Same Governor, re-invoked per hop | Redirect chain in evidence envelope | — |
| Indirect prompt injection | Hidden/visible page text redirects agent intent | Web content is data, never authority (Invariant B-02); semantic actions only come from `interpret→plan→compile`, never synthesized from page text | Structural — the two-object split in §A.4 has no code path from "text on a page" to `BrowserSemanticAction` | n/a — architectural exclusion, not a filter | MUZZLE-style adaptive red-team (arXiv:2602.09222), DoomArena |
| Cross-origin exfiltration via the agent itself | Origin A data reaches origin B through the agent, not through the browser's own SOP | Purpose-bound data flow (§C.3); browser SOP alone is explicitly insufficient once the agent is the channel (CELLMATE's central finding) | Data-flow check at the point data would cross into a new `BrowserSemanticAction`'s parameters | Data-flow decision in evidence | — |
| Credential leakage into model context/logs | Naive design puts secrets in observations | Credential broker; secrets referenced by name, never dereferenced into LLM-visible text (§C.2) | Broker role | Absence-of-secret check on observation payloads | — |
| Stale-action / TOCTOU execution | Action authorized at T0, executed at T1 after material change | Dual staleness check, `task_generation` + `state_epoch`, revalidated immediately pre-dispatch (§A.6) | `BrowserWorker`, immediately before `BrowserPhysicalAction` dispatch | Epoch/generation values in evidence envelope | CELLMATE names this class explicitly |
| Self-heal drift | Re-grounding silently changes intended operation | Two-object split — re-grounding can't touch `BrowserSemanticAction` fields (§A.7) | Type-level (physical vs semantic objects are different types) | n/a | — |
| Unverified success (false-green) | Physical action succeeds; task obligation doesn't | `execution_detail`/`ExecutionOutcome` populated richly; real success gated on (future) Verification, not on tool-call return | `WorkerResult.execution_detail` | Same evidence chain Verification will eventually consume | WebArena-Verified's own finding: contamination-prone "wins" drop to 0% under grounded checks |
| Persistent memory/learning poisoning | Untrusted content becomes durable strategy via repeated observation | Learning Gate (existing project principle) — successful ≠ verified ≠ promotable; no browser-trajectory learning path exists yet at all, so this is currently N/A by absence rather than by defense | N/A — flagged as a prerequisite before any Tier 2 learning integration is designed | — | — |

## C.5 Network Egress Is Not Browser's to Own

Correcting v1's framing: a `NetworkEgressGovernor` is not a Browser-subsystem security mechanism — it's a general Kernel-layer capability that Browser would be the *first consumer* of, not the owner of. This document does not register it, does not modify `GovernanceKernel`, and does not create it. It's listed in Part B's Authority Matrix as a future common-Governance responsibility specifically so a later implementer doesn't accidentally build it as Browser-private code.

---

# Part D — Verification & Evaluation Matrix

| Obligation | Action | Evidence | Criterion | Inspection | Expected effect | Postcondition | Failure | Recovery |
|---|---|---|---|---|---|---|---|---|
| Retrieve page content | `Navigate` + `Extract` | Fetched bytes, content-hash, final URL, redirect chain | Content present, matches requested resource | Deterministic (hash/type check) | Extracted text available to caller | Extraction non-empty, trust-classified | `TRANSPORT` / `EMPTY_RESPONSE` (existing `FailureType` values) | Retry within `OperationRecoveryBudget`, bounded |
| Submit a form (Tier 2) | `BrowserSemanticAction(semantic_intent="submit_form")` | Pre/post DOM or accessibility snapshot, settled-boundary wait, resulting URL/confirmation text | Confirmation matches `expected_effect` | Deterministic where possible; cognitive verification only as fallback, per this project's existing "deterministic-first escalation ladder" principle | Server-side state changed as requested | Confirmation observed independently of the agent's own claim | New `FailureType` values needed: `UNSAFE`/`BLOCKED`/`NEEDS_HUMAN` — coordinate with `DEBT-015`'s already-proposed taxonomy extension, don't fork it | Re-query external state before deciding to retry (brief §54) — never blind-retry a write |
| High-impact write (Tier 2) | Any `IRREVERSIBLE_WRITE`-classified semantic action | Full evidence envelope (v1 §38) + explicit pre-declared effect (this doc §33-equivalent) | Independent postcondition, not agent self-report | Human-reviewable evidence bundle if `ESCALATE` | External system reflects the declared effect | Settlement confirmed via re-query, not via the write call's own return value | `OUTCOME_UNKNOWN` is a first-class terminal state, distinct from `FAILED` — a timeout must never collapse to either `SUCCESS` or blind retry | Escalate to `SupervisorWorker`; Browser does not compensate unilaterally |

This table is intentionally three rows, not exhaustive — it demonstrates the mapping the brief's §37/§109.D asks for without inventing rows for actions that don't exist yet in any tier.

---

# Invariant Catalog

Refined from the brief's B-01…B-30 draft against what's now grounded in real code (dropped duplicates, merged near-identical pairs, added two the research surfaced).

```
B-01  Governance cannot be bypassed. [Existing, structural: AbstractCognitiveWorker.execute()]
B-02  Web content is untrusted data, never authority. [Structural via SS A.4's two-object split]
B-03  Observation does not imply authorization.
B-04  A BrowserPhysicalAction must resolve to a real BrowserSemanticAction, or fail closed.
B-05  Both task_generation and state_epoch must match at dispatch time; either moving invalidates the action. [SS A.6]
B-06  Authorization binds to execution_id + task_generation + state_epoch + target + policy_version, not to "an action that looks similar."
B-07  Self-healing repairs BrowserPhysicalAction only; it cannot alter BrowserSemanticAction. [SS A.7]
B-08  Unsupported/unknown action types fail closed, never best-effort.
B-09  Unknown external outcomes (OUTCOME_UNKNOWN) are never treated as either SUCCESS or silently retried.
B-10  Recovery may change strategy; it may never increase authority. [Authority Conservation, below]
B-11  Delegation (Planner -> Supervisor -> BrowserWorker -> runtime) may attenuate authority; it may never expand it.
B-12  Credentials never enter LLM-visible observation text. [SS C.2]
B-13  Data use is purpose-bound to the semantic_intent that authorized its collection. [SS C.3]
B-14  Cross-origin data transfer is a governed decision, not a side effect of browsing. [SS C.4]
B-15  Network destinations are validated by resolved address, not hostname string. [SS C.4]
B-16  Every redirect hop is independently revalidated against network policy.
B-17  Browser sessions cannot cross execution-ownership boundaries (existing ExecutionContext.session_id/worker_id scoping, SS A.9).
B-18  Evidence preserves provenance across every transformation (observation -> extraction -> claim -> learning candidate).
B-19  Evidence is not equivalent to the agent's own claim of success.
B-20  Task success is decided by Verification, once it exists on a live path -- never by Browser itself.
B-21  Browser may not construct a parallel Verification, recovery-budget, HITL, or Planner authority. [Part B, "No" column]
B-22  Security-relevant restrictions survive delegation, replanning, recovery, browser restart, and context compaction.
B-23  Multiple observation channels disagreeing is a signal requiring re-observation, not an invitation to pick the convenient one. [SS A.8]
B-24  Web-derived content cannot be promoted into durable learned strategy without passing the existing Learning Gate (successful AND verified AND policy-compliant).
B-25  Browser contains grounding/target-resolution/execution-adaptation intelligence and nothing resembling a second interpret()/plan()/compile(). [SS A.2]
```

Each is expressible as (positive test / negative test); none of those tests are written here — that's Tier 2 implementation-phase work, explicitly out of scope for this document.

**Authority Conservation, stated formally** (this document's answer to the brief's request): *a Browser execution, recovery path, delegated worker, runtime adapter, session, or human-approved continuation must never hold more authority than was explicitly granted by its parent execution and the policy context active at grant time.* Every "No" in Part B's rightmost column is an instance of this one invariant, not an independent rule — which is the point: one invariant, checked once, rather than N ad-hoc rules that can drift out of sync with each other.

---

# Final Audits

**No hidden authority.** Walked Part B row by row: every decision that determines whether an action is permitted, whether a side effect is safe, whether a task succeeded, whether a retry is allowed, or whether data may cross an origin maps to an existing or explicitly-future-common OCBrain authority (Governance, Verification, Learning Gate, OperationRecoveryBudget). The only two rows Browser owns (target freshness, physical execution) are bounded by an authorization it did not grant itself. No gap found.

**No hidden runtime.** Checked the proposed design against "second planner / second governance / second verification / second recovery / second HITL / second memory / second capability router / second event store": §A.2 rules out a second planner by construction (two-object split, no code path from page text to semantic action); §A.9/C.5 rule out a second governance/network-policy engine (proposed as Kernel-level, not Browser-owned); §D and Part B rule out a second verification engine; §D's "Recovery" column and the Invariant Catalog rule out a second recovery budget (must use `OperationRecoveryBudget`); no HITL persistence is proposed at all here — correctly, since none exists to extend (§0 correction 2); no Browser-specific event store is proposed — events integrate with the existing `EventStream` (v1 §49, unchanged). No gap found.

**No hidden privilege escalation.** Walked `Planner → C-MoE → Supervisor → BrowserWorker → (Broker role) → runtime → page`, `Failure → Recovery → Replan → Resume`, and `AI → Human → AI`: at every step, the Authority Conservation invariant applies, and no step in the design as specified acquires capability, data access, side-effect scope, origin scope, or credential access beyond what its parent held. The one place this *could* go wrong in a real implementation — a recovery-triggered replan silently reusing the original authorization for a materially different action — is exactly what Invariant B-10/B-06 and Part B's "No" on recovery budget are aimed at. Flagged as the highest-value thing a future implementation review should specifically test for.

---

# Contradiction Audit

| Claim | Current repo | Proposed design | Contradiction? | Resolution |
|---|---|---|---|---|
| "Browser respects governance" | `AbstractCognitiveWorker.execute()` enforces this structurally for any worker | `BrowserWorker` subclasses it, adds nothing that bypasses it | No | — |
| "Cancellation is unified" | Three coexisting mechanisms (§0.1) | Browser uses only the canonical two (asyncio + `cancellation_token`) | No, but the *premise* was wrong in v1 | Corrected in §0; not a Browser-subsystem fix |
| "HITL exists for high-risk actions" | `ESCALATE` fails closed with a flag; no resume path | Design assumes a future common HITL mechanism, doesn't build one | No — this design doesn't claim HITL works today | Flagged in the Gate below as a prerequisite |
| "C-MoE will route to Browser" | C-MoE capability *selection* logic doesn't exist; `browser_automation` is declared-not-registered | Design specifies the future contract shape only, registers nothing | No | Already correctly deferred in v1 §10 |
| "Verification will confirm Browser task success" | Not wired into any live path; interim safeguard is a confidence cap | Design populates `execution_detail` now so it's ready when Verification lands | No | — |
| "A Browser Session could be a Resource" | No `core/resources/` directory exists; `resource.py` inside `core/capabilities/` mostly documents what's *not* implemented, by deliberate policy | Design takes no position (§97-equivalent, left open) | No | Genuinely open; not resolved here |

No unresolved contradictions found between this proposal and the live repository as of `79c84d5`.

---

# Implementation-Entry Gate (Not a Schedule)

Restating the brief's own list, checked against what's now confirmed rather than assumed:

| Prerequisite | Status as of `79c84d5` |
|---|---|
| Kernel v1.0 stable | Two named blockers closed Aug 31; no fresh freeze verdict observed in what was read |
| Verification wired into a live path | No — unmerged branch, 20/90 contract types, nothing on `main` calls it |
| Canonical failure taxonomy resolved | No — `DEBT-015` (extension) and the `COMPLETED_WITH_PARTIAL_OUTPUT` bug are both open |
| Watchdog/recovery debt resolved or bounded | No — `DEBT-016` open; this document bounds it by naming which pair to target (v1 §7), doesn't resolve it |
| Common HITL mechanism exists | No — confirmed absent (§0 correction 2) |
| Network egress enforcement exists | No — confirmed absent anywhere in governance |
| Credential/identity architecture exists | No — genuinely new ground (§C.2) |
| Semantic action contract defined | Yes, by this document (§A.4) — as a proposal, not code |
| Runtime topology selected | No, deliberately deferred (§A.3) |

This is a checklist for *whoever later decides to schedule Tier 1 or Tier 2*, not a countdown this document is starting. Most rows read "No" — that's an accurate description of current state, not a problem this document needs to solve.

---

# Required Final Status

```
Status:              PROPOSAL — NOT AUTHORITATIVE
Repository basis:    1h0lde4/ocbrain-v4.1 @ 79c84d5
Implementation:      NOT STARTED
Scheduling:          NOT SCHEDULED
Current priority:    Kernel v1.0 / Verification
Browser:              FUTURE MILESTONE
```

**A note on what this document deliberately did not do**, per its own stop condition: it does not attempt exhaustive coverage of every browser feature category (permission dialogs, clipboard, drag-and-drop, localization, geolocation, and similar brief sections are real but don't change authority, security boundary, contract shape, state correctness, evidence/verification, learning integrity, runtime isolation, or evaluation validity — the test this document was told to apply). Those remain accurately described in v1 as Tier 2 detail, not re-litigated here.

**Final principle, unchanged:** Browser is an execution capability, not an independent cognitive authority. It observes, grounds, translates authorized semantic intent into physical interaction, executes within that authorization, and reports evidence. It does not decide what the user wants, what OCBrain is authorized to do, what counts as task success, what becomes durable knowledge, or what recovery authority exists. Those stay exactly where they already are in this codebase.

**Architecture approval and implementation scheduling are separate decisions.**
