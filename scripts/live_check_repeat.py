#!/usr/bin/env python3
"""live_check_repeat.py -- repeat the draft-plan live check N times, capture provenance, compare runs.

WHY. The first live run (llama3:latest, 11 requests) was ONE stochastic run: the code sets no temperature or
seed, so sampling was uncontrolled and a re-run is expected to differ in wording. The question is not whether
the wording repeats but whether the STRUCTURAL findings survive sampling variation. This tool runs the
existing harness (scripts/live_check_draft_plan.py, unchanged) several times and compares the runs against
criteria that are FIXED IN ADVANCE (docs/studies/OCBRAIN_LIVE_CHECK_REPEAT_RUNS_PROTOCOL_OCT2026.md; the
constants below must match it) so the comparison cannot drift toward whatever the data happens to show.

USAGE (run from the repo root, in the Codespace where Ollama and the model are available)
    python scripts/live_check_repeat.py run --runs 3 --out live_runs          # LIVE; ~7-8 min per run
    python scripts/live_check_repeat.py compare live_runs/<batch_id>          # tables + criteria verdicts
    python scripts/live_check_repeat.py run --runs 2 --offline generic --out /tmp/x   # synthetic self-test, NOT evidence

ISOLATION. The preflight and EVERY run execute in their own fresh Python process (`_worker`, below). This is
load-bearing, not tidiness: core/provider_mesh.py routes every model call through a module-level prompt cache
(core/prompt/cache.py, keyed by the full prompt, 1 h TTL) and a shared network client. When this tool used to
run all runs inside ONE process, runs 2..N were replays of run 1 served from that cache (0 ms calls, identical
output) and the first call of each later run hit a closed event loop. See the protocol's "Deviation 1".

`run` first does a one-request PREFLIGHT and aborts (exit 2) if the provider is not working, so a bad setup
costs seconds, not 25 minutes. It then records, automatically: repo commit + dirty state, Python/platform, the
SHA-256 of this tool and the harness, `ollama list` and `ollama show <model>` BEFORE and AFTER the batch (and
whether the model ID changed in between), and each run's UTC start/end. Each run's JSON is written as soon as
it finishes, so an interrupted batch keeps what it completed.

`compare` evaluates the pre-registered criteria. PASS means "no contradiction found in these runs", never
"proved": the result characterizes ONE model at default sampling over N runs. Offline/synthetic and degraded runs
are flagged NOT EVIDENCE and excluded, and so is any run that looks like a REPLAY (finished faster than
REPLAY_MIN_SECONDS_PER_ESCALATING_REQUEST allows, or output byte-identical to an earlier run in the batch). The word-level screens are proxies; read the steps it prints for REVIEW.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.cognitive import content_anchor as ca  # noqa: E402

# ── Pre-registered criteria (keep identical to the protocol document) ────────────────────────────────
DISPLAY_CAP = ca._MAX_STEPS_SHOWN                  # 5: steps the response shows before "(+N more)"
C2_MEDIAN_RANGE = (5, 9)                           # per-run median steps per plan must lie in this range
C2_MIN_OVER_CAP = 7                                # plans exceeding the display cap, per run, at least
C4_STORY_MIN = 5                                   # story-like plans with a character-structure step, per run
C4_ESSAY_MIN = 1                                   # essay plans with an argument/research step, per run
MIN_VALID_RUNS = 2                                 # fewer valid runs than this -> INSUFFICIENT

# Validity guards -- NOT criteria. Added AFTER the first repeated-run batch (protocol "Deviation 1"): they only decide
# whether a run counts as an independent sample. C1-C4 and every threshold above are unchanged.
# Coarse floor, deliberately far below real latencies: the two real live runs observed so far needed >= ~25 s per
# escalating request (2 model calls, each >= ~12 s); the replayed runs needed 0 s and ~1.4 s per request.
REPLAY_MIN_SECONDS_PER_ESCALATING_REQUEST = 2.0
PREFLIGHT_TIMEOUT_S = 900                          # worker wall-clock limits (a cold model load took ~95 s once)
RUN_TIMEOUT_S = 3600
HARNESS_PATH = ROOT / "scripts" / "live_check_draft_plan.py"

# The reference run: console output supplied by Moncif (llama3:latest). STEP COUNTS ONLY; the step texts are
# not available to the mechanical screens. Order matches the harness's built-in SAMPLE.
BASELINE_RUN0 = {"label": "run 0 (supplied console output; step counts only)",
                 "steps": [7, 6, 7, 7, 5, 11, 5, 7, 9, 7, 12]}

# C3: a conservative lexicon of CONCRETE premise words (genres/subjects), whole-word, lower-case. Generic
# dimension words (genre, theme, tone, setting, plot) are deliberately NOT in it. A hit => REVIEW, not FAIL.
PREMISE_LEXICON = frozenset("""
detective noir mystery murder crime heist spy dragon wizard witch magic magical fantasy sci-fi scifi alien aliens robot
robots android vampire werewolf zombie ghost haunted pirate pirates ninja samurai knight princess king queen romance
love western cowboy superhero apocalypse dystopia utopia space spaceship galaxy mars moon cyberpunk steampunk
medieval viking war soldier detective's school family
""".split())

# Descriptive categories of form/process presupposition (regex over the plan's joined step text).
CATEGORIES = {
    "character_structure": r"\b(characters?|backstor(?:y|ies)|protagonists?|personalit(?:y|ies)|motivations?|arcs?)\b",
    "plot_devices": r"\b(twists?|climax|conflicts?|obstacles?|tension|resolution)\b",
    "worldbuilding": r"\b(setting|world|environment|culture|society)\b",
    "argument_research": r"\b(thesis|research|sources|statistics|evidence|citations?)\b",
    "human_workflow": r"\b(beta|routine|schedule|feedback|publication|publish|demo|record)\b",
    "tooling": r"\b(database|algorithm)\b",
}
_STORY = re.compile(r"\b(story|novel)\b", re.I)
_ESSAY = re.compile(r"\bessay\b", re.I)


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────
def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def default_runner(cmd: Sequence[str], cwd: Optional[str] = None, timeout: int = 30) -> Tuple[int, str]:
    try:
        r = subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""


def load_harness(path: Path = HARNESS_PATH) -> Any:
    spec = importlib.util.spec_from_file_location("live_check_draft_plan", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_check_draft_plan"] = mod
    spec.loader.exec_module(mod)
    return mod


def parse_ollama_list(text: str, model: str) -> Dict[str, str]:
    """Parse the `ollama list` row for `model` (columns: NAME ID SIZE MODIFIED...). {} if absent."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and (parts[0] == model or parts[0].startswith(model + ":")):
            return {"name": parts[0], "id": parts[1], "size": " ".join(parts[2:4]) if len(parts) >= 4 else parts[2],
                    "modified": " ".join(parts[4:]) if len(parts) > 4 else ""}
    return {}


def snapshot_model(run_cmd: Callable[..., Tuple[int, str]], model: str) -> Dict[str, Any]:
    rc_l, listing = run_cmd(["ollama", "list"])
    rc_s, shown = run_cmd(["ollama", "show", model])
    return {"available": rc_l == 0 and rc_s == 0, "ollama_list": listing, "ollama_show": shown,
            "row": parse_ollama_list(listing, model)}


def collect_provenance(run_cmd: Callable[..., Tuple[int, str]], model: str, harness_path: Path, tool_path: Path) -> Dict[str, Any]:
    rc, commit = run_cmd(["git", "rev-parse", "HEAD"], cwd=str(ROOT))
    _, branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT))
    _, porcelain = run_cmd(["git", "status", "--porcelain"], cwd=str(ROOT))
    dirty = [l for l in porcelain.splitlines() if l.strip()]
    return {"repo": {"commit": commit.strip() if rc == 0 else None, "branch": branch.strip(),
                     "dirty": bool(dirty), "dirty_files": dirty[:20]},
            "python": sys.version.split()[0], "platform": platform.platform(),
            "harness_sha256": sha256_file(harness_path), "tool_sha256": sha256_file(tool_path),
            "model_requested": model, "model_before": snapshot_model(run_cmd, model)}


def ensure_git_excluded(out_dir: Path, run_cmd: Callable[..., Tuple[int, str]]) -> bool:
    """Best-effort: add the output dir to .git/info/exclude so results are not committed by accident."""
    rc, gitdir = run_cmd(["git", "rev-parse", "--git-dir"], cwd=str(ROOT))
    if rc != 0:
        return False
    try:
        rel = out_dir.resolve().relative_to(ROOT)
    except ValueError:
        return False
    ex = (ROOT / gitdir.strip() / "info" / "exclude")
    ex.parent.mkdir(parents=True, exist_ok=True)
    entry = f"{rel.as_posix()}/"
    cur = ex.read_text() if ex.exists() else ""
    if entry not in cur.splitlines():
        ex.write_text(cur + ("" if cur.endswith("\n") or not cur else "\n") + entry + "\n")
    return True


class PreflightFailed(RuntimeError):
    pass


class WorkerFailed(RuntimeError):
    """The isolated worker process exited abnormally, timed out, or wrote no readable result."""


class RunFailed(RuntimeError):
    """A run could not be completed; the batch is aborted and the runs already finished stay on disk."""


Executor = Callable[[Sequence[str], str, str, int], Dict[str, Any]]    # (requests, offline, label, timeout_s) -> result


def subprocess_executor(harness_path: Path = HARNESS_PATH, *, python: str = sys.executable) -> Executor:
    """The ONLY executor `run_batch` uses by default: one fresh interpreter per call (the preflight and every run).

    A fresh process has an empty prompt cache, fresh provider/network singletons and its own event loop, so a run
    cannot be served from, or break on, state left by an earlier one. The worker's stdout/stderr are inherited, so
    the live progress stays visible; the result travels through a temporary JSON file.
    """
    def execute(requests: Sequence[str], offline: str, label: str, timeout_s: int) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="live_check_") as td:
            inp, outp = Path(td) / "in.json", Path(td) / "out.json"
            inp.write_text(json.dumps({"requests": list(requests), "offline": offline}))
            cmd = [python, "-u", str(Path(__file__).resolve()), "_worker", "--harness", str(harness_path),
                   "--in", str(inp), "--out", str(outp)]
            try:
                rc = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout_s).returncode
            except subprocess.TimeoutExpired as e:
                raise WorkerFailed(f"{label}: worker timed out after {timeout_s}s") from e
            if rc != 0:
                raise WorkerFailed(f"{label}: worker exited with code {rc} (its output is above)")
            try:
                return json.loads(outp.read_text())
            except (OSError, json.JSONDecodeError) as e:
                raise WorkerFailed(f"{label}: worker wrote no readable result ({type(e).__name__})") from e
    return execute


def _in_process_executor(harness: Any) -> Executor:
    """TEST ONLY. Runs the harness inside THIS process, so the prompt cache, provider singletons and network client
    persist from call to call -- exactly what made the first batch's runs 2..N replays. Never use for a live batch."""
    def execute(requests: Sequence[str], offline: str, label: str, timeout_s: int) -> Dict[str, Any]:
        result = asyncio.run(harness.run(list(requests), offline=offline))
        return {**result, "worker": {"mode": "in-process", "pid": os.getpid()}}
    return execute


def worker_main(argv: Sequence[str]) -> int:
    """Internal entry point (`live_check_repeat.py _worker ...`): run the harness ONCE in this fresh process."""
    ap = argparse.ArgumentParser(prog="live_check_repeat.py _worker")
    ap.add_argument("--harness", required=True)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(list(argv))
    spec = json.loads(Path(a.inp).read_text())
    harness = load_harness(Path(a.harness))
    result = asyncio.run(harness.run(spec["requests"], offline=spec.get("offline", "")))
    result["worker"] = {"mode": "subprocess", "pid": os.getpid(), "python": sys.version.split()[0]}
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False))
    return 0


# ── replay guard (validity, not criteria) ───────────────────────────────────────────────────────────
def _parse_utc(text: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def run_seconds(rec: Dict[str, Any]) -> Optional[float]:
    a, b = _parse_utc(rec.get("started_utc")), _parse_utc(rec.get("finished_utc"))
    return None if a is None or b is None else (b - a).total_seconds()


def fingerprint(rec: Dict[str, Any]) -> str:
    """Hash of everything the model produced that the analysis reads: request, interpretation, steps (escalating rows)."""
    payload = [[r["request"], r.get("interpretation"), r["steps"]] for r in rec["rows"] if r.get("would_escalate")]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def replay_reasons(rec: Dict[str, Any], earlier: Dict[str, int]) -> List[str]:
    """Why this LIVE run cannot be counted as an independent sample. `earlier` maps fingerprint -> run index."""
    esc = [r for r in rec["rows"] if r.get("would_escalate")]
    if rec.get("mode") != "LIVE" or not esc:
        return []
    reasons: List[str] = []
    secs, floor = run_seconds(rec), REPLAY_MIN_SECONDS_PER_ESCALATING_REQUEST * len(esc)
    if secs is not None and secs < floor:
        reasons.append(f"finished in {secs:.0f}s, below the {floor:.0f}s floor ({REPLAY_MIN_SECONDS_PER_ESCALATING_REQUEST:g}s x "
                       f"{len(esc)} escalating requests): the model answers were not freshly generated (cache replay)")
    fp = fingerprint(rec)
    if fp in earlier:
        reasons.append(replay_reasons_identical(earlier[fp]))
    return reasons


def run_batch(n: int, out_root: Path, *, offline: str = "", model: str = "llama3", preflight: bool = True,
              run_cmd: Callable[..., Tuple[int, str]] = default_runner, harness: Any = None,
              execute: Optional[Executor] = None, clock: Callable[[], str] = now_utc,
              requests: Optional[Sequence[str]] = None, log: Callable[[str], None] = print) -> Path:
    harness = harness or load_harness()
    reqs = list(requests) if requests is not None else list(harness.SAMPLE)
    execute = execute or subprocess_executor()
    batch_id = clock().replace("-", "").replace(":", "")
    out = Path(out_root) / batch_id
    out.mkdir(parents=True, exist_ok=True)
    excluded = ensure_git_excluded(Path(out_root), run_cmd)
    meta: Dict[str, Any] = collect_provenance(run_cmd, model, HARNESS_PATH, Path(__file__))
    meta.update({"batch_id": batch_id, "started_utc": clock(), "mode": f"OFFLINE-SYNTHETIC:{offline}" if offline else "LIVE",
                 "requested_runs": n, "git_excluded": excluded, "runs": []})
    if not offline and not meta["model_before"]["available"]:
        log("[WARN] could not read `ollama list`/`ollama show`: the model identity will NOT be recorded for this batch.")
    if preflight:
        log("preflight: 1 request ...")
        try:
            pre = execute(reqs[:1], offline, "preflight", PREFLIGHT_TIMEOUT_S)
        except WorkerFailed as e:
            (out / "meta.json").write_text(json.dumps({**meta, "preflight": "FAILED", "aborted": str(e)}, indent=2))
            raise PreflightFailed(f"preflight failed: {e}. No runs were started.") from e
        meta["preflight_worker"] = pre.get("worker")
        bad = pre["not_evidence"] and not offline
        if bad or any(r.get("degraded") for r in pre["rows"] if r.get("would_escalate")):
            (out / "meta.json").write_text(json.dumps({**meta, "preflight": "FAILED"}, indent=2))
            raise PreflightFailed("preflight failed: the provider did not answer cleanly (see the runbook's Troubleshooting). "
                                  "No runs were started.")
        log("preflight: OK")
    seen: Dict[str, int] = {}
    for i in range(1, n + 1):
        started = clock()
        log(f"run {i}/{n} started {started} ...")
        try:
            result = execute(reqs, offline, f"run {i}", RUN_TIMEOUT_S)
        except WorkerFailed as e:
            meta["aborted"] = f"run {i}: {e}"
            (out / "meta.json").write_text(json.dumps(meta, indent=2))
            raise RunFailed(f"run {i}/{n} failed: {e}. The {i - 1} run(s) already finished are kept in {out}.") from e
        finished = clock()
        rec = {"index": i, "started_utc": started, "finished_utc": finished, **result}
        (out / f"run{i}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))   # persisted immediately
        suspect = replay_reasons(rec, seen)
        seen.setdefault(fingerprint(rec), i)
        meta["runs"].append({"index": i, "started_utc": started, "finished_utc": finished, "file": f"run{i}.json",
                             "not_evidence": result["not_evidence"], "escalating": result["escalated"],
                             "worker": result.get("worker"), "replay_suspect": suspect})
        (out / "meta.json").write_text(json.dumps(meta, indent=2))
        log(f"run {i}/{n} finished {finished} (not_evidence={result['not_evidence']})")
        if suspect:
            log(f"[WARN] run {i} will be excluded as NOT EVIDENCE: " + "; ".join(suspect))
    after = snapshot_model(run_cmd, model)
    b, a = meta["model_before"]["row"].get("id"), after["row"].get("id")
    meta.update({"finished_utc": clock(), "model_after": after,
                 "model_id_changed": (b is not None and a is not None and b != a),
                 "model_id_checked": b is not None and a is not None})
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    return out


# ── analysis ────────────────────────────────────────────────────────────────────────────────────────
def analyze_run(rec: Dict[str, Any]) -> Dict[str, Any]:
    esc = [r for r in rec["rows"] if r.get("would_escalate")]
    degraded = [r["request"] for r in esc if r.get("degraded")]
    reasons: List[str] = []
    if rec.get("mode") != "LIVE":
        reasons.append("not a LIVE run (synthetic/offline)")
    elif rec.get("not_evidence"):
        reasons.append("flagged not_evidence by the harness (every live call degraded)")
    if not esc:
        reasons.append("no escalating request")
    if degraded:
        reasons.append(f"degraded model call in {len(degraded)} request(s)")
    reasons += replay_reasons(rec, {})
    valid = not reasons
    counts = [len(r["steps"]) for r in esc]
    hits, story_hit, story_n, essay_hit, essay_n, cats = [], 0, 0, 0, 0, {k: 0 for k in CATEGORIES}
    for r in esc:
        text = " ".join(r["steps"]).lower()
        for step in r["steps"]:
            for tok in re.findall(r"[a-z][a-z'-]*", step.lower()):
                if tok in PREMISE_LEXICON:
                    hits.append({"request": r["request"], "step": step, "token": tok})
        present = {k for k, rx in CATEGORIES.items() if re.search(rx, text)}
        for k in present:
            cats[k] += 1
        if _STORY.search(r["request"]):
            story_n += 1
            story_hit += "character_structure" in present
        if _ESSAY.search(r["request"]):
            essay_n += 1
            essay_hit += "argument_research" in present
    return {"index": rec.get("index"), "valid": valid, "invalid_reasons": reasons, "mode": rec.get("mode"),
            "fingerprint": fingerprint(rec), "duration_s": run_seconds(rec), "degraded_rows": degraded,
            "requests": [r["request"] for r in esc], "counts": counts, "total": sum(counts),
            "median": statistics.median(counts) if counts else None,
            "single_step": [r["request"] for r in esc if len(r["steps"]) == 1],
            "over_cap": sum(c > DISPLAY_CAP for c in counts), "premise_hits": hits,
            "story_with_character": story_hit, "story_plans": story_n,
            "essay_with_argument": essay_hit, "essay_plans": essay_n, "categories": cats}


def flag_replays(metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Exclude any LIVE run whose output is byte-identical to an EARLIER run of the batch (the earliest one stays)."""
    first: Dict[str, int] = {}
    for m in metrics:
        if m["mode"] != "LIVE" or not m["requests"]:
            continue
        fp = m["fingerprint"]
        if fp in first:
            m["valid"] = False
            m["invalid_reasons"] = m["invalid_reasons"] + [replay_reasons_identical(first[fp])]
        else:
            first[fp] = m["index"]
    return metrics


def replay_reasons_identical(index: int) -> str:
    return f"output identical to run {index}: indistinguishable from a replay, so not an independent sample"


def evaluate(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [m for m in metrics if m["valid"]]
    out: Dict[str, Any] = {"valid_runs": len(valid), "total_runs": len(metrics),
                           "invalid_runs": [m["index"] for m in metrics if not m["valid"]]}
    if len(valid) < MIN_VALID_RUNS:
        out["verdict"] = "INSUFFICIENT"
        out["criteria"] = {}
        return out
    lo, hi = C2_MEDIAN_RANGE
    out["criteria"] = {
        "C1 every plan multi-step (no single-step plan in any run)":
            "PASS" if all(not m["single_step"] for m in valid) else "FAIL",
        f"C2 per-run median steps in [{lo},{hi}] and >= {C2_MIN_OVER_CAP} plans over the {DISPLAY_CAP}-step cap":
            "PASS" if all(lo <= m["median"] <= hi and m["over_cap"] >= C2_MIN_OVER_CAP for m in valid) else "FAIL",
        "C3 no concrete-premise word in any step (lexicon screen; human read still required)":
            "PASS" if all(not m["premise_hits"] for m in valid) else "REVIEW",
        f"C4 form/process presupposition recurs: >= {C4_STORY_MIN} story plans with a character step and "
        f">= {C4_ESSAY_MIN} essay plan with an argument/research step, in every run":
            "PASS" if all(m["story_with_character"] >= C4_STORY_MIN and m["essay_with_argument"] >= C4_ESSAY_MIN
                          for m in valid) else "FAIL",
    }
    out["verdict"] = "FAIL" if "FAIL" in out["criteria"].values() else (
        "REVIEW" if "REVIEW" in out["criteria"].values() else "PASS")
    return out


def isolation_line(meta: Dict[str, Any]) -> str:
    ws = [r.get("worker") or {} for r in (meta.get("runs") or [])]
    pids = [w.get("pid") for w in ws]
    if ws and all(w.get("mode") == "subprocess" for w in ws) and len(set(pids)) == len(pids):
        return "isolation: every run executed in its own fresh process (worker pids " + ", ".join(str(p) for p in pids) + ")"
    return ("isolation: **NOT GUARANTEED** -- these runs did not each execute in a fresh process (batch made before the "
            "isolation fix, or run in-process); a later run may have been served from an earlier run's prompt cache")


def render_report(meta: Dict[str, Any], metrics: List[Dict[str, Any]], ev: Dict[str, Any]) -> str:
    row = (meta.get("model_before") or {}).get("row") or {}
    L = ["# Repeated live check — comparison", ""]
    L.append(f"batch `{meta.get('batch_id')}` | mode **{meta.get('mode')}** | model requested `{meta.get('model_requested')}`"
             + (f" -> `{row.get('name')}` id `{row.get('id')}` {row.get('size', '')}" if row else " (model identity NOT recorded)"))
    repo = meta.get("repo") or {}
    L.append(f"commit `{repo.get('commit')}` ({'DIRTY' if repo.get('dirty') else 'clean'}) | python {meta.get('python')} | "
             f"{meta.get('started_utc')} -> {meta.get('finished_utc')}")
    if repo.get("dirty"):
        L.append("dirty files at batch start: " + "; ".join(f"`{f.strip()}`" for f in (repo.get("dirty_files") or [])[:10]))
    L.append(isolation_line(meta))
    if meta.get("model_id_checked"):
        L.append(f"model id unchanged across the batch: **{not meta.get('model_id_changed')}**")
    else:
        L.append("model id before/after the batch: **not checked** (ollama unavailable)")
    L += ["", "> Observations for ONE model at default sampling over N runs. PASS = no contradiction found, not proof."]
    if str(meta.get("mode", "")).startswith("OFFLINE"):
        L += ["", "**NOT EVIDENCE: synthetic offline runs.**"]
    L += ["", "## Steps per plan (per request, per run)", "", "| request | " + " | ".join(
        [BASELINE_RUN0["label"].split(" (")[0]] + [f"run {m['index']}" for m in metrics]) + " | min–max (runs 1..N) |",
          "|---|" + "---|" * (len(metrics) + 2)]
    reqs = metrics[0]["requests"] if metrics else []
    for i, rq in enumerate(reqs):
        series = [m["counts"][i] if i < len(m["counts"]) else None for m in metrics]
        have = [c for c in series if c is not None]
        base = BASELINE_RUN0["steps"][i] if i < len(BASELINE_RUN0["steps"]) else "–"
        L.append(f"| {rq} | {base} | " + " | ".join("–" if c is None else str(c) for c in series) +
                 f" | {min(have)}–{max(have)} |" if have else f"| {rq} | {base} | – |")
    L += ["", "## Per run", "", "| run | valid | median | total | single-step | over cap | premise-word hits | story→character | essay→argument |",
          "|---|---|---|---|---|---|---|---|---|"]
    L.append(f"| 0 (supplied) | n/a | {statistics.median(BASELINE_RUN0['steps'])} | {sum(BASELINE_RUN0['steps'])} | 0 | "
             f"{sum(c > DISPLAY_CAP for c in BASELINE_RUN0['steps'])} | n/a | n/a | n/a |")
    for m in metrics:
        L.append(f"| {m['index']} | {'yes' if m['valid'] else '**NO**'} | {m['median']} | {m['total']} | {len(m['single_step'])} | "
                 f"{m['over_cap']} | {len(m['premise_hits'])} | {m['story_with_character']}/{m['story_plans']} | "
                 f"{m['essay_with_argument']}/{m['essay_plans']} |")
    L += ["", "## Pre-registered criteria", "", f"valid runs: {ev['valid_runs']}/{ev['total_runs']}"
          + (f" (excluded: {ev['invalid_runs']})" if ev["invalid_runs"] else "")]
    if ev["verdict"] == "INSUFFICIENT":
        L += ["", f"**INSUFFICIENT**: fewer than {MIN_VALID_RUNS} valid runs; no criterion is evaluated."]
    else:
        L.append("")
        for k, v in ev["criteria"].items():
            L.append(f"- **{v}** — {k}")
        L += ["", f"**Overall: {ev['verdict']}**"]
    excluded = [m for m in metrics if not m["valid"]]
    if excluded:
        L += ["", "## Excluded runs (NOT EVIDENCE)", ""]
        L += [f"- run {m['index']}: " + "; ".join(m.get("invalid_reasons") or ["invalid"]) for m in excluded]
    for m in metrics:
        if m["premise_hits"]:
            L += ["", f"### REVIEW: premise-word hits in run {m['index']}"]
            L += [f"- `{h['token']}` in «{h['step']}» (request: {h['request']})" for h in m["premise_hits"][:20]]
    L += ["", "## Category counts per run (plans containing each; descriptive)", "", "| run | " +
          " | ".join(CATEGORIES) + " |", "|---|" + "---|" * len(CATEGORIES)]
    for m in metrics:
        L.append(f"| {m['index']} | " + " | ".join(str(m["categories"][k]) for k in CATEGORIES) + " |")
    return "\n".join(L) + "\n"


def compare_dir(d: Path) -> Tuple[str, Dict[str, Any]]:
    meta = json.loads((d / "meta.json").read_text())
    recs = [json.loads(p.read_text()) for p in sorted(d.glob("run*.json"), key=lambda p: int(re.findall(r"\d+", p.stem)[0]))]
    if not recs:
        raise FileNotFoundError(f"no run*.json in {d}")
    metrics = flag_replays([analyze_run(r) for r in recs])
    ev = evaluate(metrics)
    report = render_report(meta, metrics, ev)
    (d / "report.md").write_text(report)
    (d / "compare.json").write_text(json.dumps({"evaluation": ev, "runs": metrics}, indent=2))
    return report, ev


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "_worker":                       # internal: one fresh process per preflight/run
        return worker_main(args[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="repeat the live check and capture provenance")
    r.add_argument("--runs", type=int, default=3)
    r.add_argument("--out", default="live_runs")
    r.add_argument("--model", default="llama3", help="the Ollama model name the code asks for (default llama3)")
    r.add_argument("--no-preflight", action="store_true")
    r.add_argument("--offline", choices=["single", "generic", "speculative"], default="", help="synthetic self-test (NOT evidence)")
    c = sub.add_parser("compare", help="compare the runs in a batch directory")
    c.add_argument("batch_dir")
    a = ap.parse_args(args)
    if a.cmd == "run":
        if a.runs < 1:
            print("[ERROR] --runs must be >= 1")
            return 2
        try:
            out = run_batch(a.runs, Path(a.out), offline=a.offline, model=a.model, preflight=not a.no_preflight)
        except (PreflightFailed, RunFailed) as e:
            print(f"[ERROR] {e}")
            return 2
        print(f"\nbatch written to {out}\nnext: python scripts/live_check_repeat.py compare {out}")
        return 0
    try:
        report, _ = compare_dir(Path(a.batch_dir))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ERROR] {e}")
        return 2
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
