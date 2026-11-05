"""
core/memory/sqlite_integrity.py — Independent integrity validation (Rev 3)

Implements Rev 3 Amendment 3 (whole-database integrity validation) and the
verification parts of Amendments 4 and 8.

Four independent verification layers, each with its own scope, status and
verification time (Amendment 3 §C — the FTS `rank=1` integrity-check does NOT
stand in for whole-database integrity):

  1. SQLite structural integrity          — PRAGMA integrity_check
  2. Foreign-key consistency              — PRAGMA foreign_key_check
     (run whenever the database has foreign-key relationships, including
     relationships introduced through migrations)
  3. FTS5 internal/external-content integrity — the documented
     `INSERT INTO fts(fts, rank) VALUES ('integrity-check', 1)` command
  4. Actual retrieval health               — real FTS5 MATCH queries against
     controlled test tokens

Cost accounting: every finding carries its measured duration; callers must
not run full validation on ordinary health heartbeats (Amendment 3 §C) —
`validate_readiness()` is the cheap, schema-only startup path.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from core.memory.sqlite_contract import (
    CANONICAL_FTS_DDL,
    CANONICAL_INDEX_DDL,
    CANONICAL_KNOWLEDGE_ENTRIES_DDL,
    CANONICAL_TRIGGER_DDL,
    CONTENT_TABLE,
    FTS_CONFIG_RECOGNIZED_KEYS,
    FTS_TABLE,
    MIGRATION_ID_V1,
    META_SCHEMA_STATE,
    META_TABLE,
    MIGRATIONS_TABLE,
    SCHEMA_STATES_CURRENT,
    normalize_sql,
    canonical_columns,
    canonical_fts_options,
    parse_create_virtual_table,
    trigger_audit_classification,
)

logger = logging.getLogger("ocbrain.memory.sqlite_integrity")

# Controlled retrieval tokens mandated by Amendment 9 §1: simple alphabetic
# tokens that need no special FTS5 query syntax.
RETRIEVAL_PROBE_TOKEN_PREFIX = "xqzIntegrityProbe"

SCOPE_STRUCTURAL = "sqlite_structural_integrity"
SCOPE_FOREIGN_KEYS = "foreign_key_consistency"
SCOPE_FTS_INTERNAL = "fts_internal_external_content_integrity"
SCOPE_RETRIEVAL = "fts_retrieval_health"
SCOPE_SCHEMA_CONTRACT = "schema_contract_validation"
SCOPE_CONTENT_IDENTITY = "fts_content_row_identity"

PASS = "pass"
FAIL = "fail"
ERROR = "error"
NOT_APPLICABLE = "not_applicable"
FAILED_STATUSES = (FAIL, ERROR)


@dataclass
class IntegrityFinding:
    """One verification result: scope + status + verification time (+ cost)."""
    scope: str
    name: str
    status: str          # "pass" | "fail" | "not_applicable" | "error"
    detail: str
    verified_at: float = field(default_factory=time.time)
    duration_s: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scope": self.scope,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "verified_at": self.verified_at,
            "duration_s": round(self.duration_s, 6),
        }


def _sql_error_finding(scope: str, name: str, exc: Exception,
                       start: float = 0.0) -> IntegrityFinding:
    finding = IntegrityFinding(
        scope=scope, name=name, status=ERROR,
        detail=f"{type(exc).__name__}: {exc}",
        duration_s=time.time() - start,
    )
    return finding


# ── Amendment 3 §A — whole-database checks ──────────────────────────────────

def check_structural_integrity(conn: sqlite3.Connection) -> IntegrityFinding:
    """
    `PRAGMA integrity_check`. A corrupted database can either return error
    rows or raise mid-pragma (Session 4C observed the raised form against
    real corruption) — both are failures.
    """
    start = time.time()
    try:
        rows = [r[0] for r in conn.execute("PRAGMA integrity_check").fetchall()]
    except sqlite3.DatabaseError as exc:
        return _sql_error_finding(SCOPE_STRUCTURAL, "PRAGMA integrity_check",
                                  exc, start)
    dur = time.time() - start
    if rows == ["ok"]:
        return IntegrityFinding(SCOPE_STRUCTURAL, "PRAGMA integrity_check",
                                PASS, "database image reports ok", duration_s=dur)
    return IntegrityFinding(
        SCOPE_STRUCTURAL, "PRAGMA integrity_check", FAIL,
        f"{len(rows)} integrity problem row(s); first: {rows[:3]!r}",
        duration_s=dur,
    )


def _user_tables(conn: sqlite3.Connection) -> List[str]:
    names: List[str] = []
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        names.append(name)
    return names


def _has_foreign_key_relationships(conn: sqlite3.Connection) -> bool:
    """
    Detect FOREIGN KEY relationships on real user tables. Shadow and
    housekeeping tables are excluded from *detection* (they hold none today);
    `PRAGMA foreign_key_check` itself scans every table in the database.
    """
    for name in _user_tables(conn):
        if name.startswith(FTS_TABLE) or name.startswith("_ocbrain_"):
            continue
        try:
            fks = conn.execute(f'PRAGMA foreign_key_list("{name}")').fetchall()
        except sqlite3.Error:
            continue
        if fks:
            return True
    return False


def classify_foreign_key_violations(rows: Sequence[Any]) -> Dict[str, str]:
    """
    Amendment 3 §B.3: classify existing violations explicitly instead of
    ignoring them. `PRAGMA foreign_key_check` rows are
    (child_table, rowid, parent_table, fk_index); classification keys on the
    (child -> parent) pair so operators see WHERE the inconsistency is.
    """
    classified: Dict[str, str] = {}
    for row in rows:
        table = str(row[0]); rowid = row[1]; parent = str(row[2])
        try:
            fk_index = int(row[3])
        except (TypeError, ValueError, IndexError):
            fk_index = -1
        key = f"{table}(rowid={rowid}) -> {parent}(fk #{fk_index})"
        if parent.startswith(FTS_TABLE):
            relation = "fts_shadow_parent_fk_violation"
        elif table.startswith(FTS_TABLE):
            relation = "fts_shadow_child_fk_violation"
        else:
            relation = "content_fk_violation"
        classified[key] = relation
    return classified


def check_foreign_key_integrity(conn: sqlite3.Connection) -> IntegrityFinding:
    """
    Amendment 3 §A/§B: run `PRAGMA foreign_key_check` whenever the database
    has foreign-key relationships — including relationships introduced
    through migrations. With none defined, the result is `not_applicable`,
    recorded explicitly so absence is never mistaken for a pass.
    """
    start = time.time()
    if not _has_foreign_key_relationships(conn):
        return IntegrityFinding(
            SCOPE_FOREIGN_KEYS, "PRAGMA foreign_key_check", NOT_APPLICABLE,
            "no foreign-key relationships defined in this database",
            duration_s=time.time() - start,
        )
    try:
        rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.DatabaseError as exc:
        return _sql_error_finding(SCOPE_FOREIGN_KEYS, "PRAGMA foreign_key_check",
                                  exc, start)
    dur = time.time() - start
    if not rows:
        return IntegrityFinding(SCOPE_FOREIGN_KEYS, "PRAGMA foreign_key_check",
                                PASS, "no foreign-key violations", duration_s=dur)
    classified = classify_foreign_key_violations(rows)
    counts: Dict[str, int] = {}
    for relation in classified.values():
        counts[relation] = counts.get(relation, 0) + 1
    detail = (
        f"{len(rows)} foreign-key violation row(s); " +
        "; ".join(f"{rel}={n}" for rel, n in sorted(counts.items()))
    )
    return IntegrityFinding(SCOPE_FOREIGN_KEYS, "PRAGMA foreign_key_check",
                            FAIL, detail, duration_s=dur)


def check_fts_integrity(conn: sqlite3.Connection) -> IntegrityFinding:
    """
    Amendment 3 §A: the FTS5 external-content integrity command. Detects the
    exact drift the legacy ke_au trigger used to produce (index vs content
    table). This is the FTS-layer check ONLY — Amendment 3 §C forbids
    presenting it as whole-database integrity.
    """
    start = time.time()
    try:
        conn.execute(
            f"INSERT INTO {FTS_TABLE}({FTS_TABLE}, rank) VALUES ('integrity-check', 1)"
        )
    except sqlite3.Error as exc:
        return _sql_error_finding(SCOPE_FTS_INTERNAL,
                                  "fts5 integrity-check(rank=1)", exc, start)
    return IntegrityFinding(
        SCOPE_FTS_INTERNAL, "fts5 integrity-check(rank=1)", PASS,
        "external-content index is internally consistent with the content table",
        duration_s=time.time() - start,
    )


def check_fts_retrieval(
    conn: sqlite3.Connection,
    tokens: Sequence[tuple] = (),
) -> IntegrityFinding:
    """
    Amendment 3 §A / Amendment 9: execute real FTS5 MATCH queries. `tokens`
    is a list of (token, must_match) pairs; with no pairs a trivial probe
    verifies the MATCH machinery runs.
    """
    start = time.time()
    details: List[str] = []
    ok = True
    try:
        if not tokens:
            probe = f"{RETRIEVAL_PROBE_TOKEN_PREFIX}{time.time_ns()}"
            conn.execute(
                f"SELECT rowid FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH ?",
                (probe,),
            ).fetchall()
        for token, must_match in tokens:
            rows = conn.execute(
                f"SELECT rowid FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH ?",
                (token,),
            ).fetchall()
            if must_match and not rows:
                ok = False
                details.append(f"missing expected token {token!r}")
            if not must_match and rows:
                ok = False
                details.append(
                    f"unexpected token {token!r} still matches (rowids: "
                    f"{[r[0] for r in rows][:5]})")
    except sqlite3.Error as exc:
        return _sql_error_finding(SCOPE_RETRIEVAL, "MATCH probes", exc, start)
    dur = time.time() - start
    detail = "; ".join(details) if details else "MATCH executed"
    return IntegrityFinding(SCOPE_RETRIEVAL, "MATCH probes",
                            PASS if ok else FAIL, detail, duration_s=dur)


def run_full_integrity_validation(
    conn: sqlite3.Connection,
    retrieval_tokens: Sequence[tuple] = (),
) -> Dict[str, Any]:
    """
    All four Amendment 3 checks as independent findings, plus total cost.

    Returns: {"findings": [IntegrityFinding...], "passed": bool,
              "total_cost_s": float, "verified_at": float}
    """
    findings = [
        check_structural_integrity(conn),
        check_foreign_key_integrity(conn),
        check_fts_integrity(conn),
        check_fts_retrieval(conn, tokens=retrieval_tokens),
    ]
    return {
        "findings": [f.as_dict() for f in findings],
        "finding_objects": findings,
        "passed": all(f.status in (PASS, NOT_APPLICABLE) for f in findings),
        "total_cost_s": round(sum(f.duration_s for f in findings), 6),
        "verified_at": time.time(),
    }


# ── Amendment 4 — FTS content-row identity invariants ───────────────────────

_ROWID_ALIAS_COLUMNS = {"rowid", "oid", "_rowid_"}


def verify_content_row_identity(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Amendment 4 §A: prove against the LIVE database that the FTS
    `content_rowid='rowid'` configuration is valid for the actual content
    table:

      * the table is not WITHOUT ROWID (sqlite_schema + live behavior);
      * no declared column shadows/aliases the hidden rowid
        (rowid/oid/_rowid_);
      * the `rowid` identifier resolves on this table;
      * the identity is unique for every content row.

    The OPEN architectural classification of hidden-rowid persistence
    (Amendment 4 §B) is carried in the result: SQLite's documentation notes
    VACUUM may change rowids of tables without an INTEGER PRIMARY KEY. The
    application-level TEXT primary key is not the FTS identity and is never
    inferred to be one.
    """
    checks: List[IntegrityFinding] = []
    audit: Dict[str, Any] = {
        "content_rowid": "rowid",
        "checks": checks,
        "passed": True,
    }

    try:
        schema_row = conn.execute(
            "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?",
            (CONTENT_TABLE,),
        ).fetchone()
    except sqlite3.Error as exc:
        audit["passed"] = False
        audit["error"] = str(exc)
        return audit

    if schema_row is None or not schema_row[0]:
        audit["passed"] = False
        audit["reason"] = f"{CONTENT_TABLE} table is missing"
        return audit
    norm_schema = normalize_sql(schema_row[0])

    start = time.time()
    if "without rowid" in norm_schema:
        audit["passed"] = False
        checks.append(IntegrityFinding(
            SCOPE_CONTENT_IDENTITY, "without_rowid", FAIL,
            "content table is declared WITHOUT ROWID — the hidden rowid "
            "identity is invalid for FTS external content",
            duration_s=time.time() - start))
        return audit

    declared = [str(r[1]) for r in conn.execute(
        f"PRAGMA table_info({CONTENT_TABLE})")]
    shadowing = [c for c in declared if c.casefold() in _ROWID_ALIAS_COLUMNS]
    if shadowing:
        audit["passed"] = False
        checks.append(IntegrityFinding(
            SCOPE_CONTENT_IDENTITY, "rowid_alias_columns", FAIL,
            f"declared column(s) shadow the hidden rowid: {shadowing} — "
            "ambiguity invalidates the FTS content-row identity",
            duration_s=time.time() - start))
        return audit
    checks.append(IntegrityFinding(
        SCOPE_CONTENT_IDENTITY, "rowid_alias_columns", PASS,
        "no declared rowid/oid/_rowid_ columns observed",
        duration_s=time.time() - start))

    start = time.time()
    try:
        row = conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT rowid) FROM {CONTENT_TABLE}"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        audit["passed"] = False
        checks.append(IntegrityFinding(
            SCOPE_CONTENT_IDENTITY, "rowid_resolution_uniqueness", FAIL,
            f"hidden rowid does not resolve on the live table: {exc}",
            duration_s=time.time() - start))
        return audit
    total, distinct = int(row[0]), int(row[1])
    if total != distinct:
        audit["passed"] = False
        checks.append(IntegrityFinding(
            SCOPE_CONTENT_IDENTITY, "rowid_resolution_uniqueness", FAIL,
            f"duplicate FTS document identifiers possible: {total} content "
            f"rows vs {distinct} distinct rowid values",
            duration_s=time.time() - start))
        return audit
    checks.append(IntegrityFinding(
        SCOPE_CONTENT_IDENTITY, "rowid_resolution_uniqueness", PASS,
        f"hidden rowid resolves and is unique across {total} row(s)",
        duration_s=time.time() - start))

    audit["content_rows"] = total
    audit["open_risk_classified"] = (
        "OPEN: hidden-rowid persistence relies on SQLite rowid stability "
        "for a table without an INTEGER PRIMARY KEY; VACUUM and table "
        "rebuilds can change it (Amendment 4 §C). The stable-integer-identity "
        "decision (DBT-R3-IDENTITY) is a separately tracked OPEN item — not "
        "resolved by this remediation."
    )
    return audit


# ── Amendment 8 — complete FTS configuration audit ──────────────────────────

def read_fts_configuration(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Read the FTS5 virtual-table configuration from the live schema. FTS5
    persists only limited runtime values in the shadow `config` table
    (version; runtime secure-delete when set); the declared definition comes
    from the sqlite_schema SQL. Unknown option keys or value/column
    mismatches are classified `unknown` (fail closed).
    """
    out: Dict[str, Any] = {"classification": "unknown", "details": {}}
    row = conn.execute(
        "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?",
        (FTS_TABLE,)).fetchone()
    if row is None or not row[0]:
        out["reason"] = f"{FTS_TABLE} virtual table missing"
        return out
    ddl = str(row[0])
    try:
        columns, options = parse_create_virtual_table(ddl)
    except ValueError as exc:
        out["reason"] = f"virtual table definition not parseable: {exc}"
        return out
    out["details"]["declared_columns"] = columns
    out["details"]["declared_options"] = options
    canonical_cols = canonical_columns()
    canonical_opts = canonical_fts_options()
    out["details"]["expected_columns"] = canonical_cols
    out["details"]["expected_options"] = canonical_opts

    try:
        config_rows = conn.execute(
            f"SELECT k, v FROM {FTS_TABLE}_config").fetchall()
    except sqlite3.Error as exc:
        out["reason"] = f"shadow config table unreadable: {exc}"
        return out
    out["details"]["shadow_config_rows"] = {str(k): v for (k, v) in config_rows}
    unrecognized = [str(k) for (k, _v) in config_rows
                    if str(k) not in FTS_CONFIG_RECOGNIZED_KEYS]
    out["details"]["unrecognized_config_keys"] = unrecognized

    if columns != canonical_cols or options != canonical_opts or unrecognized:
        out["classification"] = "unknown"
        out["reason"] = (
            f"FTS definition differs from the canonical contract "
            f"(columns={columns!r}, options={options!r}, "
            f"unrecognized_config_keys={unrecognized!r})"
        )
        return out
    out["classification"] = "canonical"
    return out


def audit_trigger_contract(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Amendment 8: classify each of the three synchronization triggers against
    the canonical definitions (normalized semantic comparison — not substring
    checks). Recognizes the documented historical unsafe ke_au so a legacy
    database is a *known* state (-> migration), and fails closed on anything
    unrecognized (or anything unexpected present on a working DB).
    """
    result: Dict[str, Any] = {"triggers": {}, "classification": "unknown"}
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_schema WHERE type='trigger' AND tbl_name=?",
        (CONTENT_TABLE,)).fetchall()
    named: Dict[str, Optional[str]] = {n: None for n in CANONICAL_TRIGGER_DDL}
    for name, sql in rows:
        named_key = str(name)
        if named_key in named and named[named_key] is None:
            named[named_key] = sql
    unknown_triggers = [str(n) for (n, _s) in rows
                        if str(n) not in CANONICAL_TRIGGER_DDL]
    for name in ("ke_ai", "ke_au", "ke_ad"):
        result["triggers"][name] = trigger_audit_classification(
            named.get(name), name)
    result["unknown_triggers"] = unknown_triggers

    classes = [result["triggers"][n] for n in ("ke_ai", "ke_au", "ke_ad")]
    if all(c == "canonical" for c in classes) and not unknown_triggers:
        result["classification"] = "canonical"
    elif all(c in ("canonical", "known_legacy_unsafe", "missing")
             for c in classes) and not unknown_triggers:
        result["classification"] = "legacy_compatible"
        result["reason"] = (
            "trigger set matches a documented historical definition; the "
            "dedicated maintenance migration must restore the canonical set "
            "and verify the index"
        )
    else:
        result["classification"] = "unknown"
        result["reason"] = (
            f"unrecognized trigger definitions present "
            f"(classes={result['triggers']}, unknown={unknown_triggers})"
        )
    return result


def read_secure_delete_policy(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Amendment 6 §A: report the actual FTS5 `secure-delete` configuration and
    the SQLite core `PRAGMA secure_delete` value. Read-only by contract —
    this module never changes either setting (scope boundary, §B).
    """
    out: Dict[str, Any] = {}
    try:
        out["core_pragma_secure_delete"] = conn.execute(
            "PRAGMA secure_delete").fetchone()[0]
    except sqlite3.Error as exc:
        out["core_pragma_secure_delete"] = f"error: {exc}"
    try:
        rows = conn.execute(f"SELECT k, v FROM {FTS_TABLE}_config").fetchall()
        cfg = {str(k): v for (k, v) in rows}
        out["fts5_secure_delete"] = cfg.get("secure-delete", "default (disabled)")
        out["fts5_config_keys"] = sorted(cfg.keys())
    except sqlite3.Error as exc:
        out["fts5_secure_delete"] = f"error: {exc}"
    out["interpretation"] = (
        "FTS5 secure-delete governs the FTS5 inverted index only; the SQLite "
        "core PRAGMA secure_delete (0=off) governs regular database pages. "
        "OFF is the FTS5 default: deleted or updated terms may remain in FTS5 "
        "structures until merge operations remove them, so content-table "
        "deletion, MATCH invisibility, and a passing integrity-check each "
        "prove different things — none proves physical erasure."
    )
    return out


# ── Startup readiness validation (Amendment 2B.3 — cheap, read-only) ────────

def validate_readiness(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Validation-only readiness check for normal application startup.

    Verifies the schema contract (content table, FTS definition, trigger
    set, indexes), the per-database migration marker + ledger row, and the
    content-row identity — without running integrity_check /
    foreign_key_check / FTS rebuilds (those belong to the maintenance and
    explicit-verification paths; Amendment 3 §C).
    """
    checks: List[IntegrityFinding] = []
    summary: Dict[str, Any] = {}
    t0 = time.time()

    # 1. Migration marker + per-database ledger row
    mark = None
    try:
        mark = conn.execute(
            f"SELECT value FROM {META_TABLE} WHERE key=?", (META_SCHEMA_STATE,)
        ).fetchone()
    except sqlite3.Error as exc:
        checks.append(IntegrityFinding(
            SCOPE_SCHEMA_CONTRACT, "migration_marker", FAIL,
            f"meta table unreadable: {exc}", duration_s=time.time() - t0))
    applied = None
    try:
        applied = conn.execute(
            f"SELECT COUNT(*) FROM {MIGRATIONS_TABLE} WHERE migration_id=? "
            "AND status='applied'", (MIGRATION_ID_V1,)
        ).fetchone()[0]
    except sqlite3.Error as exc:
        checks.append(IntegrityFinding(
            SCOPE_SCHEMA_CONTRACT, "migration_ledger", FAIL,
            f"ledger table unreadable: {exc}", duration_s=time.time() - t0))
    marked = bool(mark) and str(mark[0]) in SCHEMA_STATES_CURRENT
    if bool(applied) and marked:
        checks.append(IntegrityFinding(
            SCOPE_SCHEMA_CONTRACT, "migration_marker", PASS,
            f"schema_state={mark[0]!r}, migration {MIGRATION_ID_V1} applied"))
    else:
        checks.append(IntegrityFinding(
            SCOPE_SCHEMA_CONTRACT, "migration_marker", FAIL,
            f"marker={mark!r}, applied_count={applied!r} — migration pending, "
            "incomplete or unknown state"))
    summary["schema_marked"] = bool(marked)
    summary["migration_applied"] = bool(applied)

    # 2. Content table definition
    row = conn.execute(
        "SELECT sql FROM sqlite_schema WHERE type='table' AND name=?",
        (CONTENT_TABLE,)).fetchone()
    if row and normalize_sql(row[0]) == normalize_sql(CANONICAL_KNOWLEDGE_ENTRIES_DDL):
        checks.append(IntegrityFinding(
            SCOPE_SCHEMA_CONTRACT, "content_table_definition", PASS,
            "canonical content table definition"))
    else:
        checks.append(IntegrityFinding(
            SCOPE_SCHEMA_CONTRACT, "content_table_definition", FAIL,
            "content table missing or differs from the canonical definition"))
    summary["content_table_present"] = bool(row)

    # 3. FTS virtual table configuration (complete definition, Am. 8)
    fts_cfg = read_fts_configuration(conn)
    checks.append(IntegrityFinding(
        SCOPE_SCHEMA_CONTRACT, "fts_virtual_table_definition",
        PASS if fts_cfg.get("classification") == "canonical" else FAIL,
        fts_cfg.get("reason", "canonical FTS5 external-content definition")))
    summary["fts_configuration"] = fts_cfg.get("classification")

    # 4. Trigger contract
    trig = audit_trigger_contract(conn)
    checks.append(IntegrityFinding(
        SCOPE_SCHEMA_CONTRACT, "fts_trigger_contract",
        PASS if trig["classification"] == "canonical" else FAIL,
        trig.get("reason", "canonical trigger set"),
        duration_s=time.time() - t0))
    summary["trigger_contract"] = trig["classification"]

    # 5. Supporting indexes
    present = {str(n) for (n,) in conn.execute(
        "SELECT name FROM sqlite_schema WHERE type='index'").fetchall()}
    missing = [n for n in CANONICAL_INDEX_DDL if n not in present]
    checks.append(IntegrityFinding(
        SCOPE_SCHEMA_CONTRACT, "supporting_indexes",
        PASS if not missing else FAIL,
        "all canonical indexes present" if not missing
        else f"missing indexes: {missing}"))

    # 6. Content-row identity (Amendment 4 §A)
    identity = verify_content_row_identity(conn)
    checks.extend(identity["checks"])
    summary["content_row_identity"] = PASS if identity["passed"] else FAIL
    if identity["passed"]:
        summary["open_identity_risk"] = identity.get("open_risk_classified")

    return {
        "passed": all(f.status not in FAILED_STATUSES for f in checks),
        "checks": [f.as_dict() for f in checks],
        "summary": summary,
        "total_cost_s": round(sum(f.duration_s for f in checks), 6),
        "verified_at": time.time(),
    }
