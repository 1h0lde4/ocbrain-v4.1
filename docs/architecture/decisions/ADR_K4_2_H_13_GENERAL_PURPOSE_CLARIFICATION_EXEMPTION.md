# ADR-K4.2-H-13: General-Purpose-Only Plans Exempt from ClarificationPolicy

**Status:** ACCEPTED
**Date:** August 20, 2026
**Author:** Live-debugging session (not one of H1's original nine decisions or H2's four parallel packets — see Context)
**Scope:** `core/cognitive/planner.py` (`ExecutionPlan`, `_is_general_purpose_only()`, `plan()`), `core/cognitive/compiler.py` (`compile()`), `core/governance/orchestration_governor.py` (`_evaluate_clarification_policy()`), plus test fixtures in `tests/test_runtime_integration.py`, `tests/core/cognitive/test_planner.py`, `tests/test_k2_4_governance.py`.

---

## 1. Context

Reported directly against `main` (Codespace test, not a packet branch): a plain `"hi and hello"` returned *"Sorry, this request could not be compiled into a runnable plan (escalated)."* The error persisted after reverting the two H2 merges that had briefly landed on `main` (PRs #7/#8, then reverted via #9/#10), which correctly ruled those out as the cause and pointed at something already present on `main` before H2 began.

Traced to `core/orchestrator.py`'s handling of a non-`COMPILED` `CompilationResult` (the only place this exact message exists), back through `compile()`'s `ClarificationPolicy` governance action, to `_estimate_confidence()` in `core/cognitive/planner.py`. Root cause: `core/capabilities/capability.py` confirms `LLM_COMPLETION` is, as of K2.3, the *only* capability with a registered `CapabilityContract` — everything else is declared, not registered. Its description is `"Generate text from a prompt via a language model."` Plan confidence is a Jaccard token-overlap score between a step's description and its top candidate's description, and a request essentially never lexically overlaps with a description of what its own handler *is* rather than what topics it covers. Confirmed by directly running the real tokenizer/scorer:

```
"hi and hello"                        vs description → 0.0
"book a flight to Tokyo next week"    vs description → 0.0
```

The second line is not a constructed example — it is the exact phrase `ADR-K4.2-H-02` uses as its own fixed-and-verified case for K42-002. That fix (K4.2-H1 D2) made sure a `0.0`-scoring general-purpose candidate still gets *discovered* rather than producing a spurious impasse. It did not address what happens next: that `0.0` becomes the plan's confidence via `_estimate_confidence()` (no special case for `is_general_purpose` candidates), and `ClarificationPolicy`'s default `confidence_threshold = 0.5` escalates unconditionally below that line — confirmed directly in `OrchestrationGovernor`'s evaluation code, which is a pure `confidence >= threshold` comparison with no other condition. Since `clarification_attempt` is never threaded across separate messages (Supervisor's revised-goal retry path was explicitly out of scope back in Packet 08 — see `IMPLEMENTATION_TRACKER.md`), every fresh message starts at attempt 0 of `max_escalations=2`, so the result is always `ESCALATE`, never `REJECT` — matching the reported message exactly.

**Net effect at the time of this fix: with only one capability registered, this could fire on essentially any request**, not specifically greetings — "hi and hello" simply happened to be what got tried first.

**Why the existing suite never caught this — three compounding, independently-confirmed gaps, all fixed as part of this change:**

1. `tests/test_runtime_integration.py`'s `_mock_llm_calls()` mocks the Planner's decomposition call to return `"Generate text from a prompt via a language model."` verbatim — `LLM_COMPLETION`'s own description, word for word. This guarantees a perfect (`1.0`) lexical match, which cannot happen for a real request describing what the user wants rather than what the capability is.
2. The one existing test of the escalation path (`test_escalated_compilation_invokes_supervisor_and_returns_gracefully`) additionally patched `core.cognitive.planner._estimate_confidence` directly to force `0.1`, bypassing the real scorer entirely.
3. `_build_runtime_stack()`'s own `LLM_COMPLETION` registration never set `is_general_purpose=True` (unlike `main.py`'s real registration, which does — with a comment there calling it *"the one line that makes the fix real rather than theoretical"*). This was invisible before now because neither existing test's outcome depended on the flag being correct: (1) always scored `1.0` regardless, and (2) bypassed discovery's real behavior entirely. Writing a test that actually exercises the real bypass mechanism surfaced this immediately as an `IMPASSE` instead of the expected low-confidence `COMPILED`/`ESCALATED` split — fixed here, in the fixture, so it matches production.

## 2. Decision

A plan whose *every* step's top-ranked candidate is the general-purpose fallback has no specific alternative anywhere to be uncertain between — `ClarificationPolicy` exists to catch genuine ambiguity among real options, not to gate on the fallback's own low lexical-match score against its own self-description, a mismatch `ADR-K4.2-H-02` already established is expected and uninformative for that candidate. Such plans are now exempt from `ClarificationPolicy` entirely, regardless of the raw confidence value.

- `_is_general_purpose_only(steps_with_candidates) -> bool` (`core/cognitive/planner.py`), computed independently alongside `_estimate_confidence()` at the same call site in `plan()`, not derived from it: `_estimate_confidence` answers "how low was the weakest step's score", this answers "was there ever a *specific* alternative anywhere in the plan at all". True iff every step's `candidates[0].is_general_purpose` is `True`. A step with zero candidates returns `False` for the whole plan (a materially more concerning case than "found only the fallback", conservatively not exempted). An empty plan also returns `False`, matching `_estimate_confidence`'s own explicit handling of that input.
- Because `discover_capabilities()`'s specificity-dominance ordering (D2) already guarantees any cleared non-general-purpose candidate outranks every general-purpose one for its step, checking only `candidates[0]` is sufficient — a better-ranked specific candidate silently losing to a general-purpose one is not a case that ordering can produce.
- `ExecutionPlan` gains `general_purpose_only: bool = False`, populated by `plan()`. Not part of K4 §6's original field list, added the same way `caused_by` (D9) was.
- `compile()` passes `"general_purpose_only": plan.general_purpose_only` into the `ClarificationPolicy` governance action's metadata, alongside the existing `confidence`.
- `OrchestrationGovernor._evaluate_clarification_policy()` returns `None` (approve — the same "nothing to decide here" signal already used when `confidence` is absent entirely) when `general_purpose_only` is `True`, checked immediately after confirming the action is confidence-bearing and before the threshold comparison — a third permissive-on-absence-style branch, structurally identical in spirit to the pre-existing "`confidence is None`" one.
- No hard-coded capability-type routing is introduced, consistent with D2: the exemption is driven entirely by the registry-derived `is_general_purpose` flag already on each candidate, not by inspecting `capability_type` anywhere in the new code.

## 3. Consequences

- The reported bug is fixed. Verified end-to-end, unmocked, through the real `Orchestrator`: a decomposed step reading `"Reply warmly to the user's greeting"` (deliberately *not* matching `LLM_COMPLETION`'s description) against the real registered `LLM_COMPLETION` contract scores `0.0`, `is_general_purpose=True` — and now compiles and executes (`cognitive.plan_compiled`, `workflow.completed`, real adapter invocation), instead of escalating.
- Scoping verified the other direction too: with a second, real, specific-but-weak capability registered alongside `LLM_COMPLETION`, a similarly low-confidence plan (`~0.14`, genuinely computed, no mock) still escalates exactly as before, because `general_purpose_only` correctly comes out `False` — the exemption did not become a general confidence-gate weakening.
- Practical scope today: since `LLM_COMPLETION` is still the only registered capability, this exemption applies broadly — most plans currently are general-purpose-only by construction. That is a direct, deliberate consequence of the current K2.3-era single-capability configuration, not a defect in this fix; the exemption's condition (`every step's top candidate is the fallback`) will naturally and automatically narrow in scope as real, specific capabilities are registered and start winning ranking for the requests they actually match, with no further change needed here.
- All three test gaps identified in Context are now closed: `_build_runtime_stack()` sets `is_general_purpose=True` to match `main.py`; the one existing test whose setup (perfect-match mock + forced-low-confidence mock) now legitimately qualifies as `general_purpose_only=True` under the new rule was rewritten to use a real, weakly-matching specific capability instead — genuinely escalating rather than relying on either mock, which is a strictly more honest test of the same behavior it always intended to cover.
- `ADR_INDEX.md` is not updated by this change (same handling already established for `ADR-K4.2-H-10`/`H-12`, both written but not yet indexed pending the broader H2 consolidation sync); this ADR adds one more item to that already-pending sync, not a new category of gap.
- `KNOWN_ISSUES.md` is not updated by this change either, for the same reason; worth a line at the same consolidation step.

## 4. Alternatives considered

- **Give every `is_general_purpose` candidate a fixed confidence floor** (e.g. treat it as fully confident by construction, rather than computing an exemption flag): rejected as the primary mechanism — broader than necessary, and it would silently mute `ClarificationPolicy` for general-purpose candidates *even in plans where a genuinely weak specific alternative also existed and lost narrowly*, which the chosen per-plan `general_purpose_only` signal correctly still escalates (see the scoping test in Consequences). Confidence itself stays an honest, unmodified measurement either way; only the governance decision changes.
- **Reword `LLM_COMPLETION`'s description to lexically overlap with more real queries**: rejected — this games the scorer rather than fixing the underlying category error (using self-description overlap as a proxy for "can this fallback plausibly help"), and would not reliably cover short inputs like a two-word greeting regardless of wording chosen.
- **Decouple "confidence" (ranking) from a separate "clarification-worthiness" signal architecture-wide**: the more general, more correct long-term shape of this problem, but a materially larger redesign than a live-debugging fix warrants; noted here as a candidate for `FUTURE_RESEARCH_VAULT.md` rather than attempted in this change.
