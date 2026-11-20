from unittest.mock import AsyncMock, Mock

import pytest

from core.web.browser import BrowserPage
from core.web.egress import PublicWebResponse
from modules.web_search.module import Module, _extract_ddg_urls


def test_ddg_urls_extracts_redirected_result_links():
    urls = _extract_ddg_urls(
        '<a class="result__a" href="//duckduckgo.com/l/?uddg='
        'https%3A%2F%2Fexample.org%2Fpage&rut=abc">Result</a>'
        '<a class="result__a" href="https://docs.example.org/">Docs</a>'
        '<a href="https://unrelated.example.org/">Not a result</a>'
    )

    assert urls == [
        "https://example.org/page",
        "https://docs.example.org/",
    ]


@pytest.mark.asyncio
async def test_run_discloses_when_no_web_results_are_available():
    module = Module.__new__(Module)
    module._fetch_live = AsyncMock(return_value=[])
    module.retrieve_async = AsyncMock(return_value=[])
    module._call_external_raw = AsyncMock()

    result = await module.run("current news", None)

    assert "couldn't retrieve" in result.answer
    assert result.source == "web_search"
    module._call_external_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_own_uses_fresh_web_results():
    module = Module.__new__(Module)
    module._fetch_live = AsyncMock(return_value=["fresh web result"])
    module.ingest = Mock()
    module.retrieve_async = AsyncMock(return_value=["stale stored result"])
    module._call_own_raw = AsyncMock(return_value="answer")

    result = await module.run_own("current topic", None)

    assert result.chunks_used == ["fresh web result"]
    assert "fresh web result" in module._call_own_raw.await_args.args[0]
    assert "stale stored result" not in module._call_own_raw.await_args.args[0]


@pytest.mark.asyncio
async def test_fetch_one_rejects_non_web_url():
    client = Mock()
    client.get = AsyncMock()

    chunks = await Module.__new__(Module)._fetch_one(client, "file:///etc/passwd")

    assert chunks == []
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_one_uses_browser_for_javascript_shell(monkeypatch):
    client = Mock()
    client.get = AsyncMock(
        return_value=PublicWebResponse(
            status=200,
            headers={"Content-Type": "text/html"},
            url="https://example.org/app",
            body=b"<html><body><div id='root'></div></body></html>",
        )
    )
    render_page = AsyncMock(
        return_value=BrowserPage(
            url="https://example.org/app",
            title="Rendered page",
            text="Rendered content " * 20,
        )
    )
    monkeypatch.setattr("core.web.browser.render_page", render_page)

    chunks = await Module.__new__(Module)._fetch_one(
        client, "https://example.org/app"
    )

    assert chunks
    assert "Source: https://example.org/app" in chunks[0]
    assert "Title: Rendered page" in chunks[0]
    render_page.assert_awaited_once_with("https://example.org/app", client)
