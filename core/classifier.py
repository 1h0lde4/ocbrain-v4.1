"""
core/classifier.py — V2.1: gated fast-path skips LLM for unambiguous queries.
Flow:
  1. Keyword match — if any module scores ≥ 0.75, return immediately (no LLM).
  2. Context boost — recent module usage raises confidence.
  3. LLM disambiguation — only called when top score < threshold.
  4. Fallback — knowledge module at 0.5 confidence.

Typical latency:
  Fast-path (80%+ of queries): ~1–5ms
  LLM path (ambiguous queries): ~1–3s
"""
import json
import logging
from dataclasses import dataclass

import httpx

from .config import config
from .parser import ParsedQuery

log = logging.getLogger(__name__)

FAST_PATH_THRESHOLD = 0.75   # skip LLM if keyword score ≥ this
LLM_THRESHOLD       = 0.60   # minimum acceptable confidence


@dataclass
class Label:
    module: str
    confidence: float
    subtask: str


async def label(parsed: ParsedQuery, context) -> list[Label]:
    module_names = config.all_module_names()
    scores: dict[str, float] = {}

    # ── Stage 1: keyword match (< 5ms, always runs) ──────────
    for mod in module_names:
        kws  = config.get_module_keywords(mod) or []
        hits = sum(1 for kw in kws if kw.lower() in parsed.raw.lower())
        if hits:
            base = min(0.4 + hits * 0.15, 0.85)
            boost = context.boost_module(mod) if context else 0.0
            scores[mod] = min(base + boost, 1.0)

    # ── Stage 2: fast-path gate — skip LLM entirely ──────────
    best = max(scores.values(), default=0.0)
    if best >= FAST_PATH_THRESHOLD:
        return _build_labels(scores, parsed.raw, LLM_THRESHOLD)

    # ── Stage 3: LLM disambiguation (slow path, ~1–3s) ───────
    llm_scores = await _llm_classify(parsed.raw, module_names)
    for mod, score in llm_scores.items():
        scores[mod] = max(scores.get(mod, 0.0), score)

    labels = _build_labels(scores, parsed.raw, LLM_THRESHOLD)

    # ── Stage 4: fallback ─────────────────────────────────────
    if not labels:
        labels = [Label(module="knowledge", confidence=0.5, subtask=parsed.raw)]

    return labels


def _build_labels(
    scores: dict[str, float], raw: str, threshold: float
) -> list[Label]:
    labels = [
        Label(module=mod, confidence=round(score, 3), subtask=raw)
        for mod, score in scores.items()
        if score >= threshold
    ]
    labels.sort(key=lambda label_item: label_item.confidence, reverse=True)
    return labels


async def _llm_classify(query: str, module_names: list[str]) -> dict[str, float]:
    host  = config.get("global.ollama_host") or "http://localhost:11434"
    # Use the first available module's bootstrap model, or fall back to a config default
    model = config.get("global.classifier_model") or "mistral"
    prompt = (
        f"Route this query to the correct modules. "
        f"Modules: {module_names}. "
        f"Reply ONLY with JSON mapping module names to confidence 0.0-1.0. "
        f"Query: {query}\nJSON:"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            text  = resp.json().get("response", "{}")
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
    except Exception as e:
        log.debug(f"[classifier] LLM classify failed: {e}")
    return {}
