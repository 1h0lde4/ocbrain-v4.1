# Context Compiler Architecture Reconciliation

**Status:** Canonical decision artifact. Supersedes ad hoc conclusions
scattered across prior chat turns; does not supersede the six phase
documents in `docs/research/context-engineering/`, which remain the
evidence trail underneath this document. Where this document and a
phase document appear to disagree, the phase document's specific
evidence wins and this document should be corrected.

Written under, and subject to, `PROJECT_INSTRUCTIONS.md` §20.6
("Evidence-First Reconciliation," added upstream at `456b6ca` during
this document's own preparation): every claim below traces to a fresh
code read, test run, or execution-path trace performed within this same
research track, not to a carried-over prior-session summary — this is
noted explicitly rather than assumed, per that section's own standard.
That does not exempt this document from future re-verification. A
future session should treat this reconciliation the same way §20.6
requires treating any other prior claim: as a hypothesis backed by
cited evidence, not as ground truth merely because it is labeled
canonical.

**Baseline commit:** `fc5e354`. Confirmed via `git diff` against the
three commits that landed upstream while this document was being
prepared (`bb51d46`, `8db035e`, `456b6ca`) that none touch any file this
document makes a claim about — `core/`, `docs/research/context-engineering/`,
and the six phase documents are all unaffected by that upstream work.

---

## 1. Scope and Evidence Baseline

Six audit phases complete, each with its own evidence-backed document:
Graph isolation, Cache isolation, Artifact isolation, Tool-result
isolation, Revocation/deletion/retention, Secondary copies/export.
Preceded by an initial architecture-comparison pass (conducted earlier
in this research track, not separately filed as a document — the
findings from that pass are reconciled into Section 2 below) and an
external research sweep validating several architectural choices
against current (2025-2026) literature and prior art.

**Known, intentional, permanently-tracked failing regressions (5):**
`CTX-AUTH-001` (2 tests), `CTX-SCOPE-001`, `CTX-CACHE-001`,
`CTX-DELETE-001`. None are `xfail` — this repository has no such
convention; they are left genuinely red per existing practice for
tracked known failures, consistent with how pre-existing environment-
dependent failures are already handled elsewhere in this suite.

**Full-suite verification for this document, run fresh rather than
assumed from earlier partial runs:** `1366 passed, 11 failed` (the 5
regressions above, plus 6 additional failures in this sandbox
environment specifically — `tests/test_audit_fixes.py::TestA7SystemController`
— confirmed by direct traceback inspection to be the same missing
`chromadb` dependency affecting `modules/base.py`'s import chain, not a
new finding; verified rather than assumed given the test names
plausibly suggested otherwise at first glance). `test_stress.py`,
`test_fuzz.py`, and the other `chromadb`-dependent files were excluded
from this run for the same reason and were not re-verified as part of
this reconciliation.

**Verified live paths** (executed by real production traffic today):
K4.2 Intent Hypothesis generation (`core/cognitive/intent.py`);
`UnifiedMemory` write/read/delete; `cached_generate()`'s prompt cache
(unconditional per `generate_with_fallback()`'s own docstring);
`ContextMemory`'s write side (`orchestrator.py:510`); `brain_export`'s
HTTP endpoints (`interface/api.py`, `core/brain_api.py`).

**Verified dormant paths** (real code, not reachable in production
today because `main.py` always supplies `workflow_runtime`, which makes
the Legacy Compatibility Bridge's gating condition — `workflow_runtime
is None` — never true): the Legacy Compatibility Bridge itself;
`ContextMemory`'s read side (`format_for_prompt()`); the entire
`modules/*` routing architecture reachable only through that bridge,
including `modules/web_search`'s external-content ingestion and
`modules/system_ctrl`'s OS-action execution.

**Unaudited live subsystems** (confirmed real and referenced by live
callers, never in scope for any of the six phases): `core/memory/mem_vault.py`,
`core/memory/cognitive_vault.py`, `core/web_learning/pipeline.py`,
`core/memory/consolidation/consolidator.py`, `core/shadow/collector.py`.
See Section 7.

---

## 2. Canonical Architecture Model

Reconciling the actual repository against
`retrieval → Context IR → authority/trust/freshness/admission →
budgeting → reduction → materialization → sufficiency → ContextPack →
LLM boundary`:

| Stage | Status | Evidence |
|---|---|---|
| Retrieval | **Live, canonical.** `GraphRAGPipeline.retrieve()`: Query → Intent Analysis (deliberate no-op passthrough, not a bug) → Memory Retrieval (`UnifiedMemory.search()`) → Graph Expansion (`get_neighbors()`, outgoing-edges-only — a documented limitation) → Ranking → Evidence Consolidation. | `core/memory/retrieval/graphrag/pipeline.py` |
| Context IR | **Exists, substantially.** `Evidence`/`EvidenceSet` → `ContextBlock`/`ProvenanceRecord`/`ContradictionGroup` → `Context`. Structurally close to what a `ContextPack` needs — provenance fields (`trust_score`, `truth_status`, `worker_id`, `retrieval_method`, `graph_distance`) are richer than most systems studied in the external research sweep. | `core/memory/retrieval/context/context.py` |
| Authority / trust / freshness / admission | **Partial.** `trust_score`/`truth_status` are content-reliability signals, not an authority taxonomy (no `SYSTEM_POLICY`/`USER_INSTRUCTION`/`UNTRUSTED_CONTENT` distinction anywhere). Freshness: no `expires_at`/TTL semantics found anywhere in this retrieval path (flagged unverified early in this research track, never subsequently resolved — still open). Admission: exists narrowly — the graph-indexing eligibility policy (`GraphIndexer`) gates on `truth_status`, a real but content-quality-only gate, not scope-based. | `core/memory/graph/graph_indexer.py`; Gap 2 in this section's predecessor architecture-comparison |
| Budgeting | **Exists, flat.** Single greedy pass in rank order (`RetrievalContextBuilder`); no required/optional tiers, no protection for small-but-critical items. Token counting is `chars / 4`, an explicitly-documented placeholder. | `core/memory/retrieval/context/builder.py`, `token_counter.py` |
| Reduction | **Exists, well-designed.** MinHash/LSH dedup (reused from `learning/chunker.py`, not reinvented); deterministic union-find contradiction grouping that organizes but never auto-resolves. Among the strongest-matching stages against the target architecture. | `core/memory/retrieval/context/duplicates.py`, `builder.py` |
| Materialization | **Exists — and is the central architectural fault line.** `ContextAssemblyEngine.assemble_context()` builds the rich `Context` object above, then flattens it to a bare string. Confirmed by repository-wide search: zero production consumers of the structured object exist anywhere outside `assembly.py` itself — only test files touch it directly. | `core/memory/assembly.py:151` |
| Sufficiency | **Does not exist.** No `SUFFICIENT`/`PARTIALLY_SUFFICIENT`/`INSUFFICIENT` concept, no requirement-coverage tracking, anywhere. | — |
| ContextPack | **Does not exist** as a named, identified, fingerprintable artifact. The closest analog (`Context`) has no `pack_id`, `content_hash`, or `schema_version`, and — per Materialization above — never survives to a consumer regardless. | — |
| LLM boundary | **Exists, and is where the proven security/correctness failures live.** Bare `str.format()` interpolation with plain-text labels, no delimiter, no escaping, no untrusted-data framing. This is CTX-AUTH-001's exact location. The adjacent cache boundary (`cached_generate`) is where CTX-CACHE-001 lives. | `core/cognitive/intent.py:483-497`; `core/prompt/cache.py` |

**Headline conclusion:** roughly the first half of this pipeline
(retrieval through reduction) is already close to what a Context
Compiler needs, in some respects ahead of common practice found in the
external research sweep. The second half (materialization onward) is
where the real gap is — not because nothing exists, but because what's
built gets thrown away one step before it would matter.

---

## 3. Isolation Model

| Boundary | Model | Evidence |
|---|---|---|
| Shared cognitive memory | `UnifiedMemory`/`KnowledgeEntry` — process-global singleton, no task/execution/worker scoping in `search()` or the underlying storage. `worker_id`/`workflow_id` are captured at write time but never consulted as a retrieval filter. The graph layer is *more* permissive still — `worker_id`/`workflow_id` don't even survive into graph-node properties. Evidence-supported as **intentional** for a single-user system (Decision in Section 9), not an oversight. | Cache-isolation and Graph-isolation phase docs |
| Execution-local state | `WorkingMemory` (L0) — genuinely, structurally isolated: per-execution, in-process dict, explicitly documented as never persisting, with no code-level connection to `UnifiedMemory` beyond one docstring sentence naming the handoff boundary. This is the correct existing pattern to build on, not a gap. | `core/runtime/working_memory.py` |
| Artifacts | `WorkerResult.artifacts` — transient, in-memory, no persistence found anywhere in the live worker/execution/cognitive path. Exactly one cross-worker flow exists repository-wide (Evaluator → Reflection), and it's direct object passing within one request, not a shared store. | Artifact-isolation phase doc |
| Tool results | No LLM tool-calling concept exists. The only mechanism resembling real external-content handling (`modules/web_search`) is dormant; if activated, it has genuine per-module ChromaDB partitioning, not a flat shared pool. | Tool-result-isolation phase doc |
| Caches | Mixed, correctly differentiated by whether the cached value is scope-independent by construction. Safe-by-design: classifier embeddings, module maturity scores (pure functions of their key). Genuinely broken: `cached_generate`'s compression-before-hash collision (CTX-CACHE-001). Dead code: `core/runtime/efficiency.py`'s entirely uncalled second prompt cache. | Cache-isolation phase doc |
| Context packs | N/A — doesn't exist yet (Section 2). | — |
| Exports | `brain_export`'s HTTP endpoints are a real, localhost-scoped boundary-crossing mechanism with no content validation on import. | Secondary-copies-export phase doc |
| Historical retention | L4 Memory Archive — intentional, immutable (deletion genuinely blocked, verified in code), and confirmed to never participate in `search()`. A real, working boundary between "retained" and "currently authoritative." | Revocation-deletion-retention phase doc |
| LLM-visible context | The single most consequential boundary in the system. Where `ProvenanceRecord`'s authority/trust signals are lost before any consumer sees them, and where the one proven live prompt-injection-shaped weakness (CTX-AUTH-001) and the one proven live cache-collision weakness (CTX-CACHE-001) both sit. | Context-authority-threat-model |

---

## 4. Verified Findings Matrix

Scoped deliberately to the five concrete, evidence-backed,
regression-tested gaps — not the "clean" verified-safe findings from
each phase (those are conclusions in their own right, documented in
their originating phase docs, not remediation items).

| ID | Mechanism | Path | Status | Evidence | Impact | Existing control | Missing control | Test | Class |
|---|---|---|---|---|---|---|---|---|---|
| CTX-AUTH-001 | Bare `str.format()` interpolation of flattened retrieved context, no delimiter | `core/cognitive/intent.py` Intent Hypothesis prompt | **Live** (mechanism); precondition (untrusted content reaching memory) **dormant** — no `BrowserWorker` yet | `context-authority-threat-model.md` | Security — structural prompt-injection weakness | Strict `label\|score` regex (containment, not prevention) | Delimiter/authority framing at serialization; structured `LLMContext` | `tests/core/cognitive/test_intent_security.py` (2 tests) | Must fix before Context Compiler adoption |
| CTX-SCOPE-001 | `ContextMemory.save()`/`last_n()`/`format_for_prompt()` have no scope parameter anywhere | `core/context.py` | Write path **live** (K4.2); read path **dormant** (Legacy Bridge only) | `context-memory-path-audit.md` | Security + correctness — unconditional, no attack precondition needed if activated | Privacy gate on write only | Scope parameter on the full read/write/format chain | `tests/test_context_scope_security.py` | Hardening (not blocking Context Compiler — separate subsystem it doesn't currently plan to absorb) |
| CTX-CACHE-001 | `cached_generate()` hashes prompt only after lossy `compress_context(max_words=500)` | `core/prompt/cache.py`, unconditional via `generate_with_fallback()` | **Live**, unconditional, no adversarial input needed | `context-authority-threat-model.md` | Correctness + security — real cross-request response reuse | None on the collision itself | Hash the full prompt, or hash-then-compress | `tests/test_prompt_cache_security.py` | **Must fix before Context Compiler adoption** — highest-urgency item, live and needs no precondition |
| CTX-DELETE-001 | `delete()`'s own docstring promises `False` on L1 failure; code only logs and returns `True` | `core/memory/unified_memory.py` | **Live** | `revocation-deletion-retention-audit.md` | Correctness/reliability — callers cannot trust the return contract | Non-blocking try/except (masks rather than surfaces) | `return False` in the except block, or corrected docstring + caller-side verification | `tests/test_unified_memory.py::TestUnifiedMemoryDelete` | Hardening |
| CTX-EXPORT-001 *(assigned here — not yet in the threat-model doc)* | `import_module()` validates only `manifest.json` presence, no content/signature check, `overwrite=True` fully replaces a module's knowledge base | `core/brain_export.py`, exposed via `interface/api.py` + `core/brain_api.py` | **Live**, HTTP-reachable, localhost-scoped | `secondary-copies-export-audit.md` | Security — untrusted content silently becoming trusted, whole-knowledge-base scope | `host=127.0.0.1`; `CSRFHeaderMiddleware` (browser-cross-origin defense only, not local-process defense) | Bundle signature/checksum; content inspection; path restriction on `bundle_path` | None yet — recommended follow-up (Section 8) | Hardening |

---

## 5. Architecture Gaps

The recurring structural deficiencies, each already evidenced above,
restated here as the actual scope of what a Context Compiler needs to
build (not bugs to patch, capabilities to add):

1. **Structured context flattened before the model boundary** — the
   single most consequential gap. Everything downstream (explainability,
   replay, authority-aware serialization) is blocked by this one point,
   not by independent deficiencies in each of those areas.
2. **Missing authority taxonomy** — `trust_score`/`truth_status` conflate
   content quality with source authority; no `SYSTEM_POLICY` vs.
   `USER_INSTRUCTION` vs. `UNTRUSTED_CONTENT` distinction exists.
3. **Missing sufficiency model** — relevance ranking is solid;
   "does this contain what's needed" doesn't exist as a concept.
4. **Flat budgeting** — no required/protected/optional tiers; a small
   critical item can lose to bulk lower-value content.
5. **Approximate token counting** — `chars / 4`, explicitly a
   placeholder, never replaced.
6. **Absent context profiles / model profiles** — one integer budget
   parameter; no per-worker or per-model policy.
7. **Incomplete pack identity / fingerprinting** — no `pack_id`,
   `content_hash`, or `schema_version` on anything.
8. **Repository-context separation** — confirmed as a genuinely
   different domain, not an extension of `GraphRAGPipeline`: no
   `CoderWorker` exists yet, external research (`LongMemEval-V2`)
   independently supports treating code/repo context as needing a
   different mechanism than memory retrieval.
9. **Lifecycle / snapshot / branch semantics** — confirmed
   `NOT IMPLEMENTED` across every phase that touched it (artifacts, tool
   results); nothing to reconcile, only to design.
10. **Proven prompt/cache boundary failures** — CTX-AUTH-001 and
    CTX-CACHE-001 are not separate concerns from gaps 1-2 above; they are
    what happens in production when those gaps are left unaddressed.
    Treat them as proof-of-consequence, not as isolated bugs.

---

## 6. Security Model Reconciliation

Four named findings plus one newly-assigned ID, connected without
being conflated — each is a genuinely different mechanism:

- **CTX-AUTH-001** operates at the *prompt construction* layer (how
  retrieved text is serialized into a specific template).
- **CTX-CACHE-001** operates at the *cache key construction* layer (how
  a prompt is reduced before hashing) — entirely independent of what the
  prompt's content is or how it was built.
- **CTX-SCOPE-001** operates at a *different subsystem's* retrieval layer
  (`ContextMemory`, not `UnifiedMemory`) — no shared code path with the
  other three.
- **CTX-DELETE-001** is a *correctness* issue (a false success signal),
  not a content-boundary issue at all — included here for completeness
  of the security/correctness register, not because it shares a
  mechanism with the others.
- **CTX-EXPORT-001** operates at the *system boundary* (HTTP,
  filesystem), the only one of the five reachable from outside the
  process itself (bounded to localhost).

**What connects them architecturally, not mechanistically:** four of
the five (all but CTX-DELETE-001) are instances of the same higher-level
pattern — a boundary where content crosses from "something the system
retrieved or was given" to "something the system will trust or act on,"
with no explicit checkpoint at that specific crossing. This is exactly
what Gap 1 (Section 5) names directly and Gap 2 names as the missing
taxonomy to enforce it. The reconciliation's conclusion is therefore not
"fix five bugs" but "build the one missing checkpoint type, correctly,
once" — the five findings are where its absence happens to be currently
visible, not the full extent of where its absence matters.

---

## 7. Deferred but Confirmed-Live Subsystem Boundary

Explicit, so "not audited" is never later misread as "safe" or "dead":

- `core/memory/mem_vault.py` — JSON-file-backed store, referenced from
  `core/web_learning/pipeline.py`, `core/memory/dedup.py`,
  `core/memory/hybrid_retrieval.py`.
- `core/memory/cognitive_vault.py` — same pattern, referenced from
  `core/memory/consolidation/consolidator.py`.
- `core/web_learning/pipeline.py` — an entire pipeline, unexamined.
- `core/memory/consolidation/consolidator.py` — unexamined.
- `core/shadow/collector.py` — logs parallel reasoning traces for future
  fine-tuning data; liveness of its actual call sites not verified.

One relevant nuance surfaced while preparing this document, not from a
dedicated audit of these five: `modules/system_ctrl` (part of the
dormant `modules/` architecture, audited in the tool-result phase) has
prior, real, currently-passing test coverage for injection defenses
(`tests/test_audit_fixes.py::TestA7SystemController` —
shell-metacharacter rejection, safe platform APIs for opening
applications) from what appears to be an earlier, separate hardening
pass. This doesn't extend to the five subsystems above, which have no
comparable coverage found in this search — noted so the one positive
data point isn't generalized past what it actually covers.

**None of these five are in scope for the "must fix" tiers in Section
8** — they require their own dedicated audit pass, structured the same
way as the six phases here, before any priority classification would be
evidence-backed rather than guessed.

---

## 8. Prioritized Remediation

See the companion document,
`docs/reports/context-compiler-remediation-register.md`, for the
actionable, trackable version of this list. Summary of classification
logic:

- **Must fix before Context Compiler adoption:** CTX-CACHE-001 (live,
  unconditional, no precondition — the single highest-urgency item
  found across this entire research track), CTX-AUTH-001 (dormant
  precondition today, but its root cause — Gap 1 — is definitionally
  what Context Compiler exists to fix; building Context Compiler
  without closing this specific instance first means shipping new
  infrastructure around a known, already-proven hole), and Gaps 1-2
  from Section 5 as the core scope of the work itself, not optional
  extensions to it.
- **Must fix before Kernel/C-MoE integration:** the isolation-model
  questions in Section 3 that only become consequential with genuine
  multi-worker parallelism — specifically, whether per-module or
  per-worker scoping (rather than the current global-pool pattern)
  needs to tighten once C-MoE introduces real parallel specialists with
  potentially different trust levels. Not urgent under the current
  single-path execution model; will need re-evaluation before C-MoE
  lands, not before Context Compiler's own adoption.
- **Hardening:** CTX-SCOPE-001, CTX-DELETE-001, CTX-EXPORT-001 — each
  real and worth fixing, none currently exercised in a way that blocks
  Context Compiler's own scope, since Context Compiler's architecture
  (per Section 2) is built on `UnifiedMemory`/`GraphRAGPipeline`, not
  `ContextMemory` or `brain_export`.
- **Deferred research:** the five-subsystem boundary in Section 7 — not
  yet evidence-backed enough to classify further.

---

## 9. Architecture Decisions

**Decided, with evidence:**

- **Shared cognitive memory is the correct model; execution-local
  operational state should remain execution-local.** This is the
  specific question this whole isolation-audit sequence was launched to
  resolve. The evidence: `WorkingMemory` (L0) is already genuinely,
  structurally isolated per-execution and never touches `UnifiedMemory`
  in code — the correct pattern already exists and should be extended,
  not replaced. `UnifiedMemory`'s global-pool design is consistent
  with, not contradicted by, everywhere else this pattern was checked
  (the graph layer inherits the same shape). For a single-user,
  local-first personal system, one continuous knowledge base spanning
  tasks is the appropriate design, not a gap to close by imposing new
  task/execution-level retrieval scoping. **This evidence does not
  support imposing new memory-isolation boundaries as part of Context
  Compiler adoption.**
- **Deduplication and contradiction handling should be reused, not
  rebuilt.** Both are deterministic, already correct, already validated
  against external research (A-MemGuard's finding that LLM-based
  poisoning detectors miss the majority of poisoned entries directly
  supports the existing non-LLM-judgment design as the right call, not
  a dated one).
- **Repository/code context is a genuinely separate domain.** Both the
  code evidence (zero relationship between `GraphRAGPipeline` and
  anything code-shaped) and the external research
  (`LongMemEval-V2`'s finding that coding-agent-style evidence-gathering
  outperforms generic RAG for environment-specific knowledge) point the
  same direction.

**Not yet decided; evidence is insufficient:**

- Whether compression (LLMLingua-style or otherwise) belongs in the
  eventual pipeline at all — the external research flagged that the
  compressor itself typically requires another model call, in tension
  with this project's local-first/deterministic principles, and no
  OCBrain-specific benchmark exists to weigh the tradeoff.
- The exact shape of the authority taxonomy (Gap 2) — real, necessary,
  but not designed in this reconciliation; a research/design task, not
  a finding this evidence base can settle by itself.
- Whether `ContextMemory` should eventually be absorbed into Context
  Compiler's scope or left as a separate, hardened-in-place subsystem —
  Section 8 classifies its known issue as hardening specifically
  because this question is open, not because the issue is unimportant.

---

## 10. Exit Criteria

Before this track moves from research into implementation, all of the
following must be true:

1. CTX-CACHE-001 fixed (or the compression-collision mechanism removed
   entirely) — this must not still be live when new context-compilation
   infrastructure starts routing more traffic through the same cache.
2. A structural decision made and documented (not necessarily
   implemented) for how `LLMContext` materialization will avoid
   discarding `ProvenanceRecord`/authority information before reaching a
   consumer — Gap 1 requires a chosen direction before implementation
   work can safely begin, even if the direction is phased.
3. The authority taxonomy (Gap 2) has at least a draft schema — doesn't
   need to be final, needs to exist as more than a field name.
4. A decision recorded on whether Context Compiler's initial scope
   includes `ContextMemory` reconciliation or explicitly excludes it —
   currently undecided per Section 9, and implementation shouldn't start
   with that ambiguity live.
5. This reconciliation document itself has been reviewed and either
   confirmed or corrected — it is a synthesis of six phases' evidence,
   not independently re-verified against the repository as a whole in
   its own right.

Not required before implementation can begin, explicitly: resolving the
five-subsystem boundary in Section 7 (deferred research, not blocking),
or fixing CTX-SCOPE-001/CTX-DELETE-001/CTX-EXPORT-001 (hardening,
tracked, not gating).
