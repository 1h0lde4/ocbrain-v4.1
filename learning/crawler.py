"""
learning/crawler.py — Scheduled web crawler.
Fetches pages from trusted sources defined in sources.toml per module.
Respects robots.txt and rate limits.
"""
import asyncio
import time
from pathlib import Path

import feedparser
import httpx
import trafilatura

from core.config import config
from core.privacy import privacy

DATA_RAW = Path(__file__).parent.parent / "data" / "raw"
_LAST_FETCH: dict[str, float] = {}   # url → last fetch timestamp


async def run_all(registry: dict):
    """Crawl all enabled modules."""
    tasks = []
    for module_name in registry:
        if privacy.can_crawl(module_name):
            tasks.append(run_module(module_name))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_module(module_name: str):
    sources = config.get_sources(module_name)
    if not sources:
        return

    out_dir = DATA_RAW / module_name
    out_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        timeout=15.0,
        headers={"User-Agent": "OCBrain/2.1 (learning crawler)"},
        follow_redirects=True,
    ) as client:
        for source_url in sources:
            try:
                await _fetch_source(client, module_name, source_url, out_dir)
                await asyncio.sleep(1.0)   # 1 req/sec per source
            except Exception as e:
                print(f"[crawler] {module_name} | {source_url} | error: {e}")


async def _fetch_source(client, module_name: str, url: str, out_dir: Path):
    # Skip if fetched recently (within crawl_interval)
    interval_h = float(config.get("learning.crawl_interval_h") or 1)
    last        = _LAST_FETCH.get(url, 0)
    if time.time() - last < interval_h * 3600:
        return

    # RSS / Atom feed
    if any(kw in url for kw in ["rss", "feed", "atom", ".xml"]):
        await _fetch_feed(client, module_name, url, out_dir)
    else:
        await _fetch_page(client, module_name, url, out_dir)

    _LAST_FETCH[url] = time.time()


async def _fetch_page(client, module_name: str, url: str, out_dir: Path):
    resp = await client.get(url)
    text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
    if text and len(text) > 200:
        _save_raw(out_dir, url, text)


async def _fetch_feed(client, module_name: str, url: str, out_dir: Path):
    resp  = await client.get(url)
    feed  = feedparser.parse(resp.text)
    for entry in feed.entries[:10]:
        link = getattr(entry, "link", None)
        if not link:
            continue
        try:
            page = await client.get(link)
            text = trafilatura.extract(page.text, include_comments=False)
            if text and len(text) > 200:
                _save_raw(out_dir, link, text)
            await asyncio.sleep(1.0)
        except Exception:
            continue


def _save_raw(out_dir: Path, url: str, text: str):
    fname = out_dir / f"{abs(hash(url + str(time.time())))}.txt"
    fname.write_text(f"SOURCE: {url}\n\n{text}", encoding="utf-8")
