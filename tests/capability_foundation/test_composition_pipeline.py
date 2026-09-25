"""
Composition through the REAL pipeline: FILE_READING -> STRUCTURED_REASONING ->
TEXT_GENERATION.

Real objects at every stage: interpret_request -> plan -> compile ->
WorkflowRuntime -> ExecutionRuntime -> governed step workers -> AdapterRuntime
-> real adapters (real parsers in the isolated subprocess). Only two things are
scripted, and both are named: the two LLM calls inside intent interpretation /
plan decomposition (the repository's established mock pattern) and the TextModel
behind the two model-backed capabilities.

The scripted model is *data-dependent*: it can only produce the unique document
token in its output by reading it out of the prompt it was given, so a passing
run proves the token really travelled document -> reading -> reasoning ->
generation through the typed hand-offs, not through test wiring.

Where the current runtime limits the path, the tests say so and assert the
exact boundary instead of pretending (see TestKnownBoundaries).
"""
import json
import re
from unittest.mock import AsyncMock, patch

import pytest

from core.capabilities.adapter_runtime import AdapterRuntime
from core.capabilities.capability import CapabilityContract, CapabilityType
from core.capabilities.descriptors import CapabilityStatus as S
from core.capabilities.foundation.wiring import (
    register_foundation_capabilities, register_foundation_workers,
)
from core.capabilities.registry import CapabilityRegistry
from core.capabilities.resource import ResourceManager
from core.cognitive.compiler import CompilationStatus, compile as compile_plan
from core.cognitive.intent import interpret_request
from core.cognitive.planner import ClarificationPolicy, PlannerRequest, PlannerStatus, plan as plan_fn
from core.events.event_stream import EventStream, SQLiteEventStore
from core.governance.governance_kernel import GovernanceKernel, get_governance_kernel
from core.governance.orchestration_governor import OrchestrationGovernor
from core.runtime.execution_outcome import FailureType
from core.runtime.execution_runtime import ExecutionRuntime
from core.runtime.worker_registry import WorkerRegistry
from core.workers.capability_executor import CapabilityExecutorWorker
from core.workflow.definition import WorkflowDefinition, WorkflowEdge, WorkflowNode
from core.workflow.runtime import WorkflowRuntime
from tests.capability_foundation.fixtures import (
    FakeLlmAdapter, ScriptedModel, analysis_reply, make_docx,
)

TOKEN = "ZEBRA-7731"
REPORT = (f"# Q3 Report\n\nRevenue grew 12% because of {TOKEN} adoption.\n\n"
          "## Risks\n\nSupply chain costs rose 8%.\n")
ARTIFACT = {"artifact_id": "q3-report", "revision": "5", "content": REPORT,
            "media_type": "text/markdown", "filename": "q3.md"}


def pipeline_model():
    """Data-dependent scripted model (see module docstring)."""
    def reply(prompt: str) -> str:
        if "Return ONE JSON object" in prompt:                     # STRUCTURED_REASONING
            m = re.search(r"\[(S\d+:b\d+)\][^\n]*?(" + TOKEN + r"[^\n]*)", prompt)
            if not m:                                              # nothing to analyze in the data
                return analysis_reply([], conclusions=[])
            return analysis_reply(
                [{"statement": f"Revenue growth is attributed to {TOKEN}.",
                  "kind": "observation", "cites": [m.group(1)], "confidence": 0.8}],
                conclusions=[f"Growth is driven by {TOKEN}."],
                uncertainties=["Only one quarter was supplied."])
        m = re.search(r"\[A1:c1\] conclusion: ([^\n]+)", prompt)   # TEXT_GENERATION
        return "Summary for you: " + (m.group(1) if m else "no analysis was provided")
    return ScriptedModel(reply, provider="scripted-provider", model="scripted-model-1")


class Stack:
    def __init__(self, tmp_path, model=None, *, foundation=True, governance=None):
        self.model = model or pipeline_model()
        self.event_stream = EventStream(store=SQLiteEventStore(db_path=str(tmp_path / "events.db")))
        self.registry = CapabilityRegistry()
        self.registry.register_capability(CapabilityContract(
            capability_type=CapabilityType.LLM_COMPLETION,
            description="Generate text from a prompt via a language model.",
            is_general_purpose=True))
        self.llm = FakeLlmAdapter()
        self.registry.register_adapter(CapabilityType.LLM_COMPLETION, self.llm)
        if foundation:
            register_foundation_capabilities(self.registry, text_model=self.model)
        self.adapter_runtime = AdapterRuntime(self.registry, ResourceManager(), self.event_stream)
        self.workers = WorkerRegistry()
        self.workers.register(CapabilityExecutorWorker,
                              constructor_kwargs={"adapter_runtime": self.adapter_runtime})
        if foundation:
            register_foundation_workers(self.workers, self.adapter_runtime)
        self.execution = ExecutionRuntime(
            worker_registry=self.workers, governance=governance or get_governance_kernel(),
            event_stream=self.event_stream)
        self.workflow = WorkflowRuntime(self.execution, self.event_stream)

    async def run(self, definition, artifacts=(ARTIFACT,), query="process the report"):
        return await self.workflow.execute(
            definition, query=query, session_id="s-1",
            metadata={"input_artifacts": [dict(a) for a in artifacts]})

    async def events(self, kind):
        return [e for e in await self.event_stream.query(limit=500) if e.event_type == kind]


def chain(*steps, wid="wf-cap"):
    """Hand-built sequential workflow: steps = (worker_type, config)."""
    nodes = [WorkflowNode(node_id=f"n{i}", worker_type=w, config=c)
             for i, (w, c) in enumerate(steps)]
    edges = [WorkflowEdge(from_node=f"n{i}", to_node=f"n{i + 1}") for i in range(len(steps) - 1)]
    return WorkflowDefinition(workflow_id=wid, name=wid, nodes=nodes, edges=edges,
                              entry_node="n0")


THREE = (("file_reading", {"description": "Read the attached report"}),
         ("structured_reasoning", {"description": "Analyze what drove revenue"}),
         ("text_generation", {"description": "Write a short summary for the user"}))


# ── the discovery-driven path (interpret -> plan -> compile -> execute) ─────

DECOMPOSITION = ("1. Read the attached report and extract its sections\n"
                 "2. Analyze the extracted content for revenue drivers and risks\n"
                 "3. Write a concise summary for the user")


async def plan_and_compile(stack, *, policy=None):
    with patch("core.cognitive.intent.ContextAssemblyEngine") as eng, \
         patch("core.cognitive.intent.generate_with_fallback",
               new=AsyncMock(return_value="novel:analyze_report | 0.9")), \
         patch("core.cognitive.planner.generate_with_fallback",
               new=AsyncMock(return_value=DECOMPOSITION)):
        eng.return_value.assemble_context = AsyncMock(return_value="")
        goals = await interpret_request(
            "Read the attached report, analyze it and summarize it for me.",
            memory=object(), event_stream=stack.event_stream)
        goal = goals[0]
        result = await plan_fn(PlannerRequest(goal_id=goal.resource_id, goal=goal),
                               stack.registry, event_stream=stack.event_stream)
    compilation = await compile_plan(result.execution_plan, event_stream=stack.event_stream,
                                     clarification_policy=policy)
    return result, compilation


class TestRealPipeline:
    @pytest.mark.asyncio
    async def test_request_to_downstream_capability_through_every_stage(self, tmp_path):
        stack = Stack(tmp_path)
        # The lexical confidence gate is relaxed HERE, and only here, to isolate the
        # capability pipeline from Intent Sufficiency (out of scope). The very same
        # plan under the default policy is asserted to escalate in the next test.
        result, compilation = await plan_and_compile(
            stack, policy=ClarificationPolicy(confidence_threshold=0.0))

        # discovery: three differently-worded steps found three different capabilities
        assert result.status == PlannerStatus.READY_FOR_COMPILATION
        assert [s.capability_type for s in result.execution_plan.steps] == [
            "file_reading", "structured_reasoning", "text_generation"]
        discovered = await stack.events("cognitive.capabilities_discovered")
        tops = {e.payload["candidates"][0]["capability_type"]: e.payload["candidates"][0]
                for e in discovered}
        assert tops["file_reading"]["operations"] == ["read_document", "extract_structure"]
        assert tops["file_reading"]["contract_version"] == "1.0.0"
        assert all(t["lifecycle"] == "active" for t in tops.values())

        # compilation: worker_type == capability_type for every node
        assert compilation.status == CompilationStatus.COMPILED
        wd = compilation.workflow_definition
        assert [n.worker_type for n in wd.nodes] == ["file_reading", "structured_reasoning",
                                                     "text_generation"]

        # execution
        wf = await stack.run(wd)
        assert wf.success, wf.error
        assert TOKEN in wf.output and wf.output.startswith("Summary for you:")   # crossed both hand-offs

        # the reasoning prompt saw the real reading; the final prompt saw ONLY the analysis
        reasoning_prompt, text_prompt = stack.model.prompts
        assert f"[S1:b2] Revenue grew 12% because of {TOKEN} adoption." in reasoning_prompt
        assert "artifact=q3-report revision=5" in reasoning_prompt
        assert f"conclusion: Growth is driven by {TOKEN}." in text_prompt
        assert "Supply chain costs rose 8%" not in text_prompt      # direct predecessor's output only
        assert stack.llm.calls == []                                 # the general fallback was not needed

    @pytest.mark.asyncio
    async def test_provenance_survives_every_capability_boundary(self, tmp_path):
        stack = Stack(tmp_path)
        wf = await stack.run(chain(*THREE))
        assert wf.success, wf.error
        r0, r1, r2 = (wf.node_results[f"n{i}"] for i in range(3))
        sha = r0.artifacts["structured"]["documents"][0]["artifact"]["content_sha256"]

        # each node: runtime-stamped identity + implementation facts
        for wr, cap, op in ((r0, "file_reading", "read_document"),
                            (r1, "structured_reasoning", "analyze"),
                            (r2, "text_generation", "generate")):
            p = wr.artifacts["provenance"]
            assert p["capability_type"] == cap and p["operation"] == op
            assert p["contract_version"] == "1.0.0" and p["adapter"]["name"] and p["trace_id"]
            assert p["verification"] == "not_performed"
            assert wr.artifacts["status"] == S.OK
        assert r0.artifacts["provenance"]["outcomes"][0]["reader"]["id"] == "markdown"
        assert r0.artifacts["provenance"]["inputs"][0]["content_sha256"] == sha
        assert r1.artifacts["provenance"]["prompt"]["id"] == "structured_reasoning.analyze"
        assert r1.artifacts["provenance"]["inputs"][0]["content_sha256"] == sha
        assert r2.artifacts["provenance"]["model"] == {
            "port": "scripted", "provider": "scripted-provider", "response_model": "scripted-model-1"}

        # the finding still points at the ORIGINAL artifact revision + content hash + location
        finding = r1.artifacts["structured"]["findings"][0]
        src = finding["sources"][0]
        assert (src["artifact_id"], src["revision"], src["content_sha256"]) == ("q3-report", "5", sha)
        assert src["locator"].startswith("lines=") and src["producer"].startswith("markdown@")

        # ...and lineage reaches the END of the pipeline: the generated text names the
        # artifact revision it ultimately derives from, though it only ever saw an analysis
        out = r2.artifacts["structured"]
        expected = {"artifact_id": "q3-report", "revision": "5", "content_sha256": sha}
        assert out["sources"] == [expected]
        assert r2.artifacts["provenance"]["inputs"] == [expected]
        assert out["trust"]["instruction_authority"] == "none" and out["verification"] == "not_performed"
        assert out["input_status"]["statuses"] == ["ok"]

    @pytest.mark.asyncio
    async def test_discovery_and_execution_events_expose_capability_operation_adapter(self, tmp_path):
        stack = Stack(tmp_path)
        await stack.run(chain(*THREE))
        invoked = {e.payload["capability_type"]: e.payload for e in await stack.events("adapter.invoked")}
        assert set(invoked) == {"file_reading", "structured_reasoning", "text_generation"}
        assert invoked["file_reading"]["operation"] == "read_document"
        assert invoked["file_reading"]["adapter"] == "file-reading-readers"
        assert invoked["text_generation"]["adapter_version"] == "1.0.0"
        assert invoked["structured_reasoning"]["status"] == S.OK

    @pytest.mark.asyncio
    async def test_explicit_operation_and_parameters_flow_from_node_config(self, tmp_path):
        stack = Stack(tmp_path)
        wf = await stack.run(chain(
            ("file_reading", {"description": "outline", "operation": "extract_structure"}),
            ("file_reading", {"description": "read risks", "selection": {"sections": ["Risks"]}}),
            ("text_generation", {"description": "Keep it short.", "operation": "summarize",
                                 "constraints": {"max_words": 40, "format": "bullets"}})))
        assert wf.success, wf.error
        outline = wf.node_results["n0"].artifacts["structured"]["documents"][0]["document"]
        assert outline["outline_only"] and [s["heading"] for s in outline["sections"]] == ["Q3 Report", "Risks"]
        risks = wf.node_results["n1"].artifacts["structured"]["documents"][0]["document"]
        assert [b["text"] for b in risks["blocks"]] == ["Risks", "Supply chain costs rose 8%."]
        assert wf.node_results["n2"].artifacts["operation"] == "summarize"
        assert "Maximum length: 40 words" in stack.model.prompts[0]
        assert "Format: bullets" in stack.model.prompts[0]
        assert "text_generation.summarize" in stack.model.purposes[0]

    @pytest.mark.asyncio
    async def test_multiple_mixed_format_artifacts_in_one_pipeline(self, tmp_path):
        stack = Stack(tmp_path)
        docx = {"artifact_id": "memo", "content": make_docx([f"The memo also mentions {TOKEN}."]),
                "filename": "memo.docx"}
        wf = await stack.run(chain(*THREE), artifacts=(ARTIFACT, docx))
        assert wf.success, wf.error
        doc_set = wf.node_results["n0"].artifacts["structured"]
        assert [d["provenance"]["reader"]["id"] for d in doc_set["documents"]] == ["markdown", "ooxml"]
        assert "[S1:" in stack.model.prompts[0] and "[S2:" in stack.model.prompts[0]


# ── the same plan under the default clarification policy ────────────────────

class TestK42InteractionDocumented:
    @pytest.mark.asyncio
    async def test_same_plan_is_escalated_by_the_default_policy(self, tmp_path):
        """DOCUMENTED HAZARD (ADR-CAP-03), asserted so it cannot change silently.

        Lexical discovery scores a well-formed request ~0.05 against a specific
        capability's description; plan confidence is the minimum of those scores;
        the default ClarificationPolicy escalates below 0.5. ADR-K4.2-H-13's
        exemption applies only while EVERY step's top candidate is general-purpose
        -- which stops being true the moment a specific capability is registered.
        This is why the foundation is registered only behind
        [capabilities] foundation_enabled (default false).
        """
        stack = Stack(tmp_path)
        result, compilation = await plan_and_compile(stack)          # default policy
        assert result.status == PlannerStatus.READY_FOR_COMPILATION
        assert result.execution_plan.confidence < 0.5
        assert compilation.status == CompilationStatus.ESCALATED
        assert compilation.workflow_definition is None


# ── failure, partial, empty and governance through the pipeline ─────────────

class TestPropagation:
    @pytest.mark.asyncio
    async def test_failure_stops_the_pipeline_and_nothing_is_invented(self, tmp_path):
        stack = Stack(tmp_path)
        png = {"artifact_id": "img", "content": b"\x89PNG\r\n\x1a\n" + b"0" * 32}
        wf = await stack.run(chain(*THREE), artifacts=(png,))
        assert not wf.success
        assert "unsupported" in wf.error and set(wf.node_results) == {"n0"}
        assert stack.model.calls == 0                                # downstream capabilities never ran
        r0 = wf.node_results["n0"]
        assert r0.execution_detail.failure_type == FailureType.VALIDATION_ERROR
        assert r0.artifacts["status"] == S.UNSUPPORTED and not wf.output

    @pytest.mark.asyncio
    async def test_missing_inputs_fail_explicitly_not_by_hallucination(self, tmp_path):
        stack = Stack(tmp_path)
        wf = await stack.run(chain(THREE[0]), artifacts=())          # FILE_READING with no artifacts
        assert not wf.success and "requires payload key" in wf.error
        wf2 = await stack.run(chain(THREE[1]))                       # reasoning with no upstream
        assert not wf2.success and "sources" in wf2.error
        assert stack.model.calls == 0

    @pytest.mark.asyncio
    async def test_partial_reading_is_visible_at_every_later_stage(self, tmp_path):
        stack = Stack(tmp_path)
        big = dict(ARTIFACT, artifact_id="big",
                   content=REPORT + "\n".join(f"\nFiller paragraph {i}." for i in range(300)))
        wf = await stack.run(chain(
            ("file_reading", {"description": "read", "limits": {"max_chars": 400}}),
            THREE[1], THREE[2]), artifacts=(big,))
        assert wf.success, wf.error                                   # usable, not a failure...
        statuses = [wf.node_results[f"n{i}"].artifacts["status"] for i in range(3)]
        assert statuses == [S.PARTIAL, S.DEGRADED, S.DEGRADED]        # ...but never laundered into "ok"
        for i in range(3):
            d = wf.node_results[f"n{i}"].execution_detail
            assert d.failure_type == FailureType.COMPLETED_WITH_PARTIAL_OUTPUT
            assert d.is_success and not d.is_fully_satisfied          # DEBT-020: partial != complete
        assert wf.node_results["n2"].artifacts["structured"]["input_status"]["degraded"] is True
        assert TOKEN in wf.output                                     # the first 400 chars contained it

    @pytest.mark.asyncio
    async def test_empty_document_stays_empty_through_the_pipeline(self, tmp_path):
        stack = Stack(tmp_path)
        wf = await stack.run(chain(*THREE), artifacts=(dict(ARTIFACT, artifact_id="e", content=b""),))
        assert wf.success
        assert [wf.node_results[f"n{i}"].artifacts["status"] for i in range(3)] == [S.EMPTY] * 3
        assert stack.model.calls == 0                                 # no model call, nothing invented
        assert wf.output == "No output: no_source_content"

    @pytest.mark.asyncio
    async def test_incompatible_schema_is_refused_at_the_capability_boundary(self, tmp_path):
        from core.capabilities.capability import CapabilityRequest
        stack = Stack(tmp_path)
        r = await stack.adapter_runtime.invoke("text_generation", request=CapabilityRequest(
            "text_generation", {"source": {"schema": "ocbrain.document_set/2", "status": "ok"}},
            operation="summarize"))
        assert r.status == S.INVALID_REQUEST and "incompatible_schema" in r.error
        assert stack.model.calls == 0

    @pytest.mark.asyncio
    async def test_governance_still_gates_the_new_workers(self, tmp_path):
        def kernel_denying(worker_type):
            k = GovernanceKernel()
            k._governors = [g for g in k._governors if g.name != "OrchestrationGovernor"]
            k.register_governor(OrchestrationGovernor(deny_worker_types=frozenset({worker_type})))
            return k

        # denied at the first node: nothing downstream runs, the capability is never invoked
        stack = Stack(tmp_path / "a", governance=kernel_denying("file_reading")) \
            if (tmp_path / "a").mkdir() is None else None
        wf = await stack.run(chain(*THREE))
        assert not wf.success and set(wf.node_results) == {"n0"}
        assert stack.model.calls == 0 and not await stack.events("adapter.invoked")

        # denial is per worker type: the others are still permitted (n0 runs, n1 is rejected)
        stack2 = Stack(tmp_path / "b", governance=kernel_denying("structured_reasoning")) \
            if (tmp_path / "b").mkdir() is None else None
        wf2 = await stack2.run(chain(*THREE))
        assert wf2.node_results["n0"].success and not wf2.node_results["n1"].success
        assert "n2" not in wf2.node_results and stack2.model.calls == 0


# ── replaceability inside the pipeline ──────────────────────────────────────

class TestReplaceability:
    @pytest.mark.asyncio
    async def test_swapping_implementations_keeps_the_pipeline_and_changes_provenance(self, tmp_path):
        from core.capabilities.foundation.readers.base import (
            MEDIA_MD, ReaderRegistry, ReaderSpec,
        )
        from core.capabilities.foundation.file_reading import FileReadingAdapter
        from core.capabilities.foundation.text_generation import TextGenerationAdapter

        stack = Stack(tmp_path)
        baseline = await stack.run(chain(*THREE))

        # implementation B of FILE_READING: a different reader for the same format
        def shouty_reader(data, opts):
            text = data.decode("utf-8")
            return {"blocks": [{"kind": "heading", "level": 1, "text": "Q3 Report", "locator": "x=1"},
                               {"kind": "paragraph", "text": text.split("\n\n")[1], "locator": "x=2"}]}
        readers = ReaderRegistry()
        readers.register(ReaderSpec("alt-md", "9.0", ("text",), (MEDIA_MD,), "inline"), shouty_reader)
        alt_reader = FileReadingAdapter(readers=readers)
        alt_reader.adapter_name = "file-reading-alt"
        stack.registry.register_adapter("file_reading", alt_reader)
        assert stack.registry.deregister_adapter("file_reading", "file-reading-readers")
        # implementation B of TEXT_GENERATION over a different model
        other = ScriptedModel(lambda p: "ALT: " + baseline.output.split(": ", 1)[1],
                              provider="other-provider", model="other-model")
        alt_text = TextGenerationAdapter(model=other)
        alt_text.adapter_name = "text-generation-alt"          # names are unique per capability
        stack.registry.register_adapter("text_generation", alt_text)
        assert stack.registry.deregister_adapter("text_generation", "text-generation-prompted")

        swapped = await stack.run(chain(*THREE))
        assert swapped.success, swapped.error
        # same semantic capabilities, same contracts, same pipeline shape...
        assert [swapped.node_results[f"n{i}"].artifacts["capability_type"] for i in range(3)] == [
            "file_reading", "structured_reasoning", "text_generation"]
        assert swapped.output.startswith("ALT: ") and TOKEN in swapped.output
        # ...different implementation identity, visible in provenance only
        assert swapped.node_results["n0"].artifacts["provenance"]["outcomes"][0]["reader"]["id"] == "alt-md"
        assert swapped.node_results["n2"].artifacts["provenance"]["model"]["provider"] == "other-provider"
        assert baseline.node_results["n0"].artifacts["provenance"]["outcomes"][0]["reader"]["id"] == "markdown"
