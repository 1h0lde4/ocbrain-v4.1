"""tests/core/cognitive/test_debt043_clarification_response.py -- DEBT-043.

Truthful, bounded content-anchor clarification response (ADR-KERNEL-07 slice 1,
response-path disposition C-plus; owner directive of 2026-10-19, section 5).

Scope. Pins the RESPONSE CONTRACT only:
  * at most three GENUINE planner steps, in order, on separate numbered lines,
    labelled provisional -- never padded, never fabricated, never mutated;
  * a truthful intent statement derived from detector data -- the raw request is
    never echoed back as if it were an independent interpretation;
  * an artifact-appropriate, neutral question;
  * when the K4.2 pairing (intent + a genuine plan step) cannot be produced, the
    stable generic safe-failure text and a ``query_failed`` event -- never an
    unpaired detector-specific question, never the old defective response.

What these tests do NOT prove: that a planner-generated step is semantically
appropriate (the residual product risk of C-plus: a displayed step can still be
generic or presuppose an unrequested process), that users benefit from seeing
the plan, or anything about ADR acceptance.  A passing rendering test is not
evidence that the proposed plan is good.

The integration tests drive the REAL ``Orchestrator.handle()`` with the REAL
``compile()`` and ``GovernanceKernel``; only the model-dependent stages
(``interpret_request`` and ``planner.plan``) are replaced by controlled doubles.
No live model or provider is needed.
"""
import ast
import dataclasses
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.cognitive.content_anchor as ca
from core.cognitive.content_anchor import (
    SAFE_FAILURE_MESSAGE,
    build_clarification_intent,
    build_clarification_question,
    build_clarification_response,
    detect_creative_content_anchors,
    genuine_plan_steps,
    render_clarification_response,
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
    GovernanceKernel,
    GovernanceResult,
    GovernanceVerdict,
    Governor,
)
from core.memory.unified_memory import UnifiedMemory
from core.model_router import RouteResult
from core.orchestrator import Orchestrator

REQ = "write a 1000 words story"
DESC = "Write a story of about 1000 words"          # K4.2-H1: description == the request
OLD_ECHO = "Here's how I read your request"


# ── helpers ─────────────────────────────────────────────────────────────

def _assessment(text=REQ):
    return detect_creative_content_anchors(text)


def _steps(*descriptions):
    return [PlanStep(step_id=f"s{i}", description=d, capability_type="llm_completion")
            for i, d in enumerate(descriptions, 1)]


def _plan(steps, confidence=0.9):
    return ExecutionPlan(goal_id="g1", steps=steps, confidence=confidence,
                         derived_from=["g1"], general_purpose_only=False)


def _goal(description=DESC):
    return Goal(resource_id="g1", structured_form={
        "description": description, "raw_request": description})


def _ready(plan):
    return PlannerResult(status=PlannerStatus.READY_FOR_COMPILATION,
                         execution_plan=plan, operation_id="op-1")


def _orch(enabled=True, governance=None):
    router = MagicMock()
    router.route = AsyncMock(return_value=RouteResult(answer="unused", source="mock"))
    return Orchestrator(
        modules={}, context=MagicMock(spec=ContextMemory),
        router=router, memory=AsyncMock(spec=UnifiedMemory),
        governance=governance or GovernanceKernel(),       # REAL kernel
        event_stream=AsyncMock(),
        execution_runtime=AsyncMock(), workflow_runtime=MagicMock(),
        capability_registry=MagicMock(),
        use_k42_frontend=True, creative_content_anchor_enabled=enabled,
    )


def _events(orch):
    """[(event_type, payload)] in emission order."""
    out = []
    for c in orch._event_stream.append.call_args_list:
        out.append((c.kwargs.get("event_type") or c.args[0],
                    c.kwargs.get("payload") or {}))
    return out


def _types(orch):
    return [t for t, _ in _events(orch)]


def _payload(orch, event_type):
    return [p for t, p in _events(orch) if t == event_type]


async def _handle(orch, plan, *, description=DESC, request=REQ):
    with patch("core.cognitive.intent.interpret_request",
               new=AsyncMock(return_value=[_goal(description)])), \
         patch("core.cognitive.planner.plan",
               new=AsyncMock(return_value=_ready(plan))):
        try:
            return await orch.handle(request)
        except Exception as exc:                          # downstream of compile only
            return exc


def _numbered_lines(text):
    return [ln for ln in text.split("\n") if re.match(r"\d+\. ", ln)]


class _StubGovernor(Governor):
    def __init__(self, name, verdict, only_for=None):
        self.name, self._v, self._only = name, verdict, only_for

    def evaluate(self, action):
        if self._only is not None and action.action_type != self._only:
            return GovernanceResult()
        return GovernanceResult(verdict=self._v, reason="stub", governor=self.name)


# ── 1. more than three steps: only the first three genuine steps, in order ──

class TestStepCap:
    def test_the_cap_is_three(self):
        assert ca._MAX_STEPS_SHOWN == 3

    def test_only_the_first_three_genuine_steps_appear_in_order(self):
        steps = [f"Step number {i}" for i in range(1, 8)]
        r = render_clarification_response(_assessment(), request_text=DESC, plan_steps=steps)
        assert r.paired and (r.steps_shown, r.steps_total) == (3, 7)
        assert _numbered_lines(r.text) == [
            "1. Step number 1", "2. Step number 2", "3. Step number 3"]
        assert "Step number 4" not in r.text
        assert "first 3 of 7 steps" in r.text           # omission is stated, not hidden

    def test_the_cap_applies_to_genuine_steps_not_to_raw_entries(self):
        # junk entries ahead of the real steps must not use up the three slots
        steps = [None, "", "  ", "Alpha", 12, "Beta", "Gamma", "Delta"]
        r = render_clarification_response(_assessment(), request_text=DESC, plan_steps=steps)
        assert _numbered_lines(r.text) == ["1. Alpha", "2. Beta", "3. Gamma"]
        assert (r.steps_shown, r.steps_total) == (3, 4)

    @pytest.mark.asyncio
    async def test_real_path_more_than_three_steps(self):
        orch = _orch()
        plan = _plan(_steps(*[f"Plan step {i}" for i in range(1, 7)]))
        answer = await _handle(orch, plan)
        assert isinstance(answer, str)
        assert _numbered_lines(answer) == [
            "1. Plan step 1", "2. Plan step 2", "3. Plan step 3"]
        assert "Plan step 4" not in answer
        # the EXECUTION plan is untouched: the cap is presentation only
        assert [s.description for s in plan.steps] == [f"Plan step {i}" for i in range(1, 7)]
        p = _payload(orch, "orchestrator.clarification_requested")[0]
        assert (p["plan_steps_shown"], p["plan_steps_total"]) == (3, 6)


# ── 2. one, two and three steps: no padding, no fabrication ─────────────

class TestShortPlans:
    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_no_padding(self, n):
        steps = [f"Real step {i}" for i in range(1, n + 1)]
        r = render_clarification_response(_assessment(), request_text=DESC, plan_steps=steps)
        assert r.paired and (r.steps_shown, r.steps_total) == (n, n)
        assert _numbered_lines(r.text) == [f"{i}. Real step {i}" for i in range(1, n + 1)]
        assert "more steps" not in r.text and "first " not in r.text   # nothing was omitted

    @pytest.mark.asyncio
    @pytest.mark.parametrize("n", [1, 2, 3])
    async def test_real_path_short_plans(self, n):
        orch = _orch()
        descs = [f"Real step {i}" for i in range(1, n + 1)]
        answer = await _handle(orch, _plan(_steps(*descs)))
        assert _numbered_lines(answer) == [f"{i}. {d}" for i, d in enumerate(descs, 1)]
        assert "Provisional draft plan" in answer


# ── provisional labelling and honesty about what the plan is ────────────

class TestProvisionalLabel:
    def test_plan_is_labelled_provisional_and_unverified(self):
        text = build_clarification_response(
            _assessment(), request_text=DESC, plan_steps=["Draft", "Revise"])
        assert "Provisional draft plan" in text
        assert "not checked or approved" in text
        for claim in ("verified", "validated", "approved by you", "confirmed"):
            assert claim not in text.replace("not checked or approved", "")

    def test_generic_steps_are_not_presented_as_establishing_a_subject(self):
        text = build_clarification_response(
            _assessment(), request_text=DESC, plan_steps=["Draft", "Revise"])
        assert "not yet tailored to a subject" in text

    def test_the_question_promises_no_quality_or_result(self):
        for kind in set(ca._ARTIFACTS.values()):
            q = build_clarification_question(_assessment(f"write a {kind}"))
            for promise in ("best", "perfect", "guarantee", "will be great", "amazing"):
                assert promise not in q.lower()


# ── 3. empty plan and missing plan ──────────────────────────────────────

class TestEmptyAndMissingPlan:
    @pytest.mark.parametrize("steps", [(), [], None])
    def test_renderer_safe_failure_without_a_detector_question(self, steps):
        r = render_clarification_response(_assessment(), request_text=DESC, plan_steps=steps)
        assert not r.paired and r.text == SAFE_FAILURE_MESSAGE
        assert r.failure_reason == ca.FAILURE_NO_USABLE_PLAN
        assert "surprise me" not in r.text and "about" not in r.text.lower()
        assert (r.steps_shown, r.steps_total) == (0, 0)

    @pytest.mark.asyncio
    async def test_real_path_empty_plan_yields_no_detector_question(self):
        orch = _orch()
        answer = await _handle(orch, _plan([]))
        assert isinstance(answer, str)
        assert "surprise me" not in answer and OLD_ECHO not in answer
        assert "orchestrator.clarification_requested" not in _types(orch)
        orch._workflow_runtime.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_path_missing_plan_yields_no_detector_question(self):
        # A missing plan fails inside compile() on the pre-existing error path
        # (not changed here); the property pinned is: no unpaired question.
        orch = _orch()
        answer = await _handle(orch, None)
        assert isinstance(answer, str)
        assert "surprise me" not in answer and "should the story be about" not in answer
        assert "orchestrator.clarification_requested" not in _types(orch)
        orch._workflow_runtime.execute.assert_not_called()


# ── 4. malformed or unusable step data ──────────────────────────────────

class TestMalformedSteps:
    @pytest.mark.parametrize("steps", [
        [None], [""], ["   "], [12], [{"x": 1}], [["a"]], [None, 7, "", " \n\t "],
        ["1."], ["2)"], ["-"], ["- -"], ["1. 2."], ["\u2022"],
    ])
    def test_unusable_step_data_is_a_safe_failure(self, steps):
        r = render_clarification_response(_assessment(), request_text=DESC, plan_steps=steps)
        assert not r.paired and r.text == SAFE_FAILURE_MESSAGE
        assert "surprise me" not in r.text

    def test_a_usable_step_among_junk_is_kept_and_nothing_else(self):
        r = render_clarification_response(
            _assessment(), request_text=DESC,
            plan_steps=[None, 5, "Write the opening scene", {"d": 1}, ""])
        assert r.paired and _numbered_lines(r.text) == ["1. Write the opening scene"]
        assert (r.steps_shown, r.steps_total) == (1, 1)

    @pytest.mark.asyncio
    async def test_real_path_none_description_is_a_safe_failure(self):
        plan = _plan(_steps("Write the story"))
        plan.steps[0].description = None                   # malformed planner output
        orch = _orch()
        answer = await _handle(orch, plan)
        assert answer == SAFE_FAILURE_MESSAGE
        assert "orchestrator.clarification_requested" not in _types(orch)
        orch._workflow_runtime.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_path_step_without_a_description_yields_no_detector_question(self):
        # Such a step is rejected by compile()'s pre-existing structural handling
        # before the response is rendered; the property pinned is that nothing
        # unhandled escapes and no unpaired question is produced.
        plan = _plan(_steps("Write the story"))
        plan.steps = [object()]                            # no .description at all
        orch = _orch()
        answer = await _handle(orch, plan)
        assert isinstance(answer, str)                     # handle() returned, did not raise
        assert "surprise me" not in answer and "should the story be about" not in answer
        assert "orchestrator.clarification_requested" not in _types(orch)
        orch._workflow_runtime.execute.assert_not_called()


# ── 5. absent, empty or unusable intent representation ──────────────────

class TestIntentRepresentation:
    def test_absent_assessment_is_not_an_intent(self):
        assert build_clarification_intent(None) is None
        r = render_clarification_response(None, request_text=DESC, plan_steps=["Draft"])
        assert not r.paired and r.text == SAFE_FAILURE_MESSAGE
        assert r.failure_reason == ca.FAILURE_NO_USABLE_INTENT

    def test_out_of_scope_abstention_is_not_an_intent(self):
        a = detect_creative_content_anchors("book a flight to Tokyo next week")
        assert not a.in_scope
        assert build_clarification_intent(a) is None
        r = render_clarification_response(a, request_text="book a flight", plan_steps=["Search"])
        assert not r.paired and r.text == SAFE_FAILURE_MESSAGE

    def test_an_abstaining_assessment_is_never_an_intent_even_with_an_artifact_name(self):
        # Detector-produced abstentions carry no artifact, but the guard must not depend
        # on that: abstention ("this policy abstains") is not an interpretation.
        a = dataclasses.replace(_assessment(), in_scope=False)
        assert a.artifact == "story" and not a.in_scope
        assert build_clarification_intent(a) is None
        r = render_clarification_response(a, request_text=DESC, plan_steps=["Draft"])
        assert not r.paired and r.failure_reason == ca.FAILURE_NO_USABLE_INTENT

    @pytest.mark.parametrize("kind", ["", "   ", None])
    def test_empty_artifact_is_not_an_intent(self, kind):
        a = dataclasses.replace(_assessment(), artifact=kind)
        assert build_clarification_intent(a) is None
        r = render_clarification_response(a, request_text=DESC, plan_steps=["Draft"])
        assert not r.paired and r.text == SAFE_FAILURE_MESSAGE

    def test_intent_is_derived_from_the_detector_data_only(self):
        assert build_clarification_intent(_assessment("write a story")) == (
            "I understand this as a request for a story. "
            "It doesn't say what the story should be about.")
        assert build_clarification_intent(_assessment("write an essay")).startswith(
            "I understand this as a request for an essay.")        # article agrees

    @pytest.mark.asyncio
    async def test_real_path_unusable_intent_is_a_safe_failure(self):
        # in-scope at the gate, but the intent representation cannot be built
        orch = _orch()
        with patch.object(ca, "build_clarification_intent", return_value=None):
            answer = await _handle(orch, _plan(_steps("Write the story")))
        assert answer == SAFE_FAILURE_MESSAGE
        assert "orchestrator.clarification_requested" not in _types(orch)


# ── 6. every supported artifact kind: question follows the artifact ─────

_KINDS = sorted(set(ca._ARTIFACTS.values()))
_PREMISE_WORDS = ("noir", "mystery", "fantasy", "comedy", "romance", "thriller",
                  "science fiction", "sci-fi", "research", "sources", "protagonist")


class TestArtifactQuestions:
    def test_the_supported_kinds_are_the_expected_five(self):
        assert _KINDS == ["essay", "joke", "poem", "song", "story"]

    @pytest.mark.parametrize("kind", _KINDS)
    def test_question_follows_the_artifact_without_inventing_a_premise(self, kind):
        a = _assessment(f"write a {kind}")
        assert a.artifact == kind
        q = build_clarification_question(a)
        assert q.endswith("Please send your request again with that detail.")
        assert "surprise me" in q                         # the way out the detector honours
        for word in _PREMISE_WORDS:
            assert word not in q.lower()
        assert q.count("?") <= 1

    def test_kind_specific_wording(self):
        q = {k: build_clarification_question(_assessment(f"write a {k}")) for k in _KINDS}
        assert "What should the story be about?" in q["story"] and "genre or tone" in q["story"]
        assert "poem" in q["poem"] and "theme or mood" in q["poem"]
        assert "Which topic or question should the essay address?" in q["essay"]
        assert "song" in q["song"] and "mood" in q["song"]
        assert "topic" in q["joke"] and "joke" in q["joke"]
        # no kind inherits another kind's noun
        assert "story" not in q["poem"] + q["essay"] + q["song"] + q["joke"]

    def test_the_old_story_specific_example_text_is_gone_for_every_kind(self):
        for kind in _KINDS:
            q = build_clarification_question(_assessment(f"write a {kind}"))
            assert "noir mystery" not in q and "cozy fantasy" not in q
            assert "funny office comedy" not in q and "Before I write this" not in q

    def test_generic_fallback_for_an_unlisted_artifact_kind(self):
        a = dataclasses.replace(_assessment(), artifact="sonnet-cycle")
        q = build_clarification_question(a)
        assert q.startswith("What should the sonnet-cycle be about?")
        assert q.endswith("Please send your request again with that detail.")

    def test_fallback_when_no_artifact_name_exists(self):
        a = dataclasses.replace(_assessment(), artifact="")
        assert build_clarification_question(a).startswith("What should the piece be about?")


# ── 7. no echoed raw request presented as an interpretation ─────────────

class TestNoRawEcho:
    @pytest.mark.parametrize("request_text", [
        "write a story", "Write a 1000 words story", "write a short poem.",
        "WRITE AN ESSAY", "tell me a joke",
    ])
    def test_the_request_text_is_never_displayed(self, request_text):
        a = detect_creative_content_anchors(request_text)
        r = render_clarification_response(
            a, request_text=request_text, plan_steps=["Draft it", "Revise it"])
        assert r.paired
        assert OLD_ECHO not in r.text
        assert request_text.strip(" .").casefold() not in r.text.casefold()

    @pytest.mark.parametrize("step", [
        DESC, DESC.lower(), DESC + ".", "  " + DESC + "  ", "unspecified", "Unspecified."])
    def test_the_planner_degrade_fallback_is_not_a_plan(self, step):
        # planner._decompose answers a failed model call with ONE step that is the
        # goal description itself (or "unspecified"): the request echoed, not a plan.
        assert genuine_plan_steps([step], DESC) == []
        r = render_clarification_response(_assessment(), request_text=DESC, plan_steps=[step])
        assert not r.paired and r.text == SAFE_FAILURE_MESSAGE

    def test_a_multi_step_plan_that_contains_the_request_is_still_a_plan(self):
        r = render_clarification_response(
            _assessment(), request_text=DESC, plan_steps=[DESC, "Revise the draft"])
        assert r.paired                               # not the single-step degrade shape

    @pytest.mark.asyncio
    async def test_real_path_degraded_planner_output_is_a_safe_failure(self):
        orch = _orch()
        answer = await _handle(orch, _plan(_steps(DESC)))
        assert answer == SAFE_FAILURE_MESSAGE
        assert OLD_ECHO not in answer and DESC not in answer

    @pytest.mark.asyncio
    async def test_real_path_missing_interpretation_data_does_not_invent_one(self):
        orch = _orch()
        answer = await _handle(orch, _plan(_steps("Draft the piece")), description="")
        assert isinstance(answer, str) and OLD_ECHO not in answer
        assert "I understand this as a request for a story." in answer   # from the detector
        assert "Write a story of about 1000" not in answer


# ── 8. step formatting and punctuation ──────────────────────────────────

class TestFormatting:
    def test_steps_are_separate_numbered_lines(self):
        t = build_clarification_response(
            _assessment(), request_text=DESC,
            plan_steps=["Draft the story.", "Revise the draft."])
        assert "\n1. Draft the story.\n2. Revise the draft.\n" in t
        assert "; 2." not in t and ".;" not in t           # the original defect

    def test_list_markers_are_normalised_and_never_doubled(self):
        t = build_clarification_response(
            _assessment(), request_text=DESC,
            plan_steps=["1. Alpha", "2) Beta", "- Gamma", "1. 2. Delta", "\u2022 Epsilon"])
        assert _numbered_lines(t) == ["1. Alpha", "2. Beta", "3. Gamma"]
        assert not re.search(r"\d+\. \d+\.", t)

    def test_a_decimal_or_year_prefix_is_not_a_list_marker(self):
        r = render_clarification_response(
            _assessment(), request_text=DESC,
            plan_steps=["3.5 hours of drafting", "2024. The year of the story"])
        assert _numbered_lines(r.text) == [
            "1. 3.5 hours of drafting", "2. 2024. The year of the story"]

    def test_no_empty_entries_and_no_trailing_blank_numbering(self):
        t = build_clarification_response(
            _assessment(), request_text=DESC, plan_steps=["A", "", "  ", "B", None, "C", "D"])
        lines = _numbered_lines(t)
        assert lines == ["1. A", "2. B", "3. C"]
        assert all(re.fullmatch(r"\d+\. \S.*", ln) for ln in lines)

    def test_multiline_model_text_is_flattened_and_truncated(self):
        t = build_clarification_response(
            _assessment(), request_text=DESC,
            plan_steps=["first line\nsecond   line\t" + "z" * 400])
        (line,) = _numbered_lines(t)
        assert "\n" not in line and "  " not in line
        assert len(line) <= 3 + ca._MAX_TEXT and line.endswith("\u2026")

    def test_layout_is_intent_then_plan_then_question(self):
        t = build_clarification_response(
            _assessment(), request_text=DESC, plan_steps=["Draft", "Revise"])
        blocks = t.split("\n\n")
        assert len(blocks) == 3
        assert blocks[0].startswith("I understand this as")
        assert blocks[1].startswith("Provisional draft plan")
        assert blocks[2].startswith("What should the story be about?")
        assert "\n\n\n" not in t

    def test_rendering_is_deterministic(self):
        args = dict(request_text=DESC, plan_steps=["Draft", "Revise", "Polish", "Extra"])
        assert build_clarification_response(_assessment(), **args) == \
            build_clarification_response(_assessment(), **args)


# ── 9. feature flag disabled: existing behaviour unchanged ──────────────

class TestFlagOff:
    @pytest.mark.asyncio
    async def test_flag_off_never_renders_or_emits_clarification(self):
        orch = _orch(enabled=False)
        await _handle(orch, _plan(_steps("Write the story")))
        assert "orchestrator.clarification_requested" not in _types(orch)
        assert "cognitive.content_anchor_observed" not in _types(orch)
        orch._workflow_runtime.execute.assert_called()     # proceeds exactly as before

    @pytest.mark.asyncio
    async def test_flag_off_is_independent_of_plan_shape(self):
        for plan in (_plan(_steps("A", "B", "C", "D", "E")), _plan(_steps(DESC))):
            orch = _orch(enabled=False)
            answer = await _handle(orch, plan)
            assert SAFE_FAILURE_MESSAGE not in str(answer)
            assert "Provisional draft plan" not in str(answer)
            assert not [p for t, p in _events(orch)
                        if p.get("error_type") == "ClarificationPairingUnavailable"]

    def test_default_constructor_leaves_the_feature_off(self):
        orch = Orchestrator(
            modules={}, context=MagicMock(spec=ContextMemory), router=MagicMock(),
            memory=AsyncMock(spec=UnifiedMemory), governance=GovernanceKernel(),
            event_stream=AsyncMock())
        assert orch._creative_content_anchor_enabled is False


# ── 10. flag enabled: established Orchestrator path, same governance boundary ──

class TestFlagOnGovernanceBoundary:
    @pytest.mark.asyncio
    async def test_c_plus_adds_no_governance_evaluation(self):
        async def record(flag, steps):
            order = []
            kernel = MagicMock()
            kernel.evaluate_action = MagicMock(
                side_effect=lambda a: order.append(("gov", a.action_type)) or GovernanceResult())
            orch = _orch(flag, governance=kernel)
            plan_mock = AsyncMock(side_effect=lambda *a, **k:
                                  order.append(("plan", None)) or _ready(_plan(steps)))
            with patch("core.cognitive.intent.interpret_request",
                       new=AsyncMock(return_value=[_goal()])), \
                 patch("core.cognitive.planner.plan", new=plan_mock):
                try:
                    await orch.handle(REQ)
                except Exception:
                    pass
            return order

        for steps in (_steps("A", "B", "C", "D"), _steps(DESC), _steps("Only step")):
            assert await record(True, steps) == await record(False, steps)

    @pytest.mark.asyncio
    async def test_response_follows_an_escalation_by_the_existing_orchestration_governor(self):
        orch = _orch()
        answer = await _handle(orch, _plan(_steps("Draft", "Revise")))
        order = _types(orch)
        assert order.index("cognitive.plan_rejected") < order.index(
            "orchestrator.clarification_requested")
        rejected = _payload(orch, "cognitive.plan_rejected")[0]
        assert rejected["verdict"] == "escalate" and rejected["content_anchor_score"] == 0.0
        assert "Provisional draft plan" in answer
        orch._workflow_runtime.execute.assert_not_called()   # nothing executed
        orch._execution_runtime.invoke.assert_awaited()      # Supervisor still surfaced

    @pytest.mark.asyncio
    async def test_no_model_call_is_made_to_produce_the_response_text(self):
        orch = _orch()
        await _handle(orch, _plan(_steps("Draft", "Revise")))
        orch.router.route.assert_not_called()

    def test_the_response_module_makes_no_model_call(self):
        tree = ast.parse(Path(ca.__file__).read_text())
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not [m for m in imported
                    if "model_router" in m or "provider" in m or "planner" in m]

    @pytest.mark.asyncio
    async def test_the_underlying_execution_plan_is_not_mutated(self):
        plan = _plan(_steps("1. Draft", "Revise", "Polish", "Ship"))
        before = [(s.step_id, s.description) for s in plan.steps]
        await _handle(_orch(), plan)
        assert [(s.step_id, s.description) for s in plan.steps] == before


# ── 11. other escalation causes never produce the detector's question ───

class TestOtherEscalations:
    @pytest.mark.asyncio
    async def test_escalation_from_another_governor_keeps_the_generic_path(self):
        kernel = GovernanceKernel()
        kernel._governors.insert(0, _StubGovernor(
            "SomeOtherGovernor", GovernanceVerdict.ESCALATE, only_for="plan_compile"))
        orch = _orch(governance=kernel)
        answer = await _handle(orch, _plan(_steps("Draft", "Revise")))
        assert "wasn't able to prepare" in answer
        assert "surprise me" not in answer and "Provisional" not in answer
        assert SAFE_FAILURE_MESSAGE not in answer
        assert "orchestrator.clarification_requested" not in _types(orch)
        (p,) = _payload(orch, "orchestrator.query_failed")
        assert p["error_type"] == "CompilationRejected"

    @pytest.mark.asyncio
    async def test_clarification_policy_escalation_for_an_anchored_request(self):
        orch = _orch()
        answer = await _handle(orch, _plan(_steps("Draft", "Revise"), confidence=0.1),
                               request="write a poem about autumn")
        assert "wasn't able to prepare" in answer and "surprise me" not in answer
        assert "orchestrator.clarification_requested" not in _types(orch)
        (p,) = _payload(orch, "orchestrator.query_failed")
        assert p["error_type"] == "CompilationRejected"

    @pytest.mark.asyncio
    async def test_a_governor_rejection_is_not_turned_into_a_clarification(self):
        kernel = GovernanceKernel()
        kernel._governors.insert(0, _StubGovernor(
            "Other", GovernanceVerdict.REJECT, only_for="plan_compile"))
        orch = _orch(governance=kernel)
        answer = await _handle(orch, _plan(_steps("Draft", "Revise")))
        assert "surprise me" not in str(answer)
        assert "orchestrator.clarification_requested" not in _types(orch)

    @pytest.mark.asyncio
    async def test_out_of_scope_request_abstains_and_proceeds(self):
        orch = _orch()
        await _handle(orch, _plan(_steps("Search flights", "Book")),
                      request="book a flight to Tokyo next week")
        orch._workflow_runtime.execute.assert_called()
        assert "orchestrator.clarification_requested" not in _types(orch)


# ── 12. event emission and terminal outcome ─────────────────────────────

class TestEventsAndOutcome:
    @pytest.mark.asyncio
    async def test_success_emits_clarification_requested_and_no_failure(self):
        orch = _orch()
        answer = await _handle(orch, _plan(_steps("Draft", "Revise")))
        assert isinstance(answer, str) and "Provisional draft plan" in answer
        types = _types(orch)
        assert types.count("orchestrator.clarification_requested") == 1
        assert "orchestrator.query_failed" not in types
        p = _payload(orch, "orchestrator.clarification_requested")[0]
        assert {"interaction_id", "goal_id", "status", "missing"} <= set(p)   # pre-existing keys
        assert p["goal_id"] == "g1" and p["missing"] == [ca.MISSING_SUBJECT]
        assert (p["plan_steps_shown"], p["plan_steps_total"]) == (2, 2)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("make_plan, reason", [
        (lambda: _plan(_steps(DESC)), ca.FAILURE_NO_USABLE_PLAN),
        (lambda: _plan(_steps("Write the story")), None),    # patched below
    ])
    async def test_safe_failure_emits_query_failed_not_success(self, make_plan, reason):
        orch = _orch()
        if reason is None:
            with patch.object(ca, "build_clarification_intent", return_value=None):
                answer = await _handle(orch, make_plan())
            reason = ca.FAILURE_NO_USABLE_INTENT
        else:
            answer = await _handle(orch, make_plan())
        assert answer == SAFE_FAILURE_MESSAGE
        types = _types(orch)
        assert "orchestrator.clarification_requested" not in types
        (p,) = _payload(orch, "orchestrator.query_failed")
        assert p["error_type"] == "ClarificationPairingUnavailable"
        assert reason in p["error"]
        assert {"interaction_id", "error", "error_type"} <= set(p)   # the existing contract keys
        orch._workflow_runtime.execute.assert_not_called()           # no substitute plan run

    @pytest.mark.asyncio
    async def test_safe_failure_leaks_no_internal_detail(self):
        orch = _orch()
        plan = _plan(_steps("Write the story"))
        plan.steps[0].description = None
        answer = await _handle(orch, plan)
        for leak in ("Traceback", "None", "Exception", "ClarificationPairingUnavailable",
                     "no_usable", "NoneType"):
            assert leak not in answer
        assert len(answer) < 200

    def test_safe_failure_text_is_the_specified_stable_wording(self):
        assert SAFE_FAILURE_MESSAGE == (
            "I couldn't form a reliable draft plan for this request. Please restate "
            "what you'd like me to create and include any details you already know.")
        assert "interpret" not in SAFE_FAILURE_MESSAGE.lower()     # claims no interpretation
        assert "plan for this request" in SAFE_FAILURE_MESSAGE     # claims no valid plan

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failing_event, make_plan, expected", [
        ("orchestrator.clarification_requested",
         lambda: _plan(_steps("Draft", "Revise")), "Provisional draft plan"),
        ("orchestrator.query_failed",
         lambda: _plan(_steps(DESC)), SAFE_FAILURE_MESSAGE),
    ])
    async def test_a_failing_event_emission_never_breaks_the_response(
            self, failing_event, make_plan, expected):
        # _emit_event swallows emission failures by contract; the DEBT-043 events
        # must keep that property so the user still gets the response.
        orch = _orch()

        async def append(event_type=None, source=None, payload=None):
            if event_type == failing_event:
                raise RuntimeError("stream down")
        orch._event_stream.append = AsyncMock(side_effect=append)
        answer = await _handle(orch, make_plan())
        assert isinstance(answer, str) and expected in answer
