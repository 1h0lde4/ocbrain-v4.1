"""
tests/test_debt_020_false_completion.py — DEBT-020 (Kernel freeze blocker).

Targeted adversarial tests for the false-completion fix, per Moncif's
explicit approval: (1) Constraint gets an actual checkable value, (2)
success distinguishes complete vs partial/non-conforming output, (3) the
scope/constraint check happens before final response acceptance.

Every claim in the originating false-completion report
(docs/Bugs Hunt & fix reports/FALSE_COMPLETION_KERNEL_AUDIT_PRE_IMPLEMENTATION_REPORT.md)
was independently re-verified against current `main` before this fix was
written (see docs/architecture/decisions/ADR_KERNEL_04_FALSE_COMPLETION_FIX.md)
-- these tests exist to prove the fix, not just that a plausible-looking
change was made.

Deliberately out of scope, per Moncif's explicit instruction: resumability,
generalized coverage infrastructure, continuous verification, the
Verification/Critic/Evidence branch. Not tested here.
"""
import asyncio
import pytest

from core.cognitive.planner import Constraint, ConstraintKind, ConstraintSource
from core.cognitive.planner import _extract_word_count_constraints, _extract_explicit_constraints
from core.workflow.definition import WorkflowDefinition, WorkflowEdge, WorkflowNode
from core.workflow.runtime import (
    WorkflowRuntime, _check_constraints, _measure_output,
)
from core.runtime.worker_registry import WorkerRegistry
from core.runtime.execution_runtime import ExecutionRuntime
from core.workers.base import AbstractCognitiveWorker, WorkerContext, WorkerResult
from core.governance.governance_kernel import get_governance_kernel
from core.events.event_stream import get_event_stream


# ── Layer 1: Constraint itself ──────────────────────────────────────────────


class TestConstraintCheckableValue:
    def test_unmeasurable_by_default(self):
        c = Constraint(rationale="must be polite")
        assert c.is_measurable() is False

    def test_measurable_once_all_three_fields_present(self):
        c = Constraint(measure="word_count", comparator=">=", target=100)
        assert c.is_measurable() is True

    @pytest.mark.parametrize("comparator,target,actual,expected", [
        (">=", 500, 500, True), (">=", 500, 499, False), (">=", 500, 501, True),
        ("<=", 200, 200, True), ("<=", 200, 201, False),
        ("==", 100, 100, True), ("==", 100, 99, False),
        (">", 50, 51, True), (">", 50, 50, False),
        ("<", 50, 49, True), ("<", 50, 50, False),
    ])
    def test_is_satisfied_by_every_comparator_and_boundary(self, comparator, target, actual, expected):
        c = Constraint(measure="word_count", comparator=comparator, target=target)
        assert c.is_satisfied_by(actual) is expected


# ── Layer 2: word-count extraction ──────────────────────────────────────────


class TestWordCountExtraction:
    @pytest.mark.parametrize("text,expected_comparator,expected_target", [
        ("Write a story that is at least 500 words long.", ">=", 500.0),
        ("Keep the summary to no more than 200 words.", "<=", 200.0),
        ("The essay must be exactly 1000 words.", "==", 1000.0),
        ("Write more than 50 words about the sea.", ">", 50.0),
        ("Keep it under 30 words.", "<", 30.0),
        ("Write a 300 word poem about the ocean.", ">=", 300.0),  # bare "N words" = floor, not exact
        ("Write a 1,200-word article.", ">=", 1200.0),  # comma-separated thousands
    ])
    def test_extracts_correct_comparator_and_target(self, text, expected_comparator, expected_target):
        constraints = _extract_explicit_constraints(text)
        measurable = [c for c in constraints if c.is_measurable()]
        assert len(measurable) == 1
        assert measurable[0].measure == "word_count"
        assert measurable[0].comparator == expected_comparator
        assert measurable[0].target == expected_target
        assert measurable[0].kind == ConstraintKind.HARD
        assert measurable[0].source == ConstraintSource.EXPLICIT

    def test_no_word_count_phrase_produces_no_measurable_constraint(self):
        constraints = _extract_explicit_constraints("Tell me about the weather today.")
        assert not any(c.is_measurable() for c in constraints)

    def test_qualified_phrase_does_not_also_produce_a_duplicate_bare_match(self):
        """'at least 500 words' must not ALSO match the bare 'N words'
        fallback pattern and produce two constraints for one request --
        proves the shared claimed_spans overlap tracking works across the
        two pattern lists, not just within each one independently."""
        constraints = _extract_explicit_constraints("Write at least 500 words.")
        measurable = [c for c in constraints if c.is_measurable() and c.measure == "word_count"]
        assert len(measurable) == 1
        assert measurable[0].comparator == ">="  # the qualified reading, not a stray "==" duplicate

    def test_multiple_distinct_word_count_constraints_in_one_request(self):
        constraints = _extract_explicit_constraints(
            "Write at least 100 words for the intro and no more than 50 words for the conclusion."
        )
        measurable = [c for c in constraints if c.is_measurable()]
        assert len(measurable) == 2
        comparators = sorted(c.comparator for c in measurable)
        assert comparators == ["<=", ">="]


# ── Layer 3: the pure constraint-check function ─────────────────────────────


class TestCheckConstraints:
    def test_empty_constraints_list_never_violates(self):
        assert _check_constraints([], "short") == []

    def test_satisfied_hard_constraint_produces_no_violation(self):
        c = Constraint(kind=ConstraintKind.HARD, measure="word_count", comparator=">=", target=3)
        assert _check_constraints([c], "one two three four") == []

    def test_violated_hard_constraint_is_reported(self):
        c = Constraint(kind=ConstraintKind.HARD, measure="word_count", comparator=">=", target=500)
        violations = _check_constraints([c], "one two three")
        assert len(violations) == 1
        assert "word_count" in violations[0] and "500" in violations[0]

    def test_soft_constraint_violation_is_not_enforced(self):
        """Advisory, not blocking -- matches how _detect_contradictions
        already treats HARD vs SOFT elsewhere in this codebase."""
        c = Constraint(kind=ConstraintKind.SOFT, measure="word_count", comparator=">=", target=500)
        assert _check_constraints([c], "one two three") == []

    def test_unmeasurable_constraint_is_skipped_not_flagged(self):
        c = Constraint(kind=ConstraintKind.HARD, rationale="must not include profanity")
        assert _check_constraints([c], "anything at all") == []

    def test_unsupported_measure_is_skipped_not_flagged(self):
        """A measure this module doesn't know how to compute (e.g.
        item_count, not implemented) must not be silently treated as
        violated -- you cannot fail a check you were never able to
        perform. Only word_count is supported today."""
        c = Constraint(kind=ConstraintKind.HARD, measure="item_count", comparator=">=", target=5)
        assert _check_constraints([c], "one two three") == []

    def test_non_string_output_is_skipped_not_flagged(self):
        c = Constraint(kind=ConstraintKind.HARD, measure="word_count", comparator=">=", target=5)
        assert _check_constraints([c], {"not": "a string"}) == []
        assert _check_constraints([c], None) == []
        assert _check_constraints([c], 42) == []

    def test_mixed_satisfied_and_violated_reports_only_the_violated_one(self):
        satisfied = Constraint(kind=ConstraintKind.HARD, measure="word_count", comparator=">=", target=2)
        violated = Constraint(kind=ConstraintKind.HARD, measure="word_count", comparator="<=", target=1)
        violations = _check_constraints([satisfied, violated], "one two three")
        assert len(violations) == 1

    def test_measure_output_word_count_is_whitespace_split(self):
        assert _measure_output("one two three", "word_count") == 3.0
        assert _measure_output("", "word_count") == 0.0
        assert _measure_output(123, "word_count") is None  # not a string
        assert _measure_output("text", "unknown_measure") is None


# ── Layer 4: end-to-end through WorkflowRuntime ─────────────────────────────


class WordCountWorker(AbstractCognitiveWorker):
    """Returns a fixed word count regardless of what's asked, so tests can
    deterministically land on either side of a constraint's boundary."""
    worker_type = "WordCountWorker"

    async def _run(self, context: WorkerContext) -> WorkerResult:
        n = (context.metadata or {}).get("word_count", 3)
        return WorkerResult(success=True, output=" ".join(f"w{i}" for i in range(n)))


def _make_workflow_runtime(*worker_classes):
    registry = WorkerRegistry()
    for cls in worker_classes:
        registry.register(cls)
    stream = get_event_stream()
    execution_runtime = ExecutionRuntime(
        worker_registry=registry, governance=get_governance_kernel(), event_stream=stream,
    )
    return WorkflowRuntime(execution_runtime=execution_runtime, event_stream=stream)


class TestWorkflowRuntimeEndToEnd:
    """The core invariant Moncif named directly: successful completion
    must mean the requested task actually satisfied its applicable
    constraints. These construct WorkflowDefinition.constraints by hand
    (the same way an earlier session's tests construct WorkflowDefinition
    directly, bypassing the full Planner/Compiler pipeline) -- the
    real-pipeline threading (extraction -> ExecutionPlan -> compile() ->
    WorkflowDefinition) is proven separately in
    tests/test_integration_full_pipeline.py's
    TestConstraintsSurviveRealPipeline."""

    @pytest.mark.asyncio
    async def test_output_satisfying_constraint_reports_success(self):
        runtime = _make_workflow_runtime(WordCountWorker)
        d = WorkflowDefinition(
            workflow_id="w-ok", nodes=[WorkflowNode(node_id="a", worker_type="WordCountWorker")],
            entry_node="a",
            constraints=[Constraint(kind=ConstraintKind.HARD, measure="word_count",
                                     comparator=">=", target=5)],
        )
        result = await runtime.execute(d, query="hi", metadata={"word_count": 10})
        assert result.success is True
        assert result.constraint_violations == []

    @pytest.mark.asyncio
    async def test_output_violating_hard_constraint_reports_failure_not_silent_success(self):
        """The exact bug DEBT-020 is about: a node that runs to completion
        without error, but under-delivers against an explicit request,
        must not be reported as success."""
        runtime = _make_workflow_runtime(WordCountWorker)
        d = WorkflowDefinition(
            workflow_id="w-short", nodes=[WorkflowNode(node_id="a", worker_type="WordCountWorker")],
            entry_node="a",
            constraints=[Constraint(kind=ConstraintKind.HARD, measure="word_count",
                                     comparator=">=", target=500)],
        )
        result = await runtime.execute(d, query="hi", metadata={"word_count": 10})
        assert result.success is False
        assert len(result.constraint_violations) == 1
        assert "word_count" in result.error
        # The output itself is preserved, not discarded -- partial work
        # still has value; what changes is that it's no longer silently
        # reported as fully satisfying the request.
        assert result.output == " ".join(f"w{i}" for i in range(10))

    @pytest.mark.asyncio
    async def test_soft_constraint_violation_does_not_fail_the_workflow(self):
        runtime = _make_workflow_runtime(WordCountWorker)
        d = WorkflowDefinition(
            workflow_id="w-soft", nodes=[WorkflowNode(node_id="a", worker_type="WordCountWorker")],
            entry_node="a",
            constraints=[Constraint(kind=ConstraintKind.SOFT, measure="word_count",
                                     comparator=">=", target=500)],
        )
        result = await runtime.execute(d, query="hi", metadata={"word_count": 10})
        assert result.success is True
        assert result.constraint_violations == []

    @pytest.mark.asyncio
    async def test_no_constraints_behaves_exactly_as_before_this_fix(self):
        """Regression guard: every WorkflowDefinition constructed before
        this fix existed has an empty constraints list by default -- this
        must remain a true no-op for all of them, not just for the new
        tests written alongside the fix."""
        runtime = _make_workflow_runtime(WordCountWorker)
        d = WorkflowDefinition(
            workflow_id="w-none", nodes=[WorkflowNode(node_id="a", worker_type="WordCountWorker")],
            entry_node="a",
        )
        result = await runtime.execute(d, query="hi", metadata={"word_count": 1})
        assert result.success is True
        assert result.constraint_violations == []

    @pytest.mark.asyncio
    async def test_genuine_node_failure_is_not_relabeled_as_a_constraint_violation(self):
        """A real execution error and a constraint violation are different
        things with different messages -- constraint checking must not
        run (or muddy the error) when the node itself already failed."""
        class AlwaysFailsWorker(AbstractCognitiveWorker):
            worker_type = "AlwaysFailsWorker"

            async def _run(self, context):
                return WorkerResult(success=False, error="genuine execution error")

        runtime = _make_workflow_runtime(AlwaysFailsWorker)
        d = WorkflowDefinition(
            workflow_id="w-fail", nodes=[WorkflowNode(node_id="a", worker_type="AlwaysFailsWorker")],
            entry_node="a",
            constraints=[Constraint(kind=ConstraintKind.HARD, measure="word_count",
                                     comparator=">=", target=5)],
        )
        result = await runtime.execute(d, query="hi")
        assert result.success is False
        assert result.constraint_violations == []  # not what caused this failure
        assert result.error == "genuine execution error"
