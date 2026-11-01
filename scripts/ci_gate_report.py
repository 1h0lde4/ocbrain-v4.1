"""scripts/ci_gate_report.py -- structured pytest report for scripts/ci_test_gate.py (R-1).

Why this exists
---------------
The gate used to learn about failures by parsing pytest's terminal text.  A
``FAILED`` line is ``FAILED <node id> - <message>``, but a parametrised node ID
may itself contain `` - ``, so the ID/message boundary is ambiguous (R-1), and
pytest drops the ``- <message>`` part altogether when the line would exceed the
terminal width, so the exception type is not recoverable from text for long IDs.

This plugin records the facts the gate needs *structurally*: node ID, phase,
outcome, strict-XPASS flag and the exception chain, plus a completeness marker
written only when the session finishes.

Usage::

    python -m pytest tests/ -p scripts.ci_gate_report --ci-gate-report=/tmp/report.json

Design rules
------------
* stdlib only; additive; it never changes a test outcome or pytest's exit status.
* a stale report from an earlier run is deleted at configure time, so a run
  that dies early can never be mistaken for a complete one.
* the report is written atomically (temp file + ``os.replace``) and only at
  ``pytest_sessionfinish``; ``complete`` is true only in that write.
* any plugin fault is recorded (``plugin_fault``) or leaves no report at all.
  Both make the *gate* fail closed; neither breaks pytest's own run.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import pytest

SCHEMA = 1
_MAX_CHAIN = 8
_MAX_MSG = 500
_XPASS_STRICT_PREFIX = "[XPASS(strict)]"

_STATE: dict[str, Any] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.getgroup("ci-gate").addoption(
        "--ci-gate-report",
        action="store",
        default=None,
        metavar="PATH",
        help="write a structured JSON report for scripts/ci_test_gate.py",
    )


def _path(config: pytest.Config) -> str | None:
    p = config.getoption("--ci-gate-report", default=None)
    return str(p) if p else None


def pytest_configure(config: pytest.Config) -> None:
    path = _path(config)
    if not path:
        return
    _STATE.clear()
    _STATE.update(records=[], collect_errors=[], fault=None)
    try:
        os.remove(path)  # never let a stale report masquerade as this run's
    except FileNotFoundError:
        pass
    except OSError as e:  # cannot remove -> cannot trust the path
        _STATE["fault"] = f"cannot remove stale report: {e!r}"


def _chain(excinfo: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[int] = set()
    exc: BaseException | None = excinfo.value if excinfo is not None else None
    while exc is not None and id(exc) not in seen and len(out) < _MAX_CHAIN:
        seen.add(id(exc))
        t = type(exc)
        out.append({"type": f"{t.__module__}.{t.__qualname__}", "message": str(exc)[:_MAX_MSG]})
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


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if "records" not in _STATE:
        return
    try:
        lr = report.longrepr
        _STATE["records"].append({
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "xpass_strict": bool(
                report.outcome == "failed" and isinstance(lr, str) and lr.startswith(_XPASS_STRICT_PREFIX)
            ),
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


def _counts(records: list[dict[str, Any]]) -> dict[str, int]:
    c = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for r in records:
        if r["when"] == "call":
            if r["outcome"] == "passed":
                c["passed"] += 1
            elif r["outcome"] == "failed":
                c["failed"] += 1
            elif r["outcome"] == "skipped":
                c["skipped"] += 1
        elif r["outcome"] == "failed":
            c["errors"] += 1
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
