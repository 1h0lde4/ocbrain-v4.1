# Secondary Copies / Export Audit

Sixth and final audit phase before reconciliation (Graph ✅ → Cache ✅ →
Artifact ✅ → Tool-result ✅ → Revocation/deletion/retention ✅ →
Secondary copies/export ✅ → Final reconciliation). Traced against
commit `28d9144`.

## Primary finding: `core/brain_export.py` — real, network-reachable,
unvalidated import

A fully-built export/import mechanism exists: `.ocbrain` bundles (zip
files: `manifest.json` + LoRA weights + a full ChromaDB knowledge
snapshot + eval sets + up to 100 raw training-pair samples), and it is
genuinely exposed over HTTP, not just a CLI/local tool — confirmed at
both `interface/api.py:435-445` (`@app.post("/export")`,
`@app.post("/import")`) and `core/brain_api.py:135-145` (a second,
apparently duplicate router exposing the same two operations — noted,
not chased further in this phase).

**Reachability, precisely characterized:**
- The server binds to `host="127.0.0.1"` (`main.py:453`) — localhost
  only, not exposed to the network by default.
- `CSRFHeaderMiddleware` (`interface/api.py:43`) requires an
  `X-OCBrain-Local: 1` header on mutating requests, correctly reasoning
  that browsers cannot attach custom headers cross-origin without a CORS
  preflight this server doesn't grant. This is a real, well-reasoned
  protection against a malicious *webpage* driving a victim's browser to
  attack the local server. It does **not** protect against a malicious
  *local process* directly crafting an HTTP request — trivially
  including that header — which is a different, narrower threat model
  than the header's presence might suggest at a glance.
- No authentication (API key, bearer token, session) exists on these
  routes or globally.

**The gap itself, verified by direct reading of `import_module()`:**
- `bundle_path` comes directly from the request body (`req.bundle_path`)
  with no restriction to any expected directory (e.g. `EXPORTS`) — only
  `bundle_path.exists()` is checked before it's opened as a zip.
- `manifest.json` is validated only for presence and a `module_name`
  key. No signature, no checksum, no schema validation beyond that.
- The ChromaDB knowledge snapshot inside the bundle is restored via
  `shutil.copytree` with **zero content inspection** — whatever's in
  there becomes the module's live knowledge base.
- With `overwrite=True`, the existing module directory is fully removed
  (`shutil.rmtree(mod_dir)`) before restoration — a stale or malicious
  bundle silently and completely replaces whatever the module had
  accumulated since the bundle was created, with no diff, no warning,
  no confirmation step beyond the boolean flag itself.

**Connects directly to two earlier findings, not treated as duplicates:**
- This is the concrete mechanism the tool-result audit's "resurrection
  via re-ingestion" note (about `modules/web_search`'s timestamp-based
  IDs) didn't cover — a bundle captured *before* some content was
  deleted, later re-imported, brings that content back wholesale, by
  design, not as a side effect of ID collision.
- It's the same "untrusted content silently becoming trusted" shape as
  CTX-AUTH-001 and the `modules/web_search` ingest pathway, but more
  direct: no model needs to be fooled, no retrieval scoring is involved
  — the entire knowledge base is swapped in as one operation.

**Severity, precisely calibrated:** real gap, meaningfully bounded blast
radius. This is not a remote, unauthenticated-internet vulnerability —
it requires local machine access (another local process, a compromised
local script, or another local user on a shared machine), consistent
with this system's single-user, local-first design. Within that local
threat model, though, it's a genuine gap: no validation at all stands
between "arbitrary local caller" and "complete, silent replacement of a
module's knowledge base."

**Not done in this phase:** a permanent regression test. `import_module()`
touches `core.config`, `core.module_factory`, and real filesystem
operations across several paths (`MODULES`, `DATA`, `EXPORTS`) — a
reliable test needs more fixture infrastructure than was worth building
within this phase, given how much else this phase surfaced. The finding
itself is established with high confidence from direct code reading
(the absence of validation is unambiguous, not something that needs a
test to reveal); a test would confirm reproducibility, not the finding
itself. Recommended as follow-up work, not completed here.

## Catalogued, not fully audited: newly-discovered memory-adjacent
subsystems

While tracing export/import, several previously-unmapped, **confirmed-
live** (not dormant like `modules/`) subsystems surfaced. Listed here
per this phase's scope ("catalogue where copies may exist"), not
traced end-to-end:

- **`core/memory/mem_vault.py`** — JSON-file-backed store
  (`json.dump(self.entries, f, indent=2)`). Referenced from
  `core/web_learning/pipeline.py`, `core/memory/dedup.py`,
  `core/memory/hybrid_retrieval.py`.
- **`core/memory/cognitive_vault.py`** — same JSON-dump pattern.
  Referenced from `core/memory/consolidation/consolidator.py`.
- **`core/web_learning/pipeline.py`** — an entire web-learning pipeline
  not previously encountered in this audit sequence.
- **`core/memory/consolidation/consolidator.py`** — a memory-
  consolidation subsystem, likewise not previously encountered.
- **`core/shadow/collector.py`** — `ShadowCollector`, logging "parallel
  executions of the system's internal reasoning against web-derived
  reasoning" to a JSONL file, for future fine-tuning data. Consistent
  with PROJECT_INSTRUCTIONS.md §13.3's trajectory-learning concept.
  Liveness (whether anything currently calls it) not verified in this
  phase.

None of these were part of any prior phase's scope (Graph, Cache,
Artifact, Tool-result, Revocation/deletion all focused on
`UnifiedMemory`/`ContextMemory`/`GraphRAGPipeline`/`modules/`). Their
existence means the true count of places where OCBrain content can be
duplicated or persisted is larger than what this whole audit sequence
has directly examined. Flagged explicitly as a boundary of this
sequence's coverage, not as a finding about their safety one way or the
other — recommend a dedicated pass before treating the audit sequence
as covering "all persistence in the repository."

## Previously-identified secondary copies, referenced not re-analyzed

Per instructions, not re-litigated here — already characterized in
their originating phases:
- L4 Memory Archive (revocation/deletion audit) — intentional,
  immutable retention, doesn't participate in `search()`.
- The K4.2 branch's duplicate write to both `ContextMemory.save()` and
  `UnifiedMemory.write()` (ContextMemory path audit) — a plausible,
  architecturally-supported divergence path, not empirically tested.
- Per-module ChromaDB collections (tool-result audit) — primary stores
  for the dormant `modules/` subsystem, genuinely partitioned per
  module.

## Classification

**D — divergence risk, deferred-not-dismissed.** The `brain_export`
finding is real and actionable (localhost-scoped, so not urgent in the
way an internet-facing gap would be, but not something to leave
unaddressed indefinitely either). The newly-discovered subsystems are
an honest boundary of this audit sequence's coverage, not a resolved
"safe" finding — they should be swept in a follow-up pass before anyone
relies on this sequence as a complete map of OCBrain's persistence
surface.
