"""
tests/test_execution_runtime.py — K2.1 Integration Tests

Tests for:
    - CancellationToken
    - WorkingMemory
    - ExecutionContext
    - WorkerRegistry
    - ExecutionRuntime
    - Composition root wiring
    - Production path reachability

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §7 — Execution Model.
    K2.1 success criteria verification.
"""

import asyncio
import pytest
import uuid

from core.runtime.cancellation import CancellationToken
from core.runtime.working_memory import WorkingMemory
from core.runtime.execution_context import ExecutionContext
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.execution_runtime import ExecutionRuntime
from core.workers.base import (
    AbstractCognitiveWorker,
    WorkerContext,
    WorkerResult,
    WorkerState,
)
from core.governance.governance_kernel import (
    GovernanceKernel,
    GovernanceAction,
    GovernanceResult,
    GovernanceVerdict,
    get_governance_kernel,
)
from core.events.event_stream import EventStream, get_event_stream


# ── Test Fixtures ─────────────────────────────────────────────────────────────


class EchoWorker(AbstractCognitiveWorker):
    """Test worker that echoes query back."""
    worker_type = "EchoWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(
            success=True,
            output=f"echo: {context.query}",
        )


class FailingWorker(AbstractCognitiveWorker):
    """Test worker that always raises."""
    worker_type = "FailingWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        raise RuntimeError("deliberate failure")


class SlowWorker(AbstractCognitiveWorker):
    """Test worker that sleeps, checking cancellation."""
    worker_type = "SlowWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        for i in range(10):
            if self.is_cancelled:
                return WorkerResult(success=False, error="cancelled")
            await asyncio.sleep(0.01)
        return WorkerResult(success=True, output="completed")


class BadConstructorWorker(AbstractCognitiveWorker):
    """Test worker whose constructor fails."""
    worker_type = "BadConstructorWorker"

    def __init__(self, **kwargs):
        raise ValueError("constructor exploded")

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(success=True)


# ── CancellationToken Tests ───────────────────────────────────────────────────


class TestCancellationToken:
    def test_initial_state(self):
        token = CancellationToken()
        assert not token.is_cancelled
        assert token.reason == ""

    def test_cancel(self):
        token = CancellationToken()
        token.cancel("test reason")
        assert token.is_cancelled
        assert token.reason == "test reason"

    def test_cancel_idempotent(self):
        token = CancellationToken()
        token.cancel("first")
        token.cancel("second")
        assert token.is_cancelled
        assert token.reason == "first"  # First reason preserved

    @pytest.mark.asyncio
    async def test_wait_cancelled(self):
        token = CancellationToken()
        token.cancel()
        result = await token.wait(timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_timeout(self):
        token = CancellationToken()
        result = await token.wait(timeout=0.01)
        assert result is False


# ── WorkingMemory Tests ───────────────────────────────────────────────────────


class TestWorkingMemory:
    def test_set_and_get(self):
        wm = WorkingMemory()
        wm.set("key", "value")
        assert wm.get("key") == "value"

    def test_get_default(self):
        wm = WorkingMemory()
        assert wm.get("missing", "default") == "default"

    def test_has(self):
        wm = WorkingMemory()
        wm.set("key", "value")
        assert wm.has("key")
        assert not wm.has("missing")

    def test_remove(self):
        wm = WorkingMemory()
        wm.set("key", "value")
        removed = wm.remove("key")
        assert removed == "value"
        assert not wm.has("key")

    def test_clear(self):
        wm = WorkingMemory()
        wm.set("a", 1)
        wm.set("b", 2)
        wm.clear()
        assert len(wm) == 0

    def test_snapshot(self):
        wm = WorkingMemory()
        wm.set("a", 1)
        snap = wm.snapshot()
        assert snap == {"a": 1}
        # Snapshot is independent
        snap["b"] = 2
        assert not wm.has("b")

    def test_keys(self):
        wm = WorkingMemory()
        wm.set("x", 1)
        wm.set("y", 2)
        assert sorted(wm.keys()) == ["x", "y"]


# ── ExecutionContext Tests ────────────────────────────────────────────────────


class TestExecutionContext:
    def test_default_construction(self):
        ctx = ExecutionContext()
        assert ctx.request_id  # UUID generated
        assert ctx.session_id  # UUID generated
        assert isinstance(ctx.working_memory, WorkingMemory)
        assert isinstance(ctx.cancellation_token, CancellationToken)

    def test_task_id_alias(self):
        ctx = ExecutionContext(request_id="req-123")
        assert ctx.task_id == "req-123"

    def test_query_alias(self):
        ctx = ExecutionContext(metadata={"query": "hello"})
        assert ctx.query == "hello"

    def test_recursion_depth_alias(self):
        ctx = ExecutionContext(governance_state={"recursion_depth": 3})
        assert ctx.recursion_depth == 3

    def test_to_worker_context(self):
        ctx = ExecutionContext(
            request_id="req-456",
            workflow_id="wf-1",
            parent_worker_id="parent-1",
            governance_state={"recursion_depth": 2},
            metadata={"query": "test query", "parameters": {"p": 1}},
        )
        wc = ctx.to_worker_context()
        assert isinstance(wc, WorkerContext)
        assert wc.task_id == "req-456"
        assert wc.query == "test query"
        assert wc.recursion_depth == 2
        assert wc.workflow_id == "wf-1"
        assert wc.parent_worker_id == "parent-1"
        assert wc.parameters == {"p": 1}


# ── WorkerRegistry Tests ─────────────────────────────────────────────────────


class TestWorkerRegistry:
    def test_register_and_get(self):
        registry = WorkerRegistry()
        registry.register(EchoWorker)
        assert registry.get("EchoWorker") is EchoWorker

    def test_get_unknown(self):
        registry = WorkerRegistry()
        assert registry.get("NonExistent") is None

    def test_duplicate_registration_raises(self):
        registry = WorkerRegistry()
        registry.register(EchoWorker)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(EchoWorker)

    def test_list_types(self):
        registry = WorkerRegistry()
        registry.register(EchoWorker)
        registry.register(FailingWorker)
        assert sorted(registry.list_types()) == ["EchoWorker", "FailingWorker"]

    def test_stats(self):
        registry = WorkerRegistry()
        registry.register(EchoWorker)
        stats = registry.stats()
        assert stats["EchoWorker"] == "EchoWorker"


# ── ExecutionRuntime Tests ────────────────────────────────────────────────────


class TestExecutionRuntime:
    """Tests for ExecutionRuntime.invoke().

    Architecture:
        K2.1 success criteria:
        1. invoke() returns WorkerResult for success and failure
        2. Unknown worker type returns error (never raises)
        3. CancellationToken propagation
        4. WorkingMemory cleanup
        5. Governance evaluation fires (template method)
        6. Events emitted for lifecycle
        7. Failures contained as WorkerResult(success=False)
    """

    def _make_runtime(self, *worker_classes):
        registry = WorkerRegistry()
        for cls in worker_classes:
            registry.register(cls)
        return ExecutionRuntime(
            worker_registry=registry,
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        """invoke() returns successful WorkerResult."""
        runtime = self._make_runtime(EchoWorker)
        result = await runtime.invoke("EchoWorker", query="hello world")
        assert result.success is True
        assert result.output == "echo: hello world"
        assert result.duration_ms > 0
        assert result.metadata["worker_type"] == "EchoWorker"
        assert result.metadata["request_id"]  # UUID present

    @pytest.mark.asyncio
    async def test_invoke_unknown_type(self):
        """invoke() with unknown type returns failure, never raises."""
        runtime = self._make_runtime(EchoWorker)
        result = await runtime.invoke("NonExistent", query="test")
        assert result.success is False
        assert "Unknown worker type" in result.error

    @pytest.mark.asyncio
    async def test_invoke_failing_worker(self):
        """Worker exception is contained as WorkerResult(success=False)."""
        runtime = self._make_runtime(FailingWorker)
        result = await runtime.invoke("FailingWorker", query="test")
        assert result.success is False
        assert "deliberate failure" in result.error

    @pytest.mark.asyncio
    async def test_invoke_bad_constructor(self):
        """Worker construction failure is contained."""
        runtime = self._make_runtime(BadConstructorWorker)
        result = await runtime.invoke("BadConstructorWorker", query="test")
        assert result.success is False
        assert "constructor exploded" in result.error

    @pytest.mark.asyncio
    async def test_invoke_with_context(self):
        """invoke() with pre-built ExecutionContext."""
        runtime = self._make_runtime(EchoWorker)
        ctx = ExecutionContext(
            request_id="custom-req-id",
            metadata={"query": "custom context query"},
        )
        result = await runtime.invoke("EchoWorker", context=ctx)
        assert result.success is True
        assert result.output == "echo: custom context query"
        assert result.metadata["request_id"] == "custom-req-id"

    @pytest.mark.asyncio
    async def test_working_memory_cleanup(self):
        """WorkingMemory is cleared after execution."""
        runtime = self._make_runtime(EchoWorker)
        ctx = ExecutionContext(metadata={"query": "test"})
        ctx.working_memory.set("pre_data", "should be cleared")
        await runtime.invoke("EchoWorker", context=ctx)
        assert len(ctx.working_memory) == 0

    @pytest.mark.asyncio
    async def test_stats(self):
        """Runtime stats track invocations and failures."""
        runtime = self._make_runtime(EchoWorker, FailingWorker)
        await runtime.invoke("EchoWorker", query="test")
        await runtime.invoke("FailingWorker", query="test")
        stats = runtime.stats()
        assert stats["total_invocations"] == 2
        assert stats["total_failures"] >= 1

    @pytest.mark.asyncio
    async def test_never_raises(self):
        """ExecutionRuntime.invoke() must NEVER raise."""
        runtime = self._make_runtime(FailingWorker, BadConstructorWorker)
        # All of these must return WorkerResult, never raise
        r1 = await runtime.invoke("FailingWorker", query="test")
        r2 = await runtime.invoke("BadConstructorWorker", query="test")
        r3 = await runtime.invoke("NonExistent", query="test")
        assert not r1.success
        assert not r2.success
        assert not r3.success


# ── MemoryCuratorWorker Integration ───────────────────────────────────────────


class TestMemoryCuratorIntegration:
    """Tests that MemoryCuratorWorker can be invoked through ExecutionRuntime.

    K2.1 success criterion:
        ExecutionRuntime.invoke("MemoryCuratorWorker", context)
        successfully executes MemoryCuratorWorker._run().
    """

    @pytest.mark.asyncio
    async def test_curator_through_runtime(self):
        """MemoryCuratorWorker executes through ExecutionRuntime."""
        from core.workers.curator import MemoryCuratorWorker

        registry = WorkerRegistry()
        registry.register(MemoryCuratorWorker)
        runtime = ExecutionRuntime(
            worker_registry=registry,
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )
        # invoke without registering with memory — curator handles
        # unregistered state gracefully (returns success=False or
        # runs with empty scan).
        result = await runtime.invoke(
            "MemoryCuratorWorker",
            query="curate",
        )
        # The worker executes (governance passes, events emitted).
        # It may succeed with 0 entries scanned, or fail gracefully
        # because no memory is registered — both are valid.
        assert isinstance(result, WorkerResult)
        assert result.duration_ms > 0
        assert result.metadata.get("worker_type") == "MemoryCuratorWorker"


# ── Composition Root Wiring Tests ─────────────────────────────────────────────


class TestCompositionRootContracts:
    """Verify that the types used in main.py are importable and constructable.

    These are NOT startup tests (we don't run main.py), but they verify
    the contracts that main.py depends on.
    """

    def test_worker_registry_accepts_curator(self):
        from core.workers.curator import MemoryCuratorWorker
        registry = WorkerRegistry()
        registry.register(MemoryCuratorWorker)
        assert registry.get("MemoryCuratorWorker") is MemoryCuratorWorker

    def test_execution_runtime_constructable(self):
        registry = WorkerRegistry()
        runtime = ExecutionRuntime(
            worker_registry=registry,
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )
        assert runtime.stats()["total_invocations"] == 0

    def test_execution_context_to_worker_context_roundtrip(self):
        ctx = ExecutionContext(
            request_id="test-id",
            metadata={"query": "hello", "parameters": {}},
            governance_state={"recursion_depth": 0},
        )
        wc = ctx.to_worker_context()
        assert wc.task_id == "test-id"
        assert wc.query == "hello"
        assert wc.recursion_depth == 0


# ── Governance Integration ────────────────────────────────────────────────────


class TestGovernanceIntegration:
    """Verify governance evaluation fires before _run() via template method."""

    @pytest.mark.asyncio
    async def test_governance_fires_before_run(self):
        """The template method in Worker.execute() evaluates governance
        before calling _run(). This test verifies EchoWorker passes
        governance (default governors approve standard actions)."""
        runtime = TestExecutionRuntime._make_runtime(
            TestExecutionRuntime(), EchoWorker)
        result = await runtime.invoke("EchoWorker", query="gov test")
        assert result.success is True
        # If governance had rejected, result.success would be False
        # and result.error would contain "Governance rejected"

    @pytest.mark.asyncio
    async def test_governance_fires_standalone(self):
        """Direct worker.execute() still fires governance."""
        worker = EchoWorker(
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )
        wc = WorkerContext(query="direct test")
        result = await worker.execute(wc)
        assert result.success is True
        assert result.output == "echo: direct test"


# ── Backward Compatibility ────────────────────────────────────────────────────


class TestBackwardCompatibility:
    """Verify legacy code paths still work."""

    def test_orchestrator_without_execution_runtime(self):
        """Orchestrator can be constructed without execution_runtime
        (backward compatibility for existing tests)."""
        from core.orchestrator import Orchestrator
        from core.context import ContextMemory
        from core.model_router import ModelRouter
        from core.memory.unified_memory import UnifiedMemory

        # This should NOT raise — execution_runtime is Optional
        # We just verify the constructor signature accepts it
        # (actual construction requires valid dependencies)
        import inspect
        sig = inspect.signature(Orchestrator.__init__)
        assert "execution_runtime" in sig.parameters
        param = sig.parameters["execution_runtime"]
        assert param.default is None  # Optional, defaults to None
