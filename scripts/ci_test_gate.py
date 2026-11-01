#!/usr/bin/env python3
"""scripts/ci_test_gate.py -- decide whether a CI pytest run is acceptable (FZ-07).

Why this exists
---------------
The ``tests`` job used to discard pytest's exit code (``... | tee ... || true``)
and then gated only on ``^FAILED `` lines that were not in the known-failure
list (docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt).  Anything that
does not print a ``FAILED`` line was therefore invisible: collection errors,
fixture/setup errors, ``INTERNALERROR``, a run that collected nothing, a
truncated/killed run, an interpreter that never started pytest.

This script is the whole decision, kept in one place so it can be unit-tested
instead of living as untestable inline shell.

Contract
--------
PASS only if ALL of the following hold:

1. pytest's real exit code was recorded and is 0 or 1.  Every other code is a
   failure by itself (2 interrupted/collection error, 3 internal error,
   4 usage error, 5 nothing collected, 127/130/137/... crash or kill).
2. The output contains pytest's final summary line (a truncated run has none).
3. The summary reports no errors, at least one passed test, and the output has
   no ``ERROR <nodeid>`` / ``INTERNALERROR`` lines.
4. Exit code 0  -> there are no ``FAILED`` lines and the summary reports 0 failed.
   Exit code 1  -> there is at least one failure, the number of distinct
   ``FAILED`` node IDs equals the summary's ``N failed``, and EVERY one of them
   is listed in the known-failure file.  An unlisted failure fails the gate.

What this deliberately does NOT do
----------------------------------
* It does not change the known-failure list or how it is matched: one node ID
  per line, ``#`` comment lines and blank lines ignored, exact match, an entry
  that no longer fails is fine.  The list is neither widened nor re-validated
  here.
* It does not re-label a failure as environmental.  In the legacy text mode a
  failure is tolerated only if its exact node ID is already listed.  In report
  mode (``--report``, R-1) it must ALSO match an approved failure signature
  (``--signature-policy``); an ID alone never suppresses a different failure.
  See ``evaluate_report``.

The only output is human-readable text on stdout plus the process exit code:
0 = gate passed, 1 = gate failed, 2 = the gate itself could not read its inputs
(also a failure for CI -- fail closed).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# pytest exit codes (https://docs.pytest.org/en/stable/reference/exit-codes.html)
_EXIT_MEANING = {
    0: "all tests passed",
    1: "some tests failed",
    2: "test execution was interrupted (collection error or user interrupt)",
    3: "internal error while running tests",
    4: "pytest command line usage error",
    5: "no tests were collected",
}

# Final summary line, with or without the "=====" decoration, e.g.
#   "1788 passed, 14 skipped, 1 xfailed in 100.00s (0:01:40)"
#   "2 failed, 1786 passed in 1.0s"   "1 error in 0.50s"   "no tests ran in 0.01s"
_SUMMARY_RE = re.compile(
    r"^(?:=+ )?(?P<body>no tests ran|\d+ [A-Za-z]+(?:, \d+ [A-Za-z]+)*)"
    r" in [\d.]+s(?: \(\d+:\d{2}:\d{2}\))?(?: =+)?$"
)
_COUNT_RE = re.compile(r"(\d+) ([A-Za-z]+)")

# pytest's short-summary error entries are "ERROR <path>.py" / "ERROR <path>.py::<id>"
# (optionally " - <reason>"), and "ERROR collecting <path>.py".  Captured logging lines
# ("ERROR    logger:file.py:12 msg", level name padded to 8 columns) and arbitrary
# captured stdout such as "ERROR connection refused" must NOT match: they appear inside
# the output of failing tests and are not pytest errors.
_ERROR_LINE_RE = re.compile(r"^ERROR (?:collecting )?[^\s:]+\.py(?:$|::| - )")
_INTERNALERROR_RE = re.compile(r"^INTERNALERROR")


@dataclass
class Summary:
    failed: int = 0
    passed: int = 0
    errors: int = 0
    raw: str = ""


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    known_failures_seen: list[str] = field(default_factory=list)
    new_failures: list[str] = field(default_factory=list)


def parse_allowlist(text: str) -> set[str]:
    """Same semantics as the previous shell: drop '#' lines and blanks, exact match.

    Split on "\\n" only (not str.splitlines): a stray CR must stay part of the
    entry so it can never match, exactly as it did with the shell version.
    """
    return {ln for ln in text.split("\n") if ln and not ln.startswith("#")}


def parse_failed_ids(output: str) -> set[str]:
    """Node IDs of ``FAILED`` short-summary lines (text after '- ' reason stripped)."""
    ids: set[str] = set()
    for ln in output.split("\n"):
        if ln.startswith("FAILED "):
            ids.add(ln[len("FAILED "):].split(" - ", 1)[0])
    return ids


def parse_summary(output: str) -> Summary | None:
    """Last line that looks like pytest's final summary, or None if absent."""
    found: Summary | None = None
    for ln in output.split("\n"):
        m = _SUMMARY_RE.match(ln.rstrip("\r"))
        if not m:
            continue
        s = Summary(raw=ln.strip())
        for n, word in _COUNT_RE.findall(m.group("body")):
            word = word.lower()
            if word == "failed":
                s.failed = int(n)
            elif word == "passed":
                s.passed = int(n)
            elif word in ("error", "errors"):
                s.errors = int(n)
        found = s
    return found


def evaluate(output: str, exit_code: int | None, allowlist: set[str]) -> Verdict:
    v = Verdict(ok=True)

    def fail(reason: str) -> None:
        v.ok = False
        v.reasons.append(reason)

    if exit_code is None:
        fail("pytest's exit code was not recorded (the test step did not run to completion)")
    elif exit_code not in (0, 1):
        meaning = _EXIT_MEANING.get(exit_code, "pytest was killed or crashed")
        fail(f"pytest exited with code {exit_code}: {meaning}")

    summary = parse_summary(output)
    if summary is None:
        fail("no pytest summary line found in the output (truncated, killed, or pytest never ran)")

    for ln in output.split("\n"):
        if _INTERNALERROR_RE.match(ln):
            fail("INTERNALERROR in pytest output")
            break
    error_lines = sorted({ln for ln in output.split("\n") if _ERROR_LINE_RE.match(ln)})
    if error_lines:
        fail(f"{len(error_lines)} ERROR entr{'y' if len(error_lines) == 1 else 'ies'} "
             f"(collection/setup/teardown errors are not test failures and are never allowlisted): "
             + "; ".join(e[:120] for e in error_lines[:5]))

    failed_ids = parse_failed_ids(output)

    if summary is not None:
        if summary.errors:
            fail(f"summary reports {summary.errors} error(s): {summary.raw}")
        if summary.passed == 0:
            fail(f"no test passed, so nothing was verified: {summary.raw}")
        if exit_code == 0:
            if summary.failed or failed_ids:
                fail("exit code 0 but failures are reported (inconsistent run)")
        elif exit_code == 1:
            if len(failed_ids) != summary.failed:
                fail(f"summary reports {summary.failed} failed but {len(failed_ids)} distinct FAILED "
                     f"node ID(s) were found in the output")
            if summary.failed == 0 and not summary.errors:
                fail("exit code 1 but the summary reports no failures and no errors")

    v.known_failures_seen = sorted(failed_ids & allowlist)
    v.new_failures = sorted(failed_ids - allowlist)
    if v.new_failures:
        fail(f"{len(v.new_failures)} failure(s) not in the known-failure list")
    return v


# ---------------------------------------------------------------------------
# Report mode (R-1): structured pytest report + approved failure signature.
# The legacy text path above is intentionally left unchanged.
# ---------------------------------------------------------------------------

_REPORT_SCHEMA = 1
_POLICY_SCHEMA = 1
_NODEID_RE = re.compile(r"^[A-Za-z0-9_./\-]+\.py::\S.*$")


def load_policy(text: str) -> dict:
    """Parse and validate the signature policy; raise ValueError if malformed."""
    try:
        pol = json.loads(text)
    except ValueError as e:
        raise ValueError(f"signature policy is not valid JSON: {e}") from e
    if not isinstance(pol, dict) or pol.get("schema") != _POLICY_SCHEMA:
        raise ValueError(f"signature policy must be an object with schema == {_POLICY_SCHEMA}")
    classes = pol.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ValueError("signature policy needs a non-empty 'classes' list")
    for c in classes:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not c["name"]:
            raise ValueError("each signature class needs a non-empty string 'name'")
        if c.get("phase") != "call":
            raise ValueError(f"class {c['name']!r}: only phase 'call' may be tolerated")
        toks = c.get("chain_message_contains")
        if (not isinstance(toks, list) or not toks
                or not all(isinstance(t, str) and t.strip() for t in toks)):
            raise ValueError(f"class {c['name']!r}: 'chain_message_contains' must be a non-empty list of non-blank strings")
    return pol


def validate_allowlist_entries(allowlist: set[str]) -> list[str]:
    """Return the malformed entries.  A malformed or truncated entry must never
    be able to match (or broaden) anything, so any such entry fails the gate."""
    bad: list[str] = []
    for e in sorted(allowlist):
        ok = bool(_NODEID_RE.match(e)) and e == e.strip() and "\r" not in e
        if ok and "[" in e:
            depth = 0
            for ch in e[e.index("["):]:
                depth += (ch == "[") - (ch == "]")
                if depth < 0:
                    break
            ok = depth == 0 and e.endswith("]")
        elif ok and "]" in e:
            ok = False
        if not ok:
            bad.append(e)
    return bad


def _matches_class(rec: dict, pol: dict) -> str | None:
    chain = rec.get("chain")
    if not isinstance(chain, list) or not chain:
        return None
    for cls in pol["classes"]:
        if cls["phase"] != rec.get("when"):
            continue
        toks = [t.lower() for t in cls["chain_message_contains"]]
        for exc in chain:
            msg = str(exc.get("message", "")).lower() if isinstance(exc, dict) else ""
            if all(t in msg for t in toks):
                return cls["name"]
    return None


def evaluate_report(report: object, exit_code: int | None, allowlist: set[str],
                    policy: dict, summary: Summary | None = None) -> Verdict:
    """Decide from a structured report.  Fail closed on anything unexpected.

    A failure is tolerated only if ALL hold: its exact node ID is in the
    allowlist, it failed in the ``call`` phase, it is not a strict XPASS, and
    its exception chain matches an approved signature class.
    """
    v = Verdict(ok=True)

    def fail(reason: str) -> None:
        v.ok = False
        v.reasons.append(reason)

    if exit_code is None:
        fail("pytest's exit code was not recorded (the test step did not run to completion)")
    elif exit_code not in (0, 1):
        fail(f"pytest exited with code {exit_code}: {_EXIT_MEANING.get(exit_code, 'pytest was killed or crashed')}")

    for e in validate_allowlist_entries(allowlist):
        fail(f"malformed/truncated allowlist entry (cannot be matched safely): {e[:120]!r}")

    if not isinstance(report, dict):
        fail("structured report missing or unreadable (plugin did not run, or run was killed)")
        return v
    if report.get("schema") != _REPORT_SCHEMA:
        fail(f"unsupported report schema {report.get('schema')!r}")
        return v
    if report.get("complete") is not True:
        fail("structured report is not marked complete")
    if report.get("plugin_fault"):
        fail(f"report plugin fault: {str(report['plugin_fault'])[:200]}")
    if exit_code in (0, 1) and report.get("exitstatus") != exit_code:
        fail(f"report exitstatus {report.get('exitstatus')!r} disagrees with recorded exit code {exit_code}")
    records = report.get("records")
    if not isinstance(records, list):
        fail("report has no 'records' list")
        return v
    cerr = report.get("collect_errors")
    if not isinstance(cerr, list) or cerr:
        fail(f"collection error(s) in report: {cerr!r}"[:200])

    call_fail: dict[str, dict] = {}
    errors: list[str] = []
    passed = 0
    for r in records:
        if not isinstance(r, dict) or not isinstance(r.get("nodeid"), str) or r.get("when") not in ("setup", "call", "teardown"):
            fail("malformed record in report")
            continue
        if r.get("outcome") == "failed":
            if r["when"] == "call":
                call_fail[r["nodeid"]] = r
            else:
                errors.append(f"{r['nodeid']} ({r['when']})")
        elif r["when"] == "call" and r.get("outcome") == "passed":
            passed += 1
    if errors:
        fail(f"{len(errors)} setup/teardown error(s) (never allowlisted): " + "; ".join(e[:100] for e in errors[:5]))
    if passed == 0:
        fail("no test passed, so nothing was verified")

    if exit_code == 0 and (call_fail or errors):
        fail("exit code 0 but failures are reported (inconsistent run)")
    if exit_code == 1 and not call_fail and not errors:
        fail("exit code 1 but the report contains no failures or errors")

    if summary is None:
        fail("no pytest summary line in the text output (cross-check unavailable; truncated run?)")
    else:
        if summary.failed != len(call_fail):
            fail(f"text summary reports {summary.failed} failed but the report has {len(call_fail)}")
        if summary.errors != len(errors):
            fail(f"text summary reports {summary.errors} error(s) but the report has {len(errors)}")

    for nid, rec in sorted(call_fail.items()):
        cls = None
        if rec.get("xpass_strict"):
            reason = "strict XPASS is never excused"
        elif nid not in allowlist:
            reason = "not in the known-failure list"
        else:
            cls = _matches_class(rec, policy)
            reason = None if cls else "listed, but its failure does not match an approved signature class"
        if reason is None:
            v.known_failures_seen.append(nid)
        else:
            v.new_failures.append(nid)
            fail(f"{nid}: {reason}")
    return v


def _read_json_report(path: Path) -> object:
    try:
        return json.loads(_read_text_raw(path))
    except (OSError, ValueError):
        return None


def _read_text_raw(path: Path) -> str:
    """Read without newline translation (CR is preserved; see parse_allowlist)."""
    return path.read_bytes().decode("utf-8", errors="replace")


def _read_exit_code(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--output", required=True, type=Path, help="captured pytest stdout+stderr")
    ap.add_argument("--exit-code-file", required=True, type=Path, help="file holding pytest's real exit code")
    ap.add_argument("--allowlist", required=True, type=Path, help="known-failure node-ID list")
    ap.add_argument("--report", type=Path, help="structured JSON report from scripts/ci_gate_report.py (enables report mode)")
    ap.add_argument("--signature-policy", type=Path, help="approved failure-signature policy (required with --report)")
    a = ap.parse_args(argv)
    if bool(a.report) != bool(a.signature_policy):
        print("GATE ERROR: --report and --signature-policy must be given together")
        return 2

    try:
        allowlist = parse_allowlist(_read_text_raw(a.allowlist))
    except OSError as e:
        print(f"GATE ERROR: cannot read allowlist {a.allowlist}: {e}")
        return 2
    try:
        output = _read_text_raw(a.output)
    except OSError:
        # Missing output is a failed run, not a pass: evaluate() will reject it.
        print(f"GATE: pytest output {a.output} is missing")
        output = ""
    exit_code = _read_exit_code(a.exit_code_file)

    if a.report:
        try:
            policy = load_policy(_read_text_raw(a.signature_policy))
        except (OSError, ValueError) as e:
            print(f"GATE ERROR: cannot use signature policy {a.signature_policy}: {e}")
            return 2
        v = evaluate_report(_read_json_report(a.report), exit_code, allowlist, policy, parse_summary(output))
    else:
        v = evaluate(output, exit_code, allowlist)

    print(f"pytest exit code: {exit_code if exit_code is not None else 'NOT RECORDED'}")
    summary = parse_summary(output)
    print(f"pytest summary:   {summary.raw if summary else 'NOT FOUND'}")
    print("Known environmental failures still failing (expected, not gated):")
    for t in v.known_failures_seen:
        print(f"  {t}")
    if v.new_failures:
        print("\nNEW test failure(s) not in the known-environmental list:")
        for t in v.new_failures:
            print(f"  {t}")
        print("If this is genuinely a new environmental class (not a real regression), add it")
        print("explicitly to docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt with a comment")
        print("explaining why -- do not just widen this gate silently.")
    if not v.ok:
        print("\n" + "=" * 58)
        print("TEST GATE FAILED:")
        for r in v.reasons:
            print(f"  - {r}")
        print("=" * 58)
        return 1
    print("Test gate passed: no unlisted failures, no errors, exit code acceptable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
