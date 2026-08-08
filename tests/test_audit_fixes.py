"""
tests/test_audit_fixes.py — Regression tests for verified audit findings A1–A9.

Covers:
    A1: Worker events use canonical workflow_id (definition.workflow_id)
    A2: Event lookup uses database-level workflow_id filtering
    A4: AdaptiveSemaphore actually reduces effective concurrency
    A6: Config defers non-critical writes, persists critical keys immediately
    A7: _open_app rejects shell metacharacters on all platforms
    A8: PUT /config rejects unknown/immutable keys
    A9: Mutating endpoints require X-OCBrain-Local header
"""
import asyncio
import os
import sys
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ═══════════════════════════════════════════════════════════════════════════
# A1 — Workflow Runtime identifier: worker events use canonical workflow_id
# ═══════════════════════════════════════════════════════════════════════════

class TestA1WorkflowIdentifier:
    """Worker events must be tagged with definition.workflow_id, not instance_id."""

    @pytest.mark.asyncio
    async def test_worker_events_use_definition_workflow_id(self):
        """ExecutionContext.workflow_id must equal definition.workflow_id,
        not the per-execution instance UUID."""
        from core.workflow.definition import (
            WorkflowDefinition, WorkflowNode, WorkflowEdge, RetryPolicy,
        )
        from core.workflow.runtime import WorkflowRuntime, WorkflowResult
        from core.runtime.worker_registry import WorkerRegistry
        from core.runtime.execution_runtime import ExecutionRuntime
        from core.runtime.cancellation import CancellationToken
        from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
        from core.governance.governance_kernel import get_governance_kernel
        from core.events.event_stream import get_event_stream

        # Track the workflow_id that ExecutionContext receives
        captured_workflow_ids = []

        class CapturingWorker(AbstractCognitiveWorker):
            worker_type = "CapturingWorker"

            async def _run(self, context: WorkerContext) -> WorkerResult:
                captured_workflow_ids.append(context.workflow_id)
                return WorkerResult(success=True, output="ok")

        governance = get_governance_kernel()
        event_stream = get_event_stream()
        registry = WorkerRegistry()
        registry.register(CapturingWorker)
        exec_runtime = ExecutionRuntime(
            worker_registry=registry,
            governance=governance,
            event_stream=event_stream,
        )

        canonical_wf_id = "plan-resource-id-canonical"
        definition = WorkflowDefinition(
            workflow_id=canonical_wf_id,
            entry_node="node_a",
            nodes=[WorkflowNode(
                node_id="node_a",
                worker_type="CapturingWorker",
                retry_policy=RetryPolicy(),
            )],
            edges=[],
        )

        wf_runtime = WorkflowRuntime(
            execution_runtime=exec_runtime,
            event_stream=event_stream,
        )

        result = await wf_runtime.execute(
            definition=definition,
            query="test query",
            session_id="sess-1",
        )

        assert result.success, f"Workflow failed: {result}"
        assert len(captured_workflow_ids) == 1
        assert captured_workflow_ids[0] == canonical_wf_id, (
            f"Worker received workflow_id={captured_workflow_ids[0]!r}, "
            f"expected canonical={canonical_wf_id!r}"
        )

    @pytest.mark.asyncio
    async def test_instance_id_preserved_in_metadata(self):
        """The per-execution instance UUID should be available in context metadata."""
        from core.workflow.definition import (
            WorkflowDefinition, WorkflowNode, RetryPolicy,
        )
        from core.workflow.runtime import WorkflowRuntime
        from core.runtime.worker_registry import WorkerRegistry
        from core.runtime.execution_runtime import ExecutionRuntime
        from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
        from core.governance.governance_kernel import get_governance_kernel
        from core.events.event_stream import get_event_stream

        captured_metadata = []

        class MetadataWorker(AbstractCognitiveWorker):
            worker_type = "MetadataWorker"

            async def _run(self, context: WorkerContext) -> WorkerResult:
                captured_metadata.append(dict(context.metadata))
                return WorkerResult(success=True, output="ok")

        governance = get_governance_kernel()
        event_stream = get_event_stream()
        registry = WorkerRegistry()
        registry.register(MetadataWorker)
        exec_runtime = ExecutionRuntime(
            worker_registry=registry, governance=governance, event_stream=event_stream,
        )

        definition = WorkflowDefinition(
            workflow_id="canonical-id",
            entry_node="n1",
            nodes=[WorkflowNode(node_id="n1", worker_type="MetadataWorker",
                                 retry_policy=RetryPolicy())],
            edges=[],
        )

        wf_runtime = WorkflowRuntime(
            execution_runtime=exec_runtime, event_stream=event_stream,
        )
        await wf_runtime.execute(definition=definition, query="q", session_id="s")

        assert len(captured_metadata) == 1
        assert "instance_id" in captured_metadata[0], (
            "instance_id must be preserved in context metadata for tracing"
        )
        # instance_id must be a UUID, NOT the canonical workflow_id
        assert captured_metadata[0]["instance_id"] != "canonical-id"


# ═══════════════════════════════════════════════════════════════════════════
# A2 — Evaluator event lookup: database-level workflow_id filtering
# ═══════════════════════════════════════════════════════════════════════════

class TestA2EventLookup:
    """_fetch_workflow_events must use database-level filtering."""

    @pytest.mark.asyncio
    async def test_database_level_workflow_filtering(self, tmp_path):
        """Events are filtered by workflow_id at the DB level, not in Python."""
        from core.events.event_stream import EventStream, SQLiteEventStore

        store = SQLiteEventStore(str(tmp_path / "events.db"))
        es = EventStream(store=store)

        # Append events for two different workflows
        for i in range(10):
            await es.append(
                event_type="worker.completed",
                source="TestWorker",
                payload={"workflow_id": "wf-A", "index": i},
            )
        for i in range(10):
            await es.append(
                event_type="worker.completed",
                source="TestWorker",
                payload={"workflow_id": "wf-B", "index": i},
            )

        # Query with payload_workflow_id — should only get wf-A events
        results = await es.query(
            event_type="worker.completed",
            payload_workflow_id="wf-A",
        )
        assert len(results) == 10
        assert all(e.payload["workflow_id"] == "wf-A" for e in results)

    @pytest.mark.asyncio
    async def test_high_volume_no_event_loss(self, tmp_path):
        """Under high event volume, workflow events are never lost."""
        from core.events.event_stream import EventStream, SQLiteEventStore

        store = SQLiteEventStore(str(tmp_path / "events_heavy.db"))
        es = EventStream(store=store)

        # Simulate high load: 500 events from other workflows
        for i in range(500):
            await es.append(
                event_type="worker.completed",
                source="BusyWorker",
                payload={"workflow_id": f"noise-{i % 50}", "data": "x" * 100},
            )

        # Our target workflow's events (buried under the noise)
        for i in range(5):
            await es.append(
                event_type="worker.completed",
                source="TargetWorker",
                payload={"workflow_id": "target-wf", "step": i},
            )

        # Old approach with limit=200 would miss target-wf events entirely
        # New approach with payload_workflow_id finds them directly
        results = await es.query(
            event_type="worker.completed",
            payload_workflow_id="target-wf",
        )
        assert len(results) == 5
        assert all(e.payload["workflow_id"] == "target-wf" for e in results)

    @pytest.mark.asyncio
    async def test_query_without_workflow_filter_unchanged(self, tmp_path):
        """Existing query behavior without workflow_id filter is preserved."""
        from core.events.event_stream import EventStream, SQLiteEventStore

        store = SQLiteEventStore(str(tmp_path / "events_compat.db"))
        es = EventStream(store=store)

        for i in range(5):
            await es.append(
                event_type="test.event",
                source="src",
                payload={"workflow_id": f"wf-{i}"},
            )

        # Query without payload_workflow_id — returns all events
        results = await es.query(event_type="test.event")
        assert len(results) == 5


# ═══════════════════════════════════════════════════════════════════════════
# A4 — AdaptiveSemaphore: shrinking must actually reduce concurrency
# ═══════════════════════════════════════════════════════════════════════════

class TestA4AdaptiveSemaphore:
    """AdaptiveSemaphore must actually shrink effective concurrency."""

    @pytest.mark.asyncio
    async def test_semaphore_shrinks_effective_concurrency(self):
        """After slow responses trigger a limit decrease, the semaphore
        must actually prevent that many concurrent acquisitions."""
        from core.runtime.resilience import AdaptiveSemaphore

        # Start at limit=5, target 50ms
        sem = AdaptiveSemaphore(min_limit=1, max_limit=5, target_latency_ms=50)
        # Seed the limit up to 5 via fast calls
        for _ in range(10):
            async with sem:
                await asyncio.sleep(0.005)  # 5ms — well below target

        assert sem.current_limit > 1, "Limit should have grown"
        limit_before = sem.current_limit

        # Now do slow calls to trigger shrinking
        for _ in range(5):
            async with sem:
                await asyncio.sleep(0.2)  # 200ms — well above 50ms target

        assert sem.current_limit < limit_before, (
            f"Limit should have decreased from {limit_before}, "
            f"got {sem.current_limit}"
        )

        # Verify ACTUAL concurrency is restricted:
        # Try to acquire more permits than current_limit simultaneously
        results = []

        async def try_acquire():
            try:
                await asyncio.wait_for(sem._semaphore.acquire(), timeout=0.05)
                results.append(True)
            except asyncio.TimeoutError:
                results.append(False)

        # Try to acquire current_limit + 2 permits
        tasks = [asyncio.create_task(try_acquire())
                 for _ in range(sem.current_limit + 2)]
        await asyncio.gather(*tasks)

        # At most current_limit should succeed
        successful = sum(1 for r in results if r)
        assert successful <= sem.current_limit, (
            f"Got {successful} permits but limit is {sem.current_limit}"
        )
        # Release whatever we acquired
        for _ in range(successful):
            sem._semaphore.release()

    @pytest.mark.asyncio
    async def test_grow_still_works(self):
        """Growing the semaphore still works after shrinking."""
        from core.runtime.resilience import AdaptiveSemaphore

        sem = AdaptiveSemaphore(min_limit=1, max_limit=10, target_latency_ms=100)
        assert sem.current_limit == 1

        # Fast calls -> should grow
        async with sem:
            await asyncio.sleep(0.01)
        assert sem.current_limit == 2

        async with sem:
            await asyncio.sleep(0.01)
        assert sem.current_limit == 3

    @pytest.mark.asyncio
    async def test_no_deadlock_on_shrink(self):
        """Shrinking must not cause deadlocks — tasks must complete."""
        from core.runtime.resilience import AdaptiveSemaphore

        sem = AdaptiveSemaphore(min_limit=1, max_limit=5, target_latency_ms=50)

        # Grow to 5
        for _ in range(20):
            async with sem:
                await asyncio.sleep(0.005)

        # Now cause shrink with slow calls — must not deadlock
        completed = []

        async def slow_task(i):
            async with sem:
                await asyncio.sleep(0.15)
                completed.append(i)

        # Run 5 slow tasks concurrently — all must complete
        tasks = [asyncio.create_task(slow_task(i)) for i in range(5)]
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=10.0)
        assert len(completed) == 5

    @pytest.mark.asyncio
    async def test_drain_count_correctness(self):
        """The drain count mechanism correctly absorbs permits."""
        from core.runtime.resilience import AdaptiveSemaphore

        sem = AdaptiveSemaphore(min_limit=1, max_limit=10, target_latency_ms=50)

        # Grow
        for _ in range(5):
            async with sem:
                await asyncio.sleep(0.005)

        pre_shrink_limit = sem.current_limit

        # Trigger shrink
        async with sem:
            await asyncio.sleep(0.2)

        if sem.current_limit < pre_shrink_limit:
            # drain_count should have been set and may still be positive
            # or may have been consumed by the release in __aexit__
            assert sem._drain_count >= 0, "Drain count must never go negative"


# ═══════════════════════════════════════════════════════════════════════════
# A6 — Config writes: deferred persistence for non-critical state
# ═══════════════════════════════════════════════════════════════════════════

class TestA6ConfigWrites:
    """Config must persist critical keys immediately and defer others."""

    def test_critical_key_persists_immediately(self, tmp_path):
        """Stage changes must write models.toml immediately."""
        from core.config import _CRITICAL_STATE_KEYS

        # Patch CONFIG_DIR before importing Config class
        with patch("core.config.CONFIG_DIR", tmp_path):
            # Create minimal required files
            (tmp_path / "settings.toml").write_bytes(b"")
            (tmp_path / "sources.toml").write_bytes(b"")
            (tmp_path / "models.toml").write_bytes(b"")

            from core.config import Config
            cfg = Config()

            # Set a critical key
            cfg.set_module_state("test_mod", "stage", "shadow")
            assert not cfg._models_dirty, "Critical key should not leave dirty flag"

            # Verify it was written to disk
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib
            with open(tmp_path / "models.toml", "rb") as f:
                persisted = tomllib.load(f)
            assert persisted["test_mod"]["stage"] == "shadow"

    def test_non_critical_key_deferred(self, tmp_path):
        """query_count changes must NOT write immediately."""
        with patch("core.config.CONFIG_DIR", tmp_path):
            (tmp_path / "settings.toml").write_bytes(b"")
            (tmp_path / "sources.toml").write_bytes(b"")
            (tmp_path / "models.toml").write_bytes(b"")

            from core.config import Config
            cfg = Config()

            cfg.set_module_state("test_mod", "query_count", 42)
            assert cfg._models_dirty, "Non-critical key should set dirty flag"

            # In-memory state should be updated
            assert cfg.get_module_state("test_mod")["query_count"] == 42

    def test_flush_persists_dirty_state(self, tmp_path):
        """flush() must write deferred state to disk."""
        with patch("core.config.CONFIG_DIR", tmp_path):
            (tmp_path / "settings.toml").write_bytes(b"")
            (tmp_path / "sources.toml").write_bytes(b"")
            (tmp_path / "models.toml").write_bytes(b"")

            from core.config import Config
            cfg = Config()
            cfg.set_module_state("test_mod", "query_count", 99)
            assert cfg._models_dirty

            cfg.flush()
            assert not cfg._models_dirty

            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib
            with open(tmp_path / "models.toml", "rb") as f:
                persisted = tomllib.load(f)
            assert persisted["test_mod"]["query_count"] == 99

    def test_critical_keys_defined(self):
        """Verify the critical keys set exists and contains expected entries."""
        from core.config import _CRITICAL_STATE_KEYS
        assert "stage" in _CRITICAL_STATE_KEYS
        assert "bootstrap_model" in _CRITICAL_STATE_KEYS
        # Non-critical keys should NOT be in the set
        assert "query_count" not in _CRITICAL_STATE_KEYS
        assert "maturity_score" not in _CRITICAL_STATE_KEYS


# ═══════════════════════════════════════════════════════════════════════════
# A7 — System controller: _open_app rejects shell metacharacters
# ═══════════════════════════════════════════════════════════════════════════

class TestA7SystemController:
    """_open_app must validate input and prevent shell injection."""

    def test_rejects_shell_metacharacters(self):
        """Targets with shell metacharacters must be rejected."""
        from modules.system_ctrl.module import _validate_open_target

        dangerous_inputs = [
            "notepad & del /f /q C:\\",
            "calc | rm -rf /",
            "app; malicious",
            "$(whoami)",
            "`id`",
            "file(name)",
            "target{inject}",
            "file\nmalicious",
            "app\rinjection",
            "test'quote",
            'test"double',
            "app<redirect>",
            "app!bang",
        ]
        for target in dangerous_inputs:
            with pytest.raises(ValueError, match="unsafe characters|Empty target"):
                _validate_open_target(target)

    def test_rejects_empty_target(self):
        from modules.system_ctrl.module import _validate_open_target
        with pytest.raises(ValueError, match="Empty target"):
            _validate_open_target("")
        with pytest.raises(ValueError, match="Empty target"):
            _validate_open_target("   ")

    def test_rejects_flag_like_target(self):
        from modules.system_ctrl.module import _validate_open_target
        with pytest.raises(ValueError, match="must not start with"):
            _validate_open_target("-malicious-flag")

    def test_accepts_normal_targets(self):
        """Legitimate file paths and URLs must be accepted."""
        from modules.system_ctrl.module import _validate_open_target

        safe_inputs = [
            "notepad",
            "https://example.com",
            "http://localhost:8080/page",
            "C:/Users/test/file.txt",
            "/home/user/document.pdf",
            "my-app",
            "file.name.txt",
            "path/to/file",
        ]
        for target in safe_inputs:
            result = _validate_open_target(target)
            assert result == target.strip()

    def test_open_app_with_injection_raises(self):
        """_open_app must raise ValueError for malicious input."""
        from modules.system_ctrl.module import _open_app

        # _open_app calls _validate_open_target which raises ValueError
        with pytest.raises(ValueError, match="unsafe characters"):
            _open_app("calc & del /q C:\\windows")

    def test_open_app_uses_safe_platform_apis(self):
        """Verify _open_app uses os.startfile on Windows (no shell),
        and subprocess without shell=True on other platforms."""
        import ast
        import inspect
        from modules.system_ctrl.module import _open_app

        source = inspect.getsource(_open_app)
        # Must use os.startfile for Windows (no shell involved)
        assert "os.startfile" in source, (
            "_open_app must use os.startfile on Windows"
        )
        # Must NOT pass shell=True to any subprocess call.
        # Use AST parsing to avoid false positives from comments/docstrings.
        # Dedent source so ast.parse works on method bodies.
        import textwrap
        dedented = textwrap.dedent(source)
        tree = ast.parse(dedented)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "shell":
                        if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            pytest.fail(
                                "_open_app passes shell=True to a call — "
                                "this is a shell injection risk"
                            )


# ═══════════════════════════════════════════════════════════════════════════
# A8 — Configuration endpoint: key allowlist validation
# ═══════════════════════════════════════════════════════════════════════════

class TestA8ConfigEndpoint:
    """PUT /config must reject unknown/immutable keys."""

    @pytest.mark.asyncio
    async def test_allowed_key_accepted(self):
        from interface.api import MUTABLE_CONFIG_KEYS
        # Verify the allowlist exists and has entries
        assert len(MUTABLE_CONFIG_KEYS) > 0
        assert "global.ollama_host" in MUTABLE_CONFIG_KEYS
        assert "global.debug" in MUTABLE_CONFIG_KEYS

    @pytest.mark.asyncio
    async def test_unknown_key_rejected(self):
        from fastapi.testclient import TestClient
        from interface.api import app

        client = TestClient(app)
        response = client.put(
            "/config",
            json={"global.secret_key": "evil"},
            headers={"X-OCBrain-Local": "1"},
        )
        assert response.status_code == 400
        body = response.json()
        assert "Rejected" in body["detail"]
        assert "global.secret_key" in body["detail"]

    @pytest.mark.asyncio
    async def test_mixed_keys_all_rejected(self):
        """If ANY key is invalid, the entire request is rejected."""
        from fastapi.testclient import TestClient
        from interface.api import app

        client = TestClient(app)
        response = client.put(
            "/config",
            json={"global.debug": True, "evil.key": "bad"},
            headers={"X-OCBrain-Local": "1"},
        )
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# A9 — CSRF protection: mutating endpoints require header
# ═══════════════════════════════════════════════════════════════════════════

class TestA9CSRFProtection:
    """Mutating requests must include X-OCBrain-Local header."""

    def test_post_without_header_rejected(self):
        from fastapi.testclient import TestClient
        from interface.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"query": "test"},
            # No X-OCBrain-Local header
        )
        assert response.status_code == 403
        assert "X-OCBrain-Local" in response.json()["detail"]

    def test_put_without_header_rejected(self):
        from fastapi.testclient import TestClient
        from interface.api import app

        client = TestClient(app)
        response = client.put(
            "/config",
            json={"global.debug": True},
        )
        assert response.status_code == 403

    def test_get_without_header_allowed(self):
        """GET requests must work without the CSRF header."""
        from fastapi.testclient import TestClient
        from interface.api import app

        client = TestClient(app)
        response = client.get("/config")
        # Should not be 403 — might be 500 if orchestrator not initialized,
        # but definitely not a CSRF rejection
        assert response.status_code != 403

    def test_post_with_header_passes_csrf(self):
        """Requests with the header must pass the CSRF check."""
        from fastapi.testclient import TestClient
        from interface.api import app

        client = TestClient(app)
        response = client.post(
            "/query",
            json={"query": "test"},
            headers={"X-OCBrain-Local": "1"},
        )
        # May fail for other reasons (no orchestrator), but not CSRF
        assert response.status_code != 403

    def test_docs_endpoint_exempt(self):
        """OpenAPI docs must be accessible without the header."""
        from fastapi.testclient import TestClient
        from interface.api import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
