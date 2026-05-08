"""
Compatibility facade for the older function-style V3 orchestrator API.

The class-based `core.orchestrator.Orchestrator` is the primary runtime path,
but these helpers are still useful for lightweight tests and integrations that
only need classify -> run -> merge without constructing the full brain.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .classifier_v3 import classify
from .provider_mesh import generate_with_fallback, resolve_provider

log = logging.getLogger("ocbrain.orchestrator_v3")


async def run_module(
    label: dict[str, Any],
    query: str,
    modules: dict[str, Any] | None = None,
    context: Any = None,
) -> str:
    module_name = label.get("module") or "knowledge"

    if modules and module_name in modules:
        module = modules[module_name]
        result = await module.run(query, context)
        answer = getattr(result, "answer", result)
        return f"[{module_name}] {answer}"

    providers = resolve_provider(module_name)
    answer = await generate_with_fallback(providers, query)
    return f"[{module_name}] {answer}"


def merge_results(results: list[Any]) -> str:
    valid: list[str] = []
    failures: list[Exception] = []

    for result in results:
        if isinstance(result, Exception):
            failures.append(result)
            continue
        text = str(result).strip()
        if text:
            valid.append(text)

    if not valid:
        return f"All modules failed ({len(failures)} failure(s))."
    if len(valid) == 1:
        return valid[0]
    return "\n\n".join(valid)


async def orchestrate(
    query: str,
    modules: dict[str, Any] | None = None,
    context: Any = None,
    top_k: int = 2,
) -> str:
    labels = classify(query, top_k=top_k)
    tasks = [run_module(label, query, modules=modules, context=context) for label in labels]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return merge_results(results)
