"""DEBT-025: the HTTP API authentication boundary (interface/auth.py).

What is proven here, and what is not:
* Proven: every route registered on the real app, and on the /brain/v2 router, is
  rejected without a bearer token unless it is in the explicit public allowlist;
  the allowlist itself is pinned; token comparison, parsing, provisioning, failure
  modes, auditing (and secrecy of the credential) and the clients' use of the token.
* Not proven: that an authenticated caller is authorised for an action (the
  control-plane endpoints remain outside GovernanceKernel), nor anything about an
  attacker who can already read the token file as the same user.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import stat
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from interface import auth
from interface.api import app

TOKEN = "unit-test-token-" + "a1b2c3d4" * 4          # 47 chars, >= MIN_TOKEN_LENGTH
WRONG = "unit-test-token-" + "z9y8x7w6" * 4          # same length, different value
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def required(monkeypatch, tmp_path):
    """Auth required, with a known token (overrides the suite-wide opt-out)."""
    monkeypatch.delenv(auth.ENV_MODE, raising=False)
    monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
    monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "api_token"))
    auth.reset_cache_for_tests()
    yield TOKEN
    auth.reset_cache_for_tests()


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(auth, "_emit", lambda event, payload: seen.append((event, dict(payload))))
    return seen


def _scope(method: str, path: str, headers=(), type_: str = "http", root_path: str = "",
           host: str | None = "localhost:7437") -> dict:
    """host=None omits the Host header; a Host entry in `headers` overrides the default."""
    hdrs = [(k.lower().encode(), v.encode()) for k, v in headers]
    if host is not None and not any(k == b"host" for k, _ in hdrs):
        hdrs.append((b"host", host.encode()))
    return {
        "type": type_, "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": root_path,
        "scheme": "http", "server": ("127.0.0.1", 7437), "client": ("127.0.0.1", 50000),
        "headers": hdrs,
    }


def call(target, method: str, path: str, headers=(), **scope_kw) -> tuple[int, bytes, dict]:
    """Drive an ASGI app directly (no URL normalisation, exact path preserved).

    Behaves like a real server: the request is delivered once, and the client
    "disconnects" only after the response is complete.  (Replaying `http.request`
    forever, or disconnecting early, breaks Starlette's BaseHTTPMiddleware on
    older versions: it either raises or cancels the response body.)
    """
    sent: list[dict] = []

    async def run() -> None:
        finished = asyncio.Event()
        delivered: list[int] = []

        async def receive():
            if not delivered:
                delivered.append(1)
                return {"type": "http.request", "body": b"", "more_body": False}
            await finished.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                finished.set()

        await target(_scope(method, path, headers, **scope_kw), receive, send)

    asyncio.run(run())
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    hdrs = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    return start["status"], body, hdrs


def bearer(token: str) -> list[tuple[str, str]]:
    return [("Authorization", f"Bearer {token}")]


# ── The boundary covers every route ──────────────────────────────────────────

def _routes_of(a: FastAPI) -> list[tuple[str, str]]:
    """Every (METHOD, path) the app serves.

    Union of the flat route table and the OpenAPI schema: newer FastAPI wraps an
    included router in a single opaque route object (no ``path``), so the flat
    table alone would silently miss the whole /brain/v2 router there.
    """
    found: set[tuple[str, str]] = set()
    for r in a.routes:
        path = getattr(r, "path", None)
        if path is None:
            continue
        for m in (getattr(r, "methods", None) or set()) - {"HEAD"}:
            found.add((m, path))
    for path, item in a.openapi().get("paths", {}).items():
        for m in item:
            if m.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
                found.add((m.upper(), path))
    return sorted((m, p.replace("{", "x").replace("}", "")) for m, p in found)


class TestEveryRouteIsProtected:
    def test_middleware_is_outermost_on_the_real_app(self):
        assert app.user_middleware[0].cls is auth.ApiAuthMiddleware

    def test_public_allowlist_is_pinned(self):
        # Growing the allowlist must be a deliberate, reviewed edit to this test.
        assert auth.PUBLIC_METHODS == {"GET", "HEAD"}
        assert auth.PUBLIC_EXACT_PATHS == {"/"}
        assert auth.PUBLIC_PATH_PREFIXES == ("/static/",)

    def test_all_registered_routes_reject_missing_token(self, required):
        routes = _routes_of(app)
        assert len(routes) >= 20, routes  # guards against the inventory silently emptying
        failures = []
        for method, path in routes:
            if auth.is_public(method, path):
                continue
            status, _, _ = call(app, method, path)
            if status != 401:
                failures.append((method, path, status))
        assert failures == []

    def test_brain_v2_router_routes_reject_missing_token(self, required):
        from core.brain_api import register
        fresh = FastAPI()
        register(fresh, {})
        fresh.add_middleware(auth.ApiAuthMiddleware, settings_provider=auth.get_settings)
        routes = [(m, p) for m, p in _routes_of(fresh) if p.startswith("/brain/v2")]
        assert len(routes) >= 5, routes
        for method, path in routes:
            assert call(fresh, method, path)[0] == 401, (method, path)

    def test_unknown_paths_are_401_not_404(self, required):
        # No route-existence oracle for unauthenticated callers.
        assert call(app, "GET", "/definitely/not/a/route")[0] == 401
        assert call(app, "POST", "//config")[0] == 401

    def test_auth_precedes_csrf(self, required):
        assert call(app, "POST", "/query")[0] == 401            # not 403

    def test_csrf_still_enforced_after_auth(self, required):
        status, _, _ = call(app, "POST", "/config", bearer(TOKEN))
        assert status == 403

    def test_static_prefix_cannot_be_used_to_reach_other_routes(self, required):
        status, body, _ = call(app, "GET", "/static/../config")
        assert status != 200
        assert b"ollama_host" not in body


class TestPublicSurface:
    @pytest.mark.parametrize("method,path,expected", [
        ("GET", "/", True), ("HEAD", "/", True), ("POST", "/", False),
        ("GET", "/static/auth.js", True), ("GET", "/static", False), ("GET", "/staticx/a", False),
        ("GET", "/docs", False), ("GET", "/docs/", False), ("GET", "/openapi.json", False), ("GET", "/redoc", False),
        ("GET", "/config", False), ("GET", "/health", False), ("PUT", "/static/x", False),
        ("OPTIONS", "/", False),
    ])
    def test_is_public(self, method, path, expected):
        assert auth.is_public(method, path) is expected

    def test_shell_needs_no_token(self, required):
        assert call(app, "GET", "/")[0] == 200

    def test_interactive_docs_are_disabled_and_the_schema_needs_the_token(self, required):
        # /docs and /redoc load third-party scripts from a CDN into the UI's origin: disabled.
        for path in ("/docs", "/redoc", "/docs/oauth2-redirect", "/openapi.json"):
            assert call(app, "GET", path)[0] == 401, path
        for path in ("/docs", "/redoc"):
            assert call(app, "GET", path, bearer(TOKEN))[0] == 404, path
        status, body, _ = call(app, "GET", "/openapi.json", bearer(TOKEN))
        assert status == 200
        schema = json.loads(body)
        assert schema["components"]["securitySchemes"]["bearerAuth"] == {"type": "http", "scheme": "bearer"}
        assert schema["security"] == [{"bearerAuth": []}]

    def test_options_preflight_is_not_exempt(self, required):
        assert call(app, "OPTIONS", "/query")[0] == 401


# ── Credential handling ──────────────────────────────────────────────────────

class TestCredentialChecks:
    def test_valid_token_is_accepted(self, required):
        status, body, _ = call(app, "GET", "/config", bearer(TOKEN))
        assert status == 200
        assert b"global" in body

    def test_scheme_is_case_insensitive(self, required):
        assert call(app, "GET", "/config", [("Authorization", f"bearer {TOKEN}")])[0] == 200

    @pytest.mark.parametrize("header,reason", [
        (None, auth.REASON_MISSING),
        ("Bearer", auth.REASON_MALFORMED),
        ("Bearer ", auth.REASON_MALFORMED),
        (f"Basic {TOKEN}", auth.REASON_MALFORMED),
        (TOKEN, auth.REASON_MALFORMED),
        (f"Bearer {WRONG}", auth.REASON_INVALID),
        (f"Bearer {TOKEN[:-1]}", auth.REASON_INVALID),
        (f"Bearer {TOKEN}x", auth.REASON_INVALID),
        (f"Bearer {TOKEN.upper()}", auth.REASON_INVALID),
        ("Bearer x", auth.REASON_INVALID),
    ])
    def test_rejections_carry_the_right_reason(self, required, events, header, reason):
        headers = [] if header is None else [("Authorization", header)]
        status, body, hdrs = call(app, "GET", "/config", headers)
        assert status == 401
        assert json.loads(body) == {"detail": "Authentication required"}   # generic: no oracle
        assert hdrs["www-authenticate"] == "Bearer"
        assert hdrs["cache-control"] == "no-store"
        assert [e[1]["reason"] for e in events if e[0] == auth.EVENT_DENIED] == [reason]

    def test_two_authorization_headers_are_rejected(self, required, events):
        status, _, _ = call(app, "GET", "/config", bearer(TOKEN) + bearer(TOKEN))
        assert status == 401
        assert events[0][1]["reason"] == auth.REASON_AMBIGUOUS

    def test_comparison_is_constant_time_primitive(self, required, monkeypatch):
        real = auth.hmac.compare_digest
        calls = []
        monkeypatch.setattr(auth.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or real(a, b))
        call(app, "GET", "/config", bearer(WRONG))
        assert calls == [(WRONG.encode(), TOKEN.encode())]


# ── Audit trail, and the credential never leaks into it ──────────────────────

class TestAudit:
    def test_denial_is_logged_and_emitted_without_the_credential(self, required, events, caplog):
        secret = "SUPER-SECRET-ATTEMPT-" + "q" * 30
        with caplog.at_level(logging.INFO):
            call(app, "GET", "/config", bearer(secret))
        assert events == [(auth.EVENT_DENIED, {
            "reason": auth.REASON_INVALID, "method": "GET", "path": "'/config'", "client": "'127.0.0.1'",
        })]
        assert secret not in caplog.text
        assert secret not in json.dumps(events)
        assert TOKEN not in caplog.text and TOKEN not in json.dumps(events)

    def test_attacker_controlled_path_cannot_inject_log_lines(self, required, events, caplog):
        with caplog.at_level(logging.INFO):
            call(app, "GET", "/x\nFORGED api.auth_allowed")
        assert all("\n" not in r.getMessage() for r in caplog.records)
        assert "\n" not in events[0][1]["path"]

    def test_successful_requests_are_not_evented(self, required, events):
        call(app, "GET", "/config", bearer(TOKEN))
        assert events == []

    def test_auth_events_are_in_the_event_catalogue(self):
        from core.event_bus import EVENTS
        assert {auth.EVENT_DENIED, auth.EVENT_DISABLED} <= EVENTS


# ── Mode resolution: opting out is explicit, everything else is closed ───────

class TestMode:
    @pytest.mark.parametrize("value", ["off", "false", "0", "no", "disable", "disabled!", "", "none", "required"])
    def test_anything_but_disabled_stays_required(self, monkeypatch, value):
        monkeypatch.setenv(auth.ENV_MODE, value)
        assert auth.resolve_mode(None) == auth.MODE_REQUIRED

    @pytest.mark.parametrize("value", ["disabled", "DISABLED", "  Disabled  "])
    def test_only_the_word_disabled_disables(self, monkeypatch, value):
        monkeypatch.setenv(auth.ENV_MODE, value)
        assert auth.resolve_mode(None) == auth.MODE_DISABLED

    def test_default_is_required(self, monkeypatch):
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        assert auth.resolve_mode(None) == auth.MODE_REQUIRED

    def test_config_value_is_honoured_and_env_overrides_it(self, monkeypatch):
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        assert auth.resolve_mode("disabled") == auth.MODE_DISABLED
        monkeypatch.setenv(auth.ENV_MODE, "required")
        assert auth.resolve_mode("disabled") == auth.MODE_REQUIRED

    def test_disabled_lets_requests_through_and_says_so(self, monkeypatch, events, caplog):
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        auth.reset_cache_for_tests()
        with caplog.at_level(logging.WARNING):
            assert call(app, "GET", "/config")[0] == 200
            assert call(app, "GET", "/config")[0] == 200
        assert "AUTHENTICATION IS DISABLED" in caplog.text
        assert [e[0] for e in events] == [auth.EVENT_DISABLED]          # announced once

    def test_unusable_configuration_fails_closed_with_503(self, monkeypatch, events):
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN, "short")
        auth.reset_cache_for_tests()
        status, body, _ = call(app, "GET", "/config", bearer("short"))
        assert status == 503
        assert b"short" not in body


# ── Token provisioning ───────────────────────────────────────────────────────

class TestTokenProvisioning:
    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch, tmp_path):
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "data" / "api_token"))
        auth.reset_cache_for_tests()

    def test_first_start_creates_a_private_strong_token(self, tmp_path):
        token = auth.load_or_create_token()
        path = tmp_path / "data" / "api_token"
        assert len(token) >= auth.MIN_TOKEN_LENGTH
        assert path.read_text().strip() == token
        if os.name != "nt":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_token_is_stable_across_loads(self):
        assert auth.load_or_create_token() == auth.load_or_create_token()

    def test_tokens_differ_between_installations(self, tmp_path, monkeypatch):
        first = auth.load_or_create_token()
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "other"))
        assert auth.load_or_create_token() != first

    def test_environment_token_wins_over_the_file(self, monkeypatch):
        auth.load_or_create_token()
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        assert auth.load_or_create_token() == TOKEN

    def test_short_environment_token_is_refused(self, monkeypatch):
        monkeypatch.setenv(auth.ENV_TOKEN, "short")
        with pytest.raises(auth.AuthConfigError):
            auth.load_or_create_token()

    def test_short_file_is_refused_and_not_overwritten(self, tmp_path):
        path = tmp_path / "data" / "api_token"
        path.parent.mkdir()
        path.write_text("tiny\n")
        with pytest.raises(auth.AuthConfigError):
            auth.load_or_create_token()
        assert path.read_text() == "tiny\n"

    @pytest.mark.skipif(os.name == "nt", reason="POSIX modes only")
    def test_world_readable_file_is_tightened(self, tmp_path):
        path = tmp_path / "data" / "api_token"
        path.parent.mkdir()
        path.write_text(TOKEN + "\n")
        os.chmod(path, 0o644)
        assert auth.load_or_create_token() == TOKEN
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_client_lookup_never_creates_the_file(self, tmp_path, monkeypatch):
        assert auth.read_token() is None
        assert not (tmp_path / "data" / "api_token").exists()
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        assert auth.read_token() == TOKEN

    def test_token_path_that_is_a_directory_fails_closed_and_is_not_chmodded(self, tmp_path, monkeypatch):
        d = tmp_path / "isdir"
        d.mkdir()
        os.chmod(d, 0o755)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(d))
        with pytest.raises(auth.AuthConfigError):
            auth.load_or_create_token()
        if os.name != "nt":
            assert stat.S_IMODE(d.stat().st_mode) == 0o755

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
    def test_dangling_symlink_fails_closed(self, tmp_path, monkeypatch):
        link = tmp_path / "dangling"
        link.symlink_to(tmp_path / "nowhere")
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(link))
        with pytest.raises(auth.AuthConfigError):
            auth.load_or_create_token()

    @pytest.mark.parametrize("kind", ["dir", "dangling"])
    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
    def test_unusable_token_file_gives_503_not_500(self, tmp_path, monkeypatch, kind):
        p = tmp_path / "t"
        if kind == "dir":
            p.mkdir()
        else:
            p.symlink_to(tmp_path / "nowhere")
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(p))
        auth.reset_cache_for_tests()
        assert call(app, "GET", "/config")[0] == 503

    def test_unreadable_token_file_fails_closed(self, tmp_path, monkeypatch):
        path = tmp_path / "data" / "api_token"
        path.parent.mkdir()
        path.write_text(TOKEN + "\n")
        os.chmod(path, 0o600)
        real = Path.read_text

        def deny(self, *args, **kwargs):
            if self == path:
                raise PermissionError("denied")
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", deny)   # root bypasses chmod, so simulate the denial
        with pytest.raises(auth.AuthConfigError):
            auth.load_or_create_token()

    def test_token_file_is_git_ignored(self):
        proc = subprocess.run(["git", "check-ignore", "-q", "data/api_token"], cwd=REPO_ROOT)
        assert proc.returncode == 0


# ── Middleware mechanics ─────────────────────────────────────────────────────

def _settings(token: bytes = TOKEN.encode()):
    return lambda: auth.AuthSettings(mode=auth.MODE_REQUIRED, token=token)


class TestMiddlewareMechanics:
    def test_streaming_responses_pass_through_unmodified_and_in_order(self):
        chunks = [b"data: 1\n\n", b"data: 2\n\n", b"data: 3\n\n"]

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"text/event-stream")]})
            for i, c in enumerate(chunks):
                await send({"type": "http.response.body", "body": c, "more_body": i < len(chunks) - 1})

        status, body, hdrs = call(auth.ApiAuthMiddleware(downstream, _settings()), "GET", "/events", bearer(TOKEN))
        assert (status, body) == (200, b"".join(chunks))
        assert hdrs["content-type"] == "text/event-stream"

    def test_rejected_request_never_reaches_the_app(self):
        reached = []

        async def downstream(scope, receive, send):
            reached.append(scope["path"])

        mw = auth.ApiAuthMiddleware(downstream, _settings())
        assert call(mw, "GET", "/config")[0] == 401
        assert reached == []

    def test_websocket_without_token_is_closed_with_policy_violation(self):
        sent, reached = [], []

        async def downstream(scope, receive, send):
            reached.append(1)

        async def receive():
            return {"type": "websocket.connect"}

        async def send(m):
            sent.append(m)

        mw = auth.ApiAuthMiddleware(downstream, _settings())
        asyncio.run(mw(_scope("GET", "/ws", type_="websocket"), receive, send))
        assert sent == [{"type": "websocket.close", "code": 1008}]
        assert reached == []

    def test_lifespan_scope_is_not_gated(self):
        reached = []

        async def downstream(scope, receive, send):
            reached.append(scope["type"])

        def boom():
            raise AssertionError("settings must not be resolved for lifespan")

        mw = auth.ApiAuthMiddleware(downstream, boom)
        asyncio.run(mw({"type": "lifespan"}, None, None))
        assert reached == ["lifespan"]


# ── Wire-level smoke test against a real listening server ────────────────────

class TestRealServer:
    def test_401_without_token_and_200_with_token_over_a_real_socket(self, required):
        import uvicorn
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", loop="asyncio"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.time() + 15
            while not server.started and time.time() < deadline:
                time.sleep(0.05)
            assert server.started, "server did not start"
            port = server.servers[0].sockets[0].getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            r = httpx.get(f"{base}/config", timeout=10)
            assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
            assert httpx.get(f"{base}/config", headers={"Authorization": f"Bearer {WRONG}"}, timeout=10).status_code == 401
            assert httpx.get(f"{base}/config", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10).status_code == 200
            assert httpx.get(f"{base}/", timeout=10).status_code == 200
        finally:
            server.should_exit = True
            thread.join(timeout=10)


# ── Clients: CLI, tray launcher, web UI ──────────────────────────────────────

class TestClients:
    def test_cli_sends_the_token(self, monkeypatch):
        from interface import cli
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        assert cli._auth_headers() == {"Authorization": f"Bearer {TOKEN}"}

    def test_cli_sends_no_header_when_there_is_no_token(self, monkeypatch, tmp_path):
        from interface import cli
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "absent"))
        assert cli._auth_headers() == {}

    def test_cli_turns_401_into_an_actionable_exit(self, monkeypatch):
        from interface import cli
        with pytest.raises(SystemExit) as exc:
            cli._check(httpx.Response(401, request=httpx.Request("GET", "http://x/")))
        assert exc.value.code == 1

    def test_tray_url_never_carries_the_token(self, monkeypatch):
        # The URL goes to the browser launcher's command line, readable by every local user.
        from interface import tray
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        for path in ("", "/static/settings.html"):
            url = tray._ui_url(path)
            assert url == f"http://localhost:{tray.PORT}{path}"
            assert TOKEN not in url and "token" not in url.lower()

    def test_tray_opens_the_browser_with_a_token_free_url(self, monkeypatch):
        from interface import tray
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        opened = []
        monkeypatch.setattr(tray.webbrowser, "open", lambda url, *a, **k: opened.append(url))
        tray._open_ui(None, None)
        tray._open_settings(None, None)
        assert len(opened) == 2 and all(TOKEN not in u for u in opened)

    def test_tray_url_uses_the_configured_port_not_a_hardcoded_one(self, monkeypatch):
        from interface import tray
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        monkeypatch.setattr(tray.config, "get", lambda key, default=None: 8123 if key == "global.web_ui_port" else default)
        assert tray._ui_url() == "http://localhost:8123"
        monkeypatch.setattr(tray.config, "get", lambda key, default=None: "not-a-port")
        assert tray._ui_url() == f"http://localhost:{tray.PORT}"

    @pytest.mark.parametrize("page", ["index.html", "settings.html"])
    def test_web_pages_use_the_authenticating_helpers(self, page):
        html = (REPO_ROOT / "interface" / "web" / page).read_text(encoding="utf-8")
        import re
        assert not re.search(r"(?<![A-Za-z_.])fetch\(", html), "bare fetch() would be unauthenticated"
        assert "EventSource" not in html, "EventSource cannot send an Authorization header"
        assert html.index('src="/static/auth.js"') < html.index("<script>")

    def test_auth_js_defines_the_helpers_and_keeps_the_token_out_of_persistent_storage(self):
        js = (REPO_ROOT / "interface" / "web" / "auth.js").read_text(encoding="utf-8")
        assert "window.ocFetch" in js and "window.ocEventStream" in js
        assert "sessionStorage" in js and "localStorage" not in js


# ═════════════════════════════════════════════════════════════════════════════
# Remediation round (PR #94 review): Host allowlist, root-path, opt-out transitions,
# rotation, frozen-build token location, Windows ACL logic, throttling, symlinks,
# security headers, CLI token command, and the launcher-argv leak.
# ═════════════════════════════════════════════════════════════════════════════

import sys  # noqa: E402


class TestHostAllowlist:
    """DNS rebinding: after rebinding, the Host header names the attacker's domain."""

    @pytest.mark.parametrize("value,expected", [
        ("localhost:7437", "localhost"), ("LOCALHOST", "localhost"), ("localhost.", "localhost"),
        ("127.0.0.1:7437", "127.0.0.1"), ("[::1]:7437", "::1"), ("[::1]", "::1"),
        ("evil.example:7437", "evil.example"), ("localhost:abc", None), ("", None), ("[::1", None),
        ("a:b:c", "a:b:c"),
    ])
    def test_hostname_parsing(self, value, expected):
        assert auth._hostname(value) == expected

    @pytest.mark.parametrize("host", ["localhost:7437", "localhost:9999", "127.0.0.1", "[::1]:7437", "LocalHost"])
    def test_loopback_names_are_accepted_whatever_the_port(self, required, host):
        assert call(app, "GET", "/config", bearer(TOKEN), host=host)[0] == 200

    @pytest.mark.parametrize("host", ["evil.example:7437", "localhost.evil.example", "127.0.0.1.evil.example", "192.168.1.5:7437"])
    def test_other_names_are_refused_even_with_a_valid_token(self, required, events, host):
        status, body, _ = call(app, "GET", "/config", bearer(TOKEN), host=host)
        assert status == 400 and json.loads(body) == {"detail": "Invalid host header"}
        assert events[0][1]["reason"] == auth.REASON_HOST
        assert events[0][1]["host"] == ascii(host)

    def test_the_public_shell_is_covered_too(self, required):
        assert call(app, "GET", "/", host="evil.example:7437")[0] == 400
        assert call(app, "GET", "/static/auth.js", host="evil.example:7437")[0] == 400

    def test_missing_or_duplicate_host_is_refused(self, required):
        assert call(app, "GET", "/", host=None)[0] == 400
        assert call(app, "GET", "/", [("Host", "localhost"), ("Host", "localhost")], host=None)[0] == 400

    def test_configured_names_are_accepted(self, required, monkeypatch):
        assert call(app, "GET", "/", host="ocb.example.com")[0] == 400
        monkeypatch.setenv(auth.ENV_ALLOWED_HOSTS, "ocb.example.com, 10.0.0.5:7437")
        assert call(app, "GET", "/", host="ocb.example.com")[0] == 200
        assert call(app, "GET", "/", host="10.0.0.5")[0] == 200
        assert call(app, "GET", "/", host="other.example.com")[0] == 400
        assert auth.allowed_hosts(["a.example", "B.example:80"]) >= {"a.example", "b.example"}

    def test_websockets_are_covered(self, required):
        sent = []

        async def receive():
            return {"type": "websocket.connect"}

        async def send(m):
            sent.append(m)

        mw = auth.ApiAuthMiddleware(lambda *a: None, lambda: auth.AuthSettings(auth.MODE_REQUIRED, TOKEN.encode()))
        scope = _scope("GET", "/ws", bearer(TOKEN), type_="websocket", host="evil.example")
        asyncio.run(mw(scope, receive, send))
        assert sent == [{"type": "websocket.close", "code": 1008}]

    def test_the_explicit_opt_out_keeps_the_previous_behaviour(self, monkeypatch):
        # Documented: Host validation belongs to required mode.  The opt-out is the owner's explicit choice.
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        auth.reset_cache_for_tests()
        assert call(app, "GET", "/config", host="evil.example")[0] == 200


class TestRootPathConsistency:
    """Behind a path-prefix proxy (uvicorn --root-path) the allowlist must see the router's path."""

    @pytest.mark.parametrize("path,root,expected", [
        ("/ocb/", "/ocb", "/"), ("/ocb/static/a.js", "/ocb", "/static/a.js"), ("/ocb/config", "/ocb", "/config"),
        ("/ocb", "/ocb", ""), ("/ocbx/config", "/ocb", "/ocbx/config"), ("/config", "", "/config"),
        ("/x/config", "/ocb", "/x/config"),
    ])
    def test_route_path_matches_starlettes_rule(self, path, root, expected):
        assert auth.route_path({"path": path, "root_path": root}) == expected

    def test_the_shell_stays_public_and_everything_else_protected_under_a_prefix(self, required):
        assert call(app, "GET", "/ocb/", root_path="/ocb")[0] == 200
        assert call(app, "GET", "/ocb/static/auth.js", root_path="/ocb")[0] == 200
        assert call(app, "GET", "/ocb/config", root_path="/ocb")[0] == 401
        assert call(app, "GET", "/ocb/config", bearer(TOKEN), root_path="/ocb")[0] == 200

    def test_a_prefix_cannot_make_a_protected_path_look_public(self, required):
        assert call(app, "GET", "/static/../config", root_path="/static")[0] == 401


class TestOptOutTransitions:
    """Every change of the opt-out is auditable, in both directions, not only the first."""

    def test_disable_enable_disable_is_logged_and_emitted_each_time(self, monkeypatch, events, caplog):
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        auth.reset_cache_for_tests()
        with caplog.at_level(logging.WARNING):
            auth.get_settings(None)                                   # required at start: nothing to announce
            monkeypatch.setenv(auth.ENV_MODE, "disabled"); auth.get_settings(None)
            monkeypatch.setenv(auth.ENV_MODE, "required"); auth.get_settings(None)
            monkeypatch.setenv(auth.ENV_MODE, "disabled"); auth.get_settings(None)
            auth.get_settings(None)                                   # unchanged: silent
        assert [(e[0], e[1]["previous"]) for e in events] == [
            (auth.EVENT_DISABLED, auth.MODE_REQUIRED), (auth.EVENT_ENABLED, auth.MODE_DISABLED), (auth.EVENT_DISABLED, auth.MODE_REQUIRED)]
        assert caplog.text.count("AUTHENTICATION IS DISABLED") == 2
        assert caplog.text.count("REQUIRED again") == 1

    def test_starting_disabled_is_announced_once(self, monkeypatch, events):
        monkeypatch.setenv(auth.ENV_MODE, "disabled")
        auth.reset_cache_for_tests()
        auth.get_settings(None); auth.get_settings(None)
        assert [e[0] for e in events] == [auth.EVENT_DISABLED]

    def test_a_config_value_flip_at_runtime_is_seen_and_audited(self, monkeypatch, events):
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        auth.reset_cache_for_tests()
        assert auth.get_settings("required").mode == auth.MODE_REQUIRED
        assert auth.get_settings("disabled").mode == auth.MODE_DISABLED
        assert auth.get_settings("required").mode == auth.MODE_REQUIRED
        assert [e[0] for e in events] == [auth.EVENT_DISABLED, auth.EVENT_ENABLED]

    def test_enabled_event_is_in_the_catalogue(self):
        from core.event_bus import EVENTS
        assert auth.EVENT_ENABLED in EVENTS


class TestRotationAndRevocation:
    @pytest.fixture
    def file_token(self, monkeypatch, tmp_path):
        monkeypatch.delenv(auth.ENV_MODE, raising=False)
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        path = tmp_path / "data" / "api_token"
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(path))
        auth.reset_cache_for_tests()
        assert call(app, "GET", "/config")[0] == 401           # provisions the file
        return path

    def test_rotating_revokes_the_old_token_without_a_restart(self, file_token):
        old = file_token.read_text().strip()
        assert call(app, "GET", "/config", bearer(old))[0] == 200
        new, path = auth.rotate_token()
        assert path == file_token and new != old and len(new) >= auth.MIN_TOKEN_LENGTH
        assert call(app, "GET", "/config", bearer(old))[0] == 401
        assert call(app, "GET", "/config", bearer(new))[0] == 200

    @pytest.mark.skipif(os.name == "nt", reason="POSIX modes")
    def test_rotation_keeps_the_file_private_and_leaves_no_temp_files(self, file_token):
        auth.rotate_token()
        assert stat.S_IMODE(file_token.stat().st_mode) == 0o600
        assert [p.name for p in file_token.parent.iterdir()] == ["api_token"]

    def test_deleting_the_file_revokes_the_old_token(self, file_token):
        old = file_token.read_text().strip()
        file_token.unlink()
        assert call(app, "GET", "/config", bearer(old))[0] == 401          # a fresh token was generated
        assert file_token.exists() and file_token.read_text().strip() != old

    def test_replacing_the_file_with_garbage_fails_closed(self, file_token):
        old = file_token.read_text().strip()
        file_token.write_text("short\n")
        assert call(app, "GET", "/config", bearer(old))[0] == 503
        assert call(app, "GET", "/config", bearer("short"))[0] == 503

    def test_an_unchanged_file_is_not_re_read(self, file_token, monkeypatch):
        calls = []
        real = auth._resolve_token
        monkeypatch.setattr(auth, "_resolve_token", lambda: calls.append(1) or real())
        tok = file_token.read_text().strip()
        for _ in range(5):
            assert call(app, "GET", "/config", bearer(tok))[0] == 200
        assert calls == []

    def test_an_environment_token_cannot_be_rotated_here(self, monkeypatch):
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        with pytest.raises(auth.AuthConfigError):
            auth.rotate_token()

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
    def test_a_symlinked_token_path_is_not_rotated(self, monkeypatch, tmp_path):
        real = tmp_path / "real"; real.write_text(TOKEN + "\n"); os.chmod(real, 0o600)
        link = tmp_path / "link"; link.symlink_to(real)
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(link))
        with pytest.raises(auth.AuthConfigError):
            auth.rotate_token()
        assert real.read_text().strip() == TOKEN


class TestFrozenBuildTokenLocation:
    """A PyInstaller --onefile build runs from a per-run temp directory: the token must not live there."""

    def test_source_checkout_keeps_data_dir(self):
        assert auth.default_token_path(frozen=False) == auth.DEFAULT_TOKEN_PATH

    def test_frozen_paths_per_platform(self):
        win = auth.default_token_path(frozen=True, platform="win32", env={"LOCALAPPDATA": r"C:\Users\u\AppData\Local"}, home=r"C:\Users\u")
        assert str(win) == r"C:\Users\u\AppData\Local\OCBrain\api_token"
        assert str(auth.default_token_path(frozen=True, platform="win32", env={}, home=r"C:\Users\u")) == r"C:\Users\u\AppData\Local\OCBrain\api_token"
        assert str(auth.default_token_path(frozen=True, platform="darwin", env={}, home="/Users/u")) == "/Users/u/Library/Application Support/OCBrain/api_token"
        assert str(auth.default_token_path(frozen=True, platform="linux", env={}, home="/home/u")) == "/home/u/.local/share/ocbrain/api_token"
        assert str(auth.default_token_path(frozen=True, platform="linux", env={"XDG_DATA_HOME": "/x/data"}, home="/home/u")) == "/x/data/ocbrain/api_token"

    def test_frozen_flag_selects_it_and_the_override_still_wins(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.delenv(auth.ENV_TOKEN_FILE, raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        if sys.platform.startswith("linux"):
            assert auth.token_path() == tmp_path / "ocbrain" / "api_token"
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "elsewhere"))
        assert auth.token_path() == tmp_path / "elsewhere"

    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="XDG layout")
    def test_frozen_start_creates_a_private_directory_and_a_stable_token(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.delenv(auth.ENV_TOKEN_FILE, raising=False)
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        first = auth.load_or_create_token()
        assert stat.S_IMODE((tmp_path / "ocbrain").stat().st_mode) == 0o700
        assert auth.load_or_create_token() == first


class TestWindowsAclLogic:
    """Logic only, with a stubbed icacls.  The real ACL is validated by the Windows CI job
    (scripts/check_token_acl_windows.py), not here: nothing in this class is Windows evidence."""

    SID = "S-1-5-21-111-222-333-1001"

    @pytest.fixture
    def win(self, monkeypatch, tmp_path):
        calls: list[list[str]] = []
        state = {"aces": 1, "icacls_rc": 0, "whoami": f'"HOST\\\\user","{self.SID}"'}

        def fake(args):
            calls.append(list(args))
            if args[0] == "whoami":
                return subprocess.CompletedProcess(args, 0, state["whoami"] + "\n", "")
            if len(args) == 2:  # icacls <file>: listing
                body = "".join(f"    HOST\\user:(F)\n" for _ in range(state["aces"]))
                return subprocess.CompletedProcess(args, 0, f"{args[1]} {body.strip()}\n\nSuccessfully processed 1 files\n", "")
            return subprocess.CompletedProcess(args, state["icacls_rc"], "", "")

        monkeypatch.setattr(auth, "_IS_WINDOWS", True)
        monkeypatch.setattr(auth, "_run_tool", fake)
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "api_token"))
        return calls, state

    def test_new_file_is_restricted_to_the_current_sid(self, win):
        calls, _ = win
        auth.load_or_create_token()
        grant = [c for c in calls if c[0] == "icacls" and "/grant:r" in c]
        assert grant and grant[0][2:] == ["/inheritance:r", "/grant:r", f"*{self.SID}:(F)"]

    def test_existing_file_is_re_restricted_on_every_load(self, win, tmp_path):
        calls, _ = win
        auth.load_or_create_token()
        n = sum(1 for c in calls if "/grant:r" in c)
        auth.load_or_create_token()
        assert sum(1 for c in calls if "/grant:r" in c) == n + 1

    def test_leftover_extra_entries_fail_closed(self, win):
        _, state = win
        state["aces"] = 3
        with pytest.raises(auth.AuthConfigError, match="3 access entries"):
            auth.load_or_create_token()

    def test_icacls_failure_fails_closed(self, win):
        _, state = win
        state["icacls_rc"] = 5
        with pytest.raises(auth.AuthConfigError, match="icacls exit 5"):
            auth.load_or_create_token()

    def test_unparseable_whoami_fails_closed(self, win):
        _, state = win
        state["whoami"] = "garbage"
        with pytest.raises(auth.AuthConfigError, match="SID"):
            auth.load_or_create_token()


class TestSymlinkedTokenFile:
    @pytest.fixture(autouse=True)
    def _skip_windows(self):
        if os.name == "nt":
            pytest.skip("symlinks need privileges on Windows")

    def test_a_symlink_to_a_loose_file_is_refused_and_the_target_untouched(self, monkeypatch, tmp_path):
        real = tmp_path / "real"; real.write_text(TOKEN + "\n"); os.chmod(real, 0o644)
        link = tmp_path / "link"; link.symlink_to(real)
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(link))
        with pytest.raises(auth.AuthConfigError, match="symlink"):
            auth.load_or_create_token()
        assert stat.S_IMODE(real.stat().st_mode) == 0o644

    def test_a_symlink_to_a_private_file_works(self, monkeypatch, tmp_path):
        real = tmp_path / "real"; real.write_text(TOKEN + "\n"); os.chmod(real, 0o600)
        link = tmp_path / "link"; link.symlink_to(real)
        monkeypatch.delenv(auth.ENV_TOKEN, raising=False)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(link))
        assert auth.load_or_create_token() == TOKEN


class TestDenialThrottle:
    def test_a_flood_is_rejected_in_full_but_logged_in_bounded_amount(self, required, events, caplog, monkeypatch):
        now = [1000.0]
        monkeypatch.setattr(auth, "_clock", lambda: now[0])
        with caplog.at_level(logging.WARNING):
            statuses = [call(app, "GET", "/config")[0] for _ in range(100)]
        assert statuses == [401] * 100                                   # every request still rejected
        assert len([e for e in events if e[1].get("reason") == auth.REASON_MISSING]) == auth.THROTTLE_BURST
        assert caplog.text.count("suppressing further log lines") == 1
        now[0] += auth.THROTTLE_WINDOW_S + 1
        assert call(app, "GET", "/config")[0] == 401
        summary = [e for e in events if e[1].get("reason") == auth.REASON_THROTTLED]
        assert summary and summary[0][1]["count"] == 100 - auth.THROTTLE_BURST
        assert "80 further denials were suppressed" in caplog.text

    def test_a_slow_trickle_is_never_throttled(self, required, events, monkeypatch):
        now = [0.0]
        monkeypatch.setattr(auth, "_clock", lambda: now[0])
        for _ in range(60):
            now[0] += 1.0
            call(app, "GET", "/config")
        assert len(events) == 60


class TestSecurityHeaders:
    def test_the_shell_and_assets_carry_the_headers(self, required):
        for path in ("/", "/static/auth.js"):
            _, _, h = call(app, "GET", path)
            assert "frame-ancestors 'none'" in h["content-security-policy"]
            assert "connect-src 'self'" in h["content-security-policy"]
            assert h["x-content-type-options"] == "nosniff"
            assert h["x-frame-options"] == "DENY"
            assert h["referrer-policy"] == "no-referrer"

    def test_authenticated_api_responses_carry_them_too(self, required):
        assert "content-security-policy" in call(app, "GET", "/config", bearer(TOKEN))[2]

    def test_the_policy_names_no_external_origin(self):
        from interface.headers import CONTENT_SECURITY_POLICY
        assert "http:" not in CONTENT_SECURITY_POLICY and "https:" not in CONTENT_SECURITY_POLICY and "*" not in CONTENT_SECURITY_POLICY

    def test_existing_headers_are_not_duplicated(self):
        from interface.headers import SecurityHeadersMiddleware

        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": [(b"x-frame-options", b"SAMEORIGIN")]})
            await send({"type": "http.response.body", "body": b""})

        _, _, h = call(SecurityHeadersMiddleware(downstream), "GET", "/")
        assert h["x-frame-options"] == "SAMEORIGIN"

    @pytest.mark.parametrize("page", ["index.html", "settings.html"])
    def test_pages_load_nothing_from_other_origins(self, page):
        import re
        html = (REPO_ROOT / "interface" / "web" / page).read_text(encoding="utf-8")
        assert re.findall(r'(?:src|href)="https?://[^"]+"', html) == []


class TestTokenCommand:
    def _run(self, *args, env=None):
        base = {k: v for k, v in os.environ.items() if not k.startswith("OCBRAIN_API")}
        return subprocess.run([sys.executable, "-m", "interface.cli", "token", *args], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=60, env={**base, **(env or {})})

    def test_show_prints_only_the_token_on_stdout(self, tmp_path):
        f = tmp_path / "api_token"; f.write_text(TOKEN + "\n"); os.chmod(f, 0o600)
        r = self._run("--show", env={auth.ENV_TOKEN_FILE: str(f)})
        assert r.returncode == 0 and r.stdout == TOKEN + "\n"              # safe inside $(...)
        assert "Token source" in r.stderr and TOKEN not in r.stderr

    def test_plain_form_does_not_reveal_the_token(self, tmp_path):
        f = tmp_path / "api_token"; f.write_text(TOKEN + "\n")
        r = self._run(env={auth.ENV_TOKEN_FILE: str(f)})
        assert r.returncode == 0 and TOKEN not in r.stdout + r.stderr and str(f) in r.stdout

    def test_missing_token_is_reported_not_created(self, tmp_path):
        f = tmp_path / "nope" / "api_token"
        r = self._run("--show", env={auth.ENV_TOKEN_FILE: str(f)})
        assert r.returncode == 1 and r.stdout == "" and not f.exists()

    def test_rotate_replaces_the_token_and_shows_it_only_on_request(self, tmp_path):
        f = tmp_path / "api_token"; f.write_text(TOKEN + "\n"); os.chmod(f, 0o600)
        r = self._run("--rotate", env={auth.ENV_TOKEN_FILE: str(f)})
        new = f.read_text().strip()
        assert r.returncode == 0 and new != TOKEN and new not in r.stdout + r.stderr
        r2 = self._run("--rotate", "--show", env={auth.ENV_TOKEN_FILE: str(f)})
        assert r2.stdout.strip() == f.read_text().strip() != new

    def test_rotate_refuses_an_environment_token(self):
        r = self._run("--rotate", env={auth.ENV_TOKEN: TOKEN})
        assert r.returncode == 1 and auth.ENV_TOKEN in r.stderr

    def test_packaged_binary_path_main_py_answers_token_without_starting_the_server(self, tmp_path):
        # In a packaged install `ocbrain` is main.py itself; it must answer `token` before importing
        # anything heavy or starting anything.
        f = tmp_path / "api_token"; f.write_text(TOKEN + "\n"); os.chmod(f, 0o600)
        base = {k: v for k, v in os.environ.items() if not k.startswith("OCBRAIN_API")}
        t0 = time.time()
        r = subprocess.run([sys.executable, "main.py", "token", "--show"], cwd=REPO_ROOT, capture_output=True,
                           text=True, timeout=60, env={**base, auth.ENV_TOKEN_FILE: str(f)})
        assert r.returncode == 0 and r.stdout == TOKEN + "\n", (r.stdout, r.stderr[-300:])
        assert time.time() - t0 < 10, "should not have imported the runtime"
        assert "Starting" not in r.stdout + r.stderr
        r2 = subprocess.run([sys.executable, "main.py", "token"], cwd=REPO_ROOT, capture_output=True, text=True,
                            timeout=60, env={**base, auth.ENV_TOKEN_FILE: str(tmp_path / "none")})
        assert r2.returncode == 1


class TestCliRouting:
    """`ocbrain status` used to send the text "status" to /query (the group swallowed it)."""

    @pytest.fixture
    def cli_calls(self, monkeypatch):
        from interface import cli
        calls: list[tuple] = []
        monkeypatch.setattr(cli, "_get", lambda p: calls.append(("GET", p)) or {"modules": {}})
        monkeypatch.setattr(cli, "_post", lambda p, d=None: calls.append(("POST", p, d)) or {"answer": "A", "result": "R"})
        return cli, calls

    def test_known_subcommands_run(self, cli_calls):
        from click.testing import CliRunner
        cli, calls = cli_calls
        assert CliRunner().invoke(cli.cli, ["status"]).exit_code == 0
        assert calls == [("GET", "/status")]
        calls.clear()
        assert CliRunner().invoke(cli.cli, ["train", "finance"]).exit_code == 0
        assert calls == [("POST", "/train/finance", None)]

    @pytest.mark.parametrize("args,query,module", [
        (["how are you"], "how are you", None), (["how", "are", "you"], "how are you", None),
        (["-m", "finance", "what is x"], "what is x", "finance"), (["--module", "m", "q"], "q", "m"),
    ])
    def test_free_text_is_still_a_query(self, cli_calls, args, query, module):
        from click.testing import CliRunner
        cli, calls = cli_calls
        assert CliRunner().invoke(cli.cli, args).exit_code == 0
        assert calls == [("POST", "/query", {"query": query, "module": module})]

    def test_piped_stdin_is_still_a_query(self, cli_calls):
        from click.testing import CliRunner
        cli, calls = cli_calls
        assert CliRunner().invoke(cli.cli, [], input="from a pipe\n").exit_code == 0
        assert calls == [("POST", "/query", {"query": "from a pipe", "module": None})]

    def test_help_lists_the_token_command_and_hides_the_internal_one(self, cli_calls):
        from click.testing import CliRunner
        cli, _ = cli_calls
        out = CliRunner().invoke(cli.cli, ["--help"]).output
        assert "token" in out and "status" in out and " ask " not in out


@pytest.mark.skipif(not os.path.isdir("/proc/self"), reason="needs /proc")
class TestTokenNeverOnACommandLine:
    """The tray used to pass `#token=` to the browser launcher.  Every local user can read a
    process's command line, so the token must not be in any argv.  The positive control proves
    the detector would have caught the old behaviour."""

    @staticmethod
    def _cmdlines_containing(needle: str) -> list[str]:
        hits = []
        for pid in filter(str.isdigit, os.listdir("/proc")):
            if int(pid) == os.getpid():
                continue
            try:
                raw = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace")
            except OSError:
                continue
            if needle in raw:
                hits.append(raw)
        return hits

    def _launch(self, monkeypatch, tmp_path, call_open):
        fake = tmp_path / "fakebrowser.py"
        fake.write_text("import time\ntime.sleep(6)\n")
        monkeypatch.setenv("BROWSER", f"{sys.executable} {fake} %s &")
        call_open()
        deadline = time.time() + 5
        while time.time() < deadline:
            if self._cmdlines_containing("fakebrowser.py"):
                return
            time.sleep(0.05)
        pytest.fail("the fake browser launcher never started; the detector would be vacuous")

    @staticmethod
    def _stop():
        for pid in filter(str.isdigit, os.listdir("/proc")):
            try:
                if b"fakebrowser.py" in open(f"/proc/{pid}/cmdline", "rb").read():
                    os.kill(int(pid), 9)
            except OSError:
                pass

    def test_positive_control_a_fragment_token_would_be_visible(self, monkeypatch, tmp_path):
        import webbrowser
        secret = "CONTROL" + TOKEN
        try:
            self._launch(monkeypatch, tmp_path, lambda: webbrowser.open(f"http://localhost:7437#token={secret}"))
            assert self._cmdlines_containing(secret), "detector cannot see a token on a command line"
        finally:
            self._stop()

    def test_the_trays_launch_exposes_no_token(self, monkeypatch, tmp_path):
        from interface import tray
        secret = "TRAYCHECK" + TOKEN
        monkeypatch.setenv(auth.ENV_TOKEN, secret)
        try:
            self._launch(monkeypatch, tmp_path, lambda: tray._open_ui(None, None))
            assert self._cmdlines_containing("fakebrowser.py")
            assert self._cmdlines_containing(secret) == []
        finally:
            self._stop()
