"""
learning/distiller.py — Knowledge distillation pipeline.
Uses a teacher LLM to generate rich synthetic training data on specific topics.
This is the fastest way to make a module capable — far better than waiting
for organic query/answer pairs.

Flow:
    topic → generate N question/answer pairs via teacher
          → score quality
          → save to data/raw/{module}/
          → trigger embedder to add to KB immediately
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import httpx

from core.config import config
from core.event_bus import bus

DATA_RAW = Path(__file__).parent.parent / "data" / "raw"

# Prompt templates for generating training pairs
_PAIR_PROMPT = """You are generating training data for a specialized AI module on the topic: "{topic}"

Generate {n} high-quality question/answer pairs. Each pair should:
- Cover a distinct aspect of the topic
- Have a clear, factual, detailed answer (2-5 sentences)
- Range from basic to advanced

Respond ONLY with a JSON array, no markdown:
[
  {{"question": "...", "answer": "..."}},
  ...
]"""

_DEPTH_PROMPT = """You are an expert on: "{topic}"

For each question below, provide a comprehensive, accurate answer that a domain expert would give.
Be specific, include examples where relevant, and avoid vague generalities.

Questions:
{questions}

Respond as JSON array: [{{"question": "...", "answer": "..."}}, ...]"""


async def distill_topic(
    module_name: str,
    topic: str,
    num_pairs: int = 50,
    teacher_model: Optional[str] = None,
) -> int:
    """
    Generate synthetic training pairs for a module on a specific topic.
    Returns the number of pairs actually generated and saved.
    """
    
    host  = config.get("global.ollama_host") or "http://localhost:11434"
    state = config.get_module_state(module_name)

    # Use specified teacher, or bootstrap model, or mistral
    model = teacher_model or state.get("bootstrap_model", "mistral")

    print(f"[distiller] Generating {num_pairs} pairs for '{module_name}' "
          f"on topic: '{topic}' using {model}")

    pairs = []
    batch_size = min(10, num_pairs)
    batches    = (num_pairs + batch_size - 1) // batch_size

    async with httpx.AsyncClient(timeout=120.0) as client:
        for batch_idx in range(batches):
            n_this_batch = min(batch_size, num_pairs - len(pairs))
            prompt = _PAIR_PROMPT.format(topic=topic, n=n_this_batch)

            try:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                text = resp.json().get("response", "[]")
                batch_pairs = _parse_pairs(text)

                if not batch_pairs:
                    print(f"[distiller] Batch {batch_idx+1}: no parseable pairs")
                    continue

                # Score and filter
                scored = [p for p in batch_pairs if _score_pair(p) >= 0.5]
                pairs.extend(scored)
                print(f"[distiller] Batch {batch_idx+1}: "
                      f"{len(scored)}/{len(batch_pairs)} pairs kept")

                await asyncio.sleep(0.5)   # rate limit

            except Exception as e:
                print(f"[distiller] Batch {batch_idx+1} error: {e}")
                continue

    # Save pairs to data/raw/{module}/
    saved = _save_pairs(module_name, topic, pairs)

    # Emit event
    await bus.emit("learning.distill_done", {
        "module": module_name,
        "topic": topic,
        "pairs": saved,
    })

    print(f"[distiller] Done — {saved} pairs saved for '{module_name}'")
    return saved


def _parse_pairs(text: str) -> list[dict]:
    """Extract JSON array of {question, answer} from LLM output."""
    # Try to find JSON array in response
    start = text.find("[")
    end   = text.rfind("]") + 1
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start:end])
        pairs = []
        for item in data:
            if isinstance(item, dict):
                q = item.get("question") or item.get("query") or ""
                a = item.get("answer") or ""
                if q and a:
                    pairs.append({"query": q.strip(), "answer": a.strip()})
        return pairs
    except json.JSONDecodeError:
        return []


def _score_pair(pair: dict) -> float:
    """Simple quality score for a pair."""
    q = pair.get("query", "")
    a = pair.get("answer", "")
    if len(q) < 10 or len(a) < 20:
        return 0.0
    # Reward longer, more detailed answers
    score = min(len(a) / 200, 1.0)
    # Penalise answers that start with "I" (model self-reference)
    if a.startswith("I ") or a.startswith("I'm"):
        score *= 0.5
    return score


def _save_pairs(module_name: str, topic: str, pairs: list[dict]) -> int:
    out = DATA_RAW / module_name
    out.mkdir(parents=True, exist_ok=True)
    saved = 0
    for pair in pairs:
        record = {
            "query":     pair["query"],
            "answer":    pair["answer"],
            "source":    "distillation",
            "topic":     topic,
            "timestamp": time.time(),
        }
        fname = out / f"distil_{abs(hash(pair['query'] + str(time.time())))}.json"
        fname.write_text(json.dumps(record, ensure_ascii=False))
        saved += 1
    return saved


async def distill_from_gaps(module_name: str, gaps: list[str], pairs_per_gap: int = 20) -> int:
    """Distill training data for a list of detected knowledge gaps."""
    total = 0
    for gap_topic in gaps:
        n = await distill_topic(module_name, gap_topic, num_pairs=pairs_per_gap)
        total += n
    return total
