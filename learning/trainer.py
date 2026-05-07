"""
learning/trainer.py — Formats raw query/answer pairs into JSONL training data.
Mixes 20% of previous pairs to prevent catastrophic forgetting.
"""
import json
import random
import time
from pathlib import Path

DATA_RAW    = Path(__file__).parent.parent / "data" / "raw"
DATA_CHUNKS = Path(__file__).parent.parent / "data" / "chunks"


def prepare(module_name: str, registry: dict) -> Path | None:
    """
    Collect pairs, mix in replay, build JSONL.
    Returns path to training file, or None if not enough data.
    """
    from core.config import config
    min_pairs = int(config.get("learning.min_pairs_to_train") or 500)
    replay    = float(config.get("learning.replay_ratio") or 0.2)

    raw_pairs = _load_pairs(DATA_RAW / module_name)
    if len(raw_pairs) < min_pairs:
        print(f"[trainer] {module_name}: only {len(raw_pairs)} pairs (need {min_pairs})")
        return None

    prev_pairs = _load_pairs(DATA_CHUNKS / module_name, ext=".json")
    n_replay   = int(len(raw_pairs) * replay)
    replay_set = random.sample(prev_pairs, min(n_replay, len(prev_pairs)))
    mixed      = raw_pairs + replay_set
    random.shuffle(mixed)

    out_path = DATA_CHUNKS / f"{module_name}_train.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    module = registry.get(module_name)
    with open(out_path, "w", encoding="utf-8") as f:
        for pair in mixed:
            query  = pair.get("query", "")
            answer = pair.get("answer", "")
            if not query or not answer:
                continue
            # Retrieve KB context — mirrors inference RAG
            kb_chunks = module.retrieve(query, k=3) if module else []
            kb_str    = "\n".join(kb_chunks)
            record = {
                "instruction": query,
                "input":       kb_str,
                "output":      answer,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"[trainer] {module_name}: wrote {len(mixed)} training pairs → {out_path}")
    return out_path


def _load_pairs(directory: Path, ext: str = ".json") -> list[dict]:
    if not directory.exists():
        return []
    pairs = []
    for fpath in directory.glob(f"*{ext}"):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "query" in data:
                pairs.append(data)
        except Exception:
            continue
    return pairs
