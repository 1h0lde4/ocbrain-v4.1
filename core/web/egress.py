"""Public-only HTTP access shared by web search and the browser renderer."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import aiohttp
from aiohttp.abc import AbstractResolver
from yarl import URL

logger = logging.getLogger("ocbrain.web.egress")

_ALLOWED_PORTS = {"http": 80, "https": 443}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_SENSITIVE_REQUEST_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "host",
    "connection",
    "content-length",
    "transfer-encoding",
    "upgrade",
}


class PublicEgressError(ValueError):
    """Raised when a request violates the public web egress policy."""


class ResponseTooLargeError(ValueError):
    """Raised when a response exceeds the configured byte limit."""


def validate_public_url(value: str) -> URL:
    if not isinstance(value, str):
        raise PublicEgressError("URL must be text")
    try:
        url = URL(value)
    except (TypeError, ValueError) as exc:
        raise PublicEgressError("Invalid URL") from exc

    if url.scheme not in _ALLOWED_PORTS or not url.host:
        raise PublicEgressError("Only HTTP and HTTPS URLs are allowed")
    if url.user is not None or url.password is not None:
        raise PublicEgressError("URLs containing credentials are not allowed")
    if url.port != _ALLOWED_PORTS[url.scheme]:
        raise PublicEgressError("Only standard HTTP and HTTPS ports are allowed")

    host = url.host.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise PublicEgressError("Local hostnames are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise PublicEgressError("Non-public IP addresses are not allowed")

    return url


def _validate_resolved_addresses(
    host: str, records: list[tuple[int, str]]
) -> list[tuple[int, str]]:
    addresses = []
    for family, address in records:
        parsed = ipaddress.ip_address(address.split("%", 1)[0])
        if not parsed.is_global:
            raise PublicEgressError(
                f"Host {host!r} resolved to a non-public IP address"
            )
        addresses.append((family, str(parsed)))
    if not addresses:
        raise PublicEgressError(f"Host {host!r} did not resolve to a public IP address")
    return addresses


class PublicResolver(AbstractResolver):
    """Resolve and pin only globally routable addresses for HTTP connections."""

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[dict[str, Any]]:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            loop = asyncio.get_running_loop()
            records = await loop.getaddrinfo(
                host, port, family=family, type=socket.SOCK_STREAM
            )
            candidates = [
                (record[0], record[4][0])
                for record in records
            ]
        else:
            candidates = [(socket.AF_INET6 if address.version == 6 else socket.AF_INET,
                           str(address))]

        addresses = _validate_resolved_addresses(host, candidates)
        return [
            {
                "hostname": host,
                "host": address,
                "port": port,
                "family": address_family,
                "proto": socket.IPPROTO_TCP,
                "flags": socket.AI_NUMERICHOST,
            }
            for address_family, address in addresses
        ]

    async def close(self) -> None:
        return None


@dataclass(frozen=True)
class PublicWebResponse:
    status: int
    headers: dict[str, str]
    url: str
    body: bytes
    encoding: str | None = None

    @property
    def text(self) -> str:
        return self.body.decode(self.encoding or "utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class PublicWebClient:
    """Bounded HTTP client that validates every request and DNS resolution."""

    def __init__(self, *, max_response_bytes: int = _MAX_RESPONSE_BYTES):
        self._max_response_bytes = max_response_bytes
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> PublicWebClient:
        connector = aiohttp.TCPConnector(
            resolver=PublicResolver(),
            use_dns_cache=False,
            limit=12,
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=15),
            auto_decompress=True,
            cookie_jar=aiohttp.DummyCookieJar(),
        )
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def get(
        self,
        value: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
        follow_redirects: bool = True,
    ) -> PublicWebResponse:
        if self._session is None:
            raise RuntimeError("PublicWebClient must be used as an async context manager")

        current_url = validate_public_url(value)
        if params:
            current_url = current_url.update_query(params)
        request_headers = {
            key: value
            for key, value in (headers or {}).items()
            if key.lower() not in _SENSITIVE_REQUEST_HEADERS
            and not key.lower().startswith("proxy-")
        }

        for redirect_count in range(_MAX_REDIRECTS + 1):
            current_url = validate_public_url(str(current_url))
            async with self._session.get(
                current_url,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=False,
            ) as response:
                location = response.headers.get("Location")
                if (
                    follow_redirects
                    and response.status in _REDIRECT_STATUSES
                    and location
                ):
                    if redirect_count == _MAX_REDIRECTS:
                        raise PublicEgressError("Too many redirects")
                    current_url = URL(urljoin(str(response.url), location))
                    continue

                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self._max_response_bytes:
                    raise ResponseTooLargeError("Web response exceeds the size limit")
                body = await response.content.read(self._max_response_bytes + 1)
                if len(body) > self._max_response_bytes:
                    raise ResponseTooLargeError("Web response exceeds the size limit")
                return PublicWebResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    url=str(response.url),
                    body=body,
                    encoding=response.charset,
                )

        raise PublicEgressError("Too many redirects")
