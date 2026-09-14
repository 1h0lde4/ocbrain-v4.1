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
import os
import tempfile
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
from core.workflow.runtime import WorkflowRuntime, WorkflowResult, WorkflowNodeState
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.cancellation import CancellationToken
from core.runtime.execution_budget import ExecutionBudget
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.governance.governance_kernel import get_governance_kernel
from core.events.event_stream import EventStream, SQLiteEventStore, get_event_stream


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


class SlowNodeWorker(AbstractCognitiveWorker):
    """Sleeps in small increments, cooperatively checking cancellation
    between them, without ever reporting intermediate progress -- the
    exact shape that used to defeat the graph-aware watchdog (DEBT-016 /
    ADR-KERNEL-02): a node that's genuinely running, but never calls
    report_progress(), so the only sign of life the watchdog can observe
    is the RUNNING status touch from when it started.

    Checks the token itself because ExecutionRuntime.invoke() does not
    forcibly preempt a running worker -- cancellation in this architecture
    is cooperative, not enforced (see core/runtime/cancellation.py); a
    well-behaved worker is expected to notice and stop."""
    worker_type = "SlowNodeWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        seconds = (context.metadata or {}).get("sleep_s", 1.0)
        step = 0.02
        elapsed = 0.0
        while elapsed < seconds:
            if context.cancellation_token is not None and context.cancellation_token.is_cancelled:
                return WorkerResult(success=False, error="cancelled mid-sleep")
            await asyncio.sleep(step)
            elapsed += step
        return WorkerResult(success=True, output="finally done")


class CountingNodeWorker(AbstractCognitiveWorker):
    """Records every invocation by node_id via a class-level counter, so a
    test can prove a node was (or, for the resume tests, deliberately was
    NOT) actually re-invoked -- not just that the final WorkflowResult
    looks right, which could also happen if it were harmlessly re-run and
    produced the same output. Class-level for the same reason as
    FlakyNodeWorker above: ExecutionRuntime constructs a fresh Worker
    instance per invoke()."""
    worker_type = "CountingNodeWorker"
    invocations: list = []

    async def _run(self, context: WorkerContext) -> WorkerResult:
        node_id = (context.metadata or {}).get("node_id")
        type(self).invocations.append(node_id)
        return WorkerResult(success=True, output=f"done:{node_id}")

    @classmethod
    def reset(cls):
        cls.invocations = []


# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_workflow_runtime(*worker_classes, event_stream=None):
    registry = WorkerRegistry()
    for cls in worker_classes:
        registry.register(cls)
    stream = event_stream or get_event_stream()
    execution_runtime = ExecutionRuntime(
        worker_registry=registry,
        governance=get_governance_kernel(),
        event_stream=stream,
    )
    return WorkflowRuntime(
        execution_runtime=execution_runtime,
        event_stream=stream,
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


class TestWorkflowRuntimeWatchdogReconciliation:
    """DEBT-016 / ADR-KERNEL-02: the graph-aware watchdog (used by every
    WorkflowRuntime.execute() call, the K4.2 default path) used to only
    ever *record* a stalled node, never attempt bounded recovery, and
    never cancel because of a stall (only via an unrelated hard-ceiling
    check). These exercise the fix through the real execute() path, not
    just the isolated watchdog unit tests in test_execution_inspection.py.
    """

    def test_default_budget_has_real_extension_headroom(self):
        budget = WorkflowRuntime.default_budget_for("hi")
        # This is the exact bug: absolute_ceiling_s used to equal
        # hard_ceiling_s, which makes grant_extension() structurally
        # incapable of granting anything (its own clamp is
        # min(seconds, absolute_ceiling_s - hard_ceiling_s)) regardless of
        # what max_extension_s claims. A regression here silently disables
        # every stall-recovery attempt on the default path.
        assert budget.absolute_ceiling_s > budget.hard_ceiling_s
        assert budget.max_extension_s > 0
        assert budget.grant_extension(budget.max_extension_s) is True

    @pytest.mark.asyncio
    async def test_stalled_node_recovers_via_extension_and_completes(self):
        runtime = _make_workflow_runtime(SlowNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w-slow-ok",
            nodes=[WorkflowNode(node_id="a", worker_type="SlowNodeWorker")],
            entry_node="a",
        )
        # Sleeps past progress_deadline_s (stall detected, extension
        # granted) but well within hard_ceiling_s + the granted extension
        # -- the workflow should still succeed, having been given more
        # time rather than given up at the first sign of silence.
        budget = ExecutionBudget(
            startup_deadline_s=0.2, progress_deadline_s=0.2,
            hard_ceiling_s=0.3, absolute_ceiling_s=2.0, max_extension_s=1.5,
        )
        result = await runtime.execute(
            d, query="hi", metadata={"sleep_s": 0.6, "execution_budget": budget},
        )
        assert result.success is True
        assert result.node_results["a"].output == "finally done"

    @pytest.mark.asyncio
    async def test_stalled_node_beyond_extension_is_cancelled_not_silently_stuck(self):
        runtime = _make_workflow_runtime(SlowNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w-slow-fail",
            nodes=[WorkflowNode(node_id="a", worker_type="SlowNodeWorker")],
            entry_node="a",
        )
        # Sleeps well beyond hard_ceiling_s + the one available extension:
        # before DEBT-016, this would have been marked "stalled" and left
        # to run for the full (much larger) default hard ceiling with no
        # consequence. Here it must actually fail, promptly, once the
        # bounded extension is exhausted.
        budget = ExecutionBudget(
            startup_deadline_s=0.1, progress_deadline_s=0.1,
            hard_ceiling_s=0.2, absolute_ceiling_s=0.4, max_extension_s=0.2,
        )
        result = await runtime.execute(
            d, query="hi", metadata={"sleep_s": 5.0, "execution_budget": budget},
        )
        assert result.success is False


class TestWorkflowNodeStateSerialization:
    """DEBT-003 / ADR-KERNEL-03: checkpoint-safe round-tripping."""

    def test_round_trip_preserves_primary_fields(self):
        original = WorkflowNodeState(
            node_id="a", status=NodeStatus.COMPLETED,
            result=WorkerResult(success=True, output="hello", artifacts={"x": 1},
                                 events_emitted=3, duration_ms=12.5, metadata={"m": "n"}),
            attempts=2, attempt_id="attempt-123",
            started_at=100.0, completed_at=105.0,
        )
        restored = WorkflowNodeState.from_dict(original.to_dict())

        assert restored.node_id == "a"
        assert restored.status == NodeStatus.COMPLETED
        assert restored.attempts == 2
        assert restored.attempt_id == "attempt-123"
        assert restored.started_at == 100.0
        assert restored.completed_at == 105.0
        assert restored.result.success is True
        assert restored.result.output == "hello"
        assert restored.result.artifacts == {"x": 1}
        assert restored.result.duration_ms == 12.5
        # Known, documented limitation, not a bug: execution_detail is not
        # restored (see _worker_result_to_dict's docstring).
        assert restored.result.execution_detail is None

    def test_round_trip_survives_real_json(self):
        """to_dict()'s whole point is being JSON-safe -- prove it actually
        is, not just that Python-to-Python round-tripping works."""
        import json
        state = WorkflowNodeState(
            node_id="b", status=NodeStatus.FAILED,
            result=WorkerResult(success=False, error="boom"),
        )
        blob = json.dumps(state.to_dict())
        restored = WorkflowNodeState.from_dict(json.loads(blob))
        assert restored.status == NodeStatus.FAILED
        assert restored.result.error == "boom"

    def test_pending_node_with_no_result_round_trips_to_none(self):
        state = WorkflowNodeState(node_id="c")
        restored = WorkflowNodeState.from_dict(state.to_dict())
        assert restored.status == NodeStatus.PENDING
        assert restored.result is None


class TestWorkflowRuntimeCheckpointResume:
    """DEBT-003 / ADR-KERNEL-03: WorkflowRuntime checkpoint/resume."""

    @pytest.mark.asyncio
    async def test_checkpoint_written_after_each_node_completes(self):
        CountingNodeWorker.reset()
        runtime = _make_workflow_runtime(CountingNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w-ckpt", name="ckpt",
            nodes=[WorkflowNode(node_id="a", worker_type="CountingNodeWorker"),
                   WorkflowNode(node_id="b", worker_type="CountingNodeWorker")],
            edges=[WorkflowEdge(from_node="a", to_node="b")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is True

        checkpoint = await runtime._event_stream.get_checkpoint(
            runtime._checkpoint_name(result.instance_id)
        )
        assert checkpoint is not None
        node_states = checkpoint.payload["node_states"]
        assert node_states["a"]["status"] == "completed"
        assert node_states["b"]["status"] == "completed"
        assert checkpoint.payload["workflow_id"] == "w-ckpt"

    @pytest.mark.asyncio
    async def test_resume_with_no_checkpoint_fails_cleanly_not_an_exception(self):
        runtime = _make_workflow_runtime(EchoNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w1", nodes=[WorkflowNode(node_id="a", worker_type="EchoNodeWorker")],
            entry_node="a",
        )
        result = await runtime.resume(d, "instance-that-was-never-checkpointed")
        assert result.success is False
        assert "no checkpoint" in result.error.lower()

    @pytest.mark.asyncio
    async def test_resume_rejects_mismatched_workflow_id(self):
        CountingNodeWorker.reset()
        runtime = _make_workflow_runtime(CountingNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w-original", nodes=[WorkflowNode(node_id="a", worker_type="CountingNodeWorker")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi")

        wrong_d = WorkflowDefinition(
            workflow_id="w-different", nodes=[WorkflowNode(node_id="a", worker_type="CountingNodeWorker")],
            entry_node="a",
        )
        resumed = await runtime.resume(wrong_d, result.instance_id)
        assert resumed.success is False
        assert "mismatch" in resumed.error.lower()

    @pytest.mark.asyncio
    async def test_resume_skips_completed_node_and_only_reruns_pending(self):
        """The core value proposition: a node that already finished before
        the (simulated) crash must not be re-invoked on resume -- proven
        via an invocation counter, not just by checking the final result
        looks right (which a harmless full re-run would also produce)."""
        CountingNodeWorker.reset()
        runtime = _make_workflow_runtime(CountingNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w-partial", name="partial",
            nodes=[WorkflowNode(node_id="a", worker_type="CountingNodeWorker"),
                   WorkflowNode(node_id="b", worker_type="CountingNodeWorker")],
            edges=[WorkflowEdge(from_node="a", to_node="b")],
            entry_node="a",
        )
        instance_id = "sim-crash-instance"

        # Simulate a checkpoint left behind by a process that completed
        # node 'a' and then crashed before node 'b' ever started -- written
        # directly, not via a real execute() run, so this test does not
        # depend on execute()'s own checkpoint-writing behavior to set up
        # its fixture (kept independent of the code path being tested).
        await runtime._save_checkpoint(instance_id, "w-partial", {
            "a": WorkflowNodeState(node_id="a", status=NodeStatus.COMPLETED,
                                    result=WorkerResult(success=True, output="done:a")),
            "b": WorkflowNodeState(node_id="b"),
        })

        result = await runtime.resume(d, instance_id, query="hi")

        assert result.success is True
        assert CountingNodeWorker.invocations == ["b"]  # 'a' was NOT re-invoked
        assert result.node_results["a"].output == "done:a"  # reused from checkpoint
        assert result.node_results["b"].output == "done:b"  # actually executed

    @pytest.mark.asyncio
    async def test_resume_resets_a_running_node_and_reexecutes_it(self):
        """Safety-critical: a node whose last known status was RUNNING at
        checkpoint time must be re-executed from scratch on resume, never
        assumed complete -- whether it actually finished before the crash
        is unknowable, and this project's Verification principle applies:
        RUNNING is not evidence of completion."""
        CountingNodeWorker.reset()
        runtime = _make_workflow_runtime(CountingNodeWorker)
        d = WorkflowDefinition(
            workflow_id="w-crash-mid-node",
            nodes=[WorkflowNode(node_id="a", worker_type="CountingNodeWorker")],
            entry_node="a",
        )
        instance_id = "sim-crash-mid-node"
        await runtime._save_checkpoint(instance_id, "w-crash-mid-node", {
            "a": WorkflowNodeState(node_id="a", status=NodeStatus.RUNNING,
                                    started_at=1.0),  # never completed before "crash"
        })

        result = await runtime.resume(d, instance_id, query="hi")

        assert result.success is True
        assert CountingNodeWorker.invocations == ["a"]  # re-run, not skipped
        assert result.node_results["a"].output == "done:a"

    @pytest.mark.asyncio
    async def test_resume_survives_a_real_process_restart(self):
        """The actual point of DEBT-003: prove durability across a genuine
        process boundary, not just within one Python process's memory.
        Two entirely separate WorkflowRuntime/EventStream/SQLiteEventStore
        instances, sharing only an on-disk file path -- the second one is
        constructed with no reference to any object the first one created,
        the same way a freshly-restarted process would be."""
        CountingNodeWorker.reset()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "events.db")
            d = WorkflowDefinition(
                workflow_id="w-restart", name="restart",
                nodes=[WorkflowNode(node_id="a", worker_type="CountingNodeWorker"),
                       WorkflowNode(node_id="b", worker_type="CountingNodeWorker")],
                edges=[WorkflowEdge(from_node="a", to_node="b")],
                entry_node="a",
            )

            # "Before the restart": run node 'a' to completion, then
            # simulate the crash by simply not calling execute() again --
            # the checkpoint execute() already wrote for node 'a' is all
            # that's left once this whole block ends and `stream_before`
            # goes out of scope.
            stream_before = EventStream(SQLiteEventStore(db_path=db_path))
            runtime_before = _make_workflow_runtime(CountingNodeWorker, event_stream=stream_before)
            partial = WorkflowDefinition(
                workflow_id="w-restart", name="restart",
                nodes=[WorkflowNode(node_id="a", worker_type="CountingNodeWorker")],
                entry_node="a",
            )
            first_run = await runtime_before.execute(partial, query="hi")
            assert first_run.success is True
            instance_id = first_run.instance_id
            del stream_before, runtime_before  # nothing after this point may touch process-1 objects

            # "After the restart": a fresh process, fresh objects, only the
            # SQLite file on disk is shared.
            stream_after = EventStream(SQLiteEventStore(db_path=db_path))
            runtime_after = _make_workflow_runtime(CountingNodeWorker, event_stream=stream_after)
            resumed = await runtime_after.resume(d, instance_id, query="hi")

            assert resumed.success is True
            assert CountingNodeWorker.invocations == ["a", "b"]  # 'a' from before restart, 'b' after
            assert resumed.node_results["a"].output == "done:a"
            assert resumed.node_results["b"].output == "done:b"


    @pytest.mark.asyncio
    async def test_duplicate_checkpoint_write_does_not_corrupt_retrieval(self):
        """Freeze-audit idempotency check: a checkpoint write retried after
        e.g. a timeout whose write actually succeeded must not corrupt
        state. EventStream.create_checkpoint() is a plain append -- this
        proves the append-only design already gives this for free, not
        that WorkflowRuntime adds any special-case handling."""
        runtime = _make_workflow_runtime()
        name = runtime._checkpoint_name("dup-instance")
        payload = {"workflow_id": "w", "instance_id": "dup-instance",
                   "node_states": {"a": {"status": "completed"}}}
        await runtime._event_stream.create_checkpoint(name, payload=payload)
        await runtime._event_stream.create_checkpoint(name, payload=payload)  # duplicate

        result = await runtime._event_stream.get_checkpoint(name)
        assert result.payload == payload

    @pytest.mark.asyncio
    async def test_concurrent_checkpoint_writes_do_not_corrupt_retrieval(self):
        """Two concurrent writers to the same checkpoint name (e.g. two
        overlapping node completions racing, however unlikely given
        _execute_from's own sequencing) must resolve to one coherent
        payload, never a torn/merged one -- append-only + latest-sequence-
        wins retrieval gives this structurally, not via any lock
        WorkflowRuntime itself holds."""
        runtime = _make_workflow_runtime()
        name = runtime._checkpoint_name("race-instance")
        payload_a = {"workflow_id": "w", "instance_id": "race-instance",
                     "node_states": {"a": {"status": "completed"}}}
        payload_b = {"workflow_id": "w", "instance_id": "race-instance",
                     "node_states": {"a": {"status": "completed"}, "b": {"status": "completed"}}}

        await asyncio.gather(
            runtime._event_stream.create_checkpoint(name, payload=payload_a),
            runtime._event_stream.create_checkpoint(name, payload=payload_b),
        )

        result = await runtime._event_stream.get_checkpoint(name)
        assert result.payload in (payload_a, payload_b)  # one coherent payload, not a corrupted merge


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
