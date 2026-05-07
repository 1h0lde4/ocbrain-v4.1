"""
learning/gap_detector.py — Detects what the brain doesn't know well.
Analyses query logs + module scores to find weak topics,
then queues targeted distillation jobs to fill those gaps.
"""
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

from core.config import config
from core.event_bus import bus

DATA_RAW  = Path(__file__).parent.parent / "data" / "raw"
DATA_GAPS = Path(__file__).parent.parent / "data" / "gaps"

# Confidence below this in a module = a gap
GAP_CONFIDENCE_THRESHOLD = 0.55
# Minimum occurrences of a topic to bother distilling
MIN_TOPIC_HITS = 3


async def detect_and_queue(module_name: str, registry: dict) -> list[str]:
    """
    Analyse query logs for a module, detect weak topics,
    queue distillation jobs for each gap found.
    Returns list of gap topics detected.
    """
    gaps = _detect_gaps(module_name)
    if not gaps:
        print(f"[gap_detector] {module_name}: no significant gaps found.")
        return []

    print(f"[gap_detector] {module_name}: {len(gaps)} gaps detected — "
          f"{gaps[:5]}{'...' if len(gaps) > 5 else ''}")

    # Emit event so scheduler/UI knows
    await bus.emit("learning.gap_detected", {
        "module": module_name,
        "gaps":   gaps,
    })

    # Queue distillation (non-blocking — scheduler will pick up)
    _save_gap_queue(module_name, gaps)
    return gaps


def _detect_gaps(module_name: str) -> list[str]:
    """
    Two-signal gap detection:
    1. Low-confidence answers in query logs (if scores saved)
    2. Repeated queries with similar keywords (= user is asking about it a lot)
    """
    raw_dir = DATA_RAW / module_name
    if not raw_dir.exists():
        return []

    topic_hits:  Counter = Counter()
    weak_topics: list[str] = []

    for fpath in sorted(raw_dir.glob("*.json"))[-500:]:   # last 500 pairs
        try:
            data = json.loads(fpath.read_text())
        except Exception as e:
            log.warning(f"[gap_detector] Failed to parse {fpath.name}: {e}")
            continue

        query  = data.get("query", "")
        answer = data.get("answer", "")
        source = data.get("source", "")

        # Skip distillation-sourced pairs (we generated those)
        if source == "distillation":
            continue

        # Count topic keywords
        keywords = _extract_topic_keywords(query)
        for kw in keywords:
            topic_hits[kw] += 1

        # Flag low-quality answers as gaps
        if _answer_quality(answer) < GAP_CONFIDENCE_THRESHOLD:
            weak_topics.extend(keywords)

    # Topics that appear frequently → high priority to learn
    frequent = [
        topic for topic, count in topic_hits.most_common(20)
        if count >= MIN_TOPIC_HITS
    ]

    # Combine: weak answers + frequent queries
    gap_set   = set(weak_topics) | set(frequent)
    all_known = _load_known_topics(module_name)
    new_gaps  = [g for g in gap_set if g not in all_known]

    return new_gaps[:10]   # cap at 10 gaps per run


def _extract_topic_keywords(text: str) -> list[str]:
    """Extract 1-2 word topic phrases from a query."""
    # Remove common question words
    text = re.sub(
        r'\b(what|how|why|when|where|who|is|are|does|do|can|'
        r'explain|define|describe|tell me|show me)\b',
        '', text.lower()
    )
    # Extract noun phrases (simple bigram extraction)
    words   = [w for w in re.findall(r'\b[a-z]{3,}\b', text)]
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    return [b for b in bigrams if len(b) > 6][:3]


def _answer_quality(answer: str) -> float:
    """Estimate quality of an answer 0-1."""
    if not answer or len(answer) < 20:
        return 0.1
    # Error indicators
    if any(e in answer.lower() for e in ["error:", "failed:", "[module"]):
        return 0.1
    # Short answers = likely incomplete
    score = min(len(answer) / 300, 1.0)
    return round(score, 2)


def _save_gap_queue(module_name: str, gaps: list[str]):
    """Persist gap queue so scheduler can process it later."""
    DATA_GAPS.mkdir(parents=True, exist_ok=True)
    queue_file = DATA_GAPS / f"{module_name}_gaps.json"
    existing = []
    if queue_file.exists():
        try:
            existing = json.loads(queue_file.read_text())
        except Exception:
            pass
    merged = list(set(existing + gaps))
    queue_file.write_text(json.dumps(merged, indent=2))


def load_gap_queue(module_name: str) -> list[str]:
    """Load pending gap topics for a module."""
    queue_file = DATA_GAPS / f"{module_name}_gaps.json"
    if not queue_file.exists():
        return []
    try:
        return json.loads(queue_file.read_text())
    except Exception:
        return []


def clear_gap_queue(module_name: str):
    """Clear queue after distillation."""
    queue_file = DATA_GAPS / f"{module_name}_gaps.json"
    if queue_file.exists():
        queue_file.unlink()


def _load_known_topics(module_name: str) -> set[str]:
    """Topics already well-covered (from distillation history)."""
    history_file = DATA_GAPS / f"{module_name}_known.json"
    if not history_file.exists():
        return set()
    try:
        return set(json.loads(history_file.read_text()))
    except Exception:
        return set()


def mark_topic_known(module_name: str, topic: str):
    """Mark a topic as covered so we don't re-distill it."""
    DATA_GAPS.mkdir(parents=True, exist_ok=True)
    history_file = DATA_GAPS / f"{module_name}_known.json"
    known = _load_known_topics(module_name)
    known.add(topic)
    history_file.write_text(json.dumps(list(known), indent=2))
