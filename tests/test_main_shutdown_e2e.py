"""
tests/test_main_shutdown_e2e.py -- the real server, the real EventStream, a real signal (PR #112 review).

``drain_audit()`` is unit-tested and its position in ``main.py`` is pinned statically, but neither proves that the
actual exit path works.  These tests run ``main.py`` itself in a subprocess, with its working directory (and so its
EventStream at ``.data/events/stream.db``) in a throwaway directory, and then:

1. make a few unauthenticated requests, which open a denial window and leave nothing persisted yet;
2. deliver SIGTERM (and, separately, SIGINT, which is Ctrl-C);
3. require a bounded exit;
4. reopen the SQLite file and require the aggregate that the window would otherwise have lost.

A third test breaks the store (its database path becomes a directory) and requires that the process still exits in
bounded time and says what was lost.

Skipped where the prerequisites are missing: no POSIX signals (Windows), ``chromadb`` not installed (``main.py``
cannot start without it), or the server's configured port is already in use.
"""
from __future__ import annotations

import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from interface import auth

REPO = Path(__file__).resolve().parent.parent
PORT = 7437                      # the server's configured port (config/settings.toml)
STARTUP_TIMEOUT_S = 90.0         # generous: CI starts cold and imports heavy packages
EXIT_TIMEOUT_S = 20.0            # the bound the tests require of a shutdown

pytestmark = pytest.mark.skipif(os.name == "nt", reason="needs POSIX signals")


def _port_is_free() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) != 0


def _status(path: str) -> int:
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=5).status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return 0


def _auth_rows(db_file: Path) -> list[tuple[str, dict]]:
    if not db_file.is_file():
        return []
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT event_type, payload FROM events WHERE event_type LIKE 'api.auth%' ORDER BY sequence").fetchall()
    finally:
        conn.close()
    return [(event_type, json.loads(payload)) for event_type, payload in rows]


def _log_tail(log_file: Path, lines: int = 25) -> str:
    return "\n".join(log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


@pytest.fixture
def server(tmp_path):
    pytest.importorskip("chromadb", reason="main.py cannot start without chromadb")
    if not _port_is_free():
        pytest.skip(f"port {PORT} is already in use")
    log_file = tmp_path / "server.log"
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    env[auth.ENV_TOKEN] = "e2e-token-0123456789abcdef0123456789abcdef"
    env[auth.ENV_TOKEN_FILE] = str(tmp_path / "api_token")
    env.pop(auth.ENV_MODE, None)   # default: authentication required
    with open(log_file, "wb") as log:
        proc = subprocess.Popen(
            [sys.executable, str(REPO / "main.py")], cwd=tmp_path, env=env, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
            # A CI step can hand us an ignored SIGINT; Ctrl-C must reach main.py as it does in a terminal.
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
        )
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while _status("/") != 200:
            if proc.poll() is not None:
                pytest.fail(f"main.py exited during startup (code {proc.returncode}):\n{_log_tail(log_file)}")
            if time.monotonic() > deadline:
                pytest.fail(f"main.py did not answer within {STARTUP_TIMEOUT_S:.0f} s:\n{_log_tail(log_file)}")
            time.sleep(0.5)
        yield proc, tmp_path, log_file
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


def _open_a_denial_window(count: int = 3) -> None:
    for _ in range(count):
        assert _status("/config") == 401


def _stop(proc, sig) -> float:
    started = time.monotonic()
    proc.send_signal(sig)
    try:
        proc.wait(timeout=EXIT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        pytest.fail(f"the server was still running {EXIT_TIMEOUT_S:.0f} s after {sig.name}")
    return time.monotonic() - started


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=["SIGTERM", "SIGINT"])
def test_a_pending_denial_window_is_persisted_when_the_server_is_stopped(server, sig):
    proc, cwd, log_file = server
    db_file = cwd / ".data" / "events" / "stream.db"
    _open_a_denial_window(3)
    assert _auth_rows(db_file) == [], "the window is still open: nothing may be persisted yet"

    elapsed = _stop(proc, sig)

    assert elapsed < EXIT_TIMEOUT_S
    rows = _auth_rows(db_file)
    aggregates = [p for t, p in rows if t == auth.EVENT_DENIED and p.get("kind") == "aggregate"]
    assert len(aggregates) == 1, f"expected the open window as one aggregate, got {rows}\n{_log_tail(log_file)}"
    assert aggregates[0]["total"] == 3
    assert re.fullmatch(r"[0-9a-f]{32}", aggregates[0]["aggregate_id"])


def test_a_broken_store_does_not_stop_the_server_from_exiting_and_the_loss_is_reported(server):
    proc, cwd, log_file = server
    db_file = cwd / ".data" / "events" / "stream.db"
    _open_a_denial_window(3)
    db_file.rename(db_file.with_name("stream.db.bak"))
    db_file.mkdir()                        # every sqlite3.connect() on this path now fails

    elapsed = _stop(proc, signal.SIGTERM)

    assert elapsed < EXIT_TIMEOUT_S
    log = log_file.read_text(encoding="utf-8", errors="replace")
    assert "could not be persisted at shutdown and are lost" in log, _log_tail(log_file)
    assert "api.auth_denied" in log
