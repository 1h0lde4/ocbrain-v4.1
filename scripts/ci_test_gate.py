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
* It does not re-label a failure as environmental.  A failure is tolerated only
  if its exact node ID is already listed.

The only output is human-readable text on stdout plus the process exit code:
0 = gate passed, 1 = gate failed, 2 = the gate itself could not read its inputs
(also a failure for CI -- fail closed).
"""
from __future__ import annotations

import argparse
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
    a = ap.parse_args(argv)

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
