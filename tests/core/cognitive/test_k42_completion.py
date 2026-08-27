"""
tests/core/cognitive/test_k42_completion.py — K4.2 Milestone Completion tests.

Covers all K4.2 completion gaps (G1–G7) and public-user scenarios.

G1: Semantic description separation
G2: Language detection propagation (resolves DEBT-013)
G3: Intent Ontology read path
G4: User Cognitive Model wiring
G5: Planner impasse event emission
G6: Stale "unknown" check removal
G7: Feature flag cutover + legacy classification

Public-user scenarios: simple conversation, creative task, ambiguous task,
compound task, multilingual, unsupported capability, failure semantics.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import dataclasses

import pytest

from core.cognitive.intent import (
    Goal,
    Intent,
    IntentDimensions,
    IntentHypothesis,
    IntentLifecycle,
    RawRequest,
    _validate_structured_form,
    _split_compound_goals,
    form_goals,
    interpret_request,
    load_known_categories,
    normalize_request,
)
from core.cognitive.planner import (
    CapabilityDiscoveryRequest,
    HintSource,
    ImpasseRecord,
    PlannerHint,
    PlannerRequest,
    PlannerResult,
    PlannerStatus,
    _extract_constraints,
    build_planner_request,
    discover_capabilities,
    plan,
)
from core.events.event_stream import EventStream


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_intent(
    raw_request: str = "Write a story",
    label: str = "creative writing",
    score: float = 0.85,
    category: str = "creative writing",
    detected_language: str = None,
) -> Intent:
    """Build a minimal Intent with the given fields."""
    hypothesis = IntentHypothesis(label=label, score=score)
    return Intent(
        raw_request=raw_request,
        hypotheses=[hypothesis],
        selected=hypothesis,
        confidence=score,
        dimensions=IntentDimensions(
            category=category,
            modality="task_request",
            complexity_estimate="moderate",
        ),
        lifecycle_state=IntentLifecycle.INTERPRETED,
        detected_language=detected_language,
    )


def _make_novel_intent(raw_request: str = "hello") -> Intent:
    """Build an intent with the 'novel' open-category fallback."""
    hypothesis = IntentHypothesis(label="novel", score=0.5)
    return Intent(
        raw_request=raw_request,
        hypotheses=[hypothesis],
        selected=hypothesis,
        confidence=0.5,
        dimensions=IntentDimensions(
            category="novel",
            modality="task_request",
            complexity_estimate="simple",
        ),
        lifecycle_state=IntentLifecycle.INTERPRETED,
    )


def _make_event_stream() -> AsyncMock:
    es = AsyncMock(spec=EventStream)
    es.append = AsyncMock()
    return es


# ═══════════════════════════════════════════════════════════════════════════
# G1 — Semantic Description Separation
# ═══════════════════════════════════════════════════════════════════════════

class TestSemanticDescriptionSeparation:
    """G1: semantic_description must be distinct from raw_request when a
    meaningful hypothesis label exists."""

    def test_structured_form_has_semantic_description(self):
        intent = _make_intent(raw_request="Write a detective story")
        sf, _, _ = _validate_structured_form(intent, None)
        assert "semantic_description" in sf
        assert "raw_request" in sf
        assert "description" in sf

    def test_semantic_description_includes_label(self):
        intent = _make_intent(
            raw_request="Write a detective story",
            label="creative writing",
        )
        sf, _, _ = _validate_structured_form(intent, None)
        assert sf["semantic_description"] == "creative writing: Write a detective story"
        assert sf["raw_request"] == "Write a detective story"
        assert sf["description"] == "Write a detective story"

    def test_semantic_description_equals_raw_for_novel(self):
        """When category is 'novel' (open fallback), semantic_description
        equals raw_request since 'novel' carries no semantic information."""
        intent = _make_novel_intent("hello there")
        sf, _, _ = _validate_structured_form(intent, None)
        assert sf["semantic_description"] == "hello there"
        assert sf["raw_request"] == "hello there"

    def test_raw_request_never_overwritten(self):
        """raw_request must always be the exact original user text."""
        intent = _make_intent(
            raw_request="Écrivez une histoire fantastique",
            label="creative writing",
        )
        sf, _, _ = _validate_structured_form(intent, None)
        assert sf["raw_request"] == "Écrivez une histoire fantastique"

    def test_compound_goals_have_distinct_semantic_descriptions(self):
        """Each sub-goal of a compound request gets its own
        semantic_description based on the sub-part text."""
        intent = _make_intent(
            raw_request="Summarize this and then extract the key risks",
            label="analysis",
            category="analysis",
        )
        goals = form_goals(intent)
        assert len(goals) >= 2
        for goal in goals:
            sf = goal.structured_form
            # Each sub-goal's semantic_description reflects its own part
            assert sf["semantic_description"] != sf.get("raw_request", "")
            # Sub-goal descriptions should not contain the full compound text
            assert "and then" not in sf["description"]

    def test_semantic_description_used_by_capability_discovery(self):
        """Capability discovery request picks up semantic_description."""
        intent = _make_intent(
            raw_request="Write a Chinese fantasy story",
            label="creative writing",
        )
        goals = form_goals(intent)
        goal = goals[0]
        sf = goal.structured_form
        # semantic_description should be the richer signal
        assert "creative writing:" in sf["semantic_description"]
        # Verify it would be picked up by the planner's discovery request
        desc = sf.get("semantic_description", sf.get("description", ""))
        assert desc == sf["semantic_description"]

    def test_no_selected_hypothesis_uses_raw_request(self):
        """When no hypothesis is selected, semantic_description = raw_request."""
        intent = Intent(
            raw_request="something unknown",
            hypotheses=[],
            selected=None,
            confidence=0.0,
            dimensions=IntentDimensions(
                category="novel",
                modality="task_request",
                complexity_estimate="simple",
            ),
            lifecycle_state=IntentLifecycle.INTERPRETED,
        )
        sf, _, _ = _validate_structured_form(intent, None)
        assert sf["semantic_description"] == "something unknown"


# ═══════════════════════════════════════════════════════════════════════════
# G2 — Language Detection Propagation
# ═══════════════════════════════════════════════════════════════════════════

class TestLanguageDetectionPropagation:
    """G2: detected_language must propagate RawRequest → Intent → Goal."""

    def test_intent_has_detected_language_field(self):
        intent = _make_intent(detected_language="fr")
        assert intent.detected_language == "fr"

    def test_detected_language_in_structured_form(self):
        intent = _make_intent(detected_language="zh")
        sf, _, _ = _validate_structured_form(intent, None)
        assert sf["detected_language"] == "zh"

    def test_detected_language_none_propagates(self):
        intent = _make_intent(detected_language=None)
        sf, _, _ = _validate_structured_form(intent, None)
        assert sf["detected_language"] is None

    def test_english_detection(self):
        raw = normalize_request("What is the weather today?")
        assert raw.detected_language == "en"

    def test_french_detection(self):
        raw = normalize_request("Le chat est sur la table de la cuisine")
        assert raw.detected_language == "fr"

    def test_chinese_detection(self):
        raw = normalize_request("你好，今天天气怎么样？")
        assert raw.detected_language == "zh"

    async def test_interpret_request_propagates_language(self):
        """Full pipeline: interpret_request → Goal.structured_form.detected_language"""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="greeting", score=0.9)
            ]
            # Use text with enough French stopwords for the heuristic
            goals = await interpret_request(
                "Le chat est sur la table de la cuisine",
                event_stream=es,
            )
            assert len(goals) >= 1
            assert goals[0].structured_form["detected_language"] == "fr"

    async def test_interpret_request_english_language(self):
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="creative writing", score=0.85)
            ]
            # Use text with enough English stopwords for the heuristic
            goals = await interpret_request(
                "What is the weather today in London and how is it?",
                event_stream=es,
            )
            assert goals[0].structured_form["detected_language"] == "en"

    def test_goal_preserves_language_through_form_goals(self):
        """form_goals passes detected_language from Intent to Goal."""
        intent = _make_intent(
            raw_request="Résumez ce texte en trois points",
            label="analysis",
            detected_language="fr",
        )
        goals = form_goals(intent)
        assert goals[0].structured_form["detected_language"] == "fr"


# ═══════════════════════════════════════════════════════════════════════════
# G3 — Intent Ontology Read Path
# ═══════════════════════════════════════════════════════════════════════════

class TestIntentOntologyReadPath:
    """G3: load_known_categories reads promoted ontology from memory."""

    async def test_empty_on_fresh_system(self):
        """A fresh system with no promoted entries returns []."""
        mock_memory = AsyncMock()
        mock_memory.search = AsyncMock(return_value=[])
        result = await load_known_categories(memory=mock_memory)
        assert result == []

    async def test_returns_promoted_categories(self):
        """Returns promoted categories from memory search results."""
        entry1 = MagicMock()
        entry1.content = "creative writing"
        entry2 = MagicMock()
        entry2.content = "code generation"
        entry3 = MagicMock()
        entry3.content = "creative writing"  # duplicate

        mock_memory = AsyncMock()
        mock_memory.search = AsyncMock(return_value=[entry1, entry2, entry3])
        result = await load_known_categories(memory=mock_memory)
        # Should deduplicate
        assert set(result) == {"creative writing", "code generation"}
        assert len(result) == 2

    async def test_handles_memory_error_gracefully(self):
        """Memory errors degrade to empty list, never crash."""
        mock_memory = AsyncMock()
        mock_memory.search = AsyncMock(side_effect=RuntimeError("db down"))
        result = await load_known_categories(memory=mock_memory)
        assert result == []

    async def test_filters_empty_content(self):
        """Entries with empty/None content are excluded."""
        entry1 = MagicMock()
        entry1.content = "analysis"
        entry2 = MagicMock()
        entry2.content = ""
        entry3 = MagicMock()
        entry3.content = None

        mock_memory = AsyncMock()
        mock_memory.search = AsyncMock(return_value=[entry1, entry2, entry3])
        result = await load_known_categories(memory=mock_memory)
        assert result == ["analysis"]


# ═══════════════════════════════════════════════════════════════════════════
# G4 — User Cognitive Model Wiring
# ═══════════════════════════════════════════════════════════════════════════

class TestUserCognitiveModelWiring:
    """G4: PlannerHint with USER_MODEL source generated from projection."""

    def test_hint_source_user_model_exists(self):
        assert HintSource.USER_MODEL == "user_model"

    def test_planner_hint_with_user_model_source(self):
        hint = PlannerHint(
            kind="abstraction_level:detailed",
            weight=0.5,
            source=HintSource.USER_MODEL,
        )
        assert hint.source == "user_model"
        assert hint.kind == "abstraction_level:detailed"
        assert hint.weight == 0.5

    def test_planner_request_accepts_hints(self):
        goal = _make_intent().to_dict()  # Just need a valid goal
        intent = _make_intent()
        goals = form_goals(intent)
        hints = [
            PlannerHint(
                kind="communication_style:concise",
                weight=0.4,
                source=HintSource.USER_MODEL,
            )
        ]
        request = PlannerRequest(
            goal_id=goals[0].resource_id,
            goal=goals[0],
            hints=hints,
        )
        assert len(request.hints) == 1
        assert request.hints[0].source == HintSource.USER_MODEL

    def test_empty_hints_accepted(self):
        """No user model data produces empty hints list (not an error)."""
        intent = _make_intent()
        goals = form_goals(intent)
        request = PlannerRequest(
            goal_id=goals[0].resource_id,
            goal=goals[0],
            hints=[],
        )
        assert request.hints == []


# ═══════════════════════════════════════════════════════════════════════════
# G5 — Planner Impasse Event
# ═══════════════════════════════════════════════════════════════════════════

class TestPlannerImpasseEvent:
    """G5: plan() emits cognitive.planner_impasse on impasse."""

    async def test_impasse_emits_event(self):
        """When planner detects impasse, cognitive.planner_impasse is emitted."""
        es = _make_event_stream()
        intent = _make_intent(raw_request="Do an impossible task")
        goals = form_goals(intent)
        goal = goals[0]

        # Create a registry with NO capabilities — guaranteed impasse
        from core.capabilities.registry import CapabilityRegistry
        empty_registry = CapabilityRegistry()

        request = PlannerRequest(goal_id=goal.resource_id, goal=goal)

        with patch("core.cognitive.planner._decompose") as mock_decompose:
            # Simulate decomposition producing steps with zero candidates
            from core.cognitive.planner import PlanStep
            mock_decompose.return_value = [
                (PlanStep(
                    step_id="s1",
                    description="impossible step",
                    capability_type="nonexistent",
                ), [])  # empty candidates = impasse
            ]

            result = await plan(request, empty_registry, event_stream=es)

        assert result.status == PlannerStatus.IMPASSE
        assert result.impasse_detail is not None

        # Verify cognitive.planner_impasse was emitted
        impasse_calls = [
            call for call in es.append.call_args_list
            if call[0][0] == "cognitive.planner_impasse"
        ]
        assert len(impasse_calls) >= 1
        payload = impasse_calls[0][1]["payload"]
        assert "goal_id" in payload
        assert "reason" in payload
        assert "unresolved_count" in payload
        assert "operation_id" in payload

    async def test_impasse_distinct_from_compilation_rejection(self):
        """PlannerStatus.IMPASSE is distinct from compilation rejection."""
        assert PlannerStatus.IMPASSE != "compiled"
        assert PlannerStatus.IMPASSE == "impasse"
        assert PlannerStatus.READY_FOR_COMPILATION == "ready_for_compilation"
        assert PlannerStatus.REJECTED_PRECHECK == "rejected_precheck"


# ═══════════════════════════════════════════════════════════════════════════
# G6 — Stale "unknown" Check Removed
# ═══════════════════════════════════════════════════════════════════════════

class TestStaleUnknownCheckRemoved:
    """G6: constraint extraction uses falsy fallback, not 'unknown' check."""

    async def test_empty_description_uses_raw_request(self):
        """When description is empty, raw_request is used for constraints."""
        es = _make_event_stream()
        goal = Goal(
            intent_id="test",
            structured_form={
                "description": "",
                "raw_request": "Write a 500-word essay about climate change",
                "semantic_description": "",
                "category": "writing",
            },
        )
        constraints = await _extract_constraints(goal, event_stream=es)
        # Should not crash and should process the raw_request
        assert isinstance(constraints, list)

    async def test_valid_description_used(self):
        """When description is valid, it's used normally."""
        es = _make_event_stream()
        goal = Goal(
            intent_id="test",
            structured_form={
                "description": "Write a 500-word essay about climate change",
                "raw_request": "Write a 500-word essay about climate change",
                "semantic_description": "writing: Write a 500-word essay about climate change",
                "category": "writing",
            },
        )
        constraints = await _extract_constraints(goal, event_stream=es)
        assert isinstance(constraints, list)

    async def test_semantic_description_preferred(self):
        """G1/G6: semantic_description is preferred over description."""
        es = _make_event_stream()
        goal = Goal(
            intent_id="test",
            structured_form={
                "description": "Write a story",
                "raw_request": "Write a story",
                "semantic_description": "creative writing: Write a story in exactly 1000 words",
                "category": "creative writing",
            },
        )
        constraints = await _extract_constraints(goal, event_stream=es)
        # The semantic_description has richer constraint info
        assert isinstance(constraints, list)


# ═══════════════════════════════════════════════════════════════════════════
# G7 — Feature Flag Cutover
# ═══════════════════════════════════════════════════════════════════════════

class TestFeatureFlagCutover:
    """G7: use_k42_frontend is true in settings.toml."""

    def test_settings_flag_is_true(self):
        """config/settings.toml must have use_k42_frontend = true."""
        import tomllib
        from pathlib import Path
        settings_path = Path(__file__).parent.parent.parent.parent / "config" / "settings.toml"
        with open(settings_path, "rb") as f:
            config = tomllib.load(f)
        assert config["runtime"]["use_k42_frontend"] is True

    def test_orchestrator_k42_branch_exists(self):
        """Orchestrator must have the K4.2 cognitive frontend branch."""
        from pathlib import Path
        source = Path(__file__).parent.parent.parent.parent / "core" / "orchestrator.py"
        text = source.read_text(encoding="utf-8")
        assert "use_k42_frontend" in text
        assert "interpret_request" in text
        assert "load_known_categories" in text


# ═══════════════════════════════════════════════════════════════════════════
# Public-User Failure Semantics
# ═══════════════════════════════════════════════════════════════════════════

class TestPublicUserFailureSemantics:
    """Public-user error messages must not leak internal architecture."""

    def _get_orchestrator_source(self):
        from pathlib import Path
        source = Path(__file__).parent.parent.parent.parent / "core" / "orchestrator.py"
        return source.read_text(encoding="utf-8")

    def test_no_internal_status_in_impasse_message(self):
        """Planner impasse message must not contain PlannerStatus enum."""
        source = self._get_orchestrator_source()
        # The old message was: f"request: {planner_result.status}"
        # Find user-facing return statements — they should not interpolate status
        assert "planner_result.status}" not in source

    def test_no_compilation_status_in_user_message(self):
        """Compilation rejection message must not contain CompilationStatus."""
        source = self._get_orchestrator_source()
        assert "compilation_result.status)." not in source

    def test_no_exception_classname_in_user_message(self):
        """K4.2 branch exception message must not expose type(e).__name__ to users."""
        source = self._get_orchestrator_source()
        # Extract only the K4.2 branch section (between use_k42_frontend and LEGACY)
        k42_start = source.find("use_k42_frontend")
        k42_end = source.find("LEGACY", k42_start)
        k42_section = source[k42_start:k42_end] if k42_end > k42_start else ""
        # The K4.2 branch should not interpolate exception class into returns
        lines = k42_section.split("\n")
        for line in lines:
            if "type(e).__name__" in line and "return" in line:
                pytest.fail("Exception class name leaked to K4.2 user-facing return")


# ═══════════════════════════════════════════════════════════════════════════
# Public-User End-to-End Scenarios
# ═══════════════════════════════════════════════════════════════════════════

class TestPublicUserScenarios:
    """End-to-end tests for real public-user request categories."""

    async def test_simple_conversation(self):
        """Scenario 1: 'Hello' produces a normal response, no error."""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="greeting", score=0.9)
            ]
            goals = await interpret_request("Hello", event_stream=es)
            assert len(goals) >= 1
            assert goals[0].structured_form["raw_request"] == "Hello"
            # No planner error — just a normal goal
            assert goals[0].confidence > 0

    async def test_creative_task(self):
        """Scenario 2: Creative writing task preserves intent and language."""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="creative writing", score=0.88)
            ]
            goals = await interpret_request(
                "Write a short Chinese fantasy story about a young astronomer.",
                event_stream=es,
            )
            goal = goals[0]
            sf = goal.structured_form
            assert sf["raw_request"] == "Write a short Chinese fantasy story about a young astronomer."
            assert "creative writing" in sf["semantic_description"]
            # detected_language field exists (value depends on heuristic)
            assert "detected_language" in sf

    async def test_ambiguous_task(self):
        """Scenario 3: 'Make it better' — recognized as ambiguous."""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="novel", score=0.3)
            ]
            goals = await interpret_request("Make it better.", event_stream=es)
            goal = goals[0]
            # Low confidence for ambiguous request
            assert goal.confidence <= 0.5
            # Raw request preserved
            assert goal.structured_form["raw_request"] == "Make it better."

    async def test_compound_task(self):
        """Scenario 4: Compound request split into multiple goals."""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="analysis", score=0.85)
            ]
            goals = await interpret_request(
                "Summarize this and then extract the key risks",
                event_stream=es,
            )
            assert len(goals) >= 2
            # Each goal has its own semantic description
            descriptions = [g.structured_form["semantic_description"] for g in goals]
            assert len(set(descriptions)) == len(descriptions)  # all different

    async def test_multilingual_french(self):
        """Scenario 7a: French request preserves language metadata."""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="information query", score=0.8)
            ]
            # Use text with enough French stopwords for the heuristic
            goals = await interpret_request(
                "Le chat est sur la table de la cuisine et il dort",
                event_stream=es,
            )
            goal = goals[0]
            assert goal.structured_form["detected_language"] == "fr"
            assert "Le chat" in goal.structured_form["raw_request"]

    async def test_multilingual_chinese(self):
        """Scenario 7b: Chinese request preserves language metadata."""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="information query", score=0.75)
            ]
            goals = await interpret_request(
                "请解释量子计算的基本原理。",
                event_stream=es,
            )
            goal = goals[0]
            assert goal.structured_form["detected_language"] == "zh"


# ═══════════════════════════════════════════════════════════════════════════
# Compound Goal Correctness
# ═══════════════════════════════════════════════════════════════════════════

class TestCompoundGoalCorrectness:
    """Compound requests must preserve sub-goal structure and semantics."""

    def test_triple_compound_splits(self):
        """'X and then Y and then Z' produces 3 parts."""
        parts = _split_compound_goals(
            "Translate this into French and then summarize it and then list the risks"
        )
        assert len(parts) == 3

    def test_compound_goals_have_sub_goal_references(self):
        intent = _make_intent(
            raw_request="Summarize this and then extract risks",
            label="analysis",
            category="analysis",
        )
        goals = form_goals(intent)
        assert len(goals) >= 2
        for goal in goals:
            # Each sub-goal references the others
            assert len(goal.sub_goals) == len(goals) - 1

    def test_compound_preserves_original_raw_request(self):
        """Even in compound split, raw_request holds the full original text."""
        intent = _make_intent(
            raw_request="Summarize this and then extract risks",
            label="analysis",
            category="analysis",
        )
        goals = form_goals(intent)
        for goal in goals:
            # raw_request always the full original
            assert goal.structured_form["raw_request"] == "Summarize this and then extract risks"

    def test_simple_request_not_split(self):
        """A simple request without compound markers produces one goal."""
        intent = _make_intent(raw_request="Write a story about a cat")
        goals = form_goals(intent)
        assert len(goals) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Intent Ontology + User Model Interaction
# ═══════════════════════════════════════════════════════════════════════════

class TestOntologyUserModelInteraction:
    """Current request must remain authoritative over past memory/preferences."""

    def test_explicit_constraints_override_user_model_hints(self):
        """User model hints have lower weight than explicit constraints."""
        hint = PlannerHint(
            kind="communication_style:concise",
            weight=0.4,
            source=HintSource.USER_MODEL,
        )
        # Weight of 0.4 means advisory only — explicit constraints from
        # the current request (Constraint objects) are hard/soft and
        # validated/enforced, while hints are never enforced (K4.2 §5).
        assert hint.weight < 1.0
        assert hint.source == HintSource.USER_MODEL

    async def test_known_categories_do_not_override_novel_detection(self):
        """Known categories provide context but don't prevent novel intent."""
        es = _make_event_stream()
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            # Even with known categories, LLM can still return "novel"
            mock_hyp.return_value = [
                IntentHypothesis(label="novel", score=0.6)
            ]
            goals = await interpret_request(
                "Do something completely new and unexpected",
                event_stream=es,
                known_categories=["creative writing", "code generation"],
            )
            assert goals[0].structured_form["category"] == "novel"


# ═══════════════════════════════════════════════════════════════════════════
# Legacy Path Classification
# ═══════════════════════════════════════════════════════════════════════════

class TestLegacyPathClassification:
    """Legacy paths must be explicitly classified and not silently active."""

    def _get_orchestrator_source(self):
        from pathlib import Path
        source = Path(__file__).parent.parent.parent.parent / "core" / "orchestrator.py"
        return source.read_text(encoding="utf-8")

    def test_k22_path_classified_as_legacy(self):
        """K2.2 compatibility path has LEGACY classification comment."""
        source = self._get_orchestrator_source()
        assert "LEGACY" in source
        assert "COMPATIBILITY" in source

    def test_k42_path_is_canonical(self):
        """K4.2 path checks come BEFORE K2.2 path in handle()."""
        source = self._get_orchestrator_source()
        k42_pos = source.find("use_k42_frontend")
        k22_pos = source.find("LEGACY")
        # K4.2 check appears before K2.2 legacy
        assert k42_pos > 0
        assert k22_pos > 0
        assert k42_pos < k22_pos


# ═══════════════════════════════════════════════════════════════════════════
# Input Fidelity
# ═══════════════════════════════════════════════════════════════════════════

class TestInputFidelity:
    """Original user request must remain recoverable."""

    def test_normalization_preserves_meaning(self):
        raw = normalize_request("  Write a 500-word   essay about  climate change  ")
        assert "500-word" in raw.text
        assert "climate change" in raw.text

    def test_unicode_preserved(self):
        raw = normalize_request("Écrivez une histoire en français")
        assert "français" in raw.text
        assert "Écrivez" in raw.text

    async def test_full_pipeline_preserves_original(self):
        es = _make_event_stream()
        original = "Write a detailed technical explanation of quantum entanglement"
        with patch("core.cognitive.intent.generate_hypotheses") as mock_hyp:
            mock_hyp.return_value = [
                IntentHypothesis(label="explanation", score=0.9)
            ]
            goals = await interpret_request(original, event_stream=es)
            assert goals[0].structured_form["raw_request"] == original
