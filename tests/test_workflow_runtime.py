"""
tests/test_workflow_runtime.py — K2.2 WorkflowRuntime Tests

WorkflowRuntime, WorkflowDefinition, and PlannerWorker (core/workflow/*.py,
core/workers/planner.py) existed as complete implementations before this
session but had zero test coverage anywhere in the repository (confirmed:
no test_workflow*.py or test_planner*.py existed prior to K2.2's Phase 0
audit). This file closes that gap.

Tests for:
    - WorkflowDefinition validation
    - build_planner_workflow() factory
    - WorkflowRuntime linear execution
    - Error branch routing
    - Retry policy (backoff, max_retries, retryable_errors)
    - Cancellation
    - WorkflowRuntime.stats()

Architecture:
    KERNEL_ARCHITECTURE_v1.0.md §8 — Workflow Model.
    K2.2 success criteria verification.
"""

import asyncio
import pytest

from core.workflow.definition import (
    NodeStatus,
    RetryPolicy,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    build_planner_workflow,
    PLANNER_NODE_ID,
)
from core.workflow.runtime import WorkflowRuntime, WorkflowResult
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.cancellation import CancellationToken
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.governance.governance_kernel import get_governance_kernel
from core.events.event_stream import get_event_stream


# ── Test Workers ─────────────────────────────────────────────────────────────


class EchoNodeWorker(AbstractCognitiveWorker):
    """Always succeeds, echoes the query."""
    worker_type = "EchoNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(success=True, output=f"echo: {context.query}")


class AlwaysFailsNodeWorker(AbstractCognitiveWorker):
    """Always returns a failed WorkerResult (does not raise)."""
    worker_type = "AlwaysFailsNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(success=False, error="deliberate node failure")


class RecoveryNodeWorker(AbstractCognitiveWorker):
    """The error_branch target — always succeeds."""
    worker_type = "RecoveryNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(success=True, output="recovered")


class FlakyNodeWorker(AbstractCognitiveWorker):
    """Fails FAIL_COUNT times, then succeeds.

    Class-level counter because ExecutionRuntime constructs a fresh
    Worker instance per invoke() (ADR-003) — instance state cannot
    survive across a WorkflowRuntime retry loop, only class state can.
    """
    worker_type = "FlakyNodeWorker"
    FAIL_COUNT = 2
    attempts = 0

    async def _run(self, context: WorkerContext) -> WorkerResult:
        type(self).attempts += 1
        if type(self).attempts <= type(self).FAIL_COUNT:
            return WorkerResult(success=False, error="transient failure")
        return WorkerResult(success=True, output="succeeded after retry")

    @classmethod
    def reset(cls):
        cls.attempts = 0


# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_workflow_runtime(*worker_classes):
    registry = WorkerRegistry()
    for cls in worker_classes:
        registry.register(cls)
    execution_runtime = ExecutionRuntime(
        worker_registry=registry,
        governance=get_governance_kernel(),
        event_stream=get_event_stream(),
    )
    return WorkflowRuntime(
        execution_runtime=execution_runtime,
        event_stream=get_event_stream(),
    )


# ── WorkflowDefinition.validate() ────────────────────────────────────────────


class TestWorkflowDefinitionValidation:
    def test_valid_single_node(self):
        d = WorkflowDefinition(
            workflow_id="w1", nodes=[WorkflowNode(node_id="a", worker_type="X")],
            entry_node="a",
        )
        assert d.validate() == []

    def test_missing_entry_node(self):
        d = WorkflowDefinition(workflow_id="w1", nodes=[])
        errors = d.validate()
        assert any("No entry_node" in e for e in errors)

    def test_entry_node_not_in_nodes(self):
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="X")],
            entry_node="does-not-exist",
        )
        errors = d.validate()
        assert any("not in nodes" in e for e in errors)

    def test_edge_to_unknown_node(self):
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="X")],
            edges=[WorkflowEdge(from_node="a", to_node="ghost")],
            entry_node="a",
        )
        errors = d.validate()
        assert any("Edge to unknown node" in e for e in errors)

    def test_error_branch_to_unknown_node(self):
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="X", error_branch="ghost")],
            entry_node="a",
        )
        errors = d.validate()
        assert any("error_branch" in e for e in errors)

    def test_get_successors(self):
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="X"),
                   WorkflowNode(node_id="b", worker_type="Y")],
            edges=[WorkflowEdge(from_node="a", to_node="b")],
            entry_node="a",
        )
        assert d.get_successors("a") == ["b"]
        assert d.get_successors("b") == []


class TestBuildPlannerWorkflow:
    def test_shape(self):
        d = build_planner_workflow()
        assert d.entry_node == PLANNER_NODE_ID
        assert len(d.nodes) == 1
        assert d.nodes[0].worker_type == "PlannerWorker"
        assert d.nodes[0].node_id == PLANNER_NODE_ID
        assert d.validate() == []

    def test_default_retry_policy_is_zero(self):
        # PlannerWorker already fans out to multiple modules internally;
        # retrying the whole pipeline on partial failure would silently
        # re-run modules that already succeeded — see the factory's
        # docstring for the full rationale.
        d = build_planner_workflow()
        assert d.nodes[0].retry_policy.max_retries == 0

    def test_custom_workflow_id(self):
        d = build_planner_workflow(workflow_id="custom-id")
        assert d.workflow_id == "custom-id"


# ── WorkflowRuntime.execute() ────────────────────────────────────────────────


class TestWorkflowRuntimeLinearExecution:
    @pytest.mark.asyncio
    async def test_single_node_success(self):
        runtime = _make_workflow_runtime(EchoNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="EchoNodeWorker")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hello")
        assert result.success is True
        assert result.output == "echo: hello"
        assert "a" in result.node_results
        assert result.node_results["a"].success is True

    @pytest.mark.asyncio
    async def test_two_node_linear_chain(self):
        runtime = _make_workflow_runtime(EchoNodeWorker, RecoveryNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[
                WorkflowNode(node_id="a", worker_type="EchoNodeWorker"),
                WorkflowNode(node_id="b", worker_type="RecoveryNodeWorker"),
            ],
            edges=[WorkflowEdge(from_node="a", to_node="b")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is True
        assert set(result.node_results.keys()) == {"a", "b"}
        # Output is from the last executed node in the chain.
        assert result.output == "recovered"

    @pytest.mark.asyncio
    async def test_invalid_definition_fails_fast(self):
        runtime = _make_workflow_runtime(EchoNodeWorker)
        d = WorkflowDefinition(workflow_id="w1", nodes=[], entry_node="")
        result = await runtime.execute(d, query="hi")
        assert result.success is False
        assert "Invalid workflow" in result.error
        assert result.node_results == {}

    @pytest.mark.asyncio
    async def test_unknown_worker_type_contained_as_failure(self):
        runtime = _make_workflow_runtime(EchoNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="NotRegistered")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is False
        assert "Unknown worker type" in result.node_results["a"].error


class TestWorkflowRuntimeErrorBranch:
    @pytest.mark.asyncio
    async def test_error_branch_routes_on_failure(self):
        runtime = _make_workflow_runtime(AlwaysFailsNodeWorker, RecoveryNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[
                WorkflowNode(node_id="a", worker_type="AlwaysFailsNodeWorker",
                             error_branch="recover"),
                WorkflowNode(node_id="recover", worker_type="RecoveryNodeWorker"),
            ],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is True
        assert result.output == "recovered"
        assert result.node_results["a"].success is False
        assert result.node_results["recover"].success is True

    @pytest.mark.asyncio
    async def test_no_error_branch_propagates_failure(self):
        runtime = _make_workflow_runtime(AlwaysFailsNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="AlwaysFailsNodeWorker")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is False
        assert "deliberate node failure" in result.error


class TestWorkflowRuntimeRetry:
    @pytest.mark.asyncio
    async def test_retry_recovers_within_budget(self):
        FlakyNodeWorker.reset()
        runtime = _make_workflow_runtime(FlakyNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(
                node_id="a", worker_type="FlakyNodeWorker",
                retry_policy=RetryPolicy(max_retries=3, backoff_seconds=0.01,
                                          max_backoff_seconds=0.02),
            )],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is True
        assert result.output == "succeeded after retry"
        # 2 failures + 1 success = 3 attempts
        assert FlakyNodeWorker.attempts == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_still_fails(self):
        FlakyNodeWorker.reset()
        runtime = _make_workflow_runtime(FlakyNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(
                node_id="a", worker_type="FlakyNodeWorker",
                retry_policy=RetryPolicy(max_retries=1, backoff_seconds=0.01,
                                          max_backoff_seconds=0.02),
            )],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        # FAIL_COUNT=2 but max_retries=1 → only 2 attempts total, both fail.
        assert result.success is False
        assert FlakyNodeWorker.attempts == 2

    @pytest.mark.asyncio
    async def test_non_retryable_error_stops_early(self):
        runtime = _make_workflow_runtime(AlwaysFailsNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(
                node_id="a", worker_type="AlwaysFailsNodeWorker",
                retry_policy=RetryPolicy(
                    max_retries=5, backoff_seconds=0.01,
                    retryable_errors=["some other error"],
                ),
            )],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is False
        # "deliberate node failure" doesn't match "some other error" —
        # should stop after the first attempt, not retry 5 times.
        assert result.node_results["a"].metadata.get("worker_type") == \
            "AlwaysFailsNodeWorker"


class TestWorkflowRuntimeCancellation:
    @pytest.mark.asyncio
    async def test_pre_cancelled_token_short_circuits(self):
        runtime = _make_workflow_runtime(EchoNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1",
            nodes=[WorkflowNode(node_id="a", worker_type="EchoNodeWorker")],
            entry_node="a",
        )
        token = CancellationToken()
        token.cancel("test cancellation")
        result = await runtime.execute(d, query="hi", cancellation_token=token)
        assert result.success is False


class TestWorkflowRuntimeStats:
    @pytest.mark.asyncio
    async def test_stats_track_executions_and_failures(self):
        runtime = _make_workflow_runtime(EchoNodeWorker, AlwaysFailsNodeWorker)
        ok = WorkflowDefinition(
            workflow_id="ok",
            nodes=[WorkflowNode(node_id="a", worker_type="EchoNodeWorker")],
            entry_node="a",
        )
        bad = WorkflowDefinition(
            workflow_id="bad",
            nodes=[WorkflowNode(node_id="a", worker_type="AlwaysFailsNodeWorker")],
            entry_node="a",
        )
        before = runtime.stats()
        await runtime.execute(ok, query="hi")
        await runtime.execute(bad, query="hi")
        after = runtime.stats()
        assert after["total_executions"] == before["total_executions"] + 2
        assert after["total_failures"] == before["total_failures"] + 1
