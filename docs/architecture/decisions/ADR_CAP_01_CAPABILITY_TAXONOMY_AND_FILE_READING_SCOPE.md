# ADR-CAP-01: Capability Taxonomy, FILE_READING/file_access Boundary, and Scope

**Status:** DRAFT
**Date:** September 2026
**Author:** Capability Foundation mission ("mission 1"), a separate Claude
account, not the main OCBrain implementation account. Branch
`feature/capability-foundation-mission1`, based on `main` at `2192b93`
(PR #18, Workspace architecture final consistency pass), merged forward to
current `main` (through PR #20). **Not reviewed. Not merged. Nothing in this
branch is authoritative until a human accepts it.**
**Scope:** `core/capabilities/` (new `descriptors.py`, new `foundation/`
package), `core/capabilities/capability.py`, `core/capabilities/registry.py`,
`core/capabilities/adapter_runtime.py`, `core/workflow/definition.py`,
`core/workflow/runtime.py`, `core/cognitive/planner.py` (discovery only —
ranking untouched), `core/workers/capability_steps.py`, `main.py`,
`config/settings.toml`.

---

## 1. Context

The mission ("OCBrain — Capability Foundation Research, Architecture &
Implementation Prompt") asked for three new capabilities — TEXT_GENERATION,
STRUCTURED_REASONING, FILE_READING — built as durable primitives, not
convenience functions, while explicitly requiring reconnaissance of the
existing repository before any design decision (§2–§4 of the mission prompt).

**Repository truth as of this branch's base commit:**

- `CapabilityType` (`core/capabilities/capability.py`) declares nine values:
  `LLM_COMPLETION`, `FILE_ACCESS`, `WEB_SEARCH`, `MEMORY_SEARCH`,
  `GRAPH_TRAVERSAL`, `IMAGE_GENERATION`, `TOOL_INVOCATION`, `EXTERNAL_API`,
  `EMBEDDING`. Of these, only `LLM_COMPLETION` has a registered
  `CapabilityContract` and a registered `Adapter` (`main.py`,
  `ModelRouterAdapter`). Every other value is declared and unregistered —
  metadata with no runtime behind it. Confirmed by direct inspection of
  `main.py`'s registration block and `CapabilityRegistry`'s contents at
  startup.
- `FILE_ACCESS = "file_access"` exists as a declared `CapabilityType` value
  and nowhere else. No `CapabilityContract`, no `Adapter`, no reference
  outside `capability.py` itself and its own test fixtures. It is pure
  taxonomy, not a resource-access subsystem.
- `docs/architecture/WORKSPACE_ARCHITECTURE.md` (merged via PR #18,
  8 days before this branch's base commit; its own merge commit notes it was
  **not independently reviewed** before merging) is the one document that
  discusses file/artifact access as architecture rather than as a bare enum
  value. It separates **Trust** (what a Principal is allowed to touch —
  Workspace/project/upload scoping, §G.5's grant tuple of
  Principal × Resource × Operation × Constraint) from **Authority**
  (whether a value may influence an accepted intent — the ADR-KERNEL-06
  chain this same period of `main` was independently developing). It also
  defines File/Artifact identity (content hash, revision, source) and a
  security posture for ingested content (§ "File architecture", §
  "Untrusted document content") that is a superset of what this branch
  needed and was built independently to satisfy from the mission prompt's
  own §25 requirements before this document's relevant sections were read
  in full.
- `core/workflow/definition.py`'s `WorkflowNode` and `core/cognitive/planner.py`'s
  `ExecutionPlan`/`PlanStep` already use `operation_id` and
  `root_operation_id` for the identity of one logical `plan()`/`compile()`
  lineage (ADR-KERNEL-01, ADR-K4.2-H-08). That name was not available for a
  capability's named mode of operation.
- `Orchestrator.handle()` (`core/orchestrator.py`) accepts a query string.
  There is no artifact/file ingress on the live request path. FILE_READING
  is therefore not reachable end-to-end from the production API today —
  recorded as a gap, not silently worked around (§7 "Runtime integration").

## 2. Decision

### 2.1 Vocabulary

| Term | Definition | Existing OCBrain anchor |
|---|---|---|
| **Capability** | A stable, semantic class of work OCBrain can perform, identified by `CapabilityType`. Implementation-, adapter-, model- and provider-neutral. | `CapabilityContract.capability_type` |
| **Operation** | A named mode within one capability, with its own input/output contract (`descriptors.OperationSpec`). Not `operation_id` — that name means plan lineage. Carried as `CapabilityRequest.operation` / `CapabilityResult`'s stamped provenance `operation` key. | New field; §2.3 |
| **Contract** | The versioned, machine-readable declaration of a capability's identity, operations and structured I/O (`CapabilityContract`). | `core/capabilities/capability.py` (existed; extended §ADR-CAP-02) |
| **Implementation** | One concrete way of satisfying a contract (a Python class implementing `Adapter`). Multiple implementations of one capability MUST be possible — pinned by the conformance suite (§45 of the mission prompt; `tests/capability_foundation/test_conformance.py` runs two structurally different implementations per capability through the same contract). | `core/capabilities/foundation/file_reading.py` is implementation **A** of FILE_READING; the conformance suite's `PlainTextFileReader` is implementation **B**. |
| **Adapter** | The existing `Adapter` Protocol (`core/capabilities/capability.py`). Unchanged. An implementation *is* an Adapter. | Unchanged |
| **Model / Provider** | An implementation detail of some adapters (e.g. the two model-backed capabilities), never part of capability identity. Recorded per-call in `CapabilityResult.provenance`, never in the contract. | `core/capabilities/foundation/models.py` (`TextModel` port) |
| **Resource / Access** | What artifact/data may be touched, and under what authorization. This is `FILE_ACCESS`/Workspace's domain, not FILE_READING's. §2.2. |
| **Skill** | A reusable behavioral package (workflow, prompt, or capability composition). Not built here — no speculative Skill subsystem (mission prompt §43). |

A capability MAY expose several operations without fragmenting the taxonomy
into one `CapabilityType` per operation (mission §5): a distinct operation is
justified only when its *contract* differs (different required inputs or
produced outputs), not when only a parameter changes. Concretely:
`TEXT_GENERATION` has four operations (`generate`/`rewrite`/`summarize`/
`transform`) because each has a different required-input shape;
"formal vs. casual tone" is a `constraints.tone` parameter of `generate`, not
a fifth operation.

### 2.2 FILE_READING vs. `file_access` — Model A, evidence-based

**Decision: Model A.** `file_access` remains the lower-level, declared-only
ACCESS layer (Workspace §G.5's Trust grant: Principal × Resource ×
Operation × Constraint — obtaining a *permitted* artifact). `FILE_READING` is
a new, separate, semantic READING capability: parsing an *already-obtained*
artifact's bytes into structured content. Neither activates the other.
`FILE_READING`'s adapter never opens a filesystem path, never resolves a
URI, and never lists a directory (enforced structurally — see
`tests/capability_foundation/test_boundaries.py::TestImportGraph::
test_file_reading_source_has_no_filesystem_access_at_all`, which asserts,
by AST inspection, that the relevant source files contain no `open()`,
`os.listdir`, `pathlib.Path`, etc. calls and no `os`/`pathlib`/`glob`
imports). An artifact only ever arrives as `{artifact_id, content}` — bytes
in, identity out — or through an injected `ArtifactResolver` Protocol, which
is the explicit seam to a future FILE_ACCESS/Workspace implementation and
owns none of this branch's logic.

**Why not Model B** (`file_access` = canonical reading capability, no
separate `FILE_READING`): `file_access` has zero registered behavior to
extend — extending it would mean writing FILE_READING's logic anyway, under
a name (`file_access`) that Workspace's own vocabulary already reserves for
Trust/Access, not Reading. Reusing the name would conflate two different
grant/operation semantics under one `CapabilityType`, which is exactly the
kind of "hard-coded implementation identity into semantic capability
identity" the mission prompt's §10 warns against.

**Why not a third, uninvestigated model:** Workspace §G.5's own
ACCESS → READING → REASONING → GENERATION layering (independently present
in that document, merged before this branch's own design was written) is
the strongest available repository evidence and it agrees with Model A. No
Model C was found that both (a) satisfies §19 of the mission prompt's
"safe, realistic initial support for formats already compatible with the
project" and (b) improves on Workspace's own layering. Model A is Model C —
the evidence-based answer converges with the mission prompt's default
framing.

### 2.3 The `operation` field, not `operation_id`

`CapabilityRequest.operation: str = ""` and a stamped
`CapabilityResult.provenance["operation"]`. `""` resolves to the contract's
declared default operation. Deliberately not `operation_id`, to avoid
colliding with the existing, frozen meaning of that name
(`WorkflowNode.operation_id` / `ExecutionPlan`'s `root_operation_id`: the
identity of one `plan()`→`compile()` lineage, ADR-KERNEL-01 §"whether
WorkflowNode needs root_operation_id", answered no and confirmed rather than
revisited). A capability operation and a plan's `operation_id` are answers
to different questions ("which mode of this capability" vs. "which planning
attempt this node belongs to") and must stay lexically distinct so a future
reader is never tempted to conflate them.

### 2.4 Scope boundaries (verified, not merely asserted)

Everything a capability implementation returns is data: a result, an error,
partial output, evidence-shaped source references, and (for
STRUCTURED_REASONING) claims with citations — never a plan, a route, a
verdict, or an approval. Enforced by
`tests/capability_foundation/test_boundaries.py`:

- **Import graph** (`TestImportGraph`): no file under
  `core/capabilities/foundation/` (nor `descriptors.py`, nor
  `capability_steps.py`) imports `core.cognitive`, `core.governance`,
  `core.workflow`, `core.verification`, `core.memory`, `core.orchestrator`,
  `core.model_router`, `core.learning`, `core.meta`, `core.knowledge`, or
  `core.evolution` — checked by `ast`-parsing every relevant file, not by
  convention. The isolated parser subprocess entry point
  (`readers/isolated_entry.py`) imports nothing from the project at all
  (checked separately — it is a standalone script by design, §6.1).
- **Result/descriptor shape** (`TestResultAndDescriptorShape`): no capability
  output, anywhere, contains a key from a closed forbidden set (`verified`,
  `verdict`, `receipt`, `execution_plan`, `plan`, `clarification`,
  `intent_sufficiency`, `selected_capability`, `governance`, `approved`,
  `route`, `routing_decision`) — checked by walking the JSON-serialized
  output of every sample invocation across all three capabilities. The
  registry's `describe()`/`describe_all()` and the structural
  `find_consumers()`/`find_producers()` queries contain no ranking/scoring
  vocabulary (`score`, `rank`, `best`, `selected`, `recommended`,
  `confidence`, `preferred`) in any key — they answer "what is compatible",
  never "what is best".
- **Metadata is descriptive, not enforcing** (`test_metadata_is_descriptive_
  not_enforcement`): a contract that declares `side_effects=NONE` is
  invoked against an adapter that performs a side effect anyway, and the
  side effect happens — proving the field is documentation for a future
  reader (and eventually for Governance/C-MoE to consult), never itself a
  permission check. GovernanceKernel and the sandbox remain the actual
  enforcement boundary; this branch adds no enforcement path.
- **Only `LLM_COMPLETION` is general-purpose**
  (`TestIdentityAndScope::test_only_llm_completion_is_general_purpose`):
  none of the three new contracts sets `is_general_purpose=True`.
  `LLM_COMPLETION` remains the sole fallback (§2.5).
- **Governed execution path** (`test_step_workers_go_through_the_governed_
  template_method`): every foundation step worker subclasses
  `AbstractCognitiveWorker` and does not override `execute()` (the governed
  template method in `core/workers/base.py`) — only `_run()`, matching
  `CapabilityExecutorWorker`'s own pattern. Governance evaluation is not
  bypassable by construction.

### 2.5 LLM_COMPLETION remains the fallback

None of the three contracts is `is_general_purpose=True`. This is necessary,
not incidental: `is_general_purpose` selects which candidate
`ClarificationPolicy`'s `general_purpose_only` exemption (ADR-K4.2-H-13)
treats as "not a real alternative to be uncertain among". Marking a specific
capability general-purpose would silently widen that exemption's scope
without a corresponding architectural justification. See ADR-CAP-03 for the
full interaction and the reason the foundation ships behind a feature flag.

### 2.6 Explicitly deferred (recorded, not silently dropped)

- **Namespace/seccomp isolation for the reader subprocess.** The isolated
  reader (`readers/isolation.py`) provides process-level isolation (fresh
  interpreter, rlimits, network-call raiser, wall-clock kill, output cap,
  scrubbed environment) but not a network namespace, filesystem read jail,
  or seccomp filter. `core/sandbox`'s `NamespaceBackend` (Sandbox Fabric,
  merged on the concurrent `sandbox-fabric` branch/DEBT-021/DEBT-022) is the
  natural home for that hardening; pairing FILE_READING's isolated readers
  with it needs one more `IsolatedRunner` implementation and changes nothing
  about the contract, the adapter, or the readers themselves. Not built here
  because it is a Sandbox Fabric integration, not a capability-foundation
  concern, and Sandbox Fabric was itself still landing on a separate branch
  during this mission.
- **Richer side-effect / idempotency framework.** All three capabilities are
  `NONE`/`READ_ONLY`. A capability with an external side effect will need
  stronger idempotency semantics than `descriptors.Repeatability` currently
  offers — not built speculatively (mission §38).
- **Learning / C-MoE consumption.** `descriptors.py` and `registry.describe()`
  exist so a future learner or router has something machine-readable to
  read; nothing here learns, ranks, or routes (mission §8, §39).
- **Full Workspace/FILE_ACCESS integration.** `ArtifactResolver` is a
  Protocol seam only; no concrete resolver ships. FILE_READING is therefore
  not reachable from the live `Orchestrator.handle()` request path today —
  see §7 ("Runtime integration") of the closing report for exactly where
  that boundary sits.

## 3. Consequences

- A future capability (with real side effects, needing full Sandbox Fabric
  isolation, etc.) has a taxonomy, a contract shape, a registry, an
  `AdapterRuntime`, and a conformance-test pattern already in place — see
  ADR-CAP-02.
- `file_access` is untouched: still declared, still unregistered. This ADR
  does not resolve whether/how `file_access` itself should ever be
  implemented; that decision belongs to whoever builds the Workspace ACCESS
  layer, informed by Workspace §G.5 rather than by this branch.
- The `operation` vocabulary decision means any future work MUST NOT reuse
  `operation` for a different meaning within the capability layer, and MUST
  NOT rename `WorkflowNode.operation_id` without also revisiting this ADR.
- Until a concrete `ArtifactResolver` exists and `Orchestrator.handle()`
  gains an artifact-ingress path, FILE_READING is exercised only by direct
  `CapabilityRequest` construction (tests, and any future workflow node
  built with inline `content`) — not yet by an end user attaching a file in
  a live conversation.

## 4. Alternatives considered

- **Model B** (`file_access` = canonical reading capability) — rejected,
  §2.2.
- **A capability-per-operation taxonomy** (e.g. `SUMMARIZE`, `REWRITE`,
  `EXTRACT_TABLE` as separate `CapabilityType` values) — rejected: this is
  exactly the taxonomy drift the mission prompt's §5 and §43 warn against,
  and it would prevent a future selector from ever discovering "the set of
  things this capability can do" as one queryable unit.
- **Reusing `operation_id`** for capability operations — rejected, §2.3.
- **A general resource/type ontology** for capability I/O — rejected in
  favor of the closed `descriptors.SemanticType` set the three capabilities
  actually exchange (`artifacts`, `document_set`, `analysis`, `text`);
  extending it is a future ADR-level decision, not something this branch
  pre-builds speculatively (mission §14, §43).
