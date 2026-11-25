# Kernel v1.0 — Remaining Freeze Blockers and Pre-Freeze Debts: Live-Repository Review

**Status of this document:** read-only review report. **No freeze verdict is rendered.** It does not ratify the freeze-manifest criteria, accept any owner decision, close any finding, or authorize any merge, tag or branch-protection change.

## 1. Metadata

- Baseline: `main` @ `fbe1ebdef553b52abf270a819d976d2e078feeef` (merge of PR #116, 2026-11-25 00:56 UTC). `origin/main` re-fetched before commit: still `fbe1ebd`.
- Method: fresh clone of `https://github.com/1h0lde4/ocbrain-v4.1`, read of the governing registers, tracing of the live code paths, one full-suite run, targeted adversarial runtime probes, read-only GitHub API reads.
- Evidence tags: **CONFIRMED** = reproduced or traced in live code at the baseline; **STATIC** = code read only, not executed; **REGISTER-ONLY** = taken from `KNOWN_ISSUES.md` / `CURRENT_STATE.md`, not re-checked here; **UNVERIFIED** = not examined or not examinable in this environment.
- Authority applied: live code and executed tests over documentation (`PROJECT_INSTRUCTIONS.md` §0.1–0.2). Registers were used to know what to verify, never as evidence.
- Author identity for the commit: `Claude (freeze review) <claude@anthropic.com>`.

## 2. Freeze blockers still open on `main`

| ID | Finding | Evidence | Status |
|---|---|---|---|
| FZ-01 | `POST /query` reports success regardless of workflow outcome. `answer = await _orchestrator.handle(...)` then `QueryResponse(success=True, ...)` with no failure branch; `handle()` still returns `str`. FZ-D1 (option a) is accepted but the structured internal result is not implemented. | `interface/api.py:231`, `:235` | OPEN — CONFIRMED |
| FZ-02 (residual 1) | `COMPLETED_WITH_PARTIAL_OUTPUT` and `EMPTY_RESPONSE` remain pinned as `success=True`. Not owner-accepted (FZ-D2 covers stalled/deadline only). | `core/runtime/execution_outcome.py:81`; `core/model_router.py:505` | OPEN — CONFIRMED (outcome policy is an owner decision) |
| FZ-02 (residual 2) / issue #105 | `Worker.execute()` catches `asyncio.CancelledError` and returns a failed `WorkerResult` instead of re-raising, so cancellation is absorbed. The retry-after-cancel consequence described in #105 was not executed here. | `core/workers/base.py:293-300` | OPEN — CONFIRMED (swallow), STATIC (retry consequence) |
| FZ-05a | `GET /executions/{id}` and `/executions/{id}/events` create registry state for unknown IDs; `ExecutionRegistry` has no eviction, removal or TTL method (its methods are `attach_event_stream`, `create`, `get`, `_on_event`, `events`, `ids`). | `interface/api.py:265`, `:276`; `core/runtime/execution_graph.py:133-190` | OPEN — CONFIRMED (creation path), STATIC (no eviction) |
| FZ-05b | `EventStore` retention. No retention/compaction code found under `core/events/`. Growth not re-measured. Needs FZ-D3. | `core/events/` | OPEN — STATIC / UNVERIFIED (growth) |
| FZ-06 / DEBT-030 | `CapabilityRequest.trace_id` defaults to a fresh `uuid4`; no accepted end-to-end identity join. | `core/capabilities/capability.py:93` | OPEN — STATIC |
| FZ-07 residual R-1 | CI gate still truncates `FAILED` ids at the first `" - "`. PR #107 is a diagnostic draft, not for merge. | `scripts/ci_test_gate.py:110` | OPEN — STATIC |
| CTX-AUTH-001b | Parser-acceptance hardening deliberately deferred; register says OPEN. | `KNOWN_ISSUES.md` / `CURRENT_STATE.md` | OPEN — REGISTER-ONLY |
| Freeze manifest | Exists only as DRAFT v0.1 on `origin/security/codeql-findings-sep2026`, pinned to `488129b`; stale against `fbe1ebd`; criteria unratified; not on `main`. | `git ls-tree` over all remote branches | NOT DONE — CONFIRMED |

Register dependencies recorded for sequencing (REGISTER-ONLY): FZ-06 depends on FZ-01's failure-event contract; FZ-05a (B6) follows FZ-01/FZ-06; FZ-05b (B7) is blocked on FZ-D3.

## 3. Pre-freeze debts

### 3.1 DEBT-012 — understated in the register (new evidence)

Running `pytest tests -q` on `main` leaves four tracked files modified (`git status --short`):
`config/models.toml`, `config/settings.toml`, `config/sources.toml`, `data/context.sqlite`.

`git diff --ignore-cr-at-eol --stat -- config` shows content changes, not only CRLF noise (3 files, 6 insertions, 35 deletions). Observed:
- `settings.toml`: loses the `import_root` documentation block (CTX-EXPORT-001) and the ADR-KERNEL-07 comment block; gains `module_factory_enabled = false`.
- `models.toml`: `bootstrap_model = "llama3"` becomes `"mistral"`; `query_count` changes.
- `sources.toml`: `[test_config_reg_tmp]` replaced by `[test_rce001_name_tmp]` (test-fixture sections persisted into a real config).
- `data/context.sqlite` (a tracked binary runtime database) is also modified; it was also found modified after the auth probe (§5.3), which only imported the API app, called `setup()` and issued requests, so the writer is not necessarily a test.

The register row states `models.toml`/`sources.toml` are "line-ending noise only (CRLF → LF, no content difference)" and `settings.toml` loses "5 lines" of comment. Both statements are contradicted by this run. Single reproduction in one environment; the responsible test(s) were not identified and test-order dependence is UNKNOWN. All modifications were reverted in the review clone. Candidate fix PR #91 is old (last updated 2026-11-02, register: 96 commits behind) and no replacement has been selected.

### 3.2 DEBT-025 — authentication boundary holds; authorization residual remains

- Runtime probe (§5.3): no bypass found. Residual (REGISTER-ONLY, consistent with code): one bearer token reaches every mutating route, including `PUT /config`, `POST /update/install`, `POST /update/restart`, `POST /rollback`, `POST /modules/new`, `POST /import`. ADR-KERNEL-09 is PROPOSED. Durable authentication audit events are PR #112 (draft, 7 files, +704/-13).
- Status: OPEN (authentication IMPLEMENTED and VERIFIED for the probed scope; authorization and durable audit open).

### 3.3 Other debts

| ID | Finding | Evidence | Status |
|---|---|---|---|
| DEBT-043 | Clarification response still echoes the model-derived interpretation (`Here's how I read your request: ...`). Dormant: `creative_content_anchor_enabled = false`. C-plus selected by the owner (ADR-KERNEL-07 §10.5), implementation is PR #117 (open, 8 files, GitHub `mergeable_state: behind`). | `core/cognitive/content_anchor.py:317` | OPEN — CONFIRMED on `main` |
| DEBT-028 | No instance-level lock in `WorkflowRuntime` (no lock/claim/in-flight symbol found). PR #114 open (9 files). | `core/workflow/runtime.py` (grep, no match) | OPEN — STATIC |
| DEBT-014 | DRIFT-10 names `intent.py` and `planner.py` only, while `compiler.py:388` and `learning.py:668` also call `GovernanceKernel.evaluate_action()` directly. Candidate PR #102 (last updated 2026-11-02). | `core/cognitive/compiler.py:388`; `core/cognitive/learning.py:668`; `scripts/check_drift.py` | OPEN — STATIC |
| DEBT-032 / Dependabot | 7 open alerts: #4 critical (sentence-transformers, CVE-2026-68770); chromadb CVE-2026-45830 / -45831 / -45833 each appear twice (#1/#5, #2/#6, #3/#7; two are critical, four high). The register tracks #1–#4 only. Duplicate listing from a second manifest is plausible but UNCONFIRMED; #5–#7 are unassessed. Issues #65 and #70 remain open; PRs #32/#33 must not be merged (register decision). | GitHub Dependabot API read | OPEN — CONFIRMED (alert count), UNVERIFIED (exposure) |
| DEBT-015(7), DEBT-018, DEBT-021, DEBT-024, DEBT-027, DEBT-039–041, G4 D1–D11 | Not examined in this review. | — | REGISTER-ONLY |

## 4. Documentation drift (code ahead of registers)

- **DEBT-042 is fixed in code but recorded as OPEN.** PR #116 (`1e7d27b`) rewrote `SqliteStorage._fts_escape()` (`core/memory/backends/sqlite_storage.py:371`) to quote every token as a literal and added `tests/test_debt042_fts5_literal_queries.py`; the PR changed no documentation. `KNOWN_ISSUES.md` (DEBT-042 row) and `CURRENT_STATE.md` still read "OPEN, reproduced, not fixed" / "still open". Per §16.5 the state is FIXED with the regression tests passing (102 passed, §5.2); *closure* additionally needs the register reconciled and any residual scope (intentional change: uppercase `AND`/`OR`/`NOT`/`NEAR` now literal terms) recorded.
- `CURRENT_STATE.md` last synchronized Nov 19; main has since merged #83, #88, #79, #116 (the file does record #83/#88 in places, but its headline sync is stale). The "20 open PRs" figure is the Nov 2 snapshot; live count is 12.
- DEBT-012 row contradicted by §3.1; Dependabot alert set stale (§3.3).

## 5. Verification evidence

### 5.1 Full suite at `fbe1ebd`
- Environment: Python 3.12.3, `chromadb==0.5.3`, numpy 1.26.4, scipy 1.13.1; `sentence-transformers` and `spacy` not installed.
- Command: `python -m pytest tests -q -p no:cacheprovider --maxfail=80`
- Result: **8 failed, 2435 passed, 1 xfailed** in 77 s. All 8 failures are `tests/core/sandbox/test_namespace_backend.py` (egress denied, memory limit, pids limit, artifacts, seccomp ptrace/mount/normal-exec, UTS namespace) and are classed **environmental** (this sandbox lacks namespace privileges); sandbox isolation is therefore **UNVERIFIED by this review**. They are not in the 34-entry allowlist, so CI must pass them on its runner.
- None of the 34 allowlisted tests failed here (INFER: the allowlist entries are environment-specific; its continued necessity on CI's environment is not established by this run).
- `python scripts/check_drift.py` (run on the branch with this report present): 30 PASS, 0 FAIL.
- CI on `main` @ `fbe1ebd` (GitHub check-runs): `tests`, `drift-and-ownership`, `token-acl-windows`, CodeQL ×3 all `success`. Open CodeQL alerts: 0.

### 5.2 DEBT-042 regression
`pytest tests/test_debt042_fts5_literal_queries.py tests/test_session4b_memory_hardening.py` → 102 passed.

### 5.3 API authentication probe (runtime, FastAPI `TestClient`, throwaway token via `OCBRAIN_API_TOKEN`)
- 23 route/method pairs probed; the 2 SSE routes (`/events`, `/executions/{id}/events`) were **not** probed.
- No token and wrong token: every pair `401` except `GET /` (`200`, the intentionally public shell).
- Variants without a token: `/health/`, `/Health`, `/%68ealth`, `POST /query/` → `401`; `GET //health`, `//config`, `//debug`, `//modules` → `200` but the body is the public shell HTML, not protected data; `PUT //config`, `POST //update/install`, `POST //rollback`, `GET ///health` → `401`. Host headers `evil.example` and `localhost.evil.com` → `400`. A valid token on all GET routes → `200`.
- Limits: in-process client, not a real socket; no proxy/`X-Forwarded-*` cases; SSE routes untested.

## 6. Not verified in this review

FZ-05b growth; SSE route authentication; sandbox isolation (§5.1); DEBT-021/039/040/041 (the `sandbox-fabric` branch, not on `main`); whether PR candidates #114/#117/#112 are correct (their diffs were not reviewed); CTX-AUTH-001b beyond its register status; FZ-06 beyond the default-factory site.

## 7. Owner decisions outstanding (not taken here)

FZ-D3 (FZ-05b audit-durable event classes); the `EMPTY_RESPONSE` / `COMPLETED_WITH_PARTIAL_OUTPUT` outcome policy; the R-1 signature policy; ratification of the freeze-manifest verdict criteria and a re-pin to current `main`; ADR-KERNEL-09; selection of a DEBT-012 implementation owner/candidate; whether CTX-AUTH-001b stays deferred.

## 8. Proposed next steps ([REC] — proposals only)

1. Re-pin and refresh the freeze-manifest draft against `fbe1ebd` (or its successor) before any criteria discussion.
2. FZ-01 first: it gates FZ-06 and FZ-05a per the register.
3. DEBT-012: identify the writing fixture(s) and isolate to `tmp_path`; it makes every verification run dirty the tree and can flip `bootstrap_model`.
4. Reconcile `KNOWN_ISSUES.md` / `CURRENT_STATE.md` for DEBT-042, DEBT-012 and the Dependabot set in a documentation-only PR.
5. Assess Dependabot #5–#7 against the existing embedded-only boundary decision.
6. Re-run the sandbox suite on a privileged runner to obtain the isolation evidence this review could not.

## 9. Transfer / branch note

Single new file on branch `docs/freeze-blocker-debt-review-nov2026` (base `main` @ `fbe1ebd`). No code, test, register, configuration or policy file is changed. Nothing is merged to `main`.
