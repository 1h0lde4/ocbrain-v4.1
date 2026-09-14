# Revocation / Deletion / Retention Audit

Fifth phase of the isolation audit sequence (Graph ✅ → Cache ✅ →
Artifact ✅ → Tool-result ✅ → Revocation/deletion/retention ✅ →
Secondary copies/export → Final reconciliation). Traced against commit
`b8d8fca`. Core question: after something is revoked or deleted, what
representations remain reachable, through which interfaces, and is that
intentional or accidental.

## The central distinction, established with evidence: "deprecated" and
"deleted" are two entirely different operations

No `supersede()`, `deprecate()`, or `revoke()` method exists anywhere in
`UnifiedMemory` (confirmed by direct search, zero matches). Setting
`truth_status = "deprecated"` happens through an ordinary `write()`/
`update()` call, same as any other field change. This has real
consequences, verified against the actual filtering code:

- `search()`'s `include_deprecated` parameter resolves to `not
  entry.is_searchable()` — and `search()` queries **only L1+L2**
  (confirmed by its own docstring and implementation: "Hybrid search
  across L1 + L2"). A deprecated entry is excluded from *default*
  search results, but remains fully present in storage, fully
  retrievable with `include_deprecated=True`, and — critically —
  **its graph node is untouched**, because deprecating an entry never
  calls anything in `core/memory/graph/`.
- Neither `core/memory/retrieval/graphrag/pipeline.py` nor
  `traversal.py` reference `is_searchable`, `truth_status`, or
  `deprecated` at all (confirmed, zero matches). Only
  `WeightedRankingStrategy`'s calibrated penalty touches this, and a
  ranking penalty is not exclusion. **A deprecated entry can still
  surface as a graph-traversal neighbor of an unrelated seed entry**,
  through an interface that never checked its status, even when a
  direct `search()` call (with the default `include_deprecated=False`)
  would have excluded it as a seed itself.

This is exactly the "logical ineligibility vs. actual erasure" gap the
audit was designed to find, and it's more specific than a generic
warning — it's a concrete interface asymmetry between `search()` and
graph expansion.

## `delete()` — real, well-designed, with one verified discrepancy
between its own docstring and its own code

`UnifiedMemory.delete()` (`unified_memory.py:838`) is a genuinely
well-built, governed, nine-step pipeline: load → governance evaluation
→ `before_delete` hooks → L4 archive (event + full entry snapshot,
**before** removal) → L3 graph node removal (routed through
`GraphIndexer.remove()`, which the code cites a specific existing test
for — `test_graph_engine_delete_node_removes_incident_edges` — real,
tested behavior, not just a claim) → L2 vector removal → L1 storage
removal → L0 cache eviction (unconditional) → `after_delete` hooks.

**Verified discrepancy:** the docstring states "L1 removal (step 7) is
the authoritative deletion; if it fails, `False` is returned." The
actual code:

```python
# 7. Remove L1 storage record (authoritative deletion)
try:
    await self._storage.delete(entry_id)
except Exception as e:
    logger.warning("Storage deletion failed for %s: %s", entry_id[:8], e)
# 8. Evict L0 cache (always)
self._l0.evict(entry_id)
# 9. after_delete hooks ...
return True
```

There is no `return False` inside that except block. Steps 8-9 run
unconditionally afterward, and the function falls through to an
unconditional `return True`. **If the primary storage deletion silently
fails, the caller is told the delete succeeded.** This is a genuine gap
between documented and actual behavior in the single most safety-
critical step of the pipeline, found by reading the code directly
rather than trusting a docstring that is otherwise unusually precise and
accurate everywhere else it was checked (graph removal, archival order,
governance placement all matched their documentation exactly).

This is now formally captured as **CTX-DELETE-001**
(`context-authority-threat-model.md`), with a permanent regression test:
`tests/test_unified_memory.py::TestUnifiedMemoryDelete::
test_delete_returns_false_when_l1_storage_deletion_fails` — confirmed
failing for exactly this reason (`76 passed, 1 failed` on the full
existing suite, zero collateral breakage). Worth noting precisely: an
existing test in the same file, `test_delete_archives_before_removal`,
carries a docstring making the identical "even if L1 fails" claim but
never actually exercises that failure path — this was a genuine,
previously-undetected gap in test coverage, confirmed by reading the
existing test's body, not assumed.

Everything else in the pipeline matched its own documentation: L4
archival genuinely happens before removal (`event_deleted()` +
`append_entry_snapshot(entry, reason="delete")`), graph removal is
real and edge-cleaning, governance rejection/escalation are themselves
archived as `KnowledgeEvent`s (an audit trail exists even for *blocked*
deletions), and `before_delete` hooks genuinely block deletion when they
return `None` (independently re-confirmed here, having already verified
this specifically for L4 entries during the artifact-isolation audit).

## L4 archive: intentional, permanent retention — confirmed, not assumed

Every deletion writes a full entry snapshot to L4 before proceeding.
L4 deletion is itself blocked (`curator.py`'s `_before_delete_hook`,
verified in the artifact-isolation audit). `archive_event()`/
`archive_snapshot()` are public `UnifiedMemory` APIs any worker can call
directly, independent of the delete flow — this is general-purpose,
deliberate audit infrastructure, not an accidental byproduct of
deletion specifically. **Deleted content is never truly erased under
normal operation; it is moved to an immutable archive.** This is
consistent with (not contradicted by) PROJECT_INSTRUCTIONS.md's Law 2
(event sourcing, replayability) — it is the intended design, and it
means "delete" in this system means "remove from active/searchable
layers while permanently retaining an audit copy," not "erase."

`search()` never queries L4 (confirmed above), so this retained history
is not exposed as current/authoritative content through the normal
retrieval path. Not independently verified in this phase: whether any
*other* interface (a direct L4 read, an admin/debug path, a future
worker) could resurface archived content as if current — no such
interface was found in this search, but the search was not exhaustive
of every possible L4 read site.

## Deprecated content and provenance

`ProvenanceRecord`'s `truth_status` field, once an entry carries
`"deprecated"` or `"conflicted"`, is preserved as-is through the
pipeline (it's just another field value) — there's no separate
mechanism that would present a deprecated source as if it were still
valid. This is a case where the earlier-documented general provenance-
loss problem (`Context → flat string`, CTX-AUTH-001's root cause) is
actually protective here by omission: since provenance rarely survives
to a consumer anyway, a downstream consumer wouldn't see "deprecated"
mislabeled as "current" — it more often wouldn't see the status at all.
Not a fix, just an accurate characterization of where the two gaps
interact.

## Not resolved in this phase — flagged as open, not assumed

- **Concurrent reads racing deletion.** No explicit locking or
  transaction wrapping was observed across `delete()`'s steps 5-7; each
  is a separate `await` against a separate backend (graph, vector,
  storage). Python's asyncio cooperative scheduling makes a classic
  data race less likely than in preemptively-threaded code, but this is
  a plausibility argument, not a verified guarantee — would require
  either deep review of each backend's own concurrency handling or an
  actual concurrent-access test, neither done in this phase.
- **Resurrection via re-ingestion.** `modules/web_search`'s `ingest()`
  (audited in the tool-result phase) generates IDs as
  `f"{self.name}_{abs(hash(c))}_{int(time.time())}"` — timestamp-
  inclusive, so re-ingesting identical content produces a new ID rather
  than reviving a deleted one under the same identity. This is a
  different subsystem from `UnifiedMemory` entirely (that pathway is
  also still confirmed dormant); not a full analysis, just noted for
  completeness since it touches "resurrection."

## Secondary copies — catalogued only, per phase scope

Per instructions, full analysis deferred to the dedicated phase. What
this audit surfaced in passing:

- L4 archive entries (event + snapshot) — the primary, intentional
  secondary copy, already characterized above.
- The append-only event/audit stream generally (`KnowledgeEvent`
  emissions on writes, deletes, governance rejections/escalations) —
  consistent with the event-sourcing architecture referenced elsewhere
  in this project's documentation; not independently re-verified in
  this phase beyond what's cited above.
- `modules/base.py`'s ChromaDB collections (per-module, from the
  tool-result audit) — a primary store for that dormant subsystem, not
  itself a "copy" of anything in `UnifiedMemory`, but worth listing
  since it's another place data persists outside the main memory layer.

No export/backup/snapshot-to-external-location mechanism was found in
this phase; not searched for exhaustively, since that is explicitly the
next phase's job.

## Classification

**F — Other, explain:** doesn't reduce to a single clean status.
Deletion mechanism itself: well-designed, mostly matches its own
documentation, with one verified discrepancy (silent L1-failure still
reports success). Deprecation: correctly documented behavior once
traced, but easy to misread as equivalent to deletion, and asymmetric
across `search()` vs. graph traversal in a way that isn't documented
anywhere. Retention: intentional and correctly scoped (L4 never
surfaces through `search()`). None of A-E capture "real, well-built
system with one narrow but safety-relevant discrepancy, plus one
undocumented interface asymmetry" without collapsing that nuance.
