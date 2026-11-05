"""
Rev 3 amendment tests — Amendment 3 (independent whole-database validation)
and Amendments 4/6/8 (content-row identity invariants, secure-delete
disposition, FTS configuration audit, VACUUM disposal audit).

Also covers the Amendment 3 §C operational contract: cheap schema-only
validation on startup; the four independent checks belong to the explicit
verification and maintenance paths and carry measured costs.
"""
import asyncio
import inspect
import os
import sqlite3
import time

import pytest

from core.memory.backends import sqlite_storage as storage_module
from core.memory.backends.sqlite_storage import SQLiteStorageBackend
from core.memory import sqlite_integrity as integrity_module
from core.memory import sqlite_migration as migration_module
from core.memory.sqlite_contract import (
    CONTENT_TABLE,
    FTS_TABLE,
    CANONICAL_TRIGGER_DDL,
    KNOWN_LEGACY_DEFINITIONS,
)
from core.memory.sqlite_integrity import (
    SCOPE_CONTENT_IDENTITY,
    SCOPE_FTS_INTERNAL,
    SCOPE_FOREIGN_KEYS,
    SCOPE_RETRIEVAL,
    SCOPE_STRUCTURAL,
    audit_trigger_contract,
    check_foreign_key_integrity,
    check_fts_integrity,
    check_fts_retrieval,
    check_structural_integrity,
    read_fts_configuration,
    read_secure_delete_policy,
    run_full_integrity_validation,
    validate_readiness,
    verify_content_row_identity,
)
from core.memory.sqlite_migration import initialize_schema


# A canonical-shaped FTS external-content DDL for the synthetic "known-bad"
# content tables used in the identity tests.
CANONICAL_FTS_EXTERNAL_TOY_DDL = (
    "CREATE VIRTUAL TABLE knowledge_entries_fts USING fts5("
    "content, summary, tags,"
    " content='knowledge_entries', content_rowid='rowid')")


def _canonical_db(tmp_path, name="canonical.db"):
    db_path = str(tmp_path / name)
    conn = sqlite3.connect(db_path)
    try:
        initialize_schema(conn)
    finally:
        conn.close()
    return db_path


class TestFourIndependentChecks:
    """Amendment 3 §A: four checks, independently scoped and measured."""

    @pytest.fixture
    def canonical_db(self, tmp_path):
        return _canonical_db(tmp_path)

    def test_all_four_checks_pass_and_are_measured(self, canonical_db):
        conn = sqlite3.connect(canonical_db)
        try:
            result = run_full_integrity_validation(conn)
        finally:
            conn.close()
        assert result["passed"] is True
        scopes = {f["scope"] for f in result["findings"]}
        assert scopes == {SCOPE_STRUCTURAL, SCOPE_FOREIGN_KEYS,
                          SCOPE_FTS_INTERNAL, SCOPE_RETRIEVAL}
        for f in result["findings"]:
            assert f["status"] in ("pass", "not_applicable")
            assert f["duration_s"] >= 0.0
            assert f["verified_at"] <= time.time()
        # Total cost is the sum of the independent per-check costs. The four
        # durations are floats of different magnitudes; sum() ordering makes
        # a few ulps of difference, so compare with an accounting tolerance
        # (still an order of magnitude tighter than any plausible duration).
        assert abs(result["total_cost_s"] -
                   sum(f["duration_s"] for f in result["findings"])) < 1e-5

    def test_structural_check_is_whole_database_and_separate_from_fts(
            self, canonical_db):
        """PRAGMA integrity_check covers every object in the file — the FTS
        rank=1 command is an ADDITIONAL independent check, not a substitute."""
        conn = sqlite3.connect(canonical_db)
        try:
            structural = check_structural_integrity(conn)
            fts_only = check_fts_integrity(conn)
        finally:
            conn.close()
        assert structural.status == "pass"
        assert structural.scope == SCOPE_STRUCTURAL
        assert fts_only.status == "pass"
        assert fts_only.scope == SCOPE_FTS_INTERNAL
        assert fts_only.scope != structural.scope

    def test_foreign_key_check_not_applicable_without_relationships(
            self, canonical_db):
        conn = sqlite3.connect(canonical_db)
        try:
            finding = check_foreign_key_integrity(conn)
        finally:
            conn.close()
        assert finding.status == "not_applicable"
        assert "no foreign-key" in finding.detail

    def test_retrieval_probes_are_real_match_queries(self, canonical_db):
        conn = sqlite3.connect(canonical_db)
        try:
            probe = check_fts_retrieval(conn)
        finally:
            conn.close()
        assert probe.status == "pass"
        assert "MATCH" in probe.detail


class TestValidationDetectsDamage:
    """The checks must actually FAIL when the database is damaged."""

    @pytest.fixture
    def db_path(self, tmp_path):
        return _canonical_db(tmp_path, "damaged.db")

    def test_fts_desync_is_detected_by_rank1_integrity_check(self, db_path):
        """Change the content table WITHOUT updating the FTS index (drop the
        sync triggers first, then mutate): the FTS `integrity-check(rank=1)`
        command must NOT pass — it must detect the desync. Whole-database
        PRAGMA integrity_check keeps passing (the b-tree is intact), which is
        exactly why the two checks are independent (Amendment 3 §A)."""
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO knowledge_entries (entry_id, layer, content,"
                " created_at, updated_at, accessed_at)"
                " VALUES ('k1', 'l1', 'xqzHonestBody words', 1, 1, 1)")
            conn.commit()
            # Disable synchronization so the content table can drift from FTS:
            for trig in ("ke_ai", "ke_au", "ke_ad"):
                conn.execute(f"DROP TRIGGER {trig}")
            conn.execute(
                "UPDATE knowledge_entries SET"
                " content='completely different text' WHERE entry_id='k1'")
            conn.commit()
            structural = check_structural_integrity(conn)
            fts = check_fts_integrity(conn)
        finally:
            conn.close()
        # The rank=1 command raises on mismatch, which check_fts_integrity
        # records as an ERROR finding (also in FAILED_STATUSES): the point is
        # that it never passes over the desync.
        assert structural.status == "pass"
        assert fts.status in ("fail", "error"), fts.as_dict()
        assert fts.status != "pass"
        assert fts.scope == SCOPE_FTS_INTERNAL

    def test_retrieval_probe_detects_missing_token(self, db_path):
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO knowledge_entries (entry_id, layer, content,"
                " created_at, updated_at, accessed_at)"
                " VALUES ('k1', 'l1', 'xqzFindMe body text', 1, 1, 1)")
            conn.commit()
            ok = check_fts_retrieval(conn, tokens=[("xqzFindMe", True)])
            bad = check_fts_retrieval(conn, tokens=[("xqzNoSuchToken", True)])
        finally:
            conn.close()
        assert ok.status == "pass"
        assert bad.status == "fail"
        assert "missing expected token" in bad.detail

    def test_retrieval_probe_detects_stale_token(self, db_path):
        """An ABSENT token must not match anything (Amendment 9 semantics)."""
        conn = sqlite3.connect(db_path)
        try:
            finding = check_fts_retrieval(
                conn, tokens=[("xqzNeverInsertedWord", False)])
        finally:
            conn.close()
        assert finding.status == "pass"

    def test_full_validation_reports_the_damage(self, db_path):
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO knowledge_entries (entry_id, layer, content,"
                " created_at, updated_at, accessed_at)"
                " VALUES ('k1', 'l1', 'xqzFullVal body words', 1, 1, 1)")
            conn.commit()
            for trig in ("ke_ai", "ke_au", "ke_ad"):
                conn.execute(f"DROP TRIGGER {trig}")
            conn.execute(
                "UPDATE knowledge_entries SET"
                " content='rotten drifted text' WHERE entry_id='k1'")
            conn.commit()
            result = run_full_integrity_validation(conn)
        finally:
            conn.close()
        assert result["passed"] is False
        failed = [f for f in result["findings"]
                  if f["status"] in ("fail", "error")]
        assert any(f["scope"] == SCOPE_FTS_INTERNAL for f in failed), \
            [f["scope"] + "/" + f["name"] for f in failed]


class TestForeignKeys:
    """Amendment 3 §A.2 — foreign_key_check runs whenever relationships exist."""

    @staticmethod
    def _db_with_fk(tmp_path, *, orphan):
        db_path = str(tmp_path / "fk.db")
        conn = sqlite3.connect(db_path)
        try:
            initialize_schema(conn)
            # A relationship outside the canonical schema (migrations may
            # introduce such relationships):
            conn.executescript("""
                CREATE TABLE entry_tags (
                    tag TEXT NOT NULL,
                    entry_id TEXT NOT NULL REFERENCES knowledge_entries(entry_id)
                );
            """)
            conn.execute(
                "INSERT INTO knowledge_entries (entry_id, layer, content,"
                " created_at, updated_at, accessed_at)"
                " VALUES ('k1', 'l1', 'referenced row', 1, 1, 1)")
            conn.execute(
                "INSERT INTO entry_tags(tag, entry_id) VALUES ('good', 'k1')")
            if orphan:
                conn.execute(
                    "INSERT INTO entry_tags(tag, entry_id)"
                    " VALUES ('orphan', 'zzz')")
            conn.commit()
            finding = check_foreign_key_integrity(conn)
            return finding
        finally:
            conn.close()

    def test_fk_violation_detected(self, tmp_path):
        finding = self._db_with_fk(tmp_path, orphan=True)
        assert finding.status == "fail"
        assert finding.scope == SCOPE_FOREIGN_KEYS

    def test_fk_consistency_passes_after_cleanup(self, tmp_path):
        finding = self._db_with_fk(tmp_path, orphan=False)
        assert finding.status == "pass"


class TestContentRowIdentity:
    """Amendment 4 §A — live verification of content-row identity invariants."""

    @pytest.fixture
    def canonical_db(self, tmp_path):
        db_path = _canonical_db(tmp_path, "ident.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO knowledge_entries (entry_id, layer, content,"
                " created_at, updated_at, accessed_at)"
                " VALUES ('a', 'l1', 'row one', 1, 1, 1)")
            conn.execute(
                "INSERT INTO knowledge_entries (entry_id, layer, content,"
                " created_at, updated_at, accessed_at)"
                " VALUES ('b', 'l1', 'row two', 1, 1, 1)")
            conn.commit()
        finally:
            conn.close()
        return db_path

    def test_identity_passes_on_canonical_db(self, canonical_db):
        conn = sqlite3.connect(canonical_db)
        try:
            audit = verify_content_row_identity(conn)
        finally:
            conn.close()
        assert audit["passed"] is True
        names = [c.name for c in audit["checks"]]
        assert "rowid_alias_columns" in names
        assert "rowid_resolution_uniqueness" in names
        assert audit["content_rowid"] == "rowid"
        assert audit["content_rows"] == 2

    def test_identity_fails_on_without_rowid_table(self, tmp_path):
        db_path = str(tmp_path / "wor.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE knowledge_entries ("
                " entry_id TEXT PRIMARY KEY, content TEXT, summary TEXT,"
                " tags TEXT) WITHOUT ROWID")
            conn.execute(CANONICAL_FTS_EXTERNAL_TOY_DDL)
            conn.commit()
            audit = verify_content_row_identity(conn)
        finally:
            conn.close()
        assert audit["passed"] is False
        statuses = {c.name: c.status for c in audit["checks"]}
        assert statuses.get("without_rowid") == "fail"

    def test_identity_fails_when_rowid_is_shadowed(self, tmp_path):
        """A declared column named like a hidden-rowid alias invalidates the
        `content_rowid='rowid'` configuration (Amendment 4 §A)."""
        db_path = str(tmp_path / "shadow.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                'CREATE TABLE knowledge_entries ('
                ' entry_id TEXT PRIMARY KEY, content TEXT, summary TEXT,'
                ' tags TEXT, "oid" TEXT)')
            conn.execute(CANONICAL_FTS_EXTERNAL_TOY_DDL)
            conn.commit()
            audit = verify_content_row_identity(conn)
        finally:
            conn.close()
        assert audit["passed"] is False
        found = [c for c in audit["checks"]
                 if c.name == "rowid_alias_columns" and c.status == "fail"]
        assert found, [c.as_dict() for c in audit["checks"]]
        assert "oid" in found[0].detail
        assert found[0].scope == SCOPE_CONTENT_IDENTITY

    def test_open_risk_is_classified_not_hidden(self, canonical_db):
        """Amendment 4 §B: the hidden-rowid persistence risk must stay
        VISIBLE in every identity result — this remediation must not pretend
        to have resolved it (DBT-R3-IDENTITY stays OPEN)."""
        conn = sqlite3.connect(canonical_db)
        try:
            audit = verify_content_row_identity(conn)
        finally:
            conn.close()
        risk_text = audit.get("open_risk_classified") or ""
        assert "OPEN" in risk_text
        assert "DBT-R3-IDENTITY" in risk_text
        assert "VACUUM" in risk_text


class TestFTSConfigurationAudit:
    """Amendment 8 — complete-definition audit, no substring checks."""

    def test_canonical_definition_classified_canonical(self, tmp_path):
        db_path = _canonical_db(tmp_path, "audit.db")
        conn = sqlite3.connect(db_path)
        try:
            cfg = read_fts_configuration(conn)
        finally:
            conn.close()
        assert cfg["classification"] == "canonical"
        assert cfg["details"]["declared_columns"] == ["content", "summary",
                                                      "tags"]
        assert cfg["details"]["declared_options"] == {
            "content": "knowledge_entries", "content_rowid": "rowid"}
        assert cfg["details"]["unrecognized_config_keys"] == []

    def test_column_mismatch_is_unknown(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(
                "CREATE TABLE knowledge_entries ("
                " entry_id TEXT PRIMARY KEY, content TEXT, summary TEXT,"
                " tags TEXT, extra TEXT)")
            conn.execute(
                "CREATE VIRTUAL TABLE knowledge_entries_fts USING fts5("
                "content, summary, tags, extra,"
                " content='knowledge_entries', content_rowid='rowid')")
            conn.commit()
            cfg = read_fts_configuration(conn)
        finally:
            conn.close()
        assert cfg["classification"] == "unknown"
        assert "differs from the canonical contract" in cfg["reason"]

    def test_option_mismatch_is_unknown(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(
                "CREATE TABLE knowledge_entries ("
                " entry_id TEXT PRIMARY KEY, content TEXT, summary TEXT,"
                " tags TEXT)")
            conn.execute(
                "CREATE VIRTUAL TABLE knowledge_entries_fts USING fts5("
                "content, summary, tags,"
                " content='knowledge_entries', content_rowid='rowid',"
                " tokenize='porter')")
            conn.commit()
            cfg = read_fts_configuration(conn)
        finally:
            conn.close()
        assert cfg["classification"] == "unknown"

    def test_unknown_shadow_config_key_fails_closed(self, tmp_path):
        db_path = _canonical_db(tmp_path, "cfgkw.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                f"INSERT INTO {FTS_TABLE}_config(k, v)"
                " VALUES ('mystery_key', '1')")
            conn.commit()
            cfg = read_fts_configuration(conn)
        finally:
            conn.close()
        assert cfg["classification"] == "unknown"
        assert cfg["details"]["unrecognized_config_keys"] == ["mystery_key"]

    def test_recognized_runtime_keys_do_not_fail(self, tmp_path):
        db_path = _canonical_db(tmp_path, "cfgok.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO {FTS_TABLE}_config(k, v)"
                " VALUES ('secure-delete', '0')")
            conn.commit()
            cfg = read_fts_configuration(conn)
        finally:
            conn.close()
        assert cfg["classification"] == "canonical"
        assert cfg["details"]["shadow_config_rows"].get("secure-delete") == "0"


class TestTriggerContractAudit:
    """Amendment 8 — triggers: canonical / known-historical / unknown."""

    def test_canonical_set(self, tmp_path):
        db_path = _canonical_db(tmp_path, "trig.db")
        conn = sqlite3.connect(db_path)
        try:
            audit = audit_trigger_contract(conn)
        finally:
            conn.close()
        assert audit["classification"] == "canonical"
        assert audit["unknown_triggers"] == []
        for name in ("ke_ai", "ke_au", "ke_ad"):
            assert audit["triggers"][name] == "canonical"

    def test_documented_legacy_ke_au_is_recognized(self, tmp_path):
        """A pre-Rev3 database is a KNOWN state — the audit says
        legacy_compatible with a maintenance remediation (never canonical,
        never unknown)."""
        db_path = str(tmp_path / "legacy_trig.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE knowledge_entries ("
                " entry_id TEXT PRIMARY KEY, content TEXT, summary TEXT,"
                " tags TEXT)")
            conn.execute(CANONICAL_FTS_EXTERNAL_TOY_DDL)
            conn.execute(CANONICAL_TRIGGER_DDL["ke_ai"])
            conn.execute(CANONICAL_TRIGGER_DDL["ke_ad"])
            conn.execute(KNOWN_LEGACY_DEFINITIONS["ke_au_raw_update"])
            conn.commit()
            audit = audit_trigger_contract(conn)
        finally:
            conn.close()
        assert audit["classification"] == "legacy_compatible"
        assert audit["triggers"]["ke_au"] == "known_legacy_unsafe"
        assert audit["triggers"]["ke_ai"] == "canonical"
        assert audit["triggers"]["ke_ad"] == "canonical"
        assert audit["unknown_triggers"] == []
        assert "maintenance" in audit["reason"]

    def test_unknown_trigger_fails_closed(self, tmp_path):
        db_path = _canonical_db(tmp_path, "unknown_trig.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TRIGGER sneaky AFTER INSERT ON knowledge_entries"
                " BEGIN SELECT 1; END")
            conn.commit()
            audit = audit_trigger_contract(conn)
        finally:
            conn.close()
        assert audit["classification"] == "unknown"
        assert "sneaky" in audit["unknown_triggers"]

    def test_missing_trigger_is_reported(self, tmp_path):
        db_path = _canonical_db(tmp_path, "missing_trig.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DROP TRIGGER ke_ad")
            conn.commit()
            audit = audit_trigger_contract(conn)
        finally:
            conn.close()
        assert audit["triggers"]["ke_ad"] == "missing"
        # A missing trigger is a KNOWN legacy state that migration repairs —
        # the audit reports it as legacy_compatible (not canonical), and the
        # constructor still refuses because validate_readiness fails (Am 2).
        assert audit["classification"] == "legacy_compatible"
        assert "maintenance" in audit["reason"]


class TestAmendment3StartupCostContract:
    """Amendment 3 §C: startup validation is cheap and NOT full validation."""

    @pytest.fixture
    def db_path(self, tmp_path):
        return _canonical_db(tmp_path, "cost.db")

    def test_startup_validation_is_schema_only(self, db_path):
        conn = sqlite3.connect(db_path)
        try:
            t0 = time.time()
            validation = validate_readiness(conn)
            elapsed = time.time() - t0
            findings = {c["name"] for c in validation["checks"]}
        finally:
            conn.close()
        assert validation["passed"]
        # full-validation check names must be ABSENT from the startup path:
        assert findings.isdisjoint(
            {"integrity_check", "foreign_key_check", "fts_integrity_check"})
        assert elapsed < 1.0

    def test_heartbeat_never_runs_full_validation(self, db_path):
        """Ordinary health_report() is the heartbeat input; Amendment 3 §C
        prohibits whole-database validation there."""
        backend = SQLiteStorageBackend(db_path, runtime_gate="acknowledge")
        original = storage_module.run_full_integrity_validation
        calls = {"n": 0}

        def spy(*a, **k):
            calls["n"] += 1
            return original(*a, **k)

        storage_module.run_full_integrity_validation = spy
        try:
            report = backend.health_report()
        finally:
            storage_module.run_full_integrity_validation = original
        assert calls["n"] == 0
        assert report["backend"] == "SQLiteStorageBackend"
        assert report["readiness"]["status"] == \
            "ready_degraded_runtime_not_supported"

    def test_explicit_verification_runs_full_validation_and_is_measured(
            self, db_path):
        backend = SQLiteStorageBackend(db_path, runtime_gate="acknowledge")
        outcome = asyncio.run(backend.verify_integrity_now())
        assert outcome["integrity"]["passed"] is True
        assert outcome["integrity"]["total_cost_s"] >= 0
        assert len(outcome["integrity"]["findings"]) == 4
        assert outcome["content_row_identity"]["passed"] is True
        recorded = backend.last_full_validation
        assert recorded is not None
        assert recorded["passed"] is True
        assert recorded["total_cost_s"] >= 0


class TestAmendment4DisposalAudit:
    """No production sqlite code path may VACUUM (Amendment 4 §B/§D)."""

    ALL_MODULES = (storage_module, integrity_module, migration_module)

    def test_no_vacuum_execution_in_production_code(self):
        for module in self.ALL_MODULES:
            src = inspect.getsource(module).splitlines()
            for idx, line in enumerate(src, start=1):
                low = line.lower()
                if "vacuum" in low and ".execute" in low:
                    pytest.fail(
                        f"{module.__name__} line {idx} appears to EXECUTE "
                        f"VACUUM: {line.strip()}")

    def test_backup_uses_online_backup_api_not_vacuum(self, tmp_path):
        db_path = _canonical_db(tmp_path, "bup.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO knowledge_entries (entry_id, layer, content,"
                " created_at, updated_at, accessed_at)"
                " VALUES ('a', 'l1', 'backup body text', 1, 1, 1)")
            conn.commit()
        finally:
            conn.close()
        dest_path = str(tmp_path / "bup-copy.db")
        from core.memory.sqlite_migration import create_online_backup
        outcome = create_online_backup(db_path, dest_path)
        assert outcome["ok"] is True
        assert outcome["identity_preserved"] is True
        assert outcome["method"] == \
            "sqlite3.Connection.backup (Online Backup API)"
        assert "VACUUM INTO is not used" in outcome["note"]

        # The copy is a real, consistent, searchable database:
        copy_conn = sqlite3.connect(dest_path)
        try:
            result = run_full_integrity_validation(
                copy_conn, retrieval_tokens=[("backup", True)])
        finally:
            copy_conn.close()
        assert result["passed"] is True

    def test_vacuum_into_destination_is_rejected_if_exists(self, tmp_path):
        """create_online_backup never overwrites a destination (it is a
        snapshot-preserving tool, not a compact/replace tool)."""
        db_path = _canonical_db(tmp_path, "bup2.db")
        dest_path = str(tmp_path / "bup2-copy.db")
        dest_conn = sqlite3.connect(dest_path)
        dest_conn.execute("CREATE TABLE marker(x)")
        dest_conn.commit()
        dest_conn.close()
        from core.memory.sqlite_migration import create_online_backup
        outcome = create_online_backup(db_path, dest_path)
        assert outcome["ok"] is False
        assert "destination already exists" in outcome["error"]


class TestAmendment6SecureDeleteDisposition:
    """Amendment 6: investigate + report only; NEVER enable."""

    def test_secure_delete_reported_read_only(self, tmp_path):
        db_path = _canonical_db(tmp_path, "sd.db")
        conn = sqlite3.connect(db_path)
        try:
            before_cfg = conn.execute(
                f"SELECT k, v FROM {FTS_TABLE}_config").fetchall()
            before_meta = conn.execute(
                "SELECT key, value FROM _ocbrain_memory_meta").fetchall()
            policy = read_secure_delete_policy(conn)
            after_cfg = conn.execute(
                f"SELECT k, v FROM {FTS_TABLE}_config").fetchall()
            after_meta = conn.execute(
                "SELECT key, value FROM _ocbrain_memory_meta").fetchall()
        finally:
            conn.close()
        assert policy["core_pragma_secure_delete"] == 0
        assert "disabled" in str(policy["fts5_secure_delete"])
        # The report must carry the honest interpretation (§A): FTS TERMS may
        # survive — MATCH invisibility and integrity are different properties;
        # none of them proves physical erasure.
        assert "none proves physical erasure" in policy["interpretation"]
        assert before_cfg == after_cfg
        assert before_meta == after_meta

    def test_no_secure_delete_write_in_integrity_module(self):
        """Static: the integrity module must contain no path that ENABLES
        secure-delete (that decision is explicitly out of scope, §B)."""
        src = inspect.getsource(integrity_module).splitlines()
        for idx, line in enumerate(src, start=1):
            low = line.strip().lower()
            if "secure-delete" in low and "insert" in low and (
                    low.lstrip().startswith(("c", "e"))):
                pytest.fail(
                    f"secure-delete ENABLE at integrity module line {idx}: "
                    f"{line.strip()}")
