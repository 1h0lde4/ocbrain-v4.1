"""
modules/knowledge/module.py — Knowledge / reasoning expert module.
Pure RAG: retrieve from KB → inject → generate.
"""
import time
import httpx
from modules.base import BaseModule, ModuleResult
from core.config import config


class Module(BaseModule):
    name = "knowledge"

    async def run(self, task: str, context) -> ModuleResult:
        t0     = time.monotonic()
        chunks = self.retrieve(task, k=6)
        prompt = self._build_prompt(task, chunks, context)
        answer = await self._call_external_raw(prompt)
        self.save_training_pair(task, answer)
        return ModuleResult(
            answer=answer, source="external",
            chunks_used=chunks,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def run_own(self, task: str, context) -> ModuleResult:
        t0     = time.monotonic()
        chunks = self.retrieve(task, k=6)
        prompt = self._build_prompt(task, chunks, context)
        answer = await self._call_own_raw(prompt)
        return ModuleResult(
            answer=answer, source="native",
            chunks_used=chunks,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    def _build_prompt(self, task: str, chunks: list, context) -> str:
        ctx_str = context.format_for_prompt(5) if context else ""
        kb_str  = "\n\n".join(chunks) if chunks else ""
        base    = (
            f"You are a knowledgeable assistant. "
            f"Answer clearly and accurately.\n"
        )
        if ctx_str:
            base += f"\nConversation:\n{ctx_str}\n"
        if kb_str:
            base += f"\nRelevant knowledge:\n{kb_str}\n"
        base += f"\nQuestion: {task}\n\nAnswer:"
        return base

    async def _call_external_raw(self, prompt: str) -> str:
        state = config.get_module_state(self.name)
        model = state.get("bootstrap_model", "mistral")
        host  = config.get("global.ollama_host") or "http://localhost:11434"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[Knowledge module error: {e}]"

    async def _call_own_raw(self, prompt: str) -> str:
        state = config.get_module_state(self.name)
        model = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        host  = config.get("global.ollama_host") or "http://localhost:11434"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[Knowledge own-model error: {e}]"
