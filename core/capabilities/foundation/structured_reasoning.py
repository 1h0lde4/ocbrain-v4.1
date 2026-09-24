"""
core/capabilities/foundation/structured_reasoning.py — STRUCTURED_REASONING
implementation A.

Structured analysis of supplied material. The result is *claims that point at
their sources, contradictions and stated uncertainty* -- explicitly NOT a
verdict:

  * ``verification: "not_performed"`` is stamped on every result: whether a
    finding is true is Verification's question. This capability only reports
    what it concluded and from what.
  * A finding's ``support`` is computed here, not taken from the model:
    "cited" only when at least one citation resolves to a block the model was
    actually shown; otherwise "uncited". "Cited" means *points at a source*,
    not *is true*. Citations that do not resolve are dropped and counted.
  * ``confidence`` is the model's own stated number, labelled
    ``confidence_basis: "model_stated"`` so it cannot be mistaken for match
    confidence, verification confidence or Intent Sufficiency (three different
    things).
  * Findings cite *source artifacts* (identity, revision, hash, locator) --
    never their own analysis -- so a downstream verifier is not handed circular
    evidence. A finding that cites a *prior analysis* also carries that
    finding's own artifact sources (lineage), so traceability does not stop at
    the first capability boundary.
  * Unknown model output keys (``verified``, ``verdict`` ...) are ignored: a
    model cannot smuggle a verdict through this capability.

Legitimately EMPTY (valid output, nothing found) is distinct from FAILED (the
reply did not satisfy the schema; retryable), and DEGRADED/PARTIAL follow the
inputs.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.capabilities.capability import (
    BaseAdapter, CapabilityRequest, CapabilityResult, CapabilityType,
)
from core.capabilities.descriptors import CapabilityStatus as S
from core.capabilities.foundation._common import (
    MODEL_OUTPUT_TRUST, as_list, is_plain_subject, model_provenance, run_model,
)
from core.capabilities.foundation.handoff import SourceBundle, build_bundle
from core.capabilities.foundation.models import TextModel
from core.capabilities.foundation.prompts import PromptTemplate, render_prompt
from core.capabilities.foundation.schemas import (
    SCHEMA_ANALYSIS, VERIFICATION_NOT_PERFORMED, clip,
)

ADAPTER_VERSION = "1.0.0"
FOCUSES = ("general", "diagnose", "contradictions", "alternatives", "relationships")
FINDING_KINDS = ("observation", "inference", "relationship", "contradiction",
                 "evaluation", "comparison")
_MAX_FINDINGS, _MAX_LIST, _MAX_TEXT = 50, 20, 1000

_FORMAT = (
    "Return ONE JSON object and no other text:\n"
    '{"findings":[{"statement":"...","kind":"observation|inference|relationship|'
    'contradiction|evaluation|comparison","cites":["S1:b3"],"confidence":0.0}],'
    '"contradictions":[{"between":["f1","f2"],"description":"..."}],'
    '"uncertainties":["..."],"conclusions":["..."]}\n'
    'Cite DATA references such as S1:b3, S2:t1 or A1:f1 in "cites". A finding '
    'with no citation must have kind "inference". "f1", "f2" refer to findings '
    "by position in your list (f1 is the first). \"confidence\" is your own 0-1 "
    "estimate or null. If there is nothing to report, return empty lists.")

_CONSTRAINTS = (
    "Base every non-inference finding on cited DATA.",
    "Report contradictions between sources instead of resolving them silently.",
    "Do not claim that any finding is verified.",
)
TEMPLATES: Dict[str, PromptTemplate] = {
    "analyze": PromptTemplate(
        "structured_reasoning.analyze", "1.0.0", "You are a rigorous analyst.",
        "Analyze the DATA for the TASK. State findings, note contradictions and be "
        "explicit about what you cannot determine.", _CONSTRAINTS, _FORMAT),
    "compare": PromptTemplate(
        "structured_reasoning.compare", "1.0.0", "You are a rigorous analyst.",
        'Compare the SUBJECTS across the DATA for the TASK; use kind "comparison" '
        "for each cross-subject finding.", _CONSTRAINTS, _FORMAT),
}


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """First JSON object in ``text`` (tolerates code fences and prose around
    it). Bounded: at most 50 candidate starts are tried, so pathological input
    cannot make this quadratic. None when there is no object."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        t = t.rsplit("```", 1)[0]
    decoder, tries = json.JSONDecoder(), 0
    for i, ch in enumerate(t):
        if ch != "{":
            continue
        tries += 1
        if tries > 50:
            return None
        try:
            obj, _ = decoder.raw_decode(t, i)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _strings(value: Any, size: int = _MAX_TEXT) -> List[str]:
    return [clip(v, size) for v in (value if isinstance(value, list) else [])
            if isinstance(v, str) and v.strip()][:_MAX_LIST]


def _resolve(tag: str, bundle: SourceBundle) -> List[Dict[str, Any]]:
    entry = bundle.catalog.get(tag)
    if not entry:
        return []
    if entry.get("kind") == "document":
        return [{"source_type": "artifact",
                 "source_id": f"{entry['artifact_id']}@{entry['revision'] or '-'}"
                              f"#{str(entry['content_sha256'])[:16]}",
                 "artifact_id": entry["artifact_id"], "revision": entry["revision"],
                 "content_sha256": entry["content_sha256"],
                 "locator": entry["locator"], "producer": entry["producer"]}]
    if entry.get("kind") == "analysis":
        refs = [{"source_type": "analysis_finding", "source_id": tag,
                 "finding_id": entry.get("finding_id", "")}]
        # lineage: the prior finding's own source pointers travel with it
        refs.extend(s for s in entry.get("sources") or [] if isinstance(s, dict))
        return refs
    return []  # a plain-text block has no artifact to point at


def validate_analysis(obj: Dict[str, Any], bundle: SourceBundle
                      ) -> Tuple[Dict[str, Any], List[str]]:
    """Coerce model output into the analysis body. Raises ValueError when the
    object does not satisfy the schema at all (-> FAILED, retryable)."""
    raw_findings = obj.get("findings")
    if not isinstance(raw_findings, list):
        raise ValueError("'findings' must be a list")
    notes: List[str] = []
    findings: List[Dict[str, Any]] = []
    unresolved = uncited = dropped = 0
    for pos, raw in enumerate(raw_findings[:_MAX_FINDINGS], 1):
        if (not isinstance(raw, dict) or not isinstance(raw.get("statement"), str)
                or not raw["statement"].strip()):
            dropped += 1
            continue
        kind = raw.get("kind") if raw.get("kind") in FINDING_KINDS else "inference"
        sources: List[Dict[str, Any]] = []
        for tag in (raw.get("cites") if isinstance(raw.get("cites"), list) else []):
            refs = _resolve(tag, bundle) if isinstance(tag, str) else []
            if refs:
                sources.extend(r for r in refs if r not in sources)
            else:
                unresolved += 1
        if not sources:
            uncited += 1
        conf = raw.get("confidence")
        confidence = (round(float(conf), 3)
                      if isinstance(conf, (int, float)) and not isinstance(conf, bool)
                      and 0.0 <= conf <= 1.0 else None)
        findings.append({
            "finding_id": f"f{pos}",  # position in the model's list; gaps are honest
            "kind": kind, "statement": clip(raw["statement"], _MAX_TEXT),
            "support": "cited" if sources else "uncited", "sources": sources,
            "confidence": confidence,
            "confidence_basis": "model_stated" if confidence is not None else "none"})
    ids = {f["finding_id"] for f in findings}
    contradictions: List[Dict[str, Any]] = []
    bad = 0
    for raw in (raw_findings and obj.get("contradictions") or []):
        between = raw.get("between") if isinstance(raw, dict) else None
        if (isinstance(between, list) and len(between) >= 2
                and all(isinstance(b, str) and b in ids for b in between)
                and isinstance(raw.get("description"), str)):
            contradictions.append({"between": list(between),
                                   "description": clip(raw["description"], _MAX_TEXT)})
        else:
            bad += 1
    if dropped:
        notes.append(f"findings_dropped:{dropped}")
    if unresolved:
        notes.append(f"unresolved_citations:{unresolved}")
    if uncited:
        notes.append(f"uncited_findings:{uncited}")
    if bad:
        notes.append("contradiction_dropped")
    return ({"findings": findings, "contradictions": contradictions[:_MAX_LIST],
             "uncertainties": _strings(obj.get("uncertainties")),
             "conclusions": _strings(obj.get("conclusions"))}, notes)


class StructuredReasoningAdapter(BaseAdapter):
    adapter_name = "structured-reasoning-prompted"
    capability_type = CapabilityType.STRUCTURED_REASONING
    adapter_version = ADAPTER_VERSION
    implements_contract = "1"
    supported_operations = ("analyze", "compare")

    def __init__(self, *, model: TextModel, max_input_chars: int = 120_000,
                 nonce_source: Optional[Callable[[], str]] = None) -> None:
        super().__init__()
        self._model = model
        self._max_input = max_input_chars
        self._nonce = nonce_source

    async def execute(self, request: CapabilityRequest,
                      resources: Any) -> CapabilityResult:
        op = request.operation or "analyze"
        template = TEMPLATES.get(op)
        p = request.payload
        if template is None:
            return CapabilityResult.of(S.INVALID_REQUEST, error=f"unknown operation {op!r}")
        task = p.get("task")
        if not isinstance(task, str) or not task.strip():
            return CapabilityResult.of(S.INVALID_REQUEST, error="task must be non-empty text")
        focus = p.get("focus") or "general"
        if focus not in FOCUSES:
            return CapabilityResult.of(S.INVALID_REQUEST,
                                       error=f"focus must be one of {list(FOCUSES)}")
        params: Dict[str, str] = {"FOCUS": focus}
        subjects: List[str] = []
        if op == "compare":
            raw = p.get("subjects")
            subjects = list(raw) if isinstance(raw, list) else []
            if len(subjects) < 2 or len(subjects) > 20 \
                    or not all(is_plain_subject(s) for s in subjects):
                return CapabilityResult.of(
                    S.INVALID_REQUEST,
                    error="compare needs 2-20 subjects, each a short single-line name")
            params["SUBJECTS"] = "; ".join(subjects)

        bundle = build_bundle(as_list(p.get("sources")), max_chars=self._max_input)
        if bundle.problems:
            status, reason = bundle.problems[0]
            return CapabilityResult.of(status, error=reason,
                                       metadata={"problems": [r for _, r in bundle.problems]})
        if not bundle.substantive:
            return CapabilityResult.of(
                S.EMPTY, output=self._output(op, S.EMPTY, task, focus, subjects, bundle,
                                             {"findings": [], "contradictions": [],
                                              "uncertainties": [], "conclusions": []},
                                             ["no_source_content"]),
                provenance={"model_called": False, "inputs": bundle.artifacts,
                            "verification": VERIFICATION_NOT_PERFORMED})

        rendered = render_prompt(template, task, bundle.blocks, params=params,
                                 nonce_source=self._nonce)
        completion, failure = await run_model(
            self._model, rendered.text, purpose=template.template_id,
            trace_id=request.trace_id)
        if failure is not None:
            return failure

        prov_model = model_provenance(self._model, completion)
        try:
            obj = extract_json_object(completion.text)
            if obj is None:
                raise ValueError("no JSON object in the reply")
            body, notes = validate_analysis(obj, bundle)
        except ValueError as e:
            return CapabilityResult.of(
                S.FAILED, error=f"output_schema_violation: {e}",
                metadata={"retryable": True},
                provenance={"prompt": {"id": rendered.template_id,
                                       "version": rendered.template_version},
                            "model": prov_model, "verification": VERIFICATION_NOT_PERFORMED})

        partial = False
        if bundle.truncated:
            partial = True
            notes.append("input_truncated_to_budget")
        if completion.truncated:
            partial = True
            notes.append("model_truncated")
        degraded = bundle.degraded_inputs
        if degraded:
            notes.append("inputs_partial_or_degraded")
        if not (body["findings"] or body["conclusions"] or body["contradictions"]):
            status = S.EMPTY
            notes.append("no_findings")
        else:
            status = S.PARTIAL if partial else (S.DEGRADED if degraded else S.OK)
        return CapabilityResult.of(
            status,
            output=self._output(op, status, task, focus, subjects, bundle, body, notes),
            provenance={
                "prompt": {"id": rendered.template_id, "version": rendered.template_version},
                "model": prov_model, "inputs": bundle.artifacts,
                "input_status": bundle.input_status(),
                "verification": VERIFICATION_NOT_PERFORMED,
            })

    @staticmethod
    def _output(op, status, task, focus, subjects, bundle, body, notes) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_ANALYSIS, "operation": op, "status": status,
            "task": task, "focus": focus, "subjects": subjects, **body,
            "notes": notes, "input_status": bundle.input_status(),
            "sources": list(bundle.artifacts),
            "trust": dict(MODEL_OUTPUT_TRUST),
            "verification": VERIFICATION_NOT_PERFORMED,
        }
