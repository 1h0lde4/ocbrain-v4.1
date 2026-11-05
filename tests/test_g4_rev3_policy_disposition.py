"""
Rev 3 amendment tests — Amendment 10: WAL checkpoint POLICY disposition.

Guarantees tested (all static-audit or inventory based, no behavior change
authorized by the remediation):
  * the documented explicit checkpoint inventory is real: the two listed
    sites exist in the source and are the ONLY explicit checkpoint sites in
    production code,
  * automatic checkpointing keeps SQLite's default (wal_autocheckpoint=1000
    pages per connection) and production code NEVER assigns it
    (no global policy change),
  * the maintenance runner's post-commit TRUNCATE checkpoint is recorded
    honestly (busy-value surfaced, never forced).
"""
import os
import re
import sqlite3

from core.memory.backends.sqlite_storage import SQLiteStorageBackend
from core.memory.sqlite_migration import (
    EXPLICIT_CHECKPOINT_SITES,
    collect_checkpoint_inventory,
    run_maintenance_migration,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_DIRS = ["core", "interface"]


def _iter_prod_py_sources():
    for prod_dir in PROD_DIRS:
        base = os.path.join(REPO_ROOT, prod_dir)
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in filenames:
                if filename.endswith(".py"):
                    full = os.path.join(dirpath, filename)
                    rel = os.path.relpath(full, REPO_ROOT)
                    with open(full, encoding="utf-8", errors="replace") as fh:
                        yield rel, fh.read()


def _legacy_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
CREATE TABLE knowledge_entries (
    entry_id TEXT PRIMARY KEY, layer TEXT NOT NULL, content TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '', importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 1.0, truth_status TEXT NOT NULL DEFAULT 'unknown',
    trust_score REAL NOT NULL DEFAULT 1.0, source TEXT NOT NULL DEFAULT '',
    worker_id TEXT NOT NULL DEFAULT '', workflow_id TEXT NOT NULL DEFAULT '',
    derived_from TEXT NOT NULL DEFAULT '[]', supports TEXT NOT NULL DEFAULT '[]',
    contradicts TEXT NOT NULL DEFAULT '[]', supersedes TEXT NOT NULL DEFAULT '[]',
    graph_node_id TEXT, tags TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}', procedure_name TEXT,
    created_at REAL NOT NULL, updated_at REAL NOT NULL,
    accessed_at REAL NOT NULL, access_count INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE knowledge_entries_fts USING fts5(
    content, summary, tags, content='knowledge_entries', content_rowid='rowid'
);
CREATE TRIGGER ke_ai AFTER INSERT ON knowledge_entries BEGIN
    INSERT INTO knowledge_entries_fts(rowid, content, summary, tags)
    VALUES (new.rowid, new.content, new.summary, new.tags);
END;
CREATE TRIGGER ke_au AFTER UPDATE ON knowledge_entries BEGIN
    UPDATE knowledge_entries_fts
    SET content=new.content, summary=new.summary, tags=new.tags
    WHERE rowid=old.rowid;
END;
CREATE TRIGGER ke_ad AFTER DELETE ON knowledge_entries BEGIN
    DELETE FROM knowledge_entries_fts WHERE rowid=old.rowid;
END;
""")
        conn.execute(
            "INSERT INTO knowledge_entries (entry_id, layer, content,"
            " created_at, updated_at, accessed_at)"
            " VALUES ('c1', 'l1', 'xqzCHECKPOLICY body', 1.0, 1.0, 1.0)")
        conn.commit()
    finally:
        conn.close()


class TestExplicitCheckpointSitesMatchSource:
    """The static inventory table is checked against the actual source."""

    def test_inventory_has_exactly_two_explicit_sites(self):
        assert len(EXPLICIT_CHECKPOINT_SITES) == 2
        locations = {site["location"] for site in EXPLICIT_CHECKPOINT_SITES}
        # Locations are stored as repo-relative POSIX paths by convention:
        assert locations == {
            "core/runtime/state.py",
            "core/memory/sqlite_migration.py",
        }
        for site in EXPLICIT_CHECKPOINT_SITES:
            for key in ("location", "database", "operation", "purpose",
                        "owns_memory_db"):
                assert key in site, (key, site)
                assert isinstance(site[key], (str, bool)) and (
                    site[key] or site[key] is False)
            assert "TRUNCATE" in site["operation"]

    def test_the_listed_sites_really_exist_in_source(self):
        # Count only EXECUTING occurrences (a `.execute("PRAGMA
        # wal_checkpoint...")` call), not documentation labels:
        execution_re = re.compile(r'execute\(\s*"PRAGMA wal_checkpoint')
        exec_hits = {}
        for rel, text in _iter_prod_py_sources():
            posix_rel = rel.replace(os.sep, "/")
            hits = len(execution_re.findall(text))
            if hits:
                exec_hits[posix_rel] = hits
        # Exactly the two documented files run checkpoint pragmas:
        # core/runtime/state.py carries both repair-path sites (documented
        # as one inventory "location"); the maintenance runner carries the
        # one post-commit TRUNCATE site:
        assert exec_hits == {
            "core/runtime/state.py": 2,
            "core/memory/sqlite_migration.py": 1,
        }, exec_hits
        # ...and the runner's one executing site is the documented TRUNCATE:
        migration_py = os.path.join(REPO_ROOT, "core", "memory",
                                    "sqlite_migration.py")
        with open(migration_py, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        assert re.search(
            r'execute\(\s*"PRAGMA wal_checkpoint\(TRUNCATE\)"', body)

    def test_no_memory_backend_runs_explicit_checkpoints(self):
        for rel, text in _iter_prod_py_sources():
            if rel.startswith(os.path.normpath("core/memory/backends")):
                assert "wal_checkpoint" not in text, rel


class TestNoGlobalCheckpointPolicyChange:
    """Autocheckpoint stays on SQLite's default and is NEVER assigned."""

    def test_wal_autocheckpoint_never_written(self):
        for rel, text in _iter_prod_py_sources():
            posix_rel = rel.replace(os.sep, "/")
            # A PRAGMA-statement assignment would be a prohibited global
            # policy change; inventory labels like "wal_autocheckpoint=1000
            # pages" are documentation mentions, not settings:
            assert not re.search(
                r'PRAGMA wal_autocheckpoint\s*=[^=]', text), posix_rel
            # and no backend writes it either (no keyword-style override):
            if posix_rel.startswith("core/memory/backends"):
                assert "wal_autocheckpoint" not in text, posix_rel

    def test_default_value_survives_on_real_backend_connections(self,
                                                                tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate="acknowledge")
        conn = backend._connect()
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            pages = conn.execute(
                "PRAGMA wal_autocheckpoint").fetchone()[0]
        finally:
            conn.close()
        assert mode == "wal"
        assert pages == 1000   # SQLite default: nothing overridden


class TestCheckpointInventoryAndHonestReporting:
    def test_inventory_keys_and_connection_facts(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _legacy_db(db_path)
        # Touch WAL mode so the connection facts include a live setting:
        warm = sqlite3.connect(db_path)
        warm.execute("PRAGMA journal_mode=WAL")
        warm.commit()
        warm.close()

        inv = collect_checkpoint_inventory(db_path)
        for key in ("explicit_checkpoint_sites", "automatic_checkpointing",
                    "checkpoint_scheduling_owner",
                    "multiple_processes_can_initiate",
                    "readers_preventing_completion", "wal_monitoring",
                    "db_bytes", "wal_bytes", "shm_bytes",
                    "connection_facts"):
            assert key in inv, key
        assert isinstance(inv["db_bytes"], int)
        # The automatic-checkpoint text keeps the default, unmodified:
        assert "wal_autocheckpoint=1000" in inv["automatic_checkpointing"]
        assert "no global change is authorized" in \
            inv["automatic_checkpointing"].lower()
        facts = inv["connection_facts"]
        assert facts["wal_autocheckpoint"] == 1000
        assert facts["journal_mode"] == "wal"

    def test_maintenance_checkpoint_is_recorded_honestly(self, tmp_path):
        db_path = str(tmp_path / "u.db")
        _legacy_db(db_path)
        report = run_maintenance_migration(db_path)
        assert report.outcome == "migrated"
        ck = report.checkpoint
        assert ck["operation"] == "PRAGMA wal_checkpoint(TRUNCATE)"
        assert isinstance(ck["busy"], int)
        assert "never forced" in ck["note"].lower()
        # The step trace carries it as the final maintenance action:
        steps = {s["step"] for s in report.steps}
        assert "final_checkpoint" in steps
