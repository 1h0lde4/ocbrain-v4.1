# Capability Foundation — Mission 1 Completion Report

**Branch:** `feature/capability-foundation-mission1` (base `2192b93`, merged
forward to `main` at `fbd8cc8`/PR #20). **DRAFT. Not reviewed. Not merged.
Not pushed to origin** — this work exists only in this sandbox; nothing in
it is authoritative until a human reviews it (see `HANDOFF.md` for how to
retrieve it).
**Author:** Capability Foundation mission ("mission 1"), a separate Claude
account, not the main OCBrain implementation account.
**Date:** September 2026.
**Full architecture reference:** `docs/architecture/CAPABILITY_FOUNDATION.md`.
**Decision record:** ADR-CAP-01/02/03, `docs/architecture/decisions/`
(all Status: DRAFT).

---

## A. Repository truth

Verified by direct reading, not by trusting prior descriptions (mission
§2–§4): only `LLM_COMPLETION` had a registered `CapabilityContract` and
`Adapter`; `FILE_ACCESS` and six other `CapabilityType` values were
declared-only, zero runtime behind them; `WorkflowRuntime` never handed a
node its predecessors' results (a multi-step plan executed as N independent
calls); `Orchestrator.handle()` takes a query string with no artifact
ingress; `docs/architecture/WORKSPACE_ARCHITECTURE.md` (merged 8 days
before this branch's base, itself flagged as not independently reviewed)
was the only document treating file/artifact access as architecture.
Full detail and citations: ADR-CAP-01 §1.

## B. Capability taxonomy decision

**Model A**, evidence-based: `file_access` stays the declared-only
Trust/ACCESS layer; `FILE_READING` is a new, separate READING capability
that never resolves a path/URI and only ever receives
`{artifact_id, content}` or goes through an injected `ArtifactResolver`
seam. Full reasoning, rejected Model B, and why no better Model C was found:
ADR-CAP-01 §2.2.

## C. Operation model

`CapabilityRequest.operation: str` (default = the contract's declared
default), validated by `AdapterRuntime.invoke()` against
`CapabilityContract.operations: Tuple[OperationSpec, ...]` before any
adapter runs. Deliberately not named `operation_id` (already means plan
lineage — `WorkflowNode.operation_id`/ADR-KERNEL-01/ADR-K4.2-H-08). A new
operation is justified only when its *contract* (required inputs, produced
outputs) differs, never for a parameter-only variation. Full detail:
ADR-CAP-01 §2.1/§2.3, ADR-CAP-02 §2.2, `CAPABILITY_FOUNDATION.md` §2.

## D. Final capability contracts

| Capability | Operations | Side effects | Repeatability | Why not general-purpose |
|---|---|---|---|---|
| `text_generation` | generate, rewrite, summarize, transform | none | model_variable | It is one specific ability, not a fallback for unmatched intent |
| `structured_reasoning` | analyze, compare | none | model_variable | Same |
| `file_reading` | read_document, extract_structure | read_only | repeatable | Same |
| `llm_completion` (unchanged) | — | — | — | **Remains the sole `is_general_purpose=True` capability** — the reason ADR-K4.2-H-13's exemption still functions correctly with the flag off, and the reason ADR-CAP-03 exists |

Full contract source: `core/capabilities/foundation/contracts.py`. Full
field-by-field descriptor model (`TypeSpec`, `OperationSpec`, the
`CapabilityStatus` vocabulary): ADR-CAP-02 §2.1–§2.2,
`CAPABILITY_FOUNDATION.md` §4.

## E. Inter-capability contracts

Typed, versioned, JSON-safe hand-off structures
(`core/capabilities/foundation/schemas.py`): `SCHEMA_DOCUMENT_SET`
(FILE_READING output), `SCHEMA_ANALYSIS` (STRUCTURED_REASONING output),
`SCHEMA_TEXT` (TEXT_GENERATION output), each `"<name>/<major>"`, checked by
`schema_compatible()` (name + major only) before a consumer trusts a
payload's shape. `descriptors.TypeSpec.accepts()` gives
`CapabilityRegistry.find_consumers()`/`find_producers()` a structural (not
lexical) compatibility query. Every document-derived structure carries a
`trust` block (`data_trust`/`instruction_authority`); every model-derived
one carries `verification: "not_performed"`. `WorkflowRuntime` delivers a
node its direct predecessors' *successful* results via
`context.metadata["upstream_results"]` — the actual data-flow mechanism
composition depends on (ADR-CAP-02 §2.6).

## F. Implementation — exact files changed

**46 files, 7,903 insertions, 18 deletions** (`git diff --stat 2192b93 HEAD`
on this branch, tracking docs included). Full listing in `HANDOFF.md`; the
runtime-relevant files:

```
core/capabilities/descriptors.py                 new  — operations, status/lifecycle/side-effect vocabulary
core/capabilities/capability.py                  mod  — CapabilityType +3, CapabilityRequest.operation,
                                                          CapabilityResult.status/.provenance, contract fields
core/capabilities/registry.py                    mod  — compatibility check, deregister, lifecycle, describe()
core/capabilities/adapter_runtime.py             mod  — operation validation, status-aware fallback, provenance
core/workflow/definition.py                      mod  — get_predecessors()
core/workflow/runtime.py                         mod  — upstream_results handoff
core/cognitive/planner.py                        mod  — lifecycle gate + structured evidence in discovery only
core/capabilities/foundation/                    new  — contracts, schemas, models, prompts, handoff, _common,
                                                          file_reading, text_generation, structured_reasoning,
                                                          wiring, readers/{base,defaults,text_readers,
                                                          isolated_entry,isolation}
core/workers/capability_steps.py                 new  — governed step workers for the three capabilities
main.py                                          mod  — registration behind foundation_enabled (default false)
config/settings.toml                             mod  — [capabilities] foundation_enabled = false
tests/capability_foundation/                     new  — 179 tests (registry/runtime, file reading, text+
                                                          reasoning, composition, conformance, boundaries,
                                                          discovery+K4.2)
```

Every non-test, non-doc change is additive (new field with a default that
reproduces pre-existing behavior) except `registry.register_adapter()`,
which can now raise `CapabilityRegistrationError` — scoped to fire only
when an adapter *declares* an incompatible `implements_contract` or an
undeclared `supported_operations` entry (ADR-CAP-02 §2.2).

## G. Runtime integration

`Orchestrator` → `plan()` → `compile()` → `WorkflowRuntime` → step worker
→ `AdapterRuntime.invoke()` → `Adapter.execute()`, unchanged. Discovery
(`discover_capabilities()`) unchanged mechanism, gains a lifecycle skip and
structured (additive) evidence. Each foundation step worker subclasses
`AbstractCognitiveWorker` without overriding `execute()` — governance is
not bypassable by construction (pinned test:
`test_boundaries.py::test_step_workers_go_through_the_governed_template_
method`). Full walkthrough: `CAPABILITY_FOUNDATION.md` §5–§7.

**Known boundary, not worked around:** `Orchestrator.handle()` has no
artifact-ingress path, so FILE_READING (and the full pipeline) is exercised
today via direct `CapabilityRequest` construction — tests, or a future
workflow node with inline `content` — not by a user attaching a file in a
live conversation. Tracked as DEBT-029.

## H. Provenance

`AdapterRuntime.invoke()` stamps `capability_type`/`operation`/
`contract_version`/`trace_id`/`adapter{name,version}` on every result,
*after* the adapter runs, overwriting anything the adapter put under those
keys — the runtime, not the adapter, is authoritative on identity.
`STRUCTURED_REASONING` additionally resolves and verifies its own findings'
citations against material actually shown to the model, never trusting the
model's claim, and a finding citing a prior analysis carries that analysis's
own source pointers (lineage across more than one capability boundary). A
future Verification consumer has a structurally compatible shape to ingest
(`SourceRef.to_evidence_source()`, deliberately close to the unmerged
`feature/verification-critic-evidence-phase-c` branch's own
`EvidenceSource` shape) without this branch importing or implementing
anything from it. Full detail: ADR-CAP-02 §2.4, `CAPABILITY_FOUNDATION.md`
§9–§10.

## I. Failure/degradation semantics

Closed vocabulary (`descriptors.CapabilityStatus`): `ok`/`partial`/
`degraded`/`empty` (success) vs. `unsupported`/`malformed`/`unreadable`/
`dependency_unavailable`/`invalid_request`/`limit_exceeded`/`unavailable`/
`timeout`/`cancelled`/`failed` (not). Request-level statuses never degrade
adapter health; only `unsupported`/`dependency_unavailable` fall through to
try another registered implementation. A legitimately `empty` result is
`success=True` and structurally distinct from every failure status — pinned
by the conformance suite's "empty" sample and
`FileReadingAdapter`'s zero-length-artifact handling. Full vocabulary
table and reasoning: ADR-CAP-02 §2.1, `CAPABILITY_FOUNDATION.md` §4.

## J. Security

- **Untrusted document content, never instruction.** Every prompt built
  from document-derived material uses a two-channel renderer — TASK
  (instruction, from the caller only) vs. nonce-fenced DATA (everything
  else, explicitly labelled non-authoritative) — `core/capabilities/
  foundation/prompts.py`. Every extracted structure carries a `trust`
  block; every model output carries `verification: "not_performed"`.
  Documented as defense in depth, not a guarantee — no prompt-level
  mitigation is foolproof (OWASP LLM01:2025); the load-bearing defense is
  structural: these capabilities have no tools and no side effects.
- **No filesystem access from FILE_READING**, enforced structurally (AST
  scan of the relevant source files for `open`/`os.listdir`/`pathlib.Path`/
  etc. calls and for `os`/`pathlib`/`glob` imports —
  `tests/capability_foundation/test_boundaries.py::TestImportGraph::
  test_file_reading_source_has_no_filesystem_access_at_all`). An
  `artifact_id` must be an opaque id; anything path-shaped (`/`, `\`, `..`,
  a drive letter) is refused before any reader runs.
  `_FORBIDDEN_KEYS = ("path", "file_path", ..., "uri", "url", ...)` refuses
  the request outright if present.
- **PDF/DOCX/XLSX parsed in an isolated, throwaway subprocess**
  (`readers/isolated_entry.py`, launched by `readers/isolation.py`'s
  `SubprocessRunner`) that imports no project code, applies its own rlimits
  (address space, CPU, no file writes, no core dumps, no new processes)
  before importing any parser library, replaces `socket.socket` with a
  raiser, runs in a scrubbed environment and an empty temp cwd, and is
  killed on a wall-clock timeout or an output-size cap enforced by the
  host. Verified with real subprocesses in this session: correct parsing,
  a genuine hang killed at the timeout, an output flood capped, a crash
  (SIGSEGV) classified correctly.
- **Zip-bomb/path-traversal protection** for DOCX/XLSX (both OOXML zips):
  entry-count cap, uncompressed-size cap, per-entry compression-ratio cap,
  encrypted-entry refusal, path-traversal rejection — `_zip_preflight()`.
- **Format detected from content, never trusted from extension or declared
  type alone** (`readers/base.py::detect()`); a mismatch between declared
  and detected type is reported as a warning, not silently resolved either
  way.
- **pypdf security floor 6.16.1**, verified via direct CVE/changelog lookup
  this session (2026-09-22; was `6.16.0` with an imprecise CVE list before
  the correction) — covers CVE-2026-54530/-54531/-54651/-59935/-59936/
  -84309 (crafted-PDF infinite-loop DoS) plus 6.16.1's further,
  not-yet-CVE-numbered iteration-limit hardening. A library below its floor
  reports `dependency_unavailable` rather than being trusted.
- **Not built here, explicitly deferred:** network namespace / filesystem
  jail / seccomp for the reader subprocess (pairs with `core/sandbox`'s
  `NamespaceBackend`, DEBT-029). The reader subprocess today has
  process-level isolation, not namespace-level.

## K. Versioning/compatibility

Identity ladder kept strictly separate at every level: capability identity
→ contract version (`CapabilityContract.version`, semver, major = breaking)
→ operation → implementation → `adapter_name`/`adapter_version` → model/
provider (per-call, in `provenance`, never in identity). An adapter that
*declares* `implements_contract` is refused at registration if its major
disagrees with the contract's; an adapter that declares nothing (every
adapter written before this branch) is unaffected. Full detail: ADR-CAP-01
§2.1, ADR-CAP-02 §2.2.

## L. Lifecycle

`descriptors.CapabilityLifecycle`: `active`/`deprecated`/`disabled`/
`retired`, held in the registry (not on the contract, so a contract object
already held elsewhere is never mutated behind its back).
`disabled`/`retired` are neither discoverable nor invocable; `retired` is
terminal. Absent entry = `active` (today's only behavior).
`deregister_adapter()` removes one implementation by name or instance,
leaving the capability's identity untouched — the replace-an-implementation
path. Full detail: ADR-CAP-02 §2.3.

## M. Testing

**179/179** in `tests/capability_foundation/`: registry+runtime,
file-reading (including zip-bomb/path-traversal/PDF-page-selection/
malformed-input cases), text+reasoning (including citation-resolution and
schema-violation cases), a real-pipeline composition suite through the
actual `WorkflowRuntime`, a reusable conformance checker exercised against
**two structurally different implementations per capability** (per this
project's Kernel Constitution invariant that a contract must be satisfiable
by more than one implementation) plus 4 checker self-tests proving it can
fail, negative-boundary tests (import-graph AST scan, no filesystem access,
no plan/verdict/governance leakage in any output, only `llm_completion` is
general-purpose), discovery phrasing-diversity tests (17 realistic phrases,
none of the capabilities' own description text), and the K4.2 protection
suite (4 tests pinning the exact before/after/hazard behavior described in
ADR-CAP-03).

**Regression baseline, same targeted set this repository's own tracking
docs use, run on the merged branch:** `test_capabilities.py`,
`test_capability_discrimination.py`, `test_workflow_runtime.py`,
`test_runtime_integration.py`, `test_integration_full_pipeline.py`,
`test_k2_4_governance.py`, `test_planner_capability_migration.py`,
`test_execution_runtime.py`, `test_check_drift.py`,
`test_supervisor_worker.py`, `test_evaluator_worker.py`,
`test_debt_020_false_completion.py`, `test_model_router.py`, `tests/core/`
— **827 passed, 1 failed.** The one failure
(`TestCtxAuth001ParserAcceptance`) is CTX-AUTH-001b — confirmed present on
a pristine clone of this branch's base commit *before any change in this
mission*, confirmed still present on current `main` after the merge (with a
different computed score, `0.55` vs. the pre-merge `1.0`, reflecting
origin's own unrelated CTX-AUTH-001b reconciliation work — see
`KNOWN_ISSUES.md`), and confirmed unrelated by file scope (CTX-AUTH-001b
touches `core/cognitive/intent.py`'s hypothesis parsing; this mission never
touches that file). **`scripts/check_drift.py`: 15/15 PASS.**

**Not completed:** a whole-repository `pytest` run. Attempted; hit
pre-existing collection errors unrelated to this work
(`interface/api.py` needs `fastapi`, `modules/system_ctrl` needs
`chromadb`, neither installed in this sandbox). Not chased further — out of
this mission's scope, and this project's own `CURRENT_STATE.md`/
`KNOWN_ISSUES.md` history shows its own sessions routinely run a targeted
set (35–39 pre-existing environment failures noted repeatedly) rather than
a literal 100% pass on every sync, for the same reason. Disclosed rather
than silently omitted, per this project's evidence-first convention.

## N. Research reconciliation

Full table (7 rows: MCP tool schemas, A2A `AgentSkill`/`TaskState`,
OpenTelemetry GenAI semantic conventions, indirect prompt injection /
OWASP LLM01, DoclingDocument's structured representation, OWASP File
Upload Cheat Sheet / zip-bomb mitigation, pypdf's own CVE history, and
CaMeL's control/data-flow separation) with source, OCBrain location,
existing support, gap, and an explicit reuse/minimal-extension/document-
only/defer/reject decision for each: `CAPABILITY_FOUNDATION.md` §11.
Nothing was adopted wholesale; every "reuse" decision is a principle, never
an imported protocol or library the mission prompt's §36/§43 would have
forbidden.

## O. UX compatibility

Every capability's input boundary is an OCBrain-native structure
(`CapabilityRequest.payload`, artifacts as `{artifact_id, content}`) with no
Android/Web/CLI-specific assumption. `descriptors.py`'s `SemanticType`/
`TypeSpec` and `readers/base.py`'s `SUPPORTED_MEDIA_TYPES` give a future UX
layer a stable, presentation-independent contract for what it may supply.
No UX was built in this mission beyond the tiny integration point required
to prove composition (mission §40) — `Orchestrator.handle()`'s
artifact-ingress gap (§G) is the actual remaining UX-facing work.

## P. Migration/rollback

**Migration.** Everything needed to review and adopt this work:

1. `git bundle` (or the equivalent patch series) containing this branch,
   already merged onto current `main` — see `HANDOFF.md` for exact
   retrieval commands. Seven commits, each independently reviewable and
   scoped (descriptor/status/lifecycle/provenance model; workflow
   predecessor handoff; discovery integration; the three capabilities +
   tests; the feature-flag wiring; the ADRs + architecture doc +
   corrections; the four tracking-doc syncs).
2. Required configuration: none to adopt the branch as-is (flag defaults
   `false`). To enable: `[capabilities] foundation_enabled = true` in
   `config/settings.toml` — **not recommended without first resolving
   ADR-CAP-03's open question** (§Q below).
3. New dependencies: `pypdf>=6.16.1`, `python-docx`, `openpyxl` — used only
   by the isolated reader subprocess (`readers/isolated_entry.py`), which
   reports `dependency_unavailable` rather than failing hard if any is
   absent or below its floor. Not required for `text_generation`/
   `structured_reasoning`/`text`/`markdown`/`csv` reading.
4. No schema/data migration — nothing in this branch touches persisted
   state (`data/*.sqlite`, `config/models.toml`'s learned module state) in
   a way that survives past this session; the two files this branch's own
   test runs modify in place (`data/context.sqlite`, `config/models.toml`)
   were reverted after every test run in this sandbox and are not part of
   the diff.

**Rollback.** Trivial in either direction: the flag is off by default, so
merging changes nothing observable; reverting the merge (or simply never
merging) removes the three capabilities and every additive field, none of
which any pre-existing code reads. The one non-additive change
(`register_adapter()`'s new `CapabilityRegistrationError` path) only fires
for an adapter that explicitly declares `implements_contract`/
`supported_operations` — no adapter written before this branch does, so no
existing registration call site is at risk even without a rollback.

**This branch does not assume it becomes authoritative** — per the
mission's own framing. Adoption, rejection, or partial adoption (e.g.
ADR-CAP-02's mechanical extension without the three capabilities
themselves) is entirely the reviewer's call.

## Q. Remaining gaps (explicitly deferred, not silently dropped)

1. **ADR-CAP-03's open question**: whether/how `ClarificationPolicy`'s
   `general_purpose_only` exemption should generalize once more than one
   capability is registered — owned by whoever owns `ClarificationPolicy`,
   blocks safely flipping `foundation_enabled` to `true`.
2. **`Orchestrator.handle()` artifact ingress** — FILE_READING has no live
   caller without it (DEBT-029).
3. **Sandbox Fabric pairing** for the isolated reader subprocess —
   process-level isolation exists; namespace/seccomp does not yet
   (DEBT-029).
4. **`file_access` itself** — still declared, still unregistered; this
   mission does not decide if/how it should ever be implemented.
5. Review and disposition of ADR-CAP-01/02/03 by the project's actual
   owner (all currently Status: DRAFT).
6. A whole-repository `pytest` run (§M) — blocked on optional dependencies
   not installed in this sandbox, unrelated to this mission's scope.

## R. Future evolution

- **Discover** without redesign: `CapabilityRegistry.describe()`/
  `describe_all()` already expose every capability's identity, contract
  version, operations (with structured I/O), lifecycle and registered
  implementations as one JSON-serializable projection.
- **Distinguish capability from operation**: `descriptors.OperationSpec`
  is already the unit a future selector reasons about below the
  capability level, without a `CapabilityType` explosion.
- **Replace an implementation without changing identity**: `Capability
  Registry.register_adapter(new)` + `deregister_adapter(old)`, contract
  and `CapabilityType` untouched; `implements_contract` fails registration
  closed on a real incompatibility.
- **Compose through explicit contracts**: `TypeSpec.accepts()` +
  `find_consumers()`/`find_producers()` are the structural basis; the
  three foundation capabilities are the first, real, working proof
  (§composition pipeline tests), not a speculative framework.
- **Distinguish failures/empty/partial**: the closed `CapabilityStatus`
  vocabulary (§I) is the foundation a learner, a UX, or a future retry
  policy can read without reinventing this per capability.
- **Keep document content untrusted**: the trust/`verification:
  "not_performed"` labelling is structural, present on every result today,
  not something a future capability has to remember to add.
- **Let Verification consume without becoming Verification**:
  `SourceRef.to_evidence_source()`'s shape is a deliberate, tested
  compatibility target for the unmerged Verification branch's own
  `EvidenceSource`, with zero import or implementation dependency either
  way.
- **Let C-MoE consume without this becoming C-MoE**: the structured
  discovery evidence (§discovery, ADR-CAP-02 §2.5) is additive
  observability; ranking and selection are completely untouched.
- **Let learning observe without redefining semantics**: nothing here
  learns; `descriptors.py`'s vocabulary is the shape a future learner would
  read, not a place it writes.
- **Keep `general_purpose_only` correct**: ADR-CAP-03's gate is exactly
  this — the mechanism stays correct *because* the hazard is fenced, not
  because it was ignored.
- **Test a future implementation against a stable contract**:
  `tests/capability_foundation/conformance.py`'s `check_conformance()` is
  reusable as-is for any future capability, not just these three.
- **Merge without architectural contamination**: §P.

---

## Final quality gate (mission §56)

| Question | Answer |
|---|---|
| Discover capabilities without relying only on prose? | **Yes** — `describe()`/`describe_all()`, structural `find_consumers`/`find_producers` |
| Distinguish capability from operation? | **Yes** — §C |
| Replace an implementation without changing capability identity? | **Yes** — §K, §R |
| FILE_READING distinguishes access from semantic reading? | **Yes** — §B, ADR-CAP-01 §2.2 |
| Future UX pass artifacts into FILE_READING without redesigning the kernel? | **Yes, contract-wise** — §O. **Not yet reachable from live traffic** — §Q.2, honestly reported, not glossed over |
| FILE_READING produces structured, provenance-preserving data? | **Yes** — §H, `Document`/`Block`/`Table`/`Section` with locators |
| Capabilities compose through explicit contracts? | **Yes** — §E, real pipeline test, not three isolated unit tests |
| Failures, empty results and partial results distinguishable? | **Yes** — §I |
| Document content remains untrusted? | **Yes** — §J |
| Future Verification can consume output without this becoming Verification? | **Yes** — §H, §R |
| Future C-MoE can consume metadata without this becoming C-MoE? | **Yes** — §R |
| Future learning can observe without silently redefining semantics? | **Yes** — §R |
| K4.2/general_purpose_only fallback behavior remains correct? | **Yes, and only because it is fenced** — §Q.1, ADR-CAP-03. This is the one answer that is conditional: correct *as shipped* (flag off); the underlying question is not resolved, by design (mission §33 asks to protect the existing behavior, not to unilaterally re-decide a K4.2-frozen governor) |
| Future implementation testable against a stable conformance contract? | **Yes** — §M, `conformance.py` |
| Mergeable without architectural contamination? | **Yes, contingent on review** — §P; nothing in this branch assumes it becomes authoritative |

No "no" answers. The one conditional answer (K4.2/general_purpose_only) is
conditional by design, not by gap — the fence itself is the correct,
complete answer for a mission whose mandate was to protect that behavior,
not to redesign it (mission §33).
