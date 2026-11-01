"""Tests for scripts/ci_test_gate.py and its wiring in .github/workflows/ci.yml (FZ-07).

FZ-07: the ``tests`` job discarded pytest's exit code and gated only on
``^FAILED `` lines, so collection errors, setup errors, INTERNALERROR,
zero-collected and killed runs all passed the gate. These tests pin:

* the decision logic (``evaluate``) over the full scenario matrix, using output
  shapes taken from real pytest runs;
* the CLI contract (exit codes 0 / 1 / 2);
* the wiring: the REAL ``run:`` blocks of the "Run test suite" and "Gate ..."
  steps are executed under ``bash -e`` (GitHub's default shell, no pipefail)
  with a fake ``pytest``, so re-introducing ``|| true`` or dropping the exit
  code record turns these red.

The known-failure list itself is not touched or re-validated here.
"""
from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ci_test_gate as gate  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
ALLOWLIST_FILE = ROOT / "docs" / "architecture" / "D10_KNOWN_ENVIRONMENTAL_FAILURES.txt"

KNOWN_A = "tests/test_known.py::test_a"
KNOWN_B = "tests/test_known.py::test_b"
ALLOW = {KNOWN_A, KNOWN_B}
OK_SUMMARY = "1788 passed, 14 skipped, 1 xfailed in 100.00s (0:01:40)"


def _failed(*ids: str, reason: str = " - AssertionError") -> str:
    return "".join(f"FAILED {i}{reason}\n" for i in ids)


# (id, output, exit_code, expected_ok)
MATRIX = [
    ("clean pass", f"....\n{OK_SUMMARY}\n", 0, True),
    ("clean pass with decoration", f"=== {OK_SUMMARY} ===\n", 0, True),
    ("warnings in summary", "1 passed, 2 warnings in 0.01s\n", 0, True),
    ("xfail only", "1 passed, 1 xfailed in 0.02s\n", 0, True),
    ("one listed failure", _failed(KNOWN_A) + "1 failed, 1787 passed in 1.0s\n", 1, True),
    ("two listed failures", _failed(KNOWN_A, KNOWN_B) + "2 failed, 1786 passed in 1.0s\n", 1, True),
    ("listed failure without reason suffix", f"FAILED {KNOWN_A}\n1 failed, 5 passed in 1.0s\n", 1, True),
    ("stale allowlist entry, nothing failing", "1788 passed in 1.0s\n", 0, True),
    ("captured stdout 'ERROR ...' line inside a listed failure is not a pytest ERROR entry",
     "--- Captured stdout call ---\nERROR connection refused\nERROR foo.bar failed\n"
     + _failed(KNOWN_A) + "1 failed, 1787 passed in 1.0s\n", 1, True),
    ("logged ERROR line inside listed failure is not a pytest ERROR entry",
     "--- Captured log call ---\nERROR    root:mod.py:12 something logged\n"
     + _failed(KNOWN_A) + "1 failed, 1787 passed in 1.0s\n", 1, True),
    # --- must fail ---
    ("unlisted failure", _failed("tests/test_new.py::test_x") + "1 failed, 1787 passed in 1.0s\n", 1, False),
    ("listed + unlisted failure",
     _failed(KNOWN_A, "tests/test_new.py::test_x") + "2 failed, 1786 passed in 1.0s\n", 1, False),
    ("strict XPASS surfaces as unlisted FAILED",
     "FAILED tests/test_i.py::test_hint - [XPASS(strict)] needs hint\n1 failed, 1787 passed in 1.0s\n", 1, False),
    ("fixture setup ERROR, exit 1",
     "ERROR tests/test_a.py::test_x - RuntimeError: boom\n1786 passed, 1 error in 1.0s\n", 1, False),
    ("ERROR entry listed although the summary counts none (inconsistent run)",
     "ERROR tests/a.py::t - boom\n1788 passed in 1.0s\n", 0, False),
    ("ERROR entry with a parametrize id containing spaces",
     "ERROR tests/a.py::t[a b] - boom\n1788 passed in 1.0s\n", 0, False),
    ("teardown ERROR, exit 1", "ERROR tests/test_a.py::test_x - boom\n2 passed, 1 error in 0.02s\n", 1, False),
    ("collection ERROR, exit 2",
     "ERROR collecting tests/test_a.py\nERROR tests/test_a.py\n"
     "!!! Interrupted: 1 error during collection !!!\n1 error in 0.23s\n", 2, False),
    ("collection ERROR hides a listed failure (exit 2)",
     _failed(KNOWN_A) + "ERROR tests/test_a.py - ImportError\n1 failed, 1 error in 1.0s\n", 2, False),
    ("listed failure plus setup error (exit 1)",
     _failed(KNOWN_A) + "ERROR tests/test_a.py::t - x\n1 failed, 1 passed, 1 error in 1.0s\n", 1, False),
    ("INTERNALERROR without FAILED line", "INTERNALERROR> Traceback\nINTERNALERROR> KeyError\n", 3, False),
    ("INTERNALERROR even with a clean-looking summary and exit 0",
     f"INTERNALERROR> boom\n{OK_SUMMARY}\n", 0, False),
    ("usage error", "ERROR: usage: pytest [options]\n", 4, False),
    ("nothing collected", "no tests ran in 0.01s\n", 5, False),
    ("interrupted (130)", "....\n", 130, False),
    ("killed / OOM (137) with truncated output", "....\n", 137, False),
    ("pytest not found (127)", "bash: pytest: command not found\n", 127, False),
    ("exit code not recorded", f"{OK_SUMMARY}\n", None, False),
    # Only the exit code reveals these: complete, clean-looking output.
    ("clean summary but segfault at interpreter exit (139)", f"{OK_SUMMARY}\n", 139, False),
    ("clean summary but exit 2", f"{OK_SUMMARY}\n", 2, False),
    ("clean summary but exit 5", f"{OK_SUMMARY}\n", 5, False),
    ("exit 1 and nothing parseable", "something went wrong\n", 1, False),
    ("exit 0 but FAILED line present", _failed(KNOWN_A) + "1 failed, 1787 passed in 1.0s\n", 0, False),
    ("exit 0 but summary reports an error", "1787 passed, 1 error in 1.0s\n", 0, False),
    ("exit 0 but nothing passed (all skipped)", "14 skipped in 1.0s\n", 0, False),
    ("summary count exceeds identified FAILED lines",
     _failed(KNOWN_A, KNOWN_B) + "3 failed, 1785 passed in 1.0s\n", 1, False),
    ("exit 1 with no failures and no errors reported", "1788 passed in 1.0s\n", 1, False),
    ("CR-terminated FAILED id never matches the list (preserved fail-closed)",
     f"FAILED {KNOWN_A}\r\n1 failed, 1787 passed in 1.0s\r\n", 1, False),
    ("empty output, exit 0", "", 0, False),
]


@pytest.mark.parametrize("name,output,code,expected", MATRIX, ids=[m[0] for m in MATRIX])
def test_gate_matrix(name: str, output: str, code: int | None, expected: bool) -> None:
    v = gate.evaluate(output, code, ALLOW)
    assert v.ok is expected, (name, v.reasons)
    assert bool(v.reasons) is (not expected)


def test_new_failures_and_known_failures_are_reported_separately() -> None:
    out = _failed(KNOWN_A, "tests/test_new.py::test_x") + "2 failed, 5 passed in 1.0s\n"
    v = gate.evaluate(out, 1, ALLOW)
    assert v.known_failures_seen == [KNOWN_A]
    assert v.new_failures == ["tests/test_new.py::test_x"]


def test_errors_are_never_allowlisted() -> None:
    # Even an allowlist naming the exact node ID cannot excuse an ERROR entry.
    out = "ERROR tests/test_known.py::test_a - boom\n3 passed, 1 error in 1.0s\n"
    assert not gate.evaluate(out, 1, {KNOWN_A, "tests/test_known.py::test_a - boom"}).ok


def test_summary_parser_uses_last_summary_line() -> None:
    out = "99 passed in 0.01s\n1 failed, 3 passed in 1.0s\n"  # bare decoy printed by a test, then the real one
    s = gate.parse_summary(out)
    assert s is not None and (s.failed, s.passed) == (1, 3)


def test_allowlist_semantics_unchanged() -> None:
    text = "# comment\n\n" + KNOWN_A + "\n" + KNOWN_A + "\n  indented::never\n" + KNOWN_B + "\n"
    assert gate.parse_allowlist(text) == {KNOWN_A, KNOWN_B, "  indented::never"}
    # "id - reason" is cut at the first " - " exactly like the previous sed.
    assert gate.parse_failed_ids("FAILED a::b[x - y] - reason\n") == {"a::b[x"}


def test_real_allowlist_file_parses_to_node_ids() -> None:
    entries = gate.parse_allowlist(ALLOWLIST_FILE.read_bytes().decode("utf-8"))
    assert entries, "allowlist parsed empty"
    assert all("::" in e and e.startswith("tests/") for e in entries)


# --------------------------------------------------------------------- CLI

def _run_cli(tmp: Path, output: str | None, code: str | None, allow: str | None = "# none\n"):
    args = [sys.executable, str(ROOT / "scripts" / "ci_test_gate.py")]
    out_f, code_f, allow_f = tmp / "out.txt", tmp / "rc.txt", tmp / "allow.txt"
    if output is not None:
        out_f.write_bytes(output.encode())
    if code is not None:
        code_f.write_text(code)
    if allow is not None:
        allow_f.write_text(allow)
    args += ["--output", str(out_f), "--exit-code-file", str(code_f), "--allowlist", str(allow_f)]
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def test_cli_pass(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, f"{OK_SUMMARY}\n", "0\n")
    assert r.returncode == 0 and "Test gate passed" in r.stdout


def test_cli_fail_prints_reason(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, "ERROR collecting tests/a.py\n1 error in 0.1s\n", "2\n")
    assert r.returncode == 1
    assert "TEST GATE FAILED" in r.stdout and "exited with code 2" in r.stdout


def test_cli_fail_on_unlisted_failure_names_it(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, _failed("tests/test_new.py::test_x") + "1 failed, 5 passed in 1s\n", "1\n")
    assert r.returncode == 1 and "tests/test_new.py::test_x" in r.stdout


@pytest.mark.parametrize("code", [None, "", "abc\n"])
def test_cli_unrecorded_or_garbled_exit_code_fails(tmp_path: Path, code: str | None) -> None:
    r = _run_cli(tmp_path, f"{OK_SUMMARY}\n", code)
    assert r.returncode == 1 and "not recorded" in r.stdout


def test_cli_cr_in_output_is_not_normalised_away(tmp_path: Path) -> None:
    # Same shape as the unit case, but through the file-reading path: a CR-terminated
    # node ID must not be silently "fixed" into matching the list.
    r = _run_cli(tmp_path, f"FAILED {KNOWN_A}\r\n1 failed, 1787 passed in 1.0s\r\n", "1\n", allow=KNOWN_A + "\n")
    assert r.returncode == 1


def test_cli_cr_in_allowlist_is_not_normalised_away(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, _failed(KNOWN_A) + "1 failed, 1787 passed in 1.0s\n", "1\n", allow=KNOWN_A + "\r\n")
    assert r.returncode == 1


def test_cli_listed_failure_passes_through_the_file_path(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, _failed(KNOWN_A) + "1 failed, 1787 passed in 1.0s\n", "1\n", allow=KNOWN_A + "\n")
    assert r.returncode == 0 and KNOWN_A in r.stdout


def test_cli_missing_output_fails(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, None, "0\n")
    assert r.returncode == 1


def test_cli_missing_allowlist_is_a_gate_error(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, f"{OK_SUMMARY}\n", "0\n", allow=None)
    assert r.returncode == 2 and "GATE ERROR" in r.stdout


# ------------------------------------------------------------------ wiring

def _tests_job_steps() -> dict[str, str]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for st in doc["jobs"]["tests"]["steps"]:
        n = st.get("name", "")
        if n.startswith("Run test suite"):
            found["run"] = st["run"]
        elif n.startswith("Gate on"):
            found["gate"] = st["run"]
    assert set(found) == {"run", "gate"}, f"expected both steps in the tests job, found {sorted(found)}"
    return found


_NEEDS_BASH = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="wiring test executes the workflow's bash steps",
)


_POLICY_REL = "docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURE_SIGNATURE.json"
_HF_CHAIN = [{"type": "builtins.ConnectionError", "mro": ["builtins.OSError", "builtins.Exception"],
              "message": "Can't reach huggingface.co"}]


def _synth_report(output: str, rc: int) -> dict | None:
    """The schema-2 structured report the real plugin would write for a run that printed ``output``.

    None where a real run would leave no report (no final summary line = killed or truncated;
    INTERNALERROR).  One record set per counted test; failures carry a network-type chain.
    The text summary is deliberately NOT forced to agree: a canned output whose FAILED lines
    disagree with its summary yields a report that disagrees too, and the gate must go red.
    """
    sc = gate._summary_counts(output)
    if sc is None or "INTERNALERROR" in output:
        return None

    def rec(nid, when, outcome, cat, chain=(), xf=False):
        return {"nodeid": nid, "when": when, "outcome": outcome, "category": cat, "wasxfail": xf, "chain": list(chain)}

    records: list[dict] = []
    collected: list[str] = []

    def test(nid, call_outcome, call_cat, chain=(), xf=False):
        collected.append(nid)
        records.extend([rec(nid, "setup", "passed", "phase_ok"),
                        rec(nid, "call", call_outcome, call_cat, chain, xf),
                        rec(nid, "teardown", "passed", "phase_ok")])

    for i in range(sc["passed"]):
        test(f"tests/t.py::p{i}", "passed", "passed")
    for nid in sorted(gate.parse_failed_ids(output)):
        test(nid, "failed", "failed", _HF_CHAIN)
    for i in range(sc["skipped"]):
        test(f"tests/t.py::s{i}", "skipped", "skipped")
    for i in range(sc["xfailed"]):
        test(f"tests/t.py::xf{i}", "skipped", "xfailed", xf=True)
    for i in range(sc["xpassed"]):
        test(f"tests/t.py::xp{i}", "passed", "xpassed", xf=True)
    collecting = "ERROR collecting" in output
    for i in range(0 if collecting else sc["errors"]):
        nid = f"tests/e.py::e{i}"
        collected.append(nid)
        records.append(rec(nid, "setup", "failed", "error", _HF_CHAIN))
    counts = dict.fromkeys(("passed", "failed", "errors", "skipped", "xfailed", "xpassed"), 0)
    for r in records:
        if r["category"] == "error":
            counts["errors"] += 1
        elif r["when"] == "call" and r["category"] in ("passed", "failed", "skipped", "xfailed", "xpassed"):
            counts[{"passed": "passed", "failed": "failed", "skipped": "skipped",
                    "xfailed": "xfailed", "xpassed": "xpassed"}[r["category"]]] += 1
    return {"schema": 2, "complete": True, "plugin_fault": None, "exitstatus": rc, "collected": collected,
            "counts": counts, "records": records, "collect_errors": ["tests/a.py"] if collecting else []}


def _job_is_red(tmp: Path, pytest_output: str, pytest_rc: int, run_step1: bool = True,
                real_policy: bool = False) -> bool:
    """Run the workflow's two real steps with a fake pytest; True if either step fails."""
    steps = _tests_job_steps()
    bindir = tmp / "bin"
    bindir.mkdir()
    shim = bindir / "pytest"
    # R-1: the real workflow now passes --ci-gate-report=PATH; the fake pytest (the
    # external boundary here) writes the structured report the real plugin would
    # have written for this canned output, when it would have written one.
    shim.write_text(
        '#!/bin/bash\n'
        'for a in "$@"; do case "$a" in --ci-gate-report=*) '
        '[ -f "$FAKE_REPORT" ] && cp "$FAKE_REPORT" "${a#--ci-gate-report=}";; esac; done\n'
        'cat "$FAKE_OUT"\nexit "$FAKE_RC"\n')
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    (tmp / "fake_out.txt").write_bytes(pytest_output.encode())
    report = _synth_report(pytest_output, pytest_rc)
    if report is not None:
        (tmp / "fake_report.json").write_text(json.dumps(report), encoding="utf-8")
    env = {
        "FAKE_REPORT": str(tmp / "fake_report.json"),
        "PATH": f"{bindir}:/usr/bin:/bin:{Path(sys.executable).parent}",
        "FAKE_OUT": str(tmp / "fake_out.txt"),
        "FAKE_RC": str(pytest_rc),
        "HOME": str(tmp),
    }
    scratch = tmp / "scratch"
    scratch.mkdir()
    test_policy = tmp / "policy_accepted_TEST_ONLY.json"
    test_policy.write_text(json.dumps({
        "schema": 2, "status": "ACCEPTED", "decision_ref": "TEST-ONLY (not an owner decision)",
        "classes": [{"name": "t", "phase": "call",
                     "match": {"exception_types": ["builtins.ConnectionError"], "message_contains": ["huggingface.co"]}}]}))

    def run(script: str) -> int:
        f = tmp / "step.sh"
        text = script.replace("/tmp/", f"{scratch}/")  # relocate scratch paths only
        if not real_policy:
            # Substitute a TEST-ONLY ACCEPTED policy for the shipped PROPOSED one, so the existing
            # wiring cases keep their meaning ("a listed, signature-matching failure is tolerated").
            text = text.replace(_POLICY_REL, str(test_policy))
        f.write_text(text, encoding="utf-8")
        # `bash -e` == GitHub's default shell for run: without `shell:` (no pipefail).
        return subprocess.run(["bash", "-e", str(f)], cwd=ROOT, env=env, capture_output=True, timeout=60).returncode

    rc1 = run(steps["run"]) if run_step1 else 0
    rc2 = run(steps["gate"])
    return rc1 != 0 or rc2 != 0


@_NEEDS_BASH
@pytest.mark.parametrize(
    "output,rc,red",
    [
        (f"{OK_SUMMARY}\n", 0, False),
        (_failed("tests/test_new.py::test_x") + "1 failed, 1787 passed in 1.0s\n", 1, True),
        ("ERROR collecting tests/a.py\n1 error in 0.1s\n", 2, True),
        ("ERROR tests/a.py::t - boom\n1786 passed, 1 error in 1.0s\n", 1, True),
        ("INTERNALERROR> boom\n", 3, True),
        ("no tests ran in 0.01s\n", 5, True),
        ("....\n", 137, True),
        ("bash: pytest: command not found\n", 127, True),
        (f"{OK_SUMMARY}\n", 139, True),  # clean output, only the exit code reveals the crash
    ],
    ids=["clean", "unlisted-failure", "collection-error", "setup-error",
         "internalerror", "nothing-collected", "killed", "no-pytest", "segfault-at-exit-clean-output"],
)
def test_workflow_steps_end_to_end(tmp_path: Path, output: str, rc: int, red: bool) -> None:
    assert _job_is_red(tmp_path, output, rc) is red


@_NEEDS_BASH
def test_workflow_listed_failure_is_tolerated_only_with_exit_code_1(tmp_path: Path) -> None:
    # Uses a real entry of the committed known-failure list (not hard-coded, not modified).
    entry = sorted(gate.parse_allowlist(ALLOWLIST_FILE.read_bytes().decode("utf-8")))[0]
    out = _failed(entry) + "1 failed, 1787 passed in 1.0s\n"
    (tmp_path / "a").mkdir()
    assert _job_is_red(tmp_path / "a", out, 1) is False
    (tmp_path / "b").mkdir()
    assert _job_is_red(tmp_path / "b", out, 2) is True  # same output, but pytest was interrupted


@_NEEDS_BASH
@_NEEDS_BASH
def test_workflow_with_the_shipped_proposed_policy_excuses_nothing(tmp_path: Path) -> None:
    """Batch 1A: until the owner accepts a signature policy, listed failures stay red (diagnostic mode)."""
    entry = next(iter(sorted(gate.parse_allowlist(ALLOWLIST_FILE.read_bytes().decode()))))
    out = _failed(entry) + "1 failed, 1787 passed in 1.0s\n"
    pol = gate.load_policy((ROOT / _POLICY_REL).read_text(encoding="utf-8"))
    assert _job_is_red(tmp_path, out, 1, real_policy=True) is (pol["status"] != "ACCEPTED")


def test_workflow_step_one_is_required(tmp_path: Path) -> None:
    # If the test step never ran there is no exit-code record: the gate must fail.
    assert _job_is_red(tmp_path, f"{OK_SUMMARY}\n", 0, run_step1=False) is True


def test_workflow_does_not_discard_pytest_exit_code() -> None:
    steps = _tests_job_steps()
    assert "|| true" not in steps["run"].replace("PIPESTATUS", "")
    assert "PIPESTATUS" in steps["run"]
    assert "ci_test_gate.py" in steps["gate"] and "--exit-code-file" in steps["gate"]
