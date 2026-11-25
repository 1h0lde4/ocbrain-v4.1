# Kernel v1.0 — Freeze Remediation Register (Decision-and-Closure Matrix)

**Status:** PROPOSED control artifact. Documentation only. **It authorizes nothing:** no implementation, merge, PR closure, tag, branch-protection change, policy acceptance or freeze verdict. Acceptance criteria below are **PROPOSED** (authored by this review, several adopted from an independent assessment of the baseline report) and bind no one until the project owner ratifies them.

Companion to `FREEZE_BLOCKER_AND_PRE_FREEZE_DEBT_REVIEW_NOV2026.md` (the read-only diagnostic baseline, left unchanged). Evidence files: `FREEZE_REVIEW_EVIDENCE_NOV2026/`.

## 1. Conventions

- **Baseline SHA for every row:** `fbe1ebdef553b52abf270a819d976d2e078feeef` (`main`, merge of PR #116). Evidence tags: **CONFIRMED** (reproduced or traced in live code), **STATIC** (read, not executed), **REGISTER-ONLY** (taken from project registers, not re-checked), **UNVERIFIED**.
- **Row classes:** `DEC` owner decision · `DEF` implementation defect · `EVG` evidence gap · `DOC` documentation drift. IDs are local to this register and deliberately do not reuse the register's `B1…B9` batch labels.
- **Four independent states per defect.** *Decision accepted* ≠ *implemented* ≠ *verified* ≠ *register updated*. A defect row is closable only when each applicable state is satisfied; none implies another (`PROJECT_INSTRUCTIONS.md` §0.3, §16.5, §24.2).
- **Status vocabulary:** decisions `OPEN (undecided)` / `PROPOSED` / `ACCEPTED` / `DEFERRED` / `REJECTED`; defects `OPEN` / `IN PROGRESS` / `FIXED` / `VERIFIED` / `DEFERRED` / `ACCEPTED RISK` / `BLOCKED`.
- **Implementation owner:** `UNASSIGNED` for every row. No assignment is recorded for these items; assigning one is itself an owner decision (the existing `docs/engineering/DEBT_BRANCH_OWNERSHIP_REGISTER_2026-11-02.md` is a dated Nov 2 branch/PR snapshot and was not re-inventoried here; this register complements it and does not replace it).
- **Closure authority (default):** the project owner, on evidence from an independent review. Decisions close only by the owner's written decision.
- **`IR`** = independent review of a pinned candidate SHA by a reviewer or session that did not author it, against the baseline reproduction. **`CE`** = CI success **plus** test-collection evidence **plus** per-test results (job log or artifact showing the named tests were collected and passed, not skipped or deselected). A green workflow alone is not `CE`.
- Not authority-bearing: dependency lists describe logical order only.

## 2. Errata and evidence upgrades against the baseline report

| Ref | Baseline report said | Corrected / upgraded position |
|---|---|---|
| E-1 | §5.1: namespace tests are not allowlisted, "so CI must pass them on its runner" | That was an **inference**. Observed: CI run `45521998261`, job `tests` — steps "Run test suite", "Upload full test output" and the gate all `success`. The per-test job log lives on a storage host not reachable from the review sandbox, so the eight namespace tests' individual results were **not seen**. Sandbox isolation stays **UNVERIFIED** (EVG-01). |
| E-2 | §3.3 DEBT-043: "still echoes the model-derived interpretation" | Imprecise. Live code confirms only the string at `content_anchor.py:317` and that `orchestrator.py:507-511` passes `structured_form["description"]` as the `interpretation`. That this equals the raw request (register: 33 of 33 rows) is **REGISTER-ONLY**. The register lists **three** defects (echo, `"; ".join` step-joining artifact, fixed example text) plus plan truncation; severity Low; dormant while `creative_content_anchor_enabled = false`. |
| E-3 | §2 FZ-07 R-1: STATIC | Behaviour **CONFIRMED** through the gate's own `evaluate()`: two failing parametrized IDs containing `" - "` collapse to one truncated ID (`tests/t.py::test_f[a`); count reconciliation then fails closed (`3 failed but 2 distinct FAILED node ID(s)`); an allowlisted failing ID containing `" - "` appears as a **new** failure (false red). **False green also reproduced, with a precondition:** with a hand-truncated allowlist entry (`tests/x.py::test_p[a`) and one real failing `tests/x.py::test_p[a - b]`, `evaluate()` returned `ok=True` (known failure seen, no new failure); with an empty allowlist the same output is red. The register already documents this limit and states such an entry "must never be written"; none of the 34 current allowlist entries contains `" - "` or is truncated, so it is not exploitable on `main` today without someone adding such an entry. |
| E-4 | §2 FZ-06: STATIC (default factory only) | All three production `CapabilityRequest(...)` sites (`core/capabilities/adapter_runtime.py:62`, `core/workers/capability_executor.py:116`, `core/workers/planner.py:321`) omit `trace_id`, so the `uuid4` default applies; `CapabilityResult` carries no identity field. Traced, not executed. (The register cites `planner.py:298`; the line has moved — see DOC-05.) |
| E-5 | §3.1 DEBT-012: writer "not necessarily a test", not attributed | **Attributed** (§4: DEF-08, DEF-09). Three full-suite runs produced identical tracked-file changes. TOML writers are specific tests; the SQLite change is an **import-time side effect**, identical with no test running. |
| E-6 | §5.3 / §6: SSE routes and proxy headers not probed | Partially probed in-process (EVG-02, EVG-03). Authorized-stream behaviour, real sockets and a real proxy remain untested. |
| E-7 | (assessment of baseline) FZ-05a "externally triggerable" | The creation path requires the bearer token (§5.3 probe: `/executions/*` return 401 unauthenticated), so growth is triggerable by any **authenticated client**, not an anonymous caller. Still unbounded; wording matters for severity. |

## 3. Owner decisions (class DEC)

| ID | Decision required | Why it matters / depends | Proposed closure condition | Status |
|---|---|---|---|---|
| DEC-01 | **FZ-D3:** which `EventStream` event classes are audit-durable; whether archival or compaction is acceptable. | Blocks DEF-06. `EventStream` is the Law 2 audit record: nothing may be deleted or compacted before this is decided. | Written decision (ADR) enumerating durable classes and the retention/compaction rule; recorded `ACCEPTED`. | OPEN (undecided) |
| DEC-02 | Outcome policy for `EMPTY_RESPONSE` and `COMPLETED_WITH_PARTIAL_OUTPUT` (currently pinned `success=True`: an implementation constraint, not an owner-approved contract — `KNOWN_ISSUES.md` FZ decision record). | Blocks DEF-03; determines how DEF-01 classifies them. FZ-D2 covers stalled/deadline only. | Per-class success/failure semantics stated, including where partial text lives. | OPEN (undecided) |
| DEC-03 | R-1 signature policy (last recorded as `PROPOSED`, not `ACCEPTED`). | Governs when DEF-07's gate may be called freeze-grade. Source documents are not on `main`; not re-verified here. | Owner acceptance after genuine environmental exception chains are observed and independently evaluated (last-recorded condition). | PROPOSED (REGISTER-ONLY) |
| DEC-04 | Ratify freeze-manifest verdict criteria and re-pin the draft from `488129b` to the then-current `main`. | Draft v0.1 exists only on `origin/security/codeql-findings-sep2026`; stale; criteria unratified. No verdict can be rendered until criteria and evidence are reconciled. | Criteria ratified in writing; manifest pinned to a stated SHA; evidence labelled. | OPEN (undecided) |
| DEC-05 | ADR-KERNEL-09: authorization model for mutating API routes. | Blocks DEF-10's authorization criteria. Authentication is not authorization. | ADR recorded `ACCEPTED` with roles/permissions per route. | PROPOSED |
| DEC-06 | DEBT-012: implementation owner and candidate (PR #91 is stale; whether to reuse it or start fresh), and whether DEF-08/DEF-09 are one workstream or two. | Both writers are now attributed (§4), so the A/B split can be decided on evidence. | Owner assigns scope and owner. | OPEN (undecided) |
| DEC-07 | CTX-AUTH-001b disposition. "Deliberately deferred" is not the same as "accepted as a freeze exception". | Freeze criteria (DEC-04) must say which it is. | Explicit `DEFERRED-and-excepted`, `ACCEPTED RISK`, or must-fix. | DEFERRED (exception status undecided; REGISTER-ONLY) |
| DEC-08 | FZ-06: whether an accepted design decision for end-to-end execution identity exists. The register records absence of an implementation only. | Blocks DEF-04 design. | Existing decision located, or a new ADR recorded. | UNKNOWN |

## 4. Implementation defects (class DEF)

| ID | Finding | Evidence @ baseline | Depends on | Proposed acceptance criteria | Required independent evidence | Status |
|---|---|---|---|---|---|---|
| DEF-01 | **FZ-01** — `/query` reports success regardless of workflow outcome. | `interface/api.py:231` (`handle()`), `:235` (`success=True`); **CONFIRMED** | Register: failure classification (DEC-02) and the terminal API/streaming contract | Implements **FZ-D1 option (a)**: public `handle() -> str` unchanged; a structured internal result consumed by the API; **no** typed exception as the primary result channel. `POST /query` returns `success=False` for failed workflows per DEC-02 classes; failure observable as an event; streaming path consistent. | Regression reproducing the audit scenario (red before, green after); `IR`; `CE`. | OPEN — decision ACCEPTED (FZ-D1), not implemented |
| DEF-02 | **FZ-02 cancellation / issue #105** — `Worker.execute()` converts `CancelledError` into a failed `WorkerResult`. | `core/workers/base.py:293-300`; swallow **CONFIRMED**; retry-after-cancel consequence **STATIC** | None technical; keep separate from the merged router-cleanup change (#104) | `CancelledError` propagates after cleanup; no retry after caller cancellation; regression reproduces #105 red-before; the caller-cancel, shutdown, client-disconnect and provider-termination cases each verified or explicitly scoped out. | Executed reproduction of the retry-after-cancel consequence (currently unreproduced); `IR`; `CE`. | OPEN |
| DEF-03 | **FZ-02 residual outcomes** — `EMPTY_RESPONSE`, `COMPLETED_WITH_PARTIAL_OUTPUT` pinned `success=True`. | `core/runtime/execution_outcome.py:81`; `core/model_router.py:505`; **CONFIRMED** | DEC-02 | Per DEC-02, once decided; tests pin the accepted semantics; docs updated. | `IR`; `CE`. FZ-02 is verified only for provider-failure and stalled/deadline classes (register). | BLOCKED (DEC-02) |
| DEF-04 | **FZ-06 / DEBT-030** — capability requests mint independent `trace_id`s; results carry no identity. | E-4: three construction sites, none passes `trace_id`; **CONFIRMED (traced)** | DEF-01 (failure-event contract), DEC-08 | A single query yields orchestrator events, workflow-execution records and capability requests sharing one joinable identity chain; no independent `uuid4` minted for in-flow requests; replay reconstructs the chain. | Executed end-to-end demonstration; `IR`; `CE`. | OPEN |
| DEF-05 | **FZ-05a** — unknown execution IDs allocate registry state; registry never evicts. | `interface/api.py:265`, `:276`; `ExecutionRegistry` methods: `attach_event_stream`, `create`, `get`, `_on_event`, `events`, `ids`; no removal call site found repo-wide (§7); **CONFIRMED (creation), STATIC (absence)** | DEF-01, DEF-04 (register ordering) | (From the independent assessment, adopted as PROPOSED.) Unknown IDs allocate no persistent entries; registry memory has a finite bound; lifecycle cleanup is deterministic; event retrieval never recreates deleted or nonexistent executions. Register treats this separately from DEF-06. | Re-run of the register's 20,000-random-ID measurement (baseline there: `_graphs`/`_queues` 1 → 20,001 entries, RSS about +89.7 MB) showing the bound; `IR`; `CE`. | OPEN |
| DEF-06 | **FZ-05b** — no `EventStore` retention/compaction. | None found in `core/events/` (§7); register measured about 13.4 kB/request, **not re-measured**; **STATIC / UNVERIFIED (growth)** | DEC-01 | Defined only after DEC-01; must preserve Law 2 audit integrity. | Measurement of growth before/after; `IR`; `CE`. | BLOCKED (DEC-01) |
| DEF-07 | **FZ-07 residual R-1** — CI gate cuts `FAILED` IDs at the first `" - "`. | `scripts/ci_test_gate.py:110`; behaviour **CONFIRMED** (E-3) | DEC-03; governed by its own corrective-programme authorization request (last recorded as documentation-only with implementation unauthorized; source not on `main`, **not re-verified**) | Per that programme's scenario-to-verdict contract; not restated here. Candidate PR #107 is a diagnostic draft, not for merge. | `IR` against the original bypass reproductions; the register's F-5 (suite-shrink integrity) is last recorded as mandatory before the gate is called freeze-grade. | OPEN — gated |
| DEF-08 | **DEBT-012A** — test fixtures persist content changes to tracked config. | `FREEZE_REVIEW_EVIDENCE_NOV2026/`: three identical runs; writers `tests/test_module_factory.py`, `tests/test_module_factory_security.py` (all three TOML files), `tests/test_model_router.py` (`models.toml`), plus one `settings.toml` write outside any test body (unattributed); **CONFIRMED** | DEC-06 | A full suite leaves `git status --porcelain -- config data` empty; fixtures isolate to temporary paths; a guard (test or CI step) fails if tracked config changes during a run; verified over repeated and partial runs, not one clean run. | Preserved before/after diffs (evidence dir); `IR`; `CE`. | OPEN |
| DEF-09 | **DEBT-012B** — importing the app mutates tracked `data/context.sqlite`. | `core/context.py:320` module-level `context_memory = ContextMemory()` opens the DB at `:34`; reached via `core/orchestrator.py:13`; `import interface.api` alone changes the file (hash `858b5af1…` → `a59c39a2…`, deterministic, equal to the post-suite hash); **CONFIRMED** | DEC-06 | Importing `core.orchestrator` / `interface.api` modifies no tracked file; the database is created lazily or lives outside the tracked tree; migration/compatibility impact of removing the import-time singleton (callers elsewhere) assessed before the change, not assumed trivial. Relevant constraints: Law 4, "hidden side effects", "hidden mutable globals". | Before/after hashes; `IR`; `CE`. | OPEN |
| DEF-10 | **DEBT-025** — authorization and durable audit. | Authentication **VERIFIED** for the probed scope (§5.3 of the baseline and EVG-02/03); one bearer token reaches every mutating route; durable-audit candidate PR #112 (draft) | DEC-05 | Separate authentication and authorization acceptance criteria; explicit role/permission boundaries for `PUT /config`, `POST /update/install`, `/update/restart`, `/rollback`, `/modules/new`, `/import`; durable audit events including failure scenarios. | `IR`; `CE`; adversarial authorization tests. | OPEN (authN verified; authZ and audit open) |
| DEF-11 | **DEBT-043** — content-anchor clarification defects (three, plus plan truncation). | `content_anchor.py:317`; call site `orchestrator.py:507-511`; dormant behind the flag; candidate PR #117 (open, behind `main`); **CONFIRMED (code present)** | Owner selected containment option C-plus (ADR-KERNEL-07 §10.5) | As selected by the owner: at most three genuine plan steps, corrected formatting, an honest representation of the intent, and an artifact-appropriate question. | `IR` of #117 after rebase; `CE`. Severity Low. | OPEN — selected, not implemented/verified |
| DEF-12 | **DEBT-028** — no instance-level lock in `WorkflowRuntime`. | No `Lock`/`Semaphore`/claim/in-flight symbol anywhere in `core/workflow/` (§7); candidate PR #114 (open); **STATIC** | — | Per the DEBT-028 register row: concurrent `execute()`/`resume()` on one `instance_id` cannot run simultaneously; demonstrated by a concurrency test. | Concurrency reproduction; `IR` of #114; `CE`. | OPEN |
| DEF-13 | **DEBT-014** — DRIFT-10 checks only `intent.py`/`planner.py`. | `compiler.py:388` and `learning.py:668` also call `evaluate_action()`; **STATIC** | — | DRIFT-10 covers the full cognitive directory or documents exemptions as DRIFT-07 does; drift check still 30 PASS / 0 FAIL. | `IR`; `CE`. | OPEN |
| DEF-14 | **CTX-AUTH-001b** — parser-acceptance hardening. | **REGISTER-ONLY** | DEC-07 | Defined by the owner's disposition (DEC-07). | — | DEFERRED (exception status per DEC-07) |

## 5. Evidence gaps (class EVG)

| ID | Gap | Observed so far | Required to close | Status |
|---|---|---|---|---|
| EVG-01 | Sandbox isolation (8 `tests/core/sandbox/test_namespace_backend.py` tests). | Fail in the review sandbox (no namespace privileges: environmental); CI run `45521998261` `tests` job green, per-test log not retrievable from the sandbox (E-1). | Job log or "full test output" artifact showing all 8 **collected and passed** (none skipped), or a `-v` run on a privileged runner; the egress, memory, pids, seccomp and UTS cases actually exercised. | OPEN |
| EVG-02 | SSE route authentication. | In-process: `/events` and `/executions/{id}/events` return 401 with no token, a wrong token, and a token only in the query string. | Authorized-stream behaviour, a real socket, and the failure/disconnect behaviour. | PARTIAL |
| EVG-03 | Reverse-proxy / forwarded headers. | In-process: `X-Forwarded-For`, `X-Forwarded-Host/Proto`, `Forwarded`, `X-Original-URL/X-Rewrite-URL` did not change the 401 outcome; `Host: evil.example` with `X-Forwarded-Host: localhost` returned 400. | A real proxy configuration and socket-level test. | PARTIAL |
| EVG-04 | FZ-05b storage growth. | Register-only figure (about 13.4 kB/request). | Fresh measurement at the candidate SHA (DEF-06). | OPEN |
| EVG-05 | Dependabot #1–#7. | 7 open (3 critical, 4 high); chromadb CVE-2026-45830/-45831/-45833 each listed twice (#1/#5, #2/#6, #3/#7); sentence-transformers (#4, critical). Duplicate manifest plausible, **UNCONFIRMED**. | Per alert: manifest, affected range, whether the dependency is on a reachable path under the embedded-only boundary, disposition. | OPEN |
| EVG-06 | Candidate PRs #112, #114, #115, #117, #91, #102, #107. | Diffs not reviewed; #117 `mergeable_state: behind`. | `IR` each; no PR is assumed correct. | OPEN |
| EVG-07 | CTX-AUTH-001b live status. | **REGISTER-ONLY**. | Trace the live path and state the finding. | OPEN |
| EVG-08 | Retry-after-cancel (DEF-02). | Source reading only. | Executed reproduction. | OPEN |

## 6. Documentation drift (class DOC)

Closure authority: the project owner via a documentation-only PR. Updating a register does not fix the underlying defect.

| ID | Drift | Evidence | Status |
|---|---|---|---|
| DOC-01 | DEBT-042 recorded OPEN / "not fixed" in `KNOWN_ISSUES.md` and `CURRENT_STATE.md`, but fixed in code by PR #116 (`1e7d27b`: `_fts_escape()` quotes every token as a literal; uppercase `AND`/`OR`/`NOT`/`NEAR` now literal terms — an intentional behaviour change to record). | PR #116 changed 3 files and no docs; 102 tests passed locally. State is FIXED; closure needs this reconciliation and residual scope recorded. | OPEN |
| DOC-02 | DEBT-012 row says `models.toml`/`sources.toml` are "line-ending noise only" and understates `settings.toml`. | Evidence directory; content changes are real (e.g. `bootstrap_model` `llama3` → `mistral`; `module_factory_enabled = false` added; test sections persisted into `sources.toml`). | OPEN |
| DOC-03 | Dependabot set recorded as #1–#4; seven alerts are open. | EVG-05. | OPEN |
| DOC-04 | `CURRENT_STATE.md` headline sync is Nov 19; main has since merged #83, #88, #79, #116. The "20 open PRs" figure in the ownership register is the Nov 2 snapshot; the live count is 12. | GitHub API, Nov 25. | OPEN |
| DOC-05 | Line citations drifted: DEBT-030 cites `planner.py:298` (now `:321`); DEBT-043 cites `intent.py:1090` for the `raw_request` assignment (line 1090 is now `_validate_structured_form`). | Live code. | OPEN |
| DOC-06 | Baseline report errata E-1 to E-7 (§2). | This document. | RECORDED here; baseline left unchanged by design. |

## 7. Search scope behind the "absence" findings

An absence claim is weaker than a presence claim. Scope used, and what would strengthen each:

| Claim | Scope searched | Would be stronger with |
|---|---|---|
| No eviction/removal of `ExecutionRegistry` entries (DEF-05) | Class method list read in full (`core/runtime/execution_graph.py`); repo-wide Python grep (`core`, `interface`, `scripts`) for `_graphs` / `execution_registry` lines containing `pop(`, `del `, `.clear(`, `remove`, `evict`, `expire`, `ttl` returned **no matches** | An AST-based reference analysis, plus the executed bound measurement |
| No `EventStore` retention (DEF-06) | Grep of `core/events/` and `interface/` for `retention`, `prune`, `compact`, `VACUUM`, `DELETE FROM`, `expire`, `ttl` returned no relevant matches (only unrelated throttling in `interface/auth.py`) | A measured growth run; review of operational scripts outside these paths |
| No instance lock (DEF-12) | Grep of all of `core/workflow/` for `Lock`, `Semaphore`, `_claim`, `in_flight`, `inflight`, `instance_lock` returned **no matches** | A concurrency test that attempts the double `execute()`/`resume()` |
| No identity on `CapabilityResult` (DEF-04) | Class body read (about 14 lines after the declaration) | Full-field read and an executed end-to-end trace |

## 8. Logical constraints (not an authorization to proceed)

- `DEF-01` → `DEF-04` → `DEF-05` (register ordering). `DEC-01` → `DEF-06`. `DEC-02` → `DEF-03` (and informs `DEF-01`). `DEC-05` → `DEF-10`. `DEC-03` and `DEF-07`'s own authorization gate apply to R-1; they are not an ordinary sequence slot.
- **Verification integrity first or in parallel.** `DEF-08` and `DEF-09` make every full-suite verification run dirty tracked config and the tracked database (including `bootstrap_model`), and `DEF-07` (with its suite-shrink integrity item) bears on whether a green CI is evidence. Closure evidence for `DEF-01` to `DEF-06` depends on both, so I would not defer them behind the functional fixes. The independent assessment instead placed these at positions 6–7 of an 11-step order; that difference is left for the owner.
- `DEC-04` gates the freeze verdict, not the defect work.
- No row may be closed on the basis of another row's closure, a passing regression test alone, or a register edit.

## 9. Open questions

1. Which owner decides DEC-06's single-vs-split workstream, now that both writers are attributed?
2. Is the `<between tests>` `settings.toml` write (evidence directory) collection-time, a fixture, or teardown code? Not further attributed.
3. Does DEC-08 already have a decision record somewhere not on `main`?
4. Should EVG-01 be satisfied by a retained CI artifact or by a privileged-runner run?

## 10. Transfer note

New files only, on branch `docs/freeze-blocker-debt-review-nov2026` (base `main` @ `fbe1ebd`): this register and `FREEZE_REVIEW_EVIDENCE_NOV2026/`. No code, test, register, configuration or policy file is changed. Nothing is merged to `main`.
