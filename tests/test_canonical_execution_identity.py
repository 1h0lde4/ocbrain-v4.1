from types import SimpleNamespace

import pytest

from core.capabilities import (
    AdapterRuntime,
    BaseAdapter,
    CapabilityContract,
    CapabilityRegistry,
    CapabilityResult,
    CapabilityType,
    ResourceManager,
)
from core.events.event_stream import EventStream, StreamEvent
from core.governance.governance_kernel import GovernanceVerdict
from core.orchestrator import Orchestrator
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workflow.runtime import WorkflowRuntime
from core.workers.planner import PlannerWorker


class _MemoryStore:
    def __init__(self):
        self.events = []

    async def append(self, event):
        sequence = len(self.events) + 1
        self.events.append(StreamEvent(**{**vars(event), "sequence": sequence}))
        return sequence

    async def query(self, **kwargs):
        return list(self.events)

    async def replay(self, since_sequence=0):
        for event in self.events:
            if event.sequence > since_sequence:
                yield event

    async def get_checkpoint(self, name):
        return None

    async def count(self):
        return len(self.events)

    async def close(self):
        return None


class _AllowGovernance:
    def evaluate_action(self, action):
        return SimpleNamespace(
            verdict=GovernanceVerdict.APPROVE, reason="", governor="test"
        )


class _AnswerAdapter(BaseAdapter):
    adapter_name = "identity_test_adapter"
    capability_type = CapabilityType.LLM_COMPLETION

    async def execute(self, request, resources):
        assert request.execution_id
        return CapabilityResult(success=True, output="correlated answer")


@pytest.mark.asyncio
async def test_one_execution_id_joins_orchestrator_workflow_capability_and_terminal_events(
    monkeypatch,
):
    event_stream = EventStream(_MemoryStore())
    governance = _AllowGovernance()

    capability_registry = CapabilityRegistry()
    capability_registry.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION,
        description="test completion",
    ))
    capability_registry.register_adapter(
        CapabilityType.LLM_COMPLETION, _AnswerAdapter()
    )
    adapter_runtime = AdapterRuntime(
        capability_registry, ResourceManager(), event_stream=event_stream
    )

    workers = WorkerRegistry()
    workers.register(PlannerWorker, constructor_kwargs={
        "modules": {"coding": object()},
        "context_memory": None,
        "adapter_runtime": adapter_runtime,
        "memory": None,
    })
    execution_runtime = ExecutionRuntime(
        workers, governance=governance, event_stream=event_stream
    )
    workflow_runtime = WorkflowRuntime(execution_runtime, event_stream=event_stream)
    orchestrator = Orchestrator(
        modules={},
        context=None,
        router=None,
        memory=None,
        governance=governance,
        event_stream=event_stream,
        workflow_runtime=workflow_runtime,
    )

    monkeypatch.setattr(
        "core.classifier_v3.classify",
        lambda query, top_k=2: [{"module": "coding", "confidence": 1.0}],
    )

    async def assemble_context(query):
        return ""

    monkeypatch.setattr(
        "core.memory.assembly.context_assembler.assemble_context",
        assemble_context,
    )
    monkeypatch.setattr(
        "core.merger.merge",
        lambda results, query: _async_answer(results[0].answer),
    )
    monkeypatch.setattr(
        "core.orchestrator.shadow_learner.record_interaction",
        lambda **kwargs: None,
    )

    execution_id = "exec-canonical-42"
    try:
        result = await orchestrator.handle_with_result(
            "explain the test system", execution_id=execution_id
        )
    finally:
        await orchestrator.close()

    assert result.success is True
    assert result.metadata["execution_id"] == execution_id
    correlated_events = [
        event for event in event_stream._store.events
        if event.payload.get("execution_id") == execution_id
    ]
    event_types = {event.event_type for event in correlated_events}
    assert {
        "orchestrator.query_started",
        "workflow.started",
        "adapter.invoked",
        "execution.completed",
        "orchestrator.query_completed",
    } <= event_types
    assert all(
        event.payload["execution_id"] == execution_id
        for event in correlated_events
    )


async def _async_answer(answer):
    return answer
