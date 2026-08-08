# OCBrain v4.1 — Active Runtime Bug Verification & Fix Plan

## Findings Summary

| Finding | Audit Claim | Verdict | Action |
|---------|-------------|---------|--------|
| A1 | Workflow Runtime ID mismatch | **VERIFIED** | Fix |
| A2 | Evaluator event lookup window | **VERIFIED** | Fix |
| A3 | Interaction history overwrite | **INTENTIONAL** | No fix |
| A4 | AdaptiveSemaphore shrink bug | **VERIFIED** | Fix |
| A5 | Cleaner/Crawler race | **DORMANT** | No fix |
| A6 | Config synchronous writes | **VERIFIED** | Fix |
| A7 | System controller sandbox bypass | **VERIFIED** | Fix |
| A8 | Configuration endpoint unrestricted | **VERIFIED** | Fix |
| A9 | API authentication | **INTENTIONAL** | Minimal fix |

---

## Detailed Verification

### A1 — Workflow Runtime identifier mismatch: **VERIFIED**

**Execution trace:**
1. Compiler ([compiler.py:245](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/cognitive/compiler.py#L245)) sets `WorkflowDefinition.workflow_id = plan.resource_id`
2. WorkflowRuntime ([runtime.py:151](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workflow/runtime.py#L151)) generates a new UUID `instance_id`
3. WorkflowRuntime emits `workflow.started`/`workflow.completed` events using `definition.workflow_id` (correct — matches `plan.resource_id`)
4. **BUG:** WorkflowRuntime ([runtime.py:353](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workflow/runtime.py#L353)) creates `ExecutionContext(workflow_id=instance_id)` — uses the wrong ID
5. Worker base ([base.py:402-403](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workers/base.py#L402-L403)) emits `worker.completed`/`worker.failed` events with `context.workflow_id` → tagged with `instance_id`
6. EvaluatorWorker ([evaluator.py:246](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workers/evaluator.py#L246)) queries with `plan.resource_id` → finds workflow events but **misses all worker events**
7. **Result:** `tool_success_rate` always defaults to `1.0` (no worker events match)

**Fix:** Change [runtime.py:353](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workflow/runtime.py#L353) to use `definition.workflow_id` instead of `instance_id`. The `instance_id` is still preserved in the `WorkflowResult` and event metadata for tracing purposes.

---

### A2 — Evaluator event lookup window: **VERIFIED**

**Execution trace:**
1. `_fetch_workflow_events()` ([evaluator.py:122](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workers/evaluator.py#L122)) queries `EventStream.query(event_type=..., limit=200)`
2. SQLiteEventStore ([event_stream.py:263](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/events/event_stream.py#L263)) returns the **200 most recent** events of that type across the entire system
3. Python-level filter ([evaluator.py:123](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workers/evaluator.py#L123)) then keeps only matching `workflow_id`
4. Under load, a workflow's events can be pushed out of the 200-event window, silently defaulting

**Fix:** Pass the workflow's timestamp range (`since`/`until`) from the workflow events to narrow the DB query, avoiding unbounded scanning. This uses EventStream's existing `since`/`until` parameters — no new query capability needed.

---

### A3 — Interaction history overwrite: **INTENTIONAL DESIGN**

The `_interaction_id()` docstring ([orchestrator.py:43-64](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/orchestrator.py#L43-L64)) explicitly documents this as a design decision:
- L1 = current knowledge state (one row per unique query, UPSERT)
- L4 = full response history (immutable event appended every write)

The `archive_all=False` default means L4 gets creation **events** (not full snapshots), which record the fact of every write. This is documented behavior, not a bug.

**No fix required.**

---

### A4 — AdaptiveSemaphore shrink bug: **VERIFIED**

**Execution trace in** [resilience.py:93-103](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/runtime/resilience.py#L93-L103):
- When latency exceeds target: `new_limit = max(min_limit, int(current_limit * 0.9))`
- When `diff > 0` (increase): releases extra semaphore permits ✓
- When `diff < 0` (decrease): **does nothing** — the `if diff > 0` block is the only branch that modifies the semaphore
- `current_limit` bookkeeping updates, but `asyncio.Semaphore._value` retains the old, higher capacity

**Fix:** When reducing the limit, acquire excess permits from the semaphore to actually reduce its capacity. Since permits may not be immediately available (tasks using them), track the "pending drain" count and drain as permits become available.

> [!IMPORTANT]
> The simplest correct fix is to replace the raw `asyncio.Semaphore` with a new one at the new limit. However, this would break tasks currently awaiting the old semaphore. Instead, we use a `_drain_count` that reduces available capacity by absorbing released permits.

---

### A5 — Cleaner/Crawler race: **DORMANT**

The `learning/cleaner.py` has two `glob("*.txt")` passes (line 27 and line 49). Between them, files could be processed into chunks but then fail to be moved (if the crawler adds new files), or new files could be moved without being processed. However:

1. This is part of the **legacy learning pipeline** (explicitly out of scope per the task rules)
2. The cleaner runs every 6 hours as a batch job, not concurrently with active query paths
3. It does not affect the active cognitive runtime

**No fix required — dormant legacy system.**

---

### A6 — Config synchronous writes: **VERIFIED**

**Execution trace:**
1. Every `route()` call → `_increment_query_count()` ([model_router.py:257-261](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/model_router.py#L257-L261))
2. `_increment_query_count()` → `config.set_module_state()` ([config.py:158-164](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/config.py#L158-L164))
3. `set_module_state()` writes `models.toml` synchronously with `open()/tomli_w.dump()` while holding `self._lock`
4. This blocks the async event loop on every query
5. The watcher thread also takes `self._lock` when reloading, creating contention

**Fix:** Batch `models.toml` writes with a dirty flag + periodic flush instead of writing on every state change. In-memory state changes immediately, disk sync is deferred to a background timer (every 5 seconds or on shutdown).

---

### A7 — System controller sandbox bypass: **VERIFIED**

**Execution trace in** [module.py:48-57](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/modules/system_ctrl/module.py#L48-L57):
1. `_open_app(target)` bypasses `_safe_path()` sandbox — it passes the raw LLM-parsed `target` directly to subprocess
2. On Windows: `shell=True` with `["start", target]` — if `target` contains `& malicious_command`, shell injection is possible
3. On Linux/macOS: no `shell=True`, but arbitrary files/URLs can still be opened

**Fix:**
1. On Windows, use `os.startfile()` instead of `subprocess.Popen(["start", ...], shell=True)` to avoid shell injection
2. On Linux/macOS, validate `target` against an allowlist of safe characters (alphanumeric, dots, hyphens, slashes)
3. Add basic input sanitization to reject shell metacharacters

---

### A8 — Configuration endpoint unrestricted: **VERIFIED**

[api.py:366-370](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/interface/api.py#L366-L370): `PUT /config` accepts any `dict` and writes every key/value to `config.set()`. No key validation, no value validation, no authentication.

**Fix:** Add a key allowlist for mutable configuration. Only explicitly safe keys (e.g., `global.web_ui_port`, `global.debug`) can be modified at runtime. Reject unrecognized keys.

---

### A9 — API authentication: **INTENTIONAL (localhost-only) + minimal CSRF protection**

The API is designed as a localhost-only service ([api.py:302](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/interface/api.py#L302): reference to `http://localhost:7437/debug`). No authentication is expected per the deployment model (local desktop app, not networked service).

However, browser-accessible localhost APIs are vulnerable to CSRF attacks from malicious websites. A mutating POST/PUT from a cross-origin script could be silently forwarded to localhost.

**Fix:** Add an `X-OCBrain-Local` header check on mutating endpoints (POST/PUT/DELETE). Browsers cannot set custom headers cross-origin without CORS preflight, which would fail. This is the minimal CSRF protection without redesigning the API.

---

## Proposed Changes

### WorkflowRuntime (A1)

#### [MODIFY] [runtime.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workflow/runtime.py)
- Line 353: Change `workflow_id=instance_id` → `workflow_id=definition.workflow_id`
- Pass `definition.workflow_id` instead of `instance_id` to `_execute_node_with_retry` (add parameter)

---

### Evaluator Event Lookup (A2)

#### [MODIFY] [evaluator.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/workers/evaluator.py)
- Modify `_fetch_workflow_events()` to accept optional `since`/`until` timestamps
- In `EvaluatorWorker._run()`, first fetch `workflow.completed` events, extract the timestamp range, then use it to bound worker event queries

---

### AdaptiveSemaphore (A4)

#### [MODIFY] [resilience.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/runtime/resilience.py)
- Add `_drain_count` tracker initialized to 0
- On limit decrease: increment `_drain_count` by the absolute difference
- On release: if `_drain_count > 0`, re-acquire the semaphore immediately (absorb the permit) and decrement `_drain_count`
- On limit increase: first satisfy any pending drain, then release remaining

---

### Config Batched Writes (A6)

#### [MODIFY] [config.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/core/config.py)
- Add `_models_dirty` flag (default `False`)
- `set_module_state()`: set flag instead of writing immediately
- Add `_flush_models()` helper to write if dirty
- Modify watcher thread to call `_flush_models()` every cycle (2s)
- Add `flush()` public method for graceful shutdown

---

### System Controller Sandbox (A7)

#### [MODIFY] [module.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/modules/system_ctrl/module.py)
- `_open_app()`: On Windows, use `os.startfile()` instead of `subprocess.Popen(["start", ...], shell=True)`
- Add input validation for shell metacharacters on all platforms

---

### Configuration Endpoint (A8)

#### [MODIFY] [api.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/interface/api.py)
- Add `MUTABLE_CONFIG_KEYS` allowlist
- `PUT /config`: validate keys against allowlist, reject unknown keys

---

### CSRF Protection (A9)

#### [MODIFY] [api.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/interface/api.py)
- Add FastAPI middleware that checks for `X-OCBrain-Local: 1` header on POST/PUT/DELETE requests
- GET requests remain open (read-only, no state changes)

---

### Regression Tests

#### [NEW] [test_audit_fixes.py](file:///c:/Users/Produ/Downloads/ocbrain-v4.1-main(4)/ocbrain-v4.1-main/tests/test_audit_fixes.py)
New test file covering all verified fixes:
- **A1:** Test that worker events use `definition.workflow_id`, not `instance_id`
- **A2:** Test that `_fetch_workflow_events` with bounded timestamps returns correct results under high event volume
- **A4:** Test that `AdaptiveSemaphore` actually reduces effective concurrency after slow responses
- **A6:** Test that `set_module_state` doesn't write to disk immediately; verify flush writes
- **A7:** Test that `_open_app` rejects shell metacharacters
- **A8:** Test that `PUT /config` rejects unknown keys
- **A9:** Test that mutating endpoints reject requests without the local header

---

## Verification Plan

### Automated Tests
```bash
python -m pytest tests/test_audit_fixes.py -v
python -m pytest tests/test_workflow_runtime.py -v
python -m pytest tests/test_evaluator_worker.py -v
python -m pytest tests/test_production_robustness.py -v
python -m pytest tests/test_system_ctrl.py -v
```

### Manual Verification
- Review each change for architectural compliance
- Verify no breaking changes to existing APIs
- Verify existing test suites still pass
