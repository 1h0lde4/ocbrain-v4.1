# Commands as executed (2026-11-24). Run from a clone of the repository; not re-run as a single script.

Per commit C in {4a4783c47ac37971a7d51ab3d7ab6fc904a37106, f13bfdefcdd197ed1f966de0b1f93037a4168af4}, with S = its first 7 characters:

1. `mkdir -p run/S && git archive C | tar -x -C run/S`   (clean extraction; the repository checkout is not touched)
2. `python3 -m venv run/venv_S`
3. `run/venv_S/bin/pip install --no-deps --disable-pip-version-check -r environment/pins_S.txt`
   (pin file = the package==version pairs from the "Successfully installed" line of the CI tests job log for that run,
   in `ME_RECOVERY_BATCH_3_LOGS_INTAKE_2026-11-20/received/`, minus the 19 packages `nvidia-*`, `torch`, `triton`,
   `transformers`, `sentence-transformers`)
4. `cd run/S && ../venv_S/bin/python -m pytest tests/test_execution_runtime.py tests/test_supervisor_worker.py tests/test_evaluator_worker.py tests/test_workflow_runtime.py tests/test_workflow_failure_disclosure.py tests/test_scheduler_failure_containment.py -v --tb=short -p no:cacheprovider -rfEs`

Notes: the first install attempt for 4a4783c was killed when a tool call timed out and was restarted detached (`setsid nohup`);
the wheel cache made the rerun faster. A collect-only pass (170 tests collected) preceded the run. Output headers in `run/` record the Python and pytest versions.
