"""
tests/core/cognitive/test_planner.py — Packet 01 Tests.

Architecture Sources:
    K4.2 §5, §11, §12, §15 (K4.2.3).

Tests:
    - Constraint dataclass fields match K4.2 §12
    - PlannerHint dataclass fields match K4.2 §12
    - PlannerRequest dataclass fields match K4.2 §12
    - PlannerResult dataclass fields match K4.2 §12
    - ImpasseRecord dataclass
    - extract_constraints() produces well-formed constraints
    - extract_constraints() emits cognitive.constraints_extracted event
    - Contradictory hard constraints yield rejected_precheck
    - build_planner_request() produces valid PlannerRequest with hints
    - CognitiveArtifact protocol not violated
    - No forbidden work present
"""
import asyncio
import dataclasses
import pytest

from core.cognitive.intent import (
    CognitiveArtifact,
    Goal,
    GoalLifecycle,
    Intent,
    IntentDimensions,
    IntentHypothesis,
    IntentLifecycle,
    IntentModality,
)
from core.cognitive.planner import (
    Constraint,
    ConstraintKind,
    ConstraintRelation,
    ConstraintSource,
    HintSource,
    ImpasseRecord,
    PlannerHint,
    PlannerRequest,
    PlannerResult,
    PlannerStatus,
    build_planner_request,
    check_precheck_rejection,
    extract_constraints,
)
from core.events.event_stream import EventStream


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _make_goal(
    description: str = "test goal",
    raw_request: str = "test request",
    confidence: float = 0.8,
    category: str = "test_category",
    sub_goals: list = None,
    lifecycle_state: str = GoalLifecycle.VERIFIED,
) -> Goal:
    """Create a Goal for testing."""
    return Goal(
        intent_id="test-intent-id",
        structured_form={
            "description": description,
            "category": category,
            "raw_request": raw_request,
        },
        confidence=confidence,
        sub_goals=sub_goals or [],
        derived_from=["test-intent-id"],
        lifecycle_state=lifecycle_state,
    )


class MockEventStream:
    """Minimal EventStream mock for testing event emission."""

    def __init__(self):
        self.events = []

    async def append(self, event_type, source, payload):
        self.events.append({
            "event_type": event_type,
            "source": source,
            "payload": payload,
        })


# ─────────────────────────────────────────────────────────────────────────
# Constraint dataclass — K4.2 §12
# ─────────────────────────────────────────────────────────────────────────

class TestConstraintDataclass:
    """Verify Constraint fields match K4.2 §12."""

    def test_fields_match_architecture(self):
        """K4.2 §12: kind, relation, source, rationale, validated_by."""
        c = Constraint()
        assert hasattr(c, "kind")
        assert hasattr(c, "relation")
        assert hasattr(c, "source")
        assert hasattr(c, "rationale")
        assert hasattr(c, "validated_by")

    def test_default_values(self):
        c = Constraint()
        assert c.kind == ConstraintKind.HARD
        assert c.relation == ConstraintRelation.SATISFIES
        assert c.source == ConstraintSource.EXPLICIT
        assert c.rationale == ""
        assert c.validated_by is None

    def test_kind_values(self):
        """K4.2 §12: kind: 'hard'|'soft'."""
        assert ConstraintKind.HARD == "hard"
        assert ConstraintKind.SOFT == "soft"

    def test_relation_values(self):
        """K4.2 §12: relation: 'satisfies'|'partially_satisfies'|
        'conflicts_with'."""
        assert ConstraintRelation.SATISFIES == "satisfies"
        assert ConstraintRelation.PARTIALLY_SATISFIES == "partially_satisfies"
        assert ConstraintRelation.CONFLICTS_WITH == "conflicts_with"

    def test_source_values(self):
        """K4.2 §12: source: 'explicit'|'inferred'|'policy'."""
        assert ConstraintSource.EXPLICIT == "explicit"
        assert ConstraintSource.INFERRED == "inferred"
        assert ConstraintSource.POLICY == "policy"

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(Constraint)

    def test_to_dict(self):
        c = Constraint(kind="hard", rationale="test")
        d = c.to_dict()
        assert isinstance(d, dict)
        assert d["kind"] == "hard"
        assert d["rationale"] == "test"

    def test_not_a_cognitive_artifact(self):
        """K4.2 §12: Constraint is embedded, NOT a Resource."""
        c = Constraint()
        assert not isinstance(c, CognitiveArtifact)


# ─────────────────────────────────────────────────────────────────────────
# PlannerHint dataclass — K4.2 §12
# ─────────────────────────────────────────────────────────────────────────

class TestPlannerHintDataclass:
    """Verify PlannerHint fields match K4.2 §12."""

    def test_fields_match_architecture(self):
        """K4.2 §12: kind, weight, source."""
        h = PlannerHint()
        assert hasattr(h, "kind")
        assert hasattr(h, "weight")
        assert hasattr(h, "source")

    def test_source_values(self):
        """K4.2 §12: source: 'intent_dimension'|'user_model'."""
        assert HintSource.INTENT_DIMENSION == "intent_dimension"
        assert HintSource.USER_MODEL == "user_model"

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(PlannerHint)

    def test_to_dict(self):
        h = PlannerHint(kind="prefer_speed", weight=0.5)
        d = h.to_dict()
        assert d["kind"] == "prefer_speed"
        assert d["weight"] == 0.5

    def test_not_a_cognitive_artifact(self):
        """K4.2 §12: PlannerHint is embedded, NOT a Resource."""
        h = PlannerHint()
        assert not isinstance(h, CognitiveArtifact)


# ─────────────────────────────────────────────────────────────────────────
# PlannerRequest dataclass — K4.2 §12
# ─────────────────────────────────────────────────────────────────────────

class TestPlannerRequestDataclass:
    """Verify PlannerRequest fields match K4.2 §12."""

    def test_fields_match_architecture(self):
        """K4.2 §12: goal_id, goal, context_view_ref, hints."""
        r = PlannerRequest()
        assert hasattr(r, "goal_id")
        assert hasattr(r, "goal")
        assert hasattr(r, "context_view_ref")
        assert hasattr(r, "hints")

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(PlannerRequest)

    def test_to_dict(self):
        r = PlannerRequest(goal_id="g1")
        d = r.to_dict()
        assert d["goal_id"] == "g1"

    def test_not_a_cognitive_artifact(self):
        """K4.2 §12: PlannerRequest is ephemeral, NOT a Resource."""
        r = PlannerRequest()
        assert not isinstance(r, CognitiveArtifact)


# ─────────────────────────────────────────────────────────────────────────
# PlannerResult dataclass — K4.2 §12
# ─────────────────────────────────────────────────────────────────────────

class TestPlannerResultDataclass:
    """Verify PlannerResult fields match K4.2 §12."""

    def test_fields_match_architecture(self):
        """K4.2 §12: status, execution_plan, impasse_detail."""
        r = PlannerResult()
        assert hasattr(r, "status")
        assert hasattr(r, "execution_plan")
        assert hasattr(r, "impasse_detail")
        assert hasattr(r, "constraints")

    def test_status_values(self):
        """K4.2 §12: status: 'ready_for_compilation'|'impasse'|
        'rejected_precheck'."""
        assert PlannerStatus.READY_FOR_COMPILATION == "ready_for_compilation"
        assert PlannerStatus.IMPASSE == "impasse"
        assert PlannerStatus.REJECTED_PRECHECK == "rejected_precheck"

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(PlannerResult)

    def test_to_dict(self):
        r = PlannerResult(status="impasse")
        d = r.to_dict()
        assert d["status"] == "impasse"


# ─────────────────────────────────────────────────────────────────────────
# ImpasseRecord dataclass — K4.2 §5, §12
# ─────────────────────────────────────────────────────────────────────────

class TestImpasseRecordDataclass:
    """Verify ImpasseRecord fields."""

    def test_fields(self):
        r = ImpasseRecord()
        assert hasattr(r, "reason")
        assert hasattr(r, "unresolved_subgoals")
        assert hasattr(r, "attempted_capabilities")

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(ImpasseRecord)


# ─────────────────────────────────────────────────────────────────────────
# extract_constraints() — K4.2 §5
# ─────────────────────────────────────────────────────────────────────────

class TestExtractConstraints:
    """Verify constraint extraction from Goals."""

    @pytest.mark.asyncio
    async def test_basic_extraction(self):
        """K4.2 §5: extract_constraints produces well-formed constraints."""
        goal = _make_goal(description="The system must handle errors gracefully")
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        assert isinstance(constraints, list)
        assert all(isinstance(c, Constraint) for c in constraints)

    @pytest.mark.asyncio
    async def test_explicit_hard_constraint(self):
        """Extract 'must' as hard explicit constraint."""
        goal = _make_goal(description="The output must be JSON formatted")
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        hard = [c for c in constraints if c.kind == ConstraintKind.HARD
                and c.source == ConstraintSource.EXPLICIT]
        assert len(hard) >= 1

    @pytest.mark.asyncio
    async def test_explicit_soft_constraint(self):
        """Extract 'should' as soft explicit constraint."""
        goal = _make_goal(description="The response should be concise")
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        soft = [c for c in constraints if c.kind == ConstraintKind.SOFT
                and c.source == ConstraintSource.EXPLICIT]
        assert len(soft) >= 1

    @pytest.mark.asyncio
    async def test_inferred_low_confidence(self):
        """Low confidence goal produces inferred constraint."""
        goal = _make_goal(confidence=0.3)
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        inferred = [c for c in constraints
                    if c.source == ConstraintSource.INFERRED
                    and "low_confidence" in c.rationale]
        assert len(inferred) == 1

    @pytest.mark.asyncio
    async def test_inferred_compound_goal(self):
        """Compound goal produces inferred constraint."""
        goal = _make_goal(sub_goals=["goal-2", "goal-3"])
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        compound = [c for c in constraints
                    if c.source == ConstraintSource.INFERRED
                    and "compound_goal" in c.rationale]
        assert len(compound) == 1

    @pytest.mark.asyncio
    async def test_no_constraints_for_simple_goal(self):
        """Simple goal with high confidence produces no inferred constraints."""
        goal = _make_goal(
            description="tell me a joke",
            confidence=0.9,
        )
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        # May have zero or some explicit constraints depending on text,
        # but no inferred ones.
        inferred = [c for c in constraints
                    if c.source == ConstraintSource.INFERRED]
        assert len(inferred) == 0

    @pytest.mark.asyncio
    async def test_event_emitted(self):
        """K4.2 §11: cognitive.constraints_extracted event emitted."""
        goal = _make_goal(description="must handle errors")
        es = MockEventStream()
        await extract_constraints(goal, event_stream=es)
        assert len(es.events) == 1
        event = es.events[0]
        assert event["event_type"] == "cognitive.constraints_extracted"
        assert event["source"] == "Planner"
        assert "goal_id" in event["payload"]
        assert "constraint_count" in event["payload"]
        assert "hard_count" in event["payload"]
        assert "soft_count" in event["payload"]
        assert "sources" in event["payload"]

    @pytest.mark.asyncio
    async def test_event_payload_counts_correct(self):
        """Event payload counts match actual constraint counts."""
        goal = _make_goal(
            description="must be fast and should be elegant",
            confidence=0.3,
        )
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        payload = es.events[0]["payload"]
        assert payload["constraint_count"] == len(constraints)
        hard_actual = sum(1 for c in constraints
                         if c.kind == ConstraintKind.HARD)
        soft_actual = sum(1 for c in constraints
                         if c.kind == ConstraintKind.SOFT)
        assert payload["hard_count"] == hard_actual
        assert payload["soft_count"] == soft_actual

    @pytest.mark.asyncio
    async def test_uses_description_over_raw_request(self):
        """Uses structured_form description when available."""
        goal = _make_goal(
            description="must use encryption",
            raw_request="please use encryption if possible",
        )
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        hard = [c for c in constraints if c.kind == ConstraintKind.HARD]
        assert len(hard) >= 1

    @pytest.mark.asyncio
    async def test_falls_back_to_raw_request(self):
        """Falls back to raw_request when description is 'unknown'."""
        goal = _make_goal(
            description="unknown",
            raw_request="must validate input",
        )
        es = MockEventStream()
        constraints = await extract_constraints(goal, event_stream=es)
        hard = [c for c in constraints if c.kind == ConstraintKind.HARD]
        assert len(hard) >= 1


# ─────────────────────────────────────────────────────────────────────────
# check_precheck_rejection() — K4.2 §5
# ─────────────────────────────────────────────────────────────────────────

class TestPrecheckRejection:
    """K4.2 §5: contradictory hard constraints → rejected_precheck."""

    def test_contradictory_constraints_detected(self):
        """K4.2 §15: contradictory-hard-constraint fixture correctly
        yields rejected_precheck."""
        constraints = [
            Constraint(
                kind=ConstraintKind.HARD,
                source=ConstraintSource.EXPLICIT,
                rationale="requirement_constraint: must use encryption",
            ),
            Constraint(
                kind=ConstraintKind.HARD,
                source=ConstraintSource.EXPLICIT,
                rationale="negation_constraint: must not use encryption",
            ),
        ]
        result = check_precheck_rejection(constraints)
        assert result is not None
        assert result.status == PlannerStatus.REJECTED_PRECHECK
        assert result.impasse_detail is not None
        assert result.impasse_detail.reason == "contradictory_hard_constraints"

    def test_no_contradiction_passes(self):
        """Non-contradictory constraints do not trigger rejection."""
        constraints = [
            Constraint(
                kind=ConstraintKind.HARD,
                source=ConstraintSource.EXPLICIT,
                rationale="requirement_constraint: must use encryption",
            ),
            Constraint(
                kind=ConstraintKind.SOFT,
                source=ConstraintSource.INFERRED,
                rationale="low_confidence: prefer conservative approach",
            ),
        ]
        result = check_precheck_rejection(constraints)
        assert result is None

    def test_empty_constraints_passes(self):
        """Empty constraint list does not trigger rejection."""
        result = check_precheck_rejection([])
        assert result is None

    def test_soft_contradictions_not_rejected(self):
        """Only hard constraint contradictions trigger rejection."""
        constraints = [
            Constraint(
                kind=ConstraintKind.SOFT,
                source=ConstraintSource.EXPLICIT,
                rationale="requirement_constraint: should be fast",
            ),
            Constraint(
                kind=ConstraintKind.SOFT,
                source=ConstraintSource.EXPLICIT,
                rationale="negation_constraint: should not be fast",
            ),
        ]
        result = check_precheck_rejection(constraints)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────
# build_planner_request() — K4.2 §5
# ─────────────────────────────────────────────────────────────────────────

class TestBuildPlannerRequest:
    """Verify PlannerRequest construction."""

    def test_basic_construction(self):
        goal = _make_goal()
        constraints = [Constraint(rationale="test")]
        req = build_planner_request(goal, constraints)
        assert isinstance(req, PlannerRequest)
        assert req.goal_id == goal.resource_id
        assert req.goal is goal

    def test_novel_category_hint(self):
        """Novel category goals get thoroughness hint."""
        goal = _make_goal(category="novel")
        req = build_planner_request(goal, [])
        thoroughness_hints = [h for h in req.hints
                              if h.kind == "prefer_thoroughness"]
        assert len(thoroughness_hints) >= 1

    def test_high_confidence_speed_hint(self):
        """High confidence goals get speed hint."""
        goal = _make_goal(confidence=0.9, category="known")
        req = build_planner_request(goal, [])
        speed_hints = [h for h in req.hints
                       if h.kind == "prefer_speed"]
        assert len(speed_hints) >= 1

    def test_low_confidence_thoroughness_hint(self):
        """Low confidence goals get thoroughness hint."""
        goal = _make_goal(confidence=0.3, category="known")
        req = build_planner_request(goal, [])
        thoroughness_hints = [h for h in req.hints
                              if h.kind == "prefer_thoroughness"]
        assert len(thoroughness_hints) >= 1

    def test_hints_are_intent_dimension_sourced(self):
        """All hints from this packet are intent_dimension sourced."""
        goal = _make_goal()
        req = build_planner_request(goal, [])
        for hint in req.hints:
            assert hint.source == HintSource.INTENT_DIMENSION

    def test_context_view_ref_passed(self):
        goal = _make_goal()
        req = build_planner_request(goal, [], context_view_ref="ctx-123")
        assert req.context_view_ref == "ctx-123"


# ─────────────────────────────────────────────────────────────────────────
# Architecture compliance
# ─────────────────────────────────────────────────────────────────────────

class TestArchitectureCompliance:
    """Verify Packet 01 does not violate architectural boundaries."""

    def test_constraint_has_no_resource_id(self):
        """K4.2 §12: Constraint is embedded, not independently identified."""
        fields = {f.name for f in dataclasses.fields(Constraint)}
        assert "resource_id" not in fields

    def test_planner_hint_has_no_resource_id(self):
        """K4.2 §12: PlannerHint is embedded, not independently identified."""
        fields = {f.name for f in dataclasses.fields(PlannerHint)}
        assert "resource_id" not in fields

    def test_planner_request_has_no_resource_id(self):
        """K4.2 §12: PlannerRequest is ephemeral, not a Resource."""
        fields = {f.name for f in dataclasses.fields(PlannerRequest)}
        assert "resource_id" not in fields

    def test_planner_result_has_no_resource_id(self):
        """K4.2 §12: PlannerResult is ephemeral, not a Resource."""
        fields = {f.name for f in dataclasses.fields(PlannerResult)}
        assert "resource_id" not in fields

    def test_no_capability_imports(self):
        """Evolution Directive: capability selection forbidden in K4.2."""
        import core.cognitive.planner as mod
        source = open(mod.__file__).read()
        assert "AdapterRuntime" not in source
        assert "CapabilityType" not in source
        assert "invoke" not in source.split("def ")[0]  # No invoke calls

    def test_no_memory_writes(self):
        """K4 §1: Cognitive Front-End never writes to UnifiedMemory."""
        import core.cognitive.planner as mod
        source = open(mod.__file__).read()
        assert "UnifiedMemory" not in source
        assert ".write(" not in source

    def test_no_governance_invocation(self):
        """Governance evaluation reserved for Plan Compilation."""
        import core.cognitive.planner as mod
        source = open(mod.__file__).read()
        assert "GovernanceKernel" not in source
        assert "evaluate_action" not in source
