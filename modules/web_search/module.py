"""
modules/web_search/module.py — V2.1: parallel URL fetch (asyncio.gather).
Fetching 3 URLs in parallel instead of series cuts latency ~60%.
"""
import asyncio
import logging
import time

import httpx
import trafilatura

from modules.base import BaseModule, ModuleResult
from core.config import config
from core.runtime.network import client as _network_client
from core.provider_mesh import resolve_provider, generate_with_fallback, graceful_generate_with_fallback

log = logging.getLogger(__name__)


class Module(BaseModule):
    name = "web_search"

    async def run(self, task: str, context) -> ModuleResult:
        t0 = time.monotonic()

        live_chunks = await self._fetch_live(task)
        if live_chunks:
            meta = [
                {"timestamp": time.time(), "quality_score": 0.75,
                 "source_type": "query", "source_url": "live"}
                for _ in live_chunks
            ]
            self.ingest(live_chunks, meta)

        kb_chunks = await self.retrieve_async(task, k=5)
        prompt    = self._build_prompt(task, kb_chunks or live_chunks, context)
        answer    = await self._call_external_raw(prompt)
        self.save_training_pair(task, answer)
        return ModuleResult(
            answer=answer, source="external",
            chunks_used=kb_chunks,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def run_own(self, task: str, context) -> ModuleResult:
        t0        = time.monotonic()
        kb_chunks = await self.retrieve_async(task, k=5)
        prompt    = self._build_prompt(task, kb_chunks, context)
        answer    = await self._call_own_raw(prompt)
        return ModuleResult(
            answer=answer, source="native",
            chunks_used=kb_chunks,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def _fetch_live(self, query: str) -> list[str]:
        try:
            searxng = config.get("global.searxng_url") or ""
            if searxng:
                urls = await self._searxng_urls(query, searxng)
            else:
                urls = await self._ddg_urls(query)

            # V2.1 FIX: fetch all URLs in parallel using pooled client
            tasks   = [self._fetch_one(_network_client, url) for url in urls[:3]]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            chunks = []
            for result in results:
                if isinstance(result, list):
                    chunks.extend(result)
            return chunks[:15]
        except Exception as e:
            log.debug(f"[web_search] fetch_live error: {e}")
            return []

    async def _fetch_one(self, client: httpx.AsyncClient, url: str) -> list[str]:
        """Fetch and chunk a single URL. Returns [] on any error."""
        try:
            resp = await client.get(url)
            text = trafilatura.extract(resp.text)
            if text and len(text) > 100:
                return _rough_chunk(text, 300)
        except Exception:
            pass
        return []

    async def _searxng_urls(self, query: str, base: str) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base}/search",
                params={"q": query, "format": "json", "engines": "google,bing"},
            )
            results = resp.json().get("results", [])
            return [r["url"] for r in results[:5] if "url" in r]

    async def _ddg_urls(self, query: str) -> list[str]:
        import re
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OCBrain/2.1)"},
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            urls = re.findall(r'href="(https?://[^"&]+)"', resp.text)
            return [u for u in urls if "duckduckgo.com" not in u][:5]

    def _build_prompt(self, task: str, chunks: list, context) -> str:
        ctx_str = context.format_for_prompt(3) if context else ""
        kb_str  = "\n\n".join(chunks) if chunks else "No web results found."
        return (
            f"You are a helpful assistant with access to current web information.\n"
            f"{ctx_str}\n\n"
            f"Web search results:\n{kb_str}\n\n"
            f"Query: {task}\n\nAnswer based on the search results:"
        )

    async def _call_external_raw(self, prompt: str) -> str:
        providers = resolve_provider(self.name)
        return await graceful_generate_with_fallback(
            providers, prompt,
            fallback_message="[Web search: no LLM available — start Ollama to enable AI responses]"
        )

    async def _call_own_raw(self, prompt: str) -> str:
        state = config.get_module_state(self.name)
        model = state.get("own_model_tag") or state.get("bootstrap_model", "mistral")
        from core.provider_mesh import OllamaProvider
        p = OllamaProvider(model=model)
        try:
            return await generate_with_fallback([p], prompt)
        except Exception as e:
            return f"[Web search own-model error: {e}]"


def _rough_chunk(text: str, max_tokens: int = 300) -> list[str]:
    words   = text.split()
    chunks  = []
    current = []
    for word in words:
        current.append(word)
        if len(current) >= max_tokens:
            chunks.append(" ".join(current))
            current = current[-50:]
    if current:
        chunks.append(" ".join(current))
    return chunks
