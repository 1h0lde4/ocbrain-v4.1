# handoff_artifacts

Scripts and text preserved from the ephemeral sandbox of the session described in `../handoff.md`. They are **evidence/verification tools, not product code**, and are not wired into CI.

**Paths inside them are sandbox-specific** (`/home/claude/...`, `/tmp/...`); adapt them before use. None contains a credential.

| File | Purpose |
|---|---|
| `repro_symlinks.py` | Reproduces the `module_child()` nested-symlink and symlink-loop matrix against any copy of `core/module_paths.py` (`python repro_symlinks.py <path-to-module_paths.py>`); run it on Python 3.11 to 3.14 to see the `Path.resolve()` loop difference. |
| `diff_helpers.py` | Differential harness: runs two versions of `module_child()` over 45 filesystem scenarios and prints any divergence (`python diff_helpers.py <old.py> <new.py>`). Use a pre-fix helper as a positive control. |
| `mut.py` | Ten-mutant runner for `tests/test_import_bundle_boundary.py` against `core/brain_export.py` and `interface/api.py` (run from the repo root; restores the files). |
| `mut2.py` | Seven-mutant runner for `tests/test_workflow_failure_disclosure.py` against `core/orchestrator.py` and `core/error_ref.py` (run from the repo root; restores the files). |
| `repro_planner_error.py` | Reproduces the pre-#63 leak by making `ContextMemory.save` raise inside the PlannerWorker pipeline. |
| `st_assessment.md` | The #70 exposure assessment as posted to issue #70. |

Mutation runners rewrite source files temporarily; run them on a clean worktree and confirm the sources are byte-identical afterwards.
