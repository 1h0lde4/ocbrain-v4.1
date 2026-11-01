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
  (``--signature-policy``, status ACCEPTED only); an ID alone never suppresses a different failure.
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

_REPORT_SCHEMA = 2
_POLICY_SCHEMA = 2
_POLICY_STATUSES = ("PROPOSED", "ACCEPTED", "REVOKED")
_NODEID_RE = re.compile(r"^[A-Za-z0-9_./\-]+\.py::\S.*$")
_COUNT_KEYS = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
# (phase is "call"?, outcome) -> categories a record may carry
_ALLOWED = {
    (True, "passed"): {"passed", "xpassed"},
    (True, "failed"): {"failed", "xpass_strict"},
    (True, "skipped"): {"skipped", "xfailed"},
    (False, "passed"): {"phase_ok"},
    (False, "failed"): {"error"},
    (False, "skipped"): {"skipped", "xfailed"},
}
_SUMMARY_WORDS = {"passed": "passed", "failed": "failed", "error": "errors", "errors": "errors",
                  "skipped": "skipped", "xfailed": "xfailed", "xpassed": "xpassed"}
_PROSE_COUNT_RE = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)\b")


def _str_list(v: object, what: str, *, allow_empty: bool = False) -> list[str]:
    if (not isinstance(v, list) or (not v and not allow_empty)
            or not all(isinstance(t, str) and t.strip() for t in v)):
        raise ValueError(f"{what} must be a {'' if allow_empty else 'non-empty '}list of non-blank strings")
    return v


def load_policy(text: str) -> dict:
    """Parse and validate the signature policy; raise ValueError if invalid (the gate then
    fails closed).  ``status`` is the policy lifecycle: only ACCEPTED can excuse a failure."""
    try:
        pol = json.loads(text)
    except ValueError as e:
        raise ValueError(f"signature policy is not valid JSON: {e}") from e
    if not isinstance(pol, dict) or pol.get("schema") != _POLICY_SCHEMA:
        raise ValueError(f"signature policy must be an object with schema == {_POLICY_SCHEMA}")
    if pol.get("status") not in _POLICY_STATUSES:
        raise ValueError(f"signature policy status must be one of {_POLICY_STATUSES}, got {pol.get('status')!r}")
    classes = pol.get("classes")
    if not isinstance(classes, list):
        raise ValueError("signature policy needs a 'classes' list")
    if pol["status"] == "ACCEPTED":
        ref = pol.get("decision_ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("an ACCEPTED policy must cite the owner decision in a non-empty 'decision_ref'")
        if not classes:
            raise ValueError("an ACCEPTED policy needs at least one class")
    for c in classes:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not c["name"]:
            raise ValueError("each signature class needs a non-empty string 'name'")
        if c.get("phase") != "call":
            raise ValueError(f"class {c['name']!r}: only phase 'call' may be tolerated")
        m = c.get("match")
        if not isinstance(m, dict):
            raise ValueError(f"class {c['name']!r}: 'match' object required")
        types = _str_list(m.get("exception_types"), f"class {c['name']!r}: match.exception_types")
        if not all("." in t for t in types):
            raise ValueError(f"class {c['name']!r}: exception types must be fully qualified (module.Name)")
        if "message_contains" in m:
            _str_list(m["message_contains"], f"class {c['name']!r}: match.message_contains")
        d = c.get("deny", {})
        if not isinstance(d, dict):
            raise ValueError(f"class {c['name']!r}: 'deny' must be an object")
        if "exception_types" in d:
            _str_list(d["exception_types"], f"class {c['name']!r}: deny.exception_types")
        if "http_status" in d and (not isinstance(d["http_status"], list)
                                   or not all(isinstance(x, int) and not isinstance(x, bool) for x in d["http_status"])):
            raise ValueError(f"class {c['name']!r}: deny.http_status must be a list of integers")
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


def _denied(chain: list, deny: dict) -> bool:
    for exc in chain:
        if not isinstance(exc, dict):
            return True
        names = {exc.get("type")} | set(exc.get("mro") or [])
        if names & set(deny.get("exception_types", [])):
            return True
        if exc.get("http_status") in deny.get("http_status", []):
            return True
    return False


def _matches_class(rec: dict, pol: dict) -> str | None:
    """Class name if the failure's exception chain matches an approved signature, else None.

    Needs (a) an exception in the chain whose EXACT fully-qualified type is listed and whose
    message contains every token, and (b) no exception in the chain (type or base class) or
    HTTP status in the class's deny list.  Subclasses are not inferred: list them explicitly.
    """
    if pol.get("status") != "ACCEPTED":
        return None
    chain = rec.get("chain")
    if not isinstance(chain, list) or not chain:
        return None
    for cls in pol["classes"]:
        if cls["phase"] != rec.get("when") or _denied(chain, cls.get("deny", {})):
            continue
        m = cls["match"]
        toks = [t.lower() for t in m.get("message_contains", [])]
        for exc in chain:
            if (isinstance(exc, dict) and exc.get("type") in m["exception_types"]
                    and all(t in str(exc.get("message", "")).lower() for t in toks)):
                return cls["name"]
    return None


def _summary_counts(output: str) -> dict[str, int] | None:
    """Counts from pytest's final summary line (None if absent).  Words not listed in
    ``_SUMMARY_WORDS`` (deselected, warnings, ...) are ignored; absent words count 0."""
    summary = parse_summary(output)
    if summary is None:
        return None
    out = dict.fromkeys(_COUNT_KEYS, 0)
    for n, word in _PROSE_COUNT_RE.findall(summary.raw):
        out[_SUMMARY_WORDS[word]] += int(n)
    return out


def _recompute(records: list, collected: list, fail) -> tuple[dict[str, int], dict[str, dict], list[str]]:
    """Validate every record and rebuild per-test terminal outcomes and tallies independently
    of the plugin.  Returns (counts, call-phase failures by node id, error descriptions)."""
    counts = dict.fromkeys(_COUNT_KEYS, 0)
    phases: dict[str, dict[str, dict]] = {}
    call_fail: dict[str, dict] = {}
    errors: list[str] = []
    for r in records:
        if (not isinstance(r, dict) or not isinstance(r.get("nodeid"), str)
                or r.get("when") not in ("setup", "call", "teardown")):
            fail("malformed record in report")
            continue
        nid, when, outcome, cat = r["nodeid"], r["when"], r.get("outcome"), r.get("category")
        if cat not in _ALLOWED.get((when == "call", outcome), set()):
            fail(f"inconsistent or unknown outcome for {nid[:100]} ({when}: outcome={outcome!r}, category={cat!r})")
            continue
        if cat in ("xfailed", "xpassed") and r.get("wasxfail") is not True:
            fail(f"{nid[:100]}: category {cat} without wasxfail")
        if when in phases.setdefault(nid, {}):
            fail(f"duplicate {when} record for {nid[:100]}")
            continue
        phases[nid][when] = r
        if cat == "error":
            counts["errors"] += 1
            errors.append(f"{nid} ({when})")
        elif when == "call" and cat == "passed":
            counts["passed"] += 1
        elif when == "call" and cat in ("failed", "xpass_strict"):
            counts["failed"] += 1
            call_fail[nid] = r
        elif cat in ("skipped", "xfailed", "xpassed") and when in ("call", "setup"):
            counts[cat] += 1
    cset = set(collected)
    if len(cset) != len(collected):
        fail("collection inventory contains duplicate node IDs")
    for nid in sorted(set(phases) - cset):
        fail(f"report has records for a test that was not collected: {nid[:100]}")
    for nid in collected:
        ph = phases.get(nid, {})
        terminal = "call" in ph or ("setup" in ph and ph["setup"].get("outcome") in ("failed", "skipped"))
        if "setup" not in ph or not terminal:
            fail(f"collected test has no terminal outcome in the report: {nid[:100]}")
    return counts, call_fail, errors


def evaluate_report(report: object, exit_code: int | None, allowlist: set[str],
                    policy: dict, output: str | None = None) -> Verdict:
    """Decide from a structured report.  Fail closed on anything unexpected.

    A failure is tolerated only if ALL hold: the policy status is ACCEPTED, the exact node
    ID is in the allowlist, it failed in the ``call`` phase, it is not a strict XPASS, and
    its exception chain matches an approved signature class (exact type + message, no deny).
    A PROPOSED or REVOKED policy excuses nothing: every listed failure stays red.
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
    records, collected = report.get("records"), report.get("collected")
    if not isinstance(records, list):
        fail("report has no 'records' list")
        return v
    if not isinstance(collected, list) or not all(isinstance(x, str) for x in collected):
        fail("report has no collection inventory")
        return v
    cerr = report.get("collect_errors")
    if not isinstance(cerr, list) or cerr:
        fail(f"collection error(s) in report: {cerr!r}"[:200])

    counts, call_fail, errors = _recompute(records, collected, fail)
    if report.get("counts") != counts:
        fail(f"report 'counts' {report.get('counts')!r} disagree with the records ({counts!r})")
    if errors:
        fail(f"{len(errors)} setup/teardown error(s) (never allowlisted): " + "; ".join(e[:100] for e in errors[:5]))
    if counts["passed"] == 0:
        fail("no ordinary passing test (xpassed, xfailed and skipped do not count), so nothing was verified")

    if exit_code == 0 and (call_fail or errors):
        fail("exit code 0 but failures are reported (inconsistent run)")
    if exit_code == 1 and not call_fail and not errors:
        fail("exit code 1 but the report contains no failures or errors")

    text_counts = _summary_counts(output) if output is not None else None
    if text_counts is None:
        fail("no pytest summary line in the text output (cross-check unavailable; truncated run?)")
    else:
        for k in _COUNT_KEYS:
            if text_counts[k] != counts[k]:
                fail(f"text summary reports {text_counts[k]} {k} but the report has {counts[k]}")

    for nid, rec in sorted(call_fail.items()):
        reason = None
        if rec.get("category") == "xpass_strict":
            reason = "strict XPASS is never excused"
        elif nid not in allowlist:
            reason = "not in the known-failure list"
        elif policy.get("status") != "ACCEPTED":
            reason = f"listed, but the signature policy is {policy.get('status')} and cannot excuse failures"
        elif _matches_class(rec, policy) is None:
            reason = "listed, but its failure does not match an approved signature class"
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


def _print_chains(report: object, ids: list[str]) -> None:
    """Diagnostics: show the (already redacted) exception chains of the failures that stayed red."""
    if not isinstance(report, dict) or not isinstance(report.get("records"), list):
        return
    for r in report["records"]:
        if isinstance(r, dict) and r.get("nodeid") in ids and r.get("when") == "call" and r.get("chain"):
            print(f"  diagnostic chain for {r['nodeid']}:")
            for exc in r["chain"][:4]:
                extra = "".join(f" {k}={exc[k]}" for k in ("errno", "http_status") if k in exc)
                print(f"    {exc.get('type')}{extra}: {str(exc.get('message'))[:160]!r}")


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
        rep = _read_json_report(a.report)
        v = evaluate_report(rep, exit_code, allowlist, policy, output)
    else:
        v = evaluate(output, exit_code, allowlist)

    print(f"pytest exit code: {exit_code if exit_code is not None else 'NOT RECORDED'}")
    if a.report:
        print(f"signature policy: status {policy['status']}"
              + ("" if policy["status"] == "ACCEPTED" else " -- cannot excuse any failure (diagnostic mode)"))
    summary = parse_summary(output)
    print(f"pytest summary:   {summary.raw if summary else 'NOT FOUND'}")
    print("Known environmental failures still failing (expected, not gated):")
    for t in v.known_failures_seen:
        print(f"  {t}")
    if v.new_failures:
        print("\nNEW test failure(s) not in the known-environmental list:")
        for t in v.new_failures:
            print(f"  {t}")
        if a.report:
            _print_chains(rep, v.new_failures)
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
