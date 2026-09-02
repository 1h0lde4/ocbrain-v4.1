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

## CTX-SCOPE-001 — ContextMemory Unscoped Recent-Conversation Injection

**Status:** VERIFIED CURRENT GAP (source-level finding + empirical
reproduction against the real class; production exposure depends on
which callers reach it — see below)

**Affected component:** `core/context.py::ContextMemory` —
`save()` / `last_n()` / `format_for_prompt()`

**Affected boundary:** Retrieval scope — no task/session/user/workflow
dimension exists anywhere in this subsystem's API surface

**Source:** Any caller of `ContextMemory.save()`. Confirmed production
callers (per `context-memory-path-audit.md`): the K4.2 branch
(`orchestrator.py:510`, write-only), the Legacy Compatibility Bridge
(`orchestrator.py:726`, both read and write), and the legacy K2.2
`PlannerWorker` (per an explanatory comment, not independently
re-verified against `planner.py` in this phase).

### Precondition

None required — no adversarial input, no attack precondition. Any two
organically distinct interactions saved via `ContextMemory.save()`
trigger this.

### Attack path (more precisely: mechanical failure path)

```
caller A saves a turn via ContextMemory.save(query, modules, answer)
        ↓
turns table: no scope column (id, timestamp, query, modules_used,
   answer only)
        ↓
caller B — completely unrelated — calls format_for_prompt(n)
        ↓
last_n(n): SELECT ... FROM turns ORDER BY id DESC LIMIT n
   -- most recent N interactions system-wide, unconditionally
        ↓
caller A's verbatim query/answer text appears in caller B's
   "### RECENT CONVERSATION" prompt section
```

### Current controls

None at the read path. A privacy gate exists on the *write* path
(`ContextMemory.save()` checks `privacy.can_save_history()` before
writing) but nothing scopes what gets read back once anything has been
saved.

### Evidence

- `core/context.py` — full `Turn`/`ContextMemory` implementation;
  `turns` schema has no scope column; `last_n()`'s only parameter is a
  result-count limit.
- `docs/research/context-engineering/context-memory-path-audit.md` —
  full production call-graph trace.

### Reproduction

`tests/test_context_scope_security.py::
test_recent_conversation_is_not_scoped_to_the_caller` — **FAILS**.
Saves one turn, then calls `format_for_prompt()` as an unrelated caller
would have to (no scope parameter exists to call it differently), and
finds the first turn's content present verbatim.
`test_last_n_has_no_scope_parameter_to_pass` — **PASSES** (documents
the API-surface fact directly via signature inspection, so it fails
loudly if the signature ever changes, prompting re-verification rather
than a silent assumption of "fixed").

This test does not dispute that recent-conversation continuity is a
real, intended feature for a single ongoing session — see the existing
`tests/test_context.py::test_context_save_and_retrieve` for that
positive case. The gap is the absence of any way to say "only my own
recent turns," not the feature's existence.

### Blast radius

Per the ContextMemory path audit: the *read* path
(`format_for_prompt()`) is confined to the Legacy Compatibility Bridge,
confirmed not production-exercised today (same status, same reason, as
the earlier-verified double-retrieval non-issue). The *write* path is
live in K4.2 today, meaning the data this mechanism would surface is
already accumulating even though nothing currently reads it back
unscoped. If the bridge is ever exercised — a config change, a
regression in the `use_k42_frontend`/`workflow_runtime` wiring, or a
future caller constructing `Orchestrator` without a `workflow_runtime`
— this becomes immediately live with no additional trigger required.

### Severity / confidence

Mechanism: **VERIFIED**, high confidence — direct source reading plus a
reproducible test against the real class. Production exposure today:
**NOT DEMONSTRATED** (dormant read path). Unlike CTX-AUTH-001 or
CTX-CACHE-001, this needs no adversarial input at all, only two
unrelated organic interactions — if the dormant path is ever activated,
severity should be treated as higher than CTX-AUTH-001's, not lower,
precisely because it requires nothing to go wrong on the attacker's
side.

### Future mitigation (not selected here)

- A scope parameter threaded through `save()`/`last_n()`/
  `format_for_prompt()` and the underlying `turns` table.
- Reconciling `ContextMemory` as a third persistence subsystem against
  `UnifiedMemory` generally, rather than patching this one symptom in
  isolation — see the path audit's architecture section.

### Residual risk

Even scoped correctly, raw verbatim turn injection with no provenance
carries the same authority/data conflation risk as CTX-AUTH-001 if the
bridge is ever activated — scoping alone does not address that
separately-tracked gap.

### Related Context Compiler requirements

Same as CTX-AUTH-001's — this is the same underlying class of gap
(structured/scoped materialization missing at a consumer boundary),
found at a second, independent subsystem.

---

## CTX-CACHE-001 — Prompt Cache Key Collision via Lossy Pre-Hash Compression

**Status:** VERIFIED CURRENT GAP (empirical reproduction against the
real function; confirmed live in production's LLM-call path)

**Affected component:** `core/prompt/cache.py::cached_generate`,
called unconditionally from `core/provider_mesh.py::generate_with_fallback`
("ALL calls go through the prompt cache before hitting the backend," per
that function's own docstring) — the same entry point
`core/cognitive/intent.py::generate_hypotheses()` and other K4.2 LLM
calls use.

**Affected boundary:** Cache-key correctness — the key is computed over
a lossy view of its input, not the input itself

**Affected data:** Any LLM response cached and later returned for an
unrelated request

### Precondition

None required. No adversarial input. Two organically different prompts
that both exceed 500 words and happen to share the same first-250/
last-250 words are sufficient — a realistic shape for the Intent
Hypothesis template specifically, since retrieved context sits in the
middle, between a fixed header and a fixed footer.

### Mechanism

```
prompt (>500 words, genuinely different from another prompt only in
   its middle section)
        ↓
compress_context(prompt, max_words=500)
   -- keeps first 250 words + " ... [COMPRESSED] ... " + last 250 words,
      discards everything else
        ↓
sha256(compressed) used as the cache key
        ↓
two genuinely different prompts sharing head/tail hash identically
        ↓
second caller silently receives the first caller's cached response
```

### Current controls

None on the read/collision side. On the write side: `cached_generate()`
has no exception handling around `provider.generate()`, so a raised
error correctly skips the cache write — errors are not cached. A
secondary, smaller issue: an empty-string response *would* be cached
before `generate_with_fallback()`'s own separate empty-response check
rejects it (that check runs in the caller, after `cached_generate()`
has already written the cache) — noted, not treated as part of this
finding's core mechanism.

### Evidence

`core/prompt/cache.py` — full `cached_generate`/`compress_context`
implementation. `core/provider_mesh.py:150-205` — confirms the
unconditional routing and the exact call site.

### Reproduction

`tests/test_prompt_cache_security.py`:
- `TestCtxCache001Collision::test_prompts_differing_only_in_compressed_middle_do_not_collide`
  — **FAILS**. Two 501-word prompts, confirmed non-identical, sharing
  head/tail: the second collides with the first's cached response.
- `TestBenignShortPromptBaseline` (both cases) — **PASSES**. Short
  prompts (under the 500-word threshold) don't collide, and identical
  prompts correctly reuse the cache (confirms this is a real,
  functioning cache being tested, not something accidentally disabled).

### Blast radius

Confirmed live and unconditional in the production LLM-call path used
by K4.2. Not yet traced: whether the specific shape required (>500-word
prompts sharing 250-word head/tail) occurs in practice for real Intent
Hypothesis prompts under typical retrieved-context sizes — flagged as
open, not assumed either way.

### Severity / confidence

Mechanism: **VERIFIED**, high confidence, empirically reproduced twice
(structural finding, then confirmed against the real function with a
differential control isolating the exact 500-word threshold as the
cause). Real-world trigger frequency: **UNKNOWN** — depends on
prompt-length distribution in actual production traffic, not measured
in this phase.

### Future mitigation (not selected here)

- Hash the full prompt, not a lossy compressed view of it.
- If compression before hashing remains desired for cost reasons,
  ensure the key still reflects the full input (e.g. hash-then-compress
  rather than compress-then-hash).
- Reconcile with `core/runtime/efficiency.py::PromptCache` — a second,
  entirely separate prompt-caching implementation found during this
  audit with zero live callers anywhere in the repository (dead code,
  not a current risk, but debt worth resolving alongside this fix
  rather than leaving two parallel implementations, matching the
  already-tracked DEBT-016 pattern for `ExecutionWatchdog`/
  `ProgressMonitor`).

### Residual risk

None identified beyond the fix itself — this is a pure correctness/
cache-key-construction issue, not one where the underlying feature
(caching LLM responses) carries inherent residual risk once fixed.

### Related Context Compiler requirements

Feeds the Context Compiler's dependency-aware cache identity and
invalidation requirements directly — a cache key must be a function of
everything the cached value actually depends on, not a lossy proxy for
it.

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
