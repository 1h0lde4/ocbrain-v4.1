"""
Conformance: every capability contract is satisfied by MORE THAN ONE
implementation (Kernel Constitution invariant 6), checked by one reusable
function. Implementation B of each capability is deliberately different in kind
(no model / no parser library), so passing proves the contract is about the
capability, not about the first implementation.
"""
import pytest

from core.capabilities.capability import BaseAdapter, CapabilityResult, CapabilityType
from core.capabilities.descriptors import CapabilityStatus as S
from core.capabilities.foundation.contracts import (
    file_reading_contract, structured_reasoning_contract, text_generation_contract,
)
from core.capabilities.foundation.file_reading import FileReadingAdapter
from core.capabilities.foundation._common import validate_constraints
from core.capabilities.foundation.schemas import (
    SCHEMA_ANALYSIS, SCHEMA_TEXT, VERIFICATION_NOT_PERFORMED, ArtifactIdentity,
    ReadOutcome, document_set_dict, sha256_hex, valid_artifact_id,
)
from core.capabilities.foundation.structured_reasoning import StructuredReasoningAdapter
from core.capabilities.foundation.text_generation import TextGenerationAdapter
from tests.capability_foundation.conformance import ConformanceSamples, check_conformance
from tests.capability_foundation.fixtures import ScriptedModel, analysis_reply

DOC = {"artifact_id": "a1", "content": "# Title\n\nbody text\n", "media_type": "text/markdown"}


# ── implementation B of each capability: a different kind of implementation ──

class PlainTextFileReader(BaseAdapter):
    """FILE_READING B: no reader registry, no subprocess -- reads text only."""
    adapter_name = "plain-text-reader"
    capability_type = CapabilityType.FILE_READING
    adapter_version = "0.1.0"
    implements_contract = "1"
    supported_operations = ("read_document", "extract_structure")

    async def execute(self, request, resources):
        if not all(valid_artifact_id(a.get("artifact_id")) for a in request.payload["artifacts"]):
            return CapabilityResult.of(S.INVALID_REQUEST, error="artifact_id must be opaque")
        outcomes = []
        for a in request.payload["artifacts"]:
            raw = a["content"].encode() if isinstance(a["content"], str) else a["content"]
            ident = ArtifactIdentity(a["artifact_id"], a.get("revision", ""), sha256_hex(raw),
                                     "text/plain", len(raw))
            outcomes.append(ReadOutcome(ident, S.OK if raw.strip() else S.EMPTY))
        status = S.OK if any(o.status == S.OK for o in outcomes) else S.EMPTY
        return CapabilityResult.of(status, output=document_set_dict(
            status, outcomes, request.operation), provenance={"verification": "not_performed"})


class TemplateTextGenerator(BaseAdapter):
    """TEXT_GENERATION B: deterministic, no model."""
    adapter_name = "template-text"
    capability_type = CapabilityType.TEXT_GENERATION
    adapter_version = "0.1.0"
    implements_contract = "1"
    supported_operations = ("generate", "rewrite", "summarize", "transform")

    async def execute(self, request, resources):
        p = request.payload
        _, err = validate_constraints(p.get("constraints"))
        if err:
            return CapabilityResult.of(S.INVALID_REQUEST, error=err)
        text = str(p.get("instruction") or p.get("source") or "")
        if request.operation != "generate" and not str(p.get("source", "")).strip():
            status, text = S.EMPTY, ""
        else:
            status = S.OK
        return CapabilityResult.of(status, output={
            "schema": SCHEMA_TEXT, "operation": request.operation, "status": status,
            "text": text, "trust": {"data_trust": "unverified_model_output",
                                    "instruction_authority": "none"},
            "verification": VERIFICATION_NOT_PERFORMED})


class RuleBasedReasoner(BaseAdapter):
    """STRUCTURED_REASONING B: one observation per call, no model."""
    adapter_name = "rule-based-reasoner"
    capability_type = CapabilityType.STRUCTURED_REASONING
    adapter_version = "0.1.0"
    implements_contract = "1"
    supported_operations = ("analyze", "compare")

    async def execute(self, request, resources):
        p = request.payload
        has_material = any(str(x).strip() for x in p.get("sources") or [])
        findings = [{"finding_id": "f1", "kind": "observation", "statement": str(p["task"]),
                     "support": "uncited", "sources": [], "confidence": None,
                     "confidence_basis": "none"}] if has_material else []
        status = S.OK if findings else S.EMPTY
        return CapabilityResult.of(status, output={
            "schema": SCHEMA_ANALYSIS, "operation": request.operation, "status": status,
            "task": p["task"], "findings": findings, "contradictions": [],
            "uncertainties": [], "conclusions": [], "notes": [],
            "trust": {"data_trust": "unverified_model_output", "instruction_authority": "none"},
            "verification": VERIFICATION_NOT_PERFORMED})


# ── samples ──────────────────────────────────────────────────────────────────

FILE_SAMPLES = ConformanceSamples(
    valid={"read_document": {"artifacts": [DOC]}, "extract_structure": {"artifacts": [DOC]}},
    invalid={"artifacts": [{"artifact_id": "../etc/passwd", "content": "x"}]},
    empty=("read_document", {"artifacts": [{"artifact_id": "e", "content": ""}]}))
TEXT_SAMPLES = ConformanceSamples(
    valid={"generate": {"instruction": "write a line"}, "rewrite": {"source": "some text"},
           "summarize": {"source": "some text"},
           "transform": {"source": "a, b", "target_format": "bullets"}},
    invalid={"instruction": "x", "constraints": {"max_words": 0}},
    empty=("summarize", {"source": "   "}))
REASON_SAMPLES = ConformanceSamples(
    valid={"analyze": {"task": "what happened", "sources": ["some text"]},
           "compare": {"task": "compare", "sources": ["some text"],
                       "subjects": ["Plan A", "Plan B"]}},
    invalid={"task": "", "sources": ["x"]},
    empty=("analyze", {"task": "t", "sources": ["   "]}))


def _text_a():
    return TextGenerationAdapter(model=ScriptedModel("generated"))


def _reason_a():
    return StructuredReasoningAdapter(model=ScriptedModel(analysis_reply(
        [{"statement": "s", "kind": "inference"}])))


CASES = [
    ("file_reading/readers", file_reading_contract, FileReadingAdapter, FILE_SAMPLES),
    ("file_reading/plain-text", file_reading_contract, PlainTextFileReader, FILE_SAMPLES),
    ("text_generation/prompted", text_generation_contract, _text_a, TEXT_SAMPLES),
    ("text_generation/template", text_generation_contract, TemplateTextGenerator, TEXT_SAMPLES),
    ("structured_reasoning/prompted", structured_reasoning_contract, _reason_a, REASON_SAMPLES),
    ("structured_reasoning/rule-based", structured_reasoning_contract, RuleBasedReasoner, REASON_SAMPLES),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,contract,factory,samples", CASES, ids=[c[0] for c in CASES])
async def test_implementation_conforms_to_its_capability_contract(name, contract, factory, samples):
    assert await check_conformance(contract(), factory(), samples) == []


@pytest.mark.asyncio
async def test_the_checker_actually_catches_violations():
    """A conformance suite that cannot fail proves nothing."""
    class Wrong(TemplateTextGenerator):
        implements_contract = "2"                    # incompatible contract major
    assert any("registration refused" in v for v in
               await check_conformance(text_generation_contract(), Wrong(), TEXT_SAMPLES))

    class NoSchema(TemplateTextGenerator):
        async def execute(self, request, resources):
            return CapabilityResult.of(S.OK, output={"text": "x", "status": "ok"})
    v = await check_conformance(text_generation_contract(), NoSchema(), TEXT_SAMPLES)
    assert any("lacks declared keys" in x for x in v) and any("matches no declared" in x for x in v)

    class Verdict(TemplateTextGenerator):
        async def execute(self, request, resources):
            r = await super().execute(request, resources)
            r.output["verdict"] = "true"
            return r
    assert any("authority-shaped" in x for x in
               await check_conformance(text_generation_contract(), Verdict(), TEXT_SAMPLES))

    class EmptyIsFailure(TemplateTextGenerator):
        async def execute(self, request, resources):
            if request.operation == "summarize":
                return CapabilityResult(success=False, error="nothing to summarize")
            return await super().execute(request, resources)
    assert any("legitimate empty" in x for x in
               await check_conformance(text_generation_contract(), EmptyIsFailure(), TEXT_SAMPLES))

    class BadRequestIsFault(TemplateTextGenerator):
        async def execute(self, request, resources):
            if request.payload.get("constraints"):
                return CapabilityResult(success=False, error="bad request")   # -> "failed"
            return await super().execute(request, resources)
    assert any("request-level" in x for x in
               await check_conformance(text_generation_contract(), BadRequestIsFault(), TEXT_SAMPLES))
