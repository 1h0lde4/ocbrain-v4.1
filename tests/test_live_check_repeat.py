"""tests/test_live_check_repeat.py -- scripts/live_check_repeat.py (repeated live check + pre-registered comparison).

These test the INSTRUMENT with a fake harness and a fake command runner (no model, no ollama, no network). They prove
nothing about any real model; that is what the live batch is for. Key properties: provenance is captured, a bad
provider aborts before any run, runs persist incrementally, a model change mid-batch is detected, every
pre-registered criterion can independently FAIL/REVIEW, synthetic or degraded runs never count as evidence, and the
tool's constants match the protocol document.
"""
import asyncio
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("live_check_repeat", ROOT / "scripts" / "live_check_repeat.py")
rp = importlib.util.module_from_spec(_spec)
sys.modules["live_check_repeat"] = rp
_spec.loader.exec_module(rp)
lc = rp.load_harness()
PROTOCOL = ROOT / "docs" / "studies" / "OCBRAIN_LIVE_CHECK_REPEAT_RUNS_PROTOCOL_OCT2026.md"

REAL_OLLAMA_LIST = ("NAME             ID              SIZE      MODIFIED     \n"
                    "llama3:latest    365c0bd3c000    4.7 GB    37 hours ago\n")


# ── fakes ───────────────────────────────────────────────────────────────────────────────────────────
def good_steps(req: str, variant: int = 0):
    base = ["Brainstorm ideas", "Create an outline", "Write a first draft", "Revise the draft", "Edit for grammar",
            "Proofread", "Finalize"]
    low = req.lower()
    if re.search(r"\b(story|novel)\b", low):
        base[1] = "Create a detailed outline including character arcs and key events"
        base[2] = "Develop character profiles, including backstories and motivations"
    if "essay" in low:
        base[1] = "Develop a thesis statement"
        base[2] = "Research and gather credible sources"
    return base[: 7 + (variant % 2) * 0]  # always 7: stable by construction


def make_result(req_steps, mode="LIVE", degraded_for=(), not_evidence=False):
    rows = []
    for req, steps in req_steps:
        deg = ["decompose: TimeoutError"] if req in degraded_for else []
        rows.append({"request": req, "would_escalate": True, "interpretation": req, "steps": steps, "degraded": deg,
                     "steps_detail": [], "plan_label": "generic", "shown_to_user": ""})
    return {"mode": mode, "rows": rows, "escalated": len(rows), "label_counts": {}, "not_evidence": not_evidence}


class FakeHarness:
    """Stands in for scripts/live_check_draft_plan.py; `plan` decides each run's steps."""
    SAMPLE = list(lc.SAMPLE)

    def __init__(self, plan=None, degraded_requests=(), preflight_degraded=False):
        self.calls = []
        self.plan = plan or (lambda req, call: good_steps(req))
        self.degraded_requests = degraded_requests
        self.preflight_degraded = preflight_degraded

    async def run(self, requests, offline=""):
        self.calls.append(list(requests))
        call = len(self.calls)
        if len(requests) == 1 and call == 1 and self.preflight_degraded:
            return make_result([(requests[0], [requests[0]])], degraded_for=requests, not_evidence=True)
        if offline:
            return make_result([(r, self.plan(r, call)) for r in requests], mode=f"OFFLINE-SYNTHETIC:{offline}",
                               not_evidence=True)
        return make_result([(r, self.plan(r, call)) for r in requests], degraded_for=self.degraded_requests)


def runner_factory(model_ids=("365c0bd3c000",), ollama=True, dirty=False):
    state = {"list_calls": 0}

    def run_cmd(cmd, cwd=None, timeout=30):
        cmd = list(cmd)
        if cmd[:2] == ["git", "rev-parse"] and "--git-dir" in cmd:
            return 1, ""                                   # not a git repo -> exclude step is skipped
        if cmd[:3] == ["git", "rev-parse", "HEAD"]:
            return 0, "abc123def4567890abc123def4567890abc12345\n"
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, "tools/live-check-repeat-runs\n"
        if cmd[:2] == ["git", "status"]:
            return 0, (" M scripts/x.py\n" if dirty else "")
        if cmd[:2] == ["ollama", "list"]:
            if not ollama:
                return 127, ""
            i = min(state["list_calls"], len(model_ids) - 1)
            state["list_calls"] += 1
            return 0, REAL_OLLAMA_LIST.replace("365c0bd3c000", model_ids[i])
        if cmd[:2] == ["ollama", "show"]:
            return (0, "  Model\n    parameters          8.0B\n    quantization        Q4_0\n") if ollama else (127, "")
        raise AssertionError(cmd)
    return run_cmd


def batch(tmp_path, n=3, **kw):
    clock_vals = iter(f"2026-10-04T10:{i // 60:02d}:{i % 60:02d}Z" for i in range(200))
    return rp.run_batch(n, tmp_path, harness=kw.pop("harness", FakeHarness()),
                        run_cmd=kw.pop("run_cmd", runner_factory()), clock=lambda: next(clock_vals),
                        log=lambda s: None, **kw)


def metrics_from(steps_by_req, **kw):
    return rp.analyze_run(make_result(list(steps_by_req.items()), **kw))


def good_run(index=1):
    m = rp.analyze_run({**make_result([(r, good_steps(r)) for r in lc.SAMPLE]), "index": index})
    return m


# ── parsing / provenance ────────────────────────────────────────────────────────────────────────────
def test_parse_ollama_list_on_the_real_output():
    row = rp.parse_ollama_list(REAL_OLLAMA_LIST, "llama3")
    assert row["name"] == "llama3:latest" and row["id"] == "365c0bd3c000"
    assert row["size"] == "4.7 GB" and row["modified"].startswith("37 hours")
    assert rp.parse_ollama_list(REAL_OLLAMA_LIST, "mistral") == {}


def test_provenance_is_captured(tmp_path):
    out = batch(tmp_path, n=1, dirty=False) if False else batch(tmp_path, n=1)
    meta = json.loads((out / "meta.json").read_text())
    assert meta["repo"]["commit"].startswith("abc123") and meta["repo"]["dirty"] is False
    assert meta["python"] and meta["platform"]
    assert len(meta["harness_sha256"]) == 64 and len(meta["tool_sha256"]) == 64
    assert meta["model_before"]["row"]["id"] == "365c0bd3c000" and "Q4_0" in meta["model_before"]["ollama_show"]
    assert meta["model_id_checked"] is True and meta["model_id_changed"] is False
    assert meta["runs"][0]["started_utc"] < meta["runs"][0]["finished_utc"]


def test_dirty_tree_is_recorded(tmp_path):
    meta = json.loads((batch(tmp_path, n=1, run_cmd=runner_factory(dirty=True)) / "meta.json").read_text())
    assert meta["repo"]["dirty"] is True and meta["repo"]["dirty_files"]


def test_missing_ollama_is_recorded_not_fatal(tmp_path):
    out = batch(tmp_path, n=1, run_cmd=runner_factory(ollama=False))
    meta = json.loads((out / "meta.json").read_text())
    assert meta["model_before"]["available"] is False and meta["model_id_checked"] is False
    report, _ = rp.compare_dir(out)
    assert "model identity NOT recorded" in report and "not checked" in report


def test_model_change_during_the_batch_is_detected(tmp_path):
    out = batch(tmp_path, n=2, run_cmd=runner_factory(model_ids=("aaaaaaaaaaaa", "bbbbbbbbbbbb")))
    meta = json.loads((out / "meta.json").read_text())
    assert meta["model_id_checked"] is True and meta["model_id_changed"] is True
    report, _ = rp.compare_dir(out)
    assert "model id unchanged across the batch: **False**" in report


# ── batch mechanics ─────────────────────────────────────────────────────────────────────────────────
def test_runs_are_persisted_incrementally(tmp_path):
    seen = []

    class Spy(FakeHarness):
        async def run(self, requests, offline=""):
            if len(requests) > 1:
                seen.append(sorted(p.name for p in Path(tmp_path).rglob("run*.json")))
            return await super().run(requests, offline)
    batch(tmp_path, n=3, harness=Spy())
    assert seen == [[], ["run1.json"], ["run1.json", "run2.json"]]   # each run's file exists before the next starts


def test_preflight_failure_aborts_before_any_run(tmp_path):
    h = FakeHarness(preflight_degraded=True)
    with pytest.raises(rp.PreflightFailed):
        batch(tmp_path, n=3, harness=h)
    assert len(h.calls) == 1                                          # only the one-request preflight ran
    out = next(Path(tmp_path).iterdir())
    assert not list(out.glob("run*.json"))
    assert json.loads((out / "meta.json").read_text())["preflight"] == "FAILED"


def test_preflight_can_be_skipped(tmp_path):
    h = FakeHarness()
    batch(tmp_path, n=1, harness=h, preflight=False)
    assert len(h.calls) == 1 and len(h.calls[0]) == len(lc.SAMPLE)


def test_offline_batch_is_never_evidence(tmp_path):
    out = batch(tmp_path, n=2, offline="generic")
    report, ev = rp.compare_dir(out)
    assert "NOT EVIDENCE" in report and ev["verdict"] == "INSUFFICIENT" and ev["valid_runs"] == 0


# ── metrics ─────────────────────────────────────────────────────────────────────────────────────────
def test_analyze_run_metrics():
    m = metrics_from({"write a story": ["a"] * 7, "write an essay": ["Develop a thesis", "Research sources", "c", "d", "e", "f"],
                      "tell me a joke": ["only one"]})
    assert m["valid"] and m["counts"] == [7, 6, 1] and m["total"] == 14 and m["median"] == 6
    assert m["single_step"] == ["tell me a joke"] and m["over_cap"] == 2
    assert m["essay_with_argument"] == 1 and m["essay_plans"] == 1 and m["story_plans"] == 1


def test_degraded_row_invalidates_the_run():
    m = metrics_from({"write a story": ["a"] * 7, "write a poem": ["a"] * 7}, degraded_for=("write a poem",))
    assert not m["valid"] and m["degraded_rows"] == ["write a poem"]


def test_premise_lexicon_hit_is_found_and_whole_word():
    m = metrics_from({"write a story": ["Write a detective story", "Plan the family tree", "reasoning about warfare"]})
    toks = sorted(h["token"] for h in m["premise_hits"])
    assert toks == ["detective", "family"]                           # 'warfare' must NOT match 'war'


# ── criteria: each one can fail independently ───────────────────────────────────────────────────────
def three_good():
    return [good_run(1), good_run(2), good_run(3)]


def test_all_criteria_pass_on_stable_runs():
    ev = rp.evaluate(three_good())
    assert ev["verdict"] == "PASS" and set(ev["criteria"].values()) == {"PASS"} and ev["valid_runs"] == 3


def test_c1_fails_when_any_plan_is_single_step_in_any_run():
    runs = three_good()
    runs[1]["single_step"] = ["write a poem"]
    ev = rp.evaluate(runs)
    assert ev["verdict"] == "FAIL" and ev["criteria"][next(k for k in ev["criteria"] if k.startswith("C1"))] == "FAIL"


@pytest.mark.parametrize("field,value", [("median", 4), ("median", 10), ("over_cap", 6)])
def test_c2_fails_outside_the_preregistered_range(field, value):
    runs = three_good()
    runs[2][field] = value
    ev = rp.evaluate(runs)
    assert ev["criteria"][next(k for k in ev["criteria"] if k.startswith("C2"))] == "FAIL"


def test_c2_boundaries_are_inclusive():
    runs = three_good()
    runs[0]["median"], runs[1]["median"], runs[2]["median"] = 5, 9, 7
    runs[0]["over_cap"] = 7
    assert rp.evaluate(runs)["criteria"][next(k for k in rp.evaluate(runs)["criteria"] if k.startswith("C2"))] == "PASS"


def test_c3_is_review_not_fail_and_the_hit_is_printed():
    runs = three_good()
    runs[0]["premise_hits"] = [{"request": "write a story", "step": "Write a dragon tale", "token": "dragon"}]
    ev = rp.evaluate(runs)
    assert ev["criteria"][next(k for k in ev["criteria"] if k.startswith("C3"))] == "REVIEW" and ev["verdict"] == "REVIEW"
    report = rp.render_report({"batch_id": "x", "mode": "LIVE"}, runs, ev)
    assert "REVIEW: premise-word hits in run 1" in report and "Write a dragon tale" in report


@pytest.mark.parametrize("field,value", [("story_with_character", 4), ("essay_with_argument", 0)])
def test_c4_fails_when_presuppositions_do_not_recur(field, value):
    runs = three_good()
    runs[1][field] = value
    ev = rp.evaluate(runs)
    assert ev["criteria"][next(k for k in ev["criteria"] if k.startswith("C4"))] == "FAIL"


def test_fail_outranks_review():
    runs = three_good()
    runs[0]["premise_hits"] = [{"request": "r", "step": "s", "token": "dragon"}]
    runs[1]["single_step"] = ["write a poem"]
    assert rp.evaluate(runs)["verdict"] == "FAIL"


def test_invalid_run_is_excluded_not_counted_as_a_counterexample():
    runs = three_good()
    runs[1]["valid"] = False
    runs[1]["single_step"] = ["write a poem"]                        # would FAIL C1 if it were counted
    ev = rp.evaluate(runs)
    assert ev["invalid_runs"] == [2] and ev["valid_runs"] == 2 and ev["verdict"] == "PASS"


def test_one_valid_run_is_insufficient():
    runs = three_good()
    runs[1]["valid"] = runs[2]["valid"] = False
    ev = rp.evaluate(runs)
    assert ev["verdict"] == "INSUFFICIENT" and ev["criteria"] == {}


# ── report / CLI ────────────────────────────────────────────────────────────────────────────────────
def test_compare_end_to_end_report(tmp_path):
    out = batch(tmp_path, n=3)
    report, ev = rp.compare_dir(out)
    assert ev["verdict"] == "PASS"
    assert "run 0" in report and "| 12 |" in report                  # baseline column present (run 0 had a 12-step plan)
    assert "Observations for ONE model at default sampling" in report and "not proof" in report
    assert "`llama3:latest`" in report and "365c0bd3c000" in report and "unchanged across the batch: **True**" in report
    assert (out / "report.md").exists() and json.loads((out / "compare.json").read_text())["evaluation"]["verdict"] == "PASS"


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    assert rp.main(["compare", str(tmp_path / "missing")]) == 2
    assert rp.main(["run", "--runs", "0"]) == 2

    def boom(*a, **k):
        raise rp.PreflightFailed("preflight failed")
    monkeypatch.setattr(rp, "run_batch", boom)
    assert rp.main(["run", "--runs", "2", "--out", str(tmp_path)]) == 2
    assert "preflight failed" in capsys.readouterr().out


# ── pre-registration integrity ──────────────────────────────────────────────────────────────────────
def test_protocol_document_matches_the_tools_constants():
    doc = PROTOCOL.read_text()
    lo, hi = rp.C2_MEDIAN_RANGE
    assert f"**[{lo}, {hi}]**" in doc
    assert f"**≥ {rp.C2_MIN_OVER_CAP}** plans exceed the {rp.DISPLAY_CAP}-step display cap" in doc
    assert f"**≥ {rp.C4_STORY_MIN}** of the 6 story/novel plans" in doc
    assert f"**≥ {rp.C4_ESSAY_MIN}** of the 2 essay plans" in doc
    assert f"Fewer than {rp.MIN_VALID_RUNS} valid runs" in doc
    for w in rp.PREMISE_LEXICON:                                   # every lexicon word is published in the protocol
        assert w in doc, w


def test_constants_stay_in_sync_with_the_product_and_the_supplied_run():
    assert rp.DISPLAY_CAP == rp.ca._MAX_STEPS_SHOWN == 5
    assert sum(rp.BASELINE_RUN0["steps"]) == 83 and len(rp.BASELINE_RUN0["steps"]) == len(lc.SAMPLE) == 11
    assert sum(c > rp.DISPLAY_CAP for c in rp.BASELINE_RUN0["steps"]) == 9
    story = [r for r in lc.SAMPLE if re.search(r"\b(story|novel)\b", r, re.I)]
    essay = [r for r in lc.SAMPLE if re.search(r"\bessay\b", r, re.I)]
    assert (len(story), len(essay)) == (6, 2)                       # the denominators the protocol states
