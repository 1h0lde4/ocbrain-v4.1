"""scripts/ci_gate_report.py -- structured pytest report for scripts/ci_test_gate.py (R-1, schema 2).

Why this exists
---------------
The gate used to learn about failures by parsing pytest's terminal text.  A
``FAILED`` line is ``FAILED <node id> - <message>``, but a parametrised node ID
may itself contain `` - ``, so the ID/message boundary is ambiguous (R-1), and
pytest drops the ``- <message>`` part altogether when the line would exceed the
terminal width.  This plugin records the facts the gate needs *structurally*.

Usage::

    python -m pytest tests/ -p scripts.ci_gate_report --ci-gate-report=/tmp/report.json

What the report contains (schema 2)
-----------------------------------
* ``collected``: the final collection inventory (node IDs), so completeness can
  be checked: every collected test must have an explainable terminal outcome.
* ``records``: one per executed phase, with ``category`` in
  ``passed | failed | skipped | xfailed | xpassed | xpass_strict | error | phase_ok``.
  pytest reports a non-strict XPASS as ``passed`` + ``wasxfail``; it is recorded as
  ``xpassed`` here and must never be counted as an ordinary pass.
* ``chain``: the exception cause chain (<= 8) as fully qualified ``type``, ``mro``
  (evidence only), redacted ``message``, and ``errno`` / ``http_status`` when the
  exception carries one.  No locals, no tracebacks, no frames.
* ``counts``: tallies by category, cross-checked by the gate.
* ``complete`` / ``plugin_fault`` / ``exitstatus``.

Messages are redacted for credentials (bearer/basic tokens, well-known token
prefixes, secret-looking URL query parameters, URL userinfo, ``key: value`` secrets)
before they are stored, because the report is uploaded as a CI artifact.

Design rules: stdlib only; additive (never changes a test outcome or pytest's exit
status); a stale report is deleted at configure time; written atomically and only at
``pytest_sessionfinish``.  Any fault is recorded or leaves no report; both make the
*gate* fail closed.  ``pytest-xdist`` is unsupported (a worker's records would be
lost) and therefore fails closed.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any

import pytest

SCHEMA = 2
_MAX_CHAIN = 8
_MAX_MRO = 12
_MAX_MSG = 500
_XPASS_STRICT_PREFIX = "[XPASS(strict)]"

_STATE: dict[str, Any] = {}

_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 <redacted>"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat|hf|sk|xox[abps])[_-][A-Za-z0-9_-]{10,}"), "<redacted-token>"),
    (re.compile(r"(?i)([?&;](?:token|access_token|api_key|apikey|key|secret|signature|sig|password|passwd|auth|"
                r"authorization|x-amz-signature|x-amz-credential|x-amz-security-token)=)[^&\s'\")]+"), r"\1<redacted>"),
    (re.compile(r"(?i)\b(authorization|x-api-key|api[_-]?key|token|password|secret)(\s*[:=]\s*)[^\s,;'\"]{4,}"),
     r"\1\2<redacted>"),
    (re.compile(r"(://)[^/\s:@]+:[^/\s@]+@"), r"\1<redacted>@"),
]


def redact(text: str) -> str:
    for pat, repl in _REDACTIONS:
        text = pat.sub(repl, text)
    return text


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.getgroup("ci-gate").addoption(
        "--ci-gate-report", action="store", default=None, metavar="PATH",
        help="write a structured JSON report for scripts/ci_test_gate.py")


def _path(config: pytest.Config) -> str | None:
    p = config.getoption("--ci-gate-report", default=None)
    return str(p) if p else None


def pytest_configure(config: pytest.Config) -> None:
    path = _path(config)
    if not path:
        return
    _STATE.clear()
    _STATE.update(records=[], collect_errors=[], collected=None, fault=None)
    try:
        os.remove(path)  # never let a stale report masquerade as this run's
    except FileNotFoundError:
        pass
    except OSError as e:
        _STATE["fault"] = f"cannot remove stale report: {e!r}"


def _qualname(t: type) -> str:
    return f"{t.__module__}.{t.__qualname__}"


def _int_or_none(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _chain(excinfo: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    exc: BaseException | None = excinfo.value if excinfo is not None else None
    while exc is not None and id(exc) not in seen and len(out) < _MAX_CHAIN:
        seen.add(id(exc))
        el: dict[str, Any] = {
            "type": _qualname(type(exc)),
            "mro": [_qualname(t) for t in type(exc).__mro__[1:] if t is not object][:_MAX_MRO],
            "message": redact(str(exc))[:_MAX_MSG],
        }
        errno = _int_or_none(getattr(exc, "errno", None))
        if errno is not None:
            el["errno"] = errno
        resp = getattr(exc, "response", None)
        status = _int_or_none(getattr(resp, "status_code", None))
        if status is None:
            status = _int_or_none(getattr(exc, "status_code", None))
        if status is not None and 100 <= status <= 599:
            el["http_status"] = status
        out.append(el)
        exc = exc.__cause__ or exc.__context__
    return out


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):  # type: ignore[type-arg]
    outcome = yield
    if "records" not in _STATE:
        return
    try:
        rep = outcome.get_result()
        if call.excinfo is not None:
            rep._ci_gate_chain = _chain(call.excinfo)
    except Exception as e:  # noqa: BLE001 - record, never break the run
        _STATE["fault"] = f"makereport: {e!r}"


def _category(report: pytest.TestReport) -> str:
    wasxfail = hasattr(report, "wasxfail")
    if report.when != "call":
        if report.outcome == "failed":
            return "error"
        if report.outcome == "skipped":
            return "xfailed" if wasxfail else "skipped"
        return "phase_ok"
    if report.outcome == "failed":
        lr = report.longrepr
        return "xpass_strict" if isinstance(lr, str) and lr.startswith(_XPASS_STRICT_PREFIX) else "failed"
    if report.outcome == "skipped":
        return "xfailed" if wasxfail else "skipped"
    return "xpassed" if wasxfail else "passed"


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if "records" not in _STATE:
        return
    try:
        _STATE["records"].append({
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "category": _category(report),
            "wasxfail": hasattr(report, "wasxfail"),
            "chain": getattr(report, "_ci_gate_chain", []),
        })
    except Exception as e:  # noqa: BLE001
        _STATE["fault"] = f"logreport: {e!r}"


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if "records" not in _STATE:
        return
    try:
        if report.failed:
            _STATE["collect_errors"].append(str(report.nodeid))
    except Exception as e:  # noqa: BLE001
        _STATE["fault"] = f"collectreport: {e!r}"


def pytest_collection_finish(session: pytest.Session) -> None:
    if "records" not in _STATE:
        return
    try:
        _STATE["collected"] = [it.nodeid for it in session.items]  # final list, after deselection
    except Exception as e:  # noqa: BLE001
        _STATE["fault"] = f"collection_finish: {e!r}"


def _counts(records: list[dict[str, Any]]) -> dict[str, int]:
    c = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    for r in records:
        cat, when = r["category"], r["when"]
        if cat == "error":
            c["errors"] += 1
        elif when == "call" and cat == "passed":
            c["passed"] += 1
        elif when == "call" and cat in ("failed", "xpass_strict"):
            c["failed"] += 1
        elif cat in ("skipped", "xfailed", "xpassed") and when in ("call", "setup"):
            c[{"skipped": "skipped", "xfailed": "xfailed", "xpassed": "xpassed"}[cat]] += 1
    return c


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    path = _path(session.config)
    if not path or "records" not in _STATE:
        return
    try:
        doc = {
            "schema": SCHEMA,
            "complete": True,
            "plugin_fault": _STATE.get("fault"),
            "exitstatus": int(exitstatus),
            "collected": _STATE.get("collected"),
            "counts": _counts(_STATE["records"]),
            "records": _STATE["records"],
            "collect_errors": _STATE["collect_errors"],
        }
        d = os.path.dirname(os.path.abspath(path))
        fd, tmp = tempfile.mkstemp(prefix=".ci-gate-report.", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    except Exception:  # noqa: BLE001 - no report => the gate fails closed
        pass
