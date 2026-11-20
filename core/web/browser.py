"""Read-only Playwright page rendering through the public egress client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from core.web.egress import (
    PublicEgressError,
    PublicWebClient,
    validate_public_url,
)

logger = logging.getLogger("ocbrain.web.browser")

_ALLOWED_RESOURCE_TYPES = {"document", "script", "stylesheet", "xhr", "fetch"}
_MAX_BROWSER_REQUESTS = 64
_STRIPPED_RESPONSE_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "transfer-encoding",
}


def _allows_browser_request(
    method: str, resource_type: str, request_number: int = 1
) -> bool:
    return (
        method == "GET"
        and resource_type in _ALLOWED_RESOURCE_TYPES
        and request_number <= _MAX_BROWSER_REQUESTS
    )


@dataclass(frozen=True)
class BrowserPage:
    url: str
    title: str
    text: str


async def render_page(
    url: str,
    client: PublicWebClient,
    *,
    timeout_seconds: float = 15.0,
    max_text_chars: int = 12_000,
) -> BrowserPage:
    """Render a public page without exposing click, form, or script APIs."""
    validated_url = validate_public_url(url)
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--no-first-run",
                "--host-resolver-rules=MAP * ~NOTFOUND",
                "--proxy-server=http://127.0.0.1:9",
                "--proxy-bypass-list=<-loopback>",
            ],
        )
        try:
            context = await browser.new_context(
                accept_downloads=False,
                service_workers="block",
            )
            request_count = 0

            async def fetch_request(route) -> None:
                nonlocal request_count
                request_count += 1
                request = route.request
                if not _allows_browser_request(
                    request.method, request.resource_type, request_count
                ):
                    await route.abort()
                    return

                try:
                    response = await client.get(
                        request.url,
                        headers=request.headers,
                        timeout=timeout_seconds,
                        follow_redirects=False,
                    )
                    response_headers = {
                        key: value
                        for key, value in response.headers.items()
                        if key.lower() not in _STRIPPED_RESPONSE_HEADERS
                    }
                    location = _header_value(response_headers, "location")
                    if location and 300 <= response.status < 400:
                        validate_public_url(urljoin(response.url, location))
                    if (
                        (_header_value(response_headers, "content-disposition") or "")
                        .lower()
                        .strip()
                        .startswith("attachment")
                    ):
                        await route.abort()
                        return
                    await route.fulfill(
                        status=response.status,
                        headers=response_headers,
                        body=response.body,
                    )
                except Exception as exc:
                    logger.warning(
                        "Blocked browser request to %s (%s)",
                        urlparse(request.url).hostname or "invalid",
                        type(exc).__name__,
                    )
                    await route.abort()

            async def block_websocket(websocket_route) -> None:
                nonlocal request_count
                request_count += 1
                await websocket_route.close()

            await context.route("**/*", fetch_request)
            await context.route_web_socket("**/*", block_websocket)
            page = await context.new_page()
            await page.goto(
                str(validated_url),
                wait_until="domcontentloaded",
                timeout=int(timeout_seconds * 1000),
            )
            text = await page.locator("body").inner_text(
                timeout=int(timeout_seconds * 1000)
            )
            return BrowserPage(
                url=page.url,
                title=await page.title(),
                text=text[:max_text_chars],
            )
        finally:
            await browser.close()


def _header_value(headers: dict[str, str], name: str) -> str | None:
    normalized_name = name.lower()
    return next(
        (value for key, value in headers.items() if key.lower() == normalized_name),
        None,
    )
