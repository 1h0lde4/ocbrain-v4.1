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
    - _extract_constraints() produces well-formed constraints
    - _extract_constraints() emits cognitive.constraints_extracted event
    - Contradictory hard constraints yield rejected_precheck
    - build_planner_request() produces valid PlannerRequest with hints
    - CognitiveArtifact protocol not violated
    - No forbidden work present
"""
import dataclasses

import pytest
from unittest.mock import AsyncMock, patch

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
from core.capabilities.capability import BaseAdapter, CapabilityContract
from core.capabilities.registry import CapabilityRegistry
from core.cognitive.planner import (
    CapabilityDiscoveryRequest,
    ClarificationPolicy,
    Constraint,
    ConstraintKind,
    ConstraintRelation,
    ConstraintSource,
    ExecutionPlan,
    ExecutionPlanLifecycle,
    HintSource,
    ImpasseRecord,
    PlanStep,
    PlannerHint,
    PlannerRequest,
    PlannerResult,
    PlannerStatus,
    _alternative_plans,
    _capability_match_score,
    _decompose,
    _detect_contradictions,
    _detect_impasse,
    _estimate_confidence,
    _extract_explicit_constraints,
    _fallback_paths,
    _justify,
    _parse_decomposition,
    _sequence,
    _tokenize,
    build_capability_discovery_request,
    build_planner_request,
    check_precheck_rejection,
    discover_capabilities,
    plan,
    _extract_constraints,
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
        """K4.2 §12: status, execution_plan, impasse_detail. Exactly
        these three — no additional fields (K4.2 §5/§12 both specify
        this shape precisely; a 4th field previously slipped in here
        and was removed as a verified spec deviation)."""
        r = PlannerResult()
        assert hasattr(r, "status")
        assert hasattr(r, "execution_plan")
        assert hasattr(r, "impasse_detail")
        field_names = {f.name for f in dataclasses.fields(PlannerResult)}
        assert field_names == {"status", "execution_plan", "impasse_detail"}

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
# _extract_constraints() — K4.2 §5
# ─────────────────────────────────────────────────────────────────────────

class TestExtractConstraints:
    """Verify constraint extraction from Goals."""

    @pytest.mark.asyncio
    async def test_basic_extraction(self):
        """K4.2 §5: extract_constraints produces well-formed constraints."""
        goal = _make_goal(description="The system must handle errors gracefully")
        es = MockEventStream()
        constraints = await _extract_constraints(goal, event_stream=es)
        assert isinstance(constraints, list)
        assert all(isinstance(c, Constraint) for c in constraints)

    @pytest.mark.asyncio
    async def test_explicit_hard_constraint(self):
        """Extract 'must' as hard explicit constraint."""
        goal = _make_goal(description="The output must be JSON formatted")
        es = MockEventStream()
        constraints = await _extract_constraints(goal, event_stream=es)
        hard = [c for c in constraints if c.kind == ConstraintKind.HARD
                and c.source == ConstraintSource.EXPLICIT]
        assert len(hard) >= 1

    @pytest.mark.asyncio
    async def test_explicit_soft_constraint(self):
        """Extract 'should' as soft explicit constraint."""
        goal = _make_goal(description="The response should be concise")
        es = MockEventStream()
        constraints = await _extract_constraints(goal, event_stream=es)
        soft = [c for c in constraints if c.kind == ConstraintKind.SOFT
                and c.source == ConstraintSource.EXPLICIT]
        assert len(soft) >= 1

    @pytest.mark.asyncio
    async def test_inferred_low_confidence(self):
        """Low confidence goal produces inferred constraint."""
        goal = _make_goal(confidence=0.3)
        es = MockEventStream()
        constraints = await _extract_constraints(goal, event_stream=es)
        inferred = [c for c in constraints
                    if c.source == ConstraintSource.INFERRED
                    and "low_confidence" in c.rationale]
        assert len(inferred) == 1

    @pytest.mark.asyncio
    async def test_inferred_compound_goal(self):
        """Compound goal produces inferred constraint."""
        goal = _make_goal(sub_goals=["goal-2", "goal-3"])
        es = MockEventStream()
        constraints = await _extract_constraints(goal, event_stream=es)
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
        constraints = await _extract_constraints(goal, event_stream=es)
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
        await _extract_constraints(goal, event_stream=es)
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
        constraints = await _extract_constraints(goal, event_stream=es)
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
        constraints = await _extract_constraints(goal, event_stream=es)
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
        constraints = await _extract_constraints(goal, event_stream=es)
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


class TestExtractionContradictionIntegration:
    """Regression tests for a bug found during Packet 01 Post-Implementation
    Review: _extract_explicit_constraints()'s pattern list contains
    overlapping patterns checked in priority order (e.g. "must not" before
    plain "must"), and the original context-string dedup only caught the
    resulting duplicate match by coincidence, when both matches' context
    windows happened to get clamped to the same end-of-string. With enough
    trailing text after the match, a single "must not X" statement produced
    two constraints (a correct negation_constraint and a spurious
    requirement_constraint over the same words), which then satisfied
    _detect_contradictions()'s overlapping-content-word check and incorrectly
    yielded rejected_precheck for a goal with no actual contradiction.

    These tests exercise the real extraction -> detection pipeline with
    realistic text, which none of the existing TestPrecheckRejection tests
    did (they all construct Constraint objects by hand).
    """

    def test_single_must_not_statement_is_not_self_contradictory(self):
        text = (
            "You must not use JavaScript for this task, since the team "
            "standard requires Python for all new automation scripts "
            "going forward."
        )
        constraints = _extract_explicit_constraints(text)
        assert len(constraints) == 1
        assert constraints[0].rationale.startswith("negation_constraint")
        assert _detect_contradictions(constraints) is False

    def test_single_should_not_statement_is_not_self_contradictory(self):
        text = (
            "The report should not include raw customer data, since "
            "privacy policy requires all personal fields to be redacted "
            "before distribution."
        )
        constraints = _extract_explicit_constraints(text)
        assert len(constraints) == 1
        assert constraints[0].rationale.startswith("soft_negation_constraint")
        assert _detect_contradictions(constraints) is False

    def test_genuine_cross_sentence_contradiction_still_detected(self):
        text = (
            "The report must use encryption for all stored data. However, "
            "the legacy export step must not use encryption, per the "
            "vendor contract."
        )
        constraints = _extract_explicit_constraints(text)
        assert _detect_contradictions(constraints) is True

    def test_distinct_constraint_types_in_one_sentence_not_merged(self):
        """must / only / without are genuinely different constraint
        semantics, not overlapping matches on the same words -- the span
        fix must not suppress these."""
        text = "You must only use approved vendors for this without any exceptions."
        constraints = _extract_explicit_constraints(text)
        rationale_types = {c.rationale.split(":", 1)[0] for c in constraints}
        assert "requirement_constraint" in rationale_types
        assert "scoping_constraint" in rationale_types
        assert "exclusion_constraint" in rationale_types


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

def _real_code_identifiers(filepath: str) -> set:
    """Names actually used as code in a module: imports, bare names, and
    attribute accesses. Deliberately excludes docstrings and comments —
    a raw substring search over the whole file text (the previous
    approach) false-positives on explanatory prose like "never writes
    to UnifiedMemory", which mentions the forbidden name specifically
    to disclaim it. Parsing via `ast` and collecting only Name/Attribute/
    Import nodes inspects what the code actually does, not what its
    docstrings say about what it doesn't do.
    """
    import ast

    tree = ast.parse(open(filepath).read())
    identifiers: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                identifiers.add(alias.name.split(".")[-1])
                if alias.asname:
                    identifiers.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                identifiers.add(alias.name)
                if alias.asname:
                    identifiers.add(alias.asname)
        elif isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
    return identifiers


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
        identifiers = _real_code_identifiers(mod.__file__)
        assert "AdapterRuntime" not in identifiers
        assert "CapabilityType" not in identifiers
        assert "invoke" not in identifiers  # no real .invoke(...) call

    def test_no_memory_writes(self):
        """K4 §1: Cognitive Front-End never writes to UnifiedMemory."""
        import core.cognitive.planner as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "UnifiedMemory" not in identifiers
        assert "write" not in identifiers  # no real .write(...) call

    def test_no_governance_invocation(self):
        """Governance evaluation reserved for Plan Compilation."""
        import core.cognitive.planner as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "GovernanceKernel" not in identifiers
        assert "evaluate_action" not in identifiers


# ─────────────────────────────────────────────────────────────────────────
# CapabilityDiscoveryRequest — K4.2 §12 (Packet 02)
# ─────────────────────────────────────────────────────────────────────────

def _make_registry(entries=None):
    """Builds a CapabilityRegistry for testing. entries is a list of
    (capability_type, description, has_adapter) tuples; defaults to a
    single llm_completion capability with an adapter, matching the live
    composition root (main.py)."""
    registry = CapabilityRegistry()
    entries = entries or [
        ("llm_completion", "Generate text from a prompt via a language model.", True),
    ]
    for capability_type, description, has_adapter in entries:
        registry.register_capability(CapabilityContract(
            capability_type=capability_type,
            description=description,
        ))
        if has_adapter:
            adapter = BaseAdapter()
            adapter.adapter_name = f"fake-{capability_type}"
            adapter.capability_type = capability_type
            registry.register_adapter(capability_type, adapter)
    return registry


class TestCapabilityDiscoveryRequestDataclass:
    def test_construction(self):
        request = CapabilityDiscoveryRequest(
            subgoal_ref="goal-1",
            description="summarize a document",
        )
        assert request.subgoal_ref == "goal-1"
        assert request.description == "summarize a document"
        assert request.applicable_constraints == []
        assert request.context_view_ref == ""

    def test_has_no_resource_id(self):
        """K4.2 §12: ephemeral parameter object, not a CognitiveArtifact --
        same category as PlannerRequest/PlannerResult."""
        assert not hasattr(CapabilityDiscoveryRequest, "resource_id")
        assert not dataclasses.fields(CapabilityDiscoveryRequest)[0].name == "resource_id"


class TestBuildCapabilityDiscoveryRequest:
    def test_uses_goal_resource_id_as_subgoal_ref(self):
        goal = _make_goal(description="summarize a document")
        request = build_capability_discovery_request(goal, [])
        assert request.subgoal_ref == goal.resource_id

    def test_extracts_description_from_structured_form(self):
        goal = _make_goal(description="generate an image of a cat")
        request = build_capability_discovery_request(goal, [])
        assert request.description == "generate an image of a cat"

    def test_carries_constraints_through(self):
        goal = _make_goal()
        constraint = Constraint(
            kind=ConstraintKind.HARD,
            source=ConstraintSource.EXPLICIT,
            rationale="requirement_constraint: must use Python",
        )
        request = build_capability_discovery_request(goal, [constraint])
        assert request.applicable_constraints == [constraint]

    def test_carries_context_view_ref(self):
        goal = _make_goal()
        request = build_capability_discovery_request(goal, [], context_view_ref="ctx-42")
        assert request.context_view_ref == "ctx-42"

    def test_handles_missing_structured_form_gracefully(self):
        goal = Goal(intent_id="x", structured_form={})
        request = build_capability_discovery_request(goal, [])
        assert request.description == ""


# ─────────────────────────────────────────────────────────────────────────
# _capability_match_score / _tokenize
# ─────────────────────────────────────────────────────────────────────────

class TestCapabilityMatchScore:
    def test_identical_description_scores_high(self):
        request = CapabilityDiscoveryRequest(subgoal_ref="g", description="generate text from a prompt")
        contract = CapabilityContract(
            capability_type="llm_completion",
            description="generate text from a prompt",
        )
        assert _capability_match_score(request, contract) == pytest.approx(1.0)

    def test_unrelated_description_scores_zero(self):
        request = CapabilityDiscoveryRequest(subgoal_ref="g", description="book a flight to Tokyo")
        contract = CapabilityContract(
            capability_type="llm_completion",
            description="generate text from a prompt via a language model",
        )
        assert _capability_match_score(request, contract) == 0.0

    def test_score_is_bounded(self):
        request = CapabilityDiscoveryRequest(subgoal_ref="g", description="search the web for news")
        contract = CapabilityContract(
            capability_type="web_search",
            description="search the web for current information",
        )
        score = _capability_match_score(request, contract)
        assert 0.0 <= score <= 1.0

    def test_empty_description_scores_zero(self):
        request = CapabilityDiscoveryRequest(subgoal_ref="g", description="")
        contract = CapabilityContract(capability_type="x", description="does something")
        assert _capability_match_score(request, contract) == 0.0

    def test_deterministic(self):
        request = CapabilityDiscoveryRequest(subgoal_ref="g", description="generate an image")
        contract = CapabilityContract(capability_type="image_generation", description="generate an image from text")
        first = _capability_match_score(request, contract)
        second = _capability_match_score(request, contract)
        assert first == second


class TestTokenize:
    def test_lowercases_and_strips_punctuation(self):
        assert _tokenize("Generate Text, From a Prompt!") == {
            "generate", "text", "from", "a", "prompt",
        }

    def test_empty_string(self):
        assert _tokenize("") == set()


# ─────────────────────────────────────────────────────────────────────────
# discover_capabilities() — integration
# ─────────────────────────────────────────────────────────────────────────

class TestDiscoverCapabilities:
    @pytest.mark.asyncio
    async def test_matches_relevant_capability(self):
        registry = _make_registry()
        request = CapabilityDiscoveryRequest(
            subgoal_ref="g1", description="generate text from a prompt using a model",
        )
        mock_stream = AsyncMock()
        candidates = await discover_capabilities(request, registry, event_stream=mock_stream)
        assert len(candidates) == 1
        assert candidates[0].capability_type == "llm_completion"

    @pytest.mark.asyncio
    async def test_excludes_capability_with_no_adapter(self):
        registry = _make_registry([
            ("llm_completion", "Generate text from a prompt via a language model.", True),
            ("web_search", "Search the web for current information.", False),
        ])
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="search the web for news")
        mock_stream = AsyncMock()
        candidates = await discover_capabilities(request, registry, event_stream=mock_stream)
        assert all(c.capability_type != "web_search" for c in candidates)

    @pytest.mark.asyncio
    async def test_ranks_best_match_first(self):
        registry = _make_registry([
            ("llm_completion", "Generate text from a prompt via a language model.", True),
            ("web_search", "Search the web for current news and information.", True),
        ])
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="search the web for current news")
        mock_stream = AsyncMock()
        candidates = await discover_capabilities(request, registry, event_stream=mock_stream)
        assert candidates[0].capability_type == "web_search"

    @pytest.mark.asyncio
    async def test_empty_registry_returns_empty_list(self):
        registry = CapabilityRegistry()
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="do anything")
        mock_stream = AsyncMock()
        candidates = await discover_capabilities(request, registry, event_stream=mock_stream)
        assert candidates == []

    @pytest.mark.asyncio
    async def test_no_relevant_match_still_returns_gracefully(self):
        registry = _make_registry()
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="book a flight to Tokyo")
        mock_stream = AsyncMock()
        candidates = await discover_capabilities(request, registry, event_stream=mock_stream)
        # No error, no exception -- an empty or low-scored list is a valid,
        # deterministic outcome, not a failure state.
        assert isinstance(candidates, list)

    @pytest.mark.asyncio
    async def test_min_score_filters_low_relevance(self):
        registry = _make_registry()
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="completely unrelated topic xyz")
        mock_stream = AsyncMock()
        candidates = await discover_capabilities(
            request, registry, event_stream=mock_stream, min_score=0.5,
        )
        assert candidates == []

    @pytest.mark.asyncio
    async def test_event_emitted_once_with_expected_shape(self):
        registry = _make_registry()
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="generate text from a prompt")
        mock_stream = AsyncMock()
        await discover_capabilities(request, registry, event_stream=mock_stream)
        mock_stream.append.assert_called_once()
        call = mock_stream.append.call_args
        assert call.args[0] == "cognitive.capabilities_discovered"
        assert call.kwargs["payload"]["subgoal_ref"] == "g1"
        assert "candidate_count" in call.kwargs["payload"]
        assert "candidates" in call.kwargs["payload"]

    @pytest.mark.asyncio
    async def test_deterministic_across_repeated_calls(self):
        registry = _make_registry([
            ("llm_completion", "Generate text from a prompt via a language model.", True),
            ("web_search", "Search the web for current news and information.", True),
        ])
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="search news on the web")
        mock_stream = AsyncMock()
        first = await discover_capabilities(request, registry, event_stream=mock_stream)
        second = await discover_capabilities(request, registry, event_stream=mock_stream)
        assert [c.capability_type for c in first] == [c.capability_type for c in second]

    @pytest.mark.asyncio
    async def test_never_calls_adapter_execute(self):
        """Discovery must not invoke any capability -- get_adapters() is
        used only to check registration, never to call .execute()."""
        registry = _make_registry()
        call_log = []

        class WatchedAdapter(BaseAdapter):
            adapter_name = "watched"
            capability_type = "llm_completion"
            async def execute(self, request, resources):
                call_log.append("execute called")
                raise AssertionError("Capability Discovery must never invoke an adapter")

        registry._adapters["llm_completion"] = [WatchedAdapter()]
        request = CapabilityDiscoveryRequest(subgoal_ref="g1", description="generate text from a prompt")
        mock_stream = AsyncMock()
        await discover_capabilities(request, registry, event_stream=mock_stream)
        assert call_log == []


class TestCapabilityDiscoveryArchitectureCompliance:
    """Mirrors TestArchitectureCompliance's boundary checks, specifically
    for the capability-discovery additions."""

    def test_returns_ranked_list_not_a_single_winner(self):
        """Discovery returns a list (behavioral evidence, not a text
        search over the source -- a raw substring check here would repeat
        the exact false-failure class found and fixed during the Packet 01
        review, e.g. tripping on this file's own docstrings)."""
        import inspect
        signature = inspect.signature(discover_capabilities)
        assert "List" in str(signature.return_annotation) or \
            signature.return_annotation is list or \
            "list" in str(signature.return_annotation).lower()

    def test_no_capability_execution_identifiers(self):
        import core.cognitive.planner as mod
        identifiers = _real_code_identifiers(mod.__file__)
        assert "AdapterRuntime" not in identifiers
        assert "execute" not in identifiers


# ─────────────────────────────────────────────────────────────────────────
# Planner Completion — K4 §5/§6, K4.2 §5/§12/§14/§15 (Packet 03)
# ─────────────────────────────────────────────────────────────────────────

class TestClarificationPolicyDataclass:
    def test_defaults(self):
        policy = ClarificationPolicy()
        assert policy.confidence_threshold == 0.5
        assert policy.max_escalations == 2

    def test_custom_values(self):
        policy = ClarificationPolicy(confidence_threshold=0.7, max_escalations=1)
        assert policy.confidence_threshold == 0.7
        assert policy.max_escalations == 1


class TestExecutionPlanDataclass:
    def test_default_construction(self):
        p = ExecutionPlan()
        assert p.resource_id
        assert p.produced_by == "Planner"
        assert p.lifecycle_state == ExecutionPlanLifecycle.DRAFT
        assert p.steps == []
        assert p.alternatives == []
        assert p.derived_from == []

    def test_resource_ids_are_unique(self):
        assert ExecutionPlan().resource_id != ExecutionPlan().resource_id

    def test_satisfies_cognitive_artifact(self):
        from core.cognitive.intent import CognitiveArtifact
        assert isinstance(ExecutionPlan(), CognitiveArtifact)

    def test_to_dict(self):
        p = ExecutionPlan(goal_id="g1", confidence=0.7)
        d = p.to_dict()
        assert d["goal_id"] == "g1"
        assert d["confidence"] == 0.7


class TestPlanStepDataclass:
    def test_construction(self):
        step = PlanStep(step_id="s1", description="do a thing", capability_type="llm_completion")
        assert step.error_branch is None


# ── _parse_decomposition ─────────────────────────────────────────────────

class TestParseDecomposition:
    def test_parses_multiple_lines(self):
        assert _parse_decomposition("Do X\nDo Y\nDo Z") == ["Do X", "Do Y", "Do Z"]

    def test_strips_blank_lines(self):
        assert _parse_decomposition("Do X\n\n\nDo Y\n") == ["Do X", "Do Y"]

    def test_empty_or_none(self):
        assert _parse_decomposition("") == []
        assert _parse_decomposition(None) == []


# ── _decompose ───────────────────────────────────────────────────────────

class TestDecompose:
    @pytest.mark.asyncio
    async def test_single_step_goal(self):
        registry = _make_registry()
        goal = _make_goal(description="generate text from a prompt using a model")
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Generate text from a prompt.")):
            result = await _decompose(goal, registry)
        assert len(result) == 1
        step, candidates = result[0]
        assert step.capability_type == "llm_completion"
        assert len(candidates) >= 1

    @pytest.mark.asyncio
    async def test_multi_step_goal(self):
        registry = _make_registry([
            ("llm_completion", "Generate text from a prompt via a language model.", True),
            ("web_search", "Search the web for current news and information.", True),
        ])
        goal = _make_goal(description="search the web then summarize")
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Search the web for current news.\nSummarize the results using a language model.")):
            result = await _decompose(goal, registry)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_provider_failure_degrades_to_single_step(self):
        registry = _make_registry()
        goal = _make_goal(description="generate a summary")
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(side_effect=RuntimeError("all providers failed"))):
            result = await _decompose(goal, registry)
        assert len(result) == 1
        assert result[0][0].description == "generate a summary"

    @pytest.mark.asyncio
    async def test_unparseable_completion_degrades_to_single_step(self):
        registry = _make_registry()
        goal = _make_goal(description="generate a summary")
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="")):
            result = await _decompose(goal, registry)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_step_with_no_matching_capability_has_empty_candidates(self):
        registry = _make_registry()  # only llm_completion
        goal = _make_goal(description="book a flight")
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Book a flight to Tokyo.")):
            result = await _decompose(goal, registry)
        step, candidates = result[0]
        assert candidates == []
        assert step.capability_type == ""

    @pytest.mark.asyncio
    async def test_zero_relevance_capability_not_treated_as_a_candidate(self):
        """Regression: _decompose applies a minimum-relevance floor
        (min_score=0.01) when calling discover_capabilities. Without it,
        a step with zero token overlap against every registered
        capability would still receive that capability as its "match"
        (Packet 02's own discover_capabilities correctly ranks rather
        than filters by default) -- which would make impasse detection
        fire only on a completely empty registry, not on "nothing here
        actually fits," as K4.2 §5/§14 describe."""
        registry = _make_registry()  # only llm_completion, unrelated description
        goal = _make_goal(description="reserve a table at a restaurant")
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Reserve a table at a restaurant.")):
            result = await _decompose(goal, registry)
        step, candidates = result[0]
        assert candidates == [], (
            "a capability with zero description overlap must not be "
            "surfaced as a candidate for an unrelated step"
        )


# ── _sequence / _fallback_paths ─────────────────────────────────────────

class TestSequence:
    def test_preserves_decomposition_order(self):
        step1 = PlanStep(step_id="s1", description="first", capability_type="x")
        step2 = PlanStep(step_id="s2", description="second", capability_type="y")
        result = _sequence([(step1, []), (step2, [])], [])
        assert [s.step_id for s in result] == ["s1", "s2"]


class TestFallbackPaths:
    def test_does_not_alter_step_count_or_identity(self):
        steps = [
            PlanStep(step_id="s1", description="a", capability_type="x"),
            PlanStep(step_id="s2", description="b", capability_type="y"),
        ]
        result = _fallback_paths(steps)
        assert len(result) == 2
        assert [s.step_id for s in result] == ["s1", "s2"]


# ── _estimate_confidence ─────────────────────────────────────────────────

class TestEstimateConfidence:
    def test_empty_steps_is_zero(self):
        assert _estimate_confidence([]) == 0.0

    def test_step_with_no_candidates_drags_confidence_to_zero(self):
        step = PlanStep(step_id="s1", description="x", capability_type="")
        assert _estimate_confidence([(step, [])]) == 0.0

    def test_confidence_is_bounded(self):
        step = PlanStep(step_id="s1", description="generate text from a prompt", capability_type="llm_completion")
        contract = CapabilityContract(capability_type="llm_completion", description="generate text from a prompt")
        confidence = _estimate_confidence([(step, [contract])])
        assert 0.0 <= confidence <= 1.0

    def test_weakest_step_determines_overall_confidence(self):
        strong_step = PlanStep(step_id="s1", description="generate text from a prompt", capability_type="llm_completion")
        strong_contract = CapabilityContract(capability_type="llm_completion", description="generate text from a prompt")
        weak_step = PlanStep(step_id="s2", description="completely unrelated topic", capability_type="llm_completion")
        weak_contract = CapabilityContract(capability_type="llm_completion", description="generate text from a prompt")
        confidence = _estimate_confidence([
            (strong_step, [strong_contract]), (weak_step, [weak_contract]),
        ])
        assert confidence <= _capability_match_score(
            CapabilityDiscoveryRequest(subgoal_ref="x", description="generate text from a prompt"),
            strong_contract,
        )


# ── _alternative_plans ───────────────────────────────────────────────────

class TestAlternativePlans:
    def test_no_alternatives_when_no_step_has_second_candidate(self):
        goal = _make_goal()
        step = PlanStep(step_id="s1", description="x", capability_type="llm_completion")
        contract = CapabilityContract(capability_type="llm_completion", description="x")
        alternatives = _alternative_plans(goal, [(step, [contract])])
        assert alternatives == []

    def test_generates_alternative_when_second_candidate_exists(self):
        goal = _make_goal()
        step = PlanStep(step_id="s1", description="x", capability_type="a")
        contract_a = CapabilityContract(capability_type="a", description="x")
        contract_b = CapabilityContract(capability_type="b", description="x")
        alternatives = _alternative_plans(goal, [(step, [contract_a, contract_b])])
        assert len(alternatives) == 1
        # Returns resource_id references only, not embedded ExecutionPlan objects.
        assert isinstance(alternatives[0], str)

    def test_respects_top_n(self):
        goal = _make_goal()
        contract_a = CapabilityContract(capability_type="a", description="x")
        contract_b = CapabilityContract(capability_type="b", description="x")
        steps_with_candidates = [
            (PlanStep(step_id=f"s{i}", description="x", capability_type="a"),
             [contract_a, contract_b])
            for i in range(5)
        ]
        alternatives = _alternative_plans(goal, steps_with_candidates, top_n=2)
        assert len(alternatives) == 2


# ── _justify ──────────────────────────────────────────────────────────────

class TestJustify:
    def test_empty_steps(self):
        assert "No steps" in _justify([], [])

    def test_includes_step_descriptions_and_capabilities(self):
        step = PlanStep(step_id="s1", description="generate a summary", capability_type="llm_completion")
        justification = _justify([step], [])
        assert "generate a summary" in justification
        assert "llm_completion" in justification

    def test_mentions_constraint_count(self):
        constraint = Constraint(kind=ConstraintKind.HARD, source=ConstraintSource.EXPLICIT, rationale="x")
        step = PlanStep(step_id="s1", description="x", capability_type="y")
        justification = _justify([step], [constraint])
        assert "1 requirement" in justification


# ── _detect_impasse ───────────────────────────────────────────────────────

class TestDetectImpasse:
    def test_no_impasse_when_every_step_has_a_candidate(self):
        step = PlanStep(step_id="s1", description="x", capability_type="llm_completion")
        contract = CapabilityContract(capability_type="llm_completion", description="x")
        assert _detect_impasse([(step, [contract])]) is None

    def test_impasse_when_a_step_has_no_candidates(self):
        step = PlanStep(step_id="s1", description="book a flight", capability_type="")
        record = _detect_impasse([(step, [])])
        assert isinstance(record, ImpasseRecord)
        assert "book a flight" in record.unresolved_subgoals

    def test_attempted_capabilities_collected_across_steps(self):
        step1 = PlanStep(step_id="s1", description="a", capability_type="")
        step2 = PlanStep(step_id="s2", description="b", capability_type="")
        contract = CapabilityContract(capability_type="llm_completion", description="x")
        record = _detect_impasse([(step1, [contract]), (step2, [])])
        assert record is not None
        assert "llm_completion" in record.attempted_capabilities


# ── plan() — full integration ────────────────────────────────────────────

class TestPlan:
    @pytest.mark.asyncio
    async def test_ready_for_compilation_on_success(self):
        registry = _make_registry()
        goal = _make_goal(description="generate text from a prompt using a model")
        request = PlannerRequest(goal_id=goal.resource_id, goal=goal, hints=[])
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Generate text from a prompt.")):
            result = await plan(request, registry, event_stream=AsyncMock())
        assert result.status == PlannerStatus.READY_FOR_COMPILATION
        assert result.execution_plan is not None
        assert result.execution_plan.goal_id == goal.resource_id

    @pytest.mark.asyncio
    async def test_impasse_when_no_capability_matches(self):
        registry = CapabilityRegistry()  # empty
        goal = _make_goal(description="book a flight to Tokyo")
        request = PlannerRequest(goal_id=goal.resource_id, goal=goal, hints=[])
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Book a flight to Tokyo.")):
            result = await plan(request, registry, event_stream=AsyncMock())
        assert result.status == PlannerStatus.IMPASSE
        assert result.impasse_detail is not None

    @pytest.mark.asyncio
    async def test_rejected_precheck_on_contradictory_constraints(self):
        """Reuses Packet 01's check_precheck_rejection directly -- a Goal
        whose description (the field _extract_constraints actually reads
        when it isn't 'unknown') contains contradictory hard constraints
        is rejected before decomposition is ever attempted."""
        registry = _make_registry()
        goal = _make_goal(
            description=(
                "The report must use encryption for all stored data. "
                "However, the legacy export step must not use "
                "encryption, per the vendor contract."
            ),
        )
        request = PlannerRequest(goal_id=goal.resource_id, goal=goal, hints=[])
        mock_generate = AsyncMock()
        with patch("core.cognitive.planner.generate_with_fallback", new=mock_generate):
            result = await plan(request, registry, event_stream=AsyncMock())
        assert result.status == PlannerStatus.REJECTED_PRECHECK
        # Decomposition never ran -- precheck short-circuits before it.
        mock_generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_deterministic_confidence_across_repeated_calls(self):
        registry = _make_registry()
        goal = _make_goal(description="generate text from a prompt")
        request = PlannerRequest(goal_id=goal.resource_id, goal=goal, hints=[])
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Generate text from a prompt.")):
            first = await plan(request, registry, event_stream=AsyncMock())
            second = await plan(request, registry, event_stream=AsyncMock())
        assert first.execution_plan.confidence == second.execution_plan.confidence


# ── End-to-end: Planner confidence feeding OrchestrationGovernor ────────

class TestPlannerGovernanceIntegration:
    """Confirms the seam between Planner's own output (ExecutionPlan.confidence)
    and OrchestrationGovernor's ClarificationPolicy check actually lines up --
    plan() itself does not call governance (K4.2 §2 places that at Plan
    Compilation, a later packet), so this test exercises the handoff
    explicitly rather than asserting plan() does something it correctly
    does not do."""

    @pytest.mark.asyncio
    async def test_low_confidence_plan_would_escalate_via_orchestration_governor(self):
        from core.governance.orchestration_governor import OrchestrationGovernor
        from core.governance.governance_kernel import GovernanceAction, GovernanceVerdict

        registry = _make_registry()
        # Weak but non-zero overlap with llm_completion's description
        # (score ~0.1, verified below threshold but above _decompose's
        # own min_score=0.01 relevance floor) -- tests genuine low
        # confidence, not the impasse path (zero candidates), which is
        # covered separately by TestPlan.test_impasse_when_no_capability_matches.
        goal = _make_goal(description="write some text about the weather report")
        request = PlannerRequest(goal_id=goal.resource_id, goal=goal, hints=[])
        with patch("core.cognitive.planner.generate_with_fallback",
                   new=AsyncMock(return_value="Write some text about the weather report.")):
            result = await plan(request, registry, event_stream=AsyncMock())

        assert result.status == PlannerStatus.READY_FOR_COMPILATION
        assert result.execution_plan.confidence < 0.5

        governor = OrchestrationGovernor()
        policy = ClarificationPolicy()
        governance_result = governor.evaluate(GovernanceAction(
            worker_id="plan_compiler", action_type="plan_compilation",
            metadata={
                "confidence": result.execution_plan.confidence,
                "confidence_threshold": policy.confidence_threshold,
                "clarification_attempt": 0,
                "max_escalations": policy.max_escalations,
            },
        ))
        assert governance_result.verdict == GovernanceVerdict.ESCALATE
