"""DEBT-003 acceptance criterion, literally: kill the process mid-execution, restart, resume.

The Kernel v1.0 Closure Audit (item 5) required "a new integration test that kills and restarts the process
mid-execution".  ``test_workflow_runtime.py`` proves that ``resume()`` works on freshly *constructed* objects
over one SQLite file, inside a single Python process (its ``CountingNodeWorker.invocations`` list is shared by
both phases), so it cannot show behavior across a real process boundary.  This test uses two real child
processes: the first is hard-killed (``os._exit(137)``: no cleanup, no ``except``, no ``atexit``) while node
``b`` is executing; the second resumes from nothing but the on-disk event database.

What it pins:
  * ``a`` (completed before the kill) is NOT re-executed            -> no duplicated completed work
  * ``b`` (interrupted by the kill) IS re-executed: it starts twice, once per process, and completes once
        -> resume is at-least-once for the interrupted node; a checkpoint cannot prove that node had no
           external effect (the reason DEBT-015 sub-item (7) exists)
  * ``c`` runs once, after the restart                              -> no lost work
What it does NOT claim: exactly-once external effects, or safety of concurrent ``resume()`` calls (DEBT-028).
"""
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHILD = Path(__file__).resolve().parent / "_crash_restart_child.py"
KILL_EXIT_CODE = 137


def _run_child(mode: str, db: Path, log: Path, instance_id: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(CHILD), str(REPO), mode, str(db), str(log), instance_id],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=120,
    )


def _read(log: Path) -> list:
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _instance_id_from_checkpoint(db: Path) -> str:
    con = sqlite3.connect(str(db))
    try:
        names = [r[0] for r in con.execute(
            "SELECT DISTINCT checkpoint FROM events WHERE checkpoint LIKE 'workflow:%'")]
    finally:
        con.close()
    assert len(names) == 1, f"expected exactly one workflow checkpoint to survive the kill, got {names}"
    return names[0].split(":", 1)[1]


def test_hard_kill_mid_node_then_resume_in_a_fresh_process(tmp_path):
    db, log = tmp_path / "events.db", tmp_path / "invocations.jsonl"

    # Phase 1: a real process is hard-killed while node 'b' is executing.
    crashed = _run_child("crash", db, log)
    assert crashed.returncode == KILL_EXIT_CODE, (crashed.returncode, crashed.stderr[-2000:])
    assert "UNREACHABLE" not in crashed.stdout
    rows = _read(log)
    assert [(r["node"], r["event"]) for r in rows] == [("a", "start"), ("a", "done"), ("b", "start")]
    killed_pid = rows[0]["pid"]
    assert {r["pid"] for r in rows} == {killed_pid}
    instance_id = _instance_id_from_checkpoint(db)  # the checkpoint written at a's boundary survived the kill

    # Phase 2: a different process resumes using only what is on disk.
    resumed = _run_child("resume", db, log, instance_id)
    assert resumed.returncode == 0, resumed.stderr[-2000:]
    result = json.loads(next(l for l in resumed.stdout.splitlines() if l.startswith('{"success"')))
    assert result["success"] is True, result
    assert result["outputs"] == {"a": "done:a", "b": "done:b", "c": "done:c"}

    rows = _read(log)
    pids = {r["pid"] for r in rows}
    assert len(pids) == 2, f"expected two distinct processes, got {pids}"
    resumed_pid = (pids - {killed_pid}).pop()
    starts = Counter(r["node"] for r in rows if r["event"] == "start")
    dones = Counter(r["node"] for r in rows if r["event"] == "done")
    assert starts == {"a": 1, "b": 2, "c": 1}   # b is the only node that ran twice
    assert dones == {"a": 1, "b": 1, "c": 1}    # ...and every node completed exactly once
    assert {r["pid"] for r in rows if r["node"] == "a"} == {killed_pid}  # 'a' never re-ran after the restart
    assert [r["pid"] for r in rows if r["node"] == "b" and r["event"] == "start"] == [killed_pid, resumed_pid]
    assert {r["pid"] for r in rows if r["node"] == "b" and r["event"] == "done"} == {resumed_pid}
    assert {r["pid"] for r in rows if r["node"] == "c"} == {resumed_pid}
