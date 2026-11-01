"""R-1: structured-report mode of scripts/ci_test_gate.py and scripts/ci_gate_report.py.

R-1 (KNOWN_ISSUES): the gate cut ``FAILED`` lines at the first `` - `` and matched
by node ID only.  These tests run REAL pytest in a temporary project with the REAL
plugin, then feed the REAL report and text output to the REAL gate CLI -- only the
tiny temporary test projects are synthetic.  They reproduce the pre-fix scenarios
S1-S4 recorded in the Batch 0 report (S2 and S4 were false greens before).

The legacy text path (``evaluate``) and ``tests/test_ci_test_gate.py`` are untouched
here; the strict ADR-KERNEL-07 D-4 xfail is not involved.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ci_test_gate as gate  # noqa: E402

GATE = ROOT / "scripts" / "ci_test_gate.py"
POLICY = ROOT / "docs" / "architecture" / "D10_KNOWN_ENVIRONMENTAL_FAILURE_SIGNATURE.json"
ALLOWLIST_FILE = ROOT / "docs" / "architecture" / "D10_KNOWN_ENVIRONMENTAL_FAILURES.txt"

HF = "OSError: Can't reach huggingface.co to download the model"  # matches the proposed class

PASSING = "def test_ok():\n    pass\n\n"


def dd(src: str) -> str:
    return textwrap.dedent(src).lstrip("\n")


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONPATH"] = str(ROOT)
    env.update(extra)
    return env


def run_pytest(tmp: Path, files: dict[str, str], *, plugin: bool = True, extra: list[str] | None = None,
               env: dict[str, str] | None = None) -> tuple[int, str, Path]:
    """Run real pytest (CI flags) in ``tmp``; return (exit code, text output, report path)."""
    proj = tmp / "proj"
    proj.mkdir()
    for name, body in files.items():
        (proj / name).write_text(textwrap.dedent(body), encoding="utf-8")
    report = tmp / "report.json"
    args = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider"]
    if plugin:
        args += ["-p", "scripts.ci_gate_report", f"--ci-gate-report={report}"]
    args += extra or []
    p = subprocess.run(args, cwd=proj, env=env or _env(), capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr, report


def run_gate(tmp: Path, rc: int, out: str, report: Path, allow: list[str], *, policy: Path = POLICY) -> tuple[int, str]:
    (tmp / "out.txt").write_text(out, encoding="utf-8")
    (tmp / "rc.txt").write_text(f"{rc}\n", encoding="utf-8")
    (tmp / "allow.txt").write_text("# test\n" + "\n".join(allow) + "\n", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(GATE), "--output", str(tmp / "out.txt"), "--exit-code-file", str(tmp / "rc.txt"),
         "--allowlist", str(tmp / "allow.txt"), "--report", str(report), "--signature-policy", str(policy)],
        capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout


def gated(tmp: Path, files: dict[str, str], allow: list[str], **kw) -> tuple[int, str]:
    rc, out, rep = run_pytest(tmp, files, **kw)
    return run_gate(tmp, rc, out, rep, allow)


# ----------------------------------------------------------- S1-S4 re-run on the fix

PARAM = dd(f'''
    import pytest
    @pytest.mark.parametrize("v", ["a - b", "a - c", "plain"], ids=["a - b", "a - c", "plain"])
    def test_p(v):
        if v != "plain":
            raise OSError("Can't reach huggingface.co")
''')


def test_s1_listed_param_id_containing_dash_is_matched_not_truncated(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, {"test_t.py": PASSING + PARAM},
                    ["test_t.py::test_p[a - b]", "test_t.py::test_p[a - c]"])
    assert rc == 0, out


def test_s1b_listed_dash_id_with_a_different_failure_is_red(tmp_path: Path) -> None:
    body = PASSING + dd('''
    import pytest
    @pytest.mark.parametrize("v", ["a - b"], ids=["a - b"])
    def test_p(v):
        assert v == "plain"
    ''')
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_p[a - b]"])
    assert rc == 1 and "does not match an approved signature" in out, out


def test_s2_hand_truncated_entry_is_rejected_not_a_false_green(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, {"test_t.py": PASSING + PARAM}, ["test_t.py::test_p[a"],
                    extra=["test_t.py::test_p[a - b]", "test_t.py::test_ok"])
    assert rc == 1 and "malformed/truncated allowlist entry" in out, out


def test_s3_colliding_prefix_entries_cannot_broaden(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, {"test_t.py": PASSING + PARAM},
                    ["test_t.py::test_p[a", "test_t.py::test_env"])
    assert rc == 1, out


def test_s4_listed_id_does_not_excuse_a_genuine_assertion_failure(tmp_path: Path) -> None:
    body = PASSING + 'def test_env():\n    raise AssertionError("expected 3 got 4")\n'
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_env"])
    assert rc == 1 and "does not match an approved signature" in out, out


# ------------------------------------------------------- tolerated, and how narrowly

def test_listed_failure_with_matching_signature_is_tolerated(tmp_path: Path) -> None:
    body = PASSING + f'def test_env():\n    raise {HF.split(":")[0]}("Can\'t reach huggingface.co")\n'
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_env"])
    assert rc == 0 and "test_t.py::test_env" in out, out


def test_signature_found_through_the_exception_cause_chain(tmp_path: Path) -> None:
    body = PASSING + dd('''
    def test_env():
        try:
            raise OSError("huggingface.co unreachable")
        except OSError as e:
            raise RuntimeError("model load failed") from e
    ''')
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_env"])
    assert rc == 0, out


def test_unlisted_failure_with_matching_signature_is_still_red(tmp_path: Path) -> None:
    body = PASSING + 'def test_env():\n    raise OSError("huggingface.co")\n'
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_other"])
    assert rc == 1 and "not in the known-failure list" in out, out


def test_very_long_node_id_signature_survives_terminal_width(tmp_path: Path) -> None:
    """Text parsing loses the message for long IDs (verified: COLUMNS=80); the report does not."""
    body = PASSING + dd('''
    import pytest
    @pytest.mark.parametrize("v", ["x"], ids=["y" * 90])
    def test_long_id(v):
        raise OSError("huggingface.co")
    ''')
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": body}, env=_env(COLUMNS="80"))
    failed_line = next(ln for ln in out.splitlines() if ln.startswith("FAILED"))
    assert " - " not in failed_line, "precondition: pytest dropped the message at width 80"
    nid = "test_t.py::test_long_id[" + "y" * 90 + "]"
    grc, gout = run_gate(tmp_path, rc, out, rep, [nid])
    assert grc == 0, gout


# --------------------------------------------------------------------- fail closed

def test_strict_xpass_is_never_excused_even_when_listed(tmp_path: Path) -> None:
    body = PASSING + dd('''
    import pytest
    @pytest.mark.xfail(strict=True, reason="x")
    def test_x():
        pass
    ''')
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_x"])
    assert rc == 1 and "strict XPASS" in out, out


def test_collection_error_fails(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, {"test_t.py": PASSING, "test_bad.py": "def (:\n"}, [])
    assert rc == 1, out


def test_setup_error_is_never_allowlisted(tmp_path: Path) -> None:
    body = PASSING + dd('''
    import pytest
    @pytest.fixture
    def boom():
        raise OSError("huggingface.co")
    def test_env(boom):
        pass
    ''')
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_env"])
    assert rc == 1 and "setup/teardown error" in out, out


def test_teardown_error_is_never_allowlisted(tmp_path: Path) -> None:
    body = PASSING + dd('''
    import pytest
    @pytest.fixture
    def boom():
        yield
        raise OSError("huggingface.co")
    def test_env(boom):
        pass
    ''')
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_env"])
    assert rc == 1 and "setup/teardown error" in out, out


def test_run_with_no_passing_test_fails(tmp_path: Path) -> None:
    body = 'def test_env():\n    raise OSError("huggingface.co")\n'
    rc, out = gated(tmp_path, {"test_t.py": body}, ["test_t.py::test_env"])
    assert rc == 1 and "nothing was verified" in out, out


def test_killed_run_leaves_no_report_and_fails(tmp_path: Path) -> None:
    body = PASSING + "import os\ndef test_die():\n    os._exit(1)\n"
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": body})
    assert not rep.exists(), "a dead run must not leave a (stale or partial) report"
    grc, gout = run_gate(tmp_path, rc, out, rep, [])
    assert grc == 1 and "report missing" in gout, gout


def test_stale_report_is_removed_at_start(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"schema": 1, "complete": True, "stale": True}))
    body = PASSING + "import os\ndef test_die():\n    os._exit(1)\n"
    run_pytest(tmp_path, {"test_t.py": body})
    assert not report.exists()


def test_run_without_the_plugin_fails_closed(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING}, plugin=False)
    assert rc == 0
    grc, gout = run_gate(tmp_path, rc, out, rep, [])
    assert grc == 1 and "report missing" in gout


def test_incomplete_or_tampered_report_fails(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING})
    good = json.loads(rep.read_text())
    assert run_gate(tmp_path, rc, out, rep, [])[0] == 0
    for mutate, needle in [
        (lambda d: d.update(complete=False), "not marked complete"),
        (lambda d: d.update(exitstatus=1), "disagrees with recorded exit code"),
        (lambda d: d.update(schema=2), "unsupported report schema"),
        (lambda d: d.update(plugin_fault="boom"), "plugin fault"),
        (lambda d: d.update(collect_errors=["x.py"]), "collection error"),
        (lambda d: d.update(records="nope"), "no 'records' list"),
        (lambda d: d["records"].append({"nodeid": 1}), "malformed record"),
    ]:
        d = json.loads(json.dumps(good))
        mutate(d)
        rep.write_text(json.dumps(d))
        grc, gout = run_gate(tmp_path, rc, out, rep, [])
        assert grc == 1 and needle in gout, (needle, gout)
    rep.write_text("{ not json")
    assert run_gate(tmp_path, rc, out, rep, [])[0] == 1
    rep.write_text(json.dumps(good))
    # text cross-check: the text output disagrees with the report
    grc, gout = run_gate(tmp_path, rc, out.replace("1 passed", "1 passed, 3 failed"), rep, [])
    assert grc == 1 and "text summary" in gout, gout
    grc, gout = run_gate(tmp_path, rc, "", rep, [])  # no summary at all
    assert grc == 1 and "no pytest summary" in gout, gout


@pytest.mark.parametrize("code", [None, 2, 3, 4, 5, 137])
def test_bad_exit_codes_fail(tmp_path: Path, code: int | None) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING})
    (tmp_path / "out.txt").write_text(out)
    (tmp_path / "allow.txt").write_text("")
    if code is not None:
        (tmp_path / "rc.txt").write_text(str(code))
    p = subprocess.run([sys.executable, str(GATE), "--output", str(tmp_path / "out.txt"),
                        "--exit-code-file", str(tmp_path / "rc.txt"), "--allowlist", str(tmp_path / "allow.txt"),
                        "--report", str(rep), "--signature-policy", str(POLICY)], capture_output=True, text=True)
    assert p.returncode == 1, p.stdout


def test_plugin_does_not_change_pytest_exit_status_or_outcomes(tmp_path: Path) -> None:
    body = PASSING + "def test_f():\n    assert False\n"
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    rc1, out1, _ = run_pytest(tmp_path / "a", {"test_t.py": body})
    rc2, out2, _ = run_pytest(tmp_path / "b", {"test_t.py": body}, plugin=False)
    assert rc1 == rc2 == 1
    assert gate.parse_summary(out1).raw.split(" in ")[0] == gate.parse_summary(out2).raw.split(" in ")[0]


# -------------------------------------------------------- policy / allowlist / CLI

def test_malformed_policy_is_a_gate_error(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING})
    for bad in ["{", "[]", '{"schema": 1, "classes": []}', '{"schema": 1, "classes": [{"name": "x", "phase": "setup", "chain_message_contains": ["a"]}]}',
                '{"schema": 1, "classes": [{"name": "x", "phase": "call", "chain_message_contains": []}]}',
                '{"schema": 1, "classes": [{"name": "x", "phase": "call", "chain_message_contains": [" "]}]}']:
        pol = tmp_path / "pol.json"
        pol.write_text(bad)
        grc, gout = run_gate(tmp_path, rc, out, rep, [], policy=pol)
        assert grc == 2 and "GATE ERROR" in gout, (bad, gout)


def test_report_flags_must_be_given_together(tmp_path: Path) -> None:
    (tmp_path / "x").write_text("")
    p = subprocess.run([sys.executable, str(GATE), "--output", str(tmp_path / "x"), "--exit-code-file", str(tmp_path / "x"),
                        "--allowlist", str(tmp_path / "x"), "--report", str(tmp_path / "x")], capture_output=True, text=True)
    assert p.returncode == 2 and "must be given together" in p.stdout


def test_real_allowlist_entries_are_all_well_formed_and_unchanged_in_count() -> None:
    entries = gate.parse_allowlist(ALLOWLIST_FILE.read_bytes().decode("utf-8"))
    assert gate.validate_allowlist_entries(entries) == []
    assert len(entries) == 34  # preserved: this change does not edit the allowlist


@pytest.mark.parametrize("entry", ["test_t.py::test_p[a", "test_t.py::test_p[a]]", "test_p", "test_t.py::", " test_t.py::t",
                                   "test_t.py::t\r", "test_t.py::t]", "x.txt::t"])
def test_malformed_allowlist_entries_are_detected(entry: str) -> None:
    assert gate.validate_allowlist_entries({entry}) == [entry]


@pytest.mark.parametrize("entry", ["tests/test_t.py::test_ok", "tests/a/b.py::C::test_p[a - b]", "t.py::t[x[1]]"])
def test_wellformed_allowlist_entries_pass(entry: str) -> None:
    assert gate.validate_allowlist_entries({entry}) == []


def test_legacy_text_mode_is_unchanged() -> None:
    # R-1 remains in the legacy text parser by design (unused by CI); pinned in test_ci_test_gate.py.
    assert gate.parse_failed_ids("FAILED a::b[x - y] - reason\n") == {"a::b[x"}


def test_workflow_uses_report_mode_consistently() -> None:
    """ci.yml must load the plugin, write the report, and gate on that same report + policy."""
    import re

    import yaml
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    steps = {st.get("name", ""): st for st in doc["jobs"]["tests"]["steps"]}
    run = next(st for n, st in steps.items() if n.startswith("Run test suite"))
    gate_step = next(st for n, st in steps.items() if n.startswith("Gate on"))
    assert "-p scripts.ci_gate_report" in run["run"]
    produced = re.search(r"--ci-gate-report=(\S+)", run["run"]).group(1)
    consumed = re.search(r"--report (\S+)", gate_step["run"]).group(1)
    assert produced == consumed
    assert "--signature-policy docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURE_SIGNATURE.json" in gate_step["run"]
    assert "--output" in gate_step["run"], "the text output stays as the cross-check"
    assert "PIPESTATUS" in run["run"] and "|| true" not in run["run"].replace("PIPESTATUS", "")
    assert run["env"]["PYTHONPATH"] == "${{ github.workspace }}"
    assert (ROOT / "scripts" / "ci_gate_report.py").is_file() and POLICY.is_file()
