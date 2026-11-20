import shutil
import socket
import subprocess
import sys
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
from core.web import browser
from core.web.browser import (
    BrowserSandboxUnavailableError,
    _allows_browser_request,
    _header_value,
)


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
async def test_browser_fails_closed_without_bubblewrap(monkeypatch):
    monkeypatch.setattr(browser.sys, "platform", "linux")
    monkeypatch.setattr(browser.shutil, "which", lambda _: None)

    with pytest.raises(BrowserSandboxUnavailableError, match="Bubblewrap"):
        await browser.render_page("https://example.com", None)


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
    reason="Bubblewrap network namespace is only available on supported Linux hosts",
)
def test_bubblewrap_wrapper_isolates_network_namespace(tmp_path):
    system_python = shutil.which("python3", path="/usr/bin:/bin")
    if system_python is None:
        pytest.skip("A system Python interpreter is required for the sandbox probe")

    browser_root = tmp_path / "chromium"
    browser_root.mkdir()
    probe = browser_root / "probe"
    probe.write_text(
        f"#!{system_python}\n"
        "import socket\n"
        "names = {name for _, name in socket.if_nameindex()}\n"
        "assert names <= {'lo'}, names\n"
        "print('network namespace isolated')\n"
    )
    probe.chmod(0o700)

    wrapper = tmp_path / "chromium-sandbox"
    wrapper.write_text(browser._sandbox_wrapper_source(sys.executable))
    wrapper.chmod(0o700)
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "LANG": "C.UTF-8",
        "OCBRAIN_BWRAP": shutil.which("bwrap"),
        "OCBRAIN_CHROMIUM": str(probe),
        "OCBRAIN_CHROMIUM_ROOT": str(browser_root),
    }

    result = subprocess.run(
        [str(wrapper)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=15,
    )
    if result.returncode and "Operation not permitted" in result.stderr:
        pytest.skip("This Linux host does not permit network namespaces")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "network namespace isolated"


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
