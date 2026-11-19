"""tests/core/cognitive/test_creative_content_anchor.py -- ADR-KERNEL-07 (PROPOSED),
slice 1, D-5 resolved as Option C: creative content-anchor detector.

Architecture under test:
    interpret -> detect (pure, non-governing) -> plan -> compile()
      -> EXISTING OrchestrationGovernor at Plan Compilation -> ESCALATE
      -> clarification response (question + interpreted plan)

This is a NARROW experimental detector, not general intent sufficiency.
What these tests prove: detection of form-only creative requests; that the
detector observes but never governs (architecture test); that the result rides
the EXISTING compile() governance action under its own keys; ESCALATE at that
boundary with real compile()/GovernanceKernel/ExecutionPlan; H-13 exemption and
ClarificationPolicy isolation; the response pairs the interpreted plan with a
specific question; abstention is never "sufficient"; flag-off is inert. What
they do NOT prove: material sufficiency (TestKnownLimits pins the blind spots),
a multi-turn lifecycle (no attempt state; D-3), Test D (D-4, strict xfail).
"""
import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.cognitive.content_anchor as content_anchor_module
from core.cognitive.compiler import (
    CompilationResult,
    CompilationStatus,
    compile as compile_plan,
)
from core.cognitive.content_anchor import (
    CONTENT_ANCHOR_SCORE_KEY,
    CONTENT_ANCHOR_SCORE_THRESHOLD,
    CONTENT_ANCHOR_THRESHOLD_KEY,
    MISSING_SUBJECT,
    anchor_missing,
    build_clarification_question,
    build_clarification_response,
    detect_creative_content_anchors,
    governance_metadata,
    observe_creative_content_anchors,
)
from core.cognitive.intent import Goal
from core.cognitive.planner import (
    ExecutionPlan,
    PlanStep,
    PlannerResult,
    PlannerStatus,
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
        a = detect_creative_content_anchors(text)
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
        a = detect_creative_content_anchors(text)
        assert a.in_scope
        # The property that matters: not below the policy threshold.
        assert a.score >= CONTENT_ANCHOR_SCORE_THRESHOLD
        assert a.missing == ()

    @pytest.mark.parametrize("text", [
        "write a story, surprise me",
        "write a poem about anything you like",
        "write me a story, your choice",
        "write a story, up to you",
        "write a poem, use your judgment",
    ])
    def test_c_delegated_choice_is_sufficient_and_distinct_from_silence(self, text):
        delegated = detect_creative_content_anchors(text)
        silent = detect_creative_content_anchors("write a story")
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
    def test_out_of_scope_abstains_and_makes_no_judgment(self, text):
        a = detect_creative_content_anchors(text)
        assert not a.in_scope
        # None, not 1.0: abstention must never be representable as "sufficient".
        assert a.score is None
        assert a.missing == ()

    def test_none_input_is_safe(self):
        assert detect_creative_content_anchors(None).in_scope is False  # type: ignore[arg-type]

    def test_single_content_token_sits_exactly_at_default_threshold(self):
        a = detect_creative_content_anchors("write a funny story")
        assert a.content_token_count == 1
        assert a.score == 0.5  # == default threshold -> passes (documented fail-open)

    def test_length_specification_is_form_not_content(self):
        # Numbers, "words", "short/long" must never count as content.
        for text in ("write a 5000 word story", "write a long story",
                     "write a story of at least 300 words"):
            assert detect_creative_content_anchors(text).content_token_count == 0, text

    def test_assessment_is_deterministic(self):
        t = "write a 1000 words story"
        assert detect_creative_content_anchors(t) == detect_creative_content_anchors(t)

    def test_question_is_specific_and_offers_a_way_out(self):
        q = build_clarification_question(detect_creative_content_anchors("write a story"))
        assert "story" in q and "surprise me" in q and "about" in q
        assert build_clarification_question(
            detect_creative_content_anchors("write a poem")).count("poem") >= 1


# ── Known limits (executable; the detector's blind spots, pinned) ────────

class TestKnownLimits:
    """These pass BECAUSE the detector is weak. They document what it does not
    detect so nobody mistakes it for general intent sufficiency. If a stronger
    signal replaces it, these are expected to change -- deliberately."""

    @pytest.mark.parametrize("text", [
        "Write a 1000-word science-fiction story.",   # premise/tone/audience open
        "write a story about a dragon",               # still hugely open
        "write a funny story",                        # one token: at threshold
    ])
    def test_materially_underspecified_requests_still_pass(self, text):
        a = detect_creative_content_anchors(text)
        assert a.in_scope and a.score >= CONTENT_ANCHOR_SCORE_THRESHOLD
        assert a.missing == ()

    def test_detector_reads_request_text_only(self):
        # No Intent/Goal/hypothesis input exists on the detector's surface.
        import inspect
        params = list(inspect.signature(detect_creative_content_anchors).parameters)
        assert params == ["raw_text"]

    def test_scope_is_creative_composition_only(self):
        # Under-specified but outside the lexicon -> fail-open, by design.
        for text in ("write a report", "make me a logo", "plan my trip",
                     "write me a letter", "create a presentation"):
            assert not detect_creative_content_anchors(text).in_scope, text


# ── Governor rule ───────────────────────────────────────────────────────

def _suff_action(score, **extra):
    md = {CONTENT_ANCHOR_SCORE_KEY: score}
    md.update(extra)
    return GovernanceAction(action_type="plan_compile",
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

    def test_no_attempt_bound_exists_in_slice_1(self):
        # Deliberate: attempt keys are ignored. A bound needs a real attempt
        # carrier (D-3); until then it would be unreachable governance logic.
        r = OrchestrationGovernor().evaluate(_suff_action(
            0.0, sufficiency_attempt=99, sufficiency_max_escalations=1,
            content_anchor_attempt=99, content_anchor_max_escalations=1))
        assert r.verdict == GovernanceVerdict.ESCALATE

    def test_custom_threshold_is_honored(self):
        r = OrchestrationGovernor().evaluate(
            _suff_action(0.7, content_anchor_threshold=0.9))
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
        assert gov._evaluate_content_anchor_policy(low_conf) is None
        assert gov._evaluate_content_anchor_policy(exempt) is None


# ── Non-governing observation + carrier helpers ────────────────────────

class TestObservation:
    @pytest.mark.asyncio
    async def test_observe_records_and_returns_without_deciding(self):
        events = MockEventStream()
        a = await observe_creative_content_anchors(
            "write a 1000 words story", goal_id="g-1", event_stream=events)
        assert a.missing == (MISSING_SUBJECT,) and a.score == 0.0
        assert [e["event_type"] for e in events.events] == [
            "cognitive.content_anchor_observed"]
        p = events.events[0]["payload"]
        assert p["goal_id"] == "g-1" and p["abstained"] is False
        assert p["detector"] == "creative_content_anchor"
        assert p["detector_version"] == "0" and p["score"] == 0.0

    @pytest.mark.asyncio
    async def test_abstention_is_recorded_as_abstained_not_sufficient(self):
        events = MockEventStream()
        a = await observe_creative_content_anchors(
            "book a flight to Tokyo next week", event_stream=events)
        assert a.score is None and not a.in_scope
        p = events.events[0]["payload"]
        assert p["abstained"] is True and p["score"] is None

    @pytest.mark.asyncio
    async def test_event_never_carries_raw_request_text(self):
        events = MockEventStream()
        await observe_creative_content_anchors(
            "write a story SENTINEL-RAW-TEXT-4711", event_stream=events)
        assert "SENTINEL-RAW-TEXT-4711" not in repr(events.events)

    def test_module_observes_but_never_governs(self):
        # Architecture test: the detector module must not import governance
        # or call evaluate_action. It contributes an observation, nothing more.
        src = Path(content_anchor_module.__file__).read_text()
        tree = ast.parse(src)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported += [al.name for al in node.names]
            elif isinstance(node, ast.Import):
                imported += [al.name for al in node.names]
        assert not [m for m in imported if "governance" in m.lower()], imported
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "GovernanceAction" not in names
        assert "evaluate_action" not in attrs

    def test_governance_metadata_only_for_in_scope_assessments(self):
        assert governance_metadata(None) == {}
        assert governance_metadata(
            detect_creative_content_anchors("book a flight")) == {}   # abstained
        md = governance_metadata(detect_creative_content_anchors("write a story"))
        assert md == {CONTENT_ANCHOR_SCORE_KEY: 0.0,
                      CONTENT_ANCHOR_THRESHOLD_KEY: CONTENT_ANCHOR_SCORE_THRESHOLD}
        assert "confidence" not in md          # key isolation at the source

    def test_anchor_missing_predicate(self):
        d = detect_creative_content_anchors
        assert anchor_missing(d("write a story")) is True
        assert anchor_missing(d("write a poem about autumn")) is False
        assert anchor_missing(d("write a story, surprise me")) is False
        assert anchor_missing(d("book a flight")) is False   # abstained != missing
        assert anchor_missing(None) is False


class TestClarificationResponse:
    def test_pairs_interpretation_and_plan_with_a_specific_question(self):
        a = detect_creative_content_anchors("write a 1000 words story")
        r = build_clarification_response(
            a, interpretation="Write a story of about 1000 words",
            plan_steps=["Draft the story", "Polish the draft"])
        assert "Here's how I read your request: Write a story" in r
        assert "1. Draft the story; 2. Polish the draft" in r
        assert r.rstrip().endswith("with those details.")
        assert "surprise me" in r and "story" in r

    def test_degrades_to_the_bare_question_without_context(self):
        a = detect_creative_content_anchors("write a poem")
        assert build_clarification_response(a) == build_clarification_question(a)

    def test_model_text_is_flattened_truncated_and_capped(self):
        a = detect_creative_content_anchors("write a story")
        r = build_clarification_response(
            a, interpretation="line1\nline2 " + "x" * 500,
            plan_steps=[f"step {i}" for i in range(9)])
        head = r.split("\n\n")[0]
        assert "\n" not in head and len(head) < 260
        assert "(+4 more)" in r and "6. step 5" not in r


# ── Real compile() + real GovernanceKernel (Plan Compilation boundary) ──

def _plan(confidence=0.9, general_purpose_only=False):
    return ExecutionPlan(
        goal_id="g1",
        steps=[PlanStep(step_id="s1", description="Write the story",
                        capability_type="llm_completion")],
        confidence=confidence, derived_from=["g1"],
        general_purpose_only=general_purpose_only)


class _StubGovernor(Governor):
    def __init__(self, name, verdict, only_for=None):
        self.name, self._v, self._only = name, verdict, only_for

    def evaluate(self, action):
        if self._only is not None and action.action_type != self._only:
            return GovernanceResult()                      # APPROVE, not its concern
        return GovernanceResult(verdict=self._v, reason="stub", governor=self.name)


class TestCompileBoundary:
    """D-5 = Option C: the EXISTING gate evaluates the carried observation."""

    @pytest.mark.asyncio
    async def test_a_form_only_request_escalates_at_plan_compilation(self):
        events = MockEventStream()
        r = await compile_plan(
            _plan(), event_stream=events, governance=GovernanceKernel(),
            content_anchor=detect_creative_content_anchors(
                "write a 1000 words story"))
        assert r.status == CompilationStatus.ESCALATED
        assert r.workflow_definition is None
        assert r.governance_result.governor == "OrchestrationGovernor"
        assert "Content-anchor" in r.governance_result.reason
        p = [e for e in events.events
             if e["event_type"] == "cognitive.plan_rejected"][0]["payload"]
        assert p["verdict"] == "escalate" and p["content_anchor_score"] == 0.0

    @pytest.mark.asyncio
    async def test_h13_exemption_does_not_swallow_the_content_anchor_rule(self):
        # general_purpose_only=True exempts ClarificationPolicy even at
        # confidence 0.0 -- proven here by the no-anchor baseline compiling.
        gp = _plan(confidence=0.0, general_purpose_only=True)
        base = await compile_plan(gp, event_stream=MockEventStream(),
                                  governance=GovernanceKernel())
        assert base.status == CompilationStatus.COMPILED      # exemption active
        r = await compile_plan(
            gp, event_stream=MockEventStream(), governance=GovernanceKernel(),
            content_anchor=detect_creative_content_anchors("write a story"))
        assert r.status == CompilationStatus.ESCALATED        # anchor still fires

    @pytest.mark.asyncio
    async def test_b_anchored_request_compiles(self):
        r = await compile_plan(
            _plan(), event_stream=MockEventStream(), governance=GovernanceKernel(),
            content_anchor=detect_creative_content_anchors(
                "write a poem about autumn"))
        assert r.status == CompilationStatus.COMPILED
        assert r.workflow_definition is not None

    @pytest.mark.asyncio
    async def test_c_delegated_request_compiles(self):
        r = await compile_plan(
            _plan(), event_stream=MockEventStream(), governance=GovernanceKernel(),
            content_anchor=detect_creative_content_anchors(
                "write a story, surprise me"))
        assert r.status == CompilationStatus.COMPILED

    @pytest.mark.asyncio
    async def test_abstained_observation_adds_nothing_to_the_action(self):
        kernel = MagicMock()
        kernel.evaluate_action = MagicMock(return_value=GovernanceResult())
        await compile_plan(
            _plan(), event_stream=MockEventStream(), governance=kernel,
            content_anchor=detect_creative_content_anchors("book a flight"))
        md = kernel.evaluate_action.call_args.args[0].metadata
        assert CONTENT_ANCHOR_SCORE_KEY not in md
        assert CONTENT_ANCHOR_THRESHOLD_KEY not in md

    @pytest.mark.asyncio
    async def test_default_none_is_byte_identical_metadata(self):
        kernel = MagicMock()
        kernel.evaluate_action = MagicMock(return_value=GovernanceResult())
        await compile_plan(_plan(), event_stream=MockEventStream(),
                           governance=kernel)
        action = kernel.evaluate_action.call_args.args[0]
        assert action.action_type == "plan_compile"      # NOT a new action type
        assert not [k for k in action.metadata if k.startswith("content_anchor")]

    @pytest.mark.asyncio
    async def test_same_existing_action_carries_both_key_families(self):
        kernel = MagicMock()
        kernel.evaluate_action = MagicMock(return_value=GovernanceResult())
        await compile_plan(
            _plan(confidence=0.7), event_stream=MockEventStream(),
            governance=kernel,
            content_anchor=detect_creative_content_anchors("write a story"))
        assert kernel.evaluate_action.call_count == 1     # one boundary, one call
        md = kernel.evaluate_action.call_args.args[0].metadata
        assert md["confidence"] == 0.7 and md[CONTENT_ANCHOR_SCORE_KEY] == 0.0

    @pytest.mark.asyncio
    async def test_clarification_policy_still_operates_alongside(self):
        # Anchor present, plan confidence low, NOT general-purpose-only ->
        # ClarificationPolicy escalates exactly as before; the anchor rule
        # stays out of it.
        r = await compile_plan(
            _plan(confidence=0.1), event_stream=MockEventStream(),
            governance=GovernanceKernel(),
            content_anchor=detect_creative_content_anchors(
                "write a poem about autumn"))
        assert r.status == CompilationStatus.ESCALATED
        assert "Content-anchor" not in r.governance_result.reason

    @pytest.mark.asyncio
    async def test_anchor_rule_is_evaluated_before_clarification_policy(self):
        r = await compile_plan(
            _plan(confidence=0.1), event_stream=MockEventStream(),
            governance=GovernanceKernel(),
            content_anchor=detect_creative_content_anchors("write a story"))
        assert r.status == CompilationStatus.ESCALATED
        assert "Content-anchor" in r.governance_result.reason

    @pytest.mark.asyncio
    async def test_another_governors_rejection_is_not_an_escalation(self):
        kernel = GovernanceKernel()
        kernel._governors.insert(0, _StubGovernor("Other", GovernanceVerdict.REJECT))
        r = await compile_plan(
            _plan(), event_stream=MockEventStream(), governance=kernel,
            content_anchor=detect_creative_content_anchors("write a story"))
        assert r.status == CompilationStatus.REJECTED

    def test_compile_argument_is_additive_keyword_only_default_none(self):
        prm = inspect.signature(compile_plan).parameters["content_anchor"]
        assert prm.default is None and prm.kind is inspect.Parameter.KEYWORD_ONLY


# ── Orchestrator integration (real compile + real governance) ───────────

def _goal(rid="g1"):
    return Goal(resource_id=rid, structured_form={
        "description": "Write a story of about 1000 words",
        "raw_request": "t"})


def _ready(plan):
    return PlannerResult(status=PlannerStatus.READY_FOR_COMPILATION,
                         execution_plan=plan, operation_id="op-1")


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
        use_k42_frontend=True, creative_content_anchor_enabled=enabled,
    )


def _emitted(orch):
    return [c.kwargs.get("event_type") or c.args[0]
            for c in orch._event_stream.append.call_args_list]


async def _run(orch, text, plan):
    with patch("core.cognitive.intent.interpret_request",
               new=AsyncMock(return_value=[_goal()])), \
         patch("core.cognitive.planner.plan",
               new=AsyncMock(return_value=_ready(plan))):
        try:
            return await orch.handle(text)
        except Exception as exc:                 # downstream of compile only
            return exc


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_a_form_only_request_is_answered_with_question_and_plan(self):
        orch = _orch(True)
        answer = await _run(orch, "write a 1000 words story", _plan())
        assert isinstance(answer, str)
        assert "Here's how I read your request: Write a story of about 1000" in answer
        assert "1. Write the story" in answer               # the interpreted plan
        assert "surprise me" in answer                       # the question
        assert "wasn't able to prepare" not in answer
        orch._workflow_runtime.execute.assert_not_called()   # no generation
        orch._execution_runtime.invoke.assert_awaited()      # Supervisor still surfaced
        ev = _emitted(orch)
        assert "cognitive.content_anchor_observed" in ev
        assert "cognitive.plan_rejected" in ev               # existing gate spoke
        assert "orchestrator.clarification_requested" in ev
        assert "orchestrator.query_failed" not in ev

    @pytest.mark.asyncio
    async def test_feature_adds_no_governance_evaluation_of_its_own(self):
        # The Option-C property. handle() already evaluates a request-
        # authorization action at entry (pre-existing, PI LAW 1) and the
        # compile gate evaluates plan_compile. Turning the feature on must add
        # NO governance evaluation anywhere: same actions, same order, and the
        # only post-plan one is the existing plan_compile.
        async def record(flag):
            order = []
            kernel = MagicMock()
            kernel.evaluate_action = MagicMock(
                side_effect=lambda a: order.append(("gov", a.action_type))
                or GovernanceResult())
            orch = _orch(flag, governance=kernel)
            plan_mock = AsyncMock(side_effect=lambda *a, **k:
                                  order.append(("plan", None)) or _ready(_plan()))
            with patch("core.cognitive.intent.interpret_request",
                       new=AsyncMock(return_value=[_goal()])), \
                 patch("core.cognitive.planner.plan", new=plan_mock):
                try:
                    await orch.handle("write a 1000 words story")
                except Exception:
                    pass
            return order

        off, on = await record(False), await record(True)
        assert on == off                                  # nothing added, nothing moved
        gov_types = [t for k, t in on if k == "gov"]
        assert gov_types.count("plan_compile") == 1
        post_plan = [t for k, t in on[[k for k, _ in on].index("plan"):] if k == "gov"]
        assert post_plan == ["plan_compile"]              # only the existing gate
        assert not [t for t in gov_types
                    if "anchor" in str(t).lower() or "clarif" in str(t).lower()]

    @pytest.mark.asyncio
    async def test_b_anchored_request_proceeds_to_execution(self):
        orch = _orch(True)
        await _run(orch, "write a poem about autumn", _plan())
        orch._workflow_runtime.execute.assert_called()
        assert "orchestrator.clarification_requested" not in _emitted(orch)

    @pytest.mark.asyncio
    async def test_out_of_scope_request_abstains_and_proceeds(self):
        orch = _orch(True)
        await _run(orch, "book a flight to Tokyo next week", _plan())
        orch._workflow_runtime.execute.assert_called()
        obs = [c.kwargs["payload"] for c in orch._event_stream.append.call_args_list
               if c.kwargs.get("event_type") == "cognitive.content_anchor_observed"]
        assert obs and obs[0]["abstained"] is True and obs[0]["score"] is None
        assert "orchestrator.clarification_requested" not in _emitted(orch)

    @pytest.mark.asyncio
    async def test_flag_off_is_inert_and_compile_call_is_unchanged(self):
        orch = _orch(False)
        compile_mock = AsyncMock(return_value=CompilationResult(
            status=CompilationStatus.COMPILED, workflow_definition=MagicMock()))
        with patch("core.cognitive.intent.interpret_request",
                   new=AsyncMock(return_value=[_goal()])), \
             patch("core.cognitive.planner.plan",
                   new=AsyncMock(return_value=_ready(_plan()))), \
             patch("core.cognitive.compiler.compile", new=compile_mock):
            try:
                await orch.handle("write a 1000 words story")
            except Exception:
                pass
        compile_mock.assert_awaited_once()
        assert "content_anchor" not in compile_mock.call_args.kwargs
        assert "cognitive.content_anchor_observed" not in _emitted(orch)

    @pytest.mark.asyncio
    async def test_flag_on_passes_the_observation_to_compile(self):
        orch = _orch(True)
        compile_mock = AsyncMock(return_value=CompilationResult(
            status=CompilationStatus.COMPILED, workflow_definition=MagicMock()))
        with patch("core.cognitive.intent.interpret_request",
                   new=AsyncMock(return_value=[_goal()])), \
             patch("core.cognitive.planner.plan",
                   new=AsyncMock(return_value=_ready(_plan()))), \
             patch("core.cognitive.compiler.compile", new=compile_mock):
            try:
                await orch.handle("write a 1000 words story")
            except Exception:
                pass
        assert compile_mock.call_args.kwargs["content_anchor"].missing == (
            MISSING_SUBJECT,)

    @pytest.mark.asyncio
    async def test_escalation_from_another_governor_keeps_the_generic_path(self):
        kernel = GovernanceKernel()
        # Scoped to plan_compile: handle() ALSO evaluates a request-authorization
        # action at entry (ORCHESTRATOR_ACTION_TYPE), which must pass untouched.
        kernel._governors.insert(0, _StubGovernor(
            "SomeOtherGovernor", GovernanceVerdict.ESCALATE, only_for="plan_compile"))
        orch = _orch(True, governance=kernel)
        answer = await _run(orch, "write a 1000 words story", _plan())
        assert isinstance(answer, str) and "wasn't able to prepare" in answer
        assert "surprise me" not in answer
        assert "orchestrator.clarification_requested" not in _emitted(orch)
        assert "orchestrator.query_failed" in _emitted(orch)

    @pytest.mark.asyncio
    async def test_clarification_policy_escalation_is_unchanged(self):
        # Anchored request, low-confidence plan: ClarificationPolicy escalates;
        # the user still gets the pre-existing generic message.
        orch = _orch(True)
        answer = await _run(orch, "write a poem about autumn",
                            _plan(confidence=0.1))
        assert isinstance(answer, str) and "wasn't able to prepare" in answer
        assert "orchestrator.clarification_requested" not in _emitted(orch)

    @pytest.mark.asyncio
    async def test_default_constructor_leaves_the_feature_off(self):
        orch = Orchestrator(
            modules={}, context=MagicMock(spec=ContextMemory),
            router=MagicMock(), memory=AsyncMock(spec=UnifiedMemory),
            governance=GovernanceKernel(), event_stream=AsyncMock())
        assert orch._creative_content_anchor_enabled is False


# ── Known gap, recorded rather than skipped ─────────────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="ADR-KERNEL-07 D-4: Test D (already-known-from-context) needs the "
           "hint channel wired into the detector; not in slice 1.")
def test_d_already_known_from_context_is_not_implemented():
    # A genre stated earlier in the conversation should make this sufficient.
    # Slice 1 is stateless and assesses the current request text only.
    a = detect_creative_content_anchors("write a story")  # imagine: context said "noir"
    assert a.score >= 0.5
