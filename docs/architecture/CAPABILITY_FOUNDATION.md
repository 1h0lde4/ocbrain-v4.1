# OCBrain — Capability Foundation

**Status:** Living reference for a **DRAFT, unreviewed, unmerged** branch —
`feature/capability-foundation-mission1`. Written by the Capability
Foundation mission ("mission 1"), a separate Claude account, not the main
OCBrain implementation account. Nothing here is authoritative until a human
reviews and merges it. See ADR-CAP-01/02/03
(`docs/architecture/decisions/`) for the formal decision records this
document explains in narrative form.

**Authority:** This document is the "what is a capability and how does it
work" reference for `core/capabilities/`. `PROJECT_INSTRUCTIONS.md` and
`OCBRAIN_KERNEL_CONSTITUTION.md` remain senior to it. `CURRENT_STATE.md`
remains the ground-truth status document.

---

## 1. What is a capability?

A **capability** is a stable, semantic class of work OCBrain can perform —
identified by a `CapabilityType` string, described by a
`CapabilityContract`, and satisfiable by one or more **implementations**
(Python classes implementing the existing `Adapter` Protocol).

The identity ladder, deliberately kept separate at every level
(mission §10):

```
capability identity      "text_generation"                (semantic, stable)
        │
contract version         CapabilityContract.version        (semver; major = breaking)
        │
operation                 "summarize"                       (named mode, own I/O contract)
        │
implementation            TextGenerationAdapter              (one way to satisfy it)
        │
adapter identity/version   adapter_name / adapter_version    (which implementation, which release)
        │
model / provider           per-call, in result.provenance    (never part of identity)
```

Replacing the model behind `TextGenerationAdapter`, or writing a second
implementation entirely, never requires touching `CapabilityType.
TEXT_GENERATION` or its contract — unless the *contract's meaning* actually
changes, in which case the contract's own `version` bumps.

## 2. What is an operation?

A named mode within one capability, with its own required inputs, produced
outputs, and structural I/O types (`descriptors.OperationSpec`). A
capability has several operations when their *contracts* differ — different
required payload keys or different output shape — never merely because a
parameter could vary. Concretely:

| Capability | Operations | Why separate |
|---|---|---|
| `text_generation` | `generate`, `rewrite`, `summarize`, `transform` | `generate` needs only an instruction; the other three require `source`; `transform` additionally requires `target_format` |
| `structured_reasoning` | `analyze`, `compare` | `compare` additionally requires `subjects` (≥2) |
| `file_reading` | `read_document`, `extract_structure` | same input, but `extract_structure` returns headings/table shapes only — a different, smaller output contract for progressive reading |

`CapabilityRequest.operation: str` selects one (`""` = the contract's
declared default). Not named `operation_id` — that name is already the
identity of one `plan()`→`compile()` lineage
(`WorkflowNode.operation_id`/`ExecutionPlan.root_operation_id`,
ADR-KERNEL-01 / ADR-K4.2-H-08) — a different question entirely (see
ADR-CAP-01 §2.3).

`AdapterRuntime.invoke()` validates the operation and its required keys
**before** any adapter runs: an unknown operation or a missing required key
returns `invalid_request` immediately (`descriptors.CapabilityStatus`, §4).

## 3. What is `file_access`, and what is `FILE_READING`?

`file_access` (`CapabilityType.FILE_ACCESS`) is a pre-existing, declared-only
enum value with no contract and no adapter — it names the **Trust/ACCESS**
layer (obtaining a *permitted* artifact; Workspace §G.5's Principal ×
Resource × Operation × Constraint grant). It is untouched by this branch
and remains unregistered.

`file_reading` (`CapabilityType.FILE_READING`, new) is the **READING**
layer: turning an *already-obtained* artifact's bytes into structured
content. It never resolves a path, a URI, or a filesystem location; an
artifact only ever arrives as `{artifact_id, content}` (bytes/text in,
identity out) or via an injected `ArtifactResolver` — the explicit seam to
a future FILE_ACCESS implementation, which this branch does not build.

```
ACCESS                 READING                REASONING            GENERATION
file_access             file_reading           structured_reasoning  text_generation
(declared, unregistered) (this branch)          (this branch)         (this branch)
obtain permitted         parse bytes into        analyze what the      create/transform
artifact                 structured content       content means         output
```

Full reasoning and the rejected alternatives (Model B, a capability-per-
operation taxonomy) are in ADR-CAP-01 §2.2.

## 4. What does a capability result look like, and how are failures
represented?

`CapabilityResult` carries `success`, `output`, `error`, `status`,
`provenance`. `status` is one of a closed vocabulary
(`descriptors.CapabilityStatus`):

| Status | Success? | Meaning |
|---|---|---|
| `ok` | yes | complete result |
| `partial` | yes | usable but incomplete (input truncated to a budget, some artifacts in a batch failed, a selector partially matched) |
| `degraded` | yes | complete-ish but lower fidelity (e.g. an encoding fallback, a dropped citation) |
| `empty` | yes | correctly executed; there is legitimately nothing to return |
| `unsupported` | no | this implementation cannot handle the input (another might) |
| `malformed` | no | input invalid for its declared/detected form |
| `unreadable` | no | artifact content could not be obtained |
| `dependency_unavailable` | no | a required library/runtime is missing or below its security floor |
| `invalid_request` | no | the caller violated the operation's contract |
| `limit_exceeded` | no | rejected by a hard resource limit |
| `unavailable` | no | capability disabled/retired, or no adapter registered |
| `timeout` / `cancelled` / `failed` | no | ordinary execution failure |

**The distinction that matters most:** `unsupported`, `malformed`,
`unreadable`, `dependency_unavailable`, `invalid_request` and
`limit_exceeded` describe *the request*, not a fault of the adapter that
answered — `AdapterRuntime` never lets these degrade an adapter's health
ranking. Only `unsupported`/`dependency_unavailable` fall through to try
the next registered implementation. See ADR-CAP-02 §2.1.

A legitimately empty result (`empty`, `success=True`) is never
indistinguishable from a failed one — verified directly by the conformance
suite (`tests/capability_foundation/test_conformance.py`, "empty" sample)
and by `FileReadingAdapter`'s own zero-length-artifact handling.

## 5. How is a capability discovered?

Unchanged mechanism (ADR-K4.2-H-04's `discover_capabilities()` /
`CapabilityDiscoveryResult`, lexical Jaccard scoring against each
contract's prose `description`, ADR-K4.2-H-03's registration-order
tie-break). This branch adds two things, both additive:

- A **lifecycle gate**: a `DISABLED`/`RETIRED` capability is skipped before
  scoring (`registry.is_discoverable()`, guarded by `getattr` so a test
  double without lifecycle support is unaffected).
- **Structured evidence** alongside the existing lexical score:
  `contract_version`, `operations`, `lifecycle` are recorded in
  `CapabilityMatch.evidence` and in the discovery-request event payload —
  observability for a future reader, not a new ranking input.

Realistic phrasing reaches its intended capability at a lexical score
between roughly 0.05 and 0.11
(`tests/capability_foundation/test_discovery_and_k42.py::
TestPhrasingDiversity`) — well above zero, comfortably below
`ClarificationPolicy`'s `0.5` threshold. See §8 for why that matters.

`CapabilityRegistry.describe()`/`describe_all()` and
`find_consumers(type)`/`find_producers(type)` give a future selector
(C-MoE) or UX something machine-readable to query beyond prose — structural
I/O compatibility only, ranking and selecting nothing (ADR-CAP-02 §2.5).

## 6. How is a capability executed?

`Orchestrator` → `plan()` → `compile()` → `WorkflowRuntime` →
`CapabilityExecutorWorker`/the three new step workers
(`core/workers/capability_steps.py`) → `AdapterRuntime.invoke()` →
`Adapter.execute()`. Unchanged for the existing path. New for the three
capabilities:

- Each step worker subclasses `AbstractCognitiveWorker` and does not
  override the governed `execute()` template method — only `_run()`,
  matching `CapabilityExecutorWorker`'s own shape. Governance evaluation is
  not bypassable by construction (pinned by
  `test_step_workers_go_through_the_governed_template_method`).
- `AdapterRuntime.invoke()` resolves and validates the operation against the
  contract, checks the lifecycle gate, filters to adapters that declare
  support for that operation (if any declare `supported_operations`), ranks
  the remainder by existing health, and applies the status-aware fallback
  described in §4.

## 7. How does composition work, and what is NOT reachable yet?

`WorkflowRuntime` now hands a node the results of its **direct
predecessors** that both completed and succeeded
(`WorkflowDefinition.get_predecessors()`, `context.metadata
["upstream_results"]` — set *after* the run's own metadata is spread, so a
node's own metadata cannot spoof what it receives). A real, three-step
`FILE_READING → STRUCTURED_REASONING → TEXT_GENERATION` pipeline is
exercised end-to-end through the actual `WorkflowRuntime` (not three
isolated unit tests) in
`tests/capability_foundation/test_composition_pipeline.py`.

The hand-off contracts are typed and versioned
(`core/capabilities/foundation/schemas.py`,
`SCHEMA_DOCUMENT_SET`/`SCHEMA_ANALYSIS`/`SCHEMA_TEXT`, each
`"<name>/<major>"`) so a consumer checks compatibility (`schema_compatible()`
— name plus major only) before trusting a payload's shape, rather than
assuming it.

**Not reachable from a live user request today:** `Orchestrator.handle()`
takes a query string; there is no artifact-ingress path on the production
API. FILE_READING (and therefore the full pipeline) is exercisable via
direct `CapabilityRequest` construction — tests, or a future workflow node
built with inline `content` — but not yet by a user attaching a file in a
live conversation. This is a real, stated boundary, not a silently accepted
gap (mission §47).

## 8. How does the K4.2 general-purpose exemption interact with this?

Registering a specific capability can make it the "top candidate" for a
lexically-similar ordinary request instead of `LLM_COMPLETION` — which
defeats ADR-K4.2-H-13's `general_purpose_only` exemption for that request
(measured directly: "write me a haiku about autumn" escalates once
TEXT_GENERATION is registered, where it did not before). **Not a bug in
either ADR** — H-13 was always "exempt when the only candidate is the
fallback", not "exempt whenever confidence is low" — but a real behavior
change nonetheless. Fenced behind `[capabilities] foundation_enabled =
false` (default) so this branch, merged as-is, changes zero observable
production behavior. Full account and the open follow-up decision in
ADR-CAP-03.

## 9. Provenance — how is capability output traceable?

`AdapterRuntime.invoke()` stamps `provenance.capability_type`,
`.operation`, `.contract_version`, `.trace_id`, and
`.adapter: {name, version}` on every result — **after** an adapter's own
`execute()` returns, overwriting whatever the adapter put under those keys,
so an implementation cannot misrepresent which adapter or contract version
actually served a request. Adapters add their own facts under other keys:

- `FILE_READING`: `reader: {id, version, isolation, libraries}`,
  `detected_media_type`, `declared_media_type`, `read_key` (a content-hash-
  derived cache key, computed but not yet consumed — no cache exists),
  per-block/table `locator` strings (`page=3;para=2`,
  `sheet=Sales;range=A1:C9`).
- `TEXT_GENERATION`/`STRUCTURED_REASONING`: `model: {port, provider,
  response_model, request_model}` (deliberately named after OpenTelemetry's
  GenAI semantic-convention vocabulary — see §11) and `verification:
  "not_performed"` on every single result, unconditionally.

`STRUCTURED_REASONING` additionally resolves each finding's citations
itself against the material it was actually shown (never trusting the
model's claim), labelling a finding `cited` only when at least one citation
resolves, `uncited` otherwise. A finding that cites a prior analysis
(chained reasoning) carries that analysis's own source pointers too, so
lineage survives more than one capability boundary.

## 10. Why is `verification: "not_performed"` on every model-backed result?

Because it is true, and because omitting it would let a downstream reader
assume otherwise. Capability output — including a `structured_reasoning`
finding with a resolved citation — is evidence, never a verdict. Whether a
finding is *true* is Verification's question (the unmerged
`feature/verification-critic-evidence-phase-c` branch's own
`EvidenceSource`/`EvidenceItem` shapes were read as a compatibility target:
`SourceRef.to_evidence_source()` produces a
`source_type`/`source_id`/`producer`/`locator` shape deliberately close to
that branch's `EvidenceSource`, without this branch importing or
implementing anything from it — a future Verification consumer has
something structurally compatible to ingest, and nothing here decides
verification status). See mission §7, ADR-CAP-01 §2.4.

## 11. Research reconciliation

Per mission §41–42. Verified via direct lookup during this session
(2026-09-22) unless noted; general, stable technical knowledge is cited at
the conceptual level rather than by exact spec text, to avoid overclaiming
precision on details that evolve.

| External principle | Source | OCBrain location | Existing support | Gap | Decision |
|---|---|---|---|---|---|
| Structured, machine-readable tool descriptions (input/output schemas, a read-only-ness annotation) as the basis for discovery, distinct from free-form prose | Model Context Protocol tool definitions (`inputSchema`/`outputSchema`, `annotations.readOnlyHint`) | `descriptors.OperationSpec` (`inputs`/`outputs`/`requires`/`produces`), `CapabilityContract.side_effects` | K2.3 had prose-only `CapabilityContract.description`, scored lexically | No structured I/O or side-effect declaration existed | **Minimal extension** — `OperationSpec`/`TypeSpec`/`SideEffect` added; discovery's lexical scorer is untouched (ADR-K4.2-H-04 frozen) — the structured metadata is additive observability, not yet wired into ranking |
| Declared skills with typed `inputModes`/`outputModes`, and an explicit task-lifecycle vocabulary distinct from "success/failure" (submitted/working/input-required/completed/failed/canceled) | Agent2Agent (A2A) protocol — `AgentSkill`, `TaskState` | `TypeSpec.media_types`, `descriptors.CapabilityStatus` | No media-type or richer-than-boolean status vocabulary existed | Same gap as above, plus no partial/empty/unsupported distinction | **Reject wholesale import, reuse the principle** — `CapabilityStatus` is OCBrain's own closed vocabulary (mapped at the worker boundary onto `FailureType`, not replacing it), not an A2A `TaskState` import; mission §36 explicitly forbids importing a foreign protocol wholesale |
| Standard attribute naming for LLM call observability (provider identity, request/response model, distinct from the operation name) | OpenTelemetry GenAI semantic conventions | `CapabilityResult.provenance["model"]` shape (`port`/`provider`/`response_model`/`request_model`) | `ModelRouter`/`ProviderMesh` already record some of this internally | No capability-level, OTel-shaped provenance existed | **Reuse the naming principle, minimal extension** — provenance keys chosen to be recognizable to a future OTel exporter (PROJECT_INSTRUCTIONS §12.2), not itself an OTel integration |
| Indirect prompt injection: content an LLM reads (not the operator) can carry instructions the model may obey unless structurally prevented | Greshake et al., "Not what you've signed up for" (indirect prompt injection in LLM-integrated applications); OWASP LLM01:2025 (Prompt Injection) | `foundation/prompts.py` (TASK vs. nonce-fenced DATA channels), `SourceRef`/trust blocks on every extracted structure | No document-derived content reached a model prompt before this branch | Two-channel separation, explicit non-authority labelling | **Minimal extension, explicitly not treated as sufficient on its own** — the docstring states plainly that no prompt-level mitigation is foolproof; the load-bearing defenses are structural (no tools, no side effects, document content never reaches planning/governance) |
| Structured document representation preserving location (page, bounding box, character span) and a body/furniture (main content vs. headers-footers) distinction, addressed by stable reference ids | DoclingDocument (`docling-core`): `texts`/`tables`/`pictures` content lists, `body`/`furniture` structure, `self_ref` JSON-pointer identity, per-item `prov` (`page_no`, `bbox`, `charspan`) | `foundation/schemas.py` `Document`/`Block`/`Table`/`Section`, `locator` strings, `SourceRef` | No structured document representation existed; FILE_READING would otherwise have returned plain text | Full geometric provenance (bounding boxes) — OCBrain's readers do not perform layout analysis | **Reuse the structural principle, reject the geometric layer** — location is preserved via textual locators (`page=N;para=K`, `lines=A-B`, `sheet=S;range=R`) rather than bounding boxes, which no reader here computes; `self_ref`-style stable ids are `block_id`/`table_id`/`section_id`, not JSON pointers, matching OCBrain's own JSON-dict result convention |
| Content-based format detection; hard caps on zip entry count, uncompressed size and compression ratio; path-traversal rejection in archive entries | OWASP File Upload Cheat Sheet; general zip-bomb mitigation practice | `readers/base.py` `detect()` (magic-byte sniffing, extension/declared-type as hints only), `readers/isolated_entry.py` `_zip_preflight()` | No file-format handling existed | — | **Reuse directly** — this is established, non-controversial practice; implemented as `max_zip_entries`/`max_zip_uncompressed_bytes`/`max_zip_ratio`/path-traversal checks in `_zip_preflight()`, exercised by `tests/capability_foundation/test_file_reading.py`'s malformed-archive cases |
| A specific library's own CVE history should gate a version floor, verified directly rather than assumed current | General secure-dependency practice | `readers/defaults.py` `PYPDF_SECURITY_FLOOR` | pypdf was not a project dependency before this branch | — | **Reuse directly** — floor set to `6.16.1`, verified 2026-09-22 against pypdf's own GitHub releases/changelog and CVE-2026-54530/-54531/-54651/-59935/-59936/-84309 (all crafted-PDF infinite-loop DoS, fixed 6.13.0 through 6.16.0, plus 6.16.1's further iteration-limit hardening); a library below its floor reports `dependency_unavailable` rather than being trusted |
| Strict control-flow/data-flow separation for agents that consume untrusted data, via a capability system that prevents untrusted data from influencing which action executes next | CaMeL (Debenedetti et al., "Defeating Prompt Injections by Design") | `foundation/prompts.py`'s two-channel renderer; every capability output's `trust`/`instruction_authority: "none"` label | No agentic loop consumes FILE_READING output automatically today | The full dual-interpreter, capability-gated dataflow architecture | **Reject the full architecture, adopt the labelling principle** — building a CaMeL-style enforcement layer is exactly the "new orchestration engine" / speculative-framework expansion mission §43 forbids for this mission; the lightweight version (every output explicitly labelled with zero instruction authority, so a *future* consumer is structurally told not to treat it as a command) is proportionate to what this branch actually does (no capability here chooses the next action from document content) |
