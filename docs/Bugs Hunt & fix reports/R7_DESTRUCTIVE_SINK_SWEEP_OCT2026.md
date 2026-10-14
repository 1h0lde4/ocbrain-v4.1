# R7 — Destructive-sink sweep (Oct 2026)

**Question.** `acc43b7` claims to route *every* module-name filesystem path through `core/module_paths.module_child()`. A claim of "every" has the same shape as the `export_module()` coverage gap found earlier in this workstream (CTX-EXPORT-001 fixed one function over from its sibling). Is it true, and are there other unguarded destructive sinks?

**Method.** `r7_destructive_sink_sweep.py` (same directory): an AST pass over every production `.py` file at a git ref (197 files; `tests/`, `docs/`, archives excluded) enumerating filesystem-mutating call sites and classifying each path argument's origin through local assignments. Deliberately *not* a grep — the first grep-based pass this workstream used had false negatives, and a GitHub-indexed search (another session's preliminary R7) can't resolve data flow at all.

**Recall check (done before trusting the result).** On `origin/main` the known-bad site `core/privacy.py::wipe_module_data` is classified `PARAM`; on the R6 fix branch (PR #79) it flips to `GUARDED`, and the counts move as they should (PARAM −1, GUARDED +1). One known site is a small sample — this shows the tool is not blind, not that its recall is high.

**Result: 133 filesystem-mutating call sites.** `CONST` 62 · `GUARDED` 28 · `STATE` 24 · `PARAM` 19. (The first run reported 138/30 PARAM; it counted `write_text`'s *content* argument as a path and matched `trafilatura.extract`. Both fixed; the refined script is the one committed.)

## The 19 `PARAM` sinks, each read — not shrugged at

| Site | Disposition | Basis |
|---|---|---|
| `core/privacy.py:28` `wipe_module_data` | **Was unguarded → fixed (PR #79, DEBT-042)** | Exploit-first tests: 8 failed / 6 passed on unfixed code (decoys outside `data/` deleted) → 14 passed. **Latent: no production caller.** |
| `core/brain_export.py:229` `_safe_extractall` | The zip-slip-safe extraction helper itself | PR #35's `TestZipSlipExtraction`; suite green. Its caller's `dest` not re-traced here |
| `modules/system_ctrl/module.py:114,115,136` (`_write_file`, `_delete_file`) | **Guarded by a different, bespoke boundary — sound** | `_safe_path()`: `resolve()` (absolute→`resolve()`, relative→`(root/p).resolve()`) then `requested.relative_to(root)`; not a string-prefix check. Intended capability, confined to `SAFE_ROOT` |
| `learning/crawler.py:95` `_save_raw` | Guarded by its caller | `out_dir = module_child(DATA_RAW, module_name)` at line 33 |
| `learning/scheduler.py:410` `trigger_module` | Guarded | Traced earlier: sole HTTP caller is `/train/{module_name}` behind `in _orchestrator.modules`; finetuner now uses `module_child` |
| `core/memory/backends/sqlite_archive.py:226,227` (`export_jsonl`'s nested `_export` closure) | **Latent, caller-supplied output path** | `export_jsonl(path)` has **zero callers** (a Protocol declaration + the implementation only). File creation/truncation, not deletion |
| `core/shadow/collector.py:54,57` `export_training_dataset(output_path)` | **Latent, caller-supplied output path** | One reference in the whole repo: its own definition |
| `core/events/event_stream.py:172` | Internal | `EventStream.__init__(db_path)` — constructor/config path |
| `core/sandbox/backends/_ns_init.py:65`, `namespace_backend.py:136,172,353` | Sandbox internals — **not traced** | Cgroup files and a workspace dir from `request.policy`, which is built by trusted code; not followed to an external source |
| `live_citation_check.py:275`, `scripts/check_drift.py:922`, `scripts/live_check_draft_plan.py:234` | Dev CLI tooling | Write to paths given on the command line; not runtime |

**`STATE` (24)** — db paths, log files, storage dirs, `modules/base.py`'s weights dirs under `self.root`/`self.name`. Internal *unless something outside can set those values*. The obvious HTTP candidate, `PUT /config`, accepts only `MUTABLE_CONFIG_KEYS = {global.ollama_host, global.debug, global.log_level, global.web_ui_port, global.auto_update}` — **none path-valued** (read from `interface/api.py:150`, not inferred). Individual `STATE` sinks were not traced further.

## Conclusion — stated at the strength the evidence supports

- The sweep found **one** unguarded destructive sink: R6, **latent** (no caller), now fixed. It found **no second unguarded, externally-reachable destructive sink** in the code it could see.
- That is **not** "every path is guarded." Caveats, in order of importance: (1) it is an **intra-function heuristic** — `PARAM` mixes trusted internal parameters with attacker-influenced ones, and only the listed sinks were caller-traced; (2) **recall is validated on a single known-bad site**; (3) it cannot see dynamic dispatch, shell-string file operations (`subprocess`), cross-function taint beyond parameters, or non-Python code; (4) the sandbox-backend sinks and the 24 `STATE` sinks were classified, not traced.
- Two **latent** output-path sinks (`export_jsonl`, `export_training_dataset`) are worth confining to an export root *if* they are ever wired to a route — `/import`'s `bundle_path` needed exactly that when it was (`6dee2b2`).
- Option for Moncif (not done, a policy call): a drift check that flags a new `rmtree`/`unlink` on a path not built via `module_child()` would turn this one-off audit into a standing control. The sweep script is most of the work.

## Methodology lessons recorded in-session
- A red run of a deletion-exploit test **executes the exploit**: every payload must resolve inside `tmp_path`. An early draft's `"/etc"` payload would have been `rmtree("/etc")` on unfixed code (`pathlib`: `Path("a") / "/etc"` is `Path("/etc")`). Now written into `tests/test_privacy.py`'s header.
- Twice in this workstream an *empty or zero result* came from a broken command, not a finding: `grep -c` over the output of a failing `git` (after a container reset), and a pattern `(def|\.)_?export\(` that cannot match `def _export(`. An empty result is evidence only after the command is shown to be capable of matching.
- `core/privacy.py` and `tests/test_privacy.py` are CRLF; edits were byte-aware (diffstat 6+/1−), not whole-file rewrites.

## Reconciliation notes (a second session's report vs. live data)
- **CodeQL counts.** The repo's own text (`KNOWN_ISSUES.md` header, `CURRENT_STATE.md`) says **34 fixed + 4 dismissed**; the live REST API lists **37 alerts: 33 fixed + 4 dismissed, 0 open**. They disagree by one; I could not tell which is wrong from here. A docs-vs-API mismatch for Moncif to resolve — not a result of either session.
- **Dependabot (their claims verified against the advisory data).** All three `chromadb` advisories list **no patched version** and `0.5.3` is inside every affected range; `sentence-transformers` is affected `< 5.6.0` (fixed in `5.6.0`; the repo's `<4.0` bound excludes it). **Sharper fact neither document stated:** the chromadb affected ranges end at `<= 1.5.9` — the exact version open PR #33 bumps to — so merging #33 would **not fix any chromadb alert** while breaking the `DEBT-032` pin alignment with `release.yml`. The alert count also grew from 4 to 7 (duplicate CVE entries, likely a second manifest) — not investigated.
