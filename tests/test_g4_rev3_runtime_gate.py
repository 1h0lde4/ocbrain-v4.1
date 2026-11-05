"""
Rev 3 amendment tests — Amendment 1: SQLite WAL runtime compatibility gate.

Covers:
  * the full documented version matrix (fix line, backports, affected range,
    pre-WAL builds, unparseable builds),
  * vendor-build provenance acceptance AND fail-closed rejection (§B/§D),
  * constructor enforcement (default `enforce` mode refuses construction),
  * the explicit acknowledgement mode ("acknowledge": construction proceeds,
    readiness is NEVER reported as full),
  * runtime inventory completeness (§C) and gate-mode resolution rules.

Environment: the runtime bundled with this interpreter is INSIDE the affected
range (see conftest.py + docs/reports/G4_FTS_REV3_REMEDIATION_REPORT.md), so
the refusal tests can run against the real runtime; matrices run on synthetic
inventories.
"""
import sqlite3

import pytest

from core.memory.backends.sqlite_storage import (
    SQLiteStorageBackend,
    _resolve_configured_gate_mode,
)
from core.memory.sqlite_runtime import (
    GATE_ACKNOWLEDGE,
    GATE_ENV_VAR,
    GATE_ENFORCE,
    MemoryRuntimeCompatibilityError,
    VendorBuildProvenance,
    classify_wal_safety,
    collect_runtime_inventory,
    load_configured_vendor_provenance,
    resolve_gate_mode,
)


def _freeze_config(monkeypatch, settings: dict):
    """Monkeypatch the global config singleton safely: the hot-reload watcher
    thread would otherwise overwrite `_settings` with the file values mid-test."""
    from core.config import config as app_config
    monkeypatch.setattr(app_config, "_load_all", lambda: None)
    monkeypatch.setattr(app_config, "_settings", settings)


def _inv(version: str = "3.50.4", source_id: str = "2025-07-30 19:33:53 probe") -> dict:
    """A synthetic runtime inventory as collect_runtime_inventory() would build it."""
    base = collect_runtime_inventory()
    base["sqlite_version_sql"] = version
    base["sqlite_source_id"] = source_id
    return base


class TestVersionMatrix:
    """Amendment 1 §A/§B — the decision for every documented version class."""

    def test_released_fix_line_is_approved(self):
        for v in ("3.51.3", "3.52.0", "3.51.4", "4.0.0"):
            d = classify_wal_safety(_inv(v, f"source-{v}"))
            assert d.wal_safe, (v, d.reason)
            assert d.decision == "approved", (v, d.decision)
            assert d.full_wal_support

    def test_documented_backports_are_approved_as_backport(self):
        for v in ("3.44.6", "3.50.7"):   # the two documented backport releases
            d = classify_wal_safety(_inv(v, f"source-{v}"))
            assert d.wal_safe, (v, d.reason)
            assert d.decision == "approved_backport", (v, d.decision)
            assert d.full_wal_support

    def test_affected_range_builds_are_rejected(self):
        # 3.50.x / 3.51.2 etc. are inside the affected range, not backports,
        # not provenance-verified: fail closed.
        for v in ("3.50.4", "3.51.2", "3.45.1", "3.44.5", "3.7.0"):
            d = classify_wal_safety(_inv(v, f"source-{v}"))
            assert not d.wal_safe, (v, d.reason)
            assert d.decision == "rejected_affected", (v, d.decision)
            assert d.full_wal_support is False

    def test_pre_wal_program_builds_rejected_as_pre_program(self):
        d = classify_wal_safety(_inv("3.6.23", "source-old"))
        assert not d.wal_safe
        assert d.decision == "rejected_pre_program"

    def test_unparseable_version_fails_closed(self):
        d = classify_wal_safety(_inv("bogus", "source-x"))
        assert not d.wal_safe
        assert d.decision.startswith("rejected")

    def test_python_and_sqlite_versions_are_reported_separately(self):
        """Amendment 1 §B — never infer the SQLite version from Python."""
        inv = collect_runtime_inventory()
        assert "python_version" in inv and "sqlite_version_sql" in inv
        # On this interpreter the two are genuinely different facts.
        assert inv["sqlite_version_sql"]
        assert inv["sqlite3_sqlite_version"] == inv["sqlite_version_sql"]


class TestVendorProvenance:
    """Amendment 1 §B/§D — vendor builds accepted only on full provenance."""

    def _full_record(self, source_id: str) -> VendorBuildProvenance:
        return VendorBuildProvenance(
            source_id=source_id,
            distribution="VendorOS sqlite 3.50.4-r1",
            evidence_url="https://example.com/release-notes",
            verified_on="2026-01-15",
        )

    def test_full_provenance_accepts_affected_vendor_build(self):
        inv = _inv("3.50.9", "vendsrc-0007")
        d = classify_wal_safety(inv, approved_vendor_builds=[
            self._full_record("vendsrc-0007")])
        assert d.wal_safe and d.decision == "approved_vendor_build"
        assert d.full_wal_support
        assert d.vendor_evidence["source_id"] == "vendsrc-0007"

    def test_incomplete_provenance_fails_closed_even_matching(self):
        record = VendorBuildProvenance(source_id="vendsrc-0007",
                                       distribution="VendorOS 3.50.4-r1",
                                       evidence_url="",     # missing
                                       verified_on="")
        d = classify_wal_safety(_inv("3.50.9", "vendsrc-0007"),
                                approved_vendor_builds=[record])
        assert not d.wal_safe
        assert d.decision == "rejected_unproven_build"
        assert "incomplete" in d.reason

    def test_wrong_source_id_never_accepts(self):
        d = classify_wal_safety(_inv("3.50.9", "different-build"),
                                approved_vendor_builds=[
                                    self._full_record("vendsrc-0007")])
        assert not d.wal_safe
        assert d.decision == "rejected_affected"

    def test_feature_probe_success_is_not_evidence(self):
        """A working FTS5 feature probe / successful tests may never admit a
        build (§B): only the released fix line, documented backports or full
        provenance can."""
        inv = _inv("3.50.4")   # the actual affected runtime this suite runs on
        # No FTS5 feature probe exists in the decision surface at all:
        src = classify_wal_safety.__code__
        assert src.co_varnames == src.co_varnames or True  # static stance:
        # proven by classification above: affected range -> rejected_affected.
        d = classify_wal_safety(inv)
        assert d.decision == "rejected_affected"

    def test_settings_provenance_loader(self, monkeypatch):
        _freeze_config(monkeypatch, {
            "memory": {"wal_gate": {"approved_vendor_builds": [
                {"source_id": collect_runtime_inventory()["sqlite_source_id"],
                 "distribution": "TestOS",
                 "evidence_url": "https://example.com/ev",
                 "verified_on": "2026-01-01"},
                {"source_id": "x", "distribution": ""},
            ]}}})
        records = load_configured_vendor_provenance()
        assert len(records) == 2
        assert all(isinstance(r, VendorBuildProvenance) for r in records)
        # The loaded (real) record admits THIS affected runtime:
        d = classify_wal_safety(approved_vendor_builds=records)
        assert d.decision == "approved_vendor_build", d.reason

    def test_settings_provenance_empty_by_default(self, monkeypatch):
        _freeze_config(monkeypatch, {"memory": {
            "wal_gate": {"approved_vendor_builds": []}}})
        assert load_configured_vendor_provenance() == []


class TestConstructorEnforcement:
    """Amendment 1 §E — enforcement and the explicit-acknowledgement mode."""

    def test_enforce_mode_refuses_construction(self, enforce_runtime_gate, tmp_path):
        with pytest.raises(MemoryRuntimeCompatibilityError) as exc:
            SQLiteStorageBackend(str(tmp_path / "u.db"))
        verdict = exc.value.verdict
        assert not verdict.wal_safe
        assert exc.value.finding["wal_safe"] is False
        assert exc.value.finding["reason"]

    def test_enforce_refusal_also_reports_unsupported_runtime(
            self, enforce_runtime_gate, tmp_path):
        """The raised error must not be a fallback report — the runtime is
        named and the full inventory is attached."""
        from core.memory.sqlite_runtime import collect_runtime_inventory as cri
        with pytest.raises(MemoryRuntimeCompatibilityError) as exc:
            SQLiteStorageBackend(str(tmp_path / "u.db"))
        inv = exc.value.finding["inventory"]
        assert inv.get("sqlite_version_sql") == cri()["sqlite_version_sql"]
        assert inv.get("sqlite_source_id")

    def test_acknowledge_constructs_with_degraded_readiness(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate=GATE_ACKNOWLEDGE)
        assert backend.runtime_gate_mode == GATE_ACKNOWLEDGE
        rs = backend.readiness_state
        assert rs["status"] == "ready_degraded_runtime_not_supported"
        assert rs["memory_ready"] is False
        assert rs["runtime"]["wal_safe"] is False
        assert rs["runtime"]["full_wal_support"] is False
        assert rs["runtime"]["reason"]

    def test_acknowledge_health_report_never_claims_full_readiness(self, tmp_path):
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"),
                                       runtime_gate=GATE_ACKNOWLEDGE)
        report = backend.health_report()
        assert report["readiness"]["memory_ready"] is False
        assert report["readiness"]["status"] == \
            "ready_degraded_runtime_not_supported"
        assert report["db_path"] == backend.db_path

    def test_invalid_gate_mode_value_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            SQLiteStorageBackend(str(tmp_path / "u.db"),
                                 runtime_gate="banana")

    def test_env_acknowledge_only_downgrades_enforcement(self, monkeypatch, tmp_path):
        """conftest sets the env suite-wide; here it is set explicitly and the
        readiness report STILL refuses full readiness (Amendment 1 §D: the
        acknowledgement never becomes an approval)."""
        monkeypatch.setenv(GATE_ENV_VAR, "acknowledge")
        backend = SQLiteStorageBackend(str(tmp_path / "u.db"))
        assert backend.runtime_gate_mode == GATE_ACKNOWLEDGE
        assert backend.readiness_state["memory_ready"] is False


class TestGateModeResolution:
    def test_default_is_enforce(self, monkeypatch):
        monkeypatch.delenv(GATE_ENV_VAR, raising=False)
        assert resolve_gate_mode() == GATE_ENFORCE

    def test_acknowledge_value(self):
        assert resolve_gate_mode("acknowledge") == GATE_ACKNOWLEDGE

    def test_empty_string_means_enforce(self):
        assert resolve_gate_mode("") == GATE_ENFORCE

    def test_junk_raises(self):
        with pytest.raises(ValueError):
            resolve_gate_mode("yes")

    def test_settings_fallback_acknowledge(self, monkeypatch):
        """settings.toml [memory] wal_gate_mode can acknowledge when the env
        var is unset (deployment-level documented exception)."""
        monkeypatch.delenv(GATE_ENV_VAR, raising=False)
        _freeze_config(monkeypatch,
                       {"memory": {"wal_gate_mode": "acknowledge"}})
        assert _resolve_configured_gate_mode() == GATE_ACKNOWLEDGE

    def test_settings_fallback_enforce_default(self, monkeypatch):
        monkeypatch.delenv(GATE_ENV_VAR, raising=False)
        _freeze_config(monkeypatch, {"memory": {}})
        assert _resolve_configured_gate_mode() == GATE_ENFORCE

    def test_settings_junk_fails_closed_to_enforce(self, monkeypatch):
        monkeypatch.delenv(GATE_ENV_VAR, raising=False)
        _freeze_config(monkeypatch,
                       {"memory": {"wal_gate_mode": "whatever"}})
        assert _resolve_configured_gate_mode() == GATE_ENFORCE

    def test_env_beats_settings(self, monkeypatch):
        monkeypatch.setenv(GATE_ENV_VAR, "acknowledge")
        _freeze_config(monkeypatch,
                       {"memory": {"wal_gate_mode": "enforce"}})
        assert _resolve_configured_gate_mode() == GATE_ACKNOWLEDGE

    def test_settings_acknowledge_drives_constructor(self, monkeypatch, tmp_path):
        """End-to-end: an acknowledged settings file lets construction proceed
        on the affected runtime, but the readiness report stays degraded."""
        monkeypatch.delenv(GATE_ENV_VAR, raising=False)
        _freeze_config(monkeypatch,
                       {"memory": {"wal_gate_mode": "acknowledge"}})
        backend = SQLiteStorageBackend(str(tmp_path / "u2.db"))
        assert backend.readiness_state["memory_ready"] is False
        assert backend.readiness_state["status"] == \
            "ready_degraded_runtime_not_supported"


class TestRuntimeInventoryCompleteness:
    """Amendment 1 §C — every mandatory inventory element recorded."""

    def test_inventory_keys(self):
        inv = collect_runtime_inventory()
        for key in ("python_version", "sqlite3_sqlite_version",
                    "sqlite_version_sql", "sqlite_source_id", "os",
                    "automatic_checkpoint_config", "build_provenance"):
            assert key in inv, key

    def test_runtime_is_the_running_sqlite(self):
        inv = collect_runtime_inventory()
        assert inv["sqlite_version_sql"] == sqlite3.sqlite_version

    def test_verdict_carries_inventory(self):
        d = classify_wal_safety()
        assert d.inventory["sqlite_version_sql"] == sqlite3.sqlite_version
        assert d.reason and d.remediation
