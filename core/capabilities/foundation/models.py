"""
core/capabilities/foundation/models.py — the model port.

TEXT_GENERATION and STRUCTURED_REASONING are *capabilities*; a language model is
an implementation detail of one adapter (Constitution: "Models are Adapters").
This port is the seam between the adapter (prompt construction, input handling,
output validation, provenance) and whatever produces text. Swapping the model,
the provider, or the whole inference stack means supplying another ``TextModel``;
the capability contract, the adapters and every consumer stay as they are.

The default binding (ProviderMeshTextModel) deliberately does NOT use
core.provider_mesh.generate_with_fallback(), for three verified reasons:

  1. Prompt compression. generate_with_fallback -> cached_generate() compresses
     any prompt over ~500 words by keeping the first and last words and
     discarding the middle. For a document-grounded prompt that silently drops
     the middle of the document -- and can drop the trust rules or the data
     block terminator. Capability prompts must arrive whole.
  2. Learning contamination. Routing through ModelRouter (the LLM_COMPLETION
     adapter) records every (prompt, answer) pair as training data and persists
     per-module state to models.toml; these prompts carry untrusted, possibly
     private, document-derived content. A capability must not open that channel
     implicitly.
  3. Prompt cache. The mesh's in-process prompt cache would retain
     document-derived prompts and answers.

What it keeps from the mesh: provider ranking by health, the optional
mark_success / mark_failure health hooks, fallback across providers, treating an
empty answer as a failure, and safe_llm_call's concurrency + timeout guard.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, Protocol


@dataclass(frozen=True)
class ModelCompletion:
    text: str
    provider: str = ""    # who answered, when known (OTel: provider.name)
    model: str = ""       # model that answered, when known (OTel: response.model)
    truncated: bool = False  # the model stopped at a length limit


class TextModel(Protocol):
    """Anything that turns a prompt into text. Raise on failure. An empty
    ``text`` is reported by the adapter as a *failure* (the model owed an
    answer), distinct from a legitimately EMPTY capability result."""
    model_id: str

    async def complete(self, prompt: str, *, purpose: str,
                       trace_id: str) -> ModelCompletion: ...


def _hook(provider: Any, name: str) -> None:
    fn = getattr(provider, name, None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass


class ProviderMeshTextModel:
    """Default port over the provider mesh's *providers* (not its cached
    generation path)."""
    model_id = "provider_mesh"

    def __init__(self, module_name: str = "capability_foundation", *,
                 resolve: Optional[Callable[[str], List[Any]]] = None,
                 call: Optional[Callable[..., Awaitable[Any]]] = None) -> None:
        self._module_name = module_name
        self._resolve = resolve
        self._call = call

    def _bindings(self):
        resolve, call = self._resolve, self._call
        if resolve is None:
            from core.provider_mesh import resolve_provider  # lazy: known import cycle
            resolve = resolve_provider
        if call is None:
            from core.runtime.limits import safe_llm_call
            call = safe_llm_call
        return resolve, call

    async def complete(self, prompt: str, *, purpose: str,
                       trace_id: str) -> ModelCompletion:
        resolve, call = self._bindings()
        providers = list(resolve(self._module_name))
        if not providers:
            raise RuntimeError("no providers resolved for capability model")

        def usable(p: Any) -> bool:
            checker = getattr(p, "is_available", None)
            try:
                return bool(checker()) if callable(checker) else True
            except Exception:
                return False

        pool = [p for p in providers if usable(p)] or providers
        ranked = sorted(pool, key=lambda p: getattr(p, "health_score", 0), reverse=True)
        last: Optional[BaseException] = None
        for provider in ranked:
            try:
                text = await call(provider.generate, prompt)
                if not text or not str(text).strip():
                    raise ValueError("provider returned an empty response")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last = e
                _hook(provider, "mark_failure")
                continue
            _hook(provider, "mark_success")
            return ModelCompletion(
                text=str(text),
                provider=str(getattr(provider, "name", type(provider).__name__)),
                model=str(getattr(provider, "model", "") or ""))
        raise RuntimeError(
            f"all {len(ranked)} provider(s) failed; last: {type(last).__name__}")
