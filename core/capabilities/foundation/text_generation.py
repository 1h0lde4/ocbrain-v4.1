"""
core/capabilities/foundation/text_generation.py — TEXT_GENERATION implementation A.

Produces or transforms prose. It does not plan, verify, govern, route or decide
what the user meant: it is handed an instruction (trusted channel) and optional
material (data channel) and returns text plus an honest account of what
happened. The model is behind the TextModel port; this adapter owns prompt
construction (versioned templates), input handling, output validation and
provenance -- so replacing the model, provider or inference stack does not touch
the capability.

Statuses: no source material -> EMPTY (no model call, nothing to invent from);
the model owed an answer and returned none -> FAILED; input cut to the budget or
model/output truncated -> PARTIAL; partial/degraded upstream input -> DEGRADED
(never a silently ordinary-looking OK).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.capabilities.capability import (
    BaseAdapter, CapabilityRequest, CapabilityResult, CapabilityType,
)
from core.capabilities.descriptors import CapabilityStatus as S
from core.capabilities.foundation._common import (
    FORMATS, MODEL_OUTPUT_TRUST, as_list, model_provenance, run_model,
    validate_constraints,
)
from core.capabilities.foundation.handoff import SourceBundle, build_bundle
from core.capabilities.foundation.models import TextModel
from core.capabilities.foundation.prompts import PromptTemplate, render_prompt
from core.capabilities.foundation.schemas import SCHEMA_TEXT, VERIFICATION_NOT_PERFORMED

ADAPTER_VERSION = "1.0.0"

_COMMON = ("Do not invent facts that the DATA does not support; say plainly when "
           "information is missing.",)
_FMT = "Return only the requested text, with no preamble."

TEMPLATES: Dict[str, PromptTemplate] = {
    "generate": PromptTemplate(
        "text_generation.generate", "1.0.0",
        "You are a careful writing assistant.", "Write the requested text.",
        ("Use the DATA only as background material.",) + _COMMON, _FMT),
    "rewrite": PromptTemplate(
        "text_generation.rewrite", "1.0.0",
        "You are a careful editor.",
        "Rewrite the PRIMARY MATERIAL as the TASK asks, preserving its meaning.",
        ("Change wording and style only as the TASK asks.",) + _COMMON, _FMT),
    "summarize": PromptTemplate(
        "text_generation.summarize", "1.0.0",
        "You are a careful summarizer.",
        "Summarize the PRIMARY MATERIAL as the TASK asks.",
        ("Keep only what the material supports.",) + _COMMON, _FMT),
    "transform": PromptTemplate(
        "text_generation.transform", "1.0.0",
        "You are a careful formatter.",
        "Convert the PRIMARY MATERIAL into the TARGET FORMAT without adding content.",
        ("Preserve facts and figures exactly.",) + _COMMON, _FMT),
}
_DEFAULT_INSTRUCTION = {
    "rewrite": "Rewrite the material clearly.",
    "summarize": "Summarize the material concisely.",
    "transform": "Convert the material to the target format.",
}


class TextGenerationAdapter(BaseAdapter):
    adapter_name = "text-generation-prompted"
    capability_type = CapabilityType.TEXT_GENERATION
    adapter_version = ADAPTER_VERSION
    implements_contract = "1"
    supported_operations = ("generate", "rewrite", "summarize", "transform")

    def __init__(self, *, model: TextModel, max_input_chars: int = 120_000,
                 max_output_chars: int = 100_000,
                 nonce_source: Optional[Callable[[], str]] = None) -> None:
        super().__init__()
        self._model = model
        self._max_input = max_input_chars
        self._max_output = max_output_chars
        self._nonce = nonce_source

    async def execute(self, request: CapabilityRequest,
                      resources: Any) -> CapabilityResult:
        op = request.operation or "generate"
        template = TEMPLATES.get(op)
        p = request.payload
        if template is None:
            return CapabilityResult.of(S.INVALID_REQUEST, error=f"unknown operation {op!r}")

        instruction = p.get("instruction")
        if instruction is not None and not isinstance(instruction, str):
            return CapabilityResult.of(S.INVALID_REQUEST, error="instruction must be text")
        instruction = (instruction or "").strip() or _DEFAULT_INSTRUCTION.get(op, "")
        if not instruction:
            return CapabilityResult.of(S.INVALID_REQUEST, error="instruction is required")

        params, err = validate_constraints(p.get("constraints"))
        if err:
            return CapabilityResult.of(S.INVALID_REQUEST, error=err)
        if op == "transform":
            target = p.get("target_format")
            if target not in FORMATS:
                return CapabilityResult.of(
                    S.INVALID_REQUEST, error=f"target_format must be one of {list(FORMATS)}")
            params["Target format"] = target

        primary = build_bundle(p.get("source"), max_chars=self._max_input)
        bundle = build_bundle(as_list(p.get("source")) + as_list(p.get("context")),
                              max_chars=self._max_input)
        problems = bundle.problems or primary.problems
        if problems:
            status, reason = problems[0]
            return CapabilityResult.of(status, error=reason,
                                       metadata={"problems": [r for _, r in problems]})

        # Material requirements: rewrite/summarize/transform operate ON the
        # source; generate is grounded in `context` only when some was supplied.
        # Supplied-but-empty material yields EMPTY without a model call: a
        # capability must not invent content about something absent.
        if op != "generate":
            needs_check, material = True, primary
        else:
            needs_check, material = bool(as_list(p.get("context"))), bundle
        if needs_check and not material.substantive:
            return CapabilityResult.of(
                S.EMPTY, output=self._output(op, S.EMPTY, "", bundle,
                                             ["no_source_content"]),
                provenance={"model_called": False, "inputs": bundle.artifacts,
                            "verification": VERIFICATION_NOT_PERFORMED})
        if op != "generate":
            params["PRIMARY MATERIAL"] = "DATA blocks " + ", ".join(
                b.label for b in primary.blocks)

        rendered = render_prompt(template, instruction, bundle.blocks, params=params,
                                 nonce_source=self._nonce)
        completion, failure = await run_model(
            self._model, rendered.text, purpose=template.template_id,
            trace_id=request.trace_id)
        if failure is not None:
            return failure

        text = completion.text.strip()
        notes: List[str] = []
        partial = False
        if bundle.truncated:
            partial = True
            notes.append("input_truncated_to_budget")
        if completion.truncated:
            partial = True
            notes.append("model_truncated")
        if len(text) > self._max_output:
            text = text[: self._max_output]
            partial = True
            notes.append("output_truncated")
        degraded = bundle.degraded_inputs
        if degraded:
            notes.append("inputs_partial_or_degraded")
        status = S.PARTIAL if partial else (S.DEGRADED if degraded else S.OK)
        return CapabilityResult.of(
            status, output=self._output(op, status, text, bundle, notes),
            provenance={
                "prompt": {"id": rendered.template_id, "version": rendered.template_version},
                "model": model_provenance(self._model, completion),
                "inputs": bundle.artifacts,
                "input_status": bundle.input_status(),
                "verification": VERIFICATION_NOT_PERFORMED,
            })

    @staticmethod
    def _output(op: str, status: str, text: str, bundle: SourceBundle,
                notes: List[str]) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_TEXT, "operation": op, "status": status, "text": text,
            "notes": notes, "input_status": bundle.input_status(),
            "sources": list(bundle.artifacts),
            "trust": dict(MODEL_OUTPUT_TRUST),
            "verification": VERIFICATION_NOT_PERFORMED,
        }
