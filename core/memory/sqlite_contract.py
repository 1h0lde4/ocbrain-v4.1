"""
core/memory/sqlite_contract.py — The canonical SQLite memory-DB contract (Rev 3)

Rev 3 (OCBrain G4-FTS remediation) makes every storage-backend constructor a
*validation-only* consumer of this contract. Mutation of an existing schema is
reserved for the dedicated maintenance migration
(`core/memory/sqlite_migration.py`, exposed as the `ocbrain memory-migrate`
CLI command — following the repository's existing click-command architecture
in `interface/cli.py`).

This module owns:

  * the canonical DDL (content table, FTS5 external-content virtual table,
    the three synchronization triggers, supporting indexes) — a single
    source of truth used by initialization, auditing and the migration
    runner so text cannot drift between sites (Amendment 8);
  * the known historical definitions (pre-Session 4C unsafe `ke_au`), so a
    legacy database is *recognized* rather than guessed at (Amendment 8:
    "Use the canonical migration definition and known historical definitions
    to identify supported states");
  * the per-database migration bookkeeping tables (ledger + meta) and their
    DDL — part of the database's own schema so each database file carries
    its own independent migration state (Amendment 7);
  * SQL normalization and CREATE VIRTUAL TABLE parsing used for semantic
    comparison — substring checks are NOT accepted as proof of equivalence
    (Amendment 8);
  * the `MemoryReadinessError` fail-closed refusal type (Amendment 2B.3–5).

The FTS content-row identity is intentionally `content_rowid='rowid'`
(Amendment 4). The identity is only safe because the canonical content table
has no declared rowid/oid/_rowid_ column and is not WITHOUT ROWID;
`sqlite_integrity.verify_content_row_identity()` enforces that against the
live database, and hidden-rowid persistence remains an OPEN architectural
risk (stable-integer-identity decision pending — explicitly disclosed).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ── Canonical DDL (single source of truth) ───────────────────────────────────

CANONICAL_KNOWLEDGE_ENTRIES_DDL = """
CREATE TABLE knowledge_entries (
    entry_id       TEXT PRIMARY KEY,
    layer          TEXT NOT NULL,
    content        TEXT NOT NULL,
    summary        TEXT NOT NULL DEFAULT '',
    importance     REAL NOT NULL DEFAULT 0.5,
    confidence     REAL NOT NULL DEFAULT 1.0,
    truth_status   TEXT NOT NULL DEFAULT 'unknown',
    trust_score    REAL NOT NULL DEFAULT 1.0,
    source         TEXT NOT NULL DEFAULT '',
    worker_id      TEXT NOT NULL DEFAULT '',
    workflow_id    TEXT NOT NULL DEFAULT '',
    derived_from   TEXT NOT NULL DEFAULT '[]',
    supports       TEXT NOT NULL DEFAULT '[]',
    contradicts    TEXT NOT NULL DEFAULT '[]',
    supersedes     TEXT NOT NULL DEFAULT '[]',
    graph_node_id  TEXT,
    tags           TEXT NOT NULL DEFAULT '[]',
    metadata       TEXT NOT NULL DEFAULT '{}',
    procedure_name TEXT,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    accessed_at    REAL NOT NULL,
    access_count   INTEGER NOT NULL DEFAULT 0
)"""

CANONICAL_FTS_DDL = """
CREATE VIRTUAL TABLE knowledge_entries_fts USING fts5(
    content,
    summary,
    tags,
    content='knowledge_entries',
    content_rowid='rowid'
)"""

CANONICAL_TRIGGER_DDL = {
    "ke_ai": """
CREATE TRIGGER ke_ai AFTER INSERT ON knowledge_entries BEGIN
    INSERT INTO knowledge_entries_fts(rowid, content, summary, tags)
    VALUES (new.rowid, new.content, new.summary, new.tags);
END""",
    "ke_au": """
CREATE TRIGGER ke_au AFTER UPDATE ON knowledge_entries BEGIN
    INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rowid, content, summary, tags)
    VALUES ('delete', old.rowid, old.content, old.summary, old.tags);
    INSERT INTO knowledge_entries_fts(rowid, content, summary, tags)
    VALUES (new.rowid, new.content, new.summary, new.tags);
END""",
    "ke_ad": """
CREATE TRIGGER ke_ad AFTER DELETE ON knowledge_entries BEGIN
    DELETE FROM knowledge_entries_fts WHERE rowid=old.rowid;
END""",
}

CANONICAL_INDEX_DDL = {
    "idx_ke_layer": "CREATE INDEX idx_ke_layer ON knowledge_entries(layer)",
    "idx_ke_importance": "CREATE INDEX idx_ke_importance ON knowledge_entries(importance DESC)",
    "idx_ke_truth": "CREATE INDEX idx_ke_truth ON knowledge_entries(truth_status)",
    "idx_ke_created": "CREATE INDEX idx_ke_created ON knowledge_entries(created_at DESC)",
    "idx_ke_source": "CREATE INDEX idx_ke_source ON knowledge_entries(source)",
    "idx_ke_procedure": (
        "CREATE INDEX idx_ke_procedure ON knowledge_entries(procedure_name) "
        "WHERE procedure_name IS NOT NULL"
    ),
}

# Housekeeping tables: each database file carries its own migration state so
# a process-global flag can never stand in for per-database truth (Am. 7).
HOUSEKEEPING_DDL = """
CREATE TABLE IF NOT EXISTS _ocbrain_memory_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS _ocbrain_memory_migrations (
    migration_id     TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    status           TEXT NOT NULL,
    started_at       REAL NOT NULL,
    completed_at     REAL NOT NULL,
    applied_by       TEXT NOT NULL,
    host_os          TEXT NOT NULL,
    pre_checks_json  TEXT NOT NULL DEFAULT '{}',
    post_checks_json TEXT NOT NULL DEFAULT '{}',
    wal_bytes_before INTEGER,
    wal_bytes_after  INTEGER
)"""

CANONICAL_SCHEMA_STATEMENTS: tuple = (
    CANONICAL_KNOWLEDGE_ENTRIES_DDL,
    CANONICAL_FTS_DDL,
    CANONICAL_TRIGGER_DDL["ke_ai"],
    CANONICAL_TRIGGER_DDL["ke_au"],
    CANONICAL_TRIGGER_DDL["ke_ad"],
    *CANONICAL_INDEX_DDL.values(),
    "CREATE TABLE IF NOT EXISTS _ocbrain_memory_meta ("
    "key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS _ocbrain_memory_migrations ("
    "migration_id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, "
    "started_at REAL NOT NULL, completed_at REAL NOT NULL, "
    "applied_by TEXT NOT NULL, host_os TEXT NOT NULL, "
    "pre_checks_json TEXT NOT NULL DEFAULT '{}', "
    "post_checks_json TEXT NOT NULL DEFAULT '{}', "
    "wal_bytes_before INTEGER, wal_bytes_after INTEGER)",
)

# Documentation/schema-text form (NOT used for execution — see
# CANONICAL_SCHEMA_STATEMENTS; trigger bodies contain semicolons).
CANONICAL_SCHEMA_SCRIPT = ";\n".join(CANONICAL_SCHEMA_STATEMENTS) + ";"

CONTENT_TABLE = "knowledge_entries"
FTS_TABLE = "knowledge_entries_fts"
META_TABLE = "_ocbrain_memory_meta"
MIGRATIONS_TABLE = "_ocbrain_memory_migrations"
CONTENT_COLUMNS: Tuple[str, ...] = ("content", "summary", "tags")

def split_sql_statements(script: str) -> List[str]:
    """
    DEPRECATED text splitter — kept only for reference; the canonical schema
    is executed statement-by-statement via CANONICAL_SCHEMA_STATEMENTS
    instead (trigger bodies contain semicolons; safe textual splitting is
    not possible without an SQL lexer).
    """
    statements: List[str] = []
    buf: List[str] = []
    depth = 0
    in_quote = False
    for ch in script:
        if ch == "'":
            in_quote = not in_quote
        if not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
        if ch == ";" and depth == 0 and not in_quote:
            text = "".join(buf).strip()
            if text:
                statements.append(text)
            buf = []
            continue
        buf.append(ch)
    text = "".join(buf).strip()
    if text:
        statements.append(text)
    return statements


# ── Known historical definitions (Amendment 8: recognized legacy state) ──────

# Pre-Session 4C `ke_au`: a raw UPDATE against the FTS5 shadow table — unsafe
# for external-content tables (see docs/reports/SESSION4C_REPORT.md).
KNOWN_LEGACY_TRIGGER_KE_AU = """
CREATE TRIGGER ke_au AFTER UPDATE ON knowledge_entries BEGIN
    UPDATE knowledge_entries_fts
    SET content=new.content, summary=new.summary, tags=new.tags
    WHERE rowid=old.rowid;
END"""

KNOWN_LEGACY_DEFINITIONS = {
    "ke_au_raw_update": KNOWN_LEGACY_TRIGGER_KE_AU,
}

# ── Migration identity ──────────────────────────────────────────────────────

MIGRATION_ID_V1 = "mlc_v1_fts_external_content_trigger_contract"
MIGRATION_NAME_V1 = ("verify external-content FTS trigger contract; rebuild "
                     "and verify FTS; whole-database integrity checks")

META_SCHEMA_STATE = "memory_schema_state"
SCHEMA_STATE_FRESH_CURRENT = "initialized_fresh_current"
SCHEMA_STATE_MIGRATED = "migrated_to_current"
SCHEMA_STATES_CURRENT = (SCHEMA_STATE_FRESH_CURRENT, SCHEMA_STATE_MIGRATED)

# FTS5 option values that would be recorded in the shadow config table by
# runtime commands (e.g. secure-delete). Recognized so an audit can report
# rather than fail on legitimate runtime state (Amendment 6/8).
FTS_CONFIG_RECOGNIZED_KEYS = {"version", "secure-delete"}


class MemoryReadinessError(RuntimeError):
    """
    Fail-closed refusal of memory readiness (Amendment 2B.3–5).

    Raised by storage-backend construction when the database's own migration
    state or schema contract does not currently qualify for ordinary memory
    service. The constructor never mutates the database in response; the
    operator runs the dedicated maintenance command instead.
    """

    def __init__(self, finding: Dict[str, Any], remediation: str):
        self.finding = finding
        self.remediation = remediation
        reason = finding.get("reason", "unspecified")
        super().__init__(f"Memory readiness refused: {reason}")
        self.remediation_plan = remediation


# ── Normalization & parsing (NOT substring checks — Amendment 8) ─────────────

_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def normalize_sql(sql: str) -> str:
    """
    Semantic comparison basis: strip comments, collapse whitespace, drop a
    trailing semicolon, casefold. SQLite identifiers/keywords are ASCII
    case-insensitive so casefolding is a deterministic equivalence here.
    """
    if sql is None:
        return ""
    text = _COMMENT_RE.sub(" ", sql)
    text = " ".join(text.split())
    text = text.rstrip(";").strip()
    return text.casefold()


def parse_create_virtual_table(sql: str) -> Tuple[List[str], Dict[str, str]]:
    """
    Parse `CREATE VIRTUAL TABLE name USING fts5(a, b, c, option='value')`
    into (declared columns, options) with top-level comma splitting.
    """
    inner = sql.strip()
    m = re.search(r"\bUSING\s+fts5\s*\(", inner, re.IGNORECASE)
    if not m:
        raise ValueError(f"not an FTS5 virtual table definition: {sql!r}")
    body = inner[m.end():]
    # find the matching close paren
    depth = 1
    end = len(body)
    for i, ch in enumerate(body):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    body = body[:end]

    parts: List[str] = []
    depth = 0
    buf = []
    in_quote = False
    for ch in body:
        if ch == "'":
            in_quote = not in_quote
        if not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
        if ch == "," and depth == 0 and not in_quote:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())

    columns: List[str] = []
    options: Dict[str, str] = {}
    for part in parts:
        if part == "":
            continue
        opt = re.match(r"^(\w+)\s*=\s*'([^']*)'$", part)
        if opt:
            options[opt.group(1).casefold()] = opt.group(2)
            continue
        col = re.match(r"^(\"?\w+\"?)$", part)
        if col:
            columns.append(col.group(1).casefold())
            continue
        # Anything neither an option nor a plain column cannot be proven
        # semantically equivalent to the canonical definition — signal for
        # fail-closed classification (Amendment 8).
        raise ValueError(f"unrecognized FTS5 definition token: {part!r}")
    return columns, options


def canonical_columns() -> List[str]:
    cols, _ = parse_create_virtual_table(CANONICAL_FTS_DDL)
    return cols


def canonical_fts_options() -> Dict[str, str]:
    _, opts = parse_create_virtual_table(CANONICAL_FTS_DDL)
    return opts


def trigger_audit_classification(trigger_sql: Optional[str], name: str) -> str:
    """
    Classify a stored trigger definition against the contract.

    Returns one of:
      "canonical"            — semantically equal to the canonical definition.
      "known_legacy_unsafe"  — exactly a recognized historical (unsafe) body.
      "unknown"              — anything else: fail closed (Amendment 8).
    """
    if trigger_sql is None:
        return "missing"
    norm = normalize_sql(trigger_sql)
    if name in CANONICAL_TRIGGER_DDL and norm == normalize_sql(CANONICAL_TRIGGER_DDL[name]):
        return "canonical"
    if name == "ke_au" and norm == normalize_sql(KNOWN_LEGACY_TRIGGER_KE_AU):
        return "known_legacy_unsafe"
    if name == "ke_au" and norm == normalize_sql(_LEGACY_KE_AU_INLINE):
        return "known_legacy_unsafe"
    return "unknown"


# The historical ke_au body as written inline in the original repository
# schema (single-line formatted). Recognized so the migration can name it.
_LEGACY_KE_AU_INLINE = (
    "CREATE TRIGGER ke_au AFTER UPDATE ON knowledge_entries BEGIN\n"
    "    UPDATE knowledge_entries_fts SET content=new.content, "
    "summary=new.summary, tags=new.tags WHERE rowid=old.rowid;\n"
    "END"
)
