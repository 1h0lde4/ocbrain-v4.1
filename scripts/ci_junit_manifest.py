#!/usr/bin/env python3
"""scripts/ci_junit_manifest.py -- the execution contract of the hosted test job (R1 + R4).

Why this exists
---------------
``scripts/ci_test_gate.py`` decides from pytest's terminal text.  That text cannot say whether a
named test actually ran: ``--deselect``, ``--ignore``, a narrowed path or a new unmatched skip
reason all leave a green terminal summary behind.  This checker reads pytest's own JUnit XML
(xunit2) and compares it with an independently versioned manifest of the tests whose execution
is contractual.  It is an additional step; the gate is unchanged and still decides what it decides.

The contract (spec section 3, H-R1-1)
-------------------------------------
Every manifest entry must have an observed outcome equal to its permitted outcome.  A missing
identity, a duplicate identity or an unmappable identity is red.  Identity is the pair
``(classname, name)`` exactly as xunit2 writes it; it is not a pytest node id and is never
reconstructed as one.  Outcomes are read from the XML structure, never from message text:

========================================  ======================================================
observed testcase                         disposition
========================================  ======================================================
no outcome child                          PASS
``<skipped type="pytest.skip">``          SKIP, with its exact ``message`` as the reason
``<skipped type="pytest.xfail">``         XFAIL
``<failure>`` / ``<error>``               FAIL / ERROR (a strict XPASS is a ``<failure>``)
anything else (untyped skip, two          UNKNOWN: red
outcomes, unrecognised child)
========================================  ======================================================

Entry expectations: ``PASS`` accepts only PASS (a skipped mandatory test is red); ``SKIP`` accepts
PASS or a SKIP with exactly ``skip_reason`` (an approved environmental skip may start to pass);
``XFAIL`` accepts only XFAIL (a pass means the marker no longer applies, a strict XPASS is red).
A testcase that is not in the manifest is red if it failed, errored, skipped, xfailed or is
unclassifiable; a plain pass needs no entry.

Beyond the entries the checker is red on: a missing, unparseable, truncated or DOCTYPE-bearing
report; suite totals that disagree with the testcases; duplicate JUnit identities; a manifest that
is malformed, has duplicate or empty identities, gives A9 an XFAIL expectation (H-D12: no waiver),
or still carries ``pending`` blocks (identities that cannot be known without a Docker-capable host
are never inferred, and an unresolved manifest does not enforce what it has not listed); an entry
whose declared ``condition`` does not hold in the environment; and a pytest or plugin version that
is not the pinned set (a prerelease is never accepted, an unpinned registered plugin is red).

Nothing here proves a test is *good*; it proves the tests the manifest names ran and ended as
the manifest says, under the pinned toolchain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "pytest-execution-manifest/1"
OUTCOMES = ("PASS", "XFAIL", "SKIP")
CRITICALITIES = ("runtime_verification", "security_contract", "known_gap", "environmental")
A9_NAME_PREFIX = "test_a9_"

PASS, SKIP, XFAIL, FAIL, ERROR, UNKNOWN, ABSENT = "PASS", "SKIP", "XFAIL", "FAIL", "ERROR", "UNKNOWN", "ABSENT"

_IGNORED_CHILDREN = frozenset({"system-out", "system-err", "properties"})
_PRERELEASE_RE = re.compile(r"(a|b|rc|dev|alpha|beta|pre|post)\d*", re.IGNORECASE)
_PLUGIN_RE = re.compile(r"^\s+(?P<name>\S.*?)-(?P<ver>\d+(?:\.\d+)+\S*) at ")
_CONDITION_RE = re.compile(r"^(?P<var>[A-Za-z_][A-Za-z0-9_]*)=(?P<val>.*)$")


# =================================================================================================
# JUnit
# =================================================================================================


@dataclass(frozen=True)
class CaseOutcome:
    classname: str
    name: str
    outcome: str  # PASS | SKIP | XFAIL | FAIL | ERROR | UNKNOWN
    reason: str | None = None  # SKIP: the exact message; FAIL: the first 200 chars of the message
    detail: str | None = None  # why UNKNOWN

    @property
    def key(self) -> tuple[str, str]:
        return (self.classname, self.name)


@dataclass(frozen=True)
class JunitReport:
    cases: tuple[CaseOutcome, ...]
    problems: tuple[str, ...]  # report-level problems (all red)
    sha256: str | None


def classify_testcase(tc: ET.Element) -> CaseOutcome:
    """Read one ``<testcase>``.  Only structure counts; message text never decides an outcome
    except as the reason string of a SKIP."""
    classname = tc.get("classname")
    name = tc.get("name")
    if classname is None or name is None or not name:
        return CaseOutcome(classname or "", name or "", UNKNOWN, detail="testcase without classname or name")
    kids = [c for c in tc if c.tag not in _IGNORED_CHILDREN]
    if not kids:
        return CaseOutcome(classname, name, PASS)
    if len(kids) > 1:
        return CaseOutcome(classname, name, UNKNOWN, detail=f"{len(kids)} outcome children")
    kid = kids[0]
    msg = kid.get("message") or ""
    if kid.tag == "failure":
        return CaseOutcome(classname, name, FAIL, reason=msg[:200])
    if kid.tag == "error":
        return CaseOutcome(classname, name, ERROR, reason=msg[:200])
    if kid.tag == "skipped":
        typ = kid.get("type")
        if typ == "pytest.skip":
            return CaseOutcome(classname, name, SKIP, reason=msg)
        if typ == "pytest.xfail":
            return CaseOutcome(classname, name, XFAIL, reason=msg)
        return CaseOutcome(classname, name, UNKNOWN, detail=f"skipped with unrecognised type {typ!r}")
    return CaseOutcome(classname, name, UNKNOWN, detail=f"unrecognised child <{kid.tag}>")


def parse_junit(path: Path) -> JunitReport:
    """Parse a pytest xunit2 report.  Any structural problem is returned, never swallowed."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return JunitReport((), (f"cannot read the JUnit report {path}: {exc}",), None)
    sha = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return JunitReport((), (f"the JUnit report is not valid UTF-8: {exc}",), sha)
    if not text.strip():
        return JunitReport((), ("the JUnit report is empty",), sha)
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        return JunitReport((), ("the JUnit report carries a DOCTYPE or entity declaration",), sha)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return JunitReport((), (f"the JUnit report is not well-formed XML (truncated?): {exc}",), sha)

    if root.tag not in ("testsuites", "testsuite"):
        return JunitReport((), (f"unexpected root element <{root.tag}>",), sha)
    suites = [root] if root.tag == "testsuite" else [e for e in root if e.tag == "testsuite"]
    if not suites:
        return JunitReport((), ("the JUnit report has no <testsuite>",), sha)

    problems: list[str] = []
    cases: list[CaseOutcome] = []
    for suite in suites:
        for tc in suite.iter("testcase"):
            cases.append(classify_testcase(tc))
    if not cases:
        problems.append("the JUnit report contains no testcases")

    # Suite totals must agree with what the testcases say (a truncated or hand-edited report).
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    totals_readable = True
    for suite in suites:
        for key in totals:
            try:
                totals[key] += int(suite.get(key, ""))
            except ValueError:
                totals_readable = False
                problems.append(f"testsuite {suite.get('name')!r} has no integer {key!r} attribute")
    if totals_readable:
        counted = {
            "tests": len(cases),
            "failures": sum(c.outcome == FAIL for c in cases),
            "errors": sum(c.outcome == ERROR for c in cases),
            "skipped": sum(c.outcome in (SKIP, XFAIL) for c in cases),
        }
        for key, want in counted.items():
            if totals[key] != want:
                problems.append(f"suite totals disagree with the testcases: {key}={totals[key]} but counted {want}")
    return JunitReport(tuple(cases), tuple(problems), sha)


# =================================================================================================
# manifest
# =================================================================================================


@dataclass(frozen=True)
class Entry:
    id: str
    source: str
    classname: str
    name: str
    expected: str
    skip_reason: str | None
    condition: str | None
    criticality: str
    required: bool
    provenance: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.classname, self.name)


@dataclass(frozen=True)
class Pins:
    pytest: str
    plugins: Mapping[str, str]


@dataclass(frozen=True)
class Manifest:
    manifest_version: str
    pins: Pins
    entries: tuple[Entry, ...]
    pending: tuple[Mapping[str, Any], ...]
    sha256: str


def _norm_plugin(name: str) -> str:
    return name.lower().replace("_", "-")


def _load_entry(index: int, e: object) -> tuple[Entry | None, list[str]]:
    """Validate one manifest entry in isolation.  Returns (entry, problems); no entry if unusable."""
    if not isinstance(e, dict):
        return None, [f"entries[{index}] is not an object"]
    where = f"entry {e.get('id')!r}"
    problems: list[str] = []
    for field_name in ("id", "source", "junit_classname", "junit_name", "expected_outcome", "criticality", "provenance"):
        v = e.get(field_name)
        if not isinstance(v, str) or not v:
            problems.append(f"{where}: {field_name} must be a non-empty string")
    if problems:
        return None, problems
    if e["expected_outcome"] not in OUTCOMES:
        return None, [f"{where}: expected_outcome {e['expected_outcome']!r} not in {OUTCOMES}"]
    if e["criticality"] not in CRITICALITIES:
        problems.append(f"{where}: criticality {e['criticality']!r} not in {CRITICALITIES}")
    skip_reason = e.get("skip_reason")
    if e["expected_outcome"] == "SKIP":
        if not isinstance(skip_reason, str) or not skip_reason:
            problems.append(f"{where}: a SKIP entry needs the exact skip_reason")
    elif skip_reason is not None:
        problems.append(f"{where}: skip_reason is only valid on SKIP entries")
    cond = e.get("condition")
    if cond is not None and (not isinstance(cond, str) or not _CONDITION_RE.match(cond)):
        problems.append(f"{where}: condition must look like VAR=value or VAR=unset")
    required = e.get("required", True)
    if not isinstance(required, bool):
        problems.append(f"{where}: required must be a boolean")
        required = True
    # H-D12 / M20: A9 is a security assertion; it gets no expected-failure or skip waiver.
    if e["junit_name"].startswith(A9_NAME_PREFIX) and e["expected_outcome"] != "PASS":
        problems.append(f"{where}: an A9 test may only expect PASS (no XFAIL or SKIP waiver, H-D12)")
    entry = Entry(e["id"], e["source"], e["junit_classname"], e["junit_name"], e["expected_outcome"],
                  skip_reason if isinstance(skip_reason, str) else None,
                  cond if isinstance(cond, str) else None, e["criticality"], required, e["provenance"])
    return entry, problems


def load_manifest(path: Path) -> tuple[Manifest | None, list[str]]:
    """Load and validate the manifest.  Anything malformed is a problem (red), never a default."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, [f"cannot read the manifest {path}: {exc}"]
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        return None, [f"the manifest is not valid JSON: {exc}"]
    if not isinstance(doc, dict):
        return None, ["the manifest is not a JSON object"]
    problems: list[str] = []
    if doc.get("schema_version") != MANIFEST_SCHEMA:
        problems.append(f"schema_version must be {MANIFEST_SCHEMA!r}, found {doc.get('schema_version')!r}")
    version = doc.get("manifest_version")
    if not isinstance(version, str) or not re.match(r"^\d+\.\d+\.\d+$", version):
        problems.append("manifest_version must be a semantic version string")

    pins_raw = doc.get("pins")
    pins: Pins | None = None
    if not isinstance(pins_raw, dict) or not isinstance(pins_raw.get("pytest"), str) \
            or not isinstance(pins_raw.get("plugins"), dict):
        problems.append("pins must be {pytest: str, plugins: {name: version}}")
    else:
        plugins = {_norm_plugin(k): v for k, v in pins_raw["plugins"].items()}
        if not all(isinstance(v, str) for v in plugins.values()):
            problems.append("every plugin pin must be a version string")
        elif len(plugins) != len(pins_raw["plugins"]):
            problems.append("duplicate plugin pin after name normalisation")
        else:
            pins = Pins(pins_raw["pytest"], plugins)
        for label, ver in [("pytest", pins_raw["pytest"])] + list(plugins.items()):
            if isinstance(ver, str) and not re.match(r"^\d+(\.\d+)*$", ver):
                problems.append(f"pin {label}=={ver!r} must be an exact stable release (no prerelease)")

    entries: list[Entry] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    raw_entries = doc.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        problems.append("entries must be a non-empty list")
        raw_entries = []
    for i, e in enumerate(raw_entries):
        entry, eproblems = _load_entry(i, e)
        problems.extend(eproblems)
        if entry is None:
            continue
        where = f"entry {entry.id!r}"
        if entry.id in seen_ids:
            problems.append(f"{where}: duplicate manifest id")
        seen_ids.add(entry.id)
        if entry.key in seen_keys:
            problems.append(f"{where}: duplicate JUnit identity {entry.key}")
        seen_keys.add(entry.key)
        entries.append(entry)

    pending_raw = doc.get("pending", [])
    if not isinstance(pending_raw, list) or not all(isinstance(p, dict) and isinstance(p.get("id"), str) for p in pending_raw):
        problems.append("pending must be a list of objects with an id")
        pending_raw = []
    if problems or pins is None:
        return None, problems or ["pins missing"]
    return Manifest(str(version), pins, tuple(entries), tuple(pending_raw), hashlib.sha256(raw).hexdigest()), []


# =================================================================================================
# environment (pytest and plugin versions)
# =================================================================================================


@dataclass(frozen=True)
class PytestEnvironment:
    pytest_version: str | None
    plugins: Mapping[str, str]
    problem: str | None = None


def parse_pytest_version_output(text: str) -> PytestEnvironment:
    """Parse ``pytest --version --version``: the version and the REGISTERED third-party plugins.

    This is activation, not installation: a plugin that is installed but not registered (or the
    reverse) is what the output shows.
    """
    m = re.search(r"^pytest (?:version )?(\d\S*)|This is pytest version (\d\S*)", text, re.MULTILINE)
    version = None
    if m:
        version = (m.group(1) or m.group(2)).rstrip(",")
    plugins: dict[str, str] = {}
    in_block = False
    for line in text.splitlines():
        if line.startswith("registered third-party plugins:"):
            in_block = True
            continue
        if in_block:
            pm = _PLUGIN_RE.match(line)
            if pm:
                plugins[_norm_plugin(pm.group("name"))] = pm.group("ver")
            elif line.strip():
                in_block = False
    if version is None:
        return PytestEnvironment(None, plugins, "could not read the pytest version from `pytest --version --version`")
    return PytestEnvironment(version, plugins)


def detect_environment(runner: Callable[[Sequence[str]], tuple[int, str]] | None = None) -> PytestEnvironment:
    def _run(argv: Sequence[str]) -> tuple[int, str]:
        cp = subprocess.run(list(argv), capture_output=True, text=True, timeout=120, check=False)
        return cp.returncode, cp.stdout + "\n" + cp.stderr

    run = runner or _run
    try:
        rc, out = run([sys.executable, "-m", "pytest", "--version", "--version"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return PytestEnvironment(None, {}, f"could not run pytest to read its version: {exc}")
    if rc != 0:
        return PytestEnvironment(None, {}, f"`pytest --version --version` exited {rc}")
    return parse_pytest_version_output(out)


def check_environment(pins: Pins, env: PytestEnvironment) -> list[str]:
    """Red findings for a toolchain that is not the pinned one (H-D9, M16, M21)."""
    if env.problem:
        return [env.problem]
    def note(version: str) -> str:
        return " (a prerelease or post-release)" if _PRERELEASE_RE.search(version) else ""

    out: list[str] = []
    if env.pytest_version != pins.pytest:
        out.append(f"pytest {env.pytest_version} is not the pinned {pins.pytest}{note(env.pytest_version or '')}")
    for name, want in pins.plugins.items():
        got = env.plugins.get(name)
        if got is None:
            out.append(f"pinned plugin {name}=={want} is not registered (missing or not activated)")
        elif got != want:
            out.append(f"plugin {name} {got} is not the pinned {want}{note(got)}")
    for name, got in env.plugins.items():
        if name not in pins.plugins:
            out.append(f"registered plugin {name} {got} is not in the pinned set{note(got)}")
    return out


# =================================================================================================
# evaluation
# =================================================================================================


@dataclass(frozen=True)
class EntryResult:
    id: str
    key: tuple[str, str]
    expected: str
    observed: str
    observed_reason: str | None
    ok: bool
    why: str


@dataclass
class Evaluation:
    entries: list[EntryResult] = field(default_factory=list)
    unlisted_reds: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # report, manifest, environment, pending

    @property
    def red_entries(self) -> list[EntryResult]:
        return [e for e in self.entries if not e.ok]

    @property
    def green(self) -> bool:
        return not (self.red_entries or self.unlisted_reds or self.problems)


def _condition_holds(cond: str, environ: Mapping[str, str]) -> bool:
    m = _CONDITION_RE.match(cond)
    assert m is not None  # validated at load time
    var, val = m.group("var"), m.group("val")
    return var not in environ if val == "unset" else environ.get(var) == val


def _judge(entry: Entry, case: CaseOutcome | None) -> tuple[bool, str]:
    if case is None:
        return (not entry.required, "absent from the report" + (" (not required)" if not entry.required else ""))
    out = case.outcome
    if out == UNKNOWN:
        return False, f"unclassifiable outcome ({case.detail})"
    if out in (FAIL, ERROR):
        if entry.expected == "XFAIL" and out == FAIL and "XPASS(strict)" in (case.reason or ""):
            return False, "strict XPASS: the expected failure no longer fails"
        return False, f"{out.lower()}: {case.reason or ''}".rstrip()
    if entry.expected == "PASS":
        if out == PASS:
            return True, "passed"
        if out == SKIP:
            return False, f"mandatory test skipped: {case.reason!r}"
        return False, "mandatory test xfailed"
    if entry.expected == "SKIP":
        if out == PASS:
            return True, "passed (an approved environmental skip may start to run)"
        if out == SKIP and case.reason == entry.skip_reason:
            return True, "skipped with the exact approved reason"
        if out == SKIP:
            return False, f"skipped with an unapproved reason {case.reason!r}"
        return False, "xfailed where a skip or pass was expected"
    # expected XFAIL
    if out == XFAIL:
        return True, "xfailed as expected"
    if out == PASS:
        return False, "passed: the xfail marker no longer applies"
    return False, f"skipped where an xfail was expected: {case.reason!r}"


def evaluate(
    report: JunitReport,
    manifest: Manifest,
    env: PytestEnvironment,
    environ: Mapping[str, str],
) -> Evaluation:
    ev = Evaluation()
    ev.problems.extend(report.problems)
    ev.problems.extend(check_environment(manifest.pins, env))
    for p in manifest.pending:
        ev.problems.append(
            f"MANIFEST_PENDING {p['id']}: not enforced until resolved "
            f"({p.get('reason', 'no reason recorded')}); blocked on {p.get('blocked_on', 'unspecified')}"
        )

    by_key: dict[tuple[str, str], list[CaseOutcome]] = {}
    for c in report.cases:
        by_key.setdefault(c.key, []).append(c)
    for key, group in by_key.items():
        if len(group) > 1:
            ev.problems.append(f"duplicate JUnit identity {key} appears {len(group)} times")

    listed = {e.key for e in manifest.entries}
    for entry in manifest.entries:
        group = by_key.get(entry.key, [])
        if entry.condition and not _condition_holds(entry.condition, environ):
            ev.entries.append(EntryResult(entry.id, entry.key, entry.expected, "n/a", None, False,
                                          f"declared condition {entry.condition!r} does not hold in this environment"))
            continue
        if len(group) > 1:
            ev.entries.append(EntryResult(entry.id, entry.key, entry.expected, "DUPLICATE", None, False,
                                          "duplicate JUnit identity"))
            continue
        case = group[0] if group else None
        ok, why = _judge(entry, case)
        ev.entries.append(EntryResult(entry.id, entry.key, entry.expected, case.outcome if case else ABSENT,
                                      case.reason if case else None, ok, why))

    for key, group in by_key.items():
        if key in listed:
            continue
        for c in group:
            if c.outcome == PASS:
                continue
            what = {
                FAIL: "unexpected failure", ERROR: "unexpected error", SKIP: "unapproved skip",
                XFAIL: "xfail outcome with no manifest entry", UNKNOWN: "unclassifiable outcome",
            }[c.outcome]
            ev.unlisted_reds.append(f"{what}: {c.classname}::{c.name}" + (f" ({c.reason})" if c.reason else "")
                                    + (f" [{c.detail}]" if c.detail else ""))
    return ev


# =================================================================================================
# CLI
# =================================================================================================


def to_report_json(ev: Evaluation, manifest: Manifest | None, report: JunitReport | None, env: PytestEnvironment) -> dict[str, Any]:
    return {
        "green": ev.green,
        "manifest_version": manifest.manifest_version if manifest else None,
        "manifest_sha256": manifest.sha256 if manifest else None,
        "junit_sha256": report.sha256 if report else None,
        "pytest_version": env.pytest_version,
        "plugins": dict(env.plugins),
        "problems": ev.problems,
        "unlisted_reds": ev.unlisted_reds,
        "red_entries": [e.id for e in ev.red_entries],
        "entries": [
            {"id": e.id, "classname": e.key[0], "name": e.key[1], "expected": e.expected, "observed": e.observed,
             "reason": e.observed_reason, "ok": e.ok, "why": e.why}
            for e in ev.entries
        ],
    }


def check_main(args: argparse.Namespace, *, env: PytestEnvironment | None = None,
               environ: Mapping[str, str] | None = None) -> int:
    manifest, mproblems = load_manifest(args.manifest)
    report = parse_junit(args.junit)
    observed_env = env or detect_environment()
    lines: list[str] = []
    if manifest is None:
        ev = Evaluation(problems=mproblems + list(report.problems))
    else:
        ev = evaluate(report, manifest, observed_env, os.environ if environ is None else environ)
    out = to_report_json(ev, manifest, report, observed_env)
    if args.report:
        args.report.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines.append(f"pytest {observed_env.pytest_version}; registered plugins: {dict(observed_env.plugins)}")
    if manifest:
        lines.append(f"manifest {manifest.manifest_version} ({len(manifest.entries)} entries, sha256 {manifest.sha256[:12]})")
    for e in ev.entries:
        lines.append(f"  {'ok ' if e.ok else 'RED'} {e.id}: expected {e.expected}, observed {e.observed} -- {e.why}")
    for p in ev.problems:
        lines.append(f"RED  {p}")
    for u in ev.unlisted_reds:
        lines.append(f"RED  {u}")
    verdict = "GREEN" if ev.green else (
        f"RED ({len(ev.red_entries)} manifest entries, {len(ev.unlisted_reds)} unlisted outcomes, "
        f"{len(ev.problems)} report/manifest/environment/pending problems)"
    )
    lines.append(f"junit manifest check: {verdict}")
    text = "\n".join(lines)
    print(text)
    if getattr(args, "text", None):
        args.text.write_text(text + "\n", encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("### JUnit execution manifest\n\n```\n" + text + "\n```\n")
        except OSError:
            pass
    return 0 if ev.green else 1


def verdict_main(args: argparse.Namespace) -> int:
    """Decide the job from what the recording step left behind (the recording step never fails).

    Red unless every ``--exit-code-file`` exists and holds exactly ``0``, and every
    ``--require-file`` exists and is non-empty.  A missing or unreadable file is red, never skipped:
    the recording step may not have run at all.
    """
    problems: list[str] = []
    if not args.exit_code_file:
        problems.append("no --exit-code-file given: there is nothing to decide from")
    for f in args.exit_code_file:
        try:
            raw = f.read_text(encoding="utf-8").strip()
        except OSError as exc:
            problems.append(f"{f}: cannot read the recorded exit code: {exc}")
            continue
        if raw != "0":
            problems.append(f"{f}: recorded exit code is {raw!r}, not 0")
    for f in args.require_file:
        try:
            size = f.stat().st_size
        except OSError as exc:
            problems.append(f"{f}: required evidence file is missing: {exc}")
            continue
        if size == 0:
            problems.append(f"{f}: required evidence file is empty")
    if problems:
        print("execution checks verdict: RED")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"execution checks verdict: GREEN ({len(args.exit_code_file)} exit codes, {len(args.require_file)} evidence files)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ck = sub.add_parser("check", help="compare a pytest JUnit report with the execution manifest")
    ck.add_argument("--junit", required=True, type=Path)
    ck.add_argument("--manifest", required=True, type=Path)
    ck.add_argument("--report", type=Path, default=None, help="write the machine-readable result here")
    ck.add_argument("--text", type=Path, default=None, help="also write the printed result to this file")
    vd = sub.add_parser("verdict", help="fail unless the recorded checks passed and their evidence exists")
    vd.add_argument("--exit-code-file", action="append", type=Path, default=[])
    vd.add_argument("--require-file", action="append", type=Path, default=[])
    a = ap.parse_args(argv)
    if a.cmd == "verdict":
        return verdict_main(a)
    return check_main(a)


if __name__ == "__main__":
    sys.exit(main())
