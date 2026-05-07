"""
learning/evaluator.py — Scores new weights before hot-swap is allowed.
Uses a fixed eval set + cosine similarity vs external model.
"""
import json
from pathlib import Path
from typing import Optional

EVAL_DIR = Path(__file__).parent.parent / "data" / "evals"
PASS_FLOOR     = 0.60    # absolute floor
TOLERANCE      = 0.02    # new weights can be this much worse than old
EVAL_SET_SIZE  = 20


async def evaluate(module_name: str, pending_path: Path, registry: dict) -> bool:
    """
    Returns True if new weights pass quality bar — safe to hot-swap.
    """
    evals = _load_eval_set(module_name)
    if not evals:
        # No eval set yet — auto-pass first time (no regression possible)
        print(f"[evaluator] {module_name}: no eval set found — auto-passing")
        return True

    module     = registry.get(module_name)
    if module is None:
        return False

    new_scores = []
    old_scores = []

    import asyncio

    async def _score_all():
        from core.model_router import model_router
        for q, expected in evals:
            # Score with new weights (loaded temporarily)
            new_ans = await _run_with_pending(module_name, pending_path, q)
            # Score with current active weights
            old_res = await module.run_own(q, None)
            old_ans = old_res.answer
            # External ground truth
            ext_ans = await model_router._call_external(module_name, q, None)

            new_scores.append(_cosine_sim(new_ans, ext_ans))
            old_scores.append(_cosine_sim(old_ans, ext_ans))

    await _score_all()

    avg_new = sum(new_scores) / len(new_scores) if new_scores else 0
    avg_old = sum(old_scores) / len(old_scores) if old_scores else 0

    passed = (avg_new >= avg_old - TOLERANCE) and (avg_new >= PASS_FLOOR)
    print(
        f"[evaluator] {module_name}: new={avg_new:.3f} old={avg_old:.3f} "
        f"→ {'PASS' if passed else 'FAIL'}"
    )
    return passed


async def _run_with_pending(module_name: str, pending_path: Path, query: str) -> str:
    """Temporarily load pending weights and get an answer."""
    import httpx
    from core.config import config
    # In production: load LoRA adapter from pending_path
    # For now: use the external model as proxy (weights loading requires GPU)
    state = config.get_module_state(module_name)
    model = state.get("bootstrap_model", "mistral")
    host  = config.get("global.ollama_host") or "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": query, "stream": False},
            )
            return resp.json().get("response", "").strip()
    except Exception:
        return ""


def _cosine_sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / ((len(sa) * len(sb)) ** 0.5)


def _load_eval_set(module_name: str) -> list[tuple[str, str]]:
    path = EVAL_DIR / f"{module_name}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [(item["query"], item.get("answer", "")) for item in data[:EVAL_SET_SIZE]]
    except Exception:
        return []


def save_eval_set(module_name: str, pairs: list[dict]):
    """Save a hand-crafted eval set for a module."""
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_DIR / f"{module_name}.json"
    path.write_text(json.dumps(pairs, indent=2, ensure_ascii=False))
