# OCBrain v4.1 — Audit Bug Fix Tasks

- [x] **A1** — Workflow ID mismatch (`core/workflow/runtime.py`)
- [x] **A2** — Evaluator event window (`core/events/event_stream.py`, `core/workers/evaluator.py`)
- [x] **A4** — AdaptiveSemaphore shrink (`core/runtime/resilience.py`)
- [x] **A6** — Config sync writes (`core/config.py`)
- [x] **A7** — Sandbox bypass (`modules/system_ctrl/module.py`)
- [x] **A8** — Config endpoint validation (`interface/api.py`)
- [x] **A9** — API CSRF protection (`interface/api.py`, `interface/web/*.html`)
- [x] **Tests** — Regression tests (`tests/test_audit_fixes.py`)
- [x] **Verification** — All 27 new + 59 existing tests pass (0 regressions)
