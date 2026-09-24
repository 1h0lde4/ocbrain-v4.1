# ADR-CTX-01: Long-Term-Memory Scope-Keyed Storage

**Status:** Accepted
**Date:** Sept 16-17, 2026
**Context:** CTX-SCOPE-001 re-audit (Context Engineering Security Audit)

---

## Numbering note

`ADR-CTX-NN` is a new, small series for decisions made during the Context
Engineering Security Audit (CTX-AUTH-001, CTX-SCOPE-001, CTX-CACHE-001,
CTX-DELETE-001, CTX-EXPORT-001) that have no natural home in the
K4.2-H-packet sequence or the `ADR-KERNEL-NN` series (Kernel-completion
freeze blockers specifically). Same rationale ADR-KERNEL-01 itself gave
for introducing its own series: forcing this onto an existing series
would misrepresent what closed it. Tracked in `ADR_INDEX.md` alongside
the other two standalone series.

## Context

CTX-SCOPE-001's remediation landed in two passes. The mechanism
(`core/context.py::ContextMemory.save()`/`last_n()`/`format_for_prompt()`
accepting a real `scope` parameter, backed by a `scope` column on `turns`,
prompt cache keyed on `(n, scope)`) landed first. A caller-wiring pass
(PR #14, `fix/ctx-scope-001-caller-wiring`, merged Sept 13, 2026) then
correctly wired every site the Sept 7 Context Isolation Caller Audit had
named live, and the tracking docs marked the finding resolved.

A follow-up re-audit (Sept 16-17, 2026) — prompted by treating "resolved"
as a claim to verify rather than accept, the same standard this project
applies throughout its own history — found that call premature. Two live
gaps existed outside the wiring pass's own scope:

1. `ContextMemory.boost_module()` had no `scope` parameter at all.
   Straightforward to fix by mirroring `last_n()`'s own convention
   (`scope: Optional[str] = None`, forwarded into `self.last_n()`).

2. `ContextMemory.set_long_term_memories_string()` /
   `set_long_term_memories()` wrote to `self._long_term_memories_string`
   / `self.long_term_memories` — flat, process-global fields —
   unconditionally injected by `format_for_prompt()` into every caller's
   result regardless of what `scope` (if any) that caller passed. Live
   via `core/workers/planner.py`, inside `PlannerWorker`, the same
   canonical K4.2 worker already confirmed live for the wiring pass's own
   `:218` write.

(2) is architecturally different from (1) and from the sites the wiring
pass fixed. Those are all *filters* over an existing append-only log
(`turns`) — adding `scope` narrows a query. Long-term memory is not a
log; it is a single current value that gets *replaced* on each call
(`set_long_term_memories_string()` overwrites, it doesn't append).
Threading a `scope` parameter through unchanged and using it only to
*label* the same single stored value would not fix anything — whichever
caller wrote last would still determine what every scope reads, just
with a `scope=` keyword now present at the call site. The API must not
become "scoped" syntactically while remaining globally aliased
semantically.

## Decision

Replace the two flat fields with scope-keyed storage:

```python
self._long_term_memories_by_scope: dict[str, list[dict]] = {}
self._long_term_memories_string_by_scope: dict[str, str] = {}
```

`set_long_term_memories_string(context_string, scope="")` and
`set_long_term_memories(memories, scope="")` write under the given key.
`format_for_prompt(scope=...)` reads back only the entry for that exact
key. Default `scope=""` on both setters mirrors `save()`'s own
convention — the shared/legacy bucket every unmodified caller already
writes to and reads from, preserving exact prior behavior for any
caller not yet updated on either side.

`format_for_prompt()`'s own `scope` parameter still defaults to `None`
(unfiltered), matching `last_n()`. For the long-term-memory lookup
specifically, `None` folds to `""` rather than meaning "union across
every scope": unlike `turns`, which can be meaningfully unioned (that's
exactly what `last_n(scope=None)` already does), there is no coherent
reading of "the combined long-term-memory string of several unrelated
scopes." The one sensible interpretation of "no scope requested" here
is "the shared bucket every unmodified caller already writes to" —
which is also exactly what preserves prior behavior for a caller not
yet updated on either side. A caller that *does* pass an explicit scope
only ever sees what was stored under that exact key; there is no
fallback to the shared bucket once a real scope is in play.

`set_long_term_memories()` (the list-based sibling, no live caller
today) was fixed identically, not left unscoped. This is a different
judgment from the `entities`/`get_entity()` decision made the same
session (deliberately left untouched: dormant, and a genuinely separate
table/method with no shared code path). `set_long_term_memories()`
writes into the *same* `format_for_prompt()` injection point its
sibling does, which no longer reads the old flat field at all after
this redesign — leaving it unscoped would not have left it merely
dormant-and-correct, it would have made it write to storage nothing
reads, a latent reintroduction risk the moment any future caller is
added, silently.

Incidental fix made alongside this: the original
`set_long_term_memories_string()` never invalidated `_prompt_cache` or
set `_turns_cache_dirty` (unlike its list-based sibling, which always
did). A second call with new content under an already-cached `(n,
scope)` key would have been silently masked by the stale cached result.
Fixed by adding the same two lines its sibling already had — same
cache, same invalidation strategy already in use elsewhere in this
class, not a new mechanism.

`core/classifier.py:45`'s `boost_module()` call was also found live
this session (via `interface/api.py:304`'s `label()`), not dormant as
the Sept 7 audit's row 9 had classified it — see `KNOWN_ISSUES.md`
DEBT-019 and the remediation register's REM-006 status note for that
finding's own detail; it's a parameter-threading fix like `save()`'s,
not a storage redesign, and doesn't otherwise bear on this ADR's
decision.

## Rationale

1. **Isolation semantics, not parameter presence** — the stored value
   must be *associated with* a scope, and a scoped read must retrieve
   *that scope's* value, not a labeled pointer to one shared value. A
   `scope` keyword that doesn't change what's actually stored or
   retrieved is the exact "syntactically scoped, semantically global"
   failure mode this finding's own governing task calls out by name.
2. **Consistency with the existing mechanism** — scope-keyed storage
   with a `""` default bucket is the same pattern `save()`/`turns`
   already established and already has passing tests for; this
   generalizes it rather than inventing a second convention.
3. **Minimal, not novel** — a `dict[str, T]` keyed by the same `scope`
   string used everywhere else in this class is the smallest structure
   that satisfies the isolation requirement; no new identity concept,
   no schema/persistence change (this field was never persisted to
   SQLite in the first place, unlike `turns`).

## Consequences

- `ContextMemory.__init__` no longer sets `self.long_term_memories` /
  `self._long_term_memories_string`; any external code reading those
  attributes directly (none found in a repo-wide search) would break.
  Public API (`set_long_term_memories[_string]()`, `format_for_prompt()`)
  is unchanged in call shape apart from the new optional `scope` kwarg.
- Two scopes that legitimately want to *share* long-term-memory content
  (not a known use case today) would need to explicitly agree on a
  scope string, or both omit `scope` and use the shared `""` bucket, the
  same tradeoff `save()`/`turns` already accepted.
- `core/orchestrator.py`'s K2.2-Legacy-branch call (confirmed dormant in
  production per that branch's own comment) was also updated to pass
  `scope=execution_id`, matching its already-scoped neighbor `.save()`
  call three lines away in the same function. One-line consistency fix
  on a call site of a signature already being changed for live callers,
  not new investment in dormant code — a different judgment from
  `entities`, which would have required new schema and a new method
  signature for a subsystem nothing live reaches at all.
- `core/workers/capability_executor.py:121`'s `context=""` payload was
  deliberately left untouched, matching the wiring pass's own explicit
  reasoning for the same call site (safe today by accident, not by
  design; not one of the confirmed live sites) rather than folding an
  unrelated hardening decision into this fix.

## Evidence

- `core/context.py` — storage fields, both setters, `format_for_prompt()`
- `tests/test_context_scope_security.py` —
  `test_long_term_memory_string_is_scoped_to_the_caller`,
  `test_long_term_memory_string_cache_invalidates_on_write`,
  `test_long_term_memories_list_is_scoped_to_the_caller`,
  `test_planner_worker_scopes_long_term_memory_save_and_dispatch`
  (production-path proof: a third scope that never ran sees neither
  execution's long-term-memory content — the decisive check, since both
  running scopes legitimately see their own copy of the same mocked
  content and wouldn't by themselves distinguish scoped from unscoped
  storage)
- False-green resistance: confirmed twice — once against this session's
  own pre-fix source (`git stash` of all eight originally-touched
  files), and again specifically against PR #14's already-merged wiring
  alone (`git stash` of just this session's five touched files, PR #14's
  wiring left intact) — 7 of 9 new/extended tests failed both times, as
  expected, before being restored
- `core/workers/planner.py` (scope computed once, used at both the
  long-term-memory call and `.save()`), `core/orchestrator.py` — the
  two call sites

## References

- CTX-SCOPE-001 (`docs/research/context-engineering/context-authority-threat-model.md`)
- `docs/reports/context-compiler-remediation-register.md` (REM-006)
- `docs/Bugs Hunt & fix reports/CONTEXT_ISOLATION_CALLER_AUDIT_SEP2026.md`
