"""
interface/auth.py -- authentication boundary for the HTTP API (DEBT-025).

Design (see docs/reports/api-exposure-and-auth-boundary-oct2026.md):

* Default-on, fail-closed.  Every HTTP request must carry
  ``Authorization: Bearer <token>`` unless its method and path are in the
  explicit public allowlist below.  A route added later is protected by default;
  it becomes public only by an edit to this file.
* One per-installation secret, never derived from request content.  Source, in
  order: the ``OCBRAIN_API_TOKEN`` environment variable, else the token file
  (``data/api_token``, or ``OCBRAIN_API_TOKEN_FILE``), created on first start
  with mode 0600.  The token is never logged and never placed in an event.
* Comparison is constant-time (``hmac.compare_digest``).
* Implemented as a pure ASGI middleware, not a per-route dependency: the check
  is explicit, sits in front of routing (so unknown paths do not reveal which
  routes exist), and does not buffer streaming (SSE) responses.
* Denials are audited: a structured WARNING log and an ``api.auth_denied`` event
  carrying the reason code, method and a sanitised path, never the credential.
* Authentication is not authorisation.  Authenticated control-plane requests are
  still outside GovernanceKernel (DEBT-025's second finding); this module does
  not change that.

Opting out is explicit and loud: ``OCBRAIN_API_AUTH=disabled`` or
``global.api_auth = "disabled"``.  Any other value, including a typo, resolves to
"required".
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, MutableMapping, Optional

log = logging.getLogger(__name__)

MODE_REQUIRED = "required"
MODE_DISABLED = "disabled"

ENV_MODE = "OCBRAIN_API_AUTH"
ENV_TOKEN = "OCBRAIN_API_TOKEN"
ENV_TOKEN_FILE = "OCBRAIN_API_TOKEN_FILE"

MIN_TOKEN_LENGTH = 32
DEFAULT_TOKEN_PATH = Path(__file__).resolve().parent.parent / "data" / "api_token"

# ── Public allowlist ─────────────────────────────────────────────────────────
# Deny by default.  Everything not listed here needs the bearer token.
# Only GET/HEAD may be public.  What is public, and why:
#   "/"        the static HTML shell (no data; the page then authenticates its calls)
#   "/static/" static assets (settings page, auth.js, icons)
#   docs trio  the OpenAPI schema and its UI: schema only, no runtime data.  A
#              browser navigation cannot send an Authorization header, so
#              protecting these would make them unusable; the schema declares the
#              bearer scheme so "Try it out" works after "Authorize".
PUBLIC_METHODS = frozenset({"GET", "HEAD"})
PUBLIC_EXACT_PATHS = frozenset({
    "/", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect",
})
PUBLIC_PATH_PREFIXES = ("/static/",)

# Denial reason codes (what is logged and emitted; the HTTP body is always generic).
REASON_MISSING = "missing"
REASON_MALFORMED = "malformed"
REASON_AMBIGUOUS = "ambiguous"
REASON_INVALID = "invalid"

EVENT_DENIED = "api.auth_denied"
EVENT_DISABLED = "api.auth_disabled"


class AuthConfigError(RuntimeError):
    """The authentication configuration is unusable.  Callers must fail closed."""


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    token: Optional[bytes]  # None only when mode == MODE_DISABLED


# ── Mode and token resolution ────────────────────────────────────────────────

def resolve_mode(configured: Optional[Any] = None) -> str:
    """Environment overrides config; only the exact value 'disabled' disables."""
    raw = os.environ.get(ENV_MODE)
    if raw is None:
        raw = configured
    if raw is None:
        return MODE_REQUIRED
    value = str(raw).strip().lower()
    if value == MODE_DISABLED:
        return MODE_DISABLED
    if value != MODE_REQUIRED:
        log.warning("Unrecognised API auth mode %r; failing closed to %r.", value[:32], MODE_REQUIRED)
    return MODE_REQUIRED


def token_path() -> Path:
    override = os.environ.get(ENV_TOKEN_FILE)
    return Path(override) if override else DEFAULT_TOKEN_PATH


def _validate_token(value: str, source: str) -> str:
    value = value.strip()
    if len(value) < MIN_TOKEN_LENGTH:
        raise AuthConfigError(
            f"API token from {source} is shorter than {MIN_TOKEN_LENGTH} characters; "
            "refusing to use it. Delete the file (or unset the variable) to generate a new one."
        )
    return value


def _enforce_private_mode(path: Path) -> None:
    """POSIX: the token file must not be readable by group/other."""
    if os.name == "nt":  # no POSIX modes; documented residual limitation
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        try:
            os.chmod(path, 0o600)
        except OSError as exc:
            raise AuthConfigError(
                f"API token file {path} is accessible to other users (mode {oct(mode)}) "
                f"and could not be tightened: {type(exc).__name__}"
            ) from exc
        log.warning("API token file %s was mode %s; tightened to 0600.", path, oct(mode))


def read_token() -> Optional[str]:
    """Client-side lookup (CLI, tray): env, else an existing file.  Never creates one."""
    env = os.environ.get(ENV_TOKEN)
    if env is not None and env.strip():
        return env.strip()
    path = token_path()
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def load_or_create_token() -> str:
    """Server-side: env var, else the token file (created 0600 on first use)."""
    env = os.environ.get(ENV_TOKEN)
    if env is not None:
        return _validate_token(env, f"the {ENV_TOKEN} environment variable")

    path = token_path()
    if path.exists():
        _enforce_private_mode(path)
        return _validate_token(path.read_text(encoding="utf-8"), f"the token file {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:  # lost a creation race: use the winner's token
        _enforce_private_mode(path)
        return _validate_token(path.read_text(encoding="utf-8"), f"the token file {path}")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    log.info("Generated a new API token and stored it at %s (mode 0600).", path)
    return token


_cached: Optional[AuthSettings] = None
_disabled_announced = False


def get_settings(configured_mode: Optional[Any] = None) -> AuthSettings:
    """Resolve (and cache) the settings.  Raises AuthConfigError when unusable."""
    global _cached, _disabled_announced
    mode = resolve_mode(configured_mode)
    if _cached is not None and _cached.mode == mode:
        return _cached
    if mode == MODE_DISABLED:
        settings = AuthSettings(mode=mode, token=None)
        if not _disabled_announced:
            _disabled_announced = True
            log.warning(
                "API AUTHENTICATION IS DISABLED (%s / global.api_auth). Every endpoint, including "
                "config writes, updates, import/export and /query, is open to anything that can "
                "reach the port.", ENV_MODE,
            )
            _emit(EVENT_DISABLED, {"mode": mode})
    else:
        settings = AuthSettings(mode=mode, token=load_or_create_token().encode("utf-8"))
    _cached = settings
    return settings


def reset_cache_for_tests() -> None:
    global _cached, _disabled_announced
    _cached = None
    _disabled_announced = False


# ── Auditing ─────────────────────────────────────────────────────────────────

def _emit(event: str, payload: dict) -> None:
    """Fire-and-forget audit event.  Never raises into the request path."""
    try:
        from core.event_bus import bus  # lazy: clients importing this module stay light
        bus.emit_sync(event, dict(payload))
    except Exception:  # pragma: no cover - audit must not break the boundary
        log.exception("Could not emit %s", event)


def _safe_path(path: str) -> str:
    return ascii(path[:200])


def _audit_denied(reason: str, scope: MutableMapping[str, Any]) -> None:
    method = str(scope.get("method", "WS" if scope.get("type") == "websocket" else "?"))
    path = _safe_path(str(scope.get("path", "")))
    client = scope.get("client")
    host = ascii(str(client[0])) if client else "unknown"
    log.warning("api.auth_denied reason=%s method=%s path=%s client=%s", reason, method, path, host)
    _emit(EVENT_DENIED, {"reason": reason, "method": method, "path": path, "client": host})


# ── Middleware ───────────────────────────────────────────────────────────────

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]


def is_public(method: str, path: str,
              exact: Iterable[str] = PUBLIC_EXACT_PATHS,
              prefixes: Iterable[str] = PUBLIC_PATH_PREFIXES) -> bool:
    if method not in PUBLIC_METHODS:
        return False
    return path in exact or any(path.startswith(p) for p in prefixes)


def _extract_bearer(scope: Scope) -> tuple[Optional[bytes], Optional[str]]:
    """Return (credential, None) or (None, reason)."""
    values = [v for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
    if not values:
        return None, REASON_MISSING
    if len(values) > 1:
        return None, REASON_AMBIGUOUS
    scheme, _, credential = values[0].strip().partition(b" ")
    credential = credential.strip()
    if scheme.lower() != b"bearer" or not credential:
        return None, REASON_MALFORMED
    return credential, None


class ApiAuthMiddleware:
    """Pure-ASGI bearer-token gate.  Add it LAST so it is the outermost middleware."""

    def __init__(self, app: Callable[..., Awaitable[None]],
                 settings_provider: Callable[[], AuthSettings] = get_settings) -> None:
        self.app = app
        self._settings_provider = settings_provider

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):  # lifespan etc.
            await self.app(scope, receive, send)
            return

        try:
            settings = self._settings_provider()
        except AuthConfigError:
            log.exception("API authentication is misconfigured; refusing the request.")
            await self._reject(scope, send, 503, "API authentication is misconfigured")
            return

        if settings.mode == MODE_DISABLED:
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http" and is_public(scope.get("method", ""), scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        credential, reason = _extract_bearer(scope)
        if credential is None:
            _audit_denied(reason or REASON_MALFORMED, scope)
            await self._reject(scope, send, 401, "Authentication required")
            return
        if settings.token is None or not hmac.compare_digest(credential, settings.token):
            _audit_denied(REASON_INVALID, scope)
            await self._reject(scope, send, 401, "Authentication required")
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, send: Send, status: int, detail: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"detail": detail}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
