"""Shared mechanics of the two model-backed adapters (not a public surface)."""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

from core.capabilities.capability import CapabilityResult
from core.capabilities.descriptors import CapabilityStatus as S
from core.capabilities.foundation.models import ModelCompletion, TextModel

# Output produced by a model from untrusted inputs: unverified, and it carries
# no instruction authority when some other component consumes it.
MODEL_OUTPUT_TRUST: Dict[str, str] = {
    "data_trust": "unverified_model_output",
    "instruction_authority": "none",
}

FORMATS = ("plain_text", "markdown", "bullets", "numbered_list", "table",
           "outline", "json")
_TONE = re.compile(r"^[A-Za-z][A-Za-z ,'-]{0,39}$")
_SUBJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._,'&/()+-]{0,79}$")
MAX_WORDS_CEILING = 5000


def is_plain_subject(text: Any) -> bool:
    return isinstance(text, str) and bool(_SUBJECT.match(text))


def validate_constraints(constraints: Any) -> Tuple[Dict[str, str], Optional[str]]:
    """Parameters that reach the TASK channel must be short, plain and from a
    closed set -- a free-form string there is an injection path. Returns
    (params for the prompt, error message or None)."""
    if constraints is None:
        return {}, None
    if not isinstance(constraints, dict):
        return {}, "constraints must be an object"
    params: Dict[str, str] = {}
    for key, value in constraints.items():
        if key == "max_words":
            if (isinstance(value, bool) or not isinstance(value, int)
                    or not 1 <= value <= MAX_WORDS_CEILING):
                return {}, f"max_words must be an int in 1..{MAX_WORDS_CEILING}"
            params["Maximum length"] = f"{value} words"
        elif key == "tone":
            if not isinstance(value, str) or not _TONE.match(value):
                return {}, "tone must be a short plain phrase"
            params["Tone"] = value
        elif key == "format":
            if value not in FORMATS:
                return {}, f"format must be one of {list(FORMATS)}"
            params["Format"] = value
        else:
            return {}, f"unknown constraint {key!r}"
    return params, None


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


async def run_model(model: TextModel, prompt: str, *, purpose: str,
                    trace_id: str) -> Tuple[Optional[ModelCompletion],
                                            Optional[CapabilityResult]]:
    """Run the port and map its failure modes onto capability statuses.
    Provider faults are health-affecting (FAILED / TIMEOUT: the adapter's
    dependency failing). Error text carries the exception *type* only -- a
    provider's message may echo prompt content. Cancellation propagates."""
    try:
        completion = await model.complete(prompt, purpose=purpose, trace_id=trace_id)
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        return None, CapabilityResult.of(S.TIMEOUT, error="model timeout")
    except Exception as e:
        return None, CapabilityResult.of(S.FAILED, error=f"model error: {type(e).__name__}")
    if not (completion.text or "").strip():
        # Distinct from a legitimately EMPTY result: the model owed an answer.
        return None, CapabilityResult.of(S.FAILED, error="empty model response")
    return completion, None


def model_provenance(model: TextModel, completion: ModelCompletion) -> Dict[str, str]:
    out = {"port": model.model_id, "provider": completion.provider,
           "response_model": completion.model}
    requested = str(getattr(model, "request_model", "") or "")
    if requested:  # only when the port knows what it asked for
        out["request_model"] = requested
    return out
