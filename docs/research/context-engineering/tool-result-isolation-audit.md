# Tool-Result Isolation Audit

Fourth phase of the isolation audit sequence (Graph ✅ → Cache ✅ →
Artifact ✅ → Tool-result ✅ → Revocation/deletion/retention → Secondary
copies/export → Final reconciliation). Traced against commit `13b86f8`.

## Disambiguation: there is no LLM tool-calling concept in this
repository

Repository-wide search for `ToolCall`, `ToolResult`, `tool_use`,
`tool_call_id`, `function_call` returned zero matches. There is no
mechanism anywhere for a model to decide to invoke a function and
receive a structured result back — the "tool result" framing this
audit phase inherited from general agent-security literature doesn't
map onto anything that exists in this codebase today. Three narrower,
real mechanisms are the closest analogs, traced below.

## 1. `AdapterRuntime` / `CapabilityExecutorWorker` — the closest thing
to "capability execution," and it does exactly one thing

Confirmed via `capability_executor.py`'s own detailed docstring: the
*only* `capability_type` registered anywhere in this repository today
is `"llm_completion"`. `CapabilityExecutorWorker` exists solely to
bridge `WorkflowNode.worker_type == capability_type` to
`WorkerRegistry`/`AdapterRuntime.invoke()`. There is no coding,
web-search, file-access, or any other capability live in the K4.2
execution path. Nothing here produces genuinely external or untrusted
"tool results" — an LLM completion is not a different trust category
from the rest of the cognitive pipeline already audited.

## 2. Skill system — real code, zero live callers

`core/skills/skill_interface.py` (`BaseSkill`) is fully implemented,
including a per-instance cache keyed by input kwargs (see the
cache-isolation audit). Confirmed unwired by two independent searches:
a narrow grep for actual import/instantiation (zero hits) and a broad
grep for any mention of `skill_interface`/`SkillInterface`/`BaseSkill`
repository-wide, which surfaces exactly one hit — a comment in
`core/cognitive/learning.py` describing the skill system in passing
("`core/skills/skill_interface.py` defines Skill *execution* (BaseSkill)
with no promotion/creation path"), not a functional call. Dormant, same
status as `CoderWorker`/`ReActWorker`/`BrowserWorker`.

## 3. `modules/*` — genuinely built, genuinely handles external content,
confirmed dormant

This is the one mechanism worth tracing in real depth, because unlike
the other two it actually does something interesting.
`modules/web_search/module.py::run()` performs real external fetches
(`httpx`, `trafilatura` for extraction) and calls
`self.ingest(live_chunks, meta)` with real provenance metadata attached
per chunk (`timestamp`, `quality_score`, `source_type`, `source_url`).

**Storage and scope, traced precisely:**
- `ingest()` (`modules/base.py:139`) writes via `self.db.upsert(documents=chunks, metadatas=metadatas, ids=ids)`.
- `self.db` is a **per-module ChromaDB collection**, confirmed via
  `_get_or_create_collection()`: `self._chroma_client.get_or_create_collection(name=self.name, ...)`.
  This is genuine, structural partitioning at the storage layer — the
  `web_search` module's ingested content lives in a different
  collection than `coding` or `knowledge`'s — not merely a cache-key
  convention layered on top of one shared store.
- `ingest()` also invalidates `_RETRIEVE_CACHE` entries scoped to
  `self.name` on every new ingest, keeping the cache-isolation audit's
  earlier characterization of that cache accurate.
- Scope granularity is **per-module, not per-task/execution/user** —
  coarser than the audit's ideal, but real, and a meaningfully different
  (better) situation than `ContextMemory`'s completely unscoped `turns`
  table.

**Reachability, the decisive question:** a targeted search across
`core/orchestrator.py` and `core/module_registry.py` for any
`web_search`/module-dispatch-by-name reference outside the already-
confirmed Legacy Compatibility Bridge returned zero matches. The only
path to `modules/web_search/module.py::run()` is through
`self.router.route(mod_name, query, self.context)`
(`orchestrator.py:789`), itself confirmed part of the same dormant
bridge sequence traced in the ContextMemory path audit and the
cache-isolation audit. **This mechanism is real, well-built, and not
currently exercised in production**, for the same reason as everything
else gated behind that bridge.

## Required distinctions

- **Shared cognitive/artifact state by design:** the per-module ChromaDB
  partitioning *is* a real design decision that would need explicit
  evaluation the moment this path activates — is per-module scope
  (rather than per-task/user) intentional and sufficient, or does it
  need tightening? Not resolved here; flagged for whoever activates
  this path.
- **Cross-execution access that is actually unauthorized:** NOT
  DEMONSTRATED. Not reachable in production today.
- **Stale/stale-reference reuse:** partially applicable if activated —
  `ingest()`'s cache invalidation is real but only covers
  `_RETRIEVE_CACHE`'s in-process copy; whether the underlying ChromaDB
  collection itself needs freshness semantics beyond what's already
  documented for the cache generally is unresolved.
- **Collision/overwrite:** `ids = [f"{self.name}_{abs(hash(c))}_{int(time.time())}"]`
  — collision risk is low (hash + timestamp) but not zero, and not
  independently verified as collision-free in this phase.
- **Provenance loss:** better here than elsewhere audited so far —
  `source_url`/`source_type`/`quality_score`/`timestamp` are attached at
  ingest time. Whether this provenance survives through
  `retrieve_async()` back to a consumer, or gets discarded the way
  `ProvenanceRecord` does at `ContextAssemblyEngine`, was not traced in
  this phase — flagged as open, not assumed either way.
- **Trust/authority escalation:** genuinely relevant *if activated* —
  externally-fetched web content flowing into a retrieval store that
  later feeds a prompt (via `format_for_prompt()`, per the earlier
  ContextMemory/cache findings) is exactly the MemoryGraft-shaped
  pattern the external security research described. Currently dormant,
  so NOT DEMONSTRATED as a live issue, but this is the most concrete,
  most directly analogous live-precondition candidate found anywhere in
  this audit sequence for the CTX-AUTH-001-style precondition
  ("attacker-influenceable content reaching memory") that was previously
  described as having no live entry point. Worth explicit note: if
  `modules/` is ever activated, that precondition statement in
  CTX-AUTH-001 needs revisiting.
- **Secondary copies (catalogue only):** none beyond the primary
  ChromaDB collection itself — no export/snapshot/backup mechanism found
  for this content.

## Classification

**A** for capability execution and the skill system (no remediation
needed — nothing live to remediate). **B — separate but would become
model-visible if activated** for `modules/*`, distinct from a clean A:
real, well-built code exists, is currently dormant for a documented and
independently-verified structural reason, but is not merely
hypothetical — it would need its own security pass (specifically:
does per-module scope suffice, and does ingested-content provenance
survive to consumers) before being safe to activate, not assumed safe
by default just because it currently isn't running.
