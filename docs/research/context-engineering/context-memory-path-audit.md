# ContextMemory Path Audit

Resolves the open question raised during cache isolation: does
`core/context.py::ContextMemory` participate in any live LLM prompt
path, and does that change CTX-AUTH-001's scope claim. Traced against
commit `20b67d4` (merged onto `79dd89e`).

## Architecture

`ContextMemory` is a **third, independent persistence subsystem**,
alongside `UnifiedMemory`/`KnowledgeEntry` (the K4.x cognitive memory
this whole track has otherwise focused on) and `modules/system_ctrl`'s
ChromaDB store. It has its own hardcoded SQLite database
(`data/context.sqlite`, WAL mode), its own record shape (`Turn`: `id`,
`timestamp`, `query`, `modules_used`, `answer`), and predates the K4.x
naming/documentation conventions stylistically. It is instantiated once
as a module-level singleton (`core/context.py:182`,
`context_memory = ContextMemory()`) and imported into `main.py` as `from
core.context import context_memory`.

It ties directly to an older "modules" query-routing architecture
(`modules/base.py`, `modules/coding|knowledge|web_search|_template/module.py`,
`classifier_v3.py`'s `MODULES` dict, `modules/system_ctrl`) that
coexists alongside the K4.x cognitive pipeline rather than being fully
retired.

## Production Call Graph

```
main.py:161   from core.context import context_memory
main.py:400   Orchestrator(modules, context_memory, model_router, memory, ...)
                    │
                    ▼
Orchestrator.__init__ (orchestrator.py:109)   self.context = context
                    │
        ┌───────────┴───────────────────────────────┐
        │                                            │
   K4.2 branch (line 275+)                Legacy Compatibility Bridge
   gated: use_k42_frontend AND            (line 662+)
   workflow_runtime is not None           gated: workflow_runtime is None
        │                                            │
   self.context.save(...)                 memory_context =
   (line 510, write only)                   await context_assembler
                                                .assemble_context(query)
                                            self.context.set_long_term_
                                                memories_string(memory_context)
                                            classify(query, top_k=2)
                                            self.router.route(mod_name,
                                                query, self.context)
                                                    │
                                                    ▼
                                            core/model_router.py:314
                                            ctx_str = context.
                                                format_for_prompt(5)
                                                    │
                                                    ▼
                                            (LLM prompt construction,
                                             module-specific)
```

`format_for_prompt()` is called from exactly six places repository-wide:
`modules/web_search/module.py:111`, `modules/_template/module.py:41`,
`modules/base.py:215`, `modules/knowledge/module.py:38`,
`modules/coding/module.py:55`, `core/model_router.py:314`. **Zero** call
sites exist in `core/cognitive/` — confirmed by an empty repository
search across every file in that directory.

## Production Callers (answers to trace questions 1-2)

- `ContextMemory.save()`: called from the K4.2 branch (`orchestrator.py:510`,
  writing every K4.2-processed query/answer pair), the legacy bridge
  (`orchestrator.py:726`), and independently from the legacy K2.2
  `PlannerWorker` (per an explanatory comment at `orchestrator.py:496-509`
  citing `core/workers/planner.py`'s own internal `self._context_memory.save(...)`
  call — not independently re-verified against `planner.py` itself in
  this phase).
- `ContextMemory.set_long_term_memories_string()`: called only from the
  legacy bridge (`orchestrator.py:682`).
- `ContextMemory.format_for_prompt()`: called only from `modules/*` and
  `core/model_router.py`, itself only reachable via the legacy bridge's
  `self.router.route(...)` call (`orchestrator.py:789`).

## LLM Prompt Participation (question 3)

**Yes, but only through the legacy bridge / modules-routing path.**
`format_for_prompt()`'s output (`ctx_str`) is confirmed used in
constructing prompts inside `modules/*` and `model_router.py`. This
mechanism is real and callable, not dead code.

## K4.2 Participation (question 4)

**Write-side only.** The K4.2 branch calls `self.context.save(query,
capability_types, answer, {})` (`orchestrator.py:510`) — confirmed
inside the K4.2-gated block by the surrounding `execution_plan`/
`ReflectionWorker` context and an explicit comment describing this as a
deliberate fix so "every K4.2-processed query" gets the same
short-term-continuity treatment as the legacy path. **No K4.2 code
path calls `format_for_prompt()` or reads back from `ContextMemory`** —
confirmed by an empty grep for both symbols across every file in
`core/cognitive/`. K4.2's own prompt construction (Intent Hypothesis
generation, per CTX-AUTH-001) draws exclusively from
`ContextAssemblyEngine.assemble_context()`, not from `ContextMemory`.

## Legacy-Bridge Participation (question 5)

**Yes, fully.** `assemble_context()` → `set_long_term_memories_string()`
→ `classify()` → `router.route()` → `format_for_prompt()` is a single,
continuous sequence entirely inside the bridge (`orchestrator.py:662-789`,
confirmed no branch back to the K4.2 gate in between). Per the
already-established, separately-verified finding, this bridge executes
only when `workflow_runtime is None`, which `main.py`'s composition root
never allows — **the read/prompt-construction side of `ContextMemory`
is not exercised in production today**, same status as the earlier
double-retrieval finding.

## Module-System Participation (question 6)

The legacy bridge *is* the entry point to the modules-routing
architecture (`classify()` → `router.route(mod_name, ...)` →
module-specific handler). They are not two separate systems; "legacy
bridge" and "modules routing" describe the same dormant code path from
two different angles.

## Persistence (question 7)

**Survives restarts.** Real file-backed SQLite (`data/context.sqlite`),
not `:memory:`, WAL mode. Confirmed by direct reading of `__init__`;
not empirically tested with an actual restart in this phase.

## Scope (question 8)

**None.** `Turn.__slots__ = ("id", "timestamp", "query", "modules_used",
"answer")`. No task/session/user/workflow/execution field of any kind.
`last_n(n)` is `SELECT ... FROM turns ORDER BY id DESC LIMIT n` — the
most recent N interactions system-wide, unconditionally, regardless of
origin.

## Cache (question 9)

`ContextMemory._prompt_cache: dict[int, str]`, keyed by the requested
turn-count `n`, cleared on every `save()`. Live. Low *incremental* risk
beyond what `last_n()` already does unconditionally — the cache doesn't
add a new isolation gap, it just memoizes an already-unscoped query.

## Provenance / Authority (questions 13-14)

**None survive.** `turns` stores raw `query`/`answer` text only — no
`trust_score`, `truth_status`, `worker_id`, source, or any other
provenance field. This is a starker loss than the `KnowledgeEntry` →
`ProvenanceRecord` → flat-string path audited for CTX-AUTH-001, which at
least carries structured provenance partway before discarding it.

## Overlap with UnifiedMemory (questions 10-12)

**Confirmed duplicate writes.** The K4.2 branch writes the same
interaction to both `self.context.save(...)` (line 510) and
`self.memory.write(content=answer, content_type="interaction", ...)`
(immediately following in the same block) — two independent stores,
neither aware of the other's contents at retrieval time. The comment at
`orchestrator.py:496-509` explicitly notes "non-blocking failure
handling" for this pair, meaning one write can succeed while the other
fails — a plausible, architecturally-supported divergence path, not
empirically demonstrated in this phase (would require a fault-injection
test to confirm).

## Security (question 15, synthesis)

If the legacy bridge / modules-routing path is ever exercised — a
config change, a regression in the `use_k42_frontend`/`workflow_runtime`
wiring, or a future caller constructing `Orchestrator` without a
`workflow_runtime` — `format_for_prompt()` would unconditionally inject
verbatim, unscoped, provenance-free conversation history from *any*
prior interaction (including ones written by the currently-live K4.2
branch) into whatever prompt it builds. Unlike CTX-AUTH-001, this
requires no adversarial precondition and no model susceptibility to
injection — it is a direct, mechanical read of unscoped state.
**Currently not production-exercised**, same qualifier as the earlier
double-retrieval finding, but the write-side connection to K4.2 means
the *data* this would surface is already accumulating live.

## Classification

**D — Intersects legacy bridge**, with an important qualification: the
*read*/prompt-construction side is a clean D (confined to the dormant
bridge). The *write* side intersects K4.2 directly (line 510) without
itself creating model-visibility, because K4.2 never reads
`ContextMemory` back. Neither A nor C alone is accurate; F is not
needed because D correctly identifies where the actual prompt-formation
risk lives, provided the K4.2-write caveat is stated explicitly (as
above) rather than folded into the classification letter.

## CTX-AUTH-001 Scope Impact

**Restored — with a new, separate finding alongside it, not a
correction to it.** CTX-AUTH-001's original claim — that raw
retrieved-context-to-prompt interpolation is concentrated at the Intent
Hypothesis site within `core/cognitive/` — holds. `ContextMemory`'s
prompt-construction mechanism is real but does not intersect K4.2's
prompt construction; it is a structurally separate, currently-dormant
path. This audit surfaces a second, distinct, not-currently-exercised
finding (`ContextMemory`'s unconditional, unscoped conversation-history
injection via the legacy bridge) that deserves its own threat-model
entry rather than expanding CTX-AUTH-001's own claimed boundary.
