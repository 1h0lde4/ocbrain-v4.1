"""
tests/test_debt_020_completion_semantics.py — DEBT-020 completion-gate tests

Covers the root-cause fix: execution status (WorkflowResult.success /
WorkerResult.success) and task completion status (WorkflowResult.
completion_status) are now independent, and nothing in the paths tested
here can reconstruct SUCCESS-equivalent completion from execution status
alone.

See docs/Bugs Hunt & fix reports/DEBT_020_PRE_IMPLEMENTATION_TRACE_AND_GATE_DESIGN.md
for the live-path trace this repairs.

Deliberately self-contained (does not import fixtures from
test_workflow_runtime.py) -- minor duplication of a couple of test worker
classes, traded for not coupling two test files' maintenance together.

Structure:
    TestConstraintCheckableValue           -- Constraint.has_checkable_value() / is_satisfied_by()
    TestConstraintsThreadedThroughCompilation -- ExecutionPlan -> compile() -> WorkflowDefinition
    TestCompletionGateUnit                 -- WorkflowRuntime._evaluate_completion() in isolation
    TestCompletionGateIntegration          -- real WorkflowRuntime.execute() (mission Section 34)
    TestFailClosedDefaults                 -- bare WorkflowResult(), invalid-definition path
"""

import pytest

from core.cognitive.compiler import compile as compile_plan
from core.cognitive.planner import (
    Constraint,
    ConstraintComparator,
    ConstraintKind,
    ExecutionPlan,
    PlanStep,
)
from core.events.event_stream import get_event_stream
from core.governance.governance_kernel import get_governance_kernel
from core.runtime.execution_outcome import (
    CompletionReason,
    CompletionStatus,
    ExecutionOutcome,
    FailureType,
)
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.workflow.definition import WorkflowDefinition, WorkflowNode
from core.workflow.runtime import WorkflowResult


# ── Test workers ─────────────────────────────────────────────────────────


class EchoNodeWorker(AbstractCognitiveWorker):
    """Always succeeds, echoes the query. Output word count is exactly
    len(query.split()) + 1 (the "echo:" prefix) -- controllable and exact,
    used to test constraint checking against a known observed value."""
    worker_type = "EchoNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(success=True, output=f"echo: {context.query}")


class AlwaysFailsNodeWorker(AbstractCognitiveWorker):
    worker_type = "AlwaysFailsNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(success=False, error="deliberate failure")


class PartialOutputNodeWorker(AbstractCognitiveWorker):
    """Reports success=True (execution terminated without erroring) but
    carries execution_detail.failure_type == COMPLETED_WITH_PARTIAL_OUTPUT
    -- the exact two-signal shape mission Section 32 requires regression
    coverage for: WorkerResult.success and execution_detail.is_success can
    independently disagree with the actual completion truth."""
    worker_type = "PartialOutputNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(
            success=True,
            output="only got partway through",
            execution_detail=ExecutionOutcome(
                failure_type=FailureType.COMPLETED_WITH_PARTIAL_OUTPUT,
                partial_output="only got partway through",
            ),
        )


def _make_workflow_runtime(*worker_classes):
    # Local import to avoid a module-level circular-import risk between
    # this test file and core.workflow.runtime at collection time.
    from core.workflow.runtime import WorkflowRuntime

    registry = WorkerRegistry()
    for cls in worker_classes:
        registry.register(cls)
    stream = get_event_stream()
    execution_runtime = ExecutionRuntime(
        worker_registry=registry,
        governance=get_governance_kernel(),
        event_stream=stream,
    )
    return WorkflowRuntime(execution_runtime=execution_runtime, event_stream=stream)


def _word_count_constraint(target: int, comparator: str = ConstraintComparator.GTE) -> Constraint:
    return Constraint(
        kind=ConstraintKind.HARD,
        measure="word_count",
        target=target,
        comparator=comparator,
    )


# ── Constraint.has_checkable_value() / is_satisfied_by() ───────────────────


class TestConstraintCheckableValue:
    def test_default_constraint_has_no_checkable_value(self):
        assert Constraint().has_checkable_value() is False

    def test_full_shape_is_checkable(self):
        assert _word_count_constraint(100).has_checkable_value() is True

    def test_partial_shape_is_not_checkable(self):
        assert Constraint(measure="word_count").has_checkable_value() is False
        assert Constraint(measure="word_count", target=100).has_checkable_value() is False

    def test_is_satisfied_by_gte(self):
        c = _word_count_constraint(100, ConstraintComparator.GTE)
        assert c.is_satisfied_by(150) is True
        assert c.is_satisfied_by(100) is True
        assert c.is_satisfied_by(50) is False

    def test_is_satisfied_by_lte(self):
        c = _word_count_constraint(100, ConstraintComparator.LTE)
        assert c.is_satisfied_by(50) is True
        assert c.is_satisfied_by(150) is False

    def test_is_satisfied_by_eq(self):
        c = _word_count_constraint(100, ConstraintComparator.EQ)
        assert c.is_satisfied_by(100) is True
        assert c.is_satisfied_by(99) is False

    def test_is_satisfied_by_raises_when_not_checkable(self):
        """Must not silently return True/False for a comparison that was
        never actually specified -- caller error, not a valid outcome."""
        with pytest.raises(ValueError):
            Constraint().is_satisfied_by(50)

    def test_existing_construction_pattern_unaffected(self):
        """New fields must be additive: a Constraint built the old way
        (no measure/target/comparator) still constructs cleanly and is
        simply non-checkable, not an error."""
        c = Constraint(kind=ConstraintKind.HARD, rationale="must not use profanity")
        assert c.has_checkable_value() is False


# ── ExecutionPlan.constraints -> compile() -> WorkflowDefinition.constraints ──


class TestConstraintsThreadedThroughCompilation:
    """Regression guard for the gap found only while implementing the
    gate: ExecutionPlan had no constraints field at all, so nothing a
    WorkflowRuntime gate could ever check survived past planning."""

    @pytest.mark.asyncio
    async def test_constraints_survive_compilation(self):
        c = _word_count_constraint(100)
        plan = ExecutionPlan(
            goal_id="g1",
            steps=[PlanStep(step_id="s1", description="write something",
                             capability_type="llm_completion")],
            confidence=0.9,
            constraints=[c],
        )
        result = await compile_plan(plan, event_stream=get_event_stream())
        assert result.workflow_definition is not None
        assert result.workflow_definition.constraints == [c]

    @pytest.mark.asyncio
    async def test_no_constraints_compiles_to_empty_list(self):
        plan = ExecutionPlan(
            goal_id="g1",
            steps=[PlanStep(step_id="s1", description="do a thing",
                             capability_type="llm_completion")],
            confidence=0.9,
        )
        result = await compile_plan(plan, event_stream=get_event_stream())
        assert result.workflow_definition.constraints == []


# ── WorkflowRuntime._evaluate_completion() in isolation ─────────────────────


class TestCompletionGateUnit:
    def test_none_result_is_unknown(self):
        runtime = _make_workflow_runtime()
        result = runtime._evaluate_completion(
            last_result=None, constraints=[], execution_succeeded=False,
        )
        assert result.status == CompletionStatus.UNKNOWN
        assert result.reason == CompletionReason.NO_RESULT

    def test_execution_failed_is_incomplete(self):
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=False, error="boom")
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[], execution_succeeded=False,
        )
        assert result.status == CompletionStatus.INCOMPLETE
        assert result.reason == CompletionReason.EXECUTION_FAILURE

    def test_cancellation_is_incomplete_cancelled(self):
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=False, error="Workflow cancelled")
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[], execution_succeeded=False,
        )
        assert result.status == CompletionStatus.INCOMPLETE
        assert result.reason == CompletionReason.CANCELLED

    def test_zero_constraints_is_unknown_not_satisfied(self):
        """The consequential branch flagged before implementation began:
        no constraints at all must not default to SATISFIED."""
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=True, output="hello world")
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[], execution_succeeded=True,
        )
        assert result.status == CompletionStatus.UNKNOWN
        assert result.reason == CompletionReason.NO_CHECKABLE_CONSTRAINT

    def test_non_checkable_constraint_is_unknown(self):
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=True, output="hello world")
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[Constraint()], execution_succeeded=True,
        )
        assert result.status == CompletionStatus.UNKNOWN

    def test_hard_constraint_violated(self):
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=True, output="only three words")
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[_word_count_constraint(100)],
            execution_succeeded=True,
        )
        assert result.status == CompletionStatus.VIOLATED
        assert result.reason == CompletionReason.HARD_CONSTRAINT_VIOLATED

    def test_hard_constraint_satisfied(self):
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=True, output=" ".join(["word"] * 150))
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[_word_count_constraint(100)],
            execution_succeeded=True,
        )
        assert result.status == CompletionStatus.SATISFIED
        assert result.reason == ""

    def test_soft_constraint_never_produces_violated(self):
        """Only HARD constraints participate in VIOLATED/SATISFIED -- a
        failing soft constraint must not block completion."""
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=True, output="short")
        soft = Constraint(kind=ConstraintKind.SOFT, measure="word_count",
                           target=1000, comparator=ConstraintComparator.GTE)
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[soft], execution_succeeded=True,
        )
        assert result.status != CompletionStatus.VIOLATED
        assert result.status == CompletionStatus.UNKNOWN  # no HARD checkable constraint

    def test_partial_output_signal_overrides_bare_success(self):
        """Mission Section 32: WorkerResult.success and
        execution_detail.is_success are two independent, unsynced
        execution-level signals. A worker reporting success=True but with
        execution_detail.failure_type == COMPLETED_WITH_PARTIAL_OUTPUT
        must not be eligible for SATISFIED."""
        runtime = _make_workflow_runtime()
        wr = WorkerResult(
            success=True,
            output="partial",
            execution_detail=ExecutionOutcome(
                failure_type=FailureType.COMPLETED_WITH_PARTIAL_OUTPUT,
                partial_output="partial",
            ),
        )
        result = runtime._evaluate_completion(
            last_result=wr, constraints=[], execution_succeeded=True,
        )
        assert result.status == CompletionStatus.INCOMPLETE
        assert result.reason == CompletionReason.PARTIAL_OUTPUT

    def test_gate_internal_exception_fails_closed(self):
        """Section 33: a completion-gate internal failure must never fall
        through to execution success. Force an exception via a
        constraint-like object that raises on attribute access."""
        runtime = _make_workflow_runtime()
        wr = WorkerResult(success=True, output="hello")

        class ExplodesOnAccess:
            @property
            def kind(self):
                raise RuntimeError("simulated internal failure")

        result = runtime._evaluate_completion(
            last_result=wr, constraints=[ExplodesOnAccess()], execution_succeeded=True,
        )
        assert result.status == CompletionStatus.UNKNOWN
        assert result.reason == CompletionReason.COMPLETION_EVALUATION_FAILED


# ── Integration: through the real WorkflowRuntime.execute() path ───────────
#
# Mission Section 34: "Do not validate DEBT-020 exclusively with isolated
# result-object tests... exercise the same function and state transitions
# used by real K4.2 traffic." These go through the actual
# execute() -> _execute_from() -> aggregation path.


class TestCompletionGateIntegration:
    @pytest.mark.asyncio
    async def test_plain_success_alone_is_not_satisfied(self):
        """The regression this mission exists to close: before this fix,
        a plain successful execution alone made goal_completed=True. It
        must not, by itself, produce SATISFIED."""
        runtime = _make_workflow_runtime(EchoNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="EchoNodeWorker")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hello")
        assert result.success is True  # execution status: unchanged
        assert result.completion_status == CompletionStatus.UNKNOWN
        assert result.completion_status != CompletionStatus.SATISFIED

    @pytest.mark.asyncio
    async def test_hard_constraint_violated_end_to_end(self):
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="EchoNodeWorker")],
            entry_node="a",
            constraints=[_word_count_constraint(100)],
        )
        runtime = _make_workflow_runtime(EchoNodeWorker)
        result = await runtime.execute(d, query="hi")  # "echo: hi" == 2 words
        assert result.success is True  # execution still terminated fine
        assert result.completion_status == CompletionStatus.VIOLATED
        assert result.completion_reason == CompletionReason.HARD_CONSTRAINT_VIOLATED

    @pytest.mark.asyncio
    async def test_hard_constraint_satisfied_end_to_end(self):
        long_query = " ".join(["word"] * 150)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="EchoNodeWorker")],
            entry_node="a",
            constraints=[_word_count_constraint(100)],
        )
        runtime = _make_workflow_runtime(EchoNodeWorker)
        result = await runtime.execute(d, query=long_query)
        assert result.success is True
        assert result.completion_status == CompletionStatus.SATISFIED
        assert result.completion_reason == ""

    @pytest.mark.asyncio
    async def test_execution_failure_is_incomplete_not_violated(self):
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="AlwaysFailsNodeWorker")],
            entry_node="a",
        )
        runtime = _make_workflow_runtime(AlwaysFailsNodeWorker)
        result = await runtime.execute(d, query="hi")
        assert result.success is False
        assert result.completion_status == CompletionStatus.INCOMPLETE
        assert result.completion_status != CompletionStatus.VIOLATED

    @pytest.mark.asyncio
    async def test_partial_output_end_to_end(self):
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="PartialOutputNodeWorker")],
            entry_node="a",
        )
        runtime = _make_workflow_runtime(PartialOutputNodeWorker)
        result = await runtime.execute(d, query="hi")
        assert result.success is True  # WorkerResult.success was True
        assert result.completion_status == CompletionStatus.INCOMPLETE
        assert result.completion_reason == CompletionReason.PARTIAL_OUTPUT


# ── Fail-closed defaults ─────────────────────────────────────────────────


class TestFailClosedDefaults:
    def test_bare_workflow_result_defaults_to_unknown(self):
        """A WorkflowResult built without going through
        _evaluate_completion (a hand-built object anywhere in the
        codebase, present or future) must read as not-yet-evaluated,
        never as satisfied."""
        wr = WorkflowResult()
        assert wr.completion_status == CompletionStatus.UNKNOWN
        assert wr.completion_reason == ""

    @pytest.mark.asyncio
    async def test_invalid_definition_completion_is_not_satisfied(self):
        runtime = _make_workflow_runtime(EchoNodeWorker)
        d = WorkflowDefinition(workflow_id="w1", nodes=[], entry_node="")
        result = await runtime.execute(d, query="hi")
        assert result.success is False
        assert result.completion_status != CompletionStatus.SATISFIED
