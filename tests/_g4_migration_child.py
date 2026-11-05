"""Child process for tests/test_g4_rev3_migration_lifecycle.py (not a test module: no ``test_`` prefix).

argv: <repo_root> <db_path> <jsonl_log_path>

Runs ONE maintenance migration against ONE database and appends the result
(outcome, ledger row count, step list) as a JSON line to the log file, then
exits 0 (or 1 on unexpected crash). Used to prove that concurrent invocations
of the dedicated maintenance command serialize correctly: the second runner
must acquire the lock only after the first has committed, re-read the
migration state (Amendment 2 §E) and report `already_applied` instead of
running a second migration (and NOT run bleaching/building twice).
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, sys.argv[1])
DB, LOG = sys.argv[2], sys.argv[3]

try:
    from core.memory.sqlite_migration import read_migration_ledger
    from core.memory.sqlite_migration import run_maintenance_migration

    report = run_maintenance_migration(DB)
    ledger = []
    conn = sqlite3.connect(DB)
    try:
        ledger = read_migration_ledger(conn)
    finally:
        conn.close()
    result = {
        "db": DB,
        "outcome": report.outcome,
        "failure": report.failure,
        "steps": [s["step"] for s in report.steps],
        "ledger_rows": len(ledger),
        "re_read_after_lock": any(
            s["step"] == "re_read_migration_state" for s in report.steps),
        "pid": os.getpid(),
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")
        f.flush()
        os.fsync(f.fileno())
    sys.exit(0)
except Exception as exc:  # crash: parent inspects the log
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"db": DB, "crash": repr(exc),
                            "pid": os.getpid()}) + "\n")
    sys.exit(1)
