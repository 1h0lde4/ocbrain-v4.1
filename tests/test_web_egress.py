import socket
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from yarl import URL

from core.web import egress
from core.web.egress import (
    PublicEgressError,
    PublicResolver,
    PublicWebClient,
    _validate_resolved_addresses,
    validate_public_url,
)
from core.web.browser import _allows_browser_request, _header_value


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.4/",
        "http://[::1]/",
        "http://localhost/",
        "http://printer.local/",
        "file:///etc/passwd",
        "https://user:password@example.com/",
        "https://example.com:8443/",
    ],
)
def test_validate_public_url_rejects_non_public_targets(url):
    with pytest.raises(PublicEgressError):
        validate_public_url(url)


def test_validate_public_url_allows_public_https_url():
    url = validate_public_url("https://example.com/article")

    assert url.host == "example.com"
    assert url.port == 443


def test_resolver_rejects_a_mixed_public_and_private_dns_answer():
    with pytest.raises(PublicEgressError, match="non-public"):
        _validate_resolved_addresses(
            "attacker.example",
            [
                (socket.AF_INET, "93.184.216.34"),
                (socket.AF_INET, "192.168.1.1"),
            ],
        )


def test_resolver_returns_only_public_dns_answers():
    addresses = _validate_resolved_addresses(
        "example.com",
        [(socket.AF_INET, "93.184.216.34")],
    )

    assert addresses == [(socket.AF_INET, "93.184.216.34")]


@pytest.mark.asyncio
async def test_resolver_returns_numeric_pinned_addresses(monkeypatch):
    class FakeLoop:
        async def getaddrinfo(self, host, port, *, family, type):
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("93.184.216.34", port),
                )
            ]

    monkeypatch.setattr("core.web.egress.asyncio.get_running_loop", FakeLoop)

    addresses = await PublicResolver().resolve("public.example", 443, socket.AF_UNSPEC)

    assert addresses[0]["host"] == "93.184.216.34"
    assert addresses[0]["flags"] == socket.AI_NUMERICHOST


@pytest.mark.asyncio
async def test_resolver_rejects_private_dns_answer(monkeypatch):
    class FakeLoop:
        async def getaddrinfo(self, host, port, *, family, type):
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    "",
                    ("10.0.0.1", port),
                )
            ]

    monkeypatch.setattr("core.web.egress.asyncio.get_running_loop", FakeLoop)

    with pytest.raises(PublicEgressError, match="non-public"):
        await PublicResolver().resolve("private.example", 443, socket.AF_UNSPEC)


@pytest.mark.parametrize(
    ("method", "resource_type", "allowed"),
    [
        ("GET", "document", True),
        ("GET", "script", True),
        ("GET", "fetch", True),
        ("POST", "fetch", False),
        ("PUT", "document", False),
        ("GET", "websocket", False),
        ("GET", "media", False),
        ("GET", "eventsource", False),
        ("GET", "other", False),
    ],
)
def test_browser_policy_allows_only_read_only_page_resources(
    method, resource_type, allowed
):
    assert _allows_browser_request(method, resource_type) is allowed


def test_browser_policy_enforces_page_request_limit():
    assert not _allows_browser_request("GET", "script", request_number=65)


def test_browser_response_header_lookup_is_case_insensitive():
    assert _header_value(
        {"content-disposition": " attachment; filename=page.html"},
        "Content-Disposition",
    ) == " attachment; filename=page.html"


@pytest.mark.asyncio
async def test_legacy_fetcher_uses_public_egress_policy(monkeypatch):
    from core.web import fetcher

    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, **kwargs):
            calls.append(url)
            raise PublicEgressError("blocked")

    monkeypatch.setattr(fetcher, "PublicWebClient", FakeClient)

    result = await fetcher.fetch_html("http://127.0.0.1/")

    assert result is None
    assert calls == ["http://127.0.0.1/"]


@pytest.mark.asyncio
async def test_browser_refuses_private_destination_before_startup():
    from core.web.browser import render_page

    with pytest.raises(PublicEgressError):
        await render_page("http://127.0.0.1", None)


@pytest.mark.asyncio
async def test_http_client_stops_before_following_a_private_redirect():
    response = Mock()
    response.status = 302
    response.headers = {"Location": "http://192.168.1.1/admin"}
    response.url = URL("https://public.example/")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = Mock()
    session.get = Mock(return_value=response)
    client = PublicWebClient()
    client._session = session

    with pytest.raises(PublicEgressError):
        await client.get("https://public.example/")

    session.get.assert_called_once()


@pytest.mark.asyncio
async def test_http_client_does_not_store_or_send_cookies(monkeypatch):
    session_options = {}

    class FakeSession:
        def __init__(self, **kwargs):
            session_options.update(kwargs)

        async def close(self):
            return None

    monkeypatch.setattr(egress.aiohttp, "TCPConnector", lambda **kwargs: Mock())
    monkeypatch.setattr(egress.aiohttp, "ClientSession", FakeSession)

    async with PublicWebClient():
        pass

    assert isinstance(session_options["cookie_jar"], aiohttp.DummyCookieJar)
