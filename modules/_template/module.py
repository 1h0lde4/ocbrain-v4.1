"""
modules/_template/module.py — Template for custom user-created modules.
Copied and substituted by module_factory.py.
Placeholders: {{NAME}}, {{DESC}}
"""
import time
import httpx
from modules.base import BaseModule, ModuleResult
from core.config import config


class Module(BaseModule):
    name = "{{NAME}}"
    desc = "{{DESC}}"

    async def run(self, task: str, context) -> ModuleResult:
        t0     = time.monotonic()
        chunks = self.retrieve(task, k=5)
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
        chunks = self.retrieve(task, k=5)
        prompt = self._build_prompt(task, chunks, context)
        answer = await self._call_own_raw(prompt)
        return ModuleResult(
            answer=answer, source="native",
            chunks_used=chunks,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    def _build_prompt(self, task: str, chunks: list, context) -> str:
        """Override this in your custom module to tune the prompt."""
        ctx_str = context.format_for_prompt(5) if context else ""
        kb_str  = "\n\n".join(chunks) if chunks else "No relevant knowledge found."
        return (
            f"You are an expert in {self.desc}.\n"
            f"{ctx_str}\n\n"
            f"Relevant knowledge:\n{kb_str}\n\n"
            f"Task: {task}\n\nResponse:"
        )

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
            return f"[{self.name} module error: {e}]"

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
            return f"[{self.name} own-model error: {e}]"
