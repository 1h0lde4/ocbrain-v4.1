# ADR-KERNEL-06: Instruction-Authority Taxonomy and the Intent Acceptance Boundary (REM-004 / CTX-AUTH-001b)

**Status:** **DRAFT.** Implemented and verified on branch `fix/ctx-auth-001b-rem004-authority-boundary-sep2026` (base: `main` @ `4669e21`). **Not reviewed, not approved, not on `main`.** Lifecycle for this repository: DRAFT → REVIEW → APPROVED → IMPLEMENTED → FINAL. Having working code does not move this ADR past DRAFT; that requires the owner's review and approval. Nothing in the code or docs may cite this ADR as APPROVED until then.
**Date:** September 20, 2026
**Classification:** Treated as Kernel v1.0 freeze blockers per the owner's directive in the implementation task. `docs/reports/context-compiler-remediation-register.md` records that whether REM-004 is Kernel-blocking is Moncif's call; his concurrence is **not** recorded here.
**Relates to:** `docs/research/context-engineering/context-authority-threat-model.md` (CTX-AUTH-001), `docs/reports/context-compiler-remediation-register.md` (REM-002/003/004), ADR-K4.2-H-01 (Layered Semantic Authority), ADR-K4.2-H-08 (trace/operation semantics), ADR-K4.2-H-09 (causal provenance), `docs/architecture/K4_2_CONTRACT_EVOLUTION_AND_DIAGNOSTIC_ARCHITECTURE_SPECIFICATION.md`.
**Competing proposal (not on `main`):** `ADR_KERNEL_05_CTX_AUTH_001B_DEFERRAL_PROPOSAL.md` exists on `origin/fix/ctx-auth-001-ctx-delete-001-sep2026`. It proposes deferring 001b. This ADR takes the opposite path because the owner classified 001b as a freeze blocker; KERNEL-05's status is the owner's call (see Decision Q5). The ID `KERNEL-06` was chosen to avoid colliding with it.

---

## The distinction this ADR keeps

- **REM-004** is the *architecture/design contract*: an authority taxonomy and the rules that make it non-forgeable.
- **CTX-AUTH-001b** is the *security acceptance condition*: `TestCtxAuth001ParserAcceptance` plus the invariant it stands for.

They are one piece of work, not two unrelated bugs. REM-004 defines what "authoritative" means; 001b is the test that it holds at the Intent → Goal boundary.

## The invariant

> No retrieved/untrusted content, and no model-generated proposal, can acquire authoritative user/system instruction status merely by appearing in an LLM completion, claiming authority, receiving a high confidence score, being paraphrased by the model, being serialized/replayed, or passing through a retry/cache/fallback path.

This ADR claims the **tested authority-escalation path** is closed. It does **not** claim prompt injection is impossible; see "Threat-model honesty".

---

## What tracing the live checkout found (evidence, not recall)

Everything below was re-derived from `main` @ `4669e21` by reading and executing code. Prior reports, comments and the deferral proposal were treated as hypotheses.

1. **The 001b test calls `generate_hypotheses()`, not `_parse_hypotheses()`.** `KNOWN_ISSUES.md`/`CURRENT_STATE.md` described it as isolating the parser, and ADR-KERNEL-05's "formal proof" that 001b is unsolvable rests on `test_clamps_out_of_range_scores` (`_parse_hypotheses("edge_low | 0.0\nedge_high | 1.0")`) and the sentinel test being "structurally identical, opposite outcomes". They exercise **different functions**. Once syntax parsing and security acceptance are separate stages, `_parse_hypotheses` still returns `edge_high | 1.0` (that test is unchanged and passes) while `generate_hypotheses` applies acceptance. The claimed contradiction does not exist. The proof was right that no *position/score/order/contiguity* signal exists, and right to reject keyword blacklists; it did not consider a whitelist-by-form label contract.
2. **The sentinel test's context is empty.** `assemble_context` is mocked to return `""`. No provenance or taint mechanism can distinguish the two completion lines, because nothing untrusted is in the input. Any fix that turns this test green must therefore act on the *form of the candidate itself*. This is stated plainly so the closure is not over-read (see D8).
3. **A real `MODEL_PROPOSAL → USER-authority` escalation exists downstream of the parser.** `form_goals()` builds `structured_form["semantic_description"] = "<label>: <request>"`. The planner's `_extract_constraints` then ran `_extract_explicit_constraints` over that composite string, and `ConstraintSource.EXPLICIT` is defined by the planner's own docstring (citing K4.2 §12) as "constraints the user stated directly in the request". Demonstrated against the pre-fix planner: request `"Summarize the design document for me."` (no constraint words) + a *perfectly valid* model label `only` produced `Constraint(kind=hard, source=explicit, rationale="scoping_constraint: only: Summarize…")`. A validating gate alone cannot close this (`only` is a legal label), so the planner needed a change.
4. **`generate_hypotheses` is a mock seam used by 10 existing tests** (`tests/core/cognitive/test_k42_completion.py`). A boundary that lives only inside it is bypassed by anything that returns a raw list. The boundary therefore has to be enforced at the **consumer** (`interpret_request`).
5. **Existing tests pin behavior that constrains the design:** lowercase multi-word labels are legitimate (`"creative writing"`, `"information query"`); `novel:` hypotheses at score 0.9 must stay accepted and ranked first; `novel:compound`/`novel:test` for unrelated requests must be accepted; the happy-path event count is exactly 3 (4 for compound). This ruled out a score ceiling for `novel:`, lexical grounding to the request, an identifier-only (no-space) grammar, and unconditional new events.
6. **Provenance is lost before the Intent consumer.** `ProvenanceRecord` carries `source`, `worker_id`, `workflow_id`, `confidence`, `trust_score`, `truth_status`, `retrieval_method`, `graph_distance`, `graph_path`, `seed_entry_id`. `ContextAssemblyEngine.assemble_context()` flattens the structured `Context` to `- {block.content}` lines. None of those fields survives to Intent, and **none of them is an instruction-authority concept**: they are reliability/lineage facts. `trust_score` = 1.0 is still RETRIEVED_DATA.
7. **No reusable authority mechanism exists.** `KnowledgeQuarantine` and `TrustManager` (`core/web_learning/`) have no production users outside their own modules, are file-backed, and are scoped to web-learning knowledge. `ValidationGate` (`core/cognitive/learning.py`) is the promotion path for *knowledge*, not for instruction authority. `GovernanceKernel` authorizes *actions*. `policy_version` / `state_epoch` / `task_generation` **do not exist in source on `main`** (they appear only in study documents), so no freshness mechanism could be reused.
8. **The prompt cache stores completion strings only**, keyed by the SHA-256 of the full prompt, and is provider-agnostic. `generate_with_fallback()` does not expose which provider served a completion. So authority state cannot be cached, and any recorded "provider" could be false provenance.
9. **`known_categories` is itself retrieved data.** `load_known_categories()` reads L3 entries through `memory.search`; it is interpolated into the prompt. The promotion path exists (`ValidationGate`, `ContentDomain.INTENT_ONTOLOGY`, governance action `intent_ontology_promote`, K4.2.6), but no production code constructs a `LearningCandidate` or calls the gate (grep of `core/`, `interface/`, `scripts/`), so the ontology is empty in practice unless populated out-of-band.
10. **K4.2 §2/§15 says hypotheses are "carried, never discarded before Plan Compilation."** That protects competing *interpretations*; a proposal that violates the admission contract is not one. It is retained as a bounded audit record rather than silently dropped (D13).
11. **Found by this ADR's own mutation testing (not by reading):** the bound on quarantine previews was 6 characters per source character, tighter than `safe_preview()`'s 8-character worst case (`\u10ffff`). Unreachable today (quarantined labels are ASCII by construction) but latent. Fixed, with tight-bound tests; the mutant that exposed it is now caught.

12. **Found by re-reading the final diff, not by any test:** the consumer seam trusted a carried inference whenever the *list* still matched it, but never checked that the inference belonged to *this request*. A stale inference from request A handed to request B would have lent B its lineage, including A's taint bit (A may have had no retrieved data while B did), under-reporting taint and leaking authority state across requests. Fixed with a binding check (request scope + request digest) and covered by three tests plus three mutants (each binding condition, and the whole check).

---

## Decisions

### D1. Four concepts, never one scalar

| Concept | Question | Where it lives |
|---|---|---|
| **Authority** | Who may *instruct*? | `InstructionAuthority` |
| **Provenance/origin** | Where did this value come from? | `Origin`, `InferenceLineage` |
| **Trust** | How reliable is it as *information*? | Existing `ProvenanceRecord.trust_score/truth_status`. **Not modelled here and never converted into authority.** |
| **Taint/lineage** | Was it influenced by untrusted material? | `InferenceLineage.retrieved_data_influence` |

### D2. Minimal taxonomy, precedence and conflict semantics (`core/cognitive/authority.py`)

| Authority | Precedence | May | May not |
|---|---|---|---|
| `SYSTEM_POLICY` | 3 | instruct; constrain everything below | — |
| `USER_INSTRUCTION` | 2 | instruct within policy; constrain model proposals | override policy |
| `MODEL_PROPOSAL` | 1 | propose options; be ranked among eligible options; be selected as a *hint* | instruct; reinterpret user/policy text; populate user-authority fields |
| `RETRIEVED_DATA` | 0 | inform (facts) | instruct; propose; change how higher-authority text is interpreted |

- **Conflict:** the higher-precedence source wins outright (`resolve_conflict`). No averaging, no `min()`/`max()` over trust or score, no aggregate authority. Precedence is used *only* to resolve conflicts; it is never computed from content and never compared with a confidence value.
- **A lower source cannot influence the interpretation of a higher one** (`may_influence_interpretation`).
- The model never chooses precedence. Precedence is a constant table.
- **Extension:** a new class (e.g. a future tool-result class) is added by ADR with an explicit precedence and origin mapping.

### D3. Authority conservation; content claims are not authority

- `assert_no_escalation(source, derived)` is the executable rule: any upward derivation raises. **No promotion/transition API exists**, and none is defined by this ADR. `RETRIEVED_DATA → USER_INSTRUCTION/SYSTEM_POLICY` and `MODEL_PROPOSAL → USER_INSTRUCTION/SYSTEM_POLICY` are impossible. A future explicit trusted transition (e.g. human confirmation) would need its own ADR.
- Authority is a **function of trusted `Origin`** via a read-only table. Labels, prefixes, keywords, markdown, quotes, and words like "system", "trusted", "override" never influence it. `SYSTEM_POLICY | 1.00` is a string a model wrote.
- **Namespace disjointness.** Every serialized trusted token (authority, origin, category class, disposition, reason, outcome) is `UPPER_SNAKE_CASE`. Model-controlled labels are validated (D8) to live in a disjoint lowercase namespace, so a model string can never be textually equal to a trusted token in a log, event or replayed payload. This is a type-confusion defense at serialization boundaries, and it is tested exhaustively over every trusted token.

### D4. Information authority ≠ action authorization

This layer answers "how authoritative is this *information/instruction source*?" `GovernanceKernel` answers "is this *action* permitted?" Nothing here calls, wraps or duplicates it. DRIFT-10 (Intent/Planner must not call `evaluate_action()`) still passes, a test asserts the new modules never import governance, and the only action-authorization point remains `compile() → GovernanceKernel.evaluate_action()`. An "authoritative" hypothesis cannot bypass it because authority is not a parameter of authorization. Cognitive reasoning proposes; Kernel governance authorizes; execution enforces.

### D5. Non-forgeable origin; immutable accepted state

- `AcceptedHypothesis` is a frozen dataclass that can be created only through `mint_model_proposal` / `mint_policy_default`. Those functions hard-code `Origin.INTENT_MODEL` (or `RUNTIME_DEFAULT`) and *derive* authority; there is no parameter through which a caller or a model string can choose either. It cannot carry USER, SYSTEM or RETRIEVED_SOURCE origin at all.
- Direct construction, field assignment, and `dataclasses.replace()` all fail (the mint token is not carried). It re-derives authority from origin and recomputes its own binding digest on construction and on deserialization; serialized authority is never trusted.
- **Honest limit:** the mint token is a module-private object, not a cryptographic capability. Code that deliberately imports a private symbol is outside this threat model (model text and retrieved text cannot do that). The binding digest detects inconsistency and naive tampering; it is **not** authentication of persisted state.

### D6. Data contract: separate the parsed claim from the accepted state

`IntentHypothesis` is **unchanged** and keeps its meaning: a parsed claim by the model. A distinct `AcceptedHypothesis` (frozen, self-verifying) carries the security meaning, and `ProposalDisposition` records rejected/quarantined input. Redefining `IntentHypothesis` in place (adding a mutable `authority` field) was rejected: it would corrupt a frozen contract and leave authority mutable.

### D7. Parser and acceptance are separate; acceptance sits at the consumer seam

```
raw completion ──(_parse_hypotheses: SYNTAX only, unchanged)──► ParsedProposal[]
   ──(accept_proposals: admission + provenance, core/cognitive/intent_acceptance.py)──►
AcceptedHypothesis[] (eligible, ranked) + ProposalDisposition[] (audit) ──► Intent.selected
```

- `infer_hypotheses()` is the additive richer entrypoint; `generate_hypotheses()` keeps its exact signature and `List[IntentHypothesis]` return type (a `list` subclass that also carries the inference).
- **`interpret_request()` enforces the boundary itself** on whatever `generate_hypotheses()` returned. If the list carries its inference, *still equals what that inference accepted*, **and the inference is bound to this request** (same request-scope `trace_id` and same request digest), it is used; **any other list (a test double, a foreign implementation, a mutated list) is treated as unvetted claims** and crosses the same gate, with conservative lineage (retrieved-data influence assumed, since it cannot be ruled out). Unknown lineage fails closed toward more suspicion.
- Static tests assert: `_parse_hypotheses` is referenced only inside `infer_hypotheses`; envelopes are constructed only in `authority.py`; mint functions are used only by the gate; `Intent(...)` is built in production only by `interpret_request`; only `intent.py` imports the gate.

### D8. The label-admission contract (what actually turns 001b green, and what it does not do)

A category label is a **short lowercase name**: words of `a-z0-9` (first character a letter) joined by single spaces or underscores, ≤ 64 characters, optionally prefixed `novel:`; the bare token `novel` is also valid. Formally: `label := "novel" | ["novel:"] name`, `name := [a-z][a-z0-9]* ([ _][a-z0-9]+)*`. Labels shaped `[A-Z][A-Z0-9_]*` (after an optional `novel:`) are **QUARANTINED** (`RESERVED_NAMESPACE`); everything else outside the contract is **REJECTED** (`LABEL_GRAMMAR`). The gate rejects rather than repairs: lowercasing `CONTEXT_SENTINEL_INJECTED` would launder a spoof into a valid label.

This is a **whitelist by form**, not a blacklist by content: it never inspects meaning, so there is no keyword list to evade, and uppercase/punctuation/markdown/quotes/delimiters/zero-width/bidi/homoglyph/fullwidth/encoded (`%49`, `\u0049`, base64) forms are all outside it by construction.

**What it does:** closes the 001b sentinel test with its assertion untouched; removes the reserved namespace from model control (D3); keeps free-form markup and Unicode tricks out of `semantic_description`; bounds diagnostics.

**What it does not do:** it does **not** detect a *well-formed* hijack (a lowercase `create_account | 1.00`). That is accepted as an ordinary `MODEL_PROPOSAL`, contained by D2–D5, D10 and D14, not eliminated. No deterministic, content-agnostic rule can tell it from a legitimate context-informed proposal (the benign control `explain_docstring_convention`, derived from context vocabulary the request never used, is lexically indistinguishable). The prompt template (v2) states the same contract to the model, so the format we ask for equals the format we accept.

**Alternatives rejected:** keyword/`novel:` blacklist (gameable; explicitly forbidden); lexical grounding to the request (breaks pinned tests and legitimate context use); score ceiling for `novel:` (breaks pinned 0.9 tests); identifier-only grammar (breaks pinned `creative writing`); LLM-based detector (violates AUTH-15); per-call nonce/wire-format change (KERNEL-05's own analysis: breaks legitimate lines); dual-LLM "clean-room" pass (see External validation: real utility cost, non-deterministic, extra calls).

### D9. Selection is protected: eligibility precedes ranking

Per candidate: score validated → label admitted → duplicates collapsed (the **lowest** claimed score survives, order-independently, so repetition cannot raise confidence) → candidate set capped at 5 **by completion position** (score is untrusted, so it cannot decide who survives) → envelopes minted → *only then* stable sort by score. A suspect candidate at 1.00 never reaches the sort. `Intent.selected` can only be an accepted proposal or the trusted-code default.

### D10. Taint and lineage: a small explicit contract

For this subsystem, **taint means: retrieved data was part of the prompt that produced the proposal.** It is conservative ("may have been influenced", never "was hijacked"), is recorded per invocation (a model output cannot be attributed line by line), and **does not change the proposal's authority**. `InferenceLineage` records `scope_id` (the existing `trace_id`; no second identity system), `route`, `template_version`, `prompt_digest`, and a tuple of `LineageInput`s (`request`→USER_INSTRUCTION, `context`→RETRIEVED_DATA, `known_categories`→RETRIEVED_DATA), each keeping **its own** origin/authority. Nothing is aggregated (no `min()`, no highest trust). Ontology categories are RETRIEVED_DATA by channel; no retrieved→system promotion is defined. Provider identity is deliberately **not** recorded (finding 8).

### D11. Scoping, freshness, TOCTOU

- **Scope:** bound to `trace_id` (existing) and to the exact `prompt_digest`. No module-level mutable authority state exists (asserted by AST test); each inference builds its own lineage and envelopes, so request A has nothing to hand request B.
- **Freshness:** no cross-system mechanism exists (finding 7) and none is invented. `policy_version` (`intent-acceptance/1`) is local to the gate; a different version on replay raises `StaleAcceptanceError`. Acceptance is re-derived on every inference (post-cache), so stale acceptance cannot survive a policy change.
- **TOCTOU:** the envelope is immutable and self-contained. Because the frozen K4.2 carriers (`Intent.selected`, `dimensions.category`) are mutable, `form_goals()` also revalidates at the consuming boundary: when an envelope is attached, both carriers must still equal what it accepted, else Goal formation fails closed to the open-category default with no provenance. An Intent with no envelope (hand-built/legacy) is **UNATTESTED** (`category_provenance is None`): legacy behavior, no provenance, never user-authority.
- **Replay:** `AcceptedHypothesis.from_dict()` is *consistency verification*, not an authority grant (strict keys, enum validation, authority re-derived from origin, binding recomputed, policy version checked). An authoritative replay decision re-runs the deterministic gate. Event records are evidence, never a source.

### D12. Failure semantics — recovery never raises authority

| Situation | Outcome | Result | Reason |
|---|---|---|---|
| Retrieval error | (proceeds) | inference with **no** retrieved context | less untrusted input, not more authority |
| Provider error / all providers failed | `PROVIDER_FAILURE` | trusted-code default `novel`@0.1 | fail closed |
| Empty/None completion | `NO_OUTPUT` | default | model had no answer |
| Non-text completion / no parseable line | `PARSE_FAILURE` | default | malformed |
| Every proposal rejected/quarantined | `ALL_REJECTED` | default | **security decision, distinct from "no answer"** |
| Unexpected error in parse/gate | `INTERNAL_ERROR` | default, logged | fail closed, labelled |
| Cancellation | propagates | — | `BaseException` never swallowed |

The default carries only the fixed token `novel`; **no rejected content is ever copied into it**. It has origin `RUNTIME_DEFAULT`, whose authority is defined as the class of the path it replaces (`MODEL_PROPOSAL`), so recovery preserves rather than raises authority.

### D13. Reject vs. quarantine

Both exist, minimally. **REJECTED** = contract violation with no forensic value: reason code + digest + length + position + score claim, no text. **QUARANTINED** = label shaped like a trusted token (possible spoofing): additionally a bounded (≤ 48 source chars), escaped preview. Neither enters ranking, selection, prompts or Goals. Records are capped at 16 per inference with exact totals kept. These are audit records for K4.2's "never silently discarded", not competing interpretations.

### D14. Downstream conservation

| Value | Authority | Consumers | Guarantee |
|---|---|---|---|
| `RawRequest.text`, `structured_form["description"]`/`["raw_request"]` | `USER_INSTRUCTION` | decomposition prompt; **explicit-constraint extraction** | unchanged (K42-001 preserved); the *only* text mined for `ConstraintSource.EXPLICIT` |
| `Intent.selected`, `dimensions.category`, `structured_form["category"]`, label prefix of `semantic_description` | `MODEL_PROPOSAL` (+taint) | planner `novel` hint; capability-discovery ranking | envelope preserved on `Goal.category_provenance`; consuming-boundary check; excluded from EXPLICIT constraints |
| `Goal.confidence` | derived from a model-reported score | advisory planner hints | not authority; documented residual (R3) |
| `ExecutionPlan` | a `MODEL_PROPOSAL` artifact (planner output) | `compile()` → `GovernanceKernel.evaluate_action()` | carries no authority to execute |

**Planner change (required by finding 3):** `_extract_constraints` now extracts explicit constraints from `description` (per-part text for compound goals) then `raw_request`, not from `semantic_description`. This corrects toward the planner's own definition of "explicit" (its docstring, citing K4.2 §12). For every pinned test, behavior is identical; it differs only when a model label contains constraint vocabulary. `semantic_description` remains the input to capability discovery, unchanged.

### D15. Diagnostics

Existing `EventStream.append` only. Additive optional keys on `cognitive.intent_hypotheses_generated` and `cognitive.intent_interpreted`; a new `cognitive.intent_proposals_rejected` event **only when something was rejected**, so the ordinary sequence stays 3 events (4 for compound). Payloads carry hashes and closed-vocabulary tokens only: no prompt, completion, request text or rejected label text. Logs carry counts, digests and exception *type names*; the `INTERNAL_ERROR` path additionally logs a traceback for developers (the authority errors it can raise have static messages, but an arbitrary unexpected exception's message is not controlled by this ADR).

---

## Frozen K4.2 compatibility audit

| Contract | Before | After | Classification |
|---|---|---|---|
| `IntentHypothesis` | `label`, `score`, `embedding_ref` (mutable) | identical; meaning = parsed claim | **UNCHANGED** |
| `_parse_hypotheses()` | regex syntax parser | body byte-identical; docstring states syntax-only role | **UNCHANGED** |
| `Intent` | existing fields | + `selected_proposal`, `inference_outcome`, `rejected_proposals` (all defaulted) | **ADDITIVE** |
| `Goal` | existing fields | + `category_provenance` (defaulted) | **ADDITIVE** |
| `Goal.structured_form` | keys as today | unchanged; `description` source rule (K42-001) preserved | **SEMANTICALLY PRESERVED** |
| `interpret_request()` | signature; 3 events (4 compound) | signature unchanged; happy-path events unchanged; selection is among gate-accepted hypotheses | **SEMANTICALLY PRESERVED** |
| `generate_hypotheses()` | returns every parseable line, ranked | signature/type unchanged; now returns only contract-compliant proposals (fallback `novel`@0.1 as before) | **REQUIRES ADR** (this ADR: a deliberate tightening of a frozen public function's output set) |
| Explicit-constraint source (planner) | `semantic_description` ∨ `description` ∨ `raw_request` | `description` ∨ `raw_request` | **REQUIRES ADR** (this ADR: correction toward K4.2 §12) |
| Events | 2 intent events | + optional keys; + 1 event only on rejection | **ADDITIVE** |
| Serialization | `dataclasses.asdict` | + nested keys; str-enums are JSON-safe | **ADDITIVE** |
| Prompt template | v1 (unversioned) | v2 adds the label contract line; version recorded in lineage; 001a counts unchanged | **ADDITIVE** (changes cache keys, intended) |
| Existing tests | 1501 pass / 6 fail | 0 assertions changed; `test_intent_security.py` docstring/comments corrected (AST-identical excluding docstring) | **UNCHANGED** |

No **BREAKING** change was found. Two rows are **REQUIRES ADR** and are exactly what this DRAFT asks the owner to approve.

## Legacy / dormant path audit

`interpret_request()` is the only production `Intent` constructor. The Orchestrator reaches it only on the K4.2 branch behind `use_k42_frontend` (**`true` by default in `config/settings.toml`**, `False` as the constructor default); with the flag off the legacy path never produces or consumes hypotheses. `generate_hypotheses()` direct callers are tests only. `_parse_hypotheses` has one production caller. Hand-built `Intent(...)` objects exist only in tests and are UNATTESTED. Nothing rebuilds `Goal`/`Intent` from dicts. Nothing outside `intent.py` reads `Goal.alternatives`/`Intent.hypotheses` (it is write-only), so post-acceptance mutation of non-selected labels has no production consumer (R10). `KnowledgeQuarantine`/`TrustManager` are dormant and unrelated. **Claim: no relevant alternate production path obtains authority-unsafe hypotheses while bypassing the boundary** (static tests + the exhaustive greps behind them). Out of scope and untouched: CTX-SCOPE-001's unscoped `ContextMemory.format_for_prompt()` path.

## External validation (§34)

Read in full: OWASP GenAI *LLM01:2025 Prompt Injection* (primary page). Validated from abstracts/search excerpts only (full text **not** reviewed): Wallace et al., *The Instruction Hierarchy* (arXiv:2404.13208); Hines et al., *Spotlighting* (arXiv:2403.14720); Debenedetti et al., *Defeating Prompt Injections by Design* / CaMeL (arXiv:2503.18813); memory-poisoning work (MINJA arXiv:2503.03704; MemoryGraft arXiv:2512.16962; MPBench arXiv:2606.04329; MemLineage arXiv:2605.14421); OWASP Top 10 for Agentic Applications 2026 (ASI01 Agent Goal Hijack, ASI06 Memory & Context Poisoning). Material conclusions only:

- **OWASP LLM01** says fool-proof prevention is unclear and lists impact-reducing measures. Three map directly: define expected output formats and validate them with deterministic code (D8); enforce least privilege and keep privileged functions in code rather than with the model (D4: Governance stays the sole action authority); segregate and identify external content (001a + D10 lineage). It also lists encoded/multilingual obfuscation, which a whitelist-by-form is immune to by construction. → *Claim containment, not elimination.*
- **Instruction Hierarchy** argues models should defer to higher-privilege instructions on conflict, achieved by training (probabilistic). → D2 is the deterministic, runtime-enforced counterpart; a model-trained hierarchy would be complementary defense in depth and never the enforcer (AUTH-15).
- **Spotlighting** shows that marking input provenance in the prompt reduces attack success, and that delimiters alone can be defeated by attacker-inserted delimiters (which is what 001a's neutralization addresses). → prompt-side marking is probabilistic; datamarking retrieved context is a *future* Context Compiler option, not implemented here.
- **CaMeL** derives control flow only from the trusted query, tags values with provenance/capabilities, and enforces policy outside the model, at a measured utility cost (reported 77% vs 84% task success). → adopted: provenance-tagged values and deterministic out-of-model enforcement. **Not adopted:** "Intent from the trusted query only", because OCBrain's Intent inference legitimately uses retrieved context. This is the main reason a well-formed hijack of the category *hint* is contained rather than eliminated (R1), and a clean-room classification pass is the recorded future option.
- **Memory-poisoning research** finds untrusted content crossing the memory-write boundary and later steering reasoning, and recommends source-aware retrieval and lineage-guided enforcement. → retrieved memory is RETRIEVED_DATA by channel whatever its `trust_score`; `LineageInput` is the seam where per-source provenance can attach when the Context Compiler exposes it. Memory-*write* governance is out of scope (R9).

## Threat-model honesty

Preserved from CTX-AUTH-001: **structural weakness = verified; synthetic reproduction = verified; real hostile exploitation = not demonstrated.** After this change the claim is exactly: *the tested authority-escalation paths are closed* (model output, retrieved content, score, paraphrase, retry/fallback, cache, serialization/replay, concurrency, and the label→explicit-constraint path); *not* "all prompt injection is impossible" and *not* "OCBrain is secure against arbitrary model manipulation".

## Residual risks

- **R1** A well-formed hijack of the category hint is accepted as a tainted `MODEL_PROPOSAL`; it can influence capability *ranking* via `semantic_description`. Contained by typing, taint visibility and governance at compile; not detected. Test: `TestResidualRisk`.
- **R2** Lowercase multi-word labels (≤ 64 chars) carry short free text into `semantic_description` (discovery ranking). The constraint channel is closed; the ranking channel is not.
- **R3** `Goal.confidence` derives from a model-reported score and feeds advisory planner hints.
- **R4** Per-source retrieval provenance is still flattened before Intent (REM-003 Gap 1); lineage records digest+size per input class only.
- **R5** `known_categories` are RETRIEVED_DATA by channel; the gate filters non-contract entries. The promotion path (`ValidationGate` / `intent_ontology_promote`) exists but has no production caller; whoever wires a producer must make it enforce the same label contract.
- **R6** The mint token is not a cryptographic capability and the binding digest is unauthenticated; in-process malicious code and persisted-state tampering by a privileged actor are out of scope.
- **R7** Actual serving provider is unattributable (finding 8).
- **R8** **The label contract has not been measured against a real local model in this environment** (no Ollama available in the sandbox). If a real model emits labels outside the contract, the result is `ALL_REJECTED` → `novel`@0.1 with a distinct, visible outcome (safe, but degraded). The false-rejection rate is unknown; measuring it is a follow-up.
- **R9** Memory *write* governance (persistent poisoning) is out of scope.
- **R10** Post-acceptance in-process mutation of non-selected labels reaches only the write-only `Goal.alternatives`.

## Verification evidence (measured on this branch, not recalled)

- Baseline (unmodified `main` @ `4669e21`): focused 1 failed/102 passed; full suite **6 failed / 1501 passed**; drift 15/15; the 5 non-001b failures are `KeyError: '_type'` from the installed chromadb (environment-only).
- After: full suite **5 failed / 2000 passed** (zero new failures; 001b fixed; the same 5 environment failures); drift **15/15 PASS**; `mypy` (repo configures none): new modules clean, `intent.py`/`planner.py` carry exactly the 12 pre-existing errors of `main` (the two error sets are identical once line numbers are ignored; an earlier draft of this line said 11, a miscount from a truncated listing).
- **498 new tests:** `tests/core/cognitive/test_authority.py` (159), `test_intent_acceptance.py` (174, including a seeded generated-input property suite), `test_intent_authority_boundary.py` (165: cases A–G, mixed origin, failure/fallback, consumer-seam bypass, provider/cache, concurrency, serialization/replay, immutability/TOCTOU, bounded events, static "no alternate path", six full-path integration tests: five drive real `RawRequest → prompt → parser → gate → Intent → Goal → plan()` with only the two LLM calls and the retrieval text supplied by the test, and the sixth re-runs the properties through the real provider mesh and prompt cache; plus a 14-content-case × 6-state matrix (fresh, cached, fallback provider, serialized, replayed, concurrent = 84 cells) asserting origin, authority, request binding, provenance, eligibility, selection and downstream effect per cell). The 001a and 001b tests pass with **assertions unchanged**.
- **Mutation testing:** 14 inherited regression mutants + 21 authored during this review (e.g. planner mining the label again, consuming-boundary check removed, mint guard removed, taint always false, RUNTIME_DEFAULT raised to USER_INSTRUCTION, dedupe keeping the highest score, cap removed, reserved namespace no longer quarantined, unknown fields tolerated, stale policy ignored, and three for the request/scope binding of a carried inference). **All caught.** One survivor (unbounded quarantine preview) revealed a real test gap and finding 11; both fixed and re-verified.
- **Not verified here:** behavior against a real LLM provider (R8); full text of the cited research papers.

## Decisions requested from the owner (none self-approved)

- **Q1** Approve ADR-KERNEL-06 (taxonomy, precedence, non-forgeable envelope, acceptance boundary) → REVIEW → APPROVED.
- **Q2** Confirm that the closed-world **label contract** (D8) is an acceptable closure mechanism for the 001b *test* (which has an empty context), given that it does not detect well-formed hijacks; the alternative is leaving 001b open until the Context Compiler.
- **Q3** Confirm freeze-blocker classification with Moncif (register: his call).
- **Q4** Approve the two **REQUIRES ADR** rows: `generate_hypotheses()` output tightening, and the planner explicit-constraint source correction.
- **Q5** Decide the fate of `ADR_KERNEL_05_CTX_AUTH_001B_DEFERRAL_PROPOSAL.md` (unmerged) if this ADR is approved.

## Follow-ups (recorded, not done)

Measure label-contract false rejections on a real local model; per-source provenance at the Context Compiler (REM-003); optional clean-room classification when retrieved context is present; datamarking of retrieved context; make the `INTENT_ONTOLOGY` promotion producer, when wired, enforce the label contract; memory-write governance for persistent poisoning; ADR-K4.2-H-06's deferred K4.1-L reconciliation is unaffected.

## Lifecycle

DRAFT (this document, Sept 20, 2026). Next: REVIEW by the owner. Only after APPROVED may the code comments and register stop describing it as a draft; only after merge and a passing post-merge suite may it be IMPLEMENTED; FINAL is reserved for the owner.
