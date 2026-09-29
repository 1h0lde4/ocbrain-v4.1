"""tests/core/cognitive/test_intent_sufficiency.py — ADR-KERNEL-07 (PROPOSED),
slice 1: the Intent Sufficiency gate.

Maps the study's acceptance tests (docs/studies/OCBRAIN_INTENT_SUFFICIENCY_
STUDY_SEPT2026.md §S) onto what slice 1 actually implements:

  Test A  under-specified request      -> TestAssessment / TestEvaluator / TestOrchestrator
  Test B  sufficiently specified       -> same
  Test C  delegated choice             -> same
  Test G  bounded, does not loop       -> TestGovernorRule / TestEvaluator
  Test D  already-known-from-context   -> NOT IMPLEMENTED (ADR-KERNEL-07 D-4);
                                          recorded below as an explicit xfail, not skipped
                                          silently.

Also verifies the isolation property the ADR depends on: the sufficiency rule
and ClarificationPolicy (incl. ADR-K4.2-H-13's general_purpose_only
exemption) cannot fire on, or swallow, each other.

Real OrchestrationGovernor / real GovernanceKernel throughout -- governance is
never mocked to APPROVE in the governance-facing tests.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.cognitive.intent import Goal
from core.cognitive.sufficiency import (
    MISSING_SUBJECT,
    SUFFICIENCY_ACTION_TYPE,
    SUFFICIENCY_SCORE_KEY,
    SufficiencyPolicy,
    SufficiencyStatus,
    assess_sufficiency,
    build_clarification_question,
    evaluate_intent_sufficiency,
)
from core.context import ContextMemory
from core.governance.governance_kernel import (
    GovernanceAction,
    GovernanceKernel,
    GovernanceResult,
    GovernanceVerdict,
    Governor,
)
from core.governance.orchestration_governor import OrchestrationGovernor
from core.memory.unified_memory import UnifiedMemory
from core.model_router import RouteResult
from core.orchestrator import Orchestrator


class MockEventStream:
    def __init__(self):
        self.events = []

    async def append(self, event_type, source, payload):
        self.events.append(
            {"event_type": event_type, "source": source, "payload": payload})


# ── Pure assessment ─────────────────────────────────────────────────────

class TestAssessment:
    @pytest.mark.parametrize("text", [
        "write a 1000 words story",              # the study's own example
        "write a story",
        "Write a short story.",
        "write me a poem",
        "please write a story for me",
        "can you write an essay?",
        "compose a 2000-word essay",
        "write a 500 word story",
        "tell me a joke",
        "write a really good story",
    ])
    def test_a_form_only_requests_are_underspecified(self, text):
        a = assess_sufficiency(text)
        assert a.in_scope and not a.delegated
        assert a.content_token_count == 0
        assert a.score == 0.0
        assert a.missing == (MISSING_SUBJECT,)

    @pytest.mark.parametrize("text", [
        "write a 1000-word noir detective short story, first person, ending on a twist",
        "write a poem about autumn",
        "write a story about a lonely lighthouse keeper",
        "compose an essay on the causes of the French Revolution",
        "write a bedtime story for my daughter Maya about a dragon",
    ])
    def test_b_well_specified_requests_are_sufficient(self, text):
        a = assess_sufficiency(text)
        assert a.in_scope
        # The property that matters: not below the policy threshold.
        assert a.score >= SufficiencyPolicy().score_threshold
        assert a.missing == ()

    @pytest.mark.parametrize("text", [
        "write a story, surprise me",
        "write a poem about anything you like",
        "write me a story, your choice",
        "write a story, up to you",
        "write a poem, use your judgment",
    ])
    def test_c_delegated_choice_is_sufficient_and_distinct_from_silence(self, text):
        delegated = assess_sufficiency(text)
        silent = assess_sufficiency("write a story")
        assert delegated.delegated and delegated.score == 1.0
        assert delegated.missing == ()
        assert not silent.delegated and silent.score == 0.0

    @pytest.mark.parametrize("text", [
        "write a python script that renames files",
        "write an email to my boss asking for Friday off",
        "what is the capital of France",
        "hi and hello",
        "book a flight to Tokyo next week",
        "summarize this article",
        "write a function to parse json",
        "",
    ])
    def test_out_of_scope_is_fail_open(self, text):
        a = assess_sufficiency(text)
        assert not a.in_scope
        assert a.score == 1.0
        assert a.missing == ()

    def test_none_input_is_safe(self):
        assert assess_sufficiency(None).in_scope is False  # type: ignore[arg-type]

    def test_single_content_token_sits_exactly_at_default_threshold(self):
        a = assess_sufficiency("write a funny story")
        assert a.content_token_count == 1
        assert a.score == 0.5  # == default threshold -> passes (documented fail-open)

    def test_length_specification_is_form_not_content(self):
        # Numbers, "words", "short/long" must never count as content.
        for text in ("write a 5000 word story", "write a long story",
                     "write a story of at least 300 words"):
            assert assess_sufficiency(text).content_token_count == 0, text

    def test_assessment_is_deterministic(self):
        t = "write a 1000 words story"
        assert assess_sufficiency(t) == assess_sufficiency(t)

    def test_question_is_specific_and_offers_a_way_out(self):
        q = build_clarification_question(assess_sufficiency("write a story"))
        assert "story" in q and "surprise me" in q and "about" in q
        assert build_clarification_question(
            assess_sufficiency("write a poem")).count("poem") >= 1


# ── Governor rule ───────────────────────────────────────────────────────

def _suff_action(score, **extra):
    md = {SUFFICIENCY_SCORE_KEY: score}
    md.update(extra)
    return GovernanceAction(action_type=SUFFICIENCY_ACTION_TYPE,
                            worker_id="t", metadata=md)


class TestGovernorRule:
    def test_below_threshold_escalates(self):
        r = OrchestrationGovernor().evaluate(_suff_action(0.0))
        assert r.verdict == GovernanceVerdict.ESCALATE
        assert r.governor == "OrchestrationGovernor"

    def test_at_threshold_is_not_escalated(self):
        r = OrchestrationGovernor().evaluate(_suff_action(0.5))
        assert r.verdict == GovernanceVerdict.APPROVE

    def test_absent_score_is_inert(self):
        r = OrchestrationGovernor().evaluate(
            GovernanceAction(action_type="anything", worker_id="t"))
        assert r.verdict == GovernanceVerdict.APPROVE

    def test_g_bounded_escalation_then_stalled(self):
        gov = OrchestrationGovernor()
        verdicts = [
            gov.evaluate(_suff_action(
                0.0, sufficiency_attempt=n, sufficiency_max_escalations=2)).verdict
            for n in (0, 1, 2, 3)
        ]
        assert verdicts == [
            GovernanceVerdict.ESCALATE, GovernanceVerdict.ESCALATE,
            GovernanceVerdict.REJECT, GovernanceVerdict.REJECT,
        ]

    def test_custom_threshold_is_honored(self):
        r = OrchestrationGovernor().evaluate(
            _suff_action(0.7, sufficiency_threshold=0.9))
        assert r.verdict == GovernanceVerdict.ESCALATE

    # Isolation from ClarificationPolicy / ADR-K4.2-H-13 ------------------

    def test_general_purpose_exemption_cannot_swallow_sufficiency(self):
        # general_purpose_only=True exempts *ClarificationPolicy*. It must
        # not exempt a sufficiency decision that carries the same flag.
        r = OrchestrationGovernor().evaluate(
            _suff_action(0.0, general_purpose_only=True))
        assert r.verdict == GovernanceVerdict.ESCALATE

    def test_sufficiency_key_never_triggers_clarification_rule(self):
        # No `confidence` key present -> ClarificationPolicy rule is inert;
        # only the sufficiency rule speaks, and only via its own key.
        gov = OrchestrationGovernor()
        assert gov._evaluate_clarification_policy(_suff_action(0.0)) is None

    def test_clarification_behavior_unchanged_by_sufficiency_rule(self):
        gov = OrchestrationGovernor()
        low_conf = GovernanceAction(
            action_type="plan_compile", worker_id="t",
            metadata={"confidence": 0.1, "general_purpose_only": False})
        exempt = GovernanceAction(
            action_type="plan_compile", worker_id="t",
            metadata={"confidence": 0.0, "general_purpose_only": True})
        assert gov.evaluate(low_conf).verdict == GovernanceVerdict.ESCALATE
        assert gov.evaluate(exempt).verdict == GovernanceVerdict.APPROVE
        # and the sufficiency rule stays inert for both
        assert gov._evaluate_sufficiency_policy(low_conf) is None
        assert gov._evaluate_sufficiency_policy(exempt) is None


# ── Governed evaluator (real GovernanceKernel) ──────────────────────────

class _DenyingGovernor(Governor):
    name = "SomeOtherGovernor"

    def evaluate(self, action):
        return GovernanceResult(verdict=GovernanceVerdict.REJECT,
                                reason="denied for unrelated reasons",
                                governor=self.name)


class TestEvaluator:
    @pytest.mark.asyncio
    async def test_a_underspecified_escalates_with_question_and_event(self):
        events = MockEventStream()
        res = await evaluate_intent_sufficiency(
            "write a 1000 words story", goal_id="g-1",
            event_stream=events, governance=GovernanceKernel())
        assert res.status == SufficiencyStatus.CLARIFICATION_REQUIRED
        assert res.question and "story" in res.question
        assert res.governance_result.verdict == GovernanceVerdict.ESCALATE

        assert [e["event_type"] for e in events.events] == [
            "cognitive.intent_sufficiency_evaluated"]
        p = events.events[0]["payload"]
        assert p["goal_id"] == "g-1" and p["verdict"] == "escalate"
        assert p["status"] == "clarification_required"
        assert p["missing"] == [MISSING_SUBJECT] and p["attempt"] == 0

    @pytest.mark.asyncio
    async def test_event_payload_never_carries_raw_request_text(self):
        events = MockEventStream()
        secret = "write a story SENTINEL-RAW-TEXT-4711"
        await evaluate_intent_sufficiency(
            secret, event_stream=events, governance=GovernanceKernel())
        assert "SENTINEL-RAW-TEXT-4711" not in repr(events.events)

    @pytest.mark.asyncio
    async def test_b_well_specified_is_sufficient_no_question(self):
        res = await evaluate_intent_sufficiency(
            "write a 1000-word noir detective short story, first person, "
            "ending on a twist",
            event_stream=MockEventStream(), governance=GovernanceKernel())
        assert res.status == SufficiencyStatus.SUFFICIENT
        assert res.question is None

    @pytest.mark.asyncio
    async def test_c_delegation_is_sufficient(self):
        res = await evaluate_intent_sufficiency(
            "write a story, surprise me",
            event_stream=MockEventStream(), governance=GovernanceKernel())
        assert res.status == SufficiencyStatus.SUFFICIENT

    @pytest.mark.asyncio
    async def test_out_of_scope_request_is_sufficient(self):
        res = await evaluate_intent_sufficiency(
            "book a flight to Tokyo next week",
            event_stream=MockEventStream(), governance=GovernanceKernel())
        assert res.status == SufficiencyStatus.SUFFICIENT
        assert res.assessment.in_scope is False

    @pytest.mark.asyncio
    async def test_g_stalled_at_the_bound(self):
        policy = SufficiencyPolicy(max_escalations=2)
        statuses = []
        for attempt in (0, 1, 2):
            r = await evaluate_intent_sufficiency(
                "write a story", policy=policy, attempt=attempt,
                event_stream=MockEventStream(), governance=GovernanceKernel())
            statuses.append(r.status)
        assert statuses == [SufficiencyStatus.CLARIFICATION_REQUIRED,
                            SufficiencyStatus.CLARIFICATION_REQUIRED,
                            SufficiencyStatus.STALLED]

    @pytest.mark.asyncio
    async def test_unrelated_governor_denial_is_not_reported_as_a_question(self):
        kernel = GovernanceKernel()
        kernel._governors.insert(0, _DenyingGovernor())
        res = await evaluate_intent_sufficiency(
            "write a story about a dragon",
            event_stream=MockEventStream(), governance=kernel)
        assert res.status == SufficiencyStatus.GOVERNANCE_BLOCKED
        assert res.question is None

    @pytest.mark.asyncio
    async def test_evaluation_goes_through_governance(self):
        kernel = MagicMock()
        kernel.evaluate_action = MagicMock(return_value=GovernanceResult())
        await evaluate_intent_sufficiency(
            "write a story", event_stream=MockEventStream(), governance=kernel)
        assert kernel.evaluate_action.call_count == 1
        action = kernel.evaluate_action.call_args.args[0]
        assert action.action_type == SUFFICIENCY_ACTION_TYPE
        assert "confidence" not in action.metadata  # key isolation at the source


# ── Orchestrator integration ────────────────────────────────────────────

def _goal(rid="g1"):
    return Goal(resource_id=rid, structured_form={"description": "t", "raw_request": "t"})


def _orch(enabled, governance=None):
    memory = AsyncMock(spec=UnifiedMemory)
    context = MagicMock(spec=ContextMemory)
    router = MagicMock()
    router.route = AsyncMock(return_value=RouteResult(answer="unused", source="mock"))
    return Orchestrator(
        modules={}, context=context, router=router, memory=memory,
        governance=governance or GovernanceKernel(),   # REAL kernel
        event_stream=AsyncMock(),
        execution_runtime=AsyncMock(), workflow_runtime=MagicMock(),
        capability_registry=MagicMock(),
        use_k42_frontend=True, intent_sufficiency_enabled=enabled,
    )


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_a_flag_on_underspecified_request_is_stopped_before_planning(self):
        orch = _orch(True)
        plan_mock, compile_mock = AsyncMock(), AsyncMock()
        with patch("core.cognitive.intent.interpret_request",
                   new=AsyncMock(return_value=[_goal()])), \
             patch("core.cognitive.planner.plan", new=plan_mock), \
             patch("core.cognitive.compiler.compile", new=compile_mock):
            answer = await orch.handle("write a 1000 words story")

        assert "story" in answer and "surprise me" in answer
        assert "wasn't able to prepare" not in answer   # not the generic apology
        plan_mock.assert_not_called()
        compile_mock.assert_not_called()
        orch._workflow_runtime.execute.assert_not_called()

        emitted = [c.kwargs.get("event_type") or c.args[0]
                   for c in orch._event_stream.append.call_args_list]
        assert "cognitive.intent_sufficiency_evaluated" in emitted
        assert "orchestrator.clarification_requested" in emitted

    @pytest.mark.asyncio
    async def test_flag_off_is_inert_even_for_underspecified_request(self):
        orch = _orch(False)
        gov = MagicMock()
        gov.evaluate_action = MagicMock(return_value=GovernanceResult())
        orch._governance = gov
        plan_mock = AsyncMock(side_effect=RuntimeError("reached plan()"))
        with patch("core.cognitive.intent.interpret_request",
                   new=AsyncMock(return_value=[_goal()])), \
             patch("core.cognitive.planner.plan", new=plan_mock):
            try:
                await orch.handle("write a 1000 words story")
            except Exception:
                pass
        # Flag off: pipeline proceeds to plan() exactly as before this ADR.
        assert plan_mock.call_count >= 1
        seen = {c.args[0].action_type for c in gov.evaluate_action.call_args_list}
        assert SUFFICIENCY_ACTION_TYPE not in seen

    @pytest.mark.asyncio
    async def test_b_flag_on_sufficient_request_proceeds_to_planning(self):
        orch = _orch(True)
        plan_mock = AsyncMock(side_effect=RuntimeError("reached plan()"))
        with patch("core.cognitive.intent.interpret_request",
                   new=AsyncMock(return_value=[_goal()])), \
             patch("core.cognitive.planner.plan", new=plan_mock):
            try:
                await orch.handle(
                    "write a 1000-word noir detective story, first person")
            except Exception:
                pass
        assert plan_mock.call_count >= 1

    @pytest.mark.asyncio
    async def test_flag_on_out_of_scope_request_proceeds_to_planning(self):
        orch = _orch(True)
        plan_mock = AsyncMock(side_effect=RuntimeError("reached plan()"))
        with patch("core.cognitive.intent.interpret_request",
                   new=AsyncMock(return_value=[_goal()])), \
             patch("core.cognitive.planner.plan", new=plan_mock):
            try:
                await orch.handle("book a flight to Tokyo next week")
            except Exception:
                pass
        assert plan_mock.call_count >= 1

    @pytest.mark.asyncio
    async def test_default_constructor_leaves_gate_off(self):
        orch = Orchestrator(
            modules={}, context=MagicMock(spec=ContextMemory),
            router=MagicMock(), memory=AsyncMock(spec=UnifiedMemory),
            governance=GovernanceKernel(), event_stream=AsyncMock())
        assert orch._intent_sufficiency_enabled is False


# ── Known gap, recorded rather than skipped ─────────────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="ADR-KERNEL-07 D-4: Test D (already-known-from-context) needs the "
           "hint channel wired into the sufficiency check; not in slice 1.")
def test_d_already_known_from_context_is_not_implemented():
    # A genre stated earlier in the conversation should make this sufficient.
    # Slice 1 is stateless and assesses the current request text only.
    a = assess_sufficiency("write a story")  # imagine: context said "noir"
    assert a.score >= 0.5
