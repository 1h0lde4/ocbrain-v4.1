"""Tests for scripts/ci_junit_manifest.py -- the execution contract of the hosted test job (R1, R4).

The checker is a new authority, so it is tested as one: every row of the spec's mutation matrix
that concerns the JUnit report or the manifest (M1-M12, M14-M16, M18-M21) has at least one test
here that must fail if the checker stops rejecting that input.  M13 and M17 are configuration
rules, pinned in tests/test_ci_workflow_config.py; M13's manifest half (an entry whose declared
condition no longer holds) is tested here.

What this proves is the checker's LOGIC against real pytest 9.2.0 output
(tests/fixtures/ci/junit/pytest9_all_outcomes.xml) and synthetic reports.  The real manifest's
Docker identities were observed on a hosted runner (provenance on every entry); the
`test_real_manifest_*` tests pin what is enrolled and replay the manifest's own expectations, and
its mutants, through the checker.  They do not re-observe a hosted run: only the hosted job's own
check does that, and each run is a measurement of that run.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ci_junit_manifest as cm  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "ci" / "junit"
REAL_MANIFEST = ROOT / "tests" / "ci" / "pytest-execution-manifest.json"

PINNED_ENV = cm.PytestEnvironment("9.2.0", {"pytest-asyncio": "1.5.0", "anyio": "4.16.0"})
DOCKER = "tests.core.sandbox.test_docker_backend"
A9 = "test_a9_af_vsock_socketcall_bypass_is_mitigated_by_the_container_deny_rule"
RUNTIME = "test_runtime_roundtrip"
REASON_NS = "requires unshare + a writable cgroup v1 memory controller"
XF_CLASS = "tests.core.cognitive.test_creative_content_anchor"
XF_NAME = "test_d_already_known_from_context_is_not_implemented"


# ------------------------------------------------------------------------------- builders


def tc(classname: str, name: str, kind: str = "pass", msg: str = "") -> str:
    """One <testcase>.  kinds: pass, skip, xfail, failure, error, untyped_skip, bogus, two."""
    head = f'<testcase classname="{classname}" name="{name}" time="0.000"'
    m = msg.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    body = {
        "pass": None,
        "skip": f'<skipped type="pytest.skip" message="{m}">x</skipped>',
        "xfail": f'<skipped type="pytest.xfail" message="{m}" />',
        "failure": f'<failure message="{m}">trace</failure>',
        "error": f'<error message="{m}">trace</error>',
        "untyped_skip": f'<skipped message="{m}">x</skipped>',
        "typo_skip": f'<skipped type="pytest.skipp" message="{m}">x</skipped>',
        "bogus": "<flaky />",
        "two": f'<skipped type="pytest.skip" message="{m}">x</skipped><failure message="boom">t</failure>',
        "stdout_only": "<system-out>SKIPPED FAILED xfail</system-out>",
    }[kind]
    return head + (" />" if body is None else f">{body}</testcase>")


def count(cases: list[str]) -> dict[str, int]:
    fails = sum("<failure" in c for c in cases)
    errs = sum("<error" in c for c in cases)
    skips = sum("<skipped" in c for c in cases)
    return {"tests": len(cases), "failures": fails, "errors": errs, "skipped": skips}


def xml(cases: list[str], **override: int) -> str:
    n = {**count(cases), **override}
    attrs = " ".join(f'{k}="{v}"' for k, v in n.items())
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests">'
        f'<testsuite name="pytest" {attrs}>' + "".join(cases) + "</testsuite></testsuites>"
    )


def baseline_cases() -> list[str]:
    return [
        tc(DOCKER, A9),
        tc(DOCKER, RUNTIME),
        tc("tests.core.sandbox.test_namespace_backend", "test_one", "skip", REASON_NS),
        tc("tests.core.sandbox.test_namespace_backend", "test_two", "skip", REASON_NS),
        tc(XF_CLASS, XF_NAME, "xfail", "ADR-KERNEL-07 D-4"),
        tc("tests.unrelated", "test_x"),
    ]


def entry(eid: str, classname: str, name: str, expected: str = "PASS", **kw: Any) -> dict[str, Any]:
    e: dict[str, Any] = {
        "id": eid, "source": classname.replace(".", "/") + ".py", "junit_classname": classname, "junit_name": name,
        "expected_outcome": expected, "criticality": "runtime_verification", "provenance": "test fixture",
    }
    e.update(kw)
    return e


def base_manifest() -> dict[str, Any]:
    return {
        "schema_version": cm.MANIFEST_SCHEMA,
        "manifest_version": "1.0.0",
        "pins": {"pytest": "9.2.0", "plugins": {"pytest-asyncio": "1.5.0", "anyio": "4.16.0"}},
        "entries": [
            entry("a9", DOCKER, A9, criticality="security_contract"),
            entry("runtime", DOCKER, RUNTIME),
            entry("ns1", "tests.core.sandbox.test_namespace_backend", "test_one", "SKIP",
                  skip_reason=REASON_NS, criticality="environmental"),
            entry("ns2", "tests.core.sandbox.test_namespace_backend", "test_two", "SKIP",
                  skip_reason=REASON_NS, criticality="environmental"),
            entry("gap", XF_CLASS, XF_NAME, "XFAIL", criticality="known_gap"),
        ],
        "pending": [],
    }


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.counter = 0

    def junit(self, text: str | bytes) -> Path:
        self.counter += 1
        p = self.tmp / f"report{self.counter}.xml"
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text, encoding="utf-8")
        return p

    def manifest(self, doc: dict[str, Any]) -> Path:
        self.counter += 1
        p = self.tmp / f"manifest{self.counter}.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        return p

    def run(
        self,
        cases: list[str] | None = None,
        doc: dict[str, Any] | None = None,
        env: cm.PytestEnvironment = PINNED_ENV,
        environ: dict[str, str] | None = None,
        raw_xml: str | bytes | None = None,
    ) -> cm.Evaluation:
        report = cm.parse_junit(self.junit(raw_xml if raw_xml is not None else xml(cases if cases is not None else baseline_cases())))
        manifest, problems = cm.load_manifest(self.manifest(doc if doc is not None else base_manifest()))
        assert manifest is not None, problems
        return cm.evaluate(report, manifest, env, environ or {})


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def red_reasons(ev: cm.Evaluation) -> str:
    return " | ".join([e.why for e in ev.red_entries] + ev.unlisted_reds + ev.problems)


# ------------------------------------------------------------------------------- baseline


def test_baseline_is_green(h: Harness) -> None:
    ev = h.run()
    assert ev.green, red_reasons(ev)
    assert [e.ok for e in ev.entries] == [True] * 5


def test_an_approved_environmental_skip_may_start_to_pass(h: Harness) -> None:
    cases = baseline_cases()
    cases[2] = tc("tests.core.sandbox.test_namespace_backend", "test_one")
    assert h.run(cases).green


def test_plain_pass_of_unlisted_test_needs_no_entry(h: Harness) -> None:
    ev = h.run(baseline_cases() + [tc("tests.new", "test_new_feature")])
    assert ev.green


# ------------------------------------------------------------------------------- JUnit classification


@pytest.mark.parametrize(
    "kind,expected",
    [("pass", "PASS"), ("skip", "SKIP"), ("xfail", "XFAIL"), ("failure", "FAIL"), ("error", "ERROR"),
     ("untyped_skip", "UNKNOWN"), ("typo_skip", "UNKNOWN"), ("bogus", "UNKNOWN"), ("two", "UNKNOWN"),
     ("stdout_only", "PASS")],
)
def test_classify_testcase_reads_structure(kind: str, expected: str) -> None:
    import xml.etree.ElementTree as ET
    out = cm.classify_testcase(ET.fromstring(tc("c", "n", kind, "m")))
    assert out.outcome == expected


def test_message_text_never_decides_an_outcome() -> None:
    """M12: a failure whose message says 'skipped', a pass with SKIPPED in system-out, ANSI noise."""
    import xml.etree.ElementTree as ET
    f = cm.classify_testcase(ET.fromstring(tc("c", "n", "failure", "\x1b[32mSKIPPED [1] xfailed passed\x1b[0m".replace("\x1b", ""))))
    assert f.outcome == "FAIL"
    p = cm.classify_testcase(ET.fromstring(tc("c", "n", "stdout_only")))
    assert p.outcome == "PASS"
    s = cm.classify_testcase(ET.fromstring(tc("c", "n", "skip", "FAILED xfail error")))
    assert s.outcome == "SKIP" and s.reason == "FAILED xfail error"


def test_testcase_without_identity_is_unknown_not_dropped() -> None:
    import xml.etree.ElementTree as ET
    for text in ('<testcase name="x" />', '<testcase classname="c" />', '<testcase classname="c" name="" />'):
        assert cm.classify_testcase(ET.fromstring(text)).outcome == "UNKNOWN"


def test_failure_reason_is_truncated_but_present() -> None:
    import xml.etree.ElementTree as ET
    out = cm.classify_testcase(ET.fromstring(tc("c", "n", "failure", "x" * 500)))
    assert out.reason is not None and len(out.reason) == 200


def test_real_pytest_9_report_is_classified_exactly() -> None:
    report = cm.parse_junit(FIXTURES / "pytest9_all_outcomes.xml")
    assert report.problems == ()
    got = {c.key: (c.outcome, c.reason) for c in report.cases}
    assert got[("pkg.test_outcomes", "test_plain_pass")][0] == "PASS"
    assert got[("pkg.test_outcomes", "test_param[1]")][0] == "PASS"
    assert got[("pkg.test_outcomes", "test_param[two]")][0] == "PASS"
    assert got[("pkg.test_outcomes", "test_runtime_skip")] == ("SKIP", "requires a reachable Docker daemon")
    assert got[("pkg.test_modskip", "test_a")] == ("SKIP", REASON_NS)
    assert got[("pkg.test_outcomes", "test_expected_failure")][0] == "XFAIL"
    assert got[("pkg.test_outcomes", "test_strict_xpass")][0] == "FAIL"  # strict XPASS is a <failure> in pytest 9
    assert "XPASS(strict)" in (got[("pkg.test_outcomes", "test_strict_xpass")][1] or "")
    assert got[("pkg.test_outcomes", "test_real_failure")][0] == "FAIL"
    assert got[("pkg.test_outcomes", "test_setup_error")][0] == "ERROR"
    assert got[("pkg.test_outcomes.TestGroup", "test_in_class")][0] == "PASS"
    assert len(report.cases) == 11 and report.sha256 is not None


def test_real_report_against_a_manifest_for_it(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"] = [
        entry("param", "pkg.test_outcomes", "test_param[two]"),
        entry("rt", "pkg.test_outcomes", "test_runtime_skip", "SKIP", skip_reason="requires a reachable Docker daemon"),
        entry("xf", "pkg.test_outcomes", "test_expected_failure", "XFAIL", criticality="known_gap"),
        entry("xp", "pkg.test_outcomes", "test_strict_xpass", "XFAIL", criticality="known_gap"),
    ]
    report = cm.parse_junit(FIXTURES / "pytest9_all_outcomes.xml")
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is not None, problems
    ev = cm.evaluate(report, manifest, PINNED_ENV, {})
    by_id = {e.id: e for e in ev.entries}
    assert by_id["param"].ok and by_id["rt"].ok and by_id["xf"].ok
    assert not by_id["xp"].ok and "strict XPASS" in by_id["xp"].why  # M11 on real pytest output
    # the real failure and the real setup error are not in the manifest and are red
    joined = " | ".join(ev.unlisted_reds)
    assert "unexpected failure: pkg.test_outcomes::test_real_failure" in joined
    assert "unexpected error: pkg.test_outcomes::test_setup_error" in joined
    assert not ev.green


# ------------------------------------------------------------------------------- M1-M7: deselection and absence


def test_m1_m2_m4_m5_m7_missing_mandatory_identity_is_red(h: Harness) -> None:
    """--deselect, --ignore, -k/-m, deleting the file, or selecting one other test all leave the
    mandatory identity out of the report."""
    for drop in (A9, RUNTIME):
        cases = [c for c in baseline_cases() if f'name="{drop}"' not in c]
        ev = h.run(cases)
        assert not ev.green
        assert any(e.observed == "ABSENT" and e.key[1] == drop for e in ev.red_entries), drop


def test_m3_narrowed_to_one_file_is_red(h: Harness) -> None:
    ev = h.run([tc("tests.unrelated", "test_x")])
    assert not ev.green
    assert len(ev.red_entries) == 5 and all(e.observed == "ABSENT" for e in ev.red_entries)


def test_m7_one_pure_logic_test_selected_from_the_docker_module_is_red(h: Harness) -> None:
    cases = [tc(DOCKER, "test_pure_logic_only"), tc("tests.unrelated", "test_x")]
    ev = h.run(cases)
    assert not ev.green
    assert {e.id for e in ev.red_entries} >= {"a9", "runtime"}


def test_absence_of_a_not_required_entry_is_allowed(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"][1]["required"] = False
    ev = h.run([c for c in baseline_cases() if RUNTIME not in c], doc)
    assert ev.green, red_reasons(ev)


def test_required_defaults_to_true(h: Harness) -> None:
    doc = base_manifest()
    assert "required" not in doc["entries"][1]
    assert not h.run([c for c in baseline_cases() if RUNTIME not in c], doc).green


# ------------------------------------------------------------------------------- M6, M10: skips


def test_m6_a_module_skips_with_a_new_unmatched_reason(h: Harness) -> None:
    cases = baseline_cases()
    cases[2] = tc("tests.core.sandbox.test_namespace_backend", "test_one", "skip", "requires something else now")
    ev = h.run(cases)
    assert not ev.green and "unapproved reason" in red_reasons(ev)


def test_m6_reason_must_match_exactly_not_by_prefix_or_case(h: Harness) -> None:
    for bad in (REASON_NS + ".", REASON_NS.upper(), REASON_NS[:-1], " " + REASON_NS, ""):
        cases = baseline_cases()
        cases[2] = tc("tests.core.sandbox.test_namespace_backend", "test_one", "skip", bad)
        assert not h.run(cases).green, repr(bad)


def test_m10_valid_xml_with_an_unexpected_skip_is_red(h: Harness) -> None:
    ev = h.run(baseline_cases() + [tc("tests.other", "test_new", "skip", "temporarily disabled")])
    assert not ev.green and "unapproved skip: tests.other::test_new" in red_reasons(ev)


def test_a_mandatory_pass_entry_that_skips_is_red(h: Harness) -> None:
    cases = baseline_cases()
    cases[1] = tc(DOCKER, RUNTIME, "skip", "requires a reachable Docker daemon")
    ev = h.run(cases)
    assert not ev.green and "mandatory test skipped" in red_reasons(ev)


def test_a_mandatory_pass_entry_that_xfails_is_red(h: Harness) -> None:
    cases = baseline_cases()
    cases[1] = tc(DOCKER, RUNTIME, "xfail", "x")
    assert "mandatory test xfailed" in red_reasons(h.run(cases))


def test_skip_entry_that_xfails_is_red(h: Harness) -> None:
    cases = baseline_cases()
    cases[2] = tc("tests.core.sandbox.test_namespace_backend", "test_one", "xfail", "x")
    assert "xfailed where a skip or pass was expected" in red_reasons(h.run(cases))


@pytest.mark.parametrize("kind", ["failure", "error"])
def test_failure_or_error_of_a_listed_test_is_red(h: Harness, kind: str) -> None:
    for idx in range(5):
        cases = baseline_cases()
        cls, name = cases[idx].split('"')[1], cases[idx].split('"')[3]
        cases[idx] = tc(cls, name, kind, "boom")
        ev = h.run(cases)
        assert not ev.green and any(not e.ok and e.key == (cls, name) for e in ev.entries), (idx, kind)


@pytest.mark.parametrize("kind", ["untyped_skip", "typo_skip", "bogus", "two"])
def test_m15_listed_test_with_an_unclassifiable_outcome_is_red(h: Harness, kind: str) -> None:
    for idx in range(5):
        cases = baseline_cases()
        cls, name = cases[idx].split('"')[1], cases[idx].split('"')[3]
        cases[idx] = tc(cls, name, kind, REASON_NS)
        ev = h.run(cases)
        assert not ev.green and any(not e.ok and e.key == (cls, name) and "unclassifiable" in e.why for e in ev.entries), (idx, kind)


@pytest.mark.parametrize("kind", ["failure", "error", "skip", "xfail", "untyped_skip", "bogus"])
def test_unlisted_non_pass_outcome_is_red(h: Harness, kind: str) -> None:
    ev = h.run(baseline_cases() + [tc("tests.other", "test_new", kind, "m")])
    assert not ev.green and any("tests.other::test_new" in u for u in ev.unlisted_reds)


# ------------------------------------------------------------------------------- M8, M9: the report itself


def test_m8_missing_report_is_red(h: Harness, tmp_path: Path) -> None:
    report = cm.parse_junit(tmp_path / "does-not-exist.xml")
    assert report.problems and "cannot read" in report.problems[0]
    manifest, _ = cm.load_manifest(h.manifest(base_manifest()))
    assert manifest is not None
    ev = cm.evaluate(report, manifest, PINNED_ENV, {})
    assert not ev.green and all(e.observed == "ABSENT" for e in ev.entries)


@pytest.mark.parametrize(
    "label,payload,needle",
    [
        ("empty", "", "empty"),
        ("whitespace", " \n\t ", "empty"),
        ("not xml", "this is not xml", "not well-formed"),
        ("truncated", xml(baseline_cases())[: len(xml(baseline_cases())) // 2], "not well-formed"),
        ("wrong root", "<html><body/></html>", "unexpected root"),
        ("no suite", "<testsuites></testsuites>", "no <testsuite>"),
        ("no testcases", '<testsuites><testsuite name="p" tests="0" failures="0" errors="0" skipped="0"></testsuite></testsuites>', "no testcases"),
        ("doctype", '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]>' + xml(baseline_cases()), "DOCTYPE"),
        ("entity only", xml(baseline_cases()).replace("<testsuites", '<!ENTITY a "b"><testsuites', 1), "DOCTYPE"),
        ("non utf8", b"\xff\xfe<testsuites/>", "UTF-8"),
    ],
)
def test_m9_malformed_report_is_red(h: Harness, label: str, payload: str | bytes, needle: str) -> None:
    ev = h.run(raw_xml=payload)
    assert not ev.green, label
    assert needle in " ".join(ev.problems), (label, ev.problems)


def test_m9_suite_totals_must_agree_with_the_testcases(h: Harness) -> None:
    for key in ("tests", "failures", "errors", "skipped"):
        real = count(baseline_cases())[key]
        ev = h.run(raw_xml=xml(baseline_cases(), **{key: real + 1}))
        assert not ev.green and f"{key}=" in " ".join(ev.problems), key


def test_m9_a_non_integer_total_is_a_problem_not_a_crash(h: Harness) -> None:
    raw = xml(baseline_cases()).replace('tests="6"', 'tests="six"')
    ev = h.run(raw_xml=raw)
    assert not ev.green and "integer" in " ".join(ev.problems)
    assert "disagree" not in " ".join(ev.problems), "an unreadable total is reported once, not also compared"


def test_totals_sum_across_several_suites(h: Harness) -> None:
    a, b = baseline_cases()[:3], baseline_cases()[3:]
    def suite(cs: list[str]) -> str:
        n = count(cs)
        return "<testsuite name=\"s\" " + " ".join(f'{k}="{v}"' for k, v in n.items()) + ">" + "".join(cs) + "</testsuite>"
    raw = '<?xml version="1.0"?><testsuites>' + suite(a) + suite(b) + "</testsuites>"
    assert h.run(raw_xml=raw).green
    assert h.run(raw_xml=raw.replace('tests="3"', 'tests="4"', 1)).green is False


def test_a_bare_testsuite_root_is_accepted(h: Harness) -> None:
    cs = baseline_cases()
    n = count(cs)
    raw = "<testsuite name=\"s\" " + " ".join(f'{k}="{v}"' for k, v in n.items()) + ">" + "".join(cs) + "</testsuite>"
    assert h.run(raw_xml=raw).green


# ------------------------------------------------------------------------------- M11, M18, M19, M20: xfail tripwire


def test_m11_strict_xpass_is_red_even_when_the_entry_expects_xfail(h: Harness) -> None:
    cases = baseline_cases()
    cases[4] = tc(XF_CLASS, XF_NAME, "failure", "[XPASS(strict)] ADR-KERNEL-07 D-4")
    ev = h.run(cases)
    assert not ev.green
    assert any("strict XPASS" in e.why for e in ev.red_entries)


def test_m19_marker_removed_so_the_test_passes_is_red(h: Harness) -> None:
    cases = baseline_cases()
    cases[4] = tc(XF_CLASS, XF_NAME)
    ev = h.run(cases)
    assert not ev.green and "xfail marker no longer applies" in red_reasons(ev)


def test_m19_xfail_entry_absent_or_skipped_is_red(h: Harness) -> None:
    absent = [c for c in baseline_cases() if XF_NAME not in c]
    assert any(e.observed == "ABSENT" for e in h.run(absent).red_entries)
    skipped = baseline_cases()
    skipped[4] = tc(XF_CLASS, XF_NAME, "skip", "needs docker")
    assert "skipped where an xfail was expected" in red_reasons(h.run(skipped))


def test_m18_an_xfail_outcome_with_no_manifest_entry_is_red(h: Harness) -> None:
    ev = h.run(baseline_cases() + [tc("tests.new", "test_new_strict_marker", "xfail", "new strict marker")])
    assert not ev.green and "xfail outcome with no manifest entry: tests.new::test_new_strict_marker" in red_reasons(ev)


def test_m20_a9_cannot_be_given_an_xfail_or_skip_entry(h: Harness, tmp_path: Path) -> None:
    for outcome, extra in (("XFAIL", {}), ("SKIP", {"skip_reason": "no docker"})):
        doc = base_manifest()
        doc["entries"][0].update(expected_outcome=outcome, **extra)
        manifest, problems = cm.load_manifest(h.manifest(doc))
        assert manifest is None and any("A9" in p and "no XFAIL or SKIP waiver" in p for p in problems), outcome


def test_m20_a9_that_xfails_is_red_against_a_pass_entry(h: Harness) -> None:
    cases = baseline_cases()
    cases[0] = tc(DOCKER, A9, "xfail", "bypass reproduced")
    ev = h.run(cases)
    assert not ev.green and any(e.id == "a9" and not e.ok for e in ev.entries)


def test_m20_a9_that_fails_is_red_and_that_is_the_design(h: Harness) -> None:
    cases = baseline_cases()
    cases[0] = tc(DOCKER, A9, "failure", "classification=BYPASS_REPRODUCED")
    ev = h.run(cases)
    assert [e.id for e in ev.red_entries] == ["a9"]


def test_a9_waiver_check_covers_any_a9_name_prefix_but_not_other_names(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"].append(entry("other", DOCKER, "test_not_a9_related", "XFAIL"))
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is not None, problems


# ------------------------------------------------------------------------------- M13: conditions


def test_m13_condition_unset_holds_when_the_variable_is_absent(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"][4]["condition"] = "OCBRAIN_SANDBOX_NETWORK_PROVISIONED=unset"
    assert h.run(doc=doc, environ={}).green


def test_m13_provisioned_variable_set_makes_the_conditional_entry_red(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"][4]["condition"] = "OCBRAIN_SANDBOX_NETWORK_PROVISIONED=unset"
    for value in ("1", "", "0"):
        ev = h.run(doc=doc, environ={"OCBRAIN_SANDBOX_NETWORK_PROVISIONED": value})
        assert not ev.green and "declared condition" in red_reasons(ev), repr(value)


def test_condition_equals_value(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"][4]["condition"] = "FLAG=on"
    assert h.run(doc=doc, environ={"FLAG": "on"}).green
    assert not h.run(doc=doc, environ={"FLAG": "off"}).green
    assert not h.run(doc=doc, environ={}).green


# ------------------------------------------------------------------------------- M14: manifest integrity


def test_m14_duplicate_manifest_id_is_rejected(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"].append(entry("a9", "tests.x", "test_y"))
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is None and any("duplicate manifest id" in p for p in problems)


def test_m14_duplicate_junit_identity_in_the_manifest_is_rejected(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"].append(entry("again", DOCKER, RUNTIME))
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is None and any("duplicate JUnit identity" in p for p in problems)


def test_m14_same_name_in_a_different_class_is_not_a_duplicate(h: Harness) -> None:
    doc = base_manifest()
    doc["entries"].append(entry("other", "tests.x", RUNTIME))
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is not None, problems


@pytest.mark.parametrize("field", ["id", "source", "junit_classname", "junit_name", "expected_outcome", "criticality", "provenance"])
@pytest.mark.parametrize("bad", ["", None, 7])
def test_m14_unmappable_entry_is_rejected(h: Harness, field: str, bad: Any) -> None:
    doc = base_manifest()
    doc["entries"][1][field] = bad
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is None and any(field in p and "non-empty string" in p for p in problems)


def test_m14_a_missing_field_is_rejected(h: Harness) -> None:
    doc = base_manifest()
    del doc["entries"][1]["junit_classname"]
    assert cm.load_manifest(h.manifest(doc))[0] is None


def test_m14_duplicate_identity_in_the_report_is_red(h: Harness) -> None:
    ev = h.run(baseline_cases() + [tc(DOCKER, RUNTIME)])
    assert not ev.green
    assert any("duplicate JUnit identity" in p for p in ev.problems)
    dup = [e for e in ev.entries if e.observed == "DUPLICATE"]
    assert dup and all(not e.ok for e in dup)


def test_m14_duplicate_unlisted_identity_in_the_report_is_red(h: Harness) -> None:
    ev = h.run(baseline_cases() + [tc("tests.x", "test_a"), tc("tests.x", "test_a")])
    assert not ev.green and any("tests.x" in p for p in ev.problems)


def test_m14_unmappable_testcase_in_the_report_is_red(h: Harness) -> None:
    ev = h.run(baseline_cases() + ['<testcase name="orphan" />'])
    assert not ev.green and any("unclassifiable" in u for u in ev.unlisted_reds)


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.update(schema_version="other/1"), "schema_version"),
    (lambda d: d.update(manifest_version="1.0"), "manifest_version"),
    (lambda d: d.pop("manifest_version"), "manifest_version"),
    (lambda d: d.update(entries=[]), "non-empty list"),
    (lambda d: d.update(entries="x"), "non-empty list"),
    (lambda d: d.update(pins={"pytest": "9.2.0"}), "pins must be"),
    (lambda d: d.update(pins="x"), "pins must be"),
    (lambda d: d["pins"].update(pytest="9.2.0rc1"), "exact stable release"),
    (lambda d: d["pins"].update(pytest=">=9.2"), "exact stable release"),
    (lambda d: d["pins"]["plugins"].update({"pytest-asyncio": "2.0.0a1"}), "exact stable release"),
    (lambda d: d["pins"]["plugins"].update({"pytest-asyncio": 1}), "version string"),
    (lambda d: d["pins"]["plugins"].update({"pytest_asyncio": "1.5.0"}), "duplicate plugin pin"),
    (lambda d: d.update(pending="x"), "pending must be"),
    (lambda d: d.update(pending=[{"no_id": 1}]), "pending must be"),
    (lambda d: d["entries"][1].update(expected_outcome="MAYBE"), "expected_outcome"),
    (lambda d: d["entries"][1].update(criticality="vibes"), "criticality"),
    (lambda d: d["entries"][1].update(skip_reason="x"), "skip_reason is only valid"),
    (lambda d: d["entries"][2].pop("skip_reason"), "needs the exact skip_reason"),
    (lambda d: d["entries"][2].update(skip_reason=""), "needs the exact skip_reason"),
    (lambda d: d["entries"][1].update(condition="not a condition"), "condition must look like"),
    (lambda d: d["entries"][1].update(condition=5), "condition must look like"),
    (lambda d: d["entries"][1].update(required="yes"), "required must be a boolean"),
    (lambda d: d["entries"].append("not an object"), "is not an object"),
])
def test_manifest_validation_rejects(h: Harness, mutate: Any, needle: str) -> None:
    doc = base_manifest()
    mutate(doc)
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is None and any(needle in p for p in problems), problems


def test_manifest_file_problems(tmp_path: Path) -> None:
    assert cm.load_manifest(tmp_path / "nope.json")[1][0].startswith("cannot read the manifest")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert "not valid JSON" in cm.load_manifest(bad)[1][0]
    arr = tmp_path / "arr.json"
    arr.write_text("[]")
    assert "not a JSON object" in cm.load_manifest(arr)[1][0]


def test_plugin_pin_names_are_normalised(h: Harness) -> None:
    doc = base_manifest()
    doc["pins"]["plugins"] = {"pytest_asyncio": "1.5.0", "AnyIO": "4.16.0"}
    manifest, problems = cm.load_manifest(h.manifest(doc))
    assert manifest is not None, problems
    assert set(manifest.pins.plugins) == {"pytest-asyncio", "anyio"}


# ------------------------------------------------------------------------------- pending


def test_pending_blocks_make_the_run_red_and_are_reported(h: Harness) -> None:
    doc = base_manifest()
    doc["pending"] = [{"id": "docker-runtime", "reason": "needs a Docker host", "blocked_on": "H-D3"}]
    ev = h.run(doc=doc)
    assert not ev.green and ev.red_entries == [] and ev.unlisted_reds == []
    assert any("MANIFEST_PENDING docker-runtime" in p and "H-D3" in p for p in ev.problems)


def test_pending_without_reason_still_reports(h: Harness) -> None:
    doc = base_manifest()
    doc["pending"] = [{"id": "x"}]
    ev = h.run(doc=doc)
    assert any("no reason recorded" in p and "unspecified" in p for p in ev.problems)


# ------------------------------------------------------------------------------- M16, M21: toolchain


VERSION_OUTPUT = """This is pytest version 9.2.0, imported from /x/pytest/__init__.py
registered third-party plugins:
  pytest-asyncio-1.5.0 at /x/pytest_asyncio/plugin.py
  anyio-4.16.0 at /x/anyio/pytest_plugin.py
"""


def test_parse_pytest_version_output() -> None:
    env = cm.parse_pytest_version_output(VERSION_OUTPUT)
    assert env.pytest_version == "9.2.0" and env.problem is None
    assert dict(env.plugins) == {"pytest-asyncio": "1.5.0", "anyio": "4.16.0"}


def test_parse_handles_the_older_header_and_no_plugins() -> None:
    env = cm.parse_pytest_version_output("pytest 8.3.1\n")
    assert env.pytest_version == "8.3.1" and dict(env.plugins) == {}


def test_parse_flags_an_unreadable_version() -> None:
    env = cm.parse_pytest_version_output("garbage")
    assert env.pytest_version is None and env.problem


def test_parse_plugin_with_a_digit_in_its_name() -> None:
    env = cm.parse_pytest_version_output(
        "This is pytest version 9.2.0, imported from /x\nregistered third-party plugins:\n"
        "  pytest-3d-render-1.0.2 at /x/p.py\n  pytest_asyncio-2.0.0a1 at /y.py\n"
    )
    assert dict(env.plugins) == {"pytest-3d-render": "1.0.2", "pytest-asyncio": "2.0.0a1"}


def test_plugin_block_ends_at_the_next_unindented_line() -> None:
    env = cm.parse_pytest_version_output(VERSION_OUTPUT + "rootdir: /x\n  not-a-plugin-1.0 at /z\n")
    assert "not-a-plugin" not in env.plugins


def test_m16_pytest_version_mismatch_is_red(h: Harness) -> None:
    for v in ("9.2.1", "9.1.0", "9.2.0rc1", "8.4.0"):
        env = cm.PytestEnvironment(v, PINNED_ENV.plugins)
        ev = h.run(env=env)
        assert not ev.green and f"pytest {v} is not the pinned 9.2.0" in " ".join(ev.problems), v
    assert "prerelease" in " ".join(h.run(env=cm.PytestEnvironment("9.2.0rc1", PINNED_ENV.plugins)).problems)


def test_m16_plugin_version_mismatch_is_red(h: Harness) -> None:
    env = cm.PytestEnvironment("9.2.0", {"pytest-asyncio": "1.4.0", "anyio": "4.16.0"})
    ev = h.run(env=env)
    assert not ev.green and "pytest-asyncio 1.4.0 is not the pinned 1.5.0" in " ".join(ev.problems)


def test_m21_prerelease_plugin_is_red(h: Harness) -> None:
    env = cm.PytestEnvironment("9.2.0", {"pytest-asyncio": "2.0.0a1", "anyio": "4.16.0"})
    ev = h.run(env=env)
    assert not ev.green and "2.0.0a1" in " ".join(ev.problems) and "prerelease" in " ".join(ev.problems)


def test_m21_missing_plugin_is_red(h: Harness) -> None:
    env = cm.PytestEnvironment("9.2.0", {"anyio": "4.16.0"})
    ev = h.run(env=env)
    assert not ev.green and "pinned plugin pytest-asyncio==1.5.0 is not registered" in " ".join(ev.problems)


def test_m21_unpinned_extra_plugin_is_red(h: Harness) -> None:
    env = cm.PytestEnvironment("9.2.0", {**PINNED_ENV.plugins, "pytest-randomly": "3.15.0"})
    ev = h.run(env=env)
    assert not ev.green and "pytest-randomly 3.15.0 is not in the pinned set" in " ".join(ev.problems)


def test_m21_unreadable_environment_is_red(h: Harness) -> None:
    ev = h.run(env=cm.PytestEnvironment(None, {}, "could not run pytest"))
    assert not ev.green and ev.problems == ["could not run pytest"]


def test_detect_environment_uses_the_runner_and_reports_failures() -> None:
    ok = cm.detect_environment(lambda argv: (0, VERSION_OUTPUT))
    assert ok.pytest_version == "9.2.0" and "--version" in " ".join(["--version"])
    seen: list[list[str]] = []

    def runner(argv: Any) -> tuple[int, str]:
        seen.append(list(argv))
        return 2, "boom"

    bad = cm.detect_environment(runner)
    assert bad.pytest_version is None and "exited 2" in (bad.problem or "")
    assert seen[0][1:] == ["-m", "pytest", "--version", "--version"]

    def raising(argv: Any) -> tuple[int, str]:
        raise OSError("no python")

    assert "could not run pytest" in (cm.detect_environment(raising).problem or "")


# ------------------------------------------------------------------------------- CLI


def run_cli(tmp_path: Path, junit: Path, manifest: Path, env: cm.PytestEnvironment = PINNED_ENV,
            environ: dict[str, str] | None = None, report: bool = True) -> tuple[int, dict[str, Any] | None]:
    out = tmp_path / "check-report.json"
    ns = argparse.Namespace(junit=junit, manifest=manifest, report=out if report else None)
    rc = cm.check_main(ns, env=env, environ=environ or {})
    return rc, (json.loads(out.read_text()) if report and out.exists() else None)


def test_cli_green_exit_zero_and_report(h: Harness, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, rep = run_cli(tmp_path, h.junit(xml(baseline_cases())), h.manifest(base_manifest()))
    out = capsys.readouterr().out
    assert rc == 0 and rep is not None and rep["green"] is True
    assert "junit manifest check: GREEN" in out and rep["pytest_version"] == "9.2.0"
    assert rep["manifest_sha256"] and rep["junit_sha256"] and len(rep["entries"]) == 5


def test_cli_red_exit_one_and_names_every_red(h: Harness, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cases = [c for c in baseline_cases() if A9 not in c] + [tc("tests.o", "test_bad", "failure", "x")]
    rc, rep = run_cli(tmp_path, h.junit(xml(cases)), h.manifest(base_manifest()))
    out = capsys.readouterr().out
    assert rc == 1 and rep is not None and rep["green"] is False
    assert rep["red_entries"] == ["a9"] and "unexpected failure: tests.o::test_bad" in out
    assert "RED (1 manifest entries, 1 unlisted outcomes" in out


def test_cli_invalid_manifest_is_red_not_a_crash(h: Harness, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    doc = base_manifest()
    doc["entries"] = []
    rc, rep = run_cli(tmp_path, h.junit(xml(baseline_cases())), h.manifest(doc))
    assert rc == 1 and rep is not None and rep["manifest_version"] is None and rep["problems"]
    assert "junit manifest check: RED" in capsys.readouterr().out


def test_cli_a_bad_manifest_and_a_bad_report_are_both_reported(h: Harness, tmp_path: Path) -> None:
    doc = base_manifest()
    doc["entries"] = []
    rc, rep = run_cli(tmp_path, h.junit("not xml"), h.manifest(doc))
    assert rc == 1 and rep is not None
    joined = " ".join(rep["problems"])
    assert "non-empty list" in joined and "not well-formed" in joined


def test_cli_missing_files_are_red(tmp_path: Path) -> None:
    rc, rep = run_cli(tmp_path, tmp_path / "no.xml", tmp_path / "no.json")
    assert rc == 1 and rep is not None and any("cannot read" in p for p in rep["problems"])


def test_cli_writes_the_step_summary(h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    run_cli(tmp_path, h.junit(xml(baseline_cases())), h.manifest(base_manifest()))
    assert "### JUnit execution manifest" in summary.read_text()


def test_cli_unwritable_step_summary_does_not_change_the_verdict(h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "no-such-dir" / "summary.md"))
    rc, _ = run_cli(tmp_path, h.junit(xml(baseline_cases())), h.manifest(base_manifest()))
    assert rc == 0


def test_cli_does_not_write_a_report_unless_asked(h: Harness, tmp_path: Path) -> None:
    rc, rep = run_cli(tmp_path, h.junit(xml(baseline_cases())), h.manifest(base_manifest()), report=False)
    assert rc == 0 and rep is None and not (tmp_path / "check-report.json").exists()


def test_main_parses_argv_and_exits_with_the_verdict(h: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cm, "detect_environment", lambda runner=None: PINNED_ENV)
    monkeypatch.delenv("OCBRAIN_SANDBOX_NETWORK_PROVISIONED", raising=False)
    j, m = h.junit(xml(baseline_cases())), h.manifest(base_manifest())
    assert cm.main(["check", "--junit", str(j), "--manifest", str(m)]) == 0
    assert cm.main(["check", "--junit", str(j), "--manifest", str(m), "--report", str(tmp_path / "r.json")]) == 0
    assert json.loads((tmp_path / "r.json").read_text())["green"] is True
    with pytest.raises(SystemExit):
        cm.main(["check", "--junit", str(j)])


def test_cli_text_file_holds_what_was_printed(h: Harness, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for label, cases, last in (
        ("green", baseline_cases(), "junit manifest check: GREEN"),
        ("red", [tc("tests.o", "test_bad", "failure", "x")], "junit manifest check: RED"),
    ):
        text = tmp_path / f"check-{label}.txt"
        ns = argparse.Namespace(junit=h.junit(xml(cases)), manifest=h.manifest(base_manifest()), report=None, text=text)
        cm.check_main(ns, env=PINNED_ENV, environ={})
        printed = capsys.readouterr().out
        assert text.read_text() == printed, "the file is the same text the log shows"
        assert printed.splitlines()[-1].startswith(last), label


def test_cli_text_file_is_written_even_for_an_invalid_manifest(h: Harness, tmp_path: Path) -> None:
    text = tmp_path / "check.txt"
    ns = argparse.Namespace(junit=tmp_path / "no.xml", manifest=tmp_path / "no.json", report=None, text=text)
    assert cm.check_main(ns, env=PINNED_ENV, environ={}) == 1
    assert "junit manifest check: RED" in text.read_text()


def test_cli_without_text_writes_no_file(h: Harness, tmp_path: Path) -> None:
    ns = argparse.Namespace(junit=h.junit(xml(baseline_cases())), manifest=h.manifest(base_manifest()), report=None)
    assert cm.check_main(ns, env=PINNED_ENV, environ={}) == 0
    assert not list(tmp_path.glob("check*.txt"))


# ------------------------------------------------------------------------------- verdict


def verdict(tmp_path: Path, codes: dict[str, str | None], files: dict[str, str | None]) -> tuple[int, str]:
    """Build the files (None = absent), run `verdict`, return (rc, printed)."""
    import contextlib
    import io
    args: list[str] = ["verdict"]
    for name, content in {**codes, **files}.items():
        path = tmp_path / name
        if content is not None:
            path.write_text(content, encoding="utf-8")
        args += ["--exit-code-file" if name in codes else "--require-file", str(path)]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cm.main(args)
    return rc, buf.getvalue()


def test_verdict_green_when_every_exit_code_is_zero_and_every_file_exists(tmp_path: Path) -> None:
    rc, out = verdict(tmp_path, {"a.exit": "0\n", "b.exit": "0"}, {"x.xml": "<x/>", "y.json": "{}"})
    assert rc == 0 and "verdict: GREEN (2 exit codes, 2 evidence files)" in out


@pytest.mark.parametrize("bad", ["1", "2\n", "", "00", "ok", "-1"])
def test_verdict_red_for_any_recorded_exit_code_but_zero(tmp_path: Path, bad: str) -> None:
    rc, out = verdict(tmp_path, {"a.exit": "0", "b.exit": bad}, {"x.xml": "<x/>"})
    assert rc == 1 and "b.exit" in out and "not 0" in out and "a.exit" not in out.split("RED", 1)[1]


def test_verdict_red_when_a_recording_never_happened(tmp_path: Path) -> None:
    rc, out = verdict(tmp_path, {"a.exit": "0", "b.exit": None}, {"x.xml": "<x/>"})
    assert rc == 1 and "b.exit" in out and "cannot read the recorded exit code" in out


def test_verdict_red_for_a_missing_evidence_file(tmp_path: Path) -> None:
    rc, out = verdict(tmp_path, {"a.exit": "0"}, {"x.xml": None})
    assert rc == 1 and "x.xml" in out and "missing" in out


def test_verdict_red_for_an_empty_evidence_file(tmp_path: Path) -> None:
    rc, out = verdict(tmp_path, {"a.exit": "0"}, {"x.xml": ""})
    assert rc == 1 and "x.xml" in out and "empty" in out


def test_verdict_reports_every_problem_not_just_the_first(tmp_path: Path) -> None:
    rc, out = verdict(tmp_path, {"a.exit": "3", "b.exit": None}, {"x.xml": None, "y.json": ""})
    assert rc == 1
    for needle in ("a.exit", "b.exit", "x.xml", "y.json"):
        assert needle in out


def test_verdict_with_nothing_to_decide_from_is_red(tmp_path: Path) -> None:
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cm.main(["verdict"]) == 1
        assert cm.main(["verdict", "--require-file", str(tmp_path)]) == 1
    assert "nothing to decide from" in buf.getvalue()


def test_check_environment_is_the_only_place_versions_are_judged(h: Harness) -> None:
    """The evaluation never reads versions except through check_environment (parallel to the A9
    verifier, whose classifier never reads the Engine version)."""
    import inspect
    src = inspect.getsource(cm.evaluate)
    assert "pytest_version" not in src and "plugins" not in src.replace("check_environment", "")


# ------------------------------------------------------------------------------- the real manifest


def test_real_manifest_loads_and_is_internally_valid() -> None:
    manifest, problems = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None, problems
    assert manifest.pins.pytest == "9.2.0"
    assert manifest.pins.plugins["pytest-asyncio"] == "1.5.0"


def test_real_manifest_has_exactly_the_approved_skip_inventory() -> None:
    """Appendix A, H-D2: the 18 environmental skips, exact identity and exact reason."""
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    skips = [e for e in manifest.entries if e.expected == "SKIP"]
    assert len(skips) == 18
    hosts = [e for e in skips if e.classname == "tests.core.sandbox.test_allowed_hosts"]
    ns = [e for e in skips if e.classname == "tests.core.sandbox.test_namespace_backend"]
    assert (len(hosts), len(ns)) == (4, 14)
    assert {e.skip_reason for e in hosts} == {"requires unshare + iproute2 + a writable cgroup v1 memory controller"}
    assert {e.skip_reason for e in ns} == {REASON_NS}
    assert all(e.criticality == "environmental" and e.required for e in skips)


def test_real_manifest_names_a9_as_a_mandatory_pass_with_no_waiver() -> None:
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    a9 = [e for e in manifest.entries if e.name.startswith(cm.A9_NAME_PREFIX)]
    assert len(a9) == 1
    assert (a9[0].classname, a9[0].name, a9[0].expected, a9[0].required) == (DOCKER, A9, "PASS", True)
    assert a9[0].criticality == "security_contract" and a9[0].condition is None


B01 = "tests.core.sandbox.test_network_isolation_contract"
B01_CONDITION = "OCBRAIN_SANDBOX_NETWORK_PROVISIONED=unset"
DOCKER_SKIP_REASONS = ("requires a reachable Docker daemon", "requires the test image")


def _real_doc() -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    return doc


def _replay(doc: dict[str, Any], *, skip: str = "", drop: str = "", outcome: dict[str, str] | None = None) -> list[str]:
    """Testcases that do exactly what the manifest expects (PASS, the exact skip, XFAIL), plus one
    unlisted pass.  `skip` / `drop` / `outcome` mutate one identity by manifest entry id."""
    cases: list[str] = []
    for e in doc["entries"]:
        if e["id"] == drop:
            continue
        kind = {"PASS": "pass", "SKIP": "skip", "XFAIL": "xfail"}[e["expected_outcome"]]
        msg = e.get("skip_reason", "strict xfail")
        if e["id"] == skip:
            kind, msg = "skip", DOCKER_SKIP_REASONS[0]
        if outcome and e["id"] in outcome:
            kind, msg = outcome[e["id"]], "mutated"
        cases.append(tc(e["junit_classname"], e["junit_name"], kind, msg))
    return cases + [tc("tests.unrelated", "test_x")]


def test_real_manifest_has_the_known_gap_xfail_and_the_eight_b01_xfails() -> None:
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    xf = [e for e in manifest.entries if e.expected == "XFAIL"]
    assert len(xf) == 9
    gap = [e for e in xf if e.classname != B01]
    assert [(e.classname, e.name) for e in gap] == [(XF_CLASS, XF_NAME)]
    b01 = [e for e in xf if e.classname == B01]
    assert len(b01) == 8
    assert all(e.condition == B01_CONDITION and e.criticality == "known_gap" and e.required for e in b01)
    by_tc = {tag: sum(e.name.startswith(f"test_{tag}_") for e in b01) for tag in ("tc01", "tc02", "tc03", "tc04")}
    assert by_tc == {"tc01": 1, "tc02": 1, "tc03": 4, "tc04": 2}
    assert all("[docker" in e.name for e in b01)


def test_real_manifest_has_no_pending_block() -> None:
    """H-D3: the Docker runtime identities and the eight B01 xfail identities were observed on a
    hosted runner and are enrolled, so nothing is pending.  A new pending block is red by design and
    must be a deliberate, visible change that updates this test."""
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    assert manifest.pending == ()


def test_real_manifest_enrols_the_observed_docker_runtime_identities() -> None:
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    runtime = [e for e in manifest.entries if e.criticality == "runtime_verification"]
    assert len(runtime) == 76
    assert {e.classname for e in runtime} == {DOCKER}
    assert all(e.expected == "PASS" and e.required and e.condition is None for e in runtime)
    assert all(A9 != e.name for e in runtime), "A9 is a security_contract entry, never a plain runtime one"
    # the whole manifest: A9 + 76 runtime passes, 18 approved skips, 9 xfails
    assert len(manifest.entries) == 104
    assert sum(e.expected == "PASS" for e in manifest.entries) == 77
    # every enrolled identity names where it was observed
    assert all("run 45584825671" in e.provenance for e in manifest.entries if e.id.startswith(("docker-runtime:", "b01-xfail:")))


def test_real_manifest_replay_is_green_and_every_entry_is_checked(h: Harness) -> None:
    """The manifest's own expectations, replayed, are green; the checker judged all 104 entries."""
    doc = _real_doc()
    ev = h.run(_replay(doc), doc)
    assert ev.green, red_reasons(ev)
    assert len(ev.entries) == 104 and all(e.ok for e in ev.entries)


def test_a_skip_of_any_enrolled_pass_identity_is_red(h: Harness) -> None:
    """The Docker runtime tests are mandatory: a daemon that is missing turns every one of them into
    a skip, and each skip must be red on its own (not only the aggregate)."""
    doc = _real_doc()
    for e in doc["entries"]:
        if e["expected_outcome"] != "PASS":
            continue
        ev = h.run(_replay(doc, skip=e["id"]), doc)
        assert not ev.green, e["id"]
        assert "mandatory test skipped" in red_reasons(ev), e["id"]


def test_an_absent_enrolled_identity_is_red(h: Harness) -> None:
    doc = _real_doc()
    for e in doc["entries"]:
        ev = h.run(_replay(doc, drop=e["id"]), doc)
        assert not ev.green, e["id"]
        assert "absent from the report" in red_reasons(ev), e["id"]


def test_a_b01_xfail_that_passes_or_fails_is_red_and_the_condition_is_enforced(h: Harness) -> None:
    doc = _real_doc()
    b01 = [e for e in doc["entries"] if e["junit_classname"] == B01]
    assert len(b01) == 8
    for e in b01:
        for kind in ("pass", "failure", "skip"):
            ev = h.run(_replay(doc, outcome={e["id"]: kind}), doc)
            assert not ev.green, (e["id"], kind)
    # the declared condition no longer holding (the isolation is provisioned) is red, not a quiet pass
    ev = h.run(_replay(doc), doc, environ={"OCBRAIN_SANDBOX_NETWORK_PROVISIONED": "1"})
    assert not ev.green
    assert sum("declared condition" in e.why for e in ev.red_entries) == 8


def test_no_approved_skip_accepts_a_missing_docker_daemon_or_image() -> None:
    """H-D7 premise: the grep skip step rejected any skip whose reason names the Docker daemon or the
    test image.  The manifest accepts a skip only with the exact approved reason, and no approved
    reason is one of those, so everything the grep rejected is also red here."""
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    approved = {e.skip_reason for e in manifest.entries if e.expected == "SKIP"}
    assert approved and all(r is not None for r in approved)
    for reason in approved:
        assert not any(d in str(reason) for d in DOCKER_SKIP_REASONS), reason


def test_an_unlisted_skip_for_a_missing_daemon_or_image_is_red(h: Harness) -> None:
    """H-D7: a Docker-gated test nobody enrolled (a new test, a new module) that skips for a missing
    daemon or image is still red -- an unlisted non-pass outcome is never green."""
    doc = _real_doc()
    for reason in DOCKER_SKIP_REASONS:
        cases = _replay(doc) + [tc("tests.core.sandbox.test_brand_new_docker_module", "test_new", "skip", reason)]
        ev = h.run(cases, doc)
        assert not ev.green
        assert any(u.startswith("unapproved skip") for u in ev.unlisted_reds), ev.unlisted_reds
        assert "test_brand_new_docker_module" in red_reasons(ev)


def test_real_manifest_fixture_ids_exist_in_the_repository() -> None:
    """Every listed source file exists, so a renamed or deleted test module cannot hide behind an
    entry that was never checked against the tree (an absent identity is red at run time anyway)."""
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    for e in manifest.entries:
        assert (ROOT / e.source).is_file(), e.source


def test_real_manifest_sources_define_the_listed_names() -> None:
    manifest, _ = cm.load_manifest(REAL_MANIFEST)
    assert manifest is not None
    for e in manifest.entries:
        text = (ROOT / e.source).read_text(encoding="utf-8")
        base = e.name.split("[", 1)[0]
        assert f"def {base}(" in text, (e.source, e.name)


def test_the_manifest_is_a_stable_serialisation() -> None:
    raw = REAL_MANIFEST.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert raw == json.dumps(doc, indent=2) + "\n", "keep the manifest canonical: json.dumps(indent=2) plus a newline"
    assert copy.deepcopy(doc) == doc
