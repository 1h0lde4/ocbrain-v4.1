"""DEBT-025: execute the real interface/web/auth.js against a live server.

The browser helpers (token adoption from the URL fragment, Authorization header,
single prompt on 401, cancel handling, the fetch-based SSE reader) are the only
client code that is not Python.  tests/js/auth_js_live.js runs auth.js unmodified
inside a Node vm context with a stub window, against a real uvicorn server running
the real app with the auth middleware on.  Skipped when Node is not installed.
This is not a browser test: it does not cover rendering or the page's own scripts.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from interface import auth

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "js-e2e-token-" + "k7m2p9x4" * 5

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_auth_js_against_a_live_authenticated_server(monkeypatch, tmp_path):
    import uvicorn
    from interface.api import app

    monkeypatch.delenv(auth.ENV_MODE, raising=False)
    monkeypatch.setenv(auth.ENV_TOKEN, TOKEN)
    monkeypatch.setenv(auth.ENV_TOKEN_FILE, str(tmp_path / "api_token"))
    auth.reset_cache_for_tests()

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", loop="asyncio"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 15
        while not server.started and time.time() < deadline:
            time.sleep(0.05)
        assert server.started, "server did not start"
        port = server.servers[0].sockets[0].getsockname()[1]
        proc = subprocess.run(
            ["node", str(ROOT / "tests" / "js" / "auth_js_live.js")],
            env={"PATH": __import__("os").environ["PATH"], "PORT": str(port), "TOKEN": TOKEN,
                 "AUTH_JS": str(ROOT / "interface" / "web" / "auth.js")},
            capture_output=True, text=True, timeout=90,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "15/15 checks passed" in proc.stdout, proc.stdout
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        auth.reset_cache_for_tests()
