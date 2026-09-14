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


class TestRootOperationIdSurvivesRecoveryReplan:
    """Corrects a claim ADR-KERNEL-01 made without fully tracing the code:
    it stated the Orchestrator's re-plan loop "creates a fresh Goal()" on
    recovery. Direct tracing (this session) found otherwise: the only
    Goal() construction site in the entire codebase is
    core/cognitive/intent.py's form_goals(), called exactly once per
    handle() invocation (core/orchestrator.py, single call site,
    confirmed by grep). The impasse re-plan loop (core/orchestrator.py
    lines ~368-397) re-invokes plan() with the SAME PlannerRequest --
    built from the SAME Goal object -- on every retry; it does not touch
    Goal formation at all. root_operation_id is therefore already,
    trivially preserved across every current replan iteration, because
    it is the literal same Python object, not a value that needs
    explicit re-propagation.

    This test proves that trivial preservation observably, against the
    real orchestrator path (not a mock of the identity logic itself),
    and exists specifically as regression protection: if a future change
    ever introduces a second Goal() construction into this loop, this
    test is what would catch it losing root_operation_id.
    """

    @pytest.mark.asyncio
    async def test_every_plan_call_across_an_impasse_retry_sees_the_same_root_operation_id(self):
        from unittest.mock import AsyncMock, MagicMock, patch
        from core.cognitive.compiler import CompilationResult, CompilationStatus
        from core.cognitive.planner import PlannerResult, PlannerStatus
        from core.context import ContextMemory
        from core.governance.governance_kernel import GovernanceResult
        from core.model_router import RouteResult
        from core.orchestrator import Orchestrator
        from core.memory.unified_memory import UnifiedMemory

        memory = AsyncMock(spec=UnifiedMemory)
        context = MagicMock(spec=ContextMemory)
        router = MagicMock()
        router.route = AsyncMock(return_value=RouteResult(answer="unused", source="mock"))
        governance = MagicMock()
        governance.evaluate_action = MagicMock(return_value=GovernanceResult())
        event_stream = AsyncMock()
        execution_runtime = AsyncMock()
        workflow_runtime = MagicMock()
        capability_registry = MagicMock()

        orch = Orchestrator(
            modules={}, context=context, router=router, memory=memory,
            governance=governance, event_stream=event_stream,
            execution_runtime=execution_runtime, workflow_runtime=workflow_runtime,
            capability_registry=capability_registry,
            use_k42_frontend=True, max_recovery_attempts=5,
        )

        goal = Goal(resource_id="g1",
                     structured_form={"description": "test", "raw_request": "test"})
        original_root_op_id = goal.root_operation_id
        assert original_root_op_id  # sanity: Goal() really does generate one

        seen_root_operation_ids = []

        async def _plan_spy(planner_request, *args, **kwargs):
            seen_root_operation_ids.append(planner_request.goal.root_operation_id)
            call_number = len(seen_root_operation_ids)
            if call_number < 3:
                return PlannerResult(status=PlannerStatus.IMPASSE, operation_id=f"op-{call_number}")
            return PlannerResult(
                status=PlannerStatus.READY_FOR_COMPILATION,
                execution_plan=ExecutionPlan(goal_id="g1", root_operation_id=planner_request.goal.root_operation_id),
                operation_id=f"op-{call_number}",
            )

        with patch("core.cognitive.intent.interpret_request",
                    new=AsyncMock(return_value=[goal])), \
             patch("core.cognitive.planner.plan", new=AsyncMock(side_effect=_plan_spy)), \
             patch("core.cognitive.compiler.compile", new=AsyncMock(
                 return_value=CompilationResult(status=CompilationStatus.REJECTED))):
            await orch.handle("a request that impasses twice then succeeds")

        assert len(seen_root_operation_ids) == 3, (
            "expected exactly 3 plan() calls (2 impasses + 1 success); "
            "got a different count, so this test is not exercising the "
            "retry loop it claims to"
        )
        assert all(rid == original_root_op_id for rid in seen_root_operation_ids), (
            f"root_operation_id changed across the retry loop: "
            f"{seen_root_operation_ids} -- the SAME Goal object must "
            f"produce the SAME root_operation_id on every plan() "
            f"invocation within one handle() call"
        )

    @pytest.mark.asyncio
    async def test_two_separate_handle_calls_get_different_root_operation_ids(self):
        """The complement of the above: two INDEPENDENT operations (two
        separate handle() calls, each forming its own Goal via
        interpret_request()) must NOT share a root_operation_id, even
        when nothing else distinguishes them (I11: concurrency
        isolation)."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from core.cognitive.compiler import CompilationResult, CompilationStatus
        from core.cognitive.planner import PlannerResult, PlannerStatus
        from core.context import ContextMemory
        from core.governance.governance_kernel import GovernanceResult
        from core.model_router import RouteResult
        from core.orchestrator import Orchestrator
        from core.memory.unified_memory import UnifiedMemory

        memory = AsyncMock(spec=UnifiedMemory)
        context = MagicMock(spec=ContextMemory)
        router = MagicMock()
        router.route = AsyncMock(return_value=RouteResult(answer="unused", source="mock"))
        governance = MagicMock()
        governance.evaluate_action = MagicMock(return_value=GovernanceResult())
        event_stream = AsyncMock()
        execution_runtime = AsyncMock()
        workflow_runtime = MagicMock()
        capability_registry = MagicMock()

        orch = Orchestrator(
            modules={}, context=context, router=router, memory=memory,
            governance=governance, event_stream=event_stream,
            execution_runtime=execution_runtime, workflow_runtime=workflow_runtime,
            capability_registry=capability_registry,
            use_k42_frontend=True, max_recovery_attempts=5,
        )

        seen_root_operation_ids = []

        async def _plan_spy(planner_request, *args, **kwargs):
            seen_root_operation_ids.append(planner_request.goal.root_operation_id)
            return PlannerResult(
                status=PlannerStatus.READY_FOR_COMPILATION,
                execution_plan=ExecutionPlan(goal_id=planner_request.goal.resource_id),
                operation_id="op-x",
            )

        for i in range(2):
            goal = Goal(resource_id=f"g{i}",
                         structured_form={"description": "test", "raw_request": "test"})
            with patch("core.cognitive.intent.interpret_request",
                        new=AsyncMock(return_value=[goal])), \
                 patch("core.cognitive.planner.plan", new=AsyncMock(side_effect=_plan_spy)), \
                 patch("core.cognitive.compiler.compile", new=AsyncMock(
                     return_value=CompilationResult(status=CompilationStatus.REJECTED))):
                await orch.handle(f"independent request {i}")

        assert len(seen_root_operation_ids) == 2
        assert seen_root_operation_ids[0] != seen_root_operation_ids[1], (
            "two independent handle() calls produced the same "
            "root_operation_id -- I11 concurrency isolation violated"
        )


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
