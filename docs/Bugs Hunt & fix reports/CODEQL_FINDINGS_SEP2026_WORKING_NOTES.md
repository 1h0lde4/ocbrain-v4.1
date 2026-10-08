# CodeQL Findings — Sept 2026: Working Notes

Register checked first: none of the three categories below were previously tracked in `KNOWN_ISSUES.md`. Genuinely new, surfaced by CodeQL's scan (confirmed running as part of Packet G's PR #26 checks).

**Note on this file's history:** the first version of this investigation (Category 1 below) was completed, committed locally, but not yet pushed when the underlying compute environment was reset, losing all uncommitted/unpushed local state. Nothing merged or pushed was affected — `main`'s Packet G merge (`b1e4184`) survived intact. Category 1's analysis is reconstructed here after re-verifying its key facts fresh against the re-cloned repository, not reproduced from memory alone. Lesson applied going forward: push each finding immediately rather than batching commits locally.

---

## Category 1: "Incomplete URL substring sanitization" — confirmed false positive, all 3 locations

**Flagged:** `tests/test_parser.py:18`, `tests/test_module_factory.py:120`, `tests/test_context.py:64`.

**The actual vulnerability this CodeQL query detects:** code that checks whether a trusted substring appears *anywhere within* a single URL string (e.g. `if "trusted-domain.com" in redirect_url:`) — bypassable by an attacker via a crafted URL like `evil.com/trusted-domain.com` or `trusted-domain.com.evil.com`, since substring containment says nothing about the URL's actual host.

**What's actually at each location, verified by checking the real return type, not assumed from the code's shape:**

| Location | Expression | Right-hand side type | Confirmed via |
|---|---|---|---|
| `test_parser.py:18` | `"https://example.com" in result.entities["urls"]` | `list[str]` | `core/parser.py:41`: `urls = _URL_RE.findall(text)` — `re.findall()` always returns a list |
| `test_module_factory.py:120` | `"https://example.com" in sources` | `list[str]` | `core/config.py:169`: `def get_sources(...) -> list[str]`, returns `list(dict.fromkeys(...))` |
| `test_context.py:64` | `"https://example.com" in urls` | `list[str]` | `core/context.py:178`: `def get_entity(...) -> list[str]`, returns `[r[0] for r in cur.fetchall()]` |

All three are `value in list_of_strings` — Python's `in` on a list is exact-equality membership against each element, not substring search within one string. There is no bypass here analogous to the real vulnerability class: an attacker cannot make `"https://example.com" in ["https://evil.com/https://example.com"]` evaluate `True`, because list membership doesn't do substring matching at all. This is CodeQL's heuristic pattern-matcher — which looks for the textual shape `"url-like-literal" in <expr>` — unable to distinguish string-substring containment from list-membership containment, both spelled with the same `in` keyword in Python.

**Classification: false positive, confirmed by checking the actual data flow, not asserted from confidence in the pattern alone.** All three are also test code exercising extraction/storage correctness, not a security decision gating any real request — even if the semantics *were* substring containment, there'd be no exploitable consequence here.

**Disposition:** no code change. Recommend dismissing these three specific CodeQL alerts with reason "false positive" (or GitHub's "used in tests" category, which also applies) so they stop appearing in future scans as unresolved findings requiring attention.

---

## Category 2: "Uncontrolled data used in path expression" — the 3 given examples, each traced to a full reachability conclusion

**Flagged:** `learning/trainer.py:61`, `learning/scheduler.py:162`, `core/module_factory.py:49`. Moncif's own framing noted more instances exist, "to be found later" — that broader search follows this sub-section.

**`core/module_factory.py:49`** (`shutil.copytree(TEMPLATE_DIR, dest)`, `dest = MODULES_DIR / name`): traced the full `create()` function from its start — single, linear control flow, no branch or early return that reaches this line without first passing `if not name.isidentifier(): raise ValueError(...)`. `str.isidentifier()` admits only letters, digits, and underscores; no `/`, `\`, or `.` can survive it. **Safe: the validation is airtight for this specific call.**

**`learning/scheduler.py:162`** (`shutil.rmtree(pending, ...)`, `pending` built from `module_name` inside `finetuner.train()`): a deletion operation, so traced with extra care. `trigger_module(self, module_name: str)` takes the parameter directly with no internal validation — but it has exactly one production caller, `interface/api.py:443`'s `POST /train/{module_name}`, which guards with `if module_name not in _orchestrator.modules: raise HTTPException(404, ...)` *before* calling it. Traced `_orchestrator.modules`'s own population back to `core/module_registry.py:24`: `for path in sorted(MODULES_DIR.iterdir())` — real filesystem directory entries only. `iterdir()` cannot return a value containing `/` (a single path segment can't), and POSIX directory listings never include `.`/`..`. **Safe: the one reachable external path is constrained to real, existing, single-segment directory names before this line executes, ruling out traversal by construction, not merely by convention.**

**`learning/trainer.py:61`** (`directory.glob(f"*{ext}")`, `directory = DATA_RAW / module_name` or `DATA_CHUNKS / module_name`): `trainer.prepare()` has exactly two callers, both inside `scheduler.py` — `_training_cycle`'s `for name, module in self.registry.items()` (an internal dict iteration, not external input) and `trigger_module`'s `module_name`, already traced safe immediately above. **Safe, by the same reachability chain already established.**

**All three given examples: false positive / already-mitigated, not a live vulnerability.** CodeQL's static data-flow analysis correctly identifies that a parameter named `module_name`/`name` reaches a path expression without a *local* sanitizer in the immediate function — but doesn't (or can't, at this query's precision) account for validation enforced by the caller before the parameter is ever passed in. This is a real, common limitation of intraprocedural-looking taint analysis, not a sign the alerts were arbitrary.

**No code change for these three.** Recording the full reachability trace here is the point — a future reader (or a future refactor that adds a *second*, less-careful caller to `trigger_module()` or `trainer.prepare()`) has a concrete record of exactly which property is being relied on, so it can be preserved deliberately rather than accidentally broken.

---

## Postscript — `main` overtook this branch; what is verified vs. inferred

This branch was cut from `main` @ `b1e4184` (Packet G's merge). By the time it was checkpointed, `origin/main` was **15 commits ahead** (`2e5cfc0`), including concurrent fixes for this same CodeQL scan: `9d720c1` (export-side CTX-EXPORT-001 path injection + exception-detail redaction, CWE-209/497), `b23ee9a` (zip-slip in `import_module`), `9631e4e` (two more stack-trace flows), `a2c4430` (`module_name` validation on both `/distill` routes, DEBT-038).

**Verified (by running it, not by reading commit messages):**
- During this investigation `export_module()` was found exploitable on the then-current code: two regression tests added to `tests/test_brain_export_security.py` on this branch **fail** against this branch's pre-fix `core/brain_export.py` (a decoy outside `modules/` was exfiltrated into a bundle, and the bundle was written outside `data/exports/`) and **pass 3/3 against `origin/main`'s code** (run in a throwaway worktree). So the export-side hole is real *and* already closed on `main`; these tests are valid regression tests, likely redundant with PR #34's own.
- CodeQL's code-scanning API lists **32 open alerts, all analyzed at `refs/heads/main` @ `2e5cfc0`** — i.e. the *current, post-fix* code, not stale results.
- Category 3: all three alerts named in the task (`core/brain_api.py:113`; `interface/api.py` at 178 and 544 after line shifts) are in CodeQL state **`fixed`**.

**Inferred, not proven:** the 12 `brain_export.py` alerts remain open even though the guard demonstrably blocks the exploit, so CodeQL's `py/path-injection` query evidently does not treat `str.isidentifier()` (or dict-membership checks like `in _orchestrator.modules`) as a sanitizer. Consequence: **an open `py/path-injection` alert here does not by itself mean an unfixed vulnerability** — each needs classification (guarded & reachable-only-via-guard / genuinely unguarded). The three originally-named examples (`module_factory.py:49`, `scheduler.py:162`, `trainer.py:61`) are classified above as guarded.

---

## Final disposition (supersedes the postscript's open items)

*Snapshot as of 2026-10-08 20:39 UTC (CodeQL REST API + git). Re-fetch before relying on any number below — this alert set changed three times within one session.*

**CodeQL: 37 alerts — 33 `fixed`, 4 `dismissed`, 0 open.** Your three categories are closed:

- **Category 1 — dismissed by Moncif** (`1h0lde4`): #30, #31, #32 as "used in tests" (2026-10-02 ~00:44Z). My analysis above agrees these are false positives (list membership, not substring search).
- **Category 2 — closed upstream.** All 30 `py/path-injection` alerts are `fixed` (last fix 2026-10-05T07:31Z). The structural fix is `acc43b7` — *route every module-name filesystem path through `core/module_paths.module_child()`* — a single choke-point (canonicalizes, requires a direct child, symlink-aware, error text does not echo the input) used across `brain_export`, `module_factory`, `module_registry`, and `learning/{cleaner,crawler,distiller,evaluator,finetuner,gap_detector,trainer}`; plus `6dee2b2`, which confines `/import`'s `bundle_path` to a configured import root. `module_paths.py`'s own docstring states what I had only inferred: `.isidentifier()` is not a filesystem boundary and CodeQL does not treat it as one — which is why the alerts persisted on correctly-guarded code until a recognised helper replaced the per-site checks.
- **Category 3 — closed upstream.** The three `py/stack-trace-exposure` alerts (your `core/brain_api.py:113`, `interface/api.py:529` and `:160`) are `fixed`.
- Dismissed #36 (`brain_export.py:161`, "false positive") was also Moncif's call.

**What I independently verified (by execution)**, not just by reading CodeQL's state: `tests/test_module_name_containment.py` — 76/76 pass; this branch's three end-to-end export tests pass against `main`'s code; full suite on the merged tree `1970 passed, 1 xfailed` (exit 0); `scripts/check_drift.py` 15/15.
**What I did NOT verify:** the code of the fixes line by line; that `results_count=3` on CodeQL's latest 43-rule analysis of `main` is the three dismissed alerts (an inference — dismissed results still appear in analyses).

### New finding CodeQL did not surface: `PrivacyGuard.wipe_module_data` — a latent unguarded deletion sink

My independent sweep for raw module-name path joins (the "every path" claim in `acc43b7` is the same shape as the `export_module()` coverage gap) found exactly one site that bypasses `module_child()`:

```python
# core/privacy.py (unchanged on main since 2026-06-30; no module_child)
def wipe_module_data(self, module_name: str):
    import shutil
    for folder in ["data/raw", "data/chunks"]:
        p = Path(__file__).parent.parent / folder / module_name
        if p.exists():
            shutil.rmtree(p)
```

No containment, no validation, and the operation is `shutil.rmtree` — the same class as the original CTX-EXPORT-001 (traversal-to-arbitrary-deletion). `module_name = "../../.."` resolves above the repo root.

- **Reachability: none today.** `git grep wipe_module_data|wipe_all` on `main` finds the two definitions and nothing else in production; `tests/test_privacy.py` only *stubs* `wipe_module_data` with a lambda, so the real function is not exercised by any test.
- **Classification: UNPROVEN as live; a latent sink** — the same shape as Packet D's `resume()` (real in form, currently no caller). It becomes live the moment anything wires it to an endpoint. CodeQL's silence is consistent with that (no reachable taint source) — an inference, not a verified reason.
- **Not yet proven by a test and not fixed.** The right next step is a decoy exploit test that fails first, then a fix through `module_child()` (see `handoff.md`).

### Corrections to my own earlier work

- **Packet E's dependency matrix undercounted unguarded `trafilatura` imports.** I searched `core/ interface/ modules/ tests/` and not `learning/`, so I recorded only `modules/web_search/module.py`. `learning/crawler.py:12` also has a bare top-level `import trafilatura`. It became reachable when `tests/test_module_name_containment.py` landed (its `sandbox` fixture imports `learning.crawler`): without `trafilatura`, **all 51** of that file's tests error with `ModuleNotFoundError`; with it installed they pass.
- **I lumped `trafilatura` in with the heavy ML stack. That was wrong.** It is a small package with no `torch` dependency; only `torch`/`transformers`/`sentence-transformers` are heavy. The "minimal sandbox" is now defined as *no torch/transformers/sentence-transformers, with `trafilatura` installed*, and the old `1535 passed / 0 failed` baseline no longer applies (current: `1970 passed, 1 xfailed`).
