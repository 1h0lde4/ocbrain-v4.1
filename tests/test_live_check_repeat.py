"""tests/test_live_check_repeat.py -- scripts/live_check_repeat.py (repeated live check + pre-registered comparison).

These test the INSTRUMENT with a fake harness and a fake command runner (no model, no ollama, no network). They prove
nothing about any real model; that is what the live batch is for. The isolation tests spawn REAL worker processes, but
only against a tiny stub harness script (or the real harness in --offline mode), never against a model. Key properties: provenance is captured, a bad
provider aborts before any run, runs persist incrementally, a model change mid-batch is detected, every
pre-registered criterion can independently FAIL/REVIEW, synthetic or degraded runs never count as evidence, and the
tool's constants match the protocol document -- and (after the first batch turned out to be replays of run 1 served
by the in-process prompt cache) every preflight/run executes in its own fresh process, and a run that looks like a
replay is excluded as NOT EVIDENCE instead of being counted as a stable repeat.
"""
import ast
import asyncio
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timedelta
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
    base = [f"Brainstorm ideas (sample {variant})", "Create an outline", "Write a first draft", "Revise the draft", "Edit for grammar",
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
        self.plan = plan or (lambda req, call: good_steps(req, variant=call))   # wording differs per call, structure does not
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


def fake_clock(step=60):
    """A clock that advances `step` seconds per call, so a fake run lasts a realistic minute, not one second."""
    state = {"k": -1}

    def clock():
        state["k"] += 1
        return (datetime(2026, 10, 4, 10, 0, 0) + timedelta(seconds=step * state["k"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    return clock


def batch(tmp_path, n=3, **kw):
    h = kw.pop("harness", FakeHarness())
    return rp.run_batch(n, tmp_path, harness=h, execute=kw.pop("execute", rp._in_process_executor(h)),
                        run_cmd=kw.pop("run_cmd", runner_factory()), clock=kw.pop("clock", fake_clock()),
                        log=kw.pop("log", lambda s: None), **kw)


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


# ── isolation: each preflight/run gets a fresh interpreter ─────────────────────────────────────────
STUB_HARNESS = """
import os
SAMPLE = ["write a story", "write an essay"]
_N = 0
async def run(requests, offline=""):
    global _N
    _N += 1
    rows = [{"request": r, "would_escalate": True, "interpretation": r,
             "steps": [f"step {i} of pid {os.getpid()}" for i in range(6)], "degraded": []} for r in requests]
    return {"mode": "LIVE", "rows": rows, "escalated": len(rows), "label_counts": {}, "not_evidence": False,
            "stub_calls_in_this_process": _N, "stub_pid": os.getpid(), "stub_cwd": os.getcwd()}
"""
CRASH_HARNESS = "async def run(requests, offline=''):\n    raise RuntimeError('boom')\n"
HANG_HARNESS = "import time\nasync def run(requests, offline=''):\n    time.sleep(30)\n"


def write_stub(tmp_path, text, name="stub_harness.py"):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_every_preflight_and_run_gets_a_fresh_interpreter(tmp_path):
    stub = write_stub(tmp_path, STUB_HARNESS)
    out = batch(tmp_path / "out", n=3, execute=rp.subprocess_executor(stub), requests=["write a story", "write an essay"])
    recs = [json.loads((out / f"run{i}.json").read_text()) for i in (1, 2, 3)]
    meta = json.loads((out / "meta.json").read_text())
    assert [r["stub_calls_in_this_process"] for r in recs] == [1, 1, 1]       # never a 2nd call in one process
    assert {os.path.realpath(r["stub_cwd"]) for r in recs} == {os.path.realpath(str(ROOT))}   # workers run from the repo root, as the user's shell did
    pids = [r["stub_pid"] for r in recs] + [meta["preflight_worker"]["pid"]]
    assert len(set(pids)) == 4 and os.getpid() not in pids                    # preflight + 3 runs, all distinct, none is us
    assert all(r["worker"]["mode"] == "subprocess" and r["worker"]["pid"] == r["stub_pid"] for r in recs)
    report, _ = rp.compare_dir(out)
    assert "every run executed in its own fresh process" in report


def test_the_stub_really_detects_shared_state():
    """Sanity of the test above: run in ONE process (the old design) the same stub counts 1, 2, 3."""
    mod = type(sys)("stub_h")
    exec(STUB_HARNESS, mod.__dict__)
    ex = rp._in_process_executor(mod)
    counts = [ex(["write a story"], "", "run", 60)["stub_calls_in_this_process"] for _ in range(3)]
    assert counts == [1, 2, 3]


def test_batch_without_an_explicit_executor_uses_the_subprocess_one(tmp_path, monkeypatch):
    made = []

    def fake_factory(*a, **k):
        made.append(1)
        return rp._in_process_executor(FakeHarness())
    monkeypatch.setattr(rp, "subprocess_executor", fake_factory)
    rp.run_batch(1, tmp_path, harness=FakeHarness(), run_cmd=runner_factory(), clock=fake_clock(), log=lambda s: None,
                 preflight=False)
    assert made == [1]


def test_asyncio_run_is_confined_to_the_worker_and_the_test_only_executor():
    """`run_batch` and the default executor must never call asyncio.run themselves: only the fresh worker process does."""
    owners = set()

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == "run" and isinstance(f.value, ast.Name) and f.value.id == "asyncio":
                owners.add(tuple(self.stack))
            self.generic_visit(node)
    V().visit(ast.parse((ROOT / "scripts" / "live_check_repeat.py").read_text()))
    assert owners == {("worker_main",), ("_in_process_executor", "execute")}, owners


def test_real_worker_in_offline_mode_is_isolated_end_to_end(tmp_path, capsys):
    """Spawns the REAL worker against the REAL harness in --offline mode (no model, no network)."""
    if rp.default_runner(["git", "rev-parse", "--git-dir"], cwd=str(ROOT))[0] != 0:
        pytest.skip("not a git checkout")
    rc = rp.main(["run", "--runs", "2", "--offline", "generic", "--out", str(tmp_path)])
    assert rc == 0
    out = next(Path(tmp_path).iterdir())
    r1, r2 = (json.loads((out / f"run{i}.json").read_text()) for i in (1, 2))
    assert r1["worker"]["mode"] == r2["worker"]["mode"] == "subprocess"
    assert len({r1["worker"]["pid"], r2["worker"]["pid"], os.getpid()}) == 3
    assert r1["mode"].startswith("OFFLINE")                               # and it is never evidence
    assert "NOT EVIDENCE" in rp.compare_dir(out)[0]


def test_a_crashing_worker_is_reported_not_swallowed(tmp_path):
    ex = rp.subprocess_executor(write_stub(tmp_path, CRASH_HARNESS))
    with pytest.raises(rp.WorkerFailed, match="exited with code"):
        ex(["write a story"], "", "run 1", 60)


def test_a_hung_worker_is_killed_at_the_timeout(tmp_path):
    ex = rp.subprocess_executor(write_stub(tmp_path, HANG_HARNESS))
    with pytest.raises(rp.WorkerFailed, match="timed out"):
        ex(["write a story"], "", "run 1", 2)


def test_worker_failure_in_the_preflight_aborts_before_any_run(tmp_path):
    def broken(requests, offline, label, timeout_s):
        raise rp.WorkerFailed(f"{label}: worker exited with code 1")
    with pytest.raises(rp.PreflightFailed, match="worker exited"):
        batch(tmp_path, n=3, execute=broken)
    out = next(Path(tmp_path).iterdir())
    assert not list(out.glob("run*.json")) and json.loads((out / "meta.json").read_text())["preflight"] == "FAILED"


def test_worker_failure_in_a_run_keeps_the_finished_runs(tmp_path):
    h = FakeHarness()
    inner, calls = rp._in_process_executor(h), {"n": 0}

    def flaky(requests, offline, label, timeout_s):
        calls["n"] += 1
        if calls["n"] == 3:                                               # preflight, run 1, then run 2 dies
            raise rp.WorkerFailed(f"{label}: worker exited with code 1")
        return inner(requests, offline, label, timeout_s)
    with pytest.raises(rp.RunFailed, match="run 2/3 failed"):
        batch(tmp_path, n=3, harness=h, execute=flaky)
    out = next(Path(tmp_path).iterdir())
    assert (out / "run1.json").exists() and not (out / "run2.json").exists()
    assert json.loads((out / "meta.json").read_text())["aborted"].startswith("run 2:")


def test_cli_returns_2_when_a_run_fails(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise rp.RunFailed("run 2/3 failed: worker exited with code 1")
    monkeypatch.setattr(rp, "run_batch", boom)
    assert rp.main(["run", "--runs", "3", "--out", str(tmp_path)]) == 2
    assert "run 2/3 failed" in capsys.readouterr().out


# ── replay guard: a replay is excluded, never counted as a stable repeat ────────────────────────────
def live_rec(index, salt="a", seconds=600, n=11, mode="LIVE"):
    rows = [{"request": r, "would_escalate": True, "interpretation": r,
             "steps": [f"{salt} {r} {k}" for k in range(7)], "degraded": []} for r in lc.SAMPLE[:n]]
    t0 = datetime(2026, 10, 9, 11, 0, 0)
    return {"index": index, "started_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finished_utc": (t0 + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": mode, "rows": rows, "escalated": len(rows), "label_counts": {}, "not_evidence": mode != "LIVE"}


def test_a_run_faster_than_the_floor_is_not_evidence():
    m = rp.analyze_run(live_rec(1, seconds=0))
    assert m["valid"] is False and any("below the" in r and "cache replay" in r for r in m["invalid_reasons"])


def test_the_floor_boundary_is_exact():
    floor = rp.REPLAY_MIN_SECONDS_PER_ESCALATING_REQUEST * 11                 # 22 s for 11 escalating requests
    assert rp.analyze_run(live_rec(1, seconds=int(floor)))["valid"] is True   # exactly at the floor: counts
    assert rp.analyze_run(live_rec(1, seconds=int(floor) - 1))["valid"] is False


def test_identical_output_after_the_first_run_is_excluded_and_the_first_stays():
    ms = rp.flag_replays([rp.analyze_run(live_rec(1, "same")), rp.analyze_run(live_rec(2, "same")),
                          rp.analyze_run(live_rec(3, "same"))])
    assert [m["valid"] for m in ms] == [True, False, False]
    assert "identical to run 1" in ms[1]["invalid_reasons"][-1] and "identical to run 1" in ms[2]["invalid_reasons"][-1]


def test_different_wording_is_not_flagged():
    ms = rp.flag_replays([rp.analyze_run(live_rec(i, f"salt{i}")) for i in (1, 2, 3)])
    assert [m["valid"] for m in ms] == [True, True, True]


def test_one_changed_step_is_enough_to_differ():
    a, b = live_rec(1, "x"), live_rec(2, "x")
    b["rows"][4]["steps"][3] = "a genuinely different step"
    assert rp.fingerprint(a) != rp.fingerprint(b)


def test_offline_runs_get_one_reason_not_a_replay_pile_on():
    ms = rp.flag_replays([rp.analyze_run(live_rec(i, "same", seconds=0, mode="OFFLINE-SYNTHETIC:generic")) for i in (1, 2)])
    assert [m["invalid_reasons"] for m in ms] == [["not a LIVE run (synthetic/offline)"]] * 2


def test_records_without_timestamps_are_not_flagged_by_the_duration_rule():
    rec = live_rec(1)
    del rec["started_utc"], rec["finished_utc"]
    assert rp.analyze_run(rec)["valid"] is True                              # documented limitation: legacy/synthetic records


def test_the_first_batch_shape_is_now_insufficient_not_pass(tmp_path):
    """The batch that actually happened: run 1 genuine (~6.3 min), run 2 in 0 s, run 3 in 15 s, same output."""
    d = tmp_path / "20261009T112612Z"
    d.mkdir()
    meta = {"batch_id": d.name, "mode": "LIVE", "model_requested": "llama3", "repo": {"commit": "258a58a", "dirty": True,
            "dirty_files": [" M config/settings.toml"]}, "python": "3.11.9", "runs": []}
    (d / "meta.json").write_text(json.dumps(meta))
    for i, secs in ((1, 380), (2, 0), (3, 15)):
        (d / f"run{i}.json").write_text(json.dumps(live_rec(i, "same", seconds=secs)))
    report, ev = rp.compare_dir(d)
    assert ev["verdict"] == "INSUFFICIENT" and ev["invalid_runs"] == [2, 3] and ev["valid_runs"] == 1
    assert "Overall: PASS" not in report and "Excluded runs (NOT EVIDENCE)" in report
    assert "run 2:" in report and "run 3:" in report and "isolation: **NOT GUARANTEED**" in report
    assert "config/settings.toml" in report                                    # the DIRTY files are now shown


def test_a_replay_is_warned_about_while_the_batch_runs(tmp_path):
    logs = []
    h = FakeHarness(plan=lambda req, call: good_steps(req, variant=0))        # identical wording every call
    out = batch(tmp_path, n=3, harness=h, log=logs.append)
    assert any(l.startswith("[WARN] run 2 will be excluded") for l in logs)
    runs = json.loads((out / "meta.json").read_text())["runs"]
    assert runs[0]["replay_suspect"] == [] and runs[1]["replay_suspect"] and runs[2]["replay_suspect"]
    assert rp.compare_dir(out)[1]["verdict"] == "INSUFFICIENT"


def test_an_in_process_batch_is_labelled_not_guaranteed_independent(tmp_path):
    report, _ = rp.compare_dir(batch(tmp_path, n=2))
    assert "isolation: **NOT GUARANTEED**" in report


# ── pre-registration integrity ──────────────────────────────────────────────────────────────────────
def test_protocol_document_matches_the_tools_constants():
    doc = PROTOCOL.read_text()
    lo, hi = rp.C2_MEDIAN_RANGE
    assert f"**[{lo}, {hi}]**" in doc
    assert f"**≥ {rp.C2_MIN_OVER_CAP}** plans exceed the {rp.DISPLAY_CAP}-step display cap" in doc
    assert f"**≥ {rp.C4_STORY_MIN}** of the 6 story/novel plans" in doc
    assert f"**≥ {rp.C4_ESSAY_MIN}** of the 2 essay plans" in doc
    assert f"Fewer than {rp.MIN_VALID_RUNS} valid runs" in doc
    assert f"**{rp.REPLAY_MIN_SECONDS_PER_ESCALATING_REQUEST:g} s per escalating request**" in doc    # replay floor (Deviation 1)
    assert "Deviation 1" in doc and "fresh process" in doc and "identical to an earlier run" in doc
    for w in rp.PREMISE_LEXICON:                                   # every lexicon word is published in the protocol
        assert w in doc, w


def test_constants_stay_in_sync_with_the_product_and_the_supplied_run():
    assert rp.DISPLAY_CAP == rp.ca._MAX_STEPS_SHOWN == 5
    assert sum(rp.BASELINE_RUN0["steps"]) == 83 and len(rp.BASELINE_RUN0["steps"]) == len(lc.SAMPLE) == 11
    assert sum(c > rp.DISPLAY_CAP for c in rp.BASELINE_RUN0["steps"]) == 9
    story = [r for r in lc.SAMPLE if re.search(r"\b(story|novel)\b", r, re.I)]
    essay = [r for r in lc.SAMPLE if re.search(r"\bessay\b", r, re.I)]
    assert (len(story), len(essay)) == (6, 2)                       # the denominators the protocol states
