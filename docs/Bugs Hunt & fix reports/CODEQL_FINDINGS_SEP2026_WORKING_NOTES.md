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
