# AZ1 record: verbose run of the six identified test files (2026-11-24)

**Status: record only.** The review disposition stays OPEN / NO PASS. New files only; docs-only for the repository. This is the
execution authorized by the owner as AZ1. Nothing else was executed, no repository file was modified, and AZ2 to AZ6 remain unauthorized.

## 1. Authority and scope

- Owner statement, 2026-11-24, a single-choice answer in the review chat to "What should happen to the claim that 170 tests passed on
  4a4783c and f13bfde? (RD5)": **"Authorize a verbose run of the six files (AZ1)"**. The other choices offered were "Withdraw it" and "Keep it
  open; I'll supply the original logs".
- Scope used: the six test files named in the Q4-b brief section 18 (`test_execution_runtime`, `test_supervisor_worker`, `test_evaluator_worker`,
  `test_workflow_runtime`, `test_workflow_failure_disclosure`, `test_scheduler_failure_containment`), at the two commits the claim names, verbose,
  with the environment recorded. Not run: the rest of `tests/`, anything on current `main`, any probe.

## 2. Result

| Commit | Full SHA | Run started (UTC) | Interpreter; pytest | Pinned packages installed | Result | SHA-256 of the output file |
|--------|----------|-------------------|---------------------|---------------------------|--------|----------------------------|
| `4a4783c` | `4a4783c47ac37971a7d51ab3d7ab6fc904a37106` | 2026-11-24T09:06:27Z | Python 3.12.3; pytest 9.2.0 | 129 | 170 passed in 11.57s | `8a8665c3d974b415ab6955d97e25a41e649fee90760b390d29763abe42f972b6` |
| `f13bfde` | `f13bfdefcdd197ed1f966de0b1f93037a4168af4` | 2026-11-24T09:08:36Z | Python 3.12.3; pytest 9.1.1 | 128 | 170 passed in 7.49s | `8cb8ebcc039ef1c384fe013c2d0273c75e3c82142ff9292e9d3521a5eb10482e` |

Per-file results, identical on both commits (every test PASSED, none failed, errored, skipped or xfailed): `test_execution_runtime.py` 37,
`test_supervisor_worker.py` 29, `test_evaluator_worker.py` 26, `test_workflow_runtime.py` 35, `test_workflow_failure_disclosure.py` 8,
`test_scheduler_failure_containment.py` 35: total 170. `verify/summarize_az1.py` re-derives this from the recorded outputs (22 of 22 checks,
exit 0, `verify/VERIFY_OUTPUT.txt`); a one-line alteration of a recorded result makes it exit 1.

## 3. Method

- Each commit was extracted with `git archive` into a clean directory outside the repository checkout, with its own virtual environment.
- Package versions are the ones CI installed for that run (the "Successfully installed" line of the tests job log, Batch 3 `received/I006` and `I007`),
  installed with `--no-deps`. The 19 packages of the CUDA and torch chain (`nvidia-*`, `torch`, `triton`, `transformers`, `sentence-transformers`) were not
  installed; the full pin files are in `environment/`, and `environment/pip_freeze_*.txt` lists what the virtual environments actually contained.
- Exact commands: `reproduce/COMMANDS.md`. Sandbox facts: `environment/SANDBOX.txt` (Ubuntu 24.04, Python 3.12.3, one CPU, `huggingface.co` does not resolve).

## 4. What this shows, and what it does not

- It REPRODUCES the claim in the Q4-b brief that the six files give 170 passed on `4a4783c` and on `f13bfde`: the selection, the per-file counts
  (matching the 170 collected on `16d663a` recorded earlier in the inventory) and the pass result, on both commits, in this environment.
- It does NOT recover the original execution logs behind the claim, and it is not the CI environment: CI used Python 3.12.15 and installed the
  CUDA, torch and sentence-transformers stack; this run used 3.12.3 without that stack, and without any route to Hugging Face. The package sets
  therefore differ from CI's by those 19 packages.
- `test_workflow_failure_disclosure.py::test_a_successful_workflow_run_is_unchanged` PASSED here without the model stack. The inventory records that
  this test needed the real embedding model and failed in the earlier review environment on `16d663a`. Both can be true (different commit and
  environment); the cause of the difference is NOT established here and is not explained away.
- The run says nothing about current `main` (`ef1351f` when last checked), about the rest of the suite, or about the HTTP-layer findings (AZ2).

## 5. Files

`README.md` (this record); `run/az1_4a4783c.txt`, `run/az1_f13bfde.txt` (full verbose output); `environment/` (pins, `pip freeze`, sandbox facts);
`reproduce/COMMANDS.md`; `verify/summarize_az1.py`, `verify/VERIFY_OUTPUT.txt`; `SHA256SUMS.txt` (every file above except itself; check with
`cd <this directory> && sha256sum -c SHA256SUMS.txt`).
