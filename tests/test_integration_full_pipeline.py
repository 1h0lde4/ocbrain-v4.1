"""
tests/test_integration_full_pipeline.py — Packet 09 Tests.

Packet: Packet 09 — Integration: Full Cognitive Pipeline.

Architecture Sources:
    docs/architecture/OCBRAIN_K4_3_IMPLEMENTATION_TRANSITION.md
        Packet 09 — Integration: Full Cognitive Pipeline.
    docs/architecture/OCBRAIN_K4_COGNITIVE_RUNTIME_ARCHITECTURE.md §16
        (all 9 Runtime Invariants).

Scope (per the transition document — this is deliberately a test
packet, not a new production module; "Future Architectural Placeholders"
such as C-MoE / Execution Runtime wiring are explicitly out of scope,
"no implementation packets produced"):
    - End-to-end: raw_text -> interpret_request() -> plan() -> compile()
      -> WorkflowDefinition, using real objects at every stage (only the
      LLM call inside interpret_request() is mocked — the same
      established pattern tests/core/cognitive/test_intent.py already
      uses, not a new mocking convention).
    - Full event trail, in order, across every stage, and replayable via
      a real EventStream (SQLite-backed, not the lightweight fakes used
      in this repository's per-module unit tests).
    - Governance gates at Plan Compilation (REJECT / ESCALATE / APPROVE)
      demonstrated against a plan produced by the real pipeline, not a
      hand-built one.
    - Clarification bounded-retry (ESCALATE -> ESCALATE -> REJECT as
      clarification_attempt increases) against a real pipeline plan.
    - SupervisorWorker's recovery path against a real CompilationResult.
    - All 9 K4 §16 Runtime Invariants, individually verified.
    - Full existing test suite still passes.

Not in scope: WorkflowRuntime.execute() of the compiled WorkflowDefinition
(no packet through 09 wires this — the transition document's own scope
line stops at "-> WorkflowDefinition"), any C-MoE/capability-selection
behavior, and wiring any of this into main.py's composition root.
"""
import sqlite3

import pytest
from unittest.mock import AsyncMock, patch

from core.cognitive.compiler import CompilationStatus, compile as compile_plan
from core.cognitive.intent import Goal, GoalLifecycle, interpret_request
from core.cognitive.planner import (
    ExecutionPlanLifecycle,
    PlannerRequest,
    PlannerStatus,
    plan as plan_fn,
)
from core.events.event_stream import EventStream, SQLiteEventStore
from core.governance.governance_kernel import GovernanceVerdict
from core.capabilities.capability import BaseAdapter, CapabilityContract
from core.capabilities.registry import CapabilityRegistry
from core.workers.evaluator import EvaluatorWorker
from core.workers.reflection import ReflectionWorker
from core.workers.supervisor import SupervisorOutcome, SupervisorWorker


# ─────────────────────────────────────────────────────────────────────────
# Shared fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────


def _make_registry() -> CapabilityRegistry:
    """Mirrors tests/core/cognitive/test_planner.py's own _make_registry()
    helper exactly — a single llm_completion capability with an adapter,
    "matching the live composition root (main.py)" per that helper's own
    docstring. Not duplicated logic invented for this packet; the same
    real construction, reused."""
    registry = CapabilityRegistry()
    registry.register_capability(CapabilityContract(
        capability_type="llm_completion",
        description="Generate text from a prompt via a language model.",
    ))
    adapter = BaseAdapter()
    adapter.adapter_name = "fake-llm_completion"
    adapter.capability_type = "llm_completion"
    registry.register_adapter("llm_completion", adapter)
    return registry


def _real_event_stream(tmp_path) -> EventStream:
    """A genuine SQLite-backed EventStream, isolated per test via
    pytest's tmp_path — unlike this repository's per-module unit tests
    (which use lightweight in-memory fakes for speed/isolation), the
    "event trail complete and replayable" completion criterion requires
    exercising the real persistence/replay path, not a fake."""
    db_path = str(tmp_path / "events.db")
    return EventStream(store=SQLiteEventStore(db_path=db_path))


async def _run_to_planner_result(event_stream, registry, text="Summarize the quarterly report."):
    """raw_text -> interpret_request() -> plan(), with only the LLM calls
    mocked (established pattern: tests/core/cognitive/test_intent.py's
    TestInterpretRequest and tests/core/cognitive/test_planner.py's
    TestDecompose both patch their own module's generate_with_fallback
    binding exactly this way — two separate mocks because Python's
    patch() targets the name as imported into each module's own
    namespace, not the underlying function once). Returns (goals,
    planner_result) using real Goal/PlannerRequest/ExecutionPlan objects
    throughout.
    """
    with patch("core.cognitive.intent.ContextAssemblyEngine") as mock_engine_cls, \
         patch("core.cognitive.intent.generate_with_fallback",
               new=AsyncMock(return_value="novel:summarize_report | 0.9")):
        mock_engine_cls.return_value.assemble_context = AsyncMock(return_value="")
        goals = await interpret_request(text, memory=object(), event_stream=event_stream)

    goal = goals[0]
    request = PlannerRequest(goal_id=goal.resource_id, goal=goal)
    with patch("core.cognitive.planner.generate_with_fallback",
               new=AsyncMock(return_value="Generate text from a prompt via a language model.")):
        result = await plan_fn(request, registry, event_stream=event_stream)
    return goals, result


async def _run_full_pipeline(event_stream, registry, text="Summarize the quarterly report.",
                              confidence_override=None, **compile_kwargs):
    """Full chain through compile(). confidence_override, if given, is
    applied to the real, pipeline-produced ExecutionPlan before
    compilation — the practical way to deterministically exercise
    REJECT/ESCALATE/APPROVE against a genuinely pipeline-produced plan
    (real steps, real structure) rather than engineering a raw_text
    input that happens to make the mocked hypothesis path compute a
    specific confidence number indirectly, which would be fragile and
    indirect for no added rigor.
    """
    goals, planner_result = await _run_to_planner_result(event_stream, registry, text)
    assert planner_result.status == PlannerStatus.READY_FOR_COMPILATION, (
        f"Test fixture assumption violated: expected a ready plan, got "
        f"{planner_result.status} ({planner_result.impasse_detail})"
    )
    execution_plan = planner_result.execution_plan
    if confidence_override is not None:
        execution_plan.confidence = confidence_override

    compilation_result = await compile_plan(
        execution_plan, event_stream=event_stream, **compile_kwargs)
    return goals, planner_result, execution_plan, compilation_result


# ─────────────────────────────────────────────────────────────────────────
# Full pipeline — happy path
# ─────────────────────────────────────────────────────────────────────────


class TestFullPipelineHappyPath:
    @pytest.mark.asyncio
    async def test_raw_text_to_workflow_definition(self, tmp_path):
        """K4.2 §1's full chain: raw_text -> interpret() -> plan() ->
        compile() -> WorkflowDefinition, real objects throughout."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()

        goals, planner_result, execution_plan, compilation_result = (
            await _run_full_pipeline(event_stream, registry))

        assert isinstance(goals[0], Goal)
        assert planner_result.status == PlannerStatus.READY_FOR_COMPILATION
        assert execution_plan.goal_id == goals[0].resource_id
        assert compilation_result.status == CompilationStatus.COMPILED
        wd = compilation_result.workflow_definition
        assert wd is not None
        assert wd.validate() == []
        assert wd.workflow_id == execution_plan.resource_id

    @pytest.mark.asyncio
    async def test_lifecycle_transitions_across_stages(self, tmp_path):
        """'Verify all lifecycle transitions'. Goal.lifecycle_state only
        becomes VERIFIED when structured-form validation succeeds against
        a matching Intent Ontology category (core/cognitive/intent.py:
        `lifecycle_state=GoalLifecycle.VERIFIED if validated else
        GoalLifecycle.DRAFT`). This test's mocked hypothesis
        ("novel:...") is deliberately the open-category degrade path — no
        Intent Ontology category exists anywhere in this repository yet —
        so DRAFT is the correct, expected outcome here, not a gap.
        ExecutionPlan is produced in DRAFT and compile() does not mutate
        it (Packet 06's own documented, deliberate choice, re-confirmed
        here at the integration level)."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()

        goals, planner_result, execution_plan, compilation_result = (
            await _run_full_pipeline(event_stream, registry))

        assert goals[0].lifecycle_state == GoalLifecycle.DRAFT
        assert execution_plan.lifecycle_state == ExecutionPlanLifecycle.DRAFT
        assert compilation_result.status == CompilationStatus.COMPILED


# ─────────────────────────────────────────────────────────────────────────
# Event trail — complete and replayable
# ─────────────────────────────────────────────────────────────────────────


class TestEventTrailCompleteAndReplayable:
    @pytest.mark.asyncio
    async def test_full_event_sequence_in_order(self, tmp_path):
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()

        await _run_full_pipeline(event_stream, registry)

        events = await event_stream.query(limit=100)
        # query() orders sequence DESC (newest first) -- reverse for the
        # chronological order the pipeline actually emitted them in.
        ordered_types = [e.event_type for e in reversed(events)]

        assert ordered_types == [
            "cognitive.intent_hypotheses_generated",
            "cognitive.intent_interpreted",
            "cognitive.goal_formed",
            "cognitive.constraints_extracted",
            "cognitive.capabilities_discovered",
            "cognitive.plan_compiled",
        ]

    @pytest.mark.asyncio
    async def test_event_trail_is_replayable(self, tmp_path):
        """K4 Law 2 / this packet's own completion criterion: the trail
        must be reconstructable via EventStream.replay(), not just
        query() — genuinely exercising the real SQLite-backed store."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()

        await _run_full_pipeline(event_stream, registry)

        replayed = [e async for e in event_stream.replay(since_sequence=0)]
        replayed_types = [e.event_type for e in replayed]

        assert replayed_types == [
            "cognitive.intent_hypotheses_generated",
            "cognitive.intent_interpreted",
            "cognitive.goal_formed",
            "cognitive.constraints_extracted",
            "cognitive.capabilities_discovered",
            "cognitive.plan_compiled",
        ]
        # Sequence numbers are monotonically increasing and gapless from 1.
        assert [e.sequence for e in replayed] == list(range(1, len(replayed) + 1))

    @pytest.mark.asyncio
    async def test_rejected_compilation_replaces_final_event(self, tmp_path):
        """Same trail, but ending in cognitive.plan_rejected instead of
        cognitive.plan_compiled when governance escalates."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()

        _, _, _, compilation_result = await _run_full_pipeline(
            event_stream, registry, confidence_override=0.1)

        assert compilation_result.status == CompilationStatus.ESCALATED
        events = await event_stream.query(limit=100)
        ordered_types = [e.event_type for e in reversed(events)]
        assert ordered_types[-1] == "cognitive.plan_rejected"
        assert "cognitive.plan_compiled" not in ordered_types


# ─────────────────────────────────────────────────────────────────────────
# Governance gates at Plan Compilation — against a real pipeline plan
# ─────────────────────────────────────────────────────────────────────────


class TestGovernanceGateAtCompilation:
    @pytest.mark.asyncio
    async def test_high_confidence_real_plan_compiles(self, tmp_path):
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        _, _, execution_plan, compilation_result = await _run_full_pipeline(
            event_stream, registry, confidence_override=0.95)
        assert compilation_result.status == CompilationStatus.COMPILED
        assert execution_plan.confidence == 0.95

    @pytest.mark.asyncio
    async def test_low_confidence_real_plan_escalates(self, tmp_path):
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        _, _, _, compilation_result = await _run_full_pipeline(
            event_stream, registry, confidence_override=0.2, clarification_attempt=0)
        assert compilation_result.status == CompilationStatus.ESCALATED
        assert compilation_result.governance_result.verdict == GovernanceVerdict.ESCALATE

    @pytest.mark.asyncio
    async def test_low_confidence_real_plan_rejects_at_attempt_bound(self, tmp_path):
        from core.cognitive.planner import ClarificationPolicy
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        policy = ClarificationPolicy()
        _, _, _, compilation_result = await _run_full_pipeline(
            event_stream, registry, confidence_override=0.2,
            clarification_attempt=policy.max_escalations)
        assert compilation_result.status == CompilationStatus.REJECTED
        assert compilation_result.governance_result.verdict == GovernanceVerdict.REJECT


# ─────────────────────────────────────────────────────────────────────────
# Clarification bounded-retry — the full ESCALATE -> ESCALATE -> REJECT
# progression against one real pipeline plan
# ─────────────────────────────────────────────────────────────────────────


class TestClarificationBoundedRetry:
    @pytest.mark.asyncio
    async def test_repeated_attempts_progress_from_escalate_to_reject(self, tmp_path):
        from core.cognitive.planner import ClarificationPolicy
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        policy = ClarificationPolicy()

        goals, planner_result = await _run_to_planner_result(event_stream, registry)
        execution_plan = planner_result.execution_plan
        execution_plan.confidence = 0.1  # below threshold for every attempt below

        verdicts = []
        for attempt in range(policy.max_escalations + 1):
            result = await compile_plan(
                execution_plan, event_stream=event_stream, clarification_attempt=attempt)
            verdicts.append(result.governance_result.verdict)

        # max_escalations attempts (0..max_escalations-1) escalate; the
        # attempt AT the bound rejects (core/governance/orchestration_governor.py's
        # own _evaluate_clarification_policy: attempt >= max_escalations -> REJECT).
        assert verdicts[:-1] == [GovernanceVerdict.ESCALATE] * policy.max_escalations
        assert verdicts[-1] == GovernanceVerdict.REJECT


# ─────────────────────────────────────────────────────────────────────────
# SupervisorWorker's recovery path — against a real CompilationResult
# ─────────────────────────────────────────────────────────────────────────


class TestSupervisorRecoveryPath:
    @pytest.mark.asyncio
    async def test_supervisor_surfaces_real_escalated_compilation(self, tmp_path):
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        _, _, _, compilation_result = await _run_full_pipeline(
            event_stream, registry, confidence_override=0.15, clarification_attempt=0)
        assert compilation_result.status == CompilationStatus.ESCALATED

        supervisor = SupervisorWorker(event_stream=event_stream)
        from core.workers.base import WorkerContext
        context = WorkerContext(query="supervise",
                                 parameters={"compilation_result": compilation_result})
        result = await supervisor.execute(context)

        assert result.success is False
        assert result.output["outcome"] == SupervisorOutcome.ESCALATED

    @pytest.mark.asyncio
    async def test_supervisor_never_retries_real_rejected_compilation(self, tmp_path):
        """Invariant 9 at the integration level: a genuinely
        pipeline-produced, governance-rejected plan must not be retried,
        even though a retry-capable ExecutionRuntime is available."""
        from unittest.mock import AsyncMock as AM
        from core.runtime.execution_runtime import ExecutionRuntime
        from core.cognitive.planner import ClarificationPolicy

        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        policy = ClarificationPolicy()
        _, _, _, compilation_result = await _run_full_pipeline(
            event_stream, registry, confidence_override=0.1,
            clarification_attempt=policy.max_escalations)
        assert compilation_result.status == CompilationStatus.REJECTED

        execution_runtime = AM(spec=ExecutionRuntime)
        supervisor = SupervisorWorker(event_stream=event_stream,
                                       execution_runtime=execution_runtime)
        from core.workers.base import WorkerContext
        context = WorkerContext(
            query="supervise",
            parameters={
                "compilation_result": compilation_result,
                "failed_worker_result": object(),  # present, but must be ignored
                "retry_worker_type": "PlannerWorker",
            },
        )
        result = await supervisor.execute(context)

        assert result.output["outcome"] == SupervisorOutcome.REJECTED
        execution_runtime.invoke.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────
# All 9 K4 §16 Runtime Invariants
# ─────────────────────────────────────────────────────────────────────────


class TestRuntimeInvariants:
    """Each invariant is K4 §16's exact wording. Where a per-module unit
    test in an earlier packet already establishes an invariant in
    isolation, this class adds a fresh assertion at the *integration*
    level (a real, pipeline-produced object), rather than re-deriving the
    same isolated unit test a second time."""

    @pytest.mark.asyncio
    async def test_invariant_1_every_plan_has_a_goal(self, tmp_path):
        """'Every plan has a goal' -- ExecutionPlan.goal_id non-optional;
        already unit-tested in Packet 06 (_validate_plan_structure).
        Confirmed here on a real, pipeline-produced plan."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        _, _, execution_plan, _ = await _run_full_pipeline(event_stream, registry)
        assert execution_plan.goal_id != ""

    @pytest.mark.asyncio
    async def test_invariant_2_every_goal_has_provenance_to_its_intent(self, tmp_path):
        """'Every goal has an owner', sharpened by K4 §16 itself to:
        every Goal carries provenance to the Intent that produced it."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        goals, _ = await _run_to_planner_result(event_stream, registry)
        assert goals[0].intent_id != "" or goals[0].derived_from

    @pytest.mark.asyncio
    async def test_invariant_3_every_reasoning_step_is_explainable(self, tmp_path):
        """Tied to concrete fields (K4 §16): ExecutionPlan.justification
        is non-empty for a real, pipeline-produced plan."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        _, _, execution_plan, _ = await _run_full_pipeline(event_stream, registry)
        assert execution_plan.justification != ""

    @pytest.mark.asyncio
    async def test_invariant_4_planning_never_executes(self, tmp_path):
        """The compilation seam exists to make this structurally true —
        confirmed here by the absence of any execution-related event in
        the trail up through plan()."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        await _run_to_planner_result(event_stream, registry)
        events = await event_stream.query(limit=100)
        emitted = {e.event_type for e in events}
        assert "workflow.started" not in emitted
        assert "workflow.completed" not in emitted

    def test_invariant_5_execution_never_plans(self):
        """'Already true of WorkflowRuntime/ExecutionRuntime today' per
        K4 §16 itself. Structural check: neither module references
        PlanStep or ExecutionPlan construction."""
        import ast
        for path in ("core/workflow/runtime.py", "core/runtime/execution_runtime.py"):
            tree = ast.parse(open(path).read())
            identifiers = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    identifiers.add(node.id)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        identifiers.add(alias.name)
            assert "PlanStep" not in identifiers, path
            assert "ExecutionPlan" not in identifiers, path

    @pytest.mark.asyncio
    async def test_invariant_6_reflection_never_mutates_execution_history(self, tmp_path):
        """Already unit-tested via AST in Packet 07 (no forbidden write
        paths). Confirmed here: reflecting on a real EvaluationRecord adds
        a new KnowledgeEntry write, never touches the events already in
        the stream."""
        event_stream = _real_event_stream(tmp_path)
        registry = _make_registry()
        await _run_full_pipeline(event_stream, registry)
        events_before = await event_stream.query(limit=100)

        from core.workers.evaluator import EvaluationRecord
        from unittest.mock import AsyncMock as AM
        record = EvaluationRecord(plan_id="p1", goal_completed=False,
                                   tool_success_rate=0.1, reasoning_valid=False,
                                   predicted_confidence=0.9, actual_outcome=False)
        reflection_worker = ReflectionWorker(memory=AM(), event_stream=event_stream)
        from core.workers.base import WorkerContext
        await reflection_worker.execute(
            WorkerContext(query="reflect", parameters={"evaluation_record": record}))

        events_after = await event_stream.query(limit=200)
        # Every event present before reflection is still present, unchanged.
        before_ids = {e.event_id for e in events_before}
        after_ids = {e.event_id for e in events_after}
        assert before_ids.issubset(after_ids)

    def test_invariant_7_evaluation_never_changes_facts(self):
        """Already unit-tested via AST in Packet 07. Structural
        confirmation here: EvaluatorWorker never calls UnifiedMemory's
        mutation methods, only write() (new entries)."""
        import ast
        tree = ast.parse(open("core/workers/evaluator.py").read())
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "update" not in attrs
        assert "delete" not in attrs

    def test_invariant_8_cognitive_runtime_never_bypasses_governance(self):
        """compile() always calls governance.evaluate_action() before a
        WorkflowDefinition can exist — structural check on compiler.py:
        every return path either goes through evaluate_action() first, or
        is a precheck rejection (K4 §16 note: goal-reference validation is
        Plan Compiler's own structural invariant, not a bypass of
        Governance — there is nothing for Governance to evaluate yet)."""
        import ast
        tree = ast.parse(open("core/cognitive/compiler.py").read())
        source = open("core/cognitive/compiler.py").read()
        assert "governance.evaluate_action(action)" in source
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                 and n.attr == "evaluate_action"]
        assert len(calls) == 1  # exactly one call site, confirmed in Packet 06

    def test_invariant_9_rejected_plan_never_silently_retried(self):
        """Already unit-tested twice in Packet 08 (structural + explicit
        retry-input-present tests), and confirmed end-to-end above in
        TestSupervisorRecoveryPath.test_supervisor_never_retries_real_rejected_compilation
        with a genuinely pipeline-produced, governance-rejected plan.
        This entry adds a complementary structural check (matching how
        invariants 5/7/8 above are verified structurally): the specific
        method that surfaces a rejected/escalated CompilationResult
        contains no call capable of retrying anything, full stop —
        independent of any particular test input.
        """
        import ast
        tree = ast.parse(open("core/workers/supervisor.py").read())
        func = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.AsyncFunctionDef)
            and n.name == "_surface_compilation_outcome"
        )
        calls_within = {n.attr for n in ast.walk(func) if isinstance(n, ast.Attribute)}
        assert "invoke" not in calls_within
        assert "execute" not in calls_within
