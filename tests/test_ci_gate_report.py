"""R-1 / Batch 1A: structured-report mode of scripts/ci_test_gate.py and scripts/ci_gate_report.py.

These tests run REAL pytest in a temporary project with the REAL plugin, then feed the REAL
report and text output to the REAL gate CLI -- only the tiny temporary test projects and the
TEST-ONLY policy are synthetic.  They reproduce the pre-fix scenarios S1-S4 (Batch 0 report)
and the three defects found by the independent review of 667cb94 (exception types ignored;
PROPOSED policy operational; non-strict XPASS counted as an ordinary pass).

The legacy text path (``evaluate``) and the strict ADR-KERNEL-07 D-4 xfail are not involved.
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

import ci_gate_report  # noqa: E402
import ci_test_gate as gate  # noqa: E402

GATE = ROOT / "scripts" / "ci_test_gate.py"
REAL_POLICY = ROOT / "docs" / "architecture" / "D10_KNOWN_ENVIRONMENTAL_FAILURE_SIGNATURE.json"
ALLOWLIST_FILE = ROOT / "docs" / "architecture" / "D10_KNOWN_ENVIRONMENTAL_FAILURES.txt"

TEST_POLICY = {
    "schema": 2, "status": "ACCEPTED", "decision_ref": "TEST-ONLY (not an owner decision)",
    "classes": [{
        "name": "test_net", "phase": "call",
        "match": {"exception_types": ["builtins.ConnectionError"], "message_contains": ["huggingface.co"]},
        "deny": {"exception_types": ["builtins.AssertionError"], "http_status": [401, 403, 404]},
    }],
}


def dd(src: str) -> str:
    return textwrap.dedent(src).lstrip("\n")


PASSING = "def test_ok():\n    pass\n\n"
NET = 'raise ConnectionError("Can\'t reach huggingface.co")'


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONPATH"] = str(ROOT)
    env.update(extra)
    return env


def run_pytest(tmp: Path, files: dict[str, str], *, plugin: bool = True, extra: list[str] | None = None,
               env: dict[str, str] | None = None) -> tuple[int, str, Path]:
    proj = tmp / "proj"
    proj.mkdir()
    for name, body in files.items():
        (proj / name).write_text(body, encoding="utf-8")
    report = tmp / "report.json"
    args = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider"]
    if plugin:
        args += ["-p", "scripts.ci_gate_report", f"--ci-gate-report={report}"]
    args += extra or []
    p = subprocess.run(args, cwd=proj, env=env or _env(), capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr, report


def write_policy(tmp: Path, doc: object) -> Path:
    path = tmp / "policy.json"
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return path


def run_gate(tmp: Path, rc: int | None, out: str, report: Path, allow: list[str], *,
             policy: Path | None = None) -> tuple[int, str]:
    (tmp / "out.txt").write_text(out, encoding="utf-8")
    rcfile = tmp / "rc.txt"
    if rc is not None:
        rcfile.write_text(f"{rc}\n", encoding="utf-8")
    (tmp / "allow.txt").write_text("# test\n" + "\n".join(allow) + "\n", encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(GATE), "--output", str(tmp / "out.txt"), "--exit-code-file", str(rcfile),
         "--allowlist", str(tmp / "allow.txt"), "--report", str(report),
         "--signature-policy", str(policy or write_policy(tmp, TEST_POLICY))],
        capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout


def gated(tmp: Path, body: str, allow: list[str], *, files: dict[str, str] | None = None, **kw) -> tuple[int, str]:
    rc, out, rep = run_pytest(tmp, files or {"test_t.py": body}, **kw)
    return run_gate(tmp, rc, out, rep, allow)


# ----------------------------------------------------- S1-S4 (Batch 0 probe) on the fix

PARAM = dd(f'''
    import pytest
    @pytest.mark.parametrize("v", ["a - b", "a - c", "plain"], ids=["a - b", "a - c", "plain"])
    def test_p(v):
        if v != "plain":
            {NET}
''')


def test_s1_listed_param_id_containing_dash_is_matched_not_truncated(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + PARAM, ["test_t.py::test_p[a - b]", "test_t.py::test_p[a - c]"])
    assert rc == 0, out


def test_s1b_listed_dash_id_with_a_different_failure_is_red(tmp_path: Path) -> None:
    body = PASSING + dd('''
        import pytest
        @pytest.mark.parametrize("v", ["a - b"], ids=["a - b"])
        def test_p(v):
            assert v == "plain"
    ''')
    rc, out = gated(tmp_path, body, ["test_t.py::test_p[a - b]"])
    assert rc == 1 and "does not match an approved signature" in out, out


def test_s2_hand_truncated_entry_is_rejected_not_a_false_green(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + PARAM, ["test_t.py::test_p[a"],
                    extra=["test_t.py::test_p[a - b]", "test_t.py::test_ok"])
    assert rc == 1 and "malformed/truncated allowlist entry" in out, out


def test_s3_colliding_prefix_entries_cannot_broaden(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + PARAM, ["test_t.py::test_p[a", "test_t.py::test_env"])
    assert rc == 1, out


def test_s4_listed_id_does_not_excuse_a_genuine_assertion_failure(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + 'def test_env():\n    raise AssertionError("expected 3 got 4")\n',
                    ["test_t.py::test_env"])
    assert rc == 1 and "does not match an approved signature" in out, out


# ------------------------------------------- review finding 1: exception TYPE must match

def test_review1_assertion_mentioning_the_host_is_not_environmental(tmp_path: Path) -> None:
    body = PASSING + 'def test_model_contract():\n    raise AssertionError("Invalid model configuration for huggingface.co")\n'
    rc, out = gated(tmp_path, body, ["test_t.py::test_model_contract"])
    assert rc == 1 and "does not match an approved signature" in out, out


def test_plain_oserror_with_the_host_is_not_environmental(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + 'def test_env():\n    raise OSError("huggingface.co")\n', ["test_t.py::test_env"])
    assert rc == 1, out


def test_right_type_without_the_host_in_the_message_is_not_environmental(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + 'def test_env():\n    raise ConnectionError("local socket closed")\n',
                    ["test_t.py::test_env"])
    assert rc == 1, out


def test_matching_failure_is_tolerated_with_an_accepted_policy(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + f"def test_env():\n    {NET}\n", ["test_t.py::test_env"])
    assert rc == 0 and "test_t.py::test_env" in out, out


def test_signature_found_through_the_exception_cause_chain(tmp_path: Path) -> None:
    body = PASSING + dd('''
        def test_env():
            try:
                raise ConnectionError("huggingface.co unreachable")
            except ConnectionError as e:
                raise RuntimeError("model load failed") from e
    ''')
    rc, out = gated(tmp_path, body, ["test_t.py::test_env"])
    assert rc == 0, out


def test_http_authorization_failure_in_the_chain_is_denied(tmp_path: Path) -> None:
    body = PASSING + dd('''
        import types
        class HTTPError(Exception):
            def __init__(self, code):
                super().__init__("403 Forbidden for url: https://huggingface.co/x")
                self.response = types.SimpleNamespace(status_code=code)
        def test_env():
            try:
                raise HTTPError(403)
            except HTTPError as e:
                raise ConnectionError("huggingface.co: request failed") from e
    ''')
    rc, out = gated(tmp_path, body, ["test_t.py::test_env"])
    assert rc == 1 and "does not match an approved signature" in out, out
    assert "http_status=403" in out, "the diagnostic chain should show the status"


def test_assertion_error_anywhere_in_the_chain_is_denied(tmp_path: Path) -> None:
    body = PASSING + dd('''
        def test_env():
            try:
                assert False, "app invariant"
            except AssertionError as e:
                raise ConnectionError("huggingface.co") from e
    ''')
    rc, out = gated(tmp_path, body, ["test_t.py::test_env"])
    assert rc == 1, out


def test_deny_applies_to_subclasses_of_a_denied_type(tmp_path: Path) -> None:
    body = PASSING + dd('''
        class MyAssert(AssertionError):
            pass
        def test_env():
            try:
                raise MyAssert("x")
            except MyAssert as e:
                raise ConnectionError("huggingface.co") from e
    ''')
    rc, out = gated(tmp_path, body, ["test_t.py::test_env"])
    assert rc == 1, out


def test_unlisted_failure_with_matching_signature_is_still_red(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, PASSING + f"def test_env():\n    {NET}\n", ["test_t.py::test_other"])
    assert rc == 1 and "not in the known-failure list" in out, out


def test_very_long_node_id_signature_survives_terminal_width(tmp_path: Path) -> None:
    """Text parsing loses the message for long IDs (verified at COLUMNS=80); the report does not."""
    body = PASSING + dd(f'''
        import pytest
        @pytest.mark.parametrize("v", ["x"], ids=["y" * 90])
        def test_long_id(v):
            {NET}
    ''')
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": body}, env=_env(COLUMNS="80"))
    failed_line = next(ln for ln in out.splitlines() if ln.startswith("FAILED"))
    assert " - " not in failed_line, "precondition: pytest dropped the message at width 80"
    grc, gout = run_gate(tmp_path, rc, out, rep, ["test_t.py::test_long_id[" + "y" * 90 + "]"])
    assert grc == 0, gout


# ----------------------------------------- review finding 2: policy lifecycle is enforced

LISTED_NET = PASSING + f"def test_env():\n    {NET}\n"


def test_proposed_policy_excuses_nothing_and_shows_the_chain(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": LISTED_NET})
    pol = write_policy(tmp_path, {**TEST_POLICY, "status": "PROPOSED", "decision_ref": None})
    grc, gout = run_gate(tmp_path, rc, out, rep, ["test_t.py::test_env"], policy=pol)
    assert grc == 1 and "policy is PROPOSED and cannot excuse" in gout, gout
    assert "status PROPOSED" in gout and "builtins.ConnectionError" in gout, "diagnostic chain must be shown"


def test_revoked_policy_excuses_nothing(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": LISTED_NET})
    grc, gout = run_gate(tmp_path, rc, out, rep, ["test_t.py::test_env"],
                         policy=write_policy(tmp_path, {**TEST_POLICY, "status": "REVOKED"}))
    assert grc == 1 and "REVOKED" in gout, gout


@pytest.mark.parametrize("doc", [
    {**TEST_POLICY, "status": "accepted"},
    {**TEST_POLICY, "status": "DRAFT"},
    {k: v for k, v in TEST_POLICY.items() if k != "status"},
    {**TEST_POLICY, "decision_ref": ""},
    {**TEST_POLICY, "decision_ref": None},
    {**TEST_POLICY, "schema": 1},
    {**TEST_POLICY, "classes": []},
    "{",
    "[]",
])
def test_invalid_policy_is_a_gate_error_not_a_pass(tmp_path: Path, doc: object) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": LISTED_NET})
    grc, gout = run_gate(tmp_path, rc, out, rep, ["test_t.py::test_env"], policy=write_policy(tmp_path, doc))
    assert grc == 2 and "GATE ERROR" in gout, gout


@pytest.mark.parametrize("mut", [
    lambda c: c.update(phase="setup"),
    lambda c: c["match"].update(exception_types=[]),
    lambda c: c["match"].update(exception_types=["ConnectionError"]),  # not fully qualified
    lambda c: c["match"].update(message_contains=[" "]),
    lambda c: c["deny"].update(http_status=["403"]),
    lambda c: c.pop("match"),
])
def test_malformed_policy_classes_are_rejected(mut) -> None:
    pol = json.loads(json.dumps(TEST_POLICY))
    mut(pol["classes"][0])
    with pytest.raises(ValueError):
        gate.load_policy(json.dumps(pol))


def test_shipped_policy_is_valid_and_cannot_silently_be_operational() -> None:
    pol = gate.load_policy(REAL_POLICY.read_text(encoding="utf-8"))
    assert pol["status"] in gate._POLICY_STATUSES
    if pol["status"] == "ACCEPTED":  # activation must carry the owner decision reference
        assert pol["decision_ref"]


# ----------------------------------- review finding 3: only ordinary passes count as passes

def test_xpass_only_suite_is_rejected_for_having_no_ordinary_pass(tmp_path: Path) -> None:
    body = "import pytest\n@pytest.mark.xfail(strict=False)\ndef test_x():\n    assert True\n"
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": body})
    assert rc == 0 and "1 xpassed" in out
    grc, gout = run_gate(tmp_path, rc, out, rep, [])
    assert grc == 1 and "no ordinary passing test" in gout, gout


def test_xpass_plus_listed_failure_without_ordinary_pass_is_rejected(tmp_path: Path) -> None:
    body = f"import pytest\n@pytest.mark.xfail(strict=False)\ndef test_x():\n    assert True\ndef test_env():\n    {NET}\n"
    rc, out = gated(tmp_path, body, ["test_t.py::test_env"])
    assert rc == 1 and "no ordinary passing test" in out, out


@pytest.mark.parametrize("body", [
    "import pytest\n@pytest.mark.xfail\ndef test_x():\n    assert False\n",
    "import pytest\n@pytest.mark.skip\ndef test_x():\n    pass\n",
])
def test_xfail_only_and_skip_only_suites_are_rejected(tmp_path: Path, body: str) -> None:
    rc, out = gated(tmp_path, body, [])
    assert rc == 1 and "no ordinary passing test" in out, out


def test_xpass_xfail_skip_alongside_an_ordinary_pass_reconcile_with_the_summary(tmp_path: Path) -> None:
    body = PASSING + dd('''
        import pytest
        @pytest.mark.xfail(strict=False)
        def test_xp(): assert True
        @pytest.mark.xfail
        def test_xf(): assert False
        @pytest.mark.skip
        def test_sk(): pass
        @pytest.fixture
        def skipper():
            pytest.skip("setup skip")
        def test_setup_skip(skipper): pass
    ''')
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": body})
    assert rc == 0, out
    c = json.loads(rep.read_text())["counts"]
    assert c == {"passed": 1, "failed": 0, "errors": 0, "skipped": 2, "xfailed": 1, "xpassed": 1}, c
    grc, gout = run_gate(tmp_path, rc, out, rep, [])
    assert grc == 0, gout


def test_deselected_tests_are_not_in_the_inventory_and_the_run_is_green(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING + "def test_b():\n    pass\n"}, extra=["-k", "test_ok"])
    assert json.loads(rep.read_text())["collected"] == ["test_t.py::test_ok"]
    assert run_gate(tmp_path, rc, out, rep, [])[0] == 0


# ---------------------------------------------------------------------------- fail closed

def test_strict_xpass_is_never_excused_even_when_listed(tmp_path: Path) -> None:
    body = PASSING + "import pytest\n@pytest.mark.xfail(strict=True, reason='x')\ndef test_x():\n    pass\n"
    rc, out = gated(tmp_path, body, ["test_t.py::test_x"])
    assert rc == 1 and "strict XPASS" in out, out


def test_collection_error_fails(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, "", [], files={"test_t.py": PASSING, "test_bad.py": "def (:\n"})
    assert rc == 1, out


@pytest.mark.parametrize("phase", ["setup", "teardown"])
def test_setup_and_teardown_errors_are_never_allowlisted(tmp_path: Path, phase: str) -> None:
    fixture = f"    {NET}\n    yield\n" if phase == "setup" else f"    yield\n    {NET}\n"
    body = PASSING + "import pytest\n@pytest.fixture\ndef boom():\n" + fixture + "def test_env(boom):\n    pass\n"
    rc, out = gated(tmp_path, body, ["test_t.py::test_env"])
    assert rc == 1 and "setup/teardown error" in out, out


def test_run_with_no_passing_test_fails(tmp_path: Path) -> None:
    rc, out = gated(tmp_path, f"def test_env():\n    {NET}\n", ["test_t.py::test_env"])
    assert rc == 1 and "no ordinary passing test" in out, out


def test_killed_run_leaves_no_report_and_fails(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING + "import os\ndef test_die():\n    os._exit(1)\n"})
    assert not rep.exists(), "a dead run must not leave a (stale or partial) report"
    grc, gout = run_gate(tmp_path, rc, out, rep, [])
    assert grc == 1 and "report missing" in gout, gout


def test_stale_report_is_removed_at_start(tmp_path: Path) -> None:
    (tmp_path / "report.json").write_text(json.dumps({"schema": 2, "complete": True, "stale": True}))
    run_pytest(tmp_path, {"test_t.py": PASSING + "import os\ndef test_die():\n    os._exit(1)\n"})
    assert not (tmp_path / "report.json").exists()


def test_run_without_the_plugin_fails_closed(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING}, plugin=False)
    grc, gout = run_gate(tmp_path, rc, out, rep, [])
    assert rc == 0 and grc == 1 and "report missing" in gout


@pytest.mark.parametrize("code", [None, 2, 3, 4, 5, 137])
def test_bad_exit_codes_fail(tmp_path: Path, code: int | None) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING})
    grc, gout = run_gate(tmp_path, code, out, rep, [])
    assert grc == 1, gout


def test_plugin_does_not_change_pytest_exit_status_or_outcomes(tmp_path: Path) -> None:
    body = PASSING + "def test_f():\n    assert False\n"
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    rc1, out1, _ = run_pytest(tmp_path / "a", {"test_t.py": body})
    rc2, out2, _ = run_pytest(tmp_path / "b", {"test_t.py": body}, plugin=False)
    assert rc1 == rc2 == 1
    assert gate.parse_summary(out1).raw.split(" in ")[0] == gate.parse_summary(out2).raw.split(" in ")[0]


# --------------------------------------------- review finding 4: report integrity / completeness

BASE_BODY = PASSING + dd('''
    import pytest
    @pytest.mark.xfail(strict=False)
    def test_xp(): assert True
    def test_f(): assert False
''')


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.update(complete=False), "not marked complete"),
    (lambda d: d.update(exitstatus=0), "disagrees with recorded exit code"),
    (lambda d: d.update(schema=1), "unsupported report schema"),
    (lambda d: d.update(plugin_fault="boom"), "plugin fault"),
    (lambda d: d.update(collect_errors=["x.py"]), "collection error"),
    (lambda d: d.update(records="nope"), "no 'records' list"),
    (lambda d: d.update(collected=None), "no collection inventory"),
    (lambda d: d["records"].append({"nodeid": 1}), "malformed record"),
    (lambda d: d["counts"].update(passed=99), "'counts'"),
    (lambda d: d["counts"].update(xpassed=0), "'counts'"),
    (lambda d: d["records"][1].update(category="bogus"), "inconsistent or unknown outcome"),
    (lambda d: d["records"][1].update(category="failed"), "inconsistent or unknown outcome"),
    (lambda d: d["records"][1].update(outcome="exploded"), "inconsistent or unknown outcome"),
    (lambda d: d["records"].append(dict(d["records"][1])), "duplicate call record"),
    (lambda d: d["collected"].append("test_t.py::test_never_ran"), "no terminal outcome"),
    (lambda d: d["collected"].append(d["collected"][0]), "duplicate node IDs"),
    (lambda d: d["records"].append({**d["records"][0], "nodeid": "test_t.py::ghost"}), "was not collected"),
    (lambda d: d.update(records=[r for r in d["records"] if not (r["nodeid"] == "test_t.py::test_ok" and r["when"] == "call")]),
     "no terminal outcome"),
])
def test_tampered_or_incomplete_report_fails(tmp_path: Path, mutate, needle: str) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": BASE_BODY})
    good = json.loads(rep.read_text())
    assert rc == 1 and good["counts"]["xpassed"] == 1 and good["counts"]["passed"] == 1
    assert run_gate(tmp_path, rc, out, rep, ["test_t.py::test_f"])[0] == 1  # test_f is genuinely failing
    d = json.loads(json.dumps(good))
    mutate(d)
    rep.write_text(json.dumps(d))
    grc, gout = run_gate(tmp_path, rc, out, rep, ["test_t.py::test_f"])
    assert grc == 1 and needle in gout, (needle, gout)


def test_unparsable_report_fails_and_text_cross_check_is_enforced(tmp_path: Path) -> None:
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": PASSING + "import pytest\n@pytest.mark.xfail(strict=False)\ndef test_xp(): pass\n"})
    assert rc == 0
    good = rep.read_text()
    assert run_gate(tmp_path, rc, out, rep, [])[0] == 0
    rep.write_text("{ not json")
    assert run_gate(tmp_path, rc, out, rep, [])[0] == 1
    rep.write_text(good)
    for bad in (out.replace("1 xpassed", "1 passed"), out.replace("1 passed", "3 passed"), out.replace("1 xpassed", "")):
        grc, gout = run_gate(tmp_path, rc, bad, rep, [])
        assert grc == 1 and ("text summary reports" in gout or "no pytest summary" in gout), gout
    grc, gout = run_gate(tmp_path, rc, "", rep, [])
    assert grc == 1 and "no pytest summary" in gout, gout


# ----------------------------------------------------- redaction / evidence in the report

def _fake(prefix: str, n: int = 24) -> str:
    return prefix + "A1b2" * (n // 4)  # assembled at runtime: no literal secret-looking string in the repo


def test_report_redacts_credentials_and_keeps_evidence(tmp_path: Path) -> None:
    gh, hf, bearer = _fake("gh" + "p_"), _fake("h" + "f_"), _fake("", 24)
    body = PASSING + dd(f'''
        import types
        class E(Exception):
            errno = 111
            def __init__(self):
                super().__init__("Authorization: Bearer {bearer} url https://user:pw@h.example/p?token=SECRETVALUE&x=1 {gh} {hf}")
                self.response = types.SimpleNamespace(status_code=503)
        def test_leak():
            raise E()
    ''')
    rc, out, rep = run_pytest(tmp_path, {"test_t.py": body})
    text = rep.read_text()
    for secret in (gh, hf, bearer, "SECRETVALUE", "user:pw"):
        assert secret not in text, secret
    exc = next(r for r in json.loads(text)["records"]
               if r["nodeid"].endswith("test_leak") and r["when"] == "call")["chain"][0]
    assert exc["type"].endswith(".E") and exc["errno"] == 111 and exc["http_status"] == 503
    assert "builtins.Exception" in exc["mro"] and "<redacted" in exc["message"]


@pytest.mark.parametrize("raw,gone", [
    ("see https://a:b@host/x", "a:b"),
    ("GET /f?access_token=abc123&k=v", "abc123"),
    ("password=hunter2xx", "hunter2xx"),
    ("Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA"),
])
def test_redact_unit(raw: str, gone: str) -> None:
    assert gone not in ci_gate_report.redact(raw)


def test_redact_keeps_ordinary_text() -> None:
    assert ci_gate_report.redact("Can't reach huggingface.co: connection refused") == \
        "Can't reach huggingface.co: connection refused"


# ------------------------------------------------------------ allowlist / CLI / workflow

def test_report_flags_must_be_given_together(tmp_path: Path) -> None:
    (tmp_path / "x").write_text("")
    p = subprocess.run([sys.executable, str(GATE), "--output", str(tmp_path / "x"), "--exit-code-file", str(tmp_path / "x"),
                        "--allowlist", str(tmp_path / "x"), "--report", str(tmp_path / "x")], capture_output=True, text=True)
    assert p.returncode == 2 and "must be given together" in p.stdout


def test_real_allowlist_entries_are_all_well_formed_and_unchanged_in_count() -> None:
    entries = gate.parse_allowlist(ALLOWLIST_FILE.read_bytes().decode("utf-8"))
    assert gate.validate_allowlist_entries(entries) == []
    assert len(entries) == 34  # preserved: Batch 1A edits only the header comments


@pytest.mark.parametrize("entry", ["test_t.py::test_p[a", "test_t.py::test_p[a]]", "test_p", "test_t.py::", " test_t.py::t",
                                   "test_t.py::t\r", "test_t.py::t]", "x.txt::t"])
def test_malformed_allowlist_entries_are_detected(entry: str) -> None:
    assert gate.validate_allowlist_entries({entry}) == [entry]


@pytest.mark.parametrize("entry", ["tests/test_t.py::test_ok", "tests/a/b.py::C::test_p[a - b]", "t.py::t[x[1]]"])
def test_wellformed_allowlist_entries_pass(entry: str) -> None:
    assert gate.validate_allowlist_entries({entry}) == []


def test_legacy_text_mode_is_unchanged() -> None:
    assert gate.parse_failed_ids("FAILED a::b[x - y] - reason\n") == {"a::b[x"}


def test_workflow_uses_report_mode_consistently() -> None:
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
    assert (ROOT / "scripts" / "ci_gate_report.py").is_file() and REAL_POLICY.is_file()


def test_matcher_itself_refuses_a_non_accepted_policy() -> None:
    """Defence in depth: even called directly, a PROPOSED/REVOKED policy matches nothing."""
    rec = {"when": "call", "chain": [{"type": "builtins.ConnectionError", "mro": [], "message": "huggingface.co"}]}
    accepted = gate.load_policy(json.dumps(TEST_POLICY))
    assert gate._matches_class(rec, accepted) == "test_net"
    for status in ("PROPOSED", "REVOKED"):
        assert gate._matches_class(rec, {**accepted, "status": status}) is None


def test_matcher_only_matches_the_call_phase() -> None:
    chain = [{"type": "builtins.ConnectionError", "mro": [], "message": "huggingface.co"}]
    pol = gate.load_policy(json.dumps(TEST_POLICY))
    assert gate._matches_class({"when": "call", "chain": chain}, pol) == "test_net"
    for when in ("setup", "teardown"):
        assert gate._matches_class({"when": when, "chain": chain}, pol) is None
