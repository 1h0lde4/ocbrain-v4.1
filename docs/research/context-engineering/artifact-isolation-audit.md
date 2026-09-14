# Artifact Isolation Audit

Third phase of the isolation audit sequence (Graph ✅ → Cache ✅ →
Artifact ✅ → Tool-result → Revocation/deletion/retention → Secondary
copies/export → Final reconciliation). Traced against commit `c6fa9ee`.

## Disambiguation (mandatory before anything else)

"Artifact" names two unrelated concepts in this codebase:

- **`CognitiveArtifact`** (`core/cognitive/intent.py`) — an abstract
  `Protocol`, the K4.1 base contract that `Intent`/`Goal` specialize
  (resource_id, provenance, lifecycle fields). A type-system concept,
  nothing to do with files or outputs. Not in scope for this audit.
- **`WorkerResult.artifacts: Dict[str, Any]`** (`core/workers/base.py`)
  — "Named outputs (files, data structures) produced." This is what the
  isolation-audit framing (files/workspace/VFS/attachment) actually
  means, and what this document traces.

No `ArtifactStore`, `ArtifactRegistry`, workspace, VFS, or attachment
mechanism exists anywhere in the repository (confirmed by repository-
wide search, zero matches beyond the two symbols above).

## Trace

| Stage | Finding |
|---|---|
| Creation | Inline, per-invocation. Each worker constructs its own `WorkerResult.artifacts` dict directly (`EvaluatorWorker`: `evaluation_record`; `CuratorWorker`: `curation_report`; `CapabilityExecutorWorker`: `adapter_used`). |
| Identity | **NOT IMPLEMENTED.** No artifact ID distinct from its dict key within one `WorkerResult`. No cross-result identity of any kind. |
| Ownership / scope | Implicit only — an artifact's scope is whatever the containing `WorkerResult` Python object's lifetime is. No explicit ownership model, because there's no persistence for one to govern. |
| Metadata / provenance | None beyond whatever the artifact's own content happens to carry (e.g. `EvaluationRecord`'s own fields). No wrapper-level provenance tracking, comparable to the gap already documented for `KnowledgeEntry`/`ProvenanceRecord`, but here there isn't even a first pass at it. |
| Persistence | **NOT IMPLEMENTED.** Repository-wide search for `open(...'w'`, `.write_text(`, `.write_bytes(` across `core/workers/`, `core/runtime/`, `core/cognitive/` returned zero matches. Purely in-memory, transient. |
| Indexing / registration | **NOT IMPLEMENTED.** No registry exists to trace. |
| Lookup / reference | **NOT IMPLEMENTED** as a general mechanism. The one confirmed flow (below) is direct object access, not lookup-by-ID. |
| Consumption | **One confirmed live cross-worker flow**, and only one, repository-wide (confirmed by an exhaustive search for `.artifacts[` consumption): `orchestrator.py:477`, `EvaluationRecord(**eval_result.artifacts["evaluation_record"])`, feeding `ReflectionWorker`'s next invocation. |
| Prompt / tool serialization | **NOT FOUND.** No code path serializes `.artifacts` or `.metadata` into an LLM prompt anywhere searched (`core/cognitive/`, `core/workers/`). Confirmed via direct search, not inference. |
| Mutation / overwrite | **N/A.** No shared, persistent store exists to overwrite. Each `WorkerResult.artifacts` dict is freshly constructed per invocation. |
| Deletion / retention | **N/A** for `WorkerResult.artifacts` (garbage-collected with the object). **Real and verified** for the adjacent L4 Memory Archive — see below. |

## The one confirmed flow, in full

`orchestrator.py:461-480` (K4.2 branch, "Task 5 — post-execution
hooks"): after `WorkflowRuntime.execute()` produces a result,
`EvaluatorWorker` is invoked via the governed `ExecutionRuntime.invoke()`
path (same mechanism used for `SupervisorWorker`/`PlannerWorker`,
per the surrounding comment). If `eval_result.artifacts` contains
`"evaluation_record"`, it's unpacked into an `EvaluationRecord` and
passed directly into a subsequent `ReflectionWorker` invocation, with
consistent `workflow_id=execution_plan.resource_id` and `query`
propagated across both calls. This is a synchronous, same-request,
same-execution, same-identity handoff — not a retrieval from any shared
or persistent store. There is no opportunity for cross-task/cross-
execution artifact leakage here, because there is nothing for content to
leak *from* — the mechanism is direct object passing within a single
call stack.

## L4 Memory Archive (adjacent, not `WorkerResult.artifacts`, worth
documenting here since it's the only real persistence/deletion story
touching anything artifact-shaped)

`UnifiedMemory.archive_event()`/`archive_snapshot()` write
`KnowledgeEvent`/`KnowledgeEntry` records to L4. Deletion is genuinely,
verifiably blocked for L4 entries — `curator.py`'s
`_before_delete_hook`: `if entry.layer == "l4": ... return None`, and
per `UnifiedMemory`'s own `before_delete` hook contract, returning
`None` rejects the deletion. Confirmed as real, working code, not a
docstring claim. `archive_event()` itself has no scope parameter,
consistent with (not a new instance of) the already-documented
UnifiedMemory-wide finding that no task/execution/worker scoping exists
anywhere in this memory layer.

## Required distinctions

- **Shared cognitive/artifact state by design:** N/A — nothing persists
  long enough to characterize as shared-by-design or otherwise.
- **Cross-execution access that is actually unauthorized:** NOT
  DEMONSTRATED. No mechanism exists for this to occur today.
- **Stale/stale-reference reuse:** N/A. No references exist (direct
  object handoff only) to become stale.
- **Collision/overwrite:** N/A. No shared mutable store to collide in.
- **Provenance loss:** N/A for `WorkerResult.artifacts` specifically
  (nothing is transformed away — whatever a worker puts in is what's
  there). L4 Archive inherits the general UnifiedMemory-wide provenance
  characteristics already documented elsewhere, not a new instance.
- **Trust/authority escalation:** NOT DEMONSTRATED. No prompt-
  serialization path exists for this class of escalation to occur
  through artifacts specifically.
- **Secondary copies (catalogue only, per instructions):** L4 archival
  itself is the only secondary-copy-shaped mechanism found
  (`KnowledgeEntry`/event → archived copy) — already covered by the
  general UnifiedMemory findings, not a new one. No export, snapshot,
  or backup mechanism found for `WorkerResult.artifacts`.

## Forward-looking note, not a current finding

`CoderWorker`, `ReActWorker`, and `BrowserWorker` — the worker types
that PROJECT_INSTRUCTIONS.md's canonical list describes as needing real
filesystem access, rollback, and checkpointing — do not exist yet
(confirmed: zero files, zero class definitions, repository-wide). This
audit's clean result reflects the *current* architecture; artifact
isolation becomes a materially more consequential question the moment
any of those three are built, since that is when real file content and
external (potentially untrusted) data would first enter this pathway.
Worth re-auditing at that point rather than assuming today's findings
still hold.

## Classification

Consistent with §82-83's decision framework used earlier in this track:
**A** — current implementation is correct as-is for what exists today;
no remediation needed. Revisit when CoderWorker/BrowserWorker land.
