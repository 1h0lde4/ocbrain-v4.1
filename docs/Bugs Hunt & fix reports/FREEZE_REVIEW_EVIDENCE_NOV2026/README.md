# Evidence for the Freeze Remediation Register (Nov 2026)

Read-only evidence supporting `FREEZE_REMEDIATION_REGISTER_NOV2026.md`. Baseline: `main` @ `fbe1ebdef553b52abf270a819d976d2e078feeef`. Environment: Python 3.12.3, `chromadb==0.5.3`, numpy 1.26.4, scipy 1.13.1; `sentence-transformers` not installed.

## DEBT-012 files

- `debt012_config_content_diff.patch` — `git diff --ignore-cr-at-eol -- config` after a full `pytest tests -q` run from a clean tree (6 insertions, 35 deletions; CRLF noise excluded). Three independent full-suite runs produced the same content changes (runs 2 and 3 compared byte-for-byte with `cmp`; run 1 was inspected earlier in the review session).
- `debt012_config_writers.tsv` — writes to tracked `config/` and `data/` files observed by a throw-away pytest plugin that wrapped `builtins.open`, `io.open`, `os.replace` and `os.rename` and recorded the running test node ID. Limits: it sees Python-level writes only; SQLite C-level writes are not captured; one row has no test attribution (`<between tests>`, a `config/settings.toml` write outside any test body — setup/teardown, a fixture or collection-time code; not further attributed).
- `data/context.sqlite` SHA-256 before: `858b5af1dec53ff0f4811db8c0e91d9ba407f0e727ec63e02084b1e3c95a76f0`; after `import interface.api` alone and after the full suite (identical): `a59c39a22e84bc225e47a2e375b1c1226f2fe4a963a17897ab3e2d57447c3860`. Call site of the import-time open: `core/context.py:320` (`context_memory = ContextMemory()`), opening the database at `core/context.py:34`, reached via `core/orchestrator.py:13` (`from .context import ContextMemory`) from `interface/api.py:24`.

## Sandbox files

- `sandbox_namespace_tests_run.txt` — per-test outcomes of `tests/core/sandbox/test_namespace_backend.py` (14 tests) under the system interpreter: 14 passed; header records the earlier venv-interpreter run (8 failed, `execvp` `FileNotFoundError`). Single environment; says nothing about what CI executes (see register EVG-01).

- `sandbox_namespace_tests_cc446f8.txt` — the same file at the exact CI commit `cc446f8` with host configuration (kernel, cgroup filesystem type, `memory` directory writable, `unshare` exit code): 14 passed, 0 skipped. Author-run, single environment, system interpreter. The CI result for this commit (14 skipped) was reported to the review and is not stored here as a retrieved artifact.

## Commands (clean clone, working tree reverted afterwards)

```
python -m pytest tests -q -p no:cacheprovider --maxfail=80
git status --short; git diff --ignore-cr-at-eol -- config
sha256sum data/context.sqlite     # before / after
```
