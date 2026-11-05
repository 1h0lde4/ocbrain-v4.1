"""
interface/headers.py -- baseline security headers for every HTTP response (DEBT-025).

The UI keeps its API token in sessionStorage, so anything that can run script in
the page can read it.  These headers do not stop an injected inline script, but
they remove the easy follow-ons: third-party script and style loads, requests to
other origins (``connect-src 'self'``), framing by another site, and MIME
sniffing.  ``'unsafe-inline'`` remains because the shipped pages use inline
``<script>`` blocks and ``onclick`` attributes; removing those is a separate job.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, MutableMapping

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "object-src 'none'"
)

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode("ascii")),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]


class SecurityHeadersMiddleware:
    """Pure-ASGI: adds SECURITY_HEADERS to every http response that lacks them."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Callable[[], Awaitable[Message]],
                       send: Callable[[Message], Awaitable[None]]) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in SECURITY_HEADERS if k not in present]
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        await self.app(scope, receive, send_with_headers)
