# Session Handoff

> Branch `handoff/codeql-remediation-sep2026` holds this file only. It is a transfer record, **not** an authority, and must **not** be merged into `main` (PROJECT_INSTRUCTIONS §18.4.8.10). Verify everything below against the live repository before relying on it (§18.4.9). No secrets are recorded here; the two GitHub tokens involved are deliberately omitted.

## 0. Update after the first commit (2026-10-02, verified; supersedes conflicting text below)

The repository moved while this handoff was being written, and **another session is already acting on it**. (Commits from sessions of this kind carry the same author string, "Claude (sandboxed session)", so author names cannot tell sessions apart.) Verified against GitHub:

- `main` is now `4ab5345` (verify live). **#40** (merge `9b172d0`) and **#42** (merge `4bb5974`) were merged by `1h0lde4` on 2026-10-02, all five checks green. **#43** (docs, author and merger `1h0lde4`, commit `cc01a61`) registered #36/#39/#40/#42 under DEBT-037 and added the path-injection source classification to DEBT-038 with **no new ID** -- this completes §17 step 4 and R-9.
- `1h0lde4` dismissed four Code Scanning alerts on 2026-10-02 (00:43-00:44 UTC): the three `py/incomplete-url-substring-sanitization` ones ("used in tests") and `py/path-injection` at `core/brain_export.py:161`, the `extractall` ("false positive: zipfile.extractall() sanitizes ../, absolute and drive-qualified..."). **Open alerts on `main`: 29, all `py/path-injection`, none of any other rule.** That settles R-12 for those four only; the 29 remaining are not individually dispositioned beyond the classification now in DEBT-038.
- **PR #44** (`fix/import-root-containment-oct2026`, author `1h0lde4`, head `8dec787`) is **open**: it requires `bundle_path` on `/import` and `/brain/v2/import` to resolve inside a configured import root (CTX-EXPORT-001; a behavior change on both import routes; it touches `config/settings.toml`). At last look its `CodeQL` check was **failure** and `mergeable_state` was `unstable`; the other checks passed. It addresses the "by design" `/import` source in §6 (source 481). **It is another session's work in progress: do not edit or merge it, and establish who owns it before acting.**
- PR #45 (docs: runbook for ADR-KERNEL-07's live draft-plan check) is a different workstream. A new `Graphify` check now appears on PRs; it was not investigated, and `drift-and-ownership` is still green.
- **Superseded below:** statements that #40/#42 are open, that `main` is `ecddbff`, that #42's CI is unknown, and that 32 alerts are open; the §15 rows on merges and URL dispositions; §17 steps 3-4; §19. They are left in place as the record of the first commit.

## 1. Handoff Metadata

- Handoff version: 1
- Created at: 2026-10-01 (UTC). Session spanned 2026-09-26 → 2026-10-01.
- Workstream: security-finding remediation on `1h0lde4/ocbrain-v4.1` -- the CodeQL findings Moncif supplied, and everything verification of them led to (CTX-EXPORT-001 export half, exception-text disclosure, `/distill` path traversal, answer-text redaction). Context: Kernel v1.0 freeze.
- Task identifier: DEBT-019 / CTX-EXPORT-001, DEBT-037, DEBT-038; three fixes not yet registered (see §6, §17).
- Source session purpose: verify the supplied CodeQL write-up against live code, fix what is real, report honestly what is not.
- Transfer status: §19.
- Who works on this repo besides this workstream: Moncif (commits as `N4Z`) and **other Claude sessions** (commits authored `Claude-claude.ai-sandbox`) merge to `main` concurrently on unrelated workstreams (ADR-KERNEL-07, intent-sufficiency, etc.). Do not touch those.

## 2. Original Starting Prompt

The session's first message contained **no written task sentence**. It contained:

1. `PROJECT_INSTRUCTIONS.md` pasted in full. The root `PROJECT_INSTRUCTIONS.md` is a 129-byte stub that points to `docs/architecture/PROJECT_INSTRUCTIONS.md` (the existence of that target was not re-verified). The pasted copy was **not** diffed against the repo copy.
2. A saved-preferences field containing a GitHub personal access token. **Secret -- not recorded here.** That token turned out to be dead (HTTP 401).
3. The CodeQL write-up below, **verbatim**. It was an excerpt of a much larger alert set (35 open alerts at the time, not 2) and it did not mention several things found later; see §6 and §11.

<details><summary>The CodeQL write-up, verbatim</summary>

`````text
I checked the current `main` branch rather than relying on the CodeQL report alone. Both findings are legitimate, and they expose two different trust-boundary problems.

### 1. `interface/api.py:160` — information exposure through an exception

This is a real **CWE-209 / CWE-497** issue. CodeQL rates `py/stack-trace-exposure` at security severity **5.4** with high precision. ([CodeQL][1])

The current `/query` handler does this:

```python
except Exception as e:
    err_msg = f"{type(e).__name__}: {e}"
    logging.getLogger("ocbrain").error(
        f"POST /query failed: {err_msg}\n{traceback.format_exc()}"
    )
    return QueryResponse(
        success=False,
        answer="I encountered an internal error. Check logs for details.",
        error=err_msg,
        meta={"traceback": traceback.format_exc()
              if config.get("global.debug") else None}
    )
```

So there are actually **two leak paths**:

| Path                        | Leak                                                   |
| --------------------------- | ------------------------------------------------------ |
| `error=err_msg`             | Exception class + exception message returned to caller |
| `meta.traceback` when debug | Full server traceback returned to caller               |

The server-side logging is fine. The problem is the response.

This matters because exception messages can contain filesystem paths, internal component names, SQL fragments, provider details, configuration information, and other implementation details. That is exactly the class of exposure CodeQL is warning about. ([CodeQL][1])

There is also a **second instance of the same architectural mistake** in `core/brain_api.py`:

```python
except Exception as e:
    yield f"data: {json.dumps({'error': str(e)})}\n\n"
```

So fixing only `interface/api.py:160` would leave another API error path leaking raw exception text.

**Correct fix:** keep the full exception and traceback in server logs, but return a stable public error contract, preferably with an opaque error/event ID:

```python
except Exception:
    error_id = str(uuid.uuid4())
    log.exception("POST /query failed; error_id=%s", error_id)

    return QueryResponse(
        success=False,
        answer="I encountered an internal error. Check logs for details.",
        error="internal_error",
        meta={"error_id": error_id},
    )
```

And the streaming endpoint should do the equivalent.

The current source is here: [interface/api.py on main](https://github.com/1h0lde4/ocbrain-v4.1/blob/main/interface/api.py?utm_source=chatgpt.com#L150-L170)

---

### 2. `core/brain_export.py:75` — uncontrolled data in path expression

This is the more important finding. CodeQL's `py/path-injection` is rated security severity **7.5**, high precision, covering CWE-22/CWE-23/CWE-36/CWE-73/CWE-99. ([CodeQL][2])

The important detail is that **the existing `module_name.isidentifier()` fix only protects the import path**. The export side still trusts the caller.

Current flow:

```python
def export_module(module_name: str, output_path: Optional[Path] = None):
    ...
    mod_dir = MODULES / module_name

    if output_path is None:
        output_path = EXPORTS / f"{module_name}_{ts}.ocbrain"
```

Then that attacker-controlled path propagates into:

```python
weights_src = mod_dir / "weights" / "active"
kb_src      = mod_dir / "knowledge.db"
eval_src    = DATA / "evals" / f"{module_name}.json"
raw_dir    = DATA / "raw" / module_name
```

and subsequently into `exists()`, `copytree()`, `copy2()`, `rglob()`, `read_text()`, etc.

That means the current security situation is asymmetrical:

```text
IMPORT
manifest.module_name
        ↓
isidentifier()
        ↓
MODULES / name
        ✅ containment against traversal

EXPORT
HTTP module_name
        ↓
MODULES / module_name
        ❌ no validation
        ↓
filesystem reads + output path construction
```

This is a genuine vulnerability, not merely CodeQL being unable to understand the architecture.

CodeQL explicitly recommends validating user-controlled paths and, where appropriate, normalizing/resolving them and checking containment within a trusted root. ([CodeQL][2])

The current implementation is here: [brain_export.py on main](https://github.com/1h0lde4/ocbrain-v4.1/blob/main/core/brain_export.py?utm_source=chatgpt.com#L35-L110)

### Why this is particularly relevant to OCBrain

The API exposes:

```python
@app.post("/export")
async def export_module(req: ExportRequest):
    path = export_module(req.module_name)
```

and `ExportRequest.module_name` is just:

```python
class ExportRequest(BaseModel):
    module_name: str
```

So there is a direct:

```text
HTTP request
   ↓
module_name
   ↓
export_module()
   ↓
filesystem path construction
```

The same API also exposes `/import` with a raw `bundle_path`, which is another path-trust boundary worth tightening. [brain_api.py on main](https://github.com/1h0lde4/ocbrain-v4.1/blob/main/core/brain_api.py?utm_source=chatgpt.com#L50-L155)

---

## The correct remediation

I would **not** solve this with CodeQL suppressions.

The clean design is to establish a single invariant:

> A module identifier is a logical identifier, never a filesystem path.

Then enforce it at the filesystem boundary, not merely at API-model level.

A good implementation would centralize something like:

```python
def _validated_module_dir(module_name: str) -> Path:
    if not module_name.isidentifier():
        raise ValueError(
            f"Invalid module name: {module_name!r}"
        )

    root = MODULES.resolve()
    candidate = (root / module_name).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError("Module path escapes modules directory")

    return candidate
```

Then **export and import both use the same helper**, instead of each caller constructing `MODULES / name` independently.

For export specifically, I would additionally require that the module actually exists as a directory before touching anything:

```python
mod_dir = _validated_module_dir(module_name)

if not mod_dir.is_dir():
    raise ValueError(f"Module {module_name!r} not found")
```

That fixes the whole family of export sinks at once:

```text
mod_dir
├── weights_src
├── kb_src
├── eval_src
└── raw_dir
```

and also makes:

```python
EXPORTS / f"{module_name}_{ts}.ocbrain"
```

safe because `module_name` is guaranteed to be one logical identifier rather than an arbitrary path.

---

## One more thing CodeQL has helped reveal

There is a broader pattern in the repository:

```text
module_name
    ↓
learning/distiller.py
learning/trainer.py
learning/cleaner.py
learning/crawler.py
learning/gap_detector.py
core/brain_export.py
```

Several of these construct filesystem paths from `module_name` directly. I verified examples such as:

```python
DATA_RAW / module_name
```

in the learning subsystem.

That does **not automatically mean every one of those sites is exploitable**. The important question is whether the value at that call site can originate from an untrusted boundary. But it strongly suggests that `module_name` needs to become a **first-class validated identifier type/invariant**, rather than relying on every subsystem to remember its own check.

That is exactly the sort of systemic hardening that will prevent the next CodeQL run from rediscovering the same class of defect under a different sink.

---

## Freeze impact

I would classify them separately.

**Issue 1:** real security defect, moderate severity, relatively small remediation. It is outside the kernel's core authority model but should be fixed before calling the shipped API surface security-clean.

**Issue 2:** real path-traversal boundary defect, materially more serious. It is in the export subsystem and is directly reachable through the API. I would treat this as a **release blocker for the export/API surface**, not something to dismiss as a CodeQL false positive.

There is an additional important nuance: the current server binds to `127.0.0.1`, so this is not presently equivalent to an Internet-exposed service. The repository's own security audit also documents that the API has no real authentication; the CSRF header protects against browser CSRF, not an arbitrary local process. [main.py](https://github.com/1h0lde4/ocbrain-v4.1/blob/main/main.py?utm_source=chatgpt.com#L430-L470)

So the practical threat model today is primarily:

```text
malicious / compromised local process
        ↓
localhost OCBrain API
        ↓
path injection / exception disclosure
```

That is still significant for a local-first governed system, because **localhost is not the same thing as authenticated/trusted input**.

### Bottom line

These are not two unrelated cosmetic CodeQL warnings.

They expose a common architectural gap:

**OCBrain has strong validation around some security-sensitive kernel boundaries, but its older API/export surface still treats certain caller-supplied strings as trusted filesystem/application data.**

The right remediation sequence is:

1. eliminate exception-detail responses in both normal and streaming API paths;
2. establish one canonical validated `module_name` filesystem boundary;
3. apply it to `brain_export.py` first;
4. sweep the learning/path consumers for the same taint pattern;
5. add regression tests specifically for traversal/absolute-path/module-identifier abuse;
6. rerun CodeQL and verify the findings disappear rather than being suppressed.

That would also give us a much cleaner basis for deciding whether these are **pre-freeze release blockers or post-freeze interface hardening**.

[1]: https://codeql.github.com/codeql-query-help/python/py-stack-trace-exposure/?utm_source=chatgpt.com "Information exposure through an exception — CodeQL query help documentation"
[2]: https://codeql.github.com/codeql-query-help/python/py-path-injection/?utm_source=chatgpt.com "Uncontrolled data used in path expression — CodeQL query help documentation"
`````

</details>

## 3. Subsequent User Instructions / Corrections

Chronological. Exact wording where it affects interpretation. "Continue" is a standing signal of full trust (stored preference: terse directives mean execute autonomously, no check-ins unless an architectural blocker needs a decision) -- **it has never been an authorization to merge**.

| # | Moncif said | Effect |
|---|---|---|
| 1 | "Continue" (several times, mid-investigation) | proceed autonomously |
| 2 | "Push to main" | I asked: push the branch + PR, or force onto `main`? |
| 3 | *(pasted a fresh GitHub token)* | token verified valid read-only before use |
| 4 | "open the PR" | authorized: push branch, open PR into `main`. Not a direct push to `main`. |
| 5 | "After reconciliation, merge to main" | authorized merge of PR #34 after CI passed |
| 6 | "Continue" (answering "go ahead on the zip-slip fix now?") | PR #35 -- **the zip-slip premise was wrong, see §12** |
| 7 | pasted several external reviews and, later, messages stating decisions or results (provenance: appear to be another AI assistant; some links carry `utm_source=chatgpt.com`) | treated as **unverified input**; errors found in each (§11) |
| 8 | "use the previous token until it's no longer available" | standing instruction for pushes/PRs with the 2nd token **until it returns 401, then stop and report**. Merges still need an explicit instruction. |
| 9 | "The three decisions are: `/distill` severity: P2 / Medium ... One register entry, not two ... Merge #36 first, then #37 ... #36 → wait for #157 PASS → merge #36 → update #37 with the single register entry → CI on #37 → merge #37." | decisions D-1..D-3 below; executed |
| 10 | "Finish the merge, then start fixing the remaining issues one after the other. Check the existing branches beforehand you start fixing anything" | merged #38, surveyed all branches/PRs, then fixed items 1-3 of §9 as separate PRs |
| 11 | "continue" / "CONTINUE" | proceed |
| 12 | "push the finished work to repo, then create a handoff to complete the work in a new session" | this handoff |

## 4. Goal, Scope & Success Criteria

### Goal
Verify the supplied CodeQL findings against live `main`, fix what is real with evidence, and keep the register and CodeQL state honest. Success was never "CodeQL shows zero alerts"; it is "every real exposure is fixed, tested (test fails without the fix), merged, and recorded, and every remaining alert has an explicit, evidenced disposition."

### In scope
CWE-209/497 response-text leaks; path traversal through `module_name`; register accuracy (`KNOWN_ISSUES.md`, `CURRENT_STATE.md`).

### Out of scope (do not change)
Other workstreams' branches: `feature/intent-sufficiency-slice1`, `feature/verification-critic-evidence-phase-c`, `sandbox-fabric`, `fix/ctx-auth-001b-*`, ADR-KERNEL-07 and similar. Dependabot dependency bumps (decision pending, §15). The `/import` trust model (no signature/checksum on bundles) -- CTX-EXPORT-001's larger open design question.

### Success criteria for finishing this workstream
1. PRs #40 and #42 merged (on Moncif's explicit instruction) after their CI is verified green.
2. One docs PR registers the three unregistered fixes and the path-injection classification (§17 step 4).
3. Moncif has made the disposition calls in §15 (alert dismissals, `_safe_extractall`, design question, Dependabot).

## 5. Requirement Ledger

| ID | Requirement | Source | Status | Evidence | Notes |
|---|---|---|---|---|---|
| R-1 | Verify CodeQL findings against live code, not the write-up | PROJECT_INSTRUCTIONS §0.2; instruction 1 | VERIFIED | §11 | write-up was an excerpt of 35 alerts |
| R-2 | Fix `export_module()` path traversal | write-up #2 | VERIFIED (merged #34) | test fails without fix | CTX-EXPORT-001 export half |
| R-3 | Remove exception text from API responses/SSE | write-up #1 | VERIFIED (merged #34, #36) | 0 `py/stack-trace-exposure` alerts open on `main` | |
| R-4 | Fix `/distill` + `/brain/v2/distill` traversal | found this session | VERIFIED (merged #37) | 4 traversal tests fail without fix | P2/Medium, DEBT-038 |
| R-5 | Fix `[Error in <module>: ...]` answer text | found this session | VERIFIED (merged #39) | 6 tests fail without fix | **changed 4 existing tests on purpose, §10 D-7** |
| R-6 | Fix updater `check_error` | found this session | VERIFIED (merged #40, `9b172d0`; was open at first commit) | 3 tests fail without fix | §0 |
| R-7 | Fix factory duplicate-module path in 400 | found this session | VERIFIED (merged #42, `4bb5974`; was pending at first commit) | 2 tests fail without fix | low severity; §0 |
| R-8 | One register entry for both distill routes, P2/Medium | instruction 9 | VERIFIED (merged #37/#38) | DEBT-038 | ID is **038**, Moncif wrote 039 (§10 D-4) |
| R-9 | Register entries for R-5/R-6/R-7 | register discipline | DONE by another session (#43, `cc01a61`) | -- | recorded under DEBT-037, no new ID; §0 |
| R-10 | Merge only on explicit instruction | session practice | HELD by this session | -- | #40/#42 were merged by Moncif himself; #44 is not ours |
| R-11 | Check existing branches before fixing | instruction 10 | VERIFIED | §11 | |
| R-12 | CodeQL alert dispositions | open | PARTIAL | §0 | 3 url + the `extractall` alert dismissed by `1h0lde4`; 29 path-injection open |
| R-13 | Design question: validate `module_name` in shared primitives | review 2/3 | OPEN | -- | not decided |

## 6. Current Verified State

All checked 2026-10-01 against GitHub and a fresh clone.

**VERIFIED**
- `main` was `ecddbff6968c55ed50661ef28caaef5bb1270bf4` at the first commit ("Merge pull request #41", a different workstream); **now `4ab5345`, see §0**.
- Merged to `main` from this workstream: #34, #35, #36, #37, #38, #39, and since the first commit #40 and #42 (plus docs PR #43 by another session). All their CI checks were green before merge.
- **PR #40** (`fix/updater-check-error-redaction-sep2026`): was open at the first commit with head `d14b4bce6623586bd115e588ca2c8ae139c3fc55` (my commit `10455e8` plus a merge of `main` authored by `N4Z`); **now merged** (`9b172d0`, final head `3fa6bef`).
- Code Scanning on `main`: **29 open, all `py/path-injection`**; 0 `py/stack-trace-exposure`; 4 dismissed by `1h0lde4` (§0). (At the first commit it was 32 open: those 29 plus the 3 url-substring alerts. The latest analysis reports 33 results against 29 open; the difference is dismissed alerts plus at least one unexplained.)
- All path-injection alerts flow from 5 HTTP sources in `interface/api.py` (SARIF analysis 1862152239 on `2e5cfc0`):

  | Source (api.py line) | Route | Reaches | Guard | Status |
  |---|---|---|---|---|
  | 441 | `POST /modules/new` | `module_factory.py`, `module_registry.py` | `factory_create` `.isidentifier()`; also gated off by default (`global.module_factory_enabled`, RCE-001) | guarded |
  | 453 | `POST /train/{module_name}` | `trainer`, `evaluator`, `finetuner`, `scheduler` | `if module_name not in _orchestrator.modules` -> 404; registry keys are directory basenames (`modules[path.name]`, `module_registry.py:48`; sole other insertion is `reload_module`, whose only caller `api.py:445` passes a name `factory_create` validated) | guarded (a single-basename guarantee, **not** `.isidentifier()`) |
  | 463 | `POST /distill` | `distiller.py` | `.isidentifier()` since #37 | fixed |
  | 474 | `POST /export` | `brain_export.py` (11) | `.isidentifier()` in `export_module()` since #34 | fixed |
  | 481 | `POST /import` | `brain_export.py` (2) | none by design -- `bundle_path` is a server-side file path the caller names | **by-design**, risk is CTX-EXPORT-001's no-signature question |

  `core/brain_api.py` has the same `/distill`, `/export`, `/import` handlers; CodeQL lists no sources there (blind spot) -- verified by hand, no other module-name-bearing route exists in that file.
- The 3 `py/incomplete-url-substring-sanitization` alerts are test membership asserts (`tests/test_parser.py:18`, `tests/test_module_factory.py:120`, `tests/test_context.py:64`): false positives, as `security/codeql-findings-sep2026`'s notes also conclude.
- `zipfile` already drops `..`, `.`, empty and drive/absolute components (CPython 3.11, 3.12, 3.13 sources; empirical on 3.12.3).
- `merger.merge()` appends error-source answers to the string `handle()` returns.
- Dependabot: 3 open alerts, **all `chromadb`** -- critical GHSA-36p7-vc44-83pf (CVE-2026-45833, code injection, `>= 0.4.17, <= 1.5.9`), high GHSA-xph7-9rjv-w5fr (CVE-2026-45831, RBAC provider tenant/db checks, `>= 0.5.0, <= 1.5.9`), high GHSA-2wm9-hf6c-p5cr (CVE-2026-45830, authenticated users read/write/delete, `>= 0.4.17, <= 1.5.9`). **No patched version is listed for any.** `requirements.txt` pins `chromadb==0.5.3` (deliberate, DEBT-032), which is inside every range.

**IMPLEMENTED BUT NOT VERIFIED**
- None from this session. (#42 was pending at the first commit; it merged with all checks green, final head `57dde35`.) **PR #44** is another session's unmerged work with a failing `CodeQL` check -- see §0.

**PROPOSED / DEFERRED**
- Remaining alert dispositions (the 29 path-injection alerts, R-12), the design question (R-13), the Dependabot decision, `_safe_extractall` keep/revert (D-8). The register work (R-9) is done (§0).

**UNKNOWN**
- Who owns PR #44, and why its `CodeQL` check fails (not investigated).
- Whether the chromadb advisories apply to OCBrain's usage (embedded library vs. authenticated server); advisory bodies were not read beyond the summaries above.
- Whether `PlannerWorker`'s `WorkerResult.error = f"PlannerWorker pipeline error: {e}"` (core/workers/planner.py) ever reaches a caller.
- `learning/crawler.py`, `cleaner.py`, `gap_detector.py` build paths from `module_name` (found by grep) but have **no CodeQL alerts** and CodeQL found no HTTP flow into them; call paths not traced.
- A webhook-registration model with `webhook_url: str` was noticed in `core/brain_api.py` during a grep; whether anything uses it was **not** checked.

## 7. Git / Repository Checkpoint

- Primary repository: `1h0lde4/ocbrain-v4.1` (**public**); default branch `main`; PR-based merges with merge commits; branch protection requires `tests` and `drift-and-ownership`; admins are exempt (`enforce_admins` false -- Moncif's choice, DEBT-033).
- Remote: `origin` = `https://github.com/1h0lde4/ocbrain-v4.1.git`
- Base branch / HEAD at the first commit: `main` @ `ecddbff6968c55ed50661ef28caaef5bb1270bf4`; **by 2026-10-02: `4ab5345`** (§0)
- Transfer commits at the first commit (open PR heads; **both PRs have since merged**, §0):
  - `fix/updater-check-error-redaction-sep2026` @ `d14b4bce6623586bd115e588ca2c8ae139c3fc55` (PR #40; merged as `9b172d0`)
  - `fix/module-factory-path-in-error-sep2026` @ `57dde35887bed57c05044f487b7a0d026ca75416` (PR #42; merged as `4bb5974`)
- Handoff branch: `handoff/codeql-remediation-sep2026`, parent commit `ecddbff` (the handoff commit's own SHA cannot be written inside itself; read it with `git rev-parse origin/handoff/codeql-remediation-sep2026`).
- Merge commits of this workstream on `main`: #34 `bd290ff`, #35 `2520cb4`, #36 `a949b8d`, #37 `b195ae9`, #38 `2e5cfc0`, #39 `1a1621a`.
- Working tree status: clean in my sandbox after reverting test-run pollution (see §14). The sandbox is ephemeral and **not** a source of truth.
- Merged-but-undeleted remote branches from this workstream: `fix/ctx-export-001-and-error-disclosure-sep2026`, `fix/ctx-export-001-zip-slip-sep2026`, `fix/codeql-remaining-stack-trace-flows-sep2026`, `fix/distill-module-name-validation-sep2026`, `docs/debt-038-status-sep2026`, `fix/answer-text-error-redaction-sep2026`. Not deleted (no authorization).
- Remote push status: all of the above pushed. Remote verification: each pushed SHA was confirmed with an unauthenticated `git ls-remote`.
- Relevant ignored/untracked files: none to preserve.

## 8. Active Files / Modified Files / Artifacts

Line endings are **mixed** -- check bytes before editing. The `str_replace` editing tool preserves a file's endings; raw Python `open()` without `newline=""` does not. Verified from `origin/main` blobs: **CRLF** -- `core/brain_export.py`, `core/brain_api.py`, `core/module_factory.py`, `core/orchestrator.py`, `core/dispatcher.py`, `core/model_router.py`. **LF** -- `core/workers/planner.py`, `interface/api.py`, `interface/updater.py`, `learning/distiller.py`, `KNOWN_ISSUES.md`, `CURRENT_STATE.md`, `core/error_ref.py`, the test files listed here.

| File | Why it matters |
|---|---|
| `core/brain_export.py` | `export_module()` `.isidentifier()` guard (#34); `_safe_extractall()` (#35) |
| `interface/api.py` | `_log_and_redact()`; `/query`, streaming, `/debug`, `/distill` guards |
| `core/brain_api.py` | file-local redaction in `_stream_query`; `/brain/v2/distill` guard |
| `core/model_router.py` | `_ollama_stream` no longer yields `[Error: {e}]` |
| `learning/distiller.py` | `_require_module_identifier()` in `distill_topic` and `_save_pairs` |
| `core/error_ref.py` | `log_and_ref(logger, context, exc) -> ref` (#39). `interface/api.py`, `core/brain_api.py`, `interface/updater.py` keep their own equivalents on purpose |
| `core/orchestrator.py`, `core/workers/planner.py`, `core/dispatcher.py` | answer-text redaction (#39); dispatcher is **dormant** (nothing imports it) |
| `interface/updater.py` | `check_error` redaction (#40, open) |
| `core/module_factory.py` | duplicate-module message without path (#42, open) |
| `KNOWN_ISSUES.md` | CTX-EXPORT-001 addendum inside DEBT-019's row; DEBT-037; DEBT-038 |
| `tests/test_brain_export_security.py`, `test_api_error_disclosure.py`, `test_distill_module_name.py`, `test_answer_error_disclosure.py`, `test_updater_error_disclosure.py` (#40), `test_module_factory_error_disclosure.py` (#42) | regression tests. Four older tests were changed deliberately (§10 D-7) |

External: GitHub PR pages #40, #42; Code Scanning alert list and SARIF (`GET /repos/1h0lde4/ocbrain-v4.1/code-scanning/analyses/<id>` with `Accept: application/sarif+json`).

## 9. Changes Made

1. **#34** `export_module()` rejects non-identifiers before building any path (the export half of CTX-EXPORT-001). Four CWE-209 handlers redacted: `/query`, both `_stream_response` branches, `core/brain_api.py::_stream_query` -> `{"error": "internal_error", "error_id": <uuid>}`, detail logged server-side.
2. **#35** `_safe_extractall()` in `import_module()`. **Defense-in-depth only** -- the zip-slip premise was wrong (§12).
3. **#36** `model_router._ollama_stream` and `/debug` stopped returning exception text (found by reading CodeQL's own SARIF code flows); `/debug` now shows the exception *class name* plus an `error_id` (behavior change); stale status lines corrected; zip-slip docstrings corrected.
4. **#37** `.isidentifier()` guard on `POST /distill` and `POST /brain/v2/distill`, at the sink (`distill_topic` + `_save_pairs`) **and** both handlers (400, fixed message); DEBT-038 added.
5. **#38** DEBT-038 status line fixed after it went stale.
6. **#39** `[Error in <module>: <ExceptionClass> (ref <uuid>)]` in orchestrator/planner/dispatcher; new `core/error_ref.py`.
7. **#40** (open) updater `check_error` -> `"<prefix>: <ExceptionClass> (ref <uuid>)"`.
8. **#42** (open) `Module '<name>' already exists.` (no install path in the `/modules/new` 400).

Schema/contract changes: error payloads gained `error_id`; `/debug` fields `error` (class name) and `error_id`. No governance, event-schema, or persistence changes.

## 10. Decisions & Rationale

| ID | Decision | Status | Authority | Reopen condition |
|---|---|---|---|---|
| D-1 | `/distill` severity **P2 / Medium**, worded "path traversal causing out-of-root directory creation and constrained JSON artifact creation" -- **not** arbitrary file write | DECIDED (message pasted by Moncif 2026-09-29 and treated as his decision; it read like the external reviews, so confirm if it matters) | instruction 9 | new evidence of overwrite/arbitrary content/exec |
| D-2 | **One** register entry for both distill routes (same field, sink, fix) | DECIDED | instruction 9 | -- |
| D-3 | Merge order #36 then #37, each after CI | DECIDED, executed | instruction 9 | -- |
| D-4 | Register ID is **DEBT-038**, not the `DEBT-039` Moncif wrote: 037 was the highest on `main` and 038/039 appeared nowhere in the repo or open PRs. Flagged in #37's body. | MY CALL, **not confirmed by Moncif** | -- | if 039 was intentional, renumber (one-line edit) |
| D-5 | Keep `.isidentifier()` as the module-name convention (same as `module_factory.create()`, `brain_export.py`) rather than invent a containment helper | ACCEPTED | consistency | -- |
| D-6 | Keep **both** route guards and sink guards for distill; the sink guard is the invariant for other callers | ACCEPTED | review + mine | -- |
| D-7 | Redact answer text to `module + ExceptionClass + ref`; **four existing tests changed** because they asserted the raw message was *in the answer* (`test_planner_worker::test_module_dispatch_exception_contained`, `test_planner_capability_migration::test_capability_failure_folded_into_merged_error_like_legacy` and `::test_no_adapter_runtime_and_no_model_router_is_contained_not_raised`, `test_k2_2_runtime_migration::test_workflow_failure_returns_error_not_crash`). They still assert the failure is contained and folded into the answer, and now assert the message is in the log under the ref and **not** in the answer. Consequence: config errors such as "No adapter_runtime or model_router configured" are no longer visible in the reply. | MY CALL, merged in #39 by Moncif; called out in the PR body | -- | if Moncif wants controlled messages visible: introduce a dedicated "safe to show" exception class (larger change, not done) |
| D-8 | Keep `_safe_extractall` although the stated reason was wrong (harmless, stricter than stdlib: rejects instead of silently rewriting names) | **OPEN -- Moncif's call** | -- | -- |
| D-9 | Updater uses a file-local `_log_and_ref` instead of importing `core/error_ref.py`, so #40 stands alone on `main` | ACCEPTED | independence of sibling PRs | unify once both are merged, if wanted |
| D-10 | Register edits are deferred until fix PRs land, to avoid same-line conflicts in `KNOWN_ISSUES.md` | ACCEPTED | learned from the DEBT-029 collision | -- |

## 11. Investigation Already Performed

| Area | Inspected | Result | Revisit trigger |
|---|---|---|---|
| Supplied CodeQL write-up | live `main` files it cites | both findings real; it was an excerpt of 35 alerts and missed several flows | -- |
| `export_module()` vs `import_module()` | `core/brain_export.py` | only import had the `.isidentifier()` guard (CTX-EXPORT-001's earlier fix covered import only) | -- |
| `interface/api.py` streaming + `/query` | all `except` blocks | 2 more leak sites beyond the 2 CodeQL named | -- |
| CodeQL alert list, then SARIF code flows | analyses on `b1e4184`, `2e5cfc0`, `ecddbff` | alert line numbers mislead; reading the **flows** exposed the `model_router` in-band error token and `/debug`; 5 HTTP sources feed all path-injection alerts (§6 table) | code moves -> re-download SARIF |
| zip extraction | CPython source (3.11/3.12/3.13) + experiment | no exploitable write; claim retracted | -- |
| Second distill route | `core/brain_api.py` | `POST /brain/v2/distill` exists, reproduced on unfixed source (HTTP 200, directory created outside `data/raw`). The review that mentioned it cited an unrelated repository (a `py3dtiles` changelog); verified in code | -- |
| Module registry | `module_registry.load_all`, `reload_module` + callers | keys are directory basenames; one other insertion path, one caller | registry gets a new insertion path |
| Exception text in strings, repo-wide grep | `core/`, `interface/` | answer-text sites (fixed), updater (fixed), factory path (fixed); internal-only channels (event payloads, `WorkerResult.error`, tracing spans) not changed | -- |
| Existing branches/PRs | all remote branches vs `main`; open PRs | only `feature/intent-sufficiency-slice1` touches `core/orchestrator.py` (different hunks, now merged with `main`); `security/codeql-findings-sep2026` holds a working-notes doc covering only the 3 url-substring alerts | new branches appear |
| Reviews pasted by Moncif | three | errors found: bogus citation; "invalid topic" (the field is `module_name`; `topic` is free text); "`.isidentifier()` explains the remaining alerts" (wrong: `/train` is guarded by a membership allowlist, `/distill` had no guard); "no checks on #36" (stale) | -- |
| Dependabot | alerts API | 3 chromadb alerts, no patched version | decision pending |

**Not yet investigated:** chromadb advisory bodies and OCBrain's usage mode; `PlannerWorker` `WorkerResult.error` reach; crawler/cleaner/gap_detector call paths; the webhook model in `core/brain_api.py`; `/modules/new` returning an uncaught 500 when the factory is disabled (`RuntimeError` is not caught by `except ValueError`).

## 12. Failed Attempts / Dead Ends

| Attempt | Result | Cause | Retry? |
|---|---|---|---|
| Claimed `zf.extractall()` was an exploitable arbitrary write ("more severe") and shipped #35 | **wrong** | pattern-matched on `extractall()`; never ran the ten-line experiment; stdlib sanitizes `..` | no. Rule: run the exploit before describing it as one |
| Assumed `learning/*` sinks were registry-sourced and unreachable | wrong for `/distill`, right for `/train` | skipped asking CodeQL where flows *start* | no |
| Assumed CI-green or "CodeQL check: success" meant no open alerts | wrong | the check doesn't fail on existing alerts | no -- query the alerts API |
| Used `git stash` to build an "unfixed source" run after committing the fix | tested the fixed code | nothing left to stash | use `git checkout origin/main -- <files>` then restore **after committing** |
| `git checkout HEAD -- <file>` to restore files | silently erased an uncommitted edit | clobbered work | **commit before any fail-before experiment** |
| Inserted `DEBT-029` for my finding | ID collision with PR #26 | concurrent work took 029-036 | re-read `main` and open PRs for IDs immediately before writing |
| Wrote register status "not yet on main until it merges" | went stale on merge (twice) | status tied to a future event | write status neutrally or after the merge |
| Assertion `row.count("|") == 5` | aborted (a 5-column row has **6** pipes) | off-by-one | no |
| Unauthenticated GitHub API from the sandbox | rate-limited (403) | shared egress IP | use the token read-only, or `git ls-remote` |
| `web_fetch` on PR checks/Actions pages | refused | tool only fetches URLs already seen | use the API |
| `$'\r'` in the sandbox shell | everything reported "LF" | `sh` doesn't support it | count `b"\r\n"` in Python |

## 13. Verification Evidence

- Test command: `python3 -m pytest -q --no-header -p no:cacheprovider tests/ --ignore=tests/test_break_concurrency.py --ignore=tests/test_break_empty_db.py --ignore=tests/test_break_security.py --ignore=tests/test_system_ctrl.py`
- **Baseline: 8 failed**, all `ModuleNotFoundError: No module named 'chromadb'` (environmental): `test_audit_fixes.py::TestA7SystemController` x6, `test_module_factory_security.py` x2 (`test_desc_field_cannot_break_out_of_generated_source`, `test_name_field_also_uses_safe_literal_substitution`). The four ignored files fail at *collection* for the same reason.
- Latest run (on `main` @ `ecddbff` + #42's change): **8 failed / 1628 passed / 1 xfailed** -- the xfail comes from other sessions' merged work, not from these changes.
- Fail-before checks (new/updated tests run against the unfixed source files): #36 -- 2 of 2 new tests fail; #37 -- 4 of 5 fail (the legitimate-name test passes either way by design; the `/brain/v2` test also fails against sink-guard-only source, `500 != 400`); #39 -- 6 fail (orchestrator, dispatcher, four updated tests; the helper test passes either way); #40 -- 3 of 3; #42 -- 2 of 2. **#34's first batch of tests was not run against unfixed source.**
- Experiments on unfixed source: `/distill` and `/brain/v2/distill` with `module_name="../../x"` created a directory outside `data/raw` (even with Ollama unreachable, because `mkdir` runs before the pair loop); `zipfile.extractall()` on `..`, nested `..`, and absolute members left nothing outside the destination.
- CI: #34-#39 all five checks green before merge (CI run #156/#157 were #36's). #40 and #42 both merged with all checks green (a new `Graphify` check appeared on later PRs).
- Remote checks: every pushed branch SHA matched via unauthenticated `git ls-remote`.
- Limitation: CodeQL cannot be run in the sandbox, so whether it accepts a `resolve()` + `is_relative_to()` containment check as a barrier (it does **not** treat `.isidentifier()` as one) is untested.

## 14. Environment / Tooling Assumptions

- Sandbox: Ubuntu, Python 3.12.3 (project requires `>=3.11`), light dependencies only -- **no `chromadb`, `sentence-transformers`, `scipy`** (disk space; baseline failures follow from this). `pip install --break-system-packages --no-cache-dir`.
- Scripts run outside the repo need `PYTHONPATH=<repo root>`.
- Running the suite **modifies** `config/models.toml`, `config/settings.toml`, `config/sources.toml`, `data/context.sqlite` (pre-existing test-isolation gap). Revert before committing: `git checkout -- config/models.toml config/settings.toml config/sources.toml data/context.sqlite`.
- Commits need identity flags (no global git config): `git -c user.email=... -c user.name=... commit`.
- Network: `github.com`, `api.github.com`, `raw.githubusercontent.com` reachable from bash; shallow clones need an explicit `git fetch --depth 1 origin <branch>` then `FETCH_HEAD`.
- Never store secrets: the two classic PATs pasted into the chat are exposed. The first was dead (401). The second was valid for `1h0lde4` (scopes `repo`, `workflow`; admin on the repo). Moncif was advised to revoke both and chose to keep using the second "until it's no longer available". **Neither is recorded here. A new session has no token** and needs Moncif to supply one.

## 15. Unresolved Questions / Risks / Blockers

| Issue | Evidence | Options | Safe to continue? |
|---|---|---|---|
| PR #44 (import-root containment) is open with a failing `CodeQL` check, and is not this workstream's | §0 | find its owner; let that session finish it | yes, but do not touch #44 |
| Merging anything | needs an explicit instruction each time | -- | do not merge without one |
| Alert dispositions: the 3 url-substring alerts and the `extractall` alert are dismissed (§0); 29 path-injection alerts remain open (5 sources: 4 guarded/fixed, 1 by-design, now targeted by #44) | §0, §6 | dismiss with a documented reason vs. keep open | **Moncif's call**; dismissal changes his security dashboard |
| `/import` takes a caller-named server-side path | alert source 481 | restrict to an allowed directory (behavior change) vs. leave under CTX-EXPORT-001 | no change without a decision |
| Keep or revert `_safe_extractall` (D-8) | §10 | keep / revert | yes |
| Design question: validate `module_name` in every shared filesystem primitive? | review 2/3 lean "eventually yes" | if yes, prefer a containment check (`resolve()` + `is_relative_to()`) over `.isidentifier()` for **internal** sinks -- registry directories need not be identifiers, so an identifier check could break them; CodeQL acceptance untested | undecided |
| Dependabot chromadb x3, no patched version; pin `==0.5.3` is deliberate (DEBT-032); Dependabot PRs exist | §6 | assess exposure first; do **not** bump blindly | yes; do not act without Moncif |
| Concurrent sessions edit `main` | `ecddbff` came from another workstream | always fetch + merge `main` before pushing | yes |
| DEBT ID collisions | precedent DEBT-029 | check `main` **and** open PRs just before writing | yes |

## 16. Relevant Information / References

- `docs/architecture/PROJECT_INSTRUCTIONS.md` per the root stub -- verify it exists (governing contract; §0 evidence discipline, §16.5 closure criteria, §18.4.8 this handoff format, §24 audit discipline).
- `KNOWN_ISSUES.md`: DEBT-019 (CTX-EXPORT-001 addendum), DEBT-025 (no API authentication), DEBT-032 (chromadb pin), DEBT-033 (branch protection), DEBT-037 (exception text in responses), DEBT-038 (`/distill` traversal). DEBT-037's "same class, not fixed" sentences about `orchestrator`/`planner` and `updater` are **stale once #40 merges** (and #39 already fixed the former).
- `security/codeql-findings-sep2026` branch: `docs/Bugs Hunt & fix reports/CODEQL_FINDINGS_SEP2026_WORKING_NOTES.md` -- only the url-substring category, dispositioned as false positives; its first version was lost.
- Alert API: `GET /repos/1h0lde4/ocbrain-v4.1/code-scanning/alerts?ref=refs/heads/main&state=open`; SARIF via `.../code-scanning/analyses/<id>` with `Accept: application/sarif+json`.
- Register edit conventions: one table row per line with exactly 6 `|` characters (`DEBT-018` and `DEBT-034` already deviate, untouched); `DEBT-029` appears after `DEBT-036` -- the table is not strictly ordered; insert new rows after the highest-numbered row; keep the master "Last synchronized" chains at the top of both docs untouched.
- Tests invoke handlers directly (convention in `tests/test_api_context_scope.py`) rather than building a TestClient app, except `tests/test_distill_module_name.py`'s `/brain/v2` case.

## 17. Next Steps

1. **Verify state** (§18). *Expected:* matches §6/§7.
2. **Get a token from Moncif** and check it read-only (`GET /user` -> login `1h0lde4`). Do not assume this session's authorization carries over; merges need an explicit instruction every time.
3. **[SUPERSEDED -- #40 and #42 are merged, §0]** Establish who owns PR #44 and whether its failing `CodeQL` check is understood. **Do not merge anything** without Moncif's explicit instruction.
4. **[DONE by another session as #43 -- §0; only re-check that it matches the intent below]** After #40 and #42 merge, one docs PR from a fresh branch off `main`:
   - Add register entries for #39, #40, #42. Whether that is one entry (the "exception text in caller-visible responses" class) or three is **Moncif's call**; ask once. Use the next free ID after re-reading `main` and open PRs.
   - Fix DEBT-037's now-stale "not fixed" sentences.
   - Record the §6 path-injection classification table and that crawler/cleaner/gap_detector are untraced.
   - Write status neutrally (no "not yet merged"). Check every row has 6 pipes. Run `git diff` for exactly the intended lines.
5. **Put the §15 decisions to Moncif** in one message (alert dismissals, `/import` path, `_safe_extractall`, design question, Dependabot), with the evidence above. Do not dismiss alerts or bump dependencies unasked.
6. **Optional, with authorization:** delete the merged branches listed in §7.
7. **Optional investigations** (each a separate, evidenced PR if real): `PlannerWorker` `WorkerResult.error` reach; crawler/cleaner/gap_detector call paths; the webhook model in `core/brain_api.py`; the uncaught `RuntimeError` -> 500 in `/modules/new`; chromadb advisory applicability.

## 18. Resume Instructions

1. `git fetch origin` and confirm `origin/main` and the two PR heads (§7). If `main` moved, read `git log` and what landed before acting.
2. Confirm `#40` and `#42` states via the API; confirm this file's branch exists remotely.
3. Reproduce nothing already verified. Spot-check one claim cheaply if unsure: re-download the latest Python SARIF and confirm 5 distinct sources for `py/path-injection`.
4. **Commit before experimenting.** Run fail-before checks by checking `origin/main` versions of the *source* files out and restoring from `HEAD` afterwards.
5. Begin at §17 step 2. Do not re-derive the investigation ledger (§11) unless the repository contradicts it; if it does, correct this handoff first.

## 19. Transfer Status

**TRANSFER READY**, with two stated limits:
- No token is recorded (by design); a new session needs one from Moncif before it can push anything.
- State moved after the first commit; §0 records what changed (#40/#42/#43 merged, #44 open and owned by another session). Verify live before acting.

All material work from this workstream is on `origin` and merged to `main` (#34-#40 and #42; docs #43 came from another session). This file is on `handoff/codeql-remediation-sep2026`, not merged.
