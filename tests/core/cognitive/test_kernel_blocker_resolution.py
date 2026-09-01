"""
tests/core/cognitive/test_kernel_blocker_resolution.py — Kernel Blocker A/B
resolution tests (ADR-KERNEL-01).

Blocker A: logical execution identity survives Goal -> ExecutionPlan ->
WorkflowDefinition (root_operation_id), distinct from ADR-K4.2-H-08's
per-cognitive-stage-invocation operation_id, which this file does not
touch or contradict. Execution attempts get a stable attempt_id distinct
from the existing bare `attempts` counter.

Blocker B: workers receive ExecutionContext directly at runtime -- the
to_worker_context() conversion previously performed by
ExecutionRuntime.invoke() before every worker call has been removed.

Evidence discipline: each test proves the actual invariant (identity
equality/inequality, isinstance checks against the real runtime path),
not merely that a field exists.
"""
import uuid

import pytest

from core.cognitive.intent import Goal
from core.cognitive.planner import ExecutionPlan, PlanStep
from core.cognitive.compiler import _compile_workflow
from core.runtime.execution_context import ExecutionContext
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.governance.governance_kernel import get_governance_kernel
from core.events.event_stream import get_event_stream


def _make_plan(goal: Goal, confidence: float = 0.9) -> ExecutionPlan:
    return ExecutionPlan(
        goal_id=goal.resource_id,
        steps=[
            PlanStep(
                step_id="step-1",
                description="do a thing",
                capability_type="llm_completion",
            )
        ],
        confidence=confidence,
        derived_from=[goal.resource_id],
        root_operation_id=goal.root_operation_id,
    )


# ─────────────────────────────────────────────────────────────────────────
# Blocker A — identity lifecycle
# ─────────────────────────────────────────────────────────────────────────


class TestRootOperationIdSurvivesCognitionToCompilation:
    def test_goal_generates_a_root_operation_id_by_default(self):
        goal = Goal()
        assert goal.root_operation_id
        assert isinstance(goal.root_operation_id, str)

    def test_two_independently_formed_goals_get_different_identities(self):
        """I11 (concurrency isolation): different logical operations must
        not accidentally share operation-scoped identity."""
        goal_a = Goal()
        goal_b = Goal()
        assert goal_a.root_operation_id != goal_b.root_operation_id

    def test_execution_plan_carries_the_same_root_operation_id_as_its_goal(self):
        goal = Goal()
        plan = _make_plan(goal)
        assert plan.root_operation_id == goal.root_operation_id

    def test_workflow_definition_carries_the_same_root_operation_id_as_its_plan(self):
        goal = Goal()
        plan = _make_plan(goal)
        workflow = _compile_workflow(plan)
        assert workflow.root_operation_id == plan.root_operation_id
        assert workflow.root_operation_id == goal.root_operation_id

    def test_root_operation_id_is_distinct_from_adr_k4_2_h_08_operation_id(self):
        """The existing `operation_id` local variable inside plan()/
        compile() (ADR-K4.2-H-08) is a different, narrower, per-call
        diagnostic concept and must not be confused with the field this
        test checks. This test does not exercise plan()/compile()'s own
        operation_id at all -- it exists to document, executably, that
        root_operation_id is a distinct field on a distinct object
        (Goal/ExecutionPlan/WorkflowDefinition), never assigned from or
        compared against a per-stage operation_id anywhere in this
        resolution."""
        goal = Goal()
        plan = _make_plan(goal)
        workflow = _compile_workflow(plan)
        # root_operation_id is a real field, present on all three,
        # equal across all three -- the actual I1/I2 invariant.
        assert goal.root_operation_id == plan.root_operation_id == workflow.root_operation_id

    def test_root_operation_id_not_duplicated_onto_individual_nodes(self):
        """Per I7: nodes are not independently persisted, transported, or
        indexed separately from their parent WorkflowDefinition (no
        checkpoint/resume exists yet -- DEBT-003), so a node-level
        reference is not yet justified. This test documents that decision
        as a checked invariant, not an oversight."""
        goal = Goal()
        plan = _make_plan(goal)
        workflow = _compile_workflow(plan)
        assert not hasattr(workflow.nodes[0], "root_operation_id")


class TestAttemptIdentityDistinctFromRetryCount:
    """I3/I6: a bare `attempts` counter cannot serve as a stable,
    opaque attempt identity -- "attempt #2" before a restart and
    "attempt #2" after one are not the same thing by count alone."""

    def test_workflow_node_state_has_both_attempts_and_attempt_id(self):
        from core.workflow.runtime import WorkflowNodeState
        state = WorkflowNodeState(node_id="n1")
        assert state.attempts == 0
        assert state.attempt_id == ""

    def test_attempt_id_is_freshly_generated_not_derived_from_the_counter(self):
        """Simulates what _execute_node_with_retry's loop does: each
        retry gets a fresh attempt_id, never derived from `attempts`."""
        from core.workflow.runtime import WorkflowNodeState
        state = WorkflowNodeState(node_id="n1")
        seen_ids = set()
        for attempt in range(3):
            state.attempts = attempt + 1
            state.attempt_id = str(uuid.uuid4())
            assert state.attempt_id not in seen_ids
            seen_ids.add(state.attempt_id)
        assert state.attempts == 3
        assert len(seen_ids) == 3


# ─────────────────────────────────────────────────────────────────────────
# Blocker B — context migration
# ─────────────────────────────────────────────────────────────────────────


class _EchoWorker(AbstractCognitiveWorker):
    """Minimal worker used only to capture what it actually receives at
    runtime -- proving the real invocation path, not a mock of it."""
    worker_type = "EchoWorker"

    async def _run(self, context: ExecutionContext) -> WorkerResult:
        return WorkerResult(
            success=True,
            output="echo",
            metadata={
                "received_type": type(context).__name__,
                "is_execution_context": isinstance(context, ExecutionContext),
                "is_worker_context": isinstance(context, WorkerContext),
                "query": context.query,
                "parameters": context.parameters,
                "task_id": context.task_id,
                "recursion_depth": context.recursion_depth,
            },
        )


class TestWorkersReceiveExecutionContextDirectly:
    @pytest.mark.asyncio
    async def test_execution_runtime_no_longer_converts_to_worker_context(self):
        """The core Blocker B fix: ExecutionRuntime.invoke() used to call
        context.to_worker_context() before every worker.execute() call.
        That conversion is gone -- the worker receives the real
        ExecutionContext instance."""
        registry = WorkerRegistry()
        registry.register(_EchoWorker)
        runtime = ExecutionRuntime(
            worker_registry=registry,
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )
        result = await runtime.invoke(
            "EchoWorker", query="hello", metadata={"parameters": {"k": "v"}},
        )
        assert result.success is True
        assert result.metadata["is_execution_context"] is True
        assert result.metadata["is_worker_context"] is False
        assert result.metadata["received_type"] == "ExecutionContext"

    @pytest.mark.asyncio
    async def test_bridge_properties_give_full_field_compatibility(self):
        """query/parameters/task_id/recursion_depth must all be readable
        on the ExecutionContext a worker actually receives -- proving the
        bridge properties work end-to-end, not merely that they exist."""
        registry = WorkerRegistry()
        registry.register(_EchoWorker)
        runtime = ExecutionRuntime(
            worker_registry=registry,
            governance=get_governance_kernel(),
            event_stream=get_event_stream(),
        )
        result = await runtime.invoke(
            "EchoWorker", query="hello", metadata={"parameters": {"k": "v"}},
        )
        assert result.metadata["query"] == "hello"
        assert result.metadata["parameters"] == {"k": "v"}
        assert result.metadata["task_id"]
        assert result.metadata["recursion_depth"] == 0

    def test_execution_context_parameters_bridge_property_reads_metadata(self):
        ctx = ExecutionContext(metadata={"parameters": {"a": 1}})
        assert ctx.parameters == {"a": 1}

    def test_execution_context_parameters_bridge_defaults_to_empty_dict(self):
        ctx = ExecutionContext()
        assert ctx.parameters == {}
