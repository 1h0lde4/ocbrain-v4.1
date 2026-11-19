"""
tests/test_updater_error_disclosure.py -- update-check errors reach API callers.

interface/updater.check() put exception text into UpdateResult.check_error:
f"Could not reach GitHub: {e}" for requests failures (whose messages carry the
connection target -- proxy host/port, resolver errors, URLs) and str(e) for
anything else. GET /updates returns check_error verbatim and POST
/update/install returns it as "error", so a caller saw that text. CodeQL did
not flag it. Listed as "same class, different feature area, not fixed" in
DEBT-037; fixed here on its own.

Now check_error is "<prefix>: <ExceptionClass> (ref <uuid>)" and the exception,
with its traceback, is in the server log under that ref.

Not covered: the CLI (interface/cli.py) just prints check_error from /updates
to the local console and needs no change.
"""
import logging
import re

import pytest
import requests

import interface.api as api_module
import interface.updater as updater

PROXY_DETAIL = (
    "HTTPSConnectionPool(host='corp-proxy.internal', port=8080): Max retries "
    "exceeded (Caused by ProxyError('token=hunter2'))"
)
OTHER_DETAIL = "cannot read /opt/ocbrain/.release_token: permission denied"


@pytest.fixture
def no_git_version(monkeypatch):
    monkeypatch.setattr(updater, "current_version", lambda: "1.0.0")


def test_request_failure_check_error_is_redacted(monkeypatch, no_git_version, caplog):
    def boom(*a, **kw):
        raise requests.ConnectionError(PROXY_DETAIL)

    monkeypatch.setattr(updater.requests, "get", boom)
    with caplog.at_level(logging.ERROR):
        result = updater.check()

    assert result.check_failed is True
    m = re.fullmatch(r"Could not reach GitHub: ConnectionError \(ref ([0-9a-f-]{36})\)",
                     result.check_error)
    assert m, result.check_error
    for leaked in ("corp-proxy", "8080", "hunter2", "HTTPSConnectionPool"):
        assert leaked not in result.check_error
    assert m.group(1) in caplog.text
    assert "corp-proxy" in caplog.text  # the detail is in the log, not lost


def test_generic_failure_check_error_is_redacted(monkeypatch, no_git_version, caplog):
    def boom(*a, **kw):
        raise PermissionError(OTHER_DETAIL)

    monkeypatch.setattr(updater.requests, "get", boom)
    with caplog.at_level(logging.ERROR):
        result = updater.check()

    m = re.fullmatch(r"Update check failed: PermissionError \(ref ([0-9a-f-]{36})\)",
                     result.check_error)
    assert m, result.check_error
    assert ".release_token" not in result.check_error
    assert ".release_token" in caplog.text
    assert m.group(1) in caplog.text


@pytest.mark.asyncio
async def test_updates_and_install_endpoints_return_only_the_redacted_text(
    monkeypatch, no_git_version
):
    def boom(*a, **kw):
        raise requests.ConnectionError(PROXY_DETAIL)

    monkeypatch.setattr(updater.requests, "get", boom)

    body = await api_module.check_updates()
    assert body["check_failed"] is True
    assert "corp-proxy" not in body["check_error"] and "hunter2" not in body["check_error"]
    assert re.search(r"\(ref [0-9a-f-]{36}\)", body["check_error"])

    install = await api_module.install_update()
    assert install["status"] == "check_failed"
    assert "corp-proxy" not in install["error"] and "hunter2" not in install["error"]
    assert re.search(r"\(ref [0-9a-f-]{36}\)", install["error"])
