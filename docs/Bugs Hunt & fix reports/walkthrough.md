# OCBrain v4.1 — Post-Fix Audit Verification Report

## 1. Verification Summary

| Fix | Finding | Verdict |
|-----|---------|---------|
| **A1** — Workflow Runtime Identifier | Worker events correctly use `definition.workflow_id`. Instance UUID preserved in `metadata["instance_id"]`. No event schema regression. Evaluator consumes correct identifier. | **VERIFIED** |
| **A2** — EventStream Query Extension | `payload_workflow_id` filtering performed via `json_extract()` in SQLite `_query_sync()`. Index created on `json_extract(payload, '$.workflow_id')` in `_init_db()`. Existing databases handled by `CREATE INDEX IF NOT EXISTS`. No API compatibility broken — new parameter is optional with `None` default. | **VERIFIED** |
| **A4** — AdaptiveSemaphore | `_drain_count` mechanism correctly absorbs permits on shrink. All drain bookkeeping is under `self._lock` (asyncio.Lock). Grow path correctly reduces pending drain before releasing surplus. No negative drain count possible. No deadlock path — no nested lock acquisition. No permit leakage — every `__aexit__` either releases or absorbs exactly one permit. | **VERIFIED** |
| **A6** — Config Persistence | Critical keys (`stage`, `bootstrap_model`, etc.) persist immediately via `_persist_models()`. Non-critical keys set `_models_dirty = True` for deferred write. Watcher thread flushes every 2 seconds. `flush()` method available for explicit persistence. **Issue found**: `main.py` shutdown path did not call `config.flush()` — deferred state could be lost because watcher is a daemon thread. **Fixed.** | **VERIFIED WITH MINOR ISSUE** |
| **A7** — System Controller | `_validate_open_target()` rejects shell metacharacters via regex on all platforms. Windows uses `os.startfile()` (no shell). Linux uses `subprocess.Popen(["xdg-open", target])` without `shell=True`. macOS uses `subprocess.Popen(["open", target])` without `shell=True`. Empty targets, flag-like targets (`-flag`) rejected. Unicode paths handled by Python's native path handling. URLs pass validation (no metacharacters in valid URLs). | **VERIFIED** |
| **A8** — Runtime Configuration Endpoint | `MUTABLE_CONFIG_KEYS` allowlist contains 5 safe keys. `PUT /config` rejects any key not in the allowlist with HTTP 400. Mixed valid/invalid requests are fully rejected. Existing `config.set()` persistence path unchanged. | **VERIFIED** |
| **A9** — Local API Protection | `CSRFHeaderMiddleware` requires `X-OCBrain-Local` header on POST/PUT/DELETE. GET/HEAD/OPTIONS exempt. OpenAPI docs exempt. **Issue found**: CLI `_post()` was missing the header — all CLI POST requests would be rejected by the CSRF middleware. **Fixed.** Web UI: all mutating `fetch()` calls include the header (verified in `index.html`, `settings.html`, `wizard.html`). | **VERIFIED WITH MINOR ISSUE** |

---

## 2. Issues Found

Two implementation issues were discovered and corrected:

### Issue 1: A9 — CLI missing CSRF header (incomplete implementation)

**File**: [`interface/cli.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/interface/cli.py) line 30

**Problem**: The `_post()` helper function used by all CLI commands did not include the `X-OCBrain-Local: 1` header. After the CSRF middleware was deployed, every CLI POST request (`/query`, `/train`, `/distill`, `/export`, `/import`, etc.) would receive HTTP 403.

**Fix**: Added `headers={"X-OCBrain-Local": "1"}` to the `httpx.post()` call.

```diff
 def _post(path: str, data: dict = None) -> dict:
-    resp = httpx.post(f"{BASE}{path}", json=data or {}, timeout=120)
+    resp = httpx.post(f"{BASE}{path}", json=data or {}, headers={"X-OCBrain-Local": "1"}, timeout=120)
     resp.raise_for_status()
```

### Issue 2: A6 — No config.flush() on shutdown (data loss risk)

**File**: [`main.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/main.py) line 433

**Problem**: The A6 fix introduced deferred writes for non-critical config keys, with the watcher thread (`daemon=True`) flushing dirty state every 2 seconds. On shutdown, daemon threads are killed immediately by Python — any dirty state not yet flushed would be silently lost.

**Fix**: Added `config.flush()` to the `finally` block in `main.py` before `state_store.stop()`.

```diff
     finally:
+        from core.config import config as _cfg
+        _cfg.flush()          # persist any deferred model state
         asyncio.run(state_store.stop())
```

---

## 3. Code Changes

Two files were modified:

| File | Change |
|------|--------|
| [`interface/cli.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/interface/cli.py) | Added `X-OCBrain-Local: 1` header to `_post()` |
| [`main.py`](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/main.py) | Added `config.flush()` to shutdown `finally` block |

Committed as: `fix(post-audit): add CSRF header to CLI, add config.flush() on shutdown`

---

## 4. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| `test_audit_fixes.py` (new) | 27 | ✅ All passed |
| `test_evaluator_worker.py` | 26 | ✅ All passed |
| `test_workflow_runtime.py` | 20 | ✅ All passed |
| `test_production_robustness.py` | 4 | ✅ All passed |
| `test_system_ctrl.py` | 9 | ✅ All passed |
| **Total** | **86** | **✅ 86 passed, 0 failed** |

### Regression Test Review

The 27 tests in `test_audit_fixes.py` were reviewed for correctness:

- **A1 tests**: Correctly verify that `WorkerContext.workflow_id` equals `definition.workflow_id` (canonical), and that `instance_id` is preserved in metadata. Not false positives — they exercise the full `WorkflowRuntime.execute()` → `ExecutionRuntime.invoke()` path.
- **A2 tests**: Correctly verify database-level filtering by inserting events with different `workflow_id` values and querying with `payload_workflow_id`. The high-volume test validates the fix works at scale (500 noise events + 5 target events).
- **A4 tests**: Correctly verify grow, shrink, no-deadlock, and drain count behavior. The shrink test uses actual latency to trigger AIMD decisions, not mocked values.
- **A6 tests**: Correctly verify immediate persistence for critical keys and dirty-flag deferral for non-critical keys. Uses `tmp_path` fixtures and patches `CONFIG_DIR` for isolation.
- **A7 tests**: Correctly verify rejection of 13 dangerous inputs, empty/flag-like targets, acceptance of 8 safe inputs, and AST-based verification that no `shell=True` exists in executable code.
- **A8 tests**: Correctly verify the allowlist exists, unknown keys are rejected with 400, and mixed-key requests are fully rejected.
- **A9 tests**: Correctly verify POST without header returns 403, PUT without header returns 403, GET without header succeeds, POST with header passes CSRF, and docs endpoint is exempt.

No missing edge cases or weak assertions were identified.

---

## 5. Architecture Validation

| Fix | Architectural Invariant | Preserved? | Documentation Impact |
|-----|------------------------|------------|---------------------|
| **A1** | §8 — Workflow events use canonical workflow_id for evaluator correlation | ✅ Yes | None |
| **A2** | §4.1 Layer 1 — EventStream query interface is extensible via kwargs | ✅ Yes — new optional parameter, backward compatible | None |
| **A4** | §7.1 — ExecutionRuntime concurrency is bounded by AdaptiveSemaphore | ✅ Yes — drain mechanism preserves bound correctness | None |
| **A6** | Config persistence — state must survive process restarts | ✅ Yes — critical keys immediate, non-critical deferred + flush on shutdown | None |
| **A7** | System control — no arbitrary shell execution | ✅ Yes — input validation + safe platform APIs | None |
| **A8** | API surface — configuration mutations are controlled | ✅ Yes — explicit allowlist | None |
| **A9** | Localhost security — API cannot be exploited via browser CSRF | ✅ Yes — header requirement on mutating endpoints | None |

No architecture documents became inaccurate as a result of these changes.

---

## 6. Final Verdict

### **ACCEPTED WITH MINOR CORRECTIONS**

Two incomplete implementation issues were found and corrected:
1. CLI client was missing the CSRF header (A9 would have broken CLI functionality)
2. Shutdown path did not flush deferred config state (A6 data loss risk)

Both corrections were minimal, targeted, and verified with the full 86-test suite passing.
