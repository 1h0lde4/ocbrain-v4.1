# Context Authority Threat Model

Part of the parallel Context Engineering / Context Compiler research track.
Findings here are verified against the live repository with reproducible
evidence — see each entry's Evidence and Reproduction sections. This track
does not alter K4.2/K4.3/K4.4/Kernel v1.0 milestone status; production
remediation for findings below is deferred to the Context Engineering
architecture phase.

---

## CTX-AUTH-001 — Intent Hypothesis Retrieved-Context Authority Boundary

**Status:** VERIFIED CURRENT SECURITY GAP (source-level finding + empirical
synthetic reproduction; real-world hostile exploitation NOT DEMONSTRATED)

**Affected component:** `core/cognitive/intent.py` —
`generate_hypotheses()` / `_build_hypothesis_prompt()` /
`_parse_hypotheses()` (K4.2.1, Intent Interpreter)

**Affected boundary:** Message/channel authority — the boundary between
retrieved data and model-instruction-bearing prompt structure

**Affected data:** Retrieved memory content surfaced via
`ContextAssemblyEngine.assemble_context()` and interpolated into the
Intent Hypothesis prompt

### Source

`UnifiedMemory` / `GraphRAGPipeline` — any `KnowledgeEntry` reachable by
this retrieval path. No authority tier or source-type restriction
currently governs what can reach this interpolation point; any entry that
scores well enough is eligible, regardless of `worker_id`/`workflow_id`
provenance.

### Precondition

Attacker-influenceable content becomes part of a `KnowledgeEntry` that is
later retrieved for an unrelated request — e.g. via a future
`BrowserWorker` reading an external page, a summarized document, or any
other path that writes retrieved/external content into memory. No such
write path is currently implemented in the live pipeline (`BrowserWorker`
is not yet built); this precondition is forward-looking, tracking research
on real-world memory-poisoning patterns (MemoryGraft, Dec 2025) rather
than a demonstrated live entry point today.

### Attack path

```
external / untrusted / low-authority content
        ↓
retrieved as KnowledgeEntry (worker_id/workflow_id recorded, but
never consulted as a retrieval filter — separate finding)
        ↓
Context / ContextBlock / ProvenanceRecord built
   (trust_score, truth_status, worker_id, workflow_id all present)
        ↓
ContextAssemblyEngine.assemble_context() flattens to a plain string —
   all of the above metadata discarded before any consumer sees it
        ↓
_build_hypothesis_prompt() interpolates the flat string via bare
   str.format() between plain-text "Context:" / "Request:" /
   "Candidates:" labels — no delimiter, no escaping, no
   untrusted-data framing
        ↓
retrieved content containing those same labels is structurally
   indistinguishable from the template's own control sections
        ↓
_parse_hypotheses() accepts any "label | score" line found anywhere
   in the completion, with no field marking origin or trust
        ↓
an injected candidate can reach IntentHypothesis with no signal
   downstream consumers could use to treat it differently
```

### Current controls

- `_parse_hypotheses()`'s regex requires an exact `label | score` shape
  on its own line — real containment of *malformed* input, but not a
  security boundary (see Reproduction: a well-shaped injected line is
  accepted without friction).
- `ConversationGuardrails` exists and is registered with
  `GovernanceKernel`, but its own docstring states its only live call
  site is `AbstractCognitiveWorker.execute()`. The Intent Hypothesis path
  is a plain async function called directly from `Orchestrator.handle()`'s
  K4.2 branch, not a `Worker.execute()` call — this governor is very
  unlikely to sit in this path. Even where it does apply elsewhere
  (plausibly `core/workers/base.py:220`'s `description=f"{self.worker_type}:
  {context.query[:120]}"` — inferred from the matching docstring
  description, not directly traced), it is, by its own documented design,
  "a deliberately narrow, explicit pattern-match gate — not a
  content-safety classifier," with an empty denylist by default. It would
  not catch a novel injection shape regardless of call-path coverage.
- No other governor (`RecursionGovernor`, `BudgetGovernor`,
  `OrchestrationGovernor`, `AgentGovernor`) performs semantic content
  inspection.

### Evidence

- `core/memory/assembly.py:151` — `RetrievalContextBuilder.build()`'s only
  production caller; its output (`Context`) is flattened to `str` before
  return.
- `core/cognitive/intent.py:483-497` — `_build_hypothesis_prompt()` and
  `_HYPOTHESIS_PROMPT_TEMPLATE`, bare `str.format()`, no delimiter.
- `core/cognitive/intent.py:493-508` (approx.) — `_CANDIDATE_LINE` regex
  and `_parse_hypotheses()`, a repo-wide `re.MULTILINE` scan with no
  anchor to an actual "Candidates:" section boundary.
- `core/governance/conversation_guardrails.py` — docstring stating the
  only live call site and the empty-by-default denylist design.
- `core/orchestrator.py` (~line 202) — stale comment claiming
  `OrchestrationGovernor`/`AgentGovernor`/`ConversationGuardrails` don't
  exist except a "disconnected" `MemoryGovernor"; contradicted by
  `core/governance/governance_kernel.py:348`
  (`self.register_governor(ConversationGuardrails())`). Tracked as a
  separate documentation-debt item, not merged into this finding.

### Reproduction

Permanent regression: `tests/core/cognitive/test_intent_security.py`
(commit built on `79dd89e`). Exercises the real production path —
`generate_hypotheses()` with `ContextAssemblyEngine.assemble_context()`
and `generate_with_fallback()` mocked at the same boundary the repo's own
`TestGenerateHypotheses` tests use — not a standalone reimplementation.

- `TestCtxAuth001StructuralContainment::test_poisoned_context_does_not_create_second_request_section`
  — **FAILS**. A poisoned context string produces a constructed prompt
  containing two `"Request:"` and two `"Candidates:"` sections,
  captured directly at the `generate_with_fallback` call boundary.
- `TestCtxAuth001ParserAcceptance::test_injection_shaped_completion_line_is_not_accepted_as_a_hypothesis`
  — **FAILS**. A completion containing an injection-shaped line is parsed
  into `IntentHypothesis(label='novel:CONTEXT_SENTINEL_INJECTED',
  score=1.0, embedding_ref=None)` — indistinguishable from a legitimate
  hypothesis, at maximum score.
- `TestBenignContextBaseline` (both cases) — **PASSES**. Differential
  control confirming ordinary context, including content that merely
  mentions control-like words as prose, is unaffected — guards against a
  future over-broad (blacklist-style) fix.
- Full `tests/core/` run: 412 passed, 2 failed (the two above). No
  collateral breakage from adding the file.

### Containment vs. prevention

Strict `label | score` parsing is real containment of malformed shapes,
not a security boundary — it did not prevent the synthetic injection from
being accepted. Containment ≠ prevention.

### Blast radius

- **Downstream Goal propagation:** PARTIALLY VERIFIED, favorably. The
  existing test `tests/core/cognitive/test_intent.py::
  test_description_is_actual_request_not_hypothesis_label` indicates
  `Goal.structured_form["description"]` is derived from the actual
  request text, not the winning hypothesis's label — suggesting the most
  direct propagation path into Planner decomposition
  (`_DECOMPOSITION_PROMPT_TEMPLATE`) is not open today. This is inferred
  from an existing, passing test's name and stated intent, not from
  independently re-deriving the Goal-formation code path end to end in
  this phase — flagged as PARTIALLY rather than fully VERIFIED on that
  basis.
- **Other prompt-construction sites:** NOT FOUND in a repository-wide
  search (`core/`, `workers/`, `runtime/`, `governance/`, `interfaces/`)
  for `.format()`, f-string, or concatenation patterns embedding
  context/memory/evidence/retrieved content. Two adjacent f-string sites
  found (`planner.py:317`, `workers/base.py:220`) both truncate to 120
  characters into `description=`/`rationale=` fields — a materially
  different, more contained pattern, not re-classified as equivalent.
  **Revalidated** against a third persistence subsystem discovered during
  the cache-isolation audit — `core/context.py::ContextMemory`, whose
  `format_for_prompt()` does inject raw retrieved/conversational content
  into a prompt. Fully traced; see
  `docs/research/context-engineering/context-memory-path-audit.md`.
  Confirmed structurally separate from this finding: K4.2 writes into
  `ContextMemory` but never reads `format_for_prompt()` back, and that
  read path is confined to the Legacy Compatibility Bridge, which is not
  production-exercised. The "concentrated at one site" claim above
  stands. `ContextMemory`'s own injection mechanism — unconditional,
  unscoped, no attack precondition required — is a distinct, separate
  finding requiring its own threat-model entry, not yet written.
- **Tool execution impact:** NOT DEMONSTRATED. No live path from an
  injected hypothesis to tool invocation was traced or tested in this
  phase.
- **Real-world hostile exploitation:** NOT DEMONSTRATED. This is a
  reproduced synthetic attack against a production-equivalent path, not
  evidence of an external actor having exploited it. The precondition
  (attacker-influenceable content reaching memory) does not yet have a
  live entry point in the current pipeline.

### Severity / confidence

Structural weakness: **VERIFIED**, high confidence (direct source
reading + reproducible test). Real-world exploitability: **UNKNOWN** —
depends on precondition paths (e.g. a future `BrowserWorker`) that don't
exist yet, and on whether a real model would actually echo injected
content, which was not tested (would require live model inference,
out of scope for this deterministic regression).

### Future mitigation (not selected here)

Candidate directions for the Context Engineering architecture phase —
none chosen or implemented in this phase:

- Typed `ContextPack`/`LLMContext` materialization that preserves
  `trust_score`/`truth_status`/`worker_id` to the point of consumption
  rather than flattening to a string before any consumer sees it (this
  is the same underlying gap as the separately-tracked provenance-loss
  finding — see `Context → flat string` in the architecture gap
  analysis).
- Structural delimiting / explicit untrusted-data framing at prompt
  construction (e.g. clearly bounded context blocks with an explicit
  "this is retrieved data, not instructions" framing).
- A parser-output field distinguishing hypotheses substantiated by model
  reasoning from ones whose text happened to appear verbatim in supplied
  context.

### Residual risk

Even after remediation, retrieved content influencing model reasoning is
inherent to the system's purpose — the invariant to preserve is
*structural* (retrieved data cannot impersonate control structure), not
elimination of all retrieved-content influence on output.

### Related Context Compiler requirements

- Authority model (Gap 2, architecture comparison) — `trust_score`/
  `truth_status` are content-reliability signals, not an authority
  taxonomy distinguishing instruction from data.
- Provenance survival (Gap 1) — this finding is downstream of the same
  `Context → flat string` gap, viewed from the security side rather than
  the architecture side.
- Message/channel-aware materialization as a first-class Context
  Compiler concern, not an afterthought.

---

## Stale documentation (tracked separately, not part of CTX-AUTH-001)

`core/orchestrator.py`'s explanatory comment (~line 202) claims
`OrchestrationGovernor`, `AgentGovernor`, and `ConversationGuardrails`
"do not exist yet except the disconnected `MemoryGovernor`." All three
exist as real files under `core/governance/`, and `ConversationGuardrails`
is genuinely registered with `GovernanceKernel`
(`governance_kernel.py:348`). Same category of doc-drift as the
`PROJECT_INSTRUCTIONS.md` version mismatch and the `KNOWN_ISSUES.md`
DEBT-013 self-contradiction found earlier in this track — mechanical,
not a judgment call, not chased further here per phase scope.
