"""tests/test_live_check_runbook_validator.py -- the validity checker embedded in the runbook.

The runbook (docs/studies/OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RUNBOOK_OCT2026.md) tells a human how to decide
whether a live run is usable evidence. This test extracts that exact snippet FROM THE DOCUMENT and
executes it, so the documented checker and the tested checker cannot diverge.

Regression: an earlier version treated "interpretation == request in every row" as proof the intent step
had fallen back. That was an unverified assumption: Goal.structured_form["description"] is the raw request
BY DESIGN (core/cognitive/intent.py:1090), so equality is the normal shape of a healthy run. The first real
Codespace run (llama3, 2026-10-02) had exactly that shape and the old checker would have rejected it.
"""
import asyncio
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "studies" / "OCBRAIN_LIVE_CHECK_DRAFT_PLAN_RUNBOOK_OCT2026.md"

_spec = importlib.util.spec_from_file_location(
    "live_check_draft_plan", ROOT / "scripts" / "live_check_draft_plan.py")
lc = importlib.util.module_from_spec(_spec)
sys.modules["live_check_draft_plan"] = lc
_spec.loader.exec_module(lc)


def _snippet() -> str:
    m = re.search(r"```python\npython3 - <<'PYEOF'\n(.*?)\nPYEOF\n```", RUNBOOK.read_text(), re.S)
    assert m, "validity-checker snippet not found in the runbook"
    return m.group(1) + "\n"


def _result(kind: str):
    async def pair(req):
        if kind == "real_shape":      # what the first real run looked like
            return {"interpretation": req, "degraded": [],
                    "steps": ["Develop a concept", "Create an outline", "Write a first draft",
                              "Revise", "Proofread", "Finalize", "Publish"]}
        if kind == "degraded":
            return {"interpretation": req, "steps": [req],
                    "degraded": ["decompose: RuntimeError", "decompose: empty -> single-step fallback"]}
        if kind == "single_step_genuine":   # a model that really answers with one step is still valid
            return {"interpretation": req, "steps": [req], "degraded": []}
        raise AssertionError(kind)
    orig = lc._live_pair
    lc._live_pair = pair
    try:
        return asyncio.run(lc.run(lc.SAMPLE, offline=""))
    finally:
        lc._live_pair = orig


def _run_validator(tmp_path, result) -> subprocess.CompletedProcess:
    (tmp_path / "live.json").write_text(json.dumps(result))
    return subprocess.run([sys.executable, "-c", _snippet()], cwd=tmp_path,
                          capture_output=True, text=True)


def test_snippet_exists_and_is_syntactically_valid_python():
    compile(_snippet(), "runbook-snippet", "exec")


def test_real_run_shape_is_usable__echoed_interpretation_is_normal(tmp_path):
    r = _run_validator(tmp_path, _result("real_shape"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "USABLE AS EVIDENCE" in r.stdout
    assert "steps per plan: [7, 7," in r.stdout


def test_degraded_run_is_rejected(tmp_path):
    r = _run_validator(tmp_path, _result("degraded"))
    assert r.returncode == 1 and "NOT USABLE" in r.stdout
    assert "rows with a degraded model call: 11" in r.stdout


def test_one_degraded_row_among_good_ones_is_rejected(tmp_path):
    # The harness only sets not_evidence when EVERY row degraded, so a single failed row (e.g. a timeout)
    # must be caught by the validator's own `degraded` check -- the case that matters most in practice.
    res = _result("real_shape")
    res["rows"][3]["degraded"] = ["decompose: TimeoutError", "decompose: empty -> single-step fallback"]
    res["rows"][3]["steps"] = [res["rows"][3]["request"]]
    assert res["not_evidence"] is False
    r = _run_validator(tmp_path, res)
    assert r.returncode == 1 and "NOT USABLE" in r.stdout
    assert "rows with a degraded model call: 1" in r.stdout


def test_offline_synthetic_run_is_rejected(tmp_path):
    res = asyncio.run(lc.run(lc.SAMPLE, offline="speculative"))
    r = _run_validator(tmp_path, res)
    assert r.returncode == 1 and "NOT USABLE" in r.stdout


def test_a_genuine_single_step_plan_is_not_misjudged_as_fallback(tmp_path):
    # Degradation is recorded by the harness in `degraded`; a one-step plan alone is not evidence of it.
    r = _run_validator(tmp_path, _result("single_step_genuine"))
    assert r.returncode == 0 and "USABLE AS EVIDENCE" in r.stdout


def test_a_run_with_no_escalating_rows_is_rejected(tmp_path):
    res = _result("real_shape")
    for row in res["rows"]:
        row["would_escalate"] = False
    r = _run_validator(tmp_path, res)
    assert r.returncode == 1 and "NOT USABLE" in r.stdout


def test_runbook_explains_why_equal_interpretation_is_normal():
    text = RUNBOOK.read_text()
    assert "intent.raw_request" in text and "is NORMAL, not a warning sign" in text
