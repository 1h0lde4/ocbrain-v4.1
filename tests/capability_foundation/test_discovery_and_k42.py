"""
Discovery with the new metadata, phrasing diversity, and K4.2 protection.

Part 1 characterizes the UNCHANGED lexical matcher (ADR-K4.2-H-04) over realistic
wording -- not the capabilities' own names -- and records where it does and does
not reach the intended capability. Part 2 protects the K4.2 behavior that
ADR-K4.2-H-13 established (the general_purpose_only clarification exemption):
adding specific capabilities must not silently change it, which is exactly why
the foundation registers only behind [capabilities] foundation_enabled.
"""
import pathlib
import re
import tomllib
from unittest.mock import AsyncMock, patch

import pytest

from core.capabilities.capability import CapabilityContract, CapabilityType
from core.capabilities.descriptors import CapabilityLifecycle
from core.capabilities.registry import CapabilityRegistry
from core.cognitive.compiler import CompilationStatus, compile as compile_plan
from core.cognitive.intent import interpret_request
from core.cognitive.planner import (
    CapabilityDiscoveryRequest, PlannerRequest, PlannerStatus, discover_capabilities,
    plan as plan_fn,
)
from core.capabilities.foundation.wiring import register_foundation_capabilities
from tests.capability_foundation.fixtures import FakeLlmAdapter, ScriptedModel
from tests.capability_foundation.test_composition_pipeline import Stack

ROOT = pathlib.Path(__file__).resolve().parents[2]


def registry_with_foundation():
    reg = CapabilityRegistry()
    reg.register_capability(CapabilityContract(
        capability_type=CapabilityType.LLM_COMPLETION,
        description="Generate text from a prompt via a language model.",
        is_general_purpose=True))
    reg.register_adapter(CapabilityType.LLM_COMPLETION, FakeLlmAdapter())
    register_foundation_capabilities(reg, text_model=ScriptedModel())
    return reg


async def top(reg, phrase):
    # min_score=0.01 exactly as the planner's own call (K4.2-H1, frozen)
    res = await discover_capabilities(
        CapabilityDiscoveryRequest(subgoal_ref="s", description=phrase), reg, min_score=0.01)
    return res.top_match.capability_type, res


# ── part 1: phrasing diversity against the unchanged lexical matcher ─────────

SELECTED = [
    # TEXT_GENERATION
    ("write a short poem about autumn", "text_generation"),
    ("rewrite this paragraph more formally", "text_generation"),
    ("summarize the meeting notes", "text_generation"),
    ("compose a friendly email to the team", "text_generation"),
    ("convert the notes into bullet points", "text_generation"),
    ("draft an announcement for the launch", "text_generation"),
    # STRUCTURED_REASONING
    ("compare the two proposals on cost and risk", "structured_reasoning"),
    ("analyze why revenue dropped", "structured_reasoning"),
    ("diagnose the failing deployment", "structured_reasoning"),
    ("identify inconsistencies between the two accounts", "structured_reasoning"),
    ("evaluate alternatives for the database", "structured_reasoning"),
    ("draw conclusions from the survey results", "structured_reasoning"),
    # FILE_READING
    ("inspect the report", "file_reading"),
    ("extract the table from the spreadsheet", "file_reading"),
    ("read section 4 of the PDF", "file_reading"),
    ("read the CSV file", "file_reading"),
    ("open the docx and list its headings", "file_reading"),
]


class TestPhrasingDiversity:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("phrase,expected", SELECTED)
    async def test_realistic_wording_reaches_the_intended_capability(self, phrase, expected):
        assert (await top(registry_with_foundation(), phrase))[0] == expected

    @pytest.mark.asyncio
    async def test_wording_with_no_lexical_overlap_falls_back_to_the_general_capability(self):
        # "turn this into a concise report" shares no token with any description:
        # the safe outcome is the general-purpose fallback, never a wrong specific one.
        name, res = await top(registry_with_foundation(), "turn this into a concise report")
        assert name == "llm_completion" and res.top_match.is_general_purpose

    @pytest.mark.asyncio
    async def test_multi_capability_wording_is_one_capability_per_step_by_design(self):
        # Discovery picks ONE capability per step; a request spanning two is the
        # Planner's decomposition job (see the pipeline tests), not the matcher's.
        name, _ = await top(registry_with_foundation(), "summarize the attached document")
        assert name == "text_generation"

    @pytest.mark.asyncio
    async def test_discovery_evidence_now_carries_structured_metadata(self):
        _, res = await top(registry_with_foundation(), "read the CSV file")
        ev = {m.capability_type: m.evidence for m in res.matches}["file_reading"]
        assert ev["operations"] == ["read_document", "extract_structure"]
        assert ev["contract_version"] == "1.0.0" and ev["lifecycle"] == "active"
        assert set(ev) >= {"lexical_score", "specificity_tier", "general_fallback"}   # unchanged keys

    @pytest.mark.asyncio
    async def test_lexical_scores_are_low_for_every_specific_match(self):
        """The reason enabling is gated (ADR-CAP-03): well-formed requests score
        ~0.05-0.11 against prose descriptions -- far below ClarificationPolicy's 0.5."""
        for phrase, _ in SELECTED:
            _, res = await top(registry_with_foundation(), phrase)
            assert res.top_match.relevance_score < 0.5, phrase


# ── part 2: K4.2 / general_purpose_only protection ───────────────────────────

async def plan_compile(stack, decomposition, request="Read the attached report, analyze it and summarize it for me."):
    with patch("core.cognitive.intent.ContextAssemblyEngine") as eng, \
         patch("core.cognitive.intent.generate_with_fallback",
               new=AsyncMock(return_value="novel:task | 0.9")), \
         patch("core.cognitive.planner.generate_with_fallback",
               new=AsyncMock(return_value=decomposition)):
        eng.return_value.assemble_context = AsyncMock(return_value="")
        goals = await interpret_request(request, memory=object(), event_stream=stack.event_stream)
        goal = goals[0]
        result = await plan_fn(PlannerRequest(goal_id=goal.resource_id, goal=goal),
                               stack.registry, event_stream=stack.event_stream)
    return result, await compile_plan(result.execution_plan, event_stream=stack.event_stream)


CHAT = "1. Write a short haiku about autumn leaves"


class TestGeneralPurposeExemptionProtected:
    @pytest.mark.asyncio
    async def test_unchanged_without_the_foundation(self, tmp_path):
        """Baseline: only LLM_COMPLETION registered (production today). A low
        lexical score is exempt from clarification (ADR-K4.2-H-13)."""
        stack = Stack(tmp_path, foundation=False)
        result, comp = await plan_compile(stack, CHAT, "write me a haiku about autumn")
        assert result.status == PlannerStatus.READY_FOR_COMPILATION
        assert [s.capability_type for s in result.execution_plan.steps] == ["llm_completion"]
        assert result.execution_plan.confidence < 0.5            # low score...
        assert comp.status == CompilationStatus.COMPILED          # ...but exempt: no clarification

    @pytest.mark.asyncio
    async def test_registered_but_disabled_capabilities_leave_k42_untouched(self, tmp_path):
        stack = Stack(tmp_path)
        for cap in ("file_reading", "structured_reasoning", "text_generation"):
            stack.registry.set_lifecycle(cap, CapabilityLifecycle.DISABLED, reason="not adopted")
        result, comp = await plan_compile(stack, CHAT, "write me a haiku about autumn")
        assert [s.capability_type for s in result.execution_plan.steps] == ["llm_completion"]
        assert comp.status == CompilationStatus.COMPILED

    @pytest.mark.asyncio
    async def test_documented_hazard_enabling_changes_ordinary_chat_planning(self, tmp_path):
        """ASSERTED SO IT CANNOT CHANGE SILENTLY (ADR-CAP-03): with the foundation
        active, an ordinary chat request lexically matches TEXT_GENERATION weakly,
        the top candidate is no longer general-purpose, the exemption stops
        applying, and the low score is escalated. Not a bug in this branch -- the
        ADR-K4.2-H-13 design working as specified -- but the reason the foundation
        is default-off until the gates in ADR-CAP-03 are met."""
        stack = Stack(tmp_path)
        result, comp = await plan_compile(stack, CHAT, "write me a haiku about autumn")
        assert [s.capability_type for s in result.execution_plan.steps] == ["text_generation"]
        assert result.execution_plan.confidence < 0.5
        assert comp.status == CompilationStatus.ESCALATED

    @pytest.mark.asyncio
    async def test_llm_completion_remains_the_fallback_when_nothing_specific_matches(self, tmp_path):
        stack = Stack(tmp_path)
        result, comp = await plan_compile(stack, "1. Turn this into a concise briefing",
                                          "turn this into a concise briefing")
        assert [s.capability_type for s in result.execution_plan.steps] == ["llm_completion"]
        assert comp.status == CompilationStatus.COMPILED


class TestFeatureFlag:
    def test_flag_is_off_by_default_in_shipped_config(self):
        cfg = tomllib.loads((ROOT / "config/settings.toml").read_text(encoding="utf-8"))
        assert cfg["capabilities"]["foundation_enabled"] is False

    def test_main_reads_the_flag_with_default_false_and_gates_both_registrations(self):
        src = (ROOT / "main.py").read_text(encoding="utf-8").replace("\r\n", "\n")
        assert '"capabilities.foundation_enabled", False' in src
        for call in ("register_foundation_capabilities(capability_registry)",
                     "register_foundation_workers(worker_registry, adapter_runtime)"):
            assert re.search(r"if foundation_enabled:\n(?:[^\n]*\n){0,2}\s+" + re.escape(call), src), call
        # nothing else imports the foundation into the composition root (the
        # config KEY "capabilities.foundation_enabled" also contains this
        # substring, so match the import statement specifically)
        assert src.count("core.capabilities.foundation.") == 2

    def test_importing_the_foundation_registers_nothing(self):
        import importlib
        import core.capabilities.foundation.wiring as wiring
        importlib.reload(wiring)
        assert CapabilityRegistry().list_capabilities() == []
