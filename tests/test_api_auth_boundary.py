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


def _scope(method: str, path: str, headers=(), type_: str = "http") -> dict:
    return {
        "type": type_, "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "scheme": "http", "server": ("127.0.0.1", 7437), "client": ("127.0.0.1", 50000),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers],
    }


def call(target, method: str, path: str, headers=()) -> tuple[int, bytes, dict]:
    """Drive an ASGI app directly (no URL normalisation, exact path preserved)."""
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(target(_scope(method, path, headers), receive, send))
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
        assert auth.PUBLIC_EXACT_PATHS == {"/", "/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
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
        ("GET", "/docs", True), ("GET", "/docs/", False), ("GET", "/openapi.json", True),
        ("GET", "/config", False), ("GET", "/health", False), ("PUT", "/static/x", False),
        ("OPTIONS", "/", False),
    ])
    def test_is_public(self, method, path, expected):
        assert auth.is_public(method, path) is expected

    def test_shell_and_docs_need_no_token(self, required):
        assert call(app, "GET", "/")[0] == 200
        status, body, _ = call(app, "GET", "/openapi.json")
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

    def test_tray_url_carries_the_token_in_the_fragment_only(self, monkeypatch):
        from interface import tray
        monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
        url = tray._ui_url("/static/settings.html")
        assert url == f"http://localhost:{tray.PORT}/static/settings.html#token={TOKEN}"
        monkeypatch.delenv(auth.ENV_TOKEN)
        monkeypatch.setenv(auth.ENV_TOKEN_FILE, "/nonexistent/api_token")
        assert "#" not in tray._ui_url()

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
