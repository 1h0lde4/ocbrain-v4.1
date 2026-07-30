"""Tests for core/cognitive/learning.py — Packet 04, K4.2.6 Shared
ValidationGate + Learning Wiring.

Architecture: OCBRAIN_K4_2_COGNITIVE_FRONTEND_ARCHITECTURE_AUTHORITATIVE.md
§6, §8, §11, §12, §13, §16 item 1.
"""
import ast
import inspect
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from core.cognitive import learning as learning_module
from core.cognitive.learning import (
    CognitiveDecision,
    CognitiveVerdict,
    ContentDomain,
    ContradictionCheckError,
    DEFAULT_SCORE_FLOOR,
    LearningLifecycle,
    LearningRecord,
    LearningTier,
    _find_contradiction,
    _is_textual_contradiction,
    validation_gate,
)
from core.governance.governance_kernel import EvolutionGovernor, GovernanceKernel


# ─────────────────────────────────────────────────────────────────────────
# Test doubles
# ─────────────────────────────────────────────────────────────────────────

class MockEventStream:
    """Minimal EventStream mock for testing event emission (mirrors
    tests/core/cognitive/test_planner.py's MockEventStream exactly)."""

    def __init__(self):
        self.events = []

    async def append(self, event_type, source, payload):
        self.events.append({
            "event_type": event_type,
            "source": source,
            "payload": payload,
        })


class FakeEntry:
    """Minimal KnowledgeEntry double carrying only the fields
    _find_contradiction reads."""

    def __init__(self, entry_id, content, truth_status="verified", metadata=None):
        self.entry_id = entry_id
        self.content = content
        self.truth_status = truth_status
        self.metadata = metadata or {}


class FakeSearchResult:
    def __init__(self, entry):
        self.entry = entry


class MockMemory:
    """Minimal UnifiedMemory double: records writes, returns a pre-set
    list of search results, and can simulate a search-backend failure to
    exercise the fail-closed contradiction-check path."""

    def __init__(self, search_results=None, raise_on_search=False):
        self.writes: List[Dict[str, Any]] = []
        self._search_results = search_results if search_results is not None else []
        self._raise_on_search = raise_on_search
        self.search_calls = 0

    async def write(self, *, content, content_type="", importance=0.5,
                     truth_status=None, metadata=None, derived_from=None,
                     source="", procedure_name=None, **kwargs):
        entry_id = f"entry-{len(self.writes) + 1}"
        self.writes.append({
            "entry_id": entry_id,
            "content": content,
            "content_type": content_type,
            "importance": importance,
            "truth_status": truth_status,
            "metadata": metadata,
            "derived_from": derived_from,
            "procedure_name": procedure_name,
        })
        return entry_id

    async def search(self, query, limit=10, **kwargs):
        self.search_calls += 1
        if self._raise_on_search:
            raise RuntimeError("simulated search backend failure")
        return self._search_results


class CountingGovernanceKernel(GovernanceKernel):
    """Real GovernanceKernel (not a mock of it) that additionally counts
    evaluate_action() calls. Used to pin down, as an executable
    assertion rather than just a read-through-the-code claim, that every
    Evolution-tier code path in validation_gate() consults
    EvolutionGovernor through exactly one evaluate_action() call --
    never zero on a path that promotes/escalates, never more than one on
    any path."""

    def __init__(self):
        super().__init__()
        self.evaluate_calls = 0

    def evaluate_action(self, action):
        self.evaluate_calls += 1
        return super().evaluate_action(action)


# ─────────────────────────────────────────────────────────────────────────
# Data contracts — K4.2 §12
# ─────────────────────────────────────────────────────────────────────────

class TestCognitiveDecisionDataclass:
    def test_defaults(self):
        d = CognitiveDecision()
        assert d.action_type == ""
        assert d.subject_ref == ""
        assert d.verdict == CognitiveVerdict.REJECT
        assert d.reason == ""
        assert isinstance(d.evaluated_at, float)

    def test_fields_settable(self):
        d = CognitiveDecision(
            action_type="intent_ontology_promote",
            subject_ref="cat-1",
            verdict=CognitiveVerdict.ESCALATE,
            reason="pending HITL",
        )
        assert d.action_type == "intent_ontology_promote"
        assert d.verdict == CognitiveVerdict.ESCALATE


class TestLearningRecordDataclass:
    def test_defaults(self):
        r = LearningRecord()
        assert r.tier == LearningTier.LEARNING
        assert r.content_domain == ""
        assert r.trigger_signals == []
        assert isinstance(r.gate_result, CognitiveDecision)
        assert r.resulting_entry_ref is None
        assert r.lifecycle_state == LearningLifecycle.OBSERVED

    def test_independent_default_factories(self):
        # Two independently-constructed records must not share the same
        # mutable trigger_signals list or gate_result object.
        r1 = LearningRecord()
        r2 = LearningRecord()
        assert r1.trigger_signals is not r2.trigger_signals
        assert r1.gate_result is not r2.gate_result


# ─────────────────────────────────────────────────────────────────────────
# Contradiction heuristic
# ─────────────────────────────────────────────────────────────────────────

class TestIsTextualContradiction:
    def test_negation_with_shared_content_is_contradiction(self):
        a = "the deploy step requires manual approval"
        b = "the deploy step never requires approval"
        assert _is_textual_contradiction(a, b) is True

    def test_both_affirmative_is_not_contradiction(self):
        a = "the deploy step requires manual approval"
        b = "the deploy step requires manual sign-off"
        assert _is_textual_contradiction(a, b) is False

    def test_both_negated_is_not_contradiction(self):
        a = "the deploy step never requires approval"
        b = "the deploy step does not require approval"
        assert _is_textual_contradiction(a, b) is False

    def test_negation_without_shared_content_is_not_contradiction(self):
        a = "the deploy step never requires approval"
        b = "the invoice was not paid on time"
        assert _is_textual_contradiction(a, b) is False

    def test_empty_strings_are_not_contradictions(self):
        assert _is_textual_contradiction("", "something") is False
        assert _is_textual_contradiction("something", "") is False
        assert _is_textual_contradiction("", "") is False


class TestFindContradiction:
    async def test_returns_none_when_no_results(self):
        memory = MockMemory(search_results=[])
        result = await _find_contradiction(
            ContentDomain.INTENT_ONTOLOGY, "candidate text", memory,
        )
        assert result is None

    async def test_ignores_non_verified_entries(self):
        entry = FakeEntry(
            "e1", "the deploy step never requires approval",
            truth_status="candidate",
            metadata={"content_domain": ContentDomain.INTENT_ONTOLOGY},
        )
        memory = MockMemory(search_results=[FakeSearchResult(entry)])
        result = await _find_contradiction(
            ContentDomain.INTENT_ONTOLOGY,
            "the deploy step requires manual approval",
            memory,
        )
        assert result is None

    async def test_ignores_different_domain_entries(self):
        entry = FakeEntry(
            "e1", "the deploy step never requires approval",
            truth_status="verified",
            metadata={"content_domain": ContentDomain.SKILL},
        )
        memory = MockMemory(search_results=[FakeSearchResult(entry)])
        result = await _find_contradiction(
            ContentDomain.INTENT_ONTOLOGY,
            "the deploy step requires manual approval",
            memory,
        )
        assert result is None

    async def test_finds_matching_domain_verified_contradiction(self):
        entry = FakeEntry(
            "e1", "the deploy step never requires approval",
            truth_status="verified",
            metadata={"content_domain": ContentDomain.INTENT_ONTOLOGY},
        )
        memory = MockMemory(search_results=[FakeSearchResult(entry)])
        result = await _find_contradiction(
            ContentDomain.INTENT_ONTOLOGY,
            "the deploy step requires manual approval",
            memory,
        )
        assert result == "e1"

    async def test_search_failure_raises_contradiction_check_error(self):
        memory = MockMemory(raise_on_search=True)
        with pytest.raises(ContradictionCheckError):
            await _find_contradiction(
                ContentDomain.INTENT_ONTOLOGY, "candidate text", memory,
            )


# ─────────────────────────────────────────────────────────────────────────
# validation_gate — input validation
# ─────────────────────────────────────────────────────────────────────────

class TestValidationGateInputValidation:
    async def test_unknown_tier_raises(self):
        with pytest.raises(ValueError):
            await validation_gate(
                tier="not_a_tier",
                content_domain=ContentDomain.INTENT_ONTOLOGY,
                subject_ref="x", candidate_content="y", trigger_signals=[],
                memory=MockMemory(), governance=GovernanceKernel(),
                event_stream=MockEventStream(),
            )

    async def test_unknown_content_domain_raises(self):
        with pytest.raises(ValueError):
            await validation_gate(
                tier=LearningTier.LEARNING,
                content_domain="not_a_domain",
                subject_ref="x", candidate_content="y", trigger_signals=[],
                memory=MockMemory(), governance=GovernanceKernel(),
                event_stream=MockEventStream(),
            )


# ─────────────────────────────────────────────────────────────────────────
# validation_gate — LEARNING tier (routine, existing memory_write gate
# only; K4.2 §8)
# ─────────────────────────────────────────────────────────────────────────

class TestValidationGateLearningTier:
    async def test_writes_directly_and_emits_pattern_learned(self):
        memory = MockMemory()
        events = MockEventStream()
        record = await validation_gate(
            tier=LearningTier.LEARNING,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1",
            candidate_content="a routine observed instance",
            trigger_signals=["execution_outcome"],
            memory=memory, governance=GovernanceKernel(), event_stream=events,
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert record.gate_result.verdict == CognitiveVerdict.PROCEED
        assert record.resulting_entry_ref == memory.writes[0]["entry_id"]
        assert len(memory.writes) == 1
        assert events.events[0]["event_type"] == "cognitive.pattern_learned"
        assert events.events[0]["payload"]["content_domain"] == ContentDomain.INTENT_ONTOLOGY

    async def test_no_contradiction_check_performed(self):
        # Learning tier must never call search() -- it is routine, per
        # K4.2 §8, and does not gate on contradiction.
        memory = MockMemory(raise_on_search=True)
        record = await validation_gate(
            tier=LearningTier.LEARNING,
            content_domain=ContentDomain.SKILL,
            subject_ref="", candidate_content="anything",
            trigger_signals=[],
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert memory.search_calls == 0

    async def test_no_held_out_score_required(self):
        memory = MockMemory()
        record = await validation_gate(
            tier=LearningTier.LEARNING,
            content_domain=ContentDomain.USER_MODEL,
            subject_ref="", candidate_content="anything",
            trigger_signals=[], held_out_score=None,
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED


# ─────────────────────────────────────────────────────────────────────────
# validation_gate — ADAPTATION tier (strict held-out improvement +
# contradiction check; no GovernanceKernel call; no dedicated event)
# ─────────────────────────────────────────────────────────────────────────

class TestValidationGateAdaptationTier:
    async def test_promotes_only_after_clearing_gate(self):
        memory = MockMemory(search_results=[])
        events = MockEventStream()
        record = await validation_gate(
            tier=LearningTier.ADAPTATION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1",
            candidate_content="tuned category boundary",
            trigger_signals=["reflection"],
            held_out_score=0.9, baseline_score=0.7,
            memory=memory, governance=GovernanceKernel(), event_stream=events,
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert record.gate_result.verdict == CognitiveVerdict.PROCEED
        assert len(memory.writes) == 1
        assert memory.writes[0]["truth_status"] == "candidate"
        # No K4.2.6 event is named for Adaptation tier.
        assert events.events == []

    async def test_rejected_without_held_out_score(self):
        memory = MockMemory()
        record = await validation_gate(
            tier=LearningTier.ADAPTATION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1", candidate_content="tuned boundary",
            trigger_signals=[], held_out_score=None,
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.REJECTED
        assert memory.writes == []

    async def test_rejected_when_improvement_not_strict(self):
        memory = MockMemory()
        record = await validation_gate(
            tier=LearningTier.ADAPTATION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1", candidate_content="tuned boundary",
            trigger_signals=[], held_out_score=0.7, baseline_score=0.7,
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.REJECTED
        assert memory.writes == []

    async def test_uses_default_floor_when_no_baseline(self):
        memory = MockMemory()
        below = await validation_gate(
            tier=LearningTier.ADAPTATION, content_domain=ContentDomain.SKILL,
            subject_ref="", candidate_content="c", trigger_signals=[],
            held_out_score=DEFAULT_SCORE_FLOOR, baseline_score=None,
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert below.lifecycle_state == LearningLifecycle.REJECTED

        above = await validation_gate(
            tier=LearningTier.ADAPTATION, content_domain=ContentDomain.SKILL,
            subject_ref="", candidate_content="c", trigger_signals=[],
            held_out_score=DEFAULT_SCORE_FLOOR + 0.1, baseline_score=None,
            memory=MockMemory(), governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert above.lifecycle_state == LearningLifecycle.PROMOTED

    async def test_contradiction_fixture_blocked_pre_promotion(self):
        entry = FakeEntry(
            "verified-1", "the deploy step never requires approval",
            truth_status="verified",
            metadata={"content_domain": ContentDomain.INTENT_ONTOLOGY},
        )
        memory = MockMemory(search_results=[FakeSearchResult(entry)])
        record = await validation_gate(
            tier=LearningTier.ADAPTATION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1",
            candidate_content="the deploy step requires manual approval",
            trigger_signals=[], held_out_score=0.95, baseline_score=0.5,
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.REJECTED
        assert "verified-1" in record.gate_result.reason
        assert memory.writes == []

    async def test_contradiction_check_search_failure_fails_closed(self):
        memory = MockMemory(raise_on_search=True)
        record = await validation_gate(
            tier=LearningTier.ADAPTATION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1", candidate_content="anything",
            trigger_signals=[], held_out_score=0.95, baseline_score=0.5,
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.REJECTED
        assert memory.writes == []


# ─────────────────────────────────────────────────────────────────────────
# validation_gate — EVOLUTION tier (+ EvolutionGovernor.
# SELF_MODIFYING_ACTIONS; "never automatic", K4.2 §8)
# ─────────────────────────────────────────────────────────────────────────

class TestValidationGateEvolutionTier:
    async def test_never_automatic_escalates_by_default(self):
        # Real GovernanceKernel (not a mock) -- this must go through the
        # actual EvolutionGovernor logic, since "never automatic" is the
        # single most safety-relevant property of this tier.
        memory = MockMemory(search_results=[])
        events = MockEventStream()
        governance = CountingGovernanceKernel()
        record = await validation_gate(
            tier=LearningTier.EVOLUTION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="new-category",
            candidate_content="a brand new archetype",
            trigger_signals=["reflection"],
            held_out_score=0.95, baseline_score=None,
            memory=memory, governance=governance, event_stream=events,
        )
        assert record.lifecycle_state == LearningLifecycle.GATED
        assert record.gate_result.verdict == CognitiveVerdict.ESCALATE
        # Governance boundary: consulted exactly once, not skipped (this
        # is what makes "never automatic" real rather than aspirational).
        assert governance.evaluate_calls == 1
        assert memory.writes == []
        assert events.events == []

    async def test_completes_when_hitl_approved(self):
        memory = MockMemory(search_results=[])
        events = MockEventStream()
        governance = CountingGovernanceKernel()
        record = await validation_gate(
            tier=LearningTier.EVOLUTION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="new-category",
            candidate_content="a brand new archetype",
            trigger_signals=["reflection"],
            held_out_score=0.95, baseline_score=None, hitl_approved=True,
            memory=memory, governance=governance, event_stream=events,
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert record.gate_result.verdict == CognitiveVerdict.PROCEED
        assert len(memory.writes) == 1
        assert memory.writes[0]["truth_status"] == "verified"
        assert events.events[0]["event_type"] == "cognitive.ontology_evolved"
        # Governance boundary: hitl_approved changed what GovernanceKernel
        # answered (APPROVE instead of ESCALATE), not whether it was
        # asked -- still exactly one real evaluate_action() call, proving
        # hitl_approved cannot be used to skip governance entirely.
        assert governance.evaluate_calls == 1

    async def test_skill_domain_already_registered(self):
        # "skill_promote" pre-dates K4.2.6 -- proves this packet did not
        # need to (and did not) touch it.
        memory = MockMemory(search_results=[])
        governance = CountingGovernanceKernel()
        record = await validation_gate(
            tier=LearningTier.EVOLUTION, content_domain=ContentDomain.SKILL,
            subject_ref="new-skill", candidate_content="a new skill",
            trigger_signals=[], held_out_score=0.95, hitl_approved=True,
            memory=memory, governance=governance,
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert governance.evaluate_calls == 1

    async def test_user_model_propose_for_new_entry(self):
        # K4.2 §3: a genuinely new User Model entry uses "user_model_propose",
        # registered by this packet (Packet 05). is_new_entry defaults to
        # True, matching "propose" being the common case (first-time
        # capture of a preference/pattern never recorded before).
        memory = MockMemory(search_results=[])
        events = MockEventStream()
        governance = CountingGovernanceKernel()
        record = await validation_gate(
            tier=LearningTier.EVOLUTION, content_domain=ContentDomain.USER_MODEL,
            subject_ref="new-insight", candidate_content="a new insight",
            trigger_signals=[], held_out_score=0.95, hitl_approved=True,
            procedure_name="user_model:communication_style",
            memory=memory, governance=governance, event_stream=events,
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert record.gate_result.action_type == "user_model_propose"
        assert governance.evaluate_calls == 1
        assert memory.writes[0]["procedure_name"] == "user_model:communication_style"
        # K4.2 §11: User Model gets its own event, not cognitive.ontology_evolved.
        assert events.events[0]["event_type"] == "cognitive.user_model_updated"

    async def test_user_model_promote_for_revision(self):
        # is_new_entry=False -- revising an existing, already-promoted
        # entry uses "user_model_promote" instead (reusing the same verb
        # SKILL/INTENT_ONTOLOGY already use for their one-and-only action).
        memory = MockMemory(search_results=[])
        events = MockEventStream()
        governance = CountingGovernanceKernel()
        record = await validation_gate(
            tier=LearningTier.EVOLUTION, content_domain=ContentDomain.USER_MODEL,
            subject_ref="existing-entry-1", candidate_content="a revised insight",
            trigger_signals=[], held_out_score=0.95, hitl_approved=True,
            is_new_entry=False,
            memory=memory, governance=governance, event_stream=events,
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert record.gate_result.action_type == "user_model_promote"
        assert governance.evaluate_calls == 1
        assert events.events[0]["event_type"] == "cognitive.user_model_updated"

    async def test_unregistered_action_type_defensive_guard(self):
        # The original point of this test (before Packet 05 legitimately
        # registered user_model_propose/user_model_promote) was to prove
        # the defensive "reject rather than silently auto-approve" guard
        # for any action_type EvolutionGovernor doesn't recognize. With
        # all three real content domains now registered, that guard is
        # exercised here via a temporarily patched registry instead --
        # same invariant, no longer tied to a domain's registration status.
        with patch.object(EvolutionGovernor, "SELF_MODIFYING_ACTIONS", {"skill_promote"}):
            memory = MockMemory(search_results=[])
            record = await validation_gate(
                tier=LearningTier.EVOLUTION, content_domain=ContentDomain.USER_MODEL,
                subject_ref="new-insight", candidate_content="a new insight",
                trigger_signals=[], held_out_score=0.95, hitl_approved=True,
                memory=memory, governance=GovernanceKernel(),
                event_stream=MockEventStream(),
            )
        assert record.lifecycle_state == LearningLifecycle.REJECTED
        assert memory.writes == []

    async def test_contradiction_blocks_before_governance_is_consulted(self):
        entry = FakeEntry(
            "verified-1", "the deploy step never requires approval",
            truth_status="verified",
            metadata={"content_domain": ContentDomain.INTENT_ONTOLOGY},
        )
        memory = MockMemory(search_results=[FakeSearchResult(entry)])

        governance = CountingGovernanceKernel()
        record = await validation_gate(
            tier=LearningTier.EVOLUTION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1",
            candidate_content="the deploy step requires manual approval",
            trigger_signals=[], held_out_score=0.95, hitl_approved=True,
            memory=memory, governance=governance, event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.REJECTED
        assert governance.evaluate_calls == 0
        assert memory.writes == []

    async def test_rejected_without_held_out_score_never_reaches_governance(self):
        governance = CountingGovernanceKernel()
        record = await validation_gate(
            tier=LearningTier.EVOLUTION,
            content_domain=ContentDomain.INTENT_ONTOLOGY,
            subject_ref="cat-1", candidate_content="anything",
            trigger_signals=[], held_out_score=None, hitl_approved=True,
            memory=MockMemory(), governance=governance,
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.REJECTED
        assert governance.evaluate_calls == 0


# ─────────────────────────────────────────────────────────────────────────
# Shared code path — K4.2 §16 item 1's explicit completion criterion:
# "Same gate function confirmed to serve all three content domains via
# one code path."
# ─────────────────────────────────────────────────────────────────────────

class TestValidationGateSharedCodePath:
    @pytest.mark.parametrize("domain", ContentDomain.ALL)
    async def test_same_function_serves_all_three_domains_identically(self, domain):
        memory = MockMemory(search_results=[])
        record = await validation_gate(
            tier=LearningTier.ADAPTATION,
            content_domain=domain,
            subject_ref="subject-1",
            candidate_content="a domain-neutral candidate",
            trigger_signals=["reflection"],
            held_out_score=0.9, baseline_score=0.5,
            memory=memory, governance=GovernanceKernel(),
            event_stream=MockEventStream(),
        )
        assert record.lifecycle_state == LearningLifecycle.PROMOTED
        assert record.content_domain == domain
        assert record.gate_result.action_type == f"{domain}_adapt"
        assert memory.writes[0]["metadata"]["content_domain"] == domain

    def test_only_one_public_gate_function_is_exported(self):
        # There must be exactly one public callable that performs gating
        # -- not three parallel per-domain functions.
        public_callables = [
            name for name, value in vars(learning_module).items()
            if not name.startswith("_")
            and inspect.isfunction(value)
            and inspect.getmodule(value) is learning_module
        ]
        assert public_callables == ["validation_gate"]


# ─────────────────────────────────────────────────────────────────────────
# Architecture compliance — mirrors tests/core/cognitive/test_planner.py's
# AST-based approach (checks real code, not comments/docstrings/strings).
# ─────────────────────────────────────────────────────────────────────────

def _real_code_identifiers(source: str) -> set:
    """Return the set of identifier names that appear in *executable*
    positions in the given source (Name/Attribute/FunctionDef/ClassDef
    nodes) -- i.e. names Python would actually resolve at runtime, as
    opposed to occurrences inside string literals, comments, or
    docstrings. Mirrors tests/core/cognitive/test_planner.py's helper of
    the same name and purpose exactly; duplicated locally rather than
    imported cross-test-module (test_planner.py does not expose it via
    conftest.py, and this packet does not modify that file)."""
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        names.add(base.id)
    return names


class TestArchitectureCompliance:
    """Verifies architectural boundaries (K4.2 §8, §16 item 1; this
    packet's own "Explicitly forbidden" list): no new governor, no new
    memory layer, "never automatic" not silently weakened, and exactly
    the two named events are emitted."""

    def test_no_new_governor_class_defined(self):
        source = inspect.getsource(learning_module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = {
                    b.id for b in node.bases if isinstance(b, ast.Name)
                }
                assert "Governor" not in base_names, (
                    f"{node.name} subclasses Governor -- forbidden for "
                    f"this packet"
                )

    def test_no_new_memory_layer_introduced(self):
        source = inspect.getsource(learning_module)
        identifiers = _real_code_identifiers(source)
        # The L0-L4 layer model is fixed; this module must not introduce
        # a new layer constant or reassign the existing LAYERS registry.
        assert "LAYERS" not in identifiers
        assert not any(name in identifiers for name in ("L5", "l5"))

    def test_evolution_tier_always_passes_requires_approval_true_by_default(self):
        # Structural guard against silently weakening "never automatic":
        # requires_approval must be computed from `not hitl_approved`,
        # never hardcoded False and never a bare caller-supplied bool.
        source = inspect.getsource(learning_module)
        assert "requires_approval=not hitl_approved" in source

    def test_only_two_events_are_emitted(self):
        # K4.2.6's Scope names exactly two events; this module must not
        # emit a third.
        source = inspect.getsource(learning_module)
        assert source.count('event_stream.append(') == 2
        assert '"cognitive.pattern_learned"' in source
        assert '"cognitive.ontology_evolved"' in source

    def test_gate_function_is_parameterized_by_content_domain(self):
        sig = inspect.signature(validation_gate)
        assert "content_domain" in sig.parameters
        assert "tier" in sig.parameters
