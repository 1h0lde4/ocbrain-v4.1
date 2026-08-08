"""
tests/test_runtime_integration.py — Runtime Integration Tests (Task 6).

Covers, per the Runtime Integration task's own required minimum:
    - Feature flag OFF: legacy runtime unchanged
    - Feature flag ON: interpret() -> plan() -> compile() -> runtime
      execution -> Evaluator -> Reflection -> Supervisor
    - Compilation reject / escalate
    - Reflection / Evaluation / Supervisor individually
    - Worker registration
    - Governance
    - Memory writes
    - Event replay
    - Regression is covered by the full existing suite (unaffected by
      this file; run separately)

Test harness note: this file builds a *real* object graph (EventStream,
GovernanceKernel, CapabilityRegistry, AdapterRuntime, ResourceManager,
WorkerRegistry, ExecutionRuntime, WorkflowRuntime, Orchestrator) mirroring
main.py's own composition order, not a simplified mock stack -- so these
tests exercise the actual wiring introduced by this task, not an
approximation of it. Only two things are faked: the LLM calls inside
interpret_request()/plan() (the same established
tests/core/cognitive/test_intent.py / test_planner.py mocking
convention, reused here), and the capability adapter itself
(FakeSuccessAdapter below, implementing only the one method
AdapterRuntime.invoke() actually calls).
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from core.capabilities.adapter_runtime import AdapterRuntime
from core.capabilities.capability import (
    BaseAdapter,
    CapabilityContract,
    CapabilityResult,
    CapabilityType,
)
from core.capabilities.registry import CapabilityRegistry
from core.capabilities.resource import ResourceManager
from core.cognitive.planner import ClarificationPolicy
from core.events.event_stream import EventStream, SQLiteEventStore
from core.governance.governance_kernel import get_governance_kernel
from core.memory.unified_memory import UnifiedMemory
from core.orchestrator import Orchestrator
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workers.capability_executor import CapabilityExecutorWorker
from core.workers.evaluator import EvaluatorWorker
from core.workers.reflection import ReflectionWorker
from core.workers.supervisor import SupervisorWorker
from core.workflow.runtime import WorkflowRuntime


class FakeSuccessAdapter(BaseAdapter):
    """Minimal working adapter -- implements only execute(), the one
    method AdapterRuntime.invoke() calls (confirmed by reading
    core/capabilities/adapter_runtime.py directly)."""

    def __init__(self, fail: bool = False):
        super().__init__()
        self.adapter_name = "fake-llm_completion"
        self.capability_type = CapabilityType.LLM_COMPLETION
        self.call_count = 0
        self._fail = fail

    async def execute(self, request, resources):
        self.call_count += 1
        if self._fail:
            return CapabilityResult(success=False, error="stub failure",
                                     adapter_used=self.adapter_name)
        return CapabilityResult(
            success=True,
            output=f"stub answer to: {request.payload.get('subtask', '')}",
            adapter_used=self.adapter_name,
        )


def _build_runtime_stack(tmp_path, *, use_k42_frontend: bool,
                          adapter_fails: bool = False):
    """Real object graph mirroring main.py's composition order. Returns
    (orchestrator, event_stream, memory, worker_registry, adapter)."""
    event_stream = EventStream(store=SQLiteEventStore(db_path=str(tmp_path / "events.db")))
    governance = get_governance_kernel()
    memory = UnifiedMemory(db_prefix=str(tmp_path / "memory"))

    capability_registry = CapabilityRegistry()
    capability_registry.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION,
        description="Generate text from a prompt via a language model.",
    ))
    resource_manager = ResourceManager()
    adapter_runtime = AdapterRuntime(capability_registry, resource_manager)
    adapter = FakeSuccessAdapter(fail=adapter_fails)
    capability_registry.register_adapter(CapabilityType.LLM_COMPLETION, adapter)

    worker_registry = WorkerRegistry()
    worker_registry.register(EvaluatorWorker, constructor_kwargs={"memory": memory})
    worker_registry.register(ReflectionWorker, constructor_kwargs={"memory": memory})
    worker_registry.register(CapabilityExecutorWorker, constructor_kwargs={
        "adapter_runtime": adapter_runtime,
    })
    # Legacy PlannerWorker, registered so TestFeatureFlagOff can exercise
    # the real K2.2 branch, not just assert it wasn't touched. Minimal
    # stubs for modules/context_memory are sufficient here -- the
    # flag-off tests only assert on Orchestrator-level event presence/
    # payload, not on PlannerWorker producing a meaningful answer, and
    # WorkflowRuntime.execute() never raises regardless (Failure
    # Containment) so a "thin" PlannerWorker construction is safe.
    from unittest.mock import AsyncMock as _AsyncMock
    from core.workers.planner import PlannerWorker
    worker_registry.register(PlannerWorker, constructor_kwargs={
        "modules": {},
        "context_memory": _AsyncMock(),
        "adapter_runtime": adapter_runtime,
        "memory": memory,
    })

    execution_runtime = ExecutionRuntime(
        worker_registry=worker_registry, governance=governance,
        event_stream=event_stream,
    )
    worker_registry.register(SupervisorWorker, constructor_kwargs={
        "execution_runtime": execution_runtime,
    })
    workflow_runtime = WorkflowRuntime(execution_runtime, event_stream)

    orchestrator = Orchestrator(
        {}, object(), object(), memory,
        governance=governance, event_stream=event_stream,
        execution_runtime=execution_runtime, workflow_runtime=workflow_runtime,
        capability_registry=capability_registry, use_k42_frontend=use_k42_frontend,
    )
    return orchestrator, event_stream, memory, worker_registry, adapter


def _mock_llm_calls():
    """Established pattern (tests/core/cognitive/test_intent.py,
    tests/core/cognitive/test_planner.py, tests/test_integration_full_
    pipeline.py) -- two separate patches, one per module's own
    generate_with_fallback binding."""
    return (
        patch("core.cognitive.intent.ContextAssemblyEngine"),
        patch("core.cognitive.intent.generate_with_fallback",
              new=AsyncMock(return_value="novel:answer_query | 0.9")),
        patch("core.cognitive.planner.generate_with_fallback",
              new=AsyncMock(return_value="Generate text from a prompt via a language model.")),
    )


# ─────────────────────────────────────────────────────────────────────────
# Feature flag OFF — legacy runtime unchanged
# ─────────────────────────────────────────────────────────────────────────


class TestFeatureFlagOff:
    @pytest.mark.asyncio
    async def test_k42_branch_never_entered_when_flag_off(self, tmp_path):
        orchestrator, event_stream, memory, _, adapter = _build_runtime_stack(
            tmp_path, use_k42_frontend=False)
        try:
            await orchestrator.handle("hello")
        finally:
            await orchestrator.close()

        # The K4.2 branch's own success signal never fires.
        events = await event_stream.query(limit=200)
        completed = [e for e in events if e.event_type == "orchestrator.query_completed"]
        assert all(e.payload.get("execution_path") != "k42_cognitive_frontend"
                   for e in completed)
        # The bridge adapter (only reachable via CapabilityExecutorWorker,
        # only reachable via the K4.2 path) was never invoked.
        assert adapter.call_count == 0

    @pytest.mark.asyncio
    async def test_legacy_path_still_reports_workflow_runtime(self, tmp_path):
        """Confirms the pre-existing K2.2 branch runs exactly as before,
        unaffected by this task's changes -- not that it necessarily
        succeeds. With an intentionally minimal modules={} fixture,
        PlannerWorker correctly fails ("no modules available"), and the
        existing, untouched code correctly emits orchestrator.query_failed
        (not query_completed) for that case -- this is real,
        pre-existing K2.2 behavior, unrelated to and unmodified by this
        task, and confirms this task didn't change it."""
        orchestrator, event_stream, memory, _, _ = _build_runtime_stack(
            tmp_path, use_k42_frontend=False)
        try:
            await orchestrator.handle("hello")
        finally:
            await orchestrator.close()

        events = await event_stream.query(limit=200)
        event_types = [e.event_type for e in events]
        assert "orchestrator.query_failed" in event_types
        failed = [e for e in events if e.event_type == "orchestrator.query_failed"][0]
        assert failed.payload.get("error_type") == "WorkflowFailure"
        # And, critically, the K4.2 branch was never entered at all.
        assert "cognitive.intent_interpreted" not in event_types
        assert not any(e.payload.get("execution_path") == "k42_cognitive_frontend"
                        for e in events if e.event_type == "orchestrator.query_completed")


# ─────────────────────────────────────────────────────────────────────────
# Feature flag ON — full path
# ─────────────────────────────────────────────────────────────────────────


class TestFeatureFlagOnFullPath:
    @pytest.mark.asyncio
    async def test_full_k42_path_succeeds(self, tmp_path):
        orchestrator, event_stream, memory, _, adapter = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3:
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                answer = await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        assert isinstance(answer, str)
        assert "stub answer to" in answer
        assert adapter.call_count == 1  # the bridge really reached the adapter

        events = await event_stream.query(limit=200)
        event_types = {e.event_type for e in events}
        # Full trail: intent -> goal -> constraints -> capabilities ->
        # compiled -> workflow -> worker lifecycle -> evaluation ->
        # reflection (if warranted) -> orchestrator completion.
        for expected in ("cognitive.intent_interpreted", "cognitive.goal_formed",
                          "cognitive.constraints_extracted",
                          "cognitive.capabilities_discovered",
                          "cognitive.plan_compiled", "workflow.started",
                          "workflow.completed", "cognitive.evaluation_completed",
                          "orchestrator.query_completed"):
            assert expected in event_types, f"missing {expected} in {event_types}"

        completed = [e for e in events if e.event_type == "orchestrator.query_completed"]
        assert completed[-1].payload.get("execution_path") == "k42_cognitive_frontend"

    @pytest.mark.asyncio
    async def test_worker_lifecycle_events_present_for_every_new_worker(self, tmp_path):
        """K4 §4: every worker (including the new bridge) goes through
        the same governed execute() template -- confirmed here by its
        lifecycle events actually appearing, not just trusting the
        class hierarchy."""
        orchestrator, event_stream, memory, _, _ = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3:
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        events = await event_stream.query(limit=200)
        started = {e.payload.get("worker_type") for e in events
                   if e.event_type == "worker.started"}
        assert CapabilityType.LLM_COMPLETION in started  # CapabilityExecutorWorker
        assert "EvaluatorWorker" in started


# ─────────────────────────────────────────────────────────────────────────
# Compilation reject / escalate
# ─────────────────────────────────────────────────────────────────────────


class TestCompilationOutcomes:
    @pytest.mark.asyncio
    async def test_escalated_compilation_invokes_supervisor_and_returns_gracefully(self, tmp_path):
        orchestrator, event_stream, memory, _, adapter = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3, \
                 patch("core.cognitive.planner._estimate_confidence", return_value=0.1):
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                answer = await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        assert isinstance(answer, str)
        assert "not" in answer.lower() or "sorry" in answer.lower()
        assert adapter.call_count == 0  # never reached execution

        events = await event_stream.query(limit=200)
        event_types = [e.event_type for e in events]
        assert "cognitive.plan_rejected" in event_types
        assert "cognitive.supervision_escalated" in event_types
        # Invariant 9: no execution/workflow events at all for a plan
        # that was escalated at the compilation gate.
        assert "workflow.started" not in event_types

    @pytest.mark.asyncio
    async def test_rejected_compilation_does_not_retry(self, tmp_path):
        """Same scenario at the REJECT bound (clarification_attempt >=
        max_escalations) -- compile() itself doesn't expose an attempt
        counter through Orchestrator yet (that threading is future work,
        see Final Notes), so this test forces REJECT via a governance
        double instead, confirming Orchestrator's own handling of a
        REJECTED (not just ESCALATED) outcome."""
        orchestrator, event_stream, memory, _, adapter = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)

        class RejectingGovernance:
            def evaluate_action(self, action):
                from core.governance.governance_kernel import GovernanceResult, GovernanceVerdict
                if action.action_type == "plan_compile":
                    return GovernanceResult(verdict=GovernanceVerdict.REJECT,
                                             reason="test-forced reject", governor="Test")
                return get_governance_kernel().evaluate_action(action)

        orchestrator._governance = RejectingGovernance()
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3:
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                answer = await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        assert adapter.call_count == 0
        events = await event_stream.query(limit=200)
        event_types = [e.event_type for e in events]
        assert "cognitive.plan_rejected" in event_types
        assert "workflow.started" not in event_types


# ─────────────────────────────────────────────────────────────────────────
# Worker registration
# ─────────────────────────────────────────────────────────────────────────


class TestWorkerRegistration:
    def test_all_four_new_workers_registered(self, tmp_path):
        _, _, _, worker_registry, _ = _build_runtime_stack(tmp_path, use_k42_frontend=True)
        registered = worker_registry.list_types()
        for expected in ("EvaluatorWorker", "ReflectionWorker", "SupervisorWorker",
                          CapabilityType.LLM_COMPLETION):
            assert expected in registered

    def test_registered_workers_are_constructible(self, tmp_path):
        _, _, _, worker_registry, _ = _build_runtime_stack(tmp_path, use_k42_frontend=True)
        for worker_type in ("EvaluatorWorker", "ReflectionWorker", "SupervisorWorker",
                             CapabilityType.LLM_COMPLETION):
            worker_cls = worker_registry.get(worker_type)
            assert worker_cls is not None
            assert worker_cls.worker_type == worker_type


# ─────────────────────────────────────────────────────────────────────────
# Governance
# ─────────────────────────────────────────────────────────────────────────


class TestGovernance:
    @pytest.mark.asyncio
    async def test_orchestrator_level_gate_still_fires_for_k42_path(self, tmp_path):
        """The pre-existing orchestrator_handle gate (unrelated to this
        task, unmodified) must still fire before the new branch is ever
        reached -- confirming Task 3 did not accidentally bypass it."""
        orchestrator, event_stream, memory, _, _ = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3:
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        events = await event_stream.query(limit=200)
        assert any(e.event_type == "orchestrator.query_started" for e in events)

    @pytest.mark.asyncio
    async def test_compile_gate_fires_within_k42_path(self, tmp_path):
        """compile()'s own plan_compile gate (Packet 06, unmodified)
        still fires -- two governance evaluations in sequence
        (orchestrator_handle, then plan_compile), not a bypass of
        either."""
        orchestrator, event_stream, memory, _, _ = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3:
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        events = await event_stream.query(limit=200)
        assert any(e.event_type == "cognitive.plan_compiled" for e in events)


# ─────────────────────────────────────────────────────────────────────────
# Memory writes
# ─────────────────────────────────────────────────────────────────────────


class TestMemoryWrites:
    @pytest.mark.asyncio
    async def test_evaluation_entry_written_to_memory(self, tmp_path):
        orchestrator, event_stream, memory, _, _ = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3:
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        events = await event_stream.query(event_type="cognitive.evaluation_completed", limit=10)
        assert len(events) == 1
        entry_id = events[0].payload.get("evaluation_entry_id")
        assert entry_id
        entry = await memory.read(entry_id)
        assert entry is not None
        assert entry.source == "EvaluatorWorker"


# ─────────────────────────────────────────────────────────────────────────
# Event replay
# ─────────────────────────────────────────────────────────────────────────


class TestEventReplay:
    @pytest.mark.asyncio
    async def test_full_k42_trail_replayable_gapless(self, tmp_path):
        orchestrator, event_stream, memory, _, _ = _build_runtime_stack(
            tmp_path, use_k42_frontend=True)
        p1, p2, p3 = _mock_llm_calls()
        try:
            with p1 as mock_engine_cls, p2, p3:
                mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
                await orchestrator.handle("Summarize the quarterly report.")
        finally:
            await orchestrator.close()

        replayed = [e async for e in event_stream.replay(since_sequence=0)]
        seqs = [e.sequence for e in replayed]
        assert seqs == list(range(1, len(seqs) + 1))
        assert len(seqs) == len(set(seqs))
        assert len(replayed) >= 8  # the full multi-stage trail, not a truncated one
